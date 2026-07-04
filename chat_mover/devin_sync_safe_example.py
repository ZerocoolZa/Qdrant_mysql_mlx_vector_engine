#!/usr/bin/env python3
"""Devin Sync Safe — streaming pipeline, MySQL-driven uniqueness, <300 lines.
Usage: python devin_sync_safe_example.py [--watch|--status|--verify|--dry-run]"""
import os, sys, json, glob, time, shutil, sqlite3, subprocess, re
from datetime import datetime, timezone
import mysql.connector

SQLITE_DB = os.path.expanduser("~/.local/share/devin/cli/sessions.db")
TRANSCRIPTS_DIR = os.path.expanduser("~/.local/share/devin/cli/transcripts")
SUMMARIES_DIR = os.path.expanduser("~/.local/share/devin/cli/summaries")
TMP_COPY, TMP_DB, TMP_SQL = "/tmp/dss_copy.db", "/tmp/dss_clean.db", "/tmp/dss.sql"
MYSQL = dict(host="localhost", user="root", database="devin", autocommit=True, connection_timeout=10)
POLL, RETRIES, BACKOFF = 30, 5, 2
DRY = "--dry-run" in sys.argv
FV = re.compile(r'<file-view\s+path="([^"]+)"', re.I)
FC = re.compile(r'File created successfully at:\s*(.+?)(?:\n|$)', re.I)
FU = re.compile(r'The file\s+(.+?)\s+has been updated', re.I)


def utc(ts):
    try: return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if ts else None
    except Exception: return None


def jd(v):
    return json.dumps(v, ensure_ascii=False, default=str) if isinstance(v, (dict, list)) else v


def parse_chat(raw):
    if raw is None: return None, None, None
    if isinstance(raw, str):
        try: raw = json.loads(raw)
        except Exception: return None, raw[:65000], None
    if not isinstance(raw, dict): return None, str(raw)[:65000], None
    t = raw.get("content", "")
    if not isinstance(t, str): t = json.dumps(t, ensure_ascii=False, default=str)
    if len(t) > 16_000_000: t = t[:16_000_000] + "\n...[truncated]"
    return raw.get("role"), t, raw.get("message_id")


def mconn():
    e = None
    for i in range(RETRIES):
        try:
            c = mysql.connector.connect(**MYSQL)
            if c.is_connected(): return c
        except Exception as x: e = x; time.sleep(BACKOFF * (2 ** i))
    raise RuntimeError(f"MySQL: {e}")


def recover():
    if not os.path.exists(SQLITE_DB): print("[skip] no sqlite"); return None
    shutil.copy2(SQLITE_DB, TMP_COPY)
    with open(TMP_SQL, "w") as f:
        subprocess.run(["sqlite3", TMP_COPY, ".recover"], stdout=f, stderr=subprocess.PIPE, timeout=300)
    if os.path.exists(TMP_DB): os.remove(TMP_DB)
    with open(TMP_SQL) as f:
        subprocess.run(["sqlite3", TMP_DB], stdin=f, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=300)
    db = sqlite3.connect(f"file:{TMP_DB}?mode=ro", uri=True)
    db.execute("PRAGMA query_only=ON")
    db.text_factory = lambda b: b.decode("utf-8", "replace")
    cur = db.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    if not cur.fetchall():
        db.close(); raise RuntimeError("Recovery failed: no tables found")
    return db


def cleanup():
    for f in (TMP_COPY, TMP_DB, TMP_SQL):
        if os.path.exists(f): os.remove(f)


def stream(s, table):
    """Stream rows from SQLite one at a time. Zero memory accumulation."""
    s.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in s.fetchall()]
    s.execute(f"SELECT * FROM {table}")
    while True:
        row = s.fetchone()
        if row is None: break
        yield dict(zip(cols, row))


def ins(m, sql, args, label=""):
    """MySQL-driven uniqueness via INSERT IGNORE. No Python dedup sets."""
    if DRY: return False
    try:
        m.execute(sql, args)
        return m.rowcount > 0
    except Exception as e:
        print(f"  [err] {label}: {str(e)[:120]}")
        return False


def sync_sessions(s, m):
    sql = """INSERT IGNORE INTO devin_sessions
        (id,title,working_directory,backend_type,model,agent_mode,created_at,created_at_dt,
         last_activity_at,last_activity_at_dt,hidden,main_chain_id,shell_last_seen_index,
         cogs_json,workspace_dirs,metadata,source)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'sessions.db')"""
    n = t = 0
    for r in stream(s, "sessions"):
        t += 1
        if ins(m, sql, (r["id"], r["title"], r["working_directory"], r["backend_type"], r["model"],
            r["agent_mode"], r["created_at"], utc(r["created_at"]), r["last_activity_at"],
            utc(r["last_activity_at"]), r["hidden"], r["main_chain_id"], r["shell_last_seen_index"],
            jd(r["cogs_json"]), jd(r["workspace_dirs"]), jd(r["metadata"])), "sessions"): n += 1
    print(f"  sessions:         {n} new / {t} total")


def sync_messages(s, m):
    sql = """INSERT IGNORE INTO devin_messages
        (session_id,node_id,parent_node_id,message_id,role,content,created_at,created_at_dt,metadata,source)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'sessions.db')"""
    n = t = 0
    for r in stream(s, "message_nodes"):
        t += 1
        role, content, msgid = parse_chat(r.get("chat_message"))
        if ins(m, sql, (r.get("session_id"), r.get("node_id"), r.get("parent_node_id"), msgid,
            role, content, r.get("created_at"), utc(r.get("created_at")), jd(r.get("metadata"))), "messages"): n += 1
    print(f"  messages:         {n} new / {t} total")


def sync_commits(s, m):
    sql = """INSERT IGNORE INTO devin_rendered_commits
        (session_id,sequence_number,rendered_html,created_at,created_at_dt) VALUES (%s,%s,%s,%s,%s)"""
    n = t = 0
    for r in stream(s, "rendered_commits"):
        t += 1
        if ins(m, sql, (r.get("session_id"), r.get("sequence_number"), r.get("rendered_html", ""),
            r.get("created_at"), utc(r.get("created_at"))), "commits"): n += 1
    print(f"  rendered_commits: {n} new / {t} total")


def sync_tools(s, m):
    try:
        data = stream(s, "tool_call_state")
    except sqlite3.DatabaseError:
        print("  tool_calls:       table missing"); return
    sql = """INSERT IGNORE INTO devin_tool_calls
        (session_id,tool_call_id,tool_call_json,tool_call_update_json) VALUES (%s,%s,%s,%s)"""
    n = t = 0
    for r in data:
        t += 1
        if ins(m, sql, (r.get("session_id"), r.get("tool_call_id"), jd(r.get("tool_call_json")),
            jd(r.get("tool_call_update_json"))), "tools"): n += 1
    print(f"  tool_calls:       {n} new / {t} total")


def sync_turns(s, m):
    """Stream sessions, build turns, let MySQL UNIQUE index handle dedup."""
    m.execute("SELECT DISTINCT session_id FROM devin_messages")
    sids = [r[0] for r in m.fetchall()]
    sql = """INSERT IGNORE INTO devin_chat_turns
        (session_id,turn_seq,user_message,assistant_message,files_json,file_paths,created_at,created_at_dt)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"""
    n = 0
    for sid in sids:
        try:
            s.execute("SELECT node_id,chat_message,created_at FROM message_nodes WHERE session_id=? ORDER BY created_at,node_id", (sid,))
        except Exception as e:
            print(f"  [err] turns {sid}: {e}"); continue
        seq = 0; cur = None; seen = set()
        while True:
            row = s.fetchone()
            if row is None: break
            _, raw, ca = row
            try: msg = json.loads(raw) if isinstance(raw, str) else raw
            except Exception: continue
            role = msg.get("role", ""); content = msg.get("content", "") or ""
            if role == "user":
                if cur: n += _turn(m, sql, cur)
                seq += 1; seen = set(); cur = {"sid": sid, "seq": seq, "user": content, "ai": "", "files": [], "ca": ca}
            elif cur and role == "assistant":
                cur["ai"] += content + "\n"
                for tc in msg.get("tool_calls", []):
                    a = tc.get("arguments", {})
                    if isinstance(a, str):
                        try: a = json.loads(a)
                        except Exception: continue
                    p = a.get("file_path") or a.get("path")
                    if p and p not in seen: seen.add(p); cur["files"].append({"path": p, "op": tc.get("name", "")})
            elif cur and role == "tool":
                for rx in FV.finditer(content):
                    p = rx.group(1)
                    if p not in seen: seen.add(p); cur["files"].append({"path": p, "op": "read"})
                for rx in FC.finditer(content):
                    p = rx.group(1).strip()
                    if p not in seen: seen.add(p); cur["files"].append({"path": p, "op": "write"})
                for rx in FU.finditer(content):
                    p = rx.group(1).strip()
                    if p not in seen: seen.add(p); cur["files"].append({"path": p, "op": "edit"})
        if cur: n += _turn(m, sql, cur)
    print(f"  chat_turns:       {n} new / {len(sids)} sessions")


def _turn(m, sql, t):
    fj = json.dumps(t["files"], ensure_ascii=False, default=str)
    fp = ", ".join(sorted({f["path"] for f in t["files"]}))
    return 1 if ins(m, sql, (t["sid"], t["seq"], t["user"][:16_000_000], t["ai"][:16_000_000],
        fj[:16_000_000], fp, t["ca"], utc(t["ca"])), "turns") else 0


def sync_dir(m, folder, ext, sql, afn, label):
    if not os.path.isdir(folder): return
    files = glob.glob(os.path.join(folder, f"*{ext}")); n = 0
    for path in files:
        name = os.path.basename(path)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f: txt = f.read()
        except Exception as e:
            print(f"  [err] {label} {name}: {e}"); continue
        if ins(m, sql, afn(name, txt), label): n += 1
    print(f"  {label:18s} {n} new / {len(files)} total")


def run_sync():
    print("=" * 60)
    print(f"Devin Sync Safe — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{' [DRY RUN]' if DRY else ''}")
    print("=" * 60)
    sdb = mdb = None
    try:
        sdb = recover()
        if not sdb: return False
        scur, mdb, mcur = sdb.cursor(), mconn(), None
        mdb = mconn(); mcur = mdb.cursor()
        sync_sessions(scur, mcur); sync_messages(scur, mcur); sync_tools(scur, mcur)
        sync_commits(scur, mcur); sync_turns(scur, mcur)
        sync_dir(mcur, TRANSCRIPTS_DIR, ".json",
                 "INSERT IGNORE INTO devin_transcripts (session_id,transcript_file,raw_json,imported_at) VALUES (%s,%s,%s,%s)",
                 lambda n, t: (n.removesuffix(".json"), n, t, datetime.now()), "transcripts")
        sync_dir(mcur, SUMMARIES_DIR, ".md",
                 "INSERT IGNORE INTO devin_summaries (summary_file,content,file_size,imported_at) VALUES (%s,%s,%s,%s)",
                 lambda n, t: (n, t, len(t), datetime.now()), "summaries")
        print("SYNC COMPLETE"); return True
    except Exception as e:
        print(f"ERROR: {e}"); return False
    finally:
        for db in (sdb, mdb):
            try:
                if db: db.close()
            except Exception: pass
        cleanup()


def show_status():
    db = mconn(); cur = db.cursor()
    tables = ["devin_sessions", "devin_messages", "devin_tool_calls", "devin_rendered_commits", "devin_transcripts", "devin_summaries", "devin_chat_turns"]
    print("=" * 50)
    for t in tables:
        try: cur.execute(f"SELECT COUNT(*) FROM {t}"); print(f"  {t:26s} {cur.fetchone()[0]:>12,}")
        except Exception as e: print(f"  {t:26s} ERROR: {e}")
    db.close()


def verify(s, m):
    print("=" * 50); print("VERIFY — SQLite vs MySQL"); print("=" * 50)
    for st, mt in [("sessions", "devin_sessions"), ("message_nodes", "devin_messages"), ("rendered_commits", "devin_rendered_commits")]:
        try:
            s.execute(f"SELECT COUNT(*) FROM {st}"); sc = s.fetchone()[0]
            m.execute(f"SELECT COUNT(*) FROM {mt}"); mc = m.fetchone()[0]
            print(f"  {st:20s} sqlite={sc:>8,}  mysql={mc:>8,}  {'OK' if sc <= mc else 'MISMATCH'}")
        except Exception as e: print(f"  {st:20s} ERROR: {e}")


def main():
    if "--status" in sys.argv: show_status()
    elif "--verify" in sys.argv:
        sdb, mdb = recover(), mconn()
        if sdb and mdb: verify(sdb.cursor(), mdb.cursor())
        try: sdb.close()
        except: pass
        try: mdb.close()
        except: pass
        cleanup()
    elif "--watch" in sys.argv:
        print(f"Watching every {POLL}s... Ctrl+C to stop.")
        while True:
            try: run_sync(); time.sleep(POLL)
            except KeyboardInterrupt: print("Stopped."); break
            except Exception as e: print(f"Watch error: {e}"); time.sleep(POLL)
    else: run_sync()


if __name__ == "__main__":
    main()
