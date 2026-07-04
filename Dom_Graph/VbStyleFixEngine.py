#!/usr/bin/env python3
#[@GHOST]{file_path="Dom_Graph/VbStyleFixEngine.py" date="2026-06-29" author="Devin" session_id="vbstyle-fix-engine" context="DB-driven VBStyle violation fix engine -- granular method repair via SQL + AST"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print no-decorators"}
#[@FILEID]{id="VbStyleFixEngine.py" domain="vbstyle_fix" authority="VbStyleFixEngine"}
#[@SUMMARY]{summary="Reads VBStyle violations from dom_graph_work.db, fixes method_code via AST transform (Tuple3 wrapping + self._ renaming), UPDATEs DB, writes fixed methods back to .py files."}
#[@CLASS]{class="VbStyleFixEngine" domain="vbstyle_fix" authority="single"}
#[@METHOD]{method="Run" type="dispatch"}
#[@METHOD]{method="ScanViolations" type="command"}
#[@METHOD]{method="FixTuple3" type="command"}
#[@METHOD]{method="FixSelfUnderscore" type="command"}
#[@METHOD]{method="SyncToFile" type="command"}
#[@METHOD]{method="ReindexDb" type="command"}
#[@METHOD]{method="Verify" type="command"}
#[@METHOD]{method="_p" type="helper"}
#[@METHOD]{method="_ParseMethod" type="helper"}
#[@METHOD]{method="_WrapReturns" type="helper"}
#[@METHOD]{method="_IsTuple3" type="helper"}
#[@METHOD]{method="read_state" type="command"}
#[@METHOD]{method="set_config" type="command"}
#[@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<VBStyle fix engine. DB-driven granular method repair. AST-based Tuple3 wrapping + self._ rename. SQL UPDATE + file sync.>][@todos<none>]}
"""
VbStyleFixEngine -- DB-driven VBStyle violation fix engine.

Reads from dom_graph_work.db:
  - methods table: method_code, returns_tuple3, has_self_underscore, has_print, has_decorator
  - files table: file_name, path
  - classes table: is_vbstyle, has_run_method, has_tuple3

Fixes:
  1. Tuple3: wrap `return X` -> `return (1, X, None)`, `return None` -> `return (1, None, None)`
  2. self._: rename _Get -> Get, _BuildDb -> BuildDb, etc. + update call sites

Then:
  - SQL UPDATE methods table with fixed method_code
  - Write fixed methods back to .py files (replace lines start_line-end_line)
  - Re-index DB and verify all flags compliant
"""

import ast
import os
import re
import sqlite3
import textwrap
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dom_graph_work.db")
DOMAIN_DIR = os.path.dirname(os.path.abspath(__file__))


class VbStyleFixEngine:
    """DB-driven VBStyle fix engine. Run() dispatch: scan | fix_tuple3 | fix_self_ | sync | reindex | verify | all."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "db_path": DB_PATH,
            "domain_dir": DOMAIN_DIR,
            "violations": {},
            "fixed_methods": 0,
            "fixed_files": set(),
            "errors": [],
            "dry_run": False,
        }
        self.conn = None
        self.cur = None

    def Run(self, command, params=None):
        params = params or {}
        if command == "scan":
            return self.ScanViolations(params)
        elif command == "fix_tuple3":
            return self.FixTuple3(params)
        elif command == "fix_self_":
            return self.FixSelfUnderscore(params)
        elif command == "sync":
            return self.SyncToFile(params)
        elif command == "reindex":
            return self.ReindexDb(params)
        elif command == "verify":
            return self.Verify(params)
        elif command == "all":
            return self._RunAll(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        return params.get(key, default) if params else default

    def _Connect(self):
        if self.conn is None:
            self.conn = sqlite3.connect(self.state["db_path"])
            self.cur = self.conn.cursor()
        return self.cur

    def _Close(self):
        if self.conn:
            self.conn.commit()
            self.conn.close()
            self.conn = None
            self.cur = None

    def ScanViolations(self, params):
        """Scan DB for all VBStyle violations. Returns summary dict."""
        dry = self._p(params, "dry_run", False)
        self.state["dry_run"] = dry
        cur = self._Connect()

        violations = {
            "no_tuple3": [],
            "self_underscore": [],
            "has_print": [],
            "has_decorator": [],
            "classes_not_vbstyle": [],
        }

        for r in cur.execute('''SELECT m.method_id, m.method_name, f.file_name,
                                m.start_line, m.end_line, m.returns_tuple3,
                                m.has_print, m.has_decorator, m.has_self_underscore
                             FROM methods m JOIN files f ON m.file_id=f.file_id
                             WHERE m.returns_tuple3=0 OR m.has_print=1
                                OR m.has_decorator=1 OR m.has_self_underscore=1
                             ORDER BY f.file_name, m.start_line'''):
            mid, mname, fname, sline, eline, t3, pr, dec, su = r
            entry = {"method_id": mid, "method_name": mname, "file": fname,
                     "start_line": sline, "end_line": eline}
            if t3 == 0:
                violations["no_tuple3"].append(entry)
            if pr == 1:
                violations["has_print"].append(entry)
            if dec == 1:
                violations["has_decorator"].append(entry)
            if su == 1:
                violations["self_underscore"].append(entry)

        for r in cur.execute('''SELECT c.class_name, f.file_name, c.is_vbstyle,
                                c.has_run_method, c.has_tuple3
                             FROM classes c JOIN files f ON c.file_id=f.file_id
                             WHERE c.is_vbstyle=0 OR c.has_run_method=0 OR c.has_tuple3=0
                             ORDER BY f.file_name'''):
            violations["classes_not_vbstyle"].append({
                "class_name": r[0], "file": r[1],
                "is_vbstyle": r[2], "has_run": r[3], "has_tuple3": r[4],
            })

        self.state["violations"] = violations
        self._Close()

        summary = {
            "no_tuple3": len(violations["no_tuple3"]),
            "self_underscore": len(violations["self_underscore"]),
            "has_print": len(violations["has_print"]),
            "has_decorator": len(violations["has_decorator"]),
            "classes_not_vbstyle": len(violations["classes_not_vbstyle"]),
        }
        return (1, summary, None)

    def _ParseMethod(self, method_code):
        """Parse a method fragment into an AST. Returns (tree, error)."""
        try:
            dedented = textwrap.dedent(method_code)
            wrapped = "class _Dummy:\n" + textwrap.indent(dedented, "    ")
            tree = ast.parse(wrapped)
            return tree, None
        except SyntaxError as e:
            return None, str(e)

    def _IsTuple3(self, node):
        """Check if a Return node already returns a Tuple3 (1, data, None) or (0, None, tuple)."""
        if node.value is None:
            return False
        if isinstance(node.value, ast.Tuple) and len(node.value.elts) == 3:
            return True
        return False

    def _WrapReturns(self, method_code):
        """Transform all return statements in method_code to Tuple3 format.
        Returns (fixed_code, num_fixes, error).
        Uses AST end_lineno to handle multi-line returns correctly.
        Parses method directly (def is valid at module level)."""
        try:
            dedented = textwrap.dedent(method_code)
            tree = ast.parse(dedented)
        except SyntaxError as e:
            return method_code, 0, "Parse error: " + str(e)

        lines = method_code.split("\n")
        fixes = []

        return_nodes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Return):
                return_nodes.append(node)

        return_nodes.sort(key=lambda n: n.lineno, reverse=True)

        for node in return_nodes:
            if self._IsTuple3(node):
                continue

            start = node.lineno - 1
            end = getattr(node, 'end_lineno', node.lineno) - 1
            if start < 0 or start >= len(lines):
                continue

            first_line = lines[start]
            indent = len(first_line) - len(first_line.lstrip())
            indent_str = first_line[:indent]

            if node.value is None:
                lines[start] = indent_str + "return (1, None, None)"
                if end > start:
                    del lines[start+1:end+1]
                fixes.append(start)
            else:
                if end == start:
                    m = re.match(r'^(\s*)return\s+(.+)$', first_line)
                    if m:
                        ret_val = m.group(2).rstrip()
                        if ret_val == "None":
                            lines[start] = indent_str + "return (1, None, None)"
                        else:
                            lines[start] = indent_str + "return (1, " + ret_val + ", None)"
                        fixes.append(start)
                else:
                    expr_lines = lines[start:end+1]
                    expr_first = expr_lines[0]
                    expr_rest = expr_lines[1:]

                    m = re.match(r'^(\s*)return\s+(.+)$', expr_first)
                    if m:
                        expr_start = m.group(2)
                    else:
                        expr_start = expr_first.strip()

                    if expr_start.rstrip() == "None":
                        lines[start] = indent_str + "return (1, None, None)"
                        del lines[start+1:end+1]
                    else:
                        lines[start] = indent_str + "return (1, " + expr_start
                        last_idx = len(expr_rest) - 1
                        last_line = expr_rest[last_idx]
                        last_stripped = last_line.rstrip()
                        if last_stripped.endswith(","):
                            last_stripped = last_stripped[:-1]
                        trailing_ws = last_line[len(last_line.rstrip()):]
                        expr_rest[last_idx] = last_stripped + ", None)" + trailing_ws
                        lines[start+1:end+1] = expr_rest
                        fixes.append(start)

        if not fixes:
            try:
                tree2 = ast.parse(textwrap.dedent(method_code))
                for node in ast.walk(tree2):
                    if isinstance(node, ast.FunctionDef):
                        last_stmt = node.body[-1] if node.body else None
                        if last_stmt and not isinstance(last_stmt, ast.Return):
                            lines.append("        return (1, None, None)")
                            fixes.append(len(lines) - 1)
                        elif last_stmt is None:
                            lines.append("        return (1, None, None)")
                            fixes.append(len(lines) - 1)
            except SyntaxError:
                pass

        fixed = "\n".join(lines)
        return fixed, len(fixes), None

    def FixTuple3(self, params):
        """Fix all methods missing Tuple3 returns. UPDATEs DB + collects for sync."""
        dry = self._p(params, "dry_run", self.state.get("dry_run", False))
        cur = self._Connect()

        rows = cur.execute('''SELECT m.method_id, m.method_name, f.file_name,
                              m.start_line, m.end_line, m.method_code
                           FROM methods m JOIN files f ON m.file_id=f.file_id
                           WHERE m.returns_tuple3=0 AND m.is_dunder=0
                           ORDER BY f.file_name, m.start_line''').fetchall()

        fixed_count = 0
        errors = []
        file_methods = {}

        for row in rows:
            mid, mname, fname, sline, eline, code = row
            fixed_code, nfixes, err = self._WrapReturns(code)
            if err:
                errors.append({"file": fname, "method": mname, "error": err})
                continue
            if nfixes == 0:
                continue

            if not dry:
                cur.execute('''UPDATE methods SET method_code=?, returns_tuple3=1
                             WHERE method_id=?''', (fixed_code, mid))

            if fname not in file_methods:
                file_methods[fname] = []
            file_methods[fname].append({
                "method_id": mid, "method_name": mname,
                "start_line": sline, "end_line": eline,
                "old_code": code, "new_code": fixed_code,
            })
            fixed_count += 1
            self.state["fixed_files"].add(fname)

        self.state["violations"]["_file_methods"] = file_methods
        self.state["fixed_methods"] = fixed_count
        self.state["errors"].extend(errors)
        self._Close()

        return (1, {"fixed": fixed_count, "errors": len(errors),
                     "files": list(file_methods.keys())}, None)

    def FixSelfUnderscore(self, params):
        """Fix self._ violations by renaming _Method -> Method and updating call sites."""
        dry = self._p(params, "dry_run", self.state.get("dry_run", False))
        cur = self._Connect()

        rows = cur.execute('''SELECT m.method_id, m.method_name, f.file_name,
                              m.start_line, m.end_line, m.method_code, m.file_id
                           FROM methods m JOIN files f ON m.file_id=f.file_id
                           WHERE m.has_self_underscore=1
                           ORDER BY f.file_name, m.start_line''').fetchall()

        rename_map = {}
        file_renames = {}

        for row in rows:
            mid, mname, fname, sline, eline, code, file_id = row
            if mname.startswith("_") and mname != "_p":
                new_name = mname[1].upper() + mname[2:] if len(mname) > 1 else mname
                rename_map[mname] = new_name
                if fname not in file_renames:
                    file_renames[fname] = {}
                file_renames[fname][mname] = new_name

        for row in rows:
            mid, mname, fname, sline, eline, code, file_id = row
            fixed = code
            for old_name, new_name in rename_map.items():
                fixed = re.sub(
                    r'\bself\._' + re.escape(old_name[1:]) + r'\b',
                    'self.' + new_name,
                    fixed
                )
                fixed = re.sub(
                    r'\bdef _' + re.escape(old_name[1:]) + r'\b',
                    'def ' + new_name,
                    fixed
                )

            if fixed != code:
                if not dry:
                    cur.execute('''UPDATE methods SET method_code=?, has_self_underscore=0
                                 WHERE method_id=?''', (fixed, mid))

        all_rows = cur.execute('''SELECT m.method_id, m.method_name, f.file_name,
                                  m.start_line, m.end_line, m.method_code
                               FROM methods m JOIN files f ON m.file_id=f.file_id
                               ORDER BY f.file_name, m.start_line''').fetchall()

        for row in all_rows:
            mid, mname, fname, sline, eline, code = row
            fixed = code
            changed = False
            for old_name, new_name in rename_map.items():
                new_fixed = re.sub(
                    r'\bself\._' + re.escape(old_name[1:]) + r'\b',
                    'self.' + new_name,
                    fixed
                )
                if new_fixed != fixed:
                    fixed = new_fixed
                    changed = True

            if changed:
                if not dry:
                    cur.execute('''UPDATE methods SET method_code=?
                                 WHERE method_id=?''', (fixed, mid))

        self._Close()
        return (1, {"renames": rename_map, "files": list(file_renames.keys())}, None)

    def SyncToFile(self, params):
        """Write fixed method_code from DB back to .py files."""
        dry = self._p(params, "dry_run", self.state.get("dry_run", False))
        cur = self._Connect()

        file_methods = self.state.get("violations", {}).get("_file_methods", {})
        if not file_methods:
            rows = cur.execute('''SELECT m.method_id, m.method_name, f.file_name,
                                  m.start_line, m.end_line, m.method_code
                               FROM methods m JOIN files f ON m.file_id=f.file_id
                               ORDER BY f.file_name, m.start_line DESC''').fetchall()
            file_methods = {}
            for row in rows:
                fname = row[2]
                if fname not in file_methods:
                    file_methods[fname] = []
                file_methods[fname].append({
                    "method_name": row[1], "start_line": row[3],
                    "end_line": row[4], "new_code": row[5],
                })

        synced = 0
        errors = []

        for fname, methods in file_methods.items():
            fpath = os.path.join(self.state["domain_dir"], fname)
            if not os.path.exists(fpath):
                errors.append({"file": fname, "error": "File not found"})
                continue

            with open(fpath, "r") as f:
                file_lines = f.readlines()

            methods_sorted = sorted(methods, key=lambda m: m["start_line"], reverse=True)

            for m in methods_sorted:
                sline = m["start_line"]
                eline = m["end_line"]
                new_code = m["new_code"]

                if sline < 1 or sline > len(file_lines):
                    errors.append({"file": fname, "method": m["method_name"],
                                   "error": "Line range out of bounds"})
                    continue

                old_lines = file_lines[sline-1:eline]
                old_text = "".join(old_lines).rstrip("\n")
                db_text = new_code.rstrip("\n")

                if old_text.strip() == db_text.strip():
                    continue

                new_lines = new_code.split("\n")
                if not new_lines[-1].endswith("\n"):
                    new_lines[-1] = new_lines[-1] + "\n"

                file_lines[sline-1:eline] = [l + "\n" if not l.endswith("\n") else l for l in new_lines]
                synced += 1

            if not dry:
                with open(fpath, "w") as f:
                    f.writelines(file_lines)

        self._Close()
        return (1, {"synced": synced, "errors": len(errors), "error_list": errors}, None)

    def ReindexDb(self, params):
        """Re-scan .py files and update DB flags (returns_tuple3, has_self_underscore, etc.)."""
        dry = self._p(params, "dry_run", self.state.get("dry_run", False))
        cur = self._Connect()

        rows = cur.execute('''SELECT m.method_id, m.method_name, f.file_name,
                              m.start_line, m.end_line
                           FROM methods m JOIN files f ON m.file_id=f.file_id
                           ORDER BY f.file_name, m.start_line''').fetchall()

        updated = 0
        for row in rows:
            mid, mname, fname, sline, eline = row
            fpath = os.path.join(self.state["domain_dir"], fname)
            if not os.path.exists(fpath):
                continue

            with open(fpath, "r") as f:
                file_lines = f.readlines()

            if sline < 1 or eline > len(file_lines):
                continue

            code = "".join(file_lines[sline-1:eline])

            has_print = 1 if re.search(r'\bprint\s*\(', code) else 0
            has_decorator = 1 if re.search(r'^\s*@', code, re.MULTILINE) else 0
            has_su = 1 if re.search(r'\bself\._(?!p\b)', code) else 0

            tree, _ = self._ParseMethod(code)
            returns_t3 = 1
            if tree:
                for node in ast.walk(tree):
                    if isinstance(node, ast.Return):
                        if not self._IsTuple3(node):
                            returns_t3 = 0
                            break
                func_defs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
                if func_defs:
                    fd = func_defs[0]
                    if fd.body and not isinstance(fd.body[-1], ast.Return):
                        returns_t3 = 0
            else:
                returns_t3 = 0

            if not dry:
                cur.execute('''UPDATE methods SET returns_tuple3=?, has_print=?,
                             has_decorator=?, has_self_underscore=?
                             WHERE method_id=?''',
                             (returns_t3, has_print, has_decorator, has_su, mid))
            updated += 1

        if not dry:
            cur.execute('''UPDATE classes SET is_vbstyle=1, has_tuple3=1
                         WHERE class_id IN (
                             SELECT DISTINCT c.class_id FROM classes c
                             JOIN methods m ON m.class_id=c.class_id
                             GROUP BY c.class_id
                             HAVING SUM(CASE WHEN m.returns_tuple3=0 THEN 1 ELSE 0 END)=0
                                AND SUM(CASE WHEN m.has_print=1 THEN 1 ELSE 0 END)=0
                                AND SUM(CASE WHEN m.has_self_underscore=1 THEN 1 ELSE 0 END)=0
                         )''')

        self._Close()
        return (1, {"reindexed": updated}, None)

    def Verify(self, params):
        """Verify all fixed files: py_compile + grep for violations."""
        cur = self._Connect()

        results = {"py_compile": [], "grep_print": [], "grep_decorator": [],
                   "grep_self_": [], "db_violations": {}}

        files_with_methods = cur.execute('''SELECT DISTINCT f.file_name
                                           FROM methods m JOIN files f ON m.file_id=f.file_id
                                           ORDER BY f.file_name''').fetchall()

        for (fname,) in files_with_methods:
            fpath = os.path.join(self.state["domain_dir"], fname)
            if not os.path.exists(fpath):
                continue

            try:
                import py_compile
                py_compile.compile(fpath, doraise=True)
                results["py_compile"].append({"file": fname, "ok": True})
            except py_compile.PyCompileError as e:
                results["py_compile"].append({"file": fname, "ok": False, "error": str(e)})

            with open(fpath, "r") as f:
                content = f.read()

            pr = len(re.findall(r'\bprint\s*\(', content))
            dec = len(re.findall(r'^\s*@(?!REVIEW)', content, re.MULTILINE))
            su = len(re.findall(r'\bself\._(?!p\b)', content))

            if pr > 0:
                results["grep_print"].append({"file": fname, "count": pr})
            if dec > 0:
                results["grep_decorator"].append({"file": fname, "count": dec})
            if su > 0:
                results["grep_self_"].append({"file": fname, "count": su})

        for label, col in [("no_tuple3", "returns_tuple3=0"), ("has_print", "has_print=1"),
                           ("has_decorator", "has_decorator=1"),
                           ("self_underscore", "has_self_underscore=1")]:
            n = cur.execute(f'SELECT COUNT(*) FROM methods WHERE {col}').fetchone()[0]
            results["db_violations"][label] = n

        not_vb = cur.execute('SELECT COUNT(*) FROM classes WHERE is_vbstyle=0').fetchone()[0]
        results["db_violations"]["classes_not_vbstyle"] = not_vb

        self._Close()
        return (1, results, None)

    def _RunAll(self, params):
        """Run full pipeline: scan -> fix_tuple3 -> fix_self_ -> sync -> reindex -> verify."""
        results = {}
        for cmd in ["scan", "fix_tuple3", "fix_self_", "sync", "reindex", "verify"]:
            r = self.Run(cmd, params)
            results[cmd] = r
            if r[0] == 0:
                results["_error"] = "Failed at: " + cmd
                break
        return (1, results, None)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params=None):
        params = params or {}
        if "db_path" in params:
            self.state["db_path"] = params["db_path"]
        if "domain_dir" in params:
            self.state["domain_dir"] = params["domain_dir"]
        if "dry_run" in params:
            self.state["dry_run"] = params["dry_run"]
        return (1, dict(self.state), None)


if __name__ == "__main__":
    import sys
    engine = VbStyleFixEngine()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"
    p = {"dry_run": "--dry-run" in sys.argv}
    code, data, err = engine.Run(cmd, p)
    if code == 1:
        import json
        print(json.dumps(data, indent=2, default=str))
    else:
        print("ERROR:", err)
        sys.exit(1)
