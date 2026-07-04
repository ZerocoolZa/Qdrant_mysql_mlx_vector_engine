#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/bcl_db.py"
# date="2026-08-18" author="Devin" session_id="bcl-ir-build"
# context="BCL_COMPILER_PLAN: MySQL persistence layer for IR + units + edges"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_db.py" domain="bcl_ir" authority="BclDb"}
# [@SUMMARY]{summary="MySQL persistence layer. Stores extracted IR (files, classes, methods, edges), computational units, and unit dependencies into MySQL tables. Enables diff, query, and cross-codebase analysis."}
# [@CLASS]{class="BclDb" domain="bcl_ir" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="InitSchema" type="command"}
# [@METHOD]{method="StoreAll" type="command"}
# [@METHOD]{method="StoreFile" type="command"}
# [@METHOD]{method="StoreClass" type="command"}
# [@METHOD]{method="StoreMethod" type="command"}
# [@METHOD]{method="StoreEdge" type="command"}
# [@METHOD]{method="StoreUnit" type="command"}
# [@METHOD]{method="StoreUnitDep" type="command"}
# [@METHOD]{method="QueryMethods" type="command"}
# [@METHOD]{method="QueryUnits" type="command"}
# [@METHOD]{method="QueryCodebase" type="command"}
# [@METHOD]{method="DiffCodebase" type="command"}
# [@METHOD]{method="DropCodebase" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
"""
BclDb -- MySQL persistence layer for the BCL pipeline.

Schema (database bcl_ir):
  bcl_codebases    -- one row per scanned codebase
  bcl_files        -- one row per .py file
  bcl_classes      -- one row per class
  bcl_methods      -- one row per method (with IR fields)
  bcl_edges        -- one row per IR edge (call/state/resource)
  bcl_units        -- one row per computational unit
  bcl_unit_deps    -- one row per unit-to-unit dependency
  bcl_unit_methods -- mapping table: which methods belong to which unit

Usage:
  db = BclDb(param={"db_name": "bcl_ir"})
  db.Run("init_schema", {})
  db.Run("store_all", {"extractor": ext, "partitioner": part, "codebase_name": "Dom_Graph"})
  db.Run("query_methods", {"codebase_name": "Dom_Graph", "method_type": "IO"})
  db.Run("diff_codebase", {"codebase_name": "Dom_Graph"})
"""
import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Tuple

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False


class BclDb:
    """MySQL persistence layer for IR + units + edges."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_host": "localhost",
                "db_user": "root",
                "db_password": "",
                "db_name": "vb_code_test",
            },
            "conn": None,
            "last_codebase_id": None,
            "stats": {
                "files_stored": 0,
                "classes_stored": 0,
                "methods_stored": 0,
                "edges_stored": 0,
                "units_stored": 0,
                "unit_deps_stored": 0,
            },
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "init_schema":
            return self.InitSchema(params)
        elif command == "store_all":
            return self.StoreAll(params)
        elif command == "query_methods":
            return self.QueryMethods(params)
        elif command == "query_units":
            return self.QueryUnits(params)
        elif command == "query_codebase":
            return self.QueryCodebase(params)
        elif command == "diff_codebase":
            return self.DiffCodebase(params)
        elif command == "drop_codebase":
            return self.DropCodebase(params)
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

    def _connect(self):
        if self.state["conn"] is not None:
            try:
                self.state["conn"].ping(reconnect=True, attempts=1, delay=0)
                return self.state["conn"]
            except Exception:
                self.state["conn"] = None
        cfg = self.state["config"]
        conn = mysql.connector.connect(
            user=cfg["db_user"],
            password=cfg["db_password"],
            host=cfg["db_host"],
            database=cfg["db_name"],
        )
        self.state["conn"] = conn
        return conn

    # ================================================================
    # SCHEMA INITIALIZATION
    # ================================================================

    def InitSchema(self, params):
        if not MYSQL_AVAILABLE:
            return (0, None, ("NO_MYSQL", "mysql.connector not available", 0))
        cfg = self.state["config"]
        conn = self._connect()
        cursor = conn.cursor()
        statements = [
            """CREATE TABLE IF NOT EXISTS bcl_codebases (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                root_path VARCHAR(1024),
                file_count INT DEFAULT 0,
                class_count INT DEFAULT 0,
                method_count INT DEFAULT 0,
                edge_count INT DEFAULT 0,
                unit_count INT DEFAULT 0,
                certain_edges INT DEFAULT 0,
                probable_edges INT DEFAULT 0,
                unknown_edges INT DEFAULT 0,
                io_count INT DEFAULT 0,
                core_count INT DEFAULT 0,
                link_count INT DEFAULT 0,
                init_count INT DEFAULT 0,
                cleanup_count INT DEFAULT 0,
                deterministic_subset_count INT DEFAULT 0,
                closed_units INT DEFAULT 0,
                open_units INT DEFAULT 0,
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS bcl_files (
                id INT AUTO_INCREMENT PRIMARY KEY,
                codebase_id INT NOT NULL,
                file_path VARCHAR(512) NOT NULL,
                file_name VARCHAR(255),
                file_hash VARCHAR(64),
                line_count INT DEFAULT 0,
                class_count INT DEFAULT 0,
                method_count INT DEFAULT 0,
                UNIQUE KEY uq_file (codebase_id, file_path),
                INDEX idx_codebase (codebase_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS bcl_classes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                codebase_id INT NOT NULL,
                class_name VARCHAR(255) NOT NULL,
                file_path VARCHAR(512),
                bases TEXT,
                method_count INT DEFAULT 0,
                line_start INT,
                line_end INT,
                source_class_id INT,
                UNIQUE KEY uq_class (codebase_id, class_name, file_path(255)),
                INDEX idx_codebase (codebase_id),
                INDEX idx_name (class_name),
                INDEX idx_source (source_class_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS bcl_methods (
                id INT AUTO_INCREMENT PRIMARY KEY,
                codebase_id INT NOT NULL,
                bcl_class_id INT,
                method_id VARCHAR(512) NOT NULL,
                method_id_hash VARCHAR(64) NOT NULL,
                method_name VARCHAR(255) NOT NULL,
                class_name VARCHAR(255),
                file_path VARCHAR(512),
                source_method_id INT,
                method_type VARCHAR(20),
                is_async TINYINT DEFAULT 0,
                is_deterministic_subset TINYINT DEFAULT 0,
                line_start INT,
                line_end INT,
                ast_hash VARCHAR(64),
                inputs TEXT,
                outputs TEXT,
                certain_count INT DEFAULT 0,
                probable_count INT DEFAULT 0,
                unknown_count INT DEFAULT 0,
                has_branching TINYINT DEFAULT 0,
                has_loops TINYINT DEFAULT 0,
                has_recursion TINYINT DEFAULT 0,
                throws_exceptions TINYINT DEFAULT 0,
                handles_exceptions TINYINT DEFAULT 0,
                mutates_global_state TINYINT DEFAULT 0,
                mutates_external TINYINT DEFAULT 0,
                UNIQUE KEY uq_method (codebase_id, method_id_hash),
                INDEX idx_codebase (codebase_id),
                INDEX idx_bcl_class (bcl_class_id),
                INDEX idx_type (method_type),
                INDEX idx_name (method_name),
                INDEX idx_class (class_name),
                INDEX idx_source (source_method_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS bcl_edges (
                id INT AUTO_INCREMENT PRIMARY KEY,
                codebase_id INT NOT NULL,
                bcl_method_id INT,
                source_method_id VARCHAR(512),
                source_method_row_id INT,
                target VARCHAR(512),
                target_method_row_id INT,
                edge_type VARCHAR(20) NOT NULL,
                certainty VARCHAR(10) NOT NULL,
                resolution VARCHAR(50),
                resource_type VARCHAR(20),
                line_number INT,
                INDEX idx_codebase (codebase_id),
                INDEX idx_bcl_method (bcl_method_id),
                INDEX idx_source (source_method_id(255)),
                INDEX idx_source_row (source_method_row_id),
                INDEX idx_target_row (target_method_row_id),
                INDEX idx_type (edge_type),
                INDEX idx_certainty (certainty)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS bcl_units (
                id INT AUTO_INCREMENT PRIMARY KEY,
                codebase_id INT NOT NULL,
                unit_id VARCHAR(100) NOT NULL,
                method_count INT DEFAULT 0,
                class_names TEXT,
                file_names TEXT,
                is_closed TINYINT DEFAULT 0,
                internal_calls INT DEFAULT 0,
                external_call_count INT DEFAULT 0,
                resources TEXT,
                state_keys TEXT,
                method_types_json TEXT,
                UNIQUE KEY uq_unit (codebase_id, unit_id),
                INDEX idx_codebase (codebase_id),
                INDEX idx_closed (is_closed)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS bcl_unit_methods (
                id INT AUTO_INCREMENT PRIMARY KEY,
                codebase_id INT NOT NULL,
                unit_id VARCHAR(100) NOT NULL,
                bcl_method_id INT,
                method_id VARCHAR(512),
                INDEX idx_codebase (codebase_id),
                INDEX idx_unit (unit_id),
                INDEX idx_bcl_method (bcl_method_id),
                INDEX idx_method (method_id(255))
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS bcl_unit_deps (
                id INT AUTO_INCREMENT PRIMARY KEY,
                codebase_id INT NOT NULL,
                source_unit_id VARCHAR(100) NOT NULL,
                target_unit_id VARCHAR(100) NOT NULL,
                UNIQUE KEY uq_dep (codebase_id, source_unit_id, target_unit_id),
                INDEX idx_codebase (codebase_id),
                INDEX idx_source (source_unit_id),
                INDEX idx_target (target_unit_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        ]
        for stmt in statements:
            cursor.execute(stmt)
        conn.commit()
        cursor.close()
        return (1, {"tables_created": len(statements), "db_name": cfg["db_name"]}, None)

    # ================================================================
    # STORE ALL (full pipeline persistence)
    # ================================================================

    def StoreAll(self, params):
        if not MYSQL_AVAILABLE:
            return (0, None, ("NO_MYSQL", "mysql.connector not available", 0))
        extractor = self._p(params, "extractor")
        partitioner = self._p(params, "partitioner")
        codebase_name = self._p(params, "codebase_name")
        if not extractor or not codebase_name:
            return (0, None, ("MISSING_PARAM", "extractor and codebase_name required", 0))
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM bcl_codebases WHERE name = %s", (codebase_name,))
        existing = cursor.fetchone()
        if existing:
            cb_id = existing[0]
            self._delete_codebase_data(cursor, cb_id)
        else:
            cursor.execute(
                "INSERT INTO bcl_codebases (name) VALUES (%s)", (codebase_name,)
            )
            cb_id = cursor.lastrowid
        self.state["last_codebase_id"] = cb_id
        self._store_files(cursor, cb_id, extractor)
        class_id_map = self._store_classes(cursor, cb_id, extractor)
        method_id_map = self._store_methods(cursor, cb_id, extractor, class_id_map)
        self._store_edges(cursor, cb_id, extractor, method_id_map)
        if partitioner:
            self._store_units(cursor, cb_id, partitioner, method_id_map)
            self._store_unit_deps(cursor, cb_id, partitioner)
        ir_report = extractor.Run("report", {})[1]
        unit_report = None
        if partitioner:
            unit_report = partitioner.Run("report", {})[1]
        self._update_codebase_stats(cursor, cb_id, ir_report, unit_report)
        conn.commit()
        cursor.close()
        s = self.state["stats"]
        return (1, {
            "codebase_id": cb_id,
            "codebase_name": codebase_name,
            "files": s["files_stored"],
            "classes": s["classes_stored"],
            "methods": s["methods_stored"],
            "edges": s["edges_stored"],
            "units": s["units_stored"],
            "unit_deps": s["unit_deps_stored"],
        }, None)

    def _delete_codebase_data(self, cursor, cb_id):
        for table in ("bcl_edges", "bcl_unit_methods", "bcl_unit_deps",
                      "bcl_units", "bcl_methods", "bcl_classes", "bcl_files"):
            cursor.execute("DELETE FROM " + table + " WHERE codebase_id = %s", (cb_id,))

    def _store_files(self, cursor, cb_id, extractor):
        count = 0
        for file_id, fdata in extractor.state["files"].items():
            cursor.execute(
                "INSERT INTO bcl_files (codebase_id, file_path, file_name, file_hash, "
                "line_count, class_count, method_count) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (cb_id, fdata["path"], fdata["path"].split("/")[-1],
                 fdata["hash"], fdata["line_count"],
                 len(fdata["classes"]), len(fdata["methods"]))
            )
            count += 1
        self.state["stats"]["files_stored"] = count

    def _store_classes(self, cursor, cb_id, extractor):
        count = 0
        class_id_map = {}
        cols = "(codebase_id, class_name, file_path, bases, method_count, line_start, line_end, source_class_id)"
        ordered_ids = list(extractor.state["classes"].keys())
        for class_id in ordered_ids:
            cdata = extractor.state["classes"][class_id]
            batch = [(
                cb_id, cdata["name"], cdata["file_id"][:512],
                ",".join(cdata["bases"]), len(cdata["methods"]),
                cdata["line_start"], cdata["line_end"],
                cdata.get("source_class_id")
            )]
            self._bulk_insert(cursor, "bcl_classes", cols, batch)
            class_id_map[class_id] = cursor.lastrowid
            count += 1
        self.state["stats"]["classes_stored"] = count
        return class_id_map

    def _store_methods(self, cursor, cb_id, extractor, class_id_map):
        count = 0
        method_id_map = {}
        cols = ("(codebase_id, bcl_class_id, method_id, method_id_hash, method_name, "
               "class_name, file_path, source_method_id, method_type, is_async, is_deterministic_subset, "
               "line_start, line_end, ast_hash, inputs, outputs, "
               "certain_count, probable_count, unknown_count, "
               "has_branching, has_loops, has_recursion, "
               "throws_exceptions, handles_exceptions, "
               "mutates_global_state, mutates_external)")
        ordered_ids = list(extractor.state["methods"].keys())
        BATCH_SIZE = 500
        for i in range(0, len(ordered_ids), BATCH_SIZE):
            chunk = ordered_ids[i:i+BATCH_SIZE]
            batch = []
            for mid in chunk:
                ir = extractor.state["methods"][mid]
                class_name = None
                if ir["class_id"] and "::" in ir["class_id"]:
                    class_name = ir["class_id"].split("::")[-1]
                cf = ir["control_flow"]
                ep = ir["exception_profile"]
                mp = ir["mutation_profile"]
                cs = ir["certainty_summary"]
                inputs_json = json.dumps(ir["inputs"])
                outputs_json = json.dumps(ir["outputs"])
                mid_hash = hashlib.sha256(mid.encode("utf-8")).hexdigest()[:16]
                bcl_class_id = class_id_map.get(ir["class_id"])
                batch.append((
                    cb_id, bcl_class_id, mid[:512], mid_hash, ir["name"], class_name,
                    ir["file_id"][:512] if ir["file_id"] else None,
                    ir.get("source_method_id"),
                    ir.get("method_type", "UNKNOWN"), ir["is_async"],
                    ir.get("deterministic_subset", False),
                    ir["line_start"], ir["line_end"], ir["ast_hash"],
                    inputs_json, outputs_json,
                    cs["certain_count"], cs["probable_count"], cs["unknown_count"],
                    cf["branching"], cf["loops"], cf["recursion"],
                    ep["throws_exceptions"], ep["handles_exceptions"],
                    mp["mutates_global_state"], mp["mutates_external"]
                ))
            self._bulk_insert(cursor, "bcl_methods", cols, batch)
            first_id = cursor.lastrowid
            for j, mid in enumerate(chunk):
                method_id_map[mid] = first_id + j
            count += len(batch)
        self.state["stats"]["methods_stored"] = count
        return method_id_map

    def _store_edges(self, cursor, cb_id, extractor, method_id_map):
        count = 0
        batch = []
        BATCH_SIZE = 2000
        cols = "(codebase_id, bcl_method_id, source_method_id, source_method_row_id, target, target_method_row_id, edge_type, certainty, resolution, resource_type, line_number)"
        for edge in extractor.state["edges"]:
            src_str = edge["source"]
            bcl_method_id = method_id_map.get(src_str)
            tgt_str = edge["target"]
            target_row_id = method_id_map.get(tgt_str)
            batch.append((
                cb_id, bcl_method_id,
                src_str[:512], edge.get("source_method_id"),
                tgt_str[:512], target_row_id,
                edge["edge_type"],
                edge["certainty"], edge.get("resolution", ""),
                edge.get("resource_type"), edge.get("line", 0)
            ))
            if len(batch) >= BATCH_SIZE:
                self._bulk_insert(cursor, "bcl_edges", cols, batch)
                count += len(batch)
                batch = []
        if batch:
            self._bulk_insert(cursor, "bcl_edges", cols, batch)
            count += len(batch)
        self.state["stats"]["edges_stored"] = count

    def _bulk_insert(self, cursor, table, columns, rows):
        placeholders = "(" + ",".join(["%s"] * len(rows[0])) + ")"
        values = ",".join([placeholders] * len(rows))
        flat = []
        for r in rows:
            flat.extend(r)
        sql = "INSERT INTO " + table + " " + columns + " VALUES " + values
        cursor.execute(sql, flat)

    def _store_units(self, cursor, cb_id, partitioner, method_id_map):
        count = 0
        unit_cols = "(codebase_id, unit_id, method_count, class_names, file_names, is_closed, internal_calls, external_call_count, resources, state_keys, method_types_json)"
        um_cols = "(codebase_id, unit_id, bcl_method_id, method_id)"
        unit_batch = []
        um_batch = []
        for unit_id, unit in partitioner.state["units"].items():
            class_names = ",".join(
                c.split("::")[-1] if "::" in c else c
                for c in unit["class_ids"]
            )
            file_names = ",".join(
                f.split("/")[-1] for f in unit["file_ids"]
            )
            unit_batch.append((
                cb_id, unit_id, unit["method_count"],
                class_names, file_names, unit["is_closed"],
                unit["internal_calls"], len(unit["external_calls"]),
                ",".join(unit["resources"]), ",".join(unit["state_keys"][:20]),
                json.dumps(unit["method_types"])
            ))
            for mid in unit["method_ids"]:
                bcl_method_id = method_id_map.get(mid)
                um_batch.append((cb_id, unit_id, bcl_method_id, mid[:512]))
            count += 1
            if len(unit_batch) >= 500:
                self._bulk_insert(cursor, "bcl_units", unit_cols, unit_batch)
                unit_batch = []
            if len(um_batch) >= 2000:
                self._bulk_insert(cursor, "bcl_unit_methods", um_cols, um_batch)
                um_batch = []
        if unit_batch:
            self._bulk_insert(cursor, "bcl_units", unit_cols, unit_batch)
        if um_batch:
            self._bulk_insert(cursor, "bcl_unit_methods", um_cols, um_batch)
        self.state["stats"]["units_stored"] = count

    def _store_unit_deps(self, cursor, cb_id, partitioner):
        count = 0
        batch = []
        cols = "(codebase_id, source_unit_id, target_unit_id)"
        for src_unit, targets in partitioner.state["unit_graph"].items():
            for tgt_unit in targets:
                batch.append((cb_id, src_unit, tgt_unit))
                if len(batch) >= 1000:
                    self._bulk_insert(cursor, "bcl_unit_deps", cols, batch)
                    count += len(batch)
                    batch = []
        if batch:
            self._bulk_insert(cursor, "bcl_unit_deps", cols, batch)
            count += len(batch)
        self.state["stats"]["unit_deps_stored"] = count

    def _update_codebase_stats(self, cursor, cb_id, ir_report, unit_report):
        ec = ir_report["edge_certainty"]
        mt = ir_report["method_types"]
        det = ir_report["deterministic_subset"]
        closed = 0
        open_u = 0
        if unit_report:
            closed = unit_report["closure"]["fully_closed"]
            open_u = unit_report["closure"]["with_external_calls"]
        cursor.execute(
            "UPDATE bcl_codebases SET root_path=%s, file_count=%s, class_count=%s, "
            "method_count=%s, edge_count=%s, unit_count=%s, "
            "certain_edges=%s, probable_edges=%s, unknown_edges=%s, "
            "io_count=%s, core_count=%s, link_count=%s, init_count=%s, cleanup_count=%s, "
            "deterministic_subset_count=%s, closed_units=%s, open_units=%s, "
            "scanned_at=NOW() WHERE id=%s",
            (ir_report.get("root_path", ""), ir_report["total_files"],
             ir_report["total_classes"], ir_report["total_methods"],
             ir_report["total_edges"],
             unit_report["total_units"] if unit_report else 0,
             ec["CERTAIN"], ec["PROBABLE"], ec["UNKNOWN"],
             mt.get("IO", 0), mt.get("CORE", 0), mt.get("LINK", 0),
             mt.get("INIT", 0), mt.get("CLEANUP", 0),
             det["count"], closed, open_u, cb_id)
        )

    # ================================================================
    # QUERIES
    # ================================================================

    def QueryCodebase(self, params):
        if not MYSQL_AVAILABLE:
            return (0, None, ("NO_MYSQL", "mysql.connector not available", 0))
        codebase_name = self._p(params, "codebase_name")
        if not codebase_name:
            return (0, None, ("MISSING_PARAM", "codebase_name required", 0))
        conn = self._connect()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM bcl_codebases WHERE name = %s", (codebase_name,))
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return (0, None, ("NOT_FOUND", "codebase " + codebase_name + " not found", 0))
        return (1, dict(row), None)

    def QueryMethods(self, params):
        if not MYSQL_AVAILABLE:
            return (0, None, ("NO_MYSQL", "mysql.connector not available", 0))
        codebase_name = self._p(params, "codebase_name")
        method_type = self._p(params, "method_type")
        class_name = self._p(params, "class_name")
        limit = self._p(params, "limit", 100)
        if not codebase_name:
            return (0, None, ("MISSING_PARAM", "codebase_name required", 0))
        conn = self._connect()
        cursor = conn.cursor(dictionary=True)
        sql = ("SELECT m.* FROM bcl_methods m "
               "JOIN bcl_codebases c ON m.codebase_id = c.id "
               "WHERE c.name = %s")
        args = [codebase_name]
        if method_type:
            sql += " AND m.method_type = %s"
            args.append(method_type)
        if class_name:
            sql += " AND m.class_name = %s"
            args.append(class_name)
        sql += " ORDER BY m.method_name LIMIT %s"
        args.append(limit)
        cursor.execute(sql, args)
        rows = cursor.fetchall()
        cursor.close()
        return (1, rows, None)

    def QueryUnits(self, params):
        if not MYSQL_AVAILABLE:
            return (0, None, ("NO_MYSQL", "mysql.connector not available", 0))
        codebase_name = self._p(params, "codebase_name")
        closed_only = self._p(params, "closed_only", False)
        min_size = self._p(params, "min_size", 0)
        limit = self._p(params, "limit", 100)
        if not codebase_name:
            return (0, None, ("MISSING_PARAM", "codebase_name required", 0))
        conn = self._connect()
        cursor = conn.cursor(dictionary=True)
        sql = ("SELECT u.* FROM bcl_units u "
               "JOIN bcl_codebases c ON u.codebase_id = c.id "
               "WHERE c.name = %s")
        args = [codebase_name]
        if closed_only:
            sql += " AND u.is_closed = 1"
        if min_size:
            sql += " AND u.method_count >= %s"
            args.append(min_size)
        sql += " ORDER BY u.method_count DESC LIMIT %s"
        args.append(limit)
        cursor.execute(sql, args)
        rows = cursor.fetchall()
        cursor.close()
        return (1, rows, None)

    def DiffCodebase(self, params):
        if not MYSQL_AVAILABLE:
            return (0, None, ("NO_MYSQL", "mysql.connector not available", 0))
        codebase_name = self._p(params, "codebase_name")
        extractor = self._p(params, "extractor")
        if not codebase_name or not extractor:
            return (0, None, ("MISSING_PARAM", "codebase_name and extractor required", 0))
        conn = self._connect()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM bcl_codebases WHERE name = %s", (codebase_name,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return (1, {"status": "NEW", "message": "codebase not in DB, nothing to diff"}, None)
        cb_id = row["id"]
        cursor.execute(
            "SELECT method_id, ast_hash, method_type FROM bcl_methods WHERE codebase_id = %s",
            (cb_id,)
        )
        db_methods = {r["method_id"]: r for r in cursor.fetchall()}
        cursor.close()
        current_methods = extractor.state["methods"]
        current_ids = set(current_methods.keys())
        db_ids = set(db_methods.keys())
        added = sorted(current_ids - db_ids)
        removed = sorted(db_ids - current_ids)
        changed = []
        type_changed = []
        for mid in current_ids & db_ids:
            curr = current_methods[mid]
            db_m = db_methods[mid]
            if curr["ast_hash"] != db_m["ast_hash"]:
                changed.append(mid)
            if curr.get("method_type") != db_m["method_type"]:
                type_changed.append({
                    "method_id": mid,
                    "old_type": db_m["method_type"],
                    "new_type": curr.get("method_type"),
                })
        return (1, {
            "codebase_name": codebase_name,
            "added_count": len(added),
            "removed_count": len(removed),
            "changed_count": len(changed),
            "type_changed_count": len(type_changed),
            "added_sample": added[:10],
            "removed_sample": removed[:10],
            "changed_sample": changed[:10],
            "type_changed_sample": type_changed[:10],
        }, None)

    def DropCodebase(self, params):
        if not MYSQL_AVAILABLE:
            return (0, None, ("NO_MYSQL", "mysql.connector not available", 0))
        codebase_name = self._p(params, "codebase_name")
        if not codebase_name:
            return (0, None, ("MISSING_PARAM", "codebase_name required", 0))
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM bcl_codebases WHERE name = %s", (codebase_name,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return (0, None, ("NOT_FOUND", codebase_name, 0))
        cb_id = row[0]
        self._delete_codebase_data(cursor, cb_id)
        cursor.execute("DELETE FROM bcl_codebases WHERE id = %s", (cb_id,))
        conn.commit()
        cursor.close()
        return (1, {"dropped": codebase_name, "id": cb_id}, None)
