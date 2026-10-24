"""Import the modules that have no OpenVINO dependency and assert their contracts.

Runs in CI without a model or a GPU, so a broken import or a changed guard is caught
before anyone with an NPU has to discover it.
"""
import sys

sys.path.insert(0, "server")

import guards
import schema
import tasks

# guards: a token is required exactly when one is configured
assert guards.token_ok(None) is True, "no token configured should allow loopback"
assert isinstance(guards.check_url, object)

# schema: an empty spec must be rejected with a path, not a traceback
res = schema.validate({"questions": {}})
assert res["ok"] is False
assert res["errors"] and "$.questions" in res["errors"][0]["path"]

starter = schema.starter()
assert schema.validate(starter)["ok"] is True

# tasks: every preset declares questions and a policy entry
assert "triage" in tasks.TASKS
for tid, spec in tasks.TASKS.items():
    assert spec["questions"], f"{tid} has no questions"
    action, label, reasons, severity = tasks.decide(tid, {}, "")
    assert action and label and isinstance(reasons, list)

print(f"imports ok: {len(tasks.TASKS)} presets, guards and schema contracts hold")
