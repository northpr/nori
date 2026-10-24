## Layout and git identity
- Projects live in `~/projects/<area>/`. Keep each area's work in its own folder.
- **Identity follows the repo remote owner**, not the folder. Configured GitHub owners: {{GIT_ACCOUNTS_INLINE}}. `~/.gitconfig` includes one identity file per owner for `github.com/<owner>/**`. A global pre-commit hook blocks a mismatched author, and repos from unknown owners have no identity, so commits fail. If that happens, ask {{OWNER_NAME}} which account to use (they add it to `GITHUB_ACCOUNTS` in `nori.conf` and run `./setup.sh`). Never set `user.email` by hand to get around it.
- `gh` is a wrapper (`~/.local/bin/gh`) that picks the account from the repo remote. Don't run `gh auth switch`.
- When cloning, clone into the right area and confirm `git config user.email` matches before committing.
