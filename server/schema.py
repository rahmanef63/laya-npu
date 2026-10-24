"""Schema compiler: turn a user's own format into a Jev System One payload.

The user writes a small declarative spec (JSON or YAML-shaped), the compiler
validates it, maps it onto the wire format, and can emit a runnable script.

    {
      "name": "invoice-triage",
      "state": { "text": "{{document}}" },          # template over input
      "questions": {
        "workflow": {
          "type": "choice",
          "instructions": "Which workflow?",
          "options": { "draft": "...", "review": "..." }   # or "criteria"
        },
        "urgent": { "type": "noul", "instructions": "..." }
      },
      "policy": [ {"when": "workflow == review", "action": "escalate"} ]
    }

Nothing here runs the model. It produces the request body and a script the user
can keep, so the format is portable to any Jev-compatible endpoint.
"""
from __future__ import annotations

import json
import re

TYPES = ("choice", "score", "noul")
MAX_OPTIONS = 8
MAX_LEVELS = 8
NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def _err(path: str, msg: str):
    return {"path": path, "message": msg}


def validate(spec: dict) -> dict:
    """Return {ok, errors[], warnings[], normalised}. Never raises."""
    errors: list[dict] = []
    warnings: list[dict] = []

    if not isinstance(spec, dict):
        return {"ok": False, "errors": [_err("$", "spec must be an object")],
                "warnings": [], "normalised": None}

    questions = spec.get("questions")
    if not isinstance(questions, dict) or not questions:
        errors.append(_err("$.questions", "at least one question is required"))
        return {"ok": False, "errors": errors, "warnings": warnings,
                "normalised": None}

    norm_questions: dict[str, dict] = {}
    for qid, q in questions.items():
        base = f"$.questions.{qid}"
        if not NAME_RE.match(str(qid)):
            errors.append(_err(base, "id must match [A-Za-z0-9_.-], max 64 chars"))
            continue
        if not isinstance(q, dict):
            errors.append(_err(base, "question must be an object"))
            continue

        qtype = q.get("type")
        if qtype not in TYPES:
            errors.append(_err(f"{base}.type", f"must be one of {', '.join(TYPES)}"))
            continue

        instructions = q.get("instructions")
        if not isinstance(instructions, str) or not instructions.strip():
            errors.append(_err(f"{base}.instructions", "required, non-empty string"))
            continue
        if len(instructions) > 600:
            warnings.append(_err(f"{base}.instructions",
                                 "longer than 600 chars; the server truncates"))
        if "`" not in instructions:
            warnings.append(_err(f"{base}.instructions",
                                 "the checkpoint was trained with references in backticks, "
                                 "e.g. `message` — consider naming the field"))

        row: dict = {"type": qtype, "instructions": instructions.strip()[:600]}

        if qtype == "choice":
            opts = q.get("options") or q.get("criteria")
            if isinstance(opts, list):
                opts = {str(o): str(o) for o in opts}
            if not isinstance(opts, dict):
                errors.append(_err(f"{base}.options",
                                   "expected an object {value: when-to-choose}"))
                continue
            if not 2 <= len(opts) <= MAX_OPTIONS:
                errors.append(_err(f"{base}.options",
                                   f"needs 2-{MAX_OPTIONS} options, got {len(opts)}"))
                continue
            clean = {}
            for k, v in opts.items():
                if not NAME_RE.match(str(k)):
                    errors.append(_err(f"{base}.options.{k}",
                                       "value must match [A-Za-z0-9_.-]"))
                    continue
                if not isinstance(v, str) or not v.strip():
                    errors.append(_err(f"{base}.options.{k}", "condition must be text"))
                    continue
                clean[str(k)] = v.strip()[:400]
            row["criteria"] = clean

        elif qtype == "score":
            levels = q.get("levels") or q.get("criteria")
            if not isinstance(levels, list):
                errors.append(_err(f"{base}.levels", "expected an ordered array"))
                continue
            if not 2 <= len(levels) <= MAX_LEVELS:
                errors.append(_err(f"{base}.levels",
                                   f"needs 2-{MAX_LEVELS} levels, got {len(levels)}"))
                continue
            if not all(isinstance(x, str) and x.strip() for x in levels):
                errors.append(_err(f"{base}.levels", "every level must be non-empty text"))
                continue
            row["criteria"] = [x.strip()[:300] for x in levels]

        else:  # noul
            cond = q.get("conditions") or {}
            if isinstance(cond, dict):
                t = str(cond.get("true", "") or "").strip()
                f = str(cond.get("false", "") or "").strip()
                if t or f:
                    row["criteria"] = {"true": t[:300] or "condition holds",
                                       "false": f[:300] or "condition does not hold"}

        norm_questions[qid] = row

    state = spec.get("state")
    if state is not None and not isinstance(state, (dict, str)):
        errors.append(_err("$.state", "must be an object or a string template"))

    policy = spec.get("policy")
    if policy is not None:
        if not isinstance(policy, list):
            errors.append(_err("$.policy", "must be an array"))
        else:
            for i, rule in enumerate(policy):
                if not isinstance(rule, dict):
                    errors.append(_err(f"$.policy[{i}]", "rule must be an object"))
                    continue
                if "when" not in rule:
                    errors.append(_err(f"$.policy[{i}].when",
                                       "required, e.g. \"workflow == review\""))
                if "action" not in rule:
                    errors.append(_err(f"$.policy[{i}].action", "required"))

    normalised = {
        "name": str(spec.get("name") or "untitled")[:64],
        "state": state if state is not None else {"text": "{{input}}"},
        "questions": norm_questions,
        "policy": policy or [],
        "model": str(spec.get("model") or "jev"),
    }

    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "normalised": normalised if not errors else None}


def compile_payload(spec: dict, state_text: str = "", state_key: str = "text") -> dict:
    """Build the wire body. A {{input}} / {{document}} placeholder is replaced."""
    res = validate(spec)
    if not res["ok"]:
        raise ValueError("; ".join(f"{e['path']}: {e['message']}" for e in res["errors"]))
    n = res["normalised"]

    state = n["state"]
    if isinstance(state, str):
        rendered = {"text": _fill(state, state_text)}
    else:
        rendered = {k: (_fill(v, state_text) if isinstance(v, str) else v)
                    for k, v in state.items()}

    return {
        "model": n["model"],
        "state": rendered,
        "questions": n["questions"],
        "_meta": {"name": n["name"], "policy": n["policy"],
                  "state_key": state_key,
                  "warnings": [w["message"] for w in res["warnings"]]},
    }


_PLACEHOLDER = re.compile(r"\{\{\s*(input|document|state|text)\s*\}\}")


def _fill(value: str, text: str) -> str:
    return _PLACEHOLDER.sub(text, value)


def emit_script(spec: dict, endpoint: str = "http://localhost:8649") -> str:
    """A standalone Python client for this spec. Runs anywhere with the stdlib."""
    res = validate(spec)
    if not res["ok"]:
        raise ValueError("invalid spec")
    n = res["normalised"]
    body = {
        "state": n["state"],
        "questions": n["questions"],
    }
    template = json.dumps(body, indent=2)
    tmpl = template.replace("{{input}}", "__INPUT__").replace("{{document}}", "__INPUT__")

    return f'''#!/usr/bin/env python3
"""Generated from a laya-npu spec: {n["name"]}

  python {n["name"].replace(" ", "-")}.py "text to classify"

Speaks Jev System One, so it works against the local server, a hosted
deployment, or any compatible endpoint. Stdlib only.
"""
import json
import sys
import urllib.request

ENDPOINT = {endpoint!r}
API_KEY = ""                      # set for a hosted endpoint

TEMPLATE = """{tmpl}"""

QUESTIONS = {json.dumps(n["questions"], indent=2)}

POLICY = {json.dumps(n["policy"], indent=2)}


def build_state(text: str) -> dict:
    body = json.loads(TEMPLATE.replace("__INPUT__", json.dumps(text)))
    return body


def call(state: dict) -> dict:
    payload = json.dumps({{"state": state, "questions": QUESTIONS,
                          "model": {n["model"]!r}}}).encode()
    headers = {{"Content-Type": "application/json"}}
    if API_KEY:
        headers["Authorization"] = f"Bearer {{API_KEY}}"
    req = urllib.request.Request(ENDPOINT + "/v1/systemone",
                                 data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def apply_policy(answers: dict) -> str:
    """Deliberately tiny: a condition like `workflow == review` compares the
    reported value. Anything more complex belongs in your own code."""
    for rule in POLICY:
        cond = str(rule.get("when", ""))
        if "==" in cond:
            left, right = [x.strip() for x in cond.split("==", 1)]
            got = answers.get(left, {{}})
            value = got.get("choice") if isinstance(got, dict) else got
            if str(value) == right:
                return rule.get("action")
    return POLICY[-1].get("action") if POLICY else "none"


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) or "replace with your input"
    data = call(build_state(text))
    answers = data.get("answers", {{}})
    print(json.dumps(answers, indent=2))
    if POLICY:
        print("action:", apply_policy(answers))
'''


def starter(name: str = "my-decision") -> dict:
    """A complete, valid example the UI can prefill."""
    return {
        "name": name,
        "state": {"text": "{{input}}"},
        "questions": {
            "workflow": {
                "type": "choice",
                "instructions": "Which workflow should handle `text`?",
                "options": {
                    "auto": "routine, safe to process without a human",
                    "review": "needs a person before anything happens",
                },
            },
            "urgent": {
                "type": "noul",
                "instructions": "Does `text` communicate a deadline or time pressure?",
            },
        },
        "policy": [
            {"when": "workflow == review", "action": "escalate"},
            {"when": "urgent == True", "action": "escalate"},
            {"when": "workflow == auto", "action": "process"},
        ],
        "model": "jev",
    }
