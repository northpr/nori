# Troubleshooting

## The chat bot doesn't answer
1. **No 👀 reaction** on your message: the bot isn't running. In the Ops chat send `/restart <area>`, wait ~20 s, say "hi" again. Without the Ops bot: `ssh <server> 'sudo -u <area> XDG_RUNTIME_DIR=/run/user/$(id -u <area>) systemctl --user restart claude@<area>'`. The usual cause is that something started a **second** bot instance (see the warning below).
2. **👀 but no reply**: Claude is busy or waiting for a 🔐 permission. Look for a permission message in your DM with the area bot, or attach: `ssh -t <server> attach <area>` (leave with `Ctrl+b` then `d`). `/progress` in the Ops chat shows what each session is doing.
3. Is the plugin process alive? `ssh <server> 'pgrep -af "bun .*telegram"'`.
4. Nothing at all, even in the Ops chat: is your numeric id in `CHAT_ALLOWED_IDS`? Run `./setup.sh` again after changing it. `/whoami` to the Ops bot prints your id.
5. The session never starts: `ConditionPathExists` in the unit needs `~/.claude/channels/telegram-<area>/.env`. Run `set-token <area>`, then `./setup.sh`.

## The bot doesn't answer (no 👀)
You're probably writing from a Telegram account that isn't in `CHAT_ALLOWED_IDS`. It's the account you chat **from** that counts, not the one that created the bot. Get its id from [@userinfobot](https://t.me/userinfobot), add it to `CHAT_ALLOWED_IDS` (comma separated), copy to the server and run `./setup.sh`. Ignore the bot's "To pair" reply to /start.

## `./nori up` stopped
It prints `✗ <stage>: …`. Fix that, then run `./nori up` again: it continues from the last ✅ and never creates a second server.
- **"…are sold out in …"**: Hetzner has none of those types there right now. Try `./nori up --type <type> --location <location>` (another EU location, or switch Arm ↔ x86). It shows that pair's price and creates nothing unless you type `yes`.
- **A key is refused**: it just asks again. Bot tokens are checked with Telegram, so a typo or no internet shows here. Get a fresh one from @BotFather (`/token`) or the provider's page in the checklist.
- **"The server didn't answer on SSH within 5 minutes"**: the new server may still be booting, or your network blocks port 22. Check it's running in the Hetzner console, then re-run. If SSH says the host key changed (server recreated with the same IP): `ssh-keygen -R <ip> -f ~/.ssh/nori_known_hosts`.
- **"~/.ssh/config already has your own 'Host nori'"**: Nori won't touch a `Host nori` you wrote yourself. Rename or remove it, then re-run. (Its own block sits between `# >>> nori >>>` and `# <<< nori <<<`.)
- **"generated/up-state.json is for <ip>, not <host>"**: that state file belongs to another server. To start over with this one, move the file away, then re-run.
- **It stopped half way**: re-run `./nori up`. It continues from the last ✅ stage.
- **`Hetzner: permission denied`** at `create`: the token is read-only (Hetzner's default). Make a new one with **Read & Write**, answer `y` to "Re-enter … and retry" and paste it.

## Bot replies arrive late (up to a minute)
**Symptom:** the bot (usually the Ops bot) answers, but sometimes a minute late. Most replies are fast.

**Cause:** your server's IPv6 route to Telegram is flaky: now and then a connection over IPv6 hangs. Python tries IPv6 first, so it waits for the hang before it falls back to IPv4. (Some providers have this; it is not Nori or Telegram being slow.)

**Test it** on the server (15 tries each, counts the connects slower than 2 seconds):
```
for v in 4 6; do
  n=0
  for i in $(seq 15); do
    t=$(curl -"$v" -s -o /dev/null -m 15 -w '%{time_total}' https://api.telegram.org || echo 15)
    awk -v t="$t" 'BEGIN { exit !(t > 2) }' && n=$((n+1))
  done
  echo "IPv$v: $n of 15 slower than 2 s"
done
```
If IPv6 has slow ones (say 1 or more) and IPv4 has none, this is it.

**Fix:** in `nori.conf` set `PREFER_IPV4=true`. Then (if you updated Nori since you set the server up, run `sudo bash ~/nori/bootstrap.sh` once first; see "Upgrading" in the setup guide) `./setup.sh`. That installs `/etc/gai.conf` (one line: `precedence ::ffff:0:0/96  100`) and everything on the box tries IPv4 first. Restart the Ops bot so it picks it up: `./setup.sh --restart`. Run the test again to check.

**Is it safe?** It only changes the *order* in which outgoing connections try addresses. IPv6 still works as a fallback. Nothing inbound changes: no firewall (ufw), Tailscale or port changes.

**Undo:** set `PREFER_IPV4=false` (or delete the line) and run `./setup.sh`. It removes `/etc/gai.conf` only when it is exactly Nori's file, and puts your old one back if Nori replaced it (saved as `/etc/gai.conf.nori-orig`). A `gai.conf` you wrote yourself is never touched.

## The session is up but never answers, right after the first start
It is probably waiting on a one-time prompt only a human may answer: folder trust, "Allow external CLAUDE.md imports?" (the rules import your `USER.md`), or "Enable Remote Control? (y/n)". `ssh -t <server> attach <area>`, answer it (Enter / `y`), leave with `Ctrl+b` then `d`.

## WARNING: a second bot instance kills the first
A chat bot token can be polled by only one process. **Never run `claude mcp list`, or any extra `claude` process, on the server without `--strict-mcp-config`** once the token exists: it loads the chat plugin, starts a second bot, and the always-on session's bot goes silent until it restarts. Fix: `/restart <area>`. Do the first `claude` login/trust steps *before* putting the token on the box.

## Commit blocked: "author must be ..."
The pre-commit guard found that the author doesn't match the repo owner. For a new GitHub owner or organisation add a line to `GITHUB_ACCOUNTS` in `nori.conf` (`owner|name|email|gh login`), then `./setup.sh`. Repos from unknown owners have no identity on purpose.

## `gh` says the account is not logged in
The `gh` wrapper picks the account from the repo's remote owner. Log that account in once for that Linux user: `gh auth login -h github.com -p https -w`.

## Claude asks to log in again
`ssh -t <server>`, (`sudo -iu <area>`), `claude auth login --claudeai`; it prints a link, open it and paste the code back. Then `/restart <area>`.

## Ops alert "Claude Code is not the wanted version" / upgrading Claude Code
Claude Code doesn't update itself on the server (`DISABLE_AUTOUPDATER`); every user should run the version in `CLAUDE_CODE_VERSION`, or, if that is empty, `server/claude-code.version`. The alert means a user's `claude --version` differs: someone ran `claude update` / `claude install`, or an old setting let it update. If it's **older** than wanted: `cd ~/nori && ./setup.sh` (installs the wanted version again), then `./setup.sh --restart`. If it's **newer**, `setup.sh` won't downgrade on its own: keep it with `CLAUDE_CODE_VERSION=<that version>` in `nori.conf`, or go back with `CLAUDE_CODE_VERSION=<wanted>` and `./setup.sh`, `./setup.sh --restart`.
- **Upgrade on purpose:** set `CLAUDE_CODE_VERSION="<new version>"` (or pull a newer Nori), `./setup.sh`, `./setup.sh --restart`. Then check `/progress` and that the bot answers.
- **Something broke after an upgrade** (the session won't start, "unknown option", `/progress` always says idle): roll back. Set `CLAUDE_CODE_VERSION` to the version that worked, `./setup.sh`, `./setup.sh --restart`.
- With `stable` / `latest` there is no drift alert; `/status` only shows the versions.
- `./setup.sh` warns that `/etc/claude-code/managed-settings.d/50-nori.json` is missing or old: run `sudo bash ~/nori/bootstrap.sh` (as root) once.

## Something changed on the box and I'm not sure what
`ssh <server> '~/nori/setup.sh --check'` lists every difference from the repo + `nori.conf`. Files replaced by `setup.sh` are backed up in `~/.cfg-backup/<timestamp>/`.

## Terminal looks broken / "missing or unsuitable terminal"
`missing or unsuitable terminal: xterm-ghostty` (or kitty, WezTerm...) means the server doesn't know your terminal. Quick fix for this login: `export TERM=xterm-256color`. If your terminal (Ghostty, kitty, ...) is unknown to the server, `attach` falls back to `xterm-256color` (it checks as the area user, who can't see the admin's `~/.terminfo`). For full colors and keys, install your terminal's terminfo **system-wide** from your laptop, e.g. for Ghostty: `infocmp -x xterm-ghostty | ssh <server> sudo tic -x -o /usr/share/terminfo -` (generally: `infocmp -x $TERM | ...`).

## Pool log says "claude-pool: the Claude app / Remote Control needs a browser login for this user"
Quick setup logs Claude in with a `claude setup-token` token, which Remote Control refuses ("requires a full-scope login token"). The pool stops on purpose (exit 78, no restart loop). Telegram is not affected. To use the Claude app, give that area user a full browser login (setup guide, "Claude app after Quick setup", for now Phase 5's `claude auth login --claudeai` as that user), then `systemctl --user restart claude-pool@<area>` as that user.

## After `attach` the screen shows "[exited]" or "Claude stopped"
You pressed Ctrl+d or typed `/exit`: that quits Claude. It restarts by itself in about 10 s with a fresh conversation; attach again then. To leave without stopping it, use Ctrl+b, release, then d.

## Pool sessions don't show up in the Claude app
- `sudo -u <area> XDG_RUNTIME_DIR=/run/user/$(id -u <area>) systemctl --user status claude-pool@<area>` and its `journalctl --user -u claude-pool@<area>`.
- It keeps restarting: that area user hasn't accepted Remote Control yet. Run `claude remote-control` once as that user in `~/projects/<area>`, answer `y`, Ctrl+C (setup guide section 5). The folder stays held for 1–2 minutes after a manual run; the service comes back by itself.
- Too many at once: each session uses a few hundred MB. The Ops bot alerts at 85% memory; close idle pool sessions or lower `POOL_CAPACITY`.

## Ops alert "memory < 85%"
Used memory crossed 85%. `/ask what is using memory?` in the Ops chat, `/progress`, or `free -h` / `top` on the server. Usual causes: many pool sessions, a forgotten preview or dev server, Plane plus the browser on a 4 GB box.

## Tailscale link doesn't open / Plane or previews not reachable
- The device must be **Connected** to the same tailnet (check the Tailscale app; some people have several).
- `tailscale status` on the server; `tailscale ip -4`.
- Plane: `cd ~/plane && docker compose --env-file plane.env ps` (all services running, `migrator` exited 0); start with `... up -d`. After a reboot Docker waits for Tailscale (drop-in installed by `setup.sh`); if Plane is down anyway: `sudo systemctl restart docker`.
- ufw must allow the tailnet: `sudo ufw status | grep tailscale0` (else `sudo ufw allow in on tailscale0`).

## sudo asks for a password
That's `ADMIN_SUDO=limited` working: only running as the area users and the root helper `nori-root` are passwordless; everything else as root (`sudo apt ...`, `sudo ufw ...`) asks the admin's password (set in setup guide step 3). Type it. Forgot it: provider console → rescue mode, `chroot` into the disk and `passwd <ADMIN_USER>` (setup guide step 3, "If it fails"). If **`setup.sh` or the Ops bot's `/apply`** stops at a password or says `sudo: a password is required`, the sudo rule doesn't match this repo (new area, old bootstrap): re-run `sudo bash ~/nori/bootstrap.sh`.

## setup.sh: "nori-root ... missing or not allowed by sudo" / "outdated, re-run bootstrap"
`setup.sh` does its few root actions through `/usr/local/sbin/nori-root`, a root-owned copy that only bootstrap installs (a script the admin could edit would give the admin root). After an update changed it, or on a server bootstrapped before it existed, run once: `sudo bash ~/nori/bootstrap.sh` (it asks for your password with `ADMIN_SUDO=limited`), then `./setup.sh` again. Check: `sudo -n nori-root version` prints the same number as `NORI_ROOT_VERSION` in `~/nori/server/sbin/nori-root`.

## Locked out of SSH
Use your provider's web console/rescue mode. Re-add your key to `~<ADMIN_USER>/.ssh/authorized_keys`; the hardening drop-in is `/etc/ssh/sshd_config.d/10-nori.conf`.

## Restore Plane from the off-site backup
Encrypted dumps live in your private `BACKUP_REPO` (`plane/plane-YYYYMMDD.sql.gz.gpg`). The passphrase is `~/.backup-pass` on the server; **keep another copy in your password manager**.
1. Decrypt: `gpg --batch --pinentry-mode loopback --passphrase-file <file with the passphrase> -d plane-YYYYMMDD.sql.gz.gpg | gunzip > plane.sql`
2. Restore into a fresh Plane: `cd ~/plane && docker compose --env-file plane.env exec -T plane-db sh -c 'PGPASSWORD=$POSTGRES_PASSWORD psql -h 127.0.0.1 -U $POSTGRES_USER $POSTGRES_DB' < plane.sql`

## Restore your work from the off-site backup (`WORK_BACKUP`)
The branch `work-snapshots` of your private `BACKUP_REPO` holds one file per area and night: `<area>-YYYYMMDD.tar.gz.gpg`. You need the passphrase (`~/.backup-pass` on the old server, or your password manager). Run this on any machine with `git` and `gpg`, e.g. the new server as the area user. Below, replace `main` with your area's name and `my-app` with the repo.
1. Get the files: `cd ~ && git clone --branch work-snapshots --single-branch https://github.com/<you>/<backup-repo>.git nori-restore && cd nori-restore`
2. Decrypt and unpack the newest one for an area (asks for the passphrase): `gpg -d main-YYYYMMDD.tar.gz.gpg | tar xz`
   (or without a prompt: `gpg --batch --pinentry-mode loopback --passphrase-file <file with the passphrase> -d main-YYYYMMDD.tar.gz.gpg | tar xz`)
3. Look around: `cat main/MANIFEST.txt` lists every repo and what was saved. Paths are the area name, then the path under `~/projects`: e.g. `main/main/my-app/` for `~/projects/main/my-app`. Each repo folder can have:
   - `unpushed.bundle`: the commits that were on no remote: branches, tags, a detached `HEAD` and the newest stash (`refs/stash`; older stashes are only listed in `STATUS.txt`). For a repo without a remote: its whole history. `git bundle list-heads <file>` shows what is in it,
   - `files/`: uncommitted and untracked files, as they were on disk,
   - `STATUS.txt`: the branch and `git status` at that moment; `SKIPPED.txt`: what was left out and why (a file or the bundle over a size limit, a file that changed while it was read).
4. Get the commits back into a fresh clone:
   ```
   cd ~ && git clone https://github.com/<owner>/<repo>.git my-app && cd my-app
   git fetch ~/nori-restore/main/main/my-app/unpushed.bundle 'refs/heads/*:refs/heads/restored/*'
   git branch -a                     # restored/<branch> = your branches with the unpushed commits
   git checkout -b <branch> restored/<branch>
   ```
   If that branch exists already (e.g. `main`): `git checkout <branch> && git merge --ff-only restored/<branch>`.
   A repo that had no remote: `cd ~ && git init my-app && cd my-app`, the same `git fetch` line, then `git checkout -b main restored/main`.
   Tags, a detached `HEAD` and the stash, if `list-heads` shows them (same folder; fetch only the ones it lists):
   ```
   git fetch ~/nori-restore/main/main/my-app/unpushed.bundle 'refs/tags/*:refs/tags/*'
   git fetch ~/nori-restore/main/main/my-app/unpushed.bundle HEAD:refs/heads/restored/detached-head
   git fetch ~/nori-restore/main/main/my-app/unpushed.bundle refs/stash:refs/heads/restored/stash
   git stash apply restored/stash    # on the branch the stash was made on
   ```
5. Copy the uncommitted work back, on the branch from `STATUS.txt`: `cp -a ~/nori-restore/main/main/my-app/files/. .` then `git status`.
6. The handoff note and skills, as the area user: `cp ~/nori-restore/main/main/HANDOFF.md ~/projects/main/` and `cp -a ~/nori-restore/main/.claude/skills/. ~/.claude/skills/`.

## Work backup: "NOT pushed: work-snapshots is the default branch" / "isn't ours"
`work-offsite` replaces the branch `work-snapshots` every night with a force push, so it checks first. If that branch is your backup repo's default branch (the repo was created that way, or `main` was deleted), Plane dumps would land on it and be wiped: on GitHub open the repo, Settings > General > Default branch, and pick `main` (create `main` first if it is gone). If the branch holds anything other than `*.tar.gz.gpg` files, it isn't Nori's: rename it on GitHub. Then run `~/.local/bin/work-offsite` again. Until then the snapshots stay in `~/backups/work/`.

## Cron jobs did not run
`crontab -l` (as the admin) should list them; logs are in `~/logs/`. Times use the server's timezone (`timedatectl`).

## Can't log in to a brand-new server
`Permission denied (publickey)` right after creating it: the server has a different public key than the one your laptop offers, or the key has a passphrase you no longer know. Ubuntu doesn't allow root password logins over SSH. Easiest fix: delete the server and create it again with the right key (`cat ~/.ssh/nori_ed25519.pub`). After recreating, `ssh-keygen -R <ip>` clears the old host key warning.

## Hetzner says "limited availability"
The cheap types (CAX/CX) sell out per location. Pick another EU location, or switch Arm ↔ x86 (CAX21 ↔ CX33).

## Tailscale: "already exists" / laptop is in another tailnet
Your laptop is logged in to a different tailnet (e.g. your company's). In the Tailscale app: account menu → add another account, log in with the one the server uses, switch to it. Only one tailnet is active at a time.

## GitHub login went to the wrong account / org repos say "not found"
`gh auth login -w` approves whoever is signed in on the browser page. Check the account before you approve; if wrong: `gh auth logout -h github.com -u <login>` and log in again. For an org with SSO, authorize the GitHub CLI for that org (on the approval page, or github.com → Settings → Applications → Authorized OAuth Apps → GitHub CLI).

## Claude refuses to run a command ("auto mode", "blocked", "needs approval")
Claude Code's safety check refuses some installs, `sudo` commands and answering prompts on your behalf. That's intended. Run the command yourself: in a Claude session, type it with `!` in front (`! sudo tailscale up`), or in a normal terminal.

## `git pull` blocked although you changed nothing
"Your local changes would be overwritten": usually a **file-mode change** (`git diff` shows `old mode 100644` / `new mode 100755`), because `setup.sh` makes scripts executable. On the server: `git checkout -- <file>` and pull again. For good, in your repo: `git update-index --chmod=+x <file>`, commit, push.

## Git identity guard doesn't run in a repo with Husky / lefthook
The global hooks path runs the identity guard first and then hands every hook to the repo's own hook. But a repo that sets its own local `core.hooksPath` (Husky, lefthook) overrides the global one, so the guard doesn't run there. The main protection still applies: `user.useConfigOnly` (git refuses to commit without a configured identity) plus the per-owner `includeIf` identity. Check with `git config --show-origin user.email` in that repo before committing.

## No Ops bot (PRESET=starter / OPS_BOT=false)
- Restart a session: `ssh -t <server>`, then `sudo -u <area> XDG_RUNTIME_DIR=/run/user/$(id -u <area>) systemctl --user restart claude@<area>`. All sessions: `cd ~/nori && ./setup.sh --restart`.
- Look inside: `ssh -t <server> attach <area>`.
- No health alerts and no `/ask` in this mode. The digest (if `DIGEST=true`) and the nightly report come in your DM from your area bot; if they don't, check `~/logs/morning-summary.log` and that the area's token exists (`set-token <area>`).
