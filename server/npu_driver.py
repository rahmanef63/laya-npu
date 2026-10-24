"""NPU driver detection and guided update.

Detect only: read the installed driver version from PnP, compare against the latest
published on Intel's download page, and tell the user what to do.

Why this module does not install the driver itself:
  - It requires administrator rights and a reboot, which an app that runs as the user
    cannot do.
  - The download is an OEM-sensitive package: on a laptop from ASUS or Lenovo the
    vendor build is what gets tested, and forcing Intel's generic build can break
    display or power management.
  - Running an .exe fetched from the network as a side effect of `install.cmd` is the
    kind of thing that should be an explicit choice, not an automatic one.

So `install.ps1` reports the version, links to the exact download, and offers a
`-InstallDriver` switch that the user has to type deliberately.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request

INTEL_PAGE = ("https://www.intel.com/content/www/us/en/download/794734/"
              "intel-npu-driver-windows.html")

# Versions known to crash OpenVINO 2026.2+ on Panther Lake (from the OpenVINO
# release notes). Reported as a warning, never auto-"fixed".
KNOWN_BAD = {"32.0.100.4300", "32.0.100.4509", "32.0.100.4512"}
MIN_RECOMMENDED = "32.0.100.5540"


def _date(raw) -> str:
    """PowerShell JSON turns dates into /Date(ms)/. Render it as YYYY-MM-DD."""
    import datetime
    m = re.search(r"/Date\((\d+)\)/", str(raw or ""))
    if not m:
        return str(raw or "")
    return datetime.datetime.fromtimestamp(int(m.group(1)) / 1000,
                                                  datetime.timezone.utc).strftime("%Y-%m-%d")


def _vtuple(value: str) -> tuple:
    parts = re.findall(r"\d+", value or "")
    return tuple(int(p) for p in parts[:4]) or (0,)


def installed() -> dict:
    """Read the NPU driver straight from Windows PnP. Empty dict off-Windows."""
    if os.name != "nt":
        return {"present": False, "reason": "not Windows; the NPU is Windows-only"}

    ps = (
        "$d = Get-PnpDevice -Class ComputeAccelerator -ErrorAction SilentlyContinue;"
        "if (-not $d) { '{}' } else {"
        "  $d | ForEach-Object {"
        "    $p = $_ | Get-PnpDeviceProperty -KeyName "
        "DEVPKEY_Device_DriverVersion,DEVPKEY_Device_DriverDate,"
        "DEVPKEY_Device_DriverProvider,DEVPKEY_Device_DeviceDesc -ErrorAction SilentlyContinue;"
        "    [pscustomobject]@{"
        "      status = $_.Status; name = $_.FriendlyName;"
        "      version = ($p | Where-Object KeyName -like '*DriverVersion*').Data;"
        "      date = ($p | Where-Object KeyName -like '*DriverDate*').Data;"
        "      provider = ($p | Where-Object KeyName -like '*DriverProvider*').Data"
        "    } } | ConvertTo-Json -Compress }"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=45,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout.strip()
    except Exception as e:
        return {"present": False, "reason": f"query failed: {e}"}

    if not out or out == "{}":
        return {"present": False, "reason": "no ComputeAccelerator device found"}

    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {"present": False, "reason": "could not parse PnP output"}

    rows = data if isinstance(data, list) else [data]
    npu = next((r for r in rows if "NPU" in str(r.get("name", "")).upper()), None)
    if npu is None:
        return {"present": False, "reason": "no Intel NPU device"}

    return {
        "present": True,
        "status": npu.get("status"),
        "name": npu.get("name"),
        "version": (npu.get("version") or "").strip(),
        "date": _date(npu.get("date")),
        "provider": (npu.get("provider") or "").strip(),
    }


def latest(timeout: int = 20, attempts: int = 3) -> dict:
    """Scrape the newest version Intel publishes.

    Intel's edge returns 403 for browser-like agents and 200 for a plain tool agent,
    so the honest header here is a tool one. Retried because the block is
    intermittent; on failure the caller gets `ok: False` and says so rather than
    guessing a version.
    """
    last = "no attempt"
    for i in range(attempts):
        try:
            req = urllib.request.Request(
                INTEL_PAGE, headers={"User-Agent": "curl/8.5.0",
                                     "Accept": "text/html"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                html = r.read().decode("utf-8", "replace")
            versions = re.findall(r"32\.0\.100\.\d{4}", html)
            if versions:
                return {"ok": True, "version": max(set(versions), key=_vtuple),
                        "url": INTEL_PAGE}
            last = "version not found on the page"
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
        except Exception as e:
            last = str(e)[:120]
        if i + 1 < attempts:
            time.sleep(2 + i * 3)
    return {"ok": False, "reason": last, "url": INTEL_PAGE}


def check() -> dict:
    """Everything the installer and the UI need, in one object."""
    have = installed()
    if not have.get("present"):
        return {
            "present": False,
            "reason": have.get("reason"),
            "action": "none",
            "message": "No Intel NPU detected. The app will run on GPU or CPU.",
        }

    current = have.get("version", "")
    rel = latest()

    if not rel.get("ok"):
        good = current in KNOWN_BAD
        return {
            "present": True, "current": current, "date": have.get("date"),
            "provider": have.get("provider"), "status": have.get("status"),
            "latest": None, "latest_unknown": True,
            "upgrade": False, "known_bad": good,
            "url": INTEL_PAGE,
            "action": "update" if good else "none",
            "message": (
                f"Driver {current} is known to crash OpenVINO on Panther Lake. "
                f"Update from {INTEL_PAGE}."
                if good else
                f"Driver {current} installed. Could not reach Intel to compare "
                f"({rel.get('reason')})."
            ),
        }

    newer = _vtuple(rel["version"]) > _vtuple(current)
    bad = current in KNOWN_BAD
    outdated = _vtuple(current) < _vtuple(MIN_RECOMMENDED)

    if newer or bad:
        action, verdict = "update", "outdated"
    elif outdated:
        action, verdict = "recommended", "older than recommended"
    else:
        action, verdict = "none", "up to date"

    return {
        "present": True,
        "current": current,
        "date": have.get("date"),
        "provider": have.get("provider"),
        "status": have.get("status"),
        "latest": rel["version"],
        "upgrade": newer,
        "known_bad": bad,
        "verdict": verdict,
        "url": rel["url"],
        "action": action,
        "message": (
            f"Driver {current} -> {rel['version']} available. Download: {rel['url']}"
            if newer or bad else
            f"Driver {current} is current (latest {rel['version']})."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
