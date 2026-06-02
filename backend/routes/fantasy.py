"""Fantasy: WC2026 squad builder + gameweek settlement."""
from fastapi import APIRouter, Depends, HTTPException
from db import get_db, utcnow_iso
from models import FantasySquadIn, new_id
from fantasy_scoring import compute_player_points, aggregate_player_stats_from_events
from scoring import compute_card_boost
import auth as a

router = APIRouter(prefix="/api/fantasy", tags=["fantasy"])


@router.get("/competition")
async def get_competition():
    db = get_db()
    comp = await db.fantasy_competitions.find_one({"id": "fantasy-wc2026"}, {"_id": 0})
    return {"competition": comp}


@router.get("/players")
async def list_fantasy_players(limit: int = 2000):
    db = get_db()
    # Prefer real WC2026 players from Sportmonks. Sort by name so positions are interleaved
    # in the response (clients can paginate up to ~1300 players across all 4 positions).
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
    budget = 120.0 if mode == "20" else 100.0
    if len(payload.players) > max_size:
        raise HTTPException(status_code=400, detail=f"Squad too large; max {max_size}")
    total_cost = sum(p.price_paid for p in payload.players)
    if total_cost > budget:
        raise HTTPException(status_code=400, detail=f"Over budget ({total_cost:.1f} > {budget:.1f})")

    # Derive is_starting from on_bench / bench_ids
    bench_set = set(payload.bench_ids or [p.player_id for p in payload.players if p.on_bench])
    players_out = []
    for p in payload.players:
        d = p.model_dump()
        d["is_starting"] = p.player_id not in bench_set
        d["on_bench"] = p.player_id in bench_set
        d["is_captain"] = (payload.captain_id == p.player_id)
        d["is_vice"] = (payload.vice_captain_id == p.player_id)
        players_out.append(d)

    # Validate cards belong to user with uses remaining (cap 5 per gameweek)
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
    return {"squad": doc}


@router.get("/my-teams")
async def my_teams(user: dict = Depends(a.get_current_user)):
    """Return ALL squads owned by the current user (across competitions / games)."""
    db = get_db()
    rows = await db.fantasy_squads.find({"user_id": user["id"]}, {"_id": 0}).sort("updated_at", -1).to_list(length=200)
    # Optionally enrich with game title
    out = []
    for r in rows:
        game_title = None
        if r.get("game_id"):
            g = await db.wc_games.find_one({"id": r["game_id"]}, {"_id": 0, "game_type": 1, "stage": 1, "group_letter": 1, "matchday": 1})
            if g:
                bits = [str(g.get("game_type", "")).title(), str(g.get("stage", ""))]
                if g.get("group_letter"):
                    bits.append("Group " + str(g["group_letter"]))
                if g.get("matchday"):
                    bits.append("MD" + str(g["matchday"]))
                game_title = " · ".join([b for b in bits if b])
        out.append({
            **r,
            "game_title": game_title,
            "player_count": len(r.get("players", [])),
        })
    return {"teams": out, "count": len(out)}


# ---------- Transfer cards (5 transfers across all teams) ----------
TRANSFER_CARD_PRICE_USD_CENTS = 200  # $2 per pack
TRANSFER_CARD_USES = 5
POINT_PENALTY_PER_TRANSFER = 4       # FPL-style penalty when paying with leaderboard points


@router.get("/transfers")
async def get_my_transfers(user: dict = Depends(a.get_current_user)):
    """Return remaining transfers + price for refill."""
    db = get_db()
    doc = await db.user_transfers.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
    return {
        "remaining": int(doc.get("remaining", 0)),
        "total_used": int(doc.get("total_used", 0)),
        "card_price_usd_cents": TRANSFER_CARD_PRICE_USD_CENTS,
        "card_uses": TRANSFER_CARD_USES,
        "point_penalty_per_transfer": POINT_PENALTY_PER_TRANSFER,
    }


@router.post("/transfers/buy")
async def buy_transfer_card(user: dict = Depends(a.get_current_user)):
    """Spend $2 wallet balance for a 5-transfer pack."""
    db = get_db()
    udoc = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    bal = int(udoc.get("wallet_balance_usd_cents") or 0)
    if bal < TRANSFER_CARD_PRICE_USD_CENTS:
        raise HTTPException(402, f"Insufficient wallet balance. Need ${TRANSFER_CARD_PRICE_USD_CENTS/100:.2f}, have ${bal/100:.2f}.")
    await db.users.update_one({"id": user["id"]}, {"$inc": {"wallet_balance_usd_cents": -TRANSFER_CARD_PRICE_USD_CENTS}})
    await db.user_transfers.update_one(
        {"user_id": user["id"]},
        {"$inc": {"remaining": TRANSFER_CARD_USES},
         "$setOnInsert": {"id": new_id(), "user_id": user["id"], "total_used": 0, "created_at": utcnow_iso()}},
        upsert=True,
    )
    await db.wallet_transactions.insert_one({
        "id": new_id(), "user_id": user["id"], "kind": "transfer_card_purchase",
        "amount_usd_cents": TRANSFER_CARD_PRICE_USD_CENTS, "created_at": utcnow_iso(),
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
            agg_stats = {"goals":0,"assists":0,"yellow_cards":0,"red_cards":0,"own_goals":0,"missed_penalties":0,"minutes":0,"saves":0,"penalty_saves":0}
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
                for k in ("goals", "assists", "yellow_cards", "red_cards", "own_goals", "missed_penalties"):
                    agg_stats[k] += s.get(k, 0)
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
        # Snapshot
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
        await db.fantasy_squads.update_one(
            {"id": sq.get("id")},
            {"$inc": {"total_points": gw_total}, "$set": {"gw_points": gw_total, "last_gw": gameweek}},
        )
        # Consume one use per applied card
        for sc in squad_cards:
            await db.user_cards.update_one(
                {"id": sc["user_card_id"]},
                {"$inc": {"uses_remaining": -1, "uses_left": -1, "total_uses": 1},
                 "$set": {"last_used_at": utcnow_iso()}},
            )
        settled += 1
    return {"settled": settled, "gameweek": gameweek}


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
