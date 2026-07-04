#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     BCLObjectDatabase.py
# Domain:   BCL structured code object storage
# Authority: Code object database with BCL metadata as first-class columns
# DB:       SQLite (code_objects, bcl_metadata, object_relationships, source_versions)
# Binary:   python3 BCLObjectDatabase.py <command> [params...]
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Rules followed:
#   @ghost    — Ghost Header present
#   @vbsty    — VBStyle Header present
#   @clshdr   — Class Header present
#   @mthdr    — Method Header present on every method
#   @run      — Run(command, params) dispatch entry point
#   @disp     — dispatch internal, maps keys to methods
#   @t3       — all methods return Tuple3 (ok, data, error)
#   @errfmt   — error tuple (code, desc, 0)
#   @state    — self.state dict (config, db_path, results)
#   @noself   — no self._ variables
#   @pascal   — PascalCase class name
#   @upper    — UPPERCASE constants at class level
#   @ctor     — __init__(self, mem=None, db=None, param=None)
#   @print    — no print statements (only main prints)
#   @decorators — no decorators
#   @hardcode — DB path from params, not hardcoded
#   @params   — all methods accept data as parameters
#   @rdst     — ReadState returns config snapshot
#   @phelp    — _p helper extracts params by key
#   @dismap   — every dispatch key maps to exactly one method
#
# ARCHITECTURE
# ----------------------------------------------------------------------------
# Combines three architectural families:
#   STORAGE:    Recursive CTE Tree (#6) + Normalized Tables (#4)
#   MAPPING:    AST extraction maps every node to parent object (#12)
#   EXPORT:     Cursor Walk (#11) + Template Injection (#8)
#
# SCHEMA TABLES:
#   code_objects         — one row per code element (file/class/method/...)
#   bcl_metadata         — semantic BCL layer (domain/role/stage/priority)
#   object_relationships — graph edges (contains/calls/inherits)
#   source_versions      — revision history per object_id
#   ir_nodes             — raw BCL IR blocks (compat with bcl_ir_compiler.py)
# ============================================================================

import ast
import hashlib
import json
import os
import sqlite3
import sys
import datetime
from collections import Counter


# ============================================================================
# SCHEMA SQL — Normalized relational model (Approach #4)
# ============================================================================

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS code_objects (
    object_id      TEXT PRIMARY KEY,
    object_type    TEXT NOT NULL,
    object_name    TEXT NOT NULL,
    parent_id      TEXT,
    parent_name    TEXT,
    bcl_header     TEXT,
    source_code    TEXT,
    language       TEXT DEFAULT 'python',
    namespace      TEXT,
    start_line     INTEGER,
    end_line       INTEGER,
    signature      TEXT,
    visibility     TEXT,
    docstring      TEXT,
    imports        TEXT,
    dependencies   TEXT,
    tags           TEXT,
    status         TEXT DEFAULT 'stable',
    version        TEXT DEFAULT '1.0',
    checksum       TEXT,
    created_at     TEXT,
    updated_at     TEXT,
    FOREIGN KEY (parent_id) REFERENCES code_objects(object_id)
);

CREATE TABLE IF NOT EXISTS bcl_metadata (
    object_id      TEXT PRIMARY KEY,
    bcl_type       TEXT,
    bcl_domain     TEXT,
    bcl_purpose    TEXT,
    bcl_role       TEXT,
    bcl_owner      TEXT,
    bcl_priority   TEXT,
    bcl_stage      TEXT,
    bcl_state      TEXT,
    FOREIGN KEY (object_id) REFERENCES code_objects(object_id)
);

CREATE TABLE IF NOT EXISTS object_relationships (
    parent_id      TEXT NOT NULL,
    child_id       TEXT,
    parent_name    TEXT,
    child_name     TEXT NOT NULL,
    relationship   TEXT NOT NULL,
    call_lineno    INTEGER,
    FOREIGN KEY (parent_id) REFERENCES code_objects(object_id),
    FOREIGN KEY (child_id) REFERENCES code_objects(object_id)
);

CREATE TABLE IF NOT EXISTS source_versions (
    object_id      TEXT NOT NULL,
    revision       INTEGER NOT NULL,
    checksum       TEXT NOT NULL,
    source_code    TEXT,
    created_at     TEXT,
    PRIMARY KEY (object_id, revision),
    FOREIGN KEY (object_id) REFERENCES code_objects(object_id)
);

CREATE TABLE IF NOT EXISTS ir_nodes (
    id             TEXT,
    type           TEXT,
    parent         TEXT,
    filepath       TEXT,
    bcl            TEXT
);

CREATE TABLE IF NOT EXISTS ir_files (
    filepath       TEXT,
    file_id        TEXT,
    blocks         INTEGER,
    classes        INTEGER,
    methods        INTEGER,
    violations     INTEGER
);

CREATE INDEX IF NOT EXISTS idx_obj_parent ON code_objects(parent_id);
CREATE INDEX IF NOT EXISTS idx_obj_type   ON code_objects(object_type);
CREATE INDEX IF NOT EXISTS idx_obj_name   ON code_objects(object_name);
CREATE INDEX IF NOT EXISTS idx_rel_parent ON object_relationships(parent_id);
CREATE INDEX IF NOT EXISTS idx_rel_child  ON object_relationships(child_id);
CREATE INDEX IF NOT EXISTS idx_rel_type   ON object_relationships(relationship);
CREATE INDEX IF NOT EXISTS idx_bcl_domain ON bcl_metadata(bcl_domain);
CREATE INDEX IF NOT EXISTS idx_bcl_role   ON bcl_metadata(bcl_role);
"""

# Recursive CTE for hierarchy traversal (Approach #6: Recursive Tree)
TREE_CTE = """
WITH RECURSIVE ObjectTree(object_id, object_type, object_name, parent_id, depth, path) AS (
    SELECT object_id, object_type, object_name, parent_id, 0, object_name
    FROM code_objects WHERE object_id = ?
    UNION ALL
    SELECT c.object_id, c.object_type, c.object_name, c.parent_id, t.depth + 1, t.path || ' > ' || c.object_name
    FROM code_objects c JOIN ObjectTree t ON c.parent_id = t.object_id
    WHERE t.depth < 50
)
SELECT object_id, object_type, object_name, parent_id, depth, path
FROM ObjectTree ORDER BY depth, object_name;
"""

ANCESTORS_CTE = """
WITH RECURSIVE Ancestors(object_id, object_type, object_name, parent_id, depth) AS (
    SELECT object_id, object_type, object_name, parent_id, 0
    FROM code_objects WHERE object_id = ?
    UNION ALL
    SELECT p.object_id, p.object_type, p.object_name, p.parent_id, a.depth + 1
    FROM code_objects p JOIN Ancestors a ON a.parent_id = p.object_id
    WHERE a.depth < 50
)
SELECT object_id, object_type, object_name, depth FROM Ancestors ORDER BY depth;
"""


# ============================================================================
# DOMAIN KEYWORDS — reused from bcl_ir_config.py
# ============================================================================

DOMAIN_KEYWORDS = {
    "search": ["search", "query", "retrieve", "find", "lookup", "match"],
    "index": ["index", "idx", "ann", "hnsw", "faiss", "qdrant"],
    "embed": ["embed", "vector", "encoding", "codebert", "transformer"],
    "storage": ["store", "save", "load", "db", "sqlite", "disk", "file"],
    "config": ["config", "setting", "param", "option", "preference"],
    "gui": ["gui", "widget", "window", "panel", "button", "render", "display"],
    "parse": ["parse", "token", "lex", "syntax", "ast", "grammar"],
    "network": ["http", "socket", "request", "response", "api", "url", "client"],
    "security": ["auth", "encrypt", "decrypt", "hash", "password", "token", "key"],
    "audit": ["audit", "log", "trace", "monitor", "metric", "report"],
    "graph": ["graph", "node", "edge", "vertex", "traverse", "adjacency"],
    "memory": ["memory", "cache", "buffer", "pool", "mem"],
    "text": ["text", "string", "char", "word", "sentence", "document"],
    "ingest": ["ingest", "import", "consume", "batch", "pipeline", "feed"],
    "transform": ["transform", "convert", "map", "remap", "translate", "adapt"],
    "runtime": ["runtime", "execute", "run", "dispatch", "command", "schedule"],
    "validate": ["validate", "check", "verify", "assert", "test", "inspect"],
    "compress": ["compress", "zip", "gzip", "deflate", "archive", "pack"],
    "style": ["style", "theme", "color", "font", "css", "layout", "skin"],
    "workflow": ["workflow", "step", "stage", "flow", "process", "pipeline"],
}


# ============================================================================
# HELPER FUNCTIONS — pure functions, no class state
# ============================================================================

def StableId(filepath, node_type, name, lineno):
    """Generate stable 12-char hash ID for a code object."""
    raw = "{fp}:{nt}:{nm}:{ln}".format(fp=filepath, nt=node_type, nm=name, ln=lineno)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def Sha256(text):
    """Short SHA256 hash (16 chars) for source checksums."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def NowIso():
    """Current ISO timestamp (seconds precision)."""
    return datetime.datetime.now().isoformat(timespec="seconds")


def SourceSlice(lines, start, end):
    """Extract source lines from start to end (1-based)."""
    if start is None or end is None:
        return ""
    return "\n".join(lines[start - 1:end])


def InferVisibility(name):
    """Infer visibility from naming convention."""
    if name.startswith("__") and name.endswith("__"):
        return "public"
    if name.startswith("_"):
        return "private"
    return "public"


def InferDomain(name, class_name="", calls=None):
    """Infer BCL domain from name, class, and call targets."""
    text = " ".join([name, class_name] + list(calls or [])).lower()
    tokens = set(text.replace(".", " ").split())
    signals = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            for tok in tokens:
                if tok == kw or tok.startswith(kw):
                    signals.append(domain)
                    break
            else:
                continue
            break
    if not signals:
        return "unknown"
    return Counter(signals).most_common(1)[0][0]


def InferRole(name, class_name):
    """Infer BCL role from method name."""
    n = name.lower()
    if n.startswith("get") or n.startswith("fetch") or n.startswith("load"):
        return "reader"
    if n.startswith("set") or n.startswith("save") or n.startswith("store") or n.startswith("write"):
        return "writer"
    if n.startswith("parse") or n.startswith("lex") or n.startswith("token"):
        return "parser"
    if n.startswith("serialize") or n.startswith("encode") or n.startswith("dump"):
        return "serializer"
    if n.startswith("validate") or n.startswith("check") or n.startswith("verify"):
        return "validator"
    if n == "run" or n.startswith("execute") or n.startswith("dispatch"):
        return "dispatcher"
    if n.startswith("search") or n.startswith("query") or n.startswith("find"):
        return "searcher"
    if n == "__init__":
        return "constructor"
    return "method"


def InferStage(domain):
    """Map domain to pipeline stage."""
    stage_map = {
        "ingest": "ingest", "parse": "ingest", "transform": "ingest",
        "storage": "storage", "index": "storage", "memory": "storage",
        "search": "query", "graph": "query",
        "embed": "runtime", "runtime": "runtime", "validate": "runtime",
        "gui": "export", "style": "export", "audit": "export",
    }
    return stage_map.get(domain, "runtime")


def InferPriority(complexity, call_count):
    """Infer priority from complexity and call count."""
    if complexity >= 10 or call_count >= 15:
        return "high"
    if complexity >= 5 or call_count >= 8:
        return "medium"
    return "low"


def SignatureOf(node):
    """Generate signature string from AST node."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = ", ".join(a.arg for a in node.args.args)
        ret = ""
        if node.returns:
            try:
                ret = " -> " + ast.unparse(node.returns)
            except Exception:
                ret = ""
        async_kw = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        return "{a}def {n}({ar}){r}".format(a=async_kw, n=node.name, ar=args, r=ret)
    if isinstance(node, ast.ClassDef):
        bases = ", ".join(ast.unparse(b) for b in node.bases)
        if bases:
            return "class {n}({b})".format(n=node.name, b=bases)
        return "class {n}".format(n=node.name)
    return ""


def BclTuple(values):
    """Serialize a single BCL tuple: ("a";"b";92) → ('"a";"b";92')."""
    parts = []
    for v in values:
        if isinstance(v, (int, float)):
            parts.append(str(v))
        else:
            parts.append('"{v}"'.format(v=v))
    return "({parts})".format(parts=";".join(parts))


def BclContainer(name, tuples, children=None, indent=0):
    """Serialize a BCL container: [@name]{("k";"v")...[@child]{...}}.

    Follows BCL_DECISION_TREES.md format:
      - Container: [@name]{...}
      - Tuple: ("value1";"value2";weight) — semicolons inside parens
      - Weight: always LAST element in tuple
      - Nesting: containers can hold other containers
      - No colons in container names
      - No angle brackets in values
    """
    pad = "    " * indent
    lines = ["{pad}[@{n}]{{".format(pad=pad, n=name)]
    for t in tuples:
        lines.append("{pad}    {tup}".format(pad=pad, tup=BclTuple(t)))
    for child in (children or []):
        lines.append(child)
    lines.append("{pad}}}".format(pad=pad))
    return "\n".join(lines)


def BuildBclHeader(obj_type, name, namespace, signature, docstring,
                   domain, role, owner, priority, stage, state,
                   start_line, end_line, checksum, version="1.0"):
    """Build BCL header block in real [@name]{("k";"v")} bracket format.

    Format matches BCL_DECISION_TREES.md and bcl_parser.py BCLNode.to_bcl().
    Container name = object name (dispatch ID). Tuples are ("key";"value")
    pairs. Parseable by BCLTokenizer + BCLParser round-trip.
    """
    doc_one = (docstring or "").strip().split("\n")[0][:80] or "NONE"
    safe_name = name.replace(" ", "_").replace(":", "")
    tuples = [
        ["type", obj_type],
        ["name", name],
        ["namespace", namespace or "NONE"],
        ["signature", signature or "NONE"],
        ["domain", domain],
        ["role", role],
        ["owner", owner or "NONE"],
        ["priority", priority],
        ["stage", stage],
        ["state", state],
        ["lines", "{s}-{e}".format(s=start_line, e=end_line)],
        ["version", version],
        ["checksum", checksum],
        ["doc", doc_one],
    ]
    return (1, BclContainer(safe_name, tuples), None)


def CyclomaticComplexity(node):
    """Compute cyclomatic complexity of an AST function node."""
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler,
                              ast.With, ast.Assert, ast.Match)):
            complexity += 1
        if isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
    return complexity


def ExtractCalls(node):
    """Extract all call target names from an AST function node."""
    calls = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Attribute):
                calls.append(child.func.attr)
            elif isinstance(child.func, ast.Name):
                calls.append(child.func.id)
    return calls


def ExtractCallSites(node):
    """Extract call sites with line numbers from an AST function node."""
    sites = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            callee = None
            if isinstance(child.func, ast.Attribute):
                callee = child.func.attr
            elif isinstance(child.func, ast.Name):
                callee = child.func.id
            if callee:
                sites.append({"callee": callee, "lineno": getattr(child, "lineno", 0)})
    return sites


def ExtractImports(tree):
    """Extract all imports from an AST module tree."""
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imports.append({"module": a.name, "alias": a.asname})
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for a in node.names:
                imports.append({"module": mod, "name": a.name, "alias": a.asname})
    return imports


# ============================================================================
# CLASSES HEADER
# ----------------------------------------------------------------------------
# Class:  BCLObjectDatabase
# Domain: BCL structured code object storage
# Authority: Ingest Python source into structured object DB, query via
#            recursive CTE, export source/BCL via cursor walk
# Dependencies: ast, hashlib, json, os, sqlite3, datetime, collections
# DB: SQLite (code_objects, bcl_metadata, object_relationships, source_versions)
# ============================================================================


class BCLObjectDatabase:
    """Structured code object database with BCL metadata as first-class columns.

    Combines Recursive CTE Tree (#6), Normalized Tables (#4), AST Mapping (#12),
    and Cursor Walk export (#11) into one VBStyle-compliant class.
    """

    # ------------------------------------------------------------------------
    # UPPERCASE CONSTANTS
    # ------------------------------------------------------------------------
    VERSION = "1.0"
    DEFAULT_DB = "bcl_objects.db"
    MAX_TREE_DEPTH = 50

    # ------------------------------------------------------------------------
    # CONSTRUCTOR
    # ------------------------------------------------------------------------
    # Method: __init__
    # Purpose: Initialize BCLObjectDatabase with SQLite connection
    # Params:  mem=None (unused, VBStyle convention), db=None (DB path),
    #          param=None (extra config dict)
    # Returns: None (constructor)
    # ------------------------------------------------------------------------
    def __init__(self, mem=None, db=None, param=None):
        param = param if isinstance(param, dict) else {}
        self.state = {
            "db_path": db or param.get("db_path", self.DEFAULT_DB),
            "conn": None,
            "objects_ingested": 0,
            "relationships_ingested": 0,
            "ir_blocks_ingested": 0,
            "last_file": None,
            "errors": [],
        }

    # ------------------------------------------------------------------------
    # PARAM HELPER
    # ------------------------------------------------------------------------
    # Method: _p
    # Purpose: Extract param by key with default value
    # Params:  params (dict), key (str), default (any)
    # Returns: value from params or default
    # Rule:    @phelp
    # ------------------------------------------------------------------------
    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    # ------------------------------------------------------------------------
    # READ STATE
    # ------------------------------------------------------------------------
    # Method: ReadState
    # Purpose: Return current state snapshot
    # Params:  params (dict, optional)
    # Returns: Tuple3 (1, state_copy, None)
    # Rule:    @rdst
    # ------------------------------------------------------------------------
    def ReadState(self, params=None):
        return (1, dict(self.state), None)

    # ------------------------------------------------------------------------
    # SET CONFIG
    # ------------------------------------------------------------------------
    # Method: SetConfig
    # Purpose: Update config in state from params
    # Params:  params (dict with config keys)
    # Returns: Tuple3 (1, updated_state, None)
    # ------------------------------------------------------------------------
    def SetConfig(self, params=None):
        params = params or {}
        for key, value in params.items():
            if key in self.state:
                self.state[key] = value
        return (1, dict(self.state), None)

    # ------------------------------------------------------------------------
    # DISPATCH ENTRY POINT
    # ------------------------------------------------------------------------
    # Method: Run
    # Purpose: Dispatch entry point — route command to method
    # Params:  command (str), params (dict)
    # Returns: Tuple3 (ok, data, error)
    # Rule:    @run
    # ------------------------------------------------------------------------
    def Run(self, command, params=None):
        params = params or {}
        dispatch = {
            "ingest_file": self.IngestFile,
            "ingest_directory": self.IngestDirectory,
            "tree": self.QueryTree,
            "ancestors": self.QueryAncestors,
            "children": self.QueryChildren,
            "calls": self.QueryCalls,
            "callers": self.QueryCallers,
            "by_bcl": self.QueryByBcl,
            "by_type": self.QueryByType,
            "by_name": self.QueryByName,
            "edges": self.QueryEdges,
            "stats": self.QueryStats,
            "export_source": self.ExportSource,
            "export_file": self.ExportFile,
            "export_bcl": self.ExportBcl,
            "export_tree_bcl": self.ExportTreeBcl,
            "open": self.OpenDb,
            "close": self.CloseDb,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", "Unknown: {c}".format(c=command), 0))
        return handler(params)

    # ------------------------------------------------------------------------
    # DATABASE CONNECTION
    # ------------------------------------------------------------------------
    # Method: OpenDb
    # Purpose: Open SQLite connection and initialize schema
    # Params:  params (dict with optional db_path)
    # Returns: Tuple3 (1, conn, None) or (0, None, error)
    # ------------------------------------------------------------------------
    def OpenDb(self, params=None):
        params = params or {}
        db_path = self._p(params, "db_path", self.state["db_path"])
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.executescript(SCHEMA_SQL)
            self.state["conn"] = conn
            self.state["db_path"] = db_path
            return (1, conn, None)
        except Exception as e:
            err = ("DB_OPEN_ERROR", str(e), 0)
            self.state["errors"].append(str(e))
            return (0, None, err)

    # ------------------------------------------------------------------------
    # Method: CloseDb
    # Purpose: Close SQLite connection
    # Params:  params (dict, unused)
    # Returns: Tuple3 (1, True, None)
    # ------------------------------------------------------------------------
    def CloseDb(self, params=None):
        conn = self.state.get("conn")
        if conn:
            conn.close()
            self.state["conn"] = None
        return (1, True, None)

    # ------------------------------------------------------------------------
    # INGEST OPERATIONS (Mapping layer #12)
    # ------------------------------------------------------------------------
    # Method: IngestFile
    # Purpose: Parse a Python file and store all code objects in DB
    # Params:  params (dict with filepath)
    # Returns: Tuple3 (1, result_dict, None) or (0, None, error)
    # ------------------------------------------------------------------------
    def IngestFile(self, params=None):
        params = params or {}
        filepath = self._p(params, "filepath")
        if not filepath:
            return (0, None, ("MISSING_PARAM", "filepath required", 0))
        if not os.path.isfile(filepath):
            return (0, None, ("FILE_NOT_FOUND", filepath, 0))
        conn = self.state.get("conn")
        if conn is None:
            r = self.OpenDb()
            if not r[0]:
                return r
            conn = self.state["conn"]
        try:
            with open(filepath, "r") as f:
                source = f.read()
            objects, bcl_meta, relationships, ir_blocks = self.ExtractObjects(filepath, source)
            self.WriteObjects(conn, objects, bcl_meta, relationships, ir_blocks, filepath)
            result = {
                "filepath": filepath,
                "objects": len(objects),
                "relationships": len(relationships),
                "bcl_meta": len(bcl_meta),
                "ir_blocks": len(ir_blocks),
            }
            self.state["last_file"] = filepath
            self.state["objects_ingested"] += len(objects)
            self.state["relationships_ingested"] += len(relationships)
            self.state["ir_blocks_ingested"] += len(ir_blocks)
            return (1, result, None)
        except Exception as e:
            err = ("INGEST_ERROR", str(e), 0)
            self.state["errors"].append(str(e))
            return (0, None, err)

    # ------------------------------------------------------------------------
    # Method: IngestDirectory
    # Purpose: Walk a directory and ingest all .py files
    # Params:  params (dict with dirpath)
    # Returns: Tuple3 (1, results_list, None) or (0, None, error)
    # ------------------------------------------------------------------------
    def IngestDirectory(self, params=None):
        params = params or {}
        dirpath = self._p(params, "dirpath")
        if not dirpath:
            return (0, None, ("MISSING_PARAM", "dirpath required", 0))
        if not os.path.isdir(dirpath):
            return (0, None, ("DIR_NOT_FOUND", dirpath, 0))
        conn = self.state.get("conn")
        if conn is None:
            r = self.OpenDb()
            if not r[0]:
                return r
            conn = self.state["conn"]
        results = []
        for root, dirs, files in os.walk(dirpath):
            if any(skip in root for skip in (".git", "__pycache__", "node_modules")):
                continue
            for fn in sorted(files):
                if fn.endswith(".py"):
                    fp = os.path.join(root, fn)
                    r = self.IngestFile({"filepath": fp})
                    if r[0]:
                        results.append(r[1])
                    else:
                        results.append({"filepath": fp, "error": str(r[2])})
        return (1, results, None)

    # ------------------------------------------------------------------------
    # AST EXTRACTION (Mapping layer #12 — extract objects from AST)
    # ------------------------------------------------------------------------
    # Method: ExtractObjects
    # Purpose: Walk Python AST and extract structured code objects
    # Params:  filepath (str), source (str)
    # Returns: tuple (objects, bcl_meta, relationships, ir_blocks)
    # ------------------------------------------------------------------------
    def ExtractObjects(self, filepath, source):
        lines = source.splitlines()
        tree = ast.parse(source, filename=filepath)
        namespace = filepath.replace("/", ".").replace(".py", "")
        objects = []
        bcl_meta = []
        relationships = []
        ir_blocks = []

        file_id = StableId(filepath, "file", os.path.basename(filepath), 1)
        file_checksum = Sha256(source)
        now = NowIso()

        file_obj = {
            "object_id": file_id, "object_type": "file",
            "object_name": os.path.basename(filepath),
            "parent_id": None, "parent_name": None,
            "bcl_header": BuildBclHeader(
                "file", os.path.basename(filepath), namespace,
                None, ast.get_docstring(tree),
                "ingest", "module", None, "medium", "ingest", "stable",
                1, len(lines), file_checksum),
            "source_code": source, "language": "python",
            "namespace": namespace, "start_line": 1, "end_line": len(lines),
            "signature": None, "visibility": "public",
            "docstring": ast.get_docstring(tree),
            "imports": json.dumps(ExtractImports(tree)),
            "dependencies": "[]", "tags": "file",
            "status": "stable", "version": "1.0",
            "checksum": file_checksum, "created_at": now, "updated_at": now,
        }
        objects.append(file_obj)
        bcl_meta.append(self.MakeBclMeta(file_obj, "file", "ingest",
                                          "module container", "module", None, "medium", "ingest"))
        ir_blocks.append(self.IrFileBlock(file_id, file_obj))

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                self.ExtractClass(node, file_id, filepath, lines, namespace,
                                  objects, bcl_meta, relationships, ir_blocks, now)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.ExtractFunction(node, file_id, filepath, lines, namespace,
                                     objects, bcl_meta, relationships, ir_blocks, now)
            elif isinstance(node, ast.Assign):
                self.ExtractConstant(node, file_id, filepath, lines, namespace,
                                     objects, bcl_meta, relationships, ir_blocks, now,
                                     parent_name=os.path.basename(filepath))

        return (1, {"objects": objects, "bcl_meta": bcl_meta, "relationships": relationships, "ir_blocks": ir_blocks}, None)

    # ------------------------------------------------------------------------
    # Method: ExtractClass
    # Purpose: Extract a class object and its children from AST
    # Params:  node, file_id, filepath, lines, namespace, [output lists], now
    # Returns: None (appends to output lists)
    # ------------------------------------------------------------------------
    def ExtractClass(self, node, file_id, filepath, lines, namespace,
                     objects, bcl_meta, relationships, ir_blocks, now):
        class_id = StableId(filepath, "class", node.name, node.lineno)
        start = node.lineno
        end = getattr(node, "end_lineno", start)
        src = SourceSlice(lines, start, end)
        checksum = Sha256(src)
        bases = []
        for b in node.bases:
            try:
                bases.append(ast.unparse(b))
            except Exception:
                bases.append("?")
        doc = ast.get_docstring(node)
        domain = InferDomain(node.name)
        stage = InferStage(domain)

        class_obj = {
            "object_id": class_id, "object_type": "class",
            "object_name": node.name,
            "parent_id": file_id, "parent_name": os.path.basename(filepath),
            "bcl_header": BuildBclHeader(
                "class", node.name, namespace, SignatureOf(node), doc,
                domain, "class", None, "high", stage, "stable",
                start, end, checksum),
            "source_code": src, "language": "python",
            "namespace": namespace, "start_line": start, "end_line": end,
            "signature": SignatureOf(node), "visibility": InferVisibility(node.name),
            "docstring": doc, "imports": "[]",
            "dependencies": json.dumps(bases), "tags": domain,
            "status": "stable", "version": "1.0",
            "checksum": checksum, "created_at": now, "updated_at": now,
        }
        objects.append(class_obj)
        bcl_meta.append(self.MakeBclMeta(class_obj, "class", domain,
                                          (doc or "").split("\n")[0][:200] or "Class " + node.name,
                                          "class", None, "high", stage))
        relationships.append(self.MakeRel(file_id, class_id,
                                           os.path.basename(filepath), node.name, "contains", None))
        ir_blocks.append(self.IrClassBlock(class_id, file_id, class_obj, domain))

        for b in node.bases:
            base_name = b.id if isinstance(b, ast.Name) else (
                b.attr if isinstance(b, ast.Attribute) else "?")
            if base_name != "?":
                relationships.append(self.MakeRel(class_id, None, node.name, base_name, "inherits", None))

        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.ExtractMethod(child, class_id, node.name, filepath, lines, namespace,
                                   objects, bcl_meta, relationships, ir_blocks, now)
            elif isinstance(child, ast.Assign):
                self.ExtractConstant(child, class_id, filepath, lines, namespace,
                                     objects, bcl_meta, relationships, ir_blocks, now,
                                     parent_name=node.name)
        return (1, True, None)  # Tuple3

    # ------------------------------------------------------------------------
    # Method: ExtractMethod
    # Purpose: Extract a method object from AST
    # Params:  node, class_id, class_name, filepath, lines, namespace, [outputs], now
    # Returns: None (appends to output lists)
    # ------------------------------------------------------------------------
    def ExtractMethod(self, node, class_id, class_name, filepath, lines, namespace,
                      objects, bcl_meta, relationships, ir_blocks, now):
        method_id = StableId(filepath, "method", "{c}.{n}".format(c=class_name, n=node.name), node.lineno)
        start = node.lineno
        end = getattr(node, "end_lineno", start)
        src = SourceSlice(lines, start, end)
        checksum = Sha256(src)
        doc = ast.get_docstring(node)
        calls = ExtractCalls(node)
        domain = InferDomain(node.name, class_name, calls)
        role = InferRole(node.name, class_name)
        complexity = CyclomaticComplexity(node)
        priority = InferPriority(complexity, len(calls))
        stage = InferStage(domain)

        method_obj = {
            "object_id": method_id, "object_type": "method",
            "object_name": node.name,
            "parent_id": class_id, "parent_name": class_name,
            "bcl_header": BuildBclHeader(
                "method", node.name, namespace, SignatureOf(node), doc,
                domain, role, class_name, priority, stage, "stable",
                start, end, checksum),
            "source_code": src, "language": "python",
            "namespace": namespace, "start_line": start, "end_line": end,
            "signature": SignatureOf(node), "visibility": InferVisibility(node.name),
            "docstring": doc, "imports": "[]",
            "dependencies": json.dumps(calls[:20]), "tags": "{d},{r}".format(d=domain, r=role),
            "status": "stable", "version": "1.0",
            "checksum": checksum, "created_at": now, "updated_at": now,
        }
        objects.append(method_obj)
        bcl_meta.append(self.MakeBclMeta(method_obj, "method", domain,
                                          (doc or "").split("\n")[0][:200] or "Method " + node.name,
                                          role, class_name, priority, stage))
        relationships.append(self.MakeRel(class_id, method_id, class_name, node.name, "contains", None))
        for cs in ExtractCallSites(node):
            relationships.append(self.MakeRel(method_id, None,
                                               "{c}.{n}".format(c=class_name, n=node.name),
                                               cs["callee"], "calls", cs["lineno"]))
        ir_blocks.append(self.IrMethodBlock(method_id, class_id, method_obj, complexity, calls, "method"))
        return (1, True, None)  # Tuple3

    # ------------------------------------------------------------------------
    # Method: ExtractFunction
    # Purpose: Extract a standalone function object from AST
    # Params:  node, file_id, filepath, lines, namespace, [outputs], now
    # Returns: None (appends to output lists)
    # ------------------------------------------------------------------------
    def ExtractFunction(self, node, file_id, filepath, lines, namespace,
                        objects, bcl_meta, relationships, ir_blocks, now):
        fn_id = StableId(filepath, "function", node.name, node.lineno)
        start = node.lineno
        end = getattr(node, "end_lineno", start)
        src = SourceSlice(lines, start, end)
        checksum = Sha256(src)
        doc = ast.get_docstring(node)
        calls = ExtractCalls(node)
        domain = InferDomain(node.name, "", calls)
        role = InferRole(node.name, "")
        complexity = CyclomaticComplexity(node)
        priority = InferPriority(complexity, len(calls))
        stage = InferStage(domain)

        fn_obj = {
            "object_id": fn_id, "object_type": "function",
            "object_name": node.name,
            "parent_id": file_id, "parent_name": os.path.basename(filepath),
            "bcl_header": BuildBclHeader(
                "function", node.name, namespace, SignatureOf(node), doc,
                domain, role, None, priority, stage, "stable",
                start, end, checksum),
            "source_code": src, "language": "python",
            "namespace": namespace, "start_line": start, "end_line": end,
            "signature": SignatureOf(node), "visibility": InferVisibility(node.name),
            "docstring": doc, "imports": "[]",
            "dependencies": json.dumps(calls[:20]), "tags": "{d},{r}".format(d=domain, r=role),
            "status": "stable", "version": "1.0",
            "checksum": checksum, "created_at": now, "updated_at": now,
        }
        objects.append(fn_obj)
        bcl_meta.append(self.MakeBclMeta(fn_obj, "function", domain,
                                          (doc or "").split("\n")[0][:200] or "Function " + node.name,
                                          role, None, priority, stage))
        relationships.append(self.MakeRel(file_id, fn_id, os.path.basename(filepath), node.name, "contains", None))
        for cs in ExtractCallSites(node):
            relationships.append(self.MakeRel(fn_id, None, node.name, cs["callee"], "calls", cs["lineno"]))
        ir_blocks.append(self.IrMethodBlock(fn_id, file_id, fn_obj, complexity, calls, "function"))
        return (1, True, None)  # Tuple3

    # ------------------------------------------------------------------------
    # Method: ExtractConstant
    # Purpose: Extract a UPPERCASE constant assignment from AST
    # Params:  node, parent_id, filepath, lines, namespace, [outputs], now, parent_name
    # Returns: None (appends to output lists)
    # ------------------------------------------------------------------------
    def ExtractConstant(self, node, parent_id, filepath, lines, namespace,
                        objects, bcl_meta, relationships, ir_blocks, now, parent_name=None):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                const_id = StableId(filepath, "constant", target.id, node.lineno)
                try:
                    val_repr = ast.unparse(node.value)[:80]
                except Exception:
                    val_repr = "?"
                src = SourceSlice(lines, node.lineno, node.lineno)
                checksum = Sha256(src)
                const_obj = {
                    "object_id": const_id, "object_type": "constant",
                    "object_name": target.id,
                    "parent_id": parent_id, "parent_name": parent_name,
                    "bcl_header": BuildBclHeader(
                        "constant", target.id, namespace, None, None,
                        "config", "constant", parent_name, "low", "ingest", "stable",
                        node.lineno, node.lineno, checksum),
                    "source_code": src, "language": "python",
                    "namespace": namespace, "start_line": node.lineno, "end_line": node.lineno,
                    "signature": "{n} = {v}".format(n=target.id, v=val_repr),
                    "visibility": "public", "docstring": None,
                    "imports": "[]", "dependencies": "[]", "tags": "constant",
                    "status": "stable", "version": "1.0",
                    "checksum": checksum, "created_at": now, "updated_at": now,
                }
                objects.append(const_obj)
                bcl_meta.append(self.MakeBclMeta(const_obj, "constant", "config",
                                                  "Constant " + target.id, "constant", parent_name, "low", "ingest"))
                relationships.append(self.MakeRel(parent_id, const_id, parent_name, target.id, "contains", None))

        return (1, True, None)  # Tuple3
    # ------------------------------------------------------------------------
    # ROW BUILDERS
    # ------------------------------------------------------------------------
    # Method: MakeBclMeta
    # Purpose: Build a bcl_metadata row dict from an object
    # Params:  obj, bcl_type, domain, purpose, role, owner, priority, stage
    # Returns: dict
    # ------------------------------------------------------------------------
    def MakeBclMeta(self, obj, bcl_type, domain, purpose, role, owner, priority, stage):
        return (1, {
            "object_id": obj["object_id"], "bcl_type": bcl_type,
            "bcl_domain": domain, "bcl_purpose": purpose,
            "bcl_role": role, "bcl_owner": owner,
            "bcl_priority": priority, "bcl_stage": stage,
            "bcl_state": obj.get("status", "stable"),
        }, None)

    # ------------------------------------------------------------------------
    # Method: MakeRel
    # Purpose: Build an object_relationships row dict
    # Params:  parent_id, child_id, parent_name, child_name, relationship, call_lineno
    # Returns: dict
    # ------------------------------------------------------------------------
    def MakeRel(self, parent_id, child_id, parent_name, child_name, relationship, call_lineno):
        return (1, {
            "parent_id": parent_id, "child_id": child_id,
            "parent_name": parent_name, "child_name": child_name,
            "relationship": relationship, "call_lineno": call_lineno,
        }, None)

    # ------------------------------------------------------------------------
    # IR BLOCK BUILDERS (compat with bcl_ir_compiler.py)
    # ------------------------------------------------------------------------
    # Method: IrFileBlock
    # Purpose: Build BCL IR file node block
    # Params:  file_id, obj
    # Returns: str (BCL block)
    # ------------------------------------------------------------------------
    def IrFileBlock(self, file_id, obj):
        """Build BCL IR file node in real [@name]{("k";"v")} bracket format."""
        tuples = [
            ["type", "file"],
            ["id", file_id],
            ["file", obj["object_name"]],
            ["lines", str(obj["end_line"])],
            ["checksum", obj["checksum"]],
        ]
        return (1, BclContainer("ir_file_" + file_id, tuples), None)

    # ------------------------------------------------------------------------
    # Method: IrClassBlock
    # Purpose: Build BCL IR class node block in real BCL bracket format
    # Params:  class_id, file_id, obj, domain
    # Returns: str (BCL block)
    # ------------------------------------------------------------------------
    def IrClassBlock(self, class_id, file_id, obj, domain):
        tuples = [
            ["type", "class"],
            ["id", class_id],
            ["parent", file_id],
            ["name", obj["object_name"]],
            ["lines", "{s}-{e}".format(s=obj["start_line"], e=obj["end_line"])],
            ["domain", domain],
            ["checksum", obj["checksum"]],
        ]
        return (1, BclContainer("ir_class_" + class_id, tuples), None)

    # ------------------------------------------------------------------------
    # Method: IrMethodBlock
    # Purpose: Build BCL IR method/function node block in real BCL bracket format
    # Params:  m_id, parent_id, obj, complexity, calls, node_type
    # Returns: str (BCL block)
    # ------------------------------------------------------------------------
    def IrMethodBlock(self, m_id, parent_id, obj, complexity, calls, node_type):
        calls_str = ",".join(calls[:10]) if calls else "NONE"
        tuples = [
            ["type", node_type],
            ["id", m_id],
            ["parent", parent_id],
            ["name", obj["object_name"]],
            ["signature", obj["signature"] or "NONE"],
            ["lines", "{s}-{e}".format(s=obj["start_line"], e=obj["end_line"])],
            ["complexity", str(complexity)],
            ["calls", calls_str],
            ["checksum", obj["checksum"]],
        ]
        return (1, BclContainer("ir_{t}_{i}".format(t=node_type, i=m_id), tuples), None)

    # ------------------------------------------------------------------------
    # DATABASE WRITER (Storage layer #4 + #6)
    # ------------------------------------------------------------------------
    # Method: WriteObjects
    # Purpose: Write extracted objects, metadata, relationships, IR to DB
    # Params:  conn, objects, bcl_meta, relationships, ir_blocks, filepath
    # Returns: None (commits to conn)
    # ------------------------------------------------------------------------
    def WriteObjects(self, conn, objects, bcl_meta, relationships, ir_blocks, filepath):
        cur = conn.cursor()
        now = NowIso()

        for obj in objects:
            existing = cur.execute(
                "SELECT checksum FROM code_objects WHERE object_id=?",
                (obj["object_id"],)).fetchone()
            if existing:
                if existing["checksum"] != obj["checksum"]:
                    rev = cur.execute(
                        "SELECT COUNT(*)+1 FROM source_versions WHERE object_id=?",
                        (obj["object_id"],)).fetchone()[0]
                    old_src = cur.execute(
                        "SELECT source_code, checksum FROM code_objects WHERE object_id=?",
                        (obj["object_id"],)).fetchone()
                    cur.execute(
                        "INSERT OR REPLACE INTO source_versions VALUES (?,?,?,?,?)",
                        (obj["object_id"], rev, old_src["checksum"], old_src["source_code"], now))
                    obj["updated_at"] = now
                else:
                    continue
            cur.execute("""
                INSERT OR REPLACE INTO code_objects VALUES (
                    :object_id,:object_type,:object_name,:parent_id,:parent_name,
                    :bcl_header,:source_code,:language,:namespace,:start_line,:end_line,
                    :signature,:visibility,:docstring,:imports,:dependencies,:tags,
                    :status,:version,:checksum,:created_at,:updated_at)
            """, obj)

        for m in bcl_meta:
            cur.execute("""
                INSERT OR REPLACE INTO bcl_metadata VALUES (
                    :object_id,:bcl_type,:bcl_domain,:bcl_purpose,:bcl_role,
                    :bcl_owner,:bcl_priority,:bcl_stage,:bcl_state)
            """, m)

        for r in relationships:
            cur.execute("""
                INSERT OR IGNORE INTO object_relationships VALUES (?,?,?,?,?,?)
            """, (r["parent_id"], r["child_id"], r["parent_name"],
                  r["child_name"], r["relationship"], r["call_lineno"]))

        for block in ir_blocks:
            # Parse real BCL bracket format: [@name]{("type";"file")("id";"abc")...}
            node_id = node_type = parent_id = ""
            for line in block.split("\n"):
                line = line.strip()
                if line.startswith("(") and ")" in line:
                    inner = line[1:line.index(")")]
                    parts = inner.split(";")
                    if len(parts) >= 2:
                        key = parts[0].strip().strip('"')
                        val = parts[1].strip().strip('"')
                        if key == "type":
                            node_type = val
                        elif key == "id":
                            node_id = val
                        elif key == "parent":
                            parent_id = val
            cur.execute("INSERT OR REPLACE INTO ir_nodes VALUES (?,?,?,?,?)",
                        (node_id, node_type, parent_id, filepath, block))

        class_count = sum(1 for o in objects if o["object_type"] == "class")
        method_count = sum(1 for o in objects if o["object_type"] in ("method", "function"))
        file_id = objects[0]["object_id"] if objects else ""
        cur.execute("INSERT OR REPLACE INTO ir_files VALUES (?,?,?,?,?,?)",
                    (filepath, file_id, len(ir_blocks), class_count, method_count, 0))

        conn.commit()

    # ------------------------------------------------------------------------
    # QUERY LAYER (uses recursive CTEs — Approach #6)
    # ------------------------------------------------------------------------
    # Method: QueryTree
    # Purpose: Recursive CTE — all descendants of an object
    # Params:  params (dict with object_id)
    # Returns: Tuple3 (1, rows, None) or (0, None, error)
    # ------------------------------------------------------------------------
        return (1, True, None)
    def QueryTree(self, params=None):
        params = params or {}
        object_id = self._p(params, "object_id")
        if not object_id:
            return (0, None, ("MISSING_PARAM", "object_id required", 0))
        conn = self.state.get("conn")
        if conn is None:
            return (0, None, ("DB_CLOSED", "open db first", 0))
        rows = conn.execute(TREE_CTE, (object_id,)).fetchall()
        return (1, [dict(r) for r in rows], None)

    # ------------------------------------------------------------------------
    # Method: QueryAncestors
    # Purpose: Recursive CTE — walk up to all ancestors
    # Params:  params (dict with object_id)
    # Returns: Tuple3 (1, rows, None) or (0, None, error)
    # ------------------------------------------------------------------------
    def QueryAncestors(self, params=None):
        params = params or {}
        object_id = self._p(params, "object_id")
        if not object_id:
            return (0, None, ("MISSING_PARAM", "object_id required", 0))
        conn = self.state.get("conn")
        if conn is None:
            return (0, None, ("DB_CLOSED", "open db first", 0))
        rows = conn.execute(ANCESTORS_CTE, (object_id,)).fetchall()
        return (1, [dict(r) for r in rows], None)

    # ------------------------------------------------------------------------
    # Method: QueryChildren
    # Purpose: Direct children of an object
    # Params:  params (dict with object_id)
    # Returns: Tuple3 (1, rows, None) or (0, None, error)
    # ------------------------------------------------------------------------
    def QueryChildren(self, params=None):
        params = params or {}
        object_id = self._p(params, "object_id")
        if not object_id:
            return (0, None, ("MISSING_PARAM", "object_id required", 0))
        conn = self.state.get("conn")
        if conn is None:
            return (0, None, ("DB_CLOSED", "open db first", 0))
        rows = conn.execute(
            "SELECT * FROM code_objects WHERE parent_id=? ORDER BY start_line",
            (object_id,)).fetchall()
        return (1, [dict(r) for r in rows], None)

    # ------------------------------------------------------------------------
    # Method: QueryCalls
    # Purpose: Outgoing call edges from an object
    # Params:  params (dict with object_id)
    # Returns: Tuple3 (1, rows, None) or (0, None, error)
    # ------------------------------------------------------------------------
    def QueryCalls(self, params=None):
        params = params or {}
        object_id = self._p(params, "object_id")
        if not object_id:
            return (0, None, ("MISSING_PARAM", "object_id required", 0))
        conn = self.state.get("conn")
        if conn is None:
            return (0, None, ("DB_CLOSED", "open db first", 0))
        rows = conn.execute(
            "SELECT * FROM object_relationships WHERE parent_id=? AND relationship='calls'",
            (object_id,)).fetchall()
        return (1, [dict(r) for r in rows], None)

    # ------------------------------------------------------------------------
    # Method: QueryCallers
    # Purpose: Who calls this object (by name match)
    # Params:  params (dict with object_id)
    # Returns: Tuple3 (1, rows, None) or (0, None, error)
    # ------------------------------------------------------------------------
    def QueryCallers(self, params=None):
        params = params or {}
        object_id = self._p(params, "object_id")
        if not object_id:
            return (0, None, ("MISSING_PARAM", "object_id required", 0))
        conn = self.state.get("conn")
        if conn is None:
            return (0, None, ("DB_CLOSED", "open db first", 0))
        name_row = conn.execute(
            "SELECT object_name FROM code_objects WHERE object_id=?", (object_id,)).fetchone()
        if not name_row:
            return (1, [], None)
        rows = conn.execute(
            "SELECT * FROM object_relationships WHERE child_name=? AND relationship='calls'",
            (name_row["object_name"],)).fetchall()
        return (1, [dict(r) for r in rows], None)

    # ------------------------------------------------------------------------
    # Method: QueryByBcl
    # Purpose: Query BCL metadata by domain/role/stage/priority/etc
    # Params:  params (dict with filter keys like domain, role, stage, priority)
    # Returns: Tuple3 (1, rows, None) or (0, None, error)
    # ------------------------------------------------------------------------
    def QueryByBcl(self, params=None):
        params = params or {}
        conn = self.state.get("conn")
        if conn is None:
            return (0, None, ("DB_CLOSED", "open db first", 0))
        col_map = {
            "type": "bcl_type", "domain": "bcl_domain", "purpose": "bcl_purpose",
            "role": "bcl_role", "owner": "bcl_owner", "priority": "bcl_priority",
            "stage": "bcl_stage", "state": "bcl_state",
        }
        clauses = []
        vals = []
        for k, v in params.items():
            if k in ("object_id", "db_path", "filepath", "dirpath"):
                continue
            col = col_map.get(k, k if k.startswith("bcl_") else "bcl_" + k)
            clauses.append("m.{c}=?".format(c=col))
            vals.append(v)
        if not clauses:
            where = "1=1"
        else:
            where = " AND ".join(clauses)
        rows = conn.execute(
            "SELECT m.*, o.object_name, o.object_type FROM bcl_metadata m "
            "JOIN code_objects o ON m.object_id=o.object_id WHERE {w}".format(w=where),
            tuple(vals)).fetchall()
        return (1, [dict(r) for r in rows], None)

    # ------------------------------------------------------------------------
    # Method: QueryByType
    # Purpose: Query objects by type (file/class/method/function/constant)
    # Params:  params (dict with object_type)
    # Returns: Tuple3 (1, rows, None) or (0, None, error)
    # ------------------------------------------------------------------------
    def QueryByType(self, params=None):
        params = params or {}
        object_type = self._p(params, "object_type")
        if not object_type:
            return (0, None, ("MISSING_PARAM", "object_type required", 0))
        conn = self.state.get("conn")
        if conn is None:
            return (0, None, ("DB_CLOSED", "open db first", 0))
        rows = conn.execute(
            "SELECT * FROM code_objects WHERE object_type=? ORDER BY object_name",
            (object_type,)).fetchall()
        return (1, [dict(r) for r in rows], None)

    # ------------------------------------------------------------------------
    # Method: QueryByName
    # Purpose: Query objects by name (fuzzy match)
    # Params:  params (dict with name)
    # Returns: Tuple3 (1, rows, None) or (0, None, error)
    # ------------------------------------------------------------------------
    def QueryByName(self, params=None):
        params = params or {}
        name = self._p(params, "name")
        if not name:
            return (0, None, ("MISSING_PARAM", "name required", 0))
        conn = self.state.get("conn")
        if conn is None:
            return (0, None, ("DB_CLOSED", "open db first", 0))
        rows = conn.execute(
            "SELECT * FROM code_objects WHERE object_name LIKE ? ORDER BY object_type",
            ("%{n}%".format(n=name),)).fetchall()
        return (1, [dict(r) for r in rows], None)

    # ------------------------------------------------------------------------
    # Method: QueryEdges
    # Purpose: Query relationship edges, optionally filtered by type
    # Params:  params (dict with optional relationship)
    # Returns: Tuple3 (1, rows, None) or (0, None, error)
    # ------------------------------------------------------------------------
    def QueryEdges(self, params=None):
        params = params or {}
        conn = self.state.get("conn")
        if conn is None:
            return (0, None, ("DB_CLOSED", "open db first", 0))
        rel = self._p(params, "relationship")
        if rel:
            rows = conn.execute(
                "SELECT * FROM object_relationships WHERE relationship=?", (rel,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM object_relationships").fetchall()
        return (1, [dict(r) for r in rows], None)

    # ------------------------------------------------------------------------
    # Method: QueryStats
    # Purpose: Return database statistics rollup
    # Params:  params (dict, unused)
    # Returns: Tuple3 (1, stats_dict, None) or (0, None, error)
    # ------------------------------------------------------------------------
    def QueryStats(self, params=None):
        conn = self.state.get("conn")
        if conn is None:
            return (0, None, ("DB_CLOSED", "open db first", 0))
        stats = {}
        stats["objects"] = conn.execute("SELECT COUNT(*) FROM code_objects").fetchone()[0]
        stats["by_type"] = dict(conn.execute(
            "SELECT object_type, COUNT(*) FROM code_objects GROUP BY object_type").fetchall())
        stats["relationships"] = conn.execute(
            "SELECT COUNT(*) FROM object_relationships").fetchone()[0]
        stats["by_rel"] = dict(conn.execute(
            "SELECT relationship, COUNT(*) FROM object_relationships GROUP BY relationship").fetchall())
        stats["bcl_meta"] = conn.execute(
            "SELECT COUNT(*) FROM bcl_metadata").fetchone()[0]
        stats["by_domain"] = dict(conn.execute(
            "SELECT bcl_domain, COUNT(*) FROM bcl_metadata GROUP BY bcl_domain").fetchall())
        stats["by_role"] = dict(conn.execute(
            "SELECT bcl_role, COUNT(*) FROM bcl_metadata GROUP BY bcl_role").fetchall())
        stats["versions"] = conn.execute(
            "SELECT COUNT(*) FROM source_versions").fetchone()[0]
        stats["ir_nodes"] = conn.execute(
            "SELECT COUNT(*) FROM ir_nodes").fetchone()[0]
        return (1, stats, None)

    # ------------------------------------------------------------------------
    # EXPORT LAYER (Cursor Walk #11 + Template Injection #8)
    # ------------------------------------------------------------------------
    # Method: ExportSource
    # Purpose: Reconstruct source code of a single object
    # Params:  params (dict with object_id)
    # Returns: Tuple3 (1, source_str, None) or (0, None, error)
    # ------------------------------------------------------------------------
    def ExportSource(self, params=None):
        params = params or {}
        object_id = self._p(params, "object_id")
        if not object_id:
            return (0, None, ("MISSING_PARAM", "object_id required", 0))
        conn = self.state.get("conn")
        if conn is None:
            return (0, None, ("DB_CLOSED", "open db first", 0))
        row = conn.execute(
            "SELECT source_code FROM code_objects WHERE object_id=?", (object_id,)).fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", object_id, 0))
        return (1, row["source_code"], None)

    # ------------------------------------------------------------------------
    # Method: ExportFile
    # Purpose: Reconstruct a file by walking its object tree in line order
    # Params:  params (dict with object_id = file_id)
    # Returns: Tuple3 (1, source_str, None) or (0, None, error)
    # ------------------------------------------------------------------------
    def ExportFile(self, params=None):
        params = params or {}
        file_id = self._p(params, "object_id")
        if not file_id:
            return (0, None, ("MISSING_PARAM", "object_id required", 0))
        conn = self.state.get("conn")
        if conn is None:
            return (0, None, ("DB_CLOSED", "open db first", 0))
        rows = conn.execute(
            "SELECT * FROM code_objects WHERE object_id=? OR parent_id=? "
            "ORDER BY start_line", (file_id, file_id)).fetchall()
        if not rows:
            return (0, None, ("NOT_FOUND", file_id, 0))
        parts = []
        for r in rows:
            if r["object_type"] == "file":
                continue
            parts.append(r["source_code"])
        return (1, "\n\n".join(parts), None)

    # ------------------------------------------------------------------------
    # Method: ExportBcl
    # Purpose: Emit BCL IR block for a single object (template injection)
    # Params:  params (dict with object_id)
    # Returns: Tuple3 (1, bcl_str, None) or (0, None, error)
    # ------------------------------------------------------------------------
    def ExportBcl(self, params=None):
        params = params or {}
        object_id = self._p(params, "object_id")
        if not object_id:
            return (0, None, ("MISSING_PARAM", "object_id required", 0))
        conn = self.state.get("conn")
        if conn is None:
            return (0, None, ("DB_CLOSED", "open db first", 0))
        obj = conn.execute(
            "SELECT * FROM code_objects WHERE object_id=?", (object_id,)).fetchone()
        if not obj:
            return (0, None, ("NOT_FOUND", object_id, 0))
        meta = conn.execute(
            "SELECT * FROM bcl_metadata WHERE object_id=?", (object_id,)).fetchone()
        # Emit real BCL bracket format: [@name]{("k";"v")...}
        tuples = [
            ["type", obj["object_type"]],
            ["id", obj["object_id"]],
        ]
        if obj["parent_id"]:
            tuples.append(["parent", obj["parent_id"]])
        tuples.append(["name", obj["object_name"]])
        if obj["signature"]:
            tuples.append(["signature", obj["signature"]])
        tuples.append(["lines", "{s}-{e}".format(s=obj["start_line"], e=obj["end_line"])])
        tuples.append(["checksum", obj["checksum"]])
        if meta:
            tuples.append(["domain", meta["bcl_domain"]])
            tuples.append(["role", meta["bcl_role"]])
            tuples.append(["stage", meta["bcl_stage"]])
            tuples.append(["priority", meta["bcl_priority"]])
        safe_name = obj["object_name"].replace(" ", "_").replace(":", "")
        return (1, BclContainer(safe_name, tuples), None)

    # ------------------------------------------------------------------------
    # Method: ExportTreeBcl
    # Purpose: Walk the object tree (cursor) and emit BCL for every descendant
    # Params:  params (dict with object_id = root)
    # Returns: Tuple3 (1, bcl_str, None) or (0, None, error)
    # ------------------------------------------------------------------------
    def ExportTreeBcl(self, params=None):
        params = params or {}
        object_id = self._p(params, "object_id")
        if not object_id:
            return (0, None, ("MISSING_PARAM", "object_id required", 0))
        conn = self.state.get("conn")
        if conn is None:
            return (0, None, ("DB_CLOSED", "open db first", 0))
        rows = conn.execute(TREE_CTE, (object_id,)).fetchall()
        blocks = []
        for r in rows:
            r2 = self.ExportBcl({"object_id": r["object_id"]})
            if r2[0]:
                blocks.append(r2[1])
        return (1, "\n\n".join(blocks), None)


# ============================================================================
# CLI ENTRY POINT — only place that uses print()
# ============================================================================

def main():
    if len(sys.argv) < 2:
        sys.stdout.write(
            "Usage: python3 BCLObjectDatabase.py <command> [args...]\n"
            "  test                                    — self-test\n"
            "  ingest <file|dir> [--db path]           — ingest into DB\n"
            "  query <db> --tree <id>                  — recursive tree\n"
            "  query <db> --children <id>              — direct children\n"
            "  query <db> --calls <id>                 — outgoing calls\n"
            "  query <db> --bcl domain=search          — BCL metadata query\n"
            "  query <db> --type class                 — objects by type\n"
            "  query <db> --stats                      — database stats\n"
            "  export <db> <id> source                 — reconstruct source\n"
            "  export <db> <id> bcl                    — emit BCL IR\n"
            "  export <db> <id> tree-bcl               — BCL for subtree\n"
        )
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "test":
        RunSelfTest()
        return

    if cmd == "ingest":
        target = sys.argv[2]
        db_path = "bcl_objects.db"
        if "--db" in sys.argv:
            idx = sys.argv.index("--db")
            db_path = sys.argv[idx + 1]
        db = BCLObjectDatabase(db=db_path)
        r = db.OpenDb()
        if not r[0]:
            sys.stdout.write("ERROR: {e}\n".format(e=r[2]))
            sys.exit(1)
        if os.path.isdir(target):
            r = db.IngestDirectory({"dirpath": target})
            if r[0]:
                for item in r[1]:
                    if "error" in item:
                        sys.stdout.write("  ERROR  {f}: {e}\n".format(f=item["filepath"], e=item["error"]))
                    else:
                        sys.stdout.write("  OK     {f}  objects={o}\n".format(
                            f=item["filepath"], o=item["objects"]))
                sys.stdout.write("[INGEST] {n} files -> {db}\n".format(n=len(r[1]), db=db_path))
            else:
                sys.stdout.write("ERROR: {e}\n".format(e=r[2]))
        else:
            r = db.IngestFile({"filepath": target})
            if r[0]:
                sys.stdout.write("[INGEST] {f}: {o} objects, {rel} relationships -> {db}\n".format(
                    f=target, o=r[1]["objects"], rel=r[1]["relationships"], db=db_path))
            else:
                sys.stdout.write("ERROR: {e}\n".format(e=r[2]))
        db.CloseDb()
        return

    if cmd == "query":
        db_path = sys.argv[2]
        db = BCLObjectDatabase(db=db_path)
        r = db.OpenDb()
        if not r[0]:
            sys.stdout.write("ERROR: {e}\n".format(e=r[2]))
            sys.exit(1)
        if "--tree" in sys.argv:
            oid = sys.argv[sys.argv.index("--tree") + 1]
            r = db.QueryTree({"object_id": oid})
            if r[0]:
                for row in r[1]:
                    sys.stdout.write("  {ind}[{t}] {n}\n".format(
                        ind="  " * row["depth"], t=row["object_type"], n=row["object_name"]))
        elif "--ancestors" in sys.argv:
            oid = sys.argv[sys.argv.index("--ancestors") + 1]
            r = db.QueryAncestors({"object_id": oid})
            if r[0]:
                for row in r[1]:
                    sys.stdout.write("  [{t}] {n} (depth={d})\n".format(
                        t=row["object_type"], n=row["object_name"], d=row["depth"]))
        elif "--children" in sys.argv:
            oid = sys.argv[sys.argv.index("--children") + 1]
            r = db.QueryChildren({"object_id": oid})
            if r[0]:
                for row in r[1]:
                    sys.stdout.write("  [{t}] {n}  lines={sl}-{el}\n".format(
                        t=row["object_type"], n=row["object_name"],
                        sl=row["start_line"], el=row["end_line"]))
        elif "--calls" in sys.argv:
            oid = sys.argv[sys.argv.index("--calls") + 1]
            r = db.QueryCalls({"object_id": oid})
            if r[0]:
                for row in r[1]:
                    sys.stdout.write("  -> {n} (line {ln})\n".format(
                        n=row["child_name"], ln=row["call_lineno"]))
        elif "--callers" in sys.argv:
            oid = sys.argv[sys.argv.index("--callers") + 1]
            r = db.QueryCallers({"object_id": oid})
            if r[0]:
                for row in r[1]:
                    sys.stdout.write("  <- {n} (line {ln})\n".format(
                        n=row["parent_name"], ln=row["call_lineno"]))
        elif "--bcl" in sys.argv:
            filt_str = sys.argv[sys.argv.index("--bcl") + 1]
            filters = {}
            for part in filt_str.split():
                if "=" in part:
                    k, v = part.split("=", 1)
                    filters[k] = v
            r = db.QueryByBcl(filters)
            if r[0]:
                for row in r[1]:
                    sys.stdout.write("  [{t}] {n}  domain={d} role={rl} stage={s}\n".format(
                        t=row["object_type"], n=row["object_name"],
                        d=row["bcl_domain"], rl=row["bcl_role"], s=row["bcl_stage"]))
        elif "--type" in sys.argv:
            t = sys.argv[sys.argv.index("--type") + 1]
            r = db.QueryByType({"object_type": t})
            if r[0]:
                for row in r[1]:
                    sys.stdout.write("  [{t}] {n}  parent={p}\n".format(
                        t=row["object_type"], n=row["object_name"], p=row["parent_name"]))
        elif "--name" in sys.argv:
            n = sys.argv[sys.argv.index("--name") + 1]
            r = db.QueryByName({"name": n})
            if r[0]:
                for row in r[1]:
                    sys.stdout.write("  [{t}] {n}  parent={p}\n".format(
                        t=row["object_type"], n=row["object_name"], p=row["parent_name"]))
        elif "--edges" in sys.argv:
            rel_idx = sys.argv.index("--edges") + 1
            rel = sys.argv[rel_idx] if rel_idx < len(sys.argv) else None
            params = {"relationship": rel} if rel else {}
            r = db.QueryEdges(params)
            if r[0]:
                for row in r[1]:
                    sys.stdout.write("  {p} --{rel}--> {c}\n".format(
                        p=row["parent_name"], rel=row["relationship"], c=row["child_name"]))
        elif "--stats" in sys.argv:
            r = db.QueryStats()
            if r[0]:
                s = r[1]
                sys.stdout.write("=" * 60 + "\n")
                sys.stdout.write("BCL ObjectDatabase — STATS\n")
                sys.stdout.write("=" * 60 + "\n")
                sys.stdout.write("  Total objects:      {o}\n".format(o=s["objects"]))
                sys.stdout.write("  By type:            {bt}\n".format(bt=s["by_type"]))
                sys.stdout.write("  Relationships:      {rel}\n".format(rel=s["relationships"]))
                sys.stdout.write("  By relationship:    {br}\n".format(br=s["by_rel"]))
                sys.stdout.write("  BCL metadata rows:  {bm}\n".format(bm=s["bcl_meta"]))
                sys.stdout.write("  By domain:          {bd}\n".format(bd=s["by_domain"]))
                sys.stdout.write("  By role:            {br2}\n".format(br2=s["by_role"]))
                sys.stdout.write("  Source versions:    {v}\n".format(v=s["versions"]))
                sys.stdout.write("  IR nodes:           {ir}\n".format(ir=s["ir_nodes"]))
                sys.stdout.write("=" * 60 + "\n")
        else:
            sys.stdout.write("Query options: --tree <id> | --children <id> | --calls <id> | "
                             "--bcl k=v | --type <t> | --name <n> | --edges [rel] | --stats\n")
        db.CloseDb()
        return

    if cmd == "export":
        db_path = sys.argv[2]
        object_id = sys.argv[3]
        mode = sys.argv[4] if len(sys.argv) > 4 else "source"
        db = BCLObjectDatabase(db=db_path)
        r = db.OpenDb()
        if not r[0]:
            sys.stdout.write("ERROR: {e}\n".format(e=r[2]))
            sys.exit(1)
        if mode == "source":
            r = db.ExportSource({"object_id": object_id})
        elif mode == "file":
            r = db.ExportFile({"object_id": object_id})
        elif mode == "bcl":
            r = db.ExportBcl({"object_id": object_id})
        elif mode == "tree-bcl":
            r = db.ExportTreeBcl({"object_id": object_id})
        else:
            sys.stdout.write("Unknown mode: {m}\n".format(m=mode))
            sys.exit(1)
        if r[0]:
            sys.stdout.write(r[1] + "\n")
        else:
            sys.stdout.write("ERROR: {e}\n".format(e=r[2]))
        db.CloseDb()
        return

    sys.stdout.write("Unknown command: {c}\n".format(c=cmd))
    sys.exit(1)


# ============================================================================
# SELF TEST
# ============================================================================

def RunSelfTest():
    """Built-in self-test: ingest synthetic sample, query, export, verify."""
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("BCLObjectDatabase — VBSTYLE SELF TEST\n")
    sys.stdout.write("=" * 70 + "\n")

    sample = (
        '"""Sample module for self-test."""\n'
        'import os\n'
        'import sys\n'
        '\n'
        'MAX_RETRIES = 3\n'
        'DEFAULT_TIMEOUT = 30\n'
        '\n'
        '\n'
        'class SearchEngine:\n'
        '    """Search engine over indexed objects."""\n'
        '\n'
        '    def __init__(self, db_path):\n'
        '        self.state = {"db": db_path, "cache": {}}\n'
        '\n'
        '    def Run(self, command, params=None):\n'
        '        if command == "search":\n'
        '            return self.search(params)\n'
        '        return (0, None, (1, "unknown command", 0))\n'
        '\n'
        '    def search(self, query):\n'
        '        results = []\n'
        '        for key in self.state["cache"]:\n'
        '            if query in key:\n'
        '                results.append(key)\n'
        '        return (1, results, None)\n'
        '\n'
        '    def index(self, items):\n'
        '        for item in items:\n'
        '            self.state["cache"][item["id"]] = item\n'
        '        return (1, len(self.state["cache"]), None)\n'
        '\n'
        '\n'
        'def helper_function(x):\n'
        '    """Standalone helper."""\n'
        '    return x * 2\n'
    )
    sample_path = "/tmp/_bcl_objdb_vbstyle_test.py"
    with open(sample_path, "w") as f:
        f.write(sample)

    db_path = "/tmp/_bcl_objdb_vbstyle_test.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    db = BCLObjectDatabase(db=db_path)

    # Open
    sys.stdout.write("\n[1] OpenDb\n")
    r = db.Run("open", {})
    assert r[0], "OpenDb failed: {e}".format(e=r[2])
    sys.stdout.write("    OK conn opened\n")

    # Ingest
    sys.stdout.write("\n[2] IngestFile via Run dispatch\n")
    r = db.Run("ingest_file", {"filepath": sample_path})
    assert r[0], "IngestFile failed: {e}".format(e=r[2])
    sys.stdout.write("    objects={o} rels={rel} bcl_meta={bm} ir={ir}\n".format(
        o=r[1]["objects"], rel=r[1]["relationships"], bm=r[1]["bcl_meta"], ir=r[1]["ir_blocks"]))
    assert r[1]["objects"] >= 8, "Expected >=8 objects"

    # Stats
    sys.stdout.write("\n[3] Stats via Run dispatch\n")
    r = db.Run("stats", {})
    assert r[0], "Stats failed: {e}".format(e=r[2])
    s = r[1]
    sys.stdout.write("    objects={o} by_type={bt}\n".format(o=s["objects"], bt=s["by_type"]))
    sys.stdout.write("    rels={rel} by_rel={br}\n".format(rel=s["relationships"], br=s["by_rel"]))
    sys.stdout.write("    by_domain={bd}\n".format(bd=s["by_domain"]))
    sys.stdout.write("    by_role={br2}\n".format(br2=s["by_role"]))
    assert s["objects"] >= 8

    # Find SearchEngine class
    r = db.Run("by_type", {"object_type": "class"})
    assert r[0] and len(r[1]) >= 1, "No classes found"
    cls = r[1][0]
    sys.stdout.write("\n[4] Found class: {n} (id={id})\n".format(n=cls["object_name"], id=cls["object_id"]))
    sys.stdout.write("    BCL header:\n")
    for line in cls["bcl_header"].split("\n"):
        sys.stdout.write("      {l}\n".format(l=line))

    # Recursive tree
    sys.stdout.write("\n[5] Recursive CTE tree:\n")
    r = db.Run("tree", {"object_id": cls["object_id"]})
    assert r[0], "Tree query failed: {e}".format(e=r[2])
    for row in r[1]:
        sys.stdout.write("    {ind}[{t}] {n} (depth={d})\n".format(
            ind="  " * row["depth"], t=row["object_type"], n=row["object_name"], d=row["depth"]))
    assert len(r[1]) >= 5, "Tree should have >=5 nodes"

    # Children
    sys.stdout.write("\n[6] Direct children:\n")
    r = db.Run("children", {"object_id": cls["object_id"]})
    assert r[0], "Children query failed: {e}".format(e=r[2])
    for row in r[1]:
        sys.stdout.write("    [{t}] {n}  lines={sl}-{el}\n".format(
            t=row["object_type"], n=row["object_name"], sl=row["start_line"], el=row["end_line"]))
    assert len(r[1]) >= 4, "Expected >=4 children"

    # Calls
    search_method = next((c for c in r[1] if c["object_name"] == "search"), None)
    assert search_method, "search method not found"
    sys.stdout.write("\n[7] Calls from search():\n")
    r = db.Run("calls", {"object_id": search_method["object_id"]})
    assert r[0], "Calls query failed: {e}".format(e=r[2])
    for row in r[1]:
        sys.stdout.write("    -> {n} (line {ln})\n".format(n=row["child_name"], ln=row["call_lineno"]))
    assert len(r[1]) >= 1, "Expected >=1 call"

    # BCL query
    sys.stdout.write("\n[8] BCL query: domain=search\n")
    r = db.Run("by_bcl", {"domain": "search"})
    assert r[0], "BCL query failed: {e}".format(e=r[2])
    for row in r[1]:
        sys.stdout.write("    [{t}] {n} role={rl} stage={s}\n".format(
            t=row["object_type"], n=row["object_name"], rl=row["bcl_role"], s=row["bcl_stage"]))
    assert len(r[1]) >= 1, "Expected >=1 search-domain object"

    # Export source
    sys.stdout.write("\n[9] Export source of search():\n")
    r = db.Run("export_source", {"object_id": search_method["object_id"]})
    assert r[0], "Export source failed: {e}".format(e=r[2])
    for line in r[1].split("\n"):
        sys.stdout.write("    {l}\n".format(l=line))

    # Export BCL tree
    sys.stdout.write("\n[10] Export BCL IR for class tree:\n")
    r = db.Run("export_tree_bcl", {"object_id": cls["object_id"]})
    assert r[0], "Export tree BCL failed: {e}".format(e=r[2])
    for line in r[1].split("\n"):
        sys.stdout.write("    {l}\n".format(l=line))

    # Ancestors
    sys.stdout.write("\n[11] Ancestors of search() (recursive CTE up):\n")
    r = db.Run("ancestors", {"object_id": search_method["object_id"]})
    assert r[0], "Ancestors query failed: {e}".format(e=r[2])
    for row in r[1]:
        sys.stdout.write("    [{t}] {n} (depth={d})\n".format(
            t=row["object_type"], n=row["object_name"], d=row["depth"]))
    assert len(r[1]) >= 3, "Expected >=3 ancestors"

    # ReadState
    sys.stdout.write("\n[12] ReadState:\n")
    r = db.ReadState()
    assert r[0], "ReadState failed: {e}".format(e=r[2])
    sys.stdout.write("    objects_ingested={o}\n".format(o=r[1]["objects_ingested"]))
    sys.stdout.write("    relationships_ingested={rel}\n".format(rel=r[1]["relationships_ingested"]))
    sys.stdout.write("    last_file={f}\n".format(f=r[1]["last_file"]))

    # Close
    db.Run("close", {})
    os.remove(sample_path)
    os.remove(db_path)

    sys.stdout.write("\n" + "=" * 70 + "\n")
    sys.stdout.write("VBSTYLE SELF TEST PASSED\n")
    sys.stdout.write("=" * 70 + "\n")


if __name__ == "__main__":
    main()
