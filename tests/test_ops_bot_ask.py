"""ask-owner in server/bin/ops-bot: stale outbox requests are parked, lost taps don't block later ones."""
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from test_ops_bot import load_ops_bot

RULE = "─" * 40
FOOT = f"{RULE}\n  5h 5% · wk 79%\n  ⏵⏵ auto mode on (shift+tab to cycle)\n"


def box(*prompt):
    return f"● Done.\n\n{RULE}\n❯ " + "\n".join(prompt) + "\n" + FOOT


class AskPoll(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        self.m = load_ops_bot()
        self.m.AREAS = ["personal"]
        self.root = Path(tempfile.mkdtemp())
        self.m.area_home = lambda area: self.root / area

        def as_user(area, *cmd, **kw):  # run locally instead of via sudo
            p = subprocess.run(cmd, capture_output=True, text=True)
            return p.returncode, p.stdout.strip()
        self.m.as_user = as_user
        self.posted = []
        self.m.ask_post = lambda area, req: self.posted.append(req["id"]) or True
        self.box = self.root / "personal/.ask-owner"
        (self.box / "outbox").mkdir(parents=True)

    def tearDown(self):
        os.environ.clear(); os.environ.update(self._env)

    def put(self, rid, age):
        req = {"id": rid, "area": "personal", "question": "Q?", "options": ["A: x", "B: y"], "created": int(time.time() - age)}
        (self.box / "outbox" / f"{rid}.json").write_text(json.dumps(req))

    def test_fresh_posted_once_stale_parked(self):
        self.put("fresh", 10); self.put("old", self.m.ASK_MAX_AGE + 60)
        self.m.ask_poll(); self.m.ask_poll()
        self.assertEqual(self.posted, ["fresh"])
        self.assertEqual(sorted(p.name for p in (self.box / "sent").iterdir()), ["fresh.json", "stale-old.json"])
        self.assertEqual(list((self.box / "outbox").iterdir()), [])

    def test_junk_parked_as_bad(self):
        (self.box / "outbox" / "junk.json").write_text("{nope")
        self.m.ask_poll()
        self.assertEqual(self.posted, [])
        self.assertTrue((self.box / "sent" / "bad-junk.json").exists())


class StaleDraft(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        self.m = load_ops_bot()

    def tearDown(self):
        os.environ.clear(); os.environ.update(self._env)

    def test_leftover_tap_counts_as_idle(self):
        m = self.m
        self.assertTrue(m.input_box_idle(box(f"{m.ASK_MARK} Q: Fix it? → A: yes")))
        self.assertTrue(m.input_box_idle(box(f'{m.DOIT_MARK} Work on SRV-1 ("x")', "  wrapped rest of it")))
        self.assertFalse(m.input_box_idle(box("half-typed message from the owner")))
        self.assertFalse(m.input_box_idle(box(f"{m.ASK_MARK} Q", "1. Yes", "2. No", "Esc to cancel")))

    def run_type(self, screens):
        m, sent, caps = self.m, [], list(screens)

        def as_user(area, *cmd, **kw):
            if "send-keys" in cmd:
                sent.append(cmd[cmd.index("-t") + 2]); return 0, ""
            return 0, caps.pop(0) if caps else box("")
        m.as_user = as_user
        return m.ask_type("personal", f"{m.ASK_MARK} Q: Fix? → A: yes", settle=0), sent

    def test_type_ok_when_box_clears(self):
        ok, sent = self.run_type([box("")])
        self.assertTrue(ok); self.assertEqual(sent, ["C-u", "-l", "Enter"])

    def test_lost_enter_retried_once(self):
        stuck = box(f"{self.m.ASK_MARK} Q: Fix? → A: yes")
        ok, sent = self.run_type([stuck, box("")])
        self.assertTrue(ok); self.assertEqual(sent, ["C-u", "-l", "Enter", "Enter"])

    def test_still_stuck_is_cleared_and_fails(self):
        stuck = box(f"{self.m.ASK_MARK} Q: Fix? → A: yes")
        ok, sent = self.run_type([stuck, stuck])
        self.assertFalse(ok); self.assertEqual(sent, ["C-u", "-l", "Enter", "Enter", "C-u"])


if __name__ == "__main__":
    unittest.main()
