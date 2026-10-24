# Architecture

How the pieces fit. Read this before changing anything structural.

## The shape

```
┌─────────────────────────────────────────────────────────┐
│  browser                                                │
│  SvelteKit SPA, built to web/dist, served by web.py     │
└───────────────────────────┬─────────────────────────────┘
                            │  /api/*  (JSON, or raw audio)
┌───────────────────────────▼─────────────────────────────┐
│  server/web.py           one HTTP process, stdlib only  │
│    ├── guards.py         auth, rate limit, body caps    │
│    ├── backends.py       NPU / GPU / CPU / BYOK         │
│    ├── tasks.py          presets + policy layer         │
│    ├── custom.py         user-defined questions, RPA    │
│    ├── asr.py            Whisper, any audio format      │
│    ├── pipeline.py       audio -> decision              │
│    ├── corpus.py         directory scan, PDF extract    │
│    ├── schema.py         user format -> wire payload    │
│    ├── device.py         device ID, heartbeat           │
│    └── npu_driver.py     driver detection               │
└───────────────────────────┬─────────────────────────────┘
                            │  OpenVINO runtime
┌───────────────────────────▼─────────────────────────────┐
│  Intel NPU / iGPU / CPU      static-shape INT8 graphs   │
└─────────────────────────────────────────────────────────┘
```

One process. There is no second port, no worker queue, no database for the app itself.
The only state on disk is `~/.laya-npu/device.json` (identity) and the compiled kernel
cache in `models/*/.ovcache`.

The portal is a **separate** small service (`portal/`), deployed independently at
laya.manef.dev. It shares nothing with the app except the heartbeat wire format.

## Why the model does not choose the action

This is the single most important design decision and the one most likely to be
"fixed" by a well-meaning contributor. Do not.

Asking the decision model *"what action should handle this?"* scores **2/12** on our own
test set. Asking its preset questions and deriving the action in Python scores **22/22**.

A 421M classifier reads text well and knows your business policy not at all. It does not
know that a refund needs approval and a receipt does not.

So the split is:

```
perception  (model)  ->  probabilities
policy      (python) ->  action
```

`tasks.py` holds the policy as a plain dict and a few `if` statements. Change the Python,
not the model.

## Backends

`backends.py` presents one interface over four things:

| id | what it is |
|---|---|
| `local:npu` | OpenVINO on Intel AI Boost |
| `local:gpu` | OpenVINO on the iGPU |
| `local:cpu` | OpenVINO on CPU |
| `byok` | a remote endpoint speaking Jev System One |

`backend_for(id)` returns `(backend, device)`. Both `LocalBackend` and `ByokBackend` expose
`system_one(state, questions)`, which is the only contract the rest of the server uses.

**NPU requires a static graph.** The installer reshapes the IR to `[1, 256]` and the
marker axis to `[1, 8]`, because the NPU rejects dynamic shapes outright. Three things
that bite anyone touching this:

1. The traced IR names `attention_mask` **`"120"`**. Read input names from the model, never
   assume them.
2. Tensors must be *exactly* the declared size, not "at most". Everything is padded.
3. Batching is slower on the NPU, not faster: 69 ms/query at 3 rows vs 51 ms at 1. The
   server sends one question per request on purpose.

## The wire format

Jev System One, so any compatible client can talk to us.

```json
{
  "state": { "message": "text to decide about" },
  "questions": {
    "intent": {
      "type": "choice",
      "instructions": "What does the customer want in `message`?",
      "criteria": { "refund": "money returned", "technical_help": "a bug" }
    }
  }
}
```

Answers carry probabilities, never prose. Three question types: `choice` (pick one),
`score` (ordinal position), `noul` (P(yes)).

## Frontend

SvelteKit 3, static adapter, Tailwind 4. No component library — every control is written
in the file that uses it.

```
src/routes/+page.svelte    the shell: header, dynamic menu, one view
src/lib/registry.ts        the sidebar list; adding an entry adds a page
src/lib/views/*.svelte     one component per section
src/lib/http.ts            fetch wrapper, applies the access token
src/lib/measured.ts        the only place performance numbers live
src/lib/View.svelte        shared page frame (heading, scrollable body)
```

**Adding a section** is two edits: an entry in `registry.ts` and a component in `views/`,
then map the id in `VIEWS` in `+page.svelte`. If the id is missing from `VIEWS` the page
shows an explicit error instead of silently rendering the wrong view — that bug existed
once and is now guarded.

## Things that will trip you up

| Symptom | Cause |
|---|---|
| `LAYA_MODEL not set` | `.env` has a BOM. Windows PowerShell 5.1 writes one with `-Encoding UTF8`. |
| NPU compile fails | dynamic shapes, or a driver older than the OpenVINO runtime |
| `Infer Request is busy` | two requests at once. There is one infer request per device. |
| 401 on every API call | `LAYA_TOKEN` is set but the browser has no token. The shell inlines it as a meta tag; a static `index.html` will not. |
| `npm run dev` shows 404 on /api | the Python server is not running on 8649, or `LAYA_API` points elsewhere |
| Numbers in the UI disagree | someone edited a view instead of `measured.ts` |
