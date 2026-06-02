"""Curated WC2026 star player tier list — used to override the synthetic price formula
so genuine elite players are always at the top of the price ladder.

Tiers (price floor in £m — applied AFTER the synthetic base/position; whichever is higher wins):
  S+ : £10.0  — Ballon d'Or-tier / once-in-a-generation
  S  : £9.0   — World-class regulars
  A+ : £8.0   — Top-club starters with established international form
  A  : £7.0   — Strong international starters

Matching is case-insensitive, ignores diacritics, and accepts last-name OR full-name fragments.
"""
import unicodedata

S_PLUS = {
    # Striker / FWD royalty
    "kylian mbappe", "erling haaland", "vinicius junior", "vini jr",
    "lionel messi", "neymar",
    # AM / MID kings
    "jude bellingham", "rodri", "kevin de bruyne",
    # Defenders
    "virgil van dijk",
    # Keepers
    "thibaut courtois", "alisson",
}

S_TIER = {
    "harry kane", "mohamed salah", "lautaro martinez",
    "phil foden", "bukayo saka", "florian wirtz", "pedri",
    "rodrygo", "lamine yamal", "musiala", "jamal musiala", "antoine griezmann",
    "joshua kimmich", "luka modric", "toni kroos",
    "ruben dias", "william saliba", "antonio rudiger", "marquinhos",
    "ederson", "diogo costa", "donnarumma", "gianluigi donnarumma",
    "trent alexander-arnold",
    "victor osimhen", "rafael leao", "leao",
    "darwin nunez", "julian alvarez", "alvaro morata",
    "bruno fernandes", "bernardo silva", "ilkay gundogan", "gundogan",
    "kai havertz", "gabriel jesus", "gabriel martinelli",
    "son heung-min", "heung min son",
    "achraf hakimi",
}

A_PLUS_TIER = {
    "declan rice", "marcus rashford", "cole palmer",
    "kane", "saka", "rashford",
    "raphael varane", "theo hernandez", "aurelien tchouameni",
    "lautaro", "messi", "nico paz", "alexis mac allister",
    "frenkie de jong", "memphis depay", "cody gakpo",
    "leon goretzka", "leroy sane", "serge gnabry", "florian neuhaus",
    "alessandro bastoni", "nicolo barella", "federico chiesa",
    "ferran torres", "mikel merino", "dani olmo",
    "andre silva", "joao felix", "bruno guimaraes",
    "vitinha", "joao cancelo",
    "luis diaz", "james rodriguez",
    "richarlison", "raphinha", "casemiro",
    "thiago silva", "alphonso davies",
    "khvicha kvaratskhelia", "georginio rutter",
    "edin dzeko",
}

A_TIER = {
    "ollie watkins", "harry maguire", "kyle walker", "kalvin phillips",
    "jordan pickford", "aaron ramsdale", "callum wilson",
    "ousmane dembele", "kingsley coman", "anthony martial",
    "jadon sancho", "mason mount", "jack grealish",
    "alvaro odriozola", "nico williams", "fabian ruiz",
    "manuel akanji", "ricardo rodriguez", "noah okafor",
    "denzel dumfries", "matthijs de ligt", "memphis", "wijnaldum",
    "jamal lewis", "wesley fofana", "william saliba",
    "edouard mendy", "yves bissouma", "moises caicedo",
    "andre onana", "wilfred ndidi", "alex iwobi",
    "denis zakaria", "nordi mukiele",
    "youssef en-nesyri", "noussair mazraoui", "sofyan amrabat",
    "moussa diaby", "boubacar kamara",
    "destiny udogie", "manuel locatelli",
    "alvaro odriozola", "jorginho", "jorge resurrection",
    "andreas christensen", "thomas delaney",
    "luis suarez", "facundo torres",
}


def _norm(s: str) -> str:
    """Lowercase + strip diacritics + remove non-alphanumeric (keep spaces)."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = "".join(c for c in s.lower() if c.isalnum() or c == " ")
    return " ".join(s.split())


def star_floor(player_name: str) -> float:
    """Return the price floor in £m for this player's name (0 if not a star)."""
    n = _norm(player_name)
    if not n:
        return 0.0
    words = set(n.split())
    last = n.split()[-1] if " " in n else n
    for tier_set, floor in [(S_PLUS, 10.0), (S_TIER, 9.0), (A_PLUS_TIER, 8.0), (A_TIER, 7.0)]:
        for tag in tier_set:
            tag_norm = _norm(tag)
            tag_words = tag_norm.split()
            # Full multi-word match (e.g. "kevin de bruyne" must appear contiguously)
            if " " in tag_norm and tag_norm in n:
                return floor
            # Single-token tag — require exact word match, NOT substring (avoids "rodri" → "rodriguez")
            if len(tag_words) == 1 and tag_words[0] in words:
                return floor
            # Also accept exact last-name match for single-token tags
            if len(tag_words) == 1 and tag_words[0] == last:
                return floor
    return 0.0
