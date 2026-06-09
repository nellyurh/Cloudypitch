"""One-off Sofascore price update for WC2026 players.

Data source: Sofascore Fantasy WC26 player list (user-provided screenshots).
Prices in EUR millions. Match is best-effort by surname (case-insensitive)
against the existing `players.name` field; ambiguous matches log a warning.

Usage:
    cd /app/backend && python3 -m scripts.seed_sofascore_prices
"""
from __future__ import annotations

import asyncio
import re
import sys
import os

# Make `db`, `models` etc importable when run from /app/backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import init_db, get_db

# (surname, price_eur). Order roughly matches Sofascore's price tiers.
SOFASCORE_PRICES: list[tuple[str, float]] = [
    # ── Forwards / Midfielders (top tier, FUT-flagship) ────────────
    ("Yamal", 11.5), ("Dembélé", 11.5), ("Vinicius", 11.0), ("Raphinha", 10.5),
    ("Olise", 10.5), ("Fernandes", 9.5), ("Pedri", 9.0), ("Saka", 9.0),
    ("Bellingham", 8.5), ("Díaz", 8.5), ("Wirtz", 8.5), ("Musiala", 8.5),
    ("Doku", 8.5), ("Vitinha", 8.5),
    ("Salah", 8.0), ("Valverde", 8.0), ("Güler", 8.0), ("Mané", 8.0),
    ("Fernández", 8.0), ("Doué", 8.0), ("Cherki", 8.0), ("Williams", 8.0),
    ("Ødegaard", 8.0), ("Mahrez", 8.0), ("Rice", 8.0), ("Neves", 8.0),
    ("Guimarães", 8.0), ("Çalhanoğlu", 8.0), ("Diomande", 8.0), ("Tielemans", 8.0),
    ("Modrić", 7.5), ("De Bruyne", 7.5), ("Díaz", 7.5), ("de Jong", 7.5),
    ("Yıldız", 7.5), ("Rodri", 7.5), ("Mac Allister", 7.5), ("Gakpo", 7.5),
    ("Reijnders", 7.5), ("Pulišić", 7.5), ("Ruiz", 7.5),
    ("Rashford", 7.0), ("Olmo", 7.0), ("Félix", 7.0), ("Heung-min", 7.0),
    ("Paz", 7.0), ("Semenyo", 7.0), ("Caicedo", 7.0), ("Gordon", 7.0),
    ("Neto", 7.0), ("Barcola", 7.0), ("Sané", 7.0), ("Maza", 7.0),
    ("Ounahi", 7.0), ("Trossard", 7.0), ("Gravenberch", 7.0), ("McTominay", 7.0),
    ("Xhaka", 7.0), ("Trincão", 7.0),
    ("Neymar", 6.5), ("Gavi", 6.5), ("Tchouaméni", 6.5), ("Diallo", 6.5),
    ("Casemiro", 6.5), ("de Arrascaeta", 6.5), ("Leão", 6.5), ("Paquetá", 6.5),
    ("Silva", 6.5), ("Ndiaye", 6.5), ("Ezzalzouli", 6.5), ("Kessié", 6.5),
    ("Gueye", 6.5), ("Almada", 6.5), ("Khannouss", 6.5), ("Saibari", 6.5),
    ("Kubo", 6.5), ("Simeone", 6.5), ("Pavlović", 6.5), ("Perišić", 6.5),
    ("Nusa", 6.5), ("Rabiot", 6.5), ("Anderson", 6.5), ("Beena", 6.5),
    ("Sabitzer", 6.5), ("Kramarić", 6.5),
    # ── Defenders ──────────────────────────────────────────────────
    ("Hakimi", 8.0), ("Kimmich", 7.5), ("Mendes", 7.5),
    ("van Dijk", 7.0), ("Magalhães", 7.0), ("Guardiol", 7.0), ("Saliba", 7.0),
    ("Schlotterbeck", 7.0),
    ("Koundé", 6.5), ("Dias", 6.5), ("Marquinhos", 6.5), ("Cucurella", 6.5),
    ("Timber", 6.5), ("Dumfries", 6.5), ("Tah", 6.5),
    ("Cubarsi", 6.0), ("Mazraoui", 6.0), ("Hincapié", 6.0), ("Pacho", 6.0),
    ("Bensebaini", 6.0), ("Davies", 6.0), ("O'Reilly", 6.0), ("Guéhi", 6.0),
    ("Hernández", 6.0), ("Upamecano", 6.0), ("Raum", 6.0),
    ("Cancelo", 5.5), ("Alaba", 5.5), ("García", 5.5), ("Martínez", 5.5),
    ("James", 5.5), ("Aït-Nouri", 5.5), ("Romero", 5.5), ("Wesley", 5.5),
    ("Akanji", 5.5), ("Aguerd", 5.5), ("Kadioglu", 5.5), ("Nunes", 5.5),
    ("Min-jae", 5.5), ("Vušković", 5.5), ("van de Ven", 5.5), ("Muñoz", 5.5),
    ("Porro", 5.5), ("Stanišić", 5.5), ("Llorente", 5.5), ("Laporte", 5.5),
    ("Laimer", 5.5), ("Ndicka", 5.5), ("Gómez", 5.5), ("Santos", 5.5),
    ("Inácio", 5.5), ("Giménez", 5.5), ("van Hecke", 5.5), ("Konsa", 5.5),
    ("Krejčí", 5.5), ("Theate", 5.5), ("Coufal", 5.5),
    ("Rüdiger", 5.0), ("Araújo", 5.0), ("Konaté", 5.0), ("Sarr", 5.0),
    ("Robertson", 5.0), ("Koulibaly", 5.0), ("Dalot", 5.0), ("Stones", 5.0),
    ("Aké", 5.0), ("Gusto", 5.0), ("Otamendi", 5.0), ("Wan-Bissaka", 5.0),
    ("Estupiñán", 5.0), ("Doué", 5.0), ("Pereira", 5.0), ("Bremer", 5.0),
    ("Diatta", 5.0), ("Sánchez", 5.0), ("Veiga", 5.0), ("Tagliafico", 5.0),
    ("Kossounou", 5.0), ("Montiel", 5.0), ("Lindelöf", 5.0), ("Niakhaté", 5.0),
    ("Varela", 5.0), ("Semedo", 5.0), ("Tuanzebe", 5.0), ("Salah-Eddine", 5.0),
    ("Itô", 5.0), ("Balerdi", 5.0),
    # ── Goalkeepers ────────────────────────────────────────────────
    ("Courtois", 6.5),
    ("Alisson", 6.0), ("Maignan", 6.0),
    ("Martínez", 5.5), ("Bono", 5.5), ("Neuer", 5.5), ("Mendy", 5.5),
    ("Costa", 5.5), ("Pickford", 5.5), ("Simón", 5.5), ("Kobel", 5.5),
    ("Verbruggen", 5.5),
    ("Ederson", 5.0), ("Zidane", 5.0), ("Livaković", 5.0), ("Çakır", 5.0),
    ("Fofana", 5.0), ("Rochet", 5.0), ("Vasilj", 5.0), ("Kovář", 5.0),
    ("Williams", 5.0), ("St. Clair", 5.0), ("Nyland", 5.0), ("Schlager", 5.0),
    ("Raya", 4.5), ("Lammens", 4.5), ("El-Shenawy", 4.5), ("Bayındır", 4.5),
    ("Rulli", 4.5), ("Placide", 4.5), ("Shobeir", 4.5), ("Mpasi Nzau", 4.5),
    ("Henderson", 4.5), ("Ochoa", 4.5), ("Sá", 4.5), ("Lafont", 4.5),
    ("Harrar", 4.5), ("Kotarski", 4.5), ("Roefs", 4.5), ("Galindez", 4.5),
    ("Zigi", 4.5), ("Al-Aqidi", 4.5), ("Turner", 4.5),
]


def _normalise(s: str) -> str:
    return re.sub(r"[^a-zà-ÿ]", "", s.lower())


async def main() -> None:
    init_db()
    db = get_db()
    updated, ambiguous, missed = 0, 0, []

    for surname, price in SOFASCORE_PRICES:
        key = _normalise(surname)
        # Match by surname suffix on `name`. Sportmonks often uses "L. Yamal"
        # or "Lamine Yamal" so we match where any token endswith the key.
        cursor = db.players.find(
            {"is_wc_2026": True},
            {"_id": 0, "id": 1, "name": 1, "position": 1, "country": 1},
        )
        matches = []
        async for doc in cursor:
            tokens = re.split(r"\s+", doc.get("name") or "")
            if any(_normalise(t) == key for t in tokens):
                matches.append(doc)
            elif _normalise(doc.get("name", "")).endswith(key):
                matches.append(doc)

        if not matches:
            missed.append(surname)
            continue

        # If multiple candidates, prefer FWD/MID for the expensive tier,
        # else just update them all (price-by-surname is rough).
        if len(matches) > 1:
            ambiguous += len(matches)
        for m in matches:
            res = await db.players.update_one({"id": m["id"]}, {"$set": {"price": price, "price_source": "sofascore_2026"}})
            if res.modified_count:
                updated += 1

    print(f"Updated {updated} player prices.")
    print(f"Ambiguous-name matches: {ambiguous}")
    if missed:
        print(f"Missed {len(missed)} surnames (no DB match):")
        for s in missed[:20]:
            print(f"   - {s}")
        if len(missed) > 20:
            print(f"   …and {len(missed) - 20} more")


if __name__ == "__main__":
    asyncio.run(main())
