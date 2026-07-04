#!/usr/bin/env python3
# [@GHOST]{file_path="core/Dom_Bcl/bcl_ir_bridge.py"
# date="2026-06-28" author="Cascade" session_id="bcl-bridge"
# context="Bridge script: IRCompiler output to SQLite/MySQL python_structure tables"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_ir_bridge.py" domain="BCL" authority="IrBridge"}
# [@SUMMARY]{summary="Bridge: takes IRCompiler output and writes to SQLite or MySQL. Multi-backend support."}
# [@CLASS]{class="IrBridge" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="init_schema" type="command"}
# [@METHOD]{method="store_file" type="command"}
# [@METHOD]{method="store_directory" type="command"}
# [@METHOD]{method="query_all" type="command"}
# [@METHOD]{method="query_methods" type="command"}
# [@METHOD]{method="query_edges" type="command"}
# [@METHOD]{method="query_violations" type="command"}
# [@METHOD]{method="query_domain" type="command"}
# [@METHOD]{method="query_dead_code" type="command"}
# [@METHOD]{method="stats" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

"""
IrBridge -- Bridge between IRCompiler output and database storage.

Takes the dict returned by IRCompiler.Run("compile_file", ...) and
writes it into python_structure, python_graph_edges, python_bcl_ir tables.

Backends:
  - sqlite (default, for testing) -- no server needed
  - mysql (for production) -- requires MySQL server

Usage:
  bridge = IrBridge(param={"backend": "sqlite", "db_path": "bcl_test.db"})
  bridge.Run("init_schema", {})
  bridge.Run("store_file", {"compiler_result": result_dict})
  bridge.Run("stats", {})
"""

import hashlib
import json
import os
import re
import sqlite3

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False


SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS python_structure (
    id              TEXT PRIMARY KEY,
    content_hash    TEXT NOT NULL,
    object_type     TEXT NOT NULL,
    object_name     TEXT NOT NULL,
    parent_id       TEXT,
    namespace       TEXT,
    filepath        TEXT,
    filename        TEXT,
    start_line      INTEGER,
    end_line        INTEGER,
    bcl_header      TEXT,
    bcl_ir          TEXT,
    ir_type         TEXT,
    graph_edges     TEXT,
    inheritance     TEXT,
    call_count      INTEGER DEFAULT 0,
    method_count    INTEGER DEFAULT 0,
    source_snippet  TEXT,
    signature       TEXT,
    imports         TEXT,
    description     TEXT,
    docstring       TEXT,
    violations      TEXT,
    violation_count INTEGER DEFAULT 0,
    compliant       INTEGER DEFAULT 1,
    complexity      INTEGER DEFAULT 0,
    max_nesting     INTEGER DEFAULT 0,
    branch_count    INTEGER DEFAULT 0,
    loop_count      INTEGER DEFAULT 0,
    has_print       INTEGER DEFAULT 0,
    has_self_underscore INTEGER DEFAULT 0,
    returns_tuple3  INTEGER DEFAULT 0,
    has_run         INTEGER DEFAULT 0,
    has_state       INTEGER DEFAULT 0,
    patterns        TEXT,
    domain          TEXT,
    sub_domain      TEXT,
    line_count      INTEGER,
    file_size       INTEGER,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS python_graph_edges (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       TEXT NOT NULL,
    target_id       TEXT,
    target_name     TEXT NOT NULL,
    edge_type       TEXT NOT NULL,
    call_lineno     INTEGER
);

CREATE TABLE IF NOT EXISTS python_bcl_ir (
    id              TEXT PRIMARY KEY,
    parent_id       TEXT,
    ir_type         TEXT NOT NULL,
    bcl_block       TEXT NOT NULL,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_parent ON python_structure(parent_id);
CREATE INDEX IF NOT EXISTS idx_type ON python_structure(object_type);
CREATE INDEX IF NOT EXISTS idx_domain ON python_structure(domain);
CREATE INDEX IF NOT EXISTS idx_namespace ON python_structure(namespace);
CREATE INDEX IF NOT EXISTS idx_compliant ON python_structure(compliant);
CREATE INDEX IF NOT EXISTS idx_name ON python_structure(object_name);
CREATE INDEX IF NOT EXISTS idx_edge_source ON python_graph_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edge_target ON python_graph_edges(target_id);
CREATE INDEX IF NOT EXISTS idx_edge_type ON python_graph_edges(edge_type);
CREATE INDEX IF NOT EXISTS idx_ir_parent ON python_bcl_ir(parent_id);
CREATE INDEX IF NOT EXISTS idx_ir_type ON python_bcl_ir(ir_type);
"""

SCHEMA_MYSQL = """
CREATE TABLE IF NOT EXISTS python_structure (
    id              VARCHAR(64) PRIMARY KEY,
    content_hash    VARCHAR(64) NOT NULL,
    object_type     VARCHAR(20) NOT NULL,
    object_name     VARCHAR(500) NOT NULL,
    parent_id       VARCHAR(64),
    namespace       TEXT,
    filepath        TEXT,
    filename        VARCHAR(500),
    start_line      INT,
    end_line        INT,
    bcl_header      TEXT,
    bcl_ir          TEXT,
    ir_type         VARCHAR(20),
    graph_edges     TEXT,
    inheritance     TEXT,
    call_count      INT DEFAULT 0,
    method_count    INT DEFAULT 0,
    source_snippet  TEXT,
    signature       TEXT,
    imports         TEXT,
    description     TEXT,
    docstring       TEXT,
    violations      TEXT,
    violation_count INT DEFAULT 0,
    compliant       BOOLEAN DEFAULT TRUE,
    complexity      INT DEFAULT 0,
    max_nesting     INT DEFAULT 0,
    branch_count    INT DEFAULT 0,
    loop_count      INT DEFAULT 0,
    has_print       BOOLEAN DEFAULT FALSE,
    has_self_underscore BOOLEAN DEFAULT FALSE,
    returns_tuple3  BOOLEAN DEFAULT FALSE,
    has_run         BOOLEAN DEFAULT FALSE,
    has_state       BOOLEAN DEFAULT FALSE,
    patterns        VARCHAR(200),
    domain          VARCHAR(50),
    sub_domain      VARCHAR(50),
    line_count      INT,
    file_size       BIGINT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_hash_type (content_hash, object_type),
    INDEX idx_parent (parent_id),
    INDEX idx_type (object_type),
    INDEX idx_domain (domain),
    INDEX idx_namespace (namespace(255)),
    INDEX idx_compliant (compliant),
    INDEX idx_name (object_name(255))
);

CREATE TABLE IF NOT EXISTS python_graph_edges (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    source_id       VARCHAR(64) NOT NULL,
    target_id       VARCHAR(64),
    target_name     VARCHAR(500) NOT NULL,
    edge_type       VARCHAR(20) NOT NULL,
    call_lineno     INT,
    INDEX idx_source (source_id),
    INDEX idx_target_id (target_id),
    INDEX idx_target_name (target_name(255)),
    INDEX idx_edge_type (edge_type)
);

CREATE TABLE IF NOT EXISTS python_bcl_ir (
    id              VARCHAR(64) PRIMARY KEY,
    parent_id       VARCHAR(64),
    ir_type         VARCHAR(20) NOT NULL,
    bcl_block       TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ir_parent (parent_id),
    INDEX idx_ir_type (ir_type)
);
"""


class IrBridge:
    """Bridge IRCompiler output to SQLite or MySQL."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "backend": "sqlite",
                "db_path": "bcl_ir_bridge.db",
                "mysql_host": "localhost",
                "mysql_user": "root",
                "mysql_password": "",
                "mysql_db": "vb_shared",
            },
            "conn": None,
            "rows_stored": 0,
            "edges_stored": 0,
            "ir_blocks_stored": 0,
            "errors": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "init_schema":
            return self.InitSchema(params)
        elif command == "store_file":
            return self.StoreFile(params)
        elif command == "store_directory":
            return self.StoreDirectory(params)
        elif command == "query_all":
            return self.QueryAll(params)
        elif command == "query_methods":
            return self.QueryMethods(params)
        elif command == "query_edges":
            return self.QueryEdges(params)
        elif command == "query_violations":
            return self.QueryViolations(params)
        elif command == "query_domain":
            return self.QueryDomain(params)
        elif command == "query_dead_code":
            return self.QueryDeadCode(params)
        elif command == "stats":
            return self.Stats(params)
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

    def _connect(self):
        backend = self.state["config"]["backend"]
        if backend == "sqlite":
            db_path = self.state["config"]["db_path"]
            self.state["conn"] = sqlite3.connect(db_path)
            self.state["conn"].row_factory = sqlite3.Row
            return (1, True, None)
        elif backend == "mysql":
            if not MYSQL_AVAILABLE:
                return (0, None, ("NO_MYSQL", "mysql.connector not installed", 0))
            cfg = self.state["config"]
            self.state["conn"] = mysql.connector.connect(
                host=cfg["mysql_host"],
                user=cfg["mysql_user"],
                password=cfg["mysql_password"],
                database=cfg["mysql_db"],
            )
            return (1, True, None)
        return (0, None, ("UNKNOWN_BACKEND", "Unknown backend: " + str(backend), 0))

    def _exec(self, sql, args=None):
        conn = self.state["conn"]
        cur = conn.cursor()
        if args:
            cur.execute(sql, args)
        else:
            cur.execute(sql)
        conn.commit()
        return cur

    def _executemany(self, sql, args_list):
        conn = self.state["conn"]
        cur = conn.cursor()
        cur.executemany(sql, args_list)
        conn.commit()
        return cur

    def _fetchall(self, sql, args=None):
        conn = self.state["conn"]
        cur = conn.cursor()
        if args:
            cur.execute(sql, args)
        else:
            cur.execute(sql)
        rows = cur.fetchall()
        return rows

    def InitSchema(self, params):
        conn_result = self._connect()
        if conn_result[0] == 0:
            return conn_result
        backend = self.state["config"]["backend"]
        schema = SCHEMA_MYSQL if backend == "mysql" else SCHEMA_SQLITE
        statements = [s.strip() for s in schema.split(";") if s.strip()]
        for stmt in statements:
            self._exec(stmt)
        return (1, {"schema_initialized": True, "backend": backend, "statements": len(statements)}, None)

    def _parse_ir_blocks(self, bcl_text):
        """Parse [@IRNODE]...[@ENDNODE] blocks into structured dicts."""
        blocks = []
        pattern = re.compile(r'\[@IRNODE\]\s*(.*?)\[@ENDNODE\]', re.DOTALL)
        for match in pattern.finditer(bcl_text):
            raw = match.group(0).strip()
            header = match.group(1).strip()
            fields = {}
            for line in header.split('\n'):
                line = line.strip()
                if line.startswith('#[@FIELD]'):
                    rest = line[len('#[@FIELD]'):].strip()
                    if '=' in rest:
                        k, v = rest.split('=', 1)
                        fields[k.strip()] = v.strip()
            node_type = None
            node_id = None
            parent_id = None
            for token in header.split('\n')[0].split():
                if token.startswith('type='):
                    node_type = token[5:]
                elif token.startswith('id='):
                    node_id = token[3:]
                elif token.startswith('parent='):
                    parent_id = token[7:]
            blocks.append({
                "raw": raw,
                "type": node_type,
                "id": node_id,
                "parent_id": parent_id,
                "fields": fields,
            })
        return blocks

    def _store_ir_block(self, block):
        if not block["id"]:
            return
        self._exec(
            "INSERT OR REPLACE INTO python_bcl_ir (id, parent_id, ir_type, bcl_block) VALUES (?, ?, ?, ?)",
            (block["id"], block.get("parent_id"), block.get("type", "unknown"), block["raw"]),
        )
        self.state["ir_blocks_stored"] += 1

    def _store_structure_row(self, row):
        self._exec(
            """INSERT OR REPLACE INTO python_structure (
                id, content_hash, object_type, object_name, parent_id, namespace,
                filepath, filename, start_line, end_line,
                bcl_header, bcl_ir, ir_type,
                graph_edges, inheritance, call_count, method_count,
                source_snippet, signature, imports,
                description, docstring,
                violations, violation_count, compliant,
                complexity, max_nesting, branch_count, loop_count,
                has_print, has_self_underscore, returns_tuple3, has_run, has_state,
                patterns, domain, sub_domain, line_count, file_size
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row.get("id"), row.get("content_hash", ""), row.get("object_type", ""),
                row.get("object_name", ""), row.get("parent_id"), row.get("namespace"),
                row.get("filepath"), row.get("filename"), row.get("start_line"), row.get("end_line"),
                row.get("bcl_header"), row.get("bcl_ir"), row.get("ir_type"),
                row.get("graph_edges"), row.get("inheritance"),
                row.get("call_count", 0), row.get("method_count", 0),
                row.get("source_snippet"), row.get("signature"), row.get("imports"),
                row.get("description"), row.get("docstring"),
                row.get("violations"), row.get("violation_count", 0), row.get("compliant", 1),
                row.get("complexity", 0), row.get("max_nesting", 0),
                row.get("branch_count", 0), row.get("loop_count", 0),
                row.get("has_print", 0), row.get("has_self_underscore", 0),
                row.get("returns_tuple3", 0), row.get("has_run", 0), row.get("has_state", 0),
                row.get("patterns"), row.get("domain"), row.get("sub_domain"),
                row.get("line_count"), row.get("file_size"),
            ),
        )
        self.state["rows_stored"] += 1

    def _store_edge(self, source_id, target_name, edge_type, call_lineno=None, target_id=None):
        self._exec(
            "INSERT INTO python_graph_edges (source_id, target_id, target_name, edge_type, call_lineno) VALUES (?, ?, ?, ?, ?)",
            (source_id, target_id, target_name, edge_type, call_lineno),
        )
        self.state["edges_stored"] += 1

    def StoreFile(self, params):
        result = self._p(params, "compiler_result")
        if result is None:
            return (0, None, ("MISSING_PARAM", "compiler_result required", 0))
        if self.state["conn"] is None:
            conn_result = self._connect()
            if conn_result[0] == 0:
                return conn_result
        filepath = result.get("filepath", "")
        file_id = result.get("file_id", "")
        file_hash = result.get("file_hash", "")
        bcl_text = result.get("bcl", "")
        symbols = result.get("symbols", {})
        imports = symbols.get("imports", [])
        classes = symbols.get("classes", [])
        edges = symbols.get("edges", [])

        blocks = self._parse_ir_blocks(bcl_text)

        file_block = None
        class_blocks = {}
        method_blocks = {}
        edge_blocks = []
        inherit_blocks = []
        violation_blocks = []

        for b in blocks:
            t = b.get("type")
            if t == "file":
                file_block = b
            elif t == "class":
                class_blocks[b.get("id")] = b
            elif t == "method":
                method_blocks[b.get("id")] = b
            elif t == "edge":
                edge_blocks.append(b)
            elif t == "inherit":
                inherit_blocks.append(b)
            elif t == "violate":
                violation_blocks.append(b)

        if file_block:
            f = file_block["fields"]
            row = {
                "id": file_id,
                "content_hash": file_hash,
                "object_type": "file",
                "object_name": os.path.basename(filepath),
                "parent_id": None,
                "namespace": os.path.basename(filepath).replace(".py", ""),
                "filepath": filepath,
                "filename": os.path.basename(filepath),
                "start_line": 1,
                "end_line": int(f.get("lines", 0)) if f.get("lines", "").isdigit() else None,
                "bcl_header": None,
                "bcl_ir": file_block["raw"],
                "ir_type": "file",
                "graph_edges": json.dumps([{"type": "contains", "target_id": c["id"]} for c in classes]),
                "inheritance": None,
                "call_count": len(edges),
                "method_count": result.get("method_count", 0),
                "source_snippet": None,
                "signature": None,
                "imports": json.dumps(imports),
                "description": None,
                "docstring": None,
                "violations": json.dumps([b["fields"] for b in violation_blocks]),
                "violation_count": result.get("violation_count", 0),
                "compliant": 1 if result.get("violation_count", 0) == 0 else 0,
                "complexity": 0,
                "max_nesting": 0,
                "branch_count": 0,
                "loop_count": 0,
                "has_print": 0,
                "has_self_underscore": 0,
                "returns_tuple3": 0,
                "has_run": 0,
                "has_state": 0,
                "patterns": None,
                "domain": None,
                "sub_domain": None,
                "line_count": int(f.get("lines", 0)) if f.get("lines", "").isdigit() else 0,
                "file_size": int(f.get("size", 0)) if str(f.get("size", "")).isdigit() else 0,
            }
            self._store_structure_row(row)
            self._store_ir_block(file_block)

        for cls in classes:
            cid = cls["id"]
            cname = cls["name"]
            cb = class_blocks.get(cid)
            cf = cb["fields"] if cb else {}
            methods = cls.get("methods", [])
            row = {
                "id": cid,
                "content_hash": file_hash,
                "object_type": "class",
                "object_name": cname,
                "parent_id": file_id,
                "namespace": "%s.%s" % (os.path.basename(filepath).replace(".py", ""), cname),
                "filepath": filepath,
                "filename": os.path.basename(filepath),
                "start_line": None,
                "end_line": None,
                "bcl_header": None,
                "bcl_ir": cb["raw"] if cb else None,
                "ir_type": "class",
                "graph_edges": json.dumps([{"type": "contains", "target_id": m["id"]} for m in methods]),
                "inheritance": json.dumps([b["fields"] for b in inherit_blocks if b["fields"].get("child") == cname]),
                "call_count": 0,
                "method_count": len(methods),
                "source_snippet": None,
                "signature": None,
                "imports": None,
                "description": None,
                "docstring": None,
                "violations": json.dumps([b["fields"] for b in violation_blocks if b.get("parent_id") == cid]),
                "violation_count": len([b for b in violation_blocks if b.get("parent_id") == cid]),
                "compliant": 1,
                "complexity": int(cf.get("wmc", 0)) if str(cf.get("wmc", "")).isdigit() else 0,
                "max_nesting": 0,
                "branch_count": 0,
                "loop_count": 0,
                "has_print": 0,
                "has_self_underscore": 0,
                "returns_tuple3": 0,
                "has_run": 1 if any(m["name"] == "Run" for m in methods) else 0,
                "has_state": 0,
                "patterns": None,
                "domain": cf.get("domain"),
                "sub_domain": cf.get("sub_domain"),
                "line_count": None,
                "file_size": None,
            }
            self._store_structure_row(row)
            if cb:
                self._store_ir_block(cb)

            for m in methods:
                mid = m["id"]
                mname = m["name"]
                mb = method_blocks.get(mid)
                mf = mb["fields"] if mb else {}
                m_violations = [b["fields"] for b in violation_blocks if b.get("parent_id") == mid]
                m_has_print = 1 if "print" in str(mf.get("patterns", "")) else 0
                m_has_self_under = 0
                m_returns_t3 = 1 if "tuple3" in str(mf.get("patterns", "")).lower() else 0
                m_complexity = int(mf.get("complexity", 0)) if str(mf.get("complexity", "")).isdigit() else 0
                m_nesting = int(mf.get("max_nesting", 0)) if str(mf.get("max_nesting", "")).isdigit() else 0
                m_branches = int(mf.get("branches", 0)) if str(mf.get("branches", "")).isdigit() else 0
                m_loops = int(mf.get("loops", 0)) if str(mf.get("loops", "")).isdigit() else 0
                m_calls = int(mf.get("calls", 0)) if str(mf.get("calls", "")).isdigit() else 0
                m_span = int(mf.get("span", 0)) if str(mf.get("span", "")).isdigit() else 0
                row = {
                    "id": mid,
                    "content_hash": file_hash,
                    "object_type": "method",
                    "object_name": "%s.%s" % (cname, mname),
                    "parent_id": cid,
                    "namespace": "%s.%s.%s" % (os.path.basename(filepath).replace(".py", ""), cname, mname),
                    "filepath": filepath,
                    "filename": os.path.basename(filepath),
                    "start_line": None,
                    "end_line": None,
                    "bcl_header": None,
                    "bcl_ir": mb["raw"] if mb else None,
                    "ir_type": "method",
                    "graph_edges": json.dumps([{"type": "calls", "target_name": c} for c in str(mf.get("call_targets", "")).split(",") if c]),
                    "inheritance": None,
                    "call_count": m_calls,
                    "method_count": 0,
                    "source_snippet": None,
                    "signature": mf.get("params", ""),
                    "imports": None,
                    "description": None,
                    "docstring": None,
                    "violations": json.dumps(m_violations),
                    "violation_count": len(m_violations),
                    "compliant": 1 if len(m_violations) == 0 else 0,
                    "complexity": m_complexity,
                    "max_nesting": m_nesting,
                    "branch_count": m_branches,
                    "loop_count": m_loops,
                    "has_print": m_has_print,
                    "has_self_underscore": m_has_self_under,
                    "returns_tuple3": m_returns_t3,
                    "has_run": 1 if mname == "Run" else 0,
                    "has_state": 1 if "self.state" in str(mf.get("patterns", "")) else 0,
                    "patterns": mf.get("patterns"),
                    "domain": cf.get("domain"),
                    "sub_domain": cf.get("sub_domain"),
                    "line_count": m_span,
                    "file_size": None,
                }
                self._store_structure_row(row)
                if mb:
                    self._store_ir_block(mb)

        for e in edges:
            self._store_edge(
                source_id=e.get("method_id", ""),
                target_name=e.get("callee", ""),
                edge_type="calls",
                call_lineno=None,
            )

        for ib in inherit_blocks:
            self._store_edge(
                source_id=file_id,
                target_name=ib["fields"].get("parent", ""),
                edge_type="inherits",
                call_lineno=None,
            )

        return (1, {
            "filepath": filepath,
            "rows_stored": self.state["rows_stored"],
            "edges_stored": self.state["edges_stored"],
            "ir_blocks_stored": self.state["ir_blocks_stored"],
            "block_count": result.get("block_count", 0),
        }, None)

    def StoreDirectory(self, params):
        dirpath = self._p(params, "dirpath")
        if dirpath is None:
            return (0, None, ("MISSING_PARAM", "dirpath required", 0))
        from bcl_compiler import IRCompiler
        compiler = IRCompiler()
        if self.state["conn"] is None:
            conn_result = self._connect()
            if conn_result[0] == 0:
                return conn_result
        compile_result = compiler.Run("compile_directory", {"dirpath": dirpath})
        if compile_result[0] == 0:
            return compile_result
        results = compile_result[1]["results"]
        stored = 0
        errors = []
        for r in results:
            if r.get("error"):
                errors.append({"filepath": r["filepath"], "error": r["error"]})
                continue
            store_result = self.StoreFile({"compiler_result": r})
            if store_result[0] == 1:
                stored += 1
            else:
                errors.append({"filepath": r["filepath"], "error": str(store_result[2])})
        return (1, {
            "compiled": compile_result[1]["compiled"],
            "skipped": compile_result[1]["skipped"],
            "stored": stored,
            "errors": errors,
        }, None)

    def QueryAll(self, params):
        if self.state["conn"] is None:
            conn_result = self._connect()
            if conn_result[0] == 0:
                return conn_result
        rows = self._fetchall("SELECT id, object_type, object_name, parent_id, domain, compliant FROM python_structure ORDER BY object_type, object_name")
        result = [dict(r) if hasattr(r, 'keys') else r for r in rows]
        return (1, result, None)

    def QueryMethods(self, params):
        if self.state["conn"] is None:
            conn_result = self._connect()
            if conn_result[0] == 0:
                return conn_result
        rows = self._fetchall("SELECT id, object_name, complexity, max_nesting, call_count, has_run, returns_tuple3, compliant FROM python_structure WHERE object_type = 'method' ORDER BY complexity DESC")
        result = [dict(r) if hasattr(r, 'keys') else r for r in rows]
        return (1, result, None)

    def QueryEdges(self, params):
        if self.state["conn"] is None:
            conn_result = self._connect()
            if conn_result[0] == 0:
                return conn_result
        rows = self._fetchall("SELECT source_id, target_id, target_name, edge_type, call_lineno FROM python_graph_edges ORDER BY edge_type, target_name")
        result = [dict(r) if hasattr(r, 'keys') else r for r in rows]
        return (1, result, None)

    def QueryViolations(self, params):
        if self.state["conn"] is None:
            conn_result = self._connect()
            if conn_result[0] == 0:
                return conn_result
        rows = self._fetchall("SELECT id, object_name, object_type, violations, violation_count FROM python_structure WHERE violation_count > 0 ORDER BY violation_count DESC")
        result = [dict(r) if hasattr(r, 'keys') else r for r in rows]
        return (1, result, None)

    def QueryDomain(self, params):
        domain = self._p(params, "domain")
        if self.state["conn"] is None:
            conn_result = self._connect()
            if conn_result[0] == 0:
                return conn_result
        if domain:
            rows = self._fetchall("SELECT id, object_name, object_type, domain, sub_domain FROM python_structure WHERE domain = ? ORDER BY object_type", (domain,))
        else:
            rows = self._fetchall("SELECT domain, object_type, COUNT(*) as cnt FROM python_structure WHERE domain IS NOT NULL GROUP BY domain, object_type ORDER BY domain")
        result = [dict(r) if hasattr(r, 'keys') else r for r in rows]
        return (1, result, None)

    def QueryDeadCode(self, params):
        if self.state["conn"] is None:
            conn_result = self._connect()
            if conn_result[0] == 0:
                return conn_result
        rows = self._fetchall("""
            SELECT ps.id, ps.object_name, ps.object_type
            FROM python_structure ps
            WHERE ps.object_type = 'method'
              AND ps.id NOT IN (SELECT target_id FROM python_graph_edges WHERE edge_type = 'calls' AND target_id IS NOT NULL)
            ORDER BY ps.object_name
        """)
        result = [dict(r) if hasattr(r, 'keys') else r for r in rows]
        return (1, result, None)

    def Stats(self, params):
        if self.state["conn"] is None:
            conn_result = self._connect()
            if conn_result[0] == 0:
                return conn_result
        total = self._fetchall("SELECT COUNT(*) FROM python_structure")[0][0]
        files = self._fetchall("SELECT COUNT(*) FROM python_structure WHERE object_type = 'file'")[0][0]
        classes = self._fetchall("SELECT COUNT(*) FROM python_structure WHERE object_type = 'class'")[0][0]
        methods = self._fetchall("SELECT COUNT(*) FROM python_structure WHERE object_type = 'method'")[0][0]
        edges = self._fetchall("SELECT COUNT(*) FROM python_graph_edges")[0][0]
        ir_blocks = self._fetchall("SELECT COUNT(*) FROM python_bcl_ir")[0][0]
        violations = self._fetchall("SELECT COUNT(*) FROM python_structure WHERE violation_count > 0")[0][0]
        domains = self._fetchall("SELECT domain, COUNT(*) as cnt FROM python_structure WHERE domain IS NOT NULL GROUP BY domain ORDER BY cnt DESC")
        domain_list = [{"domain": r[0], "count": r[1]} for r in domains]
        return (1, {
            "total_objects": total,
            "files": files,
            "classes": classes,
            "methods": methods,
            "edges": edges,
            "ir_blocks": ir_blocks,
            "objects_with_violations": violations,
            "domains": domain_list,
            "backend": self.state["config"]["backend"],
        }, None)


def main():
    import sys

    BCL_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(BCL_DIR, "bcl_ir_bridge.db")

    if len(sys.argv) < 2:
        sys.stderr.write("Usage: bcl_ir_bridge.py <command> [args]\n")
        sys.stderr.write("Commands:\n")
        sys.stderr.write("  test <file.py>       — compile one file, store to SQLite, show stats\n")
        sys.stderr.write("  dir <directory>      — compile all .py files, store to SQLite\n")
        sys.stderr.write("  stats                — show database stats\n")
        sys.stderr.write("  query methods        — show all methods by complexity\n")
        sys.stderr.write("  query edges          — show all graph edges\n")
        sys.stderr.write("  query violations     — show objects with violations\n")
        sys.stderr.write("  query domain [name]  — show domain distribution or filter by domain\n")
        sys.stderr.write("  query dead           — show methods with no incoming calls\n")
        sys.exit(1)

    cmd = sys.argv[1]
    bridge = IrBridge(param={"backend": "sqlite", "db_path": DB_PATH})

    if cmd == "test":
        if len(sys.argv) < 3:
            sys.stderr.write("Usage: bcl_ir_bridge.py test <file.py>\n")
            sys.exit(1)
        target = sys.argv[2]
        init_result = bridge.Run("init_schema", {})
        if init_result[0] == 0:
            sys.stderr.write("Schema init failed: %s\n" % str(init_result[2]))
            sys.exit(1)
        from bcl_compiler import IRCompiler
        compiler = IRCompiler()
        compile_result = compiler.Run("compile_file", {"filepath": target})
        if compile_result[0] == 0:
            sys.stderr.write("Compile failed: %s\n" % str(compile_result[2]))
            sys.exit(1)
        store_result = bridge.Run("store_file", {"compiler_result": compile_result[1]})
        if store_result[0] == 0:
            sys.stderr.write("Store failed: %s\n" % str(store_result[2]))
            sys.exit(1)
        stats_result = bridge.Run("stats", {})
        if stats_result[0] == 1:
            s = stats_result[1]
            sys.stdout.write("=== STORE RESULTS ===\n")
            sys.stdout.write("Backend: %s\n" % s["backend"])
            sys.stdout.write("Total objects: %d\n" % s["total_objects"])
            sys.stdout.write("  Files:   %d\n" % s["files"])
            sys.stdout.write("  Classes: %d\n" % s["classes"])
            sys.stdout.write("  Methods: %d\n" % s["methods"])
            sys.stdout.write("  Edges:   %d\n" % s["edges"])
            sys.stdout.write("  IR blocks: %d\n" % s["ir_blocks"])
            sys.stdout.write("  Violations: %d\n" % s["objects_with_violations"])
            if s["domains"]:
                sys.stdout.write("  Domains:\n")
                for d in s["domains"]:
                    sys.stdout.write("    %s: %d\n" % (d["domain"], d["count"]))

    elif cmd == "dir":
        if len(sys.argv) < 3:
            sys.stderr.write("Usage: bcl_ir_bridge.py dir <directory>\n")
            sys.exit(1)
        target = sys.argv[2]
        init_result = bridge.Run("init_schema", {})
        if init_result[0] == 0:
            sys.stderr.write("Schema init failed: %s\n" % str(init_result[2]))
            sys.exit(1)
        store_result = bridge.Run("store_directory", {"dirpath": target})
        if store_result[0] == 0:
            sys.stderr.write("Store failed: %s\n" % str(store_result[2]))
            sys.exit(1)
        r = store_result[1]
        sys.stdout.write("=== DIRECTORY RESULTS ===\n")
        sys.stdout.write("Compiled: %d\n" % r["compiled"])
        sys.stdout.write("Skipped:  %d\n" % r["skipped"])
        sys.stdout.write("Stored:   %d\n" % r["stored"])
        if r["errors"]:
            sys.stdout.write("Errors:   %d\n" % len(r["errors"]))
            for e in r["errors"][:10]:
                sys.stdout.write("  %s: %s\n" % (e["filepath"], e["error"]))
        stats_result = bridge.Run("stats", {})
        if stats_result[0] == 1:
            s = stats_result[1]
            sys.stdout.write("\n=== DATABASE STATS ===\n")
            sys.stdout.write("Total objects: %d\n" % s["total_objects"])
            sys.stdout.write("  Files:   %d\n" % s["files"])
            sys.stdout.write("  Classes: %d\n" % s["classes"])
            sys.stdout.write("  Methods: %d\n" % s["methods"])
            sys.stdout.write("  Edges:   %d\n" % s["edges"])
            sys.stdout.write("  IR blocks: %d\n" % s["ir_blocks"])

    elif cmd == "stats":
        stats_result = bridge.Run("stats", {})
        if stats_result[0] == 1:
            s = stats_result[1]
            sys.stdout.write("=== DATABASE STATS ===\n")
            sys.stdout.write("Backend: %s\n" % s["backend"])
            sys.stdout.write("Total objects: %d\n" % s["total_objects"])
            sys.stdout.write("  Files:   %d\n" % s["files"])
            sys.stdout.write("  Classes: %d\n" % s["classes"])
            sys.stdout.write("  Methods: %d\n" % s["methods"])
            sys.stdout.write("  Edges:   %d\n" % s["edges"])
            sys.stdout.write("  IR blocks: %d\n" % s["ir_blocks"])
            sys.stdout.write("  Violations: %d\n" % s["objects_with_violations"])
            if s["domains"]:
                sys.stdout.write("  Domains:\n")
                for d in s["domains"]:
                    sys.stdout.write("    %s: %d\n" % (d["domain"], d["count"]))

    elif cmd == "query":
        if len(sys.argv) < 3:
            sys.stderr.write("Usage: bcl_ir_bridge.py query <methods|edges|violations|domain|dead>\n")
            sys.exit(1)
        sub = sys.argv[2]
        if sub == "methods":
            r = bridge.Run("query_methods", {})
            if r[0] == 1:
                for row in r[1]:
                    sys.stdout.write("  %-40s complexity=%s nesting=%s calls=%s run=%s t3=%s ok=%s\n" % (
                        row.get("object_name", "?"), row.get("complexity", 0),
                        row.get("max_nesting", 0), row.get("call_count", 0),
                        row.get("has_run", 0), row.get("returns_tuple3", 0),
                        row.get("compliant", 0),
                    ))
        elif sub == "edges":
            r = bridge.Run("query_edges", {})
            if r[0] == 1:
                for row in r[1]:
                    sys.stdout.write("  %s -> %s (%s)\n" % (
                        row.get("source_id", "?")[:12], row.get("target_name", "?"),
                        row.get("edge_type", "?"),
                    ))
        elif sub == "violations":
            r = bridge.Run("query_violations", {})
            if r[0] == 1:
                for row in r[1]:
                    sys.stdout.write("  %-40s violations=%s\n" % (
                        row.get("object_name", "?"), row.get("violation_count", 0),
                    ))
        elif sub == "domain":
            domain = sys.argv[3] if len(sys.argv) > 3 else None
            r = bridge.Run("query_domain", {"domain": domain})
            if r[0] == 1:
                for row in r[1]:
                    if domain:
                        sys.stdout.write("  %-40s %s %s\n" % (
                            row.get("object_name", "?"), row.get("object_type", "?"),
                            row.get("domain", "?"),
                        ))
                    else:
                        sys.stdout.write("  %-20s %s: %d\n" % (
                            row.get("domain", "?"), row.get("object_type", "?"), row.get("cnt", 0),
                        ))
        elif sub == "dead":
            r = bridge.Run("query_dead_code", {})
            if r[0] == 1:
                sys.stdout.write("Dead code (no incoming call edges):\n")
                for row in r[1]:
                    sys.stdout.write("  %s (%s)\n" % (row.get("object_name", "?"), row.get("id", "?")[:12]))
                if not r[1]:
                    sys.stdout.write("  (none found)\n")
        else:
            sys.stderr.write("Unknown query: %s\n" % sub)
            sys.exit(1)

    else:
        sys.stderr.write("Unknown command: %s\n" % cmd)
        sys.exit(1)


if __name__ == "__main__":
    main()
