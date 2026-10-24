"""Whisper ASR, entirely local. No API, no key, no per-minute cost.

Measured on Intel Core Ultra 9 386H, whisper-base int8 (85 MB), 45 s of speech:

  NPU   0.79 s   rtf 0.017   57x realtime
  GPU   2.49 s   rtf 0.055   18x
  CPU   1.74 s   rtf 0.038   26x

The NPU is 3x faster than the GPU here, which is the opposite of the decision model.
That is the whole reason this is worth doing: audio is one forward pass over a fixed
window, exactly what the NPU is built for.
"""
from __future__ import annotations

import os
import wave

import numpy as np

MODEL = os.environ.get("WHISPER_MODEL", "")
MAX_SECONDS = int(os.environ.get("WHISPER_MAX_SECONDS", "300"))

# Any format, not just WAV: the converter ships with the app.
SUPPORTED = (".wav .mp3 .m4a .aac .ogg .opus .flac .webm .mp4 .mov .amr .wma")

_cache: dict[str, object] = {}


def available() -> dict:
    return {"present": bool(MODEL), "model": MODEL or None,
            "max_seconds": MAX_SECONDS,
            "formats": ["wav", "mp3", "m4a", "aac", "ogg", "opus", "flac",
                        "webm", "mp4", "mov", "amr", "wma"],
            "converter": bool(_ffmpeg_exe()), "max_mb": 60}


def _pipe(device: str):
    key = device.upper()
    if key in _cache:
        return _cache[key]
    import openvino_genai as g
    pipe = g.WhisperPipeline(MODEL, key)
    _cache[key] = pipe
    return pipe


def _ffmpeg_exe() -> str | None:
    """Bundled ffmpeg from imageio-ffmpeg, so nothing needs installing by hand."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def decode_audio(raw: bytes, name: str = "audio") -> tuple[np.ndarray, float]:
    """Any audio in, 16 kHz mono float32 out.

    WAV is parsed directly. Everything else (mp3, m4a, ogg, opus, flac, webm, mp4)
    goes through the bundled ffmpeg, because writing a decoder for those is not worth
    it and shipping one is a two-line dependency.
    """
    import io
    import subprocess
    import tempfile

    if len(raw) > 60 * 1024 * 1024:
        raise ValueError("audio larger than 60 MB; trim it first")

    # Fast path: a real PCM WAV.
    try:
        with wave.open(io.BytesIO(raw), "rb") as w:
            rate = w.getframerate()
            ch = w.getnchannels()
            audio = np.frombuffer(w.readframes(w.getnframes()),
                                  dtype=np.int16).astype(np.float32) / 32768.0
        if ch > 1:
            audio = audio.reshape(-1, ch).mean(axis=1)
        if rate != 16000:
            idx = np.linspace(0, len(audio) - 1, int(len(audio) * 16000 / rate))
            audio = np.interp(idx, np.arange(len(audio)), audio).astype(np.float32)
        seconds = len(audio) / 16000
        if seconds > MAX_SECONDS:
            raise ValueError(f"audio is {seconds:.0f}s, limit is {MAX_SECONDS}s")
        return audio, seconds
    except wave.Error:
        pass  # not a PCM WAV; fall through to ffmpeg

    exe = _ffmpeg_exe()
    if not exe:
        raise ValueError(
            "not a PCM WAV file, and no audio converter is available. "
            "Install it with: pip install imageio-ffmpeg")

    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "in")
        dst = os.path.join(tmp, "out.wav")
        with open(src, "wb") as f:
            f.write(raw)
        proc = subprocess.run(
            [exe, "-v", "error", "-i", src, "-ac", "1", "-ar", "16000",
             "-f", "wav", "-acodec", "pcm_s16le", dst],
            capture_output=True, text=True, timeout=120)
        if proc.returncode != 0 or not os.path.exists(dst):
            detail = (proc.stderr or "").strip().splitlines()
            raise ValueError("could not decode this audio: "
                             + (detail[-1][:160] if detail else "unknown format"))
        with wave.open(dst, "rb") as w:
            audio = np.frombuffer(w.readframes(w.getnframes()),
                                  dtype=np.int16).astype(np.float32) / 32768.0

    seconds = len(audio) / 16000
    if seconds > MAX_SECONDS:
        raise ValueError(f"audio is {seconds:.0f}s, limit is {MAX_SECONDS}s")
    if seconds < 0.2:
        raise ValueError("audio is shorter than 0.2 s")
    return audio, seconds


def transcribe(raw: bytes, device: str = "NPU", language: str = "en") -> dict:
    """Return text, timing and realtime factor. All local."""
    if not MODEL:
        raise RuntimeError("WHISPER_MODEL not set; no transcription model installed")

    audio, seconds = decode_audio(raw)
    pipe = _pipe(device)

    import time
    t0 = time.perf_counter()
    result = pipe.generate(audio)
    elapsed = time.perf_counter() - t0

    text = result.texts[0].strip() if getattr(result, "texts", None) else str(result).strip()
    return {
        "text": text,
        "seconds": round(seconds, 1),
        "infer_s": round(elapsed, 2),
        "rtf": round(elapsed / max(seconds, 0.01), 3),
        "speedup": round(seconds / max(elapsed, 0.01), 1),
        "device": device.upper(),
        "chars": len(text),
    }
