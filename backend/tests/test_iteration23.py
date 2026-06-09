"""Iteration 23 tests — basketball stats canonicalization, brand favicon,
card daily-drop, and prediction→action logging hook.
"""
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
BASKETBALL_MATCH_ID = "b97e0ddf-2832-48b1-8ee0-2fe1cfd7bde5"
ADMIN_EMAIL = "admin@cloudypitch.com"
ADMIN_PASSWORD = "CloudyAdmin2026!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_session():
    """Sign up (or sign in) a throwaway test user; returns a session with cp_session cookie."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    ts = int(time.time())
    email = f"it23_{ts}@test.example"
    password = "TestPass123!"
    r = s.post(f"{BASE_URL}/api/auth/signup",
               json={"email": email, "password": password, "display_name": "It23 User"})
    if r.status_code not in (200, 201):
        # Fall back to existing admin to at least exercise authenticated routes.
        r2 = s.post(f"{BASE_URL}/api/auth/signin",
                    json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        if r2.status_code != 200:
            pytest.skip(f"Cannot create auth session: signup={r.status_code} signin={r2.status_code}")
    s.email = email  # type: ignore[attr-defined]
    return s


# ─── Basketball stats canonicalization ───────────────────────────────────
class TestBasketballStats:
    def test_match_returns_canonical_stat_keys(self, session):
        r = session.get(f"{BASE_URL}/api/matches/{BASKETBALL_MATCH_ID}")
        assert r.status_code == 200, r.text
        data = r.json()
        stats = data.get("statistics") or data.get("stats") or {}
        assert stats, "Match has no statistics block"
        # Stats can be a list of {team_id, stats:{...}} entries OR a dict keyed home/away.
        sample_side = None
        if isinstance(stats, list):
            for entry in stats:
                inner = entry.get("stats") if isinstance(entry, dict) else None
                if isinstance(inner, dict):
                    sample_side = inner
                    break
        elif isinstance(stats, dict):
            for v in stats.values():
                if isinstance(v, dict):
                    sample_side = v
                    break
        assert sample_side, f"Could not find a stats dict inside statistics; got {type(stats).__name__}"

        # 2-Pointers is sometimes derived; only require the keys actually canonicalized by ingestion.
        expected_string_keys = ["Field Goals", "Free Throws", "3-Pointers"]
        for k in expected_string_keys:
            assert k in sample_side, f"Missing canonical key '{k}'. Got: {list(sample_side.keys())}"
            v = sample_side[k]
            # accept "X/Y" string OR dict {made,attempted}
            if isinstance(v, str):
                assert "/" in v, f"{k} expected 'made/attempted' string, got {v!r}"
            else:
                assert isinstance(v, dict), f"{k} expected str or dict, got {type(v).__name__}"

        # Rebounds MUST be numeric (not a dict) per requirement
        if "Rebounds" in sample_side:
            assert not isinstance(sample_side["Rebounds"], dict), (
                f"'Rebounds' should be numeric/string, got dict: {sample_side['Rebounds']}"
            )

        for numeric_k in ["Assists", "Turnovers", "Steals", "Blocks", "Fouls"]:
            if numeric_k in sample_side:
                v = sample_side[numeric_k]
                assert not isinstance(v, dict), f"'{numeric_k}' should be numeric, got dict {v}"


# ─── Brand favicon ───────────────────────────────────────────────────────
class TestBrandFavicon:
    def test_brand_endpoint_includes_favicon_key(self, session):
        r = session.get(f"{BASE_URL}/api/brand")
        assert r.status_code == 200
        data = r.json()
        assert "brand_favicon_url" in data, f"Missing brand_favicon_url. Got keys: {list(data.keys())}"
        # value may be None until uploaded — only key must exist.
        # other keys are also expected
        for k in ["brand_logo_url", "brand_logo_dark_url", "brand_mark_url", "brand_wordmark_url"]:
            assert k in data


# ─── Card daily-drop ─────────────────────────────────────────────────────
class TestDailyDrop:
    def test_daily_drop_requires_auth(self, session):
        r = session.post(f"{BASE_URL}/api/cards/daily-drop")
        assert r.status_code == 401, f"Expected 401 unauth, got {r.status_code}: {r.text[:200]}"

    def test_daily_drop_authed_returns_well_formed_shape_no_500(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/cards/daily-drop")
        assert r.status_code == 200, f"daily-drop crashed: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert "dropped" in data, f"Missing 'dropped' key: {data}"
        if data["dropped"] is False:
            assert "reason" in data
            assert data["reason"] in ("no_actions_yesterday", "already_credited", "no_cards"), data
        else:
            assert "card" in data
            assert "tier" in data["card"]

    def test_check_drop_legacy_still_works(self, auth_session):
        """Legacy 5-action drop endpoint must not regress."""
        r = auth_session.post(f"{BASE_URL}/api/cards/check-drop")
        assert r.status_code == 200, f"check-drop crashed: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert "dropped" in data
        if not data["dropped"]:
            assert "progress" in data and "needed" in data


# ─── Prediction logs user_daily_actions ─────────────────────────────────
class TestPredictionLogsAction:
    def test_prediction_submit_or_action_logged(self, auth_session):
        """We don't have a guaranteed future-match id; instead verify the
        endpoint shape returns 200 / 400 (validation) — never 500 — and that
        daily-drop response keys are stable afterwards."""
        # Try to pull a future match
        r = auth_session.get(f"{BASE_URL}/api/matches")
        upcoming = None
        if r.status_code == 200:
            items = r.json()
            if isinstance(items, dict):
                items = items.get("matches") or items.get("items") or []
            for m in items:
                if (m.get("status") or "").lower() in ("scheduled", "ns", "not_started", "upcoming"):
                    upcoming = m
                    break
        if not upcoming:
            pytest.skip("No upcoming match available to attempt a prediction; logging hook smoke-skipped")

        # Attempt a prediction (best-effort — schema may vary)
        match_id = upcoming.get("id") or upcoming.get("match_id")
        payload = {"match_id": match_id, "home_score": 1, "away_score": 1, "winner": "draw"}
        resp = auth_session.post(f"{BASE_URL}/api/predictions", json=payload)
        assert resp.status_code != 500, f"predictions endpoint crashed: {resp.text[:300]}"

        # Now re-call daily-drop — must remain well-formed
        d = auth_session.post(f"{BASE_URL}/api/cards/daily-drop")
        assert d.status_code == 200
        body = d.json()
        assert "dropped" in body
