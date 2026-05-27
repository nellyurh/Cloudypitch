"""Predictions: make picks, list mine, leaderboard, settle finished matches."""
from fastapi import APIRouter, Depends, HTTPException
from db import get_db, utcnow_iso, utcnow
from models import PredictionIn, new_id
import auth as a

router = APIRouter(prefix="/api/predictions", tags=["predictions"])

POINTS_EXACT = 10  # exact score
POINTS_OUTCOME = 4  # correct outcome (H/A/D)
POINTS_GOAL_DIFF = 2  # correct goal difference (but not exact)


@router.get("/upcoming")
async def upcoming_for_user(limit: int = 50, user: dict = Depends(a.get_optional_user)):
    db = get_db()
    rows = await db.matches.find(
        {"status": {"$in": ["NS", "TBD"]}, "sport_slug": "football"},
        {"_id": 0, "raw_data": 0},
    ).sort("scheduled_at", 1).to_list(length=limit)
    # Attach my prediction if user is signed in
    if user:
        ids = [m["id"] for m in rows]
        preds = await db.predictions.find(
            {"user_id": user["id"], "match_id": {"$in": ids}}, {"_id": 0}
        ).to_list(length=200)
        by_match = {p["match_id"]: p for p in preds}
        for m in rows:
            m["my_prediction"] = by_match.get(m["id"])
    return {"matches": rows}


@router.post("")
async def submit_prediction(payload: PredictionIn, user: dict = Depends(a.get_current_user)):
    db = get_db()
    m = await db.matches.find_one({"id": payload.match_id}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Match not found")
    if m.get("status") not in ("NS", "TBD"):
        raise HTTPException(status_code=400, detail="Predictions closed for this match")
    outcome = "D"
    if payload.home_score_predicted > payload.away_score_predicted:
        outcome = "H"
    elif payload.home_score_predicted < payload.away_score_predicted:
        outcome = "A"
    doc = {
        "user_id": user["id"], "match_id": payload.match_id,
        "home_score_predicted": payload.home_score_predicted,
        "away_score_predicted": payload.away_score_predicted,
        "outcome_predicted": outcome,
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
    return {"prediction": doc}


@router.get("/me")
async def my_predictions(user: dict = Depends(a.get_current_user), limit: int = 100):
    db = get_db()
    rows = await db.predictions.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(length=limit)
    # Attach match info
    ids = [r["match_id"] for r in rows]
    matches = await db.matches.find({"id": {"$in": ids}}, {"_id": 0, "raw_data": 0}).to_list(length=200)
    by_id = {m["id"]: m for m in matches}
    for r in rows:
        r["match"] = by_id.get(r["match_id"])
    total_points = sum(r.get("points_awarded", 0) for r in rows)
    return {"predictions": rows, "total_points": total_points}


@router.get("/leaderboard")
async def leaderboard(limit: int = 50):
    db = get_db()
    pipeline = [
        {"$group": {
            "_id": "$user_id",
            "total_points": {"$sum": "$points_awarded"},
            "predictions_made": {"$sum": 1},
            "exact_scores": {"$sum": {"$cond": ["$exact_score_hit", 1, 0]}},
        }},
        {"$sort": {"total_points": -1, "exact_scores": -1}},
        {"$limit": limit},
    ]
    rows = await db.predictions.aggregate(pipeline).to_list(length=limit)
    user_ids = [r["_id"] for r in rows]
    users = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "id": 1, "display_name": 1, "country_code": 1}).to_list(length=200)
    by_id = {u["id"]: u for u in users}
    out = []
    for i, r in enumerate(rows, 1):
        u = by_id.get(r["_id"], {})
        out.append({
            "rank": i, "user_id": r["_id"], "display_name": u.get("display_name") or "Player",
            "country_code": u.get("country_code") or "NG",
            "total_points": r["total_points"], "predictions_made": r["predictions_made"],
            "exact_scores": r["exact_scores"],
        })
    return {"leaderboard": out}


@router.post("/settle")
async def settle_predictions(user: dict = Depends(a.require_admin)):
    """Admin trigger: score predictions for finished matches."""
    db = get_db()
    finished = await db.matches.find(
        {"status": {"$in": ["FT", "AET", "PEN"]}}, {"_id": 0, "id": 1, "home_score": 1, "away_score": 1}
    ).to_list(length=2000)
    settled = 0
    for m in finished:
        preds = await db.predictions.find({"match_id": m["id"], "settled_at": None}, {"_id": 0}).to_list(length=1000)
        for p in preds:
            actual_outcome = "D"
            if (m.get("home_score") or 0) > (m.get("away_score") or 0):
                actual_outcome = "H"
            elif (m.get("home_score") or 0) < (m.get("away_score") or 0):
                actual_outcome = "A"
            pts = 0
            exact = (p["home_score_predicted"] == (m.get("home_score") or 0)
                     and p["away_score_predicted"] == (m.get("away_score") or 0))
            outcome_ok = (p["outcome_predicted"] == actual_outcome)
            goal_diff_ok = ((p["home_score_predicted"] - p["away_score_predicted"]) ==
                            ((m.get("home_score") or 0) - (m.get("away_score") or 0)))
            if exact:
                pts = POINTS_EXACT
            elif outcome_ok and goal_diff_ok:
                pts = POINTS_OUTCOME + POINTS_GOAL_DIFF
            elif outcome_ok:
                pts = POINTS_OUTCOME
            await db.predictions.update_one(
                {"id": p["id"]},
                {"$set": {"points_awarded": pts, "exact_score_hit": exact,
                          "outcome_correct": outcome_ok, "settled_at": utcnow_iso()}},
            )
            settled += 1
    return {"settled": settled}
