# [@GHOST]{[@file<vbs_test.py>][@domain<utility>][@role<test_engine>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<vbs_test_engine>][@return<tuple3>][@orch<SystemCheck>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{VBStyle test engine — assert, unit, integration, benchmark, mock, fixture, coverage, VBStyle compliance check}
# [@WCL]{[@self_contained<true>][@source<MySQL_VbstyleChecker+DomTesting+CodeTest>][@features<assert|unit|integration|benchmark|mock|fixture|coverage|vbs_check>]

import os
import ast
import time
import subprocess
import sys

from . import Config


class VbsTest:
    """VBStyle test engine — testing + VBStyle compliance in one.

    Features (extracted from MySQL vb_code_test):
    - VbstyleChecker (8 methods): check code, file, method, folder for VBStyle
    - DomTesting (10 methods): assert, unit, integration, benchmark, mock, fixture, coverage, skip, teardown, report
    - CodeTest (34 methods): compile, proof, sandbox, semantic equivalence

    Usage:
        from core.utility.vbs_test import VbsTest
        vt = VbsTest()
        code, result, err = vt.Run("vbs_check_file", {"path": "core/Dom_Gui/db.py"})
        code, result, err = vt.Run("unit", {"name": "test_add", "func": lambda: 1+1, "expected": 2})
        code, report, err = vt.Run("report")
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "results": [],
            "fixtures": {},
            "mocks": {},
            "passed": 0,
            "failed": 0,
            "skipped": 0,
        }
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "vbs_check": self.vbs_check,
            "vbs_check_file": self.vbs_check_file,
            "vbs_check_folder": self.vbs_check_folder,
            "vbs_check_method": self.vbs_check_method,
            "assert": self.assert_,
            "unit": self.unit,
            "integration": self.integration,
            "benchmark": self.benchmark,
            "mock": self.mock,
            "fixture": self.fixture,
            "coverage": self.coverage,
            "skip": self.skip,
            "teardown": self.teardown,
            "report": self.report,
            "compile_file": self.compile_file,
            "read_state": self.read_state,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", "Unknown: " + str(command), 0))
        return handler(params)

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def record(self, entry):
        self.state["results"].append(entry)
        if entry.get("passed") is True:
            self.state["passed"] += 1
        elif entry.get("passed") is False:
            self.state["failed"] += 1
        elif entry.get("skipped"):
            self.state["skipped"] += 1

    def vbs_check(self, params):
        code_text = params.get("code", "")
        if not code_text:
            return (0, None, ("EMPTY_CODE", "No code provided", 0))
        violations = []
        if "#[@GHOST]" not in code_text and "# [@GHOST]" not in code_text:
            violations.append({"rule": "GHOST_HEADER", "message": "Missing GHOST header"})
        if "#[@VBSTYLE]" not in code_text and "# [@VBSTYLE]" not in code_text:
            violations.append({"rule": "VBSTYLE_HEADER", "message": "Missing VBSTYLE header"})
        try:
            tree = ast.parse(code_text)
        except SyntaxError as e:
            return (0, None, ("SYNTAX_ERROR", str(e), e.lineno or 0))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                has_run = False
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name == "Run":
                            has_run = True
                        for stmt in ast.walk(item):
                            if isinstance(stmt, ast.Return):
                                if isinstance(stmt.value, ast.Tuple) and len(stmt.value.elts) != 3:
                                    violations.append({
                                        "rule": "TUPLE3_RETURN",
                                        "message": "Method {} must return Tuple3".format(item.name),
                                        "class": node.name, "line": stmt.lineno,
                                    })
                        if item.name == "__init__":
                            args = [a.arg for a in item.args.args]
                            if "self" not in args or "mem" not in args or "db" not in args or "param" not in args:
                                violations.append({
                                    "rule": "INIT_SIGNATURE",
                                    "message": "Class {} __init__ must have (self, mem, db, param)".format(node.name),
                                    "class": node.name,
                                })
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for stmt in ast.walk(item):
                            if isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Name) and stmt.func.id == "print":
                                violations.append({"rule": "PRINT_STATEMENT", "message": "Print in {}".format(item.name), "line": stmt.lineno})
                if not has_run:
                    violations.append({"rule": "MISSING_RUN", "message": "Class {} missing Run method".format(node.name), "class": node.name})
        if violations:
            return (0, {"violations": violations, "count": len(violations)}, ("VBSTYLE_VIOLATIONS", "{} violations".format(len(violations)), 0))
        return (1, {"status": "PASS", "violations": []}, None)

    def vbs_check_file(self, params):
        path = params.get("path")
        if not path or not os.path.exists(path):
            return (0, None, ("FILE_NOT_FOUND", path or "missing", 0))
        with open(path, "r") as f:
            code = f.read()
        return self.vbs_check({"code": code})

    def vbs_check_folder(self, params):
        folder = params.get("path")
        if not folder or not os.path.isdir(folder):
            return (0, None, ("FOLDER_NOT_FOUND", folder or "missing", 0))
        results = {}
        total_violations = 0
        files_checked = 0
        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for fname in sorted(files):
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                code, data, err = self.vbs_check_file({"path": fpath})
                files_checked += 1
                if code != 1:
                    v_count = data.get("count", 0) if data else 0
                    total_violations += v_count
                    results[fpath] = {"status": "FAIL", "violations": data.get("violations", []) if data else []}
                else:
                    results[fpath] = {"status": "PASS", "violations": []}
        if total_violations > 0:
            return (0, {"results": results, "files": files_checked, "violations": total_violations}, ("FOLDER_VIOLATIONS", "{} violations in {} files".format(total_violations, files_checked), 0))
        return (1, {"results": results, "files": files_checked, "violations": 0}, None)

    def vbs_check_method(self, params):
        code_text = params.get("code", "")
        method_name = params.get("method_name", "unknown")
        if not code_text:
            return (0, None, ("EMPTY_CODE", "No code", 0))
        try:
            tree = ast.parse(code_text)
        except SyntaxError as e:
            return (0, None, ("SYNTAX_ERROR", str(e), e.lineno or 0))
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name:
                has_return = False
                for stmt in ast.walk(node):
                    if isinstance(stmt, ast.Return):
                        has_return = True
                        if isinstance(stmt.value, ast.Tuple) and len(stmt.value.elts) != 3:
                            violations.append({"rule": "TUPLE3_RETURN", "message": "Must return Tuple3", "line": stmt.lineno})
                if not has_return:
                    violations.append({"rule": "MISSING_RETURN", "message": "Missing return", "line": node.lineno})
                for stmt in ast.walk(node):
                    if isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Name) and stmt.func.id == "print":
                        violations.append({"rule": "PRINT_STATEMENT", "message": "Print in {}".format(method_name), "line": stmt.lineno})
        if violations:
            return (0, {"violations": violations, "count": len(violations)}, ("METHOD_VIOLATIONS", "{} violations".format(len(violations)), 0))
        return (1, {"status": "PASS", "method": method_name}, None)

    def assert_(self, params):
        actual = params.get("actual")
        expected = params.get("expected")
        op = params.get("op", "eq")
        name = params.get("name", "assert")
        ok = False
        if op == "eq":
            ok = actual == expected
        elif op == "ne":
            ok = actual != expected
        elif op == "gt":
            ok = actual is not None and expected is not None and actual > expected
        elif op == "gte":
            ok = actual is not None and expected is not None and actual >= expected
        elif op == "lt":
            ok = actual is not None and expected is not None and actual < expected
        elif op == "lte":
            ok = actual is not None and expected is not None and actual <= expected
        elif op == "in":
            ok = actual in expected if expected else False
        elif op == "not_in":
            ok = actual not in expected if expected else True
        elif op == "is_none":
            ok = actual is None
        elif op == "is_not_none":
            ok = actual is not None
        elif op == "is_true":
            ok = actual is True
        elif op == "is_false":
            ok = actual is False
        self.record({"name": name, "passed": ok, "actual": actual, "expected": expected, "op": op})
        if ok:
            return (1, {"name": name, "passed": True}, None)
        return (0, {"name": name, "passed": False, "actual": actual, "expected": expected, "op": op}, ("ASSERT_FAIL", "{}: {} {} {}".format(name, actual, op, expected), 0))

    def unit(self, params):
        name = params.get("name", "unit")
        func = params.get("func")
        args = params.get("args", [])
        kwargs = params.get("kwargs", {})
        expected = params.get("expected")
        if not callable(func):
            self.record({"name": name, "passed": False, "error": "func not callable"})
            return (0, None, ("NOT_CALLABLE", "func not callable", 0))
        start = time.time()
        try:
            actual = func(*args, **kwargs)
            elapsed = time.time() - start
            if expected is not None:
                ok = actual == expected
            else:
                ok = True
            self.record({"name": name, "passed": ok, "actual": actual, "expected": expected, "elapsed": elapsed})
            if ok:
                return (1, {"name": name, "passed": True, "actual": actual, "elapsed": elapsed}, None)
            return (0, {"name": name, "passed": False, "actual": actual, "expected": expected}, ("UNIT_FAIL", "{}: expected {} got {}".format(name, expected, actual), 0))
        except Exception as e:
            elapsed = time.time() - start
            self.record({"name": name, "passed": False, "error": str(e), "elapsed": elapsed})
            return (0, None, ("UNIT_ERROR", "{}: {}".format(name, str(e)), 0))

    def integration(self, params):
        steps = params.get("steps", [])
        results = []
        passed = 0
        for step in steps:
            name = step.get("name", "step")
            func = step.get("func")
            args = step.get("args", [])
            kwargs = step.get("kwargs", {})
            if not callable(func):
                results.append({"name": name, "passed": False, "error": "not callable"})
                continue
            try:
                value = func(*args, **kwargs)
                results.append({"name": name, "passed": True, "value": value})
                passed += 1
            except Exception as e:
                results.append({"name": name, "passed": False, "error": str(e)})
        ok = passed == len(steps)
        self.record({"name": "integration", "passed": ok, "steps": results})
        if ok:
            return (1, {"steps": results, "passed": passed, "total": len(steps)}, None)
        return (0, {"steps": results, "passed": passed, "total": len(steps)}, ("INTEGRATION_FAIL", "{}/{} steps passed".format(passed, len(steps)), 0))

    def benchmark(self, params):
        iterations = int(params.get("iterations", 100))
        func = params.get("func")
        args = params.get("args", [])
        kwargs = params.get("kwargs", {})
        if not callable(func):
            return (0, None, ("NOT_CALLABLE", "func not callable", 0))
        times = []
        for i in range(iterations):
            start = time.time()
            func(*args, **kwargs)
            times.append(time.time() - start)
        avg = sum(times) / len(times) if times else 0
        mn = min(times) if times else 0
        mx = max(times) if times else 0
        result = {"iterations": iterations, "avg": round(avg, 6), "min": round(mn, 6), "max": round(mx, 6)}
        self.record({"name": "benchmark", "passed": True, "benchmark": result})
        return (1, result, None)

    def mock(self, params):
        name = params.get("name", "default")
        action = params.get("action", "set")
        if action == "set":
            self.state["mocks"][name] = params.get("returns")
            return (1, {"name": name, "set": True}, None)
        elif action == "get":
            return (1, {"name": name, "returns": self.state["mocks"].get(name)}, None)
        elif action == "clear":
            self.state["mocks"].pop(name, None)
            return (1, {"name": name, "cleared": True}, None)
        return (0, None, ("UNKNOWN_ACTION", action, 0))

    def fixture(self, params):
        name = params.get("name", "default")
        action = params.get("action", "set")
        if action == "set":
            self.state["fixtures"][name] = params.get("data")
            return (1, {"name": name, "set": True}, None)
        elif action == "get":
            return (1, {"name": name, "data": self.state["fixtures"].get(name)}, None)
        elif action == "clear":
            self.state["fixtures"].pop(name, None)
            return (1, {"name": name, "cleared": True}, None)
        return (0, None, ("UNKNOWN_ACTION", action, 0))

    def coverage(self, params):
        lines = params.get("lines", [])
        executed = params.get("executed", [])
        total = len(lines)
        covered = sum(1 for l in executed if l in lines)
        pct = round((covered / total * 100), 1) if total > 0 else 0
        missing = [l for l in lines if l not in executed]
        return (1, {"total": total, "covered": covered, "pct": pct, "missing": missing}, None)

    def skip(self, params):
        name = params.get("name", "test")
        reason = params.get("reason", "")
        self.record({"name": name, "passed": None, "skipped": True, "reason": reason})
        return (1, {"name": name, "skipped": True, "reason": reason}, None)

    def teardown(self, params):
        self.state["fixtures"] = {}
        self.state["mocks"] = {}
        cleared = len(self.state["results"])
        self.state["results"] = []
        self.state["passed"] = 0
        self.state["failed"] = 0
        self.state["skipped"] = 0
        return (1, {"cleared": cleared}, None)

    def report(self, params=None):
        total = self.state["passed"] + self.state["failed"] + self.state["skipped"]
        pct = round(self.state["passed"] / total * 100, 1) if total > 0 else 0
        lines = []
        for entry in self.state["results"]:
            if entry.get("skipped"):
                tag = "SKIP"
            elif entry.get("passed"):
                tag = "PASS"
            else:
                tag = "FAIL"
            line = "[{}] {}".format(tag, entry.get("name", "unknown"))
            if entry.get("error"):
                line += " — {}".format(entry["error"])
            if entry.get("elapsed"):
                line += " ({}s)".format(round(entry["elapsed"], 4))
            lines.append(line)
        lines.append("")
        lines.append("Total: {} passed, {} failed, {} skipped, {}% success".format(
            self.state["passed"], self.state["failed"], self.state["skipped"], pct
        ))
        return (1, "\n".join(lines), None)

    def compile_file(self, params):
        path = params.get("path")
        if not path or not os.path.exists(path):
            return (0, None, ("FILE_NOT_FOUND", path or "missing", 0))
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", path],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return (1, {"compiled": True, "path": path}, None)
        error_line = result.stderr.strip().split("\n")[-1] if result.stderr else "unknown"
        return (0, {"compiled": False, "path": path, "error": error_line}, ("COMPILE_FAIL", error_line, 0))
