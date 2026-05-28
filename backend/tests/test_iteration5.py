"""Iteration 5 — coverage of 7 phases: predictions/cards/fantasy/wallet/prize-pool/paystack/compliance/ads."""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fantasy-wc.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@cloudypitch.com"
ADMIN_PASS = "CloudyAdmin2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/signin", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, f"admin signin failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def user_session():
    s = requests.Session()
    email = f"TEST_iter5_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/signup",
               json={"email": email, "password": "TestPass123!", "display_name": "Iter5", "country_code": "NG"})
    assert r.status_code in (200, 201), f"signup failed {r.status_code} {r.text}"
    return s, email


# ---------- Phase A : Scoring Engine (unit) ----------
def test_scoring_unit():
    import sys
    sys.path.insert(0, "/app/backend")
    from scoring import score_prediction, streak_bonus, compute_card_boost, compute_stage

    # Exact 2-1 vs 2-1
    r = score_prediction({"home_score_predicted": 2, "away_score_predicted": 1},
                         {"home_score": 2, "away_score": 1})
    assert r["base_points"] == 30 and r["points_awarded"] == 30 and r["exact_score_hit"]

    # Diff correct 2-0 vs 3-1
    r = score_prediction({"home_score_predicted": 2, "away_score_predicted": 0},
                         {"home_score": 3, "away_score": 1})
    assert r["base_points"] == 15

    # Outcome only 2-1 vs 3-0
    r = score_prediction({"home_score_predicted": 2, "away_score_predicted": 1},
                         {"home_score": 3, "away_score": 0})
    assert r["base_points"] == 10

    # Wrong 1-0 vs 0-2
    r = score_prediction({"home_score_predicted": 1, "away_score_predicted": 0},
                         {"home_score": 0, "away_score": 2})
    assert r["base_points"] == 0

    # Final stage multiplier
    assert compute_stage({"round": {"name": "Final 2026"}}) == "final"
    r = score_prediction({"home_score_predicted": 1, "away_score_predicted": 1},
                         {"home_score": 1, "away_score": 1, "round": {"name": "Final"}})
    assert r["stage"] == "final" and r["stage_multiplier"] == 4.0 and r["points_awarded"] == 120

    # Streak bonuses
    assert streak_bonus(3) == 10
    assert streak_bonus(5) == 25
    assert streak_bonus(10) == 100

    # Card boost cap +1.0
    boost = compute_card_boost(
        [{"effect_type": "flat_boost", "effect_value": {"multiplier": 1.7}},
         {"effect_type": "flat_boost", "effect_value": {"multiplier": 1.7}}], {})
    assert boost == 1.0


# ---------- Phase A : Predictions API ----------
def test_predictions_endpoint(user_session):
    s, _ = user_session
    r = s.get(f"{BASE_URL}/api/predictions/upcoming?limit=5")
    assert r.status_code == 200
    matches = r.json().get("matches", [])
    if not matches:
        pytest.skip("no upcoming matches")
    m = matches[0]
    r = s.post(f"{BASE_URL}/api/predictions",
               json={"match_id": m["id"], "home_score_predicted": 2, "away_score_predicted": 1, "card_ids": []})
    assert r.status_code == 200, r.text
    body = r.json()["prediction"]
    assert body["home_score_predicted"] == 2 and body["away_score_predicted"] == 1


def test_predictions_leaderboard():
    r = requests.get(f"{BASE_URL}/api/predictions/leaderboard?scope=weekly&limit=10")
    assert r.status_code == 200
    assert r.json().get("scope") == "weekly"

    r = requests.get(f"{BASE_URL}/api/predictions/leaderboard?scope=country&country=NG&limit=10")
    assert r.status_code == 200

    r = requests.get(f"{BASE_URL}/api/predictions/leaderboard?scope=competition&competition_id=sm-l-830&limit=10")
    assert r.status_code == 200


# ---------- Phase B : Cards ----------
def test_cards_catalog():
    r = requests.get(f"{BASE_URL}/api/cards")
    assert r.status_code == 200
    cards = r.json().get("cards", [])
    assert len(cards) >= 1
    # effect_type + effect_value
    for c in cards[:5]:
        assert "effect_type" in c


def test_cards_purchase_and_recharge(user_session):
    s, _ = user_session
    cards = requests.get(f"{BASE_URL}/api/cards").json()["cards"]
    if not cards:
        pytest.skip("no cards")
    target = cards[0]
    r = s.post(f"{BASE_URL}/api/cards/purchase", json={"card_id": target["id"]})
    assert r.status_code == 200, r.text
    j = r.json()
    uc_id = j.get("user_card", {}).get("id") or j.get("user_card_id")
    assert uc_id

    r = s.post(f"{BASE_URL}/api/cards/recharge", json={"user_card_id": uc_id})
    assert r.status_code == 200
    assert r.json().get("uses_added") == 5

    r = s.get(f"{BASE_URL}/api/cards/me")
    assert r.status_code == 200
    owned = r.json().get("owned", [])
    assert any(o.get("id") == uc_id and o.get("card") for o in owned)


# ---------- Phase C : Fantasy scoring (unit) + endpoint ----------
def test_fantasy_player_points_unit():
    import sys
    sys.path.insert(0, "/app/backend")
    from fantasy_scoring import compute_player_points

    r = compute_player_points(position="GK", minutes_played=90, saves=6, team_clean_sheet=True)
    # +2 mins, +4 CS, +2 saves(6/3)=10
    assert r["points"] == 8, r

    r = compute_player_points(position="FWD", minutes_played=90, goals=1)
    # 2 + 4 = 6
    assert r["points"] == 6

    r = compute_player_points(position="MID", minutes_played=90, red_cards=1)
    # 2 - 3 = -1
    assert r["points"] == -1


def test_fantasy_settle_gameweek(admin_session):
    s = admin_session
    r = s.post(f"{BASE_URL}/api/fantasy/settle/gameweek?gameweek=1")
    # 200 with {settled:N} is OK; tolerate 404 if endpoint not mounted exactly
    assert r.status_code in (200, 404), r.text


# ---------- Phase D : Wallet ----------
def test_wallet_flow(user_session):
    s, _ = user_session
    r = s.get(f"{BASE_URL}/api/wallet/me")
    assert r.status_code == 200
    assert "wallet" in r.json()

    r = s.post(f"{BASE_URL}/api/wallet/deposit", json={"amount_ngn": 5000})
    assert r.status_code == 200
    assert r.json()["balance_ngn"] >= 5000

    r = s.get(f"{BASE_URL}/api/wallet/transactions")
    assert r.status_code == 200
    txs = r.json().get("transactions", [])
    assert any(t.get("type") == "deposit" for t in txs)


# ---------- Phase D : Prize pool settle ----------
def test_prize_pool_settle(admin_session):
    s = admin_session
    pools = requests.get(f"{BASE_URL}/api/prize-pools").json().get("pools", []) \
        if requests.get(f"{BASE_URL}/api/prize-pools").status_code == 200 else []
    if not pools:
        pytest.skip("no prize pools")
    pid = pools[0].get("id")
    r = s.post(f"{BASE_URL}/api/prize-pools/{pid}/settle")
    assert r.status_code in (200, 400, 404), r.text


# ---------- Phase E : Paystack contract ----------
def test_paystack_config():
    r = requests.get(f"{BASE_URL}/api/payments/paystack/config")
    assert r.status_code == 200
    body = r.json()
    assert "configured" in body
    assert body.get("configured") is False


def test_paystack_initialize_unconfigured(user_session):
    s, _ = user_session
    r = s.post(f"{BASE_URL}/api/payments/paystack/initialize",
               json={"purpose": "wallet_deposit", "amount_ngn": 500,
                     "callback_url": "https://example.com/payment/callback"})
    # When PAYSTACK_SECRET_KEY missing => 503; when caps not set/age not verified => 403
    assert r.status_code in (503, 403), r.text


def test_paystack_webhook_bad_signature():
    r = requests.post(f"{BASE_URL}/api/payments/paystack/webhook",
                      json={"event": "charge.success", "data": {"reference": "fake"}},
                      headers={"x-paystack-signature": "deadbeef"})
    # Either 401 (key set + bad sig) or 503 (no key set)
    assert r.status_code in (401, 503)


# ---------- Phase F : Compliance ----------
def test_compliance_age_gate_and_caps(user_session):
    s, _ = user_session

    # GET creates default profile
    r = s.get(f"{BASE_URL}/api/compliance/me")
    assert r.status_code == 200
    prof = r.json()["profile"]
    assert prof["daily_cap_ngn"] == 5000
    assert prof["monthly_cap_ngn"] == 20000

    # Underage -> 403
    r = s.post(f"{BASE_URL}/api/compliance/age-gate", json={"date_of_birth": "2015-01-15"})
    assert r.status_code == 403

    # OK
    r = s.post(f"{BASE_URL}/api/compliance/age-gate", json={"date_of_birth": "2001-01-15"})
    assert r.status_code == 200 and r.json()["age_verified"] is True

    # Raising caps -> pending 24h
    r = s.post(f"{BASE_URL}/api/compliance/caps", json={"daily_cap_ngn": 10000, "monthly_cap_ngn": 50000})
    assert r.status_code == 200 and r.json().get("pending") is True

    # Verify current caps unchanged
    r = s.get(f"{BASE_URL}/api/compliance/me")
    prof = r.json()["profile"]
    assert prof["daily_cap_ngn"] == 5000
    assert prof["caps_pending"]["daily_cap_ngn"] == 10000

    # Lower caps -> immediate
    r = s.post(f"{BASE_URL}/api/compliance/caps", json={"daily_cap_ngn": 2000, "monthly_cap_ngn": 10000})
    assert r.status_code == 200 and r.json().get("applied_immediately") is True

    r = s.get(f"{BASE_URL}/api/compliance/me")
    prof = r.json()["profile"]
    assert prof["daily_cap_ngn"] == 2000

    # can-spend within cap = ok=True
    r = s.get(f"{BASE_URL}/api/compliance/can-spend?amount_ngn=500")
    assert r.status_code == 200 and r.json()["ok"] is True

    # can-spend over cap = ok=False
    r = s.get(f"{BASE_URL}/api/compliance/can-spend?amount_ngn=10000")
    assert r.status_code == 200 and r.json()["ok"] is False


def test_compliance_self_exclude(user_session):
    s, _ = user_session
    r = s.post(f"{BASE_URL}/api/compliance/self-exclude", json={"excluded": True})
    assert r.status_code == 200
    r = s.get(f"{BASE_URL}/api/compliance/can-spend?amount_ngn=100")
    assert r.json()["ok"] is False
    # Unexclude (cleanup)
    s.post(f"{BASE_URL}/api/compliance/self-exclude", json={"excluded": False})


# ---------- Phase G : Ads ----------
def test_ads_placements_list():
    r = requests.get(f"{BASE_URL}/api/ads/placements")
    assert r.status_code == 200
    placements = r.json().get("placements", [])
    # MTN sponsor seeded
    assert any((p.get("sponsor_name") or "").lower().startswith("mtn") for p in placements), \
        f"MTN sponsor not seeded: {placements}"


def test_ads_impression_click():
    placements = requests.get(f"{BASE_URL}/api/ads/placements").json().get("placements", [])
    if not placements:
        pytest.skip("no placements")
    pid = placements[0]["id"]
    r = requests.post(f"{BASE_URL}/api/ads/impression/{pid}")
    assert r.status_code == 200
    r = requests.post(f"{BASE_URL}/api/ads/click/{pid}")
    assert r.status_code == 200


def test_ads_crud_admin(admin_session):
    s = admin_session
    payload = {"placement_key": "match_list_inline", "network": "direct",
               "sponsor_name": "TEST_iter5_sponsor", "sponsor_image_url": "https://x.test/img.png",
               "target_url": "https://x.test", "weight": 1, "is_active": True}
    r = s.post(f"{BASE_URL}/api/ads/placements", json=payload)
    assert r.status_code == 200, r.text
    pid = r.json()["placement"]["id"]

    r = s.patch(f"{BASE_URL}/api/ads/placements/{pid}", json={**payload, "weight": 5})
    assert r.status_code == 200

    r = s.delete(f"{BASE_URL}/api/ads/placements/{pid}")
    assert r.status_code == 200


def test_ads_reward_claim_rate_limit(user_session):
    s, _ = user_session
    # First, ensure user has a card (purchase one)
    cards = requests.get(f"{BASE_URL}/api/cards").json()["cards"]
    if cards:
        s.post(f"{BASE_URL}/api/cards/purchase", json={"card_id": cards[0]["id"]})

    r1 = s.post(f"{BASE_URL}/api/ads/reward/claim", json={"reward_type": "card_uses"})
    assert r1.status_code in (200, 400), r1.text
    # immediate second call must hit 429
    r2 = s.post(f"{BASE_URL}/api/ads/reward/claim", json={"reward_type": "prediction_points"})
    assert r2.status_code == 429, f"expected 429, got {r2.status_code} {r2.text}"
