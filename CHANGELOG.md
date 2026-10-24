# Changelog

Notable changes. Dates are shipping dates, not commit dates.

## 2026-10-24

Landing page gained the two things a visitor asked for: a diagram of what actually
happens, and an install that is one line instead of four steps.

- **Flow diagram** on the landing page: input, optional Whisper, Laya's typed answers,
  your policy, the action. Pure CSS, no script. It also states the 2/12 vs 22/22 split,
  so the "why does Python decide instead of the model" question is answered before it is
  asked.
- **One-line Windows install**: `irm https://laya.manef.dev/i.ps1 | iex`. The bootstrap
  is 30 lines, downloads the archive, and hands off to `install.ps1`; a second run reuses
  the existing copy and keeps `.env`. README and SECURITY both say plainly that this
  executes remote code and that the zip path is equivalent without it.
- Portal route `/i.ps1` serves the bootstrap as `text/plain`.

Hardening pass ahead of opening the repo.

- **The API no longer binds to all interfaces by default.** `127.0.0.1` unless you set
  `LAYA_BIND`, and the server refuses to start on a non-loopback address without
  `LAYA_TOKEN`. The API can read files and fetch URLs, so an open port was the wrong
  default.
- Token auth on every `/api/*` route, per-route rate limits, and body caps enforced
  before the body is read.
- **BYOK and portal URLs are validated.** Private, loopback and unresolvable targets are
  refused, because a caller-supplied URL is an SSRF primitive.
- **Device rows are no longer public.** `/api/devices` requires an admin key; the public
  page shows aggregate counts. `/api/device/check` returns found plus a coarse state
  instead of OS, version, backend list and report count.
- Portal gained registration rate limiting and an admin prune route.
- `LICENSE` (Apache-2.0) actually added; it was referenced but missing.
- `SECURITY.md` with defaults, the exact heartbeat payload, limits, and a list of known
  gaps.
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `Makefile`, CI workflow, issue and PR
  templates, `.env.example`.
- Performance numbers unified in `src/lib/measured.ts`; README, Compute and Performance
  all read from it. Re-measured: NPU 26.5 ms, GPU 32.5, CPU 182.3.
- **Setup check** page: server, hardware, NPU and driver, with the fix next to any red row.
- FAQ rebuilt around twenty questions, grouped from basics to troubleshooting.

## 2026-10-23

- **Voice pipeline**: audio to decision, both stages on the NPU. 45 s of speech in 0.92 s,
  end to end.
- **Whisper transcription** at 57x realtime on the NPU, 85 MB model, no API.
- Audio accepts mp3, m4a, aac, ogg, opus, flac, webm, mp4, mov, amr and wma through a
  bundled ffmpeg; WAV is parsed directly.
- Documented that the NPU is 3x faster than the GPU for audio and slightly slower for
  decisions. Both are measured, both are in the repo.

## 2026-10-22

- Playground rebuilt around Laya's own presets, verbatim wording.
- **Policy layer split from perception.** Asking the model for an action scores 2/12;
  asking the preset's questions and deriving the action in Python scores 22/22.
- Open Corpus: point at a directory, extract text, classify each file. PDF via pypdf.
- Schema compiler: write your own decision format, validate, compile, download a client.
- Four compute backends behind one interface: NPU, GPU, CPU, BYOK.
- Device registry and portal deployed at laya.manef.dev.

## 2026-10-21

- First working version: Laya on the Intel NPU through OpenVINO.
- Three findings that made it work: the static IR needs reshaping, `attention_mask` is
  named `"120"` in the traced graph, and every tensor must be exactly the declared size.
- Initial benchmark claim of 15x was wrong; corrected to 2.2x to 8.1x depending on text
  length, and the mistake is documented rather than quietly edited.
