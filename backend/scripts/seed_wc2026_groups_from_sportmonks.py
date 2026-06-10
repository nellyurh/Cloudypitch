"""Replace local `wc2026_groups` with the REAL FIFA WC 2026 final draw from
Sportmonks (season 26618). Past versions of this collection held a hardcoded
draft that included teams (e.g. Nigeria) which did not actually qualify.

Usage:
    cd /app/backend && python3 -m scripts.seed_wc2026_groups_from_sportmonks
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.sportmonks import _get
from db import init_db, get_db


# Sportmonks team names → canonical names we use across the app.
ALIASES = {
    "Korea Republic": "South Korea",
    "Korea DPR": "North Korea",
    "Czech Republic": "Czechia",
    "Türkiye": "Turkey",
    "Congo DR": "DR Congo",
    "Cape Verde Islands": "Cape Verde",
    "United States": "USA",
    "Côte d'Ivoire": "Ivory Coast",
}


async def main() -> None:
    init_db()
    db = get_db()
    d = await _get("/standings/seasons/26618", {"include": "group;participant"})
    rows = (d or {}).get("data", []) if isinstance(d, dict) else []

    bucket: dict[str, list[str]] = {}
    for r in rows:
        grp = r.get("group") or {}
        grp_name = grp.get("name") if isinstance(grp, dict) else None
        if not grp_name:
            continue
        # "Group A" → "A"
        m = re.match(r"^\s*Group\s+([A-Z])\s*$", grp_name)
        if not m:
            continue
        letter = m.group(1)
        team = (r.get("participant") or {}).get("name") if isinstance(r.get("participant"), dict) else None
        if not team:
            continue
        team = ALIASES.get(team, team)
        bucket.setdefault(letter, []).append(team)

    if len(bucket) < 12:
        print(f"WARN: only {len(bucket)} groups parsed; aborting to avoid wiping good data.")
        return

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    for letter in sorted(bucket.keys()):
        teams = sorted(bucket[letter])
        await db.wc2026_groups.update_one(
            {"group": letter},
            {"$set": {"group": letter, "teams": teams, "updated_at": now, "source": "sportmonks_26618"}},
            upsert=True,
        )
        inserted += 1
        print(f"Group {letter}: {teams}")
    print(f"Upserted {inserted} groups.")


if __name__ == "__main__":
    asyncio.run(main())
