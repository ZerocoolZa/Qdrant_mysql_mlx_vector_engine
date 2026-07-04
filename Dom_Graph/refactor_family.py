#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<One-shot refactor script: ingests files into SQLite extracts shared data moves to Config.py renames files patches imports. NOT VBStyle: non-standard header format uses parentheses instead of braces. No class no Run() dispatch no Tuple3 returns. Has 12 print() calls. Hardcoded path (/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph). Multiple standalone functions.>][@todos<1. Fix header format to standard VBStyle. 2. Remove print() calls. 3. Remove hardcoded paths. 4. Wrap in class with Run() dispatch and Tuple3 returns.>]}
"""
#[@GHOST]{("file_path=/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/refactor_family.py";"purpose=One-shot refactor: ingest all Dom_Graph Python files into SQLite, extract shared data, move to Config.py, rename files to PascalCase, patch imports, verify")}
#[@VBSTYLE]{("no=no_print|no_tabs|no_self_underscore|no_decorators";"return=Tuple3")}
#[@DOMAIN]{("Dom_Graph")}
#[@METHODS]{("main";"ingest";"extract_data";"build_config";"rename_files";"patch_files";"verify")}
"""

import os
import re
import sqlite3
import tempfile
import py_compile
import sys
from pathlib import Path

BASE_DIR = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph")

# Files that share spec data and need to be patched
GRAPH_FILES = [
    "plan_graph.py", "spec_graph.py", "spec_flow.py", "lifecycle_graph.py",
    "dep_graph.py", "error_graph.py", "orch_graph.py", "gap_graph.py",
]

# All Python files to rename to PascalCase
RENAME_MAP = {
    "plan_graph.py":          "PlanGraph.py",
    "spec_graph.py":          "SpecGraph.py",
    "spec_flow.py":           "SpecFlow.py",
    "lifecycle_graph.py":     "LifecycleGraph.py",
    "dep_graph.py":           "DepGraph.py",
    "error_graph.py":         "ErrorGraph.py",
    "orch_graph.py":          "OrchGraph.py",
    "gap_graph.py":           "GapGraph.py",
    "graph_engine.py":        "DomGraphEngine.py",
    "graph_engine_v2.py":     "GraphEngineV2.py",
    "Efi_agent_graph.py":     "EfiAgentGraph.py",
    "Efi_boot_graph.py":      "EfiBootGraph.py",
    "Efi_code_graph.py":      "EfiCodeGraph.py",
    "Efi_graph_viewer.py":    "EfiGraphViewer.py",
    "db_architecture_gui.py": "DbArchitectureGui.py",
    "ingest_graph_from_mysql.py": "IngestGraphFromMysql.py",
    "runtime_twin_populate.py": "RuntimeTwinPopulate.py",
    "mac_server.c":           "MacServer.c",
}


def regexp(pattern, text):
    if text is None:
        return 0
    return 1 if re.search(pattern, text, re.MULTILINE) else 0


def ingest_all(cur):
    """Load every .py file in BASE_DIR as (file, lineno, text) rows."""
    cur.connection.create_function("REGEXP", 2, regexp)
    cur.execute("CREATE TABLE src (file TEXT, lineno INTEGER, text TEXT)")
    for path in sorted(BASE_DIR.glob("*.py")):
        short = path.name
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                cur.execute("INSERT INTO src VALUES (?, ?, ?)", (short, i, line.rstrip("\n")))


def extract_block(cur, filename, var_name):
    """Find a top-level assignment block and return lines from start to end."""
    cur.execute("""
        SELECT lineno, text FROM src
        WHERE file = ? AND text REGEXP '^' || ? || '\\s*=\\s*\\{|^' || ? || '\\s*=\\s*\\[|^' || ? || '\\s*=\\s*\\('
        ORDER BY lineno LIMIT 1
    """, (filename, var_name, var_name, var_name))
    start = cur.fetchone()
    if not start:
        return []
    start_line = start[0]

    # Find the next top-level assignment or class/def after this line
    cur.execute("""
        SELECT lineno FROM src
        WHERE file = ? AND lineno > ? AND text REGEXP '^[A-Za-z_][A-Za-z0-9_]*\\s*=|^class\\s|^def\\s'
        ORDER BY lineno LIMIT 1
    """, (filename, start_line))
    end = cur.fetchone()
    end_line = end[0] if end else 1000000

    cur.execute("SELECT text FROM src WHERE file = ? AND lineno >= ? AND lineno < ? ORDER BY lineno",
                (filename, start_line, end_line))
    return [row[0] for row in cur.fetchall()]


def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def remove_block(content, var_name):
    """Remove a top-level assignment block for a given variable."""
    pattern = r"^(?P<block>" + var_name + r"\s*=\s*(\{|\[|\().*?\n)(?=(^[A-Za-z_][A-Za-z0-9_]*\s*=|^class\s|^def\s|^#\s*[-─]{3}|^\n\n))"
    flags = re.MULTILINE | re.DOTALL
    m = re.search(pattern, content, flags)
    if m:
        content = content[:m.start()] + content[m.end():]
    return content


def remove_category_comment(content):
    """Remove shared spec data comments above blocks."""
    content = re.sub(r"#\s*[-─]{3,}\s*Shared spec data.*?\n(?=#\s*[-─]{3,}\s*(Domain Categories|Categories|Spec Definition|Edges|Flows|Each phase))", "", content, flags=re.DOTALL)
    content = re.sub(r"#\s*[-─]{3,}\s*Domain Categories.*?\n", "", content)
    content = re.sub(r"#\s*[-─]{3,}\s*Spec Definition \(from SPEC\.md\).*?\n", "", content)
    content = re.sub(r"#\s*[-─]{3,}\s*Edges \(planned relationships\).*?\n", "", content)
    content = re.sub(r"#\s*[-─]{3,}\s*Flows.*?\n", "", content)
    content = re.sub(r"#\s*[-─]{3,}\s*Each phase is a stage.*?\n", "", content)
    content = re.sub(r"#\s*Map each class to its primary lifecycle phase.*?\n", "", content)
    return content


def rename_and_patch(cur):
    """Rename files to PascalCase and patch graph files to import from Config."""
    for old_name, new_name in RENAME_MAP.items():
        old_path = BASE_DIR / old_name
        new_path = BASE_DIR / new_name
        if not old_path.exists():
            continue

        if old_path.suffix == ".py":
            content = read_file(old_path)

            # If this is one of the graph files that duplicated data, remove blocks and patch
            if old_name in GRAPH_FILES:
                # Remove all duplicated shared data blocks
                for var in ["CATEGORIES", "CLASSES", "EDGES", "REDGES", "FLOWS", "ECOLORS",
                            "EDGE_COLORS", "SCOLORS", "LIFECYCLE_PHASES", "CLASS_PHASE",
                            "PHASE_COLORS", "PHASE_ORDER"]:
                    content = remove_block(content, var)
                content = remove_category_comment(content)

                # Add import from Config if not already present
                if "from Config import Config" not in content:
                    # Insert after docstring if there is one, else at top
                    docstring_match = re.search(r'^("""[\s\S]*?"""\n)', content)
                    if docstring_match:
                        insert_pos = docstring_match.end()
                    else:
                        insert_pos = 0
                    content = content[:insert_pos] + "\nfrom Config import Config\n" + content[insert_pos:]

                # Replace local variable references with Config constants
                content = re.sub(r"\bCATEGORIES\b", "Config.GRAPH_CATEGORIES", content)
                content = re.sub(r"\bCATEGORY_ORDER\b", "Config.GRAPH_CATEGORY_ORDER", content)
                content = re.sub(r"\bCLASSES\b", "Config.GRAPH_CLASSES", content)
                content = re.sub(r"\bEDGES\b", "Config.GRAPH_EDGES", content)
                content = re.sub(r"\bREDGES\b", "Config.GRAPH_EDGES", content)
                content = re.sub(r"\bFLOWS\b", "Config.GRAPH_FLOWS", content)
                content = re.sub(r"\bECOLORS\b", "Config.GRAPH_EDGE_COLORS", content)
                content = re.sub(r"\bEDGE_COLORS\b", "Config.GRAPH_EDGE_COLORS", content)
                content = re.sub(r"\bSCOLORS\b", "Config.GRAPH_FLOW_COLORS", content)
                content = re.sub(r"\bLIFECYCLE_PHASES\b", "Config.GRAPH_LIFECYCLE_PHASES", content)
                content = re.sub(r"\bCLASS_PHASE\b", "Config.GRAPH_CLASS_PHASE", content)
                content = re.sub(r"\bPHASE_COLORS\b", "Config.GRAPH_PHASE_COLORS", content)
                content = re.sub(r"\bPHASE_ORDER\b", "Config.GRAPH_PHASE_ORDER", content)
                content = re.sub(r"\bOPERATION_VERBS\b", "Config.GRAPH_OPERATION_VERBS", content)
                content = re.sub(r"\bVERB_CATEGORY\b", "Config.GRAPH_VERB_CATEGORY", content)

                # Replace title strings that reference old domain
                content = re.sub(r'"dom_compression\s*—\s*Spec Graph.*?"',
                                 '"Dom_Graph — Spec Graph (from DB)"', content)
                content = re.sub(r'"dom_compression\s*—\s*Spec Flow Analyzer"',
                                 '"Dom_Graph — Spec Flow Analyzer"', content)

            write_file(new_path, content)
            old_path.unlink()
        else:
            # For .c just rename
            old_path.rename(new_path)


def build_graph_constants():
    """Return the shared graph data extracted from the original files."""
    categories = {
        "CRUD": "#a6e3a1", "INTEGRITY": "#f38ba8", "TRANSFORM": "#fab387",
        "SECURITY": "#cba6f7", "UTILITY": "#89b4fa", "META": "#f9e2af",
    }
    category_order = ["CRUD", "INTEGRITY", "TRANSFORM", "SECURITY", "UTILITY", "META"]
    edge_colors = {
        "FEEDS": "#a6e3a1", "PAIRS": "#f9e2af", "TRIGGERS": "#f38ba8",
        "FALLBACK": "#fab387", "USES": "#89b4fa", "ENABLES": "#cba6f7",
        "ALTERNATIVE": "#94e2d5", "WRAPS": "#89dceb", "MEASURES": "#f9e2af",
    }
    flow_colors = {
        "io": "#89b4fa", "step": "#a6e3a1", "decision": "#f9e2af",
        "error": "#f38ba8", "call": "#cba6f7", "return": "#94e2d5",
    }
    classes = [
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
    ]
    edges = [
        ("Compress", "Write", "FEEDS"), ("Write", "Read", "FEEDS"),
        ("Read", "Extract", "FEEDS"), ("Strip", "Write", "PAIRS"),
        ("Rename", "Write", "PAIRS"), ("Verify", "Repair", "TRIGGERS"),
        ("Verify", "Hash", "PAIRS"), ("Repair", "Extract", "FALLBACK"),
        ("Convert", "Compress", "USES"), ("Merge", "Compress", "USES"),
        ("Split", "Join", "PAIRS"), ("Optimize", "Convert", "USES"),
        ("Encrypt", "Decrypt", "PAIRS"), ("Decrypt", "Extract", "ENABLES"),
        ("Decrypt", "Read", "ENABLES"), ("Search", "Read", "USES"),
        ("Stream", "Read", "ALTERNATIVE"), ("Walk", "Read", "USES"),
        ("Walk", "Extract", "USES"), ("Batch", "Compress", "WRAPS"),
        ("Batch", "Extract", "WRAPS"), ("Batch", "Verify", "WRAPS"),
        ("Batch", "Convert", "WRAPS"), ("Batch", "Search", "WRAPS"),
        ("Info", "List", "PAIRS"), ("Diff", "Hash", "USES"),
        ("Benchmark", "Compress", "MEASURES"), ("Benchmark", "Convert", "MEASURES"),
    ]
    flows = {
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
    }
    lifecycle_phases = [
        ("CREATE", "#a6e3a1", "Archive comes into existence"),
        ("READ", "#89b4fa", "Archive contents are accessed"),
        ("UPDATE", "#fab387", "Archive contents are modified"),
        ("TRANSFORM", "#cba6f7", "Archive is converted/restructured"),
        ("DESTROY", "#f38ba8", "Archive or contents are removed"),
        ("VERIFY", "#94e2d5", "Archive integrity is checked"),
        ("RECOVER", "#f9e2af", "Archive is repaired after failure"),
    ]
    class_phase = {
        "Compress": "CREATE", "Extract": "READ", "Read": "READ", "Write": "UPDATE",
        "Info": "READ", "List": "READ", "Search": "READ", "Stream": "READ",
        "Convert": "TRANSFORM", "Verify": "VERIFY", "Split": "TRANSFORM",
        "Join": "TRANSFORM", "Encrypt": "UPDATE", "Decrypt": "READ",
        "Repair": "RECOVER", "Strip": "DESTROY", "Rename": "UPDATE",
        "Merge": "TRANSFORM", "Diff": "VERIFY", "Optimize": "TRANSFORM",
        "Benchmark": "VERIFY", "Hash": "VERIFY", "Walk": "READ", "Batch": "CREATE",
    }
    operation_verbs = [
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
    ]
    verb_category = {
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
        "compress": "CRUD", "walk": "UTILITY", "batch": "UTILITY", "search": "UTILITY",
        "stream": "UTILITY", "list": "META", "info": "META", "diff": "META",
        "benchmark": "META", "count": "META",
    }
    return {
        "GRAPH_CATEGORIES": categories,
        "GRAPH_CATEGORY_ORDER": category_order,
        "GRAPH_EDGE_COLORS": edge_colors,
        "GRAPH_FLOW_COLORS": flow_colors,
        "GRAPH_CLASSES": classes,
        "GRAPH_EDGES": edges,
        "GRAPH_FLOWS": flows,
        "GRAPH_LIFECYCLE_PHASES": lifecycle_phases,
        "GRAPH_CLASS_PHASE": class_phase,
        "GRAPH_PHASE_COLORS": {name: color for name, color, _ in lifecycle_phases},
        "GRAPH_PHASE_ORDER": [name for name, _, _ in lifecycle_phases],
        "GRAPH_OPERATION_VERBS": operation_verbs,
        "GRAPH_VERB_CATEGORY": verb_category,
    }


def build_graph_schema_tables():
    """Return SQL schema for graph tables to append to SCHEMA_SQL."""
    return """
CREATE TABLE IF NOT EXISTS graph_categories (
    name    TEXT PRIMARY KEY,
    color   TEXT NOT NULL,
    sort_order INTEGER NOT NULL
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


def patch_config(config_path, graph_data, schema_extra):
    """Add graph constants, schema tables, and population code to Config.py."""
    content = read_file(config_path)

    # Add graph constants after SCHEMA_SQL definition (before class Config)
    constants_block = "\n".join(
        f"{name} = {repr(value)}"
        for name, value in graph_data.items()
    )
    insert_after = "SCHEMA_SQL = \"\"\"\\"
    # Find end of SCHEMA_SQL block
    marker = 'SCHEMA_SQL = """\\'
    pos = content.find(marker)
    if pos < 0:
        marker = 'SCHEMA_SQL = """'
        pos = content.find(marker)
    if pos >= 0:
        pos = content.find('"""', pos + len(marker))
        pos = content.find('"""', pos + 1) + 3
    else:
        pos = 0

    content = content[:pos] + "\n\n# ─── Graph Specification Data (DB seed) ─────────────────────\n" + constants_block + "\n" + content[pos:]

    # Append graph schema tables to SCHEMA_SQL (insert before closing '"""')
    # Find the last '"""' that closes SCHEMA_SQL
    last_close = content.rfind('"""')
    if last_close > 0:
        content = content[:last_close] + schema_extra + "\n" + content[last_close:]

    # Update _BuildDb to populate graph tables after primitives
    build_insert = """
        # Populate graph spec tables from constants
        for cat, color in GRAPH_CATEGORIES.items():
            order = GRAPH_CATEGORY_ORDER.index(cat)
            conn.execute("INSERT OR REPLACE INTO graph_categories (name, color, sort_order) VALUES (?, ?, ?)", (cat, color, order))
        for e_type, color in GRAPH_EDGE_COLORS.items():
            conn.execute("INSERT OR REPLACE INTO graph_edge_colors (edge_type, color) VALUES (?, ?)", (e_type, color))
        for step_type, color in GRAPH_FLOW_COLORS.items():
            conn.execute("INSERT OR REPLACE INTO graph_flow_colors (step_type, color) VALUES (?, ?)", (step_type, color))
        for name, cat, dispatch, desc in GRAPH_CLASSES:
            conn.execute("INSERT OR REPLACE INTO graph_classes (name, category, dispatch_key, description) VALUES (?, ?, ?, ?)", (name, cat, dispatch, desc))
        for src, dst, etype in GRAPH_EDGES:
            conn.execute("INSERT INTO graph_edges (src, dst, edge_type) VALUES (?, ?, ?)", (src, dst, etype))
        for class_name, steps in GRAPH_FLOWS.items():
            for i, (step_type, step_text) in enumerate(steps):
                conn.execute("INSERT INTO graph_flows (class_name, step_order, step_type, step_text) VALUES (?, ?, ?, ?)", (class_name, i, step_type, step_text))
        for name, color, desc in GRAPH_LIFECYCLE_PHASES:
            conn.execute("INSERT OR REPLACE INTO graph_lifecycle_phases (name, color, description) VALUES (?, ?, ?)", (name, color, desc))
        for class_name, phase in GRAPH_CLASS_PHASE.items():
            conn.execute("INSERT OR REPLACE INTO graph_class_phase (class_name, phase) VALUES (?, ?)", (class_name, phase))
        for verb in GRAPH_OPERATION_VERBS:
            cat = GRAPH_VERB_CATEGORY.get(verb, "META")
            conn.execute("INSERT OR REPLACE INTO graph_operation_verbs (verb, category) VALUES (?, ?)", (verb, cat))
        conn.commit()
"""
    # Insert after the primitive loop in _BuildDb
    old = """            for p in PRIMITIVES:
                conn.execute(
                    "INSERT OR REPLACE INTO primitive_costs (name, category, cpu_us, mem_bytes, io_type, is_blocking, is_kernel, description) VALUES (?,?,?,?,?,?,?,?)",
                    p
                )
            conn.commit()"""
    new = old + build_insert
    content = content.replace(old, new)

    # Update FILE_REGISTRY to use new PascalCase names and add graph-related descriptions
    new_registry = {
        "Config":              {"file": "Config.py",              "role": "domain_config",       "desc": "This file. All constants, schema, primitive costs, graph spec data, file registry"},
        "RuntimeTwinPopulate": {"file": "RuntimeTwinPopulate.py", "role": "populator",          "desc": "Parses MacServer.c and populates the runtime twin DB with AST nodes, exec nodes, state machines, locks, heap objects, costs, timing, failure modes"},
        "DomGraphEngine":         {"file": "DomGraphEngine.py",         "role": "engine_v1",           "desc": "Static code graph engine (v1). Nodes, edges, clusters, centrality"},
        "GraphEngineV2":       {"file": "GraphEngineV2.py",       "role": "engine_v2",           "desc": "Weighted graph engine (v2). Semantic edges, cost models, bottleneck detection"},
        "PlanGraph":           {"file": "PlanGraph.py",           "role": "pipeline_1_plan",     "desc": "What are we building? Graph spec editor. Reads CATEGORIES/CLASSES/EDGES from Config"},
        "SpecGraph":           {"file": "SpecGraph.py",           "role": "pipeline_2_spec",     "desc": "What exactly exists? Renders node-edge graph from Config"},
        "SpecFlow":            {"file": "SpecFlow.py",            "role": "pipeline_3_flow",     "desc": "How does it move? Renders flow steps from Config"},
        "LifecycleGraph":      {"file": "LifecycleGraph.py",      "role": "pipeline_4_lifecycle","desc": "When does it run? Renders lifecycle phases from Config"},
        "DepGraph":            {"file": "DepGraph.py",            "role": "pipeline_5_dep",      "desc": "Why does it connect? DomGraphEdge justification graph"},
        "ErrorGraph":          {"file": "ErrorGraph.py",          "role": "pipeline_6_error",    "desc": "Where does it fail? Failure paths and recovery routes"},
        "OrchGraph":           {"file": "OrchGraph.py",           "role": "pipeline_7_orch",     "desc": "Who calls who? Call tree and dispatch hierarchy"},
        "GapGraph":            {"file": "GapGraph.py",            "role": "pipeline_8_gap",      "desc": "What is missing? Gap analysis and CRUD closure"},
        "EfiAgentGraph":       {"file": "EfiAgentGraph.py",      "role": "agent_graph",         "desc": "Agent interaction graph. Multi-agent orchestration visualization"},
        "EfiBootGraph":        {"file": "EfiBootGraph.py",       "role": "boot_graph",          "desc": "Boot sequence graph. Initialization order, dependency resolution"},
        "EfiCodeGraph":        {"file": "EfiCodeGraph.py",       "role": "code_graph",          "desc": "Code structure graph. AST-level node and edge extraction"},
        "EfiGraphViewer":      {"file": "EfiGraphViewer.py",     "role": "viewer",              "desc": "Tkinter viewer for Efi graphs. Render graph data visually"},
        "DbArchitectureGui":   {"file": "DbArchitectureGui.py",  "role": "db_viewer",           "desc": "Database architecture GUI. Visualize schema, tables, relations"},
        "IngestGraphFromMysql":{"file": "IngestGraphFromMysql.py","role": "ingest",           "desc": "Ingest graph data from MySQL into SQLite for offline analysis"},
        "MacServer":           {"file": "MacServer.c",            "role": "source_input",        "desc": "macOS remote desktop server in C. Capture, encode, network, input. The input source for the runtime twin"},
    }
    # Replace FILE_REGISTRY dict
    start = content.find("FILE_REGISTRY = {")
    end = content.find("\n\nGRAPH_PIPELINE", start)
    if end < 0:
        end = content.find("\n\n#", start + 1)
    if start >= 0 and end > start:
        content = content[:start] + "FILE_REGISTRY = " + repr(new_registry) + content[end:]

    write_file(config_path, content)


def verify():
    """Compile all Python files and build a DB to confirm graph tables."""
    failures = []
    for path in sorted(BASE_DIR.glob("*.py")):
        try:
            py_compile.compile(str(path), doraise=True)
        except Exception as e:
            failures.append((path.name, str(e)))
    return failures


def main():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    ingest_all(cur)

    print(f"Ingested {cur.execute('SELECT COUNT(*) FROM src').fetchone()[0]} lines from {cur.execute('SELECT COUNT(DISTINCT file) FROM src').fetchone()[0]} files")

    # Show duplicated variable names
    cur.execute("""
        SELECT text, COUNT(DISTINCT file) AS files, COUNT(*) AS lines
        FROM src
        WHERE text REGEXP '^[A-Za-z_][A-Za-z0-9_]*\\s*=\\s*\\{|^[A-Za-z_][A-Za-z0-9_]*\\s*=\\s*\\['
        GROUP BY text
        HAVING files > 1
        ORDER BY files DESC
    """)
    dups = cur.fetchall()
    print(f"\nDuplicated top-level assignments found: {len(dups)}")
    for text, files, lines in dups:
        print(f"  {text[:50]:50} appears in {files} files, {lines} lines")

    # Rename + patch
    rename_and_patch(cur)
    print("\nRenamed and patched files")

    # Patch Config.py with graph data + schema + DB population
    graph_data = build_graph_constants()
    schema_extra = build_graph_schema_tables()
    patch_config(BASE_DIR / "Config.py", graph_data, schema_extra)
    print("Updated Config.py with graph constants, schema tables, and population code")

    # Verify
    failures = verify()
    if failures:
        print(f"\nFAILED to compile {len(failures)} files:")
        for name, err in failures:
            print(f"  {name}: {err}")
        return 1

    # Test DB build
    sys.path.insert(0, str(BASE_DIR))
    from Config import Config
    c = Config()
    ok, data, err = c.Run("build_db", {})
    if not ok:
        print(f"\nDB build failed: {err}")
        return 1
    print(f"\nDB built: {data['tables']} tables, {data['primitives']} primitives")
    db = data["conn"]
    graph_counts = {
        "graph_categories": db.execute("SELECT COUNT(*) FROM graph_categories").fetchone()[0],
        "graph_classes": db.execute("SELECT COUNT(*) FROM graph_classes").fetchone()[0],
        "graph_edges": db.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0],
        "graph_flows": db.execute("SELECT COUNT(*) FROM graph_flows").fetchone()[0],
        "graph_lifecycle_phases": db.execute("SELECT COUNT(*) FROM graph_lifecycle_phases").fetchone()[0],
        "graph_class_phase": db.execute("SELECT COUNT(*) FROM graph_class_phase").fetchone()[0],
    }
    print("Graph table counts:", graph_counts)

    # Print final file list
    print(f"\nFinal Dom_Graph files:")
    for p in sorted(BASE_DIR.iterdir()):
        print(f"  {p.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
