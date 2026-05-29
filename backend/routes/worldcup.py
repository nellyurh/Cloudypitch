"""World Cup 2026 hub routes."""
from fastapi import APIRouter
from datetime import datetime, timezone
from db import get_db
from wc_legends import PAST_TOURNAMENTS

router = APIRouter(prefix="/api/worldcup", tags=["worldcup"])

WC2026_START = "2026-06-11T18:00:00+00:00"
WC2026_WINDOW_FROM = "2026-06-01T00:00:00+00:00"
WC2026_WINDOW_TO   = "2026-07-31T00:00:00+00:00"


def _wc2026_filter() -> dict:
    """Match clause: strictly fixtures inside the WC2026 window OR explicitly tagged."""
    return {
        "$or": [
            {"is_world_cup": True, "scheduled_at": {"$gte": WC2026_WINDOW_FROM, "$lte": WC2026_WINDOW_TO}},
            {"sportmonks_league_id": 732, "scheduled_at": {"$gte": WC2026_WINDOW_FROM, "$lte": WC2026_WINDOW_TO}},
            {"competition_id": "wc-2026", "scheduled_at": {"$gte": WC2026_WINDOW_FROM, "$lte": WC2026_WINDOW_TO}},
        ],
    }


@router.get("")
async def worldcup_hub():
    db = get_db()
    groups = await db.wc2026_groups.find({}, {"_id": 0}).sort("group", 1).to_list(length=12)
    # WC2026 fixtures ONLY (no past WCs)
    matches = await db.matches.find(
        _wc2026_filter(),
        {"_id": 0, "raw_data": 0},
    ).sort("scheduled_at", 1).to_list(length=200)
    pool = await db.prize_pools.find_one({"id": "pool-wc2026-fantasy"}, {"_id": 0})
    comp = await db.fantasy_competitions.find_one({"id": "fantasy-wc2026"}, {"_id": 0})
    return {
        "starts_at": WC2026_START,
        "groups": groups,
        "matches": matches,
        "prize_pool": pool,
        "competition": comp,
    }


@router.get("/past")
async def past_tournaments():
    """Hand-curated archive of past WCs with highlights tied to Legend Cards.
    Frontend renders this as the 'Past Tournaments' tab on the WC Hub."""
    db = get_db()
    # Cross-reference each highlight's card_name → live legend_cards.id so UI can deep-link
    out = []
    for t in PAST_TOURNAMENTS:
        highlights = []
        for h in t["highlights"]:
            card_doc = None
            if h.get("card"):
                # Match either exact card name OR card name CONTAINS the highlight's "card" token
                # (cards are named like "Pelé Spirit", "Maradona Hand" — we pass "Pele"/"Maradona")
                token = h["card"].split()[0]  # first word, e.g. "Lionel"
                last = h["card"].split()[-1]  # last word, e.g. "Messi"
                card_doc = await db.legend_cards.find_one(
                    {"$or": [
                        {"name": {"$regex": f"^{h['card']}$", "$options": "i"}},
                        {"name": {"$regex": last, "$options": "i"}},
                        {"name": {"$regex": token, "$options": "i"}},
                    ]},
                    {"_id": 0, "id": 1, "name": 1, "tier": 1, "price_usd_cents": 1, "country_code": 1},
                )
            highlights.append({**h, "card_doc": card_doc})
        out.append({**t, "highlights": highlights})
    return {"tournaments": out}



@router.get("/groups")
async def list_groups():
    db = get_db()
    groups = await db.wc2026_groups.find({}, {"_id": 0}).sort("group", 1).to_list(length=12)
    return {"groups": groups}


@router.get("/bracket")
async def bracket():
    # Knockout bracket (placeholder structure for the 16-team knockout)
    return {
        "rounds": [
            {"name": "Round of 32", "matches": []},
            {"name": "Round of 16", "matches": []},
            {"name": "Quarterfinals", "matches": []},
            {"name": "Semifinals", "matches": []},
            {"name": "Final", "matches": []},
        ],
    }
