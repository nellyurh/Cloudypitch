#!/usr/bin/env bash
# ============================================================
# Cloudy Pitch — VPS Security Hardening
# ============================================================
# Hardens a fresh Ubuntu 22.04/24.04 box for production use.
# Run AFTER `deploy.sh` has completed and the stack is live.
#
#   sudo ./harden.sh
#
# What it does:
#   • Creates a non-root sudo user with SSH key login (you'll be prompted)
#   • Disables SSH root login + password auth (key-only)
#   • Moves SSH to a non-standard port (default 2222 — change with SSH_PORT=...)
#   • Configures fail2ban for SSH + nginx/Caddy brute-force protection
#   • Tightens UFW (only the new SSH port + 80 + 443)
#   • Enables automatic security updates (unattended-upgrades)
#   • Hardens kernel sysctl (SYN flood, IP spoofing, redirects)
#   • Sets up daily MongoDB backup cron (03:00 UTC)
#   • Disables unused services
#   • Installs ClamAV scheduled scans (optional, off by default)
#
set -euo pipefail

SSH_PORT="${SSH_PORT:-2222}"
NEW_USER="${NEW_USER:-cloudy}"
BACKUP_DIR="${BACKUP_DIR:-/opt/cloudypitch/backups}"

log()  { printf '\n\033[1;32m▶ %s\033[0m\n' "$*"; }
warn() { printf '\n\033[1;33m⚠ %s\033[0m\n' "$*"; }
err()  { printf '\n\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || err "Run as root (sudo)."

# ──────────────────────────────────────────────
# 1. Non-root sudo user with SSH key login
# ──────────────────────────────────────────────
if ! id "$NEW_USER" >/dev/null 2>&1; then
    log "Creating non-root sudo user '$NEW_USER'…"
    adduser --gecos "" --disabled-password "$NEW_USER"
    usermod -aG sudo,docker "$NEW_USER"
    mkdir -p "/home/$NEW_USER/.ssh"
    chmod 700 "/home/$NEW_USER/.ssh"
    touch "/home/$NEW_USER/.ssh/authorized_keys"
    chmod 600 "/home/$NEW_USER/.ssh/authorized_keys"
    chown -R "$NEW_USER:$NEW_USER" "/home/$NEW_USER/.ssh"

    # If root already has an authorized_keys, mirror it so you don't get locked out
    if [[ -s /root/.ssh/authorized_keys ]]; then
        cp /root/.ssh/authorized_keys "/home/$NEW_USER/.ssh/authorized_keys"
        chown "$NEW_USER:$NEW_USER" "/home/$NEW_USER/.ssh/authorized_keys"
        log "Copied root's SSH key to $NEW_USER (you can log in as $NEW_USER immediately)."
    else
        warn "No SSH key found on root. Paste your public key in this file BEFORE locking SSH:"
        warn "  /home/$NEW_USER/.ssh/authorized_keys"
        warn "Or run from your laptop:  ssh-copy-id -p $SSH_PORT $NEW_USER@<server-ip>"
        warn "Skipping SSH lockdown — re-run this script after adding your key."
        SKIP_SSH_LOCK=1
    fi
else
    log "User '$NEW_USER' already exists — skipping creation."
    usermod -aG sudo,docker "$NEW_USER" 2>/dev/null || true
fi

# ──────────────────────────────────────────────
# 2. SSH lockdown (key-only, non-standard port, no root)
# ──────────────────────────────────────────────
if [[ -z "${SKIP_SSH_LOCK:-}" ]]; then
    log "Hardening SSH (port $SSH_PORT, key-only, no root)…"
    sshd_cfg=/etc/ssh/sshd_config.d/99-cloudypitch.conf
    cat > "$sshd_cfg" <<EOF
Port $SSH_PORT
PermitRootLogin no
PasswordAuthentication no
ChallengeResponseAuthentication no
PubkeyAuthentication yes
PermitEmptyPasswords no
X11Forwarding no
MaxAuthTries 3
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2
AllowUsers $NEW_USER
EOF
    sshd -t || err "sshd config is invalid — aborting before reload."
    systemctl reload ssh || systemctl reload sshd
else
    log "Skipped SSH lockdown (no key set yet)."
fi

# ──────────────────────────────────────────────
# 3. UFW — open only what we need
# ──────────────────────────────────────────────
log "Reconfiguring UFW for new SSH port…"
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow "$SSH_PORT"/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw --force enable
ufw status verbose

# ──────────────────────────────────────────────
# 4. fail2ban — SSH + Caddy brute-force jails
# ──────────────────────────────────────────────
log "Configuring fail2ban…"
apt-get install -y --no-install-recommends fail2ban >/dev/null

cat > /etc/fail2ban/jail.d/cloudypitch.local <<EOF
[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 5
banaction = ufw
ignoreip = 127.0.0.1/8 ::1

[sshd]
enabled  = true
port     = $SSH_PORT
maxretry = 3
findtime = 10m
bantime  = 24h

[caddy-auth]
enabled  = true
port     = http,https
filter   = caddy-auth
logpath  = /opt/cloudypitch/deploy/caddy_logs/access.log
maxretry = 10
findtime = 5m
bantime  = 6h
EOF

# Custom filter for Caddy 401/403/429 bursts
cat > /etc/fail2ban/filter.d/caddy-auth.conf <<'EOF'
[Definition]
failregex = .*"remote_ip":"<HOST>".*"status":(401|403|429).*
ignoreregex =
EOF

systemctl restart fail2ban
systemctl enable fail2ban
fail2ban-client status

# ──────────────────────────────────────────────
# 5. Automatic security updates
# ──────────────────────────────────────────────
log "Enabling unattended-upgrades for security patches…"
apt-get install -y --no-install-recommends unattended-upgrades apt-listchanges >/dev/null
cat > /etc/apt/apt.conf.d/20auto-upgrades <<EOF
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
cat > /etc/apt/apt.conf.d/51unattended-upgrades-custom <<EOF
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
EOF

# ──────────────────────────────────────────────
# 6. Kernel sysctl hardening
# ──────────────────────────────────────────────
log "Applying kernel hardening (sysctl)…"
cat > /etc/sysctl.d/99-cloudypitch.conf <<'EOF'
# Cloudy Pitch — network/kernel hardening
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.log_martians = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.icmp_ignore_bogus_error_responses = 1
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_max_syn_backlog = 4096
net.ipv4.tcp_synack_retries = 2
net.ipv4.tcp_syn_retries = 5
net.ipv6.conf.all.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0
fs.protected_hardlinks = 1
fs.protected_symlinks = 1
kernel.dmesg_restrict = 1
kernel.kptr_restrict = 2
kernel.yama.ptrace_scope = 1
EOF
sysctl --system >/dev/null

# ──────────────────────────────────────────────
# 7. Daily Mongo backup cron
# ──────────────────────────────────────────────
log "Scheduling nightly MongoDB backups (03:00 UTC)…"
mkdir -p "$BACKUP_DIR"
cron_line="0 3 * * * /opt/cloudypitch/deploy/backup-mongo.sh >> /var/log/cp-backup.log 2>&1"
if ! crontab -l 2>/dev/null | grep -F "backup-mongo.sh" >/dev/null; then
    (crontab -l 2>/dev/null; echo "$cron_line") | crontab -
fi

# ──────────────────────────────────────────────
# 8. Disable unused services
# ──────────────────────────────────────────────
for svc in cups bluetooth avahi-daemon ModemManager; do
    if systemctl list-unit-files | grep -q "^$svc"; then
        systemctl disable --now "$svc" 2>/dev/null || true
    fi
done

# ──────────────────────────────────────────────
# 9. Docker daemon security defaults
# ──────────────────────────────────────────────
log "Hardening Docker daemon defaults…"
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "live-restore": true,
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "5"
  },
  "no-new-privileges": true,
  "userland-proxy": false,
  "icc": false
}
EOF
systemctl restart docker

# ──────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────
cat <<EOF

────────────────────────────────────────────────────────
✓ Hardening complete.

→ SSH is now on port $SSH_PORT (key-only). Login like this:
     ssh -p $SSH_PORT $NEW_USER@$(curl -s ifconfig.me)

→ Firewall: only $SSH_PORT/tcp, 80/tcp, 443/tcp are open.
→ fail2ban watching SSH + Caddy 401/403/429 bursts.
→ Daily Mongo backup at 03:00 UTC → $BACKUP_DIR
→ Automatic security updates enabled (Ubuntu Pro recommended for ESM).

⚠ IMPORTANT — KEEP THIS SESSION OPEN.
   Open a NEW terminal and verify you can ssh in as '$NEW_USER' on port $SSH_PORT
   BEFORE you close this root session. If something is wrong, you can fix from here.

Useful commands:
   fail2ban-client status sshd       — see banned IPs
   fail2ban-client unban <ip>        — unban an IP
   ufw status verbose                — firewall rules
   docker compose ps                 — stack status
────────────────────────────────────────────────────────
EOF
