#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/impact_engine.py"
# date="2026-06-26" author="Devin" session_id="phase4-analysis"
# context="Project Digital Twin Section 22 Impact Analysis"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="impact_engine.py" domain="twin_impact" authority="ImpactEngine"}
# [@SUMMARY]{summary="Impact analysis authority that computes what uses an entity, what breaks if it changes, reverse/forward call graphs, ripple radius, and risk scores."}
# [@CLASS]{class="ImpactEngine" domain="impact" authority="single"}
# [@METHOD]{method="what_uses" type="command"}
# [@METHOD]{method="what_breaks" type="command"}
# [@METHOD]{method="what_depends_on" type="command"}
# [@METHOD]{method="reverse_call_graph" type="command"}
# [@METHOD]{method="forward_call_graph" type="command"}
# [@METHOD]{method="ripple_radius" type="command"}
# [@METHOD]{method="risk_score" type="command"}
# [@METHOD]{method="confidence_score" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<ImpactEngine: computes what uses an entity, what breaks if it changes, reverse/forward call graphs, ripple radius, risk scores. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
ImpactEngine -- Impact analysis authority.
Implements Section 22 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: what_uses, what_breaks, what_depends_on, reverse_call_graph,
          forward_call_graph, ripple_radius, risk_score, confidence_score.
"""
import os
import sqlite3

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class ImpactEngine:
    """Impact analysis authority."""

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
        if command == "what_uses":
            return self.WhatUses(params)
        elif command == "what_breaks":
            return self.WhatBreaks(params)
        elif command == "what_depends_on":
            return self.WhatDependsOn(params)
        elif command == "reverse_call_graph":
            return self.ReverseCallGraph(params)
        elif command == "forward_call_graph":
            return self.ForwardCallGraph(params)
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
        return self.state["db_conn"]

    def WhatUses(self, params):
        entity_type = self._p(params, "entity_type", "method")
        entity_id = self._p(params, "entity_id")
        if not entity_id:
            return (0, None, ("NO_PARAM", "entity_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM edges WHERE dst_type=? AND dst_id=?", (entity_type, entity_id))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        # resolve source names for richer output
        for edge in results:
            edge["src_label"] = self.ResolveEntityName(cur, edge["src_type"], edge["src_id"])
        return (1, {"users": results, "count": len(results)}, None)

    def WhatDependsOn(self, params):
        # 22.3 What Depends On It: edges where dst_id=? AND edge_type IN depends_on/calls/imports
        entity_type = self._p(params, "entity_type", "method")
        entity_id = self._p(params, "entity_id")
        if not entity_id:
            return (0, None, ("NO_PARAM", "entity_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM edges WHERE dst_type=? AND dst_id=? "
                    "AND edge_type IN ('depends_on','calls','imports')",
                    (entity_type, entity_id))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        for edge in results:
            edge["src_label"] = self.ResolveEntityName(cur, edge["src_type"], edge["src_id"])
        return (1, {"dependents": results, "count": len(results)}, None)

    def ResolveEntityName(self, cur, entity_type, entity_id):
        try:
            if entity_type == "method":
                cur.execute("SELECT method_name FROM methods WHERE method_id=?", (entity_id,))
            elif entity_type == "class":
                cur.execute("SELECT class_name FROM classes WHERE class_id=?", (entity_id,))
            elif entity_type == "file":
                cur.execute("SELECT file_name FROM files WHERE file_id=?", (entity_id,))
            else:
                return None
            row = cur.fetchone()
            return row[0] if row else None
        except sqlite3.Error:
            return None

    def WhatBreaks(self, params):
        entity_type = self._p(params, "entity_type", "method")
        entity_id = self._p(params, "entity_id")
        if not entity_id:
            return (0, None, ("NO_PARAM", "entity_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("WITH RECURSIVE breaks AS ("
                    "SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type "
                    "FROM edges WHERE dst_type=? AND dst_id=? "
                    "AND edge_type IN ('depends_on','calls','imports') "
                    "UNION SELECT e.edge_id, e.src_type, e.src_id, e.dst_type, e.dst_id, e.edge_type "
                    "FROM edges e JOIN breaks b ON e.dst_type=b.src_type AND e.dst_id=b.src_id "
                    "WHERE e.edge_type IN ('depends_on','calls','imports')) "
                    "SELECT * FROM breaks", (entity_type, entity_id))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"breaks": results, "count": len(results)}, None)

    def ReverseCallGraph(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("WITH RECURSIVE reverse_calls AS ("
                    "SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type "
                    "FROM edges WHERE dst_type='method' AND dst_id=? AND edge_type='calls' "
                    "UNION SELECT e.edge_id, e.src_type, e.src_id, e.dst_type, e.dst_id, e.edge_type "
                    "FROM edges e JOIN reverse_calls r ON e.dst_type='method' AND e.dst_id=r.src_id "
                    "WHERE e.edge_type='calls') SELECT * FROM reverse_calls", (method_id,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"reverse_call_graph": results, "count": len(results)}, None)

    def ForwardCallGraph(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("WITH RECURSIVE forward_calls AS ("
                    "SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type "
                    "FROM edges WHERE src_type='method' AND src_id=? AND edge_type='calls' "
                    "UNION SELECT e.edge_id, e.src_type, e.src_id, e.dst_type, e.dst_id, e.edge_type "
                    "FROM edges e JOIN forward_calls f ON e.src_type='method' AND e.src_id=f.dst_id "
                    "WHERE e.edge_type='calls') SELECT * FROM forward_calls", (method_id,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"forward_call_graph": results, "count": len(results)}, None)

    def RippleRadius(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        # 22.6 Ripple Radius: count of nodes in reverse call graph + depth levels
        conn = self.Connect()
        cur = conn.cursor()
        # BFS over reverse call graph to compute depth levels
        visited = {method_id: 0}
        queue = [method_id]
        while queue:
            current = queue.pop(0)
            cur.execute("SELECT src_id FROM edges WHERE dst_type='method' AND dst_id=? "
                        "AND edge_type='calls'", (current,))
            for row in cur.fetchall():
                child = row[0]
                if child not in visited:
                    visited[child] = visited[current] + 1
                    queue.append(child)
        nodes = list(visited.keys())
        max_depth = max(visited.values()) if visited else 0
        return (1, {"ripple_radius": len(nodes), "nodes": nodes,
                    "max_depth": max_depth, "depth_map": visited}, None)

    def RiskScore(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        # 22.7 Risk Score: weighted by incoming edges, complexity, dependencies
        ripple = self.RippleRadius(params)
        if ripple[0] != 1:
            return ripple
        radius = ripple[1]["ripple_radius"]
        max_depth = ripple[1]["max_depth"]
        cur.execute("SELECT cyclomatic_complexity, line_count FROM methods WHERE method_id=?", (method_id,))
        row = cur.fetchone()
        complexity = row[0] if row and row[0] else 0
        line_count = row[1] if row and row[1] else 0
        # count direct incoming edges (all types)
        cur.execute("SELECT COUNT(*) FROM edges WHERE dst_type='method' AND dst_id=?", (method_id,))
        incoming = cur.fetchone()[0]
        # count outgoing dependencies
        cur.execute("SELECT COUNT(*) FROM edges WHERE src_type='method' AND src_id=? "
                    "AND edge_type IN ('calls','depends_on')", (method_id,))
        dependencies = cur.fetchone()[0]
        # weighted risk: radius * complexity / 10 + depth penalty + dependency load
        base_risk = (radius * complexity) / 10.0 if radius > 0 else 0
        depth_penalty = max_depth * 1.5
        dep_load = dependencies * 0.5
        risk = base_risk + depth_penalty + dep_load
        return (1, {"risk_score": round(risk, 2), "ripple_radius": radius,
                    "max_depth": max_depth, "complexity": complexity,
                    "incoming_edges": incoming, "dependencies": dependencies,
                    "line_count": line_count}, None)

    def ConfidenceScore(self, params):
        # 22.8 Confidence Score: based on graph completeness and test coverage
        method_id = self._p(params, "method_id")
        conn = self.Connect()
        cur = conn.cursor()
        # graph completeness: percentage of methods that have at least one edge
        cur.execute("SELECT COUNT(*) FROM methods")
        total_methods = cur.fetchone()[0] or 1
        cur.execute("SELECT COUNT(DISTINCT src_id) + COUNT(DISTINCT dst_id) FROM edges "
                    "WHERE src_type='method' AND dst_type='method'")
        connected = cur.fetchone()[0] or 0
        graph_completeness = (connected / total_methods * 100) if total_methods > 0 else 0
        # test coverage: methods with has_run_method=1 / total
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_run_method=1")
        run_methods = cur.fetchone()[0] or 0
        test_coverage = (run_methods / total_methods * 100) if total_methods > 0 else 0
        # per-method confidence: if method has edges and is tested
        method_confidence = 50.0
        if method_id:
            cur.execute("SELECT COUNT(*) FROM edges WHERE (src_id=? OR dst_id=?) "
                        "AND edge_type='calls'", (method_id, method_id))
            method_edges = cur.fetchone()[0]
            cur.execute("SELECT has_run_method, returns_tuple3 FROM methods WHERE method_id=?", (method_id,))
            row = cur.fetchone()
            if row:
                has_run = row[0]
                has_tuple3 = row[1]
                method_confidence = 30.0 + (method_edges * 5.0) + (has_run * 20.0) + (has_tuple3 * 10.0)
                method_confidence = min(method_confidence, 100.0)
        overall = (graph_completeness * 0.4 + test_coverage * 0.3 + method_confidence * 0.3)
        return (1, {"confidence_score": round(overall, 2),
                    "graph_completeness": round(graph_completeness, 2),
                    "test_coverage": round(test_coverage, 2),
                    "method_confidence": round(method_confidence, 2)}, None)

