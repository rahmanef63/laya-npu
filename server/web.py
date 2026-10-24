"""Web backend for the laya-npu webapp.

Serves the static SvelteKit build and the API. One process.

  python server/web.py      -> http://localhost:8648
"""
from __future__ import annotations

import json
import mimetypes
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import asr as A                 # noqa: E402
import corpus as K              # noqa: E402
import custom as C              # noqa: E402
import device as D              # noqa: E402
import guards as G              # noqa: E402
import npu_driver as DRV        # noqa: E402
import pipeline as P            # noqa: E402
import schema as S              # noqa: E402
import tasks as T               # noqa: E402
from backends import ByokBackend, LocalBackend  # noqa: E402

PORT = int(os.environ.get("WEB_PORT", "8648"))
BIND = "127.0.0.1"   # resolved in main() by guards.resolve_bind()
PORTAL = os.environ.get("LAYA_PORTAL", "")
# A portal on another origin needs CORS; local usage does not, so it is opt-in.
ALLOW_ORIGIN = os.environ.get("LAYA_ALLOW_ORIGIN", "")
DIST = os.path.join(ROOT, "web", "dist")
MODEL_DIR = os.environ.get("LAYA_MODEL", "")

_local: LocalBackend | None = None
_byok: ByokBackend | None = None
_error: str | None = None


def local() -> LocalBackend:
    global _local, _error
    if _local is not None:
        return _local
    if _error:
        raise RuntimeError(_error)
    try:
        _local = LocalBackend(MODEL_DIR)
    except Exception as e:
        _error = f"{type(e).__name__}: {e}"
        raise
    return _local


def byok() -> ByokBackend:
    global _byok
    if _byok is None:
        _byok = ByokBackend()
    return _byok


def backend_for(backend_id: str):
    """Resolve 'local:npu' / 'byok' to a backend plus an optional device."""
    if backend_id.startswith("local:"):
        dev = backend_id.split(":", 1)[1].upper()
        return local(), dev
    if backend_id == "byok":
        b = byok()
        if not b.configured:
            raise RuntimeError("BYOK endpoint not configured")
        return b, None
    # default: whatever the local backend picked
    lb = local()
    return lb, lb.device


def analyse(text: str, task_id: str, backend_id: str = "", **byok_opts):
    spec = T.TASKS[task_id]
    state = {spec["state_key"]: text[:20000]}
    b, dev = backend_for(backend_id or "local")

    raw, answers = {}, {}
    t0 = time.perf_counter()
    for qid, q in spec["questions"].items():
        if isinstance(b, ByokBackend):
            out = b.system_one(state, {qid: q}, **byok_opts)
        else:
            out = b.system_one(state, {qid: q}, device=dev)
        raw[qid] = out["answers"][qid]
        answers[qid] = C._summary(qid, q, out["answers"][qid])
    ms = (time.perf_counter() - t0) * 1000

    action, label, reasons, severity = T.decide(task_id, raw, text)
    top = [v for v in answers.values() if v["type"] == "choice"]
    weakest = min((v["probability"] for v in top), default=1.0)

    return {
        "task": task_id,
        "task_label": spec["label"],
        "answers": list(answers.values()),
        "action": action,
        "action_label": label,
        "reasons": reasons,
        "severity": severity,
        "review": weakest < T.ACT_THRESHOLD,
        "weakest": round(weakest, 3),
        "ms": round(ms, 1),
        "device": dev or "BYOK",
        "backend": backend_id or f"local:{str(dev).lower()}",
        "questions": len(spec["questions"]),
    }


def run_custom(text, questions, backend_id="", state_key="state", **byok_opts):
    b, dev = backend_for(backend_id or "local")
    questions = C.normalise_questions(questions)
    if not questions:
        raise ValueError("at least one question required")

    state = {state_key: str(text)[:20000]}
    answers, raw = {}, {}
    t0 = time.perf_counter()
    for qid, q in questions.items():
        if isinstance(b, ByokBackend):
            out = b.system_one(state, {qid: q}, **byok_opts)
        else:
            out = b.system_one(state, {qid: q}, device=dev)
        raw[qid] = out["answers"][qid]
        answers[qid] = C._summary(qid, q, out["answers"][qid])
    ms = (time.perf_counter() - t0) * 1000

    return {
        "answers": [answers[k] for k in questions],
        "raw": raw,
        "ms": round(ms, 1),
        "per_question_ms": round(ms / max(len(questions), 1), 1),
        "device": dev or "BYOK",
        "backend": backend_id or f"local:{str(dev).lower()}",
        "questions": len(questions),
    }


def run_rpa(payload):
    b, dev = backend_for(payload.get("backend") or "local")

    class _Shim:
        """custom.run_rpa expects an object with system_one(state, questions)."""

        def system_one(self, state, questions):
            if isinstance(b, ByokBackend):
                return b.system_one(state, questions,
                                    url=payload.get("byokUrl"),
                                    key=payload.get("byokKey"),
                                    model=payload.get("byokModel"))
            return b.system_one(state, questions, device=dev)

        device = dev or "BYOK"

    out = C.run_rpa(_Shim(), payload)
    out["backend"] = payload.get("backend") or f"local:{str(dev).lower()}"
    return out


def tasks_payload():
    return {"tasks": [{
        "id": t["id"], "label": t["label"], "blurb": t["blurb"],
        "state_key": t["state_key"], "placeholder": t["placeholder"],
        "questions": [{"id": qid, "type": q["type"], "instructions": q["instructions"]}
                      for qid, q in t["questions"].items()],
    } for t in T.TASKS.values()]}


def device_payload() -> dict:
    """Identity plus what this machine can actually do."""
    caps = {"devices": [], "byok": byok().configured}
    try:
        caps["devices"] = [{"device": b["device"], "ready": b["ready"]}
                           for b in local().available()]
    except Exception as e:
        caps["error"] = str(e)[:160]
    ident = D.identity({"capabilities": caps})
    ident["heartbeat"] = _heartbeat.last
    return ident


_heartbeat = D.Heartbeat(PORTAL)


def backends_payload():
    rows = []
    try:
        rows.extend(local().available())
    except Exception as e:
        rows.append({"id": "local", "device": "LOCAL", "label": "Local",
                     "kind": "local", "present": False, "ready": False,
                     "reason": str(e)[:200]})
    rows.append(byok().describe())
    return {"backends": rows, "default": rows[0]["id"] if rows else None}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _client(self) -> str:
        return self.client_address[0] if self.client_address else "unknown"

    def _deny(self, code: int, msg: str, retry: int = 0):
        self._json({"error": msg}, code, retry=retry)

    def _json(self, obj, code=200, retry=0):
        body = json.dumps(obj, default=float).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if retry:
            self.send_header("Retry-After", str(retry))
        if ALLOW_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", ALLOW_ORIGIN)
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        if ALLOW_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", ALLOW_ORIGIN)
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _index(self):
        """Serve the SPA shell with the access token inlined.

        The token exists to stop other machines on the network reaching the API. The
        browser page is same-origin, so giving it the token does not widen that boundary
        -- and without it the UI could not load at all once a token is set.
        """
        path = os.path.join(DIST, "index.html")
        try:
            with open(path, "rb") as f:
                html = f.read().decode("utf-8")
        except OSError:
            return self._json({"error": "web/dist not built. Run: npm install && npm run build"}, 404)

        token = os.environ.get("LAYA_TOKEN", "").strip()
        if token:
            tag = f'<meta name="laya-token" content="{token}">'
            html = html.replace("<head>", "<head>" + tag, 1)

        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path):
        try:
            with open(path, "rb") as f:
                body = f.read()
        except OSError:
            return self._json({"error": "not found"}, 404)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if path.endswith(".js"):
            ctype = "text/javascript"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path.split("?")[0]

        if p.startswith("/api/") and not G.token_ok(self.headers.get("Authorization")):
            return self._deny(401, "unauthorised")
        if p.startswith("/api/"):
            ok, retry = G.limiter.check(self._client(), "get")
            if not ok:
                return self._deny(429, "too many requests", retry)

        if p == "/api/tasks":
            return self._json(tasks_payload())
        if p == "/api/backends":
            return self._json(backends_payload())
        if p == "/api/schema/starter":
            return self._json({"spec": S.starter()})
        if p == "/api/pipeline":
            return self._json({
                "asr": A.available(),
                "tasks": [{"id": t["id"], "label": t["label"]}
                          for t in T.TASKS.values()],
                "stages": ["whisper (NPU)", "laya (NPU)", "policy (python)"],
            })
        if p == "/api/asr":
            return self._json(A.available())
        if p == "/api/driver":
            try:
                return self._json(DRV.check())
            except Exception as ex:
                return self._json({"error": str(ex)[:200]}, 500)
        if p == "/api/device":
            return self._json(device_payload())
        if p == "/api/corpus/roots":
            return self._json({"roots": [str(r) for r in K.allowed_roots()]})
        if p == "/api/health":
            try:
                lb = local()
                return self._json({"ok": True, "device": lb.device,
                                   "devices": list(lb.available())})
            except Exception as ex:
                return self._json({"ok": False, "error": str(ex)[:300]}, 503)

        if p in ("/", ""):
            p = "/index.html"
            return self._index()
        cand = os.path.normpath(os.path.join(DIST, p.lstrip("/")))
        if not cand.startswith(DIST):
            return self._json({"error": "bad path"}, 400)
        if os.path.isfile(cand):
            return self._file(cand)
        index = os.path.join(DIST, "index.html")
        if os.path.isfile(index):
            return self._file(index)
        self._json({"error": "web/dist not built. Run: cd web && npm run build"}, 404)

    def do_POST(self):
        p = self.path.split("?")[0]
        n = int(self.headers.get("Content-Length", 0))

        if not G.token_ok(self.headers.get("Authorization")):
            return self._deny(401, "unauthorised")

        heavy = p in ("/api/asr", "/api/voice", "/api/corpus/classify",
                      "/api/corpus/list", "/api/batch")
        ok, retry = G.limiter.check(self._client(), p,
                                    G.RATE_HEAVY if heavy else G.RATE_DEFAULT)
        if not ok:
            return self._deny(429, "too many requests", retry)

        cap = G.MAX_AUDIO_BYTES if p in ("/api/asr", "/api/voice") else G.MAX_JSON_BYTES
        if n > cap:
            return self._deny(413, f"body too large; limit is {cap // (1024*1024)} MB")
        if n < 0:
            return self._deny(400, "invalid Content-Length")

        # Audio arrives as raw bytes, not JSON, so it is handled before parsing.
        if p == "/api/voice":
            raw = self.rfile.read(n) if n else b""
            if not raw:
                return self._json({"error": "empty body; send a WAV file"}, 400)
            task = self.headers.get("X-Task") or "triage"
            device = self.headers.get("X-Device") or "NPU"
            if task not in T.TASKS:
                return self._json({"error": f"unknown task {task!r}"}, 400)
            try:
                return self._json(P.run_pipeline(raw, task, device, analyse))
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
            except Exception as e:
                return self._json({"error": str(e)[:300]}, 500)

        if p == "/api/asr":
            raw = self.rfile.read(n) if n else b""
            device = self.headers.get("X-Device") or "NPU"
            if not raw:
                return self._json({"error": "empty body; send a WAV file"}, 400)
            try:
                return self._json(A.transcribe(raw, device))
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
            except Exception as e:
                return self._json({"error": str(e)[:300]}, 500)

        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "invalid json"}, 400)

        backend_id = req.get("backend") or ""
        byok_url = req.get("byokUrl")
        if byok_url:
            # A caller-supplied URL is an SSRF primitive unless it is checked.
            try:
                byok_url = G.check_url(str(byok_url))
            except ValueError as e:
                return self._json({"error": f"byokUrl: {e}"}, 400)
        byok_opts = {"url": byok_url, "key": req.get("byokKey"),
                     "model": req.get("byokModel")}

        try:
            if p == "/api/custom":
                return self._json(run_custom(req.get("state", ""),
                                             req.get("questions"),
                                             backend_id,
                                             req.get("state_key", "state"),
                                             **byok_opts))
            if p == "/api/rpa":
                return self._json(run_rpa(req))

            if p == "/api/device/link":
                portal = req.get("portal") or ""
                if portal:
                    try:
                        portal = G.check_url(str(portal))
                    except ValueError as e:
                        return self._json({"error": f"portal: {e}"}, 400)
                out = D.link(portal, req.get("note") or "")
                _heartbeat.portal = out["portal"]
                if out["ok"]:
                    try:
                        out["heartbeat"] = _heartbeat.send(
                            device_payload()["capabilities"])
                    except Exception as e:
                        out["heartbeat"] = {"ok": False, "detail": str(e)[:160]}
                return self._json(out)

            if p == "/api/device/heartbeat":
                caps = device_payload()["capabilities"]
                try:
                    return self._json(_heartbeat.send(caps))
                except Exception as e:
                    return self._json({"ok": False, "detail": str(e)[:200]}, 502)

            if p == "/api/schema/validate":
                return self._json(S.validate(req.get("spec") or {}))

            if p == "/api/schema/compile":
                return self._json({
                    "payload": S.compile_payload(req.get("spec") or {},
                                                 req.get("input") or ""),
                    "script": S.emit_script(req.get("spec") or {},
                                            req.get("endpoint") or
                                            "http://localhost:8649"),
                })

            if p == "/api/corpus/list":
                return self._json(K.scan(req.get("dir") or "",
                                         int(req.get("limit") or 40)))

            if p == "/api/corpus/classify":
                task_id = req.get("task")
                if task_id not in T.TASKS:
                    return self._json({"error": "unknown task"}, 400)
                files = K.extract(req.get("dir") or "", int(req.get("limit") or 20))
                out = []
                for f in files:
                    if f["kind"] == "unsupported" or not f["text"].strip():
                        out.append({"name": f["name"], "kind": f["kind"],
                                    "error": "no extractable text"})
                        continue
                    try:
                        out.append({"name": f["name"], "kind": f["kind"],
                                    "chars": f["chars"],
                                    **analyse(f["text"], task_id, backend_id, **byok_opts)})
                    except Exception as ex:
                        out.append({"name": f["name"], "kind": f["kind"],
                                    "error": str(ex)[:200]})
                return self._json({"dir": req.get("dir"), "task": task_id,
                                   "results": out})

            if p == "/api/batch":
                task_id = req.get("task")
                if task_id not in T.TASKS:
                    return self._json({"error": "unknown task"}, 400)
                out = []
                for row in (req.get("rows") or [])[:50]:
                    txt = str(row)[:20000]
                    try:
                        out.append({"text": txt[:160], "error": None,
                                    **analyse(txt, task_id, backend_id, **byok_opts)})
                    except Exception as ex:
                        out.append({"text": txt[:160], "error": str(ex)[:200]})
                return self._json({"results": out, "task": task_id})

            if p in ("/api/analyse", "/api/classify"):
                text = (req.get("text") or "").strip()
                task_id = req.get("task")
                if not text:
                    return self._json({"error": "text required"}, 400)
                if task_id not in T.TASKS:
                    return self._json({"error": f"unknown task {task_id!r}"}, 400)
                return self._json(analyse(text, task_id, backend_id, **byok_opts))

        except Exception as ex:
            return self._json({"error": str(ex)[:400]}, 400)

        self._json({"error": "not found"}, 404)


def main():
    global BIND
    if not MODEL_DIR:
        print("LAYA_MODEL not set. Run ./start.sh or .\\start.ps1", file=sys.stderr)
        return 2
    BIND = G.resolve_bind()
    print(f"device {D.device_id()}", flush=True)
    if PORTAL:
        _heartbeat.start(lambda: device_payload()["capabilities"])
        print(f"reporting to {PORTAL}", flush=True)
    print(f"open http://localhost:{PORT}", flush=True)
    if BIND not in ("127.0.0.1", "::1", "localhost"):
        print(f"bound to {BIND} - token auth required", flush=True)
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
