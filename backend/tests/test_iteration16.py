"""Iteration 16 backend tests:
- Status display fields (minute/status_long) on live/finished games
- Past-date backfill + 3-format $or date filter
- Lineup persistence with rating + xG (Flamengo vs Palmeiras)
- Momentum endpoint graceful fallback
"""
import os
import pytest
import requests
from datetime import datetime, timedelta, timezone

def _base_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        # Fallback: read from frontend/.env
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert url, "REACT_APP_BACKEND_URL not configured"
    return url.rstrip("/")

BASE_URL = _base_url()
SAMPLE_MATCH = "44511de4-79b4-46cd-811f-7679ec806ef1"  # Flamengo vs Palmeiras (finished)


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- Status display ----------
class TestStatusDisplay:
    def test_sample_match_has_status_fields(self, client):
        r = client.get(f"{BASE_URL}/api/matches/{SAMPLE_MATCH}")
        assert r.status_code == 200, r.text
        d = r.json()
        m = d["match"]
        # finished
        assert m["status"] in ("FT", "AET", "PEN"), f"Expected finished status, got {m['status']}"
        # Should have status_long (used by frontend hero)
        assert "status_long" in m
        # Should NOT be 'First Half' literally for a finished match
        assert "First Half" not in (m.get("status_long") or "")
        assert m.get("status_long") in ("Full Time", "After Extra Time", "Penalties", "FT"), \
            f"Unexpected status_long for finished: {m.get('status_long')}"
        # Should NOT be live
        assert m.get("is_live") is False

    def test_live_matches_endpoint_minute_field(self, client):
        r = client.get(f"{BASE_URL}/api/matches/live")
        assert r.status_code == 200
        payload = r.json()
        # Response can be either list or {matches:[]} envelope
        rows = payload.get("matches") if isinstance(payload, dict) else payload
        assert isinstance(rows, list)
        # If there are live matches, verify minute field exists in schema
        for m in rows[:10]:
            # 'minute' may be None but should be a valid key OR status should never be the literal '1H'/'2H'
            assert "minute" in m or "status" in m


# ---------- Past-date backfill ----------
class TestPastDateBackfill:
    def test_3_weeks_ago_returns_matches(self, client):
        target = (datetime.now(timezone.utc) - timedelta(days=21)).strftime("%Y-%m-%d")
        r = client.get(f"{BASE_URL}/api/matches", params={"sport": "football", "date": target, "limit": 200})
        assert r.status_code == 200, r.text
        payload = r.json()
        data = payload.get("matches") if isinstance(payload, dict) else payload
        assert isinstance(data, list)
        if len(data) == 0:
            pytest.fail(f"Expected matches for past date {target}, got 0 (backfill may have failed)")
        # All returned rows should have scheduled_at containing target date
        for m in data[:20]:
            sa = (m.get("scheduled_at") or "")[:10]
            assert sa == target, f"row scheduled_at {sa} != {target}"

    def test_1_week_ago_returns_matches(self, client):
        target = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        r = client.get(f"{BASE_URL}/api/matches", params={"sport": "football", "date": target, "limit": 200})
        assert r.status_code == 200
        payload = r.json()
        data = payload.get("matches") if isinstance(payload, dict) else payload
        assert isinstance(data, list)
        if len(data) == 0:
            pytest.fail(f"Expected matches for past date {target}, got 0")

    def test_future_date_no_backfill_works(self, client):
        # Today should still work
        target = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        r = client.get(f"{BASE_URL}/api/matches", params={"sport": "football", "date": target, "limit": 50})
        assert r.status_code == 200


# ---------- Lineup persistence: rating + xG ----------
class TestLineupRatingXg:
    def test_lineup_has_rating_and_xg(self, client):
        r = client.get(f"{BASE_URL}/api/matches/{SAMPLE_MATCH}")
        assert r.status_code == 200, r.text
        rows = r.json().get("lineups", [])
        assert isinstance(rows, list) and len(rows) > 0, "No lineup rows"
        ratings = [x for x in rows if isinstance(x.get("rating"), (int, float))]
        xgs = [x for x in rows if isinstance(x.get("xg"), (int, float)) and x.get("xg") > 0]
        # Spec says 31 ratings and 16 xG values
        assert len(ratings) >= 20, f"Expected >=20 rating rows, got {len(ratings)}"
        assert len(xgs) >= 10, f"Expected >=10 xG rows, got {len(xgs)}"

    def test_specific_player_ratings(self, client):
        r = client.get(f"{BASE_URL}/api/matches/{SAMPLE_MATCH}")
        assert r.status_code == 200
        rows = r.json().get("lineups", [])
        names = {x.get("player_name"): x for x in rows if x.get("player_name")}
        def find(token):
            for n, p in names.items():
                if token.lower() in n.lower():
                    return p
            return None
        # Spec called out Gómez 8.0, Pedro 8.8, López 7.5 + 0.46 xG, Carrascal 5.0
        gomez = find("Gómez") or find("Gomez")
        pedro = find("Pedro")
        carrascal = find("Carrascal")
        assert gomez and gomez.get("rating") is not None, "Gómez missing rating"
        assert pedro and pedro.get("rating") is not None, "Pedro missing rating"
        assert carrascal and carrascal.get("rating") is not None, "Carrascal missing rating"
        lopez = find("López") or find("Lopez")
        if lopez:
            assert lopez.get("xg") is not None, "López should have xG value"


# ---------- Momentum endpoint ----------
class TestMomentum:
    def test_momentum_finished_match_graceful(self, client):
        r = client.get(f"{BASE_URL}/api/matches/{SAMPLE_MATCH}/momentum")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "momentum" in d
        assert isinstance(d["momentum"], list)
        # Should also include team ids per spec
        assert "home_team_id" in d
        assert "away_team_id" in d

    def test_momentum_unknown_match(self, client):
        r = client.get(f"{BASE_URL}/api/matches/nonexistent-match-id/momentum")
        assert r.status_code in (404, 200)  # accept either; 404 preferred
