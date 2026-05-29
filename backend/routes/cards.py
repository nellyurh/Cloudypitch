"""Legend cards: catalog + my cards + purchase + recharge.
Pricing is USD-denominated (in cents to avoid float issues).
50% of every card purchase/recharge flows into the World Cup prize pool.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import auth as a
from db import get_db
from models import new_id

router = APIRouter(prefix="/api/cards", tags=["cards"])


TIER_PRICE_USD_CENTS = {1: 200, 2: 100, 3: 50}  # $2, $1, $0.50
RECHARGE_PRICE_USD_CENTS = 20                    # $0.20
STARTER_USES = 5
RECHARGE_USES = 5
POOL_CONTRIBUTION_RATIO = 0.50  # 50% of revenue → prize pool
WC_PRIZE_POOL_ID = "pool-wc2026-fantasy"


async def _contribute_to_pool(db, amount_cents: int, user_id: str, source: str, reference: str | None):
    """Move 50% of amount_cents into the WC prize pool, log a contribution row."""
    contribution = int(amount_cents * POOL_CONTRIBUTION_RATIO)
    if contribution <= 0:
        return
    await db.prize_pools.update_one(
        {"id": WC_PRIZE_POOL_ID},
        {
            "$inc": {"amount_usd_cents": contribution, "amount_total_ngn": int(contribution * 16)},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
        },
        upsert=False,
    )
    await db.prize_pool_contributions.insert_one({
        "id": new_id(), "pool_id": WC_PRIZE_POOL_ID,
        "user_id": user_id, "source": source,
        "amount_usd_cents": contribution,
        "from_amount_usd_cents": amount_cents,
        "ratio": POOL_CONTRIBUTION_RATIO,
        "reference": reference,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


class PurchaseIn(BaseModel):
    card_id: str
    payment_reference: str | None = None


class RechargeIn(BaseModel):
    user_card_id: str
    payment_reference: str | None = None


@router.get("")
async def list_cards():
    db = get_db()
    cards = await db.legend_cards.find({}, {"_id": 0}).to_list(length=500)
    # Sort by tier asc, then price desc
    cards.sort(key=lambda c: (c.get("tier", 99), -(c.get("price_usd_cents") or 0)))
    return {
        "cards": cards,
        "currency": "USD",
        "tiers": {
            "1": {"name": "GOAT", "price_usd_cents": 200, "color": "#A3E635"},
            "2": {"name": "Elite", "price_usd_cents": 100, "color": "#0F6E56"},
            "3": {"name": "Star", "price_usd_cents": 50, "color": "#64748B"},
        },
        "recharge_price_usd_cents": RECHARGE_PRICE_USD_CENTS,
        "starter_uses": STARTER_USES,
        "pool_contribution_ratio": POOL_CONTRIBUTION_RATIO,
    }


@router.get("/me")
async def my_cards(user: dict = Depends(a.get_current_user)):
    db = get_db()
    owned = await db.user_cards.find({"user_id": user["id"]}, {"_id": 0}).to_list(length=500)
    card_ids = [c["card_id"] for c in owned]
    cards = await db.legend_cards.find({"id": {"$in": card_ids}}, {"_id": 0}).to_list(length=500)
    by_id = {c["id"]: c for c in cards}
    out = []
    for o in owned:
        c = by_id.get(o["card_id"])
        if c:
            out.append({**o, "card": c})
    return {"owned": out, "count": len(out)}


@router.get("/me/history")
async def my_card_usage_history(user: dict = Depends(a.get_current_user), limit: int = 100):
    """List every card the user has spent — with the game it was used in and the targeted player.
    Joined: card_uses ← legend_cards ← wc_games ← players (target)."""
    db = get_db()
    rows = await db.card_uses.find(
        {"user_id": user["id"]}, {"_id": 0},
    ).sort("created_at", -1).limit(limit).to_list(length=limit)
    if not rows:
        return {"history": []}
    card_ids = list({r["card_id"] for r in rows if r.get("card_id")})
    game_ids = list({r["wc_game_id"] for r in rows if r.get("wc_game_id")})
    player_ids = list({r["target_player_id"] for r in rows if r.get("target_player_id")})
    cards = await db.legend_cards.find({"id": {"$in": card_ids}}, {"_id": 0}).to_list(length=200)
    games = await db.wc_games.find({"id": {"$in": game_ids}}, {"_id": 0}).to_list(length=200)
    players = await db.players.find({"id": {"$in": player_ids}}, {"_id": 0, "id": 1, "name": 1, "team_name": 1, "team_logo": 1, "position": 1}).to_list(length=200)
    by_card = {c["id"]: c for c in cards}
    by_game = {g["id"]: g for g in games}
    by_player = {p["id"]: p for p in players}
    out = []
    for r in rows:
        out.append({
            **r,
            "card": by_card.get(r.get("card_id")),
            "game": by_game.get(r.get("wc_game_id")),
            "target_player": by_player.get(r.get("target_player_id")),
        })
    return {"history": out}


@router.post("/purchase")
async def purchase_card(body: PurchaseIn, user: dict = Depends(a.get_current_user)):
    """Create a user_card row after a successful Paystack txn (or via wallet).
    Contributes 50% of price to the WC prize pool."""
    db = get_db()
    card = await db.legend_cards.find_one({"id": body.card_id}, {"_id": 0})
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    price_cents = card.get("price_usd_cents") or TIER_PRICE_USD_CENTS.get(card.get("tier"), 50)
    existing = await db.user_cards.find_one({"user_id": user["id"], "card_id": body.card_id})
    if existing:
        await db.user_cards.update_one(
            {"id": existing["id"]},
            {"$inc": {"uses_remaining": STARTER_USES, "uses_left": STARTER_USES}},
        )
        uc_id = existing["id"]
    else:
        uc_id = new_id()
        await db.user_cards.insert_one({
            "id": uc_id, "user_id": user["id"], "card_id": body.card_id,
            "uses_remaining": STARTER_USES, "uses_left": STARTER_USES,
            "total_uses": 0,
            "acquired_via": "purchase",
            "purchase_reference": body.payment_reference,
            "acquired_at": datetime.now(timezone.utc).isoformat(),
        })
    await db.card_transactions.insert_one({
        "id": new_id(), "user_id": user["id"], "card_id": body.card_id,
        "user_card_id": uc_id, "type": "purchase",
        "amount_usd_cents": price_cents,
        "reference": body.payment_reference,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await _contribute_to_pool(db, price_cents, user["id"], "card_purchase", body.payment_reference)
    # Referral credit: if buyer was referred, give the referrer a credit
    await _referrer_credit(db, user["id"], price_cents)
    return {"ok": True, "user_card_id": uc_id, "amount_usd_cents": price_cents}


@router.post("/recharge")
async def recharge_card(body: RechargeIn, user: dict = Depends(a.get_current_user)):
    """Add +5 uses to an owned card for $0.20."""
    db = get_db()
    uc = await db.user_cards.find_one({"id": body.user_card_id, "user_id": user["id"]})
    if not uc:
        raise HTTPException(status_code=404, detail="Card not in your collection")
    await db.user_cards.update_one(
        {"id": uc["id"]},
        {"$inc": {"uses_remaining": RECHARGE_USES, "uses_left": RECHARGE_USES}},
    )
    await db.card_transactions.insert_one({
        "id": new_id(), "user_id": user["id"], "card_id": uc.get("card_id"),
        "user_card_id": uc["id"], "type": "recharge",
        "amount_usd_cents": RECHARGE_PRICE_USD_CENTS,
        "reference": body.payment_reference,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await _contribute_to_pool(db, RECHARGE_PRICE_USD_CENTS, user["id"], "card_recharge", body.payment_reference)
    await _referrer_credit(db, user["id"], RECHARGE_PRICE_USD_CENTS)
    return {"ok": True, "uses_added": RECHARGE_USES, "amount_usd_cents": RECHARGE_PRICE_USD_CENTS}


async def _referrer_credit(db, buyer_user_id: str, amount_cents: int):
    """When the buyer was referred by someone, increment that referrer's earnings counter."""
    buyer = await db.users.find_one({"id": buyer_user_id}, {"_id": 0, "referred_by_user_id": 1})
    if not buyer or not buyer.get("referred_by_user_id"):
        return
    referrer_id = buyer["referred_by_user_id"]
    # 10% kickback as referral credit (for leaderboard ranking only — not actual money)
    credit = int(amount_cents * 0.10)
    await db.referrals.update_one(
        {"referrer_user_id": referrer_id, "referred_user_id": buyer_user_id},
        {
            "$inc": {"credit_earned_usd_cents": credit, "referred_spend_usd_cents": amount_cents},
            "$setOnInsert": {
                "id": new_id(),
                "referrer_user_id": referrer_id, "referred_user_id": buyer_user_id,
                "joined_at": datetime.now(timezone.utc).isoformat(),
                "status": "active",
            },
        },
        upsert=True,
    )
