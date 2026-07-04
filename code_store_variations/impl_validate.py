import ast
import re


class DomValidate:
    """VBStyle source validation: checks naming, headers, dispatch, tuple3 returns."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "check_dispatch": self.check_dispatch,
            "check_ghost": self.check_ghost,
            "check_headers": self.check_headers,
            "check_init": self.check_init,
            "check_naming": self.check_naming,
            "check_no_decorator": self.check_no_decorator,
            "check_no_hardcode": self.check_no_hardcode,
            "check_no_print": self.check_no_print,
            "check_pascal": self.check_pascal,
            "check_run": self.check_run,
            "check_self_state": self.check_self_state,
            "check_state": self.check_state,
            "check_tuple3": self.check_tuple3,
            "check_vbstyle": self.check_vbstyle,
            "enforce": self.enforce,
            "fix": self.fix,
            "report": self.report,
        }
        if command in handlers:
            return handlers[command](params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def _parse(self, src):
        if not src:
            return None, "empty_source"
        try:
            return ast.parse(src), None
        except SyntaxError as e:
            return None, f"syntax_error: {e}"

    def check_dispatch(self, params=None):
        params = params or {}
        try:
            src = params.get("source", "")
            tree, err = self._parse(src)
            if err:
                return (0, None, ("CHECK_DISPATCH_ERROR", err, 0))
            found = False
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and item.name == "Run":
                            for sub in ast.walk(item):
                                if isinstance(sub, ast.Compare):
                                    found = True
            result = {"domain": "validate", "method": "check_dispatch", "data": {"has_dispatch": found}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_DISPATCH_ERROR", str(e), 0))

    def check_ghost(self, params=None):
        params = params or {}
        try:
            src = params.get("source", "")
            tree, err = self._parse(src)
            if err:
                return (0, None, ("CHECK_GHOST_ERROR", err, 0))
            classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            ghosts = [c for c in classes if c.startswith("Ghost")]
            result = {"domain": "validate", "method": "check_ghost", "data": {"ghost_classes": ghosts, "count": len(ghosts)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_GHOST_ERROR", str(e), 0))

    def check_headers(self, params=None):
        params = params or {}
        try:
            src = params.get("source", "")
            lines = src.splitlines()
            has_class = any(re.match(r"^class\s+\w+", l) for l in lines)
            has_docstring = '"""' in src or "'''" in src
            has_init = "def __init__" in src
            has_run = "def Run" in src
            missing = []
            if not has_class:
                missing.append("class")
            if not has_docstring:
                missing.append("docstring")
            if not has_init:
                missing.append("__init__")
            if not has_run:
                missing.append("Run")
            result = {"domain": "validate", "method": "check_headers", "data": {"missing": missing, "ok": len(missing) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_HEADERS_ERROR", str(e), 0))

    def check_init(self, params=None):
        params = params or {}
        try:
            src = params.get("source", "")
            tree, err = self._parse(src)
            if err:
                return (0, None, ("CHECK_INIT_ERROR", err, 0))
            found = False
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                    arg_names = [a.arg for a in node.args.args]
                    if "self" in arg_names:
                        found = True
            result = {"domain": "validate", "method": "check_init", "data": {"has_init": found}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_INIT_ERROR", str(e), 0))

    def check_naming(self, params=None):
        params = params or {}
        try:
            src = params.get("source", "")
            tree, err = self._parse(src)
            if err:
                return (0, None, ("CHECK_NAMING_ERROR", err, 0))
            classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            methods = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            bad_classes = [c for c in classes if not re.match(r"^[A-Z][A-Za-z0-9]*$", c)]
            bad_methods = [m for m in methods if m not in ("__init__",) and not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", m)]
            result = {"domain": "validate", "method": "check_naming", "data": {"bad_classes": bad_classes, "bad_methods": bad_methods, "ok": len(bad_classes) == 0 and len(bad_methods) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_NAMING_ERROR", str(e), 0))

    def check_no_decorator(self, params=None):
        params = params or {}
        try:
            src = params.get("source", "")
            tree, err = self._parse(src)
            if err:
                return (0, None, ("CHECK_NO_DECORATOR_ERROR", err, 0))
            decorators = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.decorator_list:
                    decorators.append(getattr(node, "name", "?"))
            result = {"domain": "validate", "method": "check_no_decorator", "data": {"decorators": decorators, "ok": len(decorators) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_NO_DECORATOR_ERROR", str(e), 0))

    def check_no_hardcode(self, params=None):
        params = params or {}
        try:
            src = params.get("source", "")
            tree, err = self._parse(src)
            if err:
                return (0, None, ("CHECK_NO_HARDCODE_ERROR", err, 0))
            hardcoded = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name) and t.id.isupper():
                            if isinstance(node.value, ast.Constant):
                                hardcoded.append(t.id)
            result = {"domain": "validate", "method": "check_no_hardcode", "data": {"hardcoded_constants": hardcoded, "ok": len(hardcoded) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_NO_HARDCODE_ERROR", str(e), 0))

    def check_no_print(self, params=None):
        params = params or {}
        try:
            src = params.get("source", "")
            tree, err = self._parse(src)
            if err:
                return (0, None, ("CHECK_NO_PRINT_ERROR", err, 0))
            prints = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                    prints.append(node.lineno)
            result = {"domain": "validate", "method": "check_no_print", "data": {"print_lines": prints, "ok": len(prints) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_NO_PRINT_ERROR", str(e), 0))

    def check_pascal(self, params=None):
        params = params or {}
        try:
            src = params.get("source", "")
            tree, err = self._parse(src)
            if err:
                return (0, None, ("CHECK_PASCAL_ERROR", err, 0))
            classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            bad = [c for c in classes if not re.match(r"^[A-Z][A-Za-z0-9]*$", c)]
            result = {"domain": "validate", "method": "check_pascal", "data": {"classes": classes, "bad_pascal": bad, "ok": len(bad) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_PASCAL_ERROR", str(e), 0))

    def check_run(self, params=None):
        params = params or {}
        try:
            src = params.get("source", "")
            tree, err = self._parse(src)
            if err:
                return (0, None, ("CHECK_RUN_ERROR", err, 0))
            found = False
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "Run":
                    found = True
            result = {"domain": "validate", "method": "check_run", "data": {"has_run": found}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_RUN_ERROR", str(e), 0))

    def check_self_state(self, params=None):
        params = params or {}
        try:
            src = params.get("source", "")
            tree, err = self._parse(src)
            if err:
                return (0, None, ("CHECK_SELF_STATE_ERROR", err, 0))
            found = False
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self" and node.attr == "state":
                    found = True
            result = {"domain": "validate", "method": "check_self_state", "data": {"has_self_state": found}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_SELF_STATE_ERROR", str(e), 0))

    def check_state(self, params=None):
        params = params or {}
        try:
            src = params.get("source", "")
            tree, err = self._parse(src)
            if err:
                return (0, None, ("CHECK_STATE_ERROR", err, 0))
            is_dict = False
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self" and t.attr == "state":
                            if isinstance(node.value, ast.Dict):
                                is_dict = True
            result = {"domain": "validate", "method": "check_state", "data": {"state_is_dict": is_dict}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_STATE_ERROR", str(e), 0))

    def check_tuple3(self, params=None):
        params = params or {}
        try:
            src = params.get("source", "")
            tree, err = self._parse(src)
            if err:
                return (0, None, ("CHECK_TUPLE3_ERROR", err, 0))
            tuple_returns = 0
            total_returns = 0
            for node in ast.walk(tree):
                if isinstance(node, ast.Return) and node.value is not None:
                    total_returns += 1
                    if isinstance(node.value, ast.Tuple) and len(node.value.elts) == 3:
                        tuple_returns += 1
            result = {"domain": "validate", "method": "check_tuple3", "data": {"tuple3_returns": tuple_returns, "total_returns": total_returns, "ok": tuple_returns == total_returns and total_returns > 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_TUPLE3_ERROR", str(e), 0))

    def check_vbstyle(self, params=None):
        params = params or {}
        try:
            src = params.get("source", "")
            checks = {}
            for name, fn in [
                ("headers", self.check_headers),
                ("init", self.check_init),
                ("run", self.check_run),
                ("pascal", self.check_pascal),
                ("no_decorator", self.check_no_decorator),
                ("no_print", self.check_no_print),
                ("self_state", self.check_self_state),
                ("tuple3", self.check_tuple3),
            ]:
                ok, data, err = fn({"source": src})
                if ok:
                    checks[name] = data.get("data", {}).get("ok", False)
                else:
                    checks[name] = False
            overall = all(checks.values())
            result = {"domain": "validate", "method": "check_vbstyle", "data": {"checks": checks, "vbstyle_ok": overall}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_VBSTYLE_ERROR", str(e), 0))

    def enforce(self, params=None):
        params = params or {}
        try:
            src = params.get("source", "")
            ok, data, err = self.check_vbstyle({"source": src})
            if not ok:
                return (0, None, ("ENFORCE_ERROR", "vbstyle check failed", 0))
            violations = []
            for k, v in data["data"]["checks"].items():
                if not v:
                    violations.append(k)
            result = {"domain": "validate", "method": "enforce", "data": {"violations": violations, "enforced": len(violations) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ENFORCE_ERROR", str(e), 0))

    def fix(self, params=None):
        params = params or {}
        try:
            src = params.get("source", "")
            fixed = src
            if "print(" in fixed:
                fixed = re.sub(r"print\([^)]*\)\s*\n?", "", fixed)
            if not fixed.startswith('"""') and '"""' not in fixed.split("\n")[0]:
                lines = fixed.splitlines()
                if lines and lines[0].startswith("class "):
                    cname = re.match(r"class\s+(\w+)", lines[0])
                    if cname:
                        doc = f'    """{cname.group(1)} VBStyle class."""\n'
                        fixed = lines[0] + "\n" + doc + "\n".join(lines[1:])
            result = {"domain": "validate", "method": "fix", "data": {"fixed_source": fixed, "changed": fixed != src}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FIX_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            src = params.get("source", "")
            ok, data, err = self.check_vbstyle({"source": src})
            checks = data["data"]["checks"] if ok else {}
            passed = [k for k, v in checks.items() if v]
            failed = [k for k, v in checks.items() if not v]
            result = {"domain": "validate", "method": "report", "data": {"passed": passed, "failed": failed, "summary": f"{len(passed)} passed, {len(failed)} failed"}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))
