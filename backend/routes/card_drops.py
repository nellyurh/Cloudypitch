"""Random card drop loop — gamification hook.

Every 5 user actions (predictions saved, fantasy squad edited, prediction
submitted) we grant a random Legend Card via /api/cards/check-drop. The
frontend pings this endpoint after any user action and shows a toast/animation
if `dropped` is truthy.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

import auth as a
from db import get_db
from models import new_id

router = APIRouter(prefix="/api/cards", tags=["cards:drops"])

ACTIONS_PER_DROP = 5
# Weighted distribution: Star most common, GOAT rarest. Match TIER mapping in FE.
TIER_WEIGHTS = {3: 70, 2: 25, 1: 5}


@router.post("/check-drop")
async def check_drop(user: dict = Depends(a.get_current_user)):
    """Increment the user's action counter; if it crosses ACTIONS_PER_DROP,
    grant one random card and reset the counter.
    Idempotency: clients can call this freely; we only grant when the counter
    actually rolls over.
    """
    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    res = await db.user_action_counters.find_one_and_update(
        {"user_id": user["id"]},
        {"$inc": {"count": 1}, "$setOnInsert": {"created_at": now_iso}},
        upsert=True,
        return_document=True,
    )
    new_count = (res or {}).get("count", 1) if res else 1
    if new_count < ACTIONS_PER_DROP:
        return {"dropped": False, "progress": new_count, "needed": ACTIONS_PER_DROP}

    # Roll a tier
    tiers = list(TIER_WEIGHTS.keys())
    weights = list(TIER_WEIGHTS.values())
    tier = random.choices(tiers, weights=weights, k=1)[0]

    # Pick a random card from that tier
    cards = await db.legend_cards.find({"tier": tier, "is_active": {"$ne": False}}, {"_id": 0}).to_list(length=100)
    if not cards:
        # No catalog yet — reset and bail
        await db.user_action_counters.update_one({"user_id": user["id"]}, {"$set": {"count": 0}})
        return {"dropped": False, "progress": 0, "needed": ACTIONS_PER_DROP, "reason": "no_cards"}
    pick = random.choice(cards)

    # Grant 5 uses to the user — append to user_cards.
    user_card = await db.user_cards.find_one({"user_id": user["id"], "card_id": pick["id"]}, {"_id": 0})
    if user_card:
        await db.user_cards.update_one(
            {"id": user_card["id"]},
            {"$inc": {"uses_remaining": pick.get("uses_granted", 5)}, "$set": {"last_dropped_at": now_iso}},
        )
    else:
        await db.user_cards.insert_one({
            "id": new_id(),
            "user_id": user["id"],
            "card_id": pick["id"],
            "uses_remaining": pick.get("uses_granted", 5),
            "uses_left": pick.get("uses_granted", 5),
            "obtained_via": "drop",
            "created_at": now_iso,
            "last_dropped_at": now_iso,
        })

    # Reset counter
    await db.user_action_counters.update_one({"user_id": user["id"]}, {"$set": {"count": 0}})

    return {
        "dropped": True,
        "card": {
            "id": pick["id"],
            "tier": pick["tier"],
            "name": pick.get("name"),
            "player_name": pick.get("player_name"),
            "uses_granted": pick.get("uses_granted", 5),
        },
        "progress": 0,
        "needed": ACTIONS_PER_DROP,
    }
