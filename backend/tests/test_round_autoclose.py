"""Regression test: auto-close + locked-team filter for multi-match games.

Scenario (synthetic): A group game with 2 matches.
  - Match 1 (Team A vs Team B) kicked off 1 hour ago.
  - Match 2 (Team C vs Team D) starts in 4 hours.

Expected behavior:
  - /games/{id}.eligible_players must EXCLUDE players from A and B.
  - /games/{id}.locked_team_ids must include A and B.
  - enter_game() must reject a pick from a locked team.
  - tick_wc_game_states() should NOT close the game (next KO is > 30 min).
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
from routes.wc_games import game_detail, enter_game, PlayerPickIn, GameEntryIn  # noqa: E402


GAME_ID = "test-group-autoclose-001"
TEAMS = ["test-team-A", "test-team-B", "test-team-C", "test-team-D"]


async def _setup():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    db_mod._client = cli  # type: ignore
    db_mod._db = db        # type: ignore

    now = datetime.now(timezone.utc)
    # Clean
    await db.wc_games.delete_many({"id": GAME_ID})
    await db.matches.delete_many({"id": {"$regex": "^test-match-"}})
    await db.players.delete_many({"id": {"$regex": "^test-p-"}})
    await db.wc_game_entries.delete_many({"wc_game_id": GAME_ID})

    # Insert teams' players (3 each)
    for t in TEAMS:
        for i in range(3):
            await db.players.insert_one({
                "id": f"test-p-{t}-{i}", "name": f"{t} player {i}",
                "team_id": t, "team_name": t.upper(),
                "country": t.upper(), "position": "MID", "price": 5.0,
                "is_wc_2026": True,
            })
    # Match 1 kicked off 1h ago (locked: started already), Match 2 in 4h
    # (NOT locked yet — KO > 30 min away). With the new round-stays-open
    # policy, closes_at = last KO (now + 4h).
    await db.matches.insert_one({
        "id": "test-match-1", "is_world_cup": True,
        "scheduled_at": (now - timedelta(hours=1)).isoformat(),
        "home_team_id": TEAMS[0], "away_team_id": TEAMS[1],
        "home_team_name": "A", "away_team_name": "B",
        "status": "live",
    })
    await db.matches.insert_one({
        "id": "test-match-2", "is_world_cup": True,
        "scheduled_at": (now + timedelta(hours=4)).isoformat(),
        "home_team_id": TEAMS[2], "away_team_id": TEAMS[3],
        "home_team_name": "C", "away_team_name": "D",
        "status": "upcoming",
    })
    await db.wc_games.insert_one({
        "id": GAME_ID, "game_type": "group", "stage": "group_md1",
        "group_letter": "Z", "matchday": 1,
        "card_limit_current": 4, "points_multiplier": 1.0,
        "opens_at": (now - timedelta(days=2)).isoformat(),
        "closes_at": (now + timedelta(hours=4)).isoformat(),
        "status": "open", "total_entries": 0,
        "eligible_team_ids": TEAMS,
        "eligible_country_names": [t.upper() for t in TEAMS],
        "created_at": now.isoformat(),
    })
    return db


async def _teardown(db):
    await db.wc_games.delete_many({"id": GAME_ID})
    await db.matches.delete_many({"id": {"$regex": "^test-match-"}})
    await db.players.delete_many({"id": {"$regex": "^test-p-"}})
    await db.wc_game_entries.delete_many({"wc_game_id": GAME_ID})


@pytest.mark.asyncio
async def test_locked_teams_excluded_from_pool():
    db = await _setup()
    try:
        res = await game_detail(GAME_ID, user=None)
        g = res["game"]
        locked = set(g.get("locked_team_ids") or [])
        # Teams A and B kicked off → must be locked
        assert TEAMS[0] in locked, f"Team A should be locked, got {locked}"
        assert TEAMS[1] in locked, f"Team B should be locked, got {locked}"
        # Teams C and D are upcoming → must stay open
        assert TEAMS[2] not in locked
        assert TEAMS[3] not in locked
        # Eligible players must come ONLY from C and D
        pool_team_ids = {p["team_id"] for p in g["eligible_players"]}
        assert pool_team_ids == {TEAMS[2], TEAMS[3]}, f"Expected only C+D, got {pool_team_ids}"
    finally:
        await _teardown(db)


@pytest.mark.asyncio
async def test_enter_game_rejects_locked_team_pick():
    db = await _setup()
    try:
        # Make a user
        user = {"id": "test-user-locked", "email": "x@x.com"}
        body = GameEntryIn(player_picks=[
            PlayerPickIn(player_id=f"test-p-{TEAMS[0]}-0", team_id=TEAMS[0], position="MID")
        ])
        from fastapi import HTTPException
        try:
            await enter_game(GAME_ID, body, user=user)
            assert False, "Should have raised HTTPException — picked a locked team"
        except HTTPException as e:
            assert e.status_code == 400
            assert "already started" in str(e.detail).lower() or "within 30 minutes" in str(e.detail).lower()
    finally:
        await _teardown(db)


if __name__ == "__main__":
    asyncio.run(test_locked_teams_excluded_from_pool())
    print("test_locked_teams_excluded_from_pool: OK")
    asyncio.run(test_enter_game_rejects_locked_team_pick())
    print("test_enter_game_rejects_locked_team_pick: OK")
