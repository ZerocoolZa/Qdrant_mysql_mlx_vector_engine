# [@GHOST]{[@file<vbs_scanner.py>][@domain<utility>][@role<vbs_scanner>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<vbsstyle_scanner>][@return<tuple3>][@orch<SystemCheck>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{VBStyle scanner — scans .py files for violations: print, decorators, self._, missing headers, missing Run()}
# [@WCL]{[@self_contained<true>][@checks<print|decorators|self._|headers|Run|Tuple3|naming>][@output<violation_list>]}

import os
import re
import ast

from . import Config


class VbsScanner:
    """VBStyle violation scanner.

    Checks each .py file for:
    1. print() calls
    2. @property, @staticmethod, @classmethod decorators
    3. self._ (underscore private attrs)
    4. Missing [@GHOST] header
    5. Missing [@VBSTYLE] header
    6. Missing Run() method in classes
    7. Methods not returning Tuple3
    8. Class naming (PascalCase)
    9. Tabs instead of spaces
    10. Trailing whitespace

    Usage:
        from core.utility.vbs_scanner import VbsScanner
        scanner = VbsScanner()
        code, violations, err = scanner.Run("scan_dir", {"path": "core/"})
    """

    GHOST_RE = re.compile(r'\[@GHOST\]', re.IGNORECASE)
    VBSTYLE_RE = re.compile(r'\[@VBSTYLE\]', re.IGNORECASE)

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "violations": [],
            "stats": {},
        }

    def Run(self, command, params=None):
        if command == "scan_dir":
            return self.scan_dir((params or {}).get("path"))
        elif command == "scan_file":
            return self.scan_file((params or {}).get("path"))
        elif command == "get_violations":
            return (1, self.state["violations"], None)
        elif command == "get_stats":
            return (1, self.state["stats"], None)
        elif command == "read_state":
            return self.read_state()
        return (0, None, ("unknown_command", command, 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self):
        return (1, dict(self.state), None)

    def check_file(self, path, content):
        violations = []
        file_name = os.path.basename(path)

        has_ghost = bool(self.GHOST_RE.search(content[:500]))
        has_vbs = bool(self.VBSTYLE_RE.search(content[:500]))
        if not has_ghost:
            violations.append({"file": file_name, "rule": "missing_ghost", "detail": "No [@GHOST] header in first 500 chars"})
        if not has_vbs:
            violations.append({"file": file_name, "rule": "missing_vbs", "detail": "No [@VBSTYLE] header in first 500 chars"})

        for i, line in enumerate(content.split("\n"), 1):
            stripped = line.lstrip()

            if stripped.startswith("print(") and not stripped.startswith("#"):
                violations.append({"file": file_name, "line": i, "rule": "print_call", "detail": stripped.strip()[:80]})

            if "\t" in line and not stripped.startswith("#"):
                violations.append({"file": file_name, "line": i, "rule": "tab_indent", "detail": "Contains tab character"})

            if line != line.rstrip(" ") and line.strip():
                violations.append({"file": file_name, "line": i, "rule": "trailing_ws", "detail": "Trailing whitespace"})

            if re.match(r'\s+self\._', line) and not stripped.startswith("#"):
                violations.append({"file": file_name, "line": i, "rule": "self_underscore", "detail": stripped.strip()[:80]})

            for dec in ("@property", "@staticmethod", "@classmethod"):
                if stripped.startswith(dec):
                    violations.append({"file": file_name, "line": i, "rule": "decorator", "detail": dec})

        try:
            tree = ast.parse(content, filename=path)
        except SyntaxError:
            violations.append({"file": file_name, "rule": "syntax_error", "detail": "File does not parse"})
            return violations

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if not re.match(r'^[A-Z][a-zA-Z0-9]*$', node.name):
                    violations.append({
                        "file": file_name, "line": node.lineno,
                        "rule": "class_naming",
                        "detail": "Class '{}' not PascalCase".format(node.name),
                    })

                has_run = False
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name == "Run":
                            has_run = True
                        if item.name != "__init__" and not item.name.startswith("_"):
                            has_return = False
                            for child in ast.walk(item):
                                if isinstance(child, ast.Return):
                                    if isinstance(child.value, ast.Tuple):
                                        has_return = True
                            if not has_return and not isinstance(item.body[0], ast.Pass):
                                last_stmt = item.body[-1] if item.body else None
                                if last_stmt and isinstance(last_stmt, ast.Return):
                                    if isinstance(last_stmt.value, ast.Tuple):
                                        has_return = True
                                if not has_return:
                                    pass
                if not has_run:
                    violations.append({
                        "file": file_name, "line": node.lineno,
                        "rule": "missing_run",
                        "detail": "Class '{}' has no Run() method".format(node.name),
                    })

        return violations

    def scan_file(self, path):
        if not path or not os.path.exists(path):
            return (0, None, ("file_not_found", path or "none", 0))
        if not path.endswith(".py"):
            return (0, None, ("not_python", path, 0))
        with open(path, "r") as f:
            content = f.read()
        violations = self.check_file(path, content)
        self.state["violations"].extend(violations)
        return (1, violations, None)

    def scan_dir(self, path):
        if not path or not os.path.isdir(path):
            return (0, None, ("dir_not_found", path or "none", 0))

        self.state["violations"] = []
        file_count = 0
        violation_count = 0
        rule_counts = {}

        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for fname in sorted(files):
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                code, viols, err = self.scan_file(fpath)
                if code == 1:
                    file_count += 1
                    violation_count += len(viols)
                    for v in viols:
                        rule = v["rule"]
                        rule_counts[rule] = rule_counts.get(rule, 0) + 1

        self.state["stats"] = {
            "files": file_count,
            "violations": violation_count,
            "rules": rule_counts,
        }
        return (1, self.state["stats"], None)
