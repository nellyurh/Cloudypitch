# Cloudy Pitch — PRD

## Original Problem Statement
Global multi-sport livescore + predictions + fantasy platform launching for FIFA WC 2026. Sofascore-inspired dense UI. African football core audience, USD pricing with NGN supported. Live at https://cloudypitch.com.

## Tech Stack
- React 18 + Tailwind + Shadcn UI (frontend)
- FastAPI + Motor MongoDB (backend) on Caddy + Docker on Contabo VPS
- Opaque cookie auth
- Sportmonks (football), API-Sports (other sports), Trybit/CryptoCloud (crypto deposits), PocketFi (NGN), Google AdSense


### 2026-02-13 (Momentum tab + fantasy double-count fix + v2 backfill)
- **🆕 Attack Momentum tab** added to football match-details. New component uses **Recharts** stacked `BarChart` per minute — home pressure lime `#A3E635` (positive Y), away pressure slate `#94A3B8` (negative Y), HT reference line at 45'. Tooltip on hover shows `Minute X' · Home N% · Away N%`. The tab is **auto-hidden** when `/api/matches/{id}/momentum` returns an empty `momentum[]` array (so it never renders a dead empty tab).
- **🐛 Fantasy auto-settler was DOUBLE-COUNTING points** — `settle_gameweek` used `$inc total_points` which compounded on every 5-min loop iteration. Fixed by **summing every gameweek snapshot for the squad** and `$set`ing the canonical total. Settler is now safe to run indefinitely. Also disabled card-use consumption inside the auto-loop (would have triple-burned cards); cards still consume via the explicit admin endpoint.
- **🆕 `POST /api/fantasy/settle/rebuild`** (admin) — One-shot backfill that wipes every gameweek snapshot, resets every squad's `total_points` to 0, then re-runs the settler with scoring v2 (CBIT/CBIRT/goals-conceded/canonical goal values). Audit-logged. Verified on preview: 8 snapshots wiped, 6 squads reset, 8 re-settled, totals match per-gw snapshots exactly.
- **📐 Design blueprint generated** — `design_guidelines.json` covers the 8-component Sofascore-grade match-details redesign (header, tabs, events timeline, momentum, lineups pitch, stats scrolling, H2H, standings mini). Used as the reference for the AttackMomentum + LineupPitch overhaul; remaining components (timeline polish, stats progress bars, H2H card) on the roadmap.


### 2026-02-13 (Match details polish: empty tabs · mobile pitch · team-name aliases)
- **🚫 Empty tabs auto-hidden** in `MatchDetail.jsx`. `events`, `stats`, `commentary`, `lineups` tabs are filtered out before render if their backing arrays are empty. `H2H` / `Standings` / `Trends` stay visible (they self-render a friendly "no data yet" state). Solves the "Attack Momentum is empty" dead-clicks on the deployed site.
- **📱 LineupPitch responsive rewrite** — On mobile (<768px) the pitch now renders **vertically** (aspect 3/4, home top, away bottom) exactly like Sofascore. Bigger player chips (36→40 px on phones), name labels with wider truncation, vertical penalty/goal boxes. Desktop keeps the 16/10 landscape layout unchanged. New helper `computePositions()` returns `{depth, lane}` so the same logic drives both orientations.
- **🛡️ Team-name alias normalizer** — Provider variants (Côte d'Ivoire / Ivory Coast, South Korea / Korea Republic, USA / United States, UAE / United Arab Emirates, Czechia / Czech Republic, Türkiye / Turkey, Bosnia / Bosnia and Herzegovina, Cape Verde / Cape Verde Islands, North Korea / Korea DPR, Iran / IR Iran) all collapse to a single canonical key inside `_normalize_team()`, eliminating the "Ivory Coast vs Ivory Coast" twin-tab the user spotted.


### 2026-02-13 (Scoring v2 + unified WC league feed)
- **🆕 Fantasy scoring updated to the canonical spec**:
  - Goals: GK/DEF +6, MID +5, FWD +4 (unchanged)
  - **NEW** Defensive Contributions: DEF +2 per 10 CBIT (clearances + blocks + interceptions + tackles); MID/FWD +2 per 12 CBIRT (CBIT + recoveries).
  - **NEW** -1 per 2 goals conceded (GK/DEF only).
  - Minutes ≤60 → +1, ≥60 → +2 (unchanged). Clean sheets: GK/DEF +4, MID +1. Penalty save +5. Yellow -1, Red -3, Own goal -2, Pen miss -2.
  - `compute_player_points()` signature expanded with `goals_conceded`, `clearances`, `blocks`, `interceptions`, `tackles`, `recoveries`. `settle_gameweek` now pulls these from `match_lineups.stats` per provider, and tallies `goals_conceded` from each opponent score.
  - Unit-tested: DEF 90'+12 CBIT+CS = **8 pts**, MID 90'+24 CBIRT = **6 pts**, GK 90'+6 saves+1 pen save+4 GC = **7 pts**.
- **🛡️ Duplicate "World Cup" sidebar tabs collapsed** — Multiple providers (Sportmonks, api-sports, StatPal) each registered their own `league_id` for WC2026, producing 2-3 "World Cup" entries in the country sidebar with overlapping match lists. Fixed in `routes/matches.py:list_matches`: any league flagged `is_world_cup=true` OR whose name matches "World Cup / World Championship / FIFA WC" is merged into a single canonical `wc-2026-canonical` bucket titled **"FIFA World Cup 2026"**, pinned at the top of the dashboard. Inner-bucket dedupe by `(home, away, day)` prevents repeats. Verified: WC groups went from 3 → 1 with 5 deduped matches.


### 2026-02-13 (Budget bump · alert → toast · fantasy auto-credit · 30m lock fix)
- **20-man squad budget bumped €120M → €150M** for all mini-game types (`group`, `round`, `matchday`). Single-match games still cap at €100M / 15-man. Updated in `routes/fantasy.py` (`_pick_rules_for_game`, `create_or_update_squad`) AND `BuildTeam.jsx` (`SQUAD_PROFILES["20"].budget`). Verified via `/api/fantasy/game-rules/{id}` → `{total: 20, budget: 150}`.
- **🐛 30-minute team-lock false-positive** — A team whose group-stage match had already finished (FT) was being permanently locked from later round/matchday mini-games. Root cause: the lock query was `scheduled_at ≤ now+30m` with no upper bound on age and no status filter, so a finished match in the past matched forever. **Fix**: added `scheduled_at ≥ now-4h` floor + `status ∉ [FT, AET, PEN, AWARDED, CANC, POSTP, ABAN]`. Now a team is locked ONLY if it has a NON-finished match starting within 30 min or currently in-play.
- **🆕 Native browser `alert()` → custom toast (Sonner)** — All 13 `alert()` calls in `BuildTeam.jsx` + 2 in `MyTeams.jsx` migrated to `toast.error()` / `toast.success()`. The toast container was already mounted in `Layout.jsx`. No more "cloudypitch.com says…" OS popups breaking the immersive UI.
- **🆕 Main fantasy team auto-credit loop** — Squad `total_points` weren't growing because `settle_gameweek` was admin-only. Wired into the existing `wc_games_settler_loop` (every 5 min) so every FT match auto-credits all 15-man and 20-man squads. Verified via manual `POST /api/fantasy/settle/gameweek?gameweek=1` → `{settled: 8}` squads re-scored.


### 2026-02-13 (Recursive coin sweep + admin pricing in coins)
- **Wallet page** rewritten to lead with **Coin Balance** in 🪙 emoji + tabular nums. Legacy NGN/USD balances shown only as a small "Legacy balances (mini-games / withdrawals)" footnote so they don't dominate.
- **Admin → Card Prices tab** rewritten: bulk-price + per-card editor both in coins, with Legendary/Elite/Star tier labels. Backend `PATCH /api/admin/cards/{id}` + `POST /api/admin/cards/bulk-price` now accept `price_coins` (preferred). Legacy `price_usd_cents` still accepted for backwards compat.
- **Transfer cards** (5-pack for fantasy transfers) re-priced from $2 → 🪙 300 coins. Updated in `/api/fantasy/transfers` (`card_price_coins` field), `MyTeams.jsx`, and `BuildTeam.jsx` confirm modal.
- **WC duplicate cleanup**: ran `POST /api/admin/cleanup/wc-duplicates` on preview → deleted 3 stale non-Sportmonks WC matches. User must run the same on prod once after deploy.


### 2026-02-13 (Coin economy + free-drops off + QualifyProgress + ad/match fixes)
- **🪙 New coin economy** — Cards now priced in coins, not USD:
  - Legendary (tier 1) = 1,000 coins
  - Elite (tier 2) = 500 coins
  - Star (tier 3) = 200 coins
  - Recharge = 100 coins (+1 use)
  - Conversion: `1 NGN = 1 coin`, `1 USD = 1,370 coins` (+5% crypto bonus on Trybit), `1 coin = $0.00073`.
  - Existing wallet balances are FROZEN — only NEW top-ups credit coins. Old USD wallet remains for legacy mini-games.
  - 50% of every coin spend still flows to the prize pool (converted back to USD-cents at the same rate).
- **🚫 Free card drops disabled** — `/api/cards/check-drop` + `/api/cards/daily-drop` now return `{disabled: true}`. Action-logging stub kept for analytics + future re-enable.
- **🆕 Admin manual grants**:
  - `POST /api/admin/cards/grant` (user_id + card_id OR tier + quantity + note) → audit-logged.
  - `POST /api/admin/coins/grant` (user_id + coins delta + note) → audit-logged, can be negative for refunds.
  - `GET /api/admin/users/search?q=` → lightweight user search for the grant UI.
- **🆕 QualifyProgress component** — Gamified prize-pool progress bar on `/profile`. Shows `X/20 predictions · Y/50 mini-games · 50% to eligible`. New backend field `eligibility.progress_pct` on `/api/users/me/stats`.
- **🛡️ Ad viewport filter — STRICT** — Desktop requests now ONLY match zones explicitly tagged `target_viewport: "desktop"`. Mobile creative zones (e.g. XM Trading 300×600 portrait) no longer leak onto desktop pages. Mobile is more forgiving — allows `"mobile"` OR `"both"`.
- **🛡️ WC fixture duplicates killed** — StatPal football sync now refuses to insert/upsert any fixture whose home+away+date collides with an existing Sportmonks WC2026 match. Sportmonks is canonical for WC; StatPal/api-sports can only own non-WC fixtures.
- **🧹 New admin cleanup**: `POST /api/admin/cleanup/wc-duplicates` — deletes every non-Sportmonks WC duplicate already in the DB (one-shot).
- Verified end-to-end: card catalog returns `currency: COINS`, `tier 1 price 1000`, `tier 3 price 200`. `/wallet/me` returns `coins`. Free-drop endpoints return `{disabled: true}`. Admin coin grant credits successfully.


### 2026-02-13 (Count-based eligibility)
- Switched prize-pool eligibility from **points** to **counts**:
  - Must have made **≥ 20 predictions** (any predictions, settled or pending — settler lag never blocks)
  - Must have entered **≥ 50 WC mini-games**
- Env vars renamed: `PRIZE_POOL_MIN_PREDICTIONS=20` (was `MIN_PRED_POINTS=10`), `PRIZE_POOL_MIN_WC_GAMES=50` (was `MIN_FANTASY_POINTS=10`).
- Response now includes `prediction_count` / `wc_game_count` per row + `min_predictions` / `min_wc_games`. Frontend NOT YET tooltip + modal warning show current counts vs targets.


### 2026-02-12 (Unified leaderboard + eligibility + 24h sessions + public profile)
- **🛡️ 24-hour session expiry** — `SESSION_TTL_DAYS=30` → `SESSION_TTL_HOURS=24`. Both the cookie max-age AND the DB-side `expires_at` are now checked on every request (previously only the browser cookie was checked, so a leaked raw cookie could be replayed indefinitely against the API). Expired session rows are deleted on first 401.
- **🏆 Prize-pool eligibility gate** — Users must have `prediction_points ≥ 10` AND `(fantasy_points + wc_fantasy_points) ≥ 10` to receive a prize-pool payout. Configurable via `PRIZE_POOL_MIN_PRED_POINTS` / `PRIZE_POOL_MIN_FANTASY_POINTS` env vars. Ineligible users keep their rank on the leaderboard but `potential_prize_usd_cents = 0`. Slot does NOT roll over to next eligible user (no whiplash mid-tournament).
- **🆕 `GET /api/leaderboard/user/{user_id}`** — Public endpoint returning anyone's predictions (incl. matches with result), main squad summary, WC mini-game entries with points, and totals. No auth required. Sensitive fields (email, IP, IP-hash, sessions) NEVER included.
- **🆕 Clickable leaderboard rows on `/leaderboards`** — each row opens a `UserDetailModal` showing: totals breakdown (Total / Pred / Fantasy / WC Mini), eligibility status, main-squad stats, last 20 predictions (pick → actual → points), last 20 WC mini-game entries.
- **♻️ Replaced separate prediction & fantasy boards with the unified leaderboard everywhere** — `RightRail.jsx` previously showed two side-by-side widgets ("World Cup Points" + "Predictions Top 5"); now a single "Prize-Pool Leaderboard" widget with a green dot next to eligible users. `Predictions.jsx` switched from `/predictions/leaderboard` to `/leaderboard`. Old endpoints kept alive (used by tests).
- **🆕 ELIGIBLE / NOT YET pills** on every unified-board row + a top-of-page rule banner explaining the threshold.
- Verified via Playwright: row click → modal renders with totals/squad/predictions correctly; backend curl confirmed `Session TTL: 24.0 hours`.


### 2026-02-12 (Samsung S22 blank/scanline fix + prediction settler unblock)
- **🐛 Samsung S22 was rendering blank `/build-team` + scanline corruption on `/profile`.** Root cause: our previous "Samsung hardening" CSS promoted **every** `.cp-surface` / `.sticky` element to its own GPU compositor layer via `transform: translateZ(0)`. Samsung S22 has a smaller texture-cache than Chrome's reference Pixel — 50+ promoted layers per page overflows it, and the GPU either renders a black/white blank or partial textures (scanlines). Removed the global GPU-promotion rule; only safe viewport/overflow rules remain.
- **🐛 Prediction auto-settler was permanently dead.** Two compounding bugs:
  1. `ingestion.py:wc_games_settler_loop` imported `from prediction_scoring import score_prediction`, but the module is `scoring`. The `ImportError` was swallowed by the surrounding try/except every 5 min — logs showed `predictions settler: No module named 'prediction_scoring'` every cycle.
  2. Even after fixing the import, both the loop AND `POST /api/predictions/settle` started from `db.matches.find({status: FT/AET/PEN}).to_list(length=5000)`. The DB has 5000+ FT matches across all sports, so WC matches fell outside the page and never got scored. Inverted: query starts from unsettled predictions, looks up only their matches in bulk.
- Verified: manually inserted exact 2-0 predictions on Mexico vs South Africa, hit `/api/predictions/settle` → returned `{"settled": 3}`, points = 30 each with `exact_score_hit: true`. Background loop now runs the same code path every 5 min.


### 2026-02-12 (Service-worker hijack killed — root cause)
- **🚫 Real culprit was the Monetag service worker** at `/sw.js` (domain `3nbf4.com`, zoneId `11139111`). It was auto-registered for every non-premium visitor via `registerAdSw.js` and hooked into navigation/notification events to hijack the first tap. Banner ads were never the issue.
- **`/app/frontend/public/sw.js`** rewritten to a no-op worker that self-unregisters on `activate` and clears all caches. Browsers that previously installed the Monetag worker will be cleaned up automatically on next visit.
- **`/app/frontend/src/lib/registerAdSw.js`** rewritten: no longer registers any ad worker; instead it iterates `navigator.serviceWorker.getRegistrations()` and unregisters anything pointing at `/sw.js` / 3nbf4.com / propellerads / monetag domains. Also purges related caches.
- Verified via Playwright on preview: **0 popups, 0 active SW registrations** after page load.
- Banners (Adsterra/AdSense/direct sponsors) and the previously-killed popunder filter remain — only this third hijack vector is now also closed.


### 2026-02-12 (Click-hijack KILL switch)
- **🚫 Click-hijacking permanently disabled** across the entire site. Three layers:
  1. `/api/ads/config` no longer returns `propellerads_serving_head` (OnClick/Vignette) or `propellerads_popunder_snippet`.
  2. `/api/ads/serve/{placement}` skips zones with `format ∈ {popunder, onclick, vignette, interstitial}` for BOTH PropellerAds and Adsterra.
  3. `AdHeadInjector.jsx` rewritten to inject ONLY verifier-required meta/link tags; refuses `<script>` nodes entirely. `AdSlot.jsx` also blocks hijack-format snippets as defense-in-depth.
- **🆕 `POST /api/ads/wipe-popunders`** (admin) — one-shot cleanup that deletes every popunder/onclick/vignette/interstitial zone from both networks + blanks the legacy `serving_head` field. Audited.
- Removed the popunder seed entry from `POST /api/ads/seed-defaults` so re-seeding can't re-introduce it.
- Inline banner ads (header, sidebar, match-list, mobile bottom, etc.) continue to render normally via `<AdSlot>`. Only the tap-stealing formats are killed.


### 2026-02-12 (My Picks visibility + Past mini-games tab)
- **🆕 Predictions "My Picks" tab** — Users can now see all their predictions (including settled ones with points) on `/predictions`. Previously only NS/TBD upcoming matches were shown so settled picks vanished. New `MyPredictionsList` component shows actual result vs user's pick, points earned, streak bonus, stage multiplier, and outcome badges (Exact/Outcome correct/Missed/Pending).
- **🆕 WC Mini-Games "Past" tab** — New backend endpoint `GET /api/wc/games/mine/past` returns the user's entries for `closed`/`settling`/`settled` games with attached `match_info`. Frontend `WcGamesPanel` now has an "Open / Upcoming / **Past**" tab. Each past card shows headline, match score, picks count, rank-in-game, and points scored. Tapping a settled card opens `/wc/games/:id/entries`.
- Notes: the prediction settler loop (`ingestion.py:wc_games_settler_loop` every 5 min) already credits the predictions leaderboard for FT matches via `settled_at`. UI gap was the only blocker.

## Implemented (rolling)
### 2026-02-11 (Player season points + PropellerAds + admin rename)
- **🆕 Player Season Points (admin pricing tool)** — New `GET /api/admin/players/season-points` aggregates every WC2026 player's total fantasy points across every settled match (uses the same scoring engine as `wc_settler`). Returns `season_points`, `matches_played`, `ppg`, and a `suggested_price`. New "Player Points" admin tab with sortable table (Total / Per-match / Suggested-current delta) and 1-click **Apply** to write the price via the existing `PATCH /api/admin/players/{id}/price` endpoint.
- **🆕 PropellerAds integration** — New network alongside AdSense:
  - `/app/frontend/public/sw.js` hosted at root for push verification (`zoneId: 11139111`).
  - Service worker auto-registers for non-premium users (`src/lib/registerAdSw.js`).
  - `db.propellerads_zones` keyed on `(placement_key, format)` — admin can paste the per-zone HTML snippet from the PropellerAds dashboard.
  - `/api/ads/serve/{placement}` prefers Propeller zones over AdSense fallback.
  - `AdSlot.jsx` re-executes the pasted `<script>` tags (innerHTML alone won't run scripts).
  - Seeded all 7 user zones (728×90 / 300×250 / 160×600 / 160×300 / 468×60 / 320×50 / popunder) mapped to 12 placements.
  - New "PropellerAds zones" panel inside Admin → Ads tab — paste-the-snippet form.

### 2026-02-11 (My Teams click → mini-game loads correctly)
- **🚨 My Teams mini-game card opened a blank page** — `/wc/games/:id` had no Route registered, so clicking a saved mini-game went nowhere. Fixed in `MyTeams.jsx`: settled games → `/wc/games/:id/entries`, otherwise → `/build-team?game_id=:id` (which already hydrates the saved squad).
- **🚨 Mini-game card showed "15/11" denominator** — Hardcoded to 11 regardless of game_type. Backend `/fantasy/my-teams` now returns `squad_size_required` (15 for match, 20 for group/round) and the UI uses that.
- **🚨 BuildTeam couldn't re-hydrate a saved mini-game entry** — Frontend reads `sq.players[]` with `is_captain`/`is_vice` flags, but the wc entry stored `player_picks[]` with captain IDs separately. Normalised `game.my_entry` in `/api/wc/games/:id` to expose `players[]` (with per-pick flags) + `applied_cards[]`. Existing squads now load correctly when re-opened.

### 2026-02-11 (Public mini-game entries + per-team points + admin rename)
- **🆕 Public mini-game entries page** — Route `/wc/games/:gameId/entries` (also reachable by clicking any settled game card). Shows ranked leaderboard of every entrant, expandable to reveal: (a) **points-by-team** chips for THAT round only (team_id → total points + player count), (b) position-grouped squad rows with per-player points, captain/vice badges, minutes, base points & multipliers, and (c) cards applied.
- **🚨 Single-match games now close 30 min BEFORE kickoff** (was: at KO). Generator + `enter_game` defense-in-depth + backfill endpoint all updated. Backfill ran live → 104 of 148 match games corrected, Mexico–S.Africa game is now closed as expected.
- **🚨 Settler scoping fix** — `_resolve_match_ids_for_game` no longer keys off `closes_at` ± window (which broke when we moved `closes_at` to LAST KO). Now uses the same matchday/stage slicing as the generator, so points are guaranteed to come ONLY from that round's matches.
- **🆕 Admin: edit user display name** — `PATCH /api/admin/users/{user_id}/display-name` + inline "Edit name" action on the Admin → Users tab. Validates length, uniqueness, logs the rename to `audit_log`.

### 2026-02-11 (Round-based open/close + per-team 30-min lock)
- **🚨 Round games stay open until LAST match's KO** — Previous behavior closed the entire Group A MD1 game as soon as the FIRST match (e.g. Mexico–S.Africa) was 30 min away, even though the second match (Czech–Korea) was still 2h+ out. Now:
  - `generate_wc_games()` sets `closes_at = LAST KO` of the round (group games use matchday chunking; round games use chronological slicing).
  - `tick_wc_game_states()` only force-closes when the LAST match is within 30 min.
  - `routes/wc_games.game_detail` + `enter_game` filter is per-team: a team is locked when its OWN match is ≤30 min away or already started; the game itself stays open for other teams' players.
  - **Backfill**: new admin endpoint `POST /api/admin/wc/games/backfill-closes-at` and corresponding "Backfill closes_at" button on the WC Games admin tab. Ran once → 6 games updated, all 26 multi-match games now have correct LAST-KO closes_at.
- **Admin "Open by stage"** — new `POST /api/admin/wc/games/open-stage?stage=group_md1` + dropdown on Admin → WC Games tab. One click opens all 12 Group MD1 games (or all 16 R32 games, etc.) instead of clicking each row.
- **Regression tests** — `tests/test_team_30min_cutoff.py` validates the per-team lock cutoff; `tests/test_round_autoclose.py` validates the per-pick rejection in `enter_game`; `tests/test_group_player_pool.py` validates the 4-team pool fix.

### 2026-02-11 (Group player pool fix)
- **🚨 Group MD mini-games only showing 2 of 4 teams' players** — `/api/fantasy/players?game_id=...` filtered by `country` name, but the denormalised `eligible_country_names` used FIFA spellings (`Czechia`, `South Korea`) while the player rows used Sportmonks spellings (`Czech Republic`, `Korea Republic`). Result: Group A MD1 showed only Mexico + South Africa (52 players) instead of all 4 teams (118). Fixed `list_fantasy_players` in `/app/backend/routes/fantasy.py` to prefer `eligible_team_ids` (exact ID match) and fall back to country names only when team IDs aren't available. Verified all 12 group games × 3 matchdays now return 4 teams of players.
- **Verified locked-team filter + 30-min auto-close** from previous handoff — `/api/wc/games/{id}` correctly removes players from teams whose match has already kicked off, and `enter_game()` rejects picks from locked teams with a clear error. `tick_wc_game_states()` force-closes multi-match games once their first contributing match is within 30 min. Added regression tests at `/app/backend/tests/test_round_autoclose.py` and `/app/backend/tests/test_group_player_pool.py` — both pass.

### 2026-02-10 (part 11: My Teams mini-game card fix)
- **🚨 My Teams mini-game card showing 0/15 + "Match · Any"** — Two bugs in `/api/fantasy/my-teams`:
  1. `len(r.get("players", []))` — wc_game_entries store the lineup in `player_picks`, NOT `players`. So `player_count` was ALWAYS 0 for every mini-game entry. Fixed.
  2. The label builder didn't read the match teams for `game_type=match` games — it concatenated `Match · Any` (the literal `stage` field) instead of fetching the matches row and showing the real team names. Fixed: for single-match games we now join `matches` by `match_id` and surface `home_team_name vs away_team_name` as the title, plus a `match_info` block with logos + kickoff + status + score for the frontend to render the matchup ribbon.
- **MyTeams frontend updated** — Added a small matchup ribbon (home logo · home name · "vs" or live score · away name · away logo) under the mini-game pill so each card visually identifies which fixture the entry covers. Player count denominator switched to `11` for mini-games (correct for single-match entries) instead of the legacy 15/20.

### 2026-02-10 (part 10 — WC kickoff time sync)
- **WC2026 kickoff time corrected** — User confirmed the World Cup opens at **8 PM Nigerian time** = 20:00 WAT (UTC+1) = **19:00 UTC**. Previous hardcoded value across the codebase was `2026-06-11T18:00:00+00:00` (= 19:00 WAT = 7 PM Lagos, off by an hour). Updated all 4 sources of truth: `routes/worldcup.py` `WC2026_START`, `seed_data.py` (competition + prize pool rows), `Header.jsx` `KICKOFF` constant, `RightRail.jsx` `<Countdown to=...>`, and `WorldCupHub.jsx` fallback default. Verified all countdown widgets shift +1 hour after restart.
- **No errors on football page** — Investigated reported errors on `/`: only console warnings were 2 expected 401s for admin-only endpoints (`/api/payments/admin/intents`, `/api/withdrawals/admin/all`) when not signed in. Page renders cleanly with all 142 countries, today's fixtures (Brasileiro U17/U20, MLS Next Pro, ASEAN U19, Club Friendlies), and the right-rail WC widgets.

### 2026-02-10 (part 9 — flags + 4 polish fixes)
- **Flag images snapped to valid flagcdn widths** — `flagUrl()` was building URLs like `flagcdn.com/w72/...` from raw pixel sizes, but flagcdn only serves a fixed width set (20/40/80/160/320/...). Now uses `_snapFlagWidth()` to round up to the next supported width. Verified: page had 249 flag images → 0 broken (previously ~95% broken on WC match cards).
- **Card usage history shows mini-game + main-squad applications** — `/api/cards/me/history` now aggregates from THREE sources (legacy `card_uses`, `wc_game_entries.cards_used`, `fantasy_squads.applied_cards`) and renders the target player + game stage + squad name + settled points/rank for every card spent. Frontend HistoryTab annotated with "Main squad" pill and "+X pts · rank #N" line.
- **Mobile Save Squad bar no longer overlays content** — added `pb-44 lg:pb-5` to BuildTeam container so the last 176px of content has clearance from the floating Save button on mobile.
- **Leaderboard excludes users without squads** — `/api/leaderboard` now filters to users who have either a `fantasy_squads` row OR at least one `wc_game_entries` row. Empty/unstarted accounts no longer pollute the ranking. Total leaderboard rows dropped from "every signup ever" to just real players.
- **Transparent post-settlement squad reveal** — new `GET /api/wc/games/{id}/entries` endpoint returns `{visible: false, reason: "..."}` while a game is still open/closed (so opponents can't copy strategies), and returns the FULL public roster of every entry — captain, vice-captain, all picks WITH photos/team/position, applied card boosts WITH target player + card metadata — once `status == "settled"`. This is the foundation for the post-game "see who beat you" sheet.

### 2026-02-10 (part 8 — prize-pool self-heal + mobile dropdown)
- **🚨 Prize-pool self-heal on every boot** — Previous fixes only restored the seeded base when the doc was INSERTED. Production already had a row with `amount_usd_cents=200` (corrupted by legacy `_contribute_to_pool` that wrote card revenue into the base) so the upsert touched only display fields, never the corruption. Now `seed_prize_pools()` runs an integrity check after each upsert: if `live.amount_usd_cents < seeded_base`, force-set to `seeded_base` and write an `audit_log` row tagged `prize_pool_self_heal` with old/new values. **Verified**: deliberately corrupted the pool to $2.00 → restarted backend → leaderboard immediately shows BASE = $2,500.00 again. No more $0.93/$0.53 tiny payouts.
- **Mobile dropdown for prize distribution** — On phones the 7-tier grid pushed the leaderboard far below the fold and added 400px of scroll. Now `PrizeBreakdown` opens a collapsible `<details>`-style panel — closed by default on <640px viewports (`PRIZE DISTRIBUTION ▸` with helper text "Tap to see 1st–100th payouts"), open by default on desktop. Toggle button has `aria-expanded` for accessibility and a `lb-breakdown-toggle` testid.

### 2026-02-10 (part 7 — NGN/USD wallet conversion + seed fix)
- **🚨 NGN → USD wallet conversion** — User deposited ₦100 (settlement ₦99) but UI showed `$0.99` because `fmtUsd(balance_ngn)` was treating the NGN amount as USD cents (divide-by-100 fallacy). Now:
  - **Backend webhook** (`/api/webhooks/pocketfi`) reads `app_settings.id='currency'.ngn_per_usd` (defaults to 1,400) and mirrors every NGN credit into `users.wallet_balance_usd_cents` so the same deposit funds both the NGN side AND the USD card-purchase wallet without a separate convert step.
  - **`GET /api/wallet/me`** now returns `wallet_balance_usd_cents` alongside the existing `wallet` doc.
  - **Frontend** renders the headline as `₦5,000` (real NGN) with a small `≈ $3.57 · spendable on cards & mini-games` under it. Deposited / Won / Spent all switched to `fmtNgn`. Manual admin credit (`POST /api/admin/wallet/credit-ngn`) gets the same NGN→USD mirror.
  - **One-time backfill endpoint** `POST /api/admin/wallet/backfill-usd` (with `dry_run` flag) walks every existing `user_wallets.balance_ngn` and tops up `users.wallet_balance_usd_cents` so users who deposited BEFORE this fix get their USD spendable balance properly credited. Verified: admin's ₦5,000 → +357 cents → $3.57 spendable.
- **🚨 Prize-pool seed conflict (round 2)** — Previous fix for "kind conflict" was incomplete because `**p` still spread overlapping fields (`title` etc.) into `$setOnInsert` while `$set` also held them. Now the upsert payload is explicitly split: `$setOnInsert` carries only IMMUTABLE fields (`id`, `kind`, `competition_id`, `currency`, `amount_usd_cents`, `amount_total_ngn`), `$set` carries only MUTABLE display fields (`title`, `status`, `image_url`, `payout_structure`, `starts_at`, `ends_at`). Zero overlap → no more conflict, base $2,502 stays seeded across reboots.

### 2026-02-10 (part 6 — prize-pool restoration + UX cleanup)
- **🚨 Prize pool BASE was being silently corrupted ($2,502 → $2.00)** — Two compounding bugs found:
  1. `seed_data.py` did `$set: {k:v for k,v in p.items() if k not in (amount_usd_cents, id, created_at)}` which left `kind` in the `$set` — MongoDB rejects the upsert with `"Updating the path 'kind' would create a conflict at 'kind'"` because the same field is in `$setOnInsert`. So the seeded base never actually got into the pool — every boot logged the warning and the pool stayed at whatever `_contribute_to_pool` had written (usually $0 or just $2 from a couple card purchases). Fixed: `$set` now whitelists only display fields (`title`, `status`, `image_url`, `payout_structure`, `starts_at`, `ends_at`).
  2. `_contribute_to_pool` was incrementing BOTH `amount_usd_cents` (the base) AND `cards_cut_usd_cents` (the bonus) — conflating the two. Base must stay fixed at the admin-configured value; only `cards_cut` grows. Fixed: `_contribute_to_pool` now only `$inc`s `cards_cut_usd_cents` and ships a `$setOnInsert` floor of `amount_usd_cents=250_000` so a missing-pool recovery still shows the correct base.
  - **Verified** after restart: `GET /api/leaderboard` now reports `base=$2,502.00, cards_cut=$2.25, total=$2,504.25`, with the full prize distribution (1st $1,000.94, 2nd $500.54, … per-position 5–15 / 16–20). Mobile screenshot confirms.
- **Ad reward grants ONE FREE CARD, not "+1 use"** — single-use card economy made `+5 card uses` nonsensical. `POST /api/ads/reward/claim` with `reward_type=free_card` now picks a random Star-tier card and adds it to the user's collection (creating a fresh `user_card` or `$inc`-ing an existing one to reflect a second copy). Backwards-compat: still accepts `card_uses` payload from older clients. Frontend label: "Watch ad → +1 FREE Star card" with the gifted card name shown on success ("+1 Mané Lion added to your cards"). Verified against admin user — granted "Mané Lion".
- **Bank name typo fix** — PocketFi ships bank labels as `KudaDymanic` / `kuda_dynamic` / camelCase variants. New `sanitizeBankName()` in `DepositPanel.jsx` normalises them: `KudaDymanic` → `Kuda Dynamic`, `9psb` → `9 Payment Service Bank`, `kuda` → `Kuda Microfinance Bank`, plus a generic camelCase → spaced title-cased fallback. Display-only — doesn't change what the server matches against.

### 2026-02-10 (part 5 — PocketFi webhook signature resilience)
- **Multi-header / multi-algorithm PocketFi verifier** — PocketFi's webhook signature spec is not publicly documented, and the production webhook was failing `Invalid signature` (user reported PFI|260611857730 for ₦100). The verifier now tries every common combination: 12 header name variants (`Pocketfi-Signature`, `X-Pocketfi-Signature`, `X-Signature`, `Signature`, `X-Hub-Signature-256/512`, `Webhook-Signature`, `HTTP_POCKETFI_SIGNATURE`, etc.) × 2 algorithms (SHA-512 + SHA-256) × 2 encodings (hex + base64) × prefix-stripping (`sha512=`, `sha256=`, `v1=`). Constant-time digest comparison preserved. Security gate **intact** — if NONE match, `400 Invalid signature` is still returned. No webhook is ever processed without a valid HMAC.
- **Webhook failure audit trail** — every signature mismatch now persists to `pocketfi_webhook_failures` with the full raw body + all non-sensitive request headers (cookie/authorization redacted) so admins can identify exactly which header PocketFi is sending. Visible in the new Admin → Payments tab; each row shows reference, amount, customer email, and "Signature headers observed" (filtered to anything matching `/sign|hmac|hub|verify/i`).
- **Manual NGN credit admin endpoint + UI** — `POST /api/admin/wallet/credit-ngn` lets admins manually credit stuck NGN deposits when the webhook silently fails. Idempotent on PocketFi `reference` (re-running won't double-credit), updates `user_wallets` + creates an audit-tagged `wallet_transactions` row + marks the matching `ngn_deposits` row as `credited`. Every call is written to `audit_log` with the human reason. New Admin → Payments tab has a credit form and a one-click "Pre-fill from failure" that copies email/amount/reference/reason out of any saved failure record.
- **For Nelson's stuck ₦100 (PFI|260611857730):** redeploy production with this patch, then go to `/admin → Payments`, click "Pre-fill manual credit form" on his failure row (or fill it manually), and submit. The credit is logged so it's traceable.

### 2026-02-10 (part 4 — free-card bug fix + UX polish + mobile fixes)
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
