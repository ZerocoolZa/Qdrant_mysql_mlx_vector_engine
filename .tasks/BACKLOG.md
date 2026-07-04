# Backlog

## TASK-112: Evidence-Provenance Confidence — 4-Stream Vector, Never Collapsed
**Priority:** P1 | **Tags:** reasoning-graph, confidence, evidence, provenance, activation, stage-2
**Updated:** 2026-07-05 13:00

Add evidence-provenance confidence to the explicit reasoning graph. Each
node carries a VECTOR of 4 independent evidence streams (structural,
semantic, topological, runtime), each preserved with its source. The
overall confidence is computed from them but the individual streams are
NEVER discarded — enabling diagnosis: "Why is confidence low?" ->
"Runtime evidence is the weak link."

### Architecture Document

`/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Gui/EXPLICIT_REASONING_GRAPH.md`
(Stage 2)

### Current State

- Stage 1 COMPLETE: 417 nodes, 2,151 edges, 5 layers wired
- Activation spreading works but is binary (active/inactive)
- Confidence data EXISTS in MySQL but is not used:
  - code_index.authority_score (1-10) -> structural
  - code_index.survival_score (0.3-0.95) -> topological
  - know_nodes.confidence (0.0-1.0) -> semantic
  - know_answers.confidence (0.85-0.95) -> semantic
  - know_memory_units.stability_score (0.0-1.0) -> runtime

### Plan

- Step 1: Add `evidence` dict to every node: {structural, semantic, topological, runtime}
- Step 2: Add `confidence` as a COMPUTED property (not stored) = weighted_average(evidence)
- Step 3: Load evidence from MySQL in OnLoadLayers:
  - BCLIR classes: structural = authority_score/10, topological = survival_score
  - BCL rules: semantic = survival_score
  - Graph nodes: topological = survival_score
  - Know nodes: semantic = confidence field
  - Memory units: runtime = stability_score
- Step 4: Modify Activate() to propagate evidence PER-STREAM:
  - Each stream decays independently: target[stream] = source[stream] * edge_weight
  - Overall confidence = weighted_average (weights configurable)
- Step 5: Add evidence display in HUD:
  ```
  ErrorCapture [act=0.92 conf=0.81]
    struct=1.00  sem=0.73  topo=0.92  rt=0.61
  ```
- Step 6: Add "Explain" button — shows full evidence chain with per-stream breakdown
- Step 7: Confidence-weighted backprop: path cost = 1/(weight * confidence)
- Step 8: Visual: node glow = activation, border thickness = confidence,
  border color = weakest evidence stream (red=weak, green=strong)
- Key files: `QuestionSpaceExplorerV2.py`
- Risks: (1) confidence propagation may dampen activation — need tuning; (2) some layers lack evidence data — use default 0.5; (3) per-stream propagation is more computation — may need optimization

---

## TASK-117: Magnetic Clustering Engine — CUs Emerge from Method Affinity
**Priority:** P1 | **Tags:** reasoning-graph, magnetic, clustering, emergence, computational-units, affinity, stage-3-foundation
**Updated:** 2026-07-05 14:00

Computational Units are not manually declared. They EMERGE through magnetic
attraction between methods. Methods have magnetic signatures (4-affinity
vectors), and compatible methods "snap together" into clusters. When a
cluster seals (internal_calls >> external_calls), it becomes a CU. This
is the foundation for Stage 3 — CUs must exist before they can execute.

### Architecture Document

`/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Gui/EXPLICIT_REASONING_GRAPH.md`
(Architectural Principle 6: Magnetic Clustering)

### The Magnetic Signature (4 affinities, parallel to evidence provenance)

| Affinity | Computed from | Source |
|---|---|---|
| Structural | params compatibility, return type match | vb_methods.params, vb_classes.return_type |
| Behavioral | called together, internal_calls, co_occurrence | bcl_units.internal_calls, code_co_occurrence |
| Semantic | same domain, same role, description similarity | vb_classes.domain, vb_classes.role |
| Historical | survived versions together | code_index.survival_score |

Same pattern as evidence provenance: 4 independent streams, never collapsed.

### What Already Exists

- bcl_units table IS the clustering result (24 units, is_closed field = magnetic seal)
- unit_3: ZramStorageAdapter (9 methods, 8 internal, 0 external, SEALED)
- unit_1: 7 classes stuck together (24 methods, subsystem forming, NOT sealed)
- MagneticSearchEngine, MagneticCluster, MagneticRank classes exist in codebase
- code_co_occurrence has behavioral data
- code_index has authority_score and survival_score

### Plan

- Step 1: Create `MagneticClusteringEngine.py` — VBStyle class:
  - Run("compute_affinity", {"method_a": "...", "method_b": "..."}) -> (1, {structural, behavioral, semantic, historical, overall}, None)
  - Run("cluster", {"threshold": 0.7}) -> discovers CUs from method pool
  - Run("seal_check", {"unit_id": "..."}) -> checks if cluster is sealed
  - Run("grow", {}) -> attempts to attract new methods to open clusters
  - Run("read_state", {}) / Run("set_config", {})
- Step 2: Compute magnetic signature for every method in vb_methods:
  - structural: param type overlap, return type match
  - behavioral: co_occurrence count, internal_calls from bcl_units
  - semantic: domain/role match from vb_classes
  - historical: survival_score from code_index
- Step 3: Cluster methods by affinity (above threshold -> same cluster)
- Step 4: Detect sealed clusters (internal_calls >> external_calls) -> CUs
- Step 5: Wire discovered CUs into reasoning graph (replaces manual CU loading)
- Step 6: CUs carry magnetic provenance: which methods, what affinity, is_open/is_closed
- Step 7: Growth mode: open clusters attract new methods, re-evaluate periodically
- Step 8: Visual: in 3D graph, show magnetic attraction as edges pulling methods together
- Key files: new `MagneticClusteringEngine.py`; modify `QuestionSpaceExplorerV2.py`
- Risks: (1) Computing affinity for 13,818 methods is O(n^2) — need sampling or indexing; (2) Threshold tuning — what affinity seals a cluster?; (3) Existing bcl_units may not match re-computed clusters — reconcile

---

## TASK-113: Executable Computational Units as Verbs — CUs Can Execute() on Activation
**Priority:** P1 | **Tags:** reasoning-graph, computational-units, execution, verbs, stage-3
**Updated:** 2026-07-05 13:00

Wire 33 computational units into the reasoning graph. CUs are VERBS
(operators that transform state), not nouns (facts that store it).
Activation flows through nouns until it reaches a verb — at which point
reasoning becomes action. When activation exceeds threshold (after policy
check), a CU can Execute() its underlying class method.

### Architecture Document

`/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Gui/EXPLICIT_REASONING_GRAPH.md`
(Stage 3 + Stage 3.5)

### Noun/Verb Distinction

- Nouns: ErrorCapture, Run, read_state, "Tuple3 return pattern" (store facts)
- Verbs: CU_Think, CU_Ask, CU_Learn, CU_ErrorCapture (transform state)

### Current State

- 33 CUs exist in CODEBASE.computational_units — all verbs:
  CU_Bootstrap, CU_ClassLoader, CU_AuthorityDispatch, CU_ErrorCapture,
  CU_QNARetrieval, CU_EventSystem, CU_Arbitration, CU_AttractorCollapse,
  CU_EventDrain, CU_EventHandlers, CU_Think, CU_Generate, CU_Learn,
  CU_Embed, CU_GraphBuild, CU_GraphReason, CU_GraphLearn, CU_Sensory,
  CU_MemUnit, CU_CommanderRoute, CU_EmbedderIndex, CU_MultiThink,
  CU_MultiThinkBranch, CU_ReasonerThink, CU_ThinkPipeline, CU_Autonomous,
  CU_Ask, CU_TestModel, CU_Validation, CU_LearnerLoop, CU_EventBus, +3
- Each CU has: unit_name, description, class_id, method_id, status
- Currently NOT loaded into the reasoning graph

### Plan

- Step 1: Load 33 CUs as nodes with layer="comp_unit" and kind="verb" in OnLoadLayers
- Step 2: Wire CU -> BCLIR class edges (CU_ErrorCapture -> ErrorCapture class)
- Step 3: Create `CuExecutor.py` — VBStyle class that safely invokes CUs:
  - Import the actual Python class by name
  - Instantiate with (mem, db, param)
  - Call Run(command, params)
  - Capture Tuple3 result: (1, data, None) or (0, None, error)
  - Feed result back into graph as new evidence (updates runtime stream)
- Step 4: Add EXEC_THRESHOLD slider to toolbar (default 0.7)
- Step 5: Add "Execute Mode" toggle — when ON, high-activation CUs can execute
- Step 6: Double-click CU node to execute (requires Execute Mode ON + policy check)
- Step 7: Log execution results in info panel:
  ```
  EXECUTE: CU_ErrorCapture (verb)
    -> ErrorCapture.Run("capture", {})
    -> (1, {errors_captured: 3}, None)
    -> Feeding back: runtime evidence +0.15 for ErrorCapture
    -> New facts: 3 errors added to know_problems
  ```
- Step 8: Safety: execution requires Execute Mode ON + policy pass (TASK-116)
- Key files: `QuestionSpaceExplorerV2.py`, new `CuExecutor.py`
- Risks: (1) Executing arbitrary code is dangerous — require explicit enable + policy; (2) CU class may not be importable — handle ImportError; (3) Side effects — dry-run mode

---

## TASK-116: Policy Layer — Capability vs Permission Guardrail
**Priority:** P0 | **Tags:** reasoning-graph, policy, safety, guardrail, capability, permission, stage-3.5
**Updated:** 2026-07-05 13:00

Add a policy layer between reasoning and action. Capability ("I can") must
be separated from permission ("You may"). Without this, any sufficiently
activated CU would execute — including dangerous ones like CU_DeleteFiles.
Policies are the guardrail that prevents reasoning from causing harm.

### Architecture Document

`/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Gui/EXPLICIT_REASONING_GRAPH.md`
(Stage 3.5)

### Principle

Policies answer: "Should this execute?" — separate from capability.
A CU may be highly activated and fully capable, but if policy says "denied,"
execution stops. Three permission levels: allowed, confirm, denied.

### Plan

- Step 1: Create `PolicyEngine.py` — VBStyle class:
  - Run("check", {"cu_name": "CU_ErrorCapture"}) -> (1, {permission, reason}, None)
  - Run("list", {}) -> all policies
  - Run("set", {"cu_name": "...", "permission": "..."}) -> update policy
  - Run("read_state", {}) / Run("set_config", {})
- Step 2: Default policies:
  - allowed: CU_ErrorCapture, CU_QNARetrieval, CU_GraphReason, CU_Sensory (safe/read-only)
  - confirm: CU_Generate, CU_Learn, CU_ClassLoader, CU_Ask, CU_Embed (costs/writes)
  - denied: CU_DeleteFiles, CU_Autonomous, CU_Bootstrap (dangerous/manual)
- Step 3: Before any CU executes, call PolicyEngine.Run("check", ...)
- Step 4: If "confirm" -> show QInputDialog asking user to approve
- Step 5: If "denied" -> log denial with reason, stop execution
- Step 6: If "allowed" -> proceed to Execute()
- Step 7: Add "Policies" toolbar button -> shows all CU permissions, editable
- Step 8: Policy decisions logged in info panel:
  ```
  POLICY CHECK: CU_DeleteFiles
    -> permission = denied
    -> reason: destructive operation
    -> execution blocked
  ```
- Key files: new `PolicyEngine.py`; modify `QuestionSpaceExplorerV2.py`, `CuExecutor.py`
- Risks: (1) Default policies must be conservative — deny by default for unknown CUs; (2) User can override — make sure overrides are logged

---

## TASK-114: Common Node Interface + Graph/Execution Separation
**Priority:** P2 | **Tags:** reasoning-graph, vbstyle, node-interface, graph-execution-separation, refactor, stage-4
**Updated:** 2026-07-05 13:00

Refactor the reasoning graph so every node is a VBStyle-compliant object
with a common interface. Additionally, separate the graph (knowledge
substrate: "what is connected?") from the execution engine (interpreter:
"what happens next?"). This separation makes the system debuggable and
evolvable.

### Architecture Document

`/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Gui/EXPLICIT_REASONING_GRAPH.md`
(Stage 4)

### Current State

- Nodes are plain dicts: {"id": "...", "label": "...", "layer": "...", ...}
- No common interface — each layer has different fields
- No Execute() or Explain() methods
- Activation logic is in the graph widget, not in nodes
- Graph and execution are tangled together

### Plan

- Step 1: Create `ReasoningNode.py` — VBStyle base class (nouns):
  - state = {id, label, type, kind (noun|verb), layer, activation, evidence (4-stream), connections}
  - Run(command, params) dispatch: activate|execute|explain|read_state|set_config
  - _Activate, _Explain, _Execute (default: not executable), _Confidence (computed from evidence)
- Step 2: Create `CompUnitNode.py` — extends ReasoningNode with real Execute() (verbs)
- Step 3: Create `ReasoningEdge.py` — VBStyle edge with weight, evidence, dimension
- Step 4: Create `ReasoningGraph.py` — graph manager (knowledge substrate ONLY):
  - Holds nodes as ReasoningNode objects
  - Activate(node_id) -> calls node.Run("activate", {})
  - Spread() -> propagates activation + evidence across edges
  - Explain(node_id) -> calls node.Run("explain", {})
  - NO execution logic here
- Step 5: Create `ExecutionEngine.py` — VBStyle class (interpreter/actor ONLY):
  - Reads graph state
  - Finds CUs with activation > EXEC_THRESHOLD
  - Calls PolicyEngine.Run("check", ...) for each
  - If permitted: calls CuExecutor.Run("execute", ...)
  - Feeds results back into graph as new evidence
  - NO graph structure logic here
- Step 6: Refactor QuestionSpaceExplorerV2.py:
  - Replace dict-based state with ReasoningGraph
  - Wire ExecutionEngine for CU execution
  - Add "Explain" button -> node.Run("explain", {}) -> full evidence chain
- Step 7: Every node is polymorphic: Activate(), Explain(), Run(), ReadState()
- Key files: new `ReasoningNode.py`, `CompUnitNode.py`, `ReasoningEdge.py`, `ReasoningGraph.py`, `ExecutionEngine.py`; modify `QuestionSpaceExplorerV2.py`
- Risks: (1) Large refactor — must preserve all existing features; (2) Performance — object overhead vs dict access; (3) VBStyle compliance — no @property, no self._, Tuple3 returns; (4) Graph/exec separation must be clean — no backdoor execution from graph

---

## TASK-115: Full Brain Wiring — All MySQL Knowledge Layers into Reasoning Graph
**Priority:** P2 | **Tags:** reasoning-graph, full-brain, knowledge-graph, scaling, stage-5
**Updated:** 2026-07-05 12:00

Wire all available MySQL knowledge layers into the reasoning graph. Target:
~2,500 curated nodes and ~37,000+ edges — a real-scale explicit reasoning
graph covering structure, semantics, topology, computation, and knowledge.

### Architecture Document

`/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Gui/EXPLICIT_REASONING_GRAPH.md`
(Stage 5)

### Current State

- 417 nodes, 2,151 edges (Stage 1)
- Available but unwired:
  - 33 computational units (CODEBASE)
  - 24 BCL units (vb_code_test.bcl_units)
  - 173 method inventory entries (method_inventory)
  - 1,694 knowledge Q-nodes + 1,516 edges (know_nodes + know_edges)
  - 32,741 knowledge answers (know_answers) — curate top 200
  - 108,037 knowledge questions (know_questions) — curate top 200
  - 16 memory units with stability scores (know_memory_units)
  - 399 known problems + 381 solutions (know_problems + know_solutions)
  - 19 component ontology entries (component_ontology)
  - 50 session graph nodes + 33,775 edges (graph_nodes + graph_edges) — curate top 500
  - 7 MU execution nodes + 5 edges (mu_nodes + mu_edges)
  - 11 inference rules + 9 decision trees (inference_rules + decision_trees)

### Plan

- Step 1: Create `LayerLoader.py` — VBStyle class that loads all layers from MySQL with curation limits
- Step 2: Wire Computational Units (33 nodes, CU->class edges)
- Step 3: Wire BCL Units (24 nodes, unit->class edges with method_types_json)
- Step 4: Wire Method Inventory (173 nodes, method->authority edges)
- Step 5: Wire Knowledge Graph (200 curated Q-nodes by confidence, 1,516 edges)
- Step 6: Wire Memory Units (16 nodes, stability_score as confidence)
- Step 7: Wire Problems/Solutions (399+381 nodes, problem->solution edges)
- Step 8: Wire Component Ontology (19 nodes, component->role edges)
- Step 9: Wire Session Graph (50 nodes, top 500 edges by weight)
- Step 10: Wire MU Execution (7 nodes, 5 edges: BLOCKS/DEPENDS/PRODUCES/SUPPORTS)
- Step 11: Wire Inference (11 rules, 9 decision trees)
- Step 12: Cross-layer activation: inquiry -> CU -> BCLIR -> BCL -> KnowGraph -> Problem -> Solution
- Step 13: Spatial clustering in 3D: layer-zones (inquiry=center, BCLIR=ring1, BCL=ring2, etc.)
- Step 14: Level-of-detail rendering: only render edges near camera for 37K+ edges
- Key files: new `LayerLoader.py`; modify `QuestionSpaceExplorerV2.py`
- Risks: (1) 2,500 nodes may need spatial clustering for usable 3D; (2) 37K edges need LOD rendering; (3) know_questions (108K) too large — curate; (4) Performance at scale — may need to reduce tick rate

---

## TASK-085: DB Entry Gate — Cognitive Loop + Registry Enforcement (Prevent AI Pollution)
**Priority:** P0 | **Tags:** critical, db-integrity, cognitive-loop, registry, anti-pollution, guardrail
**Updated:** 2026-06-23 15:47

## CRITICAL — Prevents AI from corrupting v20_hybrid_best.db

**Created:** 2026-06-23
**Session:** /Users/wws/.local/share/devin/cli/summaries/history_6162b4005b3642ac.md
**Context:** Devin violated trust by inserting workflow domain code + nodes into the DB without explicit permission. This task captures the user's design for a gate system that would have prevented that.

## The Problem

An AI agent can insert anything into the DB at any time — typos, unregistered domains, code without reasoning, nodes without cognitive loops. This causes:
- Domain pollution (workfow vs workflow vs WORKFLOW)
- Code without reasoning entering the DB
- Tables becoming inconsistent
- Loss of trust in the system
## TASK-088: Real CoreML On-Device Training via MLUpdateTask
**Priority:** P1 | **Tags:** coreml, training, mlupdatetask, on-device
**Updated:** 2026-06-28 01:50

Prove CoreML `MLUpdateTask` training actually works end-to-end. Phase 1: synthetic-data proof-of-concept (build updatable `.mlmodel` via coremltools `make_updatable` + Adam + cross-entropy, train via Python `coremltools`, verify weights change). Phase 2: adapt to user's real `BestMapper(384, 40)` PyTorch model + `token_registry.db` data. Swift `MLUpdateTask` runner included for production-real on-device training (requires Xcode to compile — currently only CommandLineTools installed).

**Files:** `/Users/wws/Qdrant_mysql_mlx_vector_engine/CoreML_Training/` (Config.py, UpdatableBuilder.py, SyntheticDataGen.py, CoreMLTrainer.py, main.py, run_training.swift, README.md)

### Plan

- Step 1: Create `CoreML_Training/` folder + `Config.py` (VBStyle, all paths/HPs as constants)
- Step 2: `UpdatableBuilder.py` — builds a tiny FC classifier (4→8→3) as updatable `.mlmodel` via `NeuralNetworkBuilder` + `make_updatable` + `set_categorical_cross_entropy_loss` + `set_adam_optimizer` + `set_epochs`
- Step 3: `SyntheticDataGen.py` — generates 200 synthetic labeled tensors (4-dim input, 3-class labels) as `MLArrayFeatureProvider` batch
- Step 4: `CoreMLTrainer.py` — runs the actual CoreML training via `coremltools` Python API (loads updatable model, runs update task, captures epoch-end progress, saves trained model)
- Step 5: `main.py` — VBStyle entry point with `Run()` dispatch: `build` → `gendata` → `train` → `verify`
- Step 6: `run_training.swift` — native Swift `MLUpdateTask` + `MLUpdateProgressHandlers` runner (production-real; requires Xcode to compile)
- Step 7: `README.md` — documents the proof + how to run + Phase 2 path
- Step 8: Verify — `py_compile` passes, no print/decorators/self._, all Tuple3, run end-to-end, confirm `isUpdatable: True` and weights differ from baseline
- Key files: `Config.py`, `UpdatableBuilder.py`, `SyntheticDataGen.py`, `CoreMLTrainer.py`, `main.py`, `run_training.swift`
- Risks: (1) coremltools 9.0 may have moved `NeuralNetworkBuilder` API — verify imports; (2) `MLUpdateTask` Python bindings may require specific spec version; (3) Swift runner can't be compiled without Xcode

---

## TASK-087: Qdrant + MySQL + MLX Vector Engine for Devin Chat (13 Classes)
**Priority:** P1 | **Tags:** qdrant, mysql, mlx, embeddings, devin-sync, vector-engine
**Updated:** 2026-06-26 11:40

Build the 13-class vector engine around the existing DevinSync.py. Source
data: MySQL devin.devin_chat_turns (produced by DevinSync.Run("sync")).
Embed target: Qdrant collection devin_chat_turns (one vector per chat turn).
Location: /Users/wws/Downloads/ChatGPTManager/ (alongside DevinSync.py,
Config.py, main.py). Template: DevinSync.py (VBStyle). Config: Config.py
(extend). DevinSync.py already exists = bullets #9 + #13 (sync + live sync
foundation).

### Plan

- Location: /Users/wws/Downloads/ChatGPTManager/ (alongside DevinSync.py,
  Config.py, main.py). 14 files total: 2 exist (DevinSync.py = sync, Config.py
  = extend), 12 new. One class per file, VBStyle, PascalCase, Tuple3, Run()
  dispatch, self.state dict, no decorators/print/self._/hardcode/tabs.
- Source data (verified real): MySQL devin DB exists with 9 tables
  (devin_sessions, devin_messages, devin_tool_calls, devin_rendered_commits,
  devin_transcripts, devin_summaries, devin_chat_turns, devin_commands,
  devin_import_log). devin_chat_turns schema: id BIGINT PK AUTO_INCREMENT,
  session_id VARCHAR(255), turn_seq INT, user_message LONGTEXT,
  assistant_message LONGTEXT, files_json LONGTEXT, file_paths TEXT,
  created_at BIGINT, created_at_dt DATETIME, UNIQUE uq_turn(session_id,
  turn_seq), idx_session(session_id). AUTO_INCREMENT=1294 (1293 turns
  already synced).
- Embed target: Qdrant collection "devin_chat_turns", Cosine distance, dim =
  MLX model dim (Config.QDRANT_DIM). Payload per point: {session_id,
  turn_seq, file_paths, created_at_dt, preview(200)}. Text per turn =
  user_message + "\n" + assistant_message (truncate EMBED_TEXT_MAX=16000000,
  matches DevinSync cap).

#### The 13 classes (one per file)

| # | Bullet (DevinSync.py lines 28-42) | File | Class | Domain | Status |
|---|-----------------------------------|------|-------|--------|--------|
| 5 | CONFIG (DB-swappable) | Config.py | Config (extend) | config | exists, extend |
| 8 | DB TO CONNECT + DETECT DB + DETECT TABLES + CREATE TABLES | DbManager.py | DbManager | db_schema | NEW (foundation) |
| 2 | CHECK PIP (transformer/mlx/pytorch) | PipChecker.py | PipChecker | pip_deps | new |
| 1 | CHECK QDRANT | QdrantChecker.py | QdrantChecker | qdrant_health | new |
| 3 | PREVENT RAM/HDD RUNAWAY | ResourceGuard.py | ResourceGuard | resource_limits | new |
| 6 | EMBEDDING > QDRANT | MlxEmbedder.py | MlxEmbedder | mlx_embedding | new (core) |
| 9 | SYNC TO DB | DevinSync.py | DevinSync | devin_sync | EXISTS (no change) |
| 13 | SYNC CHAT AS IT HAPPENS | ChatSync.py | ChatSync | live_chat_sync | new (wraps DevinSync) |
| 7 | SQLITE-RAM FOR SPEED SEARCH | SqliteRamLoader.py | SqliteRamLoader | sqlite_ram | new |
| 12 | SEARCH MYSQL DB | MysqlSearcher.py | MysqlSearcher | mysql_search | new |
| 4 | CLEAN UP QDRANT EMBEDDING | QdrantCleaner.py | QdrantCleaner | qdrant_cleanup | new |
| 11 | CLEAR OLD DB + SESSIONS | SessionCleaner.py | SessionCleaner | session_cleanup | new |
| 10 | VERIFY | Verifier.py | Verifier | data_integrity | new |
| - | entry point | main.py | (extend) | - | exists, wire commands |

#### DbManager.py (bullet #8 — FOUNDATION: detect DB, detect tables, create tables)

- Run() dispatch: detect_db | detect_tables | create_tables | ensure_all |
  connect | close | read_state | set_config.
- _DetectDb: connect to MySQL server (no db selected), SHOW DATABASES LIKE
  config.db_name. If missing -> CREATE DATABASE IF NOT EXISTS devin
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci. Reconnect to devin.
  Return {db, exists, created}.
- _DetectTables: query information_schema.TABLES WHERE TABLE_SCHEMA='devin'
  -> existing set. Compare against EXPECTED_TABLES (10 names). For each
  existing table, query information_schema.COLUMNS -> detect schema drift
  (e.g. missing 'source' column on devin_tool_calls, devin_rendered_commits,
  devin_transcripts, devin_summaries, devin_chat_turns). Build catalog
  {table: {exists, missing_columns}}. Return {existing, missing, drift}.
- _CreateTables: for each missing table -> CREATE TABLE IF NOT EXISTS
  (DDL from TABLE_DDL dict, matches real SHOW CREATE TABLE output exactly).
  For drifted tables -> ALTER TABLE ADD COLUMN for missing columns (replaces
  DevinSync._EnsureSourceColumn runtime patch). Return {created, altered}.
- _EnsureAll: detect_db -> connect -> detect_tables -> create_tables. One-shot
  setup. Return {db, tables_created, tables_altered, all_ready}.
- _Connect: copy DevinSync _ConnectMysql retry/backoff (max_retries,
  initial_backoff from Config, autocommit=True, connection_timeout=10).
- _Close: close cursor + connection, null state (matches DevinSync _Close).
- EXPECTED_TABLES (10): devin_sessions, devin_messages, devin_tool_calls,
  devin_rendered_commits, devin_transcripts, devin_summaries,
  devin_chat_turns, devin_commands, devin_import_log, embed_watermark (NEW).
- TABLE_DDL: dict of CREATE TABLE IF NOT EXISTS for all 10 tables, pulled
  from real SHOW CREATE TABLE output (see schema dump above). embed_watermark
  is new: session_id VARCHAR(128) PK, last_turn_seq INT NOT NULL,
  last_embedded_at DATETIME NOT NULL.
- Other classes receive DbManager via db ctor param, call
  db.Run("ensure_all",{}) then db.Run("connect",{}), access
  db.state["mysql_cur"]. Matches VBStyle mem/db injection.

#### Config.py extension (bullet #5 — DB-swappable)

- Add UPPERCASE constants (no hardcode inside classes): QDRANT_HOST,
  QDRANT_PORT (6333), QDRANT_COLLECTION ("devin_chat_turns"), QDRANT_DIM,
  QDRANT_DISTANCE ("Cosine"), MLX_MODEL, MLX_MAX_TOKENS (512), MLX_DEVICE
  ("mps"), MLX_BATCH (32), EMBED_WATERMARK_TABLE ("embed_watermark"),
  EMBED_TEXT_MAX (16000000), RAM_LIMIT_PCT (85), DISK_LIMIT_PCT (90),
  RESOURCE_CHECK_EVERY (64), SQLITE_RAM_DB (":memory:"),
  SESSION_RETENTION_DAYS (180), REQUIRED_PACKAGES (["mlx","mlx_lm",
  "qdrant_client","mysql.connector","numpy"]).
- Reuse existing BACKEND_DB_MAP for DB-swap (MySQL->Mongo etc. via
  set_config). Extend Config._Get attr_map with new keys. Changeable at
  runtime via set_config = the "change DB if need" requirement.

#### PipChecker.py (bullet #2)

- Run() dispatch: check | read_state | set_config.
- _CheckImport: try import each in REQUIRED_PACKAGES, version via
  importlib.metadata.version, return {pkg: (ok, version)}. Missing list
  with pip install hint string (returned in data, NOT printed).

#### QdrantChecker.py (bullet #1)

- Run() dispatch: check | ping | collection_info | ensure_collection |
  read_state | set_config.
- _Ping: qdrant_client.get_collections() health.
- _CollectionInfo: verify collection exists, vector dim == QDRANT_DIM,
  distance == Cosine.
- _EnsureCollection: idempotent create (recreate=False).

#### ResourceGuard.py (bullet #3)

- Run() dispatch: check | snapshot | read_state | set_config.
- _Snapshot: psutil.virtual_memory().percent, psutil.disk_usage(cwd).percent
  (psutil; fallback shutil.disk_usage + os if absent).
- _Check: return (1, {ok, ram_pct, disk_pct}, None); if ram > RAM_LIMIT_PCT
  or disk > DISK_LIMIT_PCT -> (0, None, ("RESOURCE_LIMIT", ..., 0)). Called
  by MlxEmbedder every RESOURCE_CHECK_EVERY rows.

#### MlxEmbedder.py (bullet #6 — CORE)

- Run() dispatch: embed_rows | embed_query | read_state | set_config.
- _LoadModel: lazy load MLX embedding model once (cache in state). Tokenize
  truncate MLX_MAX_TOKENS, mean-pool, L2-normalize (numpy).
- _EmbedRows: takes list of {session_id, turn_seq, text}, batches at
  MLX_BATCH, calls ResourceGuard.Run("check") every RESOURCE_CHECK_EVERY,
  upserts to Qdrant with payload {session_id, turn_seq, file_paths,
  created_at_dt, preview}. Returns {embedded, skipped, errors}. After each
  session's turns -> write devin.embed_watermark(session_id, last_turn_seq,
  now).
- _EmbedQuery: embed single query string -> normalized vector for search.
- Text per turn = user_message + "\n" + assistant_message (truncate
  EMBED_TEXT_MAX).

#### ChatSync.py (bullet #13 — LIVE)

- Run() dispatch: poll_once | poll_loop | read_state | set_config.
- _PollOnce: DevinSync.Run("sync") refreshes MySQL; query devin_chat_turns
  for rows where (session_id, turn_seq) > watermark; hand to
  MlxEmbedder.Run("embed_rows", {...}); update watermark.
- _PollLoop: loop _PollOnce every DEVIN_POLL_INTERVAL (existing config=30s);
  each iteration guarded by ResourceGuard.Run("check").
- State holds memunit=DevinSync, embedder=MlxEmbedder, guard=ResourceGuard
  (injected via ctor).

#### SqliteRamLoader.py (bullet #7)

- Run() dispatch: load | search | unload | read_state | set_config.
- _Load: connect :memory:, create chat_turns mirror, SELECT from MySQL
  devin_chat_turns JOIN devin_sessions, bulk insert. Return {rows_loaded}.
- _Search: LIKE/FTS5 on in-RAM table (session_id, turn_seq, user_message,
  assistant_message, file_paths). Fast, no network.
- _Unload: close :memory:, free RAM.

#### MysqlSearcher.py (bullet #12)

- Run() dispatch: search | search_sessions | read_state | set_config.
- _Search: LIKE/REGEXP over devin_chat_turns.user_message/assistant_message/
  file_paths, JOIN devin_sessions for title.
- _SearchSessions: search devin_sessions.title + working_directory.

#### QdrantCleaner.py (bullet #4)

- Run() dispatch: drop_collection | delete_orphans | recount | read_state |
  set_config.
- _DropCollection: delete_collection (requires params["confirm"]=True).
- _DeleteOrphans: Qdrant points whose (session_id, turn_seq) not in MySQL
  devin_chat_turns; delete.
- _Recount: Qdrant point count vs MySQL row count.

#### SessionCleaner.py (bullet #11)

- Run() dispatch: purge_old | vacuum | read_state | set_config.
- _PurgeOld: delete devin_chat_turns/devin_messages/devin_sessions older
  than SESSION_RETENTION_DAYS; cascade Qdrant delete by session_id (via
  QdrantCleaner).
- _Vacuum: OPTIMIZE TABLE on MySQL devin tables.

#### Verifier.py (bullet #10)

- Run() dispatch: verify | read_state | set_config.
- _Verify: MySQL devin_chat_turns count == Qdrant point count == watermark
  coverage; report orphans both directions; report dim mismatch. Return
  {mysql_count, qdrant_count, orphans_qdrant, orphans_mysql, dim_ok}.

#### main.py (extend — wire commands)

- preflight (PipChecker+QdrantChecker+ResourceGuard), sync (ChatSync),
  embed (MlxEmbedder full), sql_search (MysqlSearcher), ram_search
  (SqliteRamLoader), verify (Verifier), cleanup (QdrantCleaner+
  SessionCleaner). Each constructs needed classes with mem/db/param
  injection per VBStyle ctor.

#### Qdrant collection schema

- name: QDRANT_COLLECTION = "devin_chat_turns", size QDRANT_DIM, Cosine.
- payload: {session_id, turn_seq, file_paths, created_at_dt, preview(200)}.

#### MySQL watermark table (NEW — created by DbManager)

- devin.embed_watermark: session_id VARCHAR(128) PK, last_turn_seq INT NOT
  NULL, last_embedded_at DATETIME NOT NULL.

#### Verify (per obey.md post-code gate, each file)

- py_compile passes; grep print( = 0; grep @staticmethod|@property|
  @classmethod = 0; grep self._ = 0; all methods Tuple3; Run() exists;
  Ghost/VBStyle/Classes/Methods/Domain headers; no hardcode (all via
  Config).

#### Build order (one class at a time, verify each before next)

1. Config.py extend -> 2. DbManager.py (foundation) -> 3. PipChecker ->
4. QdrantChecker -> 5. ResourceGuard -> 6. MlxEmbedder (core) -> 7.
ChatSync -> 8. QdrantCleaner -> 9. SessionCleaner -> 10. SqliteRamLoader
-> 11. MysqlSearcher -> 12. Verifier -> 13. main.py wire.

#### Risks

- MLX model dim must match QDRANT_DIM at collection creation ->
  QdrantChecker verifies, fails fast if mismatch.
- Large chat turns (assistant_message can be huge) -> truncate at
  EMBED_TEXT_MAX (matches DevinSync 16M cap).
- psutil may not be installed -> PipChecker flags it; ResourceGuard falls
  back to shutil/os.
- Watermark race if poll_loop runs concurrent -> single-loop design avoids
  it.
- DevinSync._EnsureSourceColumn becomes redundant once DbManager handles
  schema drift at setup time -> leave DevinSync unchanged (no edit unless
  told).

---

## TASK-086: CodeBERT Semantic Domain Router for 478 Unresolved Classes
**Priority:** P1 | **Tags:** domain-routing, codebert, embeddings, qdrant, hypothesis-tier
**Updated:** 2026-06-26 10:30

Assign the 478 unresolved classes to hypothesis-tier domains using CodeBERT
embeddings + per-domain centroid kNN, anchored by the 733 truth classes.
Low-similarity classes stay unresolved (never forced). Truth (733) is never
touched. Inputs: code_store_variations/v20_hybrid_best.db (classes.class_code,
read-only) and code_store_variations/domain_graph.db (domain_truth anchors,
domain_unresolved targets, domain_hypothesis writes). New Qdrant collection
dom_class_code (768-dim Cosine) stores all class vectors with payload
{class_name, owner, layer}. Owners with >=3 truth classes form stable
centroids; each unresolved class takes cosine-nearest centroid; score >=
0.60 -> domain_hypothesis tier 3 method 'codebert-knn' + score, and is
deleted from domain_unresolved; score < 0.60 stays unresolved.

### Plan

- Path correction: spec's root DBs are 0 bytes; real data in code_store_variations/ (verified: truth 733, hypothesis 234, unresolved 478, classes 1445, all class_names join, 1 truth class has empty class_code -> skip).
- Files (one class per file, VBStyle): dom_semantic_router/{Config, ClassEmbedder, CentroidBuilder, SemanticRouter, main}.py
- Embed: microsoft/codebert-base (768-dim), tokenize truncate 512, chunk long class_code (avg 16K chars, max 2.2MB) with MAX_CHUNKS cap + even sampling, mean-pool attention-masked last_hidden_state, L2-normalize. Device MPS if available.
- Centroids: per-owner mean of truth vectors, only owners with >=3 truth members (46 of 77 owners qualify).
- Classify: numpy cosine to 46 centroids, max score; >=0.60 threshold -> hypothesis tier 3 'codebert-knn' + score, DELETE from unresolved; <0.60 stays.
- Writes: only domain_graph.db (domain_hypothesis INSERT + domain_unresolved DELETE in one transaction) + Qdrant dom_class_code upsert. v20_hybrid_best.db read-only. Truth untouched.
- Verify: py_compile + grep (no print/decorators/self._), counts (embedded/centroids/assigned/remaining), domain_truth still 733, top-10 assignments with scores.
- Risk: 2.2MB class_code monster -> MAX_CHUNKS cap bounds runtime; 1 empty class_code skipped gracefully; CodeBERT ~500MB download on first run.

---

## TASK-098: Upgrade purge (Python) + Cleaner.c (C) for aggressive memory reclamation
**Priority:** P1 | **Tags:** memory, purge, cleaner, c, dom-system
**Updated:** 2026-06-28 14:30

The Python `purge` command in DomSystem.py currently uses a single alloc-free pressure technique (512MB). The C `Cleaner.c` only handles file cache cleaning (Windsurf/Codeium cache dirs) — it has no memory reclamation capability. Upgrade both: (1) Python purge gets multi-pass + madvise + malloc_trim + pressure escalation, (2) Cleaner.c gets a new `mem` command that does C-level memory purging (mmap pressure, malloc_trim, madvise) alongside the existing file cache cleaning.

### Plan

- Step 1: Upgrade DomSystem._cmd_purge — add multi-pass pressure (3 rounds of alloc-free at escalating sizes), call malloc_trim via ctypes, use madvise(MADV_DONTNEED) on the pressure buffer, report per-pass freed MB
- Step 2: Upgrade Cleaner.c — add `mem` command: C-level memory purge via mmap+munmap pressure blocks, malloc_trim (if available), report top processes before/after
- Step 3: Add `mem` to Cleaner dispatch + CLI usage
- Step 4: Compile Cleaner.c and test both Python purge and C mem
- Key files: `core/Dom_Unified/DomSystem.py`, `Cascade_toolStack/bin_tools/Cleaner.c`
- Risks: malloc_trim not on macOS (it's glibc-specific) — use mmap pressure instead; madvise may need _GNU_SOURCE on Linux but works on macOS

---
## TASK-092: GraphViewCompiler — View to Execution Plan
**Priority:** P1 | **Tags:** graph, c, compiler, plan
**Updated:** 2026-06-28 16:00

Build the View Compiler. Converts a declarative View into an executable Plan (like SQL query plan to IR). Pipeline: View to Normalizer to Planner to Optimizer to Execution Plan.

### Plan

- Step 1: Write GraphCompiler.c class with Plan struct: root_nodes, traversal_steps, guards, cache_keys, budget_tracker
- Step 2: Normalizer: resolve node selectors, expand shorthand rules, validate constraints
- Step 3: Planner: build naive traversal tree from view rules
- Step 4: compile_view(view) to Plan: the main compiler function
- Step 5: Plan lifecycle: plan_create, plan_free, plan_add_step, plan_execute
- Step 6: Insert into MySQL via c_class_builder.py
- Dependencies: GraphTypes, GraphView (TASK-091)

---

## TASK-093: GraphOptimizer — Pruning, Dedup, Cost Reorder, Adaptive Depth
**Priority:** P1 | **Tags:** graph, c, optimizer, scoring
**Updated:** 2026-06-28 16:00

Build the Optimizer. Takes a naive Plan and optimizes it: pruning, deduplication, cost reordering, adaptive depth. Uses 3-part scoring: RuleScore + LearnedScore + StructuralScore.

### Plan

- Step 1: Write GraphOptimizer.c class with scoring functions
- Step 2: RuleScore: relevance_match, depth_penalty, cost_estimate (deterministic)
- Step 3: StructuralScore: betweenness_centrality, dependency_depth, fanout_penalty, isolation_penalty
- Step 4: LearnedScore: historical_success_rate, attention_frequency, retrieval_hit_quality (placeholder)
- Step 5: FINAL_SCORE = alpha*Rule + beta*Learned + gamma*Structural
- Step 6: optimize_plan(plan) to optimized_plan: pruning, dedup, cost reorder, depth reshape
- Step 7: Priority queue execution: highest score expands first
- Step 8: Insert into MySQL via c_class_builder.py
- Dependencies: GraphTypes, GraphCompiler (TASK-092)

---

## TASK-094: GraphTrace + GraphCache — Explainability and Reuse
**Priority:** P2 | **Tags:** graph, c, trace, cache
**Updated:** 2026-06-28 16:00

Build the Trace and Cache layers. Trace stores why each node was expanded/skipped (explainability). Cache stores subplans and results for reuse (node+view+depth to result).

### Plan

- Step 1: Write GraphTrace.c — TraceEntry struct (node_id, action, reason, cost, timestamp), trace_log, trace_dump
- Step 2: Write GraphCache.c — CacheEntry struct (node_id+view_signature+depth to result), cache_store, cache_lookup, cache_invalidate
- Step 3: Integrate with execution engine: trace logs every expand/skip, cache checks before expand
- Step 4: Insert both into MySQL via c_class_builder.py
- Dependencies: GraphTypes, GraphOptimizer (TASK-093)

---

## TASK-095: GraphTrace — Immutable Truth Log for Explainability
**Priority:** P1 | **Tags:** graph, c, trace, explainability
**Updated:** 2026-06-28 16:30

Build the Trace System. Every graph run produces an immutable log: nodes visited, nodes skipped, scores at decision time, final outcome quality, cost spent, path taken. This is never modified. Needed for the learning pipeline.

### Plan

- Step 1: Write GraphTrace.c — TraceEntry struct (node_id, action, reason, score_at_decision, cost, timestamp, view_id)
- Step 2: TraceLog struct — dynamic array of entries, append-only
- Step 3: trace_log_visit, trace_log_skip, trace_log_prune, trace_log_cost, trace_log_outcome
- Step 4: trace_dump — export trace as JSON or text for debugging
- Step 5: trace_evaluate — convert raw trace into structured learning signals (contribution_score, success_delta, cost_efficiency, redundancy_penalty)
- Step 6: Insert into MySQL via c_class_builder.py
- Dependencies: GraphTypes

---

## TASK-096: GraphCache — Multi-Layer Scoped Cache (No Contamination)
**Priority:** P1 | **Tags:** graph, c, cache, isolation
**Updated:** 2026-06-28 16:30

Build the 4-layer cache system. Cache key = (node_id, view_signature, policy_signature, depth, scoring_version). Every cache entry is context-bound. No cross-layer contamination.

### Plan

- Step 1: Write GraphCache.c — CacheEntry struct with context-bound key
- Step 2: 4 cache layers: Structural (deterministic), Semantic (view-specific), Policy (execution order), Learning (isolated)
- Step 3: cache_store, cache_lookup, cache_invalidate (with invalidation rules: view change, policy change, scoring version change, graph mutation)
- Step 4: Subgraph fingerprinting: hash(node_set + edge_set + view_rules + depth_profile)
- Step 5: cache_value function: stability_score + reuse_frequency - context_conflict_risk - freshness_requirement
- Step 6: Scope map: AST_VIEW -> {allowed_nodes, forbidden_edges}, DEBUG_VIEW -> {allowed_nodes, forbidden_edges}
- Step 7: Insert into MySQL via c_class_builder.py
- Dependencies: GraphTypes, GraphView

---

## TASK-097: GraphLearning — 3-Stage Learning Pipeline (Isolated)
**Priority:** P1 | **Tags:** graph, c, learning, reinforcement
**Updated:** 2026-06-28 16:30

Build the Learning System. 3-stage pipeline: TRACE (raw events) -> EVALUATION (signal extraction) -> UPDATE (bounded weight adjustment) -> POLICY APPLY (slow integration). Prevents feedback collapse via anti-reinforcement.

### Plan

- Step 1: Write GraphLearning.c — LearningSignal struct (node_id, view_id, contribution_score, success_delta, cost_efficiency, redundancy_penalty)
- Step 2: Credit assignment: contribution(node) = downstream_success_impact - expansion_cost_penalty - redundancy_overlap_penalty
- Step 3: Weight buffer: weight_delta[node] += learning_rate * contribution_signal (accumulate, don't apply directly)
- Step 4: Apply only if: confidence threshold met, repeated signal observed, not contradictory to rules
- Step 5: Anti-reinforcement: penalty = similarity_to_recent_paths (exploration pressure)
- Step 6: LearnedScore(node) = historical_success + contribution_weight + exploration_bonus - repetition_penalty - wasted_expansion_penalty
- Step 7: Slow integration: periodic, averaged, clipped by safety bounds
- Step 8: Insert into MySQL via c_class_builder.py
- Dependencies: GraphTypes, GraphTrace (TASK-095), GraphOptimizer (TASK-093)

---
