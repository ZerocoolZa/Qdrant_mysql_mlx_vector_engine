#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_fix_cli.py"
# date="2026-06-27" author="Cascade" session_id="bcl-vbstyle-fix"
# context="VBStyle CLI: DB-driven violation query, fix, ingest, verify"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_fix_cli.py" domain="BCL"}
# [@SUMMARY]{summary="VBStyle CLI: query bcl_inventory.db, apply fixes, re-ingest, verify."}
# [@CLASS]{name="BCLFixCli" purpose="Database-driven VBStyle violation fixer"}
# [@METHOD]{name="Run" purpose="Dispatch entry point"}

"""
BCL Fix CLI - Database-driven VBStyle violation fixer.

Usage:
    python3 bcl_fix_cli.py status              Show all violations grouped by file
    python3 bcl_fix_cli.py count               Show violation counts per file
    python3 bcl_fix_cli.py file <filename>     Show violations for one file
    python3 bcl_fix_cli.py fix <filename>      Apply fixes for one file
    python3 bcl_fix_cli.py fixall              Apply fixes for all files
    python3 bcl_fix_cli.py verify              Compile-check all BCL .py files
    python3 bcl_fix_cli.py ingest              Re-run ingestion to update DB

All fixes are applied programmatically - no manual editing needed.
"""

import sys
import os
import re
import py_compile
import sqlite3
import subprocess

DB_PATH = "bcl_inventory.db"
BCL_DIR = os.path.dirname(os.path.abspath(__file__))


class BCLFixCli:
    """Database-driven VBStyle violation fixer with Run() dispatch."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "db_path": DB_PATH,
            "bcl_dir": BCL_DIR,
            "config": {},
            "last_result": None,
        }
        if param:
            for key, value in param.items():
                self.state[key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "status":
            return self.Status(params)
        elif command == "count":
            return self.Count(params)
        elif command == "file":
            return self.File(params)
        elif command == "fix":
            return self.Fix(params)
        elif command == "fixall":
            return self.FixAll(params)
        elif command == "verify":
            return self.Verify(params)
        elif command == "ingest":
            return self.Ingest(params)
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
            self.state[key] = value
        return (1, dict(self.state), None)

    def GetDb(self, params=None):
        db = sqlite3.connect(self.state["db_path"])
        db.row_factory = sqlite3.Row
        return (1, db, None)

    def Status(self, params):
        result = self.GetDb()
        if result[0] != 1:
            return result
        db = result[1]
        rows = db.execute("""
            SELECT f.filename, v.rule, v.class_name, v.method_name, v.description
            FROM violations v JOIN files f ON v.file_id = f.id
            ORDER BY f.filename, v.class_name, v.rule
        """).fetchall()
        db.close()
        if not rows:
            return (1, "No violations found.", None)
        output = []
        current_file = ""
        for r in rows:
            if r["filename"] != current_file:
                current_file = r["filename"]
                output.append("\n=== %s ===" % current_file)
            method = r["method_name"] or ""
            desc = r["description"] or ""
            output.append("  %-15s %-20s %-15s %s" % (r["rule"], r["class_name"], method, desc))
        text = "\n".join(output)
        sys.stdout.write(text + "\n")
        return (1, text, None)

    def Count(self, params):
        result = self.GetDb()
        if result[0] != 1:
            return result
        db = result[1]
        rows = db.execute("""
            SELECT f.filename, COUNT(v.id) as cnt
            FROM files f JOIN violations v ON f.id = v.file_id
            GROUP BY f.filename ORDER BY cnt DESC
        """).fetchall()
        db.close()
        total = 0
        output = []
        for r in rows:
            output.append("  %-30s %d" % (r["filename"], r["cnt"]))
            total += r["cnt"]
        output.append("  %-30s %d" % ("TOTAL", total))
        text = "\n".join(output)
        sys.stdout.write(text + "\n")
        return (1, {"total": total, "files": dict((r["filename"], r["cnt"]) for r in rows)}, None)

    def File(self, params):
        filename = self._p(params, "filename")
        if not filename:
            return (0, None, ("MISSING_PARAM", "filename required", 0))
        result = self.GetDb()
        if result[0] != 1:
            return result
        db = result[1]
        rows = db.execute("""
            SELECT v.rule, v.class_name, v.method_name, v.description
            FROM violations v JOIN files f ON v.file_id = f.id
            WHERE f.filename = ?
            ORDER BY v.class_name, v.rule
        """, (filename,)).fetchall()
        db.close()
        if not rows:
            return (1, "No violations for %s" % filename, None)
        output = []
        for r in rows:
            method = r["method_name"] or ""
            desc = r["description"] or ""
            output.append("  %-15s %-20s %-15s %s" % (r["rule"], r["class_name"], method, desc))
        text = "\n".join(output)
        sys.stdout.write(text + "\n")
        return (1, text, None)

    def Verify(self, params):
        bcl_dir = self.state["bcl_dir"]
        files = [f for f in os.listdir(bcl_dir) if f.endswith(".py") and not f.startswith("fix_") and f != "bcl_fix_cli.py" and f != "ingest_bcl.py"]
        ok = 0
        fail = 0
        output = []
        for fn in sorted(files):
            try:
                py_compile.compile(fn, doraise=True)
                output.append("  OK:   %s" % fn)
                ok += 1
            except py_compile.PyCompileError as e:
                output.append("  FAIL: %s - %s" % (fn, str(e)[:150]))
                fail += 1
        output.append("\n%d OK, %d FAIL" % (ok, fail))
        text = "\n".join(output)
        sys.stdout.write(text + "\n")
        return (1, {"ok": ok, "fail": fail}, None)

    def Ingest(self, params):
        bcl_dir = self.state["bcl_dir"]
        result = subprocess.run([sys.executable, "ingest_bcl.py"], capture_output=True, text=True, cwd=bcl_dir)
        stdout = result.stdout.strip()
        if stdout:
            sys.stdout.write(stdout + "\n")
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if stderr:
                sys.stdout.write("STDERR: " + stderr + "\n")
            return (0, None, ("INGEST_FAIL", "Ingestion failed", 0))
        count_result = self.Count({})
        return (1, {"stdout": stdout, "count": count_result[1] if count_result[0] == 1 else None}, None)

    def ReadFile(self, params):
        filename = self._p(params, "filename")
        if not filename:
            return (0, None, ("MISSING_PARAM", "filename required", 0))
        path = os.path.join(self.state["bcl_dir"], filename)
        with open(path, "r") as f:
            return (1, f.read(), None)

    def WriteFile(self, params):
        filename = self._p(params, "filename")
        content = self._p(params, "content")
        if not filename or content is None:
            return (0, None, ("MISSING_PARAM", "filename and content required", 0))
        path = os.path.join(self.state["bcl_dir"], filename)
        with open(path, "w") as f:
            f.write(content)
        return (1, True, None)

    def Fix(self, params):
        filename = self._p(params, "filename")
        if not filename:
            return (0, None, ("MISSING_PARAM", "filename required", 0))
        db_result = self.GetDb()
        if db_result[0] != 1:
            return db_result
        db = db_result[1]
        rows = db.execute("""
            SELECT v.rule, v.class_name, v.method_name, v.description
            FROM violations v JOIN files f ON v.file_id = f.id
            WHERE f.filename = ?
            ORDER BY v.class_name, v.rule
        """, (filename,)).fetchall()
        db.close()

        if not rows:
            return (1, "No violations for %s" % filename, None)

        read_result = self.ReadFile({"filename": filename})
        if read_result[0] != 1:
            return read_result
        src = read_result[1]
        fixes_applied = []

        classes = {}
        for r in rows:
            cn = r["class_name"] or ""
            if cn not in classes:
                classes[cn] = []
            classes[cn].append(dict(r))

        for cls_name, viols in classes.items():
            if any(v["rule"] == "no_run" for v in viols):
                add_result = self.AddRunDispatch({"source": src, "class_name": cls_name})
                if add_result[0] == 1:
                    src = add_result[1]
                    fixes_applied.append("Added Run() dispatch to %s" % cls_name)

        for cls_name, viols in classes.items():
            if any(v["rule"] == "no_state" for v in viols):
                add_result = self.AddStateDict({"source": src, "class_name": cls_name})
                if add_result[0] == 1:
                    src = add_result[1]
                    fixes_applied.append("Added self.state dict to %s" % cls_name)

        for cls_name, viols in classes.items():
            tuple3_methods = [v["method_name"] for v in viols if v["rule"] == "no_tuple3" and v["method_name"]]
            for method_name in tuple3_methods:
                fix_result = self.FixTuple3({"source": src, "class_name": cls_name, "method_name": method_name})
                if fix_result[0] == 1:
                    src = fix_result[1]
                    fixes_applied.append("Fixed Tuple3 return in %s.%s" % (cls_name, method_name))

        if any(v["rule"] == "print_statement" for v in rows):
            fix_result = self.FixPrintStatements({"source": src})
            if fix_result[0] == 1:
                src = fix_result[1]
                fixes_applied.append("Removed print() statements")

        if any(v["rule"] == "decorator" for v in rows):
            fix_result = self.FixDecorators({"source": src})
            if fix_result[0] == 1:
                src = fix_result[1]
                fixes_applied.append("Removed decorators")

        if any(v["rule"] == "property_decorator" for v in rows):
            fix_result = self.FixPropertyDecorators({"source": src})
            if fix_result[0] == 1:
                src = fix_result[1]
                fixes_applied.append("Removed @property")

        if any(v["rule"] == "self_underscore" for v in rows):
            fix_result = self.FixSelfUnderscore({"source": src})
            if fix_result[0] == 1:
                src = fix_result[1]
                fixes_applied.append("Fixed self._ access")

        if fixes_applied:
            write_result = self.WriteFile({"filename": filename, "content": src})
            if write_result[0] != 1:
                return write_result
            compile_ok = True
            try:
                py_compile.compile(filename, doraise=True)
            except py_compile.PyCompileError as e:
                compile_ok = False
                fixes_applied.append("COMPILE: FAIL - %s" % str(e)[:200])
            if compile_ok:
                fixes_applied.append("COMPILE: OK")
            output = "Applied %d fixes to %s:\n  - %s" % (len(fixes_applied), filename, "\n  - ".join(fixes_applied))
            sys.stdout.write(output + "\n")
            return (1, {"fixes": fixes_applied, "compile_ok": compile_ok}, None)
        else:
            return (1, "No applicable fixes for %s" % filename, None)

    def FixAll(self, params):
        db_result = self.GetDb()
        if db_result[0] != 1:
            return db_result
        db = db_result[1]
        rows = db.execute("""
            SELECT DISTINCT f.filename
            FROM violations v JOIN files f ON v.file_id = f.id
            ORDER BY f.filename
        """).fetchall()
        db.close()
        all_results = []
        for r in rows:
            sys.stdout.write("\n--- Fixing %s ---\n" % r["filename"])
            fix_result = self.Fix({"filename": r["filename"]})
            all_results.append({"filename": r["filename"], "result": fix_result[1] if fix_result[0] == 1 else None})
        return (1, all_results, None)

    def AddRunDispatch(self, params):
        src = self._p(params, "source")
        class_name = self._p(params, "class_name")
        if src is None or not class_name:
            return (0, None, ("MISSING_PARAM", "source and class_name required", 0))
        pattern = r'(class %s.*?def __init__.*?\n)(\s+def [A-Z])' % re.escape(class_name)
        match = re.search(pattern, src, re.DOTALL)
        if match:
            run_method = match.group(1) + '''
    def Run(self, command, params=None):
        params = params or {}
        if command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

''' + match.group(2)
            src = src[:match.start()] + run_method + src[match.end():]
        return (1, src, None)

    def AddStateDict(self, params):
        src = self._p(params, "source")
        class_name = self._p(params, "class_name")
        if src is None or not class_name:
            return (0, None, ("MISSING_PARAM", "source and class_name required", 0))
        pattern = r'(class %s[^:]*:\s*.*?def __init__\([^)]*\):\s*\n)(.*?)(\n\s+def )' % re.escape(class_name)
        match = re.search(pattern, src, re.DOTALL)
        if match:
            init_body = match.group(2)
            if 'self.state' in init_body:
                return (1, src, None)
            attr_lines = re.findall(r'self\.(\w+)\s*=\s*(.+)', init_body)
            if attr_lines:
                state_entries = ', '.join('"%s": %s' % (k, v.strip()) for k, v in attr_lines)
                new_init = '\n        self.state = {\n            %s\n        }\n' % state_entries.replace(', ', ',\n            ')
                src = src[:match.start(2)] + new_init + src[match.end(2):]
        return (1, src, None)

    def FixTuple3(self, params):
        src = self._p(params, "source")
        class_name = self._p(params, "class_name")
        method_name = self._p(params, "method_name")
        if src is None or not method_name:
            return (0, None, ("MISSING_PARAM", "source and method_name required", 0))
        pattern = r'(def %s\([^)]*\):.*?)(\n\s+def |\nclass |\Z)' % re.escape(method_name)
        match = re.search(pattern, src, re.DOTALL)
        if match:
            method_body = match.group(1)
            returns = re.findall(r'return\s+\(', method_body)
            if returns:
                return (1, src, None)
            fixed_body = re.sub(
                r'return\s+(?!self\.)(?!Tuple3)(.+?)(\s*$)',
                lambda m: 'return (1, %s, None)' % m.group(1).strip(),
                method_body,
                flags=re.MULTILINE
            )
            src = src[:match.start(1)] + fixed_body + src[match.end(1):]
        return (1, src, None)

    def FixPrintStatements(self, params):
        src = self._p(params, "source")
        if src is None:
            return (0, None, ("MISSING_PARAM", "source required", 0))
        lines = src.split("\n")
        fixed = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                fixed.append(line)
                continue
            if re.match(r'\s*print\s*\(', stripped):
                indent = line[:len(line) - len(line.lstrip())]
                fixed.append(indent + "pass  # print removed")
            else:
                fixed.append(line)
        return (1, "\n".join(fixed), None)

    def FixDecorators(self, params):
        src = self._p(params, "source")
        if src is None:
            return (0, None, ("MISSING_PARAM", "source required", 0))
        lines = src.split("\n")
        fixed = []
        for line in lines:
            stripped = line.strip()
            if stripped in ("@staticmethod", "@classmethod"):
                continue
            fixed.append(line)
        return (1, "\n".join(fixed), None)

    def FixPropertyDecorators(self, params):
        src = self._p(params, "source")
        if src is None:
            return (0, None, ("MISSING_PARAM", "source required", 0))
        lines = src.split("\n")
        fixed = []
        for line in lines:
            stripped = line.strip()
            if stripped == "@property":
                continue
            fixed.append(line)
        return (1, "\n".join(fixed), None)

    def FixSelfUnderscore(self, params):
        src = self._p(params, "source")
        if src is None:
            return (0, None, ("MISSING_PARAM", "source required", 0))
        lines = src.split("\n")
        fixed = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                fixed.append(line)
                continue
            new_line = re.sub(r'self\._(?!p\b)(?!_\w)', 'self.', line)
            fixed.append(new_line)
        return (1, "\n".join(fixed), None)


def Main():
    if len(sys.argv) < 2:
        sys.stdout.write("Usage: python3 bcl_fix_cli.py <command> [args]\n")
        sys.stdout.write("Commands: status, count, file <fn>, fix <fn>, fixall, verify, ingest\n")
        return
    cmd = sys.argv[1]
    cli = BCLFixCli()
    params = {}
    if len(sys.argv) > 2:
        params["filename"] = sys.argv[2]
    result = cli.Run(cmd, params)
    if result[0] == 0:
        err = result[2]
        if err:
            sys.stdout.write("ERROR: %s - %s\n" % (err[0], err[1]))


if __name__ == "__main__":
    Main()
