#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/sandbox_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 2: Sandbox Phase (In-RAM SQLite) -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="sandbox_engine.py" domain="twin_sandbox" authority="SandboxEngine"}
# [@SUMMARY]{summary="Sandbox authority: load backup into RAM SQLite, verify schema/counts/FK/indexes/constraints, enable rollback, snapshot before experiment, auto restore after failure, never touch original."}
# [@CLASS]{class="SandboxEngine" domain="sandbox" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="load" type="command"}
# [@METHOD]{method="verify_schema" type="command"}
# [@METHOD]{method="verify_counts" type="command"}
# [@METHOD]{method="verify_foreign_keys" type="command"}
# [@METHOD]{method="verify_indexes" type="command"}
# [@METHOD]{method="verify_constraints" type="command"}
# [@METHOD]{method="enable_rollback" type="command"}
# [@METHOD]{method="snapshot" type="command"}
# [@METHOD]{method="auto_restore" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"
EXPECTED_TWIN_TABLES = [
    "files", "classes", "methods", "edges",
    "knowledge", "snapshots", "attempts", "observations",
]


class SandboxEngine:
    """Authority for in-memory SQLite sandbox experiments with rollback."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "expected_tables": list(EXPECTED_TWIN_TABLES),
            },
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
            "in_transaction": False,
            "loaded": False,
            "source_path": None,
            "snapshots": [],
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "load_ram":
            return self.LoadRam(params)
        elif command == "verify_schema":
            return self.VerifySchema(params)
        elif command == "verify_counts":
            return self.VerifyCounts(params)
        elif command == "verify_foreign_keys":
            return self.VerifyForeignKeys(params)
        elif command == "verify_indexes":
            return self.VerifyIndexes(params)
        elif command == "verify_constraints":
            return self.VerifyConstraints(params)
        elif command == "enable_rollback":
            return self.EnableRollback(params)
        elif command == "snapshot_before":
            return self.SnapshotBefore(params)
        elif command == "auto_restore":
            return self.AutoRestore(params)
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

    def Now(self):
        return (1, datetime.now(timezone.utc).isoformat(), None)

    def LoadRam(self, params):
        source = self._p(params, "source_path", self.state["config"]["db_path"])
        if not os.path.isfile(source):
            return (0, None, ("SOURCE_NOT_FOUND", source, 0))
        try:
            disk = sqlite3.connect(source)
            mem = sqlite3.connect(":memory:")
            disk.row_factory = sqlite3.Row
            cur_disk = disk.cursor()
            cur_disk.execute(
                "SELECT type, name, sql FROM sqlite_master "
                "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'"
            )
            schema_rows = cur_disk.fetchall()
            cur_mem = mem.cursor()
            for row in schema_rows:
                cur_mem.execute(row["sql"])
            cur_disk.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
            table_names = [r["name"] for r in cur_disk.fetchall()]
            for table in table_names:
                cur_disk.execute("SELECT * FROM " + table)
                rows = cur_disk.fetchall()
                if not rows:
                    continue
                cols = [d[0] for d in cur_disk.description]
                placeholders = ", ".join(["?"] * len(cols))
                col_list = ", ".join(cols)
                cur_mem.execute("DELETE FROM " + table)
                cur_mem.executemany(
                    "INSERT INTO " + table + " (" + col_list + ") VALUES (" + placeholders + ")",
                    [tuple(r) for r in rows],
                )
            mem.commit()
            disk.close()
        except sqlite3.Error as exc:
            return (0, None, ("LOAD_FAILED", str(exc), 0))
        self.state["db_conn"] = mem
        self.state["loaded"] = True
        self.state["source_path"] = source
        self.state["in_transaction"] = False
        record = {"source": source, "tables_loaded": len(table_names),
                  "loaded_at": self.Now()[1]}
        self.state["catalog"].append(record)
        return (1, record, None)

    def VerifySchema(self, params):
        conn = self._p(params, "conn", self.state["db_conn"])
        if conn is None:
            return (0, None, ("NOT_LOADED", "Call load first", 0))
        expected = self._p(params, "expected_tables",
                           self.state["config"]["expected_tables"])
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            actual = {r[0] for r in cur.fetchall()}
            missing = [t for t in expected if t not in actual]
        except sqlite3.Error as exc:
            return (0, None, ("SCHEMA_QUERY_FAILED", str(exc), 0))
        record = {"expected": list(expected), "actual": list(actual),
                  "missing": missing, "ok": not missing}
        self.state["results"] = record
        return (1, record, None)

    def VerifyCounts(self, params):
        conn = self._p(params, "conn", self.state["db_conn"])
        if conn is None:
            return (0, None, ("NOT_LOADED", "Call load first", 0))
        expected = self._p(params, "expected_tables",
                           self.state["config"]["expected_tables"])
        try:
            cur = conn.cursor()
            counts = {}
            for table in expected:
                cur.execute("SELECT COUNT(*) FROM " + table)
                counts[table] = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("COUNT_FAILED", str(exc), 0))
        record = {"counts": counts}
        self.state["results"] = record
        return (1, record, None)

    def VerifyForeignKeys(self, params):
        conn = self._p(params, "conn", self.state["db_conn"])
        if conn is None:
            return (0, None, ("NOT_LOADED", "Call load first", 0))
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_key_check")
            violations = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("FK_CHECK_FAILED", str(exc), 0))
        record = {"violations": len(violations), "ok": len(violations) == 0}
        self.state["results"] = record
        return (1, record, None)

    def VerifyIndexes(self, params):
        conn = self._p(params, "conn", self.state["db_conn"])
        if conn is None:
            return (0, None, ("NOT_LOADED", "Call load first", 0))
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT name, tbl_name FROM sqlite_master "
                "WHERE type='index' AND name NOT LIKE 'sqlite_%'"
            )
            indexes = [{"name": r[0], "table": r[1]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("INDEX_QUERY_FAILED", str(exc), 0))
        record = {"indexes": indexes, "count": len(indexes)}
        self.state["results"] = record
        return (1, record, None)

    def VerifyConstraints(self, params):
        conn = self._p(params, "conn", self.state["db_conn"])
        if conn is None:
            return (0, None, ("NOT_LOADED", "Call load first", 0))
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check")
            integrity = cur.fetchone()[0]
            cur.execute("PRAGMA foreign_key_check")
            fk_violations = cur.fetchall()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
            tables = []
            for row in cur.fetchall():
                tname = row[0]
                cur.execute("PRAGMA table_info(" + tname + ")")
                cols = [{"name": c[1], "type": c[2], "notnull": c[3],
                         "default": c[4], "pk": c[5]}
                        for c in cur.fetchall()]
                tables.append({"table": tname, "columns": cols})
        except sqlite3.Error as exc:
            return (0, None, ("CONSTRAINT_QUERY_FAILED", str(exc), 0))
        record = {"integrity": integrity,
                  "foreign_key_violations": len(fk_violations),
                  "tables": tables}
        self.state["results"] = record
        return (1, record, None)

    def EnableRollback(self, params):
        conn = self._p(params, "conn", self.state["db_conn"])
        if conn is None:
            return (0, None, ("NOT_LOADED", "Call load first", 0))
        if self.state["in_transaction"]:
            return (0, None, ("ALREADY_IN_TRANSACTION", "Commit or rollback first", 0))
        try:
            conn.execute("BEGIN TRANSACTION")
        except sqlite3.Error as exc:
            return (0, None, ("BEGIN_FAILED", str(exc), 0))
        self.state["in_transaction"] = True
        record = {"rollback_enabled": True, "started": self.Now()[1]}
        self.state["catalog"].append(record)
        return (1, record, None)

    def SnapshotBefore(self, params):
        conn = self._p(params, "conn", self.state["db_conn"])
        if conn is None:
            return (0, None, ("NOT_LOADED", "Call load first", 0))
        label = self._p(params, "label", "pre_experiment")
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
            table_names = [r[0] for r in cur.fetchall()]
            data = {}
            for table in table_names:
                cur.execute("SELECT * FROM " + table)
                data[table] = [tuple(r) for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("SNAPSHOT_FAILED", str(exc), 0))
        snapshot = {"label": label, "data": data, "created": self.Now()[1]}
        self.state["snapshots"].append(snapshot)
        return (1, {"label": label, "tables": len(data)}, None)

    def AutoRestore(self, params):
        conn = self._p(params, "conn", self.state["db_conn"])
        if conn is None:
            return (0, None, ("NOT_LOADED", "Call load first", 0))
        snapshots = self.state.get("snapshots", [])
        if not snapshots:
            return (0, None, ("NO_SNAPSHOT", "No snapshot to restore", 0))
        snapshot = snapshots[-1]
        try:
            cur = conn.cursor()
            for table, rows in snapshot["data"].items():
                cur.execute("DELETE FROM " + table)
                if rows:
                    cur.execute("PRAGMA table_info(" + table + ")")
                    cols = [c[1] for c in cur.fetchall()]
                    placeholders = ", ".join(["?"] * len(cols))
                    col_list = ", ".join(cols)
                    cur.executemany(
                        "INSERT INTO " + table + " (" + col_list + ") "
                        "VALUES (" + placeholders + ")",
                        rows,
                    )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("RESTORE_FAILED", str(exc), 0))
        return (1, {"restored_from": snapshot["label"],
                    "tables": len(snapshot["data"])}, None)
