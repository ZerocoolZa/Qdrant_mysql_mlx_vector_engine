#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/SnapshotStore.py"
# date="2026-06-27" author="Devin" session_id="memunit-eventsourcing-impl"
# context="Materialized rebuild checkpoints. Cache, not truth. Snapshots can be dropped and rebuilt from event log."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="SnapshotStore.py" domain="rebuild_cache" authority="SnapshotStore"}
# [@SUMMARY]{summary="Take + hydrate mu_snapshots. Materialized rebuild checkpoints to avoid replaying from epoch. Cache, not truth - droppable."}
# [@CLASS]{class="SnapshotStore" domain="rebuild_cache" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="TakeSnapshot" type="command"}
# [@METHOD]{method="GetLatestBefore" type="query"}
# [@METHOD]{method="Hydrate" type="query"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Materialized rebuild checkpoints for MemUnit event-sourcing. Cache not truth. Take/hydrate snapshots. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}
"""
SnapshotStore -- Materialized rebuild checkpoints (CACHE, not truth).

Snapshots capture the in-RAM state at a given event id so that RebuildAt
doesn't have to replay from epoch. They are CACHE - any snapshot can be
dropped and rebuilt from the event log.

EVENT FLOW:
  1. Append EVENT_CHECKPOINT to EventLogStore
  2. INSERT into mu_snapshots (in-RAM)
  3. Optionally write snapshot file to disk

Usage:
  ss = SnapshotStore(mem=log, db=db)
  ok, data, err = ss.Run("take_snapshot", {"event_id": 1000})
  ok, data, err = ss.Run("get_latest_before", {"event_id": 1500})
"""
import json
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Tuple

EVENT_CHECKPOINT = "EVENT_CHECKPOINT"


class SnapshotStore:
    """Materialized rebuild checkpoints. Cache, not truth."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "session_id": "default",
                "snapshot_dir": "memunit_snapshots",
            },
            "mem": mem,
            "db": db,
            "last_snapshot_id": None,
            "stats": {
                "taken": 0,
                "hydrated": 0,
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
            "take_snapshot": self.TakeSnapshot,
            "get_latest_before": self.GetLatestBefore,
            "hydrate": self.Hydrate,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def TakeSnapshot(self, params):
        event_id = self._p(params, "event_id")
        if event_id is None:
            return (0, None, ("MISSING_PARAM", "event_id required", 0))
        log = self.state["mem"]
        db = self.state["db"]
        if not log or not db:
            return (0, None, ("NO_DEPS", "mem and db required", 0))
        ts = datetime.utcnow().isoformat() + "Z"
        r = db.Run("query", {"sql": "SELECT node_id, version_id FROM mu_ast_versions WHERE is_current=1", "params": []})
        ast_versions = {str(row["node_id"]): row["version_id"] for row in r[1]["rows"]} if r[0] == 1 else {}
        r = db.Run("query", {"sql": "SELECT stamp_id FROM mu_bcl_stamps WHERE state_status='ACTIVE' AND superseded_by IS NULL", "params": []})
        active_stamps = [row["stamp_id"] for row in r[1]["rows"]] if r[0] == 1 else []
        r = db.Run("query", {"sql": "SELECT DISTINCT trace_id FROM mu_trace_steps", "params": []})
        trace_ids = [row["trace_id"] for row in r[1]["rows"]] if r[0] == 1 else []
        r = db.Run("query", {"sql": "SELECT edge_id FROM mu_dependency_edges WHERE validity_state='VALID'", "params": []})
        edge_ids = [row["edge_id"] for row in r[1]["rows"]] if r[0] == 1 else []
        content = json.dumps({
            "ast_versions": ast_versions,
            "active_stamps": active_stamps,
            "trace_ids": trace_ids,
            "edge_ids": edge_ids,
        }, sort_keys=True)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        snapshot_file = self.state["config"]["snapshot_dir"] + "/snap_" + str(event_id).zfill(6) + ".json"
        event = {
            "type": EVENT_CHECKPOINT,
            "ts": ts,
            "session_id": self.state["config"]["session_id"],
            "cause": "checkpoint at event " + str(event_id),
            "before": None,
            "after": {"snapshot_file": snapshot_file, "content_hash": content_hash},
        }
        r = log.Run("append", {"event": event})
        if r[0] != 1:
            return (0, None, ("LOG_FAILED", str(r[2]), 0))
        r = db.Run("execute", {
            "sql": """INSERT INTO mu_snapshots
                (taken_at_event_id, taken_at_ts, snapshot_file,
                 ast_node_versions, active_stamps, trace_ids,
                 dependency_edge_ids, content_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            "params": [event_id, ts, snapshot_file,
                       json.dumps(ast_versions), json.dumps(active_stamps),
                       json.dumps(trace_ids), json.dumps(edge_ids),
                       content_hash, ts],
        })
        if r[0] != 1:
            return (0, None, ("DB_FAILED", str(r[2]), 0))
        snapshot_id = r[1]["lastrowid"]
        self.state["last_snapshot_id"] = snapshot_id
        self.state["stats"]["taken"] += 1
        return (1, {
            "snapshot_id": snapshot_id,
            "event_id": event_id,
            "content_hash": content_hash,
        }, None)

    def GetLatestBefore(self, params):
        event_id = self._p(params, "event_id")
        if event_id is None:
            return (0, None, ("MISSING_PARAM", "event_id required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {
            "sql": "SELECT * FROM mu_snapshots WHERE taken_at_event_id <= ? ORDER BY taken_at_event_id DESC LIMIT 1",
            "params": [event_id],
        })
        if r[0] != 1:
            return r
        if r[1]["count"] == 0:
            return (1, {"snapshot": None, "found": False}, None)
        self.state["stats"]["queries"] += 1
        return (1, {"snapshot": r[1]["rows"][0], "found": True}, None)

    def Hydrate(self, params):
        snapshot_id = self._p(params, "snapshot_id")
        if not snapshot_id:
            return (0, None, ("MISSING_PARAM", "snapshot_id required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        r = db.Run("query", {"sql": "SELECT * FROM mu_snapshots WHERE snapshot_id=?", "params": [snapshot_id]})
        if r[0] != 1 or r[1]["count"] == 0:
            return (0, None, ("NOT_FOUND", "snapshot not found", 0))
        snap = r[1]["rows"][0]
        ast_versions = json.loads(snap["ast_node_versions"]) if snap["ast_node_versions"] else {}
        active_stamps = json.loads(snap["active_stamps"]) if snap["active_stamps"] else []
        trace_ids = json.loads(snap["trace_ids"]) if snap["trace_ids"] else []
        edge_ids = json.loads(snap["dependency_edge_ids"]) if snap["dependency_edge_ids"] else []
        self.state["stats"]["hydrated"] += 1
        return (1, {
            "snapshot_id": snapshot_id,
            "taken_at_event_id": snap["taken_at_event_id"],
            "ast_versions": ast_versions,
            "active_stamps": active_stamps,
            "trace_ids": trace_ids,
            "edge_ids": edge_ids,
        }, None)

    def read_state(self, params):
        return (1, {
            "config": self.state["config"],
            "last_snapshot_id": self.state["last_snapshot_id"],
            "stats": self.state["stats"],
        }, None)

    def set_config(self, params):
        for key in ("session_id", "snapshot_dir"):
            val = self._p(params, key)
            if val:
                self.state["config"][key] = val
        return (1, {"config": self.state["config"]}, None)
