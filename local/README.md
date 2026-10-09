# local/ (your private additions, gitignored)

Anything here stays out of git, so `git pull` of a newer Nori never conflicts with it. `setup.sh` picks it up.

- `local/rules/*.md`: extra rules appended to the server CLAUDE.md (sorted by file name). For example
  `local/rules/plane-projects.md`, if you turned on Plane:

  ```
  ## Projects and modules
  | You say | Plane project / module | Repo | Area |
  |---|---|---|---|
  | "the website" | WEB / Website | ~/projects/main/website | main |
  ```
- `profile/USER.md` (one level up) is your own profile, also gitignored.
