# Cloudy Pitch — PRD

## Original Problem Statement
Global multi-sport livescore + predictions + fantasy platform launching for FIFA WC 2026. Sofascore-inspired dense UI. African football core audience, USD pricing with NGN supported. Live at https://cloudypitch.com.

## Tech Stack
- React 18 + Tailwind + Shadcn UI (frontend)
- FastAPI + Motor MongoDB (backend) on Caddy + Docker on Contabo VPS
- Opaque cookie auth
- Sportmonks (football), API-Sports (other sports), Trybit/CryptoCloud (crypto deposits), PocketFi (NGN), Google AdSense

## Implemented (rolling)
### 2026-02-10 (this session)
- **Mini-game settlement engine (P0 fix)** — New `/app/backend/wc_settler.py` finalises `wc_games` after their dependent WC matches finish (FT/AET/PEN). Per-entry pipeline: aggregate player stats from `match_events`/`match_lineups` → `compute_player_points` (existing FPL-style engine, GK/DEF/MID/FWD goal weighting, clean-sheets, saves, minutes, MOTM, cards) → captain ×2 (vice ×2 fallback) → applied legend-card boost (cards apply only to their targeted player) → game `points_multiplier`. Writes `points_scored`, `raw_points`, `breakdown_by_player`, `rank_in_game`, `settled_at` on each entry and flips `wc_games.status` → `settled`. Auto background loop (`wc_games_settler_loop`) scans every 5 min; admin endpoints `POST /api/admin/wc/games/{id}/settle` and `POST /api/admin/wc/games/settle-due` for manual triggers. Idempotent, with `force=true` re-settle. Aggregates feed the combined `/api/leaderboard` (`wc_fantasy_points`) and the per-game / overall WC leaderboards automatically.
  - **Test**: `/app/backend/tests/test_wc_settler.py` seeds a synthetic FT match + captain striker with 2 goals → asserts 20 pts (4 × 2 goals + 2 mins) × captain×2, rank 1, game flipped to settled, idempotency holds, aggregation pipeline reflects score. Passes.
- **Brand logo flash glitch fix (P1)** — `Brand.jsx` now hides itself behind a transparent same-size placeholder until the first `/brand` GET resolves; no more "cp-mark.png + CLOUDYPITCH" fallback flashing for ~200ms before the admin-uploaded logo swaps in. `loaded` flag added to the brand cache; placeholder reserves header layout space so nothing shifts.

### 2026-02-09
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
- `POST /api/admin/wc/games/{id}/settle?force=true|false` — manual single-game settlement
- `POST /api/admin/wc/games/settle-due` — manual sweep of all settle-able closed games (same job background loop runs)
- `POST /api/cards/daily-drop` — matchday completion reward (cookie-auth)
- `POST /api/cards/check-drop` — legacy every-5-actions reward (unchanged)
- `GET /api/brand` — now returns `brand_favicon_url`
