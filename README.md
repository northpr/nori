<p align="center">
  <img src="assets/readme/hero.svg" alt="Nori: your own Claude Code, awake 24/7 on a small server, and you drive it from your phone" width="100%">
</p>

# Nori 🍙

**Your own Claude Code, running 24/7 on a ~€6/month server, that you talk to from Telegram.**

Send "fix the export bug" from the bus. Claude works on your server while your laptop is closed, shows progress, asks before it pushes (one tap: ✅ Allow), opens the PR and sends you a preview link. Every night it writes a handoff note and starts fresh. Your repos, your Claude subscription, your server.

Nori is a template plus a friendly setup guide. Clone it, open it on your laptop, run `claude`, and say "hi Nori". Nori (the guide in `CLAUDE.md`) walks you through buying a small server, connecting to it, creating your chat bots and switching everything on, one step at a time, and writes down its progress so you can stop and resume.

```
git clone <your copy of this repo> nori && cd nori && claude
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
| **Plane** tickets, `/board` `/peek`, ticket intake, weekly review, off-site backups | | | ✅ |
| Bots to create | 1 | 2 | 2 + 1 per extra area |
| Server | 4 GB | 4 GB | 8 GB |

## What you get
- One always-on Claude session per area on your server (systemd + tmux, also reachable from the Claude app via Remote Control).
- A **Telegram chat bot** to talk to it: short phone-friendly replies, progress updates, 🔐 permission requests in your DM.
- An **Ops bot** (a small script, not Claude; optional): `/status`, `/progress`, `/restart`, `/apply`, alerts when something dies or memory runs low, a daily digest, and `/ask <question>`. Without it you run just one Claude + one chat bot, and the digest comes through your chat bot.
- A **session pool** per area: start several extra Claude sessions from the Claude app or claude.ai/code next to the chat session.
- **Nightly handoff + fresh restart:** each night the session writes a handoff note, then restarts with a clean context and picks up from the note.
- **Git identity per repo owner** (personal vs company accounts) with a pre-commit guard, a `gh` wrapper, and ask-first rules for pushes and merges.
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
1. `git clone` this repo on your laptop, `cd nori`, install [Claude Code](https://docs.claude.com/en/docs/claude-code), run `claude`.
2. Say **hi Nori**. Nori asks which preset you want (starter, recommended or full), a few more questions, writes `nori.conf` for you, and guides you through the rest.
3. Prefer doing it yourself? Follow `docs/setup-guide.md`.

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
`git pull` on your laptop (your `nori.conf`, `profile/USER.md`, `local/` and `SETUP-PROGRESS.md` are gitignored), copy the repo to the server (`rsync -a --exclude .git --exclude generated ./ <server>:nori/`), then on the server `cd ~/nori && ./setup.sh` (add `--restart` if rules or settings changed). Details in `docs/setup-guide.md`.

## Safety model in short
- Tokens live only in files on the server (written with a hidden prompt via `set-token`), never in git, `nori.conf` or a chat.
- Area sessions run as separate Linux users without sudo; firewall closed except SSH and the Tailscale interface.
- Areas are separated for projects, chats, Claude state and `local/` rules. They are **not** separated for Plane: all areas share one Plane API key, so every session can read and change every project's tickets. `nori.conf` and the profile in `/opt/nori` are readable by every area user, so keep secrets out of them. If a colleague shares your server, give them their own server or Plane workspace.
- `git push`, `gh pr merge` and any command in `EXTRA_ASK_PERMISSIONS` are caught by ask rules, and a `push-guard` hook also asks for `git -C repo push`, `gh api ... merge` and similar spellings. A script Claude writes that pushes internally is not inspected. Pool sessions run with `--permission-mode auto`: confirm on your server that the ask rules and the hook still prompt there. (Plus GitHub comments/reviews in areas with `ASK_BEFORE_GITHUB_COMMENTS=true`.) No production secrets belong on the box.

## Contributing
Improvements are welcome. Use a branch and a pull request; see [CONTRIBUTING.md](CONTRIBUTING.md).
