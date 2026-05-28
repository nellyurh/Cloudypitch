"""Fantasy points engine — computes per-player gameweek points from match events/stats.

Scoring (per spec):
- Minutes: ≤60min +1, >60min +2
- Goals: GK/DEF +6, MID +5, FWD +4
- Assists: all +3
- Clean sheets: GK/DEF +4, MID +1
- GK saves: every 3 saves +1, penalty save +5
- Yellow card -1, Red card -3, Own goal -2, Missed penalty -2, MOTM +3
- Captain ×2 (vice ×2 only if captain didn't play)
"""
from collections import defaultdict


GOAL_POINTS = {"GK": 6, "DEF": 6, "MID": 5, "FWD": 4}
ASSIST_POINTS = 3
CLEAN_SHEET_POINTS = {"GK": 4, "DEF": 4, "MID": 1, "FWD": 0}
YELLOW = -1
RED = -3
OWN_GOAL = -2
MISSED_PEN = -2
MOTM = 3
PEN_SAVE = 5
SAVE_TIER = 3  # +1 per 3 saves (GK only)


def compute_player_points(
    position: str,
    minutes_played: int,
    goals: int = 0,
    assists: int = 0,
    yellow_cards: int = 0,
    red_cards: int = 0,
    own_goals: int = 0,
    missed_penalties: int = 0,
    saves: int = 0,
    penalty_saves: int = 0,
    is_motm: bool = False,
    team_clean_sheet: bool = False,
) -> dict:
    """Return points + breakdown for one player."""
    breakdown = {}
    pts = 0
    if minutes_played >= 60:
        breakdown["minutes_60+"] = 2; pts += 2
    elif minutes_played > 0:
        breakdown["minutes_<60"] = 1; pts += 1
    if goals:
        gp = GOAL_POINTS.get(position, 4)
        breakdown[f"goals_x{goals}"] = goals * gp; pts += goals * gp
    if assists:
        breakdown[f"assists_x{assists}"] = assists * ASSIST_POINTS; pts += assists * ASSIST_POINTS
    if team_clean_sheet and minutes_played >= 60:
        cs = CLEAN_SHEET_POINTS.get(position, 0)
        if cs:
            breakdown["clean_sheet"] = cs; pts += cs
    if position == "GK" and saves:
        sp = saves // SAVE_TIER
        if sp:
            breakdown[f"saves_x{saves}"] = sp; pts += sp
    if penalty_saves:
        breakdown[f"pen_saves_x{penalty_saves}"] = penalty_saves * PEN_SAVE; pts += penalty_saves * PEN_SAVE
    if yellow_cards:
        breakdown[f"yellow_x{yellow_cards}"] = yellow_cards * YELLOW; pts += yellow_cards * YELLOW
    if red_cards:
        breakdown[f"red_x{red_cards}"] = red_cards * RED; pts += red_cards * RED
    if own_goals:
        breakdown[f"own_goals_x{own_goals}"] = own_goals * OWN_GOAL; pts += own_goals * OWN_GOAL
    if missed_penalties:
        breakdown[f"missed_pen_x{missed_penalties}"] = missed_penalties * MISSED_PEN; pts += missed_penalties * MISSED_PEN
    if is_motm:
        breakdown["motm"] = MOTM; pts += MOTM
    return {"points": pts, "breakdown": breakdown}


def aggregate_player_stats_from_events(events: list[dict], player_name: str, team_id: str) -> dict:
    """Walk match_events to count goals/assists/cards/MP/etc for a single player."""
    stats = defaultdict(int)
    for e in events or []:
        if not isinstance(e, dict):
            continue
        # Match by player_name (Sportmonks lineups + events both have this)
        pname = (e.get("player_name") or "").strip().lower()
        assist = (e.get("assist_player_name") or "").strip().lower()
        target = (player_name or "").strip().lower()
        if not target:
            continue
        etype = (e.get("type") or "").strip()
        if pname == target:
            if etype in ("Goal", "Penalty", "Penalty Shootout Goal", "Pen. Shootout Goal", "Goalscorer"):
                stats["goals"] += 1
            elif etype in ("Own Goal", "Owngoal"):
                stats["own_goals"] += 1
            elif etype in ("Missed Penalty", "Penalty Missed"):
                stats["missed_penalties"] += 1
            elif etype in ("Yellow Card", "Yellowcard"):
                stats["yellow_cards"] += 1
            elif etype in ("Red Card", "Redcard", "Yellow-Red Card", "Yellowred Card"):
                stats["red_cards"] += 1
            elif etype == "Substitution":
                stats["substituted_out"] += 1
        if assist == target and etype in ("Goal", "Penalty"):
            stats["assists"] += 1
    return dict(stats)
