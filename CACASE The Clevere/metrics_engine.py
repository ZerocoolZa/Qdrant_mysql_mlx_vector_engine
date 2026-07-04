#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/metrics_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 33: Metrics Engine -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="metrics_engine.py" domain="twin_metrics" authority="MetricsEngine"}
# [@SUMMARY]{summary="Metrics authority: file metrics, class metrics, method metrics, graph metrics, VBStyle metrics, knowledge metrics, attempt metrics, complexity metrics, dependency metrics, overall metrics."}
# [@CLASS]{class="MetricsEngine" domain="metrics" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="file_metrics" type="command"}
# [@METHOD]{method="class_metrics" type="command"}
# [@METHOD]{method="method_metrics" type="command"}
# [@METHOD]{method="graph_metrics" type="command"}
# [@METHOD]{method="vbstyle_metrics" type="command"}
# [@METHOD]{method="knowledge_metrics" type="command"}
# [@METHOD]{method="attempt_metrics" type="command"}
# [@METHOD]{method="complexity_metrics" type="command"}
# [@METHOD]{method="dependency_metrics" type="command"}
# [@METHOD]{method="overall_metrics" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class MetricsEngine:
    """Authority for computing project-wide metrics."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
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
        if command == "file_metrics":
            return self.FileMetrics(params)
        elif command == "class_metrics":
            return self.ClassMetrics(params)
        elif command == "method_metrics":
            return self.MethodMetrics(params)
        elif command == "graph_metrics":
            return self.GraphMetrics(params)
        elif command == "vbstyle_metrics":
            return self.VbstyleMetrics(params)
        elif command == "knowledge_metrics":
            return self.KnowledgeMetrics(params)
        elif command == "attempt_metrics":
            return self.AttemptMetrics(params)
        elif command == "complexity_metrics":
            return self.ComplexityMetrics(params)
        elif command == "dependency_metrics":
            return self.DependencyMetrics(params)
        elif command == "overall_metrics":
            return self.OverallMetrics(params)
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

    def FileMetrics(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM files")
        total = cur.fetchone()[0]
        cur.execute("SELECT SUM(size) FROM files")
        total_size = cur.fetchone()[0] or 0
        cur.execute("SELECT extension, COUNT(*) FROM files GROUP BY extension")
        by_ext = {r[0]: r[1] for r in cur.fetchall()}
        cur.execute("SELECT AVG(class_count) FROM files")
        avg_classes = cur.fetchone()[0] or 0
        return (1, {"total_files": total, "total_size": total_size,
                    "by_extension": by_ext,
                    "avg_classes_per_file": round(avg_classes, 1)}, None)

    def ClassMetrics(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM classes")
        total = cur.fetchone()[0]
        cur.execute("SELECT AVG(method_count) FROM classes")
        avg_methods = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM classes WHERE is_vbstyle=1")
        vbstyle = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM classes WHERE has_run_method=1")
        has_run = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM classes WHERE parent IS NOT NULL")
        has_parent = cur.fetchone()[0]
        return (1, {"total_classes": total,
                    "avg_methods": round(avg_methods, 1),
                    "vbstyle_compliant": vbstyle,
                    "has_run": has_run,
                    "has_parent": has_parent}, None)

    def MethodMetrics(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM methods")
        total = cur.fetchone()[0]
        cur.execute("SELECT AVG(line_count) FROM methods")
        avg_lines = cur.fetchone()[0] or 0
        cur.execute("SELECT AVG(cyclomatic_complexity) FROM methods")
        avg_cc = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM methods WHERE returns_tuple3=1")
        tuple3 = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE is_dunder=1")
        dunder = cur.fetchone()[0]
        return (1, {"total_methods": total,
                    "avg_lines": round(avg_lines, 1),
                    "avg_complexity": round(avg_cc, 1),
                    "tuple3": tuple3, "dunder": dunder}, None)

    def GraphMetrics(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM edges")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT edge_type) FROM edges")
        types = cur.fetchone()[0]
        cur.execute("SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type")
        by_type = {r[0]: r[1] for r in cur.fetchall()}
        cur.execute("SELECT AVG(confidence) FROM edges")
        avg_conf = cur.fetchone()[0] or 0
        return (1, {"total_edges": total, "edge_types": types,
                    "by_type": by_type,
                    "avg_confidence": round(avg_conf, 1)}, None)

    def VbstyleMetrics(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM methods")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=1")
        prints = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_decorator=1")
        decorators = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_self_underscore=1")
        underscores = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE returns_tuple3=1")
        tuple3 = cur.fetchone()[0]
        compliance = (tuple3 / total * 100) if total > 0 else 0
        return (1, {"total_methods": total, "prints": prints,
                    "decorators": decorators, "underscores": underscores,
                    "tuple3": tuple3,
                    "compliance_pct": round(compliance, 1)}, None)

    def KnowledgeMetrics(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM knowledge")
        total = cur.fetchone()[0]
        cur.execute("SELECT AVG(confidence) FROM knowledge")
        avg_conf = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE fix_result='success'")
        successes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT error_type) FROM knowledge WHERE error_type IS NOT NULL")
        error_types = cur.fetchone()[0]
        return (1, {"total_entries": total,
                    "avg_confidence": round(avg_conf, 1),
                    "successful_fixes": successes,
                    "distinct_error_types": error_types}, None)

    def AttemptMetrics(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM attempts")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attempts WHERE compile_result=1 AND test_result=1")
        successes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attempts WHERE rollback=1")
        rollbacks = cur.fetchone()[0]
        pass_rate = (successes / total * 100) if total > 0 else 0
        return (1, {"total_attempts": total, "successes": successes,
                    "rollbacks": rollbacks,
                    "pass_rate": round(pass_rate, 1)}, None)

    def ComplexityMetrics(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT AVG(cyclomatic_complexity) FROM methods")
        avg = cur.fetchone()[0] or 0
        cur.execute("SELECT MAX(cyclomatic_complexity) FROM methods")
        max_cc = cur.fetchone()[0] or 0
        cur.execute("SELECT MIN(cyclomatic_complexity) FROM methods")
        min_cc = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM methods WHERE cyclomatic_complexity >= 10")
        high = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE cyclomatic_complexity >= 15")
        very_high = cur.fetchone()[0]
        return (1, {"avg": round(avg, 1), "max": max_cc, "min": min_cc,
                    "high_count": high, "very_high_count": very_high}, None)

    def DependencyMetrics(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM edges")
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT dst_type, dst_id, COUNT(*) AS incoming FROM edges "
            "GROUP BY dst_type, dst_id ORDER BY incoming DESC LIMIT 1"
        )
        top = cur.fetchone()
        max_incoming = top[2] if top else 0
        cur.execute("SELECT COUNT(DISTINCT edge_type) FROM edges")
        types = cur.fetchone()[0]
        return (1, {"total_edges": total, "max_incoming": max_incoming,
                    "edge_types": types}, None)

    def OverallMetrics(self, params):
        results = {}
        for step in ("file_metrics", "class_metrics", "method_metrics",
                     "graph_metrics", "vbstyle_metrics", "knowledge_metrics",
                     "attempt_metrics", "complexity_metrics", "dependency_metrics"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        results["generated"] = self.Now()[1]
        return (1, results, None)
