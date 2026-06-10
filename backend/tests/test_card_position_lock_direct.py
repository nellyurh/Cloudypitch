"""Direct DB test of card position-lock at the API boundary.

Seeds a synthetic user_card pointing at a real FWD-locked legend card, then
calls /api/fantasy/squad targeting that card to a DEF picked-player. Asserts
the API returns 400 with the position-lock message.

This exercises the actual validation path in routes/fantasy.py without
needing wallet balance to purchase a card.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(HERE)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(os.path.join(BACKEND_DIR, ".env"))
except Exception:
    pass

from db import init_db, get_db, utcnow_iso  # noqa: E402

BASE = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE:
    fe_env = os.path.join(BACKEND_DIR, "..", "frontend", ".env")
    if os.path.exists(fe_env):
        for ln in open(fe_env):
            if ln.startswith("REACT_APP_BACKEND_URL"):
                BASE = ln.split("=", 1)[1].strip()
                break
assert BASE
BASE = BASE.rstrip("/")


async def _seed_user_card_and_get_session(db):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"poslock2_{int(time.time())}_{uuid.uuid4().hex[:4]}@test.example"
    pw = "TestPass123!"
    r = s.post(f"{BASE}/api/auth/signup", json={
        "email": email, "password": pw, "display_name": "PosLock2",
    })
    assert r.status_code in (200, 201), r.text
    me = s.get(f"{BASE}/api/auth/me").json()
    user_id = me["user"]["id"]

    # Find a FWD-only card directly in Mongo
    fwd_card = await db.legend_cards.find_one({"position": "FWD", "tier": 1}, {"_id": 0})
    assert fwd_card, "expected at least one FWD-only GOAT card seeded"

    # Insert a user_card directly so the user "owns" it with uses
    uc_id = f"poslock2_{uuid.uuid4().hex[:8]}"
    await db.user_cards.insert_one({
        "id": uc_id, "user_id": user_id, "card_id": fwd_card["id"],
        "uses_remaining": 5, "uses_left": 5, "total_uses": 0,
        "acquired_via": "test_seed",
        "acquired_at": utcnow_iso(),
    })

    return s, user_id, uc_id, fwd_card


async def main() -> int:
    init_db()
    db = get_db()
    s, user_id, uc_id, fwd_card = await _seed_user_card_and_get_session(db)
    try:
        # Find a DEF and a FWD player
        players = s.get(f"{BASE}/api/fantasy/players?wc=true&limit=2000").json()["players"]
        def_p = next((p for p in players if p.get("position") == "DEF"), None)
        fwd_p = next((p for p in players if p.get("position") == "FWD"), None)
        if not (def_p and fwd_p):
            print("SKIP: not enough seeded players to run")
            return 0

        # 1) Attempt: apply FWD card to a DEF — MUST 400 with position lock
        bad = s.post(f"{BASE}/api/fantasy/squad", json={
            "competition_id": "fantasy-wc2026",
            "squad_name": "PosLock2",
            "captain_id": fwd_p["id"],
            "vice_captain_id": def_p["id"],
            "formation": "4-3-3",
            "bench_ids": [],
            "players": [
                {"player_id": def_p["id"], "position": "DEF", "is_starting": True, "price_paid": 5.0},
                {"player_id": fwd_p["id"], "position": "FWD", "is_starting": True, "price_paid": 7.0},
            ],
            "mode": "15",
            "applied_cards": [
                {"user_card_id": uc_id, "target_player_id": def_p["id"]},
            ],
        })
        assert bad.status_code == 400, f"expected 400 pos-lock, got {bad.status_code} {bad.text}"
        msg = bad.text.lower()
        assert ("fwd" in msg and ("only" in msg or "boost" in msg)), \
            f"expected 'FWD only/boost' in error, got: {bad.text}"
        print("PASS  reject: FWD card on DEF target →", bad.json().get("detail"))

        # 2) Attempt: apply FWD card to the FWD picked player — MUST 200
        good = s.post(f"{BASE}/api/fantasy/squad", json={
            "competition_id": "fantasy-wc2026",
            "squad_name": "PosLock2",
            "captain_id": fwd_p["id"],
            "vice_captain_id": def_p["id"],
            "formation": "4-3-3",
            "bench_ids": [],
            "players": [
                {"player_id": def_p["id"], "position": "DEF", "is_starting": True, "price_paid": 5.0},
                {"player_id": fwd_p["id"], "position": "FWD", "is_starting": True, "price_paid": 7.0},
            ],
            "mode": "15",
            "applied_cards": [
                {"user_card_id": uc_id, "target_player_id": fwd_p["id"]},
            ],
        })
        assert good.status_code == 200, f"expected 200, got {good.status_code} {good.text}"
        squad = good.json()["squad"]
        ac = squad.get("applied_cards") or []
        assert len(ac) == 1 and ac[0]["target_player_id"] == fwd_p["id"], ac
        print("PASS  accept: FWD card on FWD target — applied_cards persisted")
        return 0
    except AssertionError as e:
        print("FAIL:", e)
        return 1
    finally:
        await db.user_cards.delete_one({"id": uc_id})
        await db.users.delete_one({"id": user_id})
        await db.fantasy_squads.delete_many({"user_id": user_id})


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
