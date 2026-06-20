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

# ---------- enabled-sport gate (admin can toggle from /admin → settings) ----------
_ENABLED_CACHE: dict = {"data": None, "ts": 0.0}
_DEFAULT_ENABLED = {
    "football", "basketball", "tennis", "baseball", "hockey", "cricket",
    "rugby", "nba", "volleyball", "handball", "mma", "f1", "afl", "golf",
}

async def _enabled_sports() -> set[str]:
    """Returns the set of currently-enabled sport slugs. Cached 30 s."""
    import time
    now = time.time()
    cache = _ENABLED_CACHE
    if cache["data"] is not None and now - cache["ts"] < 30:
        return cache["data"]
    try:
        db = get_db()
        doc = await db.app_settings.find_one({"id": "site"}, {"_id": 0}) or {}
        raw = doc.get("enabled_sports")
        result = set(raw) if isinstance(raw, list) and raw else set(_DEFAULT_ENABLED)
    except Exception:
        result = set(_DEFAULT_ENABLED)
    cache["data"] = result
    cache["ts"] = now
    return result

# ---------- league/team helpers ----------
def _normalize_country(s):
    """Title-case country names but preserve uppercase abbreviations like USA, UAE, DR Congo.
    Also collapse provider-specific aliases to a canonical name (e.g. United States → USA)."""
    if not s or not isinstance(s, str):
        return "International"
    parts = s.strip().split()
    out = []
    for p in parts:
        if len(p) <= 3 and p.isupper():
            out.append(p)
        else:
            out.append(p.title())
    norm = " ".join(out) or "International"
    # Canonicalize common aliases across providers
    ALIASES = {
        "United States": "USA",
        "Usa": "USA",
        "U.S.A.": "USA",
        "U S A": "USA",
        "United Arab Emirates": "UAE",
        "Türkiye": "Turkey",
        "Turkiye": "Turkey",
        "Korea Republic": "South Korea",
        "Republic Of Korea": "South Korea",
        "Korea Dpr": "North Korea",
        "Democratic Republic Of Congo": "DR Congo",
        "Congo Dr": "DR Congo",
        "Congo Democratic Republic": "DR Congo",
        "Cote D'Ivoire": "Ivory Coast",
        "Côte D'Ivoire": "Ivory Coast",
        "Cote D'ivoire": "Ivory Coast",
        "Bosnia And Herzegovina": "Bosnia",
        "Bosnia-Herzegovina": "Bosnia",
        "Czech Republic": "Czechia",
        "Czechia": "Czechia",
        "Russian Federation": "Russia",
        "Great Britain": "England",
        "United Kingdom": "England",
        "Republic Of Ireland": "Ireland",
        "Trinidad And Tobago": "Trinidad",
        "Antigua And Barbuda": "Antigua",
        "Saint Kitts And Nevis": "Saint Kitts",
    }
    return ALIASES.get(norm, norm)


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
        "current_season_id": (league.get("currentseason") or {}).get("id") if isinstance(league.get("currentseason"), dict) else None,
        "sportmonks_id": sid,
        "sportmonks_league_id": sid,
        "tier_score": league_tier_score(league.get("name", ""), country),
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
    # If season is included separately at fx root, attach as currentseason on league dict so upsert captures it
    if league and isinstance(fx.get("season"), dict):
        league = {**league, "currentseason": fx.get("season")}
    league_doc_id = await upsert_sportmonks_league(league, "football") if league else None
    # Also separately persist season_id on the match for fast lookup
    season_id = (fx.get("season") or {}).get("id") if isinstance(fx.get("season"), dict) else fx.get("season_id")
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
        "sportmonks_home_id": (home_team or {}).get("id"),
        "sportmonks_away_id": (away_team or {}).get("id"),
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
        # Sportmonks Pro plan extras — capture if present. NB: Sportmonks lowercases
        # include keys on the response (`weatherreport`, `tvstations`).
        # Sportmonks weather has nested temperature; surface a simpler shape for the hero
        "weather": (lambda w: ({
            "temperature_celcius": (w.get("current") or {}).get("temp") if w.get("current") else (w.get("temperature") or {}).get("day") if isinstance(w.get("temperature"), dict) else None,
            "type": (w.get("current") or {}).get("description") or w.get("description"),
            "icon": w.get("icon"),
            "humidity": (w.get("current") or {}).get("humidity") or w.get("humidity"),
            "wind": (w.get("current") or {}).get("wind") or (w.get("wind") or {}).get("speed"),
        }) if isinstance(w, dict) else None)(fx.get("weatherreport") or fx.get("weatherReport") or {}),
        "tv_stations": (lambda raw: list(dict.fromkeys([
            (t.get("tvstation") or {}).get("name") for t in raw
            if isinstance(t, dict) and isinstance(t.get("tvstation"), dict) and (t.get("tvstation") or {}).get("name")
        ]))[:6])(fx.get("tvstations") or fx.get("tvStations") or []) if isinstance(fx.get("tvstations") or fx.get("tvStations"), list) else [],
        "referees": [
            {"name": (r.get("referee") or {}).get("name") if isinstance(r.get("referee"), dict) else r.get("name"),
             "type": (r.get("type") or {}).get("name") if isinstance(r.get("type"), dict) else r.get("type")}
            for r in (fx.get("referees") or []) if isinstance(r, dict)
        ][:5] if isinstance(fx.get("referees"), list) else [],
        "pressure": fx.get("pressure") if isinstance(fx.get("pressure"), list) else None,
        "predictions_raw": fx.get("predictions") if isinstance(fx.get("predictions"), list) else None,
        "coaches": fx.get("coaches") if isinstance(fx.get("coaches"), list) else None,
        # Sidelined: enrich with player names + reason from nested includes
        "sidelined_raw": (lambda raw: [
            {
                "player_id": s.get("player_id"),
                "player_name": (s.get("player") or {}).get("display_name") or (s.get("player") or {}).get("name"),
                "player_image": (s.get("player") or {}).get("image_path"),
                "team_id": s.get("participant_id"),
                "reason": (s.get("type") or {}).get("name") or "Sidelined",
                "type_id": s.get("type_id"),
            }
            for s in raw if isinstance(s, dict)
        ])(fx.get("sidelined") or []) if isinstance(fx.get("sidelined"), list) else [],
        # Comments: minute-by-minute
        "comments": [
            {"minute": c.get("minute"), "extra_minute": c.get("extra_minute"),
             "text": c.get("comment"), "is_goal": bool(c.get("is_goal")),
             "is_important": bool(c.get("is_important")), "order": c.get("order")}
            for c in (fx.get("comments") or []) if isinstance(c, dict) and c.get("comment")
        ] if isinstance(fx.get("comments"), list) else [],
        # MatchFacts with natural language only — keep facts with readable sentences
        "matchfacts": [
            {"text": m.get("natural_language"),
             "participant": m.get("participant"),
             "basis": m.get("basis"),
             "category": m.get("category"),
             "scope": m.get("scope"),
             "type": (m.get("type") or {}).get("name") if isinstance(m.get("type"), dict) else None}
            for m in (fx.get("matchfacts") or [])
            if isinstance(m, dict) and m.get("natural_language")
        ][:60] if isinstance(fx.get("matchfacts"), list) else [],
        "trends": fx.get("trends") if isinstance(fx.get("trends"), list) else None,
        "primary_provider": "sportmonks",
        "sportmonks_id": fx_id,
        "sportmonks_league_id": (league or {}).get("id") if isinstance(league, dict) else None,
        "season_id": season_id,
        "is_world_cup": ((league or {}).get("id") == 732) if isinstance(league, dict) else False,
        "last_polled_at": utcnow_iso(),
        "is_live": status in ("1H", "2H", "HT", "ET", "BR", "LIVE", "PEN_LIVE"),
    }

    existing = await db.matches.find_one({"sportmonks_id": fx_id})
    if existing:
        await db.matches.update_one({"sportmonks_id": fx_id}, {"$set": doc})
        match_doc_id = existing["id"]
    else:
        doc["id"] = new_id()
        doc["created_at"] = utcnow_iso()
        await db.matches.insert_one(doc)
        match_doc_id = doc["id"]

    # ---------- Events / Statistics / Lineups (Tier-2 data for match detail) ----------
    events = fx.get("events") or []
    if isinstance(events, list) and events:
        await db.match_events.delete_many({"match_id": match_doc_id})
        evs = []
        for e in events:
            if not isinstance(e, dict):
                continue
            type_obj = e.get("type") if isinstance(e.get("type"), dict) else None
            type_id = e.get("type_id")
            type_name = (type_obj or {}).get("name") if type_obj else None
            if not type_name and type_id is not None:
                try:
                    type_name = sportmonks.EVENT_TYPE_NAMES.get(int(type_id))
                except (TypeError, ValueError):
                    type_name = None
            if not type_name:
                type_name = f"Event {type_id}" if type_id else "Event"
            part_id = e.get("participant_id")
            related_player = e.get("related_player") if isinstance(e.get("related_player"), dict) else None
            evs.append({
                "id": new_id(),
                "match_id": match_doc_id,
                "minute": e.get("minute"),
                "extra_minute": e.get("extra_minute"),
                "team_id": f"sm-t-{part_id}" if part_id else None,
                "player_id": e.get("player_id"),
                "player_name": e.get("player_name") or "",
                "assist_player_name": e.get("related_player_name") or (related_player or {}).get("name") or "",
                "type": type_name,
                "type_id": type_id,
                "detail": e.get("info") or e.get("addition") or "",
                "provider": "sportmonks",
            })
        if evs:
            await db.match_events.insert_many(evs)

    stats = fx.get("statistics") or []
    if isinstance(stats, list) and stats:
        await db.match_statistics.delete_many({"match_id": match_doc_id})
        # Group by team
        by_team = {}
        for s in stats:
            if not isinstance(s, dict):
                continue
            tid = s.get("participant_id")
            type_obj = s.get("type") if isinstance(s.get("type"), dict) else {}
            type_id = s.get("type_id")
            type_name = type_obj.get("name") if type_obj else None
            if not type_name and type_id is not None:
                try:
                    type_name = sportmonks.STAT_TYPE_NAMES.get(int(type_id))
                except (TypeError, ValueError):
                    type_name = None
            if not type_name:
                type_name = type_obj.get("developer_name") or f"Stat {type_id}"
            val = (s.get("data") or {}).get("value") if isinstance(s.get("data"), dict) else s.get("value")
            by_team.setdefault(tid, {})[type_name] = val
        for tid, kv in by_team.items():
            await db.match_statistics.insert_one({
                "id": new_id(),
                "match_id": match_doc_id,
                "team_id": f"sm-t-{tid}" if tid else None,
                "stats": kv,
                "provider": "sportmonks",
            })

    lineups = fx.get("lineups") or []
    if isinstance(lineups, list) and lineups:
        await db.match_lineups.delete_many({"match_id": match_doc_id})
        ls = []
        for ln in lineups:
            if not isinstance(ln, dict):
                continue
            player_obj = ln.get("player") if isinstance(ln.get("player"), dict) else None
            pos_obj = ln.get("position") if isinstance(ln.get("position"), dict) else None
            type_obj = ln.get("type") if isinstance(ln.get("type"), dict) else None
            type_id = ln.get("type_id")
            # type_id 11 = starting XI, 12 = bench
            is_starter = (type_id == 11) or ((type_obj or {}).get("developer_name") == "LINEUP")
            tid = ln.get("team_id") or ln.get("participant_id")
            # Per-player stats from lineups.details.type — type_id 118 = rating, 5304 = xG, 322 = goals, etc.
            details = ln.get("details") if isinstance(ln.get("details"), list) else []
            rating = None
            xg = None
            for d in details:
                if not isinstance(d, dict):
                    continue
                tid_d = d.get("type_id")
                val = d.get("value") if d.get("value") is not None else d.get("data")
                if isinstance(val, dict):
                    val = val.get("value")
                if tid_d == 118 and val is not None:
                    try: rating = float(val)
                    except Exception: pass
                if tid_d in (5304, 5305) and val is not None:
                    try: xg = float(val)
                    except Exception: pass
            ls.append({
                "id": new_id(),
                "match_id": match_doc_id,
                "team_id": f"sm-t-{tid}" if tid else None,
                "formation": ln.get("formation"),
                "starter": is_starter,
                "player_name": ln.get("player_name") or (player_obj or {}).get("name") or "",
                "player_image": (player_obj or {}).get("image_path") or "",
                "player_number": ln.get("jersey_number"),
                "player_pos": (pos_obj or {}).get("name") if pos_obj else None,
                "position_code": (pos_obj or {}).get("code") if pos_obj else None,
                "grid": ln.get("formation_position") or ln.get("formation_field") or ln.get("grid"),
                "rating": rating,
                "xg": xg,
            })
        if ls:
            await db.match_lineups.insert_many(ls)

    return match_doc_id


# ---------- API-Sports normalization ----------
async def upsert_apisports_game(sport_slug: str, game: dict):
    db = get_db()
    # API-Sports football has its data nested under 'fixture'
    if sport_slug == "football":
        fx_obj = game.get("fixture") or {}
        gid = fx_obj.get("id")
        scheduled = fx_obj.get("date")
        status_obj = fx_obj.get("status") or {}
        short = status_obj.get("short") if isinstance(status_obj, dict) else None
        long_s = status_obj.get("long") if isinstance(status_obj, dict) else None
        # Football scores: goals.home / goals.away (current); score.fulltime etc.
        goals_obj = game.get("goals") or {}
        home_score = goals_obj.get("home")
        away_score = goals_obj.get("away")
        # Override `scores` shape so periods extraction won't crash
        scores = {"home": {"total": home_score}, "away": {"total": away_score}}
    else:
        gid = game.get("id") or (game.get("game", {}) if isinstance(game.get("game"), dict) else {}).get("id")
        if not gid:
            gid = (game.get("game") or {}).get("id") if isinstance(game.get("game"), dict) else None
        scheduled = game.get("date") or game.get("timestamp") or (game.get("game", {}) or {}).get("date")
        scores = game.get("scores") or {}
        home_score_obj = scores.get("home") if isinstance(scores.get("home"), dict) else None
        away_score_obj = scores.get("away") if isinstance(scores.get("away"), dict) else None
        home_score = (home_score_obj or {}).get("total") if home_score_obj else scores.get("home")
        away_score = (away_score_obj or {}).get("total") if away_score_obj else scores.get("away")
        status_obj = game.get("status") or {}
        short = status_obj.get("short") if isinstance(status_obj, dict) else status_obj
        long_s = status_obj.get("long") if isinstance(status_obj, dict) else status_obj

    if not gid:
        return None

    teams = game.get("teams") or {}
    home_t = teams.get("home") or {}
    away_t = teams.get("away") or {}
    league = game.get("league") or game.get("competition") or {}
    country = league.get("country", {}) if isinstance(league.get("country"), dict) else {"name": league.get("country")}
    is_live = short not in ("NS", "FT", "AET", "PEN", "POST", "CANC", "PST", "TBD", None, "")
    if isinstance(scheduled, int):
        scheduled = datetime.fromtimestamp(scheduled, tz=timezone.utc).isoformat()

    home_name = home_t.get("name") or "Home"
    away_name = away_t.get("name") or "Away"
    league_name = league.get("name") or sport_slug.upper()
    country_name = country.get("name") if isinstance(country, dict) else (country or "World")
    country_name = _normalize_country(country_name) if isinstance(country_name, str) else "International"

    # Football: cross-provider dedup. If Sportmonks already has it, skip.
    # If StatPal has it, MERGE logos from this API-Sports record (StatPal has no logos).
    overwrite_id = None
    if sport_slug == "football":
        dup = await _cross_provider_dedup("football", home_name, away_name, scheduled if isinstance(scheduled, str) else "")
        if dup:
            if dup.get("primary_provider") == "sportmonks":
                return dup.get("id")
            if dup.get("primary_provider") == "statpal":
                # We'll overwrite this match with richer API-Sports data (has logos)
                overwrite_id = dup.get("id")

    # Extract periods (basketball Q1-Q4, NBA linescore, hockey periods, MMA fight info)
    periods = []
    home_scores_obj = scores.get("home") if isinstance(scores.get("home"), dict) else {}
    away_scores_obj = scores.get("away") if isinstance(scores.get("away"), dict) else {}
    if sport_slug in ("basketball", "nba"):
        if isinstance(home_scores_obj.get("linescore"), list):
            for i, (h, a) in enumerate(zip(home_scores_obj["linescore"], away_scores_obj.get("linescore", [])), 1):
                try:
                    periods.append({"period": i, "period_name": f"Q{i}" if i <= 4 else f"OT{i-4}", "home_score": int(h) if h else 0, "away_score": int(a) if a else 0})
                except Exception:
                    pass
        else:
            for i in range(1, 5):
                h = home_scores_obj.get(f"quarter_{i}")
                a = away_scores_obj.get(f"quarter_{i}")
                if h is None and a is None:
                    continue
                try:
                    periods.append({"period": i, "period_name": f"Q{i}", "home_score": int(h or 0), "away_score": int(a or 0)})
                except Exception:
                    pass
            for ot_key in ("over_time", "overtime"):
                h = home_scores_obj.get(ot_key)
                a = away_scores_obj.get(ot_key)
                if h is not None or a is not None:
                    try:
                        periods.append({"period": 5, "period_name": "OT", "home_score": int(h or 0), "away_score": int(a or 0)})
                    except Exception:
                        pass
    elif sport_slug == "hockey":
        for i in range(1, 4):
            h = home_scores_obj.get(f"period_{i}") or home_scores_obj.get(f"p{i}")
            a = away_scores_obj.get(f"period_{i}") or away_scores_obj.get(f"p{i}")
            if h is None and a is None:
                continue
            try:
                periods.append({"period": i, "period_name": f"P{i}", "home_score": int(h or 0), "away_score": int(a or 0)})
            except Exception:
                pass
    elif sport_slug == "mma":
        fight = game.get("fight") if isinstance(game.get("fight"), dict) else {}
        rnd = fight.get("round")
        tm = fight.get("time")
        method = fight.get("method")
        if rnd or method:
            periods.append({"period": 1, "period_name": f"R{rnd or '-'}", "home_score": 0, "away_score": 0, "time": tm, "method": method})

    league_doc_id = f"as-l-{league.get('id')}" if league.get("id") else f"as-l-{sport_slug}"
    await db.leagues.update_one(
        {"id": league_doc_id},
        {"$set": {
            "id": league_doc_id, "sport_slug": sport_slug, "name": league_name,
            "country": country_name, "logo_url": league.get("logo") or "",
            "tier_score": league_tier_score(league_name, country_name), "country_priority": _country_score(country_name),
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

    # Capture stage info for NBA playoffs / cup competitions (used by /nba/playoffs endpoint)
    stage_name = None
    raw_stage = game.get("stage") or (league.get("stage") if isinstance(league, dict) else None)
    if isinstance(raw_stage, dict):
        stage_name = raw_stage.get("name")
    elif isinstance(raw_stage, str):
        stage_name = raw_stage

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
        "periods": periods,
        "stage": stage_name,
        "primary_provider": "api-sports", "api_sports_id": gid,
        "api_sports_game_id": gid,
        "api_sports_home_id": home_t.get("id"),
        "api_sports_away_id": away_t.get("id"),
        "is_live": is_live, "last_polled_at": utcnow_iso(),
    }
    existing = await db.matches.find_one({"api_sports_id": gid, "sport_slug": sport_slug})
    if existing:
        await db.matches.update_one({"id": existing["id"]}, {"$set": doc})
        return existing["id"]
    if overwrite_id:
        # Overwrite StatPal dup with richer API-Sports data (has logos)
        await db.matches.update_one({"id": overwrite_id}, {"$set": doc})
        return overwrite_id
    doc["id"] = new_id()
    doc["created_at"] = utcnow_iso()
    await db.matches.insert_one(doc)
    return doc["id"]


# ---------- StatPal tennis normalization ----------
def _parse_tennis_set_score(raw):
    """StatPal encodes tiebreaks like '7.7' (7 set with tb 7) or '6.4' (6 with tb 4).
    Returns (score:int|None, tiebreak:int|None)."""
    if raw is None or raw == "":
        return None, None
    s = str(raw)
    if "." in s:
        a, b = s.split(".", 1)
        try:
            return int(float(a)), int(float(b))
        except Exception:
            return None, None
    try:
        return int(float(s)), None
    except Exception:
        return None, None


async def upsert_statpal_tennis_match(m: dict, tournament_name: str = "Tennis", tournament_id: str = ""):
    db = get_db()
    mid = m.get("id") or m.get("@id")
    if not mid:
        return None
    players = m.get("player") or m.get("players") or []
    if not isinstance(players, list) or len(players) < 2:
        return None
    home = players[0] if isinstance(players[0], dict) else {}
    away = players[1] if isinstance(players[1], dict) else {}
    home_name = home.get("name") or "Player 1"
    away_name = away.get("name") or "Player 2"
    status_raw = (m.get("status") or "").strip()
    sl = status_raw.lower()
    if "finished" in sl or "ended" in sl:
        short = "FT"
    elif "walk over" in sl or "walkover" in sl:
        short = "WO"
    elif "set" in sl or "playing" in sl or "in progress" in sl or "game" in sl:
        short = "LIVE"
    else:
        short = "NS"

    # Sets from s1..s5
    sets_data = []
    for i in range(1, 6):
        h_raw = home.get(f"s{i}")
        a_raw = away.get(f"s{i}")
        if (h_raw in (None, "")) and (a_raw in (None, "")):
            continue
        h_score, h_tb = _parse_tennis_set_score(h_raw)
        a_score, a_tb = _parse_tennis_set_score(a_raw)
        if h_score is None and a_score is None:
            continue
        sets_data.append({
            "period": i,
            "period_name": f"Set {i}",
            "home_score": h_score,
            "away_score": a_score,
            "home_tiebreak": h_tb,
            "away_tiebreak": a_tb,
        })

    try:
        home_score = int(float(home.get("totalscore") or 0))
        away_score = int(float(away.get("totalscore") or 0))
    except Exception:
        home_score = sum(1 for s in sets_data if (s["home_score"] or 0) > (s["away_score"] or 0))
        away_score = sum(1 for s in sets_data if (s["away_score"] or 0) > (s["home_score"] or 0))

    # Parse date dd.mm.yyyy + HH:MM
    sched = utcnow_iso()
    date_str = m.get("date")
    time_str = m.get("time") or "00:00"
    if date_str:
        try:
            from datetime import datetime as _dt
            d_, mo_, y_ = date_str.split(".")
            h_, mn_ = time_str.split(":")[:2]
            sched = _dt(int(y_), int(mo_), int(d_), int(h_), int(mn_), tzinfo=timezone.utc).isoformat()
        except Exception:
            pass

    clean_t = tournament_name.replace("Atp - Singles: ", "").replace("Wta - Singles: ", "").replace("ATP - Singles: ", "").replace("WTA - Singles: ", "")
    league_doc_id = f"sp-l-tennis-{(tournament_id or clean_t).replace(' ', '-').lower()}"
    await db.leagues.update_one(
        {"id": league_doc_id},
        {"$set": {
            "id": league_doc_id, "sport_slug": "tennis", "name": clean_t,
            "country": "International", "logo_url": "", "tier_score": 70, "country_priority": 40,
            "primary_provider": "statpal", "statpal_id": tournament_id or clean_t,
            "updated_at": utcnow_iso(),
        }},
        upsert=True,
    )
    home_id = f"sp-t-tennis-{(home.get('id') or home_name).replace(' ', '-').replace('.', '').lower()}"
    away_id = f"sp-t-tennis-{(away.get('id') or away_name).replace(' ', '-').replace('.', '').lower()}"
    for tid, n in ((home_id, home_name), (away_id, away_name)):
        last = n.split()[-1] if n else "?"
        await db.teams.update_one({"id": tid}, {"$set": {
            "id": tid, "sport_slug": "tennis", "name": n,
            "short_code": last[:3].upper(),
            "logo_url": "",
        }}, upsert=True)

    doc = {
        "sport_slug": "tennis", "league_id": league_doc_id,
        "league_name": clean_t, "league_logo": "", "league_country": "International",
        "home_team_id": home_id, "away_team_id": away_id,
        "home_team_name": home_name, "away_team_name": away_name,
        "home_team_logo": "", "away_team_logo": "",
        "home_short": (home_name.split()[-1] if home_name else "P1")[:3].upper(),
        "away_short": (away_name.split()[-1] if away_name else "P2")[:3].upper(),
        "scheduled_at": sched, "status": short, "status_long": status_raw or short,
        "minute": None, "home_score": home_score, "away_score": away_score,
        "sets": sets_data,
        "primary_provider": "statpal", "statpal_id": mid,
        "is_live": short == "LIVE", "last_polled_at": utcnow_iso(),
        "raw_data": {"tournament": clean_t},
    }
    existing = await db.matches.find_one({"statpal_id": mid, "sport_slug": "tennis"})
    if existing:
        await db.matches.update_one({"id": existing["id"]}, {"$set": doc})
        return existing["id"]
    doc["id"] = new_id()
    doc["created_at"] = utcnow_iso()
    await db.matches.insert_one(doc)
    return doc["id"]
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



async def sync_sportmonks_league_schedule(league_id: int):
    """Pull all fixtures for a single league's CURRENT season (e.g. league 732 → season 26618 = WC 2026).

    This was previously pulling every historical season of league 732 (2006/2010/.../2022)
    which polluted the WC schedule with old games. Fix: look up the league's currentseason
    and ONLY ingest that one season's fixtures.
    """
    from db import get_db
    db = get_db()
    # 1) Resolve currentseason for the league
    try:
        detail = await sportmonks.fetch_league_detail(league_id)
        cur = ((detail or {}).get("data") or {}).get("currentseason") or {}
        season_id = cur.get("id")
    except Exception as e:
        log.warning(f"sm league detail {league_id}: {e}")
        season_id = None
    if not season_id:
        log.warning(f"sm league {league_id}: no current season — skipping")
        return 0
    # 2) Fetch all fixtures for that season
    try:
        data = await sportmonks.fetch_fixtures_by_season(season_id)
    except Exception as e:
        log.warning(f"sm season {season_id}: {e}")
        return 0
    season_doc = (data or {}).get("data") or {}
    fixtures = season_doc.get("fixtures") or []
    if not isinstance(fixtures, list):
        return 0
    total = 0
    for fx in fixtures:
        try:
            await upsert_sportmonks_fixture(fx)
            await db.matches.update_one(
                {"sportmonks_id": fx.get("id")},
                {"$set": {
                    "is_world_cup": True,
                    "competition_id": "wc-2026",
                    "sportmonks_league_id": league_id,
                    "sportmonks_season_id": season_id,
                    "season_year": season_doc.get("name"),
                }},
            )
            total += 1
        except Exception as e:
            log.warning(f"sm wc upsert err: {e}")
    log.info(f"sportmonks league {league_id} season {season_id} ({season_doc.get('name')}): {total} fixtures ingested")
    return total


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
    enabled = await _enabled_sports()
    total = 0
    for sport in ("football", "basketball", "nba", "baseball", "hockey", "rugby", "handball", "volleyball", "mma", "afl"):
        if sport not in enabled:
            continue
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


async def _upsert_apisports_team_stats(match_id: str, match_doc: dict, rows: list) -> None:
    """Upsert per-team statistics for an API-Sports basketball/baseball/hockey game.
    Each row in `rows` looks like {team:{id,name}, statistics:[{name:'Field Goals', value:'34/76'}, ...]} or
    a flat dict of stat→value depending on the sport. Normalises into match_statistics docs.
    """
    db = get_db()
    await db.match_statistics.delete_many({"match_id": match_id})
    sport = match_doc.get("sport_slug")
    home_t_raw = match_doc.get("api_sports_home_id") or match_doc.get("home_team_id")
    away_t_raw = match_doc.get("api_sports_away_id") or match_doc.get("away_team_id")
    # Canonical labels expected by frontend BasketballStatsView gauges/bars
    LABEL_ALIASES = {
        "Field Goals": ["field_goals", "fieldgoals", "fg", "field goals"],
        "Free Throws": ["free_throws", "ft", "freethrows", "free throws", "freethrows_goals", "freethrow_goals"],
        "2-Pointers":  ["two_points", "2_points", "2 pointers", "2-pointers", "twopointers", "two pointers", "twopoint_goals"],
        "3-Pointers":  ["three_points", "3_points", "3 pointers", "3-pointers", "threepointers", "three pointers", "threepoint_goals", "threepoints_goals"],
        "Rebounds":    ["rebounds", "total_rebounds", "totalrebounds"],
        "Defensive rebounds": ["defensive_rebounds", "def_rebounds", "defensiverebounds"],
        "Offensive rebounds": ["offensive_rebounds", "off_rebounds", "offensiverebounds"],
        "Assists":     ["assists"],
        "Turnovers":   ["turnovers"],
        "Steals":      ["steals"],
        "Blocks":      ["blocks"],
        "Fouls":       ["fouls", "personal_fouls", "personalfouls"],
    }
    def _canon(stats_in: dict) -> dict:
        out = dict(stats_in)  # keep originals
        normalised = {str(k).strip().lower().replace("-", "_").replace(" ", "_"): v for k, v in stats_in.items() if v is not None}
        for canonical, aliases in LABEL_ALIASES.items():
            if canonical in out:
                continue
            for alias in aliases:
                key = alias.lower().replace("-", "_").replace(" ", "_")
                if key in normalised:
                    out[canonical] = normalised[key]
                    break
        # Rebounds may arrive as a dict {total, offence, defense}; flatten to canonical labels
        reb = out.get("Rebounds")
        if isinstance(reb, dict):
            total = reb.get("total") or reb.get("Total")
            off = reb.get("offence") or reb.get("offensive") or reb.get("off")
            dfn = reb.get("defense") or reb.get("defensive") or reb.get("def")
            if total is not None: out["Rebounds"] = total
            if off is not None and out.get("Offensive rebounds") is None: out["Offensive rebounds"] = off
            if dfn is not None and out.get("Defensive rebounds") is None: out["Defensive rebounds"] = dfn
        # Convert shooting-stat dicts like {total, attempts, percentage} into "X/Y" string
        # so the frontend regex parser works uniformly.
        for shoot_label in ("Field Goals", "Free Throws", "2-Pointers", "3-Pointers"):
            v = out.get(shoot_label)
            if isinstance(v, dict):
                made = v.get("total") or v.get("made") or 0
                att  = v.get("attempts") or v.get("att") or 0
                out[shoot_label] = f"{made}/{att}"
        return out

    for r in rows:
        if not isinstance(r, dict):
            continue
        team = r.get("team") or {}
        team_id_raw = team.get("id")
        # Map raw API-Sports team id back to our prefixed team id
        our_team_id = match_doc.get("home_team_id") if team_id_raw == home_t_raw else (
            match_doc.get("away_team_id") if team_id_raw == away_t_raw else (
                # Fall back to name match
                match_doc.get("home_team_id") if (team.get("name") or "").strip() == (match_doc.get("home_team_name") or "").strip()
                else match_doc.get("away_team_id")
            )
        )
        stats_map: dict = {}
        # Two shapes observed across sports:
        # A) "statistics": [{name, value}, ...]
        # B) flat per-key dict (NBA shape)
        s = r.get("statistics")
        if isinstance(s, list):
            for it in s:
                if isinstance(it, dict) and it.get("name") is not None:
                    stats_map[str(it["name"])] = it.get("value")
        elif isinstance(s, dict):
            stats_map.update({k: v for k, v in s.items()})
        else:
            stats_map.update({k: v for k, v in r.items() if k not in ("team", "game")})
        stats_map = _canon(stats_map)
        await db.match_statistics.insert_one({
            "id": new_id(), "match_id": match_id,
            "team_id": our_team_id, "team_name": team.get("name") or "",
            "sport_slug": sport, "stats": stats_map,
            "updated_at": utcnow_iso(),
        })


async def _upsert_apisports_box_score(match_id: str, match_doc: dict, rows: list) -> None:
    """Persist per-player box score rows into match.box_score for basketball/nba/baseball/hockey.

    API-Sports payload shape: response: [{player:{id,name}, team:{id,name}, game:{...},
       points, minutes, assists, rebounds.total, blocks, steals, fg:{total,attempts,...}, ...}, ...]
    """
    if not isinstance(rows, list) or not rows:
        return
    db = get_db()
    home_raw = match_doc.get("api_sports_home_id")
    away_raw = match_doc.get("api_sports_away_id")
    box: list = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        player = r.get("player") or {}
        team = r.get("team") or {}
        tid_raw = team.get("id")
        if tid_raw == home_raw:
            our_team_id = match_doc.get("home_team_id")
        elif tid_raw == away_raw:
            our_team_id = match_doc.get("away_team_id")
        else:
            our_team_id = match_doc.get("home_team_id") if (team.get("name") or "").strip() == (match_doc.get("home_team_name") or "").strip() else match_doc.get("away_team_id")
        # Field-goal / 3pt / FT can be nested objects or strings
        def _shoot(o):
            if isinstance(o, dict):
                return {"made": o.get("total"), "att": o.get("attempts"), "pct": o.get("percentage")}
            if isinstance(o, str):
                import re as _re
                mm = _re.match(r"\s*(\d+)\D+(\d+)", o or "")
                if mm: return {"made": int(mm.group(1)), "att": int(mm.group(2)), "pct": None}
            return {"made": None, "att": None, "pct": None}
        reb = r.get("rebounds") if isinstance(r.get("rebounds"), dict) else {}
        box.append({
            "player_id": player.get("id"),
            "name": player.get("name") or "",
            "team_id": our_team_id,
            "team_name": team.get("name") or "",
            "minutes": r.get("minutes") or r.get("min"),
            "points": r.get("points") or r.get("pts"),
            "rebounds": (reb.get("total") if isinstance(reb, dict) else None) or r.get("rebounds") or r.get("reb"),
            "off_reb": reb.get("offence") if isinstance(reb, dict) else r.get("off_reb"),
            "def_reb": reb.get("defense") if isinstance(reb, dict) else r.get("def_reb"),
            "assists": r.get("assists") or r.get("ast"),
            "steals":  r.get("steals") or r.get("stl"),
            "blocks":  r.get("blocks") or r.get("blk"),
            "turnovers": r.get("turnovers") or r.get("to"),
            "fg": _shoot(r.get("field_goals") or r.get("fg")),
            "three": _shoot(r.get("threepoint_goals") or r.get("three_points") or r.get("3pt")),
            "ft": _shoot(r.get("freethrows_goals") or r.get("free_throws") or r.get("ft")),
            "plus_minus": r.get("plus_minus") or r.get("pm"),
            "started": r.get("started") if r.get("started") is not None else (r.get("is_starter")),
        })
    await db.matches.update_one(
        {"id": match_id},
        {"$set": {"box_score": box, "box_score_updated_at": utcnow_iso()}},
    )


# ---------- Sportmonks: standings, top scorers, WC squads ----------
async def upsert_standing(row: dict, league_doc_id: str):
    """Persist one standings row."""
    db = get_db()
    participant = row.get("participant") or {}
    team_id = await upsert_sportmonks_team(participant, "football") if isinstance(participant, dict) and participant else None
    details = row.get("details") or []
    # Sportmonks v3 standings detail type IDs (overall stat_group)
    # 129=played 130=won 131=drawn 132=lost 133=goals_for 134=goals_against 179=goal_diff 187=points
    DETAIL_MAP = {129:"played",130:"won",131:"drawn",132:"lost",133:"goals_for",134:"goals_against",179:"goal_diff",187:"points"}
    parsed = {}
    if isinstance(details, list):
        for d in details:
            if not isinstance(d, dict):
                continue
            # Only consume overall stat_group (skip home/away breakdowns)
            type_obj = d.get("type") if isinstance(d.get("type"), dict) else {}
            grp = (type_obj or {}).get("stat_group")
            if grp and grp != "overall":
                continue
            key = DETAIL_MAP.get(d.get("type_id"))
            if key:
                try:
                    parsed[key] = int(d.get("value") or 0)
                except (TypeError, ValueError):
                    parsed[key] = 0
    doc = {
        "id": f"sm-st-{row.get('id')}",
        "league_id": league_doc_id,
        "season_id": row.get("season_id"),
        "group_id": row.get("group_id"),
        "team_id": team_id,
        "team_name": participant.get("name") if isinstance(participant, dict) else None,
        "team_logo": participant.get("image_path") if isinstance(participant, dict) else None,
        "position": row.get("position"),
        "rank": row.get("position"),
        "played": parsed.get("played", 0),
        "won": parsed.get("won", 0),
        "drawn": parsed.get("drawn", 0),
        "lost": parsed.get("lost", 0),
        "goals_for": parsed.get("goals_for", 0),
        "goals_against": parsed.get("goals_against", 0),
        "goal_diff": parsed.get("goal_diff", parsed.get("goals_for", 0) - parsed.get("goals_against", 0)),
        "points": parsed.get("points", row.get("points", 0)),
        # Legacy/back-compat fields (do not remove — admin UI uses them)
        "MP": parsed.get("played", 0),
        "W": parsed.get("won", 0),
        "D": parsed.get("drawn", 0),
        "L": parsed.get("lost", 0),
        "GF": parsed.get("goals_for", 0),
        "GA": parsed.get("goals_against", 0),
        "form": row.get("form"),
        "raw_details": details,
        "updated_at": utcnow_iso(),
    }
    await db.standings.update_one(
        {"id": doc["id"]},
        {"$set": doc},
        upsert=True,
    )


async def sync_sportmonks_standings_live(league_sm_id: int):
    """Pull live standings for a Sportmonks league."""
    db = get_db()
    try:
        data = await sportmonks.fetch_standings(league_sm_id)
        rows = (data or {}).get("data", []) if isinstance(data, dict) else []
        if not isinstance(rows, list) or not rows:
            return 0
        # Wipe old standings for this league then insert
        league_doc_id = f"sm-l-{league_sm_id}"
        await db.standings.delete_many({"league_id": league_doc_id})
        for r in rows:
            try:
                await upsert_standing(r, league_doc_id)
            except Exception as e:
                log.warning(f"standing upsert: {e}")
        return len(rows)
    except Exception as e:
        log.warning(f"standings {league_sm_id}: {e}")
        return 0


async def sync_sportmonks_standings_all():
    """Pull standings for all tier-1/2 leagues we know about plus FIFA WC 2026."""
    db = get_db()
    # Tier 1+2 leagues (tier_score >= 60) plus WC
    leagues = await db.leagues.find(
        {"sport_slug": "football", "primary_provider": "sportmonks", "tier_score": {"$gte": 60}},
        {"_id": 0, "sportmonks_id": 1, "name": 1},
    ).to_list(length=200)
    sm_ids = {lg.get("sportmonks_id") for lg in leagues if lg.get("sportmonks_id")}
    # Always include FIFA World Cup 2026 (Sportmonks league 732, season 26618)
    sm_ids.add(732)
    total = 0
    for sm_id in sm_ids:
        if sm_id == 732:
            # WC uses the season-based endpoint while the league season is "future".
            try:
                data = await sportmonks.fetch_standings_by_season(26618)
                rows = (data or {}).get("data", []) if isinstance(data, dict) else []
                if isinstance(rows, list) and rows:
                    await db.standings.delete_many({"league_id": "sm-l-732"})
                    for r in rows:
                        try:
                            await upsert_standing(r, "sm-l-732")
                        except Exception as e:
                            log.warning(f"WC standing upsert: {e}")
                    total += len(rows)
            except Exception as e:
                log.warning(f"WC2026 standings: {e}")
        else:
            n = await sync_sportmonks_standings_live(sm_id)
            total += n
    log.info(f"sportmonks standings: {total} rows across {len(sm_ids)} leagues")
    return total


async def sync_sportmonks_scorers_for_season(season_id: int, league_doc_id: str):
    """Pull top scorers for one season → upsert into top_scorers."""
    db = get_db()
    try:
        data = await sportmonks.fetch_top_scorers(season_id)
        rows = (data or {}).get("data", []) if isinstance(data, dict) else []
        if not isinstance(rows, list):
            return 0
        # Filter to goalscorers (type.id = 208) when type info present
        goal_rows = []
        for r in rows:
            t = r.get("type")
            if isinstance(t, dict):
                # Sportmonks: type.developer_name 'TOPSCORER_GOALS' or name 'Goal Scorer'
                name = (t.get("developer_name") or t.get("name") or "").lower()
                if "goal" not in name:
                    continue
            goal_rows.append(r)
        if not goal_rows:
            goal_rows = rows  # fallback
        await db.top_scorers.delete_many({"league_id": league_doc_id})
        for i, r in enumerate(goal_rows[:50], 1):
            player = r.get("player") or {}
            participant = r.get("participant") or {}
            doc = {
                "id": f"sm-ts-{r.get('id')}",
                "league_id": league_doc_id,
                "season_id": season_id,
                "player_id": player.get("id"),
                "player_name": player.get("name") or player.get("display_name") or "Player",
                "player_photo": player.get("image_path"),
                "team_id": participant.get("id"),
                "team_name": participant.get("name"),
                "team_logo": participant.get("image_path"),
                "goals": r.get("total") or 0,
                "rank": r.get("position") or i,
            }
            await db.top_scorers.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        return len(goal_rows)
    except Exception as e:
        log.warning(f"top_scorers season {season_id}: {e}")
        return 0


async def sync_sportmonks_scorers_all():
    """For each tier-1/2 league, try to pull top scorers using its latest known season_id."""
    db = get_db()
    leagues = await db.leagues.find(
        {"sport_slug": "football", "primary_provider": "sportmonks", "tier_score": {"$gte": 80}},
        {"_id": 0, "sportmonks_id": 1, "id": 1, "name": 1},
    ).to_list(length=80)
    total = 0
    for lg in leagues:
        sm_id = lg.get("sportmonks_id")
        if not sm_id:
            continue
        try:
            det = await sportmonks.fetch_league_detail(sm_id)
            ldata = (det or {}).get("data") if isinstance(det, dict) else None
            cs = (ldata or {}).get("currentseason") if isinstance(ldata, dict) else None
            season_id = cs.get("id") if isinstance(cs, dict) else None
            if not season_id:
                continue
            n = await sync_sportmonks_scorers_for_season(season_id, lg["id"])
            total += n
        except Exception as e:
            log.warning(f"scorers for league {sm_id}: {e}")
    log.info(f"sportmonks top scorers: {total} rows")
    return total


async def sync_wc2026_squads():
    """Pull every WC2026 team squad → players collection. Season 26618."""
    db = get_db()
    WC_SEASON = 26618
    try:
        data = await sportmonks.fetch_teams_for_season(WC_SEASON)
        teams = (data or {}).get("data", []) if isinstance(data, dict) else []
    except Exception as e:
        log.warning(f"wc2026 teams: {e}")
        return 0
    # Filter to real national teams (placeholder entries have no country / are bracket slots)
    real_teams = [t for t in teams if isinstance(t, dict) and (t.get("country_id") or 0) > 0 and "Winner" not in (t.get("name") or "") and "Group" not in (t.get("name") or "") or "" == ""]
    # Looser filter: just exclude obvious placeholders
    real_teams = [t for t in teams if isinstance(t, dict) and t.get("name") and not any(x in t.get("name", "") for x in ["Winner ", "Loser ", "1st Group", "2nd Group", "3rd ", "Best 3rd"])]
    total_players = 0
    for team in real_teams[:64]:
        tid = team.get("id")
        if not tid:
            continue
        # Ensure team doc exists
        team_doc_id = await upsert_sportmonks_team(team, "football")
        try:
            sdata = await sportmonks.fetch_team_squad(WC_SEASON, tid)
            roster = (sdata or {}).get("data", []) if isinstance(sdata, dict) else []
        except Exception as e:
            log.warning(f"squad {tid}: {e}")
            continue
        if not isinstance(roster, list):
            continue
        # Sportmonks position IDs (rough): 24=GK, 25=DEF, 26=MID, 27=FWD
        POS_MAP = {24: "GK", 25: "DEF", 26: "MID", 27: "FWD"}
        for entry in roster:
            if not isinstance(entry, dict):
                continue
            player = entry.get("player") or {}
            pos = entry.get("position") or {}
            pos_id = pos.get("id") if isinstance(pos, dict) else None
            pos_name = (pos.get("name") or "").lower() if isinstance(pos, dict) else ""
            short_pos = POS_MAP.get(pos_id)
            if not short_pos:
                if "goalkeeper" in pos_name:
                    short_pos = "GK"
                elif "defend" in pos_name or "back" in pos_name:
                    short_pos = "DEF"
                elif "midfield" in pos_name:
                    short_pos = "MID"
                elif "attack" in pos_name or "forward" in pos_name or "striker" in pos_name or "winger" in pos_name:
                    short_pos = "FWD"
                else:
                    short_pos = "MID"
            # ----- Synthetic fantasy price (calibrated so a £100m budget can field 15) -----
            country_name = (team.get("name") or "").lower().strip()
            top_tier = {"brazil","argentina","france","england","spain","germany","portugal","netherlands","belgium","italy","croatia","uruguay","colombia","morocco"}
            mid_tier = {"japan","south korea","mexico","usa","switzerland","denmark","poland","ecuador","senegal","ghana","ivory coast","côte d'ivoire","saudi arabia","australia","austria","sweden"}
            if country_name in top_tier:
                tier_premium = 0.8
            elif country_name in mid_tier:
                tier_premium = 0.3
            else:
                tier_premium = -0.4
            # Lower base prices so the mean lands around £6.0
            base_price = {"GK": 4.0, "DEF": 4.5, "MID": 5.5, "FWD": 6.5}.get(short_pos, 5.0)
            jersey = entry.get("jersey_number") if isinstance(entry.get("jersey_number"), int) else None
            jersey_bump = 0.0
            if jersey is not None:
                if jersey == 10: jersey_bump = 1.0
                elif jersey == 9: jersey_bump = 0.8
                elif jersey == 7: jersey_bump = 0.6
                elif jersey == 1: jersey_bump = 0.4
                elif jersey <= 11: jersey_bump = 0.3
                elif jersey <= 20: jersey_bump = 0.0
                else: jersey_bump = -0.3
            try:
                h = int.from_bytes(str(pid).encode(), "big") % 7
                dispersion = (h - 3) * 0.1
            except Exception:
                dispersion = 0.0
            raw_price = base_price + tier_premium + jersey_bump + dispersion
            # Snap to 0.5 increments and clamp to [3.5, 10.0]
            snapped = round(raw_price * 2) / 2
            final_price = max(3.5, min(10.0, snapped))
            # Curated star override — known elite players always at the top of the ladder.
            try:
                from star_tiers import star_floor
                pname = player.get("display_name") or player.get("name") or ""
                floor = star_floor(pname)
                if floor and floor > final_price:
                    final_price = min(11.5, floor)
            except Exception:
                pass
            pid = player.get("id")
            if not pid:
                continue
            doc = {
                "id": f"sm-p-{pid}",
                "name": player.get("display_name") or player.get("name") or "Player",
                "team_id": team_doc_id,
                "team_name": team.get("name"),
                "team_logo": team.get("image_path") or "",
                "sportmonks_id": pid,
                "position": short_pos,
                "photo_url": player.get("image_path") or "",
                "country": team.get("name"),
                "price": final_price,
                "shirt_number": jersey,
                "is_wc_2026": True,
                "updated_at": utcnow_iso(),
            }
            await db.players.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
            total_players += 1
    log.info(f"wc2026 squads: {total_players} players across {len(real_teams)} teams")
    return total_players


# ---------- API-Sports football enrichment (cross-provider dedup) ----------
_TEAM_STOPWORDS = {
    "fc", "cf", "ac", "as", "sc", "afc", "cfc", "ssd", "ssc", "us", "ud",
    "real", "club", "athletic", "atletico", "atlético", "deportivo", "olympique",
    "city", "united", "town", "rovers", "wanderers", "albion", "borussia",
    "the", "de", "do", "da", "of", "and", "&",
    "ii", "iii", "u20", "u21", "u23",
}


def _team_tokens(name: str) -> set[str]:
    """Return meaningful 4+ char tokens from a team name (no FC/AC/Real/Olympique etc.)."""
    if not name:
        return set()
    raw = name.lower().replace("-", " ").replace(".", " ").replace("'", " ")
    out = set()
    for w in raw.split():
        if len(w) >= 4 and w not in _TEAM_STOPWORDS:
            out.add(w)
    return out


async def _cross_provider_dedup(sport: str, home_name: str, away_name: str, scheduled_at_iso: str):
    """Check if a match with same teams (fuzzy token-based) within ±24h already exists.
    Tokens drop common prefixes (FC/AC/Real/Olympique/etc.) so 'PSG' ≈ 'Paris Saint-Germain'
    and 'Marseille' ≈ 'Olympique Marseille'. Returns existing doc or None.
    """
    if not (home_name and away_name and scheduled_at_iso):
        return None
    db = get_db()
    try:
        from datetime import datetime as _dt, timedelta as _td
        d = _dt.fromisoformat(scheduled_at_iso.replace("Z", "+00:00"))
        lo = (d - _td(hours=24)).isoformat()
        hi = (d + _td(hours=24)).isoformat()
    except Exception:
        return None
    h_tokens = _team_tokens(home_name)
    a_tokens = _team_tokens(away_name)
    if not h_tokens or not a_tokens:
        return None
    # Pull all candidates in the ±24h window and intersect tokens in-memory
    candidates = await db.matches.find(
        {"sport_slug": sport, "scheduled_at": {"$gte": lo, "$lt": hi}},
        {"_id": 0, "id": 1, "primary_provider": 1, "home_team_name": 1, "away_team_name": 1},
    ).to_list(length=200)
    for c in candidates:
        ch = _team_tokens(c.get("home_team_name") or "")
        ca = _team_tokens(c.get("away_team_name") or "")
        # Match: home tokens overlap home OR away (avoids home/away swaps)
        if (h_tokens & ch and a_tokens & ca) or (h_tokens & ca and a_tokens & ch):
            return c
    return None


def _parse_cricket_score(s):
    """Parse cricket score strings like '490/8d', '232/10', '179', '(fo) 179 & 232'.
    Returns (runs:int, wickets:int|None, declared:bool).
    """
    if not s:
        return 0, None, False
    txt = str(s).strip().lstrip("(fo) ").lstrip("(f/o) ").strip()
    # If "A & B" (multiple innings), sum
    if "&" in txt:
        total = 0
        wkts = None
        decl = False
        for part in txt.split("&"):
            r, w, d = _parse_cricket_score(part.strip())
            total += r or 0
            if w is not None:
                wkts = w
            decl = decl or d
        return total, wkts, decl
    decl = txt.endswith("d")
    if decl:
        txt = txt[:-1]
    if "/" in txt:
        a, b = txt.split("/", 1)
        try:
            return int(a), int(b), decl
        except Exception:
            return 0, None, decl
    try:
        return int(txt), None, decl
    except Exception:
        return 0, None, decl


def _normalize_cricket_innings(raw_match: dict, home_name: str, away_name: str) -> list:
    """Convert StatPal cricket `inning[]` array into our normalized innings shape.
    Each output entry has team_name, runs, wickets, overs, top_batters, top_bowlers.
    """
    raw_innings = raw_match.get("inning") or []
    if isinstance(raw_innings, dict):
        raw_innings = [raw_innings]
    if not isinstance(raw_innings, list):
        return []
    out = []
    for inn in raw_innings:
        if not isinstance(inn, dict):
            continue
        # team: 'localteam' (home) | 'awayteam' (away)
        team_tag = (inn.get("team") or "").lower()
        team_name = home_name if "local" in team_tag else (away_name if "away" in team_tag else inn.get("name") or "")
        # Innings number
        try:
            inn_no = int(inn.get("inningnum") or len(out) + 1)
        except Exception:
            inn_no = len(out) + 1

        # Extract top 4 batters (highest scoring)
        bs = inn.get("batsmanstats") or {}
        players = bs.get("player") or []
        if isinstance(players, dict):
            players = [players]
        batters = []
        runs_total = 0
        for p in players if isinstance(players, list) else []:
            try:
                pts = int(p.get("r") or p.get("runs") or 0)
                runs_total += pts
                batters.append({
                    "name": p.get("batsman") or p.get("name") or "?",
                    "runs": pts,
                    "balls": int(p.get("b") or p.get("balls") or 0),
                    "fours": int(p.get("4s") or p.get("fours") or 0),
                    "sixes": int(p.get("6s") or p.get("sixes") or 0),
                    "not_out": (p.get("bat") or "").lower() == "true",
                })
            except Exception:
                continue
        batters.sort(key=lambda x: -x["runs"])

        # Top 3 bowlers
        bws = inn.get("bowlerstats") or {}
        bplayers = bws.get("player") or []
        if isinstance(bplayers, dict):
            bplayers = [bplayers]
        bowlers = []
        for p in bplayers if isinstance(bplayers, list) else []:
            try:
                bowlers.append({
                    "name": p.get("bowler") or p.get("name") or "?",
                    "overs": float(p.get("o") or p.get("overs") or 0),
                    "runs": int(p.get("r") or p.get("runs") or 0),
                    "wickets": int(p.get("w") or p.get("wickets") or 0),
                    "maidens": int(p.get("m") or p.get("maidens") or 0),
                })
            except Exception:
                continue
        bowlers.sort(key=lambda x: (-x["wickets"], x["runs"]))

        # Total runs/wickets from inning name or total
        # Some StatPal payloads include `total` or `score` keys; otherwise derive
        runs = inn.get("total") or inn.get("score") or runs_total
        wkts = inn.get("wickets") or (10 if (inn.get("status") or "").lower().startswith("all out") else None)
        overs = inn.get("overs") or None
        try:
            runs = int(runs) if runs not in (None, "") else 0
        except Exception:
            runs = runs_total
        try:
            wkts = int(wkts) if wkts not in (None, "") else None
        except Exception:
            pass

        out.append({
            "innings_no": inn_no,
            "team_name": team_name,
            "runs": runs,
            "wickets": wkts,
            "overs": overs,
            "top_batters": batters[:4],
            "top_bowlers": bowlers[:3],
        })
    return out


async def sync_statpal_cricket():
    """Pull cricket livescores + upcoming from StatPal. Properly normalizes the
    `scores.category[].match` shape and extracts innings + top batters/bowlers.
    """
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
        # StatPal cricket response: { scores: { category: [{ id, name (tournament), match: {...} or [{...}] }, ...] } }
        scores = data.get("scores") or data
        categories = scores.get("category") or []
        if isinstance(categories, dict):
            categories = [categories]
        if not isinstance(categories, list):
            categories = []
        for cat in categories:
            tournament = cat.get("name") or "Cricket"
            tournament_id = cat.get("id") or ""
            matches_in_cat = cat.get("match") or []
            if isinstance(matches_in_cat, dict):
                matches_in_cat = [matches_in_cat]
            for m in matches_in_cat if isinstance(matches_in_cat, list) else []:
                mid = m.get("id") or m.get("@id")
                if not mid:
                    continue
                home_obj = m.get("home") if isinstance(m.get("home"), dict) else {}
                away_obj = m.get("away") if isinstance(m.get("away"), dict) else {}
                home_name = home_obj.get("name") or "Team A"
                away_name = away_obj.get("name") or "Team B"
                status_raw = (m.get("status") or "").strip()
                sl = status_raw.lower()
                if "finished" in sl or "ended" in sl:
                    short = "FT"
                elif "live" in sl or "in progress" in sl or "lunch" in sl or "tea" in sl or "innings" in sl:
                    short = "LIVE"
                else:
                    short = "NS"
                # Parse total runs from totalscore
                h_runs, h_wkts, _ = _parse_cricket_score(home_obj.get("totalscore"))
                a_runs, a_wkts, _ = _parse_cricket_score(away_obj.get("totalscore"))
                # If empty totalscore but "stat" has aggregated, use that
                if h_runs == 0 and (home_obj.get("stat") or ""):
                    h_runs, _, _ = _parse_cricket_score(home_obj.get("stat"))
                if a_runs == 0 and (away_obj.get("stat") or ""):
                    a_runs, _, _ = _parse_cricket_score(away_obj.get("stat"))
                # Scheduled at — parse dd.mm.yyyy HH:MM
                sched = utcnow_iso()
                date_str = m.get("date")
                time_str = m.get("time") or "00:00"
                if date_str and "." in date_str:
                    try:
                        d_, mo_, y_ = date_str.split(".")
                        h_, mn_ = time_str.split(":")[:2]
                        sched = datetime(int(y_), int(mo_), int(d_), int(h_), int(mn_), tzinfo=timezone.utc).isoformat()
                    except Exception:
                        pass
                # League row (one per tournament)
                league_doc_id = f"sp-l-cricket-{tournament_id or tournament.replace(' ', '-').lower()}"
                await db.leagues.update_one(
                    {"id": league_doc_id},
                    {"$set": {
                        "id": league_doc_id, "sport_slug": "cricket", "name": tournament,
                        "country": "International", "logo_url": "", "tier_score": 70, "country_priority": 3,
                        "primary_provider": "statpal", "statpal_id": tournament_id,
                        "updated_at": utcnow_iso(),
                    }},
                    upsert=True,
                )
                # Team rows
                h_id = f"sp-t-cricket-{(home_obj.get('id') or home_name).replace(' ', '-').lower()}"
                a_id = f"sp-t-cricket-{(away_obj.get('id') or away_name).replace(' ', '-').lower()}"
                for tid, n in ((h_id, home_name), (a_id, away_name)):
                    await db.teams.update_one(
                        {"id": tid},
                        {"$set": {"id": tid, "sport_slug": "cricket", "name": n, "short_code": (n.split()[0][:3] if n else "—").upper(), "logo_url": ""}},
                        upsert=True,
                    )
                # Normalize innings
                innings_list = _normalize_cricket_innings(m, home_name, away_name)
                # Match comment / result string
                comment = m.get("comment") or {}
                result_text = comment.get("post") if isinstance(comment, dict) else None
                doc = {
                    "id": f"sp-cr-{mid}",
                    "sport_slug": "cricket",
                    "primary_provider": "statpal",
                    "statpal_id": mid,
                    "scheduled_at": sched,
                    "status": short, "status_long": status_raw or short,
                    "is_live": short == "LIVE",
                    "home_team_id": h_id, "away_team_id": a_id,
                    "home_team_name": home_name, "away_team_name": away_name,
                    "home_team_logo": "", "away_team_logo": "",
                    "home_short": (home_name.split()[0][:3] if home_name else "TA").upper(),
                    "away_short": (away_name.split()[0][:3] if away_name else "TB").upper(),
                    "home_score": h_runs, "away_score": a_runs,
                    "league_country": "International", "league_name": tournament,
                    "league_id": league_doc_id, "league_logo": "",
                    "match_format": m.get("type") or "",
                    "venue_name": m.get("venue") or "",
                    "innings": innings_list,
                    "result_text": result_text,
                    "raw_data": {"tournament": tournament, "comment": comment, "match_id": mid},
                    "last_polled_at": utcnow_iso(),
                }
                await db.matches.update_one(
                    {"statpal_id": mid, "sport_slug": "cricket"},
                    {"$set": doc},
                    upsert=True,
                )
                seen += 1
    log.info(f"statpal cricket: {seen} matches ingested")
    return seen


async def sync_statpal_football():
    """StatPal football livescores — supplements API-Sports/Sportmonks with extra live leagues."""
    db = get_db()
    seen = 0
    try:
        data = await statpal.fetch_football_livescores()
    except Exception as e:
        log.warning(f"statpal football fetch: {e}")
        return 0
    if not isinstance(data, dict):
        return 0
    root = data.get("livescore") or data.get("livescores") or data
    if not isinstance(root, dict):
        return 0
    categories = root.get("league") or root.get("category") or root.get("categories") or root.get("tournament") or []
    if isinstance(categories, dict):
        categories = [categories]
    if not isinstance(categories, list):
        return 0
    for cat in categories:
        if not isinstance(cat, dict):
            continue
        league_name = cat.get("name") or "Football"
        league_id = str(cat.get("id") or "")
        country_obj = cat.get("country")
        if isinstance(country_obj, dict):
            country = country_obj.get("name") or "International"
        else:
            country = country_obj or "International"
        if isinstance(country, str):
            country = _normalize_country(country)
        matches = cat.get("match") or cat.get("matches") or []
        if isinstance(matches, dict):
            matches = [matches]
        if not isinstance(matches, list):
            continue
        league_doc_id = f"sp-l-football-{league_id or league_name.replace(' ', '-').lower()}"
        await db.leagues.update_one(
            {"id": league_doc_id},
            {"$set": {
                "id": league_doc_id, "sport_slug": "football", "name": league_name,
                "country": country, "logo_url": "", "tier_score": 30,
                "country_priority": _country_score(country),
                "primary_provider": "statpal", "statpal_id": league_id or league_name,
                "updated_at": utcnow_iso(),
            }},
            upsert=True,
        )
        for m in matches:
            if not isinstance(m, dict):
                continue
            mid = m.get("id") or m.get("@id")
            if not mid:
                continue
            home = m.get("home") or m.get("local") or {}
            away = m.get("away") or m.get("visitor") or {}
            if isinstance(home, str):
                home = {"name": home}
            if isinstance(away, str):
                away = {"name": away}
            home_name = home.get("name") or "Home"
            away_name = away.get("name") or "Away"
            # Dedup vs sportmonks/api-sports
            sched_raw = m.get("date") or m.get("time") or utcnow_iso()
            try:
                # StatPal date format dd.mm.yyyy + HH:MM
                from datetime import datetime as _dt
                if m.get("date") and "." in m.get("date", ""):
                    d_, mo_, y_ = m["date"].split(".")
                    tt = (m.get("time") or "00:00").split(":")
                    sched_iso = _dt(int(y_), int(mo_), int(d_), int(tt[0]), int(tt[1]), tzinfo=timezone.utc).isoformat()
                else:
                    sched_iso = sched_raw
            except Exception:
                sched_iso = sched_raw
            dup = await _cross_provider_dedup("football", home_name, away_name, sched_iso)
            if dup and dup.get("primary_provider") in ("sportmonks", "api-sports"):
                continue
            home_score = home.get("totalscore") or home.get("goals") or 0
            away_score = away.get("totalscore") or away.get("goals") or 0
            try:
                home_score = int(home_score)
                away_score = int(away_score)
            except Exception:
                home_score = 0
                away_score = 0
            # Fallback: parse from ft.score "[1-0]" if main goals are zero but ft has a score
            ft_obj = m.get("ft") if isinstance(m.get("ft"), dict) else None
            if ft_obj and home_score == 0 and away_score == 0:
                ft_score = (ft_obj.get("score") or "").strip("[]")
                if "-" in ft_score:
                    try:
                        h, a = ft_score.split("-")
                        home_score = int(h.strip())
                        away_score = int(a.strip())
                    except Exception:
                        pass
            status_raw = (m.get("status") or "").strip()
            sl = status_raw.lower()
            import re as _re
            if "finished" in sl or "ended" in sl or sl == "ft":
                short = "FT"
                is_live = False
            elif _re.match(r"^\d{1,2}:\d{2}$", sl):
                # Status is just the scheduled kickoff time (e.g. "18:00") — not live
                short = "NS"
                is_live = False
            elif "half" in sl or " min" in sl or sl.endswith("min") or "ht" in sl.split() or "live" in sl:
                short = "LIVE"
                is_live = True
            else:
                short = "NS"
                is_live = False
            doc = {
                "id": f"sp-fb-{mid}",
                "sport_slug": "football",
                "league_id": league_doc_id, "league_name": league_name,
                "league_logo": "", "league_country": country,
                "home_team_id": f"sp-t-fb-{home_name.replace(' ', '-').lower()}",
                "away_team_id": f"sp-t-fb-{away_name.replace(' ', '-').lower()}",
                "home_team_name": home_name, "away_team_name": away_name,
                "home_team_logo": "", "away_team_logo": "",
                "home_short": home_name[:3].upper(), "away_short": away_name[:3].upper(),
                "scheduled_at": sched_iso, "status": short, "status_long": status_raw or short,
                "minute": None, "home_score": home_score, "away_score": away_score,
                "primary_provider": "statpal", "statpal_id": mid,
                "is_live": is_live, "last_polled_at": utcnow_iso(),
            }
            # 🛡️ Skip if a Sportmonks WC2026 match already exists for the same
            # teams + scheduled day. Without this guard, StatPal silently
            # creates duplicate WC fixtures under its own `statpal_id`, which
            # then appear/disappear from the football tab depending on which
            # provider's poll won the last race. WC matches are Sportmonks-only.
            wc_dup = await db.matches.find_one(
                {"is_world_cup": True,
                 "home_team_name": home_name, "away_team_name": away_name,
                 "scheduled_at": {"$regex": f"^{sched_iso[:10]}"}},
                {"_id": 0, "id": 1},
            )
            if wc_dup:
                # Don't insert/overwrite — the canonical Sportmonks doc wins.
                continue
            await db.matches.update_one({"statpal_id": mid, "sport_slug": "football"}, {"$set": doc}, upsert=True)
            seen += 1
    # Enrich StatPal football matches with logos from existing teams index (API-Sports/Sportmonks have logos for many overlapping clubs)
    try:
        fixed = await _enrich_statpal_logos()
    except Exception as e:
        log.warning(f"statpal logo enrichment failed: {e}")
        fixed = 0
    log.info(f"statpal football: {seen} matches | {fixed} logos enriched")
    return seen


async def _enrich_statpal_logos() -> int:
    """Look up team names in the teams collection (Sportmonks/API-Sports have logos for many overlapping clubs)
    and copy logo_url onto StatPal match docs missing logos.
    Uses normalized name + word-token matching to handle abbreviations like 'Bardejov W' vs 'Partizán Bardejov'."""
    import re as _re
    db = get_db()
    teams = await db.teams.find(
        {"logo_url": {"$nin": [None, ""]}, "sport_slug": "football"},
        {"_id": 0, "name": 1, "logo_url": 1, "id": 1},
    ).to_list(length=None)

    STOPWORDS = {
        "fc", "cf", "sc", "ac", "afc", "sk", "sv", "cd", "ud", "cs", "ss", "club", "us",
        "de", "del", "la", "el", "the", "al", "do", "da", "y", "i", "e",
        "u17", "u18", "u19", "u20", "u21", "u23", "ii", "iii", "jr", "w", "women", "youth",
        "reserves", "reserve", "b", "2", "3",
    }
    # Common short-form prefixes used by StatPal — expand to full word to help matching
    EXPAND = {
        "atl": "atletico", "ind": "independiente", "dep": "deportivo",
        "din": "dinamo", "spt": "sporting", "rcd": "real",
        "est": "estudiantes", "univ": "universidad", "u": "universidad",
        "ce": "centro", "ad": "atletico",
    }
    def _norm(n: str) -> str:
        n = (n or "").lower().strip()
        # Strip accents using unicode decomposition
        try:
            import unicodedata as _ud
            n = "".join(c for c in _ud.normalize("NFD", n) if _ud.category(c) != "Mn")
        except Exception:
            pass
        n = _re.sub(r"[\.\,\(\)\'\"\-/]", " ", n)
        n = _re.sub(r"\s+", " ", n).strip()
        return n

    def _tokens(n: str) -> list[str]:
        raw_words = _norm(n).split()
        # Expand short-form prefixes
        expanded = []
        for w in raw_words:
            expanded.append(w)
            if w in EXPAND:
                expanded.append(EXPAND[w])
        return [w for w in expanded if w not in STOPWORDS and len(w) >= 4]

    # Build keyed indexes — multiple keys per team
    full_idx: dict[str, str] = {}
    norm_idx: dict[str, str] = {}
    # Per-team token sets for intersection lookups
    team_records: list[tuple[set[str], str]] = []  # (token_set, logo)
    word_idx: dict[str, list[int]] = {}  # token → list of team_record indices
    for t in teams:
        nm = t.get("name") or ""
        logo = t.get("logo_url")
        if not nm or not logo:
            continue
        full_idx.setdefault(nm.strip().lower(), logo)
        norm_idx.setdefault(_norm(nm), logo)
        toks = set(_tokens(nm))
        if toks:
            idx = len(team_records)
            team_records.append((toks, logo))
            for w in toks:
                word_idx.setdefault(w, []).append(idx)

    if not full_idx:
        return 0

    def _lookup(name: str):
        if not name:
            return None
        # 1. exact match
        v = full_idx.get(name.lower().strip())
        if v:
            return v
        # 2. normalized match
        norm = _norm(name)
        v = norm_idx.get(norm)
        if v:
            return v
        # 3. token-set intersection — find teams containing ALL of the source's significant tokens
        src_toks = set(_tokens(name))
        if not src_toks:
            return None
        # Candidate teams: union of records containing any source token, then filter to those containing ALL tokens
        candidate_idxs = set()
        for tok in src_toks:
            candidate_idxs.update(word_idx.get(tok, []))
        full_matches = [i for i in candidate_idxs if src_toks.issubset(team_records[i][0])]
        if len(full_matches) == 1:
            return team_records[full_matches[0]][1]
        # 4. Single-token uniqueness fallback — use the longest source token if it maps to exactly one team
        for tok in sorted(src_toks, key=len, reverse=True):
            cands_i = word_idx.get(tok, [])
            cand_logos = {team_records[i][1] for i in cands_i}
            if len(cand_logos) == 1 and len(tok) >= 5:
                return next(iter(cand_logos))
        return None

    broken = await db.matches.find(
        {"primary_provider": "statpal", "sport_slug": "football",
         "$or": [{"home_team_logo": ""}, {"away_team_logo": ""}, {"home_team_logo": None}, {"away_team_logo": None}]},
        {"_id": 0, "id": 1, "home_team_name": 1, "away_team_name": 1, "home_team_logo": 1, "away_team_logo": 1},
    ).to_list(length=None)
    fixed = 0
    for m in broken:
        upd = {}
        if not m.get("home_team_logo"):
            h_logo = _lookup(m.get("home_team_name"))
            if h_logo:
                upd["home_team_logo"] = h_logo
        if not m.get("away_team_logo"):
            a_logo = _lookup(m.get("away_team_name"))
            if a_logo:
                upd["away_team_logo"] = a_logo
        if upd:
            await db.matches.update_one({"id": m["id"]}, {"$set": upd})
            fixed += 1
    return fixed


async def sync_statpal_tennis():
    """StatPal shape: {livescores: {tournament: [{id, name, match: [...]}]}}."""
    seen = 0
    for fetcher in (statpal.fetch_tennis_livescores, statpal.fetch_tennis_tournaments):
        try:
            data = await fetcher()
        except Exception as e:
            log.warning(f"statpal tennis fetch: {e}")
            continue
        if not isinstance(data, dict):
            continue
        root = data.get("livescores") or data.get("tournaments") or data
        if not isinstance(root, dict):
            continue
        tournaments = root.get("tournament") or root.get("tournaments") or []
        if isinstance(tournaments, dict):
            tournaments = [tournaments]
        if not isinstance(tournaments, list):
            continue
        for t in tournaments:
            if not isinstance(t, dict):
                continue
            t_name = t.get("name") or "Tennis"
            t_id = str(t.get("id") or "")
            matches = t.get("match") or t.get("matches") or []
            if isinstance(matches, dict):
                matches = [matches]
            if not isinstance(matches, list):
                continue
            for m in matches:
                if isinstance(m, dict):
                    try:
                        await upsert_statpal_tennis_match(m, tournament_name=t_name, tournament_id=t_id)
                        seen += 1
                    except Exception as e:
                        log.warning(f"statpal tennis upsert err: {e}")
    log.info(f"statpal tennis: {seen} matches")


async def stale_status_sweep():
    """Mark long-running 'live' matches as FT after 4h."""
    db = get_db()
    cutoff = (utcnow() - timedelta(hours=4)).isoformat()
    await db.matches.update_many(
        {"status": {"$in": ["1H", "2H", "HT", "LIVE", "ET", "INPLAY"]}, "scheduled_at": {"$lt": cutoff}},
        {"$set": {"status": "FT", "is_live": False, "status_long": "Full Time (assumed)"}},
    )


# ---------- WC Fantasy Game generator + state machine ----------
async def _resolve_team_ids_for_groups() -> dict:
    """Map group letter -> [team_id]. Tries to match WC2026 groups (by team name) against
    teams collection. Returns dict {'A': [team_id, ...], ...}."""
    db = get_db()
    groups = await db.wc2026_groups.find({}, {"_id": 0}).to_list(length=20)
    out = {}
    for g in groups:
        letter = g.get("group")
        team_ids: list[str] = []
        for name in g.get("teams") or []:
            t = await db.teams.find_one(
                {"$or": [{"name": name}, {"name": {"$regex": f"^{name}$", "$options": "i"}}]},
                {"_id": 0, "id": 1},
            )
            if t:
                team_ids.append(t["id"])
        out[letter] = team_ids
    return out


async def generate_wc_games() -> int:
    """Daily generator: create wc_games rows for matches/groups/rounds not yet created.
    Returns the number of rows created."""
    db = get_db()
    cfg_rows = await db.wc_game_config.find({"is_active": True}, {"_id": 0}).to_list(length=50)
    cfg_by = {(c["game_type"], c["stage"]): c for c in cfg_rows}
    created = 0
    now = utcnow()

    # ---- Match games: one wc_game per WC match not yet generated ----
    match_cfg = cfg_by.get(("match", "any"))
    if match_cfg:
        wc_matches = await db.matches.find(
            {"$or": [{"is_world_cup": True}, {"competition_id": "wc-2026"}, {"sportmonks_league_id": 732}]},
            {"_id": 0, "id": 1, "scheduled_at": 1, "home_team_id": 1, "away_team_id": 1, "status": 1},
        ).to_list(length=2000)
        for m in wc_matches:
            if not m.get("scheduled_at"):
                continue
            existing = await db.wc_games.find_one({"game_type": "match", "match_id": m["id"]})
            if existing:
                continue
            try:
                ko = datetime.fromisoformat(m["scheduled_at"].replace("Z", "+00:00"))
            except Exception:
                continue
            opens_at = ko - timedelta(hours=match_cfg["opens_hours_before"])
            # Match games close 30 minutes BEFORE kickoff so users can't sneak
            # a pick in while the team news is dropping.
            closes_at = ko - timedelta(minutes=30)
            row = {
                "id": new_id(), "game_type": "match", "stage": "any",
                "config_id": match_cfg["id"], "match_id": m["id"],
                "card_limit_current": match_cfg["card_limit_current"],
                "points_multiplier": match_cfg["points_multiplier"],
                "opens_at": opens_at.isoformat(), "closes_at": closes_at.isoformat(),
                "status": "upcoming", "total_entries": 0,
                "eligible_team_ids": [t for t in (m.get("home_team_id"), m.get("away_team_id")) if t],
                "created_at": now.isoformat(),
            }
            await db.wc_games.insert_one(row)
            created += 1

    # ---- Group games: derive from actual fixtures, NOT stale group seeds ----
    # WC2026 group draw can shift right up to draw day; seeded group rows go stale fast.
    # Strategy: cluster the first 24 sorted MD1 fixtures into 12 pairs (2 matches per group
    # in WC2026), assign letters A-L by chronological pairing. Then MD2/3 follow the same
    # 24-match windows.
    sorted_wc = await db.matches.find(
        {"is_world_cup": True, "scheduled_at": {"$gte": "2026-06-01"}},
        {"_id": 0, "id": 1, "home_team_id": 1, "away_team_id": 1, "scheduled_at": 1, "home_team_name": 1, "away_team_name": 1},
    ).sort("scheduled_at", 1).to_list(length=200)
    # Take first 72 (24 per matchday × 3 matchdays = group stage)
    group_stage_matches = [m for m in sorted_wc if m.get("home_team_id") and m.get("away_team_id")][:72]
    # Build groups: for MD1 we don't know which 4 teams cluster together without group_id
    # from Sportmonks. We treat each consecutive PAIR of matches as a group's MD1.
    # NOTE: This is heuristic — works perfectly once FIFA draw publishes & sportmonks tags group_id.
    groups_dynamic: dict[str, list[str]] = {}  # letter -> [team_id]
    for i, pair_start in enumerate(range(0, min(24, len(group_stage_matches)), 2)):
        letter = chr(ord("A") + i)
        if pair_start + 1 < len(group_stage_matches):
            m1 = group_stage_matches[pair_start]
            m2 = group_stage_matches[pair_start + 1]
            tids = list({m1["home_team_id"], m1["away_team_id"], m2["home_team_id"], m2["away_team_id"]})
            if len(tids) == 4:
                groups_dynamic[letter] = tids
    # If dynamic grouping failed (e.g. teams overlap = misclustered), fall back to seeded
    if len(groups_dynamic) < 12:
        groups_dynamic = await _resolve_team_ids_for_groups()
    for letter, tids in groups_dynamic.items():
        if not tids:
            continue
        # All matches where BOTH teams are in this group
        group_matches = [m for m in sorted_wc if m.get("home_team_id") in tids and m.get("away_team_id") in tids]
        group_matches.sort(key=lambda m: m.get("scheduled_at") or "")        # Group into matchdays of 2 matches each
        matchdays: list[list[dict]] = []
        cur: list[dict] = []
        for m in group_matches:
            cur.append(m)
            if len(cur) == 2:
                matchdays.append(cur)
                cur = []
        if cur:
            matchdays.append(cur)
        for idx, day_matches in enumerate(matchdays[:3], start=1):
            stage = f"group_md{idx}"
            cfg = cfg_by.get(("group", stage))
            if not cfg:
                continue
            existing = await db.wc_games.find_one({"game_type": "group", "group_letter": letter, "matchday": idx})
            if existing:
                continue
            try:
                first_ko = min(datetime.fromisoformat(m["scheduled_at"].replace("Z", "+00:00")) for m in day_matches)
                last_ko = max(datetime.fromisoformat(m["scheduled_at"].replace("Z", "+00:00")) for m in day_matches)
            except Exception:
                continue
            opens_at = first_ko - timedelta(hours=cfg["opens_hours_before"])
            row = {
                "id": new_id(), "game_type": "group", "stage": stage,
                "config_id": cfg["id"], "group_letter": letter, "matchday": idx,
                "card_limit_current": cfg["card_limit_current"],
                "points_multiplier": cfg["points_multiplier"],
                "opens_at": opens_at.isoformat(), "closes_at": last_ko.isoformat(),
                "status": "upcoming", "total_entries": 0,
                "eligible_team_ids": tids,
                "created_at": now.isoformat(),
            }
            await db.wc_games.insert_one(row)
            created += 1

    # ---- Round games: 8 tournament-wide round games anchored from actual fixture dates ----
    all_team_ids: list[str] = []
    seen_t = set()
    for m in sorted_wc:
        for tid in (m.get("home_team_id"), m.get("away_team_id")):
            if tid and tid not in seen_t:
                seen_t.add(tid)
                all_team_ids.append(tid)
    # Stage → (open_anchor, close_anchor) — open at the FIRST match of the
    # stage chunk; close at the LAST match (game stays selectable for the
    # whole round, per-team locks handle individual matchups).
    stage_anchors: dict[str, tuple[str, str]] = {}
    if sorted_wc:
        try:
            def _slice_anchor(lo: int, hi: int) -> tuple[str, str] | None:
                chunk = sorted_wc[lo:hi]
                if not chunk:
                    return None
                return chunk[0]["scheduled_at"], chunk[-1]["scheduled_at"]
            for stage_key, lo, hi in [
                ("group_md1", 0, 24), ("group_md2", 24, 48), ("group_md3", 48, 72),
                ("r32", 72, 88), ("r16", 88, 96), ("qf", 96, 100),
                ("sf", 100, 102), ("finals", 102, 104),
            ]:
                pair = _slice_anchor(lo, hi)
                if pair:
                    stage_anchors[stage_key] = pair
        except Exception:
            pass
    for stage, (open_iso, close_iso) in stage_anchors.items():
        cfg = cfg_by.get(("round", stage))
        if not cfg:
            continue
        existing = await db.wc_games.find_one({"game_type": "round", "stage": stage})
        if existing:
            continue
        try:
            open_dt = datetime.fromisoformat(open_iso.replace("Z", "+00:00"))
            close_dt = datetime.fromisoformat(close_iso.replace("Z", "+00:00"))
        except Exception:
            continue
        opens_at = open_dt - timedelta(hours=cfg["opens_hours_before"])
        row = {
            "id": new_id(), "game_type": "round", "stage": stage,
            "config_id": cfg["id"], "round_label": stage,
            "card_limit_current": cfg["card_limit_current"],
            "points_multiplier": cfg["points_multiplier"],
            "opens_at": opens_at.isoformat(), "closes_at": close_dt.isoformat(),
            "status": "upcoming", "total_entries": 0,
            "eligible_team_ids": all_team_ids,
            "created_at": now.isoformat(),
        }
        await db.wc_games.insert_one(row)
        created += 1

    if created:
        log.info(f"wc-games generator: created {created} new game rows")
    return created


async def tick_wc_game_states() -> int:
    """State machine: upcoming→open when opens_at arrives; open→closed when
    closes_at hits. ALSO enforces the integrity rule for multi-match games
    (round, group, matchday): the game MUST be closed at the earliest 30
    minutes BEFORE the first kickoff in the round — otherwise late entrants
    could pick a team that already played and copy its known result.
    Returns the number of state transitions."""
    db = get_db()
    now_iso = utcnow_iso()
    transitions = 0
    r1 = await db.wc_games.update_many(
        {"status": "upcoming", "opens_at": {"$lte": now_iso}, "closes_at": {"$gt": now_iso}},
        {"$set": {"status": "open"}},
    )
    transitions += r1.modified_count or 0
    r2 = await db.wc_games.update_many(
        {"status": {"$in": ["upcoming", "open"]}, "closes_at": {"$lte": now_iso}},
        {"$set": {"status": "closed"}},
    )
    transitions += r2.modified_count or 0

    # ---- Integrity sweep: force-close multi-match games once the LAST
    # contributing match in the round is within 30 min of kickoff. Up to
    # that point the game remains open — per-team locking (see wc_games
    # route) takes care of dropping individual teams whose own match has
    # started or is within 30 min.
    from datetime import datetime, timedelta, timezone
    now_dt = datetime.now(timezone.utc)
    # Pre-cache chronological WC matches once per tick for round-game slicing.
    all_wc = await db.matches.find(
        {"is_world_cup": True}, {"_id": 0, "scheduled_at": 1},
    ).sort("scheduled_at", 1).to_list(length=300)
    ROUND_SLICES = {
        "group_md1": (0, 24), "group_md2": (24, 48), "group_md3": (48, 72),
        "r32": (72, 88), "r16": (88, 96), "qf": (96, 100),
        "sf": (100, 102), "finals": (102, 104),
    }
    open_multi = await db.wc_games.find(
        {"status": {"$in": ["upcoming", "open"]},
         "game_type": {"$in": ["round", "group", "matchday"]}},
        {"_id": 0, "id": 1, "game_type": 1, "eligible_team_ids": 1,
         "closes_at": 1, "matchday": 1, "stage": 1},
    ).to_list(length=500)
    for g in open_multi:
        team_ids = list(g.get("eligible_team_ids") or [])
        last_iso: Optional[str] = None
        if g["game_type"] == "group" and g.get("matchday") and team_ids:
            ms = await db.matches.find(
                {"is_world_cup": True,
                 "home_team_id": {"$in": team_ids},
                 "away_team_id": {"$in": team_ids}},
                {"_id": 0, "scheduled_at": 1},
            ).sort("scheduled_at", 1).to_list(length=20)
            md = int(g["matchday"])
            lo, hi = (md - 1) * 2, md * 2
            chunk = ms[lo:hi]
            if chunk:
                last_iso = chunk[-1]["scheduled_at"]
        elif g["game_type"] == "round" and g.get("stage") in ROUND_SLICES:
            lo, hi = ROUND_SLICES[g["stage"]]
            chunk = all_wc[lo:hi]
            if chunk:
                last_iso = chunk[-1]["scheduled_at"]
        elif g["game_type"] == "matchday" and team_ids:
            last = await db.matches.find(
                {"is_world_cup": True,
                 "home_team_id": {"$in": team_ids},
                 "away_team_id": {"$in": team_ids}},
                {"_id": 0, "scheduled_at": 1},
            ).sort("scheduled_at", -1).limit(1).to_list(length=1)
            if last:
                last_iso = last[0]["scheduled_at"]
        if not last_iso:
            continue
        try:
            last_ko = datetime.fromisoformat(last_iso.replace("Z", "+00:00"))
            if last_ko.tzinfo is None:
                last_ko = last_ko.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        deadline = last_ko - timedelta(minutes=30)
        if now_dt >= deadline:
            res = await db.wc_games.update_one(
                {"id": g["id"], "status": {"$in": ["upcoming", "open"]}},
                {"$set": {"status": "closed",
                          "closes_at": deadline.isoformat(),
                          "auto_closed_reason": "last_match_within_30min"}},
            )
            transitions += res.modified_count or 0
    return transitions


from typing import Optional  # late import for inline annotation above


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
        # WC2026 official squads → fantasy player pool
        try:
            await sync_wc2026_squads()
        except Exception as e:
            log.warning(f"wc2026 squads: {e}")
        # Standings + top scorers for major leagues
        try:
            await sync_sportmonks_standings_all()
        except Exception as e:
            log.warning(f"standings all: {e}")
        try:
            await sync_sportmonks_scorers_all()
        except Exception as e:
            log.warning(f"scorers all: {e}")
        for sport in ("football", "basketball", "nba", "baseball", "hockey", "rugby", "handball", "volleyball", "mma", "afl"):
            try:
                if sport in await _enabled_sports():
                    await sync_apisports_today(sport, days_back=1, days_ahead=3)
            except Exception as e:
                log.warning(f"initial as {sport}: {e}")
        try:
            if "tennis" in await _enabled_sports():
                await sync_statpal_tennis()
        except Exception as e:
            log.warning(f"initial statpal tennis: {e}")
        try:
            if "cricket" in await _enabled_sports():
                await sync_statpal_cricket()
        except Exception as e:
            log.warning(f"initial statpal cricket: {e}")
        # WC2026 fixture polling — pull league 732 schedules (qualifiers + finals)
        try:
            await sync_sportmonks_league_schedule(732)
        except Exception as e:
            log.warning(f"wc2026 league 732: {e}")

    async def wc2026_poller():
        """Hourly poll of WC2026 fixtures + schedule so /predictions/upcoming stays current."""
        while True:
            await asyncio.sleep(3600)
            try:
                await sync_sportmonks_league_schedule(732)
            except Exception as e:
                log.warning(f"wc2026 hourly: {e}")

    async def wc_games_generator_loop():
        """Daily auto-generator for WC fantasy games (match/group/round)."""
        # Run once shortly after boot, then every 24h
        await asyncio.sleep(120)
        while True:
            try:
                await generate_wc_games()
            except Exception as e:
                log.warning(f"wc-games generator: {e}")
            await asyncio.sleep(24 * 3600)

    async def wc_games_state_loop():
        """State-machine tick: upcoming→open→closed every 5 minutes."""
        await asyncio.sleep(180)
        while True:
            try:
                await tick_wc_game_states()
            except Exception as e:
                log.warning(f"wc-games state tick: {e}")
            await asyncio.sleep(300)

    async def wc_games_settler_loop():
        """Auto-settle closed WC mini-games whose dependent matches are all FT.
        Runs every 5 minutes after a short boot delay so user entries get
        their points + the leaderboards refresh without admin intervention.
        Also settles all pending non-WC predictions for finished matches so
        the predictions leaderboard updates in lockstep.

        🛑 Honours admin kill-switches: when fantasy/predictions are disabled
        the corresponding settlement block is skipped so points freeze.
        """
        from wc_settler import settle_due_wc_games
        from fantasy_scoring import compute_player_points  # noqa: F401
        from routes.service_controls import is_enabled
        await asyncio.sleep(240)
        while True:
            fantasy_on = await is_enabled("fantasy")
            predictions_on = await is_enabled("predictions")
            if fantasy_on:
                try:
                    res = await settle_due_wc_games(limit=50)
                    if res.get("settled"):
                        log.info(f"wc-games settler: settled {len(res['settled'])} games")
                except Exception as e:
                    log.warning(f"wc-games settler: {e}")
            else:
                log.info("wc-games settler: SKIPPED (fantasy paused)")
            if predictions_on:
                try:
                    # Score any pending predictions whose match is now FT/AET/PEN.
                    # 🐛 Inverted (2026-02-12): query starts from UNSETTLED preds,
                    # not all FT matches — the latter exceeded our 5000-row page
                    # cap (5000+ FT matches across all sports) and WC matches were
                    # silently dropped from the loop.
                    from scoring import score_prediction
                    from db import utcnow_iso as _now
                    db = get_db()
                    pending = await db.predictions.find(
                        {"settled_at": None}, {"_id": 0},
                    ).to_list(length=20000)
                    p_count = 0
                    if pending:
                        match_ids = list({p["match_id"] for p in pending})
                        finished_matches = await db.matches.find(
                            {"id": {"$in": match_ids}, "status": {"$in": ["FT", "AET", "PEN"]}},
                            {"_id": 0},
                        ).to_list(length=len(match_ids))
                        by_id = {m["id"]: m for m in finished_matches}
                        for p in pending:
                            m = by_id.get(p["match_id"])
                            if not m:
                                continue
                            # 🐛 Fix 2026-02-15: use consecutive-from-most-recent
                            # streak (matches admin /settle behavior). The old
                            # `count_documents({outcome_correct: True})` counted
                            # ALL ever-correct preds — so anyone with 10+ correct
                            # preds in their history got +100 bonus on every new
                            # correct prediction forever. Now we walk back from
                            # the latest settled prediction and stop at the first
                            # non-outcome-correct.
                            from routes.predictions import _outcome_streak
                            scount = await _outcome_streak(db, p["user_id"])
                            result = score_prediction(
                                predicted={
                                    "home_score_predicted": p["home_score_predicted"],
                                    "away_score_predicted": p["away_score_predicted"],
                                },
                                match=m,
                                streak_count=scount + 1,
                                applied_cards=[],
                            )
                            await db.predictions.update_one(
                                {"id": p["id"]},
                                {"$set": {
                                    "points_awarded": result["points_awarded"],
                                    "base_points": result["base_points"],
                                    "stage": result["stage"],
                                    "stage_multiplier": result["stage_multiplier"],
                                    "streak_bonus": result["streak_bonus"],
                                    "exact_score_hit": result["exact_score_hit"],
                                    "outcome_correct": result["outcome_correct"],
                                    "diff_correct": result["diff_correct"],
                                    "settled_at": _now(),
                                }},
                            )
                            p_count += 1
                    if p_count:
                        log.info(f"predictions settler: settled {p_count} predictions")
                except Exception as e:
                    log.warning(f"predictions settler: {e}")
            else:
                log.info("predictions settler: SKIPPED (predictions paused)")
            # Re-credit the main fantasy squads from the latest match events.
            # Was previously admin-only via /api/fantasy/settle/gameweek so
            # squad points never grew automatically. Now runs every 5 min.
            if fantasy_on:
                try:
                    from routes.fantasy import settle_gameweek
                    # `settle_gameweek` is the admin endpoint — but it only needs
                    # the `gameweek` param + a user with `is_admin=True`. Cheat
                    # and pass a system-admin shim so the loop can call it.
                    # Each iteration re-scores ALL squads against all FT matches;
                    # idempotent so safe to re-run.
                    result = await settle_gameweek(gameweek=1, user={"id": "system", "is_admin": True})
                    if (result or {}).get("settled"):
                        log.info(f"fantasy settler: re-scored {result['settled']} squads")
                except Exception as e:
                    log.warning(f"fantasy settler: {e}")
            else:
                log.info("fantasy settler: SKIPPED (fantasy paused)")
            await asyncio.sleep(300)

    async def live_poller():
        while True:
            if "football" in await _enabled_sports():
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
            try:
                await sync_sportmonks_standings_all()
            except Exception:
                pass
            try:
                await sync_sportmonks_scorers_all()
            except Exception:
                pass
            for sport in ("football", "basketball", "nba", "baseball", "hockey", "rugby", "handball", "volleyball", "mma", "afl"):
                try:
                    if sport in await _enabled_sports():
                        await sync_apisports_today(sport, days_back=1, days_ahead=3)
                except Exception:
                    pass

    async def statpal_poller():
        while True:
            enabled = await _enabled_sports()
            if "tennis" in enabled:
                try:
                    await sync_statpal_tennis()
                except Exception:
                    pass
            if "cricket" in enabled:
                try:
                    await sync_statpal_cricket()
                except Exception:
                    pass
            if "football" in enabled:
                try:
                    await sync_statpal_football()
                except Exception:
                    pass
            await asyncio.sleep(120)

    asyncio.create_task(initial_sync())
    asyncio.create_task(live_poller())
    asyncio.create_task(apisports_live_poller())
    asyncio.create_task(fixture_daily())
    asyncio.create_task(statpal_poller())
    asyncio.create_task(wc2026_poller())
    asyncio.create_task(wc_games_generator_loop())
    asyncio.create_task(wc_games_state_loop())
    asyncio.create_task(wc_games_settler_loop())
