#!/bin/bash
# Apply this repo + nori.conf to the server. Run ON the server, as the admin user, from ~/nori:
#   ./setup.sh                    render + link/apply everything (idempotent)
#   ./setup.sh --check            show drift only, change nothing
#   ./setup.sh --restart          apply, then restart the Claude sessions + Ops bot
#                                 (needed after rules / settings / plugin changes; wipes the sessions' chat)
#   ./setup.sh --render-only DIR  just render the generated files (rules, git config, cron, ...) into DIR;
#                                 touches nothing else, needs no sudo (handy to preview what a config produces)
#
# Users: the admin (sudo) runs the Ops bot, cron and this script. Each area user (no sudo, home not
# readable by the others) runs one Claude session. The admin publishes a read-only copy of this repo to
# /opt/nori; setup-user.sh (run as each area user) links from there. Secrets never live in the repo.
# sudo is only used as `sudo -u <area>` and `sudo nori-root <subcommand>` (the root helper bootstrap.sh
# installs; with ADMIN_SUDO=limited nothing else runs as root without a password). tests/ check this.
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
MODE=apply; RENDER_DIR=""
case "${1:-}" in
  ""|apply) ;;
  --check|--restart) MODE="$1" ;;
  --render-only) MODE=render; RENDER_DIR="${2:?usage: setup.sh --render-only <dir>}" ;;
  -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
  *) echo "unknown option: $1 (see ./setup.sh --help)" >&2; exit 2 ;;
esac

export NORI_ROOT="$REPO"
# shellcheck disable=SC1091
. "$REPO/scripts/conf.sh"
# shellcheck disable=SC1091
. "$REPO/scripts/lib.sh"
# shellcheck disable=SC1090
. "$REPO/chat/$CHAT/platform.conf" 2>/dev/null || { echo "no chat/$CHAT/platform.conf" >&2; exit 2; }

if [[ $MODE == render ]]; then
  python3 "$REPO/scripts/render.py" "$REPO" "$RENDER_DIR"
  exit $?
fi

[[ $(id -un) == "$ADMIN_USER" ]] || { echo "setup.sh: run as $ADMIN_USER (ADMIN_USER in nori.conf), you are $(id -un)" >&2; exit 2; }
BACKUP="$HOME/.cfg-backup/$(date +%Y%m%d-%H%M%S)"
NOTE_TAG=""
drift=0
G="$REPO/generated"
S="$REPO/server"
OPT=/opt/nori
UNITS="$HOME/.config/systemd/user"

# --- the root helper must match this repo (bootstrap.sh installs it as a root-owned copy) ---
want=$(sed -n 's/^NORI_ROOT_VERSION=//p' "$S/sbin/nori-root")
have=$(sudo -n nori-root version 2>/dev/null || true)
if [[ $have != "$want" ]]; then
  echo "setup.sh: the root helper /usr/local/sbin/nori-root is ${have:+outdated (version $have, this repo needs $want)}${have:-missing or not allowed by sudo}." >&2
  echo "Re-run bootstrap once (it asks for your password with ADMIN_SUDO=limited):  sudo bash ~/nori/bootstrap.sh" >&2
  exit 2
fi

# --- learn the Tailscale name once it exists (used for preview and Plane links) ---
if [[ -z $TAILNET_HOST ]] && command -v tailscale >/dev/null 2>&1; then
  th=$(tailscale status --json 2>/dev/null | jq -r '.Self.DNSName // empty' | sed 's/\.$//') || th=""
  if [[ -n $th && $MODE != --check ]]; then
    if grep -q '^TAILNET_HOST=' "$REPO/nori.conf"; then sed -i "s|^TAILNET_HOST=.*|TAILNET_HOST=\"$th\"|" "$REPO/nori.conf"
    else printf 'TAILNET_HOST="%s"\n' "$th" >> "$REPO/nori.conf"; fi
    TAILNET_HOST="$th"; export TAILNET_HOST
    note "TAILNET_HOST=$th written to nori.conf"
  fi
fi

mkdir -p "$HOME/logs" "$HOME/.local/bin"
python3 "$REPO/scripts/render.py" "$REPO" "$G"
chmod +x "$REPO"/setup*.sh "$REPO"/bootstrap.sh "$S"/bin/* "$S"/sbin/* "$S/git/pre-commit" "$REPO/scripts/render.py"

# --- read-only shared copy for the area users ---
# What stays out (.git, *.env, progress notes, the admin's local/ except local/skills) is decided in server/sbin/nori-root.
if [[ $MODE == --check ]]; then
  sudo -n nori-root sync-opt --check "$REPO" >/dev/null || { drift=1; note "drift: $OPT out of date"; }
else
  sudo -n nori-root sync-opt "$REPO"
fi

# --- admin: scripts + git identity (the admin also pushes backups) ---
for f in "$S"/bin/*; do
  b=$(basename "$f"); nori_bin_wanted "$b" || continue
  link "$f" "$HOME/.local/bin/$b"
done
link "$S/tmux.conf"        "$HOME/.tmux.conf"
link "$G/git/gitconfig"    "$HOME/.gitconfig"
for f in "$G"/git/gitconfig-*; do [[ -f $f ]] && link "$f" "$HOME/.$(basename "$f")"; done
link "$G/git/gh-accounts"  "$HOME/.config/gh-accounts"
link "$S/git/pre-commit"   "$HOME/.git-hooks/pre-commit"
for d in "$REPO"/skills/*/ "$REPO"/local/skills/*/; do
  [[ -f $d/SKILL.md ]] && link "${d%/}" "$HOME/.claude/skills/$(basename "$d")"
done
# `ssh server attach <area>` runs without ~/.local/bin on PATH
for b in attach recall; do
  nori_bin_wanted "$b" || continue
  if [[ "$(readlink -f /usr/local/bin/$b 2>/dev/null)" != "$OPT/server/bin/$b" ]]; then
    drift=1
    if [[ $MODE == --check ]]; then note "drift: /usr/local/bin/$b"; else sudo -n nori-root link-bin "$b"; note "linked: /usr/local/bin/$b"; fi
  fi
done

# --- Ops bot (admin) ---
if is_on OPS_BOT; then
  link "$S/systemd/ops-bot.service" "$UNITS/ops-bot.service"
  if [[ $MODE != --check ]]; then
    systemctl --user daemon-reload
    if [[ -f $HOME/.ops-bot.env ]]; then
      systemctl --user enable ops-bot >/dev/null 2>&1
      systemctl --user is-active --quiet ops-bot || { systemctl --user start ops-bot; note "started ops-bot"; }
    else
      note "Ops bot: no ~/.ops-bot.env yet. Create the bot in BotFather, then run: set-token ops   (and re-run ./setup.sh)"
    fi
  fi
elif [[ $MODE != --check ]] && systemctl --user is-enabled --quiet ops-bot 2>/dev/null; then
  systemctl --user disable --now ops-bot >/dev/null 2>&1; note "stopped ops-bot (OPS_BOT=false)"
fi

# --- Claude Code version: every user runs the wanted one (server/claude-code.version, or CLAUDE_CODE_VERSION) ---
# Self-updates are off (settings partials + bootstrap's managed settings), so this is where upgrades and rollbacks happen.
# An exact version is installed where it differs; stable/latest is (re)installed on every apply, never on --check.
merge_json "$G/claude/settings.admin.partial.json" "$HOME/.claude/settings.json"
CC_WANT=$(nori_claude_version)
for u in "$ADMIN_USER" $AREAS; do
  id "$u" >/dev/null 2>&1 || continue
  if [[ $u == "$ADMIN_USER" ]]; then as_u=(env); else as_u=(sudo -n -u "$u" -H); fi
  cc="$(getent passwd "$u" | cut -d: -f6)/.local/bin/claude"
  have=$(cd / && "${as_u[@]}" "$cc" --version 2>/dev/null | awk '{print $1}') || have=""
  if [[ -z $have ]]; then
    drift=1; note "Claude Code not found for $u ($cc): run bootstrap.sh as root"; continue
  fi
  plan=$(nori_claude_plan "$have" "$CC_WANT")
  if [[ $plan == keep-newer ]]; then
    note "Claude Code for $u is $have, newer than the tested $CC_WANT: kept (setup.sh never downgrades on its own)."
    note "  Keep it: CLAUDE_CODE_VERSION=$have in nori.conf. Go back: CLAUDE_CODE_VERSION=$CC_WANT, then ./setup.sh"
    continue
  fi
  if [[ $CC_WANT =~ ^[0-9] ]]; then
    [[ $plan == ok ]] && continue
    drift=1
    if [[ $MODE == --check ]]; then note "drift: Claude Code for $u is $have, wanted $CC_WANT${plan/#downgrade/ (a downgrade, set in nori.conf)}"; continue; fi
    [[ $plan == downgrade ]] && note "Claude Code for $u: downgrading $have -> $CC_WANT (CLAUDE_CODE_VERSION in nori.conf)"
  elif [[ $MODE == --check ]]; then
    note "Claude Code for $u: $have (CLAUDE_CODE_VERSION=$CC_WANT, not pinned)"; continue
  fi
  if out=$(cd / && "${as_u[@]}" "$cc" install "$CC_WANT" 2>&1); then
    now=$(cd / && "${as_u[@]}" "$cc" --version 2>/dev/null | awk '{print $1}') || now=""
    [[ $now != "$have" ]] && { note "Claude Code for $u: $have -> $now"; CC_CHANGED=1; }
  else
    note "warning: 'claude install $CC_WANT' failed for $u: $(tail -n 3 <<<"$out")"
  fi
done
if [[ ${CC_CHANGED:-} == 1 ]]; then
  # the Ops bot re-reads versions on its next check; keep its "already alerted" memory so no old alert repeats
  python3 -I - "$HOME/.ops-bot.claude-version.json" <<'PY' || true
import json, sys
p = sys.argv[1]
try:
    d = json.load(open(p))
except (OSError, ValueError):
    sys.exit(0)
for k in ("ts", "versions", "wanted"):
    d.pop(k, None)
json.dump(d, open(p, "w"))
PY
  [[ $MODE == --restart ]] || note "Claude Code changed: run ./setup.sh --restart so the sessions use it"
fi
if ! cmp -s "$S/claude/managed-settings.json" /etc/claude-code/managed-settings.d/50-nori.json 2>/dev/null; then
  drift=1; note "drift: /etc/claude-code/managed-settings.d/50-nori.json is missing or old: run 'sudo bash bootstrap.sh' as root"
fi

# --- area users ---
GROUP_ID=$(jq -r '.chat_id // empty' "$HOME/.ops-bot.state.json" 2>/dev/null || true)
for a in $AREAS; do
  if ! id "$a" >/dev/null 2>&1; then
    drift=1; note "area user '$a' does not exist: run bootstrap.sh as root first"; continue
  fi
  h=$(area_home "$a")
  # the Plane token: compared and written by the area user itself (fed on stdin), no root needed
  if is_on PLANE && [[ -f $HOME/.plane-mcp.env ]] && ! sudo -n -u "$a" cmp -s - "$h/.plane-mcp.env" < "$HOME/.plane-mcp.env"; then
    drift=1
    if [[ $MODE == --check ]]; then note "drift: $h/.plane-mcp.env"; else
      sudo -n -u "$a" sh -c 'umask 077 && cat > "$1.tmp" && mv -f "$1.tmp" "$1"' sh "$h/.plane-mcp.env" < "$HOME/.plane-mcp.env"
      note "copied the Plane token to $a"
    fi
  fi
  (cd / && sudo -n -u "$a" -H "$OPT/setup-user.sh" "$a" "$MODE" "$GROUP_ID") || drift=1
done

# --- Docker waits for Tailscale at boot, so Plane can bind to the tailnet IP (the content lives in nori-root) ---
if is_on PLANE; then
  dropin=/etc/systemd/system/docker.service.d/10-after-tailscale.conf
  if ! sudo -n nori-root docker-dropin --check; then
    drift=1
    if [[ $MODE == --check ]]; then note "drift: $dropin"; else
      sudo -n nori-root docker-dropin && note "installed: $dropin"
    fi
  fi
fi

# --- PREFER_IPV4 (opt-in): outgoing connections try IPv4 first, for a flaky IPv6 route. Root-owned, so it goes
# through the helper. Off: only a gai.conf that is exactly ours is removed; a file you wrote is never touched. ---
if is_on PREFER_IPV4; then
  if ! sudo -n nori-root gai-conf --check; then
    drift=1
    if [[ $MODE == --check ]]; then note "drift: /etc/gai.conf (PREFER_IPV4=true)"; else
      sudo -n nori-root gai-conf && note "installed: /etc/gai.conf (prefer IPv4)"
    fi
  fi
elif sudo -n nori-root gai-conf --check; then
  drift=1
  if [[ $MODE == --check ]]; then note "drift: /etc/gai.conf is Nori's but PREFER_IPV4 is off"; else
    sudo -n nori-root gai-conf --remove && note "removed: /etc/gai.conf (PREFER_IPV4 is off)"
  fi
fi

# --- firewall sanity: the tailnet must be allowed (bootstrap.sh sets this) ---
if command -v ufw >/dev/null 2>&1 && ! sudo -n nori-root ufw-status 2>/dev/null | grep -q "tailscale0"; then
  note "warning: ufw has no rule for tailscale0 (previews/Plane would be unreachable). Run: sudo ufw allow in on tailscale0"
fi

# --- admin cron ---
cron_sync "$(cat "$G/crontab")"

# --- Plane: compose file, generated secrets (stay in ~/plane only) ---
if is_on PLANE; then
  link "$REPO/plane/docker-compose.yaml" "$HOME/plane/docker-compose.yaml"
  if [[ ! -f $HOME/plane/plane.env && $MODE != --check ]]; then
    ip=$(tailscale ip -4 2>/dev/null | head -1 || true)
    if [[ -n $ip && -n $TAILNET_HOST ]]; then
      umask 077
      r() { openssl rand -hex "${1:-16}"; }
      sed -e "s|__TAILNET_HOST__|$TAILNET_HOST|g" -e "s|__TAILSCALE_IP__|$ip|g" \
          -e "s|__PG_PASS__|$(r)|g" -e "s|__MQ_PASS__|$(r)|g" -e "s|__SECRET_KEY__|$(r 32)|g" \
          -e "s|__LIVE_KEY__|$(r 32)|g" -e "s|__MINIO_USER__|$(r 8)|g" -e "s|__MINIO_PASS__|$(r 16)|g" \
          "$REPO/plane/plane.env.example" > "$HOME/plane/plane.env"
      note "created ~/plane/plane.env with fresh secrets. Start Plane: cd ~/plane && docker compose --env-file plane.env up -d"
    else
      note "Plane: ~/plane/plane.env not created yet (Tailscale is not up). Re-run ./setup.sh after 'sudo tailscale up'."
    fi
  fi
fi

# --- passphrase for the encrypted off-site backups (Plane dumps, work snapshots) ---
if { is_on WORK_BACKUP || is_on PLANE_OFFSITE_BACKUP; } && [[ ! -f $HOME/.backup-pass && $MODE != --check ]]; then
  (umask 077; openssl rand -base64 33 > "$HOME/.backup-pass")
  note "created ~/.backup-pass (backup passphrase). COPY IT to your password manager now: without it the backups can't be read."
fi

if [[ $MODE == --check ]]; then
  [[ $drift == 0 ]] && note "in sync ✅" || { note "run ./setup.sh to apply"; exit 1; }
  exit 0
fi
[[ -d $BACKUP ]] && note "replaced files backed up in $BACKUP"
if [[ $MODE == --restart ]]; then
  is_on OPS_BOT && { systemctl --user restart ops-bot 2>/dev/null || true; }
  note "sessions restarted (the bots react again within ~20s)"
else
  if is_on OPS_BOT; then
    note "done. If rules, settings or plugins changed: ./setup.sh --restart (or /restart <area> in the Ops chat)"
  else
    note "done. If rules, settings or plugins changed: ./setup.sh --restart"
  fi
fi
