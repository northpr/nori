# `./nori up`: Quick setup (design)

Date: 2026-10-09 · Ticket: SRV-18 (sub-project 1 of 4, with the token logins of sub-project 3 merged in) · Status: approved in chat, spec waiting for review

## Why
Setting up a Nori server is the hard part for new users. Today it takes nine manual steps: buy a server in the browser, make an SSH key and `~/.ssh/config` entry, scp the repo, run bootstrap as root, log in to Tailscale and to Claude on the server, then the bot tokens and `setup.sh`. Each step is a place to get stuck. The goal is to make it **fewer steps, with none of them on the server**, while keeping the guided step-by-step flow for people who want to learn or have an unusual setup.

Success means a beginner with a Hetzner account and the keys from the list below gets a bot that answers "hi" by running one command and waiting about 15 minutes, without opening an SSH session themselves.

## Out of scope (later sub-projects of SRV-18)
- `./nori doctor` (check everything and give the next step): sub-project 2.
- `./nori init` (write `nori.conf` by questions): sub-project 4. The guided Claude setup already writes `nori.conf`.
- Plane's first-run UI (admin, workspace, API key). With `PLANE=true`, Quick finishes everything else and then points to the existing Plane steps.
- Providers other than Hetzner for creating servers. They use the "existing server" path.
- `./nori down` (delete a server). It isn't needed, because the Hetzner token isn't kept.

## The user's choice (guided setup, Phase 0)
The guided setup (`CLAUDE.md`) first asks:

> **How do you want to set up?**
> 1. ⚡ **Quick:** uses **Hetzner Cloud** (Nori creates the server for you through its API), **Tailscale**, your **Claude subscription** and a **Telegram bot**. You paste the keys at the start, then Nori does the rest in about 15 min.
> 2. 🧭 **Step by step:** it might take longer, but you're in control. Nori explains each step and you do it yourself, with help.
> 3. 🖥 **I already have a server:** any Ubuntu 24.04+ VPS. Give its IP and Nori sets it up from there.

Option 2 is today's flow, unchanged. Options 1 and 3 run `./nori up` (3 with `--host <ip>`). `nori.conf` is still written first, in Phase 0, by the guided chat or by hand.

## Flow (Quick)
1. **Checklist.** Nori lists the keys with a link for each and one line on where to click:
   - **Hetzner API token** (Read & Write), from a new Hetzner project named e.g. `nori`. Not needed for option 3.
   - **Tailscale auth key** (one-off, pre-approved).
   - **Claude token** from `claude setup-token`, run on the laptop.
   - **One Telegram bot token per area**, plus **one for the Ops bot** when `OPS_BOT=true`, all from BotFather.
   - **An admin password** the user chooses, to keep in their password manager. It is set with `chpasswd` over stdin, so the second bootstrap run can switch on `ADMIN_SUDO=limited` without a separate manual step.
2. **`./nori up` asks for every key at the start**, each at a hidden prompt, and checks each one straight away:
   - Hetzner token: one authenticated API call.
   - Bot tokens: Telegram `getMe`. It also prints the bot's username so the user can see it's the right bot.
   - Tailscale key: a format check (`tskey-auth-…`).
   - Claude token: a format check.

   A bad key fails here, not ten minutes in.
3. **Price confirmation.** It picks the server type and location (below), fetches the **live price** from the Hetzner API, and asks `Create "nori" (CAX21, Falkenstein, €X.XX/month)? [yes/no]`. Nothing that costs money happens without `yes`.
4. **Unattended stages**, one progress line each:
   1. `create`: upload the SSH key, then create the server (Ubuntu 24.04, public IPv4).
   2. `ssh`: wait until SSH answers. Pin the host key and write the `Host nori` block.
   3. `copy`: copy the repo and `nori.conf` to `/root/nori`.
   4. `bootstrap`: run `bash bootstrap.sh` as root. Root login is turned off at the end, as today.
   5. `tailscale`: `tailscale up` with the auth key.
   6. `admin`: set the admin password, then run bootstrap again, so `ADMIN_SUDO=limited` takes effect.
   7. `claude`: store the Claude token for the admin and every area user, and install the chat plugin per area user from `claude-plugins-official`.
   8. `prompts`: pre-answer the one-time session prompts (folder trust, external CLAUDE.md imports, "Enable Remote Control?"). Only where the probe shows a supported settings file can do it. Otherwise, see below.
   9. `tokens`: `set-token` for each area bot and the Ops bot.
   10. `setup`: run `./setup.sh --restart` as the admin.
5. **Done:** `✅ Send "hi" to @<bot>.` Nori offers to check that the bot answers (it watches for the session's reply in the Ops bot / journal).

## What Quick does not automate (said plainly at the end)
- **GitHub login** (`gh auth login` per Linux user and account): a browser device flow on the server. The bot answers without it. Quick ends with a short "to let it push to GitHub, run …" step, as in Phase 5 today.
- **Any one-time prompt** the probe finds can't be pre-answered safely. Quick then ends with "attach once and press Enter / y" (Phase 7 today). It lists exactly which prompts, so the user isn't surprised.
- **Tailscale on the phone and laptop:** the user installs the app. The checklist links it.

## Re-runs and failures
- Every stage first checks whether it's already done (server exists, SSH answers, bootstrap marker, `tailscale status`, token files present, services active) and skips it if so.
- `generated/up-state.json` (gitignored, mode 600) holds only non-secret facts: server ID, name, IP, type, location, host-key fingerprint, and the last finished stage. **Never a key.**
- A re-run reuses the server in the state file and never creates a second one. If the state file names a server that is gone, it asks before creating a new one (with a new price confirmation).
- Keys aren't kept, so a re-run asks for them again, but only the ones the remaining stages need.
- Every failure prints the stage, what went wrong and the fix. For example: `Hetzner: CAX21 is sold out in fsn1, nbg1, hel1 and CX33 too → try --location ash or later`. Waits (server running, SSH) have time limits with a clear message.

## Choosing the server
- **Type from the preset:** CAX11 (4 GB Arm) for `starter`/`recommended`, CAX21 (8 GB Arm) for `full` or `PLANE=true`. Overridable with `--type`.
- **Location:** tries `fsn1` → `nbg1` → `hel1`. Overridable with `--location`.
- **Sold out:** it switches Arm ↔ x86 at the same size (CAX11 ↔ CX23, CAX21 ↔ CX33), then gives up with the message above.
- **The final choice is what the price question shows.**

## Parts
| Part | Job | Depends on |
|---|---|---|
| `nori` (repo root, executable) | CLI entry: `nori up [--host IP] [--type T] [--location L] [--yes-price]`. Leaves room for `doctor` and `init` later. | the modules below |
| `scripts/nori/hetzner.py` | Hetzner Cloud API over `urllib`: check token, prices, server types and availability, upload SSH key, create server, wait for `running`. | stdlib only |
| `scripts/nori/remote.py` | `ssh`/`scp` wrappers (system OpenSSH). Creates `~/.ssh/nori_ed25519` if missing. Adds or updates a marked `# >>> nori >>>` block in `~/.ssh/config`. Sends secrets as **stdin**, never argv. | system `ssh`, `ssh-keygen` |
| `scripts/nori/stages.py` | The ordered stages, each with `done()` and `run()`, plus the state file. | hetzner, remote, `scripts/conf.sh` (resolved `nori.conf`) |
| `scripts/nori/keys.py` | The checklist text, hidden prompts (`getpass`) and the per-key checks. Keys are kept in memory only. | stdlib only |
| Server: `server/bin/set-token` | Already reads the secret from stdin with `read -s`, so it works over SSH input. It gains a `claude <area>` target. | — |
| Server: Claude token | `set-token claude <area>` writes `CLAUDE_CODE_OAUTH_TOKEN` to a 600 file of that user. `claude@.service` (and the admin's shell / setup) loads it. | the probe below |
| Server: Tailscale | `tailscale up --auth-key=file:<600 tmp file>`, and the file is deleted afterwards. The key never appears in `ps`. | — |

No new Python packages. It runs the same on macOS, Linux and Windows (WSL).

## Security
- Keys live only in the `./nori up` process's memory. They are sent to the server over SSH as stdin of a fixed command, and never put in argv, logs, `up-state.json`, shell history or git. The output never echoes them, and a test checks this.
- Nothing is spent without the `yes` to the price question. A re-run never creates a second server.
- The Hetzner token is used for one run and then forgotten. The docs recommend a separate Hetzner project for Nori and deleting the token afterwards if the user likes.
- The server ends in exactly the state today's bootstrap leaves it in: root login off, key-only admin, ufw, Tailscale for everything but SSH.
- The SSH host key is pinned on first contact in the managed `known_hosts` entry, so later stages don't blindly trust a changed key.

## Probe before building the Claude stage
Nobody has yet checked whether a server logged in **only with a `claude setup-token` token** can run everything Nori uses:
- the Telegram channel plugin
- Remote Control (`/rc`)
- the session pool (`claude-pool`)
- `claude -p` calls from the Ops bot

It also needs to check whether the one-time prompts can be pre-answered from a supported settings file:
- folder trust for `~/projects/<area>`
- external CLAUDE.md imports
- "Enable Remote Control?"

They must be answered through supported configuration, never by typing into the session from a script. Nori's rules say only a human answers those prompts. If no supported setting exists, the human answers them once.

**Probe:** on a throwaway Hetzner server, log in with only the token and try each item. Then delete the server.
- **All work:** the `claude` stage is fully automatic.
- **Some don't:** Quick asks for **one browser login** for that part only, at the end, and the docs say so plainly. The rest of the design is unchanged.

## Testing
- **Automated tests** in `tests/` (stdlib unittest, no network):
  - a fake Hetzner API: token check, prices, sold-out fallback order, create, wait;
  - stage order and skip-if-done;
  - resume from each stage;
  - "never a second server";
  - `~/.ssh/config` block insert and update;
  - keys never appear in argv, output or the state file.
- **The probe above** on a real server.
- **End-to-end:** `./nori up` on a fresh Hetzner server with test bots. This doubles as SRV-14 (the fresh-server test). Do Ubuntu 24.04 first, then 26.04.

## Docs
- **`CLAUDE.md`:** Phase 0 gets the three-way question. Quick and Existing server run `./nori up`; Step by step keeps Phases 1–8.
- **`docs/setup-guide.md`:** a new "Quick setup" section at the top (keys checklist, `./nori up`, what it does, re-runs). The step-by-step guide stays below it.
- **`docs/troubleshooting.md`:** `./nori up` errors (sold out, bad key, SSH wait timeout, re-run).
- **`README.md`:** one line pointing to Quick setup.
