#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/meta_learning_engine.py"
# date="2026-06-26" author="Devin" session_id="phase7-meta"
# context="Project Digital Twin Phase 7 Section 70 Meta Learning Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="meta_learning_engine.py" domain="twin_meta" authority="MetaLearningEngine"}
# [@SUMMARY]{summary="Meta learning authority that analyzes attempt history, optimizes fix strategies, evolves heuristics and benchmarks improvement over time."}
# [@CLASS]{class="MetaLearningEngine" domain="meta" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="learn_from_history" type="command"}
# [@METHOD]{method="improve_graph_accuracy" type="command"}
# [@METHOD]{method="optimize_strategies" type="command"}
# [@METHOD]{method="evolve_heuristics" type="command"}
# [@METHOD]{method="reduce_failures" type="command"}
# [@METHOD]{method="improve_predictions" type="command"}
# [@METHOD]{method="adapt_schema" type="command"}
# [@METHOD]{method="benchmark" type="command"}
# [@METHOD]{method="improve" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<MetaLearningEngine: analyzes attempt history optimizes fix strategies evolves heuristics benchmarks improvement. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations.>][@todos<none>]}
"""
MetaLearningEngine -- authority for meta learning and strategy optimization.
Implements Section 70 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: learn_from_history, optimize_strategies, evolve_heuristics,
          benchmark, improve.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
DEFAULT_THRESHOLD = 50
THRESHOLD_ADJUST_STEP = 5
MAX_THRESHOLD = 100
MIN_THRESHOLD = 0


class MetaLearningEngine:
    """Authority for meta learning, strategy optimization and heuristics evolution."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
                "violation_threshold": DEFAULT_THRESHOLD,
                "threshold_adjust_step": THRESHOLD_ADJUST_STEP,
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
        if command == "learn_from_history":
            return self.LearnFromHistory(params)
        elif command == "improve_graph_accuracy":
            return self.ImproveGraphAccuracy(params)
        elif command == "optimize_strategies":
            return self.OptimizeStrategies(params)
        elif command == "evolve_heuristics":
            return self.EvolveHeuristics(params)
        elif command == "reduce_failures":
            return self.ReduceFailures(params)
        elif command == "improve_predictions":
            return self.ImprovePredictions(params)
        elif command == "adapt_schema":
            return self.AdaptSchema(params)
        elif command == "benchmark":
            return self.Benchmark(params)
        elif command == "improve":
            return self.Improve(params)
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

    def LearnFromHistory(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT action, COUNT(*), SUM(compile_result), SUM(test_result) "
                "FROM attempts GROUP BY action ORDER BY COUNT(*) DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        patterns = []
        for row in rows:
            action = row[0]
            total = row[1] or 0
            compiled = row[2] or 0
            tested = row[3] or 0
            compile_rate = (compiled / total) if total else 0
            test_rate = (tested / total) if total else 0
            status = "success"
            if test_rate < 0.5:
                status = "failure"
            elif test_rate < 0.8:
                status = "mixed"
            patterns.append({
                "action": action,
                "total": total,
                "compiled": compiled,
                "tested": tested,
                "compile_rate": round(compile_rate, 4),
                "test_rate": round(test_rate, 4),
                "status": status,
            })
        self.state["results"] = patterns
        return (1, {"patterns": patterns, "count": len(patterns)}, None)

    def OptimizeStrategies(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT fix_applied, AVG(confidence), "
                "SUM(CASE WHEN fix_result='success' THEN 1 ELSE 0 END) "
                "FROM knowledge WHERE fix_applied IS NOT NULL "
                "GROUP BY fix_applied ORDER BY AVG(confidence) DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        strategies = []
        for row in rows:
            fix_applied = row[0]
            avg_confidence = row[1] or 0
            success_count = row[2] or 0
            strategies.append({
                "fix_applied": fix_applied,
                "avg_confidence": round(avg_confidence, 4),
                "success_count": success_count,
            })
        strategies.sort(key=lambda s: s["avg_confidence"], reverse=True)
        ranked = []
        for index, strategy in enumerate(strategies):
            entry = dict(strategy)
            entry["rank"] = index + 1
            ranked.append(entry)
        self.state["results"] = ranked
        return (1, {"strategies": ranked, "count": len(ranked)}, None)

    def EvolveHeuristics(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT observation_type, COUNT(*), AVG(confidence) "
                "FROM observations GROUP BY observation_type "
                "ORDER BY COUNT(*) DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        current_threshold = self.state["config"]["violation_threshold"]
        step = self.state["config"]["threshold_adjust_step"]
        adjusted = {}
        new_threshold = current_threshold
        for row in rows:
            obs_type = row[0]
            count = row[1] or 0
            avg_conf = row[2] or 0
            false_positive_rate = 0
            if avg_conf < 50:
                false_positive_rate = (100 - avg_conf) / 100
            new_threshold = current_threshold
            if false_positive_rate > 0.3:
                new_threshold = current_threshold + step
            elif false_positive_rate < 0.1:
                new_threshold = current_threshold - step
            if new_threshold > MAX_THRESHOLD:
                new_threshold = MAX_THRESHOLD
            if new_threshold < MIN_THRESHOLD:
                new_threshold = MIN_THRESHOLD
            adjusted[obs_type] = {
                "count": count,
                "avg_confidence": round(avg_conf, 4),
                "false_positive_rate": round(false_positive_rate, 4),
                "old_threshold": current_threshold,
                "new_threshold": new_threshold,
            }
        self.state["config"]["violation_threshold"] = new_threshold
        self.state["results"] = adjusted
        return (1, {"thresholds": adjusted,
                    "global_threshold": new_threshold}, None)

    def Benchmark(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT COUNT(*), "
                "SUM(CASE WHEN fix_result='success' THEN 1 ELSE 0 END) "
                "FROM knowledge"
            )
            knowledge_row = cur.fetchone()
            cur.execute(
                "SELECT created, COUNT(*), "
                "SUM(CASE WHEN fix_result='success' THEN 1 ELSE 0 END) "
                "FROM knowledge WHERE created IS NOT NULL "
                "GROUP BY created ORDER BY created DESC LIMIT ?",
                (limit,),
            )
            time_rows = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        total_errors = knowledge_row[0] or 0
        total_fixes = knowledge_row[1] or 0
        error_rate = (total_errors / total_fixes) if total_fixes else 0
        fix_rate = (total_fixes / total_errors) if total_errors else 0
        timeline = []
        for row in time_rows:
            created = row[0]
            count = row[1] or 0
            fixed = row[2] or 0
            timeline.append({
                "created": created,
                "errors": count,
                "fixed": fixed,
                "fix_rate": round((fixed / count) if count else 0, 4),
            })
        metrics = {
            "total_errors": total_errors,
            "total_fixes": total_fixes,
            "error_rate": round(error_rate, 4),
            "fix_rate": round(fix_rate, 4),
            "timeline": timeline,
        }
        self.state["results"] = metrics
        return (1, {"benchmarks": metrics}, None)

    def ImproveGraphAccuracy(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM methods WHERE calls IS NOT NULL "
                    "AND calls != ''")
        methods_with_calls = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM edges WHERE edge_type='calls'")
        call_edges = cur.fetchone()[0]
        missing = methods_with_calls - call_edges
        if missing < 0:
            missing = 0
        cur.execute("SELECT COUNT(*) FROM files WHERE imports IS NOT NULL "
                    "AND imports != ''")
        files_with_imports = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM edges WHERE edge_type='imports'")
        import_edges = cur.fetchone()[0]
        missing_imports = files_with_imports - import_edges
        if missing_imports < 0:
            missing_imports = 0
        result = {
            "methods_with_calls": methods_with_calls,
            "call_edges": call_edges,
            "missing_call_edges": missing,
            "files_with_imports": files_with_imports,
            "import_edges": import_edges,
            "missing_import_edges": missing_imports,
            "total_missing": missing + missing_imports,
        }
        self.state["results"] = result
        return (1, result, None)

    def ReduceFailures(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT fix_applied, COUNT(*) FROM knowledge "
                "WHERE fix_result != 'success' AND fix_applied IS NOT NULL "
                "AND fix_applied != '' GROUP BY fix_applied "
                "ORDER BY COUNT(*) DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        failures = []
        blacklist = []
        for row in rows:
            fix = row[0]
            count = row[1] or 0
            failures.append({"fix_applied": fix, "failure_count": count})
            if count >= 3:
                blacklist.append(fix)
        result = {
            "failure_patterns": failures,
            "blacklist": blacklist,
            "total_patterns": len(failures),
        }
        self.state["results"] = result
        return (1, result, None)

    def ImprovePredictions(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT error_type, COUNT(*), "
                "SUM(CASE WHEN fix_result='success' THEN 1 ELSE 0 END) "
                "FROM knowledge WHERE error_type IS NOT NULL "
                "AND error_type != '' GROUP BY error_type"
            )
            rows = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        weights = {}
        for row in rows:
            error_type = row[0]
            total = row[1] or 0
            success = row[2] or 0
            accuracy = round(success / total, 4) if total else 0
            weights[error_type] = {
                "total": total,
                "success": success,
                "accuracy": accuracy,
                "weight": round(accuracy * 100, 2),
            }
        result = {"prediction_weights": weights,
                  "types_tracked": len(weights)}
        self.state["results"] = result
        return (1, result, None)

    def AdaptSchema(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        existing_tables = [r[0] for r in cur.fetchall()]
        suggestions = []
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE root_cause IS NULL")
        missing_root_cause = cur.fetchone()[0]
        if missing_root_cause > 0:
            suggestions.append({
                "table": "knowledge",
                "column": "root_cause",
                "reason": "root_cause column has NULL values",
                "action": "populate",
            })
        cur.execute("SELECT COUNT(*) FROM methods WHERE hash IS NULL")
        missing_hash = cur.fetchone()[0]
        if missing_hash > 0:
            suggestions.append({
                "table": "methods",
                "column": "hash",
                "reason": "hash column has NULL values",
                "action": "populate",
            })
        if "twin_metadata" not in existing_tables:
            suggestions.append({
                "table": "twin_metadata",
                "column": None,
                "reason": "metadata table missing",
                "action": "create",
            })
        result = {
            "existing_tables": existing_tables,
            "suggestions": suggestions,
            "suggestion_count": len(suggestions),
        }
        self.state["results"] = result
        return (1, result, None)

    def Improve(self, params):
        history = self.LearnFromHistory(params)
        if history[0] != 1:
            return history
        strategies = self.OptimizeStrategies(params)
        if strategies[0] != 1:
            return strategies
        heuristics = self.EvolveHeuristics(params)
        if heuristics[0] != 1:
            return heuristics
        benchmarks = self.Benchmark(params)
        if benchmarks[0] != 1:
            return benchmarks
        recommendations = []
        patterns = history[1].get("patterns", [])
        for pattern in patterns:
            if pattern["status"] == "failure":
                recommendations.append({
                    "action": pattern["action"],
                    "recommendation": "avoid",
                    "reason": "low test success rate",
                })
            elif pattern["status"] == "success":
                recommendations.append({
                    "action": pattern["action"],
                    "recommendation": "prefer",
                    "reason": "high test success rate",
                })
        strat_list = strategies[1].get("strategies", [])
        if strat_list:
            recommendations.append({
                "action": strat_list[0]["fix_applied"],
                "recommendation": "top_strategy",
                "reason": "highest avg confidence",
            })
        plan = {
            "patterns": patterns,
            "strategies": strat_list,
            "thresholds": heuristics[1].get("thresholds", {}),
            "benchmarks": benchmarks[1].get("benchmarks", {}),
            "recommendations": recommendations,
        }
        self.state["results"] = plan
        return (1, plan, None)
