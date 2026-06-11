"""WC2026 Fantasy Game system: 148 games (104 Match + 36 Group + 8 Round).

Three game types:
  - 'match'  → 11 picks from BOTH teams (card_limit default 2)
  - 'group'  → 11 picks from a group's 4 teams (card_limit default 4)
  - 'round'  → 11 picks from all teams alive in that round (card_limit scales 5→10)

Game lifecycle: upcoming → open → closed → settling → settled
Auto-generation runs daily; state machine ticks every 5 minutes.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import auth as a
from db import get_db
from models import new_id

router = APIRouter(prefix="/api/wc", tags=["wc-fantasy"])


# ----- Stage helpers -----
ROUND_STAGES = ["group_md1", "group_md2", "group_md3", "r32", "r16", "qf", "sf", "finals"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


# ===== USER ENDPOINTS =====
@router.get("/games/today")
async def games_today(user: dict = Depends(a.get_optional_user)):
    db = get_db()
    rows = await db.wc_games.find(
        {"status": {"$in": ["upcoming", "open"]}, "opens_at": {"$lte": _now_iso()}, "closes_at": {"$gte": _now_iso()}},
        {"_id": 0},
    ).sort("closes_at", 1).to_list(length=200)
    if user:
        ids = [r["id"] for r in rows]
        entries = await db.wc_game_entries.find(
            {"user_id": user["id"], "wc_game_id": {"$in": ids}}, {"_id": 0}
        ).to_list(length=500)
        by_g = {e["wc_game_id"]: e for e in entries}
        for r in rows:
            r["my_entry"] = by_g.get(r["id"])
    return {"games": rows}


@router.get("/games/upcoming")
async def games_upcoming(limit: int = 50, user: dict = Depends(a.get_optional_user)):
    db = get_db()
    rows = await db.wc_games.find(
        {"status": {"$in": ["upcoming", "open"]}}, {"_id": 0},
    ).sort("opens_at", 1).limit(limit).to_list(length=limit)
    if user:
        ids = [r["id"] for r in rows]
        entries = await db.wc_game_entries.find(
            {"user_id": user["id"], "wc_game_id": {"$in": ids}}, {"_id": 0}
        ).to_list(length=500)
        by_g = {e["wc_game_id"]: e for e in entries}
        for r in rows:
            r["my_entry"] = by_g.get(r["id"])
    return {"games": rows}


@router.get("/games/{game_id}")
async def game_detail(game_id: str, user: dict = Depends(a.get_optional_user)):
    db = get_db()
    g = await db.wc_games.find_one({"id": game_id}, {"_id": 0})
    if not g:
        raise HTTPException(status_code=404, detail="Game not found")
    eligible_team_ids = list(g.get("eligible_team_ids") or [])

    # ─── Integrity gate ───────────────────────────────────────────────────
    # For round / group / matchday games (which span multiple kickoffs),
    # players from teams whose match has ALREADY STARTED must be removed
    # from the pool. Otherwise late entrants could pick a team that already
    # played and copy its known result. Single-match games don't need this
    # filter because the whole game closes at one kickoff.
    locked_team_ids: set[str] = set()
    if g.get("game_type") in ("round", "group", "matchday") and eligible_team_ids:
        from datetime import datetime, timedelta
        from db import utcnow_iso
        # Window: same as the wc_settler resolution (see wc_settler.WINDOW_HOURS).
        try:
            closes = datetime.fromisoformat((g.get("closes_at") or utcnow_iso()).replace("Z", "+00:00"))
        except Exception:
            closes = None
        if closes:
            win_pre, win_post = (2, 96) if g["game_type"] == "round" else (2, 30)
            ws = (closes - timedelta(hours=win_pre)).isoformat()
            we = (closes + timedelta(hours=win_post)).isoformat()
            q = {
                "is_world_cup": True,
                "scheduled_at": {"$gte": ws, "$lte": we, "$lt": utcnow_iso()},
            }
            if g["game_type"] in ("group", "matchday"):
                q["home_team_id"] = {"$in": eligible_team_ids}
                q["away_team_id"] = {"$in": eligible_team_ids}
            else:
                q["$or"] = [
                    {"home_team_id": {"$in": eligible_team_ids}},
                    {"away_team_id": {"$in": eligible_team_ids}},
                ]
            kicked = await db.matches.find(
                q, {"_id": 0, "home_team_id": 1, "away_team_id": 1},
            ).to_list(length=200)
            for m in kicked:
                if m.get("home_team_id"): locked_team_ids.add(m["home_team_id"])
                if m.get("away_team_id"): locked_team_ids.add(m["away_team_id"])

    # Resolve eligible players from team IDs (minus locked teams)
    pool_team_ids = [tid for tid in eligible_team_ids if tid not in locked_team_ids]
    players = []
    if pool_team_ids:
        players = await db.players.find(
            {"team_id": {"$in": pool_team_ids}}, {"_id": 0},
        ).limit(1000).to_list(length=1000)
    # Fallback: synthetic if no real squads yet
    if not players and pool_team_ids:
        teams = await db.teams.find({"id": {"$in": pool_team_ids}}, {"_id": 0}).to_list(length=50)
        POSITIONS = ["GK", "DEF", "DEF", "DEF", "MID", "MID", "MID", "FWD", "FWD"]
        for t in teams:
            for i, pos in enumerate(POSITIONS):
                players.append({
                    "id": f"{t['id']}-p{i+1}", "name": f"{t.get('name', 'Player')} #{i+1}",
                    "team_id": t["id"], "team_name": t.get("name"),
                    "team_logo": t.get("logo_url", ""),
                    "position": pos, "price": 5.0,
                })
    g["eligible_players"] = players
    g["locked_team_ids"] = sorted(list(locked_team_ids))
    if user:
        ent = await db.wc_game_entries.find_one(
            {"user_id": user["id"], "wc_game_id": game_id}, {"_id": 0}
        )
        g["my_entry"] = ent
    return {"game": g}


class PlayerPickIn(BaseModel):
    player_id: str
    team_id: Optional[str] = None
    position: Literal["GK", "DEF", "MID", "FWD"]


class CardUseIn(BaseModel):
    user_card_id: str
    target_player_id: Optional[str] = None
    target_team_id: Optional[str] = None


class GameEntryIn(BaseModel):
    # Allow main-15 / mini-game-20 squad sizes. Position validation still
    # happens on the frontend; here we just bound the array size.
    player_picks: list[PlayerPickIn] = Field(min_length=1, max_length=25)
    captain_player_id: Optional[str] = None
    vice_captain_player_id: Optional[str] = None
    cards_used: list[CardUseIn] = Field(default_factory=list)


@router.post("/games/{game_id}/enter")
async def enter_game(game_id: str, body: GameEntryIn, user: dict = Depends(a.get_current_user)):
    db = get_db()
    g = await db.wc_games.find_one({"id": game_id}, {"_id": 0})
    if not g:
        raise HTTPException(status_code=404, detail="Game not found")
    if g.get("status") not in ("upcoming", "open"):
        raise HTTPException(status_code=400, detail=f"Game is {g.get('status')} — entries closed")

    # ─── Integrity: for multi-match games (round/group/matchday), reject any
    # pick whose team has already kicked off in this round/window. Mirrors the
    # client-side gate in /games/{id}.eligible_players so a stale frontend
    # can't sneak through.
    if g.get("game_type") in ("round", "group", "matchday"):
        from datetime import datetime, timedelta, timezone
        team_ids = list(g.get("eligible_team_ids") or [])
        if team_ids:
            try:
                closes = datetime.fromisoformat((g.get("closes_at") or _now_iso()).replace("Z", "+00:00"))
            except Exception:
                closes = None
            if closes:
                win_pre, win_post = (2, 96) if g["game_type"] == "round" else (2, 30)
                ws = (closes - timedelta(hours=win_pre)).isoformat()
                we = (closes + timedelta(hours=win_post)).isoformat()
                q = {
                    "is_world_cup": True,
                    "scheduled_at": {"$gte": ws, "$lte": we, "$lt": _now_iso()},
                }
                if g["game_type"] in ("group", "matchday"):
                    q["home_team_id"] = {"$in": team_ids}
                    q["away_team_id"] = {"$in": team_ids}
                else:
                    q["$or"] = [
                        {"home_team_id": {"$in": team_ids}},
                        {"away_team_id": {"$in": team_ids}},
                    ]
                kicked_rows = await db.matches.find(
                    q, {"_id": 0, "home_team_id": 1, "away_team_id": 1, "home_team_name": 1, "away_team_name": 1},
                ).to_list(length=200)
                locked_ids = set()
                locked_names = []
                for m in kicked_rows:
                    if m.get("home_team_id"):
                        locked_ids.add(m["home_team_id"])
                        locked_names.append(m.get("home_team_name") or m["home_team_id"])
                    if m.get("away_team_id"):
                        locked_ids.add(m["away_team_id"])
                        locked_names.append(m.get("away_team_name") or m["away_team_id"])
                if locked_ids and body.player_picks:
                    pick_player_ids = [p.player_id for p in body.player_picks]
                    bad = await db.players.find(
                        {"id": {"$in": pick_player_ids}, "team_id": {"$in": list(locked_ids)}},
                        {"_id": 0, "name": 1, "team_name": 1},
                    ).to_list(length=50)
                    if bad:
                        n = bad[0]
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Player '{n.get('name')}' is from {n.get('team_name')}, which has already played this round. "
                                f"Players from {', '.join(sorted(set(locked_names))[:4])} can't be picked any more."
                            ),
                        )
    cfg = await db.wc_game_config.find_one({"id": g.get("config_id")}, {"_id": 0})
    card_cap = (cfg or {}).get("card_limit_current", 2) if cfg else 2
    if len(body.cards_used) > card_cap:
        raise HTTPException(status_code=400, detail=f"Card limit {card_cap} for this stage")
    # Enforce uniqueness: each user_card_id can only be used ONCE per game entry
    seen_card_ids: set[str] = set()
    for cu in body.cards_used:
        if cu.user_card_id in seen_card_ids:
            raise HTTPException(status_code=400, detail="Each card can only be used once per game")
        seen_card_ids.add(cu.user_card_id)
    # Each card MUST target a picked player
    picked_player_ids = {p.player_id for p in body.player_picks}
    pick_pos_by_id = {p.player_id: p.position for p in body.player_picks}
    for cu in body.cards_used:
        if not cu.target_player_id:
            raise HTTPException(status_code=400, detail="Each card must target a player in your squad")
        if cu.target_player_id not in picked_player_ids:
            raise HTTPException(status_code=400, detail="Card target must be one of your picked players")

    # Position-lock validation — a card with `position=FWD` cannot be applied
    # to a DEF/MID/GK. Cards with position='ANY' (or missing) skip the check.
    if body.cards_used:
        card_ids_for_check = list({cu.user_card_id for cu in body.cards_used})
        uc_rows = await db.user_cards.find(
            {"id": {"$in": card_ids_for_check}, "user_id": user["id"]},
            {"_id": 0, "id": 1, "card_id": 1},
        ).to_list(length=20)
        legend_ids = list({r["card_id"] for r in uc_rows if r.get("card_id")})
        legends = await db.legend_cards.find(
            {"id": {"$in": legend_ids}}, {"_id": 0, "id": 1, "position": 1, "name": 1},
        ).to_list(length=50)
        legend_by_id = {l["id"]: l for l in legends}
        uc_by_id = {r["id"]: r for r in uc_rows}
        for cu in body.cards_used:
            uc = uc_by_id.get(cu.user_card_id)
            if not uc:
                continue
            legend = legend_by_id.get(uc.get("card_id"))
            if not legend:
                continue
            card_pos = (legend.get("position") or "ANY").upper()
            if card_pos == "ANY":
                continue
            target_pos = (pick_pos_by_id.get(cu.target_player_id) or "").upper()
            if target_pos != card_pos:
                raise HTTPException(
                    status_code=400,
                    detail=f"{legend.get('name')} can only boost a {card_pos} — your target is {target_pos or 'unknown'}.",
                )

    # Compare against previous entry — figure out which cards are NEW (consume) vs UNCHANGED (skip) vs REMOVED (refund)
    existing = await db.wc_game_entries.find_one({"user_id": user["id"], "wc_game_id": game_id})
    prev_card_ids: set[str] = set()
    if existing:
        for pcu in existing.get("cards_used") or []:
            if pcu.get("user_card_id"):
                prev_card_ids.add(pcu["user_card_id"])
    new_card_ids = {cu.user_card_id for cu in body.cards_used}
    to_consume = new_card_ids - prev_card_ids   # cards being added in this submit
    to_refund = prev_card_ids - new_card_ids     # cards being removed in this submit

    # Validate ownership + uses_remaining for NEW cards only
    valid_cards = []
    for cu in body.cards_used:
        owned = await db.user_cards.find_one({"id": cu.user_card_id, "user_id": user["id"]})
        if not owned:
            continue
        if cu.user_card_id in to_consume:
            remaining = owned.get("uses_remaining", owned.get("uses_left", 0))
            if remaining <= 0:
                raise HTTPException(status_code=400, detail="One of your selected cards has 0 uses left")
        valid_cards.append(cu.model_dump())
    doc = {
        "user_id": user["id"], "wc_game_id": game_id,
        "player_picks": [p.model_dump() for p in body.player_picks],
        "captain_player_id": body.captain_player_id,
        "vice_captain_player_id": body.vice_captain_player_id,
        "cards_used": valid_cards,
        "points_scored": None, "rank_in_game": None, "settled_at": None,
        "updated_at": _now_iso(),
    }
    existing_doc = existing  # alias for clarity
    if existing_doc:
        await db.wc_game_entries.update_one({"id": existing_doc["id"]}, {"$set": doc})
        doc["id"] = existing_doc["id"]
    else:
        doc["id"] = new_id()
        doc["created_at"] = _now_iso()
        await db.wc_game_entries.insert_one(doc)
        await db.wc_games.update_one({"id": game_id}, {"$inc": {"total_entries": 1}})

    # Consume NEW cards (decrement uses + write a card_uses audit row)
    for cu in body.cards_used:
        if cu.user_card_id not in to_consume:
            continue
        owned = await db.user_cards.find_one({"id": cu.user_card_id, "user_id": user["id"]})
        if not owned:
            continue
        await db.user_cards.update_one(
            {"id": cu.user_card_id},
            {"$inc": {"uses_remaining": -1, "uses_left": -1, "total_uses": 1}},
        )
        await db.card_uses.insert_one({
            "id": new_id(), "user_id": user["id"],
            "user_card_id": cu.user_card_id, "card_id": owned.get("card_id"),
            "wc_game_id": game_id, "wc_game_entry_id": doc["id"],
            "target_player_id": cu.target_player_id, "target_team_id": cu.target_team_id,
            "created_at": _now_iso(),
        })

    # Refund REMOVED cards (only if not yet settled — game must still be open/upcoming)
    if to_refund and g.get("status") in ("upcoming", "open"):
        for uc_id in to_refund:
            used_row = await db.card_uses.find_one({"user_card_id": uc_id, "wc_game_id": game_id, "user_id": user["id"]})
            if used_row:
                await db.user_cards.update_one(
                    {"id": uc_id},
                    {"$inc": {"uses_remaining": 1, "uses_left": 1, "total_uses": -1}},
                )
                await db.card_uses.delete_one({"id": used_row["id"]})

    doc.pop("_id", None)
    # Log a daily action for the matchday-drop reward system
    try:
        from routes.card_drops import log_user_action
        await log_user_action(user["id"])
    except Exception:
        pass
    return {"entry": doc}


@router.get("/games/{game_id}/leaderboard")
async def game_leaderboard(game_id: str, limit: int = 50):
    db = get_db()
    rows = await db.wc_game_entries.find(
        {"wc_game_id": game_id, "settled_at": {"$ne": None}}, {"_id": 0},
    ).sort("points_scored", -1).limit(limit).to_list(length=limit)
    user_ids = [r["user_id"] for r in rows]
    users = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "id": 1, "display_name": 1, "country_code": 1}).to_list(length=200)
    by_id = {u["id"]: u for u in users}
    out = []
    for i, r in enumerate(rows, 1):
        u = by_id.get(r["user_id"], {})
        out.append({
            "rank": i, "user_id": r["user_id"],
            "display_name": u.get("display_name") or "Player",
            "country_code": u.get("country_code") or "—",
            "points_scored": r.get("points_scored", 0),
        })
    return {"leaderboard": out}


@router.get("/games/{game_id}/entries")
async def public_game_entries(game_id: str, limit: int = 200):
    """Transparency view: ONCE a game is `settled`, every entry's lineup +
    applied cards become publicly visible (alongside the score they got).
    Before settlement → returns `{visible: false}` so players can't copy
    each other's strategies.

    Renders enough player + card metadata for the client to build the
    Sofascore-style team-display sheet without further round-trips.
    """
    db = get_db()
    g = await db.wc_games.find_one({"id": game_id}, {"_id": 0})
    if not g:
        raise HTTPException(404, "Game not found")
    if g.get("status") != "settled":
        return {"visible": False, "reason": "Game not yet settled — entries hidden until match results are final.",
                "game": {"id": g["id"], "status": g.get("status"),
                         "closes_at": g.get("closes_at"),
                         "settled_at": g.get("settled_at")}}

    rows = await db.wc_game_entries.find(
        {"wc_game_id": game_id, "settled_at": {"$ne": None}}, {"_id": 0},
    ).sort("points_scored", -1).limit(limit).to_list(length=limit)
    if not rows:
        return {"visible": True, "entries": [], "game": g}

    # Bulk-resolve players + cards + users for display
    player_ids: set[str] = set()
    uc_ids: set[str] = set()
    user_ids: set[str] = set()
    for r in rows:
        user_ids.add(r["user_id"])
        for p in r.get("player_picks", []) or []:
            if p.get("player_id"): player_ids.add(p["player_id"])
        for cu in r.get("cards_used", []) or []:
            if cu.get("user_card_id"): uc_ids.add(cu["user_card_id"])
            if cu.get("target_player_id"): player_ids.add(cu["target_player_id"])

    players = await db.players.find(
        {"id": {"$in": list(player_ids)}},
        {"_id": 0, "id": 1, "name": 1, "team_name": 1, "team_logo": 1, "country": 1,
         "country_code": 1, "position": 1, "photo_url": 1},
    ).to_list(length=2000) if player_ids else []
    by_player = {p["id"]: p for p in players}

    uc_rows = await db.user_cards.find(
        {"id": {"$in": list(uc_ids)}}, {"_id": 0, "id": 1, "card_id": 1},
    ).to_list(length=500) if uc_ids else []
    uc_to_card = {r["id"]: r["card_id"] for r in uc_rows}
    legend_ids = list({r["card_id"] for r in uc_rows if r.get("card_id")})
    legends = await db.legend_cards.find(
        {"id": {"$in": legend_ids}},
        {"_id": 0, "id": 1, "name": 1, "tier": 1, "position": 1,
         "effect_type": 1, "effect_value": 1, "player_name": 1, "country_code": 1},
    ).to_list(length=200) if legend_ids else []
    by_legend = {l["id"]: l for l in legends}

    users = await db.users.find(
        {"id": {"$in": list(user_ids)}},
        {"_id": 0, "id": 1, "display_name": 1, "country_code": 1, "is_premium": 1},
    ).to_list(length=500) if user_ids else []
    by_user = {u["id"]: u for u in users}

    out = []
    for i, r in enumerate(rows, 1):
        u = by_user.get(r["user_id"], {})
        cards_resolved = []
        for cu in r.get("cards_used", []) or []:
            card_id = uc_to_card.get(cu.get("user_card_id"))
            cards_resolved.append({
                "target_player_id": cu.get("target_player_id"),
                "target_player": by_player.get(cu.get("target_player_id")),
                "card": by_legend.get(card_id),
            })
        out.append({
            "rank": r.get("rank_in_game") or i,
            "user_id": r["user_id"],
            "display_name": u.get("display_name") or "Player",
            "country_code": u.get("country_code") or "—",
            "is_premium": bool(u.get("is_premium")),
            "points_scored": r.get("points_scored", 0),
            "captain_player_id": r.get("captain_player_id"),
            "vice_captain_player_id": r.get("vice_captain_player_id"),
            "captain": by_player.get(r.get("captain_player_id")),
            "vice_captain": by_player.get(r.get("vice_captain_player_id")),
            "players": [
                {**(by_player.get(p["player_id"]) or {"id": p["player_id"], "name": "—"}),
                 "position_in_squad": p.get("position")}
                for p in (r.get("player_picks") or [])
            ],
            "cards_applied": cards_resolved,
        })
    return {"visible": True, "game": g, "entries": out}


@router.get("/user/entries")
async def my_entries(user: dict = Depends(a.get_current_user), limit: int = 100):
    db = get_db()
    rows = await db.wc_game_entries.find(
        {"user_id": user["id"]}, {"_id": 0},
    ).sort("created_at", -1).limit(limit).to_list(length=limit)
    game_ids = [r["wc_game_id"] for r in rows]
    games = await db.wc_games.find({"id": {"$in": game_ids}}, {"_id": 0}).to_list(length=200)
    by_id = {g["id"]: g for g in games}
    for r in rows:
        r["game"] = by_id.get(r["wc_game_id"])
    return {"entries": rows}


@router.get("/groups")
async def list_groups():
    db = get_db()
    rows = await db.wc2026_groups.find({}, {"_id": 0}).sort("group", 1).to_list(length=20)
    return {"groups": rows}


@router.get("/leaderboard/overall")
async def overall_leaderboard(limit: int = 50):
    """Overall WC Fantasy leaderboard summing every settled wc_game_entry."""
    db = get_db()
    pipeline = [
        {"$match": {"settled_at": {"$ne": None}}},
        {"$group": {
            "_id": "$user_id",
            "total_points": {"$sum": "$points_scored"},
            "games_played": {"$sum": 1},
        }},
        {"$sort": {"total_points": -1}},
        {"$limit": limit},
    ]
    rows = await db.wc_game_entries.aggregate(pipeline).to_list(length=limit)
    user_ids = [r["_id"] for r in rows]
    users = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "id": 1, "display_name": 1, "country_code": 1}).to_list(length=200)
    by_id = {u["id"]: u for u in users}
    out = []
    for i, r in enumerate(rows, 1):
        u = by_id.get(r["_id"], {})
        out.append({
            "rank": i, "user_id": r["_id"],
            "display_name": u.get("display_name") or "Player",
            "country_code": u.get("country_code") or "—",
            "total_points": r["total_points"],
            "games_played": r["games_played"],
        })
    return {"leaderboard": out}


# ===== ADMIN ENDPOINTS =====
admin_router = APIRouter(prefix="/api/admin/wc", tags=["admin-wc"])


@admin_router.get("/config")
async def admin_list_config(admin: dict = Depends(a.require_admin)):
    db = get_db()
    rows = await db.wc_game_config.find({}, {"_id": 0}).sort([("game_type", 1), ("stage", 1)]).to_list(length=50)
    return {"config": rows}


class ConfigPatch(BaseModel):
    card_limit_current: Optional[int] = Field(default=None, ge=0, le=20)
    points_multiplier: Optional[float] = Field(default=None, ge=0.1, le=10)
    opens_hours_before: Optional[int] = Field(default=None, ge=0, le=720)
    is_active: Optional[bool] = None
    notes: Optional[str] = None


@admin_router.patch("/config/{config_id}")
async def admin_update_config(config_id: str, body: ConfigPatch, admin: dict = Depends(a.require_admin)):
    db = get_db()
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if not upd:
        raise HTTPException(status_code=400, detail="No fields to update")
    old = await db.wc_game_config.find_one({"id": config_id}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Config not found")
    upd["updated_at"] = _now_iso()
    upd["updated_by"] = admin["id"]
    await db.wc_game_config.update_one({"id": config_id}, {"$set": upd})
    # Audit
    await db.audit_log.insert_one({
        "id": new_id(), "user_id": admin["id"], "email": admin.get("email"),
        "action": "wc_config_update",
        "metadata": {"config_id": config_id, "old": {k: old.get(k) for k in upd}, "new": upd},
        "created_at": _now_iso(),
    })
    return {"ok": True}


@admin_router.post("/config/reset")
async def admin_reset_config(admin: dict = Depends(a.require_admin)):
    """Reset card_limit_current back to card_limit_default for every row."""
    db = get_db()
    rows = await db.wc_game_config.find({}, {"_id": 0}).to_list(length=50)
    for r in rows:
        await db.wc_game_config.update_one(
            {"id": r["id"]},
            {"$set": {"card_limit_current": r["card_limit_default"], "updated_at": _now_iso(), "updated_by": admin["id"]}},
        )
    await db.audit_log.insert_one({
        "id": new_id(), "user_id": admin["id"], "email": admin.get("email"),
        "action": "wc_config_reset_all", "metadata": {"rows": len(rows)},
        "created_at": _now_iso(),
    })
    return {"ok": True, "rows": len(rows)}


@admin_router.get("/games")
async def admin_list_games(
    game_type: Optional[str] = None, status: Optional[str] = None,
    stage: Optional[str] = None, limit: int = 200,
    admin: dict = Depends(a.require_admin),
):
    db = get_db()
    q = {}
    if game_type: q["game_type"] = game_type
    if status: q["status"] = status
    if stage: q["stage"] = stage
    rows = await db.wc_games.find(q, {"_id": 0}).sort("opens_at", 1).limit(limit).to_list(length=limit)
    return {"games": rows}


class GamePatch(BaseModel):
    status: Optional[Literal["upcoming", "open", "closed", "settling", "settled"]] = None
    opens_at: Optional[str] = None
    closes_at: Optional[str] = None
    card_limit_override: Optional[int] = Field(default=None, ge=0, le=20)


@admin_router.patch("/games/{game_id}")
async def admin_update_game(game_id: str, body: GamePatch, admin: dict = Depends(a.require_admin)):
    db = get_db()
    old = await db.wc_games.find_one({"id": game_id}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Game not found")
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if not upd:
        raise HTTPException(status_code=400, detail="No fields to update")
    upd["updated_at"] = _now_iso()
    await db.wc_games.update_one({"id": game_id}, {"$set": upd})
    await db.audit_log.insert_one({
        "id": new_id(), "user_id": admin["id"], "email": admin.get("email"),
        "action": "wc_game_override",
        "metadata": {"game_id": game_id, "old": {k: old.get(k) for k in upd}, "new": upd},
        "created_at": _now_iso(),
    })
    return {"ok": True}


class GroupTeamsPatch(BaseModel):
    teams: list[str] = Field(min_length=4, max_length=4)


@admin_router.patch("/groups/{letter}")
async def admin_update_group(letter: str, body: GroupTeamsPatch, admin: dict = Depends(a.require_admin)):
    db = get_db()
    old = await db.wc2026_groups.find_one({"group": letter.upper()}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Group not found")
    await db.wc2026_groups.update_one(
        {"group": letter.upper()}, {"$set": {"teams": body.teams}},
    )
    await db.audit_log.insert_one({
        "id": new_id(), "user_id": admin["id"], "email": admin.get("email"),
        "action": "wc_group_update",
        "metadata": {"group": letter.upper(), "old_teams": old.get("teams"), "new_teams": body.teams},
        "created_at": _now_iso(),
    })
    return {"ok": True}


@admin_router.post("/refresh-bracket")
async def admin_refresh_bracket(admin: dict = Depends(a.require_admin)):
    """Pull WC2026 schedule from Sportmonks → generator → state machine. One-click full sync."""
    from ingestion import sync_sportmonks_league_schedule, generate_wc_games, tick_wc_game_states
    ingested = await sync_sportmonks_league_schedule(732)
    created = await generate_wc_games()
    transitions = await tick_wc_game_states()
    return {"ok": True, "ingested": ingested, "created": created, "transitions": transitions}



@admin_router.post("/games/open-all")
async def admin_open_all_games(admin: dict = Depends(a.require_admin)):
    """One-click: switch every `upcoming` WC2026 game to `open` so users can enter.
    Also relaxes `opens_at` to now so they're not blocked by the time check.
    Use sparingly — this overrides the natural stage cadence.
    """
    db = get_db()
    now = _now_iso()
    res = await db.wc_games.update_many(
        {"status": {"$in": ["upcoming", "open"]}},
        {"$set": {"status": "open", "opens_at": now, "updated_at": now}},
    )
    await db.audit_log.insert_one({
        "id": new_id(), "user_id": admin["id"], "email": admin.get("email"),
        "action": "wc_games_open_all",
        "metadata": {"affected": res.modified_count, "total_matched": res.matched_count},
        "created_at": now,
    })
    total = await db.wc_games.count_documents({"status": "open"})
    return {"ok": True, "modified": res.modified_count, "matched": res.matched_count, "now_open_total": total}


# ---------- Settlement ----------
@admin_router.post("/games/{game_id}/settle")
async def admin_settle_game(
    game_id: str,
    force: bool = False,
    admin: dict = Depends(a.require_admin),
):
    """Manually settle a single WC mini-game. Pass `?force=true` to override
    safety checks (already-settled / matches-not-finished).
    """
    from wc_settler import settle_wc_game
    res = await settle_wc_game(game_id, force=force)
    await get_db().audit_log.insert_one({
        "id": new_id(), "user_id": admin["id"], "email": admin.get("email"),
        "action": "wc_game_settle_manual",
        "metadata": {"game_id": game_id, "force": force, "result": res},
        "created_at": _now_iso(),
    })
    return res


@admin_router.post("/games/settle-due")
async def admin_settle_due(admin: dict = Depends(a.require_admin)):
    """Scan all closed/settling games and settle any whose dependent matches
    are finished. Same job the background loop runs every 5 minutes."""
    from wc_settler import settle_due_wc_games
    res = await settle_due_wc_games(limit=200)
    await get_db().audit_log.insert_one({
        "id": new_id(), "user_id": admin["id"], "email": admin.get("email"),
        "action": "wc_games_settle_due_manual",
        "metadata": res, "created_at": _now_iso(),
    })
    return res
