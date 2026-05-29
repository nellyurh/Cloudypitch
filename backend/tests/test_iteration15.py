"""Iteration 15/16 tests — Sportmonks Pro plan data + Standings + Momentum + API-Sports basketball stats."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fantasy-wc.preview.emergentagent.com").rstrip("/")
# Sample IDs from review_request
FOOTBALL_MATCH = "44511de4-79b4-46cd-811f-7679ec806ef1"  # Flamengo vs Palmeiras Serie A
BASKETBALL_MATCH = "878f188e-753e-417f-8953-090cee745f9b"
BASKETBALL_MATCH_WITH_GAME_ID = "4e83d710-6da9-4c17-93ad-61e5e875b12e"  # BSN match with api_sports_game_id=493729


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


# ----------------- Standings endpoint -----------------
class TestStandings:
    def test_football_standings_returns_rows(self, s):
        r = s.get(f"{BASE_URL}/api/matches/{FOOTBALL_MATCH}/standings", timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert "standings" in body and "highlight_team_ids" in body
        assert isinstance(body["standings"], list)
        # Expect approximately 20 rows for Brazilian Serie A
        assert len(body["standings"]) >= 10, f"Expected league standings rows, got {len(body['standings'])}"
        # Each row should have position, team_id, team_name, points
        row = body["standings"][0]
        for k in ("position", "team_id", "team_name", "points"):
            assert k in row, f"Standings row missing key {k}: {row}"
        # Highlight should contain both team_ids
        assert len(body["highlight_team_ids"]) == 2
        # Highlighted teams should also appear in the rows
        ids_in_rows = {r["team_id"] for r in body["standings"]}
        highlight_present = [hid for hid in body["highlight_team_ids"] if hid in ids_in_rows]
        assert len(highlight_present) >= 1, "Neither home nor away team appears in standings rows"

    def test_unknown_match_returns_empty(self, s):
        r = s.get(f"{BASE_URL}/api/matches/non-existent-match-id-xyz/standings", timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert body["standings"] == []
        assert body["highlight_team_ids"] == []


# ----------------- Momentum endpoint -----------------
class TestMomentum:
    def test_football_momentum_shape(self, s):
        r = s.get(f"{BASE_URL}/api/matches/{FOOTBALL_MATCH}/momentum", timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert "momentum" in body
        assert "home_team_id" in body
        assert "away_team_id" in body
        assert isinstance(body["momentum"], list)
        # Past match: pressure[] usually empty
        for item in body["momentum"]:
            assert isinstance(item, dict)
            for k in ("minute", "team_id", "value"):
                assert k in item

    def test_unknown_match_404(self, s):
        r = s.get(f"{BASE_URL}/api/matches/non-existent-match-id-xyz/momentum", timeout=20)
        assert r.status_code == 404


# ----------------- Football match-detail with Pro fields -----------------
class TestFootballMatchDetailProFields:
    def test_match_detail_refresh_returns_pro_fields(self, s):
        # Trigger lazy refresh
        r = s.get(f"{BASE_URL}/api/matches/{FOOTBALL_MATCH}?refresh=1", timeout=60)
        assert r.status_code == 200
        body = r.json()
        m = body["match"]
        # weather may be None if Sportmonks didn't return — assert key existence + structure if present
        if m.get("weather"):
            w = m["weather"]
            assert isinstance(w, dict)
            # Spec: weather flattened to {temperature_celcius, type, icon, humidity, wind}
            allowed_keys = {"temperature_celcius", "type", "icon", "humidity", "wind"}
            assert set(w.keys()).issubset(allowed_keys), f"Unexpected weather keys: {w.keys()}"
        # tv_stations: list of strings
        if m.get("tv_stations"):
            assert isinstance(m["tv_stations"], list)
            assert all(isinstance(x, str) for x in m["tv_stations"])
            assert len(m["tv_stations"]) <= 6
        # referees: list of {name, type}
        if m.get("referees"):
            assert isinstance(m["referees"], list)
            for ref in m["referees"]:
                assert "name" in ref and "type" in ref


# ----------------- API-Sports basketball stats lazy fetch -----------------
class TestBasketballLazyStats:
    def test_basketball_match_detail(self, s):
        r = s.get(f"{BASE_URL}/api/matches/{BASKETBALL_MATCH}?refresh=1", timeout=60)
        # Match may not exist if not ingested — skip rather than fail
        if r.status_code == 404:
            pytest.skip(f"Basketball match {BASKETBALL_MATCH} not ingested")
        assert r.status_code == 200
        body = r.json()
        m = body["match"]
        assert m.get("sport_slug") == "basketball"
        # After refresh, statistics should populate if api_sports_game_id was set
        # Try again to allow ingestion to settle
        r2 = s.get(f"{BASE_URL}/api/matches/{BASKETBALL_MATCH}", timeout=30)
        assert r2.status_code == 200
        body2 = r2.json()
        stats = body2.get("statistics", [])
        # Stats may be empty if api_sports_game_id missing on this specific match — log
        if not stats:
            print(f"INFO: No statistics for basketball match {BASKETBALL_MATCH}. api_sports_game_id={m.get('api_sports_game_id')}")
        else:
            assert isinstance(stats, list)
            assert len(stats) >= 1
            s0 = stats[0]
            assert "stats" in s0
            assert isinstance(s0["stats"], dict)

    def test_basketball_lazy_fetch_with_game_id(self, s):
        """Verify lazy fetch populates statistics when match has api_sports_game_id."""
        r = s.get(f"{BASE_URL}/api/matches/{BASKETBALL_MATCH_WITH_GAME_ID}?refresh=1", timeout=60)
        if r.status_code == 404:
            pytest.skip("Match not found")
        assert r.status_code == 200
        body = r.json()
        stats = body.get("statistics", [])
        assert len(stats) == 2, f"Expected 2 team stat rows, got {len(stats)}"
        for row in stats:
            assert "team_id" in row
            assert "stats" in row
            sd = row["stats"]
            assert isinstance(sd, dict)
            # Basketball expected keys
            expected_any = {"field_goals", "freethrows_goals", "threepoint_goals", "rebounds", "assists"}
            assert expected_any & set(sd.keys()), f"No basketball stat keys present: {list(sd.keys())}"
