"""Iteration 3 backend tests: World Cup hub + StatPal logo enrichment."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback to reading frontend/.env directly
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# -------- World Cup hub --------
class TestWorldCup:
    def test_hub_returns_12_groups_and_meta(self, api):
        r = api.get(f"{BASE_URL}/api/worldcup", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "starts_at" in data
        assert data["starts_at"].startswith("2026-06-11")
        groups = data.get("groups", [])
        assert len(groups) == 12, f"Expected 12 groups got {len(groups)}"
        letters = sorted([g.get("group") for g in groups])
        assert letters == list("ABCDEFGHIJKL")
        # each group has 4 teams
        for g in groups:
            assert len(g.get("teams", [])) == 4, f"group {g.get('group')} has {len(g.get('teams', []))} teams"
        # prize pool + competition objects present (may be None but key must exist)
        assert "prize_pool" in data
        assert "competition" in data

    def test_groups_endpoint(self, api):
        r = api.get(f"{BASE_URL}/api/worldcup/groups", timeout=15)
        assert r.status_code == 200
        gs = r.json().get("groups", [])
        assert len(gs) == 12

    def test_bracket_endpoint(self, api):
        r = api.get(f"{BASE_URL}/api/worldcup/bracket", timeout=15)
        assert r.status_code == 200
        rounds = r.json().get("rounds", [])
        names = [x["name"] for x in rounds]
        assert "Round of 32" in names
        assert "Final" in names


# -------- StatPal logo enrichment --------
class TestStatPalLogos:
    def test_statpal_football_logo_coverage(self):
        """At least 70/127 statpal football matches should have BOTH home and away logos."""
        import asyncio
        import sys
        sys.path.insert(0, "/app/backend")
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        # Fallback reading backend/.env
        if not mongo_url or not db_name:
            with open("/app/backend/.env") as f:
                for line in f:
                    if line.startswith("MONGO_URL="):
                        mongo_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if line.startswith("DB_NAME="):
                        db_name = line.split("=", 1)[1].strip().strip('"').strip("'")

        async def run():
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            total = await db.matches.count_documents({"primary_provider": "statpal", "sport_slug": "football"})
            with_both = await db.matches.count_documents({
                "primary_provider": "statpal",
                "sport_slug": "football",
                "home_team_logo": {"$nin": [None, ""]},
                "away_team_logo": {"$nin": [None, ""]},
            })
            client.close()
            return total, with_both

        total, with_both = asyncio.get_event_loop().run_until_complete(run()) if False else asyncio.run(run())
        print(f"StatPal football matches: total={total}, with_both_logos={with_both}")
        assert total > 0, "No statpal football matches found at all"
        # Spec: at least 70 out of ~127
        assert with_both >= 70, f"Only {with_both}/{total} statpal football matches have both logos (expected >=70)"


# -------- Logos preserved on Sportmonks/API-Sports football matches (regression) --------
class TestFootballListLogos:
    def test_football_list_has_logos(self, api):
        r = api.get(f"{BASE_URL}/api/matches?sport=football&limit=50", timeout=20)
        assert r.status_code == 200
        body = r.json()
        # could be {matches:[...]} or [...]
        matches = body.get("matches") if isinstance(body, dict) else body
        if isinstance(matches, dict):
            # grouped by status?
            flat = []
            for v in matches.values():
                if isinstance(v, list):
                    flat.extend(v)
            matches = flat
        assert matches and len(matches) > 0, "No matches returned"
        sm_or_apisports = [m for m in matches if m.get("primary_provider") in ("sportmonks", "api-sports")]
        if not sm_or_apisports:
            pytest.skip("No sportmonks/api-sports matches in current sample")
        with_logos = [m for m in sm_or_apisports if m.get("home_team_logo") and m.get("away_team_logo")]
        ratio = len(with_logos) / len(sm_or_apisports)
        print(f"sportmonks/api-sports logo ratio: {len(with_logos)}/{len(sm_or_apisports)} = {ratio:.2%}")
        assert ratio >= 0.6, f"Logo ratio too low: {ratio:.2%}"
