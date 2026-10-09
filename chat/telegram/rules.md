## Telegram specifics
- Everything the owner should read must go through the Telegram plugin's `reply` tool; your terminal output never reaches the chat. Use `reply_to` only when answering an earlier message. Attach files (screenshots) with the `files` argument (absolute paths). `edit_message` is for progress updates (edits don't notify the phone).
- 👀 on a message means the bot received it. Photos arrive with an `image_path` (Read it); other files via `download_attachment`.
- 🔐 permission requests are always sent to the owner's DM with the bot, never to a group.
