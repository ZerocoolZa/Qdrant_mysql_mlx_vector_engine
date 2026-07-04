#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_mysql_ingestor.py"
# date="2026-06-27" author="Cascade" session_id="bcl-mysql-ingest"
# context="Ingest all BCL folder Python files into MySQL vb_code_test tables"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_mysql_ingestor.py" domain="BCL"}
# [@SUMMARY]{summary="Ingest BCL folder into MySQL vb_code_test: bcl_codebases, bcl_files, bcl_classes, bcl_methods, bcl_edges."}
# [@CLASS]{name="BCLMysqlIngestor" purpose="MySQL ingestion of BCL folder"}

"""
BCL MySQL Ingestor — loads all BCL .py files into MySQL vb_code_test.

Tables populated:
  bcl_codebases — one row for the BCL codebase
  bcl_files     — one row per .py file
  bcl_classes   — one row per class
  bcl_methods   — one row per method
  bcl_edges     — call graph edges (method-to-method)

Usage:
  python3 bcl_mysql_ingestor.py ingest    — full ingestion
  python3 bcl_mysql_ingestor.py status    — show current state
  python3 bcl_mysql_ingestor.py clean     — delete BCL rows from all tables
"""

import ast
import hashlib
import os
import sys
import json
import MySQLdb

BCL_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = "vb_code_test"
CODEBASE_NAME = "bcl_folder"


class BCLMysqlIngestor:
    """Ingest BCL folder Python files into MySQL vb_code_test."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "bcl_dir": BCL_DIR,
            "db_name": DB_NAME,
            "codebase_name": CODEBASE_NAME,
            "conn": None,
            "codebase_id": None,
            "files_ingested": 0,
            "classes_ingested": 0,
            "methods_ingested": 0,
            "edges_ingested": 0,
            "errors": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state[key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "ingest":
            return self.Ingest(params)
        elif command == "status":
            return self.Status(params)
        elif command == "clean":
            return self.Clean(params)
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

    def Connect(self, params=None):
        try:
            conn = MySQLdb.connect(
                host="localhost",
                user="root",
                passwd="",
                db=self.state["db_name"],
                charset="utf8mb4",
            )
            self.state["conn"] = conn
            return (1, conn, None)
        except Exception as e:
            err = ("DB_CONNECT_ERROR", str(e), 0)
            self.state["errors"].append(str(e))
            return (0, None, err)

    def Close(self, params=None):
        conn = self.state.get("conn")
        if conn:
            conn.close()
            self.state["conn"] = None
        return (1, True, None)

    def GetCodebaseId(self, params=None):
        conn = self.state["conn"]
        cur = conn.cursor()
        cur.execute("SELECT id FROM bcl_codebases WHERE name=%s", (self.state["codebase_name"],))
        row = cur.fetchone()
        if row:
            self.state["codebase_id"] = row[0]
            return (1, row[0], None)
        cur.execute(
            "INSERT INTO bcl_codebases (name, root_path, file_count, class_count, method_count, edge_count, unit_count) VALUES (%s, %s, 0, 0, 0, 0, 0)",
            (self.state["codebase_name"], self.state["bcl_dir"]),
        )
        conn.commit()
        self.state["codebase_id"] = cur.lastrowid
        return (1, cur.lastrowid, None)

    def CleanCodebase(self, params=None):
        conn = self.state["conn"]
        cur = conn.cursor()
        cb_id = self.state["codebase_id"]
        cur.execute("DELETE FROM bcl_edges WHERE codebase_id=%s", (cb_id,))
        cur.execute("DELETE FROM bcl_methods WHERE codebase_id=%s", (cb_id,))
        cur.execute("DELETE FROM bcl_classes WHERE codebase_id=%s", (cb_id,))
        cur.execute("DELETE FROM bcl_files WHERE codebase_id=%s", (cb_id,))
        conn.commit()
        return (1, True, None)

    def StableId(self, filepath, node_type, name, lineno):
        raw = "%s:%s:%s:%s" % (filepath, node_type, name, lineno)
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def AstHash(self, node):
        try:
            return hashlib.md5(ast.dump(node).encode()).hexdigest()[:16]
        except Exception:
            return hashlib.md5(str(node).encode()).hexdigest()[:16]

    def ExtractMethodType(self, node):
        if isinstance(node, ast.AsyncFunctionDef):
            return "async"
        if node.name == "__init__":
            return "constructor"
        if node.name == "Run":
            return "dispatch"
        if node.name.startswith("_") and node.name != "__init__":
            return "private"
        return "method"

    def ExtractParams(self, node):
        params = []
        for arg in node.args.args:
            params.append(arg.arg)
        return ",".join(params)

    def ExtractCalls(self, node):
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    calls.append({"callee": child.func.attr, "type": "attr", "lineno": getattr(child, "lineno", 0)})
                elif isinstance(child.func, ast.Name):
                    calls.append({"callee": child.func.id, "type": "name", "lineno": getattr(child, "lineno", 0)})
        return calls

    def HasBranching(self, node):
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.Match, ast.ExceptHandler)):
                return True
        return False

    def HasLoops(self, node):
        for child in ast.walk(node):
            if isinstance(child, (ast.For, ast.While)):
                return True
        return False

    def HasRecursion(self, node):
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name) and child.func.id == node.name:
                    return True
        return False

    def IngestFile(self, filepath):
        conn = self.state["conn"]
        cur = conn.cursor()
        cb_id = self.state["codebase_id"]

        with open(filepath, "r") as f:
            source = f.read()
        source_lines = source.splitlines()
        file_hash = hashlib.md5(source.encode()).hexdigest()
        file_name = os.path.basename(filepath)
        rel_path = os.path.relpath(filepath, self.state["bcl_dir"])

        try:
            tree = ast.parse(source, filename=filepath)
        except SyntaxError as e:
            self.state["errors"].append("%s: %s" % (filepath, str(e)))
            return (0, None, ("PARSE_ERROR", str(e), 0))

        class_nodes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        method_count = 0
        class_ids = {}

        cur.execute(
            "INSERT INTO bcl_files (codebase_id, file_path, file_name, file_hash, line_count, class_count, method_count) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (cb_id, rel_path, file_name, file_hash, len(source_lines), len(class_nodes), 0),
        )
        file_id = cur.lastrowid

        for cls_node in class_nodes:
            cls_hash = self.AstHash(cls_node)
            bases = ",".join(ast.unparse(b) for b in cls_node.bases) if cls_node.bases else ""
            cls_methods = [n for n in cls_node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

            cur.execute(
                "INSERT INTO bcl_classes (codebase_id, class_name, file_path, bases, method_count, line_start, line_end) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (cb_id, cls_node.name, rel_path, bases, len(cls_methods), cls_node.lineno, getattr(cls_node, "end_lineno", cls_node.lineno)),
            )
            cls_db_id = cur.lastrowid
            class_ids[cls_node.name] = cls_db_id

            for m_node in cls_methods:
                m_hash = self.AstHash(m_node)
                m_hash = hashlib.md5(("%s:%s:%s" % (rel_path, cls_node.name, m_hash)).encode()).hexdigest()[:16]
                m_type = self.ExtractMethodType(m_node)
                params = self.ExtractParams(m_node)
                calls = self.ExtractCalls(m_node)
                has_branch = self.HasBranching(m_node)
                has_loops = self.HasLoops(m_node)
                has_recursion = self.HasRecursion(m_node)

                cur.execute(
                    "INSERT INTO bcl_methods (codebase_id, bcl_class_id, method_id, method_id_hash, method_name, class_name, file_path, method_type, is_async, line_start, line_end, ast_hash, inputs, has_branching, has_loops, has_recursion) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        cb_id, cls_db_id,
                        "%s.%s" % (cls_node.name, m_node.name),
                        m_hash,
                        m_node.name,
                        cls_node.name,
                        rel_path,
                        m_type,
                        1 if isinstance(m_node, ast.AsyncFunctionDef) else 0,
                        m_node.lineno,
                        getattr(m_node, "end_lineno", m_node.lineno),
                        m_hash,
                        params,
                        1 if has_branch else 0,
                        1 if has_loops else 0,
                        1 if has_recursion else 0,
                    ),
                )
                m_db_id = cur.lastrowid
                method_count += 1

                for call in calls:
                    cur.execute(
                        "INSERT INTO bcl_edges (codebase_id, bcl_method_id, source_method_id, target, edge_type, certainty, line_number) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (
                            cb_id, m_db_id,
                            "%s.%s" % (cls_node.name, m_node.name),
                            call["callee"],
                            call["type"].upper(),
                            "certain",
                            call["lineno"],
                        ),
                    )
                    self.state["edges_ingested"] += 1

            self.state["classes_ingested"] += 1

        cur.execute("UPDATE bcl_files SET method_count=%s WHERE id=%s", (method_count, file_id))
        conn.commit()
        self.state["files_ingested"] += 1
        self.state["methods_ingested"] += method_count
        return (1, {"file": rel_path, "classes": len(class_nodes), "methods": method_count}, None)

    def Ingest(self, params=None):
        conn_result = self.Connect()
        if conn_result[0] != 1:
            return conn_result
        cb_result = self.GetCodebaseId()
        if cb_result[0] != 1:
            return cb_result
        self.CleanCodebase()

        bcl_dir = self.state["bcl_dir"]
        py_files = sorted([
            f for f in os.listdir(bcl_dir)
            if f.endswith(".py") and f != "bcl_mysql_ingestor.py" and f != "ingest_bcl.py" and f != "bcl_fix_cli.py"
        ])

        results = []
        for fn in py_files:
            fp = os.path.join(bcl_dir, fn)
            r = self.IngestFile(fp)
            if r[0] == 1:
                results.append(r[1])
            else:
                self.state["errors"].append("%s: %s" % (fn, str(r[2])))

        conn = self.state["conn"]
        cur = conn.cursor()
        cur.execute(
            "UPDATE bcl_codebases SET file_count=%s, class_count=%s, method_count=%s, edge_count=%s, scanned_at=NOW() WHERE id=%s",
            (self.state["files_ingested"], self.state["classes_ingested"], self.state["methods_ingested"], self.state["edges_ingested"], self.state["codebase_id"]),
        )
        conn.commit()

        self.Close()
        summary = {
            "files": self.state["files_ingested"],
            "classes": self.state["classes_ingested"],
            "methods": self.state["methods_ingested"],
            "edges": self.state["edges_ingested"],
            "errors": self.state["errors"],
        }
        sys.stdout.write("Ingested: %d files, %d classes, %d methods, %d edges\n" % (
            summary["files"], summary["classes"], summary["methods"], summary["edges"]))
        if self.state["errors"]:
            sys.stdout.write("Errors: %d\n" % len(self.state["errors"]))
            for e in self.state["errors"]:
                sys.stdout.write("  %s\n" % e)
        return (1, summary, None)

    def Status(self, params=None):
        conn_result = self.Connect()
        if conn_result[0] != 1:
            return conn_result
        conn = self.state["conn"]
        cur = conn.cursor()

        cur.execute("SELECT * FROM bcl_codebases WHERE name=%s", (self.state["codebase_name"],))
        cb = cur.fetchone()
        if not cb:
            sys.stdout.write("Codebase '%s' not found. Run 'ingest' first.\n" % self.state["codebase_name"])
            self.Close()
            return (1, {"found": False}, None)

        cur.execute("SELECT COUNT(*) FROM bcl_files WHERE codebase_id=%s", (cb[0],))
        files = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM bcl_classes WHERE codebase_id=%s", (cb[0],))
        classes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM bcl_methods WHERE codebase_id=%s", (cb[0],))
        methods = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM bcl_edges WHERE codebase_id=%s", (cb[0],))
        edges = cur.fetchone()[0]

        sys.stdout.write("Codebase: %s (id=%s)\n" % (cb[1], cb[0]))
        sys.stdout.write("  Files:   %d\n" % files)
        sys.stdout.write("  Classes: %d\n" % classes)
        sys.stdout.write("  Methods: %d\n" % methods)
        sys.stdout.write("  Edges:   %d\n" % edges)

        sys.stdout.write("\nFiles:\n")
        cur.execute("SELECT file_name, line_count, class_count, method_count FROM bcl_files WHERE codebase_id=%s ORDER BY file_name", (cb[0],))
        for row in cur.fetchall():
            sys.stdout.write("  %-30s %4d lines  %2d classes  %3d methods\n" % (row[0], row[1], row[2], row[3]))

        sys.stdout.write("\nClasses:\n")
        cur.execute("SELECT class_name, file_path, method_count, line_start, line_end FROM bcl_classes WHERE codebase_id=%s ORDER BY class_name", (cb[0],))
        for row in cur.fetchall():
            sys.stdout.write("  %-25s %-25s %3d methods  L%d-%d\n" % (row[0], row[1], row[2], row[3], row[4]))

        self.Close()
        return (1, {"files": files, "classes": classes, "methods": methods, "edges": edges}, None)

    def Clean(self, params=None):
        conn_result = self.Connect()
        if conn_result[0] != 1:
            return conn_result
        cb_result = self.GetCodebaseId()
        if cb_result[0] != 1:
            return cb_result
        self.CleanCodebase()
        sys.stdout.write("Cleaned all BCL rows from MySQL.\n")
        self.Close()
        return (1, True, None)


def Main():
    if len(sys.argv) < 2:
        sys.stdout.write("Usage: python3 bcl_mysql_ingestor.py <ingest|status|clean>\n")
        return
    cmd = sys.argv[1]
    ingestor = BCLMysqlIngestor()
    result = ingestor.Run(cmd, {})
    if result[0] == 0:
        err = result[2]
        if err:
            sys.stdout.write("ERROR: %s - %s\n" % (err[0], err[1]))


if __name__ == "__main__":
    Main()
