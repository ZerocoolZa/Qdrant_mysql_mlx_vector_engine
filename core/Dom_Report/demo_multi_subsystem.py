#!/usr/bin/env python3
# [@GHOST]{[@file<demo_multi_subsystem.py>][@domain<Dom_Report>][@role<integration>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<integration>][@return<tuple3>][@orch<ReportUnit>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Multi-subsystem integration — wraps FileIO.walk, FileIO.read_file, FileIO.hash_file, and SystemCheck.check_all in ReportUnit. Proves universality across different operations.}
# [@FILEID]{core/Dom_Report/demo_multi_subsystem.py

import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.Dom_Report.ReportUnit import ReportUnit
from core.utility.indexer import FileIO, FileIndexer


def report_file_walk(target_dir):
    """Operation 1: Walk a directory tree."""
    ru = ReportUnit()
    ru.Run("open", {"operation": "WalkDirectory", "source": "FileIO.walk"})
    ru.Run("emit", {"kind": "input", "name": "path", "value": target_dir})

    io = FileIO()
    t0 = time.time()
    ok, result, err = io.Run("walk", {"path": target_dir})
    elapsed = time.time() - t0

    ru.Run("emit", {"kind": "measurement", "name": "elapsed", "value": round(elapsed, 4), "unit": "s"})

    if ok:
        ru.Run("emit", {"kind": "output", "name": "file_count", "value": result["count"]})
        if result["count"] > 50:
            ru.Run("emit", {"kind": "issue", "name": "large_tree", "value": "%d files found" % result["count"], "severity": "warning"})
        ru.Run("emit", {"kind": "event", "name": "walk", "value": "complete"})
        ru.Run("result", {"ok": True})
    else:
        ru.Run("emit", {"kind": "issue", "name": "walk_error", "value": str(err[1]), "severity": "error"})
        ru.Run("result", {"ok": False, "reason": str(err[1])})

    return ru


def report_file_read(file_path):
    """Operation 2: Read a single file."""
    ru = ReportUnit()
    ru.Run("open", {"operation": "ReadFile", "source": "FileIO.read_file"})
    ru.Run("emit", {"kind": "input", "name": "path", "value": file_path})

    io = FileIO()
    ok_stat, stat_data, _ = io.Run("file_stat", {"path": file_path})
    if ok_stat:
        ru.Run("emit", {"kind": "measurement", "name": "file_size", "value": stat_data["size"], "unit": "bytes"})

    t0 = time.time()
    ok, content, err = io.Run("read_file", {"path": file_path})
    elapsed = time.time() - t0

    ru.Run("emit", {"kind": "measurement", "name": "elapsed", "value": round(elapsed, 4), "unit": "s"})

    if ok:
        line_count = len(content.splitlines()) if isinstance(content, str) else 0
        ru.Run("emit", {"kind": "output", "name": "line_count", "value": line_count})
        ru.Run("emit", {"kind": "output", "name": "char_count", "value": len(content) if isinstance(content, str) else len(str(content))})
        ru.Run("emit", {"kind": "event", "name": "read", "value": "complete"})
        ru.Run("result", {"ok": True})
    else:
        ru.Run("emit", {"kind": "issue", "name": "read_error", "value": str(err[1]), "severity": "error"})
        ru.Run("result", {"ok": False, "reason": str(err[1])})

    return ru


def report_file_hash(file_path):
    """Operation 3: Hash a file."""
    ru = ReportUnit()
    ru.Run("open", {"operation": "HashFile", "source": "FileIO.hash_file"})
    ru.Run("emit", {"kind": "input", "name": "path", "value": file_path})
    ru.Run("emit", {"kind": "input", "name": "algo", "value": "md5"})

    io = FileIO()
    ok_stat, stat_data, _ = io.Run("file_stat", {"path": file_path})
    if ok_stat:
        ru.Run("emit", {"kind": "measurement", "name": "file_size", "value": stat_data["size"], "unit": "bytes"})

    t0 = time.time()
    ok, md5_hash, err = io.Run("hash_file", {"path": file_path})
    elapsed = time.time() - t0

    ru.Run("emit", {"kind": "measurement", "name": "elapsed", "value": round(elapsed, 4), "unit": "s"})

    if ok:
        ru.Run("emit", {"kind": "output", "name": "md5", "value": md5_hash})
        if md5_hash == "SKIP_LARGE":
            ru.Run("emit", {"kind": "issue", "name": "skipped", "value": "file too large to hash", "severity": "warning"})
        ru.Run("emit", {"kind": "event", "name": "hash", "value": "complete"})
        ru.Run("result", {"ok": True})
    else:
        ru.Run("emit", {"kind": "issue", "name": "hash_error", "value": str(err[1]), "severity": "error"})
        ru.Run("result", {"ok": False, "reason": str(err[1])})

    return ru


def report_index_scan(target_dir, db_path):
    """Operation 4: Full directory index with SQLite storage."""
    ru = ReportUnit()
    ru.Run("open", {"operation": "IndexDirectory", "source": "FileIndexer.scan_dir"})
    ru.Run("emit", {"kind": "input", "name": "target_dir", "value": target_dir})
    ru.Run("emit", {"kind": "input", "name": "db_path", "value": db_path})

    indexer = FileIndexer()
    t0 = time.time()
    ok, result, err = indexer.Run("scan_dir", {"path": target_dir, "db_path": db_path})
    elapsed = time.time() - t0

    ru.Run("emit", {"kind": "measurement", "name": "elapsed", "value": round(elapsed, 3), "unit": "s"})
    db_size = os.path.getsize(db_path) if os.path.isfile(db_path) else 0
    ru.Run("emit", {"kind": "measurement", "name": "db_size", "value": db_size, "unit": "bytes"})

    if ok:
        ru.Run("emit", {"kind": "output", "name": "files_indexed", "value": result["files"]})
        ru.Run("emit", {"kind": "output", "name": "code_files", "value": result["code_files"]})
        ru.Run("emit", {"kind": "output", "name": "text_files", "value": result["text_files"]})
        ru.Run("emit", {"kind": "event", "name": "scan", "value": "complete"})
        if result["code_files"] > 0:
            ru.Run("emit", {"kind": "message", "name": "metadata", "value": "extracted BCL headers, AST classes, functions"})
        ru.Run("result", {"ok": True})
    else:
        ru.Run("emit", {"kind": "issue", "name": "scan_error", "value": str(err[1]), "severity": "error", "detail": "error code: %s" % err[0]})
        ru.Run("result", {"ok": False, "reason": str(err[1])})

    return ru


def report_failed_read(missing_path):
    """Operation 5: Deliberately fail to read a nonexistent file — proves failure path."""
    ru = ReportUnit()
    ru.Run("open", {"operation": "ReadFile", "source": "FileIO.read_file"})
    ru.Run("emit", {"kind": "input", "name": "path", "value": missing_path})

    io = FileIO()
    ok, _, err = io.Run("read_file", {"path": missing_path})

    if not ok:
        ru.Run("emit", {"kind": "issue", "name": "file_not_found", "value": str(err[1]), "severity": "error", "detail": "the file does not exist on disk"})
        ru.Run("emit", {"kind": "recommendation", "name": "suggestion", "value": "verify the file path exists before calling read_file"})
        ru.Run("result", {"ok": False, "reason": str(err[1])})

    return ru


def main():
    target = os.path.join(ROOT, "core", "Dom_Report")
    test_file = os.path.join(target, "Report.py")
    db_path = "/tmp/multi_subsystem_demo.db"
    missing_file = "/nonexistent/missing.py"

    if os.path.isfile(db_path):
        os.remove(db_path)

    operations = [
        ("WalkDirectory", lambda: report_file_walk(target)),
        ("ReadFile", lambda: report_file_read(test_file)),
        ("HashFile", lambda: report_file_hash(test_file)),
        ("IndexDirectory", lambda: report_index_scan(target, db_path)),
        ("ReadFile (FAIL)", lambda: report_failed_read(missing_file)),
    ]

    sys.stdout.write("Multi-Subsystem Integration Demo\n")
    sys.stdout.write("Proving ReportUnit works across 5 different operations\n\n")

    reports = []
    for name, factory in operations:
        ru = factory()
        reports.append((name, ru))

    # Show each report at verbose level
    for name, ru in reports:
        ok, text, _ = ru.Run("render", {"verbosity": "verbose", "use_color": False})
        sys.stdout.write("=" * 60 + "\n")
        sys.stdout.write("OPERATION: %s\n" % name)
        sys.stdout.write("=" * 60 + "\n")
        sys.stdout.write(text + "\n\n")

    # Summary table — spine of all 5 operations
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("SUMMARY: All operation spines\n")
    sys.stdout.write("=" * 60 + "\n")
    for name, ru in reports:
        ok, status, _ = ru.Run("status", {})
        result_label = "PASS" if status["result"] == "ok" else "FAIL"
        reason = status["reason"] if status["reason"] else ""
        line = "%-20s  %s  %s  facts=%d" % (
            status["operation"], result_label, reason, status["facts"]
        )
        sys.stdout.write(line + "\n")


if __name__ == "__main__":
    main()
