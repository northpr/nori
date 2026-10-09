"""Unit tests for pure helpers in server/bin/ops-bot (loaded with a throwaway HOME, no network)."""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import unittest

from helpers import REPO


def load_ops_bot():
    home = tempfile.mkdtemp()
    os.environ["HOME"] = home
    os.environ["NORI_ROOT"] = home          # no nori.conf here, so defaults apply
    os.environ.pop("NORI_CONF", None)
    old_argv = sys.argv
    sys.argv = ["ops-bot"]
    try:
        loader = importlib.machinery.SourceFileLoader("ops_bot", str(REPO / "server/bin/ops-bot"))
        spec = importlib.util.spec_from_loader("ops_bot", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)   # main() only runs under __main__
        return mod
    finally:
        sys.argv = old_argv


class OpsBotHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._env = dict(os.environ)
        cls.m = load_ops_bot()

    @classmethod
    def tearDownClass(cls):
        os.environ.clear()
        os.environ.update(cls._env)

    def test_short_keeps_short_text(self):
        self.assertEqual(self.m._short("hello", 10), "hello")

    def test_short_cuts_at_word_boundary(self):
        out = self.m._short("fix the broken login page now", 15)
        self.assertTrue(out.endswith("…"))
        self.assertLessEqual(len(out), 16)
        self.assertFalse(out.startswith("fix the broken login"))

    def test_labels(self):
        issue = {"labels": [{"name": "auto"}, {"name": "bug"}, "stray-string"]}
        self.assertEqual(self.m._labels(issue), {"auto", "bug"})
        self.assertEqual(self.m._labels({}), set())

    def test_inv_priority(self):
        mk = lambda *n: {"labels": [{"name": x} for x in n]}
        self.assertEqual(self.m._inv(mk("bug")), "")
        self.assertEqual(self.m._inv(mk("needs-me")), "needs-me")
        self.assertEqual(self.m._inv(mk("needs-me", "auto")), "auto")


if __name__ == "__main__":
    unittest.main()
