#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/fix_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 12: Fix Engine -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="fix_engine.py" domain="twin_fix" authority="FixEngine"}
# [@SUMMARY]{summary="Fix authority: find error, search similar, rank fixes, apply candidate, compile, run tests, compare output, rollback if failed, record outcome, learn result."}
# [@CLASS]{class="FixEngine" domain="fix" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="find_error" type="command"}
# [@METHOD]{method="search_similar" type="command"}
# [@METHOD]{method="rank_fixes" type="command"}
# [@METHOD]{method="apply_candidate" type="command"}
# [@METHOD]{method="compile" type="command"}
# [@METHOD]{method="run_tests" type="command"}
# [@METHOD]{method="compare_output" type="command"}
# [@METHOD]{method="rollback_if_failed" type="command"}
# [@METHOD]{method="record_outcome" type="command"}
# [@METHOD]{method="learn_result" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class FixEngine:
    """Authority for automated error fixing with rollback safety."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "python_bin": "python3",
            },
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
            "current_fix": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "find_error":
            return self.FindError(params)
        elif command == "search_similar":
            return self.SearchSimilar(params)
        elif command == "rank_fixes":
            return self.RankFixes(params)
        elif command == "apply_candidate":
            return self.ApplyCandidate(params)
        elif command == "compile_fix":
            return self.CompileFix(params)
        elif command == "run_tests":
            return self.RunTests(params)
        elif command == "compare_output":
            return self.CompareOutput(params)
        elif command == "rollback_if_failed":
            return self.RollbackIfFailed(params)
        elif command == "record_outcome":
            return self.RecordOutcome(params)
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
        return (1, self.state["db_conn"], None)

    def Now(self):
        return (1, datetime.now(timezone.utc).isoformat(), None)

    def FindError(self, params):
        error_text = self._p(params, "error_text")
        method_id = self._p(params, "method_id")
        if error_text is None and method_id is None:
            return (0, None, ("MISSING_PARAM",
                              "error_text or method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        if method_id is not None:
            cur.execute(
                "SELECT knowledge_id, problem, error_type, error_text, answer "
                "FROM knowledge WHERE method_id=? ORDER BY confidence DESC",
                (method_id,),
            )
        else:
            cur.execute(
                "SELECT knowledge_id, problem, error_type, error_text, answer "
                "FROM knowledge WHERE error_text LIKE ? ORDER BY confidence DESC",
                ("%" + error_text + "%",),
            )
        errors = [{"knowledge_id": r[0], "problem": r[1], "error_type": r[2],
                   "error_text": r[3], "answer": r[4]}
                  for r in cur.fetchall()]
        return (1, {"errors": errors, "count": len(errors)}, None)

    def SearchSimilar(self, params):
        problem = self._p(params, "problem", "")
        error_type = self._p(params, "error_type")
        limit = self._p(params, "limit", 10)
        conn = self.Connect()[1]
        cur = conn.cursor()
        query = ("SELECT knowledge_id, problem, answer, confidence, fix_result "
                 "FROM knowledge WHERE 1=1")
        values = []
        if error_type:
            query += " AND error_type=?"
            values.append(error_type)
        if problem:
            query += " AND problem LIKE ?"
            values.append("%" + problem + "%")
        query += " ORDER BY confidence DESC LIMIT ?"
        values.append(limit)
        cur.execute(query, values)
        results = [{"knowledge_id": r[0], "problem": r[1], "answer": r[2],
                    "confidence": r[3], "fix_result": r[4]}
                   for r in cur.fetchall()]
        return (1, {"results": results, "count": len(results)}, None)

    def RankFixes(self, params):
        fixes = self._p(params, "fixes", [])
        if not fixes:
            return (0, None, ("MISSING_PARAM", "fixes list required", 0))
        ranked = sorted(fixes, key=lambda f: f.get("confidence", 0), reverse=True)
        return (1, {"ranked": ranked}, None)

    def ApplyCandidate(self, params):
        method_id = self._p(params, "method_id")
        new_code = self._p(params, "new_code")
        if method_id is None or new_code is None:
            return (0, None, ("MISSING_PARAM",
                              "method_id and new_code required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_code FROM methods WHERE method_id=?",
                    (method_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
        old_code = row[0]
        try:
            cur.execute("UPDATE methods SET method_code=? WHERE method_id=?",
                        (new_code, method_id))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        self.state["current_fix"] = {
            "method_id": method_id, "old_code": old_code,
            "new_code": new_code, "applied": self.Now()[1],
        }
        return (1, self.state["current_fix"], None)

    def CompileFix(self, params):
        path = self._p(params, "path")
        if path is None or not os.path.isfile(path):
            return (0, None, ("FILE_NOT_FOUND", str(path), 0))
        try:
            result = subprocess.run(
                [self.state["config"]["python_bin"], "-m", "py_compile", path],
                capture_output=True, text=True, timeout=30,
            )
        except Exception as exc:
            return (0, None, ("COMPILE_ERROR", str(exc), 0))
        ok = result.returncode == 0
        return (1, {"compiled": ok, "stderr": result.stderr if not ok else ""}, None)

    def RunTests(self, params):
        test_path = self._p(params, "test_path")
        if test_path is None or not os.path.isfile(test_path):
            return (0, None, ("FILE_NOT_FOUND", str(test_path), 0))
        try:
            result = subprocess.run(
                [self.state["config"]["python_bin"], test_path],
                capture_output=True, text=True, timeout=60,
            )
        except Exception as exc:
            return (0, None, ("TEST_ERROR", str(exc), 0))
        ok = result.returncode == 0
        return (1, {"passed": ok, "stdout": result.stdout[-500:],
                    "stderr": result.stderr[-500:]}, None)

    def CompareOutput(self, params):
        expected = self._p(params, "expected")
        actual = self._p(params, "actual")
        if expected is None or actual is None:
            return (0, None, ("MISSING_PARAM",
                              "expected and actual required", 0))
        match = expected == actual
        return (1, {"match": match, "expected": expected, "actual": actual}, None)

    def RollbackIfFailed(self, params):
        success = self._p(params, "success", False)
        if success:
            return (1, {"rolled_back": False, "reason": "success"}, None)
        fix = self.state.get("current_fix")
        if fix is None:
            return (1, {"rolled_back": False, "reason": "no_fix"}, None)
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("UPDATE methods SET method_code=? WHERE method_id=?",
                        (fix["old_code"], fix["method_id"]))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("ROLLBACK_FAILED", str(exc), 0))
        self.state["current_fix"] = None
        return (1, {"rolled_back": True, "method_id": fix["method_id"]}, None)

    def RecordOutcome(self, params):
        method_id = self._p(params, "method_id")
        success = self._p(params, "success", False)
        error_text = self._p(params, "error_text", "")
        knowledge_id = self._p(params, "knowledge_id")
        fix = self.state.get("current_fix", {})
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO attempts (method_id, action, before_code, after_code, "
                "compile_result, test_result, error_text, rollback, knowledge_id, "
                "created) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (method_id, "fix", fix.get("old_code"), fix.get("new_code"),
                 1 if success else 0, 1 if success else 0, error_text,
                 0 if success else 1, knowledge_id, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"attempt_id": cur.lastrowid, "success": success}, None)

    def LearnResult(self, params):
        attempt_id = self._p(params, "attempt_id")
        success = self._p(params, "success", True)
        lesson = self._p(params, "lesson")
        if attempt_id is None:
            return (0, None, ("MISSING_PARAM", "attempt_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO observations (observation_type, subject, evidence, "
                "created) VALUES ('fix_lesson', ?, ?, ?)",
                (str(attempt_id), lesson or ("success" if success else "failure"),
                 self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"observation_id": cur.lastrowid}, None)
