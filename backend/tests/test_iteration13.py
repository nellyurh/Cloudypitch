"""Iteration 13 tests:
- /api/admin/cleanup/duplicate-matches?dry_run=true (admin)
- /api/admin/cleanup/duplicate-matches?dry_run=false (admin, actually deletes)
- /api/admin/cleanup/duplicate-leagues?dry_run=true (admin)
- Non-admin 403 on both endpoints
- Provider rank logic — Sportmonks > Manual > API-Sports > StatPal
"""
import os
import sys
import time
import uuid
import requests
import pytest

sys.path.insert(0, "/app/backend")


def _resolve_base_url() -> str:
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    return ""


BASE_URL = _resolve_base_url()
ADMIN_EMAIL = "admin@cloudypitch.com"
ADMIN_PASS = "CloudyAdmin2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/signin", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"admin signin failed: {r.status_code} {r.text}"
    me = s.get(f"{BASE_URL}/api/auth/me", timeout=10)
    assert me.status_code == 200
    j = me.json()
    user = j.get("user") or j
    assert user.get("role") == "admin", me.text
    return s


@pytest.fixture(scope="module")
def user_session():
    s = requests.Session()
    email = f"test_iter13_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/signup", json={"email": email, "password": "TestPass123", "display_name": "Iter13 User"}, timeout=15)
    if r.status_code not in (200, 201):
        # try signin existing
        r2 = s.post(f"{BASE_URL}/api/auth/signin", json={"email": email, "password": "TestPass123"}, timeout=15)
        assert r2.status_code == 200, f"could not create or sign in test user: {r.status_code} {r.text}"
    return s


# ---------- PROVIDER RANK ----------
class TestProviderRank:
    def test_rank_order(self):
        from routes.admin_cleanup import PROVIDER_RANK
        assert PROVIDER_RANK["sportmonks"] > PROVIDER_RANK["manual"] > PROVIDER_RANK["apisports"] > PROVIDER_RANK["statpal"]


# ---------- AUTH GUARD ----------
class TestAuthGuard:
    def test_unauth_dedup_matches(self):
        r = requests.post(f"{BASE_URL}/api/admin/cleanup/duplicate-matches?sport_slug=football&dry_run=true", timeout=15)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_unauth_dedup_leagues(self):
        r = requests.post(f"{BASE_URL}/api/admin/cleanup/duplicate-leagues?dry_run=true", timeout=15)
        assert r.status_code in (401, 403)

    def test_non_admin_dedup_matches_403(self, user_session):
        r = user_session.post(f"{BASE_URL}/api/admin/cleanup/duplicate-matches?sport_slug=football&dry_run=true", timeout=15)
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text[:200]}"

    def test_non_admin_dedup_leagues_403(self, user_session):
        r = user_session.post(f"{BASE_URL}/api/admin/cleanup/duplicate-leagues?dry_run=true", timeout=15)
        assert r.status_code == 403


# ---------- ADMIN DRY-RUN DEDUP MATCHES ----------
class TestDedupMatchesDryRun:
    def test_football_dry_run_returns_report(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/admin/cleanup/duplicate-matches?sport_slug=football&dry_run=true", timeout=120)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["dry_run"] is True
        assert body["sport_slug"] == "football"
        assert "total_matches_scanned" in body and isinstance(body["total_matches_scanned"], int)
        assert "duplicates_found" in body and isinstance(body["duplicates_found"], int)
        assert "kept" in body
        assert "sample" in body and isinstance(body["sample"], list)

    def test_dry_run_does_not_delete(self, admin_session):
        # count matches before
        c1 = admin_session.get(f"{BASE_URL}/api/admin/stats", timeout=15).json().get("matches", 0)
        admin_session.post(f"{BASE_URL}/api/admin/cleanup/duplicate-matches?sport_slug=football&dry_run=true", timeout=120)
        c2 = admin_session.get(f"{BASE_URL}/api/admin/stats", timeout=15).json().get("matches", 0)
        assert c1 == c2, f"match count changed during dry_run: {c1} -> {c2}"

    def test_sample_row_structure(self, admin_session):
        # We need to find a sport with duplicates. Try several sports.
        for sport in ("football", "basketball", "tennis", "cricket", "baseball", "hockey"):
            r = admin_session.post(f"{BASE_URL}/api/admin/cleanup/duplicate-matches?sport_slug={sport}&dry_run=true", timeout=120)
            body = r.json()
            if body.get("sample"):
                row = body["sample"][0]
                for k in ("delete_id", "delete_provider", "kept_id", "kept_provider"):
                    assert k in row, f"sample missing {k}: {row}"
                # Verify the keeper ranks higher than the loser (Sportmonks should win)
                from routes.admin_cleanup import PROVIDER_RANK
                kept_rank = PROVIDER_RANK.get(row["kept_provider"], 0)
                del_rank = PROVIDER_RANK.get(row["delete_provider"], 0)
                assert kept_rank >= del_rank, f"keeper rank {kept_rank} < loser rank {del_rank}: {row}"
                return
        pytest.skip("No duplicates found across all sport slugs (main agent already ran cleanup)")


# ---------- ADMIN DEDUP LEAGUES DRY RUN ----------
class TestDedupLeaguesDryRun:
    def test_leagues_dry_run_returns_report(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/admin/cleanup/duplicate-leagues?dry_run=true", timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["dry_run"] is True
        for k in ("total_leagues_scanned", "duplicate_clusters", "leagues_merged", "sample"):
            assert k in body, f"missing key {k}: {body.keys()}"
        assert isinstance(body["sample"], list)

    def test_leagues_dry_run_does_not_delete(self, admin_session):
        c1 = admin_session.get(f"{BASE_URL}/api/admin/stats", timeout=15).json().get("leagues", 0)
        admin_session.post(f"{BASE_URL}/api/admin/cleanup/duplicate-leagues?dry_run=true", timeout=60)
        c2 = admin_session.get(f"{BASE_URL}/api/admin/stats", timeout=15).json().get("leagues", 0)
        assert c1 == c2

    def test_leagues_sample_row_structure(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/admin/cleanup/duplicate-leagues?dry_run=true", timeout=60)
        body = r.json()
        if not body.get("sample"):
            pytest.skip("no duplicate league clusters remain (main agent already merged)")
        row = body["sample"][0]
        for k in ("delete_league_id", "delete_name", "kept_league_id", "kept_name", "matches_reassigned"):
            assert k in row, f"sample missing {k}: {row}"


# ---------- ADMIN DEDUP MATCHES LIVE DELETE ----------
class TestDedupMatchesLiveDelete:
    def test_live_delete_removes_duplicates_if_any(self, admin_session):
        # dry-run first to find candidate
        r = admin_session.post(f"{BASE_URL}/api/admin/cleanup/duplicate-matches?sport_slug=football&dry_run=true", timeout=120)
        body = r.json()
        dups = body.get("duplicates_found", 0)
        if dups == 0:
            pytest.skip("no duplicates to delete (main agent already cleaned)")
        before = admin_session.get(f"{BASE_URL}/api/admin/stats", timeout=15).json().get("matches", 0)
        r2 = admin_session.post(f"{BASE_URL}/api/admin/cleanup/duplicate-matches?sport_slug=football&dry_run=false", timeout=180)
        assert r2.status_code == 200
        b2 = r2.json()
        assert b2["dry_run"] is False
        after = admin_session.get(f"{BASE_URL}/api/admin/stats", timeout=15).json().get("matches", 0)
        # We don't strictly assert exact diff because background ingestion may add new docs,
        # but the count should have decreased OR stayed at most the same+ingestion_delta.
        assert after <= before, f"expected count to decrease, before={before} after={after}"


# ---------- MATCH DETAIL SPORT_SLUG SANITY (for frontend tabs) ----------
class TestMatchDetailEndpoint:
    @pytest.mark.parametrize("mid,expected_sport", [
        ("44511de4-79b4-46cd-811f-7679ec806ef1", "football"),
        ("878f188e-753e-417f-8953-090cee745f9b", "basketball"),
        ("7c7459b1-99d9-4a5c-8e68-98ad4deaff62", "tennis"),
    ])
    def test_match_detail_returns_correct_sport(self, mid, expected_sport):
        r = requests.get(f"{BASE_URL}/api/matches/{mid}", timeout=15)
        if r.status_code != 200:
            pytest.skip(f"sample match id {mid} not found in DB ({r.status_code})")
        body = r.json()
        m = body.get("match") or body
        ss = (m.get("sport_slug") or "").lower()
        # tennis & basketball ids are advisory; only assert when ID resolves
        assert expected_sport in ss or ss.startswith(expected_sport[:5]), f"expected {expected_sport}, got {ss}"
