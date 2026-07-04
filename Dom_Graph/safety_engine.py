#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/safety_engine.py"
# date="2026-06-26" author="Devin" session_id="phase5-quality"
# context="Project Digital Twin Phase 5 Section 31 Safety Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="safety_engine.py" domain="twin_safety" authority="SafetyEngine"}
# [@SUMMARY]{summary="Safety authority for safe writes with snapshot, verify before/after and emergency rollback."}
# [@CLASS]{class="SafetyEngine" domain="safety" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="safe_write" type="command"}
# [@METHOD]{method="verify_before" type="command"}
# [@METHOD]{method="verify_after" type="command"}
# [@METHOD]{method="verify_all" type="command"}
# [@METHOD]{method="emergency_rollback" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="Connect" type="helper"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<SafetyEngine: safe writes with snapshot verify before/after and emergency rollback. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config Connect helper. No print no decorators no self._ violations.>][@todos<none>]}
"""
SafetyEngine -- authority for safe file writes with verification and rollback.
Implements Section 31 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: safe_write, verify_before, verify_after, verify_all, emergency_rollback.
"""
import hashlib
import os
import py_compile
import sqlite3
import tempfile
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class SafetyEngine:
    """Authority for safe writes with snapshot, verification and rollback."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
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
        if command == "safe_write":
            return self.SafeWrite(params)
        elif command == "verify_before":
            return self.VerifyBefore(params)
        elif command == "verify_after":
            return self.VerifyAfter(params)
        elif command == "verify_graph":
            return self.VerifyGraph(params)
        elif command == "verify_database":
            return self.VerifyDatabase(params)
        elif command == "verify_runtime":
            return self.VerifyRuntime(params)
        elif command == "verify_output":
            return self.VerifyOutput(params)
        elif command == "verify_all":
            return self.VerifyAll(params)
        elif command == "emergency_rollback":
            return self.EmergencyRollback(params)
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

    def HashContent(self, content):
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def CreateSnapshot(self, snapshot_type, file_id, class_id, method_id, content):
        conn = self.Connect()
        cur = conn.cursor()
        digest = self.HashContent(content)
        created = datetime.now(timezone.utc).isoformat()
        cur.execute(
            "INSERT INTO snapshots (snapshot_type, file_id, class_id, method_id, "
            "content, hash, created, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                snapshot_type,
                file_id,
                class_id,
                method_id,
                content,
                digest,
                created,
                "SafetyEngine safe_write",
            ),
        )
        conn.commit()
        return cur.lastrowid, digest, created

    def GetFileIds(self, params):
        file_id = self._p(params, "file_id")
        method_id = self._p(params, "method_id")
        class_id = self._p(params, "class_id")
        if file_id is None and method_id is not None:
            try:
                conn = self.Connect()
                cur = conn.cursor()
                cur.execute("SELECT file_id FROM methods WHERE method_id=?", (method_id,))
                row = cur.fetchone()
                if row:
                    file_id = row[0]
            except sqlite3.Error:
                pass
        if class_id is None and method_id is not None:
            try:
                conn = self.Connect()
                cur = conn.cursor()
                cur.execute("SELECT class_id FROM methods WHERE method_id=?", (method_id,))
                row = cur.fetchone()
                if row:
                    class_id = row[0]
            except sqlite3.Error:
                pass
        return file_id, class_id, method_id

    def VerifyBefore(self, params):
        file_path = self._p(params, "file_path")
        content = self._p(params, "content")
        if not file_path:
            return (0, None, ("MISSING_PARAM", "file_path required", 0))
        if content is None:
            return (0, None, ("MISSING_PARAM", "content required", 0))
        fd = None
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".py", prefix="safety_verify_")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
            py_compile.compile(tmp_path, doraise=True)
            result = {
                "passed": True,
                "error": None,
                "file_path": file_path,
                "stage": "verify_before",
            }
            return (1, result, None)
        except py_compile.PyCompileError as exc:
            result = {
                "passed": False,
                "error": str(exc),
                "file_path": file_path,
                "stage": "verify_before",
            }
            return (1, result, None)
        except OSError as exc:
            return (0, None, ("TEMP_ERROR", str(exc), 0))
        finally:
            if tmp_path and os.path.isfile(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def VerifyAfter(self, params):
        file_path = self._p(params, "file_path")
        if not file_path:
            return (0, None, ("MISSING_PARAM", "file_path required", 0))
        if not os.path.isfile(file_path):
            return (0, None, ("FILE_NOT_FOUND", file_path, 0))
        try:
            py_compile.compile(file_path, doraise=True)
            result = {
                "passed": True,
                "error": None,
                "file_path": file_path,
                "stage": "verify_after",
            }
            return (1, result, None)
        except py_compile.PyCompileError as exc:
            result = {
                "passed": False,
                "error": str(exc),
                "file_path": file_path,
                "stage": "verify_after",
            }
            return (1, result, None)
        except OSError as exc:
            return (0, None, ("COMPILE_ERROR", str(exc), 0))

    def VerifyGraph(self, params):
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM edges")
            edge_count = cur.fetchone()[0]
            cur.execute(
                "SELECT edge_id, src_type, src_id, dst_type, dst_id "
                "FROM edges WHERE src_type='method' AND src_id NOT IN "
                "(SELECT method_id FROM methods) "
                "OR dst_type='method' AND dst_id NOT IN "
                "(SELECT method_id FROM methods)"
            )
            dangling_methods = cur.fetchall()
            cur.execute(
                "SELECT edge_id, src_type, src_id, dst_type, dst_id "
                "FROM edges WHERE src_type='class' AND src_id NOT IN "
                "(SELECT class_id FROM classes) "
                "OR dst_type='class' AND dst_id NOT IN "
                "(SELECT class_id FROM classes)"
            )
            dangling_classes = cur.fetchall()
            cur.execute(
                "SELECT edge_id, src_type, src_id, dst_type, dst_id "
                "FROM edges WHERE src_type='file' AND src_id NOT IN "
                "(SELECT file_id FROM files) "
                "OR dst_type='file' AND dst_id NOT IN "
                "(SELECT file_id FROM files)"
            )
            dangling_files = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        dangling = []
        for row in dangling_methods:
            dangling.append({"edge_id": row[0], "type": "method", "src_id": row[2], "dst_id": row[4]})
        for row in dangling_classes:
            dangling.append({"edge_id": row[0], "type": "class", "src_id": row[2], "dst_id": row[4]})
        for row in dangling_files:
            dangling.append({"edge_id": row[0], "type": "file", "src_id": row[2], "dst_id": row[4]})
        result = {
            "edge_count": edge_count,
            "dangling_references": dangling,
            "dangling_count": len(dangling),
            "passed": len(dangling) == 0,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def VerifyDatabase(self, params):
        checks = {}
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check")
            row = cur.fetchone()
            checks["integrity_check"] = {
                "result": row[0],
                "passed": row[0] == "ok",
            }
        except sqlite3.Error as exc:
            checks["integrity_check"] = {"passed": False, "error": str(exc)}
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA foreign_key_check")
            fk_violations = cur.fetchall()
            checks["foreign_key_check"] = {
                "violations": [
                    {"table": v[0], "rowid": v[1], "parent": v[2], "fkid": v[3]}
                    for v in fk_violations
                ],
                "count": len(fk_violations),
                "passed": len(fk_violations) == 0,
            }
        except sqlite3.Error as exc:
            checks["foreign_key_check"] = {"passed": False, "error": str(exc)}
        all_passed = all(c.get("passed", False) for c in checks.values())
        result = {
            "checks": checks,
            "passed": all_passed,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def VerifyRuntime(self, params):
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT class_id, class_name, has_run_method FROM classes "
                "WHERE has_run_method=0 OR has_run_method IS NULL"
            )
            missing_run = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        violations = []
        for class_id, class_name, has_run in missing_run:
            violations.append({
                "class_id": class_id,
                "class_name": class_name,
                "has_run_method": bool(has_run) if has_run else False,
                "violation": "missing_run_method",
            })
        result = {
            "violations": violations,
            "count": len(violations),
            "passed": len(violations) == 0,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def VerifyOutput(self, params):
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT method_id, class_id, method_name, returns_tuple3 "
                "FROM methods WHERE returns_tuple3=0 OR returns_tuple3 IS NULL"
            )
            missing_tuple3 = cur.fetchall()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        violations = []
        for method_id, class_id, method_name, ret_t3 in missing_tuple3:
            if method_name in ("__init__", "_p", "read_state", "set_config", "Connect"):
                continue
            violations.append({
                "method_id": method_id,
                "class_id": class_id,
                "method_name": method_name,
                "returns_tuple3": bool(ret_t3) if ret_t3 else False,
                "violation": "missing_tuple3_return",
            })
        result = {
            "violations": violations,
            "count": len(violations),
            "passed": len(violations) == 0,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def VerifyAll(self, params):
        file_path = self._p(params, "file_path")
        checks = {}
        if file_path:
            if not os.path.isfile(file_path):
                return (0, None, ("FILE_NOT_FOUND", file_path, 0))
            try:
                py_compile.compile(file_path, doraise=True)
                checks["compile"] = {"passed": True, "error": None}
            except py_compile.PyCompileError as exc:
                checks["compile"] = {"passed": False, "error": str(exc)}
        try:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check")
            row = cur.fetchone()
            checks["integrity"] = {
                "passed": row[0] == "ok",
                "result": row[0],
            }
        except sqlite3.Error as exc:
            checks["integrity"] = {"passed": False, "error": str(exc)}
        graph_check = self.VerifyGraph(params)
        if graph_check[0] == 1:
            checks["graph"] = {
                "passed": graph_check[1]["passed"],
                "dangling_count": graph_check[1]["dangling_count"],
            }
        else:
            checks["graph"] = {"passed": False, "error": str(graph_check[2])}
        db_check = self.VerifyDatabase(params)
        if db_check[0] == 1:
            checks["database"] = {
                "passed": db_check[1]["passed"],
            }
        else:
            checks["database"] = {"passed": False, "error": str(db_check[2])}
        runtime_check = self.VerifyRuntime(params)
        if runtime_check[0] == 1:
            checks["runtime"] = {
                "passed": runtime_check[1]["passed"],
                "violation_count": runtime_check[1]["count"],
            }
        else:
            checks["runtime"] = {"passed": False, "error": str(runtime_check[2])}
        output_check = self.VerifyOutput(params)
        if output_check[0] == 1:
            checks["output"] = {
                "passed": output_check[1]["passed"],
                "violation_count": output_check[1]["count"],
            }
        else:
            checks["output"] = {"passed": False, "error": str(output_check[2])}
        all_passed = True
        for check in checks.values():
            if not check.get("passed", False):
                all_passed = False
                break
        result = {
            "file_path": file_path,
            "checks": checks,
            "passed": all_passed,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(result)
        return (1, result, None)

    def SafeWrite(self, params):
        file_path = self._p(params, "file_path")
        content = self._p(params, "content")
        method_id = self._p(params, "method_id")
        if not file_path:
            return (0, None, ("MISSING_PARAM", "file_path required", 0))
        if content is None:
            return (0, None, ("MISSING_PARAM", "content required", 0))
        file_id, class_id, method_id = self.GetFileIds(params)
        before_content = ""
        if os.path.isfile(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as fh:
                    before_content = fh.read()
            except OSError as exc:
                return (0, None, ("READ_ERROR", str(exc), 0))
        try:
            snapshot_id, snapshot_hash, created = self.CreateSnapshot(
                "before_fix", file_id, class_id, method_id, before_content
            )
        except sqlite3.Error as exc:
            return (0, None, ("SNAPSHOT_ERROR", str(exc), 0))
        verify_before = self.VerifyBefore(params)
        if verify_before[0] != 1 or not verify_before[1].get("passed"):
            return (
                1,
                {
                    "passed": False,
                    "stage": "verify_before",
                    "error": verify_before[1].get("error") if verify_before[0] == 1 else str(verify_before[2]),
                    "snapshot_id": snapshot_id,
                    "rolled_back": True,
                },
                None,
            )
        try:
            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(content)
        except OSError as exc:
            try:
                with open(file_path, "w", encoding="utf-8") as fh:
                    fh.write(before_content)
            except OSError:
                pass
            return (0, None, ("WRITE_ERROR", str(exc), 0))
        verify_after = self.VerifyAfter({"file_path": file_path})
        if verify_after[0] != 1 or not verify_after[1].get("passed"):
            try:
                with open(file_path, "w", encoding="utf-8") as fh:
                    fh.write(before_content)
            except OSError:
                pass
            return (
                1,
                {
                    "passed": False,
                    "stage": "verify_after",
                    "error": verify_after[1].get("error") if verify_after[0] == 1 else str(verify_after[2]),
                    "snapshot_id": snapshot_id,
                    "rolled_back": True,
                },
                None,
            )
        verify_all = self.VerifyAll({"file_path": file_path})
        if verify_all[0] != 1 or not verify_all[1].get("passed"):
            try:
                with open(file_path, "w", encoding="utf-8") as fh:
                    fh.write(before_content)
            except OSError:
                pass
            return (
                1,
                {
                    "passed": False,
                    "stage": "verify_all",
                    "error": verify_all[2] if verify_all[0] != 1 else "integrity or edge check failed",
                    "snapshot_id": snapshot_id,
                    "rolled_back": True,
                },
                None,
            )
        result = {
            "passed": True,
            "file_path": file_path,
            "snapshot_id": snapshot_id,
            "snapshot_hash": snapshot_hash,
            "rolled_back": False,
            "created": created,
        }
        self.state["results"].append(result)
        return (1, result, None)

    def EmergencyRollback(self, params):
        method_id = self._p(params, "method_id")
        file_id = self._p(params, "file_id")
        if method_id is None and file_id is None:
            return (0, None, ("MISSING_PARAM", "method_id or file_id required", 0))
        try:
            conn = self.Connect()
            cur = conn.cursor()
            if method_id is not None:
                cur.execute(
                    "SELECT snapshot_id, content, hash, created FROM snapshots "
                    "WHERE method_id=? ORDER BY created DESC LIMIT 1",
                    (method_id,),
                )
            else:
                cur.execute(
                    "SELECT snapshot_id, content, hash, created FROM snapshots "
                    "WHERE file_id=? ORDER BY created DESC LIMIT 1",
                    (file_id,),
                )
            row = cur.fetchone()
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        if not row:
            return (0, None, ("NO_SNAPSHOT", "No snapshot found to restore", 0))
        snapshot_id, content, snapshot_hash, created = row
        if method_id is not None:
            try:
                cur.execute(
                    "UPDATE methods SET method_code=? WHERE method_id=?",
                    (content, method_id),
                )
                conn.commit()
            except sqlite3.Error as exc:
                return (0, None, ("UPDATE_ERROR", str(exc), 0))
        else:
            try:
                cur.execute("SELECT path FROM files WHERE file_id=?", (file_id,))
                file_row = cur.fetchone()
                if not file_row:
                    return (0, None, ("FILE_NOT_FOUND", "file_id not in files table", 0))
                file_path = file_row[0]
                with open(file_path, "w", encoding="utf-8") as fh:
                    fh.write(content)
            except (sqlite3.Error, OSError) as exc:
                return (0, None, ("RESTORE_ERROR", str(exc), 0))
        result = {
            "passed": True,
            "snapshot_id": snapshot_id,
            "method_id": method_id,
            "file_id": file_id,
            "hash": snapshot_hash,
            "restored_from": created,
        }
        self.state["results"].append(result)
        return (1, result, None)
