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
    # Continental/global tournaments sit AT the very top (above all domestic)
    "World": 1, "Europe": 2, "International": 3,
    # Top-5 domestic
    "England": 10, "Spain": 11, "Italy": 12, "Germany": 13, "France": 14,
    "Netherlands": 20, "Portugal": 21, "Belgium": 22, "Turkey": 23, "Scotland": 24,
    "Brazil": 30, "Argentina": 31,
    "USA": 40, "United States": 40, "Mexico": 41,
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


def league_tier_score(name: str, country: str | None = None) -> int:
    """Return tier score (higher = more prominent). Top-5 leagues require BOTH the
    canonical name AND the canonical country (so 'Premier League' from Bhutan or
    'Serie A' from Brazil don't inherit T1 status).

    Tier scores: 100 (T1 — top-5 + UEFA + WC), 80 (T2 / cups), 60 (continentals),
    30 (everything else).
    """
    if not name:
        return 10
    n = name.strip().lower()
    c = (country or "").strip().lower()
    # ---- Tier-1 (top-5 European leagues + global tournaments) ----
    t1_country_strict = [
        ("premier league", {"england"}),
        ("la liga",        {"spain"}),
        ("laliga",         {"spain"}),
        ("serie a",        {"italy"}),
        ("bundesliga",     {"germany"}),
        ("ligue 1",        {"france"}),
    ]
    for needle, valid_countries in t1_country_strict:
        if needle in n and "2" not in n and "ii" not in n and c in valid_countries:
            return 100
    # ---- Tier-1 universal (no country needed) ----
    t1_universal = [
        "uefa champions league", "champions league",
        "uefa europa league", "europa league",
        "uefa conference league", "conference league",
        "fifa world cup", "world cup qualification", "world cup",
        "fifa club world cup", "club world cup",
        "uefa euro", "euro 2024", "euro 2028",
        "copa america", "copa américa",
    ]
    for needle in t1_universal:
        if needle in n:
            return 100
    # ---- Tier-2 (second-tier domestic + major cups + other major leagues) ----
    t2_country_strict = [
        ("championship", {"england"}),
        ("serie b",      {"italy"}),
        ("la liga 2",    {"spain"}),
        ("liga 2",       {"spain"}),
        ("ligue 2",      {"france"}),
        ("eredivisie",   {"netherlands"}),
        ("primeira liga", {"portugal"}),
        ("super lig",    {"turkey"}),
        ("süper lig",    {"turkey"}),
    ]
    for needle, valid_countries in t2_country_strict:
        if needle in n and c in valid_countries:
            return 80
    t2_universal = [
        "mls", "major league soccer", "brasileir", "liga mx", "saudi pro",
        "copa libertadores", "copa sudamericana",
        "fa cup", "copa del rey", "coppa italia", "efl cup", "carabao cup",
        "dfb pokal", "dfb-pokal", "coupe de france",
        "afcon", "africa cup of nations",
    ]
    for needle in t2_universal:
        if needle in n:
            return 80
    # ---- Tier-3 (other continentals) ----
    t3 = ["afc champions", "caf champions", "concacaf champions"]
    for needle in t3:
        if needle in n:
            return 60
    return 30


# ===== Legend Cards Catalog (100 cards) =====
def _card(name, player_name, country, tier, price, effect_type, effect_value, description, image_url="", position="ANY"):
    """Build a legend card.

    `position` is the slot the card LOCKS to — only that-position player can be
    boosted. Use 'ANY' for cards that work on any role (typically captain-style
    cards). Allowed: 'GK', 'DEF', 'MID', 'FWD', 'ANY'.
    """
    # Pricing in USD cents (stored as integer to avoid float issues). $2 = 200, $1 = 100, $0.50 = 50.
    USD_BY_TIER = {1: 200, 2: 100, 3: 50}
    return {
        "id": new_id(), "name": name, "player_name": player_name,
        "country_code": country, "tier": tier,
        "position": position.upper() if position else "ANY",
        "price_ngn": price,                          # legacy field, kept for back-compat
        "price_usd_cents": USD_BY_TIER.get(tier, 50),
        "effect_type": effect_type, "effect_value": effect_value,
        "description": description, "image_url": image_url,
    }


# Position helper — used inside the GOAT/Elite literal arrays below so we don't
# repeat the position kwarg on every single line.
def _p(pos: str):
    return pos


GOAT_CARDS = [
    _card("Pelé Spirit",          "Pelé",                "BR", 1, 2000, "score_boost",   {"multiplier": 2.0},  "Doubles points on exact-score predictions", position="FWD"),
    _card("Maradona Hand",        "Diego Maradona",      "AR", 1, 2000, "score_boost",   {"multiplier": 2.0},  "Doubles points on goal-scorer predictions", position="MID"),
    _card("Messi Magic",          "Lionel Messi",        "AR", 1, 2000, "outcome_boost", {"multiplier": 1.75}, "75% bonus on outcome correct", position="FWD"),
    _card("CR7 Power",            "Cristiano Ronaldo",   "PT", 1, 2000, "score_boost",   {"multiplier": 1.75}, "75% bonus on exact score", position="FWD"),
    _card("Zidane Class",         "Zinedine Zidane",     "FR", 1, 2000, "captain_boost", {"multiplier": 3.0},  "Triples captain points one round", position="MID"),
    _card("Cruyff Turn",          "Johan Cruyff",        "NL", 1, 2000, "outcome_boost", {"multiplier": 1.75}, "Outcome bonus + assist points x2", position="FWD"),
    _card("Beckenbauer Wall",     "Franz Beckenbauer",   "DE", 1, 2000, "defense_boost", {"multiplier": 2.0},  "Clean sheet bonus x2", position="DEF"),
    _card("Ronaldo R9",           "Ronaldo Nazário",     "BR", 1, 2000, "score_boost",   {"multiplier": 1.75}, "Goal predictions x1.75", position="FWD"),
    _card("Best of British",      "George Best",         "GB", 1, 2000, "outcome_boost", {"multiplier": 1.5},  "50% on outcome + draw bonus", position="FWD"),
    _card("Eusébio Strike",       "Eusébio",             "PT", 1, 2000, "score_boost",   {"multiplier": 1.6},  "60% bonus on goalscorers", position="FWD"),
    _card("Di Stéfano Vision",    "Alfredo Di Stéfano",  "AR", 1, 2000, "captain_boost", {"multiplier": 2.5},  "Captain x2.5", position="FWD"),
    _card("Garrincha Joy",        "Garrincha",           "BR", 1, 2000, "outcome_boost", {"multiplier": 1.75}, "Draw outcome x3", position="FWD"),
    _card("Puskás Hammer",        "Ferenc Puskás",       "HU", 1, 2000, "score_boost",   {"multiplier": 1.75}, "Away win exact-score x2", position="FWD"),
    _card("Yashin Gloves",        "Lev Yashin",          "RU", 1, 2000, "defense_boost", {"multiplier": 2.5},  "Clean sheet x2.5", position="GK"),
    _card("Platini Free-Kick",    "Michel Platini",      "FR", 1, 2000, "score_boost",   {"multiplier": 1.5},  "Set-piece goal bonus", position="MID"),
    _card("Müller Bomber",        "Gerd Müller",         "DE", 1, 2000, "score_boost",   {"multiplier": 1.75}, "Tournament top-scorer bonus", position="FWD"),
    _card("Kaká Lightning",       "Kaká",                "BR", 1, 2000, "outcome_boost", {"multiplier": 1.5},  "Win + clean sheet combo", position="MID"),
    _card("Baggio Ponytail",      "Roberto Baggio",      "IT", 1, 2000, "score_boost",   {"multiplier": 1.5},  "Knockout-round bonus", position="FWD"),
    _card("Henry Finesse",        "Thierry Henry",       "FR", 1, 2000, "score_boost",   {"multiplier": 1.75}, "Group-stage exact score x2", position="FWD"),
    _card("Zico Brazilian",       "Zico",                "BR", 1, 2000, "outcome_boost", {"multiplier": 1.5},  "Brazil match bonus x2", position="MID"),
]

ELITE_CARDS = [
    _card("Ronaldinho Smile",     "Ronaldinho",          "BR", 2, 1000, "outcome_boost", {"multiplier": 1.4}, "Outcome correct +40%", position="MID"),
    _card("Drogba King",          "Didier Drogba",       "CI", 2, 1000, "score_boost",   {"multiplier": 1.4}, "African team bonus", position="FWD"),
    _card("Okocha Showtime",      "Jay-Jay Okocha",      "NG", 2, 1000, "outcome_boost", {"multiplier": 1.5}, "Nigeria & African team x2", position="MID"),
    _card("Salah Pharaoh",        "Mohamed Salah",       "EG", 2, 1000, "score_boost",   {"multiplier": 1.4}, "Egypt & African team bonus", position="FWD"),
    _card("Mahrez Flair",         "Riyad Mahrez",        "DZ", 2, 1000, "score_boost",   {"multiplier": 1.4}, "Algeria & African team bonus", position="FWD"),
    _card("Modric Engine",        "Luka Modrić",         "HR", 2, 1000, "captain_boost", {"multiplier": 2.0}, "Captain x2", position="MID"),
    _card("Iniesta Whisper",      "Andrés Iniesta",      "ES", 2, 1000, "outcome_boost", {"multiplier": 1.4}, "Spain match bonus", position="MID"),
    _card("Xavi Maestro",         "Xavi",                "ES", 2, 1000, "captain_boost", {"multiplier": 1.8}, "Captain x1.8", position="MID"),
    _card("Kanté Engine",         "N'Golo Kanté",        "FR", 2, 1000, "defense_boost", {"multiplier": 1.5}, "Defensive players +50%", position="MID"),
    _card("Eto'o Lion",           "Samuel Eto'o",        "CM", 2, 1000, "score_boost",   {"multiplier": 1.5}, "Cameroon & African bonus", position="FWD"),
    _card("Yaya Beast",           "Yaya Touré",          "CI", 2, 1000, "score_boost",   {"multiplier": 1.4}, "Ivory Coast bonus", position="MID"),
    _card("Weah Liberian",        "George Weah",         "LR", 2, 1000, "outcome_boost", {"multiplier": 1.5}, "Underdog win bonus", position="FWD"),
    _card("Mbappé Rocket",        "Kylian Mbappé",       "FR", 2, 1000, "score_boost",   {"multiplier": 1.5}, "France match bonus", position="FWD"),
    _card("Haaland Force",        "Erling Haaland",      "NO", 2, 1000, "score_boost",   {"multiplier": 1.4}, "Goals x1.4", position="FWD"),
    _card("Vinícius Dance",       "Vinícius Júnior",     "BR", 2, 1000, "score_boost",   {"multiplier": 1.4}, "Brazil bonus", position="FWD"),
    _card("Bellingham Heart",     "Jude Bellingham",     "GB", 2, 1000, "captain_boost", {"multiplier": 1.8}, "Captain x1.8", position="MID"),
    _card("De Bruyne Vision",     "Kevin De Bruyne",     "BE", 2, 1000, "score_boost",   {"multiplier": 1.4}, "Assist points x2", position="MID"),
    _card("Pirlo Conductor",      "Andrea Pirlo",        "IT", 2, 1000, "captain_boost", {"multiplier": 1.7}, "Captain x1.7", position="MID"),
    _card("Buffon Saves",         "Gianluigi Buffon",    "IT", 2, 1000, "defense_boost", {"multiplier": 2.0}, "Goalkeeper clean sheet x2", position="GK"),
    _card("Casillas Hands",       "Iker Casillas",       "ES", 2, 1000, "defense_boost", {"multiplier": 1.8}, "Spain defense bonus", position="GK"),
    _card("Lewa Klass",           "Robert Lewandowski",  "PL", 2, 1000, "score_boost",   {"multiplier": 1.4}, "Striker goals x1.4", position="FWD"),
    _card("Suárez Bite",          "Luis Suárez",         "UY", 2, 1000, "score_boost",   {"multiplier": 1.4}, "Knockout bonus", position="FWD"),
    _card("Neymar Jr",            "Neymar",              "BR", 2, 1000, "outcome_boost", {"multiplier": 1.4}, "Brazil flair", position="FWD"),
    _card("Cantona Collar",       "Eric Cantona",        "FR", 2, 1000, "captain_boost", {"multiplier": 1.6}, "Captain x1.6", position="FWD"),
    _card("Beckham Bend",         "David Beckham",       "GB", 2, 1000, "score_boost",   {"multiplier": 1.4}, "Set-piece bonus", position="MID"),
    _card("Gerrard Heart",        "Steven Gerrard",      "GB", 2, 1000, "captain_boost", {"multiplier": 1.7}, "Captain x1.7", position="MID"),
    _card("Lampard Late",         "Frank Lampard",       "GB", 2, 1000, "score_boost",   {"multiplier": 1.4}, "Late goal bonus", position="MID"),
    _card("Cafu Run",             "Cafu",                "BR", 2, 1000, "defense_boost", {"multiplier": 1.5}, "Full-back assists", position="DEF"),
    _card("Roberto Carlos Boom",  "Roberto Carlos",      "BR", 2, 1000, "score_boost",   {"multiplier": 1.4}, "Free-kick bonus", position="DEF"),
    _card("Maldini Eternal",      "Paolo Maldini",       "IT", 2, 1000, "defense_boost", {"multiplier": 1.8}, "Italian defense bonus", position="DEF"),
]

STAR_CARDS = [
    _card(card_name, player_name, country, 3, 500, eff, val, desc, position=pos)
    for (card_name, player_name, country, pos, eff, val, desc) in [
        ("Vidal Iron Lung",      "Arturo Vidal",        "CL", "MID", "score_boost",    {"multiplier": 1.20}, "Midfield engine +20%"),
        ("Cavani El Matador",    "Edinson Cavani",      "UY", "FWD", "score_boost",    {"multiplier": 1.20}, "Striker score +20%"),
        ("Bale Wales Wonder",    "Gareth Bale",         "GB", "FWD", "score_boost",    {"multiplier": 1.25}, "Set-piece +25%"),
        ("Pogba Dab",            "Paul Pogba",          "FR", "MID", "captain_boost",  {"multiplier": 1.40}, "Captain +40%"),
        ("Hazard Eden",          "Eden Hazard",         "BE", "MID", "outcome_boost",  {"multiplier": 1.20}, "Outcome +20%"),
        ("Lukaku Bull",          "Romelu Lukaku",       "BE", "FWD", "score_boost",    {"multiplier": 1.20}, "Goals +20%"),
        ("Coutinho Magician",    "Philippe Coutinho",   "BR", "MID", "score_boost",    {"multiplier": 1.20}, "Brazil bonus"),
        ("Falcao El Tigre",      "Radamel Falcao",      "CO", "FWD", "score_boost",    {"multiplier": 1.25}, "Colombia bonus"),
        ("James No.10",          "James Rodríguez",     "CO", "MID", "outcome_boost",  {"multiplier": 1.20}, "Colombia outcome"),
        ("Forlán Uruguay",       "Diego Forlán",        "UY", "FWD", "score_boost",    {"multiplier": 1.25}, "Uruguay bonus"),
        ("Sneijder Orange",      "Wesley Sneijder",     "NL", "MID", "captain_boost",  {"multiplier": 1.40}, "Netherlands captain"),
        ("Robben Cut-In",        "Arjen Robben",        "NL", "FWD", "score_boost",    {"multiplier": 1.25}, "Cut-inside goals"),
        ("Van Persie Header",    "Robin van Persie",    "NL", "FWD", "score_boost",    {"multiplier": 1.20}, "Netherlands striker"),
        ("Kompany Captain",      "Vincent Kompany",     "BE", "DEF", "defense_boost",  {"multiplier": 1.50}, "Center-back +50%"),
        ("Ramos Warrior",        "Sergio Ramos",        "ES", "DEF", "defense_boost",  {"multiplier": 1.50}, "Spain defense"),
        ("Piqué Pillar",         "Gerard Piqué",        "ES", "DEF", "defense_boost",  {"multiplier": 1.40}, "Spain CB"),
        ("Busquets Anchor",      "Sergio Busquets",     "ES", "MID", "captain_boost",  {"multiplier": 1.40}, "Spain captain"),
        ("Alba Overlap",         "Jordi Alba",          "ES", "DEF", "defense_boost",  {"multiplier": 1.40}, "LB assists"),
        ("Marcelo Samba",        "Marcelo",             "BR", "DEF", "defense_boost",  {"multiplier": 1.40}, "Brazil LB"),
        ("Thiago Silva Wall",    "Thiago Silva",        "BR", "DEF", "defense_boost",  {"multiplier": 1.50}, "Brazil CB"),
        ("Casemiro Shield",      "Casemiro",            "BR", "MID", "defense_boost",  {"multiplier": 1.40}, "Defensive mid"),
        ("Verratti Picolo",      "Marco Verratti",      "IT", "MID", "captain_boost",  {"multiplier": 1.40}, "Italy captain"),
        ("Donnarumma Gigio",     "Gianluigi Donnarumma","IT", "GK",  "defense_boost",  {"multiplier": 1.60}, "Italy GK"),
        ("Chiellini Stopper",    "Giorgio Chiellini",   "IT", "DEF", "defense_boost",  {"multiplier": 1.50}, "Italy CB"),
        ("Insigne Maestro",      "Lorenzo Insigne",     "IT", "FWD", "score_boost",    {"multiplier": 1.20}, "Italy LW"),
        ("Kimmich Captain",      "Joshua Kimmich",      "DE", "MID", "captain_boost",  {"multiplier": 1.40}, "Germany captain"),
        ("Thomas Müller Raumdeuter", "Thomas Müller",   "DE", "FWD", "score_boost",    {"multiplier": 1.25}, "Germany striker"),
        ("Neuer Sweeper",        "Manuel Neuer",        "DE", "GK",  "defense_boost",  {"multiplier": 1.60}, "Germany GK"),
        ("Sané Speed",           "Leroy Sané",          "DE", "FWD", "score_boost",    {"multiplier": 1.20}, "Germany winger"),
        ("Aubameyang Panther",   "Pierre-Emerick Aubameyang", "GA", "FWD", "score_boost", {"multiplier": 1.25}, "Gabon striker"),
        ("Mané Lion",            "Sadio Mané",          "SN", "FWD", "score_boost",    {"multiplier": 1.30}, "Senegal bonus"),
        ("Koulibaly Stone",      "Kalidou Koulibaly",   "SN", "DEF", "defense_boost",  {"multiplier": 1.50}, "Senegal CB"),
        ("Hakimi Rocket",        "Achraf Hakimi",       "MA", "DEF", "defense_boost",  {"multiplier": 1.50}, "Morocco RB"),
        ("Ziyech Wand",          "Hakim Ziyech",        "MA", "MID", "score_boost",    {"multiplier": 1.25}, "Morocco winger"),
        ("Onana Reflex",         "André Onana",         "CM", "GK",  "defense_boost",  {"multiplier": 1.50}, "Cameroon GK"),
        ("Boateng Brick",        "Jérôme Boateng",      "GH", "DEF", "defense_boost",  {"multiplier": 1.40}, "Ghana CB"),
        ("Partey Power",         "Thomas Partey",       "GH", "MID", "captain_boost",  {"multiplier": 1.40}, "Ghana captain"),
        ("Iheanacho Sleek",      "Kelechi Iheanacho",   "NG", "FWD", "score_boost",    {"multiplier": 1.30}, "Nigeria bonus"),
        ("Osimhen Mask",         "Victor Osimhen",      "NG", "FWD", "score_boost",    {"multiplier": 1.35}, "Nigeria striker"),
        ("Lookman Wonder",       "Ademola Lookman",     "NG", "FWD", "score_boost",    {"multiplier": 1.30}, "Nigeria winger"),
        ("Chukwueze Dribble",    "Samuel Chukwueze",    "NG", "FWD", "score_boost",    {"multiplier": 1.25}, "Nigeria RW"),
        ("Trossard Pulse",       "Leandro Trossard",    "BE", "FWD", "score_boost",    {"multiplier": 1.20}, "Belgium forward"),
        ("Saka Star Boy",        "Bukayo Saka",         "GB", "FWD", "score_boost",    {"multiplier": 1.25}, "England winger"),
        ("Foden Stockport Iniesta", "Phil Foden",       "GB", "MID", "score_boost",    {"multiplier": 1.25}, "England playmaker"),
        ("Rice Anchor",          "Declan Rice",         "GB", "MID", "captain_boost",  {"multiplier": 1.30}, "England DM"),
        ("Pickford Wall",        "Jordan Pickford",     "GB", "GK",  "defense_boost",  {"multiplier": 1.40}, "England GK"),
        ("Trippier Right",       "Kieran Trippier",     "GB", "DEF", "defense_boost",  {"multiplier": 1.30}, "England RB"),
        ("Kane Captain",         "Harry Kane",          "GB", "FWD", "score_boost",    {"multiplier": 1.30}, "England captain & striker"),
        ("Pulisic American",     "Christian Pulisic",   "US", "FWD", "score_boost",    {"multiplier": 1.20}, "USA winger"),
        ("Reyna Stars",          "Giovanni Reyna",      "US", "MID", "outcome_boost",  {"multiplier": 1.20}, "USA bonus"),
        ("Modric Spirit",        "Luka Modrić",         "HR", "MID", "captain_boost",  {"multiplier": 1.35}, "Croatia maestro"),
    ]
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
        "id": "pool-cloudypitch-unified",
        "kind": "fantasy_predictions_unified",
        "competition_id": None,
        "title": "Cloudy Pitch Grand Prize Pool",
        "amount_usd_cents": 250_000,      # $2,500 base
        "currency": "USD",
        "status": "live",
    },
    {
        "id": "pool-wc2026-fantasy",
        "kind": "fantasy_wc2026",
        "competition_id": "fantasy-wc2026",
        "title": "FIFA WC 2026 Grand Prize Pool",
        "amount_total_ngn": 50_000_000,
        "amount_usd_cents": 3_000_000,
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
        "amount_usd_cents": 100_000,   # $1,000 base
        "currency": "USD",
        "payout_structure": [
            {"rank_min": 1, "rank_max": 1, "pct": 50},
            {"rank_min": 2, "rank_max": 2, "pct": 30},
            {"rank_min": 3, "rank_max": 3, "pct": 20},
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
    # One-time migration: legacy seeds named the star cards "Star Card 1..50".
    # Rename those rows IN PLACE (preserving id, so any user_cards.card_id
    # references stay valid) to the new descriptive names + add position +
    # canonical player name. STAR_CARDS preserves the original index order.
    for i, c in enumerate(STAR_CARDS):
        legacy_name = f"Star Card {i+1}"
        legacy = await db.legend_cards.find_one({"name": legacy_name}, {"_id": 0, "id": 1})
        if legacy:
            await db.legend_cards.update_one(
                {"id": legacy["id"]},
                {"$set": {
                    "name": c["name"],
                    "player_name": c["player_name"],
                    "country_code": c["country_code"],
                    "position": c.get("position", "ANY"),
                    "tier": c["tier"],
                    "price_usd_cents": c["price_usd_cents"],
                    "effect_type": c["effect_type"],
                    "effect_value": c["effect_value"],
                    "description": c["description"],
                }},
            )
    for c in ALL_CARDS:
        # Upsert by the canonical card `name`. `position` always upserts so
        # existing rows pick up the new field.
        on_insert = {k: v for k, v in c.items() if k not in ("price_usd_cents", "tier", "position", "description", "effect_type", "effect_value")}
        on_insert["created_at"] = utcnow_iso()
        always_set = {
            "tier": c["tier"],
            "position": c.get("position", "ANY"),
            "price_usd_cents": c["price_usd_cents"],
            "description": c.get("description", ""),
            "effect_type": c.get("effect_type"),
            "effect_value": c.get("effect_value"),
        }
        await db.legend_cards.update_one(
            {"name": c["name"]},
            {"$setOnInsert": on_insert, "$set": always_set},
            upsert=True,
        )
    # Fantasy comp
    await db.fantasy_competitions.update_one(
        {"id": WC2026_COMPETITION["id"]},
        {"$set": {**WC2026_COMPETITION, "created_at": utcnow_iso()}},
        upsert=True,
    )
    # Prize pools — IMPORTANT: only set the amount on FIRST insert, otherwise
    # admin edits get clobbered every time the server boots.
    for p in PRIZE_POOLS:
        # Critical: MongoDB rejects an upsert where the same field appears in
        # BOTH `$setOnInsert` and `$set` (that includes `**p` spreading every
        # field). So we explicitly split the payload:
        #   IMMUTABLE_FIELDS → only `$setOnInsert` (set once, never changed)
        #   MUTABLE_FIELDS   → only `$set` (display copy that admins can
        #                       reseed without losing running totals)
        IMMUTABLE = ("id", "kind", "competition_id", "currency", "amount_usd_cents", "amount_total_ngn")
        MUTABLE   = ("title", "status", "image_url", "payout_structure", "starts_at", "ends_at")
        set_on_insert = {k: p[k] for k in IMMUTABLE if k in p}
        set_on_insert["created_at"] = utcnow_iso()
        set_always = {k: p[k] for k in MUTABLE if k in p}
        await db.prize_pools.update_one(
            {"id": p["id"]},
            {"$setOnInsert": set_on_insert, "$set": set_always},
            upsert=True,
        )
        # ---- SELF-HEAL the base if it was corrupted (issue: previous
        # `_contribute_to_pool` versions stored card revenue into
        # `amount_usd_cents` instead of `cards_cut_usd_cents`, so existing
        # production pools may have `amount_usd_cents` BELOW the seeded
        # value). Restore the seeded base whenever the live value is lower,
        # and log the correction to `audit_log` so it's traceable.
        seeded_base = p.get("amount_usd_cents") or 0
        live = await db.prize_pools.find_one({"id": p["id"]}, {"_id": 0, "amount_usd_cents": 1})
        if live and seeded_base and int(live.get("amount_usd_cents") or 0) < seeded_base:
            old = int(live.get("amount_usd_cents") or 0)
            await db.prize_pools.update_one(
                {"id": p["id"]},
                {"$set": {"amount_usd_cents": seeded_base,
                          "self_healed_at": utcnow_iso()}},
            )
            await db.audit_log.insert_one({
                "id": new_id(), "user_id": "system", "email": "system@cloudypitch",
                "action": "prize_pool_self_heal",
                "metadata": {"pool_id": p["id"], "old_amount_usd_cents": old,
                             "new_amount_usd_cents": seeded_base,
                             "reason": "amount_usd_cents below seeded base — corruption from legacy contribution path"},
                "created_at": utcnow_iso(),
            })
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
