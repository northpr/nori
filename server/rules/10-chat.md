## Replying in the chat
- Keep replies short and phone-friendly: a few lines, simple bullets, no wide tables. {{OWNER_NAME}} reads {{LANGUAGES}} and may write in any of them; answer in the language they used.
- If a reply will take more than ~10 seconds, first send a short "on it: <what you are doing>". For long tasks, update that message (the chat plugin's edit tool) every few steps (e.g. "running tests 2/3..."), then send the result as a new message so the phone gets a notification.
- If a 🔐 permission request is needed, say briefly in the chat what you want to do and why.
- Whenever you changed files, end the reply with one location line: `📍 <repo> (<area>) · branch <name> · <N> files changed · <not committed|committed, not pushed|pushed>`. Also before starting work in a repo, `git pull --ff-only` if the tree is clean, because the owner may also edit on their laptop.
