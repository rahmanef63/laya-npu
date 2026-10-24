"""Re-measure the numbers in src/lib/measured.ts.

Run after a driver update or an OpenVINO upgrade, then copy the output into that file so
the UI and README keep telling the truth.

  python tests/bench_backends.py
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import openvino as ov

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

MAXLEN, MARKERS = 256, 8
STATE = {"message": "My payout has failed three days in a row and support chat keeps timing out."}
Q = {"intent": {"type": "choice",
                "instructions": "What does the customer want in `message`?",
                "criteria": {"refund": "money returned", "technical_help": "a bug or outage",
                             "billing_question": "an invoice or plan question",
                             "information": "general information", "other": "none of these"}}}


def main():
    model_dir = os.environ.get("LAYA_MODEL") or os.path.expanduser("~/models/laya-ov-int8")

    import laya
    from laya.common import prepare_batch

    core = ov.Core()
    m = core.read_model(os.path.join(model_dir, "openvino_model.xml"))
    shapes = {i.get_any_name(): ([1, MARKERS] if i.get_any_name().startswith("marker")
                                 else [1, MAXLEN]) for i in m.inputs}
    shapes["qtype"] = [1]
    m.reshape({i.get_any_name(): shapes[i.get_any_name()] for i in m.inputs})

    agent = laya.OVAgent(model_dir, device="CPU")
    pad = agent.tok.pad_token_id or 0
    _, _, b = prepare_batch(agent.tok, STATE, Q, MAXLEN, 192)

    def padded(key, width, fill=0):
        a = b[key].numpy().astype(np.int64)
        return np.pad(a, ((0, 0), (0, width - a.shape[1])), constant_values=fill)

    feed = {
        "input_ids": padded("input_ids", MAXLEN, pad),
        "attention_mask": padded("attention_mask", MAXLEN),
        "marker_pos": padded("marker_pos", MARKERS),
        "marker_mask": padded("marker_mask", MARKERS),
        "qtype": b["qtype"].numpy().astype(np.int64),
    }

    out = {}
    for dev in ("NPU", "GPU", "CPU"):
        if dev not in core.available_devices:
            out[dev] = {"present": False}
            continue
        try:
            t0 = time.perf_counter()
            cm = core.compile_model(m, dev)
            compile_s = time.perf_counter() - t0
            req = cm.create_infer_request()
            req.infer(feed)                    # warmup
            n = 40
            t0 = time.perf_counter()
            for _ in range(n):
                req.infer(feed)
            out[dev] = {"present": True, "compile_s": round(compile_s, 1),
                        "ms": round((time.perf_counter() - t0) / n * 1000, 1)}
        except Exception as e:
            out[dev] = {"present": True, "error": str(e)[:160]}

    print(json.dumps(out, indent=2))
    print("\nCopy these into MEASURED.decision in src/lib/measured.ts, with today's date.",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
