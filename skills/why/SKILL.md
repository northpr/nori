---
name: why
description: Find out why a piece of code exists before deleting or rewriting it. Use when code looks odd, redundant or wrong (a strange condition, a magic number, a workaround, a commented "don't touch"), or a fix would remove or change behaviour someone may have added on purpose.
---

# Why is this code here?

Spend a few minutes on history before changing it. Code that looks wrong is often a fix for a bug you can't see from the file.

1. `git log -L <start>,<end>:<file>` (or `git blame -w -C <file>` for the lines) → the commits that wrote it.
2. `git show <sha>` → read the message and the whole diff, not just your lines. A ticket id (`ABC-12`, `[ABC-3]`) or PR number in the message → open it (your ticket tool, `gh pr view <n>`) and read the description and comments.
3. Search for the same thing elsewhere: tests that cover it, other callers, a config or env flag it depends on.
4. Still unclear → `recall "<keyword>"` (if installed) for past chats and handoffs.

Then decide:
- **Reason found and still valid** → keep it; if it's unclear, add a one-line comment saying why (with the ticket id).
- **Reason found but obsolete** → change it, and say in the PR what it was for and why that no longer applies.
- **No reason found** → say so in the ticket and PR ("no history explains X; removing it, covered by test Y"). For anything customer-visible or touching money, ask the owner first.

Put a one-line summary of what you found in the ticket or PR.
