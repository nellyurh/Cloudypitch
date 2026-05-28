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

    # Accept either list-of-dicts ([{rank_min, rank_max, pct}, ...]) or legacy dict ({"1st":0.40,"4-10":0.20})
    tiers: list[dict] = []
    if isinstance(structure, list):
        for t in structure:
            if isinstance(t, dict):
                tiers.append({
                    "rank_min": int(t.get("rank_min") or 0),
                    "rank_max": int(t.get("rank_max") or 0),
                    "pct": float(t.get("pct") or 0),
                })
    elif isinstance(structure, dict):
        ORDINAL_TO_RANK = {"1st": 1, "2nd": 2, "3rd": 3}
        for key, frac in structure.items():
            # `frac` is a fraction (0.40) or percentage (40) — we normalise to percentage
            pct = float(frac) * 100 if float(frac) <= 1 else float(frac)
            rmin = rmax = None
            if isinstance(key, str) and "-" in key:
                parts = key.split("-")
                try:
                    rmin, rmax = int(parts[0]), int(parts[1])
                except ValueError:
                    continue
            elif key in ORDINAL_TO_RANK:
                rmin = rmax = ORDINAL_TO_RANK[key]
            else:
                try:
                    rmin = rmax = int(key)
                except (ValueError, TypeError):
                    continue
            tiers.append({"rank_min": rmin, "rank_max": rmax, "pct": pct})

    if not tiers:
        raise HTTPException(status_code=400, detail="payout_structure parse failed — invalid format")

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
    for tier in tiers:
        rmin = tier["rank_min"]
        rmax = tier["rank_max"]
        pct = tier["pct"]
        slice_rows = rows[rmin - 1:rmax]
        if not slice_rows:
            continue
        per_user = int((total * pct / 100.0) / max(1, len(slice_rows)))
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
