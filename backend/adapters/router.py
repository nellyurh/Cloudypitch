"""Sport → provider routing."""
SPORT_PROVIDER = {
    "football": "sportmonks",
    "basketball": "api-sports",
    "nba": "api-sports",
    "baseball": "api-sports",
    "hockey": "api-sports",
    "rugby": "api-sports",
    "handball": "api-sports",
    "volleyball": "api-sports",
    "mma": "api-sports",
    "f1": "api-sports",
    "afl": "api-sports",
    "tennis": "statpal",
    "cricket": "statpal",
    "golf": "statpal",
    "esports": "statpal",
    "horse-racing": "statpal",
}


def provider_for(sport_slug: str) -> str:
    return SPORT_PROVIDER.get(sport_slug, "unknown")
