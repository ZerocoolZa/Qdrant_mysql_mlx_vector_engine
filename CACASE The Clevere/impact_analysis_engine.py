#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/impact_analysis_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 22: Impact Analysis -- 8 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="impact_analysis_engine.py" domain="twin_impact" authority="ImpactAnalysisEngine"}
# [@SUMMARY]{summary="Impact analysis authority: what breaks, what depends on it, what uses this, forward call graph, reverse call graph, ripple radius, risk score, confidence score."}
# [@CLASS]{class="ImpactAnalysisEngine" domain="impact" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="what_breaks" type="command"}
# [@METHOD]{method="what_depends_on_it" type="command"}
# [@METHOD]{method="what_uses_this" type="command"}
# [@METHOD]{method="forward_call_graph" type="command"}
# [@METHOD]{method="reverse_call_graph" type="command"}
# [@METHOD]{method="ripple_radius" type="command"}
# [@METHOD]{method="risk_score" type="command"}
# [@METHOD]{method="confidence_score" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class ImpactAnalysisEngine:
    """Authority for analyzing impact of changes across the codebase."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "max_depth": 10,
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
        if command == "what_breaks":
            return self.WhatBreaks(params)
        elif command == "what_depends_on_it":
            return self.WhatDependsOnIt(params)
        elif command == "what_uses_this":
            return self.WhatUsesThis(params)
        elif command == "forward_call_graph":
            return self.ForwardCallGraph(params)
        elif command == "reverse_call_graph":
            return self.ReverseCallGraph(params)
        elif command == "ripple_radius":
            return self.RippleRadius(params)
        elif command == "risk_score":
            return self.RiskScore(params)
        elif command == "confidence_score":
            return self.ConfidenceScore(params)
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

    def WhatBreaks(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT method_name FROM methods WHERE method_id=?", (method_id,)
            )
            row = cur.fetchone()
            if row is None:
                return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
            method_name = row[0]
            cur.execute(
                "SELECT dst_id FROM edges WHERE src_type='method' AND dst_type='method' "
                "AND src_id=?", (method_id,)
            )
            direct_callees = [r[0] for r in cur.fetchall()]
            cur.execute(
                "SELECT method_id, method_name FROM methods WHERE method_id IN "
                "(SELECT src_id FROM edges WHERE src_type='method' AND dst_type='method' "
                "AND dst_id=?)", (method_id,)
            )
            callers = [{"method_id": r[0], "method_name": r[1]} for r in cur.fetchall()]
            cur.execute(
                "SELECT class_id FROM classes WHERE class_id IN "
                "(SELECT class_id FROM methods WHERE method_id=?)",
                (method_id,)
            )
            class_row = cur.fetchone()
            class_id = class_row[0] if class_row else None
            breaks = []
            for caller_id, caller_name in callers:
                breaks.append({"type": "caller_breaks", "method_id": caller_id,
                               "method_name": caller_name})
            if class_id:
                cur.execute(
                    "SELECT class_id, class_name FROM classes WHERE class_id=?",
                    (class_id,)
                )
                crow = cur.fetchone()
                if crow:
                    breaks.append({"type": "class_breaks", "class_id": crow[0],
                                   "class_name": crow[1]})
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"method_id": method_id, "method_name": method_name,
                    "what_breaks": breaks, "break_count": len(breaks),
                    "direct_callees": len(direct_callees)}, None)

    def WhatDependsOnIt(self, params):
        target_id = self._p(params, "target_id")
        target_type = self._p(params, "target_type", "method")
        if target_id is None:
            return (0, None, ("MISSING_PARAM", "target_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT src_id, src_type, edge_type FROM edges "
                "WHERE dst_id=? AND dst_type=?",
                (target_id, target_type),
            )
            dependents = [{"src_id": r[0], "src_type": r[1], "edge_type": r[2]}
                          for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"target_id": target_id, "target_type": target_type,
                    "dependents": dependents, "count": len(dependents)}, None)

    def WhatUsesThis(self, params):
        target_id = self._p(params, "target_id")
        target_type = self._p(params, "target_type", "method")
        if target_id is None:
            return (0, None, ("MISSING_PARAM", "target_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT src_id, src_type, edge_type FROM edges "
                "WHERE dst_id=? AND dst_type=? AND edge_type IN ('uses', 'calls', 'imports', 'references')",
                (target_id, target_type),
            )
            users = []
            for r in cur.fetchall():
                src_id, src_type, edge_type = r[0], r[1], r[2]
                name = ""
                if src_type == "method":
                    cur.execute("SELECT method_name FROM methods WHERE method_id=?", (src_id,))
                    row = cur.fetchone()
                    name = row[0] if row else ""
                elif src_type == "class":
                    cur.execute("SELECT class_name FROM classes WHERE class_id=?", (src_id,))
                    row = cur.fetchone()
                    name = row[0] if row else ""
                elif src_type == "file":
                    cur.execute("SELECT file_path FROM files WHERE file_id=?", (src_id,))
                    row = cur.fetchone()
                    name = row[0] if row else ""
                users.append({"src_id": src_id, "src_type": src_type,
                              "src_name": name, "edge_type": edge_type})
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"target_id": target_id, "target_type": target_type,
                    "users": users, "count": len(users)}, None)

    def ForwardCallGraph(self, params):
        method_id = self._p(params, "method_id")
        max_depth = self._p(params, "max_depth", self.state["config"]["max_depth"])
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        visited = set()
        graph = []
        current = [(method_id, 0)]
        try:
            while current and len(visited) < 500:
                mid, depth = current.pop(0)
                if mid in visited or depth >= max_depth:
                    continue
                visited.add(mid)
                cur.execute("SELECT method_name FROM methods WHERE method_id=?", (mid,))
                row = cur.fetchone()
                name = row[0] if row else "unknown"
                graph.append({"method_id": mid, "method_name": name, "depth": depth})
                cur.execute(
                    "SELECT dst_id FROM edges WHERE src_type='method' AND dst_type='method' AND src_id=?",
                    (mid,),
                )
                for r in cur.fetchall():
                    current.append((r[0], depth + 1))
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"graph": graph, "node_count": len(graph),
                    "max_depth_reached": max(g["depth"] for g in graph) if graph else 0}, None)

    def ReverseCallGraph(self, params):
        method_id = self._p(params, "method_id")
        max_depth = self._p(params, "max_depth", self.state["config"]["max_depth"])
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        visited = set()
        graph = []
        current = [(method_id, 0)]
        try:
            while current and len(visited) < 500:
                mid, depth = current.pop(0)
                if mid in visited or depth >= max_depth:
                    continue
                visited.add(mid)
                cur.execute("SELECT method_name FROM methods WHERE method_id=?", (mid,))
                row = cur.fetchone()
                name = row[0] if row else "unknown"
                graph.append({"method_id": mid, "method_name": name, "depth": depth})
                cur.execute(
                    "SELECT src_id FROM edges WHERE src_type='method' AND dst_type='method' AND dst_id=?",
                    (mid,),
                )
                for r in cur.fetchall():
                    current.append((r[0], depth + 1))
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"graph": graph, "node_count": len(graph),
                    "max_depth_reached": max(g["depth"] for g in graph) if graph else 0}, None)

    def RippleRadius(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        fwd = self.ForwardCallGraph(params)
        rev = self.ReverseCallGraph(params)
        if fwd[0] == 0:
            return fwd
        if rev[0] == 0:
            return rev
        forward_nodes = fwd[1]["node_count"]
        reverse_nodes = rev[1]["node_count"]
        total = forward_nodes + reverse_nodes
        radius = 0
        if total > 100:
            radius = 5
        elif total > 50:
            radius = 4
        elif total > 20:
            radius = 3
        elif total > 10:
            radius = 2
        elif total > 3:
            radius = 1
        return (1, {"forward_nodes": forward_nodes, "reverse_nodes": reverse_nodes,
                    "total_affected": total, "ripple_radius": radius,
                    "severity": "critical" if radius >= 4 else (
                               "high" if radius >= 3 else (
                               "medium" if radius >= 2 else (
                               "low" if radius >= 1 else "minimal")))}, None)

    def RiskScore(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT cyclomatic_complexity, returns_tuple3, has_print, "
                "has_decorator, has_self_underscore FROM methods WHERE method_id=?",
                (method_id,),
            )
            row = cur.fetchone()
            if row is None:
                return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
            cc, tuple3, prints, decorators, underscores = row
            score = 0
            score += (cc or 0) * 2
            score += 10 if not tuple3 else 0
            score += 5 if prints else 0
            score += 5 if decorators else 0
            score += 5 if underscores else 0
            ripple = self.RippleRadius(params)
            if ripple[0] == 1:
                score += ripple[1]["total_affected"] * 3
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        level = "critical" if score >= 80 else (
                "high" if score >= 50 else (
                "medium" if score >= 25 else "low"))
        return (1, {"method_id": method_id, "risk_score": score,
                    "risk_level": level,
                    "complexity": cc, "violations": (prints or 0) + (decorators or 0) + (underscores or 0)}, None)

    def ConfidenceScore(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT returns_tuple3, has_print, has_decorator, has_self_underscore, "
                "cyclomatic_complexity FROM methods WHERE method_id=?",
                (method_id,),
            )
            row = cur.fetchone()
            if row is None:
                return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
            tuple3, prints, decorators, underscores, cc = row
            score = 100.0
            if not tuple3:
                score -= 30
            if prints:
                score -= 15
            if decorators:
                score -= 15
            if underscores:
                score -= 10
            if cc and cc > 10:
                score -= (cc - 10) * 2
            score = max(0, min(100, score))
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        level = "high" if score >= 80 else ("medium" if score >= 50 else "low")
        return (1, {"method_id": method_id, "confidence_score": round(score, 1),
                    "confidence_level": level}, None)
