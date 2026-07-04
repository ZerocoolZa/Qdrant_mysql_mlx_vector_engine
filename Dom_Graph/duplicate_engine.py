#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/duplicate_engine.py"
# date="2026-06-26" author="Devin" session_id="phase4-analysis"
# context="Project Digital Twin Phase 4 Section 23 Duplicate Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="duplicate_engine.py" domain="twin_duplicate" authority="DuplicateEngine"}
# [@SUMMARY]{summary="Duplicate authority that detects duplicate files, classes, methods, SQL blocks and config constants by hash and content grouping."}
# [@CLASS]{class="DuplicateEngine" domain="duplicate" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="find_duplicate_files" type="command"}
# [@METHOD]{method="find_duplicate_classes" type="command"}
# [@METHOD]{method="find_duplicate_methods" type="command"}
# [@METHOD]{method="find_duplicate_sql" type="command"}
# [@METHOD]{method="find_duplicate_constants" type="command"}
# [@METHOD]{method="find_all_duplicates" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<DuplicateEngine: detects duplicate files, classes, methods, SQL blocks, config constants by hash and content grouping. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
DuplicateEngine -- authority for duplicate detection across project entities.
Implements Section 23 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: find_duplicate_files, find_duplicate_classes, find_duplicate_methods,
          find_duplicate_sql, find_duplicate_constants, find_all_duplicates.
"""
import ast
import hashlib
import json
import os
import re
import sqlite3
import textwrap

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
SQL_PATTERN = re.compile(
    r"\b(execute|SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER)\b",
    re.IGNORECASE,
)


class DuplicateEngine:
    """Authority for detecting duplicate files, classes, methods, SQL and constants."""

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
        if command == "find_duplicate_files":
            return self.FindDuplicateFiles(params)
        elif command == "find_duplicate_classes":
            return self.FindDuplicateClasses(params)
        elif command == "find_duplicate_methods":
            return self.FindDuplicateMethods(params)
        elif command == "find_duplicate_sql":
            return self.FindDuplicateSql(params)
        elif command == "find_duplicate_constants":
            return self.FindDuplicateConstants(params)
        elif command == "find_duplicate_logic":
            return self.FindDuplicateLogic(params)
        elif command == "find_duplicate_imports":
            return self.FindDuplicateImports(params)
        elif command == "find_duplicate_bcl":
            return self.FindDuplicateBcl(params)
        elif command == "find_duplicate_algorithms":
            return self.FindDuplicateAlgorithms(params)
        elif command == "find_all_duplicates":
            return self.FindAllDuplicates(params)
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

    def HashText(self, text):
        if not text:
            return ""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def FindDuplicateFiles(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT hash, COUNT(*) AS cnt FROM files "
            "WHERE hash IS NOT NULL AND hash != '' "
            "GROUP BY hash HAVING COUNT(*) > 1 ORDER BY cnt DESC LIMIT ?",
            (limit,),
        )
        dup_hashes = cur.fetchall()
        groups = []
        for dup_hash, cnt in dup_hashes:
            cur.execute(
                "SELECT file_id, file_name, path, extension, size, modified "
                "FROM files WHERE hash=? ORDER BY file_id",
                (dup_hash,),
            )
            members = [
                {
                    "file_id": r[0],
                    "file_name": r[1],
                    "path": r[2],
                    "extension": r[3],
                    "size": r[4],
                    "modified": r[5],
                }
                for r in cur.fetchall()
            ]
            groups.append({"hash": dup_hash, "count": cnt, "members": members})
        report = {"duplicate_groups": len(groups), "groups": groups}
        self.state["results"].append(report)
        return (1, report, None)

    def FindDuplicateClasses(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT hash, COUNT(*) AS cnt FROM classes "
            "WHERE hash IS NOT NULL AND hash != '' "
            "GROUP BY hash HAVING COUNT(*) > 1 ORDER BY cnt DESC LIMIT ?",
            (limit,),
        )
        dup_hashes = cur.fetchall()
        groups = []
        for dup_hash, cnt in dup_hashes:
            cur.execute(
                "SELECT class_id, file_id, class_name, start_line, end_line, "
                "method_count FROM classes WHERE hash=? ORDER BY class_id",
                (dup_hash,),
            )
            members = [
                {
                    "class_id": r[0],
                    "file_id": r[1],
                    "class_name": r[2],
                    "start_line": r[3],
                    "end_line": r[4],
                    "method_count": r[5],
                }
                for r in cur.fetchall()
            ]
            groups.append({"hash": dup_hash, "count": cnt, "members": members})
        report = {"duplicate_groups": len(groups), "groups": groups}
        self.state["results"].append(report)
        return (1, report, None)

    def FindDuplicateMethods(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT hash, COUNT(*) AS cnt FROM methods "
            "WHERE hash IS NOT NULL AND hash != '' "
            "GROUP BY hash HAVING COUNT(*) > 1 ORDER BY cnt DESC LIMIT ?",
            (limit,),
        )
        dup_hashes = cur.fetchall()
        groups = []
        for dup_hash, cnt in dup_hashes:
            cur.execute(
                "SELECT method_id, class_id, file_id, method_name, start_line, "
                "end_line, line_count FROM methods WHERE hash=? ORDER BY method_id",
                (dup_hash,),
            )
            members = [
                {
                    "method_id": r[0],
                    "class_id": r[1],
                    "file_id": r[2],
                    "method_name": r[3],
                    "start_line": r[4],
                    "end_line": r[5],
                    "line_count": r[6],
                }
                for r in cur.fetchall()
            ]
            groups.append({"hash": dup_hash, "count": cnt, "members": members})
        report = {"duplicate_groups": len(groups), "groups": groups}
        self.state["results"].append(report)
        return (1, report, None)

    def FindDuplicateSql(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_name, method_code FROM methods "
            "WHERE method_code IS NOT NULL AND method_code != ''"
        )
        sql_blocks = []
        for method_id, method_name, code in cur.fetchall():
            if not code:
                continue
            matches = SQL_PATTERN.findall(code)
            if not matches:
                continue
            sql_hash = self.HashText(code.strip())
            sql_blocks.append(
                {
                    "method_id": method_id,
                    "method_name": method_name,
                    "sql_hash": sql_hash,
                    "match_count": len(matches),
                }
            )
        hash_groups = {}
        for block in sql_blocks:
            hash_groups.setdefault(block["sql_hash"], []).append(block)
        groups = []
        for sql_hash, members in hash_groups.items():
            if len(members) < 2:
                continue
            groups.append(
                {
                    "hash": sql_hash,
                    "count": len(members),
                    "members": members[:limit],
                }
            )
        groups.sort(key=lambda g: g["count"], reverse=True)
        groups = groups[:limit]
        report = {"duplicate_groups": len(groups), "groups": groups}
        self.state["results"].append(report)
        return (1, report, None)

    def FindDuplicateConstants(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT value, COUNT(*) AS cnt FROM config_constants "
            "WHERE value IS NOT NULL AND value != '' "
            "GROUP BY value HAVING COUNT(*) > 1 ORDER BY cnt DESC LIMIT ?",
            (limit,),
        )
        dup_values = cur.fetchall()
        groups = []
        for value, cnt in dup_values:
            cur.execute(
                "SELECT name, value, type, description FROM config_constants "
                "WHERE value=? ORDER BY name",
                (value,),
            )
            members = [
                {
                    "name": r[0],
                    "value": r[1],
                    "type": r[2],
                    "description": r[3],
                }
                for r in cur.fetchall()
            ]
            groups.append({"value": value, "count": cnt, "members": members})
        report = {"duplicate_groups": len(groups), "groups": groups}
        self.state["results"].append(report)
        return (1, report, None)

    def NormalizeAstForLogic(self, code):
        if not code:
            return ""
        try:
            tree = ast.parse(textwrap.dedent(code))
        except SyntaxError:
            return ""
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                node.id = "V"
            elif isinstance(node, ast.arg):
                node.arg = "A"
            elif isinstance(node, ast.FunctionDef):
                node.name = "F"
            elif isinstance(node, ast.Attribute):
                node.attr = "M"
        try:
            sig = ast.dump(tree)
        except Exception:
            return ""
        return hashlib.sha256(sig.encode("utf-8")).hexdigest()

    def FindDuplicateLogic(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, class_id, method_name, method_code FROM methods "
            "WHERE method_code IS NOT NULL AND method_code != '' "
            "ORDER BY method_id LIMIT ?",
            (limit * 10,),
        )
        rows = cur.fetchall()
        sig_groups = {}
        for method_id, class_id, method_name, code in rows:
            sig = self.NormalizeAstForLogic(code)
            if not sig:
                continue
            sig_groups.setdefault(sig, []).append({
                "method_id": method_id,
                "class_id": class_id,
                "method_name": method_name,
            })
        groups = []
        for sig, members in sig_groups.items():
            if len(members) < 2:
                continue
            groups.append({
                "logic_hash": sig,
                "count": len(members),
                "members": members[:limit],
            })
        groups.sort(key=lambda g: g["count"], reverse=True)
        groups = groups[:limit]
        report = {"duplicate_groups": len(groups), "groups": groups}
        self.state["results"].append(report)
        return (1, report, None)

    def FindDuplicateImports(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT file_id, file_name, imports FROM files "
            "WHERE imports IS NOT NULL AND imports != '' "
            "ORDER BY file_id LIMIT ?",
            (limit * 10,),
        )
        rows = cur.fetchall()
        import_groups = {}
        for file_id, file_name, imports_json in rows:
            imports_set = set()
            if imports_json:
                try:
                    parsed = json.loads(imports_json)
                    if isinstance(parsed, list):
                        imports_set = set(sorted(str(i) for i in parsed))
                except (ValueError, TypeError):
                    pass
            if not imports_set:
                continue
            key = "|".join(sorted(imports_set))
            import_groups.setdefault(key, []).append({
                "file_id": file_id,
                "file_name": file_name,
                "imports": sorted(imports_set),
            })
        groups = []
        for key, members in import_groups.items():
            if len(members) < 2:
                continue
            groups.append({
                "import_set": members[0]["imports"],
                "count": len(members),
                "members": members[:limit],
            })
        groups.sort(key=lambda g: g["count"], reverse=True)
        groups = groups[:limit]
        report = {"duplicate_groups": len(groups), "groups": groups}
        self.state["results"].append(report)
        return (1, report, None)

    def FindDuplicateBcl(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        groups = []
        for table, id_col, name_col in (
            ("files", "file_id", "file_name"),
            ("classes", "class_id", "class_name"),
            ("methods", "method_id", "method_name"),
        ):
            cur.execute(
                "SELECT bcl, COUNT(*) AS cnt FROM " + table + " "
                "WHERE bcl IS NOT NULL AND bcl != '' "
                "GROUP BY bcl HAVING COUNT(*) > 1 ORDER BY cnt DESC LIMIT ?",
                (limit,),
            )
            dup_bcls = cur.fetchall()
            for bcl_text, cnt in dup_bcls:
                cur.execute(
                    "SELECT " + id_col + ", " + name_col + " FROM " + table + " "
                    "WHERE bcl=? ORDER BY " + id_col,
                    (bcl_text,),
                )
                members = [
                    {"entity_id": r[0], "entity_name": r[1], "table": table}
                    for r in cur.fetchall()
                ]
                bcl_hash = self.HashText(bcl_text)
                groups.append({
                    "bcl_hash": bcl_hash,
                    "table": table,
                    "count": cnt,
                    "members": members[:limit],
                })
        groups.sort(key=lambda g: g["count"], reverse=True)
        groups = groups[:limit]
        report = {"duplicate_groups": len(groups), "groups": groups}
        self.state["results"].append(report)
        return (1, report, None)

    def FindDuplicateAlgorithms(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, class_id, method_name, calls, dependencies "
            "FROM methods WHERE calls IS NOT NULL OR dependencies IS NOT NULL "
            "ORDER BY method_id LIMIT ?",
            (limit * 10,),
        )
        rows = cur.fetchall()
        algo_groups = {}
        for method_id, class_id, method_name, calls_json, deps_json in rows:
            call_set = set()
            if calls_json:
                try:
                    parsed = json.loads(calls_json)
                    if isinstance(parsed, list):
                        call_set = set(sorted(str(c) for c in parsed))
                except (ValueError, TypeError):
                    pass
            dep_set = set()
            if deps_json:
                try:
                    parsed = json.loads(deps_json)
                    if isinstance(parsed, list):
                        dep_set = set(sorted(str(d) for d in parsed))
                except (ValueError, TypeError):
                    pass
            pattern = "|".join(sorted(call_set)) + "||" + "|".join(sorted(dep_set))
            if not pattern.strip("|"):
                continue
            algo_groups.setdefault(pattern, []).append({
                "method_id": method_id,
                "class_id": class_id,
                "method_name": method_name,
                "calls": sorted(call_set),
                "dependencies": sorted(dep_set),
            })
        groups = []
        for pattern, members in algo_groups.items():
            if len(members) < 2:
                continue
            groups.append({
                "call_pattern": members[0]["calls"],
                "dependency_pattern": members[0]["dependencies"],
                "count": len(members),
                "members": members[:limit],
            })
        groups.sort(key=lambda g: g["count"], reverse=True)
        groups = groups[:limit]
        report = {"duplicate_groups": len(groups), "groups": groups}
        self.state["results"].append(report)
        return (1, report, None)

    def FindAllDuplicates(self, params):
        report = {
            "files": self.FindDuplicateFiles(params)[1],
            "classes": self.FindDuplicateClasses(params)[1],
            "methods": self.FindDuplicateMethods(params)[1],
            "sql": self.FindDuplicateSql(params)[1],
            "constants": self.FindDuplicateConstants(params)[1],
            "logic": self.FindDuplicateLogic(params)[1],
            "imports": self.FindDuplicateImports(params)[1],
            "bcl": self.FindDuplicateBcl(params)[1],
            "algorithms": self.FindDuplicateAlgorithms(params)[1],
        }
        total = 0
        for section in report.values():
            if section and "duplicate_groups" in section:
                total += section["duplicate_groups"]
        report["total_duplicate_groups"] = total
        self.state["results"].append(report)
        return (1, report, None)
