# Helpers shared by setup.sh and setup-user.sh (sourced, not executed).
# Expects the caller to set: MODE (apply|--check|--restart), BACKUP (dir for replaced files),
# NOTE_TAG (log prefix, may be empty) and to initialise drift=0.

note() { printf '%s%s\n' "${NOTE_TAG:+[$NOTE_TAG] }" "$*"; }

# link <src> <dst>: make dst a symlink to src; a pre-existing file is moved into $BACKUP first.
link() {
  local src="$1" dst="$2"
  if [[ -L $dst && "$(readlink -f "$dst")" == "$(readlink -f "$src")" ]]; then return 0; fi
  drift=1
  if [[ $MODE == --check ]]; then note "drift: $dst is not linked to $src"; return 0; fi
  mkdir -p "$(dirname "$dst")"
  if [[ -e $dst || -L $dst ]]; then mkdir -p "$BACKUP"; mv "$dst" "$BACKUP/$(echo "${dst#"$HOME"/}" | tr / _)"; fi
  ln -s "$src" "$dst"
  note "linked: $dst"
}

# merge_json <partial> <live>: deep-merge partial into live (arrays are replaced); creates live if missing.
merge_json() {
  local part="$1" live="$2" merged
  if [[ ! -f $live ]]; then
    [[ $MODE == --check ]] && { drift=1; note "drift: $live missing"; return 0; }
    mkdir -p "$(dirname "$live")"; echo '{}' > "$live"
  fi
  merged=$(jq -s '.[0] * .[1]' "$live" "$part")
  [[ "$merged" == "$(jq . "$live")" ]] && return 0
  drift=1
  if [[ $MODE == --check ]]; then note "drift: $live"; return 0; fi
  mkdir -p "$BACKUP"; cp "$live" "$BACKUP/$(basename "$live")"
  printf '%s\n' "$merged" > "$live"
  note "merged: $live"
}

# cron_sync <wanted crontab text>: manage only the block between "# >>> nori >>>" and "# <<< nori <<<" in the
# user's crontab; jobs outside it are kept. No block yet (first run): the old crontab is saved to
# $BACKUP/crontab and replaced by the block (old unmarked Nori lines would otherwise run twice).
cron_sync() {
  local want="$1" cur new b=$'# >>> nori >>>' e=$'# <<< nori <<<'
  cur=$(crontab -l 2>/dev/null || true)
  local block="$b"$'\n'"$want"$'\n'"$e"
  if grep -qxF "$b" <<<"$cur" && grep -qxF "$e" <<<"$cur"; then
    new=$(NORI_BLOCK="$block" awk -v b="$b" -v e="$e" '
      $0 == b && !skip { print ENVIRON["NORI_BLOCK"]; skip = 1; next }
      skip { if ($0 == e) skip = 0; next }
      { print }' <<<"$cur")
  else
    new="$block"
  fi
  [[ "$new" == "$cur" ]] && return 0
  drift=1
  if [[ $MODE == --check ]]; then note "drift: crontab"; return 0; fi
  if [[ -n $cur ]] && ! grep -qxF "$b" <<<"$cur"; then
    mkdir -p "$BACKUP"; printf '%s\n' "$cur" > "$BACKUP/crontab"; note "old crontab saved to $BACKUP/crontab"
  fi
  printf '%s\n' "$new" | crontab -
  note "installed: crontab"
}
