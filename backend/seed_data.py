"""Static catalog seeds: sports list, WC2026 fantasy comp, Legend Cards catalog, prize pools."""
from db import get_db, utcnow_iso
from models import new_id


SPORTS = [
    {"slug": "football", "name": "Football", "icon": "soccer-ball", "display_order": 1},
    {"slug": "basketball", "name": "Basketball", "icon": "basketball", "display_order": 2},
    {"slug": "tennis", "name": "Tennis", "icon": "tennis-ball", "display_order": 3},
    {"slug": "baseball", "name": "Baseball", "icon": "baseball", "display_order": 4},
    {"slug": "hockey", "name": "Hockey", "icon": "hockey", "display_order": 5},
    {"slug": "cricket", "name": "Cricket", "icon": "cricket", "display_order": 6},
    {"slug": "rugby", "name": "Rugby", "icon": "rugby", "display_order": 7},
    {"slug": "nba", "name": "NBA", "icon": "basketball", "display_order": 8},
    {"slug": "volleyball", "name": "Volleyball", "icon": "volleyball", "display_order": 9},
    {"slug": "handball", "name": "Handball", "icon": "handball", "display_order": 10},
    {"slug": "mma", "name": "MMA", "icon": "boxing-glove", "display_order": 11},
    {"slug": "f1", "name": "F1", "icon": "racing-car", "display_order": 12},
    {"slug": "afl", "name": "AFL", "icon": "football-helmet", "display_order": 13},
    {"slug": "golf", "name": "Golf", "icon": "golf", "display_order": 14},
]


# Country sort priority (lower = higher in sidebar)
COUNTRY_PRIORITY = {
    "England": 1, "Spain": 2, "Italy": 3, "Germany": 4, "France": 5,
    "Netherlands": 10, "Portugal": 11, "Belgium": 12, "Turkey": 13, "Scotland": 14,
    "Brazil": 20, "Argentina": 21,
    "USA": 30, "United States": 30, "Mexico": 31,
    "World": 40, "Europe": 41, "International": 42,
    "Greece": 50, "Austria": 51, "Russia": 52, "Switzerland": 53, "Poland": 54,
    "Nigeria": 60, "Egypt": 61, "South Africa": 62, "Morocco": 63,
    "Saudi Arabia": 70, "Japan": 71, "South Korea": 72, "China": 73,
}


TIER_1_LEAGUES = {
    "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
    "UEFA Champions League", "UEFA Europa League", "UEFA Conference League",
    "FIFA World Cup", "FIFA Club World Cup",
}

TIER_2_LEAGUES = {
    "Eredivisie", "Primeira Liga", "Belgian Pro League", "Scottish Premier",
    "Super Lig", "Süper Lig", "Championship", "Serie B", "Liga 2",
    "MLS", "Major League Soccer", "Brasileirão", "Liga MX",
    "Copa Libertadores", "FA Cup", "Copa del Rey", "Coppa Italia", "EFL Cup",
}


def league_tier_score(name: str) -> int:
    if not name:
        return 10
    n = name.strip()
    if n in TIER_1_LEAGUES:
        return 100
    if n in TIER_2_LEAGUES:
        return 80
    return 30


# ===== Legend Cards Catalog (100 cards) =====
def _card(name, player_name, country, tier, price, effect_type, effect_value, description, image_url=""):
    # Pricing in USD cents (stored as integer to avoid float issues). $2 = 200, $1 = 100, $0.50 = 50.
    USD_BY_TIER = {1: 200, 2: 100, 3: 50}
    return {
        "id": new_id(), "name": name, "player_name": player_name,
        "country_code": country, "tier": tier,
        "price_ngn": price,                          # legacy field, kept for back-compat
        "price_usd_cents": USD_BY_TIER.get(tier, 50),
        "effect_type": effect_type, "effect_value": effect_value,
        "description": description, "image_url": image_url,
    }


GOAT_CARDS = [
    _card("Pelé Spirit", "Pelé", "BR", 1, 2000, "score_boost", {"multiplier": 2.0}, "Doubles points on exact-score predictions"),
    _card("Maradona Hand", "Diego Maradona", "AR", 1, 2000, "score_boost", {"multiplier": 2.0}, "Doubles points on goal-scorer predictions"),
    _card("Messi Magic", "Lionel Messi", "AR", 1, 2000, "outcome_boost", {"multiplier": 1.75}, "75% bonus on outcome correct"),
    _card("CR7 Power", "Cristiano Ronaldo", "PT", 1, 2000, "score_boost", {"multiplier": 1.75}, "75% bonus on exact score"),
    _card("Zidane Class", "Zinedine Zidane", "FR", 1, 2000, "captain_boost", {"multiplier": 3.0}, "Triples captain points one round"),
    _card("Cruyff Turn", "Johan Cruyff", "NL", 1, 2000, "outcome_boost", {"multiplier": 1.75}, "Outcome bonus + assist points x2"),
    _card("Beckenbauer Wall", "Franz Beckenbauer", "DE", 1, 2000, "defense_boost", {"multiplier": 2.0}, "Clean sheet bonus x2"),
    _card("Ronaldo R9", "Ronaldo Nazário", "BR", 1, 2000, "score_boost", {"multiplier": 1.75}, "Goal predictions x1.75"),
    _card("Best of British", "George Best", "GB", 1, 2000, "outcome_boost", {"multiplier": 1.5}, "50% on outcome + draw bonus"),
    _card("Eusébio Strike", "Eusébio", "PT", 1, 2000, "score_boost", {"multiplier": 1.6}, "60% bonus on goalscorers"),
    _card("Di Stéfano Vision", "Alfredo Di Stéfano", "AR", 1, 2000, "captain_boost", {"multiplier": 2.5}, "Captain x2.5"),
    _card("Garrincha Joy", "Garrincha", "BR", 1, 2000, "outcome_boost", {"multiplier": 1.75}, "Draw outcome x3"),
    _card("Puskás Hammer", "Ferenc Puskás", "HU", 1, 2000, "score_boost", {"multiplier": 1.75}, "Away win exact-score x2"),
    _card("Yashin Gloves", "Lev Yashin", "RU", 1, 2000, "defense_boost", {"multiplier": 2.5}, "Clean sheet x2.5"),
    _card("Platini Free-Kick", "Michel Platini", "FR", 1, 2000, "score_boost", {"multiplier": 1.5}, "Set-piece goal bonus"),
    _card("Müller Bomber", "Gerd Müller", "DE", 1, 2000, "score_boost", {"multiplier": 1.75}, "Tournament top-scorer bonus"),
    _card("Kaká Lightning", "Kaká", "BR", 1, 2000, "outcome_boost", {"multiplier": 1.5}, "Win + clean sheet combo"),
    _card("Baggio Ponytail", "Roberto Baggio", "IT", 1, 2000, "score_boost", {"multiplier": 1.5}, "Knockout-round bonus"),
    _card("Henry Finesse", "Thierry Henry", "FR", 1, 2000, "score_boost", {"multiplier": 1.75}, "Group-stage exact score x2"),
    _card("Zico Brazilian", "Zico", "BR", 1, 2000, "outcome_boost", {"multiplier": 1.5}, "Brazil match bonus x2"),
]

ELITE_CARDS = [
    _card("Ronaldinho Smile", "Ronaldinho", "BR", 2, 1000, "outcome_boost", {"multiplier": 1.4}, "Outcome correct +40%"),
    _card("Drogba King", "Didier Drogba", "CI", 2, 1000, "score_boost", {"multiplier": 1.4}, "African team bonus"),
    _card("Okocha Showtime", "Jay-Jay Okocha", "NG", 2, 1000, "outcome_boost", {"multiplier": 1.5}, "Nigeria & African team x2"),
    _card("Salah Pharaoh", "Mohamed Salah", "EG", 2, 1000, "score_boost", {"multiplier": 1.4}, "Egypt & African team bonus"),
    _card("Mahrez Flair", "Riyad Mahrez", "DZ", 2, 1000, "score_boost", {"multiplier": 1.4}, "Algeria & African team bonus"),
    _card("Modric Engine", "Luka Modrić", "HR", 2, 1000, "captain_boost", {"multiplier": 2.0}, "Captain x2"),
    _card("Iniesta Whisper", "Andrés Iniesta", "ES", 2, 1000, "outcome_boost", {"multiplier": 1.4}, "Spain match bonus"),
    _card("Xavi Maestro", "Xavi", "ES", 2, 1000, "captain_boost", {"multiplier": 1.8}, "Captain x1.8"),
    _card("Kanté Engine", "N'Golo Kanté", "FR", 2, 1000, "defense_boost", {"multiplier": 1.5}, "Defensive players +50%"),
    _card("Eto'o Lion", "Samuel Eto'o", "CM", 2, 1000, "score_boost", {"multiplier": 1.5}, "Cameroon & African bonus"),
    _card("Yaya Beast", "Yaya Touré", "CI", 2, 1000, "score_boost", {"multiplier": 1.4}, "Ivory Coast bonus"),
    _card("Weah Liberian", "George Weah", "LR", 2, 1000, "outcome_boost", {"multiplier": 1.5}, "Underdog win bonus"),
    _card("Mbappé Rocket", "Kylian Mbappé", "FR", 2, 1000, "score_boost", {"multiplier": 1.5}, "France match bonus"),
    _card("Haaland Force", "Erling Haaland", "NO", 2, 1000, "score_boost", {"multiplier": 1.4}, "Goals x1.4"),
    _card("Vinícius Dance", "Vinícius Júnior", "BR", 2, 1000, "score_boost", {"multiplier": 1.4}, "Brazil bonus"),
    _card("Bellingham Heart", "Jude Bellingham", "GB", 2, 1000, "captain_boost", {"multiplier": 1.8}, "Captain x1.8"),
    _card("De Bruyne Vision", "Kevin De Bruyne", "BE", 2, 1000, "score_boost", {"multiplier": 1.4}, "Assist points x2"),
    _card("Pirlo Conductor", "Andrea Pirlo", "IT", 2, 1000, "captain_boost", {"multiplier": 1.7}, "Captain x1.7"),
    _card("Buffon Saves", "Gianluigi Buffon", "IT", 2, 1000, "defense_boost", {"multiplier": 2.0}, "Goalkeeper clean sheet x2"),
    _card("Casillas Hands", "Iker Casillas", "ES", 2, 1000, "defense_boost", {"multiplier": 1.8}, "Spain defense bonus"),
    _card("Lewa Klass", "Robert Lewandowski", "PL", 2, 1000, "score_boost", {"multiplier": 1.4}, "Striker goals x1.4"),
    _card("Suárez Bite", "Luis Suárez", "UY", 2, 1000, "score_boost", {"multiplier": 1.4}, "Knockout bonus"),
    _card("Neymar Jr", "Neymar", "BR", 2, 1000, "outcome_boost", {"multiplier": 1.4}, "Brazil flair"),
    _card("Cantona Collar", "Eric Cantona", "FR", 2, 1000, "captain_boost", {"multiplier": 1.6}, "Captain x1.6"),
    _card("Beckham Bend", "David Beckham", "GB", 2, 1000, "score_boost", {"multiplier": 1.4}, "Set-piece bonus"),
    _card("Gerrard Heart", "Steven Gerrard", "GB", 2, 1000, "captain_boost", {"multiplier": 1.7}, "Captain x1.7"),
    _card("Lampard Late", "Frank Lampard", "GB", 2, 1000, "score_boost", {"multiplier": 1.4}, "Late goal bonus"),
    _card("Cafu Run", "Cafu", "BR", 2, 1000, "defense_boost", {"multiplier": 1.5}, "Full-back assists"),
    _card("Roberto Carlos Boom", "Roberto Carlos", "BR", 2, 1000, "score_boost", {"multiplier": 1.4}, "Free-kick bonus"),
    _card("Maldini Eternal", "Paolo Maldini", "IT", 2, 1000, "defense_boost", {"multiplier": 1.8}, "Italian defense bonus"),
]

STAR_CARDS = [
    _card(f"Star Card {i+1}", name, country, 3, 500, eff, val, desc)
    for i, (name, country, eff, val, desc) in enumerate([
        ("Vidal", "CL", "score_boost", {"multiplier": 1.2}, "Mid score +20%"),
        ("Cavani", "UY", "score_boost", {"multiplier": 1.2}, "Striker score +20%"),
        ("Bale", "GB", "score_boost", {"multiplier": 1.25}, "Set-piece +25%"),
        ("Pogba", "FR", "captain_boost", {"multiplier": 1.4}, "Captain +40%"),
        ("Hazard", "BE", "outcome_boost", {"multiplier": 1.2}, "Outcome +20%"),
        ("Lukaku", "BE", "score_boost", {"multiplier": 1.2}, "Goals +20%"),
        ("Coutinho", "BR", "score_boost", {"multiplier": 1.2}, "Brazil bonus"),
        ("Falcao", "CO", "score_boost", {"multiplier": 1.25}, "Colombia bonus"),
        ("James", "CO", "outcome_boost", {"multiplier": 1.2}, "Colombia outcome"),
        ("Forlán", "UY", "score_boost", {"multiplier": 1.25}, "Uruguay bonus"),
        ("Sneijder", "NL", "captain_boost", {"multiplier": 1.4}, "Netherlands captain"),
        ("Robben", "NL", "score_boost", {"multiplier": 1.25}, "Cut-inside goals"),
        ("Van Persie", "NL", "score_boost", {"multiplier": 1.2}, "Netherlands striker"),
        ("Kompany", "BE", "defense_boost", {"multiplier": 1.5}, "Center-back +50%"),
        ("Ramos", "ES", "defense_boost", {"multiplier": 1.5}, "Spain defense"),
        ("Piqué", "ES", "defense_boost", {"multiplier": 1.4}, "Spain CB"),
        ("Busquets", "ES", "captain_boost", {"multiplier": 1.4}, "Spain captain"),
        ("Alba", "ES", "defense_boost", {"multiplier": 1.4}, "LB assists"),
        ("Marcelo", "BR", "defense_boost", {"multiplier": 1.4}, "Brazil LB"),
        ("Thiago Silva", "BR", "defense_boost", {"multiplier": 1.5}, "Brazil CB"),
        ("Casemiro", "BR", "defense_boost", {"multiplier": 1.4}, "Defensive mid"),
        ("Verratti", "IT", "captain_boost", {"multiplier": 1.4}, "Italy captain"),
        ("Donnarumma", "IT", "defense_boost", {"multiplier": 1.6}, "Italy GK"),
        ("Chiellini", "IT", "defense_boost", {"multiplier": 1.5}, "Italy CB"),
        ("Insigne", "IT", "score_boost", {"multiplier": 1.2}, "Italy LW"),
        ("Kimmich", "DE", "captain_boost", {"multiplier": 1.4}, "Germany captain"),
        ("Müller T.", "DE", "score_boost", {"multiplier": 1.25}, "Germany striker"),
        ("Neuer", "DE", "defense_boost", {"multiplier": 1.6}, "Germany GK"),
        ("Sané", "DE", "score_boost", {"multiplier": 1.2}, "Germany winger"),
        ("Aubameyang", "GA", "score_boost", {"multiplier": 1.25}, "Gabon striker"),
        ("Manè", "SN", "score_boost", {"multiplier": 1.3}, "Senegal bonus"),
        ("Koulibaly", "SN", "defense_boost", {"multiplier": 1.5}, "Senegal CB"),
        ("Hakimi", "MA", "defense_boost", {"multiplier": 1.5}, "Morocco RB"),
        ("Ziyech", "MA", "score_boost", {"multiplier": 1.25}, "Morocco winger"),
        ("Onana", "CM", "defense_boost", {"multiplier": 1.5}, "Cameroon GK"),
        ("Boateng", "GH", "defense_boost", {"multiplier": 1.4}, "Ghana CB"),
        ("Partey", "GH", "captain_boost", {"multiplier": 1.4}, "Ghana captain"),
        ("Iheanacho", "NG", "score_boost", {"multiplier": 1.3}, "Nigeria bonus"),
        ("Osimhen", "NG", "score_boost", {"multiplier": 1.35}, "Nigeria striker"),
        ("Lookman", "NG", "score_boost", {"multiplier": 1.3}, "Nigeria winger"),
        ("Chukwueze", "NG", "score_boost", {"multiplier": 1.25}, "Nigeria RW"),
        ("Trossard", "BE", "score_boost", {"multiplier": 1.2}, "Belgium forward"),
        ("Saka", "GB", "score_boost", {"multiplier": 1.25}, "England winger"),
        ("Foden", "GB", "score_boost", {"multiplier": 1.25}, "England playmaker"),
        ("Rice", "GB", "captain_boost", {"multiplier": 1.3}, "England DM"),
        ("Pickford", "GB", "defense_boost", {"multiplier": 1.4}, "England GK"),
        ("Trippier", "GB", "defense_boost", {"multiplier": 1.3}, "England RB"),
        ("Kane", "GB", "score_boost", {"multiplier": 1.3}, "England captain & striker"),
        ("Pulisic", "US", "score_boost", {"multiplier": 1.2}, "USA winger"),
        ("Reyna", "US", "outcome_boost", {"multiplier": 1.2}, "USA bonus"),
    ])
]

ALL_CARDS = GOAT_CARDS + ELITE_CARDS + STAR_CARDS


# ===== WC 2026 FANTASY COMPETITION =====
WC2026_COMPETITION = {
    "id": "fantasy-wc2026",
    "name": "FIFA World Cup 2026 Fantasy",
    "starts_at": "2026-06-11T18:00:00+00:00",
    "ends_at": "2026-07-19T22:00:00+00:00",
    "budget_total": 100.0,
    "squad_size": 15,
    "transfers_per_gw": 1,
    "image_url": "https://images.unsplash.com/photo-1705593973313-75de7bf95b56?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NjZ8MHwxfHNlYXJjaHwxfHxmb290YmFsbCUyMHN0YWRpdW0lMjBjcm93ZHxlbnwwfHx8fDE3Nzk5MTk4MTF8MA&ixlib=rb-4.1.0&q=85",
}


# ===== WC 2026 GROUPS (48 teams in 12 groups of 4) =====
WC2026_GROUPS = [
    {"group": "A", "teams": ["Mexico", "Canada", "Cameroon", "Uzbekistan"]},
    {"group": "B", "teams": ["USA", "Iran", "Tunisia", "Saudi Arabia"]},
    {"group": "C", "teams": ["Canada", "Senegal", "Japan", "Australia"]},
    {"group": "D", "teams": ["Argentina", "Ecuador", "South Korea", "Iceland"]},
    {"group": "E", "teams": ["Spain", "Croatia", "Egypt", "Costa Rica"]},
    {"group": "F", "teams": ["Brazil", "Switzerland", "Cameroon", "Panama"]},
    {"group": "G", "teams": ["England", "Denmark", "Morocco", "Qatar"]},
    {"group": "H", "teams": ["Germany", "Poland", "Algeria", "Jamaica"]},
    {"group": "I", "teams": ["France", "Serbia", "Ghana", "New Zealand"]},
    {"group": "J", "teams": ["Portugal", "Netherlands", "Nigeria", "Wales"]},
    {"group": "K", "teams": ["Italy", "Belgium", "Ivory Coast", "Honduras"]},
    {"group": "L", "teams": ["Uruguay", "Colombia", "Senegal", "Paraguay"]},
]


# ===== Prize Pools =====
PRIZE_POOLS = [
    {
        "id": "pool-wc2026-fantasy",
        "kind": "fantasy_wc2026",
        "competition_id": "fantasy-wc2026",
        "title": "FIFA WC 2026 Grand Prize Pool",
        "amount_total_ngn": 50_000_000,
        "amount_usd_cents": 3_000_000,   # $30,000 seed; auto-grows from card revenue
        "currency": "USD",
        "payout_structure": [
            {"rank_min": 1, "rank_max": 1, "pct": 40},
            {"rank_min": 2, "rank_max": 3, "pct": 15},
            {"rank_min": 4, "rank_max": 10, "pct": 3},
            {"rank_min": 11, "rank_max": 100, "pct": 0.1},
        ],
        "starts_at": "2026-06-11T18:00:00+00:00",
        "ends_at": "2026-07-19T22:00:00+00:00",
        "status": "upcoming",
        "image_url": "https://images.unsplash.com/photo-1705593973313-75de7bf95b56?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NjZ8MHwxfHNlYXJjaHwxfHxmb290YmFsbCUyMHN0YWRpdW0lMjBjcm93ZHxlbnwwfHx8fDE3Nzk5MTk4MTF8MA&ixlib=rb-4.1.0&q=85",
    },
    {
        "id": "pool-referrals",
        "kind": "referrals",
        "competition_id": None,
        "title": "Referral Champions Pool",
        "amount_total_ngn": 0,
        "amount_usd_cents": 500_000,   # $5,000 seed
        "currency": "USD",
        "payout_structure": [
            {"rank_min": 1, "rank_max": 1, "pct": 40},
            {"rank_min": 2, "rank_max": 3, "pct": 15},
            {"rank_min": 4, "rank_max": 10, "pct": 3},
        ],
        "starts_at": "2026-02-09T00:00:00+00:00",
        "ends_at": "2026-07-19T22:00:00+00:00",
        "status": "active",
        "image_url": "",
    },
]


# ===== WC Fantasy Game Config (148 games structure) =====
# (game_type, stage, card_limit_default, points_multiplier, opens_hours_before, notes)
WC_GAME_CONFIG_DEFAULTS = [
    ("match", "any",        2,  1.0, 168, "Standard match game, 2 cards"),
    ("group", "group_md1",  4,  1.0, 24,  "Group game matchday 1"),
    ("group", "group_md2",  4,  1.0, 24,  "Group game matchday 2"),
    ("group", "group_md3",  4,  1.0, 24,  "Group game matchday 3 — elimination decisions"),
    ("round", "group_md1",  5,  1.0, 48,  "Tournament-wide round game MD1"),
    ("round", "group_md2",  5,  1.0, 48,  "Tournament-wide round game MD2"),
    ("round", "group_md3",  6,  1.2, 48,  "Tournament-wide round game MD3 — increased cards"),
    ("round", "r32",        6,  1.5, 48,  "Round of 32 — knockout begins"),
    ("round", "r16",        7,  2.0, 48,  "Round of 16"),
    ("round", "qf",         8,  2.5, 48,  "Quarterfinals"),
    ("round", "sf",         9,  3.0, 48,  "Semifinals"),
    ("round", "finals",    10,  4.0, 48,  "Finals + 3rd place playoff"),
]


async def seed_all():
    db = get_db()
    # Sports
    for s in SPORTS:
        await db.sports.update_one(
            {"slug": s["slug"]},
            {"$set": {**s, "id": s["slug"]}},
            upsert=True,
        )
    # Legend Cards
    for c in ALL_CARDS:
        # $setOnInsert without the dynamic price fields (which also go to $set so it works on existing rows too)
        on_insert = {k: v for k, v in c.items() if k not in ("price_usd_cents", "tier")}
        on_insert["created_at"] = utcnow_iso()
        await db.legend_cards.update_one(
            {"name": c["name"]},
            {
                "$setOnInsert": on_insert,
                "$set": {"price_usd_cents": c["price_usd_cents"], "tier": c["tier"]},
            },
            upsert=True,
        )
    # Fantasy comp
    await db.fantasy_competitions.update_one(
        {"id": WC2026_COMPETITION["id"]},
        {"$set": {**WC2026_COMPETITION, "created_at": utcnow_iso()}},
        upsert=True,
    )
    # Prize pools
    for p in PRIZE_POOLS:
        await db.prize_pools.update_one(
            {"id": p["id"]}, {"$set": {**p, "created_at": utcnow_iso()}}, upsert=True
        )
    # WC groups (one doc per group)
    for g in WC2026_GROUPS:
        await db.wc2026_groups.update_one(
            {"group": g["group"]}, {"$set": g}, upsert=True
        )
    # WC Game Config (12 default rows — admin can edit current values)
    for game_type, stage, lim, mult, hrs, notes in WC_GAME_CONFIG_DEFAULTS:
        await db.wc_game_config.update_one(
            {"game_type": game_type, "stage": stage},
            {
                "$setOnInsert": {
                    "id": f"wcfg-{game_type}-{stage}",
                    "card_limit_default": lim,
                    "card_limit_current": lim,
                    "points_multiplier": mult,
                    "opens_hours_before": hrs,
                    "is_active": True,
                    "notes": notes,
                    "created_at": utcnow_iso(),
                    "game_type": game_type,
                    "stage": stage,
                },
            },
            upsert=True,
        )
