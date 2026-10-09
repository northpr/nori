<p align="center">
  <img src="assets/readme/hero.svg" alt="Nori: your own Claude Code, awake 24/7 on a small server, and you drive it from your phone" width="100%">
</p>

# Nori 🍙

**Your own Claude Code, running 24/7 on a ~€6/month server, that you talk to from Telegram.**

Send "fix the export bug" from the bus. Claude works on your server while your laptop is closed, shows progress, asks before it pushes (one tap: ✅ Allow), opens the PR and sends you a preview link. Every night it writes a handoff note and starts fresh. Your repos, your Claude subscription, your server.

Nori is a template plus a friendly setup guide. Clone it, open it on your laptop, run `claude`, and say "hi Nori". Nori (the guide in `CLAUDE.md`) walks you through buying a small server, connecting to it, creating your chat bots and switching everything on, one step at a time, and writes down its progress so you can stop and resume.

```
git clone -b develop https://github.com/northpr/nori && cd nori && claude
```
then type: `hi Nori`

## How it fits together

<p align="center">
  <img src="assets/readme/architecture.svg" alt="Your phone talks to your Telegram bots; each bot drives its own always-on Claude session on your server; the Ops bot handles status, alerts and buttons; the Claude app opens extra sessions; Tailscale keeps previews and tickets private; GitHub gets branches and PRs, and pushes ask you first" width="100%">
</p>

- **One `nori.conf`** describes everything; `setup.sh` turns it into the server setup and can tell you when the box drifted (`./setup.sh --check`).
- **Areas** (e.g. `personal` and `work`) are separate Linux users with their own Claude session, bot, folders and rules.
- **The Ops bot** is a small script, not Claude: it keeps answering when a session is busy or restarting.

## 📱 Run it from your phone

<table>
<tr>
<td width="320" valign="top"><img src="assets/readme/phone.svg" alt="A Telegram chat: you ask the work bot to fix the CSV export, it reacts 👀, reports progress, asks to push with Allow and Deny buttons, then sends the PR and a preview link" width="300"></td>
<td valign="top">

Most days you never open a laptop. What makes that work (🧪 = on the `develop` branch now, coming to `main` with the next release):

- **Talk normally.** In a group with several bots, start with the area's prefix (`p: …`, `w: …`). 👀 means it got your message.
- **Approve with a tap.** Pushes, merges and other risky commands ask you in Telegram first; 🧪 the Ops bot shows them as a 🔐 card with **Allow / Deny**.
- 🧪 **Answer with a tap.** When Claude asks "A or B?", you get buttons too.
- 🧪 **Never wonder if it died.** Long tasks send "⏳ still on it · 12 min · running tests".
- **Check in fast.** `/status`, `/progress`, and 🧪 `/usage` (how much of your plan you've used), `/recall <words>` (past chats and decisions).
- **Tickets from the chat** (with Plane): `/ticket <what you need>`, `/board`, `/peek CDP-4`, and 🧪 **▶️ Do it** to start one.
- **Keep it fast.** `/clear` or `/compact` from the chat when you switch topics, and a fresh start every night.
- **See the result.** Previews open on your phone over Tailscale; nothing is public.
- **More hands.** Start extra sessions from the Claude app (Remote Control) next to the chat one.

**Best phone-only setup:** the ⭐ recommended preset (or 🚀 full for tickets), Tailscale and Telegram on your phone, the Ops bot's 🔐 cards on (🧪), and Telegram two-step verification switched on, because your Telegram account is now the remote control.

</td>
</tr>
</table>

## How configurable is it?
Start small and switch things on later; nothing is lost.
- **Presets:** `PRESET=starter|recommended|full` (table below), and every single flag can still be overridden in `nori.conf`.
- **Your rules and skills:** drop extra rules into `local/rules/` and skills into `local/skills/`; they're yours and gitignored.
- **Your profile:** `profile/USER.md` tells every session who you are and how you like to work.
- **Areas, accounts and safety:** as many areas as you need, per-area GitHub identities, which commands ask first (`EXTRA_ASK_PERMISSIONS`), `ADMIN_SUDO`, and whether GitHub comments and reviews ask first in an area.
- 🧪 **The Claude Code version** is pinned (`CLAUDE_CODE_VERSION`), so an update never surprises you.

## Pick a preset
One line in `nori.conf`, `PRESET=starter|recommended|full`, picks the feature set; every single flag can still be overridden. Full table: [docs/setup-guide.md#presets](docs/setup-guide.md#presets).

| | 🌱 starter | ⭐ recommended (default) | 🚀 full |
|---|---|---|---|
| Always-on Claude session + Telegram chat bot | ✅ | ✅ | ✅ |
| Nightly handoff + fresh restart, git identity guard, push/merge approvals | ✅ | ✅ | ✅ |
| **Ops bot**: `/status` `/progress` `/restart` `/ask`, alerts, daily digest | | ✅ | ✅ |
| Session pool (extra sessions from the Claude app) | | ✅ (4) | ✅ (8) |
| Browser screenshots, phone previews, recall | | ✅ | ✅ |
| Encrypted nightly backup of unpushed work (opt-in: `WORK_BACKUP=true` + `BACKUP_REPO`) | ✅ | ✅ | ✅ |
| **Plane** tickets, `/board` `/peek`, ticket intake, weekly review, off-site backups | | | ✅ |
| Bots to create | 1 | 2 | 2 + 1 per extra area |
| Server | 4 GB | 4 GB | 8 GB |

## What you get
- One always-on Claude session per area on your server (systemd + tmux, also reachable from the Claude app via Remote Control).
- A **Telegram chat bot** to talk to it: short phone-friendly replies, progress updates, 🔐 permission requests in your DM.
- An **Ops bot** (a small script, not Claude; optional): `/status`, `/progress`, `/restart`, `/apply`, alerts when something dies or memory runs low, a daily digest, and `/ask <question>`. Without it you run just one Claude + one chat bot, and the digest comes through your chat bot.
  - The Ops bot reacts with 👀 to every command from you, shows a 🔐 permission card with just the command (Allow / Deny buttons) and builds slow answers like `/board` in the background, so it stays responsive.
  - Ops bot extras: `/usage` (token use per area and plan-limit %), `/recall <words>` (search past chats, handoffs and tickets), "still on it" pings while a long task runs, tap-to-answer buttons (Claude's A/B questions become buttons via `ask-owner`), an alert if the chat bot's connection to Telegram goes quiet, and with Plane a ▶️ **Do it** button on ticket cards. `/allow <id> <name> <area>` lets a teammate work in one area, and `/workgroup <area>` binds a group chat to an area.
- A **session pool** per area: start several extra Claude sessions from the Claude app or claude.ai/code next to the chat session.
- **Nightly handoff + fresh restart:** each night the session writes a handoff note, then restarts with a clean context and picks up from the note.
- **Git identity per repo owner** (personal vs company accounts) with a pre-commit guard, a `gh` wrapper, and ask-first rules for pushes and merges.
- **Encrypted nightly backups** of what isn't on GitHub yet (unpushed commits, uncommitted changes, handoff notes, skills) to your private repo.
- **Plane** tickets (self-hosted, Docker), encrypted off-site backups, **previews** on your phone through Tailscale, **recall** over past chats, a headless **browser**.
- **More areas**, e.g. `personal` and `work`, each its own Linux user, session and bot, unable to read each other's files. Per area you can make GitHub reviews and comments ask first.
- `cc-slash` (send `/clear`, `/compact`, `/model ...` from the chat), `attach` (look into the session).

Other chat platforms (Discord, Slack) are planned, not supported yet. The Ops bot is Telegram-only for now.

## What it costs
- **Your own Claude subscription** (Pro or Max). It must be **your own account**: never share a login. Heavy 24/7 use needs a plan with enough headroom.
- **A small VPS:** e.g. Hetzner **CAX11** (Arm, 2 vCPU, 4 GB, about €6/month in the EU in 2026) or **CAX21** (4 vCPU, 8 GB) for Plane. Prices changed in 2026; check hetzner.com/cloud.
- Tailscale, Telegram and GitHub are free. Details and gotchas: [docs/tech-stack.md](docs/tech-stack.md).

## Docs
- [docs/setup-guide.md](docs/setup-guide.md): the step-by-step tutorial, with checkpoints and "if it fails" boxes
- [docs/tech-stack.md](docs/tech-stack.md): every piece explained (what, why, cost, alternatives, gotchas)
- [docs/recommendations.md](docs/recommendations.md): "to get a setup like ours", a checklist of settings and habits
- [docs/troubleshooting.md](docs/troubleshooting.md): when something doesn't work

## Quickstart
1. You need [Claude Code](https://docs.claude.com/en/docs/claude-code). Then run `git clone -b develop https://github.com/northpr/nori && cd nori && claude` (Nori does the rest in chat; if you have a question at any point, just ask Nori in that Claude window). On a Mac, the first `git` may show a popup asking to install Apple's developer tools: click Install (about 5 min, free), then run the command again.
2. Say **hi Nori**. Nori asks which preset you want (starter, recommended or full), a few more questions, writes `nori.conf` for you, and guides you through the rest.
3. Prefer doing it yourself? Follow `docs/setup-guide.md`.

Fastest, after writing nori.conf (Step 0): `./nori up` (beta, being tested; Quick setup in docs/setup-guide.md). If something stops, the step-by-step guide always works.

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

## Updating later
`git pull` on your laptop (your `nori.conf`, `profile/USER.md`, `local/` and `SETUP-PROGRESS.md` are gitignored), copy the repo to the server (`rsync -a --exclude .git --exclude generated ./ <server>:nori/`), then on the server `cd ~/nori && ./setup.sh` (add `--restart` if rules or settings changed). Claude Code itself is pinned to a tested version and doesn't update itself; upgrade it on purpose with `CLAUDE_CODE_VERSION` in `nori.conf`. Details in `docs/setup-guide.md`.

## 🔒 Security
**Found a security problem?** Please report it privately: this repo's **Security** tab → **Report a vulnerability** ([SECURITY.md](SECURITY.md)). Don't open a public issue, and never paste real tokens, keys or passwords anywhere.

In short:
- **Your keys stay yours.** `./nori up` asks for each key with hidden typing, sends it only to your own server (over SSH, never on a command line), and saves none of them on your laptop. The Hetzner token is used once and forgotten. Keys never go into git, `nori.conf` or a chat with Claude.
- **Your server is locked down.** Firewall closed except SSH (key-only, no root login) and the private Tailscale network. The admin has only limited passwordless sudo; each Claude session runs as its own user with no sudo.
- **Risky actions ask you first.** `git push`, PR merges and anything you add to `EXTRA_ASK_PERMISSIONS` always need your 🔐 approval, even in auto mode.
- **Protect your Telegram account** with two-step verification: it's the remote control for your server.
- **This repo:** GitHub secret scanning and push protection are on, `main` and `develop` only change through reviewed pull requests with passing tests, and the tests block personal data from being committed.

### Safety model in detail
Who can do what:
- **Your Telegram account** is the remote control. Whoever gets into it can tell the area sessions to run code as the area users, approve their 🔐 pushes and merges, and use the Ops bot (`/apply` re-runs `setup.sh` as the admin, `/restart <area>`). **Turn on Telegram's two-step verification** (Settings → Privacy and Security → Two-Step Verification, a cloud password).
- **The admin account** (`ADMIN_USER`, your SSH login) runs `setup.sh`, cron and the Ops bot. With `ADMIN_SUDO=limited` (the default) it may act as the area users and run the small root helper `nori-root` without a password; anything else as root asks for the admin's password. So a stolen Telegram account or a bug in the Ops bot doesn't mean passwordless root. `ADMIN_SUDO=full` is passwordless root for everything. `limited` needs classic sudo; on Ubuntu 26.04 (`sudo-rs`) bootstrap keeps `full` until it's tested there. With `PLANE=true` the admin is also in the `docker` group, which is as good as root; `limited` doesn't change that.
- **Area users** run the Claude sessions: no sudo, and they can't read each other's or the admin's files.

And:
- Tokens live only in files on the server (written with a hidden prompt via `set-token`), never in git, `nori.conf` or a chat.
- Firewall closed except SSH and the Tailscale interface.
- Areas are separated for projects, chats, Claude state and `local/` rules. They are **not** separated for Plane: all areas share one Plane API key, so every session can read and change every project's tickets. `nori.conf` and the profile in `/opt/nori` are readable by every area user, so keep secrets out of them. If a colleague shares your server, give them their own server or Plane workspace.
- **A "work" area sends company code, diffs and screenshots through Telegram**, and Telegram bot chats are **not end-to-end encrypted**. Check your employer's policy first. For sensitive work use Remote Control / the Claude app instead of a chat bot.
- `git push`, `gh pr merge` and any command in `EXTRA_ASK_PERMISSIONS` are caught by ask rules (the push/merge ones also in root-owned managed settings, which a session can't edit away), and a `push-guard` hook also asks for `git -C repo push`, `gh api ... merge` and similar spellings. A script Claude writes that pushes internally is not inspected. Claude Code's docs say explicit ask rules prompt in every permission mode, including the auto mode pool sessions use. (Plus GitHub comments/reviews in areas with `ASK_BEFORE_GITHUB_COMMENTS=true`.) No production secrets belong on the box.

## Contributing
Improvements are welcome. Use a branch and a pull request; see [CONTRIBUTING.md](CONTRIBUTING.md).
