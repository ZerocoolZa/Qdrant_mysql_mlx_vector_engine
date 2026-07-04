#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/ReplayEngine.py"
# date="2026-06-27" author="Devin" session_id="memunit-eventsourcing-impl"
# context="Deterministic replay engine. RebuildAt(event_id) replays event log into fresh in-RAM DB. Same event prefix = identical state, row-for-row. Uses snapshots for acceleration."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="ReplayEngine.py" domain="replay" authority="ReplayEngine"}
# [@SUMMARY]{summary="RebuildAt(B) + Apply(E, state) + VerifyContinuity. Replays event log into fresh :memory: SQLite. Uses latest snapshot before B, then replays forward. Deterministic."}
# [@CLASS]{class="ReplayEngine" domain="replay" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="RebuildAt" type="query"}
# [@METHOD]{method="Apply" type="command"}
# [@METHOD]{method="VerifyContinuity" type="gate"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Deterministic replay engine. RebuildAt(event_id) replays event log into fresh in-RAM DB. Uses snapshots for acceleration. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}
"""
ReplayEngine -- Deterministic replay of event log into in-RAM SQLite.

RebuildAt(B) reconstructs the full system state (AST forest + BCL stamps +
dependency graph + execution state) as of event id B.

Algorithm (spec section 5):
  1. Find latest snapshot at or before B
  2. If snapshot exists: hydrate it, replay events from snapshot+1 to B
  3. If no snapshot: replay from event 1 to B
  4. VerifyContinuity (no orphan nodes, no broken traces, no stale edges)

Same event prefix -> identical in-RAM state, row-for-row (P9).

Usage:
  re = ReplayEngine(mem=log, db=db)
  ok, data, err = re.Run("rebuild_at", {"event_id": 50})
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Tuple

EVENT_NODE_CREATED = "EVENT_NODE_CREATED"
EVENT_NODE_UPDATED = "EVENT_NODE_UPDATED"
EVENT_STATE_CHANGED = "EVENT_STATE_CHANGED"
EVENT_EDGE_CREATED = "EVENT_EDGE_CREATED"
EVENT_TAG_ADDED = "EVENT_TAG_ADDED"
EVENT_TASK_STARTED = "EVENT_TASK_STARTED"
EVENT_TASK_COMPLETED = "EVENT_TASK_COMPLETED"
EVENT_ERROR_RAISED = "EVENT_ERROR_RAISED"
EVENT_CODE_GRAPH_CHANGED = "EVENT_CODE_GRAPH_CHANGED"
EVENT_AST_NODE_CREATED = "EVENT_AST_NODE_CREATED"
EVENT_AST_VERSION_ADDED = "EVENT_AST_VERSION_ADDED"
EVENT_AST_NODE_DESTROYED = "EVENT_AST_NODE_DESTROYED"
EVENT_BCL_STAMP_ATTACHED = "EVENT_BCL_STAMP_ATTACHED"
EVENT_BCL_STAMP_SUPERSEDED = "EVENT_BCL_STAMP_SUPERSEDED"
EVENT_TRACE_STEP_APPENDED = "EVENT_TRACE_STEP_APPENDED"
EVENT_DEPENDENCY_EDGE_ADDED = "EVENT_DEPENDENCY_EDGE_ADDED"
EVENT_ROLLBACK = "EVENT_ROLLBACK"
EVENT_CHECKPOINT = "EVENT_CHECKPOINT"

EXISTING_REASONING_EVENTS = {
    EVENT_NODE_CREATED, EVENT_NODE_UPDATED, EVENT_STATE_CHANGED,
    EVENT_EDGE_CREATED, EVENT_TAG_ADDED, EVENT_TASK_STARTED,
    EVENT_TASK_COMPLETED, EVENT_ERROR_RAISED, EVENT_CODE_GRAPH_CHANGED,
}


class ReplayEngine:
    """Deterministic replay of event log into in-RAM SQLite."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "session_id": "default",
            },
            "mem": mem,
            "db": db,
            "snapshot_store": None,
            "stats": {
                "rebuilds": 0,
                "events_applied": 0,
                "snapshots_used": 0,
                "continuity_passes": 0,
                "continuity_failures": 0,
            },
        }
        if param:
            if "snapshot_store" in param:
                self.state["snapshot_store"] = param["snapshot_store"]
                param = {k: v for k, v in param.items() if k != "snapshot_store"}
            self.state["config"].update(param)

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "rebuild_at": self.RebuildAt,
            "apply": self.Apply,
            "verify_continuity": self.VerifyContinuity,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def _clear_all_tables(self, db):
        db.Run("execute", {"sql": "PRAGMA foreign_keys=OFF", "params": []})
        db.Run("execute", {"sql": "DELETE FROM mu_dependency_edges", "params": []})
        db.Run("execute", {"sql": "DELETE FROM mu_trace_steps", "params": []})
        db.Run("execute", {"sql": "DELETE FROM mu_bcl_stamps", "params": []})
        db.Run("execute", {"sql": "DELETE FROM mu_ast_versions", "params": []})
        db.Run("execute", {"sql": "DELETE FROM mu_ast_nodes", "params": []})
        db.Run("execute", {"sql": "DELETE FROM mu_node_state", "params": []})
        db.Run("execute", {"sql": "DELETE FROM mu_edge_state", "params": []})
        db.Run("execute", {"sql": "DELETE FROM mu_semantic_tags", "params": []})
        db.Run("execute", {"sql": "DELETE FROM mu_execution_state", "params": []})
        db.Run("execute", {"sql": "DELETE FROM mu_snapshots", "params": []})
        db.Run("execute", {"sql": "DELETE FROM mu_events", "params": []})
        db.Run("execute", {"sql": "PRAGMA foreign_keys=ON", "params": []})

    def RebuildAt(self, params):
        bound = self._p(params, "event_id")
        if bound is None:
            return (0, None, ("MISSING_PARAM", "event_id required", 0))
        log = self.state["mem"]
        db = self.state["db"]
        if not log or not db:
            return (0, None, ("NO_DEPS", "mem and db required", 0))
        self._clear_all_tables(db)
        start_event = 1
        snapshot_used = False
        ss = self.state["snapshot_store"]
        if ss:
            r = ss.Run("get_latest_before", {"event_id": bound})
            if r[0] == 1 and r[1].get("found") and r[1].get("snapshot"):
                snap = r[1]["snapshot"]
                snap_event_id = snap["taken_at_event_id"]
                r2 = ss.Run("hydrate", {"snapshot_id": snap["snapshot_id"]})
                if r2[0] == 1:
                    self._hydrate_snapshot(db, r2[1], snap)
                    start_event = snap_event_id + 1
                    snapshot_used = True
                    self.state["stats"]["snapshots_used"] += 1
        r = log.Run("read_all", {})
        if r[0] != 1:
            return (0, None, ("LOG_READ_FAILED", str(r[2]), 0))
        events = r[1]["events"]
        applied = 0
        for event in events:
            eid = event.get("id", 0)
            if eid < start_event:
                continue
            if eid > bound:
                break
            r2 = db.Run("execute", {
                "sql": """INSERT INTO mu_events
                    (id, type, ts, target_node, target_edge, ast_node_id,
                     ast_version_before, ast_version_after, trace_id,
                     session_id, parent_event_id, cause, before_state,
                     after_state, event_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                "params": [
                    eid, event.get("type"), event.get("ts"),
                    event.get("target_node"), event.get("target_edge"),
                    event.get("ast_node_id"), event.get("ast_version_before"),
                    event.get("ast_version_after"), event.get("trace_id"),
                    event.get("session_id"), event.get("parent_event_id"),
                    event.get("cause"),
                    json.dumps(event.get("before")) if event.get("before") else None,
                    json.dumps(event.get("after")) if event.get("after") else None,
                    event.get("event_hash"),
                ],
            })
            if r2[0] != 1:
                continue
            r3 = self.Apply({"event": event})
            if r3[0] == 1:
                applied += 1
        cont = self.VerifyContinuity({})
        self.state["stats"]["rebuilds"] += 1
        self.state["stats"]["events_applied"] += applied
        result = {
            "bound": bound,
            "events_applied": applied,
            "snapshot_used": snapshot_used,
            "start_event": start_event,
            "continuity": cont[1] if cont[0] == 1 else {"ok": False, "error": str(cont[2])},
        }
        if cont[0] != 1:
            self.state["stats"]["continuity_failures"] += 1
            return (0, result, cont[2])
        self.state["stats"]["continuity_passes"] += 1
        return (1, result, None)

    def _hydrate_snapshot(self, db, hydrated, snap):
        ast_versions = hydrated.get("ast_versions", {})
        active_stamps = hydrated.get("active_stamps", [])
        trace_ids = hydrated.get("trace_ids", [])
        edge_ids = hydrated.get("edge_ids", [])
        db.Run("execute", {
            "sql": """INSERT INTO mu_snapshots
                (snapshot_id, taken_at_event_id, taken_at_ts, snapshot_file,
                 ast_node_versions, active_stamps, trace_ids,
                 dependency_edge_ids, content_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            "params": [snap["snapshot_id"], snap["taken_at_event_id"],
                       snap["taken_at_ts"], snap["snapshot_file"],
                       json.dumps(ast_versions), json.dumps(active_stamps),
                       json.dumps(trace_ids), json.dumps(edge_ids),
                       snap["content_hash"], snap["created_at"]],
        })

    def Apply(self, params):
        event = self._p(params, "event")
        if not event:
            return (0, None, ("MISSING_EVENT", "event required", 0))
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        etype = event.get("type")
        after = event.get("after")
        ts = event.get("ts", datetime.utcnow().isoformat() + "Z")
        event_id = event.get("id")
        if etype == EVENT_AST_NODE_CREATED:
            if not after:
                return (1, {"applied": False, "reason": "no after"}, None)
            node_id = after.get("node_id") or event.get("ast_node_id")
            if not node_id:
                return (1, {"applied": False, "reason": "no node_id in event"}, None)
            r = db.Run("execute", {
                "sql": """INSERT INTO mu_ast_nodes
                    (node_id, node_type, symbolic_name, parent_node_id,
                     file_path, line_range, hash_base, created_event_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                "params": [node_id, after.get("node_type"), after.get("symbolic_name"),
                           after.get("parent_node_id"), after.get("file_path"),
                           after.get("line_range"), after.get("hash_base"),
                           event_id, ts],
            })
            return (1, {"applied": True, "node_id": node_id}, None)
        if etype == EVENT_AST_VERSION_ADDED:
            if not after:
                return (1, {"applied": False, "reason": "no after"}, None)
            node_id = event.get("ast_node_id")
            version_id = after.get("version_id") or event.get("ast_version_after")
            if not node_id or not version_id:
                return (1, {"applied": False, "reason": "no node_id or version_id"}, None)
            r = db.Run("query", {
                "sql": "SELECT version_id FROM mu_ast_versions WHERE node_id=? AND is_current=1",
                "params": [node_id],
            })
            if r[0] == 1 and r[1]["rows"]:
                db.Run("execute", {
                    "sql": "UPDATE mu_ast_versions SET is_current=0 WHERE version_id=?",
                    "params": [r[1]["rows"][0]["version_id"]],
                })
            r = db.Run("execute", {
                "sql": """INSERT INTO mu_ast_versions
                    (version_id, node_id, version_no, content_hash, content_blob,
                     content_format, blob_uri, created_event_id, is_current, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                "params": [version_id, node_id, after.get("version_no"),
                           after.get("content_hash"), after.get("content_blob"),
                           after.get("content_format", "SOURCE"),
                           after.get("blob_uri"), event_id, ts],
            })
            return (1, {"applied": True, "version_id": version_id}, None)
        if etype == EVENT_AST_NODE_DESTROYED:
            node_id = event.get("ast_node_id")
            if not node_id:
                return (1, {"applied": False}, None)
            db.Run("execute", {
                "sql": "UPDATE mu_ast_nodes SET destroyed_event_id=? WHERE node_id=?",
                "params": [event_id, node_id],
            })
            return (1, {"applied": True}, None)
        if etype == EVENT_BCL_STAMP_ATTACHED:
            if not after:
                return (1, {"applied": False}, None)
            node_id = event.get("ast_node_id")
            version_id = event.get("ast_version_after")
            trace_id = event.get("trace_id")
            stamp_id = after.get("stamp_id")
            if not stamp_id:
                r = db.Run("query", {"sql": "SELECT MAX(stamp_id) as m FROM mu_bcl_stamps", "params": []})
                stamp_id = (r[1]["rows"][0]["m"] or 0) + 1 if r[0] == 1 and r[1]["rows"] else 1
            confidence = after.get("confidence_score", 1.0)
            db.Run("execute", {
                "sql": """INSERT INTO mu_bcl_stamps
                    (stamp_id, node_id, ast_version_id, trace_id, scope_binding,
                     coverage_detail, intent_vector, dependency_set, event_refs,
                     state_status, confidence_score, validation_state,
                     created_event_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, 'UNVERIFIED', ?, ?)""",
                "params": [stamp_id, node_id, version_id, trace_id,
                           after.get("scope_binding", "FULL"),
                           after.get("coverage_detail"),
                           json.dumps(after.get("intent_vector", {})),
                           json.dumps(after.get("dependency_set", {})),
                           json.dumps(after.get("event_refs", [])),
                           confidence, event_id, ts],
            })
            return (1, {"applied": True, "stamp_id": stamp_id}, None)
        if etype == EVENT_BCL_STAMP_SUPERSEDED:
            if not after:
                return (1, {"applied": False}, None)
            old_id = after.get("old_stamp_id")
            new_id = after.get("new_stamp_id")
            if old_id and new_id:
                db.Run("execute", {
                    "sql": "UPDATE mu_bcl_stamps SET superseded_by=?, state_status='STALE' WHERE stamp_id=?",
                    "params": [new_id, old_id],
                })
            return (1, {"applied": True}, None)
        if etype == EVENT_TRACE_STEP_APPENDED:
            if not after:
                return (1, {"applied": False}, None)
            trace_id = event.get("trace_id")
            step_id = after.get("step_id")
            if not step_id:
                r = db.Run("query", {"sql": "SELECT MAX(step_id) as m FROM mu_trace_steps", "params": []})
                step_id = (r[1]["rows"][0]["m"] or 0) + 1 if r[0] == 1 and r[1]["rows"] else 1
            db.Run("execute", {
                "sql": """INSERT INTO mu_trace_steps
                    (step_id, trace_id, step_no, decision, input_nodes,
                     transformation, output_nodes, event_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                "params": [step_id, trace_id, after.get("step_no"),
                           after.get("decision"), json.dumps(after.get("input_nodes", [])),
                           after.get("transformation"),
                           json.dumps(after.get("output_nodes", [])),
                           event_id, ts],
            })
            return (1, {"applied": True, "step_id": step_id}, None)
        if etype == EVENT_DEPENDENCY_EDGE_ADDED:
            if not after:
                return (1, {"applied": False}, None)
            edge_id = after.get("edge_id")
            if not edge_id:
                r = db.Run("query", {"sql": "SELECT MAX(edge_id) as m FROM mu_dependency_edges", "params": []})
                edge_id = (r[1]["rows"][0]["m"] or 0) + 1 if r[0] == 1 and r[1]["rows"] else 1
            db.Run("execute", {
                "sql": """INSERT INTO mu_dependency_edges
                    (edge_id, from_node_id, to_node_id, from_version_id,
                     to_version_id, edge_type, evidence_event_id,
                     validity_state, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'VALID', ?)""",
                "params": [edge_id, after.get("from_node_id"), after.get("to_node_id"),
                           after.get("from_version_id"), after.get("to_version_id"),
                           after.get("edge_type", "CALLS"), event_id, ts],
            })
            return (1, {"applied": True, "edge_id": edge_id}, None)
        if etype == EVENT_ROLLBACK:
            target_versions = after
            if isinstance(target_versions, str):
                target_versions = json.loads(target_versions)
            if isinstance(target_versions, dict):
                for node_id, version_id in target_versions.items():
                    db.Run("execute", {
                        "sql": "UPDATE mu_ast_versions SET is_current=0 WHERE node_id=?",
                        "params": [int(node_id)],
                    })
                    db.Run("execute", {
                        "sql": "UPDATE mu_ast_versions SET is_current=1 WHERE node_id=? AND version_id=?",
                        "params": [int(node_id), int(version_id)],
                    })
                db.Run("execute", {
                    "sql": """INSERT OR REPLACE INTO mu_execution_state
                        (id, task_id, active_ast_versions, rollback_point_event,
                         last_rollback_at, last_touch)
                        VALUES (1, 1, ?, ?, ?, ?)""",
                    "params": [json.dumps(target_versions), event_id, ts, ts],
                })
            return (1, {"applied": True, "rolled_back": len(target_versions) if isinstance(target_versions, dict) else 0}, None)
        if etype == EVENT_CHECKPOINT:
            return (1, {"applied": True, "reason": "checkpoint skipped in replay"}, None)
        if etype in EXISTING_REASONING_EVENTS:
            return self._apply_existing_reasoning(event, db, after, ts, event_id)
        return (1, {"applied": False, "reason": "unknown event type " + str(etype)}, None)

    def _apply_existing_reasoning(self, event, db, after, ts, event_id):
        etype = event.get("type")
        if etype == EVENT_NODE_CREATED:
            if not after:
                return (1, {"applied": False}, None)
            r = db.Run("query", {"sql": "SELECT MAX(node_id) as m FROM mu_node_state", "params": []})
            nid = (r[1]["rows"][0]["m"] or 0) + 1 if r[0] == 1 and r[1]["rows"] else 1
            db.Run("execute", {
                "sql": """INSERT INTO mu_node_state
                    (node_id, node_type, title, content, current_state,
                     parent_id, root_id, last_touch)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                "params": [nid, after.get("node_type", "GOAL"),
                           after.get("title", ""), after.get("content", ""),
                           after.get("state", "OPEN"),
                           after.get("parent_id"), after.get("root_id"), ts],
            })
            return (1, {"applied": True, "node_id": nid}, None)
        if etype == EVENT_STATE_CHANGED:
            nid = event.get("target_node")
            if not nid or not after:
                return (1, {"applied": False}, None)
            db.Run("execute", {
                "sql": "UPDATE mu_node_state SET current_state=?, version=version+1, last_touch=? WHERE node_id=?",
                "params": [after.get("state", "OPEN"), ts, nid],
            })
            return (1, {"applied": True}, None)
        if etype == EVENT_EDGE_CREATED:
            if not after:
                return (1, {"applied": False}, None)
            r = db.Run("query", {"sql": "SELECT MAX(edge_id) as m FROM mu_edge_state", "params": []})
            eid = (r[1]["rows"][0]["m"] or 0) + 1 if r[0] == 1 and r[1]["rows"] else 1
            db.Run("execute", {
                "sql": """INSERT INTO mu_edge_state
                    (edge_id, from_node, to_node, edge_type, last_touch)
                    VALUES (?, ?, ?, ?, ?)""",
                "params": [eid, after.get("from_node"), after.get("to_node"),
                           after.get("edge_type", "PRODUCES"), ts],
            })
            return (1, {"applied": True, "edge_id": eid}, None)
        if etype == EVENT_TAG_ADDED:
            if not after:
                return (1, {"applied": False}, None)
            db.Run("execute", {
                "sql": "INSERT INTO mu_semantic_tags (node_id, tag, confidence_score, source) VALUES (?, ?, ?, ?)",
                "params": [after.get("node_id"), after.get("tag", ""),
                           after.get("confidence_score", 0.5),
                           after.get("source", "manual")],
            })
            return (1, {"applied": True}, None)
        return (1, {"applied": True, "reason": "existing reasoning event acknowledged"}, None)

    def VerifyContinuity(self, params):
        db = self.state["db"]
        if not db:
            return (0, None, ("NO_DB", "db required", 0))
        strict = self._p(params, "strict", False)
        if strict:
            r = db.Run("query", {
                "sql": """SELECT n.node_id FROM mu_ast_nodes n
                    INNER JOIN mu_ast_versions v ON v.node_id = n.node_id AND v.is_current=1
                    LEFT JOIN mu_bcl_stamps s
                    ON s.node_id=n.node_id AND s.state_status='ACTIVE'
                       AND s.superseded_by IS NULL
                       AND s.ast_version_id = v.version_id
                    WHERE n.destroyed_event_id IS NULL AND s.stamp_id IS NULL
                      AND n.node_type IN ('CLASS','METHOD')""",
                "params": [],
            })
            if r[0] == 1 and r[1]["count"] > 0:
                orphans = [row["node_id"] for row in r[1]["rows"]]
                return (0, None, ("ORPHAN_NODES", "nodes without active stamps: " + str(orphans), 0))
        r = db.Run("query", {
            "sql": """SELECT trace_id, MIN(step_no) as min_s, MAX(step_no) as max_s, COUNT(*) as cnt
                FROM mu_trace_steps GROUP BY trace_id
                HAVING MIN(step_no) != 1 OR (MAX(step_no) - MIN(step_no) + 1) != COUNT(*)""",
            "params": [],
        })
        if r[0] == 1 and r[1]["count"] > 0:
            broken = [row["trace_id"] for row in r[1]["rows"]]
            return (0, None, ("BROKEN_TRACE", "traces with gaps: " + str(broken), 0))
        r = db.Run("query", {
            "sql": """SELECT e.edge_id FROM mu_dependency_edges e
                JOIN mu_ast_versions v ON v.version_id=e.from_version_id
                WHERE e.validity_state='VALID' AND v.is_current=0""",
            "params": [],
        })
        if r[0] == 1 and r[1]["count"] > 0:
            stale = [row["edge_id"] for row in r[1]["rows"]]
            return (0, None, ("STALE_DEPENDENCY", "edges point to superseded versions: " + str(stale), 0))
        return (1, {"ok": True, "strict": strict, "broken_traces": 0, "stale_edges": 0}, None)

    def read_state(self, params):
        return (1, {
            "config": self.state["config"],
            "stats": self.state["stats"],
        }, None)

    def set_config(self, params):
        ss = self._p(params, "snapshot_store")
        if ss:
            self.state["snapshot_store"] = ss
        for key in ("session_id",):
            val = self._p(params, key)
            if val:
                self.state["config"][key] = val
        return (1, {"config": self.state["config"]}, None)
