#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/evolution_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 41: Evolution Tracking -- 8 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="evolution_engine.py" domain="twin_evolution" authority="EvolutionEngine"}
# [@SUMMARY]{summary="Evolution authority: class timeline, method timeline, variable timeline, dependency timeline, architecture timeline, error timeline, fix timeline, refactor timeline."}
# [@CLASS]{class="EvolutionEngine" domain="evolution" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="class_timeline" type="command"}
# [@METHOD]{method="method_timeline" type="command"}
# [@METHOD]{method="variable_timeline" type="command"}
# [@METHOD]{method="dependency_timeline" type="command"}
# [@METHOD]{method="architecture_timeline" type="command"}
# [@METHOD]{method="error_timeline" type="command"}
# [@METHOD]{method="fix_timeline" type="command"}
# [@METHOD]{method="refactor_timeline" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class EvolutionEngine:
    """Authority for tracking codebase evolution timelines."""

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
        if command == "class_timeline":
            return self.ClassTimeline(params)
        elif command == "method_timeline":
            return self.MethodTimeline(params)
        elif command == "variable_timeline":
            return self.VariableTimeline(params)
        elif command == "dependency_timeline":
            return self.DependencyTimeline(params)
        elif command == "architecture_timeline":
            return self.ArchitectureTimeline(params)
        elif command == "error_timeline":
            return self.ErrorTimeline(params)
        elif command == "fix_timeline":
            return self.FixTimeline(params)
        elif command == "refactor_timeline":
            return self.RefactorTimeline(params)
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

    def ClassTimeline(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT class_id, class_name, method_count, created FROM classes "
                "ORDER BY class_id DESC LIMIT ?",
                (limit,),
            )
            timeline = [{"class_id": r[0], "class_name": r[1],
                         "method_count": r[2], "created": r[3]} for r in cur.fetchall()]
            cur.execute("SELECT COUNT(*) FROM classes")
            total = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"timeline": timeline, "count": len(timeline), "total": total}, None)

    def MethodTimeline(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT method_id, method_name, class_id, cyclomatic_complexity, created "
                "FROM methods ORDER BY method_id DESC LIMIT ?",
                (limit,),
            )
            timeline = [{"method_id": r[0], "method_name": r[1], "class_id": r[2],
                         "complexity": r[3], "created": r[4]} for r in cur.fetchall()]
            cur.execute("SELECT COUNT(*) FROM methods")
            total = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"timeline": timeline, "count": len(timeline), "total": total}, None)

    def VariableTimeline(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT edge_id, src_id, src_type, dst_id, dst_type, edge_type "
                "FROM edges WHERE edge_type IN ('uses_variable','reads','writes','assigns') "
                "ORDER BY edge_id DESC LIMIT ?",
                (limit,),
            )
            timeline = [{"edge_id": r[0], "src_id": r[1], "src_type": r[2],
                         "dst_id": r[3], "dst_type": r[4], "edge_type": r[5]}
                        for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"timeline": timeline, "count": len(timeline)}, None)

    def DependencyTimeline(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT edge_id, src_id, src_type, dst_id, dst_type, edge_type "
                "FROM edges WHERE edge_type IN ('imports','depends_on','uses') "
                "ORDER BY edge_id DESC LIMIT ?",
                (limit,),
            )
            timeline = [{"edge_id": r[0], "src_id": r[1], "src_type": r[2],
                         "dst_id": r[3], "dst_type": r[4], "edge_type": r[5]}
                        for r in cur.fetchall()]
            cur.execute("SELECT COUNT(*) FROM edges")
            total = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"timeline": timeline, "count": len(timeline), "total_edges": total}, None)

    def ArchitectureTimeline(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT class_id, class_name, parent, method_count, has_run_method, created "
                "FROM classes ORDER BY created DESC LIMIT ?",
                (limit,),
            )
            timeline = [{"class_id": r[0], "class_name": r[1], "parent": r[2],
                         "method_count": r[3], "has_run": r[4], "created": r[5]}
                        for r in cur.fetchall()]
            cur.execute("SELECT COUNT(*) FROM classes WHERE has_run_method=1")
            with_run = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM classes")
            total = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"timeline": timeline, "count": len(timeline),
                    "run_coverage": round(with_run / max(total, 1) * 100, 1)}, None)

    def ErrorTimeline(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT knowledge_id, method_id, error_type, problem, confidence, created "
                "FROM knowledge ORDER BY knowledge_id DESC LIMIT ?",
                (limit,),
            )
            timeline = [{"knowledge_id": r[0], "method_id": r[1], "error_type": r[2],
                         "problem": r[3], "confidence": r[4], "created": r[5]}
                        for r in cur.fetchall()]
            cur.execute("SELECT COUNT(*) FROM knowledge")
            total = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"timeline": timeline, "count": len(timeline), "total": total}, None)

    def FixTimeline(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT attempt_id, method_id, action, knowledge_id, created "
                "FROM attempts WHERE action IN ('fix_applied','fix_failed','compile_error','test_failed') "
                "ORDER BY attempt_id DESC LIMIT ?",
                (limit,),
            )
            timeline = [{"attempt_id": r[0], "method_id": r[1], "action": r[2],
                         "knowledge_id": r[3], "created": r[4]} for r in cur.fetchall()]
            cur.execute("SELECT COUNT(*) FROM attempts")
            total = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"timeline": timeline, "count": len(timeline), "total": total}, None)

    def RefactorTimeline(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT attempt_id, method_id, action, before_code, after_code, created "
                "FROM attempts WHERE action IN ('refactored','extracted','inlined','renamed','moved','split','merged') "
                "ORDER BY attempt_id DESC LIMIT ?",
                (limit,),
            )
            timeline = [{"attempt_id": r[0], "method_id": r[1], "action": r[2],
                         "has_before": r[3] is not None, "has_after": r[4] is not None,
                         "created": r[5]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"timeline": timeline, "count": len(timeline)}, None)
