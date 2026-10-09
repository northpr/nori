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

## Quick setup (`./nori up`) (beta, being tested)
The start is just:
```
git clone https://github.com/northpr/nori && cd nori && claude
```
Questions at any point? Ask Nori in that Claude window: it knows this guide.
You need Claude Code; Nori does the rest in chat. On a Mac, the first `git` may show a popup asking to install Apple's developer tools: click Install (about 5 min, free), then run the command again.

If something stops, the step-by-step guide below always works. The fast way: one command on your laptop sets up the whole server. **Quick gets you chatting on Telegram first.** Tailscale (previews on your phone, Plane) is optional and comes later with `./nori up --add tailscale`; the Claude app comes after a one-time browser login (see "Claude app after Quick setup" below). Three ways to start:
1. ⚡ **Quick**: Nori creates a **Hetzner Cloud** server for you, then does the rest.
2. 🧭 **Step by step**: skip this section and follow Step 0 onwards. Slower, but you do each step yourself.
3. 🖥 **I already have a server**: any Ubuntu 24.04+ VPS. Run `./nori up --host <ip>`. You need root SSH access like on a fresh VPS: Nori prints its public key, you add it to root's `~/.ssh/authorized_keys` (provider console, or your current ssh), then press Enter.

Do Step 0 first (preset and `nori.conf`). This is the stack we recommend and test with: **Hetzner** (server), your **Claude subscription** and **Telegram** (chat), with **Tailscale** (private network) added later. Prefer something else? Feel free: another VPS provider works through option 3 (`--host`) or the step-by-step guide; Tailscale and Telegram are what Nori is built and tested on today (Discord/Slack are planned, see `chat/*/README.md`).

🔒 **Read this first: don't paste any key yet.** Never paste one into a chat. Keep them in a password manager. `./nori up` asks for each one with hidden typing (the admin password twice).

Get these keys ready:
- **Hetzner API token**. First sign up: create an account at hetzner.com/cloud, verify your identity and add a payment method (card/PayPal). The recommended server costs about €6/month, billed by the hour (a test costs cents; delete the server to stop paying). Then: console.hetzner.cloud → new project 'nori' → Security → API tokens → Generate. **The default is Read: change it to Read & Write** (Nori has to create the server). Looks like 64 letters and digits.
- **Claude token**: open a new terminal tab (Mac ⌘T), run `claude setup-token` and copy what it prints. Looks like `sk-ant-oat01-…` (long, one line). It must be your own Claude account, never shared.
- **Telegram bot token** for each bot (one per area, plus the Ops bot if you use it): open [@BotFather](https://t.me/BotFather) (use the link; searching shows lookalikes) → /newbot. Looks like `123456789:AAH4kLm…`. Also note each bot's **username** (e.g. `my_nori_bot`): it is not secret, it's the bot you'll chat with.
- **Admin password**: you make this one up yourself (your password manager can generate it), 12+ characters.

**Later (optional): Tailscale.** Telegram doesn't need it. For previews on your phone and Plane you need it: create a one-off, pre-approved auth key (login.tailscale.com/admin/settings/keys, looks like `tskey-auth-kAb12CdEF11CNTRL-…`) and run `./nori up --add tailscale`. That asks only for that key and joins the existing server (if sudo is already limited it also asks the admin password). Install Tailscale on your phone and laptop too.


A template for one note in your password manager (paste each key after its colon):
```
Nori keys (server: nori-server)
Hetzner API token:   
Claude token:         
Bot token (main):     
Bot username (main):  
Bot token (Ops):      
Admin password:      
```

Keep the note in a password manager (e.g. Apple Passwords, 1Password, Bitwarden).

Run it in **a new terminal window (Mac: **⌘N** in Terminal or iTerm, or **⌘T** for a new tab; Linux: Ctrl+Alt+T; Windows: open Windows Terminal / WSL)**, not in a chat (it asks hidden questions). Never paste a key into a chat.
```
./nori up
```
It asks for the keys once, at the start. Typing is hidden; no keys or tokens are saved. Nori writes its own SSH key `~/.ssh/nori_ed25519` (no passphrase), a block in `~/.ssh/config` and `generated/up-state.json` (server id and IP). A bad key is refused on the spot (bot tokens are checked with Telegram). Then it shows the exact server type, location and live monthly price it will create. **Only a typed `yes` creates anything.** Use `--type` and `--location` to pick a pair yourself (its own price is shown; if it isn't available, Nori says so and creates nothing).

What it does, one stage at a time (each finished stage prints ✅):
- `create`: makes the Hetzner server (or uses your `--host`).
- `ssh`: adds a marked `# >>> nori >>>` block to `~/.ssh/config` (`Host nori`, key `~/.ssh/nori_ed25519`, host keys in `~/.ssh/nori_known_hosts`) and waits for SSH.
- `copy`: copies this repo to the server.
- `bootstrap`: runs `bootstrap.sh` (admin user, firewall, tools).
- `tailscale`: skipped in Quick (shown as ⏭, recorded as "later"); `./nori up --add tailscale` runs just this stage later.
- `claude`: puts your Claude token in for the admin and each area user, and installs the chat plugin.
- `tokens`: puts the bot tokens on the server.
- `admin`: sets the admin password and switches to limited sudo.
- `setup`: runs `./setup.sh --restart`.
- `prompts`: prints the last step (below).

If a stage fails you see `✗ <stage>: …`. When a key caused it (a read-only Hetzner token, a wrong bot key, the admin password), Nori asks `Re-enter … and retry this step? [y/N]`: type `y`, paste only that key, and that step runs again. Otherwise, fix the problem, then run `./nori up` again: it continues from the last ✅ and asks only for the keys the unfinished stages need. It never creates a second server. If the server it recorded is gone from Hetzner, it says so and asks again (with a new price) before creating one. The Hetzner token is only asked while there is no server yet or SSH isn't set up. See `troubleshooting.md`, "`./nori up` stopped".

### Claude app after Quick setup
Quick logs Claude in with a `claude setup-token` token. That works for the Telegram chat, but the Claude app / Remote Control (the session pool) needs a full **browser login** per area user, because long-lived tokens are inference-only. Once that login exists, the pool uses it automatically (it ignores the setup-token variable for that user), but this is still being tested. Until then the pool service stops with one clear line in its log (it does not restart-loop). The exact steps for Quick are **being tested**; for now use the step-by-step guide's Phase 5 login (section 5, `claude auth login --claudeai` for that area, then `claude remote-control` once) for that area.

**The Hetzner token isn't saved.** Use a separate Hetzner project for Nori, and delete the token in the console afterwards if you like.

**The last step is yours.** Only a human can answer the first-run questions of each Claude session. Answer folder trust → Enter, the CLAUDE.md imports → Yes, `Enable Remote Control?` → `y`, then detach with `Ctrl+b` then `d` (not Ctrl+d or /exit). Then run the command Nori prints, one per area:
```
ssh -t nori attach <area>
```
Closed the window or pressed Ctrl+c by accident? Nothing breaks: Claude keeps running on the server; run the same command again. `./nori up` prints these steps in your `LANGUAGES` language (Thai or English).

**GitHub login** is not automated. Once per area user (and per GitHub account it needs), on the server:
```
ssh -t nori sudo -iu <area> gh auth login -h github.com -p https -w
```
Check you're signed in as the right GitHub account before you approve the code (see the GitHub notes in Step 5).

Also yours: Tailscale on your phone and laptop (Step 4), then say "hi" to your bot.

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

Then fill in the basics: `OWNER_NAME`, `TIMEZONE`, `LANGUAGES`, `CHAT_ALLOWED_IDS` (open [@userinfobot](https://t.me/userinfobot) on the device where you use Telegram; on a computer the page shows "Open in Telegram" (or "Open in Web"): press it, then Start. It replies with your numeric id; use the link, searching shows lookalikes), `AREAS` (start with one), `GITHUB_ACCOUNTS`. Recommended: `WORK_BACKUP=true` with `BACKUP_REPO`, a private GitHub repo, for nightly encrypted backups of work that isn't pushed yet (see "Optional features"). Optional: copy `profile/USER.md.example` to `profile/USER.md` and write a few lines about yourself.

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
- Image: **Ubuntu 24.04 LTS** (the best tested). 26.04 LTS works too, but its new `sudo-rs` means limited sudo stays off there for now (step 3).
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
It sets timezone and hostname, installs packages (git, tmux, gh, Node 22, Bun, uv, Tailscale, Claude Code in the tested version with self-updates off; Docker only with Plane; Chromium only with the browser), creates your admin user and one user per area, sets up the firewall, turns off SSH passwords and root login, and copies the repo to the admin's `~/nori`. Running it again is safe.

**Before you close the root session**, open a second terminal and test: `ssh <ADMIN_USER>@<server IP>`. Then change `User root` to `User <ADMIN_USER>` in `~/.ssh/config`.
> ✅ **You should now see** `Bootstrap done. The remaining steps are MANUAL`, and the admin login works in the second terminal.
>
> ⚠️ **If it fails:**
> - **`missing or unsuitable terminal: xterm-ghostty`** (or kitty, WezTerm...): the server doesn't know your terminal. Quick fix: `export TERM=xterm-256color`. Real fix, from your 💻 laptop, installs it system-wide so every user gets it: `infocmp -x $TERM | ssh nori sudo tic -x -o /usr/share/terminfo -`
> - It stops with an error: read the last lines, fix, run `bash bootstrap.sh` again.

**Then give the admin a password and switch to limited sudo** (`ADMIN_SUDO=limited`, the default). Until the admin has a password, bootstrap keeps sudo passwordless for everything, so you can't lock yourself out. As the admin, in the second terminal:
```
sudo passwd <ADMIN_USER>              # choose a strong one and put it in your password manager
sudo bash ~/nori/bootstrap.sh         # run it once more: now it writes the limited rule
sudo -l                               # what you may do without a password
```
From now on `sudo` for anything else (`sudo apt ...`, `sudo tailscale up`) asks for this password. You log in with your SSH key as before; the password is only for sudo.
> ✅ **You should now see** `sudo for <ADMIN_USER>: limited` at the end of bootstrap, and `sudo -l` lists `(<your areas>) NOPASSWD: ALL` and `(root) NOPASSWD: /usr/local/sbin/nori-root`, next to `(ALL) ALL` (which asks the password). There is no `(ALL) NOPASSWD: ALL` line any more.
>
> ⚠️ **If it fails:**
> - **Bootstrap says `ADMIN_SUDO=limited needs a password`:** the `passwd` step didn't happen (or was for another user). Run it again, then bootstrap again.
> - **Bootstrap says `limited is only tested with classic sudo`:** Ubuntu 26.04 ships `sudo-rs` instead of classic sudo. Until the limited rule is tested there, bootstrap keeps passwordless sudo for everything (like `full`); nothing else changes. On 26.04 the rest of bootstrap and `nori-root` are also less tested than on 24.04, so 24.04 is the safer pick for now.
> - **You forgot the password:** sudo can't help you then, and root has no password either. Use your provider's console: Hetzner → your server → **Rescue** → enable rescue, reboot, log in to the rescue system with the shown password, then `mount /dev/sda1 /mnt && chroot /mnt passwd <ADMIN_USER>`, `reboot`. (The disk name may differ: `lsblk`.)
> - You'd rather keep it simple: `ADMIN_SUDO=full` in `nori.conf`, re-run bootstrap (the old passwordless-root behaviour).

*Why passwordless sudo at all:* `setup.sh`, cron and the Ops bot run things as the area users (`sudo -u <area>`) and a few fixed root actions through the helper `/usr/local/sbin/nori-root` (publish the read-only copy `/opt/nori`, link `attach`/`recall`, the Docker drop-in, read `ufw status`, and `/etc/gai.conf` with `PREFER_IPV4=true`), with nobody there to type a password. With `ADMIN_SUDO=limited` that is **all** that is passwordless, so a stolen Telegram account or a bug in the Ops bot doesn't hand out root. With `full`, whoever controls the admin account (or the Ops bot) controls the box. Logins are key-only either way. With Plane, the admin is in the `docker` group, which is as good as root whatever `ADMIN_SUDO` says.

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
In Telegram, open [@BotFather](https://t.me/BotFather) → `/newbot` → a name, and a username ending in `bot`. Make:
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
2. With the Ops bot: `/status`, `/progress`, `/ask is everything healthy?`. In a group: `/here`. The Ops bot also answers each command with a 👀 first; a 🔐 card shows just the command to approve (Allow / Deny).
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
| (with `OPS_BOT`) `/usage`, `/recall`, "still on it" pings, tap-to-answer buttons (`ask-owner`), liveness alert, `/allow <id> <name> <area>`, `/workgroup <area>` | no | yes | yes |
| `DIGEST` (daily digest) | false | true | true |
| `HANDOFF` (nightly handoff + fresh start) | true | true | true |
| `POOL_SESSIONS` / `POOL_CAPACITY` | false / 4 | true / 4 | true / 8 |
| `PREVIEWS` | false | true | true |
| `RECALL` | false | true | true |
| `BROWSER` | false | true | true |
| `PLANE` (tickets, `/board` `/peek`, ticket intake, weekly review; `/board` is built in the background, fast) | false | false | true |
| `PLANE_OFFSITE_BACKUP` | false | false | true once `BACKUP_REPO` is set |
| `WORK_BACKUP` (encrypted nightly backup of unpushed work; needs `BACKUP_REPO`) | false | false | false |
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
| `PREFER_IPV4` | `true`: outgoing connections try IPv4 first (`/etc/gai.conf`). Off in every preset; only for "bot replies arrive late", see `troubleshooting.md` |
| `ADMIN_SUDO` | `limited` (default): passwordless sudo only as the area users and for `nori-root`, the rest asks the admin's password (step 3). Needs classic sudo: on Ubuntu 26.04 (`sudo-rs`) it stays like `full` for now. `full`: passwordless root. Changed by re-running bootstrap |
| `CHAT`, `CHAT_ALLOWED_IDS` | chat platform (only `telegram`) and who may talk to the bots |
| `AREAS`, `AREA_<a>_*` | one always-on session per area; each area = own Linux user + own bot + prefix |
| `AREA_<a>_ASK_BEFORE_GITHUB_COMMENTS` | `true`: GitHub reviews, PR/issue comments, PR edit/close ask first in that area (teammates see them) |
| `AREA_<a>_WORK_BACKUP` | `false`: that area is left out of the work backup entirely (default `true` when `WORK_BACKUP=true`) |
| `GITHUB_ACCOUNTS` | `owner\|commit name\|commit email\|gh login`: git identity follows the repo owner |
| `OPS_BOT`, `OPS_ASK`, `OPS_GROUP_NAME` | the Ops bot, its `/ask`, the group label |
| `HANDOFF`, `HANDOFF_TIME` | nightly handoff note + fresh restart |
| `DIGEST`, `DIGEST_TIME`, `DIGEST_LANGUAGE` | daily repo digest (Ops chat, or your DM without the Ops bot) |
| `REMOTE_CONTROL` | also reachable from the Claude app |
| `AUTO_UPDATES`, `AUTO_REBOOT_TIME` | unattended security updates and the reboot window |
| `EXTRA_ASK_PERMISSIONS` | more commands that always ask first (`git push`, `gh pr merge` always do) |
| `CLAUDE_CODE_VERSION` | Claude Code version on the server. Empty (default): the one this Nori was tested with (`server/claude-code.version`). Or an exact version (`2.1.281`) to pin/roll back, or `stable` / `latest`. Claude Code never updates itself here; see "Updating Nori later" |
| `POOL_SESSIONS`, `POOL_CAPACITY` | extra Claude sessions per area, started from the Claude app / claude.ai/code |
| `PLANE`, `PLANE_WORKSPACE` | self-hosted Plane tickets |
| `BACKUP_REPO` | `owner/repo`: your private GitHub repo for the encrypted backups (the older name `PLANE_BACKUP_REPO` still works) |
| `WORK_BACKUP` | `true`: nightly encrypted backup of unpushed commits, uncommitted changes, `HANDOFF.md` and skills to `BACKUP_REPO`. Off by default (opt-in) |
| `PLANE_OFFSITE_BACKUP` | encrypted Plane backups to `BACKUP_REPO` |
| `PREVIEWS`, `PREVIEW_PORT_START` | `preview` command (tailnet only) |
| `RECALL` | search over past chats |
| `BROWSER` | headless browser MCP |
| `TAILNET_HOST` | filled in by `setup.sh` once Tailscale is up |

## Optional features
**Plane tickets (`PLANE=true`).** Re-run `sudo bash ~/nori/bootstrap.sh` (installs Docker and puts the admin in the `docker` group, which is root-equivalent: protect the admin account like root), make sure Tailscale is up, `./setup.sh` (creates `~/plane/plane.env` with generated secrets, binds Plane to the Tailscale IP only), then `cd ~/plane && docker compose --env-file plane.env up -d`. Open `http://<TAILNET_HOST>/god-mode/` on a tailnet device to create the instance admin, then a workspace whose slug equals `PLANE_WORKSPACE`, then your projects, and **one module per repo**. Create an API token in Plane (profile settings), then `~/nori/server/bin/set-token plane` and `./setup.sh --restart`. Add your projects/modules table to `local/rules/plane-projects.md`. The Ops bot then also offers `/board [area|project]`, `/peek <ID>`, `/ticket`, `/allow`, `/revoke`, `/people`, moves tickets to Done when a PR with the ticket id merges, and posts a weekly review. Map projects to areas with `AREA_<a>_PLANE_PROJECTS="ID1,ID2"`. The Plane API allows about 60 requests a minute. (Plane's first-run screens change between releases; follow Plane's own docs where they differ.)

**Encrypted backups of your work (`WORK_BACKUP=true`).** Your pushed code is safe on GitHub, but if the server dies, everything not pushed yet dies with it: commits on unpushed branches, uncommitted changes, each area's `HANDOFF.md`, skills the sessions saved in `~/.claude/skills/`. Every night, right after the nightly handoff (so tonight's `HANDOFF.md` is in it; without `HANDOFF` at `HANDOFF_TIME`), Nori packs these up per area, encrypts them, and pushes them to your backup repo. It only reads your repos, never changes them. Uncommitted files whose name usually means a secret are left out anyway, even though everything is gpg-encrypted: `.env`, `.env.*`, `*.pem`, `*.key`, `id_rsa*`, `id_ed25519*`, `id_ecdsa*`, `id_dsa*`, `*.p12`, `*.pfx`, `credentials.json`, `.netrc`, `.npmrc`, `.pypirc`, in any folder (listed in `SKIPPED.txt` as "excluded (looks like a secret)"; not an error). Setup:
1. On github.com create a new **private** repo, e.g. `nori-backups` (empty is fine).
2. In `nori.conf`: `BACKUP_REPO="you/nori-backups"` and `WORK_BACKUP=true` (any preset; it is off until you turn it on). Every area is included; leave one out with `AREA_<area>_WORK_BACKUP=false`. **Do that for an area with company code** (e.g. `AREA_work_WORK_BACKUP=false`), unless the backup repo belongs to the company: the backup uploads uncommitted files, and company code usually must not go to a personal repo.
3. The admin user must be logged in to GitHub: `gh auth login -h github.com -p https -w` (as the admin, with an account that can push to that repo).
4. `./setup.sh`. It creates `~/.backup-pass` (the passphrase). **Copy it into your password manager at once** (`cat ~/.backup-pass` in your own terminal, never into a chat); without it the backups are unreadable.
5. Test it: `~/.local/bin/work-offsite`, then look at the `work-snapshots` branch of your repo on GitHub.

The newest 7 nights per area stay on the server in `~/backups/work/` and on the branch `work-snapshots`, which is replaced every night, so the repo doesn't keep growing. Size limits: a file over 20 MB is left out, and so is anything that no longer fits once an area's backup reaches 90 MB (GitHub refuses files over 100 MB): uncommitted files, or even a repo's unpushed commits. The handoff note and skills always go in first. What was left out is listed in that repo's `SKIPPED.txt` and counts as a failure, so you hear about it. If it fails, you get a message in the Ops chat (or your DM); the log is `~/logs/work-backup.log`. Restore: `troubleshooting.md`.

**Encrypted Plane backups (`PLANE_OFFSITE_BACKUP=true`).** Create a **private** GitHub repo, set `BACKUP_REPO="you/that-repo"` (the same repo as the work backups), make sure the admin ran `gh auth login`. `setup.sh` creates `~/.backup-pass`; **copy that passphrase into your password manager at once**; without it the backups are unreadable. Restore: `troubleshooting.md`.

**Previews (`PREVIEWS=true`).** `preview start <name> -- <command>` inside a repo gives a link on the tailnet. Dev/test config only.

**Recall (`RECALL=true`).** An index of past chats and handoffs per area, refreshed every 15 minutes; `recall "words"`.

**Browser (`BROWSER=true`).** Re-run bootstrap (installs Chromium into `/opt/ms-playwright`), `./setup.sh --restart`. Screenshots land in `~/shots/<area>/`.

**A second area.** Add the name to `AREAS`, add `AREA_<name>_PREFIX/_DESCRIPTION/_BOT` (and `AREA_<name>_ASK_BEFORE_GITHUB_COMMENTS=true` for shared/company repos), create another bot, then: `sudo bash ~/nori/bootstrap.sh` (creates the user, installs Claude, adds it to the admin's sudo rule), step 5 for the new user, `set-token <name>`, `./setup.sh --restart`. The new session can't read the other area's files. Plane tickets (one shared API key), `nori.conf` and the profile are shared by all areas, so put no secrets in them.
> ⚠️ **A "work" area talks through Telegram too:** company code, diffs and screenshots go through Telegram, and bot chats are **not end-to-end encrypted**. Check your employer's policy before you set it up. For sensitive work, use Remote Control / the Claude app (pool sessions) instead of the chat bot.

## Updating Nori later
Your copy of Nori is the source of truth. On the laptop `git pull` (your `nori.conf`, `profile/USER.md`, `local/` are gitignored, never overwritten), then `rsync -a --exclude .git --exclude generated ./ nori:~/nori/` and on the server `cd ~/nori && ./setup.sh` (`--restart` if rules/settings changed). After the rsync, the Ops bot's `/apply` runs `setup.sh` for you. It never pulls: the server copy has no `.git`, so a push to the repo can't change the server (the admin runs `setup.sh` and has some passwordless sudo). If an update changed the root helper, `setup.sh` stops and asks you to re-run `sudo bash ~/nori/bootstrap.sh` once.

**Claude Code updates are a deliberate step.** Nori leans on fairly new Claude Code features (channels, Remote Control, the pool, the screen text `/progress` reads), so a surprise update could break a running server. `bootstrap.sh` installs the version Nori was tested with (`server/claude-code.version`) and turns self-updates off (`DISABLE_AUTOUPDATER` in each user's settings and in `/etc/claude-code/managed-settings.d/50-nori.json`).
- **Upgrade:** set `CLAUDE_CODE_VERSION="2.1.xyz"` in `nori.conf` (or pull a newer Nori whose `server/claude-code.version` changed), copy it to the server, then `./setup.sh` (runs `claude install <version>` for the admin and every area user) and `./setup.sh --restart` (the sessions start on the new version). `stable` / `latest` follow that channel instead: each `./setup.sh` installs whatever it is then.
- **Roll back:** set `CLAUDE_CODE_VERSION` to the old version (it's in `server/claude-code.version` of the older Nori, or in the drift alert), same two steps.
- **No silent downgrades:** if a user already runs a *newer* version than `server/claude-code.version`, `setup.sh` and `bootstrap.sh` keep it and say so. Going down only happens when `CLAUDE_CODE_VERSION` in `nori.conf` asks for it. To keep the newer one and silence the note, set `CLAUDE_CODE_VERSION` to it.
- `./setup.sh --check` and the Ops bot's `/status` show the versions. If one changes on its own, the Ops bot alerts once ("Claude Code is not the wanted version"): an older one is fixed by `./setup.sh`; a newer one is kept until you choose (see above). See `troubleshooting.md`.

> ⚠️ **`git pull` refuses: "Your local changes would be overwritten"** although you changed nothing: `setup.sh` made a script executable that isn't executable in git (a file-mode change). Fix it at the source, in your repo on the laptop: `git update-index --chmod=+x <file>`, commit, push. On the server, `git diff` shows `old mode 100644 / new mode 100755`; `git checkout -- <file>` then pull again.

## Upgrading
What changed in the batch of 2026-10-09, and what to do (one time, as in "Updating Nori later"):
- **Ops bot:** reacts with 👀 to every command from you or a member. The 🔐 card shows only the command (no old screen lines or dividers, up to 700 characters). `/board` has a 🍙 header, asks Plane faster (0.2 s between projects) and is built in the background, so other commands don't wait for it. The session rules now say "tap Allow on the Ops card" instead of "check your DM" when `PERM_CARDS` is on.
- **New, optional flag `PREFER_IPV4`** (default `false`): the fix for late bot replies, see `troubleshooting.md`. The root helper `nori-root` is now version 2 (it knows `gai-conf`).

To upgrade an existing server:
1. `git pull` on the laptop, then copy to the server: `rsync -a --exclude .git --exclude generated ./ nori:~/nori/`.
2. On the server: `sudo bash ~/nori/bootstrap.sh` once (asks your password with `ADMIN_SUDO=limited`; installs the new root helper; `setup.sh` stops and tells you to if you skip it).
3. `cd ~/nori && ./setup.sh --restart` (restarts the Ops bot and the sessions so they get the new code and rules; it wipes the sessions' chat).
4. Optional: if replies come late, set `PREFER_IPV4=true` and run `./setup.sh` again.

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
| `generated/claude/settings.admin.partial.json` | merged into the admin's `~/.claude/settings.json` (no self-updates) |
| `server/claude/managed-settings.json` | `/etc/claude-code/managed-settings.d/50-nori.json` (root, by `bootstrap.sh`): no self-updates, push/merge always ask |
| `server/claude-code.version` | the Claude Code version installed for every user (unless `CLAUDE_CODE_VERSION` says otherwise) |
| `generated/chat/access.<a>.json` | merged into `~/.claude/channels/telegram-<a>/access.json` |
| `generated/systemd/*` | `~/.config/systemd/user/` (`claude@`, `claude-pool@` for areas; `ops-bot` for the admin) |
| `generated/crontab` | the admin's crontab |
| `server/bin/work-backup` | run from `/opt/nori/server/bin/` as each area user (with `WORK_BACKUP`) |
| (backups) | `~/backups/work/<area>-YYYYMMDD.tar.gz.gpg` (admin, newest 7 per area) → branch `work-snapshots` of `BACKUP_REPO`; Plane dumps in `~/backups/plane/` → `plane/` on its default branch; passphrase `~/.backup-pass` |
| `plane/*` | `~/plane/` (only with `PLANE`) |
