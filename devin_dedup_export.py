#!/usr/bin/env python3
"""
Devin Chat Deduplication Export Tool
=====================================
Exports devin + CHAT_DEVIN MySQL databases into a single deduplicated SQLite file.
Triple-verifies nothing is missing. One script, one result.

Tables handled:
  - devin_messages (dedup by session_id + node_id)
  - devin_sessions (dedup by id)
  - devin_chat_turns (dedup by session_id + turn_seq)
  - devin_rendered_commits (dedup by session_id + sequence_number)
  - devin_summaries (dedup by summary_file)
  - devin_transcripts (dedup by session_id + transcript_file)
  - devin_tool_calls (dedup by session_id + tool_call_id)
  - devin_prompt_history (dedup by prompt_text hash)
  - devin_commands (full copy)
  - devin_import_log (full copy)
"""

import sqlite3
import mysql.connector
import hashlib
import os
import sys
from datetime import datetime

SQLITE_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/devin_clean.sqlite"
MYSQL_CONFIG = dict(host="localhost", user="root", password="", autocommit=True)

TABLES = [
    "devin_messages",
    "devin_sessions",
    "devin_chat_turns",
    "devin_rendered_commits",
    "devin_summaries",
    "devin_transcripts",
    "devin_tool_calls",
    "devin_prompt_history",
    "devin_commands",
    "devin_import_log",
]

DEDUP_KEYS = {
    "devin_messages": ("session_id", "node_id"),
    "devin_sessions": ("id",),
    "devin_chat_turns": ("session_id", "turn_seq"),
    "devin_rendered_commits": ("session_id", "sequence_number"),
    "devin_summaries": ("summary_file",),
    "devin_transcripts": ("session_id", "transcript_file"),
    "devin_tool_calls": ("session_id", "tool_call_id"),
    "devin_prompt_history": None,  # dedup by content hash
    "devin_commands": None,  # full copy, no dedup
    "devin_import_log": None,  # full copy, no dedup
}


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def get_mysql_conn(db_name):
    cfg = dict(MYSQL_CONFIG)
    cfg["database"] = db_name
    return mysql.connector.connect(**cfg)


def get_table_columns(conn, table):
    cur = conn.cursor()
    cur.execute(f"SHOW COLUMNS FROM {table}")
    return [row[0] for row in cur.fetchall()]


def create_sqlite_schema(sqlite_conn, table_columns):
    cur = sqlite_conn.cursor()
    for table, cols in table_columns.items():
        col_defs = ", ".join([f'"{c}" TEXT' for c in cols])
        cur.execute(f'DROP TABLE IF EXISTS "{table}"')
        cur.execute(f'CREATE TABLE "{table}" ({col_defs})')
        dedup = DEDUP_KEYS.get(table)
        if dedup:
            idx_cols = ", ".join([f'"{c}"' for c in dedup])
            cur.execute(f'CREATE UNIQUE INDEX "uq_{table}" ON "{table}" ({idx_cols})')
    sqlite_conn.commit()


def export_table(mysql_conn, sqlite_conn, table, columns, source_db):
    cur = mysql_conn.cursor(dictionary=True)
    sqlite_cur = sqlite_conn.cursor()

    placeholders = ", ".join(["?"] * len(columns))
    col_names = ", ".join([f'"{c}"' for c in columns])
    insert_sql = f'INSERT OR IGNORE INTO "{table}" ({col_names}) VALUES ({placeholders})'

    cur.execute(f"SELECT {', '.join(columns)} FROM {table}")
    batch = []
    batch_size = 500
    total = 0

    while True:
        rows = cur.fetchmany(batch_size)
        if not rows:
            break
        for row in rows:
            values = []
            for c in columns:
                v = row[c]
                if isinstance(v, (dict, list)):
                    import json
                    v = json.dumps(v)
                elif v is not None and not isinstance(v, (str, int, float, bytes)):
                    v = str(v)
                values.append(v)
            batch.append(values)
        sqlite_cur.executemany(insert_sql, batch)
        sqlite_conn.commit()
        total += len(batch)
        batch = []

    cur.close()
    log(f"  {source_db}.{table}: {total} rows exported")
    return total


def verify_counts(mysql_conn, sqlite_conn, table, columns):
    mysql_cur = mysql_conn.cursor()
    sqlite_cur = sqlite_conn.cursor()

    # Count in devin
    mysql_cur.execute(f"SELECT COUNT(*) FROM devin.{table}")
    devin_count = mysql_cur.fetchone()[0]

    # Count in CHAT_DEVIN (may not exist for some tables)
    try:
        mysql_cur.execute(f"SELECT COUNT(*) FROM CHAT_DEVIN.{table}")
        chatdevin_count = mysql_cur.fetchone()[0]
    except Exception:
        chatdevin_count = 0

    # Combined distinct count using UNION
    dedup = DEDUP_KEYS.get(table)
    if dedup:
        dedup_cols = ", ".join(dedup)
        null_check = " AND ".join([f"{c} IS NOT NULL" for c in dedup])
        # Count distinct non-NULL keys across both databases
        mysql_cur.execute(
            f"SELECT COUNT(*) FROM ("
            f"SELECT {dedup_cols} FROM devin.{table} WHERE {null_check} "
            f"UNION "
            f"SELECT {dedup_cols} FROM CHAT_DEVIN.{table} WHERE {null_check}"
            f") t"
        )
        distinct_non_null = mysql_cur.fetchone()[0]

        # Count rows with NULL in any dedup key (these are NOT deduped by SQLite unique index)
        null_cond = " OR ".join([f"{c} IS NULL" for c in dedup])
        mysql_cur.execute(f"SELECT COUNT(*) FROM devin.{table} WHERE {null_cond}")
        devin_null_rows = mysql_cur.fetchone()[0]
        try:
            mysql_cur.execute(f"SELECT COUNT(*) FROM CHAT_DEVIN.{table} WHERE {null_cond}")
            chatdevin_null_rows = mysql_cur.fetchone()[0]
        except Exception:
            chatdevin_null_rows = 0

        combined_distinct = distinct_non_null + devin_null_rows + chatdevin_null_rows
    else:
        combined_distinct = devin_count + chatdevin_count

    sqlite_cur.execute(f'SELECT COUNT(*) FROM "{table}"')
    sqlite_count = sqlite_cur.fetchone()[0]

    status = "OK" if sqlite_count == combined_distinct else "MISMATCH"
    log(f"  VERIFY {table}: devin={devin_count} chatdevin={chatdevin_count} combined_distinct={combined_distinct} sqlite={sqlite_count} [{status}]")
    return status == "OK"


def verify_sessions(mysql_conn, sqlite_conn):
    mysql_cur = mysql_conn.cursor()
    sqlite_cur = sqlite_conn.cursor()

    mysql_cur.execute("SELECT DISTINCT session_id FROM devin.devin_messages")
    mysql_sessions = set(r[0] for r in mysql_cur.fetchall())

    sqlite_cur.execute('SELECT DISTINCT session_id FROM "devin_messages"')
    sqlite_sessions = set(r[0] for r in sqlite_cur.fetchall())

    missing = mysql_sessions - sqlite_sessions
    extra = sqlite_sessions - mysql_sessions

    if not missing and not extra:
        log(f"  VERIFY sessions: mysql={len(mysql_sessions)} sqlite={len(sqlite_sessions)} [OK]")
        return True
    else:
        log(f"  VERIFY sessions: MISSING={len(missing)} EXTRA={len(extra)} [MISMATCH]")
        if missing:
            log(f"    Missing: {list(missing)[:5]}")
        return False


def verify_sample_messages(mysql_conn, sqlite_conn):
    mysql_cur = mysql_conn.cursor(dictionary=True)
    sqlite_cur = sqlite_conn.cursor()

    mysql_cur.execute(
        "SELECT session_id, node_id, role, LEFT(content, 200) as content_preview "
        "FROM devin.devin_messages ORDER BY row_id DESC LIMIT 50"
    )
    samples = mysql_cur.fetchall()

    matched = 0
    for s in samples:
        sqlite_cur.execute(
            'SELECT role, substr(content, 1, 200) FROM "devin_messages" '
            'WHERE session_id=? AND node_id=?',
            (s["session_id"], s["node_id"]),
        )
        row = sqlite_cur.fetchone()
        if row and row[0] == s["role"] and row[1] == s["content_preview"]:
            matched += 1

    status = "OK" if matched == len(samples) else "MISMATCH"
    log(f"  VERIFY sample messages: {matched}/{len(samples)} matched [{status}]")
    return matched == len(samples)


def main():
    if os.path.exists(SQLITE_PATH):
        os.remove(SQLITE_PATH)
        log(f"Removed existing {SQLITE_PATH}")

    log("=== DEVIN DEDUP EXPORT ===")
    log(f"Target: {SQLITE_PATH}")

    # Connect to MySQL
    mysql_conn = mysql.connector.connect(**MYSQL_CONFIG)
    log("Connected to MySQL")

    # Discover columns for each table from devin (the superset)
    table_columns = {}
    for table in TABLES:
        cols = get_table_columns(mysql_conn, f"devin.{table}")
        table_columns[table] = cols
        log(f"  Schema: devin.{table} -> {len(cols)} columns")

    # Create SQLite schema
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    create_sqlite_schema(sqlite_conn, table_columns)
    log("SQLite schema created")

    # Phase 1: Export from devin (the superset)
    log("=== PHASE 1: Export devin (superset) ===")
    devin_counts = {}
    for table in TABLES:
        conn = get_mysql_conn("devin")
        count = export_table(conn, sqlite_conn, table, table_columns[table], "devin")
        devin_counts[table] = count
        conn.close()

    # Phase 2: Export from CHAT_DEVIN (INSERT OR IGNORE = skip dups)
    log("=== PHASE 2: Export CHAT_DEVIN (merge, skip dups) ===")
    chatdevin_counts = {}
    for table in TABLES:
        try:
            conn = get_mysql_conn("CHAT_DEVIN")
            count = export_table(conn, sqlite_conn, table, table_columns[table], "CHAT_DEVIN")
            chatdevin_counts[table] = count
            conn.close()
        except Exception as e:
            log(f"  CHAT_DEVIN.{table}: SKIPPED ({e})")
            chatdevin_counts[table] = 0

    # Phase 3: Triple verification
    log("=== PHASE 3: TRIPLE VERIFICATION ===")

    # Verify 1: Row counts
    log("--- Verify 1: Row counts ---")
    all_ok = True
    for table in TABLES:
        ok = verify_counts(mysql_conn, sqlite_conn, table, table_columns[table])
        if not ok:
            all_ok = False

    # Verify 2: Session coverage
    log("--- Verify 2: Session coverage ---")
    if not verify_sessions(mysql_conn, sqlite_conn):
        all_ok = False

    # Verify 3: Sample message integrity
    log("--- Verify 3: Sample message integrity ---")
    if not verify_sample_messages(mysql_conn, sqlite_conn):
        all_ok = False

    # Summary
    log("=== SUMMARY ===")
    total_devin = sum(devin_counts.values())
    total_chatdevin = sum(chatdevin_counts.values())
    sqlite_cur = sqlite_conn.cursor()
    sqlite_cur.execute('SELECT COUNT(*) FROM "devin_messages"')
    final_msgs = sqlite_cur.fetchone()[0]
    sqlite_cur.execute('SELECT COUNT(DISTINCT session_id) FROM "devin_messages"')
    final_sessions = sqlite_cur.fetchone()[0]

    log(f"devin exported: {total_devin} rows across {len(TABLES)} tables")
    log(f"CHAT_DEVIN exported: {total_chatdevin} rows (deduped via INSERT OR IGNORE)")
    log(f"SQLite final: {final_sessions} sessions, {final_msgs} messages")
    log(f"SQLite file size: {os.path.getsize(SQLITE_PATH) / 1024 / 1024:.1f} MB")

    if all_ok:
        log("=== ALL VERIFICATIONS PASSED ===")
        log("Safe to drop CHAT_DEVIN from MySQL. devin is the canonical source.")
    else:
        log("=== VERIFICATION FAILED — DO NOT DROP ANYTHING ===")

    sqlite_conn.close()
    mysql_conn.close()
    log("Done.")


if __name__ == "__main__":
    main()
