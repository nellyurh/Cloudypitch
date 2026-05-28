"""League standings + top scorers — Sportmonks-backed."""
from fastapi import APIRouter, HTTPException

from db import get_db

router = APIRouter(prefix="/api/leagues", tags=["leagues"])


@router.get("/{league_id}/standings")
async def get_standings(league_id: str, season_id: int | None = None, refresh: int = 0):
    """Return cached standings for a league. Pass `refresh=1` to re-fetch from Sportmonks."""
    db = get_db()
    league = await db.leagues.find_one({"id": league_id}, {"_id": 0})
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    target_season = season_id or league.get("current_season_id")
    sportmonks_league_id = league.get("sportmonks_league_id") or league.get("sportmonks_id")

    # Read cache
    if target_season:
        rows = await db.standings.find({"season_id": target_season}, {"_id": 0}).sort("position", 1).to_list(length=200)
    else:
        rows = await db.standings.find({"league_id": league_id}, {"_id": 0}).sort("position", 1).to_list(length=200)

    # Refresh if forced or empty + we have a sportmonks linkage
    if (refresh == 1 or not rows) and sportmonks_league_id and league.get("primary_provider") == "sportmonks":
        try:
            from ingestion import sync_sportmonks_standings_live
            await sync_sportmonks_standings_live(sportmonks_league_id)
            if target_season:
                rows = await db.standings.find({"season_id": target_season}, {"_id": 0}).sort("position", 1).to_list(length=200)
            else:
                rows = await db.standings.find({"league_id": league_id}, {"_id": 0}).sort("position", 1).to_list(length=200)
        except Exception as e:
            if not rows:
                raise HTTPException(status_code=502, detail=f"Standings fetch failed: {e}")
    return {"league_id": league_id, "season_id": target_season, "standings": rows}


@router.get("/{league_id}/topscorers")
async def get_topscorers(league_id: str, season_id: int | None = None, refresh: int = 0):
    db = get_db()
    league = await db.leagues.find_one({"id": league_id}, {"_id": 0})
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    target_season = season_id or league.get("current_season_id")

    rows = await db.top_scorers.find({"league_id": league_id}, {"_id": 0}).sort("rank", 1).to_list(length=100)

    if (refresh == 1 or not rows) and target_season and league.get("primary_provider") == "sportmonks":
        try:
            from ingestion import sync_sportmonks_scorers_for_season
            await sync_sportmonks_scorers_for_season(int(target_season), league_id)
            rows = await db.top_scorers.find({"league_id": league_id}, {"_id": 0}).sort("rank", 1).to_list(length=100)
        except Exception as e:
            if not rows:
                raise HTTPException(status_code=502, detail=f"Topscorers fetch failed: {e}")
    return {"league_id": league_id, "season_id": target_season, "scorers": rows}
