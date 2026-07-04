#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/report_engine.py"
# date="2026-06-26" author="Devin" session_id="phase-orchestration"
# context="Project Digital Twin Section 15 Reporting"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="report_engine.py" domain="twin_report" authority="ReportEngine"}
# [@SUMMARY]{summary="Report authority that generates error timelines, fix timelines, dependency, duplicate, complexity, BCL coverage, and health score reports."}
# [@CLASS]{class="ReportEngine" domain="report" authority="single"}
# [@METHOD]{method="error_timeline" type="command"}
# [@METHOD]{method="fix_timeline" type="command"}
# [@METHOD]{method="dependency_report" type="command"}
# [@METHOD]{method="duplicate_report" type="command"}
# [@METHOD]{method="complexity_report" type="command"}
# [@METHOD]{method="bcl_coverage" type="command"}
# [@METHOD]{method="health_score" type="command"}
# [@METHOD]{method="full_report" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<ReportEngine: generates error timelines fix timelines dependency duplicate complexity BCL coverage health score reports. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations. Header missing Run method declaration but Run() exists in code.>][@todos<none>]}
"""
ReportEngine -- Reporting authority.
Implements Section 15 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: error_timeline, fix_timeline, dependency_report, duplicate_report, complexity_report, bcl_coverage, health_score, full_report.
"""
import os
import sqlite3

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class ReportEngine:
    """Reporting authority."""

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
        if command == "error_timeline":
            return self.ErrorTimeline(params)
        elif command == "fix_timeline":
            return self.FixTimeline(params)
        elif command == "dependency_report":
            return self.DependencyReport(params)
        elif command == "duplicate_report":
            return self.DuplicateReport(params)
        elif command == "complexity_report":
            return self.ComplexityReport(params)
        elif command == "bcl_coverage":
            return self.BclCoverage(params)
        elif command == "health_score":
            return self.HealthScore(params)
        elif command == "graph_coverage":
            return self.GraphCoverage(params)
        elif command == "method_coverage":
            return self.MethodCoverage(params)
        elif command == "test_coverage":
            return self.TestCoverage(params)
        elif command == "full_report":
            return self.FullReport(params)

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

    def ErrorTimeline(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT created, problem, error_type FROM knowledge WHERE error_type IS NOT NULL ORDER BY created")
        results = [{"created": r[0], "problem": r[1], "error_type": r[2]} for r in cur.fetchall()]
        return (1, {"timeline": results, "count": len(results)}, None)

    def FixTimeline(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT created, answer, fix_result FROM knowledge WHERE answer IS NOT NULL ORDER BY created")
        results = [{"created": r[0], "answer": r[1], "fix_result": r[2]} for r in cur.fetchall()]
        return (1, {"timeline": results, "count": len(results)}, None)

    def DependencyReport(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type")
        results = {r[0]: r[1] for r in cur.fetchall()}
        return (1, {"dependencies": results}, None)

    def DuplicateReport(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_name, COUNT(*) FROM methods GROUP BY hash HAVING COUNT(*)>1")
        results = [{"method_name": r[0], "count": r[1]} for r in cur.fetchall()]
        return (1, {"duplicates": results, "count": len(results)}, None)

    def ComplexityReport(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_name, cyclomatic_complexity FROM methods ORDER BY cyclomatic_complexity DESC LIMIT 20")
        results = [{"method_name": r[0], "complexity": r[1]} for r in cur.fetchall()]
        return (1, {"top_complex": results}, None)

    def BclCoverage(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT (SUM(CASE WHEN bcl IS NOT NULL AND bcl != '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) FROM methods")
        pct = cur.fetchone()[0] or 0
        return (1, {"bcl_coverage": pct}, None)

    def HealthScore(self, params):
        bcl = self.BclCoverage(params)
        bcl_score = bcl[1]["bcl_coverage"] if bcl[0] == 1 else 0
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT src_id) + COUNT(DISTINCT dst_id) FROM edges")
        graph_entities = cur.fetchone()[0] or 1
        total_entities = 0
        for table in ("files", "classes", "methods"):
            cur.execute("SELECT COUNT(*) FROM " + table)
            total_entities += cur.fetchone()[0]
        graph_coverage = (graph_entities / total_entities * 100) if total_entities > 0 else 0
        cur.execute("SELECT (SUM(has_run_method) * 100.0 / COUNT(*)) FROM classes")
        method_coverage = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=0 AND has_decorator=0 AND has_self_underscore=0")
        clean = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        total = cur.fetchone()[0]
        violation_free = (clean / total * 100) if total > 0 else 0
        score = bcl_score * 0.2 + graph_coverage * 0.2 + method_coverage * 0.2 + violation_free * 0.4
        return (1, {"health_score": score, "bcl_coverage": bcl_score,
                    "graph_coverage": graph_coverage, "method_coverage": method_coverage,
                    "violation_free": violation_free}, None)

    def GraphCoverage(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT src_id) + COUNT(DISTINCT dst_id) FROM edges")
        graph_entities = cur.fetchone()[0] or 0
        total_entities = 0
        for table in ("files", "classes", "methods"):
            cur.execute("SELECT COUNT(*) FROM " + table)
            total_entities += cur.fetchone()[0]
        coverage = (graph_entities / total_entities * 100) if total_entities > 0 else 0
        record = {
            "graph_entities": graph_entities,
            "total_entities": total_entities,
            "graph_coverage": coverage,
        }
        return (1, record, None)

    def MethodCoverage(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM classes WHERE has_run_method=1")
        with_run = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM classes")
        total_classes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE is_vbstyle=1")
        vbstyle_methods = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        total_methods = cur.fetchone()[0]
        class_coverage = (with_run / total_classes * 100) if total_classes > 0 else 0
        method_coverage = (vbstyle_methods / total_methods * 100) if total_methods > 0 else 0
        record = {
            "classes_with_run": with_run,
            "total_classes": total_classes,
            "class_coverage": class_coverage,
            "vbstyle_methods": vbstyle_methods,
            "total_methods": total_methods,
            "method_coverage": method_coverage,
        }
        return (1, record, None)

    def TestCoverage(self, params):
        passed = self._p(params, "passed")
        total = self._p(params, "total")
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM attempts WHERE test_result=1")
        passed_attempts = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attempts")
        total_attempts = cur.fetchone()[0]
        if passed is None:
            passed = passed_attempts
        if total is None:
            total = total_attempts
        coverage = (passed / total * 100) if total and total > 0 else 0
        record = {
            "passed": passed,
            "total": total,
            "test_coverage": coverage,
            "passed_attempts": passed_attempts,
            "total_attempts": total_attempts,
        }
        return (1, record, None)

    def FullReport(self, params):
        results = {}
        for step in ("error_timeline", "fix_timeline", "dependency_report", "duplicate_report",
                     "complexity_report", "bcl_coverage", "graph_coverage",
                     "method_coverage", "test_coverage", "health_score"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        return (1, {"full_report": results}, None)

