"""WC Past-tournaments archive — hand-curated highlights tied to Legend Cards.

Used by /api/worldcup/past to power the "Past Tournaments" tab on the WC Hub.
Each legend below points to its matching `legend_cards.name` so the UI can deep-link
to the live card listing as a marketing surface.

Add entries here as we learn more about each player's WC performance.
"""

PAST_TOURNAMENTS = [
    {
        "year": 2022, "host": "Qatar", "champion": "Argentina",
        "final": "Argentina 3-3 France (4-2 pens)",
        "golden_ball": "Lionel Messi",
        "golden_boot": "Kylian Mbappé (8 goals)",
        "image_url": "https://images.unsplash.com/photo-1521410023453-3a0686390a73?w=800&q=80",
        "highlights": [
            {"player": "Lionel Messi",   "card": "Lionel Messi", "country_code": "AR",
             "stat": "7 goals · 3 assists · Golden Ball · Lifted the trophy", "moment": "Captained Argentina to their 3rd WC, finally completing his GOAT case."},
            {"player": "Kylian Mbappé",  "card": "Kylian Mbappé", "country_code": "FR",
             "stat": "8 goals · Golden Boot · Final hat-trick", "moment": "First final hat-trick since 1966 — on the losing side."},
            {"player": "Emiliano Martinez", "card": None, "country_code": "AR",
             "stat": "Golden Glove · Final save vs Kolo Muani", "moment": "Saved the cup in the dying seconds of extra time."},
        ],
    },
    {
        "year": 2018, "host": "Russia", "champion": "France",
        "final": "France 4-2 Croatia",
        "golden_ball": "Luka Modric",
        "golden_boot": "Harry Kane (6 goals)",
        "image_url": "https://images.unsplash.com/photo-1551958219-acbc608c6377?w=800&q=80",
        "highlights": [
            {"player": "Kylian Mbappé",  "card": "Kylian Mbappé",  "country_code": "FR",
             "stat": "4 goals · Best Young Player · Goal in the final at 19", "moment": "Announced himself as the future of football."},
            {"player": "Luka Modric",    "card": "Luka Modric",    "country_code": "HR",
             "stat": "Golden Ball · Carried Croatia to the final", "moment": "Master-class in midfield orchestration through three knockout extra-times."},
            {"player": "Harry Kane",     "card": "Harry Kane",     "country_code": "GB",
             "stat": "6 goals · Golden Boot", "moment": "England's first finalist Golden Boot since 1986."},
        ],
    },
    {
        "year": 2014, "host": "Brazil", "champion": "Germany",
        "final": "Germany 1-0 Argentina (Götze 113')",
        "golden_ball": "Lionel Messi",
        "golden_boot": "James Rodriguez (6 goals)",
        "image_url": "https://images.unsplash.com/photo-1518604666860-9ed391f76460?w=800&q=80",
        "highlights": [
            {"player": "Miroslav Klose", "card": "Miroslav Klose", "country_code": "DE",
             "stat": "All-time WC top scorer · 16 goals across 4 tournaments", "moment": "Surpassed Ronaldo R9's 15-goal record during Germany's 7-1 vs Brazil."},
            {"player": "James Rodriguez","card": "James Rodriguez","country_code": "CO",
             "stat": "6 goals · Golden Boot · Goal of the tournament", "moment": "Chest-and-volley against Uruguay that defined the World Cup."},
            {"player": "Lionel Messi",   "card": "Lionel Messi",   "country_code": "AR",
             "stat": "4 goals · Golden Ball", "moment": "So close — beaten by Götze's extra-time strike in the Maracanã."},
        ],
    },
    {
        "year": 2010, "host": "South Africa", "champion": "Spain",
        "final": "Spain 1-0 Netherlands (Iniesta 116')",
        "golden_ball": "Diego Forlán",
        "golden_boot": "Müller / Sneijder / Forlán / Villa (5 each)",
        "image_url": "https://images.unsplash.com/photo-1623091410901-00e2d268901f?w=800&q=80",
        "highlights": [
            {"player": "Andrés Iniesta", "card": "Andres Iniesta", "country_code": "ES",
             "stat": "Final winning goal · 116th minute", "moment": "Tiki-taka's defining moment — Spain's first WC."},
            {"player": "Diego Forlán",   "card": None, "country_code": "UY",
             "stat": "5 goals · Golden Ball", "moment": "Single-handedly dragged Uruguay to 4th place."},
        ],
    },
    {
        "year": 2002, "host": "Korea/Japan", "champion": "Brazil",
        "final": "Brazil 2-0 Germany",
        "golden_ball": "Oliver Kahn",
        "golden_boot": "Ronaldo R9 (8 goals)",
        "image_url": "https://images.unsplash.com/photo-1551958219-acbc608c6377?w=800&q=80",
        "highlights": [
            {"player": "Ronaldo Nazário", "card": "Ronaldo Nazario", "country_code": "BR",
             "stat": "8 goals · Both goals in the final · Golden Boot", "moment": "Redemption arc after 1998 — bagged 2 vs Germany to lift Brazil's 5th."},
            {"player": "Rivaldo",         "card": "Rivaldo",         "country_code": "BR",
             "stat": "5 goals · scored in every group game", "moment": "The other half of Brazil's deadly attack."},
            {"player": "Ronaldinho",      "card": "Ronaldinho",      "country_code": "BR",
             "stat": "Lobbed Seaman from 40 yards vs England", "moment": "One of the most iconic free-kicks in WC history."},
        ],
    },
    {
        "year": 1998, "host": "France", "champion": "France",
        "final": "France 3-0 Brazil",
        "golden_ball": "Ronaldo R9",
        "golden_boot": "Davor Šuker (6 goals)",
        "image_url": "https://images.unsplash.com/photo-1574629810360-7efbbe195018?w=800&q=80",
        "highlights": [
            {"player": "Zinedine Zidane","card": "Zinedine Zidane","country_code": "FR",
             "stat": "2 headers in the final vs Brazil", "moment": "First France WC — at home, on Brazil's expense."},
            {"player": "Ronaldo Nazário","card": "Ronaldo Nazario","country_code": "BR",
             "stat": "Pre-final mystery · Golden Ball", "moment": "Reportedly had a seizure hours before kick-off; Brazil collapsed."},
        ],
    },
    {
        "year": 1986, "host": "Mexico", "champion": "Argentina",
        "final": "Argentina 3-2 West Germany",
        "golden_ball": "Diego Maradona",
        "golden_boot": "Gary Lineker (6 goals)",
        "image_url": "https://images.unsplash.com/photo-1551958219-acbc608c6377?w=800&q=80",
        "highlights": [
            {"player": "Diego Maradona", "card": "Diego Maradona", "country_code": "AR",
             "stat": "5 goals · 5 assists · Golden Ball", "moment": "Hand of God + Goal of the Century vs England — 4 minutes apart."},
        ],
    },
    {
        "year": 1970, "host": "Mexico", "champion": "Brazil",
        "final": "Brazil 4-1 Italy",
        "golden_ball": "Pelé",
        "golden_boot": "Gerd Müller (10 goals)",
        "image_url": "https://images.unsplash.com/photo-1518604666860-9ed391f76460?w=800&q=80",
        "highlights": [
            {"player": "Pelé",        "card": "Pelé",        "country_code": "BR",
             "stat": "4 goals · 6 assists · 3rd WC title", "moment": "The greatest team ever assembled — and Pelé's final WC."},
            {"player": "Gerd Müller", "card": "Müller", "country_code": "DE",
             "stat": "10 goals · Golden Boot · Hat-trick vs Peru", "moment": "Set a tournament-scoring template for decades."},
        ],
    },
    {
        "year": 1958, "host": "Sweden", "champion": "Brazil",
        "final": "Brazil 5-2 Sweden",
        "golden_ball": "Didi",
        "golden_boot": "Just Fontaine (13 goals)",
        "image_url": "https://images.unsplash.com/photo-1574629810360-7efbbe195018?w=800&q=80",
        "highlights": [
            {"player": "Pelé",          "card": "Pelé",          "country_code": "BR",
             "stat": "6 goals at age 17 · Final hat-trick · Brazil's 1st WC", "moment": "A 17-year-old changed football forever."},
            {"player": "Just Fontaine", "card": None, "country_code": "FR",
             "stat": "13 goals — still a single-tournament record", "moment": "Untouchable record nearly 70 years later."},
        ],
    },
]
