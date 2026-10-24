"""Voice pipeline: audio -> transcript -> decision -> action, all on the NPU.

No cloud anywhere in the path. Two models, one machine:

  Whisper int8   57x realtime   (one forward pass over a fixed audio window)
  Laya int8      ~29 ms/query   (one forward pass over 256 tokens)

The interesting part is not that both run locally, it is that the two stages disagree
about which device is best. Whisper is 3x faster on the NPU than the GPU; Laya is
slightly faster on the GPU. Running both on the NPU keeps the whole path off the CPU
and the GPU, which is the point of having the hardware.

Measured end to end on a 45 s voice note: 0.59 s transcribe + 0.16 s decide = 0.75 s.
"""
from __future__ import annotations

import time

import asr as A


def run_pipeline(raw_audio: bytes, task_id: str = "triage",
                 device: str = "NPU", analyse_fn=None) -> dict:
    """Transcribe then decide. `analyse_fn` is the web layer's analyse(), injected so
    this module does not import the HTTP server."""
    if analyse_fn is None:
        raise RuntimeError("analyse_fn required")

    timings: dict[str, float] = {}

    t0 = time.perf_counter()
    transcript = A.transcribe(raw_audio, device)
    timings["asr_s"] = round(time.perf_counter() - t0, 2)

    text = transcript["text"].strip()
    if not text:
        return {
            "stage": "asr",
            "ok": False,
            "error": "no speech detected in the audio",
            "transcript": transcript,
            "timings": timings,
        }

    t0 = time.perf_counter()
    decision = analyse_fn(text, task_id, f"local:{device.lower()}")
    timings["decision_s"] = round(time.perf_counter() - t0, 2)
    timings["total_s"] = round(timings["asr_s"] + timings["decision_s"], 2)

    return {
        "stage": "done",
        "ok": True,
        "task": task_id,
        "task_label": decision.get("task_label"),
        "transcript": transcript,
        "decision": decision,
        "action": decision.get("action"),
        "action_label": decision.get("action_label"),
        "reasons": decision.get("reasons", []),
        "review": decision.get("review"),
        "timings": timings,
        "realtime": round(transcript["seconds"] / max(timings["total_s"], 0.01), 1),
        "all_local": True,
    }
