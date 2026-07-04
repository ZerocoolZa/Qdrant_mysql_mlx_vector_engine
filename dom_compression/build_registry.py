#!/usr/bin/env python3
"""
Build registry tables + triggers on v20_hybrid_best.db
Approach E — tested and proven in test_registry_schema.py

Steps:
1. Create domain_registry, type_registry, category_registry
2. Populate from existing data
3. Create validation triggers
4. Test: bad insert should FAIL, valid insert should PASS
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/code_store_variations/v20_hybrid_best.db"

def Run():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    results = []
    
    # ═══ STEP 1: Create registry tables ═══
    print("=" * 70)
    print("STEP 1: Creating registry tables")
    print("=" * 70)
    
    # domain_registry
    c.execute("""CREATE TABLE IF NOT EXISTS domain_registry (
        domain_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    print("  [OK] domain_registry created")
    
    # type_registry
    c.execute("""CREATE TABLE IF NOT EXISTS type_registry (
        type_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        applies_to TEXT)""")
    print("  [OK] type_registry created")
    
    # category_registry
    c.execute("""CREATE TABLE IF NOT EXISTS category_registry (
        category_id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(domain, name))""")
    print("  [OK] category_registry created")
    
    conn.commit()
    
    # ═══ STEP 2: Populate from existing data ═══
    print("\n" + "=" * 70)
    print("STEP 2: Populating registries from existing data")
    print("=" * 70)
    
    # Domains from classes
    c.execute("SELECT DISTINCT domain FROM classes WHERE domain IS NOT NULL AND domain != ''")
    class_domains = [r[0] for r in c.fetchall()]
    for d in class_domains:
        c.execute("INSERT OR IGNORE INTO domain_registry (name, description) VALUES (?, ?)",
                  (d, "Auto-imported from classes table"))
    print("  [OK] " + str(len(class_domains)) + " domains from classes")
    
    # Domains from decision_nodes
    c.execute("SELECT DISTINCT domain FROM decision_nodes WHERE domain IS NOT NULL AND domain != ''")
    node_domains = [r[0] for r in c.fetchall()]
    new_from_nodes = 0
    for d in node_domains:
        c.execute("INSERT OR IGNORE INTO domain_registry (name, description) VALUES (?, ?)",
                  (d, "Auto-imported from decision_nodes table"))
        if c.rowcount > 0:
            new_from_nodes += 1
    print("  [OK] " + str(len(node_domains)) + " domains from decision_nodes (" + str(new_from_nodes) + " new)")
    
    # Types from decision_nodes
    c.execute("SELECT DISTINCT node_type FROM decision_nodes WHERE node_type IS NOT NULL AND node_type != ''")
    node_types = [r[0] for r in c.fetchall()]
    for t in node_types:
        c.execute("INSERT OR IGNORE INTO type_registry (name, description, applies_to) VALUES (?, ?, ?)",
                  (t, "Auto-imported from decision_nodes", "decision_nodes"))
    print("  [OK] " + str(len(node_types)) + " node types from decision_nodes")
    
    # Also add types for classes and methods
    for t in ['class', 'method', 'computational_unit', 'plan', 'orchestration', 'bcl_instruction']:
        c.execute("INSERT OR IGNORE INTO type_registry (name, description, applies_to) VALUES (?, ?, ?)",
                  (t, "Code entity type", "classes,methods,computational_units,plans,orchestration,bcl_instructions"))
    print("  [OK] 6 code entity types added (class, method, computational_unit, plan, orchestration, bcl_instruction)")
    
    # Categories from decision_nodes
    c.execute("""SELECT DISTINCT domain, category FROM decision_nodes 
                 WHERE category IS NOT NULL AND category != '' AND domain IS NOT NULL""")
    cats = c.fetchall()
    for domain, cat in cats:
        c.execute("INSERT OR IGNORE INTO category_registry (domain, name, description) VALUES (?, ?, ?)",
                  (domain, cat, "Auto-imported from decision_nodes"))
    print("  [OK] " + str(len(cats)) + " categories from decision_nodes")
    
    # Add categories for graph_engine (the ones that should exist)
    graph_engine_cats = [
        ('graph_engine', 'howto', 'How-to guides and instructions'),
        ('graph_engine', 'rules', 'Rules and constraints'),
        ('graph_engine', 'verify', 'Verification steps'),
        ('graph_engine', 'error', 'Error handling'),
        ('graph_engine', 'pipeline', 'Pipeline definitions'),
        ('graph_engine', 'permissions', 'Permission requirements'),
        ('graph_engine', 'when', 'When to use'),
        ('graph_engine', 'why', 'Why this exists'),
        ('graph_engine', 'alternatives', 'Alternative approaches'),
        ('graph_engine', 'codegraph', 'Code graph structure'),
    ]
    for domain, cat, desc in graph_engine_cats:
        c.execute("INSERT OR IGNORE INTO category_registry (domain, name, description) VALUES (?, ?, ?)",
                  (domain, cat, desc))
    print("  [OK] 10 graph_engine categories added")
    
    conn.commit()
    
    # Verify counts
    c.execute("SELECT COUNT(*) FROM domain_registry")
    domain_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM type_registry")
    type_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM category_registry")
    cat_count = c.fetchone()[0]
    
    print("\n  REGISTRY COUNTS:")
    print("    domain_registry:   " + str(domain_count) + " entries")
    print("    type_registry:     " + str(type_count) + " entries")
    print("    category_registry: " + str(cat_count) + " entries")
    
    # ═══ STEP 3: Create validation triggers ═══
    print("\n" + "=" * 70)
    print("STEP 3: Creating validation triggers")
    print("=" * 70)
    
    # Trigger: validate domain on decision_nodes
    c.execute("""CREATE TRIGGER IF NOT EXISTS validate_node_domain
        BEFORE INSERT ON decision_nodes
        FOR EACH ROW
        WHEN NEW.domain IS NOT NULL AND NEW.domain != ''
        BEGIN
            SELECT CASE
                WHEN NOT EXISTS (SELECT 1 FROM domain_registry WHERE name = NEW.domain)
                THEN RAISE(ABORT, 'Invalid domain: ' || NEW.domain || '. Query domain_registry for valid values.')
            END;
        END""")
    print("  [OK] validate_node_domain trigger created")
    
    # Trigger: validate node_type on decision_nodes
    c.execute("""CREATE TRIGGER IF NOT EXISTS validate_node_type
        BEFORE INSERT ON decision_nodes
        FOR EACH ROW
        WHEN NEW.node_type IS NOT NULL AND NEW.node_type != ''
        BEGIN
            SELECT CASE
                WHEN NOT EXISTS (SELECT 1 FROM type_registry WHERE name = NEW.node_type)
                THEN RAISE(ABORT, 'Invalid node_type: ' || NEW.node_type || '. Query type_registry for valid values.')
            END;
        END""")
    print("  [OK] validate_node_type trigger created")
    
    # Trigger: validate category on decision_nodes
    c.execute("""CREATE TRIGGER IF NOT EXISTS validate_node_category
        BEFORE INSERT ON decision_nodes
        FOR EACH ROW
        WHEN NEW.category IS NOT NULL AND NEW.category != ''
        BEGIN
            SELECT CASE
                WHEN NOT EXISTS (SELECT 1 FROM category_registry WHERE name = NEW.category AND domain = NEW.domain)
                THEN RAISE(ABORT, 'Invalid category: ' || NEW.category || ' for domain: ' || NEW.domain || '. Query category_registry for valid values.')
            END;
        END""")
    print("  [OK] validate_node_category trigger created")
    
    # Trigger: validate domain on classes
    c.execute("""CREATE TRIGGER IF NOT EXISTS validate_class_domain
        BEFORE INSERT ON classes
        FOR EACH ROW
        WHEN NEW.domain IS NOT NULL AND NEW.domain != ''
        BEGIN
            SELECT CASE
                WHEN NOT EXISTS (SELECT 1 FROM domain_registry WHERE name = NEW.domain)
                THEN RAISE(ABORT, 'Invalid domain: ' || NEW.domain || '. Query domain_registry for valid values.')
            END;
        END""")
    print("  [OK] validate_class_domain trigger created")
    
    # Trigger: validate domain on methods (via class domain)
    # Methods don't have domain directly, but we validate on classes update too
    c.execute("""CREATE TRIGGER IF NOT EXISTS validate_class_domain_update
        BEFORE UPDATE ON classes
        FOR EACH ROW
        WHEN NEW.domain IS NOT NULL AND NEW.domain != ''
        BEGIN
            SELECT CASE
                WHEN NOT EXISTS (SELECT 1 FROM domain_registry WHERE name = NEW.domain)
                THEN RAISE(ABORT, 'Invalid domain: ' || NEW.domain || '. Query domain_registry for valid values.')
            END;
        END""")
    print("  [OK] validate_class_domain_update trigger created")
    
    conn.commit()
    
    # ═══ STEP 4: Test — bad inserts should FAIL ═══
    print("\n" + "=" * 70)
    print("STEP 4: Testing — bad inserts should FAIL")
    print("=" * 70)
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Bad domain on decision_nodes
    try:
        c.execute("""INSERT INTO decision_nodes (node_id, domain, name, node_type) 
                     VALUES (999999, 'workfow', 'TestBadDomain', 'action')""")
        print("  [FAIL] Bad domain 'workfow' was ALLOWED — should have been blocked!")
        tests_failed += 1
    except sqlite3.IntegrityError as e:
        print("  [PASS] Bad domain 'workfow' BLOCKED: " + str(e))
        tests_passed += 1
    
    # Test 2: Bad node_type on decision_nodes
    try:
        c.execute("""INSERT INTO decision_nodes (node_id, domain, name, node_type) 
                     VALUES (999998, 'workflow', 'TestBadType', 'acton')""")
        print("  [FAIL] Bad node_type 'acton' was ALLOWED — should have been blocked!")
        tests_failed += 1
    except sqlite3.IntegrityError as e:
        print("  [PASS] Bad node_type 'acton' BLOCKED: " + str(e))
        tests_passed += 1
    
    # Test 3: Bad category on decision_nodes
    try:
        c.execute("""INSERT INTO decision_nodes (node_id, domain, name, node_type, category) 
                     VALUES (999997, 'workflow', 'TestBadCat', 'action', 'nonexistent_cat')""")
        print("  [FAIL] Bad category was ALLOWED — should have been blocked!")
        tests_failed += 1
    except sqlite3.IntegrityError as e:
        print("  [PASS] Bad category BLOCKED: " + str(e))
        tests_passed += 1
    
    # Test 4: Bad domain on classes
    try:
        c.execute("""INSERT INTO classes (class_name, domain) 
                     VALUES ('TestBadClass', 'fake_domain_xyz')""")
        print("  [FAIL] Bad domain on classes was ALLOWED — should have been blocked!")
        tests_failed += 1
    except sqlite3.IntegrityError as e:
        print("  [PASS] Bad domain on classes BLOCKED: " + str(e))
        tests_passed += 1
    
    # ═══ STEP 5: Test — valid inserts should PASS ═══
    print("\n" + "=" * 70)
    print("STEP 5: Testing — valid inserts should PASS")
    print("=" * 70)
    
    # Test 5: Valid domain on decision_nodes
    try:
        c.execute("""INSERT INTO decision_nodes (node_id, domain, name, node_type, category) 
                     VALUES (999996, 'workflow', 'TestValidNode', 'action', 'prj')""")
        print("  [PASS] Valid domain 'workflow' + type 'action' + category 'prj' ALLOWED")
        tests_passed += 1
        # Clean up
        c.execute("DELETE FROM decision_nodes WHERE node_id = 999996")
    except sqlite3.IntegrityError as e:
        print("  [FAIL] Valid insert was BLOCKED: " + str(e))
        tests_failed += 1
    
    # Test 6: NULL domain should be allowed (unclassified)
    try:
        c.execute("""INSERT INTO decision_nodes (node_id, domain, name, node_type) 
                     VALUES (999995, NULL, 'TestNullDomain', 'action')""")
        print("  [PASS] NULL domain ALLOWED (unclassified nodes OK)")
        tests_passed += 1
        c.execute("DELETE FROM decision_nodes WHERE node_id = 999995")
    except sqlite3.IntegrityError as e:
        print("  [FAIL] NULL domain was BLOCKED: " + str(e))
        tests_failed += 1
    
    # Test 7: Valid domain on classes
    try:
        # Get a valid domain
        c.execute("SELECT name FROM domain_registry LIMIT 1")
        valid_domain = c.fetchone()[0]
        c.execute("""INSERT INTO classes (class_name, domain) 
                     VALUES ('TestValidClass', ?)""", (valid_domain,))
        print("  [PASS] Valid domain '" + valid_domain + "' on classes ALLOWED")
        tests_passed += 1
        # Clean up
        c.execute("DELETE FROM classes WHERE class_name = 'TestValidClass'")
    except sqlite3.IntegrityError as e:
        print("  [FAIL] Valid class insert was BLOCKED: " + str(e))
        tests_failed += 1
    
    # Test 8: Try adding a new domain (register first, then use)
    try:
        c.execute("INSERT INTO domain_registry (name, description) VALUES ('test_new_domain', 'Test domain')")
        c.execute("""INSERT INTO decision_nodes (node_id, domain, name, node_type) 
                     VALUES (999994, 'test_new_domain', 'TestNewDomainNode', 'action')""")
        print("  [PASS] New domain registered then used — ALLOWED")
        tests_passed += 1
        # Clean up
        c.execute("DELETE FROM decision_nodes WHERE node_id = 999994")
        c.execute("DELETE FROM domain_registry WHERE name = 'test_new_domain'")
    except sqlite3.IntegrityError as e:
        print("  [FAIL] New domain flow failed: " + str(e))
        tests_failed += 1
    
    conn.commit()
    
    # ═══ SUMMARY ═══
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("  Registry tables created: 3")
    print("    domain_registry:   " + str(domain_count) + " domains")
    print("    type_registry:     " + str(type_count) + " types")
    print("    category_registry: " + str(cat_count) + " categories")
    print("  Triggers created: 5")
    print("  Tests passed: " + str(tests_passed))
    print("  Tests failed: " + str(tests_failed))
    
    if tests_failed == 0:
        print("\n  VERDICT: ALL TESTS PASSED — gate is working")
    else:
        print("\n  VERDICT: " + str(tests_failed) + " tests FAILED — gate has issues")
    
    # Show sample registry contents
    print("\n  SAMPLE DOMAINS (first 10):")
    c.execute("SELECT name FROM domain_registry ORDER BY name LIMIT 10")
    for r in c.fetchall():
        print("    " + r[0])
    
    print("\n  ALL TYPES:")
    c.execute("SELECT name, applies_to FROM type_registry ORDER BY name")
    for r in c.fetchall():
        print("    " + r[0] + " → " + str(r[1]))
    
    print("\n  CATEGORIES BY DOMAIN:")
    c.execute("SELECT domain, name FROM category_registry ORDER BY domain, name")
    current_domain = ""
    for r in c.fetchall():
        if r[0] != current_domain:
            current_domain = r[0]
            print("    " + current_domain + ":")
        print("      " + r[1])
    
    conn.close()
    return (1, {"tests_passed": tests_passed, "tests_failed": tests_failed}, None)


if __name__ == "__main__":
    ok, data, err = Run()
    if err:
        print("ERROR: " + str(err))
        exit(1)
