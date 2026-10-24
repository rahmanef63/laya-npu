"""Device identity and heartbeat.

The idea: a visitor installs the app locally, the app shows a short device ID, and the
visitor pastes that ID into the portal so their NPU is recognised. NPUs live on user
machines, so the portal cannot compute for them — it can only know who is running one.

The ID is derived from the machine, not random, so a reinstall keeps the same identity.
It contains no personal data: a hash prefix of a machine identifier plus a checksum.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import threading
import time
import urllib.error
import urllib.request
import uuid

STATE_DIR = os.path.join(os.path.expanduser("~"), ".laya-npu")
STATE_FILE = os.path.join(STATE_DIR, "device.json")

_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # no 0/O/1/I


def _machine_seed() -> str:
    """A stable per-machine value, without needing admin rights."""
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            ) as key:
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                if guid:
                    return str(guid)
        except Exception:
            pass
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(path) as f:
                value = f.read().strip()
            if value:
                return value
        except OSError:
            continue
    return f"{socket.gethostname()}-{uuid.getnode()}"


def _encode(raw: bytes, length: int) -> str:
    out = []
    for byte in raw[:length]:
        out.append(_ALPHABET[byte % len(_ALPHABET)])
    return "".join(out)


def device_id() -> str:
    """Stable per machine, unless the user rotates it.

    `LAYA_DEVICE_SALT` is mixed in, so deleting ~/.laya-npu/device.json and setting a
    new salt gives the machine a new identity. That is the supported way to unlink:
    the old ID stops reporting and nothing ties the two together.
    """
    salt = os.environ.get("LAYA_DEVICE_SALT", "").strip()
    digest = hashlib.sha256(("laya-npu:" + salt + _machine_seed()).encode()).digest()
    return f"NPU-{_encode(digest[:4], 4)}-{_encode(digest[4:8], 4)}"


def _load() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, STATE_FILE)


def identity(extra: dict | None = None) -> dict:
    """The payload a portal receives. No paths, no usernames, no keys."""
    data = _load()
    base = {
        "id": device_id(),
        "linked_at": data.get("linked_at"),
        "portal": data.get("portal"),
        "host": {
            "os": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "first_seen": data.get("first_seen") or _now(),
        "version": data.get("version", "1.0"),
    }
    if extra:
        base.update(extra)
    if not data:
        data.update({"first_seen": base["first_seen"]})
        _save(data)
    return base


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def link(portal: str, note: str = "") -> dict:
    """Remember which portal this device reports to. Purely local bookkeeping."""
    portal = (portal or "").rstrip("/")
    data = _load()
    data.update({"portal": portal, "linked_at": _now(), "note": note[:120],
                 "first_seen": data.get("first_seen") or _now()})
    _save(data)
    return {"ok": bool(portal), "portal": portal, "linked_at": data["linked_at"]}


def heartbeat_payload(capabilities: dict) -> dict:
    ident = identity()
    return {
        "id": ident["id"],
        "version": ident["version"],
        "os": ident["host"]["os"],
        "machine": ident["host"]["machine"],
        "capabilities": capabilities,
    }


class Heartbeat:
    """Outbound-only: the portal never reaches into a user's machine.

    Sends a small POST every `interval` seconds when a portal is linked. Failures are
    swallowed — a portal outage must not affect local inference.
    """

    def __init__(self, portal: str = "", interval: int = 300):
        self.portal = (portal or "").rstrip("/")
        self.interval = max(60, interval)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last: dict = {"ok": None, "at": None, "detail": "not sent yet"}

    def start(self, capabilities_fn):
        if not self.portal or self._thread:
            return
        self._thread = threading.Thread(
            target=self._loop, args=(capabilities_fn,), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self, capabilities_fn):
        while not self._stop.is_set():
            try:
                self.send(capabilities_fn())
            except Exception as e:
                self.last = {"ok": False, "at": _now(), "detail": str(e)[:160]}
            self._stop.wait(self.interval)

    def send(self, capabilities: dict) -> dict:
        body = json.dumps(heartbeat_payload(capabilities)).encode()
        req = urllib.request.Request(
            self.portal + "/api/device/register", data=body,
            headers={"Content-Type": "application/json",
                     "User-Agent": "laya-npu/" + identity()["version"]})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                payload = json.loads(r.read() or b"{}")
            self.last = {"ok": True, "at": _now(),
                         "detail": payload.get("status", "registered")}
        except urllib.error.HTTPError as e:
            self.last = {"ok": False, "at": _now(), "detail": f"HTTP {e.code}"}
            raise
        except urllib.error.URLError as e:
            self.last = {"ok": False, "at": _now(), "detail": str(e.reason)[:120]}
            raise
        return self.last
