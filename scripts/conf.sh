# Sourced by setup scripts and helper scripts: loads nori.conf and applies defaults.
# Usage:  . "$HOME/nori/scripts/conf.sh"      (NORI_ROOT / NORI_CONF override the location)
# Not meant to be executed. Keep the defaults here the only place they are defined.
NORI_ROOT="${NORI_ROOT:-$HOME/nori}"
NORI_CONF="${NORI_CONF:-$NORI_ROOT/nori.conf}"
if [[ ! -f $NORI_CONF ]]; then
  echo "nori: config not found: $NORI_CONF (copy nori.conf.example to nori.conf and edit it)" >&2
  return 1 2>/dev/null || exit 1
fi
set -a
# shellcheck disable=SC1090
. "$NORI_CONF"
# PRESET picks the feature defaults (starter | recommended | full); any flag set in nori.conf wins.
: "${PRESET:=recommended}"
case "$PRESET" in
  starter) _nori_preset="OPS_BOT=false OPS_ASK=false PERM_CARDS=false DIGEST=false HANDOFF=true POOL_SESSIONS=false POOL_CAPACITY=4
                         PLANE=false PREVIEWS=false RECALL=false BROWSER=false" ;;
  full)    _nori_preset="OPS_BOT=true OPS_ASK=true PERM_CARDS=true DIGEST=true HANDOFF=true POOL_SESSIONS=true POOL_CAPACITY=8
                         PLANE=true PREVIEWS=true RECALL=true BROWSER=true" ;;
  *)       # recommended (an unknown value is reported by render.py)
           _nori_preset="OPS_BOT=true OPS_ASK=true PERM_CARDS=true DIGEST=true HANDOFF=true POOL_SESSIONS=true POOL_CAPACITY=4
                         PLANE=false PREVIEWS=true RECALL=true BROWSER=true" ;;
esac
for _kv in $_nori_preset; do _n=${_kv%%=*}; [[ -n ${!_n:-} ]] || printf -v "$_n" '%s' "${_kv#*=}"; done
# one private backup repo for everything; PLANE_BACKUP_REPO is its older name and still works
: "${BACKUP_REPO:=${PLANE_BACKUP_REPO:-}}"
# full: off-site Plane backups once there is Plane and a repo to push to (render.py says so otherwise)
if [[ -z ${PLANE_OFFSITE_BACKUP:-} ]]; then
  if [[ $PRESET == full && $PLANE == true && -n $BACKUP_REPO ]]; then PLANE_OFFSITE_BACKUP=true; else PLANE_OFFSITE_BACKUP=false; fi
fi
# nightly encrypted backup of unpushed work: opt-in in every preset (it uploads uncommitted files, which
# may be company code); per area AREA_<a>_WORK_BACKUP=false leaves that area out (default true)
: "${WORK_BACKUP:=false}"
: "${OWNER_NAME:=friend}" "${SERVER_NAME:=nori-server}" "${TIMEZONE:=UTC}" "${LANGUAGES:=English}"
: "${ADMIN_USER:=admin}" "${CHAT:=telegram}" "${CHAT_ALLOWED_IDS:=}" "${AREAS:=main}"
: "${GITHUB_ACCOUNTS:=}" "${OPS_GROUP_NAME:=Nori HQ}"
: "${HANDOFF_TIME:=03:45}" "${DIGEST_TIME:=08:00}" "${DIGEST_LANGUAGE:=English}"
: "${REMOTE_CONTROL:=true}" "${AUTO_UPDATES:=true}" "${AUTO_REBOOT_TIME:=04:30}" "${EXTRA_ASK_PERMISSIONS:=}"
: "${PLANE_WORKSPACE:=main}" "${PLANE_BACKUP_REPO:=}" "${PREVIEW_PORT_START:=8100}" "${TAILNET_HOST:=}"
# not preset-dependent: scoped passwordless sudo for the admin (bootstrap.sh, docs/setup-guide.md step 3)
: "${ADMIN_SUDO:=limited}"
# opt-in in every preset: prefer IPv4 for outgoing connections (/etc/gai.conf), for a flaky IPv6 route (docs/troubleshooting.md)
: "${PREFER_IPV4:=false}"
# full: GitHub comments/reviews ask first in every area after the first one (e.g. "work")
if [[ $PRESET == full ]]; then
  read -r _first _ <<<"$AREAS"
  for _a in $AREAS; do
    [[ $_a == "$_first" ]] && continue
    _n="AREA_${_a}_ASK_BEFORE_GITHUB_COMMENTS"; [[ -n ${!_n:-} ]] || printf -v "$_n" true
  done
fi
# work backup per area: on unless AREA_<a>_WORK_BACKUP=false (only matters with WORK_BACKUP=true)
for _a in $AREAS; do
  [[ $_a =~ ^[a-zA-Z0-9]+$ ]] || continue   # a bad area name is reported by render.py
  _n="AREA_${_a}_WORK_BACKUP"; [[ -n ${!_n:-} ]] || printf -v "$_n" true
done
# Claude Code version to install: empty = the tested one in server/claude-code.version; or 2.1.x, stable, latest
: "${CLAUDE_CODE_VERSION:=}"
unset _kv _n _a _first _nori_preset
NORI_CONF_LOADED=1
set +a

# is_on PLANE  -> true when the flag is exactly "true"
is_on() { [[ "${!1:-false}" == true ]]; }
# area_var main PREFIX -> value of AREA_main_PREFIX
area_var() { local n="AREA_${1}_${2}"; printf '%s' "${!n:-}"; }
# area_home main -> that Linux user's home directory
area_home() { getent passwd "$1" | cut -d: -f6; }
# nori_bin_wanted <script name> -> should this helper script be installed with the current flags?
nori_bin_wanted() {
  case "$1" in
    plane-mcp)                         is_on PLANE ;;
    plane-backup)                      is_on PLANE ;;
    plane-offsite)                     is_on PLANE && is_on PLANE_OFFSITE_BACKUP ;;
    work-backup|work-offsite)          is_on WORK_BACKUP ;;
    preview)                           is_on PREVIEWS ;;
    recall|recall-index)               is_on RECALL ;;
    browser-mcp)                       is_on BROWSER ;;
    morning-summary)                   is_on DIGEST ;;
    nightly-handoff)                   is_on HANDOFF ;;
    claude-pool)                       is_on POOL_SESSIONS ;;
    ask-owner|usage-report|usage-snapshot) is_on OPS_BOT ;;   # the Ops bot reads their files
    *)                                 return 0 ;;
  esac
}
# nori_claude_version -> the Claude Code version every user should run (CLAUDE_CODE_VERSION, else the repo's tested one)
nori_claude_version() {
  if [[ -n ${CLAUDE_CODE_VERSION:-} ]]; then printf '%s\n' "$CLAUDE_CODE_VERSION"
  else tr -d '[:space:]' < "$NORI_ROOT/server/claude-code.version"; echo; fi
}
# nori_claude_plan <installed> <wanted> -> ok | install | downgrade | keep-newer
# Never a silent downgrade: an installed version newer than the repo's tested one is kept; going back down only
# happens when CLAUDE_CODE_VERSION in nori.conf asks for it (a deliberate rollback). stable/latest: always install.
nori_claude_plan() {
  local have=$1 want=$2
  [[ $want =~ ^[0-9] ]] || { echo install; return; }
  [[ $have == "$want" ]] && { echo ok; return; }
  if [[ -n $have && $(printf '%s\n%s\n' "$have" "$want" | sort -V | tail -n 1) == "$have" ]]; then
    if [[ -n ${CLAUDE_CODE_VERSION:-} ]]; then echo downgrade; else echo keep-newer; fi
  else
    echo install
  fi
}
