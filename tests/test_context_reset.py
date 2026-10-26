"""Context reset: usage-snapshot writes the main session's context %, ops-bot decides when to hand off + /clear."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from helpers import REPO
from test_ops_bot import load_ops_bot


class Snapshot(unittest.TestCase):
    """usage-snapshot writes the context % only for the main chat session."""

    def run_snap(self, payload=None, **env):
        home = tempfile.mkdtemp()
        Path(home, ".claude").mkdir()
        payload = payload or {"session_id": "abc-123", "context_window": {"used_percentage": 83.5},
                              "rate_limits": {"five_hour": {"used_percentage": 10, "resets_at": 1}}}
        subprocess.run([sys.executable, "-I", str(REPO / "server/bin/usage-snapshot")], input=json.dumps(payload),
                       text=True, env={"HOME": home, "PATH": os.environ["PATH"], **env}, capture_output=True, check=True)
        return Path(home, ".claude")

    def test_main_session_writes_context(self):
        d = self.run_snap(CLAUDE_TMUX_SESSION="claude-main")
        snap = json.loads((d / "context-claude-main.json").read_text())
        self.assertEqual((snap["pct"], snap["session_id"]), (83.5, "abc-123"))
        self.assertTrue((d / "usage-snapshot.json").exists())

    def test_fresh_session_without_pct_still_writes(self):
        d = self.run_snap({"session_id": "new"}, CLAUDE_TMUX_SESSION="claude-main")
        snap = json.loads((d / "context-claude-main.json").read_text())
        self.assertEqual((snap["session_id"], snap["pct"]), ("new", None))

    def test_pool_and_plain_sessions_do_not(self):
        for env in ({}, {"CLAUDE_TMUX_SESSION": "claude-main", "CLAUDE_POOL": "1"}):
            d = self.run_snap(**env)
            self.assertEqual(list(d.glob("context-*.json")), [], env)


class Skip(unittest.TestCase):
    """context_skip: each condition blocks on its own; all clear -> None."""

    def setUp(self):
        self._env = dict(os.environ)
        self.m = load_ops_bot()
        self.now = time.time()
        self.ok = dict(snap={"ts": self.now - 30, "session_id": "s1", "pct": 85}, last={}, now=self.now,
                       local_min=14 * 60, quiet_for=900, blocker=None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def skip(self, **over):
        return self.m.context_skip(**{**self.ok, **over})

    def test_all_clear(self):
        self.assertIsNone(self.skip())
        self.assertIsNone(self.skip(snap={**self.ok["snap"], "pct": 80}))   # exactly the default threshold

    def test_each_condition_blocks(self):
        cases = {
            "no snapshot": dict(snap=None),
            "below": dict(snap={**self.ok["snap"], "pct": 79.9}),
            "cooldown": dict(last={"at": self.now - 600}),
            "same session after reset": dict(last={"at": self.now - 7200, "sid": "s1"}),
            "night start": dict(local_min=3 * 60 + 15),
            "night 03:45": dict(local_min=3 * 60 + 45),
            "busy recently": dict(quiet_for=300),
            "no transcript": dict(quiet_for=None),
            "dialog": dict(blocker="busy: showing a dialog"),
            "working": dict(blocker="working"),
        }
        for name, over in cases.items():
            self.assertTrue(self.skip(**over), name)

    def test_window_edges(self):
        self.assertEqual(self.m.CTX_NIGHT, (3 * 60 + 15, 4 * 60 + 30))   # defaults: HANDOFF_TIME 03:45, AUTO_REBOOT_TIME 04:30
        self.assertIsNone(self.skip(local_min=3 * 60 + 14))
        self.assertIsNone(self.skip(local_min=4 * 60 + 30))
        self.assertIsNone(self.skip(last={"at": self.now - 3601}))
        self.assertTrue(self.m.in_window(10, (23 * 60 + 50, 60)))         # a window over midnight
        self.assertFalse(self.m.in_window(120, (23 * 60 + 50, 60)))

    def test_user_turn_since(self):
        line = lambda ts, content, **kw: json.dumps({"type": "user", "timestamp": ts, "message": {"content": content}, **kw})
        t0 = 1_800_000_000
        iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(t))
        old = line(iso(t0 - 60), "<channel source=\"plugin:telegram\">hi</channel>")
        ours = line(iso(t0 + 5), self.m.CTX_PROMPT.format(pct=82, f="/x"))
        tool = line(iso(t0 + 6), [{"type": "tool_result", "content": "ok"}])
        side = line(iso(t0 + 7), "subagent prompt", isSidechain=True)
        meta = line(iso(t0 + 8), "Base directory for this skill: /x", isMeta=True)
        q = lambda mode, prompt: json.dumps({"type": "attachment", "timestamp": iso(t0 + 9),
                                             "attachment": {"type": "queued_command", "commandMode": mode, "prompt": prompt}})
        notif = q("task-notification", "<task-notification>done</task-notification>")
        self.assertFalse(self.m.user_turn_since("\n".join([old, ours, tool, side, meta, notif, "junk"]), t0))
        self.assertTrue(self.m.user_turn_since(q("prompt", "<channel source=\"plugin:telegram\">wait</channel>"), t0))
        for new in ("<channel source=\"plugin:telegram\">wait</channel>",       # chat
                    "[Owner tapped on Telegram] Q: x → A",                         # tap-to-answer
                    [{"type": "text", "text": "from Remote Control"}]):            # Remote Control / attach
            self.assertTrue(self.m.user_turn_since("\n".join([ours, line(iso(t0 + 9), new)]), t0), new)

    def test_main_transcript_rejects_odd_ids(self):
        self.assertTrue(str(self.m.main_transcript("main", {"session_id": "ab-12"})).endswith("/ab-12.jsonl"))
        for sid in ("", "../x", "a/b", None):
            self.assertIsNone(self.m.main_transcript("main", {"session_id": sid}), sid)


if __name__ == "__main__":
    unittest.main()
