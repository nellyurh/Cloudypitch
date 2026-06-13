"""Pydantic models + helpers for serialization."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional, Literal
from pydantic import BaseModel, EmailStr, Field, ConfigDict
import uuid


def new_id() -> str:
    return str(uuid.uuid4())


# ===== Auth =====
class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=64)
    country_code: Optional[str] = None
    referral_code: Optional[str] = None


class SigninIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: EmailStr
    display_name: str
    role: Literal["user", "admin"]
    country_code: Optional[str] = None
    locale: Optional[str] = None
    timezone: Optional[str] = None
    email_verified: bool = False
    is_active: bool = True
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None


# ===== Predictions =====
class PredictionIn(BaseModel):
    match_id: str
    home_score_predicted: int = Field(ge=0, le=30)
    away_score_predicted: int = Field(ge=0, le=30)


# ===== Fantasy =====
class FantasySquadPlayerIn(BaseModel):
    player_id: str
    position: Literal["GK", "DEF", "MID", "FWD"]
    is_starting: bool = True
    is_captain: bool = False
    is_vice: bool = False
    on_bench: bool = False
    price_paid: float = 0


class CardUseIn(BaseModel):
    """One card applied to one player. Mirrors the WC mini-game payload so
    main-squad cards can be targeted (and position-validated) the same way."""
    user_card_id: str
    target_player_id: str


class FantasySquadIn(BaseModel):
    competition_id: str = "fantasy-wc2026"
    game_id: Optional[str] = None
    squad_name: str = Field(min_length=2, max_length=40)
    mode: Literal["15", "20"] = "15"
    captain_id: Optional[str] = None
    vice_captain_id: Optional[str] = None
    formation: Optional[str] = "4-3-3"
    bench_ids: list[str] = Field(default_factory=list)
    bench_boost: bool = False
    players: list[FantasySquadPlayerIn] = Field(min_length=1, max_length=20)
    # Legacy flat list (kept for backward compat) — superseded by `applied_cards`.
    applied_card_ids: list[str] = Field(default_factory=list, max_length=5)
    # New: per-player card targeting. Each entry pins a card to ONE player.
    applied_cards: list[CardUseIn] = Field(default_factory=list, max_length=5)


def clean_doc(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    doc.pop("_id", None)
    doc.pop("password_hash", None)
    return doc


def public_user(user: dict | None) -> dict | None:
    if not user:
        return None
    return {
        "id": user.get("id"),
        "email": user.get("email"),
        "display_name": user.get("display_name"),
        "role": user.get("role", "user"),
        "country_code": user.get("country_code"),
        "locale": user.get("locale"),
        "timezone": user.get("timezone"),
        "email_verified": user.get("email_verified", False),
        "is_active": user.get("is_active", True),
        "is_premium": user.get("is_premium", False),
        "premium_until": user.get("premium_until"),
        "referral_code": user.get("referral_code"),
        "coins": int(user.get("coins") or 0),
        "wallet_balance_usd_cents": int(user.get("wallet_balance_usd_cents") or 0),
        "created_at": user.get("created_at"),
        "last_login_at": user.get("last_login_at"),
    }
