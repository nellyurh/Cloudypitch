"""Legend cards: catalog + my cards + purchase + recharge.

Pricing model (2026-02-13): cards are denominated in **coins**, not USD.
The conversion is:
   • 1 NGN top-up        → 1 coin
   • 1 USD/crypto top-up → 1,370 coins (1 coin = $0.00073). Crypto gets a
     +5% bonus on top.

Card tier prices (coins):
   • Legendary (tier 1) = 1,000 coins
   • Elite     (tier 2) = 500 coins
   • Star      (tier 3) = 200 coins
   • Recharge           = 100 coins (+1 use)

50% of every coin spent on cards flows to the WC prize pool — converted back
to USD-cents for the pool ledger using the same `1 coin = $0.00073` rate.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import auth as a
from db import get_db
from models import new_id

router = APIRouter(prefix="/api/cards", tags=["cards"])


# ─── Coin-based pricing (USD-cent equivalents kept on the side for the pool) ──
TIER_PRICE_COINS = {1: 1000, 2: 500, 3: 200}
RECHARGE_PRICE_COINS = 100
COIN_TO_USD_CENTS = 0.073  # 1 coin = $0.00073 = 0.073 cents
STARTER_USES = 1
RECHARGE_USES = 1
POOL_CONTRIBUTION_RATIO = 0.50  # 50% of revenue → prize pool
WC_PRIZE_POOL_ID = "pool-cloudypitch-unified"


def coins_to_usd_cents(coins: int) -> int:
    """Convert coins → integer USD cents (rounded down) for the pool ledger."""
    return int(coins * COIN_TO_USD_CENTS)


async def _contribute_to_pool(db, amount_cents: int, user_id: str, source: str, reference: str | None):
    """Move 50% of `amount_cents` into the UNIFIED prize pool as `cards_cut`.

    Critical: the BASE pool (`amount_usd_cents`) is FIXED at the value the
    admin seeded — it represents the company-backed guaranteed prize and
    must never be incremented by card revenue (doing so would conflate the
    two and break the leaderboard's "base vs bonus" split). Only the
    `cards_cut_usd_cents` field grows with each contribution.
    """
    contribution = int(amount_cents * POOL_CONTRIBUTION_RATIO)
    if contribution <= 0:
        return
    # Use upsert here only so the pool exists; the base amount is set when
    # the doc is first inserted (by seed or by this $setOnInsert fallback).
    await db.prize_pools.update_one(
        {"id": WC_PRIZE_POOL_ID},
        {
            "$inc": {
                "cards_cut_usd_cents": contribution,
                "amount_total_ngn": int(contribution * 16),
            },
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            # If the pool doc was somehow lost (DB reset, partial migration),
            # restore the seeded base so the leaderboard never shows $0.00.
            "$setOnInsert": {
                "id": WC_PRIZE_POOL_ID,
                "kind": "fantasy_predictions_unified",
                "amount_usd_cents": 250_000,
                "currency": "USD",
                "status": "live",
                "title": "Cloudy Pitch Grand Prize Pool",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        upsert=True,
    )
    await db.prize_pool_contributions.insert_one({
        "id": new_id(), "pool_id": WC_PRIZE_POOL_ID,
        "user_id": user_id, "source": source,
        "amount_usd_cents": contribution,
        "from_amount_usd_cents": amount_cents,
        "ratio": POOL_CONTRIBUTION_RATIO,
        "reference": reference,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


class PurchaseIn(BaseModel):
    card_id: str | None = None  # optional when card_id is in the URL path
    quantity: int = 1
    payment_reference: str | None = None


class RechargeIn(BaseModel):
    user_card_id: str
    payment_reference: str | None = None


@router.get("")
async def list_cards():
    db = get_db()
    cards = await db.legend_cards.find({}, {"_id": 0}).to_list(length=500)
    # Stamp coin prices on each card so the FE always has them (legacy docs
    # may only carry `price_usd_cents` — derive the coin price from tier).
    for c in cards:
        if not c.get("price_coins"):
            c["price_coins"] = TIER_PRICE_COINS.get(c.get("tier"), 200)
    # Sort by tier asc, then price desc
    cards.sort(key=lambda c: (c.get("tier", 99), -(c.get("price_coins") or 0)))
    return {
        "cards": cards,
        "currency": "COINS",
        "tiers": {
            "1": {"name": "Legendary", "price_coins": 1000, "color": "#A3E635"},
            "2": {"name": "Elite",     "price_coins": 500,  "color": "#0F6E56"},
            "3": {"name": "Star",      "price_coins": 200,  "color": "#64748B"},
        },
        "recharge_price_coins": RECHARGE_PRICE_COINS,
        "starter_uses": STARTER_USES,
        "pool_contribution_ratio": POOL_CONTRIBUTION_RATIO,
        "coin_to_usd_cents": COIN_TO_USD_CENTS,
    }


@router.get("/me")
async def my_cards(user: dict = Depends(a.get_current_user)):
    db = get_db()
    owned = await db.user_cards.find({"user_id": user["id"]}, {"_id": 0}).to_list(length=500)
    card_ids = [c["card_id"] for c in owned]
    cards = await db.legend_cards.find({"id": {"$in": card_ids}}, {"_id": 0}).to_list(length=500)
    by_id = {c["id"]: c for c in cards}
    out = []
    for o in owned:
        c = by_id.get(o["card_id"])
        if c:
            out.append({**o, "card": c})
    return {"owned": out, "count": len(out)}


@router.get("/me/history")
async def my_card_usage_history(user: dict = Depends(a.get_current_user), limit: int = 100):
    """List every card the user has spent — with the game it was used in and the targeted player.

    Pulls from THREE sources so nothing is silently missed:
      1. Legacy `card_uses` collection (older predictions flow).
      2. New per-player applications in `wc_game_entries.cards_used`
         (the WC mini-game flow used by `/api/wc/games/{id}/enter`).
      3. Main 15-man squad cards in `fantasy_squads.applied_cards`.

    Each entry is normalised so the frontend renders one consistent row.
    """
    db = get_db()

    # 1) Legacy card_uses rows
    legacy = await db.card_uses.find(
        {"user_id": user["id"]}, {"_id": 0},
    ).sort("created_at", -1).limit(limit).to_list(length=limit)

    # 2) wc_game_entries with cards_used[]
    wc_entries = await db.wc_game_entries.find(
        {"user_id": user["id"], "cards_used": {"$exists": True, "$ne": []}},
        {"_id": 0, "id": 1, "wc_game_id": 1, "cards_used": 1,
         "created_at": 1, "updated_at": 1, "settled_at": 1,
         "points_scored": 1, "rank_in_game": 1},
    ).sort("updated_at", -1).limit(limit).to_list(length=limit)

    # 3) fantasy_squads with applied_cards[]
    squads = await db.fantasy_squads.find(
        {"user_id": user["id"], "applied_cards": {"$exists": True, "$ne": []}},
        {"_id": 0, "id": 1, "applied_cards": 1, "squad_name": 1,
         "updated_at": 1, "total_points": 1, "competition_id": 1},
    ).sort("updated_at", -1).limit(limit).to_list(length=limit)

    # Collect ids for batch joins
    card_ids: set[str] = set()
    game_ids: set[str] = set()
    player_ids: set[str] = set()
    uc_ids: set[str] = set()
    for r in legacy:
        if r.get("card_id"): card_ids.add(r["card_id"])
        if r.get("wc_game_id"): game_ids.add(r["wc_game_id"])
        if r.get("target_player_id"): player_ids.add(r["target_player_id"])
    for e in wc_entries:
        game_ids.add(e["wc_game_id"])
        for cu in e.get("cards_used", []):
            if cu.get("user_card_id"): uc_ids.add(cu["user_card_id"])
            if cu.get("target_player_id"): player_ids.add(cu["target_player_id"])
    for s in squads:
        for cu in s.get("applied_cards", []):
            if cu.get("user_card_id"): uc_ids.add(cu["user_card_id"])
            if cu.get("target_player_id"): player_ids.add(cu["target_player_id"])

    # Resolve user_card_id → card_id
    if uc_ids:
        uc_rows = await db.user_cards.find(
            {"id": {"$in": list(uc_ids)}}, {"_id": 0, "id": 1, "card_id": 1},
        ).to_list(length=len(uc_ids))
        uc_to_card = {r["id"]: r["card_id"] for r in uc_rows}
        for cid in uc_to_card.values():
            card_ids.add(cid)
    else:
        uc_to_card = {}

    cards = await db.legend_cards.find({"id": {"$in": list(card_ids)}}, {"_id": 0}).to_list(length=200) if card_ids else []
    games = await db.wc_games.find({"id": {"$in": list(game_ids)}}, {"_id": 0}).to_list(length=200) if game_ids else []
    players = await db.players.find(
        {"id": {"$in": list(player_ids)}},
        {"_id": 0, "id": 1, "name": 1, "team_name": 1, "team_logo": 1, "position": 1, "photo_url": 1},
    ).to_list(length=400) if player_ids else []
    by_card = {c["id"]: c for c in cards}
    by_game = {g["id"]: g for g in games}
    by_player = {p["id"]: p for p in players}

    out: list[dict] = []
    # Source 1
    for r in legacy:
        out.append({
            **r,
            "source": "legacy",
            "card": by_card.get(r.get("card_id")),
            "game": by_game.get(r.get("wc_game_id")),
            "target_player": by_player.get(r.get("target_player_id")),
        })
    # Source 2 — WC mini-game entries
    for e in wc_entries:
        for cu in e.get("cards_used", []):
            card_id = uc_to_card.get(cu.get("user_card_id"))
            out.append({
                "id": f"wc_{e['id']}_{cu.get('user_card_id')}",
                "source": "wc_game",
                "user_card_id": cu.get("user_card_id"),
                "card_id": card_id,
                "wc_game_id": e["wc_game_id"],
                "target_player_id": cu.get("target_player_id"),
                "created_at": e.get("updated_at") or e.get("created_at"),
                "settled_at": e.get("settled_at"),
                "points_scored": e.get("points_scored"),
                "rank_in_game": e.get("rank_in_game"),
                "card": by_card.get(card_id) if card_id else None,
                "game": by_game.get(e["wc_game_id"]),
                "target_player": by_player.get(cu.get("target_player_id")),
            })
    # Source 3 — main 15-man squad
    for s in squads:
        for cu in s.get("applied_cards", []):
            card_id = uc_to_card.get(cu.get("user_card_id"))
            out.append({
                "id": f"sq_{s['id']}_{cu.get('user_card_id')}",
                "source": "main_squad",
                "user_card_id": cu.get("user_card_id"),
                "card_id": card_id,
                "squad_id": s["id"],
                "squad_name": s.get("squad_name"),
                "target_player_id": cu.get("target_player_id"),
                "created_at": s.get("updated_at"),
                "card": by_card.get(card_id) if card_id else None,
                "target_player": by_player.get(cu.get("target_player_id")),
            })
    # Sort newest first
    out.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return {"history": out[:limit]}


async def _purchase_card_impl(db, user: dict, card_id: str, quantity: int, payment_reference: str | None):
    """Shared purchase implementation. Supports `quantity` ≥ 1 — each copy
    grants STARTER_USES (currently 1) use to the user's collection.

    Charges the buyer's COIN balance (`users.coins`). If they don't have
    enough → 402 with a friendly message telling them how short they are.
    50% of the coin spend (converted to USD-cents at $0.00073 per coin)
    flows to the WC prize pool.
    """
    if quantity < 1 or quantity > 25:
        raise HTTPException(status_code=400, detail="quantity must be between 1 and 25")
    card = await db.legend_cards.find_one({"id": card_id}, {"_id": 0})
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    unit_coins = card.get("price_coins") or TIER_PRICE_COINS.get(card.get("tier"), 200)
    total_coins = unit_coins * quantity
    uses_granted = STARTER_USES * quantity

    # ---- Coin balance check ----
    udoc = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    bal = int((udoc or {}).get("coins") or 0)
    if bal < total_coins:
        short = total_coins - bal
        raise HTTPException(
            status_code=402,
            detail=(
                f"Insufficient coins. Card costs {total_coins} coins, "
                f"you have {bal} (short by {short}). "
                "Top up your wallet to buy this card."
            ),
        )

    # ---- Atomic debit. Re-read to guard against a race / double-click. ----
    debit = await db.users.update_one(
        {"id": user["id"], "coins": {"$gte": total_coins}},
        {"$inc": {"coins": -total_coins}},
    )
    if debit.modified_count != 1:
        # Race: someone (another tab?) drained the balance between the check
        # above and this debit. Refuse cleanly so no free card is granted.
        raise HTTPException(status_code=402, detail="Insufficient coins.")

    existing = await db.user_cards.find_one({"user_id": user["id"], "card_id": card_id})
    if existing:
        await db.user_cards.update_one(
            {"id": existing["id"]},
            {"$inc": {"uses_remaining": uses_granted, "uses_left": uses_granted}},
        )
        uc_id = existing["id"]
    else:
        uc_id = new_id()
        await db.user_cards.insert_one({
            "id": uc_id, "user_id": user["id"], "card_id": card_id,
            "uses_remaining": uses_granted, "uses_left": uses_granted,
            "total_uses": 0,
            "acquired_via": "purchase",
            "purchase_reference": payment_reference,
            "acquired_at": datetime.now(timezone.utc).isoformat(),
        })
    pool_usd_cents = coins_to_usd_cents(total_coins)
    await db.card_transactions.insert_one({
        "id": new_id(), "user_id": user["id"], "card_id": card_id,
        "user_card_id": uc_id, "type": "purchase",
        "quantity": quantity,
        "amount_coins": total_coins,
        "amount_usd_cents": pool_usd_cents,
        "reference": payment_reference,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await _contribute_to_pool(db, pool_usd_cents, user["id"], "card_purchase", payment_reference)
    await _referrer_credit(db, user["id"], pool_usd_cents)
    # Re-read fresh balance to surface to the client.
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0, "coins": 1})
    return {
        "ok": True,
        "user_card_id": uc_id,
        "quantity": quantity,
        "uses_granted": uses_granted,
        "amount_coins": total_coins,
        "coins": int((fresh or {}).get("coins") or 0),
    }


@router.post("/purchase")
async def purchase_card(body: PurchaseIn, user: dict = Depends(a.get_current_user)):
    """Create/top-up a user_card after a successful payment. Body must include
    `card_id`; `quantity` defaults to 1. 50% of revenue → WC prize pool."""
    if not body.card_id:
        raise HTTPException(status_code=400, detail="card_id is required")
    return await _purchase_card_impl(get_db(), user, body.card_id, body.quantity, body.payment_reference)


@router.post("/{card_id}/purchase")
async def purchase_card_by_path(card_id: str, body: PurchaseIn, user: dict = Depends(a.get_current_user)):
    """Same as POST /purchase but the card_id is in the URL path —
    matches the existing frontend call signature `/api/cards/{id}/purchase`."""
    return await _purchase_card_impl(get_db(), user, card_id, body.quantity, body.payment_reference)


@router.post("/recharge")
async def recharge_card(body: RechargeIn, user: dict = Depends(a.get_current_user)):
    """Add +1 use to an owned card for 100 coins."""
    db = get_db()
    uc = await db.user_cards.find_one({"id": body.user_card_id, "user_id": user["id"]})
    if not uc:
        raise HTTPException(status_code=404, detail="Card not in your collection")
    # Atomic coin debit
    debit = await db.users.update_one(
        {"id": user["id"], "coins": {"$gte": RECHARGE_PRICE_COINS}},
        {"$inc": {"coins": -RECHARGE_PRICE_COINS}},
    )
    if debit.modified_count != 1:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient coins. Recharge costs {RECHARGE_PRICE_COINS} coins.",
        )
    await db.user_cards.update_one(
        {"id": uc["id"]},
        {"$inc": {"uses_remaining": RECHARGE_USES, "uses_left": RECHARGE_USES}},
    )
    pool_usd_cents = coins_to_usd_cents(RECHARGE_PRICE_COINS)
    await db.card_transactions.insert_one({
        "id": new_id(), "user_id": user["id"], "card_id": uc.get("card_id"),
        "user_card_id": uc["id"], "type": "recharge",
        "amount_coins": RECHARGE_PRICE_COINS,
        "amount_usd_cents": pool_usd_cents,
        "reference": body.payment_reference,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await _contribute_to_pool(db, pool_usd_cents, user["id"], "card_recharge", body.payment_reference)
    await _referrer_credit(db, user["id"], pool_usd_cents)
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0, "coins": 1})
    return {
        "ok": True,
        "uses_added": RECHARGE_USES,
        "amount_coins": RECHARGE_PRICE_COINS,
        "coins": int((fresh or {}).get("coins") or 0),
    }


async def _referrer_credit(db, buyer_user_id: str, amount_cents: int):
    """When the buyer was referred by someone, increment that referrer's earnings counter.

    Two effects on the referrer:
      1. USD credit (10% of the spend) — counted in the referrals leaderboard.
      2. Fantasy leaderboard points — +50 one-time bonus the first time their
         referred user spends ANY money (activates the referral) so the referrer
         climbs both the referral AND the main fantasy leaderboards.
    """
    buyer = await db.users.find_one({"id": buyer_user_id}, {"_id": 0, "referred_by_user_id": 1})
    if not buyer or not buyer.get("referred_by_user_id"):
        return
    referrer_id = buyer["referred_by_user_id"]
    # 10% kickback as referral credit (for leaderboard ranking only — not actual money)
    credit = int(amount_cents * 0.10)
    existing = await db.referrals.find_one(
        {"referrer_user_id": referrer_id, "referred_user_id": buyer_user_id},
        {"_id": 0, "referred_spend_usd_cents": 1},
    )
    was_inactive = not existing or (existing.get("referred_spend_usd_cents") or 0) == 0
    await db.referrals.update_one(
        {"referrer_user_id": referrer_id, "referred_user_id": buyer_user_id},
        {
            "$inc": {"credit_earned_usd_cents": credit, "referred_spend_usd_cents": amount_cents},
            "$setOnInsert": {
                "id": new_id(),
                "referrer_user_id": referrer_id, "referred_user_id": buyer_user_id,
                "joined_at": datetime.now(timezone.utc).isoformat(),
                "status": "active",
            },
            "$set": {"status": "active", "activated_at": datetime.now(timezone.utc).isoformat()},
        },
        upsert=True,
    )
    # First-activation bonus on the main fantasy leaderboard.
    if was_inactive and amount_cents > 0:
        REFERRAL_BONUS_POINTS = 50
        sq = await db.fantasy_squads.find_one({"user_id": referrer_id}, {"_id": 0, "id": 1})
        if sq:
            await db.fantasy_squads.update_one(
                {"id": sq["id"]},
                {"$inc": {"total_points": REFERRAL_BONUS_POINTS, "referral_bonus_points": REFERRAL_BONUS_POINTS}},
            )
        await db.audit_log.insert_one({
            "id": new_id(),
            "user_id": referrer_id,
            "action": "referral_bonus_awarded",
            "metadata": {
                "referred_user_id": buyer_user_id,
                "points": REFERRAL_BONUS_POINTS,
                "first_spend_usd_cents": amount_cents,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
