#!/usr/bin/env python3
#[@GHOST]{file_path="core/Dom_Common/ClassErrors.py" date="2026-07-04" author="devin" session_id="bcl-common-module" context="Self-learning error→fix system with live debugging / hot-fix + MySQL fact/law reporting + msearch→run_cmd→msearch→reason loop. In-RAM cache + MySQL sync."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="ClassErrors.py" domain="dom_common" authority="ErrorHandler"}
#[@SUMMARY]{summary="Self-learning error→fix system. Captures errors, compares to known, generates fixes, tests, promotes as BCL. Live debug: halt→fix→write back→re-run. Reports facts+laws to MySQL. msearch→run_cmd→msearch→reason loop."}
#[@CLASS]{class="ClassErrors" domain="dom_common" authority="ErrorHandler"}
#[@METHOD]{method="Init" type="ctor"}
#[@METHOD]{method="Run" type="dispatch"}
#[@METHOD]{method="Capture" type="command"}
#[@METHOD]{method="Compare" type="query"}
#[@METHOD]{method="Fix" type="command"}
#[@METHOD]{method="Test" type="command"}
#[@METHOD]{method="Promote" type="command"}
#[@METHOD]{method="Track" type="command"}
#[@METHOD]{method="LiveDebug" type="command"}
#[@METHOD]{method="HotFix" type="command"}
#[@METHOD]{method="LoadFromMySQL" type="command"}
#[@METHOD]{method="SyncToMySQL" type="command"}
#[@METHOD]{method="WriteBCL" type="command"}
#[@METHOD]{method="ReadBCL" type="command"}
#[@METHOD]{method="ReportFact" type="command"}
#[@METHOD]{method="ReportLaw" type="command"}
#[@METHOD]{method="Msearch" type="query"}
#[@METHOD]{method="Reason" type="query"}
#[@METHOD]{method="Loop" type="command"}
#[@METHOD]{method="ReadState" type="query"}
#[@METHOD]{method="SetConfig" type="command"}

"""
ClassErrors — Self-learning error→fix system with live debugging + MySQL reporting.

Loop:
  1. CAPTURE  — error text, traceback, file, line, class, method
  2. SIGNATURE — generate error signature
  3. COMPARE  — search in-RAM cache + MySQL error_knowledge
  4. FIX      — apply known fix OR generate candidate
  5. TEST     — apply fix, run py_compile, verify
  6. PROMOTE  — write BCL to file, sync MySQL, adjust confidence
  7. TRACK    — record in fix_attempts, update frequency

MySQL Reporting:
  - report_fact → code_index (entity, relationship, evidence)
  - report_law  → learned_rules (pattern, fix_action, confidence)

Search Loop:
  msearch(keyword) → get results → run_cmd → msearch again → reason
"""

import os
import re
import sys
import time
import json
import subprocess
import mysql.connector
from datetime import datetime

try:
    from Config import (
        MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_SOCKET, MYSQL_DB, MYSQL_PORT,
        ERROR_TYPES, FIX_TEMPLATES, ERROR_TO_FIX,
        MIN_CONFIDENCE, PROMOTE_THRESHOLD, DEMOTE_THRESHOLD,
        LIVE_DEBUG_MAX_RETRIES, LIVE_DEBUG_HALT_ON_ERROR,
        LIVE_DEBUG_WRITE_BACK, LIVE_DEBUG_RE_RUN,
        BCL_TOOL_PATH, BCL_TYPE_ERROR_FIX,
        ERROR_KNOWLEDGE_TABLE, FIX_ATTEMPTS_TABLE, EXECUTION_LOG_TABLE,
        LEARNED_RULES_TABLE,
    )
except ImportError:
    from .Config import (
        MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_SOCKET, MYSQL_DB, MYSQL_PORT,
        ERROR_TYPES, FIX_TEMPLATES, ERROR_TO_FIX,
        MIN_CONFIDENCE, PROMOTE_THRESHOLD, DEMOTE_THRESHOLD,
        LIVE_DEBUG_MAX_RETRIES, LIVE_DEBUG_HALT_ON_ERROR,
        LIVE_DEBUG_WRITE_BACK, LIVE_DEBUG_RE_RUN,
        BCL_TOOL_PATH, BCL_TYPE_ERROR_FIX,
        ERROR_KNOWLEDGE_TABLE, FIX_ATTEMPTS_TABLE, EXECUTION_LOG_TABLE,
        LEARNED_RULES_TABLE,
    )

MAX_CACHE = 500
MAX_FIX_LEN = 2048
MAX_TRACEBACK = 4096
MAX_BCL_FIX = 8192
MAX_SEARCH_RESULTS = 50


class ClassErrors:
    """Self-learning error→fix system with live debugging / hot-fix + MySQL reporting."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "initialized": True,
            "total_errors": 0,
            "total_fixed": 0,
            "total_promoted": 0,
            "total_failed": 0,
            "total_facts_reported": 0,
            "total_laws_reported": 0,
            "total_searches": 0,
            "total_loops": 0,
            "cache": {},
            "last_error": "none",
            "last_fix": "none",
            "last_signature": "none",
            "last_search_results": [],
            "last_reason": "none",
            "mysql_connected": False,
            "live_debug_active": False,
            "live_debug_retries": 0,
            "halt_on_error": LIVE_DEBUG_HALT_ON_ERROR,
            "write_back": LIVE_DEBUG_WRITE_BACK,
            "re_run": LIVE_DEBUG_RE_RUN,
            "max_retries": LIVE_DEBUG_MAX_RETRIES,
        }
        self._mem = mem
        self._db = db
        self._conn = None

    def _p(self, msg):
        """Helper — append to last_error state."""
        self.state["last_error"] = msg

    def Run(self, command, params=None):
        """Dispatch — route command to method."""
        dispatch = {
            "capture": self.Capture,
            "compare": self.Compare,
            "fix": self.Fix,
            "test": self.Test,
            "promote": self.Promote,
            "track": self.Track,
            "live_debug": self.LiveDebug,
            "hot_fix": self.HotFix,
            "load_mysql": self.LoadFromMySQL,
            "load_lessons": self.LoadLessons,
            "sync_mysql": self.SyncToMySQL,
            "write_bcl": self.WriteBCL,
            "read_bcl": self.ReadBCL,
            "report_fact": self.ReportFact,
            "report_law": self.ReportLaw,
            "msearch": self.Msearch,
            "reason": self.Reason,
            "loop": self.Loop,
            "infer": self.Infer,
            "read_state": self.ReadState,
            "set_config": self.SetConfig,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (404, "unknown command: " + str(command), 0))
        return handler(params)

    def _get_conn(self):
        """Get MySQL connection."""
        if self._conn and self._conn.is_connected():
            return self._conn
        try:
            self._conn = mysql.connector.connect(
                host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASS,
                database=MYSQL_DB, unix_socket=MYSQL_SOCKET,
                port=MYSQL_PORT if MYSQL_PORT else 3306,
            )
            self.state["mysql_connected"] = True
            return self._conn
        except Exception as e:
            self._p("mysql connect: " + str(e))
            self.state["mysql_connected"] = False
            return None

    def _now(self):
        """Current timestamp string."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _generate_signature(self, error_type, class_name="", method_name=""):
        """Generate error signature: TYPE:CLASS.METHOD or TYPE."""
        if class_name and method_name:
            return error_type + ":" + class_name + "." + method_name
        if class_name:
            return error_type + ":" + class_name
        return error_type

    def _extract_error_info(self, error_text):
        """Extract error type, class, method from error text/traceback."""
        error_type = "Unknown"
        class_name = ""
        method_name = ""
        for et in ERROR_TYPES:
            if et in error_text:
                error_type = et
                break
        class_match = re.search(r"class '(\w+)'", error_text)
        if class_match:
            class_name = class_match.group(1)
        method_match = re.search(r"attribute '(\w+)'", error_text)
        if method_match:
            method_name = method_match.group(1)
        line_match = re.search(r'File "([^"]+)", line (\d+)', error_text)
        file_path = line_match.group(1) if line_match else ""
        line_num = int(line_match.group(2)) if line_match else 0
        return {
            "error_type": error_type,
            "class_name": class_name,
            "method_name": method_name,
            "file_path": file_path,
            "line_num": line_num,
        }

    # ── CORE LOOP: capture → compare → fix → test → promote → track ──

    def Capture(self, params):
        """CAPTURE — capture error with context."""
        if params is None:
            params = {}
        error_text = params.get("error", "")
        traceback_text = params.get("traceback", "")
        file_path = params.get("file", "")
        class_name = params.get("class", "")
        method_name = params.get("method", "")
        if not error_text and traceback_text:
            error_text = traceback_text
        if not error_text:
            return (0, None, (2, "no error text provided", 0))
        info = self._extract_error_info(error_text)
        if not class_name:
            class_name = info["class_name"]
        if not method_name:
            method_name = info["method_name"]
        if not file_path:
            file_path = info["file_path"]
        error_type = info["error_type"]
        signature = self._generate_signature(error_type, class_name, method_name)
        captured = {
            "signature": signature,
            "error_type": error_type,
            "error_text": error_text[:MAX_TRACEBACK],
            "class_name": class_name,
            "method_name": method_name,
            "file_path": file_path,
            "line_num": info["line_num"],
            "timestamp": self._now(),
        }
        self.state["total_errors"] += 1
        self.state["last_error"] = error_text[:200]
        self.state["last_signature"] = signature
        return (1, captured, None)

    def Compare(self, params):
        """COMPARE — search in-RAM cache + MySQL for matching error signature."""
        if params is None:
            params = {}
        signature = params.get("signature", self.state.get("last_signature", ""))
        if not signature:
            return (0, None, (3, "no signature to compare", 0))
        cached = self.state["cache"].get(signature)
        if cached:
            return (1, {"matched": True, "source": "ram", "entry": cached}, None)
        conn = self._get_conn()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT signature, error_type, cause, solution, fix_code, "
                    "frequency, confidence FROM " + ERROR_KNOWLEDGE_TABLE +
                    " WHERE signature = %s", (signature,)
                )
                row = cursor.fetchone()
                cursor.close()
                if row:
                    entry = {
                        "signature": row["signature"],
                        "error_type": row["error_type"] or "",
                        "cause": row["cause"] or "",
                        "solution": row["solution"] or "",
                        "fix_code": row["fix_code"] or "",
                        "frequency": row["frequency"] or 0,
                        "confidence": float(row["confidence"]),
                    }
                    if len(self.state["cache"]) < MAX_CACHE:
                        self.state["cache"][signature] = entry
                    return (1, {"matched": True, "source": "mysql", "entry": entry}, None)
            except Exception as e:
                self._p("mysql compare: " + str(e))
        return (1, {"matched": False, "source": "none", "entry": None}, None)

    def Fix(self, params):
        """FIX — apply known fix OR generate candidate fix."""
        if params is None:
            params = {}
        signature = params.get("signature", "")
        error_type = params.get("error_type", "Unknown")
        error_text = params.get("error_text", "")
        entry = params.get("entry")
        if entry and entry.get("fix_code"):
            fix_code = entry["fix_code"]
            fix_source = "known"
            confidence = entry.get("confidence", MIN_CONFIDENCE)
        else:
            template = FIX_TEMPLATES.get(error_type)
            if template:
                fix_code = template.get("fix_description", "")
                examples = template.get("examples", [])
                if examples:
                    fix_code += "\nExample: " + examples[0].get("good", "")
                fix_source = "template"
                confidence = MIN_CONFIDENCE
            else:
                fix_code = "No known fix for " + error_type + ". Manual review required."
                fix_source = "none"
                confidence = 0.0
        fix_result = {
            "signature": signature,
            "error_type": error_type,
            "fix_code": fix_code[:MAX_FIX_LEN],
            "fix_source": fix_source,
            "confidence": confidence,
            "timestamp": self._now(),
        }
        self.state["last_fix"] = fix_code[:200]
        return (1, fix_result, None)

    def Test(self, params):
        """TEST — apply fix to in-RAM copy, run py_compile, verify."""
        if params is None:
            params = {}
        file_path = params.get("file", "")
        fix_code = params.get("fix_code", "")
        error_text = params.get("error_text", "")
        if not file_path or not os.path.exists(file_path):
            return (0, None, (4, "file not found: " + str(file_path), 0))
        original_content = ""
        try:
            with open(file_path, "r") as f:
                original_content = f.read()
        except Exception as e:
            return (0, None, (5, "cannot read file: " + str(e), 0))
        fixed_content = original_content
        if fix_code and fix_code != "none":
            lines = original_content.split("\n")
            for i, line in enumerate(lines):
                if "print(" in line and "NoPrint" in error_text:
                    lines[i] = line.replace("print(", "# print(")
                if "@property" in line or "@staticmethod" in line or "@classmethod" in line:
                    if "NoDecorators" in error_text:
                        lines[i] = "# " + line
            fixed_content = "\n".join(lines)
        compile_result = None
        try:
            compile(fixed_content, file_path, "exec")
            compile_result = "pass"
        except SyntaxError as e:
            compile_result = "syntax_error: " + str(e)
        except Exception as e:
            compile_result = "error: " + str(e)
        test_passed = (compile_result == "pass")
        test_result = {
            "file": file_path,
            "compile_result": compile_result,
            "passed": test_passed,
            "original_size": len(original_content),
            "fixed_size": len(fixed_content),
            "timestamp": self._now(),
        }
        if test_passed:
            self.state["total_fixed"] += 1
        else:
            self.state["total_failed"] += 1
        return (1, test_result, None)

    def Promote(self, params):
        """PROMOTE — write BCL to file, sync MySQL, adjust confidence."""
        if params is None:
            params = {}
        signature = params.get("signature", "")
        error_type = params.get("error_type", "")
        cause = params.get("cause", "")
        solution = params.get("solution", "")
        fix_code = params.get("fix_code", "")
        confidence = params.get("confidence", MIN_CONFIDENCE)
        file_path = params.get("file", "")
        test_passed = params.get("test_passed", False)
        if not signature:
            return (0, None, (6, "no signature to promote", 0))
        if test_passed and confidence < PROMOTE_THRESHOLD:
            confidence = PROMOTE_THRESHOLD
        if not test_passed and confidence > DEMOTE_THRESHOLD:
            confidence = max(DEMOTE_THRESHOLD, confidence - 0.1)
        entry = {
            "signature": signature,
            "error_type": error_type,
            "cause": cause,
            "solution": solution,
            "fix_code": fix_code[:MAX_FIX_LEN],
            "confidence": confidence,
            "frequency": 1,
            "last_seen": self._now(),
            "status": "promoted" if test_passed else "candidate",
        }
        if len(self.state["cache"]) < MAX_CACHE:
            self.state["cache"][signature] = entry
        bcl_packet = self._build_bcl_fix(entry)
        written = False
        if file_path and self.state.get("write_back", True) and test_passed:
            try:
                with open(file_path, "r") as f:
                    content = f.read()
                if BCL_TYPE_ERROR_FIX not in content:
                    with open(file_path, "a") as f:
                        f.write("\n" + bcl_packet + "\n")
                    written = True
            except Exception as e:
                self._p("write back: " + str(e))
        synced = self.SyncToMySQL({"entry": entry})
        if test_passed:
            self.state["total_promoted"] += 1
        promote_result = {
            "signature": signature,
            "confidence": confidence,
            "status": entry["status"],
            "bcl_written": written,
            "mysql_synced": synced[0] == 1,
            "bcl_packet": bcl_packet,
        }
        return (1, promote_result, None)

    def Track(self, params):
        """TRACK — record in fix_attempts, update frequency."""
        if params is None:
            params = {}
        signature = params.get("signature", "")
        result = params.get("result", "unknown")
        attempt_type = params.get("attempt_type", "auto")
        conn = self._get_conn()
        if not conn:
            return (0, None, (7, "mysql not connected", 0))
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO " + FIX_ATTEMPTS_TABLE +
                " (attempt_type, result) VALUES (%s, %s)",
                (attempt_type, result)
            )
            conn.commit()
            cursor.close()
            return (1, {"tracked": True, "result": result}, None)
        except Exception as e:
            self._p("track: " + str(e))
            return (0, None, (8, "track failed: " + str(e), 0))

    # ── LIVE DEBUG: halt → fix → write back → re-run ──

    def LiveDebug(self, params):
        """LIVE DEBUG — halt execution, capture, fix, write back, re-run."""
        if params is None:
            params = {}
        error_text = params.get("error", "")
        traceback_text = params.get("traceback", "")
        file_path = params.get("file", "")
        class_name = params.get("class", "")
        method_name = params.get("method", "")
        max_retries = params.get("max_retries", self.state.get("max_retries", 3))
        self.state["live_debug_active"] = True
        self.state["live_debug_retries"] = 0
        for attempt in range(max_retries):
            self.state["live_debug_retries"] = attempt + 1
            cap_result = self.Capture({
                "error": error_text, "traceback": traceback_text,
                "file": file_path, "class": class_name, "method": method_name,
            })
            if cap_result[0] != 1:
                continue
            captured = cap_result[1]
            cmp_result = self.Compare({"signature": captured["signature"]})
            entry = None
            if cmp_result[0] == 1 and cmp_result[1].get("matched"):
                entry = cmp_result[1].get("entry")
            fix_result = self.Fix({
                "signature": captured["signature"],
                "error_type": captured["error_type"],
                "error_text": captured["error_text"],
                "entry": entry,
            })
            if fix_result[0] != 1:
                continue
            fix_data = fix_result[1]
            test_result = self.Test({
                "file": file_path,
                "fix_code": fix_data["fix_code"],
                "error_text": captured["error_text"],
            })
            if test_result[0] != 1:
                continue
            test_data = test_result[1]
            if test_data["passed"]:
                prom_result = self.Promote({
                    "signature": captured["signature"],
                    "error_type": captured["error_type"],
                    "cause": captured["error_text"][:200],
                    "solution": fix_data["fix_code"][:200],
                    "fix_code": fix_data["fix_code"],
                    "confidence": fix_data["confidence"],
                    "file": file_path,
                    "test_passed": True,
                })
                self.Track({
                    "signature": captured["signature"],
                    "result": "success",
                    "attempt_type": "auto",
                })
                self.state["live_debug_active"] = False
                return (1, {
                    "fixed": True,
                    "attempts": attempt + 1,
                    "signature": captured["signature"],
                    "fix_source": fix_data["fix_source"],
                    "confidence": fix_data["confidence"],
                    "re_run": self.state.get("re_run", True),
                }, None)
            else:
                self.Track({
                    "signature": captured["signature"],
                    "result": "failed",
                    "attempt_type": "auto",
                })
        self.state["live_debug_active"] = False
        return (0, None, (9, "live debug failed after " + str(max_retries) + " retries", 0))

    def HotFix(self, params):
        """HOT FIX — alias for LiveDebug."""
        return self.LiveDebug(params)

    # ── MYSQL LOAD/SYNC ──

    def LoadFromMySQL(self, params):
        """Load error knowledge from MySQL into in-RAM cache."""
        if params is None:
            params = {}
        limit = params.get("limit", 100)
        conn = self._get_conn()
        if not conn:
            return (0, None, (10, "mysql not connected", 0))
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT signature, error_type, cause, solution, fix_code, "
                "frequency, confidence FROM " + ERROR_KNOWLEDGE_TABLE +
                " ORDER BY confidence DESC LIMIT %s", (limit,)
            )
            rows = cursor.fetchall()
            cursor.close()
            loaded = 0
            for row in rows:
                sig = row["signature"]
                if sig and len(self.state["cache"]) < MAX_CACHE:
                    self.state["cache"][sig] = {
                        "signature": sig,
                        "error_type": row["error_type"] or "",
                        "cause": row["cause"] or "",
                        "solution": row["solution"] or "",
                        "fix_code": row["fix_code"] or "",
                        "frequency": row["frequency"] or 0,
                        "confidence": float(row["confidence"] or 0.5),
                    }
                    loaded += 1
            return (1, {"loaded": loaded, "cache_size": len(self.state["cache"])}, None)
        except Exception as e:
            self._p("load mysql: " + str(e))
            return (0, None, (11, "load failed: " + str(e), 0))

    def LoadLessons(self, params):
        """LOAD LESSONS — load broken→fixed code pairs from ErrorFixTrainer.db into in-RAM cache.

        The SQLite DB has 280 lessons: 20 per error type (10 standard Python errors)
        + 10 per session-learned rule (8 session rules).
        Each lesson: error_text, error_name, root_cause, repair, broken_code, fixed_code, confidence.
        """
        if params is None:
            params = {}
        import sqlite3
        db_path = params.get("db_path", os.path.join(
            os.path.expanduser("~/Qdrant_mysql_mlx_vector_engine"),
            "Cascade_toolStack", "bin_tools", "ErrorFixTrainer.db"
        ))
        if not os.path.exists(db_path):
            return (0, None, (19, "ErrorFixTrainer.db not found: " + db_path, 0))
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, error_text, error_name, root_cause, repair, "
                "broken_code, fixed_code, confidence FROM lessons"
            )
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
        except Exception as e:
            return (0, None, (20, "sqlite load failed: " + str(e), 0))
        lessons = {}
        loaded = 0
        for row in rows:
            name = row["error_name"]
            if name not in lessons:
                lessons[name] = []
            lesson = {
                "id": row["id"],
                "error_text": row["error_text"] or "",
                "error_name": name,
                "root_cause": row["root_cause"] or "",
                "repair": row["repair"] or "",
                "broken_code": row["broken_code"] or "",
                "fixed_code": row["fixed_code"] or "",
                "confidence": float(row["confidence"] or 50) / 100.0,
            }
            lessons[name].append(lesson)
            loaded += 1
        self.state["lessons"] = lessons
        self.state["total_lessons"] = loaded
        return (1, {
            "loaded": loaded,
            "error_types": list(lessons.keys()),
            "per_type": {k: len(v) for k, v in lessons.items()},
        }, None)

    def Infer(self, params):
        """INFER — in-RAM inference: match error text to lessons, return best broken→fixed pair.

        Uses the 280 lessons loaded by LoadLessons. Matches by error_name keyword,
        then picks the highest-confidence lesson for that error type.
        Returns the broken_code and fixed_code so the caller can apply the fix.
        """
        if params is None:
            params = {}
        error_text = params.get("error_text", "")
        error_type = params.get("error_type", "")
        if not error_text:
            return (0, None, (34, "no error_text for infer", 0))
        lessons = self.state.get("lessons", {})
        if not lessons:
            load_result = self.LoadLessons({})
            if load_result[0] != 1:
                return (0, None, (35, "no lessons loaded — run load_lessons first", 0))
            lessons = self.state.get("lessons", {})
        if not error_type:
            for et in ERROR_TYPES:
                if et in error_text:
                    error_type = et
                    break
        if not error_type:
            error_lower = error_text.lower()
            for name in lessons.keys():
                if name.lower() in error_lower:
                    error_type = name
                    break
        if not error_type:
            return (1, {"found": False, "message": "no matching error type in lessons"}, None)
        candidates = lessons.get(error_type, [])
        if not candidates:
            for name, lesson_list in lessons.items():
                if error_type.lower() in name.lower() or name.lower() in error_type.lower():
                    candidates = lesson_list
                    break
        if not candidates:
            return (1, {"found": False, "message": "no lessons for: " + error_type}, None)
        best = max(candidates, key=lambda l: l.get("confidence", 0))
        return (1, {
            "found": True,
            "source": "in_ram_lessons",
            "error_name": best["error_name"],
            "root_cause": best["root_cause"],
            "repair": best["repair"],
            "broken_code": best["broken_code"],
            "fixed_code": best["fixed_code"],
            "confidence": best["confidence"],
            "lesson_id": best["id"],
            "total_candidates": len(candidates),
        }, None)

    def SyncToMySQL(self, params):
        """Sync an error entry to MySQL error_knowledge table."""
        if params is None:
            params = {}
        entry = params.get("entry")
        if not entry:
            return (0, None, (12, "no entry to sync", 0))
        conn = self._get_conn()
        if not conn:
            return (0, None, (13, "mysql not connected", 0))
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO " + ERROR_KNOWLEDGE_TABLE +
                " (signature, error_type, cause, solution, fix_code, frequency, confidence) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE cause=%s, solution=%s, fix_code=%s, "
                "frequency=frequency+1, confidence=%s, last_seen=NOW()",
                (
                    entry["signature"], entry.get("error_type", ""),
                    entry.get("cause", ""), entry.get("solution", ""),
                    entry.get("fix_code", ""), entry.get("frequency", 1),
                    entry.get("confidence", MIN_CONFIDENCE),
                    entry.get("cause", ""), entry.get("solution", ""),
                    entry.get("fix_code", ""), entry.get("confidence", MIN_CONFIDENCE),
                )
            )
            conn.commit()
            cursor.close()
            return (1, {"synced": True, "signature": entry["signature"]}, None)
        except Exception as e:
            self._p("sync mysql: " + str(e))
            return (0, None, (14, "sync failed: " + str(e), 0))

    # ── BCL READ/WRITE ──

    def _build_bcl_fix(self, entry):
        """Build BCL packet for an error fix."""
        lines = [
            "#[@ERROR_FIX]{[@SIGNATURE]{" + entry.get("signature", "") + "}",
            "#[@ERROR_TYPE]{" + entry.get("error_type", "") + "}",
            "#[@CAUSE]{" + entry.get("cause", "")[:200] + "}",
            "#[@SOLUTION]{" + entry.get("solution", "")[:200] + "}",
            "#[@FIX_CODE]{" + entry.get("fix_code", "")[:500] + "}",
            "#[@CONFIDENCE]{" + str(entry.get("confidence", 0.0)) + "}",
            "#[@FREQUENCY]{" + str(entry.get("frequency", 1)) + "}",
            "#[@LAST_SEEN]{" + entry.get("last_seen", self._now()) + "}",
            "#[@STATUS]{" + entry.get("status", "candidate") + "}}",
        ]
        return "\n".join(lines)

    def WriteBCL(self, params):
        """Write error fix as BCL packet to a file."""
        if params is None:
            params = {}
        entry = params.get("entry")
        file_path = params.get("file", "")
        if not entry or not file_path:
            return (0, None, (15, "no entry or file path", 0))
        bcl_packet = self._build_bcl_fix(entry)
        try:
            with open(file_path, "a") as f:
                f.write("\n" + bcl_packet + "\n")
            return (1, {"written": True, "file": file_path}, None)
        except Exception as e:
            return (0, None, (16, "write failed: " + str(e), 0))

    def ReadBCL(self, params):
        """Read error fix BCL packets from a file."""
        if params is None:
            params = {}
        file_path = params.get("file", "")
        if not file_path or not os.path.exists(file_path):
            return (0, None, (17, "file not found: " + str(file_path), 0))
        try:
            with open(file_path, "r") as f:
                content = f.read()
            fixes = []
            pattern = r"#\[@ERROR_FIX\]\{(.*?)\}\}"
            matches = re.findall(pattern, content, re.DOTALL)
            for match in matches:
                entry = {}
                for tag in ["SIGNATURE", "ERROR_TYPE", "CAUSE", "SOLUTION",
                            "FIX_CODE", "CONFIDENCE", "FREQUENCY", "LAST_SEEN", "STATUS"]:
                    tag_match = re.search(r"\[@" + tag + r"\]\{([^}]*)\}", match)
                    if tag_match:
                        entry[tag.lower()] = tag_match.group(1)
                fixes.append(entry)
            return (1, {"fixes": fixes, "count": len(fixes)}, None)
        except Exception as e:
            return (0, None, (18, "read failed: " + str(e), 0))

    # ── MYSQL REPORTING: facts + laws ──

    def ReportFact(self, params):
        """REPORT FACT — write a fact to MySQL code_index table.

        Facts are entity-relationship-evidence triples:
          entity_name + entity_type + relationship + related_entity + evidence

        Example: ClassBCL 'contains' parse method, evidence='BCL parser state machine'
        """
        if params is None:
            params = {}
        entity_name = params.get("entity_name", "")
        entity_type = params.get("entity_type", "concept")
        relationship = params.get("relationship", "defined_in")
        related_entity = params.get("related_entity", "")
        evidence = params.get("evidence", "")
        source_file = params.get("source_file", "")
        source_line = params.get("source_line", None)
        if not entity_name:
            return (0, None, (20, "no entity_name for fact", 0))
        conn = self._get_conn()
        if not conn:
            return (0, None, (21, "mysql not connected", 0))
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO code_index "
                "(source_db, source_table, source_file, source_line, "
                " entity_name, entity_type, relationship, related_entity, evidence) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    MYSQL_DB, "dom_common", source_file, source_line,
                    entity_name, entity_type, relationship, related_entity, evidence,
                )
            )
            conn.commit()
            fact_id = cursor.lastrowid
            cursor.close()
            self.state["total_facts_reported"] += 1
            return (1, {
                "reported": True, "fact_id": fact_id,
                "entity": entity_name, "relationship": relationship,
                "related": related_entity,
            }, None)
        except Exception as e:
            self._p("report fact: " + str(e))
            return (0, None, (22, "report fact failed: " + str(e), 0))

    def ReportLaw(self, params):
        """REPORT LAW — write a law/rule to MySQL learned_rules table.

        Laws are pattern → fix_action pairs with confidence:
          pattern + fix_action + trigger_condition + confidence

        Example: pattern='NoPrint in VBStyle file', fix_action='Replace with Report.Run()'
        """
        if params is None:
            params = {}
        pattern = params.get("pattern", "")
        fix_action = params.get("fix_action", "")
        trigger_condition = params.get("trigger_condition", "")
        language = params.get("language", "python")
        category = params.get("category", "vbstyle")
        severity = params.get("severity", 2)
        confidence = params.get("confidence", MIN_CONFIDENCE)
        source = params.get("source", "dom_common")
        if not pattern or not fix_action:
            return (0, None, (23, "no pattern or fix_action for law", 0))
        conn = self._get_conn()
        if not conn:
            return (0, None, (24, "mysql not connected", 0))
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO " + LEARNED_RULES_TABLE +
                " (pattern, trigger_condition, fix_action, language, category, "
                "  severity, confidence, source) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    pattern, trigger_condition, fix_action,
                    language, category, severity, confidence, source,
                )
            )
            conn.commit()
            rule_id = cursor.lastrowid
            cursor.close()
            self.state["total_laws_reported"] += 1
            return (1, {
                "reported": True, "rule_id": rule_id,
                "pattern": pattern, "fix_action": fix_action,
                "confidence": confidence,
            }, None)
        except Exception as e:
            self._p("report law: " + str(e))
            return (0, None, (25, "report law failed: " + str(e), 0))

    # ── MSEARCH: search across MySQL tables ──

    def Msearch(self, params):
        """MSEARCH — search across MySQL tables for a keyword.

        Searches: error_knowledge, learned_rules, know_problems, know_solutions, code_index
        Returns aggregated results from all tables.
        """
        if params is None:
            params = {}
        keyword = params.get("keyword", "")
        limit = params.get("limit", 10)
        tables = params.get("tables", ["error_knowledge", "learned_rules",
                                       "know_problems", "know_solutions", "code_index"])
        if not keyword:
            return (0, None, (26, "no keyword for msearch", 0))
        conn = self._get_conn()
        if not conn:
            return (0, None, (27, "mysql not connected", 0))
        all_results = []
        try:
            cursor = conn.cursor(dictionary=True)
            for table in tables:
                if table == "error_knowledge":
                    sql = ("SELECT signature, error_type, cause, solution, "
                           "confidence, frequency FROM error_knowledge "
                           "WHERE signature LIKE %s OR error_type LIKE %s "
                           "OR cause LIKE %s OR solution LIKE %s "
                           "ORDER BY confidence DESC LIMIT %s")
                    cursor.execute(sql, ("%" + keyword + "%", "%" + keyword + "%",
                                         "%" + keyword + "%", "%" + keyword + "%", limit))
                    for row in cursor.fetchall():
                        all_results.append({
                            "table": "error_knowledge",
                            "signature": row.get("signature", ""),
                            "type": row.get("error_type", ""),
                            "cause": row.get("cause", "")[:100],
                            "solution": row.get("solution", "")[:100],
                            "confidence": float(row.get("confidence", 0)),
                            "frequency": row.get("frequency", 0),
                        })
                elif table == "learned_rules":
                    sql = ("SELECT id, pattern, fix_action, confidence, "
                           "success_count, failure_count FROM learned_rules "
                           "WHERE pattern LIKE %s OR fix_action LIKE %s "
                           "ORDER BY confidence DESC LIMIT %s")
                    cursor.execute(sql, ("%" + keyword + "%", "%" + keyword + "%", limit))
                    for row in cursor.fetchall():
                        all_results.append({
                            "table": "learned_rules",
                            "id": row.get("id", 0),
                            "pattern": row.get("pattern", "")[:100],
                            "fix_action": row.get("fix_action", "")[:100],
                            "confidence": float(row.get("confidence", 0)),
                            "success_count": row.get("success_count", 0),
                            "failure_count": row.get("failure_count", 0),
                        })
                elif table == "know_problems":
                    sql = ("SELECT id, problem, description FROM know_problems "
                           "WHERE problem LIKE %s OR description LIKE %s "
                           "LIMIT %s")
                    cursor.execute(sql, ("%" + keyword + "%", "%" + keyword + "%", limit))
                    for row in cursor.fetchall():
                        all_results.append({
                            "table": "know_problems",
                            "id": row.get("id", 0),
                            "problem": row.get("problem", ""),
                            "description": row.get("description", "")[:100],
                        })
                elif table == "know_solutions":
                    sql = ("SELECT id, solution, fault_code, scope, weight "
                           "FROM know_solutions "
                           "WHERE solution LIKE %s OR fault_code LIKE %s "
                           "ORDER BY weight DESC LIMIT %s")
                    cursor.execute(sql, ("%" + keyword + "%", "%" + keyword + "%", limit))
                    for row in cursor.fetchall():
                        all_results.append({
                            "table": "know_solutions",
                            "id": row.get("id", 0),
                            "solution": row.get("solution", "")[:100],
                            "fault_code": row.get("fault_code", ""),
                            "scope": row.get("scope", ""),
                            "weight": float(row.get("weight", 0)),
                        })
                elif table == "code_index":
                    sql = ("SELECT fact_id, entity_name, entity_type, "
                           "relationship, related_entity, evidence "
                           "FROM code_index "
                           "WHERE entity_name LIKE %s OR related_entity LIKE %s "
                           "OR evidence LIKE %s "
                           "LIMIT %s")
                    cursor.execute(sql, ("%" + keyword + "%", "%" + keyword + "%",
                                         "%" + keyword + "%", limit))
                    for row in cursor.fetchall():
                        all_results.append({
                            "table": "code_index",
                            "fact_id": row.get("fact_id", 0),
                            "entity": row.get("entity_name", ""),
                            "entity_type": row.get("entity_type", ""),
                            "relationship": row.get("relationship", ""),
                            "related": row.get("related_entity", ""),
                            "evidence": row.get("evidence", "")[:100],
                        })
            cursor.close()
        except Exception as e:
            self._p("msearch: " + str(e))
            return (0, None, (28, "msearch failed: " + str(e), 0))
        self.state["total_searches"] += 1
        self.state["last_search_results"] = all_results[:MAX_SEARCH_RESULTS]
        return (1, {
            "keyword": keyword,
            "results": all_results[:MAX_SEARCH_RESULTS],
            "count": len(all_results),
            "tables_searched": tables,
        }, None)

    # ── REASON: take search results + context → produce recommendation ──

    def Reason(self, params):
        """REASON — take msearch results + context and produce a recommendation.

        Analyzes search results to find:
        - Highest confidence fix
        - Most frequent error pattern
        - Related laws/rules
        - Evidence from code_index
        Produces a structured recommendation.
        """
        if params is None:
            params = {}
        results = params.get("results", self.state.get("last_search_results", []))
        context = params.get("context", "")
        error_type = params.get("error_type", "")
        if not results:
            return (0, None, (29, "no results to reason about", 0))
        errors_found = []
        rules_found = []
        problems_found = []
        solutions_found = []
        facts_found = []
        for r in results:
            tbl = r.get("table", "")
            if tbl == "error_knowledge":
                errors_found.append(r)
            elif tbl == "learned_rules":
                rules_found.append(r)
            elif tbl == "know_problems":
                problems_found.append(r)
            elif tbl == "know_solutions":
                solutions_found.append(r)
            elif tbl == "code_index":
                facts_found.append(r)
        best_fix = None
        best_confidence = 0.0
        for e in errors_found:
            conf = e.get("confidence", 0)
            if conf > best_confidence:
                best_confidence = conf
                best_fix = e
        best_rule = None
        best_rule_conf = 0.0
        for r in rules_found:
            conf = r.get("confidence", 0)
            if conf > best_rule_conf:
                best_rule_conf = conf
                best_rule = r
        best_solution = None
        best_weight = 0.0
        for s in solutions_found:
            w = s.get("weight", 0)
            if w > best_weight:
                best_weight = w
                best_solution = s
        recommendation_parts = []
        if best_fix:
            recommendation_parts.append(
                "FIX: " + best_fix.get("signature", "") +
                " (confidence=" + str(best_confidence) + ")" +
                " → " + best_fix.get("solution", "")[:80]
            )
        if best_rule:
            recommendation_parts.append(
                "LAW: " + best_rule.get("pattern", "")[:60] +
                " → " + best_rule.get("fix_action", "")[:60] +
                " (confidence=" + str(best_rule_conf) + ")"
            )
        if best_solution:
            recommendation_parts.append(
                "SOLUTION: " + best_solution.get("solution", "")[:80] +
                " (weight=" + str(best_weight) + ")"
            )
        if problems_found:
            recommendation_parts.append(
                "PROBLEMS: " + str(len(problems_found)) + " related problems found"
            )
        if facts_found:
            entities = list(set(f.get("entity", "") for f in facts_found if f.get("entity")))
            recommendation_parts.append(
                "FACTS: " + str(len(facts_found)) + " facts about " +
                ", ".join(entities[:5])
            )
        if not recommendation_parts:
            recommendation_parts.append("NO MATCHES — generate candidate fix from template")
        recommendation = " | ".join(recommendation_parts)
        self.state["last_reason"] = recommendation
        reason_result = {
            "recommendation": recommendation,
            "best_fix": best_fix,
            "best_rule": best_rule,
            "best_solution": best_solution,
            "counts": {
                "errors": len(errors_found),
                "rules": len(rules_found),
                "problems": len(problems_found),
                "solutions": len(solutions_found),
                "facts": len(facts_found),
            },
            "action": "apply_fix" if best_fix else (
                "apply_rule" if best_rule else (
                    "apply_solution" if best_solution else "generate_candidate"
                )
            ),
        }
        return (1, reason_result, None)

    # ── LOOP: msearch → run_cmd → msearch → reason ──

    def Loop(self, params):
        """LOOP — msearch → run_cmd → msearch → reason.

        The self-learning search loop:
        1. msearch(keyword) — get initial results from MySQL
        2. run_cmd(command) — execute a command (apply fix, run test, etc.)
        3. msearch(keyword) — search again to verify
        4. reason — produce recommendation from results

        Params:
          keyword: search keyword
          command: shell command to run (optional)
          file_path: file to apply fix to (optional)
          error_type: error type for context (optional)
        """
        if params is None:
            params = {}
        keyword = params.get("keyword", "")
        command = params.get("command", "")
        file_path = params.get("file", "")
        error_type = params.get("error_type", "")
        if not keyword:
            return (0, None, (30, "no keyword for loop", 0))
        self.state["total_loops"] += 1
        loop_steps = []

        # Step 1: msearch
        search1 = self.Msearch({"keyword": keyword, "limit": 10})
        if search1[0] != 1:
            return (0, None, (31, "msearch step 1 failed", 0))
        loop_steps.append({
            "step": "msearch_1",
            "results": search1[1].get("count", 0),
        })

        # Step 2: run_cmd (if provided)
        cmd_result = None
        if command:
            try:
                proc = subprocess.run(
                    command, shell=True, capture_output=True, text=True, timeout=30
                )
                cmd_result = {
                    "command": command,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout[:500],
                    "stderr": proc.stderr[:500],
                    "success": proc.returncode == 0,
                }
            except Exception as e:
                cmd_result = {
                    "command": command,
                    "error": str(e),
                    "success": False,
                }
            loop_steps.append({
                "step": "run_cmd",
                "success": cmd_result.get("success", False),
                "exit_code": cmd_result.get("exit_code", -1),
            })

        # Step 3: msearch again (verify)
        search2 = self.Msearch({"keyword": keyword, "limit": 10})
        if search2[0] != 1:
            return (0, None, (32, "msearch step 2 failed", 0))
        loop_steps.append({
            "step": "msearch_2",
            "results": search2[1].get("count", 0),
        })

        # Step 4: reason
        reason_result = self.Reason({
            "results": search2[1].get("results", []),
            "context": cmd_result,
            "error_type": error_type,
        })
        if reason_result[0] != 1:
            return (0, None, (33, "reason step failed", 0))
        loop_steps.append({
            "step": "reason",
            "action": reason_result[1].get("action"),
        })

        # Report fact about this loop
        if file_path:
            self.ReportFact({
                "entity_name": keyword,
                "entity_type": "concept",
                "relationship": "analyzed_by",
                "related_entity": "ClassErrors.Loop",
                "evidence": reason_result[1].get("recommendation", "")[:200],
                "source_file": file_path,
            })

        loop_result = {
            "keyword": keyword,
            "steps": loop_steps,
            "initial_results": search1[1].get("count", 0),
            "final_results": search2[1].get("count", 0),
            "command_result": cmd_result,
            "reason": reason_result[1],
            "recommendation": reason_result[1].get("recommendation", ""),
            "action": reason_result[1].get("action"),
        }
        return (1, loop_result, None)

    # ── STATE / CONFIG ──

    def ReadState(self, params):
        """Return current state."""
        state = dict(self.state)
        state["cache_size"] = len(self.state["cache"])
        state["cache"] = dict(self.state["cache"])
        return (1, state, None)

    def SetConfig(self, params):
        """Set configuration."""
        if params is None:
            params = {}
        if "halt_on_error" in params:
            self.state["halt_on_error"] = params["halt_on_error"]
        if "write_back" in params:
            self.state["write_back"] = params["write_back"]
        if "re_run" in params:
            self.state["re_run"] = params["re_run"]
        if "max_retries" in params:
            self.state["max_retries"] = params["max_retries"]
        return (1, None, None)
