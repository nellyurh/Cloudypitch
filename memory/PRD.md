# Cloudy Pitch — PRD

## Original Problem Statement
Global multi-sport livescore + predictions + fantasy platform launching for FIFA WC 2026. Sofascore-inspired dense UI. African football core audience, USD pricing with NGN supported. Live at https://cloudypitch.com.

## Tech Stack
- React 18 + Tailwind + Shadcn UI (frontend)
- FastAPI + Motor MongoDB (backend) on Caddy + Docker on Contabo VPS
- Opaque cookie auth
- Sportmonks (football), API-Sports (other sports), Trybit/CryptoCloud (crypto deposits), PocketFi (NGN), Google AdSense

## Implemented (rolling)
### 2026-02-10 (this session — part 4: free-card bug fix + UX polish + mobile fixes)
- **🚨 CRITICAL: Free card bug fixed** — `POST /api/cards/{id}/purchase` was creating a `user_card` unconditionally with NO wallet check, so any signed-in user could click a card and receive it for free. Now: backend reads `users.wallet_balance_usd_cents`, atomically debits with a guarded `update_one({_id, balance >= price})`, refuses with `402 Insufficient wallet balance. Card costs $X.XX, you have $Y.YY (short by $Z.ZZ)` if short, and returns the new balance in the response. Double-click / race-safe.
  - **Test**: `tests/test_paid_purchase.py` — zero-balance buy → 402 + no card granted; funded buy debits correctly. Passes.
- **Single-use UX cleanup** — Removed every reference to "5 uses left" / "+1 use for $0.20 recharge" since cards are single-use. My Cards row now shows tier pill + name + player + an `x{n}` qty indicator only when the user owns multiple copies; 0-use rows auto-filtered out of the grid. BuyCardModal copy updated ("+5 uses…" → "{n} cards · $X each · one use each"). BuildTeam BoostCardsPanel + WcGames card list strip the "uses left" suffix, keep the boost % and only annotate `· ×N owned` when N > 1.
- **Per-tier prize distribution shows BASE + bonus split** — User asked: "the leaderboard supposed to show the original base distribution which we gave." `PrizeBreakdown` now renders each tier with the total (cp-lime), a small dot legend (Base · Cards bonus), and a sub-row `$1,000.80 + $0.13` in respective colors so the original base split is always visible alongside the live card-revenue bonus.
- **Mobile responsiveness** — Legend Cards catalog uses a new `useResponsiveCardSize()` hook that picks 130/150/170/190/220 px depending on viewport width — phones get smaller cards so the 2-col grid fits cleanly without bleed. Catalog grid switched to `justify-items-center` + responsive `gap-3 sm:gap-4`. Leaderboards tabs row got horizontal scroll (`overflow-x-auto no-scrollbar`) so "Referrals" no longer clips on 375px screens; H1 shrunk to `text-xl sm:text-2xl`. BuyCardModal art uses dual size (100px mobile / 140px desktop).

### 2026-02-10 (part 3 — single-use cards + full-loop simulation proof)
- **Cards are now SINGLE-USE** — `STARTER_USES = 1`, `RECHARGE_USES = 1`. Updated everywhere uses are granted (auth_routes signup welcome, ads.py rewarded video, payments.py card_purchase / card_recharge webhook, card_drops.py daily-drop fallback). Frontend strings ("+5 uses for $0.20 recharge" → "+1 use", "Watch ad → +5 card uses" → "+1 card use"). Each card = one use only; users buy / earn fresh copies for repeat boosts.
- **Per-player card boost actually fires in fantasy** — fixed `card_matches` so the new per-player targeting model is honored: in fantasy scope, once the position lock passes, the card always fires (legacy country/continent checks were a relic of the prediction flow and were silently blocking 99% of cards from boosting their explicit target). `captain_boost` / `defense_boost` still gated by role/position; everything else opens up. Prediction-scope rules unchanged.
- **Full-loop simulation test (`tests/test_simulation_full_loop.py`)** — proves the entire chain works end-to-end without faith. Seeds 2 synthetic teams (Alpha 15-man / Beta 15-man), 1 finished match (Alpha 3-0 Beta with captain FWD scoring 2 + star MID scoring 1), 3 users (A: FWD card "Pelé Spirit" on captain FWD · B: MID card "Maradona Hand" on star MID · C: control, no cards), runs the settler, asserts:
  - USER A (97 pts · rank 1) > USER C (77 pts) — proves FWD card boosted captain ×2 + ×2.0 (delta = 20 pts, exactly the card uplift)
  - USER B (93 pts · rank 2) > USER C — proves MID card boosted scorer
  - `breakdown_by_player` captain row shows `base_points=10, multiplier=2, card_boost=1.0, points=40` for A vs `card_boost=0.0, points=20` for C — captain × card stacking confirmed
  - `wc_games.status` flipped to `settled`, `settled_entry_count=3`
  - Leaderboard aggregation pipeline returns the correct A > B > C ranking
  - `STARTER_USES = 1` asserted (single-use enforced in code)
  Run: `python /app/backend/tests/test_simulation_full_loop.py` — all 7 phases green.

### 2026-02-10 (part 2 — Legend Cards: player-targeting + admin price editor)
- **Per-player legend-card targeting on main 15-man squad** — main `Build a Team` now mirrors the WC mini-game pattern: each owned card boosts ONE picked player. New `BoostCardsPanel` + `CardTargetPicker` components, persisted via `applied_cards: [{user_card_id, target_player_id}]` on the `FantasySquadIn` payload. Legacy `applied_card_ids` flat list preserved for backward compatibility.
- **Position lock on every card** — added `position` field (`GK`/`DEF`/`MID`/`FWD`/`ANY`) to all 101 legend cards. Backend validates in BOTH `/api/wc/games/{id}/enter` AND `/api/fantasy/squad`. `compute_card_boost` honors the lock so settled points only fire when the card's `position` matches the targeted player's. Client gates the target picker (grays out non-matching positions with `FWD only` etc.).
- **50 named Star cards** — replaced "Star Card 1..50" with curated names ("Vidal Iron Lung", "Cavani El Matador", "Bale Wales Wonder", "Pogba Dab", "Hazard Eden", "Kane Captain", "Saka Star Boy", etc.) — each carries the right player name, country code, AND position. One-time in-place migration so existing user_cards inventories stay valid.
- **Admin card price/position editor** — new `Cards` tab in `/admin` lets admins (a) bulk re-price every card in a tier (surge pricing), or (b) per-row edit price (USD cents) + position lock. Endpoints: `GET /api/admin/cards`, `PATCH /api/admin/cards/{id}`, `POST /api/admin/cards/bulk-price`. Every edit writes an `audit_log` row.
- **Pitch player-circle badge** — `PitchSlot` (BuildTeam) now renders a tiny gold "×N.NN" multiplier pill at the top-left of the player avatar when a boost card is attached, FUT-style (gold gradient, ring shadow, tooltip showing the card name + %).

### 2026-02-10 (part 1)
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
- `GET /api/admin/cards?tier=1|2|3` — admin list with edit fields
- `PATCH /api/admin/cards/{id}` — edit `price_usd_cents`, `position`, `description`
- `POST /api/admin/cards/bulk-price` — surge re-price every card of a tier
- `POST /api/admin/wc/games/{id}/settle?force=true|false` — manual single-game settlement
- `POST /api/admin/wc/games/settle-due` — manual sweep of all settle-able closed games (same job background loop runs)
- `POST /api/cards/daily-drop` — matchday completion reward (cookie-auth)
- `POST /api/cards/check-drop` — legacy every-5-actions reward (unchanged)
- `GET /api/brand` — now returns `brand_favicon_url`

## Key payload changes
- `POST /api/fantasy/squad` now accepts `applied_cards: [{user_card_id, target_player_id}]` (per-player). Old `applied_card_ids: [...]` flat list still accepted but soft-deprecated.
- `legend_cards.position` (GK/DEF/MID/FWD/ANY) — validation enforces lock on application.
