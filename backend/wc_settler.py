"""WC mini-game settlement engine.

Settles `wc_games` rows (status `closed`) by:
  1. Resolving the set of WC matches the game depended on.
  2. Verifying all those matches have finished (status in FT/AET/PEN).
  3. Walking every `wc_game_entries` row for the game, aggregating
     per-player stats from `match_events`/`match_lineups`, applying the
     shared fantasy_scoring engine, captain×2/vice×2, applied card boost,
     and the game's `points_multiplier`.
  4. Writing `points_scored` + `breakdown_by_player` on each entry,
     ranking entries, and flipping the game to status `settled`.

The settler is idempotent — entries already carrying a `settled_at` are
skipped; running again is a no-op for them.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from db import get_db, utcnow_iso
from fantasy_scoring import compute_player_points, aggregate_player_stats_from_events
from scoring import compute_card_boost

log = logging.getLogger("wc_settler")

FINISHED_STATUSES = {"FT", "AET", "PEN", "FT_PEN", "AWARDED"}

# How far either side of `closes_at` a group/round game's contributing
# matches can fall. Group matchday = ~24h window; round windows are wider.
WINDOW_HOURS = {
    "match": (1, 6),       # single kickoff
    "group": (2, 30),      # one matchday is ~24h
    "matchday": (2, 30),
    "round": (2, 96),      # whole round may span ~3-4 days
}


# ---------- match resolution ----------
async def _resolve_match_ids_for_game(db, g: dict) -> list[str]:
    """Return the list of `matches.id` values that contribute to this game."""
    gt = g.get("game_type")
    if gt == "match":
        return [g["match_id"]] if g.get("match_id") else []

    eligible_team_ids = list(g.get("eligible_team_ids") or [])
    if not eligible_team_ids:
        return []

    # Window: matches scheduled near the game's `closes_at`.
    try:
        closes = datetime.fromisoformat(g["closes_at"].replace("Z", "+00:00"))
    except Exception:
        return []
    pre_h, post_h = WINDOW_HOURS.get(gt, (2, 30))
    window_start = (closes - timedelta(hours=pre_h)).isoformat()
    window_end = (closes + timedelta(hours=post_h)).isoformat()

    q: dict = {
        "is_world_cup": True,
        "scheduled_at": {"$gte": window_start, "$lte": window_end},
    }
    if gt in ("group", "matchday"):
        # Both teams must be inside the eligible set (group internal matches).
        q["home_team_id"] = {"$in": eligible_team_ids}
        q["away_team_id"] = {"$in": eligible_team_ids}
    else:  # round
        # EITHER side in eligible set (round games span many teams).
        q["$or"] = [
            {"home_team_id": {"$in": eligible_team_ids}},
            {"away_team_id": {"$in": eligible_team_ids}},
        ]

    rows = await db.matches.find(q, {"_id": 0, "id": 1}).to_list(length=200)
    return [r["id"] for r in rows]


# ---------- single-game settlement ----------
async def settle_wc_game(game_id: str, *, force: bool = False) -> dict:
    """Settle one wc_game. Returns a summary dict.

    Skips silently (with reason) if:
      - game is already settled (unless force=True)
      - dependent matches are not all finished yet
    """
    db = get_db()
    g = await db.wc_games.find_one({"id": game_id}, {"_id": 0})
    if not g:
        return {"ok": False, "reason": "game_not_found"}
    if g.get("status") == "settled" and not force:
        return {"ok": False, "reason": "already_settled"}

    match_ids = await _resolve_match_ids_for_game(db, g)
    if not match_ids:
        return {"ok": False, "reason": "no_matches_resolved"}

    matches = await db.matches.find(
        {"id": {"$in": match_ids}},
        {"_id": 0, "id": 1, "home_team_id": 1, "away_team_id": 1,
         "home_score": 1, "away_score": 1, "status": 1, "scheduled_at": 1},
    ).to_list(length=200)
    if len(matches) != len(match_ids):
        log.warning(f"settle_wc_game({game_id}): only {len(matches)}/{len(match_ids)} matches found")

    unfinished = [m for m in matches if (m.get("status") or "").upper() not in FINISHED_STATUSES]
    if unfinished and not force:
        return {"ok": False, "reason": "matches_not_finished",
                "unfinished": [m["id"] for m in unfinished]}

    # Pre-load events + lineups for all involved matches
    finished_ids = [m["id"] for m in matches]
    events_by_match: dict[str, list[dict]] = {}
    lineups_by_match: dict[str, list[dict]] = {}
    if finished_ids:
        evs = await db.match_events.find(
            {"match_id": {"$in": finished_ids}}, {"_id": 0},
        ).to_list(length=20000)
        for e in evs:
            events_by_match.setdefault(e["match_id"], []).append(e)
        lns = await db.match_lineups.find(
            {"match_id": {"$in": finished_ids}}, {"_id": 0},
        ).to_list(length=20000)
        for ln_row in lns:
            lineups_by_match.setdefault(ln_row["match_id"], []).append(ln_row)

    # Clean-sheet map keyed by (match_id, team_id)
    cs_map: dict[tuple[str, str], bool] = {}
    for m in matches:
        h = int(m.get("home_score") or 0)
        a = int(m.get("away_score") or 0)
        if m.get("home_team_id"):
            cs_map[(m["id"], m["home_team_id"])] = (a == 0)
        if m.get("away_team_id"):
            cs_map[(m["id"], m["away_team_id"])] = (h == 0)

    points_mult = float(g.get("points_multiplier") or 1.0)

    entries = await db.wc_game_entries.find({"wc_game_id": game_id}, {"_id": 0}).to_list(length=20000)
    settled = 0
    skipped = 0
    for entry in entries:
        if entry.get("settled_at") and not force:
            skipped += 1
            continue

        # Resolve any cards used so we can apply per-player boosts.
        cards_by_target_player: dict[str, list[dict]] = {}
        for cu in entry.get("cards_used") or []:
            tgt_pid = cu.get("target_player_id")
            uc_id = cu.get("user_card_id")
            if not (tgt_pid and uc_id):
                continue
            uc = await db.user_cards.find_one({"id": uc_id, "user_id": entry["user_id"]}, {"_id": 0})
            if not uc:
                continue
            card = await db.legend_cards.find_one({"id": uc.get("card_id")}, {"_id": 0})
            if not card:
                continue
            cards_by_target_player.setdefault(tgt_pid, []).append(card)

        per_player_breakdown: list[dict] = []
        total_points = 0
        captain_played = False
        captain_id = entry.get("captain_player_id")
        vice_id = entry.get("vice_captain_player_id")

        for pick in entry.get("player_picks") or []:
            player_id = pick.get("player_id")
            position = (pick.get("position") or "MID").upper()
            if not player_id:
                continue
            player = await db.players.find_one({"id": player_id}, {"_id": 0})
            if not player:
                per_player_breakdown.append({
                    "player_id": player_id, "position": position,
                    "points": 0, "reason": "player_not_found",
                })
                continue
            name = player.get("name") or ""
            team_id = player.get("team_id")

            agg = {"goals": 0, "assists": 0, "yellow_cards": 0, "red_cards": 0,
                   "own_goals": 0, "missed_penalties": 0, "minutes": 0,
                   "saves": 0, "penalty_saves": 0}
            had_cs = False
            for m in matches:
                if team_id not in (m.get("home_team_id"), m.get("away_team_id")):
                    continue
                evs = events_by_match.get(m["id"], [])
                s = aggregate_player_stats_from_events(evs, name, team_id)
                lin = next(
                    (x for x in lineups_by_match.get(m["id"], [])
                     if (x.get("player_name") or "").strip().lower() == name.strip().lower()),
                    None,
                )
                if lin:
                    agg["minutes"] += 90 if lin.get("starter") else 30
                    if s.get("substituted_out"):
                        agg["minutes"] = max(0, agg["minutes"] - 30)
                for k in ("goals", "assists", "yellow_cards", "red_cards", "own_goals", "missed_penalties"):
                    agg[k] += int(s.get(k, 0))
                if cs_map.get((m["id"], team_id), False):
                    had_cs = True

            res = compute_player_points(
                position=position,
                minutes_played=agg["minutes"],
                goals=agg["goals"], assists=agg["assists"],
                yellow_cards=agg["yellow_cards"], red_cards=agg["red_cards"],
                own_goals=agg["own_goals"], missed_penalties=agg["missed_penalties"],
                saves=agg["saves"], penalty_saves=agg["penalty_saves"],
                team_clean_sheet=had_cs,
            )
            base_pts = int(res["points"])

            is_captain = (captain_id == player_id)
            is_vice = (vice_id == player_id)
            multiplier = 1
            if is_captain and agg["minutes"] > 0:
                multiplier = 2
                captain_played = True
            elif is_vice and not captain_played and agg["minutes"] > 0:
                multiplier = 2

            pts_after_cap = base_pts * multiplier

            # Card boost (fantasy scope, applies only to cards targeting this player)
            player_country = (player.get("country") or player.get("country_code") or "").upper()
            ctx = {
                "scope": "fantasy",
                "position": position,
                "role": "captain" if is_captain else ("vice_captain" if is_vice else "player"),
                "home_country": player_country,
                "away_country": player_country,
                "home_continent": (player.get("continent") or "").lower(),
                "away_continent": (player.get("continent") or "").lower(),
            }
            boost = compute_card_boost(cards_by_target_player.get(player_id, []), ctx)
            pts_boosted = round(pts_after_cap * (1.0 + boost))

            per_player_breakdown.append({
                "player_id": player_id,
                "name": name,
                "position": position,
                "team_id": team_id,
                "minutes": agg["minutes"],
                "base_points": base_pts,
                "captain": is_captain,
                "vice": is_vice,
                "multiplier": multiplier,
                "card_boost": boost,
                "points": pts_boosted,
                "breakdown": res["breakdown"],
            })
            total_points += pts_boosted

        # Apply the game-level points_multiplier (admin-tunable per stage).
        final_points = round(total_points * points_mult)

        await db.wc_game_entries.update_one(
            {"id": entry["id"]},
            {"$set": {
                "points_scored": final_points,
                "raw_points": total_points,
                "points_multiplier_applied": points_mult,
                "breakdown_by_player": per_player_breakdown,
                "settled_at": utcnow_iso(),
            }},
        )
        settled += 1

    # Rank entries (highest first). Ties keep insertion order — fine for now.
    ranked = await db.wc_game_entries.find(
        {"wc_game_id": game_id, "settled_at": {"$ne": None}},
        {"_id": 0, "id": 1, "points_scored": 1},
    ).sort("points_scored", -1).to_list(length=20000)
    for i, r in enumerate(ranked, start=1):
        await db.wc_game_entries.update_one({"id": r["id"]}, {"$set": {"rank_in_game": i}})

    await db.wc_games.update_one(
        {"id": game_id},
        {"$set": {"status": "settled", "settled_at": utcnow_iso(),
                  "settled_match_ids": finished_ids,
                  "settled_entry_count": len(ranked)}},
    )

    log.info(f"settle_wc_game({game_id}): settled={settled} skipped={skipped} entries={len(entries)}")
    return {
        "ok": True, "game_id": game_id,
        "matches": finished_ids,
        "entries_total": len(entries),
        "entries_settled": settled,
        "entries_skipped_already_settled": skipped,
    }


# ---------- batch / periodic ----------
async def settle_due_wc_games(limit: int = 50) -> dict:
    """Find every `closed` wc_game whose contributing matches are all finished
    and settle them. Runs from the background loop every few minutes."""
    db = get_db()
    closed = await db.wc_games.find(
        {"status": {"$in": ["closed", "settling"]}}, {"_id": 0},
    ).sort("closes_at", 1).limit(limit).to_list(length=limit)

    settled = []
    deferred = []
    for g in closed:
        res = await settle_wc_game(g["id"])
        if res.get("ok"):
            settled.append(g["id"])
        else:
            deferred.append({"game_id": g["id"], "reason": res.get("reason")})
    return {"settled": settled, "deferred": deferred, "scanned": len(closed)}
