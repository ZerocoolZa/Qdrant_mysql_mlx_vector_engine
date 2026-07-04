#!/usr/bin/env python3
"""
test_errorhandler_loop.py — Test ClassErrorHandler self-learning loop.

Loop under test:
  1. capture(producer, entity, pattern, description, severity, payload)
  2. Search BCL store for matching pattern
  3. If found: return known fix, increment occurrences, update confidence
  4. If new: record as BCL, suggest auto-fix
  5. test_fix(pattern, success) -> promote or demote
  6. Promoted fixes have high confidence on next encounter

Scenarios:
  A. New error captured -> STATUS_NEW, auto-fix suggested
  B. Same error recaptured -> found=True, occurrences increment
  C. test_fix success x1 -> STATUS_TESTING
  D. test_fix success x2 -> STATUS_PROMOTED
  E. Recapture after promotion -> confidence boost
  F. test_fix failure -> demoted back to TESTING
  G. test_fix failure again -> STATUS_FAILED
  H. Brand new unknown pattern -> default "investigate manually"
  I. report() and get_stats() output
"""

import os
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ClassErrorHandler, ClassBCL


PASS = 0
FAIL = 0


def check(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}  {detail}")


def section(title):
    print(f"\n--- {title} ---")


def main():
    tmpdir = tempfile.mkdtemp(prefix="errhandler_")
    bcl_path = os.path.join(tmpdir, "errors.bcl")
    print(f">> Test ErrorHandler self-learning loop")
    print(f"   BCL store: {bcl_path}")

    # --- Scenario A: new error ---
    section("A. Capture NEW error (UNSUPPORTED_LANGUAGE)")
    h = ClassErrorHandler(bcl_path)
    r = h.capture("scanner", "Makefile", "UNSUPPORTED_LANGUAGE",
                  "Cannot extract scents from makefile files",
                  severity=1, payload={"file": "Makefile"})
    print(f"   result: {r}")
    check("found=False on first encounter", r["found"] is False,
          f"got found={r['found']}")
    check("status=NEW", r["status"] == ClassErrorHandler.STATUS_NEW,
          f"got status={r['status']}")
    check("occurrences=1", r["occurrences"] == 1,
          f"got occ={r['occurrences']}")
    check("auto-fix suggested from AUTO_FIXES",
          r["fix"] == "skip file and continue scan",
          f"got fix={r['fix']}")
    check("confidence=0.3 default for new",
          abs(r["confidence"] - 0.3) < 1e-6,
          f"got conf={r['confidence']}")
    check("pattern recorded in known store",
          "UNSUPPORTED_LANGUAGE" in h.known)

    # --- Scenario B: recapture same error ---
    section("B. Recapture SAME error -> known hit, occurrences=2")
    r2 = h.capture("scanner", "Other.mk", "UNSUPPORTED_LANGUAGE",
                   "Cannot extract scents from makefile files",
                   severity=1)
    print(f"   result: {r2}")
    check("found=True on second encounter", r2["found"] is True)
    check("occurrences=2", r2["occurrences"] == 2,
          f"got occ={r2['occurrences']}")
    check("fix returned from known store",
          r2["fix"] == "skip file and continue scan")
    check("errors list grew to 2", len(h.errors) == 2,
          f"got len={len(h.errors)}")

    # --- Scenario C: test_fix success #1 -> TESTING ---
    section("C. test_fix(success) #1 -> STATUS_TESTING")
    t = h.test_fix("UNSUPPORTED_LANGUAGE", success=True)
    print(f"   result: {t}")
    check("status=TESTING after first success",
          t["status"] == ClassErrorHandler.STATUS_TESTING,
          f"got status={t['status']}")
    check("confidence increased",
          float(t["confidence"]) > 0.3,
          f"got conf={t['confidence']}")

    # --- Scenario D: test_fix success #2 -> PROMOTED ---
    section("D. test_fix(success) #2 -> STATUS_PROMOTED")
    t = h.test_fix("UNSUPPORTED_LANGUAGE", success=True)
    print(f"   result: {t}")
    check("status=PROMOTED after second success",
          t["status"] == ClassErrorHandler.STATUS_PROMOTED,
          f"got status={t['status']}")
    check("confidence >= 0.7",
          float(t["confidence"]) >= 0.7,
          f"got conf={t['confidence']}")

    # --- Scenario E: recapture after promotion -> confidence boost ---
    section("E. Recapture after promotion -> confidence boost")
    r3 = h.capture("scanner", "third.mk", "UNSUPPORTED_LANGUAGE",
                   "Cannot extract scents from makefile files")
    print(f"   result: {r3}")
    check("found=True", r3["found"] is True)
    check("occurrences=3", r3["occurrences"] == 3,
          f"got occ={r3['occurrences']}")
    check("status still PROMOTED",
          r3["status"] == ClassErrorHandler.STATUS_PROMOTED)
    check("confidence boosted on promoted recapture",
          r3["confidence"] > float(t["confidence"]) or
          abs(r3["confidence"] - 1.0) < 1e-6,
          f"got conf={r3['confidence']} (prev={t['confidence']})")

    # --- Scenario F: test_fix failure -> demoted to TESTING ---
    section("F. test_fix(failure) -> demoted TESTING")
    t = h.test_fix("UNSUPPORTED_LANGUAGE", success=False)
    print(f"   result: {t}")
    check("status=TESTING after demotion from PROMOTED",
          t["status"] == ClassErrorHandler.STATUS_TESTING,
          f"got status={t['status']}")
    check("confidence decreased",
          float(t["confidence"]) < r3["confidence"],
          f"got conf={t['confidence']}")

    # --- Scenario G: test_fix failure again -> FAILED ---
    section("G. test_fix(failure) again -> STATUS_FAILED")
    t = h.test_fix("UNSUPPORTED_LANGUAGE", success=False)
    print(f"   result: {t}")
    check("status=FAILED after second failure",
          t["status"] == ClassErrorHandler.STATUS_FAILED,
          f"got status={t['status']}")
    check("confidence floor at 0.1",
          float(t["confidence"]) >= 0.1,
          f"got conf={t['confidence']}")

    # --- Scenario H: unknown pattern -> default fix ---
    section("H. Unknown pattern -> default 'investigate manually'")
    r4 = h.capture("nose", "edge_x", "UNKNOWN_BUG_XYZ",
                   "Something we have never seen")
    print(f"   result: {r4}")
    check("found=False", r4["found"] is False)
    check("default fix = 'investigate manually'",
          r4["fix"] == "investigate manually",
          f"got fix={r4['fix']}")

    # --- Scenario I: persistence across instances ---
    section("I. Persistence: reload BCL store in new instance")
    h2 = ClassErrorHandler(bcl_path)
    check("known patterns reloaded from BCL",
          "UNSUPPORTED_LANGUAGE" in h2.known and
          "UNKNOWN_BUG_XYZ" in h2.known,
          f"got keys={list(h2.known.keys())}")
    check("UNSUPPORTED_LANGUAGE status preserved as FAILED",
          h2.known["UNSUPPORTED_LANGUAGE"].get("status") ==
          ClassErrorHandler.STATUS_FAILED,
          f"got status={h2.known['UNSUPPORTED_LANGUAGE'].get('status')}")
    check("UNKNOWN_BUG_XYZ status preserved as NEW",
          h2.known["UNKNOWN_BUG_XYZ"].get("status") ==
          ClassErrorHandler.STATUS_NEW)

    # --- Scenario J: test_fix on unknown pattern ---
    section("J. test_fix on unknown pattern -> graceful message")
    t = h.test_fix("DOES_NOT_EXIST", success=True)
    print(f"   result: {t}")
    check("graceful message for unknown pattern",
          "nothing to test" in t["message"].lower(),
          f"got msg={t['message']}")

    # --- Scenario K: report() and get_stats() ---
    section("K. report() and get_stats()")
    rep = h.report()
    print(rep)
    stats = h.get_stats()
    print(f"   stats: {stats}")
    check("stats total_known >= 2",
          stats["total_known"] >= 2,
          f"got total_known={stats['total_known']}")
    check("stats captured_this_run matches errors list",
          stats["captured_this_run"] == len(h.errors),
          f"got {stats['captured_this_run']} vs {len(h.errors)}")
    check("stats has promoted/testing/failed/new keys",
          all(k in stats for k in
              ("promoted", "testing", "failed", "new")))
    check("report mentions each known pattern",
          all(p in rep for p in h.known),
          "some known pattern missing from report")

    # --- Scenario L: BCL file actually written ---
    section("L. BCL file written to disk")
    check("BCL file exists", os.path.exists(bcl_path))
    with open(bcl_path) as f:
        content = f.read()
    check("BCL contains [@ERROR] container",
          "[@ERROR]" in content)
    check("BCL contains pattern field",
          "UNSUPPORTED_LANGUAGE" in content and
          "UNKNOWN_BUG_XYZ" in content)

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print(f"  PASSED: {PASS}")
    print(f"  FAILED: {FAIL}")
    print(f"  TOTAL:  {PASS + FAIL}")
    print(f"  RESULT: {'ALL PASS' if FAIL == 0 else 'HAS FAILURES'}")
    print(f"{'=' * 60}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
