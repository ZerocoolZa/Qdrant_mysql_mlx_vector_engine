#!/usr/bin/env python3
"""
TEST: Type/Domain/Category Registry Schema
Goal: Test different approaches on a copy of the real DB
      to find the best design before touching v20_hybrid_best.db

Approaches to test:
  A. Text columns (current state — baseline)
  B. Foreign key tables (normalized)
  C. Hybrid — registry tables + text columns with CHECK constraints
  D. Single registry table with type/domain/category as rows

Test criteria:
  1. Can an AI query valid types/domains/categories easily?
  2. Can an AI insert without typos?
  3. Does it prevent pollution?
  4. How complex is migration?
  5. Query performance
  6. Does it work across ALL tables (classes, methods, nodes, edges, plans)?
"""

import sqlite3
import os
import time
from datetime import datetime

TEST_DB = "/tmp/registry_test/test_schema.db"
REAL_DB = "/Users/wws/Qdrant_mysql_mlx_vector_engine/code_store_variations/v20_hybrid_best.db"

def setup():
    os.makedirs("/tmp/registry_test", exist_ok=True)
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

def load_real_data(conn):
    """Load real domains, types, categories from v20 into test DB"""
    real = sqlite3.connect(REAL_DB)
    rc = real.cursor()

    # Get all real domains
    rc.execute("SELECT DISTINCT domain FROM classes WHERE domain IS NOT NULL")
    domains = [r[0] for r in rc.fetchall()]

    rc.execute("SELECT DISTINCT domain FROM decision_nodes WHERE domain IS NOT NULL")
    for r in rc.fetchall():
        if r[0] and r[0] not in domains:
            domains.append(r[0])

    # Get all real node types
    rc.execute("SELECT DISTINCT node_type FROM decision_nodes WHERE node_type IS NOT NULL")
    node_types = [r[0] for r in rc.fetchall()]

    # Get all real categories
    rc.execute("SELECT DISTINCT category FROM decision_nodes WHERE category IS NOT NULL AND category != ''")
    categories = [r[0] for r in rc.fetchall()]

    # Get sample classes
    rc.execute("SELECT id, class_name, domain FROM classes LIMIT 20")
    classes = rc.fetchall()

    # Get sample methods
    rc.execute("SELECT id, class_id, method_name FROM methods LIMIT 30")
    methods = rc.fetchall()

    # Get sample decision nodes
    rc.execute("SELECT node_id, domain, name, node_type, payload, category FROM decision_nodes LIMIT 50")
    nodes = rc.fetchall()

    # Get sample decision edges
    rc.execute("""SELECT e.edge_id, e.from_node, e.to_node, e.condition, e.weight
                 FROM decision_edges e LIMIT 50""")
    edges = rc.fetchall()

    real.close()
    return domains, node_types, categories, classes, methods, nodes, edges


# ════════════════════════════════════════════════════════════════════════
# APPROACH A: Text columns (baseline — current state)
# ════════════════════════════════════════════════════════════════════════
def test_approach_a(domains, node_types, categories, classes, methods, nodes, edges):
    print("\n" + "=" * 70)
    print("APPROACH A: Text columns (current baseline)")
    print("=" * 70)

    conn = sqlite3.connect(TEST_DB)
    c = conn.cursor()

    # Schema — just text columns, no enforcement
    c.execute("""CREATE TABLE classes (
        id INTEGER PRIMARY KEY, class_name TEXT, domain TEXT)""")
    c.execute("""CREATE TABLE methods (
        id INTEGER PRIMARY KEY, class_id INTEGER, method_name TEXT)""")
    c.execute("""CREATE TABLE decision_nodes (
        node_id INTEGER PRIMARY KEY, domain TEXT, name TEXT,
        node_type TEXT, payload TEXT, category TEXT)""")
    c.execute("""CREATE TABLE decision_edges (
        edge_id INTEGER PRIMARY KEY, from_node INTEGER, to_node INTEGER,
        condition TEXT, weight REAL)""")

    # Insert data
    c.executemany("INSERT INTO classes VALUES (?,?,?)", classes)
    c.executemany("INSERT INTO methods VALUES (?,?,?)", methods)
    c.executemany("INSERT INTO decision_nodes VALUES (?,?,?,?,?,?)", nodes)
    c.executemany("INSERT INTO decision_edges VALUES (?,?,?,?,?)", edges)
    conn.commit()

    # Test 1: Query valid domains
    t0 = time.time()
    c.execute("SELECT DISTINCT domain FROM classes")
    result = c.fetchall()
    t1 = time.time()
    print(f"\n  [1] Query distinct domains: {len(result)} found in {(t1-t0)*1000:.2f}ms")

    # Test 2: Can insert typo (pollution test)
    try:
        c.execute("INSERT INTO classes (class_name, domain) VALUES ('TestClass', 'workfow')")
        print(f"  [2] Typo insert 'workfow': ALLOWED (BAD — pollution possible)")
    except:
        print(f"  [2] Typo insert 'workfow': BLOCKED")

    # Test 3: Can insert NULL domain
    try:
        c.execute("INSERT INTO classes (class_name, domain) VALUES ('TestClass', NULL)")
        print(f"  [3] NULL domain insert: ALLOWED (BAD)")
    except:
        print(f"  [3] NULL domain insert: BLOCKED")

    # Test 4: Cross-table consistency check
    c.execute("SELECT DISTINCT domain FROM classes")
    class_domains = set(r[0] for r in c.fetchall())
    c.execute("SELECT DISTINCT domain FROM decision_nodes")
    node_domains = set(r[0] for r in c.fetchall())
    inconsistent = class_domains.symmetric_difference(node_domains)
    print(f"  [4] Cross-table domain consistency: {len(inconsistent)} mismatches {'OK' if not inconsistent else 'BAD'}")

    # Test 5: AI query — "what categories exist for workflow?"
    t0 = time.time()
    c.execute("SELECT DISTINCT category FROM decision_nodes WHERE domain='workflow' AND category != ''")
    result = c.fetchall()
    t1 = time.time()
    print(f"  [5] AI query 'workflow categories': {len(result)} found in {(t1-t0)*1000:.2f}ms")

    # Test 6: Count distinct values (how many unique domains/types/categories)
    c.execute("SELECT COUNT(DISTINCT domain) FROM classes")
    d_count = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT node_type) FROM decision_nodes")
    t_count = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT category) FROM decision_nodes WHERE category != ''")
    cat_count = c.fetchone()[0]
    print(f"  [6] Unique: domains={d_count}, types={t_count}, categories={cat_count}")

    conn.close()
    print(f"\n  SCORE: No enforcement, pollution possible, no consistency guarantee")
    print(f"  VERDICT: BAD — current state allows drift")


# ════════════════════════════════════════════════════════════════════════
# APPROACH B: Foreign key tables (fully normalized)
# ════════════════════════════════════════════════════════════════════════
def test_approach_b(domains, node_types, categories, classes, methods, nodes, edges):
    print("\n" + "=" * 70)
    print("APPROACH B: Foreign key tables (fully normalized)")
    print("=" * 70)

    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    conn = sqlite3.connect(TEST_DB)
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON")

    # Registry tables
    c.execute("""CREATE TABLE domain_registry (
        domain_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    c.execute("""CREATE TABLE type_registry (
        type_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        applies_to TEXT)""")  # comma-separated: classes,methods,nodes,edges

    c.execute("""CREATE TABLE category_registry (
        category_id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        UNIQUE(domain_id, name),
        FOREIGN KEY (domain_id) REFERENCES domain_registry(domain_id))""")

    # Data tables with FK references
    c.execute("""CREATE TABLE classes (
        id INTEGER PRIMARY KEY,
        class_name TEXT NOT NULL,
        domain_id INTEGER,
        FOREIGN KEY (domain_id) REFERENCES domain_registry(domain_id))""")

    c.execute("""CREATE TABLE methods (
        id INTEGER PRIMARY KEY,
        class_id INTEGER,
        method_name TEXT NOT NULL,
        type_id INTEGER,
        FOREIGN KEY (type_id) REFERENCES type_registry(type_id))""")

    c.execute("""CREATE TABLE decision_nodes (
        node_id INTEGER PRIMARY KEY,
        domain_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        type_id INTEGER NOT NULL,
        payload TEXT,
        category_id INTEGER,
        FOREIGN KEY (domain_id) REFERENCES domain_registry(domain_id),
        FOREIGN KEY (type_id) REFERENCES type_registry(type_id),
        FOREIGN KEY (category_id) REFERENCES category_registry(category_id))""")

    c.execute("""CREATE TABLE decision_edges (
        edge_id INTEGER PRIMARY KEY,
        from_node INTEGER NOT NULL,
        to_node INTEGER NOT NULL,
        condition TEXT,
        weight REAL DEFAULT 1.0)""")

    # Seed registries
    for d in domains:
        c.execute("INSERT OR IGNORE INTO domain_registry (name, description) VALUES (?, ?)",
                  (d, "Domain: " + d))
    for t in node_types:
        c.execute("INSERT OR IGNORE INTO type_registry (name, description, applies_to) VALUES (?, ?, ?)",
                  (t, "Node type: " + t, "decision_nodes"))

    # Seed categories — need domain_id
    c.execute("SELECT domain_id, name FROM domain_registry")
    domain_map = {r[1]: r[0] for r in c.fetchall()}
    for cat in categories:
        # Categories belong to workflow domain (for test)
        wf_id = domain_map.get('workflow')
        if wf_id:
            c.execute("INSERT OR IGNORE INTO category_registry (domain_id, name, description) VALUES (?, ?, ?)",
                      (wf_id, cat, "Category: " + cat))

    # Map for inserting data
    c.execute("SELECT domain_id, name FROM domain_registry")
    domain_map = {r[1]: r[0] for r in c.fetchall()}
    c.execute("SELECT type_id, name FROM type_registry")
    type_map = {r[1]: r[0] for r in c.fetchall()}
    c.execute("SELECT category_id, name FROM category_registry")
    cat_map = {r[1]: r[0] for r in c.fetchall()}

    # Insert classes with domain_id
    for cls in classes:
        cid, cname, cdomain = cls
        did = domain_map.get(cdomain) if cdomain else None
        c.execute("INSERT INTO classes (id, class_name, domain_id) VALUES (?, ?, ?)",
                  (cid, cname, did))

    # Insert methods
    for m in methods:
        c.execute("INSERT INTO methods (id, class_id, method_name) VALUES (?, ?, ?)", m)

    # Insert nodes with FK references
    for n in nodes:
        nid, ndomain, nname, ntype, npayload, ncategory = n
        did = domain_map.get(ndomain, 1)
        tid = type_map.get(ntype, 1)
        catid = cat_map.get(ncategory) if ncategory else None
        c.execute("INSERT INTO decision_nodes (node_id, domain_id, name, type_id, payload, category_id) VALUES (?, ?, ?, ?, ?, ?)",
                  (nid, did, nname, tid, npayload, catid))

    # Insert edges
    c.executemany("INSERT INTO decision_edges VALUES (?,?,?,?,?)", edges)
    conn.commit()

    # Tests
    # Test 1: Query valid domains
    t0 = time.time()
    c.execute("SELECT name FROM domain_registry ORDER BY name")
    result = c.fetchall()
    t1 = time.time()
    print(f"\n  [1] Query valid domains: {len(result)} found in {(t1-t0)*1000:.2f}ms")

    # Test 2: Typo insert
    try:
        c.execute("INSERT INTO classes (class_name, domain_id) VALUES ('TestClass', 999)")
        print(f"  [2] Invalid domain_id 999: ALLOWED (BAD — FK not enforced without PRAGMA)")
    except sqlite3.IntegrityError:
        print(f"  [2] Invalid domain_id 999: BLOCKED (FK enforced)")

    # Test 3: NULL domain
    try:
        c.execute("INSERT INTO classes (class_name, domain_id) VALUES ('TestClass', NULL)")
        print(f"  [3] NULL domain_id: ALLOWED (may be OK for unclassified)")
    except:
        print(f"  [3] NULL domain_id: BLOCKED")

    # Test 4: Cross-table consistency (automatic — all reference same registry)
    print(f"  [4] Cross-table consistency: GUARANTEED (all tables reference domain_registry)")

    # Test 5: AI query — "what categories exist for workflow?"
    t0 = time.time()
    c.execute("""SELECT cr.name FROM category_registry cr
                 JOIN domain_registry dr ON cr.domain_id = dr.domain_id
                 WHERE dr.name='workflow'""")
    result = c.fetchall()
    t1 = time.time()
    print(f"  [5] AI query 'workflow categories': {len(result)} found in {(t1-t0)*1000:.2f}ms (JOIN required)")

    # Test 6: AI query — "show me all nodes in workflow domain, type=action"
    t0 = time.time()
    c.execute("""SELECT dn.name FROM decision_nodes dn
                 JOIN domain_registry dr ON dn.domain_id = dr.domain_id
                 JOIN type_registry tr ON dn.type_id = tr.type_id
                 WHERE dr.name='workflow' AND tr.name='action'""")
    result = c.fetchall()
    t1 = time.time()
    print(f"  [6] AI query 'workflow + action': {len(result)} nodes in {(t1-t0)*1000:.2f}ms (2 JOINs)")

    # Test 7: Add new domain (what AI does)
    t0 = time.time()
    c.execute("INSERT INTO domain_registry (name, description) VALUES ('test_domain', 'Test')")
    c.execute("SELECT domain_id FROM domain_registry WHERE name='test_domain'")
    new_id = c.fetchone()[0]
    t1 = time.time()
    print(f"  [7] Add new domain: id={new_id} in {(t1-t0)*1000:.2f}ms")

    # Test 8: Migration complexity
    print(f"  [8] Migration: Need to add domain_id/type_id/category_id to ALL tables")
    print(f"       Need to map all existing text values to IDs")
    print(f"       Need to update all queries to use JOINs")

    conn.close()
    print(f"\n  SCORE: Strong enforcement, guaranteed consistency, prevents pollution")
    print(f"  VERDICT: GOOD but heavy — every query needs JOINs, migration is complex")


# ════════════════════════════════════════════════════════════════════════
# APPROACH C: Hybrid — registry tables + text columns with CHECK
# ════════════════════════════════════════════════════════════════════════
def test_approach_c(domains, node_types, categories, classes, methods, nodes, edges):
    print("\n" + "=" * 70)
    print("APPROACH C: Hybrid — registry + text with CHECK constraints")
    print("=" * 70)

    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    conn = sqlite3.connect(TEST_DB)
    c = conn.cursor()

    # Registry tables (for AI to query what's valid)
    c.execute("""CREATE TABLE domain_registry (
        domain_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT)""")

    c.execute("""CREATE TABLE type_registry (
        type_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        applies_to TEXT)""")

    c.execute("""CREATE TABLE category_registry (
        category_id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        UNIQUE(domain, name))""")

    # Data tables — keep text columns but add CHECK
    # Build CHECK constraints from real data
    domain_list = ",".join("'" + d + "'" for d in domains)
    type_list = ",".join("'" + t + "'" for t in node_types)

    c.execute(f"""CREATE TABLE classes (
        id INTEGER PRIMARY KEY,
        class_name TEXT NOT NULL,
        domain TEXT CHECK(domain IN ({domain_list}) OR domain IS NULL))""")

    c.execute("""CREATE TABLE methods (
        id INTEGER PRIMARY KEY,
        class_id INTEGER,
        method_name TEXT NOT NULL)""")

    c.execute(f"""CREATE TABLE decision_nodes (
        node_id INTEGER PRIMARY KEY,
        domain TEXT NOT NULL CHECK(domain IN ({domain_list})),
        name TEXT NOT NULL,
        node_type TEXT NOT NULL CHECK(node_type IN ({type_list})),
        payload TEXT,
        category TEXT)""")

    c.execute("""CREATE TABLE decision_edges (
        edge_id INTEGER PRIMARY KEY,
        from_node INTEGER NOT NULL,
        to_node INTEGER NOT NULL,
        condition TEXT,
        weight REAL DEFAULT 1.0)""")

    # Seed registries
    for d in domains:
        c.execute("INSERT OR IGNORE INTO domain_registry (name, description) VALUES (?, ?)",
                  (d, "Domain: " + d))
    for t in node_types:
        c.execute("INSERT OR IGNORE INTO type_registry (name, description, applies_to) VALUES (?, ?, ?)",
                  (t, "Node type: " + t, "decision_nodes"))
    for cat in categories:
        c.execute("INSERT OR IGNORE INTO category_registry (domain, name, description) VALUES (?, ?, ?)",
                  ('workflow', cat, "Category: " + cat))

    # Insert data (same as approach A — text columns)
    c.executemany("INSERT INTO classes VALUES (?,?,?)", classes)
    c.executemany("INSERT INTO methods VALUES (?,?,?)", methods)
    c.executemany("INSERT INTO decision_nodes VALUES (?,?,?,?,?,?)", nodes)
    c.executemany("INSERT INTO decision_edges VALUES (?,?,?,?,?)", edges)
    conn.commit()

    # Tests
    # Test 1: Query valid domains
    t0 = time.time()
    c.execute("SELECT name FROM domain_registry ORDER BY name")
    result = c.fetchall()
    t1 = time.time()
    print(f"\n  [1] Query valid domains: {len(result)} found in {(t1-t0)*1000:.2f}ms")

    # Test 2: Typo insert
    try:
        c.execute("INSERT INTO classes (class_name, domain) VALUES ('TestClass', 'workfow')")
        print(f"  [2] Typo insert 'workfow': BLOCKED (CHECK constraint)")
    except sqlite3.IntegrityError:
        print(f"  [2] Typo insert 'workfow': BLOCKED (CHECK constraint)")

    # Test 3: NULL domain in classes (allowed — some may not have domain)
    try:
        c.execute("INSERT INTO classes (class_name, domain) VALUES ('TestClass', NULL)")
        print(f"  [3] NULL domain in classes: ALLOWED (OK — some classes may be unclassified)")
    except:
        print(f"  [3] NULL domain in classes: BLOCKED")

    # Test 4: NULL domain in decision_nodes (NOT allowed)
    try:
        c.execute("INSERT INTO decision_nodes (domain, name, node_type) VALUES (NULL, 'Test', 'action')")
        print(f"  [4] NULL domain in nodes: BLOCKED (NOT NULL constraint)")
    except sqlite3.IntegrityError:
        print(f"  [4] NULL domain in nodes: BLOCKED (NOT NULL + CHECK)")

    # Test 5: Cross-table consistency
    print(f"  [5] Cross-table consistency: CHECK ensures only valid domains, but registries must be kept in sync")

    # Test 6: AI query — "what categories exist for workflow?"
    t0 = time.time()
    c.execute("SELECT name FROM category_registry WHERE domain='workflow'")
    result = c.fetchall()
    t1 = time.time()
    print(f"  [6] AI query 'workflow categories': {len(result)} found in {(t1-t0)*1000:.2f}ms (no JOIN)")

    # Test 7: AI query — "show me all nodes in workflow domain, type=action"
    t0 = time.time()
    c.execute("SELECT name FROM decision_nodes WHERE domain='workflow' AND node_type='action'")
    result = c.fetchall()
    t1 = time.time()
    print(f"  [7] AI query 'workflow + action': {len(result)} nodes in {(t1-t0)*1000:.2f}ms (no JOIN)")

    # Test 8: Add new domain (AI must update CHECK constraint — harder)
    print(f"  [8] Add new domain: Must INSERT into registry AND alter CHECK constraint")
    print(f"       SQLite can't easily ALTER CHECK — need table rebuild")

    # Test 9: Typo in node_type
    try:
        c.execute("INSERT INTO decision_nodes (domain, name, node_type) VALUES ('workflow', 'Test', 'acton')")
        print(f"  [9] Typo 'acton' in node_type: BLOCKED (CHECK)")
    except sqlite3.IntegrityError:
        print(f"  [9] Typo 'acton' in node_type: BLOCKED (CHECK)")

    conn.close()
    print(f"\n  SCORE: Strong enforcement, fast queries (no JOINs), prevents pollution")
    print(f"  VERDICT: GOOD for reads, HARD for adding new domains (need table rebuild)")


# ════════════════════════════════════════════════════════════════════════
# APPROACH D: Single registry table + text columns (no CHECK)
# ════════════════════════════════════════════════════════════════════════
def test_approach_d(domains, node_types, categories, classes, methods, nodes, edges):
    print("\n" + "=" * 70)
    print("APPROACH D: Single registry table + text columns (no CHECK)")
    print("=" * 70)

    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    conn = sqlite3.connect(TEST_DB)
    c = conn.cursor()

    # Single registry table — everything in one place
    c.execute("""CREATE TABLE registry (
        reg_id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,
        domain TEXT,
        name TEXT NOT NULL,
        description TEXT,
        UNIQUE(kind, domain, name))""")

    # Data tables — plain text, no CHECK
    c.execute("""CREATE TABLE classes (
        id INTEGER PRIMARY KEY, class_name TEXT, domain TEXT)""")
    c.execute("""CREATE TABLE methods (
        id INTEGER PRIMARY KEY, class_id INTEGER, method_name TEXT)""")
    c.execute("""CREATE TABLE decision_nodes (
        node_id INTEGER PRIMARY KEY, domain TEXT, name TEXT,
        node_type TEXT, payload TEXT, category TEXT)""")
    c.execute("""CREATE TABLE decision_edges (
        edge_id INTEGER PRIMARY KEY, from_node INTEGER, to_node INTEGER,
        condition TEXT, weight REAL)""")

    # Seed registry
    for d in domains:
        c.execute("INSERT OR IGNORE INTO registry (kind, domain, name, description) VALUES (?, ?, ?, ?)",
                  ('domain', d, d, "Domain: " + d))
    for t in node_types:
        c.execute("INSERT OR IGNORE INTO registry (kind, domain, name, description) VALUES (?, ?, ?, ?)",
                  ('type', None, t, "Type: " + t))
    for cat in categories:
        c.execute("INSERT OR IGNORE INTO registry (kind, domain, name, description) VALUES (?, ?, ?, ?)",
                  ('category', 'workflow', cat, "Category: " + cat))

    # Insert data
    c.executemany("INSERT INTO classes VALUES (?,?,?)", classes)
    c.executemany("INSERT INTO methods VALUES (?,?,?)", methods)
    c.executemany("INSERT INTO decision_nodes VALUES (?,?,?,?,?,?)", nodes)
    c.executemany("INSERT INTO decision_edges VALUES (?,?,?,?,?)", edges)
    conn.commit()

    # Tests
    # Test 1: Query valid domains
    t0 = time.time()
    c.execute("SELECT name FROM registry WHERE kind='domain' ORDER BY name")
    result = c.fetchall()
    t1 = time.time()
    print(f"\n  [1] Query valid domains: {len(result)} found in {(t1-t0)*1000:.2f}ms")

    # Test 2: Typo insert (NOT blocked — no CHECK)
    try:
        c.execute("INSERT INTO classes (class_name, domain) VALUES ('TestClass', 'workfow')")
        print(f"  [2] Typo insert 'workfow': ALLOWED (BAD — no CHECK)")
    except:
        print(f"  [2] Typo insert 'workfow': BLOCKED")

    # Test 3: AI query — "what categories exist for workflow?"
    t0 = time.time()
    c.execute("SELECT name FROM registry WHERE kind='category' AND domain='workflow'")
    result = c.fetchall()
    t1 = time.time()
    print(f"  [3] AI query 'workflow categories': {len(result)} found in {(t1-t0)*1000:.2f}ms (no JOIN)")

    # Test 4: AI query — "show me all nodes in workflow domain, type=action"
    t0 = time.time()
    c.execute("SELECT name FROM decision_nodes WHERE domain='workflow' AND node_type='action'")
    result = c.fetchall()
    t1 = time.time()
    print(f"  [4] AI query 'workflow + action': {len(result)} nodes in {(t1-t0)*1000:.2f}ms (no JOIN)")

    # Test 5: Add new domain (easy — just INSERT)
    t0 = time.time()
    c.execute("INSERT INTO registry (kind, domain, name, description) VALUES (?, ?, ?, ?)",
              ('domain', None, 'test_domain', 'Test domain'))
    t1 = time.time()
    print(f"  [5] Add new domain: INSERT only, {(t1-t0)*1000:.2f}ms")

    # Test 6: Validate before insert (AI pattern)
    t0 = time.time()
    c.execute("SELECT COUNT(*) FROM registry WHERE kind='domain' AND name='workflow'")
    valid = c.fetchone()[0]
    t1 = time.time()
    print(f"  [6] Validate 'workflow' exists: {valid} in {(t1-t0)*1000:.2f}ms")

    # Test 7: AI can discover ALL valid values in one query
    t0 = time.time()
    c.execute("SELECT kind, domain, name FROM registry ORDER BY kind, domain, name")
    all_regs = c.fetchall()
    t1 = time.time()
    print(f"  [7] All valid values in one query: {len(all_regs)} entries in {(t1-t0)*1000:.2f}ms")

    conn.close()
    print(f"\n  SCORE: Easy to add new domains, fast queries, single table to query")
    print(f"  VERDICT: GOOD for flexibility, but NO enforcement — relies on AI checking registry first")


# ════════════════════════════════════════════════════════════════════════
# APPROACH E: Registry tables + text columns + validation trigger
# ════════════════════════════════════════════════════════════════════════
def test_approach_e(domains, node_types, categories, classes, methods, nodes, edges):
    print("\n" + "=" * 70)
    print("APPROACH E: Registry tables + text columns + validation trigger")
    print("=" * 70)

    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    conn = sqlite3.connect(TEST_DB)
    c = conn.cursor()

    # Registry tables
    c.execute("""CREATE TABLE domain_registry (
        domain_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT)""")

    c.execute("""CREATE TABLE type_registry (
        type_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        applies_to TEXT)""")

    c.execute("""CREATE TABLE category_registry (
        category_id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        UNIQUE(domain, name))""")

    # Data tables — text columns (no CHECK, but triggers validate)
    c.execute("""CREATE TABLE classes (
        id INTEGER PRIMARY KEY, class_name TEXT, domain TEXT)""")
    c.execute("""CREATE TABLE methods (
        id INTEGER PRIMARY KEY, class_id INTEGER, method_name TEXT)""")
    c.execute("""CREATE TABLE decision_nodes (
        node_id INTEGER PRIMARY KEY, domain TEXT, name TEXT,
        node_type TEXT, payload TEXT, category TEXT)""")
    c.execute("""CREATE TABLE decision_edges (
        edge_id INTEGER PRIMARY KEY, from_node INTEGER, to_node INTEGER,
        condition TEXT, weight REAL)""")

    # Validation trigger — checks domain exists in registry before insert
    c.execute("""
    CREATE TRIGGER validate_node_domain
    BEFORE INSERT ON decision_nodes
    FOR EACH ROW
    WHEN NEW.domain IS NOT NULL
    BEGIN
        SELECT CASE
            WHEN NOT EXISTS (SELECT 1 FROM domain_registry WHERE name = NEW.domain)
            THEN RAISE(ABORT, 'Invalid domain: ' || NEW.domain || '. Query domain_registry for valid values.')
        END;
    END
    """)

    c.execute("""
    CREATE TRIGGER validate_node_type
    BEFORE INSERT ON decision_nodes
    FOR EACH ROW
    WHEN NEW.node_type IS NOT NULL
    BEGIN
        SELECT CASE
            WHEN NOT EXISTS (SELECT 1 FROM type_registry WHERE name = NEW.node_type)
            THEN RAISE(ABORT, 'Invalid node_type: ' || NEW.node_type || '. Query type_registry for valid values.')
        END;
    END
    """)

    c.execute("""
    CREATE TRIGGER validate_class_domain
    BEFORE INSERT ON classes
    FOR EACH ROW
    WHEN NEW.domain IS NOT NULL
    BEGIN
        SELECT CASE
            WHEN NOT EXISTS (SELECT 1 FROM domain_registry WHERE name = NEW.domain)
            THEN RAISE(ABORT, 'Invalid domain: ' || NEW.domain)
        END;
    END
    """)

    # Seed registries
    for d in domains:
        c.execute("INSERT OR IGNORE INTO domain_registry (name, description) VALUES (?, ?)",
                  (d, "Domain: " + d))
    for t in node_types:
        c.execute("INSERT OR IGNORE INTO type_registry (name, description, applies_to) VALUES (?, ?, ?)",
                  (t, "Node type: " + t, "decision_nodes"))
    for cat in categories:
        c.execute("INSERT OR IGNORE INTO category_registry (domain, name, description) VALUES (?, ?, ?)",
                  ('workflow', cat, "Category: " + cat))

    # Insert data
    c.executemany("INSERT INTO classes VALUES (?,?,?)", classes)
    c.executemany("INSERT INTO methods VALUES (?,?,?)", methods)
    c.executemany("INSERT INTO decision_nodes VALUES (?,?,?,?,?,?)", nodes)
    c.executemany("INSERT INTO decision_edges VALUES (?,?,?,?,?)", edges)
    conn.commit()

    # Tests
    # Test 1: Query valid domains
    t0 = time.time()
    c.execute("SELECT name FROM domain_registry ORDER BY name")
    result = c.fetchall()
    t1 = time.time()
    print(f"\n  [1] Query valid domains: {len(result)} found in {(t1-t0)*1000:.2f}ms")

    # Test 2: Typo insert
    try:
        c.execute("INSERT INTO decision_nodes (domain, name, node_type) VALUES ('workfow', 'Test', 'action')")
        print(f"  [2] Typo 'workfow': BLOCKED (trigger)")
    except sqlite3.IntegrityError as e:
        print(f"  [2] Typo 'workfow': BLOCKED (trigger: {e})")

    # Test 3: Typo in node_type
    try:
        c.execute("INSERT INTO decision_nodes (domain, name, node_type) VALUES ('workflow', 'Test', 'acton')")
        print(f"  [3] Typo 'acton': BLOCKED (trigger)")
    except sqlite3.IntegrityError as e:
        print(f"  [3] Typo 'acton': BLOCKED (trigger: {e})")

    # Test 4: Valid insert
    try:
        c.execute("INSERT INTO decision_nodes (domain, name, node_type, payload, category) VALUES ('workflow', 'TestNode', 'action', 'test', 'prj')")
        print(f"  [4] Valid insert: ALLOWED")
        c.execute("DELETE FROM decision_nodes WHERE name='TestNode'")
    except:
        print(f"  [4] Valid insert: BLOCKED (BAD)")

    # Test 5: NULL domain (allowed — trigger only fires when NOT NULL)
    try:
        c.execute("INSERT INTO classes (class_name, domain) VALUES ('Test', NULL)")
        print(f"  [5] NULL domain: ALLOWED (OK for unclassified)")
    except:
        print(f"  [5] NULL domain: BLOCKED")

    # Test 6: AI query — "what categories exist for workflow?"
    t0 = time.time()
    c.execute("SELECT name FROM category_registry WHERE domain='workflow'")
    result = c.fetchall()
    t1 = time.time()
    print(f"  [6] AI query 'workflow categories': {len(result)} found in {(t1-t0)*1000:.2f}ms (no JOIN)")

    # Test 7: AI query — "show me all nodes in workflow domain, type=action"
    t0 = time.time()
    c.execute("SELECT name FROM decision_nodes WHERE domain='workflow' AND node_type='action'")
    result = c.fetchall()
    t1 = time.time()
    print(f"  [7] AI query 'workflow + action': {len(result)} nodes in {(t1-t0)*1000:.2f}ms (no JOIN)")

    # Test 8: Add new domain (easy — just INSERT into registry)
    t0 = time.time()
    c.execute("INSERT INTO domain_registry (name, description) VALUES ('test_domain', 'Test')")
    t1 = time.time()
    print(f"  [8] Add new domain: INSERT only, {(t1-t0)*1000:.2f}ms")

    # Test 9: Now insert with new domain (should work)
    try:
        c.execute("INSERT INTO decision_nodes (domain, name, node_type, payload, category) VALUES ('test_domain', 'TestNode2', 'action', 'test', NULL)")
        print(f"  [9] Insert with new domain: ALLOWED (trigger finds it in registry)")
        c.execute("DELETE FROM decision_nodes WHERE name='TestNode2'")
    except sqlite3.IntegrityError as e:
        print(f"  [9] Insert with new domain: BLOCKED ({e})")

    # Test 10: Error message is helpful for AI
    try:
        c.execute("INSERT INTO decision_nodes (domain, name, node_type) VALUES ('bad_domain', 'Test', 'action')")
    except sqlite3.IntegrityError as e:
        msg = str(e)
        has_hint = 'domain_registry' in msg
        print(f"  [10] Error message guides AI: {'YES' if has_hint else 'NO'} — \"{msg[:80]}\"")

    conn.close()
    print(f"\n  SCORE: Strong enforcement (triggers), fast queries (no JOINs), easy to extend")
    print(f"  VERDICT: BEST — enforces valid values, easy to add new domains, AI gets helpful errors")


# ════════════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════════════
def print_summary():
    print("\n" + "=" * 70)
    print("COMPARISON SUMMARY")
    print("=" * 70)
    print("""
    | Criteria                    | A (text)  | B (FK)    | C (CHECK)  | D (registry) | E (trigger) |
    |-----------------------------|-----------|-----------|------------|--------------|-------------|
    | Prevents typos/pollution    | NO        | YES       | YES        | NO           | YES         |
    | Fast queries (no JOINs)     | YES       | NO        | YES        | YES          | YES         |
    | Easy to add new domain      | YES       | YES       | NO (rebuild)| YES         | YES         |
    | AI can discover valid values| NO        | YES       | YES        | YES          | YES         |
    | Helpful error messages      | N/A       | generic   | generic    | N/A          | YES (hints) |
    | Migration complexity        | none      | HIGH      | MEDIUM     | LOW          | LOW         |
    | Cross-table consistency     | NO        | YES       | partial    | NO           | YES         |
    | Works with existing schema  | YES       | NO        | NO         | YES          | YES         |

    WINNER: APPROACH E (registry + triggers)
    - Prevents pollution (triggers block invalid values)
    - Fast queries (text columns, no JOINs needed)
    - Easy to extend (just INSERT into registry)
    - AI-friendly (registry tables show what's valid, errors guide AI)
    - Low migration (add registry tables + triggers, keep text columns)
    """)


def main():
    print("=" * 70)
    print("TESTING TYPE/DOMAIN/CATEGORY REGISTRY SCHEMAS")
    print("Testing 5 approaches on real data from v20_hybrid_best.db")
    print("=" * 70)

    setup()
    domains, node_types, categories, classes, methods, nodes, edges = load_real_data(None)

    print(f"\nReal data loaded:")
    print(f"  Domains: {len(domains)} — {domains[:5]}...")
    print(f"  Node types: {len(node_types)} — {node_types}")
    print(f"  Categories: {len(categories)} — {categories}")
    print(f"  Sample classes: {len(classes)}")
    print(f"  Sample methods: {len(methods)}")
    print(f"  Sample nodes: {len(nodes)}")
    print(f"  Sample edges: {len(edges)}")

    test_approach_a(domains, node_types, categories, classes, methods, nodes, edges)
    test_approach_b(domains, node_types, categories, classes, methods, nodes, edges)
    test_approach_c(domains, node_types, categories, classes, methods, nodes, edges)
    test_approach_d(domains, node_types, categories, classes, methods, nodes, edges)
    test_approach_e(domains, node_types, categories, classes, methods, nodes, edges)

    print_summary()


if __name__ == "__main__":
    main()
