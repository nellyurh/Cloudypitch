# Cloudy Pitch — Product Requirements (Living Doc)

## Original Problem Statement
Build "Cloudy Pitch" — a global multi-sport livescore + predictions + fantasy platform with a prize pool. Launching for the FIFA World Cup 2026 (June 11, 2026). Audience: African football fans, Lagos-HQ.

Three integrated products:
1. **Livescores** — real-time scores/fixtures across 14 sports
2. **Predictions** — score predictions, points, leaderboards
3. **Fantasy** — WC2026 squad builder with weekly gameweeks

## Stack (decided)
- React (CRA + craco) + FastAPI + MongoDB on Emergent template.
- Will redeploy to user's Contabo VPS later. Same REST API will power a future Flutter app.

## User Choices Locked In
- Build everything end-to-end in v1
- Payment gateway deferred (Paystack/Flutterwave for later)
- Cookie session auth (NOT JWT) per spec
- Live data via Sportmonks (football), API-Sports (10 sports), StatPal (tennis/cricket/golf/horse-racing/esports) — keys provided by user, baked into `/app/backend/.env`
- Brand: Lime #A3E635, Forest deep #064E3B, Forest light #0F6E56; Red #FF3D52 reserved exclusively for live indicator
- Dark mode default + light toggle; Inter font; Sofascore-inspired 3-column layout; vertical-stacked match rows

## Architecture
- **Backend**: `/app/backend/server.py` (FastAPI) → `db.py`, `auth.py`, `models.py`, `cache.py`, `seed_data.py`, `ingestion.py`, `adapters/{sportmonks,apisports,statpal,router}.py`, `routes/{auth_routes,catalog,matches,worldcup,predictions,fantasy,cards,prize_pools,profile,search,admin}.py`
- **Frontend**: `/app/frontend/src/App.js` (BrowserRouter) → `lib/{api,auth,theme}.js(x)`, `components/{Layout,Header,Brand,MatchRow,LeagueGroup,LeftSidebar,RightRail}.jsx`, `pages/{Dashboard,SportPage,MatchDetail,LeaguePage,WorldCupHub,Predictions,Fantasy,LegendCards,PrizePool,Profile,Leaderboards,Search,SignIn,SignUp,Admin}.jsx`
- **Auth**: Opaque sha256 session tokens (NOT JWT) stored server-side in `sessions` collection; cookie `cp_session` HTTP-only, SameSite=lax, Secure, 30-day TTL. bcrypt 12 rounds. 5-fail lockout (15 min). Rate limits 5 signups/hr/IP & 10 signins/15min/IP. Audit log.
- **Ingestion**: Background asyncio tasks: Sportmonks fixture sync (today+7d) every 6h, Sportmonks live poller every 20s, StatPal tennis poller every 2min, stale-status sweep, initial sync of all sports on startup.
- **Data**: All endpoints prefixed `/api`. Same-origin between frontend and backend on the preview URL (cookie auth works).

## Implemented v1 (2026-05-27)
- ✅ 14 sports catalog, 100 legend cards (20 GOAT/30 Elite/50 Star), 12 WC2026 groups, WC2026 fantasy competition, 2 prize pools — all seeded on boot
- ✅ Sportmonks ingestion live (pulling 16-25 fixtures/day across Copa Libertadores, Premier League, Ligue 1, etc.)
- ✅ Auth (signup with starter pack of 5 Star cards, signin, signout, me, lockout, rate limits, audit log)
- ✅ Match list with filters (live/upcoming/finished), match detail (events/stats/lineups/h2h tabs), live passthrough endpoint with 5s cache
- ✅ Predictions (submit, my picks, leaderboard, settle for admins)
- ✅ Fantasy squad builder (positions, budget enforcement, captain/vice, leaderboard)
- ✅ Legend cards catalog page (3 tiers)
- ✅ Prize pool list + detail with payout breakdown
- ✅ Profile, leaderboards, search, user favorites
- ✅ Admin panel: stats, users (promote/deactivate), matches table, audit log, ingestion triggers (Sportmonks sync/live, API-Sports per sport, StatPal tennis), uploads (base64 logos)
- ✅ Dark/light theme toggle, Sofascore vertical-stacked match rows, red live pulse, lime accents
- ✅ Tennis tiebreaker superscript support in MatchRow
- ✅ 3-column responsive dashboard with left sidebar (countries+leagues) and right rail (WC countdown + leaderboard + featured pool)
- ✅ Backend tested 46/46 (100%) by testing agent

## Iteration 2 — Match Detail UI Polish (2026-05-28)
- ✅ Sportmonks event/stat type IDs mapped to human-readable names (Goal, Yellow Card, Substitution, Ball Possession %, Shots on Target, etc.) via nested `events.type` / `statistics.type` includes + `EVENT_TYPE_NAMES` & `STAT_TYPE_NAMES` fallback dicts in `adapters/sportmonks.py`
- ✅ `team_id` normalized to `sm-t-{id}` prefix across events/stats/lineups → enables correct home/away split on frontend
- ✅ Stale-data detection in `GET /api/matches/{id}` auto-refreshes legacy fixtures with numeric type IDs; also supports `?refresh=1` query param + UI refresh button
- ✅ New EventsList component: home-on-left / away-on-right layout, icons for Goal/Yellow Card/Red Card/Substitution/VAR, sub assist line, minute pill in center
- ✅ New StatsBars component: Sofascore-style mirrored bar charts, lime fill for winning side, % stats normalised, priority ordering
- ✅ New LineupPitch component: green pitch with center circle/penalty boxes/goals, player number badges (lime home / white away), formation auto-derived from position_code, full bench list
- ✅ Verified by testing agent (iteration 2): 100% backend + frontend pass

## Iteration 17 — Trends + Commentary + Sidelined surfaced (2026-05-29)

### Trends/MatchFacts tab
- New `Trends.jsx` component renders Sportmonks `matchfacts` with `natural_language` populated
- 3 sections: Home team (lime), Away team (sky), Head to Head (amber). Up to 10 facts each
- Each row has a category pill (STATISTICS / STREAKS / FORM / etc.)
- Backend filters down 759 raw facts → 60 readable natural-language sentences (saves payload size)
- Live verified: "Flamengo have 9 wins (37.5%) in their Serie A matches against Palmeiras (home only: 6, 66.67%)"

### Commentary tab
- New `Commentary.jsx` component renders minute-by-minute feed sorted newest-first
- Goals get green background + lime left border + Target icon
- Important moments get sky left border
- Verified: 60 commentary entries on Flamengo vs Palmeiras including "Goal! Paulinho scores with a left-footed shot"

### Sidelined / Injuries card
- New `SidelinedCard.jsx` renders below the LineupPitch on the Lineups tab
- 2-column layout (home / away), each row showing player avatar + name + injury reason
- Backend enriches via Sportmonks `sidelined.player` + `sidelined.type` includes
- Verified: 8 sidelined players including "Everton · Hip Injury", "Bruno Fuchs · Thigh Muscle Strain"

### Backend wiring
- Sportmonks include list expanded: `sidelined.player;sidelined.type;matchfacts.type`
- `upsert_sportmonks_fixture` now enriches:
  - `sidelined_raw` → `[{player_id, player_name, player_image, team_id, reason, type_id}]`
  - `comments` → `[{minute, extra_minute, text, is_goal, is_important, order}]`
  - `matchfacts` → `[{text, participant, basis, category, scope, type}]` (filtered to natural_language only, max 60)
- New `sportmonks_home_id` / `sportmonks_away_id` raw IDs persisted so SidelinedCard can map team_id correctly

### Test Results (iteration 17)
- Verified via Playwright screenshots: 3 new tabs (Commentary, Trends) + SidelinedCard render with real Sportmonks Pro data

## Iteration 16 — Sportmonks Pro data + AttackMomentum + Standings tab + API-Sports basketball stats (2026-05-29)

### Sportmonks Pro plan data wired (we were not consuming what we already pay for)
- `fetch_fixture()` include list expanded from 9 to 23 includes — adds weatherReport, tvStations.tvstation, referees.referee, referees.type, coaches, sidelined, pressure, predictions.type, trends, matchfacts, comments, expectedLineups, xGFixture, formations, group, aggregate, lineups.details.type, round, stage
- `upsert_sportmonks_fixture` reads from Sportmonks' lowercase keys (`weatherreport`, `tvstations`) and persists:
  - `weather` (flattened: `{temperature_celcius, type, icon, humidity, wind}`)
  - `tv_stations[]` (deduped list of names)
  - `referees[]` (with type: Referee / 1st Assistant / 2nd Assistant / 4th Official)
  - `pressure`, `predictions_raw`, `coaches`, `sidelined_raw`, `matchfacts`, `trends`, `comments`
- Verified on Flamengo vs Palmeiras: weather=21.99°C broken clouds, tv=[Bet365, Fanatiz], ref=Davi de Oliveira Lacerda

### Hero meta strip enhanced
- New chips: `hero-weather` (cloud + temp), `hero-tv` (TV icon + station names), `hero-ref` (User icon + main referee)
- Shows venue_city when available (e.g. "Estádio Jornalista Mário Filho, Rio de Janeiro")

### Attack Momentum sparkline (left rail)
- New `AttackMomentum.jsx` component — SVG dual-tone bar chart (lime up = home, sky down = away) per minute with HT marker at 45'
- New endpoint `GET /api/matches/{id}/momentum` reading `match.pressure[]`
- Empty-state fallback ("Will appear minute-by-minute once play starts") when pressure[] is empty (live-only data)

### Standings/Playoffs tab
- New `StandingsTable.jsx` lazy-loads on tab click via `GET /api/matches/{id}/standings`
- Reads from `db.standings` (populated by the hourly sportmonks standings sync)
- Both competing teams highlighted in lime; full league table with P/W/D/L/GF/GA/GD/Pts
- Tab labelled "Playoffs" for NBA, "Standings" for everything else
- Verified: 20 Brazilian Serie A rows · Palmeiras #1 (38pts), Flamengo #2 (31pts) both highlighted

### API-Sports basketball stats lazy fetch
- New adapter methods `fetch_game_statistics()` + `fetch_game_players()`
- New `_upsert_apisports_team_stats()` handles both API-Sports shapes (list of {name,value} and flat dict)
- `/api/matches/{id}?refresh=1` triggers it automatically for basketball/baseball/hockey/volleyball/rugby
- Now feeds the BasketballStatsView gauges + bars built in iteration 15

### Test Results (iteration 16)
- Backend: **7/7 pytest pass** · Frontend: **Playwright PASS** · No retest needed

## Iteration 15 — Sofascore-style Match Detail layout (2026-05-29)

### 3-column Sofascore aesthetic
- New `MatchHero` component: large team logos, big 4xl–5xl score with winning side highlighted lime, league country · league name header, meta strip (date · venue · format · broadcaster) — matches Sofascore hero faithfully
- 3-column layout (`260px | 1fr | 260px`): left rail = ScoreBox + Odds + Ad · center = Tabs · right rail = "Follow this match" promo + Ad
- Sticky tabs row + tab-aware content

### New components (`/components/match/StatGauges.jsx`)
- `<StatGauge>` — dual SVG rings (lime home / sky away) with shot tally inside, used for basketball Free Throws / 2-pointers / 3-pointers / Field Goals
- `<CompareBar>` — Sofascore-style horizontal split bar with winner-highlighted score chip + dual-tone fill
- `<ScoreBox>` — per-period table (Q1-Q4 / Sets / Innings) for left rail

### Basketball Statistics tab
- New `BasketballStatsView` parses `Made/Att` strings from API-Sports basketball stats blocks (Free Throws, 2-pointers, 3-pointers, Field Goals)
- 2-column grid: gauges on the left, comparison bars (Rebounds / Defensive / Offensive / Assists / Turnovers / Steals / Blocks / Fouls) on the right

### H2H tab redesign
- "Last N meetings" header + per-row W/L pill (lime W when target team won, rose L otherwise)

### Test Results (iteration 15)
- Screenshot-verified: Mets de Guaynabo 101 - 104 Criollos with per-quarter box (29/26 · 20/20 · 24/29 · 28/29), Q1-Q4 left rail, odds card, Follow-match right rail, tab switching between Box Score / Statistics / H2H

## Iteration 14 — Cricket innings + tennis sets wired to real APIs (2026-05-29)

### Cricket ingestion fully wired
- `sync_statpal_cricket()` completely rewritten to traverse the proper StatPal shape: `{scores.category[].match}`. Previously was looking at the wrong keys and just stuffing raw_data with no normalization.
- New `_parse_cricket_score()` parses StatPal score strings: `'490/8d'` → `(490, 8, declared)`, `'(fo) 179 & 232'` → sums to `(411, last_wkts, declared)`.
- New `_normalize_cricket_innings()` extracts per-innings shape:
  - `innings_no`, `team_name`, `runs`, `wickets`, `overs`
  - `top_batters[]` — sorted by runs, includes `{name, runs, balls, fours, sixes, not_out}`
  - `top_bowlers[]` — sorted by wickets, includes `{name, overs, runs, wickets, maidens}`
- Each tournament becomes its own league (e.g. "New Zealand tour of Ireland - Test", "ICC Men's T20 World Cup Sub Regional Africa Qualifier"), not a single catch-all "International Cricket" row.

### Tennis sets (already wired in iteration 12 — verified)
- `sets[]` correctly populated with `home_score/away_score/home_tiebreak/away_tiebreak` per set (e.g. A. Davidovich Fokina vs T. A. Tirante 4-set match with tb 4-7)
- `Sets.jsx` already renders tiebreak superscripts

### Innings.jsx UI upgrade
- Green result banner at top (`"New Zealand won by an innings and 79 runs"`)
- Venue + match-format header (TEST / T20 / ODI / etc.)
- Top batters: runs(balls) + `4×N · 6×M` boundary markers + `*` not-out marker
- Top bowlers section with `W/R (overs, maidens)` format

### Results: 49 cricket matches ingested with full innings data
Sample: New Zealand 490 vs Ireland 411 (Test, Stormont) renders 3 innings cards with TA Blundell's 186(292) ton, R Ravindra 121(194), and AR McBrine 73(105) for Ireland.

### Test Results (iteration 14)
- Backend: **11/11 pytest pass** (`/app/backend/tests/test_iteration14.py`)
- Frontend: cricket match detail screenshot verified · No retest needed

## Iteration 13 — Sport-aware Match Detail + Legacy duplicate cleanup (2026-05-29)

### Sport-aware Match Detail page
- `MatchDetail.jsx` now reads `m.sport_slug` and resolves to a per-sport tab map (`SPORT_TABS`):
  - **football / rugby** → Events · Stats · Lineups · H2H
  - **basketball / NBA / american-football / baseball / hockey** → Box Score · Team Stats · H2H
  - **tennis / volleyball / table-tennis / badminton** → Sets · Stats · H2H
  - **cricket** → Innings · H2H
  - **mma** → Fight Stats · H2H
- 3 new tab renderers shipped:
  - `BoxScore.jsx` — per-period scoreline + per-team player stats table (Min/Pts/Reb/Ast/Stl/Blk/FG/3P) for hoops/NFL/baseball/hockey
  - `Sets.jsx` — set-by-set table with tiebreak superscript for tennis/volley
  - `Innings.jsx` — per-innings runs/wickets/overs + top batters for cricket
- Loading state continues to use `<AnimatedBrand>` (no regression)

### Legacy duplicate cleanup endpoints
- New `routes/admin_cleanup.py` (admin-only, mounted at `/api/admin/cleanup/*`)
- `POST /duplicate-matches?sport_slug=…&dry_run=…&window_hours=…`
  - Walks every match in sport_slug, clusters by token-overlap within ±window, keeps highest provider rank (Sportmonks=100 > Manual=80 > API-Sports=50 > StatPal=30), deletes losers when `dry_run=false`
  - Live result on football: **291 duplicates removed from 3,116 matches**
- `POST /duplicate-leagues?dry_run=…`
  - Groups leagues by normalised (name, country, sport_slug), keeps highest provider rank, reassigns losing leagues' `match.league_id` to the winner
  - Live result: **79 leagues merged across 65 clusters** (220 → 158 leagues)

### Admin UI
- Dashboard tab now has a **DB Cleanup card** with one-click buttons per sport + Merge Leagues

### Test Results (iteration 13)
- Backend: **15/15 pytest pass** (`/app/backend/tests/test_iteration13.py`)
- Frontend: 3 sport tab variants verified end-to-end (football/tennis/basketball) · No retest needed

## Iteration 12 — Brand kit, animated loader, top-league ranking, smarter dedup (2026-05-29)

### Brand kit (user-supplied artwork)
- `cp-mark.png` (triangle), `cp-wordmark.png`, `cp-logo.png` saved to `/app/frontend/public/`
- `Brand.jsx` rewritten: `<Brand>` (mark + CLOUDYPITCH wordmark), `<Brand variant="mark"/>`, `<Brand variant="text"/>`
- Triangle PNG has black background → uses `mix-blend-mode: screen` to drop the black on any surface
- Favicon + apple-touch-icon point to `/cp-mark.png`

### Animated brand loader
- New `<AnimatedBrand size label/>` component: rotating triangle (cp-spin 2.4s) + pulsing radial glow (cp-pulse-scale 1.8s) + opacity pulse on the mark itself + lime drop-shadow
- Replaces "Loading match…" text on `MatchDetail.jsx`

### Top-league ranking (Sofascore-style)
- `league_tier_score(name, country)` is now **country-aware**: 'Premier League' from England → 100, from Bhutan → 30. Same gating for La Liga/Serie A/Bundesliga/Ligue 1.
- Variants inherit tier: 'Ligue 1 Play-offs' (France) → 100; 'France: Ligue 1 - Relegation - Play Offs' → 100
- UEFA / FIFA / Copa America always → 100 regardless of country
- `COUNTRY_PRIORITY` updated: continental tournaments (World=1, Europe=2, International=3) sit **above** all domestic — so UEFA Champions League outranks Premier League in the dashboard sort
- Match-list sort key changed from `(country_priority, -tier)` → `(-tier, country_priority)` so all tier=100 leagues sit at the very top
- Rescored all 776 league rows in DB on hot-deploy

### Smarter cross-provider dedup
- `_team_tokens()` drops common stopwords (FC, AC, Real, Olympique, Athletic, City, United, etc.) → returns set of 4+ char meaningful tokens
- `_cross_provider_dedup()` checks if ANY token overlap between home/away teams of a candidate match (handles home/away swap too)
- Result: 'Paris Saint-Germain' from Sportmonks now correctly matches 'PSG Paris' from API-Sports

### Test Results (iteration 12)
- Backend: **25/25 pytest assertions pass** · Frontend: visual verified via screenshot · No retest needed

## Iteration 11 — Card consumption + per-player targeting + usage history (2026-05-29)

### Card lifecycle is now strictly enforced
- **One use per card per game** — `POST /api/wc/games/{id}/enter` rejects duplicate `user_card_id` in `cards_used[]`
- **Cards consume on submit** — for each NEW card added in the entry, `user_cards.uses_remaining` decrements -1, `total_uses` increments +1, and a `card_uses` audit row is inserted (one per card per game per user)
- **Refund on remove** — if user updates entry to remove a card while game is still `upcoming`/`open`, the use is refunded: `uses_remaining +1`, `total_uses -1`, `card_uses` row deleted
- **Idempotent resubmits** — recomputes `to_consume = new - prev` and `to_refund = prev - new`, so saving the same entry twice does NOT double-charge

### Per-player targeting
- Each `cards_used` item MUST set `target_player_id` → backend returns 400 otherwise
- Target MUST be one of the 11 picked players → backend returns 400 otherwise
- Frontend GameEntryView auto-opens a player-target picker when a card is toggled on; same player can't be boosted by two cards in one entry

### New "My Usage" tab on /cards
- 3-tab page: **Catalog** · **My Cards** (owned cards + uses_remaining) · **My Usage** (history)
- `GET /api/cards/me/history` returns the last 100 `card_uses` joined with `legend_cards`, `wc_games`, and `players` (target)
- Sign-in gate on owned/history tabs

### Test Results (iteration 11)
- Backend: **7/7 pass** · Frontend integration: **PASS** · No retest needed

## Iteration 10 — Real WC2026 Schedule from Sportmonks + Card Per-Game Uniqueness (2026-05-29)

### Bug fix: WC schedule was pulling ALL historical seasons
- `sync_sportmonks_league_schedule(league_id)` was using `fixtureLeagues:{id}` filter which returned every season ever played in that league (league 732 yields 2006/2010/2014/2018/2022 + 2026). DB was filled with 125 historical fixtures and 134 wc_games dated 2006-2022.
- Fix: First resolve `currentseason.id` via `fetch_league_detail(league_id)` (returns 26618 for WC2026), then call NEW adapter `fetch_fixtures_by_season(26618)` using `/seasons/{id}?include=fixtures.*` which returns exactly the 104 WC2026 fixtures. All matches stamped with `sportmonks_season_id=26618`, `competition_id=wc-2026`, `is_world_cup=true`.
- Result: WC Hub Schedule tab now shows the REAL opener (Mexico vs South Africa · 2026-06-11 19:00 · Estadio Banorte), Brazil vs Morocco, USA vs Paraguay, Canada vs Bosnia, Germany — flags, venues, kickoff all correct.

### Card uniqueness per game entry
- `POST /api/wc/games/{id}/enter` — added duplicate-card-id detection: if `cards_used[]` contains the same `user_card_id` more than once, returns `400 "Each card can only be used once per game"`. Enforces the requirement that each card has one use per game.

### Round-game generator coverage upgraded 3→8 stages
- `generate_wc_games()` previously only created round games for `group_md1/2/3`. Now anchors all 8 stages chronologically from the sorted fixture list: group_md1 → match[0], md2 → match[24], md3 → match[48], r32 → match[72], r16 → match[88], qf → match[96], sf → match[100], finals → match[102]. Card limits: 5/5/6/6/7/8/9/10 as specified.

### Group games — dynamic clustering
- Group resolver was matching the (stale) seed `wc2026_groups.teams[]` against db.teams by name. Since the real FIFA draw shifts, the seed-based matcher returned 0 hits in many cases. Fix: derive groups DYNAMICALLY by pairing consecutive MD1 fixtures (each group plays 2 matches on MD1) and clustering the 4 teams. Falls back to seeded groups if dynamic clustering fails.

### Admin Generate-Tick button enhanced
- `/api/admin/wc/refresh-bracket` now runs the full pipeline: Sportmonks pull → generator → state tick. Returns `{ingested, created, transitions}`.

### Results: 104 Match games + 12 Group MD1 + 3 Group MD2/3 + 8 Round games = **130/148 wc_games created** automatically. MD2/3 group games fill in as sportmonks provides resolved participants for those days.

### Test Results (iteration 10)
- Backend: **7/7 pass** · Frontend: **6/6 pass** · No retest needed

## Iteration 9 — User-Driven Restructure (2026-05-29)

User feedback batch — all resolved:

### Bug fixes
- **Fantasy player list showed only DEF** — `/fantasy/players?limit=300` was sorted by `position` ascending so all 300 returned slots filled with the 417 DEF rows. Fix: sort by `name` and bump default to 2000. All 4 positions now return (146 GK / 417 DEF / 384 MID / 347 FWD).
- **WC Hub Schedule tab leaked past WC matches** — `/api/worldcup` used `league_name regex "World Cup"` which caught 2006/2010/2014/2018/2022 fixtures. Fix: `_wc2026_filter()` constrains to `scheduled_at` in `2026-06-01..2026-07-31` AND `is_world_cup OR sportmonks_league_id=732 OR competition_id=wc-2026`. Empty state copy updated.

### New — Past Tournaments tab on WC Hub
- `/app/backend/wc_legends.py` — 9 hand-curated tournaments (1958-2022) with 21 legendary highlights
- `/api/worldcup/past` cross-references each highlight to `legend_cards` via 3-tier regex (full / last word / first word) — 14/21 highlights deep-link to live cards
- New `PastTournamentsView` component renders tournament hero (champion/Golden Ball/Golden Boot) + highlight rows with Legend Card price chips that link to `/cards`. This is the new **marketing surface for the 100-card catalog** — "every card earned its place at a World Cup"

### Unified Fantasy hub (merge `/wc/games` into `/fantasy`)
- `Fantasy.jsx` is now a 3-tab hub: **My Squad** · **WC Games (148)** · **Leaderboard**
- WC Games rendered via reusable `<WcGamesPanel/>` exported from `WcGames.jsx`
- `/wc/games` route now `<Navigate to="/fantasy" replace/>`
- Non-auth users see a clean sign-in gate (`fantasy-signin-gate` testid)

### Header cleanup
- Desktop top nav: **WC 2026 · Predictions · Leaderboards** only (was 6 links). Sports row unchanged.
- Fantasy + Legend Cards moved to top of signed-in user dropdown (mobile drawer parity)

### Sign-in gating
- `/wallet` now shows a clean gate ("Sign in to access your wallet") when not authed; no half-loaded panels

### Test Results (iteration 9)
- Backend: **9/9 pass** · Frontend: **9/9 pass** · No retest needed

## Iteration 8 — WC Fantasy Game Structure (148 games) + Auth-extras UI + Premium Tabs + Admin (2026-05-29)

### NEW — WC2026 Fantasy Game System (148 games)
Three game types now live, end-to-end:
  - **Match Game** (104 total): pick 11 from both teams, 2 cards default
  - **Group Game** (36 total = 12 groups × 3 matchdays): pick 11 from 4 teams, 4 cards
  - **Round Game** (8 total): pick 11 from all teams alive, 5→10 cards by stage, 1.0×→4.0× multiplier

**Collections added:**
- `wc_game_config` — 12 default rows (seeded idempotently in `seed_data.py`). Admin-editable card limits + multipliers + opens_hours_before.
- `wc_games` — auto-generated per match/group/round with status machine (`upcoming → open → closed → settling → settled`).
- `wc_game_entries` — user picks (11 players + captain/vice + cards_used).

**Cron added (in `ingestion.py`):**
- `wc_games_generator_loop` — daily generator (runs once at boot, then every 24h)
- `wc_games_state_loop` — 5-minute state-machine tick

**Routes (`/app/backend/routes/wc_games.py`):**
- USER: `GET /api/wc/games/today | upcoming | {id} | {id}/leaderboard`, `POST /api/wc/games/{id}/enter`, `GET /api/wc/user/entries | wc/groups | wc/leaderboard/overall`
- ADMIN: `GET/PATCH /api/admin/wc/config`, `POST /api/admin/wc/config/reset`, `GET/PATCH /api/admin/wc/games/{id}`, `PATCH /api/admin/wc/groups/{letter}`, `POST /api/admin/wc/refresh-bracket`

**Frontend:**
- New `/wc/games` page (`WcGames.jsx`) with Open Now / Upcoming tabs, GameCard, GameEntryView modal with position-grouped 11-pick interface + card multi-select up to stage cap
- Header nav + mobile drawer link "WC Games"
- Admin POOLS tab: inline pool editor (title, USD cents, payout structure JSON, start/end ISO) hooked to `PATCH /api/prize-pools/{id}`; one-click "Settle"
- Admin WCCONFIG tab: 12-row table inline editor for card_limit_current / points_multiplier / opens_hours_before / is_active + "Reset to Defaults" button
- Admin WCGAMES tab: filterable game list (type/status) with status-override dropdown + "Generate / Tick" button

### Email verification + password reset + KYC UI
- New pages: `/forgot-password`, `/reset-password?token=…`, `/verify-email?token=…`
- "Forgot password?" link added to SignIn
- New `KycModal` component on Wallet page collecting legal name, DOB, bank name, account, optional BVN — submits to `/api/auth-extras/kyc/submit`
- `RewardedVideoButton` wired in Wallet (card_uses reward) + Predictions sidebar (prediction_points reward)

### Premium-only side leaderboard + early predictions window
- `/predictions` sidebar now has 3 tabs: Global / Weekly / **Premium** (premium-only — uses existing `scope=premium` backend filter)
- Premium subscribers already get 14-day prediction horizon vs. 7-day for free users (existing backend)

### Test Results (iteration 8)
- Backend: **28/28 pass** (testing_agent_v3_fork iteration 8)
- Frontend: All pages render correctly, no critical bugs, no retest needed
- WC fixture ingestion for league 732 confirmed via `sync_sportmonks_league_schedule(732)` — 125 historical WC matches ingested + 134 wc_games rows auto-generated

## Iteration 7 — WC-Only, Referrals, USD Pricing, Pool Funding, Admin Pool Editing (2026-05-29)

### Scope changes
- **Predictions & Fantasy** are now strictly **FIFA WC 2026 only**: `_wc_match_filter` clause on `/predictions/upcoming`, 403 on POST to any non-WC match, `is_world_cup` flag set during Sportmonks ingestion for league_id 732
- **Removed** "Built in Lagos" branding from footer — now reads "© 2026 Cloudy Pitch · Global Football, Predictions & Fantasy"

### Currency switch — NGN → USD
- All card prices in USD cents: GOAT $2 (200), Elite $1 (100), Star $0.50 (50), recharge $0.20 (20)
- Premium subscription $2.00/mo (was ₦2,000)
- Wallet, Prize Pool, Right Rail, Legend Cards, Premium, Predictions all display `$X.XX` with thousands separator
- Backend `legend_cards.price_usd_cents` field added on every seed run (idempotent upsert)

### Referral System
- New `/api/referrals/me`, `/api/referrals/leaderboard`, `/api/referrals/validate/{code}` routes
- 8-char Crockford Base32 codes auto-generated on first `/me` call (no 0/O/I/L confusion)
- Signup form accepts `referral_code` field + supports `?ref=CODE` query param + live debounced validation
- Frontend `/referrals` page with hero, code+share+copy, 4 stat cards (Invited/Active/Spend/Credit), Top Referrers leaderboard, $5,000 prize pool
- Referrers earn 10% credit (USD cents) of every dollar their referrees spend on Legend Cards — for leaderboard ranking
- New `/referrals` route + Header dropdown + drawer "Invite & Earn" links
- New `pool-referrals` prize pool ($5,000 seed, separate from main WC pool)

### Prize-Pool Auto-Funding (50%)
- Every `/api/cards/purchase` and `/api/cards/recharge` writes a `prize_pool_contributions` audit row + bumps `pool-wc2026-fantasy.amount_usd_cents` by exactly 50% of the price
- New admin endpoint `GET /api/prize-pools/{id}/contributions` returns audit log + total
- WC pool now displays its USD value live (grows as cards are bought)

### Admin Pool Editing
- New `PATCH /api/prize-pools/{id}` (admin) — edit `title`, `amount_usd_cents`, `amount_total_ngn`, `payout_structure`, `starts_at`, `ends_at`, `is_active`
- `payout_structure` supports both list-of-dicts and legacy dict formats in settlement

### Frontend UX fixes (post-test)
- USD formatting with thousands separator (`$5,000.00` not `$5000.00`)
- InterstitialAd now has 90-second session grace (no interstitial in first 90s) + sessionStorage tracking → no longer blocks `/signin` form submission

### Test Results
- **Backend: 15/15 pytest pass (100%)**
- Frontend: 95% — fixed all 3 LOW/MEDIUM observations post-test (USD thousands separator, interstitial grace period; the /legend-cards observation was a non-issue — route is /cards)

## Iteration 6 — Card Picker + Premium + Wider Ad Wiring (2026-05-28)

### Card Application UI
- `CardPickerModal` component: multi-select up to 2 owned cards for a single prediction
- Live boost preview (Base × Stage / Card Boost % / If exact = final pts)
- Per-card match indicator ("no match for this game" if card's country doesn't apply)
- Empty state with CTA to browse Legend Cards
- "Apply boost" pill on every unlocked prediction row (data-testid `pred-boost-{id}`)
- Predictions submit now passes `card_ids[]` to backend (capped at 2)
- Auth starter-pack also writes `uses_left` alongside `uses_remaining` for downstream compat (admin backfilled with 5 Star cards)

### Premium Subscription (₦2K/mo)
- New `/premium` page with hero, ₦2,000/mo price, Subscribe button → Paystack initialize (`purpose='premium_sub'`)
- Compliance pre-flight check (18+ + spending caps) before initialising
- Compare Plans table — 8 rows showing Free vs Premium feature parity
- Active state when `is_premium=true` with `premium_until` date
- `public_user()` now exposes `is_premium` + `premium_until` to frontend
- Disabled state when Paystack keys not configured (graceful)
- Header dropdown + drawer now has `Go Premium` link (becomes `Premium ✓` once active)

### AdSlot Wiring
- WC Hub Groups tab — `wc_hub_sponsor` ad rendered between groups 6 and 7
- Dashboard — `match_list_inline` ad after every 3rd LeagueGroup
- New `InterstitialAd` component mounted on App root — triggers on route changes, rate-limited (1 per 3min via localStorage `cp_interstitial_last_shown`), dismissable, skips after 3 dismisses, blocked on `/payment`, `/signin`, `/signup`, `/premium`
- Seeded 4 sample direct sponsors: MTN (home_bottom_banner), Bet9ja (interstitial_nav), OPay (wc_hub_sponsor), Flutterwave (match_list_inline)

### Test Results
- Backend: **16/16** pytest pass (100%)
- Frontend: 95% — only minor observation about interstitial overlay intercepting clicks during automated nav tests (by design)
- No production bugs

## Iteration 5 — Full 7-Phase Spec Implementation (2026-05-28) — "do all"

User dumped the complete product playbook (ad revenue, prediction scoring, legend card mechanic, fantasy points, prize-pool distribution, wallet, compliance). All 7 phases shipped in one batch.

### Phase A — Prediction Scoring v2
- `/app/backend/scoring.py`: base 30/15/10 + stage multipliers (Group 1.0× → Final 4.0×) + streak bonuses (3/+10, 5/+25, 10/+100) + card boost (sum of matching cards' multiplier-1.0, capped +1.0)
- `compute_stage()` auto-detects WC stage from match.round.name / match.stage.name
- `card_matches()` supports both new spec (`country_boost/continent_boost/position_boost/role_boost/flat_boost`) AND legacy seeded vocabulary (`score_boost/outcome_boost/captain_boost/defense_boost`) using `card.country_code`
- `POST /api/predictions` accepts optional `card_ids[]` (capped at 2 per match)
- `POST /api/predictions/settle` (admin) rescores all finished matches with new engine, consumes 1 use per applied card
- `GET /api/predictions/leaderboard?scope=global|weekly|country|competition` with optional `country=NG` or `competition_id=`

### Phase B — Legend Card mechanic complete
- `POST /api/cards/purchase` creates user_card with 5 uses + writes card_transactions row
- `POST /api/cards/recharge` adds +5 uses for ₦200

### Phase C — Fantasy Scoring Engine
- `/app/backend/fantasy_scoring.py`: per-position points (GK/DEF goals×6, MID×5, FWD×4, assists×3, clean sheets, GK saves /3, MOTM +3, yellow -1, red -3, own goal -2, missed pen -2, minutes 1/2)
- `POST /api/fantasy/settle/gameweek` walks each squad's starting XI, finds matching `match_events`, aggregates stats, applies captain ×2 / vice ×2 fallback, writes `fantasy_gameweek_points` snapshot, updates squad `total_points`
- `GET /api/fantasy/squad/me/breakdown` returns latest snapshot

### Phase D — Wallet + Prize Pool Settlement
- New `user_wallets` + `wallet_transactions` collections
- `GET /api/wallet/me`, `POST /api/wallet/deposit`, `POST /api/wallet/spend`, `GET /api/wallet/transactions`, `POST /api/wallet/credit-winnings` (admin)
- `POST /api/prize-pools/{id}/settle` parses payout_structure in BOTH dict and list-of-dicts formats (post-test fix), reads final leaderboard, computes per-rank payouts, writes `prize_pool_winners` with `payout_status='pending'`

### Phase E — Paystack Integration (keys deferred)
- `/app/backend/routes/payments.py` with `/config`, `/initialize`, `/verify/{ref}`, `/webhook` (HMAC SHA-512 sig verification), `/transfer` (admin payout to user bank)
- Spending-cap pre-flight on `initialize`
- `_fulfill()` handles wallet_deposit / card_purchase / card_recharge / premium_sub purposes idempotently
- Frontend `/payment/callback` page verifies reference on redirect
- **INTEGRATION PENDING**: needs `PAYSTACK_SECRET_KEY` + `PAYSTACK_PUBLIC_KEY` in `/app/backend/.env`. Endpoints return 503 gracefully without keys.

### Phase F — Compliance Gate
- `compliance_profiles` collection auto-created on first access
- `GET /api/compliance/me`, `POST /api/compliance/age-gate` (DOB verified, must be ≥18), `POST /api/compliance/caps` (lowering immediate, raising delayed 24h), `POST /api/compliance/self-exclude`, `GET /api/compliance/can-spend?amount_ngn=…`
- Defaults: ₦5K/day, ₦20K/month
- `AgeGateModal` component blocks `/wallet` until verified

### Phase G — Ad System
- `ad_placements` collection with placement_key + network (admob/adsense/meta/direct) + sponsor fields + date window + weight
- `GET /api/ads/placements` filters by placement_key + premium subscribers
- Admin CRUD `POST/PATCH/DELETE /api/ads/placements`
- Impression + click tracking endpoints
- `POST /api/ads/reward/claim` for opt-in rewarded video: `card_uses` adds +5 uses to user's most-used card, `prediction_points` adds +50 via synthetic settled row (rate-limited 1/60s)
- `AdSlot` React component handles direct (image banner) + network (placeholder for AdMob SDK script tag); dismissible; impression+click tracking
- Seeded sample direct sponsor (MTN Nigeria) for `home_bottom_banner`

### Frontend
- New pages: `/wallet`, `/payment/callback`
- New components: `AgeGateModal`, `AdSlot`
- Predictions header updated to advertise 30/15/10 + stage multipliers + streak bonuses
- Header dropdown + drawer have Wallet link with Coins icon
- AdSlot embedded at bottom of Dashboard match list

### Test Results (iteration 5)
- Backend: **17/18** pytest pass (94%) → after fix, expected 18/18
- Frontend: routes load, AdSlot renders MTN sponsor, AgeGateModal blocks `/wallet`, regressions clean
- 1 critical bug found & fixed: prize-pool settle schema mismatch (dict vs list payout_structure) → now handles both
- Test file: `/app/backend/tests/test_iteration5.py`

## Iteration 4 — Sofascore MatchRow, Standings, Top Scorers, Cards-per-Game Caps (2026-05-28)
- ✅ **MatchRow visual rewrite** to mirror Sofascore screenshots: time + status stacked on left (kickoff HH:MM top, FT/HT/minute' below with red color for live), team logos + names stacked vertically (home top / away bottom), scores stacked on right (red for live), thin vertical dividers between cells, **favorite star** at far right with optimistic POST/DELETE to `/api/users/me/favorites/match/{id}`
- ✅ **Standings endpoint** `GET /api/leagues/{league_id}/standings?refresh=1`: fixed Sportmonks v3 type_id mapping (187=points, 179=goal_diff, 129/130/131/132/133/134) and added `details.type;form;rule` to fetch include — returns position, played, won, drawn, lost, goals_for, goals_against, goal_diff, points, form, team_logo
- ✅ **Top scorers endpoint** `GET /api/leagues/{league_id}/topscorers?refresh=1`: returns rank, player_name, team_name, team_logo, goals
- ✅ **Card usage enforcement** (`/app/backend/routes/card_usage.py`):
  - `POST /api/cards/use` with `{card_id, scope, scope_id}` — enforces cap (match: 2, group: 4, round: 5; SPECIAL_CAPS round:final = 10), idempotent (same card+scope+scope_id ignored), decrements `uses_left` on user_card
  - `GET /api/cards/usage?scope&scope_id` — returns `{count, cap, remaining, used}`
  - `GET /api/cards/usage/me` — grouped per-scope usage map
- ✅ **League doc enriched** with `current_season_id` + `sportmonks_league_id` during fixture upsert
- ✅ Verified by testing agent (iteration 4): backend 12/12 pytest pass · frontend MatchRow layout + live indicator + regression passing · favorite-star URL bug found and fixed post-test (`/users/me/favorites/*` route prefix)
- 🧹 Test suite: `/app/backend/tests/test_iteration4.py`

## Iteration 3 — WC Hub, Predictions/Fantasy UX, Logo Enrichment (2026-05-28)
- ✅ **World Cup Hub UI** redesigned with 4 tabs (Groups · Knockout · Schedule · Prize Pool): hero banner with large live countdown, 12 group cards (A-L) showing country flags via flagcdn.com + 4 teams + standings table placeholders, full knockout bracket visualization (12 R32 + 8 R16 + QF/SF/Final cards)
- ✅ **Country flag lookup**: `/app/frontend/src/lib/flags.js` with 45 ISO-3166 alpha-2 codes for WC2026 nations
- ✅ **Predictions hub UX**: matches grouped by date headers ("Mon, Mar 15"), team logos beside names, score number inputs with kickoff-time pill, Lock icon for locked matches, "Predicted X-Y · Npts" status row, signed-in header shows total points / rank / picks count, leaderboard sidebar highlights current user
- ✅ **Fantasy hub UX**: live squad stats bar (squad N/15 · starters/11 · bank/spent + budget progress bar), position-colored player pills (GK gold, DEF lime, MID blue, FWD pink), search + position filter, **MiniPitch component** showing starting XI on green pitch with C/V badges, squad list grouped by position with captain star / vice button / remove X per player
- ✅ **StatPal logo enrichment** (`ingestion._enrich_statpal_logos`): token-set intersection fuzzy matching against existing teams collection — fills missing logos for ~57% of statpal football matches (72/127); auto-runs after each statpal poll. Includes prefix expansion (Atl→Atletico, Ind→Independiente, Dep→Deportivo) and unicode-accent stripping
- ✅ Verified by testing agent (iteration 3): 100% backend (5/5 pytest) + 100% frontend (all testids + flows)
- 🧹 Test file added: `/app/backend/tests/test_iteration3.py`
- ✅ Sportmonks event/stat type IDs mapped to human-readable names (Goal, Yellow Card, Substitution, Ball Possession %, Shots on Target, etc.) via nested `events.type` / `statistics.type` includes + `EVENT_TYPE_NAMES` & `STAT_TYPE_NAMES` fallback dicts in `adapters/sportmonks.py`
- ✅ `team_id` normalized to `sm-t-{id}` prefix across events/stats/lineups → enables correct home/away split on frontend
- ✅ Stale-data detection in `GET /api/matches/{id}` auto-refreshes legacy fixtures with numeric type IDs; also supports `?refresh=1` query param + UI refresh button
- ✅ New EventsList component (`/app/frontend/src/components/match/EventsList.jsx`): home-on-left / away-on-right layout, icons for Goal/Yellow Card/Red Card/Substitution/VAR, sub assist line, minute pill in center
- ✅ New StatsBars component (`/app/frontend/src/components/match/StatsBars.jsx`): Sofascore-style side-by-side mirrored bar charts, lime fill for winning side, % stats normalised, priority ordering (possession → shots → corners → fouls → cards)
- ✅ New LineupPitch component (`/app/frontend/src/components/match/LineupPitch.jsx`): green pitch with center circle/penalty boxes/goals, player number badges (lime home / white away), formation auto-derived from position_code row counts (4-3-3 / 4-5-1 etc.), full bench list below
- ✅ Verified by testing agent (iteration 2): 100% backend + frontend pass

## Test Credentials
See `/app/memory/test_credentials.md`. Admin: `admin@cloudypitch.com` / `CloudyAdmin2026!`

## Backlog (P0/P1/P2)
**P0 (next iteration):**
- Missing team logos for some API-Sports / StatPal matches (recurring — investigate ingestion logo URL handling + frontend MatchRow fallback)
- World Cup hub UI (groups, brackets, countdown — data schema ready)
- Predictions hub UI polish (picks page + leaderboard)
- Fantasy squad builder UX pass
- Paystack/Flutterwave integration for Legend Card purchases (₦2000/₦1000/₦500 + ₦200 recharge per 5 uses)
- 18+ age gate on real-money flows
- Self-imposed spending caps UI (₦5K/day, ₦20K/month defaults)
- Cards-used-per-game enforcement (Match: 2, Group: 4, Round: 5-10)
- Standings + top scorers ingestion (Sportmonks endpoints available, table schema in place)
- WC2026 actual fixture ingestion (sportmonks league_id 732, season_id 26618)

**P1:**
- Per-sport score displays beyond tennis: NBA quarters grid, cricket overs format, MMA round timer, F1/golf leaderboards
- Knockout bracket UI (data structure ready)
- Push notifications (web + Flutter via FCM)
- Email verification + password reset flow
- Country sidebar real country names (require `include=country` in Sportmonks calls — done for leagues, pending for teams)
- Pin African leagues to top of sidebar based on user `country_code`

**P2:**
- Object storage for league/team logos beyond base64 (S3/MinIO on Contabo)
- Redis-backed cache (replace in-memory `cache.py`)
- WebSocket live push for match detail page
- Refactor `/app/backend/ingestion.py` (1272 lines) → split into per-adapter modules
- B2B sponsor placements (Bet9ja/MTN/OPay banners)
- Refer-a-friend program
- Daily/weekly free prediction streak rewards

## Flutter App Readiness
- All REST endpoints return clean JSON (no MongoDB ObjectIds, UUID strings only)
- Same cookie session token can be issued to Flutter via custom header on signin response if needed (currently HTTP-only cookie)
- For Flutter native, add `/api/auth/token` endpoint that returns raw session token; Flutter stores in secure storage and sends as `Authorization: Session <token>` header (will need minor `get_current_user` extension)

## Next Action Items
1. Wire Paystack test keys & implement card purchase flow
2. Build per-sport score-display variants
3. Ingest WC2026 official fixtures + actual squad rosters (Sportmonks teams/squads endpoint)
4. Add Flutter-friendly token header path to auth
