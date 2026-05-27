"""Cloudy Pitch - database connection, indexes, helpers."""
import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

_client: AsyncIOMotorClient | None = None
_db = None


def init_db():
    global _client, _db
    _client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    _db = _client[os.environ["DB_NAME"]]
    return _db


def get_db():
    return _db


def close_db():
    if _client:
        _client.close()


async def ensure_indexes():
    db = get_db()
    # Users
    await db.users.create_index("email", unique=True)
    # Sessions
    await db.sessions.create_index("token_hash", unique=True)
    await db.sessions.create_index("expires_at", expireAfterSeconds=0)
    await db.sessions.create_index("user_id")
    # Auth audit
    await db.auth_audit.create_index([("user_id", 1), ("created_at", -1)])
    # Sports / leagues / teams
    await db.sports.create_index("slug", unique=True)
    await db.leagues.create_index("sportmonks_id", sparse=True)
    await db.leagues.create_index("api_sports_id", sparse=True)
    await db.leagues.create_index("statpal_id", sparse=True)
    await db.leagues.create_index([("sport_slug", 1), ("country", 1)])
    await db.teams.create_index("sportmonks_id", sparse=True)
    await db.teams.create_index("api_sports_id", sparse=True)
    await db.teams.create_index("statpal_id", sparse=True)
    await db.teams.create_index([("sport_slug", 1), ("name", 1)])
    # Matches
    await db.matches.create_index("sportmonks_id", sparse=True)
    await db.matches.create_index("api_sports_id", sparse=True)
    await db.matches.create_index("statpal_id", sparse=True)
    await db.matches.create_index([("sport_slug", 1), ("scheduled_at", 1)])
    await db.matches.create_index([("status", 1), ("scheduled_at", 1)])
    await db.matches.create_index("league_id")
    # Predictions
    await db.predictions.create_index(
        [("user_id", 1), ("match_id", 1)], unique=True
    )
    await db.predictions.create_index("settled_at", sparse=True)
    # Fantasy
    await db.fantasy_squads.create_index(
        [("user_id", 1), ("competition_id", 1)], unique=True
    )
    # Favorites
    await db.favorites.create_index(
        [("user_id", 1), ("entity_type", 1), ("entity_id", 1)], unique=True
    )
    # Rate limit
    await db.rate_limits.create_index("expires_at", expireAfterSeconds=0)
    # Login attempts
    await db.login_attempts.create_index("identifier")
    await db.login_attempts.create_index("created_at", expireAfterSeconds=3600)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
