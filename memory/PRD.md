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

## Test Credentials
See `/app/memory/test_credentials.md`. Admin: `admin@cloudypitch.com` / `CloudyAdmin2026!`

## Backlog (P0/P1/P2)
**P0 (next iteration):**
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
- Email verification
- Password reset flow
- Country sidebar real country names (require `include=country` in Sportmonks calls)

**P2:**
- Object storage for league/team logos beyond base64 (S3/MinIO on Contabo)
- Redis-backed cache (replace in-memory `cache.py`)
- WebSocket live push for match detail page
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
