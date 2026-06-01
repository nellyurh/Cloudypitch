"""Admin panel routes."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
from db import get_db, utcnow_iso
import auth as a
from ingestion import sync_sportmonks_today_and_next, sync_apisports_today, sync_statpal_tennis, poll_sportmonks_live

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
async def admin_stats(_: dict = Depends(a.require_admin)):
    db = get_db()
    return {
        "users": await db.users.count_documents({}),
        "active_sessions": await db.sessions.count_documents({"revoked_at": None}),
        "matches": await db.matches.count_documents({}),
        "live_matches": await db.matches.count_documents({"is_live": True}),
        "events": await db.match_events.count_documents({}),
        "leagues": await db.leagues.count_documents({}),
        "teams": await db.teams.count_documents({}),
        "predictions": await db.predictions.count_documents({}),
        "fantasy_squads": await db.fantasy_squads.count_documents({}),
        "cards": await db.legend_cards.count_documents({}),
        "user_cards": await db.user_cards.count_documents({}),
    }


@router.get("/matches")
async def admin_matches(
    _: dict = Depends(a.require_admin),
    sport: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 100,
):
    db = get_db()
    query: dict = {}
    if sport:
        query["sport_slug"] = sport
    if q:
        rx = {"$regex": q, "$options": "i"}
        query["$or"] = [{"home_team_name": rx}, {"away_team_name": rx}, {"league_name": rx}]
    rows = await db.matches.find(query, {"_id": 0}).sort("scheduled_at", -1).limit(limit).to_list(length=limit)
    return {"matches": rows, "count": len(rows)}


@router.get("/users")
async def admin_users(_: dict = Depends(a.require_admin), limit: int = 100):
    db = get_db()
    rows = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).limit(limit).to_list(length=limit)
    return {"users": rows}


@router.post("/users/{user_id}/promote")
async def promote_user(user_id: str, _: dict = Depends(a.require_admin)):
    db = get_db()
    await db.users.update_one({"id": user_id}, {"$set": {"role": "admin"}})
    return {"ok": True}


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(user_id: str, _: dict = Depends(a.require_admin)):
    db = get_db()
    await db.users.update_one({"id": user_id}, {"$set": {"is_active": False}})
    return {"ok": True}


@router.get("/audit")
async def audit(_: dict = Depends(a.require_admin), limit: int = 100):
    db = get_db()
    rows = await db.auth_audit.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(length=limit)
    return {"audit": rows}


@router.post("/players/recompute-prices")
async def admin_recompute_prices(_: dict = Depends(a.require_admin)):
    """Reprice every existing WC2026 player using the new varied-price algorithm.
    Idempotent — safe to call multiple times.
    """
    db = get_db()
    rows = await db.players.find({"is_wc_2026": True}, {"_id": 0}).to_list(length=5000)
    top_tier = {"brazil","argentina","france","england","spain","germany","portugal","netherlands","belgium","italy","croatia","uruguay","colombia","morocco"}
    mid_tier = {"japan","south korea","mexico","usa","switzerland","denmark","poland","ecuador","senegal","ghana","ivory coast","côte d'ivoire","saudi arabia","australia","austria","sweden"}
    updated = 0
    for p in rows:
        country_name = (p.get("country") or p.get("team_name") or "").lower().strip()
        if country_name in top_tier:   tier_premium = 1.6
        elif country_name in mid_tier: tier_premium = 0.6
        else:                          tier_premium = -0.4
        pos = p.get("position", "MID")
        base_price = {"GK": 4.5, "DEF": 5.0, "MID": 7.0, "FWD": 8.5}.get(pos, 5.0)
        jersey = p.get("shirt_number")
        jersey_bump = 0.0
        if isinstance(jersey, int):
            if jersey == 10: jersey_bump = 2.0
            elif jersey == 9: jersey_bump = 1.5
            elif jersey == 7: jersey_bump = 1.2
            elif jersey == 1: jersey_bump = 0.8
            elif jersey <= 11: jersey_bump = 0.6
            elif jersey <= 20: jersey_bump = 0.0
            else: jersey_bump = -0.5
        try:
            sid = p.get("sportmonks_id") or p.get("id") or ""
            h = int.from_bytes(str(sid).encode(), "big") % 7
            dispersion = (h - 3) * 0.1
        except Exception:
            dispersion = 0.0
        raw = base_price + tier_premium + jersey_bump + dispersion
        snapped = round(raw * 2) / 2
        new_price = max(4.0, min(14.0, snapped))
        if new_price != p.get("price"):
            await db.players.update_one({"id": p["id"]}, {"$set": {"price": new_price, "updated_at": utcnow_iso()}})
            updated += 1
    return {"ok": True, "scanned": len(rows), "updated": updated}


@router.post("/ingest/sportmonks/sync")
async def trigger_sportmonks_sync(_: dict = Depends(a.require_admin), days: int = 7):
    await sync_sportmonks_today_and_next(days_ahead=days)
    return {"ok": True}


@router.post("/ingest/sportmonks/live")
async def trigger_sportmonks_live(_: dict = Depends(a.require_admin)):
    count = await poll_sportmonks_live()
    return {"ok": True, "live_count": count}


@router.post("/ingest/apisports/{sport}/sync")
async def trigger_apisports_sync(sport: str, _: dict = Depends(a.require_admin)):
    await sync_apisports_today(sport)
    return {"ok": True}


@router.post("/ingest/statpal/tennis/sync")
async def trigger_statpal_tennis(_: dict = Depends(a.require_admin)):
    await sync_statpal_tennis()
    return {"ok": True}


@router.post("/uploads")
async def upload_logo(
    file: UploadFile = File(...),
    entity_type: str = Form("league"),
    entity_id: str = Form(""),
    user: dict = Depends(a.require_admin),
):
    """Upload an image. For MVP we store as base64 in MongoDB (avoids needing object storage)."""
    if file.content_type not in ("image/png", "image/jpeg", "image/webp", "image/svg+xml"):
        raise HTTPException(status_code=400, detail="Only PNG/JPEG/WebP/SVG allowed")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Max 5MB")
    import base64
    b64 = base64.b64encode(data).decode("ascii")
    data_url = f"data:{file.content_type};base64,{b64}"
    db = get_db()
    rec = {
        "id": data_url[:64],
        "uploaded_by": user["id"], "entity_type": entity_type, "entity_id": entity_id,
        "kind": "logo", "mime_type": file.content_type, "size_bytes": len(data),
        "data_url": data_url, "created_at": utcnow_iso(),
    }
    await db.uploads.insert_one(rec)
    if entity_type == "league" and entity_id:
        await db.leagues.update_one({"id": entity_id}, {"$set": {"logo_url": data_url}})
    elif entity_type == "team" and entity_id:
        await db.teams.update_one({"id": entity_id}, {"$set": {"logo_url": data_url}})
    elif entity_type == "brand":
        # entity_id picks the slot: "logo" | "mark" | "wordmark"
        slot = entity_id or "logo"
        await db.app_settings.update_one(
            {"id": "brand"},
            {"$set": {f"brand_{slot}_url": data_url, "updated_at": utcnow_iso(), "updated_by": user["id"]}},
            upsert=True,
        )
    rec.pop("_id", None)
    return {"upload": rec}


@router.post("/users/create-admin")
async def create_admin_user(
    payload: dict,
    user: dict = Depends(a.require_admin),
):
    """Create a brand-new admin user (or promote existing) from the admin panel.

    Body: {email, password, display_name?}
    """
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    display_name = (payload.get("display_name") or "").strip() or email.split("@")[0]
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    db = get_db()
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        # Promote in place
        await db.users.update_one({"email": email}, {"$set": {"role": "admin", "is_active": True}})
        return {"ok": True, "promoted": True, "user_id": existing.get("id")}

    # Fresh creation — mirror the auth registration flow
    import uuid
    new_user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": a.hash_password(password),
        "display_name": display_name,
        "role": "admin",
        "is_active": True,
        "is_premium": False,
        "country_code": "NG",
        "wallet_balance_usd_cents": 0,
        "created_at": utcnow_iso(),
        "created_by": user["id"],
    }
    await db.users.insert_one(new_user)
    new_user.pop("_id", None)
    new_user.pop("password_hash", None)
    return {"ok": True, "created": True, "user": new_user}
