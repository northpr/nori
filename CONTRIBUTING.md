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
- **Claude Code version** (maintainer): `server/claude-code.version` is the version every server installs by default. To bump it, pick a release that has been out for about two weeks (`npm view @anthropic-ai/claude-code time --json`), run `python3 tests/claude_cli_check.py <that claude>` (e.g. after `npm i -g @anthropic-ai/claude-code@<version>`), try it on a server (`CLAUDE_CODE_VERSION=<version>`, `./setup.sh`, `./setup.sh --restart`, check `/progress` and the pool), then change the file in its own PR; the `claude-pinned` CI job must pass. The weekly `claude-latest` job runs the same check against `@latest` and warns early when a new release drops a flag Nori uses. A new flag or subcommand in Nori goes into `tests/claude_cli_check.py` too.
- Write for someone new to servers: short, clear steps.

## Layout
```
CLAUDE.md             Nori the setup guide (runs on your laptop)
nori.conf.example     the one config file; copy to nori.conf (gitignored, no secrets)
bootstrap.sh          once, as root, on a fresh Ubuntu 24.04+ server
setup.sh              apply the config (--check, --restart, --render-only DIR)
setup-user.sh         per-area-user part, called by setup.sh
scripts/              config loader, shared helpers, template renderer
server/               what lands on the server
  rules/              the rules the always-on session follows (core + optional sections)
  areas/              per-area CLAUDE.md template
  bin/                ops-bot, morning-summary, nightly-handoff, claude-session, attach, ...
  git/ systemd/ ...
chat/telegram/        platform bits: BotFather notes, access template, rules
chat/discord|slack/   planned, with what is needed
plane/                docker-compose + env template (with PLANE=true)
profile/USER.md.example   about you, read by every session
skills/               shared skills
local/                your private additions (gitignored)
docs/                 setup-guide, tech-stack, recommendations, troubleshooting, adding-a-chat-platform
```
