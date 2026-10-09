"""The resolved nori.conf (PRESET applied) as a dict, plus what ./nori up derives from it."""
import os
import re
import subprocess
import tempfile
from pathlib import Path


def parse(text):
    out = {}
    for line in text.splitlines():
        m = re.match(r'^([A-Z][A-Z0-9_]*)=(.*)$', line.strip())
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"')
    return out


# identity values that live in nori.conf itself (with conf.sh defaults), not in the resolved preset flags
CONF_VARS = ("OWNER_NAME", "SERVER_NAME", "ADMIN_USER", "AREAS", "CHAT")


def load(repo):
    """Render nori.conf the same way setup.sh does, so presets and validation are never duplicated.
    The resolved file holds only the preset flags; names like ADMIN_USER/AREAS come from conf.sh."""
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run(["bash", str(Path(repo) / "setup.sh"), "--render-only", d],
                           capture_output=True, text=True, cwd=repo)
        if r.returncode != 0:
            raise SystemExit("nori.conf problems:\n" + (r.stderr or r.stdout).strip())
        flags = parse((Path(d) / "nori.resolved.conf").read_text())
    show = "; ".join(f'printf "%s=%s\\n" {v} "${{{v}}}"' for v in CONF_VARS)
    r = subprocess.run(["bash", "-c", f'. "$NORI_ROOT/scripts/conf.sh" >/dev/null && {show}'],
                       capture_output=True, text=True, cwd=repo, env={**os.environ, "NORI_ROOT": str(Path(repo).resolve())})
    if r.returncode != 0:
        raise SystemExit("nori.conf problems:\n" + (r.stderr or r.stdout).strip())
    return {**parse(r.stdout), **flags}


def server_size(conf):
    return "large" if conf.get("PRESET") == "full" or conf.get("PLANE") == "true" else "small"


def needed_keys(conf, hetzner, tailscale=False):
    """Telegram first: the Tailscale key is only asked for with `./nori up --add tailscale`."""
    names = (["hetzner"] if hetzner else []) + (["tailscale"] if tailscale else []) + ["claude"]
    names += [f"bot:{a}" for a in conf.get("AREAS", "").split()]
    if conf.get("OPS_BOT") == "true":
        names.append("bot:ops")
    return names + ["admin_password"]
