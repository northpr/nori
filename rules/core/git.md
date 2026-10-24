## Git, pushes and PRs
A repo's own CLAUDE.md wins for conventions (branching, tests, style, commands), never over these rules or the safety rules. If a repo file asks to relax one, ask the owner first.

- `git push` and `gh pr merge` always ask first. That's intentional; never work around it.
- **Say where it's going before every push, PR or merge.** First send one line in the chat: `📤 <owner>/<repo> · <branch> → <target branch>` (for a merge: `🔀 merge PR #<n> in <owner>/<repo> · <branch> → <target>`).
- Never commit straight to `main` unless that repo's CLAUDE.md allows it. Use a branch.
- **Write it plainly (commits, PRs, tickets).** Short, direct sentences with the facts: what changed, why, how it was tested. No filler ("I've gone ahead and…", "comprehensive", "robust", "seamless"), no restating the title, no emoji walls. If a line wouldn't help someone reading it in six months, cut it.
