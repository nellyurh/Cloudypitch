"""Iteration 25 backend tests:
- POST /api/admin/wc/cards/seed-team-boosts (idempotent)
- GET  /api/admin/wc/cards/list (contains new boosts)
- POST /api/admin/wc/cards/grant
- POST /api/admin/wc/games/open-all (locks knockout stages)
- GET  /api/fantasy/leaderboard/round (valid & empty round)
"""

import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@cloudypitch.com"
ADMIN_PASS = "CloudyAdmin2026!"

LOCKED = {"r32", "r16", "qf", "sf", "finals"}


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/signin",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=30,
    )
    assert r.status_code == 200, f"admin signin failed: {r.status_code} {r.text}"
    me = s.get(f"{BASE_URL}/api/auth/me", timeout=30)
    assert me.status_code == 200, me.text
    me_payload = me.json()
    user = me_payload.get("user", me_payload)
    assert user.get("role") == "admin", f"not admin: {me.text}"
    return s


# ── Card Seed ────────────────────────────────────────────────────
class TestSeedTeamBoosts:
    def test_seed_endpoint_returns_two_cards(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/admin/wc/cards/seed-team-boosts", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert data["cards_upserted"] == 2

    def test_seed_is_idempotent(self, admin_session):
        # second call must not error
        r = admin_session.post(f"{BASE_URL}/api/admin/wc/cards/seed-team-boosts", timeout=30)
        assert r.status_code == 200
        assert r.json()["cards_upserted"] == 2


# ── Card List ────────────────────────────────────────────────────
class TestCardsList:
    def test_list_contains_team_boosts(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/wc/cards/list", timeout=30)
        assert r.status_code == 200, r.text
        cards = r.json()["cards"]
        ids = {c["id"] for c in cards}
        assert "card-team-boost-2x" in ids
        assert "card-team-boost-3x" in ids
        by_id = {c["id"]: c for c in cards}
        c2 = by_id["card-team-boost-2x"]
        c3 = by_id["card-team-boost-3x"]
        assert c2["price_coins"] == 10000
        assert c2["effect_type"] == "team_boost_2x"
        assert c3["price_coins"] == 30000
        assert c3["effect_type"] == "team_boost_3x"


# ── Grant ────────────────────────────────────────────────────────
class TestGrantCards:
    def test_grant_team_boost_to_admin(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/admin/wc/cards/grant",
            json={
                "user_emails": [ADMIN_EMAIL],
                "card_id": "card-team-boost-2x",
                "quantity": 1,
                "note": "iteration25 test grant",
            },
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        granted = data["granted"]
        assert len(granted) == 1
        assert granted[0]["email"] == ADMIN_EMAIL
        assert granted[0]["qty"] == 1
        assert data["card"]["id"] == "card-team-boost-2x"

    def test_grant_unknown_card_returns_404(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/admin/wc/cards/grant",
            json={
                "user_emails": [ADMIN_EMAIL],
                "card_id": "card-does-not-exist",
                "quantity": 1,
            },
            timeout=30,
        )
        assert r.status_code == 404

    def test_grant_unknown_user_returns_404(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/admin/wc/cards/grant",
            json={
                "user_emails": ["nobody-iter25@example.com"],
                "card_id": "card-team-boost-2x",
                "quantity": 1,
            },
            timeout=30,
        )
        assert r.status_code == 404


# ── Open-all games ───────────────────────────────────────────────
class TestOpenAllGames:
    def test_open_all_response_shape(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/admin/wc/games/open-all", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in (
            "ok",
            "flipped",
            "skipped_started",
            "open_before",
            "open_after",
            "locked_stages",
        ):
            assert k in data, f"missing key {k} in {data}"
        assert data["ok"] is True
        assert set(data["locked_stages"]) == LOCKED
        assert isinstance(data["flipped"], int)
        assert isinstance(data["open_before"], int)
        assert isinstance(data["open_after"], int)

    def test_no_locked_stage_game_flipped_by_open_all(self, admin_session):
        """Snapshot locked-stage open counts BEFORE & AFTER open-all and
        ensure they are equal — the endpoint must not touch knockout stages.
        (A pre-existing open game in a locked stage from a manual override
        is acceptable; what matters is open-all didn't flip it.)"""
        # snapshot before
        before = {}
        for stage in LOCKED:
            r = admin_session.get(
                f"{BASE_URL}/api/admin/wc/games?stage={stage}&status=open&limit=500",
                timeout=30,
            )
            assert r.status_code == 200
            before[stage] = len(r.json().get("games", []))

        # fire open-all
        r = admin_session.post(f"{BASE_URL}/api/admin/wc/games/open-all", timeout=60)
        assert r.status_code == 200, r.text

        # snapshot after
        for stage in LOCKED:
            r = admin_session.get(
                f"{BASE_URL}/api/admin/wc/games?stage={stage}&status=open&limit=500",
                timeout=30,
            )
            assert r.status_code == 200
            after = len(r.json().get("games", []))
            assert after == before[stage], (
                f"Stage {stage} open count changed: before={before[stage]} "
                f"after={after} — open-all leaked into a locked stage"
            )


# ── Round Leaderboard ────────────────────────────────────────────
class TestRoundLeaderboard:
    def test_valid_round_returns_leaderboard(self, admin_session):
        r = admin_session.get(
            f"{BASE_URL}/api/fantasy/leaderboard/round",
            params={"round": "Matchday 1", "limit": 5},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "leaderboard" in data
        assert data["round"] == "Matchday 1"
        lb = data["leaderboard"]
        assert isinstance(lb, list)
        assert len(lb) <= 5
        # If matches exist, leaderboard may be populated
        for i, row in enumerate(lb, 1):
            for k in (
                "rank",
                "user_id",
                "squad_id",
                "squad_name",
                "display_name",
                "country_code",
                "round_points",
            ):
                assert k in row, f"missing field {k} in row {row}"
            assert row["rank"] == i
        # rank ordering: round_points descending
        pts = [r["round_points"] for r in lb]
        assert pts == sorted(pts, reverse=True)

    def test_invalid_round_returns_empty(self, admin_session):
        r = admin_session.get(
            f"{BASE_URL}/api/fantasy/leaderboard/round",
            params={"round": "NotARealRound_xyz", "limit": 5},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["leaderboard"] == []
        # Endpoint may or may not include matches_in_round=0 in empty case.
        # Just ensure no crash and empty list returned.

    def test_empty_round_param_does_not_crash(self, admin_session):
        # Empty string round
        r = admin_session.get(
            f"{BASE_URL}/api/fantasy/leaderboard/round",
            params={"round": "", "limit": 5},
            timeout=30,
        )
        # Should either 200 with empty or 422 validation. Either way no 500.
        assert r.status_code in (200, 422), r.text
        if r.status_code == 200:
            assert r.json().get("leaderboard") == []
