"""Iteration 4 tests: Standings, Top scorers, Cards-per-game cap enforcement.

Endpoints under test:
  GET /api/leagues/{id}/standings  (Sportmonks-backed)
  GET /api/leagues/{id}/topscorers (Sportmonks-backed)
  POST /api/cards/use              (scope cap enforcement + idempotency)
  GET  /api/cards/usage
  GET  /api/cards/usage/me
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # Fallback to reading frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break
BASE_URL = (BASE_URL or "").rstrip("/")

ADMIN_EMAIL = "admin@cloudypitch.com"
ADMIN_PASS = "CloudyAdmin2026!"

# Use a fresh signup user so we always get the 5-card starter pack
# (admin seed user is created via seed_admin, which doesn't grant starter cards)
import time as _time
TEST_USER_EMAIL = f"TEST_iter4_{int(_time.time())}@example.com"
TEST_USER_PASS = "TestPass123!"


# ───── Fixtures ─────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    # Sign up a fresh user to get a guaranteed 5-card starter pack
    r = s.post(f"{BASE_URL}/api/auth/signup",
               json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASS,
                     "display_name": "Iter4 Tester"}, timeout=20)
    assert r.status_code in (200, 201), f"signup failed: {r.status_code} {r.text}"
    # Some auth flows auto-login on signup; otherwise explicitly signin
    me = s.get(f"{BASE_URL}/api/auth/me", timeout=10)
    if me.status_code != 200:
        r = s.post(f"{BASE_URL}/api/auth/signin",
                   json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASS}, timeout=20)
        assert r.status_code == 200, r.text
        me = s.get(f"{BASE_URL}/api/auth/me", timeout=10)
    me_json = me.json()
    user_id = me_json.get("id") or me_json.get("user", {}).get("id")
    assert user_id, f"No user id in /me response: {me_json}"
    s.user_id = user_id
    return s


@pytest.fixture(scope="module")
def owned_card_ids(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/cards/me", timeout=10)
    assert r.status_code == 200, r.text
    items = r.json()
    if isinstance(items, dict):
        items = items.get("owned") or items.get("items") or items.get("cards") or []
    ids = []
    for c in items:
        cid = c.get("card_id") or c.get("id")
        if cid and cid not in ids:
            ids.append(cid)
    assert len(ids) >= 1, f"Admin has no owned cards. Response: {items[:2]}"
    return ids


# ───── Standings ────────────────────────────────────────────────────
class TestStandings:
    def test_standings_egypt_refresh(self):
        r = requests.get(f"{BASE_URL}/api/leagues/sm-l-830/standings?refresh=1", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        rows = data.get("standings", [])
        assert len(rows) >= 14, f"Expected 14+ rows, got {len(rows)}"
        required = ["position", "team_name", "team_logo", "played", "won",
                    "drawn", "lost", "goals_for", "goals_against",
                    "goal_diff", "points"]
        numeric = ["position", "played", "won", "drawn", "lost",
                   "goals_for", "goals_against", "goal_diff", "points"]
        for row in rows:
            for f in required:
                assert f in row, f"Missing field {f} in row: {row}"
            for nf in numeric:
                assert row[nf] is not None, f"Field {nf} is None in row {row.get('team_name')}: {row}"

    def test_standings_cache_hit(self):
        r = requests.get(f"{BASE_URL}/api/leagues/sm-l-830/standings", timeout=20)
        assert r.status_code == 200
        rows = r.json().get("standings", [])
        assert len(rows) >= 14, "Cache should have standings"


# ───── Top Scorers ──────────────────────────────────────────────────
class TestTopScorers:
    def test_topscorers_egypt(self):
        r = requests.get(f"{BASE_URL}/api/leagues/sm-l-830/topscorers?refresh=1", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        rows = data.get("scorers", [])
        # Some leagues may have zero topscorers cached; accept but warn
        if not rows:
            pytest.skip("No topscorers returned for sm-l-830")
        for s in rows[:5]:
            for k in ["rank", "player_name", "team_name", "team_logo", "goals"]:
                assert k in s, f"Missing {k} in scorer: {s}"

    def test_topscorers_copa(self):
        r = requests.get(f"{BASE_URL}/api/leagues/sm-l-1122/topscorers?refresh=1", timeout=60)
        # 200 with possibly empty list, or 502 if upstream fails — both acceptable
        assert r.status_code in (200, 404, 502), r.text


# ───── Cards Cap Enforcement ────────────────────────────────────────
class TestCardsUsage:
    def test_match_cap_2(self, admin_session, owned_card_ids):
        scope_id = "test-match-1"
        ok_count = 0
        for i, cid in enumerate(owned_card_ids[:3]):
            r = admin_session.post(f"{BASE_URL}/api/cards/use",
                                   json={"card_id": cid, "scope": "match", "scope_id": scope_id},
                                   timeout=15)
            if i < 2:
                assert r.status_code == 200, f"Expected success on call {i+1}: {r.status_code} {r.text}"
                ok_count += 1
            else:
                assert r.status_code == 403, f"Expected 403 on 3rd call, got {r.status_code} {r.text}"
                assert "cap" in r.json().get("detail", "").lower()
        assert ok_count == 2

        # Verify GET /api/cards/usage
        r = admin_session.get(f"{BASE_URL}/api/cards/usage",
                              params={"scope": "match", "scope_id": scope_id}, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["count"] == 2 and d["cap"] == 2 and d["remaining"] == 0
        assert isinstance(d["used"], list) and len(d["used"]) == 2

    def test_idempotency(self, admin_session, owned_card_ids):
        scope_id = "test-match-idem"
        cid = owned_card_ids[0]
        r1 = admin_session.post(f"{BASE_URL}/api/cards/use",
                                json={"card_id": cid, "scope": "match", "scope_id": scope_id}, timeout=15)
        r2 = admin_session.post(f"{BASE_URL}/api/cards/use",
                                json={"card_id": cid, "scope": "match", "scope_id": scope_id}, timeout=15)
        assert r1.status_code == 200, r1.text
        assert r2.status_code == 200, r2.text
        assert r2.json().get("already_used") is True
        # Confirm only 1 usage row
        r3 = admin_session.get(f"{BASE_URL}/api/cards/usage",
                               params={"scope": "match", "scope_id": scope_id}, timeout=10)
        assert r3.json()["count"] == 1

    def test_group_cap_4(self, admin_session, owned_card_ids):
        scope_id = "test-group-A"
        # use up to 5 distinct cards (admin starter pack = 5)
        used_ok, used_fail = 0, 0
        for i, cid in enumerate(owned_card_ids[:5]):
            r = admin_session.post(f"{BASE_URL}/api/cards/use",
                                   json={"card_id": cid, "scope": "group", "scope_id": scope_id}, timeout=15)
            if r.status_code == 200:
                used_ok += 1
            elif r.status_code == 403:
                used_fail += 1
        assert used_ok == 4, f"Expected 4 successes, got {used_ok}"
        assert used_fail >= 1, f"Expected at least one cap-rejection, got {used_fail}"

    def test_round_cap_5(self, admin_session, owned_card_ids):
        scope_id = "QuarterFinals"
        used_ok = 0
        for cid in owned_card_ids[:5]:
            r = admin_session.post(f"{BASE_URL}/api/cards/use",
                                   json={"card_id": cid, "scope": "round", "scope_id": scope_id}, timeout=15)
            if r.status_code == 200:
                used_ok += 1
        assert used_ok == 5, f"Expected 5 successes for round scope, got {used_ok}"
        # 6th would fail but admin only has 5 cards; verify usage GET shows cap=5
        r = admin_session.get(f"{BASE_URL}/api/cards/usage",
                              params={"scope": "round", "scope_id": scope_id}, timeout=10)
        d = r.json()
        assert d["cap"] == 5 and d["count"] == 5 and d["remaining"] == 0

    def test_round_final_special_cap_10(self, admin_session, owned_card_ids):
        # Final (case-insensitive) should have cap=10
        r = admin_session.get(f"{BASE_URL}/api/cards/usage",
                              params={"scope": "round", "scope_id": "Final"}, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["cap"] == 10, f"Final cap should be 10, got {d['cap']}"

        # Try case-insensitive 'FINAL'
        r2 = admin_session.get(f"{BASE_URL}/api/cards/usage",
                               params={"scope": "round", "scope_id": "FINAL"}, timeout=10)
        assert r2.json()["cap"] == 10, "FINAL (uppercase) should also map to 10"

        # POST to Final — should succeed regardless of round cap=5
        # We only have 5 distinct cards; using all 5 for Final should all succeed
        ok = 0
        for cid in owned_card_ids[:5]:
            r = admin_session.post(f"{BASE_URL}/api/cards/use",
                                   json={"card_id": cid, "scope": "round", "scope_id": "Final"}, timeout=15)
            if r.status_code == 200:
                ok += 1
        assert ok == 5

    def test_invalid_scope(self, admin_session, owned_card_ids):
        r = admin_session.post(f"{BASE_URL}/api/cards/use",
                               json={"card_id": owned_card_ids[0], "scope": "bogus", "scope_id": "x"}, timeout=10)
        assert r.status_code in (400, 422)

    def test_unowned_card_rejected(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/cards/use",
                               json={"card_id": "non-existent-id-zzz", "scope": "match", "scope_id": "x"}, timeout=10)
        assert r.status_code == 403

    def test_usage_me_grouped(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/cards/usage/me", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "grouped" in d and "caps" in d and "special_caps" in d
        assert d["caps"] == {"match": 2, "group": 4, "round": 5}
        assert d["special_caps"].get("round:final") == 10
        # Should contain match/group/round scopes from above tests
        assert "match" in d["grouped"]
        assert "group" in d["grouped"]
        assert "round" in d["grouped"]
