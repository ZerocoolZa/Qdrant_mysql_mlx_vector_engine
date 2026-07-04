#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/class_split_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 7: Class Split -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="class_split_engine.py" domain="twin_class" authority="ClassSplitEngine"}
# [@SUMMARY]{summary="Class authority: store class, query class, update class, delete class, list classes, count classes, classes by parent, classes by file, classes by dependency, split all."}
# [@CLASS]{class="ClassSplitEngine" domain="class" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="store_class" type="command"}
# [@METHOD]{method="query_class" type="command"}
# [@METHOD]{method="update_class" type="command"}
# [@METHOD]{method="delete_class" type="command"}
# [@METHOD]{method="list_classes" type="command"}
# [@METHOD]{method="count_classes" type="command"}
# [@METHOD]{method="classes_by_parent" type="command"}
# [@METHOD]{method="classes_by_file" type="command"}
# [@METHOD]{method="classes_by_dependency" type="command"}
# [@METHOD]{method="split_all" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class ClassSplitEngine:
    """Authority for class CRUD and querying in the twin database."""

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
        if command == "store_class":
            return self.StoreClass(params)
        elif command == "query_class":
            return self.QueryClass(params)
        elif command == "update_class":
            return self.UpdateClass(params)
        elif command == "delete_class":
            return self.DeleteClass(params)
        elif command == "list_classes":
            return self.ListClasses(params)
        elif command == "count_classes":
            return self.CountClasses(params)
        elif command == "classes_by_parent":
            return self.ClassesByParent(params)
        elif command == "classes_by_file":
            return self.ClassesByFile(params)
        elif command == "classes_by_dependency":
            return self.ClassesByDependency(params)
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

    def StoreClass(self, params):
        class_name = self._p(params, "class_name")
        file_id = self._p(params, "file_id")
        if class_name is None:
            return (0, None, ("MISSING_PARAM", "class_name required", 0))
        parent = self._p(params, "parent", "")
        bcl = self._p(params, "bcl", "")
        method_count = self._p(params, "method_count", 0)
        has_run = self._p(params, "has_run_method", 0)
        has_init = self._p(params, "has_init", 0)
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO classes (class_name, file_id, parent, bcl, method_count, "
                "has_run_method, has_init, created) VALUES (?,?,?,?,?,?,?,?)",
                (class_name, file_id, parent, bcl, method_count, has_run, has_init, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"class_id": cur.lastrowid, "class_name": class_name}, None)

    def QueryClass(self, params):
        class_id = self._p(params, "class_id")
        class_name = self._p(params, "class_name")
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            if class_id:
                cur.execute("SELECT * FROM classes WHERE class_id=?", (class_id,))
            elif class_name:
                cur.execute("SELECT * FROM classes WHERE class_name=?", (class_name,))
            else:
                return (0, None, ("MISSING_PARAM", "class_id or class_name required", 0))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("CLASS_NOT_FOUND", str(class_id or class_name), 0))
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"class": row}, None)

    def UpdateClass(self, params):
        class_id = self._p(params, "class_id")
        if class_id is None:
            return (0, None, ("MISSING_PARAM", "class_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        updates = []
        values = []
        for field in ("class_name", "file_id", "parent", "bcl", "method_count", "has_run_method", "has_init"):
            val = self._p(params, field)
            if val is not None:
                updates.append(field + "=?")
                values.append(val)
        if not updates:
            return (0, None, ("NO_UPDATES", "No fields to update", 0))
        values.append(class_id)
        try:
            cur.execute("UPDATE classes SET " + ", ".join(updates) + " WHERE class_id=?", values)
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"class_id": class_id, "updated_fields": len(updates)}, None)

    def DeleteClass(self, params):
        class_id = self._p(params, "class_id")
        if class_id is None:
            return (0, None, ("MISSING_PARAM", "class_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM methods WHERE class_id=?", (class_id,))
            cur.execute("DELETE FROM classes WHERE class_id=?", (class_id,))
            conn.commit()
            deleted = cur.rowcount
        except sqlite3.Error as exc:
            return (0, None, ("DELETE_FAILED", str(exc), 0))
        return (1, {"class_id": class_id, "deleted": deleted > 0}, None)

    def ListClasses(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        offset = self._p(params, "offset", 0)
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT class_id, class_name, file_id, method_count, parent, has_run_method "
                "FROM classes ORDER BY class_id LIMIT ? OFFSET ?",
                (limit, offset),
            )
            classes = [{"class_id": r[0], "class_name": r[1], "file_id": r[2],
                        "method_count": r[3], "parent": r[4], "has_run": r[5]}
                       for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"classes": classes, "count": len(classes)}, None)

    def CountClasses(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM classes")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM classes WHERE has_run_method=1")
            with_run = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM classes WHERE has_init=1")
            with_init = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"total": total, "with_run_method": with_run,
                    "with_init": with_init}, None)

    def ClassesByParent(self, params):
        parent = self._p(params, "parent")
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            if parent:
                cur.execute(
                    "SELECT class_id, class_name, method_count FROM classes WHERE parent=? LIMIT ?",
                    (parent, limit),
                )
            else:
                cur.execute(
                    "SELECT parent, COUNT(*) FROM classes WHERE parent IS NOT NULL AND parent != '' "
                    "GROUP BY parent ORDER BY COUNT(*) DESC LIMIT ?",
                    (limit,),
                )
                result = {r[0]: r[1] for r in cur.fetchall()}
                return (1, {"by_parent": result, "total": sum(result.values())}, None)
            classes = [{"class_id": r[0], "class_name": r[1], "method_count": r[2]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"classes": classes, "count": len(classes), "parent": parent}, None)

    def ClassesByFile(self, params):
        file_id = self._p(params, "file_id")
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            if file_id:
                cur.execute(
                    "SELECT class_id, class_name, method_count FROM classes WHERE file_id=? LIMIT ?",
                    (file_id, limit),
                )
            else:
                cur.execute(
                    "SELECT file_id, COUNT(*) FROM classes GROUP BY file_id ORDER BY COUNT(*) DESC LIMIT ?",
                    (limit,),
                )
                result = {str(r[0]): r[1] for r in cur.fetchall()}
                return (1, {"by_file": result, "total": sum(result.values())}, None)
            classes = [{"class_id": r[0], "class_name": r[1], "method_count": r[2]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"classes": classes, "count": len(classes), "file_id": file_id}, None)

    def ClassesByDependency(self, params):
        dependency = self._p(params, "dependency")
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            if dependency:
                cur.execute(
                    "SELECT class_id, class_name FROM classes WHERE bcl LIKE ? LIMIT ?",
                    ("%" + dependency + "%", limit),
                )
                classes = [{"class_id": r[0], "class_name": r[1]} for r in cur.fetchall()]
            else:
                cur.execute(
                    "SELECT c.class_id, c.class_name, COUNT(e.edge_id) as dep_count "
                    "FROM classes c LEFT JOIN edges e ON c.class_id = e.src_id AND e.src_type='class' "
                    "GROUP BY c.class_id ORDER BY dep_count DESC LIMIT ?",
                    (limit,),
                )
                classes = [{"class_id": r[0], "class_name": r[1], "dep_count": r[2]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"classes": classes, "count": len(classes)}, None)

    def SplitAll(self, params):
        file_id = self._p(params, "file_id")
        if file_id is None:
            return (0, None, ("MISSING_PARAM", "file_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT file_path FROM files WHERE file_id=?", (file_id,))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("FILE_NOT_FOUND", str(file_id), 0))
            cur.execute("SELECT class_id, class_name FROM classes WHERE file_id=?", (file_id,))
            classes = [{"class_id": r[0], "class_name": r[1]} for r in cur.fetchall()]
            cur.execute("SELECT COUNT(*) FROM methods WHERE class_id IN (SELECT class_id FROM classes WHERE file_id=?)", (file_id,))
            method_count = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"file_id": file_id, "classes": classes,
                    "class_count": len(classes), "method_count": method_count}, None)
