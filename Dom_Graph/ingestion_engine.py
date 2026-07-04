#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/ingestion_engine.py"
# date="2026-06-26" author="Devin" session_id="phase1-foundation"
# context="Project Digital Twin Phase 1 Section 5 Ingestion Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="ingestion_engine.py" domain="twin_ingestion" authority="IngestionEngine"}
# [@SUMMARY]{summary="Ingestion authority that scans .py files, computes hashes, detects duplicates and updates the files table of the Project Digital Twin."}
# [@CLASS]{class="IngestionEngine" domain="ingestion" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="scan" type="command"}
# [@METHOD]{method="ingest_file" type="command"}
# [@METHOD]{method="ingest_directory" type="command"}
# [@METHOD]{method="detect_duplicates" type="command"}
# [@METHOD]{method="update_changed" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<IngestionEngine: scans .py files, computes hashes, detects duplicates, updates files table. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths. Docstring notes 5 missing spec sub-sections and critical bug (os.listdir instead of rglob) but code structure is VBStyle compliant.>][@todos<none>]}
"""
IngestionEngine -- authority for scanning and ingesting .py files.
Implements Section 5 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: scan, ingest_file, ingest_directory, detect_duplicates, update_changed.
Populates the files table with file_name, path, hash, size, imports,
class_count, method_count.

# ============================================================
# ERRORS -- Section 5 spec vs. implementation
# Rating: 3/10
# Spec has 10 sub-sections (5.1-5.10). Only 5 implemented.
# 5 methods MISSING.
# ============================================================
# MISSING METHODS:
# 5.3  ComputeBclHash    -- extract BCL header, hash separately from file hash. NOT IMPLEMENTED.
#                          (file hash is computed but BCL hash is not. bcl column left NULL.)
# 5.6  DetectLanguage    -- by extension (.py=python, .c=C, .swift=Swift). PARTIAL.
#                          (hardcoded 'python' in IngestFile, no detection logic.)
# 5.7  DetectEncoding    -- chardet.detect(content). NOT IMPLEMENTED.
#                          (encoding column left to default 'utf-8'.)
# 5.8  DetectDependencies -- parse import statements as file dependencies. NOT IMPLEMENTED.
#                          (imports are extracted but dependencies column left NULL.)
# 5.10 StoreRawSource    -- store full file content in files table or separate table. NOT IMPLEMENTED.
#                          (no raw source stored anywhere.)
#
# PARTIAL:
# 5.1  ScanFiles         -- implemented but only scans flat os.listdir, not rglob.
#                          (does not recurse into subdirectories. Spec says pathlib.Path(dir).rglob('*.py').)
# 5.2  ComputeFileHash   -- implemented, real sha256.
# 5.4  DetectDuplicates  -- implemented, queries by hash.
# 5.5  DetectVersion     -- implemented in UpdateChanged, compares hash, increments version.
# 5.9  RecordMetadata    -- implemented, INSERT into files table.
#
# CRITICAL BUG:
# 5.1  ScanFiles uses os.listdir (flat) instead of Path.rglob (recursive).
#      Subdirectory .py files are never ingested. This is a functional defect,
#      not just a missing feature.
# ============================================================
"""
import ast
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_SCAN_DIR = os.path.dirname(os.path.abspath(__file__))
PY_EXTENSION = ".py"
CHUNK_SIZE = 65536


class IngestionEngine:
    """Authority for scanning .py files and populating the files table."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "scan_dir": DEFAULT_SCAN_DIR,
                "extension": PY_EXTENSION,
            },
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "scan":
            return self.Scan(params)
        elif command == "ingest_file":
            return self.IngestFile(params)
        elif command == "ingest_directory":
            return self.IngestDirectory(params)
        elif command == "detect_duplicates":
            return self.DetectDuplicates(params)
        elif command == "update_changed":
            return self.UpdateChanged(params)
        elif command == "compute_bcl_hash":
            return self.ComputeBclHash(params)
        elif command == "detect_language":
            return self.DetectLanguage(params)
        elif command == "detect_encoding":
            return self.DetectEncoding(params)
        elif command == "detect_dependencies":
            return self.DetectDependencies(params)
        elif command == "store_raw_source":
            return self.StoreRawSource(params)
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
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def Connect(self):
        if self.state["db_conn"] is None:
            path = self.state["config"]["db_path"]
            self.state["db_conn"] = sqlite3.connect(path)
        return self.state["db_conn"]

    def HashContent(self, text):
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def ExtractImports(self, tree):
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    imports.append(mod + "." + alias.name if mod else alias.name)
        return imports

    def Scan(self, params):
        directory = self._p(params, "directory", self.state["config"]["scan_dir"])
        extension = self._p(params, "extension", self.state["config"]["extension"])
        if not os.path.isdir(directory):
            return (0, None, ("DIR_NOT_FOUND", directory, 0))
        found = []
        base = Path(directory)
        pattern = "*" + extension
        for path in sorted(base.rglob(pattern)):
            if path.is_file():
                found.append(str(path))
        self.state["results"] = found
        return (1, {"directory": directory, "files": found, "count": len(found)}, None)

    def IngestFile(self, params):
        path = self._p(params, "path")
        if not path:
            return (0, None, ("MISSING_PARAM", "path required", 0))
        if not os.path.isfile(path):
            return (0, None, ("FILE_NOT_FOUND", path, 0))
        try:
            with open(path, "rb") as fh:
                raw_bytes = fh.read()
        except OSError as exc:
            return (0, None, ("READ_FAILED", str(exc), 0))
        encoding = self.DetectEncodingValue(raw_bytes)
        try:
            content = raw_bytes.decode(encoding, errors="replace")
        except (LookupError, UnicodeDecodeError):
            content = raw_bytes.decode("utf-8", errors="replace")
            encoding = "utf-8"
        try:
            tree = ast.parse(content, filename=path)
        except SyntaxError as exc:
            return (0, None, ("PARSE_FAILED", str(exc), 0))
        imports = self.ExtractImports(tree)
        file_hash = self.HashContent(content)
        size = os.path.getsize(path)
        class_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        method_count = sum(
            1 for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
        fname = os.path.basename(path)
        ext = os.path.splitext(fname)[1]
        language = self.DetectLanguageValue(ext)
        bcl_text = self.ExtractBcl(content)
        bcl_hash = self.HashContent(bcl_text) if bcl_text else None
        dependencies = self.ResolveDependencies(imports)
        now = datetime.now(timezone.utc).isoformat()
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO files (file_name, path, extension, hash, size, "
                "imports, class_count, function_count, method_count, created, "
                "modified, language, encoding, bcl, dependencies, raw_source) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (fname, path, ext, file_hash, size,
                 json.dumps(imports), class_count, method_count, method_count,
                 now, now, language, encoding, bcl_text,
                 json.dumps(dependencies), content),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        record = {
            "file_id": cur.lastrowid,
            "file_name": fname,
            "path": path,
            "hash": file_hash,
            "size": size,
            "class_count": class_count,
            "method_count": method_count,
            "language": language,
            "encoding": encoding,
            "bcl_hash": bcl_hash,
            "dependencies": dependencies,
        }
        self.state["catalog"].append(record)
        return (1, record, None)

    def IngestDirectory(self, params):
        directory = self._p(params, "directory", self.state["config"]["scan_dir"])
        scan_result = self.Scan({"directory": directory})
        if scan_result[0] != 1:
            return scan_result
        files = scan_result[1]["files"]
        ingested = []
        skipped = []
        for path in files:
            res = self.IngestFile({"path": path})
            if res[0] == 1:
                ingested.append(res[1])
            else:
                skipped.append({"path": path, "error": res[2]})
        return (1, {"ingested": ingested, "skipped": skipped, "count": len(ingested)}, None)

    def DetectDuplicates(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT hash, COUNT(*) FROM files GROUP BY hash HAVING COUNT(*) > 1"
            )
            rows = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        duplicates = []
        for row in rows:
            cur.execute(
                "SELECT file_id, file_name, path FROM files WHERE hash=?", (row[0],)
            )
            members = [dict(zip(("file_id", "file_name", "path"), r)) for r in cur.fetchall()]
            duplicates.append({"hash": row[0], "count": row[1], "members": members})
        return (1, {"duplicates": duplicates, "duplicate_hashes": len(duplicates)}, None)

    def UpdateChanged(self, params):
        directory = self._p(params, "directory", self.state["config"]["scan_dir"])
        scan_result = self.Scan({"directory": directory})
        if scan_result[0] != 1:
            return scan_result
        files = scan_result[1]["files"]
        conn = self.Connect()
        cur = conn.cursor()
        updated = []
        new_files = []
        unchanged = []
        now = datetime.now(timezone.utc).isoformat()
        for path in files:
            fname = os.path.basename(path)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            except OSError:
                continue
            current_hash = self.HashContent(content)
            try:
                cur.execute(
                    "SELECT file_id, hash, version FROM files WHERE path=? ORDER BY version DESC LIMIT 1",
                    (path,),
                )
                row = cur.fetchone()
            except sqlite3.Error as exc:
                return (0, None, ("QUERY_FAILED", str(exc), 0))
            if row is None:
                try:
                    tree = ast.parse(content, filename=path)
                except SyntaxError:
                    continue
                imports = self.ExtractImports(tree)
                class_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
                method_count = sum(
                    1 for n in ast.walk(tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
                cur.execute(
                    "INSERT INTO files (file_name, path, extension, hash, size, "
                    "imports, class_count, function_count, method_count, created, "
                    "modified, language) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (fname, path, os.path.splitext(fname)[1], current_hash,
                     os.path.getsize(path), json.dumps(imports), class_count,
                     method_count, method_count, now, now, "python"),
                )
                new_files.append({"file_name": fname, "file_id": cur.lastrowid})
            elif row[1] != current_hash:
                cur.execute(
                    "UPDATE files SET hash=?, modified=?, version=version+1 WHERE file_id=?",
                    (current_hash, now, row[0]),
                )
                updated.append({"file_name": fname, "file_id": row[0], "old_hash": row[1], "new_hash": current_hash})
            else:
                unchanged.append({"file_name": fname, "file_id": row[0]})
        conn.commit()
        return (
            1,
            {"updated": updated, "new": new_files, "unchanged": unchanged,
             "updated_count": len(updated), "new_count": len(new_files)},
            None,
        )

    def ExtractBcl(self, content):
        # helper: extract BCL header block from file content
        if not content:
            return None
        lines = content.splitlines()
        in_bcl = False
        bcl_lines = []
        depth = 0
        for line in lines:
            if "[@BCL]" in line or "[@GHOST]" in line:
                in_bcl = True
                bcl_lines = [line]
                depth = line.count("{") - line.count("}")
                if depth <= 0:
                    break
                continue
            if in_bcl:
                bcl_lines.append(line)
                depth += line.count("{") - line.count("}")
                if depth <= 0:
                    break
        if not bcl_lines:
            return None
        return "\n".join(bcl_lines)

    def ComputeBclHash(self, params):
        # 5.3 -- extract BCL header, hash separately
        path = self._p(params, "path")
        file_id = self._p(params, "file_id")
        content = self._p(params, "content")
        if content is None and path:
            if not os.path.isfile(path):
                return (0, None, ("FILE_NOT_FOUND", path, 0))
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            except OSError as exc:
                return (0, None, ("READ_FAILED", str(exc), 0))
        if content is None and file_id:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("SELECT raw_source FROM files WHERE file_id=?", (file_id,))
            row = cur.fetchone()
            if row and row[0]:
                content = row[0]
        if content is None:
            return (0, None, ("MISSING_PARAM", "path or content required", 0))
        bcl_text = self.ExtractBcl(content)
        bcl_hash = self.HashContent(bcl_text) if bcl_text else None
        if file_id is not None:
            conn = self.Connect()
            cur = conn.cursor()
            try:
                cur.execute(
                    "UPDATE files SET bcl=?, bcl_hash=? WHERE file_id=?",
                    (bcl_text, bcl_hash, file_id),
                )
                conn.commit()
            except sqlite3.Error as exc:
                return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"file_id": file_id, "bcl": bcl_text,
                    "bcl_hash": bcl_hash}, None)

    def DetectLanguageValue(self, ext):
        # helper: detect language by extension
        lang_map = {
            ".py": "python", ".c": "C", ".h": "C", ".cpp": "C++",
            ".cc": "C++", ".hpp": "C++", ".swift": "Swift",
            ".js": "javascript", ".ts": "typescript", ".java": "java",
            ".go": "go", ".rs": "rust", ".rb": "ruby", ".php": "php",
            ".sh": "shell", ".sql": "sql", ".md": "markdown",
        }
        return lang_map.get(ext.lower(), "unknown")

    def DetectLanguage(self, params):
        # 5.6 -- detect language by extension, not hardcoded
        path = self._p(params, "path")
        ext = self._p(params, "extension")
        file_id = self._p(params, "file_id")
        if ext is None and path:
            ext = os.path.splitext(path)[1]
        if ext is None and file_id:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("SELECT extension FROM files WHERE file_id=?", (file_id,))
            row = cur.fetchone()
            if row:
                ext = row[0]
        if ext is None:
            return (0, None, ("MISSING_PARAM", "path or extension required", 0))
        language = self.DetectLanguageValue(ext)
        if file_id is not None:
            conn = self.Connect()
            cur = conn.cursor()
            try:
                cur.execute(
                    "UPDATE files SET language=? WHERE file_id=?",
                    (language, file_id),
                )
                conn.commit()
            except sqlite3.Error as exc:
                return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"extension": ext, "language": language}, None)

    def DetectEncodingValue(self, raw_bytes):
        # helper: detect encoding using chardet if available, fallback utf-8
        try:
            import chardet
            result = chardet.detect(raw_bytes)
            if result and result.get("encoding"):
                return result["encoding"]
        except ImportError:
            pass
        return "utf-8"

    def DetectEncoding(self, params):
        # 5.7 -- use chardet if available, fallback to utf-8
        path = self._p(params, "path")
        file_id = self._p(params, "file_id")
        raw_bytes = self._p(params, "raw_bytes")
        if raw_bytes is None and path:
            if not os.path.isfile(path):
                return (0, None, ("FILE_NOT_FOUND", path, 0))
            try:
                with open(path, "rb") as fh:
                    raw_bytes = fh.read()
            except OSError as exc:
                return (0, None, ("READ_FAILED", str(exc), 0))
        if raw_bytes is None:
            return (0, None, ("MISSING_PARAM", "path or raw_bytes required", 0))
        encoding = self.DetectEncodingValue(raw_bytes)
        if file_id is not None:
            conn = self.Connect()
            cur = conn.cursor()
            try:
                cur.execute(
                    "UPDATE files SET encoding=? WHERE file_id=?",
                    (encoding, file_id),
                )
                conn.commit()
            except sqlite3.Error as exc:
                return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"file_id": file_id, "encoding": encoding}, None)

    def ResolveDependencies(self, imports):
        # helper: resolve import names to file dependency paths
        deps = []
        for imp in imports:
            base = imp.split(".")[0]
            deps.append(base + ".py")
        return deps

    def DetectDependencies(self, params):
        # 5.8 -- parse imports as file dependencies, store in dependencies column
        path = self._p(params, "path")
        file_id = self._p(params, "file_id")
        imports = self._p(params, "imports")
        content = self._p(params, "content")
        if imports is None:
            if content is None and path:
                if not os.path.isfile(path):
                    return (0, None, ("FILE_NOT_FOUND", path, 0))
                try:
                    with open(path, "r", encoding="utf-8",
                              errors="replace") as fh:
                        content = fh.read()
                except OSError as exc:
                    return (0, None, ("READ_FAILED", str(exc), 0))
            if content:
                try:
                    tree = ast.parse(content, filename=path or "<str>")
                    imports = self.ExtractImports(tree)
                except SyntaxError:
                    imports = []
            else:
                imports = []
        dependencies = self.ResolveDependencies(imports)
        if file_id is not None:
            conn = self.Connect()
            cur = conn.cursor()
            try:
                cur.execute(
                    "UPDATE files SET dependencies=? WHERE file_id=?",
                    (json.dumps(dependencies), file_id),
                )
                conn.commit()
            except sqlite3.Error as exc:
                return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"file_id": file_id, "imports": imports,
                    "dependencies": dependencies}, None)

    def StoreRawSource(self, params):
        # 5.10 -- store full file content
        path = self._p(params, "path")
        file_id = self._p(params, "file_id")
        content = self._p(params, "content")
        if content is None and path:
            if not os.path.isfile(path):
                return (0, None, ("FILE_NOT_FOUND", path, 0))
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            except OSError as exc:
                return (0, None, ("READ_FAILED", str(exc), 0))
        if content is None:
            return (0, None, ("MISSING_PARAM", "path or content required", 0))
        if file_id is None:
            return (1, {"stored": False, "content_length": len(content)}, None)
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE files SET raw_source=? WHERE file_id=?",
                (content, file_id),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"file_id": file_id, "stored": True,
                    "content_length": len(content)}, None)
