"""User wallet + transaction ledger.
Funds source: Paystack deposits (test-mode flow uses payment_reference).
Funds use: card purchases, card recharges, withdrawals (with KYC).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import auth as a
from db import get_db
from models import new_id

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


class DepositIn(BaseModel):
    amount_ngn: int = Field(ge=100, le=1_000_000)
    payment_reference: str | None = None  # tied to Paystack txn ref after verify


class SpendIn(BaseModel):
    amount_ngn: int = Field(ge=1, le=1_000_000)
    type: str = Field(pattern="^(purchase|recharge|withdrawal)$")
    reference: str | None = None
    notes: str | None = None


class WithdrawIn(BaseModel):
    """User-initiated withdrawal request. No KYC — winners are contacted
    manually after the tournament with a payout link.
    """
    amount_ngn: int = Field(ge=500, le=10_000_000)
    method: str = Field(pattern="^(bank_ngn|usdt|btc|paypal|wise)$")
    # Destination is opaque on purpose — admin reads from the audit doc.
    destination: dict = Field(default_factory=dict)
    country_code: str | None = None
    notes: str | None = None


async def _ensure_wallet(user_id: str) -> dict:
    db = get_db()
    w = await db.user_wallets.find_one({"user_id": user_id}, {"_id": 0})
    if not w:
        w = {
            "id": new_id(), "user_id": user_id,
            "balance_ngn": 0, "total_deposited": 0, "total_won": 0, "total_spent": 0,
            "kyc_verified": False, "bank_account": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.user_wallets.insert_one(w)
    w.pop("_id", None)
    return w


@router.get("/me")
async def my_wallet(user: dict = Depends(a.get_current_user)):
    """Returns BOTH the NGN wallet (`user_wallets.balance_ngn` + totals) AND
    the USD spend wallet (`users.wallet_balance_usd_cents`). NGN deposits via
    PocketFi auto-mirror into the USD side at the current exchange rate so a
    single deposit funds both currencies."""
    wallet = await _ensure_wallet(user["id"])
    # Pull the latest USD balance directly from the users doc.
    udoc = await get_db().users.find_one({"id": user["id"]}, {"_id": 0, "wallet_balance_usd_cents": 1}) or {}
    return {
        "wallet": wallet,
        "wallet_balance_usd_cents": int(udoc.get("wallet_balance_usd_cents") or 0),
    }


@router.get("/transactions")
async def my_transactions(limit: int = 50, user: dict = Depends(a.get_current_user)):
    db = get_db()
    rows = await db.wallet_transactions.find(
        {"user_id": user["id"]}, {"_id": 0},
    ).sort("created_at", -1).limit(limit).to_list(length=limit)
    return {"transactions": rows}


@router.post("/deposit")
async def deposit(body: DepositIn, user: dict = Depends(a.get_current_user)):
    """Credit wallet after a verified Paystack txn (or admin manual credit in test mode)."""
    db = get_db()
    w = await _ensure_wallet(user["id"])
    new_balance = (w.get("balance_ngn") or 0) + body.amount_ngn
    await db.user_wallets.update_one(
        {"user_id": user["id"]},
        {"$inc": {"balance_ngn": body.amount_ngn, "total_deposited": body.amount_ngn},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    tx = {
        "id": new_id(), "user_id": user["id"], "type": "deposit",
        "amount_ngn": body.amount_ngn, "balance_after": new_balance,
        "reference": body.payment_reference,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.wallet_transactions.insert_one(tx)
    tx.pop("_id", None)
    return {"ok": True, "balance_ngn": new_balance, "transaction": tx}


@router.post("/spend")
async def spend(body: SpendIn, user: dict = Depends(a.get_current_user)):
    """Internal — decrement wallet for a card purchase / recharge / withdrawal."""
    db = get_db()
    w = await _ensure_wallet(user["id"])
    if (w.get("balance_ngn") or 0) < body.amount_ngn:
        raise HTTPException(status_code=402, detail="Insufficient wallet balance")
    # KYC has been removed for withdrawals — winners are contacted manually
    # after the tournament, so we don't gate the wallet `spend` flow on it.
    new_balance = (w.get("balance_ngn") or 0) - body.amount_ngn
    await db.user_wallets.update_one(
        {"user_id": user["id"]},
        {"$inc": {"balance_ngn": -body.amount_ngn, "total_spent": body.amount_ngn},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    tx = {
        "id": new_id(), "user_id": user["id"], "type": body.type,
        "amount_ngn": -body.amount_ngn, "balance_after": new_balance,
        "reference": body.reference, "notes": body.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.wallet_transactions.insert_one(tx)
    tx.pop("_id", None)
    return {"ok": True, "balance_ngn": new_balance, "transaction": tx}


@router.post("/credit-winnings")
async def credit_winnings(body: DepositIn, user_id: str, user: dict = Depends(a.require_admin)):
    """Admin-only: credit prize-pool winnings to a user's wallet."""
    db = get_db()
    w = await _ensure_wallet(user_id)
    new_balance = (w.get("balance_ngn") or 0) + body.amount_ngn
    await db.user_wallets.update_one(
        {"user_id": user_id},
        {"$inc": {"balance_ngn": body.amount_ngn, "total_won": body.amount_ngn},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    tx = {
        "id": new_id(), "user_id": user_id, "type": "winning",
        "amount_ngn": body.amount_ngn, "balance_after": new_balance,
        "reference": body.payment_reference,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.wallet_transactions.insert_one(tx)
    tx.pop("_id", None)
    return {"ok": True, "balance_ngn": new_balance, "transaction": tx}


@router.post("/withdraw")
async def request_withdrawal(body: WithdrawIn, user: dict = Depends(a.get_current_user)):
    """User submits a withdrawal request. Funds are escrowed (`balance_ngn`
    deducted, `pending_withdrawals` incremented) and a row is added to
    `withdrawal_requests` for an admin to process.

    Open to all countries. No KYC; we contact winners post-tournament.
    Method options:
      • `bank_ngn`   — Nigerian local transfer.
      • `usdt`/`btc` — crypto address.
      • `paypal`     — PayPal email (most international users).
      • `wise`       — Wise / bank wire (USD).
    """
    db = get_db()
    w = await _ensure_wallet(user["id"])
    if (w.get("balance_ngn") or 0) < body.amount_ngn:
        raise HTTPException(status_code=402, detail="Insufficient wallet balance")

    # Escrow funds — move balance into pending.
    new_balance = (w.get("balance_ngn") or 0) - body.amount_ngn
    await db.user_wallets.update_one(
        {"user_id": user["id"]},
        {"$inc": {"balance_ngn": -body.amount_ngn, "pending_withdrawals_ngn": body.amount_ngn},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    req_id = new_id()
    await db.withdrawal_requests.insert_one({
        "id": req_id,
        "user_id": user["id"],
        "amount_ngn": body.amount_ngn,
        "method": body.method,
        "destination": body.destination,
        "country_code": body.country_code or user.get("country_code"),
        "status": "pending",   # pending → approved → paid (or rejected → refunds)
        "notes": body.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    tx = {
        "id": new_id(), "user_id": user["id"], "type": "withdrawal",
        "amount_ngn": -body.amount_ngn, "balance_after": new_balance,
        "reference": req_id,
        "metadata": {"method": body.method, "country_code": body.country_code},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.wallet_transactions.insert_one(tx)
    tx.pop("_id", None)
    return {
        "ok": True,
        "request_id": req_id,
        "balance_ngn": new_balance,
        "status": "pending",
        "message": "Your withdrawal is queued. Winners are contacted within 7 days after the tournament finals.",
    }


@router.get("/withdrawals")
async def my_withdrawals(user: dict = Depends(a.get_current_user)):
    """List the current user's withdrawal history."""
    db = get_db()
    rows = await db.withdrawal_requests.find(
        {"user_id": user["id"]}, {"_id": 0},
    ).sort("created_at", -1).limit(50).to_list(length=50)
    return {"withdrawals": rows}
