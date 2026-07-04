#!/usr/bin/env python3
#[@GHOST]{[@file<exec_sandbox.py>][@state<active>][@date<2026-07-01>][@ver<1.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<exec_sandbox>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}

import ast
import importlib


class ExecSandbox:
    """
    #[@CLASS]{[@name<ExecSandbox>][@domain<security_sandbox>][@orch<Dom_Db>]}
    Safe code execution sandbox for the execution planner.
    Provides whitelist-based module access, AST-level code scanning,
    and restricted exec/eval to prevent dangerous operations.
    """

    SAFE_MODULES = (
        "json", "re", "hashlib", "collections", "itertools", "functools",
        "math", "random", "textwrap", "string", "pprint", "decimal",
        "fractions", "array", "bisect", "heapq", "numbers", "statistics",
        "operator", "struct", "base64", "uuid", "copy", "time",
        "datetime", "types", "inspect", "traceback", "warnings",
        "abc", "enum", "dataclasses", "contextlib", "io",
    )

    BLOCKED_MODULES = (
        "os", "sys", "subprocess", "socket", "shutil", "pathlib",
        "ctypes", "mmap", "signal", "pickle", "select", "tempfile",
        "glob", "fnmatch", "argparse", "configparser", "csv",
        "logging", "threading", "queue", "multiprocessing",
        "asyncio", "concurrent", "importlib", "builtins",
    )

    BLOCKED_AST_PATTERNS = (
        "Import", "ImportFrom", "Call", "Attribute",
    )

    BLOCKED_CALLS = (
        "open", "exec", "eval", "compile", "__import__",
        "globals", "locals", "vars", "dir",
    )

    BLOCKED_DUNDER_ATTRS = (
        "__builtins__", "__globals__", "__code__", "__class__",
    )

    SAFE_BUILTINS = (
        "len", "str", "int", "float", "list", "dict", "set", "tuple",
        "bool", "bytes", "range", "enumerate", "zip", "map", "filter",
        "sorted", "reversed", "min", "max", "sum", "abs", "round",
        "isinstance", "issubclass", "hasattr", "getattr", "setattr",
        "delattr", "type", "id", "hash", "repr", "format", "chr",
        "ord", "hex", "oct", "bin", "pow", "divmod", "all", "any",
        "next", "iter", "callable", "frozenset", "bytearray",
        "complex", "slice", "True", "False", "None",
    )

    BLOCKED_BUILTINS = (
        "open", "exec", "eval", "compile", "__import__", "globals",
        "locals", "vars", "dir", "help", "input", "breakpoint",
        "memoryview", "property", "staticmethod", "classmethod", "super",
    )

    NETWORK_PATTERNS = (
        "socket", "urllib", "http", "requests", "ftplib", "telnetlib",
        "smtplib", "poplib", "imaplib", "xmlrpc",
    )

    FILE_OP_PATTERNS = (
        "open", "os.remove", "os.unlink", "shutil.rmtree",
        "os.rename", "os.rmdir", "shutil.copy", "shutil.move",
    )

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "safe_modules": list(self.SAFE_MODULES),
            "blocked_modules": list(self.BLOCKED_MODULES),
            "scan_count": 0,
            "exec_count": 0,
            "block_count": 0,
            "last_violations": [],
        }

    def _p(self, params, key, default=None):
        """
        #[@METHOD]{[@name<_p>][@return<value>]}
        Param extraction helper.
        """
        if not isinstance(params, dict):
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        """
        #[@METHOD]{[@name<Run>][@return<Tuple3>]}
        Dispatch entry point.
        """
        dispatch = {
            "scan_code": self.ScanCode,
            "build_namespace": self.BuildNamespace,
            "safe_exec": self.SafeExec,
            "safe_eval": self.SafeEval,
            "validate_unit": self.ValidateUnit,
            "whitelist": self.Whitelist,
            "add_safe_module": self.AddSafeModule,
            "remove_safe_module": self.RemoveSafeModule,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", "unknown command: " + str(command), 0))
        return handler(params)

    def ScanCode(self, params=None):
        """
        #[@METHOD]{[@name<ScanCode>][@return<Tuple3>]}
        Parse source code and walk AST to detect blocked patterns.
        """
        source = self._p(params, "source")
        if source is None:
            file_path = self._p(params, "file")
            if file_path is None:
                return (0, None, ("NO_SOURCE", "missing source or file param", 0))
            try:
                with open(file_path, "r") as fh:
                    source = fh.read()
            except Exception as exc:
                return (0, None, ("READ_FAILED", str(exc), 0))
        self.state["scan_count"] = self.state["scan_count"] + 1
        violations = []
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return (1, {
                "safe": False,
                "violations": [{
                    "line": exc.lineno or 0,
                    "type": "SyntaxError",
                    "detail": str(exc.msg),
                }],
                "violation_count": 1,
            }, None)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod_name = alias.name.split(".")[0]
                    if mod_name in self.BLOCKED_MODULES:
                        violations.append({
                            "line": node.lineno,
                            "type": "BlockedImport",
                            "detail": "import of blocked module: " + alias.name,
                        })
            elif isinstance(node, ast.ImportFrom):
                mod_name = (node.module or "").split(".")[0]
                if mod_name in self.BLOCKED_MODULES:
                    violations.append({
                        "line": node.lineno,
                        "type": "BlockedImportFrom",
                        "detail": "from blocked module: " + str(node.module),
                    })
            elif isinstance(node, ast.Call):
                func = node.func
                call_name = None
                if isinstance(func, ast.Name):
                    call_name = func.id
                elif isinstance(func, ast.Attribute):
                    call_name = func.attr
                if call_name in self.BLOCKED_CALLS:
                    violations.append({
                        "line": node.lineno,
                        "type": "BlockedCall",
                        "detail": "call to blocked function: " + str(call_name),
                    })
            elif isinstance(node, ast.Attribute):
                attr_name = node.attr
                if attr_name in self.BLOCKED_DUNDER_ATTRS:
                    violations.append({
                        "line": node.lineno,
                        "type": "BlockedAttribute",
                        "detail": "access to dunder attr: " + attr_name,
                    })
        safe = len(violations) == 0
        self.state["last_violations"] = violations
        if not safe:
            self.state["block_count"] = self.state["block_count"] + 1
        return (1, {
            "safe": safe,
            "violations": violations,
            "violation_count": len(violations),
        }, None)

    def BuildNamespace(self, params=None):
        """
        #[@METHOD]{[@name<BuildNamespace>][@return<Tuple3>]}
        Build a restricted namespace dict with only safe modules and builtins.
        """
        namespace = {}
        for mod_name in self.state["safe_modules"]:
            try:
                mod = importlib.import_module(mod_name)
                namespace[mod_name] = mod
            except Exception:
                pass
        for builtin_name in self.SAFE_BUILTINS:
            builtin_obj = __builtins__.get(builtin_name) if isinstance(__builtins__, dict) else getattr(__builtins__, builtin_name, None)
            if builtin_obj is not None:
                namespace[builtin_name] = builtin_obj
        extras = self._p(params, "extras")
        if isinstance(extras, dict):
            for key, value in extras.items():
                if key not in self.BLOCKED_BUILTINS and key not in self.BLOCKED_MODULES:
                    namespace[key] = value
        return (1, namespace, None)

    def SafeExec(self, params=None):
        """
        #[@METHOD]{[@name<SafeExec>][@return<Tuple3>]}
        Scan code, build namespace, then exec with restricted access.
        """
        source = self._p(params, "source")
        if source is None:
            return (0, None, ("NO_SOURCE", "missing source param", 0))
        ok, scan_data, err = self.ScanCode({"source": source})
        if not ok:
            return (0, None, err)
        if not scan_data["safe"]:
            return (0, None, (
                "UNSAFE_CODE",
                "code blocked by scanner: " + str(scan_data["violation_count"]) + " violations",
                0,
            ))
        namespace = self._p(params, "namespace")
        if namespace is None:
            ok, ns_data, err = self.BuildNamespace()
            if not ok:
                return (0, None, err)
            namespace = ns_data
        self.state["exec_count"] = self.state["exec_count"] + 1
        try:
            exec(source, dict(namespace), namespace)
        except Exception as exc:
            return (0, None, ("EXEC_FAILED", str(exc), 0))
        result = None
        if "result" in namespace:
            result = namespace["result"]
        return (1, {
            "executed": True,
            "namespace": namespace,
            "result": result,
        }, None)

    def SafeEval(self, params=None):
        """
        #[@METHOD]{[@name<SafeEval>][@return<Tuple3>]}
        Scan expression, evaluate with restricted globals and state locals.
        """
        expr = self._p(params, "expr")
        if expr is None:
            return (0, None, ("NO_EXPR", "missing expr param", 0))
        ok, scan_data, err = self.ScanCode({"source": expr})
        if not ok:
            return (0, None, err)
        if not scan_data["safe"]:
            return (0, None, (
                "UNSAFE_EXPR",
                "expression blocked by scanner: " + str(scan_data["violation_count"]) + " violations",
                0,
            ))
        state = self._p(params, "state")
        if state is None:
            state = {}
        safe_globals = {}
        for builtin_name in self.SAFE_BUILTINS:
            builtin_obj = __builtins__.get(builtin_name) if isinstance(__builtins__, dict) else getattr(__builtins__, builtin_name, None)
            if builtin_obj is not None:
                safe_globals[builtin_name] = builtin_obj
        self.state["exec_count"] = self.state["exec_count"] + 1
        try:
            result = eval(expr, safe_globals, state)
        except Exception as exc:
            return (0, None, ("EVAL_FAILED", str(exc), 0))
        return (1, result, None)

    def ValidateUnit(self, params=None):
        """
        #[@METHOD]{[@name<ValidateUnit>][@return<Tuple3>]}
        Full validation of a unit's source code.
        """
        source = self._p(params, "source")
        if source is None:
            return (0, None, ("NO_SOURCE", "missing source param", 0))
        unit_name = self._p(params, "unit_name", "unknown")
        issues = []
        warnings = []
        ok, scan_data, err = self.ScanCode({"source": source})
        if not ok:
            return (0, None, err)
        if not scan_data["safe"]:
            for violation in scan_data["violations"]:
                issues.append({
                    "line": violation["line"],
                    "type": violation["type"],
                    "detail": violation["detail"],
                })
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            issues.append({
                "line": exc.lineno or 0,
                "type": "SyntaxError",
                "detail": str(exc.msg),
            })
            return (1, {
                "valid": False,
                "issues": issues,
                "warnings": warnings,
            }, None)
        has_run = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "Run":
                has_run = True
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "Run":
                        has_run = True
        if not has_run:
            warnings.append({
                "type": "MissingRun",
                "detail": "no Run() method detected in unit source",
            })
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                val = node.value
                if len(val) > 0 and (val[0] == "/" or val[0] == "~"):
                    issues.append({
                        "line": node.lineno,
                        "type": "HardcodedPath",
                        "detail": "hardcoded path string: " + val,
                    })
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod_root = alias.name.split(".")[0]
                    if mod_root in self.NETWORK_PATTERNS:
                        issues.append({
                            "line": node.lineno,
                            "type": "NetworkOperation",
                            "detail": "network module import: " + alias.name,
                        })
            if isinstance(node, ast.ImportFrom):
                mod_root = (node.module or "").split(".")[0]
                if mod_root in self.NETWORK_PATTERNS:
                    issues.append({
                        "line": node.lineno,
                        "type": "NetworkOperation",
                        "detail": "network module import: " + str(node.module),
                    })
            if isinstance(node, ast.Call):
                func = node.func
                call_name = None
                if isinstance(func, ast.Name):
                    call_name = func.id
                elif isinstance(func, ast.Attribute):
                    call_name = func.attr
                if call_name in self.FILE_OP_PATTERNS:
                    issues.append({
                        "line": node.lineno,
                        "type": "FileOperation",
                        "detail": "file operation call: " + str(call_name),
                    })
        valid = len(issues) == 0
        return (1, {
            "valid": valid,
            "issues": issues,
            "warnings": warnings,
        }, None)

    def Whitelist(self, params=None):
        """
        #[@METHOD]{[@name<Whitelist>][@return<Tuple3>]}
        Return current whitelist of safe modules and safe builtins.
        """
        return (1, {
            "safe_modules": list(self.state["safe_modules"]),
            "safe_builtins": list(self.SAFE_BUILTINS),
            "blocked_modules": list(self.state["blocked_modules"]),
        }, None)

    def AddSafeModule(self, params=None):
        """
        #[@METHOD]{[@name<AddSafeModule>][@return<Tuple3>]}
        Add a module to the safe list at runtime.
        """
        mod_name = self._p(params, "module")
        if mod_name is None:
            return (0, None, ("NO_MODULE", "missing module param", 0))
        if mod_name in self.BLOCKED_MODULES:
            return (0, None, (
                "BLOCKED_MODULE",
                "module is in BLOCKED_MODULES: " + mod_name,
                0,
            ))
        if mod_name not in self.state["safe_modules"]:
            self.state["safe_modules"].append(mod_name)
        return (1, {"added": True, "module": mod_name}, None)

    def RemoveSafeModule(self, params=None):
        """
        #[@METHOD]{[@name<RemoveSafeModule>][@return<Tuple3>]}
        Remove a module from the safe list.
        """
        mod_name = self._p(params, "module")
        if mod_name is None:
            return (0, None, ("NO_MODULE", "missing module param", 0))
        if mod_name in self.state["safe_modules"]:
            self.state["safe_modules"].remove(mod_name)
        return (1, {"removed": True, "module": mod_name}, None)

    def read_state(self, params=None):
        """
        #[@METHOD]{[@name<read_state>][@return<Tuple3>]}
        Return state snapshot.
        """
        return (1, dict(self.state), None)

    def set_config(self, params=None):
        """
        #[@METHOD]{[@name<set_config>][@return<Tuple3>]}
        Update config in state.
        """
        if not params:
            return (0, None, ("NO_PARAMS", "missing config", 0))
        cfg = params.get("config", params)
        if isinstance(cfg, dict):
            self.state.update(cfg)
        return (1, dict(self.state), None)
