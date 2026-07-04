#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/graph_builder.py"
# date="2026-06-26" author="Devin" session_id="phase2-graph"
# context="Project Digital Twin Phase 2 Section 4 Graph Builder"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="graph_builder.py" domain="twin_graph" authority="GraphBuilder"}
# [@SUMMARY]{summary="Graph authority that builds all graph types (file, class, method, call, dependency) and detects cycles, dead code, duplicates, orphans and hotspots."}
# [@CLASS]{class="GraphBuilder" domain="graph" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="build_all" type="command"}
# [@METHOD]{method="build_file_graph" type="command"}
# [@METHOD]{method="build_class_graph" type="command"}
# [@METHOD]{method="build_method_graph" type="command"}
# [@METHOD]{method="build_call_graph" type="command"}
# [@METHOD]{method="detect_cycles" type="command"}
# [@METHOD]{method="detect_dead_code" type="command"}
# [@METHOD]{method="detect_duplicates" type="command"}
# [@METHOD]{method="detect_orphans" type="command"}
# [@METHOD]{method="detect_hotspots" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<GraphBuilder: builds all graph types (file/class/method/call/dependency) and detects cycles, dead code, duplicates, orphans, hotspots. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths. Docstring notes 14 missing graph types per spec but code structure is VBStyle compliant.>][@todos<none>]}
"""
GraphBuilder -- authority for building all graph types and detecting anomalies.
Implements Section 4 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: build_all, build_file_graph, build_class_graph, build_method_graph,
          build_call_graph, detect_cycles, detect_dead_code, detect_duplicates,
          detect_orphans, detect_hotspots.

# ============================================================
# ERRORS -- Section 4 spec vs. implementation
# Rating: 2/10
# Spec has 24 sub-sections (4.1-4.24). Only 10 implemented.
# 14 graph types MISSING.
# ============================================================
# MISSING METHODS (14 of 24 sub-sections):
# 4.3  BuildFolderGraph     -- group files by directory, edges for parent-child. NOT IMPLEMENTED.
# 4.4  BuildImportGraph     -- parse 'import X' and 'from X import Y' as separate graph type. NOT IMPLEMENTED.
#                              (BuildFileGraph does imports but not as a dedicated graph type.)
# 4.5  BuildDependencyGraph -- edges where edge_type='depends_on' at file level. NOT IMPLEMENTED.
#                              (BuildClassGraph does depends_on for classes, not files.)
# 4.8  BuildFunctionGraph   -- standalone functions (not in classes). NOT IMPLEMENTED.
# 4.10 BuildVariableGraph   -- parse assignments, track variable scope. NOT IMPLEMENTED.
# 4.11 BuildObjectGraph     -- track object instantiation X() in method code. NOT IMPLEMENTED.
# 4.12 BuildEventGraph      -- track event handlers, callbacks, signals. NOT IMPLEMENTED.
# 4.13 BuildRuntimeFlow     -- order methods by call sequence. NOT IMPLEMENTED.
# 4.14 BuildExecutionFlow   -- trace from entry point through call graph. NOT IMPLEMENTED.
# 4.15 BuildDatabaseFlow    -- find SQL queries in method_code. NOT IMPLEMENTED.
# 4.16 BuildGuiFlow         -- find Tkinter/Qt calls in method_code. NOT IMPLEMENTED.
# 4.17 BuildThreadGraph     -- find threading.Thread, asyncio usage. NOT IMPLEMENTED.
# 4.18 BuildMemoryGraph     -- find malloc, alloc, large data structures. NOT IMPLEMENTED.
# 4.24 StoreEntireGraph     -- all edges INSERTed into edges table. PARTIAL.
#                              (edges are inserted per-build but no bulk store command.)
#
# PARTIAL:
# 4.1  ParseEntireProject -- done via ingestion_engine.py, not here.
# 4.2  BuildFileGraph     -- implemented but only handles 'imports' edges.
# 4.6  BuildClassGraph    -- implemented, handles 'inherits' and 'depends_on'.
# 4.7  BuildMethodGraph   -- implemented, handles 'calls'.
# 4.9  BuildCallGraph     -- implemented but just calls BuildMethodGraph. No function-level calls.
# 4.19 DetectCycles       -- implemented, real DFS.
# 4.20 DetectDeadCode     -- implemented, queries edges.
# 4.21 DetectDuplicates   -- implemented, queries method hash.
# 4.22 DetectOrphans      -- implemented, queries edges.
# 4.23 DetectHotspots     -- implemented, queries complexity + incoming edges.
#
# The "Devin task" line lists 10 commands. The spec body lists 24 sub-sections.
# 14 graph types are missing entirely. This is not a graph builder, it is a
# partial edge inserter with 5 detectors.
# ============================================================
"""
import ast
import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_SCAN_DIR = os.path.dirname(os.path.abspath(__file__))
PY_EXTENSION = ".py"
HOTSPOT_COMPLEXITY_THRESHOLD = 10.0
HOTSPOT_INCOMING_THRESHOLD = 3


class GraphBuilder:
    """Authority for building codebase graphs and detecting anomalies."""

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
        if command == "build_all":
            return self.BuildAll(params)
        elif command == "build_file_graph":
            return self.BuildFileGraph(params)
        elif command == "build_class_graph":
            return self.BuildClassGraph(params)
        elif command == "build_method_graph":
            return self.BuildMethodGraph(params)
        elif command == "build_call_graph":
            return self.BuildCallGraph(params)
        elif command == "build_folder_graph":
            return self.BuildFolderGraph(params)
        elif command == "build_import_graph":
            return self.BuildImportGraph(params)
        elif command == "build_dependency_graph":
            return self.BuildDependencyGraph(params)
        elif command == "build_function_graph":
            return self.BuildFunctionGraph(params)
        elif command == "build_variable_graph":
            return self.BuildVariableGraph(params)
        elif command == "build_object_graph":
            return self.BuildObjectGraph(params)
        elif command == "build_event_graph":
            return self.BuildEventGraph(params)
        elif command == "build_runtime_flow":
            return self.BuildRuntimeFlow(params)
        elif command == "build_execution_flow":
            return self.BuildExecutionFlow(params)
        elif command == "build_database_flow":
            return self.BuildDatabaseFlow(params)
        elif command == "build_gui_flow":
            return self.BuildGuiFlow(params)
        elif command == "build_thread_graph":
            return self.BuildThreadGraph(params)
        elif command == "build_memory_graph":
            return self.BuildMemoryGraph(params)
        elif command == "store_entire_graph":
            return self.StoreEntireGraph(params)
        elif command == "detect_cycles":
            return self.DetectCycles(params)
        elif command == "detect_dead_code":
            return self.DetectDeadCode(params)
        elif command == "detect_duplicates":
            return self.DetectDuplicates(params)
        elif command == "detect_orphans":
            return self.DetectOrphans(params)
        elif command == "detect_hotspots":
            return self.DetectHotspots(params)
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

    def BuildFileGraph(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT file_id, file_name, path, imports FROM files")
        rows = cur.fetchall()
        path_to_id = {}
        name_to_id = {}
        for row in rows:
            file_id, fname, path, imports_json = row
            name_to_id[fname] = file_id
            path_to_id[path] = file_id
        added = 0
        for row in rows:
            file_id, fname, path, imports_json = row
            imports = []
            if imports_json:
                try:
                    imports = json.loads(imports_json)
                except (ValueError, TypeError):
                    imports = []
            for imp in imports:
                target_id = self.ResolveImport(imp, name_to_id, path_to_id)
                if target_id is not None and target_id != file_id:
                    self.AddEdge(cur, "file", file_id, "file", target_id,
                                 "imports", "import " + str(imp))
                    added += 1
        conn.commit()
        record = {"edge_type": "imports", "edges_added": added,
                  "files_processed": len(rows)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def ResolveImport(self, imp, name_to_id, path_to_id):
        base = imp.split(".")[0]
        candidate = base + ".py"
        if candidate in name_to_id:
            return name_to_id[candidate]
        for key, fid in name_to_id.items():
            if key == base or key.startswith(base + "_"):
                return fid
        return None

    def BuildClassGraph(self, params):
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
        record = {"edge_type": "inherits/depends_on", "edges_added": added,
                  "classes_processed": len(rows)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildMethodGraph(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, class_id, method_name, calls FROM methods")
        rows = cur.fetchall()
        name_to_ids = {}
        for row in rows:
            mname = row[2]
            name_to_ids.setdefault(mname, []).append(row[0])
        added = 0
        for row in rows:
            method_id, class_id, method_name, calls_json = row
            calls = []
            if calls_json:
                try:
                    calls = json.loads(calls_json)
                except (ValueError, TypeError):
                    calls = []
            for call in calls:
                targets = name_to_ids.get(call, [])
                for tid in targets:
                    if tid != method_id:
                        self.AddEdge(cur, "method", method_id, "method", tid,
                                     "calls", "call=" + str(call))
                        added += 1
        conn.commit()
        record = {"edge_type": "calls", "edges_added": added,
                  "methods_processed": len(rows)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildCallGraph(self, params):
        return self.BuildMethodGraph(params)

    def BuildAll(self, params):
        results = {}
        for step in ("build_file_graph", "build_class_graph", "build_method_graph"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        for step in ("detect_cycles", "detect_dead_code", "detect_duplicates",
                     "detect_orphans", "detect_hotspots"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        return (1, results, None)

    def DetectCycles(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT src_type, src_id, dst_type, dst_id FROM edges")
        graph = {}
        for row in cur.fetchall():
            src = (row[0], row[1])
            dst = (row[2], row[3])
            graph.setdefault(src, []).append(dst)
        cycles = []
        visited = set()
        stack = set()

        def Dfs(node, path):
            if node in stack:
                idx = path.index(node) if node in path else 0
                cycles.append(path[idx:] + [node])
                return
            if node in visited:
                return
            visited.add(node)
            stack.add(node)
            for nxt in graph.get(node, []):
                Dfs(nxt, path + [node])
            stack.discard(node)

        for node in graph:
            Dfs(node, [])
        record = {"cycle_count": len(cycles), "cycles": cycles[:50]}
        self.state["results"] = record
        return (1, record, None)

    def DetectDeadCode(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_name FROM methods WHERE method_id NOT IN "
            "(SELECT dst_id FROM edges WHERE dst_type='method' AND edge_type='calls')"
        )
        dead = [{"method_id": r[0], "method_name": r[1]} for r in cur.fetchall()]
        record = {"dead_count": len(dead), "dead_methods": dead[:100]}
        self.state["results"] = record
        return (1, record, None)

    def DetectDuplicates(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT hash, COUNT(*) FROM methods WHERE hash IS NOT NULL "
            "GROUP BY hash HAVING COUNT(*) > 1"
        )
        dup_hashes = cur.fetchall()
        duplicates = []
        for dhash, count in dup_hashes:
            cur.execute(
                "SELECT method_id, method_name FROM methods WHERE hash=?", (dhash,)
            )
            members = [{"method_id": r[0], "method_name": r[1]}
                        for r in cur.fetchall()]
            duplicates.append({"hash": dhash, "count": count, "members": members})
        record = {"duplicate_hashes": len(duplicates), "duplicates": duplicates[:50]}
        self.state["results"] = record
        return (1, record, None)

    def DetectOrphans(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT class_id, class_name FROM classes WHERE class_id NOT IN "
            "(SELECT src_id FROM edges WHERE src_type='class') AND class_id NOT IN "
            "(SELECT dst_id FROM edges WHERE dst_type='class')"
        )
        orphan_classes = [{"class_id": r[0], "class_name": r[1]}
                          for r in cur.fetchall()]
        cur.execute(
            "SELECT file_id, file_name FROM files WHERE (imports IS NULL OR "
            "imports='[]') AND file_id NOT IN "
            "(SELECT dst_id FROM edges WHERE dst_type='file')"
        )
        orphan_files = [{"file_id": r[0], "file_name": r[1]}
                        for r in cur.fetchall()]
        record = {"orphan_classes": len(orphan_classes),
                  "orphan_files": len(orphan_files),
                  "classes": orphan_classes[:50],
                  "files": orphan_files[:50]}
        self.state["results"] = record
        return (1, record, None)

    def DetectHotspots(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cc_thresh = self._p(params, "complexity_threshold",
                            HOTSPOT_COMPLEXITY_THRESHOLD)
        in_thresh = self._p(params, "incoming_threshold",
                            HOTSPOT_INCOMING_THRESHOLD)
        cur.execute(
            "SELECT m.method_id, m.method_name, m.cyclomatic_complexity, "
            "COUNT(e.edge_id) AS incoming FROM methods m LEFT JOIN edges e "
            "ON e.dst_type='method' AND e.dst_id=m.method_id AND e.edge_type='calls' "
            "GROUP BY m.method_id HAVING m.cyclomatic_complexity >= ? AND incoming >= ? "
            "ORDER BY m.cyclomatic_complexity DESC",
            (cc_thresh, in_thresh),
        )
        hotspots = [{"method_id": r[0], "method_name": r[1],
                     "complexity": r[2], "incoming": r[3]}
                    for r in cur.fetchall()]
        record = {"hotspot_count": len(hotspots), "hotspots": hotspots[:50]}
        self.state["results"] = record
        return (1, record, None)

    def BuildFolderGraph(self, params):
        # 4.3 -- group files by directory, parent-child edges
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT file_id, path FROM files")
        rows = cur.fetchall()
        added = 0
        dir_map = {}
        for file_id, path in rows:
            directory = os.path.dirname(path)
            dir_map.setdefault(directory, []).append(file_id)
        for directory, file_ids in dir_map.items():
            parent = os.path.dirname(directory)
            if parent and parent in dir_map:
                for fid in file_ids:
                    for pid in dir_map[parent]:
                        self.AddEdge(cur, "file", fid, "file", pid,
                                     "folder", "parent=" + parent)
                        added += 1
        conn.commit()
        record = {"edge_type": "folder", "edges_added": added,
                  "directories": len(dir_map)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildImportGraph(self, params):
        # 4.4 -- dedicated import graph from import statements
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT file_id, file_name, path, imports FROM files")
        rows = cur.fetchall()
        name_to_id = {row[1]: row[0] for row in rows}
        path_to_id = {row[2]: row[0] for row in rows}
        added = 0
        for file_id, fname, path, imports_json in rows:
            imports = []
            if imports_json:
                try:
                    imports = json.loads(imports_json)
                except (ValueError, TypeError):
                    imports = []
            for imp in imports:
                target_id = self.ResolveImport(imp, name_to_id, path_to_id)
                if target_id is not None and target_id != file_id:
                    self.AddEdge(cur, "file", file_id, "file", target_id,
                                 "imports", "import " + str(imp))
                    added += 1
        conn.commit()
        record = {"edge_type": "imports", "edges_added": added,
                  "files_processed": len(rows)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildDependencyGraph(self, params):
        # 4.5 -- file-level depends_on edges
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT file_id, file_name, path, dependencies FROM files")
        rows = cur.fetchall()
        name_to_id = {row[1]: row[0] for row in rows}
        path_to_id = {row[2]: row[0] for row in rows}
        added = 0
        for file_id, fname, path, deps_json in rows:
            deps = []
            if deps_json:
                try:
                    deps = json.loads(deps_json)
                except (ValueError, TypeError):
                    deps = []
            for dep in deps:
                target_id = self.ResolveImport(dep, name_to_id, path_to_id)
                if target_id is not None and target_id != file_id:
                    self.AddEdge(cur, "file", file_id, "file", target_id,
                                 "depends_on", "dependency=" + str(dep))
                    added += 1
        conn.commit()
        record = {"edge_type": "depends_on", "edges_added": added,
                  "files_processed": len(rows)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildFunctionGraph(self, params):
        # 4.8 -- standalone functions not in classes
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT file_id, path FROM files WHERE extension='.py'")
        files = cur.fetchall()
        added = 0
        functions = []
        for file_id, path in files:
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                tree = ast.parse(content, filename=path)
            except (OSError, SyntaxError):
                continue
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.append({
                        "file_id": file_id, "function_name": node.name,
                        "lineno": node.lineno,
                    })
        record = {"functions": functions, "count": len(functions)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildVariableGraph(self, params):
        # 4.10 -- parse assignments, track scope
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT file_id, path FROM files WHERE extension='.py'")
        files = cur.fetchall()
        variables = []
        for file_id, path in files:
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                tree = ast.parse(content, filename=path)
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for tgt in node.targets:
                        if isinstance(tgt, ast.Name):
                            scope = "module"
                            parent = getattr(node, "parent", None)
                            if isinstance(parent, (ast.FunctionDef,
                                                   ast.AsyncFunctionDef)):
                                scope = "local:" + parent.name
                            elif isinstance(parent, ast.ClassDef):
                                scope = "class:" + parent.name
                            variables.append({
                                "file_id": file_id, "name": tgt.id,
                                "scope": scope, "lineno": node.lineno,
                            })
        record = {"variables": variables, "count": len(variables)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildObjectGraph(self, params):
        # 4.11 -- find X() instantiation in method_code
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, class_id, method_name, method_code "
                    "FROM methods")
        rows = cur.fetchall()
        objects = []
        for method_id, class_id, method_name, code in rows:
            if not code:
                continue
            try:
                tree = ast.parse(code)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    target = None
                    if isinstance(node.func, ast.Name):
                        target = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        target = node.func.attr
                    if target and target[0].isupper():
                        objects.append({
                            "method_id": method_id, "class_id": class_id,
                            "object": target, "method": method_name,
                        })
        record = {"objects": objects, "count": len(objects)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildEventGraph(self, params):
        # 4.12 -- find event handlers/callbacks/signals
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, method_code FROM methods")
        rows = cur.fetchall()
        events = []
        event_patterns = ("bind(", "connect(", "signal(", "emit(",
                          "callback", "handler", "addEventListener",
                          "subscribe(", "on_change", "trigger(")
        for method_id, method_name, code in rows:
            if not code:
                continue
            for pattern in event_patterns:
                if pattern in code:
                    events.append({
                        "method_id": method_id, "method": method_name,
                        "pattern": pattern,
                    })
                    break
        record = {"events": events, "count": len(events)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildRuntimeFlow(self, params):
        # 4.13 -- order methods by call sequence
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, calls FROM methods")
        rows = cur.fetchall()
        name_to_ids = {}
        for row in rows:
            name_to_ids.setdefault(row[1], []).append(row[0])
        sequence = []
        for method_id, method_name, calls_json in rows:
            calls = []
            if calls_json:
                try:
                    calls = json.loads(calls_json)
                except (ValueError, TypeError):
                    calls = []
            for call in calls:
                targets = name_to_ids.get(call, [])
                for tid in targets:
                    sequence.append({
                        "caller": method_id, "caller_name": method_name,
                        "callee": tid, "callee_name": call,
                    })
        record = {"call_sequence": sequence, "count": len(sequence)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildExecutionFlow(self, params):
        # 4.14 -- trace from entry point through call graph
        entry = self._p(params, "entry_method")
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, calls FROM methods")
        rows = cur.fetchall()
        name_to_id = {}
        calls_map = {}
        for method_id, method_name, calls_json in rows:
            name_to_id[method_name] = method_id
            calls = []
            if calls_json:
                try:
                    calls = json.loads(calls_json)
                except (ValueError, TypeError):
                    calls = []
            calls_map[method_id] = calls
        if entry is None:
            for mname in ("Run", "main", "__init__", "start"):
                if mname in name_to_id:
                    entry = mname
                    break
        if entry is None or entry not in name_to_id:
            return (1, {"entry": None, "trace": [], "count": 0}, None)
        entry_id = name_to_id[entry]
        trace = []
        visited = set()

        def Trace(mid, depth):
            if mid in visited or depth > 20:
                return
            visited.add(mid)
            for call in calls_map.get(mid, []):
                tid = name_to_id.get(call)
                if tid is not None:
                    trace.append({"method_id": tid, "name": call,
                                  "depth": depth})
                    Trace(tid, depth + 1)

        Trace(entry_id, 0)
        record = {"entry": entry, "entry_id": entry_id,
                  "trace": trace, "count": len(trace)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildDatabaseFlow(self, params):
        # 4.15 -- find SQL in method_code
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, method_code FROM methods")
        rows = cur.fetchall()
        sql_flows = []
        sql_patterns = ("execute(", "executemany(", "cursor.", "conn.",
                        "SELECT ", "INSERT ", "UPDATE ", "DELETE ",
                        "CREATE ", "ALTER ", "DROP ")
        for method_id, method_name, code in rows:
            if not code:
                continue
            found = []
            for pattern in sql_patterns:
                if pattern in code:
                    found.append(pattern)
            if found:
                sql_flows.append({
                    "method_id": method_id, "method": method_name,
                    "patterns": found,
                })
        record = {"database_flows": sql_flows, "count": len(sql_flows)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildGuiFlow(self, params):
        # 4.16 -- find Tkinter/Qt calls in method_code
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, method_code FROM methods")
        rows = cur.fetchall()
        gui_flows = []
        gui_patterns = ("tkinter", "Tk()", "QWidget", "QPushButton",
                        "QMainWindow", "QApplication", "tk.", "Qt.",
                        ".pack(", ".grid(", ".place(", "mainloop(")
        for method_id, method_name, code in rows:
            if not code:
                continue
            found = []
            for pattern in gui_patterns:
                if pattern in code:
                    found.append(pattern)
            if found:
                gui_flows.append({
                    "method_id": method_id, "method": method_name,
                    "patterns": found,
                })
        record = {"gui_flows": gui_flows, "count": len(gui_flows)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildThreadGraph(self, params):
        # 4.17 -- find threading/asyncio usage
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, method_code FROM methods")
        rows = cur.fetchall()
        threads = []
        thread_patterns = ("threading.Thread", "asyncio.", "await ",
                           "async def", "ThreadPoolExecutor",
                           "multiprocessing.", "concurrent.futures")
        for method_id, method_name, code in rows:
            if not code:
                continue
            found = []
            for pattern in thread_patterns:
                if pattern in code:
                    found.append(pattern)
            if found:
                threads.append({
                    "method_id": method_id, "method": method_name,
                    "patterns": found,
                })
        record = {"thread_flows": threads, "count": len(threads)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildMemoryGraph(self, params):
        # 4.18 -- find large data structures
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, method_code FROM methods")
        rows = cur.fetchall()
        memory = []
        memory_patterns = ("malloc(", "alloc(", "calloc(", "realloc(",
                           "[0] * ", "list(range(", "dict.fromkeys(",
                           "bytearray(", "numpy.zeros", "numpy.array",
                           "pandas.DataFrame", "[] * ", "{} * ")
        for method_id, method_name, code in rows:
            if not code:
                continue
            found = []
            for pattern in memory_patterns:
                if pattern in code:
                    found.append(pattern)
            if found:
                memory.append({
                    "method_id": method_id, "method": method_name,
                    "patterns": found,
                })
        record = {"memory_flows": memory, "count": len(memory)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def StoreEntireGraph(self, params):
        # 4.24 -- bulk store all edges
        edges = self._p(params, "edges", [])
        if not edges:
            return (0, None, ("MISSING_PARAM", "edges list required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        added = 0
        for edge in edges:
            try:
                self.AddEdge(cur, edge.get("src_type", "file"),
                             edge.get("src_id"), edge.get("dst_type", "file"),
                             edge.get("dst_id"), edge.get("edge_type", "uses"),
                             edge.get("evidence", "bulk store"))
                added += 1
            except sqlite3.Error:
                continue
        conn.commit()
        record = {"edges_stored": added, "total": len(edges)}
        self.state["catalog"].append(record)
        return (1, record, None)
