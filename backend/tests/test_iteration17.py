"""Iteration 17 tests:
- Unified leaderboard (global/weekly/premium) + prize pool
- Prize-split math correctness
- Referrals leaderboard separate
- NBA playoffs endpoint
- Regression on core routes
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fantasy-wc.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- Unified Leaderboard ----------
class TestUnifiedLeaderboard:
    def test_global_scope(self, client):
        r = client.get(f"{BASE_URL}/api/leaderboard?scope=global&limit=20", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "leaderboard" in d and isinstance(d["leaderboard"], list)
        assert "pool" in d
        assert "base_usd_cents" in d["pool"]
        assert "cards_cut_usd_cents" in d["pool"]
        assert "total_usd_cents" in d["pool"]
        assert d["pool"]["total_usd_cents"] == d["pool"]["base_usd_cents"] + d["pool"]["cards_cut_usd_cents"]
        assert d["scope"] == "global"
        # Verify sorted desc by total_points + has rank + potential_prize
        prev = None
        for i, row in enumerate(d["leaderboard"], 1):
            assert row["rank"] == i
            assert "potential_prize_usd_cents" in row
            assert "total_points" in row
            assert "prediction_points" in row
            assert "fantasy_points" in row
            assert "wc_fantasy_points" in row
            if prev is not None:
                assert row["total_points"] <= prev
            prev = row["total_points"]

    def test_weekly_scope(self, client):
        r = client.get(f"{BASE_URL}/api/leaderboard?scope=weekly&limit=20", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["scope"] == "weekly"
        assert isinstance(d["leaderboard"], list)

    def test_premium_scope(self, client):
        r = client.get(f"{BASE_URL}/api/leaderboard?scope=premium&limit=20", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["scope"] == "premium"
        # Every entry must be premium
        for row in d["leaderboard"]:
            assert row["is_premium"] is True


# ---------- Prize Split Math ----------
class TestPrizeSplit:
    def test_prize_split_with_cards_cut(self, client):
        r = client.get(
            f"{BASE_URL}/api/leaderboard/prize-split?base_usd_cents=250000&cards_cut_usd_cents=500000",
            timeout=15,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["base_usd_cents"] == 250000
        assert d["cards_cut_usd_cents"] == 500000
        assert d["total_usd_cents"] == 750000
        payouts = {p["position"]: p["usd_cents"] for p in d["payouts"]}
        # Expected: Pos1=$1312.50, Pos4=$512.50, Pos5=$144.88, Pos15=$144.88,
        #          Pos16=$60.66, Pos20=$60.66, Pos21=$29.41, Pos100=$29.41
        assert payouts[1] == 131250, f"Pos1 expected 131250 got {payouts[1]}"
        assert payouts[2] == 81250, f"Pos2 expected 81250 got {payouts[2]}"
        assert payouts[3] == 61250
        assert payouts[4] == 51250, f"Pos4 expected 51250 got {payouts[4]}"
        assert payouts[5] == 14488, f"Pos5 expected 14488 got {payouts[5]}"
        assert payouts[15] == 14488, f"Pos15 expected 14488 got {payouts[15]}"
        assert payouts[16] == 6066, f"Pos16 expected 6066 got {payouts[16]}"
        assert payouts[20] == 6066, f"Pos20 expected 6066 got {payouts[20]}"
        assert payouts[21] == 2941, f"Pos21 expected 2941 got {payouts[21]}"
        assert payouts[100] == 2941, f"Pos100 expected 2941 got {payouts[100]}"
        assert len(payouts) == 100

    def test_prize_split_zero_cards_cut(self, client):
        r = client.get(
            f"{BASE_URL}/api/leaderboard/prize-split?base_usd_cents=250000&cards_cut_usd_cents=0",
            timeout=15,
        )
        assert r.status_code == 200
        d = r.json()
        payouts = {p["position"]: p["usd_cents"] for p in d["payouts"]}
        # Positions 21+ should be 0 (no cards-cut accumulated yet)
        assert payouts[21] == 0
        assert payouts[100] == 0
        # Top4 base still applies
        assert payouts[1] == 100000
        assert payouts[2] == 50000
        assert payouts[3] == 30000
        assert payouts[4] == 20000
        # Pos 5-20 split $500 equally = $31.25
        assert payouts[5] == 3125
        assert payouts[20] == 3125


# ---------- Referrals (separate) ----------
class TestReferralsLeaderboard:
    def test_referrals_leaderboard(self, client):
        r = client.get(f"{BASE_URL}/api/referrals/leaderboard?limit=20", timeout=20)
        assert r.status_code == 200
        d = r.json()
        # Either {"leaderboard":[...]} or {"entries":[...]} - inspect & assert list-like
        assert isinstance(d, dict)
        # find a list-of-rows key
        lst = None
        for k in ("leaderboard", "entries", "rows", "referrals"):
            if isinstance(d.get(k), list):
                lst = d[k]; break
        assert lst is not None, f"Referrals leaderboard returned: {d.keys()}"


# ---------- NBA Playoffs ----------
class TestNbaPlayoffs:
    def test_playoffs_structure(self, client):
        r = client.get(f"{BASE_URL}/api/nba/playoffs", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "rounds" in d and isinstance(d["rounds"], list)
        assert len(d["rounds"]) == 4
        names = [rnd["name"] for rnd in d["rounds"]]
        assert names == ["First Round", "Conference Semifinals", "Conference Finals", "Finals"]
        for rnd in d["rounds"]:
            assert "series" in rnd
            assert isinstance(rnd["series"], list)
        assert "total_series" in d
        assert isinstance(d["total_series"], int)


# ---------- Regression ----------
class TestRegression:
    def test_matches_list(self, client):
        r = client.get(f"{BASE_URL}/api/matches?sport=football&limit=5", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "matches" in d
        assert "grouped" in d
        assert "count" in d

    def test_wc_games(self, client):
        r = client.get(f"{BASE_URL}/api/wc/games/today", timeout=20)
        assert r.status_code == 200

    def test_fantasy_players(self, client):
        r = client.get(f"{BASE_URL}/api/fantasy/players", timeout=20)
        assert r.status_code in (200, 401, 403)

    def test_predictions_upcoming(self, client):
        r = client.get(f"{BASE_URL}/api/predictions/upcoming", timeout=20)
        assert r.status_code in (200, 401, 403)

    def test_wallet_me(self, client):
        r = client.get(f"{BASE_URL}/api/wallet/me", timeout=20)
        assert r.status_code in (200, 401, 403)

    def test_cards(self, client):
        r = client.get(f"{BASE_URL}/api/cards", timeout=20)
        assert r.status_code in (200, 401, 403)
