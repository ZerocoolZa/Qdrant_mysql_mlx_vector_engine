#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/validation_engine.py"
# date="2026-06-26" author="Devin" session_id="phase5-quality"
# context="Project Digital Twin Phase 5 Section 13 Validation Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="validation_engine.py" domain="twin_validation" authority="ValidationEngine"}
# [@SUMMARY]{summary="Validation authority for syntax, imports, references, runtime and tests of the Project Digital Twin."}
# [@CLASS]{class="ValidationEngine" domain="validation" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="validate_syntax" type="command"}
# [@METHOD]{method="validate_imports" type="command"}
# [@METHOD]{method="validate_references" type="command"}
# [@METHOD]{method="validate_runtime" type="command"}
# [@METHOD]{method="validate_tests" type="command"}
# [@METHOD]{method="validate_all" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="Connect" type="helper"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<ValidationEngine: validates syntax imports references runtime tests of Project Digital Twin. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config Connect helper. No print no decorators no self._ violations.>][@todos<none>]}
"""
ValidationEngine -- authority for validating syntax, imports, references, runtime and tests.
Implements Section 13 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: validate_syntax, validate_imports, validate_references, validate_runtime, validate_tests, validate_all.
"""
import ast
import importlib
import json
import os
import py_compile
import sqlite3
import subprocess
import sys
import tempfile
import time
import tracemalloc
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
TEST_SCRIPT = "test_everything.py"


class ValidationEngine:
    """Authority for syntax, import, reference, runtime and test validation."""

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
        if command == "validate_syntax":
            return self.ValidateSyntax(params)
        elif command == "validate_imports":
            return self.ValidateImports(params)
        elif command == "validate_references":
            return self.ValidateReferences(params)
        elif command == "validate_runtime":
            return self.ValidateRuntime(params)
        elif command == "validate_tests":
            return self.ValidateTests(params)
        elif command == "validate_all":
            return self.ValidateAll(params)
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
        return self.state["db_conn"]

    def ResolveFilePath(self, params):
        file_path = self._p(params, "file_path")
        file_id = self._p(params, "file_id")
        if file_path:
            return file_path
        if file_id is None:
            return None
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("SELECT path FROM files WHERE file_id=?", (file_id,))
            row = cur.fetchone()
            if row:
                return row[0]
        except sqlite3.Error:
            pass
        return None

    def ValidateSyntax(self, params):
        file_path = self.ResolveFilePath(params)
        if not file_path:
            return (0, None, ("MISSING_PARAM", "file_path or file_id required", 0))
        if not os.path.isfile(file_path):
            return (0, None, ("FILE_NOT_FOUND", file_path, 0))
        try:
            py_compile.compile(file_path, doraise=True)
            result = {"passed": True, "error": None, "file_path": file_path}
            self.state["results"].append(result)
            return (1, result, None)
        except py_compile.PyCompileError as exc:
            result = {"passed": False, "error": str(exc), "file_path": file_path}
            self.state["results"].append(result)
            return (1, result, None)
        except OSError as exc:
            return (0, None, ("COMPILE_ERROR", str(exc), 0))

    def ValidateImports(self, params):
        file_path = self.ResolveFilePath(params)
        if not file_path:
            return (0, None, ("MISSING_PARAM", "file_path or file_id required", 0))
        if not os.path.isfile(file_path):
            return (0, None, ("FILE_NOT_FOUND", file_path, 0))
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                source = fh.read()
            tree = ast.parse(source, filename=file_path)
        except (SyntaxError, OSError) as exc:
            return (0, None, ("PARSE_ERROR", str(exc), 0))
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.append(node.module)
        failed_imports = []
        passed = True
        for mod in modules:
            try:
                importlib.import_module(mod)
            except Exception as exc:
                passed = False
                failed_imports.append({"module": mod, "error": str(exc)})
        result = {
            "passed": passed,
            "failed_imports": failed_imports,
            "checked": modules,
            "file_path": file_path,
        }
        self.state["results"].append(result)
        return (1, result, None)

    def ValidateReferences(self, params):
        file_path = self.ResolveFilePath(params)
        if not file_path:
            return (0, None, ("MISSING_PARAM", "file_path or file_id required", 0))
        if not os.path.isfile(file_path):
            return (0, None, ("FILE_NOT_FOUND", file_path, 0))
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                source = fh.read()
            tree = ast.parse(source, filename=file_path)
        except (SyntaxError, OSError) as exc:
            return (0, None, ("PARSE_ERROR", str(exc), 0))
        issues = []
        defined = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    defined.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    defined.add(alias.asname or alias.name)
            elif isinstance(node, ast.FunctionDef):
                defined.add(node.name)
            elif isinstance(node, ast.ClassDef):
                defined.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined.add(target.id)
            elif isinstance(node, ast.arg):
                defined.add(node.arg)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id not in defined and node.id not in dir(__builtins__):
                    issues.append(
                        {
                            "name": node.id,
                            "line": getattr(node, "lineno", 0),
                            "type": "unresolved_name",
                        }
                    )
        result = {
            "passed": len(issues) == 0,
            "issues": issues,
            "file_path": file_path,
        }
        self.state["results"].append(result)
        return (1, result, None)

    def ValidateRuntime(self, params):
        class_name = self._p(params, "class_name")
        file_path = self.ResolveFilePath(params)
        if not class_name:
            return (0, None, ("MISSING_PARAM", "class_name required", 0))
        if not file_path:
            return (0, None, ("MISSING_PARAM", "file_path or file_id required", 0))
        if not os.path.isfile(file_path):
            return (0, None, ("FILE_NOT_FOUND", file_path, 0))
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("_runtime_target", file_path)
            if spec is None or spec.loader is None:
                return (0, None, ("LOAD_FAILED", "Cannot load module spec", 0))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls = getattr(module, class_name, None)
            if cls is None:
                return (0, None, ("CLASS_NOT_FOUND", class_name, 0))
            instance = cls()
            run_method = getattr(instance, "Run", None)
            if run_method is None:
                return (0, None, ("NO_RUN", "Class has no Run method", 0))
            ok, data, err = run_method("read_state", {})
            if ok == 1:
                result = {
                    "passed": True,
                    "error": None,
                    "class_name": class_name,
                    "data": data,
                }
            else:
                result = {
                    "passed": False,
                    "error": str(err),
                    "class_name": class_name,
                    "data": None,
                }
            self.state["results"].append(result)
            return (1, result, None)
        except Exception as exc:
            result = {
                "passed": False,
                "error": str(exc),
                "class_name": class_name,
                "data": None,
            }
            self.state["results"].append(result)
            return (1, result, None)

    def ValidateTests(self, params):
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
        total = 0
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

    def ValidateAll(self, params):
        file_path = self.ResolveFilePath(params)
        if not file_path:
            return (0, None, ("MISSING_PARAM", "file_path or file_id required", 0))
        report = {"file_path": file_path, "checks": {}}
        syntax = self.ValidateSyntax(params)
        report["checks"]["syntax"] = syntax[1] if syntax[0] == 1 else {"error": syntax[2]}
        imports = self.ValidateImports(params)
        report["checks"]["imports"] = imports[1] if imports[0] == 1 else {"error": imports[2]}
        references = self.ValidateReferences(params)
        report["checks"]["references"] = (
            references[1] if references[0] == 1 else {"error": references[2]}
        )
        tests = self.ValidateTests(params)
        report["checks"]["tests"] = tests[1] if tests[0] == 1 else {"error": tests[2]}
        all_passed = True
        for check in report["checks"].values():
            if isinstance(check, dict) and check.get("passed") is False:
                all_passed = False
                break
        report["passed"] = all_passed
        report["created"] = datetime.now(timezone.utc).isoformat()
        self.state["results"].append(report)
        return (1, report, None)

    def ValidateMemory(self, params):
        callable_target = self._p(params, "callable")
        target = self._p(params, "target")
        if callable_target is None and target is None:
            return (0, None, ("MISSING_PARAM",
                              "callable or target required", 0))
        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()
        leak_detected = False
        error = None
        try:
            if callable_target is not None:
                callable_target()
        except Exception as exc:
            error = str(exc)
        snapshot_after = tracemalloc.take_snapshot()
        stats = snapshot_after.compare_to(snapshot_before, "lineno")
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        top_stats = []
        for stat in stats[:10]:
            top_stats.append({
                "file": str(stat.traceback),
                "size_diff": stat.size_diff,
                "count_diff": stat.count_diff,
            })
        if current > 0 and len(stats) > 0:
            total_diff = sum(s.size_diff for s in stats)
            if total_diff > 1024 * 1024:
                leak_detected = True
        result = {
            "passed": not leak_detected and error is None,
            "current_bytes": current,
            "peak_bytes": peak,
            "leak_detected": leak_detected,
            "error": error,
            "top_stats": top_stats,
        }
        self.state["results"].append(result)
        return (1, result, None)

    def ValidateDatabase(self, params):
        db_path = self._p(params, "db_path", self.state["config"]["db_path"])
        if not os.path.isfile(db_path):
            return (0, None, ("DB_NOT_FOUND", db_path, 0))
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        checks = {}
        try:
            cur.execute("PRAGMA integrity_check")
            integrity = cur.fetchone()[0]
            checks["integrity_check"] = integrity
            cur.execute("PRAGMA foreign_key_check")
            fk_violations = cur.fetchall()
            checks["foreign_key_violations"] = fk_violations
            cur.execute("PRAGMA quick_check")
            quick = cur.fetchone()[0]
            checks["quick_check"] = quick
        except sqlite3.Error as exc:
            conn.close()
            return (0, None, ("DB_ERROR", str(exc), 0))
        conn.close()
        passed = (integrity == "ok" and quick == "ok"
                  and len(fk_violations) == 0)
        result = {"passed": passed, "checks": checks, "db_path": db_path}
        self.state["results"].append(result)
        return (1, result, None)

    def ValidatePerformance(self, params):
        callable_target = self._p(params, "callable")
        iterations = self._p(params, "iterations", 1)
        if callable_target is None:
            return (0, None, ("MISSING_PARAM", "callable required", 0))
        timings = []
        error = None
        start_total = time.time()
        for _ in range(iterations):
            start = time.time()
            try:
                callable_target()
            except Exception as exc:
                error = str(exc)
                break
            timings.append(time.time() - start)
        total_time = time.time() - start_total
        avg = sum(timings) / len(timings) if timings else 0
        result = {
            "passed": error is None,
            "iterations": len(timings),
            "total_time": total_time,
            "average_time": avg,
            "min_time": min(timings) if timings else 0,
            "max_time": max(timings) if timings else 0,
            "timings": timings,
            "error": error,
        }
        self.state["results"].append(result)
        return (1, result, None)

    def ValidateRegression(self, params):
        current = self._p(params, "current")
        previous_observation_id = self._p(params, "previous_observation_id")
        subject = self._p(params, "subject", "test_run")
        if current is None:
            return (0, None, ("MISSING_PARAM", "current required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        previous = None
        if previous_observation_id is not None:
            cur.execute("SELECT evidence, confidence FROM observations WHERE observation_id=?",
                        (previous_observation_id,))
            row = cur.fetchone()
            if row:
                previous = row[0]
        else:
            cur.execute("SELECT evidence, confidence FROM observations WHERE subject=? ORDER BY created DESC LIMIT 1",
                        (subject,))
            row = cur.fetchone()
            if row:
                previous = row[0]
        regressed = False
        comparison = {}
        if previous is not None:
            try:
                prev_data = json.loads(previous)
            except (ValueError, TypeError):
                prev_data = {"raw": previous}
            if isinstance(current, dict) and isinstance(prev_data, dict):
                prev_passed = prev_data.get("passed", 0)
                curr_passed = current.get("passed", 0)
                prev_failed = prev_data.get("failed", 0)
                curr_failed = current.get("failed", 0)
                comparison = {
                    "prev_passed": prev_passed,
                    "curr_passed": curr_passed,
                    "prev_failed": prev_failed,
                    "curr_failed": curr_failed,
                    "passed_delta": curr_passed - prev_passed,
                    "failed_delta": curr_failed - prev_failed,
                }
                if curr_passed < prev_passed or curr_failed > prev_failed:
                    regressed = True
            else:
                comparison = {"previous": prev_data, "current": current}
                regressed = str(prev_data) != str(current)
        else:
            comparison = {"previous": None, "current": current}
            regressed = False
        result = {
            "passed": not regressed,
            "regressed": regressed,
            "comparison": comparison,
            "subject": subject,
        }
        self.state["results"].append(result)
        return (1, result, None)
