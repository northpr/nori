import json
import hashlib
import re
import tempfile
import unittest
from pathlib import Path

from helpers import REPO, render, repo_files

BASE = '''OWNER_NAME="Alex"
SERVER_NAME="test-server"
TIMEZONE="UTC"
ADMIN_USER="admin"
CHAT_ALLOWED_IDS="123456789"
GITHUB_ACCOUNTS="
your-github-name|Your Name|you@example.com
"
'''

CONFIGS = {
    "starter": BASE + 'AREAS="main"\nAREA_main_PREFIX="m"\nPRESET="starter"\n',
    "recommended": BASE + 'AREAS="main"\nAREA_main_PREFIX="m"\nPRESET="recommended"\n',
    "full-two-areas": BASE + 'AREAS="personal work"\nAREA_personal_PREFIX="p"\nAREA_work_PREFIX="w"\n'
                       'PRESET="full"\nPLANE_BACKUP_REPO="you/nori-backups"\n',
    "flag-override": BASE + 'AREAS="main"\nAREA_main_PREFIX="m"\nPRESET="starter"\nOPS_BOT=true\n',
}

# sha256 of strings that belong to the original owner and must never be in the shared repo
# (only the hashes are published, so this list doesn't leak what it guards). Every word of every
# file, and each part of it split on . _ - @ / :, is hashed and checked against this set.
OWNER_DATA_SHA256 = {
    "3be9579eac8845a0fad861963fe98e8a4e39cbaf3cf41252bd4eff90f83aa1a5",
    "4b7b8c9fc3654cb6739f03c36b0ba7a84f28aa19bf6b45ceede29f76d8a260e4",
    "5911c1f23bba186a0b14f6fa14654ba7acd3d85e49980b10718f662fc0fae95a",
    "6343593eb28216c71f90188b76edd24a540fd0577e22a6d3ac5614261d70428e",
    "640dcb7dab660a7f6fee80ee50709af299923230bf7ddb0d22e6f2eeff89d8ae",
    "97997f16033618eb57caab074191a3fb44a138c319a317dc30df2937f59540d3",
    "bdf25e83b1900f04e3035d91cb94e28eb61f6cbf5086555b07e29704b09d4a0e",
    "d1b6ac2abc458deaffec7f7b6bc2baefb9653dee8e3f9ac4106e994091359fc7",
    "e4e1d764402332df1556e7944951d6091590426cf3a824fb93cd96381d73526b",
    "eb942ed484b8c6a22b234bf58780135dffe2528b391b074585009940bc8b4985",
}
# Files that may name the maintainer (relative to the repo root): CODEOWNERS, and the clone URL in the quickstart.
LEAK_ALLOWED = {".github/CODEOWNERS"}



def owner_data_in(text):
    """Words of text (and their parts split on . _ - @ / : +) whose sha256 is in OWNER_DATA_SHA256."""
    words = set()
    for w in re.findall(r"[a-z0-9][a-z0-9._@/:+-]*[a-z0-9]", text.lower()):
        words.add(w)
        words.update(x for x in re.split(r"[._@/:+-]", w) if x)
    return {w for w in words if hashlib.sha256(w.encode()).hexdigest() in OWNER_DATA_SHA256}


class RenderTests(unittest.TestCase):
    def render(self, name, conf):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "out"
        r = render(conf, out, tmp.name)
        self.assertEqual(r.returncode, 0, f"{name}: {r.stdout}\n{r.stderr}")
        return out

    def test_presets_render(self):
        for name, conf in CONFIGS.items():
            with self.subTest(config=name):
                out = self.render(name, conf)
                for rel in ("crontab", "nori.resolved.conf", "CLAUDE.md", "claude/settings.partial.json",
                            "systemd/claude@.service", "git/gitconfig"):
                    self.assertTrue((out / rel).is_file(), f"missing {rel}")
                json.loads((out / "claude/settings.partial.json").read_text())
                for j in out.rglob("*.json"):
                    json.loads(j.read_text())
                for f in out.rglob("*"):
                    if f.is_file():
                        self.assertNotRegex(f.read_text(errors="replace"), r"\{\{[A-Z_]+\}\}", f"unfilled placeholder in {f}")

    def test_preset_flags(self):
        def resolved(name):
            text = (self.render(name, CONFIGS[name]) / "nori.resolved.conf").read_text()
            return dict(re.findall(r'^([A-Za-z0-9_]+)="?([^"\n]*)"?$', text, re.M))
        self.assertEqual(resolved("starter").get("OPS_BOT"), "false")
        self.assertEqual(resolved("recommended").get("OPS_BOT"), "true")
        self.assertEqual(resolved("full-two-areas").get("PLANE"), "true")
        self.assertEqual(resolved("flag-override").get("OPS_BOT"), "true")

    def resolved(self, conf):
        text = (self.render("conf", conf) / "nori.resolved.conf").read_text()
        return dict(re.findall(r'^([A-Za-z0-9_]+)="?([^"\n]*)"?$', text, re.M))

    def test_work_backup_flag(self):
        main = BASE + 'AREAS="main"\n'
        for preset in ("starter", "recommended", "full"):
            with self.subTest(preset=preset):
                p = f'PRESET="{preset}"\n'
                self.assertEqual(self.resolved(main + p).get("WORK_BACKUP"), "false")
                # opt-in: a backup repo alone (e.g. for Plane) doesn't turn it on
                self.assertEqual(self.resolved(main + p + 'BACKUP_REPO="you/nori-backups"\n').get("WORK_BACKUP"), "false")
                on = self.resolved(main + p + 'BACKUP_REPO="you/nori-backups"\nWORK_BACKUP=true\n')
                self.assertEqual(on.get("WORK_BACKUP"), "true")
                self.assertEqual(on.get("AREA_main_WORK_BACKUP"), "true")
        self.assertEqual(self.resolved(main + 'PLANE_BACKUP_REPO="you/nori-backups"\n').get("WORK_BACKUP"), "false")
        # the older repo name still works for it
        self.assertEqual(self.resolved(main + 'PLANE_BACKUP_REPO="you/b"\nWORK_BACKUP=true\n').get("WORK_BACKUP"), "true")
        # per area: on by default, off when set
        two = BASE + 'AREAS="personal work"\nBACKUP_REPO="you/b"\nWORK_BACKUP=true\nAREA_work_WORK_BACKUP=false\n'
        r = self.resolved(two)
        self.assertEqual((r.get("AREA_personal_WORK_BACKUP"), r.get("AREA_work_WORK_BACKUP")), ("true", "false"))

    def test_work_backup_cron(self):
        main = BASE + 'AREAS="main"\nPRESET="starter"\n'
        on = main + 'BACKUP_REPO="you/nori-backups"\nWORK_BACKUP=true\nHANDOFF_TIME="03:50"\n'
        # with the handoff: in the same line, right after it (so tonight's HANDOFF.md is saved)
        cron = (self.render("on", on) / "crontab").read_text()
        self.assertRegex(cron, r"(?m)^50 3 \* \* \* \S+/nightly-handoff >> \S+/nightly-handoff.log 2>&1; "
                               r"\S+/work-offsite >> \S+/work-backup.log 2>&1 \|\| \S+/ops-bot send \"Work backup failed")
        self.assertEqual(cron.count("work-offsite"), 1)
        # without it: on its own at HANDOFF_TIME
        cron = (self.render("no handoff", on + "HANDOFF=false\n") / "crontab").read_text()
        self.assertRegex(cron, r"(?m)^50 3 \* \* \* \S+/work-offsite >> \S+/work-backup.log 2>&1 \|\| \S+/ops-bot send ")
        self.assertNotIn("nightly-handoff", cron)
        for name, conf in (("off", main), ("repo only", main + 'BACKUP_REPO="you/nori-backups"\n')):
            self.assertNotIn("work-offsite", (self.render(name, conf) / "crontab").read_text(), name)

    def test_status_line_and_ask_owner_rules(self):
        for name in ("recommended", "full-two-areas"):
            out = self.render(name, CONFIGS[name])
            sl = json.loads((out / "claude/settings.partial.json").read_text())["statusLine"]
            self.assertEqual(sl, {"type": "command", "command": "$HOME/.local/bin/usage-snapshot"})
            self.assertIn("ask-owner", (out / "CLAUDE.md").read_text())
        out = self.render("starter", CONFIGS["starter"])      # no Ops bot: nothing reads the snapshot or the outbox
        self.assertNotIn("statusLine", json.loads((out / "claude/settings.partial.json").read_text()))
        self.assertNotIn("ask-owner", (out / "CLAUDE.md").read_text())

    def test_admin_sudo(self):
        text = (self.render("recommended", CONFIGS["recommended"]) / "nori.resolved.conf").read_text()
        self.assertIn('ADMIN_SUDO="limited"', text)          # the default, whatever the preset
        text = (self.render("full", CONFIGS["full-two-areas"] + 'ADMIN_SUDO="full"\n') / "nori.resolved.conf").read_text()
        self.assertIn('ADMIN_SUDO="full"', text)

    def test_two_areas(self):
        out = self.render("full", CONFIGS["full-two-areas"])
        for a in ("personal", "work"):
            self.assertTrue((out / "areas" / a / "CLAUDE.md").is_file())
            self.assertTrue((out / "areas" / a / "settings.json").is_file())

    def test_bad_input_rejected(self):
        for label, conf in {"preset": BASE + 'AREAS="main"\nPRESET="bogus"\n',
                            "reserved area": BASE + 'AREAS="ops"\n',
                            "bad area name": BASE + 'AREAS="Main"\n',
                            "bad WORK_BACKUP": BASE + 'AREAS="main"\nBACKUP_REPO="you/b"\nWORK_BACKUP=yes\n',
                            "WORK_BACKUP without repo": BASE + 'AREAS="main"\nWORK_BACKUP=true\n',
                            "bad area WORK_BACKUP": BASE + 'AREAS="main"\nAREA_main_WORK_BACKUP=no\n',
                            "bad BACKUP_REPO": BASE + 'AREAS="main"\nBACKUP_REPO="not a repo"\n',
                            "admin sudo": BASE + 'AREAS="main"\nADMIN_SUDO="sometimes"\n',
                            "bad PERM_CARDS": BASE + 'AREAS="main"\nPERM_CARDS=maybe\n',
                            "PERM_CARDS without Ops bot": BASE + 'AREAS="main"\nOPS_BOT=false\nPERM_CARDS=true\n'}.items():
            with self.subTest(case=label), tempfile.TemporaryDirectory() as tmp:
                r = render(conf, Path(tmp) / "out", tmp)
                self.assertNotEqual(r.returncode, 0, "should have been rejected")

    def test_claude_code_version(self):
        def resolved(conf):
            text = (self.render("cc", conf) / "nori.resolved.conf").read_text()
            return dict(re.findall(r'^([A-Z_]+)="?([^"\n]*)"?$', text, re.M)).get("CLAUDE_CODE_VERSION")
        pinned = (REPO / "server/claude-code.version").read_text().strip()
        self.assertEqual(resolved(CONFIGS["recommended"]), pinned)            # empty -> the repo file
        for v in ("2.1.100", "stable", "latest"):
            self.assertEqual(resolved(CONFIGS["recommended"] + f'CLAUDE_CODE_VERSION="{v}"\n'), v)
        for bad in ("2.1", "v2.1.100", "next", "2.1.100 ", "2.1.x"):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as tmp:
                r = render(CONFIGS["recommended"] + f'CLAUDE_CODE_VERSION="{bad}"\n', Path(tmp) / "out", tmp)
                self.assertNotEqual(r.returncode, 0, "should have been rejected")
                self.assertIn("CLAUDE_CODE_VERSION", r.stderr)

    def test_perm_cards(self):
        self.assertEqual(self.resolved(CONFIGS["recommended"]).get("PERM_CARDS"), "true")
        self.assertEqual(self.resolved(CONFIGS["starter"]).get("PERM_CARDS"), "false")
        out = self.render("recommended", CONFIGS["recommended"])
        allow = json.loads((out / "claude/settings.partial.json").read_text())["permissions"]["allow"]
        self.assertIn("Bash(git status:*)", allow)
        self.assertFalse([r for r in allow if "push" in r or "merge" in r], "push/merge must keep asking")
        # read-only list must not contain prefixes that can write (--output) or hang (-f, --watch)
        for bad in ("Bash(git log:*)", "Bash(git diff:*)", "Bash(tail:*)", "Bash(gh pr checks:*)"):
            self.assertNotIn(bad, allow)

    def test_perm_say_in_safety_rules(self):
        # the "say where it's going" rule tells the session what to say for the 🔐 prompt, depending on the cards
        def safety(name):
            return (self.render(name, CONFIGS[name]) / "CLAUDE.md").read_text()
        self.assertIn("tap Allow on the Ops card", safety("recommended"))
        self.assertNotIn("check your DM", safety("recommended"))
        self.assertIn("check your DM", safety("starter"))
        self.assertNotIn("tap Allow", safety("starter"))

    def test_prefer_ipv4_flag(self):
        for name in CONFIGS:                                     # opt-in: off in every preset
            self.assertEqual(self.resolved(CONFIGS[name]).get("PREFER_IPV4"), "false", name)
        self.assertEqual(self.resolved(CONFIGS["recommended"] + 'PREFER_IPV4=true\n').get("PREFER_IPV4"), "true")
        with tempfile.TemporaryDirectory() as tmp:
            r = render(CONFIGS["recommended"] + 'PREFER_IPV4="yes"\n', Path(tmp) / "out", tmp)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("PREFER_IPV4", r.stderr)

    def test_no_self_updates(self):
        out = self.render("recommended", CONFIGS["recommended"])
        for rel in ("claude/settings.partial.json", "claude/settings.admin.partial.json"):
            self.assertEqual(json.loads((out / rel).read_text())["env"]["DISABLE_AUTOUPDATER"], "1", rel)

    def test_no_owner_data_in_rendered_output(self):
        out = self.render("full", CONFIGS["full-two-areas"])
        for f in out.rglob("*"):
            if f.is_file():
                hits = owner_data_in(f.read_text(errors="replace"))
                self.assertFalse(hits, f"owner data in rendered {f.name}")


class ClaudeCodePinTests(unittest.TestCase):
    def test_version_file(self):
        text = (REPO / "server/claude-code.version").read_text()
        self.assertRegex(text, r"^\d+\.\d+\.\d+\n?$", "one exact version, one line")

    def test_managed_settings(self):
        m = json.loads((REPO / "server/claude/managed-settings.json").read_text())
        self.assertEqual(m["env"]["DISABLE_AUTOUPDATER"], "1")
        self.assertNotIn("DISABLE_UPDATES", m["env"])    # would block `claude install`, which setup.sh needs
        for rule in ("Bash(git push)", "Bash(git push:*)", "Bash(gh pr merge:*)"):
            self.assertIn(rule, m["permissions"]["ask"])
        cmds = [h["command"] for e in m["hooks"]["PreToolUse"] for h in e["hooks"]]
        self.assertEqual(cmds, ["/opt/nori/server/bin/push-guard"])   # root-owned copy, not a path in a user's home


class RepoLeakTests(unittest.TestCase):
    def test_no_owner_data_in_repo(self):
        for p in repo_files():
            rel = str(p.relative_to(REPO))
            if rel in LEAK_ALLOWED or p.name == "LICENSE":
                continue
            try:
                text = p.read_text().lower()
            except (UnicodeDecodeError, OSError):
                continue
            hits = owner_data_in(text)
            with self.subTest(file=rel):
                self.assertFalse(hits, f"owner data in {rel}")


if __name__ == "__main__":
    unittest.main()
