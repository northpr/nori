"""morning-summary: fact collection (--facts-only) and prompt text. No network, no claude."""
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "server" / "bin" / "morning-summary"


def git(cwd, *args, env=None):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=env)


class MorningSummaryFacts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / "nori/scripts").mkdir(parents=True)
        (self.home / "nori/scripts/conf.sh").write_text('AREAS="x"\n')
        # fake gh: always unavailable, so nothing touches the network
        (self.home / ".local/bin").mkdir(parents=True)
        gh = self.home / ".local/bin/gh"
        gh.write_text("#!/bin/sh\nexit 1\n")
        gh.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def make_repo(self, name, days_old):
        repo = self.home / "projects" / name
        repo.mkdir(parents=True)
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e.x",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@e.x",
                   GIT_CONFIG_GLOBAL="/dev/null")
        git(repo, "init", "-q", env=env)
        (repo / "README.md").write_text("# Title\n\nA tiny demo tool.\n")
        git(repo, "add", ".", env=env)
        date = f"{int(time.time()) - days_old * 86400} +0000"
        env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        git(repo, "commit", "-q", "-m", "init", env=env)

    def facts(self):
        env = dict(os.environ, HOME=str(self.home), GIT_CONFIG_GLOBAL="/dev/null")
        r = subprocess.run(["bash", str(SCRIPT), "--facts-only"], env=env,
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_days_since_last_commit_and_about(self):
        self.make_repo("old", 45)
        self.make_repo("fresh", 0)
        out = self.facts()
        old = out.split("== old ==")[1].split("==")[0]
        fresh = out.split("== fresh ==")[1].split("==")[0]
        self.assertRegex(old, r"days since last commit: 4[45]\b")
        self.assertRegex(fresh, r"days since last commit: 0\b")
        self.assertIn("about: A tiny demo tool.", old)

    def test_prompt_asks_for_top3_and_quiet_section(self):
        text = SCRIPT.read_text()
        self.assertIn("only the 3 repos with the fewest days since last commit", text)
        self.assertIn("more than 30 days since last commit", text)
        self.assertIn("at most 5", text)
        self.assertIn("'+N more'", text)


if __name__ == "__main__":
    unittest.main()
