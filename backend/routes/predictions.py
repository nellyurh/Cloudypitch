"""Predictions — picks, my predictions, leaderboards, and settlement.

New in v2:
  - 30/15/10 base scoring
  - Stage multipliers (Group 1.0× → Final 4.0×)
  - Streak bonuses (3/+10, 5/+25, 10/+100)
  - Legend card boost (applied at predict-time, scored at settle-time)
  - Weekly + per-competition + per-country leaderboards
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import auth as a
from db import get_db, utcnow_iso
from models import PredictionIn, new_id
from scoring import score_prediction

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


class PredictionWithCardsIn(BaseModel):
    match_id: str
    home_score_predicted: int
    away_score_predicted: int


def _outcome(h: int, a: int) -> str:
    if h > a:
        return "H"
    if h < a:
        return "A"
    return "D"


# Sportmonks league IDs that count as "World Cup 2026" matches
# 732 = FIFA World Cup 2026 (qualifiers + finals).
# For dev/staging we also accept any league flagged `is_world_cup=true`.
WC_SPORTMONKS_LEAGUE_IDS = [732]


def _wc_match_filter() -> dict:
    """Mongo filter clause that matches ONLY World Cup matches."""
    return {
        "sport_slug": "football",
        "$or": [
            {"is_world_cup": True},
            {"league_id": {"$in": [f"sm-l-{lid}" for lid in WC_SPORTMONKS_LEAGUE_IDS]}},
            {"sportmonks_league_id": {"$in": WC_SPORTMONKS_LEAGUE_IDS}},
            {"competition_id": "wc-2026"},
        ],
    }


@router.get("/upcoming")
async def upcoming_for_user(limit: int = 50, user: dict = Depends(a.get_optional_user)):
    db = get_db()
    base = _wc_match_filter()
    base["status"] = {"$in": ["NS", "TBD"]}
    # Premium users can see fixtures up to 14 days ahead; free up to 7 days
    horizon_days = 14 if (user and user.get("is_premium")) else 7
    horizon = (datetime.now(timezone.utc) + timedelta(days=horizon_days)).isoformat()
    base["scheduled_at"] = {"$lte": horizon}
    rows = await db.matches.find(base, {"_id": 0, "raw_data": 0}).sort("scheduled_at", 1).to_list(length=limit)
    if user:
        ids = [m["id"] for m in rows]
        preds = await db.predictions.find(
            {"user_id": user["id"], "match_id": {"$in": ids}}, {"_id": 0}
        ).to_list(length=200)
        by_match = {p["match_id"]: p for p in preds}
        for m in rows:
            m["my_prediction"] = by_match.get(m["id"])
    return {"matches": rows, "scope": "world_cup_2026"}


@router.post("")
async def submit_prediction(payload: PredictionWithCardsIn, user: dict = Depends(a.get_current_user)):
    db = get_db()
    m = await db.matches.find_one({"id": payload.match_id}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Match not found")
    # WC-only enforcement
    is_wc = (
        m.get("is_world_cup")
        or m.get("competition_id") == "wc-2026"
        or m.get("sportmonks_league_id") in WC_SPORTMONKS_LEAGUE_IDS
        or m.get("league_id") in [f"sm-l-{lid}" for lid in WC_SPORTMONKS_LEAGUE_IDS]
    )
    if not is_wc:
        raise HTTPException(status_code=403, detail="Predictions are only available for FIFA World Cup 2026 matches.")
    if m.get("status") not in ("NS", "TBD"):
        raise HTTPException(status_code=400, detail="Predictions closed for this match")

    doc = {
        "user_id": user["id"], "match_id": payload.match_id,
        "home_score_predicted": payload.home_score_predicted,
        "away_score_predicted": payload.away_score_predicted,
        "outcome_predicted": _outcome(payload.home_score_predicted, payload.away_score_predicted),
        "points_awarded": 0, "exact_score_hit": False, "outcome_correct": False,
        "settled_at": None, "created_at": utcnow_iso(),
    }
    existing = await db.predictions.find_one({"user_id": user["id"], "match_id": payload.match_id})
    if existing:
        await db.predictions.update_one({"id": existing["id"]}, {"$set": doc})
        doc["id"] = existing["id"]
    else:
        doc["id"] = new_id()
        await db.predictions.insert_one(doc)
    doc.pop("_id", None)
    # Log a daily action for the matchday-drop reward system
    try:
        from routes.card_drops import log_user_action
        await log_user_action(user["id"])
    except Exception:
        pass
    return {"prediction": doc}


@router.get("/me")
async def my_predictions(user: dict = Depends(a.get_current_user), limit: int = 100):
    db = get_db()
    rows = await db.predictions.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(length=limit)
    ids = [r["match_id"] for r in rows]
    matches = await db.matches.find({"id": {"$in": ids}}, {"_id": 0, "raw_data": 0}).to_list(length=200)
    by_id = {m["id"]: m for m in matches}
    for r in rows:
        r["match"] = by_id.get(r["match_id"])
    total_points = sum(r.get("points_awarded", 0) for r in rows)
    exact_count = sum(1 for r in rows if r.get("exact_score_hit"))
    return {
        "predictions": rows, "total_points": total_points,
        "exact_count": exact_count, "settled_count": sum(1 for r in rows if r.get("settled_at")),
    }


@router.get("/leaderboard")
async def leaderboard(
    limit: int = 50,
    scope: str = "global",  # global | weekly | country | competition
    country: str | None = None,
    competition_id: str | None = None,
):
    """Multi-scope leaderboards."""
    db = get_db()
    pred_filter: dict = {"settled_at": {"$ne": None}}

    if scope == "weekly":
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        pred_filter["settled_at"] = {"$gte": week_ago}
    elif scope == "premium":
        # Restrict to predictions made by premium subscribers
        premium_ids = await db.users.distinct("id", {"is_premium": True})
        pred_filter["user_id"] = {"$in": premium_ids}
    elif scope == "competition" and competition_id:
        # Filter predictions by matches that belong to a Sportmonks league/competition
        match_ids = await db.matches.distinct("id", {"league_id": competition_id})
        pred_filter["match_id"] = {"$in": match_ids}

    pipeline = [
        {"$match": pred_filter},
        {"$group": {
            "_id": "$user_id",
            "total_points": {"$sum": "$points_awarded"},
            "predictions_made": {"$sum": 1},
            "exact_scores": {"$sum": {"$cond": ["$exact_score_hit", 1, 0]}},
        }},
        {"$sort": {"total_points": -1, "exact_scores": -1}},
        {"$limit": limit * 3 if scope == "country" else limit},
    ]
    rows = await db.predictions.aggregate(pipeline).to_list(length=limit * 3 if scope == "country" else limit)
    user_ids = [r["_id"] for r in rows]
    users = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "id": 1, "display_name": 1, "country_code": 1}).to_list(length=200)
    by_id = {u["id"]: u for u in users}

    out = []
    for i, r in enumerate(rows, 1):
        u = by_id.get(r["_id"], {})
        if scope == "country" and country and (u.get("country_code") or "").upper() != country.upper():
            continue
        out.append({
            "rank": len(out) + 1,
            "user_id": r["_id"], "display_name": u.get("display_name") or "Player",
            "country_code": u.get("country_code") or "NG",
            "total_points": r["total_points"], "predictions_made": r["predictions_made"],
            "exact_scores": r["exact_scores"],
        })
        if len(out) >= limit:
            break
    return {"scope": scope, "country": country, "competition_id": competition_id, "leaderboard": out}


async def _outcome_streak(db, user_id: str) -> int:
    """Return current outcome-correct streak for the user (count of consecutive correct outcomes
    in their most-recent settled predictions, ordered by match scheduled_at desc)."""
    settled = await db.predictions.find(
        {"user_id": user_id, "settled_at": {"$ne": None}},
        {"_id": 0, "outcome_correct": 1, "settled_at": 1},
    ).sort("settled_at", -1).to_list(length=200)
    streak = 0
    for p in settled:
        if p.get("outcome_correct"):
            streak += 1
        else:
            break
    return streak


@router.post("/settle")
async def settle_predictions(user: dict = Depends(a.require_admin)):
    """Admin trigger: score predictions for finished matches with new engine.

    🐛 We used to query every FT match in the DB and look up predictions per
    match — but with 5000+ FT matches across all sports, the WC matches fell
    outside the page limit and got skipped forever. Inverted: start from
    UNSETTLED predictions, then fetch only their matches in bulk.
    """
    db = get_db()
    pending = await db.predictions.find(
        {"settled_at": None}, {"_id": 0},
    ).to_list(length=20000)
    if not pending:
        return {"settled": 0}
    match_ids = list({p["match_id"] for p in pending})
    finished_matches = await db.matches.find(
        {"id": {"$in": match_ids}, "status": {"$in": ["FT", "AET", "PEN"]}},
        {"_id": 0},
    ).to_list(length=len(match_ids))
    by_id = {m["id"]: m for m in finished_matches}
    settled = 0
    for p in pending:
        m = by_id.get(p["match_id"])
        if not m:
            continue  # Match not yet final — skip; settler will catch it later.
        streak = await _outcome_streak(db, p["user_id"])
        result = score_prediction(
            predicted={"home_score_predicted": p["home_score_predicted"], "away_score_predicted": p["away_score_predicted"]},
            match=m,
            streak_count=streak + 1,
            applied_cards=[],  # Cards apply to fantasy ONLY, not predictions
        )
        await db.predictions.update_one(
            {"id": p["id"]},
            {"$set": {
                "points_awarded": result["points_awarded"],
                "base_points": result["base_points"],
                "stage": result["stage"],
                "stage_multiplier": result["stage_multiplier"],
                "streak_bonus": result["streak_bonus"],
                "exact_score_hit": result["exact_score_hit"],
                "outcome_correct": result["outcome_correct"],
                "diff_correct": result["diff_correct"],
                "settled_at": utcnow_iso(),
            }},
        )
        settled += 1
    return {"settled": settled}
