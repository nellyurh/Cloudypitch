#!/usr/bin/env bash
# ============================================================
# Cloudy Pitch — One-Shot Contabo VPS bootstrap & deploy
# ============================================================
# Usage (on a FRESH Ubuntu 22.04/24.04 box, run as root or with sudo):
#
#   curl -fsSL https://raw.githubusercontent.com/<you>/cloudypitch/main/deploy/deploy.sh -o deploy.sh
#   chmod +x deploy.sh
#   sudo ./deploy.sh
#
# Or after cloning:
#   git clone <repo> /opt/cloudypitch && cd /opt/cloudypitch/deploy
#   cp .env.example .env && nano .env   # fill in DOMAIN, MONGO_PASSWORD, API keys
#   sudo ./deploy.sh
#
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/cloudypitch}"
DEPLOY_DIR="$REPO_DIR/deploy"

log() { printf '\n\033[1;32m▶ %s\033[0m\n' "$*"; }
warn() { printf '\n\033[1;33m⚠ %s\033[0m\n' "$*"; }
err()  { printf '\n\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# 0. Pre-flight
[[ $EUID -eq 0 ]] || err "Run as root (sudo)."
. /etc/os-release
[[ "$ID" == "ubuntu" || "$ID" == "debian" ]] || err "Unsupported OS: $ID. Use Ubuntu 22.04+ / Debian 12+."

# 1. System update + base packages
log "Installing system base packages…"
apt-get update -y
apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg lsb-release ufw git fail2ban htop nano

# 2. Docker + Compose plugin
if ! command -v docker >/dev/null 2>&1; then
    log "Installing Docker Engine…"
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/$ID/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/$ID $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
else
    log "Docker already installed: $(docker --version)"
fi

# 3. UFW firewall (open 22 / 80 / 443)
if ! ufw status | grep -q "Status: active"; then
    log "Configuring UFW firewall (22/80/443)…"
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable
else
    log "UFW already enabled."
fi

# 4. Repo / source code
if [[ ! -d "$REPO_DIR" ]]; then
    err "Source not found at $REPO_DIR. Clone your repo first:\n    git clone <your-git-url> $REPO_DIR"
fi
cd "$DEPLOY_DIR"

# 5. .env validation
if [[ ! -f .env ]]; then
    cp .env.example .env
    err ".env not found — created one from .env.example. Edit it (DOMAIN, MONGO_PASSWORD, API keys), then rerun."
fi
# shellcheck disable=SC1091
set -a; . ./.env; set +a
[[ -n "${DOMAIN:-}" ]]          || err "DOMAIN unset in .env"
[[ -n "${MONGO_PASSWORD:-}" ]]  || err "MONGO_PASSWORD unset in .env"
[[ -n "${ADMIN_PASSWORD:-}" ]]  || err "ADMIN_PASSWORD unset in .env"

# 6. Build + bring up
log "Building images (frontend bakes REACT_APP_BACKEND_URL=$PUBLIC_URL)…"
docker compose --env-file .env build

log "Starting full stack (mongo → api → worker → frontend → caddy)…"
docker compose --env-file .env up -d

# 7. Wait for health
log "Waiting for API health…"
for i in {1..40}; do
    if docker compose exec -T api curl -fs http://localhost:8001/api/health >/dev/null 2>&1; then
        log "API is healthy."
        break
    fi
    sleep 3
    [[ $i -eq 40 ]] && warn "API didn't go healthy in 2 min — check: docker compose logs api"
done

# 8. Status
log "Cloudy Pitch is live at https://$DOMAIN"
docker compose ps

cat <<EOF

────────────────────────────────────────────────────────
✓ Deployment complete.

Next steps:
  • Point your domain's A record → this VPS public IP.
  • Caddy will auto-provision Let's Encrypt SSL on first HTTPS hit.
  • Tail logs:        cd $DEPLOY_DIR && docker compose logs -f
  • Restart stack:    docker compose restart
  • Update code:      cd $REPO_DIR && git pull && cd deploy && ./deploy.sh
  • Backup mongo:     ./backup-mongo.sh

Admin login: $ADMIN_EMAIL / (the password you set)
────────────────────────────────────────────────────────
EOF
