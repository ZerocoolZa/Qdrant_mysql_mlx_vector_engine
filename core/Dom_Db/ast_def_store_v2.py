#!/usr/bin/env python3
#[@GHOST]{[@file<ast_def_store_v2.py>][@state<active>][@date<2026-07-01>][@ver<2.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<ast_def_store_v2>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}
"""
AST Definition Store v2 — Normalized schema.

v1: one flat table, 47 columns, file/class info repeated on every row.
v2: three normalized tables:

  ci_files       — one row per file (617 rows instead of 617×17)
  ci_classes     — one row per class (684 rows instead of repeated strings)
  ci_definitions — one row per function/method, FK to file_id + class_id

Migration: reads v1 /tmp/ast_definitions.sqlite, writes v2 /tmp/ast_definitions_v2.sqlite
"""

import sqlite3
import time
import os
from typing import Dict, List, Optional


V2_SCHEMA = """
CREATE TABLE IF NOT EXISTS ci_runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   REAL NOT NULL,
    root_folder TEXT NOT NULL,
    total_files INTEGER NOT NULL,
    total_classes INTEGER NOT NULL,
    total_defs INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ci_files (
    file_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL,
    file_path   TEXT NOT NULL,
    module_name TEXT NOT NULL,
    file_hash   TEXT NOT NULL,
    UNIQUE(run_id, file_path),
    FOREIGN KEY (run_id) REFERENCES ci_runs(run_id)
);

CREATE TABLE IF NOT EXISTS ci_classes (
    class_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL,
    file_id     INTEGER NOT NULL,
    name        TEXT NOT NULL,
    parent_name TEXT,
    line_start  INTEGER,
    UNIQUE(run_id, file_id, name),
    FOREIGN KEY (file_id) REFERENCES ci_files(file_id),
    FOREIGN KEY (run_id) REFERENCES ci_runs(run_id)
);

CREATE TABLE IF NOT EXISTS ci_definitions (
    def_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL,
    file_id         INTEGER NOT NULL,
    class_id        INTEGER,

    -- identity
    name            TEXT NOT NULL,
    qualname        TEXT NOT NULL,
    kind            TEXT NOT NULL,
    line_start      INTEGER NOT NULL,
    line_end        INTEGER NOT NULL,
    col_offset      INTEGER NOT NULL,
    end_col_offset  INTEGER NOT NULL,

    -- structure
    is_method       INTEGER NOT NULL DEFAULT 0,
    is_nested       INTEGER NOT NULL DEFAULT 0,
    decorator_count INTEGER NOT NULL DEFAULT 0,
    decorator_names TEXT,

    -- signature
    arg_count       INTEGER NOT NULL DEFAULT 0,
    arg_names       TEXT,
    has_vararg      INTEGER NOT NULL DEFAULT 0,
    has_kwarg       INTEGER NOT NULL DEFAULT 0,
    has_defaults    INTEGER NOT NULL DEFAULT 0,
    returns_annotation TEXT,

    -- body
    body_lines      INTEGER NOT NULL DEFAULT 0,
    docstring       TEXT,
    has_docstring   INTEGER NOT NULL DEFAULT 0,

    -- complexity
    cyclomatic      INTEGER NOT NULL DEFAULT 0,
    branches        INTEGER NOT NULL DEFAULT 0,
    loops           INTEGER NOT NULL DEFAULT 0,
    ifs             INTEGER NOT NULL DEFAULT 0,
    tries           INTEGER NOT NULL DEFAULT 0,
    withs           INTEGER NOT NULL DEFAULT 0,
    max_nesting     INTEGER NOT NULL DEFAULT 0,

    -- calls
    call_count      INTEGER NOT NULL DEFAULT 0,
    call_names      TEXT,
    recursive       INTEGER NOT NULL DEFAULT 0,

    -- variables
    assign_count    INTEGER NOT NULL DEFAULT 0,
    local_vars      TEXT,
    imports_used    TEXT,

    -- dead code
    is_empty        INTEGER NOT NULL DEFAULT 0,
    is_pass_only    INTEGER NOT NULL DEFAULT 0,
    unused_imports  TEXT,

    -- scoring
    score           INTEGER NOT NULL DEFAULT 0,
    grade           TEXT NOT NULL,
    issues          TEXT,
    suggestions     TEXT,

    source_code     TEXT,
    ast_hash        TEXT,

    timestamp       REAL NOT NULL,

    FOREIGN KEY (file_id) REFERENCES ci_files(file_id),
    FOREIGN KEY (class_id) REFERENCES ci_classes(class_id),
    FOREIGN KEY (run_id) REFERENCES ci_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_def_run ON ci_definitions(run_id);
CREATE INDEX IF NOT EXISTS idx_def_name ON ci_definitions(name);
CREATE INDEX IF NOT EXISTS idx_def_qualname ON ci_definitions(qualname);
CREATE INDEX IF NOT EXISTS idx_def_file ON ci_definitions(file_id);
CREATE INDEX IF NOT EXISTS idx_def_class ON ci_definitions(class_id);
CREATE INDEX IF NOT EXISTS idx_def_kind ON ci_definitions(kind);
CREATE INDEX IF NOT EXISTS idx_def_complexity ON ci_definitions(cyclomatic);
CREATE INDEX IF NOT EXISTS idx_def_score ON ci_definitions(score);
CREATE INDEX IF NOT EXISTS idx_def_grade ON ci_definitions(grade);
CREATE INDEX IF NOT EXISTS idx_files_path ON ci_files(file_path);
CREATE INDEX IF NOT EXISTS idx_classes_name ON ci_classes(name);
"""


def migrate(v1_path: str = "/tmp/ast_definitions.sqlite",
            v2_path: str = "/tmp/ast_definitions_v2.sqlite"):
    """Migrate v1 flat table → v2 normalized tables."""

    if os.path.exists(v2_path):
        os.remove(v2_path)

    src = sqlite3.connect(v1_path)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(v2_path)
    dst.executescript(V2_SCHEMA)
    dst.commit()

    # Get v1 run info
    s = src.cursor()
    s.execute("SELECT * FROM ci_def_runs ORDER BY run_id DESC LIMIT 1")
    run_row = s.fetchone()
    if not run_row:
        print("No runs in v1 DB")
        return

    run_id_old = run_row["run_id"]
    root_folder = run_row["root_folder"]

    # Create v2 run
    d = dst.cursor()
    d.execute(
        "INSERT INTO ci_runs (timestamp, root_folder, total_files, total_classes, total_defs) "
        "VALUES (?, ?, 0, 0, 0)",
        (time.time(), root_folder)
    )
    run_id = d.lastrowid

    # Load all v1 definitions
    s.execute("SELECT * FROM ci_definitions WHERE run_id = ? ORDER BY file_path, line_start", (run_id_old,))
    all_defs = s.fetchall()

    # Build file lookup
    file_cache: Dict[str, int] = {}
    class_cache: Dict[str, int] = {}

    total_defs = 0
    total_classes = 0

    for row in all_defs:
        fpath = row["file_path"]
        mod = row["module_name"]
        fhash = row["file_hash"]

        # Insert file if not seen
        if fpath not in file_cache:
            d.execute(
                "INSERT OR IGNORE INTO ci_files (run_id, file_path, module_name, file_hash) "
                "VALUES (?, ?, ?, ?)",
                (run_id, fpath, mod, fhash)
            )
            d.execute(
                "SELECT file_id FROM ci_files WHERE run_id = ? AND file_path = ?",
                (run_id, fpath)
            )
            file_cache[fpath] = d.fetchone()[0]

        file_id = file_cache[fpath]

        # Insert class if this is a method
        class_id = None
        if row["class_name"]:
            class_key = fpath + ":" + row["class_name"]
            if class_key not in class_cache:
                d.execute(
                    "INSERT OR IGNORE INTO ci_classes (run_id, file_id, name, parent_name, line_start) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (run_id, file_id, row["class_name"], row["parent_name"], row["line_start"])
                )
                d.execute(
                    "SELECT class_id FROM ci_classes WHERE run_id = ? AND file_id = ? AND name = ?",
                    (run_id, file_id, row["class_name"])
                )
                class_cache[class_key] = d.fetchone()[0]
                total_classes += 1
            class_id = class_cache[class_key]

        # Insert definition
        d.execute(
            "INSERT INTO ci_definitions "
            "(run_id, file_id, class_id, name, qualname, kind, "
            "line_start, line_end, col_offset, end_col_offset, "
            "is_method, is_nested, decorator_count, decorator_names, "
            "arg_count, arg_names, has_vararg, has_kwarg, has_defaults, returns_annotation, "
            "body_lines, docstring, has_docstring, "
            "cyclomatic, branches, loops, ifs, tries, withs, max_nesting, "
            "call_count, call_names, recursive, "
            "assign_count, local_vars, imports_used, "
            "is_empty, is_pass_only, unused_imports, "
            "score, grade, issues, suggestions, "
            "source_code, ast_hash, timestamp) "
            "VALUES (" + ",".join(["?"] * 46) + ")",
            (run_id, file_id, class_id, row["name"], row["qualname"], row["kind"],
             row["line_start"], row["line_end"], row["col_offset"], row["end_col_offset"],
             row["is_method"], row["is_nested"], row["decorator_count"], row["decorator_names"],
             row["arg_count"], row["arg_names"], row["has_vararg"], row["has_kwarg"],
             row["has_defaults"], row["returns_annotation"],
             row["body_lines"], row["docstring"], row["has_docstring"],
             row["cyclomatic"], row["branches"], row["loops"], row["ifs"],
             row["tries"], row["withs"], row["max_nesting"],
             row["call_count"], row["call_names"], row["recursive"],
             row["assign_count"], row["local_vars"], row["imports_used"],
             row["is_empty"], row["is_pass_only"], row["unused_imports"],
             row["score"], row["grade"], row["issues"], row["suggestions"],
             row["source_code"], row["ast_hash"], row["timestamp"])
        )
        total_defs += 1

    # Update run stats
    d.execute(
        "UPDATE ci_runs SET total_files = ?, total_classes = ?, total_defs = ? WHERE run_id = ?",
        (len(file_cache), total_classes, total_defs, run_id)
    )

    dst.commit()

    # Verify
    print("=== V2 MIGRATION COMPLETE ===")
    print(f"  Run ID:       {run_id}")
    print(f"  Files:        {len(file_cache)}")
    print(f"  Classes:      {total_classes}")
    print(f"  Definitions:  {total_defs}")

    d.execute("SELECT COUNT(*) FROM ci_definitions WHERE run_id = ?", (run_id,))
    print(f"  Verify defs:  {d.fetchone()[0]}")
    d.execute("SELECT COUNT(*) FROM ci_files WHERE run_id = ?", (run_id,))
    print(f"  Verify files: {d.fetchone()[0]}")
    d.execute("SELECT COUNT(*) FROM ci_classes WHERE run_id = ?", (run_id,))
    print(f"  Verify cls:   {d.fetchone()[0]}")

    # Dup check
    d.execute("""SELECT name, file_id, line_start, COUNT(*) cnt 
                 FROM ci_definitions WHERE run_id = ? 
                 GROUP BY name, file_id, line_start HAVING cnt > 1 LIMIT 5""", (run_id,))
    dups = d.fetchall()
    print(f"  Duplicates:   {len(dups)}")

    # Size comparison
    v1_size = os.path.getsize(v1_path)
    v2_size = os.path.getsize(v2_path)
    print(f"\n  v1 size: {v1_size:,} bytes")
    print(f"  v2 size: {v2_size:,} bytes")
    print(f"  Savings: {v1_size - v2_size:,} bytes ({(1 - v2_size/v1_size)*100:.1f}% smaller)")

    src.close()
    dst.close()


if __name__ == "__main__":
    migrate()
