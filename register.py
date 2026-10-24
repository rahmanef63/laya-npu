#!/usr/bin/env python3
"""Register this machine and print what to paste in the portal.

  python register.py                       # reads LAYA_PORTAL or manef.dev
  python register.py --portal http://host:8650

Reads the running app on localhost:8649 for its device ID, falls back to computing the
ID directly so it works before the app is started.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "server"))


def local_device(port: int) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/device", timeout=8) as r:
            return json.loads(r.read())
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--portal", default=os.environ.get("LAYA_PORTAL", "https://manef.dev"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("WEB_PORT", "8649")))
    a = ap.parse_args()

    info = local_device(a.port)
    if info is None:
        import device as D
        info = D.identity()

    print(f"device id: {info['id']}")
    print(f"portal:    {a.portal}")
    print()
    print("Open the portal, paste that ID under Install → Link your device.")
    print("Or keep it linked automatically by setting LAYA_PORTAL before start:")
    print(f"  set LAYA_PORTAL={a.portal}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
