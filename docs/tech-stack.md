# The tech stack, explained 🧰

Every piece Nori uses, for someone who has never run a server. For each: what it is, why we picked it, what it costs, how to set it up (short; the full steps are in `setup-guide.md`), alternatives, and the gotchas we actually hit.

Prices below are rough and change. **Always check the provider's page before you buy.**

---

## Hetzner Cloud (the server)
**What:** a VPS, a small computer in a data center that runs all day. Claude Code lives there, so it keeps working when your laptop is closed.

**Why Hetzner:** best price for the performance in Europe, simple console, hourly billing (delete the server and you stop paying).

**Cost (2026):** Hetzner raised prices twice in 2026 (April and June). From Hetzner's price list after the 15 June 2026 change (Germany/Finland, excluding VAT and the €0.50/month IPv4): **CX23** (x86, 2 vCPU, 4 GB) €5.49, **CAX11** (Arm, 2 vCPU, 4 GB) €5.99, **CX33** (x86, 4 vCPU, 8 GB) €8.49, **CAX21** (Arm, 4 vCPU, 8 GB) €10.49 per month. The x86 Cost-Optimized types are often sold out; the Arm CAX types usually aren't. The **Singapore and US locations cost much more** than the EU ones. Check the current numbers at [hetzner.com/cloud](https://www.hetzner.com/cloud).

| You plan to use | Size |
|---|---|
| `PRESET=starter` or `recommended` (no Plane) | 4 GB (CAX11 / CX23) is enough |
| Plane tickets (`PRESET=full`), several areas, lots of pool sessions | **8 GB** (CAX21 / CX33) |

**Set up (short):**
1. Make an account at hetzner.com and verify it (ID or card check; can take a little while).
2. Console → new project → **Add server**.
3. Location: an EU one (Nuremberg, Falkenstein, Helsinki). Image: **Ubuntu 24.04 LTS** (best tested; 26.04 works, but limited sudo stays off there for now because 26.04 ships `sudo-rs`). Type: see the table.
4. Networking: public IPv4 on.
5. **SSH key: add yours here, at create time** (`setup-guide.md` step 2 makes one).
6. Backups: optional, +20% of the server price. Your code lives in GitHub anyway (and `WORK_BACKUP` saves what is not pushed yet); turn it on if you want snapshots of the box.
7. Create. Write down the IP.

**Alternatives:** DigitalOcean, Vultr, OVH, Linode/Akamai, or any Ubuntu 24.04+ VPS with 2+ vCPU, 4+ GB RAM, 40+ GB disk. Arm or x86 both work.

**Gotchas we hit:**
- **"Limited availability" / sold out.** The cheap Cost-Optimized types (CX, CAX) are often sold out in one location. Try another EU location, or switch between Arm (CAX21) and x86 (CX33).
- **Login fails right after creating the server.** Usually the SSH key: either a different key was added than the one your laptop offers, or the key has a **passphrase you forgot**. Ubuntu blocks root password logins over SSH, so there is no back door. The easy fix: **delete the server and create it again with the right key** (it takes a minute and costs cents). Or use Hetzner's web console / rescue mode.
- **Far away?** From Southeast Asia, an EU server adds a bit of latency, but you are chatting with a bot, so you won't notice. It's not worth the Singapore price.

---

## Claude Code + your Claude subscription
**What:** Claude Code is Anthropic's coding agent for the terminal. On the server it runs 24/7 inside tmux; you talk to it through the chat bot or the Claude app.

**Why:** it works with a normal **Claude Pro or Max subscription**, so you pay a flat monthly price instead of per-token API bills. No API key needed.

**Cost:** Pro or Max, see [claude.com/pricing](https://claude.com/pricing). Pro is enough to try it; heavy 24/7 use (several sessions, Opus) needs Max. It must be **your own account; never share a login.**

**Set up (short):** `bootstrap.sh` installs Claude Code for every Linux user. Then, as each user: `claude auth login --claudeai` (it prints a link; open it, paste the code back).

**Gotchas we hit:**
- **One login per Linux user.** The admin and every area user each log in once (same subscription).
- **One-time prompts only a human can answer:** the folder-trust prompt ("Do you trust this folder?") and "Allow external CLAUDE.md imports?" (the rules import your `USER.md`). If the always-on session seems stuck after the first start, attach (`attach <area>`) and answer it. Claude itself refuses to answer these for you, on purpose.
- **Remote Control consent:** the first time each area user uses Remote Control, Claude asks "Enable Remote Control? (y/n)". Run `claude remote-control` once as that user and answer `y` (setup-guide step 5).
- **Auto-mode safety check:** sometimes Claude (on your laptop or the server) refuses a command, such as an install script or answering a prompt for you. That's a safety feature. Run the command yourself; in a Claude session type `!` before it (e.g. `! sudo tailscale up`).
- **Never run `claude mcp list`, or `claude` without `--strict-mcp-config`, on the server** once a bot token is there. It starts a second copy of the chat bot, and the real session's bot goes silent until it restarts.

**Alternatives:** Anthropic API key billing (pay per token; can get expensive 24/7). Other agents aren't supported by Nori.

---

## Telegram (the chat)
**What:** the messenger you use to talk to your server's Claude from your phone, through a bot you create.

**Why Telegram:** creating a bot takes one minute and is free, bots work in DMs and groups, and the official Claude Code channel plugin (`telegram@claude-plugins-official`) supports it today.

**Cost:** free.

**Set up (short):** in Telegram open [@BotFather](https://t.me/BotFather) → `/newbot` → pick a name and a username ending in `bot` → it shows a **token** (a password; never paste it into a chat with Claude). For group use: `/setprivacy` → pick the bot → **Disable**. Get your numeric id from [@userinfobot](https://t.me/userinfobot) (use the link; searching shows lookalikes). Details: `chat/telegram/README.md`.

**How it behaves:**
- **Allowlist, not pairing:** only the ids in `CHAT_ALLOWED_IDS` get through; no pairing code needed.
- **👀 reaction** = the bot received your message. No 👀 = the bot isn't running.
- **🔐 permission buttons** (push, merge, ...) **always arrive in your DM** with the area bot, even if you wrote in a group.
- **One bot per Claude session.** Two programs can't read the same bot, so each area gets its own bot, and the Ops bot is another one. With `PRESET=starter` you need just **one** bot.

**Security and privacy:**
- **Your Telegram account controls the server:** it talks to the sessions, approves their pushes and runs the Ops bot (`/apply`, `/restart`). Turn on **two-step verification** (Settings → Privacy and Security → Two-Step Verification): a cloud password on top of the SMS code.
- **Bot chats are not end-to-end encrypted.** Telegram's servers can read what you and the bots send: code, diffs, screenshots. Fine for your own projects; for a **work** area check your employer's policy first. Remote Control / the Claude app is the alternative for sensitive work.

**Alternatives:** Discord and Slack are planned (see `chat/discord`, `chat/slack`), not supported yet. The Claude app (Remote Control) works next to Telegram.

---

## Tailscale (the private network)
**What:** a private network ("tailnet") between your devices. Your phone, laptop and server see each other as if they were on the same Wi-Fi, encrypted, without opening ports to the internet.

**Why:** Plane, previews and SSH stay off the public internet; only devices you've logged in can reach them.

**Cost:** the free Personal plan is plenty.

**Set up (short):** make an account at tailscale.com. Install the app on your **phone** and **laptop**, and on the server `sudo tailscale up --hostname=<SERVER_NAME>`. **Log in with the same account everywhere.** Check: the server shows up in the app as Connected.

**Gotchas we hit:**
- **"Already exists" / the laptop is already in another tailnet** (e.g. your company's). Add a second account/profile in the Tailscale app (account switcher → "Add account") and switch to it. Only one tailnet is active at a time, so if a Tailscale link doesn't open, check which one is connected.

**Alternatives:** WireGuard by hand, ZeroTier, Cloudflare Tunnel. Tailscale is the easiest.

---

## GitHub
**What:** where your code lives. The server clones, commits and opens PRs there.

**Why:** everyone has it, and `gh` (the GitHub CLI) lets Claude open PRs and read issues.

**Cost:** free.

**How Nori uses it:**
- **Two accounts are fine** (personal and company). In `GITHUB_ACCOUNTS` you list them; the **commit identity follows the repo owner** (a repo under `my-company/…` commits with your company email). A pre-commit guard blocks the wrong author.
- **Log in once per Linux user**: `gh auth login -h github.com -p https -w`. It shows a one-time code and opens a page: **check you're signed in as the right account on that page** before you approve. For company orgs with SSO, also press **Authorize** for that org.
- **This repo is a template:** on GitHub press "Use this template" to make your own private copy, then clone that.

**Alternatives:** GitLab / Bitbucket work for git, but the `gh` helpers are GitHub-only.

---

## Plane (optional tickets)
**What:** a self-hosted ticket board (like Jira/Linear) running in Docker on your server. Claude reads and writes tickets through a Plane MCP server, the Ops bot shows `/board` and `/peek`, and the digest lists what needs you.

**Why:** decisions and progress land in tickets, not in a chat scroll you lose overnight. Turned on by `PRESET=full` or `PLANE=true`.

**Cost:** free (self-hosted). Needs ~3–4 GB RAM extra, so use an **8 GB** server.

**How we use it:**
- **Tailnet only**: bound to the Tailscale IP, never public.
- **Modules = repos**: each module's description says which repo it is; Claude works in that repo.
- **Involvement labels** on every ticket: 🤖 `auto` (Claude does it end to end), ⚡ `quick-ask` (needs a short answer), 🧠 `needs-me` (a real decision; Claude proposes options and waits).

**Root, plainly:** with Plane the admin user is in the `docker` group, and anyone who can run `docker` can become root (mount `/` into a container). `ADMIN_SUDO=limited` does not contain that; keep the admin account and the Ops bot as safe as root.

**Gotchas:** the Plane API allows about **60 requests a minute**; bulk scripts must slow down. Plane's first-run screens change between releases; follow Plane's own self-hosting docs where they differ. Docker ports bypass the firewall, so always bind to the Tailscale IP (Nori's compose file does).

**Alternatives:** GitHub Issues / Projects, Linear (hosted), or no tickets at all.

---

## Small tools that bootstrap installs
| Tool | What it's for |
|---|---|
| **Bun** | runs the Telegram channel plugin (it's a Bun program) |
| **uv** | fast Python package and venv manager; each Python project gets its own `.venv` |
| **Node 22** | Claude Code itself, and Node projects |
| **Docker** | only for Plane (`PLANE=true`) |
| **Playwright + Chromium** | the headless browser for screenshots (`BROWSER=true`) |
| **tmux** | keeps the Claude session alive with no one logged in; `attach` looks into it |
| **gh** | GitHub CLI (PRs, issues) |

---

## Monthly cost summary
| Item | Cost per month |
|---|---|
| Hetzner server, 4 GB (CAX11 / CX23), EU | about €6 (2026; check the site) |
| …or 8 GB (CAX21 / CX33) for Plane | €10.49 (CAX21) or €8.49 (CX33, if available) |
| Hetzner backups (optional) | +20% of the server price |
| Claude Pro or Max subscription | see claude.com/pricing (you probably have it already) |
| Telegram, Tailscale, GitHub, Plane, Bun, uv, Docker, Playwright | free |

So, on top of your Claude subscription, a Nori box costs about the price of a coffee or two a month.
