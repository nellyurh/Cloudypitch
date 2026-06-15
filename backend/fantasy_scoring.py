"""Fantasy points engine — computes per-player gameweek points from match events/stats.

Scoring spec (canonical 2026-02-13):
─────────────────────────────────────
Core match
  · Minutes ≤ 60      → +1
  · Minutes ≥ 60      → +2 (excludes stoppage time)
  · Goal — GK / DEF   → +6
  · Goal — MID        → +5
  · Goal — FWD        → +4
  · Assist            → +3
  · Clean sheet GK/DEF→ +4
  · Clean sheet MID   → +1
  · Every 3 GK saves  → +1
  · Penalty save      → +5

Defensive contributions
  · DEF: +2 for every 10 CBIT  (Clearances + Blocks + Interceptions + Tackles)
  · MID/FWD: +2 for every 12 CBIRT (CBIT + Recoveries)

Deductions
  · Yellow card                 → -1
  · Red card                    → -3
  · Own goal                    → -2
  · Penalty miss                → -2
  · Every 2 goals conceded GK/DEF → -1

Special
  · Captain ×2 (vice ×2 fallback if captain didn't play)
  · MOTM bonus +3 (kept for future use; not in the canonical spec)
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

# Defensive contribution thresholds — every N actions = +2 pts.
DEF_CBIT_THRESHOLD = 10   # for Defenders
MIDFWD_CBIRT_THRESHOLD = 12  # for MID/FWD
DEFENSIVE_BONUS_POINTS = 2

# Every 2 goals conceded → -1 point (GK/DEF only)
GOALS_CONCEDED_TIER = 2


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
    goals_conceded: int = 0,
    clearances: int = 0,
    blocks: int = 0,
    interceptions: int = 0,
    tackles: int = 0,
    recoveries: int = 0,
) -> dict:
    """Return points + breakdown for one player."""
    breakdown = {}
    pts = 0

    # Minutes
    if minutes_played >= 60:
        breakdown["minutes_60+"] = 2; pts += 2
    elif minutes_played > 0:
        breakdown["minutes_<60"] = 1; pts += 1

    # Goals / assists
    if goals:
        gp = GOAL_POINTS.get(position, 4)
        breakdown[f"goals_x{goals}"] = goals * gp; pts += goals * gp
    if assists:
        breakdown[f"assists_x{assists}"] = assists * ASSIST_POINTS; pts += assists * ASSIST_POINTS

    # Clean sheet (requires ≥60 min)
    if team_clean_sheet and minutes_played >= 60:
        cs = CLEAN_SHEET_POINTS.get(position, 0)
        if cs:
            breakdown["clean_sheet"] = cs; pts += cs

    # GK-only: saves & penalty saves
    if position == "GK" and saves:
        sp = saves // SAVE_TIER
        if sp:
            breakdown[f"saves_x{saves}"] = sp; pts += sp
    if penalty_saves:
        breakdown[f"pen_saves_x{penalty_saves}"] = penalty_saves * PEN_SAVE; pts += penalty_saves * PEN_SAVE

    # ── Defensive contributions (NEW 2026-02-13) ───────────────────────
    # DEF earns +2 per 10 CBIT; MID/FWD earn +2 per 12 CBIRT.
    cbit = (clearances or 0) + (blocks or 0) + (interceptions or 0) + (tackles or 0)
    if position == "DEF" and cbit >= DEF_CBIT_THRESHOLD:
        units = cbit // DEF_CBIT_THRESHOLD
        bonus = units * DEFENSIVE_BONUS_POINTS
        breakdown[f"cbit_{cbit}"] = bonus; pts += bonus
    elif position in ("MID", "FWD"):
        cbirt = cbit + (recoveries or 0)
        if cbirt >= MIDFWD_CBIRT_THRESHOLD:
            units = cbirt // MIDFWD_CBIRT_THRESHOLD
            bonus = units * DEFENSIVE_BONUS_POINTS
            breakdown[f"cbirt_{cbirt}"] = bonus; pts += bonus

    # ── Goals-conceded penalty (NEW 2026-02-13) ────────────────────────
    # GK and DEF lose 1 point per 2 goals conceded by their team.
    if position in ("GK", "DEF") and goals_conceded >= GOALS_CONCEDED_TIER:
        penalty = -(goals_conceded // GOALS_CONCEDED_TIER)
        breakdown[f"goals_conceded_{goals_conceded}"] = penalty; pts += penalty

    # Deductions
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
