"""Matches: list, detail, live passthrough, h2h."""
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta, timezone
from typing import Optional
from db import get_db, utcnow_iso
from cache import cget, cset
from adapters import sportmonks
from ingestion import upsert_sportmonks_fixture

router = APIRouter(prefix="/api", tags=["matches"])


def _today_range_iso():
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


@router.get("/matches")
async def list_matches(
    sport: str = "football",
    date: Optional[str] = None,
    status: Optional[str] = Query(None, description="live|upcoming|finished|all"),
    league_id: Optional[str] = None,
    limit: int = 200,
):
    db = get_db()
    q: dict = {"sport_slug": sport}
    if league_id:
        q["league_id"] = league_id
    if date:
        try:
            d = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
            start = d.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            end = (d + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            q["scheduled_at"] = {"$gte": start, "$lt": end}
        except Exception:
            pass
    else:
        start, end = _today_range_iso()
        # If filter is live, fall back to is_live regardless of date
        if status != "live":
            q["scheduled_at"] = {"$gte": start, "$lt": end}

    if status == "live":
        q["is_live"] = True
        q.pop("scheduled_at", None)
    elif status == "upcoming":
        q["status"] = {"$in": ["NS", "TBD", "POSTP"]}
    elif status == "finished":
        q["status"] = {"$in": ["FT", "AET", "PEN"]}

    rows = await db.matches.find(q, {"_id": 0, "raw_data": 0}).sort("scheduled_at", 1).to_list(length=limit)

    # Group by league for the dashboard
    by_league: dict = {}
    for r in rows:
        key = r.get("league_id") or "unknown"
        if key not in by_league:
            by_league[key] = {
                "league_id": key,
                "league_name": r.get("league_name") or "League",
                "league_logo": r.get("league_logo") or "",
                "league_country": r.get("league_country") or "World",
                "matches": [],
            }
        by_league[key]["matches"].append(r)
    grouped = sorted(by_league.values(), key=lambda x: (x["league_country"] or "", x["league_name"] or ""))
    return {"matches": rows, "grouped": grouped, "count": len(rows)}


@router.get("/matches/live")
async def live_matches():
    db = get_db()
    rows = await db.matches.find({"is_live": True}, {"_id": 0, "raw_data": 0}).sort("scheduled_at", 1).to_list(length=200)
    return {"matches": rows, "count": len(rows)}


@router.get("/matches/{match_id}")
async def match_detail(match_id: str):
    db = get_db()
    m = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Match not found")
    events = await db.match_events.find({"match_id": match_id}, {"_id": 0}).sort("minute", 1).to_list(length=200)
    stats = await db.match_statistics.find({"match_id": match_id}, {"_id": 0}).to_list(length=4)
    lineups = await db.match_lineups.find({"match_id": match_id}, {"_id": 0}).to_list(length=50)
    periods = await db.match_periods.find({"match_id": match_id}, {"_id": 0}).sort("period", 1).to_list(length=20)
    return {"match": m, "events": events, "statistics": stats, "lineups": lineups, "periods": periods}


@router.get("/matches/{match_id}/live")
async def match_live_passthrough(match_id: str):
    """Tier-1 passthrough: hit provider directly with 5s cache."""
    db = get_db()
    m = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Match not found")
    cache_key = f"live:{match_id}"
    cached = cget(cache_key)
    if cached:
        return cached
    if m.get("primary_provider") == "sportmonks" and m.get("sportmonks_id"):
        data = await sportmonks.fetch_fixture(m["sportmonks_id"])
        fx = (data or {}).get("data") if isinstance(data, dict) else None
        if isinstance(fx, dict):
            await upsert_sportmonks_fixture(fx)
        result = {"raw": fx, "match_id": match_id, "fetched_at": utcnow_iso()}
    else:
        result = {"raw": None, "match_id": match_id, "fetched_at": utcnow_iso()}
    cset(cache_key, result, 5)
    return result


@router.get("/matches/{match_id}/h2h")
async def head_to_head(match_id: str, limit: int = 10):
    db = get_db()
    m = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Match not found")
    home, away = m.get("home_team_id"), m.get("away_team_id")
    if not (home and away):
        return {"matches": []}
    rows = await db.matches.find(
        {
            "$or": [
                {"home_team_id": home, "away_team_id": away},
                {"home_team_id": away, "away_team_id": home},
            ],
            "id": {"$ne": match_id},
        },
        {"_id": 0, "raw_data": 0},
    ).sort("scheduled_at", -1).to_list(length=limit)
    return {"matches": rows}
