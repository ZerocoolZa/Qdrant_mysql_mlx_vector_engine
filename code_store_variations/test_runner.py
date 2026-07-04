#!/usr/bin/env python3

#[@GHOST]{[@file<test_runner.py>][@domain<code_store>][@role<test_runner>][@auth<cascade>][@date<2026-06-22>][@ver<2.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<runner_core>][@return<Tuple3>][@state<results,errors,meta>][@no<global_mutation|shared_exec_state>]}

"""
Unified Test Runner v2 — deterministic execution + isolated test runtime.
Key upgrades over v1:
- Per-test isolated execution state (no FAIL/ERRORS global leakage)
- Safer exec boundary (controlled namespace + stripped builtins)
- Structured result model (PASS/FAIL/ERROR/SKIP consistent)
- Stable meta schema
- Hardened DB lifecycle handling
- Domain-safe execution mapping

Usage:
    python3 test_runner.py                    # run all tests
    python3 test_runner.py --domain db        # run one domain
    python3 test_runner.py --edge-only        # run edge cases only
    python3 test_runner.py --list             # list available tests
"""

import sys
import os
import time
import sqlite3
import importlib
import tempfile
import hashlib
import json
import re
import math
import shutil
import threading
from datetime import datetime
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List

EFL_BRAIN_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'efl_brain', 'efl_brain.db'
)

V20_HYBRID_DB = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'v20_hybrid_best.db'
)

SQL_CREATE_CLOSURE_TESTS = """CREATE TABLE IF NOT EXISTS closure_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    method_name TEXT NOT NULL,
    test_status TEXT,
    test_result TEXT,
    tested_at TEXT
)"""

SQL_INSERT_CLOSURE_TEST = "INSERT INTO closure_tests (domain, method_name, test_status, test_result, tested_at) VALUES (?,?,?,?,?)"

SQL_CREATE_TEST_FEEDBACK = """CREATE TABLE IF NOT EXISTS test_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    method_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('PASS','FAIL','ERROR','SKIP')),
    error_detail TEXT,
    error_type TEXT,
    run_id TEXT,
    source TEXT DEFAULT 'test_runner',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(domain, method_name, run_id)
)"""

SQL_INSERT_FEEDBACK = "INSERT OR REPLACE INTO test_feedback (domain, method_name, status, error_detail, error_type, run_id, source) VALUES (?,?,?,?,?,?,?)"
SQL_CLEAR_FEEDBACK = "DELETE FROM test_feedback WHERE run_id = ?"

SQL_CREATE_LEARNED_FIXES_FEED = """CREATE TABLE IF NOT EXISTS learned_fixes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT,
    error_pattern TEXT,
    fix_pattern TEXT,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    confidence REAL DEFAULT 0.0,
    extracted_from_case INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)"""

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Config import (
    DB_PATH, DOM_PATH,
    SCHEMA_ALL,
    SQL_SELECT_ALL_CLASSES,
    SQL_SELECT_METHODS_BY_CLASS,
    SQL_INSERT_RESULT,
    SQL_CLEAR_RESULTS,
)

# -----------------------------------------------------------------------------
# Result Model
# -----------------------------------------------------------------------------

@dataclass
class TestResult:
    status: str
    detail: Optional[str]
    duration_ms: float

# -----------------------------------------------------------------------------
# Execution Sandbox
# -----------------------------------------------------------------------------

class ExecutionSandbox:
    UNSAFE_BUILTINS = {
        'eval', 'exec', 'globals', 'locals',
        'vars', 'dir', 'input', 'breakpoint', 'exit', 'quit',
    }

    def __init__(self, domain_class=None):
        self.domain_class = domain_class

    def _safe_builtins(self):
        import builtins
        return {k: v for k, v in vars(builtins).items() if k not in self.UNSAFE_BUILTINS}

    def _make_helpers(self):
        import tempfile as _tf, sqlite3 as _sq, os as _os, json as _json

        def make_test_db():
            fd, path = _tf.mkstemp(suffix='.db')
            _os.close(fd)
            conn = _sq.connect(path)
            conn.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)')
            conn.execute("INSERT INTO users (name, age) VALUES ('Alice', 30), ('Bob', 25)")
            conn.commit()
            conn.close()
            return path

        def make_empty_db():
            fd, path = _tf.mkstemp(suffix='.db')
            _os.close(fd)
            return path

        def make_test_dir():
            return _tf.mkdtemp()

        def make_test_file(content='hello world'):
            fd, path = _tf.mkstemp(suffix='.txt')
            with _os.fdopen(fd, 'w') as f:
                f.write(content)
            return path

        def make_test_py():
            fd, path = _tf.mkstemp(suffix='.py')
            with _os.fdopen(fd, 'w') as f:
                f.write('def foo():\n    return 42\n\nclass Bar:\n    pass\n')
            return path

        def make_test_json():
            fd, path = _tf.mkstemp(suffix='.json')
            with _os.fdopen(fd, 'w') as f:
                _json.dump({'name': 'test', 'value': 42}, f)
            return path

        def make_test_template():
            fd, path = _tf.mkstemp(suffix='.tpl')
            with _os.fdopen(fd, 'w') as f:
                f.write('Hello {{name}}, you are {{age}} years old.')
            return path

        def make_test_security():
            fd, path = _tf.mkstemp(suffix='.db')
            _os.close(fd)
            conn = _sq.connect(path)
            conn.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT, role TEXT)')
            conn.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'hash123', 'admin'), ('user', 'hash456', 'user')")
            conn.commit()
            conn.close()
            return path

        def make_bad_fk_db():
            fd, path = _tf.mkstemp(suffix='.db')
            _os.close(fd)
            conn = _sq.connect(path)
            conn.execute('CREATE TABLE parent (id INTEGER PRIMARY KEY)')
            conn.execute('CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER)')
            conn.execute('INSERT INTO child (parent_id) VALUES (999)')
            conn.commit()
            conn.close()
            return path

        def make_test_bracket():
            return '[@Test]{("key";"value";92)}'

        def make_assertion_test(assertion, expected_mode):
            return {'assertion': assertion, 'expected_mode': expected_mode}

        def make_passing_test():
            fd, path = _tf.mkstemp(suffix='.py')
            with _os.fdopen(fd, 'w') as f:
                f.write('def test_pass():\n    assert True\n')
            return path

        def make_failing_test():
            fd, path = _tf.mkstemp(suffix='.py')
            with _os.fdopen(fd, 'w') as f:
                f.write('def test_fail():\n    assert False\n')
            return path

        def make_error_test():
            fd, path = _tf.mkstemp(suffix='.py')
            with _os.fdopen(fd, 'w') as f:
                f.write('def test_error():\n    raise ValueError(\'boom\')\n')
            return path

        def make_bool_test():
            fd, path = _tf.mkstemp(suffix='.py')
            with _os.fdopen(fd, 'w') as f:
                f.write('def test_bool():\n    return True\n')
            return path

        def make_bool_fail_test():
            fd, path = _tf.mkstemp(suffix='.py')
            with _os.fdopen(fd, 'w') as f:
                f.write('def test_bool():\n    return False\n')
            return path

        def make_tmp_dir():
            return _tf.mkdtemp()

        return {
            'make_test_db': make_test_db, 'make_empty_db': make_empty_db,
            'make_test_dir': make_test_dir, 'make_test_file': make_test_file,
            'make_test_py': make_test_py, 'make_test_json': make_test_json,
            'make_test_template': make_test_template, 'make_test_security': make_test_security,
            'make_bad_fk_db': make_bad_fk_db, 'make_test_bracket': make_test_bracket,
            'make_assertion_test': make_assertion_test, 'make_passing_test': make_passing_test,
            'make_failing_test': make_failing_test, 'make_error_test': make_error_test,
            'make_bool_test': make_bool_test, 'make_bool_fail_test': make_bool_fail_test,
            'make_tmp_dir': make_tmp_dir,
        }

    def build_namespace(self) -> Dict[str, Any]:
        safe = self._safe_builtins()
        safe['print'] = lambda *a, **k: None
        ns = {
            '__builtins__': safe,
            '_FAIL': 0,
            '_ERRORS': [],
            'PASS': 0,
            'FAIL': 0,
            'ERRORS': [],
            'tempfile': tempfile, 'shutil': shutil, 'sqlite3': sqlite3,
            'hashlib': hashlib, 'json': json, 're': re, 'os': os, 'math': math,
            'time': time, 'datetime': datetime, 'Counter': Counter,
            'threading': threading, 'DOM_PATH': DOM_PATH,
        }
        ns.update(self._make_helpers())
        if self.domain_class:
            ns[self.domain_class.__name__] = self.domain_class
        return ns

    def inject_assertions(self, ns: Dict[str, Any]) -> None:
        def CheckTuple3(r, label=''):
            if not isinstance(r, tuple) or len(r) != 3:
                ns['_FAIL'] += 1
                ns['_ERRORS'].append(f'{label}: NOT Tuple3')
                return False
            return True

        def CheckSuccess(r, label=''):
            if not CheckTuple3(r, label):
                return False
            if r[0] != 1:
                ns['_FAIL'] += 1
                ns['_ERRORS'].append(f'{label}: expected ok=1, got {r[0]}')
                return False
            return True

        def CheckError(r, label='', expected_code=None):
            if not CheckTuple3(r, label):
                return False
            if r[0] != 0:
                ns['_FAIL'] += 1
                ns['_ERRORS'].append(f'{label}: expected ok=0, got {r[0]}')
                return False
            if expected_code and r[2]:
                code = r[2][0] if isinstance(r[2], tuple) else str(r[2])
                if code != expected_code:
                    ns['_FAIL'] += 1
                    ns['_ERRORS'].append(f'{label}: expected {expected_code}, got {code}')
                    return False
            return True

        ns['CheckTuple3'] = CheckTuple3
        ns['CheckSuccess'] = CheckSuccess
        ns['CheckError'] = CheckError
        ns['check_tuple3'] = CheckTuple3
        ns['check_success'] = CheckSuccess
        ns['check_error'] = CheckError

    def run(self, method_code: str, method_name: str) -> TestResult:
        ns = self.build_namespace()
        self.inject_assertions(ns)
        start = time.time()
        try:
            compiled = compile(method_code, '<test>', 'exec')
            exec(compiled, ns, ns)
        except Exception as e:
            return TestResult('ERROR', f'exec_failed: {e}', (time.time() - start) * 1000)
        func = ns.get(method_name)
        if not callable(func):
            return TestResult('SKIP', f'missing_function: {method_name}', (time.time() - start) * 1000)
        try:
            func()
        except Exception as e:
            return TestResult('ERROR', str(e), (time.time() - start) * 1000)
        duration = (time.time() - start) * 1000
        fail_count = ns.get('_FAIL', 0) + ns.get('FAIL', 0)
        if fail_count > 0:
            errors = ns.get('_ERRORS', []) + ns.get('ERRORS', [])
            return TestResult('FAIL', '; '.join(errors[:3]), duration)
        return TestResult('PASS', None, duration)

# -----------------------------------------------------------------------------
# Test Runner Core
# -----------------------------------------------------------------------------

class TestRunner:
    def __init__(self):
        self.db_path = DB_PATH
        self.dom_path = DOM_PATH
        self.state = {
            'results': [],
            'errors': [],
            'meta': {
                'total_run': 0,
                'total_pass': 0,
                'total_fail': 0,
                'total_error': 0,
                'total_skip': 0,
                'by_domain': {},
            },
        }

    def Run(self, command, params=None):
        params = params or {}
        if command == 'run_all':
            return self.run_all(params)
        if command == 'run_domain':
            return self.run_domain(params.get('domain'))
        if command == 'run_edge':
            return self.run_edge_only()
        if command == 'list':
            return self.list_tests()
        if command == 'read_state':
            return (1, self.state, None)
        return (0, None, ('UNKNOWN_COMMAND', f'TestRunner unknown: {command}', 0))

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    def _ensure_schema(self):
        conn = self._conn()
        cur = conn.cursor()
        for sql in SCHEMA_ALL:
            cur.execute(sql)
        conn.commit()
        conn.close()

    def list_tests(self):
        self._ensure_schema()
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(SQL_SELECT_ALL_CLASSES)
        classes = cur.fetchall()
        output = []
        for class_id, domain, module, cls, path in classes:
            cur.execute(SQL_SELECT_METHODS_BY_CLASS, (class_id,))
            methods = cur.fetchall()
            edge = sum(1 for _, _, is_edge in methods if is_edge)
            output.append(f'{domain}: {len(methods)} tests ({edge} edge) | {module}.{cls}')
        conn.close()
        return (1, output, None)

    def _load_class(self, module_name, class_name, import_path):
        try:
            if import_path not in sys.path:
                sys.path.insert(0, import_path)
            mod = importlib.import_module(module_name)
            return getattr(mod, class_name)
        except Exception:
            return None

    def _execute(self, method_code, method_name, domain_class):
        sandbox = ExecutionSandbox(domain_class)
        return sandbox.run(method_code, method_name)

    def run_all(self, params=None):
        params = params or {}
        edge_only = params.get('edge_only', False)
        domains = params.get('domains')
        if domains:
            domains = [d.lower() for d in domains]
        self._ensure_schema()
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(SQL_CLEAR_RESULTS)
        conn.commit()
        cur.execute(SQL_SELECT_ALL_CLASSES)
        classes = cur.fetchall()
        run_id = str(int(time.time()))
        total = pass_c = fail_c = err_c = skip_c = 0
        for class_id, domain, module_name, class_name, import_path in classes:
            if domains and domain.lower() not in domains:
                continue
            cls = self._load_class(module_name, class_name, import_path)
            cur.execute(SQL_SELECT_METHODS_BY_CLASS, (class_id,))
            methods = cur.fetchall()
            if not methods:
                continue
            if cls is None:
                for method_name, _, _ in methods:
                    cur.execute(SQL_INSERT_RESULT, (
                        class_id, method_name, 'ERROR',
                        'module_load_failed', 0, run_id
                    ))
                    err_c += 1
                    total += 1
                continue
            domain_pass = 0
            domain_fail = 0
            for method_name, method_code, is_edge in methods:
                if edge_only and not is_edge:
                    continue
                result = self._execute(method_code, method_name, cls)
                total += 1
                if result.status == 'PASS':
                    pass_c += 1
                    domain_pass += 1
                elif result.status == 'FAIL':
                    fail_c += 1
                    domain_fail += 1
                elif result.status == 'ERROR':
                    err_c += 1
                    domain_fail += 1
                else:
                    skip_c += 1
                cur.execute(SQL_INSERT_RESULT, (
                    class_id, method_name, result.status,
                    result.detail, result.duration_ms, run_id
                ))
            self.state['meta']['by_domain'][domain] = {
                'pass': domain_pass,
                'fail': domain_fail,
                'total': domain_pass + domain_fail,
            }
        conn.commit()
        conn.close()
        self.state['meta'].update({
            'total_run': total,
            'total_pass': pass_c,
            'total_fail': fail_c,
            'total_error': err_c,
            'total_skip': skip_c,
        })
        fb_ok, fb_data, fb_err = self.WriteFeedback(run_id)
        if fb_ok:
            self.state['feedback'] = fb_data
        return (1, {
            'total': total, 'pass': pass_c, 'fail': fail_c,
            'error': err_c, 'skip': skip_c,
            'by_domain': self.state['meta']['by_domain'],
            'feedback': fb_data if fb_ok else None,
        }, None)

    def run_domain(self, domain):
        return self.run_all({'domains': [domain]})

    def run_edge_only(self):
        return self.run_all({'edge_only': True})

    def WriteFeedback(self, run_id=None):
        """Write test results to efl_brain.db AND closure_tests table in v20_hybrid_best.db."""
        self._ensure_schema()
        conn = self._conn()
        cur = conn.cursor()
        cur.execute('SELECT MAX(run_id) FROM test_results')
        latest_run = cur.fetchone()[0]
        if not run_id:
            run_id = latest_run
        if not run_id:
            return (0, None, ('NO_RESULTS', 'No test results to feed back', 0))
        cur.execute("""
            SELECT tc.domain_name, tr.method_name, tr.status, tr.error_detail
            FROM test_results tr
            JOIN test_classes tc ON tr.test_class_id = tc.id
            WHERE tr.run_id = ?
        """, (run_id,))
        rows = cur.fetchall()
        conn.close()

        # --- Write to closure_tests in v20_hybrid_best.db ---
        closure_written = 0
        if os.path.exists(V20_HYBRID_DB):
            v20 = sqlite3.connect(V20_HYBRID_DB)
            vcur = v20.cursor()
            vcur.execute(SQL_CREATE_CLOSURE_TESTS)
            now = datetime.now().isoformat()
            for domain, method_name, status, error_detail in rows:
                vcur.execute(SQL_INSERT_CLOSURE_TEST, (
                    domain, method_name, status,
                    error_detail or '', now
                ))
                closure_written += 1
            v20.commit()
            v20.close()

        # --- Write to efl_brain.db test_feedback (if available) ---
        efl_written = 0
        failures = []
        if os.path.exists(EFL_BRAIN_DB):
            efl = sqlite3.connect(EFL_BRAIN_DB)
            ecur = efl.cursor()
            ecur.execute(SQL_CREATE_TEST_FEEDBACK)
            ecur.execute(SQL_CREATE_LEARNED_FIXES_FEED)
            ecur.execute(SQL_CLEAR_FEEDBACK, (run_id,))
            for domain, method_name, status, error_detail in rows:
                error_type = ''
                if error_detail:
                    if 'exec_failed' in error_detail or 'exec' in error_detail.lower():
                        error_type = 'EXEC_ERROR'
                    elif 'not defined' in error_detail.lower():
                        error_type = 'NAME_ERROR'
                    elif 'No such file' in error_detail:
                        error_type = 'FILE_ERROR'
                    elif 'module_load_failed' in error_detail:
                        error_type = 'IMPORT_ERROR'
                    elif 'missing_function' in error_detail:
                        error_type = 'MISSING_IMPL'
                    else:
                        error_type = 'RUNTIME_ERROR'
                ecur.execute(SQL_INSERT_FEEDBACK, (
                    domain, method_name, status,
                    error_detail or '', error_type, run_id, 'test_runner'
                ))
                efl_written += 1
                if status in ('FAIL', 'ERROR'):
                    failures.append((domain, method_name, error_type, error_detail or ''))
            efl.commit()
            efl.close()

        total_written = closure_written + efl_written
        return (1, {
            'written': total_written,
            'closure_tests_written': closure_written,
            'efl_feedback_written': efl_written,
            'failures': len(failures),
            'failure_details': failures[:20],
            'run_id': run_id,
        }, None)

# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main():
    runner = TestRunner()
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
        return
    if '--list' in sys.argv:
        ok, data, err = runner.list_tests()
        if ok:
            print('\n'.join(data))
        else:
            print('ERROR:', err)
        return
    if '--domain' in sys.argv:
        i = sys.argv.index('--domain')
        if i + 1 >= len(sys.argv):
            print('ERROR: --domain requires a value')
            return
        domain = sys.argv[i + 1]
        ok, data, err = runner.run_domain(domain)
    elif '--edge-only' in sys.argv:
        ok, data, err = runner.run_edge_only()
    else:
        ok, data, err = runner.run_all()
    if not ok:
        print('ERROR:', err)
        return
    print('\n' + '=' * 60)
    print(f"Tests: {data['total']} | Pass: {data['pass']} | Fail: {data['fail']} | Error: {data['error']} | Skip: {data['skip']}")
    print('=' * 60)
    for d, s in sorted(data['by_domain'].items()):
        print(f"{d:20s}: {s['pass']:3d} pass / {s['total']:3d} total")
    if data.get('feedback'):
        fb = data['feedback']
        print(f"\nFeedback: {fb['written']} written | {fb['failures']} failures | run_id={fb['run_id']}")


if __name__ == '__main__':
    main()
