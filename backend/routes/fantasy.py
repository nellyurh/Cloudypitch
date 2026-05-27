"""Fantasy: WC2026 squad builder."""
from fastapi import APIRouter, Depends, HTTPException
from db import get_db, utcnow_iso
from models import FantasySquadIn, new_id
import auth as a

router = APIRouter(prefix="/api/fantasy", tags=["fantasy"])


@router.get("/competition")
async def get_competition():
    db = get_db()
    comp = await db.fantasy_competitions.find_one({"id": "fantasy-wc2026"}, {"_id": 0})
    return {"competition": comp}


@router.get("/players")
async def list_fantasy_players(limit: int = 500):
    db = get_db()
    # Prefer real WC2026 players from Sportmonks
    players = await db.players.find({"is_wc_2026": True}, {"_id": 0}).sort([("position", 1), ("price", -1)]).limit(limit).to_list(length=limit)
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
    if len(payload.players) > comp.get("squad_size", 15):
        raise HTTPException(status_code=400, detail=f"Squad too large; max {comp.get('squad_size', 15)}")
    total_cost = sum(p.price_paid for p in payload.players)
    if total_cost > comp.get("budget_total", 100):
        raise HTTPException(status_code=400, detail=f"Over budget ({total_cost:.1f} > {comp.get('budget_total', 100):.1f})")
    doc = {
        "user_id": user["id"], "competition_id": payload.competition_id,
        "squad_name": payload.squad_name, "captain_id": payload.captain_id,
        "vice_captain_id": payload.vice_captain_id,
        "players": [p.model_dump() for p in payload.players],
        "total_cost": total_cost,
        "total_points": 0, "gw_points": 0, "rank": None,
        "updated_at": utcnow_iso(),
    }
    existing = await db.fantasy_squads.find_one({"user_id": user["id"], "competition_id": payload.competition_id})
    if existing:
        await db.fantasy_squads.update_one({"id": existing["id"]}, {"$set": doc})
        doc["id"] = existing["id"]
    else:
        doc["id"] = new_id()
        doc["created_at"] = utcnow_iso()
        await db.fantasy_squads.insert_one(doc)
    doc.pop("_id", None)
    return {"squad": doc}


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
