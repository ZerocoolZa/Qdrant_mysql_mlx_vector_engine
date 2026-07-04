#!/usr/bin/env python3

#[@GHOST]{[@file<Classifier_smart_system.py>][@state<active>][@date<2026-06-22>][@ver<1.0>][@auth<Cascade>]}
#[@VBSTYLE]{[@auth<system>][@role<classifier>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths|abc|inheritance>]}

"""
Smart Classifier Domain.
Classifies code: language detection, VBStyle compliance, class tree extraction, BCL header parsing.
No search — search is handled by Smart_search_gui.py.
"""

import re
import os
import sys
import ast
import sqlite3
import importlib.util

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Config_smart_system import *

GHOST_RE = re.compile(VBSTYLE_PATTERN_GHOST, re.IGNORECASE)
VBSTYLE_RE = re.compile(VBSTYLE_PATTERN_VBSTYLE, re.IGNORECASE)
TUPLE3_RE = re.compile(VBSTYLE_PATTERN_TUPLE3, re.IGNORECASE)
STATE_DICT_RE = re.compile(VBSTYLE_PATTERN_STATE_DICT)
RUN_DISPATCH_RE = re.compile(VBSTYLE_PATTERN_RUN_DISPATCH)
DECORATOR_RE = re.compile(VBSTYLE_PATTERN_DECORATOR)
PRINT_RE = re.compile(VBSTYLE_PATTERN_PRINT)
SELF_UNDERSCORE_RE = re.compile(VBSTYLE_PATTERN_SELF_UNDERSCORE)
HARDCODED_PATH_RE = re.compile(VBSTYLE_PATTERN_HARDCODED_PATH)

HEADER_RE = re.compile(r'^\s*#\[@(\w+)\]\{(.+)\}')
CLASS_RE = re.compile(r'^(\s*)class\s+(\w+)')
DEF_RE = re.compile(r'^(\s+)def\s+(\w+)\((.*)\)')
BCL_START_RE = re.compile(r'^\s*#\[@(\w+)\]')
PURPOSE_RE = re.compile(r'@purpose<([^>]+)>')
PARAMS_RE = re.compile(r'@params<<([^>]*)>')
RETURN_RE = re.compile(r'@return<([^>]+)>')
BOILERPLATE_METHODS = {"__init__", "Run", "read_state", "set_config"}


class SmartClassifier:
    """Smart classifier — language detection, VBStyle compliance, class tree extraction, BCL headers."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "mysql_host": DB_HOST_LOCALHOST,
                "mysql_user": DB_USER_ROOT,
                "mysql_database": DB_NAME_VB_SHARED,
                "mysql_charset": DB_CHARSET_UTF8MB4,
                "efl_db": str(BASE_DIR.parent / DB_PATH_EFL_BRAIN),
            },
            "results": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param and isinstance(param, dict):
            self.state["config"].update(param)

    def Run(self, command, params=None):
        if command == "detect_language":
            return self.DetectLanguage(params)
        elif command == "vbstyle_check":
            return self.VbstyleCheck(params)
        elif command == "scan_code":
            return self.ScanCode(params)
        elif command == "scan_class":
            return self.ScanClass(params)
        elif command == "count_methods":
            return self.CountMethodsCmd(params)
        elif command == "efl_classify":
            return self.EflClassify(params)
        elif command == "efl_class_detail":
            return self.EflClassDetail(params)
        elif command == "efl_zero_methods":
            return self.EflZeroMethods(params)
        elif command == "efl_vbstyle_summary":
            return self.EflVbstyleSummary(params)
        elif command == "efl_method_violations":
            return self.EflMethodViolations(params)
        elif command == "read_state":
            return self.ReadState()
        elif command == "set_config":
            return self.SetConfig(params)
        else:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def MysqlConn(self):
        import mysql.connector
        return mysql.connector.connect(
            host=self.state["config"]["mysql_host"],
            user=self.state["config"]["mysql_user"],
            database=self.state["config"]["mysql_database"],
            charset=self.state["config"]["mysql_charset"],
        )

    def DetectLanguage(self, params):
        if not params or "code" not in params:
            return (0, None, (ERR_MISSING_PARAM, "code required", 0))
        code = params["code"]
        lang = self.DetectLangInternal(code)
        return (1, {"language": lang}, None)

    def DetectLangInternal(self, code):
        if not code:
            return LANG_NAME_UNKNOWN
        head = code[:DEFAULT_LANGUAGE_HEAD_SCAN]
        if LANG_MARKER_C_STDIO in head or LANG_MARKER_C_STDLIB in head or LANG_MARKER_C_MATH in head:
            return LANG_NAME_C
        if LANG_MARKER_C_FOUNDATION in head or LANG_MARKER_SWIFT_IMPORT in head:
            return LANG_NAME_SWIFT
        if LANG_MARKER_SWIFT_MTL_DEVICE in head or LANG_MARKER_SWIFT_MTL_BUFFER in head or LANG_MARKER_SWIFT_MTL_COMMAND in head:
            return LANG_NAME_SWIFT
        if head.startswith("//") and ("import" in head or "MTL" in head):
            return LANG_NAME_SWIFT
        if LANG_MARKER_SWIFT_FUNC in head and LANG_MARKER_SWIFT_ARROW in head:
            return LANG_NAME_SWIFT
        if LANG_MARKER_SWIFT_LET in head and LANG_MARKER_SWIFT_VAR in head:
            return LANG_NAME_SWIFT
        if head.startswith("/*") and "#include" in head:
            return LANG_NAME_C
        if "struct " in head and "typedef" in head:
            return LANG_NAME_C
        if LANG_MARKER_PYTHON_GHOST in head or LANG_MARKER_PYTHON_VBSTYLE in head:
            return LANG_NAME_PYTHON
        if LANG_MARKER_PYTHON_DEF in head or LANG_MARKER_PYTHON_CLASS in head:
            return LANG_NAME_PYTHON
        if head.startswith("#!/") and "python" in head:
            return LANG_NAME_PYTHON
        if head.startswith(LANG_MARKER_PYTHON_FUTURE) or head.startswith(LANG_MARKER_PYTHON_IMPORT):
            return LANG_NAME_PYTHON
        if head.startswith(LANG_MARKER_MARKDOWN_HASH) and LANG_MARKER_PYTHON_DEF not in head:
            return LANG_NAME_MARKDOWN
        if head.startswith(LANG_MARKER_MARKDOWN_YES) or LANG_MARKER_MARKDOWN_THIS_FILE in head[:50]:
            return LANG_NAME_MARKDOWN
        return LANG_NAME_UNKNOWN

    def VbstyleCheck(self, params):
        if not params or "code" not in params:
            return (0, None, (ERR_MISSING_PARAM, "code required", 0))
        code = params["code"]
        lang = self.DetectLangInternal(code)
        if lang != LANG_NAME_PYTHON:
            return (1, {"language": lang, "applicable": False, "reason": f"VBStyle checks apply to Python only, got {lang}"}, None)

        checks = {
            "ghost_header": bool(GHOST_RE.search(code)),
            "vbstyle_header": bool(VBSTYLE_RE.search(code)),
            "tuple3_return": bool(TUPLE3_RE.search(code)),
            "state_dict": bool(STATE_DICT_RE.search(code)),
            "run_dispatch": bool(RUN_DISPATCH_RE.search(code)),
            "no_decorators": not bool(DECORATOR_RE.search(code)),
            "no_print": not bool(PRINT_RE.search(code)),
            "no_self_underscore": not bool(SELF_UNDERSCORE_RE.search(code)),
            "no_hardcoded_paths": not bool(HARDCODED_PATH_RE.search(code)),
        }
        passed = sum(1 for v in checks.values() if v)
        failed = [k for k, v in checks.items() if not v]
        compliant = passed == 9
        return (1, {
            "language": lang,
            "applicable": True,
            "checks": checks,
            "passed": passed,
            "total": 9,
            "compliant": compliant,
            "failed_rules": failed,
        }, None)

    def CountMethodsCmd(self, params):
        if not params or "code" not in params:
            return (0, None, (ERR_MISSING_PARAM, "code required", 0))
        code = params["code"]
        lang = self.DetectLangInternal(code)
        mc = self.CountMethods(code, lang)
        return (1, {"language": lang, "method_count": mc}, None)

    def CountMethods(self, code, lang):
        if lang != LANG_NAME_PYTHON or not code:
            return 0
        try:
            tree = ast.parse(code)
            return sum(1 for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
        except SyntaxError:
            return 0

    def ScanCode(self, params):
        """Scan raw code string — extract full class tree, methods, BCL headers, VBStyle compliance."""
        if not params or "code" not in params:
            return (0, None, (ERR_MISSING_PARAM, "code required", 0))
        code = params["code"]
        class_name = params.get("class_name", "(unknown)")
        result = self.ExtractClassTree(code, class_name)
        return (1, result, None)

    def ScanClass(self, params):
        """Scan a single class by ID from MySQL — extract full class tree, methods, BCL headers, VBStyle compliance."""
        if not params or "id" not in params:
            return (0, None, (ERR_MISSING_PARAM, "id required", 0))
        cid = params["id"]
        try:
            conn = self.MysqlConn()
            cur = conn.cursor()
            cur.execute(f"SELECT class_name, class_code FROM {TABLE_CODE_CLASSES} WHERE id = %s", (cid,))
            row = cur.fetchone()
            conn.close()
            if not row:
                return (0, None, ("NOT_FOUND", f"No class with id={cid}", 0))
            class_name, code = row
            if not code:
                return (1, {"id": cid, "class_name": class_name, "language": LANG_NAME_UNKNOWN, "tree": [], "method_count": 0, "class_count": 0, "compliance": None, "bcl_coverage": {}, "bcl_headers": {}}, None)
            result = self.ExtractClassTree(code, class_name, cid)
            return (1, result, None)
        except Exception as ex:
            return (0, None, (ERR_MYSQL_ERROR, str(ex), 0))

    def ExtractClassTree(self, code, class_name, cid=None):
        """Extract full class hierarchy with methods, params, purposes, BCL headers, VBStyle compliance.
        Mirrors vbstyle_dom_scanner.py parse_domain_file logic."""
        lang = self.DetectLangInternal(code)
        lines = code.split("\n")
        total_lines = len(lines)

        class_stack = []
        tree_entries = []
        class_ranges = {}
        bcl_headers = {}
        root_class = None
        sub_authorities = []
        pending_bcl_raw = None
        pending_header = None

        total_methods_found = 0
        methods_with_bcl = 0
        total_classes_found = 0
        classes_with_bcl = 0

        for i, line in enumerate(lines):
            stripped = line.rstrip()
            if not stripped:
                continue

            bcl_start = BCL_START_RE.match(stripped)
            header_match = HEADER_RE.match(stripped)
            if bcl_start:
                raw_bcl = self.ExtractBclHeader(stripped, lines, i)
                if raw_bcl:
                    pending_bcl_raw = raw_bcl
                if header_match:
                    pending_header = (header_match.group(1), header_match.group(2))
                continue

            class_match = CLASS_RE.match(stripped)
            if class_match:
                indent = len(class_match.group(1))
                name = class_match.group(2)
                total_classes_found += 1

                while class_stack and class_stack[-1][0] >= indent:
                    popped = class_stack.pop()
                    popped_path = ".".join([c[1] for c in class_stack] + [popped[1]])
                    if popped_path in class_ranges and class_ranges[popped_path][1] == 0:
                        class_ranges[popped_path] = (class_ranges[popped_path][0], i)

                path_parts = [c[1] for c in class_stack] + [name]
                access_path = ".".join(path_parts)
                level = len(class_stack)
                class_stack.append((indent, name, i))

                if level == 0 and root_class is None:
                    root_class = name
                elif level == 1:
                    sub_authorities.append(name)

                if pending_bcl_raw:
                    bcl_headers[("class", access_path)] = {"raw": pending_bcl_raw, "parsed_ok": True}
                    classes_with_bcl += 1
                    pending_bcl_raw = None

                class_ranges[access_path] = (i, 0)
                tree_entries.append({"type": "class", "level": level, "name": name, "access_path": access_path})
                pending_header = None
                continue

            def_match = DEF_RE.match(stripped)
            if def_match and class_stack:
                indent = len(def_match.group(1))
                name = def_match.group(2)
                params_raw = def_match.group(3).strip()
                total_methods_found += 1

                if name.startswith("__") and name.endswith("__") and name != "__init__":
                    pending_header = None
                    pending_bcl_raw = None
                    continue

                params_clean = params_raw.replace("self, ", "").replace("self", "").strip()
                if params_clean.endswith(","):
                    params_clean = params_clean[:-1].strip()

                purpose = ""
                return_type = ""
                if pending_header:
                    hdr_body = pending_header[1]
                    pm = PURPOSE_RE.search(hdr_body)
                    if pm:
                        purpose = pm.group(1)
                    rm = RETURN_RE.search(hdr_body)
                    if rm:
                        return_type = rm.group(1)
                    if not params_clean:
                        pm2 = PARAMS_RE.search(hdr_body)
                        if pm2:
                            params_clean = pm2.group(1)

                if pending_bcl_raw:
                    bcl_headers[("method", name)] = {"raw": pending_bcl_raw, "parsed_ok": True}
                    methods_with_bcl += 1
                    pending_bcl_raw = None

                is_boilerplate = name in BOILERPLATE_METHODS

                if indent > class_stack[-1][0]:
                    level = len(class_stack)
                else:
                    level = len(class_stack) - 1

                tree_entries.append({
                    "type": "method",
                    "level": level,
                    "name": name,
                    "params": params_clean,
                    "purpose": purpose,
                    "return": return_type,
                    "is_boilerplate": is_boilerplate,
                    "has_bcl": ("method", name) in bcl_headers,
                })
                pending_header = None

        for path, (start, end) in class_ranges.items():
            if end == 0:
                class_ranges[path] = (start, total_lines)

        compliance = self.CheckCompliancePerClass(code, lines, class_ranges)

        bcl_coverage = {
            "total_classes": total_classes_found,
            "classes_with_bcl": classes_with_bcl,
            "total_methods": total_methods_found,
            "methods_with_bcl": methods_with_bcl,
        }

        return {
            "id": cid,
            "class_name": class_name,
            "language": lang,
            "root_class": root_class or "(none)",
            "sub_authorities": sub_authorities,
            "total_lines": total_lines,
            "tree": tree_entries,
            "method_count": total_methods_found,
            "class_count": total_classes_found,
            "compliance": compliance,
            "bcl_coverage": bcl_coverage,
            "bcl_headers": {f"{k[0]}:{k[1]}": v for k, v in bcl_headers.items()},
        }

    def ExtractBclHeader(self, line, lines_list, line_idx):
        """Extract a full BCL header from a comment line, handling multi-line."""
        m = BCL_START_RE.match(line)
        if not m:
            return None
        raw_parts = []
        brace_depth = 0
        started = False
        for j in range(line_idx, min(line_idx + 20, len(lines_list))):
            raw_line = lines_list[j].rstrip()
            if not raw_line:
                break
            stripped = raw_line.lstrip()
            if stripped.startswith("#"):
                content = stripped[1:].lstrip()
                if content.startswith("\\"):
                    content = content[1:].lstrip()
            else:
                if started:
                    break
                else:
                    content = stripped
            raw_parts.append(content)
            brace_depth += content.count("{") - content.count("}")
            started = True
            if brace_depth <= 0 and "}" in content:
                break
        return "\n".join(raw_parts) if raw_parts else None

    def CheckCompliancePerClass(self, full_code, lines_list, class_ranges):
        """Check VBStyle compliance per class range, like vbstyle_dom_scanner.py."""
        file_comp = {
            "ghost_header": bool(GHOST_RE.search(full_code)),
            "vbstyle_header": bool(VBSTYLE_RE.search(full_code)),
            "tuple3_return": bool(TUPLE3_RE.search(full_code)),
            "state_dict": bool(STATE_DICT_RE.search(full_code)),
            "run_dispatch": bool(RUN_DISPATCH_RE.search(full_code)),
            "no_decorators": not any(DECORATOR_RE.match(l) for l in lines_list),
            "no_print": not any(PRINT_RE.search(l) for l in lines_list if not l.strip().startswith("#")),
            "no_self_underscore": not any(SELF_UNDERSCORE_RE.search(l) for l in lines_list if not l.strip().startswith("#")),
            "no_hardcoded_paths": not any(HARDCODED_PATH_RE.search(l) for l in lines_list if not l.strip().startswith("#")),
        }
        class_comp = {}
        for access_path, (start, end) in class_ranges.items():
            class_lines = lines_list[start:end]
            class_text = "\n".join(class_lines)
            class_comp[access_path] = {
                "ghost_header": bool(GHOST_RE.search(class_text)),
                "vbstyle_header": bool(VBSTYLE_RE.search(class_text)),
                "tuple3_return": bool(TUPLE3_RE.search(class_text)),
                "state_dict": bool(STATE_DICT_RE.search(class_text)),
                "run_dispatch": bool(RUN_DISPATCH_RE.search(class_text)),
                "no_decorators": not any(DECORATOR_RE.match(l) for l in class_lines),
                "no_print": not any(PRINT_RE.search(l) for l in class_lines if not l.strip().startswith("#")),
                "no_self_underscore": not any(SELF_UNDERSCORE_RE.search(l) for l in class_lines if not l.strip().startswith("#")),
                "no_hardcoded_paths": not any(HARDCODED_PATH_RE.search(l) for l in class_lines if not l.strip().startswith("#")),
            }
        return {"file": file_comp, "classes": class_comp}

    def EflConn(self):
        return sqlite3.connect(self.state["config"]["efl_db"])

    def EflClassify(self, params=None):
        """Classify all EFL classes — VBStyle compliance, method counts, domain grouping."""
        db_path = self.state["config"]["efl_db"]
        if not os.path.exists(db_path):
            return (0, None, ("EFL_DB_MISSING", f"Not found: {db_path}", 0))
        try:
            conn = self.EflConn()
            cur = conn.cursor()
            cur.execute("""
                SELECT c.id, c.class_name, c.domain, c.source, c.method_count,
                       COUNT(m.id) as actual_methods,
                       SUM(m.is_run) as run_count,
                       SUM(m.returns_tuple3) as tuple3_count,
                       SUM(m.has_try) as try_count,
                       SUM(m.has_re) as re_count,
                       SUM(m.is_init) as init_count,
                       SUM(m.is_dunder) as dunder_count
                FROM classes c
                LEFT JOIN methods m ON m.class_id = c.id
                GROUP BY c.id
                ORDER BY actual_methods DESC
            """)
            classes = []
            for row in cur.fetchall():
                cid, name, domain, source, stored_mc, actual_mc, run_c, t3_c, try_c, re_c, init_c, dun_c = row
                actual_mc = actual_mc or 0
                run_c = run_c or 0
                t3_c = t3_c or 0
                try_c = try_c or 0
                re_c = re_c or 0
                init_c = init_c or 0
                dun_c = dun_c or 0
                non_dunder = actual_mc - dun_c
                has_run = run_c > 0
                has_tuple3 = t3_c > 0
                has_try = try_c > 0
                if actual_mc == 0:
                    compliance = "empty"
                elif has_run and has_tuple3 and has_try:
                    compliance = "vbstyle_full"
                elif has_run and has_tuple3:
                    compliance = "vbstyle_partial"
                elif has_run:
                    compliance = "has_run_only"
                else:
                    compliance = "non_vbstyle"
                tuple3_ratio = t3_c / non_dunder if non_dunder > 0 else 0
                try_ratio = try_c / non_dunder if non_dunder > 0 else 0
                classes.append({
                    "id": cid,
                    "class_name": name,
                    "domain": domain,
                    "source": source,
                    "stored_method_count": stored_mc,
                    "actual_method_count": actual_mc,
                    "run_count": run_c,
                    "tuple3_count": t3_c,
                    "try_count": try_c,
                    "re_count": re_c,
                    "init_count": init_c,
                    "dunder_count": dun_c,
                    "non_dunder_count": non_dunder,
                    "tuple3_ratio": round(tuple3_ratio, 2),
                    "try_ratio": round(try_ratio, 2),
                    "compliance": compliance,
                    "has_run": has_run,
                    "has_tuple3": has_tuple3,
                    "has_try": has_try,
                })
            conn.close()
            domains = {}
            for c in classes:
                d = c["domain"] or "(none)"
                if d not in domains:
                    domains[d] = {"count": 0, "methods": 0, "vbstyle_full": 0, "empty": 0}
                domains[d]["count"] += 1
                domains[d]["methods"] += c["actual_method_count"]
                if c["compliance"] == "vbstyle_full":
                    domains[d]["vbstyle_full"] += 1
                if c["compliance"] == "empty":
                    domains[d]["empty"] += 1
            summary = {
                "total_classes": len(classes),
                "total_methods": sum(c["actual_method_count"] for c in classes),
                "vbstyle_full": sum(1 for c in classes if c["compliance"] == "vbstyle_full"),
                "vbstyle_partial": sum(1 for c in classes if c["compliance"] == "vbstyle_partial"),
                "has_run_only": sum(1 for c in classes if c["compliance"] == "has_run_only"),
                "non_vbstyle": sum(1 for c in classes if c["compliance"] == "non_vbstyle"),
                "empty": sum(1 for c in classes if c["compliance"] == "empty"),
                "total_run": sum(c["run_count"] for c in classes),
                "total_tuple3": sum(c["tuple3_count"] for c in classes),
                "total_try": sum(c["try_count"] for c in classes),
            }
            return (1, {"summary": summary, "domains": domains, "classes": classes}, None)
        except Exception as ex:
            return (0, None, ("EFL_DB_ERROR", str(ex), 0))

    def EflClassDetail(self, params):
        """Get detailed method list for a single EFL class by name or ID."""
        if not params or ("id" not in params and "name" not in params):
            return (0, None, (ERR_MISSING_PARAM, "id or name required", 0))
        db_path = self.state["config"]["efl_db"]
        if not os.path.exists(db_path):
            return (0, None, ("EFL_DB_MISSING", f"Not found: {db_path}", 0))
        try:
            conn = self.EflConn()
            cur = conn.cursor()
            if "id" in params:
                cur.execute("SELECT id, class_name, domain, source, class_code, description, method_count FROM classes WHERE id = ?", (params["id"],))
            else:
                cur.execute("SELECT id, class_name, domain, source, class_code, description, method_count FROM classes WHERE class_name = ?", (params["name"],))
            row = cur.fetchone()
            if not row:
                return (0, None, ("NOT_FOUND", "Class not found", 0))
            cid, name, domain, source, class_code, desc, mc = row
            cur.execute("""
                SELECT id, method_name, params, is_dunder, is_run, is_init, returns_tuple3,
                       has_ast, has_re, has_try, code_len, line_start, method_code
                FROM methods WHERE class_id = ? ORDER BY line_start
            """, (cid,))
            methods = []
            for mrow in cur.fetchall():
                mid, mname, mparams, mdunder, mrun, minit, mtuple3, mast, mre, mtry, mlen, mstart, mcode = mrow
                violations = []
                if SELF_UNDERSCORE_RE.search(mcode or ""):
                    violations.append("self_underscore")
                if PRINT_RE.search(mcode or ""):
                    violations.append("print")
                if DECORATOR_RE.match(mcode or ""):
                    violations.append("decorator")
                if HARDCODED_PATH_RE.search(mcode or ""):
                    violations.append("hardcoded_path")
                methods.append({
                    "id": mid,
                    "name": mname,
                    "params": mparams,
                    "is_dunder": bool(mdunder),
                    "is_run": bool(mrun),
                    "is_init": bool(minit),
                    "returns_tuple3": bool(mtuple3),
                    "has_ast": bool(mast),
                    "has_re": bool(mre),
                    "has_try": bool(mtry),
                    "code_len": mlen,
                    "line_start": mstart,
                    "violations": violations,
                })
            conn.close()
            lang = self.DetectLangInternal(class_code or "")
            return (1, {
                "id": cid,
                "class_name": name,
                "domain": domain,
                "source": source,
                "language": lang,
                "description": desc,
                "method_count": len(methods),
                "methods": methods,
            }, None)
        except Exception as ex:
            return (0, None, ("EFL_DB_ERROR", str(ex), 0))

    def EflZeroMethods(self, params=None):
        """List all EFL classes with zero methods — these need scaffolding or import."""
        db_path = self.state["config"]["efl_db"]
        if not os.path.exists(db_path):
            return (0, None, ("EFL_DB_MISSING", f"Not found: {db_path}", 0))
        try:
            conn = self.EflConn()
            cur = conn.cursor()
            cur.execute("""
                SELECT c.id, c.class_name, c.domain, c.source, c.class_code
                FROM classes c
                LEFT JOIN methods m ON m.class_id = c.id
                GROUP BY c.id
                HAVING COUNT(m.id) = 0
                ORDER BY c.domain, c.class_name
            """)
            classes = []
            for row in cur.fetchall():
                cid, name, domain, source, class_code = row
                lang = self.DetectLangInternal(class_code or "")
                classes.append({
                    "id": cid,
                    "class_name": name,
                    "domain": domain,
                    "source": source,
                    "language": lang,
                })
            conn.close()
            by_lang = {}
            for c in classes:
                l = c["language"]
                if l not in by_lang:
                    by_lang[l] = []
                by_lang[l].append(c["class_name"])
            return (1, {"count": len(classes), "by_language": by_lang, "classes": classes}, None)
        except Exception as ex:
            return (0, None, ("EFL_DB_ERROR", str(ex), 0))

    def EflVbstyleSummary(self, params=None):
        """VBStyle compliance summary across all EFL methods."""
        db_path = self.state["config"]["efl_db"]
        if not os.path.exists(db_path):
            return (0, None, ("EFL_DB_MISSING", f"Not found: {db_path}", 0))
        try:
            conn = self.EflConn()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM methods")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE returns_tuple3 = 1")
            t3 = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE is_run = 1")
            run = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE has_try = 1")
            try_c = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE has_re = 1")
            re_c = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE is_dunder = 1")
            dun = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE is_init = 1")
            init = cur.fetchone()[0]
            cur.execute("""
                SELECT class_name, COUNT(*) as mc
                FROM methods
                WHERE method_code LIKE '%self._%'
                GROUP BY class_name
                ORDER BY mc DESC
            """)
            underscore_classes = [(r[0], r[1]) for r in cur.fetchall()]
            cur.execute("""
                SELECT class_name, method_name
                FROM methods
                WHERE method_code LIKE '%' || 'print' || '(' || '%'
                AND method_code NOT LIKE '%# ' || 'print' || '%'
                LIMIT 20
            """)
            print_methods = [(r[0], r[1]) for r in cur.fetchall()]
            conn.close()
            non_dunder = total - dun
            return (1, {
                "total_methods": total,
                "non_dunder_methods": non_dunder,
                "returns_tuple3": t3,
                "tuple3_ratio": round(t3 / non_dunder, 2) if non_dunder else 0,
                "has_run": run,
                "has_try": try_c,
                "try_ratio": round(try_c / non_dunder, 2) if non_dunder else 0,
                "has_re": re_c,
                "is_dunder": dun,
                "is_init": init,
                "self_underscore_classes": underscore_classes,
                "print_methods": print_methods,
            }, None)
        except Exception as ex:
            return (0, None, ("EFL_DB_ERROR", str(ex), 0))

    def EflMethodViolations(self, params=None):
        """Find methods that violate VBStyle rules — self._, print, decorators, hardcoded paths."""
        db_path = self.state["config"]["efl_db"]
        if not os.path.exists(db_path):
            return (0, None, ("EFL_DB_MISSING", f"Not found: {db_path}", 0))
        try:
            conn = self.EflConn()
            cur = conn.cursor()
            cur.execute("""
                SELECT id, class_name, method_name, method_code
                FROM methods
                WHERE method_code LIKE '%self._%'
                   OR (method_code LIKE '%' || 'print' || '(' || '%' AND method_code NOT LIKE '%# ' || 'print' || '%')
                   OR method_code LIKE '%@staticmethod%'
                   OR method_code LIKE '%@classmethod%'
                   OR method_code LIKE '%@property%'
                ORDER BY class_name, method_name
            """)
            violations = []
            for row in cur.fetchall():
                mid, cname, mname, mcode = row
                v = []
                if SELF_UNDERSCORE_RE.search(mcode or ""):
                    v.append("self_underscore")
                if PRINT_RE.search(mcode or "") and not mcode.strip().startswith("#"):
                    v.append("print")
                if re.search(r'@staticmethod|@classmethod|@property', mcode or ""):
                    v.append("decorator")
                if HARDCODED_PATH_RE.search(mcode or ""):
                    v.append("hardcoded_path")
                if v:
                    violations.append({
                        "method_id": mid,
                        "class_name": cname,
                        "method_name": mname,
                        "violations": v,
                    })
            conn.close()
            return (1, {"count": len(violations), "violations": violations}, None)
        except Exception as ex:
            return (0, None, ("EFL_DB_ERROR", str(ex), 0))

    def ReadState(self):
        return (1, {"config": self.state["config"]}, None)

    def SetConfig(self, params):
        if not params:
            return (0, None, (ERR_MISSING_PARAM, "key and value required", 0))
        key = params.get("key", "")
        value = params.get("value", "")
        if not key:
            return (0, None, ("MISSING_KEY", "key required", 0))
        self.state["config"][key] = value
        return (1, {"key": key, "value": value}, None)
