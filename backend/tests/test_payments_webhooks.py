"""Unit tests for PocketFi + Trybit webhook signature verification.

Run from /app/backend:
  python -m pytest tests/test_payments_webhooks.py -v
"""
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone, timedelta

import pytest

os.environ.setdefault("POCKETFI_SECRET_KEY", "test_secret_pocketfi_xxxxxxxx")
os.environ.setdefault("TRYBIT_SECRET_KEY", "test_secret_trybit_xxxxxxxx")

import jwt as pyjwt  # noqa: E402

from routes.pocketfi import _verify_pocketfi_signature  # noqa: E402


def test_pocketfi_signature_roundtrip():
    secret = "test_secret_pocketfi_xxxxxxxx"
    body = json.dumps({
        "order": {"amount": 5000.0, "settlement_amount": 4875.0, "fee": 125.0, "description": "Test deposit"},
        "transaction": {"reference": "pfi_ref_abc"},
    }).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha512).hexdigest()
    assert _verify_pocketfi_signature(secret, body, sig)
    # tampered body must fail
    assert not _verify_pocketfi_signature(secret, body + b" ", sig)
    # wrong sig must fail
    assert not _verify_pocketfi_signature(secret, body, sig[:-4] + "abcd")


def test_trybit_jwt_decode_roundtrip():
    secret = "test_secret_trybit_xxxxxxxx"
    payload = {
        "status": "paid",
        "uuid": "INV-FAKEUUID",
        "order_id": "user123:nonce456",
        "amount_usd": 25.0,
        "exp": (datetime.now(timezone.utc) + timedelta(minutes=10)).timestamp(),
    }
    token = pyjwt.encode(payload, secret, algorithm="HS256")
    decoded = pyjwt.decode(token, secret, algorithms=["HS256"])
    assert decoded["status"] == "paid"
    assert decoded["uuid"] == "INV-FAKEUUID"
    # wrong secret must raise
    with pytest.raises(pyjwt.InvalidSignatureError):
        pyjwt.decode(token, "wrong_secret_xxxxxxxx", algorithms=["HS256"])


def test_trybit_expired_jwt():
    secret = "test_secret_trybit_xxxxxxxx"
    payload = {
        "status": "paid",
        "uuid": "INV-X",
        "exp": (datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp(),
    }
    token = pyjwt.encode(payload, secret, algorithm="HS256")
    with pytest.raises(pyjwt.ExpiredSignatureError):
        pyjwt.decode(token, secret, algorithms=["HS256"])
