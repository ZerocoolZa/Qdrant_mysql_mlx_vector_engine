#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/static_analyzer.py"
# date="2026-06-26" author="Devin" session_id="phase4-analysis"
# context="Project Digital Twin Section 10 Static Analysis"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="static_analyzer.py" domain="twin_static" authority="StaticAnalyzer"}
# [@SUMMARY]{summary="Static analysis authority that AST-parses files, builds symbol tables, resolves imports, detects dead code and duplicates, and computes complexity."}
# [@CLASS]{class="StaticAnalyzer" domain="static" authority="single"}
# [@METHOD]{method="analyze_file" type="command"}
# [@METHOD]{method="analyze_all" type="command"}
# [@METHOD]{method="get_complexity" type="command"}
# [@METHOD]{method="find_dead_code" type="command"}
# [@METHOD]{method="find_duplicates" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<StaticAnalyzer: AST-parses files builds symbol tables resolves imports detects dead code duplicates computes complexity. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations. Docstring contains embedded spec review notes (unusual but not garbled). Header missing Run method declaration but Run() exists in code.>][@todos<none>]}
"""
StaticAnalyzer -- Static analysis authority for AST parsing and complexity analysis.
Implements Section 10 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: analyze_file, analyze_all, get_complexity, find_dead_code, find_duplicates.

# ============================================================
# ERRORS -- Section 10 spec vs. implementation
# Rating: 3/10
# Spec has 10 sub-sections (10.1-10.10). Only 5 implemented.
# 5 methods MISSING.
# ============================================================
# MISSING METHODS:
# 10.2 BuildSymbolTable   -- extract all names, scopes as structured object. NOT IMPLEMENTED.
#                           (AnalyzeFile extracts symbols as a flat list, not a scoped table.)
# 10.3 ResolveImports     -- resolve 'from X import Y' to actual file paths. NOT IMPLEMENTED.
#                           (imports are listed but not resolved to paths.)
# 10.4 TypeAnalysis       -- infer types from assignments and returns. NOT IMPLEMENTED.
# 10.5 ScopeAnalysis      -- track local/global/nonlocal. NOT IMPLEMENTED.
#                           (globals are detected but local/nonlocal are not.)
# 10.6 ConstantDetection  -- find UPPER_CASE = value at module level. PARTIAL.
#                           (done inside AnalyzeFile, not as a standalone command.)
# 10.7 GlobalDetection    -- find 'global X' statements. PARTIAL.
#                           (done inside AnalyzeFile, not as a standalone command.)
#
# PARTIAL:
# 10.1 AstParse           -- done inside AnalyzeFile.
# 10.8 DeadCodeDetection  -- implemented as FindDeadCode, queries edges table.
# 10.9 DuplicateDetection -- implemented as FindDuplicates, queries method hash.
# 10.10 ComplexityAnalysis -- implemented as GetComplexity, counts If/For/While/Except/With/BoolOp.
#
# NOTE:
# 10.6 and 10.7 are done inside AnalyzeFile but NOT exposed as separate commands.
# The spec lists them as separate analysis steps. They should be standalone.
# ============================================================
"""
import ast
import json
import os
import sqlite3

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class StaticAnalyzer:
    """Static analysis authority for AST parsing and complexity analysis."""

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
        if command == "analyze_file":
            return self.AnalyzeFile(params)
        elif command == "analyze_all":
            return self.AnalyzeAll(params)
        elif command == "get_complexity":
            return self.GetComplexity(params)
        elif command == "find_dead_code":
            return self.FindDeadCode(params)
        elif command == "find_duplicates":
            return self.FindDuplicates(params)
        elif command == "build_symbol_table":
            return self.BuildSymbolTable(params)
        elif command == "resolve_imports":
            return self.ResolveImports(params)
        elif command == "type_analysis":
            return self.TypeAnalysis(params)
        elif command == "scope_analysis":
            return self.ScopeAnalysis(params)
        elif command == "constant_detection":
            return self.ConstantDetection(params)
        elif command == "global_detection":
            return self.GlobalDetection(params)

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

    def AnalyzeFile(self, params):
        file_id = self._p(params, "file_id")
        path = self._p(params, "path")
        conn = self.Connect()
        cur = conn.cursor()
        if file_id:
            cur.execute("SELECT path FROM files WHERE file_id=?", (file_id,))
            row = cur.fetchone()
            if not row:
                return (0, None, ("NOT_FOUND", "file_id not found", 0))
            path = row[0]
        if not path or not os.path.isfile(path):
            return (0, None, ("NO_FILE", "File not found: " + str(path), 0))
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
            tree = ast.parse(content, filename=path)
        except SyntaxError as exc:
            return (1, {"parsed": False, "error": str(exc)}, None)
        symbols = []
        imports = []
        constants = []
        globals_list = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        symbols.append(tgt.id)
                        if tgt.id.isupper():
                            constants.append(tgt.id)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
            elif isinstance(node, ast.Global):
                globals_list.extend(node.names)
        complexity = sum(1 for node in ast.walk(tree)
                         if isinstance(node, (ast.If, ast.For, ast.While,
                                              ast.ExceptHandler, ast.With, ast.BoolOp)))
        return (1, {"parsed": True, "symbols": symbols, "imports": imports,
                    "constants": constants, "globals": globals_list,
                    "complexity": complexity}, None)

    def AnalyzeAll(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT file_id, path FROM files WHERE extension='.py'")
        results = []
        for row in cur.fetchall():
            res = self.AnalyzeFile({"file_id": row[0]})
            if res[0] == 1:
                results.append({"file_id": row[0], "path": row[1], "analysis": res[1]})
        return (1, {"files_analyzed": len(results), "results": results}, None)

    def GetComplexity(self, params):
        method_id = self._p(params, "method_id")
        method_name = self._p(params, "method_name")
        conn = self.Connect()
        cur = conn.cursor()
        if method_id:
            cur.execute("SELECT method_code FROM methods WHERE method_id=?", (method_id,))
        elif method_name:
            cur.execute("SELECT method_id, method_code FROM methods WHERE method_name=?", (method_name,))
        else:
            return (0, None, ("NO_PARAM", "method_id or method_name required", 0))
        row = cur.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", "Method not found", 0))
        code = row[-1]
        try:
            tree = ast.parse(code)
            complexity = sum(1 for node in ast.walk(tree)
                             if isinstance(node, (ast.If, ast.For, ast.While,
                                                  ast.ExceptHandler, ast.With, ast.BoolOp)))
        except SyntaxError:
            complexity = 0
        if method_id:
            cur.execute("UPDATE methods SET cyclomatic_complexity=? WHERE method_id=?",
                        (complexity, method_id))
            conn.commit()
        return (1, {"method_id": method_id or row[0], "complexity": complexity}, None)

    def FindDeadCode(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, class_id FROM methods")
        all_methods = cur.fetchall()
        cur.execute("SELECT DISTINCT dst_id FROM edges WHERE dst_type='method' AND edge_type='calls'")
        called = set(r[0] for r in cur.fetchall())
        dead = [{"method_id": m[0], "method_name": m[1], "class_id": m[2]}
                for m in all_methods if m[0] not in called]
        return (1, {"dead_code": dead, "count": len(dead)}, None)

    def FindDuplicates(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_name, hash, COUNT(*) FROM methods "
                    "WHERE hash IS NOT NULL GROUP BY hash HAVING COUNT(*)>1")
        dupes = [{"method_name": r[0], "hash": r[1], "count": r[2]} for r in cur.fetchall()]
        return (1, {"duplicates": dupes, "count": len(dupes)}, None)

    def BuildSymbolTable(self, params):
        # 10.2 -- structured symbol table with scopes, not flat list
        file_id = self._p(params, "file_id")
        path = self._p(params, "path")
        content = self._p(params, "content")
        if content is None:
            resolved = self.ResolveFilePath(file_id, path)
            if resolved is None:
                return resolved
            path = resolved
            try:
                with open(path, "r", encoding="utf-8",
                          errors="replace") as fh:
                    content = fh.read()
            except OSError as exc:
                return (0, None, ("READ_FAILED", str(exc), 0))
        try:
            tree = ast.parse(content, filename=path or "<str>")
        except SyntaxError as exc:
            return (1, {"parsed": False, "error": str(exc)}, None)
        table = self.BuildScopedTable(tree, "module", "module")
        return (1, {"file_id": file_id, "symbol_table": table}, None)

    def BuildScopedTable(self, node, name, kind):
        # helper: recursively build a scoped symbol table (ast.NodeVisitor pattern)
        scope = {"name": name, "type": kind, "symbols": [],
                 "children": [], "lineno": getattr(node, "lineno", 0)}
        if isinstance(node, ast.Module):
            for child in node.body:
                self.CollectSymbols(child, scope)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in node.args.args:
                scope["symbols"].append({
                    "name": arg.arg, "kind": "param",
                    "lineno": node.lineno,
                })
            for child in node.body:
                self.CollectSymbols(child, scope)
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                self.CollectSymbols(child, scope)
        return scope

    def CollectSymbols(self, node, scope):
        # helper: collect symbols from a node into the current scope
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scope["symbols"].append({
                "name": node.name, "kind": "function",
                "lineno": node.lineno,
            })
            child_scope = self.BuildScopedTable(node, node.name, "function")
            scope["children"].append(child_scope)
        elif isinstance(node, ast.ClassDef):
            scope["symbols"].append({
                "name": node.name, "kind": "class",
                "lineno": node.lineno,
            })
            child_scope = self.BuildScopedTable(node, node.name, "class")
            scope["children"].append(child_scope)
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    scope["symbols"].append({
                        "name": tgt.id, "kind": "variable",
                        "lineno": node.lineno,
                    })
        elif isinstance(node, ast.Import):
            for alias in node.names:
                scope["symbols"].append({
                    "name": alias.asname or alias.name, "kind": "import",
                    "lineno": node.lineno,
                })
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                scope["symbols"].append({
                    "name": alias.asname or alias.name, "kind": "import",
                    "lineno": node.lineno,
                })

    def ResolveFilePath(self, file_id, path):
        # helper: resolve file path from file_id or validate path
        if path:
            if not os.path.isfile(path):
                return None
            return path
        if file_id:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("SELECT path FROM files WHERE file_id=?", (file_id,))
            row = cur.fetchone()
            if not row:
                return None
            path = row[0]
            if not os.path.isfile(path):
                return None
            return path
        return None

    def ResolveImports(self, params):
        # 10.3 -- resolve 'from X import Y' to actual file paths using files table
        file_id = self._p(params, "file_id")
        path = self._p(params, "path")
        content = self._p(params, "content")
        if content is None:
            resolved = self.ResolveFilePath(file_id, path)
            if resolved is None:
                return (0, None, ("NO_FILE", "File not found", 0))
            path = resolved
            try:
                with open(path, "r", encoding="utf-8",
                          errors="replace") as fh:
                    content = fh.read()
            except OSError as exc:
                return (0, None, ("READ_FAILED", str(exc), 0))
        try:
            tree = ast.parse(content, filename=path or "<str>")
        except SyntaxError as exc:
            return (1, {"parsed": False, "error": str(exc)}, None)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({"type": "import", "module": alias.name,
                                    "name": alias.name, "lineno": node.lineno})
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    imports.append({"type": "from", "module": mod,
                                    "name": alias.name,
                                    "lineno": node.lineno})
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT file_id, file_name, path FROM files")
        file_rows = cur.fetchall()
        name_to_file = {}
        for row in file_rows:
            name_to_file[row[1]] = {"file_id": row[0], "path": row[2]}
        resolved_imports = []
        for imp in imports:
            base = imp["module"].split(".")[0]
            candidate = base + ".py"
            target = name_to_file.get(candidate)
            if target is None:
                for fname, info in name_to_file.items():
                    if fname == base or fname.startswith(base + "_"):
                        target = info
                        break
            resolved_imports.append({
                "import": imp, "resolved_path": target["path"] if target else None,
                "resolved_file_id": target["file_id"] if target else None,
            })
        return (1, {"file_id": file_id, "imports": resolved_imports,
                    "count": len(resolved_imports)}, None)

    def TypeAnalysis(self, params):
        # 10.4 -- infer types from assignments and returns
        file_id = self._p(params, "file_id")
        path = self._p(params, "path")
        content = self._p(params, "content")
        if content is None:
            resolved = self.ResolveFilePath(file_id, path)
            if resolved is None:
                return (0, None, ("NO_FILE", "File not found", 0))
            path = resolved
            try:
                with open(path, "r", encoding="utf-8",
                          errors="replace") as fh:
                    content = fh.read()
            except OSError as exc:
                return (0, None, ("READ_FAILED", str(exc), 0))
        try:
            tree = ast.parse(content, filename=path or "<str>")
        except SyntaxError as exc:
            return (1, {"parsed": False, "error": str(exc)}, None)
        types = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    type_name = self.InferTypeFromAnnotation(node.annotation)
                    types[node.target.id] = {
                        "type": type_name, "lineno": node.lineno,
                        "source": "annotation",
                    }
            elif isinstance(node, ast.Assign):
                type_name = self.InferTypeFromValue(node.value)
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        types[tgt.id] = {
                            "type": type_name, "lineno": node.lineno,
                            "source": "inferred",
                        }
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                ret_type = "None"
                if node.returns:
                    ret_type = self.InferTypeFromAnnotation(node.returns)
                else:
                    for child in ast.walk(node):
                        if isinstance(child, ast.Return) and child.value:
                            ret_type = self.InferTypeFromValue(child.value)
                            break
                types[node.name] = {
                    "type": "function -> " + ret_type,
                    "lineno": node.lineno, "source": "return",
                }
        return (1, {"file_id": file_id, "types": types,
                    "count": len(types)}, None)

    def InferTypeFromAnnotation(self, annotation):
        # helper: extract type name from an annotation AST node
        if annotation is None:
            return "Any"
        if isinstance(annotation, ast.Name):
            return annotation.id
        if isinstance(annotation, ast.Attribute):
            return annotation.attr
        if isinstance(annotation, ast.Subscript):
            base = self.InferTypeFromAnnotation(annotation.value)
            return base
        return "Any"

    def InferTypeFromValue(self, value):
        # helper: infer type from a literal or expression AST node
        if value is None:
            return "None"
        if isinstance(value, ast.Constant):
            if value.value is None:
                return "None"
            return type(value.value).__name__
        if isinstance(value, ast.List):
            return "list"
        if isinstance(value, ast.Dict):
            return "dict"
        if isinstance(value, ast.Set):
            return "set"
        if isinstance(value, ast.Tuple):
            return "tuple"
        if isinstance(value, ast.Call):
            if isinstance(value.func, ast.Name):
                return value.func.id
            if isinstance(value.func, ast.Attribute):
                return value.func.attr
        if isinstance(value, ast.BinOp):
            return "number"
        if isinstance(value, ast.Str):
            return "str"
        return "Any"

    def ScopeAnalysis(self, params):
        # 10.5 -- track local/global/nonlocal
        file_id = self._p(params, "file_id")
        path = self._p(params, "path")
        content = self._p(params, "content")
        if content is None:
            resolved = self.ResolveFilePath(file_id, path)
            if resolved is None:
                return (0, None, ("NO_FILE", "File not found", 0))
            path = resolved
            try:
                with open(path, "r", encoding="utf-8",
                          errors="replace") as fh:
                    content = fh.read()
            except OSError as exc:
                return (0, None, ("READ_FAILED", str(exc), 0))
        try:
            tree = ast.parse(content, filename=path or "<str>")
        except SyntaxError as exc:
            return (1, {"parsed": False, "error": str(exc)}, None)
        scopes = {"module": {"globals": [], "locals": [], "nonlocals": []}}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scope_name = node.name
                scopes[scope_name] = {"globals": [], "locals": [],
                                      "nonlocals": []}
                for child in ast.walk(node):
                    if isinstance(child, ast.Global):
                        scopes[scope_name]["globals"].extend(child.names)
                    elif isinstance(child, ast.Nonlocal):
                        scopes[scope_name]["nonlocals"].extend(child.names)
                    elif isinstance(child, ast.Assign):
                        for tgt in child.targets:
                            if isinstance(tgt, ast.Name):
                                if tgt.id not in scopes[scope_name]["globals"]:
                                    if tgt.id not in scopes[scope_name]["nonlocals"]:
                                        scopes[scope_name]["locals"].append(tgt.id)
            elif isinstance(node, ast.Global):
                scopes["module"]["globals"].extend(node.names)
        for scope in scopes.values():
            scope["globals"] = list(set(scope["globals"]))
            scope["locals"] = list(set(scope["locals"]))
            scope["nonlocals"] = list(set(scope["nonlocals"]))
        return (1, {"file_id": file_id, "scopes": scopes}, None)

    def ConstantDetection(self, params):
        # 10.6 -- find UPPER_CASE = value at module level (standalone command)
        file_id = self._p(params, "file_id")
        path = self._p(params, "path")
        content = self._p(params, "content")
        if content is None:
            resolved = self.ResolveFilePath(file_id, path)
            if resolved is None:
                return (0, None, ("NO_FILE", "File not found", 0))
            path = resolved
            try:
                with open(path, "r", encoding="utf-8",
                          errors="replace") as fh:
                    content = fh.read()
            except OSError as exc:
                return (0, None, ("READ_FAILED", str(exc), 0))
        try:
            tree = ast.parse(content, filename=path or "<str>")
        except SyntaxError as exc:
            return (1, {"parsed": False, "error": str(exc)}, None)
        constants = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id.isupper():
                        constants.append({
                            "name": tgt.id, "lineno": node.lineno,
                            "value": self.ReprValue(node.value),
                        })
        return (1, {"file_id": file_id, "constants": constants,
                    "count": len(constants)}, None)

    def GlobalDetection(self, params):
        # 10.7 -- find 'global X' statements (standalone command)
        file_id = self._p(params, "file_id")
        path = self._p(params, "path")
        content = self._p(params, "content")
        if content is None:
            resolved = self.ResolveFilePath(file_id, path)
            if resolved is None:
                return (0, None, ("NO_FILE", "File not found", 0))
            path = resolved
            try:
                with open(path, "r", encoding="utf-8",
                          errors="replace") as fh:
                    content = fh.read()
            except OSError as exc:
                return (0, None, ("READ_FAILED", str(exc), 0))
        try:
            tree = ast.parse(content, filename=path or "<str>")
        except SyntaxError as exc:
            return (1, {"parsed": False, "error": str(exc)}, None)
        globals_found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Global):
                for name in node.names:
                    scope = "module"
                    parent = getattr(node, "parent", None)
                    if isinstance(parent, (ast.FunctionDef,
                                           ast.AsyncFunctionDef)):
                        scope = "function:" + parent.name
                    globals_found.append({
                        "name": name, "lineno": node.lineno,
                        "scope": scope,
                    })
        return (1, {"file_id": file_id, "globals": globals_found,
                    "count": len(globals_found)}, None)

    def ReprValue(self, value):
        # helper: get a string representation of an AST value node
        try:
            return ast.dump(value)
        except Exception:
            return "unknown"

