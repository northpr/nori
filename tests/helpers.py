"""Shared helpers for the Nori tests (stdlib only)."""
import os
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "generated", "__pycache__", "node_modules"}


def repo_files():
    """Yield every tracked-looking file under the repo (skips .git, generated, caches)."""
    for dirpath, dirnames, filenames in os.walk(REPO):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            yield Path(dirpath) / name


def shebang(path):
    try:
        with open(path, "rb") as f:
            line = f.readline(200)
    except OSError:
        return ""
    return line.decode("utf-8", "replace").strip() if line.startswith(b"#!") else ""


def shell_scripts():
    out = []
    for p in repo_files():
        sb = shebang(p)
        if sb and re.search(r"\b(ba)?sh\b", sb) or p.suffix == ".sh":
            out.append(p)
    return sorted(set(out))


def python_scripts():
    out = []
    for p in repo_files():
        if p.suffix == ".py" or "python" in shebang(p):
            out.append(p)
    return sorted(out)


def render(conf_text, outdir, tmp):
    """Run `setup.sh --render-only outdir` with a throwaway nori.conf. Returns CompletedProcess."""
    conf = Path(tmp) / "nori.conf"
    conf.write_text(conf_text)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("AREA_", "NORI_"))}
    env["NORI_CONF"] = str(conf)
    env["HOME"] = str(tmp)
    return subprocess.run(["bash", str(REPO / "setup.sh"), "--render-only", str(outdir)],
                          env=env, capture_output=True, text=True, timeout=120)
