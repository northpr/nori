import subprocess
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "server" / "bin"


class SecretGuardTest(unittest.TestCase):
    def test_selftest(self):
        p = subprocess.run([str(BIN / "secret-guard"), "--selftest"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
