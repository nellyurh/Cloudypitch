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
