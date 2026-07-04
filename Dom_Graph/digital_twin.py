#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/digital_twin.py"
# date="2026-06-26" author="Devin" session_id="phase-orchestration"
# context="Project Digital Twin Section 35 Project Digital Twin"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="digital_twin.py" domain="twin_twin" authority="DigitalTwin"}
# [@SUMMARY]{summary="Digital twin authority that gets state, simulates changes, queries, exports/imports snapshots, and compares twin states."}
# [@CLASS]{class="DigitalTwin" domain="twin" authority="single"}
# [@METHOD]{method="get_state" type="command"}
# [@METHOD]{method="simulate_change" type="command"}
# [@METHOD]{method="query" type="command"}
# [@METHOD]{method="export_snapshot" type="command"}
# [@METHOD]{method="import_snapshot" type="command"}
# [@METHOD]{method="compare_twins" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<DigitalTwin: gets state, simulates changes, queries, exports/imports snapshots, compares twin states. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
DigitalTwin -- Project digital twin authority.
Implements Section 35 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: get_state, simulate_change, query, export_snapshot, import_snapshot, compare_twins.
"""
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import sandbox_engine


class DigitalTwin:
    """Project digital twin authority."""

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
        if command == "get_state":
            return self.GetState(params)
        elif command == "simulate_change":
            return self.SimulateChange(params)
        elif command == "query":
            return self.Query(params)
        elif command == "export_snapshot":
            return self.ExportSnapshot(params)
        elif command == "import_snapshot":
            return self.ImportSnapshot(params)
        elif command == "compare_twins":
            return self.CompareTwins(params)

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

    def GetState(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        state = {}
        for table in ("files", "classes", "methods", "edges", "knowledge", "snapshots", "attempts", "observations"):
            try:
                cur.execute("SELECT COUNT(*) FROM " + table)
                state[table] = cur.fetchone()[0]
            except sqlite3.Error:
                state[table] = -1
        cur.execute("PRAGMA integrity_check")
        state["integrity"] = cur.fetchone()[0]
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        state["tables"] = [row[0] for row in cur.fetchall()]
        cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
        state["indexes"] = [row[0] for row in cur.fetchall()]
        cur.execute("SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type")
        state["edge_types"] = {row[0]: row[1] for row in cur.fetchall()}
        cur.execute("SELECT COUNT(*) FROM files WHERE bcl IS NOT NULL AND bcl != ''")
        state["files_with_bcl"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE bcl IS NOT NULL AND bcl != ''")
        state["methods_with_bcl"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE error_type IS NOT NULL")
        state["error_count"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE answer IS NOT NULL")
        state["fix_count"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE fix_result='success'")
        state["successful_fixes"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM snapshots")
        state["snapshot_count"] = cur.fetchone()[0]
        state["db_path"] = self.state["config"]["db_path"]
        state["created"] = datetime.now(timezone.utc).isoformat()
        return (1, {"state": state}, None)

    def SimulateChange(self, params):
        change = self._p(params, "change_description", "")
        method_id = self._p(params, "method_id")
        new_code = self._p(params, "new_code")
        sql_change = self._p(params, "sql")
        sb = sandbox_engine.SandboxEngine(param=self.state["config"])
        load_res = sb.Run("load", params)
        if load_res[0] != 1:
            return load_res
        sandbox_conn = sb.state.get("db_conn")
        if sandbox_conn is None:
            sandbox_conn = sqlite3.connect(":memory:")
        sb_cur = sandbox_conn.cursor()
        exp_res = sb.Run("begin_experiment", params)
        if exp_res[0] != 1:
            return exp_res
        applied = False
        if method_id and new_code:
            try:
                sb_cur.execute("UPDATE methods SET method_code=? WHERE method_id=?", (new_code, method_id))
                sandbox_conn.commit()
                applied = True
            except sqlite3.Error as exc:
                sb.Run("rollback", params)
                return (0, None, ("SIMULATE_ERROR", str(exc), 0))
        if sql_change:
            try:
                sb_cur.execute(sql_change)
                sandbox_conn.commit()
                applied = True
            except sqlite3.Error as exc:
                sb.Run("rollback", params)
                return (0, None, ("SIMULATE_ERROR", str(exc), 0))
        affected = []
        if method_id:
            sb_cur.execute(
                "WITH RECURSIVE forward AS ("
                "SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type "
                "FROM edges WHERE src_type='method' AND src_id=? AND edge_type='calls' "
                "UNION SELECT e.edge_id, e.src_type, e.src_id, e.dst_type, e.dst_id, e.edge_type "
                "FROM edges e JOIN forward f ON e.src_type='method' AND e.src_id=f.dst_id "
                "WHERE e.edge_type='calls') SELECT DISTINCT dst_id FROM forward",
                (method_id,),
            )
            affected = [r[0] for r in sb_cur.fetchall()]
        before_counts = {}
        for table in ("files", "classes", "methods", "edges", "knowledge"):
            try:
                sb_cur.execute("SELECT COUNT(*) FROM " + table)
                before_counts[table] = sb_cur.fetchone()[0]
            except sqlite3.Error:
                before_counts[table] = -1
        sb_cur.execute("PRAGMA integrity_check")
        sandbox_integrity = sb_cur.fetchone()[0]
        sb.Run("rollback", params)
        risk_level = "low"
        if len(affected) > 10:
            risk_level = "high"
        elif len(affected) > 3:
            risk_level = "medium"
        result = {
            "change": change,
            "applied": applied,
            "affected_entities": affected,
            "affected_count": len(affected),
            "risk": len(affected),
            "risk_level": risk_level,
            "sandbox_integrity": sandbox_integrity,
            "before_counts": before_counts,
            "rolled_back": True,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def Query(self, params):
        sql = self._p(params, "sql", "")
        if not sql.strip():
            return (0, None, ("NO_PARAM", "sql required", 0))
        if not sql.strip().upper().startswith("SELECT"):
            return (0, None, ("INVALID_QUERY", "Only SELECT statements allowed", 0))
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            columns = [d[0] for d in cur.description] if cur.description else []
            return (1, {"columns": columns, "rows": rows, "count": len(rows)}, None)
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_ERROR", str(exc), 0))

    def ExportSnapshot(self, params):
        export_path = self._p(params, "export_path")
        if not export_path:
            export_path = os.path.join(
                _THIS_DIR,
                "twin_snapshot_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + ".db",
            )
        src_conn = self.Connect()
        dst_conn = sqlite3.connect(export_path)
        try:
            src_conn.backup(dst_conn)
        except sqlite3.Error as exc:
            dst_conn.close()
            return (0, None, ("EXPORT_ERROR", str(exc), 0))
        dst_conn.close()
        with open(export_path, "rb") as f:
            file_bytes = f.read()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        file_size = len(file_bytes)
        cur = src_conn.cursor()
        cur.execute(
            "INSERT INTO snapshots (snapshot_type, content, hash, created, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            ("manual", export_path, file_hash, datetime.now(timezone.utc).isoformat(), "digital_twin_export"),
        )
        src_conn.commit()
        snapshot_id = cur.lastrowid
        result = {
            "snapshot_id": snapshot_id,
            "export_path": export_path,
            "hash": file_hash,
            "size": file_size,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def ImportSnapshot(self, params):
        snapshot_id = self._p(params, "snapshot_id")
        import_path = self._p(params, "import_path")
        target_db = self._p(params, "target_db")
        if not snapshot_id and not import_path:
            return (0, None, ("NO_PARAM", "snapshot_id or import_path required", 0))
        if snapshot_id and not import_path:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("SELECT content, hash, created FROM snapshots WHERE snapshot_id=?", (snapshot_id,))
            row = cur.fetchone()
            if not row:
                return (0, None, ("NOT_FOUND", "Snapshot not found", 0))
            import_path = row[0]
            stored_hash = row[1]
            created = row[2]
        else:
            stored_hash = None
            created = None
        if not os.path.isfile(import_path):
            return (0, None, ("FILE_NOT_FOUND", import_path, 0))
        with open(import_path, "rb") as f:
            file_bytes = f.read()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        if stored_hash and stored_hash != file_hash:
            return (0, None, ("HASH_MISMATCH", "Snapshot hash does not match stored hash", 0))
        if not target_db:
            target_db = ":memory:"
        dst_conn = sqlite3.connect(target_db)
        src_conn = sqlite3.connect(import_path)
        try:
            src_conn.backup(dst_conn)
        except sqlite3.Error as exc:
            src_conn.close()
            dst_conn.close()
            return (0, None, ("IMPORT_ERROR", str(exc), 0))
        dst_cur = dst_conn.cursor()
        dst_cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in dst_cur.fetchall()]
        row_counts = {}
        for table in tables:
            try:
                dst_cur.execute("SELECT COUNT(*) FROM " + table)
                row_counts[table] = dst_cur.fetchone()[0]
            except sqlite3.Error:
                row_counts[table] = -1
        dst_cur.execute("PRAGMA integrity_check")
        integrity = dst_cur.fetchone()[0]
        src_conn.close()
        dst_conn.close()
        result = {
            "import_path": import_path,
            "target_db": target_db,
            "hash": file_hash,
            "tables": tables,
            "row_counts": row_counts,
            "integrity": integrity,
            "created": created,
        }
        self.state["results"].append(result)
        return (1, result, None)

    def CompareTwins(self, params):
        snapshot1 = self._p(params, "snapshot1")
        snapshot2 = self._p(params, "snapshot2")
        twin1_state = self._p(params, "twin1_state", {})
        twin2_state = self._p(params, "twin2_state", {})
        if snapshot1 and snapshot2:
            res1 = self.ImportSnapshot({"import_path": snapshot1, "target_db": ":memory:"})
            if res1[0] != 1:
                return res1
            twin1_state = res1[1].get("row_counts", {})
            res2 = self.ImportSnapshot({"import_path": snapshot2, "target_db": ":memory:"})
            if res2[0] != 1:
                return res2
            twin2_state = res2[1].get("row_counts", {})
        diffs = []
        all_keys = set(list(twin1_state.keys()) + list(twin2_state.keys()))
        for key in sorted(all_keys):
            v1 = twin1_state.get(key)
            v2 = twin2_state.get(key)
            if v1 != v2:
                diffs.append({"key": key, "twin1": v1, "twin2": v2, "delta": (v2 - v1) if isinstance(v1, int) and isinstance(v2, int) else None})
        total_keys = len(all_keys) if all_keys else 1
        similarity = max(0, round(100 - (len(diffs) / total_keys * 100), 1))
        result = {
            "differences": diffs,
            "difference_count": len(diffs),
            "similarity": similarity,
            "twin1_keys": len(twin1_state),
            "twin2_keys": len(twin2_state),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

