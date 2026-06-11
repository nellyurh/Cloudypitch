"""World Cup 2026 hub routes."""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone

from db import get_db
from models import new_id
import auth as a
from pydantic import BaseModel, Field
from wc_legends import PAST_TOURNAMENTS

router = APIRouter(prefix="/api/worldcup", tags=["worldcup"])

WC2026_START = "2026-06-11T19:00:00+00:00"  # 8 PM Lagos kickoff (UTC+1)
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
    # Build a team→group lookup so the FE can group fixtures by Group A/B/C…
    team_to_group: dict[str, str] = {}
    # Common aliases between fixture provider names and our group seed names
    ALIASES = {
        "korea republic": ["south korea", "republic of korea"],
        "south korea": ["korea republic", "republic of korea"],
        "ir iran": ["iran"],
        "iran": ["ir iran"],
        "usa": ["united states"],
        "united states": ["usa", "us"],
        "cote d'ivoire": ["ivory coast", "côte d'ivoire"],
        "ivory coast": ["cote d'ivoire", "côte d'ivoire"],
        "czech republic": ["czechia"],
        "czechia": ["czech republic"],
        "türkiye": ["turkey"],
        "turkey": ["türkiye"],
    }
    for g in groups:
        for t in (g.get("teams") or []):
            key = t.strip().lower()
            team_to_group[key] = g["group"]
            for alias in ALIASES.get(key, []):
                team_to_group[alias] = g["group"]

    # WC2026 fixtures ONLY (no past WCs)
    matches = await db.matches.find(
        _wc2026_filter(),
        {"_id": 0, "raw_data": 0},
    ).sort("scheduled_at", 1).to_list(length=200)

    # Annotate each match with group + round + matchday so the FE can render
    # the Sofascore-style "By date / By round / By group" toggles purely client-side.
    for m in matches:
        h = (m.get("home_team_name") or "").strip().lower()
        a = (m.get("away_team_name") or "").strip().lower()
        g = team_to_group.get(h) or team_to_group.get(a)
        m["group"] = g
        # Round/matchday — derived from kickoff date relative to tournament window.
        # Group stage runs Jun 11 – Jun 27 → 3 matchdays.
        sched = (m.get("scheduled_at") or "")[:10]
        if sched and sched <= "2026-06-17":
            m["round"] = "Group · Matchday 1"
            m["matchday"] = 1
        elif sched and sched <= "2026-06-22":
            m["round"] = "Group · Matchday 2"
            m["matchday"] = 2
        elif sched and sched <= "2026-06-27":
            m["round"] = "Group · Matchday 3"
            m["matchday"] = 3
        elif sched and sched <= "2026-07-03":
            m["round"] = "Round of 32"
            m["matchday"] = 32
        elif sched and sched <= "2026-07-07":
            m["round"] = "Round of 16"
            m["matchday"] = 16
        elif sched and sched <= "2026-07-11":
            m["round"] = "Quarter-final"
            m["matchday"] = 8
        elif sched and sched <= "2026-07-15":
            m["round"] = "Semi-final"
            m["matchday"] = 4
        else:
            m["round"] = "Final"
            m["matchday"] = 2

    pool = await db.prize_pools.find_one({"id": "pool-wc2026-fantasy"}, {"_id": 0})
    comp = await db.fantasy_competitions.find_one({"id": "fantasy-wc2026"}, {"_id": 0})
    # WC news (admin-curated)
    news = await db.wc_news.find({"published": True}, {"_id": 0}).sort("created_at", -1).to_list(length=20)
    return {
        "starts_at": WC2026_START,
        "groups": groups,
        "matches": matches,
        "prize_pool": pool,
        "competition": comp,
        "news": news,
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


@router.get("/standings")
async def wc_standings():
    """Live FIFA World Cup 2026 standings sourced from Sportmonks (league 732).

    Sportmonks' raw response groups by qualification region, not the FIFA-draw
    A–L bracket — so we use our local `wc2026_groups` doc as the authoritative
    group layout and overlay live W/D/L/GF/GA/PTS rows from Sportmonks when a
    team name matches. Pre-tournament every value is 0 (correct).

    Background ingestion refreshes the underlying rows every hour via
    `sync_sportmonks_standings_live(732)` (season 26618).
    """
    db = get_db()
    sm_rows = await db.standings.find({"league_id": "sm-l-732"}, {"_id": 0}).to_list(length=64)
    local_groups = await db.wc2026_groups.find({}, {"_id": 0}).sort("group", 1).to_list(length=12)
    if not local_groups:
        return {"groups": [], "source": "none", "count": 0}

    # Tolerant name lookup — collapse whitespace and case, plus common aliases.
    ALIASES = {
        "korea republic": "south korea",
        "south korea": "south korea",
        "korea dpr": "north korea",
        "côte d'ivoire": "ivory coast",
        "cote d'ivoire": "ivory coast",
        "cape verde islands": "cape verde",
        "congo dr": "democratic republic of the congo",
        "iran": "iran",
        "iran ir": "iran",
        "usa": "united states",
    }
    def norm(s: str) -> str:
        s = (s or "").strip().lower()
        return ALIASES.get(s, s)

    by_team = {norm(r.get("team_name")): r for r in sm_rows if r.get("team_name")}

    out_groups = []
    for g in local_groups:
        rows = []
        for t in (g.get("teams") or []):
            sm = by_team.get(norm(t))
            rows.append({
                "team": t,
                "team_logo": sm.get("team_logo") if sm else None,
                "P": (sm or {}).get("MP", (sm or {}).get("played", 0)) or 0,
                "W": (sm or {}).get("W", (sm or {}).get("won", 0)) or 0,
                "D": (sm or {}).get("D", (sm or {}).get("drawn", 0)) or 0,
                "L": (sm or {}).get("L", (sm or {}).get("lost", 0)) or 0,
                "GF": (sm or {}).get("GF", (sm or {}).get("goals_for", 0)) or 0,
                "GA": (sm or {}).get("GA", (sm or {}).get("goals_against", 0)) or 0,
                "GD": (sm or {}).get("goal_diff", 0) or 0,
                "PTS": (sm or {}).get("points", 0) or 0,
                "form": (sm or {}).get("form", []),
                "position": (sm or {}).get("position", 0) or 0,
            })
        # Sort by PTS desc, then GD, then GF (FIFA tie-break).
        rows.sort(key=lambda r: (-r["PTS"], -(r["GF"] - r["GA"]), -r["GF"]))
        out_groups.append({"group": g["group"], "rows": rows})

    return {
        "groups": out_groups,
        "source": "sportmonks" if sm_rows else "local",
        "count": len(sm_rows),
        "updated_at": (sm_rows[0].get("updated_at") if sm_rows else None),
    }


@router.get("/h2h")
async def wc_head_to_head(team_a: str, team_b: str, limit: int = 10):
    """Head-to-head fixtures between two WC teams. Pulls finished matches from
    the `matches` collection where both teams appear in any order.
    """
    db = get_db()
    rows = await db.matches.find({
        "$or": [
            {"home_team_name": team_a, "away_team_name": team_b},
            {"home_team_name": team_b, "away_team_name": team_a},
        ],
    }, {"_id": 0}).sort("scheduled_at", -1).to_list(length=limit)
    a_wins = b_wins = draws = 0
    for m in rows:
        hs, as_ = m.get("home_score"), m.get("away_score")
        if hs is None or as_ is None: continue
        if m["home_team_name"] == team_a:
            if hs > as_: a_wins += 1
            elif hs < as_: b_wins += 1
            else: draws += 1
        else:
            if hs > as_: b_wins += 1
            elif hs < as_: a_wins += 1
            else: draws += 1
    return {
        "team_a": team_a, "team_b": team_b,
        "matches": rows,
        "summary": {"a_wins": a_wins, "b_wins": b_wins, "draws": draws, "total": len(rows)},
    }


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


# ───────────────────────────── WC News (admin curated) ─────────────────────────────


class WcNewsIn(BaseModel):
    title: str = Field(min_length=2, max_length=140)
    summary: str = Field(default="", max_length=600)
    image_url: str = Field(default="", max_length=1024)
    source_name: str = Field(default="", max_length=60)
    source_url: str = Field(default="", max_length=600)
    published: bool = True


@router.get("/news")
async def list_wc_news():
    """Public WC news feed (admin curated). Returns latest 30 published items."""
    db = get_db()
    items = await db.wc_news.find({"published": True}, {"_id": 0}).sort("created_at", -1).to_list(length=30)
    return {"news": items}


@router.post("/news")
async def create_wc_news(body: WcNewsIn, user: dict = Depends(a.require_admin)):
    db = get_db()
    doc = body.model_dump()
    doc.update({
        "id": new_id(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user["id"],
    })
    await db.wc_news.insert_one(doc)
    doc.pop("_id", None)
    return {"item": doc}


@router.patch("/news/{news_id}")
async def update_wc_news(news_id: str, body: WcNewsIn, user: dict = Depends(a.require_admin)):
    db = get_db()
    res = await db.wc_news.update_one({"id": news_id}, {"$set": body.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="News item not found")
    return {"ok": True}


@router.delete("/news/{news_id}")
async def delete_wc_news(news_id: str, user: dict = Depends(a.require_admin)):
    db = get_db()
    res = await db.wc_news.delete_one({"id": news_id})
    return {"deleted": res.deleted_count}
