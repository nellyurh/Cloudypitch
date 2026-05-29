"""Auth routes: signup, signin, signout, me."""
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from db import get_db, utcnow_iso
from models import SignupIn, SigninIn, new_id, public_user
import auth as a

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup")
async def signup(payload: SignupIn, request: Request, response: Response):
    ip = a.get_ip(request)
    await a.rate_limit(f"signup:{ip}", a.SIGNUP_RATE_LIMIT, a.SIGNUP_RATE_WINDOW_SEC)
    db = get_db()
    email = payload.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        await a.audit_log("signup_conflict", None, email, ip)
        raise HTTPException(status_code=409, detail="Email already registered")
    # Look up referrer if a referral code was provided
    referred_by_user_id = None
    if payload.referral_code:
        ref_user = await db.users.find_one(
            {"referral_code": payload.referral_code.upper().strip()},
            {"_id": 0, "id": 1},
        )
        if ref_user:
            referred_by_user_id = ref_user["id"]
    user = {
        "id": new_id(),
        "email": email,
        "display_name": payload.display_name.strip(),
        "password_hash": a.hash_password(payload.password),
        "role": "user",
        "email_verified": False,
        "is_active": True,
        "failed_login_attempts": 0,
        "locked_until": None,
        "country_code": payload.country_code or "NG",
        "locale": "en-NG",
        "timezone": "Africa/Lagos",
        "referred_by_user_id": referred_by_user_id,
        "referred_by_code": payload.referral_code.upper().strip() if payload.referral_code else None,
        "created_at": utcnow_iso(),
        "last_login_at": None,
    }
    await db.users.insert_one(user)
    # Generate referral code for the new user
    from routes.referrals import ensure_referral_code
    await ensure_referral_code(user["id"])
    # Create the referral row for the inviter (with $0 spend; counts toward referred_count)
    if referred_by_user_id:
        await db.referrals.insert_one({
            "id": new_id(),
            "referrer_user_id": referred_by_user_id,
            "referred_user_id": user["id"],
            "joined_at": utcnow_iso(),
            "credit_earned_usd_cents": 0,
            "referred_spend_usd_cents": 0,
            "status": "pending",  # becomes "active" once they spend
        })
    # Grant 5 free Star cards (starter pack)
    star_cards = await db.legend_cards.find({"tier": 3}, {"_id": 0}).to_list(length=200)
    import random as _r
    starter = _r.sample(star_cards, min(5, len(star_cards))) if star_cards else []
    for c in starter:
        await db.user_cards.insert_one({
            "id": new_id(), "user_id": user["id"], "card_id": c["id"],
            "uses_remaining": 5, "uses_left": 5, "total_uses": 0,
            "acquired_at": utcnow_iso(),
            "acquired_via": "signup_starter",
        })
    raw = await a.create_session(user["id"], request)
    a.set_session_cookie(response, raw)
    await a.audit_log("signup", user["id"], email, ip)
    return {"user": public_user(user), "starter_cards": len(starter)}


@router.post("/signin")
async def signin(payload: SigninIn, request: Request, response: Response):
    ip = a.get_ip(request)
    await a.rate_limit(f"signin:{ip}", a.SIGNIN_RATE_LIMIT, a.SIGNIN_RATE_WINDOW_SEC)
    db = get_db()
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user:
        await a.audit_log("signin_unknown", None, email, ip)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if await a.is_locked(user):
        await a.audit_log("signin_locked", user["id"], email, ip)
        raise HTTPException(status_code=423, detail="Account locked. Try again later.")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account deactivated")
    if not a.verify_password(payload.password, user.get("password_hash", "")):
        await a.register_failed_login(user["id"], user.get("failed_login_attempts", 0))
        await a.audit_log("signin_fail", user["id"], email, ip)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    await a.clear_failed_logins(user["id"])
    raw = await a.create_session(user["id"], request)
    a.set_session_cookie(response, raw)
    await a.audit_log("signin", user["id"], email, ip)
    user["last_login_at"] = utcnow_iso()
    return {"user": public_user(user)}


@router.post("/signout")
async def signout(request: Request, response: Response):
    raw = request.cookies.get(a.COOKIE_NAME)
    if raw:
        await a.destroy_session(raw)
    a.clear_session_cookie(response)
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(a.get_current_user)):
    return {"user": public_user(user)}
