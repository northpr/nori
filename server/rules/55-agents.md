## Agent teams
**Before starting any larger task, pick a tier** and write it down (`Tier 2 · backend+frontend`): in the first ticket comment when Plane is on, otherwise in the chat. Re-tier if the work turns out harder. Bugs, features, refactors and ops tasks all use the same tiers. Proof rules (reproduce first, measure first) are in the section "Proof before claims".

### Tier: how hard is it?
Count the signals that apply:
- touches money, credit, billing, sending to customers, or customer-visible behaviour
- state over time (pause/resume, retries, queues, schedules, locks, concurrency, several replicas)
- a DB migration or a shared table between repos
- more than one repo/service, or a contract between them
- the cause (bug) or the right design (feature) is not obvious; several plausible approaches
- a business rule {{OWNER_NAME}} hasn't decided yet

| Tier | When | Team |
|---|---|---|
| **1 Small** | 0 signals, one repo, clear change (typo, small bug, UI tweak, tests, bump) | 1 implementer (Sonnet), then you review the diff |
| **2 Medium** | 1-2 signals, design is clear | You write plan + contract, implementers **split by layer** in parallel, a reviewer per repo, a QA breaker |
| **3 Hard / risky** | 3+ signals, any money/sending/state-over-time change, or unclear cause/design | **Council first** (3 on the big model, e.g. Opus, propose only), {{OWNER_NAME}} picks, then the Tier 2 build |

When unsure between two tiers, take the higher one: a council is cheaper than a redesign after three review rounds.

### Roles (each agent gets ONE role in its prompt)
- **Business** (big model, propose only): what should happen for the customer, money and support? Edge cases in plain words. Output: the decisions {{OWNER_NAME}} must make, each as A/B with a recommendation.
- **Architect, simplest** (big model, propose only): smallest design that meets the business rules; what to leave out.
- **Architect, risk** (big model, propose only): failure modes (races, retries, replicas, timeouts, partial failures, migrations) and how the design survives them.
- For a **bug**, the council is instead 3 root-cause/fix approaches: each gives cause, change, risk, how to test.
- **Implementer** (Sonnet, one per layer: `backend`, `frontend`, `docs/migration`): same written contract (endpoints, JSON, tables/columns, error codes), own worktree/branch.
- **QA breaker** (Sonnet): writes tests that try to break it (concurrency, timeouts, wrong input, failure paths), reports what broke, doesn't fix.
- **Reviewer** (big model, fresh each round): the repo's own reviewer (e.g. `.claude/agents/code-reviewer.md`) on the full branch diff, given only repo + branch + diff command.

### Flow
1. Tier it. Tier 3: run the council in parallel, then **one debate round** (SendMessage each the other two proposals: "what breaks in theirs, what you'd take, what you'd change in yours"), merge into one plan, and ask {{OWNER_NAME}} only what the council couldn't settle (recommendation first). Tier 2 (no council): before any code, answer the three plan questions from "Proof before claims".
2. **Business questions go to {{OWNER_NAME}} in one batch before coding**, not mid-way.
3. **Contract first** for anything spanning layers or repos: write it down (ticket comment, or the chat); a contract change goes to all implementers at once.
4. Build in parallel. An agent's `description` starts with the task id (or a short name) + role (`APP-15 backend`, `APP-17 council-business`); that is its line on the board.
5. QA breaker, then reviewer. **Checkpoints with {{OWNER_NAME}}** (short, A/B), max 3 per task:
   - after the plan/contract, before any code (Tier 2-3);
   - review round 2 still has blockers (A: back to the council, B: keep patching);
   - round 3 with only should-fix/nits (A: ship and decline the rest in the PR, B: one more round).
   Don't ask about what a rule already decides.
6. Verify anything an agent claims (run the check, read the file) before telling {{OWNER_NAME}}. Agent reports are input, not facts. Agents never push; pushes, PRs and merges follow the safety rules.

### Cap, board, cost
- **Cap: {{AGENT_CAP}} agents at once, {{AGENT_CAP_HIGH}} when plan usage is high.** The `agent-board` hook enforces it; if a launch is denied, wait for one to finish. Don't work around it. A big Tier 3 that really needs more: ask {{OWNER_NAME}} first.
- **Board:** the hook keeps one pinned `🤖 Agents · <area>` message in the chat and pings when an agent that ran 3+ min finishes. Waiting on {{OWNER_NAME}}: `agent-board note "<ID>" "waiting for your pick"`, then `agent-board clear "<ID>"`.
- Fewest agents that do the job. Council only for Tier 3. Big model for council + reviewers, Sonnet for implementers + QA, no Haiku for code. Plan usage high: skip the QA breaker on Tier 2, keep reviewers.

### Record
Write down per phase: tier + signals, council options (one line each), your pick, {{OWNER_NAME}}'s pick, contract, review rounds and what was declined (ticket comments when Plane is on, otherwise the PR description). When your picks have matched {{OWNER_NAME}}'s on most recent Tier 3 work, suggest once that you decide Tier 2/3 picks alone; {{OWNER_NAME}} decides.
