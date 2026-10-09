"""Argument checks of server/sbin/nori-root, the root helper (dry-run mode: nothing is changed)."""
import os
import re
import subprocess
import tempfile
import unittest

from helpers import REPO

HELPER = REPO / "server/sbin/nori-root"


def run(*args, dry=True, sudo_user="admin"):
    env = {k: v for k, v in os.environ.items() if k not in ("NORI_ROOT_DRYRUN", "SUDO_USER")}
    if dry:
        env["NORI_ROOT_DRYRUN"] = "1"
    if sudo_user:
        env["SUDO_USER"] = sudo_user
    return subprocess.run(["bash", str(HELPER), *args], env=env, capture_output=True, text=True, timeout=30)


@unittest.skipIf(os.geteuid() == 0, "dry-run is ignored when running as root")
class NoriRootArgs(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = os.path.realpath(tmp.name)

    def assertRejected(self, *args, **kw):
        r = run(*args, **kw)
        self.assertEqual(r.returncode, 2, f"{args} should be rejected: {r.stdout}{r.stderr}")
        self.assertNotIn("would", r.stdout)

    def test_version_matches_the_file(self):
        want = re.search(r"^NORI_ROOT_VERSION=(\S+)$", HELPER.read_text(), re.M).group(1)
        self.assertEqual(run("version").stdout.strip(), want)
        self.assertRejected("version", "extra")

    def test_unknown_subcommand(self):
        for cmd in ("", "bogus", "rm", "sync-opt-now", "--version"):
            with self.subTest(cmd=cmd):
                self.assertRejected(*([cmd] if cmd else []))
        self.assertIn("nori-root link-bin attach|recall", run("--help").stderr)   # usage lists the subcommands

    def test_link_bin_only_attach_and_recall(self):
        for name in ("attach", "recall"):
            r = run("link-bin", name)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(f"/usr/local/bin/{name} -> /opt/nori/server/bin/{name}", r.stdout)
        for bad in ("ops-bot", "bash", "../attach", "attach/../../x", "/opt/nori/server/bin/attach", "attach "):
            with self.subTest(name=bad):
                self.assertRejected("link-bin", bad)
        self.assertRejected("link-bin")
        self.assertRejected("link-bin", "attach", "recall")

    def test_sync_opt_paths(self):
        r = run("sync-opt", self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("would pack", r.stdout)
        self.assertEqual(run("sync-opt", "--check", self.repo + "/").returncode, 0)
        for bad in ("relative/path", "nori", "/home/admin/../../etc", "/home/admin/nori/..", "/a/./b", "/a//b",
                    "/a;b", "/a b", "/a$(id)", "/", ""):
            with self.subTest(path=bad):
                self.assertRejected("sync-opt", bad)
        self.assertRejected("sync-opt")
        self.assertRejected("sync-opt", self.repo, self.repo)
        self.assertRejected("sync-opt", "--delete", self.repo)

    def test_sync_opt_needs_the_admin_via_sudo(self):
        self.assertRejected("sync-opt", self.repo, sudo_user="root")
        self.assertRejected("sync-opt", self.repo, sudo_user="")
        self.assertRejected("sync-opt", self.repo, sudo_user="bad;user")

    def test_docker_dropin_and_ufw(self):
        self.assertEqual(run("docker-dropin").returncode, 0)
        self.assertRejected("docker-dropin", "/tmp/evil.conf")
        self.assertEqual(run("ufw-status").returncode, 0)
        self.assertRejected("ufw-status", "allow", "22")

    def test_gai_conf(self):
        for args in ((), ("--remove",)):
            self.assertEqual(run("gai-conf", *args).returncode, 0, args)
        for bad in (("/tmp/evil.conf",), ("--check", "x"), ("--delete",), ("--remove", "--check"), ("--force",)):
            with self.subTest(args=bad):
                self.assertRejected("gai-conf", *bad)

    def test_gai_conf_text_matches_the_repo_file(self):
        # the helper carries the text itself (root never reads a file the admin controls); the shipped file must equal it
        m = re.search(r"gai_text\(\) \{\n  cat <<'EOF'\n(.*?)\nEOF\n", HELPER.read_text(), re.S)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1) + "\n", (REPO / "server/net/gai.conf").read_text())
        self.assertRegex(m.group(1), r"(?m)^precedence ::ffff:0:0/96\s+100$")

    def test_setup_gates_gai_conf_on_prefer_ipv4(self):
        text = (REPO / "setup.sh").read_text()
        on = text.index("if is_on PREFER_IPV4; then")
        off = text.index("elif sudo -n nori-root gai-conf --check; then", on)
        self.assertIn("nori-root gai-conf --check", text[on:off])          # on: install only when it differs (--check drift)
        self.assertNotIn("--remove", text[on:off])
        self.assertIn("nori-root gai-conf --remove", text[off:off + 600])  # off: remove only a file that is exactly ours

    def test_refuses_without_root(self):
        for args in (("sync-opt", self.repo), ("link-bin", "attach"), ("docker-dropin",), ("ufw-status",), ("gai-conf",)):
            with self.subTest(args=args):
                r = run(*args, dry=False)
                self.assertEqual(r.returncode, 2)
                self.assertIn("sudo", r.stderr)

    def test_dropin_content_is_inside_the_helper(self):
        text = HELPER.read_text()
        self.assertIn("After=tailscaled.service", text)
        self.assertNotRegex(text, r"docker-after-tailscale\.conf", "the drop-in must not be read from the repo")


if __name__ == "__main__":
    unittest.main()
