"""Sportmonks v3 Football adapter."""
import os
import httpx
from typing import Any

BASE = "https://api.sportmonks.com/v3/football"


def _token():
    return os.environ.get("SPORTMONKS_API_TOKEN", "")


async def _get(path: str, params: dict | None = None) -> Any:
    p = {"api_token": _token()}
    if params:
        p.update(params)
    async with httpx.AsyncClient(timeout=20.0) as c:
        r = await c.get(f"{BASE}{path}", params=p)
        if r.status_code >= 400:
            return {"error": r.status_code, "body": r.text[:300]}
        return r.json()


async def fetch_fixtures_by_date(date_str: str, page: int = 1):
    """date_str: YYYY-MM-DD"""
    return await _get(
        f"/fixtures/date/{date_str}",
        {"include": "participants;scores;state;league.country;venue;periods;season", "per_page": 50, "page": page},
    )


async def fetch_live():
    return await _get(
        "/livescores/inplay",
        {"include": "participants;scores;state;events;statistics;periods;league.country"},
    )


async def fetch_all_leagues(page: int = 1):
    return await _get("/leagues", {"include": "country", "per_page": 50, "page": page})


async def fetch_today_livescores():
    return await _get(
        "/livescores",
        {"include": "participants;scores;state;league"},
    )


async def fetch_fixture(fixture_id: int):
    return await _get(
        f"/fixtures/{fixture_id}",
        {"include": "participants;scores;state;events;statistics;periods;lineups;venue;league;referees"},
    )


async def fetch_standings(league_id: int, season_id: int | None = None):
    if season_id:
        return await _get(f"/standings/seasons/{season_id}", {"include": "participant;rule"})
    return await _get(f"/standings/live/leagues/{league_id}", {"include": "participant;rule"})


async def fetch_top_scorers(season_id: int):
    return await _get(
        f"/topscorers/seasons/{season_id}",
        {"include": "player;participant;type"},
    )


async def fetch_team_squad(season_id: int, team_id: int):
    return await _get(
        f"/squads/seasons/{season_id}/teams/{team_id}",
        {"include": "player;position"},
    )


async def fetch_teams_for_season(season_id: int):
    return await _get(f"/teams/seasons/{season_id}", {"per_page": 50})


async def fetch_seasons_for_league(league_id: int):
    return await _get("/seasons", {"filters": f"seasonLeagues:{league_id}", "per_page": 50})


async def fetch_league_detail(league_id: int):
    return await _get(f"/leagues/{league_id}", {"include": "currentseason"})


async def fetch_leagues():
    return await _get("/leagues", {"include": "country", "per_page": 50})


# ---------- Mapping helpers ----------
def map_status(state: dict | None) -> tuple[str, str]:
    if not state:
        return ("NS", "Not Started")
    short = state.get("short_name") or state.get("state") or "NS"
    long = state.get("name") or state.get("developer_name") or short
    mapping = {
        "NS": "NS", "INPLAY_1ST_HALF": "1H", "HT": "HT", "INPLAY_2ND_HALF": "2H",
        "INPLAY_ET": "ET", "INPLAY_ET_2ND_HALF": "ET", "BREAK": "BR",
        "FT": "FT", "AET": "AET", "FT_PEN": "PEN", "PEN_LIVE": "PEN_LIVE",
        "POSTP": "POSTP", "CANCL": "CANCL", "ABAN": "ABAN", "AWARDED": "AW",
        "LIVE": "LIVE",
    }
    return (mapping.get(short, short), long)


def extract_scores(scores: list | None) -> dict:
    """Return {home, away, home_ht, away_ht, home_pen, away_pen}."""
    out = {"home": 0, "away": 0, "home_ht": None, "away_ht": None, "home_pen": None, "away_pen": None}
    if not scores:
        return out
    for s in scores:
        desc = (s.get("description") or "").upper()
        score = s.get("score") or {}
        val = score.get("goals", 0)
        part = (score.get("participant") or "").lower()
        if desc in ("CURRENT", "FULL TIME", "FT", "2ND-HALF"):
            if part == "home":
                out["home"] = val
            elif part == "away":
                out["away"] = val
        elif desc in ("1ST-HALF", "HT", "HALF TIME"):
            if part == "home":
                out["home_ht"] = val
            elif part == "away":
                out["away_ht"] = val
        elif desc in ("PENALTIES",):
            if part == "home":
                out["home_pen"] = val
            elif part == "away":
                out["away_pen"] = val
    return out


def extract_minute(periods: list | None) -> int | None:
    if not periods:
        return None
    for p in periods:
        if p.get("ticking"):
            return p.get("minutes")
    return None
