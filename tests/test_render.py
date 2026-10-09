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
# Files that may name the maintainer (relative to the repo root).
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
            return dict(re.findall(r'^([A-Z_]+)="?([^"\n]*)"?$', text, re.M))
        self.assertEqual(resolved("starter").get("OPS_BOT"), "false")
        self.assertEqual(resolved("recommended").get("OPS_BOT"), "true")
        self.assertEqual(resolved("full-two-areas").get("PLANE"), "true")
        self.assertEqual(resolved("flag-override").get("OPS_BOT"), "true")

    def test_two_areas(self):
        out = self.render("full", CONFIGS["full-two-areas"])
        for a in ("personal", "work"):
            self.assertTrue((out / "areas" / a / "CLAUDE.md").is_file())
            self.assertTrue((out / "areas" / a / "settings.json").is_file())

    def test_bad_input_rejected(self):
        for label, conf in {"preset": BASE + 'AREAS="main"\nPRESET="bogus"\n',
                            "reserved area": BASE + 'AREAS="ops"\n',
                            "bad area name": BASE + 'AREAS="Main"\n'}.items():
            with self.subTest(case=label), tempfile.TemporaryDirectory() as tmp:
                r = render(conf, Path(tmp) / "out", tmp)
                self.assertNotEqual(r.returncode, 0, "should have been rejected")

    def test_no_owner_data_in_rendered_output(self):
        out = self.render("full", CONFIGS["full-two-areas"])
        for f in out.rglob("*"):
            if f.is_file():
                hits = owner_data_in(f.read_text(errors="replace"))
                self.assertFalse(hits, f"owner data in rendered {f.name}")


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
