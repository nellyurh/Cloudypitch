"""Cookie-session authentication. Opaque sha256 tokens. bcrypt 12 rounds. NOT JWT.

Per spec:
- Cookie: cp_session, HTTP-only, SameSite=lax, secure in prod, 30-day TTL.
- Account lockout: 5 failed logins → 15 min lockout.
- Rate limit: 5 signups/hr per IP, 10 signins/15min per IP.
"""
from __future__ import annotations
import os
import hashlib
import secrets
import bcrypt
from datetime import timedelta
from fastapi import Request, Response, HTTPException, Depends
from db import get_db, utcnow, utcnow_iso
from models import new_id, public_user

COOKIE_NAME = "cp_session"
SESSION_TTL_DAYS = int(os.environ.get("SESSION_TTL_DAYS", "30"))
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "lax")
BCRYPT_ROUNDS = 12

LOCKOUT_THRESHOLD = 5
LOCKOUT_MINUTES = 15
SIGNUP_RATE_LIMIT = 5  # per hour per IP
SIGNUP_RATE_WINDOW_SEC = 3600
SIGNIN_RATE_LIMIT = 10  # per 15min per IP
SIGNIN_RATE_WINDOW_SEC = 900


# ----- Password hashing -----
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ----- Tokens -----
def new_session_token() -> tuple[str, str]:
    """Return (raw_token_for_cookie, sha256_hash_for_db)."""
    raw = secrets.token_urlsafe(48)
    return raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ----- Cookie helpers -----
def set_session_cookie(response: Response, raw_token: str):
    response.set_cookie(
        key=COOKIE_NAME,
        value=raw_token,
        max_age=SESSION_TTL_DAYS * 24 * 3600,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )


def clear_session_cookie(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")


# ----- IP helper -----
def get_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return (request.client.host if request.client else "0.0.0.0") or "0.0.0.0"


# ----- Rate limit (Mongo-backed, TTL via rate_limits collection) -----
async def rate_limit(key: str, limit: int, window_sec: int):
    db = get_db()
    now = utcnow()
    expires = now + timedelta(seconds=window_sec)
    await db.rate_limits.insert_one(
        {"key": key, "created_at": now.isoformat(), "expires_at": expires}
    )
    count = await db.rate_limits.count_documents({"key": key})
    if count > limit:
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")


# ----- Audit log -----
async def audit_log(action: str, user_id: str | None, email: str | None, ip: str, meta: dict | None = None):
    db = get_db()
    await db.auth_audit.insert_one({
        "id": new_id(),
        "action": action,
        "user_id": user_id,
        "email": email,
        "ip_address": ip,
        "metadata": meta or {},
        "created_at": utcnow_iso(),
    })


# ----- Lockout helpers -----
async def is_locked(user: dict) -> bool:
    locked_until = user.get("locked_until")
    if not locked_until:
        return False
    if isinstance(locked_until, str):
        from datetime import datetime as _dt
        try:
            return _dt.fromisoformat(locked_until.replace("Z", "+00:00")) > utcnow()
        except Exception:
            return False
    return locked_until > utcnow()


async def register_failed_login(user_id: str, current_fail_count: int):
    db = get_db()
    new_count = current_fail_count + 1
    update = {"failed_login_attempts": new_count}
    if new_count >= LOCKOUT_THRESHOLD:
        update["locked_until"] = (utcnow() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
        update["failed_login_attempts"] = 0
    await db.users.update_one({"id": user_id}, {"$set": update})


async def clear_failed_logins(user_id: str):
    db = get_db()
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"failed_login_attempts": 0, "locked_until": None, "last_login_at": utcnow_iso()}},
    )


# ----- Session create/destroy -----
async def create_session(user_id: str, request: Request) -> str:
    db = get_db()
    raw, h = new_session_token()
    await db.sessions.insert_one({
        "id": new_id(),
        "user_id": user_id,
        "token_hash": h,
        "user_agent": request.headers.get("user-agent", "")[:300],
        "ip_address": get_ip(request),
        "created_at": utcnow_iso(),
        "expires_at": utcnow() + timedelta(days=SESSION_TTL_DAYS),
        "revoked_at": None,
    })
    return raw


async def destroy_session(raw_token: str):
    db = get_db()
    await db.sessions.delete_one({"token_hash": hash_token(raw_token)})


# ----- Dependency -----
async def get_current_user(request: Request) -> dict:
    db = get_db()
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        raise HTTPException(status_code=401, detail="Not authenticated")
    sess = await db.sessions.find_one({"token_hash": hash_token(raw), "revoked_at": None})
    if not sess:
        raise HTTPException(status_code=401, detail="Invalid session")
    user = await db.users.find_one({"id": sess["user_id"]})
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="User inactive")
    user.pop("_id", None)
    return user


async def get_optional_user(request: Request) -> dict | None:
    try:
        return await get_current_user(request)
    except HTTPException:
        return None


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


# ----- Seed admin -----
async def seed_admin():
    db = get_db()
    email = os.environ.get("ADMIN_EMAIL", "admin@cloudypitch.com").lower()
    pw = os.environ.get("ADMIN_PASSWORD", "CloudyAdmin2026!")
    existing = await db.users.find_one({"email": email})
    if not existing:
        await db.users.insert_one({
            "id": new_id(),
            "email": email,
            "display_name": "Cloudy Admin",
            "password_hash": hash_password(pw),
            "role": "admin",
            "email_verified": True,
            "is_active": True,
            "failed_login_attempts": 0,
            "locked_until": None,
            "country_code": "NG",
            "locale": "en-NG",
            "timezone": "Africa/Lagos",
            "created_at": utcnow_iso(),
            "last_login_at": None,
        })
    else:
        # Refresh password if it changed in .env (idempotent)
        if not verify_password(pw, existing.get("password_hash", "")):
            await db.users.update_one(
                {"id": existing["id"]},
                {"$set": {"password_hash": hash_password(pw), "role": "admin", "is_active": True}},
            )
