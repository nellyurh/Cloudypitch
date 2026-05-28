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
            evs.append({
                "id": new_id(),
                "match_id": match_doc_id,
                "minute": e.get("minute"),
                "extra_minute": e.get("extra_minute"),
                "team_id": e.get("participant_id"),
                "player_id": e.get("player_id"),
                "player_name": e.get("player_name") or "",
                "assist_player_name": e.get("related_player_name") or "",
                "type": (e.get("type") or {}).get("name") if isinstance(e.get("type"), dict) else (e.get("type_id") or "event"),
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
            key = type_obj.get("developer_name") or type_obj.get("name") or str(s.get("type_id") or "stat")
            val = (s.get("data") or {}).get("value") if isinstance(s.get("data"), dict) else s.get("value")
            by_team.setdefault(tid, {})[key] = val
        for tid, kv in by_team.items():
            await db.match_statistics.insert_one({
                "id": new_id(),
                "match_id": match_doc_id,
                "team_id": tid,
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
            ls.append({
                "id": new_id(),
                "match_id": match_doc_id,
                "team_id": ln.get("team_id") or ln.get("participant_id"),
                "formation": ln.get("formation"),
                "starter": ln.get("type_id") == 11 or ln.get("type") == "lineup",
                "player_name": ln.get("player_name") or "",
                "player_number": ln.get("jersey_number"),
                "player_pos": ((ln.get("position") or {}).get("name") if isinstance(ln.get("position"), dict) else None),
                "grid": ln.get("formation_position") or ln.get("grid"),
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
        "periods": periods,
        "primary_provider": "api-sports", "api_sports_id": gid,
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
    for sport in ("football", "basketball", "nba", "baseball", "hockey", "rugby", "handball", "volleyball", "mma", "afl"):
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


# ---------- Sportmonks: standings, top scorers, WC squads ----------
async def upsert_standing(row: dict, league_doc_id: str):
    """Persist one standings row."""
    db = get_db()
    participant = row.get("participant") or {}
    team_id = await upsert_sportmonks_team(participant, "football") if isinstance(participant, dict) and participant else None
    details = row.get("details") or []
    # details is an array of {type_id, value} — we leave it for raw; canonical fields below
    doc = {
        "id": f"sm-st-{row.get('id')}",
        "league_id": league_doc_id,
        "season_id": row.get("season_id"),
        "team_id": team_id,
        "team_name": participant.get("name") if isinstance(participant, dict) else None,
        "team_logo": participant.get("image_path") if isinstance(participant, dict) else None,
        "rank": row.get("position"),
        "points": row.get("points") or 0,
        "GF": (row.get("scores") or {}).get("goals_scored") if isinstance(row.get("scores"), dict) else None,
        "GA": (row.get("scores") or {}).get("goals_against") if isinstance(row.get("scores"), dict) else None,
        "MP": (row.get("overall") or {}).get("games_played") if isinstance(row.get("overall"), dict) else None,
        "W": (row.get("overall") or {}).get("wins") if isinstance(row.get("overall"), dict) else None,
        "D": (row.get("overall") or {}).get("draws") if isinstance(row.get("overall"), dict) else None,
        "L": (row.get("overall") or {}).get("losses") if isinstance(row.get("overall"), dict) else None,
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
    """Pull standings for all tier-1/2 leagues we know about."""
    db = get_db()
    # Tier 1+2 leagues (tier_score >= 60) plus WC
    leagues = await db.leagues.find(
        {"sport_slug": "football", "primary_provider": "sportmonks", "tier_score": {"$gte": 60}},
        {"_id": 0, "sportmonks_id": 1, "name": 1},
    ).to_list(length=200)
    total = 0
    for lg in leagues:
        if not lg.get("sportmonks_id"):
            continue
        n = await sync_sportmonks_standings_live(lg["sportmonks_id"])
        total += n
    log.info(f"sportmonks standings: {total} rows across {len(leagues)} leagues")
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
            # Synthetic fantasy price by position
            base_price = {"GK": 4.5, "DEF": 5.0, "MID": 7.0, "FWD": 8.5}.get(short_pos, 5.0)
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
                "price": base_price,
                "shirt_number": entry.get("jersey_number"),
                "is_wc_2026": True,
                "updated_at": utcnow_iso(),
            }
            await db.players.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
            total_players += 1
    log.info(f"wc2026 squads: {total_players} players across {len(real_teams)} teams")
    return total_players


# ---------- API-Sports football enrichment (cross-provider dedup) ----------
async def _cross_provider_dedup(sport: str, home_name: str, away_name: str, scheduled_at_iso: str):
    """Check if a match with same teams (fuzzy) within ±24h already exists.
    Returns existing match id or None."""
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
    # Loose case-insensitive prefix match on the first word of each team name
    h_token = (home_name.split()[0] or "")[:6]
    a_token = (away_name.split()[0] or "")[:6]
    if len(h_token) < 3 or len(a_token) < 3:
        return None
    existing = await db.matches.find_one({
        "sport_slug": sport,
        "scheduled_at": {"$gte": lo, "$lt": hi},
        "home_team_name": {"$regex": f"^{h_token}", "$options": "i"},
        "away_team_name": {"$regex": f"^{a_token}", "$options": "i"},
    }, {"id": 1, "primary_provider": 1, "_id": 0})
    return existing


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
            if "finished" in sl or "ended" in sl or "ft" in sl:
                short = "FT"
                is_live = False
            elif sl and ("half" in sl or "min" in sl or sl[0].isdigit()):
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
            await db.matches.update_one({"statpal_id": mid, "sport_slug": "football"}, {"$set": doc}, upsert=True)
            seen += 1
    log.info(f"statpal football: {seen} matches")
    return seen


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
