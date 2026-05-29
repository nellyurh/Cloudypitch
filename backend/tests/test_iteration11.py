"""Iteration 11 — Card consumption + targeting tests.

Covers:
  - GET /api/cards/me/history empty + populated
  - POST /api/wc/games/{id}/enter target_player_id validations
  - duplicate user_card_id, over card_limit
  - successful submit decrements uses + writes card_uses row
  - resubmit with same cards does NOT double-charge
  - resubmit removing a card refunds uses + deletes card_uses row
  - reject when user_card uses_remaining is 0
"""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient
from datetime import datetime, timezone

def _load_env(path):
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass

_load_env("/app/frontend/.env")
_load_env("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fantasy-wc.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "cloudypitch")

ADMIN_EMAIL = "admin@cloudypitch.com"
ADMIN_PASSWORD = "CloudyAdmin2026!"


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    return c[DB_NAME]


@pytest.fixture(scope="module")
def user_session():
    """Signup a fresh test user, return (session, user_id)."""
    s = requests.Session()
    email = f"TEST_it11_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/signup", json={
        "email": email, "password": "TestPass123!", "display_name": "It11"
    })
    assert r.status_code in (200, 201), f"signup failed: {r.status_code} {r.text}"
    me = s.get(f"{BASE_URL}/api/auth/me")
    assert me.status_code == 200
    uid = me.json()["user"]["id"] if "user" in me.json() else me.json()["id"]
    return s, uid


@pytest.fixture(scope="module")
def test_game(mongo):
    """Pick (or create) a wc_game in 'open' status with 22+ eligible players."""
    g = mongo.wc_games.find_one({"status": "open"})
    if not g:
        g = mongo.wc_games.find_one({"status": "upcoming", "eligible_team_ids": {"$exists": True, "$ne": []}})
        assert g, "no wc_game with eligible_team_ids found"
        mongo.wc_games.update_one({"id": g["id"]}, {"$set": {"status": "open"}})
        g["status"] = "open"
    # Make sure cap is reasonable for our tests
    cfg = mongo.wc_game_config.find_one({"id": g.get("config_id")})
    if cfg and (cfg.get("card_limit_current") or 0) < 4:
        mongo.wc_game_config.update_one({"id": cfg["id"]}, {"$set": {"card_limit_current": 4}})
    return g


@pytest.fixture(scope="module")
def eligible_players(mongo, test_game):
    players = list(mongo.players.find(
        {"team_id": {"$in": test_game.get("eligible_team_ids", [])}}, {"_id": 0}
    ).limit(30))
    if len(players) < 11:
        # Fallback: take any 22 players
        players = list(mongo.players.find({}, {"_id": 0}).limit(30))
    assert len(players) >= 11, "not enough players in db"
    return players


def _build_picks(players):
    picks = []
    # Roughly position-correct, but just fill 11
    for p in players[:11]:
        picks.append({
            "player_id": p["id"],
            "team_id": p.get("team_id"),
            "position": p.get("position") or "MID",
        })
    return picks


# ---------- /api/cards/me/history ----------
def test_history_empty_for_new_user(user_session):
    s, _ = user_session
    r = s.get(f"{BASE_URL}/api/cards/me/history")
    assert r.status_code == 200
    body = r.json()
    assert "history" in body
    assert body["history"] == []


# ---------- enter_game validations ----------
def test_enter_card_without_target_returns_400(user_session, mongo, test_game, eligible_players):
    s, uid = user_session
    # Give the user one card with uses
    card = mongo.legend_cards.find_one({}, {"_id": 0})
    assert card, "need at least one legend_card seed"
    uc_id = f"uc-{uuid.uuid4().hex[:8]}"
    mongo.user_cards.insert_one({
        "id": uc_id, "user_id": uid, "card_id": card["id"],
        "uses_remaining": 3, "uses_left": 3, "total_uses": 0,
        "acquired_via": "test", "acquired_at": _now_iso(),
    })
    picks = _build_picks(eligible_players)
    r = s.post(f"{BASE_URL}/api/wc/games/{test_game['id']}/enter", json={
        "player_picks": picks,
        "cards_used": [{"user_card_id": uc_id}],  # no target_player_id
    })
    assert r.status_code == 400, r.text
    assert "target a player" in r.json().get("detail", "").lower()


def test_enter_card_target_not_in_picks_returns_400(user_session, mongo, test_game, eligible_players):
    s, uid = user_session
    uc = mongo.user_cards.find_one({"user_id": uid, "uses_remaining": {"$gt": 0}})
    assert uc
    picks = _build_picks(eligible_players)
    outsider = eligible_players[20]["id"] if len(eligible_players) > 20 else "nonexistent-player"
    # Make sure outsider isn't actually in picks
    if outsider in {p["player_id"] for p in picks}:
        outsider = "definitely-not-a-picked-player-xyz"
    r = s.post(f"{BASE_URL}/api/wc/games/{test_game['id']}/enter", json={
        "player_picks": picks,
        "cards_used": [{"user_card_id": uc["id"], "target_player_id": outsider}],
    })
    assert r.status_code == 400, r.text
    assert "picked players" in r.json().get("detail", "").lower()


def test_enter_duplicate_user_card_id_returns_400(user_session, mongo, test_game, eligible_players):
    s, uid = user_session
    uc = mongo.user_cards.find_one({"user_id": uid, "uses_remaining": {"$gt": 0}})
    picks = _build_picks(eligible_players)
    target = picks[0]["player_id"]
    r = s.post(f"{BASE_URL}/api/wc/games/{test_game['id']}/enter", json={
        "player_picks": picks,
        "cards_used": [
            {"user_card_id": uc["id"], "target_player_id": target},
            {"user_card_id": uc["id"], "target_player_id": picks[1]["player_id"]},
        ],
    })
    assert r.status_code == 400, r.text
    assert "once per game" in r.json().get("detail", "").lower()


def test_enter_exceeds_card_limit_returns_400(user_session, mongo, test_game, eligible_players):
    s, uid = user_session
    # Lower the cap to 1
    cfg = mongo.wc_game_config.find_one({"id": test_game.get("config_id")})
    if not cfg:
        pytest.skip("no config for this game")
    original_cap = cfg.get("card_limit_current", 2)
    mongo.wc_game_config.update_one({"id": cfg["id"]}, {"$set": {"card_limit_current": 1}})
    try:
        # Ensure user has 2 distinct cards
        existing_cards = list(mongo.user_cards.find({"user_id": uid}))
        if len(existing_cards) < 2:
            card_b = list(mongo.legend_cards.find({}, {"_id": 0}).limit(2))
            cb = card_b[1] if len(card_b) > 1 else card_b[0]
            mongo.user_cards.insert_one({
                "id": f"uc-{uuid.uuid4().hex[:8]}", "user_id": uid, "card_id": cb["id"],
                "uses_remaining": 3, "uses_left": 3, "total_uses": 0,
                "acquired_via": "test", "acquired_at": _now_iso(),
            })
        ucs = list(mongo.user_cards.find({"user_id": uid, "uses_remaining": {"$gt": 0}}).limit(2))
        picks = _build_picks(eligible_players)
        r = s.post(f"{BASE_URL}/api/wc/games/{test_game['id']}/enter", json={
            "player_picks": picks,
            "cards_used": [
                {"user_card_id": ucs[0]["id"], "target_player_id": picks[0]["player_id"]},
                {"user_card_id": ucs[1]["id"], "target_player_id": picks[1]["player_id"]},
            ],
        })
        assert r.status_code == 400, r.text
        assert "card limit" in r.json().get("detail", "").lower()
    finally:
        mongo.wc_game_config.update_one({"id": cfg["id"]}, {"$set": {"card_limit_current": original_cap}})


# ---------- Success: consume + audit + resubmit + refund ----------
def test_enter_success_consumes_and_resubmit_no_double_charge_and_refund(user_session, mongo, test_game, eligible_players):
    s, uid = user_session
    # Clean prior entry for this game so test is deterministic
    prev = mongo.wc_game_entries.find_one({"user_id": uid, "wc_game_id": test_game["id"]})
    if prev:
        # refund prior consumed cards
        for cu in prev.get("cards_used", []):
            ucid = cu.get("user_card_id")
            if ucid:
                mongo.user_cards.update_one({"id": ucid}, {"$inc": {"uses_remaining": 1, "uses_left": 1, "total_uses": -1}})
        mongo.card_uses.delete_many({"wc_game_entry_id": prev["id"]})
        mongo.wc_game_entries.delete_one({"id": prev["id"]})

    # Ensure 2 cards exist for user
    ucs = list(mongo.user_cards.find({"user_id": uid}))
    if len(ucs) < 2:
        cards = list(mongo.legend_cards.find({}, {"_id": 0}).limit(2))
        for c in cards[:2 - len(ucs)]:
            mongo.user_cards.insert_one({
                "id": f"uc-{uuid.uuid4().hex[:8]}", "user_id": uid, "card_id": c["id"],
                "uses_remaining": 3, "uses_left": 3, "total_uses": 0,
                "acquired_via": "test", "acquired_at": _now_iso(),
            })
    ucs = list(mongo.user_cards.find({"user_id": uid}))
    # Reset uses to 3 for the two we'll use
    uc_a, uc_b = ucs[0], ucs[1]
    mongo.user_cards.update_one({"id": uc_a["id"]}, {"$set": {"uses_remaining": 3, "uses_left": 3, "total_uses": 0}})
    mongo.user_cards.update_one({"id": uc_b["id"]}, {"$set": {"uses_remaining": 3, "uses_left": 3, "total_uses": 0}})

    picks = _build_picks(eligible_players)

    # FIRST submit with uc_a only
    r1 = s.post(f"{BASE_URL}/api/wc/games/{test_game['id']}/enter", json={
        "player_picks": picks,
        "cards_used": [
            {"user_card_id": uc_a["id"], "target_player_id": picks[0]["player_id"]},
        ],
    })
    assert r1.status_code == 200, r1.text
    # Verify uses_remaining decremented for uc_a, untouched for uc_b
    a1 = mongo.user_cards.find_one({"id": uc_a["id"]})
    b1 = mongo.user_cards.find_one({"id": uc_b["id"]})
    assert a1["uses_remaining"] == 2, f"uc_a uses should be 2 after first consume, got {a1['uses_remaining']}"
    assert a1["total_uses"] == 1
    assert b1["uses_remaining"] == 3
    # card_uses row exists
    cu_rows_a = list(mongo.card_uses.find({"user_card_id": uc_a["id"], "wc_game_id": test_game["id"]}))
    assert len(cu_rows_a) == 1
    assert cu_rows_a[0]["target_player_id"] == picks[0]["player_id"]

    # RESUBMIT — keep uc_a, ADD uc_b. uc_a must NOT be re-charged. uc_b must be consumed.
    r2 = s.post(f"{BASE_URL}/api/wc/games/{test_game['id']}/enter", json={
        "player_picks": picks,
        "cards_used": [
            {"user_card_id": uc_a["id"], "target_player_id": picks[0]["player_id"]},
            {"user_card_id": uc_b["id"], "target_player_id": picks[1]["player_id"]},
        ],
    })
    assert r2.status_code == 200, r2.text
    a2 = mongo.user_cards.find_one({"id": uc_a["id"]})
    b2 = mongo.user_cards.find_one({"id": uc_b["id"]})
    assert a2["uses_remaining"] == 2, f"uc_a should still be 2 (not double-charged), got {a2['uses_remaining']}"
    assert b2["uses_remaining"] == 2, f"uc_b should be 2 after consume, got {b2['uses_remaining']}"
    assert b2["total_uses"] == 1

    # RESUBMIT — REMOVE uc_b → it should be refunded (+1 use, total_uses-1, card_uses row deleted)
    r3 = s.post(f"{BASE_URL}/api/wc/games/{test_game['id']}/enter", json={
        "player_picks": picks,
        "cards_used": [
            {"user_card_id": uc_a["id"], "target_player_id": picks[0]["player_id"]},
        ],
    })
    assert r3.status_code == 200, r3.text
    b3 = mongo.user_cards.find_one({"id": uc_b["id"]})
    assert b3["uses_remaining"] == 3, f"uc_b should be refunded to 3, got {b3['uses_remaining']}"
    assert b3["total_uses"] == 0
    cu_rows_b = list(mongo.card_uses.find({"user_card_id": uc_b["id"], "wc_game_id": test_game["id"]}))
    assert len(cu_rows_b) == 0, "card_uses row for uc_b should be deleted on refund"

    # History endpoint now shows uc_a
    rh = s.get(f"{BASE_URL}/api/cards/me/history")
    assert rh.status_code == 200
    hist = rh.json()["history"]
    assert any(h.get("user_card_id") == uc_a["id"] for h in hist)
    enriched = next(h for h in hist if h.get("user_card_id") == uc_a["id"])
    assert enriched.get("card") is not None
    assert enriched.get("game") is not None
    assert enriched.get("target_player") is not None
    assert enriched["target_player"]["id"] == picks[0]["player_id"]


def test_enter_card_with_zero_uses_returns_400(user_session, mongo, test_game, eligible_players):
    s, uid = user_session
    # Create a fresh card with 0 uses, that's not part of any existing entry
    card = mongo.legend_cards.find_one({}, {"_id": 0})
    zero_uc_id = f"uc-zero-{uuid.uuid4().hex[:8]}"
    mongo.user_cards.insert_one({
        "id": zero_uc_id, "user_id": uid, "card_id": card["id"],
        "uses_remaining": 0, "uses_left": 0, "total_uses": 5,
        "acquired_via": "test", "acquired_at": _now_iso(),
    })
    picks = _build_picks(eligible_players)
    # Get existing entry's cards to preserve them (or empty)
    prev = mongo.wc_game_entries.find_one({"user_id": uid, "wc_game_id": test_game["id"]})
    existing_cards = []
    if prev:
        existing_cards = [{"user_card_id": cu["user_card_id"], "target_player_id": cu.get("target_player_id") or picks[0]["player_id"]}
                          for cu in (prev.get("cards_used") or [])]
    r = s.post(f"{BASE_URL}/api/wc/games/{test_game['id']}/enter", json={
        "player_picks": picks,
        "cards_used": existing_cards + [
            {"user_card_id": zero_uc_id, "target_player_id": picks[2]["player_id"]},
        ],
    })
    assert r.status_code == 400, r.text
    assert "0 uses" in r.json().get("detail", "").lower()
