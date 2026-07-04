import sqlite3
import os
import hashlib
import ast

DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Unified/_hw_extract.db"
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("""CREATE TABLE code_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE,
    file_hash TEXT,
    full_source TEXT,
    line_count INTEGER,
    class_count INTEGER,
    method_count INTEGER,
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
)""")

c.execute("""CREATE TABLE code_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT,
    class_name TEXT,
    method_name TEXT,
    unit_type TEXT,
    source_text TEXT,
    line_start INTEGER,
    line_end INTEGER,
    content_hash TEXT
)""")

c.execute("""CREATE TABLE extraction_plan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step INTEGER,
    action TEXT,
    source_file TEXT,
    source_class TEXT,
    source_lines TEXT,
    target_file TEXT,
    details TEXT,
    status TEXT DEFAULT 'pending'
)""")

c.execute("""CREATE TABLE merged_code (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT,
    source_text TEXT,
    line_count INTEGER,
    content_hash TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)""")

c.execute("""CREATE TABLE validation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_name TEXT,
    target TEXT,
    passed INTEGER,
    details TEXT
)""")

FILES = [
    "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_qa_engine/GhostQAEngine.py",
    "/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Unified/LocalAgent.py",
    "/Users/wws/Qdrant_mysql_mlx_vector_engine/ModelControlCenter/hardware_detector.py",
]

for fpath in FILES:
    with open(fpath, "r") as f:
        source = f.read()
    fhash = hashlib.sha256(source.encode()).hexdigest()[:16]
    tree = ast.parse(source)
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    methods = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    c.execute(
        "INSERT INTO code_files (file_path, file_hash, full_source, line_count, class_count, method_count) VALUES (?,?,?,?,?,?)",
        (fpath, fhash, source, len(source.splitlines()), len(classes), len(methods)),
    )
    src_lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            cls_src = chr(10).join(src_lines[node.lineno - 1 : node.end_lineno])
            c.execute(
                "INSERT INTO code_units (file_path, class_name, method_name, unit_type, source_text, line_start, line_end, content_hash) VALUES (?,?,?,?,?,?,?,?)",
                (fpath, node.name, None, "CLASS", cls_src, node.lineno, node.end_lineno, hashlib.sha256(cls_src.encode()).hexdigest()[:16]),
            )
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    m_src = chr(10).join(src_lines[item.lineno - 1 : item.end_lineno])
                    c.execute(
                        "INSERT INTO code_units (file_path, class_name, method_name, unit_type, source_text, line_start, line_end, content_hash) VALUES (?,?,?,?,?,?,?,?)",
                        (fpath, node.name, item.name, "METHOD", m_src, item.lineno, item.end_lineno, hashlib.sha256(m_src.encode()).hexdigest()[:16]),
                    )

conn.commit()
print("Ingested %d files" % len(FILES))
print()

# Show what we have
print("=== CLASSES ===")
for row in c.execute(
    "SELECT file_path, class_name, line_start, line_end FROM code_units WHERE unit_type='CLASS' ORDER BY file_path, line_start"
):
    short = row[0].split("/")[-1]
    print("  %s:%d-%d  class %s" % (short, row[2], row[3], row[1]))

print()
print("=== HARDWARE METHODS ===")
for row in c.execute(
    """SELECT file_path, class_name, method_name, line_start, line_end FROM code_units
    WHERE unit_type='METHOD' AND (
    method_name LIKE '%ram%' OR method_name LIKE '%cpu%' OR method_name LIKE '%gpu%'
    OR method_name LIKE '%disk%' OR method_name LIKE '%hardware%' OR method_name LIKE '%detect%'
    OR method_name LIKE '%neural%' OR method_name LIKE '%metal%' OR method_name LIKE '%check%'
    OR method_name LIKE '%can%' OR method_name LIKE '%summary%' OR method_name LIKE '%warning%'
    ) ORDER BY file_path, line_start"""
):
    short = row[0].split("/")[-1]
    print("  %s:%d-%d  %s.%s" % (short, row[3], row[4], row[1], row[2]))

conn.close()
