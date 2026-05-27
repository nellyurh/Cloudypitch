"""Legend cards catalog + my cards."""
from fastapi import APIRouter, Depends
from db import get_db
import auth as a

router = APIRouter(prefix="/api/cards", tags=["cards"])


@router.get("")
async def list_cards():
    db = get_db()
    cards = await db.legend_cards.find({}, {"_id": 0}).to_list(length=500)
    cards.sort(key=lambda c: (c["tier"], -c["price_ngn"]))
    return {"cards": cards, "tiers": {
        "1": {"name": "GOAT", "price_ngn": 2000, "color": "#A3E635"},
        "2": {"name": "Elite", "price_ngn": 1000, "color": "#0F6E56"},
        "3": {"name": "Star", "price_ngn": 500, "color": "#64748B"},
    }}


@router.get("/me")
async def my_cards(user: dict = Depends(a.get_current_user)):
    db = get_db()
    owned = await db.user_cards.find({"user_id": user["id"]}, {"_id": 0}).to_list(length=500)
    card_ids = [c["card_id"] for c in owned]
    cards = await db.legend_cards.find({"id": {"$in": card_ids}}, {"_id": 0}).to_list(length=500)
    by_id = {c["id"]: c for c in cards}
    out = []
    for o in owned:
        c = by_id.get(o["card_id"])
        if c:
            out.append({**o, "card": c})
    return {"owned": out, "count": len(out)}
