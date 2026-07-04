#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/root_cause_engine.py"
# date="2026-06-26" author="Devin" session_id="phase6-intelligence"
# context="Project Digital Twin Section 33 Root Cause Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="root_cause_engine.py" domain="twin_rootcause" authority="RootCauseEngine"}
# [@SUMMARY]{summary="Root cause analysis authority that surfaces errors, walks backward through call chains, finds origins, and computes cascading effects."}
# [@CLASS]{class="RootCauseEngine" domain="rootcause" authority="single"}
# [@METHOD]{method="analyze_error" type="command"}
# [@METHOD]{method="walk_backward" type="command"}
# [@METHOD]{method="find_origin" type="command"}
# [@METHOD]{method="get_cascade" type="command"}
# [@METHOD]{method="full_analysis" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<RootCauseEngine: surfaces errors walks backward through call chains finds origins computes cascading effects. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations. Header missing Run method declaration but Run() exists in code.>][@todos<none>]}
"""
RootCauseEngine -- Root cause analysis authority.
Implements Section 33 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: analyze_error, walk_backward, find_origin, get_cascade, full_analysis.
"""
import ast
import json
import os
import re
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class RootCauseEngine:
    """Root cause analysis authority."""

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
        if command == "analyze_error":
            return self.AnalyzeError(params)
        elif command == "walk_backward":
            return self.WalkBackward(params)
        elif command == "find_origin":
            return self.FindOrigin(params)
        elif command == "get_cascade":
            return self.GetCascade(params)
        elif command == "full_analysis":
            return self.FullAnalysis(params)

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

    def AnalyzeError(self, params):
        method_id = self._p(params, "method_id")
        method_name = self._p(params, "method_name")
        error_text = self._p(params, "error_text", "")
        error_type = self._p(params, "error_type", "")
        if not method_id and not method_name and not error_text:
            return (0, None, ("NO_PARAM", "method_id or method_name or error_text required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        target_method = None
        if method_id:
            cur.execute(
                "SELECT method_id, method_name, class_id, file_id, method_code, start_line, end_line "
                "FROM methods WHERE method_id=?",
                (method_id,),
            )
            row = cur.fetchone()
            if row:
                target_method = {
                    "method_id": row[0],
                    "method_name": row[1],
                    "class_id": row[2],
                    "file_id": row[3],
                    "method_code": row[4],
                    "start_line": row[5],
                    "end_line": row[6],
                }
        elif method_name:
            cur.execute(
                "SELECT method_id, method_name, class_id, file_id, method_code, start_line, end_line "
                "FROM methods WHERE method_name=? LIMIT 1",
                (method_name,),
            )
            row = cur.fetchone()
            if row:
                target_method = {
                    "method_id": row[0],
                    "method_name": row[1],
                    "class_id": row[2],
                    "file_id": row[3],
                    "method_code": row[4],
                    "start_line": row[5],
                    "end_line": row[6],
                }
                method_id = row[0]
        if target_method is None and error_text:
            cur.execute(
                "SELECT method_id, method_name, class_id, file_id, method_code, start_line, end_line "
                "FROM methods WHERE method_code LIKE ? LIMIT 1",
                ("%" + error_text[:100] + "%",),
            )
            row = cur.fetchone()
            if row:
                target_method = {
                    "method_id": row[0],
                    "method_name": row[1],
                    "class_id": row[2],
                    "file_id": row[3],
                    "method_code": row[4],
                    "start_line": row[5],
                    "end_line": row[6],
                }
                method_id = row[0]
        if target_method is None:
            cur.execute(
                "SELECT knowledge_id, problem, error_type, error_text, method_id "
                "FROM knowledge WHERE error_text LIKE ? OR problem LIKE ? ORDER BY knowledge_id DESC LIMIT 1",
                ("%" + error_text[:100] + "%", "%" + error_text[:100] + "%"),
            )
            krow = cur.fetchone()
            if krow:
                method_id = krow[4]
                if method_id:
                    cur.execute(
                        "SELECT method_id, method_name, class_id, file_id, method_code, start_line, end_line "
                        "FROM methods WHERE method_id=?",
                        (method_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        target_method = {
                            "method_id": row[0],
                            "method_name": row[1],
                            "class_id": row[2],
                            "file_id": row[3],
                            "method_code": row[4],
                            "start_line": row[5],
                            "end_line": row[6],
                        }
        if target_method is None:
            return (0, None, ("METHOD_NOT_FOUND", "Could not locate method for error", 0))
        error_lines = []
        if error_text:
            for line in error_text.splitlines():
                if "Error" in line or "Exception" in line or "line" in line.lower():
                    error_lines.append(line.strip())
        result = {
            "surface_error": error_text,
            "error_type": error_type,
            "error_lines": error_lines,
            "method": target_method,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append({"step": "analyze_error", "data": result})
        return (1, result, None)

    def WalkBackward(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "WITH RECURSIVE backward AS ("
            "SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type, evidence, confidence "
            "FROM edges WHERE dst_type='method' AND dst_id=? AND edge_type='calls' "
            "UNION SELECT e.edge_id, e.src_type, e.src_id, e.dst_type, e.dst_id, e.edge_type, e.evidence, e.confidence "
            "FROM edges e JOIN backward b ON e.dst_type='method' AND e.dst_id=b.src_id "
            "WHERE e.edge_type='calls') "
            "SELECT src_id, dst_id, edge_type, evidence, confidence FROM backward",
            (method_id,),
        )
        raw_edges = cur.fetchall()
        chain = []
        visited = set()
        for row in raw_edges:
            src_id = row[0]
            if src_id not in visited:
                visited.add(src_id)
                chain.append(src_id)
        chain_details = []
        for mid in chain:
            cur.execute(
                "SELECT method_id, method_name, class_id, cyclomatic_complexity, method_code "
                "FROM methods WHERE method_id=?",
                (mid,),
            )
            mrow = cur.fetchone()
            if mrow:
                chain_details.append({
                    "method_id": mrow[0],
                    "method_name": mrow[1],
                    "class_id": mrow[2],
                    "complexity": mrow[3],
                    "code_snippet": mrow[4][:200] if mrow[4] else "",
                })
        cur.execute(
            "SELECT edge_type, COUNT(*) FROM edges WHERE (src_type='method' AND src_id=?) OR (dst_type='method' AND dst_id=?) GROUP BY edge_type",
            (method_id, method_id),
        )
        dependency_summary = {row[0]: row[1] for row in cur.fetchall()}
        data_flow = self.TraceDataFlow(cur, method_id)
        control_flow = self.TraceControlFlow(cur, method_id)
        result = {
            "chain": chain,
            "chain_details": chain_details,
            "count": len(chain),
            "dependencies": dependency_summary,
            "data_flow": data_flow,
            "control_flow": control_flow,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append({"step": "walk_backward", "data": result})
        return (1, result, None)

    def TraceDataFlow(self, cur, method_id):
        cur.execute("SELECT method_code FROM methods WHERE method_id=?", (method_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            return {"variables": [], "assignments": []}
        code = row[0]
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {"variables": [], "assignments": []}
        variables = []
        assignments = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id not in variables:
                    variables.append(node.id)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id not in assignments:
                        assignments.append(target.id)
        return {"variables": variables, "assignments": assignments}

    def TraceControlFlow(self, cur, method_id):
        cur.execute("SELECT method_code FROM methods WHERE method_id=?", (method_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            return {"branches": 0, "loops": 0, "raises": 0}
        code = row[0]
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {"branches": 0, "loops": 0, "raises": 0}
        branches = 0
        loops = 0
        raises = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.IfExp)):
                branches += 1
            elif isinstance(node, (ast.For, ast.While)):
                loops += 1
            elif isinstance(node, ast.Raise):
                raises += 1
        return {"branches": branches, "loops": loops, "raises": raises}

    def FindOrigin(self, params):
        walk_res = self.WalkBackward(params)
        if walk_res[0] != 1:
            return walk_res
        walk_data = walk_res[1]
        chain = walk_data["chain"]
        chain_details = walk_data["chain_details"]
        if not chain:
            return (1, {"origin": None, "reason": "no callers found", "chain": [], "first_cause": None}, None)
        conn = self.Connect()
        cur = conn.cursor()
        origin = chain[-1]
        origin_complexity = 0
        origin_score = -1
        for detail in chain_details:
            mid = detail["method_id"]
            complexity = detail.get("complexity", 0) or 0
            cur.execute(
                "SELECT COUNT(*) FROM edges WHERE src_type='method' AND src_id=? AND edge_type='calls'",
                (mid,),
            )
            outgoing = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM edges WHERE dst_type='method' AND dst_id=? AND edge_type='calls'",
                (mid,),
            )
            incoming = cur.fetchone()[0]
            score = complexity + incoming * 2
            if score > origin_score:
                origin_score = score
                origin = mid
                origin_complexity = complexity
        cur.execute(
            "SELECT method_name, method_code, start_line FROM methods WHERE method_id=?",
            (origin,),
        )
        row = cur.fetchone()
        first_cause = None
        if row:
            first_cause = {
                "method_id": origin,
                "method_name": row[0],
                "code_snippet": row[1][:300] if row[1] else "",
                "start_line": row[2],
            }
        result = {
            "origin": origin,
            "origin_complexity": origin_complexity,
            "origin_score": origin_score,
            "chain": chain,
            "chain_details": chain_details,
            "first_cause": first_cause,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append({"step": "find_origin", "data": result})
        return (1, result, None)

    def GetCascade(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "WITH RECURSIVE forward AS ("
            "SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type "
            "FROM edges WHERE src_type='method' AND src_id=? AND edge_type='calls' "
            "UNION SELECT e.edge_id, e.src_type, e.src_id, e.dst_type, e.dst_id, e.edge_type "
            "FROM edges e JOIN forward f ON e.src_type='method' AND e.src_id=f.dst_id "
            "WHERE e.edge_type='calls') SELECT DISTINCT dst_id FROM forward",
            (method_id,),
        )
        affected = [r[0] for r in cur.fetchall()]
        cascade_details = []
        secondary_causes = []
        for mid in affected:
            cur.execute(
                "SELECT method_id, method_name, class_id, cyclomatic_complexity FROM methods WHERE method_id=?",
                (mid,),
            )
            row = cur.fetchone()
            if row:
                detail = {
                    "method_id": row[0],
                    "method_name": row[1],
                    "class_id": row[2],
                    "complexity": row[3],
                }
                cascade_details.append(detail)
                if row[3] and row[3] > 5:
                    secondary_causes.append(row[0])
        result = {
            "affected": affected,
            "count": len(affected),
            "cascade_details": cascade_details,
            "secondary_causes": secondary_causes,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append({"step": "get_cascade", "data": result})
        return (1, result, None)

    def FullAnalysis(self, params):
        results = {}
        for step in ("analyze_error", "walk_backward", "find_origin", "get_cascade"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        origin_data = results.get("find_origin", {})
        cascade_data = results.get("get_cascade", {})
        origin = origin_data.get("origin") if isinstance(origin_data, dict) else None
        affected = cascade_data.get("affected", []) if isinstance(cascade_data, dict) else []
        summary = {
            "root_cause": origin,
            "cascade_count": len(affected) if isinstance(affected, list) else 0,
            "total_chain_length": len(results.get("walk_backward", {}).get("chain", [])) if isinstance(results.get("walk_backward"), dict) else 0,
        }
        results["summary"] = summary
        results["created"] = datetime.now(timezone.utc).isoformat()
        self.state["results"].append({"step": "full_analysis", "data": results})
        return (1, {"full_analysis": results}, None)

