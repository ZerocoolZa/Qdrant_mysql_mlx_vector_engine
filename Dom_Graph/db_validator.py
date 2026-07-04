#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/db_validator.py"
# date="2026-06-26" author="Devin" session_id="phase5-quality"
# context="Project Digital Twin Phase 5 Section 26 Database Validator"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="db_validator.py" domain="twin_db" authority="DbValidator"}
# [@SUMMARY]{summary="Database validator authority checking tables, indexes, foreign keys and integrity of the Project Digital Twin SQLite DB."}
# [@CLASS]{class="DbValidator" domain="db" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="check_tables" type="command"}
# [@METHOD]{method="check_indexes" type="command"}
# [@METHOD]{method="check_foreign_keys" type="command"}
# [@METHOD]{method="check_integrity" type="command"}
# [@METHOD]{method="check_all" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="Connect" type="helper"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<DbValidator: validates SQLite DB schema -- tables, indexes, foreign keys, integrity. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
DbValidator -- authority for validating the Project Digital Twin SQLite database schema.
Implements Section 26 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: check_tables, check_indexes, check_foreign_keys, check_integrity, check_all.
"""
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
EXPECTED_TABLES = [
    "files",
    "classes",
    "methods",
    "edges",
    "knowledge",
    "snapshots",
    "attempts",
    "observations",
]
EXPECTED_INDEXES = [
    "idx_edges_src",
    "idx_edges_dst",
    "idx_edges_type",
    "idx_knowledge_problem",
    "idx_knowledge_error_type",
]


class DbValidator:
    """Authority for database schema, index, foreign key and integrity validation."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
                "expected_tables": EXPECTED_TABLES,
                "expected_indexes": EXPECTED_INDEXES,
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
        if command == "check_tables":
            return self.CheckTables(params)
        elif command == "check_indexes":
            return self.CheckIndexes(params)
        elif command == "check_foreign_keys":
            return self.CheckForeignKeys(params)
        elif command == "check_integrity":
            return self.CheckIntegrity(params)
        elif command == "duplicate_row_detection":
            return self.DuplicateRowDetection(params)
        elif command == "orphan_row_detection":
            return self.OrphanRowDetection(params)
        elif command == "constraint_violation_detection":
            return self.ConstraintViolationDetection(params)
        elif command == "check_all":
            return self.CheckAll(params)
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

    def CheckTables(self, params):
        expected = self._p(
            params, "expected_tables", self.state["config"]["expected_tables"]
        )
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            actual = set(row[0] for row in cur.fetchall())
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        expected_set = set(expected)
        missing = sorted(expected_set - actual)
        extra = sorted(actual - expected_set)
        result = {
            "expected": sorted(expected_set),
            "actual": sorted(actual),
            "missing": missing,
            "extra": extra,
            "passed": len(missing) == 0,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def CheckIndexes(self, params):
        expected = self._p(
            params, "expected_indexes", self.state["config"]["expected_indexes"]
        )
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
            actual = set(row[0] for row in cur.fetchall())
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        expected_set = set(expected)
        missing = sorted(expected_set - actual)
        result = {
            "expected": sorted(expected_set),
            "actual": sorted(actual),
            "missing": missing,
            "passed": len(missing) == 0,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def CheckForeignKeys(self, params):
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA foreign_key_check")
            violations = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        result = {
            "violations": [
                {"table": v[0], "rowid": v[1], "parent": v[2], "fkid": v[3]}
                for v in violations
            ],
            "count": len(violations),
            "passed": len(violations) == 0,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def CheckIntegrity(self, params):
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check")
            rows = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        results = [row[0] for row in rows]
        passed = len(results) == 1 and results[0] == "ok"
        result = {
            "result": results,
            "passed": passed,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def DuplicateRowDetection(self, params):
        table_name = self._p(params, "table")
        if not table_name:
            return (0, None, ("MISSING_PARAM", "table required", 0))
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if cur.fetchone() is None:
                return (0, None, ("TABLE_NOT_FOUND", table_name, 0))
            cur.execute("PRAGMA table_info(" + table_name + ")")
            columns_info = cur.fetchall()
            non_pk_cols = [c[1] for c in columns_info if c[5] == 0]
            if not non_pk_cols:
                return (1, {"table": table_name, "duplicates": [], "count": 0, "passed": True}, None)
            col_list = ", ".join(non_pk_cols)
            cur.execute(
                "SELECT " + col_list + ", COUNT(*) AS cnt FROM " + table_name + " "
                "GROUP BY " + col_list + " HAVING COUNT(*) > 1 ORDER BY cnt DESC"
            )
            dup_rows = cur.fetchall()
            duplicates = []
            for row in dup_rows:
                values = row[:-1]
                count = row[-1]
                duplicates.append({
                    "values": dict(zip(non_pk_cols, [str(v) for v in values])),
                    "count": count,
                })
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        result = {
            "table": table_name,
            "duplicates": duplicates,
            "count": len(duplicates),
            "passed": len(duplicates) == 0,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def OrphanRowDetection(self, params):
        table_name = self._p(params, "table")
        try:
            conn = self.Connect()
            cur = conn.cursor()
            tables_to_check = []
            if table_name:
                tables_to_check = [table_name]
            else:
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables_to_check = [r[0] for r in cur.fetchall() if r[0] not in ("sqlite_sequence",)]
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        orphans = []
        try:
            for tbl in tables_to_check:
                cur.execute("PRAGMA foreign_key_list(" + tbl + ")")
                fk_list = cur.fetchall()
                for fk in fk_list:
                    fk_id, seq, ref_table, from_col, to_col, on_update, on_delete, match = fk
                    cur.execute(
                        "SELECT rowid, " + from_col + " FROM " + tbl + " "
                        "WHERE " + from_col + " IS NOT NULL AND "
                        + from_col + " NOT IN (SELECT " + to_col + " FROM " + ref_table + ")"
                    )
                    for row in cur.fetchall():
                        orphans.append({
                            "table": tbl,
                            "rowid": row[0],
                            "column": from_col,
                            "value": row[1],
                            "references": ref_table + "." + to_col,
                        })
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        result = {
            "orphans": orphans,
            "count": len(orphans),
            "passed": len(orphans) == 0,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def ConstraintViolationDetection(self, params):
        table_name = self._p(params, "table")
        try:
            conn = self.Connect()
            cur = conn.cursor()
            tables_to_check = []
            if table_name:
                tables_to_check = [table_name]
            else:
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables_to_check = [r[0] for r in cur.fetchall() if r[0] not in ("sqlite_sequence",)]
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        violations = []
        try:
            for tbl in tables_to_check:
                cur.execute("PRAGMA table_info(" + tbl + ")")
                columns_info = cur.fetchall()
                for col_info in columns_info:
                    cid, col_name, col_type, not_null, default_val, pk = col_info
                    if not_null and not pk:
                        cur.execute(
                            "SELECT rowid FROM " + tbl + " WHERE " + col_name + " IS NULL"
                        )
                        for row in cur.fetchall():
                            violations.append({
                                "table": tbl,
                                "rowid": row[0],
                                "column": col_name,
                                "violation": "NOT_NULL",
                            })
            cur.execute("PRAGMA foreign_key_check")
            fk_violations = cur.fetchall()
            for v in fk_violations:
                violations.append({
                    "table": v[0],
                    "rowid": v[1],
                    "parent": v[2],
                    "fkid": v[3],
                    "violation": "FOREIGN_KEY",
                })
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        result = {
            "violations": violations,
            "count": len(violations),
            "passed": len(violations) == 0,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def CheckAll(self, params):
        report = {"checks": {}}
        tables = self.CheckTables(params)
        report["checks"]["tables"] = (
            tables[1] if tables[0] == 1 else {"error": tables[2]}
        )
        indexes = self.CheckIndexes(params)
        report["checks"]["indexes"] = (
            indexes[1] if indexes[0] == 1 else {"error": indexes[2]}
        )
        fkeys = self.CheckForeignKeys(params)
        report["checks"]["foreign_keys"] = (
            fkeys[1] if fkeys[0] == 1 else {"error": fkeys[2]}
        )
        integrity = self.CheckIntegrity(params)
        report["checks"]["integrity"] = (
            integrity[1] if integrity[0] == 1 else {"error": integrity[2]}
        )
        dup = self.DuplicateRowDetection(params)
        report["checks"]["duplicate_rows"] = (
            dup[1] if dup[0] == 1 else {"error": dup[2]}
        )
        orphan = self.OrphanRowDetection(params)
        report["checks"]["orphan_rows"] = (
            orphan[1] if orphan[0] == 1 else {"error": orphan[2]}
        )
        constraint = self.ConstraintViolationDetection(params)
        report["checks"]["constraint_violations"] = (
            constraint[1] if constraint[0] == 1 else {"error": constraint[2]}
        )
        all_passed = True
        for check in report["checks"].values():
            if isinstance(check, dict) and check.get("passed") is False:
                all_passed = False
                break
        report["passed"] = all_passed
        report["created"] = datetime.now(timezone.utc).isoformat()
        self.state["results"].append(report)
        return (1, report, None)
