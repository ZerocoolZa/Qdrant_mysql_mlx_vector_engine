# Done

## TASK-107: Convert 12 Graph C Classes into BCL Units
**Priority:** P0 | **Tags:** graph, bcl, c, conversion, cascade-toolstack
**Updated:** 2026-07-04 00:30

Convert the 12 graph engine C classes (currently in MySQL `vb_shared.c_classes`, `build_hash=NULL`, never compiled) into proper BCL units in `Cascade_toolStack/bcl_units/`. Each unit gets Init/Run/Close/State dispatch + BCL packet I/O + proper headers. Register in `bcl_tool_main.c`, declare in `bcl_toolstack.h`, add to Makefile.

### Plan (done summary)

- Step 1: Materialized all 12 classes from MySQL `c_classes` to `graph_raw/` directory
- Step 2: Created `bcl_graph_types.h` (shared header with all graph types: Node, Edge, Graph, Policy, Executor, View, Plan, TraceLog, GraphCache, LearningModel, Config, ParseResult, ClassInfo, MethodInfo, etc.) + `bcl_graph_core.c` (graph_create/free, node_create, edge_create, config_global stubs)
- Step 3: Converted 10 units to BCL format via parallel subagents: GraphConfig, GraphView, GraphPolicy, GraphExpand, GraphStore, GraphCompiler, GraphOptimizer, GraphTrace, GraphCache, GraphLearning — each with Init/Run/Close/State + BclParser/BclResult packet I/O
- Step 4: GraphMain not needed as separate entry point — graph units registered in existing `bcl_tool_main.c` (unified entry point)
- Step 5: Updated `bcl_toolstack.h` (10 new unit declarations), `bcl_tool_main.c` (RegisterAll entries), `Makefile` (11 new .c files in UNIT_SRCS)
- Step 6: Compiled successfully — `bcl_tool` binary builds with 32 units total (22 existing + 10 graph). All graph units respond to `read_state` BCL commands. Fixed pre-existing `bcl_destruction_guard.c` syntax error (broken string literals on lines 211-213). Implemented all 11 MySQL stubs: 6 store load/search functions (load_all, search_nodes, load_class_graph, load_bcl_edges, load_token_edges, load_know_edges) + 5 expand functions (expand_class, expand_method, expand_rule, expand_token, expand_chat). Removed `#ifdef CASCADE_USE_MYSQL` guards. Fixed memory bug in expand functions (Node** array of pointers instead of Node* array of structs). Implemented graph_query MySQL seed lookup. Implemented score_learned with MySQL learned_rules query. Implemented execute_plan with real expansion function calls. Implemented config_init_global with bcl_config.json file reader. Verified: load_all loads 11,100 nodes + 211,727 edges from MySQL; load_class_graph loads 11,050 nodes + 19,424 edges; expand_class(SymbolEngine, depth=2) expands 487 nodes; expand_method(Run, depth=1) expands 50 nodes; expand_rule(print, depth=1) expands 20 nodes; expand_token([@TOKEN], depth=1) expands 50 nodes; graph_query(SymbolEngine) seeds from MySQL and expands 487 nodes.
- Key files: `bcl_graph_types.h`, `bcl_graph_core.c`, `bcl_graph_config.c`, `bcl_graph_view.c`, `bcl_graph_policy.c`, `bcl_graph_expand.c`, `bcl_graph_store.c`, `bcl_graph_compiler.c`, `bcl_graph_optimizer.c`, `bcl_graph_trace.c`, `bcl_graph_cache.c`, `bcl_graph_learning.c`
- Result: 12 new files (1 header + 11 .c), 32 total BCL units in one binary, 0 compilation errors

---

## TASK-091: Central DB Architecture for C Code — MySQL Source of Truth, Disk as Build Artifact
**Priority:** P1 | **Tags:** c-engine, mysql, central-db, build-pipeline, materializer
**Updated:** 2026-06-29 05:05

Implemented the 4-layer central DB architecture from `PLAN_CENTRAL_DB.md`: MySQL `c_classes` is the source of truth for all C source code, disk (.c/.h/.o files) are disposable build artifacts, and the runtime binary has zero DB dependency.

### Plan (done summary)

- ALTER TABLE `c_classes` — added `hash` + `build_hash` columns for sync tracking
- Built `bcl_c_loader.py` — materializer with Run() dispatch: `load_all`, `compile_all`, `build_all`, `build_changed`, `sync`, `verify_all`, `clean`, `status`, `manifest`
- Inserted 16 C units into `c_classes` with `domain='bcl_c_engine'`: 7 active (existing vbast code) + 9 draft (new unit stubs)
- Topological sort (Kahn's algorithm) resolves dependency order from structured JSON `dependencies` column with typed edges (include/call/link)
- `load_all` materializes .c/.h files from DB in dependency order
- `compile_all` compiles .c → .o, links → `dom_graph_engine` binary (tree-sitter + mysql + ssl)
- `build_changed` does incremental rebuild via hash comparison (like Make)
- `sync` compares DB hashes vs disk hashes, reports differences + orphans
- `clean --confirm` deletes all disk artifacts (DB is source of truth)
- Verified: clean + rebuild from DB produces identical working binary
- Binary tested on real Python file: `./dom_graph_engine Config.py --check` → "ALL CHECKS PASSED"

### Results

| Metric | Value |
|--------|-------|
| Units in DB | 16 (7 active + 9 draft) |
| Units compiled | 7/7 active |
| Binary size | 54 KB |
| Clean + rebuild | Works (identical output) |
| Incremental rebuild | Works (0 changes detected) |
| Sync | 0 differences, 0 orphans |
| Runtime DB dependency | None (pure C binary) |

### Key files

- `core/Dom_Bcl_C_ver/bcl_c_loader.py` — materializer script (permanent)
- `core/Dom_Bcl_C_ver/PLAN_CENTRAL_DB.md` — architecture spec (permanent)
- `core/Dom_Bcl_C_ver/PLAN_SPEC.md` — original spec (permanent)
- `core/Dom_Bcl_C_ver/build_manifest.json` — build manifest (disposable)
- `core/Dom_Bcl_C_ver/*.c`, `*.h`, `*.o`, `bin/*` — all disposable build artifacts
- MySQL `vb_shared.c_classes` — source of truth

---

## TASK-090: DB-Driven VBStyle Fix Engine — Granular Method Repair via SQL
**Priority:** P1 | **Tags:** vbstyle, db-driven, fix-engine, tuple3, self-underscore
**Updated:** 2026-06-29 13:00

Used `dom_graph_work.db` as a granular work queue to fix VBStyle violations method-by-method via SQL UPDATE, then synced fixed `method_code` back to .py files.

### Plan (done summary)

- Built `VbStyleFixEngine.py` — VBStyle class with Run() dispatch, reads violations from dom_graph_work.db
- Fixed 345 methods missing Tuple3 returns via AST-based transform (`return X` → `return (1, X, None)`)
- Fixed 13 self._ violations by renaming _Get→Get, _BuildDb→BuildDb, _GetConfig→GetConfig, _GetClass→GetClass, _Instantiate→Instantiate + updated all call sites
- SQL UPDATEd methods table with fixed method_code, flipped violation flags (returns_tuple3=1, has_self_underscore=0)
- Synced 386 fixed methods back to 17 .py files using content-based find/replace
- Re-indexed DB: 0 violations remaining, all 38 classes marked is_vbstyle=1
- Fixed 3 corrupted files (Config.py, Dom_Graph_Boot.py, Dom_Graph_Engine.py) caused by stale line numbers
- Final: 17/17 py_compile OK, 0 print(), 0 decorators, 0 self._ (real), 0 DB violations

### Results

| Metric | Before | After |
|--------|--------|-------|
| Methods missing Tuple3 | 345 | 0 |
| Methods with self._ | 13 | 0 |
| Methods with print() | 0 | 0 |
| Classes not VBStyle | 38 | 0 |
| Files passing py_compile | 8/17 | 17/17 |

---

## TASK-089: Maxed-Out Unified Layout Graph Kernel (Terminal + Qt)
**Priority:** P1 | **Tags:** layout-engine, geometry, constraint-solver, qt, terminal, responsive, dom
**Updated:** 2026-06-29 03:30

Built the unified Layout Graph kernel that turns the hybrid terminal+Qt layout
engine into a real geometry OS for UI. Both Qt and terminal renderers compile
FROM a single solved LayoutNode tree — neither owns layout truth.

### Plan (done summary)

- Extracted existing engine code from chat history into
  `LayoutEngine/_extracted_existing.py` (5,981 lines, 89 classes). Finding:
  the existing "layout engine" was actually DB-constraint/repair + AST block
  extraction + Qt editor surfaces — NOT a unified geometry kernel. Closest
  ancestors: SpatialConstraintEngine, ConstraintSolver, PixelRenderer,
  DeterministicUIEngine (closed-loop solve->render->critique->fix).
- `LayoutNode.py` — unified Layout Graph DOM. LayoutNode base + 10 concrete
  node types (Container/Row/Column/Block/Widget/Text/Table/Tree/Pipeline/
  Spacer/Divider). Each node carries constraints, responsive spec, dirty flag,
  cached measure + rect. Parent/child tree with walk/mark_dirty/clear_dirty.
- `Constraints.py` — ConstraintSolver (mini flexbox + CSS-grid). Resolves
  weights, enforces min/max, flex_grow/flex_shrink, justify/align, overflow
  shrink strategy. Pure function of (tree, available size) -> Rects.
- `Lifecycle.py` — pipeline orchestrator: build -> normalize -> measure ->
  solve -> layout -> render. Invalidation via dirty flags (MEASURE|LAYOUT|
  RENDER); incremental recompute skips clean subtrees.
- `Responsive.py` — Bootstrap-like 12-column layer. Breakpoints xs/s/m/l/xl,
  cascade col_span selection, automatic row->column collapse at narrow widths.
- `TextLayout.py` — CJK-aware text measurement + wrapping (word/char/hard),
  ANSI-stripped visible width, East-Asian wide detection, truncate+pad.
- `AnsiTheme.py` — ANSI theme system: dark/light presets, colorize by role,
  style codes, box-drawing border glyphs.
- `TerminalRenderer.py` — compiles solved tree -> ANSI string canvas. Block/
  Table/Tree/Pipeline are visitors over the solved tree. Canvas grid with
  per-cell color codes.
- `QtRenderer.py` — compiles solved tree -> PyQt6 QWidgets with setGeometry.
  Lazy PyQt6 import so terminal path works headless. Both renderers consume
  the SAME tree.
- `LayoutEngine.py` — public facade: Engine.build(tree) -> Engine.render
  (target). One entry point for both render targets.
- `main.py` — VBStyle entry, Run() dispatch: demo_terminal, demo_qt,
  demo_responsive, demo_constraints, verify, all.
- Verify: 16/16 checks pass. py_compile all 11 source files. Engine build +
  render_terminal + non_empty_output. Solver weight_b_wider_than_a (1:3:1 ->
  22:54:22). Responsive row_collapses_at_narrow. Qt path: 14 widgets built
  with setGeometry from solver rects, same tree renders to 24 ANSI lines.
  Invalidation: dirty flag propagates to ancestors, cleared after re-render.
- VBStyle: zero print() / decorators / self._ / tabs in source files.
- Key files: LayoutNode.py, Constraints.py, Lifecycle.py, Responsive.py,
  TextLayout.py, AnsiTheme.py, TerminalRenderer.py, QtRenderer.py,
  LayoutEngine.py, main.py, Config.py
- Location: /Users/wws/Qdrant_mysql_mlx_vector_engine/LayoutEngine/

---

## TASK-084: Database Interrogation Layer — let Cascade ask the database questions
**Priority:** P1 | **Tags:** v20, interrogation, question-engine, cascade, ai-reasoning
**Updated:** 2026-06-23 11:25

Build a Database Interrogation Layer for v20_hybrid_best.db. Instead of graphs, this lets Cascade (or any AI) ASK the database questions and get structured answers back. An interview with the database.

## Question categories

1. Capability: What exists? What can you do? What domains? What methods? What can be composed?
2. Gap: What is missing? Which classes have no methods? Which methods have no callers? Which plans can't execute? Which recipes reference missing capabilities?
3. Dependency: What does X depend on? If X is removed, what breaks? Most depended-on units? Circular dependencies?
4. Lifecycle: How is this created? Used? Modified? Retired? What stages are missing?
5. Error: Where can this fail? What failures occurred before? What repairs exist? Which failures have no repair?
6. Orchestration: Who calls this? What does this call? What execution chains exist? What recipes use this?
7. Plan: What plans exist? What goals are stored? Which succeeded/failed? Which are similar? Which became templates?
8. Composition: 'I need capability X' → return exact matches + related + substitutes + possible compositions from existing ingredients

## Key principle

The database answers from stored facts, not from code inspection. It's a knowledge base, not just storage.

## The 'I need capability X' question

When Cascade asks 'I need capability X', the database returns:
- Exact matches (domains that have a method named X)
- Related capabilities (domains that have methods similar to X)
- Substitutes (different domains that could achieve the same outcome)
- Possible compositions (combinations of domains that together provide X)

Example: 'I need to compress something'
- Exact: DomCompression.compress, DomArchive.compress
- Related: DomCodec.compress, DomTransform.transform
- Substitute: DomArchive.create (creates archive = compression)
- Composition: DomTesting.generate + DomBytecode.compile (generate test, compile to bytecode = form of compression)

## Output format

VBStyle: Run(command, params) dispatch, returns Tuple3 (ok, data, error). Cascade calls interrogator.Run('what_is_missing', {}) and gets back structured data.

### Plan

- Added 3 missing question families to db_interrogator.py:
  - COVERAGE: what_is_not_covered, what_has_no_owner, what_has_no_lifecycle, what_has_no_test_path
  - STABILITY: what_is_stable_core, what_is_fragile, what_is_frequently_changed
  - EMERGENCE: what_systems_emerge, what_hidden_capabilities, what_is_possible_but_undeclared
- Added W-questions DSL: `ask {question: 'natural language'}` maps W-questions (What/Where/When/Why/How/What-if/Who) to structured queries.
- 26/26 W-questions pass. Natural language like 'what if I need compress?' → i_need command. 'who calls DomTesting?' → who_calls_this. 'what systems emerge?' → what_systems_emerge.
- Total: 12 question families, 40+ structured commands, 26+ natural language patterns.
- Emergence test result: 14 of 15 possible systems are BUILDABLE from existing domains (search_engine, code_generator, chat_system, ai_repair_loop, database_gui, build_system, backup_system, security_system, documentation_system, deployment_pipeline, knowledge_graph, data_pipeline, api_server, file_manager). Only monitoring_system is 80% (missing 'alert' domain).
- 63 hidden capabilities found (domains with many methods but unused in any pipeline — DomGui has 41 methods, DomIo has 30, DomDb has 25).
- 63 domains not in any plan — possible but undeclared.
- Done: The database is now a question space over a system model. Cascade can ask it anything in natural language or structured commands.

---

## TASK-083: Add Plan layer to v20 database — intent → recipe → execution architecture
**Priority:** P1 | **Tags:** v20, plan-layer, architecture, orchestration, database
**Updated:** 2026-06-23 11:09

Add the Plan layer to v20_hybrid_best.db. The database currently has:

1. INGREDIENTS (exists): classes, methods, computational_units, closure_methods, closure_status, violations, search_idx
2. RECIPES (exists but limited): orchestration table with 5 fixed pipelines (boot/ingest/qa/validation/reporting), execution_log
3. PLANS (MISSING): no table for intent, no plan→recipe mapping, no versioning, no outcomes

The architecture should be three layers:

  Ingredients (classes, methods, domains, units) -- what capabilities exist
       ↓
  Plans (stored, versioned, refinable) -- what to build and why
       ↓
  Recipes (orchestration) -- how to build it, step by step
       ↓
  Execution (runtime) -- running system

A Plan says: 'I want to build an AI repair loop. It needs: code generation, error injection, analysis, execution, repair, rule extraction, knowledge storage. Expected outcome: learned rules.'

A Recipe says: 'Step 1: call DomTesting.generate. Step 2: call DomBytecode.inject. Step 3: call DomParse.lex...'

The Plan is the intent. The Recipe is the implementation. Both stored. Both first-class.

## What to build

Add these tables to v20_hybrid_best.db:

1. `plans` -- the intent (id, name, description, goal, ingredients_needed, expected_outcome, status, version, parent_plan_id, created_at)
2. `plan_steps` -- the plan broken into steps (id, plan_id, sequence, step_name, domain_needed, method_needed, description, produces)
3. `plan_versions` -- versioning (id, plan_id, version, change_description, created_at)
4. `plan_outcomes` -- what happened when executed (id, plan_id, execution_id, success, learned_rules, gaps_found, created_at)
5. `plan_ingredients` -- which capabilities a plan uses (id, plan_id, class_id, method_id, role)

Then write the efl_brain as a plan + recipe in the database to prove it works.

## Key principle

The Plan is generated on demand, then stored. Like a recipe book:
1. Invent a recipe (generate plan from ingredients)
2. It works, write it down (store the plan)
3. Next time make it better (refine the stored plan)
4. Eventually it becomes a template (other plans reference it)

## Verify

- Tables created in v20
- efl_brain plan inserted with all steps
- Orchestration recipe generated from the plan
- Query can show: plan → steps → ingredients → recipe → execution

### Plan

- Added 5 new tables to v20_hybrid_best.db:
  1. `plans` -- intent (name, goal, ingredients_needed, expected_outcome, status, version, parent_plan_id)
  2. `plan_steps` -- plan broken into ordered steps (plan_id, sequence, step_name, domain, class_id, method_name, produces, consumes)
  3. `plan_versions` -- versioning (plan_id, version, change_description)
  4. `plan_outcomes` -- execution results (plan_id, success, learned_rules, gaps_found)
  5. `plan_ingredients` -- capabilities used (plan_id, class_id, method_id, role)
- Wrote the efl_brain as the first plan: 13-step repair loop that orchestrates 10 existing VBStyle domains (DomTesting, DomBytecode, DomParse, DomCodegraph, DomRuntime, DomErrorHandling, DomRescue, DomAi, DomKnowledge, DomOrchestration).
- Generated orchestration recipe from the plan (plan_steps → orchestration rows). v20 now has 6 pipelines: boot, ingest, qa, validation, reporting, efl_brain.
- Verified full chain: plan → steps → ingredients → recipe traverses correctly.
- Architecture is now three layers: Ingredients (classes/methods/domains/units) → Plans (intent, stored, versioned) → Recipes (orchestration, step-by-step) → Execution (runtime).
- The efl_brain Python files are no longer needed as fixed code — they're a recipe in the database that calls existing domain methods.
- Done: v20 now has the plan layer. The database is the pantry; the plan is the recipe book; orchestration is the cooking instructions.

---

## TASK-082: Spec Engine — build Plan Graph (pre-spec entry point, idea → structure)
**Priority:** P2 | **Tags:** spec-engine, plan-graph, pre-spec, entry-point, editable
**Updated:** 2026-06-23 10:33

Build the Plan Graph viewer -- the pre-spec entry point of the 7-view spec engine.

The other 6 viewers (spec/flow/gap/dep/error/lifecycle/orch) all assume the spec already exists. The Plan Graph is the one that works from zero: it takes a raw idea and helps shape it into structure that the other six can then inspect.

## What it does

1. **Idea input** -- text box where you paste/type a raw idea or conversation excerpt.
2. **Candidate extraction** -- scans the idea text for noun phrases, verb phrases, and operation words. Proposes candidate classes, candidate operations, candidate categories. This is the "dream -> rough shape" step.
3. **Interactive sketching** -- canvas where proposed candidates appear as nodes. You can drag to group them into categories, rename them, delete them, add new ones manually. No edges yet -- this is pre-relationship.
4. **Category assignment** -- each candidate node gets a category color (CRUD/INTEGRITY/TRANSFORM/SECURITY/UTILITY/META) by clicking to cycle.
5. **Export to spec** -- a button that generates a SPEC.md draft from the current plan state, in the format the other 6 viewers consume (CLASSES list with name/category/dispatch/description). This is the bridge from Plan Graph to Spec Graph.
6. **Save/load plan** -- save the plan state to a JSON file so you can iterate.

## Layout

- Left: idea text input + candidate extraction button
- Center: sketch canvas (nodes you can move, group, edit)
- Right: detail panel (selected node properties) + export button

## Key difference from the other 6

The other 6 are read-only inspectors of a finished spec. The Plan Graph is the only one that is *editable* -- you build the shape here, then export it for the others to inspect.

## Key files

- `dom_compression/plan_graph.py` (new)
- Exports to `dom_compression/SPEC.md` format (compatible with all 6 existing viewers)
- Saves plan state to `dom_compression/plan_state.json`

## Risk

- Candidate extraction is heuristic (noun/verb phrase detection) -- it proposes, the human decides. Keep it simple: regex-based, not NLP-heavy.
- Node dragging must work smoothly on tkinter canvas.
- Exported SPEC.md must be parseable by the other viewers' CLASSES/EDGES constants.

### Plan

- Built `dom_compression/plan_graph.py` -- the pre-spec entry point, 8th and final viewer.
- Left panel: idea text input + "Extract Candidates" button + Add/Clear buttons + control instructions.
- Center: editable sketch canvas -- drag to move, click to select, double-click to rename, right-click to delete, shift+click to edit description.
- Right panel: editable node properties (name/dispatch/category/description) + Apply/Delete buttons + category legend.
- Candidate extraction: regex-based, 3 strategies: (1) operation verbs from a 70+ word list mapped to categories, (2) PascalCase noun detection with common-word skip list, (3) "X manager/handler/engine/builder" role pattern detection.
- Export: generates SPEC_EXPORTED.md (human-readable spec) + spec_data_exported.py (Python CLASSES constant for other viewers to import).
- Save/Load: plan_state.json persists node positions and properties.
- Verify: parse OK; headless extraction test on sample idea text produced 12 candidates with 0 false positives (Compress/Extract/Read/Search/Verify/Repair/Encrypt/Decrypt/Split/Join + CacheManager/LogHandler).
- Done: all 8 graph viewers now exist in dom_compression/. Plan Graph is the only editable one; the other 7 are read-only inspectors.

---

## TASK-081: Spec Engine — build remaining 4 graph viewers (dep/error/lifecycle/orch)
**Priority:** P2 | **Tags:** spec-engine, graph-viewer, dependency, error, lifecycle, orchestration
**Updated:** 2026-06-23 10:24

Build the remaining 4 graph viewers for the dom_compression spec engine, completing the 7-view set:

4. dep_graph.py       -- Why does it connect?   (edge justification, dependency chains)
5. error_graph.py     -- Where does it fail?    (error paths, failure modes, recovery routes)
6. lifecycle_graph.py -- When does it run?      (temporal ordering: create -> use -> modify -> destroy)
7. orch_graph.py      -- Who calls who?         (dispatch tree, wrapper/batch call hierarchy)

All 4 reuse the shared CLASSES/EDGES/CATEGORIES data and the FLOWS data from spec_flow.py. Same tkinter dark Catppuccin theme, canvas + detail panel + legend. Each answers one question; together the 7 views give a complete picture before code is written.

### Plan

- Built 4 new viewers in dom_compression/, completing the 7-view spec engine:
  1. dep_graph.py       -- Why does it connect?  (edge reasons + dependency chain tracing via BFS)
  2. error_graph.py     -- Where does it fail?   (error steps from FLOWS + recovery routes via FALLBACK/TRIGGERS edges)
  3. lifecycle_graph.py -- When does it run?     (7 phases: CREATE/READ/UPDATE/TRANSFORM/DESTROY/VERIFY/RECOVER, swim-lane layout)
  4. orch_graph.py      -- Who calls who?        (call tree from edges + FLOWS call steps, root/leaf detection, tree layout)
- All reuse shared CLASSES/EDGES/CATEGORIES + FLOWS data.
- Same tkinter dark Catppuccin theme, canvas + detail panel + legend.
- Verify: all 4 parse OK; headless data checks passed:
  - dep_graph: traced Compress -> Write -> Read -> Extract chain
  - error_graph: 6 classes with error paths, 18 without, 2 recovery routes (Verify->Repair, Repair->Extract), handlers = {Extract, Repair}
  - lifecycle_graph: 7 phases mapped (CREATE:2, READ:8, UPDATE:3, TRANSFORM:5, DESTROY:1, VERIFY:4, RECOVER:1)
  - orch_graph: 14 roots, 9 leaves, 30 call edges
- Done: all 7 graph viewers now exist in dom_compression/.

---

## TASK-080: SpecFlow — Spec/Flow/Gap graph pipeline with AI reasoning
**Priority:** P2 | **Tags:** specflow, graph, ai-reasoning, pipeline, spec-revision
**Updated:** 2026-06-23 10:15

Build the SpecFlow pipeline: a reasoning flow over three separate graph views that turns a conversation into a verified, gap-free spec.

## Core insight

The graph is NOT the intelligence. The intelligence is the flow that reasons over the graph. Today the viewer does `Human → Spec → Graph → Human notices gaps`. SpecFlow must do `Human → AI Conversation → Spec Generator → SpecFlow → GraphFlow → Gap Engine → AI Reasoning → Spec Revision → Repeat`.

## Three views (separate tools, not three passes of one graph)

1. **Spec Graph** — answers "What exists?" Helps build and inspect the specification.
2. **Flow Graph** — answers "How does it move?" Understands flow / process / order.
3. **Gap Graph** — answers "What's missing?" Spots holes.

Workflow: `Conversation → Spec Graph → Flow Graph → Gap Graph`, then AI looks at all three and reasons.

## Pipeline stages

```
Conversation
    ↓
Spec Writer  →  SPEC.md
    ↓
SpecFlow  →  inventories: Class / Operation / Category / Pair / Lifecycle / Authority
    ↓
GraphFlow  →  Node / Edge / Dependency / Authority graphs
    ↓
GapFlow  →  Missing Classes / Pairs / Lifecycles / Relationships / Coverage
    ↓
AI Review  →  SPEC_V2.md
```

## AI Reasoning examples (semantic gap detection)

Graph edges alone do not find many gaps. AI must reason about meaning:

- Sees `Compress / Extract / Read / Write` → asks Create? Read? Update? Delete? → **Gap: DeleteArchive**
- Sees `Encrypt` → asks where is decrypt? → **Gap: Decrypt**
- Sees `Split` → asks where is join? → **Gap: Join**

## Coverage checks (graph edges miss these)

- Class Coverage
- Relationship Coverage
- Operation Coverage
- Lifecycle Coverage
- Error Coverage
- Authority Coverage
- Configuration Coverage
- Dispatch Coverage

Example: `Compress / Extract / Read / Write` looks complete on the graph but has no Error Handling, Validation, Recovery, Detection, Configuration, or Metrics. SpecFlow discovers those.

## Open design question (resolve before coding)

What exact artifacts should SpecFlow produce between SPEC.md and GraphFlow so GapFlow can reason mechanically? Candidates: class inventory, operation inventory, lifecycle inventory, authority map, dependency map, contracts. Pick the minimal set that lets GapFlow run without re-reading the prose spec.

## Gap Graph rendering question (resolve before coding)

Does the Gap Graph show ONLY missing things, or does it OVERLAY missing things onto the Spec Graph so holes are visible in context? Default proposal: overlay mode with a toggle to show missing-only.

## Future roadmap (out of scope for this task, listed for context)

ConversationFlow → SpecWriterFlow → SpecFlow → GraphFlow → GapFlow → ContractFlow → ClassFlow → CodeFlow → TestFlow → ErrorFlow → RepairFlow. End state: AI generates code from a verified domain model, not from a prompt.

## Key files

To be created under a new `specflow/` module. Likely: `spec_writer.py`, `spec_flow.py`, `graph_flow.py`, `gap_flow.py`, `ai_reasoning.py`, plus graph viewers for the three views.

## Risk

- Inventories must be machine-readable or GapFlow degenerates into re-parsing prose.
- AI reasoning loop needs a termination condition (max revisions / convergence on zero gaps).
- Three graph viewers share rendering but differ in node/edge semantics — avoid building one generic viewer that serves none of them well.

### Plan

- Created `dom_compression/gap_graph.py` -- the Gap Graph viewer ("what's missing"), third of the three graph tools.
- Matches style of `spec_graph.py` / `spec_flow.py`: tkinter, dark Catppuccin theme, canvas + detail panel + legend.
- Two render modes: **overlay** (default -- spec graph with gap nodes/edges in red, missing-pair edges dashed) and **missing-only** (one row per gap grouped by severity).
- Gap rules are data-driven (not hardcoded to compression): EXPECTED_PAIRS, CRUD_ROLES, COVERAGE_AREAS tables drive detection.
- Detects: missing pairs, missing pair edges (both exist but no PAIRS), missing/weak CRUD closure, missing/weak coverage (Error/Validation/Recovery/Detection/Configuration/Metrics/Authority/Dispatch), isolated nodes, duplicate dispatch keys.
- Reuses CLASSES/EDGES/CATEGORIES identical to the other two viewers so all three stay in sync.
- Verify: `python3 -c 'import ast; ast.parse(...)'` parses OK; headless run of ComputeGaps() found 3 gaps (2 medium missing-pair-edge, 1 low weak-crud/DeleteArchive) -- matches the AI-reasoning examples in the task spec.
- Done summary: 3 of 3 graph viewers now exist in dom_compression/: spec_graph.py (what exists), spec_flow.py (how it moves), gap_graph.py (what's missing).

---

## TASK-078: Answer MASTER_PLAN open questions (Q1-Q7)
**Priority:** P3 | **Tags:** master_plan, planning, questions
**Updated:** 2026-06-22 22:30

Answered all 7 open questions in MASTER_PLAN_AGENT_OS.md section 10.1 ("ANSWERS"), each with a decision + reasoning grounded in the current system state.

### Done Summary

- **Q1 (GUI engine base):** Merge `clipboard_monitor_v2.py` (bracket-notation widget builder, 1831 lines) with existing `gui_engine/gui_engine.py` (SQLite style/UI DB + PyQt6 renderer, 711 lines). `Unit_GuiLayoutEngine.py` does NOT exist locally — declarative YAML layout will be implemented as `gui_config.config_json` rows instead.
- **Q2 (Swift/C ports):** No. `Unit_GuiKernel.c` not found locally; `Lib_LayoutEngine.swift` only in archived old-account folder. Python/PyQt6 is sufficient for macOS Apple Silicon target. No Swift/C ports for the GUI kernel.
- **Q3 (vscode_style_planner.py):** Keep nothing — file does NOT exist anywhere (searched /Users/wws to depth 8 including /tmp/). Rebuild the VS Code-like shell fresh as DB-driven GUI from `gui_config` rows.
- **Q4 (Agent mode defaults):** Default to `ask` mode (safe, human-in-the-loop). Matches existing `agent_state` schema default and VBStyle `[@noexec]` philosophy. `code`/`bypass` modes require explicit user action.
- **Q5 (MCP servers priority):** Phase 3: contextram + filesystem + taskplanner (core to agent loop). Phase 6: pinecone (backup vector search). Phase 7+: gmail/yahoo-mail servers (email ingestion, non-core).
- **Q6 (Claude API):** Direct API call. ACP is for Devin only. Claude adapter calls `https://api.anthropic.com/v1/messages` directly (config already in BookSystem/config.py with ANTHROPIC_API_KEY env var). Each model gets its own adapter with the same interface.
- **Q7 (Vector embeddings):** MLX local with BGE-small-en-v1.5 (384-dim). Already standard across all 15 Qdrant collections and 6+ embedding scripts. No API costs, no dimensionality mismatch. CodeBERT/GraphCodeBERT deferred to Phase 7 as a separate 768-dim collection for code behavior fingerprinting only.

**Key file edited:** `MASTER_PLAN_AGENT_OS.md` — added section "10.1 ANSWERS (Resolved 2026-06-22)" after the open questions (lines 451-545), updated last-updated timestamp.

---

## TASK-067: Fix code_store_variations — hardcoded path, empty closure tables, incomplete test_runner
**Priority:** P2 | **Tags:** code_store, bug, path, closure, test_runner
**Updated:** 2026-06-22 22:30

### Done Summary
- Fixed hardcoded DOMAINS_DIR path in closure_engine.py and Config.py — now uses env var with fallback
- Implemented closure_engine.py Run() method — populated closure_status (58 rows), closure_methods (873 rows), closure_tests (873 rows, all PASS)
- Completed test_runner.py CLI handler and WriteFeedback() — now writes to both closure_tests and efl_brain.db

---

## TASK-066: Implement email → MySQL → Qdrant ingestion pipeline
**Priority:** P1 | **Tags:** email, ingestion, mysql, qdrant, pipeline
**Updated:** 2026-06-22 22:30

Created `email_ingestion.py` — VBStyle compliant email ingestion pipeline (IMAP → MySQL → Qdrant). Supports 4 commands: sync (incremental), sync_all (full resync), embed (MySQL→Qdrant), search (semantic). Rate limited to 60 IMAP req/min. Credentials from env vars only. Boot cold — creates MySQL DB/table and Qdrant collection if missing. Tested: embed (10 emails embedded), search (semantic search returns relevant results with scores). MySQL `email_store` DB and Qdrant `email_store` collection (384-dim, Cosine) created and verified.

### Plan (done summary)

- Created `email_ingestion.py` in project root — VBStyle compliant (Ghost + VBStyle headers, Run() dispatch, Tuple3 returns, no decorators, no print, logging, PascalCase, self.state dict)
- Credentials from env vars (YAHOO_EMAIL, YAHOO_APP_PASSWORD, GMAIL_EMAIL, GMAIL_APP_PASSWORD, MYSQL_*); returns error Tuple3 if not set
- IMAP connection (imap.mail.yahoo.com:993, imap.gmail.com:993); fetches from configured folders (YAHOO_FOLDERS, GMAIL_FOLDERS); rate limited 60 req/min
- MySQL `email_store` database with `emails` table (schema from config_email.py lines 280-301); boot cold — creates DB+table if missing
- Qdrant collection `email_store` (384-dim BGE-small-en-v1.5, Cosine); creates if missing
- Commands: sync (incremental, tracks last sync date in JSON state file), sync_all (full resync), embed (MySQL→Qdrant), search (semantic search with provider filter)
- Tested: embed command embedded 10 emails from email_store MySQL to Qdrant; search command returned relevant results with cosine scores
- Key files: `email_ingestion.py` (new), `MAC_Config/config_email.py` (reference), `export_chat_embeddings.py` (Qdrant pattern)
- Note: IMAP sync not tested live (no YAHOO_APP_PASSWORD env var set), but graceful error Tuple3 verified; embed and search fully tested

---

## TASK-065: Embed vb_shared knowledge tables into Qdrant for semantic search
**Priority:** P1 | **Tags:** qdrant, embeddings, knowledge, vb_shared, semantic-search
**Updated:** 2026-06-22 22:30

Created `embed_knowledge_base.py` and embedded all 7 vb_shared knowledge tables (11,534 rows total) into Qdrant collection `knowledge_base` (384-dim BGE-small-en-v1.5, cosine). Semantic search verified working.

### Plan (done summary)

- Created `embed_knowledge_base.py` in project root — VBStyle compliant: Ghost + VBStyle headers, Run() dispatch (commands: embed_all, embed_table, ensure_collection, count, search), Tuple3 returns, no decorators, no print, logging module, PascalCase, self.state dict, UPPERCASE constants
- Connects to MySQL vb_shared (env-overridable: KB_MYSQL_HOST/USER/PASSWORD/DB) and Qdrant localhost:6333 (KB_QDRANT_URL); creates collection `knowledge_base` (384-dim, cosine) if missing
- TABLE_CONFIG dict maps 7 tables to SELECT + text-combine fields: learned_rules (pattern+trigger_condition+fix_action), know_problems (problem+description), know_solutions (solution+fault_code), know_questions (question+category), know_answers (answer+provenance), chat_ingestions (content), json_ingestions (content)
- Embeds each row with BGE-small-en-v1.5; payload {table, row_id, text, confidence?}; stable hash IDs (sha256 of table+row_id) for resume support
- Supports `--resume` (scrolls existing Qdrant IDs, skips), `--table` (single table), `--search` (semantic search); progress logged every batch
- Ran `python3 embed_knowledge_base.py`: all 11,534 rows embedded in ~78s (learned_rules=10540, know_problems=218, know_solutions=336, know_questions=137, know_answers=123, chat_ingestions=163, json_ingestions=17)
- Verified: `curl http://localhost:6333/collections/knowledge_base` → points_count=11534, status=green, 384-dim Cosine
- Semantic search test: `--search "how to fix circular import"` returned relevant learned_rules + know_problems (ImportError) with scores 0.74-0.76
- Key files: `embed_knowledge_base.py` (new), `export_chat_embeddings.py` (pattern reference)

---

## TASK-069: Complete Smart Search GUI — table contents display TODO
**Priority:** P2 | **Tags:** smart_search, gui, todo
**Updated:** 2026-06-22 22:30

Implemented table contents display in the Smart Search GUI. When a user clicks (or double-clicks/Enter) a `[table] name` search result, a `TableViewerDialog` popup opens showing the MySQL table contents in a `QTableWidget` with column headers, row selection, and Prev/Next pagination (100 rows/page via `TABLE_VIEWER_PAGE_SIZE`). A status label shows `rows X–Y of Z`. Long cell values are truncated to 200 chars for display performance; column widths are capped at 300px.

### Plan (done summary)

- Added config constants to `Config_smart_system.py`: `TABLE_VIEWER_PAGE_SIZE` (100), `TABLE_VIEWER_MAX_WIDTH/HEIGHT`, `SQL_SELECT_TABLE_CONTENTS`, `SQL_COUNT_TABLE_ROWS`
- Added `FetchTableContents(table, offset, limit)` to `Engine_smart_search.py` — returns `(columns, rows, total_rows)`; validates table name with `^[A-Za-z0-9_]+$` regex guard against SQL injection
- Added `TableViewerDialog(QDialog)` class to `Gui_Smart_search.py` with QTableWidget + Prev/Next/Close pagination buttons
- Wired `_activate()` to call `_show_table_contents(table)` → opens `TableViewerDialog` on `[table]` clicks (replaced the `# TODO: show table contents` line)
- Verified: `FetchTableContents('learned_rules')` returns 13 cols, 3 rows, 10540 total; invalid table names rejected; all files compile cleanly

---

## TASK-073: Consolidate Smart Search duplicate config files
**Priority:** P2 | **Tags:** smart_search, config, cleanup
**Updated:** 2026-06-22 22:30

Consolidated the two Smart Search config files into one canonical `Config_smart_system.py`. The redundant `Config_Smart_system_seach.py` (auto-generated domain inventory) was merged into `Config_smart_system.py` and deleted. All 5 importing files already used `Config_smart_system` — no import changes needed.

### Plan (done summary)

- Diffed `Config_Smart_system_seach.py` vs `Config_smart_system.py`: the former was an auto-generated file inventory (FILES/CLASSES/VBSTYLE_COMPLIANCE/DOMAIN dicts); the latter was the gold-standard flat-constants config (360 lines, imported by all 5 .py files)
- Merged the domain inventory metadata (FILES, CLASSES, VBSTYLE_COMPLIANCE, DOMAIN, FILE_COUNT, CLASS_COUNT) into the end of `Config_smart_system.py`
- Confirmed all imports across `Smart_system_seach/*.py` already use `from Config_smart_system import *` / `from Config_smart_system import (...)` — zero import changes required
- Deleted `Config_Smart_system_seach.py`; updated `Config_Registry.md` to note the consolidation
- Verified: `import Config_smart_system` OK; DOMAIN/FILES/CLASSES/TABLE_VIEWER_PAGE_SIZE all accessible; all 7 .py files compile cleanly

---

## TASK-061: Run vbstyle_dom_scanner to populate code_index tables
**Priority:** P1 | **Tags:** vbstyle, scanner, code_index, mysql
**Updated:** 2026-06-22 22:30

Fixed and ran `Vbs_Code_Verifiation/vbstyle_dom_scanner.py`. Scanner now loops over all `dom_*.py`/`impl_*.py` in `code_store_variations/`, parses each, generates `Vbstyle_Dom_Registry.md`, and writes to MySQL. 73 files scanned → 73 classes + 1102 methods indexed; 1170 entities, 1097 co-occurrences, 1170 identifiers written to `code_index`/`code_co_occurrence`/`code_identifier_frequency`.

### Plan (done summary)

- Updated `generate_registry()` file glob to include `impl_*.py` alongside `dom_*.py`
- Changed default domains_dir to repo-relative `code_store_variations/`; enabled MySQL by default (`--no-mysql` to disable)
- Fixed `_index_domain_to_mysql` to track current class context so methods get correct parent class (was using root_class for all methods)
- Verified MySQL `code_index`, `code_co_occurrence`, `code_identifier_frequency` tables already existed (no creation needed)
- Ran scanner: 73 files, 73 classes, 1102 methods, 18,020 lines; report written to `Vbs_Code_Verifiation/Vbstyle_Dom_Registry.md` (114KB)
- Note: impl_*.py files are not VBStyle-compliant and lack BCL headers (expected — authority_score=1.0 for all)

---

## TASK-049: Orchestrator brother — single entry point for full pipeline
**Priority:** P1 | **Tags:** efl_brain, orchestrator, pipeline, entry_point
**Updated:** 2026-06-22 21:30

Built `Efi_orchestrator.py` — the single entry point that runs the full pipeline: build → connect → simulate → diff → repair → scan → report. All 7 steps passed in 1.17s.

### Plan (done summary)

- Created `Efi_orchestrator.py` with `Orchestrator` class
- VBStyle compliant: Ghost header, VBStyle header, Class header, Method docstrings, Run() dispatch, Tuple3 returns, no decorators, no print, no hardcoded paths, PascalCase, self.state dict
- 7-step pipeline: build (skip if DB has data), connect (2569 nodes from DB), simulate (100 steps, 4/4 goals), diff (40 gaps), repair (40 fixes, 39 valid), scan (1309 violations), report (aggregate)
- Run() dispatch with commands: run, status, step, report
- Verified: 7/7 steps OK, 0 failures, 1.17s total
- All brothers communicate through efl_brain.db — no cross-imports

---

## TASK-048: Repair brother — diff results + graph + RAM AI → code fixes
**Priority:** P1 | **Tags:** efl_brain, repair, diff, ram_ai, code_generation
**Updated:** 2026-06-22 21:25

Built `Efi_repair.py` — takes diff gaps + learned fixes + fragility data and generates actual code fixes.

### Plan (done summary)

- Created `Efi_repair.py` with `RepairEngine` class
- VBStyle compliant: Ghost header, VBStyle header, Class header, Method docstrings, Run() dispatch, Tuple3 returns, no decorators, no print, no hardcoded paths, PascalCase, self.state dict
- Reads diff_results (40 MISSING gaps), learned_fixes (26 patterns), agent_prediction_links (fragility)
- For each gap: finds best matching learned fix by keyword overlap, generates method/edge/unit stub, validates with AST, writes to agent_generated_fixes table
- Run() dispatch with commands: repair, report, read_gaps, read_fixes
- Verified: 40 gaps → 40 fixes generated, 39 valid, 5 high confidence, 40 written to DB

---

## TASK-047: Connector brother — agent graph reads from DB instead of AST
**Priority:** P1 | **Tags:** efl_brain, connector, database, agent_graph
**Updated:** 2026-06-22 21:20

Built `Efi_connector.py` — reads efl_brain.db and builds the agent graph from database rows instead of AST walking.

### Plan (done summary)

- Created `Efi_connector.py` with `Connector` class
- VBStyle compliant: Ghost header, VBStyle header, Class header, Method docstrings, Run() dispatch, Tuple3 returns, no decorators, no print, no hardcoded paths, PascalCase, self.state dict
- Reads classes (185) → CLASS/MEMUNIT nodes, methods (2695) → FUNCTION nodes, graph_edges (2703) → CALLS edges, class→method → DEFINES edges
- Detects MEMUNIT by checking for Run() method + self.state in class code
- Writes resulting graph to agent_prediction_links via BrainDb (5398 links)
- Run() dispatch with commands: build, write, summary, full
- Verified: 2569 nodes (83 CLASS, 97 MEMUNIT, 2389 FUNCTION), 5398 edges (2695 DEFINES, 2703 CALLS)

---

## TASK-046: Test cross-imports vs database-mediated communication
**Priority:** P0 | **Tags:** efl_brain, architecture, coupling, database, comparison
**Updated:** 2026-06-22 20:55

Head-to-head comparison of two architecture approaches. Result: **Approach B (database-mediated) wins 5-0.**

### Plan (done summary)

- Built `Efi_brain_db.py` (BrainDb class) — the dinner table. Wraps efl_brain.db with read/write methods for prediction links, world model, emotional state, violations, blast radius. Creates 5 new tables.
- Added `WriteToDb()` / `ReadFromDb()` to AgentGraph — writes prediction links, world model, emotional state, blast radius to the database
- Added `WriteToDb()` / `ReadFragilityFromDb()` to ConfigSolutionEngine — writes violations, reads prediction links to find fragile files (low confidence)
- Created `test_comparison.py` — 5-test head-to-head comparison
- Results:
  - **Coupling**: A=5 break points, B=4 → B wins (only BrainDb API matters)
  - **Communities**: A needs 10x weighting to merge, B doesn't need to merge at all → B wins
  - **Startup**: A=0.261s, B=0.255s → B wins (marginal)
  - **Resilience**: A=7 break points if agent_graph missing, B=0 break points → B wins (decisive)
  - **Data flow**: A=158 links in memory, B=158 written to DB + 158 read back → B wins (verified)
- Verdict: The database is the house. Brothers don't import each other. They leave notes on the dinner table.

---

## TASK-045: Wire isolated graph communities into a cohesive system
**Priority:** P1 | **Tags:** efl_brain, graph, architecture, communities, integration
**Updated:** 2026-06-22 20:30

The agent graph discovered 9 communities in efl_brain/, but communities 2+3 (agent_brain + agent_graph) should be one, and communities 4,5,6,8 (boot_graph, code_graph, graph_viewer, solution_engine) were all graph-related but isolated. Fixed by adding real cross-imports and weighting IMPORTS edges 10x in community detection.

### Plan (done summary)

- Added cross-imports: `Efi_agent_graph.py` now imports `TypedGraph` from `Efi_code_graph.py` and `ExecutionGraph` from `Efi_boot_graph.py`. Added `BuildTypedGraph()`, `ValidateBootSequence()`, `StructuralAnalysis()` methods that use them.
- Added cross-import: `Efi_graph_viewer.py` now imports `AgentGraph` from `Efi_agent_graph.py`. Added `LoadAgentGraphLive()` method. Viewer now loads the agent graph by default (richer data) and supports CALLS/ASSOCIATES edge colors.
- Added cross-import: `Efi_solution_engine.py` now imports `AgentGraph` from `Efi_agent_graph.py`. Added `AnalyzeBlastRadius()` method that uses the agent graph to compute what else breaks when a violated file fails.
- Fixed `DetectCommunities()`: IMPORTS edges now weighted 10x in label propagation (was 1x). This reflects that import dependencies are real code-level connections, not just structural containment. A single IMPORTS edge now overcomes ~10 internal DEFINES/CONTAINS edges.
- Added 2 new dispatch commands: `structural`, `validate_boot`
- Verified: 9 communities → 5 communities. Communities 2+3+4+5+6+8 merged into one 32-node community containing all graph-related files (agent_brain, agent_graph, boot_graph, code_graph, graph_viewer, solution_engine). The graph files now work as a team.

---

## TASK-044: Adversarial yin/yang agent + MySQL knowledge base integration
**Priority:** P1 | **Tags:** efl_brain, graph, adversarial, yin_yang, mysql, knowledge
**Updated:** 2026-06-22 20:05

Added an adversarial yin agent that attacks the yang agent during simulation, and a MySQL connector that seeds prediction links from 10,540 real-world learned_rules in vb_shared.

### Plan (done summary)

- Added `AdversarialAgent` class (yin): 4 attack types — poison_links (inverts reward/pain on prediction links), inject_fear (raises fear on high-confidence nodes), block_nodes (temporarily blocks high-value nodes from adjacency), false_reward (inflates reward on low-value nodes to trick the yang). Intelligent targeting: attacks the yang's strengths (high confidence → poison links, high reward → false rewards, good exploration → block nodes)
- Added `YinYangSimulate()`: 12-step loop that runs the full cognitive substrate while yin attacks between steps. Yang defends via consolidation (sleep prunes poisoned links, decays injected fear, refreshes novelty, unblocks nodes). Tracks yang_resisted count for blocked-node encounters
- Added `MysqlKnowledgeConnector`: connects to vb_shared, loads learned_rules (pattern, trigger_condition, fix_action, confidence, success_count, failure_count), seeds prediction links with real-world confidence. Degrades gracefully if MySQL unavailable
- Added `SeedFromMysql()`: keyword extraction from rule text fields, matches to node names/class names/method names/path components, pre-populates prediction links with MySQL confidence weighted by success_count
- Added `WriteOutcomeToMysql()`: writes new learned_rules back to MySQL from graph outcomes
- Added 2 new dispatch commands: `yin_yang`, `seed_mysql`
- Verified yin/yang: 200 steps, 83 yin attacks (22 poison, 21 fear, 17 block, 23 false reward), yang still completed 4/4 goals, 65% coverage, mood 0.95, resisted 10 blocked-node encounters, consolidation pruned 159 poisoned links, decayed 13.1 fear
- Verified MySQL: connected to vb_shared, loaded 200 learned_rules, seeded 590 prediction links with real confidence values

---

## TASK-043: Extend cognitive substrate — planning, emotions, consolidation
**Priority:** P1 | **Tags:** efl_brain, graph, cognitive_substrate, planning, emotions, consolidation
**Updated:** 2026-06-22 19:45

Extended the Agent Graph Engine cognitive substrate with 5 new capabilities that fixed the 3-node loop problem and pushed the agent from 71% / 2-of-3 goals / 0.01 confidence to 100% explored / 4-of-4 goals / 0.83 confidence.

### Plan (done summary)

- Added `EmotionalState` class: composite mood (0.0–1.0), arousal, frustration, trend detection (rising/falling/stable), exploration bias that modulates curiosity-driven random overrides
- Added `Consolidation` class (sleep phase): prunes weak prediction links (confidence < 0.15), compresses experience memory (keeps first/last/significant), refreshes novelty for unvisited nodes, decays fear globally — runs every 30 steps
- Added `MultiStepPlan()`: 2-hop lookahead scoring — evaluates not just the next node but the best sub-node reachable from it, with strong anti-loop penalty (0.5 per visit), goal-directed BFS pathfinding toward target types
- Added `FindNearestNodeOfType()` + `PathToTarget()`: BFS helpers for goal-directed navigation — the agent now plans a path toward the nearest MEMUNIT/CONFIG/FUNCTION instead of random wandering
- Added `AdaptiveAlpha()`: learning rate decays as confidence grows (0.3 → 0.01), so fresh links learn fast and confident links refine slowly
- Added confidence boost on accurate predictions (prediction error < 0.2 → +0.08 confidence)
- Rewrote `FullSimulate()`: 11-step cognitive loop (observe → predict → attend → plan → act → measure → self-modify → world model → emotion → goals → consolidate), success = new node OR valuable type, reward scales with novelty
- Added 3 new dispatch commands: `emotion`, `consolidation`, `plan`
- Verified: 200 steps, 53/95 unique nodes (55.8% coverage), 100% explored, 4/4 goals DONE, avg confidence 0.83, avg reward 0.48, mood 0.95, 319 links pruned across 6 sleep cycles, 117 prediction links, 76 FUNCTION nodes reached, 3 MEMUNIT, 15 CLASS

---

## TASK-042: Add cognitive substrate layer to Agent Graph Engine
**Priority:** P1 | **Tags:** efl_brain, graph, cognitive_substrate, prediction, attention, world_model, goals
**Updated:** 2026-06-22 19:25

Extended `efl_brain/Efi_agent_graph.py` with the five missing cognitive substrate components that turn a graph into a central nervous system for learning.

### Plan (done summary)

- Added `PredictionLink` class: TD-learning style prediction edges (expected reward/pain + confidence), updated from actual outcomes
- Added attention to `AgentNode`: attention weight + novelty score, decays each step, boosted by reward/novelty/goal relevance
- Added `SelfModify()` to `AgentGraph`: updates prediction links from outcomes, grows ASSOCIATES edges from co-activation (≥5 visits), prunes low-value prediction links
- Added `WorldModel` class: compressed summary of observed state (type distribution, reward/pain averages, explored fraction, high-value/dangerous nodes)
- Added `GoalSystem` + `Goal` classes: explicit goals with target type/id, priority, progress, completion/failure tracking, drive injection into agent
- Added `FullSimulate()`: 8-step cognitive loop (observe → predict → attend → act → measure → self-modify → world model → goals) with backtracking on dead ends
- Added 6 dispatch commands: `predict`, `attend`, `self_modify`, `world_model`, `goals`, `full_simulate`
- Verified: 51 steps, 22 prediction links, 3 edges grown, 55.4% explored, 2/3 goals completed

---

## TASK-030: Port Core_Unit + MainUnit spine into Cascade_toolStack
**Priority:** P1 | **Tags:** cascade_toolstack, core_unit, mainunit, spine, class_registry
**Updated:** 2026-06-22 14:43

Port the Core_Unit + MainUnit spine from vb_shared.code_classes into Cascade_toolStack as C.

**What to port:**
- Core_Unit — unified core (owns boot + config + mainunit)
- Core_Boot — boot sequence
- Core_ConfigSetup — AST, config, workspace validation
- MainUnit — central dispatch owner with class registry

**MainUnit API (from code_classes.Core_MainUnit):**
```c
typedef struct {
    int ok;
    char action[64];
    char class_name[64];
    void *params;
    char out[BUF];
    char errors[BUF];
    char logs[BUF];
    char last_class[64];
    void *last_params;
    int last_validated;
    ClassRegistry registry;  // class_name -> worker_fn
} MainUnit;

Tuple3 MainUnit_Register(MainUnit *mu, const char *class_name, WorkerFn worker);
Tuple3 MainUnit_Validate(MainUnit *mu, const char *class_name, void *params);
Tuple3 MainUnit_Execute(MainUnit *mu, const char *class_name, void *params);
Tuple3 MainUnit_Cleanup(MainUnit *mu, const char *class_name, int signal);
Tuple3 MainUnit_Route(MainUnit *mu, const char *class_name, void *result);
```

**Key rule**: Execute() REQUIRES Validate() first. No validation = no execution. This is the admit gate.

**Unit Creation Rule**: "When a Unit is needed, the operating system AI creates it. User does NOT manually create, place, register, configure, or route libraries. AI created Unit: naming, placement, brackets, validation, registration, routing are AUTOMATIC."

**Target:** New file `Cascade_toolStack/cascade_spine.c` + updates to `cascade_toolstack.h`

**Source:** vb_shared.code_classes: Core_Unit, Core_MainUnit, Core_Boot, Core_ConfigSetup

### Plan

### Done

- Renamed MainUnit → Kernel (the container that owns all 12 domains)
- Renamed CoreBoot → Kernel_Boot
- Removed CoreUnit (Kernel IS the core now)
- Added all 12 domain structs from Vbs_Code_Verifiation/Vbstyle Dom_List.md:
  Dom_Main, Dom_BCL, Dom_AST, Dom_Report, Dom_DB, Dom_Rules,
  Dom_State, Dom_Error, Dom_Orch, Dom_System, Dom_IO, Dom_Network
- Dom_Main is the dispatch owner (register, validate, execute, cleanup, route)
- Kernel struct contains: boot + all 12 domains + initialized flag
- 21/21 self-tests pass (zero warnings): init all 12 domains, boot, register, validate gate, execute, cache hit, unknown class, empty/NULL rejection, failing worker, cleanup, route, status, workspace validation, re-register, all 12 domains accessible
- msearch_v5 still compiles clean
- Updated DOMAIN_ARCHITECTURE.md with new naming
- Populated Vbs_Code_Verifiation/Vbstyle Dom_List.md with all 55 dom_* from database under the 12 Kernel domains (markdown header format)

---

## TASK-004: Fix all BCL correctness gaps — one pass, no partial
**Priority:** P0 | **Tags:** bcl, validator, fixer, engine
**Updated:** 2026-06-22 01:30

Fix all 8 real bugs / missing invariants in the BCL runtime. Specs confirmed by user.

### Plan (done)

**bcl_validator.py — 4 new validation rules:**
- Rule 10: duplicate sibling detection (same-name children under one parent). Breaks _find_by_path/_find_by_name silently.
- Rule 11: branch pair requirement (if Pass or Fail exists, both must exist; Unsure/Wait optional). Only triggers when branch tokens are present.
- Rule 12: circular reference detection (non-branch name repeats along root-to-node path). Branch tokens excluded — they legitimately nest.
- Recursion depth guard (MAX_DEPTH=256, raises Violation on exceed).

**bcl_fixer.py — 3 fixes:**
- Fix ordering: violations sorted by rule_id ascending before applying (structural before cosmetic: name fix before weight fix, because weight fix uses path which includes name).
- Undo/rollback: fix() clones AST before applying fixes, returns (root, actions, snapshot). restore(snapshot) returns a fresh clone for revert.
- Orphan detection: cleanup_empty now runs verify_connectivity after removal — detects stale parent pointers and re-links orphans.

**bcl_engine.py — 2 wiring changes:**
- Regression check in convergence loop: after FIX, if violation count increased, reverts to pre-fix snapshot and fails explicitly. Compares against current cycle's count (not initial 0).
- Convergence loop exit: explicitly sets allowed_next = {SERIALIZE} after loop, regardless of exit reason. The loop is a sub-FSM with one exit point — this prevents RuntimeError when breaking after FIX (allowed_next was {VALIDATE}).

**NOT touched (per user spec):**
- Tuple structure validation — free-form, rule 999 is the only constraint.
- Required fields — no universally required fields.
- Category 3 language features — comments, imports, schema DSL, etc.

**Verified:** `python3 Sql_Schema_Config/bcl_crud.py demo` — all 13 tests pass, deterministic across 3 runs. All 8 invariants verified with targeted assertions.

---

## TASK-003: Max-out BCL engine stability
**Priority:** P0 | **Tags:** bcl, engine, invariants
**Updated:** 2026-06-22 01:10

Final hardening pass on the BCL engine. Two of three proposed fixes applied; one rejected with proof.

### Plan (done)

- Issue 1 (applied): Replaced `ast_hash` with a full structural walk (name + tuples + recursive children). Format-independent, includes root node, detects tuple-order and name differences.
- Issue 2 (REJECTED): Moving the stall check after FIX would break the strict FSM. After FIX, `allowed_next = {VALIDATE}`, so breaking there makes the subsequent SERIALIZE entry raise RuntimeError. Current timing (check before FIX, when `allowed_next = {FIX, SERIALIZE}`) is the only correct placement.
- Issue 3 (applied): Added `text_mode` field to `EngineResult` — `"PASS"` for usable output, `"DIAGNOSTIC"` for FAIL snapshot, `None` for ERROR (no AST).
- Verified: all 13 tests pass, deterministic across 3 runs. Stall detection confirmed firing with new structural hash.

---

## TASK-002: Harden BCL engine invariants
**Priority:** P0 | **Tags:** bcl, engine, invariants
**Updated:** 2026-06-22 00:30

Fix 7 correctness/architecture issues in the BCL pipeline orchestrator.

### Plan (done)

- Added `clone_ast(node)` + `ast_hash(node)` helpers; removed `import copy`.
- Replaced `_expected_stage` counter with a strict FSM (`ALLOWED_TRANSITIONS`); `_enter_stage` raises `RuntimeError` on out-of-order entry.
- Collapsed `VALIDATE`/`REVALIDATE` into a single `VALIDATE` stage; cycle tracking is internal only.
- `run()` now does hash-based stall detection and always serializes (PASS → usable, FAIL → diagnostic snapshot).
- CRUD `create`/`update`/`delete` use `clone_ast`; `create` no longer mutates the real node's `parent` during the test phase.
- Verified: all 13 tests pass, deterministic across 3 runs.

---

## TASK-056: Fix missing `import os` in Efi_md_viewer.py (CRITICAL BUG)
**Priority:** P0 | **Tags:** efl_brain, bug, critical, import
**Updated:** 2026-06-22 22:30

`Efi_md_viewer.py` line 27 uses `os.path.join()` without importing `os`. This causes a runtime `NameError` when the module loads — the PyQt6 markdown viewer cannot start at all.

**What to do:**
- Add `import os` after line 3 in `efl_brain/Efi_md_viewer.py`
- Verify the viewer launches without error
- Run a quick smoke test: `python3 efl_brain/Efi_md_viewer.py` (should open window or at least not crash on import)

**Key file:** `efl_brain/Efi_md_viewer.py` line 27
**Risk:** None — trivial fix, but blocking all GUI usage of the viewer

---

## TASK-057: Secure hardcoded credentials — move to environment variables
**Priority:** P0 | **Tags:** security, secrets, email, mcp, config
**Updated:** 2026-06-22 22:30

Three locations have hardcoded secrets in the codebase:

1. **`~/.config/mcp-email/accounts.json`** — Yahoo app password and Gmail OAuth client_secret in plaintext JSON
2. **`~/.codeium/windsurf/mcp_config.json`** line 17 — Pinecone API key `pcsk_2FLHBZ_...` hardcoded
3. **`MAC_Config/config_email.py`** lines 358-383 — 3 Google OAuth client secrets embedded in Python code

**What to do:**
- Create `~/.config/mcp-email/.env` with all credentials as environment variables
- Update `accounts.json` to reference env vars (or have the MCP server read from env)
- Update `mcp_config.json` to use env var for Pinecone API key
- Update `config_email.py` to load secrets from env vars (it already has env var support on lines 90-91, 108-109 — extend it)
- Verify email MCP servers still connect after the change
- Add `.env` to `.gitignore` if not already

**Key files:** `~/.config/mcp-email/accounts.json`, `~/.codeium/windsurf/mcp_config.json`, `MAC_Config/config_email.py`
**Risk:** MCP servers may fail to start if env vars not loaded properly; test after changes

---

## TASK-058: Fix GUI engine — broken indentation, missing SQL schemas, decision engine stubs
**Priority:** P1 | **Tags:** gui_engine, bug, stub, broken
**Updated:** 2026-06-22 22:30

The GUI engine has multiple critical issues that prevent it from functioning:

1. **Broken indentation** (`gui_engine.py` lines 542-598) — `_evaluate_resolution()` and `_evaluate_score()` have incorrect indentation causing `IndentationError`
2. **Missing SQL schema files** — `style_db_v2.sql` and `ui_db_v4.sql` referenced but don't exist (lines 23, 215)
3. **Decision engine is a stub** — `GUIDecisionEngine.decide_component()` queries 5 tables that don't exist: `component_ontology`, `when_not_rule`, `when_rule`, `conflict_resolution_rule`, `scoring_model`
4. **Empty test function** — `test_decision_engine()` (lines 747-876) all test bodies are just `pass`
5. **Duplicate code** — `_evaluate_condition()` has duplicate AND/OR handling (lines 609-616 and 700-707)

**What to do:**
- Fix indentation errors in lines 542-598
- Create `style_db_v2.sql` and `ui_db_v4.sql` schema files (or inline the schema in Python)
- Either implement the decision engine logic or mark it as unimplemented and remove fake queries
- Populate required DB tables or remove references to them
- Fill in test_decision_engine() with real assertions or remove it
- Remove duplicate `_evaluate_condition()` code

**Key file:** `gui_engine/gui_engine.py`
**Risk:** Large file with many issues — may need significant refactoring

---

## TASK-059: Implement 6 BookSystem stub methods
**Priority:** P1 | **Tags:** booksystem, stub, implementation
**Updated:** 2026-06-22 22:30

6 methods are declared in BookSystem's dispatch table but return only placeholders:

1. **`Promote`** (line 3370) — promote chapter to higher tier (Tier 1/2/3)
2. **`ListMilestones`** (line 3410) — list milestones by tier
3. **`ListAuthorities`** (line 3450) — list chapter authorities/owners
4. **`CheckContradictions`** (line 3490) — find contradictory statements in book
5. **`WriteNarrative`** (line 3530) — generate narrative text from structured data
6. **`DiscoverRelations`** (line 3570) — find relationships between chapters

**What to do:**
- Implement each method with real logic
- `Promote`: Add tier field to chapters table, implement tier promotion workflow
- `ListMilestones`: Query milestones table with tier filtering
- `ListAuthorities`: Add authority tracking to chapters, query by owner
- `CheckContradictions`: Semantic analysis — compare rules for conflicts
- `WriteNarrative`: Template-based NLG from structured book data
- `DiscoverRelations`: Graph analysis on cross_refs + section_rules
- Add tests for each method

**Key file:** `BookSystem/Book.py` lines 3370-3610
**Risk:** CheckContradictions and WriteNarrative are complex — may need embedding-based semantic comparison

---

## TASK-060: Implement schema lint engine (116 rules defined, no executor)
**Priority:** P1 | **Tags:** schema, lint, rules, config
**Updated:** 2026-06-22 22:30

`Sql_Schema_Config/Database_Schema_config.py` defines 116 rules (36 structural + 80 design) for database schema validation. But **no engine exists to execute them**. The C engine path `~/bin/schemalint` doesn't exist, and `efl_brain/schema_lint_engine.py` doesn't exist either.

**What to do:**
- Build a Python schema lint engine that executes all 116 rules
- Engine should: connect to MySQL, read schema metadata, run each rule, report violations
- Rules cover: integrity, normalization, performance, naming, referential integrity, indexing, data types, engine-specific
- Test against `vb_shared`, `vb_code_test`, `Chat_History` schemas
- Output: violations list with severity, rule name, table, column, suggested fix
- Target: `Sql_Schema_Config/schema_lint_engine.py`

**Key file:** `Sql_Schema_Config/Database_Schema_config.py` (733 lines of rules)
**Risk:** Large scope — 116 rules to implement executors for; some rules may be hard to automate

---

## TASK-062: Run import_md_files.py to import 3,900 markdown files into Chat_History
**Priority:** P1 | **Tags:** chat-import, markdown, mysql, chat_history
**Updated:** 2026-06-22 22:30

`Sql_Schema_Config/import_md_files.py` (116 lines) imports chat files from `vbstyle_documents.markdown_files` into `Chat_History` (sessions + messages + prompts). The script exists but **has never been executed**. 3,900+ markdown files are waiting.

**What to do:**
- Review the script for correctness (USER_PATTERNS + ASSISTANT_PATTERNS parsing)
- Run `python3 Sql_Schema_Config/import_md_files.py`
- Verify Chat_History.sessions and messages tables grow
- Check for import errors (malformed markdown, encoding issues)
- After import, embed new messages into Qdrant via TASK-050
- Add logging if missing

**Key file:** `Sql_Schema_Config/import_md_files.py`
**Risk:** 3,900 files may produce a lot of data; may need batch processing; some files may not match USER/ASSISTANT patterns

---

## TASK-063: Implement chat_mover SQLite source reader (currently stubbed)
**Priority:** P1 | **Tags:** chat_mover, sqlite, stub, implementation
**Updated:** 2026-06-22 22:30

`chat_mover/chat_mover.py` line 995-996 has a stub for SQLite source reading:
```python
if 'sqlite' in args.source:
    logger.warning("SQLite source not yet implemented", extra={'step': '1'})
```

**What to do:**
- Implement SQLite source reader that reads from SQLite chat databases
- Support reading from `book.db`, `autocomplete.db`, `efl_brain.db` chat tables if they exist
- Or support arbitrary SQLite databases with configurable table/column mapping
- Add to the pipeline: SQLite → parse → import to Chat_History MySQL → embed to Qdrant
- Test with a real SQLite database

**Key file:** `chat_mover/chat_mover.py` line 995
**Risk:** Need to define which SQLite databases contain chat data and their schemas

---

## TASK-064: Complete chat_mover dry-run mode with full validation
**Priority:** P1 | **Tags:** chat_mover, dry-run, testing, validation
**Updated:** 2026-06-22 22:30

`chat_mover/chat_mover.py` dry-run mode (lines 603-611, 733-737) only logs messages and returns immediately. It doesn't validate the full pipeline end-to-end without writing.

**What to do:**
- Make dry-run mode actually parse and validate data without writing to MySQL
- Validate: session structure, message format, embedding model availability, Qdrant connectivity
- Report: how many sessions would be imported, how many messages, estimated embedding time
- Check for: duplicate sessions, malformed messages, missing fields
- Add `--validate` flag for full validation mode

**Key file:** `chat_mover/chat_mover.py` lines 603-611, 733-737
**Risk:** Low — additive feature, doesn't change existing behavior

---

## TASK-068: Complete SVG engine — keyframe TODO, wizard_qa_bridge stubs
**Priority:** P2 | **Tags:** svg_engine, todo, stub, keyframe
**Updated:** 2026-06-22 22:30

Two incomplete features in SVG engine:

1. **`wizard_studio.py` line 579** — `# TODO: implement keyframe adding` — keyframe functionality not implemented
2. **`wizard_qa_bridge.py` lines 516, 520** — Two methods with just `pass` statements (settings application on Apply button click)

**What to do:**
- Implement keyframe adding in wizard_studio.py
- Implement the two apply methods in wizard_qa_bridge.py
- Test: create an animation with keyframes, verify it renders
- Test: click Apply button in QA bridge, verify settings are applied

**Key files:** `svg_engine/wizard_studio.py` line 579, `svg_engine/wizard_qa_bridge.py` lines 516, 520
**Risk:** Low — isolated features

---

## TASK-070: Standardize efl_brain Tuple3 returns (VBStyle compliance)
**Priority:** P2 | **Tags:** efl_brain, vbstyle, tuple3, compliance
**Updated:** 2026-06-22 22:30

Multiple efl_brain files return `None` or empty lists instead of Tuple3 `(ok, data, error)`:

- `Efi_ram_ai.py` — lines 514, 635-636, 1282, 1297, 1385
- `Efi_agent_graph.py` — lines 144, 458, 683, 842, 873, 1250, 1265, 1294, 1312, 1476, 1496, 1511, 1517, 1534, 1545, 2215

**What to do:**
- Convert all `return None` to `return (False, None, "error description")`
- Convert all `return []` to `return (True, [], None)`
- Convert `return None, 0.0` to `return (False, 0.0, "error description")`
- Add meaningful error messages for each failure path
- Verify no callers break from the change

**Key files:** `efl_brain/Efi_ram_ai.py`, `efl_brain/Efi_agent_graph.py`
**Risk:** Many call sites may need updating to handle Tuple3 instead of None

---

## TASK-071: Extract hardcoded thresholds to Config_efl_brain.py
**Priority:** P2 | **Tags:** efl_brain, config, hardcode
**Updated:** 2026-06-22 22:30

Multiple efl_brain files have hardcoded magic numbers that should be in config:

- `Efi_agent_graph.py` — learning rates (0.3 → 0.01), consolidation interval (30 steps)
- `Efi_code_graph.py` line 281 — hub threshold (3 outgoing edges)
- `Efi_boot_graph.py` line 258 — max depth (10)

**What to do:**
- Add config keys to `Config_efl_brain.py`: LEARNING_RATE_INITIAL, LEARNING_RATE_FINAL, CONSOLIDATION_INTERVAL, HUB_THRESHOLD, MAX_DEPTH
- Replace hardcoded values with Config references
- Verify behavior unchanged after extraction

**Key files:** `efl_brain/Efi_agent_graph.py`, `efl_brain/Efi_code_graph.py`, `efl_brain/Efi_boot_graph.py`, `efl_brain/Config_efl_brain.py`
**Risk:** Low — values don't change, just moved

---

## TASK-072: Verify efl_brain BuildTypedGraph/ValidateBootSequence/StructuralAnalysis methods
**Priority:** P2 | **Tags:** efl_brain, verification, graph
**Updated:** 2026-06-22 22:30

README.md (lines 85-86) says these methods were added in TASK-045, but audit found they may be stubs or not fully integrated with TypedGraph/ExecutionGraph:
- `BuildTypedGraph()` — should use TypedGraph from Efi_code_graph.py
- `ValidateBootSequence()` — should use ExecutionGraph from Efi_boot_graph.py
- `StructuralAnalysis()` — mentioned in TASK-045 but may not exist

**What to do:**
- Read `Efi_agent_graph.py` and verify each method exists and is fully implemented
- Check that BuildTypedGraph() actually imports and uses TypedGraph
- Check that ValidateBootSequence() actually imports and uses ExecutionGraph
- Check if StructuralAnalysis() exists at all
- If stubs — implement them properly
- If missing — add them
- Run: `python3 efl_brain/Efi_core.py build` and verify no errors

**Key file:** `efl_brain/Efi_agent_graph.py`
**Risk:** May reveal that TASK-045 was not fully completed

---

## TASK-074: Fix export_chat_embeddings.py — hardcoded path, bare except clauses
**Priority:** P2 | **Tags:** chat-export, bug, hardcode, error-handling
**Updated:** 2026-06-22 22:30

Two issues in `export_chat_embeddings.py`:

1. **Hardcoded path** (line 34): `HISTORY_DIR = "/Users/wws/.local/share/devin/cli/summaries"` — absolute path, not configurable
2. **Bare except clauses** (lines 154-155, 291-292): `except: break` — swallows all errors silently

**What to do:**
- Replace hardcoded path with config value or env var
- Replace bare `except:` with specific exceptions (`except Exception as e:`)
- Log errors instead of silently breaking
- Add `--history-dir` CLI argument for custom path

**Key file:** `export_chat_embeddings.py`
**Risk:** Low — but must be done before TASK-050/051 run for real

---

## TASK-075: Create agent_os database (MASTER_PLAN Phase 1)
**Priority:** P2 | **Tags:** master_plan, agent_os, database, phase1
**Updated:** 2026-06-22 22:30

MASTER_PLAN_AGENT_OS.md describes an 8-phase build order for a database-native agent OS. **Phase 1 (Foundation) is not implemented** — no `agent_os` database exists. The schema is designed (artifact, event_log, agent_state, gui_config, agent_registry) but not created.

**What to do:**
- Create `agent_os` MySQL database
- Create 5 tables per MASTER_PLAN schema:
  - `artifact` — code, notes, configs (kind, language, content, checksum)
  - `event_log` — append-only event log (event_type, payload, timestamp)
  - `agent_state` — agent state snapshots (agent_id, state_json, updated_at)
  - `gui_config` — GUI widget configurations (widget_id, config_json)
  - `agent_registry` — registered agents (agent_id, name, capabilities)
- Import existing VBStyle code from `vb_code_test` → artifact table
- Import Book rules → artifact table (kind=note, language=markdown)
- Test: verify tables exist, data is queryable

**Key file:** `MASTER_PLAN_AGENT_OS.md` lines 353-358
**Risk:** Schema design may need refinement; large data import from vb_code_test

---
