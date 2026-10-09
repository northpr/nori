#!/bin/bash
# Nori bootstrap: turn a FRESH Ubuntu 24.04+ server into a box that is ready for setup.sh.
# Run ONCE as root, from the copy of this repo (with your nori.conf next to it) on the server:
#     cd /root/nori && bash bootstrap.sh          (or: sudo bash bootstrap.sh)
# Safe to run again: every step checks first. Nothing here needs a secret.
#
#   bash bootstrap.sh --plan    only print what would be installed/created for your nori.conf
#
# What it does, in order:
#   1. sets timezone + hostname from nori.conf
#   2. installs packages: git jq tmux curl ufw rsync gnupg unzip, gh, Node 22, Bun, uv, Tailscale,
#      Docker (only if PLANE=true), Chromium for Playwright (only if BROWSER=true)
#   3. creates the admin user (sudo, key-only) and one user per area (NO sudo, home private)
#   4. installs Claude Code for each of those users
#   5. firewall (ufw): SSH open, everything else only via the Tailscale interface
#   6. SSH hardening (no passwords, no root login) once the admin user has your key
#   7. unattended security updates with a reboot window (if AUTO_UPDATES=true)
#   8. copies this repo to the admin's home (~/nori) and prints the next MANUAL steps
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
export NORI_ROOT="$REPO"
# shellcheck disable=SC1091
. "$REPO/scripts/conf.sh"

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
warn() { printf '\033[33mwarning: %s\033[0m\n' "$*" >&2; }
die()  { printf '\033[31merror: %s\033[0m\n' "$*" >&2; exit 1; }

if [[ ${1:-} == --plan ]]; then
  echo "preset     : $PRESET (Ops bot: $OPS_BOT, Plane: $PLANE, browser: $BROWSER, previews: $PREVIEWS)"
  echo "admin user : $ADMIN_USER (sudo)"
  echo "area users : $AREAS (no sudo)"
  echo "timezone   : $TIMEZONE   hostname: $SERVER_NAME"
  echo "installs   : base packages, gh, Node 22, Bun, uv, Tailscale, Claude Code$(is_on PLANE && echo ', Docker')$(is_on BROWSER && echo ', Chromium (Playwright)')"
  echo "firewall   : ufw, SSH open, rest only on tailscale0"
  echo "updates    : $(is_on AUTO_UPDATES && echo "unattended, reboot window $AUTO_REBOOT_TIME" || echo "not configured")"
  exit 0
fi

[[ $EUID -eq 0 ]] || die "run as root (sudo bash bootstrap.sh)"
. /etc/os-release
[[ ${ID:-} == ubuntu ]] || die "this script is written for Ubuntu (found ${PRETTY_NAME:-unknown}). Other distros: follow docs/setup-guide.md by hand."
dpkg --compare-versions "${VERSION_ID:-0}" ge 24.04 || die "Ubuntu 24.04 or newer needed (found $VERSION_ID)"
[[ $ADMIN_USER =~ ^[a-z][a-z0-9_-]*$ ]] || die "bad ADMIN_USER"
export DEBIAN_FRONTEND=noninteractive

# ---------------------------------------------------------------- 1. basics
say "timezone and hostname"
timedatectl set-timezone "$TIMEZONE" || warn "could not set timezone $TIMEZONE (check the name in nori.conf)"
[[ $(hostname) == "$SERVER_NAME" ]] || hostnamectl set-hostname "$SERVER_NAME" || warn "could not set hostname"

# ---------------------------------------------------------------- 2. packages
say "base packages"
apt-get update -q
apt-get install -y -q git jq tmux curl ca-certificates gnupg ufw rsync unzip openssl sudo python3 \
  unattended-upgrades apt-transport-https

if ! command -v gh >/dev/null; then
  say "GitHub CLI (gh)"
  install -dm 755 /etc/apt/keyrings
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /etc/apt/keyrings/githubcli-archive-keyring.gpg
  chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    > /etc/apt/sources.list.d/github-cli.list
  apt-get update -q && apt-get install -y -q gh
fi

if ! command -v node >/dev/null || [[ $(node -p 'process.versions.node.split(".")[0]') -lt 22 ]]; then
  say "Node.js 22 (NodeSource)"
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y -q nodejs
fi

if ! command -v bun >/dev/null; then
  say "Bun (system-wide; the Telegram plugin needs it)"
  curl -fsSL https://bun.sh/install | BUN_INSTALL=/usr/local bash
fi

if ! command -v uv >/dev/null; then
  say "uv (Python tooling)"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh
fi

if ! command -v tailscale >/dev/null; then
  say "Tailscale"
  curl -fsSL https://tailscale.com/install.sh | sh
fi

if is_on PLANE && ! command -v docker >/dev/null; then
  say "Docker (needed for Plane)"
  curl -fsSL https://get.docker.com | sh
fi

if is_on BROWSER && [[ ! -d /opt/ms-playwright ]]; then
  say "Chromium for the browser MCP (shared in /opt/ms-playwright)"
  # playwright version = what @playwright/mcp@0.0.82 (server/bin/browser-mcp) depends on; move both pins together
  if PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright npx -y playwright@1.64.0-alpha-1789764292000 install --with-deps chromium; then
    chmod -R a+rX /opt/ms-playwright
  else
    warn "Chromium install failed. Check 'npx playwright install --help' and re-run, or set BROWSER=false."
  fi
fi

# ---------------------------------------------------------------- 3. users
say "admin user: $ADMIN_USER"
if ! id "$ADMIN_USER" >/dev/null 2>&1; then
  useradd -m -s /bin/bash -G sudo "$ADMIN_USER"
  passwd -l "$ADMIN_USER" >/dev/null     # no password: you log in with your SSH key; sudo needs no password
fi
# Passwordless sudo is what lets the Ops bot and setup.sh reach the area users. Acceptable because
# login is key-only; see docs/setup-guide.md ("Why passwordless sudo").
echo "$ADMIN_USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-nori-admin
chmod 440 /etc/sudoers.d/90-nori-admin
visudo -cf /etc/sudoers.d/90-nori-admin >/dev/null || { rm -f /etc/sudoers.d/90-nori-admin; die "sudoers file invalid"; }
AH=$(getent passwd "$ADMIN_USER" | cut -d: -f6)
if [[ -s /root/.ssh/authorized_keys && ! -s $AH/.ssh/authorized_keys ]]; then
  install -d -m 700 -o "$ADMIN_USER" -g "$ADMIN_USER" "$AH/.ssh"
  install -m 600 -o "$ADMIN_USER" -g "$ADMIN_USER" /root/.ssh/authorized_keys "$AH/.ssh/authorized_keys"
  echo "copied root's authorized_keys to $ADMIN_USER"
fi
chmod 750 "$AH"
loginctl enable-linger "$ADMIN_USER"
getent group docker >/dev/null && usermod -aG docker "$ADMIN_USER"

for a in $AREAS; do
  say "area user: $a"
  [[ $a =~ ^[a-z][a-z0-9]{0,15}$ ]] || die "bad area name '$a'"
  id "$a" >/dev/null 2>&1 || useradd -m -s /bin/bash "$a"
  gpasswd -d "$a" sudo >/dev/null 2>&1 || true
  chmod 700 "$(getent passwd "$a" | cut -d: -f6)"      # other users (also the admin without sudo) can't read it
  loginctl enable-linger "$a"                          # user services (the Claude session) start at boot
  install -d -o "$a" -g "$a" "$(getent passwd "$a" | cut -d: -f6)/projects"
done

# ---------------------------------------------------------------- 4. Claude Code
for u in "$ADMIN_USER" $AREAS; do
  h=$(getent passwd "$u" | cut -d: -f6)
  if [[ ! -x $h/.local/bin/claude ]]; then
    say "Claude Code for $u"
    sudo -u "$u" -H bash -c 'curl -fsSL https://claude.ai/install.sh | bash' \
      || warn "Claude Code install failed for $u. Manual step: sudo -iu $u, then follow https://docs.claude.com/en/docs/claude-code/setup (or: npm install -g @anthropic-ai/claude-code)."
  fi
done

# ---------------------------------------------------------------- 5. firewall
say "firewall (ufw)"
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw allow 22/tcp comment "ssh" >/dev/null           # keep until Tailscale SSH works for you, then optionally close it
ufw allow in on tailscale0 comment "tailnet" >/dev/null
ufw --force enable >/dev/null
echo "Note: Docker-published ports bypass ufw. Plane binds to the Tailscale IP only (setup.sh does that)."

# ---------------------------------------------------------------- 6. SSH hardening
if [[ -s $AH/.ssh/authorized_keys ]]; then
  say "SSH: key-only, no root login"
  cat > /etc/ssh/sshd_config.d/10-nori.conf <<'SSHEOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
SSHEOF
  if sshd -t; then systemctl reload ssh || systemctl reload sshd || true; else rm -f /etc/ssh/sshd_config.d/10-nori.conf; warn "sshd config test failed, hardening skipped"; fi
else
  warn "$ADMIN_USER has no authorized_keys; SSH hardening skipped. Add your public key, then re-run this script."
fi

# ---------------------------------------------------------------- 7. updates
if is_on AUTO_UPDATES; then
  say "unattended security updates (reboot window $AUTO_REBOOT_TIME)"
  cat > /etc/apt/apt.conf.d/20auto-upgrades <<'APTEOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APTEOF
  cat > /etc/apt/apt.conf.d/52nori-unattended <<APTEOF
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "$AUTO_REBOOT_TIME";
APTEOF
fi

# ---------------------------------------------------------------- 8. repo copy + next steps
say "copying Nori to $AH/nori"
if [[ $REPO != "$AH/nori" ]]; then
  install -d -o "$ADMIN_USER" -g "$ADMIN_USER" "$AH/nori"
  rsync -a --exclude .git --exclude generated --exclude SETUP-PROGRESS.md "$REPO/" "$AH/nori/"
  chown -R "$ADMIN_USER:$ADMIN_USER" "$AH/nori"
fi

cat <<NEXT

Bootstrap done. The remaining steps are MANUAL (docs/setup-guide.md has the details):

  1. In a NEW terminal, test:  ssh $ADMIN_USER@<server-ip>    (keep this root session open until it works)
  2. Join the tailnet:         sudo tailscale up --hostname=$SERVER_NAME     (open the printed link in your browser)
  3. Log Claude in, once per user, with YOUR OWN subscription:
       claude auth login --claudeai                      (as $ADMIN_USER)
       sudo -iu <area> claude auth login --claudeai      (for each of: $AREAS)
     Then start 'claude' once in ~/projects/<area> as that user and accept the folder-trust prompt.
     Do this BEFORE the bot token exists on the box (see the warning about a second bot in docs/troubleshooting.md).
  4. Install the chat plugin for each area user (from claude-plugins-official), e.g.
       sudo -iu <area> claude plugin marketplace add anthropics/claude-plugins-official
       sudo -iu <area> claude plugin install telegram@claude-plugins-official
  5. Put the bot tokens on the server yourself (hidden prompt, never in a chat):
       ~/nori/server/bin/set-token <area>$(is_on OPS_BOT && echo '      and      ~/nori/server/bin/set-token ops')
  6. Apply the config:         cd ~/nori && ./setup.sh && ./setup.sh --check

NEXT
