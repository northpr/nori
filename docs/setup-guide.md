# Setup guide: step by step 🍙

Nori (the guide in `CLAUDE.md`) walks you through exactly these steps, one at a time. You can also follow them yourself. Each step has:
- **💻 laptop** or **🖥 server**: where the command runs,
- **✅ You should now see**: a checkpoint, so you know it worked,
- **⚠️ If it fails**: the problems we actually hit, and the fix.

New to the pieces (Hetzner, Tailscale, BotFather...)? Read `tech-stack.md` first. Want to know what to turn on? `recommendations.md`.

**Three rules for the whole way:**
1. Use your **own** Claude subscription (Pro or Max). Never share a login.
2. **No secrets in chats, in `nori.conf` or in git.** Bot tokens go onto the server through a hidden prompt (`set-token`).
3. **On the server, never run `claude mcp list` or `claude` without `--strict-mcp-config`** once a bot token is there. It starts a second copy of the chat bot and knocks out the real one.

Time: about 1–2 hours the first time, most of it waiting for installs.

---

## Step 0. Pick a preset and write nori.conf (💻 laptop)
```
cp nori.conf.example nori.conf
```
Open `nori.conf`. First choose **`PRESET`**:

| Preset | You get | Bots to create | Server |
|---|---|---|---|
| `starter` | 1 Claude session + 1 chat bot, nightly fresh start, git identity guard. Nothing else. | 1 | 4 GB |
| `recommended` (default) | starter + **Ops bot** (`/status` `/progress` `/restart` `/ask`, alerts, daily digest) + pool sessions (4) + browser + previews + recall | 2 | 4 GB |
| `full` | recommended + **Plane tickets** (`/board` `/peek`, ticket intake, weekly review) + off-site backups + 8 pool sessions + "GitHub comments ask first" in every area after the first | 2 + 1 per extra area | **8 GB** |

Any flag you set yourself wins over the preset (uncomment it in the "overrides" part of `nori.conf`). The full flag table is in "Presets" below.

Then fill in the basics: `OWNER_NAME`, `TIMEZONE`, `LANGUAGES`, `CHAT_ALLOWED_IDS` (message `@userinfobot` on Telegram for your numeric id), `AREAS` (start with one), `GITHUB_ACCOUNTS`. Optional: copy `profile/USER.md.example` to `profile/USER.md` and write a few lines about yourself.

Check it:
```
./setup.sh --render-only /tmp/nori-preview
```
> ✅ **You should now see** `rendered into /tmp/nori-preview`. `cat /tmp/nori-preview/nori.resolved.conf` shows which features your preset turned on.
>
> ⚠️ **If it fails:** it lists every problem (`nori.conf problems: ...`) with what to fix, e.g. `PRESET must be starter, recommended or full`.

## Step 1. Buy a server (🌐 browser)
At [hetzner.com/cloud](https://www.hetzner.com/cloud): **Add server** →
- Location: an EU one (Nuremberg, Falkenstein, Helsinki). Singapore/US cost much more; the extra latency from Asia doesn't matter for chat.
- Image: **Ubuntu 24.04 or 26.04 LTS**.
- Type: **4 GB** (CAX11 Arm / CX23 x86) for starter or recommended; **8 GB** (CAX21 / CX33) for full / Plane.
- Public IPv4: on. Backups: optional (+20%).
- SSH key: do **step 2 first**, then paste your public key here before you click Create.

> ✅ **You should now see** the server running in the console, with an IPv4 address. Write it down.
>
> ⚠️ **If it fails:**
> - **"Limited availability" / sold out:** pick another EU location, or switch Arm ↔ x86 (CAX21 ↔ CX33).
> - Any Ubuntu 24.04+ VPS elsewhere works too (2+ vCPU, 4+ GB RAM).

## Step 2. SSH key and a short name for the server (💻 laptop)
```
ssh-keygen -t ed25519 -f ~/.ssh/nori_ed25519 -C nori
cat ~/.ssh/nori_ed25519.pub        # the PUBLIC key: paste this into Hetzner's "SSH keys"
```
A passphrase is optional. If you set one, **remember it** (password manager). Add to `~/.ssh/config`:
```
Host nori
    HostName <server IP>
    User root                      # becomes your ADMIN_USER after step 3
    IdentityFile ~/.ssh/nori_ed25519
```
Test: `ssh nori 'echo hello'`
> ✅ **You should now see** `hello`.
>
> ⚠️ **If it fails** (`Permission denied (publickey)`):
> - The server got a different key, or you forgot the key's passphrase. Ubuntu doesn't allow root password logins, so there's no way around it: **delete the server and create it again with the right key.** It takes a minute and costs cents.
> - `Host key verification failed` after recreating: `ssh-keygen -R <server IP>`, then try again.

## Step 3. Bootstrap the server (🖥 server, once, as root)
```
scp -r . nori:/root/nori                         # 💻 laptop: copies the repo + your nori.conf (no secrets in it)
ssh nori
cd /root/nori && bash bootstrap.sh --plan        # shows what it will do
bash bootstrap.sh
```
It sets timezone and hostname, installs packages (git, tmux, gh, Node 22, Bun, uv, Tailscale, Claude Code; Docker only with Plane; Chromium only with the browser), creates your admin user and one user per area, sets up the firewall, turns off SSH passwords and root login, and copies the repo to the admin's `~/nori`. Running it again is safe.

**Before you close the root session**, open a second terminal and test: `ssh <ADMIN_USER>@<server IP>`. Then change `User root` to `User <ADMIN_USER>` in `~/.ssh/config`.
> ✅ **You should now see** `Bootstrap done. The remaining steps are MANUAL`, and the admin login works in the second terminal.
>
> ⚠️ **If it fails:**
> - **`missing or unsuitable terminal: xterm-ghostty`** (or kitty, WezTerm...): the server doesn't know your terminal. Quick fix: `export TERM=xterm-256color`. Real fix, from your 💻 laptop, installs it system-wide so every user gets it: `infocmp -x $TERM | ssh nori sudo tic -x -o /usr/share/terminfo -`
> - It stops with an error: read the last lines, fix, run `bash bootstrap.sh` again.

*Why passwordless sudo for the admin:* `setup.sh` (and the Ops bot) run commands as the area users (`sudo -u <area>`) without a password prompt. Logins are key-only and the account has no password. Stricter setups can limit `/etc/sudoers.d/90-nori-admin`.

## Step 4. Tailscale: your private network (🖥 server + 📱 phone + 💻 laptop)
Make a free account at tailscale.com. Install the app on your **phone and laptop**, logged in with the **same account**. On the server:
```
sudo tailscale up --hostname=<SERVER_NAME>      # open the printed link and log in
tailscale status
```
> ✅ **You should now see** your server, phone and laptop in `tailscale status` (and in the app).
>
> ⚠️ **If it fails:**
> - **"Already exists" / your laptop is already in another tailnet** (e.g. work): in the Tailscale app add a new account/profile and switch to it. Only one tailnet is active at a time.
> - Later, close public SSH (`sudo ufw delete allow 22/tcp`) only once you reach the server over Tailscale. The provider's web console is the way back if you lock yourself out.

## Step 5. Log Claude in on the server (🖥 server)
Do this **before any bot token is on the server.** For the admin, and for each area user (`sudo -iu <area>`):
```
claude auth login --claudeai       # prints a link: open it, log in with YOUR subscription, paste the code back
cd ~/projects/<area> && claude     # area users: answer the folder-trust prompt, then /exit
```
Install the chat plugin, as each **area** user:
```
claude plugin marketplace add anthropics/claude-plugins-official
claude plugin install telegram@claude-plugins-official
```
(If the subcommands differ in your version: `claude plugin --help`, or `/plugin` inside `claude`.)

**Remote Control consent** (with `REMOTE_CONTROL` or pool sessions on, the default), once per area user, in `~/projects/<area>`:
```
claude remote-control        # answer "Enable Remote Control? y", wait until it says ready, then Ctrl+C
```
**GitHub**, once per Linux user and per GitHub account it needs:
```
gh auth login -h github.com -p https -w
```
> ✅ **You should now see** `claude auth status` showing your account, `claude plugin list` showing `telegram`, and `gh auth status` showing the right GitHub login.
>
> ⚠️ **If it fails:**
> - **GitHub device login went to the wrong account:** the browser page approves whoever is signed in there. Check the account in the top-right corner before you approve; if wrong, `gh auth logout` and repeat. Company org with SSO: on the approval page press **Authorize** next to that org (later: github.com → Settings → Applications → Authorized OAuth Apps → GitHub CLI → Grant).
> - **Claude refuses to run an install or to answer a prompt for you** (auto-mode safety check): that's on purpose. Run the command yourself; inside a Claude session type it with `!` in front, e.g. `! sudo tailscale up`.
> - The pool keeps restarting later: you skipped the Remote Control consent; do it now. The folder stays busy 1–2 minutes after a manual run.

Language toolchains (Go, Rust...) are yours to install per area user, e.g. Go into `~/.local/go` (already on the session's PATH).

## Step 6. Create the bot(s) and put the tokens on the server (📱 Telegram + 🖥 server)
In Telegram, `@BotFather` → `/newbot` → a name, and a username ending in `bot`. Make:
- **one bot per area**, and
- **one Ops bot**, unless `PRESET=starter` / `OPS_BOT=false`.

For bots that will sit in a group: `/setprivacy` → the bot → **Disable**. Open each bot's DM and press **Start**. Details: `chat/telegram/README.md`.

Then on the server, as the admin, **in your own terminal** (hidden prompt; never paste a token into a chat with Claude):
```
~/nori/server/bin/set-token <area>     # once per area
~/nori/server/bin/set-token ops        # only with the Ops bot
```
> ✅ **You should now see** `wrote the token for '<area>' (mode 600 ...)`.
>
> ⚠️ **If it fails:** a token ended up in a chat or a file? In BotFather `/revoke` it, make a new one, `set-token` again.

## Step 7. Switch it on (🖥 server, as the admin)
If you changed anything on the laptop since step 3: `rsync -a --exclude .git --exclude generated ./ nori:~/nori/` (💻). Then:
```
cd ~/nori && ./setup.sh
./setup.sh --check
```
> ✅ **You should now see** `started claude@<area>` (and `started ops-bot` with the Ops bot), then `in sync ✅`.
>
> ⚠️ **If it fails:**
> - `no chat bot token yet`: step 6 for that area, then `./setup.sh` again.
> - **The session waits on a prompt** (folder trust, "Allow external CLAUDE.md imports?", Remote Control consent): look with `attach <area>`, answer it (Enter / `y`), then leave with `Ctrl+b` then `d`. Only a human can answer these; Claude won't.

## Step 8. Test (📱 phone)
1. Message your area bot `hi`.
   > ✅ A 👀 reaction within seconds, then an answer.
2. With the Ops bot: `/status`, `/progress`, `/ask is everything healthy?`. In a group: `/here`.
3. 💻 `ssh nori '~/nori/setup.sh --check'` → `in sync ✅`.
4. Look inside: `ssh -t nori attach <area>`. Leave with `Ctrl+b` then `d`. **Never type `/exit`** there.

> ⚠️ **If it fails:**
> - **No 👀:** the bot isn't running. Ops bot: `/restart <area>`. Without the Ops bot: `ssh -t nori` then `sudo -u <area> XDG_RUNTIME_DIR=/run/user/$(id -u <area>) systemctl --user restart claude@<area>`. The usual cause is a second bot copy (rule 3 at the top).
> - **👀 but no answer:** Claude is busy or waiting for a 🔐 permission. **🔐 buttons always arrive in your DM** with the area bot, not in a group.
> - More: `troubleshooting.md`.

🎉 Done. You have Claude on your own server, in your pocket.

## Step 9. Add features later
Flip a flag in `nori.conf` (or change `PRESET`), then: re-run bootstrap if the feature needs packages (Plane, browser), `./setup.sh --restart`, test. See "Optional features" below.

---

## Presets
`PRESET` sets the defaults; any flag set in `nori.conf` wins. `setup.sh` writes the result to `generated/nori.resolved.conf`.

| Flag | starter | recommended | full |
|---|---|---|---|
| `OPS_BOT` (Ops bot: `/status` `/progress` `/restart` `/apply`, alerts) | false | true | true |
| `OPS_ASK` (`/ask`) | false | true | true |
| `DIGEST` (daily digest) | false | true | true |
| `HANDOFF` (nightly handoff + fresh start) | true | true | true |
| `POOL_SESSIONS` / `POOL_CAPACITY` | false / 4 | true / 4 | true / 8 |
| `PREVIEWS` | false | true | true |
| `RECALL` | false | true | true |
| `BROWSER` | false | true | true |
| `PLANE` (tickets, `/board` `/peek`, ticket intake, weekly review) | false | false | true |
| `PLANE_OFFSITE_BACKUP` | false | false | true once `PLANE_BACKUP_REPO` is set |
| `AREA_<a>_ASK_BEFORE_GITHUB_COMMENTS` | false | false | true for every area after the first |
| Git identity guard, push/merge approvals, `attach`, `cc-slash` | always | always | always |

Areas are never added by a preset: `full` *supports* `AREAS="personal work"`, you still list them.

### Running without the Ops bot (`starter`, or `OPS_BOT=false`)
One Claude + one chat bot. What changes:
- No `ops-bot` service, no health-check cron. **Health alerts and `/ask` are not available.** (`setup.sh` stops a running Ops bot when you switch it off.)
- `/status`, `/progress`, `/restart` → use SSH instead:
  - restart: `ssh -t nori` then `sudo -u <area> XDG_RUNTIME_DIR=/run/user/$(id -u <area>) systemctl --user restart claude@<area>` (or, logged in as the area user: `systemctl --user restart claude@<area>`)
  - look: `ssh -t nori attach <area>`
  - all sessions at once: `cd ~/nori && ./setup.sh --restart`
- The daily digest (if you set `DIGEST=true`) and the nightly handoff report arrive **in your DM through your area bot** instead.
- You can add the Ops bot any time: `OPS_BOT=true`, create the bot, `set-token ops`, `./setup.sh`.

## All settings
| Setting | Meaning |
|---|---|
| `PRESET` | `starter`, `recommended` (default) or `full`: feature defaults, see above |
| `OWNER_NAME`, `LANGUAGES`, `TIMEZONE` | used in the rules Claude follows and for cron times |
| `SERVER_NAME` | hostname, Tailscale machine name, Remote Control name prefix |
| `ADMIN_USER` | Linux user with sudo: runs the Ops bot, cron, `setup.sh` |
| `CHAT`, `CHAT_ALLOWED_IDS` | chat platform (only `telegram`) and who may talk to the bots |
| `AREAS`, `AREA_<a>_*` | one always-on session per area; each area = own Linux user + own bot + prefix |
| `AREA_<a>_ASK_BEFORE_GITHUB_COMMENTS` | `true`: GitHub reviews, PR/issue comments, PR edit/close ask first in that area (teammates see them) |
| `GITHUB_ACCOUNTS` | `owner\|commit name\|commit email\|gh login`: git identity follows the repo owner |
| `OPS_BOT`, `OPS_ASK`, `OPS_GROUP_NAME` | the Ops bot, its `/ask`, the group label |
| `HANDOFF`, `HANDOFF_TIME` | nightly handoff note + fresh restart |
| `DIGEST`, `DIGEST_TIME`, `DIGEST_LANGUAGE` | daily repo digest (Ops chat, or your DM without the Ops bot) |
| `REMOTE_CONTROL` | also reachable from the Claude app |
| `AUTO_UPDATES`, `AUTO_REBOOT_TIME` | unattended security updates and the reboot window |
| `EXTRA_ASK_PERMISSIONS` | more commands that always ask first (`git push`, `gh pr merge` always do) |
| `POOL_SESSIONS`, `POOL_CAPACITY` | extra Claude sessions per area, started from the Claude app / claude.ai/code |
| `PLANE`, `PLANE_WORKSPACE` | self-hosted Plane tickets |
| `PLANE_OFFSITE_BACKUP`, `PLANE_BACKUP_REPO` | encrypted Plane backups to a private GitHub repo |
| `PREVIEWS`, `PREVIEW_PORT_START` | `preview` command (tailnet only) |
| `RECALL` | search over past chats |
| `BROWSER` | headless browser MCP |
| `TAILNET_HOST` | filled in by `setup.sh` once Tailscale is up |

## Optional features
**Plane tickets (`PLANE=true`).** Re-run `sudo bash ~/nori/bootstrap.sh` (installs Docker), make sure Tailscale is up, `./setup.sh` (creates `~/plane/plane.env` with generated secrets, binds Plane to the Tailscale IP only), then `cd ~/plane && docker compose --env-file plane.env up -d`. Open `http://<TAILNET_HOST>/god-mode/` on a tailnet device to create the instance admin, then a workspace whose slug equals `PLANE_WORKSPACE`, then your projects, and **one module per repo**. Create an API token in Plane (profile settings), then `~/nori/server/bin/set-token plane` and `./setup.sh --restart`. Add your projects/modules table to `local/rules/plane-projects.md`. The Ops bot then also offers `/board [area|project]`, `/peek <ID>`, `/ticket`, `/allow`, `/revoke`, `/people`, moves tickets to Done when a PR with the ticket id merges, and posts a weekly review. Map projects to areas with `AREA_<a>_PLANE_PROJECTS="ID1,ID2"`. The Plane API allows about 60 requests a minute. (Plane's first-run screens change between releases; follow Plane's own docs where they differ.)

**Encrypted Plane backups (`PLANE_OFFSITE_BACKUP=true`).** Create a **private** GitHub repo, set `PLANE_BACKUP_REPO="you/that-repo"`, make sure the admin ran `gh auth login`. `setup.sh` creates `~/.backup-pass`; **copy that passphrase into your password manager at once**; without it the backups are unreadable. Restore: `troubleshooting.md`.

**Previews (`PREVIEWS=true`).** `preview start <name> -- <command>` inside a repo gives a link on the tailnet. Dev/test config only.

**Recall (`RECALL=true`).** An index of past chats and handoffs per area, refreshed every 15 minutes; `recall "words"`.

**Browser (`BROWSER=true`).** Re-run bootstrap (installs Chromium into `/opt/ms-playwright`), `./setup.sh --restart`. Screenshots land in `~/shots/<area>/`.

**A second area.** Add the name to `AREAS`, add `AREA_<name>_PREFIX/_DESCRIPTION/_BOT` (and `AREA_<name>_ASK_BEFORE_GITHUB_COMMENTS=true` for shared/company repos), create another bot, then: `sudo bash ~/nori/bootstrap.sh` (creates the user, installs Claude), step 5 for the new user, `set-token <name>`, `./setup.sh --restart`. The new session can't read the other area's files. Plane tickets (one shared API key), `nori.conf` and the profile are shared by all areas, so put no secrets in them.

## Updating Nori later
Your copy of Nori is the source of truth. On the laptop `git pull` (your `nori.conf`, `profile/USER.md`, `local/` are gitignored, never overwritten), then `rsync -a --exclude .git --exclude generated ./ nori:~/nori/` and on the server `cd ~/nori && ./setup.sh` (`--restart` if rules/settings changed). After the rsync, the Ops bot's `/apply` runs `setup.sh` for you. It never pulls: the server copy has no `.git`, so a push to the repo can't change the server (the admin has passwordless sudo).

> ⚠️ **`git pull` refuses: "Your local changes would be overwritten"** although you changed nothing: `setup.sh` made a script executable that isn't executable in git (a file-mode change). Fix it at the source, in your repo on the laptop: `git update-index --chmod=+x <file>`, commit, push. On the server, `git diff` shows `old mode 100644 / new mode 100755`; `git checkout -- <file>` then pull again.

## What lives where
| Repo path | On the server |
|---|---|
| `nori.conf` | `~/nori/nori.conf` (admin), read-only copy `/opt/nori/nori.conf` |
| `generated/nori.resolved.conf` | the flags after `PRESET`, read by the Python helpers |
| `generated/CLAUDE.md` (from `server/rules/*.md`) | `~/projects/CLAUDE.md` of each area user |
| `generated/areas/<a>/*` | `~/projects/<a>/CLAUDE.md`, `.claude/settings.json`, `.mcp.json` |
| `server/bin/*` | `~/.local/bin/*` (area users get only the ones they need) |
| `generated/git/*`, `server/git/pre-commit` | `~/.gitconfig*`, `~/.config/gh-accounts`, `~/.git-hooks/pre-commit` |
| `generated/claude/settings.partial.json` | merged into `~/.claude/settings.json` |
| `generated/chat/access.<a>.json` | merged into `~/.claude/channels/telegram-<a>/access.json` |
| `generated/systemd/*` | `~/.config/systemd/user/` (`claude@`, `claude-pool@` for areas; `ops-bot` for the admin) |
| `generated/crontab` | the admin's crontab |
| `plane/*` | `~/plane/` (only with `PLANE`) |
