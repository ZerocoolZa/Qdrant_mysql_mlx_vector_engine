#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/ir_extractor.py"
# date="2026-08-18" author="Devin" session_id="bcl-ir-build"
# context="BCL_COMPILER_PLAN section 19-23: AST extractor that produces METHOD_IR from .py files"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="ir_extractor.py" domain="bcl_ir" authority="IrExtractor"}
# [@SUMMARY]{summary="AST extractor that scans .py files, parses AST, and produces METHOD_IR records with certainty-tiered edges per BCL_COMPILER_PLAN sections 19-23."}
# [@CLASS]{class="IrExtractor" domain="bcl_ir" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="ScanDir" type="command"}
# [@METHOD]{method="ExtractFile" type="command"}
# [@METHOD]{method="ExtractMethod" type="command"}
# [@METHOD]{method="ExtractClass" type="command"}
# [@METHOD]{method="ExtractEdges" type="command"}
# [@METHOD]{method="ClassifyCertainty" type="command"}
# [@METHOD]{method="ClassifyMethod" type="command"}
# [@METHOD]{method="BuildGraph" type="command"}
# [@METHOD]{method="Report" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<IrExtractor: AST extractor producing METHOD_IR records with certainty-tiered edges per BCL_COMPILER_PLAN sections 19-23. Has VBStyle headers, Run dispatch, single class, _p helper, Tuple3 returns. BUT: 51 self._ violations (self._is_method_inside_class, self._attr_chain, self._extract_inputs, self._extract_outputs, self._extract_call_edge, self._extract_state_edge, self._detect_resource, self._compute_deterministic_subset, etc. -- only self._p is allowed). Uses typing imports (Any, Dict, List, Tuple). Has module-level function _parse_batch outside class. No print/decorators/hardcoded paths.>][@todos<1. Rename all self._ methods to PascalCase without self._ prefix (e.g. self._is_method_inside_class -> self.IsMethodInsideClass). 2. Remove typing imports (Any, Dict, List, Tuple). 3. Move _parse_batch into class or document as module-level helper.>]}
"""
IrExtractor -- AST extractor that produces METHOD_IR records.

Implements sections 19-23 of BCL_COMPILER_PLAN.md:
  - section 19: code-first architecture (AST -> IR -> BCL)
  - section 20: deterministic IR schema (closed-world)
  - section 21: execution edge model (CALL/PIPE/EVENT/CALLBACK/FUTURE)
  - section 22: graph-first reconstruction (SCCs, computational units)
  - section 23: 3-tier certainty model (CERTAIN/PROBABLE/UNKNOWN)

This is NOT a behavioral predictor. It is a lossy-but-deterministic
structural compiler that produces labeled-uncertainty IR graphs.
"""
import ast
import hashlib
import os
import pickle
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import threading
from typing import Any, Dict, List, Tuple

# --- Constants (section 20.4, 20.5, 20.9, 22.6) ---

INIT_PATTERNS = frozenset(("__init__", "Init", "Setup", "Configure", "Bootstrap"))
CLEANUP_PATTERNS = frozenset(("__del__", "Cleanup", "Finalize", "Close", "Release", "Teardown"))
LINK_DEPTH_THRESHOLD = 3
CALL_DENSITY_THRESHOLD = 2
DOMAIN_RESOURCE_THRESHOLD = 2

# Resource detection patterns (section 20.2 resource_edges)
FILE_IO_FUNCS = frozenset(("open", "Path", "read_text", "write_text", "read_bytes", "write_bytes",
                           "read", "write", "remove", "rename", "unlink", "mkdir", "rmdir"))
NETWORK_IO_FUNCS = frozenset(("socket", "connect", "send", "recv", "request", "get", "post",
                              "put", "delete", "urlopen", "urllib", "http"))
DB_IO_FUNCS = frozenset(("execute", "commit", "rollback", "cursor", "connect", "fetchall",
                         "fetchone", "insert", "update", "delete", "select"))
PROCESS_IO_FUNCS = frozenset(("system", "popen", "run", "Popen", "call", "check_output",
                              "check_call", "getenv", "environ"))

# Certainty tiers (section 23)
CERTAIN = "CERTAIN"
PROBABLE = "PROBABLE"
UNKNOWN = "UNKNOWN"

# Method types (section 20.4)
TYPE_IO = "IO"
TYPE_CORE = "CORE"
TYPE_LINK = "LINK"
TYPE_INIT = "INIT"
TYPE_CLEANUP = "CLEANUP"


def _parse_batch(batch, file_id):
    """Module-level function for ProcessPoolExecutor. Parses a batch of methods."""
    ext = IrExtractor()
    all_results = []
    class_id = None
    for m, cid in batch:
        class_id = cid
        method_code = m["method_code"]
        if not method_code or len(method_code.strip()) < 10:
            continue
        try:
            tree = ast.parse(method_code, filename=cid + "." + m["method_name"])
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_result = ext.ExtractMethod({
                    "node": node,
                    "file_id": file_id,
                    "class_id": cid,
                    "source": method_code,
                    "source_method_id": m.get("id"),
                })
                if method_result[0] == 1:
                    all_results.append(method_result[1])
    return ("OK", all_results, class_id)


class IrExtractor:
    """AST extractor that produces METHOD_IR records with certainty-tiered edges."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "scan_root": None,
                "file_pattern": "*.py",
                "link_depth_threshold": LINK_DEPTH_THRESHOLD,
                "call_density_threshold": CALL_DENSITY_THRESHOLD,
                "domain_resource_threshold": DOMAIN_RESOURCE_THRESHOLD,
            },
            "files": {},          # file_path -> {hash, line_count, classes, methods}
            "methods": {},        # method_id -> METHOD_IR dict
            "classes": {},        # class_id -> {name, file, bases, methods}
            "edges": [],          # list of EDGE dicts
            "stats": {
                "total_files": 0,
                "total_classes": 0,
                "total_methods": 0,
                "certain_edges": 0,
                "probable_edges": 0,
                "unknown_edges": 0,
                "type_counts": {"IO": 0, "CORE": 0, "LINK": 0, "INIT": 0, "CLEANUP": 0},
                "deterministic_subset_count": 0,
                "parse_errors": 0,
            },
            "errors": [],
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "scan_dir":
            return self.ScanDir(params)
        elif command == "scan_dir_parallel":
            return self.ScanDirParallel(params)
        elif command == "scan_mysql":
            return self.ScanMysql(params)
        elif command == "scan_mysql_parallel":
            return self.ScanMysqlParallel(params)
        elif command == "extract_file":
            return self.ExtractFile(params)
        elif command == "build_graph":
            return self.BuildGraph(params)
        elif command == "classify_all":
            return self.ClassifyAll(params)
        elif command == "report":
            return self.Report(params)
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

    # ================================================================
    # SCANNING
    # ================================================================

    def ScanDir(self, params):
        root = self._p(params, "root") or self.state["config"]["scan_root"]
        if not root:
            return (0, None, ("MISSING_PARAM", "root or scan_root config required", 0))
        if not os.path.isdir(root):
            return (0, None, ("NOT_A_DIR", root, 0))
        py_files = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fname in filenames:
                if fname.endswith(".py"):
                    py_files.append(os.path.join(dirpath, fname))
        self.state["stats"]["total_files"] = len(py_files)
        for fpath in py_files:
            result = self.ExtractFile({"path": fpath})
            if result[0] != 1:
                self.state["errors"].append({"file": fpath, "error": result[2]})
        return (1, {"files_scanned": len(py_files),
                     "total_methods": self.state["stats"]["total_methods"],
                     "total_classes": self.state["stats"]["total_classes"],
                     "parse_errors": self.state["stats"]["parse_errors"]}, None)

    def ScanMysql(self, params):
        db_name = self._p(params, "db_name", "vb_code_test")
        db_host = self._p(params, "db_host", "localhost")
        db_user = self._p(params, "db_user", "root")
        db_password = self._p(params, "db_password", "")
        class_filter = self._p(params, "class_filter")
        limit = self._p(params, "limit", 0)
        try:
            import mysql.connector
        except ImportError:
            return (0, None, ("NO_MYSQL", "mysql.connector not available", 0))
        conn = mysql.connector.connect(
            user=db_user, password=db_password, host=db_host, database=db_name
        )
        cursor = conn.cursor(dictionary=True)
        sql = ("SELECT id, class_name, domain, role, description, class_code, "
               "source_id FROM vb_classes")
        args = []
        if class_filter:
            sql += " WHERE class_name LIKE %s"
            args.append("%" + class_filter + "%")
        if limit:
            sql += " LIMIT %s"
            args.append(limit)
        cursor.execute(sql, args)
        classes = cursor.fetchall()
        class_map = {}
        for cls in classes:
            class_id = "mysql:" + db_name + "::" + cls["class_name"]
            class_map[cls["id"]] = class_id
            self.state["classes"][class_id] = {
                "name": cls["class_name"],
                "file_id": "mysql:" + db_name,
                "bases": [],
                "methods": [],
                "line_start": 0,
                "line_end": 0,
                "domain": cls.get("domain") or "",
                "role": cls.get("role") or "",
                "description": cls.get("description") or "",
                "source_class_id": cls["id"],
            }
            self.state["stats"]["total_classes"] += 1
        file_id = "mysql:" + db_name
        if file_id not in self.state["files"]:
            self.state["files"][file_id] = {
                "path": file_id,
                "hash": "mysql",
                "line_count": 0,
                "classes": list(class_map.values()),
                "methods": [],
            }
        self.state["stats"]["total_files"] = 1
        if class_filter:
            cursor.execute(
                "SELECT m.id, m.class_id, m.method_name, m.params, m.method_code, "
                "m.line_start, m.is_dunder FROM vb_methods m "
                "JOIN vb_classes c ON m.class_id = c.id "
                "WHERE c.class_name LIKE %s AND m.method_code IS NOT NULL",
                ("%" + class_filter + "%",)
            )
        else:
            cursor.execute(
                "SELECT id, class_id, method_name, params, method_code, "
                "line_start, is_dunder FROM vb_methods WHERE method_code IS NOT NULL"
            )
        all_methods = cursor.fetchall()
        methods_by_class = {}
        for m in all_methods:
            methods_by_class.setdefault(m["class_id"], []).append(m)
        for cls_row in classes:
            cid_db = cls_row["id"]
            class_id = class_map.get(cid_db)
            if not class_id:
                continue
            methods = methods_by_class.get(cid_db, [])
            for m in methods:
                method_code = m["method_code"]
                if not method_code or len(method_code.strip()) < 10:
                    continue
                try:
                    tree = ast.parse(method_code, filename=class_id + "." + m["method_name"])
                except SyntaxError:
                    self.state["stats"]["parse_errors"] += 1
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_result = self.ExtractMethod({
                            "node": node,
                            "file_id": file_id,
                            "class_id": class_id,
                            "source": method_code,
                            "source_method_id": m["id"],
                        })
                        if method_result[0] == 1:
                            mid = method_result[1]["id"]
                            self.state["files"][file_id]["methods"].append(mid)
                            self.state["classes"][class_id]["methods"].append(mid)
        cursor.close()
        conn.close()
        return (1, {
            "db_name": db_name,
            "classes_scanned": len(classes),
            "total_methods": self.state["stats"]["total_methods"],
            "total_classes": self.state["stats"]["total_classes"],
            "parse_errors": self.state["stats"]["parse_errors"],
        }, None)

    def ScanMysqlParallel(self, params):
        db_name = self._p(params, "db_name", "vb_code_test")
        db_host = self._p(params, "db_host", "localhost")
        db_user = self._p(params, "db_user", "root")
        db_password = self._p(params, "db_password", "")
        class_filter = self._p(params, "class_filter")
        limit = self._p(params, "limit", 0)
        workers = self._p(params, "workers", 8)
        try:
            import mysql.connector
        except ImportError:
            return (0, None, ("NO_MYSQL", "mysql.connector not available", 0))
        conn = mysql.connector.connect(
            user=db_user, password=db_password, host=db_host, database=db_name
        )
        cursor = conn.cursor(dictionary=True)
        sql = ("SELECT id, class_name, domain, role, description, class_code, "
               "source_id FROM vb_classes")
        args = []
        if class_filter:
            sql += " WHERE class_name LIKE %s"
            args.append("%" + class_filter + "%")
        if limit:
            sql += " LIMIT %s"
            args.append(limit)
        cursor.execute(sql, args)
        classes = cursor.fetchall()
        if class_filter:
            cursor.execute(
                "SELECT m.id, m.class_id, m.method_name, m.params, m.method_code, "
                "m.line_start, m.is_dunder FROM vb_methods m "
                "JOIN vb_classes c ON m.class_id = c.id "
                "WHERE c.class_name LIKE %s AND m.method_code IS NOT NULL",
                ("%" + class_filter + "%",)
            )
        else:
            cursor.execute(
                "SELECT id, class_id, method_name, params, method_code, "
                "line_start, is_dunder FROM vb_methods WHERE method_code IS NOT NULL"
            )
        all_methods = cursor.fetchall()
        cursor.close()
        conn.close()
        class_map = {}
        for cls in classes:
            class_id = "mysql:" + db_name + "::" + cls["class_name"]
            class_map[cls["id"]] = class_id
            self.state["classes"][class_id] = {
                "name": cls["class_name"],
                "file_id": "mysql:" + db_name,
                "bases": [],
                "methods": [],
                "line_start": 0,
                "line_end": 0,
                "domain": cls.get("domain") or "",
                "role": cls.get("role") or "",
                "description": cls.get("description") or "",
                "source_class_id": cls["id"],
            }
            self.state["stats"]["total_classes"] += 1
        file_id = "mysql:" + db_name
        self.state["files"][file_id] = {
            "path": file_id,
            "hash": "mysql",
            "line_count": 0,
            "classes": list(class_map.values()),
            "methods": [],
        }
        self.state["stats"]["total_files"] = 1
        methods_by_class = defaultdict(list)
        for m in all_methods:
            methods_by_class[m["class_id"]].append(m)
        lock = threading.Lock()
        def parse_one(m, class_id):
            method_code = m["method_code"]
            if not method_code or len(method_code.strip()) < 10:
                return None
            try:
                tree = ast.parse(method_code, filename=class_id + "." + m["method_name"])
            except SyntaxError:
                return ("PARSE_ERROR", None, class_id)
            results = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_result = self.ExtractMethod({
                        "node": node,
                        "file_id": file_id,
                        "class_id": class_id,
                        "source": method_code,
                    })
                    if method_result[0] == 1:
                        results.append(method_result[1])
            return ("OK", results, class_id)
        tasks = []
        for cls_row in classes:
            cid_db = cls_row["id"]
            class_id = class_map.get(cid_db)
            if not class_id:
                continue
            for m in methods_by_class.get(cid_db, []):
                tasks.append((m, class_id))
        batch_size = max(1, len(tasks) // (workers * 4))
        batches = [tasks[i:i+batch_size] for i in range(0, len(tasks), batch_size)]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_parse_batch, batch, file_id): batch for batch in batches}
            for future in as_completed(futures):
                status, results, class_id = future.result()
                if status == "PARSE_ERROR":
                    self.state["stats"]["parse_errors"] += 1
                    continue
                for method_ir in results:
                    mid = method_ir["id"]
                    self.state["methods"][mid] = method_ir
                    self.state["stats"]["total_methods"] += 1
                    self.state["files"][file_id]["methods"].append(mid)
                    self.state["classes"][class_id]["methods"].append(mid)
                    for edge in method_ir["edges"]:
                        self.state["edges"].append(edge)
                        tier = edge.get("certainty", UNKNOWN)
                        if tier == CERTAIN:
                            self.state["stats"]["certain_edges"] += 1
                        elif tier == PROBABLE:
                            self.state["stats"]["probable_edges"] += 1
                        else:
                            self.state["stats"]["unknown_edges"] += 1
        return (1, {
            "db_name": db_name,
            "classes_scanned": len(classes),
            "total_methods": self.state["stats"]["total_methods"],
            "total_classes": self.state["stats"]["total_classes"],
            "parse_errors": self.state["stats"]["parse_errors"],
            "workers": workers,
        }, None)

    def ScanDirParallel(self, params):
        root = self._p(params, "root") or self.state["config"]["scan_root"]
        workers = self._p(params, "workers", 8)
        if not root:
            return (0, None, ("MISSING_PARAM", "root required", 0))
        py_files = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fname in filenames:
                if fname.endswith(".py"):
                    py_files.append(os.path.join(dirpath, fname))
        self.state["stats"]["total_files"] = len(py_files)
        lock = threading.Lock()
        def parse_file(fpath):
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                    source = fh.read()
                tree = ast.parse(source, filename=fpath)
            except (SyntaxError, OSError) as exc:
                return ("PARSE_ERROR", fpath, str(exc))
            file_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
            file_id = fpath
            file_data = {
                "path": fpath,
                "hash": file_hash,
                "line_count": source.count("\n") + 1,
                "classes": [],
                "methods": [],
            }
            classes_out = []
            methods_out = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_result = self.ExtractClass({"node": node, "file_id": file_id, "source": source})
                    if class_result[0] == 1:
                        classes_out.append(class_result[1])
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not self._is_method_inside_class(node):
                        method_result = self.ExtractMethod({
                            "node": node, "file_id": file_id,
                            "class_id": None, "source": source,
                        })
                        if method_result[0] == 1:
                            methods_out.append(method_result[1])
            return ("OK", file_id, file_data, classes_out, methods_out)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(parse_file, fpath): fpath for fpath in py_files}
            for future in as_completed(futures):
                result = future.result()
                with lock:
                    if result[0] == "PARSE_ERROR":
                        self.state["errors"].append({"file": result[1], "error": ("PARSE_ERROR", result[2], 0)})
                        self.state["stats"]["parse_errors"] += 1
                        continue
                    _, file_id, file_data, classes_out, methods_out = result
                    self.state["files"][file_id] = file_data
                    for cls_data in classes_out:
                        cid = cls_data["class_id"]
                        self.state["classes"][cid] = cls_data
                        self.state["stats"]["total_classes"] += 1
                        self.state["files"][file_id]["classes"].append(cid)
                    for method_ir in methods_out:
                        mid = method_ir["id"]
                        self.state["methods"][mid] = method_ir
                        self.state["stats"]["total_methods"] += 1
                        self.state["files"][file_id]["methods"].append(mid)
                        for edge in method_ir["edges"]:
                            self.state["edges"].append(edge)
                            tier = edge.get("certainty", UNKNOWN)
                            if tier == CERTAIN:
                                self.state["stats"]["certain_edges"] += 1
                            elif tier == PROBABLE:
                                self.state["stats"]["probable_edges"] += 1
                            else:
                                self.state["stats"]["unknown_edges"] += 1
        return (1, {
            "files_scanned": len(py_files),
            "total_methods": self.state["stats"]["total_methods"],
            "total_classes": self.state["stats"]["total_classes"],
            "parse_errors": self.state["stats"]["parse_errors"],
            "workers": workers,
        }, None)

    def ExtractFile(self, params):
        path = self._p(params, "path")
        if not path:
            return (0, None, ("MISSING_PARAM", "path required", 0))
        if not os.path.isfile(path):
            return (0, None, ("FILE_NOT_FOUND", path, 0))
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                source = fh.read()
        except OSError as exc:
            return (0, None, ("READ_FAILED", str(exc), 0))
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            self.state["stats"]["parse_errors"] += 1
            return (0, None, ("PARSE_ERROR", str(exc), 0))
        file_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
        file_id = path
        self.state["files"][file_id] = {
            "path": path,
            "hash": file_hash,
            "line_count": source.count("\n") + 1,
            "classes": [],
            "methods": [],
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_result = self.ExtractClass({"node": node, "file_id": file_id, "source": source})
                if class_result[0] == 1:
                    self.state["files"][file_id]["classes"].append(class_result[1]["class_id"])
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not self._is_method_inside_class(node):
                    method_result = self.ExtractMethod({
                        "node": node, "file_id": file_id,
                        "class_id": None, "source": source,
                    })
                    if method_result[0] == 1:
                        self.state["files"][file_id]["methods"].append(method_result[1]["id"])
        return (1, {"file_id": file_id, "hash": file_hash,
                     "classes": len(self.state["files"][file_id]["classes"]),
                     "methods": len(self.state["files"][file_id]["methods"])}, None)

    def _is_method_inside_class(self, node):
        for parent in ast.walk(ast.parse("")):
            pass
        return False

    def ExtractClass(self, params):
        node = self._p(params, "node")
        file_id = self._p(params, "file_id")
        if not isinstance(node, ast.ClassDef):
            return (0, None, ("NOT_A_CLASS", "node must be ClassDef", 0))
        class_name = node.name
        class_id = file_id + "::" + class_name
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(self._attr_chain(base))
        method_ids = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_result = self.ExtractMethod({
                    "node": item, "file_id": file_id,
                    "class_id": class_id, "source": params.get("source", ""),
                })
                if method_result[0] == 1:
                    method_ids.append(method_result[1]["id"])
        self.state["classes"][class_id] = {
            "class_id": class_id,
            "name": class_name,
            "file_id": file_id,
            "bases": bases,
            "methods": method_ids,
            "line_start": node.lineno,
            "line_end": node.end_lineno or node.lineno,
        }
        self.state["stats"]["total_classes"] += 1
        return (1, self.state["classes"][class_id], None)

    def ExtractMethod(self, params):
        node = self._p(params, "node")
        file_id = self._p(params, "file_id")
        class_id = self._p(params, "class_id")
        source = self._p(params, "source", "")
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return (0, None, ("NOT_A_METHOD", "node must be FunctionDef or AsyncFunctionDef", 0))
        method_name = node.name
        if class_id:
            method_id = class_id + "." + method_name
        else:
            method_id = file_id + "::" + method_name
        inputs = self._extract_inputs(node)
        outputs = self._extract_outputs(node)
        body_source = self._get_body_source(node, source)
        ast_hash = hashlib.sha256(body_source.encode("utf-8")).hexdigest()[:16]
        edges = self.ExtractEdges({"node": node, "method_id": method_id, "class_id": class_id})
        source_method_id = self._p(params, "source_method_id")
        for edge in edges:
            edge["source_method_id"] = source_method_id
        ir = {
            "id": method_id,
            "name": method_name,
            "class_id": class_id,
            "file_id": file_id,
            "source_method_id": self._p(params, "source_method_id"),
            "line_start": node.lineno,
            "line_end": node.end_lineno or node.lineno,
            "inputs": inputs,
            "outputs": outputs,
            "ast_hash": ast_hash,
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "edges": edges,
            "control_flow": self._extract_control_flow(node),
            "purity_flags": self._extract_purity_flags(node, edges),
            "mutation_profile": self._extract_mutation_profile(node, edges),
            "exception_profile": self._extract_exception_profile(node),
            "method_type": None,  # filled by ClassifyMethod
            "deterministic_subset": None,  # filled by ClassifyMethod
            "certainty_summary": self._certainty_summary(edges),
        }
        self.state["methods"][method_id] = ir
        self.state["stats"]["total_methods"] += 1
        for edge in edges:
            self.state["edges"].append(edge)
            tier = edge.get("certainty", UNKNOWN)
            if tier == CERTAIN:
                self.state["stats"]["certain_edges"] += 1
            elif tier == PROBABLE:
                self.state["stats"]["probable_edges"] += 1
            else:
                self.state["stats"]["unknown_edges"] += 1
        return (1, ir, None)

    # ================================================================
    # EDGE EXTRACTION (section 20.3, 21.2, 23.2)
    # ================================================================

    def ExtractEdges(self, params):
        node = self._p(params, "node")
        method_id = self._p(params, "method_id")
        class_id = self._p(params, "class_id")
        edges = []
        call_func_ids = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_func_ids.add(id(child.func))
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                edge = self._extract_call_edge(child, method_id, class_id)
                if edge:
                    edges.append(edge)
            elif isinstance(child, ast.Subscript):
                if id(child) in call_func_ids:
                    continue
                edge = self._extract_state_edge(child, method_id, class_id)
                if edge:
                    edges.append(edge)
            elif isinstance(child, ast.Attribute):
                if id(child) in call_func_ids:
                    continue
                edge = self._extract_attr_state_edge(child, method_id, class_id)
                if edge:
                    edges.append(edge)
        return edges

    def _extract_call_edge(self, call_node, method_id, class_id):
        target = None
        certainty = UNKNOWN
        resolution = "unknown"
        edge_type = "CALL"
        func = call_node.func
        if isinstance(func, ast.Name):
            target = func.id
            certainty = PROBABLE
            resolution = "name_call"
        elif isinstance(func, ast.Attribute):
            attr_name = func.attr
            if isinstance(func.value, ast.Name):
                obj_name = func.value.id
                if obj_name == "self":
                    target = "self." + attr_name
                    certainty = CERTAIN
                    resolution = "self_method_call"
                else:
                    target = obj_name + "." + attr_name
                    certainty = PROBABLE
                    resolution = "attr_call"
            elif isinstance(func.value, ast.Attribute):
                chain = self._attr_chain(func.value)
                target = chain + "." + attr_name
                certainty = PROBABLE
                resolution = "nested_attr_call"
            elif isinstance(func.value, ast.Subscript):
                target = attr_name
                certainty = PROBABLE
                resolution = "subscript_method_call"
            elif isinstance(func.value, ast.BinOp):
                target = attr_name
                certainty = PROBABLE
                resolution = "binop_method_call"
            elif isinstance(func.value, ast.Constant):
                target = attr_name
                certainty = PROBABLE
                resolution = "literal_method_call"
            elif isinstance(func.value, ast.JoinedStr):
                target = attr_name
                certainty = PROBABLE
                resolution = "fstring_method_call"
            elif isinstance(func.value, ast.Call):
                target = self._call_chain(func.value) + "." + attr_name
                certainty = PROBABLE
                resolution = "constructor_call"
            elif isinstance(func.value, (ast.BoolOp, ast.Dict, ast.List,
                                         ast.Set, ast.Tuple, ast.DictComp,
                                         ast.ListComp, ast.SetComp,
                                         ast.GeneratorExp, ast.IfExp,
                                         ast.Await, ast.Yield, ast.YieldFrom,
                                         ast.Starred, ast.FormattedValue,
                                         ast.Slice, ast.Lambda, ast.Compare)):
                target = attr_name
                certainty = PROBABLE
                resolution = "expr_method_call"
            else:
                target = attr_name
                certainty = UNKNOWN
                resolution = "dynamic_dispatch"
        elif isinstance(func, ast.Subscript):
            target = "subscript_call"
            certainty = PROBABLE
            resolution = "subscript_dispatch"
        elif isinstance(func, ast.Call):
            target = "computed_call"
            certainty = PROBABLE
            resolution = "chained_call"
        else:
            target = "?"
            certainty = UNKNOWN
            resolution = "computed_dispatch"
        resource_type = self._detect_resource(func, call_node)
        if resource_type:
            edge_type = "RESOURCE"
            if certainty == UNKNOWN:
                certainty = PROBABLE
        return {
            "source": method_id,
            "target": target,
            "edge_type": edge_type,
            "certainty": certainty,
            "resolution": resolution,
            "resource_type": resource_type,
            "line": call_node.lineno,
        }

    def _extract_state_edge(self, subscript_node, method_id, class_id):
        if not isinstance(subscript_node.value, ast.Attribute):
            return None
        attr = subscript_node.value
        if not isinstance(attr.value, ast.Name) or attr.value.id != "self":
            return None
        if attr.attr != "state":
            return None
        key = None
        certainty = UNKNOWN
        ctx = "read"
        if isinstance(subscript_node.ctx, ast.Store):
            ctx = "write"
        sl = subscript_node.slice
        if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
            key = sl.value
            certainty = CERTAIN
        elif isinstance(sl, ast.Name):
            key = "var:" + sl.id
            certainty = PROBABLE
        elif isinstance(sl, ast.Attribute):
            chain = self._attr_chain(sl)
            key = "attr:" + chain
            certainty = PROBABLE
        else:
            key = "expr"
            certainty = UNKNOWN
        return {
            "source": method_id,
            "target": "self.state[" + str(key) + "]",
            "edge_type": "STATE_" + ctx.upper(),
            "certainty": certainty,
            "resolution": "literal_key" if certainty == CERTAIN else "dynamic_key",
            "resource_type": None,
            "line": subscript_node.lineno,
        }

    def _extract_attr_state_edge(self, attr_node, method_id, class_id):
        if not isinstance(attr_node.value, ast.Name) or attr_node.value.id != "self":
            return None
        if attr_node.attr == "state":
            return None
        ctx = "read"
        if isinstance(attr_node.ctx, ast.Store):
            ctx = "write"
        return {
            "source": method_id,
            "target": "self." + attr_node.attr,
            "edge_type": "STATE_" + ctx.upper(),
            "certainty": CERTAIN,
            "resolution": "self_attr",
            "resource_type": None,
            "line": getattr(attr_node, "lineno", 0),
        }

    def _detect_resource(self, func, call_node):
        func_name = ""
        obj_name = ""
        if isinstance(func, ast.Name):
            func_name = func.id
            obj_name = ""
        elif isinstance(func, ast.Attribute):
            func_name = func.attr
            if isinstance(func.value, ast.Name):
                obj_name = func.value.id
            elif isinstance(func.value, ast.Attribute):
                obj_name = func.value.attr
            else:
                obj_name = ""
        if func_name in ("get", "post", "put", "delete"):
            if obj_name in ("requests", "http", "urllib", "session", "client", "api"):
                return "NET"
            return None
        if func_name == "connect":
            if obj_name in ("sqlite3", "conn", "db", "cursor", "database"):
                return "DB"
            if obj_name in ("socket", "s", "sock"):
                return "NET"
            return None
        if func_name in ("execute", "commit", "rollback", "fetchall", "fetchone", "cursor"):
            if obj_name in ("cur", "cursor", "conn", "db", "conn"):
                return "DB"
            if obj_name in ("self",):
                return None
            return "DB"
        if func_name in ("insert", "update", "delete", "select"):
            if obj_name in ("db", "conn", "cur", "cursor", "table"):
                return "DB"
            return None
        if func_name == "open":
            return "FILE"
        if func_name in ("read", "write", "read_text", "write_text", "read_bytes", "write_bytes"):
            if obj_name in ("file", "fh", "f", "handle", "Path", "path", "p"):
                return "FILE"
            if obj_name in ("self",):
                return None
            return None
        if func_name in ("remove", "rename", "unlink", "mkdir", "rmdir"):
            if obj_name in ("os", "path", "Path", "shutil"):
                return "FILE"
            return None
        if func_name in ("system", "popen", "Popen", "run", "call", "check_output", "check_call"):
            if obj_name in ("subprocess", "os"):
                return "PROCESS"
            return None
        if func_name in ("getenv", "environ"):
            if obj_name in ("os",):
                return "PROCESS"
            return None
        if func_name in ("socket",):
            return "NET"
        if func_name in ("send", "recv"):
            if obj_name in ("socket", "sock", "s", "conn"):
                return "NET"
            return None
        if func_name in ("urlopen",):
            return "NET"
        return None

    # ================================================================
    # CONTROL FLOW, PURITY, MUTATION, EXCEPTIONS (section 20.2)
    # ================================================================

    def _extract_control_flow(self, node):
        has_branch = False
        has_loop = False
        has_recursion = False
        method_name = node.name
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.IfExp)):
                has_branch = True
            elif isinstance(child, (ast.For, ast.While)):
                has_loop = True
            elif isinstance(child, ast.Call):
                target = None
                if isinstance(child.func, ast.Name) and child.func.id == method_name:
                    has_recursion = True
                elif isinstance(child.func, ast.Attribute) and child.func.attr == method_name:
                    if isinstance(child.func.value, ast.Name) and child.func.value.id == "self":
                        has_recursion = True
        return {"branching": has_branch, "loops": has_loop, "recursion": has_recursion}

    def _extract_purity_flags(self, node, edges):
        has_resource = any(e["edge_type"] == "RESOURCE" for e in edges)
        has_external = any(e["certainty"] == UNKNOWN and e["edge_type"] == "CALL" for e in edges)
        is_pure_math = True
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                is_pure_math = False
                break
        return {
            "pure_math": is_pure_math and not has_resource,
            "deterministic_math": is_pure_math and not has_resource,
            "external_dependency": has_resource or has_external,
        }

    def _extract_mutation_profile(self, node, edges):
        has_state_write = any(e["edge_type"] == "STATE_WRITE" for e in edges)
        has_resource = any(e["edge_type"] == "RESOURCE" for e in edges)
        has_local_mutation = False
        for child in ast.walk(node):
            if isinstance(child, ast.AugAssign):
                has_local_mutation = True
        return {
            "mutates_local": has_local_mutation,
            "mutates_global_state": has_state_write,
            "mutates_external": has_resource,
        }

    def _extract_exception_profile(self, node):
        has_raise = False
        has_handle = False
        for child in ast.walk(node):
            if isinstance(child, ast.Raise):
                has_raise = True
            elif isinstance(child, ast.ExceptHandler):
                has_handle = True
        return {"throws_exceptions": has_raise, "handles_exceptions": has_handle}

    # ================================================================
    # CERTAINTY SUMMARY (section 23.9)
    # ================================================================

    def _certainty_summary(self, edges):
        certain = sum(1 for e in edges if e["certainty"] == CERTAIN)
        probable = sum(1 for e in edges if e["certainty"] == PROBABLE)
        unknown = sum(1 for e in edges if e["certainty"] == UNKNOWN)
        has_unknown_state = any(e["edge_type"].startswith("STATE_") and e["certainty"] == UNKNOWN for e in edges)
        has_unknown_resource = any(e["edge_type"] == "RESOURCE" and e["certainty"] == UNKNOWN for e in edges)
        has_unknown_dispatch = any(e["edge_type"] == "CALL" and e["certainty"] == UNKNOWN for e in edges)
        return {
            "certain_count": certain,
            "probable_count": probable,
            "unknown_count": unknown,
            "is_state_opaque": has_unknown_state,
            "is_io_opaque": has_unknown_resource,
            "is_dispatch_opaque": has_unknown_dispatch,
        }

    # ================================================================
    # CLASSIFICATION (section 20.4, 20.5, 21.4, 25.8)
    # ================================================================

    def ClassifyAll(self, params):
        for method_id, ir in self.state["methods"].items():
            self.ClassifyMethod({"method_id": method_id})
        return (1, {"classified": self.state["stats"]["total_methods"],
                     "type_counts": self.state["stats"]["type_counts"],
                     "deterministic_subset": self.state["stats"]["deterministic_subset_count"]}, None)

    def ClassifyMethod(self, params):
        method_id = self._p(params, "method_id")
        if method_id not in self.state["methods"]:
            return (0, None, ("NOT_FOUND", method_id, 0))
        ir = self.state["methods"][method_id]
        edges = ir["edges"]
        name = ir["name"]
        has_certain_or_probable_resource = any(
            e["edge_type"] == "RESOURCE" and e["certainty"] in (CERTAIN, PROBABLE)
            for e in edges
        )
        has_certain_or_probable_orchestration = any(
            e["edge_type"] in ("PIPE", "EVENT", "CALLBACK", "FUTURE") and
            e["certainty"] in (CERTAIN, PROBABLE)
            for e in edges
        )
        has_cross_boundary_call = False
        if ir["class_id"]:
            for e in edges:
                if e["edge_type"] == "CALL" and e["certainty"] in (CERTAIN, PROBABLE):
                    target = e["target"]
                    if target and not target.startswith("self.") and "." in target:
                        if not self._is_builtin_or_stdlib_call(target):
                            has_cross_boundary_call = True
        mutates_external = ir["mutation_profile"]["mutates_external"]
        method_type = None
        if name in INIT_PATTERNS and ir["mutation_profile"]["mutates_global_state"]:
            method_type = TYPE_INIT
        elif name in CLEANUP_PATTERNS:
            method_type = TYPE_CLEANUP
        elif has_certain_or_probable_resource or mutates_external:
            method_type = TYPE_IO
        elif has_certain_or_probable_orchestration or has_cross_boundary_call:
            method_type = TYPE_LINK
        else:
            method_type = TYPE_CORE
        det_subset = self._compute_deterministic_subset(ir, edges)
        ir["method_type"] = method_type
        ir["deterministic_subset"] = det_subset
        self.state["stats"]["type_counts"][method_type] = self.state["stats"]["type_counts"].get(method_type, 0) + 1
        if det_subset:
            self.state["stats"]["deterministic_subset_count"] += 1
        return (1, {"method_id": method_id, "type": method_type,
                     "deterministic_subset": det_subset}, None)

    # Builtin function names (not cross-class calls)
    BUILTIN_FUNCS = frozenset((
        "len", "isinstance", "str", "dict", "list", "set", "tuple", "int",
        "float", "bool", "print", "range", "enumerate", "zip", "map", "filter",
        "sorted", "reversed", "min", "max", "sum", "abs", "round", "hash",
        "type", "repr", "format", "open", "super", "getattr", "setattr",
        "hasattr", "vars", "dir", "id", "callable", "iter", "next", "any",
        "all", "frozenset", "bytes", "bytearray", "complex", "object",
        "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
        "AttributeError", "RuntimeError", "StopIteration", "NotImplementedError",
        "OSError", "IOError", "NameError", "ZeroDivisionError", "FileNotFoundError",
    ))

    # Builtin method names on local variables (string/list/dict methods)
    BUILTIN_METHODS = frozenset((
        "append", "extend", "insert", "remove", "pop", "clear", "update",
        "copy", "items", "keys", "values", "get", "setdefault", "popitem",
        "lower", "upper", "strip", "lstrip", "rstrip", "split", "rsplit",
        "join", "replace", "find", "rfind", "startswith", "endswith",
        "encode", "decode", "count", "index", "isdigit", "isalpha",
        "isalnum", "isspace", "title", "capitalize", "format", "zfill",
        "ljust", "rjust", "center", "partition", "rpartition", "splitlines",
        "swapcase", "expandtabs", "islower", "isupper", "istitle",
        "add", "discard", "difference", "intersection", "union",
        "symmetric_difference", "issubset", "issuperset",
        "sort", "reverse",
    ))

    # Standard library module names
    STDLIB_MODULES = frozenset((
        "os", "sys", "json", "re", "time", "datetime", "hashlib", "sqlite3",
        "subprocess", "logging", "traceback", "collections", "functools",
        "itertools", "math", "random", "struct", "io", "csv", "shutil",
        "tempfile", "importlib", "typing", "ast", "inspect", "textwrap",
        "copy", "pprint", "uuid", "base64", "configparser", "argparse",
        "threading", "queue", "asyncio", "socket", "signal", "gc",
        "weakref", "enum", "abc", "dataclasses", "pathlib", "tkinter",
        "tk", "decimal", "fractions", "statistics", "array", "bisect",
        "heapq", "operator", "string", "unicodedata", "codecs",
        "concurrent", "multiprocessing", "select", "ssl", "http",
        "urllib", "email", "html", "xml", "htmlparser", "calendar",
        "locale", "gettext", "platform", "getpass", "glob", "fnmatch",
    ))

    def _is_builtin_or_stdlib_call(self, target):
        if not target or "." not in target:
            return target in self.BUILTIN_FUNCS
        parts = target.split(".")
        first = parts[0]
        last = parts[-1]
        if first in self.STDLIB_MODULES:
            return True
        if first in self.BUILTIN_FUNCS:
            return True
        if last in self.BUILTIN_METHODS:
            return True
        if first in ("self", "cls"):
            return True
        return False

    def _compute_deterministic_subset(self, ir, edges):
        all_certain = all(e["certainty"] == CERTAIN for e in edges) if edges else True
        no_resource = not any(e["edge_type"] == "RESOURCE" for e in edges)
        no_unknown_state = not ir["certainty_summary"]["is_state_opaque"]
        no_async = not ir["is_async"]
        no_external = not ir["purity_flags"]["external_dependency"]
        return all_certain and no_resource and no_unknown_state and no_async and no_external

    # ================================================================
    # GRAPH BUILDING (section 22)
    # ================================================================

    def BuildGraph(self, params):
        call_graph = defaultdict(list)
        state_graph = defaultdict(list)
        resource_graph = defaultdict(list)
        for edge in self.state["edges"]:
            src = edge["source"]
            if edge["edge_type"] == "CALL":
                call_graph[src].append(edge)
            elif edge["edge_type"].startswith("STATE_"):
                state_graph[src].append(edge)
            elif edge["edge_type"] == "RESOURCE":
                resource_graph[src].append(edge)
        self.state["call_graph"] = dict(call_graph)
        self.state["state_graph"] = dict(state_graph)
        self.state["resource_graph"] = dict(resource_graph)
        return (1, {
            "call_edges": sum(len(v) for v in call_graph.values()),
            "state_edges": sum(len(v) for v in state_graph.values()),
            "resource_edges": sum(len(v) for v in resource_graph.values()),
        }, None)

    # ================================================================
    # REPORTING (section 23.10, 25.10)
    # ================================================================

    def Report(self, params):
        stats = self.state["stats"]
        total_edges = stats["certain_edges"] + stats["probable_edges"] + stats["unknown_edges"]
        certain_pct = (stats["certain_edges"] / total_edges * 100) if total_edges else 0
        probable_pct = (stats["probable_edges"] / total_edges * 100) if total_edges else 0
        unknown_pct = (stats["unknown_edges"] / total_edges * 100) if total_edges else 0
        det_pct = (stats["deterministic_subset_count"] / stats["total_methods"] * 100) if stats["total_methods"] else 0
        report = {
            "total_files": stats["total_files"],
            "total_classes": stats["total_classes"],
            "total_methods": stats["total_methods"],
            "total_edges": total_edges,
            "edge_certainty": {
                "CERTAIN": stats["certain_edges"],
                "PROBABLE": stats["probable_edges"],
                "UNKNOWN": stats["unknown_edges"],
                "certain_pct": round(certain_pct, 1),
                "probable_pct": round(probable_pct, 1),
                "unknown_pct": round(unknown_pct, 1),
            },
            "method_types": stats["type_counts"],
            "deterministic_subset": {
                "count": stats["deterministic_subset_count"],
                "pct": round(det_pct, 1),
            },
            "parse_errors": stats["parse_errors"],
            "errors": self.state["errors"][:10],
        }
        return (1, report, None)

    # ================================================================
    # HELPERS
    # ================================================================

    def _extract_inputs(self, node):
        inputs = []
        args = node.args
        for arg in args.args:
            type_ann = None
            if arg.annotation and isinstance(arg.annotation, ast.Name):
                type_ann = arg.annotation.id
            inputs.append({"name": arg.arg, "type": type_ann})
        if args.vararg:
            inputs.append({"name": args.vararg.arg, "type": "*args"})
        if args.kwarg:
            inputs.append({"name": args.kwarg.arg, "type": "**kwargs"})
        return inputs

    def _extract_outputs(self, node):
        returns = []
        if node.returns:
            if isinstance(node.returns, ast.Name):
                returns.append(node.returns.id)
            elif isinstance(node.returns, ast.Tuple):
                for elt in node.returns.elts:
                    if isinstance(elt, ast.Name):
                        returns.append(elt.id)
        return returns

    def _get_body_source(self, node, source):
        if not source:
            return ""
        lines = source.splitlines()
        start = node.lineno - 1
        end = node.end_lineno or node.lineno
        return "\n".join(lines[start:end])

    def _attr_chain(self, node):
        if isinstance(node, ast.Attribute):
            return self._attr_chain(node.value) + "." + node.attr
        if isinstance(node, ast.Name):
            return node.id
        return "?"

    def _call_chain(self, call_node):
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        if isinstance(call_node.func, ast.Attribute):
            return self._attr_chain(call_node.func)
        return "?"
