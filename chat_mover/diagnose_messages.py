#!/usr/bin/env python3
"""Diagnose why 22k messages failed to insert into CHAT_DEVIN."""
import sqlite3, json, shutil, subprocess, os, sys
from datetime import datetime

SQLITE_DB = os.path.expanduser("~/.local/share/devin/cli/sessions.db")
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
COPY = f"/tmp/dss_diag_copy_{TS}.db"
SQL = f"/tmp/dss_diag_{TS}.sql"
CLEAN = f"/tmp/dss_diag_clean_{TS}.db"

print(f"[1/4] copy sqlite -> {COPY}")
shutil.copy2(SQLITE_DB, COPY)

print(f"[2/4] recover -> {SQL}")
with open(SQL, "w") as f:
    subprocess.run(["sqlite3", COPY, ".recover"], stdout=f, stderr=subprocess.PIPE, timeout=300)

print(f"[3/4] build clean -> {CLEAN}")
with open(SQL) as f:
    subprocess.run(["sqlite3", CLEAN], stdin=f, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=300)

db = sqlite3.connect(f"file:{CLEAN}?mode=ro", uri=True)
db.text_factory = lambda b: b.decode("utf-8", "replace")
c = db.cursor()

c.execute("SELECT COUNT(*) FROM message_nodes")
total = c.fetchone()[0]
print(f"\ntotal message_nodes: {total}")

c.execute("SELECT COUNT(*) FROM message_nodes WHERE node_id IS NULL")
print(f"null node_id: {c.fetchone()[0]}")

c.execute("SELECT COUNT(*) FROM message_nodes WHERE chat_message IS NULL")
print(f"null chat_message: {c.fetchone()[0]}")

c.execute("SELECT COUNT(*) FROM message_nodes WHERE session_id IS NULL OR session_id = ''")
print(f"null/empty session_id: {c.fetchone()[0]}")

# null bytes
c.execute("SELECT node_id, chat_message FROM message_nodes")
nul = 0
non_utf8 = 0
empty_content = 0
huge = 0
while True:
    row = c.fetchone()
    if row is None: break
    nid, cm = row
    if cm is None: continue
    s = str(cm)
    if "\x00" in s: nul += 1
    if len(s) > 16_000_000: huge += 1
    try:
        m = json.loads(s) if isinstance(s, str) else None
        if m and (m.get("content") is None or m.get("content") == ""): empty_content += 1
    except Exception: pass

print(f"null bytes in chat_message: {nul}")
print(f"empty content in parsed: {empty_content}")
print(f"huge (>16MB): {huge}")

# check for duplicate (session_id, node_id) in source
c.execute("SELECT session_id, node_id, COUNT(*) as cnt FROM message_nodes GROUP BY session_id, node_id HAVING cnt > 1 LIMIT 10")
dups = c.fetchall()
print(f"\nduplicate (session_id, node_id) in source: {len(dups)} shown")
for d in dups[:5]: print(f"  {d}")

# check for duplicate message_id
c.execute("SELECT message_id, COUNT(*) as cnt FROM message_nodes WHERE message_id IS NOT NULL GROUP BY message_id HAVING cnt > 1 LIMIT 10")
mdups = c.fetchall()
print(f"\nduplicate message_id in source: {len(mdups)} shown")
for d in mdups[:5]: print(f"  {d}")

# how many have NULL message_id
c.execute("SELECT COUNT(*) FROM message_nodes WHERE message_id IS NULL OR message_id = ''")
print(f"\nnull/empty message_id: {c.fetchone()[0]}")

db.close()
print(f"\n[done] temp files left: {COPY}, {SQL}, {CLEAN}")
