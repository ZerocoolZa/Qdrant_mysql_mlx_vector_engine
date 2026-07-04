```

```

# BCL C Engine — Central DB Architecture

# =======================================

# [@GHOST]{file_path="core/Dom_Bcl_C_ver/PLAN_CENTRAL_DB.md"

# date="2026-06-29" author="cascade" context="Central DB architecture for C code storage and build"}

# [@VBSTYLE]

# [@SUMMARY]{summary="Specification for storing all C unit source code in MySQL c_classes table,

# loading to disk for compilation, and managing the build lifecycle from DB."}

---

## ARCHITECTURE — 4-LAYER MODEL

### Concept

All C source code lives in MySQL. Disk is a build artifact, not source of truth.
DB is build-time only. Runtime is pure compiled C — no MySQL dependency.

### Layer 1 — Source of Truth (MySQL)

- c_classes table stores all C source code as text
- Queryable, versioned, hash-tracked
- This is the canonical source repository
- NO runtime access — build-time only

### Layer 2 — Materializer (loader script)

- Pulls rows from MySQL in dependency order
- Resolves dependencies via topological sort
- Writes .c files to disk in correct order
- Emits build manifest (JSON)
- This is a compiler feeder, NOT a runtime system

### Layer 3 — Build Output (filesystem, disposable)

- .c files — materialized from DB
- .o object files — compiled artifacts
- binaries — final executables
- All disposable — can be rebuilt from DB at any time

### Layer 4 — Runtime (compiled binary only)

- Pure C execution — no MySQL access required
- BCL in → BCL out
- No network dependency, no DB dependency
- Traditional C runtime behavior

### Flow

```
Layer 1: MySQL c_classes (source of truth, build-time only)
    ↓  loader: pull + dependency sort + materialize
Layer 2: core/Dom_Bcl_C_ver/*.c (build artifacts, disposable)
    ↓  cc compiler
Layer 3: core/Dom_Bcl_C_ver/bin/* (executables, disposable)
    ↓  run
Layer 4: BCL in → BCL out (pure C runtime, no DB)
```

### Critical Constraint

Never collapse layers. DB = build-time brain. Binary = runtime body.
Mixing them introduces nondeterministic execution, network dependency,
reproducibility loss, and debugging complexity.

---

## MYSQL SCHEMA (existing c_classes table)

```sql
-- Already exists in vb_shared.c_classes
-- Columns used:
--   id            — auto increment
--   class_name    — e.g. "IngestionEngine"
--   class_code    — full C source code as text
--   description   — one-line summary
--   domain        — e.g. "bcl_c_engine"
--   authority     — e.g. "ingestion_engine"
--   bcl_ghost     — [@GHOST] header
--   bcl_vbstyle   — [@VBSTYLE] header
--   bcl_fileid    — file identifier
--   bcl_summary   — summary text
--   bcl_methods   — comma-separated method names
--   bcl_includes  — #include lines
--   dependencies  — JSON array of structured edge objects (see below)
--   status        — active | retired | draft
--   version       — integer version number
--   hash          — SHA256 of class_code (for sync)
--   build_hash    — SHA256 of (class_code + resolved_deps + includes + flags)
--   updated_at    — timestamp of last change
```

### Schema additions needed (ALTER TABLE):

```sql
ALTER TABLE c_classes ADD COLUMN hash VARCHAR(64) DEFAULT NULL;
ALTER TABLE c_classes ADD COLUMN build_hash VARCHAR(64) DEFAULT NULL;
ALTER TABLE c_classes ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
```

### Dependency Edge Types (structured JSON in dependencies column)

Dependencies are NOT flat class name arrays. Each dependency has a type:

```json
[
  {"type": "include", "target": "vbast.h"},
  {"type": "call",    "target": "GraphStore"},
  {"type": "link",    "target": "BclParser"}
]
```

| Edge type   | Meaning                       | Affects                                    |
| ----------- | ----------------------------- | ------------------------------------------ |
| `include` | #include header dependency    | Write order — header must exist first     |
| `call`    | Function call to another unit | Compile order — callee must compile first |
| `link`    | Link-time dependency          | Link order — must be in same binary       |

### Build Fingerprint (build_hash)

build_hash = SHA256(class_code + resolved_dependencies + includes + compiler_flags)

This prevents silent drift where DB says "same version" but build output differs.
The build_hash changes if ANY of these change:

- Source code (class_code)
- Any dependency's code (transitive)
- Include tree
- Compiler flags

The `hash` column tracks source-only changes (for sync).
The `build_hash` column tracks full build context (for incremental rebuild).

---

## LOADER SCRIPT — bcl_c_loader.py

### Purpose

Pull C source from MySQL, resolve dependency order, write to disk, compile, verify.
This is a deterministic build pipeline, NOT a runtime system.

### Commands (VBStyle Run dispatch)

```
load_all      — pull all active units from c_classes, dependency sort, write .c files
load_one      — pull single unit by class_name + its dependency chain, write .c files
compile_all   — compile all .c files in dependency order
compile_one   — compile single .c file
build_all     — load_all + compile_all + emit manifest
build_one     — load_one + compile_one
build_changed — incremental: only reload + recompile units whose hash changed
verify_all    — compile + run read_state on each unit
sync          — compare DB hashes vs disk hashes, report differences
clean         — delete all .c and bin files from folder (DB is source of truth)
status        — report which units are in DB, on disk, compiled, or missing
manifest      — emit build_manifest.json listing all units, hashes, deps, compile status
```

### Parameters

```
db_host     — localhost (default)
db_user     — root (default)
db_name     — vb_shared (default)
db_table    — c_classes (default)
output_dir  — core/Dom_Bcl_C_ver/ (default)
domain      — bcl_c_engine (filter, only pull this domain)
compile_cmd — cc -c FILE.c -lsqlite3 -lssl (default)
```

### Dependency Resolution Algorithm (critical)

The loader MUST resolve dependencies before writing files. Steps:

1. SELECT all rows WHERE domain='bcl_c_engine' AND status='active'
2. Parse dependencies column (structured JSON with edge types)
3. Build dependency graph with typed edges:
   - include edges → header must be written first
   - call edges → callee must be compiled first
   - link edges → unit must be in same binary
4. Topological sort (Kahn's algorithm) over call + include edges:
   - Resolve includes first (write headers)
   - Resolve call dependencies (compile order)
   - Resolve link dependencies (link order)
5. If cycle detected → report cycle chain, abort (hard fail)
6. Write .c files in topological order
7. Compute build_hash for each unit
8. Emit build_manifest.json with resolved order + build_hashes

### Topological Sort Pseudocode

```
function ResolveOrder(units):
    # Build graph from call + include edges only
    # link edges affect final link step, not compile order
    graph = {}    # unit_name → [dependency_names from call+include]
    in_degree = {}  # unit_name → count of unresolved deps
    for unit in units:
        deps = [d["target"] for d in unit.dependencies
                if d["type"] in ("call", "include")]
        graph[unit.name] = deps
        in_degree[unit.name] = len(deps)
  
    queue = [u for u in units if in_degree[u] == 0]
    result = []
  
    while queue:
        node = queue.pop(0)
        result.append(node)
        for dependent in graph:
            if node in graph[dependent]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
  
    if len(result) != len(units):
        remaining = [u for u in units if u not in result]
        ERROR: circular dependency among: remaining
    return result
```

### Build Manifest (JSON output)

```json
{
  "built_at": "2026-06-29T04:50:00Z",
  "domain": "bcl_c_engine",
  "units": [
    {
      "class_name": "GraphTypes",
      "hash": "a1b2c3...",
      "dependencies": [],
      "file": "GraphTypes.c",
      "compiled": true,
      "order": 1
    },
    {
      "class_name": "GraphStore",
      "hash": "d4e5f6...",
      "dependencies": ["GraphTypes"],
      "file": "GraphStore.c",
      "compiled": true,
      "order": 2
    }
  ],
  "total": 14,
  "compiled": 14,
  "failed": 0
}
```

### Incremental Rebuild Logic

1. Read build_manifest.json from previous build
2. For each unit in DB: compute build_hash = SHA256(code + deps + includes + flags)
3. Compare with manifest build_hash:
   - build_hash matches → skip (no change in code or deps)
   - build_hash differs → reload + recompile + recompile dependents
   - Unit in DB but not in manifest → new unit, load + compile
   - Unit in manifest but not in DB → orphan, delete .c file
4. Only changed units and their transitive dependents get recompiled
5. If a dependency's code changed, all units that call/include it must recompile

### Sync Logic

- For each row in c_classes: compute SHA256 of class_code
- For each .c file on disk: compute SHA256 of file content
- If hashes differ: DB is newer → reload
- If file exists on disk but not in DB: orphan → report
- If row exists in DB but no file: missing → load

---

## UNIT REGISTRY (what goes in c_classes)

| class_name            | domain       | authority              | source                     | status | dependencies                                       |
| --------------------- | ------------ | ---------------------- | -------------------------- | ------ | -------------------------------------------------- |
| BclDictionary         | bcl_c_engine | bcl_dictionary         | new                        | draft  | []                                                 |
| BclParser             | bcl_c_engine | bcl_parser             | new                        | draft  | [{"call":"BclDictionary"}]                         |
| GraphStore            | bcl_c_engine | graph_store            | existing (mysql_store.c)   | active | [{"include":"vbast.h"}]                            |
| IngestionEngine       | bcl_c_engine | ingestion_engine       | existing (ast_walker.c)    | active | [{"include":"vbast.h"}]                            |
| GraphBuilder          | bcl_c_engine | graph_builder          | existing (graph_builder.c) | active | [{"include":"vbast.h"},{"call":"IngestionEngine"}] |
| StaticAnalyzer        | bcl_c_engine | static_analyzer        | existing (vbstyle_check.c) | active | [{"include":"vbast.h"},{"call":"IngestionEngine"}] |
| BclStamper            | bcl_c_engine | bcl_stamper            | existing (bcl_stamper.c)   | active | [{"include":"vbast.h"}]                            |
| CallPathEngine        | bcl_c_engine | call_path_engine       | new                        | draft  | [{"call":"GraphBuilder"}]                          |
| ControlFlowEngine     | bcl_c_engine | control_flow_engine    | new                        | draft  | [{"call":"GraphBuilder"}]                          |
| DataFlowEngine        | bcl_c_engine | data_flow_engine       | new                        | draft  | [{"call":"GraphBuilder"}]                          |
| RelationshipExtractor | bcl_c_engine | relationship_extractor | new                        | draft  | [{"call":"GraphBuilder"}]                          |
| IrExtractor           | bcl_c_engine | ir_extractor           | new                        | draft  | [{"call":"IngestionEngine"}]                       |
| ReportEngine          | bcl_c_engine | report_engine          | new                        | draft  | [{"call":"GraphStore"}]                            |
| ExecutionTracer       | bcl_c_engine | execution_tracer       | new                        | draft  | [{"call":"GraphStore"}]                            |
| BclDispatcher         | bcl_c_engine | bcl_dispatcher         | new                        | draft  | [{"link":"all"}]                                   |

---

## COMPILE AND LINK STRATEGY

### System-linked (all units → one binary)

All 14 C units compile to .o object files, then link into a single binary:
`dom_graph_engine`

```
Step 1: cc -c BclDictionary.c    -o BclDictionary.o    -lsqlite3
Step 2: cc -c BclParser.c         -o BclParser.o         -lsqlite3
Step 3: cc -c GraphStore.c        -o GraphStore.o        -lsqlite3 -lmysqlclient
...
Step N: cc *.o -o dom_graph_engine -lsqlite3 -lmysqlclient -lssl
```

### Symbol collision handling

- Each unit prefixes its functions: `BclParser_Run()`, `GraphStore_Load()`, etc.
- No global symbols except `main()` in the entry point unit
- The `vbast.h` header is the only shared header (exception to no-.h rule)
- All other communication is via BCL strings (const char *)

### BCL Execution Boundary

A central dispatcher (`bcl_dispatcher.c` or `main.c`) receives BCL input,
routes to the correct unit, and returns BCL output:

```
BCL input: [@RUN]{[@CMD]{graph.call_graph}[@FILE]{foo.py}}
    ↓
Dispatcher parses [@CMD] → routes to GraphBuilder
    ↓
GraphBuilder.Run("graph.call_graph", bcl_input)
    ↓
Returns BCL output: [@OK]{[@NODES]{...}[@EDGES]{...}}
    ↓
Dispatcher returns BCL output to caller
```

Units do NOT call each other directly. They communicate via BCL strings
through the dispatcher. This keeps units independent and testable.

---

## BUILD LIFECYCLE

### Phase 1 — Schema + Storage normalization

1. ALTER c_classes: add hash, build_hash, updated_at columns
2. Read each .c file from Cascade_toolStack/vbast/
3. Extract BCL headers from comments
4. INSERT into c_classes with domain='bcl_c_engine'
5. Parse dependencies into structured JSON with edge types
6. Compute and store SHA256 hash + build_hash for each row
7. Verify all 6 existing files are in DB with correct hashes

### Phase 2 — Create new units in MySQL

1. Write BCL shell template for each new unit
2. INSERT into c_classes with status='draft'
3. Set dependencies JSON for each unit
4. 8 new units: BclDictionary, BclParser, CallPathEngine, ControlFlowEngine,
   DataFlowEngine, RelationshipExtractor, IrExtractor, ReportEngine, ExecutionTracer

### Phase 3 — Dependency graph + first build

1. Run bcl_c_loader.py load_all — topological sort + write .c files
2. Verify dependency order is correct (no cycles)
3. Run bcl_c_loader.py compile_all
4. Fix compile errors in DB, re-load, re-compile
5. Run bcl_c_loader.py manifest — emit build_manifest.json

### Phase 4 — Incremental development

1. For each unit, write the actual implementation in MySQL class_code
2. Update hash in DB
3. Run bcl_c_loader.py build_changed — only recompiles changed units
4. Test with BCL input/output
5. Iterate until all units pass

### Phase 5 — Verify

1. Run verify_all — each unit responds to read_state
2. Run integration test — units call each other via BCL
3. Run sync — verify DB and disk are identical
4. Run clean + build_all — verify full rebuild from scratch works
5. Run spec_graph_runner against PLAN_SPEC.md
6. Run arch_validator against the compiled system
7. Delete all disk files, rebuild from DB, verify identical output

---

## ADVANTAGES OF CENTRAL DB

1. **Single source of truth** — MySQL, not disk. No file conflicts.
2. **Versioned** — every unit has a version number in c_classes
3. **Queryable** — search units by domain, authority, status, dependencies
4. **Sync-able** — compare DB vs disk hashes, detect drift
5. **Incremental rebuild** — only recompile changed units (like Make)
6. **Build artifact separation** — .c files are disposable, DB is permanent
7. **Same pattern as Python Fast Method** — already proven to work
8. **msearch compatible** — msearch can find C code in c_classes table
9. **Dependency queryable** — SELECT dependencies, traverse the graph in SQL
10. **Deterministic builds** — same DB state = same binary, every time

---

## DISADVANTAGES

1. **Cannot compile directly from DB** — must load to disk first
2. **MySQL dependency for builds** — if MySQL is down, cannot build
3. **Extra step** — load before compile (but fast, < 1 second)
4. **Not standard C workflow** — most C devs expect source on disk
5. **Runtime is clean** — no MySQL dependency at runtime (by design)

---

## FILE STRUCTURE (build artifacts only)

```
core/Dom_Bcl_C_ver/
    PLAN_SPEC.md          — original plan spec (permanent)
    PLAN_CENTRAL_DB.md    — this file (permanent)
    bcl_c_loader.py       — loader script (permanent)
    bcl_dictionary.c      — build artifact (disposable)
    bcl_parser.c          — build artifact (disposable)
    graph_store.c         — build artifact (disposable)
    ingestion_engine.c    — build artifact (disposable)
    graph_builder.c       — build artifact (disposable)
    static_analyzer.c     — build artifact (disposable)
    bcl_stamper.c         — build artifact (disposable)
    call_path_engine.c    — build artifact (disposable)
    control_flow_engine.c — build artifact (disposable)
    data_flow_engine.c    — build artifact (disposable)
    relationship_extractor.c — build artifact (disposable)
    ir_extractor.c        — build artifact (disposable)
    report_engine.c       — build artifact (disposable)
    execution_tracer.c    — build artifact (disposable)
    bin/                  — compiled binaries (disposable)
```

Only 3 files are permanent (source of truth is MySQL):

- PLAN_SPEC.md
- PLAN_CENTRAL_DB.md
- bcl_c_loader.py

Everything else can be deleted and rebuilt from DB.

---

## VERIFICATION CHECKLIST

1. All 14 units exist in c_classes with domain='bcl_c_engine'
2. bcl_c_loader.py load_all writes 14 .c files
3. bcl_c_loader.py compile_all compiles all 14 without errors
4. bcl_c_loader.py sync reports 0 differences
5. bcl_c_loader.py status shows all 14 as active+compiled
6. Each unit responds to [@RUN]{[@CMD]{read_state}} with [@OK]
7. MySQL is the only source of truth — delete disk files, rebuild, verify identical
