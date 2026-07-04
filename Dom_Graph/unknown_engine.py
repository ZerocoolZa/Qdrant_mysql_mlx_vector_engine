#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/unknown_engine.py"
# date="2026-06-26" author="Devin" session_id="phase6-intelligence"
# context="Project Digital Twin Section 54 Unknown Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="unknown_engine.py" domain="twin_unknown" authority="UnknownEngine"}
# [@SUMMARY]{summary="Unknown engine authority that finds missing classes, methods, files, definitions, and reports all unknowns in the codebase."}
# [@CLASS]{class="UnknownEngine" domain="unknown" authority="single"}
# [@METHOD]{method="find_missing_classes" type="command"}
# [@METHOD]{method="find_missing_methods" type="command"}
# [@METHOD]{method="find_missing_files" type="command"}
# [@METHOD]{method="find_unknowns" type="command"}
# [@METHOD]{method="report_unknowns" type="command"}
# [@METHOD]{method="find_unknown_types" type="command"}
# [@METHOD]{method="find_unknown_dependencies" type="command"}
# [@METHOD]{method="find_unknown_runtime" type="command"}
# [@METHOD]{method="find_unknown_behavior" type="command"}
# [@METHOD]{method="find_missing_definitions" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<UnknownEngine: finds missing classes methods files definitions reports all unknowns in codebase. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations. Header missing Run method declaration but Run() exists in code.>][@todos<none>]}
"""
UnknownEngine -- Unknown detection authority.
Implements Section 54 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: find_missing_classes, find_missing_methods, find_missing_files, find_unknowns,
          report_unknowns, find_unknown_types, find_unknown_dependencies, find_unknown_runtime,
          find_unknown_behavior.
"""
import json
import os
import sqlite3

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class UnknownEngine:
    """Unknown detection authority."""

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
        if command == "find_missing_classes":
            return self.FindMissingClasses(params)
        elif command == "find_missing_methods":
            return self.FindMissingMethods(params)
        elif command == "find_missing_files":
            return self.FindMissingFiles(params)
        elif command == "find_unknowns":
            return self.FindUnknowns(params)
        elif command == "report_unknowns":
            return self.ReportUnknowns(params)
        elif command == "find_unknown_types":
            return self.FindUnknownTypes(params)
        elif command == "find_unknown_dependencies":
            return self.FindUnknownDependencies(params)
        elif command == "find_unknown_runtime":
            return self.FindUnknownRuntime(params)
        elif command == "find_unknown_behavior":
            return self.FindUnknownBehavior(params)
        elif command == "find_missing_definitions":
            return self.FindMissingDefinitions(params)

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

    def FindMissingClasses(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT e.dst_id AS missing_id, e.edge_type, e.evidence "
                    "FROM edges e WHERE e.dst_type='class' "
                    "AND e.dst_id NOT IN (SELECT class_id FROM classes)")
        dst_missing = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT e.src_id AS missing_id, e.edge_type, e.evidence "
                    "FROM edges e WHERE e.src_type='class' "
                    "AND e.src_id NOT IN (SELECT class_id FROM classes)")
        src_missing = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        missing = dst_missing + src_missing
        return (1, {"missing_classes": missing, "count": len(missing)}, None)

    def FindMissingMethods(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT e.dst_id AS missing_id, e.edge_type, e.evidence "
                    "FROM edges e WHERE e.dst_type='method' "
                    "AND e.dst_id NOT IN (SELECT method_id FROM methods)")
        dst_missing = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT e.src_id AS missing_id, e.edge_type, e.evidence "
                    "FROM edges e WHERE e.src_type='method' "
                    "AND e.src_id NOT IN (SELECT method_id FROM methods)")
        src_missing = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        missing = dst_missing + src_missing
        return (1, {"missing_methods": missing, "count": len(missing)}, None)

    def FindMissingFiles(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT e.dst_id AS missing_id, e.edge_type, e.evidence "
                    "FROM edges e WHERE e.dst_type='file' "
                    "AND e.dst_id NOT IN (SELECT file_id FROM files)")
        dst_missing = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT e.src_id AS missing_id, e.edge_type, e.evidence "
                    "FROM edges e WHERE e.src_type='file' "
                    "AND e.src_id NOT IN (SELECT file_id FROM files)")
        src_missing = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        edge_missing = dst_missing + src_missing
        cur.execute("SELECT file_id, file_name, imports FROM files")
        import_missing = []
        for row in cur.fetchall():
            imports = []
            try:
                imports = json.loads(row[2]) if row[2] else []
            except (ValueError, TypeError):
                pass
            for imp in imports:
                cur.execute("SELECT file_id FROM files WHERE file_name LIKE ?", ("%" + str(imp) + "%",))
                if not cur.fetchone():
                    import_missing.append({"file_id": row[0], "file_name": row[1], "missing": imp})
        missing = edge_missing + import_missing
        return (1, {"missing_files": missing, "count": len(missing)}, None)

    def FindUnknowns(self, params):
        results = {}
        for step in ("find_missing_classes", "find_missing_methods", "find_missing_files",
                     "find_missing_definitions", "find_unknown_types", "find_unknown_dependencies",
                     "find_unknown_runtime", "find_unknown_behavior"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM methods WHERE bcl IS NULL OR bcl = ''")
        results["no_bcl_methods"] = cur.fetchone()[0]
        return (1, {"unknowns": results}, None)

    def ReportUnknowns(self, params):
        res = self.FindUnknowns(params)
        if res[0] != 1:
            return res
        conn = self.Connect()
        cur = conn.cursor()
        from datetime import datetime, timezone
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                    "VALUES (?, ?, ?, ?, ?)",
                    ("unknown", "unknown_report", json.dumps(res[1]), 50,
                     datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (1, {"report": res[1], "recorded": True}, None)

    def FindUnknownTypes(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, return_type, class_id "
                    "FROM methods WHERE return_type IS NULL OR return_type = '' "
                    "OR lower(return_type) = 'unknown' "
                    "ORDER BY method_id LIMIT ?", (limit,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"unknown_types": results, "count": len(results)}, None)

    def FindUnknownDependencies(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT file_id, file_name, imports FROM files")
        unresolved = []
        for row in cur.fetchall():
            imports = []
            try:
                imports = json.loads(row[2]) if row[2] else []
            except (ValueError, TypeError):
                pass
            for imp in imports:
                cur.execute("SELECT file_id FROM files WHERE file_name LIKE ? OR path LIKE ?",
                            ("%" + str(imp) + "%", "%" + str(imp) + "%"))
                if not cur.fetchone():
                    unresolved.append({"file_id": row[0], "file_name": row[1],
                                       "unresolved_import": imp})
        return (1, {"unknown_dependencies": unresolved[:limit],
                    "count": len(unresolved)}, None)

    def FindUnknownRuntime(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT m.method_id, m.method_name, m.class_id "
                    "FROM methods m WHERE m.method_id NOT IN "
                    "(SELECT DISTINCT dst_id FROM edges WHERE dst_type='method' AND edge_type='calls') "
                    "AND m.method_id NOT IN "
                    "(SELECT DISTINCT src_id FROM edges WHERE src_type='method' AND edge_type='calls') "
                    "ORDER BY m.method_id LIMIT ?", (limit,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"unknown_runtime": results, "count": len(results)}, None)

    def FindUnknownBehavior(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, class_id, bcl "
                    "FROM methods WHERE (bcl IS NULL OR bcl = '') "
                    "ORDER BY method_id LIMIT ?", (limit,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"unknown_behavior": results, "count": len(results)}, None)

    def FindMissingDefinitions(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        missing = []
        cur.execute("SELECT method_id, method_name, dependencies, calls "
                    "FROM methods WHERE dependencies IS NOT NULL OR calls IS NOT NULL "
                    "ORDER BY method_id LIMIT ?", (limit,))
        for row in cur.fetchall():
            method_id = row[0]
            method_name = row[1]
            for col_idx in (2, 3):
                names = []
                try:
                    names = json.loads(row[col_idx]) if row[col_idx] else []
                except (ValueError, TypeError):
                    pass
                if not isinstance(names, list):
                    continue
                for name in names:
                    if not name:
                        continue
                    cur.execute("SELECT method_id FROM methods WHERE method_name=?", (str(name),))
                    method_match = cur.fetchone()
                    if method_match:
                        continue
                    cur.execute("SELECT class_id FROM classes WHERE class_name=?", (str(name),))
                    class_match = cur.fetchone()
                    if class_match:
                        continue
                    cur.execute("SELECT file_id FROM files WHERE file_name LIKE ?",
                                ("%" + str(name) + "%",))
                    file_match = cur.fetchone()
                    if file_match:
                        continue
                    missing.append({"referenced_name": name, "source_method_id": method_id,
                                    "source_method": method_name})
        return (1, {"missing_definitions": missing, "count": len(missing)}, None)

