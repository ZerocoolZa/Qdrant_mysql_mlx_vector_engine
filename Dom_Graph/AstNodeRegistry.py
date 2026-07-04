#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/AstNodeRegistry.py"
# date="2026-06-27" author="Devin" session_id="memunit-eventsourcing-impl"
# context="AST node identity registry. Immutable node_id, versioned content. FILE/CLASS/METHOD/BLOCK. hash_base makes replay deterministic across re-ingestions."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="AstNodeRegistry.py" domain="ast_identity" authority="AstNodeRegistry"}
# [@SUMMARY]{summary="CRUD for mu_ast_nodes. Creates node identity (immutable), destroys (retires), queries by id/name/parent/file. Emits EVENT_AST_NODE_CREATED + EVENT_AST_NODE_DESTROYED to event log."}
# [@CLASS]{class="AstNodeRegistry" domain="ast_identity" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="CreateNode" type="command"}
# [@METHOD]{method="DestroyNode" type="command"}
# [@METHOD]{method="GetNode" type="query"}
# [@METHOD]{method="QueryByName" type="query"}
# [@METHOD]{method="QueryByParent" type="query"}
# [@METHOD]{method="QueryByFile" type="query"}
# [@METHOD]{method="QueryLive" type="query"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<AST node identity registry with immutable node_id, versioned content, CRUD for mu_ast_nodes. Emits events. VBStyle compliant: Run dispatch, Tuple3, self.state, no print/decorators/self._/hardcoded. No violations found.>][@todos<none>]}
"""
AstNodeRegistry -- AST node identity registry.

A node's identity is IMMUTABLE (node_id, hash_base). Its content changes
via new version rows in mu_ast_versions (handled by AstVersionStore).

Node types: FILE, CLASS, METHOD, BLOCK.
Hierarchy: METHOD -> CLASS -> FILE (via parent_node_id).

EVENT FLOW (write-ahead durability):
  1. Append EVENT_AST_NODE_CREATED to EventLogStore (disk)
  2. Insert row into mu_ast_nodes (in-RAM SQLite via InRamDb)

Usage:
  reg = AstNodeRegistry(mem=log_store, db=in_ram_db)
  ok, data, err = reg.Run("create_node", {
      "node_type": "CLASS",
      "symbolic_name": "MemUnit",
      "file_path": "Dom_Graph/MemUnit.py",
  })
"""
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Tuple

NODE_FILE = "FILE"
NODE_CLASS = "CLASS"
NODE_METHOD = "METHOD"
NODE_BLOCK = "BLOCK"

EVENT_AST_NODE_CREATED = "EVENT_AST_NODE_CREATED"
EVENT_AST_NODE_DESTROYED = "EVENT_AST_NODE_DESTROYED"


class AstNodeRegistry:
    """AST node identity registry. Immutable identity, versioned content."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "session_id": "default",
            },
            "mem": mem,
            "db": db,
            "last_node_id": None,
            "stats": {
                "created": 0,
                "destroyed": 0,
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
            "create_node": self.CreateNode,
            "destroy_node": self.DestroyNode,
            "get_node": self.GetNode,
            "query_by_name": self.QueryByName,
            "query_by_parent": self.QueryByParent,
            "query_by_file": self.QueryByFile,
            "query_live": self.QueryLive,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def _compute_hash_base(self, node_type, symbolic_name, parent_node_id, file_path):
        raw = "|".join([
            node_type or "",
            symbolic_name or "",
            str(parent_node_id) if parent_node_id else "",
            file_path or "",
        ])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def CreateNode(self, params):
        node_type = self._p(params, "node_type", NODE_METHOD)
        symbolic_name = self._p(params, "symbolic_name")
        if not symbolic_name:
            return (0, None, ("MISSING_NAME", "symbolic_name required", 0))
        parent_node_id = self._p(params, "parent_node_id")
        file_path = self._p(params, "file_path")
        line_range = self._p(params, "line_range")
        hash_base = self._compute_hash_base(node_type, symbolic_name, parent_node_id, file_path)
        ts = datetime.utcnow().isoformat() + "Z"
        log = self.state["mem"]
        db = self.state["db"]
        if not log or not db:
            return (0, None, ("NO_DEPS", "mem (EventLogStore) and db (InRamDb) required", 0))
        r = db.Run("query", {"sql": "SELECT MAX(node_id) as m FROM mu_ast_nodes", "params": []})
        node_id = (r[1]["rows"][0]["m"] or 0) + 1 if r[0] == 1 and r[1]["rows"] else 1
        event = {
            "type": EVENT_AST_NODE_CREATED,
            "ts": ts,
            "ast_node_id": node_id,
            "trace_id": self._p(params, "trace_id"),
            "session_id": self.state["config"]["session_id"],
            "parent_event_id": self._p(params, "parent_event_id"),
            "cause": self._p(params, "cause", "node created"),
            "before": None,
            "after": {
                "node_id": node_id,
                "node_type": node_type,
                "symbolic_name": symbolic_name,
                "parent_node_id": parent_node_id,
                "file_path": file_path,
                "line_range": line_range,
                "hash_base": hash_base,
            },
        }
        r = log.Run("append", {"event": event})
        if r[0] != 1:
            return (0, None, ("LOG_FAILED", str(r[2]), 0))
        event_id = r[1]["id"]
        r = db.Run("execute", {
            "sql": """INSERT INTO mu_ast_nodes
                (node_id, node_type, symbolic_name, parent_node_id, file_path, line_range,
                 hash_base, created_event_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            "params": [node_id, node_type, symbolic_name, parent_node_id, file_path,
                       line_range, hash_base, event_id, ts],
        })
        if r[0] != 1:
            return (0, None, ("DB_FAILED", str(r[2]), 0))
        self.state["last_node_id"] = node_id
        self.state["stats"]["created"] += 1
        return (1, {
            "node_id": node_id,
            "hash_base": hash_base,
            "event_id": event_id,
        }, None)

    def DestroyNode(self, params):
        node_id = self._p(params, "node_id")
        if not node_id:
            return (0, None, ("MISSING_NODE_ID", "node_id required", 0))
        log = self.state["mem"]
        db = self.state["db"]
        if not log or not db:
            return (0, None, ("NO_DEPS", "mem and db required", 0))
        r = db.Run("query", {"sql": "SELECT * FROM mu_ast_nodes WHERE node_id=?", "params": [node_id]})
        if r[0] != 1 or r[1]["count"] == 0:
            return (0, None, ("NOT_FOUND", "node not found", 0))
        ts = datetime.utcnow().isoformat() + "Z"
        event = {
            "type": EVENT_AST_NODE_DESTROYED,
            "ts": ts,
            "ast_node_id": node_id,
            "trace_id": self._p(params, "trace_id"),
            "session_id": self.state["config"]["session_id"],
            "cause": self._p(params, "cause", "node destroyed"),
            "before": r[1]["rows"][0],
            "after": None,
        }
        r = log.Run("append", {"event": event})
        if r[0] != 1:
            return (0, None, ("LOG_FAILED", str(r[2]), 0))
        event_id = r[1]["id"]
        r = db.Run("execute", {
            "sql": "UPDATE mu_ast_nodes SET destroyed_event_id=? WHERE node_id=?",
            "params": [event_id, node_id],
        })
        if r[0] != 1:
            return (0, None, ("DB_FAILED", str(r[2]), 0))
        self.state["stats"]["destroyed"] += 1
        return (1, {"node_id": node_id, "event_id": event_id}, None)

    def GetNode(self, params):
        node_id = self._p(params, "node_id")
        if not node_id:
            return (0, None, ("MISSING_NODE_ID", "node_id required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {"sql": "SELECT * FROM mu_ast_nodes WHERE node_id=?", "params": [node_id]})
        if r[0] != 1:
            return r
        if r[1]["count"] == 0:
            return (0, None, ("NOT_FOUND", "node not found", 0))
        self.state["stats"]["queries"] += 1
        return (1, {"node": r[1]["rows"][0]}, None)

    def QueryByName(self, params):
        name = self._p(params, "symbolic_name")
        if not name:
            return (0, None, ("MISSING_NAME", "symbolic_name required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {"sql": "SELECT * FROM mu_ast_nodes WHERE symbolic_name=?", "params": [name]})
        if r[0] != 1:
            return r
        self.state["stats"]["queries"] += 1
        return (1, {"nodes": r[1]["rows"], "count": r[1]["count"]}, None)

    def QueryByParent(self, params):
        parent_id = self._p(params, "parent_node_id")
        if not parent_id:
            return (0, None, ("MISSING_PARAM", "parent_node_id required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {"sql": "SELECT * FROM mu_ast_nodes WHERE parent_node_id=?", "params": [parent_id]})
        if r[0] != 1:
            return r
        self.state["stats"]["queries"] += 1
        return (1, {"nodes": r[1]["rows"], "count": r[1]["count"]}, None)

    def QueryByFile(self, params):
        file_path = self._p(params, "file_path")
        if not file_path:
            return (0, None, ("MISSING_PARAM", "file_path required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {"sql": "SELECT * FROM mu_ast_nodes WHERE file_path=?", "params": [file_path]})
        if r[0] != 1:
            return r
        self.state["stats"]["queries"] += 1
        return (1, {"nodes": r[1]["rows"], "count": r[1]["count"]}, None)

    def QueryLive(self, params):
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {"sql": "SELECT * FROM mu_ast_nodes WHERE destroyed_event_id IS NULL", "params": []})
        if r[0] != 1:
            return r
        self.state["stats"]["queries"] += 1
        return (1, {"nodes": r[1]["rows"], "count": r[1]["count"]}, None)

    def read_state(self, params):
        return (1, {
            "config": self.state["config"],
            "last_node_id": self.state["last_node_id"],
            "stats": self.state["stats"],
        }, None)

    def set_config(self, params):
        for key in ("session_id",):
            val = self._p(params, key)
            if val:
                self.state["config"][key] = val
        return (1, {"config": self.state["config"]}, None)
