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
        {"include": "participants;scores;state;events.type;statistics.type;periods;league.country"},
    )


async def fetch_all_leagues(page: int = 1):
    return await _get("/leagues", {"include": "country", "per_page": 50, "page": page})


async def fetch_standings_by_season(season_id: int):
    """Fetch league standings for a given season — includes participant, details, rule."""
    return await _get(
        f"/standings/seasons/{season_id}",
        {"include": "participant;details.type;form;rule"},
    )


async def fetch_topscorers_by_season(season_id: int):
    """Fetch top goal scorers + assists for a season."""
    return await _get(
        f"/topscorers/seasons/{season_id}",
        {"include": "player;participant;type"},
    )


async def fetch_fixtures_by_league(league_id: int, page: int = 1, per_page: int = 100):
    """Fetch all fixtures for a league (qualifiers + finals)."""
    return await _get(
        f"/fixtures",
        {
            "filters": f"fixtureLeagues:{league_id}",
            "include": "participants;scores;state;league;round;stage;venue",
            "per_page": per_page, "page": page,
        },
    )


async def fetch_fixtures_by_season(season_id: int):
    """Fetch all fixtures for a single season (e.g. WC 2026 = 26618).
    Uses /seasons/{id}?include=fixtures which returns ALL fixtures for that season."""
    return await _get(
        f"/seasons/{season_id}",
        {"include": "fixtures.participants;fixtures.scores;fixtures.state;fixtures.round;fixtures.stage;fixtures.venue"},
    )


async def fetch_today_livescores():
    return await _get(
        "/livescores",
        {"include": "participants;scores;state;league"},
    )


async def fetch_fixture(fixture_id: int):
    return await _get(
        f"/fixtures/{fixture_id}",
        {"include": "participants;scores;state;events.type;statistics.type;periods;lineups.player;lineups.type;lineups.position;venue;league;referees"},
    )


async def fetch_standings(league_id: int, season_id: int | None = None):
    inc = "participant;details.type;form;rule"
    if season_id:
        return await _get(f"/standings/seasons/{season_id}", {"include": inc})
    return await _get(f"/standings/live/leagues/{league_id}", {"include": inc})


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


# Sportmonks v3 event type ID → human-readable name (fallback when `events.type` include is missing)
EVENT_TYPE_NAMES = {
    14: "Goal",
    15: "Own Goal",
    16: "Penalty",
    17: "Missed Penalty",
    18: "Substitution",
    19: "Yellow Card",
    20: "Red Card",
    21: "Yellow-Red Card",
    26: "Penalty Shootout Goal",
    27: "Penalty Shootout Miss",
    28: "VAR",
    52: "Goal",
    83: "Var Card",
    1697: "VAR Goal Cancelled",
    10027: "Pen. Shootout Goal",
    10028: "Pen. Shootout Miss",
}

# Sportmonks v3 statistic type ID → human-readable name
STAT_TYPE_NAMES = {
    41: "Shots Total",
    42: "Shots on Target",
    43: "Attacks",
    44: "Dangerous Attacks",
    45: "Ball Possession %",
    46: "Ball Safe",
    47: "Penalties",
    49: "Shots off Target",
    50: "Shots Blocked",
    51: "Offsides",
    52: "Goals",
    53: "Saves",
    54: "Corners",
    55: "Hit Woodwork",
    56: "Fouls",
    57: "Tackles",
    58: "Passes Total",
    59: "Successful Passes",
    60: "Passes %",
    61: "Free Kicks",
    62: "Goal Kicks",
    63: "Throw Ins",
    64: "Successful Headers",
    65: "Yellow Cards",
    66: "Substitutions",
    78: "Counter Attacks",
    79: "Long Balls",
    80: "Cross Total",
    82: "Successful Crosses",
    84: "Successful Long Balls",
    86: "Shots Inside Box",
    87: "Shots Outside Box",
    88: "Successful Dribbles",
    96: "Goal Attempts",
    99: "Tackles Successful",
    105: "Total Crosses",
    106: "Long Pass Accuracy %",
    108: "Key Passes",
    109: "Errors Leading to Goal",
    110: "Big Chances Created",
    117: "Yellow Cards",
    118: "Red Cards",
    119: "Injuries",
    194: "Expected Goals (xG)",
    214: "Total Headed Goals",
}
