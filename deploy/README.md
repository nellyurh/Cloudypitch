# Cloudy Pitch — Contabo VPS Deployment Runbook

A complete, opinionated production deployment for Cloudy Pitch on a fresh Contabo (or any Ubuntu 22.04/24.04) VPS using **Docker Compose + Caddy (auto-SSL) + MongoDB**.

## Architecture

```
                        ┌──────────────┐
   Internet ─── 443 ───►│   Caddy      │  ← auto Let's Encrypt SSL
                        └──┬────────┬──┘
                           │        │
            ┌──────────────┘        └───────────────┐
            ▼                                       ▼
       ┌─────────┐                          ┌─────────────┐
       │ Frontend│  (nginx + static React)  │   API       │  FastAPI · RUN_INGESTION=0
       └─────────┘                          └──────┬──────┘
                                                   │
                                            ┌──────▼──────┐
                                            │   MongoDB   │ persistent volume
                                            └──────▲──────┘
                                                   │
                                            ┌──────┴──────┐
                                            │   Worker    │  same image · RUN_INGESTION=1
                                            └─────────────┘  (Sportmonks · API-Sports · StatPal pollers)
```

**5 containers**: `caddy`, `frontend`, `api`, `worker`, `mongo`.
The API container is stateless and horizontally scalable; the worker is a singleton that owns all background pollers.

---

## 1. Provision the VPS

1. Order a Contabo VPS S/M (or any 4 GB+ RAM, 2 vCPU box) running Ubuntu 24.04.
2. Get the public IPv4 → in your DNS provider create an **A record**:
   `cloudypitch.com → <VPS_IP>` (and optionally `www.cloudypitch.com → <VPS_IP>`).
3. SSH in as `root`:
   ```bash
   ssh root@<VPS_IP>
   ```

## 2. Clone the repo

```bash
apt-get update -y && apt-get install -y git
git clone <your-git-url> /opt/cloudypitch
cd /opt/cloudypitch/deploy
```

> Don't have a git remote yet? Use the **Save to GitHub** button in the Emergent chat input, then `git clone` from there.

## 3. Configure `.env`

```bash
cp .env.example .env
nano .env
```

Fill in these required values:

| Key                 | Example                          | Notes |
|---------------------|----------------------------------|-------|
| `DOMAIN`            | `cloudypitch.com`                | Bare host without scheme. |
| `PUBLIC_URL`        | `https://cloudypitch.com`        | Baked into the React build. |
| `CORS_ORIGINS`      | `https://cloudypitch.com`        | Comma-sep; backend allow-list. |
| `MONGO_USER`        | `cpadmin`                        | DB superuser. |
| `MONGO_PASSWORD`    | 32+ chars random                 | **Use a password manager**. |
| `DB_NAME`           | `cloudypitch`                    | Keep this stable. |
| `ADMIN_EMAIL`       | `admin@cloudypitch.com`          | Seeded on first boot. |
| `ADMIN_PASSWORD`    | 16+ chars random                 | Reset later via `/api/auth/reset`. |
| `SPORTMONKS_API_KEY`| `xxx`                            | https://www.sportmonks.com |
| `APISPORTS_API_KEY` | `xxx`                            | https://api-sports.io |
| `STATPAL_API_KEY`   | `xxx`                            | https://statpal.io |

Optional:
- `PAYSTACK_SECRET_KEY` — for live card-purchase deposits (toggle once Paystack onboarding is approved).
- `RESEND_API_KEY` — real email verification + password reset.
- `EMERGENT_LLM_KEY` — if you're using the Cloudy Pitch admin LLM helpers.

## 4. Run the bootstrap

```bash
chmod +x deploy.sh backup-mongo.sh
sudo ./deploy.sh
```

`deploy.sh` will:
1. Install Docker Engine + Compose plugin (if missing).
2. Configure UFW (allow 22/80/443).
3. Validate your `.env`.
4. `docker compose build` (this takes 3-5 min on a small VPS — pulls Python + Node + nginx + Caddy + Mongo).
5. `docker compose up -d`.
6. Wait for the API health probe.

When the script finishes you'll see `Cloudy Pitch is live at https://cloudypitch.com`. Open it. Caddy issues SSL on first request — give it 10-30 s for the certificate to provision.

## 5. Verify

```bash
# Health endpoint
curl https://cloudypitch.com/api/health
# → {"ok":true}

# Live leaderboard
curl https://cloudypitch.com/api/leaderboard?scope=global

# Container status
cd /opt/cloudypitch/deploy && docker compose ps
```

You should see 5 containers all in state `running (healthy)`.

## 6. Operational runbook

### Tail logs
```bash
docker compose logs -f api       # FastAPI
docker compose logs -f worker    # Ingestion poller
docker compose logs -f caddy     # SSL / proxy
docker compose logs -f mongo
```

### Deploy a new version
```bash
cd /opt/cloudypitch
git pull
cd deploy
./deploy.sh                       # rebuild + restart
```

### Restart only one service
```bash
docker compose restart api
docker compose restart worker
```

### Backup MongoDB
```bash
./backup-mongo.sh
# → /opt/cloudypitch/backups/cp-YYYYMMDD-HHMM.archive
```

Schedule daily backups with cron:
```bash
sudo crontab -e
# add:
0 3 * * * /opt/cloudypitch/deploy/backup-mongo.sh >> /var/log/cp-backup.log 2>&1
```

Restore:
```bash
docker compose exec -T mongo mongorestore \
    --username "$MONGO_USER" --password "$MONGO_PASSWORD" --authenticationDatabase admin \
    --archive < /opt/cloudypitch/backups/cp-20260601-0300.archive
```

### Scale the API horizontally
The API container is stateless. To run multiple replicas behind Caddy:
```bash
docker compose up -d --scale api=3
```
(Caddy will round-robin via Docker DNS.)

### Rotate admin password
```bash
docker compose exec api python -c "
from auth import hash_password
print(hash_password('NEW_PASSWORD_HERE'))
" 
# Take the bcrypt hash, then in mongo shell:
docker compose exec mongo mongosh -u "$MONGO_USER" -p "$MONGO_PASSWORD" --authenticationDatabase admin
> use cloudypitch
> db.users.updateOne({email:'admin@cloudypitch.com'}, {$set:{password_hash:'<paste-hash>'}})
```

## 7. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Caddy: cannot get certificate` | Wait 60 s. If still broken: check DNS A record (`dig cloudypitch.com`), and that ports 80+443 reach the VPS (`ufw status`). |
| `API container exits — Connection refused: mongo` | Mongo healthcheck not green yet. `docker compose logs mongo` — ensure data dir not corrupted. |
| `frontend: 502` | Frontend build failed. `docker compose build frontend` and inspect output. Often `REACT_APP_BACKEND_URL` is empty in `.env`. |
| `Worker not ingesting matches` | Missing provider keys in `.env`. `docker compose exec worker env \| grep API_KEY`. |
| Out-of-memory builds | Add `--memory=2g` to docker build, or upgrade VPS RAM. |

## 8. Hardening (recommended — run AFTER `deploy.sh`)

Use the included `harden.sh` script which automates SSH key-only access, fail2ban, UFW lockdown, kernel sysctl, automatic security updates, Docker daemon hardening, and nightly Mongo backups:

```bash
# Optional — change defaults (SSH port + sudo user)
export SSH_PORT=2222           # default 2222
export NEW_USER=cloudy         # default 'cloudy'

sudo ./harden.sh
```

⚠️ **Before logging out**, open a second terminal and verify:
```bash
ssh -p 2222 cloudy@<your-server-ip>
```
If you can log in, the lockdown worked. If not — keep your original root SSH session open and re-paste your public key into `/home/cloudy/.ssh/authorized_keys`.

What `harden.sh` does:
- Creates a non-root sudo user with SSH key login.
- Disables SSH root login + password authentication.
- Moves SSH to port 2222 (or your choice).
- Configures fail2ban for SSH (3 attempts → 24 h ban) + Caddy 401/403/429 bursts.
- Tightens UFW (only the new SSH port + 80 + 443).
- Enables automatic Ubuntu security updates with weekly auto-reboot at 04:00.
- Applies kernel sysctl hardening (SYN flood, IP spoofing, ICMP redirects).
- Schedules nightly Mongo backups at 03:00 UTC.
- Disables unused services (cups, bluetooth, avahi).
- Hardens Docker daemon (`no-new-privileges`, capped log files, disabled inter-container ICC).

Additional manual recommendations:
- Add **Cloudflare** in front of Caddy → DNS proxy mode → blocks 99 % of bot traffic before it reaches the VPS. Update `CORS_ORIGINS` accordingly.
- Enable **Uptime Kuma** (`docker run -d -p 3001:3001 louislam/uptime-kuma`) and monitor `https://cloudypitch.com/api/health`.
- Off-box Mongo backups → after a few days, sync `/opt/cloudypitch/backups/` to S3 / Backblaze B2 with `rclone`.

---

**Generated:** 2026-06-01 · Cloudy Pitch v1.0
