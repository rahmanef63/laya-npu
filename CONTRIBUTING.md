# Contributing

Thanks for looking. This is a small project with a narrow purpose: run a decision model
and a speech model on Intel NPU hardware, locally, without a cloud dependency.

## Before you start

```bash
git clone https://github.com/rahmanef63/laya-npu
cd laya-npu
```

- **Windows** for the NPU path: `install.cmd`, then `laya-npu.cmd`.
- **WSL or Linux**: `./install.sh`. No NPU is reachable there, so it runs CPU and BYOK.

You need Python 3.10+ and Node 20+. The installer handles both if they are missing.

## Running the tests

Two harnesses, both of which need a working model:

```bash
python tests/test_policy.py       # presets end to end, asserts the final action
python tests/test_accuracy.py     # classification tasks, including the ones that fail
python tests/bench_backends.py    # re-measures the numbers in src/lib/measured.ts
```

There is no mocked model. If `LAYA_MODEL` is not set the tests use
`~/models/laya-ov-int8`. That is intentional: a stub would let accuracy regressions
through, which is the failure mode this project exists to avoid.

`tests/test_accuracy.py` includes tasks that **fail** — shell-command gating scores
12/18, log severity 5/10. They are in the repo to document the limits. Do not "fix" the
test to make them pass.

## Making a change

1. Open an issue first for anything larger than a typo. It saves you building something
   that gets rejected.
2. Keep the diff small. Deletion beats addition.
3. Match the surrounding style. Python here is stdlib-heavy, no framework, and the same
   for the server. TypeScript is strict, Tailwind utilities, no component library.
4. If you change a number that appears in the UI, change it in
   `src/lib/measured.ts`, not in the view.

## Things this project will not accept

- **Cloud fallbacks.** If a request cannot be answered locally, it fails. Adding a
  provider as a silent fallback defeats the point.
- **Removing the honest limits.** The English-only restriction, the 256-token cap and
  the "do not use for security decisions" note are load-bearing.
- **A model that picks the action.** It scores 2/12 at that. The policy layer is plain
  Python on purpose; see the README.
- **Telemetry.** There is one outbound request, the device heartbeat, and it is
  documented and opt-out. Nothing else phones home.

## Security

Do not open a public issue for a vulnerability. See [SECURITY.md](SECURITY.md).

## Commit messages

Describe what changed and why, in the imperative. If you fixed a bug, say what it did to
the user, not which line moved. Reference an issue number when there is one.

## Licence

Contributions are accepted under Apache-2.0, the licence of the project.
