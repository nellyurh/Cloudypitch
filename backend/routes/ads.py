"""Ad placements + direct sponsorship slots.
Free-tier users see ads; premium subs (is_premium=True) get an empty list.
Networks: admob | adsense | meta | direct (in-house sponsorship)
Placement keys: home_bottom_banner | match_list_inline | wc_hub_sponsor |
  pool_sponsor | interstitial_nav | rewarded_video
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import auth as a
from db import get_db
from models import new_id

router = APIRouter(prefix="/api/ads", tags=["ads"])


VALID_NETWORKS = {"admob", "adsense", "meta", "direct"}
VALID_PLACEMENTS = {
    "home_bottom_banner",
    "match_list_inline",
    "wc_hub_sponsor",
    "pool_sponsor",
    "interstitial_nav",
    "rewarded_video",
}


class PlacementIn(BaseModel):
    placement_key: str
    network: str = Field(pattern="^(admob|adsense|meta|direct)$")
    is_active: bool = True
    sponsor_name: str | None = None
    sponsor_image_url: str | None = None
    target_url: str | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    weight: int = 1  # rotation weight for direct sponsorships


@router.get("/placements")
async def list_placements(
    placement_key: str | None = None,
    user: dict = Depends(a.get_optional_user),
):
    """Return active placements for the requesting user. Premium subs get nothing."""
    db = get_db()
    # Premium = is_premium flag on user (set when they subscribe — TODO Phase E webhook hook)
    if user and user.get("is_premium"):
        return {"placements": [], "premium": True}
    now_iso = datetime.now(timezone.utc).isoformat()
    query: dict = {"is_active": True}
    if placement_key:
        query["placement_key"] = placement_key
    # Date window filter
    placements = await db.ad_placements.find(query, {"_id": 0}).to_list(length=200)
    out = []
    for p in placements:
        if p.get("starts_at") and p["starts_at"] > now_iso:
            continue
        if p.get("ends_at") and p["ends_at"] < now_iso:
            continue
        out.append(p)
    return {"placements": out, "premium": False}


@router.post("/placements")
async def create_placement(body: PlacementIn, user: dict = Depends(a.require_admin)):
    if body.placement_key not in VALID_PLACEMENTS:
        raise HTTPException(status_code=400, detail=f"Invalid placement_key. Use one of: {sorted(VALID_PLACEMENTS)}")
    db = get_db()
    doc = body.model_dump()
    doc.update({
        "id": new_id(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "impressions": 0, "clicks": 0,
    })
    await db.ad_placements.insert_one(doc)
    doc.pop("_id", None)
    return {"placement": doc}


@router.patch("/placements/{placement_id}")
async def update_placement(placement_id: str, body: PlacementIn, user: dict = Depends(a.require_admin)):
    db = get_db()
    upd = body.model_dump()
    res = await db.ad_placements.update_one({"id": placement_id}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@router.delete("/placements/{placement_id}")
async def delete_placement(placement_id: str, user: dict = Depends(a.require_admin)):
    db = get_db()
    res = await db.ad_placements.delete_one({"id": placement_id})
    return {"deleted": res.deleted_count}


@router.post("/impression/{placement_id}")
async def track_impression(placement_id: str, user: dict = Depends(a.get_optional_user)):
    db = get_db()
    await db.ad_placements.update_one({"id": placement_id}, {"$inc": {"impressions": 1}})
    return {"ok": True}


@router.post("/click/{placement_id}")
async def track_click(placement_id: str, user: dict = Depends(a.get_optional_user)):
    db = get_db()
    await db.ad_placements.update_one({"id": placement_id}, {"$inc": {"clicks": 1}})
    return {"ok": True}


class RewardClaimIn(BaseModel):
    reward_type: str = Field(pattern="^(card_uses|prediction_points)$")


@router.post("/reward/claim")
async def claim_reward(body: RewardClaimIn, user: dict = Depends(a.get_current_user)):
    """Rate-limited: 1 reward claim per 60 seconds. Grants +5 card uses or +50 prediction points."""
    db = get_db()
    # Rate limit
    last = await db.ad_rewards.find_one(
        {"user_id": user["id"]}, sort=[("claimed_at", -1)],
    )
    if last and last.get("claimed_at"):
        last_dt = datetime.fromisoformat(last["claimed_at"])
        if (datetime.now(timezone.utc) - last_dt).total_seconds() < 60:
            raise HTTPException(status_code=429, detail="Wait 60s between rewards")

    payload: dict = {"reward_type": body.reward_type}
    if body.reward_type == "card_uses":
        # Add +5 uses to user's first owned card (or top up most-used)
        uc = await db.user_cards.find_one(
            {"user_id": user["id"]}, sort=[("uses_remaining", 1)],
        )
        if not uc:
            raise HTTPException(status_code=400, detail="No cards to top up")
        await db.user_cards.update_one(
            {"id": uc["id"]},
            {"$inc": {"uses_remaining": 5, "uses_left": 5}},
        )
        payload["user_card_id"] = uc["id"]
        payload["uses_added"] = 5
    else:
        # Add +50 bonus prediction points via a synthetic settled "prediction" row
        bonus_doc = {
            "id": new_id(), "user_id": user["id"], "match_id": "ad-reward",
            "home_score_predicted": 0, "away_score_predicted": 0,
            "outcome_predicted": "D", "points_awarded": 50,
            "exact_score_hit": False, "outcome_correct": True,
            "settled_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "ad_reward",
        }
        await db.predictions.insert_one(bonus_doc)
        payload["points_added"] = 50

    payload.update({
        "id": new_id(), "user_id": user["id"],
        "claimed_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.ad_rewards.insert_one(payload)
    payload.pop("_id", None)
    return {"ok": True, "reward": payload}
