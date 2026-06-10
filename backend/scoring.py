"""Scoring engine — applies stage multipliers, streak bonuses, and legend-card boosts
to prediction settlement.

Public API:
  - score_prediction(prediction, match, stage, streak_count, applied_cards) -> dict
  - compute_stage(match) -> str
  - compute_card_boost(applied_cards, prediction_context) -> float
"""
from __future__ import annotations

from typing import Iterable

# Base points (per spec)
POINTS_EXACT = 30
POINTS_DIFF = 15  # outcome + goal difference both correct
POINTS_OUTCOME = 10

# World Cup stage multipliers
STAGE_MULTIPLIERS = {
    "group": 1.0,
    "round_of_32": 1.5,
    "r32": 1.5,
    "round_of_16": 2.0,
    "r16": 2.0,
    "quarterfinal": 2.5,
    "qf": 2.5,
    "semifinal": 3.0,
    "sf": 3.0,
    "final": 4.0,
    "third_place": 2.5,
}

# Streak bonuses (cumulative correct-outcome predictions in a row)
STREAK_BONUSES = [
    (10, 100),
    (5, 25),
    (3, 10),
]

# Card boost stacking cap: sum of (multiplier - 1.0) cannot exceed +1.0
CARD_BOOST_CAP = 1.0


def compute_stage(match: dict | None) -> str:
    """Detect WC stage from match data. Returns key in STAGE_MULTIPLIERS or 'group' as default."""
    if not match:
        return "group"
    # Look in round name first, then stage name
    round_name = ((match.get("round") or {}).get("name") if isinstance(match.get("round"), dict) else None) or ""
    stage_name = ((match.get("stage") or {}).get("name") if isinstance(match.get("stage"), dict) else None) or ""
    text = f"{round_name} {stage_name}".lower()
    if "final" in text and "semi" not in text and "quarter" not in text and "1/8" not in text and "1/16" not in text:
        return "final"
    if "semi" in text or "1/2" in text:
        return "semifinal"
    if "quarter" in text or "1/4" in text:
        return "quarterfinal"
    if "1/8" in text or "round of 16" in text or "r16" in text:
        return "round_of_16"
    if "1/16" in text or "round of 32" in text or "r32" in text:
        return "round_of_32"
    if "third" in text or "3rd place" in text:
        return "third_place"
    return "group"


def compute_card_boost(applied_cards: Iterable[dict], context: dict) -> float:
    """Sum matching cards' (multiplier - 1.0), capped at CARD_BOOST_CAP.
    `applied_cards` is a list of legend_card dicts with effect_type + effect_value.
    `context` describes the prediction (home_country, away_country, etc.).
    """
    boost = 0.0
    for card in (applied_cards or []):
        if not isinstance(card, dict):
            continue
        if not card_matches(card, context):
            continue
        mult = float((card.get("effect_value") or {}).get("multiplier") or 1.0)
        boost += max(0.0, mult - 1.0)
    return min(boost, CARD_BOOST_CAP)


def card_matches(card: dict, context: dict) -> bool:
    """Does the card's effect condition match this prediction context?
    Supports both the spec vocabulary (country_boost/continent_boost/position_boost/role_boost/flat_boost)
    AND the existing seed vocabulary (score_boost/outcome_boost/captain_boost/defense_boost).

    Cards now ALSO carry a `position` lock — when set to GK/DEF/MID/FWD the
    card only fires on a player of that position. 'ANY' (or missing) means
    no position lock. The lock applies to all fantasy-scope card uses.
    """
    # ---- Position lock (applies to all FANTASY cards) ----
    card_pos = (card.get("position") or "ANY").upper()
    if context.get("scope") == "fantasy" and card_pos and card_pos != "ANY":
        ctx_pos = (context.get("position") or "").upper()
        if ctx_pos != card_pos:
            return False

    etype = card.get("effect_type") or "flat_boost"
    ev = card.get("effect_value") or {}
    card_country = (card.get("country_code") or "").upper()

    if etype == "flat_boost":
        return True
    if etype == "country_boost":
        wanted = (ev.get("country") or card_country).upper()
        if not wanted:
            return True
        home_c = (context.get("home_country") or "").upper()
        away_c = (context.get("away_country") or "").upper()
        return wanted in (home_c, away_c)
    if etype == "continent_boost":
        wanted = (ev.get("continent") or "").lower()
        return wanted in ((context.get("home_continent") or "").lower(), (context.get("away_continent") or "").lower())
    if etype == "position_boost":
        return context.get("scope") == "fantasy" and context.get("position") == ev.get("position")
    if etype == "role_boost":
        return context.get("scope") == "fantasy" and context.get("role") == (ev.get("role") or "").lower()
    # ---- Legacy effect_type vocabulary (existing seeds) ----
    # These all fire when the prediction/squad involves the card's COUNTRY
    if etype in ("score_boost", "outcome_boost"):
        if not card_country:
            return True  # generic boost if no country tag
        home_c = (context.get("home_country") or "").upper()
        away_c = (context.get("away_country") or "").upper()
        return card_country in (home_c, away_c)
    if etype == "captain_boost":
        return context.get("scope") == "fantasy" and context.get("role") == "captain"
    if etype == "defense_boost":
        return context.get("scope") == "fantasy" and context.get("position") in ("GK", "DEF")
    return False


def streak_bonus(streak_count: int) -> int:
    """Return the bonus for the highest streak threshold met."""
    for threshold, bonus in STREAK_BONUSES:
        if streak_count >= threshold:
            return bonus
    return 0


def base_prediction_points(predicted: dict, actual: dict) -> tuple[int, bool, bool, bool]:
    """Compute base points + flags. Returns (points, exact, diff_ok, outcome_ok)."""
    p_h = int(predicted.get("home_score_predicted") or 0)
    p_a = int(predicted.get("away_score_predicted") or 0)
    a_h = int(actual.get("home_score") or 0)
    a_a = int(actual.get("away_score") or 0)
    if p_h > p_a:
        p_out = "H"
    elif p_h < p_a:
        p_out = "A"
    else:
        p_out = "D"
    if a_h > a_a:
        a_out = "H"
    elif a_h < a_a:
        a_out = "A"
    else:
        a_out = "D"

    exact = (p_h == a_h and p_a == a_a)
    outcome_ok = (p_out == a_out)
    diff_ok = ((p_h - p_a) == (a_h - a_a))

    if exact:
        return POINTS_EXACT, True, True, True
    if outcome_ok and diff_ok:
        return POINTS_DIFF, False, True, True
    if outcome_ok:
        return POINTS_OUTCOME, False, False, True
    return 0, False, False, False


def score_prediction(
    predicted: dict,
    match: dict,
    streak_count: int = 0,
    applied_cards: list[dict] | None = None,
) -> dict:
    """Settle a single prediction. Returns full breakdown."""
    base, exact, diff_ok, outcome_ok = base_prediction_points(predicted, match)
    stage = compute_stage(match)
    stage_mult = STAGE_MULTIPLIERS.get(stage, 1.0)

    context = {
        "scope": "prediction",
        "home_country": (match.get("home_country") or match.get("home_team_country") or ""),
        "away_country": (match.get("away_country") or match.get("away_team_country") or ""),
    }
    boost = compute_card_boost(applied_cards or [], context) if outcome_ok else 0.0
    bonus = streak_bonus(streak_count) if outcome_ok else 0
    final = round(base * stage_mult * (1.0 + boost)) + bonus

    return {
        "base_points": base,
        "stage": stage,
        "stage_multiplier": stage_mult,
        "card_boost": boost,
        "streak_bonus": bonus,
        "streak_count": streak_count,
        "points_awarded": final,
        "exact_score_hit": exact,
        "diff_correct": diff_ok,
        "outcome_correct": outcome_ok,
    }
