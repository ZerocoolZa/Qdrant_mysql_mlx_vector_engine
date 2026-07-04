# Error Capture Pipeline — Errors Become Reusable Knowledge

> **Core thesis:** Every error is a lesson. When code fails, the error is captured
> into a database with its cause, solution, and frequency. Next time the same
> error pattern appears, the system already knows the fix — preventing recurrence.
>
> "Errors become data. Data prevents errors." — Kevin & Wayne

---

## Pipeline Overview

```
Code Runs → Error Occurs → Capture (signature + cause + solution)
                                    ↓
                            ┌───────┴────────┐
                            │                │
                       SQLite (local)    MySQL (global)
                     error_knowledge     learned_rules
                     error_log.db       know_problems
                                       know_solutions
                                       error_knowledge
                                       governance
                            └───────┬────────┘
                                    │
                              Query / Match
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
              Prevent()        TopErrors()      AutoApply()
              "Don't do        "Most common     "Fix it
               this again"      errors"          automatically"
```

---

## Two Storage Tiers

### Tier 1: SQLite (Local, Fast, Session-Level)

| DB | Table | Purpose |
|---|---|---|
| `core/Dom_Unified/unified_cache.db` | `error_knowledge` | Violations captured during AST parsing (vbast) |
| `error_log.db` | `error_log` | Session-level error log for immediate recall |
| `error_handler.db` | `error_events` | Runtime error events with classification + recovery |

**SQLite `error_knowledge` schema:**
```sql
CREATE TABLE error_knowledge (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path     TEXT,
    rule          TEXT,           -- VBStyle rule violated
    severity      TEXT,           -- error, warning, info
    message       TEXT,           -- human-readable description
    line_num      INTEGER,
    captured_at   REAL NOT NULL,
    reuse_count   INTEGER DEFAULT 0  -- increments when same error seen again
);
CREATE INDEX idx_error_rule ON error_knowledge(rule);
```

### Tier 2: MySQL (Global, Shared, Cross-Session)

| DB | Table | Rows | Purpose |
|---|---|---|---|
| `vb_shared` | `learned_rules` | 10,590 | Pattern → fix_action with confidence score |
| `vb_shared` | `know_problems` | 309 | Known problems with descriptions |
| `vb_shared` | `know_solutions` | 362 | Solutions linked to problems, weight + auto_apply |
| `vb_shared` | `error_knowledge` | 70 | Error signatures with cause + solution + frequency |
| `vb_shared` | `governance` | 58 | Governance policies, rules, violations, waivers |
| `vb_shared` | `rule_tokens` | 238 | VBStyle rule tokens (canonical rule store) |

**MySQL `learned_rules` schema:**
```sql
CREATE TABLE learned_rules (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    pattern           TEXT NOT NULL,        -- what triggers the error
    trigger_condition TEXT,                 -- when it happens
    fix_action        TEXT NOT NULL,        -- how to fix it
    language          VARCHAR(20),          -- python, c, swift, etc.
    category          VARCHAR(50),          -- VBStyle, import, syntax, etc.
    severity          INT DEFAULT 2,        -- 1=critical, 2=error, 3=warning
    success_count     INT DEFAULT 0,        -- times this fix worked
    failure_count     INT DEFAULT 0,        -- times this fix failed
    confidence        DOUBLE DEFAULT 0.5,   -- 0.0 to 1.0
    source            VARCHAR(100),         -- who/what created this rule
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used         TIMESTAMP NULL        -- when last applied
);
```

**MySQL `know_problems` + `know_solutions` schema:**
```sql
CREATE TABLE know_problems (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    problem     TEXT NOT NULL,      -- e.g. "AttributeError"
    description TEXT,               -- "You tried to access an attribute that does not exist"
    type_id     INT, category_id INT, context_id INT, domain_id INT, token_id INT, rule_id INT,
    source_db   VARCHAR(50) DEFAULT 'token_registry'
);

CREATE TABLE know_solutions (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    problem_id  INT,                -- FK to know_problems
    solution    TEXT NOT NULL,      -- e.g. "REPLACE_PRINT_WITH_RETURN_OR_PASS"
    weight      FLOAT DEFAULT 1,    -- confidence weight
    domain_id   INT, rule_id INT,
    fault_code  TEXT, scope TEXT,
    auto_apply  INT DEFAULT 0       -- 1 = can auto-apply without human approval
);
```

**MySQL `error_knowledge` schema:**
```sql
CREATE TABLE error_knowledge (
    error_id    INT AUTO_INCREMENT PRIMARY KEY,
    signature   VARCHAR(500) UNIQUE,  -- unique error fingerprint
    error_type  VARCHAR(100),         -- ImportError, SyntaxError, etc.
    domain      VARCHAR(100),         -- which code domain
    cause       TEXT,                 -- root cause description
    solution    TEXT,                 -- how to fix
    fix_code    TEXT,                 -- actual code fix
    frequency   INT DEFAULT 1,        -- how many times seen
    last_seen   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    confidence  FLOAT DEFAULT 0.5
);
```

---

## Components

### 1. ErrorCapture (`core/Dom_Unified/ErrorCapture.py`)

The capture engine. Runs during AST parsing — when vbast finds violations, each one is captured.

**Commands:**
| Command | What it does |
|---|---|
| `capture` | Capture violations from one file into `error_knowledge` |
| `capture_batch` | Capture violations from multiple files |
| `query` | Query error knowledge by rule, file, or get all |
| `top_errors` | Get top N most common errors by `reuse_count` |
| `prevent` | Given a file, return errors it has hit before + prevention hints |
| `stats` | Get capture statistics |

**Prevention hints** (built-in for each VBStyle rule):
- `no_type_hints` → "Remove type annotations — VBStyle forbids type hints"
- `no_decorators` → "Remove @property, @staticmethod, @classmethod"
- `no_print_outside_main` → "Use self._p() instead of print()"
- `must_return_tuple3` → "All methods must return (1, data, None) or (0, None, (code, desc, 0))"
- `must_have_run` → "Every class must have a Run(self, command, params=None) dispatch method"
- `no_self_underscore` → "Use self.state['key'] not self._key"
- `ghost_tag` → "Add #[@GHOST] header to file"
- `vbstyle_tag` → "Add #[@VBSTYLE] header to file"

### 2. CacheDb (`core/Dom_Unified/CacheDb.py`)

SQLite storage for both AST cache and error knowledge. Keyed by `file_path + mtime`.

**Error knowledge commands:**
- `capture_error` — INSERT new error or INCREMENT `reuse_count` if same `rule + message` exists
- `query_errors` — Query by rule, file, or get top errors by `reuse_count DESC`

### 3. ErrorTracker (`core/utility/error_tracker.py`)

Queries MySQL `learned_rules`, `know_problems`, `know_solutions` for known fixes.

**Commands:**
| Command | What it does |
|---|---|
| `search` | Search `learned_rules` by keyword (pattern LIKE '%keyword%') |
| `lookup_problem` | Search `know_problems` by keyword |
| `lookup_solution` | Get solutions for a problem |
| `record` | Record a new error with cause + solution to local SQLite |
| `save_lesson` | Save a learned rule to MySQL `learned_rules` |
| `recall` | Get recent errors from local log |
| `match` | Match an error against known patterns (learned_rules + know_problems) |

### 4. ErrorHandler (`core/utility/error_handler.py`)

Runtime error handler — wraps every Tuple3 result through the error pipeline.

**Features:**
- **Capture:** auto-captures failures from any `Run()` call
- **Classify:** severity (info/warning/error/critical)
- **Recover:** ignore / retry / rollback / fallback / circuit_break
- **Retry:** exponential backoff with max attempts
- **Circuit breaker:** trip after N failures, half-open probe, reset
- **Learn:** saves new errors to `learned_rules` with cause + solution

**Key method:** `consume_engine_result()` — pass any Tuple3 from any Run() call:
```python
eh = ErrorHandler()
result = some_engine.Run("do_thing", params)
code, data, err = eh.Run("consume", {"result": result, "source": "some_engine"})
```

### 5. DomGovernance (`code_store_variations/impl_governance.py`)

Governance engine — policies, rules, approvals, reviews, violations, waivers.

**Commands:** `approve`, `compliance`, `constraint`, `enforce`, `escalate`, `exception`, `policy`, `reject`, `report`, `review`, `rule`, `violation`, `waive`

---

## Step-by-Step: How the Error Pipeline Runs

### Scenario 1: VBStyle Violation During Parse

```
1. UnifiedAst.Run("parse", {"file": "eyes_26.py"})
2. vbast C binary parses file → returns violations
3. ErrorCapture.Run("capture", {
       "file": "eyes_26.py",
       "violations": [
           {"rule": "no_print_outside_main", "severity": "error", "message": "print() on line 45", "line": 45},
           {"rule": "must_have_run", "severity": "error", "message": "Class Eye01Tree missing Run()", "line": 12}
       ]
   })
4. CacheDb.capture_error() for each violation:
   a. Check if (rule + message) already exists in error_knowledge
   b. If yes → reuse_count += 1 (same error seen again)
   c. If no → INSERT new row
5. Stats updated: total_captured, total_reused, files_scanned
```

### Scenario 2: Runtime Error During Execution

```
1. Some engine.Run() returns (0, None, ("IMPORT_ERROR", "No module named 'foo'", 0))
2. ErrorHandler.Run("consume", {"result": (0, None, (...)), "source": "engine_name"})
3. ErrorHandler:
   a. Classify: severity = ERROR, error_type = "IMPORT_ERROR"
   b. Capture: save to local error_log.db
   c. Lookup: ErrorTracker.Run("match", {"error": "No module named 'foo'"})
      → queries MySQL learned_rules WHERE pattern LIKE '%import%'
      → queries MySQL know_problems WHERE problem LIKE '%ImportError%'
      → queries MySQL know_solutions for problem_id
   d. Recovery policy:
      - If auto_apply=1 and confidence > 0.8 → auto-apply fix
      - If auto_apply=0 → return fix suggestion to caller
      - If no match → save as new learned_rule with confidence=0.5
   e. Return: (1, {"fix": "pip install foo", "confidence": 0.9, "auto_applied": False}, None)
```

### Scenario 3: Prevention Before Writing Code

```
1. About to edit "eyes_26.py"
2. ErrorCapture.Run("prevent", {"file": "eyes_26.py"})
3. Query error_knowledge WHERE file_path = "eyes_26.py"
4. Returns:
   [
     {"rule": "no_print_outside_main", "times_seen": 5, "prevent_hint": "Use self._p() instead of print()"},
     {"rule": "must_have_run", "times_seen": 2, "prevent_hint": "Every class must have Run()"},
   ]
5. Developer sees hints BEFORE writing code → avoids repeating errors
```

### Scenario 4: Top Errors Across Codebase

```
1. ErrorCapture.Run("top_errors", {"limit": 10})
2. Query: SELECT * FROM error_knowledge ORDER BY reuse_count DESC LIMIT 10
3. Returns:
   [
     {"rule": "no_print_outside_main", "times_seen": 47, "message": "print() found in 47 files"},
     {"rule": "must_have_run", "times_seen": 23, "message": "23 classes missing Run()"},
     {"rule": "no_self_underscore", "times_seen": 15, "message": "self._ found in 15 places"},
   ]
4. Focus cleanup effort on most frequent errors first
```

### Scenario 5: MySQL Learning (Cross-Session)

```
1. Error occurs: "ModuleNotFoundError: No module named 'PyQt6'"
2. ErrorTracker.Run("match", {"error": "ModuleNotFoundError: No module named 'PyQt6'"})
3. MySQL query: SELECT * FROM learned_rules WHERE pattern LIKE '%ModuleNotFoundError%'
4. Found: pattern="ModuleNotFoundError", fix_action="pip install <module_name>", confidence=0.95
5. Fix applied: pip install PyQt6
6. ErrorTracker.Run("save_lesson", {
       "pattern": "ModuleNotFoundError: No module named 'PyQt6'",
       "fix_action": "pip install PyQt6",
       "confidence": 0.95,
       "source": "error_handler"
   })
7. learned_rules row updated: success_count += 1, confidence recalculated
```

---

## File Locations

```
ERROR CAPTURE PIPELINE FILES:
├── core/Dom_Unified/
│   ├── Config.py              — SQLite path, vbast path, cache TTL, CAPTURE_ERRORS flag
│   ├── CacheDb.py             — SQLite storage (ast_cache + error_knowledge tables)
│   ├── ErrorCapture.py        — Capture engine (capture, query, prevent, top_errors)
│   ├── UnifiedAst.py          — Main API (parse → cache → capture errors)
│   ├── __init__.py            — Exports: parse, get_classes, prevent, top_errors, etc.
│   └── unified_cache.db       — SQLite DB (ast_cache + error_knowledge)
│
├── core/utility/
│   ├── error_tracker.py       — MySQL learned_rules/know_problems/know_solutions query engine
│   ├── error_handler.py       — Runtime error handler (capture, classify, recover, retry, learn)
│   └── Config.py              — MySQL config for error tracker
│
├── code_store_variations/
│   └── impl_governance.py     — Governance engine (policies, rules, violations, waivers)
│
├── error_handler.db           — Local SQLite for runtime error events
├── error_log.db               — Local SQLite for session error log
│
└── MySQL vb_shared:
    ├── learned_rules           — 10,590 rules (pattern → fix_action, confidence)
    ├── know_problems           — 309 known problems with descriptions
    ├── know_solutions          — 362 solutions (weight, auto_apply)
    ├── error_knowledge         — 70 error signatures (cause, solution, frequency)
    ├── governance              — 58 governance entries
    └── rule_tokens             — 238 VBStyle rule tokens (canonical)
```

---

## The Dom_Unified Vision (Kevin & Wayne Discussion)

> "Follow code domain unified. Truly use a MySQL/SQLite DB. All code imports from a DB.
> Code unified. We would use because the classes, common, etc. There are a lot of others as well."

The vision: **all code imports from a unified DB**. Instead of `import ast`, you do:

```python
from Dom_Unified import *

classes = get_classes("file.py")        # queries SQLite cache first
methods = get_methods("file.py")        # falls back to vbast C binary
edges   = get_edges("file.py")          # call/import/inherit edges
violations = check_vbstyle("file.py")   # VBStyle rule checks
stamps  = get_bcl_stamps("file.py")     # BCL header extraction
data    = parse("file.py")              # full structured data
hints   = prevent("file.py")            # what errors has this file hit before?
top     = top_errors(10)                # most common errors across codebase
ok      = store("file.py", "bcl_ir")    # write to MySQL
```

**One import, one C binary, one SQLite cache, one error knowledge base.**

### Why unified?

| Problem | Without Dom_Unified | With Dom_Unified |
|---|---|---|
| AST parsing | Every script does `import ast` separately | One vbast C binary, cached |
| Error learning | Each session repeats same mistakes | SQLite + MySQL remember across sessions |
| VBStyle checking | Each tool reimplements scanning | One `check_vbstyle()` function |
| Class/method extraction | Indexer, Scanner, Ingester all parse separately | One `get_classes()` / `get_methods()` |
| Error prevention | No way to know what errors a file hit before | `prevent("file.py")` returns history |

### Current Status

| Component | Status | Location |
|---|---|---|
| UnifiedAst (main API) | **DONE** | `core/Dom_Unified/UnifiedAst.py` |
| CacheDb (SQLite cache) | **DONE** | `core/Dom_Unified/CacheDb.py` |
| ErrorCapture (capture engine) | **DONE** | `core/Dom_Unified/ErrorCapture.py` |
| Config (settings) | **DONE** | `core/Dom_Unified/Config.py` |
| vbast C binary | **DONE** | `Cascade_toolStack/vbast/vbast` |
| dom_unified.py (standalone) | **DONE** | `Cascade_toolStack/vbast/dom_unified.py` |
| ErrorTracker (MySQL query) | **DONE** | `core/utility/error_tracker.py` |
| ErrorHandler (runtime handler) | **DONE** | `core/utility/error_handler.py` |
| DomGovernance (policies) | **DONE** | `code_store_variations/impl_governance.py` |
| MySQL learned_rules | **10,590 rules** | `vb_shared.learned_rules` |
| MySQL know_problems | **309 problems** | `vb_shared.know_problems` |
| MySQL know_solutions | **362 solutions** | `vb_shared.know_solutions` |
| MySQL error_knowledge | **70 signatures** | `vb_shared.error_knowledge` |
| MySQL governance | **58 entries** | `vb_shared.governance` |
| MySQL rule_tokens | **238 tokens** | `vb_shared.rule_tokens` |
| Auto-apply fixes | **PARTIAL** | `know_solutions.auto_apply=1` for 5 solutions |
| Cross-domain code import | **NOT BUILT** | Future: all domains import from unified DB |
