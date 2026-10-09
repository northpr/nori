"""nori_claude_plan (scripts/conf.sh): when bootstrap.sh / setup.sh install, keep or downgrade Claude Code."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import REPO


def plan(have, want, explicit=""):
    with tempfile.TemporaryDirectory() as tmp:
        conf = Path(tmp) / "nori.conf"
        conf.write_text('AREAS="main"\n' + (f'CLAUDE_CODE_VERSION="{explicit}"\n' if explicit else ""))
        env = {k: v for k, v in os.environ.items() if not k.startswith(("AREA_", "NORI_", "CLAUDE_CODE"))}
        env.update(NORI_CONF=str(conf), NORI_ROOT=str(REPO))
        r = subprocess.run(["bash", "-c", '. "$NORI_ROOT/scripts/conf.sh" && nori_claude_plan "$1" "$2"', "_", have, want],
                           env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


class ClaudePlan(unittest.TestCase):
    def test_same_version(self):
        self.assertEqual(plan("2.1.294", "2.1.294"), "ok")

    def test_older_installed_is_upgraded(self):
        self.assertEqual(plan("2.1.281", "2.1.294"), "install")
        self.assertEqual(plan("", "2.1.294"), "install")                 # unknown: install

    def test_newer_installed_is_kept_without_explicit_setting(self):
        self.assertEqual(plan("2.1.300", "2.1.294"), "keep-newer")
        self.assertEqual(plan("2.1.100", "2.1.94"), "keep-newer")       # version order, not string order

    def test_downgrade_only_when_asked_in_nori_conf(self):
        self.assertEqual(plan("2.1.300", "2.1.294", explicit="2.1.294"), "downgrade")

    def test_channels_always_install(self):
        for ch in ("stable", "latest"):
            self.assertEqual(plan("2.1.300", ch, explicit=ch), "install")


if __name__ == "__main__":
    unittest.main()
