"""Search across teams, leagues, players, matches."""
from fastapi import APIRouter, Query
from db import get_db

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
async def search(q: str = Query(min_length=2)):
    db = get_db()
    rx = {"$regex": q, "$options": "i"}
    teams = await db.teams.find({"name": rx}, {"_id": 0}).limit(10).to_list(length=10)
    leagues = await db.leagues.find({"name": rx}, {"_id": 0}).limit(10).to_list(length=10)
    matches = await db.matches.find(
        {"$or": [{"home_team_name": rx}, {"away_team_name": rx}]},
        {"_id": 0, "raw_data": 0},
    ).sort("scheduled_at", -1).limit(10).to_list(length=10)
    return {"teams": teams, "leagues": leagues, "matches": matches}
