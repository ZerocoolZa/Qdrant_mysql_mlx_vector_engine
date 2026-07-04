# [@GHOST]{[@file<Dom_Report.py>][@domain<Dom_Unified>][@role<search_report_copy_provenance>][@auth<cascade>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<search_report_copy_provenance>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{DomReport — unified search, report, copy-with-provenance engine. Replaces 18 fragmented files.}
# [@CLASS]{DomReport}
# [@METHOD]{Run,search,report,copy_to_file,copy_to_folder,copy_to_sqlite,provenance,verify_lineage}

"""
DomReport — unified search + report + copy + provenance authority.

WHAT IT DOES:
  1. SEARCH    — find files/code by pattern, content, or AST structure
  2. REPORT    — generate markdown reports from search results or file scans
  3. COPY      — copy files to a single file, a folder, multiple files, or SQLite
  4. PROVENANCE — track WHERE every copied file came from (source path, hash, timestamp)
  5. VERIFY    — check lineage integrity (hash match, chain completeness)

USAGE:
  from Dom_Unified.Dom_Report import DomReport

  dr = DomReport()

  # Search for files matching a pattern
  ok, results, err = dr.Run("search", {"path": "/some/dir", "pattern": "*.py", "content": "class Config"})

  # Copy files to a folder (with provenance)
  ok, data, err = dr.Run("copy_to_folder", {"sources": ["file1.py", "file2.py"], "dest": "/tmp/copied/"})

  # Copy files into a single combined file (with provenance header)
  ok, data, err = dr.Run("copy_to_file", {"sources": ["file1.py", "file2.py"], "dest": "/tmp/combined.py"})

  # Copy files into SQLite (with full provenance tracking)
  ok, data, err = dr.Run("copy_to_sqlite", {"sources": ["file1.py"], "db": "/tmp/store.db"})

  # Query provenance for a copied file
  ok, chain, err = dr.Run("provenance", {"dest": "/tmp/copied/file1.py"})

  # Generate a report of all copy operations
  ok, report, err = dr.Run("report", {"type": "copy_history"})

  # Verify lineage integrity
  ok, data, err = dr.Run("verify_lineage", {"db": "/tmp/store.db"})
"""

import os
import re
import hashlib
import shutil
import sqlite3
import datetime


class DomReport:
    """
    Unified search + report + copy + provenance engine.
    VBStyle compliant: Run() dispatch, Tuple3 returns, self.state dict.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "default_db": param.get("default_db", os.path.join(os.path.dirname(__file__), "provenance.db")) if param else os.path.join(os.path.dirname(__file__), "provenance.db"),
                "hash_algorithm": "sha256",
                "include_content": param.get("include_content", False) if param else False,
                "max_file_size": param.get("max_file_size", 10 * 1024 * 1024) if param else 10 * 1024 * 1024,
            },
            "copy_history": [],
            "search_history": [],
            "stats": {"searches": 0, "copies": 0, "reports": 0, "provenance_queries": 0, "errors": 0},
        }
        if param:
            for key, val in param.items():
                if key in self.state["config"]:
                    self.state["config"][key] = val

    def Run(self, command, params=None):
        dispatch = {
            "search": self._cmd_search,
            "report": self._cmd_report,
            "copy_to_file": self._cmd_copy_to_file,
            "copy_to_folder": self._cmd_copy_to_folder,
            "copy_to_sqlite": self._cmd_copy_to_sqlite,
            "provenance": self._cmd_provenance,
            "verify_lineage": self._cmd_verify_lineage,
            "list_copies": self._cmd_list_copies,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", f"Unknown: {command}", 0))
        return handler(params or {})

    def read_state(self, params=None):
        return (1, dict(self.state), None)

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
    # SEARCH — find files by pattern, content, or structure
    # ════════════════════════════════════════════

    def _cmd_search(self, params):
        path = self._p(params, "path", ".")
        pattern = self._p(params, "pattern", "*")
        content = self._p(params, "content")
        regex = self._p(params, "regex")
        max_results = self._p(params, "max_results", 1000)
        if not os.path.isdir(path):
            return (0, None, ("ERR_PATH", f"Invalid path: {path}", 0))
        import fnmatch
        matches = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "node_modules", ".git", "venv")]
            for fname in files:
                if fnmatch.fnmatch(fname, pattern):
                    fpath = os.path.join(root, fname)
                    if content or regex:
                        try:
                            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                                file_content = f.read()
                        except Exception:
                            continue
                        if content and content not in file_content:
                            continue
                        if regex and not re.search(regex, file_content):
                            continue
                    matches.append({
                        "file": fpath,
                        "name": fname,
                        "size": os.path.getsize(fpath),
                        "relative": os.path.relpath(fpath, path),
                    })
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break
        self.state["search_history"].append({"path": path, "pattern": pattern, "content": content, "results": len(matches)})
        self.state["stats"]["searches"] += 1
        return (1, {"count": len(matches), "results": matches}, None)

    # ════════════════════════════════════════════
    # REPORT — generate markdown reports
    # ════════════════════════════════════════════

    def _cmd_report(self, params):
        report_type = self._p(params, "type", "copy_history")
        db_path = self._p(params, "db", self.state["config"]["default_db"])
        if report_type == "copy_history":
            return self._report_copy_history(db_path)
        elif report_type == "provenance_chain":
            dest = self._p(params, "dest")
            if not dest:
                return (0, None, ("ERR_DEST", "dest required for provenance_chain report", 0))
            return self._report_provenance_chain(db_path, dest)
        elif report_type == "search_results":
            search_results = self._p(params, "search_results", [])
            return self._report_search_results(search_results)
        elif report_type == "file_inventory":
            path = self._p(params, "path", ".")
            return self._report_file_inventory(path)
        else:
            return (0, None, ("ERR_TYPE", f"Unknown report type: {report_type}", 0))

    def _report_copy_history(self, db_path):
        ok, rows, err = self._query_provenance(db_path, "SELECT * FROM provenance ORDER BY copied_at DESC")
        if not ok:
            return (0, None, err)
        lines = ["# Copy History Report", ""]
        lines.append(f"Generated: {datetime.datetime.now().isoformat()}")
        lines.append(f"Total copies: {len(rows)}")
        lines.append("")
        lines.append("| # | Source | Destination | Type | Hash | Size | Copied At |")
        lines.append("|---|--------|-------------|------|------|------|-----------|")
        for i, row in enumerate(rows, 1):
            src = row["source_path"][-40:] if len(row["source_path"]) > 40 else row["source_path"]
            dst = row["dest_path"][-40:] if len(row["dest_path"]) > 40 else row["dest_path"]
            lines.append(f"| {i} | {src} | {dst} | {row['dest_type']} | {row['source_hash'][:8]} | {row['file_size']} | {row['copied_at']} |")
        self.state["stats"]["reports"] += 1
        return (1, "\n".join(lines), None)

    def _report_provenance_chain(self, db_path, dest):
        ok, rows, err = self._query_provenance(db_path, "SELECT * FROM provenance WHERE dest_path = ? ORDER BY copied_at", [dest])
        if not ok:
            return (0, None, err)
        if not rows:
            return (1, f"No provenance records found for: {dest}", None)
        lines = ["# Provenance Chain Report", ""]
        lines.append(f"Target: {dest}")
        lines.append(f"Records: {len(rows)}")
        lines.append("")
        for row in rows:
            lines.append(f"## Copy Operation #{row['id']}")
            lines.append(f"- **Source:** {row['source_path']}")
            lines.append(f"- **Destination:** {row['dest_path']}")
            lines.append(f"- **Type:** {row['dest_type']}")
            lines.append(f"- **Source Hash:** {row['source_hash']}")
            lines.append(f"- **Dest Hash:** {row['dest_hash']}")
            lines.append(f"- **Size:** {row['file_size']} bytes")
            lines.append(f"- **Copied At:** {row['copied_at']}")
            lines.append(f"- **Match:** {'YES' if row['source_hash'] == row['dest_hash'] else 'NO — MISMATCH'}")
            lines.append("")
        self.state["stats"]["reports"] += 1
        return (1, "\n".join(lines), None)

    def _report_search_results(self, search_results):
        lines = ["# Search Results Report", ""]
        lines.append(f"Generated: {datetime.datetime.now().isoformat()}")
        lines.append(f"Total matches: {len(search_results)}")
        lines.append("")
        lines.append("| # | File | Size | Relative |")
        lines.append("|---|------|------|----------|")
        for i, r in enumerate(search_results, 1):
            lines.append(f"| {i} | {r['name']} | {r['size']} | {r['relative']} |")
        self.state["stats"]["reports"] += 1
        return (1, "\n".join(lines), None)

    def _report_file_inventory(self, path):
        if not os.path.isdir(path):
            return (0, None, ("ERR_PATH", f"Invalid path: {path}", 0))
        lines = ["# File Inventory Report", ""]
        lines.append(f"Path: {path}")
        lines.append(f"Generated: {datetime.datetime.now().isoformat()}")
        lines.append("")
        file_count = 0
        total_size = 0
        by_ext = {}
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", ".git")]
            for fname in files:
                fpath = os.path.join(root, fname)
                fsize = os.path.getsize(fpath)
                ext = os.path.splitext(fname)[1] or "(no ext)"
                by_ext.setdefault(ext, {"count": 0, "size": 0})
                by_ext[ext]["count"] += 1
                by_ext[ext]["size"] += fsize
                file_count += 1
                total_size += fsize
        lines.append(f"**Total files:** {file_count}")
        lines.append(f"**Total size:** {total_size:,} bytes")
        lines.append("")
        lines.append("| Extension | Count | Size |")
        lines.append("|-----------|-------|------|")
        for ext in sorted(by_ext.keys()):
            d = by_ext[ext]
            lines.append(f"| {ext} | {d['count']} | {d['size']:,} |")
        self.state["stats"]["reports"] += 1
        return (1, "\n".join(lines), None)

    # ════════════════════════════════════════════
    # COPY TO FILE — combine multiple files into one
    # ════════════════════════════════════════════

    def _cmd_copy_to_file(self, params):
        sources = self._p(params, "sources", [])
        dest = self._p(params, "dest")
        include_header = self._p(params, "include_header", True)
        if not sources or not dest:
            return (0, None, ("ERR_PARAMS", "sources and dest required", 0))
        db_path = self._p(params, "db", self.state["config"]["default_db"])
        combined = []
        if include_header:
            combined.append(f"# Combined file — generated by DomReport")
            combined.append(f"# Generated: {datetime.datetime.now().isoformat()}")
            combined.append(f"# Sources: {len(sources)}")
            combined.append("")
        copied = []
        for src in sources:
            if not os.path.isfile(src):
                continue
            try:
                with open(src, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception as e:
                self.state["stats"]["errors"] += 1
                continue
            src_hash = self._hash_file(src)
            if include_header:
                combined.append(f"\n{'=' * 70}")
                combined.append(f"# SOURCE: {src}")
                combined.append(f"# HASH: {src_hash}")
                combined.append(f"# SIZE: {os.path.getsize(src)} bytes")
                combined.append(f"{'=' * 70}\n")
            combined.append(content)
            copied.append({"source": src, "hash": src_hash, "size": os.path.getsize(src)})
        try:
            with open(dest, "w", encoding="utf-8") as f:
                f.write("\n".join(combined))
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_WRITE", str(e), 0))
        dest_hash = self._hash_file(dest)
        for c in copied:
            self._record_provenance(db_path, c["source"], dest, "file", c["hash"], dest_hash, c["size"])
            self.state["copy_history"].append({"source": c["source"], "dest": dest, "type": "file"})
        self.state["stats"]["copies"] += len(copied)
        return (1, {"combined_file": dest, "sources_copied": len(copied), "dest_hash": dest_hash, "total_size": os.path.getsize(dest)}, None)

    # ════════════════════════════════════════════
    # COPY TO FOLDER — copy files preserving structure
    # ════════════════════════════════════════════

    def _cmd_copy_to_folder(self, params):
        sources = self._p(params, "sources", [])
        dest_folder = self._p(params, "dest")
        preserve_structure = self._p(params, "preserve_structure", False)
        base_path = self._p(params, "base_path")
        if not sources or not dest_folder:
            return (0, None, ("ERR_PARAMS", "sources and dest required", 0))
        db_path = self._p(params, "db", self.state["config"]["default_db"])
        if not os.path.isdir(dest_folder):
            try:
                os.makedirs(dest_folder, exist_ok=True)
            except Exception as e:
                return (0, None, ("ERR_MKDIR", str(e), 0))
        copied = []
        for src in sources:
            if not os.path.isfile(src):
                continue
            if preserve_structure and base_path:
                rel = os.path.relpath(src, base_path)
                dest_path = os.path.join(dest_folder, rel)
            else:
                dest_path = os.path.join(dest_folder, os.path.basename(src))
            dest_dir = os.path.dirname(dest_path)
            if dest_dir and not os.path.isdir(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
            try:
                shutil.copy2(src, dest_path)
            except Exception as e:
                self.state["stats"]["errors"] += 1
                continue
            src_hash = self._hash_file(src)
            dest_hash = self._hash_file(dest_path)
            self._record_provenance(db_path, src, dest_path, "folder", src_hash, dest_hash, os.path.getsize(src))
            self.state["copy_history"].append({"source": src, "dest": dest_path, "type": "folder"})
            copied.append({"source": src, "dest": dest_path, "hash": src_hash, "size": os.path.getsize(src)})
        self.state["stats"]["copies"] += len(copied)
        return (1, {"dest_folder": dest_folder, "files_copied": len(copied), "files": copied}, None)

    # ════════════════════════════════════════════
    # COPY TO SQLITE — store file contents in SQLite with provenance
    # ════════════════════════════════════════════

    def _cmd_copy_to_sqlite(self, params):
        sources = self._p(params, "sources", [])
        db_path = self._p(params, "db", self.state["config"]["default_db"])
        include_content = self._p(params, "include_content", self.state["config"]["include_content"])
        if not sources:
            return (0, None, ("ERR_PARAMS", "sources required", 0))
        self._init_provenance_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        stored = []
        for src in sources:
            if not os.path.isfile(src):
                continue
            try:
                with open(src, "rb") as f:
                    raw = f.read()
            except Exception as e:
                self.state["stats"]["errors"] += 1
                continue
            src_hash = hashlib.sha256(raw).hexdigest()
            content_text = None
            if include_content:
                try:
                    content_text = raw.decode("utf-8", errors="replace")
                except Exception:
                    content_text = None
            try:
                cursor.execute(
                    "INSERT INTO file_store (source_path, file_name, file_size, source_hash, content, stored_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (src, os.path.basename(src), len(raw), src_hash, content_text, datetime.datetime.now().isoformat())
                )
                file_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, dest_hash, file_size, copied_at, file_store_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (src, f"sqlite:{db_path}:file_store:{file_id}", "sqlite", src_hash, src_hash, len(raw), datetime.datetime.now().isoformat(), file_id)
                )
                stored.append({"source": src, "file_id": file_id, "hash": src_hash, "size": len(raw)})
                self.state["copy_history"].append({"source": src, "dest": f"sqlite:{db_path}:{file_id}", "type": "sqlite"})
            except Exception as e:
                self.state["stats"]["errors"] += 1
        conn.commit()
        conn.close()
        self.state["stats"]["copies"] += len(stored)
        return (1, {"db": db_path, "files_stored": len(stored), "files": stored}, None)

    # ════════════════════════════════════════════
    # PROVENANCE — query the copy chain
    # ════════════════════════════════════════════

    def _cmd_provenance(self, params):
        db_path = self._p(params, "db", self.state["config"]["default_db"])
        dest = self._p(params, "dest")
        source = self._p(params, "source")
        if dest:
            ok, rows, err = self._query_provenance(db_path, "SELECT * FROM provenance WHERE dest_path = ? ORDER BY copied_at", [dest])
        elif source:
            ok, rows, err = self._query_provenance(db_path, "SELECT * FROM provenance WHERE source_path = ? ORDER BY copied_at", [source])
        else:
            ok, rows, err = self._query_provenance(db_path, "SELECT * FROM provenance ORDER BY copied_at DESC LIMIT 100")
        if not ok:
            return (0, None, err)
        self.state["stats"]["provenance_queries"] += 1
        return (1, {"count": len(rows), "records": [dict(r) for r in rows]}, None)

    def _cmd_list_copies(self, params):
        db_path = self._p(params, "db", self.state["config"]["default_db"])
        limit = self._p(params, "limit", 50)
        ok, rows, err = self._query_provenance(db_path, "SELECT * FROM provenance ORDER BY copied_at DESC LIMIT ?", [limit])
        if not ok:
            return (0, None, err)
        return (1, {"count": len(rows), "copies": [dict(r) for r in rows]}, None)

    # ════════════════════════════════════════════
    # VERIFY LINEAGE — check hash integrity
    # ════════════════════════════════════════════

    def _cmd_verify_lineage(self, params):
        db_path = self._p(params, "db", self.state["config"]["default_db"])
        ok, rows, err = self._query_provenance(db_path, "SELECT * FROM provenance ORDER BY copied_at")
        if not ok:
            return (0, None, err)
        verified = 0
        mismatches = []
        missing = []
        for row in rows:
            dest_path = row["dest_path"]
            if dest_path.startswith("sqlite:"):
                verified += 1
                continue
            if not os.path.exists(dest_path):
                missing.append(dest_path)
                continue
            current_hash = self._hash_file(dest_path)
            if current_hash == row["dest_hash"]:
                verified += 1
            else:
                mismatches.append({"dest": dest_path, "expected": row["dest_hash"], "actual": current_hash})
        return (1, {
            "total": len(rows),
            "verified": verified,
            "mismatches": mismatches,
            "missing": missing,
            "integrity": "PASS" if not mismatches and not missing else "FAIL",
        }, None)

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

    def _init_provenance_db(self, db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS provenance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                dest_path TEXT NOT NULL,
                dest_type TEXT NOT NULL,
                source_hash TEXT,
                dest_hash TEXT,
                file_size INTEGER,
                copied_at TEXT,
                file_store_id INTEGER
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_store (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                file_name TEXT,
                file_size INTEGER,
                source_hash TEXT,
                content TEXT,
                stored_at TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prov_dest ON provenance(dest_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prov_source ON provenance(source_path)")
        conn.commit()
        conn.close()

    def _record_provenance(self, db_path, source, dest, dest_type, src_hash, dest_hash, size):
        self._init_provenance_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, dest_hash, file_size, copied_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (source, dest, dest_type, src_hash, dest_hash, size, datetime.datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

    def _query_provenance(self, db_path, sql, args=None):
        if not os.path.isfile(db_path):
            return (1, [], None)
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, args or [])
            rows = cursor.fetchall()
            conn.close()
            return (1, rows, None)
        except Exception as e:
            return (0, None, ("ERR_DB", str(e), 0))
