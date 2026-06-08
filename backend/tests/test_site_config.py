"""Site config endpoint tests — enabled sports + admin popup notice."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read frontend .env
    try:
        from pathlib import Path
        for ln in Path("/app/frontend/.env").read_text().splitlines():
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")
                break
    except Exception:
        pass

ADMIN_EMAIL = "admin@cloudypitch.com"
ADMIN_PW = "CloudyAdmin2026!"
DEFAULT_SPORTS = {
    "football", "basketball", "tennis", "baseball", "hockey", "cricket",
    "rugby", "nba", "volleyball", "handball", "mma", "f1", "afl", "golf",
}


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/signin", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    if r.status_code != 200:
        pytest.skip(f"Admin signin failed: {r.status_code} {r.text}")
    yield s
    # Cleanup — reset to all-14 enabled, popup disabled
    s.post(
        f"{BASE_URL}/api/admin/site-config",
        json={
            "enabled_sports": list(DEFAULT_SPORTS),
            "show_wc_tab": True,
            "popup_notice": {"enabled": False},
        },
    )


@pytest.fixture
def anon_session():
    return requests.Session()


# ---- Public GET /api/site-config ----

def test_get_site_config_public_no_auth(anon_session):
    r = anon_session.get(f"{BASE_URL}/api/site-config")
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, dict)
    assert "enabled_sports" in data
    assert "show_wc_tab" in data
    assert "popup_notice" in data
    assert isinstance(data["enabled_sports"], list)
    assert len(data["enabled_sports"]) >= 1
    # All slugs must be from whitelist
    for slug in data["enabled_sports"]:
        assert slug in DEFAULT_SPORTS, f"unknown slug {slug}"


# ---- POST /api/admin/site-config auth ----

def test_post_site_config_no_auth_returns_401_or_403(anon_session):
    r = anon_session.post(
        f"{BASE_URL}/api/admin/site-config",
        json={"enabled_sports": ["football"]},
    )
    assert r.status_code in (401, 403), r.status_code


def test_post_site_config_non_admin_returns_403():
    # Create a fresh non-admin user
    import uuid
    s = requests.Session()
    email = f"TEST_user_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(
        f"{BASE_URL}/api/auth/signup",
        json={"email": email, "password": "TestPass123!", "display_name": "T"},
    )
    if r.status_code not in (200, 201):
        pytest.skip(f"signup failed: {r.status_code} {r.text}")
    r = s.post(
        f"{BASE_URL}/api/admin/site-config",
        json={"enabled_sports": ["football"]},
    )
    assert r.status_code == 403, f"expected 403, got {r.status_code}"


# ---- Admin happy path: subset, then read-back ----

def test_admin_subset_sports_persists(admin_session):
    subset = ["football", "basketball", "tennis"]
    r = admin_session.post(
        f"{BASE_URL}/api/admin/site-config",
        json={"enabled_sports": subset, "show_wc_tab": True},
    )
    assert r.status_code == 200, r.text

    # Read back via public endpoint
    r2 = requests.get(f"{BASE_URL}/api/site-config")
    assert r2.status_code == 200
    data = r2.json()
    assert sorted(data["enabled_sports"]) == sorted(subset)
    assert data["show_wc_tab"] is True


def test_admin_unknown_slugs_dropped(admin_session):
    r = admin_session.post(
        f"{BASE_URL}/api/admin/site-config",
        json={"enabled_sports": ["football", "fake-sport", "rocket-league", "tennis"]},
    )
    assert r.status_code == 200
    r2 = requests.get(f"{BASE_URL}/api/site-config")
    data = r2.json()
    assert "fake-sport" not in data["enabled_sports"]
    assert "rocket-league" not in data["enabled_sports"]
    assert "football" in data["enabled_sports"]
    assert "tennis" in data["enabled_sports"]


def test_admin_show_wc_tab_toggle(admin_session):
    r = admin_session.post(
        f"{BASE_URL}/api/admin/site-config",
        json={"show_wc_tab": False},
    )
    assert r.status_code == 200
    data = requests.get(f"{BASE_URL}/api/site-config").json()
    assert data["show_wc_tab"] is False
    # Reset
    admin_session.post(f"{BASE_URL}/api/admin/site-config", json={"show_wc_tab": True})


# ---- Popup notice + version bump ----

def test_admin_popup_notice_bump_version(admin_session):
    # First enable a popup to read its current version (public GET strips when disabled)
    admin_session.post(f"{BASE_URL}/api/admin/site-config", json={
        "popup_notice": {"enabled": True, "title": "baseline", "bump_version": False}
    })
    r0 = requests.get(f"{BASE_URL}/api/site-config").json()
    old_ver = int((r0.get("popup_notice") or {}).get("version") or 0)

    payload = {
        "popup_notice": {
            "enabled": True,
            "title": "TEST Popup",
            "body": "Test body",
            "image_url": "",
            "cta_text": "OK",
            "cta_link": "/",
            "bump_version": True,
        }
    }
    r = admin_session.post(f"{BASE_URL}/api/admin/site-config", json=payload)
    assert r.status_code == 200, r.text

    r2 = requests.get(f"{BASE_URL}/api/site-config").json()
    p = r2["popup_notice"]
    assert p.get("enabled") is True
    assert p.get("title") == "TEST Popup"
    new_ver = int(p.get("version") or 0)
    assert new_ver == old_ver + 1, f"expected version {old_ver+1}, got {new_ver}"

    # Disable popup → public response should show enabled=False and strip details
    admin_session.post(
        f"{BASE_URL}/api/admin/site-config",
        json={"popup_notice": {"enabled": False}},
    )
    r3 = requests.get(f"{BASE_URL}/api/site-config").json()
    assert r3["popup_notice"].get("enabled") is False
