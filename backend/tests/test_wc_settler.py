"""WC mini-game settler — end-to-end integration test.

Seeds a synthetic match + players + lineups + events into MongoDB, creates a
`wc_games` row of game_type=match with status=closed, inserts a single
wc_game_entries doc for a test user, runs `settle_wc_game`, and asserts:

  - points_scored is set (>0 because the player scored)
  - rank_in_game is 1 (single entry)
  - game.status flipped to 'settled'
  - leaderboard aggregation reflects the points

All seeded ids are uuid-prefixed `it_settler_*` so the suite can be re-run
cleanly without colliding with production data.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

# Allow running this file directly: python tests/test_wc_settler.py
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(HERE)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Load .env so MONGO_URL/DB_NAME are populated when running outside supervisor.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(os.path.join(BACKEND_DIR, ".env"))
except Exception:
    pass

from db import init_db, get_db, utcnow_iso  # noqa: E402
from wc_settler import settle_wc_game  # noqa: E402

PREFIX = "it_settler_"


def _new_id(suffix: str) -> str:
    return f"{PREFIX}{suffix}_{uuid.uuid4().hex[:8]}"


async def _seed(db):
    """Insert one match (FT, 2-0), one player who scored, one user, one game,
    one entry. Returns the ids dict for later cleanup."""
    match_id = _new_id("match")
    home_team_id = _new_id("home")
    away_team_id = _new_id("away")
    player_id = _new_id("player")
    user_id = _new_id("user")
    game_id = _new_id("game")
    entry_id = _new_id("entry")

    await db.matches.insert_one({
        "id": match_id, "sport_slug": "football", "is_world_cup": True,
        "home_team_id": home_team_id, "away_team_id": away_team_id,
        "home_team_name": "Test Home", "away_team_name": "Test Away",
        "home_score": 2, "away_score": 0, "status": "FT",
        "scheduled_at": "2026-06-15T18:00:00+00:00",
    })

    await db.players.insert_one({
        "id": player_id, "name": "Test Striker", "team_id": home_team_id,
        "team_name": "Test Home", "position": "FWD",
        "country": "Testland", "is_wc_2026": True,
    })

    # Two goals + minutes via lineup row (starter → 90min)
    await db.match_events.insert_many([
        {"id": _new_id("ev1"), "match_id": match_id, "team_id": home_team_id,
         "player_name": "Test Striker", "type": "Goal", "minute": 23},
        {"id": _new_id("ev2"), "match_id": match_id, "team_id": home_team_id,
         "player_name": "Test Striker", "type": "Goal", "minute": 67},
    ])
    await db.match_lineups.insert_one({
        "id": _new_id("ln"), "match_id": match_id, "team_id": home_team_id,
        "starter": True, "player_name": "Test Striker", "player_pos": "FWD",
    })

    await db.users.insert_one({
        "id": user_id, "email": f"{user_id}@test.example",
        "display_name": "Settler Test", "country_code": "NG",
    })

    await db.wc_games.insert_one({
        "id": game_id, "game_type": "match", "stage": "any",
        "match_id": match_id,
        "card_limit_current": 2, "points_multiplier": 1.0,
        "opens_at": "2026-06-15T12:00:00+00:00",
        "closes_at": "2026-06-15T18:00:00+00:00",
        "status": "closed", "total_entries": 1,
        "eligible_team_ids": [home_team_id, away_team_id],
        "created_at": utcnow_iso(),
    })

    await db.wc_game_entries.insert_one({
        "id": entry_id, "user_id": user_id, "wc_game_id": game_id,
        "player_picks": [{"player_id": player_id, "team_id": home_team_id, "position": "FWD"}],
        "captain_player_id": player_id, "vice_captain_player_id": None,
        "cards_used": [],
        "points_scored": None, "rank_in_game": None, "settled_at": None,
        "created_at": utcnow_iso(), "updated_at": utcnow_iso(),
    })

    return {
        "match_id": match_id, "home_team_id": home_team_id,
        "away_team_id": away_team_id, "player_id": player_id,
        "user_id": user_id, "game_id": game_id, "entry_id": entry_id,
    }


async def _cleanup(db, ids):
    await db.matches.delete_one({"id": ids["match_id"]})
    await db.match_events.delete_many({"match_id": ids["match_id"]})
    await db.match_lineups.delete_many({"match_id": ids["match_id"]})
    await db.players.delete_one({"id": ids["player_id"]})
    await db.users.delete_one({"id": ids["user_id"]})
    await db.wc_games.delete_one({"id": ids["game_id"]})
    await db.wc_game_entries.delete_one({"id": ids["entry_id"]})


async def main() -> int:
    init_db()
    db = get_db()
    ids = await _seed(db)
    try:
        # 1) Run settler
        res = await settle_wc_game(ids["game_id"])
        assert res.get("ok"), f"settler did not run: {res}"
        assert res["entries_settled"] == 1, f"unexpected entries_settled: {res}"

        # 2) Re-read entry → must have points and rank
        entry = await db.wc_game_entries.find_one({"id": ids["entry_id"]}, {"_id": 0})
        assert entry["settled_at"], "entry missing settled_at"
        assert entry["rank_in_game"] == 1, f"expected rank 1, got {entry.get('rank_in_game')}"
        assert entry["points_scored"] is not None and entry["points_scored"] > 0, \
            f"expected >0 points, got {entry.get('points_scored')}"
        # FWD scores 4pts/goal × 2 goals = 8 + 2 mins (60+) = 10 base, captain ×2 = 20
        assert entry["points_scored"] >= 18, \
            f"FWD-captain with 2 goals should score >=18 pts, got {entry['points_scored']}"
        bd = entry.get("breakdown_by_player") or []
        assert bd and bd[0]["player_id"] == ids["player_id"], "breakdown missing/mismatch"
        assert bd[0]["captain"] is True
        assert bd[0]["multiplier"] == 2

        # 3) Game row flipped to settled
        g = await db.wc_games.find_one({"id": ids["game_id"]}, {"_id": 0})
        assert g["status"] == "settled", f"game status not settled: {g.get('status')}"

        # 4) Leaderboard aggregation reflects the score (filter on this user only)
        pipeline = [
            {"$match": {"user_id": ids["user_id"], "settled_at": {"$ne": None}}},
            {"$group": {"_id": "$user_id", "total": {"$sum": "$points_scored"}}},
        ]
        agg = await db.wc_game_entries.aggregate(pipeline).to_list(length=10)
        assert agg and agg[0]["total"] == entry["points_scored"], \
            f"leaderboard aggregation mismatch: {agg}"

        # 5) Idempotency — re-running should skip the already-settled entry
        res2 = await settle_wc_game(ids["game_id"])
        # already_settled is the expected reason for a fully-settled game
        assert res2.get("reason") == "already_settled" or res2.get("entries_settled") == 0

        # 6) Force re-settle works
        res3 = await settle_wc_game(ids["game_id"], force=True)
        assert res3.get("ok"), f"force settle failed: {res3}"
        assert res3["entries_settled"] == 1

        print("PASS  wc_settler — points scored:", entry["points_scored"],
              "| rank:", entry["rank_in_game"])
        return 0
    except AssertionError as e:
        print("FAIL  wc_settler:", e)
        return 1
    finally:
        await _cleanup(db, ids)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
