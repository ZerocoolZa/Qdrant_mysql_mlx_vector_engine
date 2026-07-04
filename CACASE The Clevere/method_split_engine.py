#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/method_split_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 8: Method Split -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="method_split_engine.py" domain="twin_method" authority="MethodSplitEngine"}
# [@SUMMARY]{summary="Method authority: store method, query method, update method, delete method, list methods, count methods, methods by class, methods by file, methods by complexity, split all."}
# [@CLASS]{class="MethodSplitEngine" domain="method" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="store_method" type="command"}
# [@METHOD]{method="query_method" type="command"}
# [@METHOD]{method="update_method" type="command"}
# [@METHOD]{method="delete_method" type="command"}
# [@METHOD]{method="list_methods" type="command"}
# [@METHOD]{method="count_methods" type="command"}
# [@METHOD]{method="methods_by_class" type="command"}
# [@METHOD]{method="methods_by_file" type="command"}
# [@METHOD]{method="methods_by_complexity" type="command"}
# [@METHOD]{method="split_all" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class MethodSplitEngine:
    """Authority for method CRUD and querying in the twin database."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "result_limit": 100,
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
        if command == "store_method":
            return self.StoreMethod(params)
        elif command == "query_method":
            return self.QueryMethod(params)
        elif command == "update_method":
            return self.UpdateMethod(params)
        elif command == "delete_method":
            return self.DeleteMethod(params)
        elif command == "list_methods":
            return self.ListMethods(params)
        elif command == "count_methods":
            return self.CountMethods(params)
        elif command == "methods_by_class":
            return self.MethodsByClass(params)
        elif command == "methods_by_file":
            return self.MethodsByFile(params)
        elif command == "methods_by_complexity":
            return self.MethodsByComplexity(params)
        elif command == "split_all":
            return self.SplitAll(params)
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

    def StoreMethod(self, params):
        method_name = self._p(params, "method_name")
        class_id = self._p(params, "class_id")
        if method_name is None:
            return (0, None, ("MISSING_PARAM", "method_name required", 0))
        method_code = self._p(params, "method_code", "")
        signature = self._p(params, "signature", "")
        bcl = self._p(params, "bcl", "")
        cyclomatic_complexity = self._p(params, "cyclomatic_complexity", 0)
        nesting_depth = self._p(params, "nesting_depth", 0)
        returns_tuple3 = self._p(params, "returns_tuple3", 0)
        has_print = self._p(params, "has_print", 0)
        has_decorator = self._p(params, "has_decorator", 0)
        has_self_underscore = self._p(params, "has_self_underscore", 0)
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO methods (method_name, class_id, method_code, signature, bcl, "
                "cyclomatic_complexity, nesting_depth, returns_tuple3, has_print, "
                "has_decorator, has_self_underscore, created) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (method_name, class_id, method_code, signature, bcl,
                 cyclomatic_complexity, nesting_depth, returns_tuple3,
                 has_print, has_decorator, has_self_underscore, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"method_id": cur.lastrowid, "method_name": method_name}, None)

    def QueryMethod(self, params):
        method_id = self._p(params, "method_id")
        method_name = self._p(params, "method_name")
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            if method_id:
                cur.execute("SELECT * FROM methods WHERE method_id=?", (method_id,))
            elif method_name:
                cur.execute("SELECT * FROM methods WHERE method_name=?", (method_name,))
            else:
                return (0, None, ("MISSING_PARAM", "method_id or method_name required", 0))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("METHOD_NOT_FOUND", str(method_id or method_name), 0))
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"method": row}, None)

    def UpdateMethod(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        updates = []
        values = []
        for field in ("method_name", "class_id", "method_code", "signature", "bcl",
                      "cyclomatic_complexity", "nesting_depth", "returns_tuple3",
                      "has_print", "has_decorator", "has_self_underscore"):
            val = self._p(params, field)
            if val is not None:
                updates.append(field + "=?")
                values.append(val)
        if not updates:
            return (0, None, ("NO_UPDATES", "No fields to update", 0))
        values.append(method_id)
        try:
            cur.execute("UPDATE methods SET " + ", ".join(updates) + " WHERE method_id=?", values)
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"method_id": method_id, "updated_fields": len(updates)}, None)

    def DeleteMethod(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM edges WHERE src_id=? AND src_type='method'", (method_id,))
            cur.execute("DELETE FROM edges WHERE dst_id=? AND dst_type='method'", (method_id,))
            cur.execute("DELETE FROM methods WHERE method_id=?", (method_id,))
            conn.commit()
            deleted = cur.rowcount
        except sqlite3.Error as exc:
            return (0, None, ("DELETE_FAILED", str(exc), 0))
        return (1, {"method_id": method_id, "deleted": deleted > 0}, None)

    def ListMethods(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        offset = self._p(params, "offset", 0)
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT method_id, method_name, class_id, signature, cyclomatic_complexity "
                "FROM methods ORDER BY method_id LIMIT ? OFFSET ?",
                (limit, offset),
            )
            methods = [{"method_id": r[0], "method_name": r[1], "class_id": r[2],
                        "signature": r[3], "complexity": r[4]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"methods": methods, "count": len(methods)}, None)

    def CountMethods(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM methods")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE returns_tuple3=1")
            with_tuple3 = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=1")
            with_print = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE has_decorator=1")
            with_decorator = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE has_self_underscore=1")
            with_underscore = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"total": total, "with_tuple3": with_tuple3,
                    "with_print": with_print, "with_decorator": with_decorator,
                    "with_underscore": with_underscore}, None)

    def MethodsByClass(self, params):
        class_id = self._p(params, "class_id")
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            if class_id:
                cur.execute(
                    "SELECT method_id, method_name, signature, cyclomatic_complexity "
                    "FROM methods WHERE class_id=? ORDER BY method_id LIMIT ?",
                    (class_id, limit),
                )
                methods = [{"method_id": r[0], "method_name": r[1],
                            "signature": r[2], "complexity": r[3]} for r in cur.fetchall()]
            else:
                cur.execute(
                    "SELECT class_id, COUNT(*) FROM methods GROUP BY class_id ORDER BY COUNT(*) DESC LIMIT ?",
                    (limit,),
                )
                methods = {"str(r[0])": r[1] for r in cur.fetchall()}
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"methods": methods, "count": len(methods) if isinstance(methods, list) else sum(methods.values())}, None)

    def MethodsByFile(self, params):
        file_id = self._p(params, "file_id")
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT m.method_id, m.method_name, m.cyclomatic_complexity "
                "FROM methods m JOIN classes c ON m.class_id = c.class_id "
                "WHERE c.file_id=? ORDER BY m.method_id LIMIT ?",
                (file_id, limit),
            )
            methods = [{"method_id": r[0], "method_name": r[1], "complexity": r[2]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"methods": methods, "count": len(methods), "file_id": file_id}, None)

    def MethodsByComplexity(self, params):
        min_complexity = self._p(params, "min_complexity", 10)
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT method_id, method_name, class_id, cyclomatic_complexity, nesting_depth "
                "FROM methods WHERE cyclomatic_complexity >= ? "
                "ORDER BY cyclomatic_complexity DESC LIMIT ?",
                (min_complexity, limit),
            )
            methods = [{"method_id": r[0], "method_name": r[1], "class_id": r[2],
                        "complexity": r[3], "nesting_depth": r[4]} for r in cur.fetchall()]
            cur.execute("SELECT AVG(cyclomatic_complexity) FROM methods")
            avg_cc = cur.fetchone()[0] or 0
            cur.execute("SELECT MAX(cyclomatic_complexity) FROM methods")
            max_cc = cur.fetchone()[0] or 0
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"methods": methods, "count": len(methods),
                    "avg_complexity": round(avg_cc, 2), "max_complexity": max_cc}, None)

    def SplitAll(self, params):
        class_id = self._p(params, "class_id")
        if class_id is None:
            return (0, None, ("MISSING_PARAM", "class_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT class_name FROM classes WHERE class_id=?", (class_id,))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("CLASS_NOT_FOUND", str(class_id), 0))
            class_name = row[0]
            cur.execute(
                "SELECT method_id, method_name, method_code, cyclomatic_complexity "
                "FROM methods WHERE class_id=? ORDER BY method_id",
                (class_id,),
            )
            methods = [{"method_id": r[0], "method_name": r[1],
                        "has_code": r[2] is not None, "complexity": r[3]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"class_id": class_id, "class_name": class_name,
                    "methods": methods, "method_count": len(methods)}, None)
