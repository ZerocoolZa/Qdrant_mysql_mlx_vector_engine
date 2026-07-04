#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/intelligence_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 43: Intelligence Engine -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="intelligence_engine.py" domain="twin_intelligence" authority="IntelligenceEngine"}
# [@SUMMARY]{summary="Intelligence authority: compute code intelligence score, compute knowledge intelligence, compute fix intelligence, compute VBStyle intelligence, compute graph intelligence, compute prediction intelligence, compute learning intelligence, compute overall intelligence, intelligence trend, intelligence report."}
# [@CLASS]{class="IntelligenceEngine" domain="intelligence" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="code_intelligence" type="command"}
# [@METHOD]{method="knowledge_intelligence" type="command"}
# [@METHOD]{method="fix_intelligence" type="command"}
# [@METHOD]{method="vbstyle_intelligence" type="command"}
# [@METHOD]{method="graph_intelligence" type="command"}
# [@METHOD]{method="prediction_intelligence" type="command"}
# [@METHOD]{method="learning_intelligence" type="command"}
# [@METHOD]{method="overall_intelligence" type="command"}
# [@METHOD]{method="intelligence_trend" type="command"}
# [@METHOD]{method="intelligence_report" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class IntelligenceEngine:
    """Authority for computing intelligence scores."""

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
        if command == "code_intelligence":
            return self.CodeIntelligence(params)
        elif command == "knowledge_intelligence":
            return self.KnowledgeIntelligence(params)
        elif command == "fix_intelligence":
            return self.FixIntelligence(params)
        elif command == "vbstyle_intelligence":
            return self.VbstyleIntelligence(params)
        elif command == "graph_intelligence":
            return self.GraphIntelligence(params)
        elif command == "prediction_intelligence":
            return self.PredictionIntelligence(params)
        elif command == "learning_intelligence":
            return self.LearningIntelligence(params)
        elif command == "overall_intelligence":
            return self.OverallIntelligence(params)
        elif command == "intelligence_trend":
            return self.IntelligenceTrend(params)
        elif command == "intelligence_report":
            return self.IntelligenceReport(params)
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

    def CodeIntelligence(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM methods")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE returns_tuple3=1 AND has_print=0 AND has_decorator=0 AND has_self_underscore=0")
        clean = cur.fetchone()[0]
        cur.execute("SELECT AVG(cyclomatic_complexity) FROM methods")
        avg_cc = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM classes WHERE has_run_method=1 AND is_vbstyle=1")
        compliant_classes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM classes")
        total_classes = cur.fetchone()[0]
        score = 0
        if total > 0:
            score += (clean / total) * 40
        if avg_cc < 10:
            score += 20
        elif avg_cc < 15:
            score += 10
        if total_classes > 0:
            score += (compliant_classes / total_classes) * 40
        return (1, {"code_intelligence": round(score, 1),
                    "clean_methods": clean, "total_methods": total,
                    "compliant_classes": compliant_classes,
                    "total_classes": total_classes}, None)

    def KnowledgeIntelligence(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM knowledge")
        total = cur.fetchone()[0]
        cur.execute("SELECT AVG(confidence) FROM knowledge")
        avg_conf = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE answer IS NOT NULL AND answer != ''")
        with_fix = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE root_cause IS NOT NULL AND root_cause != ''")
        with_root_cause = cur.fetchone()[0]
        score = 0
        if total > 0:
            score += min(avg_conf, 100) * 0.4
            score += (with_fix / total) * 30
            score += (with_root_cause / total) * 30
        return (1, {"knowledge_intelligence": round(score, 1),
                    "total": total, "avg_confidence": round(avg_conf, 1),
                    "with_fix": with_fix, "with_root_cause": with_root_cause}, None)

    def FixIntelligence(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM attempts")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attempts WHERE compile_result=1 AND test_result=1")
        successes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attempts WHERE rollback=1")
        rollbacks = cur.fetchone()[0]
        score = 0
        if total > 0:
            score += (successes / total) * 60
            score += (1 - rollbacks / total) * 40
        return (1, {"fix_intelligence": round(score, 1),
                    "total_attempts": total, "successes": successes,
                    "rollbacks": rollbacks}, None)

    def VbstyleIntelligence(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM methods")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=0 AND has_decorator=0 AND has_self_underscore=0 AND returns_tuple3=1")
        clean = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM classes WHERE has_run_method=1")
        has_run = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM classes")
        total_classes = cur.fetchone()[0]
        score = 0
        if total > 0:
            score += (clean / total) * 60
        if total_classes > 0:
            score += (has_run / total_classes) * 40
        return (1, {"vbstyle_intelligence": round(score, 1),
                    "clean_methods": clean, "total_methods": total,
                    "has_run_classes": has_run}, None)

    def GraphIntelligence(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM edges")
        total = cur.fetchone()[0]
        cur.execute("SELECT AVG(confidence) FROM edges")
        avg_conf = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(DISTINCT edge_type) FROM edges")
        types = cur.fetchone()[0]
        score = 0
        if total > 0:
            score += min(avg_conf, 100) * 0.5
        score += min(types * 5, 50)
        return (1, {"graph_intelligence": round(score, 1),
                    "total_edges": total, "avg_confidence": round(avg_conf, 1),
                    "edge_types": types}, None)

    def PredictionIntelligence(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM observations WHERE observation_type LIKE '%lesson%'")
        lessons = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM observations WHERE observation_type LIKE '%pattern%'")
        patterns = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE confidence >= 80")
        high_conf = cur.fetchone()[0]
        score = min(lessons * 2 + patterns * 3 + high_conf, 100)
        return (1, {"prediction_intelligence": round(score, 1),
                    "lessons": lessons, "patterns": patterns,
                    "high_confidence": high_conf}, None)

    def LearningIntelligence(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM observations WHERE observation_type LIKE '%lesson%' OR observation_type LIKE '%learning%'")
        learnings = cur.fetchone()[0]
        cur.execute("SELECT AVG(confidence) FROM observations WHERE observation_type LIKE '%lesson%'")
        avg_conf = cur.fetchone()[0] or 0
        score = min(learnings * 2 + avg_conf * 0.5, 100)
        return (1, {"learning_intelligence": round(score, 1),
                    "total_learnings": learnings,
                    "avg_confidence": round(avg_conf, 1)}, None)

    def OverallIntelligence(self, params):
        scores = []
        for step in ("code_intelligence", "knowledge_intelligence",
                     "fix_intelligence", "vbstyle_intelligence",
                     "graph_intelligence", "prediction_intelligence",
                     "learning_intelligence"):
            res = self.Run(step, params)
            if res[0] == 1:
                for key, value in res[1].items():
                    if "intelligence" in key.lower() and isinstance(value, (int, float)):
                        scores.append(value)
        overall = sum(scores) / len(scores) if scores else 0
        return (1, {"overall_intelligence": round(overall, 1),
                    "component_scores": scores,
                    "level": "high" if overall >= 70 else ("medium" if overall >= 40 else "low")}, None)

    def IntelligenceTrend(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM attempts WHERE compile_result=1 AND test_result=1")
        successes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attempts WHERE rollback=1")
        rollbacks = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM observations WHERE observation_type LIKE '%lesson%'")
        learnings = cur.fetchone()[0]
        if successes > rollbacks and learnings > 0:
            trend = "improving"
        elif successes < rollbacks:
            trend = "declining"
        else:
            trend = "stable"
        return (1, {"trend": trend, "successes": successes,
                    "rollbacks": rollbacks, "learnings": learnings}, None)

    def IntelligenceReport(self, params):
        results = {}
        for step in ("code_intelligence", "knowledge_intelligence",
                     "fix_intelligence", "vbstyle_intelligence",
                     "graph_intelligence", "prediction_intelligence",
                     "learning_intelligence", "overall_intelligence",
                     "intelligence_trend"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        results["generated"] = self.Now()[1]
        return (1, results, None)
