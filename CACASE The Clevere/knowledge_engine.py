#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/knowledge_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 3: Error Knowledge Database -- 20 sub-sections, Section 14: Knowledge Storage -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="knowledge_engine.py" domain="twin_knowledge" authority="KnowledgeEngine"}
# [@SUMMARY]{summary="Knowledge authority: error table, fix table, failed attempt, success, stack trace, exception type, file, class, method, line number, variables, inputs, outputs, root cause, human fix, AI fix, confidence, similar errors, resolution time, learn from previous. Also stores patches, explanations, graph changes, before/after, evidence, learning, updates search index."}
# [@CLASS]{class="KnowledgeEngine" domain="knowledge" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="record_error" type="command"}
# [@METHOD]{method="record_fix" type="command"}
# [@METHOD]{method="record_failed_attempt" type="command"}
# [@METHOD]{method="record_success" type="command"}
# [@METHOD]{method="search_similar" type="command"}
# [@METHOD]{method="learn" type="command"}
# [@METHOD]{method="get_best_fix" type="command"}
# [@METHOD]{method="store_patch" type="command"}
# [@METHOD]{method="store_explanation" type="command"}
# [@METHOD]{method="store_graph_changes" type="command"}
# [@METHOD]{method="store_before_after" type="command"}
# [@METHOD]{method="store_confidence" type="command"}
# [@METHOD]{method="store_evidence" type="command"}
# [@METHOD]{method="store_learning" type="command"}
# [@METHOD]{method="update_search_index" type="command"}
# [@METHOD]{method="search_fts" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import json
import os
import sqlite3
import traceback
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"
DEFAULT_CONFIDENCE = 50
CONFIDENCE_INCREMENT = 5
FTS_SCHEMA = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5("
    "problem, question, answer, error_type, content='knowledge', "
    "content_rowid='knowledge_id')"
)


class KnowledgeEngine:
    """Authority for error/fix knowledge storage, retrieval, and learning."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_confidence": DEFAULT_CONFIDENCE,
                "confidence_increment": CONFIDENCE_INCREMENT,
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
        if command == "record_error":
            return self.RecordError(params)
        elif command == "record_fix":
            return self.RecordFix(params)
        elif command == "record_failed_attempt":
            return self.RecordFailedAttempt(params)
        elif command == "record_success":
            return self.RecordSuccess(params)
        elif command == "search_similar":
            return self.SearchSimilar(params)
        elif command == "learn":
            return self.Learn(params)
        elif command == "get_best_fix":
            return self.GetBestFix(params)
        elif command == "store_patch":
            return self.StorePatch(params)
        elif command == "store_explanation":
            return self.StoreExplanation(params)
        elif command == "store_graph_changes":
            return self.StoreGraphChanges(params)
        elif command == "store_before_after":
            return self.StoreBeforeAfter(params)
        elif command == "store_confidence":
            return self.StoreConfidence(params)
        elif command == "store_evidence":
            return self.StoreEvidence(params)
        elif command == "store_learning":
            return self.StoreLearning(params)
        elif command == "update_search_index":
            return self.UpdateSearchIndex(params)
        elif command == "search_fts":
            return self.SearchFts(params)
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

    def RecordError(self, params):
        problem = self._p(params, "problem", "")
        question = self._p(params, "question", "")
        answer = self._p(params, "answer", "")
        error_type = self._p(params, "error_type")
        error_text = self._p(params, "error_text")
        stack_trace = self._p(params, "stack_trace", traceback.format_exc())
        file_id = self._p(params, "file_id")
        class_id = self._p(params, "class_id")
        method_id = self._p(params, "method_id")
        confidence = self._p(params, "confidence",
                             self.state["config"]["default_confidence"])
        tags = self._p(params, "tags", [])
        resolution_time = self._p(params, "resolution_time_ms")
        line_number = self._p(params, "line_number")
        variables = self._p(params, "variables")
        inputs = self._p(params, "inputs")
        outputs = self._p(params, "outputs")
        root_cause = self._p(params, "root_cause")
        if not problem:
            return (0, None, ("MISSING_PARAM", "problem required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO knowledge (problem, question, answer, confidence, "
                "file_id, class_id, method_id, error_type, error_text, "
                "stack_trace, resolution_time_ms, line_number, variables, "
                "inputs, outputs, root_cause, created, tags) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (problem, question, answer, confidence, file_id, class_id,
                 method_id, error_type, error_text, stack_trace, resolution_time,
                 line_number,
                 json.dumps(variables) if variables else None,
                 json.dumps(inputs) if inputs else None,
                 json.dumps(outputs) if outputs else None,
                 root_cause, self.Now()[1], json.dumps(tags)),
            )
            kid = cur.lastrowid
            cur.execute(
                "INSERT INTO knowledge_fts (rowid, problem, question, answer, "
                "error_type) VALUES (?,?,?,?,?)",
                (kid, problem, question, answer, error_type or ""),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        record = {"knowledge_id": kid, "problem": problem, "error_type": error_type}
        self.state["catalog"].append(record)
        return (1, record, None)

    def RecordFix(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        answer = self._p(params, "answer")
        if knowledge_id is None or answer is None:
            return (0, None, ("MISSING_PARAM", "knowledge_id and answer required", 0))
        fix_result = self._p(params, "fix_result", "success")
        is_best = self._p(params, "is_best", 1)
        evidence = self._p(params, "evidence")
        human_fix = self._p(params, "human_fix")
        ai_fix = self._p(params, "ai_fix", answer)
        confidence = self._p(params, "confidence",
                             self.state["config"]["default_confidence"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE knowledge SET answer=?, is_best=?, fix_result=?, "
                "evidence=?, confidence=?, human_fix=?, ai_fix=? "
                "WHERE knowledge_id=?",
                (answer, is_best, fix_result, evidence, confidence,
                 human_fix, ai_fix, knowledge_id),
            )
            cur.execute(
                "UPDATE knowledge_fts SET answer=? WHERE rowid=?",
                (answer, knowledge_id),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "updated": True}, None)

    def RecordFailedAttempt(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        method_id = self._p(params, "method_id")
        before_code = self._p(params, "before_code")
        after_code = self._p(params, "after_code")
        error_text = self._p(params, "error_text")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO attempts (method_id, action, before_code, after_code, "
                "compile_result, test_result, error_text, rollback, knowledge_id, "
                "created) VALUES (?,?,?,?,0,0,?,1,?,?)",
                (method_id, "fix_attempt", before_code, after_code,
                 error_text, knowledge_id, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"attempt_id": cur.lastrowid, "result": "failed"}, None)

    def RecordSuccess(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        method_id = self._p(params, "method_id")
        before_code = self._p(params, "before_code")
        after_code = self._p(params, "after_code")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO attempts (method_id, action, before_code, after_code, "
                "compile_result, test_result, error_text, rollback, knowledge_id, "
                "created) VALUES (?,?,?,?,1,1,'',0,?,?)",
                (method_id, "fix_success", before_code, after_code,
                 knowledge_id, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"attempt_id": cur.lastrowid, "result": "success"}, None)

    def SearchSimilar(self, params):
        problem = self._p(params, "problem", "")
        error_type = self._p(params, "error_type")
        limit = self._p(params, "limit", 10)
        conn = self.Connect()[1]
        cur = conn.cursor()
        query = ("SELECT knowledge_id, problem, answer, confidence, error_type, "
                 "fix_result FROM knowledge WHERE 1=1")
        values = []
        if error_type:
            query += " AND error_type=?"
            values.append(error_type)
        if problem:
            query += " AND problem LIKE ?"
            values.append("%" + problem + "%")
        query += " ORDER BY confidence DESC LIMIT ?"
        values.append(limit)
        cur.execute(query, values)
        results = [{"knowledge_id": r[0], "problem": r[1], "answer": r[2],
                    "confidence": r[3], "error_type": r[4], "fix_result": r[5]}
                   for r in cur.fetchall()]
        return (1, {"results": results, "count": len(results)}, None)

    def Learn(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        success = self._p(params, "success", True)
        if knowledge_id is None:
            return (0, None, ("MISSING_PARAM", "knowledge_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        delta = self.state["config"]["confidence_increment"]
        if not success:
            delta = -delta
        try:
            cur.execute(
                "UPDATE knowledge SET confidence=MAX(0, MIN(100, confidence+?)) "
                "WHERE knowledge_id=?",
                (delta, knowledge_id),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "delta": delta}, None)

    def GetBestFix(self, params):
        problem = self._p(params, "problem", "")
        error_type = self._p(params, "error_type")
        if not problem:
            return (0, None, ("MISSING_PARAM", "problem required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        query = ("SELECT knowledge_id, problem, answer, confidence, fix_result "
                 "FROM knowledge WHERE answer IS NOT NULL AND answer != ''")
        values = []
        if error_type:
            query += " AND error_type=?"
            values.append(error_type)
        query += " AND problem LIKE ?"
        values.append("%" + problem + "%")
        query += " ORDER BY is_best DESC, confidence DESC, fix_result DESC LIMIT 1"
        cur.execute(query, values)
        row = cur.fetchone()
        if row is None:
            return (1, {"found": False}, None)
        return (1, {"found": True, "knowledge_id": row[0], "problem": row[1],
                    "answer": row[2], "confidence": row[3],
                    "fix_result": row[4]}, None)

    def StorePatch(self, params):
        method_id = self._p(params, "method_id")
        before_code = self._p(params, "before_code")
        after_code = self._p(params, "after_code")
        action = self._p(params, "action", "patch")
        knowledge_id = self._p(params, "knowledge_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO attempts (method_id, action, before_code, after_code, "
                "knowledge_id, created) VALUES (?,?,?,?,?,?)",
                (method_id, action, before_code, after_code,
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

    def StoreBeforeAfter(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        before_code = self._p(params, "before_code")
        after_code = self._p(params, "after_code")
        method_id = self._p(params, "method_id")
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
                "method_id, created) VALUES ('learning', ?, ?, ?, ?)",
                (str(knowledge_id), learning, None, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"observation_id": cur.lastrowid}, None)

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

    def SearchFts(self, params):
        query_text = self._p(params, "query")
        limit = self._p(params, "limit", 10)
        if not query_text:
            return (0, None, ("MISSING_PARAM", "query required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT k.knowledge_id, k.problem, k.answer, k.confidence "
                "FROM knowledge_fts f JOIN knowledge k "
                "ON k.knowledge_id=f.rowid "
                "WHERE knowledge_fts MATCH ? ORDER BY k.confidence DESC LIMIT ?",
                (query_text, limit),
            )
            results = [{"knowledge_id": r[0], "problem": r[1], "answer": r[2],
                        "confidence": r[3]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("FTS_FAILED", str(exc), 0))
        return (1, {"results": results, "count": len(results)}, None)
