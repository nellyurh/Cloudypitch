"""Prize pools."""
from fastapi import APIRouter, HTTPException
from db import get_db

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
