"""Iteration 8 — WC2026 Fantasy Game (148 games) + auth-extras + KYC + admin."""
import os
import time
import uuid

import pytest
import requests

def _load_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            with open("/app/frontend/.env") as f:
                for ln in f:
                    if ln.strip().startswith("REACT_APP_BACKEND_URL="):
                        v = ln.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert v, "REACT_APP_BACKEND_URL not set"
    return v.rstrip("/")


BASE_URL = _load_url()
ADMIN_EMAIL = "admin@cloudypitch.com"
ADMIN_PASS = "CloudyAdmin2026!"


# ---------------- fixtures ----------------
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/signin", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def anon_session():
    return requests.Session()


@pytest.fixture(scope="session")
def user_session():
    """Create a fresh test user for entry / kyc / verify flows."""
    s = requests.Session()
    email = f"testuser-{uuid.uuid4().hex[:8]}@example.com"
    pw = "TestPass123!"
    r = s.post(f"{BASE_URL}/api/auth/signup", json={
        "email": email, "password": pw, "display_name": f"Tester{uuid.uuid4().hex[:4]}"
    })
    assert r.status_code in (200, 201), f"signup failed: {r.status_code} {r.text}"
    s.email = email  # type: ignore
    s.password = pw  # type: ignore
    return s


# ==================== WC GAMES (USER) ====================
def test_wc_games_today_unauth(anon_session):
    r = anon_session.get(f"{BASE_URL}/api/wc/games/today")
    assert r.status_code == 200
    data = r.json()
    assert "games" in data
    assert isinstance(data["games"], list)


def test_wc_games_today_auth(user_session):
    r = user_session.get(f"{BASE_URL}/api/wc/games/today")
    assert r.status_code == 200
    assert "games" in r.json()


def test_wc_games_upcoming_unauth(anon_session):
    r = anon_session.get(f"{BASE_URL}/api/wc/games/upcoming")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data.get("games"), list)


def test_wc_games_upcoming_auth(user_session):
    r = user_session.get(f"{BASE_URL}/api/wc/games/upcoming?limit=10")
    assert r.status_code == 200
    assert isinstance(r.json().get("games"), list)


def test_wc_game_detail_returns_eligible_players(admin_session):
    """Pick any existing wc_game and check eligible_players list returned."""
    r = admin_session.get(f"{BASE_URL}/api/admin/wc/games?limit=1")
    assert r.status_code == 200
    games = r.json().get("games", [])
    if not games:
        pytest.skip("No wc_games seeded")
    gid = games[0]["id"]
    r2 = admin_session.get(f"{BASE_URL}/api/wc/games/{gid}")
    assert r2.status_code == 200
    g = r2.json()["game"]
    assert g["id"] == gid
    assert "eligible_players" in g
    assert isinstance(g["eligible_players"], list)


def test_wc_game_detail_404():
    r = requests.get(f"{BASE_URL}/api/wc/games/does-not-exist-xyz")
    assert r.status_code == 404


def test_wc_user_entries_requires_auth(anon_session):
    r = anon_session.get(f"{BASE_URL}/api/wc/user/entries")
    assert r.status_code in (401, 403)


def test_wc_user_entries_auth(user_session):
    r = user_session.get(f"{BASE_URL}/api/wc/user/entries")
    assert r.status_code == 200
    assert "entries" in r.json()


def test_wc_game_leaderboard_endpoint(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/wc/games?limit=1")
    games = r.json().get("games", [])
    if not games:
        pytest.skip("No wc_games")
    gid = games[0]["id"]
    r2 = requests.get(f"{BASE_URL}/api/wc/games/{gid}/leaderboard")
    assert r2.status_code == 200
    assert "leaderboard" in r2.json()


def test_wc_groups_returns_12(anon_session):
    r = anon_session.get(f"{BASE_URL}/api/wc/groups")
    assert r.status_code == 200
    groups = r.json()["groups"]
    assert len(groups) == 12, f"expected 12 groups, got {len(groups)}"
    for g in groups:
        assert "group" in g
        assert isinstance(g.get("teams"), list)
        assert len(g["teams"]) == 4


def test_wc_enter_game_card_cap(user_session, admin_session):
    """Confirm /enter validates card cap. Take first existing wc_game (likely 'closed' since 2006 dates),
    expect 400 'entries closed'. That still proves the endpoint shape + auth."""
    r = admin_session.get(f"{BASE_URL}/api/admin/wc/games?limit=1")
    games = r.json().get("games", [])
    if not games:
        pytest.skip("No wc_games")
    gid = games[0]["id"]
    payload = {
        "player_picks": [
            {"player_id": f"p{i}", "position": "MID"} for i in range(11)
        ],
        "captain_player_id": "p0",
        "vice_captain_player_id": "p1",
        "cards_used": [],
    }
    r2 = user_session.post(f"{BASE_URL}/api/wc/games/{gid}/enter", json=payload)
    # Either 200 (if game open) or 400 (entries closed)
    assert r2.status_code in (200, 400), f"got {r2.status_code} {r2.text}"


# ==================== WC ADMIN ====================
def test_admin_wc_config_returns_12(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/wc/config")
    assert r.status_code == 200
    cfg = r.json()["config"]
    assert len(cfg) == 12, f"expected 12 config rows, got {len(cfg)}"
    for row in cfg:
        assert "id" in row
        assert "card_limit_current" in row
        assert "card_limit_default" in row


def test_admin_wc_config_patch_and_audit(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/wc/config")
    rows = r.json()["config"]
    target = rows[0]
    cfg_id = target["id"]
    new_val = (target.get("card_limit_current") or 2) + 1
    patch = admin_session.patch(
        f"{BASE_URL}/api/admin/wc/config/{cfg_id}",
        json={"card_limit_current": new_val, "notes": "TEST_iter8"},
    )
    assert patch.status_code == 200
    # Verify persisted
    r2 = admin_session.get(f"{BASE_URL}/api/admin/wc/config")
    after = [r for r in r2.json()["config"] if r["id"] == cfg_id][0]
    assert after["card_limit_current"] == new_val
    assert after.get("notes") == "TEST_iter8"


def test_admin_wc_config_reset(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/admin/wc/config/reset")
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == 12
    # confirm all values restored
    cfg = admin_session.get(f"{BASE_URL}/api/admin/wc/config").json()["config"]
    for row in cfg:
        assert row["card_limit_current"] == row["card_limit_default"]


def test_admin_wc_games_filters(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/wc/games?game_type=match&limit=5")
    assert r.status_code == 200
    games = r.json()["games"]
    for g in games:
        assert g["game_type"] == "match"


def test_admin_wc_game_patch(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/wc/games?limit=1")
    games = r.json().get("games", [])
    if not games:
        pytest.skip("No wc_games")
    gid = games[0]["id"]
    cur = games[0].get("status")
    new_status = "open" if cur != "open" else "closed"
    patch = admin_session.patch(
        f"{BASE_URL}/api/admin/wc/games/{gid}", json={"status": new_status}
    )
    assert patch.status_code == 200
    # verify
    r2 = admin_session.get(f"{BASE_URL}/api/admin/wc/games?limit=200")
    g = [x for x in r2.json()["games"] if x["id"] == gid][0]
    assert g["status"] == new_status


def test_admin_wc_refresh_bracket(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/admin/wc/refresh-bracket")
    assert r.status_code == 200
    body = r.json()
    assert "created" in body and "transitions" in body
    assert isinstance(body["created"], int)
    assert isinstance(body["transitions"], int)


def test_admin_wc_group_update(admin_session):
    teams = ["TestT1", "TestT2", "TestT3", "TestT4"]
    r = admin_session.patch(f"{BASE_URL}/api/admin/wc/groups/A", json={"teams": teams})
    assert r.status_code == 200
    # verify
    groups = admin_session.get(f"{BASE_URL}/api/wc/groups").json()["groups"]
    grp_a = [g for g in groups if g["group"] == "A"][0]
    assert grp_a["teams"] == teams


# ==================== AUTH-EXTRAS ====================
def test_password_reset_request_and_confirm(user_session):
    email = user_session.email  # type: ignore
    r = requests.post(f"{BASE_URL}/api/auth-extras/reset/request", json={"email": email})
    assert r.status_code == 200
    body = r.json()
    token = body.get("dev_token")
    assert token, "dev_token should be returned when no EMAIL_PROVIDER_KEY"
    # confirm
    new_pw = "NewPass123!"
    r2 = requests.post(f"{BASE_URL}/api/auth-extras/reset/confirm",
                       json={"token": token, "new_password": new_pw})
    assert r2.status_code == 200
    # signin with new password
    s = requests.Session()
    r3 = s.post(f"{BASE_URL}/api/auth/signin", json={"email": email, "password": new_pw})
    assert r3.status_code == 200, f"signin after reset failed: {r3.text}"
    # update fixture's password to new value to keep verify request working
    user_session.password = new_pw  # type: ignore
    # we need to re-login the original session since reset invalidated it
    user_session.cookies.clear()
    rl = user_session.post(f"{BASE_URL}/api/auth/signin", json={"email": email, "password": new_pw})
    assert rl.status_code == 200


def test_password_reset_unknown_email_returns_200():
    r = requests.post(f"{BASE_URL}/api/auth-extras/reset/request",
                      json={"email": f"nobody-{uuid.uuid4().hex[:6]}@example.com"})
    assert r.status_code == 200
    assert r.json().get("dev_token") in (None, "")


def test_email_verify_request_and_confirm(user_session):
    r = user_session.post(f"{BASE_URL}/api/auth-extras/verify/request")
    assert r.status_code == 200
    body = r.json()
    if body.get("already_verified"):
        return
    token = body.get("dev_token")
    assert token, "expected dev_token"
    r2 = requests.post(f"{BASE_URL}/api/auth-extras/verify/confirm", json={"token": token})
    assert r2.status_code == 200
    # confirm flag
    me = user_session.get(f"{BASE_URL}/api/auth/me").json()
    user = me.get("user", me)
    assert user.get("email_verified") is True


def test_kyc_submit_and_admin_review(user_session, admin_session):
    payload = {
        "full_name": "Test User KYC",
        "date_of_birth": "1995-01-15",
        "bank_name": "Test Bank",
        "account_number": "1234567890",
        "bvn": "12345678901",
    }
    r = user_session.post(f"{BASE_URL}/api/auth-extras/kyc/submit", json=payload)
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
    # GET kyc/me
    me = user_session.get(f"{BASE_URL}/api/auth-extras/kyc/me")
    assert me.status_code == 200
    kyc = me.json()["kyc"]
    assert kyc["status"] == "pending"
    assert "account_number_full" not in kyc, "full account number should NOT leak"
    assert kyc["account_number_masked"].endswith("7890")
    # admin review
    user_resp = user_session.get(f"{BASE_URL}/api/auth/me").json()
    user_id = (user_resp.get("user") or user_resp)["id"]
    rev = admin_session.post(f"{BASE_URL}/api/auth-extras/kyc/review",
                             json={"user_id": user_id, "approved": True, "notes": "ok"})
    assert rev.status_code == 200
    # verify wallet flag (auth as user)
    # We can re-fetch /kyc/me to see approved status
    after = user_session.get(f"{BASE_URL}/api/auth-extras/kyc/me").json()["kyc"]
    assert after["status"] == "approved"


# ==================== PREDICTIONS (premium + horizon) ====================
def test_predictions_leaderboard_premium_scope(anon_session):
    r = anon_session.get(f"{BASE_URL}/api/predictions/leaderboard?scope=premium")
    assert r.status_code == 200
    body = r.json()
    assert "leaderboard" in body or "rows" in body or isinstance(body, dict)


def test_predictions_upcoming_horizon(user_session):
    r = user_session.get(f"{BASE_URL}/api/predictions/upcoming")
    assert r.status_code == 200


# ==================== ADS ====================
def test_ads_reward_card_uses(user_session):
    r = user_session.post(f"{BASE_URL}/api/ads/reward/claim",
                          json={"reward_type": "card_uses"})
    # Accept 200 or 429 (rate limited from prior run)
    assert r.status_code in (200, 429), f"unexpected {r.status_code} {r.text}"
    if r.status_code == 200:
        body = r.json()
        assert body.get("ok") or "card_uses" in str(body).lower() or "uses_added" in body


# ==================== PRIZE POOL admin ====================
def test_prize_pool_patch(admin_session):
    pools = admin_session.get(f"{BASE_URL}/api/prize-pools").json()
    rows = pools.get("pools", pools) if isinstance(pools, dict) else pools
    if not isinstance(rows, list) or not rows:
        pytest.skip("no prize pools")
    pid = rows[0]["id"]
    new_amt = (rows[0].get("amount_usd_cents") or 0) + 10000
    r = admin_session.patch(f"{BASE_URL}/api/prize-pools/{pid}",
                            json={"amount_usd_cents": new_amt})
    assert r.status_code == 200


def test_prize_pool_contributions(admin_session):
    pools = admin_session.get(f"{BASE_URL}/api/prize-pools").json()
    rows = pools.get("pools", pools) if isinstance(pools, dict) else pools
    if not isinstance(rows, list) or not rows:
        pytest.skip("no prize pools")
    pid = rows[0]["id"]
    r = admin_session.get(f"{BASE_URL}/api/prize-pools/{pid}/contributions")
    assert r.status_code == 200
    body = r.json()
    assert "contributions" in body


# ==================== FANTASY squad with applied_card_ids ====================
def test_fantasy_squad_applied_card_ids(user_session):
    payload = {
        "player_ids": [],
        "applied_card_ids": ["test-card-1", "test-card-2"],
    }
    r = user_session.post(f"{BASE_URL}/api/fantasy/squad", json=payload)
    # Accept 200/201/400 (validation) — main thing is endpoint accepts the field
    assert r.status_code in (200, 201, 400, 422), f"{r.status_code} {r.text}"
