"""Email verification + password reset (token-based) + KYC for bank withdrawals.

Email sending is OPTIONAL — if no provider keys are set, the token is returned in
the API response so dev/admin flows can complete locally. In production wire a
Resend/SendGrid call inside _send_email().
"""
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

import auth as a
from db import get_db
from models import new_id

router = APIRouter(prefix="/api/auth-extras", tags=["auth-extras"])


VERIFY_TOKEN_TTL_HOURS = 48
RESET_TOKEN_TTL_HOURS = 2


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _new_token() -> str:
    return secrets.token_urlsafe(32)


async def _send_email(to_email: str, subject: str, body: str, kind: str = "info") -> bool:
    """Stub. Plug in Resend / SendGrid here. Returns True if dispatched."""
    if not os.environ.get("EMAIL_PROVIDER_KEY"):
        return False
    # TODO: actual provider call
    return True


# ---------------- Email verification ----------------
@router.post("/verify/request")
async def request_verification(user: dict = Depends(a.get_current_user)):
    db = get_db()
    if user.get("email_verified"):
        return {"ok": True, "already_verified": True}
    token = _new_token()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=VERIFY_TOKEN_TTL_HOURS)).isoformat()
    await db.email_verification_tokens.insert_one({
        "id": new_id(), "user_id": user["id"], "email": user["email"],
        "token": token, "expires_at": expires_at, "used_at": None,
        "created_at": _now_iso(),
    })
    verify_url = f"{os.environ.get('FRONTEND_URL', '')}/verify-email?token={token}"
    sent = await _send_email(
        user["email"],
        "Verify your Cloudy Pitch email",
        f"Click here to verify: {verify_url}",
        "verify",
    )
    return {
        "ok": True,
        "expires_at": expires_at,
        # Dev fallback — token returned only when no email provider is configured
        "dev_token": None if sent else token,
        "dev_url": None if sent else f"/verify-email?token={token}",
    }


class VerifyConfirmIn(BaseModel):
    token: str = Field(min_length=20)


@router.post("/verify/confirm")
async def confirm_verification(body: VerifyConfirmIn):
    db = get_db()
    row = await db.email_verification_tokens.find_one({"token": body.token, "used_at": None}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=400, detail="Invalid or already-used token")
    if row["expires_at"] < _now_iso():
        raise HTTPException(status_code=400, detail="Token expired")
    await db.users.update_one({"id": row["user_id"]}, {"$set": {"email_verified": True, "email_verified_at": _now_iso()}})
    await db.email_verification_tokens.update_one({"id": row["id"]}, {"$set": {"used_at": _now_iso()}})
    return {"ok": True}


# ---------------- Password reset ----------------
class ResetRequestIn(BaseModel):
    email: EmailStr


@router.post("/reset/request")
async def request_password_reset(body: ResetRequestIn):
    db = get_db()
    user = await db.users.find_one({"email": body.email.lower().strip()}, {"_id": 0, "id": 1, "email": 1})
    # Never reveal whether the email exists — always return success
    if not user:
        return {"ok": True, "dev_token": None}
    token = _new_token()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=RESET_TOKEN_TTL_HOURS)).isoformat()
    await db.password_reset_tokens.insert_one({
        "id": new_id(), "user_id": user["id"], "email": user["email"],
        "token": token, "expires_at": expires_at, "used_at": None,
        "created_at": _now_iso(),
    })
    reset_url = f"{os.environ.get('FRONTEND_URL', '')}/reset-password?token={token}"
    sent = await _send_email(
        user["email"],
        "Reset your Cloudy Pitch password",
        f"Click here to reset (expires in {RESET_TOKEN_TTL_HOURS}h): {reset_url}",
        "reset",
    )
    return {
        "ok": True,
        "dev_token": None if sent else token,
        "dev_url": None if sent else f"/reset-password?token={token}",
    }


class ResetConfirmIn(BaseModel):
    token: str = Field(min_length=20)
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/reset/confirm")
async def confirm_password_reset(body: ResetConfirmIn):
    db = get_db()
    row = await db.password_reset_tokens.find_one({"token": body.token, "used_at": None}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=400, detail="Invalid or already-used token")
    if row["expires_at"] < _now_iso():
        raise HTTPException(status_code=400, detail="Token expired")
    await db.users.update_one(
        {"id": row["user_id"]},
        {"$set": {
            "password_hash": a.hash_password(body.new_password),
            "password_reset_at": _now_iso(),
            "failed_login_attempts": 0, "locked_until": None,
        }},
    )
    await db.password_reset_tokens.update_one({"id": row["id"]}, {"$set": {"used_at": _now_iso()}})
    # Invalidate other active sessions for this user (force re-login)
    await db.sessions.delete_many({"user_id": row["user_id"]})
    return {"ok": True}


# ---------------- KYC (bank account) ----------------
class KycSubmitIn(BaseModel):
    full_name: str = Field(min_length=4, max_length=120)
    date_of_birth: str
    bank_name: str = Field(max_length=80)
    account_number: str = Field(min_length=8, max_length=20)
    bvn: str | None = None  # Optional Nigeria-specific bank verification number


@router.post("/kyc/submit")
async def submit_kyc(body: KycSubmitIn, user: dict = Depends(a.get_current_user)):
    """User-submitted KYC. Goes to status='pending' until admin approves.
    Required for prize-pool cash withdrawals."""
    db = get_db()
    doc = {
        "user_id": user["id"],
        "full_name": body.full_name, "date_of_birth": body.date_of_birth,
        "bank_name": body.bank_name,
        "account_number_masked": "*" * (len(body.account_number) - 4) + body.account_number[-4:],
        "account_number_full": body.account_number,
        "bvn_provided": bool(body.bvn),
        "status": "pending",
        "submitted_at": _now_iso(),
    }
    await db.kyc_submissions.update_one(
        {"user_id": user["id"]},
        {"$set": doc, "$setOnInsert": {"id": new_id()}},
        upsert=True,
    )
    return {"ok": True, "status": "pending"}


@router.get("/kyc/me")
async def my_kyc(user: dict = Depends(a.get_current_user)):
    db = get_db()
    sub = await db.kyc_submissions.find_one({"user_id": user["id"]}, {"_id": 0, "account_number_full": 0})
    return {"kyc": sub}


class KycReviewIn(BaseModel):
    user_id: str
    approved: bool
    notes: str | None = None


@router.post("/kyc/review")
async def review_kyc(body: KycReviewIn, admin: dict = Depends(a.require_admin)):
    db = get_db()
    upd = {"status": "approved" if body.approved else "rejected", "reviewed_at": _now_iso(), "review_notes": body.notes}
    res = await db.kyc_submissions.update_one({"user_id": body.user_id}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="No submission for that user")
    if body.approved:
        await db.user_wallets.update_one(
            {"user_id": body.user_id},
            {"$set": {"kyc_verified": True, "kyc_verified_at": _now_iso()}},
            upsert=True,
        )
    return {"ok": True}
