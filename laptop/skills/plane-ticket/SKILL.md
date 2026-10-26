---
name: plane-ticket
description: Create a ticket in your Plane (on the Nori server) from this laptop session. Use when the user says "open/create/add a ticket", "log this as a ticket", or wants findings tracked. Only works when the server has PLANE=true.
---

# Create a Plane ticket from the laptop

Needs the server to run Plane (`PLANE=true` in `nori.conf`) and the SSH alias `nori` to work (`ssh nori true`). If your alias has another name, use it instead of `nori` below.

1. Pick the project: the Plane project identifier (e.g. `APP`). Ask if unsure. Never put work in a personal project or the reverse.
2. Write it like the existing tickets: short specific title; description = who asked and where, links (repo/PR/branch), what was found or done (files, lines), what is left, open questions. Labels: one involvement label (`auto`, `quick-ask` or `needs-me`) plus one type label (`bug`, `feature`, `improvement` or `idea`). Priority only when it matters.
3. Show the user the title, labels and priority in one short message and wait for a yes.
4. Create it. Title and description go through ONE quoted heredoc on stdin (title on the first line, description after it). Only fixed flags go on the ssh command line:

```bash
ssh nori .local/bin/plane-ticket --project APP --priority high --label bug --label needs-me <<'EOT'
Fix X in Y
From a laptop session (<repo>, <date>).

What: ...
- step one
- step two
EOT
```

5. Report the key it prints (e.g. `APP-14`).

If it says `unknown project`, it lists the valid identifiers: pick one. A label that does not exist in that project is skipped with a warning.

Never put the title, description or any free text in the ssh command line (ssh passes it to a remote shell, so `;`, `$(...)` or backticks would run on the server).

Never include secrets, tokens or customer data in a ticket.
