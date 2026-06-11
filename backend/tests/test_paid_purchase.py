"""Direct unit test for the paid card purchase flow.
Validates: zero-balance purchase rejected, funded purchase succeeds, balance debited."""
from __future__ import annotations

import asyncio, os, sys, uuid
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(HERE)
if BACKEND_DIR not in sys.path: sys.path.insert(0, BACKEND_DIR)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(os.path.join(BACKEND_DIR, ".env"))
except Exception: pass

from db import init_db, get_db, utcnow_iso
from routes.cards import _purchase_card_impl
from fastapi import HTTPException

PFX = "paidpurchase_"

async def main():
    init_db()
    db = get_db()
    user_id = f"{PFX}{uuid.uuid4().hex[:8]}"
    await db.users.insert_one({
        "id": user_id, "email": f"{user_id}@test.example",
        "display_name": "Paid Test", "wallet_balance_usd_cents": 0,
    })
    star = await db.legend_cards.find_one({"tier": 3}, {"_id": 0})
    try:
        # 1) Zero-balance must 402
        try:
            await _purchase_card_impl(db, {"id": user_id}, star["id"], 1, None)
            print("FAIL: expected 402"); return 1
        except HTTPException as e:
            assert e.status_code == 402 and "insufficient" in e.detail.lower(), e.detail
            print("PASS  zero-balance → 402:", e.detail)

        # 2) Verify NO card was granted
        owned = await db.user_cards.find({"user_id": user_id}).to_list(length=5)
        assert len(owned) == 0, f"FREE CARD BUG: {owned}"
        print("PASS  inventory clean (no free card)")

        # 3) Top up wallet then buy
        await db.users.update_one({"id": user_id}, {"$set": {"wallet_balance_usd_cents": 100}})
        res = await _purchase_card_impl(db, {"id": user_id}, star["id"], 1, "test-ref")
        assert res["ok"], res
        assert res["amount_usd_cents"] == star["price_usd_cents"]
        print(f"PASS  funded purchase: charged ¢{res['amount_usd_cents']}, new balance ¢{res['wallet_balance_usd_cents']}")

        # 4) Verify balance was debited correctly
        u = await db.users.find_one({"id": user_id})
        expected = 100 - star["price_usd_cents"]
        assert u["wallet_balance_usd_cents"] == expected, f"balance {u['wallet_balance_usd_cents']} vs expected {expected}"
        print(f"PASS  wallet debited: {expected} cents remaining")

        # 5) Try to buy another — should 402 if balance < price
        if expected < star["price_usd_cents"]:
            try:
                await _purchase_card_impl(db, {"id": user_id}, star["id"], 1, None)
                print("FAIL: expected 402 on second buy"); return 1
            except HTTPException as e:
                assert e.status_code == 402
                print("PASS  second buy with low balance → 402")
        return 0
    finally:
        await db.users.delete_one({"id": user_id})
        await db.user_cards.delete_many({"user_id": user_id})
        await db.card_transactions.delete_many({"user_id": user_id})
        await db.wallet_transactions.delete_many({"user_id": user_id})

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
