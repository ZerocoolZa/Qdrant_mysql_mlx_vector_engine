#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Script creates DB tables for Config constants and class registry, then populates them. NO VBStyle headers. print() x5. No Run() dispatch, no class, no Tuple3 returns. Hardcoded /Users/wws/ path. Uses cfg._Get() (self._ violation). Not VBStyle compliant -- utility script.>][@todos<1. Add VBStyle identity headers. 2. Remove print() calls. 3. Wrap in a class with Run() dispatch and Tuple3 returns. 4. Remove hardcoded /Users/wws/ path. 5. Fix cfg._Get() self._ violation.>]}
"""Create DB tables for Config constants and class registry, then populate them."""
import sqlite3
from pathlib import Path
import sys

BASE_DIR = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph")
DB_PATH = BASE_DIR / "dom_graph_work.db"

sys.path.insert(0, str(BASE_DIR))
from Config import Config

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Create tables
cur.execute("DROP TABLE IF EXISTS config_constants")
cur.execute("DROP TABLE IF EXISTS class_registry")
cur.execute("DROP TABLE IF EXISTS method_registry")

cur.execute("""
CREATE TABLE config_constants (
    name TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    type TEXT NOT NULL,
    description TEXT
)
""")

cur.execute("""
CREATE TABLE class_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file TEXT NOT NULL,
    class_name TEXT NOT NULL,
    lineno INTEGER NOT NULL,
    class_text TEXT NOT NULL,
    method_count INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE method_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    method_name TEXT NOT NULL,
    lineno INTEGER NOT NULL,
    method_text TEXT NOT NULL,
    FOREIGN KEY (class_id) REFERENCES class_registry(id)
)
""")

# Insert Config constants
cfg = Config()
constants_to_store = [
    ("BASE_DIR", str(cfg._Get({"key": "base_dir"})[1]), "path", "Base directory path"),
    ("SOURCE_PATH", cfg._Get({"key": "source_path"})[1], "path", "MacServer.c source path"),
    ("POPULATOR_PATH", cfg._Get({"key": "populator_path"})[1], "path", "RuntimeTwinPopulate.py path"),
    ("DB_MODE", cfg._Get({"key": "db_mode"})[1], "string", "Database mode (memory/file)"),
    ("CODECS", str(cfg._Get({"key": "codecs"})[1]), "list", "Supported codecs"),
    ("DEFAULT_CODEC", cfg._Get({"key": "default_codec"})[1], "string", "Default codec"),
    ("SIM_FRAMES", str(cfg._Get({"key": "sim_frames"})[1]), "int", "Simulation frames"),
    ("SIM_SEED", str(cfg._Get({"key": "sim_seed"})[1]), "int", "Simulation seed"),
    ("TARGET_FPS", str(cfg._Get({"key": "target_fps"})[1]), "int", "Target FPS"),
    ("FRAME_INTERVAL_US", str(cfg._Get({"key": "frame_interval_us"})[1]), "int", "Frame interval microseconds"),
    ("DISPLAY_WIDTH", str(cfg._Get({"key": "display_width"})[1]), "int", "Display width"),
    ("DISPLAY_HEIGHT", str(cfg._Get({"key": "display_height"})[1]), "int", "Display height"),
    ("FRAME_BUFFER_BYTES", str(cfg._Get({"key": "frame_buffer_bytes"})[1]), "int", "Frame buffer bytes"),
    ("JPEG_QUALITY", str(cfg._Get({"key": "jpeg_quality"})[1]), "int", "JPEG quality"),
    ("JPEG_COMPRESSED_SIZE", str(cfg._Get({"key": "jpeg_compressed_size"})[1]), "int", "JPEG compressed size"),
    ("H264_COMPRESSED_SIZE", str(cfg._Get({"key": "h264_compressed_size"})[1]), "int", "H264 compressed size"),
    ("VP8_COMPRESSED_SIZE", str(cfg._Get({"key": "vp8_compressed_size"})[1]), "int", "VP8 compressed size"),
    ("CAPTURE_FAILURE_RATE", str(cfg._Get({"key": "capture_failure_rate"})[1]), "float", "Capture failure rate"),
    ("ENCODE_FAILURE_RATE", str(cfg._Get({"key": "encode_failure_rate"})[1]), "float", "Encode failure rate"),
    ("SEND_FAILURE_RATE", str(cfg._Get({"key": "send_failure_rate"})[1]), "float", "Send failure rate"),
    ("MOUSE_EVENT_PROB", str(cfg._Get({"key": "mouse_event_prob"})[1]), "float", "Mouse event probability"),
    ("KEYBOARD_EVENT_PROB", str(cfg._Get({"key": "keyboard_event_prob"})[1]), "float", "Keyboard event probability"),
    ("RECV_BUF_SIZE", str(cfg._Get({"key": "recv_buf_size"})[1]), "int", "Receive buffer size"),
    ("AUTH_TIMEOUT_SEC", str(cfg._Get({"key": "auth_timeout_sec"})[1]), "int", "Auth timeout seconds"),
    ("SERVER_PORT", str(cfg._Get({"key": "server_port"})[1]), "int", "Server port"),
    ("GRAPH_CATEGORIES", str(cfg._Get({"key": "graph_categories"})[1]), "dict", "Graph categories with colors"),
    ("GRAPH_CATEGORY_ORDER", str(cfg._Get({"key": "graph_category_order"})[1]), "list", "Graph category order"),
    ("GRAPH_EDGE_COLORS", str(cfg._Get({"key": "graph_edge_colors"})[1]), "dict", "Graph edge colors"),
    ("GRAPH_FLOW_COLORS", str(cfg._Get({"key": "graph_flow_colors"})[1]), "dict", "Graph flow colors"),
    ("GRAPH_CLASSES", str(cfg._Get({"key": "graph_classes"})[1]), "list", "Graph classes"),
    ("GRAPH_EDGES", str(cfg._Get({"key": "graph_edges"})[1]), "list", "Graph edges"),
    ("GRAPH_FLOWS", str(cfg._Get({"key": "graph_flows"})[1]), "dict", "Graph flows"),
    ("GRAPH_LIFECYCLE_PHASES", str(cfg._Get({"key": "graph_lifecycle_phases"})[1]), "list", "Graph lifecycle phases"),
    ("GRAPH_CLASS_PHASE", str(cfg._Get({"key": "graph_class_phase"})[1]), "dict", "Graph class to phase mapping"),
    ("GRAPH_PHASE_COLORS", str(cfg._Get({"key": "graph_phase_colors"})[1]), "dict", "Graph phase colors"),
    ("GRAPH_PHASE_ORDER", str(cfg._Get({"key": "graph_phase_order"})[1]), "list", "Graph phase order"),
    ("GRAPH_OPERATION_VERBS", str(cfg._Get({"key": "graph_operation_verbs"})[1]), "list", "Graph operation verbs"),
    ("GRAPH_VERB_CATEGORY", str(cfg._Get({"key": "graph_verb_category"})[1]), "dict", "Graph verb to category mapping"),
    ("FILE_REGISTRY", str(cfg._Get({"key": "file_registry"})[1]), "dict", "File registry"),
    ("GRAPH_PIPELINE", str(cfg._Get({"key": "graph_pipeline"})[1]), "list", "Graph pipeline"),
    ("PRIMITIVES", str(cfg._Get({"key": "primitives"})[1]), "list", "Primitive costs"),
    ("FUNCTION_GRAPH", str(cfg._Get({"key": "function_graph"})[1]), "dict", "Function graph"),
]

for name, value, type_, desc in constants_to_store:
    cur.execute("INSERT OR REPLACE INTO config_constants (name, value, type, description) VALUES (?, ?, ?, ?)", (name, value, type_, desc))

print(f"Inserted {len(constants_to_store)} Config constants")

# Insert class definitions from src table
cur.execute("SELECT file, lineno, text FROM src WHERE text LIKE 'class %' ORDER BY file, lineno")
classes = cur.fetchall()

for file, lineno, text in classes:
    class_name = text.split('(')[0].replace('class ', '').replace(':', '').strip()
    cur.execute("INSERT INTO class_registry (file, class_name, lineno, class_text) VALUES (?, ?, ?, ?)", (file, class_name, lineno, text))
    class_id = cur.lastrowid
    
    # Find methods for this class
    cur.execute("SELECT lineno, text FROM src WHERE file = ? AND lineno > ? AND text LIKE '    def %' ORDER BY lineno LIMIT 100", (file, lineno))
    methods = cur.fetchall()
    for meth_lineno, meth_text in methods:
        meth_name = meth_text.split('(')[0].replace('    def ', '').strip()
        cur.execute("INSERT INTO method_registry (class_id, method_name, lineno, method_text) VALUES (?, ?, ?, ?)", (class_id, meth_name, meth_lineno, meth_text))
    
    # Update method count
    cur.execute("UPDATE class_registry SET method_count = ? WHERE id = ?", (len(methods), class_id))

print(f"Inserted {len(classes)} classes with {cur.execute('SELECT COUNT(*) FROM method_registry').fetchone()[0]} methods")

conn.commit()
print(f"Config constants: {cur.execute('SELECT COUNT(*) FROM config_constants').fetchone()[0]}")
print(f"Classes: {cur.execute('SELECT COUNT(*) FROM class_registry').fetchone()[0]}")
print(f"Methods: {cur.execute('SELECT COUNT(*) FROM method_registry').fetchone()[0]}")
conn.close()
