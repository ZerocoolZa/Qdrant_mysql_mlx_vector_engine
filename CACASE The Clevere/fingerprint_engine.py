#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/fingerprint_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 17: Project Fingerprinting -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="fingerprint_engine.py" domain="twin_fingerprint" authority="FingerprintEngine"}
# [@SUMMARY]{summary="Fingerprint authority: project hash, file hashes, class hashes, method hashes, BCL hashes, dependency hashes, graph hash, snapshot ID, change signature, integrity verification."}
# [@CLASS]{class="FingerprintEngine" domain="fingerprint" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="project_hash" type="command"}
# [@METHOD]{method="file_hashes" type="command"}
# [@METHOD]{method="class_hashes" type="command"}
# [@METHOD]{method="method_hashes" type="command"}
# [@METHOD]{method="bcl_hashes" type="command"}
# [@METHOD]{method="dependency_hashes" type="command"}
# [@METHOD]{method="graph_hash" type="command"}
# [@METHOD]{method="snapshot_id" type="command"}
# [@METHOD]{method="change_signature" type="command"}
# [@METHOD]{method="integrity_verification" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class FingerprintEngine:
    """Authority for computing and verifying project fingerprints."""

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
            "last_snapshot_id": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "project_hash":
            return self.ProjectHash(params)
        elif command == "file_hashes":
            return self.FileHashes(params)
        elif command == "class_hashes":
            return self.ClassHashes(params)
        elif command == "method_hashes":
            return self.MethodHashes(params)
        elif command == "bcl_hashes":
            return self.BclHashes(params)
        elif command == "dependency_hashes":
            return self.DependencyHashes(params)
        elif command == "graph_hash":
            return self.GraphHash(params)
        elif command == "snapshot_id":
            return self.SnapshotId(params)
        elif command == "change_signature":
            return self.ChangeSignature(params)
        elif command == "integrity_verification":
            return self.IntegrityVerification(params)
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

    def ComputeHash(self, text):
        return (1, hashlib.sha256(text.encode("utf-8")).hexdigest(), None)

    def StoreFingerprint(self, fp_type, target_id, fp_hash):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO fingerprints (fingerprint_type, target_id, hash, created) "
                "VALUES (?,?,?,?)",
                (fp_type, target_id, fp_hash, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("STORE_FAILED", str(exc), 0))
        return (1, cur.lastrowid, None)

    def ProjectHash(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM files")
            file_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM classes")
            class_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods")
            method_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM edges")
            edge_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM knowledge")
            knowledge_count = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(SUM(LENGTH(method_code)),0) FROM methods")
            code_size = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        fp_text = json.dumps({
            "files": file_count, "classes": class_count,
            "methods": method_count, "edges": edge_count,
            "knowledge": knowledge_count, "code_size": code_size,
        }, sort_keys=True)
        fp_hash = self.ComputeHash(fp_text)[1]
        self.StoreFingerprint("project", 0, fp_hash)
        return (1, {"project_hash": fp_hash, "files": file_count,
                    "classes": class_count, "methods": method_count,
                    "edges": edge_count, "code_size": code_size}, None)

    def FileHashes(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        file_id = self._p(params, "file_id")
        try:
            if file_id is not None:
                cur.execute("SELECT file_id, file_path, hash FROM files WHERE file_id=?",
                            (file_id,))
                row = cur.fetchone()
                if row is None:
                    return (0, None, ("FILE_NOT_FOUND", str(file_id), 0))
                return (1, {"file_id": row[0], "file_path": row[1],
                            "hash": row[2]}, None)
            cur.execute("SELECT file_id, file_path, hash FROM files ORDER BY file_id")
            files = []
            for row in cur.fetchall():
                files.append({"file_id": row[0], "file_path": row[1],
                              "hash": row[2]})
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        all_text = json.dumps([{"p": f["file_path"], "h": f["hash"]} for f in files],
                              sort_keys=True)
        combined = self.ComputeHash(all_text)[1]
        return (1, {"files": files, "count": len(files),
                    "combined_hash": combined}, None)

    def ClassHashes(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        class_id = self._p(params, "class_id")
        try:
            if class_id is not None:
                cur.execute("SELECT class_id, class_name, parent, method_count, bcl FROM classes WHERE class_id=?",
                            (class_id,))
                row = cur.fetchone()
                if row is None:
                    return (0, None, ("CLASS_NOT_FOUND", str(class_id), 0))
                fp_text = json.dumps({"name": row[1], "parent": row[2],
                                      "methods": row[3], "bcl": row[3]})
                fp_hash = self.ComputeHash(fp_text)[1]
                self.StoreFingerprint("class", class_id, fp_hash)
                return (1, {"class_id": row[0], "class_name": row[1],
                            "fingerprint": fp_hash}, None)
            cur.execute("SELECT class_id, class_name, hash FROM classes ORDER BY class_id")
            classes = [{"class_id": r[0], "class_name": r[1], "hash": r[2]}
                       for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"classes": classes, "count": len(classes)}, None)

    def MethodHashes(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        method_id = self._p(params, "method_id")
        try:
            if method_id is not None:
                cur.execute("SELECT method_id, method_name, method_code, signature FROM methods WHERE method_id=?",
                            (method_id,))
                row = cur.fetchone()
                if row is None:
                    return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
                fp_text = json.dumps({"name": row[1], "code": row[2], "sig": row[3]})
                fp_hash = self.ComputeHash(fp_text)[1]
                self.StoreFingerprint("method", method_id, fp_hash)
                return (1, {"method_id": row[0], "method_name": row[1],
                            "fingerprint": fp_hash}, None)
            cur.execute("SELECT method_id, method_name, hash FROM methods ORDER BY method_id")
            methods = [{"method_id": r[0], "method_name": r[1], "hash": r[2]}
                       for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"methods": methods, "count": len(methods)}, None)

    def BclHashes(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT class_id, class_name, bcl FROM classes WHERE bcl IS NOT NULL AND bcl != ''")
            class_bcls = []
            for row in cur.fetchall():
                bcl_hash = self.ComputeHash(row[2])[1]
                class_bcls.append({"class_id": row[0], "class_name": row[1],
                                   "bcl_hash": bcl_hash})
            cur.execute("SELECT method_id, method_name, bcl FROM methods WHERE bcl IS NOT NULL AND bcl != ''")
            method_bcls = []
            for row in cur.fetchall():
                bcl_hash = self.ComputeHash(row[2])[1]
                method_bcls.append({"method_id": row[0], "method_name": row[1],
                                    "bcl_hash": bcl_hash})
            all_text = json.dumps({
                "classes": [{"id": c["class_id"], "h": c["bcl_hash"]} for c in class_bcls],
                "methods": [{"id": m["method_id"], "h": m["bcl_hash"]} for m in method_bcls],
            }, sort_keys=True)
            combined = self.ComputeHash(all_text)[1]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"class_bcl_hashes": class_bcls,
                    "method_bcl_hashes": method_bcls,
                    "class_count": len(class_bcls),
                    "method_count": len(method_bcls),
                    "combined_hash": combined}, None)

    def DependencyHashes(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type")
            edge_summary = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute("SELECT COUNT(*) FROM edges")
            total = cur.fetchone()[0]
            cur.execute(
                "SELECT src_id, src_type, dst_id, dst_type, edge_type FROM edges "
                "ORDER BY edge_id LIMIT 1000"
            )
            edges = []
            for r in cur.fetchall():
                edges.append({"src_id": r[0], "src_type": r[1],
                              "dst_id": r[2], "dst_type": r[3],
                              "edge_type": r[4]})
            fp_text = json.dumps({"total": total, "by_type": edge_summary,
                                  "edges": edges}, sort_keys=True)
            fp_hash = self.ComputeHash(fp_text)[1]
            self.StoreFingerprint("dependencies", 0, fp_hash)
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"dependency_hash": fp_hash, "total_edges": total,
                    "edge_types": edge_summary}, None)

    def GraphHash(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type")
            edge_summary = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute("SELECT COUNT(*) FROM edges")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM classes")
            class_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods")
            method_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM files")
            file_count = cur.fetchone()[0]
            fp_text = json.dumps({"edges": total, "edge_types": edge_summary,
                                  "classes": class_count, "methods": method_count,
                                  "files": file_count}, sort_keys=True)
            fp_hash = self.ComputeHash(fp_text)[1]
            self.StoreFingerprint("graph", 0, fp_hash)
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"graph_hash": fp_hash, "total_edges": total,
                    "edge_types": edge_summary, "classes": class_count,
                    "methods": method_count, "files": file_count}, None)

    def SnapshotId(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT MAX(snapshot_id) FROM snapshots")
            max_id = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM snapshots")
            total = cur.fetchone()[0]
            cur.execute(
                "SELECT snapshot_id, snapshot_type, method_id, created "
                "FROM snapshots ORDER BY snapshot_id DESC LIMIT 10"
            )
            recent = [{"snapshot_id": r[0], "type": r[1],
                       "method_id": r[2], "created": r[3]}
                      for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        sid = max_id if max_id is not None else 0
        self.state["last_snapshot_id"] = sid
        return (1, {"snapshot_id": sid, "total_snapshots": total,
                    "recent": recent}, None)

    def ChangeSignature(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT fingerprint_type, hash, created FROM fingerprints "
                "ORDER BY fingerprint_id DESC LIMIT 1"
            )
            latest = cur.fetchone()
            cur.execute(
                "SELECT fingerprint_type, hash FROM fingerprints "
                "WHERE fingerprint_type='project' ORDER BY fingerprint_id DESC LIMIT 2"
            )
            project_fps = cur.fetchall()
            changes = {}
            if len(project_fps) >= 2:
                changes["project_hash_changed"] = project_fps[0][1] != project_fps[1][1]
            cur.execute(
                "SELECT method_id, hash FROM methods WHERE hash IS NOT NULL "
                "ORDER BY method_id"
            )
            current_methods = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute(
                "SELECT target_id, hash FROM fingerprints "
                "WHERE fingerprint_type='method' AND target_id IN "
                "(SELECT method_id FROM methods) "
                "GROUP BY target_id HAVING MAX(fingerprint_id)"
            )
            stored_method_fps = {r[0]: r[1] for r in cur.fetchall()}
            changed_methods = []
            for mid, current_hash in current_methods.items():
                if mid in stored_method_fps and stored_method_fps[mid] != current_hash:
                    changed_methods.append(mid)
            changes["changed_methods"] = changed_methods
            changes["changed_method_count"] = len(changed_methods)
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"latest_fingerprint": latest,
                    "changes": changes,
                    "has_changes": changes.get("changed_method_count", 0) > 0}, None)

    def IntegrityVerification(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA integrity_check")
            integrity = cur.fetchone()[0]
            cur.execute("PRAGMA foreign_key_check")
            fk_violations = cur.fetchall()
            cur.execute(
                "SELECT COUNT(*) FROM methods WHERE hash IS NOT NULL"
            )
            methods_with_hash = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM fingerprints WHERE fingerprint_type='method'"
            )
            stored_fps = cur.fetchone()[0]
            cur.execute(
                "SELECT method_id, hash FROM methods WHERE hash IS NOT NULL"
            )
            current_hashes = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute(
                "SELECT target_id, hash FROM fingerprints "
                "WHERE fingerprint_type='method' GROUP BY target_id "
                "HAVING MAX(fingerprint_id)"
            )
            stored_hashes = {r[0]: r[1] for r in cur.fetchall()}
            mismatches = []
            for mid, chash in current_hashes.items():
                if mid in stored_hashes and stored_hashes[mid] != chash:
                    mismatches.append({"method_id": mid,
                                       "stored": stored_hashes[mid],
                                       "current": chash})
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        ok = integrity == "ok" and len(fk_violations) == 0 and len(mismatches) == 0
        return (1, {"integrity": integrity,
                    "fk_violations": len(fk_violations),
                    "methods_with_hash": methods_with_hash,
                    "stored_fingerprints": stored_fps,
                    "hash_mismatches": mismatches,
                    "mismatch_count": len(mismatches),
                    "valid": ok}, None)
