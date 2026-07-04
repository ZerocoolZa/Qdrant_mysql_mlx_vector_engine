#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/control_flow_engine.py"
# date="2026-06-26" author="Devin" session_id="phase4-analysis"
# context="Project Digital Twin Phase 4 Section 44 Control Flow Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="control_flow_engine.py" domain="twin_controlflow" authority="ControlFlowEngine"}
# [@SUMMARY]{summary="Control flow authority that analyzes branches, loops, unreachable code, infinite loops and exit paths via AST traversal of method bodies."}
# [@CLASS]{class="ControlFlowEngine" domain="controlflow" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="analyze_branches" type="command"}
# [@METHOD]{method="analyze_loops" type="command"}
# [@METHOD]{method="find_unreachable" type="command"}
# [@METHOD]{method="find_infinite_loops" type="command"}
# [@METHOD]{method="exit_paths" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<ControlFlowEngine: analyzes branches, loops, unreachable code, infinite loops, exit paths via AST. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
ControlFlowEngine -- authority for control flow analysis of method bodies.
Implements Section 44 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: analyze_branches, analyze_loops, find_unreachable,
          find_infinite_loops, exit_paths.
"""
import ast
import os
import re
import sqlite3

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
WHILE_TRUE_PATTERN = re.compile(r"\bwhile\s+(True|1)\b")
BREAK_PATTERN = re.compile(r"\bbreak\b")


class ControlFlowEngine:
    """Authority for branch, loop, unreachable and exit path analysis."""

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
        if command == "analyze_branches":
            return self.AnalyzeBranches(params)
        elif command == "analyze_loops":
            return self.AnalyzeLoops(params)
        elif command == "find_unreachable":
            return self.FindUnreachable(params)
        elif command == "find_infinite_loops":
            return self.FindInfiniteLoops(params)
        elif command == "exit_paths":
            return self.ExitPaths(params)
        elif command == "exception_flow_analysis":
            return self.ExceptionFlowAnalysis(params)
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

    def SafeParse(self, code):
        if not code:
            return None
        try:
            return ast.parse(code)
        except SyntaxError:
            return None

    def GetMethodCode(self, method_id):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, class_id, method_name, method_code, start_line "
            "FROM methods WHERE method_id=?",
            (method_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "method_id": row[0],
            "class_id": row[1],
            "method_name": row[2],
            "method_code": row[3],
            "start_line": row[4],
        }

    def AnalyzeBranches(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        method = self.GetMethodCode(method_id)
        if method is None:
            return (0, None, ("NOT_FOUND", "method_id not found", 0))
        code = method.get("method_code", "") or ""
        tree = self.SafeParse(code)
        branches = []
        total = 0
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.If):
                    line = getattr(node, "lineno", 0)
                    has_else = len(node.orelse) > 0
                    elif_count = sum(
                        1 for n in ast.walk(node) if isinstance(n, ast.If) and n is not node
                    )
                    branches.append(
                        {
                            "line": line,
                            "type": "if",
                            "has_else": has_else,
                            "elif_count": elif_count,
                        }
                    )
                    total += 1
        else:
            for idx, line in enumerate(code.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("if ") or stripped.startswith("elif "):
                    btype = "elif" if stripped.startswith("elif") else "if"
                    branches.append({"line": idx, "type": btype, "has_else": False, "elif_count": 0})
                    total += 1
                elif stripped.startswith("else"):
                    branches.append({"line": idx, "type": "else", "has_else": False, "elif_count": 0})
                    total += 1
        report = {
            "method_id": method_id,
            "method_name": method.get("method_name"),
            "branch_count": total,
            "branches": branches,
        }
        self.state["results"].append(report)
        return (1, report, None)

    def AnalyzeLoops(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        method = self.GetMethodCode(method_id)
        if method is None:
            return (0, None, ("NOT_FOUND", "method_id not found", 0))
        code = method.get("method_code", "") or ""
        tree = self.SafeParse(code)
        loops = []
        total = 0
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, (ast.For, ast.While)):
                    line = getattr(node, "lineno", 0)
                    ltype = "for" if isinstance(node, ast.For) else "while"
                    has_break = any(
                        isinstance(n, ast.Break) for n in ast.walk(node)
                    )
                    has_continue = any(
                        isinstance(n, ast.Continue) for n in ast.walk(node)
                    )
                    loops.append(
                        {
                            "line": line,
                            "type": ltype,
                            "has_break": has_break,
                            "has_continue": has_continue,
                        }
                    )
                    total += 1
        else:
            for idx, line in enumerate(code.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("for ") or stripped.startswith("while "):
                    ltype = "for" if stripped.startswith("for") else "while"
                    loops.append(
                        {"line": idx, "type": ltype, "has_break": False, "has_continue": False}
                    )
                    total += 1
        report = {
            "method_id": method_id,
            "method_name": method.get("method_name"),
            "loop_count": total,
            "loops": loops,
        }
        self.state["results"].append(report)
        return (1, report, None)

    def FindUnreachable(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        method = self.GetMethodCode(method_id)
        if method is None:
            return (0, None, ("NOT_FOUND", "method_id not found", 0))
        code = method.get("method_code", "") or ""
        tree = self.SafeParse(code)
        unreachable = []
        if tree is not None:
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.FunctionDef):
                    unreachable.extend(self.FindUnreachableInBody(node.body))
                else:
                    unreachable.extend(self.FindUnreachableInBody([node]))
        else:
            lines = code.splitlines()
            terminated = False
            term_line = 0
            for idx, line in enumerate(lines, 1):
                stripped = line.strip()
                if terminated:
                    if stripped and not stripped.startswith("#"):
                        unreachable.append(
                            {"start_line": idx, "end_line": idx, "reason": "after_termination"}
                        )
                if stripped.startswith("return ") or stripped == "return":
                    terminated = True
                    term_line = idx
                elif stripped.startswith("raise "):
                    terminated = True
                    term_line = idx
        report = {
            "method_id": method_id,
            "method_name": method.get("method_name"),
            "unreachable_count": len(unreachable),
            "unreachable": unreachable,
        }
        self.state["results"].append(report)
        return (1, report, None)

    def FindUnreachableInBody(self, body):
        results = []
        for idx, stmt in enumerate(body):
            if isinstance(stmt, (ast.Return, ast.Raise)):
                if idx + 1 < len(body):
                    next_stmt = body[idx + 1]
                    start = getattr(next_stmt, "lineno", 0)
                    end = getattr(next_stmt, "end_lineno", start)
                    results.append(
                        {
                            "start_line": start,
                            "end_line": end,
                            "reason": "after_" + type(stmt).__name__.lower(),
                        }
                    )
            if isinstance(stmt, ast.If):
                results.extend(self.FindUnreachableInBody(stmt.body))
                results.extend(self.FindUnreachableInBody(stmt.orelse))
            elif isinstance(stmt, (ast.For, ast.While)):
                results.extend(self.FindUnreachableInBody(stmt.body))
                results.extend(self.FindUnreachableInBody(stmt.orelse))
            elif isinstance(stmt, ast.Try):
                results.extend(self.FindUnreachableInBody(stmt.body))
                for handler in stmt.handlers:
                    results.extend(self.FindUnreachableInBody(handler.body))
                results.extend(self.FindUnreachableInBody(stmt.orelse))
                results.extend(self.FindUnreachableInBody(stmt.finalbody))
            elif isinstance(stmt, ast.With):
                results.extend(self.FindUnreachableInBody(stmt.body))
        return results

    def FindInfiniteLoops(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, class_id, method_name, method_code FROM methods "
            "WHERE method_code IS NOT NULL AND method_code != '' LIMIT ?",
            (limit * 5,),
        )
        infinite_loops = []
        for method_id, class_id, method_name, code in cur.fetchall():
            if not code:
                continue
            tree = self.SafeParse(code)
            found = []
            if tree is not None:
                for node in ast.walk(tree):
                    if isinstance(node, ast.While):
                        test = node.test
                        is_true = False
                        if isinstance(test, ast.Constant) and test.value is True:
                            is_true = True
                        elif isinstance(test, ast.Constant) and test.value == 1:
                            is_true = True
                        if is_true:
                            has_break = any(
                                isinstance(n, ast.Break) for n in ast.walk(node)
                            )
                            if not has_break:
                                found.append(
                                    {
                                        "line": getattr(node, "lineno", 0),
                                        "type": "while_true",
                                        "has_break": False,
                                    }
                                )
            else:
                lines = code.splitlines()
                for idx, line in enumerate(lines, 1):
                    if WHILE_TRUE_PATTERN.search(line):
                        block = "\n".join(lines[idx:])
                        if not BREAK_PATTERN.search(block):
                            found.append(
                                {"line": idx, "type": "while_true", "has_break": False}
                            )
            if found:
                infinite_loops.append(
                    {
                        "method_id": method_id,
                        "class_id": class_id,
                        "method_name": method_name,
                        "loops": found,
                        "loop_count": len(found),
                    }
                )
            if len(infinite_loops) >= limit:
                break
        report = {
            "infinite_loop_count": len(infinite_loops),
            "infinite_loops": infinite_loops,
        }
        self.state["results"].append(report)
        return (1, report, None)

    def ExitPaths(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        method = self.GetMethodCode(method_id)
        if method is None:
            return (0, None, ("NOT_FOUND", "method_id not found", 0))
        code = method.get("method_code", "") or ""
        tree = self.SafeParse(code)
        exits = []
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Return):
                    exits.append(
                        {
                            "line": getattr(node, "lineno", 0),
                            "type": "return",
                            "value": self.DescribeNode(node.value),
                        }
                    )
                elif isinstance(node, ast.Raise):
                    exits.append(
                        {
                            "line": getattr(node, "lineno", 0),
                            "type": "raise",
                            "value": self.DescribeNode(node.exc),
                        }
                    )
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr == "exit":
                        exits.append(
                            {
                                "line": getattr(node, "lineno", 0),
                                "type": "sys_exit",
                                "value": "sys.exit",
                            }
                        )
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id == "exit" or node.func.id == "quit":
                        exits.append(
                            {
                                "line": getattr(node, "lineno", 0),
                                "type": "builtin_exit",
                                "value": node.func.id,
                            }
                        )
        else:
            for idx, line in enumerate(code.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("return ") or stripped == "return":
                    exits.append({"line": idx, "type": "return", "value": stripped})
                elif stripped.startswith("raise "):
                    exits.append({"line": idx, "type": "raise", "value": stripped})
                elif "sys.exit" in stripped or stripped.startswith("exit(") or stripped.startswith("quit("):
                    exits.append({"line": idx, "type": "exit", "value": stripped})
        report = {
            "method_id": method_id,
            "method_name": method.get("method_name"),
            "exit_count": len(exits),
            "exits": exits,
        }
        self.state["results"].append(report)
        return (1, report, None)

    def DescribeNode(self, node):
        if node is None:
            return "None"
        if isinstance(node, ast.Constant):
            return repr(node.value)
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Tuple):
            return "tuple(" + ", ".join(self.DescribeNode(e) for e in node.elts) + ")"
        if isinstance(node, ast.Call):
            return "call(" + self.DescribeNode(node.func) + ")"
        return type(node).__name__

    def ExceptionFlowAnalysis(self, params):
        method_id = self._p(params, "method_id")
        if method_id is not None:
            return self.ExceptionFlowForMethod(method_id)
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, class_id, method_name, method_code FROM methods "
            "WHERE method_code IS NOT NULL AND method_code != '' "
            "ORDER BY method_id LIMIT ?",
            (limit,),
        )
        all_flows = []
        for mid, cid, mname, code in cur.fetchall():
            flow = self.AnalyzeExceptionFlow(code, mid, mname)
            if flow["try_count"] > 0 or flow["raise_count"] > 0:
                all_flows.append(flow)
        report = {
            "method_count": len(all_flows),
            "exception_flows": all_flows,
        }
        self.state["results"].append(report)
        return (1, report, None)

    def ExceptionFlowForMethod(self, method_id):
        method = self.GetMethodCode(method_id)
        if method is None:
            return (0, None, ("NOT_FOUND", "method_id not found", 0))
        code = method.get("method_code", "") or ""
        flow = self.AnalyzeExceptionFlow(code, method_id, method.get("method_name"))
        conn = self.Connect()
        cur = conn.cursor()
        propagation_paths = []
        cur.execute(
            "SELECT src_id FROM edges WHERE src_type='method' AND dst_type='method' "
            "AND edge_type='calls' AND dst_id=?",
            (method_id,),
        )
        caller_ids = [r[0] for r in cur.fetchall()]
        for caller_id in caller_ids:
            cur.execute("SELECT method_name FROM methods WHERE method_id=?", (caller_id,))
            row = cur.fetchone()
            if row:
                propagation_paths.append({
                    "caller_method_id": caller_id,
                    "caller_method_name": row[0],
                    "propagates_to": True,
                })
        flow["propagation_paths"] = propagation_paths
        flow["propagation_count"] = len(propagation_paths)
        self.state["results"].append(flow)
        return (1, flow, None)

    def AnalyzeExceptionFlow(self, code, method_id, method_name):
        tree = self.SafeParse(code)
        try_blocks = []
        raise_points = []
        exception_types = set()
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Try):
                    handlers = []
                    for handler in node.handlers:
                        exc_type = self.DescribeNode(handler.type)
                        handlers.append({
                            "line": getattr(handler, "lineno", 0),
                            "exception_type": exc_type,
                            "handler_name": handler.name,
                            "has_pass": len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass),
                            "has_raise": any(isinstance(n, ast.Raise) for n in ast.walk(handler)),
                        })
                        if exc_type and exc_type != "None":
                            exception_types.add(exc_type)
                    has_finally = len(node.finalbody) > 0
                    has_else = len(node.orelse) > 0
                    try_blocks.append({
                        "line": getattr(node, "lineno", 0),
                        "handler_count": len(handlers),
                        "handlers": handlers,
                        "has_finally": has_finally,
                        "has_else": has_else,
                    })
                if isinstance(node, ast.Raise):
                    exc_desc = self.DescribeNode(node.exc)
                    raise_points.append({
                        "line": getattr(node, "lineno", 0),
                        "exception": exc_desc,
                        "re_raise": node.exc is None,
                    })
                    if exc_desc and exc_desc != "None":
                        exception_types.add(exc_desc)
        else:
            for idx, line in enumerate(code.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("try"):
                    try_blocks.append({
                        "line": idx,
                        "handler_count": 0,
                        "handlers": [],
                        "has_finally": False,
                        "has_else": False,
                    })
                if stripped.startswith("except"):
                    if try_blocks:
                        try_blocks[-1]["handler_count"] += 1
                        try_blocks[-1]["handlers"].append({
                            "line": idx,
                            "exception_type": stripped,
                            "handler_name": None,
                            "has_pass": False,
                            "has_raise": False,
                        })
                if stripped.startswith("raise"):
                    raise_points.append({
                        "line": idx,
                        "exception": stripped,
                        "re_raise": stripped == "raise",
                    })
        return {
            "method_id": method_id,
            "method_name": method_name,
            "try_count": len(try_blocks),
            "try_blocks": try_blocks,
            "raise_count": len(raise_points),
            "raise_points": raise_points,
            "exception_types": sorted(exception_types),
            "bare_except_count": sum(1 for tb in try_blocks for h in tb["handlers"] if h["exception_type"] in ("None", "Exception", "BaseException")),
            "pass_except_count": sum(1 for tb in try_blocks for h in tb["handlers"] if h.get("has_pass")),
        }
