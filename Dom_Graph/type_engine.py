#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/type_engine.py"
# date="2026-06-26" author="Devin" session_id="phase4-analysis"
# context="Project Digital Twin Phase 4 Section 46 Type Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="type_engine.py" domain="twin_type" authority="TypeEngine"}
# [@SUMMARY]{summary="Type authority that extracts type hints, infers types from assignments, finds type mismatches and checks call-site compatibility for the Project Digital Twin."}
# [@CLASS]{class="TypeEngine" domain="type" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="extract_types" type="command"}
# [@METHOD]{method="infer_types" type="command"}
# [@METHOD]{method="find_violations" type="command"}
# [@METHOD]{method="check_compatibility" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<TypeEngine: extracts type hints infers types from assignments finds type mismatches checks call-site compatibility. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations.>][@todos<none>]}
"""
TypeEngine -- authority for type extraction, inference and checking.
Implements Section 46 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: extract_types, infer_types, find_violations, check_compatibility.
The engine parses stored method_code via AST to collect explicit type
hints, infer types from assignment values for untyped variables, detect
basic type-mismatch violations and verify call-site parameter
compatibility against declared signatures.
"""
import ast
import json
import os
import sqlite3
import textwrap
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
LITERAL_TYPE_MAP = (
    (ast.Constant, "str", lambda n: isinstance(n.value, str)),
    (ast.Constant, "int", lambda n: isinstance(n.value, int) and not isinstance(n.value, bool)),
    (ast.Constant, "float", lambda n: isinstance(n.value, float)),
    (ast.Constant, "bool", lambda n: isinstance(n.value, bool)),
    (ast.Constant, "NoneType", lambda n: n.value is None),
    (ast.List, "list", lambda n: True),
    (ast.Dict, "dict", lambda n: True),
    (ast.Set, "set", lambda n: True),
    (ast.Tuple, "tuple", lambda n: True),
)


class TypeEngine:
    """Authority for type extraction, inference and violation detection."""

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
        if command == "extract_types":
            return self.ExtractTypes(params)
        elif command == "infer_types":
            return self.InferTypes(params)
        elif command == "find_violations":
            return self.FindViolations(params)
        elif command == "check_compatibility":
            return self.CheckCompatibility(params)
        elif command == "cast_detection":
            return self.CastDetection(params)
        elif command == "conversion_tracking":
            return self.ConversionTracking(params)
        elif command == "nullable_analysis":
            return self.NullableAnalysis(params)
        elif command == "generic_analysis":
            return self.GenericAnalysis(params)
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

    def RenderAnnotation(self, node):
        if node is None:
            return None
        try:
            return ast.unparse(node)
        except Exception:
            return None

    def ExtractTypes(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        method_id = self._p(params, "method_id")
        conn = self.Connect()
        cur = conn.cursor()
        if method_id is not None:
            cur.execute(
                "SELECT method_id, method_code, method_name, signature, "
                "return_type, parameters FROM methods WHERE method_id=?",
                (method_id,),
            )
        else:
            cur.execute(
                "SELECT method_id, method_code, method_name, signature, "
                "return_type, parameters FROM methods "
                "WHERE method_code IS NOT NULL ORDER BY method_id LIMIT ?",
                (limit,),
            )
        rows = cur.fetchall()
        extracted = []
        for mid, code, mname, sig, rtype, params_json in rows:
            param_types = {}
            return_type = rtype
            tree = self.ParseAst(code)
            if tree is not None:
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name == mname:
                        for arg in node.args.args:
                            ann = self.RenderAnnotation(arg.annotation)
                            if ann:
                                param_types[arg.arg] = ann
                        if return_type is None:
                            return_type = self.RenderAnnotation(node.returns)
                        break
            if not param_types and params_json:
                try:
                    parsed = json.loads(params_json)
                    if isinstance(parsed, dict):
                        for k, v in parsed.items():
                            if isinstance(v, dict) and "type" in v:
                                param_types[k] = v["type"]
                            elif isinstance(v, str):
                                param_types[k] = v
                except (ValueError, TypeError):
                    pass
            extracted.append({
                "method_id": mid,
                "method_name": mname,
                "signature": sig,
                "param_types": param_types,
                "return_type": return_type,
            })
        record = {
            "extracted": extracted,
            "count": len(extracted),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def InferTypes(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        method_id = self._p(params, "method_id")
        conn = self.Connect()
        cur = conn.cursor()
        if method_id is not None:
            cur.execute(
                "SELECT method_id, method_code, method_name, start_line "
                "FROM methods WHERE method_id=?",
                (method_id,),
            )
        else:
            cur.execute(
                "SELECT method_id, method_code, method_name, start_line "
                "FROM methods WHERE method_code IS NOT NULL "
                "ORDER BY method_id LIMIT ?",
                (limit,),
            )
        rows = cur.fetchall()
        inferred = []
        for mid, code, mname, start_line in rows:
            tree = self.ParseAst(code)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    if target.id.startswith("_"):
                        continue
                    inferred_type = self.InferFromValue(node.value)
                    if inferred_type is None:
                        continue
                    inferred.append({
                        "method_id": mid,
                        "method_name": mname,
                        "variable": target.id,
                        "inferred_type": inferred_type,
                        "line": (start_line or 0) + node.lineno,
                    })
        record = {
            "inferred": inferred,
            "count": len(inferred),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def InferFromValue(self, node):
        for ast_type, type_name, predicate in LITERAL_TYPE_MAP:
            if isinstance(node, ast_type) and predicate(node):
                return type_name
        if isinstance(node, ast.BinOp):
            left = self.InferFromValue(node.left)
            right = self.InferFromValue(node.right)
            if left == "int" and right == "int":
                return "int"
            if left in ("float", "int") and right in ("float", "int"):
                return "float"
            if left == "str" and right == "str":
                return "str"
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                mapping = {
                    "str": "str", "int": "int", "float": "float",
                    "bool": "bool", "list": "list", "dict": "dict",
                    "set": "set", "tuple": "tuple",
                }
                return mapping.get(func.id)
        return None

    def FindViolations(self, params):
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
        violations = []
        for mid, code, mname, start_line in rows:
            tree = self.ParseAst(code)
            if tree is None:
                continue
            var_types = {}
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    nm = target.id
                    new_type = self.InferFromValue(node.value)
                    if new_type is None:
                        continue
                    if nm in var_types and var_types[nm] != new_type:
                        violations.append({
                            "method_id": mid,
                            "method_name": mname,
                            "variable": nm,
                            "previous_type": var_types[nm],
                            "new_type": new_type,
                            "line": (start_line or 0) + node.lineno,
                            "violation": "type_mismatch",
                        })
                    var_types[nm] = new_type
        record = {
            "violations": violations,
            "count": len(violations),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def CheckCompatibility(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_code, method_name, signature, parameters "
            "FROM methods WHERE method_id=?",
            (method_id,),
        )
        row = cur.fetchone()
        if row is None:
            return (0, None, ("NOT_FOUND", "method not found: " + str(method_id), 0))
        code, mname, sig, params_json = row
        declared = {}
        tree = self.ParseAst(code)
        target_node = None
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == mname:
                    target_node = node
                    for arg in node.args.args:
                        ann = self.RenderAnnotation(arg.annotation)
                        if ann:
                            declared[arg.arg] = ann
                    break
        if not declared and params_json:
            try:
                parsed = json.loads(params_json)
                if isinstance(parsed, dict):
                    for k, v in parsed.items():
                        if isinstance(v, dict) and "type" in v:
                            declared[k] = v["type"]
                        elif isinstance(v, str):
                            declared[k] = v
            except (ValueError, TypeError):
                pass
        cur.execute(
            "SELECT method_id, method_code, method_name, calls "
            "FROM methods WHERE calls LIKE ?",
            ("%" + str(method_id) + "%",),
        )
        callers = cur.fetchall()
        call_sites = []
        for caller_id, caller_code, caller_name, calls_json in callers:
            if caller_id == method_id:
                continue
            ctree = self.ParseAst(caller_code)
            if ctree is None:
                continue
            for node in ast.walk(ctree):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Name):
                    continue
                if node.func.id != mname:
                    continue
                issues = []
                for idx, arg in enumerate(node.args):
                    arg_type = self.InferFromValue(arg)
                    if arg_type is None:
                        continue
                    param_names = list(declared.keys())
                    if idx < len(param_names):
                        pname = param_names[idx]
                        ptype = declared[pname]
                        if ptype and ptype != arg_type and ptype != "Any":
                            issues.append({
                                "param": pname,
                                "expected": ptype,
                                "actual": arg_type,
                            })
                call_sites.append({
                    "caller_method_id": caller_id,
                    "caller_method_name": caller_name,
                    "line": node.lineno,
                    "issues": issues,
                })
        record = {
            "method_id": method_id,
            "method_name": mname,
            "signature": sig,
            "declared_params": declared,
            "call_sites": call_sites,
            "compatible": all(len(cs["issues"]) == 0 for cs in call_sites),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def CastDetection(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        method_id = self._p(params, "method_id")
        conn = self.Connect()
        cur = conn.cursor()
        if method_id is not None:
            cur.execute(
                "SELECT method_id, method_code, method_name, start_line "
                "FROM methods WHERE method_id=?",
                (method_id,),
            )
        else:
            cur.execute(
                "SELECT method_id, method_code, method_name, start_line "
                "FROM methods WHERE method_code IS NOT NULL "
                "ORDER BY method_id LIMIT ?",
                (limit,),
            )
        rows = cur.fetchall()
        casts = []
        for mid, code, mname, start_line in rows:
            tree = self.ParseAst(code)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name):
                        if func.id == "type":
                            casts.append({
                                "method_id": mid,
                                "method_name": mname,
                                "line": (start_line or 0) + node.lineno,
                                "cast_type": "type()",
                                "args": [self.RenderAnnotation(a) for a in node.args],
                            })
                        if func.id == "isinstance":
                            casts.append({
                                "method_id": mid,
                                "method_name": mname,
                                "line": (start_line or 0) + node.lineno,
                                "cast_type": "isinstance()",
                                "args": [self.RenderAnnotation(a) for a in node.args],
                            })
                    if isinstance(func, ast.Attribute):
                        if func.attr == "cast" and isinstance(func.value, ast.Name) and func.value.id == "typing":
                            casts.append({
                                "method_id": mid,
                                "method_name": mname,
                                "line": (start_line or 0) + node.lineno,
                                "cast_type": "typing.cast()",
                                "args": [self.RenderAnnotation(a) for a in node.args],
                            })
        record = {
            "casts": casts,
            "count": len(casts),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def ConversionTracking(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        method_id = self._p(params, "method_id")
        conn = self.Connect()
        cur = conn.cursor()
        if method_id is not None:
            cur.execute(
                "SELECT method_id, method_code, method_name, start_line "
                "FROM methods WHERE method_id=?",
                (method_id,),
            )
        else:
            cur.execute(
                "SELECT method_id, method_code, method_name, start_line "
                "FROM methods WHERE method_code IS NOT NULL "
                "ORDER BY method_id LIMIT ?",
                (limit,),
            )
        rows = cur.fetchall()
        conversions = []
        conv_funcs = ("int", "str", "float", "bool", "list", "dict", "set", "tuple", "bytes", "bytearray")
        for mid, code, mname, start_line in rows:
            tree = self.ParseAst(code)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in conv_funcs:
                        conversions.append({
                            "method_id": mid,
                            "method_name": mname,
                            "line": (start_line or 0) + node.lineno,
                            "conversion": node.func.id + "()",
                            "arg_count": len(node.args),
                        })
        record = {
            "conversions": conversions,
            "count": len(conversions),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def NullableAnalysis(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_code, method_name, return_type, start_line "
            "FROM methods WHERE method_code IS NOT NULL "
            "ORDER BY method_id LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        nullable_methods = []
        for mid, code, mname, rtype, start_line in rows:
            tree = self.ParseAst(code)
            returns_none = False
            has_none_check = False
            has_optional = False
            if rtype and ("Optional" in rtype or "None" in rtype):
                has_optional = True
            if tree is not None:
                for node in ast.walk(tree):
                    if isinstance(node, ast.Return):
                        if node.value is None:
                            returns_none = True
                        if isinstance(node.value, ast.Constant) and node.value.value is None:
                            returns_none = True
                    if isinstance(node, ast.Compare):
                        for cmp in node.comparators:
                            if isinstance(cmp, ast.Constant) and cmp.value is None:
                                has_none_check = True
            else:
                if "return None" in (code or "") or "return" in (code or ""):
                    returns_none = True
                if "is None" in (code or "") or "== None" in (code or ""):
                    has_none_check = True
            if returns_none or has_optional:
                nullable_methods.append({
                    "method_id": mid,
                    "method_name": mname,
                    "returns_none": returns_none,
                    "has_optional_annotation": has_optional,
                    "has_none_check": has_none_check,
                    "declared_return_type": rtype,
                })
        record = {
            "nullable_methods": nullable_methods,
            "count": len(nullable_methods),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def GenericAnalysis(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT file_id, file_name, path FROM files ORDER BY file_id LIMIT ?",
            (limit,),
        )
        files = cur.fetchall()
        generics = []
        for file_id, file_name, path in files:
            if not path or not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    source = fh.read()
            except OSError:
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
                                    constraints = []
                                    for arg in node.value.args[1:]:
                                        constraints.append(self.RenderAnnotation(arg))
                                    generics.append({
                                        "name": target.id,
                                        "type": "TypeVar",
                                        "constraints": constraints,
                                        "file_id": file_id,
                                        "file_name": file_name,
                                        "line": node.lineno,
                                    })
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        nm = self.RenderAnnotation(base)
                        if nm and "Generic" in nm:
                            generics.append({
                                "name": node.name,
                                "type": "Generic_class",
                                "base": nm,
                                "file_id": file_id,
                                "file_name": file_name,
                                "line": node.lineno,
                            })
        record = {
            "generics": generics,
            "count": len(generics),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)
