"""Per-team 30-min lock cutoff. A team becomes ineligible 30 min BEFORE its
match kickoff (not when it kicks off). The group/round game itself stays open
for other teams' players until the LAST match in the round is 30 min away.
"""
import asyncio, os, sys, pathlib
from datetime import datetime, timedelta, timezone
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import db as db_mod  # noqa: E402
from routes.wc_games import game_detail  # noqa: E402


GAME_ID = "test-30min-cutoff-001"
TEAMS = ["test-team-W", "test-team-X", "test-team-Y", "test-team-Z"]


async def _setup():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    db_mod._client = cli  # type: ignore
    db_mod._db = db        # type: ignore

    now = datetime.now(timezone.utc)
    await db.wc_games.delete_many({"id": GAME_ID})
    await db.matches.delete_many({"id": {"$regex": "^test-30min-m-"}})
    await db.players.delete_many({"id": {"$regex": "^test-30min-p-"}})
    for t in TEAMS:
        for i in range(3):
            await db.players.insert_one({
                "id": f"test-30min-p-{t}-{i}", "name": f"{t} player {i}",
                "team_id": t, "team_name": t.upper(),
                "country": t.upper(), "position": "MID", "price": 5.0,
                "is_wc_2026": True,
            })
    # Match 1: KO in 20 min (< 30 → MUST be locked).
    # Match 2: KO in 90 min (> 30 → still open).
    await db.matches.insert_one({
        "id": "test-30min-m-1", "is_world_cup": True,
        "scheduled_at": (now + timedelta(minutes=20)).isoformat(),
        "home_team_id": TEAMS[0], "away_team_id": TEAMS[1],
        "home_team_name": "W", "away_team_name": "X",
        "status": "upcoming",
    })
    await db.matches.insert_one({
        "id": "test-30min-m-2", "is_world_cup": True,
        "scheduled_at": (now + timedelta(minutes=90)).isoformat(),
        "home_team_id": TEAMS[2], "away_team_id": TEAMS[3],
        "home_team_name": "Y", "away_team_name": "Z",
        "status": "upcoming",
    })
    await db.wc_games.insert_one({
        "id": GAME_ID, "game_type": "group", "stage": "group_md1",
        "group_letter": "Z", "matchday": 1,
        "card_limit_current": 4, "points_multiplier": 1.0,
        "opens_at": (now - timedelta(days=2)).isoformat(),
        "closes_at": (now + timedelta(minutes=90)).isoformat(),
        "status": "open", "total_entries": 0,
        "eligible_team_ids": TEAMS,
        "created_at": now.isoformat(),
    })
    return db


async def _teardown(db):
    await db.wc_games.delete_many({"id": GAME_ID})
    await db.matches.delete_many({"id": {"$regex": "^test-30min-m-"}})
    await db.players.delete_many({"id": {"$regex": "^test-30min-p-"}})


@pytest.mark.asyncio
async def test_team_locked_within_30min_of_ko():
    db = await _setup()
    try:
        res = await game_detail(GAME_ID, user=None)
        locked = set(res["game"]["locked_team_ids"])
        # W and X (KO in 20 min) → LOCKED
        assert TEAMS[0] in locked and TEAMS[1] in locked, locked
        # Y and Z (KO in 90 min) → still open
        assert TEAMS[2] not in locked and TEAMS[3] not in locked
        pool_teams = {p["team_id"] for p in res["game"]["eligible_players"]}
        assert pool_teams == {TEAMS[2], TEAMS[3]}, pool_teams
    finally:
        await _teardown(db)


if __name__ == "__main__":
    asyncio.run(test_team_locked_within_30min_of_ko())
    print("test_team_locked_within_30min_of_ko: OK")
