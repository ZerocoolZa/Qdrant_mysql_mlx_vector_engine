#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/fix_engine.py"
# date="2026-06-26" author="Devin" session_id="phase3-knowledge"
# context="Project Digital Twin Phase 3 Section 12 Fix Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="fix_engine.py" domain="twin_fix" authority="FixEngine"}
# [@SUMMARY]{summary="Fix authority that finds errors, searches fixes, applies candidate fixes, compiles, tests, rolls back on failure and records outcomes."}
# [@CLASS]{class="FixEngine" domain="fix" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="find_error" type="command"}
# [@METHOD]{method="search_fixes" type="command"}
# [@METHOD]{method="apply_fix" type="command"}
# [@METHOD]{method="compile_check" type="command"}
# [@METHOD]{method="run_tests" type="command"}
# [@METHOD]{method="rollback" type="command"}
# [@METHOD]{method="record_outcome" type="command"}
# [@METHOD]{method="learn" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<FixEngine: finds errors, searches fixes, applies candidate fixes, compiles, tests, rolls back on failure, records outcomes. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
FixEngine -- authority for applying and validating fixes.
Implements Section 12 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: find_error, search_fixes, apply_fix, compile_check, run_tests,
          rollback, record_outcome, learn.
"""
import difflib
import os
import py_compile
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_TEST_FILE = "test_everything.py"
TEST_TIMEOUT = 120


class FixEngine:
    """Authority for finding, applying and validating fixes."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "test_file": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_TEST_FILE
                ),
                "base_dir": os.path.dirname(os.path.abspath(__file__)),
                "test_timeout": TEST_TIMEOUT,
            },
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
            "last_snapshot": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "find_error":
            return self.FindError(params)
        elif command == "search_fixes":
            return self.SearchFixes(params)
        elif command == "apply_fix":
            return self.ApplyFix(params)
        elif command == "compile_check":
            return self.CompileCheck(params)
        elif command == "run_tests":
            return self.RunTests(params)
        elif command == "rollback":
            return self.Rollback(params)
        elif command == "record_outcome":
            return self.RecordOutcome(params)
        elif command == "learn":
            return self.Learn(params)
        elif command == "compile_code":
            return self.CompileCode(params)
        elif command == "compare_output":
            return self.CompareOutput(params)
        elif command == "learn_result":
            return self.LearnResult(params)
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

    def Now(self):
        return datetime.now(timezone.utc).isoformat()

    def FindError(self, params):
        path = self._p(params, "path")
        if path is None:
            return (0, None, ("MISSING_PARAM", "path required", 0))
        if not os.path.isfile(path):
            return (0, None, ("FILE_NOT_FOUND", path, 0))
        try:
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as exc:
            record = {"file": path, "has_error": True, "error": str(exc)}
            return (1, record, None)
        record = {"file": path, "has_error": False, "error": None}
        return (1, record, None)

    def SearchFixes(self, params):
        problem = self._p(params, "problem", "")
        error_type = self._p(params, "error_type")
        limit = self._p(params, "limit", 10)
        conn = self.Connect()
        cur = conn.cursor()
        query = ("SELECT knowledge_id, problem, answer, confidence, fix_result "
                 "FROM knowledge WHERE answer IS NOT NULL AND answer != ''")
        values = []
        if error_type:
            query += " AND error_type=?"
            values.append(error_type)
        if problem:
            query += " AND problem LIKE ?"
            values.append("%" + problem + "%")
        query += " ORDER BY confidence DESC, fix_result DESC LIMIT ?"
        values.append(limit)
        cur.execute(query, values)
        fixes = [{"knowledge_id": r[0], "problem": r[1], "answer": r[2],
                  "confidence": r[3], "fix_result": r[4]} for r in cur.fetchall()]
        return (1, {"fixes": fixes, "count": len(fixes)}, None)

    def ApplyFix(self, params):
        method_id = self._p(params, "method_id")
        new_code = self._p(params, "new_code")
        if method_id is None or new_code is None:
            return (0, None, ("MISSING_PARAM", "method_id and new_code required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_code FROM methods WHERE method_id=?", (method_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("NOT_FOUND", "method not found", 0))
        before_code = row[0]
        self.state["last_snapshot"] = {
            "method_id": method_id, "before_code": before_code,
        }
        compile_check = self.CompileCode({"code": new_code})
        if compile_check[0] == 1 and not compile_check[1]["compiled"]:
            return (0, None, ("COMPILE_FAILED",
                              compile_check[1].get("error", "compile failed"), 0))
        try:
            cur.execute("UPDATE methods SET method_code=? WHERE method_id=?",
                        (new_code, method_id))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        record = {"method_id": method_id, "applied": True,
                  "compiled": compile_check[1]["compiled"]}
        return (1, record, None)

    def CompileCheck(self, params):
        path = self._p(params, "path")
        if path is None:
            return (0, None, ("MISSING_PARAM", "path required", 0))
        if not os.path.isfile(path):
            return (0, None, ("FILE_NOT_FOUND", path, 0))
        try:
            py_compile.compile(path, doraise=True)
            return (1, {"file": path, "compiled": True, "error": None}, None)
        except py_compile.PyCompileError as exc:
            return (1, {"file": path, "compiled": False, "error": str(exc)}, None)

    def RunTests(self, params):
        test_file = self._p(params, "test_file", self.state["config"]["test_file"])
        timeout = self._p(params, "timeout", self.state["config"]["test_timeout"])
        if not os.path.isfile(test_file):
            return (0, None, ("FILE_NOT_FOUND", test_file, 0))
        try:
            proc = subprocess.run(
                [sys.executable, test_file],
                capture_output=True, text=True, timeout=timeout,
                cwd=self.state["config"]["base_dir"],
            )
        except subprocess.TimeoutExpired:
            return (0, None, ("TIMEOUT", "tests timed out", 0))
        output = proc.stdout + proc.stderr
        passed = output.count("PASS")
        failed = output.count("FAIL")
        record = {
            "test_file": test_file,
            "returncode": proc.returncode,
            "passed": passed,
            "failed": failed,
            "output": output[-2000:],
        }
        return (1, record, None)

    def Rollback(self, params):
        snapshot = self._p(params, "snapshot", self.state.get("last_snapshot"))
        if snapshot is None:
            return (0, None, ("NO_SNAPSHOT", "no snapshot to rollback to", 0))
        method_id = snapshot["method_id"]
        before_code = snapshot["before_code"]
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute("UPDATE methods SET method_code=? WHERE method_id=?",
                        (before_code, method_id))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("ROLLBACK_FAILED", str(exc), 0))
        self.state["last_snapshot"] = None
        return (1, {"method_id": method_id, "rolled_back": True}, None)

    def RecordOutcome(self, params):
        method_id = self._p(params, "method_id")
        action = self._p(params, "action", "fix")
        compile_result = self._p(params, "compile_result")
        test_result = self._p(params, "test_result")
        error_text = self._p(params, "error_text")
        rolled_back = self._p(params, "rollback", 0)
        knowledge_id = self._p(params, "knowledge_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO attempts (method_id, action, compile_result, "
                "test_result, error_text, rollback, knowledge_id, created) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (method_id, action, compile_result, test_result, error_text,
                 rolled_back, knowledge_id, self.Now()),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"attempt_id": cur.lastrowid}, None)

    def Learn(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        success = self._p(params, "success", True)
        if knowledge_id is None:
            return (0, None, ("MISSING_PARAM", "knowledge_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        delta = 5 if success else -5
        try:
            cur.execute(
                "UPDATE knowledge SET confidence=MAX(0, MIN(100, confidence+?)) "
                "WHERE knowledge_id=?",
                (delta, knowledge_id),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "delta": delta}, None)

    def CompileCode(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        fd, tmp_path = tempfile.mkstemp(suffix=".py")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(code)
            try:
                py_compile.compile(tmp_path, doraise=True)
                return (1, {"compiled": True, "error": None,
                            "temp_file": tmp_path}, None)
            except py_compile.PyCompileError as exc:
                return (1, {"compiled": False, "error": str(exc),
                            "temp_file": tmp_path}, None)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def CompareOutput(self, params):
        before = self._p(params, "before")
        after = self._p(params, "after")
        if before is None or after is None:
            return (0, None, ("MISSING_PARAM",
                              "before and after required", 0))
        before_lines = before.splitlines() if isinstance(before, str) else list(before)
        after_lines = after.splitlines() if isinstance(after, str) else list(after)
        diff = list(difflib.unified_diff(before_lines, after_lines,
                                         fromfile="before", tofile="after"))
        before_passed = before.get("passed", 0) if isinstance(before, dict) else 0
        after_passed = after.get("passed", 0) if isinstance(after, dict) else 0
        before_failed = before.get("failed", 0) if isinstance(before, dict) else 0
        after_failed = after.get("failed", 0) if isinstance(after, dict) else 0
        record = {
            "diff": "\n".join(diff),
            "diff_lines": diff,
            "diff_count": len(diff),
            "identical": len(diff) == 0,
            "passed_delta": after_passed - before_passed,
            "failed_delta": after_failed - before_failed,
            "before_passed": before_passed,
            "after_passed": after_passed,
            "before_failed": before_failed,
            "after_failed": after_failed,
        }
        return (1, record, None)

    def LearnResult(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        outcome = self._p(params, "outcome", "success")
        answer = self._p(params, "answer")
        if knowledge_id is None and answer is None:
            return (0, None, ("MISSING_PARAM",
                              "knowledge_id or answer required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        if outcome == "success":
            delta = 5
        elif outcome == "failure":
            delta = -5
        else:
            delta = 0
        updated = 0
        try:
            if knowledge_id is not None:
                cur.execute(
                    "UPDATE knowledge SET confidence=MAX(0, MIN(100, confidence+?)), "
                    "fix_result=? WHERE knowledge_id=?",
                    (delta, outcome, knowledge_id),
                )
                updated = cur.rowcount
            else:
                cur.execute(
                    "UPDATE knowledge SET confidence=MAX(0, MIN(100, confidence+?)), "
                    "fix_result=? WHERE answer=?",
                    (delta, outcome, answer),
                )
                updated = cur.rowcount
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        record = {"knowledge_id": knowledge_id, "outcome": outcome,
                  "delta": delta, "rows_updated": updated}
        return (1, record, None)
