# Context Expansion Pipeline — Chat → In-RAM SQLite → Graph → Domain → Identity

> **Core thesis:** Chats are not just conversations — they are the raw material
> from which domains, graphs, and file identities are forged. Chat content is
> expanded into an in-RAM SQLite database, mined for structure, and the extracted
> knowledge becomes the identity that every file carries.
>
> **The chain that happened:** Chat → Parse → Nodes/Edges → Graph → Domains →
> BCL Identity → Every file carries its identity.

---

## Pipeline Overview

```
Chat Sources (MD, JSON, MySQL devin_messages)
       ↓
  PARSE — Extract nodes: CONCEPTS, FILES, TOOLS, INTENT, ERRORS, DECISIONS
       ↓
  EDGE BUILD — Typed relationships: REFERENCES, DEPENDS_ON, CAUSED_BY, RESOLVES
       ↓
  IN-RAM SQLITE — :memory: database for fast graph operations
       ↓
  GRAPH ACTIVATION — Keyword + semantic match + edge traversal + recency/frequency boost
       ↓
  DOMAIN EXTRACTION — Clusters of connected concepts → domains
       ↓
  BCL IDENTITY — Every file gets [@GHOST], [@VBSTYLE], [@FILEID], [@SUMMARY]
       ↓
  PERSIST — MySQL (devin_chat_turns), SQLite (dom_graph.db), Qdrant (embeddings)
```

---

## Stages

### Stage 1: NODE EXTRACTION — Parse Chat Content

**Tools:** `tmp_graph_ingest/GraphEngine.py`, `tmp_graph_ingest/CascadeEngine.py`

Read chat markdown/JSON and identify node types:

| Node Type | What It Captures |
|---|---|
| `CONCEPT` | Ideas, patterns, architectures mentioned |
| `FILE` | File paths referenced in chat |
| `TOOL` | Tools, utilities, scripts discussed |
| `INTENT` | What the user wanted to accomplish |
| `ENTITY` | Named things (classes, methods, variables) |
| `ERROR` | Bugs, failures, tracebacks |
| `DECISION` | Choices made during the session |
| `VALUE` | Configuration values, constants |

**Node schema:**
```sql
CREATE TABLE nodes (
    id INTEGER PRIMARY KEY,
    node_type TEXT NOT NULL,      -- CONCEPT, FILE, TOOL, INTENT, etc.
    value TEXT NOT NULL,          -- the extracted content
    timestamp TEXT,               -- when in the chat it appeared
    message_source TEXT,          -- which message it came from
    embedding BLOB,               -- semantic embedding (optional)
    importance_score REAL DEFAULT 0.5,
    mention_count INTEGER DEFAULT 1,
    last_seen TEXT,
    activation_count INTEGER DEFAULT 0
);
```

### Stage 2: EDGE BUILDING — Typed Relationships

**Tools:** `tmp_graph_ingest/GraphEngine.py`

Build typed edges between nodes:

| Edge Type | Meaning | Detection |
|---|---|---|
| `REFERENCES` | A mentions B | Proximity in chat |
| `DEPENDS_ON` | A requires B | Causality / explicit statement |
| `CONTRADICTS` | A conflicts with B | User correction / "actually" |
| `RESOLVES` | A fixes B | "The fix is X" |
| `CAUSED_BY` | A happened because of B | "This error was caused by" |
| `PART_OF` | A is a component of B | Containment |
| `RELATED_TO` | A is connected to B | Repeated mentions, user confirmation |

**Edge schema:**
```sql
CREATE TABLE edges (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL,    -- FK to nodes
    target_id INTEGER NOT NULL,    -- FK to nodes
    relationship_type TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    created_at TEXT
);
```

### Stage 3: IN-RAM SQLITE — Fast Graph Operations

**Tools:** `Cascade_toolStack/arch_test/memdb_real.py` (MemDb), `Cascade_toolStack/arch_test/boot_test.py`

The graph is loaded into an in-RAM SQLite database (`:memory:`) for fast operations:

```python
self.conn = sqlite3.connect(":memory:")
```

**Tables in RAM:**
- `command_queue` — queued graph operations (cmd_id, action, source, target, params, status, result)
- `state_cache` — cached graph state (key, value, updated_at)
- `routing_map` — action → target routing (action_pattern, target_core, target_lib, priority)

**Why in-RAM:**
- Graph traversal requires many JOINs — disk I/O is the bottleneck
- Chat expansion is a burst operation — load, process, extract, flush
- The result (domains, identities) is persisted to disk/MySQL after processing

### Stage 4: GRAPH ACTIVATION — Query the Expanded Context

**Tools:** `tmp_graph_ingest/GraphEngine.py` (search, bfs, dfs, cycle, path, topology)

When the model needs context, the graph is activated:

1. **Keyword match** — find nodes by text content
2. **Semantic match** — Qdrant/MLX embedding similarity
3. **Edge traversal** — BFS/DFS from activated nodes
4. **Recency boost** — newer messages weighted higher
5. **Frequency boost** — nodes mentioned many times weighted higher

**Activation result:** A subgraph of relevant nodes + edges, provided as structured context to the LLM.

### Stage 5: DOMAIN EXTRACTION — Clusters → Domains

**Tools:** `code_store_variations/domain_graph.db` (domain engine), `core/Dom_Vsstyle/vbs_parser.py`

From the expanded chat graph, concept clusters naturally form domains:

1. **Seed word** (e.g. "embeddings") expands into a **cluster** of connected domains
2. **Domain closure** — recursive CTE, bidirectional traversal, seed in → closed cluster out
3. **Class routing** — each real class routed into the right domain by:
   - Name match (high confidence — 483 classes)
   - BCL self-declared (high confidence — 9 classes)
   - Method vote (medium confidence — 165 classes)
   - Code content (low confidence — 110 classes)
4. **Domain purity** — domains own what they ARE, not what they USE

**Result:** 767/1,445 classes (53%) routed across 75 domains, 0 conflicts.

**Domain tables:**
- `domain_nodes` — domain definitions
- `domain_connections` — cluster edges (7 cluster domains, 9 edges)
- `domain_classes` — abstract class structure per domain
- `domain_identity` — keyword + priority per domain
- `class_routing` — routing decisions
- `class_owner` VIEW — conflict tie-break by most-specific keyword
- `domain_closure` VIEW — recursive CTE for cluster expansion

### Stage 6: BCL IDENTITY — Every File Carries Its Identity

**Tools:** `core/Dom_Vsstyle/vbs_parser.py`, `core/Dom_Vsstyle/vbs_rule_enforcer.py`, `core/Dom_Vsstyle/vbs_compliance.py`

**This is the vital outcome:** Every file in the codebase carries its identity as BCL headers.

**The identity headers (the "nametag" every file must carry):**
```python
#[@GHOST]{("file_path=...";"identity=ClassName";"purpose=What it does";"date=2026-06-26";"version=1.0";"author=Cascade";"chat_link=mysql://devin/devin_sessions?id=...")}
#[@VBSTYLE]{("auth=Cascade";"role=domain";"return=Tuple3";"orch=none";"no=no_decorators|no_print|no_hardcoded";"model=one_class_one_domain_one_authority_complete")}
#[@FILEID]{("session_id=...";"context=Session Name";"purpose=What this file does")}
#[@SUMMARY]{("What happened in the session that created this file")}
#[@CLASS]{("class=ClassName";"domain=domain_name";"authority=single")}
#[@METHOD]{("method=Run";"type=dispatch")}
```

**Compliance checks (vbs_compliance.py):**
- `ghost_header` — `#[@GHOST]` present
- `vbstyle_header` — `#[@VBSTYLE]` present
- `tuple3_return` — methods return `(1, data, None)` pattern
- `state_dict` — `self.state = {}` present
- `pascal_case` — class names are PascalCase
- `uppercase_constants` — constants are UPPERCASE
- `no_print` — no `print()` calls
- `no_decorators` — no `@property`, `@staticmethod`, `@classmethod`
- `no_self_underscore` — no `self._xxx`
- `no_tabs` — spaces only
- `has_run` — `Run()` dispatch method exists

**Rule enforcement (vbs_rule_enforcer.py):**
- `scan_file` — scan single file for violations
- `scan_folder` — scan all .py files in a directory
- `auto_fix` — automatically fix safe violations
- `check_vbstyle` — full compliance check

### Stage 7: GRAPH EVOLUTION — The 20-Component Spec

**Tools:** `tmp_graph_ingest/AutoGenerator.py`, `tmp_graph_ingest/DecisionEngine.py`

The expanded context graph evolves over time:

**Parts 1-6 (Original — Extraction & Storage):**
1. Node extraction — parse chat, identify concepts/files/tools/intent
2. Edge building — typed relationships
3. Graph activation — keyword + semantic + edge traversal
4. Memory persistence — SQLite, MySQL, Qdrant
5. Integration with LLM — activated subgraph as structured context
6. Iteration & learning — mark useful/insufficient, adjust weights

**Parts 7-20 (Missing Pieces — Retrieval & Reasoning):**
7. **Temporal model** — BEFORE, AFTER, REPLACED_BY, VALID_DURING, SUPERSEDED
8. **Belief/truth tracking** — CLAIM, VERIFIED, REJECTED, UNKNOWN
9. **Open loop detection** — TASK, QUESTION, GOAL, BLOCKER with states
10. **Importance scoring** — per-node importance_score, mention_count, activation_count
11. **Context window assembly** — select nodes that fit in token budget
12. **Contradiction detection** — flag conflicting information
13. **Source provenance** — track where each node came from
14. **Confidence scoring** — per-node confidence based on source reliability
15. **Graph compression** — summarize dense subgraphs
16. **Multi-hop reasoning** — chain edges for complex questions
17. **Entity resolution** — merge duplicate nodes referring to same thing
18. **Graph diff** — what changed between two time points
19. **Active learning** — ask user to resolve uncertain nodes
20. **Graph export** — serialize for external tools (GraphML, JSON, SVG)

### Stage 8: AUTO-GENERATION — Self-Writing Graph

**Tool:** `tmp_graph_ingest/AutoGenerator.py`

When nodes fail during execution:
1. Read failures from `execution_log`
2. Create fallback nodes automatically
3. Deduplicate similar nodes
4. Promote successful paths (above threshold)
5. Prune dead paths (below threshold)

---

## File Locations

```
CONTEXT EXPANSION PIPELINE FILES:
├── tmp_graph_ingest/                     — Graph engine (20 components)
│   ├── GraphEngine.py                    — Graph views + algorithms executor
│   ├── CascadeEngine.py                  — Pre-code validation compiler (8-graph gating)
│   ├── DecisionEngine.py                 — Decision graph engine
│   ├── AutoGenerator.py                  — Self-writing graph evolution
│   ├── GraphOrchestrator.py              — Orchestrates graph pipeline
│   ├── GraphViewer.py                    — Visualize graphs
│   ├── Inspect.py                        — Inspect graph state
│   ├── Verify.py                         — Verify graph integrity
│   ├── Config_graph_engine.py            — Graph engine config
│   ├── ChatViewer.py                     — View chat content
│   ├── TmpWorkspace.py                   — Temporary workspace
│   ├── test_all_on_chat.py               — 20-component spec + test
│   ├── PlanView.py                       — Plan graph view
│   ├── SpecView.py                       — Spec graph view
│   ├── FlowView.py                       — Flow graph view
│   ├── LifecycleView.py                  — Lifecycle graph view
│   ├── DependencyView.py                 — Dependency graph view
│   ├── ErrorView.py                      — Error graph view
│   ├── OrchestrationView.py              — Orchestration graph view
│   └── GapView.py                        — Gap graph view
│
├── Cascade_toolStack/arch_test/          — In-RAM architecture tests
│   ├── memdb_real.py                     — MemDb (in-RAM SQLite: command_queue, state_cache, routing_map)
│   ├── boot_test.py                      — Boot test (MemUnit → MemDB → MemBus → Executor)
│   ├── MemUnit_real.py                   — MemUnit (gravity center)
│   ├── Executor_real.py                  — Executor
│   └── arch_graph.py                     — Architecture graph
│
├── core/Dom_Vsstyle/                     — VBStyle verification domain
│   ├── vbs_parser.py                     — Parser: parse domains, files, BCL headers
│   ├── vbs_compliance.py                 — Compliance: check VBStyle rules
│   ├── vbs_rule_enforcer.py              — RuleEnforcer: scan + auto-fix violations
│   ├── vbs_code_index.py                 — CodeIndex: MySQL code_index CRUD
│   ├── vbs_registry.py                   — Registry: format + output registry
│   ├── vbs_main.py                       — VbsMain: orchestrator entry point
│   ├── vbs_rule_engine.py                — RuleEngine: rule_tokens authority
│   ├── vbs_rule_reader.py                — Read rules from .md files
│   ├── vbs_rule_writer.py                — Write rule tokens to MySQL
│   ├── vbs_rule_cluster_graph.py         — Cluster graph (tokens by shared keywords)
│   ├── vbs_rule_coverage_graph.py        — Coverage graph (rules vs tokens)
│   └── vbs_rule_gap_graph.py             — Gap graph (missing/weak rules)
│
├── code_store_variations/
│   └── domain_graph.db                   — Domain engine (pure SQL, reads v20_hybrid_best.db)
│
├── CACASE The Clevere/
│   └── context_engine.py                 — ContextEngine: gather file/class/method/error/fix/knowledge/graph context
│
└── MySQL:
    ├── devin.devin_messages (38K+ rows)  — Chat messages source
    ├── vb_shared.learned_rules (10,590)  — Learned rules from chats
    └── vb_code_test.vb_classes (1,394)   — Class registry (from domain extraction)
```

---

## The Vital Chain: Chat → Identity

```
Chat Content
    ↓
Parse → Nodes (CONCEPTS, FILES, TOOLS, INTENT, ERRORS, DECISIONS)
    ↓
Edges → (REFERENCES, DEPENDS_ON, CAUSED_BY, RESOLVES)
    ↓
In-RAM SQLite → Fast graph operations
    ↓
Graph Activation → Relevant subgraph for context
    ↓
Domain Extraction → 75 domains from 1,445 classes
    ↓
BCL Identity → [@GHOST] [@VBSTYLE] [@FILEID] [@SUMMARY]
    ↓
EVERY FILE CARRIES ITS IDENTITY
```

**This is why the BCL headers exist.** They are not decoration. They are the
persisted output of the context expansion pipeline. When you read a file's
`#[@GHOST]` header, you are reading the identity that was forged from chat
content, through graph expansion, through domain extraction, into a permanent
nametag that travels with the file forever.

---

## Current Status

| Component | Status | Data |
|---|---|---|
| GraphEngine (views + algorithms) | **DONE** | — |
| CascadeEngine (8-graph gating) | **DONE** | — |
| DecisionEngine | **DONE** | — |
| AutoGenerator (self-writing graph) | **DONE** | — |
| GraphOrchestrator | **DONE** | — |
| 8 Graph Views (Plan/Spec/Flow/Lifecycle/Dep/Error/Orch/Gap) | **DONE** | — |
| In-RAM SQLite (MemDb) | **DONE** | command_queue, state_cache, routing_map |
| Node extraction (8 types) | **DONE** | — |
| Edge building (7 types) | **DONE** | — |
| Graph activation (keyword + semantic + traversal) | **DONE** | — |
| Domain extraction (75 domains) | **DONE** | 767/1,445 classes routed |
| Domain closure (recursive CTE) | **DONE** | — |
| BCL identity headers | **DONE** | All .py files carry headers |
| VBStyle compliance checking | **DONE** | 12+ checks |
| VBStyle rule enforcement | **DONE** | scan + auto-fix |
| VBStyle rule engine (238 tokens) | **DONE** | — |
| ContextEngine (gather context) | **DONE** | 10 gather commands |
| Temporal model (Part 7) | **NOT BUILT** | — |
| Belief/truth tracking (Part 8) | **NOT BUILT** | — |
| Open loop detection (Part 9) | **NOT BUILT** | — |
| Importance scoring (Part 10) | **PARTIAL** | mention_count exists |
| Context window assembly (Part 11) | **NOT BUILT** | — |
| Contradiction detection (Part 12) | **NOT BUILT** | — |
| Source provenance (Part 13) | **PARTIAL** | message_source exists |
| Confidence scoring (Part 14) | **PARTIAL** | confidence in domain routing |
| Graph compression (Part 15) | **NOT BUILT** | — |
| Multi-hop reasoning (Part 16) | **PARTIAL** | BFS/DFS exist |
| Entity resolution (Part 17) | **NOT BUILT** | — |
| Graph diff (Part 18) | **NOT BUILT** | — |
| Active learning (Part 19) | **NOT BUILT** | — |
| Graph export (Part 20) | **DONE** | GraphML, JSON, SVG |
