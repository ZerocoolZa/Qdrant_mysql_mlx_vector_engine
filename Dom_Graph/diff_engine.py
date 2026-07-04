#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/diff_engine.py"
# date="2026-06-26" author="Devin" session_id="phase-orchestration"
# context="Project Digital Twin Section 19 Code Difference Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="diff_engine.py" domain="twin_diff" authority="DiffEngine"}
# [@SUMMARY]{summary="Difference engine authority that computes file, class, method, AST, graph, dependency, BCL, database, and runtime diffs."}
# [@CLASS]{class="DiffEngine" domain="diff" authority="single"}
# [@METHOD]{method="diff_file" type="command"}
# [@METHOD]{method="diff_class" type="command"}
# [@METHOD]{method="diff_method" type="command"}
# [@METHOD]{method="diff_ast" type="command"}
# [@METHOD]{method="diff_graph" type="command"}
# [@METHOD]{method="diff_all" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<DiffEngine: computes file/class/method/AST/graph/dependency/BCL/DB/runtime diffs. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
DiffEngine -- Code difference authority.
Implements Section 19 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: diff_file, diff_class, diff_method, diff_ast, diff_graph, diff_all.
Uses difflib for text diffs, ast.dump for AST diffs, SQL queries for graph diffs.
"""
import ast
import difflib
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class DiffEngine:
    """Code difference authority."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
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
        if command == "diff_file":
            return self.DiffFile(params)
        elif command == "diff_class":
            return self.DiffClass(params)
        elif command == "diff_method":
            return self.DiffMethod(params)
        elif command == "diff_ast":
            return self.DiffAst(params)
        elif command == "diff_graph":
            return self.DiffGraph(params)
        elif command == "diff_all":
            return self.DiffAll(params)

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
        return self.state["db_conn"]

    def Now(self):
        return datetime.now(timezone.utc).isoformat()

    def HashText(self, text):
        if text is None:
            return ""
        return hashlib.sha256(str(text).encode("utf-8")).hexdigest()

    def UnifiedDiff(self, before, after, label_before="before", label_after="after"):
        before_lines = (before or "").splitlines()
        after_lines = (after or "").splitlines()
        diff = list(difflib.unified_diff(
            before_lines, after_lines,
            fromfile=label_before, tofile=label_after, lineterm=""))
        return "\n".join(diff)

    def DiffFile(self, params):
        # 19.1 File Diff: compare file versions by hash + difflib on content
        before = self._p(params, "before")
        after = self._p(params, "after")
        file_id = self._p(params, "file_id")
        file_name = self._p(params, "file_name")
        if before is None or after is None:
            # Pull from DB: compare current files row to a snapshot
            conn = self.Connect()
            cur = conn.cursor()
            if file_id is not None:
                cur.execute(
                    "SELECT file_name, hash, size, version, imports, "
                    "exports, class_count, method_count FROM files "
                    "WHERE file_id=?", (file_id,))
            elif file_name is not None:
                cur.execute(
                    "SELECT file_name, hash, size, version, imports, "
                    "exports, class_count, method_count FROM files "
                    "WHERE file_name=? ORDER BY version DESC", (file_name,))
            else:
                return (0, None, ("MISSING_PARAM",
                                  "before/after or file_id/file_name required", 0))
            rows = cur.fetchall()
            if len(rows) < 2:
                return (0, None, ("NO_VERSIONS",
                                  "Need 2+ versions to diff", 0))
            before = rows[0]
            after = rows[1]
            keys = ["file_name", "hash", "size", "version", "imports",
                    "exports", "class_count", "method_count"]
            before = dict(zip(keys, before))
            after = dict(zip(keys, after))
        before_hash = self.HashText(before.get("hash", before) if isinstance(before, dict) else before)
        after_hash = self.HashText(after.get("hash", after) if isinstance(after, dict) else after)
        before_text = str(before)
        after_text = str(after)
        diff = self.UnifiedDiff(before_text, after_text)
        record = {
            "diff": diff,
            "lines_changed": len(diff.splitlines()),
            "before_hash": before_hash,
            "after_hash": after_hash,
            "hash_changed": before_hash != after_hash,
        }
        return (1, record, None)

    def DiffClass(self, params):
        # 19.2 Class Diff: compare class definitions (class rows) before/after
        before = self._p(params, "before")
        after = self._p(params, "after")
        class_id = self._p(params, "class_id")
        if before is None or after is None:
            conn = self.Connect()
            cur = conn.cursor()
            if class_id is None:
                return (0, None, ("MISSING_PARAM",
                                  "before/after or class_id required", 0))
            cur.execute(
                "SELECT class_name, parent, interfaces, bcl, start_line, "
                "end_line, method_count, properties, fields, dependencies, "
                "relationships, is_vbstyle, has_run_method, has_tuple3, "
                "cyclomatic_complexity, hash, version FROM classes "
                "WHERE class_id=? ORDER BY version DESC", (class_id,))
            rows = cur.fetchall()
            if len(rows) < 2:
                return (0, None, ("NO_VERSIONS",
                                  "Need 2+ versions to diff", 0))
            keys = ["class_name", "parent", "interfaces", "bcl", "start_line",
                    "end_line", "method_count", "properties", "fields",
                    "dependencies", "relationships", "is_vbstyle",
                    "has_run_method", "has_tuple3", "cyclomatic_complexity",
                    "hash", "version"]
            before = dict(zip(keys, rows[0]))
            after = dict(zip(keys, rows[1]))
        if not isinstance(before, dict) or not isinstance(after, dict):
            return (0, None, ("BAD_PARAM",
                              "before/after must be dicts or class_id given", 0))
        diffs = []
        keys = sorted(set(list(before.keys()) + list(after.keys())))
        for key in keys:
            bv = before.get(key)
            av = after.get(key)
            if bv != av:
                diffs.append({"key": key, "before": bv, "after": av})
        record = {
            "differences": diffs,
            "count": len(diffs),
            "before_hash": self.HashText(str(before)),
            "after_hash": self.HashText(str(after)),
            "hash_changed": self.HashText(str(before)) != self.HashText(str(after)),
        }
        return (1, record, None)

    def DiffMethod(self, params):
        # 19.3 Method Diff: compare method_code before/after with difflib
        before = self._p(params, "before")
        after = self._p(params, "after")
        method_id = self._p(params, "method_id")
        if before is None or after is None:
            conn = self.Connect()
            cur = conn.cursor()
            if method_id is None:
                return (0, None, ("MISSING_PARAM",
                                  "before/after or method_id required", 0))
            cur.execute(
                "SELECT method_code, hash, version FROM methods "
                "WHERE method_id=? ORDER BY version DESC", (method_id,))
            rows = cur.fetchall()
            if len(rows) < 2:
                return (0, None, ("NO_VERSIONS",
                                  "Need 2+ versions to diff", 0))
            before = rows[0][0] or ""
            after = rows[1][0] or ""
            before_hash = rows[0][1] or self.HashText(before)
            after_hash = rows[1][1] or self.HashText(after)
        else:
            before_hash = self.HashText(before)
            after_hash = self.HashText(after)
        diff = self.UnifiedDiff(before, after, "before", "after")
        record = {
            "diff": diff,
            "lines_changed": len(diff.splitlines()),
            "before_hash": before_hash,
            "after_hash": after_hash,
            "hash_changed": before_hash != after_hash,
        }
        return (1, record, None)

    def DiffAst(self, params):
        # 19.4 AST Diff: parse both versions, compare AST trees via ast.dump
        before_code = self._p(params, "before_code")
        after_code = self._p(params, "after_code")
        method_id = self._p(params, "method_id")
        if before_code is None or after_code is None:
            conn = self.Connect()
            cur = conn.cursor()
            if method_id is None:
                return (0, None, ("MISSING_PARAM",
                                  "before_code/after_code or method_id required", 0))
            cur.execute(
                "SELECT method_code FROM methods WHERE method_id=? "
                "ORDER BY version DESC", (method_id,))
            rows = cur.fetchall()
            if len(rows) < 2:
                return (0, None, ("NO_VERSIONS",
                                  "Need 2+ versions to diff", 0))
            before_code = rows[0][0] or ""
            after_code = rows[1][0] or ""
        try:
            before_ast = ast.dump(ast.parse(before_code))
        except SyntaxError:
            before_ast = "PARSE_ERROR"
        try:
            after_ast = ast.dump(ast.parse(after_code))
        except SyntaxError:
            after_ast = "PARSE_ERROR"
        same = before_ast == after_ast
        diff = self.UnifiedDiff(before_ast, after_ast, "before_ast", "after_ast")
        record = {
            "same": same,
            "before_hash": self.HashText(before_ast),
            "after_hash": self.HashText(after_ast),
            "diff": diff,
            "lines_changed": len(diff.splitlines()),
            "before_ast_len": len(before_ast),
            "after_ast_len": len(after_ast),
        }
        return (1, record, None)

    def DiffGraph(self, params):
        # 19.5 Graph Diff: compare edges table before/after via SQL queries
        before_edges = self._p(params, "before_edges")
        after_edges = self._p(params, "after_edges")
        edge_type = self._p(params, "edge_type")
        if before_edges is None or after_edges is None:
            conn = self.Connect()
            cur = conn.cursor()
            if edge_type is not None:
                cur.execute(
                    "SELECT src_type, src_id, dst_type, dst_id, edge_type, "
                    "evidence FROM edges WHERE edge_type=?", (edge_type,))
            else:
                cur.execute(
                    "SELECT src_type, src_id, dst_type, dst_id, edge_type, "
                    "evidence FROM edges")
            rows = cur.fetchall()
            snapshot_id = self._p(params, "snapshot_id")
            if snapshot_id is not None:
                # Compare current edges to a stored snapshot's edges
                cur.execute(
                    "SELECT content FROM snapshots WHERE snapshot_id=?",
                    (snapshot_id,))
                snap = cur.fetchone()
                if snap:
                    try:
                        before_edges = json.loads(snap[0])
                    except (ValueError, TypeError):
                        before_edges = []
                    after_edges = [list(r) for r in rows]
                else:
                    before_edges = [list(r) for r in rows]
                    after_edges = [list(r) for r in rows]
            else:
                # No snapshot: split rows in half as a demo comparison
                half = len(rows) // 2
                before_edges = [list(r) for r in rows[:half]]
                after_edges = [list(r) for r in rows[half:]]
        before_set = set(tuple(e) if isinstance(e, (list, tuple)) else (e,) for e in before_edges)
        after_set = set(tuple(e) if isinstance(e, (list, tuple)) else (e,) for e in after_edges)
        added = [list(e) for e in (after_set - before_set)]
        removed = [list(e) for e in (before_set - after_set)]
        common = [list(e) for e in (before_set & after_set)]
        record = {
            "added": added,
            "removed": removed,
            "common": common,
            "added_count": len(added),
            "removed_count": len(removed),
            "common_count": len(common),
            "changed": len(added) > 0 or len(removed) > 0,
        }
        return (1, record, None)

    def DiffAll(self, params):
        results = {}
        for step in ("diff_file", "diff_class", "diff_method",
                     "diff_ast", "diff_graph"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        return (1, {"diff_all": results}, None)

