# Security

## Reporting

Report privately. Open a [security advisory](https://github.com/rahmanef63/laya-npu/security/advisories/new)
or email the maintainer via <https://rahmanef.com>. Please do not open a public issue for
a vulnerability, and do not include model input, prompts, keys or file contents in any
report.

There is no bug bounty.

## What this software is

A local web app that runs two models on your own hardware, plus an optional public
registry that records which machines installed it.

It has three properties that make it worth thinking about security properly:

1. It can **read files** from directories you point it at.
2. It can **fetch URLs** you supply (BYOK endpoint, portal link).
3. It ships as **one process serving both the UI and the API**, with no separation
   between them.

## Defaults, and why

| Setting | Default | Reason |
|---|---|---|
| Bind address | `127.0.0.1` | The API has no separate auth layer for local use; binding to `0.0.0.0` would expose file reads and URL fetches to the whole network. |
| `LAYA_TOKEN` | unset | Required only if you change the bind. The server **refuses to start** on a non-loopback address without it. |
| `LAYA_ALLOW_PRIVATE_URL` | unset | BYOK and portal URLs are checked against private ranges. A caller-supplied URL is an SSRF primitive otherwise. |
| `LAYA_PORTAL` | `https://laya.manef.dev` in a fresh install | Heartbeat is opt-out, not opt-in, because the registry is the point of the public page. Remove the line to stop it. |
| Driver auto-install | off | Needs administrator and a reboot; on an OEM laptop the vendor build is the tested one. `install.ps1 -InstallDriver` is deliberate. |

## What the heartbeat sends

Every five minutes, only when `LAYA_PORTAL` is set:

```json
{
  "id": "NPU-7K3M-2QXV",
  "version": "1.0",
  "os": "Windows",
  "machine": "AMD64",
  "capabilities": { "devices": [{"device": "NPU", "ready": true}], "byok": false }
}
```

No text, no prompts, no file paths, no hostname, no username, no keys. The ID is
`sha256("laya-npu:" + machine-id)` encoded into 8 characters, so it is stable across
reinstalls and not reversible to anything identifying.

To stop it: remove `LAYA_PORTAL` from `.env` and restart.

To **rotate the identity** — the supported way to unlink a machine — delete
`~/.laya-npu/device.json`, set any value for `LAYA_DEVICE_SALT`, and restart. The machine
reports under a new ID; the old record goes silent and cannot be tied to the new one.

To delete records on the server: `POST /api/devices/prune` with an `X-Admin-Key`, which
removes everything older than N days.

## Rate limits and size caps

| Route class | Limit | Body cap |
|---|---|---|
| ordinary `/api/*` | 120/min per client | 2 MB |
| audio (`/api/asr`, `/api/voice`) | 20/min | 60 MB |
| corpus and batch | 20/min | 2 MB |
| portal registration | 30/min per client | 64 KB |

Exceeding a rate limit returns 429 with `Retry-After`. Oversized bodies return 413 before
being read into memory.

## Known gaps

Stated plainly, because a security document that only lists strengths is not useful:

- **Unpinned dependencies.** The installer runs `pip install openvino ...` and
  `git+https://github.com/rupeshs/laya-openvino`. A lockfile with hashes and a checksum
  for the model download are not in place.
- **No CI or dependency scanning.** No Dependabot, no `pip-audit`, no secret scanning in
  the pipeline.
- **The portal trusts what it is told.** Any install may register any ID. That is by
  design — there is no account — but it means the registry is a presence indicator, not
  an identity. A known ID can be re-registered by anyone.
- **No CSP.** The app serves static files and JSON only, so the main XSS surface is the
  absence of a restrictive header rather than injected content.
- **Whisper and the ffmpeg path** process untrusted media. ffmpeg is a large parser
  surface; it runs as the same user with the same access as the app.
- **Windows only for the NPU path**, so the driver stack is outside this project's
  control.

## Supported versions

Only the current `main` is supported. This is a single-maintainer project with no
backport branches.
