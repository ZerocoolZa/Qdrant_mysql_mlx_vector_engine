#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_exporter.py"
# date="2026-06-27" author="Cascade" session_id="bcl-vbstype-fix"
# context="BCL IR IRExporter — export BCL IR to SQLite databases"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_exporter.py" domain="BCL" authority="IRExporter"}
# [@SUMMARY]{summary="BCL IRExporter: exports IR nodes and files to SQLite. No stdout, returns dict."}
# [@CLASS]{class="IRExporter" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="export_sqlite" type="command"}
# [@METHOD]{method="export_sqlite_bcl" type="command"}
# [@METHOD]{method="export_mysql_bcl" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3


class IRExporter:
    """Export BCL IR to SQLite databases."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "last_export": None,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "export_sqlite_bcl":
            return self.ExportSqliteBcl(params)
        elif command == "export_mysql_bcl":
            return self.ExportMysqlBcl(params)
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

    def ExportSqliteBcl(self, params):
        results = self._p(params, "results")
        db_path = self._p(params, "db_path")
        if results is None or db_path is None:
            return (0, None, ("MISSING_PARAM", "results and db_path required", 0))
        db = sqlite3.connect(db_path)
        cur = db.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS ir_nodes (id TEXT, type TEXT, parent TEXT, filepath TEXT, bcl TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS ir_files (filepath TEXT, file_id TEXT, blocks INTEGER, classes INTEGER, methods INTEGER, violations INTEGER)")
        cur.execute("DELETE FROM ir_nodes")
        cur.execute("DELETE FROM ir_files")
        node_count = 0
        for r in results:
            if "error" in r:
                continue
            cur.execute("INSERT INTO ir_files VALUES (?,?,?,?,?,?)",
                (r["filepath"], r.get("file_id", ""), r.get("block_count", 0),
                 r.get("class_count", 0), r.get("method_count", 0), r.get("violation_count", 0)))
            for block in r["bcl"].split("\n\n"):
                first_line = block.split("\n")[0]
                if "[@IRNODE]" in first_line:
                    parts = first_line.split()
                    node_type = ""
                    node_id = ""
                    parent_id = ""
                    for p in parts:
                        if p.startswith("type="):
                            node_type = p[5:]
                        elif p.startswith("id="):
                            node_id = p[3:]
                        elif p.startswith("parent="):
                            parent_id = p[7:]
                    cur.execute("INSERT INTO ir_nodes VALUES (?,?,?,?,?)",
                        (node_id, node_type, parent_id, r["filepath"], block))
                    node_count += 1
        db.commit()
        db.close()
        self.state["last_export"] = {"db_path": db_path, "nodes": node_count, "files": len(results)}
        return (1, self.state["last_export"], None)

    def ExportMysqlBcl(self, params):
        results = self._p(params, "results")
        db_name = self._p(params, "db_name")
        analysis = self._p(params, "analysis")
        if results is None or db_name is None:
            return (0, None, ("MISSING_PARAM", "results and db_name required", 0))
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_name)
        db = sqlite3.connect(db_path)
        cur = db.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS ir_nodes (id TEXT, type TEXT, parent TEXT, filepath TEXT, bcl TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS ir_files (filepath TEXT, file_id TEXT, blocks INTEGER, classes INTEGER, methods INTEGER, violations INTEGER)")
        cur.execute("CREATE TABLE IF NOT EXISTS ir_analysis (key TEXT, value TEXT)")
        cur.execute("DELETE FROM ir_nodes")
        cur.execute("DELETE FROM ir_files")
        cur.execute("DELETE FROM ir_analysis")
        node_count = 0
        for r in results:
            if "error" in r:
                continue
            cur.execute("INSERT INTO ir_files VALUES (?,?,?,?,?,?)",
                (r["filepath"], r.get("file_id", ""), r.get("block_count", 0),
                 r.get("class_count", 0), r.get("method_count", 0), r.get("violation_count", 0)))
            for block in r["bcl"].split("\n\n"):
                first_line = block.split("\n")[0]
                if "[@IRNODE]" in first_line:
                    parts = first_line.split()
                    node_type = ""
                    node_id = ""
                    parent_id = ""
                    for p in parts:
                        if p.startswith("type="):
                            node_type = p[5:]
                        elif p.startswith("id="):
                            node_id = p[3:]
                        elif p.startswith("parent="):
                            parent_id = p[7:]
                    cur.execute("INSERT INTO ir_nodes VALUES (?,?,?,?,?)",
                        (node_id, node_type, parent_id, r["filepath"], block))
                    node_count += 1
        if analysis:
            for k, v in analysis.items():
                if isinstance(v, (int, str)):
                    cur.execute("INSERT INTO ir_analysis VALUES (?,?)", (k, str(v)))
        db.commit()
        db.close()
        self.state["last_export"] = {"db_name": db_name, "nodes": node_count, "files": len(results)}
        return (1, self.state["last_export"], None)
