#!/usr/bin/env python3
"""
Devin Sync Safe (Compact Rewrite) - Chunk 1
"""

import os, sys, json, glob, time, shutil, sqlite3, subprocess
from datetime import datetime, timezone
import mysql.connector

SQLITE_DB = os.path.expanduser("~/.local/share/devin/cli/sessions.db")
TRANSCRIPTS_DIR = os.path.expanduser("~/.local/share/devin/cli/transcripts")
SUMMARIES_DIR = os.path.expanduser("~/.local/share/devin/cli/summaries")

TMP_COPY="/tmp/devin_sync_copy.db"
TMP_DB="/tmp/devin_sync_recovered.db"
TMP_SQL="/tmp/devin_sync_recovered.sql"

MYSQL=dict(
    host="localhost",
    user="root",
    database="devin",
    autocommit=True,
    connection_timeout=10,
)

POLL=30
RETRIES=5
BACKOFF=2


def utc(ts):
    try:
        return datetime.fromtimestamp(int(ts),tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if ts else None
    except:
        return None


def jdump(v):
    if isinstance(v,(dict,list)):
        return json.dumps(v,ensure_ascii=False,default=str)
    return v


def parse_chat(raw):
    if raw is None:
        return None,None,None

    if isinstance(raw,str):
        try:
            raw=json.loads(raw)
        except:
            return None,raw[:65000],None

    if not isinstance(raw,dict):
        return None,str(raw)[:65000],None

    role=raw.get("role")
    msg=raw.get("message_id")
    txt=raw.get("content","")

    if not isinstance(txt,str):
        txt=json.dumps(txt,ensure_ascii=False,default=str)

    if len(txt)>16_000_000:
        txt=txt[:16_000_000]+"\n...[truncated]"

    return role,txt,msg


def mysql_conn():
    err=None
    for i in range(RETRIES):
        try:
            c=mysql.connector.connect(**MYSQL)
            if c.is_connected():
                return c
        except Exception as e:
            err=e
            time.sleep(BACKOFF*(2**i))
    raise RuntimeError(err)


def recover_sqlite():

    if not os.path.exists(SQLITE_DB):
        print("[skip] sqlite missing")
        return None

    shutil.copy2(SQLITE_DB,TMP_COPY)

    with open(TMP_SQL,"w") as out:
        subprocess.run(
            ["sqlite3",TMP_COPY,".recover"],
            stdout=out,
            stderr=subprocess.PIPE,
            timeout=300
        )

    if os.path.exists(TMP_DB):
        os.remove(TMP_DB)

    with open(TMP_SQL) as sql:
        subprocess.run(
            ["sqlite3",TMP_DB],
            stdin=sql,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=300
        )

    db=sqlite3.connect(f"file:{TMP_DB}?mode=ro",uri=True)
    db.execute("PRAGMA query_only=ON")
    db.text_factory=lambda b:b.decode("utf-8","replace")
    return db


def cleanup():
    for f in (TMP_COPY,TMP_DB,TMP_SQL):
        if os.path.exists(f):
            os.remove(f)


def existing(cur,table,key):
    cur.execute(f"SELECT {key} FROM {table}")
    return {r[0] for r in cur.fetchall()}


def existing_pair(cur,table,a,b):
    cur.execute(f"SELECT {a},{b} FROM {table}")
    return {(x,y) for x,y in cur.fetchall()}


def cols(cur,table):
    cur.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]


def rows(cur,table):
    c=cols(cur,table)
    cur.execute(f"SELECT * FROM {table}")
    for r in cur.fetchall():
        yield dict(zip(c,r))


def insert(cur,sql,args):
    try:
        cur.execute(sql,args)
        return cur.rowcount>0
    except Exception:
        return False

# ---- Chunk 2 continues ----
def sync_sessions(scur,mcur):
    have=existing(mcur,"devin_sessions","id")
    sql="""
    INSERT IGNORE INTO devin_sessions
    (id,title,working_directory,backend_type,model,agent_mode,
     created_at,created_at_dt,last_activity_at,last_activity_at_dt,
     hidden,main_chain_id,shell_last_seen_index,cogs_json,
     workspace_dirs,metadata,source)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'sessions.db')
    """
    n=t=0
    for r in rows(scur,"sessions"):
        t+=1
        if r["id"] in have: continue
        have.add(r["id"])
        if insert(mcur,sql,(
            r["id"],r["title"],r["working_directory"],
            r["backend_type"],r["model"],r["agent_mode"],
            r["created_at"],utc(r["created_at"]),
            r["last_activity_at"],utc(r["last_activity_at"]),
            r["hidden"],r["main_chain_id"],
            r["shell_last_seen_index"],
            jdump(r["cogs_json"]),
            jdump(r["workspace_dirs"]),
            jdump(r["metadata"])
        )): n+=1
    print(f"sessions: {n} new / {t} total")


def sync_messages(scur,mcur):

    have_msg=existing(mcur,"devin_messages","message_id")
    have_row=existing(mcur,"devin_messages","row_id")

    sql="""
    INSERT IGNORE INTO devin_messages
    (session_id,node_id,parent_node_id,message_id,
     role,content,created_at,created_at_dt,
     metadata,source)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'sessions.db')
    """

    n=t=0

    for r in rows(scur,"message_nodes"):

        t+=1

        role,content,msgid=parse_chat(r.get("chat_message"))

        if msgid:
            if msgid in have_msg:
                continue
            have_msg.add(msgid)
        else:
            rid=r.get("row_id")
            if rid in have_row:
                continue
            have_row.add(rid)

        if insert(mcur,sql,(
            r.get("session_id"),
            r.get("node_id"),
            r.get("parent_node_id"),
            msgid,
            role,
            content,
            r.get("created_at"),
            utc(r.get("created_at")),
            jdump(r.get("metadata"))
        )):
            n+=1

    print(f"messages: {n} new / {t} total")


def sync_rendered_commits(scur,mcur):

    have=existing_pair(
        mcur,
        "devin_rendered_commits",
        "session_id",
        "sequence_number"
    )

    sql="""
    INSERT IGNORE INTO devin_rendered_commits
    (session_id,sequence_number,rendered_html,
     created_at,created_at_dt)
    VALUES (%s,%s,%s,%s,%s)
    """

    n=t=0

    for r in rows(scur,"rendered_commits"):

        t+=1

        k=(r.get("session_id"),
           r.get("sequence_number"))

        if k in have:
            continue

        have.add(k)

        if insert(mcur,sql,(
            r.get("session_id"),
            r.get("sequence_number"),
            r.get("rendered_html",""),
            r.get("created_at"),
            utc(r.get("created_at"))
        )):
            n+=1

    print(f"rendered_commits: {n} new / {t} total")


def sync_tool_calls(scur,mcur):

    try:
        data=list(rows(scur,"tool_call_state"))
    except sqlite3.DatabaseError:
        print("tool_calls: table missing")
        return

    have=existing(mcur,"devin_tool_calls","tool_call_id")

    sql="""
    INSERT IGNORE INTO devin_tool_calls
    (session_id,tool_call_id,
     tool_call_json,
     tool_call_update_json)
    VALUES (%s,%s,%s,%s)
    """

    n=t=0

    for r in data:

        t+=1

        tid=r.get("tool_call_id")

        if tid and tid in have:
            continue

        if tid:
            have.add(tid)

        if insert(mcur,sql,(
            r.get("session_id"),
            tid,
            jdump(r.get("tool_call_json")),
            jdump(r.get("tool_call_update_json"))
        )):
            n+=1

    print(f"tool_calls: {n} new / {t} total")

# ---- Chunk 3 continues ----
def sync_files(cur,folder,table,filecol,contentcol,extra=()):
    if not os.path.isdir(folder):
        return

    have=existing(cur,table,filecol)
    ext=".json" if table.endswith("transcripts") else ".md"
    files=glob.glob(os.path.join(folder,f"*{ext}"))
    n=0

    for path in files:

        name=os.path.basename(path)

        if name in have:
            continue

        have.add(name)

        try:
            with open(path,"r",encoding="utf-8",errors="replace") as f:
                txt=f.read()
        except Exception:
            continue

        if table=="devin_transcripts":
            insert(
                cur,
                """
                INSERT IGNORE INTO devin_transcripts
                (session_id,transcript_file,raw_json,imported_at)
                VALUES(%s,%s,%s,%s)
                """,
                (
                    name.removesuffix(".json"),
                    name,
                    txt,
                    datetime.now()
                )
            )
        else:
            insert(
                cur,
                """
                INSERT IGNORE INTO devin_summaries
                (summary_file,content,file_size,imported_at)
                VALUES(%s,%s,%s,%s)
                """,
                (
                    name,
                    txt,
                    len(txt),
                    datetime.now()
                )
            )

        n+=1

    print(f"{table}: {n} new / {len(files)} total")


def run_sync():

    print("="*70)
    print("Devin Sync Safe",
          datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*70)

    sdb=None
    mdb=None

    try:

        sdb=recover_sqlite()
        if not sdb:
            return False

        scur=sdb.cursor()

        mdb=mysql_conn()
        mcur=mdb.cursor()

        sync_sessions(scur,mcur)
        sync_messages(scur,mcur)
        sync_tool_calls(scur,mcur)
        sync_rendered_commits(scur,mcur)

        sync_files(
            mcur,
            TRANSCRIPTS_DIR,
            "devin_transcripts",
            "transcript_file",
            "raw_json"
        )

        sync_files(
            mcur,
            SUMMARIES_DIR,
            "devin_summaries",
            "summary_file",
            "content"
        )

        print("SYNC COMPLETE")
        return True

    except Exception as e:
        print("ERROR:",e)
        return False

    finally:

        try:
            if sdb:
                sdb.close()
        except:
            pass

        try:
            if mdb:
                mdb.close()
        except:
            pass

        cleanup()


def show_status():

    db=mysql_conn()
    cur=db.cursor()

    tables=[
        "devin_sessions",
        "devin_messages",
        "devin_tool_calls",
        "devin_rendered_commits",
        "devin_transcripts",
        "devin_summaries",
        "devin_chat_turns"
    ]

    print("="*50)

    for t in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            print(f"{t:28}{cur.fetchone()[0]:>12,}")
        except Exception as e:
            print(f"{t:28}ERROR ({e})")

    db.close()


def watch():

    print(f"Watching every {POLL}s...")

    while True:

        try:
            run_sync()
            time.sleep(POLL)

        except KeyboardInterrupt:
            print("Stopped")
            break

        except Exception as e:
            print(e)
            time.sleep(POLL)


def main():

    if "--status" in sys.argv:
        show_status()

    elif "--watch" in sys.argv:
        watch()

    else:
        run_sync()


if __name__=="__main__":
    main()
