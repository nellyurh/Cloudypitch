"""StatPal adapter — tennis, cricket, golf, esports, horse racing."""
import os
import httpx
from typing import Any

BASE = "https://statpal.io/api/v1"


def _key():
    return os.environ.get("STATPAL_API_KEY", "")


async def _get(path: str, params: dict | None = None) -> Any:
    p = {"access_key": _key()}
    if params:
        p.update(params)
    async with httpx.AsyncClient(timeout=20.0) as c:
        r = await c.get(f"{BASE}{path}", params=p)
        if r.status_code >= 400:
            return {"error": r.status_code, "body": r.text[:300]}
        try:
            return r.json()
        except Exception:
            return {"error": "invalid_json", "body": r.text[:300]}


async def fetch_tennis_livescores():
    return await _get("/tennis/livescores")


async def fetch_tennis_tournaments():
    return await _get("/tennis/tournaments")


async def fetch_cricket_livescores():
    return await _get("/cricket/livescores")


async def fetch_cricket_upcoming():
    return await _get("/cricket/upcoming")


async def fetch_golf_tournaments():
    return await _get("/golf/tournaments")


async def fetch_horse_racing():
    return await _get("/horse-racing/racecards")
