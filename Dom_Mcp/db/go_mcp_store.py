#!/usr/bin/env python3
"""
#[@GHOST]{[@file<go_mcp_store.py>][@domain<Dom_Mcp>][@role<code_store>][@auth<cascade>][@date<2026-06-28>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<code_store>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
#[@SUMMARY]{GoMcpStore — SQLite-backed store for Go MCP server source code. Ingests cloned repos into DB tables, eliminates file sprawl. Query/modify/assemble code from DB instead of filesystem.}
#[@CLASS]{GoMcpStore}
#[@METHOD]{Run,init,ingest_repo,ingest_dir,list_servers,get_file,update_file,search_code,read_state,set_config}

GoMcpStore — SQLite code store for Go MCP server source code.

WHAT IT DOES:
  - Creates SQLite DB with tables: go_servers, go_files, go_exports
  - Ingests cloned Go repos into the DB (recursive walk, .go files + configs)
  - Provides query/search API to work with code from DB, not filesystem
  - Eliminates file sprawl — one DB file, all Go MCP code

SCHEMA:
  go_servers:  id, name, source_repo, cloned_path, ingested_at, description, build_cmd, binary_path
  go_files:    id, server_id, file_path, content, line_count, file_type, ingested_at
  go_exports:  id, server_id, file_id, symbol_name, symbol_type, signature, line_number

USAGE:
  from Dom_Mcp.db.go_mcp_store import GoMcpStore
  store = GoMcpStore()
  store.Run("init", {})
  store.Run("ingest_repo", {"name": "taskplanner", "path": "/path/to/clone"})
  store.Run("list_servers", {})
  store.Run("search_code", {"query": "func.*Tool"})
  store.Run("get_file", {"server": "taskplanner", "file_path": "main.go"})
"""

import os
import re
import sqlite3
import datetime


class GoMcpStore:
    DB_PATH = os.path.expanduser(
        "~/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/db/go_mcp_store.db"
    )
    FILE_EXTENSIONS = {".go", ".mod", ".sum", ".toml", ".yaml", ".yml", ".json", ".md", ".txt"}
    MAX_FILE_SIZE = 500000

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {"db_path": self.DB_PATH},
            "stats": {"servers": 0, "files": 0, "exports": 0},
            "db_conn": None,
            "db_cur": None,
        }
        if db:
            self.state["config"]["db_path"] = db
        if param and "db_path" in param:
            self.state["config"]["db_path"] = param["db_path"]

    def Run(self, command, params=None):
        dispatch = {
            "init": self._cmd_init,
            "ingest_repo": self._cmd_ingest_repo,
            "ingest_all": self._cmd_ingest_all,
            "list_servers": self._cmd_list_servers,
            "get_file": self._cmd_get_file,
            "update_file": self._cmd_update_file,
            "search_code": self._cmd_search_code,
            "list_files": self._cmd_list_files,
            "list_exports": self._cmd_list_exports,
            "delete_server": self._cmd_delete_server,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "Unknown command: %s" % command, 0))
        return handler(params or {})

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        if not params:
            return (0, None, ("ERR_PARAMS", "config values required", 0))
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def _connect(self):
        path = self.state["config"]["db_path"]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        self.state["db_conn"] = conn
        self.state["db_cur"] = conn.cursor()
        return conn

    def _close(self):
        if self.state["db_cur"]:
            self.state["db_cur"].close()
        if self.state["db_conn"]:
            self.state["db_conn"].close()
        self.state["db_conn"] = None
        self.state["db_cur"] = None

    def _cmd_init(self, params):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS go_servers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                source_repo TEXT,
                cloned_path TEXT,
                ingested_at TEXT,
                description TEXT,
                build_cmd   TEXT,
                binary_path TEXT,
                file_count  INTEGER DEFAULT 0,
                total_lines INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS go_files (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id   INTEGER NOT NULL,
                file_path   TEXT NOT NULL,
                content     TEXT NOT NULL,
                line_count  INTEGER DEFAULT 0,
                file_type   TEXT,
                ingested_at TEXT,
                FOREIGN KEY (server_id) REFERENCES go_servers(id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS go_exports (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id   INTEGER NOT NULL,
                file_id     INTEGER NOT NULL,
                symbol_name TEXT NOT NULL,
                symbol_type TEXT,
                signature   TEXT,
                line_number INTEGER,
                FOREIGN KEY (server_id) REFERENCES go_servers(id) ON DELETE CASCADE,
                FOREIGN KEY (file_id) REFERENCES go_files(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_files_server ON go_files(server_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_exports_server ON go_exports(server_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON go_files(file_path)")
        conn.commit()
        self._close()
        return (1, {"initialized": True, "db_path": self.state["config"]["db_path"]}, None)

    def _extract_exports(self, content):
        exports = []
        lines = content.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("func "):
                m = re.match(r'func\s+(?:\([^)]*\)\s+)?([A-Z]\w*)\s*\(', stripped)
                if m:
                    name = m.group(1)
                    sig = stripped[:120]
                    exports.append({"name": name, "type": "func", "signature": sig, "line": i + 1})
                else:
                    m2 = re.match(r'func\s+([a-z]\w*)\s*\(', stripped)
                    if m2:
                        exports.append({"name": m2.group(1), "type": "func_private", "signature": stripped[:120], "line": i + 1})
            elif stripped.startswith("type ") and "struct" in stripped:
                m = re.match(r'type\s+([A-Z]\w*)\s+struct', stripped)
                if m:
                    exports.append({"name": m.group(1), "type": "struct", "signature": stripped[:120], "line": i + 1})
            elif stripped.startswith("type ") and "interface" in stripped:
                m = re.match(r'type\s+([A-Z]\w*)\s+interface', stripped)
                if m:
                    exports.append({"name": m.group(1), "type": "interface", "signature": stripped[:120], "line": i + 1})
            elif stripped.startswith("var ") and re.match(r'var\s+([A-Z]\w*)', stripped):
                m = re.match(r'var\s+([A-Z]\w*)', stripped)
                if m:
                    exports.append({"name": m.group(1), "type": "var", "signature": stripped[:120], "line": i + 1})
            elif stripped.startswith("const ") and re.match(r'const\s+([A-Z]\w*)', stripped):
                m = re.match(r'const\s+([A-Z]\w*)', stripped)
                if m:
                    exports.append({"name": m.group(1), "type": "const", "signature": stripped[:120], "line": i + 1})
        return exports

    def _cmd_ingest_repo(self, params):
        name = self._p(params, "name")
        path = self._p(params, "path")
        source_repo = self._p(params, "source_repo", "")
        description = self._p(params, "description", "")
        if not name or not path:
            return (0, None, ("ERR_PARAMS", "name and path required", 0))
        if not os.path.isdir(path):
            return (0, None, ("ERR_NOTFOUND", "path does not exist: %s" % path, 0))

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT id FROM go_servers WHERE name = ?", (name,))
        existing = cur.fetchone()
        if existing:
            server_id = existing["id"]
            cur.execute("DELETE FROM go_files WHERE server_id = ?", (server_id,))
            cur.execute("DELETE FROM go_exports WHERE server_id = ?", (server_id,))
        else:
            cur.execute(
                "INSERT INTO go_servers (name, source_repo, cloned_path, ingested_at, description) VALUES (?, ?, ?, ?, ?)",
                (name, source_repo, path, datetime.datetime.now().isoformat(), description)
            )
            server_id = cur.lastrowid

        file_count = 0
        total_lines = 0
        skip_dirs = {".git", "node_modules", "vendor", ".idea", ".vscode", "dist", "build"}

        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in self.FILE_EXTENSIONS and fname not in ("Makefile", "Dockerfile", ".gitignore", "LICENSE"):
                    continue
                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, path)
                try:
                    fsize = os.path.getsize(fpath)
                    if fsize > self.MAX_FILE_SIZE:
                        continue
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except Exception:
                    continue
                line_count = content.count("\n") + 1
                file_type = ext.lstrip(".") if ext else "plain"
                cur.execute(
                    "INSERT INTO go_files (server_id, file_path, content, line_count, file_type, ingested_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (server_id, rel_path, content, line_count, file_type, datetime.datetime.now().isoformat())
                )
                file_id = cur.lastrowid
                file_count += 1
                total_lines += line_count
                if ext == ".go":
                    exports = self._extract_exports(content)
                    for exp in exports:
                        cur.execute(
                            "INSERT INTO go_exports (server_id, file_id, symbol_name, symbol_type, signature, line_number) VALUES (?, ?, ?, ?, ?, ?)",
                            (server_id, file_id, exp["name"], exp["type"], exp["signature"], exp["line"])
                        )

        cur.execute(
            "UPDATE go_servers SET file_count = ?, total_lines = ? WHERE id = ?",
            (file_count, total_lines, server_id)
        )
        conn.commit()
        self._close()
        self.state["stats"]["servers"] += 1
        self.state["stats"]["files"] += file_count
        return (1, {
            "server": name,
            "server_id": server_id,
            "files_ingested": file_count,
            "total_lines": total_lines,
        }, None)

    def _cmd_ingest_all(self, params):
        base = self._p(params, "base_path", os.path.expanduser("~/Qdrant_mysql_mlx_vector_engine/Dom_Mcp"))
        results = []
        if not os.path.isdir(base):
            return (0, None, ("ERR_NOTFOUND", "base path not found: %s" % base, 0))
        for entry in os.listdir(base):
            full = os.path.join(base, entry)
            if not os.path.isdir(full):
                continue
            if entry in ("db", "dom_mcp"):
                continue
            if entry.endswith("-go") or entry.endswith("-mcp"):
                ok, data, err = self._cmd_ingest_repo({
                    "name": entry,
                    "path": full,
                    "source_repo": "",
                    "description": entry,
                })
                results.append({"server": entry, "ok": ok, "data": data, "error": err})
        return (1, {"results": results}, None)

    def _cmd_list_servers(self, params):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM go_servers ORDER BY name")
        rows = cur.fetchall()
        servers = []
        for row in rows:
            servers.append({
                "id": row["id"],
                "name": row["name"],
                "source_repo": row["source_repo"],
                "file_count": row["file_count"],
                "total_lines": row["total_lines"],
                "ingested_at": row["ingested_at"],
                "description": row["description"],
            })
        self._close()
        return (1, servers, None)

    def _cmd_get_file(self, params):
        server = self._p(params, "server")
        file_path = self._p(params, "file_path")
        if not server or not file_path:
            return (0, None, ("ERR_PARAMS", "server and file_path required", 0))
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT f.* FROM go_files f
            JOIN go_servers s ON f.server_id = s.id
            WHERE s.name = ? AND f.file_path = ?
        """, (server, file_path))
        row = cur.fetchone()
        self._close()
        if not row:
            return (0, None, ("ERR_NOTFOUND", "file not found", 0))
        return (1, {
            "file_path": row["file_path"],
            "content": row["content"],
            "line_count": row["line_count"],
            "file_type": row["file_type"],
        }, None)

    def _cmd_update_file(self, params):
        server = self._p(params, "server")
        file_path = self._p(params, "file_path")
        content = self._p(params, "content")
        if not server or not file_path or content is None:
            return (0, None, ("ERR_PARAMS", "server, file_path, content required", 0))
        conn = self._connect()
        cur = conn.cursor()
        line_count = content.count("\n") + 1
        cur.execute("""
            UPDATE go_files SET content = ?, line_count = ?
            WHERE server_id = (SELECT id FROM go_servers WHERE name = ?)
            AND file_path = ?
        """, (content, line_count, server, file_path))
        changes = cur.rowcount
        conn.commit()
        self._close()
        if changes == 0:
            return (0, None, ("ERR_NOTFOUND", "file not found", 0))
        return (1, {"updated": True, "file_path": file_path, "line_count": line_count}, None)

    def _cmd_search_code(self, params):
        query = self._p(params, "query")
        server = self._p(params, "server", None)
        if not query:
            return (0, None, ("ERR_PARAMS", "query required", 0))
        conn = self._connect()
        cur = conn.cursor()
        if server:
            cur.execute("""
                SELECT f.file_path, f.content, s.name as server_name
                FROM go_files f
                JOIN go_servers s ON f.server_id = s.id
                WHERE s.name = ? AND f.content LIKE ?
                ORDER BY f.file_path
            """, (server, "%" + query + "%"))
        else:
            cur.execute("""
                SELECT f.file_path, f.content, s.name as server_name
                FROM go_files f
                JOIN go_servers s ON f.server_id = s.id
                WHERE f.content LIKE ?
                ORDER BY s.name, f.file_path
            """, ("%" + query + "%",))
        rows = cur.fetchall()
        results = []
        for row in rows:
            lines = row["content"].split("\n")
            matches = []
            for i, line in enumerate(lines):
                if query.lower() in line.lower():
                    start = max(0, i - 1)
                    end = min(len(lines), i + 2)
                    matches.append({
                        "line": i + 1,
                        "context": "\n".join(lines[start:end]),
                    })
            if matches:
                results.append({
                    "server": row["server_name"],
                    "file_path": row["file_path"],
                    "match_count": len(matches),
                    "matches": matches[:10],
                })
        self._close()
        return (1, results, None)

    def _cmd_list_files(self, params):
        server = self._p(params, "server")
        if not server:
            return (0, None, ("ERR_PARAMS", "server required", 0))
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT f.file_path, f.line_count, f.file_type
            FROM go_files f
            JOIN go_servers s ON f.server_id = s.id
            WHERE s.name = ?
            ORDER BY f.file_path
        """, (server,))
        rows = cur.fetchall()
        files = [{"file_path": r["file_path"], "line_count": r["line_count"], "file_type": r["file_type"]} for r in rows]
        self._close()
        return (1, files, None)

    def _cmd_list_exports(self, params):
        server = self._p(params, "server")
        if not server:
            return (0, None, ("ERR_PARAMS", "server required", 0))
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT e.symbol_name, e.symbol_type, e.signature, e.line_number, f.file_path
            FROM go_exports e
            JOIN go_servers s ON e.server_id = s.id
            JOIN go_files f ON e.file_id = f.id
            WHERE s.name = ?
            ORDER BY f.file_path, e.line_number
        """, (server,))
        rows = cur.fetchall()
        exports = [{"symbol": r["symbol_name"], "type": r["symbol_type"], "signature": r["signature"], "line": r["line_number"], "file": r["file_path"]} for r in rows]
        self._close()
        return (1, exports, None)

    def _cmd_delete_server(self, params):
        server = self._p(params, "server")
        if not server:
            return (0, None, ("ERR_PARAMS", "server required", 0))
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM go_files WHERE server_id = (SELECT id FROM go_servers WHERE name = ?)", (server,))
        cur.execute("DELETE FROM go_exports WHERE server_id = (SELECT id FROM go_servers WHERE name = ?)", (server,))
        cur.execute("DELETE FROM go_servers WHERE name = ?", (server,))
        changes = cur.rowcount
        conn.commit()
        self._close()
        if changes == 0:
            return (0, None, ("ERR_NOTFOUND", "server not found", 0))
        return (1, {"deleted": True, "server": server}, None)
