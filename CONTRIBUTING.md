# Contributing to Nori 🍙

Nori is shared so everyone who uses it can make it better. Found a bug in a script, a step that confused you, or support for Discord/Slack? Send a change.

## How
1. Make a branch: `git checkout -b <short-topic>` (e.g. `fix-bootstrap-arm`, `discord-chat`).
2. Change things, then check them:
   - `bash -n` on any shell script you touched, `python3 -m py_compile` on Python
   - `tests/run.sh` runs all checks (stdlib only, no installs): syntax of every script, rendering of each preset, no owner data in the repo, ops-bot helpers. CI runs it on every push and PR.
   - `./setup.sh --render-only /tmp/nori-check` with your `nori.conf` still renders
3. Open a pull request into `main` and fill in the template. The maintainer reviews and merges. Don't push to `main` directly.

## Rules
- **No personal data or secrets**: no tokens, IPs, chat ids, emails, tailnet names or company names. Your own values belong in `nori.conf`, `profile/USER.md` and `local/`, which are all gitignored.
- New features are **flags**. Decide which presets turn them on (`PRESET` defaults live in `scripts/conf.sh`; `starter` stays minimal) and update the preset table in `docs/setup-guide.md`. A flag the Python helpers read also goes into `nori.resolved.conf` in `scripts/render.py`.
- If you change the setup flow, update `docs/setup-guide.md` and the checklist in `CLAUDE.md` too, so Nori's guide stays right.
- New chat platform: follow `docs/adding-a-chat-platform.md`.
- Write for someone new to servers: short, clear steps.
