# EFL Brain — Self-Learning Code Repair Engine

## What this is

A database-native AI system that breaks code, fixes it, learns rules, detects gaps, and assembles from proven components.

## Files

| File | Purpose |
|------|---------|
| `efl.py` | Single entry point — all commands run from here |
| `efl_brain.db` | SQLite database containing everything: methods, classes, units, graph, expectations, diffs |
| `efl_ram_ai.py` | The AI model code (also ingested into the database) |

## What's in the database

- **2,070 methods** — one row per method, fixable via SQL
- **132 classes** — from MySQL + efl_ram_ai + engine scripts
- **225 compute units** — groups of methods forming pipelines
- **2,703 graph edges** — call relationships (internal, dispatch, cross-class)
- **Expectation graph** — what SHOULD exist per domain
- **Diff results** — what's MISSING (expected minus existing)
- **Execution log** — runtime success/failure tracking

## Commands

```bash
python3 efl.py build          # Rebuild everything from scratch (MySQL + scripts + graph)
python3 efl.py status         # Show database summary
python3 efl.py query repair   # Find methods/classes/units for a domain
python3 efl.py trace BrkAI.Repair  # Trace method dependencies
python3 efl.py reuse scan_fix_verify  # Find reusable patterns
python3 efl.py diff repair    # Find gaps in repair domain
python3 efl.py diff           # Diff all domains
python3 efl.py exec BrkAI.Repair  # Execute a method from the database
python3 efl.py pipeline       # Run the full orchestrator pipeline (7 steps, ~2s)
```

## Architecture

```
CODE → METHODS → COMPUTE_UNITS → GRAPH → EXPECTATION GRAPH
                                              ↓
                                         DIFF ENGINE
                                              ↓
                                      MISSING = EXPECTED - EXISTING
                                              ↓
                                      IMPLEMENTATION PLAN
                                      ├── CREATE (new methods)
                                      ├── ASSEMBLE_FROM_PARTS
                                      ├── CREATE_EDGE (wire connections)
                                      └── REUSE (proven components)
                                              ↓
                                      EXECUTE → LOG → UPDATE
                                              ↓
                                      RE-DIFF (coverage increases)
```

## Domains tracked

repair, generate, parse, scan, db, test, learn, gui, fault_inject, orchestrate

---

## Agent Graph Engine — Cognitive Substrate

The `Efi_agent_graph.py` file is a living-agent graph engine that auto-discovers the architecture of the `efl_brain/` codebase. Each node is a tiny agent with sensors, drives, memory, survival, and attention. No LLM — all "feelings" are numeric state variables that drive movement.

### Primitives

| Primitive | Class | Purpose |
|-----------|-------|---------|
| Agent Node | `AgentNode` | Graph vertex with sensors (taste, touch, vision, smell, pain, hunger), drives (curiosity, fear, confidence, reward, success, failure), memory (experiences, visits, last seen), survival (health, age, generation, alive), attention (focus weight, novelty) |
| Edge | `Edge` | Typed directed connection: CONTAINS, DEFINES, IMPORTS, CALLS, ASSOCIATES |
| Prediction Link | `PredictionLink` | TD-learning style learned edge — predicts expected reward/pain of moving A→B, updated from actual outcomes with adaptive alpha |
| World Model | `WorldModel` | Compressed summary of observed graph state — node types seen, avg reward/pain/confidence, high-value nodes, dangerous nodes, explored fraction |
| Goal System | `GoalSystem` + `Goal` | Explicit goals with target type/id, priority, progress, completion/failure tracking. Injects hunger/curiosity into nodes to steer the agent |
| Emotional State | `EmotionalState` | Composite mood (0.0–1.0), arousal, frustration, trend detection (rising/falling/stable), exploration bias that modulates curiosity-driven random overrides |
| Consolidation | `Consolidation` | Sleep phase — prunes weak prediction links (confidence < 0.15), compresses experience memory, refreshes novelty for unvisited nodes, decays fear globally. Runs every 30 steps |
| Adversarial Agent | `AdversarialAgent` (Yin) | Attacks the yang agent: poison_links (inverts reward/pain), inject_fear (raises fear on high-confidence nodes), block_nodes (temporarily blocks high-value nodes), false_reward (inflates reward on low-value nodes). Intelligent targeting: attacks the yang's strengths |
| MySQL Connector | `MysqlKnowledgeConnector` | Connects to `vb_shared.learned_rules` (10,540 rows), extracts keywords from pattern/trigger/fix_action, matches to node names/class names/method names, seeds prediction links with real-world confidence weighted by success_count. Degrades gracefully if MySQL unavailable |

### Simulation modes

| Mode | Method | What it does |
|------|--------|-------------|
| Simulate | `Simulate()` | Original agent walk — observe, predict, act, measure (50 steps) |
| Full Simulate | `FullSimulate()` | 11-step cognitive loop: observe → predict → attend → plan → act → measure → self-modify → world model → emotion → goals → consolidate (200 steps) |
| Yin/Yang | `YinYangSimulate()` | 12-step adversarial loop: same as FullSimulate but yin attacks between steps. Yang defends via consolidation. Tracks resisted attacks and battle log |

### Planning

- **MultiStepPlan()** — 2-hop lookahead scoring. Evaluates not just the next node but the best sub-node reachable from it. Strong anti-loop penalty (0.5 per visit). Goal-directed BFS pathfinding toward target types.
- **FindNearestNodeOfType()** — BFS from a node to find the nearest node of a target type (CONFIG, MEMUNIT, FUNCTION).
- **PathToTarget()** — BFS shortest path between two nodes.
- **AdaptiveAlpha()** — Learning rate decays as confidence grows (0.3 → 0.01). Fresh links learn fast; confident links refine slowly.
- **Confidence boost** — Accurate predictions (error < 0.2) boost the source node's confidence by +0.08.

### Dispatch commands (Run entry point)

```
blast         — blast radius of a node (what breaks if it dies)
reaches       — what can reach this node (reverse BFS)
path          — shortest path A → B
all_paths     — all paths A → B
boot          — real boot sequence (topological sort by imports)
communities   — subsystem clusters (label propagation)
central       — degree centrality ranking
influence     — forward reach ranking
islands       — disconnected components
simulate      — basic agent simulation
cycles        — cycle detection
export        — full graph export as JSON
predict       — predict best next node from a node
attend        — boost attention on a node
self_modify   — manually trigger a self-modify step
world_model   — current world model summary
goals         — goal system summary (or add a goal with action='add')
full_simulate — full cognitive substrate simulation
emotion       — current emotional state
consolidation — trigger a consolidation cycle
plan          — multi-step planning from a node
yin_yang      — adversarial yin/yang simulation
seed_mysql    — seed prediction links from MySQL learned_rules
```

### Verified results

**Full Simulate (TASK-043, no adversary):**
- 200 steps, 53/95 unique nodes (55.8% coverage), 100% explored
- 4/4 goals completed (CONFIG, MEMUNIT, FUNCTION, Explore 80%)
- Avg confidence 0.83, avg reward 0.48, mood 0.95
- 117 prediction links, 6 edges grown, 319 links pruned across 6 sleep cycles
- 76 FUNCTION nodes reached, 3 MEMUNIT, 15 CLASS

**Yin/Yang (TASK-044, under adversarial attack):**
- 200 steps, 83 yin attacks (22 poison, 21 fear, 17 block, 23 false reward)
- Yang still completed 4/4 goals, 65% coverage, mood 0.95
- Resisted 10 blocked-node encounters by finding alternative paths
- Consolidation pruned 159 poisoned links, decayed 13.1 fear across 6 sleep cycles

**MySQL Knowledge Seeding:**
- Connected to `vb_shared`, loaded 200 learned_rules
- Seeded 590 prediction links with real-world confidence values
- Keyword extraction from pattern/trigger/fix_action text, matched to node/class/method names

### Supporting graph files

| File | Purpose |
|------|---------|
| `Efi_agent_graph.py` | Main agent graph engine (~2670 lines) |
| `Efi_agent_graph.json` | Exported graph state (nodes, edges, derived, cognitive substrate) |
| `Efi_code_graph.py` | Simpler typed-state graph (Node + Edge + State primitives, cycle detection) |
| `Efi_code_graph.json` | Exported typed-state graph |
| `Efi_graph_viewer.py` | Tkinter visualizer — color-coded nodes/edges (CONFIG=purple, MEMUNIT=green, CLASS=blue, cycles=red) |
| `Efi_boot_graph.py` | Boot sequence graph |
| `Efi_agent_brain.py` | Agent brain that drives the graph |
| `Efi_agent_brain.json` | Brain state export |

---

## The Three Brothers — Connector, Repair, Orchestrator

The efl_brain system has three "brothers" — independent modules that communicate through `efl_brain.db` (the dinner table). No brother imports another brother. They leave notes on the dinner table; the next brother reads them.

### Architecture: Database as the Dinner Table

```
Connector Brother          Repair Brother           Solution Engine
     ↓                          ↓                         ↓
 efl_brain.db              efl_brain.db              efl_brain.db
 (the dinner table)        (the dinner table)        (the dinner table)
     ↑                          ↑                         ↑
     └────────── Orchestrator Brother ──────────┘
                    (the only one that imports all)
```

### Connector Brother (`Efi_connector.py`)

Reads `efl_brain.db` and builds the agent graph from database rows — no AST walking, no file system scanning, just SQL.

- **Classes table** → CLASS or MEMUNIT nodes (detects MEMUNIT by checking for `Run()` method + `self.state` in class code)
- **Methods table** → FUNCTION nodes
- **Graph edges table** → CALLS edges
- **Class → method** → DEFINES edges
- Writes the resulting graph to `agent_prediction_links` via BrainDb

**Verified:** 2569 nodes (83 CLASS, 97 MEMUNIT, 2389 FUNCTION), 5398 edges (2695 DEFINES, 2703 CALLS), 5398 prediction links written.

### Repair Brother (`Efi_repair.py`)

Takes diff gaps + learned fixes + fragility data and generates actual code fixes.

- Reads `diff_results` (MISSING gaps), `learned_fixes` (patterns with confidence), `agent_prediction_links` (fragility)
- For each gap: finds best matching learned fix by keyword overlap, generates method/edge/unit stub, validates with AST
- Writes generated fixes to `agent_generated_fixes` table

**Verified:** 40 gaps → 40 fixes generated, 39 valid (AST-validated), 5 high confidence, 40 written to DB.

### Orchestrator Brother (`Efi_orchestrator.py`)

The single entry point that runs the full pipeline. The only module that imports all brothers.

| Step | Name | What it does | Time |
|------|------|-------------|------|
| 1 | build | Check if DB has data (skip if yes) | 0.005s |
| 2 | connect | Build agent graph from DB rows | 0.22s |
| 3 | simulate | Run cognitive substrate simulation (100 steps) | 1.1s |
| 4 | diff | Find gaps (expected vs existing) | 0.001s |
| 5 | repair | Generate code fixes for gaps | 0.01s |
| 6 | scan | Scan for config rule violations | 0.86s |
| 7 | report | Aggregate all results | 0.002s |

**Total: 7/7 steps OK, ~2.2s**

### BrainDb (`Efi_brain_db.py`)

The dinner table itself. Wraps `efl_brain.db` with read/write methods for:
- `agent_prediction_links` — learned edges between nodes
- `agent_world_model` — compressed summary of observed graph state
- `agent_emotional_state` — mood, arousal, frustration, trend
- `agent_violations` — config rule violations found by the solution engine
- `agent_blast_radius` — impact analysis of each node
- `agent_generated_fixes` — code fixes generated by the repair brother

### VBStyle Compliance

All three brothers follow VBStyle:
- Ghost header + VBStyle header on every file
- Class header + method docstrings
- `Run()` dispatch with Tuple3 `(ok, data, error)` returns
- No decorators, no `print()`, no hardcoded paths
- PascalCase classes, UPPERCASE constants, `self.state` dict
- SQL table names extracted as constants (R7 compliance)
