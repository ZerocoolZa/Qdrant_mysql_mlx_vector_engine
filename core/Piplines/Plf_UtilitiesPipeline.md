# Utilities Pipeline — Index, Audit, Verify, Orchestrate

> **Core thesis:** Utilities are not scripts you run manually.
> They are a pipeline: Config defines triggers → Scheduler fires them →
> Orchestrator dispatches to utilities → utilities execute → results collected.
> Everything is event-driven, configurable, and automated.

---

## Table of Contents

1. [Pipeline Overview](#1-pipeline-overview)
2. [Config — The Brain](#2-config--the-brain)
3. [Scheduler — Timer & Event Engine](#3-scheduler--timer--event-engine)
4. [Orchestrator — Dispatch & Failure Handling](#4-orchestrator--dispatch--failure-handling)
5. [Indexer — In-RAM SQLite Code Index with AI Reasoning](#5-indexer--in-ram-sqlite-code-index-with-ai-reasoning)
6. [VbsScanner — VBStyle Violation Detector](#6-vbsscanner--vbstyle-violation-detector)
7. [VbsTest — Compliance & Compile Checks](#7-vbstest--compliance--compile-checks)
8. [SystemCheck — Integrity Verification](#8-systemcheck--integrity-verification)
9. [DomAudit — Baseline, Drift & Compliance](#9-domaudit--baseline-drift--compliance)
10. [DiffCheck — Before/After Index Comparison](#10-diffcheck--beforeafter-index-comparison)
11. [StatsReport — Directory Statistics](#11-statsreport--directory-statistics)
12. [ContentExtract — Regex-Based Source Analysis](#12-contentextract--regex-based-source-analysis)
13. [PreFlight — Database Integrity Checks](#13-preflight--database-integrity-checks)
14. [ErrorHandler — Capture, Classify, Recover](#14-errorhandler--capture-classify-recover)
15. [ErrorTracker — MySQL Lessons Lookup](#15-errortracker--mysql-lessons-lookup)
16. [MSearch — MySQL + Qdrant Search](#16-msearch--mysql--qdrant-search)
17. [Cleaner — Artifact Removal](#17-cleaner--artifact-removal)
18. [Compress — zlib + base64 Compression](#18-compress--zlib--base64-compression)
19. [Backup — Full Redundancy (Zip + S3 + Email + Git)](#19-backup--full-redundancy-zip--s3--email--git)
20. [Credentials — Secret Management](#20-credentials--secret-management)
21. [Pipeline Scenarios](#21-pipeline-scenarios)
22. [File Locations](#22-file-locations)
23. [How to Extend](#23-how-to-extend)

---

## 1. Pipeline Overview

```
Config.TRIGGERS → Scheduler (timer/event) → Orchestrator (dispatch) → Utility.Run() → Result
                                                                              ↓
                                                              ErrorHandler ← on_fail policy
```

The pipeline is event-driven. No utility is run manually. Instead:

- **Config** defines WHAT runs, WHEN, and what to do on failure
- **Scheduler** fires triggers on timer or event
- **Orchestrator** dispatches to the right utility in order
- **Utilities** execute and return Tuple3: `(1, data, None)` or `(0, None, (code, desc, 0))`
- **ErrorHandler** captures failures and determines recovery

All utilities follow the VBStyle contract:

- `__init__(self, mem=None, db=None, param=None)`
- `Run(self, command, params=None)` dispatch
- `self.state` dict (no `self._`)
- `_p()` helper for param extraction
- `read_state()` returns `(1, dict(self.state), None)`
- All methods return Tuple3
- No `print()`, no decorators, no hardcoded values

---

## 2. Config — The Brain

**File:** `core/utility/Config.py`

Config is the central nervous system. It defines paths, settings, triggers, schedules, and on_fail policies for every utility.

### TRIGGERS

Ordered lists of utility calls per event type:

| Trigger | When | Utilities (in order) | On Fail |
|---|---|---|---|
| `startup` | On boot | SystemCheck → DomIndexer → VbsScanner → Cleaner | report / continue |
| `error` | On error event | ErrorHandler → ErrorTracker → ErrorHandler.get_recovery_policy | escalate / cancel |
| `change` | On index change | DomAudit.drift → DiffCheck.compare → StatsReport.report_dir | report / continue |
| `code_change` | On file edit | VbsTest.vbs_check_folder → VbsTest.compile_file → ContentExtract.extract_file | report / continue |
| `db_change` | On DB change | PreFlight.check | report |
| `scheduled` | Hourly (3600s) | StatsReport → DomAudit → ErrorHandler.get_stats → Backup | continue / report |
| `backup` | Daily (86400s) | Backup.backup_all (zip + s3 + email + git) | report |

Each trigger entry has:
```python
{
    "util": "DomIndexer",       # utility class name
    "command": "index_dir",     # Run() dispatch command
    "params": {"path": None},    # params (None = filled at runtime)
    "why": "build file/class/method index",
    "order": 2,                  # execution order
    "on_fail": "continue",       # failure policy
}
```

### SCHEDULES

| Schedule | Interval | Mode | Description |
|---|---|---|---|
| `startup` | 0 | manual | Runs once on boot |
| `scheduled` | 3600s | timer | Hourly stats + audit + backup |
| `backup` | 86400s | timer | Daily full redundancy backup |
| `error` | 0 | event | Runs on error event |
| `change` | 0 | event | Runs on index change |
| `code_change` | 0 | event | Runs on file edit |
| `db_change` | 0 | event | Runs on DB change |

### ON_FAIL_ACTIONS

- **`report`** — log failure, include in report, continue pipeline
- **`continue`** — log failure, continue to next step
- **`escalate`** — escalate to higher severity
- **`cancel`** — stop pipeline immediately

### Utility Settings

Config also defines per-utility constants:

- **DomIndexer:** `use_vbast` (bool), `max_files` (int), `include_content` (bool), `INDEXER_SKIP_DIRS`, `INDEXER_EXTENSIONS`
- **VbsScanner:** `SCANNER_CHECK_PRINT`, `SCANNER_CHECK_DECORATORS`, `SCANNER_CHECK_SELF_UNDER`, `SCANNER_CHECK_HEADERS`, `SCANNER_CHECK_RUN`, `SCANNER_CHECK_TUPLE3`, `SCANNER_CHECK_NAMING`, `SCANNER_CHECK_TABS`, `SCANNER_CHECK_TRAILING_WS`
- **Cleaner:** `CLEANER_SKIP_DIRS`, `CLEANER_REMOVE_DIRS`, `CLEANER_REMOVE_EXTS`, `CLEANER_DRY_RUN`
- **ErrorHandler:** `ERROR_MAX_LOG_ENTRIES`, severity levels (`info`/`warning`/`error`/`critical`), recovery actions (`ignore`/`retry`/`rollback`/`cancel`/`snapshot`/`mark_invalid`/`request_user`)
- **ErrorTracker:** `ERROR_TRACKER_MYSQL` (host, user, password, database, unix_socket)
- **PreFlight:** `PREFLIGHT_CHECK_CONSTRAINTS`, `PREFLIGHT_CHECK_ORPHANS`, `PREFLIGHT_CHECK_OVERFLOW`, `PREFLIGHT_CHECK_FK`
- **DomAudit:** `AUDIT_MAX_HISTORY`
- **Backup:** `BACKUP_SKIP_DIRS`, `BACKUP_SKIP_EXTS`, `BACKUP_S3_BUCKET`, `BACKUP_EMAIL_PROVIDER`, `BACKUP_GIT_REMOTE`
- **VbsTest:** `TEST_TIMEOUT_SECONDS`, `TEST_BENCHMARK_DEFAULT_ITERATIONS`

### ConfigReport Class

Config also includes a `ConfigReport` class for generating pass/fail summaries from utility runs. It follows VBStyle with `Run()` dispatch (`add`, `summary`, `clear`), `self.state` dict, and Tuple3 returns.

---

## 3. Scheduler — Timer & Event Engine

**File:** `core/utility/scheduler.py`

Reads `Config.SCHEDULES` and fires triggers automatically.

### Modes

- **Timer-based:** `interval > 0` — runs every N seconds in a background thread
- **Event-based:** `interval = 0` — runs when `fire_event()` is called
- **Manual:** user calls `Run("run_trigger", {"trigger": "startup"})`

### How It Works

1. On `start()`, reads all schedules from Config
2. For each schedule with `interval > 0`, starts a background thread that fires the trigger every N seconds
3. For event-based schedules (`interval = 0`), waits for `fire_event("trigger_name")` to be called
4. Each fire dispatches to the Orchestrator with the trigger name

### Usage

```python
from core.utility.scheduler import Scheduler
from core.utility.orchestrator import Orchestrator

orch = Orchestrator()
sched = Scheduler(orch)
sched.start()                          # starts all timer-based schedules
sched.fire_event("code_change")        # manually fire an event trigger
sched.fire_event("error")              # fire error trigger
```

---

## 4. Orchestrator — Dispatch & Failure Handling

**File:** `core/utility/orchestrator.py`

Reads `Config.TRIGGERS` and executes utilities in order.

### Responsibilities

- Instantiates all utility classes on init
- Reads trigger definitions from `Config.TRIGGERS`
- Executes utilities in `order` sequence
- Handles failures per `on_fail` policy (`report`, `continue`, `escalate`, `cancel`)
- Collects results from all utilities
- Returns aggregated Tuple3

### How It Dispatches

1. Receives trigger name (e.g. `"startup"`)
2. Looks up `Config.TRIGGERS["startup"]` — gets ordered list
3. Sorts entries by `order` field
4. For each entry:
   - Gets the utility instance (e.g. `self.domindexer`)
   - Calls `utility.Run(command, params)`
   - Checks the Tuple3 result
   - If failure: applies `on_fail` policy
5. Returns collected results

### Usage

```python
from core.utility.orchestrator import Orchestrator

orch = Orchestrator()
code, results, err = orch.run_trigger("startup")
# results = [{"util": "SystemCheck", "ok": True, ...}, ...]
```

---

## 5. Indexer — In-RAM SQLite Code Index with AI Reasoning

**File:** `core/Dom_Unified/DomIndexer.py` (upgraded)
**Legacy:** `core/utility/indexer.py` (deprecated — list-based, no SQLite, no reasoning)

The Indexer uses an **in-RAM SQLite database** (`:memory:`) for super-fast queries with microsecond lookups. It parses Python files with the `vbast` C binary (when available) or falls back to Python's built-in `ast` module. Stores file paths, file names, classes, methods, functions, BCL stamps, call/import edges, and AI reasoning over code.

### Architecture

```
.py Files on Disk
       |
       v
  +--------------+
  |  PARSE LAYER |  vbast C binary (fast) -> Python ast fallback (always available)
  +------+-------+
         |
         v
  +----------------------------------+
  |  IN-RAM SQLite (:memory:)        |
  |  files        - path, hash, size |
  |  classes      - name, bases, doc |
  |  methods      - name, sig, params|
  |  functions    - top-level funcs  |
  |  bcl_stamps   - BCL identity     |
  |  edges        - CALLS, IMPORTS   |
  |  reasoning    - AI understanding |
  +----------------------------------+
         |
         v
  +--------------+
  |  QUERY LAYER |  find_class, find_method, graph, reasoning search
  +--------------+
```

### What It Does

1. **Parses files** — vbast C binary for fast AST extraction, Python `ast` module as automatic fallback
2. **Extracts BCL headers** — `[@GHOST]`, `[@VBSTYLE]`, `[@SUMMARY]`, `[@WCL]` from file comments
3. **Stores in-RAM SQLite** — 7 tables with indexes for microsecond queries:
   - `files` — file_path, file_name, file_hash, file_size, line_count, domain, parsed_at
   - `classes` — class_name, base_classes, decorators, line range, method_count, docstring
   - `methods` — method_name, class_name, signature, params, line range, docstring
   - `functions` — function_name, signature, params, line range, docstring (top-level functions)
   - `bcl_stamps` — unit_name, unit_type, stamp_hash, stamp_data (BCL identity tokens)
   - `edges` — source, target, edge_type (CALLS, IMPORTS, CONTAINS, INHERITS), line_number
   - `reasoning` — reasoning_text, reasoning_type, confidence, created_at (AI understanding)
4. **Incremental indexing** — `index_incremental` skips files whose hash hasn't changed
5. **AI reasoning storage** — store and query LLM-generated understanding of code
6. **Graph queries** — build adjacency lists from edges for call graphs, import graphs
7. **Export/import** — persist the in-RAM DB to disk and back

### Two Parser Modes

| Mode | When | Speed | Features |
|---|---|---|---|
| **vbast** (C binary) | Available at `~/bin/vbast` or `Cascade_toolStack/vbast/vbast` | Fast | Full AST + violations + BCL stamps |
| **Python ast** (fallback) | vbast not found or parse fails | Moderate | Classes, methods, functions, CALLS/IMPORTS edges, BCL headers |

### Domain Fallback

If a file has no `[@GHOST]` header (or no `[@domain<...>]` inside it), the Indexer falls back to the parent directory name as the domain.

### Commands

| Command | Params | Returns |
|---|---|---|
| `index` | `{"file": "/path/file.py"}` | `(1, {file_id, classes, methods, functions, edges, bcl_stamps}, None)` |
| `index_dir` | `{"path": "/dir", "pattern": "*.py"}` | `(1, {files_found, files_indexed, total_classes, ...}, None)` |
| `index_incremental` | `{"path": "/dir"}` | `(1, {files_found, files_indexed, files_skipped, ...}, None)` |
| `scan_file` / `scan_dir` | same as `index` / `index_dir` | aliases for pipeline compatibility |
| `find_class` | `{"name": "..."}` or `{"pattern": "..."}` | `(1, {count, classes: [...]}, None)` |
| `find_method` | `{"name": "..."}` or `{"pattern": "..."}` or `{"class_name": "..."}` | `(1, {count, methods: [...]}, None)` |
| `find_function` | `{"name": "..."}` or `{"pattern": "..."}` | `(1, {count, functions: [...]}, None)` |
| `find_file` | `{"path": "..."}` or `{"name": "..."}` or `{"pattern": "..."}` | `(1, {count, files: [...]}, None)` |
| `classes` | `{"limit": 1000}` | `(1, {count, classes: [...]}, None)` |
| `methods` | `{"limit": 1000, "class_name": "..."}` | `(1, {count, methods: [...]}, None)` |
| `functions` | `{"limit": 1000}` | `(1, {count, functions: [...]}, None)` |
| `edges` | `{"type": "CALLS", "source": "...", "limit": 1000}` | `(1, {count, edges: [...]}, None)` |
| `bcl` | `{"unit_name": "...", "file": "..."}` | `(1, {count, bcl_stamps: [...]}, None)` |
| `reasoning` | `{"action": "add", "file": "...", "text": "...", "confidence": 0.85}` | `(1, {added, id}, None)` |
| `reasoning` | `{"action": "get", "file": "..."}` | `(1, {count, reasoning: [...]}, None)` |
| `reasoning` | `{"action": "search", "query": "keyword"}` | `(1, {count, reasoning: [...]}, None)` |
| `graph` | `{"type": "CALLS", "direction": "forward"}` | `(1, {nodes, edges, adjacency}, None)` |
| `stats` | none | `(1, {files, classes, methods, functions, edges, bcl_stamps, reasoning, domains}, None)` |
| `export` | `{"path": "/tmp/index.db"}` | `(1, {exported, path, size}, None)` |
| `import_db` | `{"path": "/tmp/index.db"}` | `(1, {imported, path}, None)` |
| `clear` | none | `(1, {cleared: True}, None)` |
| `read_state` | none | `(1, state_dict, None)` |

### Usage

```python
from Dom_Unified import DomIndexer

idx = DomIndexer()

# Index a directory (full scan)
ok, stats, err = idx.Run("index_dir", {"path": "core/"})
# stats = {"files_found": 25, "files_indexed": 25, "total_classes": 24, ...}

# Incremental scan (skips unchanged files)
ok, stats, err = idx.Run("index_incremental", {"path": "core/"})
# stats = {"files_found": 25, "files_indexed": 2, "files_skipped": 23, ...}

# Find a class
ok, data, err = idx.Run("find_class", {"name": "Indexer"})

# Build a call graph
ok, data, err = idx.Run("graph", {"type": "CALLS"})
# data = {"type": "CALLS", "nodes": 233, "edges": 1159, "adjacency": {...}}

# Add AI reasoning for a file
ok, data, err = idx.Run("reasoning", {
    "file": "core/utility/indexer.py",
    "action": "add",
    "text": "Scans Python files using AST to extract BCL headers and class/method metadata.",
    "reasoning_type": "understanding",
    "confidence": 0.85
})

# Query reasoning
ok, data, err = idx.Run("reasoning", {"file": "core/utility/indexer.py", "action": "get"})

# Export index to disk for persistence
ok, data, err = idx.Run("export", {"path": "/tmp/code_index.db"})
```

### Pipeline Role

The Indexer runs at **startup** (order 2, after SystemCheck) and builds the in-RAM SQLite index that downstream utilities use:
- **DiffCheck** compares before/after index snapshots
- **StatsReport** generates markdown reports from the index
- **DomAudit** uses index data for drift detection
- **SystemCheck** uses DomIndexer internally for domain integrity checks

### AI Reasoning and MemUnit Connection

The `reasoning` table stores LLM-generated understanding of code. This connects to the broader reasoning infrastructure:

- **DomIndexer.reasoning** — fast in-RAM storage for active session reasoning
- **MemUnit** (`Dom_Graph/MemUnit.py`) — persistent MySQL-backed reasoning state store with nodes (tasks, decisions, facts, errors) and edges (DEPENDS, PRODUCES, RESOLVES, CONTRADICTS)
- **BCL stamps** (`bcl_stamps` table) — AI identity tokens following the BCL Code Graph Pipeline (Ingest, Extract, Classify, Compile, CU, Identity, Edges, Stamps)
- **InRamDb** (`Dom_Graph/InRamDb.py`) — event sourcing schema for MemUnit with AST nodes, versions, BCL stamps, dependency edges

The flow: DomIndexer indexes code files, extracts BCL headers, stores structural edges (CALLS, IMPORTS). AI then reasons over each class/method, stores understanding in the `reasoning` table. BCL stamps capture identity. MemUnit persists reasoning across sessions in MySQL.

---

## 6. VbsScanner — VBStyle Violation Detector

**File:** `core/utility/vbs_scanner.py`

Scans Python files for VBStyle compliance violations using AST parsing.

### What It Checks

- **`print()` calls** — no print statements allowed
- **Decorators** — `@property`, `@staticmethod`, `@classmethod` forbidden
- **`self._` private attributes** — use `self.state` dict instead
- **Missing BCL headers** — `[@GHOST]` and `[@VBSTYLE]` required
- **Missing `Run()` method** — every class must have a `Run()` dispatch
- **Non-Tuple3 returns** — methods must return `(code, data, error)` triples
- **Class naming** — PascalCase required (no snake_case classes)
- **Tabs** — spaces only, no tab characters
- **Trailing whitespace** — no trailing spaces on lines

### Commands

| Command | Params | Returns |
|---|---|---|
| `scan_dir` | `{"path": "core/"}` | `(1, {violations, files, ...}, None)` |
| `scan_file` | `{"path": "file.py"}` | `(1, {violations, ...}, None)` |
| `get_violations` | none | `(1, violation_list, None)` |
| `read_state` | none | `(1, state_dict, None)` |

### Pipeline Role

Runs at **startup** (order 3) after DomIndexer. Also runs on **code_change** events via VbsTest.

---

## 7. VbsTest — Compliance & Compile Checks

**File:** `core/utility/vbs_test.py`

Combined VBStyle compliance checker and test engine. Provides assert, unit, integration, benchmark, mock, fixture, coverage, and compile checks in one utility.

### Features

- **VBStyle compliance** — `vbs_check`, `vbs_check_file`, `vbs_check_folder`, `vbs_check_method`
- **Assertions** — `assert` with operators: eq, ne, gt, gte, lt, lte, in, not_in, is_none, is_not_none, is_true, is_false
- **Unit tests** — run a callable, compare to expected
- **Integration tests** — multi-step test sequences
- **Benchmarks** — run a function N iterations, measure avg/min/max time
- **Mocks** — set/get/clear mock return values
- **Fixtures** — set/get/clear test fixtures
- **Coverage** — compare executed lines against total lines
- **Compile** — `py_compile` check on a file
- **Report** — pass/fail/skip summary with percentages

### Commands

| Command | Params | Returns |
|---|---|---|
| `vbs_check` | `{"code": source_text}` | `(1, {status, violations}, None)` or `(0, {violations}, err)` |
| `vbs_check_file` | `{"path": "file.py"}` | same as vbs_check |
| `vbs_check_folder` | `{"path": "core/"}` | `(1, {results, files, violations}, None)` |
| `vbs_check_method` | `{"code": src, "method_name": "Run"}` | `(1, {status, method}, None)` |
| `assert` | `{"actual": x, "expected": y, "op": "eq", "name": "test"}` | `(1, {passed: True}, None)` |
| `unit` | `{"name": "test", "func": callable, "expected": val}` | `(1, {passed, actual, elapsed}, None)` |
| `integration` | `{"steps": [{name, func, args}, ...]}` | `(1, {steps, passed, total}, None)` |
| `benchmark` | `{"iterations": 100, "func": callable}` | `(1, {avg, min, max}, None)` |
| `compile_file` | `{"path": "file.py"}` | `(1, {compiled: True}, None)` |
| `report` | none | `(1, markdown_string, None)` |

### Pipeline Role

Runs on **code_change** trigger (order 1: vbs_check_folder, order 2: compile_file).

---

## 8. SystemCheck — Integrity Verification

**File:** `core/utility/system_check.py`

Verifies integrity of all `core/` files. Runs first at startup.

### What It Checks

1. **Index scan** — uses DomIndexer to scan core domains
2. **Compress roundtrip** — verifies Compress encode/decode roundtrip
3. **py_compile** — compiles every `.py` file in core/
4. **Importability** — checks that each domain package can be imported
5. **Domain integrity** — verifies each domain has `__init__.py` and a Config file

### Commands

| Command | Params | Returns |
|---|---|---|
| `check_all` | `{"root": PROJECT_ROOT}` | `(1, report_dict, None)` |
| `check_compile` | `{"root": path}` | `(1, {passed, failed, ...}, None)` |
| `check_imports` | `{"root": path}` | `(1, {passed, failed, ...}, None)` |
| `check_domains` | `{"root": path}` | `(1, {domains, ...}, None)` |
| `read_state` | none | `(1, state_dict, None)` |

### Pipeline Role

Runs at **startup** (order 1) — first utility to execute. Uses DomIndexer, Compress, and VbsScanner internally.

---

## 9. DomAudit — Baseline, Drift & Compliance

**File:** `core/utility/dom_audit.py`

Tracks baselines, detects drift, checks compliance rules, and maintains an audit trail.

### Features

- **Baseline** — hash a named data snapshot (SHA-256)
- **Drift detection** — compare current data hash to baseline
- **Compliance** — check data against rules (exists, eq, ne, gte, lte)
- **Diff** — unified diff between two texts
- **Flag/violation/fix/escalate** — record audit events
- **Trace** — filter history by target
- **Report** — full audit report (dict or JSON)

### Commands

| Command | Params | Returns |
|---|---|---|
| `baseline` | `{"name": "core_index", "data": {...}}` | `(1, {name, hash}, None)` |
| `drift` | `{"name": "core_index", "data": current}` | `(1, {drifted, current, baseline}, None)` |
| `compliance` | `{"rules": [...], "data": {...}}` | `(1, {passed, failed, compliant}, None)` |
| `diff` | `{"a": text1, "b": text2}` | `(1, {changes, count}, None)` |
| `flag` | `{"target": "...", "reason": "...", "severity": "low"}` | `(1, {flagged: True}, None)` |
| `violation` | `{"rule": "...", "target": "...", "detail": "..."}` | `(1, {recorded: True}, None)` |
| `fix` | `{"issue": "...", "action": "..."}` | `(1, {applied: True}, None)` |
| `escalate` | `{"issue": "...", "level": 2, "to": "admin"}` | `(1, {escalated: True}, None)` |
| `trace` | `{"target": "..."}` | `(1, {trace, count}, None)` |
| `history` | `{"limit": 20}` | `(1, {entries, count}, None)` |
| `report` | `{"format": "json"}` | `(1, {format, report}, None)` |

### Pipeline Role

Runs on **change** trigger (order 1: drift detection) and **scheduled** trigger (order 2: audit report).

---

## 10. DiffCheck — Before/After Index Comparison

**File:** `core/utility/diff_check.py`

Compares two index snapshots and reports what was added, removed, or changed.

### What It Compares

- **Files** — added / removed file paths
- **Classes** — added / removed class names (keyed by `file.ClassName`)
- **Methods** — added / removed methods per class
- **Domains** — added / removed domains

### Commands

| Command | Params | Returns |
|---|---|---|
| `compare` | `{"before": index, "after": index}` | `(1, diff_dict, None)` |
| `compare_dirs` | `{"before_dir": path, "after_dir": path}` | `(1, diff_dict, None)` |
| `get_diff` | none | `(1, last_diff, None)` |
| `read_state` | none | `(1, state_dict, None)` |

### Diff Output Structure

```python
{
    "files": {"added": [...], "removed": [...]},
    "classes": {"added": [...], "removed": [...]},
    "methods": {"added": [...], "removed": [...]},
    "domains": {"added": [...], "removed": [...]},
    "summary": {"files_added": N, "files_removed": N, ...},
}
```

### Pipeline Role

Runs on **change** trigger (order 2). Uses DomIndexer internally for `compare_dirs`.

---

## 11. StatsReport — Directory Statistics

**File:** `core/utility/stats_report.py`

Generates a markdown report from the file index with domain summaries, class inventories, cross-domain imports, and a method index.

### Report Sections

1. **Domain Summary** — files, classes, methods, lines per domain (markdown table)
2. **Class Inventory** — all classes with file, domain, methods, lines, bases
3. **Cross-Domain Imports** — which domains import from which
4. **Method Index** — all methods across all files, sorted by domain/class/method

### Commands

| Command | Params | Returns |
|---|---|---|
| `report_dir` | `{"path": "core/"}` | `(1, markdown_string, None)` |
| `report_index` | `{"index": [...]}` | `(1, markdown_string, None)` |
| `get_report` | none | `(1, last_report, None)` |
| `read_state` | none | `(1, state_dict, None)` |

### Pipeline Role

Runs on **change** trigger (order 3) and **scheduled** trigger (order 1). Uses DomIndexer internally.

---

## 12. ContentExtract — Regex-Based Source Analysis

**File:** `core/utility/content_extract.py`

Extracts metadata from Python source text using regex patterns. Complements DomIndexer's AST approach with regex-based detection.

### What It Extracts

- **Classes, methods, functions, imports** — regex-based
- **BCL header tokens** — `[@GHOST]`, `[@VBSTYLE]` presence
- **VBStyle violations** — `print()` calls, decorators, `self._`, hardcoded paths
- **SQL calls** — `.execute()` calls, table names
- **File I/O** — `open()`, `read()`, `write()`, `close()` calls
- **Error handling** — `raise` count, `try/except` count
- **Tuple3 mentions** — return pattern detection
- **Config mentions** — references to Config
- **Main exec** — `if __name__ == "__main__"` presence

### Commands

| Command | Params | Returns |
|---|---|---|
| `extract` | `{"content": source_text}` | `(1, result_dict, None)` |
| `extract_file` | `{"path": "file.py"}` | `(1, result_dict, None)` |
| `get_result` | none | `(1, last_result, None)` |
| `read_state` | none | `(1, state_dict, None)` |

### Pipeline Role

Runs on **code_change** trigger (order 3) and **scan** trigger (order 1).

---

## 13. PreFlight — Database Integrity Checks

**File:** `core/utility/preflight.py`

Validates SQLite database integrity before operations. Runs on DB changes.

### What It Checks

1. **Constraint violations** — NOT NULL columns with NULL values
2. **Orphan rows** — foreign key references to missing parent rows
3. **Type overflow** — VARCHAR/TEXT values exceeding column length limits
4. **FK resolution** — simulate FK joins to verify connectivity

### Commands

| Command | Params | Returns |
|---|---|---|
| `check` | `{"db_path": "/path/to/db.sqlite"}` | `(1, full_report, None)` |
| `detect_constraints` | `{"db_path": "..."}` | `(1, {violations, count}, None)` |
| `detect_orphans` | `{"db_path": "..."}` | `(1, {orphans, count}, None)` |
| `detect_overflow` | `{"db_path": "..."}` | `(1, {overflows, count}, None)` |
| `simulate_fk` | `{"db_path": "..."}` | `(1, {fk_results, count}, None)` |
| `migration_report` | `{"db_path": "..."}` | `(1, full_report, None)` |
| `read_state` | none | `(1, state_dict, None)` |

### Pipeline Role

Runs on **db_change** trigger (order 1, on_fail: report).

---

## 14. ErrorHandler — Capture, Classify, Recover

**File:** `core/utility/error_handler.py`

The most complex utility (561 lines, 20+ methods). Wraps every Tuple3 result through an error pipeline with capture, classification, recovery, retry, circuit breakers, bulkheads, and health checks.

### Features

**Error Capture & Classification:**
- `consume_engine_result` — pass any Tuple3 from any Run() call; auto-captures failures
- `capture_error` — records error to SQLite log with severity, category, stack trace
- `classify_error` — looks up error definition by code or log ID
- `register_error_definition` — define error codes with severity, recovery action, max retries

**Recovery:**
- `get_recovery_policy` — looks up recovery action for an error code
- `execute_recovery` — applies recovery action (ignore, retry, rollback, cancel, snapshot, mark_invalid, request_user)

**Resilience Patterns:**
- `retry` — retry a callable with exponential backoff
- `circuit_breaker` — open/closed/half-open state machine with failure threshold
- `record_outcome` — record success/failure to circuit breaker
- `fallback` — try primary, fall back to secondary on exception
- `bulkhead` — concurrency limiter (max concurrent operations)
- `timeout` — run a function with a timeout in a background thread

**Monitoring:**
- `get_error_log` — query error log (all or unresolved only)
- `get_error_stats` — total, unresolved, top error codes
- `correlate_errors` — group errors by time window
- `health_check` — check all circuit breakers and bulkheads

### Severity Levels

- `info` — informational
- `warning` — warning condition
- `error` — error condition
- `critical` — critical failure

### Recovery Actions

- `ignore` — dismiss the error
- `retry` — suggest retrying the operation
- `rollback` — request rollback
- `cancel` — cancel the operation
- `snapshot` — request snapshot restore
- `mark_invalid` — mark the data/object as invalid
- `request_user` — require user input

### SQLite Schema

ErrorHandler creates three tables in `error_handler.db`:
- `error_definitions` — error code → severity, category, recovery action, max retries
- `error_log` — timestamped error entries with stack traces and resolution status
- `recovery_policies` — per-error-code recovery actions

### Usage

```python
from core.utility.error_handler import ErrorHandler

eh = ErrorHandler()

# Wrap any engine call
result = some_engine.Run("do_thing", params)
code, data, err = eh.Run("consume", {"result": result, "source": "some_engine"})

# Retry with backoff
code, data, err = eh.Run("retry", {"fn": risky_func, "attempts": 3, "delay": 0.5, "backoff": 2.0})

# Circuit breaker
eh.Run("circuit_breaker", {"name": "db_conn", "threshold": 5, "reset_timeout": 30.0})
eh.Run("record_outcome", {"name": "db_conn", "success": False})
code, state, err = eh.Run("get_breaker_state", {"name": "db_conn"})
```

### Pipeline Role

Runs on **error** trigger (order 1: consume, order 3: get_recovery_policy) and **scheduled** trigger (order 3: get_stats).

---

## 15. ErrorTracker — MySQL Lessons Lookup

**File:** `core/utility/error_tracker.py`

Queries MySQL `vb_shared` database for known error patterns, problems, and solutions. Ensures lessons carry forward across sessions.

### Three Knowledge Stores

1. **MySQL `vb_shared.learned_rules`** (10,540 rules) — pattern → fix_action with confidence
2. **MySQL `vb_shared.know_problems`** (218 problems) — known problems with descriptions
3. **MySQL `vb_shared.know_solutions`** (336 solutions) — solutions linked to problems

### Local SQLite Log

ErrorTracker also maintains a local `error_log.db` with an `errors` table for session-level error recording.

### Commands

| Command | Params | Returns |
|---|---|---|
| `search` | `{"keyword": "missing Run"}` | `(1, {learned_rules, problems, solutions}, None)` |
| `record` | `{"error": "...", "cause": "...", "solution": "..."}` | `(1, {recorded: True}, None)` |
| `save_rule` | `{"pattern": "...", "fix_action": "...", "confidence": 0.9}` | `(1, {saved: True}, None)` |
| `get_log` | `{"limit": 20}` | `(1, {entries, count}, None)` |
| `read_state` | none | `(1, state_dict, None)` |

### MySQL Connectivity Check

ErrorTracker checks MySQL connectivity on init. If MySQL is unavailable, it gracefully degrades to local-only mode (SQLite log still works, but MySQL queries return empty).

### Pipeline Role

Runs on **error** trigger (order 2: match known lessons for the error text).

---

## 16. MSearch — MySQL + Qdrant Search

**File:** `core/utility/msearch.py`

Search utility that wraps the `msearch` binary for keyword, semantic, and hybrid search across MySQL databases and Qdrant vector collections.

### Search Modes

- **Keyword search** — MySQL queries across `vb_shared`, `CODEBASE`, all databases
- **Semantic search** — Qdrant vector search with BGE auto-embedding
- **Hybrid search** — MySQL + Qdrant combined
- **Table discovery** — `--where`, `--count`, `--qstats` modes

### Usage

```python
from core.utility import MSearch

ms = MSearch()

# Keyword search
code, data, err = ms.Run("keyword", {
    "keyword": "GhostBracket",
    "table": "learned_rules"
})

# Semantic search
code, data, err = ms.Run("semantic", {
    "query": "bracket packet parser for code graph analysis",
    "limit": 10
})

# Hybrid search
code, data, err = ms.Run("hybrid", {
    "keyword": "eyes",
    "query": "multi-dimensional code inspection perspectives",
    "limit": 5
})
```

### Auto-Query in Pipeline

MSearch can be triggered automatically:
- On `startup` → index available databases
- On `error` → search `learned_rules` and `know_problems` for matching errors
- On `change` → search for related code in other domains

---

## 17. Cleaner — Artifact Removal

**File:** `core/utility/cleaner.py`

Removes build artifacts, `__pycache__` directories, `.pyc` files, and temp files.

### What It Removes

- Directories: `__pycache__`
- Extensions: `.pyc`, `.pyo`, `.tmp`, `.DS_Store`
- Skips: `.git`, `.venv`, `venv`, `node_modules`, `.tox`

### Commands

| Command | Params | Returns |
|---|---|---|
| `clean` | `{"path": "core/", "dry_run": True}` | `(1, {removed_dirs, removed_files, ...}, None)` |
| `read_state` | none | `(1, state_dict, None)` |

### Pipeline Role

Runs at **startup** (order 4, on_fail: continue). Default is `dry_run: True` — set to `False` to actually delete.

---

## 18. Compress — zlib + base64 Compression

**File:** `core/utility/compress.py`

Combines multiple `.py` files into a single compressed output using zlib compression and base64 encoding. Used by SystemCheck for roundtrip verification.

### Commands

| Command | Params | Returns |
|---|---|---|
| `encode` | `{"files": ["a.py", "b.py"]}` | `(1, {compressed, file_count, ...}, None)` |
| `decode` | `{"data": compressed_string}` | `(1, {files, ...}, None)` |
| `roundtrip` | `{"files": [...]}` | `(1, {match: True}, None)` |
| `read_state` | none | `(1, state_dict, None)` |

### Pipeline Role

Used by SystemCheck for integrity verification (roundtrip test). Not directly triggered by Config.TRIGGERS.

---

## 19. Backup — Full Redundancy (Zip + S3 + Email + Git)

**File:** `core/utility/backup.py`

Creates redundant backups of the codebase through multiple channels: ZIP compression, AWS S3 upload, email notification, and Git commit/push.

### Backup Steps (configurable via `Config.BACKUP_STEPS`)

1. **ZIP** — compress project into timestamped `.zip` file
2. **S3** — upload zip to AWS S3 via boto3
3. **Email** — send download link via Gmail/Yahoo/SMTP
4. **Git** — commit changes and push to remote

### Commands

| Command | Params | Returns |
|---|---|---|
| `backup_all` | `{"project": PROJECT_ROOT}` | `(1, {steps, results, ...}, None)` |
| `zip` | `{"project": path}` | `(1, {zip_path, size}, None)` |
| `s3` | `{"zip_path": "..."}` | `(1, {uploaded: True, url}, None)` |
| `email` | `{"zip_path": "...", "to": "..."}` | `(1, {sent: True}, None)` |
| `git` | `{"project": path}` | `(1, {committed: True, pushed: True}, None)` |
| `read_state` | none | `(1, state_dict, None)` |

### Dependencies

- Uses `Credentials` utility for AWS keys, email passwords, Git tokens
- Uses `boto3` for S3 (optional — step skipped if not installed)
- Uses `smtplib` for email
- Uses `subprocess` for Git operations

### Pipeline Role

Runs on **scheduled** trigger (order 10) and **backup** trigger (order 1).

---

## 20. Credentials — Secret Management

**File:** `core/utility/credentials.py`

Centralized manager for accessing secrets. Loads from environment variables and a local `.credentials` file.

### Three Sources (checked in order)

1. **Environment variables** (highest priority — CI/CD, docker)
2. **Local `.credentials` file** (base64-encoded JSON, user-managed)
3. **Fallback defaults** (hardcoded safe defaults for dev)

### Supported Secrets

- **Gmail** — email, password
- **Yahoo** — email, password
- **S3** — access key, secret key, bucket
- **Git** — token, remote
- **MySQL** — host, user, password, database
- **API keys** — various third-party API keys

### Commands

| Command | Params | Returns |
|---|---|---|
| `get` | `{"key": "GMAIL_PASSWORD"}` | `(1, value, None)` |
| `set` | `{"key": "...", "value": "..."}` | `(1, {set: True}, None)` |
| `load` | none | `(1, {loaded: True, count: N}, None)` |
| `save` | none | `(1, {saved: True}, None)` |
| `list_keys` | none | `(1, [keys], None)` |
| `check_missing` | `{"keys": [...]}` | `(1, {missing: [...]}, None)` |
| `read_state` | none | `(1, state_dict, None)` |

### Security

- `.credentials` file is base64-encoded JSON (not plaintext)
- `mask()` method replaces sensitive values with `***` for logging
- Environment variables always take priority over file

### Pipeline Role

Used by `Backup` utility for S3 keys, email passwords, and Git tokens. Not directly triggered by Config.TRIGGERS.

---

## 21. Pipeline Scenarios

### Scenario 1: Startup (boot)

```
1. Scheduler starts → fires "startup" trigger
2. Orchestrator reads Config.TRIGGERS["startup"]
3. Executes in order:
   a. SystemCheck.Run("check_all", {root: PROJECT_ROOT})     → verify integrity
   b. DomIndexer.Run("index_dir", {path: PROJECT_ROOT})       → build in-RAM SQLite index
   c. VbsScanner.Run("scan_dir", {path: PROJECT_ROOT})        → find VBStyle violations
   d. Cleaner.Run("clean", {path: PROJECT_ROOT, dry_run: True}) → remove build artifacts
4. Results collected, failures logged per on_fail policy
5. State updated
```

### Scenario 2: Code Change (file edited)

```
1. User edits a .py file → fire_event("code_change")
2. Orchestrator reads Config.TRIGGERS["code_change"]
3. Executes in order:
   a. VbsTest.Run("vbs_check_folder", {path: changed_dir})    → verify VBStyle compliance
   b. VbsTest.Run("compile_file", {path: changed_file})       → compile check
   c. ContentExtract.Run("extract_file", {path: changed_file}) → extract metadata
4. If any fail with on_fail="report" → logged but pipeline continues
5. Results returned to caller
```

### Scenario 3: Error Occurs

```
1. Any utility returns (0, None, (code, desc, 0)) → fire_event("error")
2. Orchestrator reads Config.TRIGGERS["error"]
3. Executes in order:
   a. ErrorHandler.Run("consume", {result: error_result})     → capture and classify
   b. ErrorTracker.Run("match", {error_text: desc})           → lookup known lessons
   c. ErrorHandler.Run("get_recovery_policy", {error_code})    → determine action
4. Recovery policy returned: retry / skip / abort
```

### Scenario 4: Hourly Scheduled

```
1. Scheduler timer fires every 3600 seconds
2. Orchestrator reads Config.TRIGGERS["scheduled"]
3. Executes in order:
   a. StatsReport.Run("report_dir", {path: PROJECT_ROOT})     → generate stats
   b. DomAudit.Run("report", {})                              → audit trail
   c. ErrorHandler.Run("get_stats", {})                        → error statistics
   d. Backup.Run("backup_all", {project: PROJECT_ROOT})        → full backup
4. All results collected
```

### Scenario 5: DB Change

```
1. Database file modified → fire_event("db_change")
2. Orchestrator reads Config.TRIGGERS["db_change"]
3. Executes:
   a. PreFlight.Run("check", {db_path: changed_db})           → verify DB integrity
4. Report generated with constraint/orphan/overflow/FK results
```

---

## 22. File Locations

All utilities live in `core/utility/`:

```
core/utility/
├── Config.py           — TRIGGERS, SCHEDULES, TARGETS, ON_FAIL_ACTIONS
├── __init__.py         — exports all utility classes
├── scheduler.py        — Scheduler (timer/event trigger engine)
├── orchestrator.py     — Orchestrator (dispatch + failure handling)
├── msearch.py          — MSearch (MySQL + Qdrant search wrapper)
├── indexer.py          — Indexer (legacy list-based, deprecated)
├── DomIndexer.py       — DomIndexer (upgraded: in-RAM SQLite + AI reasoning) [core/Dom_Unified/]
├── vbs_scanner.py      — VbsScanner (VBStyle violation detector)
├── vbs_test.py         — VbsTest (compliance + compile checks)
├── cleaner.py          — Cleaner (artifact removal)
├── compress.py         — Compress (file combining)
├── system_check.py     — SystemCheck (integrity verification)
├── dom_audit.py        — DomAudit (audit trail + drift)
├── diff_check.py       — DiffCheck (before/after comparison)
├── stats_report.py     — StatsReport (directory statistics)
├── preflight.py        — PreFlight (DB integrity checks)
├── content_extract.py  — ContentExtract (metadata extraction)
├── error_tracker.py    — ErrorTracker (known error lookup)
├── error_handler.py    — ErrorHandler (error classification + recovery)
├── backup.py           — Backup (zip + s3 + email + git)
└── credentials.py      — Credentials (API keys, passwords)
```

---

## 23. How to Extend

### Add a New Utility

1. Create `new_util.py` in `core/utility/` with VBStyle headers (`[@GHOST]`, `[@VBSTYLE]`, `[@SUMMARY]`, `[@WCL]`)
2. Class inherits VBStyle pattern: `__init__(self, mem=None, db=None, param=None)`, `Run`, `read_state`, `_p`
3. Add to `Config.TRIGGERS` under the appropriate trigger
4. Add import to `orchestrator.py`
5. Add to `__init__.py` exports
6. Test: `PYTHONPATH=. python3 -c "from core.utility import NewUtil; print(NewUtil().Run('test', {}))"`

### Add a New Trigger

1. Add entry to `Config.TRIGGERS` with ordered utility list
2. Add entry to `Config.SCHEDULES` with interval + enabled flag
3. Scheduler will auto-pick it up on next cycle
4. Or fire manually: `scheduler.fire_event("new_trigger")`
