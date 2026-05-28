"""Iteration 6 — Card picker on Predictions, Premium subscription, AdSlot wiring, InterstitialAd.
Backend coverage: /api/cards/me, /api/predictions accepts card_ids[] (cap=2),
/api/payments/paystack/initialize purpose=premium_sub, /api/auth/me exposes is_premium/premium_until,
regression on existing routes."""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
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
    email = f"TEST_iter6_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/signup",
               json={"email": email, "password": "TestPass123!", "display_name": "Iter6", "country_code": "NG"})
    assert r.status_code in (200, 201), f"signup failed {r.status_code} {r.text}"
    # Age-gate this user (>=18) so paystack initialize can be tested
    s.post(f"{BASE_URL}/api/compliance/age-gate", json={"date_of_birth": "2000-01-15"})
    return s, email


# ---------- /api/auth/me exposes is_premium + premium_until ----------
def test_auth_me_exposes_premium_fields(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/auth/me")
    assert r.status_code == 200, r.text
    body = r.json()
    user = body.get("user") or body
    assert "is_premium" in user, f"is_premium missing from /auth/me payload: {user}"
    assert "premium_until" in user, f"premium_until missing from /auth/me payload: {user}"
    # Default admin should not be premium yet
    assert isinstance(user["is_premium"], bool)


def test_auth_me_premium_fields_new_user(user_session):
    s, _ = user_session
    r = s.get(f"{BASE_URL}/api/auth/me")
    assert r.status_code == 200
    user = (r.json().get("user") or r.json())
    assert user.get("is_premium") is False
    # premium_until may be None
    assert user.get("premium_until") in (None, "", 0) or isinstance(user.get("premium_until"), str)


# ---------- /api/cards/me returns owned with joined card object ----------
def test_cards_me_joins_card_object(user_session):
    s, _ = user_session
    cards = requests.get(f"{BASE_URL}/api/cards").json().get("cards", [])
    if not cards:
        pytest.skip("no cards in catalog")

    # Purchase one card so user has at least one
    target = cards[0]
    s.post(f"{BASE_URL}/api/cards/purchase", json={"card_id": target["id"]})

    r = s.get(f"{BASE_URL}/api/cards/me")
    assert r.status_code == 200, r.text
    owned = r.json().get("owned", [])
    assert len(owned) >= 1, f"expected at least 1 owned card, got: {owned}"
    o = owned[0]
    assert "id" in o
    assert "card" in o and isinstance(o["card"], dict), f"owned item missing nested card object: {o}"
    # nested card has the fields the CardPickerModal needs
    nested = o["card"]
    for fld in ("id", "name", "tier"):
        assert fld in nested, f"nested card missing {fld}: {nested}"


# ---------- /api/predictions accepts card_ids[] and caps at 2 ----------
def test_predictions_accepts_card_ids_capped_at_2(user_session):
    s, _ = user_session
    # Need at least 3 owned cards to test the cap
    cards = requests.get(f"{BASE_URL}/api/cards").json().get("cards", [])
    if len(cards) < 3:
        pytest.skip("not enough catalog cards to test cap")

    owned_ids = []
    for c in cards[:3]:
        r = s.post(f"{BASE_URL}/api/cards/purchase", json={"card_id": c["id"]})
        if r.status_code == 200:
            uc = r.json().get("user_card", {})
            uc_id = uc.get("id") or r.json().get("user_card_id")
            if uc_id:
                owned_ids.append(uc_id)
    if len(owned_ids) < 3:
        # fall back to /api/cards/me
        owned = s.get(f"{BASE_URL}/api/cards/me").json().get("owned", [])
        owned_ids = [o["id"] for o in owned][:3]
    if len(owned_ids) < 3:
        pytest.skip(f"could not obtain 3 owned cards, got {len(owned_ids)}")

    # Get upcoming match
    r = s.get(f"{BASE_URL}/api/predictions/upcoming?limit=5")
    matches = r.json().get("matches", []) if r.status_code == 200 else []
    if not matches:
        pytest.skip("no upcoming matches")
    m = matches[0]

    # Post prediction with 3 card_ids — cap should drop to 2
    r = s.post(f"{BASE_URL}/api/predictions",
               json={"match_id": m["id"], "home_score_predicted": 1, "away_score_predicted": 0,
                     "card_ids": owned_ids[:3]})
    assert r.status_code == 200, r.text
    pred = r.json().get("prediction", {})
    applied = pred.get("applied_card_ids", [])
    assert isinstance(applied, list), f"applied_card_ids not a list: {pred}"
    assert len(applied) <= 2, f"cap not enforced: applied={applied}"
    # All applied ids should be from our owned set
    for aid in applied:
        assert aid in owned_ids, f"foreign applied id: {aid}"


def test_predictions_card_ids_optional_empty(user_session):
    s, _ = user_session
    r = s.get(f"{BASE_URL}/api/predictions/upcoming?limit=5")
    matches = r.json().get("matches", []) if r.status_code == 200 else []
    if not matches:
        pytest.skip("no upcoming matches")
    m = matches[0]
    r = s.post(f"{BASE_URL}/api/predictions",
               json={"match_id": m["id"], "home_score_predicted": 0, "away_score_predicted": 0})
    assert r.status_code == 200, r.text
    pred = r.json().get("prediction", {})
    # applied_card_ids should default to []
    assert pred.get("applied_card_ids", []) == []


# ---------- /api/payments/paystack/initialize purpose='premium_sub' ----------
def test_paystack_initialize_premium_sub_unconfigured(user_session):
    s, _ = user_session
    r = s.post(f"{BASE_URL}/api/payments/paystack/initialize",
               json={"purpose": "premium_sub", "amount_ngn": 2000,
                     "callback_url": "https://example.com/payment/callback"})
    # No key set => 503; not-signed-in/age => 401/403
    assert r.status_code in (503, 401, 403), r.text


def test_paystack_initialize_premium_sub_unauth():
    # Anonymous call must not 500
    r = requests.post(f"{BASE_URL}/api/payments/paystack/initialize",
                      json={"purpose": "premium_sub", "amount_ngn": 2000,
                            "callback_url": "https://example.com/payment/callback"})
    assert r.status_code in (401, 403, 503), r.text


def test_paystack_initialize_invalid_purpose(user_session):
    s, _ = user_session
    r = s.post(f"{BASE_URL}/api/payments/paystack/initialize",
               json={"purpose": "totally_bogus", "amount_ngn": 2000})
    # Pydantic validation 422 or 400
    assert r.status_code in (400, 422), r.text


# ---------- Regression: ad placements seeded for new placements ----------
def test_ads_placements_new_keys_seeded():
    r = requests.get(f"{BASE_URL}/api/ads/placements")
    assert r.status_code == 200
    placements = r.json().get("placements", [])
    keys = {p.get("placement_key") for p in placements}
    # Iteration 6 placements seeded: wc_hub_sponsor, match_list_inline, interstitial_nav
    # At least one of these should exist
    expected_any = {"wc_hub_sponsor", "match_list_inline", "interstitial_nav", "home_bottom_banner"}
    assert keys & expected_any, f"none of expected placements seeded. got: {keys}"


# ---------- Regression: existing routes still load ----------
@pytest.mark.parametrize("path", [
    "/api/auth/me",
    "/api/predictions/upcoming?limit=3",
    "/api/predictions/leaderboard?scope=weekly&limit=5",
    "/api/cards",
    "/api/ads/placements",
    "/api/payments/paystack/config",
])
def test_regression_routes_load(path, admin_session):
    r = admin_session.get(f"{BASE_URL}{path}")
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"


# ---------- Auth me does not leak mongo _id ----------
def test_auth_me_no_mongo_id(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/auth/me")
    user = (r.json().get("user") or r.json())
    assert "_id" not in user, f"mongo _id leaked: {user}"
