import contextlib, importlib.machinery, io, json, os, sys, tempfile, time, unittest
from pathlib import Path
from unittest import mock
REPO = Path(__file__).resolve().parents[1]


class Board(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(); os.environ["HOME"] = self.home
        for k in ("AGENT_BOARD_CAP", "AGENT_BOARD_CAP_HIGH", "AGENT_BOARD_CHAT", "CLAUDE_POOL", "TELEGRAM_STATE_DIR"):
            os.environ.pop(k, None)
        self.m = importlib.machinery.SourceFileLoader("agent_board", str(REPO / "server/bin/agent-board")).load_module()
        self.calls = []
        self.m.tg = self.fake_tg
        self.replies = {}
        self.t = 1_000_000.0
        self.m.now = lambda: self.t

    def fake_tg(self, method, **p):
        self.calls.append((method, p))
        r = self.replies.get(method)
        if callable(r):
            r = r()
        return r or {"ok": True, "result": {"message_id": 7}}

    def telegram(self, chat="-100"):
        d = Path(self.home, ".claude/channels/telegram-" + __import__("getpass").getuser()); d.mkdir(parents=True)
        (d / ".env").write_text('TELEGRAM_BOT_TOKEN="tok123"\n')
        os.environ["AGENT_BOARD_CHAT"] = chat

    def hook(self, inp, raw=None):
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(raw if raw is not None else json.dumps(inp))), contextlib.redirect_stdout(out):
            self.m.hook()
        return out.getvalue()

    def pre(self, desc="task", **kw):
        return self.hook({"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "s", "tool_input": {"description": desc, **kw}})

    def test_other_tools_are_ignored(self):
        self.hook({"hook_event_name": "PreToolUse", "tool_name": "TaskStop", "tool_input": {"description": "x"}})
        with self.m.locked() as st:
            self.assertEqual(st["pending"], [])

    def start(self, aid, typ="general-purpose"):
        return self.hook({"hook_event_name": "SubagentStart", "agent_id": aid, "agent_type": typ, "session_id": "s"})

    def stop(self, aid):
        return self.hook({"hook_event_name": "SubagentStop", "agent_id": aid})

    def state(self):
        return json.loads(Path(self.home, ".agent-board/state.json").read_text())

    def snapshot(self, five=0, seven=0, ts=None):
        Path(self.home, ".claude").mkdir(exist_ok=True)
        Path(self.home, ".claude/usage-snapshot.json").write_text(json.dumps(
            {"ts": self.t if ts is None else ts, "five_hour": {"used_percentage": five}, "seven_day": {"used_percentage": seven}}))

    def fill(self, n):
        for i in range(n):
            self.pre(f"t{i}"); self.start(f"a{i}")

    def test_pre_queues_pending(self):
        self.assertEqual(self.pre("x" * 80, subagent_type="Explore", model="haiku"), "")
        p = self.state()["pending"]
        self.assertEqual((len(p[0]["label"]), p[0]["type"], p[0]["model"]), (60, "Explore", "haiku"))
        self.pre("y")
        self.assertEqual(self.state()["pending"][1]["type"], "general-purpose")

    def test_cap_denies(self):
        self.fill(3); self.pre("p1"); self.pre("p2")  # 3 running + 2 pending
        out = json.loads(self.pre("one more"))["hookSpecificOutput"]
        self.assertEqual((out["hookEventName"], out["permissionDecision"]), ("PreToolUse", "deny"))
        self.assertIn("5 agents already running (cap 5)", out["permissionDecisionReason"])
        self.assertEqual(len(self.state()["pending"]), 2)

    def test_high_usage_cap_3(self):
        self.snapshot(five=85); self.fill(3)
        self.assertIn("cap 3, Max usage high", self.pre())
        self.snapshot(seven=90)
        self.assertIn("cap 3", self.pre())

    def test_stale_or_low_snapshot_ignored(self):
        self.snapshot(five=99, ts=self.t - 1900); self.fill(3)
        self.assertEqual(self.pre(), "")
        self.snapshot(five=50, seven=50)
        self.assertEqual(self.m.caps(), (5, False))
        Path(self.home, ".claude/usage-snapshot.json").write_text("garbage")
        self.assertEqual(self.m.caps(), (5, False))

    def test_env_override(self):
        os.environ["AGENT_BOARD_CAP"] = "1"; self.fill(1)
        self.assertIn("cap 1", self.pre())
        os.environ["AGENT_BOARD_CAP_HIGH"] = "2"; os.environ["AGENT_BOARD_CAP"] = "9"; self.snapshot(five=80)
        self.assertEqual(self.m.caps(), (2, True))

    def test_pending_expires(self):
        self.fill(4); self.pre("old"); self.t += 121
        self.assertEqual(self.pre("new"), "")

    def test_start_label_from_pending(self):
        self.pre("first", subagent_type="Explore"); self.pre("second", subagent_type="Plan", model="opus")
        self.start("b", "Plan"); self.start("a", "Explore"); self.start("c", "Other")
        rows = {r["id"]: r for r in self.state()["rows"]}
        self.assertEqual((rows["b"]["label"], rows["b"]["model"], rows["a"]["label"], rows["c"]["label"]), ("second", "opus", "first", "Other"))
        self.assertEqual(self.state()["pending"], [])
        self.pre("x", subagent_type="Explore"); self.start("d", "Plan")  # no type match: oldest
        self.assertEqual(self.state()["rows"][-1]["label"], "x")

    def test_stop_marks_done_and_pings_only_when_long(self):
        self.telegram(); self.pre("quick"); self.start("a"); self.pre("slow"); self.start("b")
        self.t += 179; self.stop("a")
        self.assertFalse([c for c in self.calls if c[1].get("text", "").startswith("[")])
        self.t += 1; self.stop("b")
        pings = [c for c in self.calls if "finished" in c[1].get("text", "")]
        self.assertEqual(len(pings), 1)
        self.assertIn("✅ slow finished · 3m", pings[0][1]["text"])
        self.assertNotIn("disable_notification", pings[0][1])
        self.assertEqual([r["status"] for r in self.state()["rows"]], ["done", "done"])

    def test_expire(self):
        self.fill(1); self.t += 3 * 3600 + 1
        with self.m.locked() as st:
            self.assertEqual(st["rows"][0]["status"], "lost")
        self.t += 24 * 3600 + 1
        with self.m.locked() as st:
            self.assertEqual(st["rows"], [])

    def test_finished_trimmed_to_5(self):
        for i in range(8):
            self.pre(f"t{i}"); self.start(f"a{i}"); self.t += 1; self.stop(f"a{i}")
        self.assertEqual([r["id"] for r in self.state()["rows"]], [f"a{i}" for i in range(3, 8)])

    def test_render(self):
        user = __import__("getpass").getuser()
        st = {"rows": [], "pending": [], "board": {}}
        self.assertIn("(nothing running)", self.m.render(st))
        t = self.t
        st["rows"] = [
            {"id": "x", "label": "Explore repo", "started": t - 200, "ended": t - 80, "status": "done"},
            {"id": "a", "label": "APP-7 fix", "started": t - 200, "status": "running"},
            {"id": "b", "label": "APP-4", "started": t - 10, "status": "running"},
            {"id": "", "label": "APP-1", "started": t, "status": "waiting", "note": "waiting for your pick"},
            {"id": "c", "label": "gone", "started": t - 9, "ended": t, "status": "lost"},
            {"id": "d", "label": "APP-5", "started": t - 70, "status": "running", "note": "need input"}]
        lines = self.m.render(st).splitlines()
        self.assertRegex(lines[0], rf"^🤖 Agents · {user} · \d\d:\d\d$")
        self.assertEqual(lines[1:], ["⚙️ APP-7 fix · 3m", "⚙️ APP-4 · <1m", "🧠 APP-1 · waiting for your pick", "🧠 APP-5 · need input",
                                     "✅ Explore repo · 2m", "⚠️ gone · lost"])

    def test_note_and_clear_cli(self):
        self.fill(1)
        self.m.cli(["note", "a0", "waiting for your pick"])
        self.assertEqual(self.state()["rows"][0]["note"], "waiting for your pick")
        self.m.cli(["clear", "t0"])
        self.assertNotIn("note", self.state()["rows"][0])
        self.m.cli(["note", "APP-1", "your call"])
        r = self.state()["rows"][-1]
        self.assertEqual((r["status"], r["id"]), ("waiting", ""))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.m.cli(["show"])
        self.assertIn("🧠 APP-1 · your call", out.getvalue())
        self.m.cli(["clear", "APP-1"])
        self.assertEqual(len(self.state()["rows"]), 1)

    def test_telegram_send_pin_then_edit(self):
        self.telegram(); self.pre("job"); self.start("a")
        self.assertEqual([c[0] for c in self.calls], ["sendMessage", "pinChatMessage"])
        self.assertEqual((self.calls[0][1]["chat_id"], self.calls[0][1]["disable_notification"], self.calls[1][1]["disable_notification"]), ("-100", True, True))
        self.assertEqual(self.state()["board"]["message_id"], 7)
        self.calls.clear(); self.t += 5; self.stop("a")
        self.assertEqual([c[0] for c in self.calls], ["editMessageText"])
        self.assertEqual(self.calls[0][1]["message_id"], 7)

    def test_telegram_not_modified_ignored(self):
        self.telegram(); self.pre("job"); self.start("a"); self.calls.clear()
        self.replies["editMessageText"] = {"ok": False, "description": "Bad Request: message is not modified"}
        self.stop("a")
        self.assertEqual([c[0] for c in self.calls], ["editMessageText"])

    def test_telegram_edit_failure_sends_new(self):
        self.telegram(); self.pre("job"); self.start("a"); self.calls.clear()
        self.replies["editMessageText"] = {"ok": False, "description": "message to edit not found"}
        self.replies["sendMessage"] = {"ok": True, "result": {"message_id": 9}}
        self.stop("a")
        self.assertEqual([c[0] for c in self.calls], ["editMessageText", "sendMessage", "unpinChatMessage", "pinChatMessage"])
        self.assertEqual(self.state()["board"]["message_id"], 9)

    def test_telegram_new_day_sends_new(self):
        self.telegram(); self.pre("job"); self.start("a")
        with self.m.locked() as st:
            st["board"]["day"] = "2000-01-01"
        self.calls.clear(); self.stop("a")
        self.assertEqual(self.calls[0][0], "sendMessage")

    def test_pin_error_ignored(self):
        self.telegram(); self.replies["pinChatMessage"] = {"ok": False, "description": "not enough rights"}
        self.pre("job"); self.start("a")
        self.assertEqual(self.state()["board"]["message_id"], 7)

    def test_creds_from_state_dir_env_and_chat_env(self):
        d = Path(self.home, "state"); d.mkdir()
        (d / ".env").write_text("TELEGRAM_BOT_TOKEN=abc\n")
        os.environ["TELEGRAM_STATE_DIR"] = str(d); os.environ["AGENT_BOARD_CHAT"] = "55"
        self.assertEqual(self.m.creds(), ("abc", "55"))
        del os.environ["AGENT_BOARD_CHAT"]
        self.assertEqual(self.m.creds(), ("abc", ""))

    def test_dm_chat_posts_and_pins(self):
        self.telegram(chat="12345")
        self.pre("job"); self.start("a")
        self.assertEqual([c[0] for c in self.calls], ["sendMessage", "pinChatMessage"])
        self.assertEqual(self.calls[0][1]["chat_id"], "12345")

    def test_no_telegram_in_pool_or_without_creds(self):
        self.pre("a"); self.start("x"); self.stop("x")
        self.assertEqual(self.calls, [])
        self.telegram(); os.environ["CLAUDE_POOL"] = "1"
        self.t += 600; self.pre("b"); self.start("y"); self.t += 600; self.stop("y")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.state()["rows"][-1]["status"], "done")
        os.environ["CLAUDE_POOL"] = "0"; os.environ["AGENT_BOARD_CHAT"] = ""
        self.pre("c"); self.start("z")
        self.assertEqual(self.calls, [])

    def test_malformed_input_is_silent(self):
        for raw in ("{not json", "", "[]", '{"hook_event_name": "SubagentStop"}', '{"hook_event_name": "Other"}', "null"):
            self.assertEqual(self.hook(None, raw=raw), "")

    def test_hook_never_raises(self):
        with mock.patch.object(self.m, "locked", side_effect=OSError("boom")):
            self.assertEqual(self.pre(), "")

    def test_stale_rows_from_killed_session_do_not_block(self):
        for i in range(5):
            self.hook({"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "old", "tool_input": {"description": f"o{i}"}})
            self.hook({"hook_event_name": "SubagentStart", "agent_id": f"o{i}", "agent_type": "general-purpose", "session_id": "old"})
        deny = lambda sid: self.hook({"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": sid, "tool_input": {"description": "n"}})
        self.assertIn("deny", deny("old"))
        self.assertEqual(deny("NEW"), "")                       # restarted session starts clean
        self.assertEqual(len(self.state()["pending"]), 1)
        self.m.cli(["reset"])
        self.assertEqual({r["status"] for r in self.state()["rows"]}, {"lost"})
        self.assertEqual(self.state()["pending"], [])
        self.assertEqual(deny("old"), "")

    def test_start_matches_pending_of_own_session(self):
        self.hook({"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "a", "tool_input": {"description": "mine"}})
        self.hook({"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "b", "tool_input": {"description": "theirs"}})
        self.hook({"hook_event_name": "SubagentStart", "agent_id": "x", "agent_type": "general-purpose", "session_id": "b"})
        self.assertEqual(self.state()["rows"][0]["label"], "theirs")

    def test_http_not_done_under_lock(self):
        self.telegram()
        import fcntl
        def probe(method, **p):
            with open(Path(self.home, ".agent-board/lock"), "a") as lk:
                fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)   # raises if the hook still holds the lock
            return {"ok": True, "result": {"message_id": 7}}
        self.m.tg = probe
        self.pre("job"); self.start("a")
        self.assertEqual(self.state()["board"]["message_id"], 7)

    def test_edit_rate_limit_does_not_resend(self):
        self.telegram(); self.pre("job"); self.start("a"); self.calls.clear()
        for desc in ("Too Many Requests: retry after 5", "HTTP 502", "URLError"):
            self.replies["editMessageText"] = {"ok": False, "description": desc}
            self.t += 1; self.pre("x"); self.start(f"b{desc[:3]}")
        self.assertEqual({c[0] for c in self.calls}, {"editMessageText"})
        self.assertEqual(self.state()["board"]["message_id"], 7)
        self.calls.clear()
        self.replies["editMessageText"] = {"ok": False, "description": "Bad Request: message can't be edited"}
        self.pre("y"); self.start("c")
        self.assertIn("sendMessage", [c[0] for c in self.calls])

    def test_parallel_starts_post_and_pin_once(self):
        # two hooks both update state before either flushes: only one may send+pin, the other edits
        self.telegram()
        for aid in ("a", "b"):
            self.pre(aid)                      # flush already ran in hook(); redo the race by hand below
        self.calls.clear()
        with self.m.locked() as st:
            st["board"] = {}
        with self.m.locked() as st:
            self.m.start({"agent_id": "a", "agent_type": "general-purpose", "session_id": "s"}, st)
        ja = list(self.m.JOBS); self.m.JOBS.clear()
        with self.m.locked() as st:
            self.m.start({"agent_id": "b", "agent_type": "general-purpose", "session_id": "s"}, st)
        jb = list(self.m.JOBS); self.m.JOBS.clear()
        self.m.JOBS[:] = ja; self.m.flush(); self.m.JOBS[:] = jb; self.m.flush()
        self.assertEqual([c[0] for c in self.calls], ["sendMessage", "pinChatMessage", "editMessageText"])
        self.assertEqual(self.calls[2][1]["message_id"], 7)
        self.assertEqual(self.state()["board"]["message_id"], 7)

    def test_stop_after_reset_marks_done(self):
        self.pre("job"); self.start("a")
        self.m.cli(["reset"])
        self.assertEqual(self.state()["rows"][0]["status"], "lost")
        self.stop("a")
        self.assertEqual(self.state()["rows"][0]["status"], "done")

    def test_hook_fails_open_on_any_error(self):
        # a bug in the cap logic or the state file must never block an Agent call
        with mock.patch.object(self.m, "caps", side_effect=ValueError("bad env")):
            self.assertEqual(self.pre(), "")
        with mock.patch.object(self.m, "update", side_effect=RuntimeError("boom")):
            self.assertEqual(self.start("x"), "")
        self.m.os.environ["AGENT_BOARD_CAP"] = "not a number"
        self.assertEqual(self.pre(), "")
        os.environ.pop("AGENT_BOARD_CAP")
        d = Path(self.home, ".agent-board"); d.mkdir(exist_ok=True)
        (d / "state.json").write_text("garbage")
        self.assertEqual(self.pre(), "")

    def test_script_runs_and_selftest(self):
        import subprocess
        p = subprocess.run([str(REPO / "server/bin/agent-board"), "--selftest"], capture_output=True, text=True, env={**os.environ, "HOME": self.home})
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "selftest ok"))


if __name__ == "__main__":
    unittest.main()
