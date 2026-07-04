#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/symbol_engine.py"
# date="2026-06-26" author="Devin" session_id="phase4-analysis"
# context="Project Digital Twin Phase 4 Section 45 Symbol Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="symbol_engine.py" domain="twin_symbol" authority="SymbolEngine"}
# [@SUMMARY]{summary="Symbol authority that aggregates all classes, methods, variables, constants, enums and interfaces from the Project Digital Twin."}
# [@CLASS]{class="SymbolEngine" domain="symbol" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="get_all_symbols" type="command"}
# [@METHOD]{method="get_variables" type="command"}
# [@METHOD]{method="get_constants" type="command"}
# [@METHOD]{method="get_enums" type="command"}
# [@METHOD]{method="get_interfaces" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<SymbolEngine: aggregates all classes methods variables constants enums interfaces from Project Digital Twin. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations.>][@todos<none>]}
"""
SymbolEngine -- authority for symbol aggregation and extraction.
Implements Section 45 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: get_all_symbols, get_variables, get_constants, get_enums,
          get_interfaces.
The engine aggregates structural symbols (classes, methods) from the
twin database and lexical symbols (variables, constants, enums,
interfaces) via AST scanning of stored method_code and file sources.
"""
import ast
import json
import os
import re
import sqlite3
import textwrap
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
UPPER_CONSTANT_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
ENUM_BASES = ("Enum", "IntEnum", "Flag", "IntFlag")
ABC_NAMES = ("ABC", "ABCMeta", "AbstractBaseClass", "abstractbaseclass")


class SymbolEngine:
    """Authority for symbol aggregation, extraction and cataloging."""

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
        if command == "get_all_symbols":
            return self.GetAllSymbols(params)
        elif command == "get_variables":
            return self.GetVariables(params)
        elif command == "get_constants":
            return self.GetConstants(params)
        elif command == "get_enums":
            return self.GetEnums(params)
        elif command == "get_interfaces":
            return self.GetInterfaces(params)
        elif command == "get_structs":
            return self.GetStructs(params)
        elif command == "get_typedefs":
            return self.GetTypedefs(params)
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

    def ParseAst(self, source):
        if not source:
            return None
        try:
            return ast.parse(textwrap.dedent(source))
        except SyntaxError:
            return None

    def GetAllSymbols(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT class_id, class_name, file_id FROM classes "
            "ORDER BY class_id LIMIT ?",
            (limit,),
        )
        classes = [
            {"kind": "class", "id": r[0], "name": r[1], "file_id": r[2]}
            for r in cur.fetchall()
        ]
        cur.execute(
            "SELECT method_id, method_name, class_id, file_id FROM methods "
            "ORDER BY method_id LIMIT ?",
            (limit,),
        )
        methods = [
            {"kind": "method", "id": r[0], "name": r[1], "class_id": r[2],
             "file_id": r[3]}
            for r in cur.fetchall()
        ]
        var_result = self.GetVariables(params)
        variables = var_result[1] if var_result[0] == 1 else []
        const_result = self.GetConstants(params)
        constants = const_result[1] if const_result[0] == 1 else []
        enum_result = self.GetEnums(params)
        enums = enum_result[1] if enum_result[0] == 1 else []
        iface_result = self.GetInterfaces(params)
        interfaces = iface_result[1] if iface_result[0] == 1 else []
        record = {
            "classes": classes,
            "methods": methods,
            "variables": variables,
            "constants": constants,
            "enums": enums,
            "interfaces": interfaces,
            "totals": {
                "classes": len(classes),
                "methods": len(methods),
                "variables": len(variables),
                "constants": len(constants),
                "enums": len(enums),
                "interfaces": len(interfaces),
            },
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def GetVariables(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_code, method_name, start_line "
            "FROM methods WHERE method_code IS NOT NULL "
            "ORDER BY method_id LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        variables = []
        observations = []
        for method_id, code, method_name, start_line in rows:
            tree = self.ParseAst(code)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        names = self.ExtractTargetNames(target)
                        for nm in names:
                            if nm.startswith("_"):
                                continue
                            entry = {
                                "name": nm,
                                "method_id": method_id,
                                "method_name": method_name,
                                "line": (start_line or 0) + node.lineno,
                            }
                            variables.append(entry)
                            observations.append((
                                "variable_assignment",
                                nm,
                                json.dumps(entry),
                                0.8,
                                None,
                                None,
                                method_id,
                            ))
        if observations:
            self.StoreObservations(observations)
        record = {
            "variables": variables,
            "count": len(variables),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def ExtractTargetNames(self, target):
        names = []
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, ast.Tuple) or isinstance(target, ast.List):
            for elt in target.elts:
                names.extend(self.ExtractTargetNames(elt))
        elif isinstance(target, ast.Attribute):
            if isinstance(target.value, ast.Name):
                names.append(target.value.id + "." + target.attr)
        return names

    def StoreObservations(self, observations):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='observations'"
        )
        if cur.fetchone() is None:
            return
        cur.executemany(
            "INSERT INTO observations (observation_type, subject, evidence, "
            "confidence, file_id, class_id, method_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            observations,
        )
        conn.commit()

    def GetConstants(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='config_constants'")
        db_constants = []
        if cur.fetchone() is not None:
            cur.execute(
                "SELECT name, value, type, description FROM config_constants "
                "ORDER BY name LIMIT ?",
                (limit,),
            )
            db_constants = [
                {"name": r[0], "value": r[1], "type": r[2], "description": r[3],
                 "source": "config_constants"}
                for r in cur.fetchall()
            ]
        cur.execute(
            "SELECT file_id, file_name, path FROM files ORDER BY file_id LIMIT ?",
            (limit,),
        )
        files = cur.fetchall()
        ast_constants = []
        for file_id, file_name, path in files:
            source = self.ReadFileSource(path)
            if not source:
                continue
            tree = self.ParseAst(source)
            if tree is None:
                continue
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and UPPER_CONSTANT_RE.match(target.id):
                            ast_constants.append({
                                "name": target.id,
                                "value": self.RenderConstant(node.value),
                                "file_id": file_id,
                                "file_name": file_name,
                                "source": "ast_module_level",
                                "line": node.lineno,
                            })
        record = {
            "db_constants": db_constants,
            "ast_constants": ast_constants,
            "count": len(db_constants) + len(ast_constants),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def ReadFileSource(self, path):
        if not path:
            return None
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                return handle.read()
        except OSError:
            return None

    def RenderConstant(self, node):
        try:
            return ast.unparse(node)
        except Exception:
            return None

    def GetEnums(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT file_id, file_name, path FROM files ORDER BY file_id LIMIT ?",
            (limit,),
        )
        files = cur.fetchall()
        enums = []
        for file_id, file_name, path in files:
            source = self.ReadFileSource(path)
            if not source:
                continue
            tree = self.ParseAst(source)
            if tree is None:
                continue
            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                enum_base = self.DetectEnumBase(node)
                if enum_base is None:
                    continue
                members = []
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                members.append(target.id)
                enums.append({
                    "name": node.name,
                    "base": enum_base,
                    "members": members,
                    "file_id": file_id,
                    "file_name": file_name,
                    "line": node.lineno,
                })
        record = {
            "enums": enums,
            "count": len(enums),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def DetectEnumBase(self, class_node):
        for base in class_node.bases:
            nm = self.RenderName(base)
            if nm in ENUM_BASES:
                return nm
        return None

    def RenderName(self, node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return self.RenderName(node.value) + "." + node.attr
        try:
            return ast.unparse(node)
        except Exception:
            return ""

    def GetInterfaces(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT file_id, file_name, path FROM files ORDER BY file_id LIMIT ?",
            (limit,),
        )
        files = cur.fetchall()
        interfaces = []
        for file_id, file_name, path in files:
            source = self.ReadFileSource(path)
            if not source:
                continue
            tree = self.ParseAst(source)
            if tree is None:
                continue
            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                reason = self.DetectInterface(node)
                if reason is None:
                    continue
                abstract_methods = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        if self.HasAbstractMethod(item):
                            abstract_methods.append(item.name)
                interfaces.append({
                    "name": node.name,
                    "reason": reason,
                    "abstract_methods": abstract_methods,
                    "file_id": file_id,
                    "file_name": file_name,
                    "line": node.lineno,
                })
        record = {
            "interfaces": interfaces,
            "count": len(interfaces),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def DetectInterface(self, class_node):
        for base in class_node.bases:
            nm = self.RenderName(base)
            for abc in ABC_NAMES:
                if abc.lower() in nm.lower():
                    return "inherits_" + nm
        for item in class_node.body:
            if isinstance(item, ast.FunctionDef) and self.HasAbstractMethod(item):
                return "has_abstractmethod"
        return None

    def HasAbstractMethod(self, func_node):
        for dec in func_node.decorator_list:
            nm = self.RenderName(dec)
            if "abstractmethod" in nm.lower():
                return True
        body = func_node.body
        if body and isinstance(body[0], ast.Expr):
            expr = body[0]
            if isinstance(expr.value, ast.Constant):
                if isinstance(expr.value.value, str):
                    if "abstract" in expr.value.value.lower():
                        return True
        only_pass = len(body) == 1 and isinstance(body[0], ast.Pass)
        if only_pass:
            return True
        return False

    def GetStructs(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT file_id, file_name, path FROM files ORDER BY file_id LIMIT ?",
            (limit,),
        )
        files = cur.fetchall()
        structs = []
        for file_id, file_name, path in files:
            source = self.ReadFileSource(path)
            if not source:
                continue
            tree = self.ParseAst(source)
            if tree is None:
                continue
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if isinstance(node.value, ast.Call):
                                func = node.value.func
                                if isinstance(func, ast.Name) and func.id == "namedtuple":
                                    structs.append({
                                        "name": target.id,
                                        "type": "namedtuple",
                                        "file_id": file_id,
                                        "file_name": file_name,
                                        "line": node.lineno,
                                    })
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name) and target.id == "_fields":
                                    if isinstance(item.value, ast.Tuple):
                                        fields = []
                                        for elt in item.value.elts:
                                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                                fields.append(elt.value)
                                        if fields:
                                            structs.append({
                                                "name": node.name,
                                                "type": "namedtuple_class",
                                                "fields": fields,
                                                "file_id": file_id,
                                                "file_name": file_name,
                                                "line": node.lineno,
                                            })
        record = {
            "structs": structs,
            "count": len(structs),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def GetTypedefs(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT file_id, file_name, path FROM files ORDER BY file_id LIMIT ?",
            (limit,),
        )
        files = cur.fetchall()
        typedefs = []
        for file_id, file_name, path in files:
            source = self.ReadFileSource(path)
            if not source:
                continue
            tree = self.ParseAst(source)
            if tree is None:
                continue
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if isinstance(node.value, ast.Call):
                                func = node.value.func
                                if isinstance(func, ast.Name) and func.id == "TypeVar":
                                    typedefs.append({
                                        "name": target.id,
                                        "type": "TypeVar",
                                        "file_id": file_id,
                                        "file_name": file_name,
                                        "line": node.lineno,
                                    })
                            if isinstance(node.value, ast.Subscript):
                                if isinstance(node.value.value, ast.Name) and node.value.value.id == "Union":
                                    typedefs.append({
                                        "name": target.id,
                                        "type": "TypeAlias_Union",
                                        "file_id": file_id,
                                        "file_name": file_name,
                                        "line": node.lineno,
                                    })
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        nm = self.RenderName(base)
                        if nm == "Generic":
                            typedefs.append({
                                "name": node.name,
                                "type": "Generic",
                                "file_id": file_id,
                                "file_name": file_name,
                                "line": node.lineno,
                            })
        record = {
            "typedefs": typedefs,
            "count": len(typedefs),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)
