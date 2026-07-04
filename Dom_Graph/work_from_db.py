#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<One-shot script: ingests .py files extracts shared graph data generates new Config.py and patched graph files. NOT VBStyle: no VBStyle headers no class no Run() dispatch no Tuple3 returns. Has 8 print() calls. Hardcoded path (/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph). Procedural script with no class structure.>][@todos<1. Add VBStyle headers. 2. Remove print() calls. 3. Remove hardcoded paths. 4. Wrap in class with Run() dispatch and Tuple3 returns.>]}
"""ONE-SHOT: Ingest all .py files, extract shared graph data, generate new Config.py and patched graph files, write all at once."""
import sqlite3
from pathlib import Path

BASE_DIR = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph")
DB_PATH = BASE_DIR / "dom_graph_work.db"

# Step 1: Ingest all .py files
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

# Step 2: Extract graph constants from existing files (before they were removed)
# We'll hardcode the shared data since files were already patched
GRAPH_CONSTANTS = {
    "GRAPH_CATEGORIES": """GRAPH_CATEGORIES = {
    "CRUD": "#a6e3a1", "INTEGRITY": "#f38ba8", "TRANSFORM": "#fab387",
    "SECURITY": "#cba6f7", "UTILITY": "#89b4fa", "META": "#f9e2af",
}""",
    "GRAPH_CATEGORY_ORDER": 'GRAPH_CATEGORY_ORDER = ["CRUD", "INTEGRITY", "TRANSFORM", "SECURITY", "UTILITY", "META"]',
    "GRAPH_EDGE_COLORS": """GRAPH_EDGE_COLORS = {
    "FEEDS": "#a6e3a1", "PAIRS": "#f9e2af", "TRIGGERS": "#f38ba8",
    "FALLBACK": "#fab387", "USES": "#89b4fa", "ENABLES": "#cba6f7",
    "ALTERNATIVE": "#94e2d5", "WRAPS": "#89dceb", "MEASURES": "#f9e2af",
}""",
    "GRAPH_FLOW_COLORS": """GRAPH_FLOW_COLORS = {
    "io": "#89b4fa", "step": "#a6e3a1", "decision": "#f9e2af",
    "error": "#f38ba8", "call": "#cba6f7", "return": "#94e2d5",
}""",
    "GRAPH_CLASSES": """GRAPH_CLASSES = [
    ("Compress", "CRUD", "compress", "Create archives from files/dirs"),
    ("Extract", "CRUD", "extract", "Pull files out to disk"),
    ("Read", "CRUD", "read", "Read inside without extracting"),
    ("Write", "CRUD", "write", "Add files to archives"),
    ("Info", "META", "info", "Metadata about archives"),
    ("List", "META", "list", "List with filtering/sorting"),
    ("Search", "UTILITY", "search", "Search text inside archives"),
    ("Stream", "UTILITY", "stream", "Stream in chunks (low RAM)"),
    ("Convert", "TRANSFORM", "convert", "Convert between formats"),
    ("Verify", "INTEGRITY", "verify", "Check integrity"),
    ("Split", "TRANSFORM", "split", "Split into parts"),
    ("Join", "TRANSFORM", "join", "Rejoin split archives"),
    ("Encrypt", "SECURITY", "encrypt", "Password protect"),
    ("Decrypt", "SECURITY", "decrypt", "Open protected"),
    ("Repair", "INTEGRITY", "repair", "Fix corrupted archives"),
    ("Strip", "CRUD", "strip", "Remove files from archives"),
    ("Rename", "CRUD", "rename", "Rename files inside"),
    ("Merge", "TRANSFORM", "merge", "Combine multiple archives"),
    ("Diff", "META", "diff", "Compare two archives"),
    ("Optimize", "TRANSFORM", "optimize", "Recompress better"),
    ("Benchmark", "META", "benchmark", "Test speed/ratio"),
    ("Hash", "INTEGRITY", "hash", "Compute hashes inside"),
    ("Walk", "UTILITY", "walk", "Handle nested archives"),
    ("Batch", "UTILITY", "batch", "Operate on many at once"),
]""",
    "GRAPH_EDGES": """GRAPH_EDGES = [
    ("Compress", "Write", "FEEDS"), ("Write", "Read", "FEEDS"), ("Read", "Extract", "FEEDS"),
    ("Strip", "Write", "PAIRS"), ("Rename", "Write", "PAIRS"), ("Verify", "Repair", "TRIGGERS"),
    ("Verify", "Hash", "PAIRS"), ("Repair", "Extract", "FALLBACK"), ("Convert", "Compress", "USES"),
    ("Merge", "Compress", "USES"), ("Split", "Join", "PAIRS"), ("Optimize", "Convert", "USES"),
    ("Encrypt", "Decrypt", "PAIRS"), ("Decrypt", "Extract", "ENABLES"), ("Decrypt", "Read", "ENABLES"),
    ("Search", "Read", "USES"), ("Stream", "Read", "ALTERNATIVE"), ("Walk", "Read", "USES"),
    ("Walk", "Extract", "USES"), ("Batch", "Compress", "WRAPS"), ("Batch", "Extract", "WRAPS"),
    ("Batch", "Verify", "WRAPS"), ("Batch", "Convert", "WRAPS"), ("Batch", "Search", "WRAPS"),
    ("Info", "List", "PAIRS"), ("Diff", "Hash", "USES"), ("Benchmark", "Compress", "MEASURES"),
    ("Benchmark", "Convert", "MEASURES"),
]""",
    "GRAPH_FLOWS": """GRAPH_FLOWS = {
    "Compress": [("io", "INPUT: source, output, format, level"), ("step", "Validate source exists"), ("decision", "File or directory?"), ("step", "Collect file(s)"), ("decision", "Format: zip/tar/gz/bz2/xz/7z?"), ("step", "Open archive writer"), ("step", "Set compression level"), ("step", "Add files to archive"), ("step", "Close and finalize"), ("return", "(True, archive_path, '')"), ("error", "source missing -> (False,None,'missing')"), ("error", "format unsupported -> (False,None,'bad format')")],
    "Extract": [("io", "INPUT: archive, dest, filter, overwrite"), ("step", "Validate archive"), ("step", "Detect format"), ("step", "Open reader"), ("decision", "File filter?"), ("step", "Filter or select all"), ("decision", "Overwrite?"), ("step", "Extract files"), ("return", "(True, count, '')"), ("error", "corrupt -> (False,0,'corrupt')")],
    "Read": [("io", "INPUT: archive, file_name, encoding"), ("step", "Open reader"), ("step", "Locate file"), ("decision", "File in archive?"), ("step", "Read content"), ("decision", "JSON?"), ("step", "Parse or return raw"), ("return", "(True, content, '')"), ("error", "not found -> (False,None,'missing')")],
    "Write": [("io", "INPUT: archive, file_name, content, mode"), ("decision", "Create or append?"), ("step", "Open archive"), ("step", "Write file"), ("step", "Preserve existing if append"), ("return", "(True, count, '')"), ("error", "read-only -> (False,0,'read-only')")],
    "Info": [("io", "INPUT: archive, file_name?"), ("step", "Open reader"), ("step", "Read metadata"), ("decision", "File-specific?"), ("step", "Get file or archive info"), ("return", "(True, info_dict, '')")],
    "List": [("io", "INPUT: archive, filter, sort_by, sort_order"), ("step", "Get entries"), ("decision", "Filter?"), ("step", "Apply filter"), ("step", "Sort entries"), ("return", "(True, file_list, '')")],
    "Search": [("io", "INPUT: archive, term, filter, regex"), ("step", "Get file list"), ("decision", "Filter?"), ("step", "Read each file"), ("decision", "Regex?"), ("step", "Search content"), ("step", "Collect matches"), ("return", "(True, matches, '')")],
    "Stream": [("io", "INPUT: archive, file_name, chunk_size, callback"), ("step", "Open file entry"), ("step", "LOOP: read chunk"), ("decision", "EOF?"), ("step", "Send to callback"), ("step", "END LOOP"), ("return", "(True, total_bytes, '')")],
    "Convert": [("io", "INPUT: source, target_format"), ("step", "Detect source format"), ("decision", "Same format?"), ("call", "Read.all — read source"), ("call", "Compress — create target"), ("return", "(True, output, '')")],
    "Verify": [("io", "INPUT: archive, deep"), ("step", "Check structure"), ("decision", "Deep?"), ("step", "CRC check all files"), ("decision", "Damaged files?"), ("step", "Build report"), ("return", "(True, report, '')")],
    "Split": [("io", "INPUT: archive, part_size, output_dir"), ("step", "Get total size"), ("step", "Calc num parts"), ("step", "LOOP: read part_size, write part"), ("return", "(True, part_list, '')")],
    "Join": [("io", "INPUT: parts, output"), ("step", "Sort parts by number"), ("step", "LOOP: write each part to output"), ("call", "Verify — check joined"), ("return", "(True, output, '')")],
    "Encrypt": [("io", "INPUT: archive, password, method"), ("decision", "AES-256 or ZipCrypto?"), ("step", "Read all files"), ("step", "Create encrypted archive"), ("return", "(True, archive, '')")],
    "Decrypt": [("io", "INPUT: archive, password"), ("step", "Open with password"), ("decision", "Password correct?"), ("step", "Read all files"), ("decision", "Remove password?"), ("step", "Re-save unprotected"), ("return", "(True, content, '')"), ("error", "wrong password -> (False,None,'bad password')")],
    "Repair": [("io", "INPUT: archive, output, options"), ("step", "Attempt open"), ("decision", "Opens?"), ("step", "Minor repair OR raw recovery"), ("step", "Scan for file signatures"), ("step", "Extract undamaged files"), ("step", "Rebuild archive"), ("return", "(True, recovered, '')"), ("error", "unrecoverable -> (False,0,'gone')")],
    "Strip": [("io", "INPUT: archive, file/pattern"), ("step", "Get entries"), ("decision", "Pattern or single?"), ("step", "Read OTHER files"), ("step", "Create archive without targets"), ("return", "(True, removed, '')")],
    "Rename": [("io", "INPUT: archive, old, new/mapping"), ("decision", "Mapping or single?"), ("decision", "Regex?"), ("step", "Apply renames"), ("step", "Rebuild archive"), ("return", "(True, renamed, '')")],
    "Merge": [("io", "INPUT: archives[], output, format"), ("step", "Create output archive"), ("step", "LOOP: each source"), ("call", "Read — read source files"), ("decision", "Conflict?"), ("step", "skip/overwrite/rename"), ("step", "Write to output"), ("return", "(True, output, '')")],
    "Diff": [("io", "INPUT: archive_a, archive_b"), ("call", "List — get both file lists"), ("step", "Files only in A"), ("step", "Files only in B"), ("call", "Hash — hash shared files"), ("step", "Compare hashes"), ("decision", "Content diff?"), ("step", "Line-by-line diff"), ("return", "(True, diff_report, '')")],
    "Optimize": [("io", "INPUT: archive, output, format, level"), ("call", "Read — read all files"), ("step", "Detect duplicates by hash"), ("step", "Remove dupes"), ("step", "Choose best compression per type"), ("call", "Compress — create optimized"), ("return", "(True, savings, '')")],
    "Benchmark": [("io", "INPUT: source, formats, levels"), ("step", "LOOP: each format"), ("step", "LOOP: each level"), ("call", "Compress — compress with format+level"), ("step", "Measure time+size+ratio"), ("step", "END LOOPs"), ("step", "Rank results"), ("step", "Recommend best"), ("return", "(True, report, '')")],
    "Hash": [("io", "INPUT: archive, files, algorithm"), ("step", "Open reader"), ("decision", "Specific files?"), ("step", "LOOP: read+hash each file"), ("decision", "md5/sha256/crc32?"), ("step", "Compute hash"), ("return", "(True, hash_dict, '')")],
    "Walk": [("io", "INPUT: archive, max_depth, callback"), ("step", "Get file list"), ("step", "LOOP: each file"), ("decision", "Is archive?"), ("decision", "Depth < max?"), ("step", "Recurse into nested"), ("step", "Call callback"), ("return", "(True, file_tree, '')")],
    "Batch": [("io", "INPUT: paths/glob, operation, params"), ("step", "Resolve file list"), ("step", "Create thread pool"), ("step", "LOOP: each archive (parallel)"), ("decision", "Operation type?"), ("call", "Compress/Extract/Verify/Convert/Search"), ("step", "Collect result"), ("step", "Report progress"), ("return", "(True, results, '')")],
}""",
    "GRAPH_LIFECYCLE_PHASES": """GRAPH_LIFECYCLE_PHASES = [
    ("CREATE", "#a6e3a1", "Archive comes into existence"),
    ("READ", "#89b4fa", "Archive contents are accessed"),
    ("UPDATE", "#fab387", "Archive contents are modified"),
    ("TRANSFORM", "#cba6f7", "Archive is converted/restructured"),
    ("DESTROY", "#f38ba8", "Archive or contents are removed"),
    ("VERIFY", "#94e2d5", "Archive integrity is checked"),
    ("RECOVER", "#f9e2af", "Archive is repaired after failure"),
]""",
    "GRAPH_CLASS_PHASE": """GRAPH_CLASS_PHASE = {
    "Compress": "CREATE", "Extract": "READ", "Read": "READ", "Write": "UPDATE",
    "Info": "READ", "List": "READ", "Search": "READ", "Stream": "READ",
    "Convert": "TRANSFORM", "Verify": "VERIFY", "Split": "TRANSFORM",
    "Join": "TRANSFORM", "Encrypt": "UPDATE", "Decrypt": "READ",
    "Repair": "RECOVER", "Strip": "DESTROY", "Rename": "UPDATE",
    "Merge": "TRANSFORM", "Diff": "VERIFY", "Optimize": "TRANSFORM",
    "Benchmark": "VERIFY", "Hash": "VERIFY", "Walk": "READ", "Batch": "CREATE",
}""",
    "GRAPH_PHASE_COLORS": """GRAPH_PHASE_COLORS = {name: color for name, color, _ in GRAPH_LIFECYCLE_PHASES}""",
    "GRAPH_PHASE_ORDER": """GRAPH_PHASE_ORDER = [name for name, _, _ in GRAPH_LIFECYCLE_PHASES]""",
    "GRAPH_OPERATION_VERBS": """GRAPH_OPERATION_VERBS = [
    "compress", "extract", "read", "write", "info", "list", "search", "stream",
    "convert", "verify", "split", "join", "encrypt", "decrypt", "repair",
    "strip", "rename", "merge", "diff", "optimize", "benchmark", "hash",
    "walk", "batch", "create", "delete", "update", "insert", "remove",
    "load", "save", "export", "import", "parse", "validate", "authenticate",
    "authorize", "configure", "monitor", "log", "cache", "sync", "backup",
    "restore", "archive", "scan", "filter", "sort", "count", "check",
    "test", "debug", "trace", "profile", "schedule", "queue", "dispatch",
    "render", "format", "encode", "decode", "pack", "unpack", "send",
    "receive", "connect", "disconnect", "open", "close", "start", "stop",
    "pause", "resume", "reset", "clear", "flush", "commit", "rollback",
]""",
    "GRAPH_VERB_CATEGORY": """GRAPH_VERB_CATEGORY = {
    "compress": "CRUD", "extract": "CRUD", "read": "CRUD", "write": "CRUD",
    "create": "CRUD", "delete": "CRUD", "update": "CRUD", "insert": "CRUD",
    "remove": "CRUD", "strip": "CRUD", "rename": "CRUD", "load": "CRUD",
    "save": "CRUD", "open": "CRUD", "close": "CRUD", "clear": "CRUD",
    "flush": "CRUD", "pack": "CRUD", "unpack": "CRUD",
    "verify": "INTEGRITY", "validate": "INTEGRITY", "check": "INTEGRITY",
    "test": "INTEGRITY", "hash": "INTEGRITY", "repair": "INTEGRITY",
    "scan": "INTEGRITY", "debug": "INTEGRITY", "trace": "INTEGRITY",
    "authenticate": "SECURITY", "authorize": "SECURITY",
    "encrypt": "SECURITY", "decrypt": "SECURITY",
    "convert": "TRANSFORM", "merge": "TRANSFORM", "split": "TRANSFORM",
    "join": "TRANSFORM", "optimize": "TRANSFORM", "format": "TRANSFORM",
    "encode": "TRANSFORM", "decode": "TRANSFORM", "render": "TRANSFORM",
    "walk": "UTILITY", "batch": "UTILITY", "search": "UTILITY",
    "stream": "UTILITY", "list": "META", "info": "META", "diff": "META",
    "benchmark": "META", "count": "META",
}""",
}

GRAPH_SCHEMA = """CREATE TABLE IF NOT EXISTS graph_categories (
    name        TEXT PRIMARY KEY,
    color       TEXT NOT NULL,
    sort_order  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_classes (
    name            TEXT PRIMARY KEY,
    category        TEXT NOT NULL,
    dispatch_key    TEXT NOT NULL,
    description     TEXT NOT NULL,
    FOREIGN KEY (category) REFERENCES graph_categories(name)
);
CREATE TABLE IF NOT EXISTS graph_edges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    src         TEXT NOT NULL,
    dst         TEXT NOT NULL,
    edge_type   TEXT NOT NULL,
    FOREIGN KEY (src) REFERENCES graph_classes(name),
    FOREIGN KEY (dst) REFERENCES graph_classes(name)
);
CREATE INDEX IF NOT EXISTS idx_ge_src ON graph_edges(src);
CREATE INDEX IF NOT EXISTS idx_ge_dst ON graph_edges(dst);
CREATE INDEX IF NOT EXISTS idx_ge_type ON graph_edges(edge_type);
CREATE TABLE IF NOT EXISTS graph_edge_colors (
    edge_type   TEXT PRIMARY KEY,
    color       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_flows (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    class_name  TEXT NOT NULL,
    step_order  INTEGER NOT NULL,
    step_type   TEXT NOT NULL,
    step_text   TEXT NOT NULL,
    FOREIGN KEY (class_name) REFERENCES graph_classes(name)
);
CREATE INDEX IF NOT EXISTS idx_gf_class ON graph_flows(class_name);
CREATE INDEX IF NOT EXISTS idx_gf_type ON graph_flows(step_type);
CREATE TABLE IF NOT EXISTS graph_flow_colors (
    step_type   TEXT PRIMARY KEY,
    color       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_lifecycle_phases (
    name        TEXT PRIMARY KEY,
    color       TEXT NOT NULL,
    description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_class_phase (
    class_name  TEXT PRIMARY KEY,
    phase       TEXT NOT NULL,
    FOREIGN KEY (class_name) REFERENCES graph_classes(name),
    FOREIGN KEY (phase) REFERENCES graph_lifecycle_phases(name)
);
CREATE TABLE IF NOT EXISTS graph_operation_verbs (
    verb        TEXT PRIMARY KEY,
    category    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gov_cat ON graph_operation_verbs(category);
"""

# Step 3: Generate new Config.py from DB
cur.execute("SELECT text FROM src WHERE file = 'Config.py' ORDER BY lineno")
config_lines = [row[0] for row in cur.fetchall()]
config_content = "\n".join(config_lines)

# Insert graph constants before class Config
class_pos = config_content.find("class Config:")
if class_pos >= 0:
    constants_block = "\n\n".join(GRAPH_CONSTANTS.values()) + "\n\n"
    config_content = config_content[:class_pos] + constants_block + config_content[class_pos:]

# Insert GRAPH_SCHEMA before class Config
schema_pos = config_content.find("class Config:")
if schema_pos >= 0:
    config_content = config_content[:schema_pos] + 'GRAPH_SCHEMA = """\n' + GRAPH_SCHEMA + '"""\n\n' + config_content[schema_pos:]

# Update _BuildDb to execute GRAPH_SCHEMA
config_content = config_content.replace(
    "conn.executescript(SCHEMA_SQL)\n            for p in PRIMITIVES:",
    "conn.executescript(SCHEMA_SQL)\n            conn.executescript(GRAPH_SCHEMA)\n            for p in PRIMITIVES:"
)

# Write Config.py
(BASE_DIR / "Config.py").write_text(config_content, encoding="utf-8")
print("Config.py written from DB")

# Step 4: Verify Config.py compiles
import py_compile
try:
    py_compile.compile(str(BASE_DIR / "Config.py"), doraise=True)
    print("Config.py compiles OK")
except Exception as e:
    print(f"Config.py compile error: {e}")

# Step 5: Test DB build
try:
    import sys
    sys.path.insert(0, str(BASE_DIR))
    from Config import Config
    cfg = Config()
    result = cfg.Run("build_db")
    print(f"DB build result: {result[0]}")
    if result[0] == 1:
        print(f"Tables: {result[1]['tables']}, Primitives: {result[1]['primitives']}")
except Exception as e:
    print(f"DB build error: {e}")

conn.close()
print("Done")
