"""Team detail endpoint — feeds the Sofascore-style team view page.

GET /api/teams/{team_id} → {
  team: {...},
  recent_matches: [...latest 5 finished matches...],
  upcoming_matches: [...next 5...],
  squad: [...players for this team...],
  group: "A" | null,
  group_table: [...rest of group teams + this one with P/W/D/L/GF/GA/PTS...],
}
"""
from fastapi import APIRouter, HTTPException
import re
from db import get_db

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.get("/{team_id}")
async def team_detail(team_id: str):
    db = get_db()
    team = await db.teams.find_one({"id": team_id}, {"_id": 0})
    if not team:
        # Also try sportmonks_id for legacy URLs
        team = await db.teams.find_one({"sportmonks_id": team_id}, {"_id": 0})
    if not team:
        # And by case-insensitive name match (URL-friendly).
        # Escape user input to prevent regex injection.
        safe = re.escape(team_id.replace("-", " "))
        team = await db.teams.find_one(
            {"name": {"$regex": f"^{safe}$", "$options": "i"}}, {"_id": 0}
        )
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    tname = team.get("name") or ""

    # Recent finished matches (last 5)
    recent = await db.matches.find(
        {"$or": [{"home_team_name": tname}, {"away_team_name": tname}],
         "home_score": {"$ne": None}, "away_score": {"$ne": None}},
        {"_id": 0, "raw_data": 0},
    ).sort("scheduled_at", -1).limit(5).to_list(length=5)

    # Upcoming (next 5)
    upcoming = await db.matches.find(
        {"$or": [{"home_team_name": tname}, {"away_team_name": tname}],
         "scheduled_at": {"$gte": "2026-01-01"}},
        {"_id": 0, "raw_data": 0},
    ).sort("scheduled_at", 1).limit(5).to_list(length=5)

    # Squad
    squad = await db.players.find(
        {"team_name": tname},
        {"_id": 0, "raw_data": 0},
    ).limit(40).to_list(length=40)

    # Group (look up which WC group the team is in)
    groups = await db.wc2026_groups.find({"teams": tname}, {"_id": 0}).to_list(length=1)
    group_letter = groups[0]["group"] if groups else None
    group_teams = groups[0].get("teams", []) if groups else []

    # Build group table — until tournament starts these are 0s, otherwise live computed
    table = []
    for t in group_teams:
        stats = {"team": t, "P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "PTS": 0}
        table.append(stats)

    return {
        "team": team,
        "recent_matches": recent,
        "upcoming_matches": upcoming,
        "squad": squad,
        "group": group_letter,
        "group_table": table,
    }
