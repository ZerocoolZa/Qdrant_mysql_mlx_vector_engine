# 8-Graph Workflow Pipeline — Reason Before You Code

> **Core thesis:** Don't go Idea → Code → Oops → Refactor.
> Walk through 8 graph views first. Each is a checkpoint where you ask
> "is this right?" before committing further. The graphs are NOT the product.
> The reasoning pipeline IS the product. The graphs are visualization.

---

## Pipeline Overview

```
Idea → Plan → Spec → Flow → Lifecycle → Dependencies → Orchestration → Gap → Code
```

## The 8 Graphs (in order)

| # | File | Question | What it shows | Cost of change |
|---|------|----------|---------------|----------------|
| 1 | plan_graph.py | What are we building? | High-level capabilities, not classes | Erase a bubble |
| 2 | spec_graph.py | What exactly exists? | Classes, nodes, edges, categories | Redesign classes + edges |
| 3 | spec_flow.py | How does it move? | Execution paths, step-by-step logic | Rewrite execution logic |
| 4 | lifecycle_graph.py | When does it run? | Temporal phases, swim-lane ordering | Reorder temporal phases |
| 5 | dep_graph.py | Why does it connect? | Edge justifications, dependency chains | Break chains |
| 6 | error_graph.py | Where does it fail? | Error paths, failure modes, recovery routes | Add error handling |
| 7 | orch_graph.py | Who calls who? | Call tree, roots, leaves, dispatch hierarchy | Restructure call tree |
| 8 | gap_graph.py | What's missing? | Missing pairs, CRUD closure, coverage areas | Discover you built the wrong thing |

---

## Key Principles

1. **Plan Graph first** — cheapest place to be wrong. No classes committed yet.
2. **Gap Graph last** — most expensive. By then you've committed to everything.
3. **Each graph is a different lens** — same domain, different perspective.
4. **AI agents reason differently over each view** — one pass asks "what exists?", another asks "what breaks if this node disappears?", another asks "who owns this responsibility?"
5. **The graphs are NOT the product** — the reasoning pipeline IS the product. The graphs are visualization.
6. **Most code generators skip this** — they go Idea → Code → Oops → Refactor. This pipeline prevents that.

---

## Mental Models

- Plan Graph → the dream
- Spec Graph → the structure
- Flow Graph → the movement
- Lifecycle Graph → the timeline
- Dependency Graph → the support beams
- Orchestration Graph → the command chain
- Error Graph → the failure map
- Gap Graph → the holes

---

## Step-by-Step Guide

### Step 1: PLAN GRAPH — "What are we building?"

Define capabilities, NOT classes. Bubbles and arrows. No code.

```
+ Capability: SearchEngine — Run() dispatch to keyword/semantic/hybrid search
+ Capability: Indexer — scan folders, extract classes/methods/BCL headers
+ Capability: Scheduler — auto-run utilities on timer/event triggers
```

**Output:** `plan_graph.py` — Tkinter viewer showing capability bubbles.
**Cost of change:** Erase a bubble. 5 seconds.
**Question to ask:** "Is this what we're building? Anything missing?"

### Step 2: SPEC GRAPH — "What exactly exists?"

Turn capabilities into classes, nodes, edges, categories.

```
CLASSES:
  SearchEngine → [keyword, semantic, hybrid, _build_cmd, _execute]
  Indexer → [scan_file, scan_folder, _parse_ast, _extract_headers]
  Scheduler → [start, stop, fire_event, _run_trigger]

EDGES:
  SearchEngine → Indexer (uses for file scanning)
  Scheduler → SearchEngine (triggers on interval)
```

**Output:** `spec_graph.py` — class boxes with edges.
**Cost of change:** Redesign classes + edges. 30 seconds.
**Question to ask:** "Are these the right classes? Are the edges correct?"

### Step 3: SPEC FLOW — "How does it move?"

Trace execution paths step by step.

```
FLOW: keyword_search
  1. Run("keyword", {keyword: "eyes", table: "learned_rules"})
  2. → _build_cmd("keyword", params)
  3. → _execute(cmd)
  4. → _parse_concatenated_json(output)
  5. → return (1, results, None)
```

**Output:** `spec_flow.py` — step-by-step flow diagram.
**Cost of change:** Rewrite execution logic. 1 minute.
**Question to ask:** "Is this the right flow? Any unnecessary steps?"

### Step 4: LIFECYCLE GRAPH — "When does it run?"

Temporal phases, swim-lane ordering.

```
PHASE 1 (BOOT):     Config loads → Indexer scans → DB connects
PHASE 2 (IDLE):     Scheduler waits → Event listener active
PHASE 3 (TRIGGER):  Scheduler fires → Orchestrator dispatches → Utility runs
PHASE 4 (REPORT):   Results collected → StatsReport generates → State updated
PHASE 5 (SHUTDOWN): Connections close → State persisted → Cleanup
```

**Output:** `lifecycle_graph.py` — swim-lane timeline.
**Cost of change:** Reorder temporal phases. 1 minute.
**Question to ask:** "Is this the right order? Can phases run in parallel?"

### Step 5: DEPENDENCY GRAPH — "Why does it connect?"

Edge justifications, dependency chains.

```
SearchEngine DEPENDS_ON Indexer (needs file scan results)
Scheduler DEPENDS_ON Orchestrator (needs dispatch)
Orchestrator DEPENDS_ON Config.TRIGGERS (needs trigger definitions)
```

**Output:** `dep_graph.py` — dependency chains with justifications.
**Cost of change:** Break chains. 2 minutes.
**Question to ask:** "Why does this depend on that? Can we break the chain?"

### Step 6: ERROR GRAPH — "Where does it fail?"

Error paths, failure modes, recovery routes.

```
SearchEngine.FAILURE: msearch binary not found → return (0, None, ("binary_missing", path, 0))
Indexer.FAILURE: file too large → skip, log, continue
Scheduler.FAILURE: trigger crashes → on_fail="continue" → log, keep running
```

**Output:** `error_graph.py` — failure map with recovery routes.
**Cost of change:** Add error handling. 2 minutes.
**Question to ask:** "What happens when this fails? Is the recovery correct?"

### Step 7: ORCHESTRATION GRAPH — "Who calls who?"

Call tree, roots, leaves, dispatch hierarchy.

```
ROOT: Scheduler
  ├── Orchestrator
  │   ├── Indexer
  │   ├── VbsScanner
  │   ├── Cleaner
  │   ├── DiffCheck
  │   ├── StatsReport
  │   ├── DomAudit
  │   ├── PreFlight
  │   ├── ContentExtract
  │   └── ErrorTracker
  └── MSearch (standalone)
```

**Output:** `orch_graph.py` — call tree with roots and leaves.
**Cost of change:** Restructure call tree. 5 minutes.
**Question to ask:** "Is this the right hierarchy? Who owns this responsibility?"

### Step 8: GAP GRAPH — "What's missing?"

Missing pairs, CRUD closure, coverage areas.

```
GAPS:
  SearchEngine has no DELETE capability (CRUD incomplete)
  Scheduler has no PAUSE/RESUME (lifecycle incomplete)
  Indexer has no INCREMENTAL mode (only full scan)
  No utility for AUTO-REPAIR (detect + fix in one pass)
```

**Output:** `gap_graph.py` — holes and missing coverage.
**Cost of change:** Discover you built the wrong thing. Most expensive.
**Question to ask:** "What's missing? Did we build the right thing?"

---

## Implementation

- All 8 files live in the domain folder (e.g., `dom_compression/`)
- Each is a standalone Tkinter viewer
- All share the same data: CLASSES, EDGES, CATEGORIES, FLOWS
- Data-driven — swap domain data without touching rendering logic
- Gap graph includes semantic detection (missing pairs, CRUD closure, coverage areas) not just edge analysis

## File Locations

Existing 8-graph implementations (Dom_Graph domain):
- `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/Dom_Graph_Plan.py`
- `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/Dom_Graph_Spec.py`
- `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/Dom_Graph_Flow.py`
- `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/Dom_Graph_Lifecycle.py`
- `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/Dom_Graph_Dep.py`
- `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/Dom_Graph_Error.py`
- `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/Dom_Graph_Orch.py`
- `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/Dom_Graph_Gap.py`

## Cognitive Loop (companion reasoning engine)

The 8-graph pipeline is complemented by the Cognitive Loop Walker:

```
Problem → Question → Answer → Constraint → Mistake → Solution → Verify
```

- File: `/Users/wws/Qdrant_mysql_mlx_vector_engine/dom_compression/cognitive_loop_walker.py`
- DB: `v20_hybrid_best.db` — `decision_nodes` + `decision_edges` tables
- Walks the 7-step reasoning path, logs every step to `execution_log`

## Workflow Domain (project management layer)

- File: `/Users/wws/Qdrant_mysql_mlx_vector_engine/dom_compression/Dom_workflow.py`
- Commands: `prj` (project mgmt), `index` (file indexing), `config` (Config.py generation), `validate` (VBStyle check), `report` (reporting), `status` (domain status)
- All code lives in DB, .py is a bootstrap runner

---

## TOTAL TIME: 15-20 minutes of reasoning

Compare with: **Idea → Code → Oops → Refactor = 2+ hours of rework.**

The graphs are cheap to change. Code is expensive to change.
Reason in graphs first. Write code last.
