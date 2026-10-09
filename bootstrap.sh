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
#   3. creates the admin user (sudo, key-only) and one user per area (NO sudo, home private), installs the
#      root helper /usr/local/sbin/nori-root and the admin's sudo rule (ADMIN_SUDO in nori.conf)
#   4. installs Claude Code (the pinned version, no self-updates) for each of those users, plus machine-wide
#      Claude settings in /etc/claude-code (pushes/merges always ask)
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
  echo "admin sudo : $ADMIN_SUDO ($([[ $ADMIN_SUDO == full ]] && echo 'passwordless sudo for everything' || echo 'passwordless only as the area users + nori-root; the rest asks the admin password; needs classic sudo, so not yet on Ubuntu 26.04 (sudo-rs)'))"
  echo "area users : $AREAS (no sudo)"
  echo "timezone   : $TIMEZONE   hostname: $SERVER_NAME"
  echo "installs   : base packages, gh, Node 22, Bun, uv, Tailscale, Claude Code $(nori_claude_version)$(is_on PLANE && echo ', Docker')$(is_on BROWSER && echo ', Chromium (Playwright)')"
  echo "firewall   : ufw, SSH open, rest only on tailscale0"
  echo "updates    : $(is_on AUTO_UPDATES && echo "unattended, reboot window $AUTO_REBOOT_TIME" || echo "not configured")"
  exit 0
fi

[[ $EUID -eq 0 ]] || die "run as root (sudo bash bootstrap.sh)"
. /etc/os-release
[[ ${ID:-} == ubuntu ]] || die "this script is written for Ubuntu (found ${PRETTY_NAME:-unknown}). Other distros: follow docs/setup-guide.md by hand."
dpkg --compare-versions "${VERSION_ID:-0}" ge 24.04 || die "Ubuntu 24.04 or newer needed (found $VERSION_ID)"
[[ $ADMIN_USER =~ ^[a-z][a-z0-9_-]*$ ]] || die "bad ADMIN_USER"
[[ $ADMIN_SUDO == limited || $ADMIN_SUDO == full ]] || die "ADMIN_SUDO must be limited or full"
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
  passwd -l "$ADMIN_USER" >/dev/null     # no password yet: you log in with your SSH key (set one for ADMIN_SUDO=limited)
fi
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

# The root helper: the few root actions setup.sh needs. A root-owned COPY, never a link into ~/nori.
say "root helper and the admin's sudo rule (ADMIN_SUDO=$ADMIN_SUDO)"
rm -f /usr/local/sbin/nori-root
install -o root -g root -m 755 "$REPO/server/sbin/nori-root" /usr/local/sbin/nori-root
# Passwordless sudo is what lets the Ops bot, cron and setup.sh reach the area users; see docs/setup-guide.md
# ("Why passwordless sudo at all"). limited: only as the area users + nori-root; everything else as root asks the
# admin's password. So limited needs a password, or nobody could become root: until then we stay on full.
sudo_mode=$ADMIN_SUDO
sudo_held=""   # why limited isn't applied yet: sudo-rs | password
# Ubuntu 26.04 ships sudo-rs. The limited rule (runas list, last match wins, visudo -cf on a temp file) is only
# tested with classic sudo ("Sudo version 1.9..."), so on anything else we stay on full until it is.
if [[ $sudo_mode == limited && $(sudo -V 2>/dev/null | head -n 1) != "Sudo version "* ]]; then
  sudo_mode=full; sudo_held=sudo-rs
  warn "ADMIN_SUDO=limited is only tested with classic sudo; this box has '$(sudo -V 2>/dev/null | head -n 1)' (Ubuntu 26.04 uses sudo-rs).
  sudo stays passwordless for everything here for now (as ADMIN_SUDO=full)."
fi
if [[ $sudo_mode == limited && $(passwd -S "$ADMIN_USER" | awk '{print $2}') != P ]]; then
  sudo_mode=full; sudo_held=password
  warn "ADMIN_SUDO=limited needs a password for $ADMIN_USER first, so sudo stays passwordless for everything for now.
  Set one:  sudo passwd $ADMIN_USER      then re-run:  sudo bash ~/nori/bootstrap.sh"
fi
area_list=$(printf '%s,' $AREAS); area_list=${area_list%,}   # "a b" -> "a,b"
rule=$(mktemp /etc/sudoers.d/.nori.XXXXXX)            # a name with a dot: sudo ignores it until it is moved
if [[ $sudo_mode == limited ]]; then
  # sudo uses the LAST matching line, so the general rule (asks the password) comes first
  printf '%s\n' "# Nori (ADMIN_SUDO=limited). Change it in nori.conf and re-run bootstrap.sh." \
    "$ADMIN_USER ALL=(ALL) ALL" \
    "$ADMIN_USER ALL=($area_list) NOPASSWD: ALL" \
    "$ADMIN_USER ALL=(root) NOPASSWD: /usr/local/sbin/nori-root" > "$rule"
else
  printf '%s\n' "# Nori (ADMIN_SUDO=full). Change it in nori.conf and re-run bootstrap.sh." \
    "$ADMIN_USER ALL=(ALL) NOPASSWD:ALL" > "$rule"
fi
chmod 440 "$rule"
visudo -cf "$rule" >/dev/null || { rm -f "$rule"; die "sudoers rule invalid, nothing changed"; }
mv -f "$rule" /etc/sudoers.d/90-nori-admin
echo "sudo for $ADMIN_USER: $sudo_mode"

# ---------------------------------------------------------------- 4. Claude Code
# The tested version (server/claude-code.version), or CLAUDE_CODE_VERSION from nori.conf. Auto-updates are off
# (settings below), so a re-run reinstalls only when a user's version differs from an exact wanted one, and never
# downgrades unless CLAUDE_CODE_VERSION in nori.conf asks for it (nori_claude_plan in scripts/conf.sh).
CC_WANT=$(nori_claude_version)
[[ $CC_WANT =~ ^([0-9]+\.[0-9]+\.[0-9]+|stable|latest)$ ]] || die "bad Claude Code version '$CC_WANT' (CLAUDE_CODE_VERSION or server/claude-code.version)"
for u in "$ADMIN_USER" $AREAS; do
  h=$(getent passwd "$u" | cut -d: -f6)
  if [[ ! -x $h/.local/bin/claude ]]; then
    say "Claude Code $CC_WANT for $u"
    sudo -u "$u" -H bash -c 'curl -fsSL https://claude.ai/install.sh | bash -s "$1"' _ "$CC_WANT" \
      || warn "Claude Code install failed for $u. Manual step: sudo -iu $u, then: curl -fsSL https://claude.ai/install.sh | bash -s $CC_WANT"
  elif [[ $CC_WANT =~ ^[0-9] ]]; then
    have=$(cd / && sudo -u "$u" -H "$h/.local/bin/claude" --version 2>/dev/null | awk '{print $1}') || have=""
    case $(nori_claude_plan "$have" "$CC_WANT") in
      ok) ;;
      keep-newer) warn "Claude Code for $u is $have, newer than the tested $CC_WANT: kept (no silent downgrade). To go back: CLAUDE_CODE_VERSION=$CC_WANT in nori.conf" ;;
      *) say "Claude Code for $u: ${have:-unknown} -> $CC_WANT"
         (cd / && sudo -u "$u" -H "$h/.local/bin/claude" install "$CC_WANT") || warn "claude install $CC_WANT failed for $u" ;;
    esac
  fi
done

# Machine-wide Claude settings that no session can change (root-owned; managed settings beat user/project ones):
# no self-updates, and pushes/merges always ask (+ the push-guard hook from the root-owned shared copy in /opt/nori,
# which setup.sh keeps up to date). Fixed content from the repo; re-running bootstrap.sh updates it.
# EXTRA_ASK_PERMISSIONS and the per-area GitHub-comment rules stay user-level (setup.sh merges them): they change
# with nori.conf, setup.sh runs as the admin without writing to /etc, and managed rules apply to every user alike.
say "Claude managed settings (/etc/claude-code/managed-settings.d/50-nori.json)"
install -D -m 644 -o root -g root "$REPO/server/claude/managed-settings.json" /etc/claude-code/managed-settings.d/50-nori.json
if [[ ! -e /opt/nori/server/bin/push-guard ]]; then   # until the first setup.sh publishes /opt/nori
  install -D -m 755 -o root -g root "$REPO/server/bin/push-guard" /opt/nori/server/bin/push-guard
fi

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
if [[ $sudo_held == password ]]; then
  cat <<NEXT
  Then switch to limited sudo (docs/setup-guide.md step 3): as $ADMIN_USER run  sudo passwd $ADMIN_USER
  (keep the password in your password manager), then  sudo bash ~/nori/bootstrap.sh  once more.

NEXT
fi
