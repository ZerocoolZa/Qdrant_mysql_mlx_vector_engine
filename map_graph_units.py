#!/usr/bin/env python3
"""
Map all graph-related code from local codebase + MySQL vb_code_test into a SQL database.
1 method = 1 computation unit = belongs to 1 class.
"""
import os
import re
import sys
import ast
import mysql.connector
import hashlib
import json
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────────────────────
MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASSWORD = ""
MYSQL_DB = "vb_code_test"
TARGET_DB = "graph_computation_units"
LOCAL_ROOT = "/Users/wws/Qdrant_mysql_mlx_vector_engine"

# Graph-related keywords for filtering
GRAPH_KEYWORDS = [
    "graph", "node", "edge", "cascade", "decision", "embed", "vector",
    "memory", "context", "brain", "cognitive", "knowledge", "reasoning",
    "semantic", "tfidf", "cosine", "similarity", "traverse", "adjacency",
    "topology", "cluster", "community", "centrality", "pagerank",
    "bfs", "dfs", "shortest_path", "spanning", "dag", "directed",
]

GRAPH_CLASS_PATTERNS = [
    re.compile(r"%graph%", re.I),
    re.compile(r"%node%", re.I),
    re.compile(r"%edge%", re.I),
    re.compile(r"%cascade%", re.I),
    re.compile(r"%decision%", re.I),
    re.compile(r"%embed%", re.I),
    re.compile(r"%vector%", re.I),
    re.compile(r"%memory%", re.I),
    re.compile(r"%context%", re.I),
    re.compile(r"%brain%", re.I),
    re.compile(r"%cognitive%", re.I),
    re.compile(r"%knowledge%", re.I),
    re.compile(r"%reasoning%", re.I),
]

def is_graph_related(name: str) -> bool:
    name_lower = name.lower()
    return any(kw in name_lower for kw in GRAPH_KEYWORDS)

# ─── Database Setup ───────────────────────────────────────────────────────────
def create_database():
    conn = mysql.connector.connect(host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD)
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {TARGET_DB}")
    cursor.execute(f"USE {TARGET_DB}")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS computation_units (
            id INT AUTO_INCREMENT PRIMARY KEY,
            unit_hash VARCHAR(64) UNIQUE,
            class_name VARCHAR(255) NOT NULL,
            method_name VARCHAR(255) NOT NULL,
            signature TEXT,
            body TEXT,
            file_path VARCHAR(500),
            line_start INT,
            line_end INT,
            source ENUM('local', 'mysql_vb_code_test') NOT NULL,
            domain VARCHAR(255),
            role VARCHAR(255),
            is_dunder TINYINT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_class (class_name),
            INDEX idx_source (source),
            INDEX idx_domain (domain)
        )
    """)
    cursor.execute("TRUNCATE TABLE computation_units")
    conn.commit()
    cursor.close()
    conn.close()
    print(f"[DB] Database '{TARGET_DB}' ready, table 'computation_units' created/truncated")

# ─── Source 1: MySQL vb_code_test ─────────────────────────────────────────────
def extract_from_mysql_vb_code_test():
    conn = mysql.connector.connect(host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, database=MYSQL_DB)
    cursor = conn.cursor(dictionary=True)

    # Find graph-related classes
    like_clauses = " OR ".join([f"class_name LIKE '%{kw}%'" for kw in GRAPH_KEYWORDS])
    cursor.execute(f"SELECT * FROM vb_classes WHERE {like_clauses}")
    classes = cursor.fetchall()
    print(f"[MySQL] Found {len(classes)} graph-related classes in vb_code_test")

    units = []
    for cls in classes:
        class_id = cls["id"]
        class_name = cls["class_name"]
        domain = cls.get("domain")
        role = cls.get("role")

        # Get all methods for this class
        cursor.execute("SELECT * FROM vb_methods WHERE class_id = %s", (class_id,))
        methods = cursor.fetchall()

        for m in methods:
            method_name = m["method_name"]
            params = m.get("params", "")
            method_code = m.get("method_code", "")
            is_dunder = m.get("is_dunder", 0)
            line_start = m.get("line_start")

            # Build signature
            signature = f"def {method_name}({params})" if params else f"def {method_name}()"

            # Build hash for dedup
            hash_input = f"{class_name}.{method_name}.{method_code[:200]}"
            unit_hash = hashlib.sha256(hash_input.encode()).hexdigest()

            # Estimate line_end from code
            line_end = line_start + method_code.count("\n") if line_start else None

            units.append({
                "unit_hash": unit_hash,
                "class_name": class_name,
                "method_name": method_name,
                "signature": signature,
                "body": method_code,
                "file_path": f"mysql://vb_code_test/vb_classes/{class_name}",
                "line_start": line_start,
                "line_end": line_end,
                "source": "mysql_vb_code_test",
                "domain": domain,
                "role": role,
                "is_dunder": is_dunder,
            })

    cursor.close()
    conn.close()
    print(f"[MySQL] Extracted {len(units)} computation units from vb_code_test")
    return units

# ─── Source 2: Local codebase ─────────────────────────────────────────────────
def extract_from_local_codebase():
    units = []
    root = Path(LOCAL_ROOT)

    # Directories to search
    search_dirs = [
        root / "tmp_graph_ingest",
        root / "efl_brain",
        root / "dom_compression",
        root / "code_store_variations",
        root / "BCL",
        root / "gui_engine",
        root / "Smart_system_seach",
        root / "Sql_Schema_Config",
    ]

    py_files = []
    for d in search_dirs:
        if d.exists():
            py_files.extend(d.rglob("*.py"))

    print(f"[Local] Found {len(py_files)} Python files in search dirs")

    for pyfile in py_files:
        try:
            content = pyfile.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content)
        except Exception:
            continue

        # Check if file is graph-related (filename or content)
        file_is_graph = is_graph_related(pyfile.name) or any(is_graph_related(line) for line in content.split("\n")[:50])
        if not file_is_graph:
            continue

        lines = content.split("\n")

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name
                class_is_graph = is_graph_related(class_name)

                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_name = item.name
                        method_is_graph = is_graph_related(method_name)

                        # Include if class OR method is graph-related
                        if class_is_graph or method_is_graph or file_is_graph:
                            # Extract method body
                            start_line = item.lineno
                            end_line = item.end_lineno if hasattr(item, "end_lineno") else start_line
                            body = "\n".join(lines[start_line - 1:end_line])

                            # Build signature
                            args = [a.arg for a in item.args.args]
                            if item.args.vararg:
                                args.append("*" + item.args.vararg.arg)
                            if item.args.kwarg:
                                args.append("**" + item.args.kwarg.arg)
                            signature = f"def {method_name}({', '.join(args)})"

                            hash_input = f"{class_name}.{method_name}.{pyfile}.{start_line}"
                            unit_hash = hashlib.sha256(hash_input.encode()).hexdigest()

                            is_dunder = 1 if method_name.startswith("__") and method_name.endswith("__") else 0

                            units.append({
                                "unit_hash": unit_hash,
                                "class_name": class_name,
                                "method_name": method_name,
                                "signature": signature,
                                "body": body,
                                "file_path": str(pyfile),
                                "line_start": start_line,
                                "line_end": end_line,
                                "source": "local",
                                "domain": None,
                                "role": None,
                                "is_dunder": is_dunder,
                            })

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Top-level functions (not in a class)
                func_name = node.name
                if is_graph_related(func_name) and file_is_graph:
                    start_line = node.lineno
                    end_line = node.end_lineno if hasattr(node, "end_lineno") else start_line
                    body = "\n".join(lines[start_line - 1:end_line])

                    args = [a.arg for a in node.args.args]
                    signature = f"def {func_name}({', '.join(args)})"

                    hash_input = f"__top__.{func_name}.{pyfile}.{start_line}"
                    unit_hash = hashlib.sha256(hash_input.encode()).hexdigest()

                    is_dunder = 1 if func_name.startswith("__") and func_name.endswith("__") else 0

                    units.append({
                        "unit_hash": unit_hash,
                        "class_name": "__top_level__",
                        "method_name": func_name,
                        "signature": signature,
                        "body": body,
                        "file_path": str(pyfile),
                        "line_start": start_line,
                        "line_end": end_line,
                        "source": "local",
                        "domain": None,
                        "role": None,
                        "is_dunder": is_dunder,
                    })

    print(f"[Local] Extracted {len(units)} computation units from local codebase")
    return units

# ─── Insert into database ─────────────────────────────────────────────────────
def insert_units(units):
    conn = mysql.connector.connect(host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, database=TARGET_DB)
    cursor = conn.cursor()

    sql = """
        INSERT IGNORE INTO computation_units
        (unit_hash, class_name, method_name, signature, body, file_path, line_start, line_end, source, domain, role, is_dunder)
        VALUES (%(unit_hash)s, %(class_name)s, %(method_name)s, %(signature)s, %(body)s, %(file_path)s, %(line_start)s, %(line_end)s, %(source)s, %(domain)s, %(role)s, %(is_dunder)s)
    """

    inserted = 0
    skipped = 0
    for u in units:
        try:
            cursor.execute(sql, u)
            inserted += 1
        except mysql.connector.IntegrityError:
            skipped += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"[DB] Inserted {inserted} units, skipped {skipped} duplicates")

# ─── Verify ───────────────────────────────────────────────────────────────────
def verify():
    conn = mysql.connector.connect(host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, database=TARGET_DB)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM computation_units")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT source, COUNT(*) FROM computation_units GROUP BY source")
    by_source = cursor.fetchall()

    cursor.execute("SELECT COUNT(DISTINCT class_name) FROM computation_units")
    unique_classes = cursor.fetchone()[0]

    cursor.execute("SELECT class_name, COUNT(*) as method_count FROM computation_units GROUP BY class_name ORDER BY method_count DESC LIMIT 20")
    top_classes = cursor.fetchall()

    cursor.close()
    conn.close()

    print(f"\n{'='*60}")
    print(f"VERIFICATION REPORT")
    print(f"{'='*60}")
    print(f"Total computation units: {total}")
    print(f"Unique classes: {unique_classes}")
    print(f"\nBy source:")
    for src, cnt in by_source:
        print(f"  {src}: {cnt} units")
    print(f"\nTop 20 classes by method count:")
    for cls, cnt in top_classes:
        print(f"  {cls}: {cnt} methods")

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("GRAPH COMPUTATION UNITS MAPPING PIPELINE")
    print("=" * 60)

    # Step 1: Create database
    print("\n[Step 1] Creating database...")
    create_database()

    # Step 2: Extract from MySQL vb_code_test
    print("\n[Step 2] Extracting from MySQL vb_code_test...")
    mysql_units = extract_from_mysql_vb_code_test()

    # Step 3: Extract from local codebase
    print("\n[Step 3] Extracting from local codebase...")
    local_units = extract_from_local_codebase()

    # Step 4: Insert all units
    print("\n[Step 4] Inserting into database...")
    all_units = mysql_units + local_units
    insert_units(all_units)

    # Step 5: Verify
    print("\n[Step 5] Verifying...")
    verify()

    print(f"\n{'='*60}")
    print(f"DONE: {len(mysql_units)} MySQL + {len(local_units)} local = {len(all_units)} total units")
    print(f"Database: {TARGET_DB}")
    print(f"Table: computation_units")
    print(f"Schema: 1 method = 1 row = 1 computation unit → belongs to 1 class")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
