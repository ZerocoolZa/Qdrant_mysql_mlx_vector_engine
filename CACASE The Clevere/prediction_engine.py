#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/prediction_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 16: Prediction Engine -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="prediction_engine.py" domain="twin_prediction" authority="PredictionEngine"}
# [@SUMMARY]{summary="Prediction authority: predict failure risk, predict complexity growth, predict refactoring needed, predict test coverage gap, predict dependency issues, predict performance bottleneck, predict code smell, predict maintenance burden, predict technical debt, predict bug probability."}
# [@CLASS]{class="PredictionEngine" domain="prediction" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="predict_failure_risk" type="command"}
# [@METHOD]{method="predict_complexity_growth" type="command"}
# [@METHOD]{method="predict_refactoring_needed" type="command"}
# [@METHOD]{method="predict_test_coverage_gap" type="command"}
# [@METHOD]{method="predict_dependency_issues" type="command"}
# [@METHOD]{method="predict_performance_bottleneck" type="command"}
# [@METHOD]{method="predict_code_smell" type="command"}
# [@METHOD]{method="predict_maintenance_burden" type="command"}
# [@METHOD]{method="predict_technical_debt" type="command"}
# [@METHOD]{method="predict_bug_probability" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"
COMPLEXITY_THRESHOLD = 10.0
COVERAGE_THRESHOLD = 80.0


class PredictionEngine:
    """Authority for predictive code analysis and risk assessment."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "complexity_threshold": COMPLEXITY_THRESHOLD,
                "coverage_threshold": COVERAGE_THRESHOLD,
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
        if command == "predict_failure_risk":
            return self.PredictFailureRisk(params)
        elif command == "predict_complexity_growth":
            return self.PredictComplexityGrowth(params)
        elif command == "predict_refactoring_needed":
            return self.PredictRefactoringNeeded(params)
        elif command == "predict_test_coverage_gap":
            return self.PredictTestCoverageGap(params)
        elif command == "predict_dependency_issues":
            return self.PredictDependencyIssues(params)
        elif command == "predict_performance_bottleneck":
            return self.PredictPerformanceBottleneck(params)
        elif command == "predict_code_smell":
            return self.PredictCodeSmell(params)
        elif command == "predict_maintenance_burden":
            return self.PredictMaintenanceBurden(params)
        elif command == "predict_technical_debt":
            return self.PredictTechnicalDebt(params)
        elif command == "predict_bug_probability":
            return self.PredictBugProbability(params)
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

    def PredictFailureRisk(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_name, cyclomatic_complexity, has_print, "
            "has_decorator, has_self_underscore, returns_tuple3 "
            "FROM methods"
        )
        risks = []
        for row in cur.fetchall():
            score = 0
            if row[2] and row[2] >= 10:
                score += 30
            if row[3]:
                score += 15
            if row[4]:
                score += 15
            if row[5]:
                score += 20
            if not row[6]:
                score += 20
            risks.append({"method_id": row[0], "method_name": row[1],
                          "risk_score": min(score, 100),
                          "risk_level": "high" if score >= 60 else ("medium" if score >= 30 else "low")})
        risks.sort(key=lambda r: r["risk_score"], reverse=True)
        return (1, {"risks": risks[:50], "total": len(risks)}, None)

    def PredictComplexityGrowth(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT class_id, class_name, method_count, cyclomatic_complexity "
            "FROM classes ORDER BY cyclomatic_complexity DESC"
        )
        growth = []
        for row in cur.fetchall():
            projected = (row[2] or 0) * 1.5
            growth.append({"class_id": row[0], "class_name": row[1],
                           "current_methods": row[2],
                           "current_complexity": row[3],
                           "projected_complexity": projected})
        return (1, {"growth_predictions": growth[:50]}, None)

    def PredictRefactoringNeeded(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_name, cyclomatic_complexity, "
            "has_print, has_decorator, has_self_underscore "
            "FROM methods WHERE cyclomatic_complexity >= ? OR has_print=1 OR "
            "has_decorator=1 OR has_self_underscore=1",
            (self.state["config"]["complexity_threshold"],),
        )
        targets = [{"method_id": r[0], "method_name": r[1],
                    "complexity": r[2], "needs_refactor": True}
                   for r in cur.fetchall()]
        return (1, {"refactor_targets": targets[:100],
                    "count": len(targets)}, None)

    def PredictTestCoverageGap(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM methods")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT method_id) FROM attempts WHERE test_result=1")
        tested = cur.fetchone()[0]
        gap = total - tested
        coverage = (tested / total * 100) if total > 0 else 0
        return (1, {"total_methods": total, "tested": tested,
                    "untested": gap, "coverage_pct": round(coverage, 1),
                    "below_threshold": coverage < self.state["config"]["coverage_threshold"]}, None)

    def PredictDependencyIssues(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT dst_type, dst_id, COUNT(*) AS incoming FROM edges "
            "GROUP BY dst_type, dst_id HAVING incoming > 10 ORDER BY incoming DESC"
        )
        hubs = [{"type": r[0], "id": r[1], "incoming": r[2]}
                for r in cur.fetchall()]
        return (1, {"dependency_hubs": hubs[:50],
                    "hub_count": len(hubs)}, None)

    def PredictPerformanceBottleneck(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT m.method_id, m.method_name, m.cyclomatic_complexity, "
            "COUNT(e.edge_id) AS incoming FROM methods m "
            "LEFT JOIN edges e ON e.dst_type='method' AND e.dst_id=m.method_id "
            "GROUP BY m.method_id HAVING m.cyclomatic_complexity >= 10 AND incoming >= 3 "
            "ORDER BY m.cyclomatic_complexity DESC"
        )
        bottlenecks = [{"method_id": r[0], "method_name": r[1],
                        "complexity": r[2], "incoming": r[3]}
                       for r in cur.fetchall()]
        return (1, {"bottlenecks": bottlenecks[:50]}, None)

    def PredictCodeSmell(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_name, line_count, cyclomatic_complexity, "
            "has_print, has_self_underscore FROM methods "
            "WHERE line_count > 100 OR cyclomatic_complexity > 15"
        )
        smells = []
        for row in cur.fetchall():
            smell_types = []
            if row[2] and row[2] > 100:
                smell_types.append("long_method")
            if row[3] and row[3] > 15:
                smell_types.append("high_complexity")
            if row[4]:
                smell_types.append("print_statement")
            if row[5]:
                smell_types.append("self_underscore")
            smells.append({"method_id": row[0], "method_name": row[1],
                           "smells": smell_types})
        return (1, {"code_smells": smells[:50],
                    "count": len(smells)}, None)

    def PredictMaintenanceBurden(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM methods")
        total_methods = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=1 OR has_decorator=1 OR has_self_underscore=1")
        violations = cur.fetchone()[0]
        cur.execute("SELECT AVG(cyclomatic_complexity) FROM methods")
        avg_complexity = cur.fetchone()[0] or 0
        burden = (violations / total_methods * 100) if total_methods > 0 else 0
        return (1, {"total_methods": total_methods, "violations": violations,
                    "violation_pct": round(burden, 1),
                    "avg_complexity": round(avg_complexity, 1),
                    "burden_level": "high" if burden > 30 else ("medium" if burden > 10 else "low")}, None)

    def PredictTechnicalDebt(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM methods WHERE returns_tuple3=0")
        non_tuple3 = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=1")
        prints = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_decorator=1")
        decorators = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_self_underscore=1")
        underscores = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE cyclomatic_complexity >= 10")
        complex_methods = cur.fetchone()[0]
        debt_score = (non_tuple3 * 2 + prints * 3 + decorators * 3 +
                      underscores * 2 + complex_methods * 1)
        return (1, {"non_tuple3": non_tuple3, "prints": prints,
                    "decorators": decorators, "underscores": underscores,
                    "complex_methods": complex_methods,
                    "debt_score": debt_score,
                    "debt_level": "high" if debt_score > 100 else ("medium" if debt_score > 50 else "low")}, None)

    def PredictBugProbability(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_name, cyclomatic_complexity, "
            "line_count, has_print, has_self_underscore "
            "FROM methods"
        )
        probabilities = []
        for row in cur.fetchall():
            prob = 0
            if row[2] and row[2] >= 15:
                prob += 30
            if row[3] and row[3] > 100:
                prob += 20
            if row[4]:
                prob += 15
            if row[5]:
                prob += 15
            if row[2] and row[2] >= 10 and row[2] < 15:
                prob += 10
            probabilities.append({"method_id": row[0], "method_name": row[1],
                                  "bug_probability": min(prob, 100),
                                  "probability_level": "high" if prob >= 50 else ("medium" if prob >= 25 else "low")})
        probabilities.sort(key=lambda p: p["bug_probability"], reverse=True)
        return (1, {"probabilities": probabilities[:50]}, None)
