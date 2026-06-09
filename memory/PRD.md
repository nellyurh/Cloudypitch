# Cloudy Pitch — PRD

## Original Problem Statement
Global multi-sport livescore + predictions + fantasy platform launching for FIFA WC 2026. Sofascore-inspired dense UI. African football core audience, USD pricing with NGN supported. Live at https://cloudypitch.com.

## Tech Stack
- React 18 + Tailwind + Shadcn UI (frontend)
- FastAPI + Motor MongoDB (backend) on Caddy + Docker on Contabo VPS
- Opaque cookie auth
- Sportmonks (football), API-Sports (other sports), Trybit/CryptoCloud (crypto deposits), PocketFi (NGN), Google AdSense

## Implemented (rolling)
### 2026-02-09 (this session)
- **LegendCardArt premium redesign** — 3 distinct FUT/FIFA-style tier frames (Gold rays, Elite holo, Epic lava) with Cinzel serif, stat grid, corner filigree, sheen sweep, noise grain.
- **Verified Header "WC26"** + stacked sport-tab icons (icon-on-top, Sofascore parity).
- **API-Sports basketball stats wiring** — Extended ingestion LABEL_ALIASES (twopoint_goals, threepoint_goals, freethrows_goals, personal_fouls), flattened the rebounds dict, backfilled 8 existing docs. Frontend BoxScore now safely renders shooting-stat dicts. Verified: Free Throws, 3-Pointers, Field Goals dual-ring gauges + Rebounds/Assists/Turnovers/Steals/Blocks compare bars render correctly.
- **Admin save-button audit / SiteConfigForm dirty-state** — Sticky save bar with "● Unsaved changes" amber pill; Save button label switches Saved/Save changes; disabled when no diff.
- **Admin Favicon Upload** — 5th brand slot ("favicon"); `_applyFavicon()` dynamically rewrites `<link rel="icon">` in `<head>` on app boot using uploaded favicon (or fallback to brand mark).
- **Matchday Drop System (P1)** — `POST /api/cards/daily-drop` grants ONE Star-tier (3) Legend Card after each UTC day if the user took any qualifying action (prediction / fantasy edit / WC game entry) the previous day. On WC Final day (2026-07-19) a 10% chance replaces it with a GOLD drop. Idempotent via `card_drops_log`. Hooks added in predictions, fantasy, and wc_games submit endpoints. `DailyDropWatcher` component shows a celebratory Sonner toast with the FUT card art.

### Earlier
- WC Hub 3-col redesign, Header group ticker, Trybit/PocketFi/AdSense, team management formations+bench, transfer-card consumption, /team/:name page, watermarks removed.

## P1 Backlog
- Flutter wrapper readiness (token/cookie path documentation)
- Real Email Verification — BLOCKED (awaiting Resend/SendGrid key)

## P2 Backlog
- Refactor Admin.jsx (~920 lines) into sub-tabs (pre-existing lint blockers from old code, not regressions)
- `DailyDropWatcher` could also fire on `visibilitychange` to catch users who keep tab open across UTC midnight (currently only on initial mount)

## Mocked / Blocked
- Real Emails: MOCKED (returns dev_token)
- KYC: MOCKED

## Test credentials
See /app/memory/test_credentials.md

## Key endpoints added
- `POST /api/cards/daily-drop` — matchday completion reward (cookie-auth)
- `POST /api/cards/check-drop` — legacy every-5-actions reward (unchanged)
- `GET /api/brand` — now returns `brand_favicon_url`
