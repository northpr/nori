"""ssh plumbing for ./nori up. Secrets only ever travel as stdin of a fixed command."""
import os
import re
import subprocess
import time
from pathlib import Path

BEGIN, END = "# >>> nori >>>", "# <<< nori <<<"


class RemoteError(Exception):
    pass


def ensure_key(home, run=subprocess.run):
    key = Path(home) / ".ssh" / "nori_ed25519"
    if not key.exists():
        key.parent.mkdir(mode=0o700, exist_ok=True)
        run(["ssh-keygen", "-t", "ed25519", "-N", "", "-C", "nori", "-f", str(key)], check=True, capture_output=True)
    return (key.parent / "nori_ed25519.pub").read_text().strip()


def upsert_host(config_path, alias, ip, user):
    p = Path(config_path)
    p.parent.mkdir(mode=0o700, exist_ok=True)
    txt = p.read_text() if p.exists() else ""
    outside = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", "", txt, flags=re.S)
    if re.search(rf"(?mi)^\s*Host\s+(.*\s)?{re.escape(alias)}(\s|$)", outside):
        raise RemoteError(f"~/.ssh/config already has your own 'Host {alias}'. Rename it, or remove it, then re-run.")
    block = (f"{BEGIN}\nHost {alias}\n  HostName {ip}\n  User {user}\n"
             f"  IdentityFile ~/.ssh/nori_ed25519\n  IdentitiesOnly yes\n"
             f"  StrictHostKeyChecking accept-new\n  UserKnownHostsFile ~/.ssh/nori_known_hosts\n"
             f"Match all\n{END}\n")  # Match all ends 'Host nori', so the user's lines below stay global
    new = block + ("\n" + outside.lstrip("\n") if outside.strip() else "")  # first: ssh uses the first value it sees
    p.write_text(new)
    os.chmod(p, 0o600)


def ssh(alias, command, stdin=None, run=subprocess.run, timeout=1800):
    feed = {"input": stdin + "\n"} if stdin is not None else {"stdin": subprocess.DEVNULL}
    r = run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", alias, command],
            capture_output=True, text=True, timeout=timeout, **feed)
    out = (r.stdout or "") + (getattr(r, "stderr", "") or "")
    if "REMOTE HOST IDENTIFICATION HAS CHANGED" in out or "Host key verification failed" in out:
        raise RemoteError("The server's SSH host key changed. If you recreated the server, "
                          "remove its line from ~/.ssh/nori_known_hosts, then re-run.")
    return r.returncode, out


def wait_ssh(alias, run=subprocess.run, tries=60, sleep=time.sleep):
    for _ in range(tries):
        try:
            if ssh(alias, "true", run=run, timeout=20)[0] == 0:
                return
        except (subprocess.TimeoutExpired, OSError):
            pass
        sleep(5)
    raise RemoteError("The server didn't answer on SSH within 5 minutes. Check it's running, then re-run.")


def copy_repo(alias, repo, popen=subprocess.Popen):
    """Repo + nori.conf to /root/nori as a tar stream (no .git, no generated/: no secrets live in the repo)."""
    tar = popen(["tar", "-C", str(repo), "--exclude=.git", "--exclude=generated", "-cf", "-", "."],
                stdout=subprocess.PIPE, env={**os.environ, "COPYFILE_DISABLE": "1"})  # no macOS ._ files
    ssh_ = popen(["ssh", "-o", "BatchMode=yes", alias,
                  "rm -rf /root/nori && mkdir -p /root/nori && tar --warning=no-unknown-keyword --no-same-owner -x -C /root/nori"], stdin=tar.stdout)
    if ssh_.wait() != 0 or tar.wait() != 0:
        raise RemoteError("Copying the repo to the server failed. Re-run ./nori up.")
