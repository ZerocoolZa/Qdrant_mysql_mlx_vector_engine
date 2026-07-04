#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/graph_builder.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 4: Graph Original Codebase -- 24 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="graph_builder.py" domain="twin_graph" authority="GraphBuilder"}
# [@SUMMARY]{summary="Graph authority: parse project, build file/folder/import/dependency/class/method/function/call/variable/object/event/runtime/execution/database/GUI/thread/memory graphs, detect cycles/dead code/duplicates/orphans/hotspots, store entire graph."}
# [@CLASS]{class="GraphBuilder" domain="graph" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="parse_project" type="command"}
# [@METHOD]{method="build_file_graph" type="command"}
# [@METHOD]{method="build_folder_graph" type="command"}
# [@METHOD]{method="build_import_graph" type="command"}
# [@METHOD]{method="build_dependency_graph" type="command"}
# [@METHOD]{method="build_class_graph" type="command"}
# [@METHOD]{method="build_method_graph" type="command"}
# [@METHOD]{method="build_function_graph" type="command"}
# [@METHOD]{method="build_call_graph" type="command"}
# [@METHOD]{method="build_variable_graph" type="command"}
# [@METHOD]{method="build_object_graph" type="command"}
# [@METHOD]{method="build_event_graph" type="command"}
# [@METHOD]{method="build_runtime_flow" type="command"}
# [@METHOD]{method="build_execution_flow" type="command"}
# [@METHOD]{method="build_database_flow" type="command"}
# [@METHOD]{method="build_gui_flow" type="command"}
# [@METHOD]{method="build_thread_graph" type="command"}
# [@METHOD]{method="build_memory_graph" type="command"}
# [@METHOD]{method="detect_cycles" type="command"}
# [@METHOD]{method="detect_dead_code" type="command"}
# [@METHOD]{method="detect_duplicates" type="command"}
# [@METHOD]{method="detect_orphans" type="command"}
# [@METHOD]{method="detect_hotspots" type="command"}
# [@METHOD]{method="store_graph" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import ast
import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"
HOTSPOT_COMPLEXITY_THRESHOLD = 10.0
HOTSPOT_INCOMING_THRESHOLD = 3


class GraphBuilder:
    """Authority for building all graph types and detecting anomalies."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "scan_dir": os.path.dirname(os.path.abspath(__file__)),
                "extension": ".py",
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
        if command == "parse_project":
            return self.ParseProject(params)
        elif command == "build_file_graph":
            return self.BuildFileGraph(params)
        elif command == "build_folder_graph":
            return self.BuildFolderGraph(params)
        elif command == "build_import_graph":
            return self.BuildImportGraph(params)
        elif command == "build_dependency_graph":
            return self.BuildDependencyGraph(params)
        elif command == "build_class_graph":
            return self.BuildClassGraph(params)
        elif command == "build_method_graph":
            return self.BuildMethodGraph(params)
        elif command == "build_function_graph":
            return self.BuildFunctionGraph(params)
        elif command == "build_call_graph":
            return self.BuildCallGraph(params)
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
        elif command == "detect_cycles":
            return self.DetectCycles(params)
        elif command == "detect_dead_code":
            return self.DetectDeadCode(params)
        elif command == "detect_duplicate_code":
            return self.DetectDuplicateCode(params)
        elif command == "detect_orphans":
            return self.DetectOrphans(params)
        elif command == "detect_hotspots":
            return self.DetectHotspots(params)
        elif command == "store_graph":
            return self.StoreGraph(params)
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

    def AddEdge(self, cur, src_type, src_id, dst_type, dst_id, edge_type, evidence):
        cur.execute(
            "INSERT INTO edges (src_type, src_id, dst_type, dst_id, edge_type, "
            "evidence, confidence, created) VALUES (?,?,?,?,?,?,?,?)",
            (src_type, src_id, dst_type, dst_id, edge_type, evidence, 100.0,
             self.Now()[1]),
        )

    def ParseProject(self, params):
        scan_dir = self._p(params, "scan_dir", self.state["config"]["scan_dir"])
        files = []
        for root, dirs, fnames in os.walk(scan_dir):
            for fname in fnames:
                if fname.endswith(".py"):
                    files.append(os.path.join(root, fname))
        record = {"files_found": len(files), "scan_dir": scan_dir}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildFileGraph(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT file_id, file_name, path, imports FROM files")
        rows = cur.fetchall()
        name_to_id = {row[1]: row[0] for row in rows}
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
                base = imp.split(".")[0]
                candidate = base + ".py"
                target_id = name_to_id.get(candidate)
                if target_id is None:
                    for key, fid in name_to_id.items():
                        if key == base or key.startswith(base + "_"):
                            target_id = fid
                            break
                if target_id is not None and target_id != file_id:
                    self.AddEdge(cur, "file", file_id, "file", target_id,
                                 "imports", "import " + str(imp))
                    added += 1
        conn.commit()
        record = {"edge_type": "imports", "edges_added": added,
                  "files_processed": len(rows)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildFolderGraph(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT file_id, path FROM files")
        rows = cur.fetchall()
        folder_to_files = {}
        for row in rows:
            file_id, path = row
            folder = os.path.dirname(path)
            folder_to_files.setdefault(folder, []).append(file_id)
        added = 0
        for folder, file_ids in folder_to_files.items():
            parent = os.path.dirname(folder)
            if parent and parent in folder_to_files:
                for parent_fid in folder_to_files[parent]:
                    for child_fid in file_ids:
                        if parent_fid != child_fid:
                            self.AddEdge(cur, "folder", parent_fid, "folder",
                                         child_fid, "contains", folder)
                            added += 1
        conn.commit()
        record = {"edge_type": "folder_contains", "edges_added": added}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildImportGraph(self, params):
        return self.BuildFileGraph(params)

    def BuildDependencyGraph(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT file_id, dependencies FROM files WHERE dependencies IS NOT NULL")
        rows = cur.fetchall()
        name_to_id = {}
        cur.execute("SELECT file_id, file_name FROM files")
        for row in cur.fetchall():
            name_to_id[row[1]] = row[0]
        added = 0
        for row in rows:
            file_id, deps_json = row
            deps = []
            if deps_json:
                try:
                    deps = json.loads(deps_json)
                except (ValueError, TypeError):
                    deps = []
            for dep in deps:
                base = dep.split(".")[0] + ".py"
                target_id = name_to_id.get(base)
                if target_id is not None and target_id != file_id:
                    self.AddEdge(cur, "file", file_id, "file", target_id,
                                 "depends_on", dep)
                    added += 1
        conn.commit()
        record = {"edge_type": "depends_on", "edges_added": added}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildClassGraph(self, params):
        conn = self.Connect()[1]
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
        record = {"edge_type": "inherits/depends_on", "edges_added": added}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildMethodGraph(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_id, class_id, method_name, calls FROM methods")
        rows = cur.fetchall()
        name_to_ids = {}
        for row in rows:
            name_to_ids.setdefault(row[2], []).append(row[0])
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
        record = {"edge_type": "calls", "edges_added": added}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildFunctionGraph(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, calls FROM methods WHERE class_id IS NULL")
        rows = cur.fetchall()
        name_to_ids = {}
        for row in rows:
            name_to_ids.setdefault(row[1], []).append(row[0])
        added = 0
        for row in rows:
            method_id, method_name, calls_json = row
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
                        self.AddEdge(cur, "function", method_id, "function", tid,
                                     "calls", "call=" + str(call))
                        added += 1
        conn.commit()
        record = {"edge_type": "function_calls", "edges_added": added}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildCallGraph(self, params):
        return self.BuildMethodGraph(params)

    def BuildVariableGraph(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_code FROM methods WHERE method_code IS NOT NULL")
        rows = cur.fetchall()
        added = 0
        for row in rows:
            method_id, code = row
            try:
                tree = ast.parse(code)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    self.AddEdge(cur, "method", method_id, "variable", 0,
                                 "uses", "variable=" + node.id)
                    added += 1
        conn.commit()
        record = {"edge_type": "uses_variable", "edges_added": added}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildObjectGraph(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_code FROM methods WHERE method_code IS NOT NULL")
        rows = cur.fetchall()
        class_names = set()
        cur.execute("SELECT class_name FROM classes")
        for row in cur.fetchall():
            class_names.add(row[0])
        added = 0
        for row in rows:
            method_id, code = row
            try:
                tree = ast.parse(code)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in class_names:
                        self.AddEdge(cur, "method", method_id, "class", 0,
                                     "instantiates", "new=" + node.func.id)
                        added += 1
        conn.commit()
        record = {"edge_type": "instantiates", "edges_added": added}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildEventGraph(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name FROM methods")
        rows = cur.fetchall()
        added = 0
        event_prefixes = ("on_", "handle_", "process_", "dispatch_")
        for row in rows:
            method_id, method_name = row
            for prefix in event_prefixes:
                if method_name.startswith(prefix):
                    self.AddEdge(cur, "event", 0, "method", method_id,
                                 "triggers", "event_handler=" + method_name)
                    added += 1
                    break
        conn.commit()
        record = {"edge_type": "triggers", "edges_added": added}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildRuntimeFlow(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, calls FROM methods")
        rows = cur.fetchall()
        name_to_ids = {}
        for row in rows:
            name_to_ids.setdefault(row[1], []).append(row[0])
        added = 0
        for row in rows:
            method_id, method_name, calls_json = row
            calls = []
            if calls_json:
                try:
                    calls = json.loads(calls_json)
                except (ValueError, TypeError):
                    calls = []
            for call in calls:
                targets = name_to_ids.get(call, [])
                for tid in targets:
                    self.AddEdge(cur, "runtime", method_id, "runtime", tid,
                                 "flow", "runtime_call=" + str(call))
                    added += 1
        conn.commit()
        record = {"edge_type": "runtime_flow", "edges_added": added}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildExecutionFlow(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name FROM methods WHERE method_name IN ('Run','Main','Start','Boot','Init')")
        entry_points = cur.fetchall()
        cur.execute("SELECT method_id, calls FROM methods")
        all_methods = cur.fetchall()
        name_to_ids = {}
        cur.execute("SELECT method_id, method_name FROM methods")
        for row in cur.fetchall():
            name_to_ids.setdefault(row[1], []).append(row[0])
        added = 0
        for row in all_methods:
            method_id, calls_json = row
            calls = []
            if calls_json:
                try:
                    calls = json.loads(calls_json)
                except (ValueError, TypeError):
                    calls = []
            for call in calls:
                targets = name_to_ids.get(call, [])
                for tid in targets:
                    self.AddEdge(cur, "execution", method_id, "execution", tid,
                                 "flow", "exec_call=" + str(call))
                    added += 1
        conn.commit()
        record = {"edge_type": "execution_flow", "edges_added": added,
                  "entry_points": len(entry_points)}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildDatabaseFlow(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_code FROM methods WHERE method_code IS NOT NULL")
        rows = cur.fetchall()
        added = 0
        db_indicators = ("sqlite3", "connect", "execute", "cursor", "commit",
                         "query", "INSERT", "SELECT", "UPDATE", "DELETE")
        for row in rows:
            method_id, code = row
            for indicator in db_indicators:
                if indicator in code:
                    self.AddEdge(cur, "method", method_id, "database", 0,
                                 "db_access", indicator)
                    added += 1
                    break
        conn.commit()
        record = {"edge_type": "db_access", "edges_added": added}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildGuiFlow(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_code FROM methods WHERE method_code IS NOT NULL")
        rows = cur.fetchall()
        added = 0
        gui_indicators = ("tkinter", "Tk()", "QWidget", "QMainWindow", "QApplication",
                          "Frame", "Button", "Label", "Canvas", "pack(", "grid(",
                          "bind(", "configure(", "mainloop")
        for row in rows:
            method_id, code = row
            for indicator in gui_indicators:
                if indicator in code:
                    self.AddEdge(cur, "method", method_id, "gui", 0,
                                 "gui_access", indicator)
                    added += 1
                    break
        conn.commit()
        record = {"edge_type": "gui_access", "edges_added": added}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildThreadGraph(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_code FROM methods WHERE method_code IS NOT NULL")
        rows = cur.fetchall()
        added = 0
        thread_indicators = ("threading", "Thread(", "Lock(", "Queue(",
                             "asyncio", "await", "async def", "concurrent")
        for row in rows:
            method_id, code = row
            for indicator in thread_indicators:
                if indicator in code:
                    self.AddEdge(cur, "method", method_id, "thread", 0,
                                 "thread_access", indicator)
                    added += 1
                    break
        conn.commit()
        record = {"edge_type": "thread_access", "edges_added": added}
        self.state["catalog"].append(record)
        return (1, record, None)

    def BuildMemoryGraph(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_code FROM methods WHERE method_code IS NOT NULL")
        rows = cur.fetchall()
        added = 0
        mem_indicators = ("malloc", "alloc", "free(", "del ", "gc.collect",
                          "memcpy", "memset", "buffer", "bytearray")
        for row in rows:
            method_id, code = row
            for indicator in mem_indicators:
                if indicator in code:
                    self.AddEdge(cur, "method", method_id, "memory", 0,
                                 "memory_op", indicator)
                    added += 1
                    break
        conn.commit()
        record = {"edge_type": "memory_op", "edges_added": added}
        self.state["catalog"].append(record)
        return (1, record, None)

    def DetectCycles(self, params):
        conn = self.Connect()[1]
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
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_name FROM methods WHERE method_id NOT IN "
            "(SELECT dst_id FROM edges WHERE dst_type='method' AND edge_type='calls')"
        )
        dead = [{"method_id": r[0], "method_name": r[1]} for r in cur.fetchall()]
        record = {"dead_count": len(dead), "dead_methods": dead[:100]}
        self.state["results"] = record
        return (1, record, None)

    def DetectDuplicateCode(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT hash, COUNT(*) FROM methods WHERE hash IS NOT NULL "
            "GROUP BY hash HAVING COUNT(*) > 1"
        )
        dup_hashes = cur.fetchall()
        duplicates = []
        for dhash, count in dup_hashes:
            cur.execute(
                "SELECT method_id, method_name FROM methods WHERE hash=?",
                (dhash,),
            )
            members = [{"method_id": r[0], "method_name": r[1]}
                        for r in cur.fetchall()]
            duplicates.append({"hash": dhash, "count": count, "members": members})
        record = {"duplicate_hashes": len(duplicates),
                  "duplicates": duplicates[:50]}
        self.state["results"] = record
        return (1, record, None)

    def DetectOrphans(self, params):
        conn = self.Connect()[1]
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
        conn = self.Connect()[1]
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

    def StoreGraph(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM edges")
        edge_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT edge_type) FROM edges")
        type_count = cur.fetchone()[0]
        record = {"total_edges": edge_count, "edge_types": type_count,
                  "stored": True, "timestamp": self.Now()[1]}
        self.state["results"] = record
        return (1, record, None)

    def BuildAll(self, params):
        results = {}
        steps = [
            "build_file_graph", "build_folder_graph", "build_import_graph",
            "build_dependency_graph", "build_class_graph", "build_method_graph",
            "build_function_graph", "build_call_graph", "build_variable_graph",
            "build_object_graph", "build_event_graph", "build_runtime_flow",
            "build_execution_flow", "build_database_flow", "build_gui_flow",
            "build_thread_graph", "build_memory_graph",
        ]
        for step in steps:
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        for step in ("detect_cycles", "detect_dead_code", "detect_duplicate_code",
                     "detect_orphans", "detect_hotspots"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        res = self.Run("store_graph", params)
        results["store_graph"] = res[1] if res[0] == 1 else {"error": str(res[2])}
        return (1, results, None)
