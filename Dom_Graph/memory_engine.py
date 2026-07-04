#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/memory_engine.py"
# date="2026-06-26" author="Devin" session_id="phase3-knowledge"
# context="Project Digital Twin Phase 3 Section 29 AI Memory"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="memory_engine.py" domain="twin_memory" authority="MemoryEngine"}
# [@SUMMARY]{summary="Memory authority that recalls previous errors, fixes, successes, failures, rules and learned patterns from the knowledge and observations tables."}
# [@CLASS]{class="MemoryEngine" domain="memory" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="recall_errors" type="command"}
# [@METHOD]{method="recall_fixes" type="command"}
# [@METHOD]{method="recall_successes" type="command"}
# [@METHOD]{method="recall_failures" type="command"}
# [@METHOD]{method="recall_rules" type="command"}
# [@METHOD]{method="recall_patterns" type="command"}
# [@METHOD]{method="recall_user_rules" type="command"}
# [@METHOD]{method="recall_architecture_rules" type="command"}
# [@METHOD]{method="recall_all" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<MemoryEngine: recalls errors fixes successes failures rules patterns from knowledge/observations tables. Full VBStyle headers present. Run() dispatch with Tuple3 returns. self.state dict, _p helper, read_state, set_config all present. No print no decorators no self._ violations.>][@todos<none>]}
"""
MemoryEngine -- authority for AI memory recall.
Implements Section 29 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: recall_errors, recall_fixes, recall_successes, recall_failures,
          recall_rules, recall_patterns, recall_user_rules,
          recall_architecture_rules, recall_all.
Supports filtering by date_range (start, end) and confidence_threshold.
"""
import json
import os
import sqlite3

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class MemoryEngine:
    """Authority for recalling past errors, fixes, rules and patterns."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
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
        if command == "recall_errors":
            return self.RecallErrors(params)
        elif command == "recall_fixes":
            return self.RecallFixes(params)
        elif command == "recall_successes":
            return self.RecallSuccesses(params)
        elif command == "recall_failures":
            return self.RecallFailures(params)
        elif command == "recall_rules":
            return self.RecallRules(params)
        elif command == "recall_patterns":
            return self.RecallPatterns(params)
        elif command == "recall_user_rules":
            return self.RecallUserRules(params)
        elif command == "recall_architecture_rules":
            return self.RecallArchitectureRules(params)
        elif command == "recall_all":
            return self.RecallAll(params)
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

    def BuildFilter(self, params):
        # Build optional WHERE clauses for date range and confidence threshold
        clauses = []
        values = []
        start = self._p(params, "start")
        end = self._p(params, "end")
        conf_threshold = self._p(params, "confidence_threshold")
        if start:
            clauses.append("created >= ?")
            values.append(start)
        if end:
            clauses.append("created <= ?")
            values.append(end)
        if conf_threshold is not None:
            clauses.append("confidence >= ?")
            values.append(conf_threshold)
        filter_sql = ""
        if clauses:
            filter_sql = " AND " + " AND ".join(clauses)
        return filter_sql, values

    def RecallErrors(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        filter_sql, filter_values = self.BuildFilter(params)
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT knowledge_id, problem, error_type, error_text, confidence, created "
            "FROM knowledge WHERE error_type IS NOT NULL" + filter_sql +
            " ORDER BY created DESC LIMIT ?",
            filter_values + [limit],
        )
        errors = [{"knowledge_id": r[0], "problem": r[1], "error_type": r[2],
                   "error_text": r[3], "confidence": r[4], "created": r[5]} for r in cur.fetchall()]
        return (1, {"errors": errors, "count": len(errors)}, None)

    def RecallFixes(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        filter_sql, filter_values = self.BuildFilter(params)
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT knowledge_id, problem, answer, fix_result, confidence, created "
            "FROM knowledge WHERE answer IS NOT NULL AND answer != ''" + filter_sql +
            " ORDER BY created DESC LIMIT ?",
            filter_values + [limit],
        )
        fixes = [{"knowledge_id": r[0], "problem": r[1], "answer": r[2],
                  "fix_result": r[3], "confidence": r[4], "created": r[5]}
                 for r in cur.fetchall()]
        return (1, {"fixes": fixes, "count": len(fixes)}, None)

    def RecallSuccesses(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        filter_sql, filter_values = self.BuildFilter(params)
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT knowledge_id, problem, answer, confidence, created "
            "FROM knowledge WHERE fix_result='success'" + filter_sql +
            " ORDER BY created DESC LIMIT ?",
            filter_values + [limit],
        )
        successes = [{"knowledge_id": r[0], "problem": r[1], "answer": r[2],
                      "confidence": r[3], "created": r[4]} for r in cur.fetchall()]
        return (1, {"successes": successes, "count": len(successes)}, None)

    def RecallFailures(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        filter_sql, filter_values = self.BuildFilter(params)
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT knowledge_id, problem, error_text, confidence, created "
            "FROM knowledge WHERE fix_result='failure'" + filter_sql +
            " ORDER BY created DESC LIMIT ?",
            filter_values + [limit],
        )
        failures = [{"knowledge_id": r[0], "problem": r[1], "error_text": r[2],
                     "confidence": r[3], "created": r[4]} for r in cur.fetchall()]
        return (1, {"failures": failures, "count": len(failures)}, None)

    def RecallRules(self, params):
        # 29.6 Coding Rules: stored in knowledge table with tags containing 'rule'
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        filter_sql, filter_values = self.BuildFilter(params)
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT knowledge_id, problem, answer, confidence, tags, created "
            "FROM knowledge WHERE tags LIKE '%rule%'" + filter_sql +
            " ORDER BY confidence DESC LIMIT ?",
            filter_values + [limit],
        )
        rules = []
        for r in cur.fetchall():
            tags = []
            try:
                tags = json.loads(r[4]) if r[4] else []
            except (ValueError, TypeError):
                tags = []
            rules.append({"knowledge_id": r[0], "rule": r[1], "answer": r[2],
                          "confidence": r[3], "tags": tags, "created": r[5]})
        return (1, {"rules": rules, "count": len(rules)}, None)

    def RecallPatterns(self, params):
        # 29.8 Learned Patterns: tags containing 'pattern' with high confidence
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conf_threshold = self._p(params, "confidence_threshold", 50)
        filter_sql, filter_values = self.BuildFilter(params)
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT knowledge_id, problem, answer, confidence, tags, error_type, created "
            "FROM knowledge WHERE tags LIKE '%pattern%' AND confidence >= ?" + filter_sql +
            " ORDER BY confidence DESC LIMIT ?",
            [conf_threshold] + filter_values + [limit],
        )
        patterns = []
        for r in cur.fetchall():
            tags = []
            try:
                tags = json.loads(r[4]) if r[4] else []
            except (ValueError, TypeError):
                tags = []
            patterns.append({"knowledge_id": r[0], "pattern": r[1], "answer": r[2],
                             "confidence": r[3], "tags": tags,
                             "error_type": r[5], "created": r[6]})
        return (1, {"patterns": patterns, "count": len(patterns)}, None)

    def RecallUserRules(self, params):
        # 29.5 User Rules: stored in Config.py constants, also check knowledge for user rules
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        # query knowledge for user-defined rules (tags containing 'user' or 'config')
        cur.execute(
            "SELECT knowledge_id, problem, answer, confidence, tags, created "
            "FROM knowledge WHERE tags LIKE '%user%' OR tags LIKE '%config%' "
            "ORDER BY confidence DESC LIMIT ?",
            (limit,),
        )
        user_rules = []
        for r in cur.fetchall():
            tags = []
            try:
                tags = json.loads(r[4]) if r[4] else []
            except (ValueError, TypeError):
                tags = []
            user_rules.append({"knowledge_id": r[0], "rule": r[1], "answer": r[2],
                               "confidence": r[3], "tags": tags, "created": r[4]})
        return (1, {"user_rules": user_rules, "count": len(user_rules)}, None)

    def RecallArchitectureRules(self, params):
        # 29.7 Architecture Rules: stored in knowledge table with tags=['architecture']
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        filter_sql, filter_values = self.BuildFilter(params)
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT knowledge_id, problem, answer, confidence, tags, created "
            "FROM knowledge WHERE tags LIKE '%architecture%'" + filter_sql +
            " ORDER BY confidence DESC LIMIT ?",
            filter_values + [limit],
        )
        arch_rules = []
        for r in cur.fetchall():
            tags = []
            try:
                tags = json.loads(r[4]) if r[4] else []
            except (ValueError, TypeError):
                tags = []
            arch_rules.append({"knowledge_id": r[0], "rule": r[1], "answer": r[2],
                               "confidence": r[3], "tags": tags, "created": r[4]})
        return (1, {"architecture_rules": arch_rules, "count": len(arch_rules)}, None)

    def RecallAll(self, params):
        results = {}
        for step in ("recall_errors", "recall_fixes", "recall_successes",
                     "recall_failures", "recall_rules", "recall_patterns",
                     "recall_user_rules", "recall_architecture_rules"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        return (1, results, None)
