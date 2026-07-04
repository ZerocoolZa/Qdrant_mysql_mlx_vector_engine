#!/usr/bin/env python3
# [@GHOST]{[@file<ingest_to_db.py>][@domain<chat_mover>][@role<ingest>][@auth<devin>][@date<2026-06-30>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<chat_mover_ingest>][@return<tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths|abc|inheritance>]}
# [@FILEID]{[@fileid<chat_mover.ingest_to_db>]}
# [@SUMMARY]{[@summary<AST-based ingester: parses all .py files in chat_mover/ and indexes files/classes/methods/constants/imports into chat_mover_work.db with VBStyle compliance flags.>]}
# [@CLASS]{[@class<ChatMoverIngester>]}
# [@METHOD]{[@method<Run>][@method<IngestAll>][@method<IngestFile>][@method<CreateSchema>][@method<ExtractMethods>][@method<ExtractConstants>][@method<ExtractImports>][@method<AnalyzeClass>][@method<MethodReturnsTuple3>][@method<MethodHasPrint>][@method<MethodHasDecorator>][@method<MethodHasSelfUnderscore>][@method<IsDunder>][@method<BuildSummary>]}

"""Ingest all .py files in chat_mover/ into SQLite database chat_mover_work.db.

Indexes files, classes, methods, constants, and imports using the ast module.
Computes VBStyle compliance flags for every class and method.
"""

import ast
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "chat_mover_work.db"


class ChatMoverIngester:
    """AST-based ingester that indexes chat_mover .py files into SQLite."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "db_path": str(DB_PATH),
            "base_dir": str(BASE_DIR),
            "files_total": 0,
            "classes_total": 0,
            "methods_total": 0,
            "constants_total": 0,
            "imports_total": 0,
            "parse_errors": [],
            "violations": {
                "missing_tuple3": 0,
                "has_print": 0,
                "has_decorator": 0,
                "has_self_underscore": 0,
            },
            "non_vbstyle_classes": [],
        }
        self.conn = None
        self.cur = None

    def _p(self, key):
        return self.state.get(key)

    def read_state(self):
        return dict(self.state)

    def set_config(self, key, value):
        self.state[key] = value
        return (1, self.state, None)

    def Run(self, command, params=None):
        """Dispatch entry point. Commands: ingest, schema, summary, restore, restore_one, list_files, gc_sweep, gc_status."""
        dispatch = {
            "ingest": self.CmdIngest,
            "schema": self.CmdSchema,
            "summary": self.CmdSummary,
            "restore": self.CmdRestore,
            "restore_one": self.CmdRestoreOne,
            "list_files": self.CmdListFiles,
            "gc_sweep": self.CmdGcSweep,
            "gc_status": self.CmdGcStatus,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (404, "Unknown command: " + str(command), 0))
        return handler(params)

    def CmdIngest(self, params):
        conn_res = self.OpenDb()
        if conn_res[0] == 0:
            return conn_res
        schema_res = self.CreateSchema()
        if schema_res[0] == 0:
            return schema_res
        ingest_res = self.IngestAll()
        if ingest_res[0] == 0:
            return ingest_res
        self.CloseDb()
        summary_res = self.BuildSummary()
        if summary_res[0] == 0:
            return summary_res
        return (1, self.state, None)

    def CmdSchema(self, params):
        conn_res = self.OpenDb()
        if conn_res[0] == 0:
            return conn_res
        schema_res = self.CreateSchema()
        if schema_res[0] == 0:
            return schema_res
        self.CloseDb()
        return (1, {"schema_created": True}, None)

    def CmdSummary(self, params):
        return self.BuildSummary()

    def CmdRestore(self, params):
        """Restore all .py files from DB to disk."""
        conn_res = self.OpenDb()
        if conn_res[0] == 0:
            return conn_res
        rows = self.cur.execute("SELECT file_name, content FROM files").fetchall()
        restored = []
        for fname, content in rows:
            fpath = os.path.join(self.state["base_dir"], fname)
            with open(fpath, "w") as f:
                f.write(content)
            restored.append(fname)
        self.CloseDb()
        return (1, {"restored": len(restored), "files": restored}, None)

    def CmdRestoreOne(self, params):
        """Restore a single .py file from DB by file_name."""
        if not params or "file_name" not in params:
            return (0, None, (400, "file_name required", 0))
        fname = params["file_name"]
        conn_res = self.OpenDb()
        if conn_res[0] == 0:
            return conn_res
        row = self.cur.execute("SELECT content FROM files WHERE file_name=?", (fname,)).fetchone()
        self.CloseDb()
        if row is None:
            return (0, None, (404, "File not found in DB: " + fname, 0))
        fpath = os.path.join(self.state["base_dir"], fname)
        with open(fpath, "w") as f:
            f.write(row[0])
        return (1, {"restored": fname, "path": fpath}, None)

    def CmdListFiles(self, params):
        """List all files in the DB."""
        conn_res = self.OpenDb()
        if conn_res[0] == 0:
            return conn_res
        rows = self.cur.execute("SELECT file_name, line_count FROM files ORDER BY file_name").fetchall()
        self.CloseDb()
        files = [{"file_name": r[0], "line_count": r[1]} for r in rows]
        return (1, {"files": files, "total": len(files)}, None)

    def CmdGcStatus(self, params):
        """Report GC status: how many files active vs retired vs on disk."""
        conn_res = self.OpenDb()
        if conn_res[0] == 0:
            return conn_res
        db_total = self.cur.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        db_active = self.cur.execute("SELECT COUNT(*) FROM files WHERE status='active'").fetchone()[0] if self._HasStatusColumn() else db_total
        db_retired = self.cur.execute("SELECT COUNT(*) FROM files WHERE status='retired'").fetchone()[0] if self._HasStatusColumn() else 0
        self.CloseDb()
        disk_files = [f for f in os.listdir(self.state["base_dir"]) if f.endswith(".py")]
        return (1, {
            "db_total": db_total,
            "db_active": db_active,
            "db_retired": db_retired,
            "disk_files": len(disk_files),
            "disk_files_list": sorted(disk_files),
        }, None)

    def CmdGcSweep(self, params):
        """GC pipeline sweep — follows Plf_PipelineBclCodeLifecycle.md.
        
        Flow (per GC_PIPELINE.md):
        1. For each .py file on disk:
           a. Check if file is in DB (SELECT content FROM files WHERE file_name=?)
           b. If YES: verify DB content matches disk content (hash check)
              → Mark DB row status='retired'
              → Remove file from disk (safe — DB has content + zip has backup)
           c. If NO: SKIP (code would be lost forever)
        2. Never use raw rm — this method IS the GC pipeline
        3. Return sweep report
        
        Params:
          confirm: "yes" required to actually remove files (dry-run by default)
          keep: list of filenames to keep (e.g., ["__init__.py", "ingest_to_db.py"])
        """
        confirm = "no"
        keep = ["__init__.py", "ingest_to_db.py"]
        if params:
            confirm = params.get("confirm", "no")
            keep_param = params.get("keep", "")
            if keep_param:
                keep = keep_param.split(",")
        
        conn_res = self.OpenDb()
        if conn_res[0] == 0:
            return conn_res
        
        self._EnsureStatusColumn()
        
        disk_files = sorted(f for f in os.listdir(self.state["base_dir"]) if f.endswith(".py"))
        swept = []
        skipped_not_in_db = []
        skipped_keep = []
        skipped_hash_mismatch = []
        
        for fname in disk_files:
            if fname in keep:
                skipped_keep.append(fname)
                continue
            
            row = self.cur.execute("SELECT content FROM files WHERE file_name=?", (fname,)).fetchone()
            if row is None:
                skipped_not_in_db.append(fname)
                continue
            
            db_content = row[0]
            fpath = os.path.join(self.state["base_dir"], fname)
            with open(fpath) as f:
                disk_content = f.read()
            
            import hashlib
            db_hash = hashlib.sha256(db_content.encode("utf-8")).hexdigest()
            disk_hash = hashlib.sha256(disk_content.encode("utf-8")).hexdigest()
            
            if db_hash != disk_hash:
                skipped_hash_mismatch.append(fname)
                continue
            
            if confirm == "yes":
                self.cur.execute("UPDATE files SET status='retired', retired_at=CURRENT_TIMESTAMP WHERE file_name=?", (fname,))
                os.remove(fpath)
                swept.append(fname)
            else:
                swept.append(fname + " (dry-run)")
        
        self.conn.commit()
        self.CloseDb()
        
        return (1, {
            "mode": "live" if confirm == "yes" else "dry-run",
            "swept": swept,
            "swept_count": len(swept),
            "skipped_keep": skipped_keep,
            "skipped_not_in_db": skipped_not_in_db,
            "skipped_hash_mismatch": skipped_hash_mismatch,
            "total_disk": len(disk_files),
        }, None)

    def _HasStatusColumn(self):
        """Check if files table has status column."""
        cols = self.cur.execute("PRAGMA table_info(files)").fetchall()
        return any(c[1] == "status" for c in cols)

    def _EnsureStatusColumn(self):
        """Add status + retired_at columns if missing."""
        if not self._HasStatusColumn():
            self.cur.execute("ALTER TABLE files ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'")
            self.cur.execute("ALTER TABLE files ADD COLUMN retired_at TIMESTAMP NULL")
            self.conn.commit()

    def OpenDb(self):
        try:
            self.conn = sqlite3.connect(self.state["db_path"])
            self.cur = self.conn.cursor()
            return (1, True, None)
        except Exception as exc:
            return (0, None, (500, "DB open failed: " + str(exc), 0))

    def CloseDb(self):
        if self.conn is not None:
            self.conn.commit()
            self.conn.close()
            self.conn = None
            self.cur = None
        return (1, True, None)

    def CreateSchema(self):
        """Drop and recreate all tables."""
        try:
            self.cur.execute("DROP TABLE IF EXISTS files")
            self.cur.execute("DROP TABLE IF EXISTS classes")
            self.cur.execute("DROP TABLE IF EXISTS methods")
            self.cur.execute("DROP TABLE IF EXISTS constants")
            self.cur.execute("DROP TABLE IF EXISTS imports")
            self.cur.execute(
                "CREATE TABLE files ("
                "file_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "file_name TEXT, "
                "path TEXT, "
                "line_count INTEGER, "
                "content TEXT)"
            )
            self.cur.execute(
                "CREATE TABLE classes ("
                "class_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "file_id INTEGER, "
                "class_name TEXT, "
                "start_line INTEGER, "
                "end_line INTEGER, "
                "method_count INTEGER, "
                "is_vbstyle INTEGER, "
                "has_run_method INTEGER, "
                "has_tuple3 INTEGER, "
                "has_print INTEGER, "
                "has_decorator INTEGER, "
                "has_self_underscore INTEGER, "
                "FOREIGN KEY(file_id) REFERENCES files(file_id))"
            )
            self.cur.execute(
                "CREATE TABLE methods ("
                "method_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "class_id INTEGER, "
                "file_id INTEGER, "
                "method_name TEXT, "
                "method_code TEXT, "
                "start_line INTEGER, "
                "end_line INTEGER, "
                "returns_tuple3 INTEGER, "
                "has_print INTEGER, "
                "has_decorator INTEGER, "
                "has_self_underscore INTEGER, "
                "is_dunder INTEGER, "
                "is_vbstyle INTEGER, "
                "FOREIGN KEY(class_id) REFERENCES classes(class_id), "
                "FOREIGN KEY(file_id) REFERENCES files(file_id))"
            )
            self.cur.execute(
                "CREATE TABLE constants ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "file_id INTEGER, "
                "name TEXT, "
                "value TEXT, "
                "line INTEGER, "
                "FOREIGN KEY(file_id) REFERENCES files(file_id))"
            )
            self.cur.execute(
                "CREATE TABLE imports ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "file_id INTEGER, "
                "module TEXT, "
                "alias TEXT, "
                "line INTEGER, "
                "FOREIGN KEY(file_id) REFERENCES files(file_id))"
            )
            return (1, True, None)
        except Exception as exc:
            return (0, None, (501, "Schema creation failed: " + str(exc), 0))

    def IngestAll(self):
        """Walk BASE_DIR for .py files and ingest each."""
        base = Path(self.state["base_dir"])
        py_files = sorted(base.glob("*.py"))
        for py_file in py_files:
            if py_file.name == "ingest_to_db.py":
                continue
            res = self.IngestFile(py_file)
            if res[0] == 0:
                self.state["parse_errors"].append(
                    {"file": py_file.name, "error": str(res[2])}
                )
        return (1, self.state, None)

    def IngestFile(self, py_path):
        """Parse a single .py file and insert rows for all its symbols."""
        try:
            source = py_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return (0, None, (502, "Read failed: " + str(exc), 0))
        try:
            tree = ast.parse(source, filename=str(py_path))
        except SyntaxError as exc:
            return (0, None, (503, "Parse failed: " + str(exc), 0))
        source_lines = source.splitlines()
        line_count = len(source_lines)
        self.cur.execute(
            "INSERT INTO files (file_name, path, line_count, content) VALUES (?, ?, ?, ?)",
            (py_path.name, str(py_path), line_count, source),
        )
        file_id = self.cur.lastrowid
        self.state["files_total"] += 1

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                cls_res = self.AnalyzeClass(node, file_id, source)
                if cls_res[0] == 0:
                    return cls_res
            elif isinstance(node, ast.Assign):
                self.ExtractConstants(node, file_id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                self.ExtractImports(node, file_id)
        return (1, file_id, None)

    def AnalyzeClass(self, node, file_id, source):
        """Insert a class row and all its method rows; compute VBStyle flags."""
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)
        method_nodes = [
            n for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        method_rows = []
        has_run = 0
        for m_node in method_nodes:
            if m_node.name == "Run":
                has_run = 1
            is_dunder = self.IsDunder(m_node.name)
            returns_t3 = self.MethodReturnsTuple3(m_node)
            has_print = self.MethodHasPrint(m_node)
            has_dec = self.MethodHasDecorator(m_node)
            has_su = self.MethodHasSelfUnderscore(m_node)
            method_code = ast.get_source_segment(source, m_node)
            if method_code is None:
                method_code = "\n".join(source.splitlines()[m_node.lineno - 1: m_node.end_lineno])
            is_vb = 1 if (returns_t3 == 1 or is_dunder == 1) and has_print == 0 and has_dec == 0 and has_su == 0 else 0
            method_rows.append({
                "method_name": m_node.name,
                "method_code": method_code,
                "start_line": m_node.lineno,
                "end_line": getattr(m_node, "end_lineno", m_node.lineno),
                "returns_tuple3": returns_t3,
                "has_print": has_print,
                "has_decorator": has_dec,
                "has_self_underscore": has_su,
                "is_dunder": is_dunder,
                "is_vbstyle": is_vb,
            })
            self.state["methods_total"] += 1
            if returns_t3 == 0 and is_dunder == 0:
                self.state["violations"]["missing_tuple3"] += 1
            if has_print == 1:
                self.state["violations"]["has_print"] += 1
            if has_dec == 1:
                self.state["violations"]["has_decorator"] += 1
            if has_su == 1:
                self.state["violations"]["has_self_underscore"] += 1

        non_dunder = [r for r in method_rows if r["is_dunder"] == 0]
        all_tuple3 = 1 if non_dunder and all(r["returns_tuple3"] == 1 for r in non_dunder) else 0
        any_print = 1 if any(r["has_print"] == 1 for r in method_rows) else 0
        any_dec = 1 if any(r["has_decorator"] == 1 for r in method_rows) else 0
        any_su = 1 if any(r["has_self_underscore"] == 1 for r in method_rows) else 0
        all_compliant = 1 if method_rows and all(r["is_vbstyle"] == 1 for r in method_rows) else 0
        is_vbstyle = 1 if all_compliant == 1 else 0
        if is_vbstyle == 0:
            self.state["non_vbstyle_classes"].append(node.name)

        self.cur.execute(
            "INSERT INTO classes (file_id, class_name, start_line, end_line, "
            "method_count, is_vbstyle, has_run_method, has_tuple3, has_print, "
            "has_decorator, has_self_underscore) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (file_id, node.name, start_line, end_line, len(method_rows),
             is_vbstyle, has_run, all_tuple3, any_print, any_dec, any_su),
        )
        class_id = self.cur.lastrowid
        self.state["classes_total"] += 1
        for r in method_rows:
            self.cur.execute(
                "INSERT INTO methods (class_id, file_id, method_name, method_code, "
                "start_line, end_line, returns_tuple3, has_print, has_decorator, "
                "has_self_underscore, is_dunder, is_vbstyle) VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (class_id, file_id, r["method_name"], r["method_code"],
                 r["start_line"], r["end_line"], r["returns_tuple3"],
                 r["has_print"], r["has_decorator"], r["has_self_underscore"],
                 r["is_dunder"], r["is_vbstyle"]),
            )
        return (1, class_id, None)

    def ExtractConstants(self, node, file_id):
        """Module-level UPPERCASE constants."""
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                value = self.RenderConstantValue(node.value)
                self.cur.execute(
                    "INSERT INTO constants (file_id, name, value, line) VALUES (?, ?, ?, ?)",
                    (file_id, target.id, value, node.lineno),
                )
                self.state["constants_total"] += 1
        return (1, True, None)

    def ExtractImports(self, node, file_id):
        """Import statements."""
        if isinstance(node, ast.Import):
            for alias in node.names:
                self.cur.execute(
                    "INSERT INTO imports (file_id, module, alias, line) VALUES (?, ?, ?, ?)",
                    (file_id, alias.name, alias.asname, node.lineno),
                )
                self.state["imports_total"] += 1
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                full = mod + "." + alias.name if mod else alias.name
                self.cur.execute(
                    "INSERT INTO imports (file_id, module, alias, line) VALUES (?, ?, ?, ?)",
                    (file_id, full, alias.asname, node.lineno),
                )
                self.state["imports_total"] += 1
        return (1, True, None)

    def RenderConstantValue(self, value_node):
        try:
            return ast.unparse(value_node)
        except Exception:
            return "<unparseable>"

    def MethodReturnsTuple3(self, node):
        """1 if method has at least one return of a 3-tuple."""
        for sub in ast.walk(node):
            if isinstance(sub, ast.Return) and sub.value is not None:
                if isinstance(sub.value, ast.Tuple) and len(sub.value.elts) == 3:
                    return 1
        return 0

    def MethodHasPrint(self, node):
        """1 if any print() call in method body (excluding nested functions)."""
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                func = sub.func
                if isinstance(func, ast.Name) and func.id == "print":
                    return 1
                if isinstance(func, ast.Attribute) and func.attr == "print":
                    return 1
        return 0

    def MethodHasDecorator(self, node):
        """1 if any decorator present."""
        if node.decorator_list:
            return 1
        return 0

    def MethodHasSelfUnderscore(self, node):
        """1 if self._ found (excluding self._p which is the VBStyle helper)."""
        for sub in ast.walk(node):
            if isinstance(sub, ast.Attribute):
                val = sub.value
                if isinstance(val, ast.Name) and val.id == "self":
                    if sub.attr.startswith("_") and sub.attr != "_p":
                        return 1
        return 0

    def IsDunder(self, name):
        """1 if name starts and ends with __."""
        if name.startswith("__") and name.endswith("__") and len(name) >= 4:
            return 1
        return 0

    def BuildSummary(self):
        """Build the final summary dict."""
        summary = {
            "db_path": self.state["db_path"],
            "files_total": self.state["files_total"],
            "classes_total": self.state["classes_total"],
            "methods_total": self.state["methods_total"],
            "constants_total": self.state["constants_total"],
            "imports_total": self.state["imports_total"],
            "parse_errors": self.state["parse_errors"],
            "violations": self.state["violations"],
            "non_vbstyle_classes": self.state["non_vbstyle_classes"],
            "vbstyle_compliant_classes": (
                self.state["classes_total"] - len(self.state["non_vbstyle_classes"])
            ),
        }
        self.state["summary"] = summary
        return (1, summary, None)


def main():
    """CLI entry point. Supports: ingest, restore, restore_one, list_files, summary."""
    import sys
    ingester = ChatMoverIngester()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ingest"
    params = {}
    for arg in sys.argv[2:]:
        if "=" in arg:
            k, v = arg.split("=", 1)
            params[k] = v

    if cmd == "ingest":
        result = ingester.Run("ingest")
        if result[0] == 0:
            print("INGEST FAILED: " + str(result[2]))
            return 1
        summary = ingester._p("summary") or result[1]
        print("=" * 60)
        print("CHAT_MOVER INGEST SUMMARY")
        print("=" * 60)
        print("DB path: " + str(summary["db_path"]))
        print("Files ingested:    " + str(summary["files_total"]))
        print("Classes found:     " + str(summary["classes_total"]))
        print("Methods found:     " + str(summary["methods_total"]))
        print("Constants found:   " + str(summary["constants_total"]))
        print("Imports found:     " + str(summary["imports_total"]))
        print("-" * 60)
        print("VBStyle violation counts (methods):")
        v = summary["violations"]
        print("  Missing Tuple3:   " + str(v["missing_tuple3"]))
        print("  Has print():      " + str(v["has_print"]))
        print("  Has decorator:    " + str(v["has_decorator"]))
        print("  Has self._:       " + str(v["has_self_underscore"]))
        print("-" * 60)
        print("VBStyle compliant classes: " + str(summary["vbstyle_compliant_classes"]))
        print("Non-VBStyle classes:       " + str(len(summary["non_vbstyle_classes"])))
        if summary["non_vbstyle_classes"]:
            print("  " + ", ".join(summary["non_vbstyle_classes"]))
        print("=" * 60)
        return 0
    elif cmd in ("restore", "restore_one", "list_files", "summary", "schema", "gc_sweep", "gc_status"):
        result = ingester.Run(cmd, params)
        if result[0] == 0:
            print("ERROR: " + str(result[2]))
            return 1
        import json
        print(json.dumps(result[1], indent=2, default=str))
        return 0
    else:
        print("Usage: python3 ingest_to_db.py [ingest|restore|restore_one file_name=X|list_files|gc_sweep confirm=yes|gc_status|summary]")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
