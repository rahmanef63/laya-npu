"""Portal: the public page at manef.dev that recognises devices running an NPU.

An NPU lives on the visitor's machine, so this server cannot compute for them. What it
can do is hold the registry: which device IDs exist, what they can run, and when they
last reported. The local apps POST to /api/device/register on a timer.

Nothing sensitive is stored: the ID is a hash prefix of a machine identifier, and the
only other fields are OS, architecture, version and which OpenVINO devices compiled.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(HERE, "public")
DB = os.environ.get("PORTAL_DB", os.path.join(ROOT, "portal.sqlite"))
PORT = int(os.environ.get("PORTAL_PORT", "8650"))
BIND = os.environ.get("PORTAL_BIND", "0.0.0.0")
# Registration is unauthenticated by design (any install may announce itself), but it is
# rate limited and the ID space is large enough that guessing one is not useful:
# NPU-XXXX-XXXX over a 32-character alphabet is ~10^12 combinations.
ADMIN = os.environ.get("PORTAL_ADMIN_KEY", "")
RATE_WINDOW = 60
RATE_LIMIT = 30
_hits: dict[str, list[float]] = {}

def rate_ok(client: str) -> bool:
    now = time.monotonic()
    stamps = _hits.setdefault(client, [])
    stamps[:] = [t for t in stamps if now - t < RATE_WINDOW]
    if len(stamps) >= RATE_LIMIT:
        return False
    stamps.append(now)
    if len(_hits) > 2048:
        for k in [k for k, v in _hits.items() if not v][:512]:
            _hits.pop(k, None)
    return True
ID_RE = re.compile(r"^NPU-[A-Z0-9]{4}-[A-Z0-9]{4}$")
STALE_SECONDS = 900          # 15 min without a heartbeat marks a device idle

_lock = threading.Lock()


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                version TEXT,
                os TEXT,
                machine TEXT,
                capabilities TEXT,
                first_seen INTEGER,
                last_seen INTEGER,
                reports INTEGER DEFAULT 1,
                note TEXT
            )""")
        conn.commit()


def register(payload: dict) -> dict:
    dev_id = str(payload.get("id") or "").strip()
    if not ID_RE.match(dev_id):
        raise ValueError("invalid device id; expected NPU-XXXX-XXXX")

    caps = payload.get("capabilities") or {}
    now = int(time.time())
    with _lock, db() as conn:
        row = conn.execute("SELECT id, reports FROM devices WHERE id = ?",
                           (dev_id,)).fetchone()
        if row:
            conn.execute("""
                UPDATE devices SET version=?, os=?, machine=?, capabilities=?,
                                   last_seen=?, reports=reports+1
                WHERE id=?""",
                         (str(payload.get("version") or "")[:32],
                          str(payload.get("os") or "")[:32],
                          str(payload.get("machine") or "")[:32],
                          json.dumps(caps)[:2000], now, dev_id))
            status = "updated"
        else:
            conn.execute("""
                INSERT INTO devices (id, version, os, machine, capabilities,
                                     first_seen, last_seen, reports)
                VALUES (?,?,?,?,?,?,?,1)""",
                         (dev_id, str(payload.get("version") or "")[:32],
                          str(payload.get("os") or "")[:32],
                          str(payload.get("machine") or "")[:32],
                          json.dumps(caps)[:2000], now, now))
            status = "registered"
        conn.commit()
    return {"ok": True, "status": status, "id": dev_id}


def list_devices(limit: int = 100) -> dict:
    now = int(time.time())
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM devices ORDER BY last_seen DESC LIMIT ?", (limit,)).fetchall()

    out = []
    for r in rows:
        caps = {}
        try:
            caps = json.loads(r["capabilities"] or "{}")
        except json.JSONDecodeError:
            pass
        age = now - (r["last_seen"] or now)
        devices = caps.get("devices") or []
        out.append({
            "id": r["id"],
            "version": r["version"],
            "os": r["os"],
            "machine": r["machine"],
            "devices": [d.get("device") for d in devices if d.get("ready")],
            "byok": bool(caps.get("byok")),
            "online": age < STALE_SECONDS,
            "age_s": age,
            "reports": r["reports"],
            "first_seen": r["first_seen"],
            "last_seen": r["last_seen"],
        })

    total = len(out)
    online = sum(1 for d in out if d["online"])
    return {"devices": out, "total": total, "online": online,
            "stale_after_s": STALE_SECONDS}


def summary() -> dict:
    data = list_devices(1000)
    by_device: dict[str, int] = {}
    for d in data["devices"]:
        for dev in d["devices"]:
            by_device[dev] = by_device.get(dev, 0) + 1
    return {
        "total": data["total"],
        "online": data["online"],
        "by_device": by_device,
        "os": _count(data["devices"], "os"),
        "byok": sum(1 for d in data["devices"] if d["byok"]),
    }


def _count(rows, key) -> dict:
    out: dict[str, int] = {}
    for r in rows:
        out[r[key] or "unknown"] = out.get(r[key] or "unknown", 0) + 1
    return out


def body_days(handler) -> int:
    """Read the JSON body for the prune route. Kept tiny on purpose."""
    try:
        n = int(handler.headers.get("Content-Length", 0))
        raw = handler.rfile.read(n) if n else b"{}"
        return max(1, int(json.loads(raw).get("days", 30)))
    except Exception:
        return 30


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # The local apps call this from another origin.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                body = f.read()
        except OSError:
            return self._json({"error": "not found"}, 404)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        p = self.path.split("?")[0]

        if p == "/api/devices":
            # Device rows identify a specific machine and reveal when it is used, so
            # they are admin-only. The public page shows aggregates instead.
            if not ADMIN or (self.headers.get("X-Admin-Key") or "") != ADMIN:
                return self._json({"error": "unauthorised"}, 401)
            return self._json(list_devices())
        if p == "/api/summary":
            return self._json(summary())
        if p == "/api/health":
            return self._json({"ok": True, "devices": summary()["total"]})
        if p in ("/", "/index.html"):
            return self._file(os.path.join(DIST, "index.html"), "text/html; charset=utf-8")
        if p == "/app.js":
            return self._file(os.path.join(DIST, "app.js"), "text/javascript")
        if p == "/style.css":
            return self._file(os.path.join(DIST, "style.css"), "text/css")

        # Static assets the share cards need: crawlers fetch these unauthenticated.
        ASSETS = {
            "/og.png": ("og.png", "image/png"),
            "/og.svg": ("og.svg", "image/svg+xml"),
            "/favicon.svg": ("favicon.svg", "image/svg+xml"),
            "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png"),
            "/icon-192.png": ("icon-192.png", "image/png"),
            "/icon-512.png": ("icon-512.png", "image/png"),
            "/manifest.json": ("manifest.json", "application/manifest+json"),
            "/sitemap.xml": ("sitemap.xml", "application/xml"),
            "/robots.txt": ("robots.txt", "text/plain"),
        }
        if p in ASSETS:
            name, ctype = ASSETS[p]
            return self._file(os.path.join(DIST, name), ctype)
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        p = self.path.split("?")[0]
        n = int(self.headers.get("Content-Length", 0))

        if n > 64 * 1024:
            return self._json({"error": "body too large"}, 413)
        client = self.client_address[0] if self.client_address else "unknown"
        if not rate_ok(client):
            return self._json({"error": "too many requests"}, 429)

        # Admin-only route, gated by a key that actually has a use now.
        if p == "/api/devices/prune":
            if not ADMIN or (self.headers.get("X-Admin-Key") or "") != ADMIN:
                return self._json({"error": "unauthorised"}, 401)
            days = int(body_days(self))
            with db() as conn:
                cutoff = int(time.time()) - days * 86400
                cur = conn.execute("DELETE FROM devices WHERE last_seen < ?", (cutoff,))
                conn.commit()
                return self._json({"deleted": cur.rowcount, "older_than_days": days})

        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "invalid json"}, 400)

        if p == "/api/device/register":
            try:
                return self._json(register(body))
            except ValueError as e:
                return self._json({"error": str(e)}, 400)

        if p == "/api/device/check":
            # Confirms a device is known without turning itself into an oracle that
            # leaks OS, versions, report counts or current activity to anyone who
            # guesses an ID. Coarse online/recent distinction only.
            dev_id = str(body.get("id") or "").strip().upper()
            if not ID_RE.match(dev_id):
                return self._json({"found": False, "error": "invalid id"}, 400)
            with db() as conn:
                row = conn.execute(
                    "SELECT id, last_seen FROM devices WHERE id = ?", (dev_id,)).fetchone()
            if not row:
                return self._json({"found": False})
            age = int(time.time()) - (row["last_seen"] or 0)
            if age < STALE_SECONDS:
                state = "active today"
            elif age < 7 * 86400:
                state = "seen this week"
            else:
                state = "seen longer ago"
            return self._json({"found": True, "id": row["id"], "state": state})

        self._json({"error": "not found"}, 404)


def main():
    init()
    print(f"portal on http://localhost:{PORT}  db={DB}", flush=True)
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
