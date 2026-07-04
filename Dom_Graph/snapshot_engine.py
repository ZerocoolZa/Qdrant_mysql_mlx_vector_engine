#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/snapshot_engine.py"
# date="2026-06-26" author="Devin" session_id="phase2-graph"
# context="Project Digital Twin Phase 2 Section 18 Version Snapshots"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="snapshot_engine.py" domain="twin_snapshot" authority="SnapshotEngine"}
# [@SUMMARY]{summary="Snapshot authority that creates, restores, compares and lists version snapshots of files, classes and methods."}
# [@CLASS]{class="SnapshotEngine" domain="snapshot" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="create_snapshot" type="command"}
# [@METHOD]{method="restore_snapshot" type="command"}
# [@METHOD]{method="compare_snapshots" type="command"}
# [@METHOD]{method="list_snapshots" type="command"}
# [@METHOD]{method="timeline" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<SnapshotEngine: creates restores compares lists version snapshots of files classes methods. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations.>][@todos<none>]}
"""
SnapshotEngine -- authority for version snapshots.
Implements Section 18 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: create_snapshot, restore_snapshot, compare_snapshots,
          list_snapshots, timeline.
"""
import difflib
import hashlib
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"


class SnapshotEngine:
    """Authority for creating and restoring version snapshots."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
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
        if command == "create_snapshot":
            return self.CreateSnapshot(params)
        elif command == "restore_snapshot":
            return self.RestoreSnapshot(params)
        elif command == "compare_snapshots":
            return self.CompareSnapshots(params)
        elif command == "list_snapshots":
            return self.ListSnapshots(params)
        elif command == "timeline":
            return self.Timeline(params)
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

    def Now(self):
        return datetime.now(timezone.utc).isoformat()

    def HashText(self, text):
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def CreateSnapshot(self, params):
        snapshot_type = self._p(params, "snapshot_type", "manual")
        content = self._p(params, "content")
        if content is None:
            return (0, None, ("MISSING_PARAM", "content required", 0))
        file_id = self._p(params, "file_id")
        class_id = self._p(params, "class_id")
        method_id = self._p(params, "method_id")
        notes = self._p(params, "notes", "")
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO snapshots (snapshot_type, file_id, class_id, "
                "method_id, content, hash, created, notes) VALUES (?,?,?,?,?,?,?,?)",
                (snapshot_type, file_id, class_id, method_id, content,
                 self.HashText(content), self.Now(), notes),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        record = {
            "snapshot_id": cur.lastrowid,
            "snapshot_type": snapshot_type,
            "hash": self.HashText(content),
            "created": self.Now(),
        }
        self.state["catalog"].append(record)
        return (1, record, None)

    def RestoreSnapshot(self, params):
        snapshot_id = self._p(params, "snapshot_id")
        if snapshot_id is None:
            return (0, None, ("MISSING_PARAM", "snapshot_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT content, method_id, file_id, class_id FROM snapshots WHERE snapshot_id=?",
                    (snapshot_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("NOT_FOUND", "snapshot not found", 0))
        content, method_id, file_id, class_id = row
        if method_id is not None:
            cur.execute("UPDATE methods SET method_code=? WHERE method_id=?",
                        (content, method_id))
        elif file_id is not None:
            cur.execute("UPDATE files SET bcl=? WHERE file_id=?", (content, file_id))
        elif class_id is not None:
            cur.execute("UPDATE classes SET bcl=? WHERE class_id=?", (content, class_id))
        conn.commit()
        record = {
            "snapshot_id": snapshot_id,
            "restored_to": {"method_id": method_id, "file_id": file_id,
                            "class_id": class_id},
        }
        return (1, record, None)

    def CompareSnapshots(self, params):
        snap_a = self._p(params, "snapshot_id_a")
        snap_b = self._p(params, "snapshot_id_b")
        if snap_a is None or snap_b is None:
            return (0, None, ("MISSING_PARAM",
                              "snapshot_id_a and snapshot_id_b required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT content, hash FROM snapshots WHERE snapshot_id=?", (snap_a,))
        row_a = cur.fetchone()
        cur.execute("SELECT content, hash FROM snapshots WHERE snapshot_id=?", (snap_b,))
        row_b = cur.fetchone()
        if row_a is None or row_b is None:
            return (0, None, ("NOT_FOUND", "one or both snapshots not found", 0))
        content_a, hash_a = row_a
        content_b, hash_b = row_b
        lines_a = content_a.splitlines() if content_a else []
        lines_b = content_b.splitlines() if content_b else []
        added = []
        removed = []
        modified = []
        if hash_a == hash_b:
            diff_lines = []
            unified = ""
        else:
            matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == "equal":
                    continue
                elif tag == "delete":
                    for idx in range(i1, i2):
                        removed.append({"line_no": idx + 1, "content": lines_a[idx]})
                elif tag == "insert":
                    for idx in range(j1, j2):
                        added.append({"line_no": idx + 1, "content": lines_b[idx]})
                elif tag == "replace":
                    for idx in range(i1, i2):
                        removed.append({"line_no": idx + 1, "content": lines_a[idx],
                                        "modified": True})
                    for idx in range(j1, j2):
                        added.append({"line_no": idx + 1, "content": lines_b[idx],
                                      "modified": True})
                    modified.append({
                        "before_start": i1 + 1, "before_end": i2,
                        "after_start": j1 + 1, "after_end": j2,
                    })
            diff_lines = list(difflib.unified_diff(
                lines_a, lines_b, fromfile="snapshot_" + str(snap_a),
                tofile="snapshot_" + str(snap_b), lineterm=""))
            unified = "\n".join(diff_lines)
        record = {
            "snapshot_id_a": snap_a,
            "snapshot_id_b": snap_b,
            "hash_a": hash_a,
            "hash_b": hash_b,
            "identical": hash_a == hash_b,
            "lines_a": len(lines_a),
            "lines_b": len(lines_b),
            "added": added,
            "removed": removed,
            "modified": modified,
            "added_count": len(added),
            "removed_count": len(removed),
            "modified_count": len(modified),
            "unified_diff": unified,
            "diff_lines": diff_lines,
        }
        return (1, record, None)

    def ListSnapshots(self, params):
        method_id = self._p(params, "method_id")
        file_id = self._p(params, "file_id")
        class_id = self._p(params, "class_id")
        conn = self.Connect()
        cur = conn.cursor()
        query = "SELECT snapshot_id, snapshot_type, hash, created, notes FROM snapshots"
        conditions = []
        values = []
        if method_id is not None:
            conditions.append("method_id=?")
            values.append(method_id)
        if file_id is not None:
            conditions.append("file_id=?")
            values.append(file_id)
        if class_id is not None:
            conditions.append("class_id=?")
            values.append(class_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created DESC"
        cur.execute(query, values)
        snapshots = [{"snapshot_id": r[0], "snapshot_type": r[1], "hash": r[2],
                      "created": r[3], "notes": r[4]} for r in cur.fetchall()]
        self.state["results"] = snapshots
        return (1, {"snapshots": snapshots, "count": len(snapshots)}, None)

    def Timeline(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT snapshot_id, snapshot_type, method_id, file_id, class_id, "
            "content, hash, created, notes FROM snapshots ORDER BY created"
        )
        rows = cur.fetchall()
        timeline = []
        prev_hash = None
        prev_size = None
        for row in rows:
            snap_id, snap_type, method_id, file_id, class_id, content, shash, created, notes = row
            size = len(content) if content else 0
            line_count = len(content.splitlines()) if content else 0
            hash_changed = prev_hash is not None and prev_hash != shash
            size_changed = prev_size is not None and prev_size != size
            entry = {
                "snapshot_id": snap_id,
                "snapshot_type": snap_type,
                "method_id": method_id,
                "file_id": file_id,
                "class_id": class_id,
                "hash": shash,
                "created": created,
                "notes": notes,
                "size": size,
                "line_count": line_count,
                "hash_changed": hash_changed,
                "size_changed": size_changed,
                "size_delta": (size - prev_size) if prev_size is not None else 0,
            }
            timeline.append(entry)
            prev_hash = shash
            prev_size = size
        return (1, {"timeline": timeline, "count": len(timeline)}, None)
