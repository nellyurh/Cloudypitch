"""User profile."""
from fastapi import APIRouter, Depends
from db import get_db
import auth as a
from models import public_user

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me/stats")
async def my_stats(user: dict = Depends(a.get_current_user)):
    db = get_db()
    pred_count = await db.predictions.count_documents({"user_id": user["id"]})
    pred_points = 0
    async for p in db.predictions.find({"user_id": user["id"]}, {"points_awarded": 1}):
        pred_points += p.get("points_awarded", 0)
    exact = await db.predictions.count_documents({"user_id": user["id"], "exact_score_hit": True})
    fantasy_squad = await db.fantasy_squads.find_one({"user_id": user["id"]}, {"_id": 0})
    cards_count = await db.user_cards.count_documents({"user_id": user["id"]})
    favs = await db.favorites.count_documents({"user_id": user["id"]})
    wc_entries_count = await db.wc_game_entries.count_documents({"user_id": user["id"]})
    # Eligibility thresholds — mirror routes/leaderboard.py.
    from routes.leaderboard import PRIZE_POOL_MIN_PREDICTIONS, PRIZE_POOL_MIN_WC_GAMES
    return {
        "user": public_user(user),
        "stats": {
            "predictions_made": pred_count,
            "predictions_points": pred_points,
            "exact_scores": exact,
            "fantasy_total_points": (fantasy_squad or {}).get("total_points", 0),
            "cards_owned": cards_count,
            "favorites": favs,
            "wc_games_played": wc_entries_count,
        },
        "eligibility": {
            "min_predictions": PRIZE_POOL_MIN_PREDICTIONS,
            "min_wc_games": PRIZE_POOL_MIN_WC_GAMES,
            "predictions_made": pred_count,
            "wc_games_played": wc_entries_count,
            "is_eligible": (
                pred_count >= PRIZE_POOL_MIN_PREDICTIONS
                and wc_entries_count >= PRIZE_POOL_MIN_WC_GAMES
            ),
            "progress_pct": min(100, int(round(
                (min(pred_count, PRIZE_POOL_MIN_PREDICTIONS) / max(PRIZE_POOL_MIN_PREDICTIONS, 1) * 50)
                + (min(wc_entries_count, PRIZE_POOL_MIN_WC_GAMES) / max(PRIZE_POOL_MIN_WC_GAMES, 1) * 50)
            ))),
        },
        "fantasy_squad": fantasy_squad,
    }


@router.post("/me/favorites/{entity_type}/{entity_id}")
async def add_favorite(entity_type: str, entity_id: str, user: dict = Depends(a.get_current_user)):
    db = get_db()
    await db.favorites.update_one(
        {"user_id": user["id"], "entity_type": entity_type, "entity_id": entity_id},
        {"$setOnInsert": {"user_id": user["id"], "entity_type": entity_type, "entity_id": entity_id}},
        upsert=True,
    )
    return {"ok": True}


@router.delete("/me/favorites/{entity_type}/{entity_id}")
async def remove_favorite(entity_type: str, entity_id: str, user: dict = Depends(a.get_current_user)):
    db = get_db()
    await db.favorites.delete_one(
        {"user_id": user["id"], "entity_type": entity_type, "entity_id": entity_id}
    )
    return {"ok": True}


@router.get("/me/favorites")
async def list_favorites(user: dict = Depends(a.get_current_user)):
    db = get_db()
    favs = await db.favorites.find({"user_id": user["id"]}, {"_id": 0}).to_list(length=500)
    return {"favorites": favs}
