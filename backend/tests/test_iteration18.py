"""Iteration 18 tests:
- Pool Pulse endpoint (/api/leaderboard/pulse)
- Worker module imports cleanly
- Regression on iteration 17 endpoints
"""
import os
import sys
import importlib
import pytest
import requests

def _resolve_base_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        # Fallback to frontend/.env (pytest run from shell may not inherit it)
        try:
            with open("/app/frontend/.env", "r") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert url, "REACT_APP_BACKEND_URL not set"
    return url.rstrip("/")


BASE_URL = _resolve_base_url()


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- Pool Pulse ----------
class TestPoolPulse:
    def test_pulse_default(self, client):
        r = client.get(f"{BASE_URL}/api/leaderboard/pulse", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "events" in d and isinstance(d["events"], list)
        assert "today" in d and isinstance(d["today"], dict)
        for k in ("card_spend_usd_cents", "pool_delta_usd_cents", "purchases"):
            assert k in d["today"], f"missing today.{k}"
            assert isinstance(d["today"][k], int)
        # pool delta is half of card spend
        assert d["today"]["pool_delta_usd_cents"] == d["today"]["card_spend_usd_cents"] // 2

    def test_pulse_limit_param(self, client):
        r = client.get(f"{BASE_URL}/api/leaderboard/pulse?limit=3", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert len(d["events"]) <= 3

    def test_pulse_event_shape(self, client):
        r = client.get(f"{BASE_URL}/api/leaderboard/pulse?limit=10", timeout=20)
        assert r.status_code == 200
        events = r.json()["events"]
        # Per agent note: 4 seeded card_purchase events exist
        for ev in events:
            assert "handle" in ev
            assert isinstance(ev["handle"], str)
            assert ev["handle"].startswith("@")
            assert "country_code" in ev
            assert "amount_usd_cents" in ev
            assert isinstance(ev["amount_usd_cents"], int)
            assert "pool_delta_usd_cents" in ev
            # pool delta = half of amount (50% goes to pool)
            assert ev["pool_delta_usd_cents"] == ev["amount_usd_cents"] // 2
            assert "created_at" in ev
            # card_name is optional but must be present as a key
            assert "card_name" in ev

    def test_pulse_handle_redacted(self, client):
        """Handle should be @First L. format, never expose full last names."""
        r = client.get(f"{BASE_URL}/api/leaderboard/pulse?limit=10", timeout=20)
        assert r.status_code == 200
        for ev in r.json()["events"]:
            handle = ev["handle"]
            assert handle.startswith("@"), f"handle should start with @: {handle}"
            # If multi-word, second word must be a single character + '.'
            rest = handle[1:].strip()
            parts = rest.split()
            if len(parts) >= 2:
                assert len(parts[1]) == 2 and parts[1].endswith("."), \
                    f"second token must be 'X.' not '{parts[1]}'"

    def test_pulse_today_aggregates_match_seed(self, client):
        """Per agent: 4 seeded card_purchase tx today (500+1000+250+750=2500 cents)."""
        r = client.get(f"{BASE_URL}/api/leaderboard/pulse?limit=10", timeout=20)
        d = r.json()
        # Allow at least the seeded 4 (in case of additional tx between iterations)
        assert d["today"]["purchases"] >= 4, f"expected >=4 purchases, got {d['today']['purchases']}"
        assert d["today"]["card_spend_usd_cents"] >= 2500
        assert d["today"]["pool_delta_usd_cents"] >= 1250

    def test_pulse_graceful_with_large_limit(self, client):
        r = client.get(f"{BASE_URL}/api/leaderboard/pulse?limit=1000", timeout=20)
        assert r.status_code == 200


# ---------- Worker module ----------
class TestWorker:
    def test_worker_imports_cleanly(self):
        """worker.py should import without raising."""
        sys.path.insert(0, "/app/backend")
        try:
            if "worker" in sys.modules:
                del sys.modules["worker"]
            mod = importlib.import_module("worker")
            assert hasattr(mod, "main"), "worker.main missing"
            assert callable(mod.main)
        finally:
            sys.path.pop(0)

    def test_server_respects_run_ingestion_env(self):
        """server.py source must read RUN_INGESTION env and have API-only branch."""
        with open("/app/backend/server.py", "r") as f:
            src = f.read()
        assert "RUN_INGESTION" in src, "RUN_INGESTION env var not referenced"
        assert "API-only" in src or "api-only" in src.lower(), "API-only log missing"


# ---------- Regression: iteration 17 endpoints ----------
class TestRegression:
    def test_leaderboard_global(self, client):
        r = client.get(f"{BASE_URL}/api/leaderboard?scope=global&limit=10", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "leaderboard" in d
        assert "pool" in d
        assert d["pool"]["total_usd_cents"] == d["pool"]["base_usd_cents"] + d["pool"]["cards_cut_usd_cents"]

    def test_leaderboard_prize_split(self, client):
        r = client.get(
            f"{BASE_URL}/api/leaderboard/prize-split?base_usd_cents=250000&cards_cut_usd_cents=0",
            timeout=15,
        )
        assert r.status_code == 200
        payouts = {p["position"]: p["usd_cents"] for p in r.json()["payouts"]}
        assert payouts[1] == 100000
        assert payouts[5] == 3125
        assert payouts[100] == 0

    def test_nba_playoffs(self, client):
        r = client.get(f"{BASE_URL}/api/nba/playoffs", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert len(d["rounds"]) == 4

    def test_referrals_leaderboard(self, client):
        r = client.get(f"{BASE_URL}/api/referrals/leaderboard?limit=10", timeout=20)
        assert r.status_code == 200

    def test_health(self, client):
        r = client.get(f"{BASE_URL}/api/health", timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True
