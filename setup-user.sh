#!/bin/bash
# Per-user part of the setup, for an area user that runs one Claude session.
# Called by setup.sh (as the admin) via:  sudo -u <area> -H /opt/nori/setup-user.sh <area> <mode> [ops chat id]
# It links from the read-only shared copy /opt/nori (area users can't read the admin's home).
set -euo pipefail
AREA="${1:?usage: setup-user.sh <area> [apply|--check|--restart] [ops chat id]}"; MODE="${2:-apply}"; GROUP_ID="${3:-}"
export NORI_ROOT=/opt/nori
R=$NORI_ROOT
S="$R/server"
G="$R/generated"
BACKUP="$HOME/.cfg-backup/$(date +%Y%m%d-%H%M%S)"
NOTE_TAG="$AREA"
drift=0
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
[[ $(id -un) == "$AREA" ]] || { echo "setup-user.sh: run as user $AREA"; exit 2; }
# shellcheck disable=SC1091
. "$R/scripts/conf.sh"
# shellcheck disable=SC1091
. "$R/scripts/lib.sh"
# shellcheck disable=SC1090
. "$R/chat/$CHAT/platform.conf"

# shared config (read-only) at ~/nori: profile import, skills, docs
link "$R" "$HOME/nori"
for f in "$S"/bin/*; do
  b=$(basename "$f"); nori_bin_wanted "$b" || continue
  case "$b" in ops-bot|morning-summary|nightly-handoff|plane-backup|plane-offsite|work-offsite|set-token) continue ;; esac  # admin-only
  link "$f" "$HOME/.local/bin/$b"
done
for d in "$R"/skills/*/ "$R"/local/skills/*/; do
  [[ -f $d/SKILL.md ]] && link "${d%/}" "$HOME/.claude/skills/$(basename "$d")"
done

# rules: shared + this area's
link "$G/CLAUDE.md"                "$HOME/projects/CLAUDE.md"
link "$G/areas/$AREA/CLAUDE.md"    "$HOME/projects/$AREA/CLAUDE.md"
link "$G/areas/$AREA/settings.json" "$HOME/projects/$AREA/.claude/settings.json"
link "$G/areas/$AREA/mcp.json"     "$HOME/projects/$AREA/.mcp.json"
link "$S/tmux.conf"                "$HOME/.tmux.conf"

# git identities (identity follows the repo owner; this user has its own GitHub login via `gh auth login`)
link "$G/git/gitconfig"   "$HOME/.gitconfig"
for f in "$G"/git/gitconfig-*; do [[ -f $f ]] && link "$f" "$HOME/.$(basename "$f")"; done
link "$G/git/gh-accounts" "$HOME/.config/gh-accounts"
link "$S/git/pre-commit"  "$HOME/.git-hooks/pre-commit"

# Claude settings and chat access list (merged; the tools write these too)
merge_json "$G/claude/settings.partial.json" "$HOME/.claude/settings.json"
TDIR="$HOME/.claude/channels/${CHAT_STATE_PREFIX}${AREA}"
if [[ -f $TDIR/$CHAT_TOKEN_FILE ]]; then
  part="$G/chat/access.$AREA.json"
  if [[ $CHAT == telegram && $GROUP_ID == -* ]]; then   # the Ops chat is a group: answer there when prefixed
    part=$(mktemp)
    jq --arg g "$GROUP_ID" '. + {groups: {($g): {requireMention: true, allowFrom: .allowFrom}}}' "$G/chat/access.$AREA.json" > "$part"
  fi
  merge_json "$part" "$TDIR/access.json"
else
  note "no chat bot token yet (as the admin run: set-token $AREA), so no session is started"
fi

# cron: own recall index
if is_on RECALL; then
  want_cron=$'PATH='"$HOME"'/.local/bin:/usr/local/bin:/usr/bin:/bin\n*/15 * * * * /usr/bin/python3 -I '"$HOME"'/.local/bin/recall-index >> '"$HOME"'/recall/index.log 2>&1'
  [[ $MODE == --check ]] || mkdir -p "$HOME/recall"
  cron_sync "$want_cron"
fi

# the 24/7 session
link "$G/systemd/claude@.service" "$HOME/.config/systemd/user/claude@.service"
if [[ $MODE != --check ]]; then
  systemctl --user daemon-reload
  if [[ -f $TDIR/$CHAT_TOKEN_FILE ]]; then
    systemctl --user enable "claude@$AREA" >/dev/null 2>&1
    if [[ $MODE == --restart ]]; then systemctl --user restart "claude@$AREA"; note "restarted claude@$AREA"
    elif ! systemctl --user is-active --quiet "claude@$AREA"; then systemctl --user start "claude@$AREA"; note "started claude@$AREA"; fi
  fi
fi

# the session pool (Claude app / claude.ai/code); not restarted by --restart, that would end open sessions
if is_on POOL_SESSIONS; then
  link "$G/systemd/claude-pool@.service" "$HOME/.config/systemd/user/claude-pool@.service"
  if [[ $MODE != --check ]]; then
    systemctl --user daemon-reload
    systemctl --user enable "claude-pool@$AREA" >/dev/null 2>&1
    systemctl --user is-active --quiet "claude-pool@$AREA" || { systemctl --user start "claude-pool@$AREA"; note "started claude-pool@$AREA (the Claude app needs a browser login for $AREA; after Quick setup see docs/setup-guide.md, 'Claude app after Quick setup'; otherwise run 'claude remote-control' once as $AREA and answer y)"; }
  fi
elif [[ $MODE != --check ]] && systemctl --user is-enabled --quiet "claude-pool@$AREA" 2>/dev/null; then
  systemctl --user disable --now "claude-pool@$AREA" >/dev/null 2>&1; note "stopped claude-pool@$AREA (POOL_SESSIONS=false)"
fi
[[ -d $BACKUP ]] && note "backups in $BACKUP"
[[ $MODE == --check && $drift == 1 ]] && exit 1
exit 0
