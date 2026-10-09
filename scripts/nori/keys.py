"""The keys checklist, hidden prompts and quick checks. Keys stay in memory; nothing here prints one."""
import getpass
import json
import re
import sys
import warnings
from urllib.request import urlopen

CHECKLIST = {
    "hetzner": ("Hetzner API token. First an account: hetzner.com/cloud → verify identity, add a payment method "
                "(card/PayPal); about €6/month for the recommended server, billed by the hour (delete the server to stop paying). "
                "Then console.hetzner.cloud → new project 'nori' → Security → API tokens → Generate; "
                "the default is Read: change it to Read & Write"),
    "tailscale": "Tailscale auth key (one-off, pre-approved): login.tailscale.com/admin/settings/keys",
    "claude": ("Claude token: open a new terminal tab (Mac ⌘T), run `claude setup-token`, copy what it prints "
              "(starts with sk-ant-oat01-…). Your own Claude account, never shared"),
    "bot": ("Telegram bot token for {name}: open https://t.me/BotFather → /newbot. Also note the bot's username "
            "(e.g. my_nori_bot; not secret): it's the bot you'll chat with"),
    "admin_password": "Admin password: you make this one up yourself (your password manager can generate it), 12+ characters",
}


SAFETY = ("🔒 Don't paste any key into a chat (never here, never to Claude). Keep them in a password manager: "
          "typing is hidden, and the admin password is asked twice.")

# what each key looks like (made-up examples), shown next to the checklist so people paste the right thing
SHAPES = {
    "hetzner": "64 letters and digits, e.g. AbC1dEf2…(64)",
    "tailscale": "tskey-auth-kAb12CdEF11CNTRL-aBcDeF1234…",
    "claude": "sk-ant-oat01-AbCd…(long, one line)",
    "bot": "123456789:AAH4kLm…(about 46 characters)",
    "admin_password": "anything you choose, 12+ characters",
}


def shape(name):
    return SHAPES["bot" if name.startswith("bot:") else name]


def label(name):
    if name.startswith("bot:"):
        who = name[4:]
        return CHECKLIST["bot"].format(name="the Ops bot" if who == "ops" else f"area '{who}'")
    return CHECKLIST[name]


def check(name, value, http=urlopen):
    return check_info(name, value, http)[0]


def check_info(name, value, http=urlopen):
    """(problem, info): problem is None when fine; info is the bot's @username for a valid bot token."""
    if not value:
        return "empty", None
    if name == "tailscale":
        return (None if re.fullmatch(r"tskey-auth-[A-Za-z0-9-]+", value) else "should start with tskey-auth-"), None
    if name == "claude":
        return (None if re.fullmatch(r"sk-ant-oat\d\d-[A-Za-z0-9_-]{20,}", value) else "doesn't look like a `claude setup-token` token"), None
    if name == "admin_password":
        return (None if len(value) >= 12 else "use 12 or more characters"), None
    if name.startswith("bot:"):
        if not re.fullmatch(r"\d+:[A-Za-z0-9_-]{5,}", value):
            return "doesn't look like a BotFather token (digits:letters)", None
        try:
            data = json.load(http(f"https://api.telegram.org/bot{value}/getMe", timeout=15))
        except Exception:
            return "Telegram didn't accept it (check the token, or your internet)", None
        if not data.get("ok"):
            return "Telegram didn't accept it", None
        return None, (data.get("result") or {}).get("username")
    return None, None  # hetzner is checked by its first API call


NO_TTY = ("✗ Typing can't be hidden here, so no keys were asked. Run ./nori up in a separate terminal window "
          "(Mac: ⌘N in Terminal or iTerm), not inside a chat session.")


def hidden_prompt(text):
    """getpass, but its 'can't hide, will echo' fallback becomes an error instead of showing the key."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        return getpass.getpass(text)


def ask_keys(names, prompt=None, out=sys.stdout, http=urlopen, hint=None):
    got, bots = {}, {}
    read = prompt or hidden_prompt

    def ask(text):
        try:
            return read(text)
        except getpass.GetPassWarning:
            raise SystemExit(NO_TTY) from None
    print(SAFETY, file=out)
    print("Keys needed now. No keys or tokens are saved; Nori writes its own SSH key ~/.ssh/nori_ed25519 "
          "(no passphrase), a block in ~/.ssh/config and generated/up-state.json (server id and IP):", file=out)
    for n in names:
        print(f"  • {label(n)}", file=out)
        print(f"      looks like: {shape(n)}", file=out)
    for n in names:
        while True:
            shown = f"{n} ({hint[n]})" if hint and n in hint else n
            v = ask(f"{shown}: ").strip()
            problem, info = check_info(n, v, http)
            if not problem and n == "admin_password" and ask(f"{n} again to confirm: ").strip() != v:
                problem = "the two entries differ"
            if not problem and info:
                other = next((o for o, u in bots.items() if u == info), None)
                if other:
                    problem = f"that's the same bot as {other}; each area and the Ops bot need their own"
            if not problem:
                if info:
                    bots[n] = info
                # enough to see the paste worked, never the secret part (the password: only its length)
                seen = f"{len(v)} characters" if n == "admin_password" else f"{v[:3]}… ({len(v)} characters)"
                print(f"  ✓ {seen}" + (f"  @{info}" if info else ""), file=out)
                got[n] = v
                break
            print(f"  ✗ {n}: {problem}. Try again.", file=out)
    return got
