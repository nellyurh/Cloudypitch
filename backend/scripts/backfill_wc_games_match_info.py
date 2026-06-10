"""Backfill `match_info` on every wc_game with game_type=match.

The match-mode mini-game card needs to surface the home/away team names AND
logos. Existing docs only carry `match_id` referencing the `matches`
collection — this script resolves the join once so the API can serve the
two-team summary cheaply.

Also populates `eligible_country_names` (denormalised team names) so the
fantasy player-pool filter can narrow to those two countries without an extra
DB round-trip.

Usage:
    cd /app/backend && python3 -m scripts.backfill_wc_games_match_info
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import init_db, get_db


async def main() -> None:
    init_db()
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    cur = db.wc_games.find({"game_type": "match"}, {"_id": 0})
    updated = 0
    skipped = 0
    async for g in cur:
        if g.get("match_info") and (g.get("match_info") or {}).get("home_team_name"):
            continue
        if not g.get("match_id"):
            skipped += 1
            continue
        m = await db.matches.find_one(
            {"id": g["match_id"]},
            {"_id": 0,
             "home_team_name": 1, "away_team_name": 1,
             "home_team_logo": 1, "away_team_logo": 1,
             "home_team_id":   1, "away_team_id":   1,
             "scheduled_at":   1, "round":          1},
        )
        if not m or not m.get("home_team_name") or not m.get("away_team_name"):
            skipped += 1
            continue
        match_info = {
            "home_team_name": m["home_team_name"],
            "away_team_name": m["away_team_name"],
            "home_team_logo": m.get("home_team_logo"),
            "away_team_logo": m.get("away_team_logo"),
            "scheduled_at":   m.get("scheduled_at"),
            "round":          m.get("round"),
        }
        await db.wc_games.update_one(
            {"id": g["id"]},
            {"$set": {
                "match_info": match_info,
                "eligible_country_names": [m["home_team_name"], m["away_team_name"]],
                "updated_at": now,
            }},
        )
        updated += 1
    print(f"Updated {updated} match-game docs (skipped {skipped}).")

    # Also denormalise eligible_country_names on group / matchday / round games.
    gcur = db.wc_games.find({"game_type": "group", "group_letter": {"$ne": None}}, {"_id": 0})
    g_updated = 0
    async for g in gcur:
        grp = await db.wc2026_groups.find_one({"group": g["group_letter"]}, {"_id": 0})
        if not grp:
            continue
        await db.wc_games.update_one(
            {"id": g["id"]},
            {"$set": {"eligible_country_names": grp.get("teams", []), "updated_at": now}},
        )
        g_updated += 1
    print(f"Updated {g_updated} group-game docs with eligible_country_names.")

    # Round games — use the union of all teams in matches with that round_label.
    rcur = db.wc_games.find({"game_type": "round", "round_label": {"$ne": None}}, {"_id": 0})
    r_updated = 0
    async for g in rcur:
        ms = await db.matches.find(
            {"round": g["round_label"]},
            {"_id": 0, "home_team_name": 1, "away_team_name": 1},
        ).to_list(length=64)
        countries = sorted({t for m in ms for t in (m.get("home_team_name"), m.get("away_team_name")) if t})
        if not countries:
            continue
        await db.wc_games.update_one(
            {"id": g["id"]},
            {"$set": {"eligible_country_names": countries, "updated_at": now}},
        )
        r_updated += 1
    print(f"Updated {r_updated} round-game docs.")


if __name__ == "__main__":
    asyncio.run(main())
