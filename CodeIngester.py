#!/usr/bin/env python3
"""
#[@GHOST]{("file_path=/Users/wws/Qdrant_mysql_mlx_vector_engine/CodeIngester.py";"identity=CodeIngester";"purpose=Stage 1: Ingest .py files into SQLite code_graph DB. One row per method + full file row + dependency edges.";"date=2026-06-27";"version=1.1";"author=Devin";"chat_link=sqlite://code_graph.db/code_units")}
#[@VBSTYLE]{("auth=Devin";"role=tool";"return=Tuple3";"orch=none";"no=no_decorators|no_print|no_hardcoded";"model=one_class_one_domain_one_authority_complete")}
#[@FILEID]{("session_id=mire-region";"context=Code Graph Pipeline Stage 1";"purpose=Ingest source files into normalized SQLite rows for graph-based reasoning")}
#[@SUMMARY]{("Stage 1 of the code graph pipeline. Reads .py files, uses ast.parse to extract FILE/CLASS/METHOD/FUNCTION/IMPORT/MODULE_CONST units, stores full file text in code_files, per-unit rows in code_units, and dependency edges in code_edges. SQLite for testing. The table IS the file.")}
"""
import ast
import os
import sys
import sqlite3
import hashlib
import argparse


DB_PATH = "code_graph.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS code_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE,
    file_hash TEXT,
    full_source TEXT,
    line_count INTEGER,
    class_count INTEGER,
    method_count INTEGER,
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS code_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT,
    file_hash TEXT,
    class_name TEXT,
    method_name TEXT,
    unit_type TEXT NOT NULL CHECK (unit_type IN
        ('FILE','CLASS','METHOD','FUNCTION','MODULE_CONST','IMPORT','MAIN_BLOCK')),
    source_text TEXT,
    docstring TEXT,
    return_type TEXT,
    dispatch_key TEXT,
    calls TEXT,
    called_by TEXT,
    imports TEXT,
    line_start INTEGER,
    line_end INTEGER,
    parent_class TEXT,
    is_vbstyle INTEGER DEFAULT 0,
    content_hash TEXT,
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cu_class ON code_units(class_name);
CREATE INDEX IF NOT EXISTS idx_cu_method ON code_units(method_name);
CREATE INDEX IF NOT EXISTS idx_cu_file ON code_units(file_path);
CREATE INDEX IF NOT EXISTS idx_cu_type ON code_units(unit_type);
CREATE INDEX IF NOT EXISTS idx_cu_hash ON code_units(content_hash);

CREATE TABLE IF NOT EXISTS code_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_class TEXT,
    from_method TEXT,
    to_class TEXT,
    to_method TEXT,
    edge_type TEXT NOT NULL CHECK (edge_type IN
        ('CALLS','IMPORTS','CONTAINS','INHERITS','DECORATES','REFERENCES')),
    evidence_line INTEGER
);
CREATE INDEX IF NOT EXISTS idx_ce_from ON code_edges(from_class, from_method);
CREATE INDEX IF NOT EXISTS idx_ce_to ON code_edges(to_class, to_method);
CREATE INDEX IF NOT EXISTS idx_ce_type ON code_edges(edge_type);
"""


def _hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _connect(db_path=None):
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    return conn


def _get_source_segment(source_lines, start_line, end_line):
    if start_line is None or end_line is None:
        return ""
    return "".join(source_lines[start_line - 1:end_line])


def _extract_calls(node):
    calls = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Attribute):
                calls.add(func.attr)
            elif isinstance(func, ast.Name):
                calls.add(func.id)
    return sorted(calls)


def _get_dispatch_key(node):
    for child in ast.walk(node):
        if isinstance(child, ast.Dict):
            keys = []
            for k in child.keys:
                if isinstance(k, ast.Constant):
                    keys.append(str(k.value))
            if keys and len(keys) > 1:
                return ",".join(keys)
    return None


def _has_vbstyle_markers(source_text):
    markers = ["def Run(self", "Tuple3", "self.state", "def _p(self"]
    return sum(1 for m in markers if m in source_text) >= 2


def _get_return_type(node):
    if node.returns:
        if isinstance(node.returns, ast.Name):
            return node.returns.id
        if isinstance(node.returns, ast.Subscript):
            return ast.dump(node.returns)[:50]
    if node.body:
        for child in ast.walk(node):
            if isinstance(child, ast.Return) and child.value:
                if isinstance(child, ast.Tuple):
                    return "Tuple3"
    return None


def ingest_file(conn, file_path, base_dir=""):
    abs_path = file_path if os.path.isabs(file_path) else os.path.join(base_dir, file_path)
    if not os.path.exists(abs_path):
        return 0, 0, None

    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()

    source_lines = source.splitlines(keepends=True)
    file_hash = _hash(source)

    try:
        tree = ast.parse(source, filename=abs_path)
    except SyntaxError as e:
        sys.stderr.write(f"PARSE FAIL {file_path}: {e}\n")
        return 0, 0, None

    cur = conn.cursor()
    units = 0
    edges = 0

    # --- code_files: full file row ---
    cur.execute("""
        INSERT INTO code_files (file_path, file_hash, full_source, line_count, class_count, method_count)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(file_path) DO UPDATE SET
            file_hash=excluded.file_hash, full_source=excluded.full_source,
            line_count=excluded.line_count, class_count=excluded.class_count,
            method_count=excluded.method_count, ingested_at=CURRENT_TIMESTAMP
    """, (file_path, file_hash, source, len(source_lines),
          sum(1 for n in ast.iter_child_nodes(tree) if isinstance(n, ast.ClassDef)),
          sum(1 for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))))

    # --- imports ---
    imports = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    imports_str = ",".join(sorted(set(imports)))

    # --- module-level constants ---
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    seg = _get_source_segment(source_lines, node.lineno,
                                              getattr(node, "end_lineno", node.lineno))
                    cur.execute("""
                        INSERT INTO code_units
                            (file_path, file_hash, class_name, method_name, unit_type,
                             source_text, dispatch_key, imports, line_start, line_end,
                             is_vbstyle, content_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (file_path, file_hash, None, target.id, "MODULE_CONST",
                          seg, None, imports_str, node.lineno,
                          getattr(node, "end_lineno", node.lineno),
                          1 if _has_vbstyle_markers(source) else 0,
                          _hash(seg)))
                    units += 1

    # --- import block as a unit ---
    if imports:
        first_import = None
        last_import = None
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if first_import is None:
                    first_import = node.lineno
                last_import = getattr(node, "end_lineno", node.lineno)
        cur.execute("""
            INSERT INTO code_units
                (file_path, file_hash, class_name, method_name, unit_type,
                 source_text, dispatch_key, imports, line_start, line_end,
                 is_vbstyle, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (file_path, file_hash, None, "__imports__", "IMPORT",
              ",".join(sorted(set(imports))), None, imports_str,
              first_import or 0, last_import or 0,
              1 if _has_vbstyle_markers(source) else 0,
              _hash(imports_str)))
        units += 1

    # --- classes and methods ---
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            class_start = node.lineno
            class_end = getattr(node, "end_lineno", node.lineno)
            class_seg = _get_source_segment(source_lines, class_start, class_end)
            class_doc = ast.get_docstring(node)

            cur.execute("""
                INSERT INTO code_units
                    (file_path, file_hash, class_name, method_name, unit_type,
                     source_text, docstring, dispatch_key, imports, line_start, line_end,
                     parent_class, is_vbstyle, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (file_path, file_hash, class_name, None, "CLASS",
                  class_seg, class_doc, None, imports_str,
                  class_start, class_end, None,
                  1 if _has_vbstyle_markers(class_seg) else 0,
                  _hash(class_seg)))
            units += 1

            method_names = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    m_name = item.name
                    m_start = item.lineno
                    m_end = getattr(item, "end_lineno", item.lineno)
                    m_seg = _get_source_segment(source_lines, m_start, m_end)
                    m_doc = ast.get_docstring(item)
                    m_calls = _extract_calls(item)
                    m_dispatch = _get_dispatch_key(item)
                    m_return = _get_return_type(item)

                    cur.execute("""
                        INSERT INTO code_units
                            (file_path, file_hash, class_name, method_name, unit_type,
                             source_text, docstring, return_type, dispatch_key,
                             calls, imports, line_start, line_end,
                             parent_class, is_vbstyle, content_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (file_path, file_hash, class_name, m_name, "METHOD",
                          m_seg, m_doc, m_return, m_dispatch,
                          ",".join(m_calls), imports_str, m_start, m_end,
                          class_name,
                          1 if _has_vbstyle_markers(m_seg) else 0,
                          _hash(m_seg)))
                    units += 1
                    method_names.append(m_name)

                    for called in m_calls:
                        cur.execute("""
                            INSERT INTO code_edges
                                (from_class, from_method, to_class, to_method, edge_type, evidence_line)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (class_name, m_name, None, called, "CALLS", m_start))
                        edges += 1

            for m_name in method_names:
                cur.execute("""
                    INSERT INTO code_edges
                        (from_class, from_method, to_class, to_method, edge_type, evidence_line)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (class_name, None, class_name, m_name, "CONTAINS", class_start))
                edges += 1

    # --- top-level functions ---
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            f_name = node.name
            f_start = node.lineno
            f_end = getattr(node, "end_lineno", node.lineno)
            f_seg = _get_source_segment(source_lines, f_start, f_end)
            f_calls = _extract_calls(node)

            cur.execute("""
                INSERT INTO code_units
                    (file_path, file_hash, class_name, method_name, unit_type,
                     source_text, docstring, return_type, dispatch_key,
                     calls, imports, line_start, line_end,
                     parent_class, is_vbstyle, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (file_path, file_hash, None, f_name, "FUNCTION",
                  f_seg, ast.get_docstring(node), _get_return_type(node), None,
                  ",".join(f_calls), imports_str, f_start, f_end, None,
                  1 if _has_vbstyle_markers(f_seg) else 0,
                  _hash(f_seg)))
            units += 1

            for called in f_calls:
                cur.execute("""
                    INSERT INTO code_edges
                        (from_class, from_method, to_class, to_method, edge_type, evidence_line)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (None, f_name, None, called, "CALLS", f_start))
                edges += 1

    # --- main block ---
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.If):
            test = ast.dump(node.test)
            if "__name__" in test and "__main__" in test:
                m_start = node.lineno
                m_end = getattr(node, "end_lineno", node.lineno)
                m_seg = _get_source_segment(source_lines, m_start, m_end)
                cur.execute("""
                    INSERT INTO code_units
                        (file_path, file_hash, class_name, method_name, unit_type,
                         source_text, dispatch_key, imports, line_start, line_end,
                         is_vbstyle, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (file_path, file_hash, None, "__main__", "MAIN_BLOCK",
                      m_seg, None, imports_str, m_start, m_end,
                      1 if _has_vbstyle_markers(m_seg) else 0,
                      _hash(m_seg)))
                units += 1

    # --- resolve called_by (reverse edges) ---
    cur.execute("SELECT from_class, from_method, to_method FROM code_edges WHERE edge_type='CALLS'")
    reverse_map = {}
    for row in cur.fetchall():
        from_class = row["from_class"]
        from_method = row["from_method"]
        to_method = row["to_method"]
        key = to_method or ""
        caller = f"{from_class}.{from_method}" if from_class else from_method
        reverse_map.setdefault(key, set()).add(caller)

    for method_name, callers in reverse_map.items():
        cur.execute("UPDATE code_units SET called_by=? WHERE method_name=?",
                    (",".join(sorted(callers)), method_name))

    conn.commit()
    return units, edges, file_hash


def ingest_directory(conn, directory, pattern="*.py"):
    total_files = 0
    total_units = 0
    total_edges = 0
    failed = []

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        for fname in sorted(files):
            if not fname.endswith(".py"):
                continue
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, directory)
            try:
                u, e, h = ingest_file(conn, full_path, "")
                if h:
                    total_files += 1
                    total_units += u
                    total_edges += e
                    sys.stdout.write(f"  OK {rel_path}: {u} units, {e} edges\n")
                else:
                    failed.append(rel_path)
            except Exception as ex:
                sys.stderr.write(f"  FAIL {rel_path}: {ex}\n")
                failed.append(rel_path)

    return total_files, total_units, total_edges, failed


def show_status(conn):
    cur = conn.cursor()
    for table in ["code_files", "code_units", "code_edges"]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  {table}: {count} rows")
    cur.execute("SELECT unit_type, COUNT(*) FROM code_units GROUP BY unit_type ORDER BY 2 DESC")
    print("\n  Units by type:")
    for row in cur.fetchall():
        print(f"    {row[0]}: {row[1]}")
    cur.execute("SELECT edge_type, COUNT(*) FROM code_edges GROUP BY edge_type ORDER BY 2 DESC")
    print("\n  Edges by type:")
    for row in cur.fetchall():
        print(f"    {row[0]}: {row[1]}")
    cur.execute("SELECT file_path, class_count, method_count FROM code_files ORDER BY method_count DESC LIMIT 10")
    print("\n  Top 10 files by method count:")
    for row in cur.fetchall():
        print(f"    {row[0]}: {row[1]} classes, {row[2]} methods")


def main():
    parser = argparse.ArgumentParser(description="Stage 1: Ingest .py files into SQLite code_graph")
    parser.add_argument("directory", nargs="?", help="Directory to ingest")
    parser.add_argument("--db", default=DB_PATH, help="SQLite DB path")
    parser.add_argument("--status", action="store_true", help="Show DB stats and exit")
    args = parser.parse_args()

    conn = _connect(args.db)

    if args.status:
        show_status(conn)
        conn.close()
        return

    if not args.directory:
        parser.error("directory required (or use --status)")

    print(f"INGESTING: {args.directory}")
    print(f"DB: {args.db}")
    print()

    files, units, edges, failed = ingest_directory(conn, args.directory)

    print()
    print(f"DONE: {files} files, {units} units, {edges} edges")
    if failed:
        print(f"FAILED: {len(failed)} files")
        for f in failed:
            print(f"  {f}")

    conn.close()


if __name__ == "__main__":
    main()
