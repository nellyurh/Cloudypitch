"""Unified leaderboard + prize distribution for Cloudy Pitch.

ONE leaderboard combining fantasy + predictions points.
Referrals stay on their own separate leaderboard.

Eligibility (2026-02-12, updated 2026-02-13)
-------------------------------------------
Users must satisfy BOTH gates to receive a prize-pool payout:
  · Made at least `PRIZE_POOL_MIN_PREDICTIONS` predictions (default **20**)
  · Entered at least `PRIZE_POOL_MIN_WC_GAMES` WC mini-games (default **50**)

Counts use ALL submitted entries — settled or not — so users can't be
blocked from eligibility by the settler being behind. They still appear on
the leaderboard with their rank but `potential_prize_usd_cents = 0` until
qualified. This prevents bots that grind one pillar from extracting the pool.

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
import os
from fastapi import APIRouter
from db import get_db

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])

# Base pool defaults (USD cents) — admin can override via prize_pools.amount_usd_cents
BASE_POOL_USD_CENTS = 250_000
TOP4_USD_CENTS = [100_000, 50_000, 30_000, 20_000]
POS_5_20_REMAINING = BASE_POOL_USD_CENTS - sum(TOP4_USD_CENTS)  # $500

# Anti-bot minimums to qualify for any prize-pool payout (count-based).
PRIZE_POOL_MIN_PREDICTIONS = int(os.environ.get("PRIZE_POOL_MIN_PREDICTIONS", "20"))
PRIZE_POOL_MIN_WC_GAMES = int(os.environ.get("PRIZE_POOL_MIN_WC_GAMES", "50"))


def compute_prize_split(base_usd_cents: int, cards_cut_usd_cents: int):
    """Return {position: payout_usd_cents} for positions 1..100."""
    top4 = [100_000, 50_000, 30_000, 20_000]
    # Scale top4 proportionally if admin edited base pool
    base_factor = base_usd_cents / BASE_POOL_USD_CENTS if BASE_POOL_USD_CENTS else 0
    top4_scaled = [int(round(v * base_factor)) for v in top4]
    remaining_base = max(0, base_usd_cents - sum(top4_scaled))
    pos_5_20_each = remaining_base // 16 if remaining_base > 0 else 0

    # Cards cut splits (25/25/50)
    cc_5_15 = cards_cut_usd_cents // 4 // 11 if cards_cut_usd_cents > 0 else 0
    cc_16_100 = (cards_cut_usd_cents // 2) // 85 if cards_cut_usd_cents > 0 else 0
    # 25% bucket split equally across positions 1–4
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

    # Sum MAIN-TEAM fantasy points per user (15-man squad total).
    # 🐛 Fix 2026-02-15: previously summed "$points" which doesn't exist on the
    # `fantasy_squads` doc — the canonical field is `total_points` written by
    # `settle_gameweek`. The bug meant the main 15-man squad never contributed
    # to the unified leaderboard total. Now correctly summed.
    fan_pipeline = [
        {"$group": {"_id": "$user_id", "fan_pts": {"$sum": "$total_points"}}},
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

    # Count predictions made + WC mini-game entries per user — drives eligibility.
    pred_count_agg = await db.predictions.aggregate([
        {"$group": {"_id": "$user_id", "n": {"$sum": 1}}},
    ]).to_list(length=10000)
    pred_count_by = {r["_id"]: r["n"] for r in pred_count_agg}
    wc_count_agg = await db.wc_game_entries.aggregate([
        {"$group": {"_id": "$user_id", "n": {"$sum": 1}}},
    ]).to_list(length=10000)
    wc_count_by = {r["_id"]: r["n"] for r in wc_count_agg}

    # Hard requirement: only show users who actually HAVE a squad (main 15-man
    # OR at least one WC mini-game entry). Users who only signed up but never
    # built a team shouldn't pollute the leaderboard with 0-point rows.
    squad_user_ids = set()
    main_squads = await db.fantasy_squads.find({}, {"_id": 0, "user_id": 1}).to_list(length=10000)
    for s in main_squads:
        if s.get("user_id"):
            squad_user_ids.add(s["user_id"])
    wc_entries_users = await db.wc_game_entries.find({}, {"_id": 0, "user_id": 1}).to_list(length=10000)
    for e in wc_entries_users:
        if e.get("user_id"):
            squad_user_ids.add(e["user_id"])

    user_ids = list(set(pred_by) | set(fan_by) | set(wc_by))
    # Apply the squad-presence filter
    user_ids = [uid for uid in user_ids if uid in squad_user_ids]
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
        pred_pts = int(pred_by.get(uid, 0) or 0)
        fan_pts = int(fan_by.get(uid, 0) or 0)
        wc_pts = int(wc_by.get(uid, 0) or 0)
        total = pred_pts + fan_pts + wc_pts
        # Eligibility = made enough predictions AND entered enough mini-games.
        # Count-based (NOT points-based) so the settler lag never blocks anyone.
        pred_count = int(pred_count_by.get(uid, 0) or 0)
        wc_count = int(wc_count_by.get(uid, 0) or 0)
        is_eligible = (
            pred_count >= PRIZE_POOL_MIN_PREDICTIONS
            and wc_count >= PRIZE_POOL_MIN_WC_GAMES
        )
        combined.append({
            "user_id": uid,
            "display_name": u.get("display_name") or "Player",
            "country_code": u.get("country_code") or "—",
            "is_premium": bool(u.get("is_premium")),
            "prediction_points": pred_pts,
            "fantasy_points": fan_pts,
            "wc_fantasy_points": wc_pts,
            "total_points": int(total),
            "prediction_count": pred_count,
            "wc_game_count": wc_count,
            "is_eligible": is_eligible,
            "min_predictions": PRIZE_POOL_MIN_PREDICTIONS,
            "min_wc_games": PRIZE_POOL_MIN_WC_GAMES,
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
        # 🛡️ Eligibility gate: ineligible users keep their rank but get $0
        # potential prize. The slot is held — it does NOT roll over to the
        # next eligible user — to avoid leaderboard whiplash if a user dips
        # below the threshold mid-tournament. This can be revisited on the
        # final settlement pass via /api/leaderboard/admin/redistribute.
        row["potential_prize_usd_cents"] = payouts.get(i, 0) if row.get("is_eligible") else 0

    return {
        "leaderboard": combined[:limit],
        "pool": {
            "base_usd_cents": base,
            "cards_cut_usd_cents": cards_cut,
            "total_usd_cents": base + cards_cut,
        },
        "scope": scope,
        "eligibility": {
            "min_predictions": PRIZE_POOL_MIN_PREDICTIONS,
            "min_wc_games": PRIZE_POOL_MIN_WC_GAMES,
            "rule": (
                f"Must have made ≥ {PRIZE_POOL_MIN_PREDICTIONS} predictions "
                f"AND entered ≥ {PRIZE_POOL_MIN_WC_GAMES} WC mini-games "
                "to receive a prize-pool payout."
            ),
        },
    }


@router.get("/user/{user_id}")
async def public_user_profile(user_id: str, limit: int = 50):
    """Public view of any user's predictions + fantasy squad + WC mini-game entries.

    Returns everything needed to render a 'how are they getting points' modal
    on the leaderboard — for full transparency. Anyone can call this; no auth
    required. Sensitive fields (email, IP, etc.) are NEVER included.
    """
    db = get_db()
    user = await db.users.find_one(
        {"id": user_id},
        {"_id": 0, "id": 1, "display_name": 1, "country_code": 1, "is_premium": 1, "created_at": 1},
    )
    if not user:
        return {"user": None, "predictions": [], "squad": None, "wc_entries": [], "totals": {}}

    # Predictions (most recent 50, including pending + settled)
    preds = await db.predictions.find(
        {"user_id": user_id}, {"_id": 0},
    ).sort("created_at", -1).to_list(length=limit)
    match_ids = list({p["match_id"] for p in preds})
    matches = await db.matches.find(
        {"id": {"$in": match_ids}},
        {"_id": 0, "id": 1, "home_team_name": 1, "away_team_name": 1,
         "home_team_logo": 1, "away_team_logo": 1, "scheduled_at": 1,
         "home_score": 1, "away_score": 1, "status": 1, "league_name": 1, "league_country": 1},
    ).to_list(length=len(match_ids)) if match_ids else []
    m_by = {m["id"]: m for m in matches}
    for p in preds:
        p["match"] = m_by.get(p["match_id"])

    # Main fantasy squad (15-man)
    squad = await db.fantasy_squads.find_one(
        {"user_id": user_id, "competition_id": "fantasy-wc2026"},
        {"_id": 0},
    )

    # WC mini-game entries (closed/settled only — pre-deadline entries hidden
    # so users can't copy each other's picks)
    open_game_ids = await db.wc_games.distinct("id", {"status": "open"})
    wc_entries = await db.wc_game_entries.find(
        {"user_id": user_id, "wc_game_id": {"$nin": open_game_ids}},
        {"_id": 0},
    ).sort("updated_at", -1).to_list(length=100)
    wc_game_ids = [e["wc_game_id"] for e in wc_entries]
    wc_games = await db.wc_games.find(
        {"id": {"$in": wc_game_ids}}, {"_id": 0},
    ).to_list(length=len(wc_game_ids)) if wc_game_ids else []
    wcg_by = {g["id"]: g for g in wc_games}
    for e in wc_entries:
        e["wc_game"] = wcg_by.get(e["wc_game_id"])

    # Totals — mirror the unified leaderboard math.
    pred_pts = sum((p.get("points_awarded") or 0) for p in preds if p.get("settled_at"))
    fan_pts = int((squad or {}).get("total_points", 0) or 0)
    wc_pts = sum((e.get("points_scored") or 0) for e in wc_entries if e.get("settled_at"))
    # Count-based eligibility check — count ALL submitted entries, not just
    # the most-recent N we returned to the caller.
    total_pred_count = await db.predictions.count_documents({"user_id": user_id})
    total_wc_count = await db.wc_game_entries.count_documents({"user_id": user_id})
    totals = {
        "prediction_points": int(pred_pts),
        "fantasy_points": int(fan_pts),
        "wc_fantasy_points": int(wc_pts),
        "total_points": int(pred_pts + fan_pts + wc_pts),
        "prediction_count": int(total_pred_count),
        "wc_game_count": int(total_wc_count),
        "is_eligible": (
            total_pred_count >= PRIZE_POOL_MIN_PREDICTIONS
            and total_wc_count >= PRIZE_POOL_MIN_WC_GAMES
        ),
        "min_predictions": PRIZE_POOL_MIN_PREDICTIONS,
        "min_wc_games": PRIZE_POOL_MIN_WC_GAMES,
    }
    return {
        "user": user,
        "predictions": preds,
        "squad": squad,
        "wc_entries": wc_entries,
        "totals": totals,
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

