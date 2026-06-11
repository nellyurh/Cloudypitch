// ISO-3166 alpha-2 codes for WC2026 participating nations (flagcdn.com lookup)
export const COUNTRY_CODES = {
  "Argentina": "ar",
  "Algeria": "dz",
  "Australia": "au",
  "Austria": "at",
  "Belgium": "be",
  "Bosnia and Herzegovina": "ba",
  "Brazil": "br",
  "Canada": "ca",
  "Cameroon": "cm",
  "Cape Verde": "cv",
  "Colombia": "co",
  "Costa Rica": "cr",
  "Croatia": "hr",
  "Curacao": "cw",
  "Czechia": "cz",
  "Czech Republic": "cz",
  "Denmark": "dk",
  "DR Congo": "cd",
  "Congo DR": "cd",
  "Democratic Republic of the Congo": "cd",
  "Ecuador": "ec",
  "Egypt": "eg",
  "England": "gb-eng",
  "France": "fr",
  "Germany": "de",
  "Ghana": "gh",
  "Haiti": "ht",
  "Honduras": "hn",
  "Iceland": "is",
  "Iran": "ir",
  "Iraq": "iq",
  "Italy": "it",
  "Ivory Coast": "ci",
  "Côte d'Ivoire": "ci",
  "Jamaica": "jm",
  "Japan": "jp",
  "Jordan": "jo",
  "Mexico": "mx",
  "Morocco": "ma",
  "Netherlands": "nl",
  "New Zealand": "nz",
  "Nigeria": "ng",
  "North Korea": "kp",
  "Norway": "no",
  "Panama": "pa",
  "Paraguay": "py",
  "Poland": "pl",
  "Portugal": "pt",
  "Qatar": "qa",
  "Saudi Arabia": "sa",
  "Scotland": "gb-sct",
  "Senegal": "sn",
  "Serbia": "rs",
  "South Africa": "za",
  "South Korea": "kr",
  "Korea Republic": "kr",
  "Spain": "es",
  "Sweden": "se",
  "Switzerland": "ch",
  "Tunisia": "tn",
  "Turkey": "tr",
  "Türkiye": "tr",
  "United States": "us",
  "Uruguay": "uy",
  "USA": "us",
  "Uzbekistan": "uz",
  "Wales": "gb-wls",
};

// flagcdn only serves a fixed set of widths — picking anything else (like w72)
// returns 404, which is what was breaking every match-card flag (size 36 →
// w72 → broken). Snap to the next supported width ≥ requested.
const FLAGCDN_WIDTHS = [20, 40, 80, 160, 320, 640, 1280, 2560];
function _snapFlagWidth(requested) {
  const n = Math.max(20, Number(requested) || 20);
  for (const w of FLAGCDN_WIDTHS) if (w >= n) return w;
  return FLAGCDN_WIDTHS[FLAGCDN_WIDTHS.length - 1];
}

export const flagUrl = (country, size = 32) => {
  const code = COUNTRY_CODES[country];
  if (!code) return null;
  return `https://flagcdn.com/w${_snapFlagWidth(size)}/${code}.png`;
};
