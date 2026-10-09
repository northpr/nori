"""Runs server/bin/work-backup collect against throwaway git repos (HOME is a temp dir; needs git)."""
import hashlib
import os
import pwd
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from helpers import REPO

USER = pwd.getpwuid(os.getuid()).pw_name


class Fixture(unittest.TestCase):
    """A temp HOME with ~/projects/<user>/app (pushed + unpushed commit, local changes) and .../notes (no remote)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.home = self.tmp / "home"
        self.env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(self.home),
                    "GIT_CONFIG_NOSYSTEM": "1", "GIT_OPTIONAL_LOCKS": "0",
                    "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.com",
                    "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.com"}
        area = self.home / "projects" / USER
        area.mkdir(parents=True)

        # a bare "remote" and a clone with one pushed and one unpushed commit
        self.git(self.tmp, "init", "-q", "--bare", "remote.git")
        self.app = area / "app"
        self.git(self.tmp, "clone", "-q", str(self.tmp / "remote.git"), str(self.app))
        self.git(self.app, "symbolic-ref", "HEAD", "refs/heads/main")
        (self.app / ".gitignore").write_text("*.log\n")
        (self.app / "tracked.txt").write_text("v1\n")
        self.git(self.app, "add", ".")
        self.git(self.app, "commit", "-qm", "pushed")
        self.git(self.app, "push", "-q", "origin", "main")
        (self.app / "new.txt").write_text("unpushed\n")
        self.git(self.app, "add", "new.txt")
        self.git(self.app, "commit", "-qm", "unpushed commit")
        self.unpushed = self.git(self.app, "rev-parse", "HEAD")
        (self.app / "tracked.txt").write_text("v2 uncommitted\n")
        (self.app / "staged.txt").write_text("staged\n")
        self.git(self.app, "add", "staged.txt")
        (self.app / "untracked.txt").write_text("untracked\n")
        (self.app / "debug.log").write_text("ignored\n")
        with open(self.app / "big.bin", "wb") as f:     # sparse, over the 20 MB limit
            f.truncate(21 * 1024 * 1024)

        # a repo without a remote
        self.local = area / "notes"
        self.local.mkdir()
        self.git(self.local, "init", "-q")
        (self.local / "n.md").write_text("note\n")
        self.git(self.local, "add", ".")
        self.git(self.local, "commit", "-qm", "local only")

        (area / "HANDOFF.md").write_text("handoff\n")
        (self.home / ".claude" / "skills" / "mine").mkdir(parents=True)
        (self.home / ".claude" / "skills" / "mine" / "SKILL.md").write_text("skill\n")

    def git(self, cwd, *args):
        r = subprocess.run(["git", *args], cwd=str(cwd), env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, f"git {args}: {r.stderr}")
        return r.stdout.strip()

    def collect(self, script=REPO / "server/bin/work-backup"):
        """Runs the collector; returns (extracted dir, tar member list, stderr)."""
        out = self.tmp / "backup.tar.gz"
        with open(out, "wb") as f:
            r = subprocess.run([sys.executable, "-I", str(script), "collect"], stdout=f, stderr=subprocess.PIPE,
                               env=self.env, cwd=str(self.tmp), timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        x = self.tmp / "x"
        shutil.rmtree(x, ignore_errors=True)
        with tarfile.open(out) as t:
            members = t.getmembers()
            t.extractall(x)
        return x, members, r.stderr.decode()

    def patched(self, **consts):
        """A copy of the collector with other limits, e.g. patched(MAX_TOTAL="3 * MB")."""
        text = (REPO / "server/bin/work-backup").read_text()
        for k, v in consts.items():
            text, n = re.subn(rf"(?m)^{k} = .*$", f"{k} = {v}", text)
            self.assertEqual(n, 1, k)
        p = self.tmp / "work-backup"
        p.write_text(text)
        return p

    def commit_random(self, repo, name, size):
        (repo / name).write_bytes(os.urandom(size))     # random: neither gzip nor the bundle shrinks it
        self.git(repo, "add", name)
        self.git(repo, "commit", "-qm", f"add {name}")

    def snapshot(self, repo):
        index = repo / ".git" / "index"
        return (self.git(repo, "status", "--porcelain=v1", "-b"), self.git(repo, "for-each-ref"),
                self.git(repo, "stash", "list"), hashlib.sha256(index.read_bytes()).hexdigest())


@unittest.skipUnless(shutil.which("git"), "git not installed")
class WorkBackupCollect(Fixture):
    def test_collect(self):
        before = {r: self.snapshot(r) for r in (self.app, self.local)}
        x, _, err = self.collect()
        # the only problem: big.bin, over the per-file limit
        self.assertEqual(err.splitlines(), [f"work-backup ({USER}): {self.app}: left out big.bin  "
                                            "(21.0 MB, over the 20 MB per-file limit)"])
        after = {r: self.snapshot(r) for r in (self.app, self.local)}
        self.assertEqual(before, after, "the collector changed a repo")

        app = x / USER / USER / "app"
        files = app / "files"
        self.assertEqual((files / "tracked.txt").read_text(), "v2 uncommitted\n")
        self.assertEqual((files / "untracked.txt").read_text(), "untracked\n")
        self.assertEqual((files / "staged.txt").read_text(), "staged\n")
        self.assertFalse((files / "debug.log").exists(), "ignored file was saved")
        self.assertFalse((files / "new.txt").exists(), "committed file was saved as uncommitted")
        self.assertFalse((files / "big.bin").exists(), "file over the size limit was saved")
        self.assertIn("big.bin", (app / "SKIPPED.txt").read_text())
        self.assertIn("## main", (app / "STATUS.txt").read_text())
        self.assertEqual((x / USER / USER / "HANDOFF.md").read_text(), "handoff\n")
        self.assertEqual((x / USER / ".claude/skills/mine/SKILL.md").read_text(), "skill\n")
        manifest = (x / USER / "MANIFEST.txt").read_text()
        self.assertIn(f"area user: {USER}", manifest)
        self.assertIn(f"{USER}/{USER}/app: branch main; bundle 1 commit(s); 3 uncommitted file(s)", manifest)
        self.assertIn(f"{USER}/{USER}/notes: branch ", manifest)

        # the bundle restores exactly the unpushed commit into a fresh clone
        bundle = app / "unpushed.bundle"
        restored = self.tmp / "restored"
        self.git(self.tmp, "clone", "-q", str(self.tmp / "remote.git"), str(restored))
        self.git(restored, "bundle", "verify", str(bundle))
        self.git(restored, "fetch", "-q", str(bundle), "refs/heads/*:refs/heads/restored/*")
        self.assertEqual(self.git(restored, "rev-parse", "restored/main"), self.unpushed)
        # no remote: the whole history
        self.git(self.tmp, "init", "-q", "fresh")
        self.git(self.tmp / "fresh", "fetch", "-q", str(x / USER / USER / "notes" / "unpushed.bundle"),
                 "refs/heads/*:refs/heads/restored/*")
        self.assertIn("local only", self.git(self.tmp / "fresh", "log", "--all", "--format=%s"))

    def test_area_total(self):
        """A bundle or file over what is left of the area's total is left out and reported; the rest stays."""
        script = self.patched(MAX_TOTAL="3 * MB")       # 2 MB after the reserve for MANIFEST.txt
        self.commit_random(self.app, "data.bin", 2500 * 1024)
        (self.local / "blob.bin").write_bytes(os.urandom(2500 * 1024))
        x, names, err = self.collect(script)
        names = {m.name for m in names}
        app, notes = f"{USER}/{USER}/app", f"{USER}/{USER}/notes"
        self.assertIn(f"{self.app}: left out unpushed.bundle", err)
        self.assertIn("commits are NOT saved", err)
        self.assertIn(f"{self.local}: left out blob.bin  (2.4 MB, over the 3 MB total for this area)", err)
        self.assertNotIn(f"{app}/unpushed.bundle", names)
        self.assertNotIn(f"{notes}/files/blob.bin", names)
        self.assertIn("unpushed.bundle", (x / app / "SKIPPED.txt").read_text())
        # the small things are all there
        for n in (f"{USER}/{USER}/HANDOFF.md", f"{USER}/.claude/skills/mine/SKILL.md", f"{USER}/MANIFEST.txt",
                  f"{app}/STATUS.txt", f"{app}/files/tracked.txt", f"{notes}/unpushed.bundle"):
            self.assertIn(n, names)
        self.assertIn("SKIPPED (too big)", (x / USER / "MANIFEST.txt").read_text())

    def test_secrets_left_out(self):
        secrets = [".env", ".env.local", "config/credentials.json", "keys/server.pem", "tls.key", "id_rsa",
                   "id_ed25519.pub", "deploy/id_ecdsa", "id_dsa", "cert.p12", "cert.pfx", ".netrc", ".npmrc",
                   "sub/.pypirc"]
        for name in secrets:
            (self.app / name).parent.mkdir(parents=True, exist_ok=True)
            (self.app / name).write_text("secret\n")
        (self.app / "env.txt").write_text("not a secret\n")
        x, names, err = self.collect()
        self.assertNotIn("secret", err, "a left-out secret is not a problem")
        app = x / USER / USER / "app"
        for name in secrets:
            self.assertFalse((app / "files" / name).exists(), name)
        self.assertTrue((app / "files" / "env.txt").exists())
        skipped = (app / "SKIPPED.txt").read_text().splitlines()
        for name in secrets:
            self.assertIn(f"{name}  excluded (looks like a secret)", skipped)

    def test_hard_links(self):
        """Hard-linked files are stored as regular files, never as tar hard links (which could dangle)."""
        (self.app / "data.txt").write_text("linked\n")
        os.link(self.app / "data.txt", self.app / ".env")       # sorts first and is left out (a secret)
        os.link(self.app / "data.txt", self.app / "data-link.txt")
        skill = self.home / ".claude/skills/mine"
        os.link(skill / "SKILL.md", skill / "LINK.md")
        x, members, _ = self.collect()
        self.assertEqual([m.name for m in members if m.islnk()], [])
        files = x / USER / USER / "app" / "files"
        self.assertEqual((files / "data.txt").read_text(), "linked\n")
        self.assertEqual((files / "data-link.txt").read_text(), "linked\n")
        self.assertEqual((x / USER / ".claude/skills/mine/LINK.md").read_text(), "skill\n")

    def test_tags_detached_head_stash(self):
        """Unpushed tags, a detached HEAD and the newest stash are in the bundle; the repo is unchanged."""
        self.git(self.tmp, "init", "-q", "--bare", "lab.git")
        lab = self.home / "projects" / USER / "lab"
        self.git(self.tmp, "clone", "-q", str(self.tmp / "lab.git"), str(lab))
        self.git(lab, "symbolic-ref", "HEAD", "refs/heads/main")
        (lab / "f.txt").write_text("v1\n")
        self.git(lab, "add", ".")
        self.git(lab, "commit", "-qm", "pushed")
        self.git(lab, "push", "-q", "origin", "main")
        self.git(lab, "checkout", "-q", "-b", "tmp")           # a commit only a tag points at
        self.git(lab, "commit", "-q", "--allow-empty", "-m", "tagged")
        self.git(lab, "tag", "v-local")
        self.git(lab, "checkout", "-q", "main")
        self.git(lab, "branch", "-q", "-D", "tmp")
        (lab / "f.txt").write_text("stashed\n")
        self.git(lab, "stash", "-q")
        self.git(lab, "checkout", "-q", "--detach")
        self.git(lab, "commit", "-q", "--allow-empty", "-m", "detached")
        want = {r: self.git(lab, "rev-parse", r) for r in ("v-local", "HEAD", "refs/stash")}
        before = self.snapshot(lab)

        x, _, err = self.collect()
        self.assertNotIn(str(lab), err)
        self.assertEqual(self.snapshot(lab), before, "the collector changed the repo (stash list, refs, index)")
        self.assertIn("stash@{0}", (x / USER / USER / "lab" / "STATUS.txt").read_text())

        restored = self.tmp / "lab-restored"
        self.git(self.tmp, "clone", "-q", str(self.tmp / "lab.git"), str(restored))
        bundle = str(x / USER / USER / "lab" / "unpushed.bundle")
        self.git(restored, "fetch", "-q", bundle, "refs/tags/*:refs/tags/*", "HEAD:refs/heads/restored-head",
                 "refs/stash:refs/heads/restored-stash")
        self.assertEqual(self.git(restored, "rev-parse", "v-local"), want["v-local"])
        self.assertEqual(self.git(restored, "rev-parse", "restored-head"), want["HEAD"])
        self.assertEqual(self.git(restored, "rev-parse", "restored-stash"), want["refs/stash"])
        self.git(restored, "checkout", "-q", "main")
        self.git(restored, "stash", "apply", "-q", want["refs/stash"])
        self.assertEqual((restored / "f.txt").read_text(), "stashed\n")

    def test_nothing_unpushed(self):
        self.git(self.app, "push", "-q", "origin", "main")
        out = self.tmp / "b.tar.gz"
        with open(out, "wb") as f:
            r = subprocess.run([sys.executable, "-I", str(REPO / "server/bin/work-backup"), "collect"],
                               stdout=f, stderr=subprocess.PIPE, env=self.env, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        with tarfile.open(out) as t:
            self.assertNotIn(f"{USER}/{USER}/app/unpushed.bundle", t.getnames())
            manifest = t.extractfile(f"{USER}/MANIFEST.txt").read().decode()
        self.assertIn("nothing unpushed", manifest)


# test stand-ins: sudo runs the collector from this repo as the current user, gpg just copies
FAKE_SUDO = """#!/bin/sh
while [ $# -gt 0 ]; do case "$1" in -n|-H) shift ;; -u) shift 2 ;; *) break ;; esac; done
[ "$1" = /opt/nori/server/bin/work-backup ] || exit 99
shift
exec "$NORI_TEST_PY" -I "$NORI_TEST_REPO/server/bin/work-backup" "$@"
"""
FAKE_GPG = """#!/bin/sh
while [ $# -gt 0 ]; do [ "$1" = -o ] && { cat > "$2"; exit 0; }; shift; done
exit 98
"""


@unittest.skipUnless(shutil.which("git"), "git not installed")
class WorkOffsite(Fixture):
    """work-offsite end to end, with a local bare repo standing in for github.com."""

    def setUp(self):
        super().setUp()
        (self.app / "big.bin").unlink()     # a clean night: the collector reports nothing
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        for name, text in (("sudo", FAKE_SUDO), ("gpg", FAKE_GPG)):
            (bin_dir / name).write_text(text)
            (bin_dir / name).chmod(0o755)
        gh = self.tmp / "gh"
        self.git(self.tmp, "init", "-q", "--bare", str(gh / "you" / "backups.git"))
        self.remote = gh / "you" / "backups.git"
        (self.home / ".gitconfig").write_text(f'[url "{gh.as_uri()}/"]\n\tinsteadOf = https://github.com/\n')
        (self.home / "nori").symlink_to(REPO)
        (self.home / ".backup-pass").write_text("test-passphrase\n")
        conf = self.tmp / "nori.conf"
        conf.write_text(f'AREAS="{USER}"\nBACKUP_REPO="you/backups"\nPRESET="starter"\n')
        self.work = self.home / "backups" / "work"
        self.work.mkdir(parents=True)
        for d in range(1, 9):     # older snapshots: only the newest 7 per area stay
            (self.work / f"{USER}-2020010{d}.tar.gz.gpg").write_text("old")
        self.env.update({"PATH": f"{bin_dir}:{self.env['PATH']}", "NORI_CONF": str(conf),
                         "NORI_TEST_PY": sys.executable, "NORI_TEST_REPO": str(REPO)})

    def run_offsite(self, rc=0):
        r = subprocess.run(["bash", str(REPO / "server/bin/work-offsite")], env=self.env, cwd=str(self.tmp),
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, rc, r.stdout + r.stderr)
        return r

    def remote_git(self, *args):
        return self.git(self.remote, *args)

    def test_publish(self):
        self.run_offsite()
        main = self.remote_git("rev-parse", "main")
        self.assertIn("README.md", self.remote_git("ls-tree", "--name-only", "main"))
        self.run_offsite()     # second night: still one commit, main untouched
        self.assertEqual(self.remote_git("rev-parse", "main"), main)
        self.assertEqual(self.remote_git("rev-list", "--count", "work-snapshots"), "1")
        published = self.remote_git("ls-tree", "--name-only", "work-snapshots").split()
        local = sorted(p.name for p in self.work.iterdir())
        self.assertEqual(sorted(published), local)
        self.assertEqual(len(local), 7)
        today = [n for n in local if not n.startswith(f"{USER}-2020")]
        self.assertEqual(len(today), 1)
        self.assertNotIn(f"{USER}-20200101.tar.gz.gpg", local)
        with tarfile.open(self.work / today[0]) as t:     # the fake gpg doesn't encrypt
            self.assertIn(f"{USER}/{USER}/app/unpushed.bundle", t.getnames())

    def test_refuses_default_branch(self):
        """work-snapshots as the remote's default branch (HEAD): no force push, it would wipe the Plane dumps."""
        self.run_offsite()
        snap = self.remote_git("rev-parse", "work-snapshots")
        self.remote_git("symbolic-ref", "HEAD", "refs/heads/work-snapshots")
        r = self.run_offsite(rc=1)
        self.assertIn("default branch", r.stderr)
        self.assertIn("Default branch: main", r.stderr)
        self.assertEqual(self.remote_git("rev-parse", "work-snapshots"), snap, "pushed anyway")

    def test_refuses_foreign_branch(self):
        """A remote work-snapshots with anything but *.tar.gz.gpg at the top isn't ours: not replaced."""
        self.run_offsite()
        other = self.tmp / "other"
        self.git(self.tmp, "clone", "-q", "--branch", "work-snapshots", str(self.remote), str(other))
        (other / "notes.txt").write_text("not a snapshot\n")
        self.git(other, "add", "notes.txt")
        self.git(other, "commit", "-qm", "someone else's work")
        self.git(other, "push", "-q", "origin", "work-snapshots")
        theirs = self.remote_git("rev-parse", "work-snapshots")
        r = self.run_offsite(rc=1)
        self.assertIn("isn't ours", r.stderr)
        self.assertEqual(self.remote_git("rev-parse", "work-snapshots"), theirs, "pushed anyway")

    def test_accepts_own_snapshots_from_elsewhere(self):
        """A snapshot branch this server didn't push (new server, same repo) is replaced as usual."""
        self.run_offsite()
        shutil.rmtree(self.home / "backups" / "offsite-work")
        self.run_offsite()
        self.run_offsite()      # the shallow fetch above leaves the local repo usable
        self.assertEqual(self.remote_git("rev-list", "--count", "work-snapshots"), "1")

    def test_problems_fail_the_run(self):
        with open(self.app / "big.bin", "wb") as f:     # over the 20 MB limit: reported, so cron alerts
            f.truncate(21 * 1024 * 1024)
        r = self.run_offsite(rc=1)
        self.assertIn("big.bin", r.stderr)
        self.assertEqual(len(self.remote_git("ls-tree", "--name-only", "work-snapshots").split()), 7)

    def test_area_switched_off(self):
        self.run_offsite()      # a snapshot from when the area was still on
        with open(self.env["NORI_CONF"], "a") as f:
            f.write(f"AREA_{USER}_WORK_BACKUP=false\n")
        (self.tmp / "bin" / "sudo").write_text("#!/bin/sh\nexit 97\n")     # must not collect at all
        before = sorted(p.name for p in self.work.iterdir())
        r = self.run_offsite()
        self.assertIn(f"{USER} skipped", r.stdout)
        self.assertEqual(sorted(p.name for p in self.work.iterdir()), before, "collected or deleted anyway")
        self.assertEqual(self.remote_git("ls-tree", "--name-only", "work-snapshots"), "", "the area is still published")


if __name__ == "__main__":
    unittest.main()
