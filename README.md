<p align="center">
  <img src="assets/readme/hero.svg" alt="Nori: your own Claude Code, awake 24/7 on a small server, and you drive it from your phone" width="100%">
</p>

# Nori 🍙

**Your own Claude Code, running 24/7 on a ~€6/month server, that you talk to from Telegram.**

Send "fix the export bug" from the bus. Claude works on your server while your laptop is closed, asks before it pushes (one tap: ✅ Allow), opens the PR and sends you a preview link. Your repos, your Claude subscription, your server.

### 🔒 Security at a glance
- **Your keys stay yours:** typed hidden, sent only to your own server, never saved on your laptop, in git or in a chat.
- **Your server is locked down:** firewall closed except key-only SSH and private Tailscale; each Claude runs as its own user without sudo.
- **Risky actions ask you first:** pushes and merges always need your 🔐 tap, even in auto mode.
- **What it can't protect:** whoever gets into your Telegram account can make Claude run code on your server, so turn on Telegram two-step verification. Bot chats aren't end-to-end encrypted.
- Found a problem? Report it privately ([SECURITY.md](SECURITY.md)). Details: [docs/security.md](docs/security.md).

## Start
You need [Claude Code](https://docs.claude.com/en/docs/claude-code). Then:
```
git clone https://github.com/northpr/nori && cd nori && claude
```
and say **hi Nori**. Nori (the guide in `CLAUDE.md`) asks a few questions in English or Thai, writes your config, and sets up the server with you, step by step (or in one go with `./nori up`). Questions at any point? Just ask Nori.

On a Mac, the first `git` may show a popup to install Apple's developer tools: click Install (about 5 min, free), then run it again.

## How it fits together
<p align="center">
  <img src="assets/readme/architecture.svg" alt="Your phone talks to your Telegram bots; each bot drives its own always-on Claude session on your server; the Ops bot handles status, alerts and buttons; the Claude app opens extra sessions; Tailscale keeps previews and tickets private; GitHub gets branches and PRs, and pushes ask you first" width="100%">
</p>

<table>
<tr>
<td width="320" valign="top"><img src="assets/readme/phone.svg" alt="A Telegram chat: you ask the work bot to fix the CSV export, it reacts 👀, reports progress, asks to push with Allow and Deny buttons, then sends the PR and a preview link" width="300"></td>
<td valign="top">

**What you get**
- An always-on Claude session that you chat with on Telegram (👀 = got it), with a fresh start every night, and a handoff plus `/clear` mid-day when its context gets 80% full.
- 🔐 Allow / Deny cards for pushes, merges and file edits, and tap-to-answer buttons.
- An **Ops bot**: `/status`, `/progress`, `/restart`, alerts, a daily digest, `/usage`, `/recall`.
- Previews on your phone over Tailscale, extra sessions from the Claude app.
- Secrets kept out of chats and git: `nori-env` hands them to a command, `secret-guard` blocks reads.
- Proof before claims: bugs get a repro first, speed claims need numbers, odd code gets a `why` check before it's removed.
- Replies in your language (or one fixed language), with technical words kept in English.
- Optional: Plane tickets from the chat, encrypted backups, separate `personal` and `work` areas.

</td>
</tr>
</table>

<p align="center">
  <img src="assets/readme/screens.svg" alt="Three Telegram screens: the Ops bot's morning digest with repos, tickets and a suggested focus; Nori asking a question with tap-to-answer buttons and acting on the tap; the /board ticket list grouped by Doing, To do and Backlog" width="100%">
</p>

## Works with your other apps
| App | What Nori does with it |
|---|---|
| 💬 **Telegram** | Your main remote: chat with each area's bot, tap 🔐 Allow / Deny, get alerts and the morning digest. |
| 📱 **Claude app** (iOS, Android, claude.ai/code) | Open extra sessions on the server, or drop into a running one with Remote Control. |
| 🐙 **GitHub** | Branches, commits and PRs with the right account per repo owner. Pushes and merges always ask you first. |
| 💻 **Your laptop** | `laptop/setup-laptop.sh` makes Claude Code on your laptop follow the same core rules as the server, in every project. |
| 🔒 **Tailscale** | Private previews of your app on your phone, and Plane, without opening any port. |
| 📋 **Plane** (optional) | Self-hosted tickets: create them from the chat, see them in `/board`, and the session keeps decisions there. |

## Pick a preset
One line in `nori.conf`; every feature can still be switched on or off later. Full table: [docs/setup-guide.md](docs/setup-guide.md#presets).

| | 🌱 starter | ⭐ recommended | 🚀 full |
|---|---|---|---|
| Claude session + Telegram bot, nightly fresh start, push approvals | ✅ | ✅ | ✅ |
| Ops bot, extra sessions, previews, browser, recall | | ✅ | ✅ |
| Plane tickets, off-site backups | | | ✅ |
| Server | 4 GB | 4 GB | 8 GB |

## What it costs
Your own Claude subscription (Pro or Max; never share a login) and a small server, e.g. Hetzner CAX11 at about €6/month. Telegram, Tailscale and GitHub are free.

## Docs
[Setup guide](docs/setup-guide.md) · [Tech stack](docs/tech-stack.md) · [Recommendations](docs/recommendations.md) · [Troubleshooting](docs/troubleshooting.md) · [Security](docs/security.md)

## Contributing
Improvements are welcome: fork, branch, pull request. See [CONTRIBUTING.md](CONTRIBUTING.md).
