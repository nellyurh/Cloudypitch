"""Compliance: 18+ age gate, self-imposed spending caps, self-exclusion.
Spec: ₦5K/day, ₦20K/month defaults · 24h delay on raising caps · self-exclude any time."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import auth as a
from db import get_db
from models import new_id

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


DEFAULT_DAILY_CAP_NGN = 5_000
DEFAULT_MONTHLY_CAP_NGN = 20_000
CAP_RAISE_COOLDOWN_HOURS = 24


class AgeGateIn(BaseModel):
    date_of_birth: str  # YYYY-MM-DD
    confirm_18_plus: bool = True


class CapsIn(BaseModel):
    daily_cap_ngn: int = Field(ge=0, le=10_000_000)
    monthly_cap_ngn: int = Field(ge=0, le=100_000_000)


class SelfExcludeIn(BaseModel):
    excluded: bool
    until: str | None = None  # ISO date when self-exclusion ends; None = permanent


async def _get_profile(user_id: str) -> dict:
    db = get_db()
    p = await db.compliance_profiles.find_one({"user_id": user_id}, {"_id": 0})
    if not p:
        p = {
            "id": new_id(), "user_id": user_id,
            "age_verified": False, "date_of_birth": None,
            "daily_cap_ngn": DEFAULT_DAILY_CAP_NGN,
            "monthly_cap_ngn": DEFAULT_MONTHLY_CAP_NGN,
            "caps_pending": None,
            "caps_pending_effective_at": None,
            "self_excluded": False, "self_excluded_until": None,
            "kyc_verified": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.compliance_profiles.insert_one(p)
    p.pop("_id", None)
    return p


@router.get("/me")
async def my_compliance(user: dict = Depends(a.get_current_user)):
    p = await _get_profile(user["id"])
    return {"profile": p, "defaults": {
        "daily_cap_ngn": DEFAULT_DAILY_CAP_NGN,
        "monthly_cap_ngn": DEFAULT_MONTHLY_CAP_NGN,
        "cap_raise_cooldown_hours": CAP_RAISE_COOLDOWN_HOURS,
    }}


@router.post("/age-gate")
async def age_gate(body: AgeGateIn, user: dict = Depends(a.get_current_user)):
    """Verify the user is 18+ from a confirmed DOB. Stores DOB + sets age_verified=True."""
    db = get_db()
    try:
        dob = datetime.strptime(body.date_of_birth, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    today = datetime.now(timezone.utc).date()
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if years < 18:
        raise HTTPException(status_code=403, detail="You must be 18 or older to access real-money features.")
    if not body.confirm_18_plus:
        raise HTTPException(status_code=400, detail="You must confirm you are 18+")
    await _get_profile(user["id"])
    await db.compliance_profiles.update_one(
        {"user_id": user["id"]},
        {"$set": {
            "age_verified": True,
            "date_of_birth": body.date_of_birth,
            "age_verified_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"ok": True, "age_verified": True, "years": years}


@router.post("/caps")
async def update_caps(body: CapsIn, user: dict = Depends(a.get_current_user)):
    """Update spending caps. Lowering takes effect immediately;
    raising requires a 24-hour cooldown (stored in `caps_pending`)."""
    db = get_db()
    p = await _get_profile(user["id"])
    raising = (body.daily_cap_ngn > p.get("daily_cap_ngn", DEFAULT_DAILY_CAP_NGN)
               or body.monthly_cap_ngn > p.get("monthly_cap_ngn", DEFAULT_MONTHLY_CAP_NGN))
    if raising:
        effective_at = (datetime.now(timezone.utc) + timedelta(hours=CAP_RAISE_COOLDOWN_HOURS)).isoformat()
        await db.compliance_profiles.update_one(
            {"user_id": user["id"]},
            {"$set": {
                "caps_pending": {"daily_cap_ngn": body.daily_cap_ngn, "monthly_cap_ngn": body.monthly_cap_ngn},
                "caps_pending_effective_at": effective_at,
            }},
        )
        return {"ok": True, "effective_at": effective_at, "pending": True,
                "message": f"New higher cap takes effect in {CAP_RAISE_COOLDOWN_HOURS}h (anti-impulse delay)."}
    # Lowering — immediate
    await db.compliance_profiles.update_one(
        {"user_id": user["id"]},
        {"$set": {
            "daily_cap_ngn": body.daily_cap_ngn,
            "monthly_cap_ngn": body.monthly_cap_ngn,
            "caps_pending": None, "caps_pending_effective_at": None,
        }},
    )
    return {"ok": True, "applied_immediately": True}


@router.post("/self-exclude")
async def self_exclude(body: SelfExcludeIn, user: dict = Depends(a.get_current_user)):
    """Toggle self-exclusion. While excluded, real-money flows are blocked."""
    db = get_db()
    await _get_profile(user["id"])
    await db.compliance_profiles.update_one(
        {"user_id": user["id"]},
        {"$set": {
            "self_excluded": body.excluded,
            "self_excluded_until": body.until,
            "self_excluded_at": datetime.now(timezone.utc).isoformat() if body.excluded else None,
        }},
    )
    return {"ok": True, "self_excluded": body.excluded}


async def check_can_spend(user_id: str, amount_ngn: int) -> tuple[bool, str | None]:
    """Helper used by purchase/recharge endpoints to enforce caps before charging."""
    db = get_db()
    p = await _get_profile(user_id)
    if p.get("self_excluded"):
        until = p.get("self_excluded_until")
        if not until or until > datetime.now(timezone.utc).isoformat():
            return False, "Self-exclusion is active. No real-money transactions allowed."
    if not p.get("age_verified"):
        return False, "Age verification required (18+) before spending."

    # Apply pending raise if cooldown passed
    pending_eff = p.get("caps_pending_effective_at")
    if pending_eff and pending_eff <= datetime.now(timezone.utc).isoformat() and p.get("caps_pending"):
        pending = p["caps_pending"]
        await db.compliance_profiles.update_one(
            {"user_id": user_id},
            {"$set": {
                "daily_cap_ngn": pending.get("daily_cap_ngn", p["daily_cap_ngn"]),
                "monthly_cap_ngn": pending.get("monthly_cap_ngn", p["monthly_cap_ngn"]),
                "caps_pending": None, "caps_pending_effective_at": None,
            }},
        )
        p["daily_cap_ngn"] = pending.get("daily_cap_ngn", p["daily_cap_ngn"])
        p["monthly_cap_ngn"] = pending.get("monthly_cap_ngn", p["monthly_cap_ngn"])

    # Daily / monthly aggregations from wallet_transactions
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    daily_spend = await db.wallet_transactions.aggregate([
        {"$match": {"user_id": user_id, "type": {"$in": ["purchase", "recharge"]},
                    "created_at": {"$gte": day_start}}},
        {"$group": {"_id": None, "total": {"$sum": {"$abs": "$amount_ngn"}}}},
    ]).to_list(length=1)
    monthly_spend = await db.wallet_transactions.aggregate([
        {"$match": {"user_id": user_id, "type": {"$in": ["purchase", "recharge"]},
                    "created_at": {"$gte": month_start}}},
        {"$group": {"_id": None, "total": {"$sum": {"$abs": "$amount_ngn"}}}},
    ]).to_list(length=1)
    daily_total = (daily_spend[0]["total"] if daily_spend else 0) + amount_ngn
    monthly_total = (monthly_spend[0]["total"] if monthly_spend else 0) + amount_ngn
    if daily_total > p["daily_cap_ngn"]:
        return False, f"Daily spending cap reached (₦{p['daily_cap_ngn']:,})."
    if monthly_total > p["monthly_cap_ngn"]:
        return False, f"Monthly spending cap reached (₦{p['monthly_cap_ngn']:,})."
    return True, None


@router.get("/can-spend")
async def can_spend(amount_ngn: int, user: dict = Depends(a.get_current_user)):
    """Pre-flight check from the frontend before opening the payment modal."""
    ok, reason = await check_can_spend(user["id"], amount_ngn)
    return {"ok": ok, "reason": reason}
