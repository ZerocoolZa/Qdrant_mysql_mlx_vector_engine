# [@GHOST]{[@file<error_tracker.py>][@domain<utility>][@role<error_tracker>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<error_tracker>][@return<tuple3>][@orch<SystemCheck>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Error tracker — records errors, causes, solutions; queries MySQL learned_rules/know_problems/know_solutions}
# [@WCL]{[@self_contained<true>][@source<MySQL_vb_shared>][@tables<learned_rules|know_problems|know_solutions>][@ensures<lessons_carry_forward>]}

import os
import sqlite3
import json
from datetime import datetime

from . import Config


class ErrorTracker:
    """Error tracker — ensures lessons carry forward across sessions.

    Three stores:
    1. MySQL vb_shared.learned_rules (10,540 rules) — pattern → fix_action with confidence
    2. MySQL vb_shared.know_problems (218 problems) — known problems with descriptions
    3. MySQL vb_shared.know_solutions (336 solutions) — solutions linked to problems
    4. Local SQLite error_log.db — session-level error log for immediate recall

    Commands:
    - search: search learned_rules by keyword
    - lookup_problem: search know_problems by keyword
    - lookup_solution: get solutions for a problem
    - record: record a new error with cause and solution
    - save_lesson: save a learned rule to MySQL
    - recall: get recent errors from local log
    - match: match an error against known patterns
    - read_state: get current state

    Usage:
        from core.utility.error_tracker import ErrorTracker
        et = ErrorTracker()
        code, lessons, err = et.Run("search", {"keyword": "import"})
        code, result, err = et.Run("record", {"error": "ImportError", "cause": "missing module", "solution": "pip install"})
    """

    MYSQL_CONFIG = Config.ERROR_TRACKER_MYSQL

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "last_search": [],
            "last_record": {},
            "mysql_ok": False,
        }
        self.local_db = Config.ERROR_LOG_DB
        self.init_local()
        self.check_mysql()

    def Run(self, command, params=None):
        if command == "search":
            return self.search((params or {}).get("keyword", ""))
        elif command == "lookup_problem":
            return self.lookup_problem((params or {}).get("keyword", ""))
        elif command == "lookup_solution":
            return self.lookup_solution((params or {}).get("problem_id"))
        elif command == "record":
            return self.record(params or {})
        elif command == "save_lesson":
            return self.save_lesson(params or {})
        elif command == "recall":
            return self.recall((params or {}).get("limit", 20))
        elif command == "match":
            return self.match((params or {}).get("error_text", ""))
        elif command == "read_state":
            return self.read_state()
        return (0, None, ("unknown_command", command, 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self):
        return (1, dict(self.state), None)

    def init_local(self):
        conn = sqlite3.connect(self.local_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS error_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                error TEXT,
                cause TEXT,
                solution TEXT,
                context TEXT,
                file_path TEXT,
                domain TEXT,
                resolved INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def check_mysql(self):
        try:
            import mysql.connector
            cfg = dict(self.MYSQL_CONFIG)
            unix_socket = cfg.pop("unix_socket", None)
            if unix_socket and os.path.exists(unix_socket):
                conn = mysql.connector.connect(unix_socket=unix_socket, **cfg)
            else:
                conn = mysql.connector.connect(**cfg)
            conn.close()
            self.state["mysql_ok"] = True
        except Exception:
            self.state["mysql_ok"] = False

    def mysql_connect(self):
        if not self.state["mysql_ok"]:
            return None
        import mysql.connector
        cfg = dict(self.MYSQL_CONFIG)
        unix_socket = cfg.pop("unix_socket", None)
        if unix_socket and os.path.exists(unix_socket):
            return mysql.connector.connect(unix_socket=unix_socket, **cfg)
        return mysql.connector.connect(**cfg)

    def search(self, keyword):
        if not keyword:
            return (0, None, ("missing_param", "keyword", 0))
        if not self.state["mysql_ok"]:
            return (0, None, ("mysql_unavailable", "MySQL not connected", 0))
        conn = self.mysql_connect()
        if not conn:
            return (0, None, ("mysql_connect_failed", "could not connect", 0))
        cur = conn.cursor()
        cur.execute(
            "SELECT pattern, fix_action, confidence, success_count, failure_count "
            "FROM learned_rules WHERE pattern LIKE %s ORDER BY confidence DESC, success_count DESC LIMIT 10",
            ("%" + keyword + "%",)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        results = [
            {
                "pattern": r[0],
                "fix_action": r[1],
                "confidence": r[2],
                "success_count": r[3],
                "failure_count": r[4],
            }
            for r in rows
        ]
        self.state["last_search"] = results
        return (1, results, None)

    def lookup_problem(self, keyword):
        if not keyword:
            return (0, None, ("missing_param", "keyword", 0))
        if not self.state["mysql_ok"]:
            return (0, None, ("mysql_unavailable", "MySQL not connected", 0))
        conn = self.mysql_connect()
        if not conn:
            return (0, None, ("mysql_connect_failed", "could not connect", 0))
        cur = conn.cursor()
        cur.execute(
            "SELECT id, problem, description FROM know_problems WHERE problem LIKE %s LIMIT 10",
            ("%" + keyword + "%",)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        results = [
            {"id": r[0], "problem": r[1], "description": r[2]}
            for r in rows
        ]
        return (1, results, None)

    def lookup_solution(self, problem_id):
        if not problem_id:
            return (0, None, ("missing_param", "problem_id", 0))
        if not self.state["mysql_ok"]:
            return (0, None, ("mysql_unavailable", "MySQL not connected", 0))
        conn = self.mysql_connect()
        if not conn:
            return (0, None, ("mysql_connect_failed", "could not connect", 0))
        cur = conn.cursor()
        cur.execute(
            "SELECT id, solution, weight, fault_code, scope, auto_apply "
            "FROM know_solutions WHERE problem_id = %s ORDER BY weight DESC",
            (problem_id,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        results = [
            {
                "id": r[0], "solution": r[1], "weight": r[2],
                "fault_code": r[3], "scope": r[4], "auto_apply": bool(r[5]),
            }
            for r in rows
        ]
        return (1, results, None)

    def record(self, params):
        error = self._p(params, "error", "")
        cause = self._p(params, "cause", "")
        solution = self._p(params, "solution", "")
        context = self._p(params, "context", "")
        file_path = self._p(params, "file_path", "")
        domain = self._p(params, "domain", "")
        if not error:
            return (0, None, ("missing_param", "error", 0))
        conn = sqlite3.connect(self.local_db)
        conn.execute(
            "INSERT INTO error_log (error, cause, solution, context, file_path, domain) VALUES (?, ?, ?, ?, ?, ?)",
            (error, cause, solution, context, file_path, domain)
        )
        conn.commit()
        cur = conn.cursor()
        cur.execute("SELECT last_insert_rowid()")
        row_id = cur.fetchone()[0]
        conn.close()
        entry = {
            "id": row_id, "error": error, "cause": cause,
            "solution": solution, "context": context,
            "file_path": file_path, "domain": domain,
        }
        self.state["last_record"] = entry
        return (1, entry, None)

    def save_lesson(self, params):
        pattern = self._p(params, "pattern", "")
        fix_action = self._p(params, "fix_action", "")
        trigger_condition = self._p(params, "trigger_condition", "")
        language = self._p(params, "language", "python")
        category = self._p(params, "category", "general")
        severity = self._p(params, "severity", 2)
        source = self._p(params, "source", "cascade")
        if not pattern or not fix_action:
            return (0, None, ("missing_param", "pattern and fix_action required", 0))
        if not self.state["mysql_ok"]:
            return (0, None, ("mysql_unavailable", "MySQL not connected", 0))
        conn = self.mysql_connect()
        if not conn:
            return (0, None, ("mysql_connect_failed", "could not connect", 0))
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO learned_rules (pattern, trigger_condition, fix_action, language, category, severity, confidence, source) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (pattern, trigger_condition, fix_action, language, category, severity, 0.5, source)
        )
        conn.commit()
        rule_id = cur.lastrowid
        cur.close()
        conn.close()
        return (1, {"id": rule_id, "pattern": pattern, "fix_action": fix_action, "saved": True}, None)

    def recall(self, limit=20):
        conn = sqlite3.connect(self.local_db)
        cur = conn.cursor()
        cur.execute(
            "SELECT id, timestamp, error, cause, solution, context, file_path, domain, resolved "
            "FROM error_log ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = cur.fetchall()
        conn.close()
        results = [
            {
                "id": r[0], "timestamp": r[1], "error": r[2], "cause": r[3],
                "solution": r[4], "context": r[5], "file_path": r[6],
                "domain": r[7], "resolved": bool(r[8]),
            }
            for r in rows
        ]
        return (1, results, None)

    def match(self, error_text):
        if not error_text:
            return (0, None, ("missing_param", "error_text", 0))
        results = {"learned_rules": [], "problems": [], "local": []}
        if self.state["mysql_ok"]:
            conn = self.mysql_connect()
            if conn:
                cur = conn.cursor()
                words = error_text.replace("'", "").replace('"', "").split()
                for word in words:
                    if len(word) < 4:
                        continue
                    cur.execute(
                        "SELECT pattern, fix_action, confidence FROM learned_rules "
                        "WHERE pattern LIKE %s ORDER BY confidence DESC LIMIT 3",
                        ("%" + word + "%",)
                    )
                    for row in cur.fetchall():
                        entry = {"pattern": row[0], "fix_action": row[1], "confidence": row[2]}
                        if entry not in results["learned_rules"]:
                            results["learned_rules"].append(entry)
                    cur.execute(
                        "SELECT id, problem FROM know_problems WHERE problem LIKE %s LIMIT 3",
                        ("%" + word + "%",)
                    )
                    for row in cur.fetchall():
                        entry = {"id": row[0], "problem": row[1]}
                        if entry not in results["problems"]:
                            results["problems"].append(entry)
                cur.close()
                conn.close()
        conn = sqlite3.connect(self.local_db)
        cur = conn.cursor()
        cur.execute(
            "SELECT error, cause, solution FROM error_log WHERE error LIKE ? ORDER BY id DESC LIMIT 5",
            ("%" + error_text[:50] + "%",)
        )
        for row in cur.fetchall():
            results["local"].append({"error": row[0], "cause": row[1], "solution": row[2]})
        conn.close()
        return (1, results, None)
