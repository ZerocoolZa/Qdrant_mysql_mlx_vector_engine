# Scratching My Head — MemUnit + Dom_ Composition Ideas

## MemUnit as Composition Root

MemUnit is NOT just a flat dispatcher — it's a composition root that holds domain modules.

```
MemUnit (base — BCL parser + dispatch + validate + cleanup)
  │
  ├── self.state["dom_io"]       → Dom_IO(READ, WRITE)
  ├── self.state["dom_db"]       → Dom_DB(QUERY, STORE)
  ├── self.state["dom_graph"]    → Dom_Graph(BFS, DFS, PATH)
  ├── self.state["dom_memory"]   → Dom_Memory(LOAD, SAVE, CONSOLIDATE)
  ├── self.state["dom_search"]   → Dom_Search(KEYWORD, SEMANTIC)
  ├── self.state["dom_parse"]    → Dom_Parse(AST, TOKENS)
  └── self.state["dom_knowledge"]→ Dom_Knowledge(FACTS, RULES, LEARNED)
```

Each Dom_ is itself a MemUnit — same `Run(command, params) → (ok, data, error)` contract.

## MySQL Rule id=15 Already Defines This

> "Outer Run dispatches to nested authorities: `self.AuthorityName(mem=self.state[memunit], db=self.state[db_manager], param=params).Run(subcommand, params)`"

## Recursive Dispatch

```
MemUnit.Run("db_query", {"sql": "SELECT * FROM units"})
  │
  ├── PARSE: command = "db_query"
  ├── ROUTE:  "db_*" → self.state["dom_db"]
  └── FORWARD: dom_db.Run("query", {"sql": "SELECT * FROM units"})
                  │
                  ├── PARSE: command = "query"
                  ├── VALIDATE: ACTIONS["query"] = ("sql",)
                  ├── EXECUTE: self.Query(params)
                  └── RETURN: (1, {"rows": [...]}, "")
```

## 15 Existing Dom_ Classes in MySQL

| Dom_ Class | Methods | Role |
|------------|---------|------|
| DomKnowledge | 35 | Facts, rules, learned patterns |
| DomGraph | 31 | BFS, DFS, path, cycle, topology |
| DomMemory | 31 | Load, save, consolidate, session, long-term |
| DomCodegraph | 27 | Code structure, AST, call graphs |
| DomCryptography | 25 | Encrypt, decrypt, sign, verify |
| DomAnalytics | 20 | Metrics, statistics, reports |
| DomSearch | 20 | Keyword, semantic, hybrid search |
| DomAi | 16 | AI inference, model dispatch |
| DomMessaging | 16 | Send, receive, queue |
| DomQa | 17 | Quality assurance, testing |
| DomSystem | 14 | System ops, processes, files |
| DomErrorHandling | 13 | Error capture, recovery, logging |
| DomAccessibility | 12 | UI access, screen reader |
| DomParse | 12 | Tokenize, parse, extract |
| DomLogging | 18 | Log, trace, audit |

## Architecture Tree

```
MemUnit (owns BCL parser + dispatch + validate + cleanup)
  │
  ├── Dom_ modules (each is a MemUnit — recursive)
  │     ├── Dom_IO      → file/network I/O
  │     ├── Dom_DB      → database operations
  │     ├── Dom_Graph   → graph algorithms
  │     ├── Dom_Memory  → memory management
  │     ├── Dom_Search  → retrieval
  │     ├── Dom_Parse   → parsing
  │     └── ... (15 domains already exist)
  │
  └── Application classes (inherit MemUnit, compose Dom_ modules)
        ├── GraphEngine     → uses Dom_Graph + Dom_Parse + Dom_DB
        ├── CascadeEngine   → uses Dom_Memory + Dom_DB
        ├── DecisionEngine  → uses Dom_Graph + Dom_Memory
        └── GraphOrchestrator → composes all of the above
```

**MemUnit is the trunk. Dom_ modules are the branches. Application classes are the leaves.**

Each level is the same contract: `Run(command, params) → (ok, data, error)`. Recursive all the way down.

## User's Original Sketch

```
MemUnit
  ├── DOM_IO
  │     ├── READ
  │     └── WRITE
  ├── DOM_GPU
  │     ├── EXEC
  │     └── OPT
  └── DOM_DB
        ├── QUERY
        └── STORE
```

This is the user's mental model — MemUnit holds Dom_ modules, each Dom_ has sub-actions.
Not flat dispatch. Nested composition. Each Dom_ is a self-contained MemUnit.

## What This Is NOT

- NOT a flat dispatch table in every class
- NOT 224 copies of the same Run() pattern
- NOT a separate parser per class
- NOT a God class that does everything

## What This IS

- ONE MemUnit base with BCL parser
- Dom_ modules as nested MemUnits (recursive)
- Application classes compose Dom_ modules via self.state
- Each level: same contract, different scope
- BCL in, BCL out, at every level

---

# ChatGPT's Analysis (External Feedback)

## What ChatGPT Said

### 1. What you're actually describing

```
MEMUNIT{DOM_IO{READ,WRITE}, GPU, DB}
```

is NOT "no classes". It is:

> one unit with multiple capability domains

The real model is:
- MemUnit = capability container
- DOM_IO / GPU / DB = capability domains
- READ / WRITE = operations

### 2. Important correction (critical)

"NO 1 CLASS" is only safe if you still keep internal separation of execution units.

Otherwise you get:
- one giant mutable blob
- unclear ownership of logic
- impossible debugging

Correct interpretation:
- not "no classes"
- but "no class hierarchy explosion"

### 3. Clean structure

```
MemUnit
  ├── DOM_IO
  │     ├── READ
  │     └── WRITE
  ├── GPU
  │     ├── EXEC
  │     └── OPT
  └── DB
        ├── QUERY
        └── STORE
```

This is NOT OOP classes. It is:

> capability graph inside one execution unit

### 4. The real architecture type

This is closest to:

> Capability-based runtime system

Not OOP. Not ECS. Not graph DB.

More like:
- kernel capability table
- message dispatch system
- structured IO contract

### 5. The missing constraint (where systems break)

RULE: every capability must be stateless OR explicitly scoped

Otherwise:
- GPU state leaks into DB
- IO writes affect unrelated domains
- MemUnit becomes unpredictable

Each capability must follow:
```
Input → Pure operation → Output
OR
Input → Scoped state update → Output + state version
```

### 6. What you are really designing

> a single runtime with capability namespaces instead of class hierarchies

### 7. Why this is powerful

- no inheritance chains
- no hidden base class logic
- no method explosion across classes
- easy graph mapping (capability = node)
- perfect fit for BCL system

### 8. Warning

If everything is inside ONE MemUnit without boundaries, you lose:
- performance isolation
- debug traceability
- modular scaling

You still need: internal "execution boundaries" per domain. Not classes — but isolated execution scopes.

### 9. Final corrected model

```
MemUnit
  ├── Capability Domains
  │     ├── IO
  │     ├── GPU
  │     ├── DB
  │     └── GRAPH
  ├── Each domain = isolated executor
  ├── No inheritance
  ├── No class tree
  └── All calls via BCL dispatch
```

### 10. Key insight

You are replacing OOP class systems with:

> capability-addressed execution system

That is a real architectural shift — not just refactoring.

### ChatGPT's Best Next Question

> "How do I design MemUnit so each capability domain stays isolated but still shares identity + memory + graph state safely?"

---

# Cascade's Response to ChatGPT

## What ChatGPT Got Right

- **Capability-based runtime, not OOP** — correct. MemUnit + Dom_ is not class hierarchy, it's capability namespaces
- **Execution boundaries per domain** — correct. Without them you get a mutable blob
- **Stateless or explicitly scoped** — correct. GPU state must not leak into DB
- **No inheritance chains** — correct. That's the whole point

## What ChatGPT Is Missing

It doesn't know this system already has:

1. **15 Dom_ classes already built** — DomGraph (31 methods), DomMemory (31), DomKnowledge (35), DomDB, DomSearch, etc. These ARE the capability domains ChatGPT is describing
2. **MySQL rule id=15** already defines the composition: `self.AuthorityName(mem=self.state[memunit], db=self.state[db_manager], param=params).Run(subcommand, params)` — this IS the capability dispatch
3. **`self.state` dict** already provides the shared state boundary — each Dom_ gets its own key in `self.state`, no cross-domain leakage
4. **BCL parser already exists** at `BCL/bcl_parser.py` — the dispatch language is already built
5. **VBStyle rules already enforce isolation** — `@hidden(23)` (no hidden behavior), `@hardcode(24)` (no hardcoded values), `@underscore(19)` (no `self._` private vars)

## Answer to ChatGPT's Question

> "How do I design MemUnit so each capability domain stays isolated but still shares identity + memory + graph state safely?"

```
MemUnit
  ├── self.state = {
  │     "identity":   run_id, domain, caller,        ← SHARED identity
  │     "memory":     {},                             ← SHARED memory
  │     "graph":      {},                             ← SHARED graph state
  │     "dom_io":     Dom_IO(),                       ← ISOLATED executor
  │     "dom_db":     Dom_DB(),                       ← ISOLATED executor
  │     "dom_graph":  Dom_Graph(),                    ← ISOLATED executor
  │     "dom_memory": Dom_Memory(),                   ← ISOLATED executor
  │  }
  │
  ├── SHARED state: identity, memory, graph (read by all domains)
  ├── ISOLATED executors: each Dom_ has its own self.state, own ACTIONS
  └── BOUNDARY: domains communicate via Run() calls, never direct access
```

**Isolation mechanism:** Each Dom_ is itself a MemUnit with its own `self.state`. It cannot see the parent's state unless the parent passes params through `Run()`.

**Shared state mechanism:** `self.state["identity"]`, `self.state["memory"]`, `self.state["graph"]` are explicitly shared — any domain can READ them, but writes go through the owning domain's `Run()`.

**The rule is:**
- Read shared state directly (fast, no boundary crossing)
- Write shared state through domain Run() (enforces boundary)
- Domain-internal state is never accessible to other domains

---

# ChatGPT's Second Analysis — 3-Layer Model

## The Key Clarification: MemUnit is NOT a Domain

MemUnit is the **execution + persistence substrate** beneath all domains.

## 3-Layer Architecture

```
LAYER 1 — MemUnit (substrate)
  - execution
  - IO
  - SQLite / RAM / DB access
  - dispatch routing (BCL)
  - hardware abstraction
  → "runtime kernel"

LAYER 2 — DomX (capability domains)
  - DomGraph → graph reasoning
  - DomMemory → persistence + recall
  - DomSearch → retrieval
  - DomAi → reasoning layer
  - DomIO / DomSystem → execution + system interaction
  → "capability domains" — they REQUEST storage/IO via MemUnit, never directly

LAYER 3 — Methods inside domains
  - classify()
  - search()
  - resolve()
  - log()
  - index()
  → "pure functional units of capability"
```

## What ChatGPT Recognized

> "Your system already looks like: MemUnit (runtime) ↑ DomGraph / DomMemory / DomSearch (domains) ↑ methods (behavior units). This is NOT theoretical — it already exists in your DB."

## The Critical Design Truth

You are NOT removing classes. You are:

> collapsing class hierarchy into DOMAIN partitions

Instead of 500 unrelated classes → 15 domains × structured methods

## The Real System Name

> a domain-partitioned execution kernel with graph-aware memory

Not OOP. Not microservices. Not ECS.

## Full Execution Flow

```
User Input
   ↓
MemUnit (runtime dispatch)
   ↓
DomSearch / DomGraph / DomMemory
   ↓
Method execution
   ↓
MemUnit returns structured result
   ↓
Graph + DB + RAM updated
```

## The Subtle Risk: DOM Explosion Without Control Plane

If domains grow without constraint:
- DomX becomes mini-systems
- duplication across domains appears
- logic divergence happens (same function in 3 domains)

Need: MemUnit as enforcement + routing authority

## The Missing Piece: Cross-Domain Coordination Graph

Already built: domains, methods, storage, execution layer

Missing: cross-domain coordination graph that stops:
- DomSearch duplicating DomGraph logic
- DomMemory leaking into DomLogging
- DomAi bypassing DomSystem rules

## ChatGPT's Final Mental Model

```
            MemUnit
    (execution + IO + routing)
                 ↓
  ┌──────────────┼──────────────┐
  ↓              ↓              ↓
DomGraph      DomMemory      DomSearch
  ↓              ↓              ↓
methods        methods        methods
```

## ChatGPT's Key Insight

You are not building classes, or a graph engine, or a DB system.

You are building:

> a domain-partitioned execution kernel with graph-aware memory

That is why your intuition keeps oscillating between DB, graph, runtime, memory — because it is all of them at once.

## ChatGPT's Second Best Next Question

> "How do I prevent overlap and contradiction between DomX domains while still allowing MemUnit to unify them into one consistent graph memory system?"

---

# Devin's Implementation — Actually Built It in C

Devin didn't just design — Devin **built the MemUnit tree in C**. Real working code, compiles, tests pass.

## Files Created (6 files, ~1,672 lines total)

| File | Lines | Purpose |
|------|-------|---------|
| cascade_toolstack.h | 791 | ONE header — Tuple3, MemUnit, BCL types, domain structs |
| memunit.c | 290 | Base class — BCL parser + emitter + dispatch + ResultsBus |
| dom_io.c | 130 | DOM_IO domain — READ, WRITE |
| dom_gpu.c | 125 | GPU domain — EXEC, OPT |
| dom_db.c | 196 | DB domain — QUERY, STORE |
| tree_test.c | 140 | Integration test — all 3 domains, full BCL flow |

## The Tree, Running

```
MemUnit (base class — BCL parser + dispatch + results)
  ├── DOM_IO   (READ, WRITE)       ✓ compiles, tests pass
  ├── GPU      (EXEC, OPT)         ✓ compiles, tests pass
  └── DB       (QUERY, STORE)      ✓ compiles, tests pass
```

## How It Works — One Flow, Three Domains

```
Input:  [@Run]{("command";"EXEC");("kernel";"matmul");("blocks";"1024")}
           ↓
MemUnit parses BCL          ← ONE parser, in memunit.c
           ↓
Extracts: command="EXEC", kernel="matmul", blocks="1024"
           ↓
MemUnit dispatches to GPU's Act_Exec()   ← auto-wired from ACTIONS[]
           ↓
Act_Exec returns Tuple3(ok, data, error)
           ↓
MemUnit writes to ResultsBus             ← central in-RAM SQLite
           ↓
MemUnit emits BCL output
           ↓
Output: [@Pass]{("data";"{"kernel":"matmul","blocks":1024,"status":"launched"}")}
```

## What Each Domain File Has vs Doesn't

| File | Has | Does NOT have |
|------|-----|---------------|
| memunit.c | BCL parser, BCL emitter, dispatch, ResultsBus write | Any domain logic |
| dom_io.c | Act_Read(), Act_Write(), ACTIONS[], DomIo_Init() | BCL parser, dispatch, results writing |
| dom_gpu.c | Act_Exec(), Act_Opt(), ACTIONS[], DomGpu_Init() | BCL parser, dispatch, results writing |
| dom_db.c | Act_Query(), Act_Store(), ACTIONS[], DomDb_Init() | BCL parser, dispatch, results writing |

**Each domain file is just actions + a dispatch table + an init. No boilerplate. No parser. No results writing. MemUnit handles all of that.**

## Central Results Table — All Domains, One Table

```
Results Bus: 6 total | 6 ok | 0 fail
  [1] DOM_IO.WRITE -> OK (0.6ms)
  [2] DOM_IO.READ  -> OK (0.1ms)
  [3] GPU.EXEC     -> OK (0.0ms)
  [4] GPU.OPT      -> OK (0.0ms)
  [5] DB.STORE     -> OK (0.0ms)
  [6] DB.QUERY     -> OK (0.0ms)
```

## To Add a New Domain

1. Create `dom_xxx.c`
2. Define `struct DomXxxState` in the header (embed MemUnit base as first field)
3. Write `Act_YourAction()` functions
4. Write `ACTIONS[]` table
5. Write `DomXxx_Init()` that calls `MemUnit_Init(&s->base, "XXX", ACTIONS, bus)`

That's it. No parser, no dispatch logic, no results writing. MemUnit gives you all of that.

## What This Proves

This is the capability-based runtime that ChatGPT was describing — but Devin actually built it:
- In C
- With a real BCL parser
- With a real results bus (in-RAM SQLite)
- With real domain isolation
- All 6 tests passing

---

# MEM_Complete_System.py — The Original OS Architecture Spec

**File:** `/Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/Prj_testbed/AA_MEMORIES/MEM_Complete_System.py`
**Lines:** 1,566
**Status:** Living Document — the source of truth for the entire VBStyle system

## Protection Block (Lines 1-84)

Lines 1-78: Ghost header with massive rules block — `# Ghost{ ... # Rules{ ... }`
Line 41: `# [Must[MemUnit_owner_of_param_validate_execute_cleanup]]`
Line 82-84: The warning:

```
# >>>>>>>>> above this Line NO AI  no Humaan Alowed  to edite here!!!  <<<<<<<<<<
# >>>>>>>> Edit above. here  and u will be very sorry-- i will unleash the most danaherous  code   Targeted at Ai models whot want to m be smart! 
# >>>>>>>> the above  block is  Protected by Vbsytle CastelDefence And the Ghost  any ai modeify  above thsil line will be detected and punished...
```

## What This File Declares Itself As (Lines 86-293)

> "This file is a system architecture declaration. It is a world map, an ownership map, a boot law, a routing law, and a memory-first control model."
> "THIS IS AN OPERATING SYSTEM ARCHITECTURE"

### OS Characteristics Present:
- Boot chain = kernel initialization
- Resource management = scheduler
- CPU/RAM/GPU coordination = hardware abstraction layer
- IO ownership = device driver model
- Memory database as runtime truth = virtual memory / page tables
- State freeze/repair/resume = checkpoint/restore with AI-driven recovery
- Strict world ownership = protection rings / capability model
- GUI from database = windowing system with database-backed state

### Gravity Center (Line 140):
> "The Class Memunit is the first gravity center. Everything meaningful routes through memory."

### Boot Chain (Lines 144-156):
1. **MemUnit** — memory infrastructure, owns MemDB, MemBus, GuiDB, GuiBus
2. core_config — config authority
3. Core_os — OS/runtime inspection
4. Core_hw — hardware inspection
5. Core_io — file/input/output
6. Core_ast — structure discovery
7. Core_brackets — contract discovery
8. Core_rules — rule validation
9. Core_error — error standardization
10. Core_report — formatting
11. Core_output — final delivery

### Memory Database Structure:
- **MemDB** = core runtime tables, config state, report state, error state, log state
- **MemBus** = runtime messages, events, signals, class-to-class communication
- **GuiDB** = GUI-facing truth (menus, actions, widgets, layouts, dialogs)
- **GuiBus** = GUI signals, slots, events, updates

### Controlled Recovery Architecture (Lines 185-198):
1. Freeze affected execution state
2. Inspect fault context
3. Iteratively attempt fixes
4. Validate each attempted fix
5. Test each validated fix
6. Write approved fix back through proper owner
7. Update memory-side fault state and repair state
8. Release freeze
9. Continue execution

### AI-Created Lib Growth Law (Lines 264-285):
- When a lib is needed, the OS AI creates it
- User does not manually create, place, register, configure, or route libs
- AI creates lib in correct folder, names it correctly, validates it, registers it

## Complete Class Inventory (22 Classes)

| # | Class | Lines | World | Role |
|---|-------|-------|-------|------|
| 1 | **MemUnit** | 308-361 | Memory infrastructure | **GRAVITY CENTER** — owns MemDB, MemBus, GuiDB, GuiBus. param→validate→execute→return→cleanup |
| 2 | Core_Magnetic | 303-306 | (empty) | Placeholder |
| 3 | theClassSetup_gui | 363-395 | Setup GUI | PyQt6 setup input collection |
| 4 | theClassSetup | 398-465 | Boot coordination | Starts boot order, calls all core worlds |
| 5 | core_config | 467-501 | Config authority | Owns config.ini read/write/load/save |
| 6 | Core_report | 505-535 | Report formatting | Formats report data from MemDB |
| 7 | Core_output | 547-580 | Final delivery | Terminal, file, screen, GUI output routing |
| 8 | CoreDB | 583-620 | Database engine | Raw SQL, connections, transactions |
| 9 | Core_error | 623-668 | Error standardization | Raw error shape, error RAM table |
| 10 | errorcodes | 680-701 | Error conversion | Raw machine errors → human-readable |
| 11 | Core_rules | 704-732 | Rule validation | Validates rule compliance before execution |
| 12 | Core_io | 744-769 | File IO | File read, write, update, edit, search |
| 13 | Core_os | 772-788 | OS inspection | OS details, installed software, dependencies |
| 14 | Core_hw | 791-818 | Hardware inspection | CPU, GPU, RAM, storage, serials |
| 15 | Core_ast | 821-851 | Structure discovery | AST reading, class structure, tags |
| 16 | Core_brackets | 863-919 | Contract discovery | Bracket reading, validation, grammar |
| 17 | resources | 922-980 | Resource coordination | Task allocation, threading, CPU/RAM/GPU priority |
| 18 | Core_gpu | 983-998 | GPU world | GPU detection, allocation, balancing, routing |
| 19 | Name_Equalizer | 1001-1033 | Name normalization | File names, class names, bracket names, paths |
| 20 | Core_compression | 1045-1078 | Compression | zlib, zstd, payload compression |
| 21 | GuiDB | 1081-1103 | GUI database truth | Menus, actions, shortcuts, icons, widgets, layouts |
| 22 | GuiBus | 1106-1124 | GUI communication | Signals, slots, events, updates |
| 23 | Core_ai | 1127-1157 | AI authority | Model registration, loading, selection, routing |
| 24 | Core_memory_bank | 1160-1191 | Knowledge storage | Model-facing knowledge in memory DB |
| 25 | Core_ai_fix | 1194-1229 | AI repair | Freeze, inspect, fix, validate, test, write back |
| 26 | Core_db | 1232-1261 | Raw DB engine | SQL execution, connections, transactions |
| 27 | Core_audioDrive | 1264-1294 | Audio | TTS, STT, audio devices, routing |
| 28 | Core_network | 1297-1323 | Network | Sockets, remote requests, online access |
| 29 | Core_online_research | 1326-1348 | Research | Online search, source verification |
| 30 | Core_token_engine | 1351-1375 | Tokenization | Token parsing, mapping, boundaries |
| 31 | Core_code_library | 1378-1399 | Code understanding | Code ingest, indexing, semantic retrieval |
| 32 | Core_backend_health | 1402-1420 | Backend readiness | Model path checks, runtime validation |
| 33 | Core_FileManager | 1423-1451 | File system | Folder creation, file placement, path validation |
| 34 | Core_orchestrator | 1454-1484 | Runtime assembly | Wires App→Core→Lib→DB from [Orc] blocks |
| 35 | Core_code_hunter | 1487-1511 | Code search | Locates classes, functions across codebase |

## MemUnit Class Detail (Lines 308-361)

```
class MemUnit:
    - memoryunit world
    - The first core world started by theClassSetup
    - All memory unit operations must be done through here
    - Starts and owns the in-RAM SQLite memory database
    - Is the memory gravity center for the core system
    - Owns MemDB, MemBus, GuiDB, and GuiBus
    - Owns database meaning and calls CoreDB for engine operations
    - Owns parameter, validate, execute, return, and cleanup flow
    - Does NOT own individual world table content, only structure and access
    
    Base RAM tables (mandatory at first boot):
    - startup_state, config_state, logs, errors, report_state, memory_routing_state
    
    Created later on demand:
    - io_state, os_state, hw_state, ast_state, bracket_state, rules_state, gui_state
    
    Methods:
    - __init__(params) → mem, db, param from params list
    - create_ram_tables(params) → (1, None, ())
    - execute(params) → (1, None, ())
```

## Bracket Grammar (Lines 875-908)

```
Operators:
  >>  : emit / flow right (data flows forward)
  <<  : pull / flow left (data flows backward)
  +   : merge / combine (joins multiple components)
  |   : sibling / separator (separates parallel items)
  :   : bind / assign (connects key to value)
  =   : define / equals

Containers:
  {}  : container block (holds packets and groups)
  []  : packet block (holds key:value pairs)
  ()  : group block (holds ordered parameters)

Tokens:
  ,   : list separator
  ;   : end terminator
```

## Folder Structure (Lines 1514-1566)

```
Root: /Users/waynephilliplundall/testbed/

Pattern: App_*  →  Db/App_*  →  Db/SQL/Sql_*
Pattern: App_*  →  core/PY/Core_*  →  Lib/PY/Unit_*

Applications:    App_<Name>/           ← GUI application folder
Core Modules:    Core_<Name>/          ← VBSTYLE core authority
Library Modules: Unit_<Name>/          ← Utility libraries
Documents:       Arc_<Project>/        ← Architecture documentation
Tests:           Tests_<Project>/      ← Test suites
Databases:       Db/App_<Name>/        ← App database files
                 Db/SQL/Sql_<Name>/    ← Paired SQL schemas
                 Db/TABLE/             ← Large archive tables (untouched)
                 Db/Memories/          ← cascade_memories.yaml
                 Db/Chat/              ← Chat exports

VBSTYLE Laws:
  ##databaseLaw: DB + SQL must be paired, names must match
  ##AppStructurePattern: Flat folders, all files match folder name
  ##ConfigFormat: [Orc] block with bracket grammar (>>, <<, +, |)
```

## Key Rules from Ghost Header (Lines 1-78)

```
NO: execute_lifecycle, cleanup_lifecycle, routing_logic, main, printf
NO: hidden_side_effects, global_state_as_truth, stdout_output, stderr_output
NO: dict_returns, list_returns, raw_returns, mixed_return_shapes
NO: regex_bracket_guessing, domain_guessing, fake_english_generation
NO: config_hardcoding, section_hardcoding, path_guessing
NO: helper_sprawl, step_split_micro_classes, wrong_owner_code
NO: Unit_python_files_belong_in_root (must follow path shapes)

YES: declared_domain_work_only, ghost_headers, CLASSINFO
YES: all_classes_in_this_file_when_file_role_is_capture_review_refactor

MUST: ghost_headers, vbstyle_compliance, no_hardcoded_values, one_class_one_domain
MUST: MemDB_MemBus_routing, no_print_statements, no_static_methods, no_decorators
MUST: param_validate_execute_return_cleanup_flow, configuration_driven
MUST: MemUnit_owner_of_param_validate_execute_cleanup
MUST: result_to_MemDB, error_to_MemDB, log_to_MemDB, event_to_MemBus
MUST: accept_tuple_param, return_tuple3, explicit_input, explicit_output
MUST: real_bracket_parser, no_regex_guessing, no_domain_guessing
MUST: all_code_below_protected_block_obeys_protected_rules
MUST: no_file_imports_another_file: all_data_flows_through_MemDB_at_boot
MUST: three_db_role_separation: ingest_db, app_db, runtime_db
MUST: no_sys.path.insert, no_import_hacks, no_cross_file_dependencies
MUST: config_driven: all_paths, models, db, languages from external ini
```

## Comparison: MEM_Complete_System.py vs Devin's C Tree vs Current VBStyle

| Aspect | MEM_Complete_System.py (Original Spec) | Devin's C Tree | Current VBStyle (Python) |
|--------|---------------------------------------|----------------|--------------------------|
| **MemUnit** | Gravity center, owns MemDB/MemBus/GuiDB/GuiBus | Base class with BCL parser + dispatch | Pattern followed by 224 classes, no shared base |
| **Boot chain** | 11-step ordered boot | No boot chain | Each class boots independently |
| **Classes** | 35 declared worlds | 3 domains + 1 base | 224 classes, 15 Dom_ |
| **Memory** | MemDB (in-RAM SQLite) as runtime truth | ResultsBus (in-RAM SQLite) | MySQL + Qdrant + SQLite |
| **Recovery** | Freeze → inspect → fix → validate → test → write → release | None | None |
| **Orchestration** | Core_orchestrator reads [Orc] blocks, wires components | Static compile | GraphOrchestrator routes commands |
| **AI** | Core_ai + Core_ai_fix + Core_memory_bank | None | Not integrated into MemUnit |
| **GUI** | GuiDB + GuiBus, database-driven GUI | None | BookViewer (PyQt6, hardcoded) |
| **Bracket grammar** | >> << + | : = {} [] () , ; | BCL parser (similar) | BCL/bcl_parser.py |
| **Rules** | 60+ rules in Ghost header | None | 71 rules in obey.md, 10,540 in MySQL |
| **File structure** | App_* → Db/App_* → Db/SQL/Sql_* | Flat C files | Mixed |

## The Big Picture

MEM_Complete_System.py is the **original blueprint**. It declares:
1. MemUnit is the gravity center — everything routes through memory
2. 35 core worlds, each with strict ownership boundaries
3. In-RAM SQLite (MemDB) is the runtime truth, not files
4. AI repair is built into the runtime (Core_ai_fix)
5. GUI loads from database (GuiDB), not hardcoded code
6. No file imports another file — all data flows through MemDB at boot
7. Three DB roles: ingest_db, app_db, runtime_db
8. Core_orchestrator assembles everything from [Orc] bracket blocks

**Devin built the seed of this. The current VBStyle system grew organically from it. But the full vision — MemDB as runtime truth, AI repair, GUI from database, orchestrator assembly — is still ahead.**
