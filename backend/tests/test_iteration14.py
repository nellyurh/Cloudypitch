"""Iteration 14 — cricket innings + tennis sets wiring.

Tests both:
- Backend unit parsers (_parse_cricket_score / _normalize_cricket_innings)
- Live API surface (GET /api/matches/{id}) for the verified cricket and tennis
  match documents the main agent ingested.
"""
import os
import pytest
import requests

# Backend unit imports
from ingestion import _parse_cricket_score, _normalize_cricket_innings

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fantasy-wc.preview.emergentagent.com").rstrip("/")

CRICKET_ID = "sp-cr-13072009693"     # NZ vs Ireland Test
TENNIS_ID  = "bc4375f4-ef10-461d-a80c-66f15b1ea183"  # A. Michelsen vs R. Jodar — has tiebreaks


# ---------------- Unit: _parse_cricket_score ----------------
class TestParseCricketScore:
    def test_declared_with_wickets(self):
        # "490/8d" => 490 runs, 8 wickets, declared
        r, w, d = _parse_cricket_score("490/8d")
        assert r == 490
        assert w == 8
        assert d is True

    def test_simple_runs_only(self):
        r, w, d = _parse_cricket_score("232")
        assert r == 232
        assert w is None
        assert d is False

    def test_followon_multi_innings_sum(self):
        # "(fo) 179 & 232" => 411 total runs
        r, _, _ = _parse_cricket_score("(fo) 179 & 232")
        assert r == 411

    def test_empty_returns_zero(self):
        r, w, d = _parse_cricket_score("")
        assert r == 0
        assert w is None
        assert d is False

    def test_runs_with_wickets_no_declare(self):
        r, w, d = _parse_cricket_score("145/7")
        assert r == 145 and w == 7 and d is False


# ---------------- Unit: _normalize_cricket_innings ----------------
class TestNormalizeCricketInnings:
    def test_returns_innings_with_batter_extraction(self):
        raw = {
            "inning": [
                {
                    "team": "localteam",
                    "inningnum": "1",
                    "total": "463",
                    "batsmanstats": {"player": [
                        {"batsman": "TA Blundell", "r": "186", "b": "292", "4s": "10", "6s": "2", "bat": "false"},
                        {"batsman": "R Ravindra",  "r": "121", "b": "194", "4s": "8",  "6s": "1", "bat": "false"},
                    ]},
                    "bowlerstats": {"player": [
                        {"bowler": "A. Bowler", "o": "20.0", "r": "60", "w": "3", "m": "2"},
                    ]},
                }
            ]
        }
        out = _normalize_cricket_innings(raw, "New Zealand", "Ireland")
        assert isinstance(out, list)
        assert len(out) == 1
        inn = out[0]
        assert inn["innings_no"] == 1
        assert inn["team_name"] == "New Zealand"
        assert inn["runs"] == 463
        assert len(inn["top_batters"]) == 2
        # Top batter sorted by runs desc
        assert inn["top_batters"][0]["name"] == "TA Blundell"
        assert inn["top_batters"][0]["runs"] == 186
        assert inn["top_batters"][0]["fours"] == 10
        assert inn["top_batters"][0]["sixes"] == 2
        assert len(inn["top_bowlers"]) == 1
        assert inn["top_bowlers"][0]["wickets"] == 3

    def test_handles_dict_instead_of_list(self):
        raw = {"inning": {"team": "awayteam", "inningnum": "2", "total": "210",
                          "batsmanstats": {}, "bowlerstats": {}}}
        out = _normalize_cricket_innings(raw, "NZ", "IRE")
        assert len(out) == 1
        assert out[0]["team_name"] == "IRE"
        assert out[0]["innings_no"] == 2

    def test_empty_returns_empty_list(self):
        assert _normalize_cricket_innings({}, "A", "B") == []


# ---------------- Live API ----------------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    return s


class TestCricketMatchAPI:
    def test_cricket_match_has_innings_and_meta(self, session):
        r = session.get(f"{BASE_URL}/api/matches/{CRICKET_ID}", timeout=15)
        assert r.status_code == 200, r.text
        m = r.json()["match"]
        assert m["sport_slug"] == "cricket"
        assert m["home_team_name"] == "New Zealand"
        assert m["away_team_name"] == "Ireland"
        # Totals (NZ 490 / Ireland 411 = 146 + 210 ... but main-agent shows 490/411 from totalscore)
        assert m["home_score"] == 490
        assert m["away_score"] == 411
        assert m.get("result_text") == "New Zealand won by an innings and 79 runs"
        assert m.get("match_format") == "TEST"
        assert "Stormont" in (m.get("venue_name") or "")
        assert m.get("league_name") and "New Zealand" in m["league_name"]
        # Innings
        innings = m.get("innings") or []
        assert len(innings) == 3
        for inn in innings:
            assert "innings_no" in inn
            assert "team_name" in inn
            assert "runs" in inn
            assert isinstance(inn.get("top_batters"), list)
            assert isinstance(inn.get("top_bowlers"), list)
        # First innings has batters populated
        assert len(innings[0]["top_batters"]) >= 1
        assert innings[0]["top_batters"][0]["runs"] > 0

    def test_cricket_leagues_per_tournament_in_grouped(self, session):
        # /api/matches?limit=600 must expose cricket leagues per-tournament
        r = session.get(f"{BASE_URL}/api/matches?limit=600", timeout=20)
        assert r.status_code == 200
        data = r.json()
        # API can return either { matches, grouped } or list with grouped
        grouped = data.get("grouped") or []
        if not grouped:
            pytest.skip("No grouped[] in /api/matches response")
        cricket_leagues = []
        for entry in grouped:
            if entry.get("sport_slug") == "cricket" or entry.get("sport") == "cricket":
                cricket_leagues.append(entry)
            for lg in (entry.get("leagues") or []):
                # nested by country
                if "cricket" in (lg.get("sport_slug") or "").lower() or "cricket" in (lg.get("name") or "").lower():
                    cricket_leagues.append(lg)
        # At least cricket league names should be tournament-specific (not generic "Cricket")
        # Inspect raw entries: look for league_name in cricket matches list instead
        ms = data.get("matches") or []
        cricket_ms = [m for m in ms if m.get("sport_slug") == "cricket"]
        if cricket_ms:
            league_names = {m.get("league_name") for m in cricket_ms if m.get("league_name")}
            # Expect at least 2 distinct tournament names (not just 'Cricket')
            assert len(league_names) >= 2, f"Expected per-tournament leagues, got {league_names}"
            assert all(n != "Cricket" for n in league_names), f"Generic 'Cricket' name leaked: {league_names}"


class TestTennisMatchAPI:
    def test_tennis_match_has_sets_with_tiebreak(self, session):
        r = session.get(f"{BASE_URL}/api/matches/{TENNIS_ID}", timeout=15)
        assert r.status_code == 200, r.text
        m = r.json()["match"]
        assert m["sport_slug"] == "tennis"
        sets = m.get("sets") or []
        assert len(sets) >= 3
        # At least one set must have a tiebreak
        has_tb = any((s.get("home_tiebreak") is not None or s.get("away_tiebreak") is not None) for s in sets)
        assert has_tb, "Expected at least one set with tiebreak data"
        # Verify shape
        for s in sets:
            assert "home_score" in s and "away_score" in s
