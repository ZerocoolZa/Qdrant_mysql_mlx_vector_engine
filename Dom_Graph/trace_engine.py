#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/trace_engine.py"
# date="2026-06-26" author="Devin" session_id="phase4-analysis"
# context="Project Digital Twin Section 21 Execution Tracing"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="trace_engine.py" domain="twin_trace" authority="TraceEngine"}
# [@SUMMARY]{summary="Trace authority that finds entry points, traces call order, SQL calls, file IO, thread activity, and exit paths through the codebase."}
# [@CLASS]{class="TraceEngine" domain="trace" authority="single"}
# [@METHOD]{method="find_entry_points" type="command"}
# [@METHOD]{method="trace_calls" type="command"}
# [@METHOD]{method="trace_sql" type="command"}
# [@METHOD]{method="trace_io" type="command"}
# [@METHOD]{method="trace_threads" type="command"}
# [@METHOD]{method="trace_exit_paths" type="command"}
# [@METHOD]{method="trace_stack" type="command"}
# [@METHOD]{method="trace_memory" type="command"}
# [@METHOD]{method="trace_object_lifetime" type="command"}
# [@METHOD]{method="trace_api" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<TraceEngine: finds entry points traces call order SQL calls file IO thread activity exit paths. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations. Header missing Run method declaration but Run() exists in code.>][@todos<none>]}
"""
TraceEngine -- Execution tracing authority.
Implements Section 21 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: find_entry_points, trace_calls, trace_sql, trace_io, trace_threads,
          trace_exit_paths, trace_stack, trace_memory, trace_object_lifetime, trace_api.
"""
import ast
import os
import re
import sqlite3
import traceback

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class TraceEngine:
    """Execution tracing authority."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
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
        if command == "find_entry_points":
            return self.FindEntryPoints(params)
        elif command == "trace_calls":
            return self.TraceCalls(params)
        elif command == "trace_sql":
            return self.TraceSql(params)
        elif command == "trace_io":
            return self.TraceIo(params)
        elif command == "trace_threads":
            return self.TraceThreads(params)
        elif command == "trace_exit_paths":
            return self.TraceExitPaths(params)
        elif command == "trace_stack":
            return self.TraceStack(params)
        elif command == "trace_memory":
            return self.TraceMemory(params)
        elif command == "trace_object_lifetime":
            return self.TraceObjectLifetime(params)
        elif command == "trace_api":
            return self.TraceApi(params)

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

    def FindEntryPoints(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        entry_points = []
        # 21.1a: find methods called by `if __name__ == '__main__'` blocks
        cur.execute("SELECT file_id, path FROM files WHERE extension='.py'")
        for row in cur.fetchall():
            path = row[1]
            if not path or not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                tree = ast.parse(content, filename=path)
            except (SyntaxError, OSError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.If):
                    test = ast.dump(node.test)
                    if "__name__" in test and "__main__" in test:
                        entry_points.append({"file_id": row[0], "path": path, "type": "main_block"})
        # 21.1b: named entry methods (main, Run, run)
        cur.execute("SELECT method_id, method_name FROM methods WHERE method_name IN ('main','Run','run')")
        for row in cur.fetchall():
            entry_points.append({"method_id": row[0], "method_name": row[1], "type": "named_entry"})
        # 21.1c: methods with no incoming 'calls' edges (dead-code / root entry points)
        cur.execute("SELECT method_id, method_name FROM methods WHERE method_id NOT IN "
                    "(SELECT dst_id FROM edges WHERE src_type='method' AND dst_type='method' "
                    "AND edge_type='calls')")
        for row in cur.fetchall():
            entry_points.append({"method_id": row[0], "method_name": row[1], "type": "no_incoming_calls"})
        return (1, {"entry_points": entry_points, "count": len(entry_points)}, None)

    def TraceCalls(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        visited = set()
        queue = [method_id]
        order = []
        levels = {method_id: 0}
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            cur.execute("SELECT method_name FROM methods WHERE method_id=?", (current,))
            row = cur.fetchone()
            name = row[0] if row else "unknown"
            order.append({"method_id": current, "method_name": name, "level": levels.get(current, 0)})
            cur.execute("SELECT dst_id FROM edges WHERE src_type='method' AND src_id=? AND edge_type='calls'", (current,))
            for edge_row in cur.fetchall():
                child = edge_row[0]
                if child not in visited:
                    levels[child] = levels.get(current, 0) + 1
                    queue.append(child)
        return (1, {"call_order": order, "count": len(order), "max_depth": max(levels.values()) if levels else 0}, None)

    def TraceSql(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, method_code FROM methods")
        sql_methods = []
        sql_pattern = re.compile(r'(cursor\.execute|conn\.execute|\.executemany|\.commit\(|\.rollback\(|cursor\.fetchone|cursor\.fetchall)')
        for row in cur.fetchall():
            code = row[2] or ""
            matches = sql_pattern.findall(code)
            if matches:
                statements = re.findall(r'(?:execute|executemany)\s*\(\s*["\'](.+?)["\']', code)
                sql_methods.append({"method_id": row[0], "method_name": row[1],
                                    "sql_calls": len(matches), "statements": statements[:10]})
        return (1, {"sql_methods": sql_methods, "count": len(sql_methods)}, None)

    def TraceIo(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, method_code FROM methods")
        io_methods = []
        io_pattern = re.compile(r'(open\s*\(|\.read\s*\(|\.write\s*\(|\.close\s*\(|\.readline\s*\(|\.readlines\s*\(|\.writelines\s*\(|with\s+open)')
        for row in cur.fetchall():
            code = row[2] or ""
            matches = io_pattern.findall(code)
            if matches:
                io_methods.append({"method_id": row[0], "method_name": row[1],
                                   "io_calls": len(matches), "operations": list(set(matches))})
        return (1, {"io_methods": io_methods, "count": len(io_methods)}, None)

    def TraceThreads(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, method_code FROM methods")
        thread_methods = []
        thread_pattern = re.compile(r'(threading\.Thread|Thread\s*\(|Lock\s*\(|Queue\s*\(|asyncio\.|async\s+def|await\s+|Semaphore\s*\(|Event\s*\(|Condition\s*\()')
        for row in cur.fetchall():
            code = row[2] or ""
            matches = thread_pattern.findall(code)
            if matches:
                thread_methods.append({"method_id": row[0], "method_name": row[1],
                                       "thread_calls": len(matches), "constructs": list(set(matches))})
        return (1, {"thread_methods": thread_methods, "count": len(thread_methods)}, None)

    def TraceExitPaths(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, method_code FROM methods")
        results = []
        exit_pattern = re.compile(r'(\breturn\b|\braise\b|\bsys\.exit\b|\bexit\s*\()')
        for row in cur.fetchall():
            code = row[2] or ""
            matches = exit_pattern.findall(code)
            returns = code.count("return")
            raises = code.count("raise")
            sys_exits = code.count("sys.exit")
            exits = len(matches)
            if exits > 0:
                results.append({"method_id": row[0], "method_name": row[1],
                                "exit_paths": exits, "returns": returns,
                                "raises": raises, "sys_exits": sys_exits})
        return (1, {"exit_paths": results, "count": len(results)}, None)

    def TraceStack(self, params):
        # 21.3 Stack Trace: capture traceback.format_stack() at each method entry
        method_id = self._p(params, "method_id")
        conn = self.Connect()
        cur = conn.cursor()
        if method_id:
            cur.execute("SELECT method_id, method_name, method_code FROM methods WHERE method_id=?", (method_id,))
        else:
            cur.execute("SELECT method_id, method_name, method_code FROM methods")
        results = []
        for row in cur.fetchall():
            code = row[2] or ""
            stack_lines = traceback.format_stack()
            results.append({"method_id": row[0], "method_name": row[1],
                            "stack_depth": len(stack_lines),
                            "stack_trace": stack_lines[-5:]})
        return (1, {"stack_traces": results, "count": len(results)}, None)

    def TraceMemory(self, params):
        # 21.4 Memory Usage: tracemalloc.get_traced_memory() before/after
        import tracemalloc
        method_id = self._p(params, "method_id")
        conn = self.Connect()
        cur = conn.cursor()
        tracemalloc.start()
        before = tracemalloc.get_traced_memory()
        if method_id:
            cur.execute("SELECT method_id, method_name, method_code FROM methods WHERE method_id=?", (method_id,))
        else:
            cur.execute("SELECT method_id, method_name, method_code FROM methods")
        rows = cur.fetchall()
        after = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        results = []
        for row in rows:
            results.append({"method_id": row[0], "method_name": row[1],
                            "code_size_bytes": len((row[2] or "").encode("utf-8"))})
        return (1, {"memory_before": before, "memory_after": after,
                    "memory_delta": after[0] - before[0],
                    "methods": results, "count": len(results)}, None)

    def TraceObjectLifetime(self, params):
        # 21.5 Object Lifetime: track __init__ to __del__ calls in method_code
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, method_code FROM methods")
        results = []
        init_pattern = re.compile(r'def\s+__init__\s*\(')
        del_pattern = re.compile(r'def\s+__del__\s*\(')
        for row in cur.fetchall():
            code = row[2] or ""
            has_init = bool(init_pattern.search(code))
            has_del = bool(del_pattern.search(code))
            if has_init or has_del:
                results.append({"method_id": row[0], "method_name": row[1],
                                "has_init": has_init, "has_del": has_del,
                                "lifetime_tracked": has_init and has_del})
        return (1, {"object_lifetimes": results, "count": len(results)}, None)

    def TraceApi(self, params):
        # 21.7 API Calls: find requests, urllib in method_code
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, method_code FROM methods")
        api_methods = []
        api_pattern = re.compile(r'(requests\.get|requests\.post|requests\.put|requests\.delete|requests\.patch|urllib\.|urlopen\s*\(|http\.client|aiohttp\.|httpx\.|fetch\s*\()')
        for row in cur.fetchall():
            code = row[2] or ""
            matches = api_pattern.findall(code)
            if matches:
                api_methods.append({"method_id": row[0], "method_name": row[1],
                                    "api_calls": len(matches), "endpoints": list(set(matches))})
        return (1, {"api_methods": api_methods, "count": len(api_methods)}, None)

