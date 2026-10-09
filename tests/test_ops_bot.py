"""Unit tests for pure helpers in server/bin/ops-bot (loaded with a throwaway HOME, no network)."""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

from helpers import REPO


def load_ops_bot(conf=None):
    """conf: optional nori.conf text (e.g. two areas with Plane projects mapped)."""
    home = tempfile.mkdtemp()
    os.environ["HOME"] = home
    os.environ["NORI_ROOT"] = home          # no nori.conf here, so defaults apply
    os.environ.pop("NORI_CONF", None)
    if conf:
        with open(os.path.join(home, "nori.conf"), "w") as f:
            f.write(conf)
        os.makedirs(os.path.join(home, "chat/telegram"))
        shutil.copy(REPO / "chat/telegram/platform.conf", os.path.join(home, "chat/telegram/platform.conf"))
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


    PROMPT = ["⏺ Bash(git push origin main)", "╭────────╮", "│ Bash command", "│   git push origin main",
              "│   Push the branch", "│ Do you want to proceed?", "│ ❯ 1. Yes", "│   2. No, and tell Claude"]

    def test_perm_prompt_detail_and_hash(self):
        self.assertTrue(self.m.has_perm_prompt("\n".join(self.PROMPT)))
        self.assertFalse(self.m.has_perm_prompt("⏺ just working"))
        detail, h = self.m.perm_prompt(self.PROMPT)
        self.assertIn("git push origin main", detail)
        self.assertNotIn("Do you want", detail)
        self.assertRegex(h, r"^[0-9a-f]{10}$")
        other = [l.replace("main", "dev") for l in self.PROMPT]
        self.assertNotEqual(self.m.perm_prompt(other)[1], h)
        self.assertEqual(self.m.perm_prompt(["⏺ idle"]), ("", ""))

    def test_perm_card_detail_is_just_the_dialog(self):
        # a realistic screen: old prompt, chat line and tool line above the dialog, dashed dividers inside it
        dash = "╌" * 200
        screen = ["❯ /clear", "← telegram · owner: p: run git push --dry-run in the app repo",
                  "● Dry-run push", "  ⎿  $ cd ~/projects/main/app && git push --dry-run",
                  " Bash command", " Dry-run push", dash,
                  " │ cd ~/projects/main/app && git push --dry-run 2>&1; echo \"exit=$?\"", dash,
                  " Ask rule Bash(git push:*) overrides auto mode for this command.", " /permissions to let auto mode decide",
                  " Do you want to proceed?", " ❯ 1. Yes", "   2. Yes, and don't ask again for: git push *", "   3. No",
                  " Esc to cancel · Tab to amend"]
        detail, h = self.m.perm_prompt(screen)
        self.assertEqual(detail.splitlines(), ["Bash command", "Dry-run push",
                                               'cd ~/projects/main/app && git push --dry-run 2>&1; echo "exit=$?"'])
        self.assertTrue(h)
        # a long command is not cut early by dividers: the cap is 700 characters
        long_cmd = "git push origin " + "x" * 600
        detail, _ = self.m.perm_prompt(["● old output", " Bash command", dash, " │ " + long_cmd, dash,
                                        " Do you want to proceed?", " ❯ 1. Yes", "   2. No"])
        self.assertIn(long_cmd, detail)

    def test_perm_prompt_strict_live_only(self):
        has = self.m.has_perm_prompt
        footer = ["", "  Esc to cancel · Tab to amend"]
        self.assertTrue(has(self.PROMPT + ["│   3. Yes, and don't ask again"] + footer + ["╰────────╯"]))
        self.assertTrue(has([l.replace("❯ 1", "  1").replace("  2.", "❯ 2.") for l in self.PROMPT]))  # cursor moved
        # the same text quoted in earlier output, with newer output after it: not live
        self.assertFalse(has(self.PROMPT + ["⏺ Done, pushed.", "> "]))
        self.assertFalse(has(self.PROMPT + ["● the user asked: Do you want to proceed?"]))
        # a bare option list or a different dialog without the question
        self.assertFalse(has(["❯ 1. Yes", "  2. No"]))
        self.assertFalse(has(["│ Do you want to proceed?", "│ ❯ 2. No"]))
        # question quoted inside prose
        self.assertFalse(has(["I will ask: Do you want to proceed? ❯ 1. Yes", "  2. No"]))
        self.assertEqual(self.m.perm_prompt(self.PROMPT + ["⏺ later output"]), ("", ""))

    def test_perm_buttons(self):
        h = "0123456789"
        data = self.m.perm_data("main", h, "y")
        self.assertLessEqual(len(data.encode()), 64)        # Telegram's callback_data limit
        self.assertEqual(self.m.PERM_DATA.fullmatch(data).groups(), ("main", h, "y"))
        self.assertIsNone(self.m.PERM_DATA.fullmatch("perm:main:xyz:y"))

    def test_same_prompt(self):
        self.assertTrue(self.m.same_prompt("permission", "abc", "abc"))
        self.assertFalse(self.m.same_prompt("permission", "abd", "abc"))
        self.assertFalse(self.m.same_prompt("idle", "abc", "abc"))
        self.assertFalse(self.m.same_prompt("permission", "", ""))


class ClaudeVersionDrift(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._env = dict(os.environ)
        cls.m = load_ops_bot()

    @classmethod
    def tearDownClass(cls):
        os.environ.clear()
        os.environ.update(cls._env)

    def test_parse(self):
        p = self.m.parse_claude_version
        self.assertEqual(p("2.1.281 (Claude Code)\n"), "2.1.281")
        self.assertEqual(p("2.1.281"), "2.1.281")
        for bad in ("", None, "sudo: a password is required", "error: unknown option", "v2.1.281 (Claude Code)"):
            self.assertIsNone(p(bad), bad)

    def test_drift(self):
        d = self.m.claude_drift
        self.assertEqual(d("2.1.281", {"admin": "2.1.281", "main": "2.1.281"}), [])
        self.assertEqual(d("2.1.281", {"admin": "2.1.281", "main": "2.1.290"}), [("main", "2.1.290")])
        self.assertEqual(d("2.1.281", {"admin": None, "main": "2.1.281"}), [])     # unknown never alerts
        for channel in ("stable", "latest", ""):
            self.assertEqual(d(channel, {"admin": "2.1.1", "main": "2.1.2"}), [], channel)

    def test_alert_once_then_recover(self):
        a = self.m.claude_version_alert
        bad = {"admin": "2.1.281", "main": "2.1.290"}
        sig, msg = a("", "2.1.281", bad)
        self.assertTrue(sig)
        self.assertIn("main: 2.1.290", msg)
        self.assertEqual(a(sig, "2.1.281", bad), (sig, None))                     # same drift: no repeat
        sig2, msg2 = a(sig, "2.1.281", {"admin": "2.1.281", "main": "2.1.291"})
        self.assertNotEqual(sig2, sig)
        self.assertIn("2.1.291", msg2)                                            # changed drift: alert again
        sig3, msg3 = a(sig2, "2.1.281", {"admin": "2.1.281", "main": "2.1.281"})
        self.assertEqual(sig3, "")
        self.assertIn("back on 2.1.281", msg3)
        self.assertEqual(a("", "2.1.281", {"admin": "2.1.281"}), ("", None))        # never drifted: silent
        self.assertEqual(a("", "latest", bad), ("", None))                         # channel: report only

    def test_alert_wording_newer_vs_older(self):
        a = self.m.claude_version_alert
        _, older = a("", "2.1.294", {"admin": "2.1.294", "main": "2.1.290"})
        self.assertIn("run ./setup.sh", older)
        self.assertNotIn("never downgrades", older)
        _, newer = a("", "2.1.294", {"admin": "2.1.294", "main": "2.1.300"})
        self.assertIn("never downgrades", newer)
        self.assertIn("CLAUDE_CODE_VERSION=2.1.300", newer)                       # how to keep it
        self.assertIn("CLAUDE_CODE_VERSION=2.1.294", newer)                       # how to go back
        self.assertNotIn("Older ones", newer)
        _, both = a("", "2.1.294", {"main": "2.1.290", "work": "2.1.300"})
        self.assertIn("Older ones", both)
        self.assertIn("Newer ones", both)
        _, tens = a("", "2.1.94", {"main": "2.1.100"})                             # numeric, not string order
        self.assertIn("Newer ones", tens)

    def test_status_line(self):
        line = self.m.claude_version_line
        self.assertIn("2.1.281 (pinned)", line("2.1.281", {"admin": "2.1.281", "main": "2.1.281"}))
        self.assertIn("main 2.1.290", line("2.1.281", {"admin": "2.1.281", "main": "2.1.290"}))
        self.assertIn("main ?", line("2.1.281", {"admin": "2.1.281", "main": None}))
        self.assertIn("wanted: stable", line("stable", {"admin": "2.1.290"}))


CONF2 = '''AREAS="home work"
PLANE=true
RECALL=true
TIMEZONE="Asia/Tokyo"
AREA_home_PLANE_PROJECTS="HOM"
AREA_work_PLANE_PROJECTS="WRK"
'''


class OpsBotFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._env = dict(os.environ)
        cls.m = load_ops_bot(CONF2)

    @classmethod
    def tearDownClass(cls):
        os.environ.clear()
        os.environ.update(cls._env)

    def setUp(self):
        m = self.m
        self.sent = []
        self._saved = (m.send, m.api, m.plane, m.plane_items, m.time.sleep)
        m.send = lambda chat, text, token=None: self.sent.append((chat, text))
        m.api = lambda method, **kw: {"result": {"message_id": 1}}
        m.time.sleep = lambda s: None

    def tearDown(self):
        m = self.m
        m.send, m.api, m.plane, m.plane_items, m.time.sleep = self._saved

    # --- board ---
    def fake_plane(self):
        projects = [{"id": "p1", "identifier": "HOM", "name": "Home app"}, {"id": "p2", "identifier": "WRK", "name": "Work app"},
                    {"id": "p3", "identifier": "ZZZ", "name": "Unmapped"}]
        item = lambda n, grp, prio, *lb: {"sequence_id": n, "name": f"ticket {n}", "priority": prio, "state": {"group": grp},
                                          "labels": [{"name": x} for x in lb]}
        items = {"p1": [item(1, "started", "urgent", "auto"), item(2, "unstarted", "low"), item(3, "backlog", "none", "needs-me")],
                 "p2": [item(1, "unstarted", "high", "quick-ask")], "p3": [item(1, "unstarted", "medium")]}
        self.m.plane = lambda method, path, body=None: {"results": projects}
        self.m.plane_items = lambda pid, expand, max_pages=20: items[pid]

    def test_board_formatting(self):
        self.fake_plane()
        out = self.m.board_text()
        for want in ("🍙 Board", "📁 Home app (HOM) · 3 open · ✅ 0 this week", "🔨 Doing", "📋 To do", "🗂 Backlog",
                     "HOM-1 🔴🤖 ticket 1", "HOM-2 ⚪ ticket 2", "HOM-3 🧠 ticket 3", "🔎 /peek <ID> for details", "🔴🟠🟡⚪ priority"):
            self.assertIn(want, out)

    def test_board_owner_area_and_unmapped_goes_to_first_area(self):
        self.fake_plane()
        home = self.m.board_text("home")
        self.assertIn("HOM-1", home)
        self.assertIn("ZZZ-1", home)           # owner view: unmapped -> first area
        self.assertNotIn("WRK-1", home)
        work = self.m.board_text("work")
        self.assertIn("WRK-1", work)
        self.assertNotIn("ZZZ-1", work)

    def test_board_nothing_open(self):
        self.m.plane = lambda *a, **k: {"results": [{"id": "p1", "identifier": "HOM", "name": "Home app"}]}
        self.m.plane_items = lambda *a, **k: []
        self.assertIn("✨ Nothing open: HOM", self.m.board_text())

    def test_board_command_is_built_off_the_poll_loop(self):
        m = self.m
        threads = []
        real = m.threading.Thread

        class Tracked(real):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                threads.append(self)
        m.threading.Thread = Tracked
        try:
            self.fake_plane()
            m.send_bg(7, m.board_text, None)
            self.assertEqual(len(threads), 1)
            threads[0].join(5)
            self.assertIn("🍙 Board", self.sent[-1][1])
            self.assertEqual(self.sent[-1][0], 7)
            m.send_bg(7, lambda: 1 / 0)                   # a failure is reported, not raised
            threads[1].join(5)
            self.assertTrue(self.sent[-1][1].startswith("⚠️"))
            # the owner's /board and a member's /board both go through it
            calls = []
            allowed, m.ALLOWED = m.ALLOWED, {1}
            m.send_bg, orig = (lambda chat, make, *a: calls.append((chat, make.__name__, a))), m.send_bg
            try:
                m.handle({"chat": {"id": 7, "type": "private"}, "from": {"id": 1}, "text": "/board work", "message_id": 5})
                m.member_cmd({"chat": {"id": 8}, "from": {"id": 2}}, "home", "/board", ["HOM"])
            finally:
                m.send_bg, m.ALLOWED = orig, allowed
            self.assertEqual(calls, [(7, "board_text", ("work",)), (8, "member_board", ("home", "HOM"))])
        finally:
            m.threading.Thread = real

    def test_react_on_commands_from_owner_and_members_not_strangers(self):
        m = self.m
        reactions = []
        m.api = lambda method, **kw: reactions.append((method, kw)) or {}
        saved = (m.ALLOWED, m.member_area)
        m.ALLOWED = {1}
        m.member_area = lambda uid: "home" if uid == 2 else None
        try:
            msg = lambda uid: {"chat": {"id": 9, "type": "private"}, "from": {"id": uid}, "text": "/help", "message_id": 42}
            m.handle(msg(1))        # owner
            m.handle(msg(2))        # member
            m.handle(msg(3))        # stranger
        finally:
            m.ALLOWED, m.member_area = saved
        got = [kw for method, kw in reactions if method == "setMessageReaction"]
        self.assertEqual(len(got), 2)
        self.assertEqual({kw["message_id"] for kw in got}, {42})
        self.assertEqual(json.loads(got[0]["reaction"]), [{"type": "emoji", "emoji": "👀"}])
        # best effort: a Telegram error never breaks the command
        def boom(method, **kw):
            raise OSError("down")
        m.api = boom
        m.react(9, 42)
        m.react(9, None)

    # --- members ---
    def test_member_scoping_mapped_vs_unmapped(self):
        mp = self.m.member_projects
        self.assertEqual(mp("home", ["HOM", "WRK", "ZZZ"]), ["HOM"])      # unmapped ZZZ is not the first area's for members
        self.assertEqual(mp("work", ["HOM", "wrk", "ZZZ"]), ["wrk"])
        self.assertEqual(self.m.project_area("ZZZ"), "home")            # ...though the owner's view still files it under the first area

    def test_member_board_hides_other_projects(self):
        self.fake_plane()
        out = self.m.member_board("home", None)
        self.assertIn("HOM-1", out)
        self.assertNotIn("ZZZ-1", out)
        self.assertNotIn("WRK-1", out)
        self.assertNotIn("WRK-1", self.m.member_board("home", "WRK"))       # naming another area's project doesn't open it

    def test_member_peek_refusal(self):
        called = []
        self.m.peek_text = lambda key: called.append(key) or "🔎 ok"
        self.assertEqual(self.m.member_peek("home", "WRK-1"), "WRK-1 isn't a home ticket")
        self.assertEqual(self.m.member_peek("home", "ZZZ-1"), "ZZZ-1 isn't a home ticket")
        self.assertEqual(called, [])
        self.assertEqual(self.m.member_peek("home", "hom-1"), "🔎 ok")
        self.assertEqual(called, ["HOM-1"])
        self.assertIn("Usage", self.m.member_peek("home", "nonsense"))

    # --- workgroup ---
    def test_workgroup_binding_rules(self):
        w = self.m.workgroup_apply
        st = {}
        self.assertIn("inside the group", w(st, 5, "work", 99, True))     # private chat: refused
        self.assertIn("ops chat", w(st, 99, "work", 99, False))            # ops chat: refused
        self.assertIn("Usage", w(st, -5, "nope", 99, False))               # unknown area
        self.assertEqual(st.get("groups", {}), {})
        self.assertIn("Bound to work", w(st, -5, "work", 99, False))
        self.assertEqual(st["groups"], {"-5": "work"})
        self.assertIn("Unbound", w(st, -5, "off", 99, False))
        self.assertEqual(st["groups"], {})

    def test_workgroup_owner_only(self):
        self.m.ALLOWED.add(1)
        try:
            self.m.workgroup_cmd({"chat": {"id": -7, "type": "group"}, "from": {"id": 2}}, ["work"])   # not the owner
            self.assertEqual(self.sent, [])
        finally:
            self.m.ALLOWED.discard(1)

    # --- ask-owner / do it ---
    def test_ask_clean(self):
        c = self.m.ask_clean
        self.assertEqual(c("a\nb\x1b[31m\tc", 50), "a b [31m c")
        self.assertEqual(c("x" * 500, 10), "x" * 10)
        self.assertEqual(c("  a\u2028b  ", 50), "a b")
        self.assertNotIn("\n", c("line1\r\nline2", 50))

    def test_ask_keyboard_callbacks_fit_telegram(self):
        kb = json.loads(self.m.ask_keyboard("0123456789", ["yes", "no"]))
        self.assertEqual([r[0]["callback_data"] for r in kb["inline_keyboard"]], ["ask:0123456789:0", "ask:0123456789:1"])
        self.assertLessEqual(len(self.m.doit_keyboard("ABCDEFGHIJ-999999")), 200)

    def test_doit_refused_when_permission_prompt_or_down(self):
        answers = []
        self.m.api = lambda method, **kw: answers.append((method, kw)) or {}
        typed = []
        orig = (self.m.session_state, self.m.ask_type)
        self.m.ask_type = lambda area, text: typed.append((area, text)) or True
        try:
            for st in ("permission", "down"):
                self.m.session_state = lambda area, st=st: (st, "")
                self.m.doit_callback({"id": "1", "data": "do:HOM-1", "message": {"chat": {"id": 1}, "message_id": 2}})
            self.assertEqual(typed, [])
            self.assertTrue(all(kw.get("show_alert") for _, kw in answers))
            self.m.doit_callback({"id": "1", "data": "do:bad", "message": {"chat": {"id": 1}, "message_id": 2}})
            self.assertEqual(typed, [])
        finally:
            self.m.session_state, self.m.ask_type = orig

    def test_input_box_idle(self):
        m = self.m
        self.assertTrue(m.input_box_idle(IDLE_SCREEN))
        self.assertTrue(m.input_box_idle(IDLE_SCREEN.replace("❯ \n", '❯ Try "fix lint errors"\n')))
        self.assertTrue(m.input_box_idle(IDLE_SCREEN.replace("❯ \n", "> \n")))
        self.assertTrue(m.input_box_idle(IDLE_SCREEN + "".join(f"  ◯ general-purpose  job {i}  4s\n" for i in range(8))))
        self.assertFalse(m.input_box_idle(""))
        for name, scr in SCREENS_NOT_IDLE.items():
            self.assertFalse(m.input_box_idle(scr), name)

    def test_doit_refuses_dialogs_and_drafts_then_works_when_idle(self):
        answers, typed = [], []
        orig = (self.m.api, self.m.session_state, self.m.ask_type, self.m.as_user, self.m.find_item, self.m.load_state, self.m.save_state)
        state = {}
        self.m.api = lambda method, **kw: answers.append((method, kw)) or {}
        self.m.session_state = lambda area: ("idle", "")
        self.m.ask_type = lambda area, text: typed.append((area, text)) or True
        self.m.find_item = lambda ident, seq: ({"id": "p"}, {"name": "x", "id": "i"})
        self.m.load_state, self.m.save_state = (lambda: state), (lambda s: None)
        cq = {"id": "1", "data": "do:HOM-1", "message": {"chat": {"id": 1}, "message_id": 2, "text": "t"}}
        try:
            for name, scr in SCREENS_NOT_IDLE.items():
                self.m.as_user = lambda *a, scr=scr, **k: (0, scr)
                self.m.doit_callback(cq)
                self.assertEqual(typed, [], name)
                self.assertIn("Tap again", answers[-1][1]["text"], name)
            self.assertNotIn("doit", state)                      # refused taps claim nothing
            self.m.as_user = lambda *a, **k: (0, IDLE_SCREEN)
            self.m.doit_callback(cq)
            self.assertEqual(len(typed), 1)
        finally:
            (self.m.api, self.m.session_state, self.m.ask_type, self.m.as_user, self.m.find_item, self.m.load_state, self.m.save_state) = orig

    # --- recall ---
    def test_recall_parse(self):
        p = self.m.recall_parse
        self.assertEqual(p("deploy notes"), (None, "deploy notes"))
        self.assertEqual(p("work: deploy"), ("work", "deploy"))
        self.assertEqual(p("w: deploy"), ("work", "deploy"))
        self.assertEqual(p("h：x y"), ("home", "x y"))
        self.assertEqual(p("other: deploy"), (None, "other: deploy"))      # not an area: part of the query

    # --- transcripts / still on it ---
    def test_transcript_dir_and_facts(self):
        d = str(self.m.transcript_dir("work"))
        self.assertNotIn(".", d.rsplit("/projects/", 1)[1])
        lines = [
            {"type": "user", "timestamp": "2026-01-01T10:00:00.000Z", "message": {"content": '<channel source="plugin:telegram:telegram" chat_id="1">hi</channel>'}},
            {"type": "assistant", "timestamp": "2026-01-01T10:01:00.000Z", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "go test ./..."}}]}},
        ]
        raw = "\n".join(json.dumps(x) for x in lines)
        inbound, reply, step = self.m.transcript_facts(raw)
        self.assertGreater(inbound, 0)
        self.assertEqual(reply, 0)
        self.assertEqual(step, "Bash: go test ./...")
        self.assertTrue(self.m.is_inbound('<channel source="plugin:telegram:telegram">x'))
        self.assertFalse(self.m.is_inbound("plain user typing"))

    # --- telegram liveness ---
    def test_live_step_state_machine(self):
        st = self.m.live_step
        t0 = 1000
        rec, msg = st({}, {"n": 3, "err": ""}, t0)
        self.assertIsNone(msg)                                              # first bad check: wait
        rec, msg = st(rec, {"n": 3, "err": ""}, t0 + 60)
        self.assertIsNone(msg)                                              # second, but < 240 s apart
        rec, msg = st(rec, {"n": 3, "err": ""}, t0 + 300)
        self.assertIn("isn't receiving", msg)                               # alert once
        rec, msg = st(rec, {"n": 4, "err": ""}, t0 + 600)
        self.assertIsNone(msg)
        rec, msg = st(rec, {"n": 0, "err": ""}, t0 + 900)
        self.assertIn("receiving again", msg)
        rec, msg = st(rec, {"n": 0, "err": ""}, t0 + 1200)
        self.assertIsNone(msg)

    def test_live_step_probe_errors(self):
        rec, msgs = {}, []
        for i in range(4):
            rec, msg = self.m.live_step(rec, {"n": None, "err": "URLError"}, 1000 + i)
            msgs.append(msg)
        self.assertEqual([bool(x) for x in msgs], [False, False, True, False])    # one note on the 3rd failure
        rec, _ = self.m.live_step(rec, {"n": 0, "err": ""}, 2000)
        self.assertEqual(rec["fails"], 0)

    def test_live_probe_never_returns_token(self):
        self.m.as_user = lambda *a, **k: (0, '{"n": 2, "err": "x"}')
        self.assertEqual(self.m.live_probe("home"), {"n": 2, "err": "x"})
        self.m.as_user = lambda *a, **k: (1, "sudo: a password is required")
        self.assertEqual(self.m.live_probe("home")["n"], None)

    # --- member updates ---
    def test_member_diff_first_run_silent(self):
        items = {"HOM-1": {"name": "one", "state": {"group": "started"}}, "HOM-2": {"name": "two", "state": {"group": "unstarted"}}}
        seen, notes = self.m.member_diff(["HOM-1", "HOM-2"], {}, items, True)
        self.assertEqual(notes, {})
        self.assertEqual(seen, {"HOM-1": "started", "HOM-2": "unstarted"})
        items["HOM-2"]["state"]["group"] = "completed"
        items["HOM-1"]["state"]["group"] = "cancelled"
        seen, notes = self.m.member_diff(["HOM-1", "HOM-2"], seen, items, False)
        self.assertIn("is done", notes["HOM-2"])
        self.assertIn("was cancelled", notes["HOM-1"])
        _, again = self.m.member_diff(["HOM-1", "HOM-2"], seen, items, False)
        self.assertEqual(again, {})                                         # no repeat
        _, fresh = self.m.member_diff(["HOM-3"], {}, {"HOM-3": {"name": "x", "state": {"group": "started"}}}, False)
        self.assertIn("in progress", fresh["HOM-3"])                        # new ticket starts from To do

    def test_timezone_and_platform_values(self):
        self.assertEqual(self.m.TZ.key, "Asia/Tokyo")
        self.assertEqual(self.m.PLUGIN, "telegram")
        self.assertEqual(self.m.REPLY_TOOLS[0], "mcp__plugin_telegram_telegram__reply")


RULE = "─" * 60
# shape of a real Claude Code 2.1.29x pane at rest (status line, mode line under the box)
IDLE_SCREEN = f"● Done.\n\n{RULE}\n❯ \n{RULE}\n  5h 5% · wk 79%\n  ⏵⏵ auto mode on (shift+tab to cycle) · ← for agents\n"
SCREENS_NOT_IDLE = {
    "draft": f"{RULE}\n❯ half typed\n{RULE}\n  ? for shortcuts\n",
    "multiline draft": f"{RULE}\n❯ line one\n  line two\n{RULE}\n  ? for shortcuts\n",
    "trust": " Do you trust the files in this folder?\n\n ❯ 1. Yes, proceed\n   2. No, exit\n\n Enter to confirm · Esc to cancel\n",
    "remote control": " Enable Remote Control? (y/n)\n",
    "ask menu": f"{RULE}\n ☐ Pick one\n\n❯ 1. A\n  2. B\n\n{RULE}\n Enter to select · ↑/↓ to navigate · Esc to cancel\n",
    "box then menu": f"{RULE}\n❯ \n{RULE}\n❯ 1. Resume\n  2. Other\n Enter to select\n",
    "permission": " Do you want to proceed?\n ❯ 1. Yes\n   2. Yes, and don't ask again\n   3. No\n Esc to cancel · Tab to amend\n",
}

if __name__ == "__main__":
    unittest.main()
