#!/usr/bin/env python3
#[@GHOST]{[@file<exec_planner_maintenance.py>][@state<active>][@date<2026-07-01>][@ver<1.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<exec_planner_maintenance>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}

import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_EXECUTION_PLANNER = """
CREATE TABLE IF NOT EXISTS execution_units (
    unit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_name    TEXT NOT NULL UNIQUE,
    method_ids   TEXT NOT NULL,
    method_names TEXT NOT NULL,
    description  TEXT,
    ast_fingerprint TEXT,
    created_at   REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS unit_deps (
    unit_id      INTEGER NOT NULL,
    depends_on   INTEGER NOT NULL,
    dep_type     TEXT DEFAULT 'call',
    FOREIGN KEY (unit_id) REFERENCES execution_units(unit_id),
    FOREIGN KEY (depends_on) REFERENCES execution_units(unit_id)
);
CREATE INDEX IF NOT EXISTS idx_ud_unit ON unit_deps(unit_id);
CREATE INDEX IF NOT EXISTS idx_ud_dep ON unit_deps(depends_on);

CREATE TABLE IF NOT EXISTS execution_plans (
    plan_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_name    TEXT NOT NULL UNIQUE,
    unit_names   TEXT NOT NULL,
    step_order   TEXT NOT NULL,
    description  TEXT,
    created_at   REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS execution_log (
    log_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_name    TEXT NOT NULL,
    step_index   INTEGER NOT NULL,
    unit_name    TEXT NOT NULL,
    status       TEXT NOT NULL,
    duration_ms  REAL,
    result_json  TEXT,
    error_msg    TEXT,
    timestamp    REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_el_plan ON execution_log(plan_name);

CREATE TABLE IF NOT EXISTS state_snapshots (
    snapshot_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_name    TEXT NOT NULL,
    step_index   INTEGER NOT NULL,
    state_json   TEXT NOT NULL,
    timestamp    REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_ss_plan ON state_snapshots(plan_name);

CREATE TABLE IF NOT EXISTS conflicts (
    conflict_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_a       TEXT NOT NULL,
    unit_b       TEXT NOT NULL,
    conflict_type TEXT NOT NULL,
    detail       TEXT,
    severity     TEXT DEFAULT 'error',
    resolved     INTEGER DEFAULT 0
);
"""

SCHEMA_META = """
CREATE TABLE IF NOT EXISTS _meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

INDEX_DEFINITIONS = [
    "idx_eu_name ON execution_units(unit_name)",
    "idx_eu_fp ON execution_units(ast_fingerprint)",
    "idx_conf_a ON conflicts(unit_a)",
    "idx_conf_b ON conflicts(unit_b)",
    "idx_el_status ON execution_log(status)",
    "idx_el_time ON execution_log(timestamp)",
    "idx_ss_time ON state_snapshots(timestamp)",
]


class ExecPlannerMaintenance:
    # [@CLASSES]{[@class<ExecPlannerMaintenance>][@domain<exec_planner_maintenance>][@orch<Dom_Db>]}

    DEFAULT_DB_PATH = "/tmp/execution_planner.sqlite"
    DEFAULT_MAX_AGE_DAYS = 30
    SCHEMA_VERSION = 2

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": self.DEFAULT_DB_PATH,
                "max_age_days": self.DEFAULT_MAX_AGE_DAYS,
            },
            "catalog": {
                "commands": [
                    "add_indexes",
                    "enable_foreign_keys",
                    "cleanup_old_logs",
                    "cleanup_plan",
                    "vacuum",
                    "integrity_check",
                    "table_stats",
                    "migrate_schema",
                    "export_db",
                    "import_db",
                    "health_check",
                    "optimize",
                ],
            },
            "results": {},
            "mem": mem,
            "db": db,
            "param": param,
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        if not isinstance(params, dict):
            return default
        return params.get(key, default)

    def set_config(self, config):
        if not isinstance(config, dict):
            return (0, None, (1, "config must be dict", 0))
        self.state["config"].update(config)
        return (1, {"config": self.state["config"]}, None)

    def read_state(self):
        return (1, {"config": dict(self.state["config"]),
                    "catalog": dict(self.state["catalog"]),
                    "results": dict(self.state["results"])}, None)

    def Run(self, command, params=None):
        dispatch = {
            "add_indexes": self.add_indexes,
            "enable_foreign_keys": self.enable_foreign_keys,
            "cleanup_old_logs": self.cleanup_old_logs,
            "cleanup_plan": self.cleanup_plan,
            "vacuum": self.vacuum,
            "integrity_check": self.integrity_check,
            "table_stats": self.table_stats,
            "migrate_schema": self.migrate_schema,
            "export_db": self.export_db,
            "import_db": self.import_db,
            "health_check": self.health_check,
            "optimize": self.optimize,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (1, "unknown command: " + str(command), 0))
        try:
            return handler(params)
        except Exception as exc:
            return (0, None, (2, "command failed: " + str(exc), 0))

    def _db_path(self, params):
        path = self._p(params, "db_path", self.state["config"].get("db_path", self.DEFAULT_DB_PATH))
        if not path:
            path = self.DEFAULT_DB_PATH
        return path

    def _connect(self, params):
        path = self._db_path(params)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn, path

    def _ensure_schema(self, conn):
        conn.executescript(SCHEMA_EXECUTION_PLANNER)
        conn.commit()

    def add_indexes(self, params):
        # [@METHOD]{[@name<add_indexes>][@return<Tuple3>]}
        conn, path = self._connect(params)
        try:
            self._ensure_schema(conn)
            added = 0
            for idx_def in INDEX_DEFINITIONS:
                idx_name = idx_def.split(" ")[0]
                cur = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                    (idx_name,),
                )
                existed = cur.fetchone() is not None
                conn.execute("CREATE INDEX IF NOT EXISTS " + idx_def)
                if not existed:
                    added += 1
            conn.commit()
            return (1, {"indexes_added": added, "db_path": path}, None)
        finally:
            conn.close()

    def enable_foreign_keys(self, params):
        # [@METHOD]{[@name<enable_foreign_keys>][@return<Tuple3>]}
        conn, path = self._connect(params)
        try:
            cur = conn.execute("PRAGMA foreign_keys")
            row = cur.fetchone()
            was_enabled = bool(row[0]) if row else False
            conn.execute("PRAGMA foreign_keys = ON")
            cur2 = conn.execute("PRAGMA foreign_keys")
            row2 = cur2.fetchone()
            now_enabled = bool(row2[0]) if row2 else False
            return (1, {"foreign_keys_enabled": now_enabled,
                        "was_enabled": was_enabled,
                        "db_path": path}, None)
        finally:
            conn.close()

    def cleanup_old_logs(self, params):
        # [@METHOD]{[@name<cleanup_old_logs>][@return<Tuple3>]}
        max_age = self._p(params, "max_age_days", self.DEFAULT_MAX_AGE_DAYS)
        cutoff = time.time() - (max_age * 86400.0)
        conn, path = self._connect(params)
        try:
            self._ensure_schema(conn)
            cur1 = conn.execute(
                "DELETE FROM execution_log WHERE timestamp < ?",
                (cutoff,),
            )
            logs_deleted = cur1.rowcount
            cur2 = conn.execute(
                "DELETE FROM state_snapshots WHERE timestamp < ?",
                (cutoff,),
            )
            snapshots_deleted = cur2.rowcount
            conn.commit()
            return (1, {"logs_deleted": logs_deleted,
                        "snapshots_deleted": snapshots_deleted,
                        "db_path": path}, None)
        finally:
            conn.close()

    def cleanup_plan(self, params):
        # [@METHOD]{[@name<cleanup_plan>][@return<Tuple3>]}
        plan_name = self._p(params, "plan_name")
        if not plan_name:
            return (0, None, (1, "plan_name required", 0))
        conn, path = self._connect(params)
        try:
            self._ensure_schema(conn)
            cur1 = conn.execute(
                "DELETE FROM execution_log WHERE plan_name = ?",
                (plan_name,),
            )
            logs_deleted = cur1.rowcount
            cur2 = conn.execute(
                "DELETE FROM state_snapshots WHERE plan_name = ?",
                (plan_name,),
            )
            snapshots_deleted = cur2.rowcount
            cur3 = conn.execute(
                "DELETE FROM execution_plans WHERE plan_name = ?",
                (plan_name,),
            )
            plan_deleted = cur3.rowcount > 0
            conn.commit()
            return (1, {"deleted": {"logs": logs_deleted,
                                     "snapshots": snapshots_deleted,
                                     "plan": plan_deleted},
                        "db_path": path}, None)
        finally:
            conn.close()

    def vacuum(self, params):
        # [@METHOD]{[@name<vacuum>][@return<Tuple3>]}
        path = self._db_path(params)
        conn = sqlite3.connect(path)
        try:
            conn.execute("VACUUM")
            return (1, {"vacuumed": True, "db_path": path}, None)
        finally:
            conn.close()

    def integrity_check(self, params):
        # [@METHOD]{[@name<integrity_check>][@return<Tuple3>]}
        conn, path = self._connect(params)
        try:
            cur1 = conn.execute("PRAGMA integrity_check")
            rows = cur1.fetchall()
            integrity = "ok"
            for row in rows:
                val = row[0] if not isinstance(row, dict) else row.get("integrity_check")
                if str(val).lower() != "ok":
                    integrity = "corrupt"
                    break
            cur2 = conn.execute("PRAGMA foreign_key_check")
            fk_rows = cur2.fetchall()
            violations = []
            for row in fk_rows:
                violations.append(list(row))
            return (1, {"integrity": integrity,
                        "foreign_key_violations": violations,
                        "db_path": path}, None)
        finally:
            conn.close()

    def table_stats(self, params):
        # [@METHOD]{[@name<table_stats>][@return<Tuple3>]}
        conn, path = self._connect(params)
        try:
            self._ensure_schema(conn)
            def count_rows(table):
                cur = conn.execute("SELECT COUNT(*) FROM " + table)
                r = cur.fetchone()
                return int(r[0]) if r else 0

            def fetch_one(query, args=()):
                cur = conn.execute(query, args)
                r = cur.fetchone()
                if r is None:
                    return None
                return r[0]

            eu_count = count_rows("execution_units")
            ud_count = count_rows("unit_deps")
            ep_count = count_rows("execution_plans")
            el_count = count_rows("execution_log")
            ss_count = count_rows("state_snapshots")
            cf_count = count_rows("conflicts")

            el_oldest = fetch_one("SELECT MIN(timestamp) FROM execution_log")
            el_newest = fetch_one("SELECT MAX(timestamp) FROM execution_log")
            ss_oldest = fetch_one("SELECT MIN(timestamp) FROM state_snapshots")
            ss_newest = fetch_one("SELECT MAX(timestamp) FROM state_snapshots")
            cf_unresolved = fetch_one(
                "SELECT COUNT(*) FROM conflicts WHERE resolved = 0"
            )

            tables = {
                "execution_units": {"count": eu_count},
                "unit_deps": {"count": ud_count},
                "execution_plans": {"count": ep_count},
                "execution_log": {
                    "count": el_count,
                    "oldest_entry": el_oldest,
                    "newest_entry": el_newest,
                },
                "state_snapshots": {
                    "count": ss_count,
                    "oldest_entry": ss_oldest,
                    "newest_entry": ss_newest,
                },
                "conflicts": {
                    "count": cf_count,
                    "unresolved_count": int(cf_unresolved or 0),
                },
            }

            page_size_cur = conn.execute("PRAGMA page_size")
            ps_row = page_size_cur.fetchone()
            page_size = int(ps_row[0]) if ps_row else 0
            page_count_cur = conn.execute("PRAGMA page_count")
            pc_row = page_count_cur.fetchone()
            page_count = int(pc_row[0]) if pc_row else 0
            total_size = page_size * page_count
            tables["execution_units"]["total_size_bytes"] = total_size

            return (1, {"tables": tables,
                        "total_size_bytes": total_size,
                        "db_path": path}, None)
        finally:
            conn.close()

    def _get_schema_version(self, conn):
        conn.executescript(SCHEMA_META)
        cur = conn.execute("SELECT value FROM _meta WHERE key = 'schema_version'")
        row = cur.fetchone()
        if row is None:
            return 0
        try:
            return int(row[0])
        except (TypeError, ValueError):
            return 0

    def _set_schema_version(self, conn, version):
        conn.executescript(SCHEMA_META)
        conn.execute(
            "INSERT INTO _meta(key, value) VALUES('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(version),),
        )
        conn.commit()

    def migrate_schema(self, params):
        # [@METHOD]{[@name<migrate_schema>][@return<Tuple3>]}
        target = self._p(params, "target_version", self.SCHEMA_VERSION)
        conn, path = self._connect(params)
        try:
            self._ensure_schema(conn)
            current = self._get_schema_version(conn)
            migrated = False
            if current < 2 and target >= 2:
                for idx_def in INDEX_DEFINITIONS:
                    conn.execute("CREATE INDEX IF NOT EXISTS " + idx_def)
                cols_cur = conn.execute("PRAGMA table_info(execution_units)")
                cols = [r[1] for r in cols_cur.fetchall()]
                if "created_at" not in cols:
                    conn.execute(
                        "ALTER TABLE execution_units ADD COLUMN created_at REAL DEFAULT 0"
                    )
                cols_cur2 = conn.execute("PRAGMA table_info(execution_plans)")
                cols2 = [r[1] for r in cols_cur2.fetchall()]
                if "created_at" not in cols2:
                    conn.execute(
                        "ALTER TABLE execution_plans ADD COLUMN created_at REAL DEFAULT 0"
                    )
                conn.execute("PRAGMA foreign_keys = ON")
                self._set_schema_version(conn, 2)
                current = 2
                migrated = True
            if current < target:
                self._set_schema_version(conn, target)
                current = target
                migrated = True
            return (1, {"migrated": migrated,
                        "from_version": current if not migrated else (current if current == target else current),
                        "to_version": target,
                        "db_path": path}, None)
        finally:
            conn.close()

    def export_db(self, params):
        # [@METHOD]{[@name<export_db>][@return<Tuple3>]}
        output_path = self._p(params, "output_path")
        if not output_path:
            return (0, None, (1, "output_path required", 0))
        conn, path = self._connect(params)
        try:
            self._ensure_schema(conn)
            data = {"schema_version": self.SCHEMA_VERSION, "tables": {}}

            def dump(table):
                cur = conn.execute("SELECT * FROM " + table)
                rows = cur.fetchall()
                out = []
                for row in rows:
                    out.append({k: row[k] for k in row.keys()})
                return out

            data["tables"]["execution_units"] = dump("execution_units")
            data["tables"]["unit_deps"] = dump("unit_deps")
            data["tables"]["execution_plans"] = dump("execution_plans")
            data["tables"]["execution_log"] = dump("execution_log")
            data["tables"]["state_snapshots"] = dump("state_snapshots")
            data["tables"]["conflicts"] = dump("conflicts")

            with open(output_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, default=str)
            size = os.path.getsize(output_path)
            return (1, {"exported": True,
                        "output_path": output_path,
                        "size_bytes": size,
                        "db_path": path}, None)
        finally:
            conn.close()

    def import_db(self, params):
        # [@METHOD]{[@name<import_db>][@return<Tuple3>]}
        json_path = self._p(params, "json_path")
        if not json_path:
            return (0, None, (1, "json_path required", 0))
        if not os.path.exists(json_path):
            return (0, None, (2, "json file not found: " + json_path, 0))
        path = self._db_path(params)
        if os.path.exists(path):
            return (0, None, (3, "target db exists, refusing overwrite: " + path, 0))
        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            conn.executescript(SCHEMA_EXECUTION_PLANNER)
            conn.executescript(SCHEMA_META)
            tables = data.get("tables", {})

            def insert_rows(table_name, rows):
                if not rows:
                    return 0
                cols = list(rows[0].keys())
                placeholders = ",".join(["?"] * len(cols))
                col_list = ",".join(cols)
                sql = "INSERT INTO " + table_name + " (" + col_list + ") VALUES (" + placeholders + ")"
                count = 0
                for row in rows:
                    conn.execute(sql, tuple(row.get(c) for c in cols))
                    count += 1
                return count

            units_n = insert_rows("execution_units", tables.get("execution_units", []))
            deps_n = insert_rows("unit_deps", tables.get("unit_deps", []))
            plans_n = insert_rows("execution_plans", tables.get("execution_plans", []))
            logs_n = insert_rows("execution_log", tables.get("execution_log", []))
            snaps_n = insert_rows("state_snapshots", tables.get("state_snapshots", []))
            confs_n = insert_rows("conflicts", tables.get("conflicts", []))
            sv = data.get("schema_version", self.SCHEMA_VERSION)
            self._set_schema_version(conn, sv)
            conn.commit()
            return (1, {"imported": {"units": units_n,
                                      "deps": deps_n,
                                      "plans": plans_n,
                                      "logs": logs_n,
                                      "snapshots": snaps_n,
                                      "conflicts": confs_n},
                        "db_path": path}, None)
        finally:
            conn.close()

    def health_check(self, params):
        # [@METHOD]{[@name<health_check>][@return<Tuple3>]}
        conn, path = self._connect(params)
        try:
            self._ensure_schema(conn)
            issues = []
            warnings = []

            cur1 = conn.execute("PRAGMA integrity_check")
            for row in cur1.fetchall():
                val = row[0]
                if str(val).lower() != "ok":
                    issues.append("integrity_check: " + str(val))

            cur2 = conn.execute("PRAGMA foreign_key_check")
            for row in cur2.fetchall():
                issues.append("foreign_key_violation: " + str(list(row)))

            cur3 = conn.execute(
                "SELECT ud.depends_on FROM unit_deps ud "
                "LEFT JOIN execution_units eu ON eu.unit_id = ud.depends_on "
                "WHERE eu.unit_id IS NULL"
            )
            for row in cur3.fetchall():
                issues.append("orphaned_unit_dep: depends_on=" + str(row[0]))

            cur4 = conn.execute(
                "SELECT ud.unit_id FROM unit_deps ud "
                "LEFT JOIN execution_units eu ON eu.unit_id = ud.unit_id "
                "WHERE eu.unit_id IS NULL"
            )
            for row in cur4.fetchall():
                issues.append("orphaned_unit_dep: unit_id=" + str(row[0]))

            cur5 = conn.execute("SELECT unit_names FROM execution_plans")
            for row in cur5.fetchall():
                names_raw = row[0]
                if not names_raw:
                    warnings.append("empty_plan_units: plan has empty unit_names")
                    continue
                try:
                    names = json.loads(names_raw)
                except (ValueError, TypeError):
                    names = [n.strip() for n in str(names_raw).split(",") if n.strip()]
                for name in names:
                    cur6 = conn.execute(
                        "SELECT unit_id FROM execution_units WHERE unit_name = ?",
                        (name,),
                    )
                    if cur6.fetchone() is None:
                        issues.append("plan_references_missing_unit: " + str(name))

            cur7 = conn.execute("SELECT plan_name FROM execution_plans")
            for row in cur7.fetchall():
                pn = row[0]
                cur8 = conn.execute(
                    "SELECT unit_names FROM execution_plans WHERE plan_name = ?",
                    (pn,),
                )
                r8 = cur8.fetchone()
                if r8 is None:
                    continue
                names_raw = r8[0]
                try:
                    names_list = json.loads(names_raw) if names_raw else []
                except (ValueError, TypeError):
                    names_list = [n.strip() for n in str(names_raw).split(",") if n.strip()]
                if not names_list:
                    warnings.append("empty_plan: " + str(pn))

            cur9 = conn.execute(
                "SELECT unit_name, method_ids FROM execution_units"
            )
            for row in cur9.fetchall():
                mid = row[1]
                if not mid or mid in ("[]", ""):
                    warnings.append("unit_no_methods: " + str(row[0]))

            healthy = len(issues) == 0
            return (1, {"healthy": healthy,
                        "issues": issues,
                        "warnings": warnings,
                        "db_path": path}, None)
        finally:
            conn.close()

    def optimize(self, params):
        # [@METHOD]{[@name<optimize>][@return<Tuple3>]}
        path = self._db_path(params)
        steps = []
        before_size = os.path.getsize(path) if os.path.exists(path) else 0

        ok, data, err = self.add_indexes(params)
        if not ok:
            return (0, None, err)
        steps.append("add_indexes")

        ok, data, err = self.enable_foreign_keys(params)
        if not ok:
            return (0, None, err)
        steps.append("enable_foreign_keys")

        ok, data, err = self.cleanup_old_logs(params)
        if not ok:
            return (0, None, err)
        steps.append("cleanup_old_logs")

        ok, data, err = self.vacuum(params)
        if not ok:
            return (0, None, err)
        steps.append("vacuum")

        ok, data, err = self.integrity_check(params)
        if not ok:
            return (0, None, err)
        steps.append("integrity_check")

        after_size = os.path.getsize(path) if os.path.exists(path) else 0
        reclaimed = before_size - after_size
        if reclaimed < 0:
            reclaimed = 0
        return (1, {"optimized": True,
                    "steps_completed": steps,
                    "space_reclaimed_bytes": reclaimed,
                    "db_path": path}, None)
