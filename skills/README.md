# Skills

A skill is a folder with a `SKILL.md` (front matter `name` + `description`, then when to use it, the steps and the gotchas).

- Put general skills here as `skills/<name>/SKILL.md`. `setup.sh` links each one into `~/.claude/skills/` of the admin and of every area user on the server.
- Skills specific to one repo belong in that repo's `.claude/skills/` (via a PR).
- Sessions on the server may also save new skills directly to their own `~/.claude/skills/`, but only after you said yes in chat.
- Never put secrets in a skill.
