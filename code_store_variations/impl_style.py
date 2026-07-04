import re
import ast


class DomStyle:
    """VBStyle compliance checking and enforcement for source code."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        if command in ("Run",):
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        handler = getattr(self, command, None)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def _parse(self, params):
        code = params.get("code") or params.get("source") or ""
        if not code and params.get("path"):
            try:
                with open(params.get("path"), "r", encoding="utf-8") as fh:
                    code = fh.read()
            except Exception:
                code = ""
        return code

    def check_class(self, params=None):
        params = params or {}
        try:
            code = self._parse(params)
            issues = []
            for m in re.finditer(r"class\s+(\w+)", code):
                name = m.group(1)
                if not re.match(r"^Dom[A-Z]", name) and name not in ("VBStyle",):
                    issues.append({"rule": "class_name_pascal", "name": name, "msg": "class name should be Dom<Pascal>"})
            result = {"domain": "style", "method": "check_class", "data": {"issues": issues, "ok": len(issues) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_CLASS_ERROR", str(e), 0))

    def check_format(self, params=None):
        params = params or {}
        try:
            code = self._parse(params)
            issues = []
            lines = code.splitlines()
            for i, line in enumerate(lines, 1):
                if "\t" in line:
                    issues.append({"line": i, "rule": "no_tabs", "msg": "tab character found"})
                if line.endswith(" ") or line.endswith("\t"):
                    issues.append({"line": i, "rule": "trailing_ws", "msg": "trailing whitespace"})
                if len(line) > 120:
                    issues.append({"line": i, "rule": "line_too_long", "msg": f"line length {len(line)} > 120"})
            result = {"domain": "style", "method": "check_format", "data": {"issues": issues, "ok": len(issues) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_FORMAT_ERROR", str(e), 0))

    def check_ghost(self, params=None):
        params = params or {}
        try:
            code = self._parse(params)
            issues = []
            if "def Run" not in code:
                issues.append({"rule": "missing_run", "msg": "no Run dispatch method"})
            if "self.state" not in code:
                issues.append({"rule": "missing_state", "msg": "no self.state dict"})
            result = {"domain": "style", "method": "check_ghost", "data": {"issues": issues, "ok": len(issues) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_GHOST_ERROR", str(e), 0))

    def check_header(self, params=None):
        params = params or {}
        try:
            code = self._parse(params)
            issues = []
            lines = code.splitlines()
            if not lines:
                issues.append({"rule": "empty", "msg": "no code"})
            else:
                if not (lines[0].startswith('"""') or lines[0].startswith("'''")):
                    if not any('"""' in l for l in lines[:5]):
                        issues.append({"rule": "missing_docstring", "msg": "class docstring missing"})
            result = {"domain": "style", "method": "check_header", "data": {"issues": issues, "ok": len(issues) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_HEADER_ERROR", str(e), 0))

    def check_method(self, params=None):
        params = params or {}
        try:
            code = self._parse(params)
            issues = []
            for m in re.finditer(r"def\s+(\w+)\s*\(", code):
                name = m.group(1)
                if name in ("Run", "__init__"):
                    continue
                if not re.match(r"^[a-z][a-zA-Z0-9_]*$", name):
                    issues.append({"rule": "method_name", "name": name, "msg": "method name not snake/lower"})
            result = {"domain": "style", "method": "check_method", "data": {"issues": issues, "ok": len(issues) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_METHOD_ERROR", str(e), 0))

    def check_naming(self, params=None):
        params = params or {}
        try:
            code = self._parse(params)
            issues = []
            for m in re.finditer(r"class\s+(\w+)", code):
                name = m.group(1)
                if not re.match(r"^[A-Z][a-zA-Z0-9]*$", name):
                    issues.append({"rule": "class_pascal", "name": name})
            for m in re.finditer(r"^([A-Z_][A-Z0-9_]+)\s*=", code, re.M):
                pass
            result = {"domain": "style", "method": "check_naming", "data": {"issues": issues, "ok": len(issues) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_NAMING_ERROR", str(e), 0))

    def check_structure(self, params=None):
        params = params or {}
        try:
            code = self._parse(params)
            issues = []
            try:
                ast.parse(code)
            except SyntaxError as se:
                issues.append({"rule": "syntax", "msg": str(se)})
            if "def __init__" not in code:
                issues.append({"rule": "missing_init", "msg": "no __init__"})
            if "def Run" not in code:
                issues.append({"rule": "missing_run", "msg": "no Run dispatch"})
            result = {"domain": "style", "method": "check_structure", "data": {"issues": issues, "ok": len(issues) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_STRUCTURE_ERROR", str(e), 0))

    def check_vbstyle(self, params=None):
        params = params or {}
        try:
            code = self._parse(params)
            checks = ["check_class", "check_format", "check_ghost", "check_header", "check_method", "check_naming", "check_structure"]
            all_issues = []
            for c in checks:
                ok, data, err = getattr(self, c)({"code": code})
                if err:
                    all_issues.append({"check": c, "error": err[1]})
                elif data and not data["data"]["ok"]:
                    for it in data["data"]["issues"]:
                        it["check"] = c
                        all_issues.append(it)
            result = {"domain": "style", "method": "check_vbstyle", "data": {"issues": all_issues, "ok": len(all_issues) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_VBSTYLE_ERROR", str(e), 0))

    def enforce(self, params=None):
        params = params or {}
        try:
            code = self._parse(params)
            fixed = code
            fixed = self._fix_format_text(fixed)
            fixed = self._fix_header_text(fixed)
            fixed = self._fix_naming_text(fixed)
            changed = fixed != code
            result = {"domain": "style", "method": "enforce", "data": {"changed": changed, "code": fixed}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ENFORCE_ERROR", str(e), 0))

    def fix_format(self, params=None):
        params = params or {}
        try:
            code = self._parse(params)
            fixed = self._fix_format_text(code)
            result = {"domain": "style", "method": "fix_format", "data": {"changed": fixed != code, "code": fixed}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FIX_FORMAT_ERROR", str(e), 0))

    def _fix_format_text(self, code):
        lines = code.splitlines()
        out = []
        for line in lines:
            line = line.replace("\t", "    ")
            line = line.rstrip()
            out.append(line)
        return "\n".join(out) + ("\n" if code.endswith("\n") else "")

    def fix_header(self, params=None):
        params = params or {}
        try:
            code = self._parse(params)
            fixed = self._fix_header_text(code)
            result = {"domain": "style", "method": "fix_header", "data": {"changed": fixed != code, "code": fixed}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FIX_HEADER_ERROR", str(e), 0))

    def _fix_header_text(self, code):
        lines = code.splitlines()
        if not lines:
            return code
        if not any('"""' in l for l in lines[:5]):
            m = re.search(r"class\s+(\w+)", code)
            cname = m.group(1) if m else "DomClass"
            doc = f'"""{cname} VBStyle class."""'
            for i, line in enumerate(lines):
                if line.startswith("class "):
                    indent = ""
                    lines.insert(i + 1, indent + doc)
                    break
            return "\n".join(lines) + ("\n" if code.endswith("\n") else "")
        return code

    def fix_naming(self, params=None):
        params = params or {}
        try:
            code = self._parse(params)
            fixed = self._fix_naming_text(code)
            result = {"domain": "style", "method": "fix_naming", "data": {"changed": fixed != code, "code": fixed}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FIX_NAMING_ERROR", str(e), 0))

    def _fix_naming_text(self, code):
        def cap(m):
            name = m.group(1)
            if name.startswith("dom_"):
                name = "Dom" + "".join(p.capitalize() for p in name[4:].split("_"))
            return "class " + name + ":"
        return re.sub(r"class\s+(dom_\w+):", cap, code)

    def report(self, params=None):
        params = params or {}
        try:
            code = self._parse(params)
            ok, data, err = self.check_vbstyle({"code": code})
            issues = data["data"]["issues"] if ok and data else []
            counts = {}
            for it in issues:
                r = it.get("rule", it.get("check", "unknown"))
                counts[r] = counts.get(r, 0) + 1
            result = {"domain": "style", "method": "report", "data": {"total_issues": len(issues), "by_rule": counts, "issues": issues}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))

    def score(self, params=None):
        params = params or {}
        try:
            code = self._parse(params)
            ok, data, err = self.check_vbstyle({"code": code})
            issues = data["data"]["issues"] if ok and data else []
            total_checks = 7
            failed = len(set(it.get("check", it.get("rule", "")) for it in issues))
            score = max(0, round((1 - failed / total_checks) * 100, 2))
            result = {"domain": "style", "method": "score", "data": {"score": score, "issues": len(issues)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SCORE_ERROR", str(e), 0))
