"""Just enough of the Hetzner Cloud API for ./nori up (stdlib urllib). The token lives only in this object."""
import hashlib
import json
import time
import urllib.error
import urllib.request

API = "https://api.hetzner.cloud/v1"
TYPES = {"small": ["cax11", "cx23"], "large": ["cax21", "cx33"]}
LOCATIONS = ["fsn1", "nbg1", "hel1"]


def _available(server_type):
    """Location names where this server type can be ordered now. Since 2026-10-01 this lives on
    server_types[].locations[] (available, deprecation); GET /datacenters returns 410 Gone."""
    return {loc.get("name") for loc in server_type.get("locations") or []
            if loc.get("available") and not loc.get("deprecation")}


class HetznerError(Exception):
    pass


class Hetzner:
    def __init__(self, token, transport=None):
        self._token = token
        self._t = transport or self._http

    def _http(self, method, path, body):
        req = urllib.request.Request(API + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"})
        try:
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return r.status, json.load(r)
            except urllib.error.HTTPError as e:
                try:
                    return e.code, json.load(e)
                except Exception:
                    return e.code, {}
        except (urllib.error.URLError, OSError, ValueError) as e:
            reason = getattr(e, "reason", None) or e.__class__.__name__
            raise HetznerError(f"Hetzner: couldn't reach the API ({str(reason)[:80]}). "
                               "Check your internet, then re-run.") from None

    def _call(self, method, path, body=None, ok=(200, 201)):
        status, data = self._t(method, path, body)
        if status not in ok:
            msg = (data.get("error") or {}).get("message") or f"HTTP {status}"
            if status == 403 and method != "GET":
                msg += (". Your Hetzner token is probably read-only: in the console (Security → API tokens) "
                        "make a new one with Read & Write, then run ./nori up again")
            err = HetznerError(f"Hetzner: {msg}")
            err.status = status
            raise err
        return data

    def check(self):
        self._call("GET", "/locations")

    def _ipv4(self, location):
        """Monthly gross price of a primary IPv4 in this location, or None if Hetzner doesn't say."""
        try:
            for ip in self._call("GET", "/pricing")["pricing"]["primary_ips"]:
                if ip.get("type") == "ipv4":
                    p = next((x for x in ip["prices"] if x["location"] == location), None)
                    return f"{float(p['price_monthly']['gross']):.2f}" if p else None
        except (HetznerError, KeyError, TypeError, ValueError):
            pass
        return None

    def _priced(self, name, loc, price):
        out = {"type": name, "location": loc, "price": f"{float(price):.2f}"}
        ipv4 = self._ipv4(loc)
        if ipv4:
            out["ipv4"] = ipv4
        return out

    def pick(self, size):
        types = {t["name"]: t for t in self._call("GET", "/server_types")["server_types"]}
        for name in TYPES[size]:
            st = types.get(name)
            for loc in LOCATIONS:
                if st and loc in _available(st):
                    price = next(p["price_monthly"]["gross"] for p in st["prices"] if p["location"] == loc)
                    return self._priced(name, loc, price)
        raise HetznerError(f"Hetzner: {' and '.join(TYPES[size])} are sold out in {', '.join(LOCATIONS)}. "
                           "Try again later, or pass --type / --location.")

    def price_for(self, type_, location=None):
        """Live gross price of exactly this type in this location (first available location if none given)."""
        types = {t["name"]: t for t in self._call("GET", "/server_types")["server_types"]}
        st = types.get(type_)
        for loc in ([location] if location else LOCATIONS):
            if st and loc in _available(st):
                price = next((p["price_monthly"]["gross"] for p in st["prices"] if p["location"] == loc), None)
                if price is not None:
                    return self._priced(type_, loc, price)
        where = location or "any of " + ", ".join(LOCATIONS)
        raise HetznerError(f"Hetzner: {str(type_).upper()} isn't available in {where} right now.")

    def ssh_key_id(self, name, pubkey):
        ident = " ".join(pubkey.split()[:2])
        for k in self._call("GET", "/ssh_keys?per_page=50")["ssh_keys"]:
            if " ".join(k.get("public_key", "").split()[:2]) == ident:
                return k["id"]
        unique = f"{name}-{hashlib.sha256(ident.encode()).hexdigest()[:8]}"
        return self._call("POST", "/ssh_keys", {"name": unique, "public_key": pubkey})["ssh_key"]["id"]

    def create(self, name, type_, location, key_id):
        srv = self._call("POST", "/servers", {"name": name, "server_type": type_, "image": "ubuntu-24.04",
                                              "location": location, "ssh_keys": [key_id],
                                              "public_net": {"enable_ipv4": True, "enable_ipv6": True}})["server"]
        return {"id": srv["id"], "ip": srv["public_net"]["ipv4"]["ip"]}

    def server(self, sid):
        status, data = self._t("GET", f"/servers/{sid}", None)
        if status == 404:
            return None
        if status != 200:
            raise HetznerError(f"Hetzner: {(data.get('error') or {}).get('message', status)}")
        return data["server"]

    def wait_running(self, sid, timeout=300, sleep=time.sleep):
        for _ in range(max(1, timeout // 5)):
            srv = self.server(sid)
            if srv and srv["status"] == "running":
                return
            sleep(5)
        raise HetznerError("Hetzner: the server didn't reach 'running' in 5 minutes. Check the console, then re-run.")
