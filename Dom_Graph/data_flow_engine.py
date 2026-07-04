#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/data_flow_engine.py"
# date="2026-06-26" author="Devin" session_id="phase4-analysis"
# context="Project Digital Twin Phase 4 Section 43 Data Flow Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="data_flow_engine.py" domain="twin_dataflow" authority="DataFlowEngine"}
# [@SUMMARY]{summary="Data flow authority that traces variables, parameters, returns, database query flow and file I/O flow through method bodies via AST analysis."}
# [@CLASS]{class="DataFlowEngine" domain="dataflow" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="trace_variable" type="command"}
# [@METHOD]{method="trace_parameter" type="command"}
# [@METHOD]{method="trace_return" type="command"}
# [@METHOD]{method="trace_database_flow" type="command"}
# [@METHOD]{method="trace_file_flow" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<DataFlowEngine: traces variables, parameters, returns, DB query flow, file I/O flow via AST. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
DataFlowEngine -- authority for tracing data flow through method bodies.
Implements Section 43 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: trace_variable, trace_parameter, trace_return,
          trace_database_flow, trace_file_flow.
"""
import ast
import os
import re
import sqlite3

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
SQL_FLOW_PATTERN = re.compile(
    r"\b(execute|fetchone|fetchall|fetchmany|commit|rollback|SELECT|INSERT|UPDATE|DELETE)\b",
    re.IGNORECASE,
)
FILE_FLOW_PATTERN = re.compile(
    r"\b(open|read|readline|readlines|write|writelines|close|read_bytes|read_text)\b"
)
NETWORK_FLOW_PATTERN = re.compile(
    r"\b(requests\.(get|post|put|delete|patch|head)|urllib|httpx|aiohttp|"
    r"http\.client|socket\.|urlopen|urlretrieve)\b"
)
NETWORK_FUNCS = ("get", "post", "put", "delete", "patch", "head", "request")
NETWORK_MODULES = ("requests", "httpx", "aiohttp", "urllib", "http")


class DataFlowEngine:
    """Authority for tracing variable, parameter, return, DB and file data flow."""

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
        if command == "trace_variable":
            return self.TraceVariable(params)
        elif command == "trace_parameter":
            return self.TraceParameter(params)
        elif command == "trace_return":
            return self.TraceReturn(params)
        elif command == "trace_database_flow":
            return self.TraceDatabaseFlow(params)
        elif command == "trace_file_flow":
            return self.TraceFileFlow(params)
        elif command == "trace_network_flow":
            return self.TraceNetworkFlow(params)
        elif command == "trace_variable_deep":
            return self.TraceVariableDeep(params)
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
            "SELECT method_id, class_id, method_name, method_code, parameters, "
            "signature FROM methods WHERE method_id=?",
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
            "parameters": row[4],
            "signature": row[5],
        }

    def TraceVariable(self, params):
        variable_name = self._p(params, "variable_name")
        method_id = self._p(params, "method_id")
        if variable_name is None:
            return (0, None, ("MISSING_PARAM", "variable_name required", 0))
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        method = self.GetMethodCode(method_id)
        if method is None:
            return (0, None, ("NOT_FOUND", "method_id not found", 0))
        code = method.get("method_code", "") or ""
        tree = self.SafeParse(code)
        origin_line = None
        mutations = []
        uses = []
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == variable_name:
                            line = getattr(node, "lineno", 0)
                            if origin_line is None:
                                origin_line = line
                            mutations.append(line)
                elif isinstance(node, ast.AugAssign):
                    if isinstance(node.target, ast.Name) and node.target.id == variable_name:
                        mutations.append(getattr(node, "lineno", 0))
                elif isinstance(node, ast.Name) and node.id == variable_name:
                    if isinstance(node.ctx, ast.Load):
                        uses.append(getattr(node, "lineno", 0))
        else:
            for idx, line in enumerate(code.splitlines(), 1):
                if variable_name in line:
                    if "=" in line and line.strip().startswith(variable_name):
                        if origin_line is None:
                            origin_line = idx
                        mutations.append(idx)
                    else:
                        uses.append(idx)
        last_use_line = uses[-1] if uses else (mutations[-1] if mutations else origin_line)
        report = {
            "variable_name": variable_name,
            "method_id": method_id,
            "method_name": method.get("method_name"),
            "origin_line": origin_line,
            "mutations": mutations,
            "mutation_count": len(mutations),
            "uses": uses,
            "last_use_line": last_use_line,
        }
        self.state["results"].append(report)
        return (1, report, None)

    def TraceParameter(self, params):
        param_name = self._p(params, "param_name")
        method_id = self._p(params, "method_id")
        if param_name is None:
            return (0, None, ("MISSING_PARAM", "param_name required", 0))
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        method = self.GetMethodCode(method_id)
        if method is None:
            return (0, None, ("NOT_FOUND", "method_id not found", 0))
        code = method.get("method_code", "") or ""
        tree = self.SafeParse(code)
        uses = []
        modifications = []
        passed_to_calls = []
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id == param_name:
                    line = getattr(node, "lineno", 0)
                    if isinstance(node.ctx, ast.Load):
                        uses.append(line)
                    elif isinstance(node.ctx, ast.Store):
                        modifications.append(line)
                elif isinstance(node, ast.Call):
                    for arg in node.args:
                        if isinstance(arg, ast.Name) and arg.id == param_name:
                            passed_to_calls.append(getattr(node, "lineno", 0))
                    for kw in node.keywords:
                        if isinstance(kw.value, ast.Name) and kw.value.id == param_name:
                            passed_to_calls.append(getattr(node, "lineno", 0))
        else:
            for idx, line in enumerate(code.splitlines(), 1):
                if param_name in line:
                    uses.append(idx)
        report = {
            "param_name": param_name,
            "method_id": method_id,
            "method_name": method.get("method_name"),
            "uses": uses,
            "use_count": len(uses),
            "modifications": modifications,
            "passed_to_calls": passed_to_calls,
            "call_pass_count": len(passed_to_calls),
        }
        self.state["results"].append(report)
        return (1, report, None)

    def TraceReturn(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        method = self.GetMethodCode(method_id)
        if method is None:
            return (0, None, ("NOT_FOUND", "method_id not found", 0))
        code = method.get("method_code", "") or ""
        tree = self.SafeParse(code)
        return_points = []
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Return):
                    line = getattr(node, "lineno", 0)
                    value_desc = self.DescribeNode(node.value)
                    return_points.append(
                        {"line": line, "value": value_desc, "type": "return"}
                    )
                elif isinstance(node, ast.Raise):
                    line = getattr(node, "lineno", 0)
                    return_points.append(
                        {
                            "line": line,
                            "value": self.DescribeNode(node.exc),
                            "type": "raise",
                        }
                    )
        else:
            for idx, line in enumerate(code.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("return ") or stripped == "return":
                    return_points.append(
                        {"line": idx, "value": stripped, "type": "return"}
                    )
                elif stripped.startswith("raise "):
                    return_points.append(
                        {"line": idx, "value": stripped, "type": "raise"}
                    )
        callers = []
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT src_id FROM edges WHERE src_type='method' AND dst_type='method' "
            "AND edge_type='calls' AND dst_id=?",
            (method_id,),
        )
        caller_ids = [r[0] for r in cur.fetchall()]
        for caller_id in caller_ids:
            cur.execute(
                "SELECT method_name FROM methods WHERE method_id=?", (caller_id,)
            )
            row = cur.fetchone()
            if row:
                callers.append({"method_id": caller_id, "method_name": row[0]})
        report = {
            "method_id": method_id,
            "method_name": method.get("method_name"),
            "return_points": return_points,
            "return_count": len(return_points),
            "callers": callers,
            "caller_count": len(callers),
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
        if isinstance(node, ast.Attribute):
            return self.DescribeNode(node.value) + "." + node.attr
        return type(node).__name__

    def TraceDatabaseFlow(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        method = self.GetMethodCode(method_id)
        if method is None:
            return (0, None, ("NOT_FOUND", "method_id not found", 0))
        code = method.get("method_code", "") or ""
        tree = self.SafeParse(code)
        query_points = []
        result_flow = []
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    attr = node.func.attr
                    if attr in ("execute", "fetchone", "fetchall", "fetchmany", "commit", "rollback"):
                        line = getattr(node, "lineno", 0)
                        query_points.append(
                            {
                                "line": line,
                                "operation": attr,
                                "args": [self.DescribeNode(a) for a in node.args],
                            }
                        )
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(node.value, ast.Call) and isinstance(
                            node.value.func, ast.Attribute
                        ):
                            attr = node.value.func.attr
                            if attr in ("fetchone", "fetchall", "fetchmany", "execute"):
                                target_name = self.DescribeNode(target)
                                result_flow.append(
                                    {
                                        "line": getattr(node, "lineno", 0),
                                        "target": target_name,
                                        "source": attr,
                                    }
                                )
        else:
            for idx, line in enumerate(code.splitlines(), 1):
                matches = SQL_FLOW_PATTERN.findall(line)
                if matches:
                    query_points.append(
                        {"line": idx, "operation": matches[0], "args": []}
                    )
        report = {
            "method_id": method_id,
            "method_name": method.get("method_name"),
            "query_points": query_points,
            "query_count": len(query_points),
            "result_flow": result_flow,
            "result_flow_count": len(result_flow),
        }
        self.state["results"].append(report)
        return (1, report, None)

    def TraceFileFlow(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        method = self.GetMethodCode(method_id)
        if method is None:
            return (0, None, ("NOT_FOUND", "method_id not found", 0))
        code = method.get("method_code", "") or ""
        tree = self.SafeParse(code)
        open_points = []
        data_flow = []
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id == "open":
                        open_points.append(
                            {
                                "line": getattr(node, "lineno", 0),
                                "args": [self.DescribeNode(a) for a in node.args],
                            }
                        )
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    attr = node.func.attr
                    if attr in ("read", "readline", "readlines", "write", "writelines", "close", "read_bytes", "read_text"):
                        data_flow.append(
                            {
                                "line": getattr(node, "lineno", 0),
                                "operation": attr,
                                "source": self.DescribeNode(node.func.value),
                            }
                        )
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(node.value, ast.Call):
                            inner = node.value
                            if isinstance(inner.func, ast.Attribute) and inner.func.attr in ("read", "readline", "readlines", "read_bytes", "read_text"):
                                data_flow.append(
                                    {
                                        "line": getattr(node, "lineno", 0),
                                        "operation": "assign_from_" + inner.func.attr,
                                        "target": self.DescribeNode(target),
                                        "source": self.DescribeNode(inner.func.value),
                                    }
                                )
        else:
            for idx, line in enumerate(code.splitlines(), 1):
                matches = FILE_FLOW_PATTERN.findall(line)
                if matches:
                    data_flow.append(
                        {"line": idx, "operation": matches[0], "source": "text"}
                    )
        report = {
            "method_id": method_id,
            "method_name": method.get("method_name"),
            "open_points": open_points,
            "open_count": len(open_points),
            "data_flow": data_flow,
            "data_flow_count": len(data_flow),
        }
        self.state["results"].append(report)
        return (1, report, None)

    def TraceNetworkFlow(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        method = self.GetMethodCode(method_id)
        if method is None:
            return (0, None, ("NOT_FOUND", "method_id not found", 0))
        code = method.get("method_code", "") or ""
        tree = self.SafeParse(code)
        network_points = []
        response_flow = []
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Attribute):
                        if func.attr in NETWORK_FUNCS:
                            if isinstance(func.value, ast.Name) and func.value.id in NETWORK_MODULES:
                                network_points.append({
                                    "line": getattr(node, "lineno", 0),
                                    "module": func.value.id,
                                    "method": func.attr,
                                    "args": [self.DescribeNode(a) for a in node.args],
                                })
                        if func.attr in ("urlopen", "urlretrieve", "Request"):
                            if isinstance(func.value, ast.Name) and func.value.id in ("urllib", "urllib_request", "request"):
                                network_points.append({
                                    "line": getattr(node, "lineno", 0),
                                    "module": "urllib",
                                    "method": func.attr,
                                    "args": [self.DescribeNode(a) for a in node.args],
                                })
                    if isinstance(func, ast.Name) and func.id in ("urlopen", "urlretrieve"):
                        network_points.append({
                            "line": getattr(node, "lineno", 0),
                            "module": "urllib",
                            "method": func.id,
                            "args": [self.DescribeNode(a) for a in node.args],
                        })
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(node.value, ast.Call):
                            inner = node.value
                            if isinstance(inner.func, ast.Attribute) and inner.func.attr in NETWORK_FUNCS:
                                if isinstance(inner.func.value, ast.Name) and inner.func.value.id in NETWORK_MODULES:
                                    response_flow.append({
                                        "line": getattr(node, "lineno", 0),
                                        "target": self.DescribeNode(target),
                                        "source": inner.func.value.id + "." + inner.func.attr,
                                    })
        else:
            for idx, line in enumerate(code.splitlines(), 1):
                matches = NETWORK_FLOW_PATTERN.findall(line)
                if matches:
                    network_points.append({
                        "line": idx,
                        "module": "text_scan",
                        "method": matches[0],
                        "args": [],
                    })
        report = {
            "method_id": method_id,
            "method_name": method.get("method_name"),
            "network_points": network_points,
            "network_count": len(network_points),
            "response_flow": response_flow,
            "response_flow_count": len(response_flow),
        }
        self.state["results"].append(report)
        return (1, report, None)

    def TraceVariableDeep(self, params):
        variable_name = self._p(params, "variable_name")
        method_id = self._p(params, "method_id")
        if variable_name is None:
            return (0, None, ("MISSING_PARAM", "variable_name required", 0))
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        method = self.GetMethodCode(method_id)
        if method is None:
            return (0, None, ("NOT_FOUND", "method_id not found", 0))
        code = method.get("method_code", "") or ""
        tree = self.SafeParse(code)
        origin_line = None
        mutations = []
        uses = []
        passed_to_methods = []
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == variable_name:
                            line = getattr(node, "lineno", 0)
                            if origin_line is None:
                                origin_line = line
                            mutations.append(line)
                elif isinstance(node, ast.AugAssign):
                    if isinstance(node.target, ast.Name) and node.target.id == variable_name:
                        mutations.append(getattr(node, "lineno", 0))
                elif isinstance(node, ast.Name) and node.id == variable_name:
                    if isinstance(node.ctx, ast.Load):
                        uses.append(getattr(node, "lineno", 0))
                if isinstance(node, ast.Call):
                    for arg in node.args:
                        if isinstance(arg, ast.Name) and arg.id == variable_name:
                            callee = self.DescribeNode(node.func)
                            passed_to_methods.append({
                                "line": getattr(node, "lineno", 0),
                                "callee": callee,
                            })
        else:
            for idx, line in enumerate(code.splitlines(), 1):
                if variable_name in line:
                    if "=" in line and line.strip().startswith(variable_name):
                        if origin_line is None:
                            origin_line = idx
                        mutations.append(idx)
                    else:
                        uses.append(idx)
        conn = self.Connect()
        cur = conn.cursor()
        cross_method_tracking = []
        for entry in passed_to_methods:
            callee_name = entry["callee"]
            if "." in callee_name:
                callee_name = callee_name.split(".")[-1]
            cur.execute(
                "SELECT method_id FROM methods WHERE method_name=? LIMIT 1",
                (callee_name,),
            )
            row = cur.fetchone()
            if row:
                callee_id = row[0]
                cross_method_tracking.append({
                    "line": entry["line"],
                    "callee_method_id": callee_id,
                    "callee_method_name": callee_name,
                    "variable": variable_name,
                })
        cur.execute(
            "SELECT dst_id FROM edges WHERE src_type='method' AND dst_type='method' "
            "AND edge_type='calls' AND src_id=?",
            (method_id,),
        )
        outgoing = [r[0] for r in cur.fetchall()]
        for dst_id in outgoing:
            cur.execute("SELECT method_name FROM methods WHERE method_id=?", (dst_id,))
            row = cur.fetchone()
            if row:
                cross_method_tracking.append({
                    "line": 0,
                    "callee_method_id": dst_id,
                    "callee_method_name": row[0],
                    "variable": variable_name,
                    "via_edge": True,
                })
        last_use_line = uses[-1] if uses else (mutations[-1] if mutations else origin_line)
        report = {
            "variable_name": variable_name,
            "method_id": method_id,
            "method_name": method.get("method_name"),
            "origin_line": origin_line,
            "mutations": mutations,
            "mutation_count": len(mutations),
            "uses": uses,
            "use_count": len(uses),
            "last_use_line": last_use_line,
            "passed_to_methods": passed_to_methods,
            "cross_method_tracking": cross_method_tracking,
            "cross_method_count": len(cross_method_tracking),
        }
        self.state["results"].append(report)
        return (1, report, None)
