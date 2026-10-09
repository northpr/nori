# Telegram (supported)

Nori talks to Claude through a Claude Code **channel plugin**. For Telegram that is `telegram@claude-plugins-official` (marketplace `anthropics/claude-plugins-official`; plugins from other marketplaces do not register as channels).

## Files here
- `platform.conf`: facts the scripts read (plugin id, where the token lives, how to detect the bot process).
- `access.json.tmpl`: the allowlist template; `scripts/render.py` fills it per area (your numeric ids, the group prefix).
- `rules.md`, `rules-group.md`: the Telegram-specific part of the rules Claude follows on the server.

## 1. Find your numeric user id
Open [@userinfobot](https://t.me/userinfobot) (use this link: searching Telegram shows many lookalike bots) on the device where you use Telegram (on a computer the page shows "Open in Telegram" or "Open in Web": press it) and press **Start**; it answers with your id. Put it in `CHAT_ALLOWED_IDS` in `nori.conf` (several ids separated by commas, e.g. a second account of yours). Anyone not in that list is ignored by the bots (no 👀, no answer). What counts is the account you **chat from**, not the one that created the bot: if you have a personal and a work account, add both ids. Later, `/whoami` to your Ops bot shows the id too.

## 2. Create one bot per area, plus one for Ops (BotFather)
In Telegram open [@BotFather](https://t.me/BotFather) (use the link; searching shows lookalike bots):
1. `/newbot`, choose a display name and a username ending in `bot`. Repeat for each area, and once for the Ops bot unless you run without it (`PRESET=starter` or `OPS_BOT=false`). So: 1 area + Ops = 2 bots; starter = 1 bot. One bot per Claude session: two programs can't read the same bot.
2. BotFather prints a **token**, and you chose a **username** (e.g. `my_nori_bot`): note it, it's not secret and it's the bot you'll chat with. Treat the token like a password: never paste it into a chat with Claude, into git or a ticket. You put it on the server yourself with `~/nori/server/bin/set-token <area>` or `set-token ops`, which asks for it with hidden input.
3. For bots that will sit in a group: `/setprivacy` > pick the bot > **Disable** (or `/mybots` > your bot > Bot Settings > Group Privacy > **Turn off**), so the bot also sees plain prefixed messages (`m: do X`). Telegram's wording may change.
4. Optional: `/setuserpic`, `/setdescription`.

## 3. Open each bot once
In your DM with each bot press **Start** (a bot cannot message you first). The bot replies with the plugin's "To pair: … /telegram:access pair" text: ignore it, Nori already put your ids on the allowlist. Just send "hi".

## 4. Allowlist instead of pairing
The default policy in `access.json.tmpl` is `dmPolicy: allowlist`: only ids in `CHAT_ALLOWED_IDS` get through, no pairing code needed. `setup.sh` writes `~/.claude/channels/telegram-<area>/access.json` once the token file exists. (The plugin also supports a pairing flow, `/telegram:access`; not used by default.)

## 5. Optional group chat ("Nori HQ")
One group with you, the area bot(s) and the Ops bot gives one place for alerts and for talking to any session. (Needs the Ops bot: it learns the group with `/here`.)
1. Create a group, add yourself (all your accounts) and all the bots.
2. In the group send `/here` to the **Ops bot**: it remembers the group's id for alerts and the digest, and the next `./setup.sh` adds that group to every area's `access.json`.
3. Talk to a session with its prefix: `m: what is on my plate?` (`AREA_<area>_PREFIX` in `nori.conf`) or reply to the bot's message.
4. 🔐 permission prompts (push, merge, ...) still arrive in your DM with the area bot, not in the group. This is a plugin limitation.

## 6. Check
- Message the area bot "hi": it reacts with 👀 immediately, then answers.
- Ops bot: `/status`, `/progress`. It also reacts with 👀 to each command. With the Ops bot, a push or merge comes as a 🔐 card showing just the command, with Allow / Deny buttons (`PERM_CARDS`, on in `recommended` and `full`).
- No 👀? See `docs/troubleshooting.md`.

## Ops bot
Optional (`OPS_BOT=true`, on in `recommended` and `full`). Without it, the daily digest and nightly report come to your DM through the first area's chat bot, and there are no alerts or `/ask`. The Ops bot (`server/bin/ops-bot`) is a plain Python script that talks to the Telegram Bot API directly; it is **Telegram-only** for now. Other platforms would need a port of that one file (see `docs/adding-a-chat-platform.md`).
