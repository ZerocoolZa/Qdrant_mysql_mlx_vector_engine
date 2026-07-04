#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/BclStampStore.py"
# date="2026-06-27" author="Devin" session_id="memunit-eventsourcing-impl"
# context="BCL stamp store. Reasoning layer binding to (node_id, version_id). Class AND method level stamps. Append-only supersede. No-orphan rule enforcement."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="BclStampStore.py" domain="bcl_reasoning" authority="BclStampStore"}
# [@SUMMARY]{summary="CRUD for mu_bcl_stamps. Attaches reasoning stamps to AST nodes at specific versions. Supports FULL/PARTIAL/DELTA scope. Supersede is append-only (never deletes). VerifyNoOrphans enforces P7. Emits EVENT_BCL_STAMP_ATTACHED and EVENT_BCL_STAMP_SUPERSEDED."}
# [@CLASS]{class="BclStampStore" domain="bcl_reasoning" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="AttachStamp" type="command"}
# [@METHOD]{method="SupersedeStamp" type="command"}
# [@METHOD]{method="GetStamp" type="query"}
# [@METHOD]{method="QueryByNode" type="query"}
# [@METHOD]{method="QueryActive" type="query"}
# [@METHOD]{method="VerifyNoOrphans" type="gate"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<BCL stamp store binding reasoning to AST node versions. Append-only supersede, no-orphan rule enforcement. CRUD for mu_bcl_stamps. VBStyle compliant: Run dispatch, Tuple3, self.state. No violations found.>][@todos<none>]}
"""
BclStampStore -- Reasoning layer for the MemUnit event-sourcing system.

BCL stamps bind reasoning (intent_vector, dependency_set, event_refs) to a
specific (node_id, ast_version_id) pair. This means old reasoning is preserved
when code changes -- a new version gets a new stamp, the old stamp is superseded.

Class-level stamps describe class-wide intent. Method-level stamps describe
per-method logic. A method stamp's event_refs[0] MUST be its class stamp's
created_event_id (causality: method reasoning descends from class reasoning).

EVENT FLOW:
  AttachStamp:
    1. Append EVENT_BCL_STAMP_ATTACHED to EventLogStore
    2. INSERT into mu_bcl_stamps (in-RAM)

  SupersedeStamp:
    1. Append EVENT_BCL_STAMP_SUPERSEDED to EventLogStore
    2. UPDATE old stamp: superseded_by=new_id, state_status='STALE'
    3. INSERT new stamp row

No-orphan rule (P7): every live AST node (destroyed_event_id IS NULL) of type
CLASS or METHOD must have at least one ACTIVE, non-superseded stamp at its
current version. VerifyNoOrphans enforces this.

Usage:
  bs = BclStampStore(mem=log, db=db)
  ok, data, err = bs.Run("attach_stamp", {
      "node_id": 1,
      "ast_version_id": 2,
      "trace_id": "tr_001",
      "scope_binding": "FULL",
      "intent_vector": {"primary_goal": "Reasoning state store"},
      "dependency_set": {"writes": ["mu_ast_nodes"]},
      "event_refs": [1],
      "cause": "class reasoning bound",
  })
  # data = {"stamp_id": 1, "event_id": 3}
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Tuple

EVENT_BCL_STAMP_ATTACHED = "EVENT_BCL_STAMP_ATTACHED"
EVENT_BCL_STAMP_SUPERSEDED = "EVENT_BCL_STAMP_SUPERSEDED"

SCOPE_FULL = "FULL"
SCOPE_PARTIAL = "PARTIAL"
SCOPE_DELTA = "DELTA"

STATUS_ACTIVE = "ACTIVE"
STATUS_STALE = "STALE"
STATUS_BROKEN = "BROKEN"
STATUS_DERIVED = "DERIVED"

VALIDATION_UNVERIFIED = "UNVERIFIED"
VALIDATION_VERIFIED = "VERIFIED"
VALIDATION_FAILED = "FAILED"

VALID_SCOPES = (SCOPE_FULL, SCOPE_PARTIAL, SCOPE_DELTA)


class BclStampStore:
    """BCL reasoning stamps. Bind to (node_id, version_id). Append-only supersede."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "session_id": "default",
            },
            "mem": mem,
            "db": db,
            "last_stamp_id": 0,
            "stats": {
                "attached": 0,
                "superseded": 0,
                "queries": 0,
                "orphan_checks": 0,
                "orphans_found": 0,
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
            "query_by_node": self.QueryByNode,
            "query_active": self.QueryActive,
            "verify_no_orphans": self.VerifyNoOrphans,
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
        scope_binding = self._p(params, "scope_binding", SCOPE_FULL)
        intent_vector = self._p(params, "intent_vector", {})
        dependency_set = self._p(params, "dependency_set", {})
        event_refs = self._p(params, "event_refs", [])
        if not node_id or not ast_version_id or not trace_id:
            return (0, None, ("MISSING_PARAM", "node_id, ast_version_id, trace_id required", 0))
        if scope_binding not in VALID_SCOPES:
            return (0, None, ("INVALID_SCOPE", "scope_binding must be FULL/PARTIAL/DELTA", 0))
        coverage_detail = self._p(params, "coverage_detail")
        confidence_score = self._p(params, "confidence_score", 1.0)
        log = self.state["mem"]
        db = self.state["db"]
        if not log or not db:
            return (0, None, ("NO_DEPS", "mem (EventLogStore) and db (InRamDb) required", 0))
        r = db.Run("query", {"sql": "SELECT MAX(stamp_id) as m FROM mu_bcl_stamps", "params": []})
        stamp_id = (r[1]["rows"][0]["m"] or 0) + 1 if r[0] == 1 and r[1]["rows"] else 1
        ts = datetime.utcnow().isoformat() + "Z"
        after = {
            "stamp_id": stamp_id,
            "node_id": node_id,
            "ast_version_id": ast_version_id,
            "trace_id": trace_id,
            "scope_binding": scope_binding,
            "coverage_detail": coverage_detail,
            "intent_vector": intent_vector,
            "dependency_set": dependency_set,
            "event_refs": event_refs,
            "confidence_score": confidence_score,
        }
        event = {
            "type": EVENT_BCL_STAMP_ATTACHED,
            "ts": ts,
            "ast_node_id": node_id,
            "ast_version_after": ast_version_id,
            "trace_id": trace_id,
            "session_id": self.state["config"]["session_id"],
            "parent_event_id": self._p(params, "parent_event_id"),
            "cause": self._p(params, "cause", "stamp attached"),
            "before": None,
            "after": after,
        }
        r = log.Run("append", {"event": event})
        if r[0] != 1:
            return (0, None, ("LOG_FAILED", str(r[2]), 0))
        event_id = r[1]["id"]
        r = db.Run("execute", {
            "sql": """INSERT INTO mu_bcl_stamps
                (stamp_id, node_id, ast_version_id, trace_id, scope_binding,
                 coverage_detail, intent_vector, dependency_set, event_refs,
                 state_status, confidence_score, validation_state,
                 created_event_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, 'UNVERIFIED', ?, ?)""",
            "params": [stamp_id, node_id, ast_version_id, trace_id, scope_binding,
                       json.dumps(coverage_detail) if coverage_detail else None,
                       json.dumps(intent_vector),
                       json.dumps(dependency_set),
                       json.dumps(event_refs),
                       confidence_score, event_id, ts],
        })
        if r[0] != 1:
            return (0, None, ("DB_FAILED", str(r[2]), 0))
        self.state["last_stamp_id"] = stamp_id
        self.state["stats"]["attached"] += 1
        return (1, {
            "stamp_id": stamp_id,
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
        r = db.Run("query", {
            "sql": "SELECT * FROM mu_bcl_stamps WHERE stamp_id=?",
            "params": [old_stamp_id],
        })
        if r[0] != 1 or r[1]["count"] == 0:
            return (0, None, ("NOT_FOUND", "old stamp not found", 0))
        old_row = r[1]["rows"][0]
        node_id = self._p(params, "node_id", old_row["node_id"])
        ast_version_id = self._p(params, "ast_version_id", old_row["ast_version_id"])
        trace_id = self._p(params, "trace_id", old_row["trace_id"])
        scope_binding = self._p(params, "scope_binding", old_row["scope_binding"])
        intent_vector = self._p(params, "intent_vector", json.loads(old_row["intent_vector"]))
        dependency_set = self._p(params, "dependency_set", json.loads(old_row["dependency_set"]))
        event_refs = self._p(params, "event_refs", json.loads(old_row["event_refs"]))
        coverage_detail = self._p(params, "coverage_detail")
        confidence_score = self._p(params, "confidence_score", old_row["confidence_score"])
        r = db.Run("query", {"sql": "SELECT MAX(stamp_id) as m FROM mu_bcl_stamps", "params": []})
        new_stamp_id = (r[1]["rows"][0]["m"] or 0) + 1 if r[0] == 1 and r[1]["rows"] else 1
        ts = datetime.utcnow().isoformat() + "Z"
        after = {
            "old_stamp_id": old_stamp_id,
            "new_stamp_id": new_stamp_id,
            "stamp_id": new_stamp_id,
            "node_id": node_id,
            "ast_version_id": ast_version_id,
            "trace_id": trace_id,
            "scope_binding": scope_binding,
            "coverage_detail": coverage_detail,
            "intent_vector": intent_vector,
            "dependency_set": dependency_set,
            "event_refs": event_refs,
            "confidence_score": confidence_score,
        }
        event = {
            "type": EVENT_BCL_STAMP_SUPERSEDED,
            "ts": ts,
            "ast_node_id": node_id,
            "ast_version_after": ast_version_id,
            "trace_id": trace_id,
            "session_id": self.state["config"]["session_id"],
            "parent_event_id": self._p(params, "parent_event_id"),
            "cause": self._p(params, "cause", "stamp superseded"),
            "before": {"stamp_id": old_stamp_id},
            "after": after,
        }
        r = log.Run("append", {"event": event})
        if r[0] != 1:
            return (0, None, ("LOG_FAILED", str(r[2]), 0))
        event_id = r[1]["id"]
        db.Run("execute", {
            "sql": "UPDATE mu_bcl_stamps SET superseded_by=?, state_status='STALE' WHERE stamp_id=?",
            "params": [new_stamp_id, old_stamp_id],
        })
        r = db.Run("execute", {
            "sql": """INSERT INTO mu_bcl_stamps
                (stamp_id, node_id, ast_version_id, trace_id, scope_binding,
                 coverage_detail, intent_vector, dependency_set, event_refs,
                 state_status, confidence_score, validation_state,
                 created_event_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, 'UNVERIFIED', ?, ?)""",
            "params": [new_stamp_id, node_id, ast_version_id, trace_id, scope_binding,
                       json.dumps(coverage_detail) if coverage_detail else None,
                       json.dumps(intent_vector),
                       json.dumps(dependency_set),
                       json.dumps(event_refs),
                       confidence_score, event_id, ts],
        })
        if r[0] != 1:
            return (0, None, ("DB_FAILED", str(r[2]), 0))
        self.state["last_stamp_id"] = new_stamp_id
        self.state["stats"]["superseded"] += 1
        return (1, {
            "old_stamp_id": old_stamp_id,
            "new_stamp_id": new_stamp_id,
            "event_id": event_id,
        }, None)

    def GetStamp(self, params):
        stamp_id = self._p(params, "stamp_id")
        if not stamp_id:
            return (0, None, ("MISSING_PARAM", "stamp_id required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {
            "sql": "SELECT * FROM mu_bcl_stamps WHERE stamp_id=?",
            "params": [stamp_id],
        })
        if r[0] != 1:
            return r
        if r[1]["count"] == 0:
            return (0, None, ("NOT_FOUND", "stamp not found", 0))
        self.state["stats"]["queries"] += 1
        row = r[1]["rows"][0]
        row = self._decode_json_fields(row)
        return (1, {"stamp": row}, None)

    def QueryByNode(self, params):
        node_id = self._p(params, "node_id")
        if not node_id:
            return (0, None, ("MISSING_PARAM", "node_id required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        include_superseded = self._p(params, "include_superseded", False)
        if include_superseded:
            sql = "SELECT * FROM mu_bcl_stamps WHERE node_id=? ORDER BY stamp_id"
        else:
            sql = "SELECT * FROM mu_bcl_stamps WHERE node_id=? AND superseded_by IS NULL ORDER BY stamp_id"
        r = db.Run("query", {"sql": sql, "params": [node_id]})
        if r[0] != 1:
            return r
        self.state["stats"]["queries"] += 1
        rows = [self._decode_json_fields(row) for row in r[1]["rows"]]
        return (1, {"stamps": rows, "count": len(rows)}, None)

    def QueryActive(self, params):
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        node_id = self._p(params, "node_id")
        version_id = self._p(params, "ast_version_id")
        if node_id and version_id:
            sql = """SELECT * FROM mu_bcl_stamps
                WHERE node_id=? AND ast_version_id=?
                  AND state_status='ACTIVE' AND superseded_by IS NULL
                ORDER BY stamp_id"""
            r = db.Run("query", {"sql": sql, "params": [node_id, version_id]})
        else:
            sql = """SELECT * FROM mu_bcl_stamps
                WHERE state_status='ACTIVE' AND superseded_by IS NULL
                ORDER BY stamp_id"""
            r = db.Run("query", {"sql": sql, "params": []})
        if r[0] != 1:
            return r
        self.state["stats"]["queries"] += 1
        rows = [self._decode_json_fields(row) for row in r[1]["rows"]]
        return (1, {"stamps": rows, "count": len(rows)}, None)

    def VerifyNoOrphans(self, params):
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        self.state["stats"]["orphan_checks"] += 1
        r = db.Run("query", {
            "sql": """SELECT n.node_id, n.symbolic_name, n.node_type
                FROM mu_ast_nodes n
                INNER JOIN mu_ast_versions v ON v.node_id = n.node_id AND v.is_current=1
                LEFT JOIN mu_bcl_stamps s
                  ON s.node_id = n.node_id
                     AND s.state_status = 'ACTIVE'
                     AND s.superseded_by IS NULL
                     AND s.ast_version_id = v.version_id
                WHERE n.destroyed_event_id IS NULL
                  AND s.stamp_id IS NULL
                  AND n.node_type IN ('CLASS', 'METHOD')""",
            "params": [],
        })
        if r[0] != 1:
            return r
        orphans = r[1]["rows"]
        if orphans:
            self.state["stats"]["orphans_found"] += len(orphans)
            names = [row["symbolic_name"] for row in orphans]
            return (0, None, ("ORPHAN_NODES", "nodes without active stamps: " + str(names), 0))
        return (1, {"orphan_count": 0, "checked": True}, None)

    def _decode_json_fields(self, row):
        decoded = dict(row)
        for field in ("intent_vector", "dependency_set", "event_refs", "coverage_detail"):
            val = decoded.get(field)
            if val and isinstance(val, str):
                try:
                    decoded[field] = json.loads(val)
                except (ValueError, TypeError):
                    pass
        return decoded

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
