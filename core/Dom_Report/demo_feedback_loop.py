#!/usr/bin/env python3
# [@GHOST]{[@file<demo_feedback_loop.py>][@domain<Dom_Report>][@role<demo>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<demo>][@return<tuple3>][@orch<Investigator>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Full feedback loop demo — Execution → Report → Investigation → Knowledge Base → Enriched Diagnosis. Shows all 3 layers working together.}
# [@FILEID]{core/Dom_Report/demo_feedback_loop.py

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.Dom_Report.ReportUnit import ReportUnit
from core.Dom_Report.Investigator import Investigator
from core.Dom_Report.KnowledgeBase import KnowledgeBase
from core.Dom_Report import Config


def main():
    # ── Layer 1: Execution → Report ──
    ru = ReportUnit()
    ru.Run("open", {"operation": "ReadFile", "source": "FileIO.read_file"})
    ru.Run("emit", {"kind": "input", "name": "path", "value": "/nonexistent/missing.py"})
    ru.Run("emit", {"kind": "issue", "name": "file_not_found", "value": "File not found", "severity": "error", "detail": "the file does not exist on disk"})
    ru.Run("emit", {"kind": "recommendation", "name": "suggestion", "value": "verify the file path exists before calling read_file"})
    ru.Run("result", {"ok": False, "reason": "File not found"})
    ru.Run("finalize", {})

    ok, report_text, _ = ru.Run("render", {"verbosity": "verbose", "use_color": False})
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("LAYER 1 — REPORT (the case file)\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write(report_text + "\n\n")

    # ── Layer 2a: Investigation WITHOUT knowledge base ──
    inv_no_kb = Investigator()
    inv_no_kb.Run("investigate", {"report": ru.state["report"]})
    ok, diag_no_kb, _ = inv_no_kb.Run("render_diagnosis", {"use_color": False})
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("LAYER 2a — INVESTIGATION (without knowledge base)\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write(diag_no_kb + "\n")

    # Count answers
    known_no_kb = 0
    pending_no_kb = 0
    for cat in inv_no_kb.state["diagnosis"].values():
        for q in cat.values():
            if q["status"] == Config.ANSWER_KNOWN:
                known_no_kb += 1
            elif q["status"] == Config.ANSWER_PENDING:
                pending_no_kb += 1
    sys.stdout.write("Without KB: %d known, %d pending\n\n" % (known_no_kb, pending_no_kb))

    # ── Layer 2b: Investigation WITH knowledge base ──
    kb = KnowledgeBase()
    inv_with_kb = Investigator()
    inv_with_kb.Run("investigate", {"report": ru.state["report"], "knowledge_base": kb})
    ok, diag_with_kb, _ = inv_with_kb.Run("render_diagnosis", {"use_color": False})
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("LAYER 2b — INVESTIGATION (with knowledge base)\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write(diag_with_kb + "\n")

    # Count answers
    known_with_kb = 0
    pending_with_kb = 0
    for cat in inv_with_kb.state["diagnosis"].values():
        for q in cat.values():
            if q["status"] == Config.ANSWER_KNOWN:
                known_with_kb += 1
            elif q["status"] == Config.ANSWER_PENDING:
                pending_with_kb += 1
    sys.stdout.write("With KB: %d known, %d pending\n\n" % (known_with_kb, pending_with_kb))

    # ── The feedback loop ──
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("THE FEEDBACK LOOP\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("Execution → Report → Investigation → Knowledge Base\n")
    sys.stdout.write("\n")
    sys.stdout.write("Without KB: %d/%d questions answered (%d pending)\n" % (known_no_kb, known_no_kb + pending_no_kb, pending_no_kb))
    sys.stdout.write("With KB:    %d/%d questions answered (%d pending)\n" % (known_with_kb, known_with_kb + pending_with_kb, pending_with_kb))
    sys.stdout.write("KB filled:  %d questions that were pending are now known\n" % (known_with_kb - known_no_kb))
    sys.stdout.write("\n")
    sys.stdout.write("KB findings recorded: %d\n" % len(kb.state["findings"]))
    for f in kb.state["findings"]:
        sys.stdout.write("  — [%s] %s\n" % (f["category"], f["finding"]))
    sys.stdout.write("\n")
    remaining = pending_with_kb
    if remaining > 0:
        sys.stdout.write("Next: %d questions still pending — these need:\n" % remaining)
        sys.stdout.write("  - Deeper analysis (root cause)\n")
        sys.stdout.write("  - More knowledge base entries (learning)\n")
        sys.stdout.write("  - AI-assisted investigation (Cascade/Devin)\n")


if __name__ == "__main__":
    main()
