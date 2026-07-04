#!/usr/bin/env python3
# [@GHOST]{[@file<demo_indexer_report.py>][@domain<Dom_Report>][@role<demo>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<demo>][@return<tuple3>][@orch<ReportUnit>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Integration demo — wraps FileIndexer.scan_dir in a ReportUnit, emits real facts, renders at 3 verbosity levels.}
# [@FILEID]{core/Dom_Report/demo_indexer_report.py

import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.Dom_Report.ReportUnit import ReportUnit
from core.utility.indexer import FileIndexer


def run_indexer_with_report(target_dir, db_path):
    """Run FileIndexer.scan_dir wrapped in a ReportUnit.

    This demonstrates the reporting system on a real operation:
    - Inputs: the directory path and db path
    - Outputs: the scan results (file counts)
    - Observations: elapsed time, db size
    - Occurrences: any errors as issues
    - Result: ok/fail based on scan outcome
    """
    ru = ReportUnit()
    ru.Run("open", {"operation": "IndexDirectory", "source": "FileIndexer.scan_dir"})

    # ── inputs ──
    ru.Run("emit", {"kind": "input", "name": "target_dir", "value": target_dir})
    ru.Run("emit", {"kind": "input", "name": "db_path", "value": db_path})

    # ── run the actual operation ──
    indexer = FileIndexer()
    t0 = time.time()
    ok, result, err = indexer.Run("scan_dir", {"path": target_dir, "db_path": db_path})
    elapsed = time.time() - t0

    # ── observations ──
    ru.Run("emit", {"kind": "measurement", "name": "elapsed", "value": round(elapsed, 3), "unit": "s"})
    db_size = os.path.getsize(db_path) if os.path.isfile(db_path) else 0
    ru.Run("emit", {"kind": "measurement", "name": "db_size", "value": db_size, "unit": "bytes"})

    if ok:
        # ── outputs ──
        ru.Run("emit", {"kind": "output", "name": "files_indexed", "value": result["files"]})
        ru.Run("emit", {"kind": "output", "name": "code_files", "value": result["code_files"]})
        ru.Run("emit", {"kind": "output", "name": "text_files", "value": result["text_files"]})

        # ── occurrences ──
        ru.Run("emit", {"kind": "event", "name": "scan_complete", "value": "success"})
        if result["code_files"] > 0:
            ru.Run("emit", {"kind": "message", "name": "code_metadata", "value": "extracted BCL headers, AST classes, functions"})
        if result["files"] > 100:
            ru.Run("emit", {"kind": "issue", "name": "large_scan", "value": "indexed %d files" % result["files"], "severity": "warning", "detail": "large directories may benefit from incremental indexing"})

        # ── result ──
        ru.Run("result", {"ok": True})
    else:
        # ── occurrences (errors) ──
        ru.Run("emit", {"kind": "issue", "name": "scan_error", "value": str(err[1]), "severity": "error", "detail": "error code: %s" % err[0]})

        # ── result ──
        ru.Run("result", {"ok": False, "reason": str(err[1])})

    return ru


def main():
    target = os.path.join(ROOT, "core", "Dom_Report")
    db_path = "/tmp/indexer_demo.db"

    if os.path.isfile(db_path):
        os.remove(db_path)

    sys.stdout.write("Scanning: %s\n\n" % target)
    ru = run_indexer_with_report(target, db_path)

    for verbosity in ("quiet", "normal", "verbose"):
        ok, text, _ = ru.Run("render", {"verbosity": verbosity, "use_color": False})
        sys.stdout.write("=" * 60 + "\n")
        sys.stdout.write("VERBOSITY: %s\n" % verbosity)
        sys.stdout.write("=" * 60 + "\n")
        sys.stdout.write(text + "\n\n")

    # Also show the Status command output
    ok, status, err = ru.Run("status", {})
    sys.stdout.write("Status: %s\n" % status)


if __name__ == "__main__":
    main()
