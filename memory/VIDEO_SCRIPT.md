# Cloudy Pitch — World Cup 2026 Fantasy: 1-Minute Video Brief

Total runtime: **~60 seconds** · VO target ≈ **150 words**.
Capture screens at 1280×900 (desktop) and 390×844 (mobile) so the editor can pick.

---

## The 6 Things a User Gets (the "story")

1. **One main 15-man squad** for the whole tournament (€100M budget).
2. **148 mini-games** to play alongside it (per-match, per-group, per-round).
3. **Free daily card rewards** for staying active.
4. **Legend Cards** (Gold/Elite/Star) you can buy or earn to boost any player.
5. **Substitutions + Transfers** anytime before the gameweek deadline.
6. **Live prize pool** + leaderboard across all games.

---

## Scene-by-Scene (storyboard for editor)

| t (s) | Screen / Route                     | What to show                                                                                  |
|-------|-----------------------------------|------------------------------------------------------------------------------------------------|
| 0–4   | `/`  (Home)                        | Sofascore-style hub, live group ticker scrolling, "WC26" tab.                                  |
| 4–8   | `/fantasy` (competition picker)    | "Choose a competition" card — FIFA World Cup 2026 lit up; Champions League / Euros locked.     |
| 8–15  | `/build-team`                      | Pitch with Sportmonks player photos + flag chips. Pan across all 15 players.                  |
| 15–20 | `/build-team` (picker open)        | Player list with photo, price (€11.5M Yamal, €11.5M Dembélé, etc.), filter.                   |
| 20–27 | `/build-team` → tap a player       | **Player Detail bottom sheet** — PTS/MATCH · FORM · SELECTED % · TOTAL + R1/R2/R3 fixture bars.|
| 27–32 | Substitutions mode + Transfers UI  | Tap "Substitutions" → swap. Then open Transfers → free count + bank + 4pt penalty pill.        |
| 32–40 | `/cards`                           | FUT-style **GOAT · Elite · Star** cards; show "Buy" CTA + counter "Prize pool +$X".            |
| 40–47 | `/leaderboards` (Fantasy tab)      | Live leaderboard — Rank · User · Points · **Prize $**. Highlight live "Prize pool: $X,XXX".    |
| 47–53 | Daily drop toast                   | "Matchday Reward!" toast with card art — caption: "Free card every active day".                |
| 53–60 | `/fantasy` → WC hub                | 148 mini-games grid + prize pool counter + logo end frame.                                     |

---

## Voice-Over Script (~150 words)

> **(0–10s)** *Welcome to Cloudy Pitch — the home of World Cup 2026 fantasy.*
> *Pick one competition, build one squad, and play 148 mini-games all in one place.*
>
> **(10–22s)** *You get a 100-million-euro budget to draft 15 stars: two keepers, five defenders, five midfielders, and three forwards.*
> *Tap any player to see their form, selected percentage, total points, and the difficulty of their next three fixtures.*
>
> **(22–32s)** *Make substitutions any time before the deadline.*
> *Run out of free transfers? Grab a Transfer Pack — five moves for two dollars — or pay just four points.*
>
> **(32–47s)** *Buy or earn Legend Cards — Star, Elite, even Gold — and apply them to multiply any player's points.*
> *And here's the magic: half of every card sale flows straight into the live prize pool — the more you boost, the bigger everyone's payout.*
>
> **(47–60s)** *Climb the leaderboard. The top 100 share the prize. Build. Boost. Win. Cloudy Pitch — your World Cup. Your team.*

---

## Concrete Features We've Built (for talking points / chyrons)

### The main 15-man squad
- €100M budget, formation chips (3-4-3, 3-5-2, 4-3-3, 4-4-2, 5-3-2, 5-4-1).
- Real Sportmonks player photos + country flag chip on every avatar.
- Opponent code below the name (e.g. `MOR`, `CRO`) sourced from Round 1 fixtures.
- Captain (×2) + Vice-Captain auto-fallback.
- Bench order, position-validated substitutions.

### Player Detail Bottom Sheet (Sofascore-style)
- Photo + flag + price + position.
- 4 stat boxes: **PTS/MATCH, FORM, SELECTED %, TOTAL** — each with `n of 493` position rank.
- **R1/R2/R3** fixture chips coloured green → red by difficulty.
- One-tap **Remove** or **Replace**.

### Transfers
- Free transfers tracker, transfer fee (4 pts) once you exceed.
- Bank balance live in the header.
- Pay via wallet, crypto (Trybit) or NGN virtual account (PocketFi).

### Legend Cards (premium look + boost mechanic)
- Three tiers, each with a distinct FUT-grade design:
  - **GOAT (Gold)** — black backdrop, radiating gold rays, ornate serif "99 GOAT".
  - **Elite** — emerald + holographic chrome stripes + star burst.
  - **Star (Epic)** — crimson lava + bronze frame + glow halo.
- Buy with USD / NGN / crypto, or earn for free via drops.
- Apply on any player in any of your 148 game entries.

### Random Card Drops (retention loop)
- **Daily Matchday Reward**: 1 free Star card any day you predict/build/edit.
- **Final Day Twist**: 10% chance the daily drop becomes a GOLD.
- **In-session drop**: every 5 actions → 1 random card.
- Each drop celebrated with a Sonner toast that previews the card art.

### 148 WC Mini-Games (extra TAM per user)
- 104 single-match games · 36 group-stage games · 8 round-wide games.
- Build a fresh 15- or 20-man squad per game, with optional Bench Boost.
- Apply Legend Cards anywhere.
- Admin lock/unlock per game — locked games show 🔒 "Closed" badge.

### Live Leaderboard (the prize page)
- Route: **`/leaderboards`** — global ranking across all WC2026 squads.
- Each row shows: **Rank · Username · Country flag · Points · Prize ($)**.
- Top 100 are paid:
  - **#1** $1,000 · **#2** $500 · **#3** $300 · **#4** $200 (base tier).
  - **#5–#15** share the next base slice.
  - **#16–#100** share the dynamic Cards Cut slice.
- Updates in near-real-time as gameweek scores settle.
- Your own row sticky-highlights so you always see where you stand.

### Dynamic Prize Pool — "the more you spend, the bigger you win"
- **Starting pool**: **$2,500 base** seeded by Cloudy Pitch.
- Every time anyone buys a Legend Card or Transfer Pack, **50 % of that revenue goes straight into the prize pool** (`pool-cloudypitch-unified.cards_cut_usd_cents`).
- That extra `cards_cut` slice is then split:
  - **25 %** added to the Top 4 (×4 positions).
  - **25 %** spread across #5–#15 (11 positions).
  - **50 %** spread across #16–#100 (85 positions).
- On screen this looks like a **live ticking counter** at the top of `/leaderboards` and on the WC hub — every purchase animates the number upward.
- Public ticker: the **last 5 anonymised card purchases** are shown ("****1234 bought Elite +$2,500") to social-proof the rising pot.

### Transfers — full mechanic
- **Free transfers** per gameweek — count visible in the Transfers panel.
- **Out of frees?** Two options:
  1. **Buy a Transfer Pack** — **5 moves for $2** via wallet (instant). Pack purchases also feed the prize pool (50 %).
  2. **Pay with points** — burn **4 leaderboard points** to push a single transfer.
- Transfer market panel shows: `Remaining transfers · Total used · Pack price · Point penalty · Bank`.
- Each transfer is logged in the audit trail; the gameweek settler applies point penalties automatically.

### Cross-cutting features
- Live group-stage ticker and group standings widget in header.
- "Until deadline" countdown card on every team page.
- Substitutions + Transfers buttons present on every team page (universal action row).
- Sponsor ad slots + AdSense fallback, hidden for premium.
- Multi-currency: USD primary, NGN supported, € for fantasy prices to match the Sofascore-style economy.

---

## On-screen captions / lower-thirds (drop in over scenes)

- *"€100M budget. 15 players. 1 trophy."*
- *"148 ways to win."*
- *"Sportmonks-powered. Real photos. Real stats."*
- *"5 transfers for $2 — or 4 points."*
- *"50% of every card sale = bigger prize pool for everyone."*
- *"Top 100 get paid."*
- *"Earn cards. Boost players. Win bigger."*
- *"Built for African fans. Open to the world."*

---

## Capture checklist for the videographer

- [ ] Capture at desktop **1280×900** AND mobile **390×844** for both vertical & horizontal cuts.
- [ ] Record 10 s of idle pitch (no clicks) so editor can layer the VO cleanly.
- [ ] Catch a real "Matchday Reward!" toast on screen.
- [ ] Hover/tap each Legend Card tier to show the metallic sheen sweep animation.
- [ ] Show the **group ticker** strip in the header scrolling at least one full loop.
- [ ] Record the **prize-pool counter** at `/leaderboards` ticking up after a card purchase (do a $1 demo buy on stage so the number visibly jumps).
- [ ] Capture **public ticker row** of anonymised card buys feeding the pool.
- [ ] Show the **leaderboard top 10** with their prize-USD column.
- [ ] Show the **Transfer Pack purchase modal** ($2 → +5 transfers) and the **−4pt point-penalty alternative**.
- [ ] End frame: Cloudy Pitch logo + tagline.

---

*Doc maintained at `/app/memory/VIDEO_SCRIPT.md` — update when the model evolves.*
