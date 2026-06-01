"""Cloudy Pitch — FastAPI main app."""
from dotenv import load_dotenv
from pathlib import Path
import os

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

import logging
from fastapi import FastAPI
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
        await start_background_jobs()
        log.info("Cloudy Pitch ingestion jobs kicked off")
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
