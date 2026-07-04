#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/signal_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 49: Signal Engine -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="signal_engine.py" domain="twin_signal" authority="SignalEngine"}
# [@SUMMARY]{summary="Signal authority: detect complexity signals, detect VBStyle signals, detect dependency signals, detect knowledge signals, detect anomaly signals, detect regression signals, detect health signals, detect evolution signals, rank signals, signal report."}
# [@CLASS]{class="SignalEngine" domain="signal" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="detect_complexity_signals" type="command"}
# [@METHOD]{method="detect_vbstyle_signals" type="command"}
# [@METHOD]{method="detect_dependency_signals" type="command"}
# [@METHOD]{method="detect_knowledge_signals" type="command"}
# [@METHOD]{method="detect_anomaly_signals" type="command"}
# [@METHOD]{method="detect_regression_signals" type="command"}
# [@METHOD]{method="detect_health_signals" type="command"}
# [@METHOD]{method="detect_evolution_signals" type="command"}
# [@METHOD]{method="rank_signals" type="command"}
# [@METHOD]{method="signal_report" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class SignalEngine:
    """Authority for detecting and ranking signals."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
            },
            "catalog": [],
            "results": [],
            "signals": [],
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "detect_complexity_signals":
            return self.DetectComplexitySignals(params)
        elif command == "detect_vbstyle_signals":
            return self.DetectVbstyleSignals(params)
        elif command == "detect_dependency_signals":
            return self.DetectDependencySignals(params)
        elif command == "detect_knowledge_signals":
            return self.DetectKnowledgeSignals(params)
        elif command == "detect_anomaly_signals":
            return self.DetectAnomalySignals(params)
        elif command == "detect_regression_signals":
            return self.DetectRegressionSignals(params)
        elif command == "detect_health_signals":
            return self.DetectHealthSignals(params)
        elif command == "detect_evolution_signals":
            return self.DetectEvolutionSignals(params)
        elif command == "rank_signals":
            return self.RankSignals(params)
        elif command == "signal_report":
            return self.SignalReport(params)
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

    def DetectComplexitySignals(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT AVG(cyclomatic_complexity) FROM methods")
        avg = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM methods WHERE cyclomatic_complexity >= 15")
        critical = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE cyclomatic_complexity >= 10 AND cyclomatic_complexity < 15")
        high = cur.fetchone()[0]
        signals = []
        if avg > 10:
            signals.append({"signal": "high_avg_complexity", "value": round(avg, 1), "strength": "strong"})
        if critical > 0:
            signals.append({"signal": "critical_complexity_methods", "count": critical, "strength": "critical"})
        if high > 0:
            signals.append({"signal": "high_complexity_methods", "count": high, "strength": "strong"})
        return (1, {"signals": signals, "count": len(signals)}, None)

    def DetectVbstyleSignals(self, params):
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
        signals = []
        if prints > 0:
            signals.append({"signal": "print_violations", "count": prints, "strength": "strong"})
        if decorators > 0:
            signals.append({"signal": "decorator_violations", "count": decorators, "strength": "strong"})
        if underscores > 0:
            signals.append({"signal": "underscore_violations", "count": underscores, "strength": "strong"})
        if non_tuple3 > 0:
            signals.append({"signal": "tuple3_violations", "count": non_tuple3, "strength": "critical"})
        return (1, {"signals": signals, "count": len(signals)}, None)

    def DetectDependencySignals(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM edges")
        total = cur.fetchone()[0]
        cur.execute("SELECT MAX(incoming) FROM (SELECT COUNT(*) AS incoming FROM edges GROUP BY dst_type, dst_id)")
        max_hub = cur.fetchone()[0] or 0
        signals = []
        if max_hub > 20:
            signals.append({"signal": "dependency_hub_overload", "max_incoming": max_hub, "strength": "critical"})
        if total > 500:
            signals.append({"signal": "high_edge_density", "total": total, "strength": "strong"})
        return (1, {"signals": signals, "count": len(signals)}, None)

    def DetectKnowledgeSignals(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT AVG(confidence) FROM knowledge")
        avg_conf = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE answer IS NULL OR answer = ''")
        no_fix = cur.fetchone()[0]
        signals = []
        if avg_conf < 50:
            signals.append({"signal": "low_knowledge_confidence", "value": round(avg_conf, 1), "strength": "strong"})
        if no_fix > 5:
            signals.append({"signal": "missing_fixes", "count": no_fix, "strength": "strong"})
        return (1, {"signals": signals, "count": len(signals)}, None)

    def DetectAnomalySignals(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM classes WHERE method_count > 30")
        god_classes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE line_count > 200")
        long_methods = cur.fetchone()[0]
        signals = []
        if god_classes > 0:
            signals.append({"signal": "god_classes", "count": god_classes, "strength": "critical"})
        if long_methods > 0:
            signals.append({"signal": "long_methods", "count": long_methods, "strength": "strong"})
        return (1, {"signals": signals, "count": len(signals)}, None)

    def DetectRegressionSignals(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM attempts WHERE rollback=1")
        rollbacks = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attempts WHERE compile_result=0")
        compile_fails = cur.fetchone()[0]
        signals = []
        if rollbacks > 3:
            signals.append({"signal": "high_rollback_rate", "count": rollbacks, "strength": "critical"})
        if compile_fails > 5:
            signals.append({"signal": "compile_failures", "count": compile_fails, "strength": "strong"})
        return (1, {"signals": signals, "count": len(signals)}, None)

    def DetectHealthSignals(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check")
        integrity = cur.fetchone()[0]
        signals = []
        if integrity != "ok":
            signals.append({"signal": "db_integrity_issue", "value": integrity, "strength": "critical"})
        cur.execute("SELECT COUNT(*) FROM methods WHERE returns_tuple3=1 AND has_print=0 AND has_decorator=0 AND has_self_underscore=0")
        clean = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        total = cur.fetchone()[0]
        compliance = (clean / total * 100) if total > 0 else 0
        if compliance < 80:
            signals.append({"signal": "low_vbstyle_compliance", "value": round(compliance, 1), "strength": "strong"})
        return (1, {"signals": signals, "count": len(signals)}, None)

    def DetectEvolutionSignals(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM observations WHERE observation_type LIKE '%lesson%'")
        lessons = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM knowledge")
        knowledge = cur.fetchone()[0]
        signals = []
        if lessons > 10:
            signals.append({"signal": "active_learning", "count": lessons, "strength": "positive"})
        if knowledge > 50:
            signals.append({"signal": "growing_knowledge_base", "count": knowledge, "strength": "positive"})
        return (1, {"signals": signals, "count": len(signals)}, None)

    def RankSignals(self, params):
        all_signals = []
        strength_order = {"critical": 0, "strong": 1, "positive": 2, "weak": 3}
        for step in ("detect_complexity_signals", "detect_vbstyle_signals",
                     "detect_dependency_signals", "detect_knowledge_signals",
                     "detect_anomaly_signals", "detect_regression_signals",
                     "detect_health_signals", "detect_evolution_signals"):
            res = self.Run(step, params)
            if res[0] == 1:
                for sig in res[1].get("signals", []):
                    sig["source"] = step
                    all_signals.append(sig)
        ranked = sorted(all_signals, key=lambda s: strength_order.get(s.get("strength", "weak"), 99))
        return (1, {"ranked": ranked, "total": len(ranked)}, None)

    def SignalReport(self, params):
        results = {}
        for step in ("detect_complexity_signals", "detect_vbstyle_signals",
                     "detect_dependency_signals", "detect_knowledge_signals",
                     "detect_anomaly_signals", "detect_regression_signals",
                     "detect_health_signals", "detect_evolution_signals"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        results["generated"] = self.Now()[1]
        return (1, results, None)
