#!/usr/bin/env python3
"""Check that a Claude Code binary still accepts every CLI flag and subcommand Nori uses.

  tests/claude_cli_check.py [path/to/claude]      (default: `claude` on PATH)

Run by CI against the pinned version (server/claude-code.version) and, weekly, against @latest.
Nothing here logs in, talks to a model or touches your real config: every call runs with a throwaway
HOME and stops before doing anything. Three kinds of checks:

  flags  `claude <flags Nori uses> --nori-cli-check-sentinel`. The CLI rejects the FIRST unknown option
         ("error: unknown option '--x'"), so if the sentinel is the one named, everything before it was
         accepted. Bad choice values ("argument 'x' is invalid") fail too. `--help` and `--version` are no
         use here: both answer before unknown options are looked at.
  sub    `claude <subcommand> --help` must print that subcommand's own usage line (an unknown word is taken
         as a prompt or ignored, so a vanished subcommand shows the parent's help instead).
  binary `claude remote-control` parses its flags only after a full claude.ai login, so for it (and for the
         screen text ops-bot reads for /progress) we can only check that the strings are still in the binary.
         Weaker: it catches removals, not renamed behaviour.
"""
import mmap
import os
import re
import shutil
import subprocess
import sys
import tempfile

SENTINEL = "--nori-cli-check-sentinel"
SCHEMA = '{"type":"object","properties":{"a":{"type":"string"}}}'

# (what uses it, args). Keep in step with server/bin/claude-session, claude-pool, ops-bot, morning-summary and the docs.
FLAGS = [
    ("claude-session", ["--channels", "plugin:telegram@claude-plugins-official", "--remote-control", "nori-main"]),
    ("ops-bot /ask, morning-summary", ["-p", "--model", "sonnet", "--permission-mode", "dontAsk", "--tools", "",
                                       "--strict-mcp-config", "--no-session-persistence"]),
    ("ops-bot ticket triage", ["-p", "--model", "sonnet", "--permission-mode", "dontAsk", "--tools", "",
                               "--strict-mcp-config", "--no-session-persistence", "--output-format", "json",
                               "--json-schema", SCHEMA]),
    ("claude-pool (permission mode value)", ["--permission-mode", "auto"]),
    ("setup step 5: login", ["auth", "login", "--claudeai"]),
    ("setup step 5: plugin", ["plugin", "marketplace", "add", "anthropics/claude-plugins-official"]),
    ("setup step 5: plugin", ["plugin", "install", "telegram@claude-plugins-official"]),
]
SUBCOMMANDS = [["install"], ["update"], ["auth", "login"], ["auth", "status"], ["plugin", "install"],
               ["plugin", "marketplace", "add"], ["remote-control"]]
# claude-pool's flags + the terminal text ops-bot parses (session_state)
BINARY_STRINGS = ["--spawn", "same-dir", "--capacity", "--no-create-session-in-dir",
                  "--remote-control-session-name-prefix", "Do you want to proceed?", "esc to interrupt"]

TOP_USAGE = re.compile(r"Usage:\s*claude \[options\] \[command\]", re.I)
REJECTED = re.compile(r"(unknown|unrecognized|unexpected|invalid)\s+(option|argument|command|flag)\W*?(-{1,2}[\w-]+|\w[\w-]*)|"
                      r"argument '[^']*' is invalid", re.I)


def run(claude, args, home):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("ANTHROPIC_", "CLAUDE_")) and k not in ("HOME", "XDG_CONFIG_HOME")}
    env.update(HOME=home, DISABLE_AUTOUPDATER="1", CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1", NO_COLOR="1")
    try:
        p = subprocess.run([claude, *args], env=env, cwd=home, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=60)
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return None, "(timed out: the CLI did not stop at the sentinel)"


def check_flags(claude, args, home):
    rc, out = run(claude, args + [SENTINEL], home)
    m = REJECTED.search(out)
    if rc not in (None, 0) and m and SENTINEL in m.group(0):
        return None
    if m:
        return f"rejected: {m.group(0)}"
    return f"sentinel not reported (rc={rc}), the CLI may have changed its error wording: {out[:300]!r}"


def check_sub(claude, sub, home):
    rc, out = run(claude, sub + ["--help"], home)
    if rc is None:
        return out
    # "Usage: claude plugin install|i [options] <plugin>"; an unknown word gives the parent's (or top-level) usage
    own = re.compile(r"Usage:\s*claude" + "".join(r"\s+" + re.escape(w) + r"(\|[\w-]+)*" for w in sub) + r"(\s|$)")
    if own.search(out):
        return None
    if sub == ["remote-control"] and "Remote Control" in out and not TOP_USAGE.search(out):
        return None     # its --help sits behind the login check; this message comes from the subcommand itself
    return f"not a subcommand any more (no 'Usage: claude {' '.join(sub)}'): {out[:200]!r}"


def check_binary(claude):
    path = os.path.realpath(claude)
    if os.path.getsize(path) < 5_000_000:      # a JS wrapper, not the native binary: skip rather than guess
        return [f"skipped: {path} is not the native binary"]
    with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
        return [f"missing from the binary: {s!r}" for s in BINARY_STRINGS if m.find(s.encode()) < 0]


def main():
    claude = shutil.which(sys.argv[1] if len(sys.argv) > 1 else "claude")
    if not claude:
        sys.exit("claude not found")
    failed = 0
    with tempfile.TemporaryDirectory(prefix="nori-cli-check-") as home:
        rc, ver = run(claude, ["--version"], home)
        print(f"checking {claude}: {ver}")
        for label, args in FLAGS:
            problem = check_flags(claude, args, home)
            failed += bool(problem)
            print(f"{'FAIL' if problem else 'ok  '} flags  {' '.join(a or repr(a) for a in args)}   ({label})"
                  + (f"\n       {problem}" if problem else ""))
        for sub in SUBCOMMANDS:
            problem = check_sub(claude, sub, home)
            failed += bool(problem)
            print(f"{'FAIL' if problem else 'ok  '} sub    claude {' '.join(sub)}" + (f"\n       {problem}" if problem else ""))
        problems = check_binary(claude)
        for problem in problems:
            failed += not problem.startswith("skipped")
            print(f"{'skip' if problem.startswith('skipped') else 'FAIL'} binary {problem}")
        if not problems:
            print(f"ok   binary {', '.join(BINARY_STRINGS)}")
    print("all Nori CLI checks passed" if not failed else f"{failed} check(s) failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
