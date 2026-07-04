<!-- [@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<README for Dom_Graph code reasoning engine. Documents entry points, CLI usage, GUI viewers, tests. No VBStyle violations (markdown doc).>][@todos<none>]} -->
# Dom_Graph — Code Reasoning Engine

## What This Is

A multi-layer system that reasons about code: discovers structure, finds gaps,
makes fix decisions, simulates agent behavior, and visualizes 8 graph perspectives.

## Quick Start — Entry Points

### CLI (most common)
```bash
# Get DB stats
python3 Dom_Graph/dom_graph_bridge.py stats

# Ask the engine to decide a fix
python3 Dom_Graph/dom_graph_bridge.py decide --domain codefix --query "NameError" --limit 5

# Get candidates for a problem
python3 Dom_Graph/dom_graph_bridge.py get_candidates --domain codefix --query "import error" --limit 10

# Show reasoning trace
python3 Dom_Graph/dom_graph_bridge.py trace

# Full ContextRAM assembly (for Swift ctx integration)
python3 Dom_Graph/dom_graph_bridge.py to_context_assembly --domain codefix --query "fix deadlock" --file server.py
```

### Direct Engine (Python)
```python
import sys; sys.path.insert(0, "Dom_Graph")
from DomGraphEngine import DomGraphEngine
engine = DomGraphEngine()
ok, data, err = engine.Run("decide", {"domain": "codefix", "query": "NameError", "limit": 5})
```

### GUI Viewers
```bash
python3 Dom_Graph/Dom_Graph_Plan.py      # What are we building?
python3 Dom_Graph/Dom_Graph_Spec.py      # What exactly exists?
python3 Dom_Graph/Dom_Graph_Flow.py      # How does it move?
python3 Dom_Graph/Dom_Graph_Lifecycle.py # When does it run?
python3 Dom_Graph/Dom_Graph_Dep.py       # Why does it connect?
python3 Dom_Graph/Dom_Graph_Error.py     # Where does it fail?
python3 Dom_Graph/Dom_Graph_Orch.py      # Who calls who?
python3 Dom_Graph/Dom_Graph_Gap.py       # What's missing?
python3 Dom_Graph/Dom_Graph_Gui.py       # Visual DB auditor (Tkinter)
python3 Dom_Graph/Dom_Graph_Viewer.py    # General graph viewer (Tkinter)
```

### Tests
```bash
python3 Dom_Graph/utils/core/_TEST.py --list      # List suites
python3 Dom_Graph/utils/core/_TEST.py             # Run all 4 suites
python3 Dom_Graph/utils/core/_TEST.py --suite 1   # Domain loader tests
python3 Dom_Graph/utils/core/_TEST.py --suite 2   # Everything (DB+Config+graph)
python3 Dom_Graph/utils/core/_TEST.py --suite 3   # MemUnit event-sourcing
python3 Dom_Graph/utils/core/_TEST.py --suite 4   # Spec compliance
```

### 26-Eyes Analysis (core/Dom_Graph/)
```bash
python3 -m core.Dom_Graph.codegraph_26eyes --db core/Dom_Graph/dom_graph.db --json-out output.json
```

---

## Architecture — 3 Layers

### Layer 1: Data (`dom_graph_unified.db`)

5 tables, 3 domains (`codefix`, `session`, `gui`):

| Table | Count | Purpose |
|-------|-------|---------|
| nodes | 1,343 | Everything is a node: files, classes, methods, observations, knowledge, sessions, paths |
| edges | 9,015 | Every relationship: reads, writes, calls, gui_call, api_call, imports, thread_call |
| rules | 0 | Decision rules (EMPTY — should be populated from MySQL learned_rules) |
| decisions | 5 | Past fix decisions with scores and reasoning traces |
| snapshots | 11 | Session resume points with progress % and resume actions |

Node types in `codefix` domain: observation (451), method (419), knowledge (381), file (42), class (38), attempt (1)
Node types in `session` domain: path (10), session (1)

Edge types: reads (3827), writes (2187), calls (1368), gui_call (1139), api_call (381), thread_call (76), database_access (20), imports (14)

### Layer 2: Engine (`DomGraphEngine.py`, 1860 lines)

The unified decision engine. One class, one `Run()` dispatch, 40+ commands.

**Decision pipeline:**
```
get_candidates -> filter -> when_rules -> resolve_conflicts -> score -> decide
```

**Extended analysis:**
```
rank_fixes -> analyze_risk -> simulate -> validate -> analyze_cost -> analyze_benefit
```

**Confidence scoring:**
```
parse_confidence, match_confidence, graph_confidence, repair_confidence, runtime_confidence, overall_confidence
```

**CRUD:**
```
add_node, get_node, query_nodes, add_edge, get_edges, add_rule, get_rules,
get_decision, query_decisions, add_snapshot, get_snapshot
```

**Session management:**
```
open_session, add_path, update_path, add_resume, get_resume, render, dashboard, close_session, list_sessions
```

**Maintenance:**
```
init_schema, migrate_codefix, migrate_session, gc, stats, read_state, set_config
```

### Layer 3: Bridge + Viewers

- `dom_graph_bridge.py` — CLI to JSON bridge (for ContextRAM Swift integration)
- 8 Tkinter graph viewers (Plan, Spec, Flow, Lifecycle, Dep, Error, Orch, Gap)
- `Dom_Graph_Gui.py` — visual DB auditor (VBStyle, BCL, cognitive loop, hardcoded paths)
- `Dom_Graph_Viewer.py` — general purpose graph viewer
- `codegraph_26eyes.py` (in `core/Dom_Graph/`) — 26-perspective analysis

---

## File Map

### Core Engine Files

| File | Lines | Class | Run() Commands | Purpose |
|------|-------|-------|----------------|---------|
| `DomGraphEngine.py` | 1860 | DomGraphEngine | 40+ | Unified decision engine (THE main engine) |
| `dom_graph_bridge.py` | 202 | (functions) | 5 | CLI bridge -> JSON stdout |
| `Dom_Graph_Engine.py` | 695 | CuriosityController, GraphEngine, ReportMaker | 3x Run() | Self-discovering DB investigator |
| `Dom_Graph_EngineV2.py` | 813 | + ConstraintChecker, SolutionSuggester, MistakeRecorder | 7x Run() | V2 with full cognitive loop |
| `Dom_Graph_Agent.py` | 2460 | AgentGraph + 10 classes | 24 | Living agent simulation (Yin/Yang) |
| `Dom_Graph_Boot.py` | 551 | ExecutionGraph | 9 | Boot sequence analyzer |
| `Dom_Graph_Code.py` | 315 | TypedGraph, Node, Edge | 3x Run() | Typed graph builder |
| `Dom_Graph_Ingest.py` | 307 | (functions) | - | Ingest from MySQL to SQLite |

### 8 Graph Viewers (Tkinter, one per perspective)

| File | Class | Question |
|------|-------|----------|
| `Dom_Graph_Plan.py` | PlanGraph | What are we building? |
| `Dom_Graph_Spec.py` | SpecGraph | What exactly exists? |
| `Dom_Graph_Flow.py` | SpecFlow | How does it move? |
| `Dom_Graph_Lifecycle.py` | LifecycleGraph | When does it run? |
| `Dom_Graph_Dep.py` | DomGraphDep | Why does it connect? |
| `Dom_Graph_Error.py` | ErrorGraph | Where does it fail? |
| `Dom_Graph_Orch.py` | OrchGraph | Who calls who? |
| `Dom_Graph_Gap.py` | GapGraph | What's missing? |

### Config

| File | Lines | Purpose |
|------|-------|---------|
| `Config.py` | 1350 | Schema, constants, primitive costs, Config class. NOTE: mixes runtime twin (mac_server.c sim) + code graph in one file. |
| `Config_ChatGui.py` | ~400 | ChatGui-specific config |
| `chatgui_settings.json` | 14 | ChatGui runtime settings |

### Brain System (AI brain simulation)

| File | Class | Purpose |
|------|-------|---------|
| `BrainDockSystem.py` | BrainDockSystem | Brain dock coordinator |
| `BrainGenerator.py` | BrainGenerator | Synthetic brain generation |
| `BrainLearning.py` | BrainLearning | Learning algorithm |
| `BrainRL.py` | BrainRL | Reinforcement learning |
| `BrainRenderer.py` | BrainRenderer | Brain visualization |
| `BrainStorageClient.py` | BrainStorageClient | Brain storage backend |
| `BrainSynthetic.py` | BrainSynthetic | Synthetic data generation |
| `BrainTrainer.py` | BrainTrainer | Training pipeline |
| `BrainValidator.py` | BrainValidator | Validation checks |
| `GuiAiBrain.py` | GuiAiBrain | PyQt6 brain GUI |
| `brain_server/` | (Node.js) | Express server for brain API |
| `brain_model*.pt` | - | Trained PyTorch models (4 files) |

### Stores (persistence layer)

| File | Class | Purpose |
|------|-------|---------|
| `AstNodeRegistry.py` | AstNodeRegistry | AST node registry |
| `AstVersionStore.py` | AstVersionStore | AST version history |
| `BclStampStore.py` | BclStampStore | BCL identity stamps |
| `DependencyEdgeStore.py` | DependencyEdgeStore | Dependency edges |
| `EventLogStore.py` | EventLogStore | Event log |
| `EventSourcedMemUnit.py` | EventSourcedMemUnit | Event-sourced memory unit |
| `SnapshotStore.py` | SnapshotStore | State snapshots |
| `TraceChainStore.py` | TraceChainStore | Execution trace chains |
| `InRamDb.py` | InRamDb | In-RAM SQLite database |

### Physics + Visualization

| File | Class | Purpose |
|------|-------|---------|
| `GraphPhysics.py` | GraphPhysics | Force-directed layout physics |
| `GraphSignalMatrix.py` | GraphSignalMatrix | Signal propagation matrix |
| `EnergyFieldGraph.py` | EnergyFieldGraph | Energy field visualization |
| `GuiEnergyGraph.py` | GuiEnergyGraph | Energy graph GUI |
| `GuiGraph.py` | GuiGraph | Graph GUI component |
| `HeatmapRenderer.py` | HeatmapRenderer | Heatmap rendering |
| `IdeGraphLayout.py` | IdeGraphLayout | IDE graph layout |
| `LayoutStateSpace.py` | LayoutStateSpace | Layout state space search |
| `MagneticGraph.py` | MagneticGraph | Magnetic graph layout |
| `MagneticGui.py` | MagneticGui | Magnetic graph GUI |
| `PhysicsRenderer.py` | PhysicsRenderer | Physics-based rendering |
| `PhysicsRuleLoader.py` | PhysicsRuleLoader | Physics rule loader |

### GUI Components

| File | Class | Purpose |
|------|-------|---------|
| `ChatGui.py` | ChatGui | Devin chat GUI (PyQt6, 86KB) |
| `Dom_Graph_Gui.py` | DbArchitectureGui | DB architecture auditor (Tkinter) |
| `GuiAspect.py` | GuiAspect | GUI aspect base |
| `GuiAspectRegistry.py` | GuiAspectRegistry | Aspect registry |
| `GuiAspects.py` | GuiAspects | Aspect collection |
| `TokenCounter.py` | TokenCounter | Token counting GUI |

### Analysis Engines

| File | Class | Purpose |
|------|-------|---------|
| `CodeGraph.py` | CodeGraph | Code graph builder |
| `ContextCompiler.py` | ContextCompiler | Context compilation |
| `ContextReconstructor.py` | ContextReconstructor | Context reconstruction |
| `call_path_engine.py` | CallPathEngine | Call path analysis |
| `control_flow_engine.py` | ControlFlowEngine | Control flow analysis |
| `data_flow_engine.py` | DataFlowEngine | Data flow analysis |
| `decision_engine.py` | DecisionEngine | Fix decision engine |
| `digital_twin.py` | DigitalTwin | Digital twin simulation |
| `diff_engine.py` | DiffEngine | Diff comparison |
| `duplicate_engine.py` | DuplicateEngine | Duplicate detection |
| `evolution_engine.py` | EvolutionEngine | Code evolution tracking |
| `evidence_engine.py` | EvidenceEngine | Evidence collection |
| `fingerprint_engine.py` | FingerprintEngine | Code fingerprinting |
| `impact_engine.py` | ImpactEngine | Change impact analysis |
| `knowledge_engine.py` | KnowledgeEngine | Knowledge extraction |
| `memory_engine.py` | MemoryEngine | Memory management |
| `naming_engine.py` | NamingEngine | Naming convention checks |
| `pattern_engine.py` | PatternEngine | Pattern detection |
| `prediction_engine.py` | PredictionEngine | Failure prediction |
| `quality_engine.py` | QualityEngine | Quality scoring |
| `refactor_engine.py` | RefactorEngine | Refactoring recommendations |
| `refactor_family.py` | RefactorFamily | Family-based refactoring |
| `relationship_extractor.py` | RelationshipExtractor | Relationship extraction |
| `report_engine.py` | ReportEngine | Report generation |
| `root_cause_engine.py` | RootCauseEngine | Root cause analysis |
| `runtime_engine.py` | RuntimeEngine | Runtime analysis |
| `safety_engine.py` | SafetyEngine | Safety checks |
| `sandbox_engine.py` | SandboxEngine | Sandbox execution |
| `search_engine.py` | SearchEngine | Code search |
| `self_check_engine.py` | SelfCheckEngine | Self-checking |
| `snapshot_engine.py` | SnapshotEngine | Snapshot management |
| `sql_analyzer.py` | SqlAnalyzer | SQL analysis |
| `static_analyzer.py` | StaticAnalyzer | Static analysis |
| `symbol_engine.py` | SymbolEngine | Symbol resolution |
| `trace_engine.py` | TraceEngine | Execution tracing |
| `type_engine.py` | TypeEngine | Type analysis |
| `unit_partitioner.py` | UnitPartitioner | Unit partitioning |
| `unknown_engine.py` | UnknownEngine | Unknown pattern detection |
| `validation_engine.py` | ValidationEngine | Validation checks |

### Utilities + Other

| File | Purpose |
|------|---------|
| `ir_extractor.py` | IR extraction from source (53KB) |
| `ingestion_engine.py` | Code ingestion pipeline |
| `build_pipeline.py` | Build pipeline |
| `build_registry.py` | Build registry |
| `compiler_engine.py` | Compiler engine |
| `config_engine.py` | Config engine |
| `confidence_engine.py` | Confidence scoring |
| `continuity_engine.py` | Continuity checks |
| `continuous_loop.py` | Continuous loop runner |
| `db_validator.py` | DB validation |
| `error_resistance.py` | Error resistance |
| `file_forensics.py` | File forensics |
| `fix_engine.py` | Fix engine |
| `format_kernel.py` | Format kernel |
| `memory_forensics.py` | Memory forensics |
| `meta_learning_engine.py` | Meta-learning |
| `observation_engine.py` | Observation engine |
| `orchestration_engine.py` | Orchestration |
| `output_integrity.py` | Output integrity |
| `PreExecutionGate.py` | Pre-execution gate |
| `ReplayEngine.py` | Replay engine |
| `RollbackEngine.py` | Rollback engine |
| `use_memunit.py` | MemUnit usage |
| `work_from_db.py` | Work from DB |
| `domain_loader.py` | Domain loader |
| `populate_twin.py` | Twin populator |
| `autonomous_loop.py` | Autonomous loop |
| `backup_engine.py` | Backup engine |
| `arch_validator.py` | Architecture validator |
| `audit_vbstyle.py` | VBStyle auditor |
| `vscode_layout_rules.json` | VSCode layout rules |
| `MemUnit.py` | MemUnit class |
| `SilenceDetector.py` | Silence detection |
| `SttController.py` | Speech-to-text |
| `TtsController.py` | Text-to-speech |
| `VoiceEngine.py` | Voice engine |
| `VoiceConfig.py` | Voice config |
| `AudioEngineManager.py` | Audio manager |
| `TokenCounter.py` | Token counter |
| `dom_graph_bridge.py` | CLI bridge (entry point) |

### core/Dom_Graph/ (26-Eyes System)

| File | Lines | Purpose |
|------|-------|---------|
| `eyes_26.py` | 867 | 26 inspection eyes + GhostBracket parser + Eyes26 dispatcher |
| `codegraph_26eyes.py` | 865 | Bridge: loads graph DB, runs 26 eyes, outputs JSON |
| `eyes_26_v1.py` | 79667 | V1 (older, larger) |
| `_ingest_eyes.py` | 3193 | Ingestion for eyes |
| `_fix_all.py` | 7768 | Fix-all utility |
| `dom_graph.db` | 3.7MB | Graph DB (ast_nodes, edges, classes, methods, etc.) |

### Databases

| File | Size | Tables | Purpose |
|------|------|--------|---------|
| `dom_graph_unified.db` | 4.5MB | nodes, edges, rules, decisions, snapshots | Main unified DB |
| `dom_graph_work.db` | 3.7MB | (same as core/Dom_Graph/dom_graph.db) | Working copy |
| `dom_graph_ingest.db` | 1.5MB | | Ingestion staging |
| `code_store_variations/v20_hybrid_best.db` | 75MB | | Large code store (used by Dom_Graph_Engine.py) |

### Documentation

| File | Purpose |
|------|---------|
| `DOM_GRAPH_ENGINE_DESIGN.md` | Design document for unified engine (1581 lines) |
| `DEVIN_SPEC_DOMAIN_TWIN.md` | Domain twin spec |
| `MEMUNIT_EVENT_SOURCING_SPEC.md` | MemUnit event-sourcing spec |
| `SPEC_CHAT_CORE.md` | Chat core spec |
| `ERRORS_LIST.md` | Known errors list |
| `VBSTYLE_LESSONS.md` | VBStyle lessons learned |
| `db refactore lessoons.md` | DB refactoring lessons |
| `devin_task.txt` / `devin_full_task.txt` | Devin task definitions |
| `devin_output.log` | Devin execution log (29MB) |

### Tests

| File | Purpose |
|------|---------|
| `utils/core/_TEST.py` | Unified test runner (4 suites) |
| `utils/_test_engine.py` | Test engine utility |
| `tests/*.py.bak` | Old individual test files (backed up, merged into _TEST.py) |
| `utils/fixes_archive/` | Old fix scripts (7 files) |

---

## The 26 Eyes (core/Dom_Graph/eyes_26.py)

| # | Name | Class | What it sees |
|---|------|-------|-------------|
| 1 | tree | Eye01Tree | Node hierarchy, child map |
| 2 | token | Eye02Token | Token sequence |
| 3 | depth | Eye03Depth | Max depth, depth distribution |
| 4 | sibling | Eye04Sibling | Sibling relationships |
| 5 | parent | Eye05Parent | Parent map |
| 6 | path | Eye06Path | Full paths from root |
| 7 | leaf | Eye07Leaf | Leaf nodes |
| 8 | subtree | Eye08Subtree | Subtree snapshots |
| 9 | adjacency | Eye09Adjacency | Adjacency matrix + list |
| 10 | feature | Eye10Feature | Feature vectors |
| 11 | semantic | Eye11Semantic | Semantic roles |
| 12 | constraint | Eye12Constraint | Constraints |
| 13 | embedding | Eye13Embedding | Embeddings |
| 14 | hypergraph | Eye14Hypergraph | Hypergraph layers |
| 15 | crosslayer | Eye15CrossLayer | Cross-layer dependencies |
| 16 | event | Eye16Event | Event log |
| 17 | temporal | Eye17Temporal | Temporal log |
| 18 | lock | Eye18Lock | Locked nodes |
| 19 | scaffold | Eye19Scaffold | Scaffold integrity |
| 20 | validation | Eye20Validation | Bracket law validation |
| 21 | codetobracket | Eye21CodeToBracket | Code -> bracket conversion |
| 22 | brackettocode | Eye22BracketToCode | Bracket -> code reconstruction |
| 23 | tensor | Eye23Tensor | Tensor representation |
| 24 | metrics | Eye24Metrics | Aggregate metrics |
| 25 | impact | Eye25Impact | Change impact |
| 26 | risk | Eye26Risk | Change risk |

---

## The Agent System (Dom_Graph_Agent.py)

A cognitive agent simulation on top of the code graph:

| Class | Purpose |
|-------|---------|
| AgentNode | Graph vertex with sensors, drives, memory, survival |
| Edge | Structural edge (IMPORTS, CALLS, CONTAINS) |
| PredictionLink | Learned prediction (reward/pain expectations) |
| WorldModel | Compressed summary the agent carries |
| Goal | Single goal (reach target node/type) |
| GoalSystem | Manages goals, injects drive signals |
| EmotionalState | Mood (0=depressed, 1=elated) |
| Consolidation | Sleep phase, memory pruning |
| AdversarialAgent | Yin adversary that tries to break Yang agent |
| MysqlConnector | Bridges prediction links to MySQL learned_rules |
| AgentGraph | Main graph engine, 24 Run() commands |

Agent Run() commands: blast, reaches, path, all_paths, boot, communities, central,
influence, islands, simulate, cycles, export, predict, attend, self_modify,
world_model, goals, full_simulate, emotion, consolidation, plan, yin_yang,
seed_mysql, structural, validate_boot, write_db, read_db

---

## Known Issues

| Issue | Impact | Fix |
|-------|--------|-----|
| `rules` table empty (0 rows) | `decide` pipeline returns "no candidates" | Populate from MySQL `learned_rules` (10,540 available) |
| `gui` domain empty (0 nodes) | GUI component ontology never ingested | Run ingestion for gui domain |
| `ast_nodes` empty in `dom_graph.db` | 26-eyes engine has no AST data | Run ingestion pipeline |
| Config.py mixes 2 domains | Runtime twin + code graph in one 1350-line file | Split into Config_Runtime.py + Config_Graph.py |
| `Dom_Graph_Engine.py` points at wrong DB | Uses `v20_hybrid_best.db` not `dom_graph_unified.db` | Update DB_PATH |
| 0/38 classes VBStyle compliant | `is_vbstyle=0` for all | Run VBStyle audit + fix violations |
| 6 methods have decorators | VBStyle violation | Remove decorators |
| 13 methods use `self._` | VBStyle violation | Rename to `self.state["key"]` |
| `tests/` contains .bak files | Old test files | Already merged into `_TEST.py`, safe to delete |

---

## Database Schema (dom_graph_unified.db)

### nodes
```sql
node_id, domain, node_type, name, qualified_name, description, content,
properties, domain_tags, complexity_level, confidence, status, score,
parent_node_id, source_file, line_start, line_end, hash, version, created, updated
```

### edges
```sql
edge_id, domain, src_node_id, src_type, dst_node_id, dst_type, edge_type,
evidence, confidence, weight, created
```

### rules
```sql
rule_id, domain, rule_type, target_node_id, condition_expr, resolution_expr,
score_expr, base_score, max_score, priority, description, category,
correction, anti_pattern, implementation, is_active, created
```

### decisions
```sql
decision_id, domain, decision_type, input_context, chosen_node_id,
chosen_name, decision_score, reason, reason_trace, evaluated, state,
resume_action, is_active, created
```

### snapshots
```sql
snapshot_id, domain, snapshot_type, target_node_id, project_name, progress,
state, resume_action, content, hash, notes, is_active, created
```

---

## ContextRAM Integration

`dom_graph_bridge.py` converts engine output to ContextRAM ContextAssembly shape:

```
decisions[]  <- DomGraphEngine decide output (chosen fix)
facts[]      <- DomGraphEngine candidates (knowledge nodes)
rules[]      <- DomGraphEngine when_rules (triggered rules)
memories[]   <- DomGraphEngine past decisions
reason_trace <- DomGraphEngine trace steps
```

Called by Swift `ctx` binary via subprocess:
```bash
python3 dom_graph_bridge.py to_context_assembly --domain codefix --query "fix deadlock" --file server.py
```

---

## Dependencies

- Python 3.13+
- PyQt6 (for GUI viewers, ChatGui, TokenCounter)
- Tkinter (for 8 graph viewers, Dom_Graph_Gui)
- numpy (for 26-eyes tensor analysis)
- sqlite3 (built-in, for all DBs)
- MySQL (optional, for learned_rules bridge in AgentGraph)
- PyTorch (for brain_model*.pt files)
- Node.js (for brain_server/)
