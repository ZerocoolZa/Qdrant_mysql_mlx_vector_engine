#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/call_path_engine.py"
# date="2026-06-26" author="Devin" session_id="phase4-analysis"
# context="Project Digital Twin Phase 4 Section 42 Call Path Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="call_path_engine.py" domain="twin_callpath" authority="CallPathEngine"}
# [@SUMMARY]{summary="Call path authority that traces incoming/outgoing calls, recursion, async calls, execution paths and call chains via the edges graph."}
# [@CLASS]{class="CallPathEngine" domain="callpath" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="incoming" type="command"}
# [@METHOD]{method="outgoing" type="command"}
# [@METHOD]{method="recursive" type="command"}
# [@METHOD]{method="async_calls" type="command"}
# [@METHOD]{method="execution_paths" type="command"}
# [@METHOD]{method="call_chain" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<CallPathEngine: traces incoming/outgoing calls, recursion, async calls, execution paths, call chains. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
CallPathEngine -- authority for call graph traversal and path analysis.
Implements Section 42 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: incoming, outgoing, recursive, async_calls, execution_paths, call_chain.
"""
import ast
import os
import re
import sqlite3

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
MAX_PATH_DEPTH = 25
ASYNC_PATTERN = re.compile(r"\basync\s+def\b|\bawait\b")
ASYNC_KEYWORDS = ("create_task", "gather", "wait", "ensure_future", "run_in_executor", "sleep")


class CallPathEngine:
    """Authority for call graph traversal, recursion and path enumeration."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
                "max_path_depth": MAX_PATH_DEPTH,
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
        if command == "incoming":
            return self.Incoming(params)
        elif command == "outgoing":
            return self.Outgoing(params)
        elif command == "recursive":
            return self.Recursive(params)
        elif command == "async_calls":
            return self.AsyncCalls(params)
        elif command == "execution_paths":
            return self.ExecutionPaths(params)
        elif command == "call_chain":
            return self.CallChain(params)
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

    def Incoming(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type, "
            "evidence, confidence FROM edges WHERE dst_type='method' AND "
            "dst_id=? AND edge_type='calls' ORDER BY edge_id LIMIT ?",
            (method_id, limit),
        )
        edges = []
        for row in cur.fetchall():
            edges.append(
                {
                    "edge_id": row[0],
                    "src_type": row[1],
                    "src_id": row[2],
                    "dst_type": row[3],
                    "dst_id": row[4],
                    "edge_type": row[5],
                    "evidence": row[6],
                    "confidence": row[7],
                }
            )
        report = {"method_id": method_id, "incoming_count": len(edges), "edges": edges}
        return (1, report, None)

    def Outgoing(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type, "
            "evidence, confidence FROM edges WHERE src_type='method' AND "
            "src_id=? AND edge_type='calls' ORDER BY edge_id LIMIT ?",
            (method_id, limit),
        )
        edges = []
        for row in cur.fetchall():
            edges.append(
                {
                    "edge_id": row[0],
                    "src_type": row[1],
                    "src_id": row[2],
                    "dst_type": row[3],
                    "dst_id": row[4],
                    "edge_type": row[5],
                    "evidence": row[6],
                    "confidence": row[7],
                }
            )
        report = {"method_id": method_id, "outgoing_count": len(edges), "edges": edges}
        return (1, report, None)

    def Recursive(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT edge_id, src_id, dst_id, edge_type, evidence, confidence "
            "FROM edges WHERE src_type='method' AND dst_type='method' AND "
            "edge_type='calls' AND src_id=dst_id ORDER BY edge_id LIMIT ?",
            (limit,),
        )
        recursive = []
        for row in cur.fetchall():
            recursive.append(
                {
                    "edge_id": row[0],
                    "method_id": row[1],
                    "edge_type": row[3],
                    "evidence": row[4],
                    "confidence": row[5],
                }
            )
        report = {"recursive_count": len(recursive), "recursive": recursive}
        self.state["results"].append(report)
        return (1, report, None)

    def SafeParse(self, code):
        if not code:
            return None
        try:
            return ast.parse(code)
        except SyntaxError:
            return None

    def AsyncCalls(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, class_id, method_name, method_code FROM methods "
            "WHERE method_code IS NOT NULL AND method_code != '' LIMIT ?",
            (limit * 4,),
        )
        async_methods = []
        for method_id, class_id, method_name, code in cur.fetchall():
            if not code:
                continue
            tree = self.SafeParse(code)
            has_async_def = False
            has_await = False
            asyncio_calls = []
            if tree is not None:
                for node in ast.walk(tree):
                    if isinstance(node, ast.AsyncFunctionDef):
                        has_async_def = True
                    if isinstance(node, ast.Await):
                        has_await = True
                    if isinstance(node, ast.Call):
                        func = node.func
                        if isinstance(func, ast.Attribute):
                            if func.attr in ASYNC_KEYWORDS:
                                if isinstance(func.value, ast.Name) and func.value.id == "asyncio":
                                    asyncio_calls.append({
                                        "call": "asyncio." + func.attr,
                                        "line": getattr(node, "lineno", 0),
                                    })
                                elif isinstance(func.value, ast.Attribute) and isinstance(func.value.value, ast.Name) and func.value.value.id == "asyncio":
                                    asyncio_calls.append({
                                        "call": "asyncio." + func.value.attr + "." + func.attr,
                                        "line": getattr(node, "lineno", 0),
                                    })
            else:
                matches = ASYNC_PATTERN.findall(code)
                if not matches:
                    continue
                has_async_def = "async def" in code
                has_await = "await" in code
                for kw in ASYNC_KEYWORDS:
                    if "asyncio." + kw in code or "asyncio.gather" in code:
                        asyncio_calls.append({"call": "asyncio." + kw, "line": 0})
            if has_async_def or has_await or asyncio_calls:
                async_methods.append({
                    "method_id": method_id,
                    "class_id": class_id,
                    "method_name": method_name,
                    "has_async_def": has_async_def,
                    "has_await": has_await,
                    "asyncio_calls": asyncio_calls,
                    "asyncio_call_count": len(asyncio_calls),
                })
                if len(async_methods) >= limit:
                    break
        report = {
            "async_count": len(async_methods),
            "async_methods": async_methods,
        }
        self.state["results"].append(report)
        return (1, report, None)

    def ExecutionPaths(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        max_depth = self._p(
            params, "max_depth", self.state["config"]["max_path_depth"]
        )
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT src_id, dst_id FROM edges WHERE src_type='method' AND "
            "dst_type='method' AND edge_type='calls'"
        )
        graph = {}
        all_dst = set()
        all_src = set()
        for src_id, dst_id in cur.fetchall():
            graph.setdefault(src_id, []).append(dst_id)
            all_src.add(src_id)
            all_dst.add(dst_id)
        entry_points = list(all_src - all_dst)
        if not entry_points:
            entry_points = list(all_src)
        leaf_methods = list(all_dst - all_src)
        cur.execute("SELECT method_id, method_name FROM methods")
        method_names = {r[0]: r[1] for r in cur.fetchall()}
        paths = []
        for entry in entry_points:
            self.DfsPathsToLeaves(entry, graph, [], paths, max_depth, set(), leaf_methods, method_names)
            if len(paths) >= limit:
                break
        paths = paths[:limit]
        report = {
            "entry_point_count": len(entry_points),
            "entry_points": [{"method_id": ep, "method_name": method_names.get(ep, "unknown")} for ep in entry_points],
            "leaf_method_count": len(leaf_methods),
            "leaf_methods": [{"method_id": lm, "method_name": method_names.get(lm, "unknown")} for lm in leaf_methods],
            "path_count": len(paths),
            "paths": paths,
        }
        self.state["results"].append(report)
        return (1, report, None)

    def DfsPathsToLeaves(self, node, graph, current, paths, max_depth, visited, leaf_methods, method_names):
        if len(current) >= max_depth:
            full_path = current + [node]
            paths.append([{"method_id": m, "method_name": method_names.get(m, "unknown")} for m in full_path])
            return
        if node in visited:
            full_path = current + [node]
            paths.append([{"method_id": m, "method_name": method_names.get(m, "unknown")} for m in full_path])
            return
        new_path = current + [node]
        neighbors = graph.get(node, [])
        if not neighbors or node in leaf_methods:
            paths.append([{"method_id": m, "method_name": method_names.get(m, "unknown")} for m in new_path])
            return
        new_visited = set(visited)
        new_visited.add(node)
        for neighbor in neighbors:
            self.DfsPathsToLeaves(neighbor, graph, new_path, paths, max_depth, new_visited, leaf_methods, method_names)

    def DfsPaths(self, node, graph, current, paths, max_depth, visited):
        if len(current) >= max_depth:
            paths.append(list(current) + [node])
            return
        if node in visited:
            paths.append(list(current) + [node])
            return
        new_path = current + [node]
        neighbors = graph.get(node, [])
        if not neighbors:
            paths.append(new_path)
            return
        new_visited = set(visited)
        new_visited.add(node)
        for neighbor in neighbors:
            self.DfsPaths(neighbor, graph, new_path, paths, max_depth, new_visited)

    def CallChain(self, params):
        from_id = self._p(params, "from_method_id")
        to_id = self._p(params, "to_method_id")
        if from_id is None:
            return (0, None, ("MISSING_PARAM", "from_method_id required", 0))
        if to_id is None:
            return (0, None, ("MISSING_PARAM", "to_method_id required", 0))
        max_depth = self._p(
            params, "max_depth", self.state["config"]["max_path_depth"]
        )
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT src_id, dst_id FROM edges WHERE src_type='method' AND "
            "dst_type='method' AND edge_type='calls'"
        )
        graph = {}
        for src_id, dst_id in cur.fetchall():
            graph.setdefault(src_id, []).append(dst_id)
        queue = [(from_id, [from_id])]
        visited = {from_id}
        found_path = None
        while queue:
            node, path = queue.pop(0)
            if node == to_id:
                found_path = path
                break
            if len(path) >= max_depth:
                continue
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        if found_path is None:
            report = {
                "from_method_id": from_id,
                "to_method_id": to_id,
                "found": False,
                "path": None,
                "length": 0,
            }
            return (1, report, None)
        report = {
            "from_method_id": from_id,
            "to_method_id": to_id,
            "found": True,
            "path": found_path,
            "length": len(found_path),
        }
        self.state["results"].append(report)
        return (1, report, None)
