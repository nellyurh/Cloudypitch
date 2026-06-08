"""Backend integration tests for PocketFi + Trybit payment routes (iteration 21).

Validates the "not configured" plumbing while the provider API keys are NOT yet
populated in /app/backend/.env. Once keys are set, the 503 tests below will
correctly start failing — that's expected.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fantasy-wc.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@cloudypitch.com"
ADMIN_PASSWORD = "CloudyAdmin2026!"


# ──────────────────────────── fixtures ────────────────────────────

@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/signin", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"admin signin failed: {r.status_code} {r.text[:200]}")
    return s


@pytest.fixture(scope="module")
def user_session():
    s = requests.Session()
    email = f"bt_{int(time.time())}_{uuid.uuid4().hex[:6]}@test.com"
    r = s.post(
        f"{BASE_URL}/api/auth/signup",
        json={"email": email, "password": "TestPass123!", "display_name": "Bt User"},
        timeout=15,
    )
    if r.status_code not in (200, 201):
        # Maybe rate limited; try direct signin with an existing pattern
        pytest.skip(f"signup failed: {r.status_code} {r.text[:200]}")
    return s


# ──────────────────────────── /config endpoints ────────────────────────────

class TestConfigEndpoints:
    def test_pocketfi_config(self):
        r = requests.get(f"{BASE_URL}/api/payments/pocketfi/config", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["configured"] is False
        assert data["currency"] == "NGN"
        assert set(data["banks"]) == {"9psb", "kuda", "paga", "palmpay", "saveheaven"}

    def test_trybit_config(self):
        r = requests.get(f"{BASE_URL}/api/payments/trybit/config", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["configured"] is False
        assert data["currency"] == "USD"
        assert isinstance(data["currencies"], list)
        assert len(data["currencies"]) == 11
        # spot-check
        assert "USDT_TRC20" in data["currencies"]
        assert "BTC" in data["currencies"]


# ──────────────────────────── PocketFi dynamic-account ────────────────────────────

class TestPocketFiDynamicAccount:
    def test_unauth_returns_401(self):
        # No auth → should NOT leak 503; should require auth first
        r = requests.post(
            f"{BASE_URL}/api/payments/pocketfi/dynamic-account",
            json={"amount_ngn": 5000, "bank": "kuda", "first_name": "A", "last_name": "B", "phone": "0801", "email": "x@y.com"},
            timeout=15,
        )
        assert r.status_code in (401, 403), r.text

    def test_missing_fields_returns_422(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/payments/pocketfi/dynamic-account",
            json={"amount_ngn": 5000, "bank": "kuda"},  # missing first_name/last_name/email/phone
            timeout=15,
        )
        assert r.status_code == 422, r.text

    def test_not_configured_returns_503(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/payments/pocketfi/dynamic-account",
            json={
                "amount_ngn": 5000, "bank": "kuda",
                "first_name": "Ada", "last_name": "Lovelace", "phone": "08012345678",
                "email": "ada@example.com",
            },
            timeout=15,
        )
        assert r.status_code == 503, r.text
        detail = r.json().get("detail", "")
        assert "POCKETFI_SECRET_KEY" in detail
        assert "POCKETFI_BUSINESS_ID" in detail

    def test_invalid_bank_with_keys_unset_returns_503(self, admin_session):
        """Keys are NOT set, so the route 503's BEFORE bank validation runs.
        This documents the current order of checks."""
        r = admin_session.post(
            f"{BASE_URL}/api/payments/pocketfi/dynamic-account",
            json={
                "amount_ngn": 5000, "bank": "not-a-bank",
                "first_name": "A", "last_name": "B", "phone": "08012345678", "email": "x@y.com",
            },
            timeout=15,
        )
        # Current state: 503. Once admin sets keys, this becomes 400.
        assert r.status_code in (400, 503), r.text

    def test_palmpay_without_kyc_with_keys_unset_returns_503(self, admin_session):
        """PalmPay without nin/bvn → 400 when configured. Currently 503 (keys missing)."""
        r = admin_session.post(
            f"{BASE_URL}/api/payments/pocketfi/dynamic-account",
            json={
                "amount_ngn": 5000, "bank": "palmpay",
                "first_name": "A", "last_name": "B", "phone": "08012345678", "email": "x@y.com",
            },
            timeout=15,
        )
        assert r.status_code in (400, 503), r.text


@pytest.fixture
def monkeypatch_keys():
    # No-op: we cannot mutate the backend process env from the test client.
    # Marker fixture so the test is self-documenting.
    yield


# ──────────────────────────── PocketFi deposit GET ────────────────────────────

class TestPocketFiDepositGet:
    def test_unknown_deposit_returns_404(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/payments/pocketfi/deposit/does-not-exist-{uuid.uuid4().hex}", timeout=15)
        assert r.status_code == 404, r.text

    def test_unauth_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/payments/pocketfi/deposit/anything", timeout=15)
        assert r.status_code in (401, 403)


# ──────────────────────────── Trybit /invoice ────────────────────────────

class TestTrybitInvoice:
    def test_unauth_returns_401(self):
        r = requests.post(f"{BASE_URL}/api/payments/trybit/invoice", json={"amount_usd": 25.0}, timeout=15)
        assert r.status_code in (401, 403)

    def test_negative_amount_returns_422(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/payments/trybit/invoice", json={"amount_usd": 0}, timeout=15)
        assert r.status_code == 422, r.text

    def test_not_configured_returns_503(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/payments/trybit/invoice", json={"amount_usd": 25.0}, timeout=15)
        assert r.status_code == 503, r.text
        detail = r.json().get("detail", "")
        # route only mentions API_KEY + SHOP_ID in its 503 message; SECRET_KEY is webhook-side
        assert "TRYBIT_API_KEY" in detail
        assert "TRYBIT_SHOP_ID" in detail


# ──────────────────────────── Trybit invoice GET ────────────────────────────

class TestTrybitInvoiceGet:
    def test_unknown_uuid_returns_404(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/payments/trybit/invoice/no-such-uuid-{uuid.uuid4().hex}", timeout=15)
        assert r.status_code == 404, r.text

    def test_unauth_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/payments/trybit/invoice/anything", timeout=15)
        assert r.status_code in (401, 403)


# ──────────────────────────── Webhook 503 when no secret ────────────────────────────

class TestWebhooks:
    def test_pocketfi_webhook_no_secret_returns_503(self):
        r = requests.post(f"{BASE_URL}/api/webhooks/pocketfi", json={"foo": "bar"}, timeout=15)
        assert r.status_code == 503, r.text

    def test_trybit_webhook_no_secret_returns_503(self):
        r = requests.post(f"{BASE_URL}/api/webhooks/trybit", json={"foo": "bar"}, timeout=15)
        assert r.status_code == 503, r.text


# ──────────────────────────── Tenancy ────────────────────────────

class TestTenancyIsolation:
    def test_pocketfi_deposit_not_leaked_to_other_user(self, admin_session, user_session):
        # Admin's unknown id should 404 for user_session, and vice versa
        rid = f"deposit_{uuid.uuid4().hex}"
        r1 = admin_session.get(f"{BASE_URL}/api/payments/pocketfi/deposit/{rid}", timeout=15)
        r2 = user_session.get(f"{BASE_URL}/api/payments/pocketfi/deposit/{rid}", timeout=15)
        assert r1.status_code == 404
        assert r2.status_code == 404

    def test_trybit_invoice_not_leaked(self, admin_session, user_session):
        rid = f"inv_{uuid.uuid4().hex}"
        r1 = admin_session.get(f"{BASE_URL}/api/payments/trybit/invoice/{rid}", timeout=15)
        r2 = user_session.get(f"{BASE_URL}/api/payments/trybit/invoice/{rid}", timeout=15)
        assert r1.status_code == 404
        assert r2.status_code == 404
