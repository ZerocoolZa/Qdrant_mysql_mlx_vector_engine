#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/static_analysis_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 10: Static Analysis -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="static_analysis_engine.py" domain="twin_static" authority="StaticAnalysisEngine"}
# [@SUMMARY]{summary="Static analysis authority: ast parse, symbol table, import resolution, type analysis, scope analysis, constant detection, global detection, dead code detection, duplicate detection, complexity analysis."}
# [@CLASS]{class="StaticAnalysisEngine" domain="static" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="ast_parse" type="command"}
# [@METHOD]{method="symbol_table" type="command"}
# [@METHOD]{method="import_resolution" type="command"}
# [@METHOD]{method="type_analysis" type="command"}
# [@METHOD]{method="scope_analysis" type="command"}
# [@METHOD]{method="constant_detection" type="command"}
# [@METHOD]{method="global_detection" type="command"}
# [@METHOD]{method="dead_code_detection" type="command"}
# [@METHOD]{method="duplicate_detection" type="command"}
# [@METHOD]{method="complexity_analysis" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import ast
import os
import re
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class StaticAnalysisEngine:
    """Authority for static code analysis."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
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
        if command == "ast_parse":
            return self.AstParse(params)
        elif command == "symbol_table":
            return self.SymbolTable(params)
        elif command == "import_resolution":
            return self.ImportResolution(params)
        elif command == "type_analysis":
            return self.TypeAnalysis(params)
        elif command == "scope_analysis":
            return self.ScopeAnalysis(params)
        elif command == "constant_detection":
            return self.ConstantDetection(params)
        elif command == "global_detection":
            return self.GlobalDetection(params)
        elif command == "dead_code_detection":
            return self.DeadCodeDetection(params)
        elif command == "duplicate_detection":
            return self.DuplicateDetection(params)
        elif command == "complexity_analysis":
            return self.ComplexityAnalysis(params)
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
        return (1, self.state["db_conn"], None)

    def Now(self):
        return (1, datetime.now(timezone.utc).isoformat(), None)

    def AstParse(self, params):
        code = self._p(params, "code")
        file_path = self._p(params, "file_path")
        if code is None and file_path is None:
            return (0, None, ("MISSING_PARAM", "code or file_path required", 0))
        if code is None:
            try:
                with open(file_path, "r") as f:
                    code = f.read()
            except OSError as exc:
                return (0, None, ("FILE_READ_FAILED", str(exc), 0))
        try:
            tree = ast.parse(code)
            nodes = []
            for node in ast.walk(tree):
                nodes.append({"type": type(node).__name__, "line": getattr(node, "lineno", 0)})
        except SyntaxError as exc:
            return (0, None, ("SYNTAX_ERROR", str(exc), 0))
        return (1, {"node_count": len(nodes), "nodes": nodes[:50],
                    "parse_success": True}, None)

    def SymbolTable(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return (0, None, ("SYNTAX_ERROR", str(exc), 0))
        symbols = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                symbols.append({"name": node.name, "type": "class", "line": node.lineno})
            elif isinstance(node, ast.FunctionDef):
                symbols.append({"name": node.name, "type": "function", "line": node.lineno})
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        symbols.append({"name": target.id, "type": "variable", "line": node.lineno})
        return (1, {"symbols": symbols, "count": len(symbols)}, None)

    def ImportResolution(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return (0, None, ("SYNTAX_ERROR", str(exc), 0))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({"module": alias.name, "alias": alias.asname, "line": node.lineno})
            elif isinstance(node, ast.ImportFrom):
                imports.append({"module": node.module, "names": [a.name for a in node.names],
                                "line": node.lineno})
        return (1, {"imports": imports, "count": len(imports)}, None)

    def TypeAnalysis(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return (0, None, ("SYNTAX_ERROR", str(exc), 0))
        types = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and node.annotation:
                types.append({"target": getattr(node.target, "id", "?"),
                              "annotation": ast.dump(node.annotation), "line": node.lineno})
            elif isinstance(node, ast.FunctionDef) and node.returns:
                types.append({"function": node.name, "return_type": ast.dump(node.returns),
                              "line": node.lineno})
        return (1, {"type_annotations": types, "count": len(types)}, None)

    def ScopeAnalysis(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return (0, None, ("SYNTAX_ERROR", str(exc), 0))
        scopes = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                scope_type = "module" if isinstance(node, ast.Module) else (
                    "class" if isinstance(node, ast.ClassDef) else "function")
                name = getattr(node, "name", "<module>")
                scopes.append({"name": name, "type": scope_type,
                               "line": getattr(node, "lineno", 0)})
        return (1, {"scopes": scopes, "count": len(scopes)}, None)

    def ConstantDetection(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return (0, None, ("SYNTAX_ERROR", str(exc), 0))
        constants = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        constants.append({"name": target.id, "line": node.lineno})
        return (1, {"constants": constants, "count": len(constants)}, None)

    def GlobalDetection(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return (0, None, ("SYNTAX_ERROR", str(exc), 0))
        globals = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        globals.append({"name": target.id, "line": node.lineno})
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                globals.append({"name": node.name, "type": type(node).__name__, "line": node.lineno})
        return (1, {"globals": globals, "count": len(globals)}, None)

    def DeadCodeDetection(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return (0, None, ("SYNTAX_ERROR", str(exc), 0))
        dead = []
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") and not stripped.startswith("# [@"):
                dead.append({"line": i, "type": "comment"})
        for node in ast.walk(tree):
            if isinstance(node, ast.Pass):
                dead.append({"line": node.lineno, "type": "pass"})
        return (1, {"dead_code": dead, "count": len(dead)}, None)

    def DuplicateDetection(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return (0, None, ("SYNTAX_ERROR", str(exc), 0))
        hashes = {}
        duplicates = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                body_hash = hash(ast.dump(node))
                if body_hash in hashes:
                    duplicates.append({"name": node.name, "line": node.lineno,
                                       "duplicate_of": hashes[body_hash]})
                else:
                    hashes[body_hash] = node.name
        return (1, {"duplicates": duplicates, "count": len(duplicates)}, None)

    def ComplexityAnalysis(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return (0, None, ("SYNTAX_ERROR", str(exc), 0))
        results = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                complexity = 1
                for child in ast.walk(node):
                    if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                        complexity += 1
                    elif isinstance(child, ast.BoolOp):
                        complexity += len(child.values) - 1
                nesting = 0
                max_nesting = 0
                for child in ast.walk(node):
                    if isinstance(child, (ast.If, ast.While, ast.For, ast.With)):
                        nesting += 1
                        max_nesting = max(max_nesting, nesting)
                results.append({"function": node.name, "complexity": complexity,
                                "max_nesting": max_nesting, "line": node.lineno})
        return (1, {"complexity": results, "count": len(results)}, None)
