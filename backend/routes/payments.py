"""Paystack payments: initialize, verify, webhook, and transfer (prize payouts).
Test-mode keys: set PAYSTACK_SECRET_KEY and PAYSTACK_PUBLIC_KEY env vars.
"""
import hashlib
import hmac
import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

import auth as a
from db import get_db
from models import new_id
from routes.compliance import check_can_spend

router = APIRouter(prefix="/api/payments/paystack", tags=["payments"])

PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = os.environ.get("PAYSTACK_PUBLIC_KEY", "")
PAYSTACK_BASE = "https://api.paystack.co"


class InitTxnIn(BaseModel):
    purpose: str = Field(pattern="^(card_purchase|card_recharge|wallet_deposit|premium_sub)$")
    amount_ngn: int = Field(ge=100, le=10_000_000)
    target_id: str | None = None  # card_id (purchase) or user_card_id (recharge)
    callback_url: str  # frontend supplies window.location.origin + "/payment/callback"


@router.get("/config")
async def paystack_config():
    """Frontend pulls the public key (safe to expose)."""
    return {
        "public_key": PAYSTACK_PUBLIC_KEY,
        "configured": bool(PAYSTACK_SECRET_KEY and PAYSTACK_PUBLIC_KEY),
        "currency": "NGN",
    }


@router.post("/initialize")
async def initialize(body: InitTxnIn, user: dict = Depends(a.get_current_user)):
    if not PAYSTACK_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Paystack not configured. Set PAYSTACK_SECRET_KEY in backend env.")
    # Spending cap pre-flight
    ok, reason = await check_can_spend(user["id"], body.amount_ngn)
    if not ok:
        raise HTTPException(status_code=403, detail=reason or "Spending cap reached")

    reference = f"cp_{new_id().replace('-', '')[:16]}"
    payload = {
        "email": user["email"],
        "amount": body.amount_ngn * 100,  # kobo
        "reference": reference,
        "callback_url": body.callback_url,
        "metadata": {
            "user_id": user["id"],
            "purpose": body.purpose,
            "target_id": body.target_id,
        },
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            f"{PAYSTACK_BASE}/transaction/initialize",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"},
            json=payload,
        )
    data = r.json()
    if not data.get("status"):
        raise HTTPException(status_code=502, detail=data.get("message", "Paystack init failed"))
    # Persist pending txn
    db = get_db()
    await db.payment_intents.insert_one({
        "id": reference, "user_id": user["id"],
        "purpose": body.purpose, "target_id": body.target_id,
        "amount_ngn": body.amount_ngn, "status": "pending",
        "authorization_url": data["data"]["authorization_url"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {
        "authorization_url": data["data"]["authorization_url"],
        "reference": reference,
        "access_code": data["data"].get("access_code"),
    }


@router.get("/verify/{reference}")
async def verify(reference: str, user: dict = Depends(a.get_current_user)):
    if not PAYSTACK_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Paystack not configured")
    db = get_db()
    intent = await db.payment_intents.find_one({"id": reference, "user_id": user["id"]}, {"_id": 0})
    if not intent:
        raise HTTPException(status_code=404, detail="Payment intent not found")
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{PAYSTACK_BASE}/transaction/verify/{reference}",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"},
        )
    data = r.json()
    if not (data.get("status") and (data.get("data") or {}).get("status") == "success"):
        await db.payment_intents.update_one({"id": reference}, {"$set": {"status": "failed"}})
        return {"status": "failed", "details": data.get("data")}
    # Idempotency
    if intent.get("status") == "fulfilled":
        return {"status": "success", "already_fulfilled": True}
    await _fulfill(intent, data["data"])
    return {"status": "success", "purpose": intent["purpose"]}


@router.post("/webhook")
async def webhook(request: Request):
    if not PAYSTACK_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Paystack not configured")
    signature = request.headers.get("x-paystack-signature", "")
    body = await request.body()
    computed = hmac.new(PAYSTACK_SECRET_KEY.encode(), body, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(computed, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    event = await request.json()
    etype = event.get("event")
    if etype == "charge.success":
        data = event["data"]
        reference = data["reference"]
        db = get_db()
        intent = await db.payment_intents.find_one({"id": reference}, {"_id": 0})
        if intent and intent.get("status") != "fulfilled":
            await _fulfill(intent, data)
    return {"status": "ok"}


async def _fulfill(intent: dict, paystack_data: dict):
    """Mark intent fulfilled + perform the purpose action (credit wallet / grant card / etc.)."""
    db = get_db()
    user_id = intent["user_id"]
    purpose = intent["purpose"]
    amount = intent["amount_ngn"]

    if purpose == "wallet_deposit":
        # Credit wallet
        await db.user_wallets.update_one(
            {"user_id": user_id},
            {"$inc": {"balance_ngn": amount, "total_deposited": amount},
             "$setOnInsert": {"id": new_id(), "user_id": user_id, "total_won": 0, "total_spent": 0,
                              "kyc_verified": False}},
            upsert=True,
        )
        w = await db.user_wallets.find_one({"user_id": user_id}, {"_id": 0})
        await db.wallet_transactions.insert_one({
            "id": new_id(), "user_id": user_id, "type": "deposit",
            "amount_ngn": amount, "balance_after": (w or {}).get("balance_ngn", amount),
            "reference": intent["id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    elif purpose == "card_purchase":
        card_id = intent.get("target_id")
        existing = await db.user_cards.find_one({"user_id": user_id, "card_id": card_id})
        if existing:
            await db.user_cards.update_one({"id": existing["id"]}, {"$inc": {"uses_remaining": 1, "uses_left": 1}})
        else:
            uc_id = new_id()
            await db.user_cards.insert_one({
                "id": uc_id, "user_id": user_id, "card_id": card_id,
                "uses_remaining": 1, "uses_left": 1, "total_uses": 0,
                "acquired_via": "purchase", "purchase_reference": intent["id"],
                "acquired_at": datetime.now(timezone.utc).isoformat(),
            })
        await db.card_transactions.insert_one({
            "id": new_id(), "user_id": user_id, "card_id": card_id,
            "type": "purchase", "amount_ngn": amount,
            "reference": intent["id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    elif purpose == "card_recharge":
        await db.user_cards.update_one(
            {"id": intent.get("target_id"), "user_id": user_id},
            {"$inc": {"uses_remaining": 1, "uses_left": 1}},
        )
        await db.card_transactions.insert_one({
            "id": new_id(), "user_id": user_id, "user_card_id": intent.get("target_id"),
            "type": "recharge", "amount_ngn": amount,
            "reference": intent["id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    elif purpose == "premium_sub":
        # Mark user premium for 30 days
        from datetime import timedelta
        until = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        await db.users.update_one({"id": user_id}, {"$set": {"is_premium": True, "premium_until": until}})

    await db.payment_intents.update_one(
        {"id": intent["id"]},
        {"$set": {"status": "fulfilled", "fulfilled_at": datetime.now(timezone.utc).isoformat(),
                  "paystack_data": paystack_data}},
    )


# ===== Transfers (prize-pool payouts) =====
class TransferIn(BaseModel):
    user_id: str
    amount_ngn: int
    reason: str = "Cloudy Pitch prize payout"


@router.post("/transfer")
async def transfer_to_user(body: TransferIn, admin: dict = Depends(a.require_admin)):
    """Admin-only: payout to a user's bank via Paystack Transfers API.
    Requires the user to have a verified `recipient_code` on their wallet."""
    if not PAYSTACK_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Paystack not configured")
    db = get_db()
    w = await db.user_wallets.find_one({"user_id": body.user_id}, {"_id": 0})
    if not w or not w.get("paystack_recipient_code"):
        raise HTTPException(status_code=400, detail="User has no verified bank account / Paystack recipient_code")
    if not w.get("kyc_verified"):
        raise HTTPException(status_code=403, detail="User not KYC-verified")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{PAYSTACK_BASE}/transfer",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"},
            json={
                "source": "balance",
                "amount": body.amount_ngn * 100,
                "recipient": w["paystack_recipient_code"],
                "reason": body.reason,
            },
        )
    data = r.json()
    if not data.get("status"):
        raise HTTPException(status_code=502, detail=data.get("message", "Transfer failed"))
    return {"ok": True, "transfer": data["data"]}
