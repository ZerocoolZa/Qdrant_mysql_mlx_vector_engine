#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/comparison_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 19: Code Difference Engine -- 9 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="comparison_engine.py" domain="twin_comparison" authority="ComparisonEngine"}
# [@SUMMARY]{summary="Comparison authority: file diff, class diff, method diff, AST diff, BCL diff, dependency diff, graph diff, database diff, runtime diff."}
# [@CLASS]{class="ComparisonEngine" domain="comparison" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="file_diff" type="command"}
# [@METHOD]{method="class_diff" type="command"}
# [@METHOD]{method="method_diff" type="command"}
# [@METHOD]{method="ast_diff" type="command"}
# [@METHOD]{method="bcl_diff" type="command"}
# [@METHOD]{method="dependency_diff" type="command"}
# [@METHOD]{method="graph_diff" type="command"}
# [@METHOD]{method="database_diff" type="command"}
# [@METHOD]{method="runtime_diff" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import ast
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class ComparisonEngine:
    """Authority for comparing code, structure, and runtime state."""

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
        if command == "file_diff":
            return self.FileDiff(params)
        elif command == "class_diff":
            return self.ClassDiff(params)
        elif command == "method_diff":
            return self.MethodDiff(params)
        elif command == "ast_diff":
            return self.AstDiff(params)
        elif command == "bcl_diff":
            return self.BclDiff(params)
        elif command == "dependency_diff":
            return self.DependencyDiff(params)
        elif command == "graph_diff":
            return self.GraphDiff(params)
        elif command == "database_diff":
            return self.DatabaseDiff(params)
        elif command == "runtime_diff":
            return self.RuntimeDiff(params)
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

    def FileDiff(self, params):
        file_id1 = self._p(params, "file_id1")
        file_id2 = self._p(params, "file_id2")
        if file_id1 is None or file_id2 is None:
            return (0, None, ("MISSING_PARAM", "file_id1 and file_id2 required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT file_path, hash, line_count FROM files WHERE file_id=?",
                    (file_id1,))
        row1 = cur.fetchone()
        cur.execute("SELECT file_path, hash, line_count FROM files WHERE file_id=?",
                    (file_id2,))
        row2 = cur.fetchone()
        if row1 is None or row2 is None:
            return (0, None, ("FILE_NOT_FOUND", "One or both files missing", 0))
        identical = row1[1] == row2[1]
        line_delta = (row2[2] or 0) - (row1[2] or 0)
        return (1, {"identical": identical, "file1": row1[0], "file2": row2[0],
                    "hash1": row1[1], "hash2": row2[1],
                    "line_delta": line_delta}, None)

    def ClassDiff(self, params):
        class_id1 = self._p(params, "class_id1")
        class_id2 = self._p(params, "class_id2")
        if class_id1 is None or class_id2 is None:
            return (0, None, ("MISSING_PARAM", "class_id1 and class_id2 required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT class_name, parent, method_count, bcl FROM classes WHERE class_id=?",
                    (class_id1,))
        row1 = cur.fetchone()
        cur.execute("SELECT class_name, parent, method_count, bcl FROM classes WHERE class_id=?",
                    (class_id2,))
        row2 = cur.fetchone()
        if row1 is None or row2 is None:
            return (0, None, ("CLASS_NOT_FOUND", "One or both classes missing", 0))
        diffs = []
        if row1[0] != row2[0]:
            diffs.append({"field": "name", "old": row1[0], "new": row2[0]})
        if row1[1] != row2[1]:
            diffs.append({"field": "parent", "old": row1[1], "new": row2[1]})
        if row1[2] != row2[2]:
            diffs.append({"field": "method_count", "old": row1[2], "new": row2[2]})
        if row1[3] != row2[3]:
            diffs.append({"field": "bcl", "old": row1[3], "new": row2[3]})
        return (1, {"diffs": diffs, "identical": len(diffs) == 0,
                    "class1": row1[0], "class2": row2[0]}, None)

    def MethodDiff(self, params):
        method_id1 = self._p(params, "method_id1")
        method_id2 = self._p(params, "method_id2")
        if method_id1 is None or method_id2 is None:
            return (0, None, ("MISSING_PARAM", "method_id1 and method_id2 required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_name, method_code, hash, signature FROM methods WHERE method_id=?",
                    (method_id1,))
        row1 = cur.fetchone()
        cur.execute("SELECT method_name, method_code, hash, signature FROM methods WHERE method_id=?",
                    (method_id2,))
        row2 = cur.fetchone()
        if row1 is None or row2 is None:
            return (0, None, ("METHOD_NOT_FOUND", "One or both methods missing", 0))
        code_identical = row1[2] == row2[2]
        sig_changed = row1[3] != row2[3]
        return (1, {"code_identical": code_identical,
                    "signature_changed": sig_changed,
                    "method1": row1[0], "method2": row2[0],
                    "hash1": row1[2], "hash2": row2[2]}, None)

    def AstDiff(self, params):
        path1 = self._p(params, "path1")
        path2 = self._p(params, "path2")
        if path1 is None or path2 is None:
            return (0, None, ("MISSING_PARAM", "path1 and path2 required", 0))
        if not os.path.isfile(path1) or not os.path.isfile(path2):
            return (0, None, ("FILE_NOT_FOUND", "One or both files missing", 0))
        with open(path1, "r", errors="replace") as f:
            content1 = f.read()
        with open(path2, "r", errors="replace") as f:
            content2 = f.read()
        try:
            tree1 = ast.parse(content1)
            tree2 = ast.parse(content2)
        except SyntaxError as exc:
            return (0, None, ("PARSE_FAILED", str(exc), 0))
        nodes1 = {type(n).__name__ for n in ast.walk(tree1)}
        nodes2 = {type(n).__name__ for n in ast.walk(tree2)}
        added = nodes2 - nodes1
        removed = nodes1 - nodes2
        classes1 = {n.name for n in ast.walk(tree1) if isinstance(n, ast.ClassDef)}
        classes2 = {n.name for n in ast.walk(tree2) if isinstance(n, ast.ClassDef)}
        funcs1 = {n.name for n in ast.walk(tree1) if isinstance(n, ast.FunctionDef)}
        funcs2 = {n.name for n in ast.walk(tree2) if isinstance(n, ast.FunctionDef)}
        return (1, {"node_types_added": sorted(added),
                    "node_types_removed": sorted(removed),
                    "classes_added": sorted(classes2 - classes1),
                    "classes_removed": sorted(classes1 - classes2),
                    "functions_added": sorted(funcs2 - funcs1),
                    "functions_removed": sorted(funcs1 - funcs2),
                    "identical": len(added) == 0 and len(removed) == 0 and
                                 len(classes2 - classes1) == 0 and
                                 len(classes1 - classes2) == 0 and
                                 len(funcs2 - funcs1) == 0 and
                                 len(funcs1 - funcs2) == 0}, None)

    def BclDiff(self, params):
        class_id1 = self._p(params, "class_id1")
        class_id2 = self._p(params, "class_id2")
        if class_id1 is None or class_id2 is None:
            return (0, None, ("MISSING_PARAM", "class_id1 and class_id2 required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT class_name, bcl FROM classes WHERE class_id=?", (class_id1,))
        row1 = cur.fetchone()
        cur.execute("SELECT class_name, bcl FROM classes WHERE class_id=?", (class_id2,))
        row2 = cur.fetchone()
        if row1 is None or row2 is None:
            return (0, None, ("CLASS_NOT_FOUND", "One or both classes missing", 0))
        bcl1 = row1[1] or ""
        bcl2 = row2[1] or ""
        hash1 = hashlib.sha256(bcl1.encode("utf-8")).hexdigest()
        hash2 = hashlib.sha256(bcl2.encode("utf-8")).hexdigest()
        return (1, {"bcl_identical": hash1 == hash2,
                    "class1": row1[0], "class2": row2[0],
                    "bcl1_hash": hash1, "bcl2_hash": hash2,
                    "bcl1_length": len(bcl1), "bcl2_length": len(bcl2)}, None)

    def DependencyDiff(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        snapshot1 = self._p(params, "snapshot1")
        snapshot2 = self._p(params, "snapshot2")
        try:
            cur.execute("SELECT COUNT(*) FROM edges")
            total = cur.fetchone()[0]
            cur.execute("SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type")
            by_type = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute(
                "SELECT src_id, src_type, dst_id, dst_type, edge_type FROM edges "
                "ORDER BY edge_id"
            )
            edges = [{"src_id": r[0], "src_type": r[1], "dst_id": r[2],
                      "dst_type": r[3], "edge_type": r[4]}
                     for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"total_edges": total, "edge_types": by_type,
                    "edges": edges[:500],
                    "edge_count": len(edges)}, None)

    def GraphDiff(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM edges")
            total_edges = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM classes")
            total_classes = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods")
            total_methods = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM files")
            total_files = cur.fetchone()[0]
            cur.execute("SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type")
            by_type = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute(
                "SELECT src_type, dst_type, COUNT(*) FROM edges "
                "GROUP BY src_type, dst_type ORDER BY COUNT(*) DESC"
            )
            by_pair = [{"src": r[0], "dst": r[1], "count": r[2]}
                       for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"total_edges": total_edges, "total_classes": total_classes,
                    "total_methods": total_methods, "total_files": total_files,
                    "edge_types": by_type, "edge_pairs": by_pair}, None)

    def DatabaseDiff(self, params):
        db_path1 = self._p(params, "db_path1")
        db_path2 = self._p(params, "db_path2")
        if db_path1 is None or db_path2 is None:
            return (0, None, ("MISSING_PARAM", "db_path1 and db_path2 required", 0))
        if not os.path.isfile(db_path1) or not os.path.isfile(db_path2):
            return (0, None, ("FILE_NOT_FOUND", "One or both DBs missing", 0))
        conn1 = sqlite3.connect(db_path1)
        conn2 = sqlite3.connect(db_path2)
        cur1 = conn1.cursor()
        cur2 = conn2.cursor()
        try:
            cur1.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables1 = {r[0] for r in cur1.fetchall()}
            cur2.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables2 = {r[0] for r in cur2.fetchall()}
            added = tables2 - tables1
            removed = tables1 - tables2
            common = tables1 & tables2
            row_diffs = {}
            for table in common:
                cur1.execute("SELECT COUNT(*) FROM " + table)
                c1 = cur1.fetchone()[0]
                cur2.execute("SELECT COUNT(*) FROM " + table)
                c2 = cur2.fetchone()[0]
                if c1 != c2:
                    row_diffs[table] = {"db1": c1, "db2": c2, "delta": c2 - c1}
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        finally:
            conn1.close()
            conn2.close()
        return (1, {"tables_added": sorted(added), "tables_removed": sorted(removed),
                    "row_differences": row_diffs,
                    "identical": len(added) == 0 and len(removed) == 0 and
                                 len(row_diffs) == 0}, None)

    def RuntimeDiff(self, params):
        path = self._p(params, "path")
        if path is None or not os.path.isfile(path):
            return (0, None, ("FILE_NOT_FOUND", str(path), 0))
        import subprocess
        import time
        try:
            start = time.perf_counter()
            result = subprocess.run(
                ["python3", path], capture_output=True, text=True, timeout=30,
            )
            elapsed = time.perf_counter() - start
        except subprocess.TimeoutExpired:
            return (1, {"valid": False, "error": "timeout", "file": path}, None)
        except Exception as exc:
            return (0, None, ("RUNTIME_ERROR", str(exc), 0))
        return (1, {"returncode": result.returncode,
                    "elapsed": round(elapsed, 4),
                    "stdout_length": len(result.stdout),
                    "stderr_length": len(result.stderr),
                    "stderr_preview": result.stderr[:200] if result.stderr else "",
                    "file": path}, None)
