# laya-npu

Typed decisions — **choice / score / noul** — and local speech-to-text, on whatever
compute you have: an Intel NPU, a GPU, a CPU, or an endpoint you bring yourself.

[![ci](https://github.com/rahmanef63/laya-npu/actions/workflows/ci.yml/badge.svg)](https://github.com/rahmanef63/laya-npu/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![node](https://img.shields.io/badge/node-20%2B-blue.svg)](https://nodejs.org/)

**Live:** [laya.manef.dev](https://laya.manef.dev) · **Web UI source:** `src/` in this repo, not a bundle

---

## What this is

Most laptops now ship a neural processor that nothing uses. Windows runs background blur
on it and leaves it alone. This is software that actually runs on it: two models, one for
decisions and one for speech, both local, both free per request.

| | |
|---|---|
| **Decision model** | Laya, 421M parameters, INT8. Give it text and typed questions, get back a label or score with a probability. It cannot write prose. |
| **Speech model** | Whisper base, 85 MB, INT8. 45 seconds of audio in 0.79 seconds. |
| **Runs on** | Intel NPU (fastest for audio), iGPU, CPU, or an endpoint you already pay for. |
| **Cost per request** | $0 on local hardware. |
| **Cloud dependency** | None. One optional outbound heartbeat, documented and opt-out. |

The interesting finding, and the reason this project exists: **an NPU is excellent at
single-pass work and poor at autoregressive generation.** Transcription is 3x faster on
the NPU than on the GPU; an LLM decode loop is slower than the GPU. Both measurements are
in this repo rather than asserted.

## Contents

- [Which file do I run?](#which-file-do-i-run)
- [Backends](#backends)
- [Install](#install)
- [Device ID and the registry](#device-id-and-the-registry)
- [The five presets](#the-five-presets)
- [Transcribe](#transcribe-whisper-local)
- [Voice: audio to decision](#voice-audio-to-decision-one-pipeline)
- [Why the model does not pick the action](#why-the-model-does-not-pick-the-action)
- [Security](#security)
- [Layout](#layout)
- [Limits](#limits)
- [Contributing](#contributing)
- [Credits](#credits)

---

## Which file do I run?

| Your shell | Run this | Why |
|---|---|---|
| **PowerShell / cmd** (Windows) | `install.cmd` then `laya-npu.cmd` | the NPU path lives here |
| **WSL** (bash inside Windows) | `./install.sh` then `./start.sh` | these detect WSL and hand off to Windows |
| **Linux** | `./install.sh` then `./start.sh` | CPU and BYOK; no NPU exists there |
| **Git Bash** | `./install.sh` | same handoff |

If you typed `.\install.cmd` in a bash prompt and got `command not found`: that is a
Windows batch file, bash cannot run it. Use `./install.sh`, or open the folder in
Explorer and double-click `install.cmd`.

The NPU is **not reachable from WSL or any VM**. OpenVINO inside a VM sees CPU only —
a host's graphics and neural hardware are not passed through. So on WSL the installer
deliberately hands off to the Windows side rather than installing a CPU-only copy.


---

## Backends

The same checkpoint everywhere. Only the forward pass moves.

Measured 2026-10-24, Intel Core Ultra 9 386H, OpenVINO 2026.4.1, INT8, 256-token
window, 40 iterations after warmup. `src/lib/measured.ts` is the single source these
numbers come from everywhere in the UI.

| Backend | Hardware | Warm latency | First compile |
|---|---|---|---|
| **NPU** | Intel AI Boost | **26.5 ms** | 17.6 s |
| **GPU** | Intel Xe3 iGPU | 32.5 ms | 3.7 s |
| **CPU** | any x86 | 182.3 ms | 3.3 s |
| **BYOK** | your endpoint | depends | none |

### Also: Whisper

| Backend | 45 s of audio | realtime |
|---|---|---|
| NPU | 0.79 s | 57x |
| CPU | 1.74 s | 26x |
| GPU | 2.49 s | 18x |

Re-measure both with `python tests/bench_backends.py`.

Measured on Intel Core Ultra 9 386H, OpenVINO 2026.4.1, INT8, 256-token window,
one question per request. The NPU is the low-power choice; the GPU is faster on a
machine that has both, which surprises people. Numbers are in `Performance` in the app.

### BYOK

Point the app at any server speaking the **Jev System One** protocol:

```
POST {your-endpoint}/v1/systemone
Authorization: Bearer {your-key}
{ "state": {...}, "questions": { "id": {"type": "choice", ...} } }
```

The key is forwarded server-side, never written to disk, never echoed back. Set
`BYOK_URL` / `BYOK_KEY` in the environment, or type them in Compute → Bring your own key.

---

## Install

### Windows (has the NPU)

```powershell
git clone https://github.com/rahmanef63/laya-npu.git
cd laya-npu
.\install.cmd
```

Or double-click `install.cmd` after extracting a zip. Then double-click the
`laya-npu` icon the installer put on your Desktop.

`install.ps1` does, in order:

1. finds or installs Python 3.12
2. installs OpenVINO and the laya fork
3. downloads the INT8 model (405 MB, skipped if present)
4. rebuilds the IR to a static shape the NPU accepts
5. reads the installed NPU driver, scrapes the latest from Intel, reports the verdict
6. verifies that NPU, GPU and CPU each compile
7. builds the web app
8. writes `.env` and creates the shortcuts

Idempotent: run it again and it skips finished steps.

### NPU driver

The installer **detects** the driver and tells you what to do; it does not silently
install one.

```
== NPU driver
  installed: 32.0.100.5540 (2026-08-20)
  latest:    32.0.100.5540
  ok  driver is current
```

Four states, each with one action:

| state | action |
|---|---|
| current | none |
| newer version published | link + `-InstallDriver` hint |
| version OpenVINO documents as crashing Panther Lake | link, marked as known-bad |
| no NPU present | app falls back to GPU or CPU |

Automatic install is available but **opt-in**:

```powershell
.\install.ps1 -InstallDriver
```

It needs administrator rights and a reboot, and on an OEM laptop the vendor build is
the one that was tested — which is exactly why it is a flag you type, not something
`install.cmd` does for you.

In the app, **Compute → NPU driver** shows the same verdict with a download link.

### Linux / WSL (CPU and BYOK)

```bash
git clone https://github.com/rahmanef63/laya-npu.git
cd laya-npu
./install.sh
./start.sh
```

The NPU is not reachable from WSL or Linux — only from the Windows host.

---

## Device ID and the registry

Each install derives a stable ID from the machine identifier, shown in **Compute**:

```
NPU-7K3M-2QXV
```

The installer writes `LAYA_PORTAL=https://laya.manef.dev` into `.env`, so the app
reports to the registry every five minutes on its own. You can also paste the ID into
the portal to check it.

Reporting is **outbound only**. The portal never reaches into a machine, and what it
stores is thin: the ID, OS, architecture, app version, which OpenVINO devices
compiled, and timestamps. No text, no prompts, no paths, no keys.

## The five presets

Question wording is copied verbatim from `laya/presets.py`, so results match the
reference implementation:

| Preset | Questions |
|---|---|
| Email | category, spam, phishing, urgency, needs-reply |
| Support ticket | intent, urgency, frustration, refund, churn |
| LLM guardrail | jailbreak, injection, sensitive data, harm |
| Model router | difficulty, domain, tools, sensitivity |
| Moderation | toxicity, harassment, violence, spam, severity |

Plus a custom playground: define your own `choice` options, `score` levels, or a
`noul` with true/false conditions, and run it against any backend.

---

## Transcribe (Whisper, local)

Speech to text with **no API and no key**. whisper-base int8 is 85 MB and runs on the
same devices as everything else.

Measured on 45 s of speech, Intel Core Ultra 9 386H:

| device | time | realtime factor |
|---|---|---|
| **NPU** | **0.79 s** | **57x realtime** |
| CPU | 1.74 s | 26x |
| GPU | 2.49 s | 18x |

The NPU beats the GPU by 3x here — the opposite of the decision model. That is the
distinction worth understanding: transcription is one forward pass over a fixed audio
window, while an LLM decode loop is inherently sequential. The NPU is built for the
first and bad at the second.

Setup:

```powershell
python -c "from huggingface_hub import snapshot_download; snapshot_download('OpenVINO/whisper-base-int8-ov', local_dir=r'C:\Users\you\models\whisper-base-int8')"
```

Then add to `.env`:

```
WHISPER_MODEL=C:\Users\you\models\whisper-base-int8
```

The installer writes this line for you. WAV only (16-bit PCM); other formats must be
converted first. 300 s per file.

API: `POST /api/asr` with the WAV as the raw body, `X-Device: NPU` as a header.

```bash
curl -X POST http://localhost:8649/api/asr \
  -H "X-Device: NPU" -H "Content-Type: application/octet-stream" \
  --data-binary @meeting.wav
```

```json
{"text": "We are writing about invoice 1042 from Northwind Supplies...",
 "seconds": 45.3, "infer_s": 0.59, "speedup": 76.4, "device": "NPU"}
```

## Voice: audio to decision, one pipeline

A voice note goes in, a decision comes out. No cloud anywhere in the path.

```
audio.wav -> [Whisper NPU] -> transcript -> [Laya NPU] -> probabilities -> [Python] -> action
```

Two models, both on the same NPU. Measured end to end:

| input | transcription | decision | total | realtime |
|---|---|---|---|---|
| 45 s invoice note | 0.78 s | 0.14 s | **0.92 s** | **49x** |
| 6.8 s outage report | 0.24 s | 0.07 s | **0.31 s** | 22x |

Results, verbatim from a run:

```
"We are writing about invoice 1042 from Northwind Supplies..."
  -> Auto-reply, billing_question
     intent billing_question p=0.90 · churn_risk 0.05

"The dashboard will not load since this morning. All our users are blocked..."
  -> Escalate to technical
     intent technical_help p=0.99
```

First request after a restart takes about 88 s: both graphs compile for the NPU. Every
request after that is under a second. The compiled kernels are cached in
`models/*/.ovcache`, so a warm restart is fast too.

API:

```bash
curl -X POST http://localhost:8649/api/voice \
  -H "X-Device: NPU" -H "X-Task: triage" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @voice-note.wav
```

`X-Task` picks any preset: `triage`, `email`, `guard`, `router`, `moderation`.

Why this is the strongest use of the hardware so far: both stages are single forward
passes over a fixed window, which is exactly what an NPU is for. A 45-second recording
becomes a routed, labelled ticket in under a second, for free, with the audio never
leaving the machine.

## Why the model does not pick the action

Asking the model for an action scores **2/12**. Asking the preset's questions and
deriving the action in Python scores **22/22**.

The model reads text well and knows your policy not at all. It does not know that a
refund needs approval and a receipt does not. So the policy is ordinary code:

```python
if team == "security":      return "escalate", "Escalate to security"
if _yes(is_phishing, 0.85): return "quarantine", "Quarantine: phishing"
if kind == "refund":        return "request_approval", "Refund needs approval"
```

Thresholds were measured, not guessed:

| signal | false positive | true positive | threshold |
|---|---|---|---|
| `is_spam` | legit sales email 0.619 | real spam 0.88–1.00 | 0.80 |
| `is_phishing` | legit sales email 0.741 | real phishing 0.859+ | 0.85 |
| `jailbreak` | "write a python function" 0.919 | real 0.998 | 0.95 |
| `sensitive_data` | answers 0.230 on a prompt with an email + SSN | — | unusable, regex instead |

---

## Layout

```
laya-npu/
├── install.ps1 / install.cmd      one-click setup (double-clickable)
├── laya-npu.cmd / start.ps1       launch (double-clickable)
├── shortcut.ps1                   desktop + Start Menu shortcuts
├── server/
│   ├── backends.py                NPU / GPU / CPU / BYOK
│   ├── web.py                     API + static file server
│   ├── tasks.py                   presets and the policy layer
│   └── custom.py                  custom questions and the RPA pipeline
├── src/
│   ├── routes/+page.svelte        shell: header, dynamic menu, one view
│   └── lib/
│       ├── registry.ts            sidebar entries and project metadata
│       ├── views/                 one component per section
│       └── api.ts                 typed API client
├── web/dist/                      static build served by web.py
└── tests/                         accuracy and policy harnesses
```

The menu is generated from `registry.ts`. Adding an entry there and a component in
`views/` is all it takes to add a page. Each view fills the viewport; nothing
autoscrolls and no section is clipped.

---

## Security

The API can read files and fetch URLs, so it is treated as something that must not be
exposed casually.

- **Binds to `127.0.0.1` by default.** Setting `LAYA_BIND=0.0.0.0` without `LAYA_TOKEN`
  refuses to start rather than opening an unauthenticated port on your network.
- **Token auth** on every `/api/*` route when `LAYA_TOKEN` is set.
- **Rate limited** per client and per route: 120 requests/min normally, 20 for audio,
  corpus and batch.
- **Body caps**: 2 MB for JSON, 60 MB for audio. Oversized requests get a 413 before
  being read.
- **URL validation on BYOK and the device link.** Anything resolving to a private,
  loopback or link-local address is refused, because a caller-supplied URL is an SSRF
  primitive. Override with `LAYA_ALLOW_PRIVATE_URL=1` if you genuinely mean to call a
  machine on your own network.
- **The portal** rate limits registration to 30/min per client and exposes an admin
  prune (`POST /api/devices/prune`, `X-Admin-Key`) that deletes records older than N
  days.

Not done yet: the Python dependencies are not pinned to hashes, there is no CI or
dependency scanning, and the registry has no captcha. Read `SECURITY.md` before
exposing anything.

## Limits

- **English only.** The shipped checkpoint is English. It scores near zero on
  non-Latin scripts while reporting 0.95 confidence — a silent failure.
  `laya-multilingual` has never been exported to OpenVINO.
- **256 tokens** of state, **8 options** per choice question.
- **Threshold margin 0.03.** Device drift reaches 0.025.
- Zero-shot. For a domain job, fine-tune a head with
  [stuntd](https://github.com/bladedevoff/stuntd) on ~3000 labelled rows.

---

## Team

Maintained by [rahmanef63](https://rahmanef.com) with
[official-manef](https://github.com/official-manef) and
[ManefDev](https://github.com/ManefDev). Built to be shown on
[manef.dev](https://manef.dev).

## Contributing

Issues and pull requests are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) first — it
lists the changes this project will not accept (cloud fallbacks, removing the honest
limits, telemetry) so you do not build something that gets declined.

```bash
make lint     # python syntax + ruff + svelte-check
make test     # policy and accuracy harnesses, real model, no mocks
make bench    # re-measure backend latency
```

New to the codebase? [docs/DEVELOPING.md](docs/DEVELOPING.md) gets you to a running dev
environment, and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) explains how the pieces fit.
The web UI is fully in this repo under `src/` — `npm run dev` gives hot reload against the
real API.

Security issues: see [SECURITY.md](SECURITY.md). Do not open a public issue.

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

## Credits

- [Laya](https://github.com/NandhaKishorM/laya) by Convai Innovations (Apache-2.0)
- [laya-openvino](https://github.com/rupeshs/laya-openvino) by Rupesh Sreeraman
- [rupeshs/laya-ov-int8](https://huggingface.co/rupeshs/laya-ov-int8) — the INT8 IR

Not affiliated with Convai Innovations. Apache-2.0.
