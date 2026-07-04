#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/validation_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 13: Validation Engine -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="validation_engine.py" domain="twin_validation" authority="ValidationEngine"}
# [@SUMMARY]{summary="Validation authority: validate syntax, validate imports, validate references, validate runtime, validate unit tests, validate integration tests, validate memory, validate database, validate performance, validate regression."}
# [@CLASS]{class="ValidationEngine" domain="validation" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="validate_syntax" type="command"}
# [@METHOD]{method="validate_imports" type="command"}
# [@METHOD]{method="validate_references" type="command"}
# [@METHOD]{method="validate_runtime" type="command"}
# [@METHOD]{method="validate_unit_tests" type="command"}
# [@METHOD]{method="validate_integration_tests" type="command"}
# [@METHOD]{method="validate_memory" type="command"}
# [@METHOD]{method="validate_database" type="command"}
# [@METHOD]{method="validate_performance" type="command"}
# [@METHOD]{method="validate_regression" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import ast
import os
import re
import sqlite3
import subprocess
import time
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class ValidationEngine:
    """Authority for comprehensive validation of code and database."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "python_bin": "python3",
                "test_timeout": 60,
                "perf_baseline": {},
            },
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
            "baselines": {},
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "validate_syntax":
            return self.ValidateSyntax(params)
        elif command == "validate_imports":
            return self.ValidateImports(params)
        elif command == "validate_references":
            return self.ValidateReferences(params)
        elif command == "validate_runtime":
            return self.ValidateRuntime(params)
        elif command == "validate_unit_tests":
            return self.ValidateUnitTests(params)
        elif command == "validate_integration_tests":
            return self.ValidateIntegrationTests(params)
        elif command == "validate_memory":
            return self.ValidateMemory(params)
        elif command == "validate_database":
            return self.ValidateDatabase(params)
        elif command == "validate_performance":
            return self.ValidatePerformance(params)
        elif command == "validate_regression":
            return self.ValidateRegression(params)
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
        return (1, self.state["db_conn"], None)

    def Now(self):
        return (1, datetime.now(timezone.utc).isoformat(), None)

    def ValidateSyntax(self, params):
        path = self._p(params, "path")
        if path is None or not os.path.isfile(path):
            return (0, None, ("FILE_NOT_FOUND", str(path), 0))
        with open(path, "r", errors="replace") as f:
            content = f.read()
        try:
            tree = ast.parse(content)
        except SyntaxError as exc:
            return (1, {"valid": False, "error": str(exc),
                        "line": exc.lineno, "file": path}, None)
        return (1, {"valid": True, "file": path}, None)

    def ValidateImports(self, params):
        path = self._p(params, "path")
        if path is None or not os.path.isfile(path):
            return (0, None, ("FILE_NOT_FOUND", str(path), 0))
        with open(path, "r", errors="replace") as f:
            content = f.read()
        try:
            tree = ast.parse(content)
        except SyntaxError as exc:
            return (0, None, ("PARSE_FAILED", str(exc), 0))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        missing = []
        for imp in imports:
            base = imp.split(".")[0]
            try:
                __import__(base)
            except ImportError:
                missing.append(imp)
        return (1, {"imports": imports, "missing": missing,
                    "valid": len(missing) == 0, "file": path}, None)

    def ValidateReferences(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        issues = []
        try:
            cur.execute(
                "SELECT method_id, method_name FROM methods WHERE class_id IS NOT NULL "
                "AND class_id NOT IN (SELECT class_id FROM classes)"
            )
            orphan_methods = cur.fetchall()
            for row in orphan_methods:
                issues.append({"type": "orphan_method", "method_id": row[0],
                               "method_name": row[1]})
            cur.execute(
                "SELECT class_id, class_name FROM classes WHERE file_id IS NOT NULL "
                "AND file_id NOT IN (SELECT file_id FROM files)"
            )
            orphan_classes = cur.fetchall()
            for row in orphan_classes:
                issues.append({"type": "orphan_class", "class_id": row[0],
                               "class_name": row[1]})
            cur.execute(
                "SELECT dst_id, dst_type FROM edges WHERE dst_type='method' "
                "AND dst_id NOT IN (SELECT method_id FROM methods)"
            )
            dangling_edges = cur.fetchall()
            for row in dangling_edges:
                issues.append({"type": "dangling_edge", "dst_id": row[0],
                               "dst_type": row[1]})
            cur.execute(
                "SELECT dst_id, dst_type FROM edges WHERE dst_type='class' "
                "AND dst_id NOT IN (SELECT class_id FROM classes)"
            )
            dangling_class_edges = cur.fetchall()
            for row in dangling_class_edges:
                issues.append({"type": "dangling_edge", "dst_id": row[0],
                               "dst_type": row[1]})
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"issues": issues, "count": len(issues),
                    "valid": len(issues) == 0}, None)

    def ValidateRuntime(self, params):
        path = self._p(params, "path")
        if path is None or not os.path.isfile(path):
            return (0, None, ("FILE_NOT_FOUND", str(path), 0))
        try:
            result = subprocess.run(
                [self.state["config"]["python_bin"], path],
                capture_output=True, text=True, timeout=30,
            )
        except subprocess.TimeoutExpired:
            return (1, {"valid": False, "error": "timeout", "file": path}, None)
        except Exception as exc:
            return (0, None, ("RUNTIME_ERROR", str(exc), 0))
        ok = result.returncode == 0
        return (1, {"valid": ok, "returncode": result.returncode,
                    "stderr": result.stderr[:500] if result.stderr else "",
                    "file": path}, None)

    def ValidateUnitTests(self, params):
        test_path = self._p(params, "test_path")
        if test_path is None or not os.path.isfile(test_path):
            return (1, {"valid": True, "reason": "no test file",
                        "passed": 0, "failed": 0}, None)
        try:
            result = subprocess.run(
                [self.state["config"]["python_bin"], "-m", "pytest",
                 test_path, "-v", "--tb=short"],
                capture_output=True, text=True,
                timeout=self.state["config"]["test_timeout"],
            )
        except subprocess.TimeoutExpired:
            return (1, {"valid": False, "error": "timeout",
                        "test_path": test_path}, None)
        except Exception as exc:
            return (0, None, ("TEST_ERROR", str(exc), 0))
        output = result.stdout + result.stderr
        passed = len(re.findall(r"PASSED|PASSED", output))
        failed = len(re.findall(r"FAILED|ERROR", output))
        ok = result.returncode == 0
        return (1, {"valid": ok, "passed": passed, "failed": failed,
                    "returncode": result.returncode,
                    "test_path": test_path}, None)

    def ValidateIntegrationTests(self, params):
        test_dir = self._p(params, "test_dir")
        if test_dir is None or not os.path.isdir(test_dir):
            return (1, {"valid": True, "reason": "no integration test dir",
                        "passed": 0, "failed": 0}, None)
        integration_files = []
        for root, dirs, files in os.walk(test_dir):
            for fname in files:
                if fname.startswith("test_integration") and fname.endswith(".py"):
                    integration_files.append(os.path.join(root, fname))
        if not integration_files:
            return (1, {"valid": True, "reason": "no integration tests found",
                        "passed": 0, "failed": 0}, None)
        total_passed = 0
        total_failed = 0
        errors = []
        for tf in integration_files:
            try:
                result = subprocess.run(
                    [self.state["config"]["python_bin"], "-m", "pytest",
                     tf, "-v", "--tb=short"],
                    capture_output=True, text=True,
                    timeout=self.state["config"]["test_timeout"],
                )
            except subprocess.TimeoutExpired:
                errors.append({"file": tf, "error": "timeout"})
                total_failed += 1
                continue
            except Exception as exc:
                errors.append({"file": tf, "error": str(exc)})
                total_failed += 1
                continue
            output = result.stdout + result.stderr
            passed = len(re.findall(r"PASSED", output))
            failed = len(re.findall(r"FAILED|ERROR", output))
            total_passed += passed
            total_failed += failed
            if result.returncode != 0:
                errors.append({"file": tf, "returncode": result.returncode})
        ok = total_failed == 0 and len(errors) == 0
        return (1, {"valid": ok, "passed": total_passed,
                    "failed": total_failed, "files_tested": len(integration_files),
                    "errors": errors[:20]}, None)

    def ValidateMemory(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        issues = []
        try:
            cur.execute("PRAGMA integrity_check")
            integrity = cur.fetchone()[0]
            if integrity != "ok":
                issues.append({"type": "integrity", "detail": integrity})
            cur.execute("PRAGMA foreign_key_check")
            fk_violations = cur.fetchall()
            for v in fk_violations:
                issues.append({"type": "fk_violation", "table": v[0],
                               "rowid": v[1]})
            page_size = cur.execute("PRAGMA page_size").fetchone()[0]
            page_count = cur.execute("PRAGMA page_count").fetchone()[0]
            db_size = page_size * page_count
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
            tables = [r[0] for r in cur.fetchall()]
            empty_tables = []
            for table in tables:
                cur.execute("SELECT COUNT(*) FROM " + table)
                count = cur.fetchone()[0]
                if count == 0:
                    empty_tables.append(table)
            if empty_tables:
                issues.append({"type": "empty_tables", "tables": empty_tables})
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        return (1, {"valid": len(issues) == 0, "issues": issues,
                    "db_size_bytes": db_size, "page_count": page_count,
                    "table_count": len(tables)}, None)

    def ValidateDatabase(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA integrity_check")
            integrity = cur.fetchone()[0]
            cur.execute("PRAGMA foreign_key_check")
            fk_violations = cur.fetchall()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
            tables = [r[0] for r in cur.fetchall()]
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name NOT LIKE 'sqlite_%'"
            )
            indexes = [r[0] for r in cur.fetchall()]
            duplicate_check = {}
            for table in tables:
                cur.execute("SELECT COUNT(*) FROM " + table)
                duplicate_check[table] = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        return (1, {"integrity": integrity,
                    "fk_violations": len(fk_violations),
                    "tables": len(tables), "indexes": len(indexes),
                    "row_counts": duplicate_check,
                    "valid": integrity == "ok" and len(fk_violations) == 0}, None)

    def ValidatePerformance(self, params):
        path = self._p(params, "path")
        if path is None or not os.path.isfile(path):
            return (0, None, ("FILE_NOT_FOUND", str(path), 0))
        baseline = self._p(params, "baseline", self.state["baselines"].get(path))
        try:
            start = time.perf_counter()
            result = subprocess.run(
                [self.state["config"]["python_bin"], path],
                capture_output=True, text=True, timeout=60,
            )
            elapsed = time.perf_counter() - start
        except subprocess.TimeoutExpired:
            return (1, {"valid": False, "error": "timeout",
                        "file": path}, None)
        except Exception as exc:
            return (0, None, ("PERF_ERROR", str(exc), 0))
        ok = result.returncode == 0
        perf_data = {"elapsed": round(elapsed, 4), "valid": ok,
                     "file": path, "returncode": result.returncode}
        if baseline is not None:
            delta = elapsed - baseline
            perf_data["baseline"] = baseline
            perf_data["delta"] = round(delta, 4)
            perf_data["regressed"] = delta > baseline * 0.2
            if perf_data["regressed"]:
                perf_data["valid"] = False
        self.state["baselines"][path] = elapsed
        return (1, perf_data, None)

    def ValidateRegression(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        regressions = []
        try:
            cur.execute(
                "SELECT method_id, method_name, hash FROM methods "
                "WHERE hash IS NOT NULL ORDER BY method_id"
            )
            current = cur.fetchall()
            cur.execute(
                "SELECT method_id, hash FROM snapshots "
                "WHERE snapshot_type='before_fix' "
                "AND method_id IN (SELECT method_id FROM methods) "
                "GROUP BY method_id HAVING MAX(snapshot_id)"
            )
            before_hashes = {r[0]: r[1] for r in cur.fetchall()}
            for method_id, method_name, current_hash in current:
                if method_id in before_hashes:
                    before_hash = before_hashes[method_id]
                    if before_hash != current_hash:
                        regressions.append({
                            "method_id": method_id,
                            "method_name": method_name,
                            "before_hash": before_hash,
                            "current_hash": current_hash,
                        })
            cur.execute(
                "SELECT method_id, method_name, returns_tuple3 "
                "FROM methods WHERE returns_tuple3=0"
            )
            tuple3_regressions = cur.fetchall()
            for row in tuple3_regressions:
                regressions.append({
                    "method_id": row[0],
                    "method_name": row[1],
                    "type": "tuple3_regression",
                })
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"regressions": regressions,
                    "count": len(regressions),
                    "valid": len(regressions) == 0}, None)
