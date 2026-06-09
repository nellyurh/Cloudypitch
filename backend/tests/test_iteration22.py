"""Iteration 22 — Ads + WC News + WC enrichment backend tests.

Coverage:
  * /api/ads/config (public)
  * /api/ads/serve/{placement_key} (direct → adsense fallback, premium suppression)
  * /api/ads/placements CRUD (admin)
  * /api/ads/impression and /api/ads/click counters
  * /api/ads/adsense-slots CRUD (admin)
  * /api/worldcup enrichment (.group / .round / .matchday / .news)
  * /api/worldcup/news CRUD (admin) + public GET
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fantasy-wc.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@cloudypitch.com"
ADMIN_PASS = "CloudyAdmin2026!"

PUBLISHER_ID = "ca-pub-7276060210938369"

EXPECTED_PLACEMENTS = {
    "home_bottom_banner", "match_list_inline", "wc_hub_sponsor",
    "pool_sponsor", "interstitial_nav", "rewarded_video",
    "header_banner", "sidebar_right", "leaderboard_above", "mobile_bottom",
    "wc_hub_top", "predictions_inline", "fantasy_sidebar",
}


@pytest.fixture(scope="module")
def anon():
    s = requests.Session()
    return s


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/signin", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return s


# ──────────────────────────── /api/ads/config ────────────────────────────

class TestAdsConfig:
    def test_config_anonymous(self, anon):
        r = anon.get(f"{API}/ads/config", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["adsense_enabled"] is True
        assert data["adsense_publisher_id"] == PUBLISHER_ID
        assert data["premium"] is False
        placements = set(data["valid_placements"])
        assert EXPECTED_PLACEMENTS.issubset(placements), f"Missing: {EXPECTED_PLACEMENTS - placements}"


# ──────────────────────────── /api/ads/serve/* ────────────────────────────

class TestServeAd:
    def test_serve_header_banner_adsense_fallback(self, anon, admin):
        # Ensure there's no active direct sponsor for header_banner (so fallback is adsense)
        # Clean existing direct sponsors for header_banner
        list_r = admin.get(f"{API}/ads/placements?placement_key=header_banner", timeout=10)
        if list_r.status_code == 200:
            for p in list_r.json().get("placements", []):
                if p.get("network") == "direct":
                    admin.delete(f"{API}/ads/placements/{p['id']}", timeout=10)
        r = anon.get(f"{API}/ads/serve/header_banner", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["premium"] is False
        assert data["source"] == "adsense"
        ad = data["ad"]
        assert ad["network"] == "adsense"
        assert ad["placement_key"] == "header_banner"
        assert ad["publisher_id"] == PUBLISHER_ID
        assert "ad_slot" in ad  # may be empty string for auto-ads

    def test_serve_invalid_placement_400(self, anon):
        r = anon.get(f"{API}/ads/serve/not_a_real_placement", timeout=10)
        assert r.status_code == 400


# ──────────────────────────── /api/ads/placements (admin CRUD) ────────────────────────────

class TestPlacementsCRUD:
    created_id = None

    def test_create_direct_sponsor(self, admin):
        payload = {
            "placement_key": "header_banner",
            "network": "direct",
            "sponsor_name": "TEST_Acme",
            "sponsor_image_url": "https://example.com/x.jpg",
            "target_url": "https://acme.com",
            "weight": 3,
            "is_active": True,
        }
        r = admin.post(f"{API}/ads/placements", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        pl = r.json()["placement"]
        assert pl["sponsor_name"] == "TEST_Acme"
        assert pl["weight"] == 3
        assert pl["network"] == "direct"
        assert pl["impressions"] == 0
        assert pl["clicks"] == 0
        TestPlacementsCRUD.created_id = pl["id"]

    def test_serve_returns_direct_after_create(self, anon, admin):
        # We just created a direct active sponsor for header_banner.
        r = anon.get(f"{API}/ads/serve/header_banner", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "direct", f"Expected direct, got {data['source']}"
        ad = data["ad"]
        assert ad["sponsor_name"] == "TEST_Acme"
        assert ad["target_url"] == "https://acme.com"
        # Impressions auto-incremented by serve endpoint
        time.sleep(0.3)
        lst = admin.get(f"{API}/ads/placements?placement_key=header_banner", timeout=10).json()
        match = next((p for p in lst["placements"] if p["id"] == TestPlacementsCRUD.created_id), None)
        assert match is not None
        assert match["impressions"] >= 1, f"Impressions not incremented: {match}"

    def test_impression_and_click_counters(self, anon, admin):
        pid = TestPlacementsCRUD.created_id
        assert pid, "Need created placement"
        before = admin.get(f"{API}/ads/placements?placement_key=header_banner", timeout=10).json()
        before_p = next(p for p in before["placements"] if p["id"] == pid)
        imp0, clk0 = before_p["impressions"], before_p["clicks"]

        r1 = anon.post(f"{API}/ads/impression/{pid}", timeout=10)
        r2 = anon.post(f"{API}/ads/click/{pid}", timeout=10)
        assert r1.status_code == 200
        assert r2.status_code == 200
        time.sleep(0.3)
        after = admin.get(f"{API}/ads/placements?placement_key=header_banner", timeout=10).json()
        after_p = next(p for p in after["placements"] if p["id"] == pid)
        assert after_p["impressions"] >= imp0 + 1
        assert after_p["clicks"] == clk0 + 1

    def test_delete_placement_cleanup(self, admin):
        pid = TestPlacementsCRUD.created_id
        if pid:
            r = admin.delete(f"{API}/ads/placements/{pid}", timeout=10)
            assert r.status_code == 200


# ──────────────────────────── /api/ads/adsense-slots ────────────────────────────

class TestAdsenseSlots:
    def test_upsert_and_list_slot(self, admin):
        r = admin.post(f"{API}/ads/adsense-slots",
                       json={"placement_key": "sidebar_right", "ad_slot": "1234567890"}, timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["ad_slot"] == "1234567890"

        r2 = admin.get(f"{API}/ads/adsense-slots", timeout=10)
        assert r2.status_code == 200
        slots = r2.json()["slots"]
        match = next((s for s in slots if s["placement_key"] == "sidebar_right"), None)
        assert match is not None
        assert match["ad_slot"] == "1234567890"
        assert r2.json()["publisher_id"] == PUBLISHER_ID

    def test_serve_sidebar_right_uses_slot(self, anon):
        r = anon.get(f"{API}/ads/serve/sidebar_right", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "adsense"
        assert data["ad"]["ad_slot"] == "1234567890"
        assert data["ad"]["publisher_id"] == PUBLISHER_ID

    def test_delete_slot_cleanup(self, admin):
        r = admin.delete(f"{API}/ads/adsense-slots/sidebar_right", timeout=10)
        assert r.status_code == 200

    def test_invalid_placement_rejected(self, admin):
        r = admin.post(f"{API}/ads/adsense-slots",
                       json={"placement_key": "nonsense_key", "ad_slot": "abcdef"}, timeout=10)
        assert r.status_code == 400


# ──────────────────────────── /api/worldcup enrichment ────────────────────────────

class TestWorldCupHub:
    def test_hub_returns_enriched_matches(self):
        r = requests.get(f"{API}/worldcup", timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert "matches" in data
        assert "news" in data
        assert isinstance(data["news"], list)
        matches = data["matches"]
        assert len(matches) > 0, "No WC2026 matches returned"
        # All matches must have round + matchday
        for m in matches[:10]:
            assert "round" in m
            assert "matchday" in m
            assert "group" in m  # may be None for knockout placeholders but key must exist

        # Verify at least one match has a group letter A–L
        with_group = [m for m in matches if (m.get("group") or "") in "ABCDEFGHIJKL" and m.get("group")]
        assert len(with_group) > 0, "No match has a derived group (A–L)"

        # Verify round labels are correct on early matches (Matchday 1)
        early = [m for m in matches if (m.get("scheduled_at") or "")[:10] <= "2026-06-17"]
        if early:
            assert all("Matchday 1" in m["round"] for m in early), \
                f"Early matches mislabeled: {[m['round'] for m in early[:3]]}"


# ──────────────────────────── /api/worldcup/news CRUD ────────────────────────────

class TestWcNews:
    created_id = None

    def test_admin_create_news(self, admin):
        payload = {
            "title": "TEST_News headline",
            "summary": "Iteration 22 test summary",
            "image_url": "https://example.com/news.jpg",
            "source_name": "Goal.com",
            "source_url": "https://goal.com/x",
            "published": True,
        }
        r = admin.post(f"{API}/worldcup/news", json=payload, timeout=10)
        assert r.status_code == 200, r.text
        item = r.json()["item"]
        assert item["title"] == "TEST_News headline"
        assert item["published"] is True
        assert "id" in item
        TestWcNews.created_id = item["id"]

    def test_public_get_returns_published(self):
        r = requests.get(f"{API}/worldcup/news", timeout=10)
        assert r.status_code == 200
        items = r.json()["news"]
        match = next((i for i in items if i["id"] == TestWcNews.created_id), None)
        assert match is not None, "Newly created news not visible publicly"
        assert match["source_name"] == "Goal.com"

    def test_hub_includes_news(self):
        r = requests.get(f"{API}/worldcup", timeout=20)
        items = r.json()["news"]
        ids = {i["id"] for i in items}
        assert TestWcNews.created_id in ids, "Created news not in /api/worldcup .news array"

    def test_admin_patch_news(self, admin):
        nid = TestWcNews.created_id
        payload = {
            "title": "TEST_News headline (edited)",
            "summary": "edited",
            "image_url": "",
            "source_name": "Goal.com",
            "source_url": "https://goal.com/x",
            "published": True,
        }
        r = admin.patch(f"{API}/worldcup/news/{nid}", json=payload, timeout=10)
        assert r.status_code == 200
        # verify
        pub = requests.get(f"{API}/worldcup/news", timeout=10).json()["news"]
        m = next((i for i in pub if i["id"] == nid), None)
        assert m is not None and m["title"] == "TEST_News headline (edited)"

    def test_admin_delete_news(self, admin):
        nid = TestWcNews.created_id
        r = admin.delete(f"{API}/worldcup/news/{nid}", timeout=10)
        assert r.status_code == 200
        assert r.json().get("deleted", 0) == 1
        # Confirm gone
        pub = requests.get(f"{API}/worldcup/news", timeout=10).json()["news"]
        assert all(i["id"] != nid for i in pub)

    def test_news_requires_admin(self, anon):
        r = anon.post(f"{API}/worldcup/news", json={"title": "nope", "summary": ""}, timeout=10)
        assert r.status_code in (401, 403)


# ──────────────────────────── /ads.txt ────────────────────────────

class TestAdsTxt:
    def test_ads_txt_served(self):
        # ads.txt is served from frontend root
        r = requests.get(f"{BASE_URL}/ads.txt", timeout=10)
        assert r.status_code == 200
        assert "pub-7276060210938369" in r.text
        assert "google.com" in r.text
        assert "DIRECT" in r.text
