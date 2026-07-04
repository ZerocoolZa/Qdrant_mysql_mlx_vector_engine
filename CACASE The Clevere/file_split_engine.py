#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/file_split_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 6: File Split -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="file_split_engine.py" domain="twin_file" authority="FileSplitEngine"}
# [@SUMMARY]{summary="File authority: store file, query file, update file, delete file, list files, count files, files by extension, files by status, files by hash, files by dependency."}
# [@CLASS]{class="FileSplitEngine" domain="file" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="store_file" type="command"}
# [@METHOD]{method="query_file" type="command"}
# [@METHOD]{method="update_file" type="command"}
# [@METHOD]{method="delete_file" type="command"}
# [@METHOD]{method="list_files" type="command"}
# [@METHOD]{method="count_files" type="command"}
# [@METHOD]{method="files_by_extension" type="command"}
# [@METHOD]{method="files_by_status" type="command"}
# [@METHOD]{method="files_by_hash" type="command"}
# [@METHOD]{method="files_by_dependency" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import hashlib
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class FileSplitEngine:
    """Authority for file CRUD and querying in the twin database."""

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
        if command == "store_file":
            return self.StoreFile(params)
        elif command == "query_file":
            return self.QueryFile(params)
        elif command == "update_file":
            return self.UpdateFile(params)
        elif command == "delete_file":
            return self.DeleteFile(params)
        elif command == "list_files":
            return self.ListFiles(params)
        elif command == "count_files":
            return self.CountFiles(params)
        elif command == "files_by_extension":
            return self.FilesByExtension(params)
        elif command == "files_by_status":
            return self.FilesByStatus(params)
        elif command == "files_by_hash":
            return self.FilesByHash(params)
        elif command == "files_by_dependency":
            return self.FilesByDependency(params)
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

    def StoreFile(self, params):
        file_path = self._p(params, "file_path")
        if file_path is None:
            return (0, None, ("MISSING_PARAM", "file_path required", 0))
        content = self._p(params, "content", "")
        language = self._p(params, "language", "")
        line_count = self._p(params, "line_count", len(content.split("\n")) if content else 0)
        file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest() if content else ""
        status = self._p(params, "status", "active")
        imports = self._p(params, "imports", "")
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO files (file_path, hash, line_count, language, status, imports, created) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (file_path, file_hash, line_count, language, status, imports, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"file_id": cur.lastrowid, "file_path": file_path,
                    "hash": file_hash}, None)

    def QueryFile(self, params):
        file_id = self._p(params, "file_id")
        file_path = self._p(params, "file_path")
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            if file_id:
                cur.execute("SELECT * FROM files WHERE file_id=?", (file_id,))
            elif file_path:
                cur.execute("SELECT * FROM files WHERE file_path=?", (file_path,))
            else:
                return (0, None, ("MISSING_PARAM", "file_id or file_path required", 0))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("FILE_NOT_FOUND", str(file_id or file_path), 0))
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"file": row}, None)

    def UpdateFile(self, params):
        file_id = self._p(params, "file_id")
        if file_id is None:
            return (0, None, ("MISSING_PARAM", "file_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        updates = []
        values = []
        for field in ("file_path", "hash", "line_count", "language", "status", "imports"):
            val = self._p(params, field)
            if val is not None:
                updates.append(field + "=?")
                values.append(val)
        if not updates:
            return (0, None, ("NO_UPDATES", "No fields to update", 0))
        values.append(file_id)
        try:
            cur.execute("UPDATE files SET " + ", ".join(updates) + " WHERE file_id=?", values)
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"file_id": file_id, "updated_fields": len(updates)}, None)

    def DeleteFile(self, params):
        file_id = self._p(params, "file_id")
        if file_id is None:
            return (0, None, ("MISSING_PARAM", "file_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM files WHERE file_id=?", (file_id,))
            conn.commit()
            deleted = cur.rowcount
        except sqlite3.Error as exc:
            return (0, None, ("DELETE_FAILED", str(exc), 0))
        return (1, {"file_id": file_id, "deleted": deleted > 0}, None)

    def ListFiles(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        offset = self._p(params, "offset", 0)
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT file_id, file_path, hash, line_count, language, status "
                "FROM files ORDER BY file_id LIMIT ? OFFSET ?",
                (limit, offset),
            )
            files = [{"file_id": r[0], "file_path": r[1], "hash": r[2],
                      "line_count": r[3], "language": r[4], "status": r[5]}
                     for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"files": files, "count": len(files)}, None)

    def CountFiles(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM files")
            total = cur.fetchone()[0]
            cur.execute("SELECT language, COUNT(*) FROM files GROUP BY language")
            by_lang = {r[0] or "unknown": r[1] for r in cur.fetchall()}
            cur.execute("SELECT status, COUNT(*) FROM files GROUP BY status")
            by_status = {r[0] or "unknown": r[1] for r in cur.fetchall()}
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"total": total, "by_language": by_lang, "by_status": by_status}, None)

    def FilesByExtension(self, params):
        extension = self._p(params, "extension")
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            if extension:
                cur.execute(
                    "SELECT file_id, file_path, line_count FROM files "
                    "WHERE file_path LIKE ? ORDER BY file_id LIMIT ?",
                    ("%" + extension, limit),
                )
            else:
                cur.execute(
                    "SELECT file_path FROM files"
                )
                ext_map = {}
                for r in cur.fetchall():
                    ext = os.path.splitext(r[0])[1] or "none"
                    ext_map[ext] = ext_map.get(ext, 0) + 1
                return (1, {"by_extension": ext_map, "total": sum(ext_map.values())}, None)
            files = [{"file_id": r[0], "file_path": r[1], "line_count": r[2]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"files": files, "count": len(files), "extension": extension}, None)

    def FilesByStatus(self, params):
        status = self._p(params, "status")
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            if status:
                cur.execute(
                    "SELECT file_id, file_path, line_count FROM files WHERE status=? LIMIT ?",
                    (status, limit),
                )
                files = [{"file_id": r[0], "file_path": r[1], "line_count": r[2]} for r in cur.fetchall()]
            else:
                cur.execute("SELECT status, COUNT(*) FROM files GROUP BY status")
                files = {r[0] or "unknown": r[1] for r in cur.fetchall()}
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"files": files, "count": len(files) if isinstance(files, list) else sum(files.values())}, None)

    def FilesByHash(self, params):
        file_hash = self._p(params, "hash")
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            if file_hash:
                cur.execute(
                    "SELECT file_id, file_path, line_count FROM files WHERE hash=? LIMIT ?",
                    (file_hash, limit),
                )
                files = [{"file_id": r[0], "file_path": r[1], "line_count": r[2]} for r in cur.fetchall()]
            else:
                cur.execute(
                    "SELECT hash, COUNT(*) as cnt FROM files WHERE hash IS NOT NULL "
                    "GROUP BY hash HAVING cnt > 1 LIMIT ?",
                    (limit,),
                )
                files = [{"hash": r[0], "count": r[1]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"files": files, "count": len(files)}, None)

    def FilesByDependency(self, params):
        dependency = self._p(params, "dependency")
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            if dependency:
                cur.execute(
                    "SELECT file_id, file_path, imports FROM files WHERE imports LIKE ? LIMIT ?",
                    ("%" + dependency + "%", limit),
                )
                files = [{"file_id": r[0], "file_path": r[1], "imports": r[2]} for r in cur.fetchall()]
            else:
                cur.execute(
                    "SELECT file_id, file_path, imports FROM files WHERE imports IS NOT NULL AND imports != '' LIMIT ?",
                    (limit,),
                )
                files = [{"file_id": r[0], "file_path": r[1], "imports": r[2]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"files": files, "count": len(files)}, None)
