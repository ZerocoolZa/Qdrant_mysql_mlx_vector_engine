#!/usr/bin/env python3
# [@GHOST]{[@file<DevinSyncUnit.py>][@domain<chat_mover>][@role<devin_sync>][@auth<devin>][@date<2026-07-04>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<chat_mover_sync>][@return<tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths|abc|inheritance>]}
# [@FILEID]{[@fileid<chat_mover.DevinSyncUnit>]}
# [@SUMMARY]{[@summary<Unified Devin sync unit: streams SQLite sessions.db to MySQL (devin + CHAT_DEVIN). Combines devin_sync_safe.py, devin_sync_safe_example.py, devin_sync_chat_devin.py into one. Supports dual-target, constraint checking, turns extraction, file sync, verify, status, watch, dry-run.>]}
# [@CLASS]{[@class<DevinSyncUnit>]}
# [@METHOD]{[@method<Run>][@method<CmdSync>][@method<CmdStatus>][@method<CmdVerify>][@method<CmdWatch>][@method<SyncSessions>][@method<SyncMessages>][@method<SyncTools>][@method<SyncCommits>][@method<SyncTurns>][@method<SyncDir>][@method<RecoverSqlite>][@method<CheckConstraints>][@method<ParseChat>][@method<StreamRows>][@method<MysqlConnect>][@method<Cleanup>][@method<ReadState>][@method<SetConfig>]}

"""
DevinSyncUnit — Unified Devin SQLite to MySQL sync.

Combines 3 files into one:
  - devin_sync_safe.py         (target: devin DB, Python dedup)
  - devin_sync_safe_example.py (target: devin DB, INSERT IGNORE dedup, turns)
  - devin_sync_chat_devin.py   (target: CHAT_DEVIN DB, constraints, turns)

Usage:
    python3 DevinSyncUnit.py sync [--target devin|chat_devin|both]
    python3 DevinSyncUnit.py status [--target devin|chat_devin|both]
    python3 DevinSyncUnit.py verify
    python3 DevinSyncUnit.py watch [--poll 30] [--target both]
    python3 DevinSyncUnit.py sync --dry-run
"""

import os
import sys
import json
import glob
import time
import shutil
import sqlite3
import subprocess
import re
from datetime import datetime, timezone
from pathlib import Path
import mysql.connector

# ════════════════════════════════════════════════════════════════
# UPPERCASE CONSTANTS
# ════════════════════════════════════════════════════════════════

SQLITE_DB = os.path.expanduser("~/.local/share/devin/cli/sessions.db")
TRANSCRIPTS_DIR = os.path.expanduser("~/.local/share/devin/cli/transcripts")
SUMMARIES_DIR = os.path.expanduser("~/.local/share/devin/cli/summaries")

TMP_COPY = "/tmp/devin_sync_copy.db"
TMP_DB = "/tmp/devin_sync_clean.db"
TMP_SQL = "/tmp/devin_sync_recover.sql"

MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_TIMEOUT = 10
POLL = 30
RETRIES = 5
BACKOFF = 2

TARGET_DEVIN = "devin"
TARGET_CHAT_DEVIN = "CHAT_DEVIN"

REGEX_FILE_VIEW = re.compile(r'<file-view\s+path="([^"]+)"', re.I)
REGEX_FILE_CREATE = re.compile(r'File created successfully at:\s*(.+?)(?:\n|$)', re.I)
REGEX_FILE_UPDATE = re.compile(r'The file\s+(.+?)\s+has been updated', re.I)

REQUIRED_INDEXES = {
    "devin_messages": ["uq_session_node"],
    "devin_sessions": ["PRIMARY"],
    "devin_tool_calls": ["uq_tool_call_id"],
    "devin_rendered_commits": ["uq_session_seq"],
    "devin_transcripts": ["uq_transcript_file"],
    "devin_summaries": ["uq_summary_file"],
    "devin_chat_turns": ["uq_turn"],
}


class DevinSyncUnit:
    """Unified Devin SQLite to MySQL sync unit. Dual-target, streaming, constraint-safe."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "target": TARGET_BOTH if (TARGET_BOTH := "both") else "both",
            "dry_run": False,
            "poll": POLL,
            "sqlite_db": SQLITE_DB,
            "transcripts_dir": TRANSCRIPTS_DIR,
            "summaries_dir": SUMMARIES_DIR,
            "mysql_host": MYSQL_HOST,
            "mysql_user": MYSQL_USER,
            "sync_result": {},
            "errors": [],
        }
        self.conn_sdb = None
        self.conn_mdb = None

    def _p(self, key):
        return self.state.get(key)

    def read_state(self):
        return dict(self.state)

    def set_config(self, key, value):
        self.state[key] = value
        return (1, self.state, None)

    def Run(self, command, params=None):
        """Dispatch entry point. Commands: sync, status, verify, watch."""
        dispatch = {
            "sync": self.CmdSync,
            "status": self.CmdStatus,
            "verify": self.CmdVerify,
            "watch": self.CmdWatch,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (404, "Unknown command: " + str(command), 0))
        return handler(params)

    # ════════════════════════════════════════════════════════════════
    # COMMAND DISPATCH
    # ════════════════════════════════════════════════════════════════

    def CmdSync(self, params):
        params = params or {}
        self.state["dry_run"] = params.get("dry_run", False)
        targets = self._resolve_targets(params.get("target", "both"))
        results = {}
        for target in targets:
            results[target] = self._sync_one(target)
        return (1, results, None)

    def CmdStatus(self, params):
        params = params or {}
        targets = self._resolve_targets(params.get("target", "both"))
        results = {}
        for target in targets:
            results[target] = self._status_one(target)
        return (1, results, None)

    def CmdVerify(self, params):
        params = params or {}
        sdb = self.RecoverSqlite()
        if sdb is None:
            return (0, None, (1, "SQLite recovery failed", 0))
        scur = sdb.cursor()
        targets = self._resolve_targets(params.get("target", "both"))
        results = {}
        for target in targets:
            mdb = self.MysqlConnect(target)
            if mdb is None:
                results[target] = {"error": "MySQL connection failed"}
                continue
            mcur = mdb.cursor()
            results[target] = self._verify_one(scur, mcur, target)
            mdb.close()
        sdb.close()
        self.Cleanup()
        return (1, results, None)

    def CmdWatch(self, params):
        params = params or {}
        self.state["poll"] = params.get("poll", POLL)
        targets = self._resolve_targets(params.get("target", "both"))
        while True:
            try:
                for target in targets:
                    self._sync_one(target)
                time.sleep(self.state["poll"])
            except KeyboardInterrupt:
                return (1, {"stopped": True}, None)
            except Exception as e:
                self.state["errors"].append(str(e))
                time.sleep(self.state["poll"])

    # ════════════════════════════════════════════════════════════════
    # TARGET RESOLUTION
    # ════════════════════════════════════════════════════════════════

    def _resolve_targets(self, target_str):
        if target_str == "both":
            return [TARGET_DEVIN, TARGET_CHAT_DEVIN]
        if target_str == "devin":
            return [TARGET_DEVIN]
        if target_str == "chat_devin":
            return [TARGET_CHAT_DEVIN]
        return [TARGET_DEVIN, TARGET_CHAT_DEVIN]

    # ════════════════════════════════════════════════════════════════
    # SYNC (one target)
    # ════════════════════════════════════════════════════════════════

    def _sync_one(self, target):
        result = {"target": target, "dry_run": self.state["dry_run"], "tables": {}}
        sdb = None
        mdb = None
        try:
            sdb = self.RecoverSqlite()
            if sdb is None:
                result["error"] = "SQLite recovery failed"
                return result
            scur = sdb.cursor()

            mdb = self.MysqlConnect(target)
            if mdb is None:
                result["error"] = "MySQL connection failed"
                return result
            mcur = mdb.cursor(prepared=True)

            if target == TARGET_CHAT_DEVIN:
                check = self.CheckConstraints(mcur)
                if check[0] == 0:
                    result["error"] = check[2][1]
                    return result

            result["tables"]["sessions"] = self.SyncSessions(scur, mcur)
            result["tables"]["messages"] = self.SyncMessages(scur, mcur)
            result["tables"]["tool_calls"] = self.SyncTools(scur, mcur)
            result["tables"]["rendered_commits"] = self.SyncCommits(scur, mcur)
            result["tables"]["chat_turns"] = self.SyncTurns(scur, mcur)
            result["tables"]["transcripts"] = self.SyncDir(mcur, self.state["transcripts_dir"], ".json",
                "devin_transcripts",
                "INSERT IGNORE INTO devin_transcripts (session_id,transcript_file,raw_json,imported_at) VALUES (%s,%s,%s,%s)",
                lambda n, t: (n.removesuffix(".json"), n, t, datetime.now()))
            result["tables"]["summaries"] = self.SyncDir(mcur, self.state["summaries_dir"], ".md",
                "devin_summaries",
                "INSERT IGNORE INTO devin_summaries (summary_file,content,file_size,imported_at) VALUES (%s,%s,%s,%s)",
                lambda n, t: (n, t, len(t), datetime.now()))

            result["status"] = "complete"
            return result
        except Exception as e:
            result["error"] = str(e)
            result["status"] = "failed"
            return result
        finally:
            for db in (sdb, mdb):
                try:
                    if db:
                        db.close()
                except Exception:
                    pass
            self.Cleanup()

    # ════════════════════════════════════════════════════════════════
    # SYNC TABLES
    # ════════════════════════════════════════════════════════════════

    def SyncSessions(self, scur, mcur):
        sql = """INSERT IGNORE INTO devin_sessions
            (id,title,working_directory,backend_type,model,agent_mode,created_at,created_at_dt,
             last_activity_at,last_activity_at_dt,hidden,main_chain_id,shell_last_seen_index,
             cogs_json,workspace_dirs,metadata,source)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'sessions.db')"""
        n = t = 0
        for r in self.StreamRows(scur, "sessions"):
            t += 1
            if self._ins(mcur, sql, (
                r["id"], r["title"], r["working_directory"], r["backend_type"], r["model"],
                r["agent_mode"], r["created_at"], self._utc(r["created_at"]),
                r["last_activity_at"], self._utc(r["last_activity_at"]),
                r["hidden"], r["main_chain_id"], r["shell_last_seen_index"],
                self._jd(r["cogs_json"]), self._jd(r["workspace_dirs"]), self._jd(r["metadata"])
            ), "sessions"):
                n += 1
        return {"new": n, "total": t}

    def SyncMessages(self, scur, mcur):
        sql = """INSERT IGNORE INTO devin_messages
            (session_id,node_id,parent_node_id,message_id,role,content,created_at,created_at_dt,metadata,source)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'sessions.db')"""
        n = t = 0
        for r in self.StreamRows(scur, "message_nodes"):
            t += 1
            role, content, msgid = self.ParseChat(r.get("chat_message"))
            if self._ins(mcur, sql, (
                r.get("session_id"), r.get("node_id"), r.get("parent_node_id"), msgid,
                role, content, r.get("created_at"), self._utc(r.get("created_at")),
                self._jd(r.get("metadata"))
            ), "messages"):
                n += 1
        return {"new": n, "total": t}

    def SyncTools(self, scur, mcur):
        try:
            data = list(self.StreamRows(scur, "tool_call_state"))
        except sqlite3.DatabaseError:
            return {"new": 0, "total": 0, "note": "table missing"}
        sql = """INSERT IGNORE INTO devin_tool_calls
            (session_id,tool_call_id,tool_call_json,tool_call_update_json) VALUES (%s,%s,%s,%s)"""
        n = t = 0
        for r in data:
            t += 1
            if self._ins(mcur, sql, (
                r.get("session_id"), r.get("tool_call_id"),
                self._jd(r.get("tool_call_json")), self._jd(r.get("tool_call_update_json"))
            ), "tools"):
                n += 1
        return {"new": n, "total": t}

    def SyncCommits(self, scur, mcur):
        sql = """INSERT IGNORE INTO devin_rendered_commits
            (session_id,sequence_number,rendered_html,created_at,created_at_dt) VALUES (%s,%s,%s,%s,%s)"""
        n = t = 0
        for r in self.StreamRows(scur, "rendered_commits"):
            t += 1
            if self._ins(mcur, sql, (
                r.get("session_id"), r.get("sequence_number"), r.get("rendered_html", ""),
                r.get("created_at"), self._utc(r.get("created_at"))
            ), "commits"):
                n += 1
        return {"new": n, "total": t}

    def SyncTurns(self, scur, mcur):
        """Build user→assistant turns with file extraction. MySQL UNIQUE handles dedup."""
        mcur.execute("SELECT DISTINCT session_id FROM devin_messages")
        sids = [r[0] for r in mcur.fetchall()]
        sql = """INSERT IGNORE INTO devin_chat_turns
            (session_id,turn_seq,user_message,assistant_message,files_json,file_paths,created_at,created_at_dt)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"""
        n = 0
        for sid in sids:
            try:
                scur.execute(
                    "SELECT node_id,chat_message,created_at FROM message_nodes WHERE session_id=? ORDER BY created_at,node_id",
                    (sid,)
                )
            except Exception as e:
                self.state["errors"].append("turns " + str(sid) + ": " + str(e))
                continue
            seq = 0
            cur = None
            seen = set()
            while True:
                row = scur.fetchone()
                if row is None:
                    break
                _, raw, ca = row
                try:
                    msg = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    continue
                role = msg.get("role", "")
                content = msg.get("content", "") or ""
                if role == "user":
                    if cur:
                        n += self._emit_turn(mcur, sql, cur)
                    seq += 1
                    seen = set()
                    cur = {"sid": sid, "seq": seq, "user": content, "ai": "", "files": [], "ca": ca}
                elif cur and role == "assistant":
                    cur["ai"] += content + "\n"
                    for tc in msg.get("tool_calls", []):
                        a = tc.get("arguments", {})
                        if isinstance(a, str):
                            try:
                                a = json.loads(a)
                            except Exception:
                                continue
                        p = a.get("file_path") or a.get("path")
                        if p and p not in seen:
                            seen.add(p)
                            cur["files"].append({"path": p, "op": tc.get("name", "")})
                elif cur and role == "tool":
                    for rx in REGEX_FILE_VIEW.finditer(content):
                        p = rx.group(1)
                        if p not in seen:
                            seen.add(p)
                            cur["files"].append({"path": p, "op": "read"})
                    for rx in REGEX_FILE_CREATE.finditer(content):
                        p = rx.group(1).strip()
                        if p not in seen:
                            seen.add(p)
                            cur["files"].append({"path": p, "op": "write"})
                    for rx in REGEX_FILE_UPDATE.finditer(content):
                        p = rx.group(1).strip()
                        if p not in seen:
                            seen.add(p)
                            cur["files"].append({"path": p, "op": "edit"})
            if cur:
                n += self._emit_turn(mcur, sql, cur)
        return {"new": n, "sessions": len(sids)}

    def _emit_turn(self, mcur, sql, t):
        fj = json.dumps(t["files"], ensure_ascii=False, default=str)
        fp = ", ".join(sorted({f["path"] for f in t["files"]}))
        return 1 if self._ins(mcur, sql, (
            t["sid"], t["seq"], t["user"][:16000000], t["ai"][:16000000],
            fj[:16000000], fp, t["ca"], self._utc(t["ca"])
        ), "turns") else 0

    def SyncDir(self, mcur, folder, ext, table, sql, arg_fn):
        if not os.path.isdir(folder):
            return {"new": 0, "total": 0, "note": "dir missing"}
        files = glob.glob(os.path.join(folder, "*" + ext))
        n = 0
        for path in files:
            name = os.path.basename(path)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    txt = f.read()
            except Exception as e:
                self.state["errors"].append(name + ": " + str(e))
                continue
            if self._ins(mcur, sql, arg_fn(name, txt), table):
                n += 1
        return {"new": n, "total": len(files)}

    # ════════════════════════════════════════════════════════════════
    # STATUS + VERIFY
    # ════════════════════════════════════════════════════════════════

    def _status_one(self, target):
        mdb = self.MysqlConnect(target)
        if mdb is None:
            return {"error": "MySQL connection failed"}
        cur = mdb.cursor()
        tables = [
            "devin_sessions", "devin_messages", "devin_tool_calls",
            "devin_rendered_commits", "devin_transcripts", "devin_summaries", "devin_chat_turns"
        ]
        result = {}
        for t in tables:
            try:
                cur.execute("SELECT COUNT(*) FROM " + t)
                result[t] = cur.fetchone()[0]
            except Exception as e:
                result[t] = "ERROR: " + str(e)
        mdb.close()
        return result

    def _verify_one(self, scur, mcur, target):
        pairs = [
            ("sessions", "devin_sessions"),
            ("message_nodes", "devin_messages"),
            ("rendered_commits", "devin_rendered_commits"),
        ]
        result = {}
        for st, mt in pairs:
            try:
                scur.execute("SELECT COUNT(*) FROM " + st)
                sc = scur.fetchone()[0]
                mcur.execute("SELECT COUNT(*) FROM " + mt)
                mc = mcur.fetchone()[0]
                result[st] = {"sqlite": sc, "mysql": mc, "ok": sc <= mc}
            except Exception as e:
                result[st] = {"error": str(e)}
        return result

    # ════════════════════════════════════════════════════════════════
    # INFRASTRUCTURE
    # ════════════════════════════════════════════════════════════════

    def RecoverSqlite(self):
        """Copy SQLite, run .recover, return read-only connection."""
        db_path = self.state["sqlite_db"]
        if not os.path.exists(db_path):
            self.state["errors"].append("sqlite missing")
            return None
        shutil.copy2(db_path, TMP_COPY)
        with open(TMP_SQL, "w") as out:
            subprocess.run(
                ["sqlite3", TMP_COPY, ".recover"],
                stdout=out, stderr=subprocess.PIPE, timeout=300
            )
        if os.path.exists(TMP_DB):
            os.remove(TMP_DB)
        with open(TMP_SQL) as sql:
            subprocess.run(
                ["sqlite3", TMP_DB],
                stdin=sql, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=300
            )
        db = sqlite3.connect("file:" + TMP_DB + "?mode=ro", uri=True)
        db.execute("PRAGMA query_only=ON")
        db.text_factory = lambda b: b.decode("utf-8", "replace")
        cur = db.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        if not cur.fetchall():
            db.close()
            self.state["errors"].append("recovery failed: no tables")
            return None
        return db

    def CheckConstraints(self, mcur):
        """Verify required unique indexes exist before syncing."""
        for table, indexes in REQUIRED_INDEXES.items():
            try:
                mcur.execute("SHOW INDEX FROM " + table)
                have = {r[2] for r in mcur.fetchall()}
            except Exception as e:
                return (0, None, (1, "Cannot check " + table + ": " + str(e), 0))
            for idx in indexes:
                if idx not in have:
                    return (0, None, (1, table + " missing index " + idx, 0))
        return (1, True, None)

    def MysqlConnect(self, target):
        """Connect to MySQL with retry/backoff."""
        cfg = dict(
            host=self.state["mysql_host"],
            user=self.state["mysql_user"],
            database=target,
            autocommit=True,
            connection_timeout=MYSQL_TIMEOUT,
        )
        err = None
        for i in range(RETRIES):
            try:
                c = mysql.connector.connect(**cfg)
                if c.is_connected():
                    return c
            except Exception as e:
                err = e
                time.sleep(BACKOFF * (2 ** i))
        self.state["errors"].append("MySQL " + target + ": " + str(err))
        return None

    def ParseChat(self, raw):
        """Extract role, content, message_id from chat_message JSON."""
        if raw is None:
            return None, None, None
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                return None, raw[:65000], None
        if not isinstance(raw, dict):
            return None, str(raw)[:65000], None
        t = raw.get("content", "")
        if not isinstance(t, str):
            t = json.dumps(t, ensure_ascii=False, default=str)
        if len(t) > 16000000:
            t = t[:16000000] + "\n...[truncated]"
        return raw.get("role"), t, raw.get("message_id")

    def StreamRows(self, cur, table):
        """Stream rows from SQLite one at a time. Zero memory accumulation."""
        cur.execute("PRAGMA table_info(" + table + ")")
        cols = [r[1] for r in cur.fetchall()]
        cur.execute("SELECT * FROM " + table)
        while True:
            row = cur.fetchone()
            if row is None:
                break
            yield dict(zip(cols, row))

    def _ins(self, mcur, sql, args, label=""):
        """MySQL INSERT IGNORE. Returns True if row inserted."""
        if self.state["dry_run"]:
            return False
        try:
            mcur.execute(sql, args)
            return mcur.rowcount > 0
        except Exception as e:
            self.state["errors"].append(label + ": " + str(e)[:120])
            return False

    @staticmethod
    def _utc(ts):
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if ts else None
        except Exception:
            return None

    @staticmethod
    def _jd(v):
        return json.dumps(v, ensure_ascii=False, default=str) if isinstance(v, (dict, list)) else v

    def Cleanup(self):
        """Remove temp files."""
        for f in (TMP_COPY, TMP_DB, TMP_SQL):
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass


# ════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ════════════════════════════════════════════════════════════════

def main():
    unit = DevinSyncUnit()
    args = sys.argv[1:]
    if not args:
        print("Usage: python3 DevinSyncUnit.py <sync|status|verify|watch> [--target devin|chat_devin|both] [--dry-run] [--poll N]")
        return

    cmd = args[0]
    params = {}
    if "--dry-run" in args:
        params["dry_run"] = True
    if "--target" in args:
        idx = args.index("--target")
        if idx + 1 < len(args):
            params["target"] = args[idx + 1]
    if "--poll" in args:
        idx = args.index("--poll")
        if idx + 1 < len(args):
            params["poll"] = int(args[idx + 1])

    result = unit.Run(cmd, params)
    if result[0] == 1:
        print(json.dumps(result[1], indent=2, default=str))
    else:
        print("ERROR:", result[2][1])
        sys.exit(1)


if __name__ == "__main__":
    main()
