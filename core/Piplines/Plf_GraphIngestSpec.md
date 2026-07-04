# SPEC.md — Graph Engine Domain

## 1. Purpose

Unify all graph code from three folders (dom_compression, efl_brain, code_store_variations) into a single VBStyle domain stored in v20_hybrid_best.db. Any AI agent can discover, understand, add to, and verify graph code by reading the BCL instructions in the database.

## 2. What Exists Now (As-Is)

### 2.1 Three Separate Folders

| Folder | Files | Classes | Methods | VBStyle? | DB-backed? |
|--------|-------|---------|---------|----------|------------|
| dom_compression/ | 8 | 8 viewers | ~121 | No (no Run()) | No |
| efl_brain/ | 16 | 30+ brothers | ~400+ | Partial (21 Run()) | Yes (efl_brain.db) |
| code_store_variations/ | 3 | 3 MemUnits | ~47 | Yes (3 Run()) | Yes (code_store.db) |

### 2.2 Problems

- **Data duplication**: CLASSES= copied 16x, EDGES= copied 30x, CATEGORIES= copied 13x across dom_compression files
- **UI duplication**: 9 Tkinter patterns (Canvas, create_oval, DrawGraph, BuildUI, etc.) copied across 9 files in 2 folders
- **No VBStyle**: dom_compression has zero Run() dispatches, zero Tuple3 returns
- **No unified dispatch**: Each file is standalone, no single entry point
- **No BCL instructions**: No decision tree for AI agents to follow
- **Not in the database**: Graph code lives in .py files, not in v20_hybrid_best.db

### 2.3 What's Already In v20_hybrid_best.db

- 1,700+ classes, 14,256 methods across 80+ domains
- 48 graph_engine classes, 541 methods (just ingested)
- 11 BCL instructions (just created)
- 14 plan_steps for graph_engine_pipeline
- 25 orchestration entries
- Tables: classes, methods, search_idx (FTS5), orchestration, plans, plan_steps, violations, bcl_instructions

## 3. What We're Building (To-Be)

### 3.1 GraphEngine — Single VBStyle MemUnit

```
GraphEngine.Run(command, params) → Tuple3(ok, data, error)
```

Dispatch commands:

| Command | What it does | Params |
|---------|-------------|--------|
| `plan` | Open Plan view — editable idea → candidates → spec | {domain: "x"} |
| `spec` | Open Spec view — classes, nodes, edges, categories | {domain: "x"} |
| `flow` | Open Flow view — execution paths, step-by-step | {domain: "x"} |
| `lifecycle` | Open Lifecycle view — temporal phases, swim-lane | {domain: "x"} |
| `dependency` | Open Dependency view — edge justifications | {domain: "x"} |
| `error` | Open Error view — failure modes, recovery | {domain: "x"} |
| `orchestration` | Open Orchestration view — call tree | {domain: "x"} |
| `gap` | Open Gap view — missing pairs, CRUD closure | {domain: "x"} |
| `inspect` | Read real .py files, build code graph (from efl_brain) | {path: "/x"} |
| `verify` | Compare plan vs actual code | {domain: "x"} |
| `bfs` | BFS traversal (from DomGraph) | {start: "node"} |
| `dfs` | DFS traversal (from DomGraph) | {start: "node"} |
| `cycle` | Detect cycles (from DomGraph) | {} |
| `path` | Shortest path (from DomGraph) | {from: "a", to: "b"} |
| `topology` | Topological sort (from DomGraph) | {} |
| `search` | Search graph code in DB | {query: "text"} |
| `instructions` | Read BCL instructions | {category: "howto"} |
| `status` | Show DB summary — classes, methods, violations | {} |

### 3.2 Shared Data (One Copy, Not 16)

```
spec_data = {
    "domain": "compression",
    "classes": { ... },     # was CLASSES =, copied 16x
    "edges": [ ... ],       # was EDGES =, copied 30x
    "categories": { ... },  # was CATEGORIES =, copied 13x
    "flows": { ... },       # was FLOWS =, copied 4x
}
```

Stored in v20_hybrid_best.db, not in .py files.

### 3.3 Shared Viewer (One Copy, Not 9)

GraphViewer provides:
- Tkinter Canvas with node circles, edge arrows, labels
- Click-to-inspect detail panel
- Filter by category/type
- Drag-and-drop node positioning
- Zoom and pan
- Export to DOT / JSON / SPEC.md

Each view (Plan, Spec, Flow, etc.) only defines what makes it unique:
- **PlanView**: capability grouping, expansion arrows, editable text input
- **SpecView**: circular layout, category colors, edge type labels
- **FlowView**: linear/swim-lane layout, step numbers, arrow direction
- **LifecycleView**: swim-lane by phase, temporal ordering
- **DependencyView**: chain tracing, edge reason tooltips
- **ErrorView**: error producers vs handlers, recovery edges highlighted
- **OrchestrationView**: tree layout, root/leaf detection, call hierarchy
- **GapView**: missing pairs overlay, CRUD closure check, coverage areas

### 3.4 BCL Instructions (Already Created)

11 tokens in bcl_instructions table:
- AddDomCode (howto, weight=100)
- CodeStyle (rules, weight=95)
- HowToVerify (verify, weight=95)
- GraphEnginePipeline (pipeline, weight=95)
- WhereDoesCodeGo (where, weight=90)
- ErrorDecisionTree (error_handling, weight=90)
- KnowledgeCodegraph (codegraph, weight=90)
- AmIAllowed (permissions, weight=88)
- WhenToAddCode (when, weight=85)
- AlternativeSteps (alternatives, weight=85)
- WhyVBStyle (why, weight=80)

### 3.5 GUI

A Tkinter GUI that:
- Shows all graph_engine classes in the DB as a codegraph
- Nodes = classes, edges = orchestration sequence
- Click a class → show methods, Run() dispatch, Tuple3 returns
- Click a BCL instruction → show the decision tree
- Filter by subdomain (plan_view, spec_view, code_graph, etc.)
- Run a view: button that calls GraphEngine.Run("plan", {domain: "compression"})
- Violations panel: shows any VBStyle rule violations
- Search bar: FTS5 search across all graph methods

## 4. Architecture

```
v20_hybrid_best.db
├── classes (domain=graph_engine, 48 classes)
├── methods (541 methods, 375 VBStyle, 109 Tuple3)
├── search_idx (FTS5, 564 graph hits)
├── orchestration (pipeline=graph_engine, 25 entries)
├── plans (graph_engine_pipeline, 14 steps)
├── plan_steps (14 steps: ingest → BCL → engine → views → GUI → verify)
├── violations (per-method rule violations)
├── bcl_instructions (11 BCL decision trees)
├── spec_data (NEW — domain specs, not yet created)
├── decision_nodes (DEGS)
├── decision_edges (DEGS)
├── execution_log (DEGS)
├── run_state (DEGS)
├── run_metrics (tracks run success/failure counts)
├── cascade_runs (CASCADE — pre-code validation runs)
├── cascade_stage_results (CASCADE — per-graph verdicts)
└── cascade_rules (CASCADE — enforcement rules per stage)

SYSTEM TRIANGLE:

  CascadeEngine  →  VALIDATES structure (compiler)
       ↓
  GraphEngine    →  EXECUTES structure (executor)
       ↓
  DecisionEngine →  EVOLVES structure (DEGS — learns from failures)

GraphOrchestrator (Root MemUnit — coordinates all subsystems)
├── Run("cascade", {idea}) → starts CascadeEngine validation run
├── Run("pipeline", {domain}) → runs full 8-graph pipeline via CascadeEngine
├── Run("degs", {start_node}) → starts DEGS decision loop
├── Run("sandbox", {code}) → runs code in TmpWorkspace
├── Run("engine", {command, params}) → forwards to GraphEngine (GATED by cascade)
├── Run("gui", {}) → launches DecisionGUI
└── Run("status", {}) → returns status of all subsystems

CascadeEngine (MemUnit — PRE-CODE VALIDATION COMPILER)
├── Run("start", {idea}) → creates cascade_run, writes initial SPEC.md
├── Run("stage", {run_id, stage}) → executes one graph projection
├── Run("validate", {run_id}) → runs all 8 graphs in sequence
├── Run("status", {run_id}) → returns current stage + verdicts
├── Run("rewrite", {run_id}) → regenerates SPEC.md with fixes
├── Run("commit", {run_id}) → allows code generation (only if status=passed)
└── Run("rules", {stage}) → returns cascade_rules for stage

HARD GATE: GraphEngine.Run("code", ...) BLOCKED unless cascade_runs.status == "passed"

GraphEngine (MemUnit — graph views + algorithms)
├── Run("plan", {domain}) → PlanView
├── Run("spec", {domain}) → SpecView
├── Run("flow", {domain}) → FlowView
├── Run("lifecycle", {domain}) → LifecycleView
├── Run("dependency", {domain}) → DependencyView
├── Run("error", {domain}) → ErrorView
├── Run("orchestration", {domain}) → OrchestrationView
├── Run("gap", {domain}) → GapView
├── Run("inspect", {path}) → Inspect (AST parse real files)
├── Run("verify", {domain}) → Verify (compare plan vs actual)
├── Run("bfs"/"dfs"/"cycle"/"path"/"topology", params) → DomGraph algorithms
├── Run("search", {query}) → FTS5 search in DB
├── Run("instructions", {category}) → Read BCL
├── Run("status", {}) → DB summary
└── Run("remove_class", {class_id}) → removes bad code from DB

GraphViewer (Shared Tkinter)
├── Canvas + nodes + edges + labels
├── Click → detail panel
├── Filter by type/category
├── Drag/drop, zoom, pan
├── Export (DOT/JSON/SPEC.md)
└── Headless mode: if Tkinter init fails, returns Tuple3(0, None, "tkinter_unavailable")

DecisionEngine (DEGS — decision graph execution)
├── Run("start", {start_node}) → starts run, returns run_id
├── Run("step", {run_id}) → executes one node
├── Run("auto", {run_id, max_steps}) → runs to completion or max_steps
├── Run("end", {run_id}) → ends run, cleans up run_state
├── Run("auto_generate", {run_id}) → creates fallback nodes from failures
├── Run("merge_runs", {run_ids}) → compares failed runs, finds patterns
├── Run("promote_path", {node_id, threshold}) → promotes weight after N successes
├── Run("prune_dead", {threshold}) → removes edges with weight below threshold
└── Run("status", {run_id}) → returns current node + state

TmpWorkspace (Sandbox MemUnit)
├── Run("create", {}) → creates run folder, returns (run_id, path)
├── Run("write", {run_path, filename, content}) → writes file
├── Run("read", {run_path, filename}) → reads file
├── Run("list", {run_path}) → lists files
├── Run("clean", {run_id}) → removes run folder
└── Run("compile", {filepath}) → py_compile, returns (ok, error)

Inspect (Post-code analysis — bridge to efl_brain)
├── Run("parse", {path}) → AST parse .py files, extract classes/methods
├── Run("build_graph", {path}) → build typed graph from real code
└── Run("compare", {domain}) → compare DB classes vs real .py files

Verify (Plan vs Actual comparison)
├── Run("check", {domain}) → compare spec_data classes vs DB classes
├── Run("missing", {domain}) → list classes in spec but not in DB
├── Run("extra", {domain}) → list classes in DB but not in spec
└── Run("report", {domain}) → full verification report

AutoGenerator (Self-writing graph evolution)
├── Run("auto_generate", {run_id}) → reads failures, creates fallback nodes
├── Run("dedup", {domain}) → removes duplicate fallback nodes
├── Run("merge_runs", {run_ids}) → finds patterns across failed runs
├── Run("promote_path", {node_id, threshold}) → promotes weight after N successes
├── Run("prune_dead", {threshold}) → removes edges below threshold
└── Run("metrics", {domain}) → returns run success/failure counts

Config_graph_engine (VBStyle Config — all paths, schema, settings)
├── DB_PATH → tmp_graph_ingest/graph_engine_dev.db (DEV COPY — not production)
├── TMP_DIR → /tmp_graph_ingest/runs/
├── DOMAIN → graph_engine
├── MAX_RETRY → 3 (pipeline loop limit)
├── MAX_STEPS → 50 (DEGS auto-run limit)
├── PRUNE_THRESHOLD → 0.1 (edge weight below which pruned)
├── PROMOTE_THRESHOLD → 3 (successes needed to promote path)
├── GUI_WINDOW → {width: 1200, height: 800, title: "Graph Engine"}
├── COLORS → {node: {...}, edge: {...}, highlight: {...}}
├── SCHEMA_SQL → embedded CREATE TABLE statements
└── cfg = Config_graph_engine()
```

### 4.1 Dispatch Table (GraphEngine)

The Run() method uses a dispatch dictionary, not if/elif chains:

```python
DISPATCH = {
    "plan":         ("view", PlanView),
    "spec":         ("view", SpecView),
    "flow":         ("view", FlowView),
    "lifecycle":    ("view", LifecycleView),
    "dependency":   ("view", DependencyView),
    "error":        ("view", ErrorView),
    "orchestration":("view", OrchestrationView),
    "gap":          ("view", GapView),
    "inspect":      ("engine", Inspect),
    "verify":       ("engine", Verify),
    "bfs":          ("algo", DomGraph, "bfs"),
    "dfs":          ("algo", DomGraph, "dfs"),
    "cycle":        ("algo", DomGraph, "cycle"),
    "path":         ("algo", DomGraph, "path"),
    "topology":     ("algo", DomGraph, "topology"),
    "search":       ("db", None),
    "instructions": ("db", None),
    "status":       ("db", None),
    "remove_class": ("db", None),
}
```

### 4.2 BCL Payload Parsing Flow

When DecisionEngine executes a node with node_type="action":

```
1. Read node.payload (BCL token name, e.g. "AddDomCode")
2. Query bcl_instructions WHERE token_name = node.payload
3. Parse BCL token:
   a. Extract [@Pass] and [@Fail] branches
   b. Extract ("key";"value") properties
   c. Extract weight values
4. For each [@Pass] branch → create virtual success edge
5. For each [@Fail] branch → create virtual failure edge
6. Execute the BCL instruction:
   a. If payload is a howto → follow steps in order
   b. If payload is a rule → check against code
   c. If payload is a verify → run verification checks
7. Return Tuple3(ok, result, error)
```

If the BCL token name does not exist in bcl_instructions:
```
→ Return Tuple3(0, None, "bcl_token_not_found: {payload}")
→ Log to execution_log with status=failed
→ Follow fallback edge if exists, else pause run
```

## 5. Rules

1. **No .py files** — all code lives in v20_hybrid_best.db (nofiles rule)
2. **VBStyle** — Run() dispatch, Tuple3 returns, self.state dict, PascalCase, UPPERCASE
3. **No print()** — use return values
4. **No decorators** — no @property, @staticmethod
5. **No hardcoded paths** — all from Config_graph_engine
6. **BCL instructions** — any AI can read bcl_instructions table to know how/when/why
7. **One copy of data** — spec_data in DB, not duplicated across files
8. **One copy of rendering** — GraphViewer shared by all views
9. **Verify before done** — py_compile + violations check + search_idx update
10. **Pipeline order** — Plan → Spec → Flow → Lifecycle → Dependency → Error → Orchestration → Gap → Code → Verify
11. **Max retry** — pipeline loop limited to MAX_RETRY (3) attempts. After 3 failures, pause run and log "max_retry_exceeded"
12. **Max steps** — DEGS auto-run limited to MAX_STEPS (50). After 50 steps, pause run and log "max_steps_exceeded"
13. **AmIAllowed enforcement** — before any write to DB, check AmIAllowed BCL token. If permission denied, return Tuple3(0, None, "permission_denied")
14. **End run required** — every run_id must be ended with Run("end", {run_id}) to clean up run_state. Runs not ended after 1 hour are auto-cleaned
15. **Dedup fallback nodes** — auto_generate checks for existing fallback nodes with same name + condition before creating new ones
16. **Headless fallback** — if Tkinter fails to init, GraphViewer returns Tuple3(0, None, "tkinter_unavailable") instead of crashing
17. **DB locking** — all writes use SQLite transactions with BEGIN IMMEDIATE to prevent concurrent write corruption

## 6. Verification

### 6.1 Manual Checks

- `SELECT COUNT(*) FROM classes WHERE domain='graph_engine'` → 48
- `SELECT COUNT(*) FROM methods m JOIN classes c ON m.class_id=c.id WHERE c.domain='graph_engine'` → 541
- `SELECT COUNT(*) FROM bcl_instructions` → 11
- `SELECT * FROM search_idx WHERE search_idx MATCH 'graph'` → 564 hits
- `SELECT COUNT(*) FROM plan_steps WHERE plan_id=(SELECT id FROM plans WHERE name='graph_engine_pipeline')` → 14
- `SELECT COUNT(*) FROM violations` → should be 0 for new code
- `py_compile` on any extracted code → no syntax errors

### 6.2 Automated Verification Runner

```
VerifyRunner.Run("all", {domain: "graph_engine"}) → Tuple3(ok, report, error)
```

Checks performed automatically:
1. py_compile all class_code in domain
2. Check every class has Run() method
3. Check every Run() returns Tuple3
4. Check no print() in any method_code
5. Check no decorators in any method_code
6. Check no hardcoded paths (regex for /Users/)
7. Check no self._ (must use self.state)
8. Check search_idx is updated
9. Check bcl_instructions count matches expected
10. Check run_metrics for success rate

Returns JSON report:
```json
{
  "total_checks": 10,
  "passed": 8,
  "failed": 2,
  "failures": ["check_3", "check_7"],
  "timestamp": "2026-06-23T15:00:00"
}
```

### 6.3 Run Metrics Table

```sql
CREATE TABLE run_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    domain TEXT,
    total_nodes INTEGER,
    nodes_executed INTEGER,
    nodes_failed INTEGER,
    fallbacks_created INTEGER,
    duration_seconds REAL,
    success INTEGER,  -- 1 = success, 0 = failed
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);
```

Query: `SELECT AVG(success), COUNT(*) FROM run_metrics WHERE domain='graph_engine'`

## 7. Build Order (from plan_steps)

1. ✅ Ingest graph code into DB (done — 48 classes, 541 methods)
2. ✅ Create BCL instructions (done — 11 tokens)
3. ⬜ Build GraphEngine MemUnit (Run() dispatch to all views)
4. ⬜ Build GraphViewer (shared Tkinter rendering)
5. ⬜ Build PlanView (editable idea → candidates → spec)
6. ⬜ Build SpecView (classes, nodes, edges, categories)
7. ⬜ Build FlowView (execution paths, step-by-step logic)
8. ⬜ Build LifecycleView (temporal phases, swim-lane ordering)
9. ⬜ Build DependencyView (edge justifications, dependency chains)
10. ⬜ Build ErrorView (error paths, failure modes, recovery)
11. ⬜ Build OrchestrationView (call tree, roots, leaves, dispatch)
12. ⬜ Build GapView (missing pairs, CRUD closure, coverage)
13. ⬜ Build GUI (visualize and manage graph codegraph)
14. ⬜ Verify (run all views, check Tuple3 returns, no errors)

## 8. Decision Execution Graph System (DEGS)

A controlled loop where any AI can run: ACT → VERIFY → BRANCH → LOG → REPEAT

### 8.1 DEGS Schema (SQLite in v20_hybrid_best.db)

```sql
CREATE TABLE decision_nodes (
    node_id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT,
    name TEXT,
    node_type TEXT,    -- question | action | check | fallback
    payload TEXT,      -- BCL instruction or code to execute
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE decision_edges (
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_node INTEGER,
    to_node INTEGER,
    condition TEXT,    -- success | fail | error | true | false | custom
    weight REAL DEFAULT 1.0,
    FOREIGN KEY(from_node) REFERENCES decision_nodes(node_id),
    FOREIGN KEY(to_node) REFERENCES decision_nodes(node_id)
);

CREATE TABLE execution_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    node_id INTEGER,
    status TEXT,       -- executed | failed | skipped
    output TEXT,       -- JSON result
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(node_id) REFERENCES decision_nodes(node_id)
);

CREATE TABLE run_state (
    run_id TEXT PRIMARY KEY,
    current_node INTEGER,
    state TEXT,        -- running | paused | completed | failed
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(current_node) REFERENCES decision_nodes(node_id)
);
```

### 8.2 DecisionEngine (VBStyle MemUnit)

```
DecisionEngine.Run(command, params) → Tuple3(ok, data, error)

Commands:
  "start"    → start_run(start_node) → creates run_id, initializes run_state, returns run_id
  "step"     → step(run_id) → execute current node, branch to next
  "auto"     → auto(run_id, max_steps) → runs to completion or max_steps (default MAX_STEPS=50)
  "end"      → end_run(run_id) → sets run_state=completed, cleans up, writes run_metrics
  "get_node" → get_node(node_id) → return node data
  "get_edges" → get_edges(node_id) → return outgoing edges
  "log"      → log(run_id, node_id, status, output) → write to execution_log
  "status"   → read run_state → return current node + state
  "history"  → read execution_log for run_id → return full trace
```

Node types and execution:
- **question** → returns awaiting_input, pauses run
- **action** → executes payload (BCL or code), returns result
- **check** → evaluates condition, returns pass/fail
- **fallback** → recovery path, logs error, continues

Branching logic:
- For each outgoing edge, evaluate condition against result
- Follow first matching edge (highest weight first)
- If no match → log as failed, follow fallback edge if exists
- If no fallback → pause run, set state=failed
- If node has no outgoing edges → log as "terminal_node", set state=completed
- If run_state.current_node points to deleted node → log error, set state=failed, return Tuple3(0, None, "current_node_deleted")
- If max_steps reached in auto mode → pause run, set state=paused, log "max_steps_exceeded"
- If pipeline loop count > MAX_RETRY (3) → pause run, set state=failed, log "max_retry_exceeded"

BCL payload parsing (when node_type="action" and payload is BCL token name):
```
1. Query bcl_instructions WHERE token_name = payload
2. If not found → return Tuple3(0, None, "bcl_token_not_found")
3. Parse BCL: extract [@Pass]/[@Fail] branches and properties
4. Execute BCL instruction steps
5. Return Tuple3 with result
```

AmIAllowed enforcement (before any DB write):
```
1. Query bcl_instructions WHERE token_name = "AmIAllowed"
2. Check if current operation is permitted
3. If denied → return Tuple3(0, None, "permission_denied")
4. If permitted → proceed with write
```

End run cleanup:
```
end_run(run_id):
  1. Set run_state.state = "completed" (or "failed")
  2. Write run_metrics row (total_nodes, nodes_executed, nodes_failed, duration, success)
  3. Keep execution_log rows (append-only, for auto_generate analysis)
  4. Return Tuple3(1, {run_id, state, metrics}, None)
```

Auto-cleanup: runs not ended after 1 hour are auto-cleaned by a periodic check.
Stale run_state rows are set to state="timeout".

### 8.3 TmpWorkspace (VBStyle MemUnit)

```
TmpWorkspace.Run(command, params) → Tuple3(ok, data, error)

Commands:
  "create"   → create_run_folder() → returns (run_id, path)
  "write"    → write_file(run_path, filename, content) → returns full path
  "read"     → read_file(run_path, filename) → returns content
  "list"     → list_files(run_path) → returns file list
  "clean"    → clean_run(run_id) → removes run folder
  "compile"  → py_compile(filepath) → returns (ok, error)
```

Each AI run gets its own tmp folder. Safe iteration environment.
No cross-contamination between runs.

### 8.4 DecisionGUI (Tkinter, VBStyle)

Tkinter viewer (not PyQt — consistent with existing graph viewers):

- **Start button** → starts a new run from node 1
- **Step button** → executes one node, shows result
- **Auto button** → runs to completion (or failure)
- **Node display** → shows current node name, type, payload
- **Edge display** → shows outgoing edges and conditions
- **Log panel** → scrolling execution_log for this run_id
- **Graph view** → visual tree of decision_nodes + decision_edges
- **Branch highlight** → shows which edge was taken (green) vs not taken (gray)

### 8.5 Self-Writing Graph (AutoGenerator MemUnit)

The system evolves: AI generates new nodes + edges from failure logs.

```
AutoGenerator.Run(command, params) → Tuple3(ok, data, error)

Commands:
  "auto_generate" → reads failure logs, creates fallback nodes
  "dedup"         → removes duplicate fallback nodes (same name + condition)
  "merge_runs"    → compares multiple failed runs, finds patterns
  "promote_path"  → if a fallback path succeeds N times (PROMOTE_THRESHOLD=3), promote its weight
  "prune_dead"    → remove edges with weight < PRUNE_THRESHOLD (0.1) that haven't been traversed in last 10 runs
  "metrics"       → returns run success/failure counts from run_metrics
```

Auto-generate flow:
```
After a run fails:
  1. Read execution_log for this run_id (status=failed rows)
  2. Find the node that failed
  3. Analyze the failure output
  4. Check for existing fallback node with same name + condition (dedup)
     → If exists: skip creation, just add edge to existing fallback
     → If not: generate a new fallback node with BCL instruction
  5. Create a new edge: failed_node → fallback_node (condition="error", weight=0.5)
  6. Log the new node + edge in decision_nodes + decision_edges
  7. Next run, the same failure follows the fallback path
```

Promote path trigger:
```
  - After each successful run, count how many times each fallback edge was traversed
  - If count >= PROMOTE_THRESHOLD (3): increase weight by 0.5 (max 2.0)
  - Log promotion in execution_log
```

Prune dead trigger:
```
  - Periodically (every 10 runs) or on explicit call
  - Find edges with weight < PRUNE_THRESHOLD (0.1)
  - Check if traversed in last 10 runs (execution_log)
  - If not traversed: delete edge from decision_edges
  - Log pruning in execution_log
```

Merge runs trigger:
```
  - On explicit call with multiple run_ids
  - Compare failure patterns across runs
  - If same node fails with same error in >1 run: create shared fallback
  - Log merge in execution_log
```

### 8.6 Integration with BCL Instructions

Each decision_node with node_type="action" has a payload that is a BCL token name.
The engine reads the BCL from bcl_instructions table and follows it.

```
node.payload = "AddDomCode"
→ engine reads bcl_instructions WHERE token_name="AddDomCode"
→ follows the BCL decision tree
→ each Pass/Fail branch maps to a decision_edge
```

This means the 11 BCL instructions we created ARE the decision tree.
The DEGS engine walks them as a graph, not as text.

### 8.7 Integration with Graph Engine Pipeline

The 10-step pipeline (Plan → Spec → ... → Gap → Code → Verify) becomes
a decision graph in decision_nodes + decision_edges:

```
Node 1: Plan (action, payload="GraphEnginePipeline step 1")
  → success → Node 2: Spec
  → fail → Node 99: Fallback (review plan)

Node 2: Spec (action, payload="GraphEnginePipeline step 2")
  → success → Node 3: Flow
  → fail → Node 98: Fallback (review spec)

...

Node 9: Code (action, payload="AddDomCode")
  → success → Node 10: Verify
  → fail → Node 97: Fallback (check violations)

Node 10: Verify (check, payload="HowToVerify")
  → success → END (call end_run, write run_metrics)
  → fail → Node 1: Plan (loop back — start over with new knowledge)
           → loop_count incremented
           → if loop_count >= MAX_RETRY (3): pause run, log "max_retry_exceeded"
```

The pipeline is no longer a linear checklist — it's a graph with recovery paths.
Each failure creates a new fallback node. The graph gets smarter every run.
MAX_RETRY (3) prevents infinite loops. After 3 failures, the run pauses
and a human or higher-level AI reviews the issue.

## 9. Build Order (Updated with Cascade + DEGS + Gap Fixes)

1. ✅ Ingest graph code into DB (48 classes, 541 methods)
2. ✅ Create BCL instructions (11 tokens)
3. ✅ Write SPEC.md (this file)
4. ✅ Run 8-graph pipeline on SPEC (found 10 high-severity gaps)
5. ✅ Fix SPEC.md gaps (Config, Orchestrator, BCL parsing, error modes, etc.)
6. ✅ Add CascadeEngine layer (pre-code validation compiler)
7. ⬜ Create CASCADE schema (cascade_runs, cascade_stage_results, cascade_rules)
8. ⬜ Create DEGS schema (decision_nodes, decision_edges, execution_log, run_state, run_metrics)
9. ⬜ Build Config_graph_engine (VBStyle config, all paths/constants/schema)
10. ⬜ Build CascadeEngine MemUnit (VBStyle, 8-graph validation, hard gate)
11. ⬜ Seed cascade_rules (8 stages × rules per stage)
12. ⬜ Build GraphOrchestrator (root coordinator, routes through CascadeEngine first)
13. ⬜ Build DecisionEngine MemUnit (VBStyle, Run() dispatch, Tuple3, BCL parsing, AmIAllowed)
14. ⬜ Build TmpWorkspace MemUnit (VBStyle, safe sandbox)
15. ⬜ Build AutoGenerator MemUnit (self-writing graph, dedup, promote, prune)
16. ⬜ Build Inspect MemUnit (AST parse, bridge to efl_brain)
17. ⬜ Build Verify MemUnit (plan vs actual, automated runner)
18. ⬜ Seed decision_nodes from BCL instructions (11 tokens → 11 nodes)
19. ⬜ Seed decision_edges from BCL Pass/Fail branches
20. ⬜ Build DecisionGUI (Tkinter, step button, log panel, graph view, headless fallback)
21. ⬜ Build GraphEngine MemUnit (Run() dispatch table, all commands, CASCADE GATE)
22. ⬜ Build GraphViewer (shared Tkinter rendering, headless mode)
23. ⬜ Build 8 Views (Plan, Spec, Flow, Lifecycle, Dependency, Error, Orchestration, Gap)
24. ⬜ Create spec_data table and migrate domain specs from .py files
25. ⬜ Build VerifyRunner (automated 10-check verification)
26. ⬜ Verify (run full pipeline, check Tuple3, no violations, run_metrics pass)

## 10. Error Handling (Complete)

### 10.1 All Error Modes and Recovery

| Error | Detection | Recovery | Fallback |
|-------|-----------|----------|----------|
| SyntaxError in ingested code | py_compile | Fix syntax in class_code, UPDATE, re-run | ErrorDecisionTree BCL |
| Missing Run() method | VerifyRunner check 2 | Add Run() or mark is_vbstyle=0 | ErrorDecisionTree BCL |
| Missing Tuple3 return | VerifyRunner check 3 | Refactor returns | ErrorDecisionTree BCL |
| Hardcoded path found | VerifyRunner check 6 | Replace with Config constant | ErrorDecisionTree BCL |
| ImportError | Runtime | Search DB or create stub | ErrorDecisionTree BCL |
| VBStyle violation | VerifyRunner checks 4,5,7,8 | Fix or mark resolved | ErrorDecisionTree BCL |
| Decision node has no outgoing edges | step() check | Log "terminal_node", set state=completed | N/A — terminal is valid |
| Run state points to deleted node | step() check | Log error, set state=failed | Return Tuple3(0, None, "current_node_deleted") |
| BCL payload references non-existent token | BCL parser check | Return Tuple3(0, None, "bcl_token_not_found") | Follow fallback edge if exists |
| GUI Tkinter fails to initialize | GraphViewer try/except | Return Tuple3(0, None, "tkinter_unavailable") | Headless mode continues without GUI |
| auto_generate creates duplicate fallback | dedup check | Skip creation, link to existing | Log "dedup_skipped" |
| Concurrent runs writing to same DB | BEGIN IMMEDIATE | SQLite handles locking | Retry after 100ms, max 3 retries |
| Pipeline loop exceeds MAX_RETRY | loop_count check | Pause run, log "max_retry_exceeded" | Human/higher AI review |
| DEGS auto-run exceeds MAX_STEPS | step counter | Pause run, log "max_steps_exceeded" | User can resume with step() |
| Permission denied by AmIAllowed | Pre-write check | Return Tuple3(0, None, "permission_denied") | Log to execution_log |
| Run not ended after 1 hour | Auto-cleanup | Set state="timeout", write run_metrics | N/A |
| Cascade validation blocked (status=blocked) | cascade_stage_results verdict=fail | Return Tuple3(0, None, "cascade_blocked: {stage}") | Rewrite SPEC.md via Run("rewrite") |
| Code execution without cascade pass | GraphEngine hard gate check | Return Tuple3(0, None, "cascade_not_passed") | Must run CascadeEngine.Run("validate") first |
| Cascade stage produces REWRITE verdict | cascade_rules violation_action=rewrite | Auto-rewrite SPEC.md, re-run stage | Log to cascade_stage_results |
| Cascade stage produces BLOCK verdict | cascade_rules violation_action=block | Stop cascade run, set status=blocked | Human review required |

## 11. CascadeEngine (Pre-Code Validation Compiler)

### 11.1 Purpose

CascadeEngine is the COMPILER. It validates structure before code is allowed to exist.
It sits ABOVE GraphEngine. It CONTROLS GraphEngine.

```
Idea → CascadeEngine.validate() → PASS/BLOCK/REWRITE → GraphEngine.execute() → DEGS.evolve()
```

The invariant: **An idea is INVALID until it survives 8 graph projections.**

### 11.2 CASCADE Schema

```sql
CREATE TABLE cascade_runs (
    run_id TEXT PRIMARY KEY,
    idea TEXT,
    spec_path TEXT,
    current_stage TEXT,
    status TEXT DEFAULT 'running',  -- running | blocked | passed | failed
    loop_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cascade_stage_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    stage TEXT,         -- plan | spec | flow | lifecycle | dependency | error | orchestration | gap
    graph_snapshot TEXT, -- JSON snapshot of graph at this stage
    verdict TEXT,       -- pass | fail | rewrite | unknown
    issues TEXT,        -- JSON array of issues found
    issue_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(run_id) REFERENCES cascade_runs(run_id)
);

CREATE TABLE cascade_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage TEXT,         -- plan | spec | flow | lifecycle | dependency | error | orchestration | gap
    rule_text TEXT,     -- human-readable rule description
    violation_action TEXT,  -- block | rewrite | fallback
    severity INTEGER DEFAULT 1,  -- 1=info, 2=warn, 3=error, 4=critical
    query_template TEXT  -- SQL template to check this rule
);
```

### 11.3 CascadeEngine MemUnit

```
CascadeEngine.Run(command, params) → Tuple3(ok, data, error)

Commands:
  "start"    → start(idea) → creates cascade_run, writes initial SPEC.md, returns run_id
  "stage"    → stage(run_id, stage_name) → executes one graph projection, returns verdict
  "validate" → validate(run_id) → runs all 8 graphs in sequence, returns overall verdict
  "status"   → status(run_id) → returns current_stage + all verdicts
  "rewrite"  → rewrite(run_id) → regenerates SPEC.md with fixes from failed stages
  "commit"   → commit(run_id) → checks all stages passed, allows code generation
  "rules"    → rules(stage) → returns cascade_rules for stage
```

### 11.4 The 8 Graphs as DB Query Templates

Each graph is NOT a UI view — it is a deterministic query transform:

| Graph | Query Template | What it checks |
|-------|---------------|----------------|
| Plan | SELECT capabilities FROM spec_data WHERE domain=? | Every capability maps to a Run() command |
| Spec | SELECT nodes, edges FROM spec_data WHERE domain=? | All classes defined, no missing views |
| Flow | ORDER BY dependency chain | All flows return Tuple3, no missing flow definitions |
| Lifecycle | GROUP BY temporal_phase | All CRUD phases covered, MAX_RETRY defined |
| Dependency | JOIN edges + justification | All dependencies wired, no orphan deps |
| Error | WHERE failure_modes != NULL | All error modes handled, recovery defined |
| Orchestration | Recursive call graph | Single root, no cycles in call tree |
| Gap | LEFT JOIN missing relationships | CRUD closure complete, no missing classes |

### 11.5 Hard Gate Enforcement

GraphEngine.Run("code", ...) is BLOCKED unless cascade_runs.status == "passed".

```python
# In GraphEngine.Run():
if command == "code":
    row = db.execute("SELECT status FROM cascade_runs WHERE run_id=?", (params.get("cascade_run_id"),)).fetchone()
    if not row or row[0] != "passed":
        return Tuple3(0, None, "cascade_not_passed: run CascadeEngine.Run('validate') first")
```

This prevents drift. No code generation without validation.

### 11.6 Self-Correcting Loop

```
Idea
  → Cascade validation (8 graphs)
  → DEGS simulation (run test graph)
  → GraphEngine execution (real run)
  → execution_log
  → failure clustering (AutoGenerator)
  → graph mutation (new fallback nodes)
  → next Cascade run (with new knowledge)
```

This is a self-rewriting execution compiler for structured reasoning systems.

### 11.7 Cascade Stage Execution Flow

```
start(idea):
  1. Create cascade_run row (status=running, current_stage=plan)
  2. Write initial SPEC.md from idea
  3. Return Tuple3(1, {run_id, spec_path}, None)

stage(run_id, stage_name):
  1. Load SPEC.md
  2. Run query template for stage_name
  3. Check cascade_rules for this stage
  4. For each rule:
     - If violation_action=block and rule violated → verdict=fail, set status=blocked
     - If violation_action=rewrite and rule violated → verdict=rewrite
     - If no violations → verdict=pass
  5. Write cascade_stage_results row
  6. Update cascade_runs.current_stage
  7. Return Tuple3(1, {verdict, issues}, None)

validate(run_id):
  1. Run all 8 stages in sequence: plan → spec → flow → lifecycle → dependency → error → orchestration → gap
  2. If any stage verdict=fail → set status=blocked, return Tuple3(0, {stage, issues}, "blocked")
  3. If any stage verdict=rewrite → call rewrite(), re-run failed stages
  4. If all stages verdict=pass → set status=passed, return Tuple3(1, {all_verdicts}, None)
  5. If loop_count > MAX_RETRY → set status=failed, return Tuple3(0, None, "max_retry_exceeded")

commit(run_id):
  1. Check cascade_runs.status == "passed"
  2. If not → return Tuple3(0, None, "cascade_not_passed")
  3. If yes → return Tuple3(1, {run_id, allowed: True}, None)
  4. GraphEngine can now accept Run("code", ...)
```
