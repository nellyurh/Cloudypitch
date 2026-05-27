"""World Cup 2026 hub routes."""
from fastapi import APIRouter
from datetime import datetime, timezone
from db import get_db

router = APIRouter(prefix="/api/worldcup", tags=["worldcup"])

WC2026_START = "2026-06-11T18:00:00+00:00"
WC2026_LEAGUE_NAME = "FIFA World Cup"


@router.get("")
async def worldcup_hub():
    db = get_db()
    groups = await db.wc2026_groups.find({}, {"_id": 0}).sort("group", 1).to_list(length=12)
    # WC fixtures pulled from sportmonks (league = "FIFA World Cup")
    matches = await db.matches.find(
        {"league_name": {"$regex": "World Cup", "$options": "i"}},
        {"_id": 0, "raw_data": 0},
    ).sort("scheduled_at", 1).to_list(length=200)
    pool = await db.prize_pools.find_one({"id": "pool-wc2026-fantasy"}, {"_id": 0})
    comp = await db.fantasy_competitions.find_one({"id": "fantasy-wc2026"}, {"_id": 0})
    return {
        "starts_at": WC2026_START,
        "groups": groups,
        "matches": matches,
        "prize_pool": pool,
        "competition": comp,
    }


@router.get("/groups")
async def list_groups():
    db = get_db()
    groups = await db.wc2026_groups.find({}, {"_id": 0}).sort("group", 1).to_list(length=12)
    return {"groups": groups}


@router.get("/bracket")
async def bracket():
    # Knockout bracket (placeholder structure for the 16-team knockout)
    return {
        "rounds": [
            {"name": "Round of 32", "matches": []},
            {"name": "Round of 16", "matches": []},
            {"name": "Quarterfinals", "matches": []},
            {"name": "Semifinals", "matches": []},
            {"name": "Final", "matches": []},
        ],
    }
