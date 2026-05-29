"""Iteration 7 — USD pricing, WC-only predictions, referrals, prize pool admin."""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fantasy-wc.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@cloudypitch.com"
ADMIN_PASS = "CloudyAdmin2026!"


@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/signin", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def anon_session():
    return requests.Session()


# ---------- Cards (USD pricing) ----------
def test_cards_currency_usd(anon_session):
    r = anon_session.get(f"{BASE_URL}/api/cards")
    assert r.status_code == 200
    data = r.json()
    assert data["currency"] == "USD"
    assert data["recharge_price_usd_cents"] == 20
    assert data["pool_contribution_ratio"] == 0.50
    tiers = data["tiers"]
    assert tiers["1"]["price_usd_cents"] == 200
    assert tiers["2"]["price_usd_cents"] == 100
    assert tiers["3"]["price_usd_cents"] == 50
    # every card has price_usd_cents
    for c in data["cards"]:
        assert "price_usd_cents" in c, f"card {c.get('id')} missing price_usd_cents"


# ---------- Predictions WC-only gate ----------
def test_predictions_upcoming_scope_wc(anon_session):
    r = anon_session.get(f"{BASE_URL}/api/predictions/upcoming")
    assert r.status_code == 200
    data = r.json()
    assert data["scope"] == "world_cup_2026"
    # All returned matches must be WC
    for m in data["matches"]:
        assert (
            m.get("is_world_cup")
            or m.get("competition_id") == "wc-2026"
            or m.get("sportmonks_league_id") == 732
        ), f"non-WC match leaked: {m.get('id')}"


def test_predictions_post_non_wc_returns_403(admin_session):
    # find any non-WC match
    r = admin_session.get(f"{BASE_URL}/api/matches?limit=20")
    if r.status_code != 200:
        pytest.skip("No /api/matches endpoint or no data")
    payload = r.json()
    matches = payload.get("matches") or payload if isinstance(payload, list) else payload.get("matches", [])
    non_wc = None
    for m in matches:
        if not (m.get("is_world_cup") or m.get("competition_id") == "wc-2026" or m.get("sportmonks_league_id") == 732):
            non_wc = m
            break
    if not non_wc:
        pytest.skip("No non-WC match available to test 403")
    resp = admin_session.post(
        f"{BASE_URL}/api/predictions",
        json={"match_id": non_wc["id"], "home_score_predicted": 1, "away_score_predicted": 0, "card_ids": []},
    )
    assert resp.status_code == 403, f"Expected 403 got {resp.status_code}: {resp.text}"
    assert "World Cup" in resp.json().get("detail", "")


# ---------- Referrals ----------
def test_referrals_me_signed_out(anon_session):
    r = anon_session.get(f"{BASE_URL}/api/referrals/me")
    assert r.status_code in (401, 403)


def test_referrals_me_admin(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/referrals/me")
    assert r.status_code == 200
    data = r.json()
    code = data["referral_code"]
    assert isinstance(code, str) and len(code) == 8
    # Crockford base32 alphabet
    alphabet = set("23456789ABCDEFGHJKMNPQRSTUVWXYZ")
    assert set(code).issubset(alphabet), f"non-Crockford char in {code}"
    assert "count" in data
    assert "active_count" in data
    assert "total_credits_usd_cents" in data
    assert "total_referred_spend_usd_cents" in data
    assert isinstance(data["referrals"], list)
    # Store for other tests
    pytest.admin_referral_code = code


def test_referrals_leaderboard(anon_session):
    r = anon_session.get(f"{BASE_URL}/api/referrals/leaderboard")
    assert r.status_code == 200
    data = r.json()
    assert "leaderboard" in data
    assert isinstance(data["leaderboard"], list)
    pool = data["pool"]
    assert pool is not None, "pool-referrals seed missing"
    assert pool["id"] == "pool-referrals"
    assert pool["amount_usd_cents"] == 500000
    assert pool["currency"] == "USD"


def test_referrals_validate_invalid(anon_session):
    r = anon_session.post(f"{BASE_URL}/api/referrals/validate/ZZZZZZZZ")
    assert r.status_code == 404


def test_referrals_validate_valid(anon_session, admin_session):
    # ensure code generated
    me = admin_session.get(f"{BASE_URL}/api/referrals/me").json()
    code = me["referral_code"]
    r = anon_session.post(f"{BASE_URL}/api/referrals/validate/{code}")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "referrer_name" in body


# ---------- Signup with referral ----------
@pytest.fixture(scope="session")
def new_user(admin_session):
    """Create a new user signed up with admin's referral code."""
    me = admin_session.get(f"{BASE_URL}/api/referrals/me").json()
    code = me["referral_code"]
    suffix = uuid.uuid4().hex[:8]
    email = f"testuser-{suffix}@example.com"
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/signup",
        json={
            "email": email,
            "password": "TestPass123!",
            "display_name": f"Tester {suffix}",
            "country_code": "NG",
            "referral_code": code,
        },
    )
    assert r.status_code in (200, 201), f"signup failed: {r.status_code} {r.text}"
    return {"session": s, "email": email, "admin_code": code}


def _me(session):
    body = session.get(f"{BASE_URL}/api/auth/me").json()
    return body.get("user", body)


def test_signup_with_referral_links_user(new_user, admin_session):
    user = _me(new_user["session"])
    # public_user must expose referral_code
    assert user.get("referral_code"), f"new user has no referral_code: {user}"
    assert len(user["referral_code"]) == 8
    # And it's different from admin's
    admin_me = admin_session.get(f"{BASE_URL}/api/referrals/me").json()
    assert user["referral_code"] != admin_me["referral_code"]
    # referred_by_user_id should be admin
    admin_user = _me(admin_session)
    # We can't read referred_by_user_id from public /me, so verify indirectly via admin's referrals list
    refs = admin_me.get("referrals", [])
    found = any(r.get("referred_user_id") == user["id"] for r in refs)
    assert found, "new user not linked to admin via referrals row"


def test_signup_referrer_sees_new_referral(new_user, admin_session):
    me = admin_session.get(f"{BASE_URL}/api/referrals/me").json()
    refs = me.get("referrals", [])
    new_user_me = _me(new_user["session"])
    found = any(r.get("referred_user_id") == new_user_me["id"] for r in refs)
    assert found, f"new user {new_user_me['id']} not in admin's referrals list"


# ---------- Card purchase contribution flow ----------
def test_card_purchase_contributes_to_pool(admin_session):
    # snapshot pool
    r = admin_session.get(f"{BASE_URL}/api/prize-pools/pool-wc2026-fantasy")
    assert r.status_code == 200, r.text
    pool_before = r.json()["pool"]
    amount_before = pool_before.get("amount_usd_cents") or 0

    # pick any tier-1 card
    cards = admin_session.get(f"{BASE_URL}/api/cards").json()["cards"]
    tier1 = next((c for c in cards if c.get("tier") == 1), None)
    assert tier1, "no tier-1 card found"

    pay_ref = f"TEST_REF_{uuid.uuid4().hex[:8]}"
    resp = admin_session.post(
        f"{BASE_URL}/api/cards/purchase",
        json={"card_id": tier1["id"], "payment_reference": pay_ref},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["amount_usd_cents"] == 200

    # pool went up by 100 (50%)
    r2 = admin_session.get(f"{BASE_URL}/api/prize-pools/pool-wc2026-fantasy")
    amount_after = r2.json()["pool"].get("amount_usd_cents") or 0
    assert amount_after - amount_before == 100, f"expected +100, got +{amount_after - amount_before}"

    # contribution row visible in audit
    contribs = admin_session.get(f"{BASE_URL}/api/prize-pools/pool-wc2026-fantasy/contributions").json()
    found = any(c.get("reference") == pay_ref and c.get("amount_usd_cents") == 100 for c in contribs["contributions"])
    assert found, "contribution row not found in audit log"


def test_card_recharge_contributes(admin_session):
    # find an owned card
    mine = admin_session.get(f"{BASE_URL}/api/cards/me").json().get("owned", [])
    assert mine, "admin should own at least one card after purchase"
    uc = mine[0]
    r = admin_session.get(f"{BASE_URL}/api/prize-pools/pool-wc2026-fantasy")
    before = r.json()["pool"].get("amount_usd_cents") or 0
    resp = admin_session.post(
        f"{BASE_URL}/api/cards/recharge",
        json={"user_card_id": uc["id"], "payment_reference": f"TEST_RC_{uuid.uuid4().hex[:6]}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["amount_usd_cents"] == 20
    after = admin_session.get(f"{BASE_URL}/api/prize-pools/pool-wc2026-fantasy").json()["pool"].get("amount_usd_cents") or 0
    assert after - before == 10, f"expected +10, got +{after - before}"


# ---------- Admin PATCH prize pool ----------
def test_admin_patch_prize_pool(admin_session):
    new_amount = 5000000  # $50,000
    payout = [{"rank_min": 1, "rank_max": 1, "pct": 50}, {"rank_min": 2, "rank_max": 10, "pct": 50}]
    r = admin_session.patch(
        f"{BASE_URL}/api/prize-pools/pool-wc2026-fantasy",
        json={"amount_usd_cents": new_amount, "payout_structure": payout},
    )
    assert r.status_code == 200, r.text
    pool = r.json()["pool"]
    assert pool["amount_usd_cents"] == new_amount
    assert pool["payout_structure"] == payout
    # GET back confirms
    g = admin_session.get(f"{BASE_URL}/api/prize-pools/pool-wc2026-fantasy").json()["pool"]
    assert g["amount_usd_cents"] == new_amount
    assert g["payout_structure"] == payout


def test_admin_patch_non_admin_forbidden(anon_session):
    r = anon_session.patch(
        f"{BASE_URL}/api/prize-pools/pool-wc2026-fantasy",
        json={"amount_usd_cents": 1},
    )
    assert r.status_code in (401, 403)


# ---------- Referred-user purchase grants referrer credit ----------
def test_referred_purchase_credits_referrer(new_user, admin_session):
    """When referred user buys a card, admin's referrals[] row should show credit + spend."""
    # admin already has the pool patched amount, snapshot referrals first
    admin_me_before = admin_session.get(f"{BASE_URL}/api/referrals/me").json()
    nu_id = _me(new_user["session"])["id"]
    before_row = next((r for r in admin_me_before["referrals"] if r.get("referred_user_id") == nu_id), {})
    credit_before = before_row.get("credit_earned_usd_cents", 0) or 0
    spend_before = before_row.get("referred_spend_usd_cents", 0) or 0

    # New user buys a tier-1 card
    cards = new_user["session"].get(f"{BASE_URL}/api/cards").json()["cards"]
    tier1 = next((c for c in cards if c.get("tier") == 1), None)
    assert tier1
    resp = new_user["session"].post(
        f"{BASE_URL}/api/cards/purchase",
        json={"card_id": tier1["id"], "payment_reference": f"TEST_REFB_{uuid.uuid4().hex[:6]}"},
    )
    assert resp.status_code == 200, resp.text

    admin_me_after = admin_session.get(f"{BASE_URL}/api/referrals/me").json()
    after_row = next((r for r in admin_me_after["referrals"] if r.get("referred_user_id") == nu_id), {})
    credit_after = after_row.get("credit_earned_usd_cents", 0) or 0
    spend_after = after_row.get("referred_spend_usd_cents", 0) or 0
    assert credit_after - credit_before == 20, f"expected +20 credit (10% of 200), got +{credit_after - credit_before}"
    assert spend_after - spend_before == 200, f"expected +200 spend, got +{spend_after - spend_before}"
