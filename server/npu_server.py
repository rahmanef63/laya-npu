"""Laya on Intel NPU — Jev System-One wire protocol.

NPU requires a fully static graph. The installer calls `prepare()` once to turn the
dynamic IR from Hugging Face into a static one; after that this server just loads it.

Three things NPU insists on, all handled here:
  1. every input has a fixed shape (no `[?,?]`)
  2. tensors are *exactly* that size, not "at most" — so we pad
  3. input names are read from the model, because the traced IR names
     attention_mask `"120"`
"""
from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import openvino as ov

import laya
from laya.common import decode_answers, prepare_batch

MODEL_DIR = os.environ.get("LAYA_MODEL", "")
DEVICE = os.environ.get("LAYA_DEVICE", "NPU")
PORT = int(os.environ.get("LAYA_PORT", "8645"))
BIND = os.environ.get("LAYA_BIND", "127.0.0.1")
MAXLEN = int(os.environ.get("LAYA_MAXLEN", "256"))
MARKERS = int(os.environ.get("LAYA_MARKERS", "8"))
ROWS = int(os.environ.get("LAYA_ROWS", "1"))
API_KEY = os.environ.get("LAYA_API_KEY", "")

IR = "openvino_model"


def _input_shape(name: str) -> list[int]:
    if name == "qtype":
        return [ROWS]
    if name.startswith("marker"):
        return [ROWS, MARKERS]
    return [ROWS, MAXLEN]


def prepare(model_dir: str, maxlen: int = MAXLEN, markers: int = MARKERS) -> str:
    """Turn the dynamic IR into a static one NPU accepts. Idempotent."""
    src = os.path.join(model_dir, IR + ".xml")
    dst = os.path.join(model_dir, IR + "_static.xml")
    core = ov.Core()
    model = core.read_model(src)
    shapes = {}
    for i in model.inputs:
        n = i.get_any_name()
        shapes[n] = [1, markers] if n.startswith("marker") else [1, maxlen]
    shapes["qtype"] = [1]
    model.reshape({i.get_any_name(): shapes[i.get_any_name()] for i in model.inputs})
    ov.save_model(model, dst)
    # weights are shared: point the static IR at the same .bin
    if not os.path.exists(os.path.join(model_dir, IR + "_static.bin")):
        bin_src = os.path.join(model_dir, IR + ".bin")
        if os.path.exists(bin_src):
            os.replace(dst.replace(".xml", ".bin"), dst.replace(".xml", ".bin"))
    return dst


class Engine:
    def __init__(self, model_dir: str, device: str = DEVICE):
        self.dir = model_dir
        self.device = device
        self.agent = laya.OVAgent(model_dir, device="CPU")   # tokenizer + temperatures
        self.pad_id = self.agent.tok.pad_token_id or 0

        static = os.path.join(model_dir, IR + "_static.xml")
        xml = static if os.path.exists(static) else os.path.join(model_dir, IR + ".xml")
        core = ov.Core()
        core.set_property({"CACHE_DIR": os.path.join(model_dir, ".ovcache")})
        model = core.read_model(xml)
        try:
            shapes = {i.get_any_name(): _input_shape(i.get_any_name()) for i in model.inputs}
            model.reshape(shapes)
        except Exception:
            pass                                    # already static
        self.compiled = core.compile_model(model, device)
        self.lock = threading.Lock()
        self.local = threading.local()

    def _req(self):
        r = getattr(self.local, "req", None)
        if r is None:
            r = self.local.req = self.compiled.create_infer_request()
        return r

    def _pad(self, a, rows, cols, value=0):
        out = np.full((rows, cols), value, np.int64)
        r = min(rows, a.shape[0])
        c = min(cols, a.shape[1])
        out[:r, :c] = a[:r, :c]
        return out

    def system_one(self, state, questions):
        qids, items, b = prepare_batch(self.agent.tok, state, questions, MAXLEN, 192)
        n = len(qids)

        ids = self._pad(b["input_ids"].numpy().astype(np.int64), ROWS, MAXLEN, self.pad_id)
        att = self._pad(b["attention_mask"].numpy().astype(np.int64), ROWS, MAXLEN)
        mpos = self._pad(b["marker_pos"].numpy().astype(np.int64), ROWS, MARKERS)
        mmask = self._pad(b["marker_mask"].numpy().astype(np.int64), ROWS, MARKERS)
        qtype = np.zeros(ROWS, np.int64)
        src = b["qtype"].numpy().astype(np.int64)
        qtype[: min(ROWS, len(src))] = src[:ROWS]

        with self.lock:
            req = self._req()
            req.infer({"input_ids": ids, "attention_mask": att, "marker_pos": mpos,
                       "marker_mask": mmask, "qtype": qtype})
            logits = req.get_tensor("logits").data[:n]
            act = req.get_tensor("act_logits").data[:n]

        answers = decode_answers(logits, act, qids, items, questions,
                                 self.agent.temperature, self.agent.temperature_by_options)
        return {
            "model": "laya-rl-agent",
            "answers": answers,
            "usage": {"input_tokens": int(att[:n].sum()), "output_tokens": 0,
                      "maxlen": MAXLEN, "markers": MARKERS},
            "routing": {"model": "english", "device": self.device,
                        "reason": "static IR", "maxlen": MAXLEN},
        }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    engine: Engine = None

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200, extra=None):
        body = json.dumps(obj, default=float).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _authorised(self):
        if not API_KEY:
            return True
        got = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        return got == API_KEY

    def do_GET(self):
        p = self.path.rstrip("/")
        if p.endswith("/health"):
            return self._json({"status": "ok", "device": self.engine.device,
                               "maxlen": MAXLEN, "markers": MARKERS, "rows": ROWS})
        if p.endswith("/models"):
            return self._json({"object": "list", "data": [
                {"id": "laya", "object": "model", "owned_by": "intel-npu"}]})
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        p = self.path.rstrip("/")
        if not (p.endswith("/v1/systemone") or p.endswith("/predict")):
            return self._json({"error": "not found"}, 404)
        if not self._authorised():
            return self._json({"error": "unauthorised"}, 401)

        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        state = body.get("state")
        questions = body.get("questions")
        if state is None or not isinstance(questions, dict) or not questions:
            return self._json({"error": "state and questions required"}, 400)
        if len(questions) > ROWS:
            return self._json({"error": f"at most {ROWS} questions per request"}, 413)

        t0 = time.perf_counter()
        try:
            out = self.engine.system_one(state, questions)
        except Exception as e:
            return self._json({"error": str(e)[:300]}, 422)
        ms = (time.perf_counter() - t0) * 1000
        self._json(out, extra={"X-Inference-Time-Ms": f"{ms:.1f}"})


def serve(model_dir: str, device: str = DEVICE):
    Handler.engine = Engine(model_dir, device)
    print(f"[laya] {device} ready maxlen={MAXLEN} markers={MARKERS} rows={ROWS}", flush=True)
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()


if __name__ == "__main__":
    if not MODEL_DIR:
        raise SystemExit("set LAYA_MODEL to the model directory")
    serve(MODEL_DIR)
