#!/usr/bin/env bash
# One-click install for laya-npu.
#
#   Linux        -> CPU and BYOK backends only
#   WSL          -> hands off to the Windows installer, because the NPU lives on the
#                   Windows host and is not reachable from inside the VM
#   Git Bash     -> same handoff
#
# Windows users should run install.ps1 or install.cmd directly instead; this script
# exists so a clone works from any shell without reading the README first.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

say()  { echo "  $1"; }
step() { echo; echo "== $1"; }
ok()   { echo "  ok  $1"; }
warn() { echo "  !!  $1"; }

is_wsl() {
  grep -qiE "microsoft|wsl" /proc/version 2>/dev/null && return 0
  [ -n "${WSL_DISTRO_NAME:-}" ] && return 0
  return 1
}

# Windows PowerShell from inside WSL or Git Bash.
find_powershell() {
  for c in powershell.exe pwsh.exe /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe; do
    if command -v "$c" >/dev/null 2>&1; then echo "$c"; return 0; fi
  done
  return 1
}

# Translate /mnt/c/Users/... to C:\Users\... for the Windows side.
win_path() {
  local p="$1"
  if command -v wslpath >/dev/null 2>&1; then
    wslpath -w "$p" 2>/dev/null && return 0
  fi
  case "$p" in
    /mnt/[a-z]/*)
      local drive="${p:5:1}"
      printf '%s:\\%s\n' "${drive^^}" "${p:7}" | tr '/' '\\'
      ;;
    *) printf '%s\n' "$p" ;;
  esac
}

if is_wsl; then
  echo
  echo "laya-npu: WSL detected"
  echo
  say "The Intel NPU is not reachable from WSL. OpenVINO inside the VM only sees CPU."
  say "Windows' own GPU/NPU are the host's; a VM cannot pass them through."
  echo
  say "Handing off to the Windows installer, which is where the NPU path lives."
  echo

  PS="$(find_powershell || true)"
  if [ -z "$PS" ]; then
    warn "powershell.exe not found on PATH."
    say "Run this from Windows instead:"
    say "  install.cmd     (double-click, or in PowerShell)"
    exit 1
  fi

  WROOT="$(win_path "$ROOT")"
  say "repo on the Windows side: $WROOT"
  echo

  # -NoExit keeps the window readable if the installer fails; -File needs a Windows path.
  exec "$PS" -NoProfile -ExecutionPolicy Bypass \
    -Command "Set-Location -LiteralPath '${WROOT//\'/\'\'}'; & '.\install.ps1' $*"
fi

# ------------------------------------------------------------------ native Linux
echo
echo "laya-npu installer"
echo "typed decisions on a decision model"
echo

step "Python"

PY=""
for c in python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    v=$("$c" -c 'import sys;print("%d.%d"%sys.version_info[:2])')
    if [ "$(printf '%s\n3.10\n' "$v" | sort -V | head -1)" = "3.10" ]; then PY="$c"; break; fi
  fi
done
if [ -z "$PY" ]; then
  echo "Python >= 3.10 required." >&2
  echo "  Debian/Ubuntu: sudo apt install python3 python3-venv python3-pip" >&2
  exit 1
fi
ok "$PY ($($PY --version 2>&1))"

step "Environment"

VENV="$ROOT/.venv"
if [ ! -d "$VENV" ]; then
  "$PY" -m venv "$VENV"
  ok "created .venv"
else
  ok ".venv exists"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install --quiet --upgrade pip

step "Packages"

if python -c "import laya, openvino" 2>/dev/null; then
  ok "already installed"
else
  say "installing openvino + laya-openvino (a few minutes)"
  pip install --quiet \
    "openvino>=2026.0" openvino-tokenizers openvino-genai \
    huggingface_hub transformers numpy torch pypdf \
    --extra-index-url https://download.pytorch.org/whl/cpu
  pip install --quiet "git+https://github.com/rupeshs/laya-openvino.git"
  ok "installed"
fi

step "Model"

MODEL="${LAYA_MODEL:-$HOME/models/laya-ov-int8}"
if [ -f "$MODEL/openvino_model.xml" ]; then
  ok "model present ($MODEL)"
else
  say "downloading rupeshr/laya-ov-int8 (405 MB)"
  python - "$MODEL" <<'PY'
import sys
from huggingface_hub import snapshot_download
snapshot_download("rupeshs/laya-ov-int8", local_dir=sys.argv[1])
print("done")
PY
  ok "downloaded"
fi

step "Static IR"

if [ -f "$MODEL/openvino_model_static.xml" ]; then
  ok "already static"
else
  python - "$MODEL" <<'PY'
import os, sys
import openvino as ov
d = sys.argv[1]
core = ov.Core()
m = core.read_model(os.path.join(d, "openvino_model.xml"))
shapes = {i.get_any_name(): ([1, 8] if i.get_any_name().startswith("marker") else [1, 256])
          for i in m.inputs}
shapes["qtype"] = [1]
m.reshape({i.get_any_name(): shapes[i.get_any_name()] for i in m.inputs})
ov.save_model(m, os.path.join(d, "openvino_model_static.xml"))
print("static ok")
PY
  ok "built"
fi

step "Backends"
python - "$MODEL" <<'PY'
import os, sys
import openvino as ov
core = ov.Core()
devs = core.available_devices
print("  devices visible:", devs)
if "NPU" in devs:
    print("  NPU present")
else:
    print("  no NPU - this is expected on Linux and in WSL")
    print("  run install.cmd on Windows for the NPU path")
m = core.read_model(os.path.join(sys.argv[1], "openvino_model_static.xml"))
dev = "GPU" if "GPU" in devs else "CPU"
core.compile_model(m, dev)
print(f"  compiled on {dev}")
PY

step "Web UI"

if [ -f "$ROOT/web/dist/index.html" ]; then
  ok "already built"
else
  if command -v npm >/dev/null 2>&1; then
    ( cd "$ROOT" && npm install --silent && npm run build --silent )
    ok "built"
  else
    warn "npm not found - skipping UI build"
    warn "install Node.js 20+ then: npm install && npm run build"
  fi
fi

step "Config"

if [ ! -f "$ROOT/.env" ]; then
  cat > "$ROOT/.env" <<EOF
LAYA_MODEL=$MODEL
LAYA_DEVICE=NPU
LAYA_MAXLEN=256
LAYA_MARKERS=8
WEB_PORT=8649
LAYA_PORTAL=https://laya.manef.dev
EOF
  ok "wrote .env"
else
  ok ".env exists"
fi

cat <<'EOS'

Done.
Start it with:  ./start.sh
Then open:      http://localhost:8649
No NPU here, so Compute will show GPU or CPU.
EOS
