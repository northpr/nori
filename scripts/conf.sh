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
  starter) _nori_preset="OPS_BOT=false OPS_ASK=false DIGEST=false HANDOFF=true POOL_SESSIONS=false POOL_CAPACITY=4
                         PLANE=false PREVIEWS=false RECALL=false BROWSER=false" ;;
  full)    _nori_preset="OPS_BOT=true OPS_ASK=true DIGEST=true HANDOFF=true POOL_SESSIONS=true POOL_CAPACITY=8
                         PLANE=true PREVIEWS=true RECALL=true BROWSER=true" ;;
  *)       # recommended (an unknown value is reported by render.py)
           _nori_preset="OPS_BOT=true OPS_ASK=true DIGEST=true HANDOFF=true POOL_SESSIONS=true POOL_CAPACITY=4
                         PLANE=false PREVIEWS=true RECALL=true BROWSER=true" ;;
esac
for _kv in $_nori_preset; do _n=${_kv%%=*}; [[ -n ${!_n:-} ]] || printf -v "$_n" '%s' "${_kv#*=}"; done
# full: off-site Plane backups once there is Plane and a repo to push to (render.py says so otherwise)
if [[ -z ${PLANE_OFFSITE_BACKUP:-} ]]; then
  if [[ $PRESET == full && $PLANE == true && -n ${PLANE_BACKUP_REPO:-} ]]; then PLANE_OFFSITE_BACKUP=true; else PLANE_OFFSITE_BACKUP=false; fi
fi
: "${OWNER_NAME:=friend}" "${SERVER_NAME:=nori-server}" "${TIMEZONE:=UTC}" "${LANGUAGES:=English}"
: "${ADMIN_USER:=admin}" "${CHAT:=telegram}" "${CHAT_ALLOWED_IDS:=}" "${AREAS:=main}"
: "${GITHUB_ACCOUNTS:=}" "${OPS_GROUP_NAME:=Nori HQ}"
: "${HANDOFF_TIME:=03:45}" "${DIGEST_TIME:=08:00}" "${DIGEST_LANGUAGE:=English}"
: "${REMOTE_CONTROL:=true}" "${AUTO_UPDATES:=true}" "${AUTO_REBOOT_TIME:=04:30}" "${EXTRA_ASK_PERMISSIONS:=}"
: "${PLANE_WORKSPACE:=main}" "${PLANE_BACKUP_REPO:=}" "${PREVIEW_PORT_START:=8100}" "${TAILNET_HOST:=}"
# full: GitHub comments/reviews ask first in every area after the first one (e.g. "work")
if [[ $PRESET == full ]]; then
  read -r _first _ <<<"$AREAS"
  for _a in $AREAS; do
    [[ $_a == "$_first" ]] && continue
    _n="AREA_${_a}_ASK_BEFORE_GITHUB_COMMENTS"; [[ -n ${!_n:-} ]] || printf -v "$_n" true
  done
fi
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
    preview)                           is_on PREVIEWS ;;
    recall|recall-index)               is_on RECALL ;;
    browser-mcp)                       is_on BROWSER ;;
    morning-summary)                   is_on DIGEST ;;
    nightly-handoff)                   is_on HANDOFF ;;
    claude-pool)                       is_on POOL_SESSIONS ;;
    *)                                 return 0 ;;
  esac
}
