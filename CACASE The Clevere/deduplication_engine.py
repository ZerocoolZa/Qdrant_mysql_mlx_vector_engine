#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/deduplication_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 23: Duplicate Detection -- 9 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="deduplication_engine.py" domain="twin_dedup" authority="DeduplicationEngine"}
# [@SUMMARY]{summary="Deduplication authority: duplicate methods, classes, files, imports, constants, logic, algorithms, BCL, SQL."}
# [@CLASS]{class="DeduplicationEngine" domain="dedup" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="duplicate_methods" type="command"}
# [@METHOD]{method="duplicate_classes" type="command"}
# [@METHOD]{method="duplicate_files" type="command"}
# [@METHOD]{method="duplicate_imports" type="command"}
# [@METHOD]{method="duplicate_constants" type="command"}
# [@METHOD]{method="duplicate_logic" type="command"}
# [@METHOD]{method="duplicate_algorithms" type="command"}
# [@METHOD]{method="duplicate_bcl" type="command"}
# [@METHOD]{method="duplicate_sql" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class DeduplicationEngine:
    """Authority for detecting duplicates across the codebase."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "min_dup_lines": 3,
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
        if command == "duplicate_methods":
            return self.DuplicateMethods(params)
        elif command == "duplicate_classes":
            return self.DuplicateClasses(params)
        elif command == "duplicate_files":
            return self.DuplicateFiles(params)
        elif command == "duplicate_imports":
            return self.DuplicateImports(params)
        elif command == "duplicate_constants":
            return self.DuplicateConstants(params)
        elif command == "duplicate_logic":
            return self.DuplicateLogic(params)
        elif command == "duplicate_algorithms":
            return self.DuplicateAlgorithms(params)
        elif command == "duplicate_bcl":
            return self.DuplicateBcl(params)
        elif command == "duplicate_sql":
            return self.DuplicateSql(params)
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

    def DuplicateMethods(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT hash, COUNT(*) as cnt FROM methods WHERE hash IS NOT NULL "
                "GROUP BY hash HAVING cnt > 1 ORDER BY cnt DESC"
            )
            dup_hashes = cur.fetchall()
            duplicates = []
            for dhash, cnt in dup_hashes:
                cur.execute(
                    "SELECT method_id, method_name, class_id, file_id FROM methods WHERE hash=?",
                    (dhash,),
                )
                methods = [{"method_id": r[0], "method_name": r[1],
                            "class_id": r[2], "file_id": r[3]} for r in cur.fetchall()]
                duplicates.append({"hash": dhash, "count": cnt, "methods": methods})
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"duplicates": duplicates, "groups": len(duplicates),
                    "total_dup_methods": sum(d["count"] for d in duplicates)}, None)

    def DuplicateClasses(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT class_name, COUNT(*) as cnt FROM classes "
                "GROUP BY class_name HAVING cnt > 1 ORDER BY cnt DESC"
            )
            dup_names = cur.fetchall()
            duplicates = []
            for name, cnt in dup_names:
                cur.execute(
                    "SELECT class_id, file_id FROM classes WHERE class_name=?",
                    (name,),
                )
                classes = [{"class_id": r[0], "file_id": r[1]} for r in cur.fetchall()]
                duplicates.append({"class_name": name, "count": cnt, "instances": classes})
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"duplicates": duplicates, "groups": len(duplicates)}, None)

    def DuplicateFiles(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT hash, COUNT(*) as cnt FROM files WHERE hash IS NOT NULL "
                "GROUP BY hash HAVING cnt > 1"
            )
            dup_hashes = cur.fetchall()
            duplicates = []
            for dhash, cnt in dup_hashes:
                cur.execute(
                    "SELECT file_id, file_path FROM files WHERE hash=?",
                    (dhash,),
                )
                files = [{"file_id": r[0], "file_path": r[1]} for r in cur.fetchall()]
                duplicates.append({"hash": dhash, "count": cnt, "files": files})
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"duplicates": duplicates, "groups": len(duplicates)}, None)

    def DuplicateImports(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT file_id, file_path, imports FROM files WHERE imports IS NOT NULL AND imports != ''"
            )
            import_map = {}
            for row in cur.fetchall():
                file_id, file_path, imports_raw = row[0], row[1], row[2]
                try:
                    import json
                    imports_list = json.loads(imports_raw) if imports_raw.startswith("[") else [imports_raw]
                except Exception:
                    imports_list = [imports_raw]
                for imp in imports_list:
                    if imp not in import_map:
                        import_map[imp] = []
                    import_map[imp].append({"file_id": file_id, "file_path": file_path})
            duplicates = [{"import": imp, "files": files, "count": len(files)}
                          for imp, files in import_map.items() if len(files) > 1]
            duplicates.sort(key=lambda x: x["count"], reverse=True)
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"duplicates": duplicates, "count": len(duplicates)}, None)

    def DuplicateConstants(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT method_id, method_name, method_code FROM methods "
                "WHERE method_code LIKE '%UPPERCASE%' OR method_code LIKE '%_CONST%'"
            )
            constant_map = {}
            for row in cur.fetchall():
                import re
                code = row[2] or ""
                constants = re.findall(r'([A-Z][A-Z_0-9]{2,})\s*=', code)
                for const in constants:
                    if const not in constant_map:
                        constant_map[const] = []
                    constant_map[const].append({"method_id": row[0], "method_name": row[1]})
            duplicates = [{"constant": c, "locations": locs, "count": len(locs)}
                          for c, locs in constant_map.items() if len(locs) > 1]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"duplicates": duplicates, "count": len(duplicates)}, None)

    def DuplicateLogic(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT method_id, method_name, method_code FROM methods "
                "WHERE method_code IS NOT NULL ORDER BY method_id"
            )
            methods = cur.fetchall()
            import hashlib
            block_map = {}
            for mid, mname, code in methods:
                if not code or len(code) < 50:
                    continue
                lines = code.strip().split("\n")
                for i in range(len(lines) - 2):
                    block = "\n".join(lines[i:i+3]).strip()
                    if len(block) < 20:
                        continue
                    bhash = hashlib.sha256(block.encode("utf-8")).hexdigest()
                    if bhash not in block_map:
                        block_map[bhash] = {"block": block, "locations": []}
                    block_map[bhash]["locations"].append({"method_id": mid, "method_name": mname, "line": i})
            duplicates = []
            for bhash, info in block_map.items():
                if len(info["locations"]) > 1:
                    duplicates.append({"hash": bhash, "block": info["block"][:100],
                                       "locations": info["locations"][:10],
                                       "count": len(info["locations"])})
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"duplicates": duplicates[:100], "count": len(duplicates)}, None)

    def DuplicateAlgorithms(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT method_id, method_name, hash, signature FROM methods "
                "WHERE hash IS NOT NULL ORDER BY method_id"
            )
            methods = cur.fetchall()
            sig_map = {}
            for mid, mname, mhash, sig in methods:
                if sig is None:
                    continue
                normalized = "".join(sig.split()).lower()
                if normalized not in sig_map:
                    sig_map[normalized] = []
                sig_map[normalized].append({"method_id": mid, "method_name": mname, "hash": mhash})
            duplicates = [{"signature": sig, "methods": methods, "count": len(methods)}
                          for sig, methods in sig_map.items() if len(methods) > 1]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"duplicates": duplicates, "count": len(duplicates)}, None)

    def DuplicateBcl(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT class_id, class_name, bcl FROM classes WHERE bcl IS NOT NULL AND bcl != ''"
            )
            bcl_map = {}
            import hashlib
            for row in cur.fetchall():
                bcl_hash = hashlib.sha256((row[2] or "").encode("utf-8")).hexdigest()
                if bcl_hash not in bcl_map:
                    bcl_map[bcl_hash] = []
                bcl_map[bcl_hash].append({"class_id": row[0], "class_name": row[1]})
            duplicates = [{"bcl_hash": h, "classes": classes, "count": len(classes)}
                          for h, classes in bcl_map.items() if len(classes) > 1]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"duplicates": duplicates, "count": len(duplicates)}, None)

    def DuplicateSql(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT method_id, method_name, method_code FROM methods "
                "WHERE method_code LIKE '%SELECT %' OR method_code LIKE '%INSERT %' "
                "OR method_code LIKE '%UPDATE %' OR method_code LIKE '%DELETE %'"
            )
            sql_map = {}
            import re
            for row in cur.fetchall():
                code = row[2] or ""
                sqls = re.findall(r'(?:SELECT|INSERT|UPDATE|DELETE)[^;]+', code, re.IGNORECASE)
                for sql in sqls:
                    normalized = " ".join(sql.split()).upper()
                    if normalized not in sql_map:
                        sql_map[normalized] = []
                    sql_map[normalized].append({"method_id": row[0], "method_name": row[1]})
            duplicates = [{"sql": sql[:100], "locations": locs, "count": len(locs)}
                          for sql, locs in sql_map.items() if len(locs) > 1]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"duplicates": duplicates[:100], "count": len(duplicates)}, None)
