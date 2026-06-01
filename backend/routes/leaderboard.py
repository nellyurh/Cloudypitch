"""Unified leaderboard + prize distribution for Cloudy Pitch.

ONE leaderboard combining fantasy + predictions points.
Referrals stay on their own separate leaderboard.

Prize structure
---------------
BASE POOL: $2,500 (admin-editable via /admin → POOLS)
  · Pos 1  : $1,000
  · Pos 2  : $500
  · Pos 3  : $300
  · Pos 4  : $200
  · Pos 5–20 : split remaining $500 equally (16 winners × $31.25)

CARDS CUT: 50% of every dollar spent on Legend Cards goes to the pool. Split:
  · 25% → positions 1–4 (equal split, 4 winners)
  · 25% → positions 5–15 (equal split, 11 winners)
  · 50% → positions 16–100 (equal split, 85 winners)

Positions 21–100 only see rewards once the cards-cut accumulates.
"""
from __future__ import annotations
from fastapi import APIRouter
from db import get_db

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])

# Base pool defaults (USD cents) — admin can override via prize_pools.amount_usd_cents
BASE_POOL_USD_CENTS = 250_000
TOP4_USD_CENTS = [100_000, 50_000, 30_000, 20_000]
POS_5_20_REMAINING = BASE_POOL_USD_CENTS - sum(TOP4_USD_CENTS)  # $500


def compute_prize_split(base_usd_cents: int, cards_cut_usd_cents: int):
    """Return {position: payout_usd_cents} for positions 1..100."""
    top4 = [100_000, 50_000, 30_000, 20_000]
    # Scale top4 proportionally if admin edited base pool
    base_factor = base_usd_cents / BASE_POOL_USD_CENTS if BASE_POOL_USD_CENTS else 0
    top4_scaled = [int(round(v * base_factor)) for v in top4]
    remaining_base = max(0, base_usd_cents - sum(top4_scaled))
    pos_5_20_each = remaining_base // 16 if remaining_base > 0 else 0

    # Cards cut splits (25/25/50)
    cc_top4 = cards_cut_usd_cents // 4 if cards_cut_usd_cents > 0 else 0
    cc_5_15 = cards_cut_usd_cents // 4 // 11 if cards_cut_usd_cents > 0 else 0
    cc_16_100 = (cards_cut_usd_cents // 2) // 85 if cards_cut_usd_cents > 0 else 0
    # cc_top4 here is the 25%-pool divided per-position-of-4; we need to divide by 4
    cc_top4_each = (cards_cut_usd_cents // 4) // 4 if cards_cut_usd_cents > 0 else 0

    payouts: dict[int, int] = {}
    for i in range(1, 5):
        payouts[i] = top4_scaled[i - 1] + cc_top4_each
    for i in range(5, 16):
        payouts[i] = pos_5_20_each + cc_5_15
    for i in range(16, 21):
        payouts[i] = pos_5_20_each + cc_16_100
    for i in range(21, 101):
        payouts[i] = cc_16_100
    return payouts


@router.get("")
async def unified_leaderboard(scope: str = "global", limit: int = 100):
    """Unified leaderboard = sum(prediction_points) + sum(fantasy_squad.points).
    Optional scope=weekly|premium filters to that subset.
    """
    db = get_db()
    # Sum prediction points per user
    pred_pipeline = [
        {"$match": {"points_awarded": {"$ne": None}}},
        {"$group": {"_id": "$user_id", "pred_pts": {"$sum": "$points_awarded"}}},
    ]
    if scope == "weekly":
        from datetime import datetime, timedelta, timezone
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        pred_pipeline.insert(0, {"$match": {"created_at": {"$gte": since}}})
    preds = await db.predictions.aggregate(pred_pipeline).to_list(length=5000)
    pred_by = {p["_id"]: p["pred_pts"] for p in preds}

    # Sum fantasy points per user (squad total)
    fan_pipeline = [
        {"$group": {"_id": "$user_id", "fan_pts": {"$sum": "$points"}}},
    ]
    fan = await db.fantasy_squads.aggregate(fan_pipeline).to_list(length=5000)
    fan_by = {f["_id"]: f["fan_pts"] for f in fan}

    # Sum WC fantasy points per user (from settled entries)
    wc_pipeline = [
        {"$match": {"settled_at": {"$ne": None}}},
        {"$group": {"_id": "$user_id", "wc_pts": {"$sum": "$points_scored"}}},
    ]
    wc = await db.wc_game_entries.aggregate(wc_pipeline).to_list(length=5000)
    wc_by = {w["_id"]: w["wc_pts"] for w in wc}

    user_ids = list(set(pred_by) | set(fan_by) | set(wc_by))
    if not user_ids:
        return await _empty_with_pool(db)
    rows = await db.users.find(
        {"id": {"$in": user_ids}}, {"_id": 0, "id": 1, "display_name": 1, "country_code": 1, "is_premium": 1},
    ).to_list(length=5000)
    by_user = {u["id"]: u for u in rows}

    combined = []
    for uid in user_ids:
        u = by_user.get(uid) or {}
        if scope == "premium" and not u.get("is_premium"):
            continue
        total = (pred_by.get(uid, 0) or 0) + (fan_by.get(uid, 0) or 0) + (wc_by.get(uid, 0) or 0)
        combined.append({
            "user_id": uid,
            "display_name": u.get("display_name") or "Player",
            "country_code": u.get("country_code") or "—",
            "is_premium": bool(u.get("is_premium")),
            "prediction_points": int(pred_by.get(uid, 0) or 0),
            "fantasy_points": int(fan_by.get(uid, 0) or 0),
            "wc_fantasy_points": int(wc_by.get(uid, 0) or 0),
            "total_points": int(total),
        })
    combined.sort(key=lambda x: -x["total_points"])

    # Prize pool computation
    pool_doc = await db.prize_pools.find_one({"id": "pool-cloudypitch-unified"}, {"_id": 0})
    base = (pool_doc or {}).get("amount_usd_cents", BASE_POOL_USD_CENTS)
    cards_cut = (pool_doc or {}).get("cards_cut_usd_cents", 0)
    # Fallback: aggregate from wallet_transactions if cards_cut not maintained
    if not cards_cut:
        agg = await db.wallet_transactions.aggregate([
            {"$match": {"kind": "card_purchase"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount_usd_cents"}}},
        ]).to_list(length=1)
        total_card_spend = (agg[0]["total"] if agg else 0) or 0
        cards_cut = total_card_spend // 2  # 50%

    payouts = compute_prize_split(base, cards_cut)
    for i, row in enumerate(combined[:limit], 1):
        row["rank"] = i
        row["potential_prize_usd_cents"] = payouts.get(i, 0)

    return {
        "leaderboard": combined[:limit],
        "pool": {
            "base_usd_cents": base,
            "cards_cut_usd_cents": cards_cut,
            "total_usd_cents": base + cards_cut,
        },
        "scope": scope,
    }


async def _empty_with_pool(db):
    pool_doc = await db.prize_pools.find_one({"id": "pool-cloudypitch-unified"}, {"_id": 0})
    base = (pool_doc or {}).get("amount_usd_cents", BASE_POOL_USD_CENTS)
    return {"leaderboard": [], "pool": {"base_usd_cents": base, "cards_cut_usd_cents": 0, "total_usd_cents": base}}


@router.get("/prize-split")
async def prize_split_preview(base_usd_cents: int = BASE_POOL_USD_CENTS, cards_cut_usd_cents: int = 0):
    """Inspect how prize would distribute for given (base, cards_cut) — admin/transparency view."""
    payouts = compute_prize_split(base_usd_cents, cards_cut_usd_cents)
    return {
        "base_usd_cents": base_usd_cents,
        "cards_cut_usd_cents": cards_cut_usd_cents,
        "total_usd_cents": base_usd_cents + cards_cut_usd_cents,
        "payouts": [{"position": p, "usd_cents": v} for p, v in sorted(payouts.items())],
    }


def _redact_display_name(name: str | None) -> str:
    """First-name + masked last-initial. e.g. 'Damilola Adebayo' → '@Damilola A.'"""
    if not name or not isinstance(name, str):
        return "@Anonymous"
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "@Anonymous"
    first = parts[0]
    if len(parts) == 1:
        return f"@{first}"
    return f"@{first} {parts[1][0]}."


@router.get("/pulse")
async def pool_pulse(limit: int = 10):
    """Live ticker of recent card purchases growing the prize pool.

    Returns last N `card_purchase` wallet transactions with redacted user name,
    amount spent, and the resulting pool delta (50% of spend).
    """
    db = get_db()
    rows = await db.wallet_transactions.find(
        {"kind": "card_purchase"},
        {"_id": 0, "user_id": 1, "amount_usd_cents": 1, "created_at": 1, "metadata": 1},
    ).sort("created_at", -1).limit(limit).to_list(length=limit)
    user_ids = list({r.get("user_id") for r in rows if r.get("user_id")})
    users = []
    if user_ids:
        users = await db.users.find(
            {"id": {"$in": user_ids}},
            {"_id": 0, "id": 1, "display_name": 1, "country_code": 1},
        ).to_list(length=len(user_ids))
    by_id = {u["id"]: u for u in users}
    out = []
    for r in rows:
        u = by_id.get(r.get("user_id") or "", {})
        amt = int(r.get("amount_usd_cents") or 0)
        pool_delta = amt // 2  # 50% goes to pool
        out.append({
            "user_id": r.get("user_id"),
            "handle": _redact_display_name(u.get("display_name")),
            "country_code": u.get("country_code") or "—",
            "amount_usd_cents": amt,
            "pool_delta_usd_cents": pool_delta,
            "card_name": (r.get("metadata") or {}).get("card_name") if isinstance(r.get("metadata"), dict) else None,
            "created_at": r.get("created_at"),
        })
    # Aggregate today's totals
    from datetime import datetime, timezone
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    today_agg = await db.wallet_transactions.aggregate([
        {"$match": {"kind": "card_purchase", "created_at": {"$gte": start_of_day}}},
        {"$group": {"_id": None, "total_spend": {"$sum": "$amount_usd_cents"}, "count": {"$sum": 1}}},
    ]).to_list(length=1)
    today = today_agg[0] if today_agg else {"total_spend": 0, "count": 0}
    return {
        "events": out,
        "today": {
            "card_spend_usd_cents": int(today.get("total_spend") or 0),
            "pool_delta_usd_cents": int(today.get("total_spend") or 0) // 2,
            "purchases": int(today.get("count") or 0),
        },
    }

