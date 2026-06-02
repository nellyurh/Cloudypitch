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


# Mount routers
for r in (auth_router, catalog_router, matches_router, worldcup_router,
          predictions_router, fantasy_router, cards_router, card_usage_router,
          leagues_router, pools_router,
          profile_router, search_router, admin_router,
          wallet_router, compliance_router, ads_router, payments_router,
          referrals_router, auth_extras_router,
          wc_games_router, wc_admin_router,
          admin_cleanup_router,
          leaderboard_router):
    app.include_router(r)
