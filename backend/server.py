"""Cloudy Pitch — FastAPI main app."""
from dotenv import load_dotenv
from pathlib import Path
import os

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

import logging
from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from db import init_db, close_db, ensure_indexes
from auth import seed_admin
from seed_data import seed_all
from ingestion import start_background_jobs

# Routers
from routes.auth_routes import router as auth_router
from routes.auth_extras import router as auth_extras_router
from routes.catalog import router as catalog_router
from routes.matches import router as matches_router
from routes.worldcup import router as worldcup_router
from routes.predictions import router as predictions_router
from routes.fantasy import router as fantasy_router
from routes.cards import router as cards_router
from routes.card_usage import router as card_usage_router
from routes.leagues import router as leagues_router
from routes.prize_pools import router as pools_router
from routes.profile import router as profile_router
from routes.search import router as search_router
from routes.admin import router as admin_router
from routes.referrals import router as referrals_router
from routes.wallet import router as wallet_router
from routes.compliance import router as compliance_router
from routes.ads import router as ads_router
from routes.payments import router as payments_router
from routes.pocketfi import router as pocketfi_router, webhook_router as pocketfi_webhook_router
from routes.trybit import router as trybit_router, webhook_router as trybit_webhook_router
from routes.wc_games import router as wc_games_router, admin_router as wc_admin_router
from routes.admin_cleanup import router as admin_cleanup_router
from routes.leaderboard import router as leaderboard_router


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("cloudypitch")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        await ensure_indexes()
        await seed_admin()
        await seed_all()
        log.info("Cloudy Pitch boot: indexes + seeds OK")
        # Ingestion only runs when explicitly enabled (worker container sets RUN_INGESTION=1).
        # The API-only container leaves this off so it can scale horizontally without
        # duplicate background pollers.
        if os.environ.get("RUN_INGESTION", "1") == "1":
            await start_background_jobs()
            log.info("Cloudy Pitch ingestion jobs kicked off (RUN_INGESTION=1)")
        else:
            log.info("API-only mode (RUN_INGESTION=0); ingestion handled by worker container")
    except Exception as e:
        log.exception(f"Startup error: {e}")
    yield
    close_db()


app = FastAPI(title="Cloudy Pitch API", version="1.0.0", lifespan=lifespan)


# CORS — credentials enabled, origin from env
_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
if "*" in _origins:
    # allow_credentials with * is invalid; mirror request origin via regex
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/api")
async def api_root():
    return {"app": "Cloudy Pitch", "version": "1.0.0", "status": "ok"}


@app.get("/api/health")
async def health():
    return {"ok": True}


@app.get("/api/brand")
async def get_brand():
    """Public brand settings — frontend reads on boot to render the live logo."""
    from db import get_db
    db = get_db()
    doc = await db.app_settings.find_one({"id": "brand"}, {"_id": 0}) or {}
    return {
        "brand_logo_url": doc.get("brand_logo_url"),
        "brand_logo_dark_url": doc.get("brand_logo_dark_url"),
        "brand_mark_url": doc.get("brand_mark_url"),
        "brand_wordmark_url": doc.get("brand_wordmark_url"),
    }


@app.get("/api/currency")
async def currency_settings(request: Request):
    """Returns {code, symbol, rate} based on the visitor's country.

    Country is taken from CF-IPCountry (set by Cloudflare proxy) or X-Country.
    Admin can edit the NGN exchange rate in app_settings.id='currency'.
    """
    from db import get_db
    db = get_db()
    doc = await db.app_settings.find_one({"id": "currency"}, {"_id": 0}) or {}
    ngn_rate = float(doc.get("ngn_per_usd") or 1400)
    headers = request.headers
    country = (
        headers.get("cf-ipcountry")
        or headers.get("x-country")
        or headers.get("x-vercel-ip-country")
        or ""
    ).upper().strip()
    # Allow ?force=NG for testing
    forced = (request.query_params.get("force") or "").upper().strip()
    if forced:
        country = forced
    if country == "NG":
        return {"country": "NG", "code": "NGN", "symbol": "₦", "rate": ngn_rate, "base": "USD"}
    return {"country": country or "WORLD", "code": "USD", "symbol": "$", "rate": 1.0, "base": "USD"}


@app.post("/api/admin/currency")
async def set_currency_rate(payload: dict, request: Request):
    """Admin: set the NGN exchange rate. Requires admin session."""
    from db import get_db
    import auth as a
    # Manual auth check (this isn't on the router with global dep)
    user = await a.get_current_user(request)
    if not user or user.get("role") != "admin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin required")
    db = get_db()
    rate = float(payload.get("ngn_per_usd") or 0)
    if not (1 <= rate <= 100000):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="rate must be 1–100000")
    await db.app_settings.update_one(
        {"id": "currency"},
        {"$set": {"ngn_per_usd": rate, "updated_by": user["id"], "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"ok": True, "ngn_per_usd": rate}


# ============ Site config: enabled sports + admin popup ============
_DEFAULT_ENABLED_SPORTS = [
    "football", "basketball", "tennis", "baseball", "hockey", "cricket",
    "rugby", "nba", "volleyball", "handball", "mma", "f1", "afl", "golf",
]


@app.get("/api/site-config")
async def site_config():
    """Public site config — enabled sport tabs + active admin popup notice.

    Frontend reads on boot. Disabled sports are hidden from the nav and
    skipped by the ingestion worker (to save API quota).
    """
    from db import get_db
    db = get_db()
    doc = await db.app_settings.find_one({"id": "site"}, {"_id": 0}) or {}
    enabled = doc.get("enabled_sports")
    if not isinstance(enabled, list) or not enabled:
        enabled = list(_DEFAULT_ENABLED_SPORTS)
    popup = doc.get("popup_notice") or {}
    # Strip empty/disabled
    if not popup.get("enabled"):
        popup = {"enabled": False}
    return {
        "enabled_sports": enabled,
        "show_wc_tab": bool(doc.get("show_wc_tab", True)),
        "popup_notice": popup,
    }


@app.post("/api/admin/site-config")
async def update_site_config(payload: dict, request: Request):
    """Admin: update enabled sports and popup notice.

    Body: {enabled_sports?: list[str], show_wc_tab?: bool,
           popup_notice?: {enabled, title, body, image_url, cta_text, cta_link, version}}
    """
    from db import get_db
    import auth as a
    user = await a.get_current_user(request)
    if not user or user.get("role") != "admin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin required")
    db = get_db()
    update: dict = {"updated_by": user["id"], "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}
    if "enabled_sports" in payload:
        raw = payload.get("enabled_sports") or []
        if not isinstance(raw, list):
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="enabled_sports must be a list of slugs")
        # Whitelist against known sports
        update["enabled_sports"] = [s for s in raw if s in _DEFAULT_ENABLED_SPORTS]
    if "show_wc_tab" in payload:
        update["show_wc_tab"] = bool(payload.get("show_wc_tab"))
    if "popup_notice" in payload:
        p = payload.get("popup_notice") or {}
        # Bump version on save so frontend re-shows once even to users who already dismissed.
        existing = await db.app_settings.find_one({"id": "site"}, {"_id": 0}) or {}
        old_ver = int((existing.get("popup_notice") or {}).get("version") or 0)
        update["popup_notice"] = {
            "enabled": bool(p.get("enabled")),
            "title": (p.get("title") or "").strip()[:120],
            "body": (p.get("body") or "").strip()[:600],
            "image_url": (p.get("image_url") or "").strip()[:1024],
            "cta_text": (p.get("cta_text") or "").strip()[:40],
            "cta_link": (p.get("cta_link") or "").strip()[:500],
            "version": old_ver + 1 if p.get("bump_version") else old_ver,
        }
        if not update["popup_notice"]["version"]:
            update["popup_notice"]["version"] = 1
    await db.app_settings.update_one(
        {"id": "site"},
        {"$set": update},
        upsert=True,
    )
    doc = await db.app_settings.find_one({"id": "site"}, {"_id": 0}) or {}
    return {"ok": True, "site": doc}


# Mount routers
for r in (auth_router, catalog_router, matches_router, worldcup_router,
          predictions_router, fantasy_router, cards_router, card_usage_router,
          leagues_router, pools_router,
          profile_router, search_router, admin_router,
          wallet_router, compliance_router, ads_router, payments_router,
          pocketfi_router, pocketfi_webhook_router,
          trybit_router, trybit_webhook_router,
          referrals_router, auth_extras_router,
          wc_games_router, wc_admin_router,
          admin_cleanup_router,
          leaderboard_router):
    app.include_router(r)
