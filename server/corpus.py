"""Local corpus: point at a directory, extract text, classify each file.

Supported: .txt .md .json .csv .log .html and .pdf (via pypdf). Anything else is
listed but skipped, never guessed at.

Paths are resolved and checked against an allowlist of roots so a request cannot
walk the filesystem. The UI only ever sends a directory the user typed.
"""
from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path

TEXT_EXT = {".txt", ".md", ".markdown", ".rst", ".log", ".csv", ".tsv",
            ".json", ".yaml", ".yml", ".html", ".htm", ".xml", ".ini", ".conf"}
PDF_EXT = {".pdf"}
MAX_BYTES = 2 * 1024 * 1024        # per file
MAX_FILES = 200                    # per scan
MAX_CHARS = 20000                  # what the model gets

# Roots a scan may touch. Widen with LA_ALLOWED_ROOTS (colon/semicolon separated).
# Resolved at import so Windows and WSL each get a native path, not a translated one.
def _default_roots() -> list[str]:
    home = os.path.expanduser("~")
    roots = [home]
    if os.name == "nt":
        roots.append(os.path.join(os.environ.get("SystemDrive", "C:") + os.sep, "Users"))
    elif os.path.isdir("/mnt/c/Users"):
        roots.append("/mnt/c/Users")
    return roots


_DEFAULT_ROOTS = _default_roots()


def allowed_roots() -> list[Path]:
    raw = os.environ.get("LA_ALLOWED_ROOTS", "")
    extra = [p for p in raw.replace(";", ":").split(":") if p.strip()]
    roots = [Path(os.path.expanduser(r)).resolve() for r in extra] or \
            [Path(os.path.expanduser(r)).resolve() for r in _DEFAULT_ROOTS]
    return roots


def resolve_dir(raw: str) -> Path:
    """Resolve a user-supplied directory and confirm it sits under an allowed root.

    Accepts a Windows path from the UI (C:\\Users\\...) as well as a POSIX one.
    """
    if not raw or not str(raw).strip():
        raise ValueError("directory required")

    candidate = str(raw).strip().strip('"').strip("'")
    p = Path(os.path.expanduser(candidate)).resolve()

    # A Windows path sent from WSL does not exist as written, so try the /mnt form
    # only after the native path fails. Doing the translation first breaks Windows,
    # where C:\Users is already correct.
    if not p.exists() and len(candidate) > 2 and candidate[1] == ":":
        drive = candidate[0].lower()
        rest = candidate[2:].replace("\\", "/")
        p = Path(f"/mnt/{drive}{rest}").resolve()

    if not p.exists():
        raise ValueError(f"not found: {raw}")
    if not p.is_dir():
        raise ValueError(f"not a directory: {p}")

    for root in allowed_roots():
        try:
            p.relative_to(root)
        except ValueError:
            continue
        return p
    raise ValueError("directory is outside the allowed roots "
                     f"({', '.join(str(r) for r in allowed_roots())})")


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    out = []
    for page in reader.pages[:40]:
        out.append(page.extract_text() or "")
        if sum(len(x) for x in out) > MAX_CHARS:
            break
    return "\n".join(out)


def _read_text(path: Path) -> str:
    raw = path.read_bytes()[:MAX_BYTES]
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def read_file(path: Path) -> tuple[str, str]:
    """Return (kind, text). kind is 'text' | 'pdf' | 'unsupported'."""
    ext = path.suffix.lower()
    if ext in PDF_EXT:
        return "pdf", _read_pdf(path)
    if ext in TEXT_EXT or ext == "":
        text = _read_text(path)
        if ext in (".csv", ".tsv"):
            # keep it readable for the model rather than raw commas
            try:
                dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t")
                rows = list(csv.reader(io.StringIO(text), dialect))[:60]
                text = "\n".join(" | ".join(r) for r in rows)
            except Exception:
                pass
        elif ext == ".json":
            try:
                text = json.dumps(json.loads(text), indent=1)[:MAX_CHARS]
            except Exception:
                pass
        return "text", text
    return "unsupported", ""


def scan(raw_dir: str, limit: int = 40) -> dict:
    """List files in a directory with size and kind, without running the model."""
    root = resolve_dir(raw_dir)
    rows = []
    for path in sorted(root.iterdir()):
        if path.name.startswith("."):
            continue
        if path.is_dir():
            rows.append({"name": path.name, "path": str(path), "kind": "dir",
                         "size": None})
            continue
        ext = path.suffix.lower()
        kind = "pdf" if ext in PDF_EXT else ("text" if ext in TEXT_EXT or ext == ""
                                            else "unsupported")
        try:
            size = path.stat().st_size
        except OSError:
            size = None
        rows.append({"name": path.name, "path": str(path), "kind": kind,
                     "size": size})
        if len(rows) >= limit:
            break
    return {"dir": str(root), "files": rows,
            "allowed_roots": [str(r) for r in allowed_roots()]}


def extract(raw_dir: str, limit: int = 20) -> list[dict]:
    """Read every supported file in the directory, ready for classification."""
    root = resolve_dir(raw_dir)
    out = []
    for path in sorted(root.iterdir()):
        if path.name.startswith(".") or not path.is_file():
            continue
        kind, text = read_file(path)
        out.append({"name": path.name, "path": str(path), "kind": kind,
                    "chars": len(text), "text": text[:MAX_CHARS]})
        if len(out) >= min(limit, MAX_FILES):
            break
    return out
