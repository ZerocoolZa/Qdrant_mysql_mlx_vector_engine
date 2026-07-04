#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/knowledge_storage_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 14: Knowledge Storage -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="knowledge_storage_engine.py" domain="twin_knowledge_storage" authority="KnowledgeStorageEngine"}
# [@SUMMARY]{summary="Knowledge storage authority: store patch, store explanation, store before/after, store confidence, store evidence, store learning, store graph changes, store resolution time, store tags, update search index."}
# [@CLASS]{class="KnowledgeStorageEngine" domain="knowledge_storage" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="store_patch" type="command"}
# [@METHOD]{method="store_explanation" type="command"}
# [@METHOD]{method="store_before_after" type="command"}
# [@METHOD]{method="store_confidence" type="command"}
# [@METHOD]{method="store_evidence" type="command"}
# [@METHOD]{method="store_learning" type="command"}
# [@METHOD]{method="store_graph_changes" type="command"}
# [@METHOD]{method="store_error" type="command"}
# [@METHOD]{method="store_fix" type="command"}
# [@METHOD]{method="update_search_index" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"
FTS_SCHEMA = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5("
    "problem, question, answer, error_type, content='knowledge', "
    "content_rowid='knowledge_id')"
)


class KnowledgeStorageEngine:
    """Authority for storing knowledge metadata and updates."""

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
        if command == "store_patch":
            return self.StorePatch(params)
        elif command == "store_explanation":
            return self.StoreExplanation(params)
        elif command == "store_before_after":
            return self.StoreBeforeAfter(params)
        elif command == "store_confidence":
            return self.StoreConfidence(params)
        elif command == "store_evidence":
            return self.StoreEvidence(params)
        elif command == "store_learning":
            return self.StoreLearning(params)
        elif command == "store_graph_changes":
            return self.StoreGraphChanges(params)
        elif command == "store_error":
            return self.StoreError(params)
        elif command == "store_fix":
            return self.StoreFix(params)
        elif command == "update_search_index":
            return self.UpdateSearchIndex(params)
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
            cur = self.state["db_conn"].cursor()
            cur.execute(FTS_SCHEMA)
            self.state["db_conn"].commit()
        return (1, self.state["db_conn"], None)

    def Now(self):
        return (1, datetime.now(timezone.utc).isoformat(), None)

    def StorePatch(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        method_id = self._p(params, "method_id")
        before_code = self._p(params, "before_code")
        after_code = self._p(params, "after_code")
        if knowledge_id is None or method_id is None:
            return (0, None, ("MISSING_PARAM",
                              "knowledge_id and method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO attempts (method_id, action, before_code, after_code, "
                "knowledge_id, created) VALUES (?,?,?,?,?,?)",
                (method_id, "patch", before_code, after_code,
                 knowledge_id, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"attempt_id": cur.lastrowid}, None)

    def StoreExplanation(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        explanation = self._p(params, "explanation")
        if knowledge_id is None or explanation is None:
            return (0, None, ("MISSING_PARAM",
                              "knowledge_id and explanation required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("UPDATE knowledge SET evidence=? WHERE knowledge_id=?",
                        (explanation, knowledge_id))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "updated": True}, None)

    def StoreBeforeAfter(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        method_id = self._p(params, "method_id")
        before_code = self._p(params, "before_code")
        after_code = self._p(params, "after_code")
        if knowledge_id is None:
            return (0, None, ("MISSING_PARAM", "knowledge_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO attempts (method_id, action, before_code, after_code, "
                "knowledge_id, created) VALUES (?,?,?,?,?,?)",
                (method_id, "before_after", before_code, after_code,
                 knowledge_id, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"attempt_id": cur.lastrowid}, None)

    def StoreConfidence(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        confidence = self._p(params, "confidence")
        if knowledge_id is None or confidence is None:
            return (0, None, ("MISSING_PARAM",
                              "knowledge_id and confidence required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("UPDATE knowledge SET confidence=? WHERE knowledge_id=?",
                        (confidence, knowledge_id))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "confidence": confidence}, None)

    def StoreEvidence(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        evidence = self._p(params, "evidence")
        if knowledge_id is None or evidence is None:
            return (0, None, ("MISSING_PARAM",
                              "knowledge_id and evidence required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("UPDATE knowledge SET evidence=? WHERE knowledge_id=?",
                        (evidence, knowledge_id))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "updated": True}, None)

    def StoreLearning(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        learning = self._p(params, "learning")
        if knowledge_id is None or learning is None:
            return (0, None, ("MISSING_PARAM",
                              "knowledge_id and learning required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO observations (observation_type, subject, evidence, "
                "created) VALUES ('learning', ?, ?, ?)",
                (str(knowledge_id), learning, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"observation_id": cur.lastrowid}, None)

    def StoreGraphChanges(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        graph_changes = self._p(params, "graph_changes")
        if knowledge_id is None or graph_changes is None:
            return (0, None, ("MISSING_PARAM",
                              "knowledge_id and graph_changes required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("UPDATE knowledge SET graph_changes=? WHERE knowledge_id=?",
                        (json.dumps(graph_changes) if isinstance(graph_changes, dict)
                         else graph_changes, knowledge_id))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "updated": True}, None)

    def StoreError(self, params):
        method_id = self._p(params, "method_id")
        error_type = self._p(params, "error_type")
        error_message = self._p(params, "error_message")
        stack_trace = self._p(params, "stack_trace", "")
        if method_id is None or error_type is None:
            return (0, None, ("MISSING_PARAM",
                              "method_id and error_type required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO knowledge (method_id, problem, error_type, "
                "evidence, confidence, created) VALUES (?,?,?,?,?,?)",
                (method_id, error_message, error_type, stack_trace,
                 0.0, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        kid = cur.lastrowid
        self.state["catalog"].append({"action": "store_error",
                                       "knowledge_id": kid,
                                       "time": self.Now()[1]})
        return (1, {"knowledge_id": kid, "method_id": method_id,
                    "error_type": error_type}, None)

    def StoreFix(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        method_id = self._p(params, "method_id")
        fix_code = self._p(params, "fix_code")
        fix_explanation = self._p(params, "fix_explanation", "")
        confidence = self._p(params, "confidence", 50.0)
        if knowledge_id is None or method_id is None or fix_code is None:
            return (0, None, ("MISSING_PARAM",
                              "knowledge_id, method_id and fix_code required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE knowledge SET answer=?, confidence=?, "
                "evidence=? WHERE knowledge_id=?",
                (fix_code, confidence, fix_explanation, knowledge_id),
            )
            cur.execute(
                "INSERT INTO attempts (method_id, action, after_code, "
                "knowledge_id, created) VALUES (?,?,?,?,?)",
                (method_id, "fix_applied", fix_code, knowledge_id,
                 self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id,
                    "attempt_id": cur.lastrowid,
                    "confidence": confidence}, None)

    def UpdateSearchIndex(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM knowledge_fts")
            cur.execute(
                "INSERT INTO knowledge_fts (rowid, problem, question, answer, "
                "error_type) SELECT knowledge_id, problem, "
                "COALESCE(question, ''), COALESCE(answer, ''), "
                "COALESCE(error_type, '') FROM knowledge"
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("FTS_UPDATE_FAILED", str(exc), 0))
        return (1, {"indexed": cur.rowcount}, None)
