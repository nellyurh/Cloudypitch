"""Admin cleanup endpoints — one-off DB hygiene operations."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime as _dt, timedelta as _td

import auth as a
from db import get_db
from ingestion import _team_tokens

router = APIRouter(prefix="/api/admin/cleanup", tags=["admin-cleanup"])

# Provider preference: highest-priority survives; lower-priority duplicates are deleted.
PROVIDER_RANK = {"sportmonks": 100, "apisports": 50, "statpal": 30, "manual": 80}


def _rank(doc: dict) -> int:
    return PROVIDER_RANK.get(doc.get("primary_provider"), 0)


@router.post("/duplicate-matches")
async def cleanup_duplicate_matches(
    sport_slug: str = "football",
    dry_run: bool = True,
    window_hours: int = 24,
    admin: dict = Depends(a.require_admin),
):
    """Walk every match in `sport_slug`. For each, find candidates in the ±window
    where home/away team tokens overlap (in either order). Keep the doc with the
    highest provider rank (Sportmonks > Manual > API-Sports > StatPal); delete the
    rest.

    Returns a report. Pass `dry_run=false` to actually delete.
    """
    db = get_db()
    matches = await db.matches.find(
        {"sport_slug": sport_slug}, {"_id": 0},
    ).sort("scheduled_at", 1).to_list(length=20000)

    deletes: list[dict] = []
    keep_set: set[str] = set()
    seen_ids: set[str] = set()

    for i, m in enumerate(matches):
        if m["id"] in seen_ids:
            continue
        h_tok = _team_tokens(m.get("home_team_name") or "")
        a_tok = _team_tokens(m.get("away_team_name") or "")
        if not h_tok or not a_tok:
            continue
        try:
            d = _dt.fromisoformat((m.get("scheduled_at") or "").replace("Z", "+00:00"))
        except Exception:
            continue
        lo, hi = (d - _td(hours=window_hours)).isoformat(), (d + _td(hours=window_hours)).isoformat()
        # Candidate window: same sport, ±window
        cands = [
            c for c in matches
            if c["id"] != m["id"]
            and c["id"] not in seen_ids
            and (c.get("scheduled_at") or "") >= lo
            and (c.get("scheduled_at") or "") <= hi
        ]
        cluster = [m]
        for c in cands:
            ch = _team_tokens(c.get("home_team_name") or "")
            ca = _team_tokens(c.get("away_team_name") or "")
            if (h_tok & ch and a_tok & ca) or (h_tok & ca and a_tok & ch):
                cluster.append(c)
        if len(cluster) < 2:
            continue
        # Highest provider rank wins; ties broken by oldest created (more authoritative)
        cluster.sort(key=lambda x: (-_rank(x), x.get("created_at") or x.get("updated_at") or ""))
        winner, losers = cluster[0], cluster[1:]
        keep_set.add(winner["id"])
        for L in losers:
            deletes.append({
                "delete_id": L["id"],
                "delete_provider": L.get("primary_provider"),
                "kept_id": winner["id"],
                "kept_provider": winner.get("primary_provider"),
                "home": L.get("home_team_name"),
                "away": L.get("away_team_name"),
                "scheduled_at": L.get("scheduled_at"),
            })
            seen_ids.add(L["id"])
        seen_ids.add(winner["id"])

    if not dry_run and deletes:
        ids_to_delete = [d["delete_id"] for d in deletes]
        await db.matches.delete_many({"id": {"$in": ids_to_delete}})

    return {
        "dry_run": dry_run, "sport_slug": sport_slug,
        "total_matches_scanned": len(matches),
        "duplicates_found": len(deletes),
        "kept": len(keep_set),
        "sample": deletes[:20],
    }


@router.post("/duplicate-leagues")
async def cleanup_duplicate_leagues(
    dry_run: bool = True,
    admin: dict = Depends(a.require_admin),
):
    """Merge leagues with identical normalised (name, country, sport_slug) pairs.
    Keeps the one with `primary_provider == 'sportmonks'` (else highest rank);
    deletes the rest and reassigns their matches' `league_id` to the winner.
    """
    db = get_db()
    leagues = await db.leagues.find({}, {"_id": 0}).to_list(length=5000)

    def norm(name: str | None) -> str:
        if not name:
            return ""
        s = name.lower().strip()
        # Drop "Country: " prefix and the country itself if echoed
        for sep in (":", " - "):
            if sep in s:
                s = s.split(sep, 1)[-1].strip()
        return s

    groups: dict[tuple, list[dict]] = {}
    for lg in leagues:
        key = (norm(lg.get("name")), (lg.get("country") or "").lower(), lg.get("sport_slug") or "")
        groups.setdefault(key, []).append(lg)

    merge_ops: list[dict] = []
    for key, cluster in groups.items():
        if len(cluster) < 2:
            continue
        cluster.sort(key=lambda x: (-_rank(x), len(x.get("name") or "")))
        winner, losers = cluster[0], cluster[1:]
        for L in losers:
            n_matches = await db.matches.count_documents({"league_id": L["id"]})
            merge_ops.append({
                "delete_league_id": L["id"], "delete_name": L.get("name"),
                "kept_league_id": winner["id"], "kept_name": winner.get("name"),
                "country": L.get("country"), "matches_reassigned": n_matches,
            })
            if not dry_run:
                await db.matches.update_many(
                    {"league_id": L["id"]},
                    {"$set": {"league_id": winner["id"], "league_name": winner.get("name"), "league_logo": winner.get("logo_url") or L.get("logo_url") or ""}},
                )
                await db.leagues.delete_one({"id": L["id"]})

    return {
        "dry_run": dry_run,
        "total_leagues_scanned": len(leagues),
        "duplicate_clusters": sum(1 for v in groups.values() if len(v) > 1),
        "leagues_merged": len(merge_ops),
        "sample": merge_ops[:30],
    }
