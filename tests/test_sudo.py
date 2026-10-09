"""How the automation uses sudo (ADMIN_SUDO=limited only allows these two forms without a password):
  sudo [-n] -u <area> ...             run as an area user
  sudo [-n] nori-root <subcommand>    the root helper, server/sbin/nori-root
Every other sudo call in setup.sh, setup-user.sh or server/bin/* fails this test. bootstrap.sh runs as root
and is not checked. Text for the human ("Run: sudo ufw allow ...") is fine: only sudo in command position
counts. Known blind spot: sudo hidden inside a quoted `bash -c "..."` string is not seen; don't do that.
"""
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import REPO, shebang

HELPER_CMDS = re.findall(r"^  ([a-z-]+)\)", (REPO / "server/sbin/nori-root").read_text(), re.M)
# shell: sudo at the start of a command (line start, after ; & | ( { ! $( ` or a keyword)
SH_CALL = re.compile(r"(?:^|[;&|({!`]|\$\(|\b(?:then|do|else|exec|if|while|until|time)\s)\s*sudo\b(.*)")
SH_AREA = re.compile(r"^\s+(?:-n\s+)?-u\s+\"?\$\{?[A-Za-z_]\w*\}?\"?\s")
SH_HELPER = re.compile(r"^\s+(?:-n\s+)?nori-root\s+([a-z-]+)\b")
# python: a "sudo" element in an argument list
PY_CALL = re.compile(r"""["']sudo["']\s*,(.*)""")
PY_AREA = re.compile(r"""^\s*["']-n["']\s*,\s*["']-u["']\s*,\s*[A-Za-z_]\w*\s*,""")


def checked_files():
    files = [REPO / "setup.sh", REPO / "setup-user.sh"]
    files += sorted(p for p in (REPO / "server/bin").iterdir() if p.is_file())
    return files


class SudoUsage(unittest.TestCase):
    def test_helper_subcommands_found(self):
        self.assertTrue({"version", "sync-opt", "link-bin", "docker-dropin", "ufw-status", "gai-conf"} <= set(HELPER_CMDS))

    def test_only_area_users_and_nori_root(self):
        calls = 0
        for p in checked_files():
            is_py = "python" in shebang(p)
            for n, line in enumerate(p.read_text().splitlines(), 1):
                code = line.split("#", 1)[0] if not is_py else line
                if code.lstrip().startswith("#"):
                    continue
                where = f"{p.relative_to(REPO)}:{n}: {line.strip()}"
                if is_py:
                    for m in PY_CALL.finditer(code):
                        calls += 1
                        self.assertRegex(m.group(1), PY_AREA, f"sudo must be sudo -n -u <area>: {where}")
                    continue
                for m in SH_CALL.finditer(code):
                    calls += 1
                    rest = m.group(1)
                    if SH_AREA.match(rest):
                        self.assertNotRegex(rest, r"-u\s+\"?root\b", where)
                        continue
                    h = SH_HELPER.match(rest)
                    self.assertTrue(h and h.group(1) in HELPER_CMDS,
                                    f"sudo may only be `sudo -u <area>` or `sudo nori-root <subcommand>`: {where}")
        self.assertGreater(calls, 10, "the checker found suspiciously few sudo calls")

    def test_checker_catches_broad_root_calls(self):
        for bad in ('sudo rsync -a x /opt/nori', '  sudo ln -sfn a b', 'x && sudo install -m 600 a b',
                    'out=$(sudo cat /etc/shadow)', 'sudo -u root id', 'sudo nori-root rm -rf /'):
            m = SH_CALL.search(bad)
            with self.subTest(line=bad):
                self.assertIsNotNone(m)
                rest = m.group(1)
                ok_area = SH_AREA.match(rest) and not re.search(r"-u\s+\"?root\b", rest)
                h = SH_HELPER.match(rest)
                self.assertFalse(ok_area or (h and h.group(1) in HELPER_CMDS))
        self.assertIsNone(SH_CALL.search('note "warning: run: sudo ufw allow in on tailscale0"'))


class BootstrapPlan(unittest.TestCase):
    def plan(self, extra=""):
        with tempfile.TemporaryDirectory() as tmp:
            conf = Path(tmp) / "nori.conf"
            conf.write_text('ADMIN_USER="admin"\nAREAS="main"\n' + extra)
            env = {k: v for k, v in os.environ.items() if not k.startswith(("AREA_", "NORI_", "ADMIN_"))}
            env["NORI_CONF"] = str(conf)
            r = subprocess.run(["bash", str(REPO / "bootstrap.sh"), "--plan"], env=env,
                               capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_plan_shows_admin_sudo(self):
        self.assertRegex(self.plan(), r"admin sudo : limited")
        self.assertRegex(self.plan('ADMIN_SUDO="full"\n'), r"admin sudo : full")

    def test_limited_needs_classic_sudo(self):
        # Ubuntu 26.04 ships sudo-rs: limited must not be applied there until it is tested
        text = (REPO / "bootstrap.sh").read_text()
        gate = text.index('!= "Sudo version "*')
        self.assertLess(gate, text.index("ALL=(ALL) ALL"), "the sudo-rs gate must run before the limited rule is written")
        self.assertRegex(self.plan(), r"classic sudo")


if __name__ == "__main__":
    unittest.main()
