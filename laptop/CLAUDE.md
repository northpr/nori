# Nori rules on your laptop (all projects)

Imported by `~/.claude/CLAUDE.md` (added by `laptop/setup-laptop.sh`). These are the same rule files the server sessions get; change them in `rules/core/`, not here.

@../rules/core/git.md
@../rules/core/proof.md

## Differences on the laptop
- No chat bot, Ops bot or `push-guard` here: you're talking to the owner directly. Ask in this chat (A/B choices as a normal question), send the 📤/🔀 line before every push, PR or merge, then wait for a yes.
- Workflow plugins (e.g. Superpowers) are fine for *how* to do the work (brainstorming, plans, TDD, debugging). Where they disagree with these rules (e.g. a skill offering to merge or push on its own), these rules win.
- These rules live only in `~/.claude`; never copy them into a repo, especially one teammates use.
- The `plane-ticket` skill (in `laptop/skills/`, laptop only; create a Plane ticket over `ssh nori`) only works when the server has `PLANE=true`. Without Plane, ignore it.
