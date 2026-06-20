"""🛑 Service Controls — kill-switches for Fantasy and Predictions.

The admin can disable either feature with a public-facing reason. While
disabled:
  - All write endpoints for that feature return HTTP 423 Locked with the
    reason so the frontend can render a clean "Service paused" state.
  - The background settler loop skips that feature so points freeze.
  - The Fantasy / Predictions PAGES render only the shutdown notice (the
    Leaderboards are explicitly NOT gated and keep showing historical
    standings).

Storage: a single `service_controls` collection with two docs:
  - {id: "fantasy",     enabled, shutdown_reason, updated_at, updated_by}
  - {id: "predictions", enabled, shutdown_reason, updated_at, updated_by}
"""
from __future__ import annotations
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import auth as a
from db import get_db, utcnow_iso
from models import new_id


ServiceKind = Literal["fantasy", "predictions"]
_VALID_KINDS = ("fantasy", "predictions")


# ─── Public surface ───────────────────────────────────────────────────
router = APIRouter(prefix="/api/services", tags=["services"])

# ─── Admin surface ────────────────────────────────────────────────────
admin_router = APIRouter(prefix="/api/admin/services", tags=["admin-services"])


async def _get_doc(kind: str) -> dict:
    """Load (or auto-seed) the control doc for `kind`."""
    if kind not in _VALID_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown service: {kind}")
    db = get_db()
    doc = await db.service_controls.find_one({"id": kind}, {"_id": 0})
    if not doc:
        doc = {
            "id": kind,
            "enabled": True,
            "shutdown_reason": "",
            "updated_at": utcnow_iso(),
            "updated_by": None,
        }
        await db.service_controls.insert_one(doc)
    return doc


async def is_enabled(kind: str) -> bool:
    """Cheap read used by route guards. Defaults to enabled if the doc is
    missing so a fresh deployment doesn't lock itself out."""
    db = get_db()
    doc = await db.service_controls.find_one({"id": kind}, {"_id": 0, "enabled": 1})
    return bool(doc.get("enabled", True)) if doc else True


async def ensure_enabled(kind: str) -> None:
    """Route-level guard. Raises 423 LOCKED with the admin-set reason
    when the service is disabled."""
    db = get_db()
    doc = await db.service_controls.find_one({"id": kind}, {"_id": 0})
    if doc and not doc.get("enabled", True):
        reason = doc.get("shutdown_reason") or f"{kind.title()} is temporarily paused by an admin."
        raise HTTPException(status_code=423, detail={
            "code": "service_paused",
            "service": kind,
            "reason": reason,
        })


# ─── Public endpoints (no auth) ───────────────────────────────────────
@router.get("/status")
async def services_status():
    """Public status — used by the frontend gate. Returns BOTH services so
    the SPA can render banners + page-level shutdown screens off one fetch."""
    db = get_db()
    docs = await db.service_controls.find(
        {"id": {"$in": list(_VALID_KINDS)}}, {"_id": 0},
    ).to_list(length=10)
    by_id = {d["id"]: d for d in docs}
    out = {}
    for k in _VALID_KINDS:
        d = by_id.get(k) or {"id": k, "enabled": True, "shutdown_reason": "", "updated_at": None}
        out[k] = {
            "enabled": bool(d.get("enabled", True)),
            "shutdown_reason": d.get("shutdown_reason") or "",
            "updated_at": d.get("updated_at"),
        }
    return out


# ─── Admin endpoints ──────────────────────────────────────────────────
@admin_router.get("")
async def admin_list_services(admin: dict = Depends(a.require_admin)):
    """Admin view — same as public status plus `updated_by`."""
    db = get_db()
    docs = await db.service_controls.find(
        {"id": {"$in": list(_VALID_KINDS)}}, {"_id": 0},
    ).to_list(length=10)
    by_id = {d["id"]: d for d in docs}
    out = []
    for k in _VALID_KINDS:
        d = by_id.get(k) or await _get_doc(k)
        out.append(d)
    return {"services": out}


class ServicePatch(BaseModel):
    enabled: bool
    shutdown_reason: Optional[str] = Field(default="", max_length=500)


@admin_router.patch("/{kind}")
async def admin_update_service(
    kind: ServiceKind,
    body: ServicePatch,
    admin: dict = Depends(a.require_admin),
):
    """Flip a service on/off and set the public-facing reason. Audit-logged."""
    if kind not in _VALID_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown service: {kind}")
    db = get_db()
    old = await _get_doc(kind)
    new_doc = {
        "id": kind,
        "enabled": bool(body.enabled),
        "shutdown_reason": (body.shutdown_reason or "").strip(),
        "updated_at": utcnow_iso(),
        "updated_by": admin.get("email"),
    }
    await db.service_controls.update_one(
        {"id": kind}, {"$set": new_doc}, upsert=True,
    )
    await db.audit_log.insert_one({
        "id": new_id(),
        "user_id": admin["id"],
        "email": admin.get("email"),
        "action": "service_control_update",
        "metadata": {
            "service": kind,
            "old": {"enabled": old.get("enabled"), "shutdown_reason": old.get("shutdown_reason", "")},
            "new": {"enabled": new_doc["enabled"], "shutdown_reason": new_doc["shutdown_reason"]},
        },
        "created_at": utcnow_iso(),
    })
    return {"ok": True, "service": new_doc}
