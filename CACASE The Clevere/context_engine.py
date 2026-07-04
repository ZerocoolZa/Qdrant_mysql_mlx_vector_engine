#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/context_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 42: Context Engine -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="context_engine.py" domain="twin_context" authority="ContextEngine"}
# [@SUMMARY]{summary="Context authority: gather file context, gather class context, gather method context, gather error context, gather fix context, gather knowledge context, gather graph context, merge context, clear context, context report."}
# [@CLASS]{class="ContextEngine" domain="context" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="gather_file_context" type="command"}
# [@METHOD]{method="gather_class_context" type="command"}
# [@METHOD]{method="gather_method_context" type="command"}
# [@METHOD]{method="gather_error_context" type="command"}
# [@METHOD]{method="gather_fix_context" type="command"}
# [@METHOD]{method="gather_knowledge_context" type="command"}
# [@METHOD]{method="gather_graph_context" type="command"}
# [@METHOD]{method="merge_context" type="command"}
# [@METHOD]{method="clear_context" type="command"}
# [@METHOD]{method="context_report" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class ContextEngine:
    """Authority for gathering and managing context."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
            },
            "catalog": [],
            "results": [],
            "context": {},
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "gather_file_context":
            return self.GatherFileContext(params)
        elif command == "gather_class_context":
            return self.GatherClassContext(params)
        elif command == "gather_method_context":
            return self.GatherMethodContext(params)
        elif command == "gather_error_context":
            return self.GatherErrorContext(params)
        elif command == "gather_fix_context":
            return self.GatherFixContext(params)
        elif command == "gather_knowledge_context":
            return self.GatherKnowledgeContext(params)
        elif command == "gather_graph_context":
            return self.GatherGraphContext(params)
        elif command == "merge_context":
            return self.MergeContext(params)
        elif command == "clear_context":
            return self.ClearContext(params)
        elif command == "context_report":
            return self.ContextReport(params)
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

    def GatherFileContext(self, params):
        file_id = self._p(params, "file_id")
        if file_id is None:
            return (0, None, ("MISSING_PARAM", "file_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT file_name, extension, size, class_count, method_count, status FROM files WHERE file_id=?", (file_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("FILE_NOT_FOUND", str(file_id), 0))
        context = {"file_id": file_id, "file_name": row[0], "extension": row[1],
                   "size": row[2], "class_count": row[3], "method_count": row[4],
                   "status": row[5]}
        self.state["context"]["file"] = context
        return (1, context, None)

    def GatherClassContext(self, params):
        class_id = self._p(params, "class_id")
        if class_id is None:
            return (0, None, ("MISSING_PARAM", "class_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT class_name, parent, method_count, is_vbstyle, has_run_method, has_tuple3 FROM classes WHERE class_id=?", (class_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("CLASS_NOT_FOUND", str(class_id), 0))
        context = {"class_id": class_id, "class_name": row[0], "parent": row[1],
                   "method_count": row[2], "is_vbstyle": row[3],
                   "has_run": row[4], "has_tuple3": row[5]}
        self.state["context"]["class"] = context
        return (1, context, None)

    def GatherMethodContext(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_name, class_id, cyclomatic_complexity, line_count, returns_tuple3, has_print, has_decorator, has_self_underscore FROM methods WHERE method_id=?", (method_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
        context = {"method_id": method_id, "method_name": row[0], "class_id": row[1],
                   "complexity": row[2], "line_count": row[3],
                   "tuple3": row[4], "prints": row[5], "decorators": row[6],
                   "underscores": row[7]}
        self.state["context"]["method"] = context
        return (1, context, None)

    def GatherErrorContext(self, params):
        error_text = self._p(params, "error_text", "")
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT knowledge_id, problem, error_type, confidence FROM knowledge WHERE error_text LIKE ? OR problem LIKE ?", ("%" + error_text + "%", "%" + error_text + "%"))
        errors = [{"knowledge_id": r[0], "problem": r[1], "error_type": r[2], "confidence": r[3]} for r in cur.fetchall()]
        context = {"error_text": error_text, "related_errors": errors[:20]}
        self.state["context"]["error"] = context
        return (1, context, None)

    def GatherFixContext(self, params):
        attempt_id = self._p(params, "attempt_id")
        if attempt_id is None:
            return (0, None, ("MISSING_PARAM", "attempt_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_id, action, compile_result, test_result, rollback, knowledge_id FROM attempts WHERE attempt_id=?", (attempt_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("ATTEMPT_NOT_FOUND", str(attempt_id), 0))
        context = {"attempt_id": attempt_id, "method_id": row[0], "action": row[1],
                   "compile": row[2], "test": row[3], "rollback": row[4],
                   "knowledge_id": row[5]}
        self.state["context"]["fix"] = context
        return (1, context, None)

    def GatherKnowledgeContext(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        if knowledge_id is None:
            return (0, None, ("MISSING_PARAM", "knowledge_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT problem, answer, error_type, confidence, fix_result, root_cause FROM knowledge WHERE knowledge_id=?", (knowledge_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("KNOWLEDGE_NOT_FOUND", str(knowledge_id), 0))
        context = {"knowledge_id": knowledge_id, "problem": row[0], "answer": row[1],
                   "error_type": row[2], "confidence": row[3],
                   "fix_result": row[4], "root_cause": row[5]}
        self.state["context"]["knowledge"] = context
        return (1, context, None)

    def GatherGraphContext(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM edges")
        edges = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT edge_type) FROM edges")
        types = cur.fetchone()[0]
        cur.execute("SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type")
        by_type = {r[0]: r[1] for r in cur.fetchall()}
        context = {"total_edges": edges, "edge_types": types, "by_type": by_type}
        self.state["context"]["graph"] = context
        return (1, context, None)

    def MergeContext(self, params):
        merged = {}
        for key, value in self.state["context"].items():
            merged[key] = value
        merged["merged_at"] = self.Now()[1]
        return (1, {"merged": merged, "keys": list(self.state["context"].keys())}, None)

    def ClearContext(self, params):
        self.state["context"] = {}
        return (1, {"cleared": True}, None)

    def ContextReport(self, params):
        report = {"context_keys": list(self.state["context"].keys()),
                  "context_size": len(self.state["context"]),
                  "generated": self.Now()[1]}
        for key, value in self.state["context"].items():
            report[key] = value
        return (1, report, None)
