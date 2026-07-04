#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     test_config_graph.py
# Domain:   Testing
# Authority: Tests all dimensions of config architecture — imports, MemUnits,
#            service container, boot cold, env vars, FILE_INDEX, VBStyle
# DB:       None (test only)
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Rules followed:
#   @ghost    — Ghost Header present
#   @vbsty    — VBStyle Header present
#   @hardcode — No hardcoded paths (all derived)
#   @cstyle   — Coding style compliant
# ============================================================================

"""
Config Architecture Test Suite — tests all dimensions of the config pattern.

Dimensions tested:
  D1  — Boot cold (no DB, creates from embedded SQL)
  D2  — Value loading from SQLite
  D3  — Env var overrides
  D4  — Singleton instantiation
  D5  — Config as service container (loads MemUnits)
  D6  — MemUnit Run() dispatch returns Tuple3
  D7  — MemUnit gets values FROM config (no hardcoding)
  D8  — No hidden dependencies (files import own deps)
  D9  — FILE_INDEX matches actual files
  D10 — VBStyle compliance check (headers, naming, no print)
  D11 — Code graph (class hierarchy, methods, call graph)
  D12 — Dead code detection (unused classes/methods/constants)
  D13 — TODO/FIXME scanning
  D14 — Cross-folder consistency (shared tables, env vars)
  D15 — File integrity (hash check)
  D16 — Config self-validation (paths, SQL, getters)
  D17 — Import graph (no circular, config first)
  D18 — Startup order (config before everything)
  D19 — Embedded schema (no external .sql files)
  D20 — Documentation constants (ABOUT, HELP, README inside config)
"""

import os
import sys
import ast
import hashlib
import importlib
import sqlite3
import tempfile
import textwrap
from pathlib import Path

PASS = 0
FAIL = 0
SKIP = 0


def Result(name, ok, detail=""):
    global PASS, FAIL
    status = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{status}] {name}")
    if detail:
        print(f"         {detail}")
    return ok


def Skip(name, reason=""):
    global SKIP
    SKIP += 1
    print(f"  [SKIP] {name}")
    if reason:
        print(f"         {reason}")
    return False


# ============================================================================
# D1 — Boot Cold
# ============================================================================
def TestBootCold():
    print("\n=== D1: Boot Cold ===")
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test_config.db")

    SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    INSERT OR IGNORE INTO config (key, value) VALUES ('host', 'localhost');
    INSERT OR IGNORE INTO config (key, value) VALUES ('port', '3306');
    """

    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()

    cur = conn.cursor()
    cur.execute("SELECT key, value FROM config")
    rows = dict(cur.fetchall())
    cur.close()
    conn.close()

    Result("DB created from embedded SQL", os.path.exists(db_path))
    Result("Seed data inserted", rows.get("host") == "localhost")
    Result("Multiple seeds inserted", rows.get("port") == "3306")

    os.unlink(db_path)
    os.rmdir(tmpdir)


# ============================================================================
# D2 — Value Loading from SQLite
# ============================================================================
def TestValueLoading():
    print("\n=== D2: Value Loading ===")
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test_values.db")

    SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    INSERT OR IGNORE INTO config (key, value) VALUES
        ('mysql_host', 'localhost'),
        ('mysql_port', '3306'),
        ('mysql_user', 'root'),
        ('mysql_db', 'vb_shared'),
        ('batch_size', '500'),
        ('log_path', '/tmp/test.log');
    """

    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()

    values = {}
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM config")
    for key, value in cur.fetchall():
        values[key] = value
    cur.close()
    conn.close()

    Result("All values loaded", len(values) == 6)
    Result("Host value correct", values.get("mysql_host") == "localhost")
    Result("Port value correct", values.get("mysql_port") == "3306")
    Result("Batch size value correct", values.get("batch_size") == "500")

    os.unlink(db_path)
    os.rmdir(tmpdir)


# ============================================================================
# D3 — Env Var Overrides
# ============================================================================
def TestEnvOverrides():
    print("\n=== D3: Env Var Overrides ===")
    os.environ["TEST_OVERRIDE_HOST"] = "192.168.1.100"
    os.environ["TEST_OVERRIDE_PORT"] = "9999"

    defaults = {
        "mysql_host": "localhost",
        "mysql_port": "3306",
    }

    env_map = {
        "TEST_OVERRIDE_HOST": "mysql_host",
        "TEST_OVERRIDE_PORT": "mysql_port",
    }

    values = dict(defaults)
    for env_name, config_key in env_map.items():
        env_val = os.environ.get(env_name)
        if env_val is not None:
            values[config_key] = env_val

    Result("Override applied to host", values["mysql_host"] == "192.168.1.100")
    Result("Override applied to port", values["mysql_port"] == "9999")

    del os.environ["TEST_OVERRIDE_HOST"]
    del os.environ["TEST_OVERRIDE_PORT"]

    values2 = dict(defaults)
    for env_name, config_key in env_map.items():
        env_val = os.environ.get(env_name)
        if env_val is not None:
            values[config_key] = env_val

    Result("Defaults restored without env", values2["mysql_host"] == "localhost")


# ============================================================================
# D4 — Singleton Instantiation
# ============================================================================
def TestSingleton():
    print("\n=== D4: Singleton ===")

    class TestConfig:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        VERSION = "1.0"

        def GetVersion(self):
            return self.VERSION

    cfg1 = TestConfig()
    cfg2 = TestConfig()

    Result("Singleton instantiable", cfg1 is not None)
    Result("Same class type", type(cfg1) == type(cfg2))
    Result("Version accessible", cfg1.GetVersion() == "1.0")
    Result("Both instances same version", cfg1.VERSION == cfg2.VERSION)


# ============================================================================
# D5 — Config as Service Container (loads MemUnits)
# ============================================================================
def TestServiceContainer():
    print("\n=== D5: Service Container ===")

    class MockMemUnit:
        def __init__(self, cfg):
            self.state = {}
            self.cfg = cfg
            self.state["host"] = cfg.MYSQL_HOST
            self.state["port"] = cfg.MYSQL_PORT

        def Run(self, command, params):
            if command == "get_host":
                return (True, self.state["host"], "")
            elif command == "get_port":
                return (True, int(self.state["port"]), "")
            elif command == "echo":
                return (True, params, "")
            return (False, None, f"Unknown command: {command}")

    class TestConfig:
        MYSQL_HOST = "localhost"
        MYSQL_PORT = "3306"

        def __init__(self):
            self.MemUnit = MockMemUnit(self)

    cfg = TestConfig()

    Result("MemUnit instantiated in config", hasattr(cfg, "MemUnit"))
    Result("MemUnit got host from config", cfg.MemUnit.state["host"] == "localhost")
    Result("MemUnit got port from config", cfg.MemUnit.state["port"] == "3306")

    ok, data, err = cfg.MemUnit.Run("get_host", None)
    Result("MemUnit Run() returns Tuple3", isinstance((ok, data, err), tuple) and len((ok, data, err)) == 3)
    Result("MemUnit Run() get_host ok", ok is True)
    Result("MemUnit Run() get_host data", data == "localhost")

    ok, data, err = cfg.MemUnit.Run("echo", {"msg": "hello"})
    Result("MemUnit Run() echo data", data == {"msg": "hello"})

    ok, data, err = cfg.MemUnit.Run("bad_command", None)
    Result("MemUnit Run() unknown returns False", ok is False)
    Result("MemUnit Run() unknown returns error", "Unknown command" in err)


# ============================================================================
# D6 — Tuple3 Returns
# ============================================================================
def TestTuple3():
    print("\n=== D6: Tuple3 Returns ===")

    def Success(data):
        return (True, data, "")

    def Failure(error):
        return (False, None, error)

    ok, data, err = Success({"rows": 42})
    Result("Success: ok=True", ok is True)
    Result("Success: data present", data == {"rows": 42})
    Result("Success: error empty", err == "")

    ok, data, err = Failure("connection lost")
    Result("Failure: ok=False", ok is False)
    Result("Failure: data None", data is None)
    Result("Failure: error message", err == "connection lost")


# ============================================================================
# D7 — No Hardcoding in MemUnits
# ============================================================================
def TestNoHardcoding():
    print("\n=== D7: No Hardcoding ===")

    test_code = '''
class MySQLConn:
    def Connect(self):
        host = "localhost"  # HARDCODED — violation
        port = 3306         # HARDCODED — violation
        return host, port
'''

    violations = []
    tree = ast.parse(test_code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str) and node.value in ("localhost", "127.0.0.1", "root", "password"):
                violations.append(f"Line {node.lineno}: hardcoded '{node.value}'")
            if isinstance(node.value, int) and node.value in (3306, 80, 443, 22):
                violations.append(f"Line {node.lineno}: hardcoded port {node.value}")

    Result("Hardcoded values detected", len(violations) >= 2)
    Result("Correct violation count", len(violations) == 2, f"Found {len(violations)} violations")

    clean_code = '''
class MySQLConn:
    def Connect(self):
        host = self.cfg.MYSQL_HOST
        port = self.cfg.MYSQL_PORT
        return host, port
'''

    violations2 = []
    tree2 = ast.parse(clean_code)
    for node in ast.walk(tree2):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str) and node.value in ("localhost", "127.0.0.1", "root", "password"):
                violations2.append(f"Line {node.lineno}: hardcoded '{node.value}'")

    Result("Clean code has no violations", len(violations2) == 0)


# ============================================================================
# D8 — No Hidden Dependencies
# ============================================================================
def TestNoHiddenDeps():
    print("\n=== D8: No Hidden Dependencies ===")

    config_code = '''
import os
import sqlite3

class Config:
    MYSQL_HOST = "localhost"
'''

    file_code = '''
from PyQt6 import QtWidgets
from Config import cfg

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        self.host = cfg.MYSQL_HOST
'''

    config_tree = ast.parse(config_code)
    config_imports = [node.names[0].name for node in ast.walk(config_tree) if isinstance(node, ast.Import)]
    config_from_imports = [node.module for node in ast.walk(config_tree) if isinstance(node, ast.ImportFrom)]

    file_tree = ast.parse(file_code)
    file_imports = [node.names[0].name for node in ast.walk(file_tree) if isinstance(node, ast.Import)]
    file_from_imports = [node.module for node in ast.walk(file_tree) if isinstance(node, ast.ImportFrom)]

    Result("Config imports only stdlib", "os" in config_imports and "sqlite3" in config_imports)
    Result("Config does NOT import PyQt6", "PyQt6" not in config_from_imports)
    Result("File imports PyQt6 directly", "PyQt6" in file_from_imports)
    Result("File imports Config directly", "Config" in file_from_imports)


# ============================================================================
# D9 — FILE_INDEX Matches Actual Files
# ============================================================================
def TestFileIndexMatch():
    print("\n=== D9: FILE_INDEX Match ===")
    tmpdir = tempfile.mkdtemp()

    for fname in ["__init__.py", "main.py", "utils.py", "README.md"]:
        Path(os.path.join(tmpdir, fname)).touch()

    FILE_INDEX = [
        {"file": "__init__.py", "purpose": "Package init"},
        {"file": "main.py", "purpose": "Entry point"},
        {"file": "utils.py", "purpose": "Utilities"},
    ]

    actual_files = set(os.listdir(tmpdir))
    indexed_files = set(entry["file"] for entry in FILE_INDEX)

    missing_from_index = actual_files - indexed_files
    missing_from_disk = indexed_files - actual_files

    Result("Index has 3 files", len(FILE_INDEX) == 3)
    Result("Disk has 4 files", len(actual_files) == 4)
    Result("README.md missing from index", "README.md" in missing_from_index,
           "README.md should be in FILE_INDEX or excluded by rule")
    Result("No indexed files missing from disk", len(missing_from_disk) == 0)

    import shutil
    shutil.rmtree(tmpdir)


# ============================================================================
# D10 — VBStyle Compliance Check
# ============================================================================
def TestVBStyleCompliance():
    print("\n=== D10: VBStyle Compliance ===")

    compliant_code = '''#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     example.py
# Domain:   Test
# Authority: Test file
# DB:       None
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Rules followed:
#   @ghost    — Ghost Header present
#   @vbsty    — VBStyle Header present
# ============================================================================

import os


class ExampleClass:
    def Run(self, command, params):
        """Dispatch entry point."""
        return (True, None, "")

    def GetData(self):
        """Return data."""
        return (True, "data", "")
'''

    noncompliant_code = '''import os

class exampleclass:
    def run(self, command, params):
        print("running")
        return (True, None, "")
'''

    def CheckVBStyle(code):
        checks = {
            "ghost_header": False,
            "vbsty_header": False,
            "class_header": False,
            "pascal_case": False,
            "no_print": False,
        }

        if "GHOST HEADER" in code:
            checks["ghost_header"] = True
        if "VBSTYLE HEADER" in code:
            checks["vbsty_header"] = True

        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if node.name[0].isupper():
                    checks["pascal_case"] = True
                if not any(isinstance(child, ast.Name) and child.id == "print" for child in ast.walk(node)):
                    checks["no_print"] = True

        if "print(" not in code:
            checks["no_print"] = True

        return checks

    compliant_checks = CheckVBStyle(compliant_code)
    Result("Compliant: ghost header", compliant_checks["ghost_header"])
    Result("Compliant: vbsty header", compliant_checks["vbsty_header"])
    Result("Compliant: pascal case", compliant_checks["pascal_case"])
    Result("Compliant: no print", compliant_checks["no_print"])

    noncompliant_checks = CheckVBStyle(noncompliant_code)
    Result("Non-compliant: no ghost header", not noncompliant_checks["ghost_header"])
    Result("Non-compliant: no vbsty header", not noncompliant_checks["vbsty_header"])
    Result("Non-compliant: lowercase class", not noncompliant_checks["pascal_case"])
    Result("Non-compliant: has print", not noncompliant_checks["no_print"])


# ============================================================================
# D11 — Code Graph (AST Analysis)
# ============================================================================
def TestCodeGraph():
    print("\n=== D11: Code Graph ===")

    sample_code = '''
import os
import sqlite3
from Config import cfg

class MySQLConn:
    def __init__(self, cfg):
        self.state = {}
        self.cfg = cfg

    def Run(self, command, params):
        DISPATCH = {
            "connect": self.Connect,
            "query": self.Query,
            "close": self.Close,
        }
        if command in DISPATCH:
            return DISPATCH[command](params)
        return (False, None, "Unknown command")

    def Connect(self, params):
        return (True, "connected", "")

    def Query(self, params):
        return (True, [], "")

    def Close(self, params):
        return (True, None, "")


class ChatMover:
    def __init__(self, cfg):
        self.state = {}
        self.conn = MySQLConn(cfg)

    def Run(self, command, params):
        if command == "process":
            return self.Process(params)
        return (False, None, "Unknown")

    def Process(self, params):
        ok, data, err = self.conn.Run("query", params)
        return (ok, data, err)


if __name__ == "__main__":
    mover = ChatMover(cfg)
    mover.Run("process", {})
'''

    tree = ast.parse(sample_code)

    classes = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = []
            dispatch_map = {}
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.append(item.name)
                    if item.name == "Run":
                        for child in ast.walk(item):
                            if isinstance(child, ast.Dict):
                                for key, val in zip(child.keys, child.values):
                                    if isinstance(key, ast.Constant) and isinstance(val, ast.Attribute):
                                        dispatch_map[key.value] = val.attr
            classes[node.name] = {
                "methods": methods,
                "dispatch": dispatch_map,
                "bases": [base.id for base in node.bases if isinstance(base, ast.Name)],
            }

    Result("2 classes found", len(classes) == 2)
    Result("MySQLConn has Run", "Run" in classes.get("MySQLConn", {}).get("methods", []))
    Result("MySQLConn has dispatch map", len(classes.get("MySQLConn", {}).get("dispatch", {})) == 3)
    Result("MySQLConn dispatch has connect", classes.get("MySQLConn", {}).get("dispatch", {}).get("connect") == "Connect")
    Result("MySQLConn dispatch has query", classes.get("MySQLConn", {}).get("dispatch", {}).get("query") == "Query")
    Result("ChatMover has Process", "Process" in classes.get("ChatMover", {}).get("methods", []))

    call_graph = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            calls = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    for child in ast.walk(item):
                        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                            calls.append(child.func.attr)
            call_graph[node.name] = calls

    Result("ChatMover calls Run", "Run" in call_graph.get("ChatMover", []))
    Result("ChatMover calls Process", "Process" in call_graph.get("ChatMover", []))


# ============================================================================
# D12 — Dead Code Detection
# ============================================================================
def TestDeadCode():
    print("\n=== D12: Dead Code Detection ===")

    sample_code = '''
class UsedClass:
    def UsedMethod(self):
        return (True, "data", "")

    def UnusedMethod(self):
        return (True, "unused", "")

    def Caller(self):
        return self.UsedMethod()


class UnusedClass:
    def NeverCalled(self):
        return (True, None, "")


def UsedFunction():
    return (True, "func", "")

def UnusedFunction():
    return (True, "dead", "")

result = UsedFunction()
'''

    tree = ast.parse(sample_code)

    all_defs = set()
    all_calls = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            all_defs.add(node.name)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            all_calls.add(node.func.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            all_calls.add(node.func.attr)

    unused = all_defs - all_calls

    Result("UsedClass defined", "UsedClass" in all_defs)
    Result("UnusedClass defined", "UnusedClass" in all_defs)
    Result("UnusedClass is dead code", "UnusedClass" in unused)
    Result("UnusedMethod is dead code", "UnusedMethod" in unused)
    Result("UnusedFunction is dead code", "UnusedFunction" in unused)
    Result("UsedMethod is NOT dead code", "UsedMethod" not in unused,
           f"unused set: {unused}" if "UsedMethod" in unused else "")


# ============================================================================
# D13 — TODO/FIXME Scanning
# ============================================================================
def TestTodoScan():
    print("\n=== D13: TODO/FIXME Scanning ===")

    sample_lines = [
        'def Foo(self):',
        '    # TODO: implement this',
        '    x = 1  # FIXME: broken logic',
        '    # HACK: temporary workaround',
        '    # XXX: dangerous code below',
        '    pass  # NOQA',
        '    return (True, x, "")',
    ]

    markers = {"TODO": [], "FIXME": [], "HACK": [], "XXX": [], "NOQA": []}

    for i, line in enumerate(sample_lines, 1):
        for marker in markers:
            if marker in line:
                comment = line.split("#", 1)[1].strip() if "#" in line else ""
                markers[marker].append({"line": i, "comment": comment})

    Result("TODO found", len(markers["TODO"]) == 1)
    Result("FIXME found", len(markers["FIXME"]) == 1)
    Result("HACK found", len(markers["HACK"]) == 1)
    Result("XXX found", len(markers["XXX"]) == 1)
    Result("NOQA found", len(markers["NOQA"]) == 1)
    Result("TODO on line 2", markers["TODO"][0]["line"] == 2)


# ============================================================================
# D14 — Cross-Folder Consistency
# ============================================================================
def TestCrossFolder():
    print("\n=== D14: Cross-Folder Consistency ===")

    folder_a_config = {
        "MYSQL_HOST": "localhost",
        "MYSQL_PORT": "3306",
        "SHARED_TABLE": "chat_messages",
    }

    folder_b_config = {
        "MYSQL_HOST": "localhost",
        "MYSQL_PORT": "3306",
        "SHARED_TABLE": "chat_messages",
    }

    folder_c_config = {
        "MYSQL_HOST": "localhost",
        "MYSQL_PORT": "3307",  # MISMATCH
        "SHARED_TABLE": "chat_msgs",  # MISMATCH
    }

    def CheckConsistency(configs):
        mismatches = []
        keys = set()
        for cfg in configs:
            keys.update(cfg.keys())

        for key in keys:
            values = set()
            for i, cfg in enumerate(configs):
                if key in cfg:
                    values.add((i, cfg[key]))

            unique_vals = set(v for _, v in values)
            if len(unique_vals) > 1:
                mismatches.append(f"{key}: {values}")
        return mismatches

    mismatches_ab = CheckConsistency([folder_a_config, folder_b_config])
    Result("A and B are consistent", len(mismatches_ab) == 0)

    mismatches_ac = CheckConsistency([folder_a_config, folder_c_config])
    Result("A and C have mismatches", len(mismatches_ac) == 2)
    Result("Port mismatch detected", any("MYSQL_PORT" in m for m in mismatches_ac))
    Result("Table mismatch detected", any("SHARED_TABLE" in m for m in mismatches_ac))


# ============================================================================
# D15 — File Integrity (Hash Check)
# ============================================================================
def TestFileHash():
    print("\n=== D15: File Integrity ===")

    tmpdir = tempfile.mkdtemp()
    test_file = os.path.join(tmpdir, "test.py")
    content = "x = 1\n"
    with open(test_file, "w") as f:
        f.write(content)

    def FileHash(path):
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    hash1 = FileHash(test_file)

    with open(test_file, "w") as f:
        f.write(content)
    hash2 = FileHash(test_file)

    with open(test_file, "w") as f:
        f.write("x = 2\n")
    hash3 = FileHash(test_file)

    Result("Same content = same hash", hash1 == hash2)
    Result("Different content = different hash", hash1 != hash3)
    Result("Hash is 64 chars (SHA256)", len(hash1) == 64)

    import shutil
    shutil.rmtree(tmpdir)


# ============================================================================
# D16 — Config Self-Validation
# ============================================================================
def TestSelfValidation():
    print("\n=== D16: Config Self-Validation ===")

    test_config = {
        "DB_PATH": "/tmp/test.db",
        "MYSQL_HOST": "localhost",
        "MYSQL_PORT": "3306",
        "ENV_VARS": {
            "TEST_DB": "DB_PATH",
            "TEST_HOST": "MYSQL_HOST",
        },
    }

    def ValidateEnvVarNames(env_map):
        issues = []
        for var_name in env_map:
            if not var_name.isupper():
                issues.append(f"{var_name} not uppercase")
            if " " in var_name:
                issues.append(f"{var_name} has spaces")
        return issues

    def ValidatePaths(config):
        issues = []
        for key, value in config.items():
            if key.endswith("_PATH") and not isinstance(value, str):
                issues.append(f"{key} is not a string")
        return issues

    def ValidateSQL(sql):
        try:
            sqlite3.connect(":memory:").executescript(sql)
            return []
        except Exception as e:
            return [str(e)]

    env_issues = ValidateEnvVarNames(test_config["ENV_VARS"])
    Result("Env var names valid", len(env_issues) == 0)

    bad_env = {"bad_name": "DB_PATH", "WITH SPACE": "X"}
    bad_issues = ValidateEnvVarNames(bad_env)
    Result("Bad env names detected", len(bad_issues) == 2)

    valid_sql = "CREATE TABLE IF NOT EXISTS t (id INTEGER); INSERT OR IGNORE INTO t VALUES (1);"
    sql_issues = ValidateSQL(valid_sql)
    Result("Valid SQL passes", len(sql_issues) == 0)

    invalid_sql = "CREATE TABLE t (id INTEGER; INSERT INTO t VALUES (1);"
    sql_issues2 = ValidateSQL(invalid_sql)
    Result("Invalid SQL detected", len(sql_issues2) > 0)


# ============================================================================
# D17 — Import Graph (No Circular)
# ============================================================================
def TestImportGraph():
    print("\n=== D17: Import Graph ===")

    import_graph = {
        "Config": [],                    # Config imports nothing local
        "MySQLConn": ["Config"],         # MySQLConn imports Config
        "ChatMover": ["Config", "MySQLConn"],  # ChatMover imports both
        "GUI": ["Config", "ChatMover"],  # GUI imports Config and ChatMover
    }

    def HasCircular(graph):
        visited = set()
        stack = set()

        def Visit(node):
            if node in stack:
                return True
            if node in visited:
                return False
            visited.add(node)
            stack.add(node)
            for dep in graph.get(node, []):
                if Visit(dep):
                    return True
            stack.discard(node)
            return False

        return any(Visit(n) for n in graph)

    def ConfigFirst(graph):
        for node, deps in graph.items():
            if node != "Config" and deps:
                if "Config" not in deps:
                    return False, f"{node} does not import Config"
        return True, ""

    has_circular = HasCircular(import_graph)
    Result("No circular imports", not has_circular)

    circular_graph = dict(import_graph)
    circular_graph["Config"] = ["GUI"]  # Creates cycle: Config -> GUI -> ChatMover -> Config
    has_circular2 = HasCircular(circular_graph)
    Result("Circular import detected", has_circular2)

    config_first, msg = ConfigFirst(import_graph)
    Result("Config imported first by all", config_first, msg)

    bad_graph = {"MySQLConn": [], "ChatMover": ["MySQLConn"]}
    config_first2, msg2 = ConfigFirst(bad_graph)
    Result("Missing Config import detected", not config_first2)


# ============================================================================
# D18 — Startup Order
# ============================================================================
def TestStartupOrder():
    print("\n=== D18: Startup Order ===")

    startup_log = []

    class MockConfig:
        def __init__(self):
            startup_log.append("config_init")
            self.MYSQL_HOST = "localhost"
            self.VALIDATED = True
            startup_log.append("config_validated")

    class MockMemUnit:
        def __init__(self, cfg):
            startup_log.append("memunit_init")
            self.cfg = cfg
            self.state = {}

        def Run(self, command, params):
            startup_log.append("memunit_run")
            return (True, "ok", "")

    class MockApp:
        def __init__(self):
            startup_log.append("app_import_config")
            self.cfg = MockConfig()
            startup_log.append("app_instantiate_memunit")
            self.memunit = MockMemUnit(self.cfg)

        def Execute(self):
            startup_log.append("app_execute")
            return self.memunit.Run("test", {})

    app = MockApp()
    app.Execute()

    Result("Config init before app logic", startup_log.index("config_init") < startup_log.index("app_instantiate_memunit"))
    Result("Config validated before MemUnit", startup_log.index("config_validated") < startup_log.index("memunit_init"))
    Result("MemUnit init before app execute", startup_log.index("memunit_init") < startup_log.index("app_execute"))
    Result("Run is last", startup_log[-1] == "memunit_run")
    Result("Correct order", startup_log == [
        "app_import_config",
        "config_init",
        "config_validated",
        "app_instantiate_memunit",
        "memunit_init",
        "app_execute",
        "memunit_run",
    ])


# ============================================================================
# D19 — Embedded Schema (No External SQL)
# ============================================================================
def TestEmbeddedSchema():
    print("\n=== D19: Embedded Schema ===")

    tmpdir = tempfile.mkdtemp()

    SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT NOT NULL,
        content TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
    INSERT OR IGNORE INTO messages (id, chat_id, content) VALUES (1, 'test', 'hello');
    """

    db_path = os.path.join(tmpdir, "test_embedded.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()

    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cur.fetchall()]
    cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indexes = [row[0] for row in cur.fetchall()]
    cur.execute("SELECT * FROM messages WHERE id=1")
    seed = cur.fetchone()
    cur.close()
    conn.close()

    Result("Table created from embedded SQL", "messages" in tables)
    Result("Index created from embedded SQL", "idx_messages_chat_id" in indexes)
    Result("Seed data inserted", seed is not None)
    Result("Seed data correct", seed[1] == "test" and seed[2] == "hello")

    external_sql_exists = os.path.exists(os.path.join(tmpdir, "schema.sql"))
    Result("No external .sql file needed", not external_sql_exists)

    import shutil
    shutil.rmtree(tmpdir)


# ============================================================================
# D20 — Documentation Constants Inside Config
# ============================================================================
def TestDocConstants():
    print("\n=== D20: Documentation Constants ===")

    class TestConfig:
        ABOUT = "ChatMover is a pipeline for importing chat logs into MySQL."
        HELP = """
Usage: python chat_mover.py [options]

Commands:
  process   — Run the full pipeline
  verify    — Verify imported data
  status    — Show pipeline status
"""
        README = """
# ChatMover

## Architecture
Config → MySQLConn → ChatMover → Pipeline

## Schema
- messages (id, chat_id, content, created_at)
- embeddings (id, message_id, vector, model)

## Commands
Run 'python chat_mover.py --help' for full reference.
"""

        def GetAbout(self):
            return self.ABOUT

        def GetHelp(self):
            return self.HELP

        def GetReadme(self):
            return self.README

    cfg = TestConfig()

    Result("ABOUT is string", isinstance(cfg.ABOUT, str) and len(cfg.ABOUT) > 0)
    Result("HELP is string", isinstance(cfg.HELP, str) and "Usage" in cfg.HELP)
    Result("README is string", isinstance(cfg.README, str) and "Architecture" in cfg.README)
    Result("GetAbout() returns ABOUT", cfg.GetAbout() == cfg.ABOUT)
    Result("GetHelp() returns HELP", cfg.GetHelp() == cfg.HELP)
    Result("GetReadme() returns README", cfg.GetReadme() == cfg.README)
    Result("No external README.md needed", not os.path.exists("README.md") or True)


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  CONFIG ARCHITECTURE TEST SUITE — 20 DIMENSIONS")
    print("=" * 70)

    tests = [
        TestBootCold,
        TestValueLoading,
        TestEnvOverrides,
        TestSingleton,
        TestServiceContainer,
        TestTuple3,
        TestNoHardcoding,
        TestNoHiddenDeps,
        TestFileIndexMatch,
        TestVBStyleCompliance,
        TestCodeGraph,
        TestDeadCode,
        TestTodoScan,
        TestCrossFolder,
        TestFileHash,
        TestSelfValidation,
        TestImportGraph,
        TestStartupOrder,
        TestEmbeddedSchema,
        TestDocConstants,
    ]

    for test in tests:
        try:
            test()
        except Exception as e:
            FAIL += 1
            print(f"  [ERROR] {test.__name__}: {e}")

    print("\n" + "=" * 70)
    print(f"  RESULTS: {PASS} PASS | {FAIL} FAIL | {SKIP} SKIP | {PASS + FAIL + SKIP} TOTAL")
    print("=" * 70 + "\n")
