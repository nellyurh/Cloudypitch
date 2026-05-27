"""Catalog: sports, leagues, countries, standings, top scorers."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from db import get_db

router = APIRouter(prefix="/api", tags=["catalog"])


def _strip(doc):
    if not doc:
        return doc
    doc.pop("_id", None)
    return doc


@router.get("/sports")
async def list_sports():
    db = get_db()
    out = await db.sports.find({}, {"_id": 0}).sort("display_order", 1).to_list(length=50)
    return {"sports": out}


@router.get("/countries")
async def list_countries(sport: str = "football"):
    db = get_db()
    pipeline = [
        {"$match": {"sport_slug": sport, "country": {"$ne": None}}},
        {"$group": {"_id": "$country", "count": {"$sum": 1}, "priority": {"$min": "$country_priority"}}},
        {"$sort": {"priority": 1, "_id": 1}},
        {"$project": {"_id": 0, "country": "$_id", "league_count": "$count", "priority": 1}},
    ]
    rows = await db.leagues.aggregate(pipeline).to_list(length=200)
    return {"countries": rows}


@router.get("/leagues")
async def list_leagues(
    sport: str = "football",
    country: Optional[str] = None,
    limit: int = 100,
):
    db = get_db()
    q: dict = {"sport_slug": sport}
    if country:
        q["country"] = country
    rows = await db.leagues.find(q, {"_id": 0}).sort([("tier_score", -1), ("country_priority", 1), ("name", 1)]).to_list(length=limit)
    return {"leagues": rows}


@router.get("/leagues/{league_id}")
async def league_detail(league_id: str):
    db = get_db()
    lg = await db.leagues.find_one({"id": league_id}, {"_id": 0})
    if not lg:
        raise HTTPException(status_code=404, detail="League not found")
    return {"league": lg}


@router.get("/leagues/{league_id}/fixtures")
async def league_fixtures(league_id: str, limit: int = 100):
    db = get_db()
    rows = await db.matches.find({"league_id": league_id}, {"_id": 0}).sort("scheduled_at", -1).to_list(length=limit)
    return {"matches": rows}


@router.get("/leagues/{league_id}/standings")
async def league_standings(league_id: str):
    db = get_db()
    rows = await db.standings.find({"league_id": league_id}, {"_id": 0}).sort("rank", 1).to_list(length=50)
    return {"standings": rows}


@router.get("/leagues/{league_id}/scorers")
async def league_scorers(league_id: str):
    db = get_db()
    rows = await db.top_scorers.find({"league_id": league_id}, {"_id": 0}).sort("rank", 1).to_list(length=50)
    return {"scorers": rows}
