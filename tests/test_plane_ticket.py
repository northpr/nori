"""server/bin/plane-ticket: input parsing, argv validation, ticket creation against a stubbed Plane (no network)."""
import contextlib, importlib.machinery, io, os, subprocess, sys, tempfile, unittest
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]


def load():
    argv, sys.argv = sys.argv, ["plane-ticket", "lib"]
    try:
        return importlib.machinery.SourceFileLoader("pt", str(REPO / "server/bin/plane-ticket")).load_module()
    finally:
        sys.argv = argv


class ToHtml(unittest.TestCase):
    def test_paragraphs_lists_and_escaping(self):
        h = load().to_html("Intro <b>\n\n- one\n- two & three\n\nEnd")
        self.assertEqual(h, "<p>Intro &lt;b&gt;</p><ul><li>one</li><li>two &amp; three</li></ul><p>End</p>")

    def test_empty(self):
        self.assertEqual(load().to_html("  \n"), "")


class ParseInput(unittest.TestCase):
    def test_title_first_line_rest_description(self):
        self.assertEqual(load().parse_input("\n  \n  Fix   X \tin Y \nbody 1\n\n- a\n"), ("Fix X in Y", "body 1\n\n- a\n"))

    def test_title_only(self):
        self.assertEqual(load().parse_input("Just a title"), ("Just a title", ""))

    def test_blank(self):
        self.assertEqual(load().parse_input(" \n\n"), ("", ""))

    def test_title_capped(self):
        self.assertEqual(len(load().parse_input("x" * 400)[0]), 255)


class Validation(unittest.TestCase):
    def run_main(self, argv, text=""):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = load().main(argv, text)
        return rc, err.getvalue()

    def exits_2(self, argv):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as c:
            load().main(argv, "T\nbody")
        self.assertEqual(c.exception.code, 2)

    def test_blank_title_rejected(self):
        rc, err = self.run_main(["--project", "APP"], "  \n\n")
        self.assertEqual(rc, 2)
        self.assertIn("title", err)

    def test_description_too_long_rejected(self):
        rc, err = self.run_main(["--project", "APP"], "T\n" + "a" * 20001)
        self.assertEqual(rc, 2)
        self.assertIn("20000", err)

    def test_bad_priority(self):
        self.exits_2(["--project", "APP", "--priority", "huge"])

    def test_rejects_malformed_project(self):
        self.exits_2(["--project", "APP; rm -rf /"])
        self.exits_2(["--project", "app"])

    def test_rejects_malformed_label(self):
        self.exits_2(["--project", "APP", "--label", "x$(id)"])
        self.exits_2(["--project", "APP", "--label", "Bug"])

    def test_no_title_flag(self):
        self.exits_2(["--project", "APP", "--title", "Fix X"])


class Create(unittest.TestCase):
    """main() with the Ops bot's Plane client replaced by a fake: nothing leaves the process."""

    def run_main(self, argv, text, cat=None, fresh=None, ob=None):
        pt = load()
        calls, fetches = [], []
        self.fetches = fetches

        class FakeOb:
            @staticmethod
            def plane_catalog(only=None):
                return {"APP": cat} if cat else {}

            @staticmethod
            def _fetch_catalog():
                fetches.append(1)
                return {"APP": fresh or cat}

            @staticmethod
            def plane(method, path, body=None):
                calls.append((method, path, body))
                if method == "GET":
                    return {"results": [{"identifier": "APP"}, {"identifier": "WEB"}]}
                return {"sequence_id": 14}
        pt.load_ops_bot = lambda: ob or FakeOb
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = pt.main(argv, text)
        return rc, out.getvalue(), err.getvalue(), calls

    CAT = {"id": "p1", "labels": {"bug": "L1", "needs-me": "L2"}, "todo": "S1"}

    def test_creates_ticket_with_labels_state_and_html(self):
        rc, out, err, calls = self.run_main(["--project", "APP", "--priority", "high", "--label", "bug", "--label", "nope"],
                                            "Fix X\n\n- a\nbody & more", self.CAT)
        self.assertEqual((rc, out.strip()), (0, "APP-14"))
        self.assertIn("no label 'nope'", err)
        method, path, body = calls[-1]
        self.assertEqual((method, path), ("POST", "/projects/p1/work-items/"))
        self.assertEqual(body["name"], "Fix X")
        self.assertEqual((body["priority"], body["labels"], body["state"]), ("high", ["L1"], "S1"))
        self.assertEqual(body["description_html"], "<ul><li>a</li></ul><p>body &amp; more</p>")

    def test_label_miss_refetches_catalog_once(self):
        fresh = {**self.CAT, "labels": {**self.CAT["labels"], "idea": "L9"}}
        rc, out, err, calls = self.run_main(["--project", "APP", "--label", "idea"], "T", self.CAT, fresh)
        self.assertEqual((rc, calls[-1][2]["labels"], self.fetches, err), (0, ["L9"], [1], ""))
        rc, out, err, calls = self.run_main(["--project", "APP", "--label", "bug"], "T", self.CAT)
        self.assertEqual(self.fetches, [])   # no miss, no refetch

    def test_missing_token_file_is_a_clean_error(self):
        class NoToken:
            @staticmethod
            def plane_catalog(only=None):
                raise FileNotFoundError(2, "No such file", "/home/x/.plane-mcp.env")
        rc, out, err, calls = self.run_main(["--project", "APP"], "T", ob=NoToken)
        self.assertEqual((rc, out), (1, ""))
        self.assertIn("Plane token missing: run set-token plane", err)
        self.assertNotIn("Traceback", err)

    def test_unknown_project_lists_valid_ones(self):
        rc, out, err, calls = self.run_main(["--project", "ZZZ"], "T", None)
        self.assertEqual(rc, 2)
        self.assertIn("valid: APP, WEB", err)
        self.assertEqual([c[0] for c in calls], ["GET"])   # nothing was created


class OnlyWithPlane(unittest.TestCase):
    def wanted(self, plane):
        r = subprocess.run(["bash", "-c", '. "$NORI_ROOT/scripts/conf.sh" && nori_bin_wanted plane-ticket && echo yes || echo no'],
                           env={**os.environ, "NORI_ROOT": str(REPO), "NORI_CONF": str(self.conf(plane))}, capture_output=True, text=True)
        return r.stdout.strip()

    def conf(self, plane):
        d = Path(tempfile.mkdtemp())
        (d / "nori.conf").write_text(f'PRESET="starter"\nPLANE={plane}\n')
        return d / "nori.conf"

    def test_installed_only_when_plane_is_on(self):
        self.assertEqual(self.wanted("true"), "yes")
        self.assertEqual(self.wanted("false"), "no")

    def test_laptop_script_links_the_skill(self):
        self.assertTrue((REPO / "laptop/skills/plane-ticket/SKILL.md").is_file())
        self.assertFalse((REPO / "skills/plane-ticket").exists())
        r = subprocess.run(["bash", str(REPO / "laptop/setup-laptop.sh"), "--dry-run"], env={"HOME": tempfile.mkdtemp(), "PATH": os.environ["PATH"]},
                           capture_output=True, text=True)
        self.assertIn("link skill plane-ticket", r.stdout)

    def test_server_setup_does_not_link_laptop_skills(self):
        for f in ("setup.sh", "setup-user.sh"):
            self.assertNotIn("laptop/skills", (REPO / f).read_text(), f)


if __name__ == "__main__":
    unittest.main()
