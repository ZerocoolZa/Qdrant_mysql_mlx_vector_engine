#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/DependencyEdgeStore.py"
# date="2026-06-27" author="Devin" session_id="memunit-eventsourcing-impl"
# context="Versioned dependency graph edges. READS/WRITES/CALLS/IMPORTS/INHERITS/GRAPH. Edges bind versions, not just nodes."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="DependencyEdgeStore.py" domain="dep_graph" authority="DependencyEdgeStore"}
# [@SUMMARY]{summary="CRUD for mu_dependency_edges. Edges bind versions (from_version_id, to_version_id). Emits EVENT_DEPENDENCY_EDGE_ADDED. Queries by node/version/type."}
# [@CLASS]{class="DependencyEdgeStore" domain="dep_graph" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="AddEdge" type="command"}
# [@METHOD]{method="GetEdge" type="query"}
# [@METHOD]{method="QueryFromNode" type="query"}
# [@METHOD]{method="QueryToNode" type="query"}
# [@METHOD]{method="QueryByType" type="query"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Versioned dependency graph edges store. Edges bind versions not just nodes. CRUD for mu_dependency_edges. Emits events. VBStyle compliant: Run dispatch, Tuple3, self.state. No violations found.>][@todos<none>]}
"""
DependencyEdgeStore -- Versioned dependency graph edges.

Edges bind VERSIONS, not just nodes - because a method's dependencies
can change between versions. from_version_id is required; to_version_id
is NULL for "any version" (e.g. imports).

Edge types: READS, WRITES, CALLS, IMPORTS, INHERITS, GRAPH.

EVENT FLOW:
  1. Append EVENT_DEPENDENCY_EDGE_ADDED to EventLogStore
  2. INSERT into mu_dependency_edges (in-RAM)

Usage:
  de = DependencyEdgeStore(mem=log, db=db)
  ok, data, err = de.Run("add_edge", {
      "from_node_id": 5,
      "to_node_id": 3,
      "from_version_id": 8,
      "edge_type": "CALLS",
  })
"""
from datetime import datetime
from typing import Any, Dict, List, Tuple

EDGE_READS = "READS"
EDGE_WRITES = "WRITES"
EDGE_CALLS = "CALLS"
EDGE_IMPORTS = "IMPORTS"
EDGE_INHERITS = "INHERITS"
EDGE_GRAPH = "GRAPH"
EVENT_DEPENDENCY_EDGE_ADDED = "EVENT_DEPENDENCY_EDGE_ADDED"


class DependencyEdgeStore:
    """Versioned dependency graph edges. Bind versions, not just nodes."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "session_id": "default",
            },
            "mem": mem,
            "db": db,
            "last_edge_id": None,
            "stats": {
                "added": 0,
                "queries": 0,
            },
        }
        if param:
            self.state["config"].update(param)

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "add_edge": self.AddEdge,
            "get_edge": self.GetEdge,
            "query_from_node": self.QueryFromNode,
            "query_to_node": self.QueryToNode,
            "query_by_type": self.QueryByType,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def AddEdge(self, params):
        from_node_id = self._p(params, "from_node_id")
        to_node_id = self._p(params, "to_node_id")
        from_version_id = self._p(params, "from_version_id")
        edge_type = self._p(params, "edge_type", EDGE_CALLS)
        if not from_node_id or not to_node_id or not from_version_id:
            return (0, None, ("MISSING_PARAM", "from_node_id, to_node_id, from_version_id required", 0))
        to_version_id = self._p(params, "to_version_id")
        log = self.state["mem"]
        db = self.state["db"]
        if not log or not db:
            return (0, None, ("NO_DEPS", "mem and db required", 0))
        ts = datetime.utcnow().isoformat() + "Z"
        event = {
            "type": EVENT_DEPENDENCY_EDGE_ADDED,
            "ts": ts,
            "session_id": self.state["config"]["session_id"],
            "cause": self._p(params, "cause", "edge added"),
            "before": None,
            "after": {
                "from_node_id": from_node_id,
                "to_node_id": to_node_id,
                "from_version_id": from_version_id,
                "to_version_id": to_version_id,
                "edge_type": edge_type,
            },
        }
        r = log.Run("append", {"event": event})
        if r[0] != 1:
            return (0, None, ("LOG_FAILED", str(r[2]), 0))
        event_id = r[1]["id"]
        r = db.Run("execute", {
            "sql": """INSERT INTO mu_dependency_edges
                (from_node_id, to_node_id, from_version_id, to_version_id,
                 edge_type, evidence_event_id, validity_state, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'VALID', ?)""",
            "params": [from_node_id, to_node_id, from_version_id,
                       to_version_id, edge_type, event_id, ts],
        })
        if r[0] != 1:
            return (0, None, ("DB_FAILED", str(r[2]), 0))
        edge_id = r[1]["lastrowid"]
        self.state["last_edge_id"] = edge_id
        self.state["stats"]["added"] += 1
        return (1, {"edge_id": edge_id, "event_id": event_id}, None)

    def GetEdge(self, params):
        edge_id = self._p(params, "edge_id")
        if not edge_id:
            return (0, None, ("MISSING_PARAM", "edge_id required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {"sql": "SELECT * FROM mu_dependency_edges WHERE edge_id=?", "params": [edge_id]})
        if r[0] != 1:
            return r
        if r[1]["count"] == 0:
            return (0, None, ("NOT_FOUND", "edge not found", 0))
        self.state["stats"]["queries"] += 1
        return (1, {"edge": r[1]["rows"][0]}, None)

    def QueryFromNode(self, params):
        from_node_id = self._p(params, "from_node_id")
        if not from_node_id:
            return (0, None, ("MISSING_PARAM", "from_node_id required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {"sql": "SELECT * FROM mu_dependency_edges WHERE from_node_id=?", "params": [from_node_id]})
        if r[0] != 1:
            return r
        self.state["stats"]["queries"] += 1
        return (1, {"edges": r[1]["rows"], "count": r[1]["count"]}, None)

    def QueryToNode(self, params):
        to_node_id = self._p(params, "to_node_id")
        if not to_node_id:
            return (0, None, ("MISSING_PARAM", "to_node_id required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {"sql": "SELECT * FROM mu_dependency_edges WHERE to_node_id=?", "params": [to_node_id]})
        if r[0] != 1:
            return r
        self.state["stats"]["queries"] += 1
        return (1, {"edges": r[1]["rows"], "count": r[1]["count"]}, None)

    def QueryByType(self, params):
        edge_type = self._p(params, "edge_type")
        if not edge_type:
            return (0, None, ("MISSING_PARAM", "edge_type required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {"sql": "SELECT * FROM mu_dependency_edges WHERE edge_type=?", "params": [edge_type]})
        if r[0] != 1:
            return r
        self.state["stats"]["queries"] += 1
        return (1, {"edges": r[1]["rows"], "count": r[1]["count"]}, None)

    def read_state(self, params):
        return (1, {
            "config": self.state["config"],
            "last_edge_id": self.state["last_edge_id"],
            "stats": self.state["stats"],
        }, None)

    def set_config(self, params):
        for key in ("session_id",):
            val = self._p(params, key)
            if val:
                self.state["config"][key] = val
        return (1, {"config": self.state["config"]}, None)
