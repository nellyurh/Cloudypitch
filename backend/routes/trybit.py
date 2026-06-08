"""Trybit (CryptoCloud) — Crypto deposits via hosted-invoice checkout.

Customer-facing flow:
  1) User picks "Crypto deposit" + amount (USD) → frontend POSTs /api/payments/trybit/invoice.
  2) Backend calls Trybit `POST https://api.trybit.com/v2/invoice/create`, persists the invoice in
     `crypto_invoices`, returns the hosted `pay_url` (link to pay.trybit.com/<uuid>).
  3) Customer pays on Trybit's hosted page in their chosen coin.
  4) Trybit fires a postback (JWT) to /api/webhooks/trybit. We decode with HS256 + SECRET_KEY,
     verify status="paid", and credit the wallet (NGN, using admin-set USD→NGN rate).

Required env vars:
  TRYBIT_API_KEY      -- "API key" from Trybit dashboard → Project settings.
  TRYBIT_SHOP_ID      -- "SHOP_ID" from same panel (per project).
  TRYBIT_SECRET_KEY   -- "SECRET_KEY" used to sign/verify postback JWTs.
  TRYBIT_BASE_URL     -- defaults to https://api.trybit.com/v2
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx
import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

import auth as a
from db import get_db
from models import new_id

router = APIRouter(prefix="/api/payments/trybit", tags=["payments:trybit"])
webhook_router = APIRouter(prefix="/api/webhooks/trybit", tags=["webhooks:trybit"])

TRYBIT_API_KEY = os.environ.get("TRYBIT_API_KEY", "")
TRYBIT_SHOP_ID = os.environ.get("TRYBIT_SHOP_ID", "")
TRYBIT_SECRET_KEY = os.environ.get("TRYBIT_SECRET_KEY", "")
TRYBIT_BASE_URL = os.environ.get("TRYBIT_BASE_URL", "https://api.trybit.com/v2")

# Sensible default for the customer's "Available payment currencies" list.
DEFAULT_PAY_CURRENCIES = [
    "USDT_TRC20", "USDT_ERC20", "USDT_BSC", "USDT_SOL",
    "BTC", "ETH", "TRX", "SOL", "BNB", "USDC_ERC20", "USDC_TRC20",
]

log = logging.getLogger("payments.trybit")


class TrybitInvoiceIn(BaseModel):
    amount_usd: float = Field(gt=0, le=100_000.0, description="Amount in USD (Trybit will offer customer-selected coins)")
    available_currencies: Optional[list[str]] = None
    email: Optional[str] = None


@router.get("/config")
async def trybit_config():
    return {
        "configured": bool(TRYBIT_API_KEY and TRYBIT_SHOP_ID and TRYBIT_SECRET_KEY),
        "currency": "USD",
        "currencies": DEFAULT_PAY_CURRENCIES,
    }


async def _get_usd_to_ngn() -> float:
    """Resolve the admin-configured USD→NGN rate. Defaults to 1500."""
    db = get_db()
    doc = await db.app_settings.find_one({"id": "site"}, {"_id": 0}) or {}
    rate = doc.get("ngn_per_usd")
    try:
        rate = float(rate)
    except (TypeError, ValueError):
        rate = 1500.0
    return rate if rate > 0 else 1500.0


@router.post("/invoice")
async def create_invoice(body: TrybitInvoiceIn, request: Request, user: dict = Depends(a.get_current_user)):
    """Create a hosted Trybit invoice and persist a `crypto_invoices` row.

    Returns the `pay_url` for the frontend to redirect/open.
    """
    if not (TRYBIT_API_KEY and TRYBIT_SHOP_ID):
        raise HTTPException(status_code=503, detail="Trybit not configured. Set TRYBIT_API_KEY + TRYBIT_SHOP_ID + TRYBIT_SECRET_KEY in backend env.")

    order_id = f"{user['id']}:{new_id()[:12]}"

    payload: dict = {
        "amount": float(body.amount_usd),
        "currency": "USD",
        "shop_id": TRYBIT_SHOP_ID,
        "order_id": order_id,
        "add_fields": {
            "available_currencies": body.available_currencies or DEFAULT_PAY_CURRENCIES,
            "time_to_pay": {"hours": 1, "minutes": 0},
        },
    }
    if body.email:
        payload["email"] = body.email

    try:
        async with httpx.AsyncClient(
            base_url=TRYBIT_BASE_URL,
            headers={
                "Authorization": f"Token {TRYBIT_API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=httpx.Timeout(20.0, connect=10.0),
        ) as client:
            resp = await client.post("/invoice/create", json=payload)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Trybit timed out — please retry.")
    except httpx.HTTPError as e:
        log.warning(f"Trybit network error: {e}")
        raise HTTPException(status_code=502, detail="Trybit network error")

    if resp.status_code >= 400:
        log.warning(f"Trybit {resp.status_code}: {resp.text[:200]}")
        raise HTTPException(status_code=502, detail=f"Trybit error: {resp.text[:200]}")
    data = resp.json() if resp.text else {}
    if data.get("status") != "success":
        raise HTTPException(status_code=502, detail=f"Trybit rejected: {data}")

    result = data.get("result") or {}
    invoice_uuid = result.get("uuid") or result.get("invoice_id")
    pay_url = result.get("link")
    if pay_url and not pay_url.startswith("http"):
        pay_url = f"https://{pay_url}"

    if not (invoice_uuid and pay_url):
        raise HTTPException(status_code=502, detail=f"Trybit response missing uuid/link: {result}")

    db = get_db()
    invoice_doc = {
        "id": new_id(),
        "user_id": user["id"],
        "provider": "trybit",
        "invoice_uuid": invoice_uuid,
        "order_id": order_id,
        "amount_usd": float(body.amount_usd),
        "pay_url": pay_url,
        "status": "pending",
        "raw_create_response": result,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.crypto_invoices.insert_one(invoice_doc)

    return {
        "invoice_uuid": invoice_uuid,
        "order_id": order_id,
        "amount_usd": body.amount_usd,
        "pay_url": pay_url,
        "expires_in_seconds": 3600,
    }


@router.get("/invoice/{invoice_uuid}")
async def get_invoice(invoice_uuid: str, user: dict = Depends(a.get_current_user)):
    db = get_db()
    doc = await db.crypto_invoices.find_one(
        {"invoice_uuid": invoice_uuid, "user_id": user["id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"invoice": doc}


# ───────────────────────────── Webhook (postback) ─────────────────────────────


@webhook_router.post("")
async def trybit_webhook(request: Request):
    """Receive postback from Trybit and credit user wallet when status=paid.

    Trybit signs postbacks as JWTs using the project's SECRET_KEY (HS256).
    The JWT can arrive as:
      - a form field `token` (form-encoded body), or
      - a JSON field `token`, or
      - an `Authorization: Bearer <token>` header.
    Inside the JWT payload, look for `status` and identifiers (`uuid` / `order_id`).
    """
    if not TRYBIT_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Trybit secret key not configured.")

    # Extract the token from any of the supported locations
    token: Optional[str] = None
    content_type = (request.headers.get("content-type") or "").lower()
    raw = await request.body()
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        try:
            form = await request.form()
            token = form.get("token")
        except Exception:
            token = None
    if not token:
        try:
            body_json = await request.json() if raw else {}
            if isinstance(body_json, dict):
                token = body_json.get("token")
        except Exception:
            token = None
    if not token:
        auth_h = request.headers.get("authorization", "")
        if auth_h.lower().startswith("bearer "):
            token = auth_h.split(" ", 1)[1].strip()

    # Fallback: also accept a non-signed payload sent via JSON `status` (for sandboxes that don't sign)
    try:
        decoded: dict = pyjwt.decode(token, TRYBIT_SECRET_KEY, algorithms=["HS256"]) if token else None
    except pyjwt.InvalidSignatureError:
        log.warning("Trybit webhook: invalid signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError as e:
        log.warning(f"Trybit webhook: invalid token: {e}")
        raise HTTPException(status_code=400, detail="Invalid token")

    if not decoded or not isinstance(decoded, dict):
        raise HTTPException(status_code=400, detail="Missing token")

    status = (decoded.get("status") or decoded.get("invoice_status") or "").lower()
    invoice_uuid = decoded.get("uuid") or decoded.get("invoice_id") or decoded.get("invoice_uuid")
    order_id = decoded.get("order_id")
    amount_usd_claim = decoded.get("amount_usd") or decoded.get("amount_in_fiat") or decoded.get("amount")

    db = get_db()

    # Locate the invoice in our DB
    query: dict = {"$or": []}
    if invoice_uuid:
        query["$or"].append({"invoice_uuid": invoice_uuid})
    if order_id:
        query["$or"].append({"order_id": order_id})
    if not query["$or"]:
        raise HTTPException(status_code=400, detail="Missing invoice identifier")
    invoice = await db.crypto_invoices.find_one(query, {"_id": 0})
    if not invoice:
        log.warning(f"Trybit webhook: unknown invoice uuid={invoice_uuid} order_id={order_id}")
        return {"status": "ok", "matched": False}

    # Idempotency
    if invoice.get("status") == "paid":
        return {"status": "ok", "duplicate": True}

    # Persist non-paid states (partial/canceled) for visibility
    if status != "paid":
        await db.crypto_invoices.update_one(
            {"id": invoice["id"]},
            {"$set": {"status": status or "unknown", "last_webhook_at": datetime.now(timezone.utc).isoformat()}},
        )
        return {"status": "ok", "trybit_status": status}

    # Convert USD → NGN at the admin-set rate; credit wallet in NGN.
    rate = await _get_usd_to_ngn()
    amount_usd = float(amount_usd_claim or invoice.get("amount_usd") or 0)
    credit_ngn = int(round(amount_usd * rate))

    now = datetime.now(timezone.utc).isoformat()

    res = await db.user_wallets.update_one(
        {"user_id": invoice["user_id"]},
        {
            "$inc": {"balance_ngn": credit_ngn, "total_deposited": credit_ngn},
            "$set": {"updated_at": now},
        },
        upsert=True,
    )
    if res.upserted_id:
        await db.user_wallets.update_one(
            {"_id": res.upserted_id},
            {"$set": {"id": new_id(), "user_id": invoice["user_id"], "total_won": 0, "total_spent": 0, "kyc_verified": False, "bank_account": None}},
        )

    wallet = await db.user_wallets.find_one({"user_id": invoice["user_id"]}, {"_id": 0})
    new_balance = (wallet or {}).get("balance_ngn", credit_ngn)

    await db.wallet_transactions.insert_one({
        "id": new_id(),
        "user_id": invoice["user_id"],
        "type": "deposit",
        "amount_ngn": credit_ngn,
        "balance_after": new_balance,
        "reference": invoice_uuid or order_id,
        "provider": "trybit",
        "amount_usd": amount_usd,
        "usd_to_ngn_rate": rate,
        "created_at": now,
    })

    await db.crypto_invoices.update_one(
        {"id": invoice["id"]},
        {"$set": {
            "status": "paid",
            "credited_amount_ngn": credit_ngn,
            "credited_amount_usd": amount_usd,
            "usd_to_ngn_rate": rate,
            "credited_at": now,
        }},
    )

    log.info(f"Trybit deposit credited: user={invoice['user_id']} usd={amount_usd} ngn={credit_ngn}")
    return {"status": "ok", "credited": True, "amount_ngn": credit_ngn, "amount_usd": amount_usd}
