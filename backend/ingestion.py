"""Ingestion jobs: pull data from providers, normalize, upsert into MongoDB.

All jobs are async, log failures, and never crash the app. Triggered on startup
and via background asyncio.create_task tasks.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from db import get_db, utcnow_iso, utcnow
from models import new_id
from seed_data import league_tier_score, COUNTRY_PRIORITY
from adapters import sportmonks, apisports, statpal

log = logging.getLogger("ingest")

# ---------- league/team helpers ----------
def _country_score(country: str | None) -> int:
    return COUNTRY_PRIORITY.get((country or "").strip(), 200)


async def upsert_sportmonks_league(league: dict, sport_slug: str = "football"):
    if not league:
        return None
    db = get_db()
    sid = league.get("id")
    # Country can be nested object (when include=country) or null
    country_obj = league.get("country")
    if isinstance(country_obj, dict):
        country = country_obj.get("name")
    elif isinstance(country_obj, str):
        country = country_obj
    else:
        country = None
    if not country:
        country = league.get("country_name") or "International"
    doc = {
        "id": f"sm-l-{sid}",
        "sport_slug": sport_slug,
        "name": league.get("name"),
        "country": country,
        "logo_url": league.get("image_path") or league.get("image_url") or "",
        "type": league.get("type") or "domestic",
        "season": league.get("currentseason", {}).get("name") if isinstance(league.get("currentseason"), dict) else None,
        "sportmonks_id": sid,
        "tier_score": league_tier_score(league.get("name", "")),
        "country_priority": _country_score(country),
        "primary_provider": "sportmonks",
        "updated_at": utcnow_iso(),
    }
    await db.leagues.update_one({"sportmonks_id": sid}, {"$set": doc}, upsert=True)
    return doc["id"]


async def upsert_sportmonks_team(team: dict, sport_slug: str = "football"):
    if not team:
        return None
    db = get_db()
    sid = team.get("id")
    doc = {
        "id": f"sm-t-{sid}",
        "sport_slug": sport_slug,
        "name": team.get("name"),
        "short_code": team.get("short_code") or (team.get("name") or "")[:3].upper(),
        "country": (team.get("country") or {}).get("name") if isinstance(team.get("country"), dict) else None,
        "logo_url": team.get("image_path") or "",
        "sportmonks_id": sid,
        "updated_at": utcnow_iso(),
    }
    await db.teams.update_one({"sportmonks_id": sid}, {"$set": doc}, upsert=True)
    return doc["id"]


# ---------- match upsert ----------
async def upsert_sportmonks_fixture(fx: dict):
    """Upsert a Sportmonks fixture into matches collection."""
    db = get_db()
    fx_id = fx.get("id")
    if not fx_id:
        return None

    # League
    league = fx.get("league") if isinstance(fx.get("league"), dict) else None
    league_doc_id = await upsert_sportmonks_league(league, "football") if league else None
    # Country from league (could be nested object after include=league.country)
    league_country = None
    if league:
        c = league.get("country")
        if isinstance(c, dict):
            league_country = c.get("name")
        elif isinstance(c, str):
            league_country = c
    if not league_country:
        league_country = "International"

    # Participants → home / away
    parts = fx.get("participants") or []
    home_team = away_team = None
    for p in parts:
        meta = p.get("meta") or {}
        if meta.get("location") == "home":
            home_team = p
        elif meta.get("location") == "away":
            away_team = p
    if not home_team and parts:
        home_team = parts[0]
    if not away_team and len(parts) > 1:
        away_team = parts[1]
    home_id = await upsert_sportmonks_team(home_team, "football") if home_team else None
    away_id = await upsert_sportmonks_team(away_team, "football") if away_team else None

    state = fx.get("state") if isinstance(fx.get("state"), dict) else None
    status, status_long = sportmonks.map_status(state)
    scores = sportmonks.extract_scores(fx.get("scores") or [])
    minute = sportmonks.extract_minute(fx.get("periods") or [])

    venue = fx.get("venue") if isinstance(fx.get("venue"), dict) else None

    doc = {
        "sport_slug": "football",
        "league_id": league_doc_id,
        "league_name": (league or {}).get("name"),
        "league_logo": (league or {}).get("image_path") or "",
        "league_country": league_country,
        "home_team_id": home_id,
        "away_team_id": away_id,
        "home_team_name": (home_team or {}).get("name"),
        "away_team_name": (away_team or {}).get("name"),
        "home_team_logo": (home_team or {}).get("image_path") or "",
        "away_team_logo": (away_team or {}).get("image_path") or "",
        "home_short": (home_team or {}).get("short_code") or ((home_team or {}).get("name", "")[:3].upper() if home_team else ""),
        "away_short": (away_team or {}).get("short_code") or ((away_team or {}).get("name", "")[:3].upper() if away_team else ""),
        "scheduled_at": fx.get("starting_at"),
        "status": status,
        "status_long": status_long,
        "minute": minute,
        "home_score": scores["home"],
        "away_score": scores["away"],
        "home_score_ht": scores["home_ht"],
        "away_score_ht": scores["away_ht"],
        "home_score_pen": scores["home_pen"],
        "away_score_pen": scores["away_pen"],
        "venue_name": (venue or {}).get("name"),
        "venue_city": (venue or {}).get("city_name"),
        "primary_provider": "sportmonks",
        "sportmonks_id": fx_id,
        "last_polled_at": utcnow_iso(),
        "is_live": status in ("1H", "2H", "HT", "ET", "BR", "LIVE", "PEN_LIVE"),
    }

    existing = await db.matches.find_one({"sportmonks_id": fx_id})
    if existing:
        await db.matches.update_one({"sportmonks_id": fx_id}, {"$set": doc})
        return existing["id"]
    doc["id"] = new_id()
    doc["created_at"] = utcnow_iso()
    await db.matches.insert_one(doc)
    return doc["id"]


# ---------- API-Sports normalization ----------
async def upsert_apisports_game(sport_slug: str, game: dict):
    db = get_db()
    gid = game.get("id") or (game.get("game", {}) if isinstance(game.get("game"), dict) else {}).get("id")
    if not gid:
        # NBA shape sometimes nested differently
        gid = (game.get("game") or {}).get("id") if isinstance(game.get("game"), dict) else None
    if not gid:
        return None

    teams = game.get("teams") or {}
    home_t = teams.get("home") or {}
    away_t = teams.get("away") or {}
    league = game.get("league") or game.get("competition") or {}
    country = league.get("country", {}) if isinstance(league.get("country"), dict) else {"name": league.get("country")}
    scores = game.get("scores") or {}
    home_score = (scores.get("home") or {}).get("total") if isinstance(scores.get("home"), dict) else scores.get("home")
    away_score = (scores.get("away") or {}).get("total") if isinstance(scores.get("away"), dict) else scores.get("away")
    status_obj = game.get("status") or {}
    short = status_obj.get("short") if isinstance(status_obj, dict) else status_obj
    long_s = status_obj.get("long") if isinstance(status_obj, dict) else status_obj
    is_live = short not in ("NS", "FT", "AET", "PEN", "POST", "CANC", "PST", "TBD", None, "")
    scheduled = game.get("date") or game.get("timestamp") or (game.get("game", {}) or {}).get("date")
    if isinstance(scheduled, int):
        scheduled = datetime.fromtimestamp(scheduled, tz=timezone.utc).isoformat()

    home_name = home_t.get("name") or "Home"
    away_name = away_t.get("name") or "Away"
    league_name = league.get("name") or sport_slug.upper()
    country_name = country.get("name") if isinstance(country, dict) else (country or "World")

    league_doc_id = f"as-l-{league.get('id')}" if league.get("id") else f"as-l-{sport_slug}"
    await db.leagues.update_one(
        {"id": league_doc_id},
        {"$set": {
            "id": league_doc_id, "sport_slug": sport_slug, "name": league_name,
            "country": country_name, "logo_url": league.get("logo") or "",
            "tier_score": league_tier_score(league_name), "country_priority": _country_score(country_name),
            "primary_provider": "api-sports", "api_sports_id": league.get("id"),
            "updated_at": utcnow_iso(),
        }},
        upsert=True,
    )
    home_id = f"as-t-{sport_slug}-{home_t.get('id', 'h')}"
    away_id = f"as-t-{sport_slug}-{away_t.get('id', 'a')}"
    for tid, t in ((home_id, home_t), (away_id, away_t)):
        await db.teams.update_one({"id": tid}, {"$set": {
            "id": tid, "sport_slug": sport_slug, "name": t.get("name"),
            "short_code": (t.get("name") or "")[:3].upper(), "logo_url": t.get("logo") or "",
            "api_sports_id": t.get("id"),
        }}, upsert=True)

    doc = {
        "sport_slug": sport_slug, "league_id": league_doc_id,
        "league_name": league_name, "league_logo": league.get("logo") or "",
        "league_country": country_name,
        "home_team_id": home_id, "away_team_id": away_id,
        "home_team_name": home_name, "away_team_name": away_name,
        "home_team_logo": home_t.get("logo") or "", "away_team_logo": away_t.get("logo") or "",
        "home_short": (home_name or "")[:3].upper(), "away_short": (away_name or "")[:3].upper(),
        "scheduled_at": scheduled, "status": short or "NS", "status_long": long_s or "Not Started",
        "minute": None, "home_score": home_score or 0, "away_score": away_score or 0,
        "home_score_ht": None, "away_score_ht": None,
        "primary_provider": "api-sports", "api_sports_id": gid,
        "is_live": is_live, "last_polled_at": utcnow_iso(),
    }
    existing = await db.matches.find_one({"api_sports_id": gid, "sport_slug": sport_slug})
    if existing:
        await db.matches.update_one({"id": existing["id"]}, {"$set": doc})
        return existing["id"]
    doc["id"] = new_id()
    doc["created_at"] = utcnow_iso()
    await db.matches.insert_one(doc)
    return doc["id"]


# ---------- StatPal tennis normalization ----------
async def upsert_statpal_tennis_match(m: dict):
    db = get_db()
    mid = m.get("id") or m.get("@id")
    if not mid:
        return None
    home = m.get("player_1") or m.get("home") or {}
    away = m.get("player_2") or m.get("away") or {}
    if isinstance(home, str):
        home = {"name": home}
    if isinstance(away, str):
        away = {"name": away}
    home_name = home.get("name") or "Player 1"
    away_name = away.get("name") or "Player 2"
    tournament = m.get("tournament") or m.get("league") or "Tennis"
    status_raw = (m.get("status") or "").lower()
    is_live = "playing" in status_raw or "in progress" in status_raw or "set" in status_raw
    short = "LIVE" if is_live else ("FT" if "finished" in status_raw or "ended" in status_raw else "NS")
    scheduled = m.get("date") or m.get("start_time") or utcnow_iso()

    league_doc_id = f"sp-l-{(tournament or 'tennis').replace(' ', '-').lower()}"
    await db.leagues.update_one(
        {"id": league_doc_id},
        {"$set": {
            "id": league_doc_id, "sport_slug": "tennis", "name": tournament,
            "country": "World", "logo_url": "", "tier_score": 60, "country_priority": 40,
            "primary_provider": "statpal", "statpal_id": tournament,
            "updated_at": utcnow_iso(),
        }},
        upsert=True,
    )
    home_id = f"sp-t-tennis-{home_name.replace(' ', '-').lower()}"
    away_id = f"sp-t-tennis-{away_name.replace(' ', '-').lower()}"
    for tid, n in ((home_id, home_name), (away_id, away_name)):
        await db.teams.update_one({"id": tid}, {"$set": {
            "id": tid, "sport_slug": "tennis", "name": n,
            "short_code": "".join([w[0] for w in n.split()[:3]]).upper() or n[:3].upper(),
            "logo_url": "",
        }}, upsert=True)

    # Sets → match_periods + tiebreaker info in raw_data
    sets = m.get("sets") or m.get("scores") or []
    sets_data = []
    if isinstance(sets, list):
        for i, s in enumerate(sets):
            if isinstance(s, dict):
                sets_data.append({
                    "period": i + 1,
                    "period_name": f"Set {i+1}",
                    "home_score": s.get("home") or s.get("player_1") or s.get("p1"),
                    "away_score": s.get("away") or s.get("player_2") or s.get("p2"),
                    "home_tiebreak": s.get("home_tiebreak") or s.get("tiebreak_home"),
                    "away_tiebreak": s.get("away_tiebreak") or s.get("tiebreak_away"),
                })

    home_score = sum(1 for s in sets_data if (s["home_score"] or 0) > (s["away_score"] or 0))
    away_score = sum(1 for s in sets_data if (s["away_score"] or 0) > (s["home_score"] or 0))

    doc = {
        "sport_slug": "tennis", "league_id": league_doc_id,
        "league_name": tournament, "league_logo": "", "league_country": "World",
        "home_team_id": home_id, "away_team_id": away_id,
        "home_team_name": home_name, "away_team_name": away_name,
        "home_team_logo": "", "away_team_logo": "",
        "home_short": home_name.split(" ")[-1][:3].upper(), "away_short": away_name.split(" ")[-1][:3].upper(),
        "scheduled_at": scheduled, "status": short, "status_long": m.get("status") or short,
        "minute": None, "home_score": home_score, "away_score": away_score,
        "sets": sets_data,
        "primary_provider": "statpal", "statpal_id": mid,
        "is_live": is_live, "last_polled_at": utcnow_iso(),
        "raw_data": {"tournament": tournament, "round": m.get("round")},
    }
    existing = await db.matches.find_one({"statpal_id": mid})
    if existing:
        await db.matches.update_one({"id": existing["id"]}, {"$set": doc})
        return existing["id"]
    doc["id"] = new_id()
    doc["created_at"] = utcnow_iso()
    await db.matches.insert_one(doc)
    return doc["id"]


# ---------- High-level jobs ----------
async def sync_sportmonks_leagues_catalog():
    """Pull complete league catalog so countries/leagues sidebar is populated even before fixtures arrive."""
    log.info("sportmonks leagues catalog sync starting")
    seen = 0
    for page in range(1, 12):  # up to ~600 leagues
        try:
            data = await sportmonks.fetch_all_leagues(page=page)
            leagues = (data or {}).get("data", []) if isinstance(data, dict) else []
            if not isinstance(leagues, list) or not leagues:
                break
            for lg in leagues:
                try:
                    await upsert_sportmonks_league(lg, "football")
                    seen += 1
                except Exception as e:
                    log.warning(f"sm league upsert: {e}")
            pag = (data or {}).get("pagination") or {}
            if not pag.get("has_more"):
                break
        except Exception as e:
            log.warning(f"sm leagues page {page}: {e}")
            break
    log.info(f"sportmonks leagues catalog: {seen} leagues")
    return seen


async def sync_sportmonks_today_and_next(days_ahead: int = 7, days_back: int = 3):
    base = utcnow().date()
    for i in range(-days_back, days_ahead + 1):
        d = (base + timedelta(days=i)).isoformat()
        try:
            # Paginate through all fixtures of the day
            total = 0
            for page in range(1, 8):
                data = await sportmonks.fetch_fixtures_by_date(d, page=page)
                fixtures = (data or {}).get("data", []) if isinstance(data, dict) else []
                if not isinstance(fixtures, list) or not fixtures:
                    break
                for fx in fixtures:
                    try:
                        await upsert_sportmonks_fixture(fx)
                        total += 1
                    except Exception as e:
                        log.warning(f"sm upsert err: {e}")
                pag = (data or {}).get("pagination") or {}
                if not pag.get("has_more"):
                    break
            log.info(f"sportmonks {d}: {total} fixtures")
        except Exception as e:
            log.warning(f"sportmonks date {d} failed: {e}")


async def poll_sportmonks_live():
    try:
        data = await sportmonks.fetch_live()
        fixtures = (data or {}).get("data", []) if isinstance(data, dict) else []
        if isinstance(fixtures, list):
            for fx in fixtures:
                try:
                    await upsert_sportmonks_fixture(fx)
                except Exception as e:
                    log.warning(f"sm live upsert err: {e}")
        return len(fixtures) if isinstance(fixtures, list) else 0
    except Exception as e:
        log.warning(f"sportmonks live poll failed: {e}")
        return 0


async def sync_apisports_today(sport_slug: str, days_back: int = 1, days_ahead: int = 3):
    """Sync games for past N days + next M days for a given API-Sports sport."""
    base = utcnow().date()
    total = 0
    for i in range(-days_back, days_ahead + 1):
        d = (base + timedelta(days=i)).isoformat()
        try:
            data = await apisports.fetch_games(sport_slug, d)
            games = (data or {}).get("response", []) if isinstance(data, dict) else []
            if isinstance(games, list):
                for g in games:
                    try:
                        await upsert_apisports_game(sport_slug, g)
                        total += 1
                    except Exception as e:
                        log.warning(f"as upsert {sport_slug} err: {e}")
        except Exception as e:
            log.warning(f"api-sports {sport_slug} sync {d} failed: {e}")
    log.info(f"api-sports {sport_slug}: {total} games across window")


async def poll_apisports_live():
    """Poll live games for ALL API-Sports sports in one pass."""
    total = 0
    for sport in ("basketball", "nba", "baseball", "hockey", "rugby", "handball", "volleyball", "mma", "afl"):
        try:
            data = await apisports.fetch_games(sport, live=True)
            games = (data or {}).get("response", []) if isinstance(data, dict) else []
            if isinstance(games, list):
                for g in games:
                    try:
                        await upsert_apisports_game(sport, g)
                        total += 1
                    except Exception as e:
                        log.warning(f"as live upsert {sport} err: {e}")
        except Exception as e:
            log.warning(f"api-sports live {sport} failed: {e}")
    return total


async def sync_statpal_cricket():
    """Pull cricket livescores + upcoming. Lightweight schema — store raw in matches."""
    db = get_db()
    seen = 0
    for fetcher, kind in ((statpal.fetch_cricket_livescores, "live"), (statpal.fetch_cricket_upcoming, "upcoming")):
        try:
            data = await fetcher()
        except Exception as e:
            log.warning(f"statpal cricket {kind}: {e}")
            continue
        if not isinstance(data, dict):
            continue
        # StatPal returns nested structures; flatten as much as possible
        candidates = []
        for k in ("matches", "match", "tournament", "tournaments", "data"):
            v = data.get(k)
            if isinstance(v, list):
                candidates.extend([x for x in v if isinstance(x, dict)])
            elif isinstance(v, dict):
                inner = v.get("match") or v.get("matches") or []
                if isinstance(inner, list):
                    candidates.extend([x for x in inner if isinstance(x, dict)])
        for m in candidates:
            mid = m.get("id") or m.get("@id")
            if not mid:
                continue
            doc = {
                "id": f"sp-cr-{mid}",
                "sport_slug": "cricket",
                "primary_provider": "statpal",
                "statpal_id": mid,
                "scheduled_at": m.get("date") or m.get("start_time") or utcnow_iso(),
                "status": "LIVE" if kind == "live" else "NS",
                "is_live": kind == "live",
                "home_team_name": (m.get("home") or {}).get("name") if isinstance(m.get("home"), dict) else (m.get("team_a") or "Team A"),
                "away_team_name": (m.get("away") or {}).get("name") if isinstance(m.get("away"), dict) else (m.get("team_b") or "Team B"),
                "home_team_logo": "", "away_team_logo": "",
                "home_short": "TA", "away_short": "TB",
                "home_score": 0, "away_score": 0,
                "league_country": "International", "league_name": "Cricket",
                "league_id": "sp-l-cricket",
                "raw_data": m,
                "last_polled_at": utcnow_iso(),
            }
            await db.matches.update_one({"statpal_id": mid, "sport_slug": "cricket"}, {"$set": doc}, upsert=True)
            seen += 1
    # Ensure league row exists
    await db.leagues.update_one({"id": "sp-l-cricket"}, {"$set": {
        "id": "sp-l-cricket", "sport_slug": "cricket", "name": "International Cricket",
        "country": "International", "logo_url": "", "tier_score": 60, "country_priority": 40,
        "primary_provider": "statpal",
    }}, upsert=True)
    log.info(f"statpal cricket: {seen} matches")


async def sync_statpal_tennis():
    try:
        data = await statpal.fetch_tennis_livescores()
        # StatPal returns various shapes; try multiple paths
        matches = []
        if isinstance(data, dict):
            tournaments = data.get("tournament") or data.get("tournaments") or []
            if isinstance(tournaments, list):
                for t in tournaments:
                    if isinstance(t, dict):
                        for m in (t.get("matches", {}).get("match") if isinstance(t.get("matches"), dict) else (t.get("matches") or [])):
                            if isinstance(m, dict):
                                m["tournament"] = t.get("name")
                                matches.append(m)
            if not matches:
                m_root = data.get("matches") or data.get("data") or []
                if isinstance(m_root, list):
                    matches.extend([x for x in m_root if isinstance(x, dict)])
        for m in matches:
            try:
                await upsert_statpal_tennis_match(m)
            except Exception as e:
                log.warning(f"statpal tennis upsert err: {e}")
        log.info(f"statpal tennis: {len(matches)} matches")
    except Exception as e:
        log.warning(f"statpal tennis sync failed: {e}")


async def stale_status_sweep():
    """Mark long-running 'live' matches as FT after 4h."""
    db = get_db()
    cutoff = (utcnow() - timedelta(hours=4)).isoformat()
    await db.matches.update_many(
        {"status": {"$in": ["1H", "2H", "HT", "LIVE", "ET", "INPLAY"]}, "scheduled_at": {"$lt": cutoff}},
        {"$set": {"status": "FT", "is_live": False, "status_long": "Full Time (assumed)"}},
    )


# ---------- Background loop ----------
async def start_background_jobs():
    """Kick off long-running background tasks."""

    async def initial_sync():
        # Pull all leagues first so sidebar populates immediately
        try:
            await sync_sportmonks_leagues_catalog()
        except Exception as e:
            log.warning(f"initial leagues catalog: {e}")
        try:
            await sync_sportmonks_today_and_next(days_ahead=7, days_back=3)
        except Exception as e:
            log.warning(f"initial sm sync: {e}")
        for sport in ("basketball", "nba", "baseball", "hockey", "rugby", "handball", "volleyball", "mma", "afl"):
            try:
                await sync_apisports_today(sport, days_back=1, days_ahead=3)
            except Exception as e:
                log.warning(f"initial as {sport}: {e}")
        try:
            await sync_statpal_tennis()
        except Exception as e:
            log.warning(f"initial statpal tennis: {e}")
        try:
            await sync_statpal_cricket()
        except Exception as e:
            log.warning(f"initial statpal cricket: {e}")

    async def live_poller():
        while True:
            try:
                await poll_sportmonks_live()
            except Exception as e:
                log.warning(f"live poll: {e}")
            try:
                await stale_status_sweep()
            except Exception:
                pass
            await asyncio.sleep(20)

    async def apisports_live_poller():
        # Slower than football — 90s cadence
        while True:
            try:
                await poll_apisports_live()
            except Exception as e:
                log.warning(f"apisports live: {e}")
            await asyncio.sleep(90)

    async def fixture_daily():
        while True:
            await asyncio.sleep(6 * 3600)
            try:
                await sync_sportmonks_today_and_next(days_ahead=7, days_back=3)
            except Exception:
                pass
            for sport in ("basketball", "nba", "baseball", "hockey", "rugby", "handball", "volleyball", "mma", "afl"):
                try:
                    await sync_apisports_today(sport, days_back=1, days_ahead=3)
                except Exception:
                    pass

    async def statpal_poller():
        while True:
            try:
                await sync_statpal_tennis()
            except Exception:
                pass
            try:
                await sync_statpal_cricket()
            except Exception:
                pass
            await asyncio.sleep(120)

    asyncio.create_task(initial_sync())
    asyncio.create_task(live_poller())
    asyncio.create_task(apisports_live_poller())
    asyncio.create_task(fixture_daily())
    asyncio.create_task(statpal_poller())
