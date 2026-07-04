#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/self_check_engine.py"
# date="2026-06-26" author="Devin" session_id="phase5-quality"
# context="Project Digital Twin Phase 5 Section 34 Self Check Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="self_check_engine.py" domain="twin_selfcheck" authority="SelfCheckEngine"}
# [@SUMMARY]{summary="Self-check authority comparing hashes, scope, tests and graph before and after changes."}
# [@CLASS]{class="SelfCheckEngine" domain="selfcheck" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="check_changes" type="command"}
# [@METHOD]{method="check_expected" type="command"}
# [@METHOD]{method="check_tests" type="command"}
# [@METHOD]{method="check_graph" type="command"}
# [@METHOD]{method="check_all" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="Connect" type="helper"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<SelfCheckEngine: compares hashes scope tests graph before and after changes. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config Connect helper. No print no decorators no self._ violations.>][@todos<none>]}
"""
SelfCheckEngine -- authority for self-checking changes, scope, tests and graph integrity.
Implements Section 34 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: check_changes, check_expected, check_tests, check_graph, check_database,
          check_bcl, check_runtime, check_confidence, check_all.
"""
import ast
import hashlib
import json
import os
import pathlib
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
TEST_SCRIPT = "test_everything.py"

EXPECTED_TABLES = (
    "files",
    "classes",
    "methods",
    "edges",
    "knowledge",
    "snapshots",
    "attempts",
    "observations",
)


class SelfCheckEngine:
    """Authority for self-checking changes, expected scope, tests and graph state."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
                "test_script": TEST_SCRIPT,
                "cwd": os.path.dirname(os.path.abspath(__file__)),
            },
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "check_changes":
            return self.CheckChanges(params)
        elif command == "check_expected":
            return self.CheckExpected(params)
        elif command == "check_tests":
            return self.CheckTests(params)
        elif command == "check_graph":
            return self.CheckGraph(params)
        elif command == "check_database":
            return self.CheckDatabase(params)
        elif command == "check_bcl":
            return self.CheckBcl(params)
        elif command == "check_runtime":
            return self.CheckRuntime(params)
        elif command == "check_confidence":
            return self.CheckConfidence(params)
        elif command == "check_all":
            return self.CheckAll(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def Connect(self):
        if self.state["db_conn"] is None:
            self.state["db_conn"] = sqlite3.connect(self.state["config"]["db_path"])
        return self.state["db_conn"]

    def CheckChanges(self, params):
        target_dir = self._p(params, "target_dir", self.state["config"]["cwd"])
        before_hashes = self._p(params, "before_hashes")
        after_hashes = self._p(params, "after_hashes")
        if before_hashes is not None and after_hashes is not None:
            if not isinstance(before_hashes, dict) or not isinstance(after_hashes, dict):
                return (0, None, ("INVALID_PARAM", "before_hashes and after_hashes must be dicts", 0))
        else:
            py_files = sorted(pathlib.Path(target_dir).rglob("*.py"))
            after_hashes = {}
            for pyf in py_files:
                try:
                    text = pyf.read_text(encoding="utf-8", errors="replace")
                    after_hashes[str(pyf)] = hashlib.sha256(text.encode("utf-8")).hexdigest()
                except OSError:
                    continue
            try:
                conn = self.Connect()
                cur = conn.cursor()
                cur.execute("SELECT path, hash FROM files WHERE status='active'")
                before_hashes = {row[0]: row[1] for row in cur.fetchall()}
            except sqlite3.Error:
                before_hashes = {}
        changed = []
        added = []
        removed = []
        for key, after_hash in after_hashes.items():
            if key not in before_hashes:
                added.append({"key": key, "hash": after_hash})
            elif before_hashes[key] != after_hash:
                changed.append(
                    {
                        "key": key,
                        "before": before_hashes[key],
                        "after": after_hash,
                    }
                )
        for key, before_hash in before_hashes.items():
            if key not in after_hashes:
                removed.append({"key": key, "hash": before_hash})
        result = {
            "changed": changed,
            "added": added,
            "removed": removed,
            "changed_count": len(changed),
            "added_count": len(added),
            "removed_count": len(removed),
            "total_changes": len(changed) + len(added) + len(removed),
            "passed": len(changed) + len(added) + len(removed) == 0,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def CheckExpected(self, params):
        expected_tables = self._p(params, "expected_tables", list(EXPECTED_TABLES))
        if not isinstance(expected_tables, list):
            return (0, None, ("INVALID_PARAM", "expected_tables must be a list", 0))
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            actual_tables = {row[0] for row in cur.fetchall()}
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        present = []
        missing = []
        for table in expected_tables:
            if table in actual_tables:
                present.append(table)
            else:
                missing.append(table)
        result = {
            "expected": expected_tables,
            "present": present,
            "missing": missing,
            "present_count": len(present),
            "missing_count": len(missing),
            "passed": len(missing) == 0,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def CheckTests(self, params):
        cwd = self._p(params, "cwd", self.state["config"]["cwd"])
        script = self._p(params, "test_script", self.state["config"]["test_script"])
        script_path = os.path.join(cwd, script)
        if not os.path.isfile(script_path):
            return (0, None, ("TEST_NOT_FOUND", script_path, 0))
        try:
            proc = subprocess.run(
                ["python3", script],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return (0, None, ("TEST_TIMEOUT", "Test suite timed out", 0))
        except OSError as exc:
            return (0, None, ("TEST_ERROR", str(exc), 0))
        passed = 0
        failed = 0
        for line in proc.stdout.splitlines():
            if "RESULTS:" in line:
                parts = line.split("RESULTS:")[1].strip()
                for token in parts.split(","):
                    token = token.strip()
                    if "passed" in token:
                        try:
                            passed = int(token.split()[0])
                        except (ValueError, IndexError):
                            pass
                    elif "failed" in token:
                        try:
                            failed = int(token.split()[0])
                        except (ValueError, IndexError):
                            pass
        total = passed + failed
        result = {
            "passed": passed,
            "failed": failed,
            "total": total,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
        }
        self.state["results"].append(result)
        return (1, result, None)

    def CheckGraph(self, params):
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM edges")
            edge_count = cur.fetchone()[0]
            cur.execute(
                "SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type ORDER BY edge_type"
            )
            type_counts = {row[0]: row[1] for row in cur.fetchall()}
            cur.execute(
                "SELECT COUNT(*) FROM edges e WHERE e.src_type='method' AND e.src_id NOT IN (SELECT method_id FROM methods)"
            )
            dangling_src = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM edges e WHERE e.dst_type='method' AND e.dst_id NOT IN (SELECT method_id FROM methods)"
            )
            dangling_dst = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM edges WHERE confidence < 0 OR confidence > 100"
            )
            bad_confidence = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        before_count = self._p(params, "before_count")
        after_count = self._p(params, "after_count")
        changed = False
        delta = None
        if before_count is not None and after_count is not None:
            changed = before_count != after_count
            delta = after_count - before_count
        result = {
            "edge_count": edge_count,
            "type_counts": type_counts,
            "dangling_src": dangling_src,
            "dangling_dst": dangling_dst,
            "bad_confidence": bad_confidence,
            "before_count": before_count,
            "after_count": after_count,
            "changed": changed,
            "delta": delta,
            "passed": dangling_src == 0 and dangling_dst == 0 and bad_confidence == 0 and not changed,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def CheckDatabase(self, params):
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check")
            integrity = cur.fetchone()[0]
            cur.execute("PRAGMA foreign_key_check")
            fk_violations = cur.fetchall()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cur.fetchall()]
            row_counts = {}
            for table in tables:
                try:
                    cur.execute("SELECT COUNT(*) FROM " + table)
                    row_counts[table] = cur.fetchone()[0]
                except sqlite3.Error:
                    row_counts[table] = -1
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        result = {
            "integrity": integrity,
            "fk_violations": fk_violations,
            "fk_violation_count": len(fk_violations),
            "tables": tables,
            "row_counts": row_counts,
            "passed": integrity == "ok" and len(fk_violations) == 0,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def CheckBcl(self, params):
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM files")
            total_files = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM files WHERE bcl IS NOT NULL AND bcl != ''")
            files_with_bcl = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM classes")
            total_classes = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM classes WHERE bcl IS NOT NULL AND bcl != ''")
            classes_with_bcl = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods")
            total_methods = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE bcl IS NOT NULL AND bcl != ''")
            methods_with_bcl = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        file_coverage = (files_with_bcl / total_files * 100) if total_files > 0 else 0
        class_coverage = (classes_with_bcl / total_classes * 100) if total_classes > 0 else 0
        method_coverage = (methods_with_bcl / total_methods * 100) if total_methods > 0 else 0
        overall = (file_coverage + class_coverage + method_coverage) / 3
        result = {
            "files": {"total": total_files, "with_bcl": files_with_bcl, "coverage": round(file_coverage, 1)},
            "classes": {"total": total_classes, "with_bcl": classes_with_bcl, "coverage": round(class_coverage, 1)},
            "methods": {"total": total_methods, "with_bcl": methods_with_bcl, "coverage": round(method_coverage, 1)},
            "overall_coverage": round(overall, 1),
            "passed": overall >= 80,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def CheckRuntime(self, params):
        target_dir = self._p(params, "target_dir", self.state["config"]["cwd"])
        py_files = sorted(pathlib.Path(target_dir).rglob("*.py"))
        files_with_run = 0
        files_without_run = []
        for pyf in py_files:
            try:
                text = pyf.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(text, filename=str(pyf))
            except (OSError, SyntaxError):
                continue
            has_run = False
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and item.name == "Run":
                            has_run = True
                            break
                    if has_run:
                        break
            if has_run:
                files_with_run += 1
            else:
                fname = os.path.basename(str(pyf))
                if not fname.startswith("test_") and fname not in ("__init__.py",):
                    files_without_run.append(str(pyf))
        total = len(py_files)
        result = {
            "total_files": total,
            "files_with_run": files_with_run,
            "files_without_run": files_without_run,
            "coverage": round(files_with_run / total * 100, 1) if total > 0 else 0,
            "passed": len(files_without_run) == 0,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def CheckConfidence(self, params):
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM knowledge")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM knowledge WHERE confidence < 0 OR confidence > 100")
            invalid = cur.fetchone()[0]
            cur.execute("SELECT AVG(confidence) FROM knowledge")
            avg_row = cur.fetchone()
            avg_confidence = avg_row[0] if avg_row[0] is not None else 0
            cur.execute("SELECT COUNT(*) FROM edges WHERE confidence < 0 OR confidence > 100")
            invalid_edges = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM edges")
            total_edges = cur.fetchone()[0]
            cur.execute("SELECT AVG(confidence) FROM edges")
            avg_edge_row = cur.fetchone()
            avg_edge_confidence = avg_edge_row[0] if avg_edge_row[0] is not None else 0
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        result = {
            "knowledge": {
                "total": total,
                "invalid": invalid,
                "avg_confidence": round(avg_confidence, 1),
            },
            "edges": {
                "total": total_edges,
                "invalid": invalid_edges,
                "avg_confidence": round(avg_edge_confidence, 1),
            },
            "passed": invalid == 0 and invalid_edges == 0,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def CheckAll(self, params):
        report = {"checks": {}}
        checks = [
            ("changes", self.CheckChanges),
            ("expected", self.CheckExpected),
            ("tests", self.CheckTests),
            ("graph", self.CheckGraph),
            ("database", self.CheckDatabase),
            ("bcl", self.CheckBcl),
            ("runtime", self.CheckRuntime),
            ("confidence", self.CheckConfidence),
        ]
        all_passed = True
        for check_name, check_fn in checks:
            try:
                res = check_fn(params)
                if res[0] == 1:
                    report["checks"][check_name] = res[1]
                    if not res[1].get("passed", True):
                        all_passed = False
                else:
                    report["checks"][check_name] = {"error": res[2]}
                    all_passed = False
            except Exception as exc:
                report["checks"][check_name] = {"error": str(exc)}
                all_passed = False
        report["passed"] = all_passed
        report["created"] = datetime.now(timezone.utc).isoformat()
        self.state["results"].append(report)
        return (1, report, None)
