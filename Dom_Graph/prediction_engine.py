#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/prediction_engine.py"
# date="2026-06-26" author="Devin" session_id="phase6-intelligence"
# context="Project Digital Twin Section 59 Prediction Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="prediction_engine.py" domain="twin_prediction" authority="PredictionEngine"}
# [@SUMMARY]{summary="Prediction authority that predicts next errors, broken code, side effects, build failures, refactor risk, and maintenance costs."}
# [@CLASS]{class="PredictionEngine" domain="prediction" authority="single"}
# [@METHOD]{method="predict_next_error" type="command"}
# [@METHOD]{method="predict_broken_code" type="command"}
# [@METHOD]{method="predict_side_effects" type="command"}
# [@METHOD]{method="predict_build_failure" type="command"}
# [@METHOD]{method="predict_runtime_failure" type="command"}
# [@METHOD]{method="predict_performance_impact" type="command"}
# [@METHOD]{method="predict_refactor_risk" type="command"}
# [@METHOD]{method="predict_maintenance_cost" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<PredictionEngine: predicts next errors broken code side effects build failures refactor risk maintenance costs. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations. Header missing Run method declaration but Run() exists in code.>][@todos<none>]}
"""
PredictionEngine -- Prediction authority.
Implements Section 59 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: predict_next_error, predict_broken_code, predict_side_effects, predict_build_failure, predict_refactor_risk, predict_maintenance_cost.
"""
import os
import sqlite3

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class PredictionEngine:
    """Prediction authority."""

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
        if command == "predict_next_error":
            return self.PredictNextError(params)
        elif command == "predict_broken_code":
            return self.PredictBrokenCode(params)
        elif command == "predict_side_effects":
            return self.PredictSideEffects(params)
        elif command == "predict_build_failure":
            return self.PredictBuildFailure(params)
        elif command == "predict_runtime_failure":
            return self.PredictRuntimeFailure(params)
        elif command == "predict_performance_impact":
            return self.PredictPerformanceImpact(params)
        elif command == "predict_refactor_risk":
            return self.PredictRefactorRisk(params)
        elif command == "predict_maintenance_cost":
            return self.PredictMaintenanceCost(params)

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

    def PredictNextError(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT error_type, COUNT(*) FROM knowledge "
                    "WHERE error_type IS NOT NULL AND error_type != '' "
                    "GROUP BY error_type ORDER BY COUNT(*) DESC")
        rows = cur.fetchall()
        total = sum(r[1] for r in rows) if rows else 0
        if not rows or total == 0:
            return (1, {"predicted_error_type": "unknown",
                        "likelihood": 0, "at_risk_methods": []}, None)
        top = rows[0]
        predicted_type = top[0]
        likelihood = round(top[1] / total, 4)
        cur.execute("SELECT method_id, method_name, cyclomatic_complexity "
                    "FROM methods WHERE cyclomatic_complexity > 10 "
                    "ORDER BY cyclomatic_complexity DESC LIMIT 20")
        at_risk = [{"method_id": r[0], "method_name": r[1],
                    "complexity": r[2]} for r in cur.fetchall()]
        return (1, {"predicted_error_type": predicted_type,
                    "likelihood": likelihood, "total_errors": total,
                    "at_risk_methods": at_risk}, None)

    def PredictBrokenCode(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, cyclomatic_complexity, "
                    "version FROM methods WHERE cyclomatic_complexity > 10 "
                    "AND version > 1 ORDER BY cyclomatic_complexity DESC")
        at_risk = [{"method_id": r[0], "method_name": r[1],
                    "complexity": r[2], "version": r[3]} for r in cur.fetchall()]
        return (1, {"at_risk_methods": at_risk, "count": len(at_risk)}, None)

    def PredictSideEffects(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("WITH RECURSIVE forward AS ("
                    "SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type "
                    "FROM edges WHERE src_type='method' AND src_id=? AND edge_type='calls' "
                    "UNION SELECT e.edge_id, e.src_type, e.src_id, e.dst_type, e.dst_id, e.edge_type "
                    "FROM edges e JOIN forward f ON e.src_type='method' AND e.src_id=f.dst_id "
                    "WHERE e.edge_type='calls') "
                    "SELECT DISTINCT dst_id FROM forward", (method_id,))
        affected = [r[0] for r in cur.fetchall()]
        radius = len(affected)
        return (1, {"ripple_radius": radius, "method_id": method_id,
                    "affected_methods": affected}, None)

    def PredictBuildFailure(self, params):
        import py_compile
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT path FROM files WHERE extension='.py' OR extension='py'")
        issues = []
        total = 0
        for row in cur.fetchall():
            path = row[0]
            if not path or not os.path.isfile(path):
                continue
            total = total + 1
            try:
                py_compile.compile(path, doraise=True)
            except py_compile.PyCompileError as exc:
                issues.append({"file": path, "error": str(exc)[:200]})
            except Exception as exc:
                issues.append({"file": path, "error": str(exc)[:200]})
        failure_risk = len(issues) > 0
        risk_score = round(len(issues) / total, 4) if total else 0
        return (1, {"failure_risk": failure_risk, "risk_score": risk_score,
                    "issues": issues, "total_files": total,
                    "failed_files": len(issues)}, None)

    def PredictRuntimeFailure(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, cyclomatic_complexity "
                    "FROM methods WHERE cyclomatic_complexity > 10 "
                    "AND method_id NOT IN ("
                    "SELECT DISTINCT method_id FROM methods "
                    "WHERE method_name LIKE 'test_%') "
                    "ORDER BY cyclomatic_complexity DESC LIMIT 50")
        at_risk = [{"method_id": r[0], "method_name": r[1],
                    "complexity": r[2]} for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) FROM methods WHERE method_name LIKE 'test_%'")
        tested = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        total = cur.fetchone()[0]
        coverage = round(tested / total, 4) if total else 0
        return (1, {"at_risk_methods": at_risk, "count": len(at_risk),
                    "test_coverage": coverage}, None)

    def PredictPerformanceImpact(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, cyclomatic_complexity, calls "
                    "FROM methods WHERE cyclomatic_complexity > 10 "
                    "AND calls IS NOT NULL AND calls != '' "
                    "ORDER BY cyclomatic_complexity DESC LIMIT 50")
        hot_methods = []
        for r in cur.fetchall():
            calls_len = len(r[3] or "")
            hot_methods.append({
                "method_id": r[0],
                "method_name": r[1],
                "complexity": r[2],
                "call_count": calls_len,
                "impact_score": round(r[2] * calls_len, 2),
            })
        return (1, {"hot_path_methods": hot_methods,
                    "count": len(hot_methods)}, None)

    def PredictRefactorRisk(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        side_res = self.PredictSideEffects(params)
        if side_res[0] != 1:
            return side_res
        radius = side_res[1]["ripple_radius"]
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT cyclomatic_complexity FROM methods WHERE method_id=?", (method_id,))
        row = cur.fetchone()
        complexity = row[0] if row else 0
        cur.execute("SELECT COUNT(*) FROM methods WHERE method_name LIKE 'test_%'")
        tested = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        total = cur.fetchone()[0]
        coverage = tested / total if total > 0 else 0
        risk = round(radius * complexity * (1 - coverage), 4)
        return (1, {"refactor_risk": risk, "radius": radius,
                    "complexity": complexity,
                    "coverage": round(coverage * 100, 2)}, None)

    def PredictMaintenanceCost(self, params):
        method_id = self._p(params, "method_id")
        class_id = self._p(params, "class_id")
        conn = self.Connect()
        cur = conn.cursor()
        if method_id:
            cur.execute("SELECT cyclomatic_complexity, version FROM methods WHERE method_id=?", (method_id,))
        elif class_id:
            cur.execute("SELECT AVG(cyclomatic_complexity), MAX(version) FROM methods WHERE class_id=?", (class_id,))
        else:
            return (0, None, ("NO_PARAM", "method_id or class_id required", 0))
        row = cur.fetchone()
        complexity = row[0] or 0
        version = row[1] or 1
        cost = round(complexity + version * 2, 4)
        return (1, {"maintenance_cost": cost, "complexity": complexity,
                    "version": version}, None)

