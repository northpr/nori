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
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
MODE=apply; RENDER_DIR=""
case "${1:-}" in
  ""|apply) ;;
  --check|--restart) MODE="$1" ;;
  --render-only) MODE=render; RENDER_DIR="${2:?usage: setup.sh --render-only <dir>}" ;;
  -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
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
chmod +x "$REPO"/setup*.sh "$REPO"/bootstrap.sh "$S"/bin/* "$S/git/pre-commit" "$REPO/scripts/render.py"

# --- read-only shared copy for the area users ---
# Not shared: the admin's local/ (private rules, notes), except local/skills (linked by setup-user.sh; local rules are
# already rendered into generated/), plus .git, progress notes and *.env. nori.conf and profile/ stay: setup-user.sh reads them.
SHARE_FILTER=(--exclude .git --exclude SETUP-PROGRESS.md --exclude '*.env'
              --include /local/skills/ --include '/local/skills/**' --exclude '/local/*')
if [[ $MODE == --check ]]; then
  [[ -z "$(sudo rsync -rcni --delete --delete-excluded "${SHARE_FILTER[@]}" "$REPO/" "$OPT/" 2>/dev/null)" ]] || { drift=1; note "drift: $OPT out of date"; }
else
  sudo mkdir -p "$OPT"
  sudo rsync -a --delete --delete-excluded "${SHARE_FILTER[@]}" "$REPO/" "$OPT/"
  sudo chown -R root:root "$OPT" && sudo chmod -R a+rX,go-w "$OPT"
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
    if [[ $MODE == --check ]]; then note "drift: /usr/local/bin/$b"; else sudo ln -sfn "$OPT/server/bin/$b" "/usr/local/bin/$b"; note "linked: /usr/local/bin/$b"; fi
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

# --- area users ---
GROUP_ID=$(jq -r '.chat_id // empty' "$HOME/.ops-bot.state.json" 2>/dev/null || true)
for a in $AREAS; do
  if ! id "$a" >/dev/null 2>&1; then
    drift=1; note "area user '$a' does not exist: run bootstrap.sh as root first"; continue
  fi
  h=$(area_home "$a")
  if is_on PLANE && [[ -f $HOME/.plane-mcp.env ]] && ! sudo cmp -s "$HOME/.plane-mcp.env" "$h/.plane-mcp.env"; then
    drift=1
    if [[ $MODE == --check ]]; then note "drift: $h/.plane-mcp.env"; else
      sudo install -o "$a" -g "$a" -m 600 "$HOME/.plane-mcp.env" "$h/.plane-mcp.env"; note "copied the Plane token to $a"
    fi
  fi
  (cd / && sudo -n -u "$a" -H "$OPT/setup-user.sh" "$a" "$MODE" "$GROUP_ID") || drift=1
done

# --- Docker waits for Tailscale at boot, so Plane can bind to the tailnet IP (root-owned: installed as a copy) ---
if is_on PLANE; then
  dropin=/etc/systemd/system/docker.service.d/10-after-tailscale.conf
  if ! cmp -s "$S/systemd/docker-after-tailscale.conf" "$dropin" 2>/dev/null; then
    drift=1
    if [[ $MODE == --check ]]; then note "drift: $dropin"; else
      sudo install -D -m 644 "$S/systemd/docker-after-tailscale.conf" "$dropin" && sudo systemctl daemon-reload
      note "installed: $dropin"
    fi
  fi
fi

# --- firewall sanity: the tailnet must be allowed (bootstrap.sh sets this) ---
if command -v ufw >/dev/null 2>&1 && ! sudo ufw status 2>/dev/null | grep -q "tailscale0"; then
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
  if is_on PLANE_OFFSITE_BACKUP && [[ ! -f $HOME/.backup-pass && $MODE != --check ]]; then
    (umask 077; openssl rand -base64 33 > "$HOME/.backup-pass")
    note "created ~/.backup-pass (backup passphrase). COPY IT to your password manager now: without it the backups can't be read."
  fi
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
