#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/priority_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 48: Priority Engine -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="priority_engine.py" domain="twin_priority" authority="PriorityEngine"}
# [@SUMMARY]{summary="Priority authority: rank methods by risk, rank classes by complexity, rank files by violations, rank fixes by urgency, rank knowledge by confidence, rank issues by impact, rank anomalies by severity, rank regressions by frequency, compute priority, priority report."}
# [@CLASS]{class="PriorityEngine" domain="priority" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="rank_methods_by_risk" type="command"}
# [@METHOD]{method="rank_classes_by_complexity" type="command"}
# [@METHOD]{method="rank_files_by_violations" type="command"}
# [@METHOD]{method="rank_fixes_by_urgency" type="command"}
# [@METHOD]{method="rank_knowledge_by_confidence" type="command"}
# [@METHOD]{method="rank_issues_by_impact" type="command"}
# [@METHOD]{method="rank_anomalies_by_severity" type="command"}
# [@METHOD]{method="rank_regressions_by_frequency" type="command"}
# [@METHOD]{method="compute_priority" type="command"}
# [@METHOD]{method="priority_report" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class PriorityEngine:
    """Authority for computing and ranking priorities."""

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
        if command == "rank_methods_by_risk":
            return self.RankMethodsByRisk(params)
        elif command == "rank_classes_by_complexity":
            return self.RankClassesByComplexity(params)
        elif command == "rank_files_by_violations":
            return self.RankFilesByViolations(params)
        elif command == "rank_fixes_by_urgency":
            return self.RankFixesByUrgency(params)
        elif command == "rank_knowledge_by_confidence":
            return self.RankKnowledgeByConfidence(params)
        elif command == "rank_issues_by_impact":
            return self.RankIssuesByImpact(params)
        elif command == "rank_anomalies_by_severity":
            return self.RankAnomaliesBySeverity(params)
        elif command == "rank_regressions_by_frequency":
            return self.RankRegressionsByFrequency(params)
        elif command == "compute_priority":
            return self.ComputePriority(params)
        elif command == "priority_report":
            return self.PriorityReport(params)
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

    def RankMethodsByRisk(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_name, cyclomatic_complexity, "
            "has_print, has_decorator, has_self_underscore, returns_tuple3 "
            "FROM methods ORDER BY cyclomatic_complexity DESC"
        )
        ranked = []
        for row in cur.fetchall():
            score = 0
            if row[2] and row[2] >= 15:
                score += 40
            elif row[2] and row[2] >= 10:
                score += 20
            if row[3]:
                score += 15
            if row[4]:
                score += 15
            if row[5]:
                score += 15
            if not row[6]:
                score += 15
            ranked.append({"method_id": row[0], "method_name": row[1],
                           "risk_score": score,
                           "priority": "P0" if score >= 70 else ("P1" if score >= 50 else ("P2" if score >= 30 else "P3"))})
        ranked.sort(key=lambda r: r["risk_score"], reverse=True)
        return (1, {"ranked": ranked[:100], "count": len(ranked)}, None)

    def RankClassesByComplexity(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT class_id, class_name, method_count FROM classes "
            "ORDER BY method_count DESC"
        )
        ranked = [{"class_id": r[0], "class_name": r[1],
                   "method_count": r[2],
                   "priority": "P0" if r[2] > 30 else ("P1" if r[2] > 20 else ("P2" if r[2] > 10 else "P3"))}
                  for r in cur.fetchall()]
        return (1, {"ranked": ranked[:100], "count": len(ranked)}, None)

    def RankFilesByViolations(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT f.file_id, f.file_name, COUNT(m.method_id) AS violations "
            "FROM files f JOIN methods m ON m.file_id=f.file_id "
            "WHERE m.has_print=1 OR m.has_decorator=1 OR m.has_self_underscore=1 OR m.returns_tuple3=0 "
            "GROUP BY f.file_id ORDER BY violations DESC"
        )
        ranked = [{"file_id": r[0], "file_name": r[1], "violations": r[2],
                   "priority": "P0" if r[2] > 20 else ("P1" if r[2] > 10 else ("P2" if r[2] > 5 else "P3"))}
                  for r in cur.fetchall()]
        return (1, {"ranked": ranked[:100], "count": len(ranked)}, None)

    def RankFixesByUrgency(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT a.method_id, m.method_name, COUNT(a.attempt_id) AS attempts, "
            "SUM(CASE WHEN a.rollback=1 THEN 1 ELSE 0 END) AS rollbacks "
            "FROM attempts a JOIN methods m ON m.method_id=a.method_id "
            "GROUP BY a.method_id ORDER BY rollbacks DESC, attempts DESC"
        )
        ranked = [{"method_id": r[0], "method_name": r[1],
                   "attempts": r[2], "rollbacks": r[3],
                   "priority": "P0" if r[3] > 3 else ("P1" if r[3] > 1 else ("P2" if r[2] > 3 else "P3"))}
                  for r in cur.fetchall()]
        return (1, {"ranked": ranked[:100], "count": len(ranked)}, None)

    def RankKnowledgeByConfidence(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT knowledge_id, problem, confidence FROM knowledge "
            "ORDER BY confidence ASC"
        )
        ranked = [{"knowledge_id": r[0], "problem": r[1], "confidence": r[2],
                   "priority": "P0" if r[2] < 20 else ("P1" if r[2] < 40 else ("P2" if r[2] < 60 else "P3"))}
                  for r in cur.fetchall()]
        return (1, {"ranked": ranked[:100], "count": len(ranked)}, None)

    def RankIssuesByImpact(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT dst_id, COUNT(*) AS incoming FROM edges WHERE dst_type='method' AND edge_type='calls' "
            "GROUP BY dst_id ORDER BY incoming DESC LIMIT 100"
        )
        ranked = [{"method_id": r[0], "incoming": r[1],
                   "priority": "P0" if r[1] > 10 else ("P1" if r[1] > 5 else ("P2" if r[1] > 2 else "P3"))}
                  for r in cur.fetchall()]
        return (1, {"ranked": ranked, "count": len(ranked)}, None)

    def RankAnomaliesBySeverity(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM methods WHERE cyclomatic_complexity >= 15")
        critical = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE cyclomatic_complexity >= 10 AND cyclomatic_complexity < 15")
        high = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=1 OR has_decorator=1 OR has_self_underscore=1")
        medium = cur.fetchone()[0]
        ranked = [
            {"anomaly": "critical_complexity", "count": critical, "priority": "P0"},
            {"anomaly": "high_complexity", "count": high, "priority": "P1"},
            {"anomaly": "vbstyle_violations", "count": medium, "priority": "P2"},
        ]
        return (1, {"ranked": ranked}, None)

    def RankRegressionsByFrequency(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, COUNT(*) AS failures FROM attempts "
            "WHERE compile_result=0 OR (compile_result=1 AND test_result=0) "
            "GROUP BY method_id ORDER BY failures DESC LIMIT 100"
        )
        ranked = [{"method_id": r[0], "failures": r[1],
                   "priority": "P0" if r[1] > 5 else ("P1" if r[1] > 3 else ("P2" if r[1] > 1 else "P3"))}
                  for r in cur.fetchall()]
        return (1, {"ranked": ranked, "count": len(ranked)}, None)

    def ComputePriority(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT cyclomatic_complexity, has_print, has_decorator, has_self_underscore, returns_tuple3 FROM methods WHERE method_id=?", (method_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
        score = 0
        if row[0] and row[0] >= 15:
            score += 30
        if row[1]:
            score += 15
        if row[2]:
            score += 15
        if row[3]:
            score += 15
        if not row[4]:
            score += 15
        cur.execute("SELECT COUNT(*) FROM edges WHERE dst_type='method' AND dst_id=? AND edge_type='calls'", (method_id,))
        incoming = cur.fetchone()[0]
        score += min(incoming * 2, 10)
        priority = "P0" if score >= 70 else ("P1" if score >= 50 else ("P2" if score >= 30 else "P3"))
        return (1, {"method_id": method_id, "priority_score": score,
                    "priority": priority, "incoming_calls": incoming}, None)

    def PriorityReport(self, params):
        results = {}
        for step in ("rank_methods_by_risk", "rank_classes_by_complexity",
                     "rank_files_by_violations", "rank_fixes_by_urgency",
                     "rank_knowledge_by_confidence", "rank_issues_by_impact",
                     "rank_anomalies_by_severity", "rank_regressions_by_frequency"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        results["generated"] = self.Now()[1]
        return (1, results, None)
