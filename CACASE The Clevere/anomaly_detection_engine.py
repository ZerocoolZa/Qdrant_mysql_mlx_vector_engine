#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/anomaly_detection_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 30: Anomaly Detection -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="anomaly_detection_engine.py" domain="twin_anomaly" authority="AnomalyDetectionEngine"}
# [@SUMMARY]{summary="Anomaly detection authority: detect complexity anomalies, detect size anomalies, detect dependency anomalies, detect naming anomalies, detect VBStyle anomalies, detect structural anomalies, detect behavioral anomalies, detect knowledge anomalies, rank anomalies, anomaly report."}
# [@CLASS]{class="AnomalyDetectionEngine" domain="anomaly_detection" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="detect_complexity_anomalies" type="command"}
# [@METHOD]{method="detect_size_anomalies" type="command"}
# [@METHOD]{method="detect_dependency_anomalies" type="command"}
# [@METHOD]{method="detect_naming_anomalies" type="command"}
# [@METHOD]{method="detect_vbstyle_anomalies" type="command"}
# [@METHOD]{method="detect_structural_anomalies" type="command"}
# [@METHOD]{method="detect_behavioral_anomalies" type="command"}
# [@METHOD]{method="detect_knowledge_anomalies" type="command"}
# [@METHOD]{method="rank_anomalies" type="command"}
# [@METHOD]{method="anomaly_report" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class AnomalyDetectionEngine:
    """Authority for detecting anomalies across the codebase."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "complexity_stddev_threshold": 2.0,
                "size_stddev_threshold": 2.0,
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
        if command == "detect_complexity_anomalies":
            return self.DetectComplexityAnomalies(params)
        elif command == "detect_size_anomalies":
            return self.DetectSizeAnomalies(params)
        elif command == "detect_dependency_anomalies":
            return self.DetectDependencyAnomalies(params)
        elif command == "detect_naming_anomalies":
            return self.DetectNamingAnomalies(params)
        elif command == "detect_vbstyle_anomalies":
            return self.DetectVbstyleAnomalies(params)
        elif command == "detect_structural_anomalies":
            return self.DetectStructuralAnomalies(params)
        elif command == "detect_behavioral_anomalies":
            return self.DetectBehavioralAnomalies(params)
        elif command == "detect_knowledge_anomalies":
            return self.DetectKnowledgeAnomalies(params)
        elif command == "rank_anomalies":
            return self.RankAnomalies(params)
        elif command == "anomaly_report":
            return self.AnomalyReport(params)
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

    def DetectComplexityAnomalies(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT AVG(cyclomatic_complexity) FROM methods WHERE cyclomatic_complexity IS NOT NULL")
        avg = cur.fetchone()[0] or 0
        cur.execute("SELECT method_id, method_name, cyclomatic_complexity FROM methods WHERE cyclomatic_complexity IS NOT NULL AND cyclomatic_complexity > ? ORDER BY cyclomatic_complexity DESC", (avg * 2,))
        anomalies = [{"method_id": r[0], "method_name": r[1],
                      "complexity": r[2], "avg": round(avg, 1)}
                     for r in cur.fetchall()]
        return (1, {"anomalies": anomalies[:50],
                    "count": len(anomalies), "avg_complexity": round(avg, 1)}, None)

    def DetectSizeAnomalies(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT AVG(line_count) FROM methods WHERE line_count IS NOT NULL")
        avg = cur.fetchone()[0] or 0
        cur.execute("SELECT method_id, method_name, line_count FROM methods WHERE line_count IS NOT NULL AND line_count > ? ORDER BY line_count DESC", (avg * 3,))
        anomalies = [{"method_id": r[0], "method_name": r[1],
                      "line_count": r[2], "avg": round(avg, 1)}
                     for r in cur.fetchall()]
        return (1, {"anomalies": anomalies[:50],
                    "count": len(anomalies), "avg_lines": round(avg, 1)}, None)

    def DetectDependencyAnomalies(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT dst_type, dst_id, COUNT(*) AS incoming FROM edges "
            "GROUP BY dst_type, dst_id HAVING incoming > 15 ORDER BY incoming DESC"
        )
        anomalies = [{"type": r[0], "id": r[1], "incoming": r[2]}
                     for r in cur.fetchall()]
        return (1, {"anomalies": anomalies[:50],
                    "count": len(anomalies)}, None)

    def DetectNamingAnomalies(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        anomalies = []
        cur.execute("SELECT class_name FROM classes")
        for row in cur.fetchall():
            name = row[0]
            if name and name[0].islower():
                anomalies.append({"type": "class", "name": name,
                                  "issue": "lowercase_start"})
            if name and "_" in name:
                anomalies.append({"type": "class", "name": name,
                                  "issue": "underscore_in_name"})
        cur.execute("SELECT method_name FROM methods WHERE method_name NOT LIKE '\\_%' AND method_name NOT LIKE '\\\\__%'")
        for row in cur.fetchall():
            name = row[0]
            if name and name[0].isupper() and not name.startswith("__"):
                anomalies.append({"type": "method", "name": name,
                                  "issue": "uppercase_start"})
        return (1, {"anomalies": anomalies[:100],
                    "count": len(anomalies)}, None)

    def DetectVbstyleAnomalies(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        anomalies = []
        cur.execute("SELECT method_id, method_name, has_print, has_decorator, has_self_underscore, returns_tuple3 FROM methods WHERE has_print=1 OR has_decorator=1 OR has_self_underscore=1 OR returns_tuple3=0")
        for row in cur.fetchall():
            issues = []
            if row[2]:
                issues.append("print")
            if row[3]:
                issues.append("decorator")
            if row[4]:
                issues.append("self._")
            if not row[5]:
                issues.append("no_tuple3")
            anomalies.append({"method_id": row[0], "method_name": row[1],
                              "issues": issues})
        return (1, {"anomalies": anomalies[:100],
                    "count": len(anomalies)}, None)

    def DetectStructuralAnomalies(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        anomalies = []
        cur.execute("SELECT class_id, class_name, method_count FROM classes WHERE method_count > 30")
        for row in cur.fetchall():
            anomalies.append({"class_id": row[0], "class_name": row[1],
                              "method_count": row[2], "issue": "god_class"})
        cur.execute("SELECT class_id, class_name FROM classes WHERE has_run_method=0")
        for row in cur.fetchall():
            anomalies.append({"class_id": row[0], "class_name": row[1],
                              "issue": "missing_run"})
        return (1, {"anomalies": anomalies[:100],
                    "count": len(anomalies)}, None)

    def DetectBehavioralAnomalies(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        anomalies = []
        cur.execute(
            "SELECT method_id, COUNT(*) AS attempts FROM attempts "
            "GROUP BY method_id HAVING attempts > 5"
        )
        for row in cur.fetchall():
            anomalies.append({"method_id": row[0], "attempts": row[1],
                              "issue": "repeated_fixes"})
        cur.execute(
            "SELECT method_id, COUNT(*) AS rollbacks FROM attempts "
            "WHERE rollback=1 GROUP BY method_id HAVING rollbacks > 2"
        )
        for row in cur.fetchall():
            anomalies.append({"method_id": row[0], "rollbacks": row[1],
                              "issue": "repeated_rollbacks"})
        return (1, {"anomalies": anomalies[:100],
                    "count": len(anomalies)}, None)

    def DetectKnowledgeAnomalies(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        anomalies = []
        cur.execute("SELECT knowledge_id, problem, confidence FROM knowledge WHERE confidence < 30")
        for row in cur.fetchall():
            anomalies.append({"knowledge_id": row[0], "problem": row[1],
                              "confidence": row[2], "issue": "low_confidence"})
        cur.execute("SELECT knowledge_id, problem FROM knowledge WHERE answer IS NULL OR answer = ''")
        for row in cur.fetchall():
            anomalies.append({"knowledge_id": row[0], "problem": row[1],
                              "issue": "no_answer"})
        return (1, {"anomalies": anomalies[:100],
                    "count": len(anomalies)}, None)

    def RankAnomalies(self, params):
        all_anomalies = []
        for step in ("detect_complexity_anomalies", "detect_size_anomalies",
                     "detect_dependency_anomalies", "detect_vbstyle_anomalies",
                     "detect_structural_anomalies", "detect_behavioral_anomalies",
                     "detect_knowledge_anomalies"):
            res = self.Run(step, params)
            if res[0] == 1:
                for a in res[1].get("anomalies", []):
                    a["source"] = step
                    all_anomalies.append(a)
        ranked = sorted(all_anomalies, key=lambda a: a.get("count", 1), reverse=True)
        return (1, {"ranked": ranked[:200], "total": len(ranked)}, None)

    def AnomalyReport(self, params):
        results = {}
        for step in ("detect_complexity_anomalies", "detect_size_anomalies",
                     "detect_dependency_anomalies", "detect_naming_anomalies",
                     "detect_vbstyle_anomalies", "detect_structural_anomalies",
                     "detect_behavioral_anomalies", "detect_knowledge_anomalies"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        results["generated"] = self.Now()[1]
        return (1, results, None)
