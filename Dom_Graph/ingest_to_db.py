#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Script ingests all .py files into SQLite src table. NO VBStyle headers. print() x2. No Run() dispatch, no class, no Tuple3 returns. Hardcoded /Users/wws/ path. Not VBStyle compliant -- utility script.>][@todos<1. Add VBStyle identity headers. 2. Remove print() calls. 3. Wrap in a class with Run() dispatch and Tuple3 returns. 4. Remove hardcoded /Users/wws/ path.>]}
"""Ingest all .py files in Dom_Graph into SQLite database."""
import sqlite3
from pathlib import Path

BASE_DIR = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph")
DB_PATH = BASE_DIR / "dom_graph_work.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS src")
cur.execute("CREATE TABLE src (file TEXT, lineno INTEGER, text TEXT)")

for path in sorted(BASE_DIR.glob("*.py")):
    short = path.name
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            cur.execute("INSERT INTO src VALUES (?, ?, ?)", (short, i, line.rstrip("\n")))

conn.commit()
print(f"Ingested {cur.execute('SELECT COUNT(*) FROM src').fetchone()[0]} lines from {cur.execute('SELECT COUNT(DISTINCT file) FROM src').fetchone()[0]} files")
print(f"DB: {DB_PATH}")
conn.close()
