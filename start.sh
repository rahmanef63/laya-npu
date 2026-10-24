#!/usr/bin/env bash
# Start laya-npu.
#
#   ./start.sh
#
# In WSL this hands off to Windows, same as install.sh: the NPU and its compiled
# graph live on the host, so running the server inside the VM would only ever reach
# CPU.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

is_wsl() {
  grep -qiE "microsoft|wsl" /proc/version 2>/dev/null && return 0
  [ -n "${WSL_DISTRO_NAME:-}" ] && return 0
  return 1
}

win_path() {
  if command -v wslpath >/dev/null 2>&1; then wslpath -w "$1" 2>/dev/null && return 0; fi
  case "$1" in
    /mnt/[a-z]/*) printf '%s:\\%s\n' "${1:5:1}" "${1:7}" | tr '/' '\\' ;;
    *) printf '%s\n' "$1" ;;
  esac
}

if is_wsl; then
  PS=""
  for c in powershell.exe pwsh.exe /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe; do
    command -v "$c" >/dev/null 2>&1 && { PS="$c"; break; }
  done
  if [ -z "$PS" ]; then
    echo "powershell.exe not found. Run laya-npu.cmd on Windows instead." >&2
    exit 1
  fi
  WROOT="$(win_path "$ROOT")"
  echo "WSL detected: starting the Windows-side app so the NPU is used."
  exec "$PS" -NoProfile -ExecutionPolicy Bypass \
    -Command "Set-Location -LiteralPath '${WROOT//\'/\'\'}'; & '.\start.ps1'"
fi

if [ ! -f "$ROOT/.env" ]; then
  echo "Run ./install.sh first." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

if [ ! -d "$ROOT/.venv" ]; then
  echo ".venv missing. Run ./install.sh" >&2
  exit 1
fi
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"

PORT="${WEB_PORT:-8649}"

if command -v ss >/dev/null 2>&1 && ss -ltn "sport = :$PORT" 2>/dev/null | grep -q LISTEN; then
  echo "Port $PORT already in use - is it already running?" >&2
  exit 0
fi

echo "starting laya-npu on http://localhost:$PORT"
echo "the first compile takes 30-90s on NPU, a few seconds on CPU."
echo

cd "$ROOT"
exec python server/web.py
