#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/regression_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 36: Regression Engine -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="regression_engine.py" domain="twin_regression" authority="RegressionEngine"}
# [@SUMMARY]{summary="Regression authority: detect compile regression, detect test regression, detect VBStyle regression, detect complexity regression, detect dependency regression, detect performance regression, detect knowledge regression, detect structural regression, rank regressions, regression report."}
# [@CLASS]{class="RegressionEngine" domain="regression" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="detect_compile_regression" type="command"}
# [@METHOD]{method="detect_test_regression" type="command"}
# [@METHOD]{method="detect_vbstyle_regression" type="command"}
# [@METHOD]{method="detect_complexity_regression" type="command"}
# [@METHOD]{method="detect_dependency_regression" type="command"}
# [@METHOD]{method="detect_performance_regression" type="command"}
# [@METHOD]{method="detect_knowledge_regression" type="command"}
# [@METHOD]{method="detect_structural_regression" type="command"}
# [@METHOD]{method="rank_regressions" type="command"}
# [@METHOD]{method="regression_report" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class RegressionEngine:
    """Authority for detecting regressions across the project."""

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
        if command == "detect_compile_regression":
            return self.DetectCompileRegression(params)
        elif command == "detect_test_regression":
            return self.DetectTestRegression(params)
        elif command == "detect_vbstyle_regression":
            return self.DetectVbstyleRegression(params)
        elif command == "detect_complexity_regression":
            return self.DetectComplexityRegression(params)
        elif command == "detect_dependency_regression":
            return self.DetectDependencyRegression(params)
        elif command == "detect_performance_regression":
            return self.DetectPerformanceRegression(params)
        elif command == "detect_knowledge_regression":
            return self.DetectKnowledgeRegression(params)
        elif command == "detect_structural_regression":
            return self.DetectStructuralRegression(params)
        elif command == "rank_regressions":
            return self.RankRegressions(params)
        elif command == "regression_report":
            return self.RegressionReport(params)
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

    def DetectCompileRegression(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, COUNT(*) AS total, "
            "SUM(CASE WHEN compile_result=0 THEN 1 ELSE 0 END) AS failures "
            "FROM attempts GROUP BY method_id HAVING failures > 0"
        )
        regressions = [{"method_id": r[0], "total": r[1], "failures": r[2]}
                       for r in cur.fetchall()]
        return (1, {"compile_regressions": regressions[:100],
                    "count": len(regressions)}, None)

    def DetectTestRegression(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, COUNT(*) AS total, "
            "SUM(CASE WHEN compile_result=1 AND test_result=0 THEN 1 ELSE 0 END) AS test_fails "
            "FROM attempts GROUP BY method_id HAVING test_fails > 0"
        )
        regressions = [{"method_id": r[0], "total": r[1], "test_fails": r[2]}
                       for r in cur.fetchall()]
        return (1, {"test_regressions": regressions[:100],
                    "count": len(regressions)}, None)

    def DetectVbstyleRegression(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_name FROM methods WHERE has_print=1 OR "
            "has_decorator=1 OR has_self_underscore=1 OR returns_tuple3=0"
        )
        regressions = [{"method_id": r[0], "method_name": r[1]}
                       for r in cur.fetchall()]
        return (1, {"vbstyle_regressions": regressions[:100],
                    "count": len(regressions)}, None)

    def DetectComplexityRegression(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT AVG(cyclomatic_complexity) FROM methods")
        avg = cur.fetchone()[0] or 0
        cur.execute(
            "SELECT method_id, method_name, cyclomatic_complexity FROM methods "
            "WHERE cyclomatic_complexity > ? ORDER BY cyclomatic_complexity DESC",
            (avg * 2,),
        )
        regressions = [{"method_id": r[0], "method_name": r[1],
                        "complexity": r[2], "avg": round(avg, 1)}
                       for r in cur.fetchall()]
        return (1, {"complexity_regressions": regressions[:100],
                    "count": len(regressions)}, None)

    def DetectDependencyRegression(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT dst_type, dst_id, COUNT(*) AS incoming FROM edges "
            "GROUP BY dst_type, dst_id HAVING incoming > 20 ORDER BY incoming DESC"
        )
        regressions = [{"type": r[0], "id": r[1], "incoming": r[2]}
                       for r in cur.fetchall()]
        return (1, {"dependency_regressions": regressions[:100],
                    "count": len(regressions)}, None)

    def DetectPerformanceRegression(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, COUNT(*) AS attempts FROM attempts "
            "GROUP BY method_id HAVING attempts > 5 ORDER BY attempts DESC"
        )
        regressions = [{"method_id": r[0], "attempts": r[1]}
                       for r in cur.fetchall()]
        return (1, {"performance_regressions": regressions[:100],
                    "count": len(regressions)}, None)

    def DetectKnowledgeRegression(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT knowledge_id, problem, confidence FROM knowledge "
            "WHERE confidence < 30 OR (answer IS NULL OR answer = '')"
        )
        regressions = [{"knowledge_id": r[0], "problem": r[1],
                        "confidence": r[2]} for r in cur.fetchall()]
        return (1, {"knowledge_regressions": regressions[:100],
                    "count": len(regressions)}, None)

    def DetectStructuralRegression(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT class_id, class_name, method_count FROM classes WHERE method_count > 30")
        regressions = [{"class_id": r[0], "class_name": r[1],
                        "method_count": r[2]} for r in cur.fetchall()]
        cur.execute("SELECT method_id, method_name, line_count FROM methods WHERE line_count > 200")
        for r in cur.fetchall():
            regressions.append({"method_id": r[0], "method_name": r[1],
                                "line_count": r[2]})
        return (1, {"structural_regressions": regressions[:100],
                    "count": len(regressions)}, None)

    def RankRegressions(self, params):
        all_regs = []
        for step in ("detect_compile_regression", "detect_test_regression",
                     "detect_vbstyle_regression", "detect_complexity_regression",
                     "detect_dependency_regression", "detect_performance_regression",
                     "detect_knowledge_regression", "detect_structural_regression"):
            res = self.Run(step, params)
            if res[0] == 1:
                count = res[1].get("count", 0)
                all_regs.append({"source": step, "count": count})
        ranked = sorted(all_regs, key=lambda r: r["count"], reverse=True)
        return (1, {"ranked": ranked, "total_sources": len(ranked)}, None)

    def RegressionReport(self, params):
        results = {}
        total = 0
        for step in ("detect_compile_regression", "detect_test_regression",
                     "detect_vbstyle_regression", "detect_complexity_regression",
                     "detect_dependency_regression", "detect_performance_regression",
                     "detect_knowledge_regression", "detect_structural_regression"):
            res = self.Run(step, params)
            if res[0] == 1:
                results[step] = res[1]
                total += res[1].get("count", 0)
            else:
                results[step] = {"error": str(res[2])}
        results["total_regressions"] = total
        results["generated"] = self.Now()[1]
        return (1, results, None)
