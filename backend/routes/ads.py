"""Ad placements + direct sponsorship slots.
Free-tier users see ads; premium subs (is_premium=True) get an empty list.
Networks: admob | adsense | meta | direct (in-house sponsorship)
Placement keys: home_bottom_banner | match_list_inline | wc_hub_sponsor |
  pool_sponsor | interstitial_nav | rewarded_video |
  header_banner | sidebar_right | leaderboard_above | mobile_bottom |
  wc_hub_top | predictions_inline | fantasy_sidebar
"""
from datetime import datetime, timezone
import os
import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import auth as a
from db import get_db
from models import new_id

router = APIRouter(prefix="/api/ads", tags=["ads"])


VALID_NETWORKS = {"admob", "adsense", "meta", "direct", "propellerads", "adsterra"}
VALID_PLACEMENTS = {
    # Legacy
    "home_bottom_banner", "match_list_inline", "wc_hub_sponsor",
    "pool_sponsor", "interstitial_nav", "rewarded_video",
    # Sofascore-style placements added 2026-02
    "header_banner",      # full-width banner just under sports nav
    "sidebar_right",      # right rail sticky slot (300x250 / 300x600)
    "leaderboard_above",  # above the WC leaderboard widget
    "mobile_bottom",      # sticky bottom bar on mobile
    "wc_hub_top",         # banner inside /worldcup above the trophy hero
    "predictions_inline", # between prediction rows
    "fantasy_sidebar",    # /fantasy + /build-team sidebar
}

ADSENSE_PUBLISHER_ID = os.environ.get("ADSENSE_PUBLISHER_ID", "")
ADSENSE_ENABLED = bool(ADSENSE_PUBLISHER_ID)


class PlacementIn(BaseModel):
    placement_key: str
    network: str = Field(pattern="^(admob|adsense|meta|direct)$")
    is_active: bool = True
    sponsor_name: str | None = None
    sponsor_image_url: str | None = None
    target_url: str | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    weight: int = 1  # rotation weight for direct sponsorships


@router.get("/config")
async def ads_config(user: dict = Depends(a.get_optional_user)):
    """Public ad config — FE injects the AdSense script using this.
    Premium users always get `{enabled: false}` so no ad code is ever loaded.

    🚫 Click-hijack hardening (2026-02-12): we permanently stop serving
    Monetag/PropellerAds `serving_head` (OnClick/Vignette/Interstitial) and
    `popunder` snippets. These scripts intercepted the first tap on any
    page and forced a redirect — destroying UX. Only inline banner ads
    (rendered by `<AdSlot>`) and the safe-to-render verification meta
    tags remain.
    """
    is_premium = bool(user and user.get("is_premium"))
    db = get_db()
    site_doc = await db.settings.find_one({"id": "propellerads_site"}, {"_id": 0})
    propellerads_verification_head = (site_doc or {}).get("verification_head") or ""
    push_zone = await db.propellerads_zones.find_one(
        {"format": "push", "is_active": True}, {"_id": 0, "zone_id": 1}
    )
    return {
        "adsense_enabled": ADSENSE_ENABLED and not is_premium,
        "adsense_publisher_id": ADSENSE_PUBLISHER_ID if (ADSENSE_ENABLED and not is_premium) else "",
        "propellerads_enabled": bool(push_zone and not is_premium),
        "propellerads_push_zone_id": (push_zone or {}).get("zone_id") if not is_premium else None,
        # Click-hijack vectors permanently disabled (see docstring).
        "propellerads_popunder_snippet": None,
        "propellerads_verification_head": propellerads_verification_head,
        "propellerads_serving_head": "",
        "premium": is_premium,
        "valid_placements": sorted(VALID_PLACEMENTS),
    }


@router.get("/serve/{placement_key}")
async def serve_ad(
    placement_key: str,
    user: dict = Depends(a.get_optional_user),
    viewport: str | None = None,
):
    """Return the best active ad for this placement.

    Priority:
      1) Premium → empty (no ad anywhere)
      2) An eligible `direct` sponsor (weighted random pick) → returned with `network: 'direct'`
      3) Else → tell FE to fall back to AdSense (`network: 'adsense'`, with the ad_slot)
    """
    if placement_key not in VALID_PLACEMENTS:
        raise HTTPException(status_code=400, detail=f"Unknown placement_key. Use one of: {sorted(VALID_PLACEMENTS)}")
    if user and user.get("is_premium"):
        return {"ad": None, "premium": True}

    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor = db.ad_placements.find(
        {"placement_key": placement_key, "is_active": True, "network": "direct"},
        {"_id": 0},
    )
    eligible: list[dict] = []
    async for p in cursor:
        if p.get("starts_at") and p["starts_at"] > now_iso:
            continue
        if p.get("ends_at") and p["ends_at"] < now_iso:
            continue
        eligible.append(p)

    if eligible:
        # Weighted random pick — weight defaults to 1.
        weights = [max(1, int(p.get("weight", 1))) for p in eligible]
        pick = random.choices(eligible, weights=weights, k=1)[0]
        # Fire-and-forget impression bump
        await db.ad_placements.update_one({"id": pick["id"]}, {"$inc": {"impressions": 1}})
        return {"ad": pick, "premium": False, "source": "direct"}

    # PropellerAds zones (admin-configured per placement). Wins over AdSense
    # because the user pasted these in for their preferred network. If both
    # PropellerAds and Adsterra are configured for the same placement, we
    # alternate roughly 50/50 so neither network dominates inventory.
    # `viewport=mobile|desktop` query lets the client say "skip ads not sized
    # for this device" — prevents a 728×90 from breaking a 360px phone.
    candidates: list[dict] = []
    pa_q: dict = {"placement_key": placement_key, "is_active": True,
                  # 🚫 Skip popunder/onclick/vignette formats — they hijack taps.
                  "format": {"$nin": ["popunder", "onclick", "vignette", "interstitial"]}}
    if viewport in ("mobile", "desktop"):
        pa_q["$or"] = [{"target_viewport": viewport}, {"target_viewport": "both"}, {"target_viewport": {"$exists": False}}]
    pa = await db.propellerads_zones.find_one(pa_q, {"_id": 0})
    if pa and (pa.get("snippet_html") or pa.get("zone_id")):
        candidates.append({"network": "propellerads", "zone": pa, "collection": "propellerads_zones"})
    at = await db.adsterra_zones.find_one(pa_q, {"_id": 0})
    if at and (at.get("snippet_html") or at.get("zone_id")):
        candidates.append({"network": "adsterra", "zone": at, "collection": "adsterra_zones"})
    if candidates:
        pick = random.choice(candidates)
        z = pick["zone"]
        await db[pick["collection"]].update_one(
            {"placement_key": placement_key},
            {"$inc": {"impressions": 1}},
        )
        return {
            "ad": {
                "network": pick["network"],
                "placement_key": placement_key,
                "zone_id": z.get("zone_id"),
                "snippet_html": z.get("snippet_html") or "",
                "width": z.get("width"),
                "height": z.get("height"),
                "format": z.get("format") or "banner",
                "target_viewport": z.get("target_viewport") or "both",
            },
            "premium": False,
            "source": pick["network"],
        }

    if ADSENSE_ENABLED:
        # Look up an admin-configured AdSense slot id for this placement (optional).
        slot = await db.adsense_slots.find_one({"placement_key": placement_key}, {"_id": 0})
        ad_slot = (slot or {}).get("ad_slot") or ""
        return {
            "ad": {
                "network": "adsense",
                "placement_key": placement_key,
                "ad_slot": ad_slot,
                "publisher_id": ADSENSE_PUBLISHER_ID,
            },
            "premium": False,
            "source": "adsense",
        }
    return {"ad": None, "premium": False, "source": "none"}


class AdSenseSlotIn(BaseModel):
    placement_key: str
    ad_slot: str = Field(min_length=4, max_length=32)


@router.post("/adsense-slots")
async def upsert_adsense_slot(body: AdSenseSlotIn, user: dict = Depends(a.require_admin)):
    if body.placement_key not in VALID_PLACEMENTS:
        raise HTTPException(status_code=400, detail=f"Unknown placement_key. Use one of: {sorted(VALID_PLACEMENTS)}")
    db = get_db()
    await db.adsense_slots.update_one(
        {"placement_key": body.placement_key},
        {"$set": {"ad_slot": body.ad_slot, "updated_at": datetime.now(timezone.utc).isoformat(),
                   "updated_by": user["id"]}},
        upsert=True,
    )
    return {"ok": True, "placement_key": body.placement_key, "ad_slot": body.ad_slot}


@router.get("/adsense-slots")
async def list_adsense_slots(user: dict = Depends(a.require_admin)):
    db = get_db()
    slots = await db.adsense_slots.find({}, {"_id": 0}).to_list(length=50)
    return {"slots": slots, "publisher_id": ADSENSE_PUBLISHER_ID}


@router.delete("/adsense-slots/{placement_key}")
async def delete_adsense_slot(placement_key: str, user: dict = Depends(a.require_admin)):
    db = get_db()
    res = await db.adsense_slots.delete_one({"placement_key": placement_key})
    return {"deleted": res.deleted_count}


# ─── PropellerAds zones ────────────────────────────────────────────────────
class PropellerZoneIn(BaseModel):
    placement_key: str
    zone_id: str | None = None
    snippet_html: str | None = None
    width: int | None = None
    height: int | None = None
    format: str = Field(default="banner", pattern="^(banner|popunder|push|native)$")
    is_active: bool = True
    target_viewport: str = Field(default="both", pattern="^(mobile|desktop|both)$")


@router.get("/propellerads-zones")
async def list_propellerads_zones(_: dict = Depends(a.require_admin)):
    db = get_db()
    rows = await db.propellerads_zones.find({}, {"_id": 0}).sort("placement_key", 1).to_list(length=200)
    return {"zones": rows, "valid_placements": sorted(VALID_PLACEMENTS),
            "valid_formats": ["banner", "popunder", "push", "native"]}


@router.post("/propellerads-zones")
async def upsert_propellerads_zone(body: PropellerZoneIn, user: dict = Depends(a.require_admin)):
    # popunder/push zones are global — they don't need a real placement_key,
    # but a sentinel string keeps the unique-index clean.
    if body.format == "banner" and body.placement_key not in VALID_PLACEMENTS:
        raise HTTPException(status_code=400, detail=f"Unknown placement_key. Use one of: {sorted(VALID_PLACEMENTS)}")
    if not (body.zone_id or body.snippet_html):
        raise HTTPException(status_code=400, detail="Provide at least zone_id or snippet_html")
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    payload = body.model_dump()
    payload["updated_at"] = now
    payload["updated_by"] = user["id"]
    await db.propellerads_zones.update_one(
        {"placement_key": body.placement_key, "format": body.format},
        {"$set": payload, "$setOnInsert": {"id": new_id(), "impressions": 0, "created_at": now}},
        upsert=True,
    )
    return {"ok": True, **payload}


@router.delete("/propellerads-zones/{placement_key}")
async def delete_propellerads_zone(placement_key: str, format: str = "banner", _: dict = Depends(a.require_admin)):
    db = get_db()
    res = await db.propellerads_zones.delete_one({"placement_key": placement_key, "format": format})
    return {"deleted": res.deleted_count}


# ─── Adsterra zones ────────────────────────────────────────────────────
class AdsterraZoneIn(BaseModel):
    placement_key: str
    zone_id: str | None = None
    snippet_html: str | None = None
    width: int | None = None
    height: int | None = None
    format: str = Field(default="banner", pattern="^(banner|popunder|push|native|social_bar|direct_link)$")
    is_active: bool = True
    target_viewport: str = Field(default="both", pattern="^(mobile|desktop|both)$")


@router.get("/adsterra-zones")
async def list_adsterra_zones(_: dict = Depends(a.require_admin)):
    db = get_db()
    rows = await db.adsterra_zones.find({}, {"_id": 0}).sort("placement_key", 1).to_list(length=200)
    return {
        "zones": rows,
        "valid_placements": sorted(VALID_PLACEMENTS),
        "valid_formats": ["banner", "popunder", "push", "native", "social_bar", "direct_link"],
    }


@router.post("/adsterra-zones")
async def upsert_adsterra_zone(body: AdsterraZoneIn, user: dict = Depends(a.require_admin)):
    if body.format == "banner" and body.placement_key not in VALID_PLACEMENTS:
        raise HTTPException(status_code=400, detail=f"Unknown placement_key. Use one of: {sorted(VALID_PLACEMENTS)}")
    if not (body.zone_id or body.snippet_html):
        raise HTTPException(status_code=400, detail="Provide at least zone_id or snippet_html")
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    payload = body.model_dump()
    payload["updated_at"] = now
    payload["updated_by"] = user["id"]
    await db.adsterra_zones.update_one(
        {"placement_key": body.placement_key, "format": body.format},
        {"$set": payload, "$setOnInsert": {"id": new_id(), "impressions": 0, "created_at": now}},
        upsert=True,
    )
    return {"ok": True, **payload}


@router.delete("/adsterra-zones/{placement_key}")
async def delete_adsterra_zone(placement_key: str, format: str = "banner", _: dict = Depends(a.require_admin)):
    db = get_db()
    res = await db.adsterra_zones.delete_one({"placement_key": placement_key, "format": format})
    return {"deleted": res.deleted_count}


# ─── One-click seed for the user's known ad inventory ───────────────────
# Builds the 12 Adsterra placement bindings from the keys the user pasted in
# their dashboard. Idempotent: re-running on prod won't duplicate rows. Call
# once after a deploy if the zones table looks empty.
@router.post("/seed-defaults")
async def seed_default_zones(admin: dict = Depends(a.require_admin)):
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    def adsterra_snippet(k: str, w: int, h: int) -> str:
        return (
            '<script type="text/javascript">'
            f'atOptions = {{"key":"{k}","format":"iframe","height":{h},"width":{w},"params":{{}}}};'
            '</script>'
            f'<script type="text/javascript" src="//www.topcreativeformat.com/{k}/invoke.js"></script>'
        )

    popunder_snip = '<script src="https://pl29726725.effectivecpmnetwork.com/c9/b4/77/c9b4775d5c519901cc2963972c3760d1.js"></script>'  # noqa: F841 — kept as reference; popunder zones are NOT seeded (click-hijack policy)

    adsterra_zones = [
        # 🚫 popunder zone INTENTIONALLY removed — popunders hijack taps.
        # 728x90 (desktop only)
        ("header_banner", "47bdc4aa", adsterra_snippet("47bdc4aaee0adc9a3a3054dc90bcde88", 728, 90), 728, 90, "banner", "desktop"),
        ("leaderboard_above", "47bdc4aa", adsterra_snippet("47bdc4aaee0adc9a3a3054dc90bcde88", 728, 90), 728, 90, "banner", "desktop"),
        # 468x60 (desktop only)
        ("wc_hub_sponsor", "1c75ccba", adsterra_snippet("1c75ccbae5b09a41c7fa02b82d9cc5cc", 468, 60), 468, 60, "banner", "desktop"),
        ("pool_sponsor", "1c75ccba", adsterra_snippet("1c75ccbae5b09a41c7fa02b82d9cc5cc", 468, 60), 468, 60, "banner", "desktop"),
        # 300x250 (both)
        ("match_list_inline", "414b1005", adsterra_snippet("414b1005460ea6e384f05845cd42fbe9", 300, 250), 300, 250, "banner", "both"),
        ("sidebar_right", "414b1005", adsterra_snippet("414b1005460ea6e384f05845cd42fbe9", 300, 250), 300, 250, "banner", "both"),
        ("predictions_inline", "414b1005", adsterra_snippet("414b1005460ea6e384f05845cd42fbe9", 300, 250), 300, 250, "banner", "both"),
        # 160x300 (both)
        ("wc_hub_top", "f935c3db", adsterra_snippet("f935c3dbc830c6d0b0e8db8d259bba39", 160, 300), 160, 300, "banner", "both"),
        # 160x600 (desktop only)
        ("fantasy_sidebar", "26bdc9ff", adsterra_snippet("26bdc9ff6c38a8bd47a6c5702c655cdb", 160, 600), 160, 600, "banner", "desktop"),
        # 320x50 (mobile only)
        ("mobile_bottom", "3d9ad5a5", adsterra_snippet("3d9ad5a5b07f4de03be71dd3a1fd121a", 320, 50), 320, 50, "banner", "mobile"),
        ("home_bottom_banner", "3d9ad5a5", adsterra_snippet("3d9ad5a5b07f4de03be71dd3a1fd121a", 320, 50), 320, 50, "banner", "mobile"),
    ]

    adsterra_written = 0
    for pk, zid, html, w, h, fmt, vp in adsterra_zones:
        payload = {
            "placement_key": pk, "zone_id": zid, "snippet_html": html,
            "width": w, "height": h, "format": fmt, "is_active": True,
            "target_viewport": vp, "updated_at": now, "updated_by": admin["id"],
        }
        await db.adsterra_zones.update_one(
            {"placement_key": pk, "format": fmt},
            {"$set": payload, "$setOnInsert": {"id": new_id(), "impressions": 0, "created_at": now}},
            upsert=True,
        )
        adsterra_written += 1

    # Also tag PropellerAds rows (if present) with viewport so the device
    # filter applies uniformly across both networks.
    PA_VIEWPORT = {
        "header_banner": "desktop", "leaderboard_above": "desktop",
        "wc_hub_sponsor": "desktop", "pool_sponsor": "desktop",
        "fantasy_sidebar": "desktop",
        "mobile_bottom": "mobile", "home_bottom_banner": "mobile",
    }
    pa_updated = 0
    for pk, vp in PA_VIEWPORT.items():
        r = await db.propellerads_zones.update_many(
            {"placement_key": pk, "target_viewport": {"$ne": vp}},
            {"$set": {"target_viewport": vp, "updated_at": now}},
        )
        pa_updated += r.modified_count or 0

    await db.audit_log.insert_one({
        "user_id": admin["id"], "email": admin.get("email"),
        "action": "ads_seed_defaults",
        "metadata": {"adsterra_written": adsterra_written, "propellerads_viewport_updated": pa_updated},
        "created_at": now,
    })
    return {
        "ok": True,
        "adsterra_written": adsterra_written,
        "propellerads_viewport_updated": pa_updated,
        "next_step": "Open Admin → Ads → Adsterra zones panel; you should see 12 rows.",
    }


@router.post("/wipe-popunders")
async def wipe_popunder_zones(admin: dict = Depends(a.require_admin)):
    """Permanently delete every popunder/onclick/vignette/interstitial zone
    from PropellerAds AND Adsterra. Click-hijack hardening — call once on
    prod after the deploy that disables popunders."""
    db = get_db()
    HIJACK_FORMATS = ["popunder", "onclick", "vignette", "interstitial"]
    pa = await db.propellerads_zones.delete_many({"format": {"$in": HIJACK_FORMATS}})
    at = await db.adsterra_zones.delete_many({"format": {"$in": HIJACK_FORMATS}})
    # Also blank the legacy `serving_head` field that used to ship OnClick.
    await db.settings.update_one(
        {"id": "propellerads_site"},
        {"$set": {"serving_head": "", "updated_at": datetime.now(timezone.utc).isoformat(),
                  "updated_by": admin["id"]}},
    )
    await db.audit_log.insert_one({
        "user_id": admin["id"], "email": admin.get("email"),
        "action": "ads_wipe_popunders",
        "metadata": {"propellerads_deleted": pa.deleted_count, "adsterra_deleted": at.deleted_count},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {
        "ok": True,
        "propellerads_deleted": pa.deleted_count,
        "adsterra_deleted": at.deleted_count,
    }


class PropellerSiteIn(BaseModel):
    verification_head: str | None = None


@router.get("/propellerads-site")
async def get_propellerads_site(_: dict = Depends(a.require_admin)):
    db = get_db()
    doc = await db.settings.find_one({"id": "propellerads_site"}, {"_id": 0}) or {}
    return {
        "verification_head": doc.get("verification_head") or "",
        "verification_files": doc.get("verification_files") or [],
    }


@router.post("/propellerads-site")
async def set_propellerads_site(body: PropellerSiteIn, admin: dict = Depends(a.require_admin)):
    """Persist the raw `<meta>` / `<script>` Multitag verification snippet
    PropellerAds wants in `<head>`. Two write paths so it works for *both*
    Monetag's static crawler verifier AND any runtime ad-tag loader:

      1. **Static** — patched into `/app/frontend/public/index.html` between
         `<!-- CP_AD_VERIFICATION_START --> ... END -->` markers, so the
         next `yarn build` ships the snippet in the initial HTML. This is
         the path the Monetag verifier actually reads.
      2. **Runtime** — stored in `db.settings.propellerads_site` and injected
         on every page via `<AdHeadInjector/>` so SPAs picked up post-boot
         still see it.

    Security: admin-only, 8 KB cap, audited.
    """
    head = (body.verification_head or "").strip()
    if len(head) > 8000:
        raise HTTPException(status_code=400, detail="Verification head too large (max 8 KB)")

    # Split the snippet: <meta>/<link>/comment tags can live in the static
    # `index.html` (safe for verifier crawlers, doesn't run JS). <script>
    # tags are isolated into `serving_head` and only injected via the React
    # runtime on browse routes — keeps Monetag's OnClick/Vignette from
    # hijacking clicks on /my-teams, /build-team, /admin, etc.
    import re
    static_safe = "\n".join(
        m.group(0) for m in re.finditer(r'<(meta|link|!--)[^>]*?(?:/>|-->)|<meta[^>]*>', head)
    )
    serving_only = re.sub(
        r'<(meta|link|!--)[^>]*?(?:/>|-->)', "", head, flags=re.IGNORECASE
    )
    serving_only = re.sub(r'<meta[^>]*>', "", serving_only, flags=re.IGNORECASE).strip()

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    old = await db.settings.find_one({"id": "propellerads_site"}, {"_id": 0, "verification_head": 1})
    await db.settings.update_one(
        {"id": "propellerads_site"},
        {"$set": {
            "verification_head": head,            # raw original (admin-editable)
            "static_head": static_safe,           # only safe-to-render-in-html
            "serving_head": serving_only,         # gated by route on the frontend
            "updated_at": now,
            "updated_by": admin["id"],
        }, "$setOnInsert": {"id": "propellerads_site"}},
        upsert=True,
    )

    # Patch into the static index.html so the verifier crawler sees the
    # <meta> tags. Scripts are NOT written here — they'd otherwise fire on
    # every page including click-sensitive ones (build-team, my-teams) and
    # let Monetag's OnClick/Vignette steal taps.
    static_patched = False
    static_error: str | None = None
    try:
        import pathlib
        idx_path = pathlib.Path("/app/frontend/public/index.html")
        if idx_path.exists():
            txt = idx_path.read_text(encoding="utf-8")
            START = "<!-- CP_AD_VERIFICATION_START -->"
            END = "<!-- CP_AD_VERIFICATION_END -->"
            if START in txt and END in txt:
                pre, rest = txt.split(START, 1)
                _, post = rest.split(END, 1)
                new_block = START + ("\n        " + static_safe if static_safe else "") + "\n        " + END
                idx_path.write_text(pre + new_block + post, encoding="utf-8")
                static_patched = True
            else:
                static_error = "Index markers missing — add CP_AD_VERIFICATION_START / END comments to <head>."
    except Exception as e:
        static_error = str(e)

    await db.audit_log.insert_one({
        "user_id": admin["id"], "email": admin.get("email"),
        "action": "propellerads_verification_head_set",
        "metadata": {
            "old_len": len((old or {}).get("verification_head") or ""),
            "new_len": len(head),
            "static_patched": static_patched,
            "static_error": static_error,
        },
        "created_at": now,
    })
    return {
        "ok": True,
        "verification_head": head,
        "static_patched": static_patched,
        "static_error": static_error,
        "next_step": "Redeploy cloudypitch.com (yarn build + restart) so the static index.html ships the snippet."
        if static_patched else "Add markers to /app/frontend/public/index.html, then save again.",
    }


class PropellerFileIn(BaseModel):
    filename: str
    content: str


@router.post("/propellerads-file")
async def upload_propellerads_file(body: PropellerFileIn, admin: dict = Depends(a.require_admin)):
    """Some PropellerAds verification paths need a small HTML / TXT file at
    the site root (e.g. `propeller-verification.html`). The admin pastes the
    filename + body; we (a) write the file into `/app/frontend/public/` so the
    static server serves it at `/{filename}`, and (b) persist a copy in
    `settings.propellerads_site.verification_files` so a fresh deploy can
    regenerate the file on boot.
    """
    import re
    import pathlib
    fn = (body.filename or "").strip().strip("/")
    # Strict allowlist: no leading dot, no path separators, length-bounded.
    if not re.match(r"^[a-zA-Z0-9_-][a-zA-Z0-9._-]{2,79}$", fn):
        raise HTTPException(
            status_code=400,
            detail="Filename must be 3–80 chars, start with [a-zA-Z0-9_-], and only contain letters/digits/_-.",
        )
    if len(body.content or "") > 8000:
        raise HTTPException(status_code=400, detail="File content too large (max 8 KB)")
    # Block overwriting the framework / sensitive files. (Belt-and-braces;
    # the regex above already rejects leading dots like `.env` / `.htaccess`.)
    BLOCKED = {
        "index.html", "manifest.json", "favicon.ico", "robots.txt",
        "asset-manifest.json", "service-worker.js",
    }
    if fn in BLOCKED or fn.lower().endswith(".js"):
        raise HTTPException(status_code=400, detail=f"Cannot overwrite {fn}")

    public_dir = pathlib.Path("/app/frontend/public").resolve()
    target = (public_dir / fn).resolve()
    # Defense in depth: ensure the resolved path is *inside* public_dir.
    if public_dir not in target.parents and target != public_dir:
        raise HTTPException(status_code=400, detail="Resolved path escapes public dir")
    public_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(body.content, encoding="utf-8")

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.settings.update_one(
        {"id": "propellerads_site"},
        {"$set": {"updated_at": now, "updated_by": admin["id"]},
         "$pull": {"verification_files": {"filename": fn}}},
        upsert=True,
    )
    await db.settings.update_one(
        {"id": "propellerads_site"},
        {"$push": {"verification_files": {"filename": fn, "content": body.content, "created_at": now}}},
        upsert=True,
    )
    await db.audit_log.insert_one({
        "user_id": admin["id"], "email": admin.get("email"),
        "action": "propellerads_verification_file_upload",
        "metadata": {"filename": fn, "bytes": len(body.content or "")},
        "created_at": now,
    })
    return {"ok": True, "filename": fn, "served_at": f"/{fn}"}


@router.delete("/propellerads-file/{filename}")
async def delete_propellerads_file(filename: str, admin: dict = Depends(a.require_admin)):
    import pathlib
    import re
    if not re.match(r"^[a-zA-Z0-9_-][a-zA-Z0-9._-]{2,79}$", filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    target = pathlib.Path("/app/frontend/public") / filename
    if target.exists() and filename not in {"index.html", "manifest.json", "favicon.ico", "robots.txt", "sw.js"}:
        try:
            target.unlink()
        except Exception:
            pass
    db = get_db()
    res = await db.settings.update_one(
        {"id": "propellerads_site"},
        {"$pull": {"verification_files": {"filename": filename}}},
    )
    await db.audit_log.insert_one({
        "user_id": admin["id"], "email": admin.get("email"),
        "action": "propellerads_verification_file_delete",
        "metadata": {"filename": filename, "modified": res.modified_count},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True, "modified": res.modified_count}


@router.get("/placements")
async def list_placements(
    placement_key: str | None = None,
    user: dict = Depends(a.get_optional_user),
):
    """Return active placements for the requesting user. Premium subs get nothing."""
    db = get_db()
    # Premium = is_premium flag on user (set when they subscribe — TODO Phase E webhook hook)
    if user and user.get("is_premium"):
        return {"placements": [], "premium": True}
    now_iso = datetime.now(timezone.utc).isoformat()
    query: dict = {"is_active": True}
    if placement_key:
        query["placement_key"] = placement_key
    # Date window filter
    placements = await db.ad_placements.find(query, {"_id": 0}).to_list(length=200)
    out = []
    for p in placements:
        if p.get("starts_at") and p["starts_at"] > now_iso:
            continue
        if p.get("ends_at") and p["ends_at"] < now_iso:
            continue
        out.append(p)
    return {"placements": out, "premium": False}


@router.post("/placements")
async def create_placement(body: PlacementIn, user: dict = Depends(a.require_admin)):
    if body.placement_key not in VALID_PLACEMENTS:
        raise HTTPException(status_code=400, detail=f"Invalid placement_key. Use one of: {sorted(VALID_PLACEMENTS)}")
    db = get_db()
    doc = body.model_dump()
    doc.update({
        "id": new_id(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "impressions": 0, "clicks": 0,
    })
    await db.ad_placements.insert_one(doc)
    doc.pop("_id", None)
    return {"placement": doc}


@router.patch("/placements/{placement_id}")
async def update_placement(placement_id: str, body: PlacementIn, user: dict = Depends(a.require_admin)):
    db = get_db()
    upd = body.model_dump()
    res = await db.ad_placements.update_one({"id": placement_id}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@router.delete("/placements/{placement_id}")
async def delete_placement(placement_id: str, user: dict = Depends(a.require_admin)):
    db = get_db()
    res = await db.ad_placements.delete_one({"id": placement_id})
    return {"deleted": res.deleted_count}


@router.post("/impression/{placement_id}")
async def track_impression(placement_id: str, user: dict = Depends(a.get_optional_user)):
    db = get_db()
    await db.ad_placements.update_one({"id": placement_id}, {"$inc": {"impressions": 1}})
    return {"ok": True}


@router.post("/click/{placement_id}")
async def track_click(placement_id: str, user: dict = Depends(a.get_optional_user)):
    db = get_db()
    await db.ad_placements.update_one({"id": placement_id}, {"$inc": {"clicks": 1}})
    return {"ok": True}


class RewardClaimIn(BaseModel):
    # Accept both legacy `card_uses` and the new `free_card` value so older
    # clients keep working until they hot-reload the JS bundle.
    reward_type: str = Field(pattern="^(card_uses|free_card|prediction_points)$")


@router.post("/reward/claim")
async def claim_reward(body: RewardClaimIn, user: dict = Depends(a.get_current_user)):
    """Rate-limited: 1 reward claim per 60 seconds. Grants ONE free random
    Star-tier (3) legend card, or +50 prediction points."""
    db = get_db()
    # Rate limit
    last = await db.ad_rewards.find_one(
        {"user_id": user["id"]}, sort=[("claimed_at", -1)],
    )
    if last and last.get("claimed_at"):
        last_dt = datetime.fromisoformat(last["claimed_at"])
        if (datetime.now(timezone.utc) - last_dt).total_seconds() < 60:
            raise HTTPException(status_code=429, detail="Wait 60s between rewards")

    payload: dict = {"reward_type": body.reward_type}
    if body.reward_type in ("card_uses", "free_card"):
        # Single-use card economy: a "card use" doesn't exist as a concept
        # any more — instead, the ad reward grants ONE FREE random Star-tier
        # card. The user adds a fresh boost-card to their inventory.
        import random
        star_cards = await db.legend_cards.find(
            {"tier": 3}, {"_id": 0, "id": 1, "name": 1},
        ).to_list(length=200)
        if not star_cards:
            raise HTTPException(status_code=503, detail="No reward cards available")
        gift = random.choice(star_cards)
        existing = await db.user_cards.find_one(
            {"user_id": user["id"], "card_id": gift["id"]},
        )
        if existing:
            await db.user_cards.update_one(
                {"id": existing["id"]},
                {"$inc": {"uses_remaining": 1, "uses_left": 1}},
            )
            uc_id = existing["id"]
        else:
            uc_id = new_id()
            await db.user_cards.insert_one({
                "id": uc_id, "user_id": user["id"], "card_id": gift["id"],
                "uses_remaining": 1, "uses_left": 1, "total_uses": 0,
                "acquired_via": "ad_reward",
                "acquired_at": datetime.now(timezone.utc).isoformat(),
            })
        payload["user_card_id"] = uc_id
        payload["card_id"] = gift["id"]
        payload["card_name"] = gift.get("name")
        # Keep `uses_added` for the legacy frontend that reads it
        payload["uses_added"] = 1
    else:
        # Add +50 bonus prediction points via a synthetic settled "prediction" row
        bonus_doc = {
            "id": new_id(), "user_id": user["id"], "match_id": "ad-reward",
            "home_score_predicted": 0, "away_score_predicted": 0,
            "outcome_predicted": "D", "points_awarded": 50,
            "exact_score_hit": False, "outcome_correct": True,
            "settled_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "ad_reward",
        }
        await db.predictions.insert_one(bonus_doc)
        payload["points_added"] = 50

    payload.update({
        "id": new_id(), "user_id": user["id"],
        "claimed_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.ad_rewards.insert_one(payload)
    payload.pop("_id", None)
    return {"ok": True, "reward": payload}
