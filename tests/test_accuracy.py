"""Accuracy harness. Every number in the README comes from here.

  python tests/test_accuracy.py            # all tasks
  python tests/test_accuracy.py doc_type   # one task

Exit code 1 if any task scores below its floor. The floors are the measured
scores minus one case, so a regression fails the run.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import tasks as T  # noqa: E402

GOLD = {
    "doc_type": [
        ("INVOICE #4411. Amount due: $2,400.00. Payment terms: net 30. Please remit to account 8821.", "invoice"),
        ("Payment received. Thank you for your purchase. Order 9912, total $84.20, paid by card ending 4412.", "receipt"),
        ("Hi, the app crashes every time I open settings. Can you help?", "support"),
        ("Quarterly newsletter: what shipped in Q3, upcoming events, team updates.", "other"),
        ("Bill to: Acme Corp. Invoice number INV-2026-0301. Due date 30 April. Total: $1,150.", "invoice"),
        ("Your payment of $59.00 was successful. Transaction ID TX-88213. Confirmation attached.", "receipt"),
        ("I cannot log in, password reset email never arrives. Need access urgently.", "support"),
        ("Reminder: the office will be closed on Monday for maintenance.", "other"),
        ("Statement of charges for March. Please pay the outstanding balance of $320 by Friday.", "invoice"),
        ("Thanks, we got your payment. Here is your receipt for $120.00 dated 12 March.", "receipt"),
        ("Getting a 500 error on checkout since this morning, customers cannot buy.", "support"),
        ("Announcing our new pricing page and a blog post about scaling.", "other"),
    ],
    "issue_type": [
        ("The app crashes when I click save. It worked yesterday.", "bug"),
        ("It would be great if you could add dark mode.", "feature"),
        ("How do I export my data to CSV?", "question"),
        ("Getting a 500 error on the checkout page since this morning.", "bug"),
        ("Please support SSO login with Okta.", "feature"),
        ("Where can I find the API documentation?", "question"),
        ("The button is misaligned on mobile Safari.", "bug"),
        ("Can you add a bulk delete option?", "feature"),
        ("What is the rate limit for the free tier?", "question"),
        ("Login fails with 'invalid token' after resetting password.", "bug"),
    ],
    "spam": [
        ("CONGRATULATIONS! You WON $1,000,000. Click here NOW to claim your prize!!!", "spam"),
        ("Hi team, the sprint review moved to Thursday 3pm, same room.", "legit"),
        ("Buy cheap viagra online, no prescription needed, limited offer", "spam"),
        ("Please find attached the invoice for September, due on the 30th.", "legit"),
        ("URGENT: your account will be suspended, verify your password immediately", "spam"),
        ("Thanks for the pull request, I left two comments on the auth module.", "legit"),
        ("Lose 10kg in 7 days with this one weird trick, doctors hate it", "spam"),
        ("The deploy finished, all health checks are green.", "legit"),
        ("Claim your free crypto airdrop, connect your wallet now", "spam"),
        ("Can we reschedule our 1:1 to Friday morning?", "legit"),
        ("Production is down, all users cannot log in. Need help immediately.", "legit"),
        ("Limited time offer: 90% off, click the link before it expires", "spam"),
    ],
    "priority": [
        ("Production is down, all users cannot log in.", "critical"),
        ("Typo in the settings page label.", "normal"),
        ("Data loss reported by three customers.", "critical"),
        ("The docs link points to an old version.", "normal"),
        ("Payment processing is failing for everyone.", "critical"),
        ("The footer year says 2024 instead of 2026.", "normal"),
        ("Security breach suspected, credentials leaked.", "critical"),
        ("Minor spacing issue in the dashboard header.", "normal"),
        ("Request to rename a column in the internal admin table.", "normal"),
    ],
    "sentiment": [
        ("This product is terrible, it broke after two days.", "negative"),
        ("Works exactly as described, very happy with it.", "positive"),
        ("Support never answered, I want a refund.", "negative"),
        ("Fast delivery and great build quality. Recommended.", "positive"),
        ("The app crashes constantly, completely unusable.", "negative"),
        ("Setup took two minutes, everything works perfectly.", "positive"),
        ("Worst purchase this year, do not buy.", "negative"),
        ("Exceeded my expectations, will buy again.", "positive"),
        ("Not what I expected, very disappointed.", "negative"),
        ("Beautiful design and the battery lasts all day.", "positive"),
    ],
    "commit_type": [
        ("Add dark mode toggle to the settings page", "feat"),
        ("Resolve crash when opening an empty project", "fix"),
        ("Update the installation guide for Windows users", "docs"),
        ("Implement CSV export for the reports table", "feat"),
        ("Correct off-by-one error in pagination", "fix"),
        ("Document the new environment variables", "docs"),
        ("Upgrade CI runner image to ubuntu-26.04", "chore"),
        ("Introduce SSO login with Okta", "feat"),
        ("Patch memory leak in the websocket handler", "fix"),
    ],
    "review_severity": [
        ("This will throw a null pointer if the session is missing. Needs a guard before merge.", "blocking"),
        ("Nit: could rename this variable to be clearer.", "suggestion"),
        ("Consider extracting this into a helper function.", "suggestion"),
        ("This breaks the public API contract, existing clients will fail.", "blocking"),
        ("Maybe add a comment explaining the magic number.", "suggestion"),
        ("Race condition: two writes can interleave and corrupt the row.", "blocking"),
        ("I would prefer early returns here, but it is fine either way.", "suggestion"),
        ("Credentials are logged in plaintext on this line.", "blocking"),
        ("Minor style: use const instead of let.", "suggestion"),
    ],
}

# measured score minus one, so a single regression fails the run
FLOOR = {
    "doc_type": 11,
    "issue_type": 9,
    "spam": 8,
    "priority": 8,
    "sentiment": 9,
    "commit_type": 8,
    "review_severity": 8,
}


def engine():
    env = dict(os.environ)
    model = env.get("LAYA_MODEL") or os.path.expanduser("~/models/laya-ov-int8")
    env["LAYA_MODEL"] = model
    os.environ.update(env)
    from npu_server import Engine
    return Engine(model, env.get("LAYA_DEVICE", "NPU"))


def main(argv):
    only = argv[1] if len(argv) > 1 else None
    e = engine()
    print(f"device: {e.device}\n")

    failed = []
    for task_id, rows in GOLD.items():
        if only and task_id != only:
            continue
        spec = T.TASKS[task_id]
        q = {task_id: {"type": "choice", "instructions": spec["instructions"],
                       "criteria": spec["criteria"]}}
        hit = 0
        misses = []
        for text, want in rows:
            out = e.system_one({"text": text}, q)
            got = out["answers"][task_id]["choice"]
            if got == want:
                hit += 1
            else:
                misses.append((text[:48], got, want))

        floor = FLOOR.get(task_id, len(rows))
        status = "ok  " if hit >= floor else "FAIL"
        print(f"{status} {task_id:16s} {hit}/{len(rows)}  (floor {floor})")
        for text, got, want in misses:
            print(f"       miss: got {got!r} want {want!r}  {text!r}")
        if hit < floor:
            failed.append(task_id)

    if failed:
        print(f"\nfailed: {', '.join(failed)}")
        return 1
    print("\nall tasks above floor")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
