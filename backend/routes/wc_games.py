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
    # Resolve eligible players from team IDs
    eligible_team_ids = g.get("eligible_team_ids", [])
    players = []
    if eligible_team_ids:
        players = await db.players.find(
            {"team_id": {"$in": eligible_team_ids}}, {"_id": 0},
        ).limit(1000).to_list(length=1000)
    # Fallback: synthetic if no real squads yet
    if not players and eligible_team_ids:
        teams = await db.teams.find({"id": {"$in": eligible_team_ids}}, {"_id": 0}).to_list(length=50)
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
    player_picks: list[PlayerPickIn] = Field(min_length=1, max_length=11)
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
    for cu in body.cards_used:
        if not cu.target_player_id:
            raise HTTPException(status_code=400, detail="Each card must target a player in your squad")
        if cu.target_player_id not in picked_player_ids:
            raise HTTPException(status_code=400, detail="Card target must be one of your picked players")

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
