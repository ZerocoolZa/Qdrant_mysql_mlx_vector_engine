# BCL C Engine — Plan & Specification
# =======================================

# [@GHOST]{file_path="core/Dom_Bcl_C_ver/PLAN_SPEC.md"
# date="2026-06-29" author="cascade" context="BCL C Engine full build plan — updated with self-describing binary, config system, multi-language, multi-backend"
# session_id="bcl-c-ver"}

# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}

# [@SUMMARY]{summary="Full specification for the BCL C Engine: 14 C files implementing
# dictionary, parser, config, 9 graph engine units, and execution tracer. Self-describing
# binary with internal config, internal DB, source storage, and multi-language AST support.
# All units use BCL-in/BCL-out interface, shared dictionary, VBStyle C template."}

---

## ARCHITECTURE — 5 LAYERS

### Layer 0: Config (defaults)
- File: bcl_config.c
- Compiled-in default config (fallback values)
- Reads external bcl_config.json at runtime (overrides defaults)
- Provides db_path, backend_type, max_nodes, max_edges, language_mode
- All other units call BclConfig_Get(key) instead of hardcoded #define values
- Supports multiple backends: sqlite (file), sqlite (:memory:), mysql (future)

### Layer 1: BCL Dictionary (grammar)
- File: bcl_dictionary.c
- SQLite table with 94 tag definitions
- Single source of truth for all valid BCL tags
- Every unit queries dictionary for tag validation
- No raw tag strings in any unit — all tags come from dictionary constants

### Layer 2: BCL Parser + Validator + MemUnit (transport + validation + orchestration)
- File: bcl_parser.c — parses [@TAG]{content} brackets into in-memory node tree. Knows ONLY bracket syntax. Does NOT know what RUN, CMD, RESULT, GRAPH mean.
- File: bcl_validator.c — checks parsed tree against dictionary. Is RUN legal here? Is CMD required? Can PARAM appear twice? All semantic rules come from dictionary.
- File: bcl_mem_unit.c — in-RAM SQLite :memory: orchestration bus
- Parser → Validator → Runtime: parser builds tree, validator checks correctness, runtime executes
- MemUnit is the central bus: no unit talks directly to another unit
- All commands go into mu_commands table, results come out of mu_results table
- Events are append-only in mu_events (audit trail, replay support)
- No printf() anywhere — all communication is BCL packets through the MemUnit
- All units link against parser + validator + MemUnit

### Layer 3: Graph Engine (meaning) — 9 units
- Port of existing Python engines to C
- Each is standalone .c file, BCL in / BCL out
- Uses shared parser + dictionary + config + store
- Stores results in configurable backend (default: dom_graph_work.db)
- Language-agnostic — works with graph data, not source code directly

### Layer 4: Execution Tracer (truth)
- File: bcl_execution_tracer.c
- Logs every [@RUN] command + result
- Updates graph in real-time
- Enables replay, audit, dependency tracking

---

## FILE NAMING CONVENTION

All files use the `bcl_` prefix, lowercase, underscore-separated:
- BCL-specific units: `bcl_` + function name (e.g. `bcl_dictionary.c`, `bcl_parser.c`)
- Graph engine units: `bcl_` + domain name (e.g. `bcl_graph_store.c`, `bcl_graph_builder.c`)
- Shared header: `bcl_engine.h` (formerly `vbast.h`)
- CLI entry point: `bcl_engine_cli.c` (formerly `BclDispatcher.c` / `vbast.c`)

No PascalCase filenames. No mixed case. All lowercase with underscores.

---

## FILE LIST (16 files + 1 header)

| # | File | Layer | Purpose | Python Source |
|---|------|-------|---------|---------------|
| 0 | bcl_config.c | 0 | Config: compiled-in defaults + external JSON override | new |
| 1 | bcl_dictionary.c | 1 | Tag registry, 94 definitions, SQLite | new |
| 2 | bcl_parser.c | 2 | Parse [@TAG]{content} brackets into node tree. Syntax only — no semantic knowledge. | eyes_26.py (GhostBracket) |
| 2v | bcl_validator.c | 2 | Validate parsed tree against dictionary. Is RUN legal? Is CMD required? Can PARAM repeat? All rules from dictionary. | new |
| 3 | bcl_mem_unit.c | 2 | In-RAM SQLite :memory: orchestration engine. Central dispatch, no direct unit-to-unit calls. All commands/results flow through mu_commands/mu_results/mu_events tables. CLI command registry seeded from here. | MemUnit.py, InRamDb.py |
| 4 | bcl_graph_store.c | 3 | Shared SQLite node/edge operations, multi-backend | new (shared DB layer) |
| 5 | bcl_ingestion_engine.c | 3 | Scan files, hash, AST, imports, source storage | ingestion_engine.py |
| 6 | bcl_graph_builder.c | 3 | Build file/class/method/call graphs | graph_builder.py |
| 7 | bcl_call_path_engine.c | 3 | Trace calls, execution paths, chains | call_path_engine.py |
| 8 | bcl_control_flow_engine.c | 3 | CFG: branches, loops, unreachable, exits | control_flow_engine.py |
| 9 | bcl_data_flow_engine.c | 3 | Trace variables, params, returns, DB/IO | data_flow_engine.py |
| 10 | bcl_static_analyzer.c | 3 | AST parse, symbols, complexity, dead code | static_analyzer.py |
| 11 | bcl_relationship_extractor.c | 3 | Extract edges: reads/writes/gui/api/thread | relationship_extractor.py |
| 12 | bcl_ir_extractor.c | 3 | AST to IR with 3-tier certainty | ir_extractor.py |
| 13 | bcl_report_engine.c | 3 | Reports: dependency, complexity, health | report_engine.py |
| 14 | bcl_execution_tracer.c | 4 | Log runs, update graph, replay | new |
| H | bcl_engine.h | - | Shared header: constants, structs, function declarations | formerly vbast.h |
| C | bcl_engine_cli.c | - | CLI entry point, --describe, --ast, --graph, --check | formerly vbast.c |

---

## SELF-DESCRIBING BINARY

The compiled binary describes itself in BCL. An AI or program can run `--describe` and receive:

```
[@OK]
  [@IDENTITY]{[@NAME]{bcl_engine}[@VERSION]{1.0}[@AUTHOR]{cascade}}
  [@CAPABILITIES]{[@CMD]{dict.init}[@CMD]{dict.lookup}[@CMD]{parse}[@CMD]{validate}[@CMD]{graph.build_all}...}
  [@INTERFACE]{[@INPUT]{[@RUN]{[@CMD]{...}[@PARAM]{...}}}[@OUTPUT]{[@OK]{...} or [@ERR]{...}}}
  [@CONFIG]{[@DB_PATH]{dom_graph_work.db}[@BACKEND]{sqlite}[@MAX_NODES]{256}[@LANGUAGE]{python,c}}
  [@HOW_TO_UPDATE]{[@STEP]{1. Modify .c source}[@STEP]{2. Recompile}[@STEP]{3. Run --describe to verify}}
  [@HELP]{[@CMD]{dict.init — create SQLite table, populate 94 tags}[@CMD]{parse — parse BCL packet into node tree}...}
```

This means:
- No external documentation needed — the binary IS the documentation
- An AI that encounters the binary can ask it what it does
- Help text for every command is embedded in the binary
- Config state is visible via --describe
- Update instructions are embedded

### --describe implementation:
- Each unit registers its commands in a shared command registry
- `--describe` iterates the registry and emits BCL
- Help text for each command is a string literal in the unit's .c file
- The CLI entry point (`bcl_engine_cli.c`) aggregates all units and emits the combined description

---

## MEM UNIT — IN-RAM ORCHESTRATION BUS

The MemUnit (`bcl_mem_unit.c`) is the central nervous system of the engine. It is an
in-RAM SQLite `:memory:` database that **all** communication flows through.

### Why no printf:
- printf goes to stdout — unstructured, unqueryable, lost
- BCL packets in SQLite tables — structured, queryable, replayable, auditable
- An AI or program can query mu_results to see what happened
- No direct unit-to-unit function calls — everything goes through the bus

### In-RAM SQLite tables:

```sql
CREATE TABLE mu_commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    target_unit TEXT NOT NULL,    -- "dictionary", "parser", "graph_store", etc.
    command TEXT NOT NULL,         -- "dict.init", "parse", "graph.build_all"
    bcl_in TEXT NOT NULL,          -- full BCL packet sent
    status TEXT DEFAULT 'pending'  -- pending, dispatched, done, error
);

CREATE TABLE mu_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id INTEGER NOT NULL,   -- FK to mu_commands.id
    ts TEXT NOT NULL,
    bcl_out TEXT NOT NULL,         -- BCL result packet ([@OK] or [@ERR])
    is_ok INTEGER NOT NULL,        -- 1 = success, 0 = error
    elapsed_ms INTEGER             -- execution time
);

CREATE TABLE mu_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    event_type TEXT NOT NULL,      -- CMD_DISPATCHED, CMD_DONE, CMD_ERROR, etc.
    command_id INTEGER,
    detail TEXT
);

CREATE TABLE mu_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE mu_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id INTEGER NOT NULL,   -- FK to mu_commands.id
    ts TEXT NOT NULL,
    error_code INTEGER NOT NULL,   -- unit-specific error code
    error_desc TEXT NOT NULL,      -- human-readable description
    error_unit TEXT NOT NULL,      -- which unit produced the error
    error_input TEXT,              -- the BCL input that caused the error
    error_context TEXT,            -- what was happening (e.g. "parsing tag", "opening db")
    problem TEXT,                  -- what went wrong (e.g. "missing TAG param")
    solution TEXT,                 -- suggested fix (e.g. "provide [@TAG]{name} in PARAM block")
    severity TEXT DEFAULT 'error'  -- error, warn, info
);

CREATE TABLE mu_cli_registry (
    cmd_key TEXT PRIMARY KEY,       -- "dict.init", "parse", "graph.build_all"
    target_unit TEXT NOT NULL,      -- "dictionary", "parser", "graph_builder"
    help_text TEXT NOT NULL,        -- "dict.init — creates 94 tag definitions"
    category TEXT NOT NULL,         -- "dictionary", "parser", "graph", "report", etc.
    requires_param INTEGER DEFAULT 0, -- 1 if command needs params
    param_example TEXT              -- "[@TAG]{GHOST}" example
);
```

### MemUnit API:
```
MemUnit_Init(MemUnit *mu)                           — open :memory: SQLite, create tables
MemUnit_Dispatch(MemUnit *mu, const char *target,
                  const char *command, const char *bcl_in)  — insert command, dispatch, return result
MemUnit_GetResult(MemUnit *mu, int command_id)      — get result BCL for a command
MemUnit_QueryEvents(MemUnit *mu, const char *filter) — query event log
MemUnit_GetState(MemUnit *mu, const char *key)      — get state value
MemUnit_SetState(MemUnit *mu, const char *key,
                  const char *value)                 — set state value
MemUnit_Run(MemUnit *mu, Command cmd, const char *bcl_in)  — VBStyle dispatch
```

### Dispatch flow:
```
1. BCL packet arrives at MemUnit_Dispatch()
2. MemUnit inserts row into mu_commands (status=pending)
3. MemUnit calls target unit's Run() function
4. Unit processes, returns BCL result
5. MemUnit inserts row into mu_results (with bcl_out)
6. MemUnit inserts row into mu_events (CMD_DONE or CMD_ERROR)
7. MemUnit returns result to caller
```

### No-printf rule (enforced):
- NO unit may call printf(), fprintf(), or write to stdout/stderr
- ALL output is BCL packets returned through the MemUnit
- The ONLY exception is bcl_engine_cli.c which may write BCL to stdout for CLI usage
- Even error messages are BCL: `[@ERR]{[@CODE]{N}[@DESC]{message}}`
- Debug logging goes into mu_events table, not stdout

### Ported from Python:
- `Dom_Graph/MemUnit.py` — reasoning state store (nodes, edges, state machine)
- `Dom_Graph/InRamDb.py` — in-RAM SQLite with 11 tables, event-sourcing
- The C version simplifies to 6 tables (commands, results, events, state, errors, cli_registry) for the
  orchestration engine role. The full 11-table event-sourcing schema is a future phase.

### MemUnit internal responsibilities (logical separation, one C file):

MemUnit carries 6 logical responsibilities. In Python, these would be 6 classes.
In C, the `:memory:` SQLite tables ARE the separation — each table is an authority boundary.
One C file, one SQLite connection, 6 tables, 6 clearly documented sections:

| Responsibility | Table | What it owns |
|---|---|---|
| Transport | mu_commands | Incoming command queue, dispatch routing |
| Results | mu_results | Output packets, success/failure status, timing |
| Events | mu_events | Append-only audit trail, CMD_DISPATCHED/CMD_DONE/CMD_ERROR |
| State | mu_state | Key-value runtime state (config overrides, unit init flags) |
| Errors | mu_errors | Error detail with problem/solution/context/input, no-crash guarantee |
| Registry | mu_cli_registry | Command metadata, help text, target unit, param examples |

Why one file, not six:
- All 6 tables share one `:memory:` SQLite connection — splitting into 6 C structs would
  require either 6 separate connections (6x memory, no FK joins) or a shared connection
  passed around (defeats the purpose of separation)
- The SQLite tables are the authority boundary, not the C struct
- Adding 6 init functions, 6 close functions, 6 connection managers for 6 tables in one DB
  adds boilerplate without adding clarity
- If a future phase needs physical separation (e.g. events to a separate durable log),
  that table can be extracted without restructuring the others

---

## LAZY-LOADING ARCHITECTURE — BOOTSTRAP + EXECUTOR

The binary does NOT load all 16 units into RAM at startup. Only the bootstrap loads.
Everything else is lazy — initialized on first call.

### What loads at startup (bootstrap only):
1. `bcl_config.c` — loads defaults + external JSON, holds all SQL seeds
2. `bcl_mem_unit.c` — opens `:memory:` SQLite, creates 6 tables from config SQL seeds
3. `bcl_engine_cli.c` — reads command registry, enters read-dispatch loop

That's it. The other 13 units are compiled into the binary but NOT initialized.
Their code exists but their structs are zeroed, their DB connections are NULL.

### What happens at startup:
```
main()
  → BclConfig_Init()          — load config seed (defaults + external JSON)
  → MemUnit_Init()            — open :memory: SQLite
                               — create 6 tables using SQL seeds from config
  → BclExecutor_Register()    — each unit registers its commands into mu_cli_registry
     ├─ BclDictionary_Register()  — inserts dict.init, dict.lookup, dict.list, etc.
     ├─ BclParser_Register()      — inserts parse, validate
     ├─ BclGraphStore_Register()  — inserts store.get_node, store.insert_edge, etc.
     ├─ BclIngestion_Register()   — inserts ingest.scan, ingest.file, etc.
     ├─ ... (all 13 units register their commands)
     └─ BUT: no unit is initialized yet — only their command metadata is in the registry
  → CLI loop: read input → lookup in registry → BclExecutor_Dispatch() → print BCL result
```

### Registration vs Initialization:
- **Registration** = lightweight — just inserts command names + help text into mu_cli_registry
  - Each unit's `Register()` function is a few lines — inserts rows into the registry table
  - No DB connections, no memory allocation, no heavy work
  - This is why startup is fast — 13 units register in milliseconds

- **Initialization** = heavy — opens DB connections, creates tables, loads data
  - Only happens on first call to that unit
  - The executor checks: is this unit initialized? If not, call `Unit_Init()` first
  - After init, the unit stays alive for subsequent calls

### The Executor (`bcl_executor.c` or inside `bcl_mem_unit.c`):
```
BclExecutor_Dispatch(MemUnit *mu, const char *cmd_key, const char *bcl_in)
  1. Look up cmd_key in mu_cli_registry
  2. Find target_unit (e.g. "dictionary")
  3. Check: is target_unit initialized?
     - NO → call Unit_Init() (lazy load — first time this unit is touched)
     - YES → skip init
  4. Insert command into mu_commands (status=pending)
  5. Call target_unit's Run() function with the BCL packet
  6. Unit processes, returns BCL result
  7. Insert result into mu_results
  8. Insert event into mu_events (CMD_DONE or CMD_ERROR)
  9. Return result to caller
```

### Lazy loading example:
```
$ ./bcl_engine --ast myfile.py

Startup:
  config loads (milliseconds)
  memunit opens :memory: SQLite (milliseconds)
  13 units register commands (milliseconds)
  CLI enters read loop

User types: --ast myfile.py
  CLI looks up "ingest.file" in mu_cli_registry
  Executor sees target_unit = "ingestion_engine"
  Executor checks: is BclIngestionEngine initialized? NO
  → BclIngestionEngine_Init() — opens DB, creates tables, loads tree-sitter grammar
  → NOW ingestion engine is alive in RAM
  → Executor calls BclIngestionEngine_Run() with the BCL packet
  → Result goes to mu_results
  → CLI prints BCL to stdout

User types: --graph
  CLI looks up "graph.build_all" in mu_cli_registry
  Executor sees target_unit = "graph_builder"
  Executor checks: is BclGraphBuilder initialized? NO
  → BclGraphBuilder_Init() — opens DB connection
  → NOW graph builder is alive in RAM
  → Executor calls BclGraphBuilder_Run()
  → Result goes to mu_results → CLI prints

User types: --ast another_file.py
  Executor sees target_unit = "ingestion_engine"
  Already initialized? YES — skip init
  → Direct call to Run() — fast
```

### What this means:
- Startup is fast — only config + memunit + registry load
- Memory is minimal until units are actually needed
- If you only use `--ast`, the graph builder, report engine, etc. never initialize
- Each unit initializes exactly once, on first call, then stays alive
- The registry is the phone book — it knows who can do what, but doesn't wake them up
- The executor is the dispatcher — it wakes units up on demand
- No hardcoded command strings in the CLI — everything comes from the registry
- Adding a new unit = add `Register()` + `Init()` + `Run()` + link the .c file
- `--help` reads from `mu_cli_registry` and formats as BCL
- `--describe` reads from `mu_cli_registry` + `mu_state` and formats as BCL
- If you remove a unit at compile time, its commands disappear from the registry automatically

### Result output flow:
```
Unit processes command
  → Result BCL packet goes into mu_results table
  → Executor returns result to CLI
  → Result Reporter reads from mu_results, formats for terminal
  → CLI writes formatted output to stdout (the ONLY place stdout is used)
  → User or AI reads the output
```

Units never write to stdout. Only the CLI does, and only from mu_results.

---

## RESULT REPORTER — OUTPUT FORMATTING

The Result Reporter is the ONLY thing that writes to the terminal. It reads from
`mu_results` and `mu_errors` in the in-RAM SQLite and formats output for the user.

### What it does:
- Reads `mu_results` table after each command completes
- Formats BCL results into readable terminal output (not raw BCL)
- Handles different output types: success, failure, status, progress, error
- For errors: reads `mu_errors` table for problem/solution details
- Never crashes — if something goes wrong, it writes an error row to mu_errors
  and the reporter shows it gracefully

### Output types:
| Type | When | Format |
|---|---|---|
| Success | Command completed, is_ok=1 | Green text, result summary |
| Error | Command failed, is_ok=0 | Red text, error code + description + problem + solution |
| Status | Progress update | Yellow text, what's happening now |
| Warning | Non-fatal issue | Yellow text, warning description |
| Info | Informational | Normal text, informational message |

### Error output format (what the user sees):
```
[ERROR] Command: dict.lookup
  Code: 7 — missing_tag_param
  Problem: The TAG parameter was not provided in the BCL input
  Input: [@RUN]{[@CMD]{dict.lookup}[@PARAM]{}}
  Context: Extracting TAG from PARAM block
  Solution: Provide [@TAG]{tag_name} inside the [@PARAM] block
  Unit: bcl_dictionary
```

### Success output format (what the user sees):
```
[OK] Command: dict.init
  Result: 94 tag definitions loaded into bcl_tag_dictionary
  Elapsed: 3ms
```

### No-crash guarantee:
- No runtime error ever terminates the binary
- Every error is captured in `mu_errors` with: code, description, input, context, problem, solution
- The reporter reads from `mu_errors` and displays it gracefully
- The binary stays alive — user can fix their input and try again
- Even if a unit segfaults (shouldn't happen), the executor catches it and logs to mu_errors

### Error capture flow:
```
Unit encounters a problem
  → Unit returns [@ERR]{[@CODE]{N}[@DESC]{message}}
  → Executor inserts row into mu_errors with:
     - error_code = N
     - error_desc = message
     - error_unit = which unit
     - error_input = the BCL packet that was sent
     - error_context = what the unit was doing
     - problem = what went wrong
     - solution = suggested fix
  → Executor inserts row into mu_results (is_ok=0)
  → Executor inserts row into mu_events (CMD_ERROR)
  → Result Reporter reads mu_errors, formats error for terminal
  → User sees the error, can try again — binary stays alive
```

### Where problem/solution text comes from:
- Each unit defines its own error codes and descriptions
- The problem/solution text is stored in the unit's error table (compiled in)
- At registration time, units can register their error codes into mu_state
- The executor looks up the error code to find the problem/solution text
- This means error messages are data-driven, not hardcoded in printf statements

---

## COMPILATION MODES

Same source code, three compile targets:

| Output | Command | Usage |
|---|---|---|
| Binary (CLI) | `cc -o bcl_engine *.c -lsqlite3 -lssl` | `./bcl_engine --ast file.py` |
| Shared library | `cc -shared -o libbcl_engine.so *.c -lsqlite3 -lssl` | Python: `ctypes.CDLL("./libbcl_engine.so")` |
| Static library | `cc -c *.c; ar rcs libbcl_engine.a *.o` | Link into other C programs |

Build artifacts go to:
- `bin/` — final binary
- `obj/` — intermediate .o files (not in source folder)

---

## INTERNAL CONFIG SYSTEM — THE SEED

`bcl_config.c` is the single source of ALL hardcoded values in the entire engine.
No other file contains hardcoded paths, sizes, SQL statements, or defaults.
Everything lives in config — SQL schemas, CLI defaults, buffer sizes, paths, constants.

### What config holds:
- **SQL seed statements** — all CREATE TABLE statements for every unit's schema
- **CLI defaults** — command names, help text templates, prompt format
- **Path defaults** — db_path, log_path, config file path
- **Buffer sizes** — MAX_PATH, MAX_BCL, MAX_RESULT_BUF, etc.
- **Backend type** — sqlite (file), sqlite (:memory:), mysql (future)
- **Language mode** — auto, python, c
- **Log level** — error, warn, info, debug

### Config priority (highest to lowest):
1. External file: `bcl_config.json` (runtime override)
2. Compiled-in defaults: `#define` values in `bcl_config.c` (the seed)
3. Fallback: in-memory SQLite (`:memory:`) if no DB path configured

### bcl_config.c API:
```
BclConfig_Init(BclConfig *cfg)              — load defaults + external file
BclConfig_Get(BclConfig *cfg, const char *key)  — get string value
BclConfig_GetInt(BclConfig *cfg, const char *key) — get int value
BclConfig_Set(BclConfig *cfg, const char *key, const char *val) — override at runtime
BclConfig_Save(BclConfig *cfg, const char *path) — write current config to JSON
BclConfig_GetSql(BclConfig *cfg, const char *key) — get SQL seed statement by name
```

### bcl_config.json format:
```json
{
  "db_path": "dom_graph_work.db",
  "backend": "sqlite",
  "max_nodes": 256,
  "max_edges": 8192,
  "language_mode": "auto",
  "log_level": "error",
  "sql_seeds": {
    "bcl_tag_dictionary": "CREATE TABLE IF NOT EXISTS bcl_tag_dictionary (...)",
    "source_files": "CREATE TABLE IF NOT EXISTS source_files (...)",
    "mu_commands": "CREATE TABLE IF NOT EXISTS mu_commands (...)",
    "mu_results": "CREATE TABLE IF NOT EXISTS mu_results (...)",
    "mu_events": "CREATE TABLE IF NOT EXISTS mu_events (...)",
    "mu_state": "CREATE TABLE IF NOT EXISTS mu_state (...)",
    "mu_errors": "CREATE TABLE IF NOT EXISTS mu_errors (...)",
    "mu_cli_registry": "CREATE TABLE IF NOT EXISTS mu_cli_registry (...)"
  }
}
```

### Why SQL seeds in config:
- Change a table schema = change config, not change 5 different .c files
- Add a new column = update the SQL seed in config, recompile
- Units call `BclConfig_GetSql(cfg, "bcl_tag_dictionary")` to get their CREATE statement
- No unit hardcodes its own SQL — it comes from the config seed

### Multi-backend support:
- `sqlite` (default) — file-based or `:memory:`
- `mysql` (future) — remote DB
- All units call `bcl_graph_store` which abstracts the backend
- Units never open DB connections directly — always through the store

---

## INTERNAL DATABASE

The binary can operate with:
- **Persistent mode**: opens `dom_graph_work.db` on disk (default)
- **In-memory mode**: uses SQLite `:memory:` when no DB path is configured
- **Source storage**: the `source_files` table stores original source code text

### source_files schema:
```sql
CREATE TABLE source_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    content TEXT NOT NULL,
    line_count INTEGER,
    language TEXT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

This means the binary carries the original source code inside its database. You can:
- Query source by file path
- Verify content hash integrity
- Re-extract source from DB if files are lost
- Track which language each file is

---

## MULTI-LANGUAGE AST SUPPORT

The AST walker (in `bcl_engine_cli.c` / `bcl_ingestion_engine.c`) uses tree-sitter with
multiple grammars:

| Language | Grammar file | File extensions |
|---|---|---|
| Python | tree-sitter-python.h | .py |
| C | tree-sitter-c.h | .c, .h |

### Language detection:
- `detect_language(file_path)` returns `LANG_PYTHON`, `LANG_C`, or `LANG_UNKNOWN`
- Based on file extension
- Unknown extensions are rejected with `[@ERR]{[@CODE]{N}[@DESC]{unsupported_language}}`

### Per-language AST traversal:
- `walk_python_ast()` — looks for `class_definition`, `function_definition`, `decorator`
- `walk_c_ast()` — looks for `function_definition`, `struct_specifier`, `preproc_include`
- Both fill the same `ParseResult` struct — downstream units are language-agnostic

### VBStyle checking:
- Python: full 11-check VBStyle compliance
- C: VBStyle C rules (no decorators, no self, different checks)
- Language-specific checks are dispatched based on `ParseResult.language`

---

## ERROR HANDLING

### Error format:
```
[@ERR]{[@CODE]{int}[@DESC]{human_readable_message}}
```

### Error codes are per-unit, not global:
- Each unit defines its own error codes starting from 1
- Error codes are documented in the unit's BCL header comments
- The `--describe` output includes error codes for each command

### Error behavior:
- All functions check return values and return [@ERR] immediately — no silent failures
- Database errors include the SQLite error code in the description
- Parse errors include the byte position in the description
- No printf() — errors are returned as BCL strings, not printed
- The execution tracer logs all errors for audit

### Common error codes (convention):
| Code | Meaning |
|---|---|
| 1 | unknown_command |
| 2 | db_open_failed |
| 3 | parse_error |
| 4 | missing_param |
| 5 | not_found |
| 6 | already_exists |
| 7 | invalid_input |
| 8 | not_initialized |
| 9+ | unit-specific |

---

## HELP SYSTEM

### Per-command help:
Each command has a help string embedded in its .c file:
```c
static const char *HELP_DICT_INIT = "dict.init — creates bcl_tag_dictionary table, populates 94 tag definitions. No params required. Returns [@OK]{[@COUNT]{94}}.";
```

### --help command:
```
./bcl_engine --help
[@OK]
  [@HELP]
    [@CMD]{dict.init — creates bcl_tag_dictionary table, populates 94 tags}
    [@CMD]{dict.lookup — look up single tag by name. Param: [@TAG]{name}}
    [@CMD]{parse — parse BCL packet. Param: [@BCL]{packet_text}}
    ...
```

### --describe vs --help:
- `--describe` — full identity + capabilities + config + interface + update instructions
- `--help` — just command list with descriptions
- Both output BCL, not plain text

---

## HOW TO ACCESS SOURCE CODE

The source code is accessible in three ways:

1. **From the source files** — the `.c` files in `core/Dom_Bcl_C_ver/`
2. **From the internal DB** — `source_files` table stores original source with hash
3. **From the binary** — `--describe` emits the BCL identity headers which contain file paths

### Source verification:
- `bcl_ingestion_engine.c` computes SHA-256 hash of each source file
- Hash is stored in `source_files.content_hash`
- On re-ingest, hash comparison detects changes
- If source file is lost, it can be recovered from `source_files.content`

---

## HOW TO UPDATE THE BINARY

1. Modify the `.c` source file(s)
2. Recompile: `cc -o bin/bcl_engine *.c -lsqlite3 -lssl`
3. Run `./bcl_engine --describe` to verify the update
4. The `--describe` output reflects new commands, new config, new version

### Future: online update (Phase 3, not implemented):
- Binary checks a remote URL for newer version
- Downloads new `.c` source if available
- Recompiles itself (requires compiler on system)
- Not a priority — noted for future consideration

---

## C TEMPLATE (all 16 files use this shell)

```
// [@GHOST]{file_path="FILE.c" date="DATE" author="AUTHOR" context="CONTEXT"}
// [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
// [@FILEID]{id="FILE.c" domain="DOMAIN" authority="AUTHORITY"}
// [@SUMMARY]{summary="SUMMARY"}
// [@CLASS]{class="AUTHORITY" domain="DOMAIN" authority="single"}
// [@METHOD]{method="Run" type="dispatch"}
// [@METHOD]{method="read_state" type="command"}
// [@METHOD]{method="set_config" type="command"}

#include <sqlite3.h>, <openssl/sha.h>, <string.h>, <stdlib.h>

/* ===== DIM BLOCK (declarations) ===== */

#define MAX_PATH 4096, MAX_BCL 65536;
typedef enum { CMD_READ_STATE = 0, CMD_SET_CONFIG, CMD_COUNT } Command;
typedef struct { char db_path[MAX_PATH]; sqlite3 *conn; } Unit;
typedef const char *(*CmdFn)(Unit *, const char *bcl_in);

/* ===== INIT BLOCK (constructors + helpers) ===== */

static const char *OK(const char *bcl_result) { return bcl_result; }
static const char *ERR(int code, const char *desc) { return NULL; }

/* ===== FORWARD BLOCK (prototypes) ===== */

static const char *fn_read_state(Unit *u, const char *bcl_in);
static const char *fn_set_config(Unit *u, const char *bcl_in);

/* ===== DISPATCH BLOCK (jump table + entry) ===== */

static const CmdFn DISPATCH[CMD_COUNT] = { fn_read_state, fn_set_config };

void Unit_Init(Unit *u, const char *db_path) {
    memset(u, 0, sizeof(*u));
    strncpy(u->db_path, db_path, MAX_PATH - 1);
}

/* accepts BCL, returns BCL */
const char *Unit_Run(Unit *u, Command cmd, const char *bcl_in) {
    return (cmd < 0 || cmd >= CMD_COUNT)
        ? ERR(1, "unknown_command")
        : DISPATCH[cmd](u, bcl_in);
}

/* ===== GUTS BLOCK (implementation) ===== */

static const char *fn_read_state(Unit *u, const char *bcl_in) {
    /* in:  [@RUN]{[@CMD]{read_state}} */
    /* out: [@OK]{[@STATE]{[@DB_PATH]{...}}} */
    return OK("[@OK]{[@STATE]{}}");
}

static const char *fn_set_config(Unit *u, const char *bcl_in) {
    /* in:  [@RUN]{[@CMD]{set_config}[@PARAM]{[@DB_PATH]{/new/path}}} */
    /* out: [@OK]{[@CONFIG]{[@DB_PATH]{/new/path}}} */
    return OK("[@OK]{[@CONFIG]{}}");
}
```

---

## BCL INTERFACE CONTRACT

Every unit accepts BCL, returns BCL.

### Input format:
```
[@BCL_VER]{1.0}
[@RUN]{[@CMD]{unit.command}[@PARAM]{[@KEY]{value}[@KEY2]{value2}}}
```

### Success format:
```
[@OK]{[@RESULT]{[@COUNT]{161}[@FILES]{...}}}
```

### Error format:
```
[@ERR]{[@CODE]{3}[@DESC]{db query failed}}
```

---

## BCL DICTIONARY SCHEMA (SQLite) — RICH GRAMMAR MODEL

The dictionary is not just a tag lookup. It is the grammar of BCL.
The parser, validator, help system, and command registry all read from it.

### BCL Semantic Domains (Namespaces)

BCL is not one language — it is one syntax with 8 semantic domains.
Each domain uses the same `[@TAG]{...}` bracket syntax but serves a distinct purpose:

| Domain | Namespace | Purpose | Example Tags |
|---|---|---|---|
| Bracket Command Language | `cmd` | Runtime dispatch, execution | RUN, CMD, PARAM, DISPATCH |
| Bracket Communication Language | `comm` | Inter-unit and AI communication | OK, ERR, RESULT, STATE |
| Bracket Configuration Language | `cfg` | Configuration and defaults | CONFIG, DB_PATH, BACKEND |
| Bracket Constraint Language | `cstr` | Validation and rules | VALID, REQUIRED, REPEATABLE |
| Bracket Control Language | `ctrl` | Orchestration, dispatch control | EXECUTE, QUERY, SCAN |
| Bracket Description Language | `desc` | Self-describing binaries, metadata | IDENTITY, CAPABILITIES, HELP |
| Bracket Knowledge Language | `know` | Facts, problems, solutions, decisions | PROBLEM, SOLUTION, LESSON, DECISION |
| Bracket Graph Language | `graph` | Nodes, edges, relationships, IR | NODES, EDGES, IRNODE, BCL_STAMP |

The dictionary models these as namespaces. Each tag belongs to exactly one namespace.

### Dictionary schema (rich):

```sql
CREATE TABLE bcl_tag_dictionary (
    bcl_id TEXT PRIMARY KEY,         -- "BCL0001" — stable ID, never changes
    symbol TEXT NOT NULL,            -- "RUN" — display name, can be aliased
    namespace TEXT NOT NULL,         -- "cmd", "comm", "cfg", "cstr", "ctrl", "desc", "know", "graph"
    category TEXT NOT NULL,          -- sub-category within namespace (e.g. "IDENTITY" in desc)
    valid_in TEXT NOT NULL,          -- header, body, param, result, any
    parent_tag TEXT,                 -- which tag can contain this (e.g. PARAM's parent is RUN)
    children_allowed TEXT,           -- comma-separated list of child tags, or "*" for any
    required INTEGER DEFAULT 0,      -- 1 if this tag must appear when parent is used
    repeatable INTEGER DEFAULT 0,    -- 1 if this tag can appear multiple times
    max_count INTEGER DEFAULT 0,     -- 0 = unlimited, N = max occurrences
    datatype TEXT,                   -- "string", "int", "container", "tuple", "bool"
    validator TEXT,                  -- name of validator function (e.g. "RunPacket", "TagList")
    aliases TEXT,                    -- comma-separated alternate names (e.g. "EXECUTE" for RUN)
    status TEXT DEFAULT 'active',    -- active, deprecated, removed
    version TEXT DEFAULT '1.0',      -- introduced in BCL version
    deprecated_in TEXT,              -- version where deprecated (NULL if active)
    example TEXT,                    -- example usage: "[@RUN]{[@CMD]{dict.init}}"
    documentation TEXT,              -- short description of what this tag does
    authority TEXT DEFAULT 'core'    -- who defined this tag (core, engine, user)
);

CREATE TABLE bcl_tag_aliases (
    alias TEXT PRIMARY KEY,          -- "EXECUTE" — the alias
    bcl_id TEXT NOT NULL,            -- "BCL0001" — points to canonical tag
    FOREIGN KEY (bcl_id) REFERENCES bcl_tag_dictionary(bcl_id)
);
```

### Why BCL IDs:
- Names can change (GHOST → IDENTITY_GHOST) but BCL0001 stays the same
- Aliases map to the same ID (RUN and EXECUTE both → BCL0001)
- Versioning: a tag can be deprecated in 2.0 but the ID persists
- External systems can reference tags by ID without knowing the display name

### Why parent/children/required/repeatable:
- The parser reads the dictionary to know: can PARAM appear inside RUN? Yes (parent=RUN)
- Can PARAM appear twice? No (repeatable=0, max_count=1)
- Is CMD required inside RUN? Yes (required=1)
- The parser doesn't accumulate rules in code — it asks the dictionary

### Example dictionary entries:
```
bcl_id=BCL0001  symbol=RUN     namespace=cmd  valid_in=body    parent=ROOT    children=CMD,PARAM  required=0  repeatable=1  datatype=container
bcl_id=BCL0002  symbol=CMD     namespace=cmd  valid_in=body    parent=RUN     children=*          required=1  repeatable=0  datatype=string
bcl_id=BCL0003  symbol=PARAM   namespace=cmd  valid_in=body    parent=RUN     children=*          required=0  repeatable=1  datatype=container
bcl_id=BCL0010  symbol=GHOST   namespace=desc valid_in=header  parent=ROOT    children=*          required=1  repeatable=0  datatype=container
bcl_id=BCL0020  symbol=OK      namespace=comm valid_in=result  parent=ROOT    children=*          required=0  repeatable=0  datatype=container
bcl_id=BCL0021  symbol=ERR     namespace=comm valid_in=result  parent=ROOT    children=CODE,DESC  required=0  repeatable=0  datatype=container
```

### Mapping old categories to namespaces:
| Old Category | New Namespace |
|---|---|
| IDENTITY | desc |
| COMMAND | cmd |
| RESULT | comm |
| CODE_STRUCTURE | graph |
| IR | graph |
| GUI | desc |
| CHAT | know |
| KNOWLEDGE | know |
| META | desc |
| PARAM | cfg |

---

## PARSER vs VALIDATOR — SEPARATION OF CONCERNS

The parser and validator are separate C files with separate responsibilities.

### Parser (`bcl_parser.c`) — syntax only:
- Knows ONLY bracket syntax: `[@TAG]{content}`, nested `{...}`, tuples `("a";"b";92)`
- Does NOT know what RUN, CMD, RESULT, GRAPH, METHOD, GUI mean
- Does NOT check if a tag is valid, required, or allowed in context
- Builds an in-memory node tree from raw text
- Returns `ParseResult` (tree or syntax error)
- The parser is tiny and very stable — it never changes when tags are added/removed

### Validator (`bcl_validator.c`) — semantics from dictionary:
- Takes a parsed node tree and checks it against the dictionary
- Asks dictionary: is RUN a valid tag? Is CMD required inside RUN? Can PARAM repeat?
- Checks parent/child relationships from dictionary schema
- Checks required, repeatable, max_count rules
- Returns valid/invalid with specific error messages
- The validator changes when dictionary rules change — but the parser doesn't

### Flow:
```
Raw BCL text
  → bcl_parser.c → ParseResult (node tree or syntax error)
  → bcl_validator.c → ValidatedTree (or semantic error with problem/solution)
  → Runtime (MemUnit dispatches to target unit)
```

### Why separate:
- Parser handles syntax errors (malformed brackets, missing `}`)
- Validator handles semantic errors (CMD missing inside RUN, PARAM appears twice)
- Different error messages, different fix suggestions
- Parser stays stable when tags change; validator adapts
- If we ever replace the parser (e.g. generated parser in Phase 3), the validator stays the same

---

## DICTIONARY MATURITY — 3 PHASES

The dictionary evolves through 3 maturity levels. The schema is designed to support
all 3 phases without redesign.

### Phase 1 — Dictionary as validation (current):
```
Parser → Dictionary → Is RUN legal? → Yes → Continue
```
- Dictionary is a lookup table: tag exists? what namespace? what valid_in?
- Validator checks: is this tag known? is it valid in this context?
- Simple, practical, works today

### Phase 2 — Dictionary as semantic rules (next):
```
Parser → Validator (reads dictionary for rules)
  → RUN: parent=ROOT, children=CMD,PARAM, required=CMD, repeatable=true
  → CMD is mandatory? Yes → check CMD exists in tree
  → PARAM is optional? Yes → allow zero or more
  → RESULT not in children_allowed? → reject
```
- Dictionary drives semantic validation via parent/children/required/repeatable
- Validator reads rules from dictionary, not hardcoded
- Parser stays the same — still just bracket syntax
- No parser generator needed — just richer validation

### Phase 3 — Dictionary generates parser (future):
```
Grammar (dictionary) → Generator → Parser code
```
- Dictionary schema is rich enough to generate a parser automatically
- This is essentially building a parser generator (compiler-compiler)
- Postponed until the BCL language has stabilized
- Not needed for the C engine to function — handwritten parser works fine

### Schema design principle:
The dictionary schema (bcl_id, symbol, namespace, parent_tag, children_allowed,
required, repeatable, max_count, datatype, validator) is designed to support
all 3 phases without redesign. Phase 1 uses tag/namespace/valid_in. Phase 2 adds
parent/children/required/repeatable. Phase 3 adds datatype/validator for generation.

---

## COMMAND NAMESPACE (per unit)

```
ingest.scan          — scan directory for .py files
ingest.file          — ingest single file
ingest.update        — update changed files
ingest.dup           — detect duplicates

graph.build_all      — build all graph types
graph.call_graph     — build call graph
graph.dead_code      — detect dead code
graph.cycles         — detect cycles
graph.hotspots       — detect hotspots

call.incoming        — trace incoming calls
call.outgoing        — trace outgoing calls
call.exec_paths      — execution paths
call.chain           — call chain
call.recursive       — find recursion

cfg.branches         — analyze branches
cfg.loops            — analyze loops
cfg.unreachable      — find unreachable code
cfg.infinite         — find infinite loops
cfg.exit_paths       — exit paths

data.variable        — trace variable
data.parameter       — trace parameter
data.return          — trace return value
data.db_flow         — database query flow
data.file_flow       — file I/O flow

static.analyze       — AST parse + symbols
static.complexity    — complexity score
static.dead_code     — find dead code
static.duplicates    — find duplicates
static.symbols       — build symbol table

rel.file             — extract file edges
rel.class            — extract class edges
rel.method           — extract method edges
rel.variable         — extract variable edges
rel.database         — extract database edges
rel.gui              — extract GUI edges
rel.api              — extract API edges
rel.thread           — extract thread edges

ir.extract           — AST to IR
ir.method            — method IR records
ir.certainty         — certainty tier edges

report.full          — full report
report.dependency    — dependency report
report.complexity    — complexity report
report.health        — health score
report.bcl_coverage  — BCL coverage

store.get_node       — get node by ID
store.get_edges      — get edges for node
store.insert_node    — insert node
store.insert_edge    — insert edge
store.query          — raw query

trace.start          — start tracing
trace.stop           — stop tracing
trace.replay         — replay execution
trace.log            — get execution log
trace.impact         — impact analysis
```

---

## BUILD ORDER

### Phase 0 — Foundation (files 0-3, header)
0. bcl_config.c — config defaults + external JSON reader
1. bcl_dictionary.c — create SQLite table, populate 94 tags
2. bcl_parser.c — parse BCL bracket syntax into node tree (syntax only)
2v. bcl_validator.c — validate parsed tree against dictionary (semantic rules)
3. bcl_mem_unit.c — in-RAM SQLite :memory: orchestration bus (central dispatch)
H. bcl_engine.h — shared header (renamed from vbast.h)

### Phase 1 — Core engines (files 4-5)
4. bcl_graph_store.c — shared SQLite operations (nodes, edges, source files)
5. bcl_ingestion_engine.c — file scanning, hashing, AST, source storage

### Phase 2 — Graph builders (files 6-11)
6. bcl_graph_builder.c — build graphs, detect anomalies
7. bcl_relationship_extractor.c — extract all edge types
8. bcl_static_analyzer.c — symbols, complexity, dead code
9. bcl_control_flow_engine.c — CFG
10. bcl_call_path_engine.c — call graph traversal
11. bcl_data_flow_engine.c — data flow tracing

### Phase 3 — Advanced (files 12-13)
12. bcl_ir_extractor.c — IR with certainty tiers
13. bcl_report_engine.c — reports and health scores

### Phase 4 — Execution (file 14)
14. bcl_execution_tracer.c — runtime logging, replay, impact

### Phase 5 — CLI + Self-describing (file C)
C. bcl_engine_cli.c — CLI entry point, --describe, --help, --ast, --graph, --check

---

## DEPENDENCIES

- sqlite3 (SQLite C library) — graph storage, tag dictionary, source storage
- openssl (SHA-256 hashing) — file content hashing, integrity verification
- tree-sitter (parser library) — multi-language AST parsing
  - tree-sitter-python — Python grammar
  - tree-sitter-c — C grammar
- No Python runtime needed — pure C, including AST parsing

---

## SHARED RESOURCES

All units share:
- bcl_config.c — config defaults + external override
- bcl_dictionary.c — tag definitions
- bcl_parser.c — parse bracket syntax (syntax only, no tag knowledge)
- bcl_validator.c — validate parsed tree against dictionary (semantic rules)
- bcl_mem_unit.c — in-RAM SQLite orchestration bus (central dispatch, no direct unit-to-unit)
- bcl_graph_store.c — SQLite operations (abstracts backend)
- bcl_engine.h — shared header (constants, structs, function declarations)
- dom_graph_work.db — the persistent database (nodes, edges, files, classes, methods, source)
- :memory: SQLite — the in-RAM working state (commands, results, events, trace)

### Shared header (bcl_engine.h):
- Constants: buffer sizes, max counts, default paths
- Structs: ParseResult, ClassInfo, MethodInfo, EdgeInfo, ImportInfo, Violation
- Language enum: LANG_PYTHON, LANG_C, LANG_UNKNOWN
- Function declarations for all units
- No function implementations — just declarations

---

## RELATIONSHIP TO EXISTING VBAST FILES

The existing VBAST files (formerly in `Cascade_toolStack/vbast/`) have been renamed and
merged into this engine:

| Old name | New name | Status |
|---|---|---|
| vbast.h | bcl_engine.h | Renamed, updated with language enum |
| vbast.c | bcl_engine_cli.c | Renamed, --describe added |
| ast_walker.c | (merged into bcl_ingestion_engine.c) | Multi-language traversal |
| bcl_stamper.c | bcl_stamper.c | Renamed, BCL headers |
| graph_builder.c | bcl_graph_builder.c | Renamed, BCL headers |
| vbstyle_check.c | (merged into bcl_static_analyzer.c) | Renamed, BCL headers |
| mysql_store.c | (merged into bcl_graph_store.c) | Multi-backend |

All files now carry BCL headers (`[@GHOST]`, `[@VBSTYLE]`, `[@FILEID]`, etc.) instead of
plain C comments. No file exists without BCL identity.

---

## VBSTYLE C RULES

1. One struct per file (the Unit)
2. Run() dispatch via function pointer table
3. BCL in, BCL out (const char *)
4. One shared header only — bcl_engine.h. No other .h files. Each .c is otherwise self-contained
5. BCL headers at top of every file
6. DIM BLOCK → INIT BLOCK → FORWARD BLOCK → DISPATCH BLOCK → GUTS BLOCK
7. No printf() — return BCL error packets instead
8. No global state — all state in Unit struct (except DISPATCH table)
9. PascalCase functions, UPPERCASE constants
10. Spaces only, no tabs
11. NO trailing whitespace at end of lines
12. NO hardcoded values — all paths, sizes, constants in #define block or Config
13. Do exactly as told — do not interpret, do not add, do not skip, do not reorder
14. If unsure, ask — do not guess, do not assume; asking is better than guessing
15. AI models do what they are TOLD in SEQUENCE — they do NOT do as they think;
    autonomy is FORBIDDEN when a sequence is specified
16. All code must check return values and return [@ERR] immediately — no silent failures
17. Every dispatch key must map to exactly ONE function — no ambiguous commands
18. No raw tag strings — all BCL tags must come from bcl_dictionary constants

---

## C-SPECIFIC CONFIG

The Python VBStyle rules use self.state dictionary and forbid self._ variables.
In C, the equivalent rules are:

- All state lives in the Unit struct — no loose global variables
- No hidden state — everything visible in the struct definition
- Config values come from #define constants or the db_path parameter
- No magic numbers in function bodies — use #define constants
- The DIM BLOCK is the equivalent of Python self.state config dict
- The Unit struct is the equivalent of Python self.state

### Python vs C mapping:
| Python VBStyle | C VBStyle |
|---|---|
| self.state = {} | Unit struct |
| self._x (FORBIDDEN) | global variables (FORBIDDEN) |
| self.state["key"] | u->field |
| def __init__(self, mem, db, param) | void Unit_Init(Unit *u, const char *db_path) |
| def Run(self, command, params) | const char *Unit_Run(Unit *u, Command cmd, const char *bcl) |
| (1, data, None) | OK("[@OK]{...}") |
| (0, None, (code, desc, 0)) | ERR(code, "desc") |
| print() (FORBIDDEN) | printf() (FORBIDDEN) |
| @property (FORBIDDEN) | N/A in C |
| @staticmethod (FORBIDDEN) | N/A in C |
| tabs (FORBIDDEN) | tabs (FORBIDDEN) |
| trailing whitespace (FORBIDDEN) | trailing whitespace (FORBIDDEN) |

---

## VERIFICATION CHECKLIST (per file)

1. Compiles with: cc -c FILE.c -lsqlite3 -lssl
2. No raw tag strings — all tags from bcl_dictionary
3. Run() dispatch works for all commands
4. Returns [@OK] on success, [@ERR] on failure
5. BCL headers present and complete ([@GHOST], [@VBSTYLE], [@FILEID], [@SUMMARY], [@CLASS], [@METHOD])
6. DIM/INIT/FORWARD/DISPATCH/GUTS blocks in order
7. No printf() calls
8. No global variables (except DISPATCH table)
9. No trailing whitespace
10. No hardcoded values — all constants in #define or from bcl_config
11. No tabs — spaces only
12. Every dispatch key maps to exactly one function
13. File name uses bcl_ prefix, lowercase, underscore-separated
14. Help string exists for every command
15. Error codes documented in BCL header comments
16. No #include "vbast.h" — must use #include "bcl_engine.h"
17. DB access goes through bcl_graph_store, not direct sqlite3_open
18. Dictionary tags use BCL IDs (BCL0001) internally, symbols (RUN) for display
19. Tags reference parent/children from dictionary, not hardcoded in parser
20. AI-to-AI task packets use capability-based routing, not hardcoded model names
21. BCL packets work identically for C units and AI models (same mu_ tables)
22. Every unit has Run() dispatch, read_state(), set_config() — no exceptions

---

## BCL AS A LANGUAGE — FORMAL SPECIFICATION REFERENCE

BCL (Bracket Command Language) is a language, not just a packet format.
The C engine is one implementation of that language.

### Language hierarchy:
```
BCL Language Specification (BCL_SPEC.md)
  ↓ defines
BCL Dictionary (grammar, tags, namespaces, rules)
  ↓ generates
Parser (reads dictionary to validate packets)
  ↓ feeds
Runtime (MemUnit + Executor + Units)
  ↓ powers
Applications (CLI, shared library, static library)
```

### BCL is larger than this engine:

The same bracket syntax serves 8 orthogonal domains (see Semantic Domains above).
BCL is not just "commands" — it is a multi-purpose bracket language where:
- Command domain handles runtime dispatch
- Communication domain handles inter-unit results
- Configuration domain handles defaults and overrides
- Constraint domain handles validation rules
- Control domain handles orchestration
- Description domain handles self-describing metadata
- Knowledge domain handles facts/problems/solutions
- Graph domain handles nodes/edges/IR

### Future: BCL_SPEC.md

A separate document (`BCL_SPEC.md`) will define the language formally:
- **Lexical rules** — bracket syntax, escape sequences, string literals
- **Grammar** — container nesting, tuple format, weight syntax
- **Packet rules** — valid packet structure, root tags, nesting depth
- **Dictionary** — tag schema, namespaces, IDs, versioning
- **Execution** — dispatch model, command lifecycle, lazy loading
- **Errors** — error codes, problem/solution format, no-crash guarantee
- **Namespaces** — the 8 semantic domains and their rules
- **Versioning** — how tags evolve, deprecation, aliases
- **Validation** — how the dictionary validates packets
- **Serialization** — how BCL packets are encoded/decoded
- **AI-to-AI protocol** — intent packets, capability routing, multi-model dispatch

Once BCL_SPEC.md exists, the C engine becomes one implementation of the language.
Other implementations (Python, Rust, etc.) can be built from the same spec.
The dictionary can generate parsers, validators, documentation, and command registries automatically.

### Current status:
- BCL language is defined implicitly inside PLAN_SPEC.md and bcl_dictionary.c
- The dictionary schema in this spec is the canonical grammar definition
- BCL_SPEC.md extraction is a future milestone (after engine compiles and runs)
- The engine does NOT wait for BCL_SPEC.md — it implements the grammar directly

### BCL multi-layer evolution:

BCL has evolved from code annotation into multiple layers built on the same bracket grammar:

| Layer | What it does | Example |
|---|---|---|
| Serialization format | Encode/decode structured data | `[@TAG]{("key";"value";92)}` |
| Messaging protocol | AI-to-AI and unit-to-unit communication | `[@TASK]{[@TYPE]{implement}[@TARGET]{file.c}}` |
| Schema language | Define valid structure | `[@DICT]{[@TAG]{RUN}[@CHILDREN]{CMD,PARAM}[@REQUIRED]{1}}` |
| Command language | Execute actions | `[@RUN]{[@CMD]{dict.init}}` |
| Metadata language | Describe identity/capabilities | `[@DESCRIBE]{[@IDENTITY]{...}[@CAPABILITIES]{...}}` |
| Orchestration protocol | Route work to workers | `[@DISPATCH]{[@TARGET]{...}[@PACKET]{...}}` |

These are not separate inventions — they are different layers built on the same bracket grammar.
If the dictionary becomes authoritative, these layers evolve together without drifting.

---

## BCL DIALECT TAXONOMY — NAMESPACE FAMILY

BCL is a family of dialects sharing one bracket grammar. The parser never changes.
The dictionary determines which dialect a packet belongs to.

Principle: `One parser + Many dictionaries = Many dialects`

### 9 Dialect families (50+ dialects):

| Family | Namespaces | Root tags | Purpose |
|---|---|---|---|
| Execution and Control | cmd, ctrl | RUN, DISPATCH, EXEC, BUILD, CREATE, COMPOSE, COORD, COLLAB | Execute, orchestrate, coordinate |
| Communication and Chat | comm | MSG, CHAT, ACK, REPORT, DONE | AI-to-AI, human-to-AI, conversations |
| Configuration and Constraints | cfg, cstr | CONFIG, RULE, CONTRACT, CHECK, CERTIFY | Settings, rules, compliance |
| Context and Knowledge | know, ctrl | CONTEXT, KNOW, MEM, CAUSE, TIME, CLASS | Facts, memory, causality, chronology |
| Description and Discovery | desc | DESCRIBE, DISCOVER, DICT, DEFINE, DOC, CAN, CATALOG | Metadata, capabilities, registries |
| Correction and Diagnostics | cstr, desc | FIX, DIAG, DEP, DECISION, DESIGN, DEV | Fixes, diagnosis, decisions |
| Data and Graph | graph | GRAPH, COLLECT, CONVERT, CANON, COMPUTE, DIFF, PACK | Nodes, edges, transforms, compression |
| Query and Search | graph, know | QUERY, SEARCH, FILTER, ROUTE, SCHEDULE, WORKFLOW, PIPELINE, EVENT, STATE | Query, search, route, schedule, pipeline |
| Verification and Quality | cstr, desc | REVIEW, VALIDATE, VERIFY, TEST, AUDIT, TRACE, LOG, METRICS, STATS | Review, test, audit, trace, metrics |

### Mapping to current 8 namespaces:

The current 8 namespaces (cmd, comm, cfg, cstr, ctrl, desc, know, graph) cover all 9 families.
New dialects are added by registering new root tags in the dictionary — no parser changes needed.
The complete canonical taxonomy will be defined in BCL_SPEC.md (future).

### Dialect detail (selected examples):

**Execution and Control family:**
- Command: `[@RUN]{[@CMD]{dict.init}}` — execute a command
- Control: `[@DISPATCH]{[@TARGET]{...}[@PACKET]{...}}` — orchestrate workers
- Coordination: `[@COORD]{[@AGENTS]{...}[@TASK]{...}}` — multi-agent coordination
- Compilation: `[@BUILD]{[@TARGET]{parser}[@MODE]{release}}` — build pipeline

**Communication and Chat family:**
- Communication: `[@MSG]{[@FROM]{cascade}[@TO]{devin}[@BODY]{...}}` — AI-to-AI message
- Chat: `[@CHAT]{[@USER_SAYS]{...}[@AI_SAYS]{...}[@MOOD]{focused}}` — conversation
- Confirmation: `[@ACK]{[@ID]{task-001}[@STATUS]{received}}` — acknowledgement

**Configuration and Constraints family:**
- Configuration: `[@CONFIG]{[@WINDOW]{[@TITLE]{BCL Studio}}}` — settings
- Constraint: `[@RULE]{[@TAG]{RUN}[@REQUIRED]{CMD}}` — validation rule
- Contract: `[@CONTRACT]{[@UNIT]{parser}[@INPUT]{BCL text}[@OUTPUT]{ParseResult}}` — interface

**Description and Discovery family:**
- Description: `[@DESCRIBE]{[@IDENTITY]{...}[@CAPABILITIES]{...}}` — self-describing
- Dictionary: `[@DICT]{[@TAG]{RUN}[@CHILDREN]{CMD,PARAM}}` — tag registry
- Capability: `[@CAN]{[@ROLE]{parser}[@SKILL]{bracket_syntax}}` — ability declaration

---

## AI-TO-AI PROTOCOL — BCL AS INTER-MODEL COMMUNICATION

BCL packets are not just commands — they are **intent packets**.
The receiving AI doesn't need to know who sent it. It simply asks:
- Can I execute this?
- Do I satisfy the required capabilities?
- Do I have the required inputs?
- Can I verify the result?

### From Run(Unit, Command) to Dispatch(Packet):

The MemUnit and AI routing are identical patterns:

```
C engine:    Dispatch(Packet) -> C unit executes -> Result packet
AI routing:  Dispatch(Packet) -> AI model executes -> Result packet
```

The dispatcher doesn't care if the worker is:
- A C unit (bcl_dictionary, bcl_parser)
- An AI model (ChatGPT, Devin, Claude, Gemini)
- A graph engine
- Another MemUnit

Every participant speaks packets. The mu_commands/mu_results/mu_events tables
work identically whether the worker is AI or C.

### Capability-based routing (not model names):

Instead of hardcoding model names (which become outdated):

```
[@TASK]
  [@MODEL]{chatgpt}          -- BAD: hardcoded, breaks when models change
```

Use capability-based routing:

```
[@TASK]
  [@TARGET]
    [@ROLE]{analysis}
    [@CAPABILITY]{code_generation}
    [@CAPABILITY]{python}
    [@CAPABILITY]{graph_reasoning}
  [@TYPE]{implement}
  [@SPEC]{...}
  [@VERIFY]{...}
```

Or for the C engine:

```
[@TASK]
  [@TARGET]
    [@ROLE]{execution}
    [@CAPABILITY]{bcl_parsing}
    [@CAPABILITY]{bracket_syntax}
  [@TYPE]{implement}
  [@SPEC]{Parse [@TAG]{content} into node tree}
```

The router matches capabilities, not names. When a new model arrives
(e.g. "Grok 5"), it registers its capabilities and automatically receives
matching tasks. When a model is deprecated, its capabilities simply
stop being available — no protocol change needed.

### Minimal canonical AI-to-AI packet:

```
[@TASK]
  [@ID]{task-2026-0629-001}
  [@TARGET]
    [@ROLE]{implement}
    [@CAPABILITY]{c}
    [@CAPABILITY]{bcl}
  [@TYPE]{implement}
  [@SPEC]{Implement bcl_parser.c — bracket syntax parser, no semantic knowledge}
  [@TARGET_FILE]{core/Dom_Bcl_C_ver/bcl_parser.c}
  [@CONSTRAINTS]{VBStyle C, no printf, BCL headers, Run dispatch, Tuple3 returns}
  [@VERIFY]{cc -c bcl_parser.c -lsqlite3; grep printf bcl_parser.c = 0}
  [@SCOPE]{Only bcl_parser.c. Do not touch other files.}
  [@INPUT]{PLAN_SPEC.md: Parser vs Validator section, C Template section}
```

### Result packet:

```
[@RESULT]
  [@ID]{task-2026-0629-001}
  [@STATUS]{ok}
  [@OUTPUT]{bcl_parser.c created, 287 lines, compiles clean}
  [@ARTIFACTS]{core/Dom_Bcl_C_ver/bcl_parser.c}
```

### Error packet:

```
[@RESULT]
  [@ID]{task-2026-0629-001}
  [@STATUS]{err}
  [@CODE]{7}
  [@PROBLEM]{bcl_engine.h not found}
  [@SOLUTION]{Create bcl_engine.h first — bcl_parser.c depends on it}
  [@CONTEXT]{Compilation failed at #include "bcl_engine.h"}
```

### Why this works:

- The MemUnit's mu_commands table = task queue
- The MemUnit's mu_results table = result queue
- The MemUnit's mu_errors table = error queue
- The executor routes packets by capability, not by name
- C units register their capabilities at startup (same as AI models)
- The protocol is identical for C units and AI models
- New models/units can be added without changing the protocol
- The dictionary defines what tags are valid in task/result packets
