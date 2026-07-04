#!/usr/bin/env python3
"""Fix Config.py using DB - remove graph tables from SCHEMA_SQL, restore class definition."""
import sqlite3
from pathlib import Path

BASE_DIR = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph")
DB_PATH = BASE_DIR / "dom_graph_ingest.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Get all lines from Config.py
cur.execute("SELECT lineno, text FROM source_lines WHERE file = 'Config.py' ORDER BY lineno")
lines = [(row[0], row[1]) for row in cur.fetchall()]

# Build new content: keep lines 1-808 (before graph tables were inserted), skip 750-1003 (graph tables inside SCHEMA_SQL), add graph schema as separate constant, then add class definition
new_lines = []
skip_graph_tables = False
schema_closed = False

for lineno, text in lines:
    # Skip graph tables that were incorrectly inserted inside SCHEMA_SQL (lines 750-1003)
    if lineno == 750 and "CREATE TABLE IF NOT EXISTS graph_categories" in text:
        skip_graph_tables = True
        continue
    if skip_graph_tables and lineno == 1003 and text.strip() == '"""':
        skip_graph_tables = False
        # Close SCHEMA_SQL properly (it should have closed at line 808)
        if not schema_closed:
            new_lines.append((808, '"""'))
            schema_closed = True
        continue
    if skip_graph_tables:
        continue

    # At line 808, close SCHEMA_SQL properly
    if lineno == 808 and text.strip() == '"""':
        new_lines.append((lineno, text))
        schema_closed = True
        # Add graph schema as separate constant
        new_lines.append((809, ""))
        new_lines.append((810, "# Graph schema tables (executed after SCHEMA_SQL)"))
        new_lines.append((811, "GRAPH_SCHEMA = \"\"\""))
        new_lines.append((812, "CREATE TABLE IF NOT EXISTS graph_categories ("))
        new_lines.append((813, "    name        TEXT PRIMARY KEY,"))
        new_lines.append((814, "    color       TEXT NOT NULL,"))
        new_lines.append((815, "    sort_order  INTEGER NOT NULL"))
        new_lines.append((816, ");"))
        new_lines.append((817, "CREATE TABLE IF NOT EXISTS graph_classes ("))
        new_lines.append((818, "    name            TEXT PRIMARY KEY,"))
        new_lines.append((819, "    category        TEXT NOT NULL,"))
        new_lines.append((820, "    dispatch_key    TEXT NOT NULL,"))
        new_lines.append((821, "    description     TEXT NOT NULL,"))
        new_lines.append((822, "    FOREIGN KEY (category) REFERENCES graph_categories(name)"))
        new_lines.append((823, ");"))
        new_lines.append((824, "CREATE TABLE IF NOT EXISTS graph_edges ("))
        new_lines.append((825, "    id          INTEGER PRIMARY KEY AUTOINCREMENT,"))
        new_lines.append((826, "    src         TEXT NOT NULL,"))
        new_lines.append((827, "    dst         TEXT NOT NULL,"))
        new_lines.append((828, "    edge_type   TEXT NOT NULL,"))
        new_lines.append((829, "    FOREIGN KEY (src) REFERENCES graph_classes(name),"))
        new_lines.append((830, "    FOREIGN KEY (dst) REFERENCES graph_classes(name)"))
        new_lines.append((831, ");"))
        new_lines.append((832, "CREATE INDEX IF NOT EXISTS idx_ge_src ON graph_edges(src);"))
        new_lines.append((833, "CREATE INDEX IF NOT EXISTS idx_ge_dst ON graph_edges(dst);"))
        new_lines.append((834, "CREATE INDEX IF NOT EXISTS idx_ge_type ON graph_edges(edge_type);"))
        new_lines.append((835, "CREATE TABLE IF NOT EXISTS graph_edge_colors ("))
        new_lines.append((836, "    edge_type   TEXT PRIMARY KEY,"))
        new_lines.append((837, "    color       TEXT NOT NULL"))
        new_lines.append((838, ");"))
        new_lines.append((839, "CREATE TABLE IF NOT EXISTS graph_flows ("))
        new_lines.append((840, "    id          INTEGER PRIMARY KEY AUTOINCREMENT,"))
        new_lines.append((841, "    class_name  TEXT NOT NULL,"))
        new_lines.append((842, "    step_order  INTEGER NOT NULL,"))
        new_lines.append((843, "    step_type   TEXT NOT NULL,"))
        new_lines.append((844, "    step_text   TEXT NOT NULL,"))
        new_lines.append((845, "    FOREIGN KEY (class_name) REFERENCES graph_classes(name)"))
        new_lines.append((846, ");"))
        new_lines.append((847, "CREATE INDEX IF NOT EXISTS idx_gf_class ON graph_flows(class_name);"))
        new_lines.append((848, "CREATE INDEX IF NOT EXISTS idx_gf_type ON graph_flows(step_type);"))
        new_lines.append((849, "CREATE TABLE IF NOT EXISTS graph_flow_colors ("))
        new_lines.append((850, "    step_type   TEXT PRIMARY KEY,"))
        new_lines.append((851, "    color       TEXT NOT NULL"))
        new_lines.append((852, ");"))
        new_lines.append((853, "CREATE TABLE IF NOT EXISTS graph_lifecycle_phases ("))
        new_lines.append((854, "    name        TEXT PRIMARY KEY,"))
        new_lines.append((855, "    color       TEXT NOT NULL,"))
        new_lines.append((856, "    description TEXT NOT NULL"))
        new_lines.append((857, ");"))
        new_lines.append((858, "CREATE TABLE IF NOT EXISTS graph_class_phase ("))
        new_lines.append((859, "    class_name  TEXT PRIMARY KEY,"))
        new_lines.append((860, "    phase       TEXT NOT NULL,"))
        new_lines.append((861, "    FOREIGN KEY (class_name) REFERENCES graph_classes(name),"))
        new_lines.append((862, "    FOREIGN KEY (phase) REFERENCES graph_lifecycle_phases(name)"))
        new_lines.append((863, ");"))
        new_lines.append((864, "CREATE TABLE IF NOT EXISTS graph_operation_verbs ("))
        new_lines.append((865, "    verb        TEXT PRIMARY KEY,"))
        new_lines.append((866, "    category    TEXT NOT NULL"))
        new_lines.append((867, ");"))
        new_lines.append((868, "CREATE INDEX IF NOT EXISTS idx_gov_cat ON graph_operation_verbs(category);"))
        new_lines.append((869, '"""'))
        new_lines.append((870, ""))
        new_lines.append((871, ""))
        new_lines.append((872, "class Config:"))
        new_lines.append((873, '    """Authority for Dom_Graph domain configuration. Schema embedded, DB on-demand."""'))
        continue

    # Add class definition before def __init__ if missing
    if lineno == 1005 and "def __init__" in text:
        if not any("class Config:" in t for _, t in new_lines[-10:]):
            new_lines.append((872, "class Config:"))
            new_lines.append((873, '    """Authority for Dom_Graph domain configuration. Schema embedded, DB on-demand."""'))

    new_lines.append((lineno, text))

# Write to file
config_path = BASE_DIR / "Config.py"
with open(config_path, "w", encoding="utf-8") as f:
    for _, text in new_lines:
        f.write(text + "\n")

print(f"Config.py fixed: {len(new_lines)} lines written")
conn.close()
