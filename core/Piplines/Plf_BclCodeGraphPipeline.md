# BCL Code Graph Pipeline — Code → Computational Units → BCL Identity → MySQL

> **Core thesis:** Code is not just text. Every `.py` file is parsed into classes,
> methods, functions, and computational units. Each unit gets a BCL identity token
> (a "nametag"). Units are stored in MySQL with their relationships, stamps, and
> metadata — forming a queryable code graph.
>
> **The Garmin Principle:** Pipelines are the roads. The CodeGPS Garmin navigator
> visualizes these roads. Green = safe route, red = failed route, gray = unexplored.
> The pipelines ARE the infrastructure the Garmin drives on. Without pipelines,
> the Garmin has no roads. Without the Garmin, the pipelines have no navigation.

---

## Pipeline Overview

```
.py Files → AST Parse → Extract Classes/Methods/Functions
                                ↓
                    Computational Units (tightly coupled groups)
                                ↓
                    BCL Identity Tokens (nametags for every entity)
                                ↓
                    MySQL vb_code_test (bcl_classes, bcl_methods, bcl_units)
                                ↓
                    Code Graph (bcl_edges: calls, inherits, contains)
                                ↓
                    BCL Stamps (reasoning traces linked to methods)
                                ↓
                    BCL Projection (.bcl view files — derived, not source)
```

---

## Stages

### Stage 1: INGEST — Parse .py Files

**Tools:** `ingest_bcl.py`, `bcl_mysql_ingestor.py`, `ingest_graph_code.py`

Read every `.py` file in a directory. Use Python's `ast` module to extract:
- **Classes** — name, bases, methods, line range, docstring
- **Methods** — name, params, body, calls, decorators, return type, line range
- **Functions** — top-level functions (same as methods without class)
- **Imports** — imported names, modules
- **Constants** — module-level UPPERCASE assignments

**Stable IDs:** Every entity gets a deterministic ID:
```python
StableId(filepath, "class", class_name, lineno)  → md5 hash → 12-char hex
StableId(filepath, "method", class_name, method_name, lineno)  → md5 hash
```

**Output:** Rows in `bcl_files`, `bcl_classes`, `bcl_methods` (MySQL `vb_code_test`)

### Stage 2: EXTRACT FEATURES — FeatureExtractor

**Tool:** `bcl_extractor.py` (`FeatureExtractor` class)

For each method, extract features via AST walking:
- `has_print` — print() calls found
- `has_self_underscore` — self._xxx access
- `decorator_count` — number of decorators
- `returns_tuple3` — returns (1, data, None) pattern
- `has_branching` — if/elif/else statements
- `has_loops` — for/while loops
- `has_recursion` — calls self.method_name
- `throws_exceptions` — raise statements
- `handles_exceptions` — try/except blocks
- `mutates_global_state` — global keyword
- `mutates_external` — file/network/DB writes
- `certain_count` / `probable_count` / `unknown_count` — certainty tiers
- `inputs` / `outputs` — parameter and return analysis
- `method_type` — init / run / command / query / helper / cli
- `is_async` — async def
- `is_deterministic_subset` — pure function, no side effects

**Output:** Feature map per method → feeds into RuleEngine + IRCompiler

### Stage 3: CLASSIFY — RuleEngine + Domain Inference

**Tool:** `BclGenerator.py` (`RuleEngine` class), `bcl_extractor.py` (`infer_domain`)

**RuleEngine** evaluates VBStyle rules against features:
```
@print(22)     — has_print == True → VIOLATION
@decorators(20) — decorator_count > 0 → VIOLATION
@underscore(19) — has_self_underscore → VIOLATION
@t3(50)        — return_count > 0 and not returns_tuple3 → VIOLATION
@pascal(38)    — class_name not PascalCase → VIOLATION
@run(43)       — not has_run → VIOLATION
@ctor(40)      — not has_init → VIOLATION
@state(41)     — not has_state → VIOLATION
@tabs(25)      — has_tabs → VIOLATION
```

**Domain inference** — keywords in file path, class names, method names:
- `graph` → domain=graph
- `bcl` → domain=bcl
- `chat` → domain=chat_mover
- `error` → domain=error
- `utility` → domain=utility

### Stage 4: COMPILE — IRCompiler

**Tool:** `bcl_compiler.py` (`IRCompiler` class)

Compiles Python AST → BCL IR blocks:
1. `FeatureExtractor` extracts features per method
2. `RuleEngine` evaluates rules → violations list
3. `BCLSerializer` serializes to BCL IR format

**BCL IR format:**
```
[@ClassName]{
    (@file;"/path/to/file.py")
    (@domain;"graph")
    (@role;"spec_viewer")
    (@methods;3)
    (@violations;0)
    (92)
}
[@MethodName]{
    (@class;"ClassName")
    (@type;"command")
    (@params;"data;params")
    (@returns;"Tuple3")
    (@calls;"MethodA;MethodB")
    (@certain;5)(@probable;2)(@unknown;1)
    (92)
}
```

**Output:** IR blocks stored in `ir_nodes`, `ir_files` tables

### Stage 5: COMPUTATIONAL UNITS

**Tool:** `ingest_graph_code.py`, `bcl_identity_generator.py`

Group tightly coupled classes/methods into **computational units** (CUs):
- A CU is a set of methods that must run together to accomplish a task
- Detected by: high internal call density, shared state keys, shared resources
- `is_closed` — all internal calls are within the unit (no external dependencies)
- `internal_calls` — calls between methods in the same unit
- `external_call_count` — calls to methods outside the unit

**BCL identity for CUs:**
```
[@CU_Bootstrap]{
    ("identity";"CU_Bootstrap")
    ("unit_type";"init_sequence")
    ("class";"DomWorkflow")
    ("methods";"Init+load_knowledge+load_embedder")
    ("description";"Bootstraps the workflow domain")
    (92)
}
```

**Output:** Rows in `bcl_units`, `bcl_unit_methods`, `bcl_unit_deps`

### Stage 6: BCL IDENTITY TOKENS

**Tool:** `bcl_identity_generator.py`

Generate self-description BCL tokens for every entity at 4 levels:

| Level | Entity | Example |
|---|---|---|
| DOMAIN | "I am the ai domain. I do X. My classes are Y." | `[@DomAi]{("identity";"AI domain")...}` |
| CLASS | "I am DomAi. I can classify, generate, ..." | `[@DomAi]{("identity";"DomAi")("capabilities";"classify,generate")...}` |
| METHOD | "I am the compress method. I take (data, algorithm)." | `[@Compress]{("class";"DomCompression")("params";"data;algorithm")...}` |
| CU | "I am CU_Bootstrap. I am Init + load knowledge + load embedder." | `[@CU_Bootstrap]{("identity";"CU_Bootstrap")...}` |

**Storage:** `bcl_identity` table with FTS5 search:
```sql
CREATE TABLE bcl_identity (
    id INTEGER PRIMARY KEY,
    entity_type TEXT,      -- 'domain', 'class', 'method', 'cu'
    entity_id TEXT,
    entity_name TEXT,
    domain TEXT,
    bcl_token TEXT,        -- the full BCL token
    self_narrative TEXT    -- natural language description
);
CREATE VIRTUAL TABLE bcl_search USING fts5(
    entity_name, bcl_token, self_narrative,
    content='bcl_identity', content_rowid='id'
);
```

When you ask "How does DomAi work?", the interrogator retrieves the BCL token, the LLM reads it and formats it as natural speech.

### Stage 7: CODE GRAPH EDGES

**Tool:** `bcl_object_database.py`, `bcl_mysql_ingestor.py`

Build relationship edges between code objects:

| Edge Type | Meaning | Certainty |
|---|---|---|
| `contains` | Class contains method | CERTAIN |
| `calls` | Method A calls Method B | CERTAIN / PROBABLE / UNKNOWN |
| `inherits` | Class A inherits from Class B | CERTAIN |
| `imports` | File A imports from File B | CERTAIN |
| `depends` | Unit A depends on Unit B | CERTAIN / PROBABLE |

**Edge table:**
```sql
CREATE TABLE bcl_edges (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codebase_id INT NOT NULL,
    bcl_method_id INT,           -- source method
    source_method_id VARCHAR(512),
    target VARCHAR(512),         -- target method/class
    target_method_row_id INT,
    edge_type VARCHAR(20) NOT NULL,  -- calls, inherits, contains, imports, depends
    certainty VARCHAR(10) NOT NULL,  -- CERTAIN, PROBABLE, UNKNOWN
    resolution VARCHAR(50),      -- how the edge was resolved
    resource_type VARCHAR(20),   -- io, core, link, init, cleanup
    line_number INT
);
```

**Current data:** 4,147 edges in `vb_code_test.bcl_edges`

### Stage 8: BCL STAMPS — Reasoning Traces

**Tools:** `BclStampBuilder.py`, `BclStampStore.py`

Link code to reasoning. When the LLM generates code + reasoning, a BCL stamp is created:

```
[@BCL_STAMP]{
    trace_id="tr_4410"
    goal="fix print() violation in eyes_26.py"
    intent="replace print() with return Tuple3"
    source_nodes="node_12;node_15"
    changes_applied="line 45: print(x) → return (1, x, None)"
    rejected_paths="path_3: would break paren depth"
    event_refs="evt_100;evt_101"
}
```

**Stamp lifecycle:**
1. LLM generates code + reasoning → `BuildStampFromReasoning()`
2. Stamp stored in `bcl_stamps` table (linked to `bcl_method_id`)
3. `InjectStampIntoCode()` — adds `[@BCL_STAMP]` header to method source
4. When method changes → old stamp superseded (append-only), new stamp attached
5. Events emitted: `EVENT_BCL_STAMP_ATTACHED`, `EVENT_BCL_STAMP_SUPERSEDED`

**Stamp table:**
```sql
CREATE TABLE bcl_stamps (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bcl_method_id INT NOT NULL,
    bcl_class_id INT,
    stamp_type VARCHAR(20) DEFAULT 'METHOD',  -- METHOD or CLASS
    trace_id VARCHAR(50),
    goal VARCHAR(255),
    intent VARCHAR(255),
    source_nodes TEXT,
    changes_applied TEXT,
    rejected_paths TEXT,
    event_refs TEXT,
    mu_node_id INT,             -- link to MemUnit reasoning node
    stamp_status VARCHAR(20) DEFAULT 'VALID'  -- VALID, SUPERSEDED, INVALID
);
```

### Stage 9: BCL PROJECTION — Derived Views

**Tool:** `bcl_projector.py` (`BclProjector` class)

Generate `.bcl` view files from classified IR. BCL is a **derived projection**, not the source of truth:
- `@CLASS` blocks from AST-extracted classes
- `@METHOD` blocks from classified IR
- `@DOMAIN` blocks from domain clusters
- `@DEPENDENCIES` from call + execution edges
- `@STATE_USAGE` from state-coupling graph
- `@RESOURCE_USAGE` from resource graph
- Certainty tier annotations: `[CERTAIN]` / `[PROBABLE]` / `[UNKNOWN]`

**Key principle:** BCL is GENERATED, not hand-written. Editing BCL does not change code. Code changes → IR changes → BCL regenerates.

### Stage 10: OBJECT DATABASE — Unified Storage

**Tool:** `bcl_object_database.py` (`BCLObjectDatabase` class)

SQLite database combining all code objects with BCL metadata:

```sql
-- One row per code element (file/class/method/function)
CREATE TABLE code_objects (
    object_id TEXT PRIMARY KEY,    -- StableId hash
    object_type TEXT NOT NULL,     -- 'file', 'class', 'method', 'function'
    object_name TEXT NOT NULL,
    parent_id TEXT,                -- FK to parent object
    bcl_header TEXT,               -- raw BCL header from file
    source_code TEXT,              -- full source of this object
    language TEXT DEFAULT 'python',
    namespace TEXT,
    start_line INT, end_line INT,
    signature TEXT, visibility TEXT, docstring TEXT,
    imports TEXT, dependencies TEXT, tags TEXT,
    status TEXT DEFAULT 'stable',
    version TEXT DEFAULT '1.0',
    checksum TEXT
);

-- Semantic BCL layer
CREATE TABLE bcl_metadata (
    object_id TEXT PRIMARY KEY,
    bcl_type TEXT, bcl_domain TEXT, bcl_purpose TEXT,
    bcl_role TEXT, bcl_owner TEXT, bcl_priority TEXT,
    bcl_stage TEXT, bcl_state TEXT
);

-- Graph edges
CREATE TABLE object_relationships (
    parent_id TEXT, child_id TEXT,
    parent_name TEXT, child_name TEXT,
    relationship TEXT NOT NULL,   -- contains, calls, inherits
    call_lineno INT
);

-- Revision history
CREATE TABLE source_versions (
    object_id TEXT, revision INT,
    checksum TEXT, source_code TEXT,
    created_at TEXT,
    PRIMARY KEY (object_id, revision)
);
```

---

## MySQL Schema (vb_code_test)

The production database. All code graph data lives here.

| Table | Rows | Purpose |
|---|---|---|
| `bcl_codebases` | 2 | Registered codebases (name, root_path, counts) |
| `bcl_files` | 54 | One row per ingested .py file (hash, line/class/method counts) |
| `bcl_classes` | 63 | One row per class (name, file_path, bases, method_count, line range) |
| `bcl_methods` | 655 | One row per method (name, class, type, features, certainty counts) |
| `bcl_units` | 24 | Computational units (method groups, closure, call counts) |
| `bcl_edges` | 4,147 | Code graph edges (calls, inherits, contains with certainty) |
| `bcl_stamps` | 1 | BCL reasoning stamps linked to methods |
| `bcl_stamp_events` | — | Stamp lifecycle events |
| `bcl_unit_methods` | — | Methods belonging to each computational unit |
| `bcl_unit_deps` | — | Dependencies between computational units |
| `vb_classes` | 1,394 | Simplified class registry (name, domain, role, description) |
| `vb_methods` | 13,818 | Simplified method registry (name, class_id, params, code) |

---

## File Locations

```
BCL CODE GRAPH PIPELINE FILES:
├── core/Dom_Bcl/                        — BCL domain (40+ files)
│   ├── Config_BCL.py                    — BCL config
│   ├── bcl_extractor.py                 — FeatureExtractor (AST → features)
│   ├── bcl_compiler.py                  — IRCompiler (AST → BCL IR)
│   ├── bcl_engine.py                    — BCLEngine (LEX → PARSE → VALIDATE → FIX → SERIALIZE)
│   ├── bcl_lexer.py                     — BCLTokenizer (tokenize BCL text)
│   ├── bcl_parser.py                    — BCLParser (parse tokens → BCLNode tree)
│   ├── bcl_validator.py                 — BCLValidator (validate BCL structure)
│   ├── bcl_fixer.py                     — BCLFixer (auto-fix BCL violations)
│   ├── bcl_serializer.py                — BCLSerializer (serialize BCL to text)
│   ├── bcl_identity_generator.py        — Generate BCL identity tokens (4 levels)
│   ├── bcl_object_database.py           — SQLite object DB (code_objects + relationships)
│   ├── bcl_mysql_ingestor.py            — Ingest .py files into MySQL vb_code_test
│   ├── bcl_projector.py                 — BclProjector (IR → .bcl view files)
│   ├── bcl_crud.py                      — CRUD operations on BCL objects
│   ├── bcl_query.py                     — Query BCL objects
│   ├── bcl_diff.py                      — Diff between BCL versions
│   ├── bcl_roundtrip.py                 — Round-trip: code → BCL → code
│   ├── bcl_reporter.py                  — Reports on BCL coverage
│   ├── bcl_analyzer.py                  — Analyze BCL structure
│   ├── bcl_visitor.py                   — Visitor pattern for BCL tree
│   ├── bcl_rules.py                     — RuleEngine (VBStyle rule evaluation)
│   ├── bcl_schema.py                    — Schema definitions
│   ├── bcl_importer.py                  — Import BCL from external sources
│   ├── bcl_exporter.py                  — Export BCL to various formats
│   ├── bcl_formatter.py                 — Format BCL text
│   ├── bcl_merger.py                    — Merge BCL from multiple sources
│   ├── bcl_cache.py                     — Cache for BCL parse results
│   ├── bcl_cli.py / bcl_cli_dom.py      — CLI tools
│   ├── bcl_fix_cli.py                   — CLI fixer tool
│   ├── BclGenerator.py                  — AST → FeatureMap → RuleEngine → BCL header
│   ├── BclGenerator_v2.py               — V2 generator
│   ├── BclStampBuilder.py               — Build BCL stamps from reasoning
│   ├── BclStampStore.py                 — CRUD for BCL stamps (append-only supersede)
│   ├── BclViewer.py                     — Visualize BCL
│   ├── ingest_bcl.py                    — One-shot ingestion into SQLite
│   └── bcl_all.py                       — Combined runner
│
├── chat_mover/                          — CodeGPS Garmin (pipeline navigator)
│   ├── codegps_garmin.py                — PyQt6 Garmin GPS visual navigator
│   ├── codegps.py                       — PyQt6 repair graph GPS
│   ├── codegps_map.py                   — Tkinter map with 3 views
│   ├── gen_gps_svg.py                   — SVG generation for GPS
│   └── Config.py                        — Color, Font, Style, Theme (ROAD color = #3B4D63)
│
├── dom_compression/
│   └── ingest_graph_code.py             — Ingest graph code into v20_hybrid_best.db
│
├── Cascade_toolStack/
│   ├── ingest_codebase.sql              — SQL schema for codebase ingestion
│   └── vbast/
│       ├── bcl_stamper.c                — C binary for BCL stamping
│       └── dom_unified.py               — Unified AST wrapper (vbast C binary)
│
└── MySQL vb_code_test                   — Production database
    ├── bcl_codebases (2)                — Registered codebases
    ├── bcl_files (54)                   — Ingested files
    ├── bcl_classes (63)                 — Classes
    ├── bcl_methods (655)                — Methods with features
    ├── bcl_units (24)                   — Computational units
    ├── bcl_edges (4,147)                — Code graph edges
    ├── bcl_stamps (1)                   — Reasoning stamps
    ├── vb_classes (1,394)               — Simplified class registry
    └── vb_methods (13,818)              — Simplified method registry
```

---

## The Garmin Principle — Pipelines Are the Roads

> **VITAL CONCEPT:** The CodeGPS Garmin navigator visualizes pipelines as roads.
> The pipelines ARE the roads. Without pipelines, the Garmin has no roads to navigate.
> Without the Garmin, the pipelines have no navigation aid.
>
> This concept MUST be captured in the Garmin's help/config file.

### How the Garmin Maps to Pipelines

| Garmin Concept | Pipeline Reality |
|---|---|
| **Road** | A pipeline (Code→DB, Chat Ingestion, Utilities, Error Capture, BCL Code Graph) |
| **Destination** | A pipeline stage (INGEST, PARSE, COMPILE, EXPORT, VERIFY) |
| **Green road** | Pipeline stage that succeeded (no errors, all checks pass) |
| **Red road** | Pipeline stage that failed (errors, violations, broken output) |
| **Yellow road** | Pipeline stage partially complete (warnings, partial success) |
| **Dashed gray road** | Pipeline stage not yet built / unexplored |
| **Cascade robot** | The AI agent driving along the roads |
| **Trip history** | Pipeline execution log (what ran, when, result) |
| **Telemetry graph** | Live pipeline metrics (violations found, errors, success rate) |
| **Map views** | Different pipeline perspectives (Repair, Plan, Error) |
| **Route confidence** | learned_rules confidence score for a fix path |

### The 6 Roads (Pipelines) on the Garmin Map

```
                    ┌──────────────────────────┐
                    │   CODEGPS GARMIN MAP     │
                    ├──────────────────────────┤
                    │                          │
                    │  Road 1: Code→DB         │
                    │  ├── INGEST (green)      │
                    │  ├── GRAPH (green)       │
                    │  ├── REASON (gray)       │ ← not built
                    │  ├── VALIDATE (green)    │
                    │  ├── REPAIR (green)      │
                    │  ├── EXPORT (green)      │
                    │  └── VERIFY (green)      │
                    │                          │
                    │  Road 2: 8-Graph         │
                    │  ├── Plan (green)        │
                    │  ├── Spec (green)        │
                    │  ├── Flow (green)        │
                    │  ├── Lifecycle (green)   │
                    │  ├── Dep (green)         │
                    │  ├── Error (green)       │
                    │  ├── Orch (green)        │
                    │  └── Gap (green)         │
                    │                          │
                    │  Road 3: Utilities       │
                    │  ├── Config (green)      │
                    │  ├── Scheduler (green)   │
                    │  ├── Orchestrator (green)│
                    │  └── 15 Utilities (green)│
                    │                          │
                    │  Road 4: Chat Ingestion  │
                    │  ├── Sources (green)     │
                    │  ├── Classify (green)    │
                    │  ├── Parse (green)       │
                    │  ├── Import (green)      │
                    │  ├── Embed (yellow)      │ ← optional
                    │  └── Verify (green)      │
                    │                          │
                    │  Road 5: Error Capture   │
                    │  ├── Capture (green)     │
                    │  ├── SQLite (green)      │
                    │  ├── MySQL (green)       │
                    │  ├── Prevent (green)     │
                    │  └── Auto-Apply (yellow) │ ← partial
                    │                          │
                    │  Road 6: BCL Code Graph  │
                    │  ├── Ingest (green)      │
                    │  ├── Extract (green)     │
                    │  ├── Classify (green)    │
                    │  ├── Compile (green)     │
                    │  ├── CU (green)          │
                    │  ├── Identity (green)    │
                    │  ├── Edges (green)       │
                    │  ├── Stamps (yellow)     │ ← 1 stamp
                    │  └── Projection (green)  │
                    │                          │
                    └──────────────────────────┘
```

### Garmin Help File Entry (for Config)

```
HELP_PIPELINES_ARE_ROADS:
  The Garmin navigator visualizes the system's 6 pipelines as roads.
  Each pipeline is a road. Each pipeline stage is a destination on that road.
  Road colors:
    Green  = stage succeeded (all checks pass)
    Red    = stage failed (errors, violations)
    Yellow = stage partial (warnings, optional not run)
    Gray   = stage not built yet (unexplored)

  The 6 Roads:
    1. Code→DB Road      — Files → Graph → Reason → Repair → Export → Verify
    2. 8-Graph Road      — Plan → Spec → Flow → Lifecycle → Dep → Error → Orch → Gap
    3. Utilities Road    — Config → Scheduler → Orchestrator → 15 Utilities
    4. Chat Ingestion    — Sources → Classify → Parse → Import → Embed → Verify
    5. Error Capture     — Capture → SQLite → MySQL → Prevent → Auto-Apply
    6. BCL Code Graph    — Ingest → Extract → Classify → Compile → CU → Identity → Edges → Stamps

  The Cascade robot drives along these roads. When it hits a red road,
  it learns to avoid that route next time (learned_rules).
  When it finds a green road, it remembers the successful path (bcl_stamps).

  WITHOUT PIPELINES, THE GARMIN HAS NO ROADS.
  WITHOUT THE GARMIN, THE PIPELINES HAVE NO NAVIGATION.
```

---

## Current Status

| Component | Status | Data |
|---|---|---|
| `ingest_bcl.py` (AST → SQLite) | **DONE** | — |
| `bcl_mysql_ingestor.py` (AST → MySQL) | **DONE** | 54 files, 63 classes, 655 methods |
| `bcl_extractor.py` (FeatureExtractor) | **DONE** | — |
| `BclGenerator.py` (AST → BCL headers) | **DONE** | — |
| `bcl_compiler.py` (IRCompiler) | **DONE** | — |
| `bcl_engine.py` (LEX → PARSE → VALIDATE → FIX → SERIALIZE) | **DONE** | — |
| `bcl_identity_generator.py` (4-level identity tokens) | **DONE** | — |
| `bcl_object_database.py` (SQLite object DB) | **DONE** | — |
| `bcl_projector.py` (IR → .bcl view) | **DONE** | — |
| `BclStampBuilder.py` (reasoning stamps) | **DONE** | 1 stamp |
| `BclStampStore.py` (stamp CRUD) | **DONE** | — |
| `ingest_graph_code.py` (graph code → v20) | **DONE** | — |
| MySQL `vb_code_test` | **DONE** | 2 codebases, 4,147 edges |
| MySQL `vb_classes` / `vb_methods` | **DONE** | 1,394 classes, 13,818 methods |
| CodeGPS Garmin (`codegps_garmin.py`) | **DONE** | PyQt6 visual navigator |
| CodeGPS Map (`codegps_map.py`) | **DONE** | Tkinter 3-view map |
| Garmin help file entry | **NOT BUILT** | Needs to be added to Config |
| Pipeline-as-road mapping in Garmin | **NOT BUILT** | Garmin currently shows repair routes, not pipeline stages |
