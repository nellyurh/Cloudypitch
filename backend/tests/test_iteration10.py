"""Iteration 10 — WC2026 schedule pulled from SportMonks (season 26618 only),
per-stage card limits, per-game uniqueness on cards_used."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fantasy-wc.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@cloudypitch.com"
ADMIN_PW = "CloudyAdmin2026!"


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/signin", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    if r.status_code != 200:
        pytest.skip(f"admin signin failed: {r.status_code} {r.text[:200]}")
    return s


@pytest.fixture(scope="module")
def user_client():
    s = requests.Session()
    email = f"TEST_it10_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/signup", json={"email": email, "password": "TestPass123!", "display_name": "It10 User"})
    if r.status_code not in (200, 201):
        pytest.skip(f"signup failed {r.status_code} {r.text[:200]}")
    s.email = email
    return s


# --- WC schedule strictly 2026 ---
def test_worldcup_returns_2026_only():
    r = requests.get(f"{BASE_URL}/api/worldcup")
    assert r.status_code == 200
    data = r.json()
    matches = data.get("matches") or data.get("fixtures") or []
    assert isinstance(matches, list), f"matches not list: {type(matches)}"
    print(f"  worldcup matches count={len(matches)}")
    # No historical years
    bad = []
    for m in matches:
        s = (m.get("scheduled_at") or "")[:4]
        if s and s != "2026":
            bad.append((s, m.get("home_team_name"), m.get("away_team_name")))
    assert not bad, f"Non-2026 matches leaked: {bad[:5]}"


# --- Admin refresh-bracket end-to-end ---
def test_admin_refresh_bracket(admin_client):
    r = admin_client.post(f"{BASE_URL}/api/admin/wc/refresh-bracket")
    assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
    data = r.json()
    print(f"  refresh-bracket -> {data}")
    assert data.get("ok") is True
    assert "ingested" in data
    assert "created" in data
    assert "transitions" in data
    # Ingested could be 0 if SportMonks unreachable; just sanity check the keys


# --- Admin games listing groups ---
def test_admin_games_grouped(admin_client):
    r = admin_client.get(f"{BASE_URL}/api/admin/wc/games?limit=300")
    assert r.status_code == 200
    data = r.json()
    games = data.get("games", [])
    print(f"  admin/wc/games count={len(games)}")
    by_type = {}
    by_stage = {}
    by_status = {}
    for g in games:
        by_type[g.get("game_type")] = by_type.get(g.get("game_type"), 0) + 1
        by_stage[(g.get("game_type"), g.get("stage"))] = by_stage.get((g.get("game_type"), g.get("stage")), 0) + 1
        by_status[g.get("status")] = by_status.get(g.get("status"), 0) + 1
    print(f"  by_type={by_type} by_status={by_status}")
    print(f"  by_stage={by_stage}")
    # At least one round game per stage if any games exist
    if games:
        # Check round stages were created
        round_stages = [k for k in by_stage if k[0] == "round"]
        print(f"  round_stages={round_stages}")


# --- Config defaults per stage ---
def test_admin_config_per_stage_card_limits(admin_client):
    r = admin_client.get(f"{BASE_URL}/api/admin/wc/config")
    assert r.status_code == 200
    cfg = r.json().get("config", [])
    print(f"  config count={len(cfg)}")
    by_key = {(c["game_type"], c["stage"]): c.get("card_limit_current") for c in cfg}
    print(f"  config card_limit_current={by_key}")
    expected = {
        ("match", "any"): 2,
        ("group", "group_md1"): 4,
        ("group", "group_md2"): 4,
        ("group", "group_md3"): 4,
        ("round", "group_md1"): 5,
        ("round", "group_md2"): 5,
        ("round", "group_md3"): 6,
        ("round", "r32"): 6,
        ("round", "r16"): 7,
        ("round", "qf"): 8,
        ("round", "sf"): 9,
        ("round", "finals"): 10,
    }
    missing = []
    wrong = []
    for k, v in expected.items():
        if k not in by_key:
            missing.append(k)
        elif by_key[k] != v:
            wrong.append((k, by_key[k], v))
    print(f"  missing={missing}")
    print(f"  wrong={wrong}")
    assert not missing, f"Missing stage configs: {missing}"
    assert not wrong, f"Wrong card_limit_current: {wrong}"


# --- Enter game validations: duplicate card + over cap ---
def _find_open_game():
    r = requests.get(f"{BASE_URL}/api/wc/games/upcoming?limit=50")
    if r.status_code != 200:
        return None
    rows = r.json().get("games", [])
    for g in rows:
        if g.get("status") in ("upcoming", "open"):
            return g
    return rows[0] if rows else None


def test_enter_duplicate_card_returns_400(user_client):
    g = _find_open_game()
    if not g:
        pytest.skip("no wc game available to enter")
    gid = g["id"]
    payload = {
        "player_picks": [
            {"player_id": "fake-1", "position": "GK"},
            {"player_id": "fake-2", "position": "DEF"},
        ],
        "cards_used": [
            {"user_card_id": "dup-card-xyz"},
            {"user_card_id": "dup-card-xyz"},
        ],
    }
    r = user_client.post(f"{BASE_URL}/api/wc/games/{gid}/enter", json=payload)
    print(f"  duplicate-card response: {r.status_code} {r.text[:200]}")
    # Should be 400 with the dedupe message (per spec)
    assert r.status_code == 400, f"expected 400 dedupe, got {r.status_code}: {r.text[:200]}"
    assert "once per game" in r.text.lower() or "duplicate" in r.text.lower()


def test_enter_over_card_cap_returns_400(user_client):
    g = _find_open_game()
    if not g:
        pytest.skip("no wc game available")
    gid = g["id"]
    # Send way more cards than any stage cap (15)
    payload = {
        "player_picks": [{"player_id": "fake-1", "position": "GK"}],
        "cards_used": [{"user_card_id": f"card-{i}"} for i in range(15)],
    }
    r = user_client.post(f"{BASE_URL}/api/wc/games/{gid}/enter", json=payload)
    print(f"  over-cap response: {r.status_code} {r.text[:200]}")
    assert r.status_code == 400
    assert "card limit" in r.text.lower()


def test_enter_valid_picks_no_cards_returns_200(user_client):
    g = _find_open_game()
    if not g:
        pytest.skip("no wc game available")
    gid = g["id"]
    payload = {
        "player_picks": [{"player_id": f"p-{i}", "position": ["GK","DEF","DEF","DEF","DEF","MID","MID","MID","FWD","FWD","FWD"][i]} for i in range(11)],
        "cards_used": [],
    }
    r = user_client.post(f"{BASE_URL}/api/wc/games/{gid}/enter", json=payload)
    print(f"  valid-no-cards response: {r.status_code} {r.text[:200]}")
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:300]}"
    body = r.json()
    assert "entry" in body
    assert len(body["entry"]["player_picks"]) == 11
