"""Prize pools + settlement."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

import auth as a
from db import get_db
from models import new_id

router = APIRouter(prefix="/api/prize-pools", tags=["prize-pools"])


@router.get("")
async def list_pools():
    db = get_db()
    pools = await db.prize_pools.find({}, {"_id": 0}).sort("starts_at", -1).to_list(length=50)
    return {"pools": pools}


@router.get("/{pool_id}")
async def pool_detail(pool_id: str):
    db = get_db()
    pool = await db.prize_pools.find_one({"id": pool_id}, {"_id": 0})
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    winners = await db.prize_pool_winners.find({"pool_id": pool_id}, {"_id": 0}).sort("rank", 1).to_list(length=100)
    return {"pool": pool, "winners": winners}


@router.post("/{pool_id}/settle")
async def settle_pool(pool_id: str, admin: dict = Depends(a.require_admin)):
    """Compute payouts from the pool's payout_structure + leaderboard at settlement time.
    Writes prize_pool_winners with `payout_status='pending'`. Actual money transfer happens
    via /api/payments/paystack/transfer for cash payout OR /api/wallet/credit-winnings for
    store-credit fallback."""
    db = get_db()
    pool = await db.prize_pools.find_one({"id": pool_id}, {"_id": 0})
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")

    pool_type = pool.get("type", "predictions")  # predictions | fantasy
    total = int(pool.get("amount_total_ngn") or 0)
    structure = pool.get("payout_structure") or []
    if total <= 0 or not structure:
        raise HTTPException(status_code=400, detail="Pool has no amount or payout_structure")

    # Pull final leaderboard
    if pool_type == "fantasy":
        comp_id = pool.get("competition_id", "fantasy-wc2026")
        rows = await db.fantasy_squads.find(
            {"competition_id": comp_id}, {"_id": 0, "user_id": 1, "total_points": 1, "squad_name": 1},
        ).sort("total_points", -1).to_list(length=10000)
    else:
        pipeline = [
            {"$match": {"settled_at": {"$ne": None}}},
            {"$group": {"_id": "$user_id", "total_points": {"$sum": "$points_awarded"}}},
            {"$sort": {"total_points": -1}},
            {"$limit": 10000},
        ]
        rows = await db.predictions.aggregate(pipeline).to_list(length=10000)
        rows = [{"user_id": r["_id"], "total_points": r["total_points"]} for r in rows]

    # Clear previous winners
    await db.prize_pool_winners.delete_many({"pool_id": pool_id})

    winners = []
    for tier in structure:
        rmin = int(tier.get("rank_min") or 0)
        rmax = int(tier.get("rank_max") or 0)
        pct = float(tier.get("pct") or 0)
        slice_rows = rows[rmin - 1:rmax]
        if not slice_rows:
            continue
        per_user = int((total * pct / 100.0))
        for offset, r in enumerate(slice_rows):
            rank = rmin + offset
            w = {
                "id": new_id(), "pool_id": pool_id,
                "user_id": r["user_id"], "rank": rank,
                "amount_ngn": per_user, "points": r.get("total_points", 0),
                "payout_status": "pending",
                "settled_at": datetime.now(timezone.utc).isoformat(),
            }
            winners.append(w)
    if winners:
        await db.prize_pool_winners.insert_many(winners)
        await db.prize_pools.update_one(
            {"id": pool_id},
            {"$set": {"settled_at": datetime.now(timezone.utc).isoformat(), "winner_count": len(winners)}},
        )
    return {"ok": True, "winners_count": len(winners), "pool_type": pool_type}
