#!/usr/bin/env python3
"""
CodeIngester — ingests code files into SQLite DB.
Tables: files, dependencies, methods.
Config comes from Config.py.
"""

import ast
import json
import sqlite3
import hashlib
import re

from Config import DB_PATH, SOURCES, DESCRIPTIONS, PURPOSES, LOCAL_MODULES

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    source_dir TEXT NOT NULL,
    code TEXT NOT NULL,
    description TEXT,
    purpose TEXT,
    graph TEXT,
    content_hash TEXT,
    line_count INTEGER,
    size_bytes INTEGER,
    ingested_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_files_name ON files(file_name);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(content_hash);

CREATE TABLE IF NOT EXISTS dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    import_type TEXT NOT NULL,
    module TEXT NOT NULL,
    alias TEXT,
    line INTEGER,
    is_local INTEGER DEFAULT 0,
    FOREIGN KEY (file_id) REFERENCES files(id)
);
CREATE INDEX IF NOT EXISTS idx_deps_module ON dependencies(module);
CREATE INDEX IF NOT EXISTS idx_deps_file ON dependencies(file_id);
CREATE INDEX IF NOT EXISTS idx_deps_local ON dependencies(is_local);
CREATE UNIQUE INDEX IF NOT EXISTS idx_deps_unique ON dependencies(file_id, module, import_type, alias);

CREATE TABLE IF NOT EXISTS methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    class_name TEXT,
    method_name TEXT NOT NULL,
    code TEXT NOT NULL,
    description TEXT,
    category TEXT,
    group_name TEXT,
    bcl TEXT,
    bcl_ir TEXT,
    line_start INTEGER,
    line_end INTEGER,
    args TEXT,
    line_count INTEGER,
    FOREIGN KEY (file_id) REFERENCES files(id)
);
CREATE INDEX IF NOT EXISTS idx_methods_name ON methods(method_name);
CREATE INDEX IF NOT EXISTS idx_methods_class ON methods(class_name);
CREATE INDEX IF NOT EXISTS idx_methods_category ON methods(category);
CREATE INDEX IF NOT EXISTS idx_methods_file ON methods(file_id);
"""

CATEGORY_RULES = [
    ("parse", "Parser", "Parsing"),
    ("build", "Builder", "Construction"),
    ("render", "Renderer", "Rendering"),
    ("route", "Router", "EventRouting"),
    ("connect", "Router", "EventRouting"),
    ("disconnect", "Router", "EventRouting"),
    ("register", "Bus", "Registration"),
    ("fire", "Bus", "EventDispatch"),
    ("dispatch", "Bus", "EventDispatch"),
    ("query", "DB", "DataAccess"),
    ("get", "DB", "DataAccess"),
    ("load", "Loader", "DataLoading"),
    ("save", "DB", "DataAccess"),
    ("insert", "DB", "DataAccess"),
    ("update", "DB", "DataAccess"),
    ("delete", "DB", "DataAccess"),
    ("validate", "Validator", "Validation"),
    ("check", "Validator", "Validation"),
    ("apply", "Theme", "Styling"),
    ("style", "Theme", "Styling"),
    ("embed", "Embedder", "Embedding"),
    ("ingest", "Ingester", "Ingestion"),
    ("extract", "Extractor", "Extraction"),
    ("import", "Ingester", "Ingestion"),
    ("classify", "Classifier", "Classification"),
    ("filter", "Filter", "Filtering"),
    ("score", "Scorer", "Scoring"),
    ("decide", "DecisionEngine", "DecisionMaking"),
    ("resolve", "DecisionEngine", "DecisionMaking"),
    ("close", "Lifecycle", "Cleanup"),
    ("init", "Lifecycle", "Initialization"),
    ("run", "Dispatch", "CommandDispatch"),
    ("read_state", "State", "StateRead"),
    ("set_config", "Config", "Configuration"),
]

BCL_PATTERN = re.compile(r'#\s*\[@(\w+)\]\{([^}]*)\}')
KV_PATTERN = re.compile(r'\[@(\w+)<([^>]*)>\]')

HINTS = {
    "Parser": "Parses input into structured data",
    "Builder": "Builds and returns constructed object",
    "Renderer": "Renders data to output format",
    "Router": "Routes signals/events to handlers",
    "Bus": "Manages event bus operations",
    "DB": "Database access operation",
    "Loader": "Loads data from source",
    "Validator": "Validates input or state",
    "Theme": "Applies styling/theme",
    "Embedder": "Generates embeddings",
    "Ingester": "Ingests data into storage",
    "Extractor": "Extracts information from source",
    "DecisionEngine": "Makes decisions based on context",
    "Lifecycle": "Lifecycle management",
    "Dispatch": "Dispatches commands",
    "State": "Reads internal state",
    "Config": "Configuration management",
    "Dunder": "Python special method",
    "Internal": "Internal helper",
    "General": "General method",
}


class CodeIngester:
    """Ingest code files into SQLite. Extracts AST graph, dependencies, and methods."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {}
        self.db_path = str(DB_PATH)
        self.conn = None
        self.cursor = None

    def Run(self, command, params=None):
        if command == "ingest_all":
            return self.cmdIngestAll(params)
        if command == "ingest_files":
            return self.cmdIngestFiles(params)
        if command == "extract_deps":
            return self.cmdExtractDeps(params)
        if command == "extract_methods":
            return self.cmdExtractMethods(params)
        if command == "extract_all":
            return self.cmdExtractAll(params)
        if command == "read_state":
            return self.readState()
        return (0, None, ("UNKNOWN_COMMAND", "Unknown: " + str(command), 0))

    def _connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.cursor.executescript(SCHEMA)
        self.conn.commit()

    def _close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None

    def _buildGraph(self, source_code, filename):
        nodes = []
        edges = []
        try:
            tree = ast.parse(source_code, filename=filename)
        except SyntaxError as e:
            return json.dumps({"error": str(e), "nodes": [], "edges": []})
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                nodes.append({"type": "ClassDef", "name": node.name, "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "bases": [b.id if isinstance(b, ast.Name) else ast.dump(b) for b in node.bases]})
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        edges.append({"source": node.name, "target": child.name, "type": "CONTAINS", "line": child.lineno})
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nodes.append({"type": "FunctionDef", "name": node.name, "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "args": [a.arg for a in node.args.args]})
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute):
                    edges.append({"source": "module_level", "target": func.attr, "type": "CALLS", "line": node.lineno})
                elif isinstance(func, ast.Name):
                    edges.append({"source": "module_level", "target": func.id, "type": "CALLS", "line": node.lineno})
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    nodes.append({"type": "Import", "name": alias.name, "line": node.lineno})
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    nodes.append({"type": "ImportFrom", "name": f"{module}.{alias.name}", "line": node.lineno})
        return json.dumps({"nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges)})

    def _extractImports(self, code, file_id, file_name):
        imports = []
        try:
            tree = ast.parse(code, filename=file_name)
        except SyntaxError:
            return imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    alias_name = alias.asname or module.split(".")[0]
                    is_local = 1 if module.split(".")[0] in LOCAL_MODULES else 0
                    imports.append({"file_id": file_id, "file_name": file_name, "import_type": "import",
                        "module": module, "alias": alias_name, "line": node.lineno, "is_local": is_local})
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    alias_name = alias.asname or alias.name
                    is_local = 1 if module.split(".")[0] in LOCAL_MODULES else 0
                    imports.append({"file_id": file_id, "file_name": file_name, "import_type": "from",
                        "module": f"{module}.{alias.name}" if module else alias.name,
                        "alias": alias_name, "line": node.lineno, "is_local": is_local})
        return imports

    def _classifyMethod(self, name, code):
        lname = name.lower()
        for keyword, category, group in CATEGORY_RULES:
            if keyword in lname:
                return category, group
        if name.startswith("__") and name.endswith("__"):
            return "Dunder", "Lifecycle"
        if name.startswith("_"):
            return "Internal", "Utility"
        return "General", "General"

    def _extractBcl(self, code):
        bcl_tokens = []
        for match in BCL_PATTERN.finditer(code):
            tag = match.group(1)
            body = match.group(2)
            kvs = {}
            for kv_match in KV_PATTERN.finditer(body):
                kvs[kv_match.group(1)] = kv_match.group(2)
            bcl_tokens.append({"tag": tag, "props": kvs})
        return json.dumps(bcl_tokens) if bcl_tokens else None

    def _generateBclIr(self, class_name, method_name, args, code, category, group):
        args_clean = [a for a in args if a != "self"]
        has_return = "return " in code
        has_loop = "for " in code or "while " in code
        has_if = "if " in code
        has_try = "try:" in code
        calls = []
        for call_match in re.finditer(r'self\.(\w+)\s*\(', code):
            calls.append(call_match.group(1))
        for call_match in re.finditer(r'(\w+)\.\w+\s*\(', code):
            if call_match.group(1) not in ("self", "cursor", "conn", "widget", "f"):
                calls.append(call_match.group(1))
        ir = {"method": method_name, "class": class_name or "module", "category": category,
            "group": group, "args": args_clean, "returns": has_return,
            "control_flow": {"loop": has_loop, "conditional": has_if, "try_except": has_try},
            "calls": list(set(calls))[:10],
            "complexity": (1 if has_if else 0) + (2 if has_loop else 0) + (3 if has_try else 0)}
        return json.dumps(ir)

    def _generateMethodDesc(self, class_name, method_name, args, category):
        args_clean = [a for a in args if a != "self"]
        parts = []
        if class_name:
            parts.append(class_name)
        parts.append(method_name)
        if args_clean:
            parts.append(f"({', '.join(args_clean)})")
        desc = " ".join(parts)
        hint = HINTS.get(category, "")
        if hint:
            desc += f" \u2014 {hint}"
        return desc

    def _extractMethodInfo(self, node, lines, file_id, file_name, class_name):
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", node.lineno)
        method_name = node.name
        args = [a.arg for a in node.args.args]
        method_code = "".join(lines[start_line - 1:end_line])
        category, group = self._classifyMethod(method_name, method_code)
        description = self._generateMethodDesc(class_name, method_name, args, category)
        bcl = self._extractBcl(method_code)
        bcl_ir = self._generateBclIr(class_name, method_name, args, method_code, category, group)
        line_count = end_line - start_line + 1
        return {"file_id": file_id, "file_name": file_name, "class_name": class_name,
            "method_name": method_name, "code": method_code, "description": description,
            "category": category, "group_name": group, "bcl": bcl, "bcl_ir": bcl_ir,
            "line_start": start_line, "line_end": end_line, "args": json.dumps(args), "line_count": line_count}

    def _extractMethodsFromFile(self, code, file_id, file_name):
        methods = []
        try:
            tree = ast.parse(code, filename=file_name)
        except SyntaxError:
            return methods
        lines = code.splitlines(keepends=True)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        m = self._extractMethodInfo(child, lines, file_id, file_name, class_name)
                        if m:
                            methods.append(m)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                m = self._extractMethodInfo(node, lines, file_id, file_name, None)
                if m:
                    methods.append(m)
        return methods

    def _insertMethod(self, m):
        self.cursor.execute(
            "INSERT INTO methods (file_id, file_name, class_name, method_name, "
            "code, description, category, group_name, bcl, bcl_ir, "
            "line_start, line_end, args, line_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (m["file_id"], m["file_name"], m["class_name"], m["method_name"],
             m["code"], m["description"], m["category"], m["group_name"],
             m["bcl"], m["bcl_ir"], m["line_start"], m["line_end"],
             m["args"], m["line_count"]))

    def cmdIngestAll(self, params):
        self._connect()
        cur = self.cursor
        files_ingested = 0
        deps_extracted = 0
        for source_dir in SOURCES:
            if not source_dir.exists():
                continue
            for fpath in sorted(source_dir.glob("*.py")):
                fname = fpath.name
                code = fpath.read_text(encoding="utf-8", errors="replace")
                content_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
                line_count = code.count("\n") + 1
                size_bytes = fpath.stat().st_size
                description = DESCRIPTIONS.get(fname, "")
                purpose = PURPOSES.get(fname, "")
                graph = self._buildGraph(code, fname)
                cur.execute(
                    "INSERT INTO files (file_name, source_dir, code, description, "
                    "purpose, graph, content_hash, line_count, size_bytes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (fname, str(source_dir), code, description, purpose,
                     graph, content_hash, line_count, size_bytes))
                file_id = cur.lastrowid
                self.conn.commit()
                files_ingested += 1
                imports = self._extractImports(code, file_id, fname)
                for imp in imports:
                    cur.execute(
                        "INSERT OR IGNORE INTO dependencies (file_id, file_name, "
                        "import_type, module, alias, line, is_local) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (imp["file_id"], imp["file_name"], imp["import_type"],
                         imp["module"], imp["alias"], imp["line"], imp["is_local"]))
                self.conn.commit()
                deps_extracted += len(imports)
        cur.execute("SELECT COUNT(*) FROM files")
        file_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM dependencies")
        dep_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT module) FROM dependencies")
        unique_modules = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM dependencies WHERE is_local=1")
        local_count = cur.fetchone()[0]
        self.state = {
            "files_ingested": files_ingested, "deps_extracted": deps_extracted,
            "file_count": file_count, "dep_count": dep_count,
            "unique_modules": unique_modules, "local_deps": local_count,
            "db_path": self.db_path}
        self._close()
        return (1, self.state, None)

    def cmdIngestFiles(self, params):
        self._connect()
        cur = self.cursor
        total = 0
        for source_dir in SOURCES:
            if not source_dir.exists():
                continue
            for fpath in sorted(source_dir.glob("*.py")):
                fname = fpath.name
                code = fpath.read_text(encoding="utf-8", errors="replace")
                content_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
                line_count = code.count("\n") + 1
                size_bytes = fpath.stat().st_size
                description = DESCRIPTIONS.get(fname, "")
                purpose = PURPOSES.get(fname, "")
                graph = self._buildGraph(code, fname)
                cur.execute(
                    "INSERT INTO files (file_name, source_dir, code, description, "
                    "purpose, graph, content_hash, line_count, size_bytes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (fname, str(source_dir), code, description, purpose,
                     graph, content_hash, line_count, size_bytes))
                self.conn.commit()
                total += 1
        cur.execute("SELECT COUNT(*) FROM files")
        count = cur.fetchone()[0]
        self._close()
        return (1, {"ingested": total, "total": count}, None)

    def cmdExtractDeps(self, params):
        self._connect()
        cur = self.cursor
        cur.execute("SELECT id, file_name, code FROM files ORDER BY id")
        files = cur.fetchall()
        total = 0
        for file_id, file_name, code in files:
            imports = self._extractImports(code, file_id, file_name)
            for imp in imports:
                cur.execute(
                    "INSERT OR IGNORE INTO dependencies (file_id, file_name, "
                    "import_type, module, alias, line, is_local) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (imp["file_id"], imp["file_name"], imp["import_type"],
                     imp["module"], imp["alias"], imp["line"], imp["is_local"]))
            self.conn.commit()
            total += len(imports)
        cur.execute("SELECT COUNT(*) FROM dependencies")
        count = cur.fetchone()[0]
        self._close()
        return (1, {"extracted": total, "total": count}, None)

    def cmdExtractMethods(self, params):
        self._connect()
        cur = self.cursor
        cur.execute("DELETE FROM methods")
        self.conn.commit()
        cur.execute("SELECT id, file_name, code FROM files ORDER BY id")
        files = cur.fetchall()
        total = 0
        for file_id, file_name, code in files:
            methods = self._extractMethodsFromFile(code, file_id, file_name)
            for m in methods:
                self._insertMethod(m)
            self.conn.commit()
            total += len(methods)
        cur.execute("SELECT COUNT(*) FROM methods")
        count = cur.fetchone()[0]
        cur.execute(
            "SELECT SUM(CASE WHEN bcl_ir IS NOT NULL THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN length(description) > 0 THEN 1 ELSE 0 END) FROM methods")
        completeness = cur.fetchone()
        self.state["methods_extracted"] = total
        self.state["method_count"] = count
        self.state["has_bcl_ir"] = completeness[0]
        self.state["has_desc"] = completeness[1]
        self._close()
        return (1, self.state, None)

    def cmdExtractAll(self, params):
        self._connect()
        cur = self.cursor
        cur.execute("SELECT id, file_name, code FROM files ORDER BY id")
        files = cur.fetchall()
        deps_total = 0
        for file_id, file_name, code in files:
            imports = self._extractImports(code, file_id, file_name)
            for imp in imports:
                cur.execute(
                    "INSERT OR IGNORE INTO dependencies (file_id, file_name, "
                    "import_type, module, alias, line, is_local) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (imp["file_id"], imp["file_name"], imp["import_type"],
                     imp["module"], imp["alias"], imp["line"], imp["is_local"]))
            self.conn.commit()
            deps_total += len(imports)
        cur.execute("DELETE FROM methods")
        self.conn.commit()
        methods_total = 0
        for file_id, file_name, code in files:
            methods = self._extractMethodsFromFile(code, file_id, file_name)
            for m in methods:
                self._insertMethod(m)
            self.conn.commit()
            methods_total += len(methods)
        cur.execute("SELECT COUNT(*) FROM dependencies")
        dep_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        method_count = cur.fetchone()[0]
        self.state = {
            "deps_extracted": deps_total, "dep_count": dep_count,
            "methods_extracted": methods_total, "method_count": method_count}
        self._close()
        return (1, self.state, None)

    def readState(self):
        return (1, self.state, None)


if __name__ == "__main__":
    ingester = CodeIngester()
    result = ingester.Run("ingest_all")
    state = result[1]
    print(f"Files ingested: {state['files_ingested']}")
    print(f"Deps extracted: {state['deps_extracted']}")
    print(f"DB file count:  {state['file_count']}")
    print(f"DB dep count:   {state['dep_count']} (deduplicated)")
    print(f"Unique modules: {state['unique_modules']}")
    print(f"Local deps:     {state['local_deps']}")
    print()
    result2 = ingester.Run("extract_methods")
    state2 = result2[1]
    print(f"Methods extracted: {state2['methods_extracted']}")
    print(f"DB method count:   {state2['method_count']}")
    print(f"Has bcl_ir:        {state2['has_bcl_ir']}/{state2['method_count']}")
    print(f"Has description:   {state2['has_desc']}/{state2['method_count']}")
    print(f"\nDB location: {state['db_path']}")
