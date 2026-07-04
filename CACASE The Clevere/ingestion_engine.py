#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/ingestion_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 5: Ingestion -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="ingestion_engine.py" domain="twin_ingestion" authority="IngestionEngine"}
# [@SUMMARY]{summary="Ingestion authority: scan files, compute file hash, compute BCL hash, detect duplicates, detect version, detect language, detect encoding, detect dependencies, record metadata, store raw source."}
# [@CLASS]{class="IngestionEngine" domain="ingestion" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="scan_files" type="command"}
# [@METHOD]{method="compute_file_hash" type="command"}
# [@METHOD]{method="compute_bcl_hash" type="command"}
# [@METHOD]{method="detect_duplicates" type="command"}
# [@METHOD]{method="detect_version" type="command"}
# [@METHOD]{method="detect_language" type="command"}
# [@METHOD]{method="detect_encoding" type="command"}
# [@METHOD]{method="detect_dependencies" type="command"}
# [@METHOD]{method="record_metadata" type="command"}
# [@METHOD]{method="store_raw_source" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import ast
import hashlib
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"
BCL_PREFIX = "# [@"
BCL_SUFFIX = "]"


class IngestionEngine:
    """Authority for file ingestion, hashing, and metadata extraction."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "scan_dir": os.path.dirname(os.path.abspath(__file__)),
                "extensions": [".py", ".c", ".h", ".md", ".sql", ".json", ".yaml"],
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
        if command == "scan_files":
            return self.ScanFiles(params)
        elif command == "compute_file_hash":
            return self.ComputeFileHash(params)
        elif command == "compute_bcl_hash":
            return self.ComputeBclHash(params)
        elif command == "detect_duplicates":
            return self.DetectDuplicates(params)
        elif command == "detect_version":
            return self.DetectVersion(params)
        elif command == "detect_language":
            return self.DetectLanguage(params)
        elif command == "detect_encoding":
            return self.DetectEncoding(params)
        elif command == "detect_dependencies":
            return self.DetectDependencies(params)
        elif command == "record_metadata":
            return self.RecordMetadata(params)
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
            self.state["db_conn"] = sqlite3.connect(self.state["config"]["db_path"])
        return (1, self.state["db_conn"], None)

    def Now(self):
        return (1, datetime.now(timezone.utc).isoformat(), None)

    def ScanFiles(self, params):
        scan_dir = self._p(params, "scan_dir", self.state["config"]["scan_dir"])
        extensions = self._p(params, "extensions", self.state["config"]["extensions"])
        files = []
        for root, dirs, fnames in os.walk(scan_dir):
            for fname in fnames:
                ext = os.path.splitext(fname)[1]
                if ext in extensions:
                    files.append(os.path.join(root, fname))
        record = {"files_found": len(files), "scan_dir": scan_dir}
        self.state["catalog"].append(record)
        return (1, record, None)

    def ComputeFileHash(self, params):
        path = self._p(params, "path")
        if path is None or not os.path.isfile(path):
            return (0, None, ("FILE_NOT_FOUND", str(path), 0))
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return (1, {"path": path, "hash": h.hexdigest()}, None)

    def ComputeBclHash(self, params):
        path = self._p(params, "path")
        if path is None or not os.path.isfile(path):
            return (0, None, ("FILE_NOT_FOUND", str(path), 0))
        bcl_lines = []
        with open(path, "r", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith(BCL_PREFIX) and BCL_SUFFIX in stripped:
                    bcl_lines.append(stripped)
        bcl_text = "\n".join(bcl_lines)
        bcl_hash = hashlib.sha256(bcl_text.encode("utf-8")).hexdigest()
        return (1, {"path": path, "bcl_hash": bcl_hash,
                    "bcl_lines": len(bcl_lines)}, None)

    def DetectDuplicates(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT hash, COUNT(*) FROM files WHERE hash IS NOT NULL "
            "GROUP BY hash HAVING COUNT(*) > 1"
        )
        dup_hashes = cur.fetchall()
        duplicates = []
        for dhash, count in dup_hashes:
            cur.execute(
                "SELECT file_id, file_name, path FROM files WHERE hash=?",
                (dhash,),
            )
            members = [{"file_id": r[0], "file_name": r[1], "path": r[2]}
                        for r in cur.fetchall()]
            duplicates.append({"hash": dhash, "count": count, "members": members})
        record = {"duplicate_hashes": len(duplicates),
                  "duplicates": duplicates[:50]}
        self.state["results"] = record
        return (1, record, None)

    def DetectVersion(self, params):
        path = self._p(params, "path")
        if path is None or not os.path.isfile(path):
            return (0, None, ("FILE_NOT_FOUND", str(path), 0))
        ext = os.path.splitext(path)[1]
        version = None
        if ext == ".py":
            with open(path, "r", errors="replace") as f:
                for line in f:
                    if "version" in line.lower() and "=" in line:
                        version = line.strip()
                        break
        return (1, {"path": path, "version": version}, None)

    def DetectLanguage(self, params):
        path = self._p(params, "path")
        if path is None:
            return (0, None, ("MISSING_PARAM", "path required", 0))
        ext = os.path.splitext(path)[1].lower()
        lang_map = {
            ".py": "python", ".c": "c", ".h": "c",
            ".md": "markdown", ".sql": "sql",
            ".json": "json", ".yaml": "yaml", ".yml": "yaml",
            ".rs": "rust", ".go": "go", ".swift": "swift",
            ".dart": "dart", ".js": "javascript", ".ts": "typescript",
        }
        language = lang_map.get(ext, "unknown")
        return (1, {"path": path, "language": language, "extension": ext}, None)

    def DetectEncoding(self, params):
        path = self._p(params, "path")
        if path is None or not os.path.isfile(path):
            return (0, None, ("FILE_NOT_FOUND", str(path), 0))
        with open(path, "rb") as f:
            raw = f.read(4096)
        encoding = "utf-8"
        if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
            encoding = "utf-16"
        elif raw.startswith(b"\xef\xbb\xbf"):
            encoding = "utf-8-sig"
        else:
            try:
                raw.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    raw.decode("latin-1")
                    encoding = "latin-1"
                except Exception:
                    encoding = "binary"
        return (1, {"path": path, "encoding": encoding}, None)

    def DetectDependencies(self, params):
        path = self._p(params, "path")
        if path is None or not os.path.isfile(path):
            return (0, None, ("FILE_NOT_FOUND", str(path), 0))
        ext = os.path.splitext(path)[1]
        deps = []
        if ext == ".py":
            try:
                with open(path, "r", errors="replace") as f:
                    tree = ast.parse(f.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            deps.append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            deps.append(node.module)
            except SyntaxError:
                pass
        return (1, {"path": path, "dependencies": deps}, None)

    def RecordMetadata(self, params):
        path = self._p(params, "path")
        if path is None or not os.path.isfile(path):
            return (0, None, ("FILE_NOT_FOUND", str(path), 0))
        stat = os.stat(path)
        ext = os.path.splitext(path)[1]
        fname = os.path.basename(path)
        metadata = {
            "file_name": fname,
            "path": path,
            "extension": ext,
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime, timezone.utc).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        }
        return (1, metadata, None)

    def StoreRawSource(self, params):
        path = self._p(params, "path")
        if path is None or not os.path.isfile(path):
            return (0, None, ("FILE_NOT_FOUND", str(path), 0))
        with open(path, "r", errors="replace") as f:
            content = f.read()
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT file_id FROM files WHERE path=?", (path,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("FILE_NOT_INGESTED",
                              "Run ingest_file first", 0))
        file_id = row[0]
        cur.execute(
            "INSERT INTO snapshots (snapshot_type, file_id, content, hash, created, notes) "
            "VALUES ('raw_source', ?, ?, ?, ?, 'ingestion raw source')",
            (file_id, content, hashlib.sha256(content.encode("utf-8")).hexdigest(),
             self.Now()[1]),
        )
        conn.commit()
        return (1, {"file_id": file_id, "snapshot_id": cur.lastrowid}, None)

    def IngestFile(self, params):
        path = self._p(params, "path")
        if path is None or not os.path.isfile(path):
            return (0, None, ("FILE_NOT_FOUND", str(path), 0))
        fname = os.path.basename(path)
        ext = os.path.splitext(path)[1]
        stat = os.stat(path)
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        file_hash = h.hexdigest()
        bcl_lines = []
        with open(path, "r", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith(BCL_PREFIX) and BCL_SUFFIX in stripped:
                    bcl_lines.append(stripped)
        bcl_text = "\n".join(bcl_lines)
        bcl_hash = hashlib.sha256(bcl_text.encode("utf-8")).hexdigest()
        deps = []
        if ext == ".py":
            try:
                with open(path, "r", errors="replace") as f:
                    tree = ast.parse(f.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            deps.append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            deps.append(node.module)
            except SyntaxError:
                pass
        lang_map = {".py": "python", ".c": "c", ".h": "c", ".md": "markdown",
                    ".sql": "sql", ".json": "json", ".yaml": "yaml"}
        language = lang_map.get(ext, "unknown")
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO files (file_name, path, extension, hash, bcl, size, "
                "imports, dependencies, created, modified, version, status, "
                "encoding, language) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (fname, path, ext, file_hash, bcl_text, stat.st_size,
                 json.dumps(deps), json.dumps(deps),
                 datetime.fromtimestamp(stat.st_ctime, timezone.utc).isoformat(),
                 datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                 1, "active", "utf-8", language),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        record = {"file_id": cur.lastrowid, "file_name": fname,
                  "hash": file_hash, "bcl_hash": bcl_hash,
                  "dependencies": len(deps)}
        self.state["catalog"].append(record)
        return (1, record, None)
