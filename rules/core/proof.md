## Proof before claims
- **Bug: reproduce first.** Before any fix, have a failing test or written repro steps. After the fix, rerun that exact case and paste the result in the PR (and ticket). Can't reproduce it → say so and ask; don't fix blind.
- **Performance: measure first.** Before/after numbers (load time, query ms, memory) measured the same way, in the PR. No numbers, no "faster" claim.
- **Non-trivial plan:** before writing code, answer three questions where the owner can see them: what can break, is there a simpler way, how will it be tested. Change the plan if an answer shows a problem.
- **Odd-looking code:** before deleting or rewriting it, load the `why` skill.
