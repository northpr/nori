# Troubleshooting

## The chat bot doesn't answer
1. **No 👀 reaction** on your message: the bot isn't running. In the Ops chat send `/restart <area>`, wait ~20 s, say "hi" again. Without the Ops bot: `ssh <server> 'sudo -u <area> XDG_RUNTIME_DIR=/run/user/$(id -u <area>) systemctl --user restart claude@<area>'`. The usual cause is that something started a **second** bot instance (see the warning below).
2. **👀 but no reply**: Claude is busy or waiting for a 🔐 permission. Look for a permission message in your DM with the area bot, or attach: `ssh -t <server> attach <area>` (leave with `Ctrl+b` then `d`). `/progress` in the Ops chat shows what each session is doing.
3. Is the plugin process alive? `ssh <server> 'pgrep -af "bun .*telegram"'`.
4. Nothing at all, even in the Ops chat: is your numeric id in `CHAT_ALLOWED_IDS`? Run `./setup.sh` again after changing it. `/whoami` to the Ops bot prints your id.
5. The session never starts: `ConditionPathExists` in the unit needs `~/.claude/channels/telegram-<area>/.env`. Run `set-token <area>`, then `./setup.sh`.

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

## Something changed on the box and I'm not sure what
`ssh <server> '~/nori/setup.sh --check'` lists every difference from the repo + `nori.conf`. Files replaced by `setup.sh` are backed up in `~/.cfg-backup/<timestamp>/`.

## Terminal looks broken / "missing or unsuitable terminal"
`missing or unsuitable terminal: xterm-ghostty` (or kitty, WezTerm...) means the server doesn't know your terminal. Quick fix for this login: `export TERM=xterm-256color`. If your terminal (Ghostty, kitty, ...) is unknown to the server, `attach` falls back to `xterm-256color` (it checks as the area user, who can't see the admin's `~/.terminfo`). For full colors and keys, install your terminal's terminfo **system-wide** from your laptop, e.g. for Ghostty: `infocmp -x xterm-ghostty | ssh <server> sudo tic -x -o /usr/share/terminfo -` (generally: `infocmp -x $TERM | ...`).

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

## Locked out of SSH
Use your provider's web console/rescue mode. Re-add your key to `~<ADMIN_USER>/.ssh/authorized_keys`; the hardening drop-in is `/etc/ssh/sshd_config.d/10-nori.conf`.

## Restore Plane from the off-site backup
Encrypted dumps live in your private `PLANE_BACKUP_REPO` (`plane/plane-YYYYMMDD.sql.gz.gpg`). The passphrase is `~/.backup-pass` on the server; **keep another copy in your password manager**.
1. Decrypt: `gpg --batch --pinentry-mode loopback --passphrase-file <file with the passphrase> -d plane-YYYYMMDD.sql.gz.gpg | gunzip > plane.sql`
2. Restore into a fresh Plane: `cd ~/plane && docker compose --env-file plane.env exec -T plane-db sh -c 'PGPASSWORD=$POSTGRES_PASSWORD psql -h 127.0.0.1 -U $POSTGRES_USER $POSTGRES_DB' < plane.sql`

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
