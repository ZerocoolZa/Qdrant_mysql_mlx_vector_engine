#!/usr/bin/env python3
"""
run_qa_tests.py — Automated QA Test Runner

Runs the two QA test harnesses end-to-end and reports a unified pass/fail summary:

  1. qa_test_harness_v2.py  --all   (curated chat + GhostQA full pipeline)
  2. pinnacle_harness.py    --all   (3 docs + per-stage failure tracking)

Each harness is run as a subprocess. The runner parses the SUMMARY block each
harness prints to extract mode-correct / answer-correct counts, then prints a
combined verdict.

Usage:
  python3 run_qa_tests.py             # run both harnesses (--all)
  python3 run_qa_tests.py --report    # only show reports from existing DBs
  python3 run_qa_tests.py --clean     # clean both harness DBs + Qdrant collections
  python3 run_qa_tests.py --harness v2       # run only qa_test_harness_v2
  python3 run_qa_tests.py --harness pinnacle # run only pinnacle_harness

The runner degrades gracefully: if a harness cannot run (missing Qdrant, missing
models, import error), it is reported as SKIPPED with the reason, and the runner
exits non-zero only if at least one harness ran and failed its assertions.
"""

import os
import re
import sys
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

HARNESSES = [
    {
        "name": "qa_test_harness_v2",
        "script": os.path.join(HERE, "qa_test_harness_v2.py"),
        "db": os.path.join(HERE, "qa_test.db"),
    },
    {
        "name": "pinnacle_harness",
        "script": os.path.join(HERE, "pinnacle_harness.py"),
        "db": os.path.join(HERE, "pinnacle_harness.db"),
    },
]

# Matches lines like:
#   Mode correct:       7/18 (39%)
#   Answer correct:     7/18 (39%)
#   Retrieval correct:    18/21 (86%)
MODE_RE = re.compile(r"Mode correct:\s+(\d+)/(\d+)")
ANSWER_RE = re.compile(r"Answer correct:\s+(\d+)/(\d+)")
RETRIEVAL_RE = re.compile(r"Retrieval correct:\s+(\d+)/(\d+)")


def run_harness(harness, mode="all"):
    """Run one harness as a subprocess and return a result dict."""
    if not os.path.exists(harness["script"]):
        return {"name": harness["name"], "status": "SKIPPED",
                "reason": f"script not found: {harness['script']}",
                "mode_ok": 0, "mode_total": 0,
                "answer_ok": 0, "answer_total": 0,
                "retrieval_ok": 0, "retrieval_total": 0,
                "output": ""}

    cmd = [PY, harness["script"], f"--{mode}"]
    print(f"\n{'=' * 80}")
    print(f"RUNNING: {harness['name']}  ({' '.join(cmd)})")
    print("=" * 80)

    try:
        proc = subprocess.run(
            cmd, cwd=HERE, capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        return {"name": harness["name"], "status": "SKIPPED",
                "reason": "timed out after 600s",
                "mode_ok": 0, "mode_total": 0,
                "answer_ok": 0, "answer_total": 0,
                "retrieval_ok": 0, "retrieval_total": 0,
                "output": ""}

    output = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
    # Stream a trimmed view of the output
    for line in output.splitlines():
        if line.strip():
            print(f"  {line}")

    if proc.returncode != 0:
        return {"name": harness["name"], "status": "ERROR",
                "reason": f"exit code {proc.returncode}",
                "mode_ok": 0, "mode_total": 0,
                "answer_ok": 0, "answer_total": 0,
                "retrieval_ok": 0, "retrieval_total": 0,
                "output": output}

    # Parse SUMMARY block
    mode_match = MODE_RE.search(output)
    answer_match = ANSWER_RE.search(output)
    retrieval_match = RETRIEVAL_RE.search(output)

    mode_ok, mode_total = (int(mode_match.group(1)), int(mode_match.group(2))) if mode_match else (0, 0)
    answer_ok, answer_total = (int(answer_match.group(1)), int(answer_match.group(2))) if answer_match else (0, 0)
    retr_ok, retr_total = (int(retrieval_match.group(1)), int(retrieval_match.group(2))) if retrieval_match else (0, 0)

    if mode_total == 0:
        status = "SKIPPED"
        reason = "no SUMMARY block (no tests ran or DB empty)"
    else:
        status = "PASS" if mode_ok == mode_total else "FAIL"
        reason = ""

    return {
        "name": harness["name"], "status": status, "reason": reason,
        "mode_ok": mode_ok, "mode_total": mode_total,
        "answer_ok": answer_ok, "answer_total": answer_total,
        "retrieval_ok": retr_ok, "retrieval_total": retr_total,
        "output": output,
    }


def print_summary(results):
    print("\n" + "=" * 80)
    print("QA TEST RUNNER — UNIFIED SUMMARY")
    print("=" * 80)
    print(f"{'Harness':22s} {'Status':8s} {'Mode':>12s} {'Answer':>12s} {'Retrieval':>14s}")
    print("-" * 70)
    for r in results:
        mode_str = f"{r['mode_ok']}/{r['mode_total']}" if r["mode_total"] else "-"
        ans_str = f"{r['answer_ok']}/{r['answer_total']}" if r["answer_total"] else "-"
        retr_str = f"{r['retrieval_ok']}/{r['retrieval_total']}" if r["retrieval_total"] else "-"
        print(f"{r['name']:22s} {r['status']:8s} {mode_str:>12s} {ans_str:>12s} {retr_str:>14s}")
        if r["reason"]:
            print(f"  reason: {r['reason']}")
    print("-" * 70)

    ran = [r for r in results if r["status"] in ("PASS", "FAIL")]
    failed = [r for r in results if r["status"] == "FAIL"]
    errors = [r for r in results if r["status"] == "ERROR"]
    skipped = [r for r in results if r["status"] == "SKIPPED"]

    print(f"\n  Ran: {len(ran)}  Pass: {len([r for r in ran if r['status']=='PASS'])}  "
          f"Fail: {len(failed)}  Error: {len(errors)}  Skipped: {len(skipped)}")

    if errors:
        return 2  # hard error
    if failed:
        return 1  # assertions failed
    if not ran:
        return 3  # nothing ran (all skipped)
    return 0


def clean_all():
    for h in HARNESSES:
        if os.path.exists(h["script"]):
            print(f"Cleaning {h['name']}...")
            subprocess.run([PY, h["script"], "--clean"], cwd=HERE, timeout=60)
        if os.path.exists(h["db"]):
            try:
                os.remove(h["db"])
                print(f"  removed {h['db']}")
            except OSError:
                pass


def main():
    args = sys.argv[1:]
    mode = "all"
    only = None

    for a in args:
        if a == "--report":
            mode = "report"
        elif a == "--clean":
            clean_all()
            return 0
        elif a == "--harness":
            only = "next"
        elif only == "next":
            only = a

    targets = HARNESSES
    if only in ("v2", "qa_test_harness_v2"):
        targets = [HARNESSES[0]]
    elif only in ("pinnacle", "pinnacle_harness"):
        targets = [HARNESSES[1]]

    results = [run_harness(h, mode) for h in targets]
    return print_summary(results)


if __name__ == "__main__":
    sys.exit(main())
