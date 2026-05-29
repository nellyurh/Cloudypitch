"""Referral system: invite code, leaderboard, prize pool."""
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

import auth as a
from db import get_db

router = APIRouter(prefix="/api/referrals", tags=["referrals"])


def generate_referral_code(length: int = 8) -> str:
    """Crockford Base32 (no 0/O/I/L confusion). 8 chars = ~32^8 ≈ 1 trillion combos."""
    alphabet = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def ensure_referral_code(user_id: str) -> str:
    """Generate + persist a referral code for a user if they don't have one yet."""
    db = get_db()
    u = await db.users.find_one({"id": user_id}, {"_id": 0, "referral_code": 1})
    if u and u.get("referral_code"):
        return u["referral_code"]
    for _ in range(8):
        code = generate_referral_code()
        clash = await db.users.find_one({"referral_code": code}, {"_id": 0, "id": 1})
        if not clash:
            await db.users.update_one({"id": user_id}, {"$set": {"referral_code": code}})
            return code
    raise HTTPException(status_code=500, detail="Could not generate unique referral code")


@router.get("/me")
async def my_referrals(user: dict = Depends(a.get_current_user)):
    db = get_db()
    code = await ensure_referral_code(user["id"])
    # All referrals I made
    rows = await db.referrals.find({"referrer_user_id": user["id"]}, {"_id": 0}).to_list(length=500)
    # Hydrate with referred-user display name + email-redacted
    referred_ids = [r["referred_user_id"] for r in rows]
    users = await db.users.find(
        {"id": {"$in": referred_ids}},
        {"_id": 0, "id": 1, "display_name": 1, "country_code": 1, "created_at": 1},
    ).to_list(length=500)
    by_id = {u["id"]: u for u in users}
    enriched = []
    for r in rows:
        u = by_id.get(r["referred_user_id"], {})
        enriched.append({
            **r,
            "referred_display_name": u.get("display_name") or "Friend",
            "referred_country_code": u.get("country_code"),
            "referred_joined_at": u.get("created_at"),
        })
    # Totals
    total_credits = sum(r.get("credit_earned_usd_cents", 0) for r in rows)
    total_spend = sum(r.get("referred_spend_usd_cents", 0) for r in rows)
    return {
        "referral_code": code,
        "share_url_template": "/signup?ref={code}",
        "count": len(rows),
        "active_count": sum(1 for r in rows if (r.get("referred_spend_usd_cents") or 0) > 0),
        "total_credits_usd_cents": total_credits,
        "total_referred_spend_usd_cents": total_spend,
        "referrals": sorted(enriched, key=lambda r: -(r.get("credit_earned_usd_cents") or 0)),
    }


@router.get("/leaderboard")
async def leaderboard(limit: int = 50, scope: str = "all_time"):
    """Top referrers by credit earned (10% of referred-user lifetime card spend)."""
    db = get_db()
    pipeline = [
        {"$group": {
            "_id": "$referrer_user_id",
            "total_credits": {"$sum": "$credit_earned_usd_cents"},
            "total_referred_spend": {"$sum": "$referred_spend_usd_cents"},
            "referred_count": {"$sum": 1},
            "active_count": {"$sum": {"$cond": [{"$gt": ["$referred_spend_usd_cents", 0]}, 1, 0]}},
        }},
        {"$sort": {"total_credits": -1, "active_count": -1, "referred_count": -1}},
        {"$limit": limit},
    ]
    rows = await db.referrals.aggregate(pipeline).to_list(length=limit)
    user_ids = [r["_id"] for r in rows]
    users = await db.users.find(
        {"id": {"$in": user_ids}},
        {"_id": 0, "id": 1, "display_name": 1, "country_code": 1},
    ).to_list(length=200)
    by_id = {u["id"]: u for u in users}
    out = []
    for i, r in enumerate(rows, 1):
        u = by_id.get(r["_id"], {})
        out.append({
            "rank": i,
            "user_id": r["_id"],
            "display_name": u.get("display_name") or "Anonymous Champion",
            "country_code": u.get("country_code") or "NG",
            "total_credits_usd_cents": r["total_credits"],
            "total_referred_spend_usd_cents": r["total_referred_spend"],
            "referred_count": r["referred_count"],
            "active_count": r["active_count"],
        })
    # Referral prize pool details
    pool = await db.prize_pools.find_one({"id": "pool-referrals"}, {"_id": 0})
    return {"scope": scope, "leaderboard": out, "pool": pool}


@router.post("/validate/{code}")
async def validate_code(code: str):
    """Check if a referral code is valid (used by signup form)."""
    db = get_db()
    u = await db.users.find_one({"referral_code": code.upper().strip()}, {"_id": 0, "id": 1, "display_name": 1})
    if not u:
        raise HTTPException(status_code=404, detail="Referral code not found")
    return {"ok": True, "referrer_name": u.get("display_name") or "A Cloudy Pitch player"}
