#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/traceability_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 34: Traceability Engine -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="traceability_engine.py" domain="twin_traceability" authority="TraceabilityEngine"}
# [@SUMMARY]{summary="Traceability authority: trace file to class, trace class to method, trace method to fix, trace fix to knowledge, trace knowledge to observation, trace observation to learning, trace error to fix, trace change to impact, trace requirement to implementation, traceability report."}
# [@CLASS]{class="TraceabilityEngine" domain="traceability" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="trace_file_to_class" type="command"}
# [@METHOD]{method="trace_class_to_method" type="command"}
# [@METHOD]{method="trace_method_to_fix" type="command"}
# [@METHOD]{method="trace_fix_to_knowledge" type="command"}
# [@METHOD]{method="trace_knowledge_to_observation" type="command"}
# [@METHOD]{method="trace_observation_to_learning" type="command"}
# [@METHOD]{method="trace_error_to_fix" type="command"}
# [@METHOD]{method="trace_change_to_impact" type="command"}
# [@METHOD]{method="trace_requirement_to_impl" type="command"}
# [@METHOD]{method="traceability_report" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class TraceabilityEngine:
    """Authority for tracing relationships across the project."""

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
        if command == "trace_file_to_class":
            return self.TraceFileToClass(params)
        elif command == "trace_class_to_method":
            return self.TraceClassToMethod(params)
        elif command == "trace_method_to_fix":
            return self.TraceMethodToFix(params)
        elif command == "trace_fix_to_knowledge":
            return self.TraceFixToKnowledge(params)
        elif command == "trace_knowledge_to_observation":
            return self.TraceKnowledgeToObservation(params)
        elif command == "trace_observation_to_learning":
            return self.TraceObservationToLearning(params)
        elif command == "trace_error_to_fix":
            return self.TraceErrorToFix(params)
        elif command == "trace_change_to_impact":
            return self.TraceChangeToImpact(params)
        elif command == "trace_requirement_to_impl":
            return self.TraceRequirementToImpl(params)
        elif command == "traceability_report":
            return self.TraceabilityReport(params)
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

    def TraceFileToClass(self, params):
        file_id = self._p(params, "file_id")
        if file_id is None:
            return (0, None, ("MISSING_PARAM", "file_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT class_id, class_name, method_count FROM classes WHERE file_id=?", (file_id,))
        classes = [{"class_id": r[0], "class_name": r[1], "method_count": r[2]} for r in cur.fetchall()]
        return (1, {"file_id": file_id, "classes": classes,
                    "count": len(classes)}, None)

    def TraceClassToMethod(self, params):
        class_id = self._p(params, "class_id")
        if class_id is None:
            return (0, None, ("MISSING_PARAM", "class_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, returns_tuple3 FROM methods WHERE class_id=?", (class_id,))
        methods = [{"method_id": r[0], "method_name": r[1], "tuple3": r[2]} for r in cur.fetchall()]
        return (1, {"class_id": class_id, "methods": methods,
                    "count": len(methods)}, None)

    def TraceMethodToFix(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT attempt_id, action, compile_result, test_result, rollback FROM attempts WHERE method_id=?", (method_id,))
        fixes = [{"attempt_id": r[0], "action": r[1], "compile": r[2], "test": r[3], "rollback": r[4]} for r in cur.fetchall()]
        return (1, {"method_id": method_id, "fixes": fixes,
                    "count": len(fixes)}, None)

    def TraceFixToKnowledge(self, params):
        attempt_id = self._p(params, "attempt_id")
        if attempt_id is None:
            return (0, None, ("MISSING_PARAM", "attempt_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT knowledge_id FROM attempts WHERE attempt_id=?", (attempt_id,))
        row = cur.fetchone()
        if row is None or row[0] is None:
            return (1, {"attempt_id": attempt_id, "knowledge_id": None}, None)
        knowledge_id = row[0]
        cur.execute("SELECT problem, answer, confidence FROM knowledge WHERE knowledge_id=?", (knowledge_id,))
        krow = cur.fetchone()
        if krow is None:
            return (1, {"attempt_id": attempt_id, "knowledge_id": knowledge_id}, None)
        return (1, {"attempt_id": attempt_id, "knowledge_id": knowledge_id,
                    "problem": krow[0], "answer": krow[1], "confidence": krow[2]}, None)

    def TraceKnowledgeToObservation(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        if knowledge_id is None:
            return (0, None, ("MISSING_PARAM", "knowledge_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT observation_id, observation_type, evidence FROM observations WHERE subject=?", (str(knowledge_id),))
        observations = [{"observation_id": r[0], "type": r[1], "evidence": r[2]} for r in cur.fetchall()]
        return (1, {"knowledge_id": knowledge_id, "observations": observations,
                    "count": len(observations)}, None)

    def TraceObservationToLearning(self, params):
        observation_id = self._p(params, "observation_id")
        if observation_id is None:
            return (0, None, ("MISSING_PARAM", "observation_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT observation_type, subject, evidence, confidence FROM observations WHERE observation_id=?", (observation_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("OBSERVATION_NOT_FOUND", str(observation_id), 0))
        is_learning = "lesson" in row[0] or "learning" in row[0]
        return (1, {"observation_id": observation_id, "type": row[0],
                    "subject": row[1], "evidence": row[2],
                    "confidence": row[3], "is_learning": is_learning}, None)

    def TraceErrorToFix(self, params):
        error_text = self._p(params, "error_text", "")
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT knowledge_id, problem, answer, fix_result FROM knowledge WHERE error_text LIKE ? OR problem LIKE ?", ("%" + error_text + "%", "%" + error_text + "%"))
        fixes = [{"knowledge_id": r[0], "problem": r[1], "answer": r[2], "fix_result": r[3]} for r in cur.fetchall()]
        return (1, {"error_text": error_text, "fixes": fixes,
                    "count": len(fixes)}, None)

    def TraceChangeToImpact(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        visited = set()
        queue = [method_id]
        impacted = []
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            impacted.append(current)
            cur.execute("SELECT src_id FROM edges WHERE dst_type='method' AND dst_id=? AND edge_type='calls'", (current,))
            for r in cur.fetchall():
                if r[0] not in visited:
                    queue.append(r[0])
        return (1, {"method_id": method_id, "impacted": impacted,
                    "blast_radius": len(impacted)}, None)

    def TraceRequirementToImpl(self, params):
        requirement = self._p(params, "requirement", "")
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name FROM methods WHERE method_name LIKE ?", ("%" + requirement + "%",))
        methods = [{"method_id": r[0], "method_name": r[1]} for r in cur.fetchall()]
        cur.execute("SELECT class_id, class_name FROM classes WHERE class_name LIKE ?", ("%" + requirement + "%",))
        classes = [{"class_id": r[0], "class_name": r[1]} for r in cur.fetchall()]
        return (1, {"requirement": requirement, "methods": methods,
                    "classes": classes}, None)

    def TraceabilityReport(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM files")
        files = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM classes")
        classes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        methods = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attempts")
        attempts = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM knowledge")
        knowledge = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM observations")
        observations = cur.fetchone()[0]
        return (1, {"files": files, "classes": classes, "methods": methods,
                    "attempts": attempts, "knowledge": knowledge,
                    "observations": observations,
                    "trace_chain": "files->classes->methods->attempts->knowledge->observations",
                    "generated": self.Now()[1]}, None)
