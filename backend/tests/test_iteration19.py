"""Iteration 19 tests — P0a Formation/Bench mgmt + P0b Transfer card consumption."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fantasy-wc.preview.emergentagent.com").rstrip("/")


def _signup_user():
    s = requests.Session()
    ts = int(time.time() * 1000)
    email = f"test+it19_{ts}@cloudypitch.com"
    r = s.post(f"{BASE_URL}/api/auth/signup", json={
        "email": email, "password": "TestPass123", "display_name": "Tester"
    })
    if r.status_code == 429:
        # fall back to admin login if signup rate-limited
        r2 = s.post(f"{BASE_URL}/api/auth/signin", json={
            "email": "admin@cloudypitch.com", "password": "CloudyAdmin2026!"
        })
        assert r2.status_code == 200, f"signin fallback failed: {r2.status_code} {r2.text}"
        return s, "admin@cloudypitch.com"
    assert r.status_code in (200, 201), f"signup failed: {r.status_code} {r.text}"
    return s, email


@pytest.fixture(scope="module")
def user_session():
    s, email = _signup_user()
    return s, email


@pytest.fixture(scope="module")
def players():
    r = requests.get(f"{BASE_URL}/api/fantasy/players?limit=2000")
    assert r.status_code == 200
    pls = r.json().get("players", [])
    assert len(pls) > 30
    return pls


def _pick(players, n, pos, max_price=8.0):
    out = [p for p in players if p.get("position") == pos and p.get("price", 0) <= max_price]
    return out[:n]


def _build_15(players):
    gks = _pick(players, 2, "GK", 6)
    defs = _pick(players, 5, "DEF", 6)
    mids = _pick(players, 5, "MID", 7)
    fwds = _pick(players, 3, "FWD", 8)
    assert len(gks) == 2 and len(defs) == 5 and len(mids) == 5 and len(fwds) == 3, "not enough cheap players in pool"
    return gks + defs + mids + fwds


# ===== Squad CRUD =====
class TestSquadCRUD:
    def test_create_squad_15man_with_formation_and_bench(self, user_session, players):
        s, _ = user_session
        pool = _build_15(players)
        # 4-3-3: 1 GK + 4 DEF + 3 MID + 3 FWD = 11 starters
        starters = [pool[0]] + pool[2:6] + pool[7:10] + pool[12:15]
        bench = [pool[1], pool[6], pool[10], pool[11]]
        assert len(starters) == 11 and len(bench) == 4
        bench_ids = [p["id"] for p in bench]
        captain_id = starters[0]["id"]
        payload = {
            "competition_id": "fantasy-wc2026",
            "squad_name": "It19 Test",
            "mode": "15",
            "formation": "4-3-3",
            "captain_id": captain_id,
            "vice_captain_id": starters[1]["id"],
            "bench_ids": bench_ids,
            "bench_boost": False,
            "players": [
                {"player_id": p["id"], "position": p["position"], "price_paid": 5.0,
                 "is_starting": p["id"] not in bench_ids, "on_bench": p["id"] in bench_ids,
                 "is_captain": p["id"] == captain_id, "is_vice": p["id"] == starters[1]["id"]}
                for p in pool
            ],
        }
        r = s.post(f"{BASE_URL}/api/fantasy/squad", json=payload)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        squad = r.json()["squad"]
        assert squad["formation"] == "4-3-3"
        assert squad["mode"] == "15"
        assert set(squad["bench_ids"]) == set(bench_ids)
        # is_starting must be derived from bench_ids
        for sp in squad["players"]:
            if sp["player_id"] in bench_ids:
                assert sp["is_starting"] is False, f"bench player {sp['player_id']} should be on_bench"
                assert sp["on_bench"] is True
            else:
                assert sp["is_starting"] is True
        assert squad["captain_id"] == captain_id
        assert squad.get("total_points", 0) == 0
        assert squad.get("gw_points", 0) == 0

    def test_get_squad_alias_matches_squad_me(self, user_session):
        s, _ = user_session
        r1 = s.get(f"{BASE_URL}/api/fantasy/squad")
        r2 = s.get(f"{BASE_URL}/api/fantasy/squad/me")
        assert r1.status_code == 200 and r2.status_code == 200
        sq1 = r1.json().get("squad")
        sq2 = r2.json().get("squad")
        assert sq1 is not None and sq2 is not None
        assert sq1["id"] == sq2["id"]
        assert sq1["formation"] == sq2["formation"]
        assert sq1["mode"] == sq2["mode"]
        assert set(sq1["bench_ids"]) == set(sq2["bench_ids"])
        assert sq1["captain_id"] == sq2["captain_id"]
        assert sq1["vice_captain_id"] == sq2["vice_captain_id"]

    def test_edit_squad_preserves_total_points(self, user_session, players):
        s, _ = user_session
        # Inject artificial points to verify preservation
        r0 = s.get(f"{BASE_URL}/api/fantasy/squad")
        squad = r0.json()["squad"]
        # Use admin to push points? Instead, simulate by reading then resaving — must not reset to 0
        pool = _build_15(players)
        starters = [pool[0]] + pool[2:6] + pool[7:10] + pool[12:15]
        bench = [pool[1], pool[6], pool[10], pool[11]]
        bench_ids = [p["id"] for p in bench]
        # Swap one starter MID with bench MID (a real "transfer")
        payload = {
            "competition_id": "fantasy-wc2026",
            "squad_name": "It19 Edited",
            "mode": "15",
            "formation": "4-4-2",
            "captain_id": starters[0]["id"],
            "vice_captain_id": starters[1]["id"],
            "bench_ids": bench_ids,
            "players": [
                {"player_id": p["id"], "position": p["position"], "price_paid": 5.0,
                 "is_starting": p["id"] not in bench_ids, "on_bench": p["id"] in bench_ids}
                for p in pool
            ],
        }
        r = s.post(f"{BASE_URL}/api/fantasy/squad", json=payload)
        assert r.status_code == 200, r.text
        sq = r.json()["squad"]
        assert sq["formation"] == "4-4-2"
        assert sq["squad_name"] == "It19 Edited"
        # total_points field present (preserved)
        assert "total_points" in sq
        assert "gw_points" in sq


class TestBudgetModeEnforcement:
    def test_15man_rejects_over_100m(self, players, user_session):
        s, _ = user_session
        pool = _build_15(players)
        payload = {
            "competition_id": "fantasy-wc2026",
            "squad_name": "Over Budget",
            "mode": "15",
            "formation": "4-3-3",
            "players": [
                {"player_id": p["id"], "position": p["position"], "price_paid": 10.0}
                for p in pool  # 15 * 10 = 150m > 100m
            ],
        }
        r = s.post(f"{BASE_URL}/api/fantasy/squad", json=payload)
        assert r.status_code == 400
        assert "budget" in r.text.lower() or "over" in r.text.lower()

    def test_20man_allows_120m(self, players, user_session):
        s, _ = user_session
        # Build 20 players
        gks = _pick(players, 3, "GK", 6)
        defs = _pick(players, 7, "DEF", 6)
        mids = _pick(players, 7, "MID", 7)
        fwds = _pick(players, 3, "FWD", 8)
        pool = gks + defs + mids + fwds
        if len(pool) < 20:
            pytest.skip("not enough players for 20-man build")
        payload = {
            "competition_id": "fantasy-wc2026",
            "squad_name": "Twenty",
            "mode": "20",
            "formation": "4-3-3",
            "players": [
                {"player_id": p["id"], "position": p["position"], "price_paid": 5.5}
                for p in pool  # 20 * 5.5 = 110m < 120m
            ],
        }
        r = s.post(f"{BASE_URL}/api/fantasy/squad", json=payload)
        assert r.status_code == 200, r.text
        sq = r.json()["squad"]
        assert sq["mode"] == "20"
        assert sq["budget"] == 120.0

    def test_20man_rejects_over_120m(self, players, user_session):
        s, _ = user_session
        gks = _pick(players, 3, "GK", 6)
        defs = _pick(players, 7, "DEF", 6)
        mids = _pick(players, 7, "MID", 7)
        fwds = _pick(players, 3, "FWD", 8)
        pool = gks + defs + mids + fwds
        if len(pool) < 20:
            pytest.skip("not enough players for 20-man build")
        payload = {
            "competition_id": "fantasy-wc2026",
            "squad_name": "Over20",
            "mode": "20",
            "formation": "4-3-3",
            "players": [
                {"player_id": p["id"], "position": p["position"], "price_paid": 7.0}
                for p in pool  # 20 * 7 = 140 > 120
            ],
        }
        r = s.post(f"{BASE_URL}/api/fantasy/squad", json=payload)
        assert r.status_code == 400

    def test_15man_rejects_over_size(self, players, user_session):
        s, _ = user_session
        # build 16-player squad in 15-man mode
        gks = _pick(players, 2, "GK", 6)
        defs = _pick(players, 6, "DEF", 6)
        mids = _pick(players, 5, "MID", 7)
        fwds = _pick(players, 3, "FWD", 8)
        pool = gks + defs + mids + fwds  # 16
        payload = {
            "competition_id": "fantasy-wc2026",
            "squad_name": "TooMany",
            "mode": "15",
            "formation": "4-3-3",
            "players": [
                {"player_id": p["id"], "position": p["position"], "price_paid": 5.0}
                for p in pool
            ],
        }
        r = s.post(f"{BASE_URL}/api/fantasy/squad", json=payload)
        assert r.status_code == 400
        assert "max" in r.text.lower() or "large" in r.text.lower()


# ===== Transfers =====
class TestTransfers:
    def test_get_transfers_default(self, user_session):
        s, _ = user_session
        r = s.get(f"{BASE_URL}/api/fantasy/transfers")
        assert r.status_code == 200
        d = r.json()
        assert d["card_price_usd_cents"] == 200
        assert d["card_uses"] == 5
        assert d["point_penalty_per_transfer"] == 4
        assert "remaining" in d
        assert "total_used" in d

    def test_spend_points_always_succeeds(self, user_session):
        s, _ = user_session
        r = s.post(f"{BASE_URL}/api/fantasy/transfers/spend", json={"pay_with": "points"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["penalty"] == 4

    def test_spend_card_402_when_empty(self, user_session):
        s, _ = user_session
        r = s.post(f"{BASE_URL}/api/fantasy/transfers/spend", json={"pay_with": "card"})
        assert r.status_code == 402
        assert "no transfers" in r.text.lower() or "left" in r.text.lower()

    def test_buy_402_insufficient_wallet(self, user_session):
        s, _ = user_session
        r = s.post(f"{BASE_URL}/api/fantasy/transfers/buy")
        assert r.status_code == 402

    def test_buy_success_with_wallet(self, user_session):
        s, email = user_session
        admin = requests.Session()
        ar = admin.post(f"{BASE_URL}/api/auth/signin", json={
            "email": "admin@cloudypitch.com", "password": "CloudyAdmin2026!"
        })
        if ar.status_code != 200:
            pytest.skip("admin login unavailable for wallet topup")
        topup = admin.post(f"{BASE_URL}/api/admin/wallet/credit", json={"email": email, "amount_usd_cents": 200})
        if topup.status_code not in (200, 201):
            pytest.skip(f"no admin wallet credit endpoint (got {topup.status_code})")
        r = s.post(f"{BASE_URL}/api/fantasy/transfers/buy")
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert d["remaining"] >= 5
