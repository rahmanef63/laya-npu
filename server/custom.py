"""Custom-question endpoint and the RPA decision pipeline.

The model answers typed questions. This module owns everything else: thresholds,
readiness checks, rule precedence, workflow mapping, idempotency.

  POST /api/custom   {state, questions:{id:{type,instructions,criteria}}}
  POST /api/rpa      {state, question, workflows, checks, rules}
"""
from __future__ import annotations

import time


def _p(a):
    if not a:
        return 0.0
    t = a.get("type")
    if t == "choice":
        return a["probabilities"][a["choice"]]
    if t == "noul":
        return a["noul"]
    return a.get("confidence", 0.0)


def _summary(qid, q, a):
    t = a.get("type")
    out = {"id": qid, "type": t,
           "label": qid.replace("_", " "),
           "instructions": q.get("instructions", "")}
    if t == "choice":
        probs = a.get("probabilities") or {}
        ranked = sorted(probs.items(), key=lambda kv: -kv[1])
        out.update({
            "value": a.get("choice"),
            "probability": probs.get(a.get("choice"), 0.0),
            "ranked": [{"name": k, "p": v} for k, v in ranked],
        })
    elif t == "score":
        scale = q.get("criteria") or []
        score = float(a.get("score", 0))
        idx = max(0, min(int(round(score)), len(scale) - 1)) if scale else 0
        out.update({
            "value": round(score, 2),
            "scale": scale,
            "level": scale[idx] if scale else None,
            "max": max(0, len(scale) - 1),
            "probability": a.get("confidence", 0.0),
            "probabilities": a.get("probabilities") or {},
        })
    else:
        out.update({"value": a.get("noul", 0.0) >= 0.5,
                    "probability": a.get("noul", 0.0)})
    return out


def normalise_questions(raw):
    """Accept the form shape and turn it into Jev System One questions."""
    out = {}
    for qid, q in (raw or {}).items():
        t = q.get("type")
        if t == "choice":
            crit = q.get("criteria") or {}
            if isinstance(crit, list):
                crit = {str(c): str(c) for c in crit}
            if len(crit) < 2 or len(crit) > 8:
                raise ValueError(f"{qid}: choice needs 2-8 options, got {len(crit)}")
            out[qid] = {"type": "choice",
                        "instructions": str(q.get("instructions", ""))[:600],
                        "criteria": {str(k)[:80]: str(v)[:400] for k, v in crit.items()}}
        elif t == "score":
            crit = q.get("criteria") or []
            if not isinstance(crit, list) or len(crit) < 2 or len(crit) > 8:
                raise ValueError(f"{qid}: score needs 2-8 levels")
            out[qid] = {"type": "score",
                        "instructions": str(q.get("instructions", ""))[:600],
                        "criteria": [str(c)[:300] for c in crit]}
        elif t == "noul":
            row = {"type": "noul",
                   "instructions": str(q.get("instructions", ""))[:600]}
            crit = q.get("criteria")
            if isinstance(crit, dict) and ("true" in crit or "false" in crit):
                row["criteria"] = {"true": str(crit.get("true", ""))[:300],
                                   "false": str(crit.get("false", ""))[:300]}
            out[qid] = row
        else:
            raise ValueError(f"{qid}: unknown question type {t!r}")
    return out


def run_custom(engine, state_text, raw_questions, state_key="state"):
    """One request per question: the NPU is faster that way."""
    questions = normalise_questions(raw_questions)
    if not questions:
        raise ValueError("at least one question required")

    state = {state_key: str(state_text)[:20000]}
    answers, raw = {}, {}
    t0 = time.perf_counter()
    for qid, q in questions.items():
        a = engine.system_one(state, {qid: q})["answers"][qid]
        raw[qid] = a
        answers[qid] = _summary(qid, q, a)
    ms = (time.perf_counter() - t0) * 1000

    return {
        "answers": [answers[k] for k in questions],
        "raw": raw,
        "ms": round(ms, 1),
        "per_question_ms": round(ms / max(len(questions), 1), 1),
        "device": engine.device,
        "questions": len(questions),
    }


# --------------------------------------------------------------- RPA policy

RULE_TEXT = {
    1: "Input or model response failed schema validation.",
    2: "An existing invoice or completed idempotent operation was found.",
    3: "Supplier or purchase-order lookup failed, or a business exception was detected.",
    4: "Required fields are incomplete.",
    5: "Routing confidence is below the configured threshold.",
    6: "All checks passed.",
}


def run_rpa(engine, payload):
    """Model picks a workflow; application rules decide the final route.

    Returns a preview object. Nothing is dispatched: this is simulation only.
    """
    state_text = str(payload.get("state") or "")[:20000]
    question = str(payload.get("question") or "Which approved workflow should handle this task?")[:600]
    workflows = payload.get("workflows") or []
    checks = payload.get("checks") or []
    rules = payload.get("rules") or {}

    if len(workflows) < 2:
        raise ValueError("at least two allowed workflows required")
    wf_crit = {str(w["value"])[:80]: str(w.get("condition", w["value"]))[:400]
               for w in workflows}

    # ---- model: routing choice, then each readiness check ----
    state = {"state": state_text}
    t0 = time.perf_counter()

    route = engine.system_one(state, {"workflow": {
        "type": "choice", "instructions": question, "criteria": wf_crit}})
    route_a = route["answers"]["workflow"]
    selected = route_a["choice"]
    confidence = route_a["probabilities"][selected]
    probs = route_a["probabilities"]

    check_results = []
    for chk in checks:
        if not chk.get("enabled", True):
            check_results.append({**chk, "status": "not_evaluated",
                                  "yes_probability": None, "passed": None})
            continue
        qid = chk["id"]
        q = {"type": "noul",
             "instructions": str(chk.get("question", ""))[:600],
             "criteria": {"true": str(chk.get("trueWhen", ""))[:300] or "condition holds",
                          "false": str(chk.get("falseWhen", ""))[:300] or "condition does not hold"}}
        a = engine.system_one(state, {qid: q})["answers"][qid]
        p = float(a.get("noul", 0.0))
        thr = float(chk.get("threshold", 0.5))
        passed = p >= thr
        check_results.append({
            **chk,
            "yes_probability": round(p, 4),
            "passed": passed,
            "status": "passed" if passed else "failed",
        })

    ms = (time.perf_counter() - t0) * 1000

    # ---- application rules, in the documented order ----
    trace = []
    final = selected
    rule_no, rule_msg = 6, RULE_TEXT[6]
    dispatch_ok = True

    def trip(n, extra=""):
        nonlocal final, rule_no, rule_msg
        rule_no, rule_msg = n, RULE_TEXT[n] + ((" " + extra) if extra else "")

    # 2: existing record
    if payload.get("existingRecordFound"):
        final = "create_invoice_draft"
        trip(2, "Returning the existing result instead of creating a duplicate.")
        dispatch_ok = False

    # 3: lookups / business exception
    elif payload.get("lookupFailed") or any(
        c["id"] == "business_exception_present" and c.get("passed") for c in check_results
    ):
        final = "manual_review"
        trip(3)

    # 4: required fields
    elif any(c["id"] == "required_fields_present" and c.get("passed") is False
             for c in check_results):
        final = "request_missing_information"
        trip(4)

    # 5: confidence
    elif confidence < float(rules.get("minConfidence", 0.85)):
        final = "manual_review"
        trip(5, f"Confidence {confidence:.2f} < {rules.get('minConfidence', 0.85):.2f}.")

    trace = [
        {"at": "input", "status": "ok", "message": "Input parsed and bounded"},
        {"at": "lookups", "status": "ok" if not payload.get("lookupFailed") else "failed",
         "message": "Supplier, purchase order and duplicate lookups supplied by the caller"},
        {"at": "model", "status": "ok",
         "message": f"Routed to {selected} at confidence {confidence:.3f}"},
        {"at": "checks", "status": "ok",
         "message": f"{sum(1 for c in check_results if c.get('status') == 'failed')} of "
                    f"{len(check_results)} readiness checks failed"},
        {"at": "rules", "status": "ok", "message": f"Rule {rule_no}: {rule_msg}"},
        {"at": "handoff", "status": "simulated", "message": "Simulation mode: nothing dispatched"},
    ]

    missing = []
    low = state_text.lower()
    if "invoice date" not in low and "invoice_date" not in low:
        missing.append("invoice_date")

    return {
        "mode": "simulation",
        "decision": {
            "selected_workflow": selected,
            "routing_confidence": round(confidence, 4),
            "probabilities": {k: round(v, 4) for k, v in sorted(probs.items(), key=lambda kv: -kv[1])},
        },
        "checks": [{
            "id": c["id"],
            "label": c.get("label", c["id"].replace("_", " ")),
            "status": c.get("status"),
            "yes_probability": c.get("yes_probability"),
            "threshold": c.get("threshold"),
            "on_failure": c.get("onFailure"),
        } for c in check_results],
        "policy": {
            "final_workflow": final,
            "rule": rule_no,
            "rule_text": rule_msg,
            "execution_eligible": dispatch_ok,
            "dispatched": False,
            "dispatch_note": "Simulation mode",
        },
        "handoff": {
            "workflow_id": (payload.get("mapping") or {}).get(final, final),
            "input": {
                "invoice_id": _field(state_text, "Invoice ID"),
                "supplier": _field(state_text, "Supplier"),
                "purchase_order": _field(state_text, "Purchase order"),
                "amount": _field(state_text, "Amount"),
                "missing_fields": missing,
            },
            "idempotency_key": _idempotency(payload.get("idempotencyKey") or
                                            "{{supplier_id}}:{{invoice_id}}", state_text),
        },
        "trace": trace,
        "ms": round(ms, 1),
        "per_question_ms": round(ms / max(len(check_results) + 1, 1), 1),
        "device": engine.device,
        "schema_note": "Application preview format; not a native JEV API response.",
    }


def _field(text, name):
    """Cheap labelled-field read. The connector owns real extraction; this only
    echoes what the caller already supplied."""
    for line in text.splitlines():
        if line.lower().startswith(name.lower() + ":"):
            return line.split(":", 1)[1].strip()
    return None


def _idempotency(template, text):
    return (template
            .replace("{{invoice_id}}", _field(text, "Invoice ID") or "")
            .replace("{{supplier_id}}", (_field(text, "Supplier") or "").lower()
                     .replace(" ", "-"))
            .strip(":"))
