# Slack (planned, not yet supported)

`CHAT="slack"` is rejected by `setup.sh` today. What would be needed:

1. **A channel plugin for Slack.** Whether `claude-plugins-official` has one is **to be checked** at https://github.com/anthropics/claude-plugins-official (and in Claude Code's `/plugin` browser). If none exists, a channel plugin would have to be written (a Claude Code MCP server that declares the channel capability); see the Claude Code docs on channels.
2. Once a plugin exists: `chat/slack/platform.conf`, `access.json.tmpl`, `rules.md` as described in `chat/discord/README.md` and `docs/adding-a-chat-platform.md`.
3. Slack needs an app with the right scopes and tokens (bot token, and an app-level token if Socket Mode is used). They go into the plugin's state directory via `set-token`, never into the chat or git.
4. The Ops bot is Telegram-only (see Discord notes).
