"""Regression test: Group MD games must expose players from ALL teams in the
group, even when FIFA / Sportmonks naming drifts (e.g. "Czechia" vs
"Czech Republic", "South Korea" vs "Korea Republic"). Bug: /fantasy/players
filtered on country name, so 2 of the 4 teams' squads were missing.

The fix: prefer `eligible_team_ids` (exact IDs) over country-string match.
"""
import asyncio, os, sys, pathlib
import pytest

# Allow `import db, routes.fantasy` when run from repo root or /app/backend
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from routes.fantasy import list_fantasy_players  # noqa: E402


@pytest.mark.asyncio
async def test_group_md1_returns_all_four_teams():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    # Patch get_db for the route
    import db as db_mod
    db_mod._client = cli  # type: ignore
    db_mod._db = db        # type: ignore

    g = await db.wc_games.find_one({"game_type": "group", "group_letter": "A", "matchday": 1})
    assert g, "Group A MD1 fixture missing — run generate_wc_games() first"
    assert len(g.get("eligible_team_ids") or []) == 4

    res = await list_fantasy_players(limit=2000, game_id=g["id"])
    players = res["players"]
    teams = set(p.get("team_name") for p in players)
    # All 4 group teams should be represented
    assert len(teams) == 4, f"Expected 4 teams, got {len(teams)}: {teams}"
    assert len(players) > 80, f"Expected ~110+ players, got {len(players)}"


if __name__ == "__main__":
    asyncio.run(test_group_md1_returns_all_four_teams())
    print("OK")
