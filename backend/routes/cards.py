"""Legend cards: catalog + my cards + purchase + recharge."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import auth as a
from db import get_db
from models import new_id

router = APIRouter(prefix="/api/cards", tags=["cards"])


TIER_PRICE_NGN = {1: 2000, 2: 1000, 3: 500}
RECHARGE_PRICE_NGN = 200
STARTER_USES = 5
RECHARGE_USES = 5


class PurchaseIn(BaseModel):
    card_id: str
    # In production this will be tied to a successful Paystack txn reference
    payment_reference: str | None = None


class RechargeIn(BaseModel):
    user_card_id: str
    payment_reference: str | None = None


@router.get("")
async def list_cards():
    db = get_db()
    cards = await db.legend_cards.find({}, {"_id": 0}).to_list(length=500)
    cards.sort(key=lambda c: (c["tier"], -c["price_ngn"]))
    return {
        "cards": cards,
        "tiers": {
            "1": {"name": "GOAT", "price_ngn": 2000, "color": "#A3E635"},
            "2": {"name": "Elite", "price_ngn": 1000, "color": "#0F6E56"},
            "3": {"name": "Star", "price_ngn": 500, "color": "#64748B"},
        },
        "recharge_price_ngn": RECHARGE_PRICE_NGN,
        "starter_uses": STARTER_USES,
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


@router.post("/purchase")
async def purchase_card(body: PurchaseIn, user: dict = Depends(a.get_current_user)):
    """Create a user_card row after a successful Paystack txn (or via wallet)."""
    db = get_db()
    card = await db.legend_cards.find_one({"id": body.card_id}, {"_id": 0})
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    # Already owned? Cards in this MVP are one-instance-per-user — recharges extend uses.
    existing = await db.user_cards.find_one({"user_id": user["id"], "card_id": body.card_id})
    if existing:
        # Top up rather than create duplicate
        await db.user_cards.update_one(
            {"id": existing["id"]},
            {"$inc": {"uses_remaining": STARTER_USES, "uses_left": STARTER_USES}},
        )
        return {"ok": True, "user_card_id": existing["id"], "topped_up": True}
    uc_id = new_id()
    doc = {
        "id": uc_id, "user_id": user["id"], "card_id": body.card_id,
        "uses_remaining": STARTER_USES, "uses_left": STARTER_USES,
        "total_uses": 0,
        "acquired_via": "purchase",
        "purchase_reference": body.payment_reference,
        "acquired_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.user_cards.insert_one(doc)
    await db.card_transactions.insert_one({
        "id": new_id(), "user_id": user["id"], "card_id": body.card_id,
        "user_card_id": uc_id, "type": "purchase",
        "amount_ngn": TIER_PRICE_NGN.get(card.get("tier"), card.get("price_ngn", 0)),
        "reference": body.payment_reference,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    doc.pop("_id", None)
    return {"ok": True, "user_card": doc}


@router.post("/recharge")
async def recharge_card(body: RechargeIn, user: dict = Depends(a.get_current_user)):
    """Add +5 uses to an owned card for ₦200. Requires the user to have already paid."""
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
        "amount_ngn": RECHARGE_PRICE_NGN,
        "reference": body.payment_reference,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True, "uses_added": RECHARGE_USES, "amount_ngn": RECHARGE_PRICE_NGN}
