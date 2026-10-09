"""./nori up: ordered stages that skip what is done, with a state file that never holds a key."""
import json
import os
import shlex
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from . import config, hetzner, keys, remote

STAGES = ["create", "ssh", "copy", "bootstrap", "tailscale", "claude", "tokens", "admin", "setup", "prompts"]
ALIAS = "nori"


def _load(repo):
    p = Path(repo) / "generated/up-state.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _save(repo, st):
    p = Path(repo) / "generated/up-state.json"
    p.parent.mkdir(exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".up-state-")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(st, f, indent=1)
        os.chmod(tmp, 0o600)
        os.replace(tmp, p)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _done(st, stage):
    return st.get("stage") in STAGES and STAGES.index(st["stage"]) >= STAGES.index(stage)


def keys_for(conf, st, use_hetzner, tailscale=False):
    """Only the keys that unfinished stages still need."""
    need_hz = use_hetzner and (not st.get("server_id") or not _done(st, "ssh"))
    out = []
    for n in config.needed_keys(conf, hetzner=need_hz, tailscale=tailscale):
        stage = ("create" if n == "hetzner" else "tailscale" if n == "tailscale" else "claude" if n == "claude"
                 else "admin" if n == "admin_password" else "tokens")
        if n == "hetzner" or not _done(st, stage):
            out.append(n)
    return out


def _price_line(pick):
    if pick.get("ipv4"):
        total = float(pick["price"]) + float(pick["ipv4"])
        return f"€{pick['price']} + €{pick['ipv4']} IPv4 = €{total:.2f}/month"
    return f"€{pick['price']}/month + IPv4 (see hetzner.com/cloud)"


# how long each stage usually takes, so a slow one doesn't look stuck
TYPICAL = {"ssh": "under 1 min", "copy": "under 1 min", "bootstrap": "5–10 min", "tailscale": "under 1 min",
           "claude": "1–3 min", "tokens": "under 1 min", "admin": "3–5 min", "setup": "1–3 min"}


def start_ticker(out, name, typical, every=1.0):
    """On a terminal, keep rewriting '⏳ <stage>… m:ss (usually …)' so it's clear Nori is still working.
    Returns a function that stops it. Does nothing when the output isn't a terminal."""
    if not getattr(out, "isatty", lambda: False)():
        return lambda: None
    done, t0 = threading.Event(), time.monotonic()

    def tick():
        while True:
            s_ = int(time.monotonic() - t0)
            out.write(f"\r⏳ {name}… {s_ // 60}:{s_ % 60:02d}  (usually {typical})")
            out.flush()
            if done.wait(every):
                out.write("\r\033[K")
                out.flush()
                return
    th = threading.Thread(target=tick, daemon=True)
    th.start()
    return lambda: (done.set(), th.join())


TAILSCALE_BODY = ('umask 077; f=$(mktemp); cat > "$f"; sudo tailscale up --auth-key=file:"$f" --hostname={name}; '
                  'rc=$?; rm -f "$f"; exit $rc')


def tailscale_command(server_name, limited=False):
    """The key comes on stdin (after the admin password when sudo is limited), never in argv.
    Everything after the sudo check is inside braces, so a wrong password can't fall through to the key."""
    body = TAILSCALE_BODY.format(name=shlex.quote(server_name))
    return "sudo -S -p '' -v && { " + body + "; }" if limited else body


def next_steps(areas, later=True, language=""):
    """The finish line: what only a human can do now, step by step. Thai when the conf's LANGUAGES starts with Thai."""
    attach = "\n".join(f"      ssh -t {ALIAS} attach {a}" for a in areas)
    th = language.strip().lower().startswith(("thai", "ไทย"))
    if th:
        return ("\n✅ server พร้อมแล้ว\n"
                "NEXT (ประมาณ 2 นาที) ใน terminal นี้:\n"
                " 1. เปิด Claude session ของแต่ละ area ครั้งแรก. จะมีคำถามให้ตอบ (สูงสุด 3 ข้อ ทีละข้อ):\n"
                "      • \"Do you trust the files in this folder?\"  → กด Enter (Yes)\n"
                "      • \"Allow external CLAUDE.md imports?\"      → เลือก Yes แล้วกด Enter\n"
                "      • \"Enable Remote Control?\"                 → พิมพ์ y แล้วกด Enter\n"
                "    พอเห็น prompt ❯ ปกติ: ออกด้วย Ctrl+b แล้วกด d (ห้ามใช้ Ctrl+d หรือ /exit เพราะจะปิด Claude)\n"
                "    คัดลอกบรรทัดนี้:\n"
                f"{attach}\n"
                "    เผลอปิดหน้าต่างหรือกด Ctrl+c? ไม่เป็นไร Claude ยังรันอยู่บน server แค่รันคำสั่งเดิมอีกครั้ง\n"
                " 2. ใน Telegram ส่ง \"hi\" หา bot ของคุณ: ควรเห็น 👀 แล้วมีคำตอบ\n"
                " 3. login GitHub เพื่อให้ push ได้ (docs/setup-guide.md, \"GitHub login\")\n"
                "ทีหลัง (ไม่บังคับ):\n"
                + ("  • preview บนมือถือ (ต้องมี Tailscale): ./nori up --add tailscale\n" if later else "")
                + "  • Claude app / Remote Control: ต้อง login ผ่าน browser ครั้งเดียวต่อ area "
                  "(docs/setup-guide.md, \"Claude app after Quick setup\")"
                + "\n❓ มีคำถามหรือติดตรงไหน? ถาม Nori ในหน้าต่าง Claude ที่เปิดไว้ได้เลย (ที่รัน `claude` ในโฟลเดอร์ nori)")
    return ("\n✅ The server is ready.\n"
            "NEXT (about 2 min), in this same terminal:\n"
            " 1. Open each Claude session for the first time. It asks up to 3 questions, one at a time:\n"
            "      • \"Do you trust the files in this folder?\"  → Enter (Yes)\n"
            "      • \"Allow external CLAUDE.md imports?\"      → pick Yes, Enter\n"
            "      • \"Enable Remote Control?\"                 → y, Enter\n"
            "    At the normal ❯ prompt: leave with Ctrl+b then d. Not Ctrl+d or /exit: those quit Claude.\n"
            "    copy this line:\n"
            f"{attach}\n"
            "    Closed the window or pressed Ctrl+c by accident? Nothing breaks: Claude keeps running on the "
            "server; just run the same command again.\n"
            " 2. In Telegram, send \"hi\" to your bot: you should see 👀, then an answer.\n"
            " 3. GitHub login so it can push (docs/setup-guide.md, \"GitHub login\").\n"
            "Later (optional):\n"
            + ("  • Previews on your phone (needs Tailscale): ./nori up --add tailscale\n" if later else "")
            + "  • Claude app / Remote Control: needs a one-time browser login per area "
              "(docs/setup-guide.md, \"Claude app after Quick setup\")"
            + "\n❓ Questions or stuck? Ask Nori in your Claude window (the one you opened with `claude` in the nori folder).")


class _Stopped(Exception):
    """The user declined to re-enter a key; the error was already shown."""


def add_tailscale(repo, e):
    """./nori up --add tailscale: join the existing server (from the state file) to a tailnet, nothing else."""
    out = e.get("out", sys.stdout)
    say = lambda m: print(m, file=out, flush=True)  # noqa: E731
    st = _load(repo)
    if not st.get("ip") or not _done(st, "bootstrap"):
        say("✗ No server yet (or it isn't set up): run ./nori up first, then ./nori up --add tailscale.")
        return 1
    conf = e.get("conf") or config.load(repo)
    ssh = e.get("ssh", remote.ssh)
    try:
        crc, ctext = ssh(ALIAS, "sudo -n true")
        limited = crc == 1 and "a password is required" in ctext
        if crc != 0 and not limited:
            raise remote.RemoteError(f"couldn't reach the server (exit {crc}): {ctext.strip()[-300:]}")
        names = ["tailscale"] + (["admin_password"] if limited else [])
        k = e.get("keys") or e.get("ask_keys", keys.ask_keys)(names)
        cmd = tailscale_command(conf["SERVER_NAME"], limited)
        while True:
            # sudo is limited since the admin stage: password first, then the key
            stdin = k["admin_password"] + "\n" + k["tailscale"] if limited else k["tailscale"]
            say("⏳ tailscale… (usually under 1 min)")
            rc, text = ssh(ALIAS, cmd, stdin=stdin)
            if rc == 0:
                break
            if limited and ("incorrect password" in text or "Sorry, try again" in text):
                say("✗ tailscale: that isn't the admin password you set before")
                if e.get("confirm", input)(f"Re-enter {keys.label('admin_password')} and retry this step? [y/N] ").strip().lower() not in ("y", "yes"):
                    say("Fix that, then run ./nori up --add tailscale again.")
                    return 1
                k.update(e.get("ask_keys", keys.ask_keys)(["admin_password"]))
                continue
            raise remote.RemoteError(f"`tailscale up` failed (exit {rc}):\n{text[-1500:]}")
        say("⏳ setup (so previews and Plane see Tailscale; the Claude sessions restart)…")
        rc, text = ssh(ALIAS, "cd ~/nori && ./setup.sh --restart")
        if rc != 0:
            raise remote.RemoteError(f"`setup.sh` failed (exit {rc}):\n{text[-1500:]}")
    except KeyboardInterrupt:
        say("\n✗ stopped.")
        return 130
    except (remote.RemoteError, subprocess.TimeoutExpired, EOFError) as err:
        say(f"✗ tailscale: {err}\nFix that, then run ./nori up --add tailscale again.")
        return 1
    st["later"] = [x for x in st.get("later", []) if x != "tailscale"]
    _save(repo, st)
    say("✅ tailscale\nNext: install Tailscale on your phone and laptop and sign in to the same account.")
    return 0


def run_up(repo, host=None, type_=None, location=None, env=None, add=None):
    e = env or {}
    if add == "tailscale":
        return add_tailscale(repo, e)
    out = e.get("out", sys.stdout)
    say = lambda m: print(m, file=out, flush=True)  # noqa: E731
    conf = e.get("conf") or config.load(repo)
    st = _load(repo)
    if host and st.get("ip") and st["ip"] != host:
        say(f"✗ generated/up-state.json is for {st['ip']}, not {host}. Move it away to start over.")
        return 1
    type_ = type_.lower() if type_ else type_
    use_hetzner = not host and not st.get("host")
    ssh = e.get("ssh", remote.ssh)
    admin, areas = conf["ADMIN_USER"], conf["AREAS"].split()
    home = Path(e.get("home", Path.home()))
    cur = ["keys"]
    failed = [None]  # the key the last failure points at, if any

    def fix_and_retry(err):
        """After a failure caused by one key: offer to re-enter just that key and retry this step."""
        name = failed[0]
        if not name:
            return False
        say(f"✗ {cur[0]}: {err}")
        if e.get("confirm", input)(f"Re-enter {keys.label(name)} and retry this step? [y/N] ").strip().lower() not in ("y", "yes"):
            raise _Stopped()
        k.update(e.get("ask_keys", keys.ask_keys)([name]))
        return True

    def step(name, fn, key=None):
        if _done(st, name):
            return
        cur[0] = name
        typical = TYPICAL.get(name)
        say(f"⏳ {name}…" + (f" (usually {typical})" if typical else ""))
        while True:
            failed[0] = key
            stop = start_ticker(out, name, typical) if typical else (lambda: None)
            try:
                fn()
                break
            except (hetzner.HetznerError, remote.RemoteError) as err:
                stop()
                if not fix_and_retry(err):
                    raise
            finally:
                stop()
        st["stage"] = name
        _save(repo, st)
        say(f"✅ {name}")

    def run(cmd, stdin=None, label=None, key=None):
        rc, text = ssh(ALIAS, cmd, stdin=stdin)
        if rc != 0:
            failed[0] = key
            who = f" ({label})" if label else ""
            raise remote.RemoteError(f"`{cmd.split()[0]}`{who} failed (exit {rc}):\n{text[-1500:]}")

    try:
        names = keys_for(conf, st, use_hetzner)
        k = e.get("keys")
        if k is None:
            hint = {"admin_password": "the admin password you set before (if you set one)"} if st.get("ip") else None
            ask = e.get("ask_keys", keys.ask_keys)
            k = (ask(names, hint=hint) if hint and "admin_password" in names else ask(names)) if names else {}
        cur[0] = "create"

        def create_on_hetzner():
            """True when the server exists (created now or before); False when the price wasn't accepted."""
            nonlocal st
            hz = e.get("hetzner") or e.get("hetzner_factory", hetzner.Hetzner)(k["hetzner"])
            if True:
                hz.check()
                if st.get("server_id") and hz.server(st["server_id"]) is None:
                    say(f"⚠️ The server in generated/up-state.json (id {st['server_id']}) no longer exists.")
                    st = {}
                if not st.get("server_id"):
                    size = config.server_size(conf)
                    if type_ or location:
                        last = None
                        for t in ([type_] if type_ else hetzner.TYPES[size]):
                            try:
                                pick = hz.price_for(t, location)
                                break
                            except hetzner.HetznerError as err:
                                last = err
                        else:
                            raise last
                    else:
                        pick = hz.pick(size)
                    q = f"Create \"{conf['SERVER_NAME']}\" ({pick['type'].upper()}, {pick['location']}, {_price_line(pick)})? Type yes: "
                    if e.get("confirm", input)(q) != "yes":
                        say("Nothing created.")
                        return False
                    pub = e.get("ensure_key", remote.ensure_key)(home)
                    srv = hz.create(conf["SERVER_NAME"], pick["type"], pick["location"], hz.ssh_key_id("nori", pub))
                    st = {"server_id": srv["id"], "name": conf["SERVER_NAME"], "ip": srv["ip"], "type": pick["type"],
                          "location": pick["location"], "stage": "create"}
                    _save(repo, st)
                    hz.wait_running(srv["id"])
                    say(f"✅ create ({srv['ip']})")
            return True

        # create: a Hetzner server, or the given host
        if use_hetzner and "hetzner" in names:
            while True:
                failed[0] = "hetzner"
                try:
                    if not create_on_hetzner():
                        return 1
                    break
                except hetzner.HetznerError as err:
                    # only a token problem is fixed by a new token (not "sold out" or a network error)
                    if getattr(err, "status", None) not in (401, 403) or not fix_and_retry(err):
                        raise
        elif not use_hetzner and not st:
            st = {"host": host, "ip": host, "stage": "create"}
            _save(repo, st)

        upsert = e.get("upsert_host", remote.upsert_host)
        cfg = home / ".ssh" / "config"

        if not use_hetzner and not _done(st, "ssh"):
            pub = e.get("ensure_key", remote.ensure_key)(home)
            say(f"Your Nori public key:\n{pub}\n"
                "Add this line to root's ~/.ssh/authorized_keys on that server (provider console, or your current ssh), "
                "then press Enter.")
            e.get("confirm", input)("")

        def to_root():
            upsert(cfg, ALIAS, st["ip"], "root")
            e.get("wait_ssh", remote.wait_ssh)(ALIAS)
        step("ssh", to_root)
        step("copy", lambda: e.get("copy_repo", remote.copy_repo)(ALIAS, repo))

        def bootstrap():
            upsert(cfg, ALIAS, st["ip"], "root")  # an earlier run may have left the alias on the admin
            rc, text = ssh(ALIAS, "true")
            if rc == 0:
                run("cd /root/nori && bash bootstrap.sh")
                upsert(cfg, ALIAS, st["ip"], admin)
            elif "Permission denied" in text:  # root login already off from an earlier, interrupted run
                upsert(cfg, ALIAS, st["ip"], admin)
                run("sudo bash /root/nori/bootstrap.sh")
            else:
                raise remote.RemoteError(f"couldn't reach the server as root (exit {rc}):\n{text[-500:]}")
        step("bootstrap", bootstrap)
        if "tailscale" in k:
            step("tailscale", lambda: run(tailscale_command(conf["SERVER_NAME"]),
                                          stdin=k["tailscale"], key="tailscale"), key="tailscale")
        elif not _done(st, "tailscale"):  # Telegram first: skipped, not failed; later runs go on
            st["stage"] = "tailscale"
            st["later"] = sorted(set(st.get("later", [])) | {"tailscale"})
            _save(repo, st)
            say("⏭ tailscale skipped (optional; add it later with ./nori up --add tailscale)")

        def claude():
            for who in [admin] + areas:
                run(f"~/nori/server/bin/set-token claude {shlex.quote(who)}", stdin=k["claude"], label=who, key="claude")
            for a in areas:
                run(f"cd / && sudo -u {shlex.quote(a)} -H bash -lc 'claude plugin marketplace add anthropics/claude-plugins-official; "
                    f"claude plugin install telegram@claude-plugins-official || claude plugin list | grep -q telegram'", label=a)
        step("claude", claude)

        def tokens():
            for a in areas:
                run(f"~/nori/server/bin/set-token {shlex.quote(a)}", stdin=k[f"bot:{a}"], label=a, key=f"bot:{a}")
            if "bot:ops" in k:
                run("~/nori/server/bin/set-token ops", stdin=k["bot:ops"], label="ops", key="bot:ops")
        step("tokens", tokens)

        def admin_stage():
            pw = k["admin_password"]
            failed[0] = "admin_password"
            crc, ctext = ssh(ALIAS, "sudo -n true")
            if crc == 0:  # still full NOPASSWD sudo: this run's password is the one to set
                run("sudo chpasswd", stdin=f"{admin}:{pw}", key="admin_password")
            elif not (crc == 1 and "a password is required" in ctext):  # not provably limited (e.g. ssh rc 255)
                raise remote.RemoteError(f"couldn't check sudo (exit {crc}): {ctext.strip()[-300:]}; run ./nori up again")
            # one ssh command: both sudo calls share a parent shell, so the credential cache applies without a tty.
            # Already limited: sudo -S -v is what checks the password.
            rc, text = ssh(ALIAS, "sudo -S -p '' -v && sudo -n bash ~/nori/bootstrap.sh </dev/null", stdin=pw + "\n")
            if rc != 0:
                if "incorrect password" in text or "Sorry, try again" in text:
                    raise remote.RemoteError("that isn't the admin password you set before")
                raise remote.RemoteError(f"`sudo` (second bootstrap) failed (exit {rc}):\n{text[-1500:]}")
        step("admin", admin_stage, key="admin_password")
        step("setup", lambda: run("cd ~/nori && ./setup.sh --restart"))
        step("prompts", lambda: None)  # only a human answers the first-run questions: see NEXT below
    except _Stopped:
        say("Fix that, then run ./nori up again: it continues from here.")
        return 1
    except KeyboardInterrupt:
        say("\n✗ stopped. Run ./nori up again to continue.")
        return 130
    except (hetzner.HetznerError, remote.RemoteError, subprocess.TimeoutExpired, EOFError) as err:
        what = "timed out" if isinstance(err, subprocess.TimeoutExpired) else (
            "no answer (input closed)" if isinstance(err, EOFError) else str(err))
        say(f"✗ {cur[0]}: {what}\nFix that, then run ./nori up again: it continues from here.")
        return 1
    say(next_steps(areas, later="tailscale" in st.get("later", []), language=conf.get("LANGUAGES", "")))
    return 0
