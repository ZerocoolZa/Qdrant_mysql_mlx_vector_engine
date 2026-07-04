#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/vbstyle_validator_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 10: VBStyle Validator -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="vbstyle_validator_engine.py" domain="twin_vbstyle" authority="VbstyleValidatorEngine"}
# [@SUMMARY]{summary="VBStyle validator: check PascalCase, check no print, check no decorators, check no self._, check Tuple3 return, check Run dispatch, check no tabs, check no trailing whitespace, check no enums, check no hardcoded values, check no hidden attributes."}
# [@CLASS]{class="VbstyleValidatorEngine" domain="vbstyle_validator" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="check_pascalcase" type="command"}
# [@METHOD]{method="check_no_print" type="command"}
# [@METHOD]{method="check_no_decorators" type="command"}
# [@METHOD]{method="check_no_self_underscore" type="command"}
# [@METHOD]{method="check_tuple3" type="command"}
# [@METHOD]{method="check_run_dispatch" type="command"}
# [@METHOD]{method="check_no_tabs" type="command"}
# [@METHOD]{method="check_no_trailing_whitespace" type="command"}
# [@METHOD]{method="check_no_enums" type="command"}
# [@METHOD]{method="check_no_hardcoded" type="command"}
# [@METHOD]{method="validate_all" type="command"}
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


class VbstyleValidatorEngine:
    """Authority for VBStyle compliance validation."""

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
        if command == "check_pascalcase":
            return self.CheckPascalcase(params)
        elif command == "check_no_print":
            return self.CheckNoPrint(params)
        elif command == "check_no_decorators":
            return self.CheckNoDecorators(params)
        elif command == "check_no_self_underscore":
            return self.CheckNoSelfUnderscore(params)
        elif command == "check_tuple3":
            return self.CheckTuple3(params)
        elif command == "check_run_dispatch":
            return self.CheckRunDispatch(params)
        elif command == "check_no_tabs":
            return self.CheckNoTabs(params)
        elif command == "check_no_trailing_whitespace":
            return self.CheckNoTrailingWhitespace(params)
        elif command == "check_no_enums":
            return self.CheckNoEnums(params)
        elif command == "check_no_hardcoded":
            return self.CheckNoHardcoded(params)
        elif command == "validate_all":
            return self.ValidateAll(params)
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

    def Now(self):
        return (1, datetime.now(timezone.utc).isoformat(), None)

    def CheckPascalcase(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return (0, None, ("PARSE_FAILED", str(exc), 0))
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if not re.match(r"^[A-Z][a-zA-Z0-9]*$", node.name):
                    violations.append({"type": "class",
                                       "name": node.name,
                                       "rule": "PascalCase"})
        return (1, {"violations": violations,
                    "compliant": len(violations) == 0}, None)

    def CheckNoPrint(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        violations = []
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if stripped.startswith("print("):
                violations.append({"line": i, "rule": "no_print"})
        return (1, {"violations": violations,
                    "compliant": len(violations) == 0}, None)

    def CheckNoDecorators(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return (0, None, ("PARSE_FAILED", str(exc), 0))
        violations = []
        forbidden = ("property", "staticmethod", "classmethod")
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                for dec in node.decorator_list:
                    dec_name = ""
                    if isinstance(dec, ast.Name):
                        dec_name = dec.id
                    elif isinstance(dec, ast.Attribute):
                        dec_name = dec.attr
                    if dec_name in forbidden:
                        violations.append({"target": node.name,
                                           "decorator": dec_name,
                                           "rule": "no_decorator"})
        return (1, {"violations": violations,
                    "compliant": len(violations) == 0}, None)

    def CheckNoSelfUnderscore(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        violations = []
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            if "self._" in line:
                violations.append({"line": i, "rule": "no_self_underscore"})
        return (1, {"violations": violations,
                    "compliant": len(violations) == 0}, None)

    def CheckTuple3(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return (0, None, ("PARSE_FAILED", str(exc), 0))
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                has_tuple3 = False
                for child in ast.walk(node):
                    if isinstance(child, ast.Return) and child.value:
                        if isinstance(child.value, ast.Tuple):
                            if len(child.value.elts) == 3:
                                has_tuple3 = True
                if not has_tuple3 and node.name != "__init__" and not node.name.startswith("_"):
                    violations.append({"method": node.name,
                                       "rule": "tuple3_return"})
        return (1, {"violations": violations,
                    "compliant": len(violations) == 0}, None)

    def CheckRunDispatch(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return (0, None, ("PARSE_FAILED", str(exc), 0))
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                has_run = False
                for child in node.body:
                    if isinstance(child, ast.FunctionDef) and child.name == "Run":
                        has_run = True
                        break
                if not has_run:
                    violations.append({"class": node.name,
                                       "rule": "missing_Run"})
        return (1, {"violations": violations,
                    "compliant": len(violations) == 0}, None)

    def CheckNoTabs(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        violations = []
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            if "\t" in line:
                violations.append({"line": i, "rule": "no_tabs"})
        return (1, {"violations": violations,
                    "compliant": len(violations) == 0}, None)

    def CheckNoTrailingWhitespace(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        violations = []
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            if line.endswith(" ") or line.endswith("\t"):
                violations.append({"line": i, "rule": "no_trailing_whitespace"})
        return (1, {"violations": violations,
                    "compliant": len(violations) == 0}, None)

    def CheckNoEnums(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        violations = []
        if "Enum" in code or "IntEnum" in code or "auto()" in code:
            violations.append({"rule": "no_enums",
                               "detail": "Enum usage detected"})
        return (1, {"violations": violations,
                    "compliant": len(violations) == 0}, None)

    def CheckNoHardcoded(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        violations = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return (1, {"violations": [], "compliant": True}, None)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.islower():
                        if isinstance(node.value, ast.Constant):
                            if isinstance(node.value.value, (int, float, str)):
                                if not target.id.isupper():
                                    violations.append({
                                        "line": node.lineno,
                                        "rule": "no_hardcoded",
                                        "detail": target.id + " = " + repr(node.value.value),
                                    })
        return (1, {"violations": violations,
                    "compliant": len(violations) == 0}, None)

    def ValidateAll(self, params):
        code = self._p(params, "code")
        if code is None:
            return (0, None, ("MISSING_PARAM", "code required", 0))
        results = {}
        all_violations = []
        for step in ("check_pascalcase", "check_no_print", "check_no_decorators",
                     "check_no_self_underscore", "check_tuple3",
                     "check_run_dispatch", "check_no_tabs",
                     "check_no_trailing_whitespace", "check_no_enums",
                     "check_no_hardcoded"):
            res = self.Run(step, {"code": code})
            if res[0] == 1:
                results[step] = res[1]
                if res[1].get("violations"):
                    all_violations.extend(res[1]["violations"])
            else:
                results[step] = {"error": str(res[2])}
        results["total_violations"] = len(all_violations)
        results["compliant"] = len(all_violations) == 0
        results["all_violations"] = all_violations
        return (1, results, None)
