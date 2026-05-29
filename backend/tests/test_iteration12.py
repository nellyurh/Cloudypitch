"""Iteration 12 tests:
- league_tier_score country-aware
- COUNTRY_PRIORITY top-of-list
- _team_tokens / _cross_provider_dedup
- /api/matches grouped[] sort puts tier=100 leagues at top
"""
import os
import sys
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


# ------------ seed_data.league_tier_score ------------
class TestLeagueTierScore:
    def setup_method(self):
        from seed_data import league_tier_score
        self.lts = league_tier_score

    def test_premier_league_england_t1(self):
        assert self.lts("Premier League", "England") == 100

    def test_premier_league_bhutan_not_t1(self):
        v = self.lts("Premier League", "Bhutan")
        assert v != 100, f"Expected non-T1 for Bhutan, got {v}"

    def test_premier_league_belarus_not_t1(self):
        assert self.lts("Premier League", "Belarus") != 100

    def test_premier_league_egypt_not_t1(self):
        assert self.lts("Premier League", "Egypt") != 100

    def test_serie_a_italy_t1(self):
        assert self.lts("Serie A", "Italy") == 100

    def test_serie_a_brazil_not_t1(self):
        v = self.lts("Serie A", "Brazil")
        assert v != 100

    def test_ligue_1_france_t1(self):
        assert self.lts("Ligue 1", "France") == 100

    def test_ligue_1_algeria_not_t1(self):
        assert self.lts("Ligue 1", "Algeria") != 100

    def test_ligue_1_ivory_coast_not_t1(self):
        assert self.lts("Ligue 1", "Ivory Coast") != 100

    def test_ligue_1_playoffs_france_t1(self):
        v = self.lts("Ligue 1 Play-offs", "France")
        assert v == 100, f"got {v}"

    def test_ligue_1_relegation_playoffs_france_t1(self):
        v = self.lts("France: Ligue 1 - Relegation - Play Offs", "France")
        assert v == 100

    def test_la_liga_spain_t1(self):
        assert self.lts("La Liga", "Spain") == 100

    def test_la_liga_2_spain_t2(self):
        v = self.lts("La Liga 2", "Spain")
        assert v == 80, f"got {v}"

    def test_liga_2_spain_t2(self):
        assert self.lts("Liga 2", "Spain") == 80

    def test_bundesliga_germany_t1(self):
        assert self.lts("Bundesliga", "Germany") == 100

    def test_ucl_universal_t1(self):
        assert self.lts("UEFA Champions League", "Europe") == 100

    def test_world_cup_universal_t1(self):
        assert self.lts("FIFA World Cup", None) == 100


# ------------ COUNTRY_PRIORITY ------------
class TestCountryPriority:
    def test_continental_at_top(self):
        from seed_data import COUNTRY_PRIORITY
        assert COUNTRY_PRIORITY["World"] == 1
        assert COUNTRY_PRIORITY["Europe"] == 2
        assert COUNTRY_PRIORITY["International"] == 3
        assert COUNTRY_PRIORITY["England"] == 10
        # Europe must outrank England
        assert COUNTRY_PRIORITY["Europe"] < COUNTRY_PRIORITY["England"]


# ------------ ingestion._team_tokens / _cross_provider_dedup ------------
class TestTeamTokens:
    def setup_method(self):
        from ingestion import _team_tokens
        self.tok = _team_tokens

    def test_psg_full_name(self):
        toks = self.tok("Paris Saint-Germain")
        assert "paris" in toks
        assert "saint" in toks
        assert "germain" in toks

    def test_drops_fc_real_olympique(self):
        toks = self.tok("Real Madrid CF")
        assert "real" not in toks
        assert "madrid" in toks

    def test_olympique_dropped(self):
        toks = self.tok("Olympique Marseille")
        assert "olympique" not in toks
        assert "marseille" in toks

    def test_psg_paris_overlap(self):
        # 'Paris Saint-Germain' and 'PSG Paris' should both contain 'paris' so dedup matches.
        a = self.tok("Paris Saint-Germain")
        b = self.tok("PSG Paris")
        assert a & b, f"expected overlap, got a={a} b={b}"


# ------------ /api/matches grouped sort ------------
class TestMatchesGroupedSort:
    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=15)
        assert r.status_code == 200, r.text

    def test_grouped_top_is_tier_100(self):
        r = requests.get(f"{BASE_URL}/api/matches", params={"sport": "football"}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        grouped = body.get("grouped", [])
        if not grouped:
            pytest.skip("no football matches in window")
        # First group must have tier_score 100 (UCL or top-5 league)
        top = grouped[0]
        assert top.get("_tier") == 100, f"top group is not tier=100: {top.get('league_name')} tier={top.get('_tier')}"
        # No tier-30 or 80 league must appear before a tier-100 group
        seen_lower = False
        for g in grouped:
            t = g.get("_tier", 30)
            if t < 100:
                seen_lower = True
            elif t == 100 and seen_lower:
                pytest.fail(f"tier-100 league '{g.get('league_name')}' appears after a lower-tier league")

    def test_grouped_top_names_are_known_t1(self):
        r = requests.get(f"{BASE_URL}/api/matches", params={"sport": "football"}, timeout=30)
        body = r.json()
        grouped = body.get("grouped", [])
        if not grouped:
            pytest.skip("no matches")
        top_tier_names = [g.get("league_name", "").lower() for g in grouped if g.get("_tier") == 100]
        if not top_tier_names:
            pytest.skip("no tier=100 leagues in window")
        # At least one should look like UCL / Premier / Liga / Serie / Bundes / Ligue
        keywords = ["champions league", "premier league", "la liga", "laliga", "serie a", "bundesliga", "ligue 1", "world cup", "europa", "conference"]
        assert any(any(kw in n for kw in keywords) for n in top_tier_names), f"no recognised T1 names found: {top_tier_names[:10]}"
