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
    country = league.get("country", {}).get("name") if isinstance(league.get("country"), dict) else None
    doc = {
        "id": f"sm-l-{sid}",
        "sport_slug": sport_slug,
        "name": league.get("name"),
        "country": country or league.get("country_id_name") or "World",
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
        "league_country": (league or {}).get("country", {}).get("name") if isinstance((league or {}).get("country"), dict) else None,
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
async def sync_sportmonks_today_and_next(days_ahead: int = 7):
    base = utcnow().date()
    for i in range(days_ahead + 1):
        d = (base + timedelta(days=i)).isoformat()
        try:
            data = await sportmonks.fetch_fixtures_by_date(d)
            fixtures = (data or {}).get("data", []) if isinstance(data, dict) else []
            if isinstance(fixtures, list):
                for fx in fixtures:
                    try:
                        await upsert_sportmonks_fixture(fx)
                    except Exception as e:
                        log.warning(f"sm upsert err: {e}")
            log.info(f"sportmonks {d}: {len(fixtures) if isinstance(fixtures, list) else 0} fixtures")
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


async def sync_apisports_today(sport_slug: str):
    today = utcnow().date().isoformat()
    try:
        data = await apisports.fetch_games(sport_slug, today)
        games = (data or {}).get("response", []) if isinstance(data, dict) else []
        if isinstance(games, list):
            for g in games:
                try:
                    await upsert_apisports_game(sport_slug, g)
                except Exception as e:
                    log.warning(f"as upsert {sport_slug} err: {e}")
        log.info(f"api-sports {sport_slug}: {len(games) if isinstance(games, list) else 0} games")
    except Exception as e:
        log.warning(f"api-sports {sport_slug} sync failed: {e}")


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
        try:
            await sync_sportmonks_today_and_next(days_ahead=7)
        except Exception as e:
            log.warning(f"initial sm sync: {e}")
        for sport in ("basketball", "nba", "baseball", "hockey", "rugby", "handball", "volleyball", "mma", "afl"):
            try:
                await sync_apisports_today(sport)
            except Exception as e:
                log.warning(f"initial as {sport}: {e}")
        try:
            await sync_statpal_tennis()
        except Exception as e:
            log.warning(f"initial statpal tennis: {e}")

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

    async def fixture_daily():
        while True:
            await asyncio.sleep(6 * 3600)
            try:
                await sync_sportmonks_today_and_next(days_ahead=7)
            except Exception:
                pass

    async def statpal_poller():
        while True:
            try:
                await sync_statpal_tennis()
            except Exception:
                pass
            await asyncio.sleep(120)

    asyncio.create_task(initial_sync())
    asyncio.create_task(live_poller())
    asyncio.create_task(fixture_daily())
    asyncio.create_task(statpal_poller())
