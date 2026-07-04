#!/usr/bin/env python3
"""
EFL RAM AI — Error → Fix Learning Loop
Broken Code Generator + Executor + Repair Engine + SQLite Memory
Core idea:
generate broken python → execute → capture error → fix → store → reuse patterns
"""
import sqlite3
import traceback
import random
import re
import ast
import difflib
from datetime import datetime, timezone

from Config_efl_brain import DB_PATH as EFL_DB_PATH, SQL_CREATE_EXECUTION_LOG, SQL_CREATE_LEARNED_FIXES

DB_PATH = EFL_DB_PATH
WORKER_DB_TEMPLATE = "efl_memory_worker_{}.db"

# =========================================================
# SQLITE MEMORY
# =========================================================
class MemoryDB:
    def __init__(self, db_path=None):
        self.conn = sqlite3.connect(db_path or DB_PATH)
        self.cur = self.conn.cursor()
        self._init()

    def _init(self):
        self.cur.execute("""
        CREATE TABLE IF NOT EXISTS error_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            broken_code TEXT,
            error_type TEXT,
            error_message TEXT,
            fixed_code TEXT,
            fix_rule TEXT,
            re_run_success INTEGER DEFAULT 0,
            timestamp TEXT
        )
        """)
        self.cur.execute("""
        CREATE TABLE IF NOT EXISTS learned_fixes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_name TEXT UNIQUE,
            error_pattern TEXT,
            fix_pattern TEXT,
            success_count INTEGER DEFAULT 0,
            failure_count INTEGER DEFAULT 0,
            confidence REAL DEFAULT 0.5,
            extracted_from_case INTEGER,
            created_at TEXT
        )
        """)
        self.cur.execute("""
        CREATE TABLE IF NOT EXISTS extracted_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            error_signature TEXT,
            remove_pattern TEXT,
            add_pattern TEXT,
            uses INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            score REAL DEFAULT 1.0,
            created_at TEXT
        )
        """)
        self.conn.commit()

    def insert(self, broken, err_type, err_msg, fixed, rule, success=0):
        self.cur.execute("""
        INSERT INTO error_cases (
            broken_code, error_type, error_message, fixed_code, fix_rule, re_run_success, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            broken, err_type, err_msg, fixed, rule, success,
            datetime.now(timezone.utc).isoformat()
        ))
        self.conn.commit()
        return self.cur.lastrowid

    def record_fix_outcome(self, case_id, success):
        if success:
            self.cur.execute("UPDATE error_cases SET re_run_success = 1 WHERE id = ?", (case_id,))
        self.conn.commit()

    def learn_rule(self, rule_name, error_pattern, fix_pattern, success, case_id=None):
        self.cur.execute("SELECT id, success_count, failure_count, confidence FROM learned_fixes WHERE rule_name = ?", (rule_name,))
        row = self.cur.fetchone()
        if row:
            rid, sc, fc, conf = row
            sc += 1 if success else 0
            fc += 0 if success else 1
            total = sc + fc
            conf = sc / total if total > 0 else 0.5
            self.cur.execute("UPDATE learned_fixes SET success_count = ?, failure_count = ?, confidence = ? WHERE id = ?", (sc, fc, conf, rid))
        else:
            self.cur.execute("""
            INSERT OR IGNORE INTO learned_fixes (rule_name, error_pattern, fix_pattern, success_count, failure_count, confidence, extracted_from_case, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (rule_name, error_pattern, fix_pattern, 1 if success else 0, 0 if success else 1, 0.5 if not success else 1.0, case_id, datetime.now(timezone.utc).isoformat()))
        self.conn.commit()

    def add_extracted_rule(self, error_sig, remove_pat, add_pat):
        self.cur.execute("SELECT id, uses, wins, score FROM extracted_rules WHERE error_signature = ? AND remove_pattern = ?", (error_sig, remove_pat))
        row = self.cur.fetchone()
        if row:
            return row[0]
        self.cur.execute("""
        INSERT INTO extracted_rules (error_signature, remove_pattern, add_pattern, uses, wins, score, created_at)
        VALUES (?, ?, ?, 0, 0, 1.0, ?)
        """, (error_sig, remove_pat, add_pat, datetime.now(timezone.utc).isoformat()))
        self.conn.commit()
        return self.cur.lastrowid

    def fetch_extracted_rules(self):
        self.cur.execute("SELECT error_signature, remove_pattern, add_pattern, uses, wins, score FROM extracted_rules ORDER BY score DESC")
        return self.cur.fetchall()

    def update_extracted_rule(self, error_sig, remove_pat, success):
        self.cur.execute("SELECT id, uses, wins, score FROM extracted_rules WHERE error_signature = ? AND remove_pattern = ?", (error_sig, remove_pat))
        row = self.cur.fetchone()
        if row:
            rid, uses, wins, score = row
            uses += 1
            wins += 1 if success else 0
            score = wins / uses if uses > 0 else 0.5
            self.cur.execute("UPDATE extracted_rules SET uses = ?, wins = ?, score = ? WHERE id = ?", (uses, wins, score, rid))
            self.conn.commit()

    def fetch_all(self):
        self.cur.execute("SELECT * FROM error_cases")
        return self.cur.fetchall()

    def fetch_learned_rules(self):
        self.cur.execute("SELECT rule_name, success_count, failure_count, confidence FROM learned_fixes ORDER BY confidence DESC")
        return self.cur.fetchall()

    def stats(self):
        self.cur.execute("SELECT COUNT(*) FROM error_cases")
        total = self.cur.fetchone()[0]
        self.cur.execute("SELECT COUNT(*) FROM error_cases WHERE re_run_success = 1")
        fixed = self.cur.fetchone()[0]
        self.cur.execute("SELECT COUNT(*) FROM learned_fixes")
        rules = self.cur.fetchone()[0]
        return total, fixed, rules

# =========================================================
# ERROR FAMILIES (12 families, AST + template hybrid)
# =========================================================
ERROR_FAMILIES = [
    "syntax_structure",
    "indentation",
    "quotes_strings",
    "name_resolution",
    "import_errors",
    "type_errors",
    "attribute_errors",
    "index_errors",
    "argument_mismatch",
    "scope_errors",
    "logic_structure",
    "runtime_environment",
]


class BrokenCodeGenerator:
    DEFAULT_WEIGHTS = {
        "syntax_structure": 0.20,
        "indentation": 0.10,
        "quotes_strings": 0.10,
        "name_resolution": 0.12,
        "import_errors": 0.08,
        "type_errors": 0.10,
        "attribute_errors": 0.08,
        "index_errors": 0.07,
        "argument_mismatch": 0.05,
        "scope_errors": 0.05,
        "logic_structure": 0.03,
        "runtime_environment": 0.02,
    }

    def __init__(self):
        self.difficulty_weights = dict(self.DEFAULT_WEIGHTS)
        self.family_map = {
            "syntax_structure": [self.missing_colon, self.missing_colon_if, self.missing_colon_for,
                                 self.missing_colon_class, self.missing_paren, self.missing_comma,
                                 self.wrong_keyword, self.broken_bracket],
            "indentation": [self.bad_indentation, self.over_indentation, self.tab_space_mix],
            "quotes_strings": [self.missing_quote, self.missing_double_quote, self.mixed_quotes],
            "name_resolution": [self.undefined_var, self.undefined_var_nested, self.typo_variable],
            "import_errors": [self.missing_import, self.wrong_import_name, self.partial_import],
            "type_errors": [self.int_str_add, self.list_plus_int, self.dict_key_wrong_type],
            "attribute_errors": [self.wrong_attribute, self.method_on_none, self.missing_attribute],
            "index_errors": [self.list_index_overflow, self.list_negative_overflow, self.dict_missing_key],
            "argument_mismatch": [self.too_few_args, self.too_many_args, self.wrong_kwarg],
            "scope_errors": [self.local_before_global, self.modifying_global_without_global, self.nested_scope_leak],
            "logic_structure": [self.unreachable_code, self.empty_block, self.duplicate_function],
            "runtime_environment": [self.missing_file, self.division_by_zero, self.key_error_runtime],
        }

    def generate(self, n_errors=1):
        families = list(self.difficulty_weights.keys())
        weights = list(self.difficulty_weights.values())
        if n_errors == 1:
            family = random.choices(families, weights=weights, k=1)[0]
            generator = random.choice(self.family_map[family])
            return generator(), family

        # Compositional: stack n_errors from different families
        families_used = []
        code = None
        for _ in range(n_errors):
            family = random.choices(families, weights=weights, k=1)[0]
            families_used.append(family)
            generator = random.choice(self.family_map[family])
            new_code = generator()
            if code is None:
                code = new_code
            else:
                # Append additional error code
                code = code + "\n" + new_code
        return code, "compositional:" + "+".join(families_used)

    # ── Family 1: Syntax Structure ───────────────────────────
    def missing_colon(self):
        return "def test()\n    print('hello')\ntest()"

    def missing_colon_if(self):
        return "x = 5\nif x > 3\n    print('big')"

    def missing_colon_for(self):
        return "for i in range(3)\n    print(i)"

    def missing_colon_class(self):
        return "class Foo\n    def bar(self):\n        return 1\nFoo().bar()"

    def missing_paren(self):
        return "def add(a, b:\n    return a + b\nprint(add(1, 2))"

    def missing_comma(self):
        return "def add(a b):\n    return a + b\nprint(add(1, 2))"

    def wrong_keyword(self):
        return "x = 5\niff x > 3:\n    print('big')"

    def broken_bracket(self):
        return "x = [1, 2, 3\nprint(x)"

    # ── Family 2: Indentation ────────────────────────────────
    def bad_indentation(self):
        return "def run():\nprint('bad indent')\nrun()"

    def over_indentation(self):
        return "def run():\n        print('too much')\nrun()"

    def tab_space_mix(self):
        return "def run():\n\tprint('tab')\n    print('space')\nrun()"

    # ── Family 3: Quotes/Strings ─────────────────────────────
    def missing_quote(self):
        return "x = 'hello\nprint(x)"

    def missing_double_quote(self):
        return 'y = "world\nprint(y)'

    def mixed_quotes(self):
        return "z = 'hello\"\nprint(z)"

    # ── Family 4: Name Resolution ────────────────────────────
    def undefined_var(self):
        return "def calc():\n    return a + 1\ncalc()"

    def undefined_var_nested(self):
        return "def outer():\n    def inner():\n        return missing_var\n    return inner()\nouter()"

    def typo_variable(self):
        return "count = 5\nprint(cont)"

    # ── Family 5: Import Errors ──────────────────────────────
    def missing_import(self):
        return "result = json.loads('{\"a\": 1}')\nprint(result)"

    def wrong_import_name(self):
        return "import math\nprint(maths.sqrt(4))"

    def partial_import(self):
        return "from os import pathh\nprint(pathh.exists('/tmp'))"

    # ── Family 6: Type Errors ────────────────────────────────
    def int_str_add(self):
        return "x = 5 + 'hello'\nprint(x)"

    def list_plus_int(self):
        return "x = [1, 2] + 3\nprint(x)"

    def dict_key_wrong_type(self):
        return "d = {1: 'a'}\nprint(d['1'])"

    # ── Family 7: Attribute Errors ───────────────────────────
    def wrong_attribute(self):
        return "x = [1, 2, 3]\nprint(x.lenght)"

    def method_on_none(self):
        return "x = None\nprint(x.append(1))"

    def missing_attribute(self):
        return "import math\nprint(math.pie)"

    # ── Family 8: Index Errors ───────────────────────────────
    def list_index_overflow(self):
        return "x = [1, 2, 3]\nprint(x[10])"

    def list_negative_overflow(self):
        return "x = [1, 2]\nprint(x[-5])"

    def dict_missing_key(self):
        return "d = {'a': 1}\nprint(d['z'])"

    # ── Family 9: Argument Mismatch ──────────────────────────
    def too_few_args(self):
        return "def add(a, b, c):\n    return a + b + c\nprint(add(1, 2))"

    def too_many_args(self):
        return "def add(a, b):\n    return a + b\nprint(add(1, 2, 3))"

    def wrong_kwarg(self):
        return "def greet(name, age=0):\n    return f'{name} {age}'\nprint(greet(nam='Bob'))"

    # ── Family 10: Scope Errors ──────────────────────────────
    def local_before_global(self):
        return "x = 1\ndef f():\n    print(x)\n    x = 2\nf()"

    def modifying_global_without_global(self):
        return "counter = 0\ndef increment():\n    counter += 1\nincrement()"

    def nested_scope_leak(self):
        return "def outer():\n    inner_val = 42\ndef caller():\n    return inner_val\ncaller()"

    # ── Family 11: Logic Structure ───────────────────────────
    def unreachable_code(self):
        return "def f():\n    return 1\nf()\nprint(undefined_after_call)"

    def empty_block(self):
        return "def f():\n    if True:\n    return 1\nf()"

    def duplicate_function(self):
        return "def f(a, b):\n    return a + b\ndef f(a):\n    return a\nprint(f(1, 2, 3))"

    # ── Family 12: Runtime Environment ───────────────────────
    def missing_file(self):
        return "f = open('nonexistent_file_xyz.txt', 'r')\nprint(f.read())"

    def division_by_zero(self):
        return "x = 10\ny = 0\nprint(x / y)"

    def key_error_runtime(self):
        return "d = {}\nprint(d['missing'])"


# =========================================================
# AST ERROR INJECTOR — unlimited structured failure cases
# =========================================================
class ASTErrorInjector:
    """Takes valid Python code, injects errors via AST mutation, returns broken code."""

    INJECTIONS = [
        "remove_colon",
        "remove_import",
        "rename_variable",
        "remove_argument",
        "change_operator",
        "remove_return",
        "swap_args",
        "inject_none",
        "remove_list_item",
        "change_number",
    ]

    CLEAN_TEMPLATES = [
        "def add(a, b):\n    return a + b\nprint(add(1, 2))",
        "def greet(name):\n    return f'Hello {name}'\nprint(greet('World'))",
        "def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)\nprint(factorial(5))",
        "class Counter:\n    def __init__(self):\n        self.count = 0\n    def increment(self):\n        self.count += 1\n        return self.count\nc = Counter()\nprint(c.increment())",
        "def filter_even(nums):\n    return [n for n in nums if n % 2 == 0]\nprint(filter_even([1, 2, 3, 4, 5, 6]))",
        "import math\ndef circle_area(radius):\n    return math.pi * radius ** 2\nprint(circle_area(5))",
        "def merge_dicts(a, b):\n    result = a.copy()\n    result.update(b)\n    return result\nprint(merge_dicts({1: 'a'}, {2: 'b'}))",
        "def fibonacci(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a\nprint(fibonacci(10))",
    ]

    def generate(self):
        template = random.choice(self.CLEAN_TEMPLATES)
        # Capture expected output from clean template
        try:
            from io import StringIO
            import sys
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            local_env = {}
            exec(template, {}, local_env)
            expected = sys.stdout.getvalue().strip()
            sys.stdout = old_stdout
        except Exception:
            expected = None
        for _ in range(len(self.INJECTIONS)):
            injection = random.choice(self.INJECTIONS)
            broken = self._inject(template, injection)
            if broken is not None:
                return broken, "ast_injected", expected
        return self._inject(template, "remove_colon") or (template, "ast_injected", expected)

    def _inject(self, code, injection_type):
        if injection_type == "remove_colon":
            lines = code.split("\n")
            candidates = [i for i, l in enumerate(lines) if l.rstrip().endswith(":")]
            if candidates:
                idx = random.choice(candidates)
                lines[idx] = lines[idx].rstrip()[:-1]
                return "\n".join(lines)

        elif injection_type == "remove_import":
            lines = code.split("\n")
            for i, l in enumerate(lines):
                if l.strip().startswith("import ") or l.strip().startswith("from "):
                    lines.pop(i)
                    return "\n".join(lines)

        elif injection_type == "rename_variable":
            try:
                tree = ast.parse(code)
                names = set()
                imported = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imported.add(alias.asname or alias.name)
                    if isinstance(node, ast.ImportFrom):
                        for alias in node.names:
                            imported.add(alias.asname or alias.name)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Name) and node.id not in ('print', 'True', 'False', 'None', 'self') and node.id not in imported:
                        names.add(node.id)
                if names:
                    target = random.choice(list(names))
                    typo = target[:-1] if len(target) > 2 else target + "x"
                    return re.sub(rf"\b{target}\b", typo, code)
            except SyntaxError:
                pass

        elif injection_type == "remove_argument":
            lines = code.split("\n")
            for i, l in enumerate(lines):
                m = re.match(r'(def \w+\()([^)]+)(\))', l)
                if m and "," in m.group(2):
                    params = [p.strip() for p in m.group(2).split(",")]
                    if len(params) > 1:
                        params.pop(random.randrange(len(params)))
                        lines[i] = f"{m.group(1)}{', '.join(params)}{m.group(3)}"
                        return "\n".join(lines)

        elif injection_type == "change_operator":
            # Only change operators that will cause TypeError (str + int) or ZeroDivisionError
            for old_op in ["+", "-", "*", "/", "%"]:
                pattern = re.escape(old_op)
                if re.search(pattern, code):
                    new_op = random.choice(["/", "%", "+", "-"])
                    if new_op != old_op:
                        return re.sub(pattern, new_op, code, count=1)

        elif injection_type == "remove_return":
            lines = code.split("\n")
            candidates = [i for i, l in enumerate(lines) if "return " in l and l.strip().startswith("return")]
            if candidates:
                idx = random.choice(candidates)
                # Remove the return value entirely, leaving bare 'return' with no value
                lines[idx] = lines[idx].split("return")[0] + "return"
                return "\n".join(lines)

        elif injection_type == "swap_args":
            lines = code.split("\n")
            for i, l in enumerate(lines):
                m = re.match(r'(def \w+\()([^)]+)(\))', l)
                if m and "," in m.group(2):
                    params = [p.strip() for p in m.group(2).split(",")]
                    if len(params) >= 2:
                        random.shuffle(params)
                        lines[i] = f"{m.group(1)}{', '.join(params)}{m.group(3)}"
                        return "\n".join(lines)

        elif injection_type == "inject_none":
            lines = code.split("\n")
            for i, l in enumerate(lines):
                stripped = l.strip()
                if stripped.startswith("return ") and not "None" in stripped:
                    lines[i] = l.replace(stripped, "return None")
                    return "\n".join(lines)

        elif injection_type == "remove_list_item":
            m = re.search(r'\[([^\]]+)\]', code)
            if m and "," in m.group(1):
                items = [it.strip() for it in m.group(1).split(",")]
                if len(items) > 1:
                    items.pop(random.randrange(len(items)))
                    new_list = "[" + ", ".join(items) + "]"
                    return code.replace(m.group(0), new_list, 1)

        elif injection_type == "change_number":
            numbers = re.findall(r'\b\d+\b', code)
            if numbers:
                target = random.choice(numbers)
                new_val = str(int(target) + random.choice([-1, 1, 100, -100]))
                return re.sub(rf'\b{target}\b', new_val, code, count=1)

        return None

# =========================================================
# STATIC ANALYZER — 3-layer silent bug detection
# =========================================================
class StaticAnalyzer:
    """Detects bugs that don't produce runtime errors.
    Layer 1: AST introspection (dead methods, no-op replaces, type mismatches)
    Layer 2: Pattern linter (custom regex/AST rules for known bug classes)
    Layer 3: pyflakes integration (undefined names, unused imports)"""

    def __init__(self):
        self.findings = []

    def analyze(self, code, filename="<string>"):
        self.findings = []
        self._layer1_ast(code, filename)
        self._layer2_patterns(code, filename)
        self._layer3_pyflakes(code, filename)
        return self.findings

    # ── Layer 1: AST introspection ──────────────────────────
    def _layer1_ast(self, code, filename):
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return

        # 1a: Dead methods — defined but never called
        defined_methods = set()
        called_names = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defined_methods.add(node.name)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)
            if isinstance(node, ast.Name):
                called_names.add(node.id)

        for method in defined_methods:
            if method not in called_names and not method.startswith("_"):
                self.findings.append({
                    "layer": "ast",
                    "type": "dead_method",
                    "severity": "medium",
                    "message": f"Method '{method}' is defined but never called",
                    "line": None,
                    "fix_hint": "remove_or_call",
                })

        # 1b: No-op replacements — code.replace(X, X) or re.sub(X, X, ...)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "replace" and len(node.args) >= 2:
                    old_val = self._get_literal(node.args[0])
                    new_val = self._get_literal(node.args[1])
                    if old_val is not None and new_val is not None and old_val == new_val:
                        self.findings.append({
                            "layer": "ast",
                            "type": "noop_replace",
                            "severity": "high",
                            "message": f"No-op replace: .replace({old_val!r}, {new_val!r})",
                            "line": getattr(node, "lineno", None),
                            "fix_hint": "remove_or_fix",
                        })
                if node.func.attr == "sub" and len(node.args) >= 2:
                    old_val = self._get_literal(node.args[0])
                    new_val = self._get_literal(node.args[1])
                    if old_val is not None and new_val is not None and old_val == new_val:
                        self.findings.append({
                            "layer": "ast",
                            "type": "noop_sub",
                            "severity": "high",
                            "message": f"No-op re.sub({old_val!r}, {new_val!r}, ...)",
                            "line": getattr(node, "lineno", None),
                            "fix_hint": "remove_or_fix",
                        })

        # 1c: Duplicate function definitions (same name, same scope)
        seen_defs = {}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in seen_defs:
                    self.findings.append({
                        "layer": "ast",
                        "type": "duplicate_def",
                        "severity": "high",
                        "message": f"Function '{node.name}' redefined (line {node.lineno}, first at line {seen_defs[node.name]})",
                        "line": node.lineno,
                        "fix_hint": "rename_or_remove",
                    })
                seen_defs[node.name] = node.lineno

        # 1d: Unreachable code after return/raise
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = node.body
                for i, stmt in enumerate(body):
                    if isinstance(stmt, (ast.Return, ast.Raise)):
                        if i < len(body) - 1:
                            next_stmt = body[i + 1]
                            self.findings.append({
                                "layer": "ast",
                                "type": "unreachable_code",
                                "severity": "low",
                                "message": f"Unreachable code after return/raise in '{node.name}' (line {getattr(next_stmt, 'lineno', '?')})",
                                "line": getattr(next_stmt, "lineno", None),
                                "fix_hint": "remove_dead_code",
                            })
                        break

    @staticmethod
    def _get_literal(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.JoinedStr):
            try:
                return ast.unparse(node)
            except Exception:
                return None
        return None

    # ── Layer 2: Pattern linter ─────────────────────────────
    def _layer2_patterns(self, code, filename):
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # 2a: No-op string replace (f-string variant)
            if ".replace(" in stripped:
                m = re.search(r'\.replace\(\s*["\']([^"\']*)["\']\s*,\s*["\']([^"\']*)["\']\s*\)', stripped)
                if m and m.group(1) == m.group(2):
                    self.findings.append({
                        "layer": "pattern",
                        "type": "noop_replace",
                        "severity": "high",
                        "message": f"No-op .replace('{m.group(1)}', '{m.group(2)}') on line {i}",
                        "line": i,
                        "fix_hint": "remove_or_fix",
                    })

            # 2b: Bare except (catches everything including KeyboardInterrupt)
            if re.match(r'^\s*except\s*:', stripped):
                self.findings.append({
                    "layer": "pattern",
                    "type": "bare_except",
                    "severity": "medium",
                    "message": f"Bare 'except:' on line {i} — catches all exceptions including SystemExit",
                    "line": i,
                    "fix_hint": "specify_exception_type",
                })

            # 2c: Mutable default argument
            if re.search(r'def\s+\w+\(.*=\s*(\[\]|\{\}|\(\))', stripped):
                self.findings.append({
                    "layer": "pattern",
                    "type": "mutable_default",
                    "severity": "medium",
                    "message": f"Mutable default argument on line {i} — shared across calls",
                    "line": i,
                    "fix_hint": "use_none_default",
                })

            # 2d: == None / != None instead of is None / is not None
            if re.search(r'==\s*None', stripped) or re.search(r'!=\s*None', stripped):
                self.findings.append({
                    "layer": "pattern",
                    "type": "none_comparison",
                    "severity": "low",
                    "message": f"Use 'is None' instead of '== None' on line {i}",
                    "line": i,
                    "fix_hint": "use_is_none",
                })

            # 2e: Unused variable (assigned but never read — simple heuristic)
            m = re.match(r'^\s*(\w+)\s*=\s*.*$', stripped)
            if m and not stripped.startswith("self.") and not m.group(1).startswith("_"):
                var_name = m.group(1)
                if var_name not in ("self", "cls", "result", "return"):
                    rest_of_code = "\n".join(lines[i:])
                    uses = len(re.findall(rf'\b{var_name}\b', rest_of_code))
                    if uses == 0 and var_name not in code.split("\n")[i-1].split("=")[1]:
                        pass  # Heuristic too noisy, skip for now

    # ── Layer 3: pyflakes integration ───────────────────────
    def _layer3_pyflakes(self, code, filename):
        try:
            import pyflakes.api as pyf_api

            warnings = []
            class _Reporter:
                def unexpectedError(self, filename, msg):
                    pass
                def syntaxError(self, filename, msg, lineno, offset, text):
                    pass
                def flake(self, message):
                    warnings.append(message)

            pyf_api.check(code, filename, _Reporter())

            for w in warnings:
                severity = "high"
                if "unused" in str(w).lower():
                    severity = "low"
                elif "undefined" in str(w).lower():
                    severity = "high"
                elif "redefinition" in str(w).lower():
                    severity = "high"

                self.findings.append({
                    "layer": "pyflakes",
                    "type": str(w).split(":")[0].strip() if ":" in str(w) else "flake",
                    "severity": severity,
                    "message": str(w),
                    "line": getattr(w, "lineno", None),
                    "fix_hint": "see_pyflakes_message",
                })
        except ImportError:
            pass  # pyflakes not installed — graceful fallback

    def summary(self):
        if not self.findings:
            return "  No issues found."
        by_layer = {}
        for f in self.findings:
            layer = f["layer"]
            by_layer.setdefault(layer, []).append(f)
        lines = []
        for layer in ("ast", "pattern", "pyflakes"):
            if layer not in by_layer:
                continue
            items = by_layer[layer]
            lines.append(f"  [{layer}] {len(items)} finding(s):")
            for item in items:
                lines.append(f"    {item['severity']:6s} {item['type']:20s} {item['message']}")
        return "\n".join(lines)

# =========================================================
# EXECUTOR
# =========================================================
class Executor:
    def run(self, code: str):
        try:
            local_env = {}
            exec(code, {}, local_env)
            return True, None
        except SyntaxError as e:
            return False, f"SyntaxError: {e.msg} (line {e.lineno})"
        except Exception:
            return False, traceback.format_exc()

# =========================================================
# REPAIR ENGINE (RULE-BASED LEARNER)
# =========================================================
class RepairEngine:
    def fix(self, code: str, error: str):
        rules_applied = []

        # RULE 1: missing colon after def/if/for/while/class
        if "expected ':'" in error or ("SyntaxError" in error and "expected an indented block" not in error):
            patterns = [
                (r"(def\s+\w+\s*\([^)]*\))\s*$", r"\1:"),
                (r"(if\s+.+)\s*$", r"\1:"),
                (r"(for\s+.+)\s*$", r"\1:"),
                (r"(while\s+.+)\s*$", r"\1:"),
                (r"(class\s+\w+)\s*$", r"\1:"),
                (r"(elif\s+.+)\s*$", r"\1:"),
                (r"(else)\s*$", r"\1:"),
                (r"(try)\s*$", r"\1:"),
                (r"(except.*)\s*$", r"\1:"),
                (r"(finally)\s*$", r"\1:"),
                (r"(with\s+.+)\s*$", r"\1:"),
            ]
            for pat, rep in patterns:
                new_code = re.sub(pat, rep, code, flags=re.MULTILINE)
                if new_code != code:
                    code = new_code
                    rules_applied.append("add_colon")
                    break

        # RULE 2: bad indentation — add indentation to lines after def/if/for/while/class
        if "IndentationError" in error or "expected an indented block" in error:
            code = self.fix_indentation(code)
            rules_applied.append("fix_indentation")

        # RULE 2b: tab/space mix — normalize all tabs to 4 spaces
        if "unindent does not match" in error or "inconsistent use of tabs and spaces" in error:
            lines = code.split("\n")
            fixed = []
            for line in lines:
                fixed.append(line.replace("\t", "    "))
            code = "\n".join(fixed)
            if "fix_indentation" not in rules_applied:
                rules_applied.append("fix_tab_space_mix")
            else:
                code = self.fix_indentation(code)

        # RULE 3: unterminated string literal (Python 3.13 message)
        if "unterminated string literal" in error or "EOL while scanning" in error:
            code = self.fix_missing_quote(code)
            rules_applied.append("fix_missing_quote")

        # RULE 4: NameError — check import first, then typo, then inject
        if "NameError" in error:
            name_match = re.search(r"name '(\w+)' is not defined", error)
            if name_match:
                var_name = name_match.group(1)
                handled = False

                # 4a: check if it's a missing import (json, os, sys, re, etc.)
                known_modules = {"json", "os", "sys", "re", "math", "random", "datetime",
                                 "collections", "itertools", "functools", "string", "pathlib",
                                 "sqlite3", "traceback", "copy", "time", "io", "csv",
                                 "hashlib", "base64", "typing", "decimal", "fractions"}
                if var_name in known_modules:
                    code = f"import {var_name}\n" + code
                    rules_applied.append("add_missing_import")
                    handled = True

                # 4b: check if it's a typo of an existing variable or builtin
                if not handled:
                    lines = code.split("\n")
                    defined_names = set()
                    for line in lines:
                        for m in re.finditer(r'(?:^|\s)(\w+)\s*=', line):
                            defined_names.add(m.group(1))
                        for m in re.finditer(r'import\s+(\w+)', line):
                            defined_names.add(m.group(1))
                        for m in re.finditer(r'def\s+(\w+)', line):
                            defined_names.add(m.group(1))
                    builtins = {"range", "print", "len", "str", "int", "float", "list",
                               "dict", "set", "tuple", "bool", "abs", "min", "max",
                               "sum", "sorted", "reversed", "enumerate", "zip", "map",
                               "filter", "open", "type", "isinstance", "input"}
                    defined_names.update(builtins)
                    best_match = None
                    best_score = 0
                    for defined in defined_names:
                        if defined == var_name:
                            continue
                        score = sum(1 for a, b in zip(var_name, defined) if a == b)
                        if score > best_score and score >= len(var_name) - 2:
                            best_score = score
                            best_match = defined
                    if best_match and best_score >= max(3, len(var_name) - 2):
                        code = re.sub(rf"\b{var_name}\b", best_match, code)
                        rules_applied.append("fix_variable_typo")
                        handled = True

                # 4c: fallback — inject at module level if var used outside its defining function
                if not handled:
                    lines = code.split("\n")
                    var_def_func = None
                    current_func = None
                    var_used_outside = False
                    for line in lines:
                        stripped = line.strip()
                        if stripped.startswith("def "):
                            current_func = stripped
                        if re.search(rf"\b{var_name}\s*=", line) and current_func:
                            var_def_func = current_func
                        if re.search(rf"\b{var_name}\b", line) and current_func and current_func != var_def_func and var_def_func:
                            var_used_outside = True
                    if var_used_outside:
                        code = f"{var_name} = 0\n" + code
                        rules_applied.append("inject_missing_variable")
                    else:
                        injected = False
                        for i, line in enumerate(lines):
                            stripped = line.strip()
                            if stripped.startswith("def ") or stripped.startswith("class "):
                                indent = len(line) - len(line.lstrip())
                                lines.insert(i + 1, " " * (indent + 4) + f"{var_name} = 0")
                                injected = True
                                break
                        if not injected:
                            code = f"{var_name} = 0\n" + code
                        else:
                            code = "\n".join(lines)
                        rules_applied.append("inject_missing_variable")
            else:
                code = "a = 0\n" + code
                rules_applied.append("inject_missing_variable")

        # RULE 5: missing closing parenthesis — '(' was never closed (Python 3.13)
        if "never closed" in error or "expected ')'" in error or "closing parenthesis" in error:
            lines = code.split("\n")
            for i, line in enumerate(lines):
                open_count = line.count("(")
                close_count = line.count(")")
                if open_count > close_count:
                    deficit = open_count - close_count
                    if line.rstrip().endswith(":"):
                        lines[i] = line.rstrip()[:-1] + ")" * deficit + ":"
                    else:
                        lines[i] = line + ")" * deficit
                    rules_applied.append("add_closing_paren")
                    break
            code = "\n".join(lines)

        # RULE 6: missing comma in function params (a b) → (a, b)
        if "invalid syntax" in error or "expected ','" in error or "expected ')'" in error:
            new_code = re.sub(r"(def\s+\w+\([^)]*\w)\s+(\w)(\s*[):])", r"\1, \2\3", code)
            if new_code != code:
                code = new_code
                if "add_closing_paren" not in rules_applied:
                    rules_applied.append("add_missing_comma")

        # RULE 7: wrong keyword (iff → if)
        if "SyntaxError" in error:
            typo_map = {
                "iff ": "if ",
                "eliff ": "elif ",
                "forr ": "for ",
                "whilee ": "while ",
                "defe ": "def ",
                "classs ": "class ",
                "returnn ": "return ",
            }
            for typo, correct in typo_map.items():
                if typo in code:
                    code = code.replace(typo, correct)
                    rules_applied.append("fix_keyword_typo")
                    break

        # RULE 8: missing import — inject import statement (no duplicates)
        if "ModuleNotFoundError" in error or "No module named" in error:
            mod_match = re.search(r"No module named '(\w+)", error)
            if mod_match:
                mod_name = mod_match.group(1)
                if f"import {mod_name}" not in code:
                    code = f"import {mod_name}\n" + code
                rules_applied.append("add_missing_import")

        # RULE 9: ImportError / wrong import name / wrong module attr
        if "ImportError" in error or "cannot import name" in error or ("AttributeError" in error and "module" in error):
            name_match = re.search(r"cannot import name '(\w+)' from '(\w+)", error)
            if name_match:
                bad_name = name_match.group(1)
                mod_name = name_match.group(2)
                # Special case: pathh → os.path, not just os
                if bad_name == "pathh" and mod_name == "os":
                    code = code.replace(f"from {mod_name} import {bad_name}", f"import {mod_name}")
                    code = code.replace(f"{bad_name}.", f"{mod_name}.path.")
                    code = code.replace(f"{bad_name}", f"{mod_name}.path")
                else:
                    code = code.replace(f"from {mod_name} import {bad_name}", f"import {mod_name}")
                    code = re.sub(rf"\b{bad_name}\.", f"{mod_name}.", code)
                rules_applied.append("fix_wrong_import")
            else:
                attr_match = re.search(r"module '(\w+)' has no attribute '(\w+)", error)
                if attr_match:
                    mod_name = attr_match.group(1)
                    bad_attr = attr_match.group(2)
                    if mod_name == "os" and bad_attr == "exists":
                        code = code.replace("os.exists", "os.path.exists")
                    else:
                        code = code.replace(f"{mod_name}.{bad_attr}", f"{mod_name}")
                    rules_applied.append("fix_wrong_attribute")

        # RULE 9c: NameError for wrong module name (maths, pathh, etc.)
        if "NameError" in error and not any("add_missing_import" in r or "fix_variable_typo" in r or "inject_missing_variable" in r for r in rules_applied):
            name_match = re.search(r"name '(\w+)' is not defined", error)
            if name_match:
                var_name = name_match.group(1)
                module_aliases = {
                    "maths": "math", "pathh": "os.path", "ospath": "os.path",
                    "syss": "sys", "jsons": "json", "rees": "re",
                    "mat": "math", "math": "math",
                }
                fix = module_aliases.get(var_name)
                if fix:
                    if "." in fix:
                        parts = fix.split(".")
                        code = f"import {parts[0]}\n" + code.replace(var_name, fix)
                    else:
                        code = f"import {fix}\n" + code.replace(var_name, fix)
                    rules_applied.append("fix_module_name_typo")

        # RULE 10: TypeError — int + str, wrong args
        if "TypeError" in error:
            if "unsupported operand" in error:
                type_match = re.search(r"unsupported operand type\(s\) for (.+): '(\w+)' and '(\w+)'", error)
                if type_match:
                    left_type = type_match.group(2)
                    right_type = type_match.group(3)
                    if left_type == "int" and right_type == "str":
                        code = re.sub(r"(\d+)(\s*\+\s*)", r"str(\1)\2", code, count=1)
                    elif left_type == "str" and right_type == "int":
                        code = re.sub(r"(\+\s*)(\d+)", r"\1str(\2)", code, count=1)
                    elif left_type == "list" and right_type == "int":
                        code = re.sub(r"(\+\s*)(\d+)", r"\1[\2]", code, count=1)
                    rules_applied.append("fix_type_mismatch")
            elif "can only concatenate" in error:
                concat_match = re.search(r"can only concatenate (\w+) \(not \"(\w+)\"\) to", error)
                if concat_match:
                    good_type = concat_match.group(1)
                    bad_type = concat_match.group(2)
                    if good_type == "str" and bad_type == "int":
                        code = re.sub(r"(\+\s*)(\d+)", r"\1str(\2)", code, count=1)
                    elif good_type == "list" and bad_type == "int":
                        code = re.sub(r"(\+\s*)(\d+)", r"\1[\2]", code, count=1)
                    elif good_type == "int" and bad_type == "str":
                        code = re.sub(r"(\d+)(\s*\+\s*)", r"str(\1)\2", code, count=1)
                    rules_applied.append("fix_type_mismatch")
            elif "missing" in error and ("positional argument" in error or "required" in error):
                num_match = re.search(r"missing (\d+) required positional argument", error)
                if not num_match:
                    num_match = re.search(r"missing (\d+) required", error)
                if num_match:
                    missing_count = int(num_match.group(1))
                else:
                    missing_count = 1
                func_match = re.search(r"(\w+)\(\) missing", error)
                if func_match:
                    func_name = func_match.group(1)
                    lines = code.split("\n")
                    for i, l in enumerate(lines):
                        if f"{func_name}(" in l and not l.strip().startswith("def "):
                            lines[i] = re.sub(rf"({func_name}\()([^)]*)\)", lambda m: m.group(1) + m.group(2) + ", " + ", ".join(["0"] * missing_count) + ")", l, count=1)
                            break
                    code = "\n".join(lines)
                else:
                    lines = code.split("\n")
                    for i, l in enumerate(lines):
                        if "(" in l and not l.strip().startswith("def "):
                            lines[i] = re.sub(r'(\w+\()([^)]*)\)', lambda m: m.group(1) + m.group(2) + ", " + ", ".join(["0"] * missing_count) + ")", l, count=1)
                            break
                    code = "\n".join(lines)
                rules_applied.append("add_missing_args")
            elif "takes" in error and "arguments" in error:
                if "missing" in error:
                    num_match = re.search(r"missing (\d+) required", error)
                    if num_match:
                        missing_count = int(num_match.group(1))
                    else:
                        missing_count = 1
                    code = re.sub(r'(\w+\()([^)]*)\)', lambda m: m.group(1) + m.group(2) + ", " + ", ".join(["0"] * missing_count) + ")", code, count=1)
                    rules_applied.append("add_missing_args")
                elif "given" in error:
                    code = re.sub(r", \d+\)", ")", code, count=1)
                    rules_applied.append("remove_extra_args")
            elif "unexpected keyword argument" in error:
                kw_match = re.search(r"unexpected keyword argument '(\w+)", error)
                if kw_match:
                    bad_kw = kw_match.group(1)
                    code = re.sub(rf"{bad_kw}=", "", code, count=1)
                    code = re.sub(r", ,", ", ", code)
                    code = re.sub(r", \)", ")", code)
                    rules_applied.append("fix_wrong_kwarg")

        # RULE 11: AttributeError
        if "AttributeError" in error:
            attr_match = re.search(r"'(\w+)' object has no attribute '(\w+)", error)
            mod_attr_match = re.search(r"module '(\w+)' has no attribute '(\w+)", error)
            bad_attr = None
            obj_type = None
            if attr_match:
                obj_type = attr_match.group(1)
                bad_attr = attr_match.group(2)
            elif mod_attr_match:
                obj_type = "module"
                bad_attr = mod_attr_match.group(2)
            if bad_attr:
                fixes = {
                    "lenght": "len", "lengh": "len", "length": "len",
                    "pie": "pi", "pi": "pi",
                    "apend": "append", "apend": "append",
                    "sortd": "sorted", "sortd": "sorted",
                    "lowerr": "lower", "upperr": "upper",
                    "splitr": "split", "joinr": "join",
                    "startswiths": "startswith", "endswiths": "endswith",
                }
                correct = fixes.get(bad_attr)
                if correct:
                    if correct == "len":
                        code = re.sub(rf"(\w+)\.{bad_attr}", r"len(\1)", code, count=1)
                    else:
                        code = code.replace(f".{bad_attr}", f".{correct}")
                    rules_applied.append("fix_attribute_typo")
                elif bad_attr == "append" and obj_type == "NoneType":
                    lines = code.split("\n")
                    for i, l in enumerate(lines):
                        if "= None" in l:
                            lines[i] = l.replace("= None", "= []")
                            rules_applied.append("fix_none_to_list")
                            break
                    code = "\n".join(lines)
            none_match = re.search(r"'NoneType' object has no attribute '(\w+)", error)
            if none_match and "fix_none_to_list" not in rules_applied:
                lines = code.split("\n")
                for i, l in enumerate(lines):
                    if "= None" in l:
                        lines[i] = l.replace("= None", "= []")
                        rules_applied.append("fix_none_to_list")
                        break
                code = "\n".join(lines)

        # RULE 12: IndexError — list overflow
        if "IndexError" in error:
            idx_match = re.search(r"list index out of range", error)
            if idx_match:
                code = re.sub(r"\[(\-?\d+)\]", "[0]", code, count=1)
                rules_applied.append("fix_index_overflow")

        # RULE 13: KeyError
        if "KeyError" in error:
            key_match = re.search(r"KeyError: (.+)", error)
            if key_match:
                key = key_match.group(1).strip().strip("'").strip('"')
                lines = code.split("\n")
                for i, l in enumerate(lines):
                    if "= {" in l and "}" in l and "'" in l:
                        if l.strip().endswith("}"):
                            lines[i] = l.replace("}", f", '{key}': 0}}")
                        else:
                            lines[i] = l.replace("}", f", '{key}': 0}}")
                        rules_applied.append("add_missing_key")
                        break
                    elif "= {" in l and l.strip().endswith("{}"):
                        lines[i] = l.replace("{}", f"{{'{key}': 0}}")
                        rules_applied.append("add_missing_key")
                        break
                code = "\n".join(lines)

        # RULE 14: ZeroDivisionError — also handle division by variable that is 0
        if "ZeroDivisionError" in error:
            var_match = re.search(r"division by zero", error)
            if var_match:
                lines = code.split("\n")
                for i, l in enumerate(lines):
                    stripped = l.strip()
                    if stripped.endswith("= 0") and i < len(lines) - 1:
                        lines[i] = l.replace("= 0", "= 1")
                        rules_applied.append("fix_division_by_zero")
                        break
                if "fix_division_by_zero" not in rules_applied:
                    code = re.sub(r"/\s*0\b", "/ 1", code, count=1)
                    code = re.sub(r"//\s*0\b", "// 1", code, count=1)
                    code = re.sub(r"%\s*0\b", "% 1", code, count=1)
                    rules_applied.append("fix_division_by_zero")
                else:
                    code = "\n".join(lines)

        # RULE 15: FileNotFoundError
        if "FileNotFoundError" in error or "No such file" in error:
            code = re.sub(r"'[^']*\.txt'", "'/dev/null'", code, count=1)
            rules_applied.append("fix_missing_file")

        # RULE 16: UnboundLocalError / scope — Python 3.13 message format
        if "UnboundLocalError" in error:
            var_match = re.search(r"cannot access local variable '(\w+)'", error)
            if not var_match:
                var_match = re.search(r"local variable '(\w+)' referenced before assignment", error)
            if var_match:
                var_name = var_match.group(1)
                lines = code.split("\n")
                if "+=" in code or "=" in code:
                    for i, l in enumerate(lines):
                        stripped = l.strip()
                        if stripped.startswith("def "):
                            indent = len(l) - len(l.lstrip())
                            if "+=" in code and var_name + "+=" in code.replace(" ", ""):
                                lines.insert(i + 1, " " * (indent + 4) + f"global {var_name}")
                                rules_applied.append("add_global_keyword")
                            else:
                                lines.insert(i + 1, " " * (indent + 4) + f"{var_name} = 0")
                                rules_applied.append("fix_unbound_local")
                            break
                else:
                    for i, l in enumerate(lines):
                        stripped = l.strip()
                        if stripped.startswith("def "):
                            indent = len(l) - len(l.lstrip())
                            lines.insert(i + 1, " " * (indent + 4) + f"{var_name} = 0")
                            rules_applied.append("fix_unbound_local")
                            break
                code = "\n".join(lines)

        # RULE 17: broken bracket — unclosed [ 
        if "never closed" in error and "[" in code:
            lines = code.split("\n")
            for i, line in enumerate(lines):
                open_sq = line.count("[")
                close_sq = line.count("]")
                if open_sq > close_sq:
                    lines[i] = line + "]" * (open_sq - close_sq)
                    rules_applied.append("add_closing_bracket")
                    break
            code = "\n".join(lines)

        return code, ",".join(rules_applied)

    def fix_indentation(self, code: str):
        lines = code.split("\n")
        fixed = []
        indent_stack = [0]
        block_keywords = re.compile(r"^(def\s|class\s|if\s|elif\s|else:|for\s|while\s|try:|except|finally:|with\s)")
        for line in lines:
            stripped = line.strip()
            if not stripped:
                fixed.append("")
                continue
            current_indent = len(line) - len(line.lstrip())
            if block_keywords.match(stripped):
                if current_indent < indent_stack[-1]:
                    while len(indent_stack) > 1 and indent_stack[-1] > current_indent:
                        indent_stack.pop()
                fixed.append(" " * current_indent + stripped)
                indent_stack.append(current_indent + 4)
            else:
                if current_indent == 0 and indent_stack[-1] > 0:
                    fixed.append(" " * indent_stack[-1] + stripped)
                else:
                    fixed.append(" " * current_indent + stripped)
        return "\n".join(fixed)

    def fix_missing_quote(self, code: str):
        lines = code.split("\n")
        fixed = []
        for line in lines:
            single_quotes = line.count("'")
            double_quotes = line.count('"')
            if single_quotes % 2 != 0 and double_quotes % 2 != 0:
                first_sq = line.find("'")
                first_dq = line.find('"')
                if first_sq < first_dq:
                    line = line + "'"
                else:
                    line = line + '"'
            elif single_quotes % 2 != 0:
                last_pos = line.rfind("'")
                if last_pos == 0 or line[last_pos - 1] != "\\":
                    line = line + "'"
            elif double_quotes % 2 != 0:
                last_pos = line.rfind('"')
                if last_pos == 0 or line[last_pos - 1] != "\\":
                    line = line + '"'
            fixed.append(line)
        return "\n".join(fixed)

# =========================================================
# RULE EXTRACTOR — learns from successful (broken → fixed) diffs
# =========================================================
class RuleExtractor:
    META_CLASSES = {
        "SyntaxError": "syntax", "IndentationError": "syntax", "TabError": "syntax",
        "NameError": "binding", "UnboundLocalError": "binding", "ModuleNotFoundError": "binding",
        "ImportError": "binding",
        "TypeError": "type",
        "AttributeError": "type",
        "IndexError": "runtime", "KeyError": "runtime", "ZeroDivisionError": "runtime",
        "FileNotFoundError": "runtime", "ValueError": "runtime", "RuntimeError": "runtime",
    }

    @staticmethod
    def _error_sig(error):
        last_line = error.strip().split("\n")[-1]
        return last_line.split(":")[0] if ":" in last_line else last_line[:50]

    @staticmethod
    def _meta_class(error_sig):
        return RuleExtractor.META_CLASSES.get(error_sig, "unknown")

    def extract(self, broken, fixed, error):
        if broken == fixed:
            return (False, None, "broken and fixed code are identical — no diff to extract")
        error_sig = self._error_sig(error)
        broken_lines = broken.splitlines()
        fixed_lines = fixed.splitlines()
        remover = []
        adder = []
        diff = difflib.unified_diff(broken_lines, fixed_lines)
        for line in diff:
            if line.startswith('---') or line.startswith('+++') or line.startswith('@@'):
                continue
            if line.startswith('-'):
                remover.append(line[1:])
            elif line.startswith('+'):
                adder.append(line[1:])
        if not remover and not adder:
            return (False, None, "diff produced no removable or addable patterns")
        remove_pat = "\n".join(remover)
        add_pat = "\n".join(adder)
        return error_sig, remove_pat, add_pat

    def apply(self, code, error, rules):
        error_sig = self._error_sig(error)
        meta = self._meta_class(error_sig)
        # Pass 1: exact error signature match
        for sig, remove_pat, add_pat, uses, wins, score in rules:
            if score < 0.5:
                continue
            if sig != error_sig:
                continue
            if remove_pat and remove_pat in code:
                new_code = code.replace(remove_pat, add_pat, 1)
                if new_code != code:
                    return new_code, True, remove_pat
        # Pass 2: same meta-class fallback (generalization)
        for sig, remove_pat, add_pat, uses, wins, score in rules:
            if score < 0.7:
                continue
            if sig == error_sig:
                continue
            if self._meta_class(sig) != meta or meta == "unknown":
                continue
            if remove_pat and remove_pat in code:
                new_code = code.replace(remove_pat, add_pat, 1)
                if new_code != code:
                    return new_code, True, remove_pat
        return code, False, None

# =========================================================
# META-CONTROLLER — learns how to learn (adjusts training distribution)
# =========================================================
class MetaController:
    """Tracks per-family performance and adjusts generator weights
    to focus training on weak areas. Also tracks which strategy
    (learned vs hardcoded) works better per meta-class."""

    def __init__(self, generator):
        self.gen = generator
        self.family_attempts = {}
        self.family_successes = {}
        self.meta_strategy = {}  # meta_class -> {"learned": wins, "hardcoded": wins}
        self.adaptation_count = 0

    def record(self, family, success, strategy_used, error_sig=None):
        self.family_attempts[family] = self.family_attempts.get(family, 0) + 1
        if success:
            self.family_successes[family] = self.family_successes.get(family, 0) + 1
        if strategy_used and error_sig:
            meta = RuleExtractor._meta_class(error_sig)
            if meta not in self.meta_strategy:
                self.meta_strategy[meta] = {"learned": 0, "hardcoded": 0}
            if "learned_reuse" in strategy_used:
                self.meta_strategy[meta]["learned"] += 1 if success else 0
            elif "learned" not in strategy_used:
                self.meta_strategy[meta]["hardcoded"] += 1 if success else 0

    def adapt(self):
        """Adjust difficulty weights: increase weight for weak families,
        decrease for strong ones. Keeps total weight normalized."""
        if not self.family_attempts:
            return
        new_weights = {}
        for family, base_w in self.gen.difficulty_weights.items():
            attempts = self.family_attempts.get(family, 0)
            successes = self.family_successes.get(family, 0)
            if attempts < 5:
                new_weights[family] = base_w
                continue
            fail_rate = 1.0 - (successes / attempts)
            # Boost weak areas, reduce strong ones
            adjustment = 1.0 + (fail_rate - 0.1) * 0.5
            adjustment = max(0.5, min(2.0, adjustment))
            new_weights[family] = base_w * adjustment
        # Normalize
        total = sum(new_weights.values())
        for f in new_weights:
            new_weights[f] = new_weights[f] / total
        self.gen.difficulty_weights = new_weights
        self.adaptation_count += 1

    def best_strategy(self, error_sig):
        """Returns 'learned' or 'hardcoded' based on past performance."""
        meta = RuleExtractor._meta_class(error_sig)
        if meta not in self.meta_strategy:
            return None
        stats = self.meta_strategy[meta]
        if stats["learned"] > stats["hardcoded"]:
            return "learned"
        return "hardcoded"

    def stats(self):
        lines = [f"  Adaptations: {self.adaptation_count}"]
        if self.meta_strategy:
            lines.append("  Strategy preference by meta-class:")
            for meta, stats in sorted(self.meta_strategy.items()):
                pref = "learned" if stats["learned"] > stats["hardcoded"] else "hardcoded"
                lines.append(f"    {meta:15s}  learned={stats['learned']:3d}  hardcoded={stats['hardcoded']:3d}  → {pref}")
        weak = []
        for family in sorted(self.family_attempts.keys()):
            attempts = self.family_attempts[family]
            successes = self.family_successes.get(family, 0)
            if attempts >= 5:
                rate = successes / attempts
                if rate < 0.8:
                    weak.append(f"    {family:30s}  {rate:.0%} ({successes}/{attempts})")
        if weak:
            lines.append("  Weak families (training focus):")
            lines.extend(weak)
        return "\n".join(lines)

# =========================================================
# PARALLEL WORKER (module-level for pickling)
# =========================================================
def _parallel_worker(args):
    batch_size, seed, multi_error, worker_id = args
    random.seed(seed)
    db_path = WORKER_DB_TEMPLATE.format(worker_id)
    loop = EFLLoop(multi_error=multi_error, db_path=db_path)
    results = []
    for _ in range(batch_size):
        result = loop.step_silent()
        results.append(result)
    # Also return learned rules and extracted rules from worker DB
    learned = loop.db.fetch_learned_rules()
    extracted = loop.db.fetch_extracted_rules()
    loop.db.conn.close()
    return results, learned, extracted

# =========================================================
# RAM AI LOOP ENGINE
# =========================================================
class EFLLoop:
    def __init__(self, multi_error=1, db_path=None):
        self.db = MemoryDB(db_path=db_path)
        self.gen = BrokenCodeGenerator()
        self.ast_injector = ASTErrorInjector()
        self.exec = Executor()
        self.repair = RepairEngine()
        self.multi_error = multi_error
        self.extractor = RuleExtractor()
        self.analyzer = StaticAnalyzer()
        self.meta = MetaController(self.gen)
        self.pass_count = 0
        self.fail_count = 0
        self.family_stats = {}
        self.learned_reuse_count = 0
        self.chain_fix_count = 0

    def step_silent(self):
        """Run one step without printing — for parallel workers."""
        expected_output = None
        use_ast = random.random() < 0.3
        if use_ast:
            result = self.ast_injector.generate()
            code, family = result[0], result[1]
            if len(result) > 2:
                expected_output = result[2]
        else:
            code, family = self.gen.generate(n_errors=self.multi_error)

        ok, err = self.exec.run(code)
        if ok:
            return ("pass", family, None, None, None, None, expected_output)

        extracted_rules = self.db.fetch_extracted_rules()
        candidates = []
        learned_fixed, learned_reused, matched_remove_pat = self.extractor.apply(code, err, extracted_rules)
        if learned_reused:
            candidates.append(("learned_reuse", learned_fixed, True))
        hardcoded_fixed, hardcoded_rule = self.repair.fix(code, err)
        if hardcoded_rule:
            candidates.append((hardcoded_rule, hardcoded_fixed, False))

        best_fixed = None
        best_rule = ""
        best_reused = False
        best_ok = False
        best_err = None
        for cand_rule, cand_code, cand_reused in candidates:
            ok_cand, err_cand = self.exec.run(cand_code)
            if ok_cand and not best_ok:
                best_fixed = cand_code
                best_rule = cand_rule
                best_reused = cand_reused
                best_ok = True
                best_err = None
            elif not best_ok:
                if best_fixed is None:
                    best_fixed = cand_code
                    best_rule = cand_rule
                    best_reused = cand_reused
                    best_err = err_cand

        fixed = best_fixed or code
        rule = best_rule
        reused = best_reused
        ok2 = best_ok
        err2 = best_err

        if ok2 and expected_output is not None:
            try:
                import sys as _sys
                from io import StringIO as _SI
                _old = _sys.stdout
                _sys.stdout = _SI()
                _env = {}
                exec(fixed, {}, _env)
                _actual = _sys.stdout.getvalue().strip()
                _sys.stdout = _old
                if _actual != expected_output:
                    ok2 = False
                    err2 = f"SemanticError: expected {expected_output!r}, got {_actual!r}"
            except Exception as e:
                _sys.stdout = _old
                ok2 = False
                err2 = str(e)

        if reused and matched_remove_pat is not None:
            self.db.update_extracted_rule(RuleExtractor._error_sig(err), matched_remove_pat, bool(ok2))

        if not ok2:
            for attempt in range(3):
                if ok2 or not err2:
                    break
                fixed2, rule2 = self.repair.fix(fixed, err2)
                if fixed2 == fixed:
                    break
                fixed = fixed2
                rule = rule + "," + rule2 if rule else rule2
                ok2, err2 = self.exec.run(fixed)
            if ok2:
                self.chain_fix_count += 1

        success = 1 if ok2 else 0
        self.meta.record(family, bool(success), rule, error_sig=RuleExtractor._error_sig(err))
        return ("fix" if success else "fail", family, code, err, fixed, rule, expected_output)

    def run_parallel(self, steps=1000, workers=4):
        """Run steps in parallel using multiprocessing with per-worker DBs."""
        from multiprocessing import Pool
        import os, shutil

        # Copy main DB to worker DBs so workers inherit learned rules
        self.db.conn.commit()
        for w in range(workers):
            wpath = WORKER_DB_TEMPLATE.format(w)
            if os.path.exists(DB_PATH):
                shutil.copy2(DB_PATH, wpath)

        batch = steps // workers
        remainder = steps % workers
        tasks = []
        for w in range(workers):
            batch_size = batch + (remainder if w == 0 else 0)
            tasks.append((batch_size, random.randint(0, 2**31), self.multi_error, w))

        print(f"Running {steps} steps on {workers} workers (multi_error={self.multi_error})...")
        with Pool(workers) as pool:
            all_worker_data = pool.map(_parallel_worker, tasks)

        # Unpack results and merge worker rules into main DB
        flat = []
        for worker_results, worker_learned, worker_extracted in all_worker_data:
            flat.extend(worker_results)
            # Merge learned rules from worker into main DB
            for name, sc, fc, conf in worker_learned:
                self.db.cur.execute("SELECT id, success_count, failure_count FROM learned_fixes WHERE rule_name = ?", (name,))
                row = self.db.cur.fetchone()
                if row:
                    rid, old_sc, old_fc = row
                    self.db.cur.execute("UPDATE learned_fixes SET success_count = ?, failure_count = ?, confidence = ? WHERE id = ?",
                                        (old_sc + sc, old_fc + fc, (old_sc + sc) / max(old_sc + sc + old_fc + fc, 1), rid))
                else:
                    self.db.cur.execute("INSERT OR IGNORE INTO learned_fixes (rule_name, success_count, failure_count, confidence) VALUES (?, ?, ?, ?)",
                                        (name, sc, fc, conf))
            # Merge extracted rules from worker into main DB
            for sig, rpat, apat, uses, wins, score in worker_extracted:
                self.db.add_extracted_rule(sig, rpat, apat)
        self.db.conn.commit()

        # Clean up worker DB files
        for w in range(workers):
            wpath = WORKER_DB_TEMPLATE.format(w)
            if os.path.exists(wpath):
                os.remove(wpath)

        pass_count = 0
        fail_count = 0
        family_stats = {}
        reuse_count = 0
        chain_count = 0

        for status, family, code, err, fixed, rule, expected in flat:
            if status == "pass":
                pass_count += 1
                family_stats[family] = family_stats.get(family, [0, 0])
                family_stats[family][0] += 1
                continue

            success = 1 if status == "fix" else 0
            if success:
                pass_count += 1
            else:
                fail_count += 1

            family_stats[family] = family_stats.get(family, [0, 0])
            family_stats[family][0 if success else 1] += 1

            if code and err and fixed:
                case_id = self.db.insert(
                    broken=code,
                    err_type=RuleExtractor._error_sig(err),
                    err_msg=err,
                    fixed=fixed,
                    rule=rule or "",
                    success=success
                )
                if rule:
                    for r in rule.split(","):
                        self.db.learn_rule(r, err, fixed, bool(success), case_id)
                if success and not (rule and "learned_reuse" in rule):
                    esig, rpat, apat = self.extractor.extract(code, fixed, err)
                    if esig and rpat:
                        self.db.add_extracted_rule(esig, rpat, apat)
                if rule and "learned_reuse" in rule and success:
                    reuse_count += 1

        self.pass_count = pass_count
        self.fail_count = fail_count
        self.family_stats = family_stats
        self.learned_reuse_count = reuse_count
        self.chain_fix_count = chain_count

        # Feed family stats into meta-controller and adapt
        for fam, (p, f) in family_stats.items():
            self.meta.family_attempts[fam] = self.meta.family_attempts.get(fam, 0) + p + f
            self.meta.family_successes[fam] = self.meta.family_successes.get(fam, 0) + p
        self.meta.adapt()

        self._print_stats()

    def _print_stats(self):
        total, fixed, rules = self.db.stats()
        print("\n" + "=" * 60)
        print("FINAL STATS")
        print("=" * 60)
        print(f"  Total cases stored: {total}")
        print(f"  Successfully fixed: {fixed}")
        print(f"  Failed to fix:      {total - fixed}")
        print(f"  Learned rules:      {rules}")
        print(f"  This session:       {self.pass_count} passed, {self.fail_count} failed")
        print(f"  Fix rate:           {self.pass_count / max(self.pass_count + self.fail_count, 1) * 100:.1f}%")
        print(f"  Learned rule reuses: {self.learned_reuse_count}")
        print(f"  Chain multi-step fixes: {self.chain_fix_count}")
        print()
        if self.family_stats:
            print("ERROR FAMILY COVERAGE:")
            for fam in sorted(self.family_stats.keys()):
                p, f = self.family_stats[fam]
                rate = p / max(p + f, 1) * 100
                print(f"  {fam:30s}  pass={p:3d}  fail={f:3d}  rate={rate:5.1f}%")
        print()
        learned = self.db.fetch_learned_rules()
        if learned:
            print("LEARNED RULES (by confidence):")
            for name, sc, fc, conf in learned:
                print(f"  {name:30s}  success={sc:4d}  fail={fc:4d}  confidence={conf:.2f}")
        print()
        extracted = self.db.fetch_extracted_rules()
        if extracted:
            print("EXTRACTED RULES (self-learned diffs):")
            for sig, rpat, apat, uses, wins, score in extracted:
                rpat_short = rpat[:40].replace('\n', '\\n') if rpat else ""
                print(f"  {sig:20s}  uses={uses:3d}  wins={wins:3d}  score={score:.2f}  {rpat_short}")
        print()
        print("META-CONTROLLER (learning strategy):")
        print(self.meta.stats())

    def step(self):
        expected_output = None
        use_ast = random.random() < 0.3
        if use_ast:
            result = self.ast_injector.generate()
            code, family = result[0], result[1]
            if len(result) > 2:
                expected_output = result[2]
        else:
            code, family = self.gen.generate(n_errors=self.multi_error)
        print(f"\n[GEN] family={family}\n{code}")

        ok, err = self.exec.run(code)
        if ok:
            if expected_output is not None:
                print(f"[OK] executed but may be semantically wrong (expected: {expected_output})")
            else:
                print("[OK] executed clean (unexpected for broken generator)")
            self.pass_count += 1
            return
        print("[ERROR]", err)

        extracted_rules = self.db.fetch_extracted_rules()

        # BEAM SEARCH: try multiple fix paths and pick the best
        candidates = []
        learned_fixed, learned_reused, matched_remove_pat = self.extractor.apply(code, err, extracted_rules)
        if learned_reused:
            candidates.append(("learned_reuse", learned_fixed, True))
        hardcoded_fixed, hardcoded_rule = self.repair.fix(code, err)
        if hardcoded_rule:
            candidates.append((hardcoded_rule, hardcoded_fixed, False))

        best_fixed = None
        best_rule = ""
        best_reused = False
        best_ok = False
        best_err = None
        for cand_rule, cand_code, cand_reused in candidates:
            ok_cand, err_cand = self.exec.run(cand_code)
            if ok_cand and not best_ok:
                best_fixed = cand_code
                best_rule = cand_rule
                best_reused = cand_reused
                best_ok = True
                best_err = None
            elif not best_ok and best_fixed is None:
                best_fixed = cand_code
                best_rule = cand_rule
                best_reused = cand_reused
                best_err = err_cand

        fixed = best_fixed or code
        rule = best_rule
        reused = best_reused
        ok2 = best_ok
        err2 = best_err

        print("[FIXED]\n", fixed)
        print("[RULES]", rule)
        print("[RE-RUN]", "SUCCESS" if ok2 else f"FAILED: {err2}")

        if ok2 and expected_output is not None:
            try:
                import sys as _sys
                from io import StringIO as _SI
                _old = _sys.stdout
                _sys.stdout = _SI()
                _env = {}
                exec(fixed, {}, _env)
                _actual = _sys.stdout.getvalue().strip()
                _sys.stdout = _old
                if _actual != expected_output:
                    print(f"[SEMANTIC MISMATCH] expected: {expected_output}, got: {_actual}")
                    ok2 = False
                    err2 = f"SemanticError: expected {expected_output!r}, got {_actual!r}"
            except Exception as e:
                _sys.stdout = _old
                ok2 = False
                err2 = str(e)

        if reused and matched_remove_pat is not None:
            self.db.update_extracted_rule(RuleExtractor._error_sig(err), matched_remove_pat, bool(ok2))
            if ok2:
                self.learned_reuse_count += 1

        if not ok2:
            for attempt in range(3):
                if ok2 or not err2:
                    break
                print(f"[CHAIN STEP {attempt+1}] re-fixing...")
                fixed2, rule2 = self.repair.fix(fixed, err2)
                if fixed2 == fixed:
                    break
                fixed = fixed2
                rule = rule + "," + rule2 if rule else rule2
                ok2, err2 = self.exec.run(fixed)
                print("[CHAIN RESULT]", "SUCCESS" if ok2 else f"FAILED: {err2}")
            if ok2:
                self.chain_fix_count += 1

        success = 1 if ok2 else 0
        self.meta.record(family, bool(success), rule, error_sig=RuleExtractor._error_sig(err))
        if success:
            self.pass_count += 1
        else:
            self.fail_count += 1
        self.family_stats[family] = self.family_stats.get(family, [0, 0])
        self.family_stats[family][0 if success else 1] += 1

        case_id = self.db.insert(
            broken=code,
            err_type=RuleExtractor._error_sig(err),
            err_msg=err,
            fixed=fixed,
            rule=rule,
            success=success
        )
        if rule:
            for r in rule.split(","):
                self.db.learn_rule(r, err, fixed, bool(success), case_id)
        if success and not reused:
            esig, rpat, apat = self.extractor.extract(code, fixed, err)
            if esig and rpat:
                self.db.add_extracted_rule(esig, rpat, apat)

    def run(self, steps=10):
        for i in range(steps):
            print("\n" + "=" * 60)
            print(f"STEP {i+1}/{steps}")
            print("=" * 60)
            self.step()
            if (i + 1) % 20 == 0:
                self.meta.adapt()
                print(f"[META] adapted training distribution (adaptation #{self.meta.adaptation_count})")
        self._print_stats()

    def self_analyze(self, filepath=None):
        """Run static analysis on this file (or a given file) and report findings."""
        target = filepath or __file__
        print(f"\n{'=' * 60}")
        print(f"STATIC ANALYSIS: {target}")
        print(f"{'=' * 60}")
        with open(target, "r") as f:
            code = f.read()
        findings = self.analyzer.analyze(code, target)
        if not findings:
            print("  No issues found. Code is clean.")
            return
        print(f"  {len(findings)} finding(s) across {len(set(f['layer'] for f in findings))} layer(s):")
        print()
        print(self.analyzer.summary())
        print()
        high = [f for f in findings if f["severity"] == "high"]
        medium = [f for f in findings if f["severity"] == "medium"]
        low = [f for f in findings if f["severity"] == "low"]
        print(f"  Summary: {len(high)} high, {len(medium)} medium, {len(low)} low")

# =========================================================
# ENTRY
# =========================================================
if __name__ == "__main__":
    import sys, os
    steps = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 60
    fresh = "--fresh" in sys.argv
    parallel = "--parallel" in sys.argv
    analyze = "--analyze" in sys.argv
    workers = 4
    multi_error = 1
    analyze_target = None
    for i, a in enumerate(sys.argv):
        if a == "--workers" and i + 1 < len(sys.argv):
            workers = int(sys.argv[i + 1])
        if a == "--multi-error" and i + 1 < len(sys.argv):
            multi_error = int(sys.argv[i + 1])
        if a == "--analyze" and i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"):
            analyze_target = sys.argv[i + 1]
    if fresh and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    system = EFLLoop(multi_error=multi_error)
    if analyze:
        system.self_analyze(analyze_target)
    elif parallel:
        system.run_parallel(steps=steps, workers=workers)
    else:
        system.run(steps=steps)
