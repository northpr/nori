"""laptop/setup-laptop.sh only adds (import line + free skill names); laptop/CLAUDE.md imports resolve."""
import os, re, subprocess, tempfile, unittest
from pathlib import Path

from helpers import REPO

SCRIPT = REPO / "laptop/setup-laptop.sh"


class SetupLaptop(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.c = self.home / ".claude"
        (self.c / "skills/why").mkdir(parents=True)            # an existing skill with a shared name
        (self.c / "skills/why/SKILL.md").write_text("mine\n")
        (self.c / "skills/add-endpoint").mkdir()
        self.md = self.c / "CLAUDE.md"
        self.md.write_text("# Global instructions\n\n@~/x/profile/USER.md\n- my rule")   # no trailing newline

    def run_it(self, *args):
        return subprocess.run(["bash", str(SCRIPT), *args], env={"HOME": str(self.home), "PATH": os.environ["PATH"]},
                              text=True, capture_output=True, check=True).stdout

    def snapshot(self):
        return {str(p.relative_to(self.home)): (os.readlink(p) if p.is_symlink() else p.read_text() if p.is_file() else "dir")
                for p in sorted(self.home.rglob("*"))}

    def line(self):
        return f"@{REPO}/laptop/CLAUDE.md"   # REPO isn't under the fake HOME, so the path stays absolute

    def test_dry_run_changes_nothing(self):
        before = self.snapshot()
        out = self.run_it("--dry-run")
        self.assertEqual(self.snapshot(), before)
        self.assertIn("would: add to", out)
        self.assertIn("skip: skill why", out)

    def test_adds_line_and_free_skills_only(self):
        out = self.run_it()
        text = self.md.read_text()
        self.assertTrue(text.startswith("# Global instructions\n\n@~/x/profile/USER.md\n- my rule\n"), text)
        self.assertEqual(text.count(self.line()), 1)
        backups = list((self.c / "nori-backup").iterdir())
        self.assertEqual([b.read_text() for b in backups], ["# Global instructions\n\n@~/x/profile/USER.md\n- my rule"])
        self.assertEqual((self.c / "skills/why/SKILL.md").read_text(), "mine\n")   # existing skill untouched
        self.assertIn("skip: skill why", out)
        self.assertTrue((self.c / "skills/add-endpoint").is_dir())
        self.assertFalse((self.c / "settings.json").exists())

    def test_links_free_skill_names(self):
        (self.c / "skills/why/SKILL.md").unlink()
        (self.c / "skills/why").rmdir()
        self.run_it()
        self.assertEqual(os.readlink(self.c / "skills/why"), str(REPO / "skills/why"))

    def test_rerun_is_a_no_op(self):
        self.run_it()
        before = self.snapshot()
        out = self.run_it()
        self.assertEqual(self.snapshot(), before)
        self.assertIn("already imports", out)

    def test_tilde_path_under_home(self):
        home = Path(tempfile.mkdtemp())
        repo = home / "Code/nori-personal"
        (repo / "laptop").mkdir(parents=True)
        (repo / "skills").mkdir()
        (repo / "laptop/setup-laptop.sh").write_text(SCRIPT.read_text())
        subprocess.run(["bash", str(repo / "laptop/setup-laptop.sh")], env={"HOME": str(home), "PATH": os.environ["PATH"]},
                       capture_output=True, check=True)
        self.assertIn("@~/Code/nori-personal/laptop/CLAUDE.md\n", (home / ".claude/CLAUDE.md").read_text())


class Imports(unittest.TestCase):
    def test_laptop_imports_resolve_and_need_no_config(self):
        found = re.findall(r"^@(\S+)$", (REPO / "laptop/CLAUDE.md").read_text(), re.M)
        self.assertTrue(found)
        for imp in found:
            f = (REPO / "laptop" / imp).resolve()
            self.assertTrue(f.is_file(), imp)
            self.assertNotRegex(f.read_text(), r"\{\{[A-Z_]+\}\}", f"{imp}: the laptop can't fill placeholders")

    def test_server_rules_include_core(self):
        render = (REPO / "scripts/render.py").read_text()
        for core in sorted((REPO / "rules/core").glob("*.md")):
            self.assertIn(f'("rules/core/{core.name}", True)', render)


if __name__ == "__main__":
    unittest.main()
