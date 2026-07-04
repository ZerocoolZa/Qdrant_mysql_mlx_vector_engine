#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/ai_memory_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 29: AI Memory -- 8 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="ai_memory_engine.py" domain="twin_aimem" authority="AiMemoryEngine"}
# [@SUMMARY]{summary="AI memory authority: previous errors, previous fixes, previous successes, previous failures, user rules, coding rules, architecture rules, learned patterns."}
# [@CLASS]{class="AiMemoryEngine" domain="aimem" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="previous_errors" type="command"}
# [@METHOD]{method="previous_fixes" type="command"}
# [@METHOD]{method="previous_successes" type="command"}
# [@METHOD]{method="previous_failures" type="command"}
# [@METHOD]{method="user_rules" type="command"}
# [@METHOD]{method="coding_rules" type="command"}
# [@METHOD]{method="architecture_rules" type="command"}
# [@METHOD]{method="learned_patterns" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class AiMemoryEngine:
    """Authority for AI memory: recalling past errors, fixes, rules, and patterns."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "result_limit": 50,
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
        if command == "previous_errors":
            return self.PreviousErrors(params)
        elif command == "previous_fixes":
            return self.PreviousFixes(params)
        elif command == "previous_successes":
            return self.PreviousSuccesses(params)
        elif command == "previous_failures":
            return self.PreviousFailures(params)
        elif command == "user_rules":
            return self.UserRules(params)
        elif command == "coding_rules":
            return self.CodingRules(params)
        elif command == "architecture_rules":
            return self.ArchitectureRules(params)
        elif command == "learned_patterns":
            return self.LearnedPatterns(params)
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

    def PreviousErrors(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        error_type = self._p(params, "error_type")
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            if error_type:
                cur.execute(
                    "SELECT knowledge_id, method_id, error_type, problem, confidence, created "
                    "FROM knowledge WHERE error_type=? ORDER BY knowledge_id DESC LIMIT ?",
                    (error_type, limit),
                )
            else:
                cur.execute(
                    "SELECT knowledge_id, method_id, error_type, problem, confidence, created "
                    "FROM knowledge ORDER BY knowledge_id DESC LIMIT ?",
                    (limit,),
                )
            errors = [{"knowledge_id": r[0], "method_id": r[1], "error_type": r[2],
                       "problem": r[3], "confidence": r[4], "created": r[5]}
                      for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"errors": errors, "count": len(errors)}, None)

    def PreviousFixes(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT knowledge_id, method_id, answer, evidence, confidence, created "
                "FROM knowledge WHERE answer IS NOT NULL AND answer != '' "
                "ORDER BY confidence DESC LIMIT ?",
                (limit,),
            )
            fixes = [{"knowledge_id": r[0], "method_id": r[1], "answer": r[2],
                      "evidence": r[3], "confidence": r[4], "created": r[5]}
                     for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"fixes": fixes, "count": len(fixes)}, None)

    def PreviousSuccesses(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT attempt_id, method_id, action, after_code, knowledge_id, created "
                "FROM attempts WHERE action='fix_applied' ORDER BY attempt_id DESC LIMIT ?",
                (limit,),
            )
            successes = [{"attempt_id": r[0], "method_id": r[1], "action": r[2],
                          "has_code": r[3] is not None, "knowledge_id": r[4],
                          "created": r[5]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"successes": successes, "count": len(successes)}, None)

    def PreviousFailures(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT attempt_id, method_id, action, created "
                "FROM attempts WHERE action IN ('fix_failed', 'compile_error', 'test_failed') "
                "ORDER BY attempt_id DESC LIMIT ?",
                (limit,),
            )
            failures = [{"attempt_id": r[0], "method_id": r[1], "action": r[2],
                         "created": r[3]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"failures": failures, "count": len(failures)}, None)

    def UserRules(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT rule_name, rule_body, category, confidence FROM rules "
                "WHERE category='User' OR category='Workflow' ORDER BY confidence DESC LIMIT ?",
                (limit,),
            )
            rules = [{"rule_name": r[0], "rule_body": r[1], "category": r[2],
                      "confidence": r[3]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"user_rules": rules, "count": len(rules)}, None)

    def CodingRules(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT rule_name, rule_body, category, confidence FROM rules "
                "WHERE category IN ('Method', 'Naming', 'Format', 'Forbidden') "
                "ORDER BY confidence DESC LIMIT ?",
                (limit,),
            )
            rules = [{"rule_name": r[0], "rule_body": r[1], "category": r[2],
                      "confidence": r[3]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"coding_rules": rules, "count": len(rules)}, None)

    def ArchitectureRules(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT rule_name, rule_body, category, confidence FROM rules "
                "WHERE category IN ('Architecture', 'State', 'Database') "
                "ORDER BY confidence DESC LIMIT ?",
                (limit,),
            )
            rules = [{"rule_name": r[0], "rule_body": r[1], "category": r[2],
                      "confidence": r[3]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"architecture_rules": rules, "count": len(rules)}, None)

    def LearnedPatterns(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT pattern, fix_action, confidence FROM learned_rules "
                "ORDER BY confidence DESC LIMIT ?",
                (limit,),
            )
            patterns = [{"pattern": r[0], "fix_action": r[1], "confidence": r[2]}
                        for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"learned_patterns": patterns, "count": len(patterns)}, None)
