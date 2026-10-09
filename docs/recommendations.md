# To get a setup like ours ✅

An opinionated checklist from the setup Nori was built from. Each item has a one-line why, the setting (or "habit"), and how hard it is. You don't need all of it on day one: start with **Must-have**, live with it for a week, then add.

Shortcut: `PRESET=recommended` in `nori.conf` turns on most of the Must-have and Nice-to-have settings; `PRESET=full` adds the Power-user ones. See `setup-guide.md`, "Presets".

Difficulty: 🟢 easy (minutes) · 🟡 medium (half an hour) · 🔴 more work (an evening).

## Must-have
| | Item | Why | Setting / habit | Difficulty |
|---|---|---|---|---|
| [ ] | Your own server with Claude Code always on | it keeps working while your laptop sleeps | `setup-guide.md` steps 1–8 | 🟡 1–2 h the first time |
| [ ] | One chat bot per area | quick tasks from your phone, from anywhere | `AREAS`, one bot each | 🟢 |
| [ ] | Approve pushes and merges in your DM | nothing leaves the box without your 🔐 tap | always on (`git push`, `gh pr merge` ask) | 🟢 |
| [ ] | Nightly fresh start | a clean context every morning, continued from a short handoff note | `HANDOFF=true` (all presets) | 🟢 |
| [ ] | Git identity follows the repo owner | personal repos commit as you, company repos with your work email; a guard blocks mix-ups | `GITHUB_ACCOUNTS` | 🟢 |
| [ ] | Put your profile in `USER.md` | every session knows who you are, how you like answers, your tools | `profile/USER.md` | 🟢 10 min |
| [ ] | Keep secrets out of git and chats | tokens only on the server, via `set-token`; nothing to leak if a repo goes public | habit (+ `.gitignore`) | 🟢 |
| [ ] | Encrypted nightly backup of your work | a dead server doesn't take unpushed work with it (commits, uncommitted changes, handoff notes, skills) | `WORK_BACKUP=true` + `BACKUP_REPO`; `AREA_work_WORK_BACKUP=false` for company code (unless the backup repo is the company's) | 🟢 store the passphrase! |
| [ ] | Tailscale on server, phone and laptop | private links (previews, Plane) and SSH without opening ports | `setup-guide.md` step 4 | 🟢 |

## Nice-to-have
| | Item | Why | Setting / habit | Difficulty |
|---|---|---|---|---|
| [ ] | Ops bot | `/status`, `/progress`, `/restart`, alerts when something dies or RAM runs low, works even when Claude is stuck | `OPS_BOT=true` (recommended) | 🟢 one more bot |
| [ ] | Daily digest | one message each morning: repos, open PRs, what needs you | `DIGEST=true`, `DIGEST_TIME` | 🟢 |
| [ ] | `/usage` and `/recall` | token use per area and your plan-limit % (5h / weekly, from the status line); search past chats, handoffs and tickets from the chat | `OPS_BOT=true` (`/recall` needs `RECALL=true`) | 🟢 |
| [ ] | Tap-to-answer buttons and "still on it" pings | Claude's A/B questions arrive as buttons; long tasks ping you so you know nothing died; an alert if the chat bot's Telegram connection goes quiet | `OPS_BOT=true` | 🟢 |
| [ ] | `/ask` | ask the server questions ("why is RAM high?") without SSH | `OPS_ASK=true` | 🟢 |
| [ ] | Pool sessions for deep work | start extra Claude sessions from the Claude app for long, parallel tasks; keep the chat bot for quick ones | `POOL_SESSIONS=true`, `POOL_CAPACITY=4` + one-time consent | 🟢 |
| [ ] | Use `plan:` before big changes | Claude proposes a plan first, you say go; fewer surprises in big refactors | habit: start the message with `plan:` | 🟢 |
| [ ] | Previews | open the app Claude just built on your phone, tailnet-only | `PREVIEWS=true` | 🟢 |
| [ ] | Browser | Claude takes screenshots to check its own UI work | `BROWSER=true` (re-run bootstrap) | 🟢 |
| [ ] | Recall | "what did we decide about X last week?" searches past chats and handoffs | `RECALL=true` | 🟢 |
| [ ] | A group chat ("Nori HQ") | alerts, the digest and all your bots in one place | `/here` to the Ops bot in the group | 🟢 |

## Power-user
| | Item | Why | Setting / habit | Difficulty |
|---|---|---|---|---|
| [ ] | A separate area per life (personal / work) | each area is its own Linux user: the work session can't read personal files and the other way round (Plane tickets, `nori.conf` and the profile are shared by all areas, see README "Safety model") | `AREAS="personal work"` | 🟡 |
| [ ] | GitHub comments ask first in work | reviews and comments under your name in company repos are public; approve each one | `AREA_work_ASK_BEFORE_GITHUB_COMMENTS=true` (`full` sets it) | 🟢 |
| [ ] | Plane tickets | decisions live in tickets, not in a chat you scroll past; `/board`, `/peek`, a weekly review | `PLANE=true` (8 GB server) | 🔴 |
| [ ] | Keep decisions in tickets | the ticket is the record: questions, answers, branch, PR, "Done:" summary | habit (with Plane) | 🟢 |
| [ ] | Involvement labels | 🤖 auto tickets get done on their own; ⚡/🧠 ones wait for you, and the digest lists them | habit (with Plane) | 🟢 |
| [ ] | Ticket intake from others | teammates send `/ticket` to the Ops bot; Claude triages, you accept | `/allow` in the Ops bot | 🟢 |
| [ ] | ▶️ Do it on ticket cards | one tap on a ticket card tells the area session to start that ticket | `PLANE=true` + `OPS_BOT=true` | 🟢 |
| [ ] | Work members and work groups | `/allow <id> <name> <area>` lets a teammate use one area only; `/workgroup <area>` binds a group chat to an area | Ops bot commands | 🟢 |
| [ ] | Encrypted off-site backups of Plane | a dead server doesn't take your tickets with it | `PLANE_OFFSITE_BACKUP=true`, `BACKUP_REPO` | 🟡 store the passphrase! |
| [ ] | Close public SSH | only the tailnet can reach the box | `sudo ufw delete allow 22/tcp` (after Tailscale works) | 🟡 careful |
| [ ] | Your own rules and skills | teach the sessions your conventions once | `local/rules/*.md`, `local/skills/` | 🟡 |

## Habits that matter more than settings
- **Quick task → chat bot. Deep work → a pool session.** The chat session stays responsive; long refactors run next to it.
- **`plan:` first** for anything bigger than a small fix.
- **Approve pushes in your DM** and read the `📤 owner/repo · branch → target` line before you tap.
- **Let the nightly fresh start happen.** Don't fight it with one endless conversation; the handoff note carries what matters.
- **Write things down where they last:** decisions in tickets (or PR descriptions), your preferences in `USER.md`, conventions in `local/rules/`.
- **Secrets never go into git, `nori.conf` or a chat.** If one slips, revoke it and make a new one.
- **One Linux user per area** is the wall between work and personal. Don't share files across it.
