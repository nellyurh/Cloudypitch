"""Iteration 26 — Admin kill-switch for Fantasy and Predictions.

Tests:
- GET /api/services/status (public)
- GET /api/admin/services (admin)
- PATCH /api/admin/services/{kind}
- HTTP 423 gating on fantasy/predictions write endpoints
- Idempotent re-enable
- Unknown kind validation
- Leaderboard endpoints NOT gated
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://fantasy-wc.preview.emergentagent.com").rstrip("/")
API = BASE_URL + "/api"

ADMIN_EMAIL = "admin@cloudypitch.com"
ADMIN_PASSWORD = "CloudyAdmin2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/signin", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin signin failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def user_session():
    s = requests.Session()
    email = f"test_kill_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/signup", json={
        "email": email, "password": "TestPass123!", "display_name": "KillTester"
    })
    if r.status_code != 200:
        pytest.skip(f"signup failed: {r.status_code} {r.text}")
    return s


def _reset_all(admin_session):
    """Ensure both services are enabled at start/end."""
    for kind in ("fantasy", "predictions"):
        admin_session.patch(f"{API}/admin/services/{kind}",
                            json={"enabled": True, "shutdown_reason": ""})


# ─── Phase 1: public status ──────────────────────────────────────────
def test_public_status_no_auth():
    r = requests.get(f"{API}/services/status")
    assert r.status_code == 200
    data = r.json()
    assert "fantasy" in data and "predictions" in data
    for k in ("fantasy", "predictions"):
        assert "enabled" in data[k]
        assert "shutdown_reason" in data[k]
        assert "updated_at" in data[k]


# ─── Phase 2: admin list ─────────────────────────────────────────────
def test_admin_list_services(admin_session):
    _reset_all(admin_session)
    r = admin_session.get(f"{API}/admin/services")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "services" in data
    ids = {s["id"] for s in data["services"]}
    assert {"fantasy", "predictions"}.issubset(ids)


def test_admin_list_requires_admin(user_session):
    r = user_session.get(f"{API}/admin/services")
    assert r.status_code in (401, 403)


# ─── Phase 3: PATCH persists + audit log ─────────────────────────────
def test_patch_fantasy_persists(admin_session):
    reason = "Audit in progress"
    r = admin_session.patch(f"{API}/admin/services/fantasy",
                            json={"enabled": False, "shutdown_reason": reason})
    assert r.status_code == 200, r.text
    # Verify public status reflects change
    r2 = requests.get(f"{API}/services/status")
    data = r2.json()
    assert data["fantasy"]["enabled"] is False
    assert data["fantasy"]["shutdown_reason"] == reason
    # Predictions stays enabled
    assert data["predictions"]["enabled"] is True
    # Cleanup
    admin_session.patch(f"{API}/admin/services/fantasy",
                        json={"enabled": True, "shutdown_reason": ""})


def test_patch_predictions_independent(admin_session):
    _reset_all(admin_session)
    r = admin_session.patch(f"{API}/admin/services/predictions",
                            json={"enabled": False, "shutdown_reason": "Pred down"})
    assert r.status_code == 200
    data = requests.get(f"{API}/services/status").json()
    assert data["predictions"]["enabled"] is False
    assert data["fantasy"]["enabled"] is True  # untouched
    _reset_all(admin_session)


# ─── Phase 4: 423 gating ─────────────────────────────────────────────
def test_fantasy_endpoints_return_423_when_paused(admin_session, user_session):
    reason = "Fantasy maintenance"
    admin_session.patch(f"{API}/admin/services/fantasy",
                        json={"enabled": False, "shutdown_reason": reason})
    try:
        # /fantasy/squad — body needs to pass pydantic; gate runs after
        squad_body = {
            "competition_id": "fantasy-wc2026",
            "squad_name": "TEST_GatedSquad",
            "players": [{"player_id": "p1", "position": "GK", "price_paid": 4.0}],
        }
        r = user_session.post(f"{API}/fantasy/squad", json=squad_body)
        assert r.status_code == 423, f"squad: {r.status_code} {r.text}"
        body = r.json()
        detail = body.get("detail", {})
        assert detail.get("code") == "service_paused"
        assert detail.get("service") == "fantasy"
        assert detail.get("reason") == reason

        # /fantasy/transfers/buy
        r = user_session.post(f"{API}/fantasy/transfers/buy",
                              json={"competition_id": "fantasy-wc2026", "player_id": "x", "position": "GK", "price_paid": 4.0})
        assert r.status_code == 423, f"transfers/buy: {r.status_code} {r.text}"

        # /fantasy/transfers/spend
        r = user_session.post(f"{API}/fantasy/transfers/spend",
                              json={"competition_id": "fantasy-wc2026", "count": 1})
        assert r.status_code == 423, f"transfers/spend: {r.status_code} {r.text}"

        # /wc/games/{id}/enter — use a placeholder id; gate runs before lookup
        r = user_session.post(f"{API}/wc/games/dummy_game_id/enter",
                              json={"player_picks": [{"player_id": "p1", "position": "GK", "pick_type": "goals", "pick_value": 1}]})
        assert r.status_code == 423, f"wc/games enter: {r.status_code} {r.text}"
    finally:
        _reset_all(admin_session)


def test_predictions_endpoint_returns_423_when_paused(admin_session, user_session):
    reason = "Predictions maintenance"
    admin_session.patch(f"{API}/admin/services/predictions",
                        json={"enabled": False, "shutdown_reason": reason})
    try:
        r = user_session.post(f"{API}/predictions",
                              json={"match_id": "any", "home_score_predicted": 1, "away_score_predicted": 1})
        assert r.status_code == 423, f"predictions: {r.status_code} {r.text}"
        detail = r.json().get("detail", {})
        assert detail.get("code") == "service_paused"
        assert detail.get("service") == "predictions"
        assert detail.get("reason") == reason
    finally:
        _reset_all(admin_session)


# ─── Phase 5: re-enable restores normal behaviour ───────────────────
def test_reenable_restores_normal(admin_session, user_session):
    admin_session.patch(f"{API}/admin/services/fantasy",
                        json={"enabled": False, "shutdown_reason": "x"})
    admin_session.patch(f"{API}/admin/services/fantasy",
                        json={"enabled": True, "shutdown_reason": ""})
    # Should no longer return 423 (might still be 400/401/422 due to invalid body — that's fine)
    r = user_session.post(f"{API}/fantasy/squad", json={"players": []})
    assert r.status_code != 423


def test_reenable_idempotent(admin_session):
    for _ in range(2):
        r = admin_session.patch(f"{API}/admin/services/fantasy",
                                json={"enabled": True, "shutdown_reason": ""})
        assert r.status_code == 200


# ─── Phase 6: unknown kind ──────────────────────────────────────────
def test_unknown_kind_rejected(admin_session):
    r = admin_session.patch(f"{API}/admin/services/foobar",
                            json={"enabled": False, "shutdown_reason": "x"})
    assert r.status_code in (400, 422)


# ─── Phase 7: leaderboards NOT gated ────────────────────────────────
def test_leaderboards_open_when_paused(admin_session):
    # Pause both
    admin_session.patch(f"{API}/admin/services/fantasy",
                        json={"enabled": False, "shutdown_reason": "x"})
    admin_session.patch(f"{API}/admin/services/predictions",
                        json={"enabled": False, "shutdown_reason": "y"})
    try:
        for path in ("/fantasy/leaderboard", "/fantasy/leaderboard/round?round=1", "/leaderboard"):
            r = requests.get(f"{API}{path}")
            assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
    finally:
        _reset_all(admin_session)


# ─── Final teardown ─────────────────────────────────────────────────
def test_zz_final_reset(admin_session):
    """Make sure both services are RE-ENABLED so we don't leave preview paused."""
    _reset_all(admin_session)
    data = requests.get(f"{API}/services/status").json()
    assert data["fantasy"]["enabled"] is True
    assert data["predictions"]["enabled"] is True
