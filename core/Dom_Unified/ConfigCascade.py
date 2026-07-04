# [@GHOST]{[@file<ConfigCascade.py>][@domain<Dom_Unified>][@role<config_authority>][@auth<cascade>][@date<2026-06-28>][@ver<2.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<config_authority>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{ConfigCascade — unified config authority. Merges Prj_VBScanner + config_extractor + ConfigCascade into one VBStyle class.}
# [@CLASS]{ConfigCascade}
# [@METHOD]{Run,scan,extract,generate,read,write,update,verify,catalog,scan_files,file_index,full_run,regex_extract}

"""
ConfigCascade — the unified config authority.

Merges three tools into one:
  1. ConfigCascade  — scan, extract (AST), generate, read, write, update, verify, catalog
  2. Prj_VBScanner   — file index generation, BCL tokens, VBStyle compliance, config template
  3. config_extractor — regex-based extraction (works even with syntax errors)

Commands (Run dispatch):
  scan         — walk folder, find config-like constants in all .py files
  extract      — AST-extract config data from a single .py file
  regex_extract — regex-extract config data (fallback for syntax-broken files)
  generate     — create a Config.py for a domain folder
  read         — load an existing config.py and return its constants
  write        — write a config.py file from scratch
  update       — update specific keys in an existing config.py
  verify       — check VBStyle compliance of a config.py
  catalog      — list all config.py files across the project
  scan_files   — scan folder for file index entries (BCL tokens, VBStyle, BCL headers)
  file_index   — append/replace FILE_INDEX in Config.py
  full_run     — generate config + scan files + append file index
"""

import os
import re
import ast
import json
import sys
import datetime
from datetime import datetime as Dt

# ─── VBSTYLE COMPLIANCE REGEXES (from Prj_VBScanner) ─────────────────────
GHOST_RE = re.compile(r"#\[@GHOST\]", re.IGNORECASE)
VBSTYLE_RE = re.compile(r"#\[@VBSTYLE\]", re.IGNORECASE)
TUPLE3_RE = re.compile(r"Tuple3|tuple3|\(1,\s*\w+,\s*None\)|\(0,\s*None,", re.IGNORECASE)
STATE_DICT_RE = re.compile(r"self\.state\s*=")
RUN_DISPATCH_RE = re.compile(r"def\s+Run\s*\(")
DECORATOR_RE = re.compile(r"^\s*@(?:staticmethod|classmethod|property|abstractmethod|functools)")
PRINT_RE = re.compile(r"\bprint\s*\(")
SELF_UNDERSCORE_RE = re.compile(r"self\._[a-z]")
HARDCODED_PATH_RE = re.compile(r'["\']/(?:Users|home|tmp|var|opt)/')
CLASS_RE = re.compile(r"^(\s*)class\s+(\w+)")
DEF_RE = re.compile(r"^(\s+)def\s+(\w+)\((.*)\)")
BCL_HEADER_START_RE = re.compile(r"^\s*#\[@(\w+)\]")


class ConfigCascade:
    """
    Unified config authority — scans, extracts, generates, reads, writes,
    updates, verifies, catalogs config.py files.
    Also generates file indexes with BCL tokens and VBStyle compliance checks.
    VBStyle compliant: Run() dispatch, Tuple3 returns, self.state dict.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "project_root": param.get("project_root", os.getcwd()) if param else os.getcwd(),
                "header_author": param.get("author", "cascade") if param else "cascade",
                "auto_verify": param.get("auto_verify", True) if param else True,
            },
            "catalog": [],
            "last_scan": None,
            "files": [],
            "folder": None,
            "config_path": None,
            "errors": [],
            "created_count": 0,
            "appended_count": 0,
            "stats": {"scanned": 0, "extracted": 0, "generated": 0, "verified": 0, "errors": 0},
        }
        if param:
            for key, val in param.items():
                if key in self.state["config"]:
                    self.state["config"][key] = val

    def Run(self, command, params=None):
        dispatch = {
            "scan": self._cmd_scan,
            "extract": self._cmd_extract,
            "regex_extract": self._cmd_regex_extract,
            "generate": self._cmd_generate,
            "read": self._cmd_read,
            "write": self._cmd_write,
            "update": self._cmd_update,
            "verify": self._cmd_verify,
            "catalog": self._cmd_catalog,
            "scan_files": self._cmd_scan_files,
            "file_index": self._cmd_file_index,
            "full_run": self._cmd_full_run,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", f"Unknown: {command}", 0))
        return handler(params or {})

    def read_state(self, params=None):
        safe = {k: v for k, v in self.state.items() if k not in ("conn",)}
        return (1, safe, None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def _cmd_scan(self, params):
        path = self._p(params, "path")
        if not path or not os.path.isdir(path):
            return (0, None, ("ERR_PATH", f"Invalid path: {path}", 0))
        results = []
        py_files = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "node_modules", ".git")]
            for fname in files:
                if fname.endswith(".py"):
                    py_files.append(os.path.join(root, fname))
        for pyfile in py_files:
            ok, data, err = self._extract_from_file(pyfile)
            if ok and data["constants"]:
                results.append({
                    "file": pyfile,
                    "domain": os.path.basename(os.path.dirname(pyfile)),
                    "constant_count": len(data["constants"]),
                    "constants": data["constants"],
                    "has_config_class": data["has_config_class"],
                    "has_run_method": data["has_run_method"],
                })
                self.state["stats"]["scanned"] += 1
        self.state["last_scan"] = {"path": path, "files": len(py_files), "with_config": len(results)}
        return (1, {"scanned_files": len(py_files), "files_with_config": len(results), "results": results}, None)


    def _cmd_extract(self, params):
        filepath = self._p(params, "file")
        if not filepath or not os.path.isfile(filepath):
            return (0, None, ("ERR_FILE", f"File not found: {filepath}", 0))
        ok, data, err = self._extract_from_file(filepath)
        if not ok:
            return (0, None, err)
        self.state["stats"]["extracted"] += 1
        return (1, data, None)


    def _extract_from_file(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
        except Exception as e:
            return (0, None, ("ERR_READ", str(e), 0))
        constants = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return (1, {"file": filepath, "constants": [], "constant_count": 0, "has_config_class": False, "has_run_method": False, "classes": []}, None)
        has_config_class = False
        has_run_method = False
        classes = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        val = self._ast_to_value(node.value)
                        if val is not None:
                            constants.append({
                                "name": target.id,
                                "value": val,
                                "type": type(val).__name__,
                                "line": node.lineno,
                            })
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
                if "Config" in node.name or "config" in node.name.lower():
                    has_config_class = True
                for item in ast.iter_child_nodes(node):
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name == "Run":
                            has_run_method = True
        return (1, {
            "file": filepath,
            "constants": constants,
            "has_config_class": has_config_class,
            "has_run_method": has_run_method,
            "classes": classes,
            "constant_count": len(constants),
        }, None)


    def _ast_to_value(self, node):
        try:
            if isinstance(node, ast.Constant):
                return node.value
            elif isinstance(node, ast.List):
                return [self._ast_to_value(e) for e in node.elts]
            elif isinstance(node, ast.Tuple):
                return tuple(self._ast_to_value(e) for e in node.elts)
            elif isinstance(node, ast.Dict):
                return {self._ast_to_value(k): self._ast_to_value(v) for k, v in zip(node.keys, node.values)}
            elif isinstance(node, ast.Name):
                return node.id
            elif isinstance(node, ast.Attribute):
                return f"{self._ast_to_value(node.value)}.{node.attr}"
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                left = self._ast_to_value(node.left)
                right = self._ast_to_value(node.right)
                if isinstance(left, str) and isinstance(right, str):
                    return left + right
                return f"{left} + {right}"
            elif isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                elif isinstance(node.func, ast.Name):
                    func_name = node.func.id
                args = [self._ast_to_value(a) for a in node.args]
                return f"{func_name}({', '.join(str(a) for a in args)})"
        except Exception:
            return None
        return None


    def _cmd_generate(self, params):
        path = self._p(params, "path")
        domain_name = self._p(params, "domain")
        if not path or not os.path.isdir(path):
            return (0, None, ("ERR_PATH", f"Invalid folder: {path}", 0))
        if not domain_name:
            domain_name = os.path.basename(os.path.abspath(path))
        config_path = os.path.join(path, "Config.py")
        existing_constants = []
        ok, scan_data, err = self._cmd_scan({"path": path})
        if ok:
            seen = set()
            for result in scan_data["results"]:
                for c in result["constants"]:
                    if c["name"] not in seen and not c["name"].startswith("_"):
                        existing_constants.append(c)
                        seen.add(c["name"])
        content = self._build_config_content(domain_name, config_path, existing_constants)
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_WRITE", str(e), 0))
        self.state["stats"]["generated"] += 1
        return (1, {
            "generated": True,
            "file": config_path,
            "domain": domain_name,
            "constants_included": len(existing_constants),
            "constants": [c["name"] for c in existing_constants],
        }, None)


    def _build_config_content(self, domain_name, config_path, constants):
        now = datetime.datetime.now().strftime("%Y-%m-%d")
        author = self.state["config"]["header_author"]
        lines = []
        lines.append(f"# [@GHOST]{{[@file<Config.py>][@domain<{domain_name}>][@role<config>][@auth<{author}>][@date<{now}>][@ver<1.0>]}}")
        lines.append(f"# [@VBSTYLE]{{[@auth<{author}>][@role<config>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}}")
        lines.append(f"# [@SUMMARY]{{Config for {domain_name} — generated by ConfigCascade}}")
        lines.append(f"# [@CLASS]{{Config}}")
        lines.append(f"# [@METHOD]{{Run,read_state,set_config}}")
        lines.append("")
        lines.append(f'"""')
        lines.append(f"Config for {domain_name} domain.")
        lines.append(f"All paths, DB settings, and constants live here.")
        lines.append(f'"""')
        lines.append("")
        lines.append("import os")
        lines.append("")
        lines.append(f"BASE_DIR = os.path.dirname(os.path.abspath(__file__))")
        lines.append(f'DOMAIN = "{domain_name}"')
        lines.append(f'VERSION = "1.0"')
        lines.append("")
        if constants:
            lines.append("# ════════════════════════════════════════════")
            lines.append(f"# EXTRACTED CONSTANTS (from {domain_name} .py files)")
            lines.append("# ════════════════════════════════════════════")
            for c in constants:
                val_repr = self._format_value(c["value"])
                lines.append(f"{c['name']} = {val_repr}")
            lines.append("")
        lines.append("class Config:")
        lines.append(f'    """Config holder for {domain_name}."""')
        lines.append("")
        lines.append("    def __init__(self, mem=None, db=None, param=None):")
        lines.append("        self.state = {")
        lines.append('            "config": {')
        lines.append('                "base_dir": BASE_DIR,')
        lines.append('                "domain": DOMAIN,')
        lines.append('                "version": VERSION,')
        for c in constants:
            if c["name"] in ("BASE_DIR", "DOMAIN", "VERSION"):
                continue
            key_lower = c["name"].lower()
            lines.append(f'                "{key_lower}": {c["name"]},')
        lines.append("            },")
        lines.append('            "initialized": True,')
        lines.append("        }")
        lines.append("        if param:")
        lines.append("            for key, val in param.items():")
        lines.append("                if key in self.state[\"config\"]:")
        lines.append("                    self.state[\"config\"][key] = val")
        lines.append("")
        lines.append("    def Run(self, command, params=None):")
        lines.append("        if command == \"get\":")
        lines.append("            key = params.get(\"key\", \"\") if params else \"\"")
        lines.append("            if not key:")
        lines.append("                return (1, dict(self.state[\"config\"]), None)")
        lines.append("            return (1, self.state[\"config\"].get(key), None)")
        lines.append("        if command == \"set\":")
        lines.append("            if not params:")
        lines.append("                return (0, None, (\"ERR_NO_PARAMS\", \"params required\", 0))")
        lines.append("            for key, val in params.items():")
        lines.append("                if key in self.state[\"config\"]:")
        lines.append("                    self.state[\"config\"][key] = val")
        lines.append("            return (1, dict(self.state[\"config\"]), None)")
        lines.append("        return (0, None, (\"ERR_UNKNOWN_CMD\", f\"Unknown: {command}\", 0))")
        lines.append("")
        lines.append("    def read_state(self, params=None):")
        lines.append("        return (1, dict(self.state), None)")
        lines.append("")
        lines.append("    def set_config(self, params):")
        lines.append("        for key, val in params.items():")
        lines.append("            if key in self.state[\"config\"]:")
        lines.append("                self.state[\"config\"][key] = val")
        lines.append("        return (1, dict(self.state[\"config\"]), None)")
        return "\n".join(lines) + "\n"


    def _format_value(self, val):
        if isinstance(val, bool):
            return "True" if val else "False"
        elif isinstance(val, (int, float)):
            return str(val)
        elif isinstance(val, str):
            if self._is_python_expr(val):
                return val
            return f'"{val}"'
        elif isinstance(val, list):
            return "[" + ", ".join(self._format_value(v) for v in val) + "]"
        elif isinstance(val, dict):
            items = ", ".join(f'{self._format_value(k)}: {self._format_value(v)}' for k, v in val.items())
            return "{" + items + "}"
        elif isinstance(val, tuple):
            return "(" + ", ".join(self._format_value(v) for v in val) + ")"
        elif val is None:
            return "None"
        return f'"{val}"'


    def _is_python_expr(self, val):
        """Check if a string value is a Python expression (not a literal)."""
        if "(" in val and ")" in val:
            return True
        if val.startswith(("os.", "sys.", "pathlib.", "datetime.")):
            return True
        if val in ("True", "False", "None"):
            return True
        if val.startswith("BASE_DIR") or val.startswith("PROJECT_DIR"):
            return True
        if "." in val and not val.startswith("/") and not val.startswith("~"):
            parts = val.split(".")
            if all(p.isidentifier() for p in parts):
                return True
        return False


    def _cmd_read(self, params):
        filepath = self._p(params, "file")
        if not filepath or not os.path.isfile(filepath):
            return (0, None, ("ERR_FILE", f"File not found: {filepath}", 0))
        ok, data, err = self._extract_from_file(filepath)
        if not ok:
            return (0, None, err)
        return (1, data, None)


    def _cmd_write(self, params):
        path = self._p(params, "path")
        domain_name = self._p(params, "domain")
        constants = self._p(params, "constants", {})
        if not path:
            return (0, None, ("ERR_PATH", "path required", 0))
        if not domain_name:
            domain_name = os.path.basename(os.path.abspath(path))
        config_path = os.path.join(path, "Config.py")
        const_list = [{"name": k, "value": v} for k, v in constants.items()]
        content = self._build_config_content(domain_name, config_path, const_list)
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_WRITE", str(e), 0))
        self.state["stats"]["generated"] += 1
        return (1, {"written": True, "file": config_path, "domain": domain_name}, None)


    def _cmd_update(self, params):
        filepath = self._p(params, "file")
        keys = self._p(params, "keys", {})
        if not filepath or not os.path.isfile(filepath):
            return (0, None, ("ERR_FILE", f"File not found: {filepath}", 0))
        if not keys:
            return (0, None, ("ERR_KEYS", "keys dict required", 0))
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                source = f.read()
        except Exception as e:
            return (0, None, ("ERR_READ", str(e), 0))
        updated = []
        for key, val in keys.items():
            pattern = f"^{key} = .*$"
            replacement = f"{key} = {self._format_value(val)}"
            new_source, count = re.subn(pattern, replacement, source, flags=re.MULTILINE)
            if count > 0:
                source = new_source
                updated.append(key)
            else:
                insert_line = f"{key} = {self._format_value(val)}\n"
                source = insert_line + source
                updated.append(key)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(source)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_WRITE", str(e), 0))
        return (1, {"updated": True, "file": filepath, "keys_updated": updated}, None)


    def _cmd_verify(self, params):
        filepath = self._p(params, "file")
        if not filepath or not os.path.isfile(filepath):
            return (0, None, ("ERR_FILE", f"File not found: {filepath}", 0))
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                source = f.read()
        except Exception as e:
            return (0, None, ("ERR_READ", str(e), 0))
        checks = {
            "has_ghost_header": "[@GHOST]" in source,
            "has_vbstyle_header": "[@VBSTYLE]" in source,
            "has_summary": "[@SUMMARY]" in source,
            "has_class_header": "[@CLASS]" in source,
            "has_run_method": bool(re.search(r"def Run\s*\(\s*self\s*,", source)),
            "has_tuple3_return": "(1," in source and "None)" in source,
            "no_print": "print(" not in source,
            "no_decorators": "@property" not in source and "@staticmethod" not in source and "@classmethod" not in source,
            "no_self_underscore": "self._" not in source,
            "no_tabs": "\t" not in source,
            "has_state_dict": "self.state" in source,
        }
        passed = sum(1 for v in checks.values() if v)
        failed = [k for k, v in checks.items() if not v]
        is_compliant = len(failed) == 0
        self.state["stats"]["verified"] += 1
        return (1, {
            "file": filepath,
            "compliant": is_compliant,
            "passed": passed,
            "failed": failed,
            "checks": checks,
        }, None)


    def _cmd_catalog(self, params):
        root = self._p(params, "root", self.state["config"]["project_root"])
        if not os.path.isdir(root):
            return (0, None, ("ERR_ROOT", f"Invalid root: {root}", 0))
        config_files = []
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "node_modules", ".git", "venv", "env")]
            for fname in files:
                if fname.lower() in ("config.py", "config_.py") or fname.lower().startswith("config_") and fname.endswith(".py"):
                    fpath = os.path.join(dirpath, fname)
                    ok, verify_data, _ = self._cmd_verify({"file": fpath})
                    ok, extract_data, _ = self._extract_from_file(fpath)
                    config_files.append({
                        "file": fpath,
                        "domain": os.path.basename(dirpath),
                        "compliant": verify_data.get("compliant", False) if verify_data else False,
                        "constant_count": extract_data.get("constant_count", 0) if extract_data else 0,
                        "has_config_class": extract_data.get("has_config_class", False) if extract_data else False,
                        "has_run_method": extract_data.get("has_run_method", False) if extract_data else False,
                    })
        self.state["catalog"] = config_files
        compliant_count = sum(1 for c in config_files if c["compliant"])
        return (1, {
            "root": root,
            "total_config_files": len(config_files),
            "compliant": compliant_count,
            "non_compliant": len(config_files) - compliant_count,
            "files": config_files,
        }, None)


    def _scan_file(self, fpath, fname):
        """Scan a single .py file and return a FILE_INDEX entry."""
        try:
            stat = os.stat(fpath)
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            lines = content.splitlines()
        except Exception as e:
            self.state['errors'].append(f"{fname}: {e}")
            return None

        # Parse with AST
        classes = []
        functions = []
        purpose = ""

        try:
            tree = ast.parse(content)
            # Extract docstring as purpose
            if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
                doc = tree.body[0].value.value
                if isinstance(doc, str):
                    purpose = doc.strip().split('\n')[0][:200]

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                    classes.append({
                        'name': node.name,
                        'methods': methods,
                    })
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith('_'):
                    # Only top-level functions (not inside classes)
                    if not hasattr(node, '_in_class'):
                        functions.append(node.name)
        except SyntaxError:
            # Fall back to regex parsing
            classes, functions, purpose = self._regex_parse(lines)

        # Check VBStyle compliance
        compliance = self._check_vbstyle(lines)

        # Check BCL headers
        bcl_headers = self._check_bcl_headers(lines)

        # Build entry matching gold standard format
        all_methods = []
        for cls in classes:
            for m in cls['methods']:
                all_methods.append(f"{cls['name']}.{m}")

        entry = {
            'file': fname,
            'purpose': purpose or '(no docstring)',
            'classes': [cls['name'] for cls in classes],
            'methods': all_methods if all_methods else [],
            'functions': functions,
            'vbstyle_compliant': compliance['is_compliant'],
            'vbstyle_rules_passed': compliance['passed'],
            'vbstyle_rules_total': compliance['total'],
            'vbstyle_failed': compliance['failed'],
            'has_bcl': bcl_headers['has_bcl'],
            'bcl_headers_found': bcl_headers['headers'],
            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'size': stat.st_size,
            'lines': len(lines),
        }
        return entry


    def _scan_non_py_file(self, fpath, fname):
        """Scan a non-.py file (md, sql, json, etc.) and return a basic entry."""
        try:
            stat = os.stat(fpath)
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            lines = content.splitlines()
        except Exception as e:
            self.state['errors'].append(f"{fname}: {e}")
            return None

        # Extract purpose from first non-empty line
        purpose = ""
        for line in lines:
            if line.strip() and not line.strip().startswith('#'):
                purpose = line.strip()[:200]
                break
            elif line.strip().startswith('#') and not line.strip().startswith('#!'):
                purpose = line.strip().lstrip('#').strip()[:200]
                break

        entry = {
            'file': fname,
            'purpose': purpose or '(non-Python file)',
            'classes': [],
            'methods': [],
            'functions': [],
            'vbstyle_compliant': False,
            'vbstyle_rules_passed': 0,
            'vbstyle_rules_total': 0,
            'vbstyle_failed': [],
            'has_bcl': False,
            'bcl_headers_found': [],
            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'size': stat.st_size,
            'lines': len(lines),
        }
        return entry


    def _regex_parse(self, lines):
        """Fallback regex parsing when AST fails."""
        classes = []
        functions = []
        purpose = ""

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if not purpose:
                    purpose = stripped.strip('"""').strip("'''")[:200]

            m = CLASS_RE.match(stripped)
            if m:
                classes.append({'name': m.group(2), 'methods': []})

            m = DEF_RE.match(stripped)
            if m and not m.group(2).startswith('_'):
                functions.append(m.group(2))

        return classes, functions, purpose


    def _check_vbstyle(self, lines):
        """Check VBStyle compliance rules."""
        full_text = "".join(lines)
        checks = {
            'ghost_header': bool(GHOST_RE.search(full_text)),
            'vbstyle_header': bool(VBSTYLE_RE.search(full_text)),
            'tuple3_return': bool(TUPLE3_RE.search(full_text)),
            'state_dict': bool(STATE_DICT_RE.search(full_text)),
            'run_dispatch': bool(RUN_DISPATCH_RE.search(full_text)),
            'no_decorators': not any(DECORATOR_RE.match(l) for l in lines),
            'no_print': not any(PRINT_RE.search(l) for l in lines if not l.strip().startswith("#")),
            'no_self_underscore': not any(SELF_UNDERSCORE_RE.search(l) for l in lines if not l.strip().startswith("#")),
            'no_hardcoded_paths': not any(HARDCODED_PATH_RE.search(l) for l in lines if not l.strip().startswith("#")),
        }

        passed = sum(1 for v in checks.values() if v)
        total = len(checks)
        failed = [k for k, v in checks.items() if not v]
        is_compliant = passed == total

        return {
            'is_compliant': is_compliant,
            'passed': passed,
            'total': total,
            'failed': failed,
        }


    def _check_bcl_headers(self, lines):
        """Check for BCL headers in the file."""
        headers = []
        for line in lines:
            m = BCL_HEADER_START_RE.match(line)
            if m:
                headers.append(m.group(1))

        return {
            'has_bcl': len(headers) > 0,
            'headers': headers,
        }


    def _config_template(self, domain, folder):
        """Generate a gold-standard Config.py from template."""
        folder_name = os.path.basename(folder)
        now = datetime.now().strftime('%Y-%m-%d')

        return f'''#!/usr/bin/env python3

#[@GHOST]{{[@file<Config.py>][@domain<{domain}>][@role<config>][@auth<devin>][@date<{now}>][@ver<1.0>]}}
#[@VBSTYLE]{{[@auth<system>][@role<config>][@return<dict>][@no<decorators|print|hardcoded_paths>]}}

"""
Gold Standard Config for {domain} domain.
Auto-generated by Prj_VBScanner.
All settings in SQLite config table — key/value/description.
Env vars override SQLite values at runtime.
"""

import os
import json
import sqlite3

# ─── BASE DIR ──────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.expanduser("~/.config/{domain}")
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_DB_PATH = os.path.join(CONFIG_DIR, "{domain}_config.db")

# ─── VERSIONS ──────────────────────────────────────────────────────────────

DOMAIN_VERSION = "1.0.0"
CONFIG_VERSION = "1.0.0"

# ─── CONFIG SEED SQL (embedded — no external .sql file) ────────────────────

CONFIG_SEED_SQL = """
CREATE TABLE IF NOT EXISTS config (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    description TEXT
);

INSERT OR IGNORE INTO config VALUES
('domain',                  '{domain}',                           'Domain name'),
('v20_db_path',             '',                                   'Path to v20_hybrid_best.db (empty = default)');
"""

# ─── ENV VAR OVERRIDE MAP ──────────────────────────────────────────────────

ENV_OVERRIDES = {{
    "{domain.upper()}_V20_DB_PATH":  "v20_db_path",
}}


# ─── FILE INDEX ────────────────────────────────────────────────────────────
# Full index of all files in this folder. Auto-generated by Prj_VBScanner.
# Each entry is a BCL token: [@File:name]{{("field";"value")...}}
# DO NOT EDIT MANUALLY — run: python3 Prj_VBScanner.py {folder} --append-only
# BCL fields: file, purpose, classes, methods, functions, vbstyle,
#             vbstyle_passed, vbstyle_total, vbstyle_failed, bcl, bcl_headers,
#             created, modified, size, lines

FILE_INDEX = [
    # Prj_VBScanner will append BCL entries here
]


# ─── CONFIG CLASS ──────────────────────────────────────────────────────────

class {self._pascal_case(domain)}Config:
    """Single source of truth for {domain} configuration.

    Loads all values from SQLite config table on init.
    Env vars override SQLite values.
    """

    DOMAIN_VERSION = DOMAIN_VERSION
    FILE_INDEX = FILE_INDEX

    def __init__(self):
        self._db_path = CONFIG_DB_PATH
        self._values = {{}}
        self._load()

    def _load(self):
        """Load config from SQLite, apply env overrides."""
        conn = sqlite3.connect(self._db_path)
        cur = conn.cursor()
        cur.executescript(CONFIG_SEED_SQL)
        conn.commit()
        cur.execute("SELECT key, value FROM config")
        for key, value in cur.fetchall():
            self._values[key] = value
        cur.close()
        conn.close()
        for env_name, config_key in ENV_OVERRIDES.items():
            env_val = os.environ.get(env_name)
            if env_val is not None:
                self._values[config_key] = env_val

    def _get(self, key, default=None):
        return self._values.get(key, default)

    def GetFileIndex(self):
        """Return full file index for this folder — list of BCL token strings."""
        return self.FILE_INDEX

    def GetFileList(self):
        """Return just the list of filenames from BCL entries."""
        import re
        names = []
        for entry in self.FILE_INDEX:
            m = re.search(r'\\("file";"([^"]+)"\\)', entry)
            if m:
                names.append(m.group(1))
        return names

    def GetFileEntry(self, filename):
        """Return the BCL entry for a specific file."""
        for entry in self.FILE_INDEX:
            if '("file";"' + filename + '")' in entry:
                return entry
        return None


# ─── SINGLETON ─────────────────────────────────────────────────────────────

cfg = {self._pascal_case(domain)}Config()
'''


    def _pascal_case(self, s):
        """Convert snake_case or lowercase to PascalCase."""
        return ''.join(word.capitalize() for word in s.split('_'))


    def _format_file_index(self, files):
        """Format the file index as BCL tokens.

        Each file entry is a BCL token:
        # [@File:name.py]{("purpose";"...")("classes";"...")("methods";"...")...}

        This is consistent with the system's BCL-first philosophy.
        The FILE_INDEX is a Python list of BCL token strings.
        """
        lines = []
        lines.append("FILE_INDEX = [")
        for entry in files:
            # Build BCL token for this file
            bcl = self._entry_to_bcl(entry)
            lines.append(f"    {json.dumps(bcl)},")
        lines.append("]")
        return '\n'.join(lines)


    def _entry_to_bcl(self, entry):
        """Convert a file entry dict to a BCL token string.

        Format:
        [@File:name.py]{{("purpose";"...")("classes";"A,B,C")("methods";"A.run,A.scan")...}}
        """
        fname = entry['file']
        # BCL-safe name (remove special chars for token name)
        safe_name = fname.replace('.', '_').replace('-', '_')
        # Join lists with commas for compact BCL
        classes_str = ','.join(entry['classes'])
        methods_str = ','.join(entry['methods'])
        functions_str = ','.join(entry['functions'])
        failed_str = ','.join(entry['vbstyle_failed'])
        bcl_headers_str = ','.join(entry['bcl_headers_found'])

        bcl = (f"# [@File:{safe_name}]{{"
               f"(\"file\";\"{fname}\")"
               f"(\"purpose\";\"{entry['purpose']}\")"
               f"(\"classes\";\"{classes_str}\")"
               f"(\"methods\";\"{methods_str}\")"
               f"(\"functions\";\"{functions_str}\")"
               f"(\"vbstyle\";\"{entry['vbstyle_compliant']}\")"
               f"(\"vbstyle_passed\";\"{entry['vbstyle_rules_passed']}\")"
               f"(\"vbstyle_total\";\"{entry['vbstyle_rules_total']}\")"
               f"(\"vbstyle_failed\";\"{failed_str}\")"
               f"(\"bcl\";\"{entry['has_bcl']}\")"
               f"(\"bcl_headers\";\"{bcl_headers_str}\")"
               f"(\"created\";\"{entry['created']}\")"
               f"(\"modified\";\"{entry['modified']}\")"
               f"(\"size\";\"{entry['size']}\")"
               f"(\"lines\";\"{entry['lines']}\")"
               f"}}")
        return bcl


    def _replace_file_index(self, existing, new_index_block):
        """Replace existing FILE_INDEX in Config.py with new one."""
        # Find FILE_INDEX = [ ... ] — match from FILE_INDEX to the next line that starts with ]
        # at the same indentation level (closing bracket of the list)
        lines = existing.split('\n')
        start_idx = None
        end_idx = None
        for i, line in enumerate(lines):
            if re.match(r'^FILE_INDEX\s*=\s*\[', line):
                start_idx = i
                continue
            if start_idx is not None and i > start_idx and re.match(r'^\]', line):
                end_idx = i
                break

        if start_idx is not None and end_idx is not None:
            # Replace lines start_idx through end_idx (inclusive)
            new_lines = lines[:start_idx] + new_index_block.split('\n') + lines[end_idx + 1:]
            return '\n'.join(new_lines)
        elif start_idx is not None:
            # Fallback: replace from start to end of file
            new_lines = lines[:start_idx] + new_index_block.split('\n')
            return '\n'.join(new_lines)
        else:
            # No existing FILE_INDEX — insert it
            return self._insert_file_index(existing, new_index_block)


    def _insert_file_index(self, existing, index_block):
        """Insert FILE_INDEX into Config.py (before CONFIG CLASS section)."""
        # Find the CONFIG CLASS section
        marker = "# ─── CONFIG CLASS"
        if marker in existing:
            parts = existing.split(marker, 1)
            return parts[0] + index_block + "\n\n" + marker + parts[1]
        else:
            # Append at end
            return existing + "\n\n" + index_block + "\n"


    def _cmd_scan_files(self, params):
        """Scan a folder for file index entries (BCL tokens, VBStyle, BCL headers)."""
        folder = self._p(params, "folder") or self._p(params, "path")
        if not folder or not os.path.isdir(folder):
            return (0, None, ("ERR_PATH", f"Invalid folder: {folder}", 0))
        folder = os.path.abspath(folder)
        self.state["folder"] = folder
        self.state["files"] = []
        py_files = sorted([f for f in os.listdir(folder) if f.endswith(".py") and not f.startswith(".")])
        for fname in py_files:
            fpath = os.path.join(folder, fname)
            entry = self._scan_file(fpath, fname)
            if entry:
                self.state["files"].append(entry)
        other_files = sorted([f for f in os.listdir(folder) if not f.endswith(".py") and not f.startswith(".") and os.path.isfile(os.path.join(folder, f))])
        for fname in other_files:
            fpath = os.path.join(folder, fname)
            entry = self._scan_non_py_file(fpath, fname)
            if entry:
                self.state["files"].append(entry)
        return (1, self.state["files"], None)

    def _cmd_file_index(self, params):
        """Append or replace FILE_INDEX in Config.py."""
        folder = self._p(params, "folder") or self._p(params, "path")
        if not folder:
            return (0, None, ("ERR_PATH", "folder required", 0))
        folder = os.path.abspath(folder)
        config_path = os.path.join(folder, "Config.py")
        if not self.state["files"] or self.state["folder"] != folder:
            result = self._cmd_scan_files({"folder": folder})
            if result[0] != 1:
                return result
        index_block = self._format_file_index(self.state["files"])
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                existing = f.read()
        except FileNotFoundError:
            result = self._cmd_generate({"path": folder})
            if result[0] != 1:
                return result
            with open(config_path, "r", encoding="utf-8") as f:
                existing = f.read()
        except Exception as e:
            return (0, None, ("ERR_READ", str(e), 0))
        if "FILE_INDEX" in existing:
            updated = self._replace_file_index(existing, index_block)
        else:
            updated = self._insert_file_index(existing, index_block)
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(updated)
            self.state["config_path"] = config_path
            self.state["appended_count"] += 1
            return (1, len(self.state["files"]), None)
        except Exception as e:
            return (0, None, ("ERR_WRITE", str(e), 0))

    def _cmd_full_run(self, params):
        """Full run: generate Config.py if needed, scan files, append FILE_INDEX."""
        folder = self._p(params, "folder") or self._p(params, "path")
        if not folder:
            return (0, None, ("ERR_PATH", "folder required", 0))
        result = self._cmd_generate({"path": folder})
        if result[0] != 1:
            return result
        result = self._cmd_scan_files({"folder": folder})
        if result[0] != 1:
            return result
        result = self._cmd_file_index({"folder": folder})
        if result[0] != 1:
            return result
        summary = {
            "folder": folder,
            "config_path": self.state["config_path"],
            "files_indexed": len(self.state["files"]),
            "config_created": self.state["created_count"] > 0,
            "index_appended": True,
        }
        return (1, summary, None)

    def _regex_extract_from_file(self, filepath):
        src = Path(filepath).read_text()
        fname = Path(filepath).name
        results = {
            'file': fname,
            'constants': {},
            'strings': set(),
            'numbers': set(),
            'defaults': {},
            'get_fallbacks': {},
            'classes': [],
            'methods': {},
        }

        # Module-level constants: UPPER_CASE = value
        for m in re.finditer(r'^([A-Z][A-Z_0-9]+)\s*=\s*(.+?)$', src, re.MULTILINE):
            name = m.group(1)
            raw = m.group(2).strip()
            val = parse_literal(raw)
            if val is not None:
                results['constants'][name] = val

        # Class names
        for m in re.finditer(r'^class\s+(\w+)', src, re.MULTILINE):
            results['classes'].append(m.group(1))

        # Method names per class
        current_class = None
        for line in src.split('\n'):
            cm = re.match(r'^class\s+(\w+)', line)
            if cm:
                current_class = cm.group(1)
                results['methods'][current_class] = []
                continue
            if current_class:
                mm = re.match(r'^\s+def\s+(\w+)', line)
                if mm:
                    results['methods'][current_class].append(mm.group(1))

        # Default parameters: def foo(self, x="value", y=42)
        for m in re.finditer(r'def\s+\w+\s*\(([^)]*)\)', src, re.DOTALL):
            params = m.group(1)
            for pm in re.finditer(r'(\w+)\s*=\s*([^,)]+)', params):
                pname = pm.group(1)
                praw = pm.group(2).strip()
                if pname in ('self', 'mem', 'db', 'param'):
                    continue
                val = parse_literal(praw)
                if val is not None:
                    results['defaults'][pname] = val

        # .get("key", "fallback") calls
        for m in re.finditer(r'\.get\(\s*["\']([^"\']+)["\']\s*,\s*([^)]+)\)', src):
            key = m.group(1)
            fallback_raw = m.group(2).strip()
            val = parse_literal(fallback_raw)
            if val is not None:
                results['get_fallbacks'][key] = val

        # All string literals
        for m in re.finditer(r'["\']([^"\']{1,200})["\']', src):
            s = m.group(1)
            if is_config_string(s):
                results['strings'].add(s)

        # All number literals
        for m in re.finditer(r'(?<![\w.])(\d+\.?\d*)(?![\w.])', src):
            raw = m.group(1)
            try:
                if '.' in raw:
                    n = float(raw)
                else:
                    n = int(raw)
                if is_config_number(n):
                    results['numbers'].add(n)
            except ValueError:
                pass

        return results


    def _parse_literal(self, raw):
        raw = raw.strip().rstrip(',')
        if raw.startswith('"') and raw.endswith('"'):
            return raw[1:-1]
        if raw.startswith("'") and raw.endswith("'"):
            return raw[1:-1]
        if raw in ('None', 'True', 'False'):
            return raw == 'True' if raw != 'None' else None
        try:
            if '.' in raw:
                return float(raw)
            return int(raw)
        except ValueError:
            return None


    def _is_config_string(self, s):
        if not s or len(s) > 200:
            return False
        if s.endswith('.db') or s.endswith('.sql'):
            return True
        if re.match(r'^#[0-9A-Fa-f]{3,8}$', s):
            return True
        if re.match(r'^[a-z][a-z_]+$', s) and '_' in s and len(s) > 3:
            return True
        if s in ('color', 'font', 'format', 'spacing', 'background', 'text',
                 'border', 'padding', 'margin', 'size', 'weight', 'border_width'):
            return True
        if s in ('bold', 'normal', 'light'):
            return True
        if '/' in s and not s.startswith('http') and len(s) < 100:
            return True
        if s.isdigit() and len(s) <= 5:
            return True
        if s in ('true', 'false'):
            return True
        if s in ('data_shape', 'user_intent', 'interaction_type', 'device_type'):
            return True
        return False


    def _is_config_number(self, n):
        if isinstance(n, bool):
            return False
        if 1000 <= n <= 9999:
            return True
        if n in (0, 1, 2, 4, 8, 12, 14, 16, 18, 20, 22, 24, 28, 32, 48, 64, 100, 200):
            return True
        if isinstance(n, float) and 0.0 <= n <= 1.0:
            return True
        return False


    def _safe_name(self, s):
        if re.match(r'^#[0-9A-Fa-f]+$', s):
            return f'COLOR_{s.lstrip("#").upper()}'
        if s.endswith('.db'):
            return f'DB_PATH_{s.replace(".db", "").upper()}'
        if s.endswith('.sql'):
            return f'SQL_FILE_{s.replace(".sql", "").upper()}'
        if '/' in s:
            parts = s.strip('/').split('/')
            return 'PATH_' + '_'.join(p.upper() for p in parts if p)
        if s in ('color', 'font', 'format', 'spacing'):
            return f'STORE_{s.upper()}'
        if s in ('background', 'text', 'border', 'padding', 'margin', 'size', 'weight', 'border_width'):
            return f'PROP_{s.upper()}'
        if s in ('bold', 'normal', 'light'):
            return f'FONT_WEIGHT_{s.upper()}'
        if s in ('true', 'false'):
            return f'BOOL_{s.upper()}'
        if s in ('data_shape', 'user_intent', 'interaction_type', 'device_type'):
            return f'CONTEXT_{s.upper()}'
        if s.isdigit():
            return f'PORT_{s}'
        if re.match(r'^[a-z_]+$', s):
            return f'TABLE_{s.upper()}'
        return 'STR_' + re.sub(r'[^A-Z0-9]', '_', s.upper())


    def _safe_name_num(self, n):
        if isinstance(n, float):
            return f'NUM_{str(n).replace(".", "_")}'
        if 1000 <= n <= 9999:
            return f'PORT_{n}'
        if n <= 100:
            return f'SIZE_{n}'
        return f'NUM_{n}'


    def _cmd_regex_extract(self, params):
        """Regex-extract config data from a .py file (works even with syntax errors)."""
        filepath = self._p(params, "file")
        if not filepath or not os.path.isfile(filepath):
            return (0, None, ("ERR_FILE", f"File not found: {filepath}", 0))
        data = self._regex_extract_from_file(filepath)
        self.state["stats"]["extracted"] += 1
        return (1, data, None)


def main():
    """CLI entry point for ConfigCascade."""
    if len(sys.argv) < 2:
        print("Usage: python3 ConfigCascade.py <command> [options]")
        print("Commands: scan, extract, regex_extract, generate, read, write, update, verify, catalog, scan_files, file_index, full_run")
        sys.exit(1)
    command = sys.argv[1]
    params = {}
    for arg in sys.argv[2:]:
        if "=" in arg:
            key, val = arg.split("=", 1)
            params[key] = val
        else:
            params["path"] = arg
    cc = ConfigCascade()
    ok, data, err = cc.Run(command, params)
    if ok:
        print(json.dumps(data, indent=2, default=str))
    else:
        print(f"Error [{err[0]}]: {err[1]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
