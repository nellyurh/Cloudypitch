"""API-Sports adapter — basketball, NBA, baseball/MLB, NHL/hockey, rugby, handball, volleyball, MMA, F1, AFL."""
import os
import httpx
from typing import Any

# API-Sports hosts (per sport)
HOSTS = {
    "basketball": "https://v1.basketball.api-sports.io",
    "nba": "https://v2.nba.api-sports.io",
    "baseball": "https://v1.baseball.api-sports.io",
    "hockey": "https://v1.hockey.api-sports.io",
    "rugby": "https://v1.rugby.api-sports.io",
    "handball": "https://v1.handball.api-sports.io",
    "volleyball": "https://v1.volleyball.api-sports.io",
    "mma": "https://v1.mma.api-sports.io",
    "f1": "https://v1.formula-1.api-sports.io",
    "afl": "https://v1.afl.api-sports.io",
    "football": "https://v3.football.api-sports.io",
}


def _key():
    return os.environ.get("APISPORTS_API_KEY", "")


async def _get(sport: str, path: str, params: dict | None = None) -> Any:
    host = HOSTS.get(sport)
    if not host:
        return {"error": "unknown_sport"}
    headers = {"x-apisports-key": _key()}
    async with httpx.AsyncClient(timeout=20.0) as c:
        r = await c.get(f"{host}{path}", headers=headers, params=params or {})
        if r.status_code >= 400:
            return {"error": r.status_code, "body": r.text[:300]}
        return r.json()


async def fetch_games(sport: str, date: str | None = None, live: bool = False):
    # API-Sports football endpoint is /fixtures, not /games
    if sport == "football":
        path = "/fixtures"
    else:
        path = "/games"
    if live:
        return await _get(sport, path, {"live": "all"})
    params = {"date": date} if date else {}
    return await _get(sport, path, params)


async def fetch_standings(sport: str, league: int, season: int):
    return await _get(sport, "/standings", {"league": league, "season": season})


async def fetch_leagues(sport: str):
    return await _get(sport, "/leagues")


async def fetch_game(sport: str, game_id: int):
    return await _get(sport, "/games", {"id": game_id})
