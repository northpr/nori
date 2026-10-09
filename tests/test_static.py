import ast
import subprocess
import unittest

from helpers import REPO, python_scripts, shell_scripts


class StaticChecks(unittest.TestCase):
    def test_found_scripts(self):
        self.assertGreater(len(shell_scripts()), 5)
        self.assertTrue(any(p.name == "ops-bot" for p in python_scripts()))

    def test_bash_syntax(self):
        for p in shell_scripts():
            with self.subTest(script=str(p.relative_to(REPO))):
                r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_python_syntax(self):
        for p in python_scripts():
            with self.subTest(script=str(p.relative_to(REPO))):
                ast.parse(p.read_text(), filename=str(p))

    def test_no_floating_latest(self):
        for p in [*(REPO / "server/bin").glob("*"), REPO / "bootstrap.sh"]:
            if p.is_file():
                with self.subTest(script=str(p.relative_to(REPO))):
                    self.assertNotIn("@latest", p.read_text())


if __name__ == "__main__":
    unittest.main()
