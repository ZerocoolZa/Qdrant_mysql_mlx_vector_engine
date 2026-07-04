#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/backup_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 1: Backup Phase -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="backup_engine.py" domain="twin_backup" authority="BackupEngine"}
# [@SUMMARY]{summary="Backup authority: primary backup, integrity verify, secondary backup, offline storage, hash both, record metadata, read-only, restore test, log session, never modify original."}
# [@CLASS]{class="BackupEngine" domain="backup" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="create_primary" type="command"}
# [@METHOD]{method="verify_integrity" type="command"}
# [@METHOD]{method="create_secondary" type="command"}
# [@METHOD]{method="store_offline" type="command"}
# [@METHOD]{method="hash_both" type="command"}
# [@METHOD]{method="record_metadata" type="command"}
# [@METHOD]{method="make_readonly" type="command"}
# [@METHOD]{method="restore_test" type="command"}
# [@METHOD]{method="log_session" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import hashlib
import os
import shutil
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class BackupEngine:
    """Authority for backup creation, verification, and restore testing."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "backup_dir": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "backups"
                ),
                "offline_dir": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "offline"
                ),
            },
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "primary_path": None,
            "secondary_path": None,
            "primary_hash": None,
            "secondary_hash": None,
            "session_log": [],
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "create_primary":
            return self.CreatePrimary(params)
        elif command == "verify_integrity":
            return self.VerifyIntegrity(params)
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

    def Now(self):
        return (1, datetime.now(timezone.utc).isoformat(), None)

    def ComputeHash(self, path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return (1, h.hexdigest(), None)

    def CreatePrimary(self, params):
        source = self._p(params, "source_path", self.state["config"]["db_path"])
        if not os.path.isfile(source):
            return (0, None, ("SOURCE_NOT_FOUND", source, 0))
        backup_dir = self.state["config"]["backup_dir"]
        os.makedirs(backup_dir, exist_ok=True)
        now_res = self.Now()
        dest = os.path.join(backup_dir, "primary_" + now_res[1].replace(":", "-") + ".db")
        shutil.copy2(source, dest)
        self.state["primary_path"] = dest
        now_res = self.Now()
        record = {"source": source, "backup": dest, "created": now_res[1]}
        self.state["catalog"].append(record)
        return (1, record, None)

    def VerifyIntegrity(self, params):
        path = self._p(params, "backup_path", self.state["primary_path"])
        if path is None or not os.path.isfile(path):
            return (0, None, ("BACKUP_NOT_FOUND", str(path), 0))
        try:
            conn = sqlite3.connect(path)
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check")
            result = cur.fetchone()[0]
            conn.close()
        except sqlite3.Error as exc:
            return (0, None, ("INTEGRITY_FAILED", str(exc), 0))
        record = {"backup": path, "integrity": result, "ok": result == "ok"}
        self.state["results"] = record
        return (1, record, None)

    def CreateSecondary(self, params):
        source = self._p(params, "source_path", self.state["primary_path"])
        if source is None or not os.path.isfile(source):
            return (0, None, ("PRIMARY_NOT_FOUND", "Create primary first", 0))
        backup_dir = self.state["config"]["backup_dir"]
        now_res = self.Now()
        dest = os.path.join(
            backup_dir, "secondary_" + now_res[1].replace(":", "-") + ".db"
        )
        shutil.copy2(source, dest)
        self.state["secondary_path"] = dest
        now_res = self.Now()
        record = {"source": source, "backup": dest, "created": now_res[1]}
        self.state["catalog"].append(record)
        return (1, record, None)

    def StoreOffline(self, params):
        source = self._p(params, "backup_path", self.state["secondary_path"])
        if source is None or not os.path.isfile(source):
            return (0, None, ("SECONDARY_NOT_FOUND", "Create secondary first", 0))
        offline_dir = self.state["config"]["offline_dir"]
        os.makedirs(offline_dir, exist_ok=True)
        dest = os.path.join(offline_dir, os.path.basename(source))
        shutil.move(source, dest)
        self.state["secondary_path"] = dest
        now_res = self.Now()
        record = {"moved_from": source, "offline_path": dest, "stored": now_res[1]}
        self.state["catalog"].append(record)
        return (1, record, None)

    def HashBoth(self, params):
        primary = self.state["primary_path"]
        secondary = self.state["secondary_path"]
        if primary is None or not os.path.isfile(primary):
            return (0, None, ("PRIMARY_NOT_FOUND", "Create primary first", 0))
        p_res = self.ComputeHash(primary)
        p_hash = p_res[1]
        self.state["primary_hash"] = p_hash
        s_hash = None
        if secondary and os.path.isfile(secondary):
            s_res = self.ComputeHash(secondary)
            s_hash = s_res[1]
            self.state["secondary_hash"] = s_hash
        record = {"primary_hash": p_hash, "secondary_hash": s_hash}
        self.state["results"] = record
        return (1, record, None)

    def RecordMetadata(self, params):
        record = {
            "primary_path": self.state["primary_path"],
            "secondary_path": self.state["secondary_path"],
            "primary_hash": self.state["primary_hash"],
            "secondary_hash": self.state["secondary_hash"],
            "timestamp": self.Now()[1],
        }
        self.state["session_log"].append(record)
        return (1, record, None)

    def MakeReadonly(self, params):
        targets = []
        for path in [self.state["primary_path"], self.state["secondary_path"]]:
            if path and os.path.isfile(path):
                os.chmod(path, 0o444)
                targets.append(path)
        now_res = self.Now()
        record = {"made_readonly": targets, "timestamp": now_res[1]}
        self.state["catalog"].append(record)
        return (1, record, None)

    def RestoreTest(self, params):
        backup = self._p(params, "backup_path", self.state["primary_path"])
        if backup is None or not os.path.isfile(backup):
            return (0, None, ("BACKUP_NOT_FOUND", str(backup), 0))
        test_path = backup + ".restore_test"
        shutil.copy2(backup, test_path)
        try:
            conn = sqlite3.connect(test_path)
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check")
            integrity = cur.fetchone()[0]
            conn.close()
            os.remove(test_path)
        except sqlite3.Error as exc:
            if os.path.isfile(test_path):
                os.remove(test_path)
            return (0, None, ("RESTORE_TEST_FAILED", str(exc), 0))
        record = {"backup": backup, "integrity": integrity,
                  "test_passed": integrity == "ok"}
        self.state["results"] = record
        return (1, record, None)

    def LogSession(self, params):
        now_res = self.Now()
        log = {
            "session_id": now_res[1],
            "primary": self.state["primary_path"],
            "secondary": self.state["secondary_path"],
            "primary_hash": self.state["primary_hash"],
            "secondary_hash": self.state["secondary_hash"],
            "entries": len(self.state["catalog"]),
        }
        self.state["session_log"].append(log)
        return (1, log, None)
