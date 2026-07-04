#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/feedback_loop_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 46: Feedback Loop -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="feedback_loop_engine.py" domain="twin_feedback" authority="FeedbackLoopEngine"}
# [@SUMMARY]{summary="Feedback loop authority: collect feedback, process feedback, apply feedback, measure feedback impact, detect feedback pattern, rank feedback, link feedback to fix, link feedback to learning, feedback cycle, feedback report."}
# [@CLASS]{class="FeedbackLoopEngine" domain="feedback_loop" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="collect_feedback" type="command"}
# [@METHOD]{method="process_feedback" type="command"}
# [@METHOD]{method="apply_feedback" type="command"}
# [@METHOD]{method="measure_feedback_impact" type="command"}
# [@METHOD]{method="detect_feedback_pattern" type="command"}
# [@METHOD]{method="rank_feedback" type="command"}
# [@METHOD]{method="link_feedback_to_fix" type="command"}
# [@METHOD]{method="link_feedback_to_learning" type="command"}
# [@METHOD]{method="feedback_cycle" type="command"}
# [@METHOD]{method="feedback_report" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class FeedbackLoopEngine:
    """Authority for collecting and processing feedback loops."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
            },
            "catalog": [],
            "results": [],
            "feedback": [],
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "collect_feedback":
            return self.CollectFeedback(params)
        elif command == "process_feedback":
            return self.ProcessFeedback(params)
        elif command == "apply_feedback":
            return self.ApplyFeedback(params)
        elif command == "measure_feedback_impact":
            return self.MeasureFeedbackImpact(params)
        elif command == "detect_feedback_pattern":
            return self.DetectFeedbackPattern(params)
        elif command == "rank_feedback":
            return self.RankFeedback(params)
        elif command == "link_feedback_to_fix":
            return self.LinkFeedbackToFix(params)
        elif command == "link_feedback_to_learning":
            return self.LinkFeedbackToLearning(params)
        elif command == "feedback_cycle":
            return self.FeedbackCycle(params)
        elif command == "feedback_report":
            return self.FeedbackReport(params)
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

    def CollectFeedback(self, params):
        source = self._p(params, "source")
        message = self._p(params, "message")
        feedback_type = self._p(params, "feedback_type", "general")
        if source is None or message is None:
            return (0, None, ("MISSING_PARAM",
                              "source and message required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO observations (observation_type, subject, evidence, "
                "confidence, created) VALUES (?, ?, ?, ?, ?)",
                ("feedback:" + feedback_type, source, message, 50.0, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        entry = {"observation_id": cur.lastrowid, "source": source,
                 "message": message, "type": feedback_type}
        self.state["feedback"].append(entry)
        return (1, entry, None)

    def ProcessFeedback(self, params):
        feedback_id = self._p(params, "feedback_id")
        action = self._p(params, "action", "acknowledged")
        if feedback_id is None:
            return (0, None, ("MISSING_PARAM", "feedback_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("UPDATE observations SET confidence=70.0 WHERE observation_id=?", (feedback_id,))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"feedback_id": feedback_id, "action": action,
                    "processed": True}, None)

    def ApplyFeedback(self, params):
        feedback_id = self._p(params, "feedback_id")
        target_method = self._p(params, "target_method")
        if feedback_id is None or target_method is None:
            return (0, None, ("MISSING_PARAM",
                              "feedback_id and target_method required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO edges (src_type, src_id, dst_type, dst_id, "
                "edge_type, evidence, confidence, created) "
                "VALUES ('observation', ?, 'method', ?, 'feedback_applied', 'feedback_loop', 80.0, ?)",
                (feedback_id, target_method, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"edge_id": cur.lastrowid,
                    "feedback_id": feedback_id,
                    "target_method": target_method}, None)

    def MeasureFeedbackImpact(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM observations WHERE observation_type LIKE 'feedback:%'")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM edges WHERE edge_type='feedback_applied'")
        applied = cur.fetchone()[0]
        impact = (applied / total * 100) if total > 0 else 0
        return (1, {"total_feedback": total, "applied": applied,
                    "impact_pct": round(impact, 1)}, None)

    def DetectFeedbackPattern(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT subject, COUNT(*) AS freq FROM observations "
            "WHERE observation_type LIKE 'feedback:%' "
            "GROUP BY subject HAVING freq > 1 ORDER BY freq DESC"
        )
        patterns = [{"source": r[0], "frequency": r[1]} for r in cur.fetchall()]
        return (1, {"patterns": patterns[:50], "count": len(patterns)}, None)

    def RankFeedback(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT observation_id, subject, evidence, confidence, created "
            "FROM observations WHERE observation_type LIKE 'feedback:%' "
            "ORDER BY confidence DESC, created DESC LIMIT 50"
        )
        ranked = [{"observation_id": r[0], "source": r[1], "message": r[2],
                   "confidence": r[3], "created": r[4]}
                  for r in cur.fetchall()]
        return (1, {"ranked": ranked, "count": len(ranked)}, None)

    def LinkFeedbackToFix(self, params):
        feedback_id = self._p(params, "feedback_id")
        attempt_id = self._p(params, "attempt_id")
        if feedback_id is None or attempt_id is None:
            return (0, None, ("MISSING_PARAM",
                              "feedback_id and attempt_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO edges (src_type, src_id, dst_type, dst_id, "
                "edge_type, evidence, confidence, created) "
                "VALUES ('observation', ?, 'attempt', ?, 'feedback_to_fix', 'feedback_loop', 85.0, ?)",
                (feedback_id, attempt_id, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"edge_id": cur.lastrowid}, None)

    def LinkFeedbackToLearning(self, params):
        feedback_id = self._p(params, "feedback_id")
        lesson = self._p(params, "lesson", "")
        if feedback_id is None:
            return (0, None, ("MISSING_PARAM", "feedback_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO observations (observation_type, subject, evidence, "
                "confidence, created) VALUES ('feedback_lesson', ?, ?, ?, ?)",
                (str(feedback_id), lesson, 85.0, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"observation_id": cur.lastrowid,
                    "linked_feedback": feedback_id}, None)

    def FeedbackCycle(self, params):
        results = {}
        res1 = self.CollectFeedback(params)
        results["collect"] = res1[0] == 1
        if res1[0] == 1:
            res2 = self.ProcessFeedback({"feedback_id": res1[1]["observation_id"]})
            results["process"] = res2[0] == 1
        res3 = self.MeasureFeedbackImpact(params)
        results["measure"] = res3[0] == 1
        results["cycle_completed"] = self.Now()[1]
        return (1, results, None)

    def FeedbackReport(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM observations WHERE observation_type LIKE 'feedback:%'")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM edges WHERE edge_type='feedback_applied'")
        applied = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM observations WHERE observation_type='feedback_lesson'")
        lessons = cur.fetchone()[0]
        return (1, {"total_feedback": total, "applied": applied,
                    "lessons_learned": lessons,
                    "generated": self.Now()[1]}, None)
