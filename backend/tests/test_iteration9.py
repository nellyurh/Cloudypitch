"""Iteration 9 — Cloudy Pitch backend tests.

Validates the WC2026 restructure:
- /api/worldcup matches[] strictly filtered to 2026-06-01..2026-07-31 (no historical)
- /api/worldcup/past returns 9 tournaments with >=14 highlights having card_doc populated
- /api/fantasy/players?limit=2000 returns 1294 players across all 4 positions
"""
import os
import re
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@cloudypitch.com"
ADMIN_PASSWORD = "CloudyAdmin2026!"


@pytest.fixture(scope="session")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/signin", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"Admin signin failed: {r.status_code} {r.text[:200]}")
    return s


@pytest.fixture(scope="session")
def user_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"testuser-{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/signup", json={
        "email": email, "password": "TestPass123!", "display_name": "TEST_iter9"
    })
    if r.status_code not in (200, 201):
        pytest.skip(f"Signup failed: {r.status_code} {r.text[:200]}")
    return s


# ============= /api/worldcup — strict WC2026 date window =============

class TestWorldCupHub:
    def test_worldcup_returns_only_2026_window(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/worldcup")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "matches" in data
        assert "groups" in data
        assert isinstance(data["matches"], list)

        # Every match (if any) MUST be in WC2026 window
        out_of_window = []
        for m in data["matches"]:
            sched = m.get("scheduled_at") or ""
            # Window strings: 2026-06-01..2026-07-31
            if not (sched >= "2026-06-01" and sched <= "2026-07-31T23:59:59+00:00"):
                out_of_window.append({"id": m.get("id"), "scheduled_at": sched})
        assert not out_of_window, f"Historical/out-of-window matches leaked: {out_of_window[:3]}"
        print(f"matches in 2026 window: {len(data['matches'])}")

    def test_groups_seeded(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/worldcup")
        assert r.status_code == 200
        groups = r.json().get("groups") or []
        # 12 group rows expected for WC2026 expanded format
        assert len(groups) == 12, f"expected 12 groups, got {len(groups)}"


# ============= /api/worldcup/past — Legend Card linking =============

class TestPastTournaments:
    EXPECTED_CARD_LINKS = {
        # highlight player → legend_cards.name (regex contains, case-insensitive)
        "Lionel Messi": r"messi",
        "Diego Maradona": r"maradona",
        "Pelé": r"pel",
        "Kylian Mbappé": r"mbapp",
        "Zinedine Zidane": r"zidane",
        "Ronaldo Nazário": r"ronaldo",
        "Luka Modric": r"modric",
        "Andrés Iniesta": r"iniesta",
        "Ronaldinho": r"ronaldinho",
        "Gerd Müller": r"m(ü|u)ller",
    }

    def test_past_returns_9_tournaments(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/worldcup/past")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "tournaments" in data
        ts = data["tournaments"]
        years = sorted([t["year"] for t in ts], reverse=True)
        assert years == [2022, 2018, 2014, 2010, 2002, 1998, 1986, 1970, 1958], f"years mismatch: {years}"
        # at least 21 highlights total
        total_highlights = sum(len(t["highlights"]) for t in ts)
        assert total_highlights >= 21, f"only {total_highlights} highlights"

    def test_past_has_at_least_14_card_docs(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/worldcup/past")
        assert r.status_code == 200
        ts = r.json()["tournaments"]
        with_card = 0
        for t in ts:
            for h in t["highlights"]:
                if h.get("card_doc"):
                    with_card += 1
        assert with_card >= 14, f"only {with_card} highlights have card_doc populated"
        print(f"highlights with card_doc: {with_card}")

    def test_specific_legends_resolve_to_cards(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/worldcup/past")
        assert r.status_code == 200
        ts = r.json()["tournaments"]
        # build map of highlight.player -> card_doc.name
        seen = {}
        for t in ts:
            for h in t["highlights"]:
                if h.get("card_doc") and h["card_doc"].get("name"):
                    seen.setdefault(h["player"], h["card_doc"]["name"])
        missing = []
        for player, regex in self.EXPECTED_CARD_LINKS.items():
            card_name = seen.get(player)
            if not card_name or not re.search(regex, card_name, re.IGNORECASE):
                missing.append({"player": player, "got": card_name, "want_regex": regex})
        assert not missing, f"missing/unmatched card links: {missing}"


# ============= /api/fantasy/players — all 4 positions =============

class TestFantasyPlayers:
    def test_players_all_four_positions(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/fantasy/players?limit=2000")
        assert r.status_code == 200, r.text
        data = r.json()
        players = data.get("players") or []
        assert len(players) >= 500, f"expected ~1294 players, got {len(players)}"
        positions = {}
        for p in players:
            pos = (p.get("position") or "").upper()
            positions[pos] = positions.get(pos, 0) + 1
        print(f"positions: {positions} total={len(players)}")
        # Require ALL four positions to be present with meaningful counts
        for pos in ("GK", "DEF", "MID", "FWD"):
            assert positions.get(pos, 0) >= 50, f"position {pos} only has {positions.get(pos, 0)} players"

    def test_default_limit_returns_all_positions(self, api_client):
        # No explicit limit — default is 2000 in code
        r = api_client.get(f"{BASE_URL}/api/fantasy/players")
        assert r.status_code == 200
        players = r.json().get("players") or []
        positions = {p.get("position") for p in players}
        for pos in ("GK", "DEF", "MID", "FWD"):
            assert pos in positions, f"default-limit response missing {pos}; got {positions}"


# ============= Auth gating helpers =============

class TestAuthGate:
    def test_signin_admin(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200
        user = r.json().get("user") or {}
        assert user.get("email") == ADMIN_EMAIL

    def test_signup_user_works(self, user_client):
        r = user_client.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200
        assert r.json().get("user", {}).get("email", "").startswith("testuser-")
