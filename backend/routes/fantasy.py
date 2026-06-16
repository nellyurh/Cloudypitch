"""Fantasy: WC2026 squad builder + gameweek settlement."""
from fastapi import APIRouter, Depends, HTTPException
from db import get_db, utcnow_iso
from models import FantasySquadIn, new_id
from fantasy_scoring import compute_player_points, aggregate_player_stats_from_events
from scoring import compute_card_boost
from typing import Optional
import auth as a

router = APIRouter(prefix="/api/fantasy", tags=["fantasy"])


@router.get("/competition")
async def get_competition():
    db = get_db()
    comp = await db.fantasy_competitions.find_one({"id": "fantasy-wc2026"}, {"_id": 0})
    return {"competition": comp}


@router.get("/players")
async def list_fantasy_players(limit: int = 2000, game_id: Optional[str] = None):
    """Player pool. With `game_id`, returns the subset eligible for that
    mini-game (driven by the game's eligible countries / teams). Without it,
    returns the full WC2026 pool used by the main 15-man squad builder.
    """
    db = get_db()
    # When the caller passes a game_id, narrow the pool to that mini-game.
    if game_id:
        g = await db.wc_games.find_one({"id": game_id}, {"_id": 0})
        if not g:
            raise HTTPException(status_code=404, detail="Game not found")
        # Prefer `eligible_team_ids` (exact team IDs) over country-name string
        # matching, since FIFA / Sportmonks naming drifts (e.g. "Czechia" vs
        # "Czech Republic", "South Korea" vs "Korea Republic") and would drop
        # half the squad pool on a group game.
        team_ids = list(g.get("eligible_team_ids") or [])
        countries = await _eligible_countries_for_game(db, g)
        if team_ids:
            q = {"team_id": {"$in": team_ids}}
            players = await db.players.find(q, {"_id": 0}).sort("name", 1).limit(limit).to_list(length=limit)
            # Backstop: if team_id pool is empty (e.g. round games where IDs
            # aren't denormalised), fall back to country-name match.
            if not players and countries:
                players = await db.players.find(
                    {"is_wc_2026": True, "country": {"$in": list(countries)}},
                    {"_id": 0},
                ).sort("name", 1).limit(limit).to_list(length=limit)
            return {"players": players, "source": "wc2026_filtered",
                    "team_ids": team_ids, "countries": list(countries),
                    "rules": _pick_rules_for_game(g)}
        if countries:
            players = await db.players.find(
                {"is_wc_2026": True, "country": {"$in": list(countries)}},
                {"_id": 0},
            ).sort("name", 1).limit(limit).to_list(length=limit)
            return {"players": players, "source": "wc2026_filtered", "countries": list(countries), "rules": _pick_rules_for_game(g)}

    # Default — full WC2026 pool.
    players = await db.players.find({"is_wc_2026": True}, {"_id": 0}).sort("name", 1).limit(limit).to_list(length=limit)
    if players:
        return {"players": players, "source": "wc2026"}
    # Fallback synthetic pool (used before WC squad ingest finishes)
    teams = await db.teams.find({"sport_slug": "football"}, {"_id": 0}).limit(200).to_list(length=200)
    POSITIONS = ["GK", "DEF", "DEF", "DEF", "MID", "MID", "MID", "FWD", "FWD"]
    PRICE = {"GK": 5.0, "DEF": 5.5, "MID": 7.5, "FWD": 9.0}
    out = []
    for t in teams[:60]:
        for i in range(9):
            pos = POSITIONS[i]
            out.append({
                "id": f"{t['id']}-p{i+1}",
                "name": f"{t.get('name', 'Player')} #{i+1}",
                "team_id": t["id"], "team_name": t.get("name"), "team_logo": t.get("logo_url", ""),
                "position": pos, "price": PRICE[pos] + (i * 0.1),
                "country": t.get("country") or "World",
            })
    return {"players": out[:limit], "source": "synthetic"}


# ── Mini-game eligibility / pick-rule helpers ──────────────────────────────

async def _eligible_countries_for_game(db, g: dict) -> set[str]:
    """Resolve the country names eligible for `g`. Prefers the denormalised
    `eligible_country_names` field when present (set by the backfill script).
    Falls back to live joins on `match_info`, `wc2026_groups`, etc.
    """
    # Fast path — denormalised field (populated by backfill_wc_games_match_info).
    if g.get("eligible_country_names"):
        return set(g["eligible_country_names"])

    gt = g.get("game_type")
    out: set[str] = set()

    if gt == "match" and g.get("match_info"):
        mi = g["match_info"]
        for k in ("home_team_name", "away_team_name", "home", "away"):
            if isinstance(mi.get(k), str):
                out.add(mi[k])

    elif gt == "group" and g.get("group_letter"):
        grp = await db.wc2026_groups.find_one({"group": g["group_letter"]}, {"_id": 0})
        for t in (grp or {}).get("teams", []):
            out.add(t)

    elif gt == "matchday" and g.get("matchday"):
        ms = await db.matches.find(
            {"competition_kind": "wc2026", "matchday": g["matchday"]},
            {"_id": 0, "home_team_name": 1, "away_team_name": 1},
        ).to_list(length=64)
        for m in ms:
            if m.get("home_team_name"): out.add(m["home_team_name"])
            if m.get("away_team_name"): out.add(m["away_team_name"])

    elif gt == "round":
        # If we know the round label, prefer that; else fall back to all WC2026.
        if g.get("round_label"):
            ms = await db.matches.find(
                {"competition_kind": "wc2026", "round_label": g["round_label"]},
                {"_id": 0, "home_team_name": 1, "away_team_name": 1},
            ).to_list(length=64)
            for m in ms:
                if m.get("home_team_name"): out.add(m["home_team_name"])
                if m.get("away_team_name"): out.add(m["away_team_name"])

    # Fallback: if we couldn't resolve, use all WC2026 countries (no narrowing).
    if not out:
        all_g = await db.wc2026_groups.find({}, {"_id": 0}).to_list(length=12)
        for grp in all_g:
            out.update(grp.get("teams", []))
    return out


def _pick_rules_for_game(g: dict) -> dict:
    """Pick rules per game_type — squad size, budget, per-country caps."""
    gt = g.get("game_type")
    if gt == "match":
        # 8/7 split across the two teams playing the match.
        # XI must field at least 5 from each side (fair-play rule).
        return {"total": 15, "budget": 100, "max_per_country": 8,
                "starters_min_per_country": 5,
                "slots": {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}}
    if gt == "group":
        # 4 teams in the group, 20-man squad, 5 per country max.
        return {"total": 20, "budget": 150, "max_per_country": 5,
                "slots": {"GK": 3, "DEF": 7, "MID": 6, "FWD": 4}}
    if gt in ("matchday", "round"):
        # Many teams playing → 20-man with hard 2-per-country cap so no single
        # nation dominates.
        return {"total": 20, "budget": 150, "max_per_country": 2,
                "slots": {"GK": 3, "DEF": 7, "MID": 6, "FWD": 4}}
    return {"total": 15, "budget": 100, "max_per_country": 2,
            "slots": {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}}


@router.get("/game-rules/{game_id}")
async def game_rules(game_id: str):
    """Public — return pick rules + eligible-country list for a mini-game."""
    db = get_db()
    g = await db.wc_games.find_one({"id": game_id}, {"_id": 0})
    if not g:
        raise HTTPException(status_code=404, detail="Game not found")
    countries = await _eligible_countries_for_game(db, g)
    return {
        "game_id": game_id,
        "game_type": g.get("game_type"),
        "rules": _pick_rules_for_game(g),
        "eligible_countries": sorted(countries),
        "title": g.get("title"),
    }


@router.get("/squad")
@router.get("/squad/me")
async def my_squad(user: dict = Depends(a.get_current_user)):
    db = get_db()
    squad = await db.fantasy_squads.find_one(
        {"user_id": user["id"], "competition_id": "fantasy-wc2026"}, {"_id": 0}
    )
    return {"squad": squad}


@router.post("/squad")
async def create_or_update_squad(payload: FantasySquadIn, user: dict = Depends(a.get_current_user)):
    db = get_db()
    comp = await db.fantasy_competitions.find_one({"id": payload.competition_id}, {"_id": 0})
    if not comp:
        raise HTTPException(status_code=404, detail="Competition not found")
    # Honor explicit mode (15-man £100m vs 20-man £120m). Fall back to comp config.
    mode = payload.mode or "15"
    max_size = 20 if mode == "20" else 15
    budget = 150.0 if mode == "20" else 100.0
    if len(payload.players) > max_size:
        raise HTTPException(status_code=400, detail=f"Squad too large; max {max_size}")
    total_cost = sum(p.price_paid for p in payload.players)
    if total_cost > budget:
        raise HTTPException(status_code=400, detail=f"Over budget ({total_cost:.1f} > {budget:.1f})")

    # Derive is_starting from on_bench / bench_ids
    bench_set = set(payload.bench_ids or [p.player_id for p in payload.players if p.on_bench])
    players_out = []
    pick_pos_by_id: dict[str, str] = {}
    for p in payload.players:
        d = p.model_dump()
        d["is_starting"] = p.player_id not in bench_set
        d["on_bench"] = p.player_id in bench_set
        d["is_captain"] = (payload.captain_id == p.player_id)
        d["is_vice"] = (payload.vice_captain_id == p.player_id)
        players_out.append(d)
        pick_pos_by_id[p.player_id] = p.position

    # ---- Per-player card targeting (new) ----
    # Accept both the legacy `applied_card_ids` (flat list) and the new
    # `applied_cards` (per-player target). Validate ownership + uses_left +
    # position lock for the new shape.
    valid_per_player_cards: list[dict] = []
    if payload.applied_cards:
        # Enforce uniqueness — one card use per submit
        seen_uc_ids: set[str] = set()
        seen_targets: set[str] = set()
        for cu in payload.applied_cards[:5]:
            if cu.user_card_id in seen_uc_ids:
                raise HTTPException(400, "Each card can only be applied once per squad")
            seen_uc_ids.add(cu.user_card_id)
            if cu.target_player_id in seen_targets:
                raise HTTPException(400, "Each player can carry at most one boost card")
            seen_targets.add(cu.target_player_id)
            if cu.target_player_id not in pick_pos_by_id:
                raise HTTPException(400, "Card target must be one of your picked players")
            owned = await db.user_cards.find_one({"id": cu.user_card_id, "user_id": user["id"]}, {"_id": 0, "id": 1, "card_id": 1, "uses_remaining": 1, "uses_left": 1})
            if not owned:
                raise HTTPException(400, "You don't own one of the applied cards")
            remaining = int(owned.get("uses_remaining", owned.get("uses_left", 0)) or 0)
            if remaining <= 0:
                raise HTTPException(400, "One of your selected cards has 0 uses left")
            legend = await db.legend_cards.find_one({"id": owned.get("card_id")}, {"_id": 0, "id": 1, "position": 1, "name": 1})
            if legend:
                card_pos = (legend.get("position") or "ANY").upper()
                if card_pos != "ANY":
                    tgt_pos = (pick_pos_by_id.get(cu.target_player_id) or "").upper()
                    if tgt_pos != card_pos:
                        raise HTTPException(
                            400,
                            f"{legend.get('name')} can only boost a {card_pos} — your target is {tgt_pos or 'unknown'}.",
                        )
            valid_per_player_cards.append({
                "user_card_id": cu.user_card_id,
                "target_player_id": cu.target_player_id,
            })

    # Validate cards belong to user with uses remaining (cap 5 per gameweek) — LEGACY flat path
    valid_cards: list[str] = []
    for ucid in (payload.applied_card_ids or [])[:5]:
        owned = await db.user_cards.find_one({"id": ucid, "user_id": user["id"]})
        if owned and (owned.get("uses_remaining", 0) > 0 or owned.get("uses_left", 0) > 0):
            valid_cards.append(ucid)

    doc = {
        "user_id": user["id"], "competition_id": payload.competition_id,
        "game_id": payload.game_id,
        "squad_name": payload.squad_name,
        "mode": mode,
        "captain_id": payload.captain_id,
        "vice_captain_id": payload.vice_captain_id,
        "formation": payload.formation or "4-3-3",
        "bench_ids": list(bench_set),
        "bench_boost": bool(payload.bench_boost),
        "players": players_out,
        "applied_card_ids": valid_cards,
        "applied_cards": valid_per_player_cards,
        "total_cost": total_cost,
        "budget": budget,
        "updated_at": utcnow_iso(),
    }
    existing = await db.fantasy_squads.find_one({"user_id": user["id"], "competition_id": payload.competition_id})
    if existing:
        await db.fantasy_squads.update_one({"id": existing["id"]}, {"$set": doc})
        doc["id"] = existing["id"]
        # Preserve total_points / gw_points across edits
        doc["total_points"] = existing.get("total_points", 0)
        doc["gw_points"] = existing.get("gw_points", 0)
    else:
        doc["id"] = new_id()
        doc["created_at"] = utcnow_iso()
        doc["total_points"] = 0
        doc["gw_points"] = 0
        doc["rank"] = None
        await db.fantasy_squads.insert_one(doc)
    doc.pop("_id", None)
    # Log a daily action for the matchday-drop reward system
    try:
        from routes.card_drops import log_user_action
        await log_user_action(user["id"])
    except Exception:
        pass
    return {"squad": doc}


@router.get("/my-teams")
async def my_teams(user: dict = Depends(a.get_current_user)):
    """Return ALL squads owned by the current user — both the main fantasy
    squads AND all WC mini-game entries (`wc_game_entries`), unified under one
    shape so the frontend `/my-teams` page renders everything in one list.
    """
    db = get_db()
    out: list[dict] = []

    # 1) Main fantasy squads (per competition)
    fs = await db.fantasy_squads.find({"user_id": user["id"]}, {"_id": 0}).sort("updated_at", -1).to_list(length=200)
    for r in fs:
        out.append({
            **r,
            "kind": "main",
            "game_title": "Main squad",
            "player_count": len(r.get("players", [])),
        })

    # 2) WC mini-game entries
    ge = await db.wc_game_entries.find({"user_id": user["id"]}, {"_id": 0}).sort("updated_at", -1).to_list(length=400)
    for r in ge:
        game_title = None
        squad_name = None
        match_meta = None
        if r.get("wc_game_id"):
            g = await db.wc_games.find_one(
                {"id": r["wc_game_id"]},
                {"_id": 0, "game_type": 1, "stage": 1, "group_letter": 1,
                 "matchday": 1, "title": 1, "match_info": 1, "match_id": 1,
                 "status": 1, "closes_at": 1},
            )
            wc_game_status = (g or {}).get("status")
            wc_game_type = (g or {}).get("game_type")
            if g:
                # For a single-match mini-game, prefer "Home Team vs Away Team"
                # (e.g. "South Africa vs Mexico") over the generic "Match · Any".
                if g.get("game_type") == "match":
                    home_name = away_name = home_code = away_code = None
                    if g.get("match_id"):
                        m = await db.matches.find_one(
                            {"id": g["match_id"]},
                            {"_id": 0, "home_team_name": 1, "away_team_name": 1,
                             "home_team_code": 1, "away_team_code": 1,
                             "home_team_logo": 1, "away_team_logo": 1,
                             "scheduled_at": 1, "status": 1,
                             "home_score": 1, "away_score": 1},
                        )
                        if m:
                            home_name = m.get("home_team_name")
                            away_name = m.get("away_team_name")
                            home_code = m.get("home_team_code")
                            away_code = m.get("away_team_code")
                            match_meta = {
                                "home_team_name": home_name, "away_team_name": away_name,
                                "home_team_code": home_code, "away_team_code": away_code,
                                "home_team_logo": m.get("home_team_logo"),
                                "away_team_logo": m.get("away_team_logo"),
                                "scheduled_at": m.get("scheduled_at"),
                                "status": m.get("status"),
                                "home_score": m.get("home_score"),
                                "away_score": m.get("away_score"),
                            }
                    if home_name and away_name:
                        game_title = f"{home_name} vs {away_name}"
                        squad_name = game_title
                    elif g.get("title"):
                        game_title = g["title"]
                if not game_title and g.get("title"):
                    game_title = g["title"]
                if not game_title:
                    bits = [str(g.get("game_type", "")).title()]
                    if g.get("stage") and g.get("stage") != "any":
                        bits.append(str(g["stage"]).title())
                    if g.get("group_letter"):
                        bits.append("Group " + str(g["group_letter"]))
                    if g.get("matchday"):
                        bits.append("MD" + str(g["matchday"]))
                    game_title = " · ".join([b for b in bits if b])
        # Mini-game entries store the lineup in `player_picks` (not `players`).
        picks = r.get("player_picks") or []
        # Compute the squad size cap so the UI can show "15/15" or "20/20"
        # rather than the legacy "/11" denominator.
        try:
            squad_size_required = int(_pick_rules_for_game(g or {}).get("total") or 15) if r.get("wc_game_id") else 15
        except Exception:
            squad_size_required = 15
        out.append({
            **r,
            "kind": "wc_game",
            "game_title": game_title or "WC mini-game",
            "squad_name": r.get("squad_name") or squad_name or game_title or "Mini-game entry",
            "player_count": len(picks),
            "squad_size_required": squad_size_required,
            "wc_game_status": wc_game_status if r.get("wc_game_id") else None,
            "wc_game_type": wc_game_type if r.get("wc_game_id") else None,
            "players": picks,  # so the existing 15/20-detection on the frontend still works
            "captain_id": r.get("captain_player_id"),
            "match_info": match_meta,
            "total_points": r.get("points_scored") or 0,
        })

    out.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return {"teams": out, "count": len(out)}


# ---------- Transfer cards (5 transfers across all teams) ----------
# Priced in COINS (2026-02-13). Was $2 (200 USD cents) = 1370 × 2 × 1.05 ≈
# 2,877 coins at the crypto-bonus rate; we round to a clean 300 coins
# (≈ ₦300) to keep it accessible for NGN funders.
TRANSFER_CARD_PRICE_COINS = 300
TRANSFER_CARD_USES = 5
POINT_PENALTY_PER_TRANSFER = 4       # FPL-style penalty when paying with leaderboard points


@router.get("/transfers")
async def get_my_transfers(user: dict = Depends(a.get_current_user)):
    """Return remaining transfers + coin price for refill."""
    db = get_db()
    doc = await db.user_transfers.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
    return {
        "remaining": int(doc.get("remaining", 0)),
        "total_used": int(doc.get("total_used", 0)),
        "card_price_coins": TRANSFER_CARD_PRICE_COINS,
        # Legacy alias for any old FE caches still reading this field.
        "card_price_usd_cents": int(TRANSFER_CARD_PRICE_COINS * 0.073),
        "card_uses": TRANSFER_CARD_USES,
        "point_penalty_per_transfer": POINT_PENALTY_PER_TRANSFER,
    }


@router.post("/transfers/buy")
async def buy_transfer_card(user: dict = Depends(a.get_current_user)):
    """Spend 🪙 300 coins for a 5-transfer pack."""
    db = get_db()
    udoc = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    bal = int(udoc.get("coins") or 0)
    if bal < TRANSFER_CARD_PRICE_COINS:
        raise HTTPException(402, f"Insufficient coins. Need 🪙 {TRANSFER_CARD_PRICE_COINS}, have 🪙 {bal}.")
    debit = await db.users.update_one(
        {"id": user["id"], "coins": {"$gte": TRANSFER_CARD_PRICE_COINS}},
        {"$inc": {"coins": -TRANSFER_CARD_PRICE_COINS}},
    )
    if debit.modified_count != 1:
        raise HTTPException(402, "Insufficient coins.")
    await db.user_transfers.update_one(
        {"user_id": user["id"]},
        {"$inc": {"remaining": TRANSFER_CARD_USES},
         "$setOnInsert": {"id": new_id(), "user_id": user["id"], "total_used": 0, "created_at": utcnow_iso()}},
        upsert=True,
    )
    await db.wallet_transactions.insert_one({
        "id": new_id(), "user_id": user["id"], "kind": "transfer_card_purchase",
        "amount_coins": TRANSFER_CARD_PRICE_COINS, "created_at": utcnow_iso(),
        "metadata": {"uses_added": TRANSFER_CARD_USES},
    })
    doc = await db.user_transfers.find_one({"user_id": user["id"]}, {"_id": 0})
    return {"ok": True, "remaining": int(doc.get("remaining", 0))}


@router.post("/transfers/spend")
async def spend_transfer(payload: dict, user: dict = Depends(a.get_current_user)):
    """Spend ONE transfer. If `pay_with=points`, applies -4pt penalty instead.

    Body: {pay_with: "card" | "points"}
    """
    pay_with = (payload or {}).get("pay_with", "card")
    db = get_db()
    if pay_with == "card":
        doc = await db.user_transfers.find_one({"user_id": user["id"]}, {"_id": 0})
        if not doc or int(doc.get("remaining", 0)) <= 0:
            raise HTTPException(402, "No transfers left. Buy a Transfer Pack ($2 for 5) or pay with points (−4pt).")
        await db.user_transfers.update_one(
            {"user_id": user["id"]},
            {"$inc": {"remaining": -1, "total_used": 1}, "$set": {"updated_at": utcnow_iso()}},
        )
        await db.audit_log.insert_one({
            "id": new_id(), "user_id": user["id"], "action": "transfer_spent_card",
            "metadata": {}, "created_at": utcnow_iso(),
        })
        return {"ok": True, "pay_with": "card"}
    elif pay_with == "points":
        # Deduct from leaderboard points — applied at next gameweek-settle.
        await db.transfer_penalties.insert_one({
            "id": new_id(), "user_id": user["id"], "points": POINT_PENALTY_PER_TRANSFER,
            "applied": False, "created_at": utcnow_iso(),
        })
        return {"ok": True, "pay_with": "points", "penalty": POINT_PENALTY_PER_TRANSFER}
    else:
        raise HTTPException(400, "pay_with must be 'card' or 'points'")



@router.post("/players/lookup")
async def lookup_players(payload: dict):
    """Bulk fetch player docs by IDs — used by team viewers to hydrate
    `image_path`, club info, etc. without pulling the full pool."""
    db = get_db()
    ids = list({pid for pid in (payload or {}).get("player_ids", []) if pid})
    if not ids:
        return {"players": []}
    docs = await db.players.find({"id": {"$in": ids}}, {"_id": 0}).to_list(length=200)
    return {"players": docs}


@router.get("/squad/{squad_id}/daily")
async def squad_daily_points(squad_id: str, user: dict = Depends(a.get_current_user)):
    """📅 Per-calendar-date points breakdown for a main 15-man squad.

    Walks every finished match the squad's team_ids appeared in, groups by
    `scheduled_at.date()`, and computes per-match player points with the
    canonical FPL spec. Caller-friendly: returns a list the FE can render as a
    swipeable day-by-day slider plus a `total` matching `total_points`.
    """
    from datetime import datetime
    db = get_db()
    sq = await db.fantasy_squads.find_one({"id": squad_id, "user_id": user["id"]}, {"_id": 0})
    if not sq:
        raise HTTPException(404, "Squad not found")

    picks = sq.get("players") or []
    if not picks:
        return {"squad_id": squad_id, "total": int(sq.get("total_points") or 0), "days": []}
    player_ids = [p.get("player_id") for p in picks if p.get("player_id")]
    pdocs = await db.players.find({"id": {"$in": player_ids}}, {"_id": 0}).to_list(length=200)
    pmap = {p["id"]: p for p in pdocs}
    team_ids = list({p.get("team_id") for p in pdocs if p.get("team_id")})

    matches = await db.matches.find(
        {"is_world_cup": True, "status": {"$in": ["FT", "AET", "PEN", "Ended", "Finished"]},
         "$or": [{"home_team_id": {"$in": team_ids}}, {"away_team_id": {"$in": team_ids}}]},
        {"_id": 0},
    ).sort("scheduled_at", 1).to_list(length=400)

    events_by_match: dict[str, list[dict]] = {}
    lineups_by_match: dict[str, list[dict]] = {}
    match_ids = [m["id"] for m in matches]
    if match_ids:
        evs = await db.match_events.find({"match_id": {"$in": match_ids}}, {"_id": 0}).to_list(length=10000)
        for e in evs:
            events_by_match.setdefault(e["match_id"], []).append(e)
        lns = await db.match_lineups.find({"match_id": {"$in": match_ids}}, {"_id": 0}).to_list(length=10000)
        for ln in lns:
            lineups_by_match.setdefault(ln["match_id"], []).append(ln)

    cap_id = sq.get("captain_id")
    vice_id = sq.get("vice_captain_id")
    cap_played_today = False  # track cap played to allow vice fallback per day

    by_day: dict[str, dict] = {}
    for m in matches:
        sched = m.get("scheduled_at") or ""
        if not sched:
            continue
        try:
            date_key = datetime.fromisoformat(sched.replace("Z", "+00:00")).date().isoformat()
        except Exception:
            date_key = sched[:10]
        bucket = by_day.setdefault(date_key, {"date": date_key, "points": 0, "matches": 0, "player_points": []})
        bucket["matches"] += 1
        cap_played_today = False

        for sp in picks:
            pid = sp.get("player_id")
            player = pmap.get(pid)
            if not player:
                continue
            team_id = player.get("team_id")
            if team_id not in (m.get("home_team_id"), m.get("away_team_id")):
                continue
            name = player.get("name") or sp.get("name") or ""
            position = sp.get("position") or player.get("position") or "MID"
            evs_for = events_by_match.get(m["id"], [])
            s = aggregate_player_stats_from_events(evs_for, name, team_id)
            lin = next((x for x in lineups_by_match.get(m["id"], [])
                       if (x.get("player_name") or "").strip().lower() == name.strip().lower()), None)
            minutes = 0
            saves = pen_saves = clearances = blocks = interceptions = tackles = recoveries = 0
            if lin:
                minutes = 90 if lin.get("starter") else 30
                if s.get("substituted_out"):
                    minutes = max(0, minutes - 30)
                ps = lin.get("stats") or {}
                saves = int(ps.get("saves") or 0)
                pen_saves = int(ps.get("penalty_saves") or ps.get("saves_penalty") or 0)
                clearances = int(ps.get("clearances") or 0)
                blocks = int(ps.get("blocks") or 0)
                interceptions = int(ps.get("interceptions") or 0)
                tackles = int(ps.get("tackles") or 0)
                recoveries = int(ps.get("recoveries") or 0)
            gc = 0
            if position in ("GK", "DEF"):
                gc = int((m.get("away_score") if m.get("home_team_id") == team_id else m.get("home_score")) or 0)
            cs = ((m.get("away_score") or 0) == 0 and m.get("home_team_id") == team_id) or \
                 ((m.get("home_score") or 0) == 0 and m.get("away_team_id") == team_id)
            res = compute_player_points(
                position=position, minutes_played=minutes,
                goals=int(s.get("goals", 0)), assists=int(s.get("assists", 0)),
                yellow_cards=int(s.get("yellow_cards", 0)), red_cards=int(s.get("red_cards", 0)),
                own_goals=int(s.get("own_goals", 0)), missed_penalties=int(s.get("missed_penalties", 0)),
                saves=saves, penalty_saves=pen_saves, team_clean_sheet=bool(cs),
                goals_conceded=gc, clearances=clearances, blocks=blocks,
                interceptions=interceptions, tackles=tackles, recoveries=recoveries,
            )
            p_pts = int(res["points"])
            is_cap = (pid == cap_id)
            is_vice = (pid == vice_id)
            if is_cap and minutes > 0:
                cap_played_today = True
                p_pts *= 2
            elif is_vice and not cap_played_today and minutes > 0:
                p_pts *= 2
            bucket["points"] += p_pts
            bucket["player_points"].append({
                "player_id": pid, "name": name, "position": position, "team_id": team_id,
                "match_id": m["id"], "opponent": (m.get("away_team_name") if m.get("home_team_id") == team_id else m.get("home_team_name")),
                "points": p_pts, "captain": is_cap, "vice": is_vice, "minutes": minutes,
                "breakdown": res["breakdown"],
            })

    days = sorted(by_day.values(), key=lambda d: d["date"])
    return {
        "squad_id": squad_id,
        "total": sum(d["points"] for d in days),
        "snapshot_total": int(sq.get("total_points") or 0),
        "days": days,
    }


@router.get("/leaderboard")
async def fantasy_leaderboard(limit: int = 50):
    db = get_db()
    rows = await db.fantasy_squads.find(
        {"competition_id": "fantasy-wc2026"}, {"_id": 0}
    ).sort("total_points", -1).limit(limit).to_list(length=limit)
    user_ids = [r["user_id"] for r in rows]
    users = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "id": 1, "display_name": 1, "country_code": 1}).to_list(length=200)
    by_id = {u["id"]: u for u in users}
    out = []
    for i, r in enumerate(rows, 1):
        u = by_id.get(r["user_id"], {})
        out.append({
            "rank": i, "user_id": r["user_id"], "squad_name": r["squad_name"],
            "display_name": u.get("display_name") or "Player",
            "country_code": u.get("country_code") or "NG",
            "total_points": r.get("total_points", 0),
            "gw_points": r.get("gw_points", 0),
        })
    return {"leaderboard": out}



@router.post("/settle/gameweek")
async def settle_gameweek(gameweek: int = 1, user: dict = Depends(a.require_admin)):
    """Admin trigger: compute gameweek points for every squad based on FT matches.
    Walks each squad's players, finds matching match_events/lineups/statistics, applies
    captain ×2 (vice ×2 fallback), and updates total_points + writes a snapshot."""
    db = get_db()
    squads = await db.fantasy_squads.find({"competition_id": "fantasy-wc2026"}, {"_id": 0}).to_list(length=10000)
    finished = await db.matches.find(
        {"status": {"$in": ["FT", "AET", "PEN"]}, "sport_slug": "football"},
        {"_id": 0, "id": 1, "home_team_id": 1, "away_team_id": 1, "home_score": 1, "away_score": 1},
    ).to_list(length=5000)
    finished_ids = [m["id"] for m in finished]
    events_by_match = {}
    lineups_by_match = {}
    if finished_ids:
        ev = await db.match_events.find({"match_id": {"$in": finished_ids}}, {"_id": 0}).to_list(length=20000)
        for e in ev:
            events_by_match.setdefault(e["match_id"], []).append(e)
        ln = await db.match_lineups.find({"match_id": {"$in": finished_ids}}, {"_id": 0}).to_list(length=20000)
        for ln_row in ln:
            lineups_by_match.setdefault(ln_row["match_id"], []).append(ln_row)
    # Clean sheets per (match_id, team_id)
    clean = {}
    for m in finished:
        h, a_ = m.get("home_score") or 0, m.get("away_score") or 0
        clean[(m["id"], m.get("home_team_id"))] = (a_ == 0)
        clean[(m["id"], m.get("away_team_id"))] = (h == 0)

    settled = 0
    for sq in squads:
        # Load applied cards for this squad
        squad_cards = []
        for ucid in (sq.get("applied_card_ids") or []):
            uc = await db.user_cards.find_one({"id": ucid, "user_id": sq.get("user_id")}, {"_id": 0})
            if uc and (uc.get("uses_remaining", 0) > 0 or uc.get("uses_left", 0) > 0):
                card = await db.legend_cards.find_one({"id": uc.get("card_id")}, {"_id": 0})
                if card:
                    squad_cards.append({"user_card_id": ucid, "card": card})

        gw_total = 0
        per_player = []
        cap_played = False
        cap_pts = 0
        vice_pts = 0
        for sp in sq.get("players", []):
            if not sp.get("is_starting"):
                continue
            player = await db.players.find_one({"id": sp.get("player_id")}, {"_id": 0})
            if not player:
                continue
            name = player.get("name") or ""
            team_id = player.get("team_id")
            position = sp.get("position") or player.get("position") or "MID"
            # Accumulate across matches the team played
            agg_stats = {"goals":0,"assists":0,"yellow_cards":0,"red_cards":0,"own_goals":0,"missed_penalties":0,"minutes":0,"saves":0,"penalty_saves":0,"clearances":0,"blocks":0,"interceptions":0,"tackles":0,"recoveries":0,"goals_conceded":0}
            for m in finished:
                if team_id not in (m.get("home_team_id"), m.get("away_team_id")):
                    continue
                events = events_by_match.get(m["id"], [])
                s = aggregate_player_stats_from_events(events, name, team_id)
                # Lineup gives minutes via starter status (assume 90 if starter present)
                lin = next((x for x in lineups_by_match.get(m["id"], []) if (x.get("player_name") or "").strip().lower() == name.strip().lower()), None)
                if lin:
                    agg_stats["minutes"] += 90 if lin.get("starter") else 30
                    if s.get("substituted_out"):
                        agg_stats["minutes"] = max(0, agg_stats["minutes"] - 30)
                    # Defensive contribution stats from the lineup row (Sportmonks
                    # publishes these per-player statistics in `lineup.stats`).
                    pstats = (lin.get("stats") or {})
                    for k in ("clearances", "blocks", "interceptions", "tackles", "recoveries", "saves"):
                        v = pstats.get(k)
                        if isinstance(v, (int, float)):
                            agg_stats[k] += int(v)
                    pen_saves = pstats.get("penalty_saves") or pstats.get("saves_penalty")
                    if isinstance(pen_saves, (int, float)):
                        agg_stats["penalty_saves"] += int(pen_saves)
                for k in ("goals", "assists", "yellow_cards", "red_cards", "own_goals", "missed_penalties"):
                    agg_stats[k] += s.get(k, 0)
                # Team goals conceded for THIS match (only relevant for GK/DEF)
                if position in ("GK", "DEF"):
                    if m.get("home_team_id") == team_id:
                        agg_stats["goals_conceded"] += int(m.get("away_score") or 0)
                    else:
                        agg_stats["goals_conceded"] += int(m.get("home_score") or 0)
            # Clean sheet across team's finished matches
            had_cs = any(clean.get((m["id"], team_id), False) for m in finished if team_id in (m.get("home_team_id"), m.get("away_team_id")))
            res = compute_player_points(
                position=position,
                minutes_played=agg_stats["minutes"],
                goals=agg_stats["goals"], assists=agg_stats["assists"],
                yellow_cards=agg_stats["yellow_cards"], red_cards=agg_stats["red_cards"],
                own_goals=agg_stats["own_goals"], missed_penalties=agg_stats["missed_penalties"],
                saves=agg_stats["saves"], penalty_saves=agg_stats["penalty_saves"],
                team_clean_sheet=had_cs,
                goals_conceded=agg_stats["goals_conceded"],
                clearances=agg_stats["clearances"], blocks=agg_stats["blocks"],
                interceptions=agg_stats["interceptions"], tackles=agg_stats["tackles"],
                recoveries=agg_stats["recoveries"],
            )
            p_pts = res["points"]
            is_cap = (sq.get("captain_id") == sp.get("player_id"))
            is_vice = (sq.get("vice_captain_id") == sp.get("player_id"))
            if is_cap and agg_stats["minutes"] > 0:
                cap_played = True
                cap_pts = p_pts * 2
                p_pts = cap_pts
            elif is_vice and not cap_played:
                vice_pts = p_pts * 2
                p_pts = vice_pts
            # Apply card boost (cards are FANTASY-only)
            player_country = (player.get("country") or player.get("country_code") or "").upper()
            ctx = {
                "scope": "fantasy",
                "position": position,
                "role": "captain" if is_cap else ("vice_captain" if is_vice else "player"),
                "home_country": player_country,
                "away_country": player_country,
                "home_continent": player.get("continent", "").lower(),
                "away_continent": player.get("continent", "").lower(),
            }
            cards_only = [sc["card"] for sc in squad_cards]
            boost = compute_card_boost(cards_only, ctx)
            p_pts_boosted = round(p_pts * (1.0 + boost))
            per_player.append({
                "player_id": sp.get("player_id"), "name": name, "position": position,
                "points": p_pts_boosted, "base_points": p_pts, "card_boost": boost,
                "breakdown": res["breakdown"],
                "minutes": agg_stats["minutes"], "captain": is_cap, "vice": is_vice,
            })
            gw_total += p_pts_boosted
        # Snapshot — upsert (idempotent re-runs allowed).
        await db.fantasy_gameweek_points.update_one(
            {"squad_id": sq.get("id"), "gameweek": gameweek},
            {"$set": {
                "id": sq.get("id") + f"-gw{gameweek}",
                "squad_id": sq.get("id"), "user_id": sq.get("user_id"),
                "gameweek": gameweek, "points": gw_total, "players": per_player,
                "settled_at": utcnow_iso(),
            }},
            upsert=True,
        )
        # 🐛 Fixed (2026-02-13): previously `$inc total_points` which double-
        # counted on every 5-min auto-loop. Now compute the canonical total
        # by SUMMING every snapshot for this squad, then `$set` it. Makes the
        # settler safe to call any number of times without inflating points.
        all_snaps = await db.fantasy_gameweek_points.find(
            {"squad_id": sq.get("id")}, {"_id": 0, "points": 1},
        ).to_list(length=200)
        canonical_total = sum(int(s.get("points") or 0) for s in all_snaps)
        await db.fantasy_squads.update_one(
            {"id": sq.get("id")},
            {"$set": {"total_points": canonical_total, "gw_points": gw_total, "last_gw": gameweek}},
        )
        # NOTE: card-use consumption disabled in the auto-loop to keep it
        # idempotent. Cards are consumed ONCE per gameweek by the explicit
        # admin endpoint or the new `re-settle` backfill below.
        settled += 1
    return {"settled": settled, "gameweek": gameweek, "scoring_version": "v2-2026-02-13"}


@router.post("/settle/rebuild")
async def rebuild_all_fantasy_points(user: dict = Depends(a.require_admin)):
    """🧹 BACKFILL: nuke every squad's existing gameweek snapshots, reset
    `total_points` to 0, then re-run `settle_gameweek(1)` from scratch
    using the latest scoring engine (v2 — CBIT / CBIRT / goals conceded /
    spec'd goal values).

    Run this ONCE on production after deploying scoring v2 so all
    historical games get re-credited with the new rules. Idempotent —
    re-running it just re-applies the same canonical totals.
    """
    db = get_db()
    wipe1 = await db.fantasy_gameweek_points.delete_many({})
    wipe2 = await db.fantasy_squads.update_many(
        {}, {"$set": {"total_points": 0, "gw_points": 0}},
    )
    # Re-settle gameweek 1 (covers every FT match in DB).
    result = await settle_gameweek(gameweek=1, user=user)
    await db.audit_log.insert_one({
        "id": new_id(), "user_id": user["id"], "email": user.get("email"),
        "action": "fantasy_rebuild_all",
        "metadata": {
            "snapshots_wiped": wipe1.deleted_count,
            "squads_reset": wipe2.modified_count,
            "settled_after_rebuild": result.get("settled", 0),
        },
        "created_at": utcnow_iso(),
    })
    return {
        "ok": True,
        "snapshots_wiped": wipe1.deleted_count,
        "squads_reset": wipe2.modified_count,
        "settled": result.get("settled", 0),
        "scoring_version": "v2-2026-02-13",
    }


@router.get("/squad/me/breakdown")
async def my_squad_breakdown(user: dict = Depends(a.get_current_user)):
    """Latest gameweek breakdown for the signed-in user's squad."""
    db = get_db()
    sq = await db.fantasy_squads.find_one({"user_id": user["id"], "competition_id": "fantasy-wc2026"}, {"_id": 0})
    if not sq:
        return {"snapshot": None}
    snap = await db.fantasy_gameweek_points.find_one(
        {"squad_id": sq.get("id")}, {"_id": 0}, sort=[("gameweek", -1)],
    )
    return {"snapshot": snap, "squad_id": sq.get("id")}
