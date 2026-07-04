# [@GHOST]{[@file<indexer.py>][@domain<utility>][@role<file_indexer>][@auth<cascade>][@date<2026-07-02>][@ver<2.0.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<file_indexer>][@return<tuple3>][@orch<VbsMain>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{FileIO + FileIndexer — disk I/O class and all-file-type indexer with SQLite storage. Replaces old Indexer + FileIndexer.py.}
# [@WCL]{[@self_contained<true>][@input<filesystem>][@output<sqlite_db>][@commands<scan_dir|scan_file|get_index|get_stats|query_domain|query_class|query_method|query_category|query_duplicates|query_large_files>]}
# [@CLASS]{FileIO,FileIndexer}
# [@METHOD]{Run,walk,read_file,file_stat,hash_file,exists,scan_dir,scan_file,extract_disk_metadata,extract_code_metadata,extract_text_metadata,create_schema,insert_batch,query_domain,query_class,query_method,query_category,query_duplicates,query_large_files,read_state,set_config}

"""
indexer.py — FileIO + FileIndexer
=================================
Two classes:
  1. FileIO       — pure disk I/O (walk, read, stat, hash, exists)
  2. FileIndexer  — uses FileIO, extracts all metadata, stores in SQLite

FileIO has no SQLite, no reporting. Just file system operations.
FileIndexer scans ALL file types (not just .py), extracts disk metadata
(size, hash, dates), code metadata (BCL headers, AST classes/methods for
.py, regex functions for C/MM), and text metadata (line/word counts).
Stores everything in SQLite with proper indexes.

Usage:
    from core.utility.indexer import FileIO, FileIndexer

    # FileIO — low-level disk operations
    io = FileIO()
    ok, files, err = io.Run("walk", {"path": "/some/dir"})
    ok, content, err = io.Run("read_file", {"path": "/some/file.py"})
    ok, stat, err = io.Run("file_stat", {"path": "/some/file.py"})
    ok, md5, err = io.Run("hash_file", {"path": "/some/file.py"})

    # FileIndexer — full indexing with SQLite storage
    idx = FileIndexer()
    ok, stats, err = idx.Run("scan_dir", {"path": "/some/dir", "db_path": "/tmp/index.db"})
    ok, results, err = idx.Run("query_category", {"db_path": "/tmp/index.db", "category": "Python"})
    ok, results, err = idx.Run("query_duplicates", {"db_path": "/tmp/index.db"})
    ok, results, err = idx.Run("query_large_files", {"db_path": "/tmp/index.db", "n": 20})
"""

import os
import re
import ast
import json
import hashlib
import sqlite3
import datetime

from . import Config


# ================================================================
# FileIO — Pure disk I/O operations
# ================================================================

class FileIO:
    """Pure file system I/O — walk, read, stat, hash, exists.

    No SQLite, no reporting, no indexing logic.
    Just disk operations wrapped in VBStyle Tuple3.

    self.state:
        state['root']: last walked root path
        state['files']: last walk result (list of paths)
        state['stats']: operation counters
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "root": None,
            "files": [],
            "stats": {"walks": 0, "reads": 0, "hashes": 0, "stats": 0, "errors": 0},
        }

    def Run(self, command, params=None):
        dispatch = {
            "walk": self.walk,
            "read_file": self.read_file,
            "file_stat": self.file_stat,
            "hash_file": self.hash_file,
            "exists": self.exists,
            "read_state": self.read_state,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", command, 0))
        return handler(params or {})

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def walk(self, params):
        path = self._p(params, "path")
        skip_dirs = self._p(params, "skip_dirs", Config.INDEXER_SKIP_DIRS)
        extensions = self._p(params, "extensions")
        if not path or not os.path.isdir(path):
            return (0, None, ("ERR_PATH", f"Invalid path: {path}", 0))
        results = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for fname in sorted(files):
                if fname == ".DS_Store":
                    continue
                if extensions:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in extensions:
                        continue
                fpath = os.path.join(root, fname)
                results.append(fpath)
        self.state["root"] = path
        self.state["files"] = results
        self.state["stats"]["walks"] += 1
        return (1, {"path": path, "files": results, "count": len(results)}, None)

    def read_file(self, params):
        path = self._p(params, "path")
        mode = self._p(params, "mode", "r")
        if not path or not os.path.isfile(path):
            return (0, None, ("ERR_FILE", f"File not found: {path}", 0))
        try:
            if mode == "rb":
                with open(path, "rb") as f:
                    content = f.read()
            else:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            self.state["stats"]["reads"] += 1
            return (1, content, None)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_READ", str(e), 0))

    def file_stat(self, params):
        path = self._p(params, "path")
        if not path or not os.path.exists(path):
            return (0, None, ("ERR_FILE", f"Path not found: {path}", 0))
        try:
            stat = os.stat(path)
            self.state["stats"]["stats"] += 1
            return (1, {
                "path": path,
                "size": stat.st_size,
                "created": datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "is_dir": os.path.isdir(path),
                "is_file": os.path.isfile(path),
                "mode": stat.st_mode,
            }, None)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_STAT", str(e), 0))

    def hash_file(self, params):
        path = self._p(params, "path")
        algo = self._p(params, "algo", "md5")
        threshold = self._p(params, "threshold", Config.INDEXER_HASH_THRESHOLD)
        if not path or not os.path.isfile(path):
            return (0, None, ("ERR_FILE", f"File not found: {path}", 0))
        try:
            size = os.path.getsize(path)
            if size > threshold:
                return (1, "SKIP_LARGE", None)
            h = hashlib.new(algo)
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    h.update(chunk)
            self.state["stats"]["hashes"] += 1
            return (1, h.hexdigest(), None)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_HASH", str(e), 0))

    def exists(self, params):
        path = self._p(params, "path")
        if not path:
            return (0, None, ("ERR_PATH", "path required", 0))
        return (1, os.path.exists(path), None)


# ================================================================
# FileIndexer — Extraction + SQLite storage
# ================================================================

class FileIndexer:
    """All-file-type indexer with SQLite storage.

    Uses FileIO for disk operations. Extracts:
      - Disk metadata: size, ext, category, dates, hash, depth, parent
      - Code metadata: BCL headers, AST classes/methods (.py), regex functions (.c/.mm)
      - Text metadata: line count, word count

    Stores in SQLite. Query commands return Tuple3.

    self.state:
        state['db_path']: last used DB path
        state['stats']: scan statistics
        state['io']: FileIO instance
    """

    GHOST_RE = re.compile(r'\[@GHOST\]\{([^}]*)\}', re.IGNORECASE)
    VBSTYLE_RE = re.compile(r'\[@VBSTYLE\]\{([^}]*)\}', re.IGNORECASE)
    SUMMARY_RE = re.compile(r'\[@SUMMARY\]\{([^}]*)\}', re.IGNORECASE)
    WCL_RE = re.compile(r'\[@WCL\]\{([^}]*)\}', re.IGNORECASE)
    FILE_RE = re.compile(r'\[@file<([^>]*)>\]', re.IGNORECASE)
    DOMAIN_RE = re.compile(r'\[@domain<([^>]*)>\]', re.IGNORECASE)
    ROLE_RE = re.compile(r'\[@role<([^>]*)>\]', re.IGNORECASE)

    C_FUNC_RE = re.compile(r'^(?:static\s+)?(?:void|int|float|double|char|unsigned|size_t|bool|id|NS[A-Za-z]+\*?)\s+(\w+)\s*\(')

    CATEGORY_MAP = {
        ".py": "Python", ".c": "C", ".h": "CHeader", ".cpp": "CPP", ".hpp": "CPPHeader",
        ".mm": "ObjCpp", ".m": "ObjC", ".metal": "Metal", ".swift": "Swift",
        ".sh": "Shell", ".sql": "SQL", ".md": "Markdown", ".rmd": "RMarkdown",
        ".json": "JSON", ".yaml": "YAML", ".yml": "YAML", ".xml": "XML",
        ".html": "HTML", ".css": "CSS", ".js": "JavaScript", ".ts": "TypeScript",
        ".db": "SQLite", ".sqlite": "SQLite", ".sqlite3": "SQLite",
        ".bak": "Backup", ".zip": "Archive", ".gz": "Archive", ".tar": "Archive",
        ".bin": "Binary", ".so": "Library", ".dylib": "Library", ".a": "Library",
        ".o": "ObjectFile", ".txt": "Text", ".csv": "CSV",
        ".conf": "Config", ".cfg": "Config", ".plist": "Plist",
        ".png": "Image", ".jpg": "Image", ".jpeg": "Image", ".svg": "Image", ".icns": "Image",
        ".pdf": "PDF", ".woff": "Font", ".woff2": "Font", ".ttf": "Font",
    }

    CODE_EXTENSIONS = {".py", ".c", ".h", ".cpp", ".hpp", ".mm", ".m", ".metal", ".swift"}
    TEXT_EXTENSIONS = {".py", ".c", ".h", ".cpp", ".hpp", ".mm", ".m", ".metal", ".swift",
                       ".sh", ".sql", ".md", ".txt", ".json", ".yaml", ".yml", ".xml",
                       ".html", ".css", ".js", ".ts", ".csv", ".conf", ".cfg", ".rmd"}

    DUP_MARKERS = ("_original", "_backup", "_old", "_bak", ".bak", "_v1", "_1.")

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "db_path": None,
            "stats": {"files": 0, "code_files": 0, "text_files": 0, "errors": 0},
            "io": FileIO(),
        }

    def Run(self, command, params=None):
        dispatch = {
            "scan_dir": self.scan_dir,
            "scan_file": self.scan_file,
            "get_index": self.get_index,
            "get_stats": self.get_stats,
            "query_domain": self.query_domain,
            "query_class": self.query_class,
            "query_method": self.query_method,
            "query_category": self.query_category,
            "query_duplicates": self.query_duplicates,
            "query_large_files": self.query_large_files,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", command, 0))
        return handler(params or {})

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        state_copy = dict(self.state)
        state_copy["io"] = self.state["io"].read_state()[1]
        return (1, state_copy, None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state:
                self.state[key] = val
        return (1, dict(self.state), None)

    # ================================================================
    # SCANNING
    # ================================================================

    def scan_dir(self, params):
        path = self._p(params, "path")
        db_path = self._p(params, "db_path")
        if not path or not os.path.isdir(path):
            return (0, None, ("ERR_PATH", f"Invalid path: {path}", 0))
        if not db_path:
            return (0, None, ("ERR_DB", "db_path required", 0))
        self.state["db_path"] = db_path
        self._create_schema(db_path)
        ok, walk_data, err = self.state["io"].Run("walk", {"path": path})
        if not ok:
            return (ok, None, err)
        files = walk_data["files"]
        conn = sqlite3.connect(db_path)
        batch = []
        file_count = 0
        code_count = 0
        text_count = 0
        for fpath in files:
            entry = self._extract_all(fpath, path)
            if entry:
                batch.append(entry)
                file_count += 1
                if entry.get("classes_json") or entry.get("functions_json"):
                    code_count += 1
                if entry.get("line_count") is not None:
                    text_count += 1
                if len(batch) >= 500:
                    self._insert_batch(conn, batch)
                    batch.clear()
        if batch:
            self._insert_batch(conn, batch)
        conn.commit()
        conn.close()
        self.state["stats"] = {"files": file_count, "code_files": code_count, "text_files": text_count, "errors": 0}
        return (1, {"path": path, "db_path": db_path, "files": file_count, "code_files": code_count, "text_files": text_count}, None)

    def scan_file(self, params):
        path = self._p(params, "path")
        db_path = self._p(params, "db_path", self.state["db_path"])
        root = self._p(params, "root", os.path.dirname(path))
        if not path or not os.path.isfile(path):
            return (0, None, ("ERR_FILE", f"File not found: {path}", 0))
        if not db_path:
            return (0, None, ("ERR_DB", "db_path required", 0))
        self._create_schema(db_path)
        entry = self._extract_all(path, root)
        if not entry:
            return (0, None, ("ERR_EXTRACT", f"Failed to extract: {path}", 0))
        conn = sqlite3.connect(db_path)
        self._insert_batch(conn, [entry])
        conn.commit()
        conn.close()
        return (1, entry, None)

    def get_index(self, params):
        db_path = self._p(params, "db_path", self.state["db_path"])
        if not db_path or not os.path.isfile(db_path):
            return (0, None, ("ERR_DB", f"DB not found: {db_path}", 0))
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM files ORDER BY path")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return (1, rows, None)

    def get_stats(self, params):
        return (1, dict(self.state["stats"]), None)

    # ================================================================
    # EXTRACTION
    # ================================================================

    def _extract_all(self, fpath, root):
        ok, stat_data, err = self.state["io"].Run("file_stat", {"path": fpath})
        if not ok:
            return None
        ok, md5_hash, _ = self.state["io"].Run("hash_file", {"path": fpath})
        if not ok:
            md5_hash = "ERROR"
        rel_path = os.path.relpath(fpath, root)
        fname = os.path.basename(fpath)
        ext = os.path.splitext(fname)[1].lower()
        category = self._get_category(fname, ext)
        size = stat_data["size"]
        dup_flag = 1 if self._is_duplicate_name(fname) else 0
        depth = rel_path.count(os.sep)
        parent = os.path.dirname(rel_path)
        entry = {
            "path": rel_path,
            "filename": fname,
            "extension": ext,
            "category": category,
            "size_bytes": size,
            "size_human": self._human_size(size),
            "created": stat_data["created"],
            "modified": stat_data["modified"],
            "md5": md5_hash,
            "is_duplicate_name": dup_flag,
            "depth": depth,
            "parent_dir": parent,
            "line_count": None,
            "word_count": None,
            "domain": None,
            "role": None,
            "summary": None,
            "bcl_headers": None,
            "classes_json": None,
            "imports_json": None,
            "functions_json": None,
            "is_vbstyle": None,
        }
        if ext in self.CODE_EXTENSIONS:
            self._extract_code(fpath, ext, entry)
        if ext in self.TEXT_EXTENSIONS:
            self._extract_text(fpath, entry)
        return entry

    def _extract_code(self, fpath, ext, entry):
        ok, content, _ = self.state["io"].Run("read_file", {"path": fpath})
        if not ok:
            return
        lines = content.splitlines()
        entry["line_count"] = len(lines)
        if ext == ".py":
            headers = self._extract_headers(content)
            entry["domain"] = headers["domain"]
            entry["role"] = headers["role"]
            entry["summary"] = headers["summary"]
            entry["bcl_headers"] = json.dumps(headers["bcl_list"]) if headers["bcl_list"] else None
            classes, imports = self._parse_ast(content, fpath)
            entry["classes_json"] = json.dumps(classes) if classes else None
            entry["imports_json"] = json.dumps(imports) if imports else None
            entry["is_vbstyle"] = 1 if self._check_vbstyle(lines) else 0
            if not entry["domain"]:
                entry["domain"] = os.path.basename(os.path.dirname(fpath))
        else:
            functions = []
            for line in lines:
                m = self.C_FUNC_RE.match(line.strip())
                if m:
                    functions.append(m.group(1))
            entry["functions_json"] = json.dumps(functions) if functions else None

    def _extract_text(self, fpath, entry):
        if entry["line_count"] is not None:
            return
        ok, content, _ = self.state["io"].Run("read_file", {"path": fpath})
        if not ok:
            return
        lines = content.splitlines()
        entry["line_count"] = len(lines)
        entry["word_count"] = len(content.split())

    def _extract_headers(self, content):
        result = {"domain": "", "role": "", "summary": "", "bcl_list": []}
        ghost_match = self.GHOST_RE.search(content)
        if ghost_match:
            ghost_body = ghost_match.group(1)
            file_match = self.FILE_RE.search(ghost_body)
            if file_match:
                result["domain"] = file_match.group(1)
            domain_match = self.DOMAIN_RE.search(ghost_body)
            if domain_match:
                result["domain"] = domain_match.group(1)
            result["bcl_list"].append("GHOST")
        vbs_match = self.VBSTYLE_RE.search(content)
        if vbs_match:
            vbs_body = vbs_match.group(1)
            role_match = self.ROLE_RE.search(vbs_body)
            if role_match:
                result["role"] = role_match.group(1)
            result["bcl_list"].append("VBSTYLE")
        sum_match = self.SUMMARY_RE.search(content)
        if sum_match:
            result["summary"] = sum_match.group(1).strip()
            result["bcl_list"].append("SUMMARY")
        wcl_match = self.WCL_RE.search(content)
        if wcl_match:
            result["bcl_list"].append("WCL")
        return result

    def _parse_ast(self, content, file_path):
        classes = []
        imports = []
        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError:
            return (classes, imports)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = []
                bases = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        bases.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        bases.append(base.attr)
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append(item.name)
                classes.append({
                    "name": node.name,
                    "methods": methods,
                    "line_start": node.lineno,
                    "line_end": getattr(node, "end_lineno", node.lineno),
                    "bases": bases,
                })
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return (classes, imports)

    def _check_vbstyle(self, lines):
        full = "\n".join(lines)
        has_ghost = bool(self.GHOST_RE.search(full))
        has_vbstyle = bool(self.VBSTYLE_RE.search(full))
        has_run = bool(re.search(r'def\s+Run\s*\(', full))
        has_state = bool(re.search(r'self\.state\s*=', full))
        has_tuple = bool(re.search(r'\(1,\s*\w+,\s*None\)|\(0,\s*None,', full))
        no_print = not any(re.search(r'\bprint\s*\(', l) for l in lines if not l.strip().startswith("#"))
        no_decorators = not any(re.match(r'^\s*@(?:staticmethod|classmethod|property)', l) for l in lines)
        return has_ghost and has_vbstyle and has_run and has_state and has_tuple and no_print and no_decorators

    # ================================================================
    # SQLITE STORAGE
    # ================================================================

    def _create_schema(self, db_path):
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE,
                filename TEXT,
                extension TEXT,
                category TEXT,
                size_bytes INTEGER,
                size_human TEXT,
                created TEXT,
                modified TEXT,
                md5 TEXT,
                is_duplicate_name INTEGER DEFAULT 0,
                depth INTEGER,
                parent_dir TEXT,
                line_count INTEGER,
                word_count INTEGER,
                domain TEXT,
                role TEXT,
                summary TEXT,
                bcl_headers TEXT,
                classes_json TEXT,
                imports_json TEXT,
                functions_json TEXT,
                is_vbstyle INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_category ON files(category);
            CREATE INDEX IF NOT EXISTS idx_ext ON files(extension);
            CREATE INDEX IF NOT EXISTS idx_size ON files(size_bytes DESC);
            CREATE INDEX IF NOT EXISTS idx_md5 ON files(md5);
            CREATE INDEX IF NOT EXISTS idx_dup ON files(is_duplicate_name);
            CREATE INDEX IF NOT EXISTS idx_domain ON files(domain);
        """)
        conn.commit()
        conn.close()

    def _insert_batch(self, conn, batch):
        conn.executemany(
            "INSERT OR REPLACE INTO files "
            "(path, filename, extension, category, size_bytes, size_human, "
            "created, modified, md5, is_duplicate_name, depth, parent_dir, "
            "line_count, word_count, domain, role, summary, bcl_headers, "
            "classes_json, imports_json, functions_json, is_vbstyle) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(
                e["path"], e["filename"], e["extension"], e["category"],
                e["size_bytes"], e["size_human"], e["created"], e["modified"],
                e["md5"], e["is_duplicate_name"], e["depth"], e["parent_dir"],
                e["line_count"], e["word_count"], e["domain"], e["role"],
                e["summary"], e["bcl_headers"], e["classes_json"],
                e["imports_json"], e["functions_json"], e["is_vbstyle"],
            ) for e in batch]
        )

    # ================================================================
    # QUERIES
    # ================================================================

    def _query_db(self, db_path, sql, args=None):
        if not db_path or not os.path.isfile(db_path):
            return (0, None, ("ERR_DB", f"DB not found: {db_path}", 0))
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(sql, args or [])
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return (1, rows, None)
        except Exception as e:
            return (0, None, ("ERR_QUERY", str(e), 0))

    def query_domain(self, params):
        db_path = self._p(params, "db_path", self.state["db_path"])
        domain = self._p(params, "domain")
        if not domain:
            return (0, None, ("ERR_PARAMS", "domain required", 0))
        return self._query_db(db_path, "SELECT * FROM files WHERE domain = ? ORDER BY path", [domain])

    def query_class(self, params):
        db_path = self._p(params, "db_path", self.state["db_path"])
        class_name = self._p(params, "class_name")
        if not class_name:
            return (0, None, ("ERR_PARAMS", "class_name required", 0))
        sql = "SELECT path, filename, domain, classes_json FROM files WHERE classes_json LIKE ? ORDER BY path"
        return self._query_db(db_path, sql, [f'%"{class_name}"%'])

    def query_method(self, params):
        db_path = self._p(params, "db_path", self.state["db_path"])
        method_name = self._p(params, "method_name")
        if not method_name:
            return (0, None, ("ERR_PARAMS", "method_name required", 0))
        sql = "SELECT path, filename, domain, classes_json FROM files WHERE classes_json LIKE ? ORDER BY path"
        return self._query_db(db_path, sql, [f'%"{method_name}"%'])

    def query_category(self, params):
        db_path = self._p(params, "db_path", self.state["db_path"])
        category = self._p(params, "category")
        if not category:
            return (0, None, ("ERR_PARAMS", "category required", 0))
        return self._query_db(db_path, "SELECT * FROM files WHERE category = ? ORDER BY size_bytes DESC", [category])

    def query_duplicates(self, params):
        db_path = self._p(params, "db_path", self.state["db_path"])
        sql = ("SELECT md5, COUNT(*) as dup_count, SUM(size_bytes) as total_size, "
               "GROUP_CONCAT(path, ';') as paths "
               "FROM files WHERE md5 NOT IN ('SKIP_LARGE','ERROR') "
               "GROUP BY md5 HAVING dup_count > 1 ORDER BY total_size DESC")
        return self._query_db(db_path, sql)

    def query_large_files(self, params):
        db_path = self._p(params, "db_path", self.state["db_path"])
        n = self._p(params, "n", 20)
        return self._query_db(db_path, "SELECT * FROM files ORDER BY size_bytes DESC LIMIT ?", [n])

    # ================================================================
    # HELPERS
    # ================================================================

    def _get_category(self, fname, ext):
        lower = fname.lower()
        if lower.endswith(".bak.db") or lower.endswith(".bak.db-wal") or lower.endswith(".bak.db-shm"):
            return "BackupDB"
        return self.CATEGORY_MAP.get(ext, "Other")

    def _is_duplicate_name(self, fname):
        lower = fname.lower()
        return any(m in lower for m in self.DUP_MARKERS)

    def _human_size(self, n):
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} PB"


# Backward-compat alias — old code imported `Indexer`; the class is now `FileIndexer`.
Indexer = FileIndexer
