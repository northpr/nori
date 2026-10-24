#!/bin/bash
# Laptop (macOS or Linux): load the shared Nori rules and skills in every Claude Code project.
# Only adds: one import line at the end of ~/.claude/CLAUDE.md (backed up first) and skill links
# whose names are free. Never touches settings.json or existing skills. Safe to rerun.
#   ./laptop/setup-laptop.sh --dry-run   show what it would do, change nothing
#   ./laptop/setup-laptop.sh             do it
# Undo: delete the import line from ~/.claude/CLAUDE.md and the links it lists.
# Plain bash 3.2 (macOS default): no readlink -f, no associative arrays.
set -euo pipefail
R="$(cd "$(dirname "$0")/.." && pwd)"
C="$HOME/.claude"
DRY=0
case "${1:-}" in
  --dry-run) DRY=1 ;;
  "") ;;
  *) echo "usage: $0 [--dry-run]"; exit 2 ;;
esac
say() { if ((DRY)); then echo "would: $*"; else echo "$*"; fi; }

# 1. one import line in ~/.claude/CLAUDE.md
case $R in "$HOME"/*) P="~${R#"$HOME"}" ;; *) P="$R" ;; esac
LINE="@$P/laptop/CLAUDE.md"
MD="$C/CLAUDE.md"
if [[ -f $MD ]] && grep -qxF "$LINE" "$MD"; then
  echo "ok: $MD already imports laptop/CLAUDE.md"
else
  say "add to $MD: $LINE"
  if ((!DRY)); then
    mkdir -p "$C"
    if [[ -f $MD ]]; then
      mkdir -p "$C/nori-backup"
      cp -p "$MD" "$C/nori-backup/CLAUDE.md.$(date +%Y%m%d-%H%M%S)"
      echo "backup: $C/nori-backup/"
      [[ -z $(tail -c1 "$MD") ]] || echo >> "$MD"
    fi
    printf '\n# Nori rules (shared with the server sessions)\n%s\n' "$LINE" >> "$MD"
  fi
fi

# 2. shared skills, only where the name is free
for d in "$R"/skills/*/ "$R"/local/skills/*/; do
  [[ -f $d/SKILL.md ]] || continue
  src="${d%/}"; name="$(basename "$src")"; dst="$C/skills/$name"
  if [[ -L $dst && "$(readlink "$dst")" == "$src" ]]; then
    echo "ok: skill $name"
  elif [[ -e $dst || -L $dst ]]; then
    echo "skip: skill $name (you already have one with that name; left as is)"
  else
    say "link skill $name"
    if ((!DRY)); then mkdir -p "$C/skills"; ln -s "$src" "$dst"; fi
  fi
done

((DRY)) && echo "dry run: nothing changed" || echo "done. New Claude Code sessions pick it up (check with /memory)."
