# [@GHOST]{[@file<Dom_Indexer.py>][@domain<Dom_Unified>][@role<indexer>][@auth<cascade>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<indexer>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{DomIndexer — in-RAM SQLite index of files, classes, methods, BCL stamps, edges, AI reasoning. Super fast queries.}
# [@CLASS]{DomIndexer}
# [@METHOD]{Run,index,index_dir,find_class,find_method,find_file,classes,methods,edges,bcl,reasoning,graph,stats}

"""
DomIndexer — in-RAM SQLite code index.

WHAT IT DOES:
  1. INDEX     — parse a file or directory with vbast, store results in in-RAM SQLite
  2. QUERY     — find classes, methods, files by name, pattern, or content
  3. BCL       — store and query BCL stamps (behavioral classification labels)
  4. EDGES     — store and query call/import/state edges (graph data)
  5. REASONING — store and query AI reasoning over code (understanding, intent, risk)
  6. GRAPH     — build adjacency lists from edges for graph traversal
  7. STATS     — index statistics (file count, class count, method count, etc.)

WHY IN-RAM:
  SQLite :memory: is super fast — no disk I/O.
  Index 1000 files in seconds, query in microseconds.
  Persist to disk only when you want to (export command).

USAGE:
  from Dom_Unified.Dom_Indexer import DomIndexer

  idx = DomIndexer()

  # Index a single file
  ok, data, err = idx.Run("index", {"file": "/path/to/Engine.py"})

  # Index an entire directory
  ok, data, err = idx.Run("index_dir", {"path": "/path/to/project"})

  # Find a class by name
  ok, data, err = idx.Run("find_class", {"name": "Config"})
  # data = [{"class_name": "Config", "file_path": "...", "methods": 12, ...}]

  # Find methods matching a pattern
  ok, data, err = idx.Run("find_method", {"pattern": "search%"})

  # Get all classes
  ok, data, err = idx.Run("classes", {})

  # Build a call graph
  ok, data, err = idx.Run("graph", {"type": "call"})

  # Add AI reasoning for a file
  ok, data, err = idx.Run("reasoning", {
      "file": "/path/to/Engine.py",
      "action": "add",
      "text": "This module handles search dispatch. High complexity in Run().",
      "reasoning_type": "understanding",
      "confidence": 0.85
  })

  # Query reasoning
  ok, data, err = idx.Run("reasoning", {"file": "/path/to/Engine.py", "action": "get"})

  # Export index to disk
  ok, data, err = idx.Run("export", {"path": "/tmp/index.db"})

  # Stats
  ok, data, err = idx.Run("stats", {})
"""

import os
import re
import ast
import sqlite3
import datetime
import hashlib
import json

try:
    from .UnifiedAst import parse, parse_dir
    HAS_VBAST = True
except Exception:
    HAS_VBAST = False

GHOST_RE = re.compile(r'\[@GHOST\]\{([^}]*)\}', re.IGNORECASE)
VBSTYLE_RE = re.compile(r'\[@VBSTYLE\]\{([^}]*)\}', re.IGNORECASE)
SUMMARY_RE = re.compile(r'\[@SUMMARY\]\{([^}]*)\}', re.IGNORECASE)
WCL_RE = re.compile(r'\[@WCL\]\{([^}]*)\}', re.IGNORECASE)
FILE_RE = re.compile(r'\[@file<([^>]*)>\]', re.IGNORECASE)
DOMAIN_RE = re.compile(r'\[@domain<([^>]*)>\]', re.IGNORECASE)
ROLE_RE = re.compile(r'\[@role<([^>]*)>\]', re.IGNORECASE)


class DomIndexer:
    """
    In-RAM SQLite code index — files, classes, methods, BCL, edges, reasoning.
    VBStyle compliant: Run() dispatch, Tuple3 returns, self.state dict.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "use_vbast": param.get("use_vbast", True) if param else True,
                "max_files": param.get("max_files", 10000) if param else 10000,
                "include_content": param.get("include_content", False) if param else False,
            },
            "db_path": ":memory:",
            "indexed_count": 0,
            "stats": {"files": 0, "classes": 0, "methods": 0, "edges": 0, "bcl_stamps": 0, "reasoning": 0, "errors": 0},
        }
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def Run(self, command, params=None):
        dispatch = {
            "index": self._cmd_index,
            "index_dir": self._cmd_index_dir,
            "index_incremental": self._cmd_index_incremental,
            "scan_file": self._cmd_index,
            "scan_dir": self._cmd_index_dir,
            "find_class": self._cmd_find_class,
            "find_method": self._cmd_find_method,
            "find_file": self._cmd_find_file,
            "find_function": self._cmd_find_function,
            "classes": self._cmd_classes,
            "methods": self._cmd_methods,
            "functions": self._cmd_functions,
            "edges": self._cmd_edges,
            "bcl": self._cmd_bcl,
            "reasoning": self._cmd_reasoning,
            "graph": self._cmd_graph,
            "suggest_moves": self._cmd_suggest_moves,
            "stats": self._cmd_stats,
            "export": self._cmd_export,
            "import_db": self._cmd_import_db,
            "clear": self._cmd_clear,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", f"Unknown: {command}", 0))
        return handler(params or {})

    def read_state(self, params=None):
        safe = {k: v for k, v in self.state.items() if k != "conn"}
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

    # ════════════════════════════════════════════
    # SCHEMA
    # ════════════════════════════════════════════

    def _init_schema(self):
        c = self.conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT,
                file_hash TEXT,
                file_size INTEGER,
                line_count INTEGER,
                domain TEXT,
                parsed_at TEXT,
                from_cache INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                class_name TEXT NOT NULL,
                base_classes TEXT,
                decorators TEXT,
                line_start INTEGER,
                line_end INTEGER,
                method_count INTEGER DEFAULT 0,
                docstring TEXT,
                FOREIGN KEY (file_id) REFERENCES files(id)
            );

            CREATE TABLE IF NOT EXISTS methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                class_name TEXT,
                method_name TEXT NOT NULL,
                signature TEXT,
                decorators TEXT,
                return_type TEXT,
                params TEXT,
                line_start INTEGER,
                line_end INTEGER,
                is_method INTEGER DEFAULT 0,
                docstring TEXT,
                FOREIGN KEY (file_id) REFERENCES files(id)
            );

            CREATE TABLE IF NOT EXISTS bcl_stamps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                unit_name TEXT NOT NULL,
                unit_type TEXT,
                stamp_hash TEXT,
                stamp_data TEXT,
                FOREIGN KEY (file_id) REFERENCES files(id)
            );

            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                line_number INTEGER,
                FOREIGN KEY (file_id) REFERENCES files(id)
            );

            CREATE TABLE IF NOT EXISTS functions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                function_name TEXT NOT NULL,
                signature TEXT,
                params TEXT,
                line_start INTEGER,
                line_end INTEGER,
                docstring TEXT,
                FOREIGN KEY (file_id) REFERENCES files(id)
            );

            CREATE TABLE IF NOT EXISTS reasoning (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER,
                class_name TEXT,
                method_name TEXT,
                reasoning_text TEXT NOT NULL,
                reasoning_type TEXT,
                confidence REAL,
                created_at TEXT,
                FOREIGN KEY (file_id) REFERENCES files(id)
            );

            CREATE INDEX IF NOT EXISTS idx_classes_name ON classes(class_name);
            CREATE INDEX IF NOT EXISTS idx_classes_file ON classes(file_id);
            CREATE INDEX IF NOT EXISTS idx_methods_name ON methods(method_name);
            CREATE INDEX IF NOT EXISTS idx_methods_class ON methods(class_name);
            CREATE INDEX IF NOT EXISTS idx_methods_file ON methods(file_id);
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target);
            CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type);
            CREATE INDEX IF NOT EXISTS idx_files_path ON files(file_path);
            CREATE INDEX IF NOT EXISTS idx_files_hash ON files(file_hash);
            CREATE INDEX IF NOT EXISTS idx_functions_name ON functions(function_name);
            CREATE INDEX IF NOT EXISTS idx_functions_file ON functions(file_id);
            CREATE INDEX IF NOT EXISTS idx_reasoning_file ON reasoning(file_id);
        """)
        self.conn.commit()

    def _get_or_create_file(self, file_path, file_hash, file_size, line_count, domain, from_cache):
        c = self.conn.cursor()
        c.execute("SELECT id FROM files WHERE file_path = ?", [file_path])
        row = c.fetchone()
        if row:
            return row["id"]
        c.execute(
            "INSERT INTO files (file_path, file_name, file_hash, file_size, line_count, domain, parsed_at, from_cache) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [file_path, os.path.basename(file_path), file_hash, file_size, line_count, domain, datetime.datetime.now().isoformat(), 1 if from_cache else 0]
        )
        self.conn.commit()
        return c.lastrowid

    # ════════════════════════════════════════════
    # INDEX — parse a single file and store results
    # ════════════════════════════════════════════

    def _parse_python_ast(self, filepath):
        """Fallback parser using Python ast module when vbast is not available."""
        try:
            with open(filepath, "r") as f:
                content = f.read()
        except Exception:
            return None
        classes = []
        methods = []
        functions = []
        edges = []
        imports = []
        bcl_stamps = []
        headers = {"domain": "", "role": "", "summary": "", "wcl": ""}
        ghost_match = GHOST_RE.search(content)
        if ghost_match:
            ghost_body = ghost_match.group(1)
            file_match = FILE_RE.search(ghost_body)
            if file_match:
                headers["file_tag"] = file_match.group(1)
            domain_match = DOMAIN_RE.search(ghost_body)
            if domain_match:
                headers["domain"] = domain_match.group(1)
        vbs_match = VBSTYLE_RE.search(content)
        if vbs_match:
            vbs_body = vbs_match.group(1)
            role_match = ROLE_RE.search(vbs_body)
            if role_match:
                headers["role"] = role_match.group(1)
        sum_match = SUMMARY_RE.search(content)
        if sum_match:
            headers["summary"] = sum_match.group(1).strip()
        wcl_match = WCL_RE.search(content)
        if wcl_match:
            headers["wcl"] = wcl_match.group(1).strip()
        try:
            tree = ast.parse(content, filename=filepath)
        except SyntaxError:
            return {"classes": [], "methods": [], "functions": [], "edges": [],
                    "imports": [], "bcl_stamps": [], "violations": [],
                    "headers": headers, "line_count": content.count("\n") + 1}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                cls_methods = []
                bases = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        bases.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        bases.append(base.attr)
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        cls_methods.append(item.name)
                        methods.append({
                            "name": item.name,
                            "class_name": node.name,
                            "signature": item.name + "(" + ", ".join(
                                [a.arg for a in item.args.args]) + ")",
                            "params": json.dumps([a.arg for a in item.args.args]),
                            "line_start": item.lineno,
                            "line_end": getattr(item, "end_lineno", item.lineno),
                            "docstring": ast.get_docstring(item) or "",
                            "decorators": [],
                            "return_type": "",
                        })
                        for child in ast.walk(item):
                            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                                edges.append({
                                    "source": node.name + "." + item.name,
                                    "target": child.func.id,
                                    "edge_type": "CALLS",
                                    "line": child.lineno,
                                })
                classes.append({
                    "name": node.name,
                    "base_classes": bases,
                    "decorators": [],
                    "line_start": node.lineno,
                    "line_end": getattr(node, "end_lineno", node.lineno),
                    "method_count": len(cls_methods),
                    "docstring": ast.get_docstring(node) or "",
                })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not hasattr(node, "_in_class"):
                if not any(isinstance(parent, ast.ClassDef) for parent in ast.walk(tree) if node in ast.walk(parent)):
                    functions.append({
                        "name": node.name,
                        "signature": node.name + "(" + ", ".join(
                            [a.arg for a in node.args.args]) + ")",
                        "params": json.dumps([a.arg for a in node.args.args]),
                        "line_start": node.lineno,
                        "line_end": getattr(node, "end_lineno", node.lineno),
                        "docstring": ast.get_docstring(node) or "",
                    })
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
                    edges.append({
                        "source": os.path.basename(filepath),
                        "target": alias.name,
                        "edge_type": "IMPORTS",
                        "line": node.lineno,
                    })
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
                    edges.append({
                        "source": os.path.basename(filepath),
                        "target": node.module,
                        "edge_type": "IMPORTS",
                        "line": node.lineno,
                    })
        if headers["summary"]:
            bcl_stamps.append({
                "unit_name": os.path.basename(filepath),
                "unit_type": "FILE",
                "stamp_hash": hashlib.sha256(headers["summary"].encode()).hexdigest()[:16],
                "stamp_data": json.dumps(headers),
            })
        return {
            "classes": classes,
            "methods": methods,
            "functions": functions,
            "edges": edges,
            "imports": imports,
            "bcl_stamps": bcl_stamps,
            "violations": [],
            "headers": headers,
            "line_count": content.count("\n") + 1,
            "from_cache": False,
        }

    def _cmd_index(self, params):
        filepath = self._p(params, "file")
        if not filepath or not os.path.isfile(filepath):
            return (0, None, ("ERR_FILE", f"File not found: {filepath}", 0))
        if HAS_VBAST:
            data = parse(filepath)
            if not data or "error" in data:
                data = self._parse_python_ast(filepath)
                if data is None:
                    return (0, None, ("ERR_PARSE", f"Parse failed: {filepath}", 0))
        else:
            data = self._parse_python_ast(filepath)
            if data is None:
                return (0, None, ("ERR_PARSE", f"Parse failed: {filepath}", 0))
        file_hash = self._hash_file(filepath)
        file_size = os.path.getsize(filepath)
        line_count = data.get("line_count", 0)
        headers = data.get("headers", {})
        domain = headers.get("domain", "") or os.path.basename(os.path.dirname(filepath))
        file_id = self._get_or_create_file(filepath, file_hash, file_size, line_count, domain, data.get("from_cache", False))
        self._delete_file_children(file_id)
        class_count = self._store_classes(file_id, data.get("classes", []))
        method_count = self._store_methods(file_id, data.get("methods", []))
        function_count = self._store_functions(file_id, data.get("functions", []))
        edge_count = self._store_edges(file_id, data.get("edges", []))
        bcl_count = self._store_bcl(file_id, data.get("bcl_stamps", []))
        self.state["indexed_count"] += 1
        self.state["stats"]["files"] = self._count("files")
        self.state["stats"]["classes"] = self._count("classes")
        self.state["stats"]["methods"] = self._count("methods")
        self.state["stats"]["edges"] = self._count("edges")
        self.state["stats"]["bcl_stamps"] = self._count("bcl_stamps")
        return (1, {
            "file": filepath,
            "file_id": file_id,
            "from_cache": data.get("from_cache", False),
            "classes": class_count,
            "methods": method_count,
            "functions": function_count,
            "edges": edge_count,
            "bcl_stamps": bcl_count,
            "violations": len(data.get("violations", [])),
        }, None)

    def _cmd_index_incremental(self, params):
        path = self._p(params, "path")
        if not path or not os.path.isdir(path):
            return (0, None, ("ERR_PATH", f"Invalid path: {path}", 0))
        import fnmatch
        py_files = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", ".git", "venv", "node_modules")]
            for fname in files:
                if fname.endswith(".py"):
                    py_files.append(os.path.join(root, fname))
        skipped = 0
        indexed = 0
        errors = 0
        total_classes = 0
        total_methods = 0
        total_edges = 0
        total_bcl = 0
        for pyfile in py_files:
            file_hash = self._hash_file(pyfile)
            c = self.conn.cursor()
            c.execute("SELECT id, file_hash FROM files WHERE file_path = ?", [pyfile])
            row = c.fetchone()
            if row and row["file_hash"] == file_hash:
                skipped += 1
                continue
            ok, data, err = self._cmd_index({"file": pyfile})
            if ok:
                indexed += 1
                total_classes += data["classes"]
                total_methods += data["methods"]
                total_edges += data["edges"]
                total_bcl += data["bcl_stamps"]
            else:
                errors += 1
        return (1, {
            "path": path,
            "files_found": len(py_files),
            "files_indexed": indexed,
            "files_skipped": skipped,
            "errors": errors,
            "total_classes": total_classes,
            "total_methods": total_methods,
            "total_edges": total_edges,
            "total_bcl_stamps": total_bcl,
        }, None)

    def _cmd_index_dir(self, params):
        path = self._p(params, "path")
        pattern = self._p(params, "pattern", "*.py")
        max_files = self._p(params, "max_files", self.state["config"]["max_files"])
        if not path or not os.path.isdir(path):
            return (0, None, ("ERR_PATH", f"Invalid path: {path}", 0))
        import fnmatch
        py_files = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", ".git", "venv", "node_modules")]
            for fname in files:
                if fnmatch.fnmatch(fname, pattern):
                    py_files.append(os.path.join(root, fname))
                    if len(py_files) >= max_files:
                        break
            if len(py_files) >= max_files:
                break
        indexed = 0
        errors = 0
        total_classes = 0
        total_methods = 0
        total_edges = 0
        total_bcl = 0
        for pyfile in py_files:
            ok, data, err = self._cmd_index({"file": pyfile})
            if ok:
                indexed += 1
                total_classes += data["classes"]
                total_methods += data["methods"]
                total_edges += data["edges"]
                total_bcl += data["bcl_stamps"]
            else:
                errors += 1
        return (1, {
            "path": path,
            "files_found": len(py_files),
            "files_indexed": indexed,
            "errors": errors,
            "total_classes": total_classes,
            "total_methods": total_methods,
            "total_edges": total_edges,
            "total_bcl_stamps": total_bcl,
        }, None)

    def _delete_file_children(self, file_id):
        c = self.conn.cursor()
        for table in ("classes", "methods", "functions", "edges", "bcl_stamps"):
            c.execute(f"DELETE FROM {table} WHERE file_id = ?", [file_id])
        self.conn.commit()

    def _store_functions(self, file_id, functions):
        c = self.conn.cursor()
        count = 0
        for fn in functions:
            params = json.dumps(fn.get("params", [])) if isinstance(fn.get("params"), list) else str(fn.get("params", ""))
            c.execute(
                "INSERT INTO functions (file_id, function_name, signature, params, line_start, line_end, docstring) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [file_id, fn.get("name", ""), fn.get("signature", ""), params, fn.get("line_start", 0), fn.get("line_end", 0), fn.get("docstring", "")]
            )
            count += 1
        self.conn.commit()
        return count

    def _store_classes(self, file_id, classes):
        c = self.conn.cursor()
        count = 0
        for cls in classes:
            base = ",".join(cls.get("base_classes", [])) if isinstance(cls.get("base_classes"), list) else str(cls.get("base_classes", ""))
            decorators = ",".join(cls.get("decorators", [])) if isinstance(cls.get("decorators"), list) else str(cls.get("decorators", ""))
            c.execute(
                "INSERT INTO classes (file_id, class_name, base_classes, decorators, line_start, line_end, method_count, docstring) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [file_id, cls.get("name", ""), base, decorators, cls.get("line_start", 0), cls.get("line_end", 0), cls.get("method_count", 0), cls.get("docstring", "")]
            )
            count += 1
        self.conn.commit()
        return count

    def _store_methods(self, file_id, methods):
        c = self.conn.cursor()
        count = 0
        for m in methods:
            params = json.dumps(m.get("params", [])) if isinstance(m.get("params"), list) else str(m.get("params", ""))
            decorators = ",".join(m.get("decorators", [])) if isinstance(m.get("decorators"), list) else str(m.get("decorators", ""))
            is_method = 1 if m.get("class_name") else 0
            c.execute(
                "INSERT INTO methods (file_id, class_name, method_name, signature, decorators, return_type, params, line_start, line_end, is_method, docstring) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [file_id, m.get("class_name", ""), m.get("name", ""), m.get("signature", ""), decorators, m.get("return_type", ""), params, m.get("line_start", 0), m.get("line_end", 0), is_method, m.get("docstring", "")]
            )
            count += 1
        self.conn.commit()
        return count

    def _store_edges(self, file_id, edges):
        c = self.conn.cursor()
        count = 0
        EDGE_ALIASES = {"CALL": "CALLS", "IMPORT": "IMPORTS", "CONTAIN": "CONTAINS",
                         "INHERIT": "INHERITS", "REFERENCE": "REFERENCES"}
        for e in edges:
            if isinstance(e, dict):
                source = e.get("source", "")
                target = e.get("target", "")
                raw_type = e.get("edge_type", e.get("type", "CALLS"))
                line = e.get("line_number", e.get("line", 0))
            elif isinstance(e, (list, tuple)) and len(e) >= 3:
                source, target, raw_type = e[0], e[1], e[2]
                line = e[3] if len(e) > 3 else 0
            else:
                continue
            edge_type = EDGE_ALIASES.get(raw_type.upper(), raw_type.upper())
            c.execute(
                "INSERT INTO edges (file_id, source, target, edge_type, line_number) VALUES (?, ?, ?, ?, ?)",
                [file_id, source, target, edge_type, line]
            )
            count += 1
        self.conn.commit()
        return count

    def _store_bcl(self, file_id, bcl_stamps):
        c = self.conn.cursor()
        count = 0
        for stamp in bcl_stamps:
            if isinstance(stamp, dict):
                unit_name = stamp.get("unit_name", stamp.get("name", ""))
                unit_type = stamp.get("unit_type", stamp.get("type", ""))
                stamp_hash = stamp.get("stamp_hash", stamp.get("hash", ""))
                stamp_data = json.dumps(stamp) if not isinstance(stamp.get("stamp_data"), str) else stamp.get("stamp_data", "")
            elif isinstance(stamp, (list, tuple)):
                unit_name = stamp[0] if len(stamp) > 0 else ""
                unit_type = stamp[1] if len(stamp) > 1 else ""
                stamp_hash = stamp[2] if len(stamp) > 2 else ""
                stamp_data = stamp[3] if len(stamp) > 3 else ""
            else:
                continue
            c.execute(
                "INSERT INTO bcl_stamps (file_id, unit_name, unit_type, stamp_hash, stamp_data) VALUES (?, ?, ?, ?, ?)",
                [file_id, unit_name, unit_type, stamp_hash, stamp_data]
            )
            count += 1
        self.conn.commit()
        return count

    # ════════════════════════════════════════════
    # QUERY — find classes, methods, files
    # ════════════════════════════════════════════

    def _cmd_find_class(self, params):
        name = self._p(params, "name")
        pattern = self._p(params, "pattern")
        c = self.conn.cursor()
        if name:
            c.execute("""
                SELECT c.*, f.file_path, f.file_name, f.domain
                FROM classes c JOIN files f ON c.file_id = f.id
                WHERE c.class_name = ?
                ORDER BY f.file_path
            """, [name])
        elif pattern:
            c.execute("""
                SELECT c.*, f.file_path, f.file_name, f.domain
                FROM classes c JOIN files f ON c.file_id = f.id
                WHERE c.class_name LIKE ?
                ORDER BY f.file_path
            """, [pattern])
        else:
            return (0, None, ("ERR_PARAMS", "name or pattern required", 0))
        rows = [dict(r) for r in c.fetchall()]
        return (1, {"count": len(rows), "classes": rows}, None)

    def _cmd_find_method(self, params):
        name = self._p(params, "name")
        pattern = self._p(params, "pattern")
        class_name = self._p(params, "class_name")
        c = self.conn.cursor()
        if name:
            c.execute("""
                SELECT m.*, f.file_path, f.file_name, f.domain
                FROM methods m JOIN files f ON m.file_id = f.id
                WHERE m.method_name = ?
                ORDER BY f.file_path
            """, [name])
        elif pattern:
            sql = "SELECT m.*, f.file_path, f.file_name, f.domain FROM methods m JOIN files f ON m.file_id = f.id WHERE m.method_name LIKE ?"
            args = [pattern]
            if class_name:
                sql += " AND m.class_name = ?"
                args.append(class_name)
            sql += " ORDER BY f.file_path"
            c.execute(sql, args)
        elif class_name:
            c.execute("""
                SELECT m.*, f.file_path, f.file_name, f.domain
                FROM methods m JOIN files f ON m.file_id = f.id
                WHERE m.class_name = ?
                ORDER BY m.method_name
            """, [class_name])
        else:
            return (0, None, ("ERR_PARAMS", "name, pattern, or class_name required", 0))
        rows = [dict(r) for r in c.fetchall()]
        return (1, {"count": len(rows), "methods": rows}, None)

    def _cmd_find_file(self, params):
        name = self._p(params, "name")
        path = self._p(params, "path")
        pattern = self._p(params, "pattern")
        c = self.conn.cursor()
        if path:
            c.execute("SELECT * FROM files WHERE file_path = ?", [path])
        elif name:
            c.execute("SELECT * FROM files WHERE file_name = ?", [name])
        elif pattern:
            c.execute("SELECT * FROM files WHERE file_path LIKE ? OR file_name LIKE ?", [pattern, pattern])
        else:
            return (0, None, ("ERR_PARAMS", "name, path, or pattern required", 0))
        rows = [dict(r) for r in c.fetchall()]
        return (1, {"count": len(rows), "files": rows}, None)

    def _cmd_find_function(self, params):
        name = self._p(params, "name")
        pattern = self._p(params, "pattern")
        c = self.conn.cursor()
        if name:
            c.execute("""
                SELECT fn.*, f.file_path, f.file_name, f.domain
                FROM functions fn JOIN files f ON fn.file_id = f.id
                WHERE fn.function_name = ?
                ORDER BY f.file_path
            """, [name])
        elif pattern:
            c.execute("""
                SELECT fn.*, f.file_path, f.file_name, f.domain
                FROM functions fn JOIN files f ON fn.file_id = f.id
                WHERE fn.function_name LIKE ?
                ORDER BY f.file_path
            """, [pattern])
        else:
            return (0, None, ("ERR_PARAMS", "name or pattern required", 0))
        rows = [dict(r) for r in c.fetchall()]
        return (1, {"count": len(rows), "functions": rows}, None)

    def _cmd_functions(self, params):
        limit = self._p(params, "limit", 1000)
        c = self.conn.cursor()
        c.execute("""
            SELECT fn.function_name, fn.signature, fn.line_start,
                   f.file_path, f.file_name, f.domain
            FROM functions fn JOIN files f ON fn.file_id = f.id
            ORDER BY fn.function_name LIMIT ?
        """, [limit])
        rows = [dict(r) for r in c.fetchall()]
        return (1, {"count": len(rows), "functions": rows}, None)

    def _cmd_classes(self, params):
        limit = self._p(params, "limit", 1000)
        c = self.conn.cursor()
        c.execute("""
            SELECT c.class_name, c.method_count, c.line_start, c.line_end,
                   f.file_path, f.file_name, f.domain
            FROM classes c JOIN files f ON c.file_id = f.id
            ORDER BY c.class_name LIMIT ?
        """, [limit])
        rows = [dict(r) for r in c.fetchall()]
        return (1, {"count": len(rows), "classes": rows}, None)

    def _cmd_methods(self, params):
        limit = self._p(params, "limit", 1000)
        class_name = self._p(params, "class_name")
        c = self.conn.cursor()
        if class_name:
            c.execute("""
                SELECT m.method_name, m.class_name, m.signature, m.return_type, m.line_start,
                       f.file_path, f.file_name
                FROM methods m JOIN files f ON m.file_id = f.id
                WHERE m.class_name = ?
                ORDER BY m.method_name LIMIT ?
            """, [class_name, limit])
        else:
            c.execute("""
                SELECT m.method_name, m.class_name, m.signature, m.return_type, m.line_start,
                       f.file_path, f.file_name
                FROM methods m JOIN files f ON m.file_id = f.id
                ORDER BY m.class_name, m.method_name LIMIT ?
            """, [limit])
        rows = [dict(r) for r in c.fetchall()]
        return (1, {"count": len(rows), "methods": rows}, None)

    def _cmd_edges(self, params):
        edge_type = self._p(params, "type")
        source = self._p(params, "source")
        target = self._p(params, "target")
        limit = self._p(params, "limit", 1000)
        c = self.conn.cursor()
        sql = "SELECT e.*, f.file_path FROM edges e JOIN files f ON e.file_id = f.id WHERE 1=1"
        args = []
        if edge_type:
            sql += " AND e.edge_type = ?"
            args.append(edge_type)
        if source:
            sql += " AND e.source = ?"
            args.append(source)
        if target:
            sql += " AND e.target = ?"
            args.append(target)
        sql += " LIMIT ?"
        args.append(limit)
        c.execute(sql, args)
        rows = [dict(r) for r in c.fetchall()]
        return (1, {"count": len(rows), "edges": rows}, None)

    def _cmd_bcl(self, params):
        unit_name = self._p(params, "unit_name")
        file_path = self._p(params, "file")
        limit = self._p(params, "limit", 1000)
        c = self.conn.cursor()
        sql = "SELECT b.*, f.file_path, f.file_name FROM bcl_stamps b JOIN files f ON b.file_id = f.id WHERE 1=1"
        args = []
        if unit_name:
            sql += " AND b.unit_name = ?"
            args.append(unit_name)
        if file_path:
            sql += " AND f.file_path = ?"
            args.append(file_path)
        sql += " LIMIT ?"
        args.append(limit)
        c.execute(sql, args)
        rows = [dict(r) for r in c.fetchall()]
        return (1, {"count": len(rows), "bcl_stamps": rows}, None)

    # ════════════════════════════════════════════
    # REASONING — AI understanding of code
    # ════════════════════════════════════════════

    def _cmd_reasoning(self, params):
        action = self._p(params, "action", "get")
        filepath = self._p(params, "file")
        if action == "add":
            text = self._p(params, "text")
            if not text:
                return (0, None, ("ERR_TEXT", "text required for add", 0))
            reasoning_type = self._p(params, "reasoning_type", "understanding")
            confidence = self._p(params, "confidence", 0.5)
            class_name = self._p(params, "class_name", "")
            method_name = self._p(params, "method_name", "")
            file_id = None
            if filepath:
                c = self.conn.cursor()
                c.execute("SELECT id FROM files WHERE file_path = ?", [filepath])
                row = c.fetchone()
                if row:
                    file_id = row["id"]
            c = self.conn.cursor()
            c.execute(
                "INSERT INTO reasoning (file_id, class_name, method_name, reasoning_text, reasoning_type, confidence, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [file_id, class_name, method_name, text, reasoning_type, confidence, datetime.datetime.now().isoformat()]
            )
            self.conn.commit()
            self.state["stats"]["reasoning"] = self._count("reasoning")
            return (1, {"added": True, "id": c.lastrowid, "file": filepath, "type": reasoning_type, "confidence": confidence}, None)
        elif action == "get":
            c = self.conn.cursor()
            if filepath:
                c.execute("""
                    SELECT r.*, f.file_path, f.file_name
                    FROM reasoning r LEFT JOIN files f ON r.file_id = f.id
                    WHERE f.file_path = ?
                    ORDER BY r.created_at DESC
                """, [filepath])
            else:
                c.execute("""
                    SELECT r.*, f.file_path, f.file_name
                    FROM reasoning r LEFT JOIN files f ON r.file_id = f.id
                    ORDER BY r.created_at DESC
                """)
            rows = [dict(r) for r in c.fetchall()]
            return (1, {"count": len(rows), "reasoning": rows}, None)
        elif action == "search":
            query = self._p(params, "query", "")
            if not query:
                return (0, None, ("ERR_QUERY", "query required for search", 0))
            c = self.conn.cursor()
            c.execute("""
                SELECT r.*, f.file_path, f.file_name
                FROM reasoning r LEFT JOIN files f ON r.file_id = f.id
                WHERE r.reasoning_text LIKE ?
                ORDER BY r.confidence DESC
            """, [f"%{query}%"])
            rows = [dict(r) for r in c.fetchall()]
            return (1, {"count": len(rows), "reasoning": rows}, None)
        else:
            return (0, None, ("ERR_ACTION", f"Unknown action: {action}", 0))

    # ════════════════════════════════════════════
    # GRAPH — build adjacency lists from edges
    # ════════════════════════════════════════════

    def _cmd_graph(self, params):
        graph_type = self._p(params, "type", "CALL").upper()
        direction = self._p(params, "direction", "forward")
        c = self.conn.cursor()
        c.execute("SELECT DISTINCT source, target FROM edges WHERE edge_type = ?", [graph_type])
        adjacency = {}
        for row in c.fetchall():
            src = row["source"]
            tgt = row["target"]
            if direction == "forward":
                adjacency.setdefault(src, []).append(tgt)
            elif direction == "reverse":
                adjacency.setdefault(tgt, []).append(src)
            else:
                adjacency.setdefault(src, []).append(tgt)
                adjacency.setdefault(tgt, []).append(src)
        node_count = len(adjacency)
        edge_count = sum(len(v) for v in adjacency.values())
        return (1, {
            "type": graph_type,
            "direction": direction,
            "nodes": node_count,
            "edges": edge_count,
            "adjacency": adjacency,
        }, None)

    # ════════════════════════════════════════════
    # SUGGEST MOVES — migration analysis
    # ════════════════════════════════════════════

    def _cmd_suggest_moves(self, params):
        threshold = self._p(params, "threshold", 0.5)
        c = self.conn.cursor()
        suggestions = []
        c.execute("SELECT id, file_path, file_name, domain FROM files")
        all_files = c.fetchall()
        all_domains = set(row["domain"] for row in all_files if row["domain"] and row["domain"] != ".")
        for row in all_files:
            file_path = row["file_path"]
            file_name = row["file_name"]
            current_domain = row["domain"]
            actual_dir = os.path.basename(os.path.dirname(file_path))
            if actual_dir == "." or not current_domain:
                continue
            c.execute(
                "SELECT target FROM edges WHERE file_id = ? AND edge_type = 'IMPORTS'",
                [row["id"]]
            )
            imports = [r["target"] for r in c.fetchall()]
            import_domains = {}
            for imp in imports:
                parts = imp.replace("/", ".").split(".")
                for part in parts:
                    if part in all_domains:
                        import_domains.setdefault(part, 0)
                        import_domains[part] += 1
                        break
            top_import_domain = ""
            top_import_count = 0
            if import_domains:
                top_import_domain = max(import_domains, key=import_domains.get)
                top_import_count = import_domains[top_import_domain]
            total_imports = len(imports)
            coupling_ratio = top_import_count / total_imports if total_imports > 0 else 0
            c2 = self.conn.cursor()
            c2.execute(
                "SELECT DISTINCT f.file_path FROM edges e JOIN files f ON e.file_id = f.id WHERE e.edge_type = 'IMPORTS' AND e.target LIKE ?",
                ["%" + file_name.replace(".py", "") + "%"]
            )
            reverse_deps = [r["file_path"] for r in c2.fetchall() if r["file_path"] != file_path]
            reverse_dep_count = len(reverse_deps)
            c2.execute(
                "SELECT class_name FROM classes WHERE file_id = ?",
                [row["id"]]
            )
            class_names = [r["class_name"] for r in c2.fetchall()]
            class_domain_hints = []
            for cn in class_names:
                for domain in all_domains:
                    clean_domain = domain.replace("_", "").replace(" ", "").lower()
                    if clean_domain and clean_domain in cn.lower() and domain != current_domain:
                        class_domain_hints.append((cn, domain))
            suggested_domain = current_domain
            reason = ""
            if top_import_domain and top_import_domain != current_domain and coupling_ratio >= threshold:
                suggested_domain = top_import_domain
                reason = "imports %d/%d (%.0f%%) from %s" % (top_import_count, total_imports, coupling_ratio * 100, top_import_domain)
            elif class_domain_hints:
                suggested_domain = class_domain_hints[0][1]
                reason = "class '%s' name matches domain '%s'" % (class_domain_hints[0][0], class_domain_hints[0][1])
            if suggested_domain == current_domain:
                continue
            suggestions.append({
                "file": file_path,
                "file_name": file_name,
                "current_folder": current_domain,
                "suggested_domain": suggested_domain,
                "reason": reason,
                "top_import_domain": top_import_domain,
                "coupling_ratio": round(coupling_ratio, 2),
                "total_imports": total_imports,
                "reverse_dep_count": reverse_dep_count,
                "reverse_deps": reverse_deps[:10],
                "class_hints": class_domain_hints[:5],
                "severity": "HIGH" if reverse_dep_count > 10 else ("MEDIUM" if reverse_dep_count > 3 else "LOW"),
            })
        suggestions.sort(key=lambda s: (s["severity"], -s["reverse_dep_count"]))
        return (1, {
            "count": len(suggestions),
            "threshold": threshold,
            "suggestions": suggestions,
        }, None)

    # ════════════════════════════════════════════
    # STATS / EXPORT / IMPORT / CLEAR
    # ════════════════════════════════════════════

    def _cmd_stats(self, params):
        c = self.conn.cursor()
        stats = {}
        for table in ("files", "classes", "methods", "functions", "edges", "bcl_stamps", "reasoning"):
            c.execute(f"SELECT COUNT(*) as cnt FROM {table}")
            stats[table] = c.fetchone()["cnt"]
        c.execute("SELECT COUNT(DISTINCT domain) as cnt FROM files")
        stats["domains"] = c.fetchone()["cnt"]
        c.execute("SELECT domain, COUNT(*) as cnt FROM files GROUP BY domain ORDER BY cnt DESC LIMIT 10")
        stats["by_domain"] = [dict(r) for r in c.fetchall()]
        self.state["stats"] = {k: stats[k] for k in ("files", "classes", "methods", "edges", "bcl_stamps", "reasoning")}
        return (1, stats, None)

    def _cmd_export(self, params):
        dest_path = self._p(params, "path")
        if not dest_path:
            return (0, None, ("ERR_PATH", "path required", 0))
        try:
            backup = sqlite3.connect(dest_path)
            self.conn.backup(backup)
            backup.close()
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_EXPORT", str(e), 0))
        return (1, {"exported": True, "path": dest_path, "size": os.path.getsize(dest_path)}, None)

    def _cmd_import_db(self, params):
        src_path = self._p(params, "path")
        if not src_path or not os.path.isfile(src_path):
            return (0, None, ("ERR_PATH", f"File not found: {src_path}", 0))
        try:
            source = sqlite3.connect(src_path)
            source.row_factory = sqlite3.Row
            self.conn.execute("DELETE FROM files")
            self.conn.execute("DELETE FROM classes")
            self.conn.execute("DELETE FROM methods")
            self.conn.execute("DELETE FROM functions")
            self.conn.execute("DELETE FROM edges")
            self.conn.execute("DELETE FROM bcl_stamps")
            self.conn.execute("DELETE FROM reasoning")
            for table in ("files", "classes", "methods", "functions", "edges", "bcl_stamps", "reasoning"):
                c = source.cursor()
                c.execute(f"SELECT * FROM {table}")
                rows = c.fetchall()
                if rows:
                    cols = rows[0].keys()
                    placeholders = ", ".join(["?"] * len(cols))
                    col_names = ", ".join(cols)
                    for row in rows:
                        self.conn.execute(f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})", list(row))
            self.conn.commit()
            source.close()
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_IMPORT", str(e), 0))
        return (1, {"imported": True, "path": src_path}, None)

    def _cmd_clear(self, params):
        for table in ("files", "classes", "methods", "functions", "edges", "bcl_stamps", "reasoning"):
            self.conn.execute(f"DELETE FROM {table}")
        self.conn.commit()
        self.state["indexed_count"] = 0
        return (1, {"cleared": True}, None)

    # ════════════════════════════════════════════
    # HELPERS
    # ════════════════════════════════════════════

    def _hash_file(self, filepath):
        try:
            h = hashlib.sha256()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return ""

    def _count(self, table):
        c = self.conn.cursor()
        c.execute(f"SELECT COUNT(*) as cnt FROM {table}")
        return c.fetchone()["cnt"]
