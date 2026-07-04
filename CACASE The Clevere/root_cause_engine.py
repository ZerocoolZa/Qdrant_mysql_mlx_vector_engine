#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/root_cause_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 33: Root Cause Analysis -- 9 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="root_cause_engine.py" domain="twin_rootcause" authority="RootCauseEngine"}
# [@SUMMARY]{summary="Root cause authority: surface error, walk backward, dependency analysis, data flow analysis, control flow analysis, origin detection, first cause, secondary causes, cascading effects."}
# [@CLASS]{class="RootCauseEngine" domain="rootcause" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="surface_error" type="command"}
# [@METHOD]{method="walk_backward" type="command"}
# [@METHOD]{method="dependency_analysis" type="command"}
# [@METHOD]{method="data_flow_analysis" type="command"}
# [@METHOD]{method="control_flow_analysis" type="command"}
# [@METHOD]{method="origin_detection" type="command"}
# [@METHOD]{method="first_cause" type="command"}
# [@METHOD]{method="secondary_causes" type="command"}
# [@METHOD]{method="cascading_effects" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class RootCauseEngine:
    """Authority for tracing errors to their root causes."""

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
        if command == "surface_error":
            return self.SurfaceError(params)
        elif command == "walk_backward":
            return self.WalkBackward(params)
        elif command == "dependency_analysis":
            return self.DependencyAnalysis(params)
        elif command == "data_flow_analysis":
            return self.DataFlowAnalysis(params)
        elif command == "control_flow_analysis":
            return self.ControlFlowAnalysis(params)
        elif command == "origin_detection":
            return self.OriginDetection(params)
        elif command == "first_cause":
            return self.FirstCause(params)
        elif command == "secondary_causes":
            return self.SecondaryCauses(params)
        elif command == "cascading_effects":
            return self.CascadingEffects(params)
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

    def SurfaceError(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        if knowledge_id is None:
            return (0, None, ("MISSING_PARAM", "knowledge_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT k.knowledge_id, k.method_id, k.error_type, k.problem, k.evidence, "
                "m.method_name, c.class_name, f.file_path "
                "FROM knowledge k "
                "LEFT JOIN methods m ON k.method_id = m.method_id "
                "LEFT JOIN classes c ON m.class_id = c.class_id "
                "LEFT JOIN files f ON c.file_id = f.file_id "
                "WHERE k.knowledge_id=?",
                (knowledge_id,),
            )
            row = cur.fetchone()
            if row is None:
                return (0, None, ("KNOWLEDGE_NOT_FOUND", str(knowledge_id), 0))
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"knowledge_id": row[0], "method_id": row[1],
                    "error_type": row[2], "problem": row[3], "evidence": row[4],
                    "method_name": row[5], "class_name": row[6],
                    "file_path": row[7]}, None)

    def WalkBackward(self, params):
        method_id = self._p(params, "method_id")
        max_depth = self._p(params, "max_depth", self.state["config"]["max_depth"])
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        chain = []
        visited = set()
        current = [(method_id, 0)]
        try:
            while current and len(visited) < 300:
                mid, depth = current.pop(0)
                if mid in visited or depth >= max_depth:
                    continue
                visited.add(mid)
                cur.execute("SELECT method_name FROM methods WHERE method_id=?", (mid,))
                row = cur.fetchone()
                name = row[0] if row else "unknown"
                chain.append({"method_id": mid, "method_name": name, "depth": depth})
                cur.execute(
                    "SELECT src_id FROM edges WHERE dst_type='method' AND dst_id=? "
                    "AND edge_type IN ('calls','depends_on','uses')",
                    (mid,),
                )
                for r in cur.fetchall():
                    current.append((r[0], depth + 1))
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"chain": chain, "depth": len(chain)}, None)

    def DependencyAnalysis(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT src_id, src_type, edge_type FROM edges "
                "WHERE dst_id=? AND dst_type='method'",
                (method_id,),
            )
            deps = [{"src_id": r[0], "src_type": r[1], "edge_type": r[2]} for r in cur.fetchall()]
            cur.execute(
                "SELECT dst_id, dst_type, edge_type FROM edges "
                "WHERE src_id=? AND src_type='method'",
                (method_id,),
            )
            dependents = [{"dst_id": r[0], "dst_type": r[1], "edge_type": r[2]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"dependencies": deps, "dependents": dependents,
                    "dep_count": len(deps), "dependent_count": len(dependents)}, None)

    def DataFlowAnalysis(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT dst_id, dst_type, edge_type FROM edges "
                "WHERE src_id=? AND src_type='method' "
                "AND edge_type IN ('produces','passes','returns','writes','outputs')",
                (method_id,),
            )
            outputs = [{"dst_id": r[0], "dst_type": r[1], "edge_type": r[2]} for r in cur.fetchall()]
            cur.execute(
                "SELECT src_id, src_type, edge_type FROM edges "
                "WHERE dst_id=? AND dst_type='method' "
                "AND edge_type IN ('consumes','reads','receives','inputs')",
                (method_id,),
            )
            inputs = [{"src_id": r[0], "src_type": r[1], "edge_type": r[2]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"inputs": inputs, "outputs": outputs,
                    "input_count": len(inputs), "output_count": len(outputs)}, None)

    def ControlFlowAnalysis(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT method_name, cyclomatic_complexity, nesting_depth, "
                "branch_count, loop_count, return_paths "
                "FROM methods WHERE method_id=?",
                (method_id,),
            )
            row = cur.fetchone()
            if row is None:
                return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
            cur.execute(
                "SELECT dst_id, edge_type FROM edges "
                "WHERE src_id=? AND src_type='method' AND edge_type IN ('calls','branches','loops')",
                (method_id,),
            )
            flow = [{"dst_id": r[0], "edge_type": r[1]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"method_name": row[0], "complexity": row[1],
                    "nesting_depth": row[2], "branches": row[3],
                    "loops": row[4], "return_paths": row[5],
                    "flow_edges": flow}, None)

    def OriginDetection(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        if knowledge_id is None:
            return (0, None, ("MISSING_PARAM", "knowledge_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT method_id, error_type, problem FROM knowledge WHERE knowledge_id=?", (knowledge_id,))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("KNOWLEDGE_NOT_FOUND", str(knowledge_id), 0))
            method_id, error_type, problem = row
            origins = []
            if method_id:
                wb = self.WalkBackward({"method_id": method_id, "max_depth": 5})
                if wb[0] == 1:
                    for entry in wb[1]["chain"]:
                        if entry["depth"] == wb[1]["depth"] - 1:
                            origins.append({"origin": entry["method_name"],
                                            "method_id": entry["method_id"],
                                            "confidence": 80 - entry["depth"] * 10})
            if not origins:
                origins.append({"origin": error_type or "unknown", "confidence": 20})
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"knowledge_id": knowledge_id, "origins": origins,
                    "top_origin": origins[0] if origins else None}, None)

    def FirstCause(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        if knowledge_id is None:
            return (0, None, ("MISSING_PARAM", "knowledge_id required", 0))
        od = self.OriginDetection(params)
        if od[0] == 0:
            return od
        origins = od[1]["origins"]
        if not origins:
            return (1, {"first_cause": None, "confidence": 0}, None)
        first = max(origins, key=lambda o: o.get("confidence", 0))
        return (1, {"first_cause": first["origin"],
                    "method_id": first.get("method_id"),
                    "confidence": first["confidence"]}, None)

    def SecondaryCauses(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        if knowledge_id is None:
            return (0, None, ("MISSING_PARAM", "knowledge_id required", 0))
        od = self.OriginDetection(params)
        if od[0] == 0:
            return od
        origins = od[1]["origins"]
        if len(origins) <= 1:
            return (1, {"secondary_causes": [], "count": 0}, None)
        secondary = sorted(origins[1:], key=lambda o: o.get("confidence", 0), reverse=True)
        return (1, {"secondary_causes": secondary, "count": len(secondary)}, None)

    def CascadingEffects(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        affected = []
        visited = set()
        current = [(method_id, 0)]
        try:
            while current and len(visited) < 300:
                mid, depth = current.pop(0)
                if mid in visited or depth >= self.state["config"]["max_depth"]:
                    continue
                visited.add(mid)
                cur.execute("SELECT method_name FROM methods WHERE method_id=?", (mid,))
                row = cur.fetchone()
                name = row[0] if row else "unknown"
                affected.append({"method_id": mid, "method_name": name, "depth": depth})
                cur.execute(
                    "SELECT dst_id FROM edges WHERE src_type='method' AND dst_type='method' AND src_id=?",
                    (mid,),
                )
                for r in cur.fetchall():
                    current.append((r[0], depth + 1))
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"affected": affected, "cascade_count": len(affected),
                    "max_depth": max(a["depth"] for a in affected) if affected else 0}, None)
