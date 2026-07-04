#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/refactor_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 49: Refactoring Engine -- 8 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="refactor_engine.py" domain="twin_refactor" authority="RefactorEngine"}
# [@SUMMARY]{summary="Refactoring authority: safe rename, safe move, safe extract, safe inline, safe split, safe merge, safe delete, safe replace."}
# [@CLASS]{class="RefactorEngine" domain="refactor" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="safe_rename" type="command"}
# [@METHOD]{method="safe_move" type="command"}
# [@METHOD]{method="safe_extract" type="command"}
# [@METHOD]{method="safe_inline" type="command"}
# [@METHOD]{method="safe_split" type="command"}
# [@METHOD]{method="safe_merge" type="command"}
# [@METHOD]{method="safe_delete" type="command"}
# [@METHOD]{method="safe_replace" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class RefactorEngine:
    """Authority for safe refactoring operations with snapshot protection."""

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
        if command == "safe_rename":
            return self.SafeRename(params)
        elif command == "safe_move":
            return self.SafeMove(params)
        elif command == "safe_extract":
            return self.SafeExtract(params)
        elif command == "safe_inline":
            return self.SafeInline(params)
        elif command == "safe_split":
            return self.SafeSplit(params)
        elif command == "safe_merge":
            return self.SafeMerge(params)
        elif command == "safe_delete":
            return self.SafeDelete(params)
        elif command == "safe_replace":
            return self.SafeReplace(params)
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

    def SafeSnapshot(self, method_id, content, action):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO snapshots (snapshot_type, method_id, content, hash, created, notes) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("before_" + action, method_id, content,
                 __import__("hashlib").sha256((content or "").encode("utf-8")).hexdigest(),
                 self.Now()[1], "safe_" + action),
            )
            conn.commit()
        except sqlite3.Error:
            pass
        return cur.lastrowid

    def SafeRename(self, params):
        method_id = self._p(params, "method_id")
        new_name = self._p(params, "new_name")
        if method_id is None or new_name is None:
            return (0, None, ("MISSING_PARAM", "method_id and new_name required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT method_name, method_code FROM methods WHERE method_id=?", (method_id,))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
            old_name, code = row
            self.SafeSnapshot(method_id, code, "rename")
            cur.execute("UPDATE methods SET method_name=? WHERE method_id=?", (new_name, method_id))
            if code:
                new_code = code.replace("self." + old_name, "self." + new_name)
                cur.execute("UPDATE methods SET method_code=? WHERE method_id=?", (new_code, method_id))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        return (1, {"method_id": method_id, "old_name": old_name,
                    "new_name": new_name, "renamed": True}, None)

    def SafeMove(self, params):
        method_id = self._p(params, "method_id")
        target_class_id = self._p(params, "target_class_id")
        if method_id is None or target_class_id is None:
            return (0, None, ("MISSING_PARAM", "method_id and target_class_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT class_id, method_code FROM methods WHERE method_id=?", (method_id,))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
            old_class_id, code = row
            self.SafeSnapshot(method_id, code, "move")
            cur.execute("UPDATE methods SET class_id=? WHERE method_id=?", (target_class_id, method_id))
            cur.execute("UPDATE classes SET method_count = method_count - 1 WHERE class_id=?", (old_class_id,))
            cur.execute("UPDATE classes SET method_count = method_count + 1 WHERE class_id=?", (target_class_id,))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        return (1, {"method_id": method_id, "old_class_id": old_class_id,
                    "new_class_id": target_class_id, "moved": True}, None)

    def SafeExtract(self, params):
        method_id = self._p(params, "method_id")
        new_name = self._p(params, "new_name")
        if method_id is None or new_name is None:
            return (0, None, ("MISSING_PARAM", "method_id and new_name required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT method_code, class_id FROM methods WHERE method_id=?", (method_id,))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
            code, class_id = row
            self.SafeSnapshot(method_id, code, "extract")
            cur.execute(
                "INSERT INTO methods (method_name, method_code, class_id, created) "
                "VALUES (?, ?, ?, ?)",
                (new_name, code, class_id, self.Now()[1]),
            )
            new_id = cur.lastrowid
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        return (1, {"new_method_id": new_id, "new_name": new_name,
                    "source_method_id": method_id, "extracted": True}, None)

    def SafeInline(self, params):
        method_id = self._p(params, "method_id")
        target_method_id = self._p(params, "target_method_id")
        if method_id is None or target_method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id and target_method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT method_code, method_name FROM methods WHERE method_id=?", (method_id,))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
            source_code, source_name = row
            cur.execute("SELECT method_code FROM methods WHERE method_id=?", (target_method_id,))
            target_row = cur.fetchone()
            if target_row is None:
                return (0, None, ("METHOD_NOT_FOUND", str(target_method_id), 0))
            target_code = target_row[0] or ""
            self.SafeSnapshot(target_method_id, target_code, "inline")
            inlined = target_code.replace("self." + source_name + "(params)", source_code or "")
            cur.execute("UPDATE methods SET method_code=? WHERE method_id=?", (inlined, target_method_id))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        return (1, {"inlined_method": source_name, "target_method_id": target_method_id,
                    "inlined": True}, None)

    def SafeSplit(self, params):
        class_id = self._p(params, "class_id")
        new_class_name = self._p(params, "new_class_name")
        method_ids = self._p(params, "method_ids", [])
        if class_id is None or new_class_name is None:
            return (0, None, ("MISSING_PARAM", "class_id and new_class_name required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT class_name, file_id FROM classes WHERE class_id=?", (class_id,))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("CLASS_NOT_FOUND", str(class_id), 0))
            old_name, file_id = row
            cur.execute(
                "INSERT INTO classes (class_name, file_id, method_count, has_run_method, has_init, created) "
                "VALUES (?, ?, 0, 0, 0, ?)",
                (new_class_name, file_id, self.Now()[1]),
            )
            new_class_id = cur.lastrowid
            moved = 0
            for mid in method_ids:
                cur.execute("UPDATE methods SET class_id=? WHERE method_id=?", (new_class_id, mid))
                moved += 1
            cur.execute("UPDATE classes SET method_count = method_count - ? WHERE class_id=?", (moved, class_id))
            cur.execute("UPDATE classes SET method_count = ? WHERE class_id=?", (moved, new_class_id))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        return (1, {"new_class_id": new_class_id, "new_class_name": new_class_name,
                    "methods_moved": moved, "split": True}, None)

    def SafeMerge(self, params):
        source_class_id = self._p(params, "source_class_id")
        target_class_id = self._p(params, "target_class_id")
        if source_class_id is None or target_class_id is None:
            return (0, None, ("MISSING_PARAM", "source_class_id and target_class_id required", 0))
        if source_class_id == target_class_id:
            return (0, None, ("INVALID_PARAM", "cannot merge class with itself", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT method_count FROM classes WHERE class_id=?", (source_class_id,))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("CLASS_NOT_FOUND", str(source_class_id), 0))
            source_count = row[0]
            cur.execute("UPDATE methods SET class_id=? WHERE class_id=?", (target_class_id, source_class_id))
            cur.execute("UPDATE classes SET method_count = method_count + ? WHERE class_id=?", (source_count, target_class_id))
            cur.execute("DELETE FROM classes WHERE class_id=?", (source_class_id,))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        return (1, {"source_class_id": source_class_id, "target_class_id": target_class_id,
                    "merged": True, "methods_transferred": source_count}, None)

    def SafeDelete(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT method_code, class_id FROM methods WHERE method_id=?", (method_id,))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
            code, class_id = row
            self.SafeSnapshot(method_id, code, "delete")
            cur.execute("DELETE FROM edges WHERE src_id=? AND src_type='method'", (method_id,))
            cur.execute("DELETE FROM edges WHERE dst_id=? AND dst_type='method'", (method_id,))
            cur.execute("DELETE FROM methods WHERE method_id=?", (method_id,))
            if class_id:
                cur.execute("UPDATE classes SET method_count = method_count - 1 WHERE class_id=?", (class_id,))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        return (1, {"method_id": method_id, "deleted": True}, None)

    def SafeReplace(self, params):
        method_id = self._p(params, "method_id")
        new_code = self._p(params, "new_code")
        if method_id is None or new_code is None:
            return (0, None, ("MISSING_PARAM", "method_id and new_code required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT method_code FROM methods WHERE method_id=?", (method_id,))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
            old_code = row[0]
            self.SafeSnapshot(method_id, old_code, "replace")
            cur.execute("UPDATE methods SET method_code=? WHERE method_id=?", (new_code, method_id))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        return (1, {"method_id": method_id, "replaced": True,
                    "old_length": len(old_code or ""), "new_length": len(new_code)}, None)
