# Discord (planned, not yet supported)

`CHAT="discord"` is rejected by `setup.sh` today. What would be needed:

1. **A Claude Code channel plugin for Discord.** Channel plugins come from the `claude-plugins-official` marketplace (`anthropics/claude-plugins-official`); a Discord one exists there. Check the marketplace for its exact plugin id (likely `discord@claude-plugins-official`) and how it stores its bot token and allowlist.
2. **`chat/discord/platform.conf`** with `CHAT_SUPPORTED="true"` and the plugin id, state-directory prefix and env var, token file and key, and the process pattern (see `chat/telegram/platform.conf`).
3. **`chat/discord/access.json.tmpl`** in whatever format that plugin uses for its allowlist (Discord user ids, guild/channel ids, how mentions work).
4. **`chat/discord/rules.md`** (and `rules-group.md` if relevant): the plugin's reply/edit tool names and quirks.
5. **The Ops bot** is Telegram-only. Either keep a small Telegram bot just for Ops, or port `server/bin/ops-bot` to the Discord API (long polling becomes a gateway connection).
6. `setup-user.sh` has one Telegram-specific `jq` line (adding the group to `access.json`); give Discord its own branch there.

Full checklist: `docs/adding-a-chat-platform.md`.
