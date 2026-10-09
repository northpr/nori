"""./nori up: config, keys, hetzner, remote, stages (stdlib only, no network)."""
import io, json, os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
from helpers import REPO
sys.path.insert(0, str(REPO / "scripts"))
from nori import config, hetzner, keys, remote, stages  # noqa: E402

CONF = {"PRESET": "recommended", "AREAS": "main work", "OPS_BOT": "true", "PLANE": "false",
        "SERVER_NAME": "nori-server", "ADMIN_USER": "admin"}


class ConfigKeys(unittest.TestCase):
    def test_parse_resolved(self):
        txt = '# generated\nPRESET="full"\nAREAS="main work"\nOPS_BOT=true\n'
        self.assertEqual(config.parse(txt), {"PRESET": "full", "AREAS": "main work", "OPS_BOT": "true"})

    def test_load_real_conf_has_identity_values(self):
        """config.load on a real nori.conf gives what run_up needs, not only the preset flags."""
        import shutil
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            shutil.copytree(REPO, repo, ignore=shutil.ignore_patterns(".git", "generated", "__pycache__", ".superpowers"))
            (repo / "nori.conf").write_text((REPO / "nori.conf.example").read_text())
            conf = config.load(repo)
            for k in ("ADMIN_USER", "AREAS", "SERVER_NAME", "PRESET", "OPS_BOT", "PLANE"):
                self.assertTrue(conf.get(k), k)
            self.assertEqual(conf["ADMIN_USER"], "admin")

    def test_checklist_shows_what_each_key_looks_like(self):
        out = io.StringIO()
        answers = iter(["tskey-auth-good-1"])
        keys.ask_keys(["tailscale", "claude", "bot:main", "hetzner", "admin_password"][:1], prompt=lambda p: next(answers), out=out)
        self.assertIn("looks like: tskey-auth-", out.getvalue())
        for n in ("hetzner", "claude", "bot:main", "admin_password"):
            self.assertTrue(keys.shape(n), n)
        self.assertIn("sk-ant-oat01-", keys.shape("claude"))
        self.assertIn(":AA", keys.shape("bot:ops"))

    def test_safety_note_is_first_line_and_bot_checklist_mentions_username(self):
        out = io.StringIO()
        keys.ask_keys(["tailscale"], prompt=lambda p: "tskey-auth-ok1", out=out)
        first = out.getvalue().splitlines()[0]
        self.assertTrue(first.startswith("🔒"))
        self.assertIn("password manager", first)
        self.assertIn("username", keys.label("bot:main"))
        self.assertIn("12+", keys.label("admin_password"))
        self.assertIn("Read & Write", keys.label("hetzner"))
        self.assertIn("claude setup-token", keys.label("claude"))

    def test_refuses_when_typing_cannot_be_hidden(self):
        import getpass as gp
        def no_tty(p):
            raise gp.GetPassWarning("Can not control echo on the terminal.")
        out = io.StringIO()
        with self.assertRaises(SystemExit) as e:
            keys.ask_keys(["bot:main"], prompt=no_tty, out=out)
        self.assertIn("separate terminal window", str(e.exception))

    def test_hidden_prompt_turns_echo_fallback_into_an_error(self):
        import getpass as gp, warnings
        def fake_getpass(p):
            warnings.warn("Can not control echo on the terminal.", gp.GetPassWarning)
            return "would-have-been-echoed"
        with mock.patch.object(keys.getpass, "getpass", fake_getpass):
            with self.assertRaises(gp.GetPassWarning):
                keys.hidden_prompt("bot:main: ")

    def test_accepted_key_shows_only_first_three_and_length(self):
        out = io.StringIO()
        ts, pw = "tskey-auth-abcdefSECRETPART-xyz", "correct horse battery"
        answers = iter([ts, pw, pw])
        keys.ask_keys(["tailscale", "admin_password"], prompt=lambda p: next(answers), out=out)
        text = out.getvalue()
        self.assertIn(f"✓ tsk… ({len(ts)} characters)", text)
        self.assertNotIn("SECRETPART", text)
        self.assertIn(f"✓ {len(pw)} characters", text)
        self.assertNotIn("cor", text.split("admin_password")[-1])

    def test_server_size(self):
        self.assertEqual(config.server_size(CONF), "small")
        self.assertEqual(config.server_size({**CONF, "PRESET": "full"}), "large")
        self.assertEqual(config.server_size({**CONF, "PLANE": "true"}), "large")

    def test_needed_keys(self):
        self.assertEqual(config.needed_keys(CONF, hetzner=True),
                         ["hetzner", "claude", "bot:main", "bot:work", "bot:ops", "admin_password"])
        self.assertIn("tailscale", config.needed_keys(CONF, hetzner=False, tailscale=True))
        self.assertNotIn("hetzner", config.needed_keys(CONF, hetzner=False))
        self.assertNotIn("bot:ops", config.needed_keys({**CONF, "OPS_BOT": "false"}, hetzner=True))

    def test_checks(self):
        self.assertIsNone(keys.check("tailscale", "tskey-auth-abc123-XYZ"))
        self.assertIn("tskey-auth-", keys.check("tailscale", "abc"))
        self.assertIsNone(keys.check("claude", "sk-ant-oat01-" + "x" * 40))
        self.assertIsNotNone(keys.check("claude", "hello"))
        self.assertIsNotNone(keys.check("admin_password", "short"))
        self.assertIsNone(keys.check("admin_password", "long enough pass"))

    def test_bot_check_uses_getme_and_never_prints_token(self):
        tok = "123456:ABC-def"
        def http(url, timeout=0):
            self.assertIn(tok, url)          # only inside the request URL to Telegram
            return io.BytesIO(b'{"ok":true,"result":{"username":"my_bot"}}')
        self.assertIsNone(keys.check("bot:main", tok, http=http))

    def test_ask_keys_reprompts_and_hides(self):
        answers = iter(["bad", "tskey-auth-good-1"])
        out = io.StringIO()
        got = keys.ask_keys(["tailscale"], prompt=lambda p: next(answers), out=out)
        self.assertEqual(got, {"tailscale": "tskey-auth-good-1"})
        self.assertNotIn("tskey-auth-good-1", out.getvalue())


class AskKeysTest(unittest.TestCase):
    def test_admin_password_asked_twice_and_reasked_on_mismatch(self):
        answers = iter(["long enough pass", "different pass 1", "long enough pass", "long enough pass"])
        asked, out = [], io.StringIO()
        def prompt(p):
            asked.append(p)
            return next(answers)
        got = keys.ask_keys(["admin_password"], prompt=prompt, out=out)
        self.assertEqual(got, {"admin_password": "long enough pass"})
        self.assertEqual(len(asked), 4)
        self.assertIn("again to confirm", asked[1])
        self.assertNotIn("long enough pass", out.getvalue())
        self.assertNotIn("different pass 1", out.getvalue())

    def test_bot_username_shown_and_duplicate_rejected(self):
        def http(url, timeout=0):
            name = "bot_a" if "BOTA" in url or "BOTA2" in url else "bot_b"
            return io.BytesIO(json.dumps({"ok": True, "result": {"username": name}}).encode())
        answers = iter(["1:BOTAxx", "2:BOTA2xx", "3:BOTBxx"])
        out = io.StringIO()
        got = keys.ask_keys(["bot:main", "bot:work"], prompt=lambda p: next(answers), out=out, http=http)
        self.assertEqual(got, {"bot:main": "1:BOTAxx", "bot:work": "3:BOTBxx"})
        o = out.getvalue()
        self.assertIn("@bot_a", o)
        self.assertIn("same bot as bot:main; each area and the Ops bot need their own", o)
        self.assertNotIn("BOTA", o)

    def test_check_info_returns_username(self):
        http = lambda url, timeout=0: io.BytesIO(b'{"ok":true,"result":{"username":"my_bot"}}')
        self.assertEqual(keys.check_info("bot:main", "123456:ABC-def", http=http), (None, "my_bot"))


class FakeAPI:
    """In-memory Hetzner: server types with prices, which datacenter has which type, servers, keys."""
    def __init__(self, available=None, status=200):
        self.available = available or {"fsn1": ["cax11", "cax21", "cx23", "cx33"]}
        self.servers, self.keys, self.calls, self.status = {}, {}, [], status
        self.pricing = True
        self.stored_keys = []  # [{"id", "name", "public_key"}] as Hetzner returns them

    def __call__(self, method, path, body):
        self.calls.append((method, path, body))
        if self.status != 200:
            return self.status, {"error": {"code": "unauthorized", "message": "unable to authenticate"}}
        ids = {"cax11": 1, "cax21": 2, "cx23": 3, "cx33": 4}
        if path == "/locations":
            return 200, {"locations": []}
        if path == "/server_types":
            # since 2026-10-01 availability lives on server_types[].locations[] (GET /datacenters is 410 Gone)
            return 200, {"server_types": [{"id": i, "name": n, "prices": [
                {"location": l, "price_monthly": {"gross": f"{i + 3}.9900"}} for l in hetzner.LOCATIONS],
                "locations": [{"id": k, "name": l, "available": n in self.available.get(l, ()), "recommended": True,
                               "deprecation": None} for k, l in enumerate(hetzner.LOCATIONS)]}
                for n, i in ids.items()]}
        if path == "/pricing":
            if not self.pricing:
                return 404, {"error": {"code": "not_found", "message": "no pricing"}}
            return 200, {"pricing": {"primary_ips": [
                {"type": "ipv6", "prices": [{"location": "fsn1", "price_monthly": {"gross": "0.0000"}}]},
                {"type": "ipv4", "prices": [{"location": l, "price_monthly": {"gross": "0.6100"}} for l in ("fsn1", "nbg1")]}]}}
        if path == "/datacenters":
            return 410, {"error": {"code": "deprecated_api_endpoint", "message": "API functionality was removed"}}
        if method == "POST" and path == "/ssh_keys":
            self.keys[body["name"]] = 7
            self.stored_keys.append({"id": 7, "name": body["name"], "public_key": body["public_key"]})
            return 201, {"ssh_key": {"id": 7}}
        if method == "GET" and path.startswith("/ssh_keys"):
            return 200, {"ssh_keys": list(self.stored_keys)}
        if method == "POST" and path == "/servers":
            self.servers[42] = {"id": 42, "status": "running", "public_net": {"ipv4": {"ip": "203.0.113.5"}}}
            return 201, {"server": self.servers[42]}
        if method == "GET" and path.startswith("/servers/"):
            sid = int(path.rsplit("/", 1)[1])
            return (200, {"server": self.servers[sid]}) if sid in self.servers else (404, {"error": {"code": "not_found", "message": "server not found"}})
        return 404, {"error": {"code": "not_found", "message": path}}


class HetznerTest(unittest.TestCase):
    def test_pick_first_location_and_price(self):
        h = hetzner.Hetzner("t", transport=FakeAPI())
        self.assertEqual(h.pick("large"), {"type": "cax21", "location": "fsn1", "price": "5.99", "ipv4": "0.61"})

    def test_pick_without_ipv4_price(self):
        api = FakeAPI()
        api.pricing = False
        self.assertNotIn("ipv4", hetzner.Hetzner("t", transport=api).pick("large"))
        self.assertEqual(hetzner.Hetzner("t", transport=FakeAPI()).price_for("cx33", "fsn1")["ipv4"], "0.61")

    def test_pick_falls_back_location_then_arch(self):
        api = FakeAPI(available={"fsn1": [], "nbg1": ["cx33"], "hel1": []})
        self.assertEqual(hetzner.Hetzner("t", transport=api).pick("large")["type"], "cx33")
        api = FakeAPI(available={"fsn1": [], "nbg1": [], "hel1": ["cax21"]})
        self.assertEqual(hetzner.Hetzner("t", transport=api).pick("large")["location"], "hel1")

    def test_pick_sold_out_everywhere(self):
        api = FakeAPI(available={"fsn1": [], "nbg1": [], "hel1": []})
        with self.assertRaises(hetzner.HetznerError) as e:
            hetzner.Hetzner("t", transport=api).pick("small")
        self.assertIn("sold out", str(e.exception))

    def test_create_and_wait(self):
        api = FakeAPI()
        h = hetzner.Hetzner("t", transport=api)
        kid = h.ssh_key_id("nori", "ssh-ed25519 AAAA nori")
        srv = h.create("nori-server", "cax11", "fsn1", kid)
        self.assertEqual(srv, {"id": 42, "ip": "203.0.113.5"})
        body = [b for m, p, b in api.calls if p == "/servers"][0]
        self.assertEqual(body["image"], "ubuntu-24.04")
        h.wait_running(42, sleep=lambda s: None)
        self.assertIsNone(h.server(99))

    def test_read_only_token_says_how_to_fix(self):
        api = FakeAPI()
        def t(method, path, body):
            if method == "POST":
                return 403, {"error": {"code": "forbidden", "message": "permission denied"}}
            return api(method, path, body)
        with self.assertRaises(hetzner.HetznerError) as e:
            hetzner.Hetzner("t", transport=t).ssh_key_id("nori", "ssh-ed25519 AAAA nori")
        self.assertIn("Read & Write", str(e.exception))

    def test_api_error_is_short_and_clean(self):
        with self.assertRaises(hetzner.HetznerError) as e:
            hetzner.Hetzner("secret-token", transport=FakeAPI(status=401)).check()
        self.assertIn("unable to authenticate", str(e.exception))
        self.assertNotIn("secret-token", str(e.exception))

    def test_ssh_key_reused_when_same_key(self):
        api = FakeAPI()
        api.stored_keys.append({"id": 5, "name": "old-name", "public_key": "ssh-ed25519 AAAA other-comment"})
        kid = hetzner.Hetzner("t", transport=api).ssh_key_id("nori", "ssh-ed25519 AAAA nori")
        self.assertEqual(kid, 5)
        self.assertFalse([c for c in api.calls if c[0] == "POST"])

    def test_ssh_key_same_name_different_key_is_not_reused(self):
        api = FakeAPI()
        api.stored_keys.append({"id": 5, "name": "nori", "public_key": "ssh-ed25519 OLDKEY nori"})
        kid = hetzner.Hetzner("t", transport=api).ssh_key_id("nori", "ssh-ed25519 NEWKEY nori")
        self.assertEqual(kid, 7)
        posts = [b for m, p, b in api.calls if m == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertRegex(posts[0]["name"], r"^nori-[0-9a-f]{8}$")

    def test_network_failure_is_clean(self):
        import urllib.error
        h = hetzner.Hetzner("secret-token")
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timed out")):
            with self.assertRaises(hetzner.HetznerError) as e:
                h.check()
        self.assertIn("couldn't reach the API", str(e.exception))
        self.assertNotIn("secret-token", str(e.exception))


class RemoteTest(unittest.TestCase):
    def test_upsert_adds_then_updates_marked_block(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config"
            p.write_text("Host other\n  HostName 1.2.3.4\n")
            remote.upsert_host(p, "nori", "203.0.113.5", "root")
            remote.upsert_host(p, "nori", "203.0.113.5", "admin")
            txt = p.read_text()
            self.assertIn("Host other", txt)
            self.assertLess(txt.index("# >>> nori >>>"), txt.index("Host other"))
            self.assertEqual(txt.count("# >>> nori >>>"), 1)
            self.assertIn("User admin", txt)
            self.assertNotIn("User root", txt)
            self.assertEqual(oct(p.stat().st_mode & 0o777), "0o600")
            self.assertIn("  StrictHostKeyChecking accept-new", txt)
            self.assertIn("  UserKnownHostsFile ~/.ssh/nori_known_hosts", txt)

    def test_block_ends_with_match_all_and_user_globals_follow(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config"
            user = "Include ~/.orbstack/ssh/config\nServerAliveInterval 30\n\nHost other\n  HostName 1.2.3.4\n"
            p.write_text(user)
            remote.upsert_host(p, "nori", "203.0.113.5", "root")
            remote.upsert_host(p, "nori", "203.0.113.5", "admin")
            txt = p.read_text()
            self.assertEqual(txt.count("Match all"), 1)
            self.assertEqual(txt.count("# >>> nori >>>"), 1)
            after = txt.split("Match all\n", 1)[1]
            self.assertEqual(after, "# <<< nori <<<\n\n" + user)

    def test_hand_written_host_is_left_alone(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config"
            p.write_text("Host nori\n  HostName 9.9.9.9\n")
            with self.assertRaises(remote.RemoteError):
                remote.upsert_host(p, "nori", "203.0.113.5", "root")
            self.assertEqual(p.read_text(), "Host nori\n  HostName 9.9.9.9\n")

    def test_multi_alias_host_line_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config"
            p.write_text("Host nori nori2\n  HostName 9.9.9.9\n")
            with self.assertRaises(remote.RemoteError):
                remote.upsert_host(p, "nori", "203.0.113.5", "root")
            self.assertEqual(p.read_text(), "Host nori nori2\n  HostName 9.9.9.9\n")

    def test_host_key_changed_raises(self):
        def run(argv, input=None, **kw):
            class R: returncode, stdout, stderr = 255, "", "WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!"
            return R()
        with self.assertRaises(remote.RemoteError) as cm:
            remote.ssh("nori", "true", run=run)
        self.assertIn("nori_known_hosts", str(cm.exception))

    def test_wait_ssh_survives_timeouts(self):
        import subprocess
        calls = []
        def run(argv, input=None, **kw):
            calls.append(argv)
            if len(calls) <= 2:
                raise subprocess.TimeoutExpired(argv, 20)
            class R: returncode, stdout = 0, ""
            return R()
        remote.wait_ssh("nori", run=run, sleep=lambda s: None)
        self.assertEqual(len(calls), 3)
        self.assertIn("ConnectTimeout=10", calls[0])

    def test_ssh_sends_secret_on_stdin_only(self):
        seen = {}
        def run(argv, input=None, **kw):
            seen["argv"], seen["input"] = argv, input
            class R: returncode, stdout = 0, "ok"
            return R()
        rc, _ = remote.ssh("nori", "~/nori/server/bin/set-token main", stdin="123:SECRET", run=run)
        self.assertEqual(rc, 0)
        self.assertNotIn("SECRET", " ".join(seen["argv"]))
        self.assertEqual(seen["input"], "123:SECRET\n")

    def test_copy_repo_pipes_tar_into_ssh(self):
        procs = []
        class P:
            def __init__(self, argv, stdin=None, stdout=None, env=None):
                self.argv, self.stdout, self.env = argv, object(), env
                procs.append(self)
            def wait(self):
                return 0
        remote.copy_repo("nori", "/repo", popen=P)
        tar, ssh_ = procs[0].argv, procs[1].argv
        self.assertEqual(tar[:3], ["tar", "-C", "/repo"])
        self.assertIn("--exclude=.git", tar)
        self.assertIn("--exclude=generated", tar)
        self.assertEqual(procs[0].env["COPYFILE_DISABLE"], "1")
        self.assertEqual(ssh_[-1], "rm -rf /root/nori && mkdir -p /root/nori && "
                                   "tar --warning=no-unknown-keyword --no-same-owner -x -C /root/nori")

    def test_ssh_without_stdin_uses_devnull(self):
        import subprocess
        seen = {}
        def run(argv, **kw):
            seen.update(kw)
            class R: returncode, stdout = 0, ""
            return R()
        remote.ssh("nori", "true", run=run)
        self.assertIs(seen["stdin"], subprocess.DEVNULL)
        self.assertNotIn("input", seen)


class ServerSide(unittest.TestCase):
    def test_units_load_claude_env(self):
        for f in ("server/systemd/claude@.service.tmpl", "server/systemd/claude-pool@.service",
                  "server/systemd/ops-bot.service"):
            self.assertIn("EnvironmentFile=-%h/.config/nori/claude.env", (REPO / f).read_text(), f)

    def test_set_token_has_claude_target_reading_stdin(self):
        txt = (REPO / "server/bin/set-token").read_text()
        self.assertIn("claude)", txt)
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", txt)
        self.assertIn(".config/nori/claude.env", txt)


class ServerSideTelegramFirst(unittest.TestCase):
    def test_pool_stops_cleanly_without_a_full_login(self):
        txt = (REPO / "server/bin/claude-pool").read_text()
        self.assertIn(".claude/.credentials.json", txt)
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", txt)
        self.assertIn("exit 78", txt)
        self.assertIn("unset CLAUDE_CODE_OAUTH_TOKEN", txt)
        self.assertLess(txt.index("unset CLAUDE_CODE_OAUTH_TOKEN"), txt.index("exit 78"))
        self.assertIn("Claude app after Quick setup", txt)
        self.assertLess(txt.index("exit 78"), txt.index("exec claude remote-control"))
        self.assertIn("RestartPreventExitStatus=78", (REPO / "server/systemd/claude-pool@.service").read_text())

    def test_attach_explains_how_to_leave_and_what_happened(self):
        txt = (REPO / "server/bin/attach").read_text()
        for t in ("Ctrl+b then d", "not Ctrl+d or /exit", "Claude keeps running in the background",
                  "has-session", "Claude stopped", "run the same attach command again"):
            self.assertIn(t, txt)
        self.assertIn("No Claude session for", txt)
        self.assertLess(txt.index("No Claude session for"), txt.index("attach -t"))
        self.assertNotIn("ssh -t nori", txt)
        self.assertNotIn("exec tmux", txt)
        self.assertNotIn("exec sudo", txt)


class StagesTest(unittest.TestCase):
    KEYS = {"hetzner": "HTOKEN", "claude": "sk-ant-oat01-" + "c" * 30,
            "bot:main": "1:BOTMAIN", "bot:work": "2:BOTWORK", "bot:ops": "3:BOTOPS", "admin_password": "pw-pw-pw-pw-pw"}

    def env(self, d, api=None, answer="yes"):
        self.cmds = []
        def ssh(alias, command, stdin=None, **kw):
            self.cmds.append((alias, command, stdin))
            return 0, ""
        self.out = io.StringIO()
        return {"conf": CONF, "keys": dict(self.KEYS), "hetzner": hetzner.Hetzner("HTOKEN", transport=api or FakeAPI()),
                "ssh": ssh, "wait_ssh": lambda alias: None, "ensure_key": lambda home: "ssh-ed25519 AAAA nori",
                "upsert_host": lambda *a: None, "copy_repo": lambda alias, repo: None, "confirm": lambda q: "n" if "retry" in q else answer, "out": self.out, "home": Path(d)}

    def state(self, repo):
        return json.loads((Path(repo) / "generated/up-state.json").read_text())

    def test_bad_hetzner_token_reasks_only_that_key_and_retries(self):
        with tempfile.TemporaryDirectory() as d:
            api = FakeAPI()
            def transport_for(token):
                def t(method, path, body):
                    if method == "POST" and token == "READONLY":
                        return 403, {"error": {"code": "forbidden", "message": "permission denied"}}
                    return api(method, path, body)
                return t
            e = self.env(d, api=api)
            e["keys"]["hetzner"] = "READONLY"
            e.pop("hetzner")
            e["hetzner_factory"] = lambda tok: hetzner.Hetzner(tok, transport=transport_for(tok))
            answers = iter(["yes", "y", "yes"])          # price, retry?, price again
            e["confirm"] = lambda q: next(answers)
            asked = []
            e["ask_keys"] = lambda names, **kw: asked.append(list(names)) or {"hetzner": "GOOD"}
            self.assertEqual(stages.run_up(d, env=e), 0)
            self.assertEqual(asked, [["hetzner"]])
            self.assertEqual(sum(1 for m, p, _ in api.calls if m == "POST" and p == "/servers"), 1)
            self.assertIn("Read & Write", self.out.getvalue())

    def test_bad_bot_token_reasks_only_that_bot(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.env(d)
            fails = {"n": 1}
            inner = e["ssh"]
            def ssh(alias, command, stdin=None, **kw):
                if command.endswith("set-token main") and fails["n"]:
                    fails["n"] -= 1
                    inner(alias, command, stdin=stdin)
                    return 1, "invalid token"
                return inner(alias, command, stdin=stdin)
            e["ssh"] = ssh
            e["confirm"] = lambda q: "y" if "retry" in q else "yes"
            asked = []
            e["ask_keys"] = lambda names, **kw: asked.append(list(names)) or {"bot:main": "9:NEWMAIN"}
            self.assertEqual(stages.run_up(d, env=e), 0)
            self.assertEqual(asked, [["bot:main"]])
            self.assertIn("9:NEWMAIN", [s for _, c, s in self.cmds if c.endswith("set-token main")])

    def test_saying_no_to_retry_stops_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.env(d)
            def ssh(alias, command, stdin=None, **kw):
                return (1, "nope") if "set-token claude" in command else (0, "")
            e["ssh"] = ssh
            e["confirm"] = lambda q: "n" if "retry" in q else "yes"
            self.assertEqual(stages.run_up(d, env=e), 1)
            self.assertIn("run ./nori up again", self.out.getvalue())

    def test_each_step_says_how_long_it_usually_takes(self):
        with tempfile.TemporaryDirectory() as d:
            stages.run_up(d, env=self.env(d))
            out = self.out.getvalue()
            self.assertIn("⏳ bootstrap… (usually 5–10 min)", out)
            for name in [n for n in stages.STAGES[1:-1] if n != "tailscale"]:
                self.assertIn(f"⏳ {name}… (usually", out, name)
            self.assertNotIn("\r", out)          # no live timer when output isn't a terminal

    def test_ticker_shows_elapsed_time_on_a_terminal(self):
        class Tty(io.StringIO):
            def isatty(self):
                return True
        out = Tty()
        stop = stages.start_ticker(out, "bootstrap", "5–10 min", every=0.01)
        import time
        time.sleep(0.05)
        stop()
        self.assertIn("\r⏳ bootstrap… 0:00  (usually 5–10 min)", out.getvalue())

    def test_ends_with_a_clear_next_block(self):
        with tempfile.TemporaryDirectory() as d:
            stages.run_up(d, env=self.env(d))
            tail = self.out.getvalue().split("NEXT")[-1]
            for a in CONF["AREAS"].split():
                self.assertIn(f"ssh -t nori attach {a}", tail)
            for text in ("same terminal", "Do you trust the files in this folder?", "Enable Remote Control?",
                         "Ctrl+b then d", "Not Ctrl+d or /exit", 'send "hi"', "Later (optional)",
                         "./nori up --add tailscale", "Claude app after Quick setup"):
                self.assertIn(text, tail)

    def test_full_run_order_and_no_secret_leaks(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(stages.run_up(d, env=self.env(d)), 0)
            st = self.state(d)
            self.assertEqual((st["server_id"], st["ip"], st["stage"]), (42, "203.0.113.5", "prompts"))
            raw = (Path(d) / "generated/up-state.json").read_text() + self.out.getvalue()
            for v in self.KEYS.values():
                self.assertNotIn(v, raw)
                for _, command, _ in self.cmds:
                    self.assertNotIn(v, command)
            sent = [s for _, _, s in self.cmds if s]
            self.assertIn("1:BOTMAIN", sent)
            self.assertEqual(oct((Path(d) / "generated/up-state.json").stat().st_mode & 0o777), "0o600")

    def test_price_needs_exact_yes(self):
        for ans in ("y", "YES ", "", "no"):
            with tempfile.TemporaryDirectory() as d:
                api = FakeAPI()
                self.assertEqual(stages.run_up(d, env=self.env(d, api=api, answer=ans)), 1)
                self.assertFalse(any(p == "/servers" and m == "POST" for m, p, _ in api.calls), ans)

    def test_rerun_never_creates_second_server(self):
        with tempfile.TemporaryDirectory() as d:
            api = FakeAPI()
            stages.run_up(d, env=self.env(d, api=api))
            stages.run_up(d, env=self.env(d, api=api))
            self.assertEqual(sum(1 for m, p, _ in api.calls if m == "POST" and p == "/servers"), 1)

    def test_gone_server_asks_again(self):
        with tempfile.TemporaryDirectory() as d:
            api = FakeAPI()
            stages.run_up(d, env=self.env(d, api=api))
            st = self.state(d)
            st["stage"] = "create"  # interrupted before ssh: the server is still being relied on
            (Path(d) / "generated/up-state.json").write_text(json.dumps(st))
            api.servers.clear()
            self.assertEqual(stages.run_up(d, env=self.env(d, api=api, answer="no")), 1)
            self.assertIn("no longer exists", self.out.getvalue())

    def test_host_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as d:
            stages.run_up(d, env=self.env(d))
            self.assertEqual(stages.run_up(d, host="198.51.100.9", env=self.env(d)), 1)
            self.assertIn("203.0.113.5", self.out.getvalue())

    def test_existing_host_skips_hetzner(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.env(d)
            e["keys"].pop("hetzner")
            e["hetzner"] = None
            self.assertEqual(stages.run_up(d, host="198.51.100.9", env=e), 0)
            self.assertEqual(self.state(d)["ip"], "198.51.100.9")

    def test_override_shows_its_own_price_and_unavailable_fails(self):
        with tempfile.TemporaryDirectory() as d:
            api = FakeAPI(available={"fsn1": ["cax11"], "nbg1": ["cx33"]})
            e = self.env(d, api=api)
            asked = []
            e["confirm"] = lambda q: asked.append(q) or "yes"
            self.assertEqual(stages.run_up(d, type_="cx33", location="nbg1", env=e), 0)
            self.assertIn("CX33", asked[0])
            self.assertIn("nbg1", asked[0])
            self.assertIn("€7.99", asked[0])
        with tempfile.TemporaryDirectory() as d:
            api = FakeAPI(available={"fsn1": ["cax11"]})
            self.assertEqual(stages.run_up(d, type_="cx33", location="nbg1", env=self.env(d, api=api)), 1)
            self.assertIn("CX33 isn't available in nbg1", self.out.getvalue())
            self.assertFalse(any(p == "/servers" and m == "POST" for m, p, _ in api.calls))

    def test_bootstrap_resume_after_root_login_disabled(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.env(d)
            plain = e["ssh"]
            def ssh(alias, command, stdin=None, **kw):
                if command == "true":
                    return 255, "root@x: Permission denied (publickey)."
                return plain(alias, command, stdin=stdin)
            e["ssh"] = ssh
            self.assertEqual(stages.run_up(d, env=e), 0)
            cmds = [c for _, c, _ in self.cmds]
            self.assertIn("sudo bash /root/nori/bootstrap.sh", cmds)
            self.assertNotIn("cd /root/nori && bash bootstrap.sh", cmds)

    ONE = "sudo -S -p '' -v && sudo -n bash ~/nori/bootstrap.sh </dev/null"

    def test_admin_full_sudo_always_chpasswd(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(stages.run_up(d, env=self.env(d)), 0)
            cmds = [c for _, c, _ in self.cmds]
            self.assertIn("sudo chpasswd", cmds)
            self.assertLess(cmds.index("sudo chpasswd"), cmds.index(self.ONE))
            self.assertIn(("nori", "sudo chpasswd", "admin:pw-pw-pw-pw-pw"), self.cmds)
            for v in self.KEYS.values():
                for c in cmds:
                    self.assertNotIn(v, c)

    def test_admin_limited_skips_chpasswd(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.env(d)
            plain = e["ssh"]
            e["ssh"] = lambda alias, command, stdin=None, **kw: (1, "sudo: a password is required") if command == "sudo -n true" else plain(alias, command, stdin=stdin)
            self.assertEqual(stages.run_up(d, env=e), 0)
            cmds = [c for _, c, _ in self.cmds]
            self.assertNotIn("sudo chpasswd", cmds)
            self.assertIn(self.ONE, cmds)
            self.assertNotIn("passwd -S", cmds)

    def _admin_check(self, result):
        with tempfile.TemporaryDirectory() as d:
            e = self.env(d)
            plain = e["ssh"]
            e["ssh"] = lambda alias, command, stdin=None, **kw: result if command == "sudo -n true" else plain(alias, command, stdin=stdin)
            rc = stages.run_up(d, env=e)
            return rc, [c for _, c, _ in self.cmds]

    def test_admin_sudo_check_rc255_aborts(self):
        rc, cmds = self._admin_check((255, "ssh: connection reset"))
        self.assertEqual(rc, 1)
        self.assertIn("✗ admin: couldn't check sudo", self.out.getvalue())
        self.assertIn("run ./nori up again", self.out.getvalue())
        self.assertNotIn("sudo chpasswd", cmds)
        self.assertNotIn(self.ONE, cmds)

    def test_admin_sudo_check_rc1_other_text_aborts(self):
        rc, cmds = self._admin_check((1, "sudo: something else"))
        self.assertEqual(rc, 1)
        self.assertNotIn("sudo chpasswd", cmds)
        self.assertNotIn(self.ONE, cmds)

    def test_admin_sudo_check_rc0_chpasswd(self):
        rc, cmds = self._admin_check((0, ""))
        self.assertEqual(rc, 0)
        self.assertIn("sudo chpasswd", cmds)

    def test_admin_wrong_password_message(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.env(d)
            plain = e["ssh"]
            def ssh(alias, command, stdin=None, **kw):
                if command == "sudo -n true":
                    return 1, "sudo: a password is required"
                if command == self.ONE:
                    return 1, "Sorry, try again.\nsudo: 1 incorrect password attempt"
                return plain(alias, command, stdin=stdin)
            e["ssh"] = ssh
            self.assertEqual(stages.run_up(d, env=e), 1)
            self.assertIn("✗ admin: that isn't the admin password you set before", self.out.getvalue())
            self.assertNotIn("pw-pw-pw", self.out.getvalue())

    def test_rerun_labels_admin_password_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            stages.run_up(d, env=self.env(d))
            st = self.state(d)
            st["stage"] = "tokens"
            (Path(d) / "generated/up-state.json").write_text(json.dumps(st))
            e = self.env(d)
            del e["keys"]
            seen = {}
            def ask(names, hint=None):
                seen["hint"] = hint
                return dict(self.KEYS)
            e["ask_keys"] = ask
            stages.run_up(d, env=e)
            self.assertIn("if you set one", seen["hint"]["admin_password"])

    def test_price_line_with_and_without_ipv4(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.env(d)
            asked = []
            e["confirm"] = lambda q: asked.append(q) or "no"
            stages.run_up(d, env=e)
            self.assertIn("€4.99 + €0.61 IPv4 = €5.60/month", asked[0])
        with tempfile.TemporaryDirectory() as d:
            api = FakeAPI()
            api.pricing = False
            e = self.env(d, api=api)
            asked = []
            e["confirm"] = lambda q: asked.append(q) or "no"
            stages.run_up(d, env=e)
            self.assertIn("€4.99/month + IPv4 (see hetzner.com/cloud)", asked[0])

    def test_type_is_lowercased(self):
        with tempfile.TemporaryDirectory() as d:
            api = FakeAPI()
            self.assertEqual(stages.run_up(d, type_="CX33", env=self.env(d, api=api)), 0)
            body = [b for m, p, b in api.calls if m == "POST" and p == "/servers"][0]
            self.assertEqual(body["server_type"], "cx33")

    def test_ctrl_c_is_clean(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.env(d)
            def stop(q):
                raise KeyboardInterrupt
            e["confirm"] = stop
            self.assertEqual(stages.run_up(d, env=e), 130)
            self.assertIn("stopped. Run ./nori up again to continue.", self.out.getvalue())

    def test_host_prints_pubkey_and_waits(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.env(d)
            e["keys"].pop("hetzner")
            e["hetzner"] = None
            asked = []
            e["confirm"] = lambda q: asked.append(q) or ""
            self.assertEqual(stages.run_up(d, host="198.51.100.9", env=e), 0)
            self.assertIn("ssh-ed25519 AAAA nori", self.out.getvalue())
            self.assertIn("authorized_keys", self.out.getvalue())
            self.assertEqual(len(asked), 1)

    def test_rerun_after_done_asks_for_no_keys(self):
        with tempfile.TemporaryDirectory() as d:
            api = FakeAPI()
            stages.run_up(d, env=self.env(d, api=api))
            e = self.env(d, api=api)
            del e["keys"]
            def boom(names):
                raise AssertionError(f"asked for {names}")
            e["ask_keys"] = boom
            self.assertEqual(stages.run_up(d, env=e), 0)

    def test_keys_for_only_unfinished(self):
        st = {"server_id": 1, "stage": "tailscale"}
        self.assertEqual(stages.keys_for(CONF, st, True),
                         ["claude", "bot:main", "bot:work", "bot:ops", "admin_password"])
        self.assertEqual(stages.keys_for(CONF, {"server_id": 1, "stage": "create"}, True)[0], "hetzner")

    def test_error_names_stage_and_user(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.env(d)
            def ssh(alias, command, stdin=None, **kw):
                return (1, "boom") if "set-token claude work" in command else (0, "")
            e["ssh"] = ssh
            self.assertEqual(stages.run_up(d, env=e), 1)
            self.assertIn("✗ claude:", self.out.getvalue())
            self.assertIn("(work)", self.out.getvalue())

    def test_eof_at_confirm_is_clean(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.env(d)
            def eof(q):
                raise EOFError
            e["confirm"] = eof
            self.assertEqual(stages.run_up(d, env=e), 1)
            self.assertIn("run ./nori up again", self.out.getvalue())

    def test_stage_commands_follow_stage_order(self):
        with tempfile.TemporaryDirectory() as d:
            stages.run_up(d, env=self.env(d))
            cmds = [c for _, c, _ in self.cmds]
            marks = ["cd /root/nori && bash bootstrap.sh", "set-token claude", "set-token main",
                     "chpasswd", "setup.sh --restart"]
            idx = [next(i for i, c in enumerate(cmds) if m in c) for m in marks]
            self.assertEqual(idx, sorted(idx))
            self.assertEqual(["bootstrap", "tailscale", "claude", "tokens", "admin", "setup"],
                             [s for s in stages.STAGES if s in ("bootstrap", "tailscale", "claude", "tokens", "admin", "setup")])
            self.assertFalse(any("tailscale up" in c for c in cmds))

    def test_failed_fallback_retries_from_root_again(self):
        with tempfile.TemporaryDirectory() as d:
            users = []
            e = self.env(d)
            e["upsert_host"] = lambda cfg, alias, ip, user: users.append(user)
            plain = e["ssh"]
            def ssh(alias, command, stdin=None, **kw):
                if command == "true":
                    return 255, "Permission denied (publickey)"
                if command == "sudo bash /root/nori/bootstrap.sh":
                    self.cmds.append((alias, command, stdin))
                    return 1, "nope"
                return plain(alias, command, stdin=stdin)
            e["ssh"] = ssh
            self.assertEqual(stages.run_up(d, env=e), 1)
            e2 = self.env(d)
            e2["upsert_host"] = e["upsert_host"]
            e2["ssh"] = ssh
            self.assertEqual(stages.run_up(d, env=e2), 1)
            self.assertNotIn("cd /root/nori && bash bootstrap.sh", [c for _, c, _ in self.cmds])
            # each attempt resets to root before falling back to admin
            self.assertEqual(users[users.index("admin") + 1], "root")

    def test_probe_failure_without_denied_does_not_switch_to_admin(self):
        with tempfile.TemporaryDirectory() as d:
            users = []
            e = self.env(d)
            e["upsert_host"] = lambda cfg, alias, ip, user: users.append(user)
            e["ssh"] = lambda alias, command, stdin=None, **kw: (255, "Connection timed out") if command == "true" else (0, "")
            self.assertEqual(stages.run_up(d, env=e), 1)
            self.assertNotIn("admin", users)
            self.assertIn("bootstrap:", self.out.getvalue())

    def test_no_tailscale_key_asked_and_stage_skipped_but_run_completes(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.env(d)
            self.assertNotIn("tailscale", e["keys"])
            self.assertEqual(stages.run_up(d, env=e), 0)
            st = self.state(d)
            self.assertEqual(st["stage"], "prompts")
            self.assertEqual(st["later"], ["tailscale"])
            self.assertFalse(any("tailscale up" in c for _, c, _ in self.cmds))
            self.assertTrue(any("set-token main" in c for _, c, _ in self.cmds))
            self.assertIn("./nori up --add tailscale", self.out.getvalue().split("NEXT")[-1])

    def test_default_ask_has_no_tailscale(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.env(d)
            del e["keys"]
            asked = []
            e["ask_keys"] = lambda names, **kw: asked.append(list(names)) or dict(self.KEYS)
            stages.run_up(d, env=e)
            self.assertNotIn("tailscale", asked[0])

    def test_next_steps_without_tailscale_later_hides_that_item(self):
        txt = stages.next_steps(["main"], later=False)
        self.assertNotIn("--add tailscale", txt)
        self.assertIn("Later (optional)", txt)
        self.assertIn("Not Ctrl+d or /exit", txt)

    def test_next_steps_language_follows_conf(self):
        for lang in ("Thai", "thai and English", "ไทย", "  Thai"):
            self.assertIn("พร้อมแล้ว", stages.next_steps(["main"], language=lang), lang)
        for lang in ("English", "English and Thai", ""):
            txt = stages.next_steps(["main"], language=lang)
            self.assertIn("The server is ready", txt, lang)
            self.assertNotIn("พร้อมแล้ว", txt)

    def test_next_steps_explains_before_the_command(self):
        for lang, marker, intro in (("English", "copy this line:", "Enable Remote Control?"),
                                    ("Thai", "คัดลอกบรรทัดนี้:", "Enable Remote Control?")):
            txt = stages.next_steps(["main"], language=lang)
            self.assertLess(txt.index(intro), txt.index(marker))
            self.assertLess(txt.index("Ctrl+b"), txt.index(marker))
            self.assertLess(txt.index(marker), txt.index("ssh -t nori attach main"))
            self.assertIn("Ctrl+c", txt)
            self.assertLess(txt.index("ssh -t nori attach main"), txt.index("Ctrl+c"))

    def test_run_up_prints_thai_next_when_conf_says_thai(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.env(d)
            e["conf"] = dict(CONF, LANGUAGES="Thai and English")
            stages.run_up(d, env=e)
            self.assertIn("คัดลอกบรรทัดนี้:", self.out.getvalue())

    def add(self, d, **over):
        e = self.env(d)
        e.pop("keys")
        asked = []
        e["ask_keys"] = lambda names, **kw: asked.append(list(names)) or {"tailscale": "tskey-auth-K"}
        e.update(over)
        return e, asked

    def test_add_tailscale_asks_only_that_key_runs_only_that_stage(self):
        with tempfile.TemporaryDirectory() as d:
            stages.run_up(d, env=self.env(d))
            e, asked = self.add(d)
            self.cmds.clear()
            self.assertEqual(stages.run_up(d, add="tailscale", env=e), 0)
            self.assertEqual(asked, [["tailscale"]])
            ups = [(c, s) for _, c, s in self.cmds if "tailscale up" in c]
            self.assertEqual(len(ups), 1)
            self.assertEqual(ups[0][1], "tskey-auth-K")
            self.assertNotIn("tskey-auth-K", ups[0][0])
            self.assertEqual([c for _, c, _ in self.cmds if "tailscale" not in c and "sudo -n true" not in c
                              and "setup.sh" not in c], [])
            st = self.state(d)
            self.assertEqual(st["later"], [])
            self.assertEqual(st["stage"], "prompts")
            self.assertNotIn("tskey-auth-K", (Path(d) / "generated/up-state.json").read_text() + self.out.getvalue())

    def test_add_tailscale_without_server_errors_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            e, asked = self.add(d)
            self.assertEqual(stages.run_up(d, add="tailscale", env=e), 1)
            self.assertEqual(asked, [])
            self.assertIn("No server yet", self.out.getvalue())

    def test_add_tailscale_with_limited_sudo_uses_admin_password(self):
        with tempfile.TemporaryDirectory() as d:
            stages.run_up(d, env=self.env(d))
            e, asked = self.add(d)
            plain = e["ssh"]
            def ssh(alias, command, stdin=None, **kw):
                if command == "sudo -n true":
                    return 1, "sudo: a password is required"
                return plain(alias, command, stdin=stdin)
            e["ssh"] = ssh
            e["ask_keys"] = lambda names, **kw: asked.append(list(names)) or {"tailscale": "tskey-auth-K", "admin_password": "pw-pw-pw-pw-pw"}
            self.cmds.clear()
            self.assertEqual(stages.run_up(d, add="tailscale", env=e), 0)
            self.assertEqual(asked, [["tailscale", "admin_password"]])
            cmd, _, stdin = [x for x in self.cmds if "tailscale up" in x[1]][0]
            self.assertEqual(stdin, "pw-pw-pw-pw-pw\ntskey-auth-K")
            self.assertNotIn("pw-pw-pw", cmd)

    def test_add_tailscale_reruns_setup_after_tailscale_up(self):
        with tempfile.TemporaryDirectory() as d:
            stages.run_up(d, env=self.env(d))
            e, _ = self.add(d)
            self.cmds.clear()
            self.assertEqual(stages.run_up(d, add="tailscale", env=e), 0)
            cmds = [c for _, c, _ in self.cmds]
            up = next(i for i, c in enumerate(cmds) if "tailscale up" in c)
            setup = next(i for i, c in enumerate(cmds) if "./setup.sh --restart" in c)
            self.assertLess(up, setup)
            self.assertIn("restart", self.out.getvalue())

    def test_add_tailscale_wrong_admin_password_offers_reentry(self):
        with tempfile.TemporaryDirectory() as d:
            stages.run_up(d, env=self.env(d))
            e, asked = self.add(d)
            plain = e["ssh"]
            def ssh(alias, command, stdin=None, **kw):
                if command == "sudo -n true":
                    return 1, "sudo: a password is required"
                if "tailscale up" in command and stdin.startswith("bad"):
                    return 1, "Sorry, try again."
                return plain(alias, command, stdin=stdin)
            e["ssh"] = ssh
            answers = iter([{"tailscale": "tskey-auth-K", "admin_password": "bad-bad-bad-bad"}, {"admin_password": "good-good-good"}])
            e["ask_keys"] = lambda names, **kw: asked.append(list(names)) or next(answers)
            e["confirm"] = lambda q: "y"
            self.assertEqual(stages.run_up(d, add="tailscale", env=e), 0)
            self.assertEqual(asked[1], ["admin_password"])
            self.assertIn("that isn't the admin password you set before", self.out.getvalue())

    def test_tailscale_command_guards_key_behind_sudo_check(self):
        """Run the real command string with fake sudo/tailscale: a wrong password must never reach tailscale."""
        import subprocess, stat
        for good, tag in ((False, "wrong"), (True, "right")):
            with tempfile.TemporaryDirectory() as d:
                bindir = Path(d) / "bin"
                bindir.mkdir()
                log = Path(d) / "log"
                (bindir / "sudo").write_text('''#!/bin/bash
if [[ $1 == -S ]]; then
  read -r pw
  [[ $pw == rightpw ]] || { echo "Sorry, try again." >&2; exit 1; }
  exit 0
fi
exec "$@"
''')
                (bindir / "tailscale").write_text('''#!/bin/bash
for a in "$@"; do case $a in --auth-key=file:*) cat "${a#--auth-key=file:}" > "$LOG";; esac; done
''')
                for f in ("sudo", "tailscale"):
                    (bindir / f).chmod(0o755)
                cmd = stages.tailscale_command("srv", limited=True)
                stdin = ("rightpw" if good else "wrongpw") + "\ntskey-auth-SECRET"
                r = subprocess.run(["bash", "-c", cmd], input=stdin, capture_output=True, text=True,
                                   env={**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "LOG": str(log)})
                if good:
                    self.assertEqual(r.returncode, 0, r.stderr)
                    self.assertEqual(log.read_text(), "tskey-auth-SECRET")
                else:
                    self.assertNotEqual(r.returncode, 0)
                    self.assertFalse(log.exists(), "tailscale must not run after a wrong password")
                self.assertNotIn("tskey-auth-SECRET", cmd)

    def test_add_and_host_together_refused(self):
        import subprocess
        r = subprocess.run([sys.executable, "-B", str(REPO / "nori"), "up", "--add", "tailscale", "--host", "1.2.3.4"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--add", r.stderr)



class AskNori(unittest.TestCase):
    def test_next_steps_say_to_ask_nori(self):
        self.assertIn("Ask Nori in your Claude window", stages.next_steps(["main"]))
        self.assertIn("ถาม Nori", stages.next_steps(["main"], True, "Thai"))
