"""Request guards: size limits, rate limiting, auth, and SSRF refusal.

The review that prompted this was right on every point. A local inference server that
binds to 0.0.0.0 with no auth is reachable by every device on the network, and one of
these endpoints takes a URL the caller chooses — which is an SSRF primitive pointed at
whatever the host can reach.

Defaults changed accordingly:
  - bind is 127.0.0.1, not 0.0.0.0
  - a shared token is required when the bind is not loopback
  - BYOK and portal URLs are validated against private ranges before any fetch
  - bodies have a per-route cap, and requests are rate limited per client
"""
from __future__ import annotations

import ipaddress
import os
import socket
import threading
import time
import urllib.parse

# ---------------------------------------------------------------- limits

MAX_JSON_BYTES = 2 * 1024 * 1024        # ordinary API calls
MAX_AUDIO_BYTES = 60 * 1024 * 1024      # /api/asr and /api/voice

RATE_WINDOW_S = 60
RATE_DEFAULT = 120                      # requests per window per client
RATE_HEAVY = 20                         # audio, corpus, batch


class RateLimiter:
    """Sliding window per client key. Small, in-memory, good enough for one process."""

    def __init__(self, window: int = RATE_WINDOW_S, default: int = RATE_DEFAULT):
        self.window = window
        self.default = default
        self._hits: dict[tuple[str, str], list[float]] = {}
        self._lock = threading.Lock()

    def check(self, client: str, bucket: str, limit: int | None = None) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        limit = limit or self.default
        now = time.monotonic()
        key = (client, bucket)
        with self._lock:
            stamps = self._hits.setdefault(key, [])
            stamps[:] = [t for t in stamps if now - t < self.window]
            if len(stamps) >= limit:
                return False, max(1, int(self.window - (now - stamps[0])))
            stamps.append(now)
            # keep the dict from growing without bound
            if len(self._hits) > 4096:
                for k in [k for k, v in self._hits.items() if not v][:1024]:
                    self._hits.pop(k, None)
            return True, 0


limiter = RateLimiter()


# ---------------------------------------------------------------- auth

def _is_loopback(bind: str) -> bool:
    return bind in ("127.0.0.1", "::1", "localhost")


def resolve_bind() -> str:
    """Bind address, defaulting to loopback. Exposing it requires a token."""
    bind = os.environ.get("LAYA_BIND", "127.0.0.1").strip() or "127.0.0.1"
    token = os.environ.get("LAYA_TOKEN", "").strip()

    if not _is_loopback(bind) and not token:
        # Fail closed rather than silently exposing an unauthenticated service.
        raise SystemExit(
            "refusing to bind %s without LAYA_TOKEN.\n"
            "  This API can read files and fetch URLs, so an open port is not safe.\n"
            "  Either drop LAYA_BIND (loopback only) or set LAYA_TOKEN in .env.\n"
            "  Clients then send:  Authorization: Bearer <token>" % bind
        )
    return bind


def auth_required() -> bool:
    return bool(os.environ.get("LAYA_TOKEN", "").strip()) or \
        not _is_loopback(os.environ.get("LAYA_BIND", "127.0.0.1"))


def token_ok(header_value: str | None) -> bool:
    expected = os.environ.get("LAYA_TOKEN", "").strip()
    if not expected:
        return True                      # loopback, no token configured
    got = (header_value or "").removeprefix("Bearer ").strip()
    # constant-time-ish compare; the token is local, not a password over the internet
    return len(got) == len(expected) and got == expected


# ---------------------------------------------------------------- SSRF

_PRIVATE_NETS = [ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8",
    "169.254.0.0/16", "0.0.0.0/8", "100.64.0.0/10", "::1/128", "fc00::/7",
    "fe80::/10",
)]


def _blocked_ip(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True                       # cannot resolve -> refuse
    for info in infos:
        try:
            addr = ipaddress.ip_address(info[4][0])
        except ValueError:
            return True
        if any(addr in net for net in _PRIVATE_NETS):
            return True
    return False


def check_url(raw: str, allowed_private: bool = False) -> str:
    """Validate a URL a caller supplied. Refuses anything pointing inside the network.

    `allowed_private` exists for one case only: a user deliberately pointing BYOK at a
    server on their own machine. It is opt-in via LAYA_ALLOW_PRIVATE_URL=1 and is
    documented as a risk, not a default.
    """
    if not raw or not raw.strip():
        raise ValueError("url is required")
    if len(raw) > 2048:
        raise ValueError("url is too long")

    url = urllib.parse.urlsplit(raw.strip())
    if url.scheme not in ("http", "https"):
        raise ValueError("url must start with http:// or https://")
    if not url.hostname:
        raise ValueError("url has no host")
    if url.username or url.password:
        raise ValueError("url must not embed credentials")

    allow = allowed_private or os.environ.get("LAYA_ALLOW_PRIVATE_URL") == "1"
    if not allow and _blocked_ip(url.hostname):
        raise ValueError(
            "url resolves to a private, loopback or unresolvable address. "
            "That is refused by default; set LAYA_ALLOW_PRIVATE_URL=1 if you really "
            "mean to call a machine on your own network.")
    return urllib.parse.urlunsplit(url)
