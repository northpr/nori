"""scripts/lib.sh merge_json: permissions.allow is unioned, everything else keeps the old semantics."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import REPO


@unittest.skipUnless(shutil.which("jq"), "jq not installed")
class MergeJson(unittest.TestCase):
    def run_merge(self, part, live, mode=""):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "part.json").write_text(json.dumps(part))
        (tmp / "live.json").write_text(json.dumps(live))
        script = (f'source "{REPO}/scripts/lib.sh"; MODE="{mode}"; BACKUP="{tmp}/bk"; drift=0; '
                  f'note() {{ echo "$*"; }}; merge_json "{tmp}/part.json" "{tmp}/live.json"; echo "drift=$drift"')
        r = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        return json.loads((tmp / "live.json").read_text()), r

    def test_allow_is_unioned_in_stable_order(self):
        live = {"permissions": {"allow": ["Bash(mine:*)", "Bash(ls:*)"], "ask": ["x"]}, "keep": 1}
        part = {"permissions": {"allow": ["Bash(ls:*)", "Bash(new:*)"], "ask": ["y"]}}
        out, _ = self.run_merge(part, live)
        self.assertEqual(out["permissions"]["allow"], ["Bash(mine:*)", "Bash(ls:*)", "Bash(new:*)"])
        self.assertEqual(out["permissions"]["ask"], ["y"])      # other arrays still replaced
        self.assertEqual(out["keep"], 1)

    def test_allow_created_when_live_has_none(self):
        out, _ = self.run_merge({"permissions": {"allow": ["a", "b"]}}, {})
        self.assertEqual(out["permissions"]["allow"], ["a", "b"])

    def test_check_reports_no_drift_with_extra_user_rules(self):
        live = {"permissions": {"allow": ["Bash(mine:*)", "a", "b"]}}
        out, r = self.run_merge({"permissions": {"allow": ["a", "b"]}}, live, "--check")
        self.assertIn("drift=0", r.stdout)
        self.assertEqual(out, live)

    def test_check_reports_drift_when_ours_missing(self):
        _, r = self.run_merge({"permissions": {"allow": ["a", "b"]}}, {"permissions": {"allow": ["a"]}}, "--check")
        self.assertIn("drift=1", r.stdout)

    def test_idempotent(self):
        part = {"permissions": {"allow": ["a", "b"]}}
        out, _ = self.run_merge(part, {"permissions": {"allow": ["z"]}})
        out2, r = self.run_merge(part, out)
        self.assertEqual(out2, out)
        self.assertIn("drift=0", r.stdout)

    def test_partial_without_allow_leaves_live_alone(self):
        live = {"permissions": {"allow": ["z"]}}
        out, _ = self.run_merge({"env": {"A": "1"}}, live)
        self.assertEqual(out["permissions"]["allow"], ["z"])
        self.assertEqual(out["env"], {"A": "1"})


if __name__ == "__main__":
    unittest.main()
