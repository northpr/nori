import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from helpers import REPO

BIN = REPO / "server/bin"


def run(script, *args, env=None, stdin=None):
    e = {k: v for k, v in os.environ.items() if k not in ("TIMEZONE", "NORI_CONF", "NORI_ROOT")}
    e.update(env or {})
    return subprocess.run([sys.executable, str(BIN / script), *args], env=e, input=stdin,
                          capture_output=True, text=True)


def entry(mid, req, ts, model="claude-x", **usage):
    u = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    u.update(usage)
    return json.dumps({"type": "assistant", "requestId": req, "uuid": "u-" + mid,
                       "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                       "message": {"id": mid, "model": model, "usage": u}})


class UsageReportTests(unittest.TestCase):
    def test_dedupe_and_buckets(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d) / "proj"
            proj.mkdir()
            lines = [
                entry("m1", "r1", now, input_tokens=1, output_tokens=5),            # streaming: same message twice,
                entry("m1", "r1", now, input_tokens=10, output_tokens=50,            # the last entry wins
                      cache_read_input_tokens=7, cache_creation_input_tokens=3),
                entry("m2", "r2", now - timedelta(days=3), output_tokens=100),       # this week, not today
                entry("m3", "r3", now - timedelta(days=9), output_tokens=999),       # too old
                entry("m4", "r4", now, model="<synthetic>", output_tokens=999),      # ignored
                "not json",
            ]
            (proj / "a.jsonl").write_text("\n".join(lines) + "\n")
            r = run("usage-report", env={"USAGE_PROJECTS_DIR": d, "TIMEZONE": "UTC", "NORI_ROOT": d})
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads(r.stdout)
            self.assertEqual(set(out), {"today", "week"})
            self.assertEqual(out["week"]["claude-x"], {"in": 10, "out": 150, "cr": 7, "cc": 3})
            self.assertEqual(set(out["week"]), {"claude-x"})
            today = datetime.now(timezone.utc).date() == now.date()
            if today:
                self.assertEqual(out["today"]["claude-x"], {"in": 10, "out": 50, "cr": 7, "cc": 3})

    def test_bad_timezone_falls_back_to_utc(self):
        with tempfile.TemporaryDirectory() as d:
            r = run("usage-report", env={"USAGE_PROJECTS_DIR": d, "TIMEZONE": "Not/AZone", "NORI_ROOT": d})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout), {"today": {}, "week": {}})


class UsageSnapshotTests(unittest.TestCase):
    def test_writes_file_and_prints(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".claude").mkdir()
            data = {"rate_limits": {"five_hour": {"used_percentage": 42.2, "resets_at": 1000, "x": 1},
                                    "seven_day": {"used_percentage": 61, "resets_at": 2000}}}
            r = run("usage-snapshot", env={"HOME": d}, stdin=json.dumps(data))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "5h 42% · wk 61%")
            snap = json.loads((Path(d) / ".claude/usage-snapshot.json").read_text())
            self.assertEqual(snap["five_hour"], {"used_percentage": 42.2, "resets_at": 1000})
            self.assertEqual(snap["seven_day"], {"used_percentage": 61, "resets_at": 2000})
            self.assertIsInstance(snap["ts"], int)
            self.assertEqual(list((Path(d) / ".claude").glob("*.tmp")), [])

    def test_no_limits(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".claude").mkdir()
            r = run("usage-snapshot", env={"HOME": d}, stdin="{}")
            self.assertEqual((r.returncode, r.stdout.strip()), (0, ""))
            self.assertFalse((Path(d) / ".claude/usage-snapshot.json").exists())


class AskOwnerTests(unittest.TestCase):
    def test_selftest(self):
        r = run("ask-owner", "--selftest")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("selftest ok", r.stdout)


if __name__ == "__main__":
    unittest.main()
