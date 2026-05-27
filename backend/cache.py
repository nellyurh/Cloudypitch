"""Tiny in-memory cache with TTL. For MVP — replace with Redis in prod."""
import time
from typing import Any

_store: dict[str, tuple[float, Any]] = {}


def cget(key: str):
    item = _store.get(key)
    if not item:
        return None
    expires_at, value = item
    if expires_at < time.time():
        _store.pop(key, None)
        return None
    return value


def cset(key: str, value: Any, ttl_sec: int):
    _store[key] = (time.time() + ttl_sec, value)


def cdel(key: str):
    _store.pop(key, None)
