#!/usr/bin/env python3

#[@GHOST]{[@file<Config.py>][@domain<code_store>][@role<test_config>][@auth<cascade>][@date<2026-06-22>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<config>][@return<dict>][@no<decorators|print|hardcoded_paths>]}

"""
Gold Standard Config for CodeStore test runner.
Shared test infrastructure — check functions, counters, paths.
All 17 test_dom_*.py files merged into database-driven runner.
"""

import os
import sys
import time
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent

# ── Paths ─────────────────────────────────────────────────────
DB_PATH = str(BASE_DIR / 'code_store.db')
DOM_PATH = os.environ.get(
    "CODE_STORE_DOMAINS_DIR",
    "/Users/wws/contestsystem/VBSTYLE_MASTER _CORE/VBstyle_Python/Domains"
)
if not os.path.isdir(DOM_PATH):
    DOM_PATH = str(BASE_DIR)

# ── Test Counters ─────────────────────────────────────────────
PASS = 0
FAIL = 0
ERRORS = []


def ResetCounters():
    global PASS, FAIL, ERRORS
    PASS = 0
    FAIL = 0
    ERRORS = []


def GetResults():
    return {'pass': PASS, 'fail': FAIL, 'errors': list(ERRORS)}


# ── Check Functions ───────────────────────────────────────────
def CheckTuple3(r, label):
    global PASS, FAIL
    if not isinstance(r, tuple) or len(r) != 3:
        FAIL += 1
        ERRORS.append(label + ': NOT Tuple3')
        return False
    PASS += 1
    return True


def CheckSuccess(r, label):
    global PASS, FAIL
    if not CheckTuple3(r, label):
        return False
    if r[0] != 1:
        FAIL += 1
        ERRORS.append(label + ': expected ok=1, got ' + str(r[0]))
        return False
    PASS += 1
    return True


def CheckError(r, label, expected_code=None):
    global PASS, FAIL
    if not CheckTuple3(r, label):
        return False
    if r[0] != 0:
        FAIL += 1
        ERRORS.append(label + ': expected ok=0, got ' + str(r[0]))
        return False
    if expected_code and r[2]:
        code = r[2][0] if isinstance(r[2], tuple) else str(r[2])
        if code != expected_code:
            FAIL += 1
            ERRORS.append(label + ': expected ' + str(expected_code) + ', got ' + str(code))
            return False
    PASS += 1
    return True


# ── Database Schema ───────────────────────────────────────────
SQL_CREATE_TEST_CLASSES = """CREATE TABLE IF NOT EXISTS test_classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_name TEXT NOT NULL UNIQUE,
    module_name TEXT NOT NULL,
    class_name TEXT NOT NULL,
    import_path TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)"""

SQL_CREATE_TEST_METHODS = """CREATE TABLE IF NOT EXISTS test_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_class_id INTEGER NOT NULL REFERENCES test_classes(id) ON DELETE CASCADE,
    method_name TEXT NOT NULL,
    method_code TEXT NOT NULL,
    is_edge_case INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(test_class_id, method_name)
)"""

SQL_CREATE_TEST_RESULTS = """CREATE TABLE IF NOT EXISTS test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_class_id INTEGER REFERENCES test_classes(id) ON DELETE CASCADE,
    method_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('PASS','FAIL','ERROR','SKIP')),
    error_detail TEXT,
    duration_ms REAL,
    run_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)"""

SQL_INSERT_TEST_CLASS = "INSERT OR IGNORE INTO test_classes (domain_name, module_name, class_name, import_path) VALUES (?,?,?,?)"
SQL_INSERT_TEST_METHOD = "INSERT OR IGNORE INTO test_methods (test_class_id, method_name, method_code, is_edge_case) VALUES (?,?,?,?)"
SQL_SELECT_ALL_CLASSES = "SELECT id, domain_name, module_name, class_name, import_path FROM test_classes ORDER BY domain_name"
SQL_SELECT_METHODS_BY_CLASS = "SELECT method_name, method_code, is_edge_case FROM test_methods WHERE test_class_id = ? ORDER BY method_name"
SQL_INSERT_RESULT = "INSERT INTO test_results (test_class_id, method_name, status, error_detail, duration_ms, run_id) VALUES (?,?,?,?,?,?)"
SQL_CLEAR_RESULTS = "DELETE FROM test_results"

SCHEMA_ALL = [SQL_CREATE_TEST_CLASSES, SQL_CREATE_TEST_METHODS, SQL_CREATE_TEST_RESULTS]
