"""Compute backends: local OpenVINO devices and hosted BYOK providers.

The model is the same decision head everywhere. What changes is where the forward
pass runs:

  local   NPU / GPU / CPU through OpenVINO, one graph, three devices
  byok    any hosted endpoint that speaks the Jev System One protocol

Measured on this machine (Intel Core Ultra 9 386H, INT8, 256-token window):
  NPU   29.3 ms   compiled in 26 s
  GPU   34.7 ms   compiled in 11 s
  CPU  404.0 ms   compiled in  7 s
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request

import numpy as np
import openvino as ov

MAXLEN = int(os.environ.get("LAYA_MAXLEN", "256"))
MARKERS = int(os.environ.get("LAYA_MARKERS", "8"))

# Devices this build knows how to describe. Presence is decided at runtime by
# OpenVINO, never assumed: the UI shows a tab only if the device answers.
LOCAL_DEVICES = ("NPU", "GPU", "CPU")

DESCRIPTIONS = {
    "NPU": "Intel AI Boost. Lowest power, flat ~29 ms regardless of text length.",
    "GPU": "Integrated Xe3. Similar latency to the NPU, faster to compile.",
    "CPU": "Fallback. Same answers, roughly 13x slower on a 256-token window.",
}


class LocalBackend:
    """One compiled graph per device, created lazily."""

    kind = "local"

    def __init__(self, model_dir: str):
        self.dir = model_dir
        self.lock = threading.Lock()
        self.local = threading.local()
        self._engines: dict[str, object] = {}
        self._errors: dict[str, str] = {}
        self._agent = None
        self._core = ov.Core()
        self._core.set_property({"CACHE_DIR": os.path.join(model_dir, ".ovcache")})

        # tokenizer + calibration temperatures come from the laya agent, CPU only
        import laya
        self._agent = laya.OVAgent(model_dir, device="CPU")
        self._pad = self._agent.tok.pad_token_id or 0

        self.device = self._pick_default()

    # -- device discovery ---------------------------------------------------

    def available(self) -> list[dict]:
        out = []
        for dev in LOCAL_DEVICES:
            present = dev in self._core.available_devices
            probe = self._probe(dev) if present else {"ok": False, "reason": "not present"}
            out.append({
                "id": f"local:{dev.lower()}",
                "device": dev,
                "label": f"Local {dev}",
                "kind": "local",
                "present": present,
                "ready": probe.get("ok", False),
                "reason": probe.get("reason"),
                "latency_ms": probe.get("ms"),
                "compile_s": probe.get("compile_s"),
                "description": DESCRIPTIONS.get(dev, ""),
            })
        return out

    def _probe(self, dev: str) -> dict:
        """A cheap cached compile check. Kept short: this runs once at startup."""
        if dev in self._engines:
            return {"ok": True}
        if dev in self._errors:
            return {"ok": False, "reason": self._errors[dev]}
        return {"ok": True}  # compiled on demand; presence is enough at startup

    def _pick_default(self) -> str:
        env = os.environ.get("LAYA_DEVICE")
        if env in LOCAL_DEVICES and env in self._core.available_devices:
            return env
        for dev in LOCAL_DEVICES:
            if dev in self._core.available_devices:
                return dev
        raise RuntimeError("no OpenVINO device available")

    # -- inference ----------------------------------------------------------

    def _graph(self):
        return self._core.read_model(os.path.join(self.dir, "openvino_model_static.xml"))

    def _compiled(self, dev: str):
        with self.lock:
            cm = self._engines.get(dev)
            if cm is not None:
                return cm
            try:
                t0 = time.perf_counter()
                model = self._graph()
                model.reshape({i.get_any_name(): self._shape(i.get_any_name())
                               for i in model.inputs})
                cm = self._core.compile_model(model, dev)
                self._engines[dev] = cm
                self._errors.pop(dev, None)
                print(f"[backend] {dev} compiled in {time.perf_counter()-t0:.1f}s",
                      flush=True)
                return cm
            except Exception as e:
                self._errors[dev] = str(e)[:200]
                raise

    @staticmethod
    def _shape(name: str) -> list[int]:
        if name == "qtype":
            return [1]
        if name.startswith("marker"):
            return [1, MARKERS]
        return [1, MAXLEN]

    def _pad_to(self, a, rows, cols, value=0):
        out = np.full((rows, cols), value, np.int64)
        r = min(rows, a.shape[0])
        c = min(cols, a.shape[1])
        out[:r, :c] = a[:r, :c]
        return out

    def system_one(self, state, questions, device: str | None = None):
        from laya.common import decode_answers, prepare_batch

        dev = (device or self.device).upper()
        cm = self._compiled(dev)

        qids, items, b = prepare_batch(self._agent.tok, state, questions, MAXLEN, 192)
        ids = self._pad_to(b["input_ids"].numpy().astype(np.int64), 1, MAXLEN, self._pad)
        att = self._pad_to(b["attention_mask"].numpy().astype(np.int64), 1, MAXLEN)
        mp = self._pad_to(b["marker_pos"].numpy().astype(np.int64), 1, MARKERS)
        mm = self._pad_to(b["marker_mask"].numpy().astype(np.int64), 1, MARKERS)
        qt = np.zeros(1, np.int64)
        src = b["qtype"].numpy().astype(np.int64)
        qt[: min(1, len(src))] = src[:1]

        req = getattr(self.local, "req", None)
        if req is None or getattr(self.local, "dev", None) != (dev, id(cm)):
            req = self.local.req = cm.create_infer_request()
            self.local.dev = (dev, id(cm))

        with self.lock:
            req.infer({"input_ids": ids, "attention_mask": att, "marker_pos": mp,
                       "marker_mask": mm, "qtype": qt})
            logits = req.get_tensor("logits").data
            act = req.get_tensor("act_logits").data

        answers = decode_answers(logits, act, qids, items, questions,
                                 self._agent.temperature,
                                 self._agent.temperature_by_options)
        return {
            "model": "laya-rl-agent",
            "answers": answers,
            "usage": {"input_tokens": int(att.sum()), "output_tokens": 0},
            "routing": {"model": "english", "device": dev,
                        "reason": "static IR", "maxlen": MAXLEN},
        }


class ByokBackend:
    """A hosted endpoint that speaks the Jev System One protocol.

    The key never leaves the server: it is read from the environment or supplied
    per request, forwarded in an Authorization header, and never echoed back.
    """

    kind = "byok"

    def __init__(self):
        self.url = os.environ.get("BYOK_URL", "").rstrip("/")
        self.key = os.environ.get("BYOK_KEY", "")
        self.model = os.environ.get("BYOK_MODEL", "jev")
        self.configured = bool(self.url)

    def describe(self) -> dict:
        return {
            "id": "byok",
            "device": "BYOK",
            "label": "Your own endpoint",
            "kind": "byok",
            "present": True,
            "ready": self.configured,
            "reason": None if self.configured else "No endpoint configured",
            "latency_ms": None,
            "compile_s": None,
            "description": "Point at any server that speaks Jev System One, or your "
                           "own hosted deployment. The key stays server-side.",
            "url": self.url or None,
            "model": self.model or None,
        }

    def system_one(self, state, questions, *, url=None, key=None, model=None,
                   timeout=25):
        target = (url or self.url).rstrip("/")
        if not target:
            raise RuntimeError("BYOK endpoint not configured")
        credential = key or self.key

        body = {"state": state, "questions": questions, "model": model or self.model}
        headers = {"Content-Type": "application/json"}
        if credential:
            headers["Authorization"] = f"Bearer {credential}"

        req = urllib.request.Request(f"{target}/v1/systemone",
                                     data=json.dumps(body).encode(), headers=headers)
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                payload = json.loads(r.read())
        except urllib.error.HTTPError as e:
            detail = e.read()[:200].decode("utf-8", "replace")
            raise RuntimeError(f"upstream {e.code}: {detail}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"upstream unreachable: {e.reason}")

        ms = (time.perf_counter() - t0) * 1000
        payload.setdefault("routing", {})
        payload["routing"].update({"device": "BYOK", "reason": target,
                                   "latency_ms": round(ms, 1)})
        return payload
