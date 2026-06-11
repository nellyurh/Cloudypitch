"""PocketFi — Nigerian Virtual Dynamic Account integration.

Customer-facing flow:
  1) User opens "Deposit (NGN)" and enters an amount → frontend POSTs `/api/payments/pocketfi/dynamic-account`.
  2) Backend calls PocketFi `POST /api/v1/virtual-accounts/create` with `type=dynamic` + amount,
     persists the returned bank account(s) in `ngn_deposits`, and returns banks[] to the FE.
  3) User transfers the amount via mobile banking. PocketFi posts a webhook to
     `/api/webhooks/pocketfi`. We verify SHA-512 HMAC, then credit the wallet (NGN).

Required env vars (admin must populate /app/backend/.env):
  POCKETFI_SECRET_KEY    -- "Secret Key" from PocketFi dashboard → Settings → API Keys.
  POCKETFI_BUSINESS_ID   -- Your PocketFi businessId (also from dashboard).
  POCKETFI_BASE_URL      -- defaults to https://api.pocketfi.ng/api/v1 (use /api/test for sandbox).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

import auth as a
from db import get_db
from models import new_id

router = APIRouter(prefix="/api/payments/pocketfi", tags=["payments:pocketfi"])
webhook_router = APIRouter(prefix="/api/webhooks/pocketfi", tags=["webhooks:pocketfi"])

POCKETFI_SECRET_KEY = os.environ.get("POCKETFI_SECRET_KEY", "")  # used to verify inbound webhooks (HMAC-SHA512)
POCKETFI_PUBLIC_KEY = os.environ.get("POCKETFI_PUBLIC_KEY", "")  # used as Authorization Bearer for outbound API calls
POCKETFI_BUSINESS_ID = os.environ.get("POCKETFI_BUSINESS_ID", "")
POCKETFI_BASE_URL = os.environ.get("POCKETFI_BASE_URL", "https://api.pocketfi.ng/api/v1")

ALLOWED_BANKS = {"saveheaven", "paga", "kuda", "9psb", "palmpay"}

log = logging.getLogger("payments.pocketfi")


class PocketFiAccountIn(BaseModel):
    amount_ngn: int = Field(ge=100, le=10_000_000, description="Amount in NGN")
    bank: str = Field(default="kuda")
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    phone: str = Field(min_length=8, max_length=20)
    email: EmailStr
    nin: Optional[str] = Field(default=None, max_length=11)
    bvn: Optional[str] = Field(default=None, max_length=11)


@router.get("/config")
async def pocketfi_config():
    """Frontend uses this to know whether PocketFi is wired up."""
    return {
        "configured": bool(POCKETFI_PUBLIC_KEY and POCKETFI_SECRET_KEY and POCKETFI_BUSINESS_ID),
        "currency": "NGN",
        "banks": sorted(ALLOWED_BANKS),
    }


@router.post("/dynamic-account")
async def create_dynamic_account(body: PocketFiAccountIn, user: dict = Depends(a.get_current_user)):
    """Create a one-time virtual account locked to `body.amount_ngn`.

    Returns `banks[]` — the FE shows account number + bank name to the user for transfer.
    """
    if not (POCKETFI_PUBLIC_KEY and POCKETFI_SECRET_KEY and POCKETFI_BUSINESS_ID):
        raise HTTPException(status_code=503, detail="PocketFi not configured. Set POCKETFI_PUBLIC_KEY + POCKETFI_SECRET_KEY + POCKETFI_BUSINESS_ID in backend env.")
    bank = (body.bank or "kuda").lower()
    if bank not in ALLOWED_BANKS:
        raise HTTPException(status_code=400, detail=f"bank must be one of {sorted(ALLOWED_BANKS)}")
    if bank == "palmpay" and not (body.nin or body.bvn):
        raise HTTPException(status_code=400, detail="PalmPay accounts require KYC: provide nin OR bvn.")

    payload: dict = {
        "first_name": body.first_name,
        "last_name": body.last_name,
        "phone": body.phone,
        "email": body.email,
        "amount": str(body.amount_ngn),
        "type": "dynamic",
        "businessId": POCKETFI_BUSINESS_ID,
        "bank": bank,
    }
    if body.nin:
        payload["nin"] = body.nin
    if body.bvn:
        payload["bvn"] = body.bvn

    # PocketFi has had intermittent 500s on individual banks during the WC ramp-up.
    # Retry once with a fallback bank when the chosen bank errors so users can
    # still deposit. Order tuned for highest uptime: kuda → providus → wema → vfd.
    FALLBACK_BANKS = ["kuda", "providus", "wema", "vfd"]
    tried_banks = [bank] + [b for b in FALLBACK_BANKS if b != bank and b in ALLOWED_BANKS]
    last_err: str | None = None
    resp = None

    for try_bank in tried_banks[:3]:  # cap at 3 tries
        payload["bank"] = try_bank
        try:
            async with httpx.AsyncClient(
                base_url=POCKETFI_BASE_URL,
                headers={
                    "Authorization": f"Bearer {POCKETFI_PUBLIC_KEY}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=httpx.Timeout(15.0, connect=10.0),
            ) as client:
                resp = await client.post("/virtual-accounts/create", json=payload)
        except httpx.TimeoutException:
            last_err = f"{try_bank}: timeout"
            log.warning(f"PocketFi timeout on {try_bank}")
            continue
        except httpx.HTTPError as e:
            last_err = f"{try_bank}: {e}"
            log.warning(f"PocketFi network error on {try_bank}: {e}")
            continue

        if resp.status_code < 400:
            break
        # 5xx → try next bank; 4xx → fail immediately (likely bad input).
        if resp.status_code >= 500:
            last_err = f"{try_bank}: upstream {resp.status_code}"
            log.warning(f"PocketFi {resp.status_code} on {try_bank}: {resp.text[:200]}")
            continue
        # 4xx — surface to user
        log.warning(f"PocketFi {resp.status_code} on {try_bank}: {resp.text[:200]}")
        raise HTTPException(status_code=502, detail=f"PocketFi error: {resp.text[:200]}")

    if resp is None or resp.status_code >= 400:
        # All banks failed — guide user to crypto fallback.
        raise HTTPException(
            status_code=503,
            detail=(
                "PocketFi's NGN deposit service is temporarily down. "
                "Please use the Crypto (Trybit) tab to deposit instead, or try again in a few minutes. "
                f"(diagnostic: {last_err})"
            ),
        )
    data = resp.json() if resp.text else {}
    if not data.get("status"):
        raise HTTPException(status_code=502, detail=f"PocketFi rejected: {data}")

    banks = data.get("banks") or []
    if not banks:
        raise HTTPException(status_code=502, detail="PocketFi returned no bank accounts.")

    db = get_db()
    deposit_id = new_id()
    primary = banks[0]
    # PocketFi includes a per-bank `reference` (e.g. "PFI|7001096034") that we save and use
    # to match incoming webhooks reliably (replaces regex-on-description guessing).
    payment_reference = primary.get("reference") or ""
    full_name = f"{body.first_name} {body.last_name}".strip()
    doc = {
        "id": deposit_id,
        "user_id": user["id"],
        "provider": "pocketfi",
        "status": "pending",
        "amount_ngn": body.amount_ngn,
        "bank": primary.get("bankName"),
        "account_number": primary.get("accountNumber"),
        "account_name": primary.get("accountName") or full_name,
        "payment_reference": payment_reference,
        "all_banks": banks,
        "customer": {"first_name": body.first_name, "last_name": body.last_name, "email": body.email, "phone": body.phone},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ngn_deposits.insert_one(doc)

    # Ensure the FE always has an `accountName` to display (PocketFi sometimes omits it).
    for b in banks:
        if not b.get("accountName"):
            b["accountName"] = full_name

    return {
        "deposit_id": deposit_id,
        "amount_ngn": body.amount_ngn,
        "banks": banks,
        "expires_in_seconds": 1800,  # PocketFi dynamic accounts are typically short-lived; tune per business
    }


@router.get("/deposit/{deposit_id}")
async def get_deposit(deposit_id: str, user: dict = Depends(a.get_current_user)):
    """Frontend polls this while waiting for the customer to fund the VA."""
    db = get_db()
    doc = await db.ngn_deposits.find_one({"id": deposit_id, "user_id": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Deposit not found")
    return {"deposit": doc}


# ───────────────────────────── Webhook ─────────────────────────────


# Common header names + algorithms used by Nigerian payment providers. PocketFi's
# exact spec is not documented publicly — we therefore try EVERY common variant.
# If ANY combination matches, the webhook is authentic. If NONE match, we reject
# with 400 and persist the failed delivery (with all headers redacted-safe) to
# `pocketfi_webhook_failures` so admins can identify the real header name and
# tighten this list in the future.
_CANDIDATE_HEADER_NAMES = (
    "Pocketfi-Signature", "X-Pocketfi-Signature", "X-PocketFi-Signature",
    "pocketfi-signature", "x-pocketfi-signature",
    "X-Signature", "Signature", "X-Webhook-Signature", "Webhook-Signature",
    "X-Hub-Signature", "X-Hub-Signature-256", "X-Hub-Signature-512",
    "HTTP_POCKETFI_SIGNATURE",
)
_CANDIDATE_ALGOS = (
    ("sha512", hashlib.sha512),
    ("sha256", hashlib.sha256),
)


def _verify_pocketfi_signature(secret: str, raw_body: bytes, headers) -> tuple[bool, str, str, str]:
    """Try every (header, algorithm, encoding) combination. Returns
    (verified, header_name, algo_name, encoding) for the match — or
    (False, "", "", "") if nothing matched. Constant-time digest comparison.
    """
    import base64
    secret_b = secret.encode("utf-8")
    for hdr in _CANDIDATE_HEADER_NAMES:
        raw_sig = headers.get(hdr) or headers.get(hdr.lower())
        if not raw_sig:
            continue
        # Strip common provider prefixes like `sha512=` / `sha256=`
        candidate_digests: list[str] = []
        s = raw_sig.strip()
        for pfx in ("sha512=", "sha256=", "sha1=", "v1=", "v1,"):
            if s.lower().startswith(pfx):
                candidate_digests.append(s[len(pfx):])
                break
        candidate_digests.append(s)  # also try the raw value as-is

        for algo_name, h in _CANDIDATE_ALGOS:
            mac = hmac.new(secret_b, raw_body, h)
            expected_hex = mac.hexdigest()
            expected_b64 = base64.b64encode(mac.digest()).decode("ascii")
            for cand in candidate_digests:
                if hmac.compare_digest(expected_hex, cand):
                    return True, hdr, algo_name, "hex"
                if hmac.compare_digest(expected_b64, cand):
                    return True, hdr, algo_name, "base64"
    return False, "", "", ""


@webhook_router.post("")
async def pocketfi_webhook(request: Request):
    """Receive payment notifications from PocketFi and credit the user's wallet.

    Tries every common HMAC header/algo/encoding combination (PocketFi's exact
    spec isn't public). On verification failure → 400 + payload persisted to
    `pocketfi_webhook_failures` so we can post-mortem from the admin panel.
    """
    if not POCKETFI_SECRET_KEY:
        raise HTTPException(status_code=503, detail="PocketFi webhook secret not configured.")

    raw = await request.body()

    verified, hdr_used, algo_used, enc_used = _verify_pocketfi_signature(
        POCKETFI_SECRET_KEY, raw, request.headers,
    )
    if not verified:
        log.warning("PocketFi webhook: invalid signature — no candidate combination matched")
        # Persist a failure record so an admin can replay manually if needed.
        # We DO NOT credit any wallet here — the security gate stays closed.
        try:
            await get_db().pocketfi_webhook_failures.insert_one({
                "id": new_id(),
                "received_at": datetime.now(timezone.utc).isoformat(),
                "raw_body": raw.decode("utf-8", errors="replace"),
                "headers": {k: v for k, v in request.headers.items()
                            if "cookie" not in k.lower() and "authorization" not in k.lower()},
                "reason": "invalid_signature_all_candidates",
            })
        except Exception as e:
            log.warning(f"PocketFi webhook: could not persist failure: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    log.info(f"PocketFi webhook verified via header={hdr_used} algo={algo_used} enc={enc_used}")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    order = (payload.get("order") or {})
    txn = (payload.get("transaction") or {})
    reference = txn.get("reference")
    settlement_amount = order.get("settlement_amount")
    gross_amount = order.get("amount")
    description = order.get("description") or ""

    if not reference:
        raise HTTPException(status_code=400, detail="Missing transaction.reference")

    db = get_db()
    # Idempotency: drop duplicates by reference
    existing_tx = await db.wallet_transactions.find_one({"reference": reference, "type": "deposit"})
    if existing_tx:
        log.info(f"PocketFi webhook: duplicate reference {reference}")
        return {"status": "ok", "duplicate": True}

    # Map back to a pending deposit. Priority:
    #   1) Exact match on `payment_reference` (which PocketFi forwards in transaction.reference or order.description)
    #   2) Account number lookup
    #   3) Amount + pending status fallback
    deposit = None
    if reference:
        deposit = await db.ngn_deposits.find_one(
            {"payment_reference": reference, "status": "pending"}, {"_id": 0}
        )
    if not deposit and description:
        # Sometimes PocketFi forwards the reference inside description
        deposit = await db.ngn_deposits.find_one(
            {"payment_reference": description, "status": "pending"}, {"_id": 0}
        )
    if not deposit and description:
        # Last-resort: account-name match. Escape the description to avoid regex injection.
        safe = re.escape(description)
        deposit = await db.ngn_deposits.find_one(
            {"status": "pending", "$or": [
                {"account_name": {"$regex": safe, "$options": "i"}},
                {"customer.first_name": {"$regex": safe, "$options": "i"}},
            ]},
            {"_id": 0},
        )
    if not deposit and gross_amount:
        deposit = await db.ngn_deposits.find_one(
            {"status": "pending", "amount_ngn": int(float(gross_amount))},
            {"_id": 0},
        )

    if not deposit:
        log.warning(f"PocketFi webhook: no matching deposit for ref={reference} amount={gross_amount}")
        # Still acknowledge 200 so PocketFi doesn't retry indefinitely
        return {"status": "ok", "matched": False}

    credit_amount = int(float(settlement_amount if settlement_amount is not None else gross_amount))

    # Credit the user's wallet (NGN)
    now = datetime.now(timezone.utc).isoformat()
    res = await db.user_wallets.update_one(
        {"user_id": deposit["user_id"]},
        {
            "$inc": {"balance_ngn": credit_amount, "total_deposited": credit_amount},
            "$set": {"updated_at": now},
        },
        upsert=True,
    )
    # If wallet doesn't exist yet, the upsert created it; ensure base fields are seeded.
    if res.upserted_id:
        await db.user_wallets.update_one(
            {"_id": res.upserted_id},
            {"$set": {"id": new_id(), "user_id": deposit["user_id"], "total_won": 0, "total_spent": 0, "kyc_verified": False, "bank_account": None}},
        )

    wallet = await db.user_wallets.find_one({"user_id": deposit["user_id"]}, {"_id": 0})
    new_balance = (wallet or {}).get("balance_ngn", credit_amount)

    await db.wallet_transactions.insert_one({
        "id": new_id(),
        "user_id": deposit["user_id"],
        "type": "deposit",
        "amount_ngn": credit_amount,
        "balance_after": new_balance,
        "reference": reference,
        "provider": "pocketfi",
        "gross_amount": gross_amount,
        "fee": order.get("fee"),
        "description": description,
        "created_at": now,
    })

    await db.ngn_deposits.update_one(
        {"id": deposit["id"]},
        {"$set": {
            "status": "credited",
            "credited_amount_ngn": credit_amount,
            "transaction_reference": reference,
            "credited_at": now,
        }},
    )

    log.info(f"PocketFi deposit credited: user={deposit['user_id']} amount={credit_amount} ref={reference}")
    return {"status": "ok", "credited": True, "amount_ngn": credit_amount}
