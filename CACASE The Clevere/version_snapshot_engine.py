#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/version_snapshot_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 18: Version Snapshot -- 8 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="version_snapshot_engine.py" domain="twin_snapshot" authority="VersionSnapshotEngine"}
# [@SUMMARY]{summary="Snapshot authority: snapshot before, snapshot after, auto restore point, branch experiment, compare snapshots, restore snapshot, snapshot notes, snapshot timeline."}
# [@CLASS]{class="VersionSnapshotEngine" domain="snapshot" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="snapshot_before" type="command"}
# [@METHOD]{method="snapshot_after" type="command"}
# [@METHOD]{method="auto_restore_point" type="command"}
# [@METHOD]{method="branch_experiment" type="command"}
# [@METHOD]{method="compare_snapshots" type="command"}
# [@METHOD]{method="restore_snapshot" type="command"}
# [@METHOD]{method="snapshot_notes" type="command"}
# [@METHOD]{method="snapshot_timeline" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import hashlib
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class VersionSnapshotEngine:
    """Authority for version snapshots and restore points."""

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
        if command == "snapshot_before":
            return self.SnapshotBefore(params)
        elif command == "snapshot_after":
            return self.SnapshotAfter(params)
        elif command == "auto_restore_point":
            return self.AutoRestorePoint(params)
        elif command == "branch_experiment":
            return self.BranchExperiment(params)
        elif command == "compare_snapshots":
            return self.CompareSnapshots(params)
        elif command == "restore_snapshot":
            return self.RestoreSnapshot(params)
        elif command == "snapshot_notes":
            return self.SnapshotNotes(params)
        elif command == "snapshot_timeline":
            return self.SnapshotTimeline(params)
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

    def ComputeHash(self, content):
        if content is None:
            return (1, "", None)
        return (1, hashlib.sha256(content.encode("utf-8")).hexdigest(), None)

    def SnapshotBefore(self, params):
        method_id = self._p(params, "method_id")
        content = self._p(params, "content")
        if content is None:
            return (0, None, ("MISSING_PARAM", "content required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO snapshots (snapshot_type, method_id, content, hash, created, notes) "
                "VALUES ('before', ?, ?, ?, ?, ?)",
                (method_id, content, self.ComputeHash(content)[1],
                 self.Now()[1], self._p(params, "notes", "before change")),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"snapshot_id": cur.lastrowid, "type": "before",
                    "method_id": method_id}, None)

    def SnapshotAfter(self, params):
        method_id = self._p(params, "method_id")
        content = self._p(params, "content")
        if content is None:
            return (0, None, ("MISSING_PARAM", "content required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO snapshots (snapshot_type, method_id, content, hash, created, notes) "
                "VALUES ('after', ?, ?, ?, ?, ?)",
                (method_id, content, self.ComputeHash(content)[1],
                 self.Now()[1], self._p(params, "notes", "after change")),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"snapshot_id": cur.lastrowid, "type": "after",
                    "method_id": method_id}, None)

    def AutoRestorePoint(self, params):
        method_id = self._p(params, "method_id")
        content = self._p(params, "content")
        if content is None:
            return (0, None, ("MISSING_PARAM", "content required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO snapshots (snapshot_type, method_id, content, hash, created, notes) "
                "VALUES ('auto_restore', ?, ?, ?, ?, ?)",
                (method_id, content, self.ComputeHash(content)[1],
                 self.Now()[1], "automatic restore point"),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"snapshot_id": cur.lastrowid, "type": "auto_restore",
                    "method_id": method_id}, None)

    def BranchExperiment(self, params):
        method_id = self._p(params, "method_id")
        content = self._p(params, "content")
        branch_name = self._p(params, "branch_name", "experiment")
        if content is None:
            return (0, None, ("MISSING_PARAM", "content required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO snapshots (snapshot_type, method_id, content, hash, created, notes) "
                "VALUES ('branch', ?, ?, ?, ?, ?)",
                (method_id, content, self.ComputeHash(content)[1],
                 self.Now()[1], "branch: " + branch_name),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"snapshot_id": cur.lastrowid, "type": "branch",
                    "branch_name": branch_name, "method_id": method_id}, None)

    def CompareSnapshots(self, params):
        snapshot_id1 = self._p(params, "snapshot_id1")
        snapshot_id2 = self._p(params, "snapshot_id2")
        if snapshot_id1 is None or snapshot_id2 is None:
            return (0, None, ("MISSING_PARAM", "snapshot_id1 and snapshot_id2 required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT content, hash, snapshot_type FROM snapshots WHERE snapshot_id=?", (snapshot_id1,))
            row1 = cur.fetchone()
            cur.execute("SELECT content, hash, snapshot_type FROM snapshots WHERE snapshot_id=?", (snapshot_id2,))
            row2 = cur.fetchone()
            if row1 is None or row2 is None:
                return (0, None, ("SNAPSHOT_NOT_FOUND", "One or both snapshots missing", 0))
            identical = row1[1] == row2[1]
            content1 = row1[0] or ""
            content2 = row2[0] or ""
            lines1 = content1.split("\n")
            lines2 = content2.split("\n")
            added = max(0, len(lines2) - len(lines1))
            removed = max(0, len(lines1) - len(lines2))
            changed_lines = sum(1 for a, b in zip(lines1, lines2) if a != b)
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"identical": identical, "type1": row1[2], "type2": row2[2],
                    "hash1": row1[1], "hash2": row2[1],
                    "lines_added": added, "lines_removed": removed,
                    "lines_changed": changed_lines}, None)

    def RestoreSnapshot(self, params):
        snapshot_id = self._p(params, "snapshot_id")
        if snapshot_id is None:
            return (0, None, ("MISSING_PARAM", "snapshot_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT content, hash, method_id, snapshot_type FROM snapshots WHERE snapshot_id=?", (snapshot_id,))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("SNAPSHOT_NOT_FOUND", str(snapshot_id), 0))
            content, snap_hash, method_id, snap_type = row
            if method_id:
                cur.execute("UPDATE methods SET method_code=? WHERE method_id=?", (content, method_id))
                conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("RESTORE_FAILED", str(exc), 0))
        return (1, {"snapshot_id": snapshot_id, "restored": True,
                    "method_id": method_id, "type": snap_type,
                    "hash": snap_hash}, None)

    def SnapshotNotes(self, params):
        snapshot_id = self._p(params, "snapshot_id")
        notes = self._p(params, "notes")
        if snapshot_id is None:
            return (0, None, ("MISSING_PARAM", "snapshot_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            if notes is not None:
                cur.execute("UPDATE snapshots SET notes=? WHERE snapshot_id=?", (notes, snapshot_id))
                conn.commit()
                return (1, {"snapshot_id": snapshot_id, "notes": notes, "updated": True}, None)
            cur.execute("SELECT notes FROM snapshots WHERE snapshot_id=?", (snapshot_id,))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("SNAPSHOT_NOT_FOUND", str(snapshot_id), 0))
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"snapshot_id": snapshot_id, "notes": row[0]}, None)

    def SnapshotTimeline(self, params):
        method_id = self._p(params, "method_id")
        limit = self._p(params, "limit", 50)
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            if method_id:
                cur.execute(
                    "SELECT snapshot_id, snapshot_type, hash, created, notes "
                    "FROM snapshots WHERE method_id=? ORDER BY snapshot_id DESC LIMIT ?",
                    (method_id, limit),
                )
            else:
                cur.execute(
                    "SELECT snapshot_id, snapshot_type, hash, created, notes "
                    "FROM snapshots ORDER BY snapshot_id DESC LIMIT ?",
                    (limit,),
                )
            timeline = [{"snapshot_id": r[0], "type": r[1], "hash": r[2],
                         "created": r[3], "notes": r[4]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"timeline": timeline, "count": len(timeline)}, None)
