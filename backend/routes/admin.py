"""Admin panel routes."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
from pydantic import BaseModel
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


class UserNameIn(BaseModel):
    display_name: str


@router.patch("/users/{user_id}/display-name")
async def admin_set_display_name(
    user_id: str,
    body: UserNameIn,
    admin: dict = Depends(a.require_admin),
):
    """Rename a user. Validates uniqueness and length (2–30 chars). Logs to
    audit trail so the change is traceable. Idempotent — same name is a no-op.
    """
    db = get_db()
    new_name = (body.display_name or "").strip()
    if not (2 <= len(new_name) <= 30):
        raise HTTPException(status_code=400, detail="Display name must be 2–30 characters")
    target = await db.users.find_one({"id": user_id}, {"_id": 0, "display_name": 1, "email": 1})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.get("display_name") == new_name:
        return {"ok": True, "user_id": user_id, "display_name": new_name, "unchanged": True}
    clash = await db.users.find_one({"display_name": new_name, "id": {"$ne": user_id}}, {"_id": 0, "id": 1})
    if clash:
        raise HTTPException(status_code=400, detail="That display name is already taken")
    await db.users.update_one({"id": user_id}, {"$set": {"display_name": new_name}})
    await db.audit_log.insert_one({
        "user_id": admin["id"], "email": admin.get("email"),
        "action": "user_display_name_change",
        "metadata": {
            "target_user_id": user_id,
            "target_email": target.get("email"),
            "old_name": target.get("display_name"),
            "new_name": new_name,
        },
    })
    return {"ok": True, "user_id": user_id, "display_name": new_name}


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
    rows = await db.players.find({"is_wc_2026": True, "$or": [{"price_override": {"$exists": False}}, {"price_override": False}]}, {"_id": 0}).to_list(length=5000)
    top_tier = {"brazil","argentina","france","england","spain","germany","portugal","netherlands","belgium","italy","croatia","uruguay","colombia","morocco"}
    mid_tier = {"japan","south korea","mexico","usa","switzerland","denmark","poland","ecuador","senegal","ghana","ivory coast","côte d'ivoire","saudi arabia","australia","austria","sweden"}
    updated = 0
    for p in rows:
        country_name = (p.get("country") or p.get("team_name") or "").lower().strip()
        if country_name in top_tier:
            tier_premium = 0.8
        elif country_name in mid_tier:
            tier_premium = 0.3
        else:
            tier_premium = -0.4
        pos = p.get("position", "MID")
        base_price = {"GK": 4.0, "DEF": 4.5, "MID": 5.5, "FWD": 6.5}.get(pos, 5.0)
        jersey = p.get("shirt_number")
        jersey_bump = 0.0
        if isinstance(jersey, int):
            if jersey == 10:
                jersey_bump = 1.0
            elif jersey == 9:
                jersey_bump = 0.8
            elif jersey == 7:
                jersey_bump = 0.6
            elif jersey == 1:
                jersey_bump = 0.4
            elif jersey <= 11:
                jersey_bump = 0.3
            elif jersey <= 20:
                jersey_bump = 0.0
            else:
                jersey_bump = -0.3
        try:
            sid = p.get("sportmonks_id") or p.get("id") or ""
            h = int.from_bytes(str(sid).encode(), "big") % 7
            dispersion = (h - 3) * 0.1
        except Exception:
            dispersion = 0.0
        raw = base_price + tier_premium + jersey_bump + dispersion
        snapped = round(raw * 2) / 2
        new_price = max(3.5, min(10.0, snapped))
        # Curated star floor — real elite players always end up on top of the price ladder.
        try:
            from star_tiers import star_floor
            floor = star_floor(p.get("name") or "")
            if floor and floor > new_price:
                new_price = min(11.5, floor)
        except Exception:
            pass
        if new_price != p.get("price"):
            await db.players.update_one({"id": p["id"]}, {"$set": {"price": new_price, "updated_at": utcnow_iso()}})
            updated += 1
    return {"ok": True, "scanned": len(rows), "updated": updated}


@router.get("/players/season-points")
async def admin_players_season_points(
    _: dict = Depends(a.require_admin),
    limit: int = 1500,
):
    """For every WC2026 player, sum the fantasy points they have actually
    earned across every settled match this tournament. The output drives the
    "Player Points" admin tab and lets the admin re-price under-/over-valued
    players using `suggested_price`.

    `season_points` is computed from `match_events` + `match_lineups` (same
    source the settler uses) — so prices stay locked to the live scoring engine.

    `suggested_price` rule of thumb (matches the rest of the price ladder):
       suggested = current_price + (season_points - 8 * matches_played) * 0.04
    Then clamped to [4.0, 14.5] and rounded to 0.1.
    """
    from fantasy_scoring import compute_player_points, aggregate_player_stats_from_events
    db = get_db()

    # Load all finished WC matches (FT / AET / PEN / FT_PEN / AWARDED).
    FINISHED = {"FT", "AET", "PEN", "FT_PEN", "AWARDED"}
    matches = await db.matches.find(
        {"is_world_cup": True},
        {"_id": 0, "id": 1, "home_team_id": 1, "away_team_id": 1,
         "home_score": 1, "away_score": 1, "status": 1},
    ).to_list(length=400)
    matches = [m for m in matches if (m.get("status") or "").upper() in FINISHED]
    match_ids = [m["id"] for m in matches]

    events_by_match: dict[str, list[dict]] = {}
    lineups_by_match: dict[str, list[dict]] = {}
    cs_map: dict[tuple[str, str], bool] = {}
    if match_ids:
        for e in await db.match_events.find({"match_id": {"$in": match_ids}}, {"_id": 0}).to_list(length=20000):
            events_by_match.setdefault(e["match_id"], []).append(e)
        for ln in await db.match_lineups.find({"match_id": {"$in": match_ids}}, {"_id": 0}).to_list(length=20000):
            lineups_by_match.setdefault(ln["match_id"], []).append(ln)
        for m in matches:
            h = int(m.get("home_score") or 0)
            a = int(m.get("away_score") or 0)
            if m.get("home_team_id"):
                cs_map[(m["id"], m["home_team_id"])] = (a == 0)
            if m.get("away_team_id"):
                cs_map[(m["id"], m["away_team_id"])] = (h == 0)

    players = await db.players.find(
        {"is_wc_2026": True},
        {"_id": 0, "id": 1, "name": 1, "team_id": 1, "team_name": 1,
         "country": 1, "position": 1, "price": 1, "photo_url": 1},
    ).sort("name", 1).limit(limit).to_list(length=limit)

    out: list[dict] = []
    for p in players:
        name = p.get("name") or ""
        team_id = p.get("team_id")
        position = (p.get("position") or "MID").upper()
        total_pts = 0
        matches_played = 0
        for m in matches:
            if team_id not in (m.get("home_team_id"), m.get("away_team_id")):
                continue
            evs = events_by_match.get(m["id"], [])
            agg = aggregate_player_stats_from_events(evs, name, team_id)
            lin = next(
                (x for x in lineups_by_match.get(m["id"], [])
                 if (x.get("player_name") or "").strip().lower() == name.strip().lower()),
                None,
            )
            minutes = 0
            if lin:
                minutes = 90 if lin.get("starter") else 30
                if agg.get("substituted_out"):
                    minutes = max(0, minutes - 30)
            if minutes == 0 and not (agg.get("goals") or agg.get("assists") or agg.get("yellow_cards") or agg.get("red_cards")):
                continue
            matches_played += 1
            res = compute_player_points(
                position=position,
                minutes_played=minutes,
                goals=int(agg.get("goals", 0)),
                assists=int(agg.get("assists", 0)),
                yellow_cards=int(agg.get("yellow_cards", 0)),
                red_cards=int(agg.get("red_cards", 0)),
                own_goals=int(agg.get("own_goals", 0)),
                missed_penalties=int(agg.get("missed_penalties", 0)),
                clean_sheet=bool(cs_map.get((m["id"], team_id), False)),
                saves=int(agg.get("saves", 0)),
                penalty_saves=int(agg.get("penalty_saves", 0)),
                is_motm=False,
            )
            total_pts += int(res["points"])

        # Suggested price: nudge by performance vs a flat 8pts/match baseline.
        cur = float(p.get("price") or 5.0)
        delta = (total_pts - 8 * matches_played) * 0.04 if matches_played else 0.0
        suggested = round(max(4.0, min(14.5, cur + delta)) * 10) / 10.0

        out.append({
            "player_id": p["id"],
            "name": name,
            "team_id": team_id,
            "team_name": p.get("team_name") or p.get("country"),
            "country": p.get("country"),
            "position": position,
            "price": cur,
            "photo_url": p.get("photo_url"),
            "season_points": total_pts,
            "matches_played": matches_played,
            "ppg": round(total_pts / matches_played, 2) if matches_played else 0.0,
            "suggested_price": suggested,
        })

    out.sort(key=lambda r: (-(r["season_points"] or 0), -(r["matches_played"] or 0), r["name"]))
    return {
        "players": out,
        "matches_processed": len(matches),
        "scanned_players": len(players),
    }


class PlayerPriceIn(BaseModel):
    price: float


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



# ---------- Player price admin ----------
@router.get("/players")
async def admin_list_players(
    q: str = "",
    team: str = "",
    position: str = "",
    limit: int = 50,
    _: dict = Depends(a.require_admin),
):
    """Admin search players (defaults to WC2026 pool)."""
    db = get_db()
    qry = {"is_wc_2026": True}
    if q:
        qry["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"team_name": {"$regex": q, "$options": "i"}},
        ]
    if team:
        qry["team_name"] = team
    if position:
        qry["position"] = position
    rows = await db.players.find(qry, {"_id": 0}).sort([("price", -1), ("name", 1)]).limit(min(limit, 200)).to_list(length=limit)
    return {"players": rows, "count": len(rows)}


@router.patch("/players/{player_id}/price")
async def admin_set_player_price(player_id: str, payload: dict, user: dict = Depends(a.require_admin)):
    """Set a single player's fantasy price manually. Persists `price_override=True`
    so the next recompute will SKIP this row (admin choice wins).
    """
    price = float(payload.get("price") or 0)
    if not (3.0 <= price <= 15.0):
        raise HTTPException(400, "price must be £3.0–£15.0")
    db = get_db()
    res = await db.players.update_one(
        {"id": player_id},
        {"$set": {"price": price, "price_override": True, "price_overridden_by": user["id"], "updated_at": utcnow_iso()}},
    )
    if not res.matched_count:
        raise HTTPException(404, "Player not found")
    return {"ok": True, "id": player_id, "price": price}



# ---------- Legend Cards (price + position editor) ----------
@router.get("/cards")
async def admin_list_cards(user: dict = Depends(a.require_admin), tier: Optional[int] = None):
    """List every legend card with its admin-editable fields."""
    db = get_db()
    q: dict = {}
    if tier in (1, 2, 3):
        q["tier"] = tier
    rows = await db.legend_cards.find(q, {"_id": 0}).sort([("tier", 1), ("name", 1)]).to_list(length=500)
    return {"cards": rows, "count": len(rows)}


@router.patch("/cards/{card_id}")
async def admin_update_card(card_id: str, payload: dict, user: dict = Depends(a.require_admin)):
    """Edit price (in COINS, was USD cents) and/or position lock of a single
    legend card.

    Supported fields:
      * `price_coins` (1-1_000_000) ← preferred, COIN units.
      * `price_usd_cents` (10-100000) ← legacy, kept for backwards compat.
      * `position` (GK/DEF/MID/FWD/ANY)
      * `description` (free text, ≤200 chars)
    """
    db = get_db()
    old = await db.legend_cards.find_one({"id": card_id}, {"_id": 0})
    if not old:
        raise HTTPException(404, "Card not found")
    upd: dict = {}
    if "price_coins" in payload and payload["price_coins"] is not None:
        try:
            c = int(payload["price_coins"])
        except (TypeError, ValueError):
            raise HTTPException(400, "price_coins must be an integer")
        if not (1 <= c <= 1_000_000):
            raise HTTPException(400, "price_coins must be 1-1,000,000")
        upd["price_coins"] = c
    if "price_usd_cents" in payload and payload["price_usd_cents"] is not None:
        try:
            p = int(payload["price_usd_cents"])
        except (TypeError, ValueError):
            raise HTTPException(400, "price_usd_cents must be an integer (cents)")
        if not (10 <= p <= 100000):
            raise HTTPException(400, "price_usd_cents must be 10-100000 (¢$0.10-$1,000)")
        upd["price_usd_cents"] = p
    if "position" in payload and payload["position"] is not None:
        pos = str(payload["position"]).upper()
        if pos not in ("GK", "DEF", "MID", "FWD", "ANY"):
            raise HTTPException(400, "position must be GK/DEF/MID/FWD/ANY")
        upd["position"] = pos
    if "description" in payload and payload["description"] is not None:
        desc = str(payload["description"])[:200]
        upd["description"] = desc
    if not upd:
        raise HTTPException(400, "No editable fields supplied")
    upd["updated_at"] = utcnow_iso()
    upd["updated_by"] = user["id"]
    await db.legend_cards.update_one({"id": card_id}, {"$set": upd})
    await db.audit_log.insert_one({
        "id": __import__("uuid").uuid4().hex, "user_id": user["id"], "email": user.get("email"),
        "action": "legend_card_update",
        "metadata": {"card_id": card_id, "old": {k: old.get(k) for k in upd}, "new": upd},
        "created_at": utcnow_iso(),
    })
    fresh = await db.legend_cards.find_one({"id": card_id}, {"_id": 0})
    return {"ok": True, "card": fresh}


@router.post("/cards/bulk-price")
async def admin_bulk_set_card_price(payload: dict, user: dict = Depends(a.require_admin)):
    """Bulk-update all cards of a tier to a new price.

    Body: `{tier: 1|2|3, price_coins?: int, price_usd_cents?: int}`
    Either `price_coins` (preferred) OR legacy `price_usd_cents` accepted.
    """
    try:
        tier = int(payload.get("tier"))
    except (TypeError, ValueError):
        raise HTTPException(400, "tier is required (1, 2, or 3)")
    if tier not in (1, 2, 3):
        raise HTTPException(400, "tier must be 1, 2 or 3")

    coins = payload.get("price_coins")
    cents = payload.get("price_usd_cents")
    if coins is None and cents is None:
        raise HTTPException(400, "price_coins (preferred) or price_usd_cents required")

    set_doc: dict = {"updated_at": utcnow_iso(), "updated_by": user["id"]}
    if coins is not None:
        try:
            c = int(coins)
        except (TypeError, ValueError):
            raise HTTPException(400, "price_coins must be an integer")
        if not (1 <= c <= 1_000_000):
            raise HTTPException(400, "price_coins must be 1-1,000,000")
        set_doc["price_coins"] = c
    if cents is not None:
        try:
            p = int(cents)
        except (TypeError, ValueError):
            raise HTTPException(400, "price_usd_cents must be an integer")
        if not (10 <= p <= 100000):
            raise HTTPException(400, "price_usd_cents must be 10-100000")
        set_doc["price_usd_cents"] = p

    db = get_db()
    res = await db.legend_cards.update_many({"tier": tier}, {"$set": set_doc})
    await db.audit_log.insert_one({
        "id": __import__("uuid").uuid4().hex, "user_id": user["id"], "email": user.get("email"),
        "action": "legend_card_bulk_price",
        "metadata": {"tier": tier, **{k: set_doc[k] for k in set_doc if k.startswith("price_")},
                     "matched": res.matched_count, "modified": res.modified_count},
        "created_at": utcnow_iso(),
    })
    return {"ok": True, "tier": tier, "modified": res.modified_count}



# ---------- PocketFi webhook failures + manual NGN credit ----------
@router.get("/webhooks/pocketfi/failures")
async def admin_list_pocketfi_failures(
    user: dict = Depends(a.require_admin), limit: int = 50,
):
    """List recent webhook deliveries that FAILED signature verification.
    Used to identify which header name + algorithm PocketFi is actually
    sending so we can tighten the verifier in code.
    """
    db = get_db()
    rows = await db.pocketfi_webhook_failures.find(
        {}, {"_id": 0},
    ).sort("received_at", -1).limit(max(1, min(limit, 200))).to_list(length=200)
    return {"failures": rows, "count": len(rows)}


@router.post("/wallet/credit-ngn")
async def admin_credit_ngn(payload: dict, user: dict = Depends(a.require_admin)):
    """Manually credit a user's NGN wallet for a stuck PocketFi deposit.

    Body:
      { user_id?: str, email?: str, amount_ngn: int (≥1),
        reference: str, reason: str (required), settlement_amount?: int }

    Idempotent on `reference` — re-running with the same reference returns
    the existing transaction (no double credit). Every call is audited.
    """
    db = get_db()
    amount = int(payload.get("amount_ngn") or 0)
    ref = (payload.get("reference") or "").strip()
    reason = (payload.get("reason") or "").strip()
    if amount < 1:
        raise HTTPException(400, "amount_ngn must be ≥ 1")
    if not ref:
        raise HTTPException(400, "reference is required (use the PocketFi transaction reference)")
    if not reason:
        raise HTTPException(400, "reason is required for audit (e.g. 'Webhook failed signature — verified deposit manually')")

    target_user = None
    if payload.get("user_id"):
        target_user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    elif payload.get("email"):
        target_user = await db.users.find_one(
            {"email": str(payload["email"]).strip().lower()}, {"_id": 0},
        )
    if not target_user:
        raise HTTPException(404, "User not found (provide user_id or email).")

    # Idempotency — refuse a second credit for the same reference.
    existing = await db.wallet_transactions.find_one({"reference": ref, "type": "deposit"})
    if existing:
        return {"ok": True, "duplicate": True, "transaction_id": existing.get("id"),
                "message": "This reference was already credited; no change."}

    now = utcnow_iso()
    # Compute USD equivalent so the mirror to wallet_balance_usd_cents lines
    # up with what the auto webhook would have done.
    currency_doc = await get_db().app_settings.find_one({"id": "currency"}, {"_id": 0}) or {}
    ngn_per_usd = float(currency_doc.get("ngn_per_usd") or 1400)
    usd_cents_credit = int((amount / ngn_per_usd) * 100)
    res = await db.user_wallets.update_one(
        {"user_id": target_user["id"]},
        {
            "$inc": {"balance_ngn": amount, "total_deposited": amount},
            "$set": {"updated_at": now},
        },
        upsert=True,
    )
    if res.upserted_id:
        await db.user_wallets.update_one(
            {"_id": res.upserted_id},
            {"$set": {"id": __import__("uuid").uuid4().hex, "user_id": target_user["id"],
                      "total_won": 0, "total_spent": 0, "kyc_verified": False, "bank_account": None}},
        )
    if usd_cents_credit > 0:
        await db.users.update_one(
            {"id": target_user["id"]},
            {"$inc": {"wallet_balance_usd_cents": usd_cents_credit}},
        )
    wallet = await db.user_wallets.find_one({"user_id": target_user["id"]}, {"_id": 0})
    new_balance = (wallet or {}).get("balance_ngn", amount)

    tx_id = __import__("uuid").uuid4().hex
    await db.wallet_transactions.insert_one({
        "id": tx_id, "user_id": target_user["id"], "type": "deposit",
        "amount_ngn": amount, "balance_after": new_balance,
        "reference": ref, "provider": "manual_admin",
        "gross_amount": payload.get("settlement_amount") or amount,
        "fee": 0, "description": f"Manual credit by admin: {reason}",
        "created_at": now,
    })
    # Mark the matching pending deposit (if any) as credited
    await db.ngn_deposits.update_one(
        {"payment_reference": ref, "status": "pending"},
        {"$set": {"status": "credited", "credited_amount_ngn": amount,
                  "transaction_reference": ref, "credited_at": now,
                  "credited_by": user["id"], "credited_reason": reason}},
    )
    await db.audit_log.insert_one({
        "id": __import__("uuid").uuid4().hex, "user_id": user["id"], "email": user.get("email"),
        "action": "wallet_credit_ngn_manual",
        "metadata": {"target_user_id": target_user["id"], "target_email": target_user.get("email"),
                     "amount_ngn": amount, "reference": ref, "reason": reason,
                     "new_balance_ngn": new_balance, "transaction_id": tx_id},
        "created_at": now,
    })
    return {"ok": True, "transaction_id": tx_id, "user_id": target_user["id"],
            "email": target_user.get("email"),
            "amount_credited_ngn": amount, "new_balance_ngn": new_balance}


@router.post("/wallet/backfill-usd")
async def admin_backfill_usd_wallet(payload: dict, user: dict = Depends(a.require_admin)):
    """One-time migration: convert every user's existing `balance_ngn` into a
    `users.wallet_balance_usd_cents` credit at the current exchange rate.

    Useful AFTER deploying the NGN→USD mirror so users who deposited before
    the fix get their USD spendable balance topped up.

    Body: { dry_run: bool, user_id?: str }
      - dry_run=true returns the diff without writing
      - user_id (optional) restricts to a single user; omit to backfill all
    """
    db = get_db()
    dry = bool(payload.get("dry_run", True))
    currency_doc = await db.app_settings.find_one({"id": "currency"}, {"_id": 0}) or {}
    ngn_per_usd = float(currency_doc.get("ngn_per_usd") or 1400)

    q = {}
    if payload.get("user_id"):
        q["user_id"] = payload["user_id"]
    wallets = await db.user_wallets.find(q, {"_id": 0}).to_list(length=10000)
    plan = []
    for w in wallets:
        ngn = int(w.get("balance_ngn") or 0)
        if ngn <= 0:
            continue
        target_cents = int((ngn / ngn_per_usd) * 100)
        # Read the user's current USD balance so we only top up the delta
        udoc = await db.users.find_one({"id": w["user_id"]}, {"_id": 0, "wallet_balance_usd_cents": 1}) or {}
        existing = int(udoc.get("wallet_balance_usd_cents") or 0)
        delta = max(0, target_cents - existing)
        if delta <= 0:
            continue
        plan.append({"user_id": w["user_id"], "ngn": ngn,
                     "existing_usd_cents": existing,
                     "target_usd_cents": target_cents,
                     "delta_usd_cents": delta})
    if not dry:
        for row in plan:
            await db.users.update_one(
                {"id": row["user_id"]},
                {"$inc": {"wallet_balance_usd_cents": row["delta_usd_cents"]}},
            )
        await db.audit_log.insert_one({
            "id": __import__("uuid").uuid4().hex, "user_id": user["id"], "email": user.get("email"),
            "action": "wallet_backfill_usd",
            "metadata": {"users_updated": len(plan), "ngn_per_usd": ngn_per_usd},
            "created_at": utcnow_iso(),
        })
    return {"ok": True, "dry_run": dry, "ngn_per_usd": ngn_per_usd,
            "users_affected": len(plan), "plan": plan[:50]}



@router.post("/cleanup/wc-duplicates")
async def cleanup_wc_duplicates(admin: dict = Depends(a.require_admin)):
    """One-shot: remove every StatPal/api-sports match whose home+away+date
    collides with an existing Sportmonks WC2026 fixture. Fixes the "match
    appears, then disappears, then appears" flicker the user saw on the
    football tab — root cause was multiple providers writing the same fixture
    under different IDs."""
    db = get_db()
    wc_matches = await db.matches.find(
        {"is_world_cup": True},
        {"_id": 0, "home_team_name": 1, "away_team_name": 1, "scheduled_at": 1},
    ).to_list(length=1000)
    removed = 0
    for wc in wc_matches:
        day_prefix = (wc.get("scheduled_at") or "")[:10]
        if not day_prefix:
            continue
        res = await db.matches.delete_many({
            "is_world_cup": {"$ne": True},
            "home_team_name": wc["home_team_name"],
            "away_team_name": wc["away_team_name"],
            "scheduled_at": {"$regex": f"^{day_prefix}"},
        })
        removed += res.deleted_count
    await db.audit_log.insert_one({
        "user_id": admin["id"], "email": admin.get("email"),
        "action": "cleanup_wc_duplicates",
        "metadata": {"removed": removed, "wc_count": len(wc_matches)},
        "created_at": utcnow_iso(),
    })
    return {"ok": True, "removed": removed, "wc_count": len(wc_matches)}



# ─────────────────────────────────────────────────────────────────────────
# Admin: manual card grants + coin grants
# ─────────────────────────────────────────────────────────────────────────
class CardGrantIn(BaseModel):
    user_id: str
    card_id: Optional[str] = None  # if omitted, server picks a random card of `tier`
    tier: Optional[int] = None     # 1=Legendary, 2=Elite, 3=Star (required if card_id omitted)
    quantity: int = 1
    note: Optional[str] = None


@router.post("/cards/grant")
async def admin_grant_card(body: CardGrantIn, admin: dict = Depends(a.require_admin)):
    """Manually grant a Legend Card to a user. Use this as a replacement for
    the (now-disabled) automatic free-drop mechanic — e.g. for tournament
    winners, support refunds, or VIP gifts.

    Either `card_id` OR `tier` must be supplied. With `tier` and no `card_id`,
    a random active card of that tier is picked.
    """
    if body.quantity < 1 or body.quantity > 50:
        raise HTTPException(status_code=400, detail="quantity must be 1..50")
    db = get_db()
    target = await db.users.find_one({"id": body.user_id}, {"_id": 0, "id": 1, "email": 1, "display_name": 1})
    if not target:
        raise HTTPException(status_code=404, detail="user not found")

    card = None
    if body.card_id:
        card = await db.legend_cards.find_one({"id": body.card_id}, {"_id": 0})
        if not card:
            raise HTTPException(status_code=404, detail="card not found")
    elif body.tier in (1, 2, 3):
        import random
        pool = await db.legend_cards.find(
            {"tier": body.tier, "is_active": {"$ne": False}}, {"_id": 0},
        ).to_list(length=500)
        if not pool:
            raise HTTPException(status_code=404, detail=f"no active cards in tier {body.tier}")
        card = random.choice(pool)
    else:
        raise HTTPException(status_code=400, detail="provide card_id OR a valid tier (1, 2, or 3)")

    uses_granted = (card.get("uses_granted") or 1) * body.quantity
    now_iso = utcnow_iso()
    existing = await db.user_cards.find_one(
        {"user_id": body.user_id, "card_id": card["id"]}, {"_id": 0},
    )
    if existing:
        await db.user_cards.update_one(
            {"id": existing["id"]},
            {"$inc": {"uses_remaining": uses_granted, "uses_left": uses_granted},
             "$set": {"last_admin_grant_at": now_iso}},
        )
        uc_id = existing["id"]
    else:
        uc_id = a.new_session_token.__module__  # placeholder; replaced below
        from models import new_id as _new_id
        uc_id = _new_id()
        await db.user_cards.insert_one({
            "id": uc_id, "user_id": body.user_id, "card_id": card["id"],
            "uses_remaining": uses_granted, "uses_left": uses_granted,
            "obtained_via": "admin_grant",
            "created_at": now_iso, "last_admin_grant_at": now_iso,
        })

    await db.audit_log.insert_one({
        "user_id": admin["id"], "email": admin.get("email"),
        "action": "admin_card_grant",
        "metadata": {
            "target_user_id": body.user_id,
            "target_email": target.get("email"),
            "card_id": card["id"],
            "card_name": card.get("name"),
            "tier": card.get("tier"),
            "quantity": body.quantity,
            "uses_granted": uses_granted,
            "note": body.note,
        },
        "created_at": now_iso,
    })

    return {
        "ok": True,
        "user_card_id": uc_id,
        "card": {"id": card["id"], "name": card.get("name"), "tier": card.get("tier")},
        "uses_granted": uses_granted,
        "target": target,
    }


class CoinGrantIn(BaseModel):
    user_id: str
    coins: int
    note: Optional[str] = None


@router.post("/coins/grant")
async def admin_grant_coins(body: CoinGrantIn, admin: dict = Depends(a.require_admin)):
    """Credit (or debit, with a negative `coins`) the user's coin balance.

    Audit logged. Use for refunds, support adjustments, or seeding test users.
    """
    if body.coins == 0:
        raise HTTPException(status_code=400, detail="coins must be non-zero")
    db = get_db()
    target = await db.users.find_one({"id": body.user_id}, {"_id": 0, "id": 1, "email": 1, "coins": 1})
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    if body.coins < 0 and (target.get("coins") or 0) + body.coins < 0:
        raise HTTPException(status_code=400, detail="would result in negative balance")
    await db.users.update_one({"id": body.user_id}, {"$inc": {"coins": body.coins}})
    fresh = await db.users.find_one({"id": body.user_id}, {"_id": 0, "coins": 1})
    await db.audit_log.insert_one({
        "user_id": admin["id"], "email": admin.get("email"),
        "action": "admin_coins_grant",
        "metadata": {
            "target_user_id": body.user_id,
            "target_email": target.get("email"),
            "delta_coins": body.coins,
            "new_balance": int((fresh or {}).get("coins") or 0),
            "note": body.note,
        },
        "created_at": utcnow_iso(),
    })
    return {"ok": True, "coins": int((fresh or {}).get("coins") or 0), "delta": body.coins}


@router.get("/users/search")
async def admin_search_users(q: str = "", limit: int = 20, _: dict = Depends(a.require_admin)):
    """Lightweight user search by email/display_name for the admin grant UI."""
    db = get_db()
    if not q or len(q) < 2:
        return {"users": []}
    rx = {"$regex": q, "$options": "i"}
    users = await db.users.find(
        {"$or": [{"email": rx}, {"display_name": rx}]},
        {"_id": 0, "id": 1, "email": 1, "display_name": 1, "country_code": 1,
         "coins": 1, "is_premium": 1},
    ).limit(limit).to_list(length=limit)
    return {"users": users}
