"""Random card drop loop — gamification hook.

Two drop mechanics exist:

1. Per-action ("check-drop"): every 5 user actions while in-app
   (predictions/fantasy edits) grants one random card. Existing legacy
   mechanism, kept for retention.

2. Matchday drop ("daily-drop"): once per UTC calendar day, the first time a
   user opens the app after taking any qualifying action the previous day,
   they receive ONE low-tier (Star) Legend Card as a reward. On the WC Final
   day a small chance of a rare GOLD drop replaces it.

The matchday flow:
  • predictions / fantasy edits / WC entries call `log_user_action(user_id)`
    which upserts a doc into `user_daily_actions` keyed by (user_id, day).
  • Frontend pings `POST /api/cards/daily-drop` on every page load. If the user
    had an action yesterday AND has not yet been credited for that day, we
    grant the drop and persist a `card_drops_log` row to prevent doubles.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

import auth as a
from db import get_db
from models import new_id

router = APIRouter(prefix="/api/cards", tags=["cards:drops"])

# ─── Mechanic 1: per-action drops ────────────────────────────────────────
ACTIONS_PER_DROP = 5
# Weighted distribution: Star most common, GOAT rarest. Match TIER mapping in FE.
TIER_WEIGHTS = {3: 70, 2: 25, 1: 5}

# ─── Mechanic 2: matchday drops ──────────────────────────────────────────
# FIFA World Cup 2026 Final — UTC date. After kickoff (16:00 ET = 20:00 UTC)
# the drop rules apply.
WC_FINAL_DAY = "2026-07-19"
# On Final Day, % chance of a GOLD card instead of the standard Star drop.
WC_FINAL_GOLD_PCT = 10


def _yesterday_utc() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def log_user_action(user_id: str) -> None:
    """Idempotently record that `user_id` performed a qualifying action today.

    Called from predictions / fantasy / WC-game submit endpoints. Cheap upsert;
    safe to call multiple times per request.
    """
    if not user_id:
        return
    db = get_db()
    day = _today_utc()
    await db.user_daily_actions.update_one(
        {"user_id": user_id, "day": day},
        {"$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()},
         "$inc": {"actions": 1}},
        upsert=True,
    )


async def _grant_card(user_id: str, tier: int, source: str) -> dict | None:
    """Grant a random card of `tier` to `user_id`. Returns dict for client or
    None if the catalog has nothing for that tier."""
    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    cards = await db.legend_cards.find({"tier": tier, "is_active": {"$ne": False}}, {"_id": 0}).to_list(length=200)
    if not cards:
        return None
    pick = random.choice(cards)
    uses = pick.get("uses_granted", 1)
    existing = await db.user_cards.find_one({"user_id": user_id, "card_id": pick["id"]}, {"_id": 0})
    if existing:
        await db.user_cards.update_one(
            {"id": existing["id"]},
            {"$inc": {"uses_remaining": uses}, "$set": {"last_dropped_at": now_iso}},
        )
    else:
        await db.user_cards.insert_one({
            "id": new_id(), "user_id": user_id, "card_id": pick["id"],
            "uses_remaining": uses, "uses_left": uses,
            "obtained_via": source, "created_at": now_iso, "last_dropped_at": now_iso,
        })
    return {
        "id": pick["id"], "tier": pick["tier"], "name": pick.get("name"),
        "player_name": pick.get("player_name"), "uses_granted": uses,
    }


@router.post("/check-drop")
async def check_drop(user: dict = Depends(a.get_current_user)):
    """Increment the user's action counter; if it crosses ACTIONS_PER_DROP,
    grant one random card and reset the counter. (Legacy in-session reward.)
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

    tiers = list(TIER_WEIGHTS.keys())
    weights = list(TIER_WEIGHTS.values())
    tier = random.choices(tiers, weights=weights, k=1)[0]
    card = await _grant_card(user["id"], tier, source="drop")
    await db.user_action_counters.update_one({"user_id": user["id"]}, {"$set": {"count": 0}})
    if not card:
        return {"dropped": False, "progress": 0, "needed": ACTIONS_PER_DROP, "reason": "no_cards"}
    return {"dropped": True, "card": card, "progress": 0, "needed": ACTIONS_PER_DROP}


@router.post("/daily-drop")
async def daily_drop(user: dict = Depends(a.get_current_user)):
    """Grant the once-per-day matchday-completion card.

    Eligibility: the user must have performed at least one qualifying action
    on the previous UTC day, AND must not have already received this day's
    drop (tracked by `card_drops_log`).
    """
    db = get_db()
    uid = user["id"]
    y_day = _yesterday_utc()
    today = _today_utc()

    # Already credited for today?
    if await db.card_drops_log.find_one({"user_id": uid, "for_day": y_day}):
        return {"dropped": False, "reason": "already_credited", "for_day": y_day}

    # Did the user act yesterday?
    acted = await db.user_daily_actions.find_one({"user_id": uid, "day": y_day})
    if not acted:
        return {"dropped": False, "reason": "no_actions_yesterday", "for_day": y_day}

    # On Final Day reward, small chance of GOLD; otherwise always Star (tier 3).
    if y_day == WC_FINAL_DAY:
        tier = 1 if random.randint(1, 100) <= WC_FINAL_GOLD_PCT else 3
        source = "matchday_final"
    else:
        tier = 3
        source = "matchday"

    card = await _grant_card(uid, tier, source=source)
    if not card:
        return {"dropped": False, "reason": "no_cards", "for_day": y_day}

    await db.card_drops_log.insert_one({
        "id": new_id(), "user_id": uid, "for_day": y_day, "granted_on": today,
        "tier": tier, "card_id": card["id"], "source": source,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "dropped": True, "card": card, "for_day": y_day, "source": source,
        "is_final_day_drop": (y_day == WC_FINAL_DAY),
    }
