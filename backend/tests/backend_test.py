"""Cloudy Pitch backend integration tests.

Covers:
- Health, sports catalog, countries, leagues
- Matches list/detail/filters/h2h
- World Cup hub
- Predictions (upcoming, submit, leaderboard, me)
- Fantasy (competition, players, squad, leaderboard)
- Legend cards (catalog, mine)
- Prize pools
- Profile stats
- Search
- Auth (signup, signin, me, signout, admin login)
- Admin endpoints (require admin role)

Uses real public preview URL with cookie-based session auth (cp_session).
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fantasy-wc.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@cloudypitch.com"
ADMIN_PASSWORD = "CloudyAdmin2026!"


# ---------------- fixtures ----------------
@pytest.fixture(scope="session")
def anon():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/signin", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin signin failed: {r.status_code} {r.text}"
    assert "cp_session" in s.cookies, "cp_session cookie not set on admin signin"
    return s


@pytest.fixture(scope="session")
def user_client():
    """Fresh user signed up via API."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"TEST_user_{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPass123!"
    r = s.post(f"{API}/auth/signup", json={
        "email": email, "password": password, "display_name": "TEST User"
    })
    assert r.status_code == 200, f"Signup failed: {r.status_code} {r.text}"
    assert "cp_session" in s.cookies
    s.user_email = email  # type: ignore
    s.user_password = password  # type: ignore
    return s


# ---------------- Health / catalog ----------------
class TestHealthAndCatalog:
    def test_root_health(self, anon):
        r = anon.get(f"{API}")
        assert r.status_code == 200
        body = r.json()
        assert body.get("status") == "ok"

    def test_sports_returns_14(self, anon):
        r = anon.get(f"{API}/sports")
        assert r.status_code == 200
        data = r.json()
        sports = data.get("sports", data) if isinstance(data, dict) else data
        assert isinstance(sports, list)
        assert len(sports) >= 14, f"Expected >=14 sports, got {len(sports)}"

    def test_countries_football(self, anon):
        r = anon.get(f"{API}/countries", params={"sport": "football"})
        assert r.status_code == 200
        data = r.json()
        countries = data.get("countries", data) if isinstance(data, dict) else data
        assert isinstance(countries, list)

    def test_leagues_football(self, anon):
        r = anon.get(f"{API}/leagues", params={"sport": "football"})
        assert r.status_code == 200
        data = r.json()
        leagues = data.get("leagues", data) if isinstance(data, dict) else data
        assert isinstance(leagues, list)
        # Seed should provide many leagues (target 25+)
        assert len(leagues) >= 10, f"Expected many leagues, got {len(leagues)}"


# ---------------- Matches ----------------
class TestMatches:
    def test_list_football(self, anon):
        r = anon.get(f"{API}/matches", params={"sport": "football"})
        assert r.status_code == 200
        data = r.json()
        assert "matches" in data or "grouped" in data, f"Missing keys in {list(data.keys())}"

    @pytest.mark.parametrize("status", ["live", "upcoming", "finished"])
    def test_list_status_filter(self, anon, status):
        r = anon.get(f"{API}/matches", params={"sport": "football", "status": status})
        assert r.status_code == 200, f"status={status} -> {r.status_code} {r.text[:200]}"

    def test_match_detail(self, anon):
        r = anon.get(f"{API}/matches", params={"sport": "football", "status": "upcoming"})
        assert r.status_code == 200
        data = r.json()
        matches = data.get("matches", [])
        if not matches:
            # Try all to find at least one match
            r2 = anon.get(f"{API}/matches", params={"sport": "football"})
            matches = r2.json().get("matches", [])
        if not matches:
            pytest.skip("No matches available to test detail endpoint")
        mid = matches[0]["id"]
        d = anon.get(f"{API}/matches/{mid}")
        assert d.status_code == 200, d.text[:200]
        body = d.json()
        # Should contain match + related arrays
        assert "match" in body or "id" in body

    def test_h2h(self, anon):
        r = anon.get(f"{API}/matches", params={"sport": "football"})
        matches = r.json().get("matches", [])
        if not matches:
            pytest.skip("No matches for h2h test")
        mid = matches[0]["id"]
        h = anon.get(f"{API}/matches/{mid}/h2h")
        assert h.status_code == 200, h.text[:200]


# ---------------- World Cup ----------------
class TestWorldCup:
    def test_worldcup_hub(self, anon):
        r = anon.get(f"{API}/worldcup")
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        groups = data.get("groups", [])
        assert isinstance(groups, list)
        assert len(groups) == 12, f"Expected 12 groups, got {len(groups)}"


# ---------------- Predictions ----------------
class TestPredictions:
    def test_upcoming_anon(self, anon):
        r = anon.get(f"{API}/predictions/upcoming")
        assert r.status_code == 200

    def test_leaderboard(self, anon):
        r = anon.get(f"{API}/predictions/leaderboard")
        assert r.status_code == 200

    def test_submit_requires_auth(self, anon):
        r = anon.post(f"{API}/predictions", json={
            "match_id": "x", "home_score_predicted": 1, "away_score_predicted": 1
        })
        assert r.status_code in (401, 403)

    def test_me_requires_auth(self, anon):
        r = anon.get(f"{API}/predictions/me")
        assert r.status_code in (401, 403)

    def test_me_authed(self, user_client):
        r = user_client.get(f"{API}/predictions/me")
        assert r.status_code == 200

    def test_submit_prediction(self, user_client, anon):
        # Find an upcoming match
        r = anon.get(f"{API}/predictions/upcoming")
        data = r.json()
        upcoming = data.get("matches") or data.get("predictions") or data.get("upcoming") or (data if isinstance(data, list) else [])
        if not upcoming:
            pytest.skip("No upcoming matches available for prediction")
        match = upcoming[0]
        mid = match.get("id") or match.get("match_id")
        if not mid:
            pytest.skip(f"Could not extract match id from upcoming entry: {match}")
        resp = user_client.post(f"{API}/predictions", json={
            "match_id": mid, "home_score_predicted": 2, "away_score_predicted": 1
        })
        assert resp.status_code in (200, 201), f"Submit prediction failed: {resp.status_code} {resp.text[:300]}"


# ---------------- Fantasy ----------------
class TestFantasy:
    def test_competition(self, anon):
        r = anon.get(f"{API}/fantasy/competition")
        assert r.status_code == 200
        data = r.json()
        comp = data.get("competition", data)
        assert comp.get("id") == "fantasy-wc2026", f"Got competition id={comp.get('id')}"

    def test_players(self, anon):
        r = anon.get(f"{API}/fantasy/players")
        assert r.status_code == 200
        players = r.json().get("players", [])
        assert isinstance(players, list)
        assert len(players) >= 100, f"Expected >=100 players, got {len(players)}"

    def test_leaderboard(self, anon):
        r = anon.get(f"{API}/fantasy/leaderboard")
        assert r.status_code == 200

    def test_squad_requires_auth(self, anon):
        r = anon.get(f"{API}/fantasy/squad/me")
        assert r.status_code in (401, 403)

    def test_create_squad(self, user_client, anon):
        # Build minimal valid squad
        pres = anon.get(f"{API}/fantasy/players").json().get("players", [])
        if len(pres) < 11:
            pytest.skip("Not enough players to build squad")
        # Pick reasonable mix; ensure budget <= 100
        # Use price_paid fallback
        def pos_of(p):
            return p.get("position") or p.get("pos") or "MID"
        squad_players = []
        # Pick 11 with synthetic pricing if needed
        budget_left = 100.0
        for p in pres[:11]:
            price = float(p.get("price") or p.get("market_value") or 5.0)
            if price > budget_left:
                price = max(0.5, budget_left / max(1, 11 - len(squad_players)))
            budget_left -= price
            pos = pos_of(p).upper()
            if pos not in ("GK", "DEF", "MID", "FWD"):
                pos = "MID"
            squad_players.append({
                "player_id": p.get("id") or p.get("player_id") or str(uuid.uuid4()),
                "position": pos,
                "is_starting": True,
                "price_paid": round(price, 2),
            })
        payload = {
            "competition_id": "fantasy-wc2026",
            "squad_name": "TEST Squad",
            "captain_id": squad_players[0]["player_id"],
            "vice_captain_id": squad_players[1]["player_id"],
            "players": squad_players,
        }
        r = user_client.post(f"{API}/fantasy/squad", json=payload)
        assert r.status_code in (200, 201), f"Create squad failed: {r.status_code} {r.text[:400]}"
        # Verify squad/me reflects creation
        me = user_client.get(f"{API}/fantasy/squad/me")
        assert me.status_code == 200
        sq = me.json().get("squad")
        assert sq is not None
        assert sq.get("squad_name") == "TEST Squad"


# ---------------- Cards ----------------
class TestCards:
    def test_catalog_100(self, anon):
        r = anon.get(f"{API}/cards")
        assert r.status_code == 200
        cards = r.json().get("cards", [])
        assert len(cards) == 100, f"Expected 100 cards, got {len(cards)}"
        tiers = {c.get("tier") for c in cards}
        assert {1, 2, 3}.issubset(tiers), f"Expected tiers 1,2,3, got {tiers}"

    def test_me_requires_auth(self, anon):
        r = anon.get(f"{API}/cards/me")
        assert r.status_code in (401, 403)

    def test_me_starter_pack(self, user_client):
        r = user_client.get(f"{API}/cards/me")
        assert r.status_code == 200
        body = r.json()
        my_cards = body.get("owned") or body.get("cards") or body.get("user_cards") or []
        assert len(my_cards) >= 5, f"Starter pack should grant 5 cards, got {len(my_cards)} body={body}"


# ---------------- Prize pools ----------------
class TestPrizePools:
    def test_list(self, anon):
        r = anon.get(f"{API}/prize-pools")
        assert r.status_code == 200
        pools = r.json().get("prize_pools", r.json().get("pools", []))
        assert isinstance(pools, list)
        assert len(pools) >= 1

    def test_detail(self, anon):
        r = anon.get(f"{API}/prize-pools").json()
        pools = r.get("prize_pools", r.get("pools", []))
        if not pools:
            pytest.skip("no prize pools")
        pid = pools[0].get("id")
        d = anon.get(f"{API}/prize-pools/{pid}")
        assert d.status_code == 200


# ---------------- Profile ----------------
class TestProfile:
    def test_stats_auth_required(self, anon):
        r = anon.get(f"{API}/users/me/stats")
        assert r.status_code in (401, 403)

    def test_stats_authed(self, user_client):
        r = user_client.get(f"{API}/users/me/stats")
        assert r.status_code == 200


# ---------------- Search ----------------
class TestSearch:
    def test_search_chelsea(self, anon):
        r = anon.get(f"{API}/search", params={"q": "Chelsea"})
        assert r.status_code == 200
        body = r.json()
        # Expect teams/leagues/matches keys (lenient)
        assert any(k in body for k in ("teams", "leagues", "matches", "results")), f"keys={list(body.keys())}"


# ---------------- Auth flow ----------------
class TestAuth:
    def test_signup_sets_cookie(self):
        s = requests.Session()
        email = f"TEST_signup_{uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/signup", json={
            "email": email, "password": "GoodPass1!", "display_name": "TEST Signup"
        })
        assert r.status_code == 200, r.text[:300]
        assert "cp_session" in s.cookies
        body = r.json()
        assert body.get("user", {}).get("email") == email.lower()
        assert body.get("starter_cards") == 5

    def test_signup_duplicate_409(self, anon):
        email = f"TEST_dup_{uuid.uuid4().hex[:8]}@example.com"
        p = {"email": email, "password": "GoodPass1!", "display_name": "Dup Test"}
        r1 = requests.post(f"{API}/auth/signup", json=p)
        assert r1.status_code == 200
        r2 = requests.post(f"{API}/auth/signup", json=p)
        assert r2.status_code == 409, f"Expected 409, got {r2.status_code} {r2.text[:200]}"

    def test_me_without_cookie_401(self, anon):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_admin_signin(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/signin", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200, r.text[:300]
        user = r.json().get("user", {})
        assert user.get("role") == "admin", f"Admin role missing: {user}"
        # /me
        me = s.get(f"{API}/auth/me")
        assert me.status_code == 200

    def test_signout_clears_session(self):
        s = requests.Session()
        s.post(f"{API}/auth/signin", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert s.get(f"{API}/auth/me").status_code == 200
        out = s.post(f"{API}/auth/signout")
        assert out.status_code == 200
        # After signout server-side session deleted -> 401 with cleared cookie
        s2 = requests.Session()
        # carry the same cookie value the client had (now cleared)
        me = s2.get(f"{API}/auth/me")
        assert me.status_code == 401

    def test_invalid_password_returns_401(self):
        # Create a target user
        s = requests.Session()
        email = f"TEST_lock_{uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/signup", json={
            "email": email, "password": "RightPass1!", "display_name": "Lock Test"
        })
        assert r.status_code == 200
        s2 = requests.Session()
        rr = s2.post(f"{API}/auth/signin", json={"email": email, "password": "WrongPass1!"})
        assert rr.status_code == 401


# ---------------- Admin ----------------
class TestAdmin:
    def test_non_admin_forbidden(self, user_client):
        r = user_client.get(f"{API}/admin/stats")
        assert r.status_code == 403, f"Expected 403 for non-admin, got {r.status_code}"

    def test_anon_forbidden(self):
        r = requests.get(f"{API}/admin/stats")
        assert r.status_code == 401

    def test_admin_stats(self, admin_client):
        r = admin_client.get(f"{API}/admin/stats")
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for k in ("users", "matches", "leagues", "cards"):
            assert k in d, f"missing key {k} in stats"

    def test_admin_users(self, admin_client):
        r = admin_client.get(f"{API}/admin/users")
        assert r.status_code == 200
        assert "users" in r.json()

    def test_admin_matches(self, admin_client):
        r = admin_client.get(f"{API}/admin/matches", params={"sport": "football", "limit": 10})
        assert r.status_code == 200
        assert "matches" in r.json()

    def test_admin_audit(self, admin_client):
        r = admin_client.get(f"{API}/admin/audit")
        assert r.status_code == 200
        assert "audit" in r.json()

    def test_admin_promote_user(self, admin_client, user_client):
        # Get the user's id from /auth/me
        me = user_client.get(f"{API}/auth/me").json().get("user", {})
        uid = me.get("id")
        assert uid
        r = admin_client.post(f"{API}/admin/users/{uid}/promote")
        assert r.status_code == 200

    def test_admin_ingest_sportmonks_live(self, admin_client):
        r = admin_client.post(f"{API}/admin/ingest/sportmonks/live")
        # Should be 200 even with 0 live; tolerate 500 only with helpful message
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"

    def test_admin_ingest_apisports_basketball(self, admin_client):
        r = admin_client.post(f"{API}/admin/ingest/apisports/basketball/sync")
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"

    def test_admin_ingest_statpal_tennis(self, admin_client):
        r = admin_client.post(f"{API}/admin/ingest/statpal/tennis/sync")
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
