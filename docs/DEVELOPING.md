# Developing

For anyone who wants to change something. Takes about ten minutes to a running dev
environment, assuming the installer has already fetched the model.

## 1. Get the code

```bash
git clone https://github.com/rahmanef63/laya-npu
cd laya-npu
```

## 2. Install the runtime once

The model, OpenVINO and the static IR are the slow part, so let the installer do them:

```bash
# Windows
install.cmd

# WSL or Linux
./install.sh
```

That leaves you with `~/.laya-npu` state, a model in `~/models/laya-ov-int8`, and a working
`.env`. You do not need to repeat it when you change code.

## 3. Run the API

```bash
# Windows
laya-npu.cmd

# Linux / WSL
./start.sh
```

It listens on `http://localhost:8649`. First start compiles the graph: ~18 s on the NPU,
~4 s on the GPU. Cached afterwards in `models/.ovcache`.

## 4. Run the UI in dev mode

Second terminal:

```bash
npm install
npm run dev
```

`http://localhost:5173` — hot reload, and `/api/*` is proxied to `127.0.0.1:8649` so you
see real data.

Point the proxy elsewhere when the API is not on loopback:

```bash
# WSL: the API runs on the Windows host, not inside the VM
LAYA_API="http://$(ip route show default | awk '{print $3}'):8649" npm run dev

# a remote box
LAYA_API=http://192.168.1.20:8649 npm run dev
```

**If the API sets `LAYA_TOKEN`**, the browser needs it too. The built app gets it inlined as
a meta tag by `web.py`; dev mode has no such tag. Either develop against a token-less
loopback API (simplest, and the default), or run the Python server and browse 8649
directly instead of using Vite.

Verified both ways: proxy returns 401 without a token and real task data with one.

## What you can change without the model

Most of the UI, the portal, the schema compiler and the guards need no model at all:

```bash
npm run dev                  # UI, with the API proxied
python scripts/check-imports.py   # guards, schema and task contracts, no model
```

`make lint` is the same gate CI runs: Python syntax, ruff, and `svelte-check`. It takes
about 20 seconds and catches most mistakes.

## What needs the model

```bash
python tests/test_policy.py     # presets end to end, asserts the final action
python tests/test_accuracy.py   # classification, including the tasks that fail
python tests/bench_backends.py  # re-measure latency
```

There is no mocked model. That is deliberate: a stub would let accuracy regressions
through, which is the exact failure this project exists to avoid.

`test_accuracy.py` includes tasks that fail on purpose — shell-command gating scores 12/18
and log severity 5/10. They document the limits. Do not make them pass by loosening the
test.

## Frontend conventions

- **Monochrome.** `#000` page, white accent, grayscale everything. No colour to
  distinguish data; the design carries that weight.
- **Dense, not spacious.** 11–13px text, 5–6px radii, hairline borders. This is a
  developer tool, not a landing page.
- **One view per section.** Each fills the viewport. Nothing autoscrolls; tall content
  scrolls inside its own panel.
- **Tailwind utilities, no component library.** A control used twice is a component in
  `src/lib/`; used once, it stays inline.
- **Numbers come from `measured.ts`.** Never hardcode a latency in a view.

## Backend conventions

- **stdlib over dependencies.** The server has no framework. `http.server` is enough for
  one process with a handful of routes.
- **Fail closed.** Unknown task id, missing model, private URL, oversized body: refuse with
  a clear message rather than guessing.
- **No silent fallbacks.** If the NPU is missing we do not quietly call a cloud provider.
  The user picks a backend and sees which one ran.
- **Bound the input.** Every route that reads a body has a cap; every route that takes a
  path resolves it against an allowlist.

## Adding a preset

`tasks.py` is the whole surface. A preset is a dict of typed questions plus an entry in
`decide()`:

```python
MY_TASK = {
    "id": "my_task",
    "label": "My task",
    "blurb": "What it is for, in one line.",
    "state_key": "text",
    "placeholder": "A realistic example to prefill the form.",
    "questions": {
        "kind": {"type": "choice", "instructions": "Which kind is `text`?",
                 "criteria": {"a": "condition for a", "b": "condition for b"}},
    },
}
```

Then add a branch in `decide(task_id, answers, text)` that maps the answers to an action.
Write it as plain Python. Do not ask the model for the action.

Add a case to `tests/test_policy.py` with a text and the action you expect.

## Adding an endpoint

1. Handler in `server/web.py`, routed in `do_GET` or `do_POST`.
2. Auth and rate limit come from `guards.py` automatically for `/api/*`.
3. Body cap: pick `MAX_JSON_BYTES` or `MAX_AUDIO_BYTES`.
4. Caller-supplied URL or path? Run it through `guards.check_url` or `corpus.resolve_dir`.
5. Client method in `src/lib/http.ts`, never a bare `fetch` in a view — otherwise the
   access token is not applied.

## Adding a UI section

Two files and one mapping:

1. `src/lib/registry.ts` — an entry with `id`, `label`, `icon`, `group`.
2. `src/lib/views/MyThing.svelte` — wrap the content in `<View title=... >`.
3. `src/routes/+page.svelte` — import it and add it to `VIEWS`.

Run `npm run dev` and click it. If it shows "No view registered", you missed step three —
that message exists because the opposite bug was shipped once.

## Checking a change

Before opening a PR:

```bash
make lint      # syntax, ruff, svelte-check  (fast, no model)
make test      # policy and accuracy          (needs the model)
```

Both are what CI runs. If `make test` fails on a task you did not touch, check whether it
is one of the documented failures before assuming you broke it.

## Where things live

See [ARCHITECTURE.md](ARCHITECTURE.md) for the module map, the wire format, and the three
NPU quirks that will otherwise waste your afternoon.
