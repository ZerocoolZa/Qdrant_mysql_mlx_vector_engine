# VBSTYLE CODE RULES

## Rule: File Format and Header Requirements

### H1 — Ghost Header (Required)
Every `.py` file must start with a Ghost Header block:
```python
#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     <filename>
# Domain:   <domain>
# Authority: <what this file controls>
# DB:       <database name or None>
```

### H2 — VBStyle Header (Required)
Immediately after the Ghost Header, every file must have a VBStyle Header:
```python
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Rules followed:
#   @ghost    — Ghost Header present
#   @vbsty    — VBStyle Header present
#   @hardcode — NO hardcoded paths
#   @cstyle   — Coding style compliant
#   ...
```

### H3 — AI Guide Block (Required on config files)
Config files must include an AI Guide block after the VBStyle Header:
```python
# AI GUIDE — READ THIS FIRST
# ----------------------------------------------------------------------------
# <What this file is and what AI agents need to know>
```

### H4 — Class Header (Required on every class)
Every class definition must be preceded by a Class Header:
```python
# ============================================================================
# CLASSES HEADER
# ----------------------------------------------------------------------------
# Class:  <ClassName>
# Domain: <domain>
# Authority: <what this class controls>
# Dependencies: <imports>
# ============================================================================
```

### H5 — Method Header (Required on every method)
Every method must have a method header comment:
```python
def MethodName(self, params):
    """Brief description of what this method does."""
```

## Rule: Naming Conventions

### N1 — PascalCase Classes
All class names use PascalCase: `MySQLConn`, `ChatMoverConfig`, `EditorTabs`

### N2 — UPPERCASE Constants
All constants use UPPERCASE with underscores: `BASE_DIR`, `DB_PATH`, `SCHEMA_VERSION`

### N3 — camelCase Methods
All method names use PascalCase/camelCase: `GetFileIndex`, `LoadConfig`, `RunPipeline`

### N4 — No Underscore Prefix
Never use `self._` for private attributes. Use `self.state` dict pattern for executable classes. Config classes may use `self._values` for internal storage.

## Rule: Code Style

### C1 — No Print Statements
Never use `print()` in production code. Use logging or return values.

### C2 — No Decorators
No decorators unless explicitly required by the framework. No `@staticmethod`, `@classmethod`, `@functools` etc. unless absolutely necessary.

### C3 — No Hardcoded Values
No hardcoded paths, URLs, database names, ports, or credentials. All values must come from config or environment variables.

### C4 — No Tabs
Use spaces only. 4 spaces per indent level.

### C5 — No Trailing Whitespace
No trailing spaces on any line.

### C6 — No Enums
Do not use `enum.Enum`. Use string constants or integer constants instead.

### C7 — No Hidden Imports
All imports at the top of the file. No imports inside functions.

## Rule: VBStyle Architecture

### V1 — Run() Dispatch Entry
Every executable class must have a `Run(command, params)` dispatch method that returns a Tuple3: `(ok, data, error)`.

### V2 — Tuple3 Returns
Methods that report success/failure must return a 3-tuple: `(ok: bool, data: any, error: str)`

### V3 — State Dict
Executable classes use `self.state` dict for state management. No `self._` private attributes.

### V4 — Constructor Pattern
Constructors initialize `self.state = {}` and load config from the config singleton.

### V5 — Config Singleton
Every config file exports a singleton: `cfg = Config()`. Other files import `from Config import cfg`.

### V6 — Dispatch Map
Executable classes use a dispatch dict in `Run()` to map commands to methods:
```python
DISPATCH = {
    "create": self.Create,
    "read": self.Read,
    "update": self.Update,
    "delete": self.Delete,
}
```

### V7 — No Memory Units
Do not create classes that are just data containers. Use dicts or namedtuples for pure data.

### V8 — Remote Destination
Methods that write data must support a remote destination parameter for MySQL/external DB writes.

## Rule: File Organization

### F1 — Import Order
1. Standard library imports
2. Third-party imports
3. Local/project imports

### F2 — File Structure Order
1. Ghost Header
2. VBStyle Header
3. AI Guide (config files only)
4. Imports
5. Constants
6. Class Headers + Class definitions
7. Singleton instance (config files only)
8. Main entry point (if applicable)

### F3 — Whitespace
- 2 blank lines between class definitions
- 1 blank line between methods
- No more than 2 consecutive blank lines

## Rule: Error Handling

### E1 — Tuple3 Error Returns
All methods that can fail must return `(False, None, "error message")` on failure and `(True, data, "")` on success. Never raise exceptions in production code — catch and return.

### E2 — No Bare Except
Never use bare `except:`. Always catch specific exceptions: `except sqlite3.Error`, `except mysql.connector.Error`, etc.

### E3 — Error Messages
Error messages must be descriptive and include context: what failed, what was the input, what was expected. No generic "error occurred" messages.

### E4 — Logging on Error
All errors must be logged before returning the Tuple3. Use the logging module, not print.

### E5 — No Silent Failures
Never swallow exceptions with `pass` or empty except blocks. If you catch an exception, log it or return it.

## Rule: Logging

### L1 — Use Logging Module
All logging must use Python's `logging` module. No `print()` statements anywhere.

### L2 — Log Levels
- `logging.DEBUG` — detailed diagnostic info
- `logging.INFO` — confirmation that things are working
- `logging.WARNING` — something unexpected, but software still works
- `logging.ERROR` — serious problem, operation failed
- `logging.CRITICAL` — program may not be able to continue

### L3 — Rotating Logs
Log files must use `RotatingFileHandler` with max 5MB per file and 3 backup files. Log path comes from config.

### L4 — Log Format
Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`

## Rule: SQL and Schema

### S1 — Embedded Schema (No External SQL Files)
All database schema (CREATE TABLE, CREATE VIEW, INSERT seed data) must be embedded as SQL string constants inside the config file. 

**No external `.sql` files.** No `config_seed.sql`, no `schema.sql`, no `init.sql`. All SQL lives inside `Config_<foldername>.py` as string constants. If you need schema, it lives in config.

### S2 — Boot Cold
The application must boot cold — if no database exists, it creates one from the embedded schema in config. No manual setup required.

### S3 — No Inline SQL in Logic
SQL queries must not be written inline in business logic. Define query templates as constants in config or use parameterized methods.

### S4 — Parameterized Queries
All SQL queries must use parameterized inputs (`?` for SQLite, `%s` for MySQL). No string concatenation or f-strings for SQL.

### S5 — Idempotent Seeds
Seed data inserts must be idempotent: `INSERT OR IGNORE` (SQLite) or `INSERT ... ON DUPLICATE KEY UPDATE` (MySQL).

## Rule: Environment Variables

### EV1 — Naming Convention
Environment variable names must be UPPERCASE with folder prefix: `CHAT_MOVER_MYSQL_HOST`, `BOOK_DB`, `QA_ENGINE_EMBED_MODEL`

### EV2 — Override Pattern
Env vars override config values, not replace them. Config provides defaults, env vars override at load time.

### EV3 — Env Var Documentation
All env vars must be documented in the config file's AI Guide block and in the config seed table description field.

### EV4 — No Required Env Vars
All env vars must be optional. If not set, config provides a sensible default. The app must run without any env vars set.

## Rule: Documentation

### D1 — Documentation Constants (No External Files)
Config files must contain ALL documentation as constants: `ABOUT`, `HELP`, `README`. These are rendered dynamically by the GUI/CLI. 

**No external `.md` files.** No `README.md`, no `HELP.md`, no `ABOUT.md`. The config file IS the documentation. If you need docs, it lives inside `Config_<foldername>.py` as a string constant.

### D2 — ABOUT
One-paragraph description of what the system is. Used in `--about` or About dialog. Lives inside config as `ABOUT = """..."""`.

### D3 — HELP
Quick start + command reference. Used in `--help` output. Lives inside config as `HELP = """..."""`.

### D4 — README
Full project documentation embedded as a constant in config. Covers architecture, commands, schema, features. Lives inside config as `README = """..."""`. No separate `README.md` file.

### D5 — Config Registry
A top-level `Config_Registry.md` file must exist at workspace root, cataloging all config files across all folders with their variables, rules, and patterns. This is the ONLY `.md` file allowed for documentation — it indexes configs, it does not replace them.

## Rule: Database Access

### DB1 — Connection Management
All database connections must be managed through a connection class (e.g., `MySQLConn`). No direct `sqlite3.connect()` or `mysql.connector.connect()` calls in business logic — only in the connection class.

### DB2 — Connection Cleanup
All connections must be closed in a `finally` block or via context manager. No orphaned connections.

### DB3 — Reconnect Support
Database connection classes must support automatic reconnection after connection loss.

### DB4 — Transaction Management
Use explicit `commit()` and `rollback()`. No autocommit mode for multi-step operations.

## Rule: Testing

### T1 — Test Before Implementation
Design or update tests before major implementation work. Never delete or weaken tests without explicit direction.

### T2 — Test Naming
Test files: `test_<module>.py`. Test methods: `test_<what_it_tests>`.

### T3 — Test Isolation
Each test must be self-contained. No dependencies between tests. Use setup/teardown for state.

### T4 — Verify Commands
Share copy-pastable verification commands when tests cannot be run automatically.

## Rule: Dependencies

### DEP1 — Python Version
Target Python 3.13+. Use modern syntax and features.

### DEP2 — Requirements File
All third-party dependencies must be listed in `requirements.txt` with pinned versions.

### DEP3 — No Unnecessary Dependencies
Do not add dependencies for functionality that can be achieved with the standard library. Each new dependency must be justified.

### DEP4 — Import Only What You Need
Use specific imports: `from os import path, environ`. Avoid `import os` if only one function is needed (exception: common modules like `os`, `sys`).

## Rule: Security

### SEC1 — No Credentials in Code
No passwords, API keys, tokens, or secrets in source code. All credentials come from environment variables.

### SEC2 — No Credentials in Logs
Never log passwords, tokens, or sensitive data. Mask them in log output.

### SEC3 — No Credentials in Config Seed
Config seed SQL must not contain real passwords. Use placeholder defaults that are overridden by env vars.

### SEC4 — File Permissions
Database files and config databases must have restrictive permissions (owner read/write only).

## Rule: BCL Tokens

### B1 — Token Format
BCL tokens use bracket format: `[@name]{("key";"value")}`. NOT JSON. NOT XML.

### B2 — Weight Last
Weight is ALWAYS the last element in a tuple: `("text";92)`.

### B3 — Semicolon Separator
Tuples use semicolons inside parens: `("value1";"value2";"value3")`.

### B4 — Capital First Letter
Token names must start with capital: `[@Pass]`, `[@Fail]`, `[@CascadeSearch]`.

### B5 — Real Bracket Parser
Never use regex to parse BCL. Must use a real bracket parser that handles nesting.

## Rule: Static Resources

### SR1 — Embed Static Resources
Static resources (JS libraries, CSS, images) must be embedded as compressed base64 constants in config. No external file dependencies for resources that ship with the app.

### SR2 — Compression
Use `zlib.compress` + `base64.b64encode` for embedding. Decompress at load time.

### SR3 — No File Sprawl
If a resource is needed by the app, it lives in config as a constant. Not as a loose file in the folder.

## Rule: Config Registry

### CR1 — Registry File
A `Config_Registry.md` file must exist at workspace root, cataloging all config files.

### CR2 — Registry Content
Each entry in the registry must include:
- Folder name
- Config file name
- All variables/keys with descriptions
- Environment variable overrides
- Rules and patterns followed
- Database tables managed (if any)

### CR3 — Registry Maintenance
The registry must be updated whenever a config file is added, removed, or its variables change.

## Rule: File Naming

### FN1 — Python Files
All Python files use snake_case: `chat_mover.py`, `mysql_conn.py`. Exception: Config files use `Config_<foldername>.py`.

### FN2 — No Generic Names
No files named `utils.py`, `helpers.py`, `common.py`, `misc.py`. Every file name must describe its domain.

### FN3 — One Class Per File (Preferred)
Each file should contain one primary class. Small helper classes are acceptable but the file name must reflect the primary class.

## Rule: Import Rules

### IM1 — No Circular Imports
No file may import from another file that imports back. Use config singleton as the shared bridge.

### IM2 — Config Import First
Local imports must start with the config import: `from Config_<foldername> import cfg`. Then other local imports.

### IM3 — No Wildcard Imports
Never use `from module import *`. Always import specific names.

## Rule: Pipeline and Processing

### P1 — Idempotent Operations
All pipeline operations must be idempotent. Running the same operation twice must not create duplicates.

### P2 — Resumable Pipelines
Pipelines must be resumable. If interrupted, they can continue from where they left off using state tracking.

### P3 — Batch Processing
Large operations must process in batches. Batch size comes from config.

### P4 — Self-Healing
Pipelines must detect and repair common issues automatically (missing tables, broken connections, stale state).
