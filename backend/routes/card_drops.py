"""Random card drop loop — gamification hook.

🚫 As of 2026-02-13 the AUTOMATIC free-drop mechanics are disabled by user
request. Both endpoints (`/check-drop` and `/daily-drop`) now return
`{dropped: false}` regardless of state. The action-counter / daily-action
upserts remain (cheap) so we can re-enable later if the meta needs it.

Admins can still grant cards to any user manually via
`POST /api/admin/cards/grant` (see `routes/admin.py`).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

import auth as a
from db import get_db
from models import new_id  # noqa: F401 — kept for re-enable path

router = APIRouter(prefix="/api/cards", tags=["cards:drops"])


def _yesterday_utc() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def log_user_action(user_id: str) -> None:
    """Idempotently record that `user_id` performed a qualifying action today.

    Kept as a no-op-free record so analytics + future re-enable work, but
    nothing automatically grants cards anymore.
    """
    if not user_id:
        return
    db = get_db()
    day = _today_utc()
    await db.user_daily_actions.update_one(
        {"user_id": user_id, "day": day},
        {"$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()},
         "$inc": {"actions": 1}},
        upsert=True,
    )


@router.post("/check-drop")
async def check_drop(user: dict = Depends(a.get_current_user)):
    """Free-drop mechanic DISABLED — always returns `{dropped: false}`.

    Admins can grant cards manually via `POST /api/admin/cards/grant`.
    """
    return {"dropped": False, "disabled": True, "reason": "free_drops_disabled"}


@router.post("/daily-drop")
async def daily_drop(user: dict = Depends(a.get_current_user)):
    """Daily free-drop mechanic DISABLED — always returns `{dropped: false}`."""
    return {"dropped": False, "disabled": True, "reason": "free_drops_disabled"}
