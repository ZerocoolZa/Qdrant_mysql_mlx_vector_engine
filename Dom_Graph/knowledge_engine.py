#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/knowledge_engine.py"
# date="2026-06-26" author="Devin" session_id="phase3-knowledge"
# context="Project Digital Twin Phase 3 Sections 3, 14 Knowledge Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="knowledge_engine.py" domain="twin_knowledge" authority="KnowledgeEngine"}
# [@SUMMARY]{summary="Knowledge authority that records errors, fixes, searches similar problems, learns from outcomes and provides FTS5-backed Q&A storage."}
# [@CLASS]{class="KnowledgeEngine" domain="knowledge" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="record_error" type="command"}
# [@METHOD]{method="record_fix" type="command"}
# [@METHOD]{method="search_similar" type="command"}
# [@METHOD]{method="learn" type="command"}
# [@METHOD]{method="get_best_fix" type="command"}
# [@METHOD]{method="store_patch" type="command"}
# [@METHOD]{method="store_explanation" type="command"}
# [@METHOD]{method="store_graph_changes" type="command"}
# [@METHOD]{method="search_fts" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<KnowledgeEngine: records errors/fixes, searches similar problems, learns from outcomes, FTS5-backed Q&A storage. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths. Docstring notes 11 missing spec sub-sections but code structure is VBStyle compliant.>][@todos<none>]}
"""
KnowledgeEngine -- authority for the error/fix knowledge database.
Implements Sections 3 and 14 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: record_error, record_fix, search_similar, learn, get_best_fix,
          store_patch, store_explanation, store_graph_changes, search_fts.

# ============================================================
# ERRORS -- Section 3 spec vs. implementation
# Rating: 3/10
# Spec has 20 sub-sections (3.1-3.20). Only 9 commands implemented.
# ============================================================
# MISSING METHODS:
# 3.10 StoreLineNumber   -- parse line number from traceback. NOT a separate command.
#                          (line_number is a param to RecordError, not parsed automatically.)
# 3.11 StoreVariables     -- locals() snapshot as JSON. NOT a separate command.
#                          (variables is a param, not captured automatically.)
# 3.12 StoreInputs        -- function args. NOT a separate command.
#                          (inputs is a param, not captured automatically.)
# 3.13 StoreOutputs       -- return value. NOT a separate command.
#                          (outputs is a param, not captured automatically.)
# 3.14 StoreRootCause     -- analysis of stack trace -> knowledge.problem. NOT a separate command.
#                          (root_cause is a param, not derived automatically.)
# 3.15 StoreHumanFix      -- the human fix text. NOT a separate command.
#                          (human_fix is a param to RecordFix, not standalone.)
# 3.16 StoreAiFix         -- the AI fix text. NOT a separate command.
#                          (ai_fix is a param to RecordFix, not standalone.)
# 3.17 StoreConfidence    -- 0-100 based on similarity to past successes. NOT a separate command.
#                          (confidence is a param, not computed automatically.)
# 3.18 StoreSimilarErrors -- SELECT * FROM knowledge WHERE error_type=? AND problem LIKE ?.
#                          NOT a separate command. (SearchSimilar does this but does not STORE.)
# 3.19 StoreResolutionTime -- time.time() - start_time. NOT a separate command.
#                          (resolution_time_ms is a param, not measured automatically.)
# 3.20 LearnFromPreviousFixes -- query knowledge table BEFORE attempting fix. NOT IMPLEMENTED.
#                          (Learn only updates confidence AFTER, does not query BEFORE.)
#
# PARTIAL:
# 3.1-3.4 Create tables -- tables exist in Config.py but this engine does not create them.
#                          Relies on external schema setup.
# 3.5  StoreStackTrace   -- done inside RecordError via traceback.format_exc() default.
# 3.6  StoreExceptionType -- done inside RecordError via error_type param.
# 3.7-3.9 Store File/Class/Method -- done inside RecordError via file_id/class_id/method_id params.
#
# Section 14 (Knowledge Storage) coverage:
# 14.1 StoreError        -- RecordError covers this.
# 14.2 StoreFix          -- RecordFix covers this.
# 14.3 StorePatch        -- StorePatch covers this.
# 14.4 StoreExplanation  -- StoreExplanation covers this.
# 14.5 StoreGraphChanges -- StoreGraphChanges covers this.
# 14.6 StoreBefore/After -- NOT IMPLEMENTED as separate command.
#                          (snapshots table exists but no command writes to it from here.)
# 14.7 StoreConfidence   -- param only, not computed.
# 14.8 StoreEvidence     -- param only, not captured from compile/test results.
# 14.9 StoreLearning     -- Learn covers this partially.
# 14.10 UpdateSearchIndex -- FTS5 table created on Connect. OK.
# ============================================================
"""
import json
import os
import sqlite3
import sys
import time
import hashlib
import inspect
import traceback
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_CONFIDENCE = 50
CONFIDENCE_INCREMENT = 5
FTS_SCHEMA = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5("
    "problem, question, answer, error_type, content='knowledge', "
    "content_rowid='knowledge_id')"
)


class KnowledgeEngine:
    """Authority for error/fix knowledge storage and retrieval."""

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
        elif command == "search_fts":
            return self.SearchFts(params)
        elif command == "store_line_number":
            return self.StoreLineNumber(params)
        elif command == "store_variables":
            return self.StoreVariables(params)
        elif command == "store_inputs":
            return self.StoreInputs(params)
        elif command == "store_outputs":
            return self.StoreOutputs(params)
        elif command == "store_root_cause":
            return self.StoreRootCause(params)
        elif command == "store_human_fix":
            return self.StoreHumanFix(params)
        elif command == "store_ai_fix":
            return self.StoreAiFix(params)
        elif command == "store_confidence":
            return self.StoreConfidence(params)
        elif command == "store_similar_errors":
            return self.StoreSimilarErrors(params)
        elif command == "store_resolution_time":
            return self.StoreResolutionTime(params)
        elif command == "learn_from_previous_fixes":
            return self.LearnFromPreviousFixes(params)
        elif command == "store_before_after":
            return self.StoreBeforeAfter(params)
        elif command == "store_evidence":
            return self.StoreEvidence(params)
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
        return self.state["db_conn"]

    def Now(self):
        return datetime.now(timezone.utc).isoformat()

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
        conn = self.Connect()
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
                 line_number, json.dumps(variables) if variables else None,
                 json.dumps(inputs) if inputs else None,
                 json.dumps(outputs) if outputs else None,
                 root_cause, self.Now(), json.dumps(tags)),
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
        conn = self.Connect()
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
                "UPDATE knowledge_fts SET answer=? WHERE rowid=?", (answer, knowledge_id)
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "updated": True}, None)

    def SearchSimilar(self, params):
        problem = self._p(params, "problem", "")
        error_type = self._p(params, "error_type")
        limit = self._p(params, "limit", 10)
        conn = self.Connect()
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
        conn = self.Connect()
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
        conn = self.Connect()
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
        record = {"found": True, "knowledge_id": row[0], "problem": row[1],
                  "answer": row[2], "confidence": row[3], "fix_result": row[4]}
        return (1, record, None)

    def StorePatch(self, params):
        method_id = self._p(params, "method_id")
        before_code = self._p(params, "before_code")
        after_code = self._p(params, "after_code")
        action = self._p(params, "action", "patch")
        knowledge_id = self._p(params, "knowledge_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO attempts (method_id, action, before_code, after_code, "
                "knowledge_id, created) VALUES (?,?,?,?,?,?)",
                (method_id, action, before_code, after_code, knowledge_id,
                 self.Now()),
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
        conn = self.Connect()
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
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute("UPDATE knowledge SET graph_changes=? WHERE knowledge_id=?",
                        (json.dumps(graph_changes) if isinstance(graph_changes, dict)
                         else graph_changes, knowledge_id))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "updated": True}, None)

    def SearchFts(self, params):
        query_text = self._p(params, "query")
        limit = self._p(params, "limit", 10)
        if not query_text:
            return (0, None, ("MISSING_PARAM", "query required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT k.knowledge_id, k.problem, k.answer, k.confidence "
                "FROM knowledge_fts f JOIN knowledge k ON k.knowledge_id=f.rowid "
                "WHERE knowledge_fts MATCH ? ORDER BY k.confidence DESC LIMIT ?",
                (query_text, limit),
            )
            results = [{"knowledge_id": r[0], "problem": r[1], "answer": r[2],
                        "confidence": r[3]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("FTS_FAILED", str(exc), 0))
        return (1, {"results": results, "count": len(results)}, None)

    def StoreLineNumber(self, params):
        # 3.10 -- parse traceback to extract line number automatically
        knowledge_id = self._p(params, "knowledge_id")
        stack_trace = self._p(params, "stack_trace")
        exc_info = self._p(params, "exc_info")
        if stack_trace is None and exc_info is not None:
            stack_trace = "".join(traceback.format_exception(*exc_info))
        if stack_trace is None:
            stack_trace = traceback.format_exc()
        line_number = None
        file_name = None
        if exc_info is not None and len(exc_info) > 2 and exc_info[2] is not None:
            try:
                extracted = traceback.extract_tb(exc_info[2])
                if extracted:
                    frame = extracted[-1]
                    line_number = frame.lineno
                    file_name = frame.filename
            except Exception:
                pass
        if line_number is None:
            parsed = self.ParseTracebackLines(stack_trace)
            line_number = parsed.get("line_number")
            file_name = parsed.get("file_name")
        if knowledge_id is None:
            return (1, {"line_number": line_number, "file_name": file_name}, None)
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE knowledge SET line_number=? WHERE knowledge_id=?",
                (line_number, knowledge_id),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "line_number": line_number,
                    "file_name": file_name}, None)

    def ParseTracebackLines(self, stack_trace):
        # helper: parse File "path", line N lines from a traceback string
        result = {"line_number": None, "file_name": None}
        if not stack_trace:
            return result
        lines = stack_trace.splitlines()
        for line in lines:
            if "File \"" in line and ", line " in line:
                try:
                    fstart = line.index("File \"") + 6
                    fend = line.index("\"", fstart)
                    fname = line[fstart:fend]
                    lstart = line.index(", line ") + 7
                    rest = line[lstart:].split(",")
                    lnum = int(rest[0].strip())
                    result["file_name"] = fname
                    result["line_number"] = lnum
                except (ValueError, IndexError):
                    continue
        return result

    def StoreVariables(self, params):
        # 3.11 -- capture locals() as JSON snapshot
        knowledge_id = self._p(params, "knowledge_id")
        variables = self._p(params, "variables")
        frame = self._p(params, "frame")
        if variables is None and frame is not None:
            try:
                variables = dict(frame.f_locals)
            except Exception:
                variables = {}
        if variables is None:
            try:
                caller_frame = inspect.currentframe().f_back
                variables = dict(caller_frame.f_locals) if caller_frame else {}
            except Exception:
                variables = {}
        safe = {}
        for key, value in variables.items():
            if key.startswith("__"):
                continue
            safe[key] = repr(value)
        if knowledge_id is None:
            return (1, {"variables": safe, "count": len(safe)}, None)
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE knowledge SET variables=? WHERE knowledge_id=?",
                (json.dumps(safe), knowledge_id),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "variables": safe,
                    "count": len(safe)}, None)

    def StoreInputs(self, params):
        # 3.12 -- capture function args
        knowledge_id = self._p(params, "knowledge_id")
        inputs = self._p(params, "inputs")
        args = self._p(params, "args")
        kwargs = self._p(params, "kwargs")
        if inputs is None:
            inputs = {}
            if args is not None:
                inputs["args"] = [repr(a) for a in args]
            if kwargs is not None:
                inputs["kwargs"] = {k: repr(v) for k, v in kwargs.items()}
        if knowledge_id is None:
            return (1, {"inputs": inputs}, None)
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE knowledge SET inputs=? WHERE knowledge_id=?",
                (json.dumps(inputs), knowledge_id),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "inputs": inputs}, None)

    def StoreOutputs(self, params):
        # 3.13 -- capture return value
        knowledge_id = self._p(params, "knowledge_id")
        outputs = self._p(params, "outputs")
        return_value = self._p(params, "return_value")
        if outputs is None and return_value is not None:
            outputs = {"return_value": repr(return_value)}
        if outputs is None:
            outputs = {}
        if knowledge_id is None:
            return (1, {"outputs": outputs}, None)
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE knowledge SET outputs=? WHERE knowledge_id=?",
                (json.dumps(outputs), knowledge_id),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "outputs": outputs}, None)

    def StoreRootCause(self, params):
        # 3.14 -- analyze stack trace to derive root cause
        knowledge_id = self._p(params, "knowledge_id")
        stack_trace = self._p(params, "stack_trace", traceback.format_exc())
        root_cause = self._p(params, "root_cause")
        if root_cause is None:
            root_cause = self.DeriveRootCause(stack_trace)
        if knowledge_id is None:
            return (1, {"root_cause": root_cause}, None)
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE knowledge SET root_cause=? WHERE knowledge_id=?",
                (root_cause, knowledge_id),
            )
            cur.execute(
                "UPDATE knowledge SET problem=? WHERE knowledge_id=? "
                "AND (problem IS NULL OR problem='')",
                (root_cause, knowledge_id),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "root_cause": root_cause}, None)

    def DeriveRootCause(self, stack_trace):
        # helper: derive a root cause string from a stack trace
        if not stack_trace:
            return "unknown"
        lines = stack_trace.splitlines()
        error_line = ""
        for line in reversed(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith("File"):
                if not stripped.startswith("Traceback"):
                    if ":" in stripped and not stripped.startswith("During"):
                        error_line = stripped
                        break
        parsed = self.ParseTracebackLines(stack_trace)
        parts = []
        if parsed.get("file_name"):
            parts.append("in " + os.path.basename(parsed["file_name"]))
        if parsed.get("line_number"):
            parts.append("at line " + str(parsed["line_number"]))
        if error_line:
            parts.append("error: " + error_line)
        if not parts:
            return lines[-1].strip() if lines else "unknown"
        return " | ".join(parts)

    def StoreHumanFix(self, params):
        # 3.15 -- standalone command to store a human-authored fix
        knowledge_id = self._p(params, "knowledge_id")
        human_fix = self._p(params, "human_fix")
        if knowledge_id is None or human_fix is None:
            return (0, None, ("MISSING_PARAM",
                              "knowledge_id and human_fix required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE knowledge SET answer=?, is_best=1 "
                "WHERE knowledge_id=? AND (answer IS NULL OR answer='')",
                (human_fix, knowledge_id),
            )
            cur.execute(
                "UPDATE knowledge SET human_fix=? WHERE knowledge_id=?",
                (human_fix, knowledge_id),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "human_fix": human_fix}, None)

    def StoreAiFix(self, params):
        # 3.16 -- standalone command to store an AI-generated fix
        knowledge_id = self._p(params, "knowledge_id")
        ai_fix = self._p(params, "ai_fix")
        if knowledge_id is None or ai_fix is None:
            return (0, None, ("MISSING_PARAM",
                              "knowledge_id and ai_fix required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE knowledge SET answer=? "
                "WHERE knowledge_id=? AND (answer IS NULL OR answer='')",
                (ai_fix, knowledge_id),
            )
            cur.execute(
                "UPDATE knowledge SET ai_fix=? WHERE knowledge_id=?",
                (ai_fix, knowledge_id),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "ai_fix": ai_fix}, None)

    def StoreConfidence(self, params):
        # 3.17 -- compute confidence from similarity to past successes
        knowledge_id = self._p(params, "knowledge_id")
        problem = self._p(params, "problem")
        error_type = self._p(params, "error_type")
        if knowledge_id is None:
            return (0, None, ("MISSING_PARAM", "knowledge_id required", 0))
        confidence = self.ComputeConfidence(problem, error_type)
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE knowledge SET confidence=? WHERE knowledge_id=?",
                (confidence, knowledge_id),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "confidence": confidence}, None)

    def ComputeConfidence(self, problem, error_type):
        # helper: compute 0-100 confidence from similarity to past successes
        if not problem and not error_type:
            return self.state["config"]["default_confidence"]
        conn = self.Connect()
        cur = conn.cursor()
        query = ("SELECT confidence, fix_result FROM knowledge WHERE "
                 "fix_result='success'")
        values = []
        if error_type:
            query += " AND error_type=?"
            values.append(error_type)
        if problem:
            query += " AND problem LIKE ?"
            values.append("%" + problem + "%")
        query += " ORDER BY confidence DESC LIMIT 20"
        try:
            cur.execute(query, values)
            rows = cur.fetchall()
        except sqlite3.Error:
            return self.state["config"]["default_confidence"]
        if not rows:
            return self.state["config"]["default_confidence"]
        total = sum(r[0] for r in rows)
        avg = total / len(rows)
        successes = sum(1 for r in rows if r[1] == "success")
        ratio = successes / len(rows) if rows else 0.5
        confidence = int(avg * ratio)
        if confidence < 1:
            confidence = 1
        if confidence > 100:
            confidence = 100
        return confidence

    def StoreSimilarErrors(self, params):
        # 3.18 -- query AND store similar errors
        knowledge_id = self._p(params, "knowledge_id")
        problem = self._p(params, "problem", "")
        error_type = self._p(params, "error_type")
        limit = self._p(params, "limit", 10)
        if not problem and not error_type:
            return (0, None, ("MISSING_PARAM",
                              "problem or error_type required", 0))
        conn = self.Connect()
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
        similar = [{"knowledge_id": r[0], "problem": r[1], "answer": r[2],
                    "confidence": r[3], "error_type": r[4], "fix_result": r[5]}
                   for r in cur.fetchall()]
        if knowledge_id is not None and similar:
            similar_ids = [s["knowledge_id"] for s in similar]
            try:
                cur.execute(
                    "UPDATE knowledge SET similar_errors=? WHERE knowledge_id=?",
                    (json.dumps(similar_ids), knowledge_id),
                )
                conn.commit()
            except sqlite3.Error as exc:
                return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "similar": similar,
                    "count": len(similar)}, None)

    def StoreResolutionTime(self, params):
        # 3.19 -- measure time automatically
        knowledge_id = self._p(params, "knowledge_id")
        start_time = self._p(params, "start_time")
        end_time = self._p(params, "end_time")
        resolution_time_ms = self._p(params, "resolution_time_ms")
        if resolution_time_ms is None:
            if start_time is None:
                start_time = self.state.get("resolution_start")
            if start_time is not None:
                if end_time is None:
                    end_time = time.time()
                resolution_time_ms = int((end_time - start_time) * 1000)
            else:
                resolution_time_ms = 0
        if knowledge_id is None:
            return (1, {"resolution_time_ms": resolution_time_ms}, None)
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE knowledge SET resolution_time_ms=? WHERE knowledge_id=?",
                (resolution_time_ms, knowledge_id),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id,
                    "resolution_time_ms": resolution_time_ms}, None)

    def LearnFromPreviousFixes(self, params):
        # 3.20 -- query knowledge BEFORE attempting fix
        problem = self._p(params, "problem", "")
        error_type = self._p(params, "error_type")
        if not problem and not error_type:
            return (0, None, ("MISSING_PARAM",
                              "problem or error_type required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        query = ("SELECT knowledge_id, problem, answer, confidence, fix_result, "
                 "human_fix, ai_fix FROM knowledge WHERE answer IS NOT NULL "
                 "AND answer != ''")
        values = []
        if error_type:
            query += " AND error_type=?"
            values.append(error_type)
        if problem:
            query += " AND problem LIKE ?"
            values.append("%" + problem + "%")
        query += " ORDER BY is_best DESC, confidence DESC, fix_result DESC LIMIT 20"
        cur.execute(query, values)
        fixes = []
        for r in cur.fetchall():
            fixes.append({
                "knowledge_id": r[0], "problem": r[1], "answer": r[2],
                "confidence": r[3], "fix_result": r[4],
                "human_fix": r[5], "ai_fix": r[6],
            })
        best = fixes[0] if fixes else None
        return (1, {"previous_fixes": fixes, "count": len(fixes),
                    "best_fix": best}, None)

    def StoreBeforeAfter(self, params):
        # 14.6 -- write before/after content to snapshots table
        file_id = self._p(params, "file_id")
        class_id = self._p(params, "class_id")
        method_id = self._p(params, "method_id")
        before_content = self._p(params, "before_content")
        after_content = self._p(params, "after_content")
        notes = self._p(params, "notes")
        results = []
        conn = self.Connect()
        cur = conn.cursor()
        for label, content in (("before_fix", before_content),
                               ("after_fix", after_content)):
            if content is None:
                continue
            try:
                content_hash = hashlib.sha256(
                    content.encode("utf-8")).hexdigest()
                cur.execute(
                    "INSERT INTO snapshots (snapshot_type, file_id, class_id, "
                    "method_id, content, hash, created, notes) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (label, file_id, class_id, method_id, content,
                     content_hash, self.Now(),
                     notes or (label + " snapshot")),
                )
                results.append({"snapshot_type": label,
                                "snapshot_id": cur.lastrowid,
                                "hash": content_hash})
            except sqlite3.Error as exc:
                return (0, None, ("INSERT_FAILED", str(exc), 0))
        conn.commit()
        return (1, {"snapshots": results, "count": len(results)}, None)

    def StoreEvidence(self, params):
        # 14.8 -- capture evidence from compile/test results
        knowledge_id = self._p(params, "knowledge_id")
        compile_result = self._p(params, "compile_result")
        test_result = self._p(params, "test_result")
        compile_output = self._p(params, "compile_output")
        test_output = self._p(params, "test_output")
        if knowledge_id is None:
            return (0, None, ("MISSING_PARAM", "knowledge_id required", 0))
        evidence = {}
        if compile_result is not None:
            evidence["compile_result"] = "pass" if compile_result else "fail"
        if compile_output is not None:
            evidence["compile_output"] = str(compile_output)
        if test_result is not None:
            evidence["test_result"] = "pass" if test_result else "fail"
        if test_output is not None:
            evidence["test_output"] = str(test_output)
        evidence_text = json.dumps(evidence) if evidence else ""
        fix_result = None
        if evidence.get("test_result") == "pass":
            fix_result = "success"
        elif evidence.get("test_result") == "fail":
            fix_result = "failure"
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE knowledge SET evidence=?, fix_result=? "
                "WHERE knowledge_id=?",
                (evidence_text, fix_result, knowledge_id),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "evidence": evidence}, None)
