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


def _date_window_expr(start_key: str, end_key: str) -> dict:
    """Build a $expr that compares `scheduled_at` after normalising space→T.

    Returns a dict compatible with Mongo's $expr operator. Ensures that values
    stored with either "YYYY-MM-DDTHH:MM:SS" or "YYYY-MM-DD HH:MM:SS" both sort
    correctly into the window [start_key, end_key) where keys are in T-format.
    """
    return {
        "$let": {
            "vars": {"s": {"$replaceOne": {"input": {"$ifNull": ["$scheduled_at", ""]}, "find": " ", "replacement": "T"}}},
            "in": {"$and": [
                {"$gte": ["$$s", start_key]},
                {"$lt": ["$$s", end_key]},
            ]}
        }
    }


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
        q["$expr"] = _date_window_expr(now.strftime("%Y-%m-%dT%H:%M:%S"), end_utc.strftime("%Y-%m-%dT%H:%M:%S"))
    elif status == "finished":
        # Matches finished earlier today (user's local day)
        offset = timedelta(minutes=tz_offset_min)
        now = datetime.now(timezone.utc)
        local_now = now + offset
        local_start_of_day = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_utc = local_start_of_day - offset
        q["status"] = {"$in": ["FT", "AET", "PEN"]}
        q["$expr"] = _date_window_expr(start_utc.strftime("%Y-%m-%dT%H:%M:%S"), now.strftime("%Y-%m-%dT%H:%M:%S"))
        sort_order = -1
    elif date:
        try:
            # `date` is the user-LOCAL calendar date (YYYY-MM-DD). Convert to the
            # UTC window that corresponds to that whole local day for the user.
            d = datetime.fromisoformat(date)
            offset = timedelta(minutes=tz_offset_min)
            local_midnight = d.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
            start_dt = local_midnight - offset
            end_dt = start_dt + timedelta(days=1)
            q["$expr"] = _date_window_expr(
                start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            )
        except Exception:
            pass
        # On-demand backfill: if this date's match count is below threshold,
        # fire sportmonks.fetch_fixtures_by_date and api-sports.fetch_games (football) to top up.
        # Covers BOTH past (history) and future (upcoming fixtures) within ±30 days.
        try:
            existing = await db.matches.count_documents({"sport_slug": sport, **q})
            ago_days = (datetime.now(timezone.utc).date() - datetime.fromisoformat(date).date()).days
            # ago_days < 0 means future date. Backfill if within ±30d and sparse.
            if existing < 5 and abs(ago_days) <= 30:
                from ingestion import upsert_sportmonks_fixture
                from adapters import sportmonks as sm
                cache_key = f"backfill:{sport}:{date}"
                if not cget(cache_key):
                    if sport == "football":
                        for page in range(1, 6):
                            data = await sm.fetch_fixtures_by_date(date, page=page)
                            fixtures = (data or {}).get("data", []) if isinstance(data, dict) else []
                            if not fixtures: break
                            for fx in fixtures:
                                try: await upsert_sportmonks_fixture(fx)
                                except Exception: pass
                            pag = (data or {}).get("pagination") or {}
                            if not pag.get("has_more"): break
                    cset(cache_key, True, 3600)
                    # Re-fetch rows after backfill
                    pass
        except Exception:
            pass
    else:
        # Default: today (in user's TZ)
        offset = timedelta(minutes=tz_offset_min)
        today_utc = datetime.now(timezone.utc)
        local_now = today_utc + offset
        local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = local_start - offset
        end = start + timedelta(days=1)
        q["$expr"] = _date_window_expr(
            start.strftime("%Y-%m-%dT%H:%M:%S"),
            end.strftime("%Y-%m-%dT%H:%M:%S"),
        )

    rows = await db.matches.find(q, {"_id": 0, "raw_data": 0}).sort("scheduled_at", sort_order).to_list(length=limit)

    # Group by league for the dashboard (sort groups by country priority then league tier)
    by_league: dict = {}
    # 🛡️ Multiple providers (Sportmonks, api-sports, StatPal) each register the
    # 2026 World Cup as their own `league_id` — historically appearing as 3
    # separate "World Cup" sidebar entries with duplicate matches. We collapse
    # any league with a WC-ish name (case-insensitive) into a single canonical
    # bucket, then dedupe by (home, away, day).
    def _is_wc_name(n: str) -> bool:
        if not n:
            return False
        n = n.lower()
        return (
            "world cup" in n
            or "world championship" in n
            or "fifa wc" in n
            or "fifa world" in n
        )

    WC_CANONICAL = "wc-2026-canonical"

    def _bucket_key(row):
        # Collapse all WC providers into one canonical bucket.
        if row.get("is_world_cup") or _is_wc_name(row.get("league_name") or ""):
            return WC_CANONICAL
        return row.get("league_id") or "unknown"

    def _normalize_team(n: str) -> str:
        """Normalize provider team-name variants so 'Côte d'Ivoire' and
        'Ivory Coast' dedupe to the same key."""
        if not n:
            return ""
        s = n.strip().lower()
        # Common alias collapses across Sportmonks / api-sports / StatPal.
        ALIASES = {
            "ivory coast": "côte d'ivoire", "cote d'ivoire": "côte d'ivoire",
            "south korea": "korea republic", "korea south": "korea republic",
            "north korea": "korea dpr", "korea north": "korea dpr",
            "iran": "ir iran", "usa": "united states", "us": "united states",
            "uae": "united arab emirates", "england": "england",
            "czechia": "czech republic", "türkiye": "turkey", "turkiye": "turkey",
            "bosnia": "bosnia and herzegovina", "bosnia & herzegovina": "bosnia and herzegovina",
            "cape verde": "cape verde islands",
        }
        return ALIASES.get(s, s)

    for r in rows:
        key = _bucket_key(r)
        if key not in by_league:
            if key == WC_CANONICAL:
                by_league[key] = {
                    "league_id": WC_CANONICAL,
                    "league_name": "FIFA World Cup 2026",
                    "league_logo": r.get("league_logo") or "",
                    "league_country": "World",
                    "matches": [],
                    "_seen": set(),
                }
            else:
                by_league[key] = {
                    "league_id": key,
                    "league_name": r.get("league_name") or "League",
                    "league_logo": r.get("league_logo") or "",
                    "league_country": r.get("league_country") or "International",
                    "matches": [],
                    "_seen": set(),
                }
        # Dedupe matches within a bucket by (normalized_home, normalized_away, day).
        sig = (
            _normalize_team(r.get("home_team_name") or ""),
            _normalize_team(r.get("away_team_name") or ""),
            (r.get("scheduled_at") or "")[:10],
        )
        if sig in by_league[key]["_seen"]:
            continue
        by_league[key]["_seen"].add(sig)
        by_league[key]["matches"].append(r)
    # Drop the internal `_seen` set before returning (not JSON-serializable).
    for g in by_league.values():
        g.pop("_seen", None)
    # Pull tier/priority from leagues collection for stable ordering
    league_ids = [lid for lid in by_league.keys() if lid != WC_CANONICAL]
    league_meta = await db.leagues.find({"id": {"$in": league_ids}}, {"_id": 0, "id": 1, "tier_score": 1, "country_priority": 1}).to_list(length=2000)
    meta_by_id = {m["id"]: m for m in league_meta}
    for g in by_league.values():
        if g["league_id"] == WC_CANONICAL:
            # WC always at the top of the dashboard during tournament window.
            g["_tier"] = 999
            g["_country_priority"] = 0
        else:
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
                    m = await db.matches.find_one({"id": match_id}, {"_id": 0}) or m
                    events = await db.match_events.find({"match_id": match_id}, {"_id": 0}).sort("minute", 1).to_list(length=200)
                    stats = await db.match_statistics.find({"match_id": match_id}, {"_id": 0}).to_list(length=4)
                    lineups = await db.match_lineups.find({"match_id": match_id}, {"_id": 0}).to_list(length=50)
            except Exception:
                pass
            cset(cache_key, True, 60)
    # API-Sports basketball/baseball/hockey: lazy-fetch team statistics on demand
    if need_fetch and m.get("primary_provider") == "api-sports" and m.get("api_sports_game_id") and m.get("sport_slug") in ("basketball", "baseball", "hockey", "volleyball", "rugby", "nba"):
        cache_key = f"as-stats:{match_id}"
        if refresh == 1 or not cget(cache_key):
            try:
                from adapters import apisports
                from ingestion import _upsert_apisports_team_stats, _upsert_apisports_box_score
                data = await apisports.fetch_game_statistics(m["sport_slug"], m["api_sports_game_id"])
                rows = (data or {}).get("response", []) if isinstance(data, dict) else []
                if rows:
                    await _upsert_apisports_team_stats(match_id, m, rows)
                    stats = await db.match_statistics.find({"match_id": match_id}, {"_id": 0}).to_list(length=4)
                # Box score (basketball/nba/baseball/hockey only)
                if m.get("sport_slug") in ("basketball", "nba", "baseball", "hockey"):
                    pdata = await apisports.fetch_game_players(m["sport_slug"], m["api_sports_game_id"])
                    prows = (pdata or {}).get("response", []) if isinstance(pdata, dict) else []
                    if prows:
                        await _upsert_apisports_box_score(match_id, m, prows)
                        m = await db.matches.find_one({"id": match_id}, {"_id": 0}) or m
            except Exception:
                pass
            cset(cache_key, True, 90)
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


@router.get("/matches/{match_id}/standings")
async def match_standings(match_id: str):
    """League standings for this match's competition. Reads from db.standings
    (populated by `sync_sportmonks_standings_live` every hour)."""
    db = get_db()
    m = await db.matches.find_one({"id": match_id}, {"_id": 0, "league_id": 1, "home_team_id": 1, "away_team_id": 1})
    if not m or not m.get("league_id"):
        return {"standings": [], "highlight_team_ids": []}
    rows = await db.standings.find(
        {"league_id": m["league_id"]}, {"_id": 0},
    ).sort("position", 1).to_list(length=40)
    return {
        "standings": rows,
        "highlight_team_ids": [m.get("home_team_id"), m.get("away_team_id")],
    }


@router.get("/matches/{match_id}/momentum")
async def match_momentum(match_id: str):
    """Minute-by-minute attack momentum for the live football match. Reads from
    `match.pressure[]` populated by Sportmonks Pro (empty on lower tiers).
    """
    db = get_db()
    m = await db.matches.find_one({"id": match_id}, {"_id": 0, "pressure": 1, "home_team_id": 1, "away_team_id": 1})
    if not m:
        raise HTTPException(status_code=404, detail="Match not found")
    pressure = m.get("pressure") or []
    out = []
    for p in pressure if isinstance(pressure, list) else []:
        if not isinstance(p, dict):
            continue
        out.append({
            "minute": p.get("minute") or p.get("time"),
            "team_id": p.get("participant_id") or p.get("team_id"),
            "value": p.get("pressure") or p.get("value") or 0,
        })
    return {"momentum": out, "home_team_id": m.get("home_team_id"), "away_team_id": m.get("away_team_id")}


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


# ---------- NBA Playoffs Bracket ----------
NBA_ROUND_ORDER = [
    "First Round",
    "Conference Semifinals",
    "Conference Finals",
    "Finals",
    "NBA Finals",
]


def _classify_nba_round(stage: str | None) -> str | None:
    """Normalise API-Sports / NBA `stage` strings into 4 canonical rounds."""
    if not stage:
        return None
    s = stage.lower()
    if "first" in s or "round 1" in s or "r1" in s:
        return "First Round"
    if "semi" in s and "conf" in s:
        return "Conference Semifinals"
    if "conf" in s and "final" in s:
        return "Conference Finals"
    if "final" in s:
        return "Finals"
    if "playoff" in s:
        return "First Round"
    return None


@router.get("/nba/playoffs")
async def nba_playoffs():
    """NBA playoffs bracket — groups stored NBA games whose `stage` indicates playoffs.

    Falls back to ALL NBA games scheduled after Apr-01 of the current season if no
    explicit stage tagging is present (covers minimal-data API tiers).
    """
    db = get_db()
    # Pull every NBA game with a stage that maps to playoffs
    rows = await db.matches.find(
        {"sport_slug": {"$in": ["nba", "basketball_nba"]}, "stage": {"$ne": None}},
        {"_id": 0, "raw_data": 0},
    ).sort("scheduled_at", 1).to_list(length=2000)
    bucketed: dict = {r: [] for r in NBA_ROUND_ORDER[:4]}
    by_series: dict[str, dict] = {}
    for g in rows:
        rnd = _classify_nba_round(g.get("stage") or "")
        if not rnd:
            continue
        if rnd == "NBA Finals":
            rnd = "Finals"
        # Series key = sorted team IDs so home/away flips don't create duplicates
        h, a = g.get("home_team_id"), g.get("away_team_id")
        if not (h and a):
            continue
        key = f"{rnd}::{'|'.join(sorted([h, a]))}"
        s = by_series.setdefault(key, {
            "round": rnd,
            "home_team_id": h, "away_team_id": a,
            "home_team_name": g.get("home_team_name"), "away_team_name": g.get("away_team_name"),
            "home_team_logo": g.get("home_team_logo"), "away_team_logo": g.get("away_team_logo"),
            "home_wins": 0, "away_wins": 0, "games": [],
        })
        # Track wins
        hs = int(g.get("home_score") or 0); as_ = int(g.get("away_score") or 0)
        finished = (g.get("status") in ("FT", "AET", "PEN", "Ended", "Finished")) and (hs or as_)
        if finished:
            # Normalise scores back to series perspective (home_team_id of series may differ from game)
            if g.get("home_team_id") == s["home_team_id"]:
                if hs > as_: s["home_wins"] += 1
                elif as_ > hs: s["away_wins"] += 1
            else:
                if hs > as_: s["away_wins"] += 1
                elif as_ > hs: s["home_wins"] += 1
        s["games"].append({
            "id": g.get("id"),
            "scheduled_at": g.get("scheduled_at"),
            "status": g.get("status"),
            "home_score": hs, "away_score": as_,
            "home_team_id": g.get("home_team_id"),
            "away_team_id": g.get("away_team_id"),
        })
    for key, s in by_series.items():
        s["games"].sort(key=lambda x: x.get("scheduled_at") or "")
        # winner
        s["winner_team_id"] = None
        if s["home_wins"] >= 4: s["winner_team_id"] = s["home_team_id"]
        elif s["away_wins"] >= 4: s["winner_team_id"] = s["away_team_id"]
        bucketed[s["round"]].append(s)
    return {
        "rounds": [{"name": r, "series": bucketed.get(r, [])} for r in NBA_ROUND_ORDER[:4]],
        "total_series": sum(len(v) for v in bucketed.values()),
    }

