# [@GHOST]
# Ghost header — Verify
# Purpose: Plan vs actual comparison. Automated verification runner.
# Layer: Called by GraphEngine after code execution.
# [@VBSTYLE]
# VBStyle: Run() dispatch, Tuple3 returns, self.state dict, PascalCase, UPPERCASE
# Rules: @ghost(33), @vbsty(34), @cstyle(35), @clshdr(36), @mthdr(37), @pascal(38), @upper(39), @print(22), @decorators(20), @hardcode(24), @underscore(19), @run(43), @t3(50), @state(41), @ctor(40), @memunit(32), @dismap(31)

import os
import sys
import ast
import json
import sqlite3
from Config_graph_engine import cfg


class Verify:
    """Plan vs actual verification. Runs automated checks on DB classes."""

    def __init__(self):
        self.state = {
            "db_path": cfg.DB_PATH,
            "domain": cfg.DOMAIN,
            "results": None,
        }

    def Run(self, command, params):
        """Dispatch entry point. Returns Tuple3(ok, data, error)."""
        if params is None:
            params = {}
        dispatch = {
            "check": self.Check,
            "missing": self.Missing,
            "extra": self.Extra,
            "report": self.Report,
            "all": self.RunAll,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, "unknown_command: {command}".format(command=command))
        return handler(params)

    def Check(self, params):
        """Run a single verification check by number (1-10)."""
        check_num = params.get("check_num")
        if not check_num:
            return (0, None, "missing_param: check_num")
        checks = self.GetChecks()
        if check_num < 1 or check_num > len(checks):
            return (0, None, "invalid_check: {num}".format(num=check_num))
        check = checks[check_num - 1]
        result = check["fn"]()
        return (1, {"check": check_num, "name": check["name"], "passed": result["passed"], "details": result["details"]}, None)

    def Missing(self, params):
        """Find classes in SPEC but not in DB."""
        spec_classes = params.get("spec_classes", [])
        if not spec_classes:
            return (0, None, "missing_param: spec_classes")
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        db_classes = cur.execute(
            "SELECT class_name FROM classes WHERE domain=?", (self.state["domain"],)
        ).fetchall()
        db_names = {row[0] for row in db_classes}
        db.close()
        missing = [name for name in spec_classes if name not in db_names]
        return (1, {"missing": missing, "count": len(missing)}, None)

    def Extra(self, params):
        """Find classes in DB but not in SPEC."""
        spec_classes = params.get("spec_classes", [])
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        db_classes = cur.execute(
            "SELECT class_name FROM classes WHERE domain=?", (self.state["domain"],)
        ).fetchall()
        db_names = {row[0] for row in db_classes}
        db.close()
        spec_set = set(spec_classes)
        extra = [name for name in db_names if name not in spec_set]
        return (1, {"extra": extra, "count": len(extra)}, None)

    def Report(self, params):
        """Generate a full verification report."""
        ok, data, err = self.RunAll(params)
        if not ok:
            return (0, data, err)
        checks = data["checks"]
        passed = sum(1 for c in checks if c["passed"])
        failed = len(checks) - passed
        report_lines = ["VERIFICATION REPORT", "=" * 40, ""]
        for c in checks:
            status = "PASS" if c["passed"] else "FAIL"
            report_lines.append("[{status}] Check {num}: {name}".format(status=status, num=c["check"], name=c["name"]))
        report_lines.append("")
        report_lines.append("Total: {total}, Passed: {passed}, Failed: {failed}".format(total=len(checks), passed=passed, failed=failed))
        report_text = "\n".join(report_lines)
        return (1, {"report": report_text, "passed": passed, "failed": failed, "total": len(checks)}, None)

    def RunAll(self, params):
        """Run all 10 verification checks."""
        checks = self.GetChecks()
        results = []
        for i, check in enumerate(checks, 1):
            result = check["fn"]()
            results.append({
                "check": i,
                "name": check["name"],
                "passed": result["passed"],
                "details": result["details"],
            })
        passed = sum(1 for r in results if r["passed"])
        self.state["results"] = results
        return (1, {"checks": results, "total": len(results), "passed": passed, "failed": len(results) - passed}, None)

    def GetChecks(self):
        """Return list of 10 verification check functions."""
        return [
            {"name": "Classes have Run() method", "fn": self.CheckRunMethod},
            {"name": "Methods return Tuple3", "fn": self.CheckTuple3},
            {"name": "No print() statements", "fn": self.CheckNoPrint},
            {"name": "No decorators", "fn": self.CheckNoDecorators},
            {"name": "VBStyle compliance", "fn": self.CheckVbstyle},
            {"name": "No hardcoded paths", "fn": self.CheckNoHardcode},
            {"name": "PascalCase classes", "fn": self.CheckPascalCase},
            {"name": "UPPERCASE constants", "fn": self.CheckUppercase},
            {"name": "self.state used (not self._)", "fn": self.CheckSelfState},
            {"name": "run_metrics has entries", "fn": self.CheckRunMetrics},
        ]

    def _QueryClasses(self):
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        rows = cur.execute(
            "SELECT class_name, class_code FROM classes WHERE domain=?", (self.state["domain"],)
        ).fetchall()
        db.close()
        return rows

    def CheckRunMethod(self):
        rows = self._QueryClasses()
        missing = [name for name, code in rows if code and "def Run(" not in code]
        return {"passed": len(missing) == 0, "details": {"missing_run": missing}}

    def CheckTuple3(self):
        rows = self._QueryClasses()
        missing = [name for name, code in rows if code and "Tuple3" not in code and "(0," not in code and "(1," not in code]
        return {"passed": len(missing) == 0, "details": {"missing_tuple3": missing}}

    def CheckNoPrint(self):
        rows = self._QueryClasses()
        found = [name for name, code in rows if code and "print(" in code]
        return {"passed": len(found) == 0, "details": {"has_print": found}}

    def CheckNoDecorators(self):
        rows = self._QueryClasses()
        found = [name for name, code in rows if code and "@" in code and "@" not in code.split("'")[0]]
        return {"passed": len(found) == 0, "details": {"has_decorators": found}}

    def CheckVbstyle(self):
        rows = self._QueryClasses()
        non_vb = [name for name, code in rows if code and "VBSTYLE" not in code and "VBStyle" not in code]
        return {"passed": len(non_vb) == 0, "details": {"non_vbstyle": non_vb}}

    def CheckNoHardcode(self):
        rows = self._QueryClasses()
        found = [name for name, code in rows if code and "/Users/" in code]
        return {"passed": len(found) == 0, "details": {"has_hardcode": found}}

    def CheckPascalCase(self):
        rows = self._QueryClasses()
        bad = [name for name, _ in rows if name and not name[0].isupper()]
        return {"passed": len(bad) == 0, "details": {"non_pascal": bad}}

    def CheckUppercase(self):
        rows = self._QueryClasses()
        bad = []
        for name, code in rows:
            if code:
                for line in code.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("self.") and "=" in stripped and not stripped[5:6].islower():
                        if stripped[5:6] != "_" and not stripped[5:6].isupper():
                            bad.append(name)
                            break
        return {"passed": len(bad) == 0, "details": {"non_uppercase_constants": bad}}

    def CheckSelfState(self):
        rows = self._QueryClasses()
        bad = [name for name, code in rows if code and "self._" in code]
        return {"passed": len(bad) == 0, "details": {"uses_self_underscore": bad}}

    def CheckRunMetrics(self):
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        count = cur.execute("SELECT COUNT(*) FROM run_metrics").fetchone()[0]
        db.close()
        return {"passed": count > 0, "details": {"run_metrics_count": count}}
