#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/lifecycle_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 29: Lifecycle Engine -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="lifecycle_engine.py" domain="twin_lifecycle" authority="LifecycleEngine"}
# [@SUMMARY]{summary="Lifecycle authority: track file lifecycle, track class lifecycle, track method lifecycle, track fix lifecycle, track knowledge lifecycle, track experiment lifecycle, detect lifecycle phase, predict lifecycle end, record lifecycle event, lifecycle report."}
# [@CLASS]{class="LifecycleEngine" domain="lifecycle" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="file_lifecycle" type="command"}
# [@METHOD]{method="class_lifecycle" type="command"}
# [@METHOD]{method="method_lifecycle" type="command"}
# [@METHOD]{method="fix_lifecycle" type="command"}
# [@METHOD]{method="knowledge_lifecycle" type="command"}
# [@METHOD]{method="experiment_lifecycle" type="command"}
# [@METHOD]{method="detect_phase" type="command"}
# [@METHOD]{method="predict_end" type="command"}
# [@METHOD]{method="record_event" type="command"}
# [@METHOD]{method="lifecycle_report" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class LifecycleEngine:
    """Authority for tracking lifecycle phases of project entities."""

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
        if command == "file_lifecycle":
            return self.FileLifecycle(params)
        elif command == "class_lifecycle":
            return self.ClassLifecycle(params)
        elif command == "method_lifecycle":
            return self.MethodLifecycle(params)
        elif command == "fix_lifecycle":
            return self.FixLifecycle(params)
        elif command == "knowledge_lifecycle":
            return self.KnowledgeLifecycle(params)
        elif command == "experiment_lifecycle":
            return self.ExperimentLifecycle(params)
        elif command == "detect_phase":
            return self.DetectPhase(params)
        elif command == "predict_end":
            return self.PredictEnd(params)
        elif command == "record_event":
            return self.RecordEvent(params)
        elif command == "lifecycle_report":
            return self.LifecycleReport(params)
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

    def FileLifecycle(self, params):
        file_id = self._p(params, "file_id")
        if file_id is None:
            return (0, None, ("MISSING_PARAM", "file_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT file_name, created, modified, status FROM files WHERE file_id=?", (file_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("FILE_NOT_FOUND", str(file_id), 0))
        cur.execute("SELECT COUNT(*) FROM classes WHERE file_id=?", (file_id,))
        classes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE file_id=?", (file_id,))
        methods = cur.fetchone()[0]
        phase = "active" if row[3] == "active" else "inactive"
        return (1, {"file_id": file_id, "file_name": row[0],
                    "created": row[1], "modified": row[2],
                    "status": row[3], "phase": phase,
                    "classes": classes, "methods": methods}, None)

    def ClassLifecycle(self, params):
        class_id = self._p(params, "class_id")
        if class_id is None:
            return (0, None, ("MISSING_PARAM", "class_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT class_name, is_vbstyle, has_run_method, has_tuple3, method_count FROM classes WHERE class_id=?", (class_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("CLASS_NOT_FOUND", str(class_id), 0))
        phase = "complete" if row[1] and row[2] and row[3] else "incomplete"
        return (1, {"class_id": class_id, "class_name": row[0],
                    "vbstyle": row[1], "has_run": row[2],
                    "has_tuple3": row[3], "method_count": row[4],
                    "phase": phase}, None)

    def MethodLifecycle(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_name, returns_tuple3, has_print, has_decorator, has_self_underscore, cyclomatic_complexity FROM methods WHERE method_id=?", (method_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
        phase = "compliant" if row[1] and not row[2] and not row[3] and not row[4] else "needs_fix"
        return (1, {"method_id": method_id, "method_name": row[0],
                    "tuple3": row[1], "prints": row[2],
                    "decorators": row[3], "underscores": row[4],
                    "complexity": row[5], "phase": phase}, None)

    def FixLifecycle(self, params):
        attempt_id = self._p(params, "attempt_id")
        if attempt_id is None:
            return (0, None, ("MISSING_PARAM", "attempt_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT action, compile_result, test_result, rollback, created FROM attempts WHERE attempt_id=?", (attempt_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("ATTEMPT_NOT_FOUND", str(attempt_id), 0))
        if row[3]:
            phase = "rolled_back"
        elif row[1] and row[2]:
            phase = "succeeded"
        elif row[1] and not row[2]:
            phase = "compiled_not_tested"
        else:
            phase = "failed"
        return (1, {"attempt_id": attempt_id, "action": row[0],
                    "compile": row[1], "test": row[2],
                    "rollback": row[3], "created": row[4],
                    "phase": phase}, None)

    def KnowledgeLifecycle(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        if knowledge_id is None:
            return (0, None, ("MISSING_PARAM", "knowledge_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT problem, answer, confidence, fix_result FROM knowledge WHERE knowledge_id=?", (knowledge_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("KNOWLEDGE_NOT_FOUND", str(knowledge_id), 0))
        if row[3] == "success":
            phase = "verified"
        elif row[1] and row[2] and row[2] >= 80:
            phase = "high_confidence"
        elif row[1]:
            phase = "has_fix"
        else:
            phase = "unresolved"
        return (1, {"knowledge_id": knowledge_id, "problem": row[0],
                    "has_answer": bool(row[1]), "confidence": row[2],
                    "fix_result": row[3], "phase": phase}, None)

    def ExperimentLifecycle(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM attempts WHERE action LIKE 'experiment:%'")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attempts WHERE action LIKE 'experiment:%' AND compile_result=1 AND test_result=1")
        succeeded = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attempts WHERE action LIKE 'experiment:%' AND rollback=1")
        rolled_back = cur.fetchone()[0]
        return (1, {"total_experiments": total, "succeeded": succeeded,
                    "rolled_back": rolled_back,
                    "phase": "active" if total > 0 else "idle"}, None)

    def DetectPhase(self, params):
        entity_type = self._p(params, "entity_type")
        entity_id = self._p(params, "entity_id")
        if entity_type is None or entity_id is None:
            return (0, None, ("MISSING_PARAM",
                              "entity_type and entity_id required", 0))
        if entity_type == "file":
            return self.FileLifecycle(params)
        elif entity_type == "class":
            return self.ClassLifecycle(params)
        elif entity_type == "method":
            return self.MethodLifecycle(params)
        elif entity_type == "fix":
            return self.FixLifecycle(params)
        elif entity_type == "knowledge":
            return self.KnowledgeLifecycle(params)
        return (0, None, ("UNKNOWN_TYPE", str(entity_type), 0))

    def PredictEnd(self, params):
        entity_type = self._p(params, "entity_type")
        entity_id = self._p(params, "entity_id")
        if entity_type is None or entity_id is None:
            return (0, None, ("MISSING_PARAM",
                              "entity_type and entity_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM observations WHERE subject LIKE ?",
            ("%" + str(entity_id) + "%",),
        )
        activity = cur.fetchone()[0]
        if activity > 10:
            prediction = "stable"
        elif activity > 3:
            prediction = "maturing"
        else:
            prediction = "early"
        return (1, {"entity_type": entity_type, "entity_id": entity_id,
                    "activity_count": activity,
                    "predicted_phase": prediction}, None)

    def RecordEvent(self, params):
        entity_type = self._p(params, "entity_type")
        entity_id = self._p(params, "entity_id")
        event = self._p(params, "event")
        if entity_type is None or entity_id is None or event is None:
            return (0, None, ("MISSING_PARAM",
                              "entity_type, entity_id, event required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO observations (observation_type, subject, evidence, "
                "confidence, created) VALUES (?, ?, ?, ?, ?)",
                ("lifecycle_event:" + entity_type,
                 str(entity_id), event, 50.0, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"observation_id": cur.lastrowid,
                    "event": event}, None)

    def LifecycleReport(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM files WHERE status='active'")
        active_files = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM classes WHERE is_vbstyle=1 AND has_run_method=1")
        complete_classes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE returns_tuple3=1 AND has_print=0 AND has_decorator=0 AND has_self_underscore=0")
        compliant_methods = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attempts WHERE compile_result=1 AND test_result=1")
        successful_fixes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE confidence >= 80")
        high_conf_knowledge = cur.fetchone()[0]
        return (1, {"active_files": active_files,
                    "complete_classes": complete_classes,
                    "compliant_methods": compliant_methods,
                    "successful_fixes": successful_fixes,
                    "high_confidence_knowledge": high_conf_knowledge,
                    "generated": self.Now()[1]}, None)
