# CLI Safe Execution Pipeline — Cascade CLI (CEK v3)

> **Core thesis:** Every command execution goes through a formal state machine
> that prevents terminal errors, captures failures, learns from them, and queries
> the knowledge base for fixes — before the error reaches the user.

---

## Pipeline Overview

```
Command Received → Validate → Normalize → Execute (subprocess)
       ↓              ↓           ↓              ↓
   INIT          BLOCKED      shell=False    RUNNING → STREAMING
                                                   ↓
                                          ┌───────┴────────┐
                                          │                │
                                       DONE            FAILED/STUCK
                                          │            /TIMEOUT/KILLED
                                          ↓                ↓
                                     exit=0          Detect Error Pattern
                                                          ↓
                                                   Query Knowledge Base
                                                   (MySQL + SQLite)
                                                          ↓
                                                   Learn Error
                                                   (insert/update frequency)
                                                          ↓
                                                   Return Fix Suggestion
```

---

## State Machine (Formal Lifecycle)

```
INIT → RUNNING → STREAMING → DONE (exit=0)
                   ↓
              STUCK (no output) → KILLED (frozen) → FAILED
                   ↓
              TIMEOUT → FAILED
                   ↓
              FAILED (exit≠0) → Detect Error → Query KB → Learn

BLOCKED (validation rejected) → terminal
ERROR (exception) → terminal
```

| State | Meaning | Terminal? |
|---|---|---|
| `INIT` | Command received, not started | No |
| `RUNNING` | Process spawned, waiting for output | No |
| `STREAMING` | Receiving output on stdout/stderr | No |
| `STUCK` | No output for `max_no_output` seconds | No |
| `TIMEOUT` | Hard timeout exceeded | No (→ FAILED/DONE) |
| `KILLED` | Hard freeze detected (2x stuck threshold), force-killed | No (→ FAILED/DONE) |
| `FAILED` | Process exited non-zero | Yes |
| `DONE` | Process exited zero | Yes |
| `BLOCKED` | Command validation rejected | Yes |
| `ERROR` | Exception during execution | Yes |

**State transition violations** are logged but allowed (with warning).

---

## Stages

### Stage 1: VALIDATE — Command Safety Check

**Tool:** `validate_command(cmd, allow_dangerous=False)`

Blocks dangerous patterns:
- `rm -rf /` — destructive
- `> /dev/sda` — disk overwrite
- `mkfs` — filesystem format
- `dd of=/dev/` — raw disk write
- `:(){ :|:& };:` — fork bomb

If `allow_dangerous=True`, command proceeds but violation is logged.

### Stage 2: NORMALIZE — Command Splitting

**Tool:** `normalize_command(cmd, shell)`

- If `shell=False`: auto-splits with `shlex.split()` → safe argv list
- If `shell=True` (with `--shell` flag): passes as string to `/bin/bash -c`
- Shell mode enables pipes, redirections, and shell builtins

### Stage 3: EXECUTE — Subprocess with Triple-Layer Protection

**Tool:** `subprocess.Popen()` with:
- **Timeout:** hard timeout (`--timeout N` seconds)
- **Stuck detection:** no output for `max_no_output` seconds → STUCK
- **Freeze detection:** 2x stuck threshold → KILLED (process group kill)

Non-blocking stream reader (threaded, try/finally, no pipe deadlock).

### Stage 4: DETECT ERROR PATTERNS — Classify Failures

**Tool:** `detect_error_patterns(stderr_text, stdout_text)`

Pattern dictionary with keywords and priorities:

| Pattern | Type | Priority | Keywords |
|---|---|---|---|
| `MySQLProgrammingError` | mysql | 3 | `unknown database`, `unknown column`, `sql syntax` |
| `MySQLInterfaceError` | mysql | 3 | `mysqlinterfaceerror` |
| `ImportError` | python | 2 | `no module named`, `importerror` |
| `ModuleNotFoundError` | python | 2 | `module not found` |
| `SyntaxError` | python | 2 | `syntaxerror`, `unexpected indent` |
| `AttributeError` | python | 2 | `has no attribute`, `attributeerror` |
| `TypeError` | python | 2 | `typeerror`, `unsupported operand` |
| `ZeroDivisionError` | python | 1 | `division by zero` |
| `FileNotFoundError` | python | 2 | `no such file or directory` |
| `PermissionError` | python | 2 | `permission denied` |
| `missing_header` | vbstyle | 1 | `ghost`, `vbstyle`, `class header` (source scan only) |

### Stage 5: QUERY KNOWLEDGE BASE — Find Known Fixes

**Tool:** `query_knowledge_base(detected_errors, cmd)`

Queries both MySQL and SQLite in order:

**MySQL (vb_shared):**
1. `error_knowledge` — structured error signatures (cause, solution, fix_code)
2. `know_problems` → `know_causes` → `know_solutions` → `know_fixes` — problem-solution chain
3. `know_lessons` — learned lessons
4. `learned_rules` — pattern → fix_action with confidence (10,590 rules)

**SQLite (fallback/standalone):**
1. `error_knowledge` — local error knowledge (same schema as MySQL)

Returns guidance with: `pattern_name`, `type`, `priority`, `fix_action`, `source`, `confidence`

### Stage 6: LEARN ERROR — Capture for Future Prevention

**Tool:** `learn_error(error_type, stderr_text, cmd)`

If error is new:
- INSERT into `error_knowledge` (signature, error_type, domain, cause, solution, confidence, frequency=1)

If error already exists:
- UPDATE `frequency = frequency + 1`, `last_seen = now`

Writes to both MySQL and SQLite (dual write).

### Stage 7: VBSTYLE PRE-SCAN — Check Source Before Running

**Tool:** `scan_python_source(filepath)`

Before executing a `.py` file, scans for VBStyle violations:
- `print_statement` — `print()` calls (line stripped, starts with `print(`)
- `missing_header` — class without `#[@GHOST]` or `#[@VBSTYLE]` header

For each violation, queries knowledge base for known fixes and includes them in the guidance output.

### Stage 8: LOG EXECUTION — Structured Event Timeline

**Tool:** `log_execution(result, cmd, error_type, linked_error_id)`

Every execution is logged with:
- `run_id` — unique execution ID
- `cmd` — command string
- `exit_code` — process exit code
- `state` — final state (DONE/FAILED/TIMEOUT/etc.)
- `duration` — wall clock time
- `error_type` — detected error pattern (if any)
- `linked_error_id` — FK to error_knowledge table
- `events` — JSON timeline of all state transitions

---

## File Locations

```
CLI SAFE EXECUTION PIPELINE FILES:
├── /Users/wws/Downloads/cascade_cli.py     — Cascade Execution Kernel (CEK v3)
│
└── MySQL vb_shared:
    ├── error_knowledge                      — 70 error signatures (cause, solution, frequency)
    ├── learned_rules                        — 10,590 rules (pattern → fix_action, confidence)
    ├── know_problems                        — 309 known problems
    ├── know_solutions                       — 362 solutions
    └── know_lessons                         — learned lessons
```

---

## CLI Usage

```bash
# Basic execution
python3 /Users/wws/Downloads/cascade_cli.py "ls -la"

# With timeout
python3 /Users/wws/Downloads/cascade_cli.py "python3 slow_script.py" --timeout 30

# With shell mode (pipes, redirections)
python3 /Users/wws/Downloads/cascade_cli.py "mysql -u root vb_shared -e 'QUERY'" --shell --no-stuck --timeout 30

# JSON output
python3 /Users/wws/Downloads/cascade_cli.py "cat file.py" --json

# Retry with backoff
python3 /Users/wws/Downloads/cascade_cli.py "flake8 ." --retry 3

# Dry run (no execution)
python3 /Users/wws/Downloads/cascade_cli.py "rm -rf /tmp/test" --dry-run

# Working directory
python3 /Users/wws/Downloads/cascade_cli.py "ls" --cwd /Users/wws/Qdrant_mysql_mlx_vector_engine

# Disable stuck detection (long queries)
python3 /Users/wws/Downloads/cascade_cli.py "mysql -u root -e 'SELECT ...'" --no-stuck --timeout 60
```

---

## Current Status

| Component | Status | Data |
|---|---|---|
| State machine (9 states) | **DONE** | — |
| Command validation | **DONE** | — |
| Command normalization (shlex) | **DONE** | — |
| Subprocess execution | **DONE** | — |
| Stuck/freeze/timeout protection | **DONE** | — |
| Error pattern detection | **DONE** | 12 patterns |
| MySQL knowledge base query | **DONE** | 10,590 rules + 70 signatures |
| SQLite fallback query | **DONE** | — |
| Error learning (insert/update) | **DONE** | — |
| VBStyle pre-scan | **DONE** | print + missing_header |
| Execution logging (JSONL) | **DONE** | — |
| Retry with backoff | **DONE** | — |
| Dry run mode | **DONE** | — |
| Process group kill | **DONE** | — |
