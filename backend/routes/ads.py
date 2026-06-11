"""Ad placements + direct sponsorship slots.
Free-tier users see ads; premium subs (is_premium=True) get an empty list.
Networks: admob | adsense | meta | direct (in-house sponsorship)
Placement keys: home_bottom_banner | match_list_inline | wc_hub_sponsor |
  pool_sponsor | interstitial_nav | rewarded_video |
  header_banner | sidebar_right | leaderboard_above | mobile_bottom |
  wc_hub_top | predictions_inline | fantasy_sidebar
"""
from datetime import datetime, timezone
import os
import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import auth as a
from db import get_db
from models import new_id

router = APIRouter(prefix="/api/ads", tags=["ads"])


VALID_NETWORKS = {"admob", "adsense", "meta", "direct"}
VALID_PLACEMENTS = {
    # Legacy
    "home_bottom_banner", "match_list_inline", "wc_hub_sponsor",
    "pool_sponsor", "interstitial_nav", "rewarded_video",
    # Sofascore-style placements added 2026-02
    "header_banner",      # full-width banner just under sports nav
    "sidebar_right",      # right rail sticky slot (300x250 / 300x600)
    "leaderboard_above",  # above the WC leaderboard widget
    "mobile_bottom",      # sticky bottom bar on mobile
    "wc_hub_top",         # banner inside /worldcup above the trophy hero
    "predictions_inline", # between prediction rows
    "fantasy_sidebar",    # /fantasy + /build-team sidebar
}

ADSENSE_PUBLISHER_ID = os.environ.get("ADSENSE_PUBLISHER_ID", "")
ADSENSE_ENABLED = bool(ADSENSE_PUBLISHER_ID)


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


@router.get("/config")
async def ads_config(user: dict = Depends(a.get_optional_user)):
    """Public ad config — FE injects the AdSense script using this.
    Premium users always get `{enabled: false}` so no ad code is ever loaded.
    """
    is_premium = bool(user and user.get("is_premium"))
    return {
        "adsense_enabled": ADSENSE_ENABLED and not is_premium,
        "adsense_publisher_id": ADSENSE_PUBLISHER_ID if (ADSENSE_ENABLED and not is_premium) else "",
        "premium": is_premium,
        "valid_placements": sorted(VALID_PLACEMENTS),
    }


@router.get("/serve/{placement_key}")
async def serve_ad(placement_key: str, user: dict = Depends(a.get_optional_user)):
    """Return the best active ad for this placement.

    Priority:
      1) Premium → empty (no ad anywhere)
      2) An eligible `direct` sponsor (weighted random pick) → returned with `network: 'direct'`
      3) Else → tell FE to fall back to AdSense (`network: 'adsense'`, with the ad_slot)
    """
    if placement_key not in VALID_PLACEMENTS:
        raise HTTPException(status_code=400, detail=f"Unknown placement_key. Use one of: {sorted(VALID_PLACEMENTS)}")
    if user and user.get("is_premium"):
        return {"ad": None, "premium": True}

    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor = db.ad_placements.find(
        {"placement_key": placement_key, "is_active": True, "network": "direct"},
        {"_id": 0},
    )
    eligible: list[dict] = []
    async for p in cursor:
        if p.get("starts_at") and p["starts_at"] > now_iso:
            continue
        if p.get("ends_at") and p["ends_at"] < now_iso:
            continue
        eligible.append(p)

    if eligible:
        # Weighted random pick — weight defaults to 1.
        weights = [max(1, int(p.get("weight", 1))) for p in eligible]
        pick = random.choices(eligible, weights=weights, k=1)[0]
        # Fire-and-forget impression bump
        await db.ad_placements.update_one({"id": pick["id"]}, {"$inc": {"impressions": 1}})
        return {"ad": pick, "premium": False, "source": "direct"}

    if ADSENSE_ENABLED:
        # Look up an admin-configured AdSense slot id for this placement (optional).
        slot = await db.adsense_slots.find_one({"placement_key": placement_key}, {"_id": 0})
        ad_slot = (slot or {}).get("ad_slot") or ""
        return {
            "ad": {
                "network": "adsense",
                "placement_key": placement_key,
                "ad_slot": ad_slot,
                "publisher_id": ADSENSE_PUBLISHER_ID,
            },
            "premium": False,
            "source": "adsense",
        }
    return {"ad": None, "premium": False, "source": "none"}


class AdSenseSlotIn(BaseModel):
    placement_key: str
    ad_slot: str = Field(min_length=4, max_length=32)


@router.post("/adsense-slots")
async def upsert_adsense_slot(body: AdSenseSlotIn, user: dict = Depends(a.require_admin)):
    if body.placement_key not in VALID_PLACEMENTS:
        raise HTTPException(status_code=400, detail=f"Unknown placement_key. Use one of: {sorted(VALID_PLACEMENTS)}")
    db = get_db()
    await db.adsense_slots.update_one(
        {"placement_key": body.placement_key},
        {"$set": {"ad_slot": body.ad_slot, "updated_at": datetime.now(timezone.utc).isoformat(),
                   "updated_by": user["id"]}},
        upsert=True,
    )
    return {"ok": True, "placement_key": body.placement_key, "ad_slot": body.ad_slot}


@router.get("/adsense-slots")
async def list_adsense_slots(user: dict = Depends(a.require_admin)):
    db = get_db()
    slots = await db.adsense_slots.find({}, {"_id": 0}).to_list(length=50)
    return {"slots": slots, "publisher_id": ADSENSE_PUBLISHER_ID}


@router.delete("/adsense-slots/{placement_key}")
async def delete_adsense_slot(placement_key: str, user: dict = Depends(a.require_admin)):
    db = get_db()
    res = await db.adsense_slots.delete_one({"placement_key": placement_key})
    return {"deleted": res.deleted_count}


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
            {"$inc": {"uses_remaining": 1, "uses_left": 1}},
        )
        payload["user_card_id"] = uc["id"]
        payload["uses_added"] = 1
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
