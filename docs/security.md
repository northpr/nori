# Security in detail

The short version is in the [README](../README.md#-security-at-a-glance). To report a problem privately, see [SECURITY.md](../SECURITY.md).

## Who can do what
- **Your Telegram account** is the remote control. Whoever gets into it can tell the area sessions to run code as the area users, approve their 🔐 pushes and merges, and use the Ops bot (`/apply` re-runs `setup.sh` as the admin, `/restart <area>`). **Turn on Telegram's two-step verification** (Settings → Privacy and Security → Two-Step Verification, a cloud password).
- **The admin account** (`ADMIN_USER`, your SSH login) runs `setup.sh`, cron and the Ops bot. With `ADMIN_SUDO=limited` (the default) it may act as the area users and run the small root helper `nori-root` without a password; anything else as root asks for the admin's password. So a stolen Telegram account or a bug in the Ops bot doesn't mean passwordless root. `ADMIN_SUDO=full` is passwordless root for everything. `limited` needs classic sudo; on Ubuntu 26.04 (`sudo-rs`) bootstrap keeps `full` until it's tested there. With `PLANE=true` the admin is also in the `docker` group, which is as good as root; `limited` doesn't change that.
- **Area users** run the Claude sessions: no sudo, and they can't read each other's or the admin's files.

## More
- Tokens live only in files on the server (written with a hidden prompt via `set-token`), never in git, `nori.conf` or a chat.
- Firewall closed except SSH and the Tailscale interface.
- Areas are separated for projects, chats, Claude state and `local/` rules. They are **not** separated for Plane: all areas share one Plane API key, so every session can read and change every project's tickets. `nori.conf` and the profile in `/opt/nori` are readable by every area user, so keep secrets out of them. If a colleague shares your server, give them their own server or Plane workspace.
- **A "work" area sends company code, diffs and screenshots through Telegram**, and Telegram bot chats are **not end-to-end encrypted**. Check your employer's policy first. For sensitive work use Remote Control / the Claude app instead of a chat bot.
- `git push`, `gh pr merge` and any command in `EXTRA_ASK_PERMISSIONS` are caught by ask rules (the push/merge ones also in root-owned managed settings, which a session can't edit away), and a `push-guard` hook also asks for `git -C repo push`, `gh api ... merge` and similar spellings. A script Claude writes that pushes internally is not inspected. Claude Code's docs say explicit ask rules prompt in every permission mode, including the auto mode pool sessions use. (Plus GitHub comments/reviews in areas with `ASK_BEFORE_GITHUB_COMMENTS=true`.) No production secrets belong on the box.
