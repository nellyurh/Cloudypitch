"""Legend Card usage enforcement.
Scopes per game:
  match: 2 cards max
  group: 4 cards max
  round: 5 cards max (Final-round may bump to 10 via override)
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import auth as a
from db import get_db
from models import new_id

router = APIRouter(prefix="/api/cards", tags=["cards"])


SCOPE_CAPS = {
    "match": 2,
    "group": 4,
    "round": 5,  # Round of 16/Quarters/Semis. Override for Final via SPECIAL_CAPS.
}

# Override caps for specific scope_ids (e.g., "round:final" gets 10 cards)
SPECIAL_CAPS = {
    "round:final": 10,
}


class UseCardBody(BaseModel):
    card_id: str
    scope: str = Field(pattern="^(match|group|round)$")
    scope_id: str  # match.id / group letter / round name


def _cap_for(scope: str, scope_id: str) -> int:
    key = f"{scope}:{(scope_id or '').lower()}"
    if key in SPECIAL_CAPS:
        return SPECIAL_CAPS[key]
    return SCOPE_CAPS.get(scope, 0)


@router.get("/usage")
async def usage(scope: str, scope_id: str, user: dict = Depends(a.get_current_user)):
    """How many cards has the current user already used in this scope?"""
    if scope not in SCOPE_CAPS:
        raise HTTPException(status_code=400, detail="Invalid scope")
    db = get_db()
    count = await db.card_usages.count_documents({
        "user_id": user["id"], "scope": scope, "scope_id": scope_id
    })
    cap = _cap_for(scope, scope_id)
    used = await db.card_usages.find(
        {"user_id": user["id"], "scope": scope, "scope_id": scope_id},
        {"_id": 0}
    ).to_list(length=cap)
    return {
        "scope": scope, "scope_id": scope_id,
        "count": count, "cap": cap, "remaining": max(0, cap - count),
        "used": used,
    }


@router.post("/use")
async def use_card(body: UseCardBody, user: dict = Depends(a.get_current_user)):
    """Apply one of the user's owned cards to a scope (match/group/round).
    Enforces per-scope cap and that the user actually owns the card."""
    db = get_db()
    cap = _cap_for(body.scope, body.scope_id)
    if cap <= 0:
        raise HTTPException(status_code=400, detail="Invalid scope")

    # Verify ownership
    owned = await db.user_cards.find_one({"user_id": user["id"], "card_id": body.card_id})
    if not owned:
        raise HTTPException(status_code=403, detail="You don't own this card")

    # Already used (idempotency)
    existing = await db.card_usages.find_one({
        "user_id": user["id"], "card_id": body.card_id,
        "scope": body.scope, "scope_id": body.scope_id,
    })
    if existing:
        return {"ok": True, "already_used": True, "usage": {**existing, "_id": None}}

    # Cap check
    current = await db.card_usages.count_documents({
        "user_id": user["id"], "scope": body.scope, "scope_id": body.scope_id,
    })
    if current >= cap:
        raise HTTPException(
            status_code=403,
            detail=f"Cap reached: only {cap} cards allowed per {body.scope} (used {current})",
        )

    # Decrement uses_left if tracked on user_cards (otherwise just record)
    doc = {
        "id": new_id(),
        "user_id": user["id"],
        "card_id": body.card_id,
        "user_card_id": owned.get("id"),
        "scope": body.scope,
        "scope_id": body.scope_id,
        "used_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.card_usages.insert_one(doc)
    # Optional: decrement uses_left on the user_cards row
    if isinstance(owned.get("uses_left"), int) and owned["uses_left"] > 0:
        await db.user_cards.update_one(
            {"id": owned["id"]},
            {"$inc": {"uses_left": -1}, "$set": {"last_used_at": doc["used_at"]}},
        )
    doc.pop("_id", None)
    return {"ok": True, "usage": doc, "remaining": max(0, cap - (current + 1))}


@router.get("/usage/me")
async def my_usage(user: dict = Depends(a.get_current_user)):
    """All scope usages for the current user — grouped by scope."""
    db = get_db()
    rows = await db.card_usages.find({"user_id": user["id"]}, {"_id": 0}).sort("used_at", -1).to_list(length=500)
    grouped: dict[str, dict[str, list]] = {}
    for r in rows:
        grouped.setdefault(r["scope"], {}).setdefault(r["scope_id"], []).append(r)
    return {"usages": rows, "grouped": grouped, "caps": SCOPE_CAPS, "special_caps": SPECIAL_CAPS}
