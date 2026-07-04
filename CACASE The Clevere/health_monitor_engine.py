#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/health_monitor_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 32: Health Monitor -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="health_monitor_engine.py" domain="twin_health" authority="HealthMonitorEngine"}
# [@SUMMARY]{summary="Health monitor authority: check DB health, check graph health, check VBStyle health, check knowledge health, check test health, check dependency health, check complexity health, compute health score, health alert, health report."}
# [@CLASS]{class="HealthMonitorEngine" domain="health_monitor" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="check_db_health" type="command"}
# [@METHOD]{method="check_graph_health" type="command"}
# [@METHOD]{method="check_vbstyle_health" type="command"}
# [@METHOD]{method="check_knowledge_health" type="command"}
# [@METHOD]{method="check_test_health" type="command"}
# [@METHOD]{method="check_dependency_health" type="command"}
# [@METHOD]{method="check_complexity_health" type="command"}
# [@METHOD]{method="health_score" type="command"}
# [@METHOD]{method="health_alert" type="command"}
# [@METHOD]{method="health_report" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class HealthMonitorEngine:
    """Authority for monitoring project health metrics."""

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
        if command == "check_db_health":
            return self.CheckDbHealth(params)
        elif command == "check_graph_health":
            return self.CheckGraphHealth(params)
        elif command == "check_vbstyle_health":
            return self.CheckVbstyleHealth(params)
        elif command == "check_knowledge_health":
            return self.CheckKnowledgeHealth(params)
        elif command == "check_test_health":
            return self.CheckTestHealth(params)
        elif command == "check_dependency_health":
            return self.CheckDependencyHealth(params)
        elif command == "check_complexity_health":
            return self.CheckComplexityHealth(params)
        elif command == "health_score":
            return self.HealthScore(params)
        elif command == "health_alert":
            return self.HealthAlert(params)
        elif command == "health_report":
            return self.HealthReport(params)
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

    def CheckDbHealth(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA integrity_check")
            integrity = cur.fetchone()[0]
            cur.execute("PRAGMA foreign_key_check")
            fk_violations = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        healthy = integrity == "ok" and len(fk_violations) == 0
        return (1, {"integrity": integrity, "fk_violations": len(fk_violations),
                    "healthy": healthy}, None)

    def CheckGraphHealth(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM edges")
        edges = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        methods = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM classes")
        classes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM files")
        files = cur.fetchone()[0]
        healthy = edges > 0 and methods > 0 and classes > 0 and files > 0
        return (1, {"edges": edges, "methods": methods, "classes": classes,
                    "files": files, "healthy": healthy}, None)

    def CheckVbstyleHealth(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=1")
        prints = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_decorator=1")
        decorators = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_self_underscore=1")
        underscores = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE returns_tuple3=0")
        non_tuple3 = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM classes WHERE has_run_method=0")
        no_run = cur.fetchone()[0]
        violations = prints + decorators + underscores + non_tuple3 + no_run
        healthy = violations == 0
        return (1, {"prints": prints, "decorators": decorators,
                    "underscores": underscores, "non_tuple3": non_tuple3,
                    "no_run": no_run, "violations": violations,
                    "healthy": healthy}, None)

    def CheckKnowledgeHealth(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM knowledge")
        total = cur.fetchone()[0]
        cur.execute("SELECT AVG(confidence) FROM knowledge")
        avg_conf = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE answer IS NOT NULL AND answer != ''")
        with_fix = cur.fetchone()[0]
        healthy = total > 0 and avg_conf >= 50
        return (1, {"total": total, "avg_confidence": round(avg_conf, 1),
                    "with_fix": with_fix, "healthy": healthy}, None)

    def CheckTestHealth(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM attempts")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attempts WHERE compile_result=1 AND test_result=1")
        successes = cur.fetchone()[0]
        pass_rate = (successes / total * 100) if total > 0 else 0
        healthy = pass_rate >= 80
        return (1, {"total_attempts": total, "successes": successes,
                    "pass_rate": round(pass_rate, 1), "healthy": healthy}, None)

    def CheckDependencyHealth(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT dst_type, dst_id, COUNT(*) AS incoming FROM edges "
            "GROUP BY dst_type, dst_id HAVING incoming > 20"
        )
        hubs = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM edges")
        total = cur.fetchone()[0]
        healthy = len(hubs) == 0
        return (1, {"total_edges": total, "overloaded_hubs": len(hubs),
                    "healthy": healthy}, None)

    def CheckComplexityHealth(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT AVG(cyclomatic_complexity) FROM methods")
        avg = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM methods WHERE cyclomatic_complexity >= 15")
        high = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        total = cur.fetchone()[0]
        healthy = avg < 10 and high < total * 0.1
        return (1, {"avg_complexity": round(avg, 1), "high_complexity": high,
                    "total_methods": total, "healthy": healthy}, None)

    def HealthScore(self, params):
        scores = []
        for step in ("check_db_health", "check_graph_health", "check_vbstyle_health",
                     "check_knowledge_health", "check_test_health",
                     "check_dependency_health", "check_complexity_health"):
            res = self.Run(step, params)
            if res[0] == 1 and res[1].get("healthy"):
                scores.append(100)
            elif res[0] == 1:
                scores.append(50)
        overall = sum(scores) / len(scores) if scores else 0
        return (1, {"overall_score": round(overall, 1),
                    "checks_passed": sum(1 for s in scores if s == 100),
                    "total_checks": len(scores),
                    "status": "healthy" if overall >= 80 else ("warning" if overall >= 50 else "critical")}, None)

    def HealthAlert(self, params):
        res = self.HealthScore(params)
        if res[0] == 0:
            return res
        score = res[1]["overall_score"]
        alerts = []
        if score < 50:
            alerts.append("CRITICAL: Health score below 50")
        elif score < 80:
            alerts.append("WARNING: Health score below 80")
        for step in ("check_db_health", "check_vbstyle_health", "check_complexity_health"):
            step_res = self.Run(step, params)
            if step_res[0] == 1 and not step_res[1].get("healthy"):
                alerts.append("ALERT: " + step + " check failed")
        return (1, {"score": score, "alerts": alerts,
                    "alert_count": len(alerts)}, None)

    def HealthReport(self, params):
        results = {}
        for step in ("check_db_health", "check_graph_health", "check_vbstyle_health",
                     "check_knowledge_health", "check_test_health",
                     "check_dependency_health", "check_complexity_health",
                     "health_score", "health_alert"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        results["generated"] = self.Now()[1]
        return (1, results, None)
