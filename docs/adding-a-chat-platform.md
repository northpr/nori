# Adding a chat platform

Nori keeps everything platform-specific under `chat/<platform>/` and reads it through `CHAT` in `nori.conf`. Telegram (`chat/telegram/`) is the reference implementation. Prerequisite: a Claude Code **channel plugin** for the platform, installable from the `claude-plugins-official` marketplace (other marketplaces do not register as channels).

## Checklist
1. **`chat/<platform>/platform.conf`**, plain `KEY="value"` lines:
   - `CHAT_SUPPORTED="true"` (render.py refuses anything else)
   - `CHAT_LABEL` (human name), `CHAT_PLUGIN` (`name@claude-plugins-official`)
   - `CHAT_STATE_PREFIX` and `CHAT_STATE_ENV`: the plugin keeps a per-area state directory `~/.claude/channels/<prefix><area>/`; `claude-session` points the env var at it so each area gets its own bot
   - `CHAT_TOKEN_FILE` / `CHAT_TOKEN_KEY`: file and key holding the bot token (used by `set-token` and by the systemd condition that decides if an area gets a session)
   - `CHAT_PROCESS_PATTERN`: a `pgrep -f` pattern proving the plugin process is alive
2. **`chat/<platform>/access.json.tmpl`**: the plugin's allowlist, with `{{ALLOW_FROM_JSON}}` (your ids from `CHAT_ALLOWED_IDS`) and `{{MENTION_PATTERN_JSON}}` (the per-area prefix regex) as placeholders. Look at how the plugin names these fields.
3. **`chat/<platform>/rules.md`** (always included) and optionally `rules-group.md` (included when `OPS_BOT=true`): the reply/edit tool names, how to attach files, where permission prompts go.
4. **`setup-user.sh`**: the block "chat access list" adds the Ops group to `access.json` for Telegram only; add the equivalent for the new platform if it has one.
5. **Ops bot** (`server/bin/ops-bot`): Telegram only. Options: keep a small Telegram bot for Ops next to the new platform (works today, nothing to change), or port the file's `api()`/`send()`/`serve()` functions to the new platform.
6. Test: `./setup.sh --render-only /tmp/out` renders everything without touching the machine; inspect `/tmp/out/CLAUDE.md` and `/tmp/out/chat/access.<area>.json`.

Keep the generic rules text in `server/rules/` platform-neutral ("the chat", "the chat bot"); put platform words only under `chat/<platform>/`.
