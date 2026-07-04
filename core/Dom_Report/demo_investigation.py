#!/usr/bin/env python3
# [@GHOST]{[@file<demo_investigation.py>][@domain<Dom_Report>][@role<demo>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<demo>][@return<tuple3>][@orch<Investigator>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Investigation demo — runs a failed operation, produces a report, then investigates it with the diagnostic protocol. Shows Layer 1 → Layer 2 pipeline.}
# [@FILEID]{core/Dom_Report/demo_investigation.py

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.Dom_Report.ReportUnit import ReportUnit
from core.Dom_Report.Investigator import Investigator


def main():
    # ── Layer 1: produce the report (the case file) ──
    ru = ReportUnit()
    ru.Run("open", {"operation": "ReadFile", "source": "FileIO.read_file"})
    ru.Run("emit", {"kind": "input", "name": "path", "value": "/nonexistent/missing.py"})
    ru.Run("emit", {"kind": "issue", "name": "file_not_found", "value": "File not found: /nonexistent/missing.py", "severity": "error", "detail": "the file does not exist on disk"})
    ru.Run("emit", {"kind": "recommendation", "name": "suggestion", "value": "verify the file path exists before calling read_file"})
    ru.Run("result", {"ok": False, "reason": "File not found: /nonexistent/missing.py"})
    ru.Run("finalize", {})

    # Show the case file (Layer 1)
    ok, report_text, _ = ru.Run("render", {"verbosity": "verbose", "use_color": False})
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("LAYER 1 — THE REPORT (case file)\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write(report_text + "\n\n")

    # ── Layer 2: investigate the report (the detective) ──
    inv = Investigator()
    ok, diagnosis, _ = inv.Run("investigate", {"report": ru.state["report"]})

    # Show the investigation (Layer 2)
    ok, diag_text, _ = inv.Run("render_diagnosis", {"use_color": False})
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("LAYER 2 — THE INVESTIGATION (diagnostic protocol)\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write(diag_text + "\n")

    # Show the summary of what's known vs pending
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("DIAGNOSTIC SUMMARY\n")
    sys.stdout.write("=" * 60 + "\n")
    known = 0
    pending = 0
    na = 0
    unknown = 0
    for cat in diagnosis.values():
        for q in cat.values():
            if q["status"] == "known":
                known += 1
            elif q["status"] == "pending":
                pending += 1
            elif q["status"] == "n/a":
                na += 1
            else:
                unknown += 1
    sys.stdout.write("Answered from report:    %d\n" % known)
    sys.stdout.write("Pending (needs KB):      %d\n" % pending)
    sys.stdout.write("Not applicable:          %d\n" % na)
    sys.stdout.write("Unknown:                 %d\n" % unknown)
    sys.stdout.write("\nNext step: connect knowledge base to answer the %d pending questions.\n" % pending)


if __name__ == "__main__":
    main()
