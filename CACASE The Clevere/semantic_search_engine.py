#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/semantic_search_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 20: Semantic Search -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="semantic_search_engine.py" domain="twin_search" authority="SemanticSearchEngine"}
# [@SUMMARY]{summary="Semantic search authority: search by name, signature, error, dependency, call chain, variable, comment, BCL, behavior, and full-text search."}
# [@CLASS]{class="SemanticSearchEngine" domain="search" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="search_by_name" type="command"}
# [@METHOD]{method="search_by_signature" type="command"}
# [@METHOD]{method="search_by_error" type="command"}
# [@METHOD]{method="search_by_dependency" type="command"}
# [@METHOD]{method="search_by_call_chain" type="command"}
# [@METHOD]{method="search_by_variable" type="command"}
# [@METHOD]{method="search_by_comment" type="command"}
# [@METHOD]{method="search_by_bcl" type="command"}
# [@METHOD]{method="search_by_behavior" type="command"}
# [@METHOD]{method="search_by_fix" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import re
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"
FTS_SCHEMA = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS code_fts USING fts5("
    "content, content='methods', content_rowid='method_id')"
)


class SemanticSearchEngine:
    """Authority for semantic code search across the twin database."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "result_limit": 50,
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
        if command == "search_by_name":
            return self.SearchByName(params)
        elif command == "search_by_signature":
            return self.SearchBySignature(params)
        elif command == "search_by_error":
            return self.SearchByError(params)
        elif command == "search_by_dependency":
            return self.SearchByDependency(params)
        elif command == "search_by_call_chain":
            return self.SearchByCallChain(params)
        elif command == "search_by_variable":
            return self.SearchByVariable(params)
        elif command == "search_by_comment":
            return self.SearchByComment(params)
        elif command == "search_by_bcl":
            return self.SearchByBcl(params)
        elif command == "search_by_behavior":
            return self.SearchByBehavior(params)
        elif command == "search_by_fix":
            return self.SearchByFix(params)
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

    def SearchByName(self, params):
        query = self._p(params, "query")
        if query is None:
            return (0, None, ("MISSING_PARAM", "query required", 0))
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT method_id, method_name, class_id, file_id FROM methods "
                "WHERE method_name LIKE ? ORDER BY method_id LIMIT ?",
                ("%" + query + "%", limit),
            )
            methods = [{"method_id": r[0], "method_name": r[1],
                        "class_id": r[2], "file_id": r[3]} for r in cur.fetchall()]
            cur.execute(
                "SELECT class_id, class_name, file_id FROM classes "
                "WHERE class_name LIKE ? ORDER BY class_id LIMIT ?",
                ("%" + query + "%", limit),
            )
            classes = [{"class_id": r[0], "class_name": r[1], "file_id": r[2]}
                       for r in cur.fetchall()]
            cur.execute(
                "SELECT file_id, file_path FROM files WHERE file_path LIKE ? LIMIT ?",
                ("%" + query + "%", limit),
            )
            files = [{"file_id": r[0], "file_path": r[1]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"methods": methods, "classes": classes, "files": files,
                    "total": len(methods) + len(classes) + len(files)}, None)

    def SearchBySignature(self, params):
        query = self._p(params, "query")
        if query is None:
            return (0, None, ("MISSING_PARAM", "query required", 0))
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT method_id, method_name, signature FROM methods "
                "WHERE signature LIKE ? ORDER BY method_id LIMIT ?",
                ("%" + query + "%", limit),
            )
            results = [{"method_id": r[0], "method_name": r[1],
                        "signature": r[2]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"results": results, "count": len(results)}, None)

    def SearchByError(self, params):
        query = self._p(params, "query")
        if query is None:
            return (0, None, ("MISSING_PARAM", "query required", 0))
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT knowledge_id, method_id, error_type, problem, answer "
                "FROM knowledge WHERE error_type LIKE ? OR problem LIKE ? "
                "ORDER BY knowledge_id LIMIT ?",
                ("%" + query + "%", "%" + query + "%", limit),
            )
            results = [{"knowledge_id": r[0], "method_id": r[1],
                        "error_type": r[2], "problem": r[3], "answer": r[4]}
                       for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"results": results, "count": len(results)}, None)

    def SearchByDependency(self, params):
        query = self._p(params, "query")
        if query is None:
            return (0, None, ("MISSING_PARAM", "query required", 0))
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT file_id, file_path, imports FROM files "
                "WHERE imports LIKE ? LIMIT ?",
                ("%" + query + "%", limit),
            )
            results = [{"file_id": r[0], "file_path": r[1], "imports": r[2]}
                       for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"results": results, "count": len(results)}, None)

    def SearchByCallChain(self, params):
        method_id = self._p(params, "method_id")
        direction = self._p(params, "direction", "forward")
        depth = self._p(params, "depth", 5)
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        visited = set()
        chain = []
        current = [method_id]
        try:
            for level in range(depth):
                if not current:
                    break
                next_level = []
                for mid in current:
                    if mid in visited:
                        continue
                    visited.add(mid)
                    cur.execute(
                        "SELECT method_name FROM methods WHERE method_id=?",
                        (mid,)
                    )
                    row = cur.fetchone()
                    if row:
                        chain.append({"method_id": mid, "method_name": row[0],
                                      "level": level})
                    if direction == "forward":
                        cur.execute(
                            "SELECT dst_id FROM edges WHERE src_type='method' "
                            "AND dst_type='method' AND src_id=?", (mid,)
                        )
                    else:
                        cur.execute(
                            "SELECT src_id FROM edges WHERE dst_type='method' "
                            "AND src_type='method' AND dst_id=?", (mid,)
                        )
                    next_level.extend(r[0] for r in cur.fetchall())
                current = next_level
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"chain": chain, "depth": len(chain),
                    "direction": direction}, None)

    def SearchByVariable(self, params):
        query = self._p(params, "query")
        if query is None:
            return (0, None, ("MISSING_PARAM", "query required", 0))
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT method_id, method_name, method_code FROM methods "
                "WHERE method_code LIKE ? LIMIT ?",
                ("%" + query + "%", limit),
            )
            results = [{"method_id": r[0], "method_name": r[1],
                        "matched": query} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"results": results, "count": len(results)}, None)

    def SearchByComment(self, params):
        query = self._p(params, "query")
        if query is None:
            return (0, None, ("MISSING_PARAM", "query required", 0))
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT method_id, method_name, method_code FROM methods "
                "WHERE method_code LIKE ? OR method_code LIKE ? LIMIT ?",
                ("%#%" + query + "%", "%\"\"\"" + query + "%", limit),
            )
            results = [{"method_id": r[0], "method_name": r[1],
                        "comment_query": query} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"results": results, "count": len(results)}, None)

    def SearchByBcl(self, params):
        query = self._p(params, "query")
        if query is None:
            return (0, None, ("MISSING_PARAM", "query required", 0))
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT class_id, class_name, bcl FROM classes "
                "WHERE bcl LIKE ? LIMIT ?",
                ("%" + query + "%", limit),
            )
            classes = [{"class_id": r[0], "class_name": r[1], "bcl": r[2]}
                       for r in cur.fetchall()]
            cur.execute(
                "SELECT method_id, method_name, bcl FROM methods "
                "WHERE bcl LIKE ? LIMIT ?",
                ("%" + query + "%", limit),
            )
            methods = [{"method_id": r[0], "method_name": r[1], "bcl": r[2]}
                       for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"classes": classes, "methods": methods,
                    "count": len(classes) + len(methods)}, None)

    def SearchByBehavior(self, params):
        query = self._p(params, "query")
        if query is None:
            return (0, None, ("MISSING_PARAM", "query required", 0))
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT method_id, method_name, method_code, signature FROM methods "
                "WHERE method_code LIKE ? OR signature LIKE ? LIMIT ?",
                ("%" + query + "%", "%" + query + "%", limit),
            )
            results = [{"method_id": r[0], "method_name": r[1],
                        "signature": r[3]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"results": results, "count": len(results)}, None)

    def SearchByFix(self, params):
        query = self._p(params, "query")
        if query is None:
            return (0, None, ("MISSING_PARAM", "query required", 0))
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT knowledge_id, method_id, answer, evidence, confidence "
                "FROM knowledge WHERE answer LIKE ? OR evidence LIKE ? "
                "ORDER BY confidence DESC LIMIT ?",
                ("%" + query + "%", "%" + query + "%", limit),
            )
            results = [{"knowledge_id": r[0], "method_id": r[1],
                        "answer": r[2], "evidence": r[3], "confidence": r[4]}
                       for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"results": results, "count": len(results)}, None)
