#!/usr/bin/env python3
# [@GHOST]{[@file<pb_reader.py>][@domain<chat_mover>][@role<pb_reader>][@auth<devin>][@date<2026-06-29>][@ver<1.0>][@context<Decrypt and search Cascade .pb chat files in RAM>]}
# [@VBSTYLE]{[@auth<devin>][@role<pb_reader>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{PB Reader — decrypts Windsurf Cascade .pb chat files, parses protobuf wire-format, loads into in-RAM SQLite, provides CLI search/read/export}
# [@FILEID]{pb_reader.py}
# [@CLASS]{PbReader}
# [@METHOD]{Run,scan,list,read,search,export,decrypt_file,parse_trajectory,parse_step,parse_checkpoint,load_to_ram,read_state,set_config}

"""
PB Reader — Decrypt, parse, and search Windsurf Cascade .pb chat files.

Usage:
    python3 pb_reader.py scan                          # list all .pb files found
    python3 pb_reader.py list                          # list loaded trajectories
    python3 pb_reader.py load <file.pb>                # load one file into RAM
    python3 pb_reader.py load-all                      # load all .pb files into RAM
    python3 pb_reader.py read <file.pb>                # show chat conversation
    python3 pb_reader.py read <file.pb> --step 5       # show specific step
    python3 pb_reader.py search "query text"           # search all loaded chats
    python3 pb_reader.py search "query" --user         # search only user messages
    python3 pb_reader.py search "query" --assistant    # search only assistant messages
    python3 pb_reader.py export <file.pb> <outdir>     # export to markdown
    python3 pb_reader.py stats                         # show RAM DB statistics

Encryption:
    Algorithm: AES-256-GCM
    Key: 32-byte ASCII string hardcoded in language_server_macos_arm binary
    File layout: [12-byte nonce][ciphertext][16-byte GCM tag]
    Plaintext: raw protobuf-encoded CortexTrajectory / ImplicitTrajectory / CortexMemory
"""

import os
import sys
import json
import re
import hashlib
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ════════════════════════════════════════════════════════════════
# UPPERCASE CONSTANTS (class level)
# ════════════════════════════════════════════════════════════════

AES_KEY = bytes.fromhex(
    "73616665436f646569756d776f726c644b655973656372657442616c6c6f6f6e"
)
assert AES_KEY == b"safeCodeiumworldKeYsecretBalloon"
assert len(AES_KEY) == 32

NONCE_SIZE = 12
TAG_SIZE = 16

WINDSURF_ROOT = os.path.expanduser("~/.codeium/windsurf")
PB_DIRS = ["cascade", "implicit", "memories"]

# Protobuf wire types
WIRE_VARINT = 0
WIRE_64BIT = 1
WIRE_LENGTH = 2
WIRE_32BIT = 5
WIRE_GROUP_START = 3
WIRE_GROUP_END = 4

# CortexTrajectoryStep variant field numbers (empirically discovered)
VARIANT_USER_INPUT = 19
VARIANT_PLANNER_RESPONSE = 20
VARIANT_RUN_COMMAND = 28
VARIANT_CHECKPOINT = 30
VARIANT_FILE_CONTEXT = 15
VARIANT_COMMAND_RESULT = 37

# Step type names (partial — filled empirically)
STEP_TYPE_NAMES = {
    0: "UNSPECIFIED",
    1: "PLAN_INPUT",
    2: "MQUERY",
    3: "CODE_ACTION",
    4: "FINISH",
    5: "GREP_SEARCH",
    6: "DUMMY",
    56: "CHECKPOINT",
}


# ════════════════════════════════════════════════════════════════
# PROTOBUF WIRE-FORMAT PARSING (standalone, no .proto needed)
# ════════════════════════════════════════════════════════════════

def read_varint(buf, pos):
    """Read a varint. Return (value, new_pos)."""
    val = 0
    shift = 0
    while pos < len(buf):
        b = buf[pos]
        pos += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            return val, pos
        shift += 7
    raise ValueError("unterminated varint")


def parse_tag(tag):
    """Return (field_no, wire_type)."""
    return tag >> 3, tag & 7


def skip_value(buf, pos, wire_type):
    """Skip a single field value. Return new pos."""
    if wire_type == WIRE_VARINT:
        _, pos = read_varint(buf, pos)
    elif wire_type == WIRE_64BIT:
        pos += 8
    elif wire_type == WIRE_LENGTH:
        length, pos = read_varint(buf, pos)
        pos += length
    elif wire_type == WIRE_32BIT:
        pos += 4
    elif wire_type == WIRE_GROUP_START:
        while True:
            t, pos = read_varint(buf, pos)
            _, wt = parse_tag(t)
            if wt == WIRE_GROUP_END:
                return pos
            pos = skip_value(buf, pos, wt)
    else:
        raise ValueError("unknown wire type %d" % wire_type)
    return pos


def iter_fields(buf, start=0, end=None):
    """Yield (field_no, wire_type, value_offset, value_bytes_or_int) over a message."""
    if end is None:
        end = len(buf)
    pos = start
    while pos < end:
        tag, pos = read_varint(buf, pos)
        fno, wt = parse_tag(tag)
        if wt == WIRE_VARINT:
            val, new_pos = read_varint(buf, pos)
            yield fno, wt, pos, val
            pos = new_pos
        elif wt == WIRE_64BIT:
            yield fno, wt, pos, buf[pos:pos + 8]
            pos += 8
        elif wt == WIRE_LENGTH:
            length, lpos = read_varint(buf, pos)
            yield fno, wt, lpos, buf[lpos:lpos + length]
            pos = lpos + length
        elif wt == WIRE_32BIT:
            yield fno, wt, pos, buf[pos:pos + 4]
            pos += 4
        else:
            raise ValueError("wire type %d unsupported at %d" % (wt, pos))


def read_string_field(data, target_fno):
    """Walk a message body, return first string-typed value at field number target_fno."""
    for fno, wt, _off, val in iter_fields(data):
        if fno == target_fno and wt == WIRE_LENGTH and isinstance(val, (bytes, bytearray)):
            try:
                return val.decode("utf-8", errors="replace")
            except Exception:
                return None
    return None


# ════════════════════════════════════════════════════════════════
# TRAJECTORY PARSING
# ════════════════════════════════════════════════════════════════

def parse_trajectory(buf):
    """Parse top-level CortexTrajectory. Returns dict with trajectory_id, cascade_id, steps."""
    info = {
        "trajectory_id": None,
        "cascade_id": None,
        "trajectory_type": None,
        "source": None,
        "steps_count": 0,
        "steps": [],
    }
    for fno, wt, _off, val in iter_fields(buf):
        if fno == 1 and wt == WIRE_LENGTH:
            info["trajectory_id"] = val.decode("utf-8", errors="replace")
        elif fno == 6 and wt == WIRE_LENGTH:
            info["cascade_id"] = val.decode("utf-8", errors="replace")
        elif fno == 4 and wt == WIRE_VARINT:
            info["trajectory_type"] = val
        elif fno == 8 and wt == WIRE_VARINT:
            info["source"] = val
        elif fno == 2 and wt == WIRE_LENGTH:
            info["steps_count"] += 1
            info["steps"].append(val)
    return info


def parse_step(step_buf):
    """Parse a CortexTrajectoryStep. Returns dict with type, status, variant_field, variant_data."""
    out = {
        "type": None,
        "status": None,
        "variant_field": None,
        "variant_data": None,
    }
    for fno, wt, _off, val in iter_fields(step_buf):
        if fno == 1 and wt == WIRE_VARINT:
            out["type"] = val
        elif fno == 4 and wt == WIRE_VARINT:
            out["status"] = val
        elif 7 <= fno <= 110 and wt == WIRE_LENGTH:
            if out["variant_field"] is None:
                out["variant_field"] = fno
                out["variant_data"] = val
    return out


def parse_checkpoint(cp_buf):
    """Parse CortexStepCheckpoint. Returns dict with summary fields."""
    out = {
        "checkpoint_index": None,
        "user_intent": None,
        "session_summary": None,
        "code_change_summary": None,
        "memory_summary": None,
        "conversation_title": None,
        "plan_snapshot": None,
        "intent_only": None,
        "included_step_index_start": None,
        "included_step_index_end": None,
        "included_step_indices": [],
        "edited_files": [],
    }
    for fno, wt, _off, val in iter_fields(cp_buf):
        if fno == 1 and wt == WIRE_VARINT:
            out["checkpoint_index"] = val
        elif fno == 3:
            if wt == WIRE_VARINT:
                out["included_step_indices"].append(val)
            elif wt == WIRE_LENGTH:
                pos = 0
                while pos < len(val):
                    v, pos = read_varint(val, pos)
                    out["included_step_indices"].append(v)
        elif fno == 4 and wt == WIRE_LENGTH:
            out["user_intent"] = val.decode("utf-8", errors="replace")
        elif fno == 5 and wt == WIRE_LENGTH:
            out["session_summary"] = val.decode("utf-8", errors="replace")
        elif fno == 6 and wt == WIRE_LENGTH:
            out["code_change_summary"] = val.decode("utf-8", errors="replace")
        elif fno == 7 and wt == WIRE_LENGTH:
            file_path = None
            for ifno, iwt, _ioff, ival in iter_fields(val):
                if ifno == 1 and iwt == WIRE_LENGTH:
                    file_path = ival.decode("utf-8", errors="replace")
            if file_path:
                out["edited_files"].append(file_path)
        elif fno == 8 and wt == WIRE_LENGTH:
            out["memory_summary"] = val.decode("utf-8", errors="replace")
        elif fno == 9 and wt == WIRE_VARINT:
            out["intent_only"] = bool(val)
        elif fno == 10 and wt == WIRE_LENGTH:
            out["conversation_title"] = val.decode("utf-8", errors="replace")
        elif fno == 11 and wt == WIRE_VARINT:
            out["included_step_index_start"] = val
        elif fno == 12 and wt == WIRE_VARINT:
            out["included_step_index_end"] = val
        elif fno == 13 and wt == WIRE_LENGTH:
            out["plan_snapshot"] = val.decode("utf-8", errors="replace")
    return out


# ════════════════════════════════════════════════════════════════
# PB READER CLASS
# ════════════════════════════════════════════════════════════════

class PbReader:
    """Decrypt, parse, and search Windsurf Cascade .pb chat files.

    Usage:
        r = PbReader()
        ok, data, err = r.Run("scan", {})
        ok, data, err = r.Run("read", {"file": "/path/to/file.pb"})
        ok, data, err = r.Run("search", {"query": "keyword"})
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "db": None,
            "loaded_files": [],
            "scan_results": [],
            "last_error": None,
            "config": {
                "windsurf_root": WINDSURF_ROOT,
                "pb_dirs": PB_DIRS,
            },
        }

    def Run(self, command, params=None):
        """Dispatch entry point. Returns Tuple3."""
        p = params or {}
        dispatch = {
            "scan": self.cmd_scan,
            "list": self.cmd_list,
            "index": self.cmd_index,
            "load": self.cmd_load,
            "load-all": self.cmd_load_all,
            "read": self.cmd_read,
            "search": self.cmd_search,
            "search-sessions": self.cmd_search_sessions,
            "session-detail": self.cmd_session_detail,
            "search-files": self.cmd_search_files,
            "export": self.cmd_export,
            "stats": self.cmd_stats,
            "export-db": self.cmd_export_db,
            "verify-db": self.cmd_verify_db,
            "clean": self.cmd_clean,
            "compress": self.cmd_compress,
            "dry_run": self.cmd_dry_run,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        fn = dispatch.get(command)
        if fn is None:
            return (0, None, ("unknown_command", command, 0))
        return fn(p)

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params=None):
        if not params:
            return (0, None, ("no_params", "set_config needs params", 0))
        cfg = self.state["config"]
        for k, v in params.items():
            if k in cfg:
                cfg[k] = v
        return (1, dict(cfg), None)

    # ── DB ──────────────────────────────────────────────────────

    def _init_db(self):
        """Initialize in-RAM SQLite database."""
        conn = sqlite3.connect(":memory:")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS trajectories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trajectory_id TEXT,
                cascade_id TEXT,
                file_path TEXT UNIQUE,
                file_category TEXT,
                trajectory_type INTEGER,
                source INTEGER,
                steps_count INTEGER,
                decrypted_size INTEGER,
                loaded_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trajectory_fk INTEGER,
                step_index INTEGER,
                step_type INTEGER,
                step_type_name TEXT,
                status INTEGER,
                variant_field INTEGER,
                variant_data BLOB,
                FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id)
            );
            CREATE TABLE IF NOT EXISTS user_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trajectory_fk INTEGER,
                step_index INTEGER,
                prompt TEXT,
                FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id)
            );
            CREATE TABLE IF NOT EXISTS assistant_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trajectory_fk INTEGER,
                step_index INTEGER,
                user_facing TEXT,
                internal_planning TEXT,
                FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id)
            );
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trajectory_fk INTEGER,
                step_index INTEGER,
                command TEXT,
                output TEXT,
                FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id)
            );
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trajectory_fk INTEGER,
                step_index INTEGER,
                checkpoint_index INTEGER,
                conversation_title TEXT,
                user_intent TEXT,
                session_summary TEXT,
                code_change_summary TEXT,
                memory_summary TEXT,
                plan_snapshot TEXT,
                intent_only INTEGER,
                edited_files TEXT,
                FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id)
            );
            CREATE INDEX IF NOT EXISTS idx_steps_traj ON steps(trajectory_fk);
            CREATE INDEX IF NOT EXISTS idx_user_traj ON user_messages(trajectory_fk);
            CREATE INDEX IF NOT EXISTS idx_asst_traj ON assistant_messages(trajectory_fk);
            CREATE INDEX IF NOT EXISTS idx_cmd_traj ON commands(trajectory_fk);
            CREATE INDEX IF NOT EXISTS idx_cp_traj ON checkpoints(trajectory_fk);
        """)
        self.state["db"] = conn
        return conn

    def _get_db(self):
        if self.state["db"] is None:
            self._init_db()
        return self.state["db"]

    # ── DECRYPT ─────────────────────────────────────────────────

    def decrypt_file(self, pb_path):
        """Decrypt a single .pb file. Returns plaintext bytes."""
        data = Path(pb_path).read_bytes()
        if len(data) < NONCE_SIZE + TAG_SIZE:
            raise ValueError("%s too small (%d bytes)" % (pb_path, len(data)))
        nonce = data[:NONCE_SIZE]
        ct_and_tag = data[NONCE_SIZE:]
        return AESGCM(AES_KEY).decrypt(nonce, ct_and_tag, None)

    # ── LOAD ────────────────────────────────────────────────────

    def _load_one(self, pb_path, category):
        """Decrypt, parse, and load one .pb file into RAM DB."""
        conn = self._get_db()
        pt = self.decrypt_file(pb_path)
        info = parse_trajectory(pt)

        # Handle ImplicitTrajectory (wraps CortexTrajectory in field 1)
        if info["steps_count"] == 0 and info["trajectory_id"] is None:
            for fno, wt, _off, val in iter_fields(pt):
                if fno == 1 and wt == WIRE_LENGTH:
                    info = parse_trajectory(val)
                    break

        # Handle CortexMemory (different structure — just store raw)
        raw_traj_id = info["trajectory_id"]
        # Validate: trajectory_id should be a UUID-like string (<= 128 chars, printable)
        if raw_traj_id and (len(raw_traj_id) > 128 or not all(c.isprintable() for c in raw_traj_id[:50])):
            raw_traj_id = None  # Garbage ID — fall back to filename
        traj_id = raw_traj_id or os.path.basename(pb_path).replace(".pb", "")

        conn.execute(
            "INSERT OR REPLACE INTO trajectories "
            "(trajectory_id, cascade_id, file_path, file_category, trajectory_type, source, steps_count, decrypted_size) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (traj_id, info["cascade_id"], str(pb_path), category,
             info["trajectory_type"], info["source"], info["steps_count"], len(pt)),
        )
        fk = conn.execute(
            "SELECT id FROM trajectories WHERE file_path = ?", (str(pb_path),)
        ).fetchone()[0]

        for idx, step_buf in enumerate(info["steps"]):
            step = parse_step(step_buf)
            step_type = step["type"] if step["type"] is not None else -1
            type_name = STEP_TYPE_NAMES.get(step_type, "TYPE_%d" % step_type)

            conn.execute(
                "INSERT INTO steps (trajectory_fk, step_index, step_type, step_type_name, status, variant_field, variant_data) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (fk, idx, step_type, type_name, step["status"],
                 step["variant_field"], step["variant_data"]),
            )

            vf = step["variant_field"]
            vd = step["variant_data"] or b""

            if vf == VARIANT_USER_INPUT:
                prompt = read_string_field(vd, 2) or ""
                conn.execute(
                    "INSERT INTO user_messages (trajectory_fk, step_index, prompt) VALUES (?, ?, ?)",
                    (fk, idx, prompt),
                )
            elif vf == VARIANT_PLANNER_RESPONSE:
                user_facing = read_string_field(vd, 1) or ""
                internal = read_string_field(vd, 3) or ""
                conn.execute(
                    "INSERT INTO assistant_messages (trajectory_fk, step_index, user_facing, internal_planning) "
                    "VALUES (?, ?, ?, ?)",
                    (fk, idx, user_facing, internal),
                )
            elif vf == VARIANT_RUN_COMMAND:
                cmd = read_string_field(vd, 23) or read_string_field(vd, 25) or ""
                output = ""
                for cfno, cwt, _coff, cval in iter_fields(vd):
                    if cfno == 24 and cwt == WIRE_LENGTH and isinstance(cval, (bytes, bytearray)):
                        output = cval.decode("utf-8", errors="replace")
                        break
                conn.execute(
                    "INSERT INTO commands (trajectory_fk, step_index, command, output) VALUES (?, ?, ?, ?)",
                    (fk, idx, cmd, output),
                )
            elif vf == VARIANT_CHECKPOINT:
                cp = parse_checkpoint(vd)
                conn.execute(
                    "INSERT INTO checkpoints "
                    "(trajectory_fk, step_index, checkpoint_index, conversation_title, "
                    "user_intent, session_summary, code_change_summary, memory_summary, "
                    "plan_snapshot, intent_only, edited_files) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (fk, idx, cp["checkpoint_index"], cp["conversation_title"],
                     cp["user_intent"], cp["session_summary"],
                     cp["code_change_summary"], cp["memory_summary"],
                     cp["plan_snapshot"], int(bool(cp["intent_only"])),
                     "\n".join(cp["edited_files"])),
                )

        conn.commit()
        return traj_id, info["steps_count"]

    # ── COMMANDS ────────────────────────────────────────────────

    def cmd_scan(self, params):
        """Scan ~/.codeium/windsurf/ for .pb files."""
        root = self._p(params, "root", self.state["config"]["windsurf_root"])
        results = []
        for subdir in self.state["config"]["pb_dirs"]:
            d = os.path.join(root, subdir)
            if not os.path.isdir(d):
                continue
            for f in sorted(os.listdir(d)):
                if f.endswith(".pb"):
                    fp = os.path.join(d, f)
                    size = os.path.getsize(fp)
                    results.append({
                        "path": fp,
                        "category": subdir,
                        "filename": f,
                        "size_bytes": size,
                        "size_kb": round(size / 1024, 1),
                    })
        self.state["scan_results"] = results
        return (1, results, None)

    def cmd_list(self, params):
        """List loaded trajectories in RAM DB."""
        conn = self._get_db()
        rows = conn.execute(
            "SELECT t.id, t.trajectory_id, t.cascade_id, t.file_path, t.file_category, "
            "t.steps_count, t.decrypted_size, "
            "(SELECT COUNT(*) FROM user_messages WHERE trajectory_fk = t.id) as user_msgs, "
            "(SELECT COUNT(*) FROM assistant_messages WHERE trajectory_fk = t.id) as ai_msgs, "
            "(SELECT COUNT(*) FROM commands WHERE trajectory_fk = t.id) as cmds "
            "FROM trajectories t ORDER BY t.id"
        ).fetchall()
        data = []
        for r in rows:
            data.append({
                "db_id": r[0],
                "trajectory_id": r[1],
                "cascade_id": r[2],
                "file_path": r[3],
                "category": r[4],
                "steps": r[5],
                "decrypted_kb": round(r[6] / 1024, 1) if r[6] else 0,
                "user_msgs": r[7],
                "ai_msgs": r[8],
                "commands": r[9],
            })
        return (1, data, None)

    def cmd_index(self, params):
        """Build a chat_index TABLE in the in-RAM SQLite.

        Creates a real persistent table 'chat_index' in the RAM SQLite DB that
        maps funny_name (UUID.pb filename) to decrypted_name (chat title from
        first user message) plus ALL details from checkpoints, file metadata,
        relative time, and word counts.

        The table persists in RAM until the process exits. You can query it
        with any SQL after calling this once:

            SELECT file_name, chat_name, minutes_ago FROM chat_index ORDER BY minutes_ago;
            SELECT file_name, chat_name FROM chat_index WHERE chat_name LIKE '%mysql%';
            SELECT file_name, total_words FROM chat_index ORDER BY total_words DESC;

        Table schema:
            chat_index(
                id              INTEGER PRIMARY KEY,
                file_name       TEXT,          -- the funny UUID.pb name
                trajectory_id   TEXT,          -- internal UUID
                cascade_id      TEXT,          -- windsurf cascade ID
                category        TEXT,          -- cascade/implicit/memories
                chat_name       TEXT,          -- full first user message (decrypted)
                chat_name_short TEXT,          -- cleaned IDE-style title (first 60 chars, one line)
                checkpoint_title TEXT,         -- from checkpoints.conversation_title
                user_intent     TEXT,          -- from checkpoints.user_intent
                session_summary TEXT,          -- from checkpoints.session_summary
                code_change_summary TEXT,      -- from checkpoints.code_change_summary
                memory_summary  TEXT,          -- from checkpoints.memory_summary
                edited_files    TEXT,          -- from checkpoints.edited_files
                step_count      INTEGER,       -- total steps
                user_msg_count  INTEGER,       -- user messages
                ai_msg_count    INTEGER,       -- assistant messages
                command_count   INTEGER,       -- commands run
                checkpoint_count INTEGER,      -- checkpoints
                total_words     INTEGER,       -- word count across all messages
                decrypted_kb    REAL,          -- decrypted size in KB
                pb_size_kb      REAL,          -- original .pb file size on disk in KB
                pb_modified     TEXT,          -- .pb file last-modified timestamp (ISO)
                minutes_ago     REAL,          -- minutes since pb_modified (relative time)
                loaded_at       TEXT           -- when loaded into RAM
            )

        Optional params:
            query  -- filter RESULTS by chat_name/file_name/trajectory_id (LIKE)
            limit  -- max results to return (default all)
        """
        import time as _time
        from datetime import datetime as _dt

        conn = self._get_db()
        if conn is None:
            return (0, None, ("not_loaded", "No trajectories loaded. Use load-all first.", 0))

        query = self._p(params, "query", "")
        limit = self._p(params, "limit", 0)
        now_ts = _time.time()

        # Step 1: CREATE TABLE chat_index (drop if exists)
        conn.execute("DROP TABLE IF EXISTS chat_index")
        conn.execute(
            "CREATE TABLE chat_index ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  file_name TEXT,"
            "  trajectory_id TEXT,"
            "  cascade_id TEXT,"
            "  category TEXT,"
            "  chat_name TEXT,"
            "  chat_name_short TEXT,"
            "  checkpoint_title TEXT,"
            "  user_intent TEXT,"
            "  session_summary TEXT,"
            "  code_change_summary TEXT,"
            "  memory_summary TEXT,"
            "  edited_files TEXT,"
            "  step_count INTEGER,"
            "  user_msg_count INTEGER,"
            "  ai_msg_count INTEGER,"
            "  command_count INTEGER,"
            "  checkpoint_count INTEGER,"
            "  total_words INTEGER,"
            "  decrypted_kb REAL,"
            "  pb_size_kb REAL,"
            "  pb_modified TEXT,"
            "  minutes_ago REAL,"
            "  loaded_at TEXT"
            ")"
        )
        conn.execute("CREATE INDEX idx_chat_index_name ON chat_index(chat_name)")
        conn.execute("CREATE INDEX idx_chat_index_short ON chat_index(chat_name_short)")
        conn.execute("CREATE INDEX idx_chat_index_file ON chat_index(file_name)")
        conn.execute("CREATE INDEX idx_chat_index_traj ON chat_index(trajectory_id)")
        conn.execute("CREATE INDEX idx_chat_index_time ON chat_index(minutes_ago)")

        # Step 2: INSERT all trajectories with joined details
        rows = conn.execute(
            "SELECT "
            "  t.id as t_id, "
            "  t.file_path, "
            "  t.trajectory_id, "
            "  t.cascade_id, "
            "  t.file_category, "
            "  COALESCE((SELECT prompt FROM user_messages WHERE trajectory_fk = t.id ORDER BY step_index LIMIT 1), '(no user message)') AS chat_name, "
            "  (SELECT conversation_title FROM checkpoints WHERE trajectory_fk = t.id AND conversation_title IS NOT NULL ORDER BY step_index LIMIT 1) AS checkpoint_title, "
            "  (SELECT user_intent FROM checkpoints WHERE trajectory_fk = t.id AND user_intent IS NOT NULL ORDER BY step_index LIMIT 1) AS user_intent, "
            "  (SELECT session_summary FROM checkpoints WHERE trajectory_fk = t.id AND session_summary IS NOT NULL ORDER BY step_index LIMIT 1) AS session_summary, "
            "  (SELECT code_change_summary FROM checkpoints WHERE trajectory_fk = t.id AND code_change_summary IS NOT NULL ORDER BY step_index LIMIT 1) AS code_change_summary, "
            "  (SELECT memory_summary FROM checkpoints WHERE trajectory_fk = t.id AND memory_summary IS NOT NULL ORDER BY step_index LIMIT 1) AS memory_summary, "
            "  (SELECT edited_files FROM checkpoints WHERE trajectory_fk = t.id AND edited_files IS NOT NULL ORDER BY step_index LIMIT 1) AS edited_files, "
            "  t.steps_count, "
            "  (SELECT COUNT(*) FROM user_messages WHERE trajectory_fk = t.id) AS user_msg_count, "
            "  (SELECT COUNT(*) FROM assistant_messages WHERE trajectory_fk = t.id) AS ai_msg_count, "
            "  (SELECT COUNT(*) FROM commands WHERE trajectory_fk = t.id) AS command_count, "
            "  (SELECT COUNT(*) FROM checkpoints WHERE trajectory_fk = t.id) AS checkpoint_count, "
            "  t.decrypted_size, "
            "  t.loaded_at "
            "FROM trajectories t "
            "ORDER BY t.loaded_at DESC"
        ).fetchall()

        inserted = 0
        for r in rows:
            t_id, file_path, traj_id, cascade_id, category, chat_name, cp_title, u_intent, s_sum, cc_sum, m_sum, e_files, steps, um_count, ai_count, cmd_count, cp_count, dec_size, loaded_at = r
            file_name = file_path.split("/")[-1] if file_path else ""

            # File metadata from disk
            pb_modified = None
            pb_size_kb = 0.0
            minutes_ago = None
            if file_path and os.path.isfile(file_path):
                try:
                    st = os.stat(file_path)
                    pb_modified = _dt.fromtimestamp(st.st_mtime).isoformat()
                    pb_size_kb = round(st.st_size / 1024, 1)
                    minutes_ago = round((now_ts - st.st_mtime) / 60.0, 1)
                except Exception:
                    pass

            # Clean chat_name → chat_name_short (IDE-style: first line, max 60 chars)
            chat_name_short = self._make_short_name(chat_name)

            # Total word count across all message types
            total_words = 0
            for um in conn.execute("SELECT prompt FROM user_messages WHERE trajectory_fk = ?", (t_id,)).fetchall():
                total_words += len((um[0] or "").split())
            for am in conn.execute("SELECT user_facing, internal_planning FROM assistant_messages WHERE trajectory_fk = ?", (t_id,)).fetchall():
                total_words += len((am[0] or "").split())
                total_words += len((am[1] or "").split())
            for cmd in conn.execute("SELECT command, output FROM commands WHERE trajectory_fk = ?", (t_id,)).fetchall():
                total_words += len((cmd[0] or "").split())
                total_words += len((cmd[1] or "").split())

            conn.execute(
                "INSERT INTO chat_index (file_name, trajectory_id, cascade_id, category, chat_name, chat_name_short, "
                "checkpoint_title, user_intent, session_summary, code_change_summary, memory_summary, "
                "edited_files, step_count, user_msg_count, ai_msg_count, command_count, checkpoint_count, "
                "total_words, decrypted_kb, pb_size_kb, pb_modified, minutes_ago, loaded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (file_name, traj_id, cascade_id, category, (chat_name or "")[:300], chat_name_short,
                 (cp_title or "")[:300] if cp_title else None,
                 (u_intent or "")[:500] if u_intent else None,
                 (s_sum or "")[:500] if s_sum else None,
                 (cc_sum or "")[:500] if cc_sum else None,
                 (m_sum or "")[:500] if m_sum else None,
                 e_files,
                 steps, um_count, ai_count, cmd_count, cp_count,
                 total_words,
                 round(dec_size / 1024, 1) if dec_size else 0,
                 pb_size_kb, pb_modified, minutes_ago,
                 loaded_at)
            )
            inserted += 1
        conn.commit()

        # Step 3: Query back from the new table (with optional filter)
        qsql = ("SELECT id, file_name, trajectory_id, cascade_id, category, chat_name, chat_name_short, "
                "checkpoint_title, user_intent, session_summary, code_change_summary, memory_summary, "
                "edited_files, step_count, user_msg_count, ai_msg_count, command_count, checkpoint_count, "
                "total_words, decrypted_kb, pb_size_kb, pb_modified, minutes_ago, loaded_at FROM chat_index")
        args = []
        if query:
            qsql += " WHERE chat_name LIKE ? OR chat_name_short LIKE ? OR file_name LIKE ? OR trajectory_id LIKE ?"
            like = "%" + query.replace("%", "\\%").replace("_", "\\_") + "%"
            args = [like, like, like, like]
        qsql += " ORDER BY minutes_ago"
        if limit and limit > 0:
            qsql += " LIMIT ?"
            args.append(limit)

        result_rows = conn.execute(qsql, args).fetchall()
        data = []
        for r in result_rows:
            data.append({
                "id": r[0],
                "file_name": r[1],
                "trajectory_id": r[2],
                "cascade_id": r[3],
                "category": r[4],
                "chat_name": (r[5] or "")[:120],
                "chat_name_short": r[6],
                "checkpoint_title": (r[7] or "")[:120] if r[7] else None,
                "user_intent": (r[8] or "")[:200] if r[8] else None,
                "session_summary": (r[9] or "")[:200] if r[9] else None,
                "code_change_summary": (r[10] or "")[:200] if r[10] else None,
                "memory_summary": (r[11] or "")[:200] if r[11] else None,
                "edited_files": r[12],
                "step_count": r[13],
                "user_msg_count": r[14],
                "ai_msg_count": r[15],
                "command_count": r[16],
                "checkpoint_count": r[17],
                "total_words": r[18],
                "decrypted_kb": r[19],
                "pb_size_kb": r[20],
                "pb_modified": r[21],
                "minutes_ago": r[22],
                "loaded_at": r[23],
            })
        return (1, {"count": len(data), "inserted": inserted, "chats": data}, None)

    def _make_short_name(self, raw_name):
        """Clean a first-user-message into an IDE-style short chat title.

        Rules:
          - Take first non-empty line
          - Strip @ mentions, file paths, leading punctuation
          - Collapse whitespace
          - Truncate to 60 chars
          - If empty after cleaning, return '(empty)'
        """
        if not raw_name:
            return "(empty)"
        # First non-empty line
        lines = [l.strip() for l in raw_name.split("\n") if l.strip()]
        first = lines[0] if lines else raw_name.strip()
        # Strip leading @ mentions like @[path/to/file]
        import re as _re
        first = _re.sub(r'^@\[[^\]]+\]\s*', '', first)
        # Strip leading punctuation/symbols
        first = _re.sub(r'^[.?,!@#~\s]+', '', first)
        # Collapse whitespace
        first = _re.sub(r'\s+', ' ', first).strip()
        # Truncate
        if len(first) > 60:
            first = first[:57] + "..."
        return first if first else "(empty)"

    def cmd_load(self, params):
        """Load one .pb file into RAM DB."""
        fp = self._p(params, "file")
        if not fp:
            return (0, None, ("no_file", "load needs 'file' param", 0))
        fp = os.path.expanduser(fp)
        if not os.path.isfile(fp):
            return (0, None, ("file_not_found", fp, 0))
        category = self._p(params, "category", "unknown")
        try:
            traj_id, steps = self._load_one(fp, category)
            self.state["loaded_files"].append(fp)
            return (1, {"trajectory_id": traj_id, "steps": steps, "file": fp}, None)
        except Exception as e:
            self.state["last_error"] = str(e)
            return (0, None, ("decrypt_failed", str(e), 0))

    def cmd_load_all(self, params):
        """Load all .pb files found via scan."""
        ok, scan_data, _err = self.cmd_scan(params)
        if not ok:
            return (0, None, ("scan_failed", "scan failed", 0))
        results = []
        fail_count = 0
        for item in scan_data:
            try:
                traj_id, steps = self._load_one(item["path"], item["category"])
                results.append({"file": item["path"], "trajectory_id": traj_id, "steps": steps})
                self.state["loaded_files"].append(item["path"])
            except Exception as e:
                fail_count += 1
                results.append({"file": item["path"], "error": str(e)})
        return (1, {"loaded": len(results) - fail_count, "failed": fail_count, "results": results}, None)

    def cmd_read(self, params):
        """Read a .pb file as a chat conversation. Loads if not already loaded."""
        fp = self._p(params, "file")
        if not fp:
            return (0, None, ("no_file", "read needs 'file' param", 0))
        fp = os.path.expanduser(fp)

        # Auto-load if not in DB
        conn = self._get_db()
        row = conn.execute(
            "SELECT id FROM trajectories WHERE file_path = ?", (fp,)
        ).fetchone()
        if row is None:
            category = "unknown"
            for subdir in PB_DIRS:
                if subdir in fp:
                    category = subdir
                    break
            ok, data, err = self.cmd_load({"file": fp, "category": category})
            if not ok:
                return (0, None, err)
            row = conn.execute(
                "SELECT id FROM trajectories WHERE file_path = ?", (fp,)
            ).fetchone()

        fk = row[0]
        step_filter = self._p(params, "step")

        # Get trajectory info
        traj = conn.execute(
            "SELECT trajectory_id, cascade_id, steps_count FROM trajectories WHERE id = ?", (fk,)
        ).fetchone()

        # Get all steps in order
        steps = conn.execute(
            "SELECT step_index, step_type, step_type_name, status, variant_field "
            "FROM steps WHERE trajectory_fk = ? ORDER BY step_index", (fk,)
        ).fetchall()

        lines = []
        lines.append("=" * 70)
        lines.append("TRAJECTORY: %s" % (traj[0] or "?"))
        lines.append("CASCADE ID: %s" % (traj[1] or "?"))
        lines.append("STEPS: %d" % traj[2])
        lines.append("=" * 70)

        for s in steps:
            idx, stype, sname, status, vf = s
            if step_filter is not None and idx != step_filter:
                continue

            if vf == VARIANT_USER_INPUT:
                um = conn.execute(
                    "SELECT prompt FROM user_messages WHERE trajectory_fk = ? AND step_index = ?",
                    (fk, idx),
                ).fetchone()
                prompt = um[0] if um else ""
                lines.append("")
                lines.append("-" * 50)
                lines.append("USER (step %d):" % idx)
                lines.append("-" * 50)
                lines.append(prompt.strip())

            elif vf == VARIANT_PLANNER_RESPONSE:
                am = conn.execute(
                    "SELECT user_facing, internal_planning FROM assistant_messages "
                    "WHERE trajectory_fk = ? AND step_index = ?",
                    (fk, idx),
                ).fetchone()
                lines.append("")
                lines.append("-" * 50)
                lines.append("ASSISTANT (step %d):" % idx)
                lines.append("-" * 50)
                if am and am[0]:
                    lines.append(am[0].strip())
                elif am and am[1]:
                    lines.append("(internal only): " + am[1].strip()[:500])
                else:
                    lines.append("(no text — tool-call-only turn)")

            elif vf == VARIANT_RUN_COMMAND:
                cm = conn.execute(
                    "SELECT command, output FROM commands WHERE trajectory_fk = ? AND step_index = ?",
                    (fk, idx),
                ).fetchone()
                lines.append("")
                lines.append("  [CMD] (step %d): %s" % (idx, (cm[0] or "")[:200]))
                if cm and cm[1]:
                    out = cm[1]
                    if len(out) > 500:
                        out = out[:500] + "... [+%d chars]" % (len(cm[1]) - 500)
                    lines.append("  [OUT]: %s" % out)

            elif vf == VARIANT_CHECKPOINT:
                cp = conn.execute(
                    "SELECT conversation_title, user_intent, session_summary "
                    "FROM checkpoints WHERE trajectory_fk = ? AND step_index = ?",
                    (fk, idx),
                ).fetchone()
                lines.append("")
                lines.append("  [CHECKPOINT] (step %d): %s" % (idx, (cp[0] or "")[:100] if cp else ""))
                if cp and cp[1]:
                    lines.append("  [INTENT]: %s" % cp[1][:300])

            elif vf is not None:
                lines.append("  [step %d] type=%s variant=%d" % (idx, sname, vf))

        return (1, "\n".join(lines), None)

    def cmd_search(self, params):
        """Search loaded chat content. Full-text across user + assistant + commands."""
        query = self._p(params, "query")
        if not query:
            return (0, None, ("no_query", "search needs 'query' param", 0))
        scope = self._p(params, "scope", "all")  # all | user | assistant | commands
        conn = self._get_db()
        results = []

        like = "%%%s%%" % query.replace("%", "\\%")

        if scope in ("all", "user"):
            rows = conn.execute(
                "SELECT t.trajectory_id, t.file_path, um.step_index, um.prompt "
                "FROM user_messages um JOIN trajectories t ON um.trajectory_fk = t.id "
                "WHERE um.prompt LIKE ? ORDER BY t.id, um.step_index",
                (like,),
            ).fetchall()
            for r in rows:
                results.append({
                    "type": "user",
                    "trajectory_id": r[0],
                    "file": r[1],
                    "step": r[2],
                    "text": r[3][:500] if r[3] else "",
                })

        if scope in ("all", "assistant"):
            rows = conn.execute(
                "SELECT t.trajectory_id, t.file_path, am.step_index, am.user_facing, am.internal_planning "
                "FROM assistant_messages am JOIN trajectories t ON am.trajectory_fk = t.id "
                "WHERE (am.user_facing LIKE ? OR am.internal_planning LIKE ?) "
                "ORDER BY t.id, am.step_index",
                (like, like),
            ).fetchall()
            for r in rows:
                results.append({
                    "type": "assistant",
                    "trajectory_id": r[0],
                    "file": r[1],
                    "step": r[2],
                    "text": (r[3] or r[4] or "")[:500],
                })

        if scope in ("all", "commands"):
            rows = conn.execute(
                "SELECT t.trajectory_id, t.file_path, c.step_index, c.command, c.output "
                "FROM commands c JOIN trajectories t ON c.trajectory_fk = t.id "
                "WHERE (c.command LIKE ? OR c.output LIKE ?) "
                "ORDER BY t.id, c.step_index",
                (like, like),
            ).fetchall()
            for r in rows:
                results.append({
                    "type": "command",
                    "trajectory_id": r[0],
                    "file": r[1],
                    "step": r[2],
                    "text": (r[3] or "")[:300],
                })

        return (1, results, None)

    # ── ENHANCED SEARCH (MySQL direct — no RAM load needed) ──────

    def cmd_search_sessions(self, params):
        """Search MySQL cascade_chats for keyword(s). Returns ranked sessions with weighted scores.

        Scoring:
          first_prompt match  = 5 pts per keyword
          round prompt match  = 4 pts per keyword
          user message match  = 3 pts per keyword
          assistant match     = 2 pts per keyword
          command/file match  = 1 pt per keyword

        Multiple keywords sum. Returns sessions ranked by total score.
        """
        query = self._p(params, "query")
        if not query:
            return (0, None, ("no_query", "search-sessions needs 'query' param", 0))
        limit = self._p(params, "limit", 20)
        detail = self._p(params, "detail", False)

        mysql_conn = self._get_mysql_conn()
        if mysql_conn is None:
            return (0, None, ("mysql_failed", self.state.get("last_error", ""), 0))

        keywords = [k.strip() for k in query.split() if k.strip()]
        if not keywords:
            return (0, None, ("no_keywords", "query produced no keywords", 0))

        cursor = mysql_conn.cursor(dictionary=True)
        scores = {}

        for kw in keywords:
            like = "%%%s%%" % kw.replace("%", "\\%").replace("_", "\\_")

            # first_prompt (weight 5)
            cursor.execute(
                "SELECT id, first_prompt, step_count, round_count FROM trajectories WHERE first_prompt LIKE %s",
                (like,),
            )
            for row in cursor.fetchall():
                tid = row["id"]
                if tid not in scores:
                    scores[tid] = {"trajectory_id": tid, "first_prompt": row["first_prompt"], "step_count": row["step_count"], "round_count": row["round_count"], "score": 0, "matches": {}}
                scores[tid]["score"] += 5
                scores[tid]["matches"].setdefault("first_prompt", 0)
                scores[tid]["matches"]["first_prompt"] += 5

            # round prompts (weight 4)
            cursor.execute(
                "SELECT DISTINCT trajectory_id FROM rounds WHERE prompt LIKE %s",
                (like,),
            )
            for row in cursor.fetchall():
                tid = row["trajectory_id"]
                if tid not in scores:
                    tr = cursor.execute("SELECT first_prompt, step_count, round_count FROM trajectories WHERE id=%s", (tid,))
                    tr = cursor.fetchone()
                    if not tr:
                        continue
                    scores[tid] = {"trajectory_id": tid, "first_prompt": tr["first_prompt"], "step_count": tr["step_count"], "round_count": tr["round_count"], "score": 0, "matches": {}}
                scores[tid]["score"] += 4
                scores[tid]["matches"].setdefault("round_prompt", 0)
                scores[tid]["matches"]["round_prompt"] += 4

            # user messages (weight 3)
            cursor.execute(
                "SELECT DISTINCT trajectory_id FROM messages WHERE role='user' AND content LIKE %s",
                (like,),
            )
            for row in cursor.fetchall():
                tid = row["trajectory_id"]
                if tid not in scores:
                    cursor.execute("SELECT first_prompt, step_count, round_count FROM trajectories WHERE id=%s", (tid,))
                    tr = cursor.fetchone()
                    if not tr:
                        continue
                    scores[tid] = {"trajectory_id": tid, "first_prompt": tr["first_prompt"], "step_count": tr["step_count"], "round_count": tr["round_count"], "score": 0, "matches": {}}
                scores[tid]["score"] += 3
                scores[tid]["matches"].setdefault("user_msg", 0)
                scores[tid]["matches"]["user_msg"] += 3

            # assistant messages (weight 2)
            cursor.execute(
                "SELECT DISTINCT trajectory_id FROM messages WHERE role='assistant' AND (content LIKE %s OR internal_planning LIKE %s)",
                (like, like),
            )
            for row in cursor.fetchall():
                tid = row["trajectory_id"]
                if tid not in scores:
                    cursor.execute("SELECT first_prompt, step_count, round_count FROM trajectories WHERE id=%s", (tid,))
                    tr = cursor.fetchone()
                    if not tr:
                        continue
                    scores[tid] = {"trajectory_id": tid, "first_prompt": tr["first_prompt"], "step_count": tr["step_count"], "round_count": tr["round_count"], "score": 0, "matches": {}}
                scores[tid]["score"] += 2
                scores[tid]["matches"].setdefault("assistant_msg", 0)
                scores[tid]["matches"]["assistant_msg"] += 2

            # commands / file_context (weight 1)
            cursor.execute(
                "SELECT DISTINCT trajectory_id FROM messages WHERE (role='command_result' AND content LIKE %s) OR (role='file_context' AND content LIKE %s) OR (command LIKE %s)",
                (like, like, like),
            )
            for row in cursor.fetchall():
                tid = row["trajectory_id"]
                if tid not in scores:
                    cursor.execute("SELECT first_prompt, step_count, round_count FROM trajectories WHERE id=%s", (tid,))
                    tr = cursor.fetchone()
                    if not tr:
                        continue
                    scores[tid] = {"trajectory_id": tid, "first_prompt": tr["first_prompt"], "step_count": tr["step_count"], "round_count": tr["round_count"], "score": 0, "matches": {}}
                scores[tid]["score"] += 1
                scores[tid]["matches"].setdefault("command_file", 0)
                scores[tid]["matches"]["command_file"] += 1

        cursor.close()
        mysql_conn.close()

        ranked = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
        ranked = ranked[:limit]

        if detail:
            for s in ranked:
                s["top_matches"] = self._get_session_snippets(s["trajectory_id"], keywords, 3)

        return (1, {"query": query, "keywords": keywords, "session_count": len(ranked), "sessions": ranked}, None)

    def _get_session_snippets(self, trajectory_id, keywords, max_snippets):
        """Get top matching snippets from a session for preview."""
        mysql_conn = self._get_mysql_conn()
        if mysql_conn is None:
            return []
        cursor = mysql_conn.cursor(dictionary=True)
        snippets = []
        for kw in keywords:
            like = "%%%s%%" % kw.replace("%", "\\%").replace("_", "\\_")
            cursor.execute(
                "SELECT step_index, role, LEFT(content,300) as snippet FROM messages WHERE trajectory_id=%s AND content LIKE %s ORDER BY step_index LIMIT %s",
                (trajectory_id, like, max_snippets),
            )
            for row in cursor.fetchall():
                snippets.append({"step": row["step_index"], "role": row["role"], "snippet": row["snippet"]})
        cursor.close()
        mysql_conn.close()
        return snippets[:max_snippets]

    def cmd_session_detail(self, params):
        """Get full detail of a chat session by trajectory_id from MySQL.

        Returns: trajectory info, all rounds with prompts, user messages,
        key assistant responses, commands run, files referenced, checkpoints.
        """
        traj_id = self._p(params, "trajectory_id")
        if not traj_id:
            return (0, None, ("no_traj", "session-detail needs 'trajectory_id' param", 0))
        max_messages = self._p(params, "max_messages", 50)

        mysql_conn = self._get_mysql_conn()
        if mysql_conn is None:
            return (0, None, ("mysql_failed", self.state.get("last_error", ""), 0))

        cursor = mysql_conn.cursor(dictionary=True)

        # Trajectory info
        cursor.execute("SELECT * FROM trajectories WHERE id=%s", (traj_id,))
        traj = cursor.fetchone()
        if not traj:
            cursor.close()
            mysql_conn.close()
            return (0, None, ("not_found", "trajectory %s not found" % traj_id, 0))

        # Rounds
        cursor.execute(
            "SELECT round_number, LEFT(prompt,200) as prompt, prompt_slug, step_count FROM rounds WHERE trajectory_id=%s ORDER BY round_number",
            (traj_id,),
        )
        rounds = cursor.fetchall()

        # User messages
        cursor.execute(
            "SELECT step_index, LEFT(content,500) as content FROM messages WHERE trajectory_id=%s AND role='user' ORDER BY step_index",
            (traj_id,),
        )
        user_msgs = cursor.fetchall()

        # Key assistant messages (first 300 chars each)
        cursor.execute(
            "SELECT step_index, LEFT(content,300) as content FROM messages WHERE trajectory_id=%s AND role='assistant' AND content IS NOT NULL AND content != '' ORDER BY step_index LIMIT %s",
            (traj_id, max_messages),
        )
        assistant_msgs = cursor.fetchall()

        # Commands run
        cursor.execute(
            "SELECT step_index, LEFT(command,200) as command FROM messages WHERE trajectory_id=%s AND command IS NOT NULL AND command != '' ORDER BY step_index LIMIT %s",
            (traj_id, max_messages),
        )
        commands = cursor.fetchall()

        # Files referenced
        cursor.execute(
            "SELECT step_index, LEFT(content,200) as content FROM messages WHERE trajectory_id=%s AND role='file_context' ORDER BY step_index LIMIT %s",
            (traj_id, max_messages),
        )
        files = cursor.fetchall()

        # Checkpoints
        cursor.execute(
            "SELECT step_index, LEFT(content,300) as content FROM messages WHERE trajectory_id=%s AND role='checkpoint' ORDER BY step_index",
            (traj_id,),
        )
        checkpoints = cursor.fetchall()

        cursor.close()
        mysql_conn.close()

        result = {
            "trajectory": {
                "id": traj["id"],
                "first_prompt": traj["first_prompt"],
                "step_count": traj["step_count"],
                "round_count": traj["round_count"],
                "ingested_at": str(traj["ingested_at"]) if traj.get("ingested_at") else None,
            },
            "rounds": [{"round": r["round_number"], "prompt": r["prompt"], "slug": r["prompt_slug"], "steps": r["step_count"]} for r in rounds],
            "user_messages": [{"step": m["step_index"], "text": m["content"]} for m in user_msgs],
            "assistant_messages": [{"step": m["step_index"], "text": m["content"]} for m in assistant_msgs],
            "commands": [{"step": c["step_index"], "command": c["command"]} for c in commands],
            "files_referenced": [{"step": f["step_index"], "file": f["content"]} for f in files],
            "checkpoints": [{"step": c["step_index"], "text": c["content"]} for c in checkpoints],
            "counts": {
                "rounds": len(rounds),
                "user_messages": len(user_msgs),
                "assistant_messages": len(assistant_msgs),
                "commands": len(commands),
                "files": len(files),
                "checkpoints": len(checkpoints),
            },
        }
        return (1, result, None)

    def cmd_search_files(self, params):
        """Search for which chat sessions mentioned or created specific files.

        Searches command outputs, file_context messages, and assistant messages
        for file paths matching the query. Returns sessions ranked by file mention count.
        """
        query = self._p(params, "query")
        if not query:
            return (0, None, ("no_query", "search-files needs 'query' param", 0))
        limit = self._p(params, "limit", 20)

        mysql_conn = self._get_mysql_conn()
        if mysql_conn is None:
            return (0, None, ("mysql_failed", self.state.get("last_error", ""), 0))

        cursor = mysql_conn.cursor(dictionary=True)
        like = "%%%s%%" % query.replace("%", "\\%").replace("_", "\\_")

        # Search file_context messages
        cursor.execute(
            "SELECT trajectory_id, step_index, LEFT(content,200) as content FROM messages WHERE role='file_context' AND content LIKE %s ORDER BY trajectory_id, step_index LIMIT 200",
            (like,),
        )
        file_hits = cursor.fetchall()

        # Search command outputs for file paths
        cursor.execute(
            "SELECT trajectory_id, step_index, LEFT(command,200) as command FROM messages WHERE command LIKE %s ORDER BY trajectory_id, step_index LIMIT 200",
            (like,),
        )
        cmd_hits = cursor.fetchall()

        # Search assistant messages for file path mentions
        cursor.execute(
            "SELECT trajectory_id, step_index, LEFT(content,300) as content FROM messages WHERE role='assistant' AND content LIKE %s ORDER BY trajectory_id, step_index LIMIT 200",
            (like,),
        )
        asst_hits = cursor.fetchall()

        cursor.close()
        mysql_conn.close()

        # Aggregate by trajectory
        sessions = {}
        for hit in file_hits:
            tid = hit["trajectory_id"]
            if tid not in sessions:
                sessions[tid] = {"trajectory_id": tid, "file_hits": 0, "command_hits": 0, "assistant_hits": 0, "total": 0, "examples": []}
            sessions[tid]["file_hits"] += 1
            sessions[tid]["total"] += 3
            if len(sessions[tid]["examples"]) < 3:
                sessions[tid]["examples"].append({"type": "file", "step": hit["step_index"], "text": hit["content"]})
        for hit in cmd_hits:
            tid = hit["trajectory_id"]
            if tid not in sessions:
                sessions[tid] = {"trajectory_id": tid, "file_hits": 0, "command_hits": 0, "assistant_hits": 0, "total": 0, "examples": []}
            sessions[tid]["command_hits"] += 1
            sessions[tid]["total"] += 2
            if len(sessions[tid]["examples"]) < 3:
                sessions[tid]["examples"].append({"type": "command", "step": hit["step_index"], "text": hit["command"]})
        for hit in asst_hits:
            tid = hit["trajectory_id"]
            if tid not in sessions:
                sessions[tid] = {"trajectory_id": tid, "file_hits": 0, "command_hits": 0, "assistant_hits": 0, "total": 0, "examples": []}
            sessions[tid]["assistant_hits"] += 1
            sessions[tid]["total"] += 1
            if len(sessions[tid]["examples"]) < 3:
                sessions[tid]["examples"].append({"type": "assistant", "step": hit["step_index"], "text": hit["content"]})

        # Get first_prompt for each session
        mysql_conn = self._get_mysql_conn()
        if mysql_conn:
            cursor = mysql_conn.cursor(dictionary=True)
            for tid in sessions:
                cursor.execute("SELECT first_prompt, step_count FROM trajectories WHERE id=%s", (tid,))
                row = cursor.fetchone()
                if row:
                    sessions[tid]["first_prompt"] = row["first_prompt"]
                    sessions[tid]["step_count"] = row["step_count"]
            cursor.close()
            mysql_conn.close()

        ranked = sorted(sessions.values(), key=lambda x: x["total"], reverse=True)[:limit]
        return (1, {"query": query, "session_count": len(ranked), "sessions": ranked}, None)

    def cmd_export(self, params):
        """Export a .pb file to markdown files in outdir."""
        fp = self._p(params, "file")
        outdir = self._p(params, "outdir")
        if not fp or not outdir:
            return (0, None, ("no_params", "export needs 'file' and 'outdir'", 0))
        fp = os.path.expanduser(fp)
        outdir = os.path.expanduser(outdir)

        # Ensure loaded
        conn = self._get_db()
        row = conn.execute(
            "SELECT id, trajectory_id FROM trajectories WHERE file_path = ?", (fp,)
        ).fetchone()
        if row is None:
            ok, _data, err = self.cmd_load({"file": fp, "category": "export"})
            if not ok:
                return (0, None, err)
            row = conn.execute(
                "SELECT id, trajectory_id FROM trajectories WHERE file_path = ?", (fp,)
            ).fetchone()

        fk = row[0]
        traj_id = row[1]
        os.makedirs(outdir, exist_ok=True)

        steps = conn.execute(
            "SELECT step_index, variant_field FROM steps WHERE trajectory_fk = ? ORDER BY step_index",
            (fk,),
        ).fetchall()

        rounds = []
        current = None
        for s in steps:
            idx, vf = s
            if vf == VARIANT_USER_INPUT:
                if current is not None:
                    rounds.append(current)
                um = conn.execute(
                    "SELECT prompt FROM user_messages WHERE trajectory_fk = ? AND step_index = ?",
                    (fk, idx),
                ).fetchone()
                current = {"start": idx, "prompt": um[0] if um else "", "steps": [idx]}
            elif current is not None:
                current["steps"].append(idx)
        if current is not None:
            rounds.append(current)

        files_written = []
        for i, r in enumerate(rounds, start=1):
            slug = r["prompt"][:40].replace("/", "-").replace("\n", " ").strip() or "untitled"
            fname = "%04d-%s.md" % (i, slug)
            fpath = os.path.join(outdir, fname)

            lines = ["# Round %d: %s" % (i, slug), "", "_Steps %d-%d_" % (r["start"], r["steps"][-1]), ""]
            for idx in r["steps"]:
                step_row = conn.execute(
                    "SELECT variant_field FROM steps WHERE trajectory_fk = ? AND step_index = ?",
                    (fk, idx),
                ).fetchone()
                vf = step_row[0] if step_row else None

                if vf == VARIANT_USER_INPUT:
                    um = conn.execute(
                        "SELECT prompt FROM user_messages WHERE trajectory_fk = ? AND step_index = ?",
                        (fk, idx),
                    ).fetchone()
                    lines.append("## User (step %d)" % idx)
                    lines.append("")
                    lines.append((um[0] if um else "").strip())
                    lines.append("")
                elif vf == VARIANT_PLANNER_RESPONSE:
                    am = conn.execute(
                        "SELECT user_facing, internal_planning FROM assistant_messages "
                        "WHERE trajectory_fk = ? AND step_index = ?",
                        (fk, idx),
                    ).fetchone()
                    lines.append("## Assistant (step %d)" % idx)
                    lines.append("")
                    if am and am[0]:
                        lines.append(am[0].strip())
                    elif am and am[1]:
                        lines.append("(internal): " + am[1].strip()[:1000])
                    lines.append("")
                elif vf == VARIANT_RUN_COMMAND:
                    cm = conn.execute(
                        "SELECT command, output FROM commands WHERE trajectory_fk = ? AND step_index = ?",
                        (fk, idx),
                    ).fetchone()
                    if cm:
                        lines.append("<details><summary>Command (step %d): %s</summary>" % (idx, (cm[0] or "")[:100]))
                        lines.append("")
                        lines.append("```bash")
                        lines.append((cm[0] or "").strip())
                        lines.append("```")
                        if cm[1]:
                            out = cm[1][:2000]
                            if len(cm[1]) > 2000:
                                out += "... [+%d chars]" % (len(cm[1]) - 2000)
                            lines.append("")
                            lines.append("```")
                            lines.append(out.strip())
                            lines.append("```")
                        lines.append("</details>")
                        lines.append("")

            Path(fpath).write_text("\n".join(lines), encoding="utf-8")
            files_written.append(fpath)

        # Write index
        idx_path = os.path.join(outdir, "00-index.md")
        idx_lines = ["# Trajectory %s" % traj_id, "", "| # | Title | Steps | File |", "|---|---|---|---|"]
        for i, r in enumerate(rounds, start=1):
            slug = r["prompt"][:40].replace("/", "-").replace("\n", " ").strip() or "untitled"
            fname = "%04d-%s.md" % (i, slug)
            title = r["prompt"][:60].replace("\n", " ").replace("|", "\\|")
            idx_lines.append("| %d | %s | %d-%d | [%s](%s) |" % (i, title, r["start"], r["steps"][-1], fname, fname))
        Path(idx_path).write_text("\n".join(idx_lines), encoding="utf-8")
        files_written.append(idx_path)

        return (1, {"rounds": len(rounds), "files": files_written, "outdir": outdir}, None)

    def cmd_stats(self, params):
        """Show RAM DB statistics."""
        conn = self._get_db()
        stats = {}
        for table in ("trajectories", "steps", "user_messages", "assistant_messages", "commands", "checkpoints"):
            count = conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
            stats[table] = count
        stats["loaded_files"] = len(self.state["loaded_files"])
        stats["scan_results"] = len(self.state["scan_results"])
        return (1, stats, None)

    # ── EXPORT TO MYSQL ────────────────────────────────────────

    def _get_mysql_conn(self):
        """Get MySQL connection to cascade_chats database."""
        try:
            import mysql.connector
            return mysql.connector.connect(
                host="localhost", user="root", password="", database="cascade_chats"
            )
        except Exception as e:
            self.state["last_error"] = str(e)
            return None

    def cmd_export_db(self, params):
        """Export all loaded trajectories from RAM SQLite to MySQL cascade_chats.

        Transfers trajectories, rounds, and messages using prepared statements.
        Skips trajectories already in MySQL (dedup by trajectory_id).
        """
        conn = self._get_db()
        mysql_conn = self._get_mysql_conn()
        if mysql_conn is None:
            return (0, None, ("mysql_failed", self.state.get("last_error", ""), 0))

        cursor = mysql_conn.cursor(prepared=True)
        exported = 0
        skipped = 0
        errors = []

        # Get all loaded trajectories
        trajs = conn.execute(
            "SELECT trajectory_id, cascade_id, file_path, file_category, trajectory_type, source, steps_count FROM trajectories"
        ).fetchall()

        for t in trajs:
            traj_id, cascade_id, file_path, file_cat, traj_type, source, steps_count = t
            if not traj_id:
                continue

            # Check if already in MySQL
            cursor.execute("SELECT id FROM trajectories WHERE id = %s", (traj_id,))
            if cursor.fetchone():
                skipped += 1
                continue

            # Get first user prompt
            first_prompt_row = conn.execute(
                "SELECT prompt FROM user_messages WHERE trajectory_fk = (SELECT id FROM trajectories WHERE trajectory_id = ?) ORDER BY step_index LIMIT 1",
                (traj_id,)
            ).fetchone()
            first_prompt = first_prompt_row[0] if first_prompt_row else ""
            # Truncate to fit TEXT column (65535 bytes max, leave room for multi-byte)
            if first_prompt and len(first_prompt.encode("utf-8")) > 60000:
                first_prompt = first_prompt[:60000]

            # Count rounds (user messages = rounds)
            round_count = conn.execute(
                "SELECT COUNT(*) FROM user_messages WHERE trajectory_fk = (SELECT id FROM trajectories WHERE trajectory_id = ?)",
                (traj_id,)
            ).fetchone()[0]

            # Insert trajectory using prepared statement
            cursor.execute(
                "INSERT INTO trajectories (id, cascade_id, file_name, trajectory_type, source, step_count, round_count, first_prompt) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (traj_id, cascade_id, os.path.basename(file_path) if file_path else "", traj_type, source, steps_count, round_count, first_prompt)
            )

            # Get the trajectory FK from SQLite
            fk_row = conn.execute("SELECT id FROM trajectories WHERE trajectory_id = ?", (traj_id,)).fetchone()
            if not fk_row:
                continue
            fk = fk_row[0]

            # Export rounds
            user_msgs = conn.execute(
                "SELECT step_index, prompt FROM user_messages WHERE trajectory_fk = ? ORDER BY step_index", (fk,)
            ).fetchall()

            round_num = 0
            for um in user_msgs:
                um_step, um_prompt = um
                round_num += 1
                slug = (um_prompt or "")[:40].replace("/", "-").replace("\n", " ").strip() or "untitled"

                cursor.execute(
                    "INSERT INTO rounds (trajectory_id, round_number, start_step, end_step, step_count, prompt, prompt_slug) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (traj_id, round_num, um_step, um_step, 1, um_prompt, slug)
                )
                round_id = cursor.lastrowid

                # Export messages for this round (from this user message to next user message)
                steps = conn.execute(
                    "SELECT step_index, step_type, variant_field FROM steps WHERE trajectory_fk = ? AND step_index >= ? ORDER BY step_index",
                    (fk, um_step)
                ).fetchall()

                # Find end of round (next user input)
                next_user = conn.execute(
                    "SELECT MIN(step_index) FROM user_messages WHERE trajectory_fk = ? AND step_index > ?",
                    (fk, um_step)
                ).fetchone()[0]

                for s in steps:
                    s_idx, s_type, s_vf = s
                    if next_user is not None and s_idx >= next_user:
                        break

                    role = "other"
                    content = None
                    internal = None
                    command = None
                    cmd_output = None

                    if s_vf == VARIANT_USER_INPUT:
                        role = "user"
                        row = conn.execute("SELECT prompt FROM user_messages WHERE trajectory_fk = ? AND step_index = ?", (fk, s_idx)).fetchone()
                        content = row[0] if row else ""
                    elif s_vf == VARIANT_PLANNER_RESPONSE:
                        role = "assistant"
                        row = conn.execute("SELECT user_facing, internal_planning FROM assistant_messages WHERE trajectory_fk = ? AND step_index = ?", (fk, s_idx)).fetchone()
                        content = row[0] if row else None
                        internal = row[1] if row else None
                    elif s_vf == VARIANT_RUN_COMMAND:
                        role = "tool"
                        row = conn.execute("SELECT command, output FROM commands WHERE trajectory_fk = ? AND step_index = ?", (fk, s_idx)).fetchone()
                        command = row[0] if row else None
                        cmd_output = row[1] if row else None
                    elif s_vf == VARIANT_CHECKPOINT:
                        role = "checkpoint"
                        row = conn.execute("SELECT session_summary FROM checkpoints WHERE trajectory_fk = ? AND step_index = ?", (fk, s_idx)).fetchone()
                        content = row[0] if row else None
                    elif s_vf == VARIANT_FILE_CONTEXT:
                        role = "file_context"
                    elif s_vf == VARIANT_COMMAND_RESULT:
                        role = "command_result"
                    else:
                        role = "other"

                    wc = len(content.split()) if content else 0
                    cc = len(content) if content else 0
                    # Truncate command to fit TEXT column
                    if command and len(command.encode("utf-8")) > 60000:
                        command = command[:60000]

                    cursor.execute(
                        "INSERT INTO messages (trajectory_id, round_id, step_index, role, variant_field, step_type, content, internal_planning, command, command_output, word_count, char_count) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (traj_id, round_id, s_idx, role, s_vf, s_type, content, internal, command, cmd_output, wc, cc)
                    )

            exported += 1

        mysql_conn.commit()
        cursor.close()
        mysql_conn.close()

        return (1, {
            "exported": exported,
            "skipped": skipped,
            "errors": errors,
            "total_in_db": exported + skipped,
        }, None)

    # ── VERIFY DB ───────────────────────────────────────────────

    def cmd_verify_db(self, params):
        """Verify that all scanned .pb files are present in MySQL cascade_chats.

        Returns:
            - verified: list of files confirmed in DB
            - missing: list of files NOT in DB
            - all_verified: True if all files are in DB
        """
        # First scan if not already done
        if not self.state["scan_results"]:
            self.cmd_scan(params)

        mysql_conn = self._get_mysql_conn()
        if mysql_conn is None:
            return (0, None, ("mysql_failed", self.state.get("last_error", ""), 0))

        cursor = mysql_conn.cursor()

        # Get all trajectory IDs from MySQL
        cursor.execute("SELECT id FROM trajectories")
        db_ids = set(row[0] for row in cursor.fetchall())

        # Get all .pb file paths from MySQL (file_name column)
        cursor.execute("SELECT file_name FROM trajectories WHERE file_name IS NOT NULL AND file_name != ''")
        db_filenames = set(row[0] for row in cursor.fetchall())

        cursor.close()
        mysql_conn.close()

        verified = []
        missing = []

        for item in self.state["scan_results"]:
            filename = os.path.basename(item["path"])
            traj_id = filename.replace(".pb", "")

            # Check by trajectory ID or filename
            if traj_id in db_ids or filename in db_filenames:
                verified.append({
                    "path": item["path"],
                    "filename": filename,
                    "category": item["category"],
                    "size_kb": item["size_kb"],
                })
            else:
                missing.append({
                    "path": item["path"],
                    "filename": filename,
                    "category": item["category"],
                    "size_kb": item["size_kb"],
                })

        return (1, {
            "total_scanned": len(self.state["scan_results"]),
            "verified_count": len(verified),
            "missing_count": len(missing),
            "all_verified": len(missing) == 0,
            "verified": verified[:10],  # first 10 for preview
            "missing": missing[:10],    # first 10 for preview
        }, None)

    # ── CLEAN (DELETE .PB FILES AFTER VERIFICATION) ─────────────

    def cmd_clean(self, params):
        """Clean (delete) .pb files ONLY after verifying all are in MySQL.

        params:
            confirm: True/False — must be True to actually delete.
                     If False or missing, returns verification report only.

        Safety:
            1. Scans all .pb files
            2. Verifies each is in MySQL cascade_chats
            3. If ANY file is missing from DB, aborts — nothing deleted
            4. If all verified, requires confirm=True to proceed
            5. Deletes only .pb files, preserves directory structure
        """
        confirm = self._p(params, "confirm", False)

        # Step 1: Verify
        ok, verify_data, err = self.cmd_verify_db(params)
        if not ok:
            return (0, None, err)

        if not verify_data["all_verified"]:
            return (1, {
                "action": "aborted",
                "reason": "not_all_verified",
                "missing_count": verify_data["missing_count"],
                "missing_files": verify_data["missing"],
                "message": "Cannot clean: {} .pb files are NOT in the database. Export them first with export-db.".format(verify_data["missing_count"]),
            }, None)

        # Step 2: Require confirmation
        if not confirm:
            return (1, {
                "action": "pending_confirmation",
                "total_files": verify_data["total_scanned"],
                "verified_count": verify_data["verified_count"],
                "message": "All {} .pb files verified in database. Set confirm=true to delete them.".format(verify_data["verified_count"]),
                "warning": "This will permanently delete {} .pb files from disk. This cannot be undone.".format(verify_data["verified_count"]),
            }, None)

        # Step 3: Delete
        deleted = 0
        failed = 0
        errors = []

        for item in self.state["scan_results"]:
            try:
                os.remove(item["path"])
                deleted += 1
            except Exception as e:
                failed += 1
                errors.append({"file": item["path"], "error": str(e)})

        return (1, {
            "action": "cleaned",
            "deleted": deleted,
            "failed": failed,
            "errors": errors[:5],
            "message": "Deleted {} .pb files. {} failed.".format(deleted, failed),
        }, None)

    def cmd_compress(self, params):
        """Compress a chat markdown file to BCL tokens (Stage 1).
        Delegates to BclChatCompressor.
        Params: input_path (required), output_path (optional).
        """
        if not hasattr(self, "_compressor"):
            self._compressor = BclChatCompressor()
        return self._compressor.Run("compress", params)

    def cmd_dry_run(self, params):
        """Dry-run BCL compression — extract tokens without writing.
        Delegates to BclChatCompressor.
        Params: input_path (required).
        """
        if not hasattr(self, "_compressor"):
            self._compressor = BclChatCompressor()
        return self._compressor.Run("dry_run", params)


# ════════════════════════════════════════════════════════════════
# BCL CHAT COMPRESSOR — Stage 1 BCL token extraction
# Originally from bcl_chat_compressor.py — merged into pb_reader.py
# [@GHOST]{file_path="chat_mover/bcl_chat_compressor.py" date="2026-06-29" author="Devin" session_id="bcl-compress" context="Stage 1 BCL chat compression — extract tokens from chat files"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
# [@FILEID]{id="bcl_chat_compressor.py" domain="chat_mover" authority="BclChatCompressor"}
# [@SUMMARY]{summary="Stage 1 BCL compressor — extracts [@USER_SAYS] [@AI_SAYS] [@ERROR] [@FILE] [@COMMAND_RAN] [@FRUSTRATION_SIGNAL] [@QUESTION] [@TOPIC] tokens from chat files"}
# [@CLASS]{class="BclChatCompressor" domain="chat_mover" authority="single"}
# [@METHOD]{methods="Run,compress,extract_dialogue,extract_errors,extract_files,extract_commands,extract_frustration,extract_questions,extract_topics,format_output,write_stats,read_state,set_config"}
# ════════════════════════════════════════════════════════════════

FRUSTRATION_KEYWORDS = [
    "stuck", "frozen", "why", "weird", "shit", "hell", "damn",
    "broke", "broken", "crash", "hang", "hangs", "failed", "fail",
    "problem", "wrong", "error", "bug", "issue", "not working",
    "give up", "doesn't work", "dont work", "not working",
]

ERROR_PATTERNS = [
    (r"Traceback \(most recent call last\)", "python_traceback"),
    (r"\bError\b", "generic_error"),
    (r"\bTypeError\b", "type_error"),
    (r"\bValueError\b", "value_error"),
    (r"\bKeyError\b", "key_error"),
    (r"\bIndexError\b", "index_error"),
    (r"\bAttributeError\b", "attribute_error"),
    (r"\bModuleNotFoundError\b", "module_not_found"),
    (r"\bImportError\b", "import_error"),
    (r"\bFileNotFoundError\b", "file_not_found"),
    (r"\bNameError\b", "name_error"),
    (r"\bSyntaxError\b", "syntax_error"),
    (r"\bRuntimeError\b", "runtime_error"),
    (r"\bFAILED\b", "failed_marker"),
    (r"\bError:\s", "error_marker"),
    (r"exit code [1-9]", "exit_code_error"),
    (r"command not found", "not_found_error"),
    (r"permission denied", "permission_error"),
    (r"no such file or directory", "not_found_error"),
]

FILE_PATTERN = re.compile(r'[\w/.\-]+\.(py|c|h|md|sql|sh|json|yaml|yml|txt|js|ts|tsx|jsx|rb|go|rs|java|cpp|cc|hh)')
QUESTION_PATTERN = re.compile(r'\?')
USER_INPUT_HEADER = re.compile(r'^###\s*User Input', re.MULTILINE)
PLANNER_HEADER = re.compile(r'^###\s*Planner Response', re.MULTILINE)
COMMAND_ACCEPTED = re.compile(r'\*User accepted command\*')
COMMAND_REJECTED = re.compile(r'\*User rejected command\*')
CODE_BLOCK = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)

STAGE2_TOKENS = "[@PROBLEM] [@SOLUTION] [@ROOT_CAUSE] [@LESSON] [@SUCCESS] [@FAILED] [@DECISION] [@USER_PREF] [@MOOD] [@INTENT] [@AI_CORRECT] [@AI_WRONG]"


class BclChatCompressor:
    """Stage 1 BCL chat compressor — code-based token extraction."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "min_lines": 500,
                "chronological": True,
                "inline_lessons": True,
                "extract_errors": True,
                "extract_files": True,
                "extract_commands": True,
                "extract_frustration": True,
                "extract_questions": True,
                "extract_topics": True,
                "extract_dialogue": True,
            },
            "last_input": None,
            "last_output": None,
            "last_stats": None,
            "last_error": None,
        }

    def _p(self, params, key, default=None):
        """Extract param from dict safely."""
        if not params:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        """Dispatch commands."""
        dispatch = {
            "compress": self.cmd_compress,
            "dry_run": self.cmd_dry_run,
            "read_state": self.cmd_read_state,
            "set_config": self.cmd_set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, (1, "unknown_command: %s" % command, 0))
        return handler(params)

    def cmd_read_state(self, params):
        return (1, dict(self.state), None)

    def cmd_set_config(self, params):
        if not params:
            return (0, None, (1, "no params", 0))
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def cmd_compress(self, params):
        input_path = self._p(params, "input_path")
        output_path = self._p(params, "output_path")
        if not input_path:
            return (0, None, (1, "missing input_path", 0))
        if not output_path:
            base = Path(input_path).stem
            output_path = str(Path(input_path).parent / (base + "_BCL_stage1.md"))

        ok, data, err = self.compress_file(input_path, output_path)
        if err:
            return (0, None, err)
        self.state["last_input"] = input_path
        self.state["last_output"] = output_path
        self.state["last_stats"] = data.get("stats", {})
        return (1, data, None)

    def cmd_dry_run(self, params):
        input_path = self._p(params, "input_path")
        if not input_path:
            return (0, None, (1, "missing input_path", 0))
        ok, data, err = self.compress_file(input_path, None)
        if err:
            return (0, None, err)
        return (1, data, None)

    # ── CORE COMPRESSION ──

    def compress_file(self, input_path, output_path):
        """Read file, extract tokens, write output."""
        p = Path(input_path)
        if not p.exists():
            return (0, None, (2, "file not found: %s" % input_path, 0))

        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        line_count = len(lines)

        md5 = hashlib.md5(content.encode()).hexdigest()[:12]
        date_str = datetime.now().strftime("%Y-%m-%d")

        tokens = []
        cfg = self.state["config"]

        if cfg.get("extract_dialogue", True):
            tokens.extend(self.extract_dialogue(lines))
        if cfg.get("extract_errors", True):
            tokens.extend(self.extract_errors(lines))
        if cfg.get("extract_files", True):
            tokens.extend(self.extract_files(lines))
        if cfg.get("extract_commands", True):
            tokens.extend(self.extract_commands(lines))
        if cfg.get("extract_frustration", True):
            tokens.extend(self.extract_frustration(lines))
        if cfg.get("extract_questions", True):
            tokens.extend(self.extract_questions(lines))
        if cfg.get("extract_topics", True):
            tokens.extend(self.extract_topics(lines))

        tokens.sort(key=lambda t: t.get("line", 0))

        stats = self.compute_stats(tokens, line_count)

        output_text = self.format_output(
            tokens, stats, input_path, line_count, md5, date_str
        )

        data = {
            "output_path": output_path,
            "tokens": tokens,
            "stats": stats,
            "token_count": len(tokens),
            "line_count": line_count,
            "md5": md5,
        }

        if output_path:
            Path(output_path).write_text(output_text, encoding="utf-8")
            data["output_path"] = output_path
        else:
            data["output_text"] = output_text

        return (1, data, None)

    # ── EXTRACTION METHODS ──

    def extract_dialogue(self, lines):
        """Extract [@USER_SAYS] and [@AI_SAYS] tokens."""
        tokens = []
        current_section = None
        current_text = []
        current_line = 0

        for i, line in enumerate(lines):
            line_num = i + 1

            if USER_INPUT_HEADER.match(line):
                if current_section and current_text:
                    tokens.append(self.make_dialogue_token(
                        current_section, current_line, "\n".join(current_text)
                    ))
                current_section = "user"
                current_text = []
                current_line = line_num
                continue

            if PLANNER_HEADER.match(line):
                if current_section and current_text:
                    tokens.append(self.make_dialogue_token(
                        current_section, current_line, "\n".join(current_text)
                    ))
                current_section = "ai"
                current_text = []
                current_line = line_num
                continue

            if current_section:
                stripped = line.strip()
                if stripped and not stripped.startswith("###"):
                    current_text.append(stripped)

        if current_section and current_text:
            tokens.append(self.make_dialogue_token(
                current_section, current_line, "\n".join(current_text)
            ))

        return tokens

    def make_dialogue_token(self, section, line_num, text):
        text_clean = text.strip()[:500]
        tag = "USER_SAYS" if section == "user" else "AI_SAYS"
        return {
            "tag": tag,
            "line": line_num,
            "text": text_clean,
            "type": "dialogue",
        }

    def extract_errors(self, lines):
        """Extract [@ERROR] tokens using regex patterns."""
        tokens = []
        for i, line in enumerate(lines):
            line_num = i + 1
            for pattern, error_type in ERROR_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    text = line.strip()[:300]
                    tokens.append({
                        "tag": "ERROR",
                        "line": line_num,
                        "text": text,
                        "error_type": error_type,
                        "type": "error",
                    })
                    break
        return tokens

    def extract_files(self, lines):
        """Extract [@FILE] tokens — file paths mentioned."""
        tokens = []
        seen = set()
        for i, line in enumerate(lines):
            line_num = i + 1
            for match in FILE_PATTERN.finditer(line):
                path = match.group(0)
                if len(path) < 5 or path.startswith("http"):
                    continue
                key = (path, line_num)
                if key not in seen:
                    seen.add(key)
                    tokens.append({
                        "tag": "FILE",
                        "line": line_num,
                        "text": path,
                        "type": "file",
                    })
        return tokens

    def extract_commands(self, lines):
        """Extract [@COMMAND_RAN] tokens."""
        tokens = []
        for i, line in enumerate(lines):
            line_num = i + 1
            if COMMAND_ACCEPTED.search(line):
                tokens.append({
                    "tag": "COMMAND_RAN",
                    "line": line_num,
                    "text": "user_accepted",
                    "type": "command",
                })
            elif COMMAND_REJECTED.search(line):
                tokens.append({
                    "tag": "COMMAND_RAN",
                    "line": line_num,
                    "text": "user_rejected",
                    "type": "command",
                })
        return tokens

    def extract_frustration(self, lines):
        """Extract [@FRUSTRATION_SIGNAL] tokens."""
        tokens = []
        for i, line in enumerate(lines):
            line_num = i + 1
            lower = line.lower()
            for kw in FRUSTRATION_KEYWORDS:
                if kw in lower:
                    tokens.append({
                        "tag": "FRUSTRATION_SIGNAL",
                        "line": line_num,
                        "text": "keyword=%s" % kw,
                        "type": "frustration",
                    })
                    break
        return tokens

    def extract_questions(self, lines):
        """Extract [@QUESTION] tokens — lines with ?."""
        tokens = []
        for i, line in enumerate(lines):
            line_num = i + 1
            if QUESTION_PATTERN.search(line) and line.strip():
                text = line.strip()[:300]
                tokens.append({
                    "tag": "QUESTION",
                    "line": line_num,
                    "text": text,
                    "type": "question",
                })
        return tokens

    def extract_topics(self, lines):
        """Extract [@TOPIC] tokens — markdown headings."""
        tokens = []
        for i, line in enumerate(lines):
            line_num = i + 1
            stripped = line.strip()
            if stripped.startswith("#") and not stripped.startswith("#[@"):
                topic = stripped.lstrip("#").strip()
                if topic and len(topic) > 2:
                    tokens.append({
                        "tag": "TOPIC",
                        "line": line_num,
                        "text": topic[:200],
                        "type": "topic",
                    })
        return tokens

    # ── FORMATTING ──

    def compute_stats(self, tokens, line_count):
        """Compute compression statistics."""
        stats = {"source_lines": line_count, "tokens": len(tokens)}
        tag_counts = {}
        for t in tokens:
            tag = t["tag"]
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        stats["tag_counts"] = tag_counts
        if line_count > 0:
            stats["compression_ratio"] = round(line_count / max(len(tokens), 1), 1)
        return stats

    def format_output(self, tokens, stats, source_path, line_count, md5, date_str):
        """Format tokens into BCL output file."""
        source_name = Path(source_path).name
        token_count = len(tokens)
        ratio = stats.get("compression_ratio", 0)

        lines = []

        lines.append("#[@FILE]      %s path=%s" % (Path(source_path).stem + "_BCL.md", source_path))
        lines.append("#[@FILEID]    md5=%s date=%s source=%s(%d_lines)" % (md5, date_str, source_name, line_count))
        lines.append("#[@SUMMARY]   BCL Stage 1 compression (code extraction). %d lines -> %d tokens." % (line_count, token_count))
        lines.append("#[@METHOD]    parse_structure -> regex_extraction -> dict_matching -> format_output")
        lines.append("#[@TOKENS]    Stage 1 only — AI semantic pass needed for %s" % STAGE2_TOKENS)
        lines.append("")
        lines.append("#[@CHAT]      source=%s lines=%d" % (source_name, line_count))
        lines.append('#[@CHATSOURCE]{path="%s";lines=%d;md5=%s;date="%s"}' % (source_path, line_count, md5, date_str))
        lines.append('#[@CHATFULLIDEARS]{source="%s";compressed_tokens=%d;compression_ratio=%s:1;stage="1_code_only";stage2_needed="%s"}' % (source_name, token_count, ratio, STAGE2_TOKENS))
        lines.append("")

        for t in tokens:
            tag = t["tag"]
            line_num = t["line"]
            text = t["text"]

            if tag == "USER_SAYS":
                lines.append("#[@USER_SAYS] L%d: %s" % (line_num, text))
            elif tag == "AI_SAYS":
                lines.append("#[@AI_SAYS]   L%d: %s" % (line_num, text))
            elif tag == "ERROR":
                etype = t.get("error_type", "generic")
                lines.append("#[@ERROR]     L%d [%s] %s" % (line_num, etype, text))
            elif tag == "FILE":
                lines.append("#[@FILE]      L%d %s" % (line_num, text))
            elif tag == "COMMAND_RAN":
                lines.append("#[@COMMAND_RAN] L%d %s" % (line_num, text))
            elif tag == "FRUSTRATION_SIGNAL":
                lines.append("#[@FRUSTRATION_SIGNAL] L%d %s" % (line_num, text))
            elif tag == "QUESTION":
                lines.append("#[@QUESTION]  L%d: %s" % (line_num, text))
            elif tag == "TOPIC":
                lines.append("#[@TOPIC]     L%d: %s" % (line_num, text))

        lines.append("")
        lines.append("=" * 60)
        lines.append("# STAGE 1 STATS (code extraction only)")
        lines.append("=" * 60)
        lines.append("#[@STATS]     source_lines=%d -> tokens=%d" % (line_count, token_count))
        tag_counts = stats.get("tag_counts", {})
        for tag in sorted(tag_counts.keys()):
            lines.append("#[@STATS]     %s=%d" % (tag, tag_counts[tag]))

        lines.append("")
        lines.append("=" * 60)
        lines.append("# STAGE 2 NEEDED — AI must extract:")
        lines.append("=" * 60)
        lines.append("#[@NEEDED]    [@PROBLEM] [@SOLUTION] [@ROOT_CAUSE] [@LESSON]")
        lines.append("#[@NEEDED]    [@SUCCESS] [@FAILED] [@DECISION] [@USER_PREF]")
        lines.append("#[@NEEDED]    [@MOOD] [@INTENT] [@AI_CORRECT] [@AI_WRONG]")
        lines.append("#[@NEEDED]    Pair problems with solutions, inline lessons under problems")
        lines.append("#[@NEEDED]    Output in chronological order with cause chain")

        return "\n".join(lines) + "\n"


# ════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ════════════════════════════════════════════════════════════════

def cli_main():
    """CLI wrapper around PbReader class."""
    ap = argparse.ArgumentParser(
        description="Decrypt and search Windsurf Cascade .pb chat files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("scan", help="List all .pb files found in ~/.codeium/windsurf/")
    sub.add_parser("list", help="List trajectories loaded in RAM")
    sub.add_parser("load-all", help="Load all .pb files into RAM")
    sub.add_parser("stats", help="Show RAM DB statistics")

    p_index = sub.add_parser("index", help="Build chat index: funny_name -> decrypted_name + all details")
    p_index.add_argument("query", nargs="?", default="", help="Filter by title/file/trajectory_id")
    p_index.add_argument("--limit", type=int, default=0, help="Max results (0=all)")

    p_load = sub.add_parser("load", help="Load one .pb file into RAM")
    p_load.add_argument("file", help="Path to .pb file")

    p_read = sub.add_parser("read", help="Read a .pb file as chat conversation")
    p_read.add_argument("file", help="Path to .pb file")
    p_read.add_argument("--step", type=int, default=None, help="Show only specific step")

    p_search = sub.add_parser("search", help="Search loaded chat content")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--scope", choices=["all", "user", "assistant", "commands"], default="all")

    p_search_sessions = sub.add_parser("search-sessions", help="Search MySQL for which chat sessions match keywords (weighted)")
    p_search_sessions.add_argument("query", help="Search query (multi-word = multiple keywords)")
    p_search_sessions.add_argument("--limit", type=int, default=20, help="Max sessions to return")
    p_search_sessions.add_argument("--detail", action="store_true", help="Include snippet previews")

    p_session_detail = sub.add_parser("session-detail", help="Get full detail of a chat session")
    p_session_detail.add_argument("trajectory_id", help="Trajectory ID from search-sessions")
    p_session_detail.add_argument("--max-messages", type=int, default=50, help="Max messages per type")

    p_search_files = sub.add_parser("search-files", help="Search which sessions mentioned/created files")
    p_search_files.add_argument("query", help="File path or filename keyword")
    p_search_files.add_argument("--limit", type=int, default=20, help="Max sessions to return")

    p_export = sub.add_parser("export", help="Export .pb to markdown")
    p_export.add_argument("file", help="Path to .pb file")
    p_export.add_argument("outdir", help="Output directory for markdown files")

    sub.add_parser("export-db", help="Export all loaded trajectories from RAM to MySQL cascade_chats")
    sub.add_parser("verify-db", help="Verify all scanned .pb files are present in MySQL cascade_chats")

    p_clean = sub.add_parser("clean", help="Clean (delete) .pb files after verifying all are in MySQL")
    p_clean.add_argument("--confirm", action="store_true", help="Confirm deletion (required to actually delete)")

    p_compress = sub.add_parser("compress", help="Compress a chat .md file to BCL tokens (Stage 1)")
    p_compress.add_argument("input", help="Path to source chat .md file")
    p_compress.add_argument("output", nargs="?", default=None, help="Output BCL .md file path")

    p_dryrun = sub.add_parser("dry-run", help="Extract BCL tokens without writing output file")
    p_dryrun.add_argument("input", help="Path to source chat .md file")

    args = ap.parse_args()
    reader = PbReader()

    if args.cmd == "scan":
        ok, data, err = reader.Run("scan")
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        sys.stderr.write("Found %d .pb files:\n" % len(data))
        for item in data:
            sys.stderr.write("  [%s] %s (%.1f KB)\n" % (item["category"], item["filename"], item["size_kb"]))
        # Also output paths to stdout for piping
        for item in data:
            sys.stdout.write(item["path"] + "\n")
        return 0

    if args.cmd == "list":
        ok, data, err = reader.Run("list")
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        if not data:
            sys.stderr.write("No trajectories loaded. Use 'load' or 'load-all' first.\n")
            return 0
        sys.stderr.write("Loaded trajectories (%d):\n" % len(data))
        for t in data:
            sys.stderr.write("  [%s] %s — %d steps, %d user, %d ai, %d cmds (%.1f KB)\n" % (
                t["category"], t["trajectory_id"][:20] if t["trajectory_id"] else "?",
                t["steps"], t["user_msgs"], t["ai_msgs"], t["commands"], t["decrypted_kb"],
            ))
        return 0

    if args.cmd == "index":
        # Auto-load all if nothing loaded
        ok, stats, _ = reader.Run("stats")
        if stats["trajectories"] == 0:
            sys.stderr.write("Nothing loaded — auto-loading all .pb files...\n")
            reader.Run("load-all")
        ok, data, err = reader.Run("index", {"query": args.query, "limit": args.limit})
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        sys.stderr.write("Chat index: %d chats (inserted %d)\n" % (data["count"], data.get("inserted", 0)))
        for c in data["chats"]:
            sys.stderr.write("\n  [%s] %s\n" % (c["category"], c["file_name"]))
            sys.stderr.write("    chat_name: %s\n" % c["chat_name"][:100])
            if c.get("checkpoint_title"):
                sys.stderr.write("    checkpoint: %s\n" % c["checkpoint_title"][:100])
            if c.get("user_intent"):
                sys.stderr.write("    intent: %s\n" % c["user_intent"][:100])
            sys.stderr.write("    steps=%d user=%d ai=%d cmds=%d checkpoints=%d (%.1f KB)\n" % (
                c["step_count"], c["user_msg_count"], c["ai_msg_count"],
                c["command_count"], c["checkpoint_count"], c["decrypted_kb"],
            ))
            if c.get("edited_files"):
                sys.stderr.write("    edited_files: %s\n" % c["edited_files"][:200])
        sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")
        return 0

    if args.cmd == "load":
        ok, data, err = reader.Run("load", {"file": args.file})
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        sys.stderr.write("Loaded: %s (%d steps)\n" % (data["trajectory_id"][:40], data["steps"]))
        return 0

    if args.cmd == "load-all":
        sys.stderr.write("Loading all .pb files...\n")
        ok, data, err = reader.Run("load-all")
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        sys.stderr.write("Loaded %d, failed %d\n" % (data["loaded"], data["failed"]))
        for r in data["results"]:
            if "error" in r:
                sys.stderr.write("  FAIL: %s — %s\n" % (r["file"], r["error"]))
            else:
                sys.stderr.write("  OK: %s (%d steps)\n" % (r["trajectory_id"][:30], r["steps"]))
        return 0

    if args.cmd == "read":
        ok, data, err = reader.Run("read", {"file": args.file, "step": args.step})
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        sys.stdout.write(data + "\n")
        return 0

    if args.cmd == "search":
        # Auto-load-all if nothing loaded
        ok, stats, _ = reader.Run("stats")
        if stats["trajectories"] == 0:
            sys.stderr.write("Nothing loaded — auto-loading all .pb files...\n")
            reader.Run("load-all")
        ok, data, err = reader.Run("search", {"query": args.query, "scope": args.scope})
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        if not data:
            sys.stderr.write("No matches for '%s'\n" % args.query)
            return 0
        sys.stderr.write("Found %d matches for '%s':\n" % (len(data), args.query))
        for r in data:
            sys.stderr.write("\n[%s] traj=%s step=%d\n" % (r["type"], r["trajectory_id"][:20] if r["trajectory_id"] else "?", r["step"]))
            text = r["text"].replace("\n", " ")[:200]
            sys.stderr.write("  %s\n" % text)
        return 0

    if args.cmd == "search-sessions":
        ok, data, err = reader.Run("search-sessions", {"query": args.query, "limit": args.limit, "detail": args.detail})
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        sys.stderr.write("Search: '%s' → %d sessions (keywords: %s)\n" % (data["query"], data["session_count"], ", ".join(data["keywords"])))
        for s in data["sessions"]:
            sys.stderr.write("\n  [score=%d] %s\n" % (s["score"], s["trajectory_id"][:40]))
            sys.stderr.write("    prompt: %s\n" % (s["first_prompt"] or "")[:100])
            sys.stderr.write("    steps=%d rounds=%d matches=%s\n" % (s["step_count"], s["round_count"], s["matches"]))
            if s.get("top_matches"):
                for m in s["top_matches"][:2]:
                    sys.stderr.write("    → [%s step=%d] %s\n" % (m["role"], m["step"], (m["snippet"] or "")[:120].replace("\n", " ")))
        sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")
        return 0

    if args.cmd == "session-detail":
        ok, data, err = reader.Run("session-detail", {"trajectory_id": args.trajectory_id, "max_messages": args.max_messages})
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        t = data["trajectory"]
        sys.stderr.write("Session: %s\n" % t["id"][:40])
        sys.stderr.write("  prompt: %s\n" % (t["first_prompt"] or "")[:120])
        sys.stderr.write("  steps=%d rounds=%d\n" % (t["step_count"], t["round_count"]))
        sys.stderr.write("  counts: %s\n" % data["counts"])
        sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")
        return 0

    if args.cmd == "search-files":
        ok, data, err = reader.Run("search-files", {"query": args.query, "limit": args.limit})
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        sys.stderr.write("File search: '%s' → %d sessions\n" % (data["query"], data["session_count"]))
        for s in data["sessions"]:
            sys.stderr.write("\n  [total=%d] %s\n" % (s["total"], s["trajectory_id"][:40]))
            sys.stderr.write("    prompt: %s\n" % (s.get("first_prompt") or "")[:100])
            sys.stderr.write("    files=%d commands=%d assistant=%d\n" % (s["file_hits"], s["command_hits"], s["assistant_hits"]))
            for ex in s["examples"][:2]:
                sys.stderr.write("    → [%s step=%d] %s\n" % (ex["type"], ex["step"], (ex["text"] or "")[:120].replace("\n", " ")))
        sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")
        return 0

    if args.cmd == "export":
        ok, data, err = reader.Run("export", {"file": args.file, "outdir": args.outdir})
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        sys.stderr.write("Exported %d rounds, %d files → %s\n" % (data["rounds"], len(data["files"]), data["outdir"]))
        return 0

    if args.cmd == "export-db":
        # Auto-load all if nothing loaded
        ok, stats, _ = reader.Run("stats")
        if stats["trajectories"] == 0:
            sys.stderr.write("Nothing loaded — auto-loading all .pb files...\n")
            reader.Run("load-all")
        ok, data, err = reader.Run("export-db", {})
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")
        return 0

    if args.cmd == "verify-db":
        ok, data, err = reader.Run("verify-db", {})
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")
        return 0

    if args.cmd == "clean":
        ok, data, err = reader.Run("clean", {"confirm": args.confirm})
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")
        return 0

    if args.cmd == "compress":
        ok, data, err = reader.Run("compress", {"input_path": args.input, "output_path": args.output})
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        stats = data.get("stats", {})
        sys.stderr.write("Compressed: %d lines -> %d tokens (ratio %s:1)\n" % (
            data.get("line_count", 0), data.get("token_count", 0),
            stats.get("compression_ratio", 0)))
        sys.stderr.write("Output: %s\n" % data.get("output_path", ""))
        sys.stdout.write(json.dumps({"output_path": data.get("output_path"),
                                      "token_count": data.get("token_count"),
                                      "line_count": data.get("line_count"),
                                      "stats": stats}, indent=2, default=str) + "\n")
        return 0

    if args.cmd == "dry-run":
        ok, data, err = reader.Run("dry_run", {"input_path": args.input})
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        stats = data.get("stats", {})
        sys.stderr.write("Dry run: %d lines -> %d tokens (ratio %s:1)\n" % (
            data.get("line_count", 0), data.get("token_count", 0),
            stats.get("compression_ratio", 0)))
        tag_counts = stats.get("tag_counts", {})
        for tag in sorted(tag_counts.keys()):
            sys.stderr.write("  %s: %d\n" % (tag, tag_counts[tag]))
        sys.stdout.write(json.dumps({"token_count": data.get("token_count"),
                                      "line_count": data.get("line_count"),
                                      "stats": stats}, indent=2, default=str) + "\n")
        return 0

    if args.cmd == "stats":
        ok, data, err = reader.Run("stats")
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            return 1
        sys.stderr.write("RAM DB Statistics:\n")
        for k, v in data.items():
            sys.stderr.write("  %s: %d\n" % (k, v))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(cli_main())
