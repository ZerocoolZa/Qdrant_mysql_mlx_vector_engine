#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/BclStampStore.py"
# date="2026-06-27" author="Devin" session_id="memunit-eventsourcing-impl"
# context="BCL stamp store. Class AND method level reasoning. Binds to (node_id, ast_version_id). intent_vector, dependency_set, event_refs as JSON. Supersede is append-only."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="BclStampStore.py" domain="bcl_reasoning" authority="BclStampStore"}
# [@SUMMARY]{summary="CRUD for mu_bcl_stamps. Class-level + method-level reasoning. Binds stamp to (node_id, version_id). Supersede is append-only (old stamp kept, marked superseded_by). Emits EVENT_BCL_STAMP_ATTACHED + EVENT_BCL_STAMP_SUPERSEDED."}
# [@CLASS]{class="BclStampStore" domain="bcl_reasoning" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="AttachStamp" type="command"}
# [@METHOD]{method="SupersedeStamp" type="command"}
# [@METHOD]{method="GetStamp" type="query"}
# [@METHOD]{method="QueryActiveForNode" type="query"}
# [@METHOD]{method="QueryByTrace" type="query"}
# [@METHOD]{method="QueryClassStamps" type="query"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
"""
BclStampStore -- BCL reasoning stamps. Class AND method level.

A stamp binds reasoning (intent_vector, dependency_set, event_refs) to a
specific (node_id, ast_version_id) pair. When a node gets a new version,
a new stamp is attached and the old one is superseded (append-only).

Class-level stamps: scope=FULL, describe class-wide intent.
Method-level stamps: scope=FULL or PARTIAL, describe per-method logic.
Method stamp event_refs[0] MUST be the class stamp's created_event_id.

EVENT FLOW:
  1. Append EVENT_BCL_STAMP_ATTACHED to EventLogStore
  2. INSERT into mu_bcl_stamps (in-RAM)
  On supersede:
  1. Append EVENT_BCL_STAMP_SUPERSEDED
  2. UPDATE old stamp superseded_by=new_id
  3. INSERT new stamp

Usage:
  bs = BclStampStore(mem=log, db=db)
  ok, data, err = bs.Run("attach_stamp", {
      "node_id": 1,
      "ast_version_id": 2,
      "trace_id": "tr_abc",
      "scope_binding": "FULL",
      "intent_vector": {"primary_goal": "..."},
      "dependency_set": {"reads": [], "writes": []},
      "event_refs": [3],
  })
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Tuple

SCOPE_FULL = "FULL"
SCOPE_PARTIAL = "PARTIAL"
SCOPE_DELTA = "DELTA"
STATUS_ACTIVE = "ACTIVE"
STATUS_STALE = "STALE"
STATUS_BROKEN = "BROKEN"
STATUS_DERIVED = "DERIVED"
EVENT_BCL_STAMP_ATTACHED = "EVENT_BCL_STAMP_ATTACHED"
EVENT_BCL_STAMP_SUPERSEDED = "EVENT_BCL_STAMP_SUPERSEDED"


class BclStampStore:
    """BCL reasoning stamps. Class + method level. Append-only supersede."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "session_id": "default",
            },
            "mem": mem,
            "db": db,
            "last_stamp_id": None,
            "stats": {
                "attached": 0,
                "superseded": 0,
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
            "attach_stamp": self.AttachStamp,
            "supersede_stamp": self.SupersedeStamp,
            "get_stamp": self.GetStamp,
            "query_active_for_node": self.QueryActiveForNode,
            "query_by_trace": self.QueryByTrace,
            "query_class_stamps": self.QueryClassStamps,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def AttachStamp(self, params):
        node_id = self._p(params, "node_id")
        ast_version_id = self._p(params, "ast_version_id")
        trace_id = self._p(params, "trace_id")
        if not node_id or not ast_version_id or not trace_id:
            return (0, None, ("MISSING_PARAM", "node_id, ast_version_id, trace_id required", 0))
        scope_binding = self._p(params, "scope_binding", SCOPE_FULL)
        coverage_detail = self._p(params, "coverage_detail")
        intent_vector = self._p(params, "intent_vector", {})
        dependency_set = self._p(params, "dependency_set", {})
        event_refs = self._p(params, "event_refs", [])
        confidence_score = self._p(params, "confidence_score", 1.0)
        log = self.state["mem"]
        db = self.state["db"]
        if not log or not db:
            return (0, None, ("NO_DEPS", "mem and db required", 0))
        r = db.Run("query", {"sql": "SELECT MAX(stamp_id) as m FROM mu_bcl_stamps", "params": []})
        stamp_id = (r[1]["rows"][0]["m"] or 0) + 1 if r[0] == 1 and r[1]["rows"] else 1
        ts = datetime.utcnow().isoformat() + "Z"
        event = {
            "type": EVENT_BCL_STAMP_ATTACHED,
            "ts": ts,
            "ast_node_id": node_id,
            "ast_version_after": ast_version_id,
            "trace_id": trace_id,
            "session_id": self.state["config"]["session_id"],
            "cause": self._p(params, "cause", "stamp attached"),
            "before": None,
            "after": {
                "stamp_id": stamp_id,
                "scope_binding": scope_binding,
                "intent_vector": intent_vector,
                "dependency_set": dependency_set,
                "event_refs": event_refs,
            },
        }
        r = log.Run("append", {"event": event})
        if r[0] != 1:
            return (0, None, ("LOG_FAILED", str(r[2]), 0))
        event_id = r[1]["id"]
        r = db.Run("execute", {
            "sql": """INSERT INTO mu_bcl_stamps
                (stamp_id, node_id, ast_version_id, trace_id, scope_binding, coverage_detail,
                 intent_vector, dependency_set, event_refs, state_status,
                 confidence_score, validation_state, created_event_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, 'UNVERIFIED', ?, ?)""",
            "params": [stamp_id, node_id, ast_version_id, trace_id, scope_binding,
                       coverage_detail, json.dumps(intent_vector),
                       json.dumps(dependency_set), json.dumps(event_refs),
                       confidence_score, event_id, ts],
        })
        if r[0] != 1:
            return (0, None, ("DB_FAILED", str(r[2]), 0))
        self.state["last_stamp_id"] = stamp_id
        self.state["stats"]["attached"] += 1
        return (1, {
            "stamp_id": stamp_id,
            "node_id": node_id,
            "trace_id": trace_id,
            "event_id": event_id,
        }, None)

    def SupersedeStamp(self, params):
        old_stamp_id = self._p(params, "old_stamp_id")
        if not old_stamp_id:
            return (0, None, ("MISSING_PARAM", "old_stamp_id required", 0))
        log = self.state["mem"]
        db = self.state["db"]
        if not log or not db:
            return (0, None, ("NO_DEPS", "mem and db required", 0))
        r = db.Run("query", {"sql": "SELECT * FROM mu_bcl_stamps WHERE stamp_id=?", "params": [old_stamp_id]})
        if r[0] != 1 or r[1]["count"] == 0:
            return (0, None, ("NOT_FOUND", "old stamp not found", 0))
        old = r[1]["rows"][0]
        attach_params = dict(params)
        attach_params.pop("old_stamp_id", None)
        attach_params.setdefault("node_id", old["node_id"])
        attach_params.setdefault("trace_id", old["trace_id"])
        r2 = self.AttachStamp(attach_params)
        if r2[0] != 1:
            return r2
        new_stamp_id = r2[1]["stamp_id"]
        ts = datetime.utcnow().isoformat() + "Z"
        event = {
            "type": EVENT_BCL_STAMP_SUPERSEDED,
            "ts": ts,
            "trace_id": old["trace_id"],
            "session_id": self.state["config"]["session_id"],
            "cause": self._p(params, "cause", "stamp superseded"),
            "before": {"old_stamp_id": old_stamp_id},
            "after": {"old_stamp_id": old_stamp_id, "new_stamp_id": new_stamp_id},
        }
        log.Run("append", {"event": event})
        db.Run("execute", {
            "sql": "UPDATE mu_bcl_stamps SET superseded_by=?, state_status='STALE' WHERE stamp_id=?",
            "params": [new_stamp_id, old_stamp_id],
        })
        self.state["stats"]["superseded"] += 1
        return (1, {"old_stamp_id": old_stamp_id, "new_stamp_id": new_stamp_id}, None)

    def GetStamp(self, params):
        stamp_id = self._p(params, "stamp_id")
        if not stamp_id:
            return (0, None, ("MISSING_PARAM", "stamp_id required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {"sql": "SELECT * FROM mu_bcl_stamps WHERE stamp_id=?", "params": [stamp_id]})
        if r[0] != 1:
            return r
        if r[1]["count"] == 0:
            return (0, None, ("NOT_FOUND", "stamp not found", 0))
        self.state["stats"]["queries"] += 1
        return (1, {"stamp": r[1]["rows"][0]}, None)

    def QueryActiveForNode(self, params):
        node_id = self._p(params, "node_id")
        if not node_id:
            return (0, None, ("MISSING_PARAM", "node_id required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {
            "sql": """SELECT * FROM mu_bcl_stamps
                WHERE node_id=? AND state_status='ACTIVE' AND superseded_by IS NULL""",
            "params": [node_id],
        })
        if r[0] != 1:
            return r
        self.state["stats"]["queries"] += 1
        return (1, {"stamps": r[1]["rows"], "count": r[1]["count"]}, None)

    def QueryByTrace(self, params):
        trace_id = self._p(params, "trace_id")
        if not trace_id:
            return (0, None, ("MISSING_PARAM", "trace_id required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {"sql": "SELECT * FROM mu_bcl_stamps WHERE trace_id=?", "params": [trace_id]})
        if r[0] != 1:
            return r
        self.state["stats"]["queries"] += 1
        return (1, {"stamps": r[1]["rows"], "count": r[1]["count"]}, None)

    def QueryClassStamps(self, params):
        class_node_id = self._p(params, "class_node_id")
        if not class_node_id:
            return (0, None, ("MISSING_PARAM", "class_node_id required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {
            "sql": """SELECT * FROM mu_bcl_stamps
                WHERE node_id=? AND state_status='ACTIVE' AND superseded_by IS NULL""",
            "params": [class_node_id],
        })
        if r[0] != 1:
            return r
        self.state["stats"]["queries"] += 1
        return (1, {"stamps": r[1]["rows"], "count": r[1]["count"]}, None)

    def read_state(self, params):
        return (1, {
            "config": self.state["config"],
            "last_stamp_id": self.state["last_stamp_id"],
            "stats": self.state["stats"],
        }, None)

    def set_config(self, params):
        for key in ("session_id",):
            val = self._p(params, key)
            if val:
                self.state["config"][key] = val
        return (1, {"config": self.state["config"]}, None)
