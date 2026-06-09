# Cloudy Pitch — PRD

## Original Problem Statement
Global multi-sport livescore + predictions + fantasy platform launching for FIFA WC 2026. Sofascore-inspired dense UI. African football core audience, USD pricing with NGN supported. Live at https://cloudypitch.com.

## Tech Stack
- React 18 + Tailwind + Shadcn UI (frontend)
- FastAPI + Motor MongoDB (backend) on Caddy + Docker on Contabo VPS
- Opaque cookie auth
- Sportmonks (data), Trybit/CryptoCloud (crypto deposits), PocketFi (NGN), Google AdSense

## Implemented (rolling)
- 2026-02-09: **LegendCardArt premium redesign** — 3 distinct FUT/FIFA-style tier frames (Gold rays, Elite holo, Epic lava) with Cinzel serif, stat grid, corner filigree, sheen sweep, noise grain
- 2026-02-09: Verified Header "WC26" + stacked sport-tab icons (icon-on-top, Sofascore parity)
- Earlier: WC Hub 3-col redesign, Header group ticker, Trybit/PocketFi/AdSense, team management formations+bench, transfer-card consumption, /team/:name page, watermarks removed

## P1 Backlog
- Random Card Drop System (every 5 actions drops free card; rare GOLD)
- Flutter wrapper readiness (token/cookie path documentation)
- Real Email Verification (BLOCKED — awaiting Resend/SendGrid key)

## P2 Backlog
- Admin Favicon Upload
- Admin save-button audit on non-pricing tabs
- API-Sports basketball stats wiring → BasketballStatsView
- Refactor Admin.jsx (~900 lines)

## Mocked / Blocked
- Real Emails: MOCKED (returns dev_token)
- KYC: MOCKED

## Test credentials
See /app/memory/test_credentials.md
