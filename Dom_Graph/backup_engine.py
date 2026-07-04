#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/backup_engine.py"
# date="2026-06-26" author="Devin" session_id="phase1-foundation"
# context="Project Digital Twin Phase 1 Section 1 Backup Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="backup_engine.py" domain="twin_backup" authority="BackupEngine"}
# [@SUMMARY]{summary="Backup authority for the Project Digital Twin SQLite database. Creates, verifies, restores and lists backups with hash integrity checks."}
# [@CLASS]{class="BackupEngine" domain="backup" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="create_backup" type="command"}
# [@METHOD]{method="verify_backup" type="command"}
# [@METHOD]{method="restore_backup" type="command"}
# [@METHOD]{method="list_backups" type="command"}
# [@METHOD]{method="create_secondary" type="command"}
# [@METHOD]{method="store_offline" type="command"}
# [@METHOD]{method="hash_both" type="command"}
# [@METHOD]{method="record_metadata" type="command"}
# [@METHOD]{method="make_readonly" type="command"}
# [@METHOD]{method="restore_test" type="command"}
# [@METHOD]{method="log_session" type="command"}
# [@METHOD]{method="never_modify_original" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<BackupEngine: SQLite backup authority with create/verify/restore/list commands. Full VBStyle headers present, Run dispatch, Tuple3 returns, single class, _p helper. No print/self._/decorators/hardcoded paths found. Docstring notes 6 missing spec sub-sections (1.3-1.10) but code structure is VBStyle compliant.>][@todos<none>]}
"""
BackupEngine -- authority for backing up the Project Digital Twin database.
Implements Section 1 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: create_backup, verify_backup, restore_backup, list_backups.

# ============================================================
# ERRORS -- Section 1 spec vs. implementation
# Rating: 2/10
# Spec has 10 sub-sections (1.1-1.10). Only 4 implemented.
# ============================================================
# MISSING METHODS:
# 1.3  CreateSecondary  -- copy backup to a different directory. NOT IMPLEMENTED.
# 1.4  StoreOffline      -- copy secondary backup to ~/backups/ or external. NOT IMPLEMENTED.
# 1.5  HashBoth          -- hash primary AND secondary, compare. NOT IMPLEMENTED.
# 1.6  RecordMetadata    -- INSERT backup metadata into snapshots table. NOT IMPLEMENTED.
# 1.7  MakeReadonly      -- os.chmod(backup, 0o444) as a standalone command. NOT IMPLEMENTED.
#                          (chmod is done inside CreateBackup but not exposed as a command.)
# 1.8  RestoreTest       -- copy backup to temp, open, verify tables, delete temp. NOT IMPLEMENTED.
# 1.9  LogSession        -- INSERT observation 'backup_created'. NOT IMPLEMENTED.
# 1.10 NeverModifyOriginal -- enforce db_path != original_db_path via wrapper. NOT IMPLEMENTED.
#
# PARTIAL:
# 1.1  CreatePrimary -- done as create_backup, but does not record to snapshots table.
# 1.2  VerifyIntegrity -- done as verify_backup, but does not compare hash to original.
#
# SPEC SAYS commands: create_backup, verify_backup, restore_backup, list_backups.
# But the 10 sub-sections above require MORE commands than those 4.
# The "Devin task" line at the bottom of Section 1 is a SUMMARY, not the full list.
# The 10 numbered sub-sections are the real requirement.
# ============================================================
"""
import hashlib
import os
import shutil
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_BACKUP_SUFFIX = ".bak.db"
READ_ONLY_MODE = 0o444
CHUNK_SIZE = 65536


class BackupEngine:
    """Authority for database backup, verification and restore operations."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "backup_suffix": DEFAULT_BACKUP_SUFFIX,
                "read_only_mode": READ_ONLY_MODE,
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
        if command == "create_backup":
            return self.CreateBackup(params)
        elif command == "verify_backup":
            return self.VerifyBackup(params)
        elif command == "restore_backup":
            return self.RestoreBackup(params)
        elif command == "list_backups":
            return self.ListBackups(params)
        elif command == "create_secondary":
            return self.CreateSecondary(params)
        elif command == "store_offline":
            return self.StoreOffline(params)
        elif command == "hash_both":
            return self.HashBoth(params)
        elif command == "record_metadata":
            return self.RecordMetadata(params)
        elif command == "make_readonly":
            return self.MakeReadonly(params)
        elif command == "restore_test":
            return self.RestoreTest(params)
        elif command == "log_session":
            return self.LogSession(params)
        elif command == "never_modify_original":
            return self.NeverModifyOriginal(params)
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

    def HashFile(self, path):
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            chunk = fh.read(CHUNK_SIZE)
            while chunk:
                digest.update(chunk)
                chunk = fh.read(CHUNK_SIZE)
        return digest.hexdigest()

    def CreateBackup(self, params):
        db_path = self._p(params, "db_path", self.state["config"]["db_path"])
        suffix = self._p(
            params, "backup_suffix", self.state["config"]["backup_suffix"]
        )
        read_only = self._p(
            params, "read_only", True
        )
        if not os.path.isfile(db_path):
            return (0, None, ("DB_NOT_FOUND", "Database file not found: " + db_path, 0))
        backup_path = self._p(params, "backup_path", db_path + suffix)
        try:
            shutil.copy2(db_path, backup_path)
        except OSError as exc:
            return (0, None, ("COPY_FAILED", str(exc), 0))
        original_hash = self.HashFile(db_path)
        backup_hash = self.HashFile(backup_path)
        if original_hash != backup_hash:
            return (
                0,
                None,
                ("HASH_MISMATCH", "Backup hash does not match original", 0),
            )
        if read_only:
            try:
                os.chmod(backup_path, self.state["config"]["read_only_mode"])
            except OSError as exc:
                return (0, None, ("CHMOD_FAILED", str(exc), 0))
        record = {
            "backup_path": backup_path,
            "original_path": db_path,
            "hash": backup_hash,
            "size": os.path.getsize(backup_path),
            "created": datetime.now(timezone.utc).isoformat(),
            "read_only": bool(read_only),
        }
        self.state["catalog"].append(record)
        return (1, record, None)

    def VerifyBackup(self, params):
        backup_path = self._p(params, "backup_path")
        if not backup_path:
            return (0, None, ("MISSING_PARAM", "backup_path required", 0))
        if not os.path.isfile(backup_path):
            return (0, None, ("BACKUP_NOT_FOUND", backup_path, 0))
        try:
            conn = sqlite3.connect(backup_path)
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check")
            result = cur.fetchone()[0]
            conn.close()
        except sqlite3.Error as exc:
            return (0, None, ("INTEGRITY_ERROR", str(exc), 0))
        backup_hash = self.HashFile(backup_path)
        record = {
            "backup_path": backup_path,
            "hash": backup_hash,
            "size": os.path.getsize(backup_path),
            "integrity": result,
            "ok": result == "ok",
        }
        return (1, record, None)

    def RestoreBackup(self, params):
        backup_path = self._p(params, "backup_path")
        target_path = self._p(params, "target_path", self.state["config"]["db_path"])
        if not backup_path:
            return (0, None, ("MISSING_PARAM", "backup_path required", 0))
        if not os.path.isfile(backup_path):
            return (0, None, ("BACKUP_NOT_FOUND", backup_path, 0))
        confirm = self._p(params, "confirm", False)
        if not confirm:
            return (
                0,
                None,
                ("CONFIRM_REQUIRED", "Set confirm=True to restore", 0),
            )
        try:
            shutil.copy2(backup_path, target_path)
        except OSError as exc:
            return (0, None, ("RESTORE_FAILED", str(exc), 0))
        record = {
            "backup_path": backup_path,
            "target_path": target_path,
            "hash": self.HashFile(target_path),
            "size": os.path.getsize(target_path),
        }
        return (1, record, None)

    def ListBackups(self, params):
        db_path = self._p(params, "db_path", self.state["config"]["db_path"])
        directory = self._p(params, "directory", os.path.dirname(db_path))
        suffix = self._p(
            params, "backup_suffix", self.state["config"]["backup_suffix"]
        )
        backups = []
        if os.path.isdir(directory):
            for name in sorted(os.listdir(directory)):
                if name.endswith(suffix):
                    full = os.path.join(directory, name)
                    try:
                        backups.append(
                            {
                                "backup_path": full,
                                "size": os.path.getsize(full),
                                "hash": self.HashFile(full),
                            }
                        )
                    except OSError:
                        continue
        self.state["results"] = backups
        return (1, backups, None)

    def Connect(self):
        if self.state["db_conn"] is None:
            self.state["db_conn"] = sqlite3.connect(
                self.state["config"]["db_path"]
            )
        return self.state["db_conn"]

    def CreateSecondary(self, params):
        # 1.3 Create Secondary Backup: copy primary backup to a different directory
        primary = self._p(params, "backup_path")
        if not primary:
            primary_res = self.CreateBackup(params)
            if primary_res[0] != 1:
                return primary_res
            primary = primary_res[1]["backup_path"]
        if not os.path.isfile(primary):
            return (0, None, ("BACKUP_NOT_FOUND", primary, 0))
        secondary_dir = self._p(params, "secondary_dir")
        if not secondary_dir:
            return (0, None, ("MISSING_PARAM", "secondary_dir required", 0))
        try:
            os.makedirs(secondary_dir, exist_ok=True)
        except OSError as exc:
            return (0, None, ("MKDIR_FAILED", str(exc), 0))
        secondary_path = self._p(
            params, "secondary_path",
            os.path.join(secondary_dir, os.path.basename(primary)),
        )
        try:
            shutil.copy2(primary, secondary_path)
        except OSError as exc:
            return (0, None, ("COPY_FAILED", str(exc), 0))
        record = {
            "primary_path": primary,
            "secondary_path": secondary_path,
            "secondary_hash": self.HashFile(secondary_path),
            "size": os.path.getsize(secondary_path),
        }
        self.state["catalog"].append(record)
        return (1, record, None)

    def StoreOffline(self, params):
        # 1.4 Store Secondary Backup Offline: copy to ~/backups/ or external
        source = self._p(params, "source_path")
        if not source or not os.path.isfile(source):
            return (0, None, ("MISSING_PARAM", "source_path required", 0))
        offline_dir = self._p(
            params, "offline_dir",
            os.path.join(os.path.expanduser("~"), "backups"),
        )
        try:
            os.makedirs(offline_dir, exist_ok=True)
        except OSError as exc:
            return (0, None, ("MKDIR_FAILED", str(exc), 0))
        dest = self._p(
            params, "dest_path",
            os.path.join(offline_dir, os.path.basename(source)),
        )
        try:
            shutil.copy2(source, dest)
        except OSError as exc:
            return (0, None, ("COPY_FAILED", str(exc), 0))
        record = {
            "source_path": source,
            "offline_path": dest,
            "offline_hash": self.HashFile(dest),
            "size": os.path.getsize(dest),
        }
        self.state["catalog"].append(record)
        return (1, record, None)

    def HashBoth(self, params):
        # 1.5 Hash Both Backups: hash primary and secondary, compare
        primary = self._p(params, "primary_path")
        secondary = self._p(params, "secondary_path")
        if not primary or not secondary:
            return (0, None, ("MISSING_PARAM", "primary_path and secondary_path required", 0))
        if not os.path.isfile(primary):
            return (0, None, ("PRIMARY_NOT_FOUND", primary, 0))
        if not os.path.isfile(secondary):
            return (0, None, ("SECONDARY_NOT_FOUND", secondary, 0))
        primary_hash = self.HashFile(primary)
        secondary_hash = self.HashFile(secondary)
        record = {
            "primary_path": primary,
            "secondary_path": secondary,
            "primary_hash": primary_hash,
            "secondary_hash": secondary_hash,
            "match": primary_hash == secondary_hash,
        }
        if primary_hash != secondary_hash:
            return (1, record, ("HASH_MISMATCH", "Primary and secondary hashes differ", 0))
        return (1, record, None)

    def RecordMetadata(self, params):
        # 1.6 Record Backup Metadata: INSERT into snapshots table
        backup_path = self._p(params, "backup_path")
        if not backup_path:
            return (0, None, ("MISSING_PARAM", "backup_path required", 0))
        if not os.path.isfile(backup_path):
            return (0, None, ("BACKUP_NOT_FOUND", backup_path, 0))
        snapshot_type = self._p(params, "snapshot_type", "manual")
        notes = self._p(params, "notes", "backup_engine RecordMetadata")
        file_id = self._p(params, "file_id")
        class_id = self._p(params, "class_id")
        method_id = self._p(params, "method_id")
        content = self._p(params, "content", backup_path)
        backup_hash = self.HashFile(backup_path)
        created = datetime.now(timezone.utc).isoformat()
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO snapshots (snapshot_type, file_id, class_id, "
                "method_id, content, hash, created, notes) VALUES "
                "(?,?,?,?,?,?,?,?)",
                (snapshot_type, file_id, class_id, method_id, content,
                 backup_hash, created, notes),
            )
            conn.commit()
            snapshot_id = cur.lastrowid
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        record = {
            "snapshot_id": snapshot_id,
            "backup_path": backup_path,
            "hash": backup_hash,
            "snapshot_type": snapshot_type,
            "created": created,
        }
        return (1, record, None)

    def MakeReadonly(self, params):
        # 1.7 Make Backups Read-Only: os.chmod(backup_path, 0o444) standalone
        backup_path = self._p(params, "backup_path")
        if not backup_path:
            return (0, None, ("MISSING_PARAM", "backup_path required", 0))
        if not os.path.isfile(backup_path):
            return (0, None, ("BACKUP_NOT_FOUND", backup_path, 0))
        mode = self._p(params, "mode", self.state["config"]["read_only_mode"])
        try:
            os.chmod(backup_path, mode)
        except OSError as exc:
            return (0, None, ("CHMOD_FAILED", str(exc), 0))
        record = {
            "backup_path": backup_path,
            "mode": oct(mode),
            "readonly": True,
        }
        return (1, record, None)

    def RestoreTest(self, params):
        # 1.8 Create Restore Test: copy backup to temp, open, verify tables, delete
        import tempfile
        backup_path = self._p(params, "backup_path")
        if not backup_path:
            return (0, None, ("MISSING_PARAM", "backup_path required", 0))
        if not os.path.isfile(backup_path):
            return (0, None, ("BACKUP_NOT_FOUND", backup_path, 0))
        expected_tables = self._p(params, "expected_tables", [])
        temp_dir = tempfile.mkdtemp(prefix="restore_test_")
        temp_path = os.path.join(temp_dir, os.path.basename(backup_path))
        try:
            shutil.copy2(backup_path, temp_path)
        except OSError as exc:
            return (0, None, ("COPY_FAILED", str(exc), 0))
        tables = []
        integrity = None
        try:
            conn = sqlite3.connect(temp_path)
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check")
            integrity = cur.fetchone()[0]
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [r[0] for r in cur.fetchall()]
            conn.close()
        except sqlite3.Error as exc:
            return (0, None, ("RESTORE_TEST_ERROR", str(exc), 0))
        missing = [t for t in expected_tables if t not in tables]
        try:
            shutil.rmtree(temp_dir)
        except OSError:
            pass
        ok = integrity == "ok" and len(missing) == 0
        record = {
            "backup_path": backup_path,
            "integrity": integrity,
            "tables": tables,
            "expected_missing": missing,
            "ok": ok,
        }
        if not ok:
            return (1, record, ("RESTORE_TEST_FAIL", "Restore test failed", 0))
        return (1, record, None)

    def LogSession(self, params):
        # 1.9 Log Backup Session: INSERT observation 'backup_created'
        backup_path = self._p(params, "backup_path")
        subject = self._p(params, "subject", "backup_created")
        evidence = self._p(params, "evidence", backup_path or "")
        confidence = self._p(params, "confidence", 100.0)
        created = datetime.now(timezone.utc).isoformat()
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO observations (observation_type, subject, "
                "evidence, confidence, created) VALUES (?,?,?,?,?)",
                ("fact", subject, evidence, confidence, created),
            )
            conn.commit()
            obs_id = cur.lastrowid
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        record = {
            "observation_id": obs_id,
            "subject": subject,
            "evidence": evidence,
            "created": created,
        }
        return (1, record, None)

    def NeverModifyOriginal(self, params):
        # 1.10 Never Modify Original Database: enforce db_path != original_db_path
        target_path = self._p(params, "target_path")
        if not target_path:
            return (0, None, ("MISSING_PARAM", "target_path required", 0))
        original = self.state["config"]["db_path"]
        if os.path.abspath(target_path) == os.path.abspath(original):
            return (
                0,
                None,
                ("ORIGINAL_PROTECTED",
                 "Refusing to modify original database: " + original, 0),
            )
        return (1, {"target_path": target_path, "original": original,
                    "protected": True}, None)
