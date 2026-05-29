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
    country: Optional[str] = None,
    tz_offset_min: int = 0,
    limit: int = 500,
):
    db = get_db()
    q: dict = {"sport_slug": sport}
    if league_id:
        q["league_id"] = league_id
    if country:
        q["league_country"] = country

    sort_order = 1  # ascending by default

    if status == "live":
        q["is_live"] = True
    elif status == "upcoming":
        # Matches scheduled later today (user's local day)
        offset = timedelta(minutes=tz_offset_min)
        now = datetime.now(timezone.utc)
        local_now = now + offset
        local_end_of_day = (local_now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)) - timedelta(seconds=1)
        end_utc = local_end_of_day - offset
        q["status"] = {"$in": ["NS", "TBD", "POSTP"]}
        q["scheduled_at"] = {"$gte": now.isoformat(), "$lt": end_utc.isoformat()}
    elif status == "finished":
        # Matches finished earlier today (user's local day)
        offset = timedelta(minutes=tz_offset_min)
        now = datetime.now(timezone.utc)
        local_now = now + offset
        local_start_of_day = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_utc = local_start_of_day - offset
        q["status"] = {"$in": ["FT", "AET", "PEN"]}
        q["scheduled_at"] = {"$gte": start_utc.isoformat(), "$lt": now.isoformat()}
        sort_order = -1
    elif date:
        try:
            d = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
            # Shift local-day boundary into UTC using tz_offset_min
            # tz_offset_min = local_minutes_ahead_of_utc (e.g. Lagos +1h = 60)
            offset = timedelta(minutes=tz_offset_min)
            start = (d - offset).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            end = ((d - offset) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            # Adjust: start_local 00:00 = UTC start - offset (offset positive when local ahead of UTC)
            start = (d.replace(hour=0, minute=0, second=0, microsecond=0) - offset).isoformat()
            end = (d.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1) - offset).isoformat()
            q["scheduled_at"] = {"$gte": start, "$lt": end}
        except Exception:
            pass
    else:
        # Default: today (in user's TZ)
        offset = timedelta(minutes=tz_offset_min)
        today_utc = datetime.now(timezone.utc)
        local_now = today_utc + offset
        local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = (local_start - offset).isoformat()
        end = (local_start + timedelta(days=1) - offset).isoformat()
        q["scheduled_at"] = {"$gte": start, "$lt": end}

    rows = await db.matches.find(q, {"_id": 0, "raw_data": 0}).sort("scheduled_at", sort_order).to_list(length=limit)

    # Group by league for the dashboard (sort groups by country priority then league tier)
    by_league: dict = {}
    for r in rows:
        key = r.get("league_id") or "unknown"
        if key not in by_league:
            by_league[key] = {
                "league_id": key,
                "league_name": r.get("league_name") or "League",
                "league_logo": r.get("league_logo") or "",
                "league_country": r.get("league_country") or "International",
                "matches": [],
            }
        by_league[key]["matches"].append(r)
    # Pull tier/priority from leagues collection for stable ordering
    league_ids = list(by_league.keys())
    league_meta = await db.leagues.find({"id": {"$in": league_ids}}, {"_id": 0, "id": 1, "tier_score": 1, "country_priority": 1}).to_list(length=2000)
    meta_by_id = {m["id"]: m for m in league_meta}
    for g in by_league.values():
        m = meta_by_id.get(g["league_id"], {})
        g["_tier"] = m.get("tier_score", 30)
        g["_country_priority"] = m.get("country_priority", 200)
    grouped = sorted(
        by_league.values(),
        # Order: highest tier first (top European leagues + UEFA + WC at top),
        # then country priority, then alphabetical for stability.
        key=lambda x: (-x["_tier"], x["_country_priority"], x["league_country"] or "", x["league_name"] or ""),
    )
    return {"matches": rows, "grouped": grouped, "count": len(rows)}


@router.get("/matches/live")
async def live_matches():
    db = get_db()
    rows = await db.matches.find({"is_live": True}, {"_id": 0, "raw_data": 0}).sort("scheduled_at", 1).to_list(length=200)
    return {"matches": rows, "count": len(rows)}


@router.get("/matches/{match_id}")
async def match_detail(match_id: str, refresh: int = 0):
    db = get_db()
    m = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Match not found")
    # Lazy-fetch full data on first detail open for Sportmonks football matches
    events = await db.match_events.find({"match_id": match_id}, {"_id": 0}).sort("minute", 1).to_list(length=200)
    stats = await db.match_statistics.find({"match_id": match_id}, {"_id": 0}).to_list(length=4)
    lineups = await db.match_lineups.find({"match_id": match_id}, {"_id": 0}).to_list(length=50)
    # Detect stale legacy data (numeric type IDs, missing team_id prefix) and force a refresh
    stale = False
    if events and any((isinstance(e.get("type"), int) or (isinstance(e.get("type"), str) and e.get("type").isdigit())) for e in events):
        stale = True
    if not stale and stats and any(any(k.startswith("Stat ") or k.isdigit() for k in (s.get("stats") or {}).keys()) for s in stats):
        stale = True
    if not stale and (events or stats or lineups):
        # Old docs had numeric team_id without sm-t- prefix
        sample = (events[:1] + stats[:1] + lineups[:1])
        if any(t and not (isinstance(t, str) and t.startswith("sm-t-")) for t in [d.get("team_id") for d in sample]):
            stale = True
    need_fetch = refresh == 1 or stale or (not events and not stats and not lineups)
    if need_fetch and m.get("primary_provider") == "sportmonks" and m.get("sportmonks_id"):
        cache_key = f"detail-fetch:{match_id}"
        if refresh == 1 or stale or not cget(cache_key):
            try:
                from ingestion import upsert_sportmonks_fixture
                data = await sportmonks.fetch_fixture(m["sportmonks_id"])
                fx = (data or {}).get("data") if isinstance(data, dict) else None
                if isinstance(fx, dict):
                    await upsert_sportmonks_fixture(fx)
                    events = await db.match_events.find({"match_id": match_id}, {"_id": 0}).sort("minute", 1).to_list(length=200)
                    stats = await db.match_statistics.find({"match_id": match_id}, {"_id": 0}).to_list(length=4)
                    lineups = await db.match_lineups.find({"match_id": match_id}, {"_id": 0}).to_list(length=50)
            except Exception:
                pass
            cset(cache_key, True, 60)
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
