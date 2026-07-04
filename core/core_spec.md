# Core VBStyle Architecture Spec

> **Location**: `/Core/`
> **Source**: `v20_hybrid_best.db` (classes + methods tables)
> **Created**: 2026-06-26
> **Status**: Draft — pending user review

---

## Purpose

The `Core/` folder contains the foundational VBStyle classes that every other module, domain, and tool builds on. These are not domain-specific implementations — they are the infrastructure layer: memory, dispatch, execution, reporting, error handling, AST parsing, OS/hardware detection, indexing, and bootstrapping.

All classes follow VBStyle conventions:
- `__init__(self, mem=None, db=None, param=None)`
- `self.state = {}` dict (no `self._` variables)
- `Run(self, command, params=None)` dispatch method
- `read_state(self)` / `set_config(self, config)`
- All methods return Tuple3: `(1, data, None)` or `(0, None, (code, desc, 0))`
- No `print()`, no decorators, no hardcoded paths, PascalCase classes, UPPERCASE constants

---

## File Inventory

| File | Class | Domain | Methods | Source |
|------|-------|--------|---------|--------|
| `core_config.py` | Config | config | — | New — follows BookSystem config pattern |
| `core_mem_unit.py` | MemUnit | orchestration | 6 | VBSTYLE_MemUnit.py |
| `core_mem_db.py` | MemDb | storage | 8 | dom_db |
| `core_mem_bus.py` | MemBus | storage | 3 | VBSTYLE_MemUnit.py |
| `core_orchestration.py` | Orchestration | orchestration | 4 | dom_orchestration |
| `core_executor.py` | Executor | orchestration | 6 | dom_runtime |
| `core_report.py` | Report | reporting | 9 | CODEBASE scan |
| `core_error_handler.py` | ErrorHandler | errorhandling | 29 | CODEBASE scan |
| `core_ast.py` | AST | analysis | 6 | VBSTYLE_AST.py |
| `core_class_ast.py` | ClassAST | analysis | 9 | CODEBASE scan |
| `core_hardware.py` | Hardware | storage | 7 | CODEBASE scan |
| `core_os.py` | OSLayer | orchestration | 5 | CODEBASE scan |
| `core_class_os.py` | ClassOS | config | 6 | CODEBASE scan |
| `core_domain_system.py` | DomainSystem | config | — | Unified from UnifyDomain + SystemDomain |
| `core_class_indexer.py` | ClassIndexer | ingest | 10 | CODEBASE scan |
| `core_index_authority.py` | IndexAuthority | storage | 11 | dom_index |
| `core_gui_bus.py` | GuiBus | gui | — | Unified from EventBus + MemBus scoped to GUI |
| `core_gui_db.py` | GuiDB | gui | — | Unified from GuiDBActions + GuiDbWriter |
| `core_bootstrap.py` | BootstrapLoader | orchestration | 6 | CODEBASE scan |
| `core_runtime_guard.py` | RuntimeGuard | orchestration | 7 | CODEBASE scan |
| `core_unit_base.py` | UnitBase | orchestration | 5 | CODEBASE scan |
| `core_verification.py` | VerificationSuite | orchestration | 16 | Core_Verification.py |

**Total: 22 files, 22 classes**

---

## Class Responsibilities

### 1. Config (`core_config.py`)

**Authority**: Configuration — all constants, paths, schema, MySQL config

**Responsibilities**:
- BASE_DIR derivation from `__file__`
- File paths for all Core modules
- MySQL connection config (user, host, port, database)
- VBStyle rule definitions (9 rules)
- Domain registry constants
- Schema SQL for bootstrap (tables + views)
- Version constants
- Documentation constants (ABOUT, HELP, README)

**Pattern**: Follows BookSystem/config.py gold standard — single Config class, all class attributes, singleton instance `cfg = Config()`

**VBStyle rules not applicable**: `@run`, `@t3`, `@state`, `@ctor`, `@memunit`, `@dismap`, `@rdst`, `@cfg` — config is passive authority, not executable

---

### 2. MemUnit (`core_mem_unit.py`)

**Authority**: Central dispatch unit — the heart of VBStyle

**Responsibilities**:
- Connect core modules (`connect_core`)
- Connect library modules (`connect_lib`)
- Execute commands (`execute`)
- Dispatch via `Run(self, command, params)`
- Track state in `self.state`

**Methods from DB**:
- `__init__(self, mem, db, param)`
- `Run(self, command, params)`
- `connect_core(self, params)` — wire up Core modules
- `connect_lib(self, params)` — wire up external libraries
- `execute(self, params)` — execute a command through connected units
- `read_state(self, params)`

**Domain**: orchestration

---

### 3. MemDb (`core_mem_db.py`)

**Authority**: Command queue + schema persistence

**Responsibilities**:
- Create and manage SQLite/MySQL schema
- Queue commands for async execution
- Retrieve next command from queue
- Update command results
- Track execution state

**Methods from DB**:
- `__init__(self, mem, db, param)`
- `Run(self, command, params)`
- `_create_schema(self)` — initialize DB tables
- `_queue_command(self, params)` — enqueue a command
- `_get_next_command(self, params)` — dequeue next command
- `_update_command_result(self, params)` — record execution result
- `read_state(self)`
- `set_config(self, values)`

**Domain**: storage

---

### 4. MemBus (`core_mem_bus.py`)

**Authority**: Pub/sub message bus

**Responsibilities**:
- Publish events to subscribers
- Subscribe to event channels
- Route messages between modules

**Methods from DB**:
- `__init__(self, mem, db, param)`
- `publish(self, params)` — publish an event
- `subscribe(self, params)` — subscribe to a channel

**Domain**: storage

---

### 5. Orchestration (`core_orchestration.py`)

**Authority**: Task orchestration — dispatch, scheduling, worker management

**Responsibilities**:
- Dispatch tasks to executors
- Schedule task execution
- Manage worker lifecycle
- Track task status

**Methods from DB**:
- `__init__(self, mem, db, param)`
- `Run(self, command, params)`
- `read_state(self)`
- `set_config(self, values)`

**Domain**: orchestration

**Note**: The full domain implementation is `DomOrchestration` (13 methods: `dispatch`, `queue`, `schedule`, `parallel`, `retry`, `worker`, `priority`, `timeout`, `sequence`, `dependency`, `pause`, `resume`, `status`). This Core class is the minimal interface; `DomOrchestration` is the full domain.

---

### 6. Executor (`core_executor.py`)

**Authority**: Command execution engine

**Responsibilities**:
- Execute individual commands
- Call functions with parameters
- Manage execution context

**Methods from DB**:
- `__init__(self, mem, db, param)`
- `Run(self, command, params)`
- `_call(self, params)` — invoke a callable
- `_execute(self, params)` — execute a command
- `read_state(self)`
- `set_config(self, values)`

**Domain**: orchestration

---

### 7. Report (`core_report.py`)

**Authority**: Structured reporting, snapshots, semantic clustering

**Responsibilities**:
- Build reports from multiple layers
- Attach data layers (OS, hardware, etc.)
- Take system snapshots
- Extract tags from objects
- Build semantic clusters from keywords
- Ingest report data

**Methods from DB**:
- `__init__(self, mem, db, param)`
- `Run(self, command, params)`
- `attach_layer(self, params)` — attach a data layer
- `build(self, params)` — build the full report
- `build_semantic_clusters(self, keywords, file_paths)` — cluster by keywords
- `extract_tags(self, obj)` — extract tags from an object
- `ingest(self, params)` — ingest report data
- `set_layers(self, os_layer, hw_layer)` — set OS and hardware layers
- `snapshot(self, params)` — take a system snapshot

**Domain**: reporting

---

### 8. ErrorHandler (`core_error_handler.py`)

**Authority**: Error capture, classification, recovery, suppression

**Responsibilities**:
- Capture errors with system state
- Classify error types
- Execute recovery strategies
- Correlate related errors
- Track error frequency and trends
- Manage suppression rules
- Resolve errors
- Provide human-readable reports
- Initialize and manage error schema

**Methods from DB** (29 total):
- `__init__(self, mem, db, param)`
- `Run(self, command, params)`
- `capture_error(self, params)` — capture an error
- `capture_system_state(self, params)` — snapshot system on error
- `classify_error(self, params)` — classify error type
- `check_rate_limit(self, params)` — rate limiting
- `clear_error_log(self, params)` — clear log
- `consume_engine_result(self, params)` — process engine result
- `correlate_errors(self, params)` — find related errors
- `delete_suppression_rule(self, params)` — remove suppression
- `execute_recovery(self, params)` — run recovery strategy
- `get_error_definitions(self, params)` — retrieve definitions
- `get_error_frequency(self, params)` — frequency stats
- `get_error_log(self, params)` — retrieve log
- `get_error_stats(self, params)` — summary stats
- `get_error_trends(self, params)` — trend analysis
- `get_human_readable_report(self, params)` — formatted report
- `get_recovery_policy(self, params)` — recovery policy
- `get_snapshots(self, params)` — retrieve snapshots
- `get_suppression_rules(self, params)` — retrieve suppressions
- `get_unresolved_count(self, params)` — count unresolved
- `initialize_schema(self, params)` — create DB tables
- `read_state(self, params)`
- `register_error_definition(self, params)` — define error type
- `resolve_error(self, params)` — mark resolved
- `set_config(self, params)`
- `set_suppression_rule(self, params)` — add suppression
- `_seed_defaults(self, cursor)` — seed default data
- `Get_connection(self)` — DB connection

**Domain**: storage (DB says storage; full domain is `DomErrorHandling` in errorhandling domain)

---

### 9. AST (`core_ast.py`)

**Authority**: Python AST parsing and class rule validation

**Responsibilities**:
- Parse Python files into AST
- Validate single class rules
- Provide state access

**Methods from DB**:
- `__init__(self, mem, db, param)`
- `Run(self, command, params)`
- `parse_python_file(self, params)` — parse a .py file
- `validate_one_class_rule(self, params)` — validate a class against rules
- `read_state(self, params)`
- `set_config(self, params)`

**Domain**: analysis

---

### 10. ClassAST (`core_class_ast.py`)

**Authority**: Class-level AST analysis — detection, parsing, discovery

**Responsibilities**:
- Detect classes in source files
- Parse source code into class structures
- Find classes with Run methods
- Extract parameters from function nodes

**Methods from DB**:
- `__init__(self, mem, db, param)`
- `Run(self, command, params)`
- `detect(self, params)` — detect classes in source
- `find_run_classes(self, params)` — find classes with Run() method
- `parse_file(self, params)` — parse a file
- `parse_source(self, params)` — parse source string
- `_params(self, func_node)` — extract params from AST
- `read_state(self)`
- `set_config(self, config)`

**Domain**: analysis

---

### 11. Hardware (`core_hardware.py`)

**Authority**: Hardware detection and resource limits

**Responsibilities**:
- Detect available hardware (CPU, RAM, cores)
- Calculate optimal thread counts
- Determine safe memory limits
- Provide hardware state

**Methods from DB**:
- `__init__(self, mem, db, param)`
- `Run(self, command, params)`
- `_detect(self, params)` — detect hardware
- `_get_optimal_threads(self, params)` — calculate thread count
- `_get_safe_memory_limit(self, params)` — calculate safe RAM
- `read_state(self)`
- `set_config(self, config)`

**Domain**: storage

---

### 12. OSLayer (`core_os.py`)

**Authority**: OS detection, paths, safe file operations

**Responsibilities**:
- Detect operating system
- Provide safe file operations
- Manage OS-specific paths
- Take system snapshots

**Methods from DB**:
- `__init__(self, mem, db, param)`
- `Run(self, command, params)`
- `read_state(self)`
- `set_config(self, config)`
- `snapshot(self, params)` — system snapshot

**Domain**: orchestration

---

### 13. ClassOS (`core_class_os.py`)

**Authority**: Foundation OS class for DOM operations

**Responsibilities**:
- Detect OS capabilities
- Check if features are supported
- Provide OS state for domain modules

**Methods from DB**:
- `__init__(self, mem, db, param)`
- `Run(self, command, params)`
- `detect(self, params)` — detect OS
- `is_supported(self, params)` — check feature support
- `read_state(self)`
- `set_config(self, config)`

**Domain**: config

---

### 14. DomainSystem (`core_domain_system.py`)

**Authority**: Unified domain registry and dispatch

**Responsibilities**:
- Register domains
- Route commands to the correct domain
- Unify domain access (merges UnifyDomain + SystemDomain)
- Provide domain status

**Methods from DB** (merged from UnifyDomain + SystemDomain):
- `__init__(self, mem, db, param)`
- `Run(self, command, params)`
- `read_state(self)`
- `set_config(self, config)`

**Domain**: config (unified)

**Note**: DB has `UnifyDomain` (storage, 4 methods) and `SystemDomain` (config, 4 methods) as separate classes. This Core class unifies them into a single domain system dispatcher.

---

### 15. ClassIndexer (`core_class_indexer.py`)

**Authority**: Index classes from source files

**Responsibilities**:
- Extract classes from Python files
- Parse class names from source lines
- Parse VBStyle annotations from class content
- Index classes by name and role
- Find classes by name
- Find classes by role

**Methods from DB**:
- `__init__(self, mem, db, param)`
- `Run(self, command, params)`
- `Extract_classes(self, path)` — extract classes from a path
- `_parse_class_name(self, line)` — parse class name from line
- `_parse_vbstyle(self, content, class_name)` — parse VBStyle annotations
- `find_by_name(self, params)` — find class by name
- `find_by_role(self, params)` — find class by role
- `index(self, params)` — index a file or directory
- `read_state(self)`
- `set_config(self, config)`

**Domain**: ingest

---

### 16. IndexAuthority (`core_index_authority.py`)

**Authority**: Inverted index generation and validation

**Responsibilities**:
- Generate inverted index for a directory
- Invert index directory
- Generate file brackets for index entries
- Validate index integrity
- Manage index results

**Methods from DB**:
- `__init__(self, mem, db, param)`
- `Run(self, command, params)`
- `generate_index(self, target_dir)` — generate index for directory
- `Invert_index_directory(self, target_dir)` — invert directory index
- `_generate_file_bracket(self, path, target_dir)` — create file bracket entry
- `_now_utc(self)` — current UTC timestamp
- `clear_results(self)` — clear index results
- `get_results(self)` — retrieve index results
- `validate(self)` — validate index
- `read_state(self)`
- `set_config(self, values)`

**Domain**: storage

---

### 17. GuiBus (`core_gui_bus.py`)

**Authority**: GUI event bus — pub/sub scoped to GUI events

**Responsibilities**:
- Publish GUI events (click, key, mouse, resize, close)
- Subscribe to GUI event channels
- Route events to GUI handlers

**Methods** (unified from EventBus + MemBus pattern):
- `__init__(self, mem, db, param)`
- `Run(self, command, params)`
- `publish(self, params)` — publish a GUI event
- `subscribe(self, params)` — subscribe to GUI events
- `read_state(self)`
- `set_config(self, config)`

**Domain**: gui

**Note**: DB has no class literally called `GuiBus`. Closest: `EventBus` (orchestration, pub/sub), `MemBus` (storage, pub/sub). This Core class is EventBus scoped to GUI.

---

### 18. GuiDB (`core_gui_db.py`)

**Authority**: GUI database actions and writes

**Responsibilities**:
- Execute DB actions from GUI (GuiDBActions: 12 methods)
- Write GUI state to DB (GuiDbWriter: 11 methods)
- Manage GUI database snapshots
- Bridge GUI operations to persistence layer

**Methods** (unified from GuiDBActions + GuiDbWriter):
- `__init__(self, mem, db, param)`
- `Run(self, command, params)`
- DB action methods (from GuiDBActions)
- DB write methods (from GuiDbWriter)
- `read_state(self)`
- `set_config(self, config)`

**Domain**: gui

**Note**: DB has `GuiDBActions` (storage, 12 methods) and `GuiDbWriter` (storage, 11 methods) as separate classes. This Core class unifies them.

---

### 19. BootstrapLoader (`core_bootstrap.py`)

**Authority**: System bootstrap — every model runs this first

**Responsibilities**:
- Load system architecture
- Find the correct table for a token
- Get instructions by name
- Explain architecture to new models
- Database access

**Methods from DB**:
- `__init__(self)`
- `load(self)` — load bootstrap data
- `find_table_for_token(self, token_name)` — locate token's table
- `get_instruction(self, name)` — get instruction by name
- `explain_architecture(self)` — explain system to models
- `_db(self)` — database access

**Domain**: orchestration

**Note**: This class does NOT follow VBStyle yet (no `Run`, no `mem/db/param` init, no `read_state`/`set_config`). Needs conversion.

---

### 20. RuntimeGuard (`core_runtime_guard.py`)

**Authority**: Runtime limits — max RAM, max time, abort on breach

**Responsibilities**:
- Check memory usage against limits
- Run processes with guardrails
- Run threads with guardrails
- Safe execution with mode selection
- Track crashes
- Add solutions for problems

**Methods from DB**:
- `__init__(self, max_ram_mb, max_time_sec)`
- `check_memory(self)` — check RAM usage
- `run_process(self, func, args, kwargs)` — run with process guard
- `run_thread(self, func, args, kwargs)` — run with thread guard
- `safe_execute(self, func, mode)` — safe execution
- `get_crashes(self)` — retrieve crash log
- `add_solution(self, problem_index, solution_text)` — add solution

**Domain**: orchestration

**Note**: This class does NOT follow VBStyle yet (no `Run`, no `mem/db/param` init, no `read_state`/`set_config`). Needs conversion.

---

### 21. UnitBase (`core_unit_base.py`)

**Authority**: Base class for all units

**Responsibilities**:
- Provide Dispatch method
- Provide Run method
- Handle bad actions
- Handle bad params
- Track unit name, authority, params

**Methods from DB**:
- `__init__(self, name, authority, params)`
- `Run(self, action, params)`
- `Dispatch(self, action, params)`
- `_bad_action(self, message)`
- `_bad_params(self, message)`

**Domain**: orchestration

**Note**: Has `_bad_action` and `_bad_params` which use `self._` — VBStyle violation. Needs conversion to `self.state["bad_action"]` pattern.

---

### 22. VerificationSuite (`core_verification.py`)

**Authority**: System verification — cold boot, circular deps, VBStyle audit

**Responsibilities**:
- Run all verification tests
- Test cold boot
- Test circular dependencies
- Test class discovery
- Test Claude bridge
- Test component registry
- Test duplicate public classes
- Test memory centrality
- Test QA engine
- Test runtime integrity
- Test shard compression
- Test shutdown integrity
- Test VBStyle audit
- Log test results
- Print results

**Methods from DB** (16 total):
- `__init__(self)`
- `run_all(self)` — run all tests
- `test_cold_boot(self)` — cold boot test
- `test_circular_dependencies(self)` — circular dep check
- `test_class_discovery(self)` — class discovery test
- `test_claude_bridge(self)` — Claude bridge test
- `test_component_registry(self)` — registry test
- `test_duplicate_public_classes(self)` — duplicate check
- `test_memory_centrality(self)` — memory centrality
- `test_qa_engine(self)` — QA engine test
- `test_runtime_integrity(self)` — runtime check
- `test_shard_compression(self)` — shard compression
- `test_shutdown_integrity(self)` — shutdown test
- `test_vbstyle_audit(self)` — VBStyle compliance audit
- `log(self, category, test, result, details)` — log result
- `print_results(self)` — output results

**Domain**: orchestration

**Note**: Uses `print_results` — VBStyle violation (`@print(22)`). Needs conversion to return Tuple3.

---

## Dependency Graph

```
BootstrapLoader
  └── loads → Config
  └── loads → DomainSystem
       ├── registers → all domains

MemUnit (central dispatch)
  ├── connects → MemDb (persistence)
  ├── connects → MemBus (pub/sub)
  ├── connects → Orchestration
  │     └── dispatches → Executor
  ├── connects → Report
  ├── connects → ErrorHandler
  ├── connects → OSLayer
  │     └── uses → Hardware
  ├── connects → ClassOS
  ├── connects → AST
  │     └── uses → ClassAST
  ├── connects → ClassIndexer
  ├── connects → IndexAuthority
  ├── connects → GuiBus
  ├── connects → GuiDB
  └── connects → VerificationSuite

RuntimeGuard
  └── wraps → Executor (safe execution)

UnitBase
  └── parent of → all units
```

---

## Classes Needing VBStyle Conversion

| Class | Issue | Fix |
|-------|-------|-----|
| BootstrapLoader | No `Run`, no `mem/db/param` init, no `read_state`/`set_config` | Add VBStyle boilerplate |
| RuntimeGuard | No `Run`, no `mem/db/param` init, no `read_state`/`set_config` | Add VBStyle boilerplate |
| UnitBase | Has `self._` (`_bad_action`, `_bad_params`) | Convert to `self.state["bad_action"]` |
| VerificationSuite | Has `print_results` (print violation) | Convert to return Tuple3 |
| MemBus | Missing `Run`, `read_state`, `set_config` | Add VBStyle boilerplate |

---

## Domain Registry (from DB)

The following domains are registered in `v20_hybrid_best.db`:

```
Dom_Vector, accessibility, ai, analysis, analytics, arch, archive, asm, audit,
automation, bytecode, caching, cli, codec, codegraph, compass, compression,
concurrency, config, convert, cryptography, csplit, cu, db, db_inv, db_studio,
deployment, documentation, errorhandling, factory, featureflags, fileops,
folder, general, governance, graph, graph_engine, graphs, gui, http, index,
ingest, ingest_cli, ingest_gui, io, knowledge, localization, log, logging,
memory, messaging, network, observability, orchestration, package, parse,
process, project_indexer, qa, qt, ratelimiting, reporting, rescue, resilience,
runtime, schedule, search, security, serialization, storage, style, system,
testing, text, transform, unify, validate, validation, vcs, workflow,
wws_index, yaml
```

Core classes map to these domains:
- Config → config
- MemUnit, Orchestration, Executor, OSLayer, BootstrapLoader, RuntimeGuard, UnitBase, VerificationSuite → orchestration
- MemDb, MemBus, Hardware, IndexAuthority → storage
- Report → reporting
- ErrorHandler → errorhandling
- AST, ClassAST → analysis
- ClassOS, DomainSystem → config
- ClassIndexer → ingest
- GuiBus, GuiDB → gui
