#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/file_forensics.py"
# date="2026-06-26" author="Devin" session_id="phase-orchestration"
# context="Project Digital Twin Section 40 File Forensics"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="file_forensics.py" domain="twin_fileforensics" authority="FileForensics"}
# [@SUMMARY]{summary="File forensics authority that gets metadata, rename history, hash timelines, and permission checks for files."}
# [@CLASS]{class="FileForensics" domain="fileforensics" authority="single"}
# [@METHOD]{method="get_metadata" type="command"}
# [@METHOD]{method="rename_history" type="command"}
# [@METHOD]{method="hash_timeline" type="command"}
# [@METHOD]{method="permissions_check" type="command"}
# [@METHOD]{method="file_signature" type="command"}
# [@METHOD]{method="encoding_detection" type="command"}
# [@METHOD]{method="move_history" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<FileForensics: gets metadata, rename history, hash timelines, permission checks, file signatures, encoding detection. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
FileForensics -- File forensics authority.
Implements Section 40 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: get_metadata, rename_history, hash_timeline, permissions_check,
          file_signature, encoding_detection, move_history.
"""
import os
import json
import hashlib
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50

try:
    import chardet
    CHARDET_AVAILABLE = True
except Exception:
    CHARDET_AVAILABLE = False


class FileForensics:
    """File forensics authority."""

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
        if command == "get_metadata":
            return self.GetMetadata(params)
        elif command == "rename_history":
            return self.RenameHistory(params)
        elif command == "hash_timeline":
            return self.HashTimeline(params)
        elif command == "permissions_check":
            return self.PermissionsCheck(params)
        elif command == "file_signature":
            return self.FileSignature(params)
        elif command == "encoding_detection":
            return self.EncodingDetection(params)
        elif command == "move_history":
            return self.MoveHistory(params)

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

    def ResolvePath(self, params):
        # helper: resolve path from file_id or path param
        file_id = self._p(params, "file_id")
        path = self._p(params, "path")
        conn = self.Connect()
        cur = conn.cursor()
        if file_id:
            cur.execute("SELECT path FROM files WHERE file_id=?", (file_id,))
            row = cur.fetchone()
            if not row:
                return (0, None, ("NOT_FOUND", "file not found", 0))
            path = row[0]
        return (1, path, None)

    def GetMetadata(self, params):
        # 40.1 Creation Date, 40.2 Modification History, 40.5 Ownership, 40.6 Permissions
        res = self.ResolvePath(params)
        if res[0] == 0:
            return res
        path = res[1]
        if not path or not os.path.isfile(path):
            return (0, None, ("NO_FILE", "File not found", 0))
        stat = os.stat(path)
        try:
            import pwd
            owner = pwd.getpwuid(stat.st_uid).pw_name
        except Exception:
            owner = stat.st_uid
        try:
            import grp
            group = grp.getgrgid(stat.st_gid).gr_name
        except Exception:
            group = stat.st_gid
        metadata = {
            "path": path, "size": stat.st_size,
            "creation": stat.st_ctime, "modification": stat.st_mtime,
            "metadata_change": stat.st_ctime,
            "owner_uid": stat.st_uid, "owner": owner,
            "group_gid": stat.st_gid, "group": group,
            "permissions": oct(stat.st_mode & 0o777),
            "permissions_raw": stat.st_mode,
            "device": stat.st_dev, "inode": stat.st_ino,
            "nlink": stat.st_nlink,
        }
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                    "VALUES (?, ?, ?, ?, ?)",
                    ("fact", "file_metadata:" + path, json.dumps(metadata), 50,
                     datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (1, metadata, None)

    def RenameHistory(self, params):
        # 40.3 Rename History: track file_name changes in files table via version column
        file_id = self._p(params, "file_id")
        file_name = self._p(params, "file_name")
        if not file_id and not file_name:
            return (0, None, ("NO_PARAM", "file_id or file_name required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        if file_id:
            cur.execute("SELECT file_id, file_name, path, version, modified, status "
                        "FROM files WHERE file_id=? ORDER BY version", (file_id,))
        else:
            cur.execute("SELECT file_id, file_name, path, version, modified, status "
                        "FROM files WHERE file_name LIKE ? ORDER BY version",
                        ("%" + file_name + "%",))
        rows = cur.fetchall()
        history = []
        prev_name = None
        for r in rows:
            entry = {"file_id": r[0], "file_name": r[1], "path": r[2],
                     "version": r[3], "modified": r[4], "status": r[5]}
            if prev_name is not None and r[1] != prev_name:
                entry["renamed_from"] = prev_name
                entry["renamed_to"] = r[1]
            prev_name = r[1]
            history.append(entry)
        return (1, {"rename_history": history, "count": len(history)}, None)

    def HashTimeline(self, params):
        # 40.9 Hash Timeline: SELECT hash, modified, version from files ORDER BY modified
        file_id = self._p(params, "file_id")
        conn = self.Connect()
        cur = conn.cursor()
        if file_id:
            cur.execute("SELECT file_id, file_name, hash, modified, version, size "
                        "FROM files WHERE file_id=? ORDER BY modified", (file_id,))
        else:
            cur.execute("SELECT file_id, file_name, hash, modified, version, size "
                        "FROM files ORDER BY modified")
        results = []
        for r in cur.fetchall():
            results.append({"file_id": r[0], "file_name": r[1], "hash": r[2],
                            "modified": r[3], "version": r[4], "size": r[5]})
        return (1, {"hash_timeline": results, "count": len(results)}, None)

    def PermissionsCheck(self, params):
        # 40.6 Permissions: check file permissions against expected
        res = self.ResolvePath(params)
        if res[0] == 0:
            return res
        path = res[1]
        if not path or not os.path.isfile(path):
            return (0, None, ("NO_FILE", "File not found", 0))
        stat = os.stat(path)
        perms = oct(stat.st_mode & 0o777)
        expected = self._p(params, "expected_perms", "0o644")
        expected_clean = expected.replace("0o", "") if isinstance(expected, str) else str(expected)
        actual_clean = perms.replace("0o", "")
        matches = (perms == expected) or (actual_clean == expected_clean)
        result = {
            "permissions": perms, "expected": expected, "matches": matches,
            "readable": os.access(path, os.R_OK),
            "writable": os.access(path, os.W_OK),
            "executable": os.access(path, os.X_OK),
        }
        if not matches:
            result["violation"] = "Permissions " + perms + " do not match expected " + str(expected)
        return (1, result, None)

    def FileSignature(self, params):
        # 40.8 File Signature: first 16 bytes as hex (magic number / file type detection)
        res = self.ResolvePath(params)
        if res[0] == 0:
            return res
        path = res[1]
        if not path or not os.path.isfile(path):
            return (0, None, ("NO_FILE", "File not found", 0))
        try:
            with open(path, "rb") as f:
                header = f.read(16)
        except Exception as exc:
            return (0, None, ("READ_ERROR", str(exc), 0))
        hex_sig = header.hex()
        file_type = self.DetectFileType(header)
        # compute full sha256 hash too
        try:
            with open(path, "rb") as f:
                full_hash = hashlib.sha256(f.read()).hexdigest()
        except Exception:
            full_hash = None
        return (1, {"path": path, "signature_hex": hex_sig, "file_type": file_type,
                    "sha256": full_hash}, None)

    def DetectFileType(self, header):
        # magic number detection
        if header.startswith(b"\x7fELF"):
            return "ELF executable"
        if header.startswith(b"\xca\xfe\xba\xbe"):
            return "Java class"
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "PNG image"
        if header.startswith(b"\xff\xd8\xff"):
            return "JPEG image"
        if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
            return "GIF image"
        if header.startswith(b"PK\x03\x04"):
            return "ZIP archive"
        if header.startswith(b"\x1f\x8b"):
            return "GZIP archive"
        if header.startswith(b"#!/"):
            return "Script (shebang)"
        if header.startswith(b"\xfe\xff") or header.startswith(b"\xff\xfe"):
            return "Unicode text (BOM)"
        if header[:4] == b"%PDF":
            return "PDF document"
        # python source heuristic
        try:
            header.decode("ascii")
            return "Text/ASCII"
        except Exception:
            return "Binary/Unknown"

    def EncodingDetection(self, params):
        # 40.7 Encoding: chardet.detect() if available
        res = self.ResolvePath(params)
        if res[0] == 0:
            return res
        path = res[1]
        if not path or not os.path.isfile(path):
            return (0, None, ("NO_FILE", "File not found", 0))
        try:
            with open(path, "rb") as f:
                raw = f.read(8192)
        except Exception as exc:
            return (0, None, ("READ_ERROR", str(exc), 0))
        if CHARDET_AVAILABLE:
            detected = chardet.detect(raw)
            return (1, {"path": path, "encoding": detected.get("encoding"),
                        "confidence": detected.get("confidence"),
                        "language": detected.get("language"),
                        "chardet_available": True}, None)
        # fallback: simple heuristic
        encoding = "utf-8"
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                raw.decode("latin-1")
                encoding = "latin-1"
            except Exception:
                encoding = "binary"
        return (1, {"path": path, "encoding": encoding,
                    "chardet_available": False,
                    "note": "chardet not installed, heuristic used"}, None)

    def MoveHistory(self, params):
        # 40.4 Move History: track path changes in files table
        file_id = self._p(params, "file_id")
        file_name = self._p(params, "file_name")
        if not file_id and not file_name:
            return (0, None, ("NO_PARAM", "file_id or file_name required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        if file_id:
            cur.execute("SELECT file_id, file_name, path, version, modified "
                        "FROM files WHERE file_id=? ORDER BY version", (file_id,))
        else:
            cur.execute("SELECT file_id, file_name, path, version, modified "
                        "FROM files WHERE file_name LIKE ? ORDER BY version",
                        ("%" + file_name + "%",))
        rows = cur.fetchall()
        history = []
        prev_path = None
        for r in rows:
            entry = {"file_id": r[0], "file_name": r[1], "path": r[2],
                     "version": r[3], "modified": r[4]}
            if prev_path is not None and r[2] != prev_path:
                entry["moved_from"] = prev_path
                entry["moved_to"] = r[2]
            prev_path = r[2]
            history.append(entry)
        return (1, {"move_history": history, "count": len(history)}, None)

