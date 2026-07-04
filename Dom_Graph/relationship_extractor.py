#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/relationship_extractor.py"
# date="2026-06-26" author="Devin" session_id="phase2-graph"
# context="Project Digital Twin Phase 2 Section 11 Relationship Extractor"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="relationship_extractor.py" domain="twin_relationships" authority="RelationshipExtractor"}
# [@SUMMARY]{summary="Relationship authority that extracts file, class, method, variable, database, GUI, API and thread edges from the codebase."}
# [@CLASS]{class="RelationshipExtractor" domain="relationships" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="extract_all" type="command"}
# [@METHOD]{method="extract_file_edges" type="command"}
# [@METHOD]{method="extract_class_edges" type="command"}
# [@METHOD]{method="extract_method_edges" type="command"}
# [@METHOD]{method="extract_method_variable_edges" type="command"}
# [@METHOD]{method="extract_method_database_edges" type="command"}
# [@METHOD]{method="extract_method_gui_edges" type="command"}
# [@METHOD]{method="extract_method_api_edges" type="command"}
# [@METHOD]{method="extract_method_thread_edges" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<RelationshipExtractor: extracts file class method variable database GUI API thread edges from codebase. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations.>][@todos<none>]}
"""
RelationshipExtractor -- authority for extracting relationships into edges.
Implements Section 11 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: extract_all, extract_file_edges, extract_class_edges,
          extract_method_edges.
"""
import ast
import json
import os
import re
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DB_CALL_PATTERN = re.compile(r"\b(?:cursor|conn|connection|db)\.execute\b")
GUI_CALL_PATTERN = re.compile(r"\b(?:tk|tkinter|Qt|PyQt|PySide)\b")
API_CALL_PATTERN = re.compile(r"\b(?:requests|urllib|httpx|aiohttp)\b")
THREAD_CALL_PATTERN = re.compile(r"\b(?:threading|asyncio|Thread|Lock|Queue)\b")


class RelationshipExtractor:
    """Authority for extracting code relationships into the edges table."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
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
        if command == "extract_all":
            return self.ExtractAll(params)
        elif command == "extract_file_edges":
            return self.ExtractFileEdges(params)
        elif command == "extract_class_edges":
            return self.ExtractClassEdges(params)
        elif command == "extract_method_edges":
            return self.ExtractMethodEdges(params)
        elif command == "extract_method_variable_edges":
            return self.ExtractMethodVariableEdges(params)
        elif command == "extract_method_database_edges":
            return self.ExtractMethodDatabaseEdges(params)
        elif command == "extract_method_gui_edges":
            return self.ExtractMethodGuiEdges(params)
        elif command == "extract_method_api_edges":
            return self.ExtractMethodApiEdges(params)
        elif command == "extract_method_thread_edges":
            return self.ExtractMethodThreadEdges(params)
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
        return self.state["db_conn"]

    def Now(self):
        return datetime.now(timezone.utc).isoformat()

    def AddEdge(self, cur, src_type, src_id, dst_type, dst_id, edge_type, evidence):
        cur.execute(
            "INSERT INTO edges (src_type, src_id, dst_type, dst_id, edge_type, "
            "evidence, confidence, created) VALUES (?,?,?,?,?,?,?,?)",
            (src_type, src_id, dst_type, dst_id, edge_type, evidence, 100.0,
             self.Now()),
        )

    def ExtractFileEdges(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT file_id, file_name, imports FROM files")
        rows = cur.fetchall()
        name_to_id = {}
        for row in rows:
            name_to_id[row[1]] = row[0]
        added = 0
        for row in rows:
            file_id, fname, imports_json = row
            imports = []
            if imports_json:
                try:
                    imports = json.loads(imports_json)
                except (ValueError, TypeError):
                    imports = []
            for imp in imports:
                base = imp.split(".")[0]
                candidate = base + ".py"
                tid = name_to_id.get(candidate)
                if tid is None:
                    for key, fid in name_to_id.items():
                        if key == base + ".py" or key.startswith(base + "_"):
                            tid = fid
                            break
                if tid is not None and tid != file_id:
                    self.AddEdge(cur, "file", file_id, "file", tid, "imports",
                                 "import " + str(imp))
                    added += 1
        conn.commit()
        record = {"edges_added": added, "files_processed": len(rows)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def ExtractClassEdges(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT class_id, class_name, parent, dependencies FROM classes")
        rows = cur.fetchall()
        name_to_id = {row[1]: row[0] for row in rows}
        added = 0
        for row in rows:
            class_id, class_name, parent, deps_json = row
            if parent and parent in name_to_id:
                self.AddEdge(cur, "class", class_id, "class",
                             name_to_id[parent], "inherits",
                             "parent=" + str(parent))
                added += 1
            deps = []
            if deps_json:
                try:
                    deps = json.loads(deps_json)
                except (ValueError, TypeError):
                    deps = []
            for dep in deps:
                if dep in name_to_id and name_to_id[dep] != class_id:
                    self.AddEdge(cur, "class", class_id, "class",
                                 name_to_id[dep], "depends_on",
                                 "dependency=" + str(dep))
                    added += 1
        conn.commit()
        record = {"edges_added": added, "classes_processed": len(rows)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def ExtractMethodEdges(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, class_id, method_name, method_code FROM methods")
        rows = cur.fetchall()
        name_to_ids = {}
        for row in rows:
            name_to_ids.setdefault(row[2], []).append(row[0])
        added = 0
        for row in rows:
            method_id, class_id, method_name, method_code = row
            code = method_code or ""
            calls = self.ExtractCallsFromCode(code)
            for call in calls:
                targets = name_to_ids.get(call, [])
                for tid in targets:
                    if tid != method_id:
                        self.AddEdge(cur, "method", method_id, "method", tid,
                                     "calls", "call=" + str(call))
                        added += 1
            if DB_CALL_PATTERN.search(code):
                self.AddEdge(cur, "method", method_id, "method", method_id,
                             "database_access", "cursor.execute")
                added += 1
            if GUI_CALL_PATTERN.search(code):
                self.AddEdge(cur, "method", method_id, "method", method_id,
                             "gui_call", "tk/Qt")
                added += 1
            if API_CALL_PATTERN.search(code):
                self.AddEdge(cur, "method", method_id, "method", method_id,
                             "api_call", "requests/urllib")
                added += 1
            if THREAD_CALL_PATTERN.search(code):
                self.AddEdge(cur, "method", method_id, "method", method_id,
                             "thread_call", "threading/asyncio")
                added += 1
        conn.commit()
        record = {"edges_added": added, "methods_processed": len(rows)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def ExtractCallsFromCode(self, code):
        calls = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute):
                    calls.append(func.attr)
                elif isinstance(func, ast.Name):
                    calls.append(func.id)
        return calls

    def ParseMethodTree(self, code):
        if not code:
            return None
        import textwrap
        dedented = textwrap.dedent(code)
        try:
            return ast.parse(dedented)
        except SyntaxError:
            return None

    def AttrChain(self, node):
        # Build dotted chain like "cursor.execute" or "requests.get"
        parts = []
        cur = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        parts.reverse()
        return parts

    def ExtractMethodVariableEdges(self, params):
        # 11.6 Method->Variable: parse variable reads/writes in method_code
        conn = self.Connect()
        cur = conn.cursor()
        method_id = self._p(params, "method_id")
        if method_id is not None:
            cur.execute(
                "SELECT method_id, method_code FROM methods WHERE method_id=?",
                (method_id,),
            )
        else:
            cur.execute("SELECT method_id, method_code FROM methods")
        rows = cur.fetchall()
        added = 0
        for row in rows:
            mid, code = row
            tree = self.ParseMethodTree(code)
            if tree is None:
                continue
            reads = set()
            writes = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    if isinstance(node.ctx, ast.Load):
                        reads.add(node.id)
                    elif isinstance(node.ctx, (ast.Store, ast.Del)):
                        writes.add(node.id)
                elif isinstance(node, ast.Attribute):
                    if isinstance(node.value, ast.Name):
                        if isinstance(node.ctx, ast.Load):
                            reads.add(node.value.id)
                        elif isinstance(node.ctx, (ast.Store, ast.Del)):
                            writes.add(node.value.id)
            for var in sorted(writes):
                self.AddEdge(cur, "method", mid, "variable", 0,
                             "writes", "var=" + str(var))
                added += 1
            for var in sorted(reads):
                self.AddEdge(cur, "method", mid, "variable", 0,
                             "reads", "var=" + str(var))
                added += 1
        conn.commit()
        record = {"edges_added": added, "methods_processed": len(rows)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def ExtractMethodDatabaseEdges(self, params):
        # 11.7 Method->Database: find cursor.execute, conn.execute in method_code
        conn = self.Connect()
        cur = conn.cursor()
        method_id = self._p(params, "method_id")
        if method_id is not None:
            cur.execute(
                "SELECT method_id, method_code FROM methods WHERE method_id=?",
                (method_id,),
            )
        else:
            cur.execute("SELECT method_id, method_code FROM methods")
        rows = cur.fetchall()
        added = 0
        db_roots = ("cursor", "conn", "connection", "db", "session")
        exec_attrs = ("execute", "executemany", "executescript", "commit",
                      "rollback", "fetchone", "fetchall", "fetchmany")
        for row in rows:
            mid, code = row
            tree = self.ParseMethodTree(code)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not isinstance(func, ast.Attribute):
                    continue
                chain = self.AttrChain(func)
                if len(chain) >= 2 and chain[0] in db_roots and \
                        chain[-1] in exec_attrs:
                    self.AddEdge(cur, "method", mid, "database", 0,
                                 "database_access",
                                 ".".join(chain))
                    added += 1
        conn.commit()
        record = {"edges_added": added, "methods_processed": len(rows)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def ExtractMethodGuiEdges(self, params):
        # 11.8 Method->GUI: find Tkinter/Qt calls in method_code
        conn = self.Connect()
        cur = conn.cursor()
        method_id = self._p(params, "method_id")
        if method_id is not None:
            cur.execute(
                "SELECT method_id, method_code FROM methods WHERE method_id=?",
                (method_id,),
            )
        else:
            cur.execute("SELECT method_id, method_code FROM methods")
        rows = cur.fetchall()
        added = 0
        gui_roots = ("tk", "tkinter", "Qt", "PyQt", "PySide", "QtWidgets",
                     "QtGui", "QtCore", "QApplication", "QWidget", "Tk",
                     "ttk", "messagebox", "filedialog")
        gui_attrs = ("mainloop", "pack", "grid", "place", "bind", "configure",
                     "config", "get", "set", "show", "hide", "clicked",
                     "connect", "exec", "exec_", "setText", "text", "Button",
                     "Label", "Entry", "Frame", "Window", "Dialog")
        for row in rows:
            mid, code = row
            tree = self.ParseMethodTree(code)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    chain = self.AttrChain(func) if isinstance(
                        func, (ast.Attribute, ast.Name)) else []
                    if not chain:
                        continue
                    if chain[0] in gui_roots or chain[-1] in gui_attrs or \
                            any(part in gui_roots for part in chain):
                        self.AddEdge(cur, "method", mid, "gui", 0,
                                     "gui_call", ".".join(chain))
                        added += 1
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in gui_roots:
                            self.AddEdge(cur, "method", mid, "gui", 0,
                                         "gui_import", alias.name)
                            added += 1
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split(".")[0] in gui_roots:
                        self.AddEdge(cur, "method", mid, "gui", 0,
                                     "gui_import", node.module)
                        added += 1
        conn.commit()
        record = {"edges_added": added, "methods_processed": len(rows)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def ExtractMethodApiEdges(self, params):
        # 11.9 Method->API: find requests.get/post, urllib calls
        conn = self.Connect()
        cur = conn.cursor()
        method_id = self._p(params, "method_id")
        if method_id is not None:
            cur.execute(
                "SELECT method_id, method_code FROM methods WHERE method_id=?",
                (method_id,),
            )
        else:
            cur.execute("SELECT method_id, method_code FROM methods")
        rows = cur.fetchall()
        added = 0
        api_roots = ("requests", "urllib", "httpx", "aiohttp", "http",
                     "urllib2", "urllib3")
        api_attrs = ("get", "post", "put", "delete", "patch", "head",
                     "request", "urlopen", "Request", "Session", "Client",
                     "fetch", "AsyncClient")
        for row in rows:
            mid, code = row
            tree = self.ParseMethodTree(code)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    chain = self.AttrChain(func) if isinstance(
                        func, (ast.Attribute, ast.Name)) else []
                    if not chain:
                        continue
                    if chain[0] in api_roots or chain[-1] in api_attrs:
                        self.AddEdge(cur, "method", mid, "api", 0,
                                     "api_call", ".".join(chain))
                        added += 1
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in api_roots:
                            self.AddEdge(cur, "method", mid, "api", 0,
                                         "api_import", alias.name)
                            added += 1
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split(".")[0] in api_roots:
                        self.AddEdge(cur, "method", mid, "api", 0,
                                     "api_import", node.module)
                        added += 1
        conn.commit()
        record = {"edges_added": added, "methods_processed": len(rows)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def ExtractMethodThreadEdges(self, params):
        # 11.10 Method->Thread: find threading.Thread, asyncio usage
        conn = self.Connect()
        cur = conn.cursor()
        method_id = self._p(params, "method_id")
        if method_id is not None:
            cur.execute(
                "SELECT method_id, method_code FROM methods WHERE method_id=?",
                (method_id,),
            )
        else:
            cur.execute("SELECT method_id, method_code FROM methods")
        rows = cur.fetchall()
        added = 0
        thread_roots = ("threading", "asyncio", "concurrent", "multiprocessing",
                        "queue", "Queue")
        thread_attrs = ("Thread", "Lock", "RLock", "Semaphore", "Event",
                        "Condition", "Queue", "gather", "create_task",
                        "run", "start", "join", "sleep", "wait", "notify",
                        "acquire", "release", "run_until_complete",
                        "get_event_loop", "new_event_loop", "Future",
                        "Task", "Pool", "Process")
        for row in rows:
            mid, code = row
            tree = self.ParseMethodTree(code)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    chain = self.AttrChain(func) if isinstance(
                        func, (ast.Attribute, ast.Name)) else []
                    if not chain:
                        continue
                    if chain[0] in thread_roots or chain[-1] in thread_attrs:
                        self.AddEdge(cur, "method", mid, "thread", 0,
                                     "thread_call", ".".join(chain))
                        added += 1
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in thread_roots:
                            self.AddEdge(cur, "method", mid, "thread", 0,
                                         "thread_import", alias.name)
                            added += 1
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split(".")[0] in thread_roots:
                        self.AddEdge(cur, "method", mid, "thread", 0,
                                     "thread_import", node.module)
                        added += 1
        conn.commit()
        record = {"edges_added": added, "methods_processed": len(rows)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def ExtractAll(self, params):
        results = {}
        for step in ("extract_file_edges", "extract_class_edges",
                     "extract_method_edges", "extract_method_variable_edges",
                     "extract_method_database_edges",
                     "extract_method_gui_edges",
                     "extract_method_api_edges",
                     "extract_method_thread_edges"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        return (1, results, None)
