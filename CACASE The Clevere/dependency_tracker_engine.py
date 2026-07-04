#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/dependency_tracker_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 27: Dependency Tracker -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="dependency_tracker_engine.py" domain="twin_dependency" authority="DependencyTrackerEngine"}
# [@SUMMARY]{summary="Dependency tracker authority: trace imports, trace calls, trace class hierarchy, trace file deps, trace module deps, detect circular deps, detect unused deps, detect missing deps, rank dependencies, visualize deps."}
# [@CLASS]{class="DependencyTrackerEngine" domain="dependency_tracker" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="trace_imports" type="command"}
# [@METHOD]{method="trace_calls" type="command"}
# [@METHOD]{method="trace_class_hierarchy" type="command"}
# [@METHOD]{method="trace_file_deps" type="command"}
# [@METHOD]{method="trace_module_deps" type="command"}
# [@METHOD]{method="detect_circular_deps" type="command"}
# [@METHOD]{method="detect_unused_deps" type="command"}
# [@METHOD]{method="detect_missing_deps" type="command"}
# [@METHOD]{method="rank_dependencies" type="command"}
# [@METHOD]{method="visualize_deps" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class DependencyTrackerEngine:
    """Authority for tracing and analyzing dependencies."""

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
        if command == "trace_imports":
            return self.TraceImports(params)
        elif command == "trace_calls":
            return self.TraceCalls(params)
        elif command == "trace_class_hierarchy":
            return self.TraceClassHierarchy(params)
        elif command == "trace_file_deps":
            return self.TraceFileDeps(params)
        elif command == "trace_module_deps":
            return self.TraceModuleDeps(params)
        elif command == "detect_circular_deps":
            return self.DetectCircularDeps(params)
        elif command == "detect_unused_deps":
            return self.DetectUnusedDeps(params)
        elif command == "detect_missing_deps":
            return self.DetectMissingDeps(params)
        elif command == "rank_dependencies":
            return self.RankDependencies(params)
        elif command == "visualize_deps":
            return self.VisualizeDeps(params)
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

    def TraceImports(self, params):
        file_id = self._p(params, "file_id")
        conn = self.Connect()[1]
        cur = conn.cursor()
        if file_id:
            cur.execute("SELECT imports FROM files WHERE file_id=?", (file_id,))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("FILE_NOT_FOUND", str(file_id), 0))
            imports = json.loads(row[0]) if row[0] else []
            return (1, {"file_id": file_id, "imports": imports,
                        "count": len(imports)}, None)
        cur.execute("SELECT file_name, imports FROM files WHERE imports IS NOT NULL AND imports != '[]'")
        all_imports = {}
        for row in cur.fetchall():
            imps = json.loads(row[1]) if row[1] else []
            all_imports[row[0]] = imps
        return (1, {"all_imports": all_imports,
                    "total_files": len(all_imports)}, None)

    def TraceCalls(self, params):
        method_id = self._p(params, "method_id")
        conn = self.Connect()[1]
        cur = conn.cursor()
        if method_id:
            cur.execute("SELECT calls FROM methods WHERE method_id=?", (method_id,))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
            calls = json.loads(row[0]) if row[0] else []
            return (1, {"method_id": method_id, "calls": calls,
                        "count": len(calls)}, None)
        cur.execute("SELECT method_name, calls FROM methods WHERE calls IS NOT NULL AND calls != '[]'")
        all_calls = {}
        for row in cur.fetchall():
            cls = json.loads(row[1]) if row[1] else []
            all_calls[row[0]] = cls
        return (1, {"all_calls": all_calls,
                    "total_methods": len(all_calls)}, None)

    def TraceClassHierarchy(self, params):
        class_id = self._p(params, "class_id")
        conn = self.Connect()[1]
        cur = conn.cursor()
        if class_id:
            cur.execute("SELECT class_name, parent FROM classes WHERE class_id=?", (class_id,))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("CLASS_NOT_FOUND", str(class_id), 0))
            hierarchy = [row[0]]
            parent = row[1]
            while parent:
                cur.execute("SELECT class_name, parent FROM classes WHERE class_name=?", (parent,))
                prow = cur.fetchone()
                if prow is None:
                    hierarchy.append(parent)
                    break
                hierarchy.append(prow[0])
                parent = prow[1]
            return (1, {"class_id": class_id, "hierarchy": hierarchy}, None)
        cur.execute("SELECT class_name, parent FROM classes WHERE parent IS NOT NULL")
        hierarchy = {r[0]: r[1] for r in cur.fetchall()}
        return (1, {"class_hierarchy": hierarchy,
                    "total": len(hierarchy)}, None)

    def TraceFileDeps(self, params):
        file_id = self._p(params, "file_id")
        conn = self.Connect()[1]
        cur = conn.cursor()
        if file_id:
            cur.execute(
                "SELECT dst_id, edge_type, evidence FROM edges WHERE src_type='file' AND src_id=?",
                (file_id,),
            )
            deps = [{"dst_id": r[0], "type": r[1], "evidence": r[2]} for r in cur.fetchall()]
            return (1, {"file_id": file_id, "dependencies": deps,
                        "count": len(deps)}, None)
        cur.execute(
            "SELECT src_id, dst_id, edge_type FROM edges WHERE src_type='file' AND dst_type='file'"
        )
        all_deps = [{"src": r[0], "dst": r[1], "type": r[2]} for r in cur.fetchall()]
        return (1, {"file_dependencies": all_deps,
                    "count": len(all_deps)}, None)

    def TraceModuleDeps(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT edge_type, COUNT(*) FROM edges WHERE src_type IN ('file','class','method') "
            "GROUP BY edge_type ORDER BY COUNT(*) DESC"
        )
        deps = {r[0]: r[1] for r in cur.fetchall()}
        return (1, {"module_dependencies": deps}, None)

    def DetectCircularDeps(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT src_id, dst_id FROM edges WHERE src_type=dst_type")
        graph = {}
        for row in cur.fetchall():
            graph.setdefault(row[0], []).append(row[1])
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
        return (1, {"circular_deps": cycles[:50],
                    "count": len(cycles)}, None)

    def DetectUnusedDeps(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT file_id, imports FROM files WHERE imports IS NOT NULL AND imports != '[]'"
        )
        unused = []
        for row in cur.fetchall():
            file_id = row[0]
            imports = json.loads(row[1]) if row[1] else []
            for imp in imports:
                cur.execute(
                    "SELECT COUNT(*) FROM edges WHERE src_type='file' AND src_id=? "
                    "AND evidence LIKE ?",
                    (file_id, "%" + imp + "%"),
                )
                count = cur.fetchone()[0]
                if count == 0:
                    unused.append({"file_id": file_id, "import": imp})
        return (1, {"unused_deps": unused[:100],
                    "count": len(unused)}, None)

    def DetectMissingDeps(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, calls FROM methods WHERE calls IS NOT NULL AND calls != '[]'"
        )
        missing = []
        for row in cur.fetchall():
            method_id = row[0]
            calls = json.loads(row[1]) if row[1] else []
            for call in calls:
                cur.execute("SELECT COUNT(*) FROM methods WHERE method_name=?", (call,))
                count = cur.fetchone()[0]
                if count == 0:
                    missing.append({"method_id": method_id, "call": call})
        return (1, {"missing_deps": missing[:100],
                    "count": len(missing)}, None)

    def RankDependencies(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT dst_type, dst_id, COUNT(*) AS incoming FROM edges "
            "GROUP BY dst_type, dst_id ORDER BY incoming DESC LIMIT 50"
        )
        ranked = [{"type": r[0], "id": r[1], "incoming": r[2]}
                  for r in cur.fetchall()]
        return (1, {"ranked": ranked, "count": len(ranked)}, None)

    def VisualizeDeps(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT src_type, src_id, dst_type, dst_id, edge_type FROM edges LIMIT 200")
        nodes = set()
        edges = []
        for row in cur.fetchall():
            src = str(row[0]) + ":" + str(row[1])
            dst = str(row[2]) + ":" + str(row[3])
            nodes.add(src)
            nodes.add(dst)
            edges.append({"source": src, "target": dst, "type": row[4]})
        return (1, {"nodes": list(nodes), "edges": edges,
                    "node_count": len(nodes), "edge_count": len(edges)}, None)
