# Pipeline Gap Analysis — All 10 Pipelines + Garmin

> Graph all pipelines. Find where they connect, where they don't, and where the holes are.

---

## The 10 Pipelines

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PIPELINE ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. CODE→DB PIPELINE (PIPELINE.md)                                  │
│     Files → Ingest → Graph → Reason → Validate → Repair → Export    │
│     DB: dom_graph.db / MySQL vb_shared                              │
│                                                                     │
│  2. 8-GRAPH WORKFLOW (WORKFLOW_8_GRAPH_PIPELINE.md)                 │
│     Idea → Plan → Spec → Flow → Lifecycle → Dep → Error → Orch      │
│     → Gap → Code                                                    │
│     DB: v20_hybrid_best.db (decision_nodes, decision_edges)         │
│                                                                     │
│  3. UTILITIES PIPELINE (UTILITIES_PIPELINE.md)                      │
│     Config.TRIGGERS → Scheduler → Orchestrator → Utility.Run()      │
│     DB: SQLite config (chat_mover_config.db)                        │
│                                                                     │
│  4. CHAT INGESTION (CHAT_INGESTION_PIPELINE.md)                     │
│     Sources → Classify → Filter → Parse → Import → Embed → Verify   │
│     DB: MySQL Chat_History, cascade_chats, chatgpt_chats, devin     │
│                                                                     │
│  5. ERROR CAPTURE (ERROR_CAPTURE_PIPELINE.md)                       │
│     Code Runs → Error → Capture → SQLite + MySQL → Prevent          │
│     DB: SQLite unified_cache.db + MySQL vb_shared (10,590 rules)    │
│                                                                     │
│  6. BCL CODE GRAPH (BCL_CODE_GRAPH_PIPELINE.md)                    │
│     .py → AST → Classes/Methods → CU → BCL Identity → MySQL        │
│     DB: MySQL vb_code_test (655 methods, 4,147 edges, 24 units)    │
│                                                                     │
│  7. CLI SAFE EXECUTION (CLI_SAFE_EXECUTION_PIPELINE.md)            │
│     Command → Validate → Execute → Detect → Query KB → Learn       │
│     DB: MySQL vb_shared (10,590 rules) + SQLite error_knowledge    │
│                                                                     │
│  8. CONTEXT EXPANSION (CONTEXT_EXPANSION_PIPELINE.md)              │
│     Chat → Parse → Nodes/Edges → In-RAM SQLite → Graph → Domain    │
│     → BCL Identity → Every file carries its identity               │
│     DB: In-RAM SQLite + dom_graph.db + MySQL devin_messages        │
│                                                                     │
│  9. BCL TEMPLATE MAKER (BCL_TEMPLATE_MAKER_PIPELINE.md)            │
│     Header Editor → Template → Stamp → Capsule → Verify            │
│     DB: bcl_header.txt + MySQL vb_shared.rule_tokens (238 tokens)  │
│                                                                     │
│  10. CONFIG CASCADE (CONFIG_CASCADE_PIPELINE.md)                   │
│     Scan .py → Extract Constants → Generate Config.py → Verify     │
│     DB: Config.py per domain (26+ files) + ConfigEngine (Section 52) │
│                                                                     │
│  GARMIN: CodeGPS navigator visualizes all 10 pipelines as roads    │
│     Green=success, Red=failed, Yellow=partial, Gray=not built      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

> **GARMIN PRINCIPLE:** Pipelines are the roads. The Garmin navigator drives on them.
> Without pipelines, the Garmin has no roads. Without the Garmin, no navigation.
> This concept must be captured in the Garmin's help/config file.
>
> The 10 Roads:
> 1. Code→DB — 2. 8-Graph — 3. Utilities — 4. Chat Ingestion — 5. Error Capture
> 6. BCL Code Graph — 7. CLI Safe Execution — 8. Context Expansion — 9. BCL Template Maker
> 10. Config Cascade
```

---

## Spec Graph — What Exists

### Pipeline 1: Code→DB

| Node | Type | Status |
|---|---|---|
| INGEST | stage | DONE |
| GRAPH | stage | DONE |
| REASON | stage | NOT BUILT |
| REGRAPH | stage | NOT BUILT |
| VALIDATE | stage | DONE (Fast Method) |
| PLAN | stage | NOT BUILT |
| REPAIR | stage | DONE (Fast Method) |
| CONFIG | stage | NOT BUILT |
| EXPORT | stage | DONE (Fast Method) |
| VERIFY | stage | DONE (py_compile + VbsScanner) |
| ARCHIVE | stage | NOT BUILT |
| SYNC | stage | NOT BUILT |

### Pipeline 2: 8-Graph Workflow

| Node | Type | Status |
|---|---|---|
| plan_graph | graph | EXISTS (Dom_Graph_Plan.py) |
| spec_graph | graph | EXISTS (Dom_Graph_Spec.py) |
| spec_flow | graph | EXISTS (Dom_Graph_Flow.py) |
| lifecycle_graph | graph | EXISTS (Dom_Graph_Lifecycle.py) |
| dep_graph | graph | EXISTS (Dom_Graph_Dep.py) |
| error_graph | graph | EXISTS (Dom_Graph_Error.py) |
| orch_graph | graph | EXISTS (Dom_Graph_Orch.py) |
| gap_graph | graph | EXISTS (Dom_Graph_Gap.py) |
| CognitiveLoopWalker | engine | EXISTS (cognitive_loop_walker.py) |
| Dom_workflow | domain | EXISTS (Dom_workflow.py) |

### Pipeline 3: Utilities

| Node | Type | Status |
|---|---|---|
| Config | config | DONE |
| Scheduler | scheduler | DONE |
| Orchestrator | orchestrator | DONE |
| MSearch | utility | DONE |
| Indexer | utility | DONE |
| VbsScanner | utility | DONE |
| VbsTest | utility | DONE |
| Cleaner | utility | DONE |
| Compress | utility | DONE |
| SystemCheck | utility | DONE |
| DomAudit | utility | DONE |
| DiffCheck | utility | DONE |
| StatsReport | utility | DONE |
| PreFlight | utility | DONE |
| ContentExtract | utility | DONE |
| ErrorTracker | utility | DONE |
| ErrorHandler | utility | DONE |
| Backup | utility | DONE |

### Pipeline 4: Chat Ingestion

| Node | Type | Status |
|---|---|---|
| chat_mover.py (main) | pipeline | DONE |
| Config.py | config | DONE |
| chatgpt_mysql_ingest.py | ingester | DONE |
| cascade_mysql.py | ingester | DONE |
| CascadeIngester.py | ingester | DONE (VBStyle) |
| Devin_Chat_msql.py | ingester | DONE |
| MySQLIngester.py | ingester | DONE (VBStyle) |
| Qdrant embeddings | embedder | DONE (optional) |
| Pipeline locking | safety | DONE |
| Pipeline state | tracking | DONE |
| Validation mode | validator | DONE |
| Error knowledge | learning | DONE |

---

## Dependency Graph — How They Connect

```
Pipeline 4 (Chat Ingestion)
    │
    │ chats contain code discussions
    │ → mine for lessons (Stage 3c in Pipeline 1)
    │
    ▼
Pipeline 1 (Code→DB)
    │
    │ code graph needs visualization
    │ → 8-graph workflow shows the structure
    │
    ▼
Pipeline 2 (8-Graph Workflow)
    │
    │ workflow needs automated execution
    │ → utilities pipeline runs triggers
    │
    ▼
Pipeline 3 (Utilities)
    │
    │ utilities scan/validate/repair code
    │ → results feed back into Pipeline 1 DB
    │
    ▼
    cycles back to Pipeline 1
```

### Cross-Pipeline Edges

| From | To | Edge Type | Status |
|---|---|---|---|
| Chat Ingestion → Code→DB | MINE_PAST (Stage 3c) | **NOT BUILT** — chats should be mined for code lessons |
| Code→DB → 8-Graph Workflow | VISUALIZE | **PARTIAL** — Dom_Graph files exist but not connected to dom_graph.db |
| 8-Graph Workflow → Utilities | AUTOMATE | **NOT BUILT** — workflow should trigger utilities |
| Utilities → Code→DB | FEEDBACK | **PARTIAL** — VbsScanner feeds violations but not into dom_graph.db |
| Chat Ingestion → Utilities | TRIGGER | **NOT BUILT** — chat import should trigger code_change pipeline |
| Code→DB → Chat Ingestion | REFERENCE | **NOT BUILT** — code graph should reference chat sessions |

---

## Gap Graph — What's Missing

### GAP 1: No MINE_PAST integration (Chat → Code)

**Problem:** Pipeline 1 Stage 3c says "scan devin_messages, cascade_chats.messages, chatgpt_chats.messages for findings about each method." This is NOT BUILT.

**Fix:** Create a `ChatMiner` utility that:
1. Queries `Chat_History.messages` for method names
2. Extracts findings ("found a bug in X", "the fix is Y")
3. Writes `[@KnownBugs]`, `[@Gotchas]`, `[@FixesApplied]` stamps to `stamps` table
4. Attaches stamps to `code_units` by method name match

### GAP 2: dom_graph.db not connected to 8-graph viewers

**Problem:** The 8 graph viewers (`Dom_Graph_Plan.py`, etc.) use hardcoded data, not `dom_graph.db`.

**Fix:** Each viewer should:
1. Query `dom_graph.db` for classes, methods, edges
2. Render the graph from DB data, not hardcoded constants
3. Update when DB changes

### GAP 3: No workflow → utility trigger bridge

**Problem:** The 8-graph workflow produces a plan, but doesn't trigger utilities to execute it.

**Fix:** After Gap Graph (step 8), if gaps found:
1. Auto-create `Config.TRIGGERS["workflow_gap"]` entry
2. Scheduler fires it
3. Orchestrator dispatches to relevant utilities (Indexer, VbsScanner, etc.)

### GAP 4: Chat import doesn't trigger code_change pipeline

**Problem:** When chats are ingested, they may reference code changes, but no trigger fires.

**Fix:** After `chat_mover.py` Step 4 (Import):
1. Scan imported messages for file paths (e.g., `/Users/wws/...`)
2. If file paths found → `fire_event("code_change")`
3. Utilities pipeline runs VbsTest, ContentExtract on those files

### GAP 5: No unified pipeline state across all 4 pipelines

**Problem:** Each pipeline tracks its own state independently. No way to see "all 4 pipelines ran successfully."

**Fix:** Create a `pipeline_registry` table in MySQL:
```sql
CREATE TABLE pipeline_registry (
  pipeline_name VARCHAR(50),
  last_run TIMESTAMP,
  status VARCHAR(50),
  items_processed INT,
  errors INT,
  details JSON
);
```

### GAP 6: REASON stage not built (Code→DB)

**Problem:** Stage 3 (REASON) is the "hard part" — surface stamps, deep stamps, mine past. None of it is built.

**Fix:** This is the biggest gap. Requires:
1. SURFACE_STAMP: automated docstring/BCL extraction → `stamps` table
2. DEEP_STAMP: AI reasoning per method (expensive, on-demand)
3. MINE_PAST: chat mining (see GAP 1)

### GAP 7: ARCHIVE stage not built (Code→DB)

**Problem:** No automatic archiving of old files before overwriting.

**Fix:** Before EXPORT writes files:
1. Copy current files to `archive/YYYY-MM-DD/`
2. Write new files
3. Log archive event in DB

### GAP 8: SYNC stage not built (Code→DB)

**Problem:** No file hash comparison before pipeline runs. Can't detect if files were edited outside the pipeline.

**Fix:** Before INGEST:
1. Compute SHA-256 of each .py file
2. Compare to `code_files.file_hash` in DB
3. Flag drift: "file X was edited outside pipeline"

---

## Orchestration Graph — Who Calls Who

```
ROOT: User / Cron
  ├── Pipeline 4: Chat Ingestion
  │   ├── chat_mover.py (main)
  │   │   ├── Config.py
  │   │   ├── MySQLConn
  │   │   ├── classify_content
  │   │   ├── parse_chat
  │   │   ├── import_session
  │   │   ├── embed_messages (Qdrant)
  │   │   └── verify_import
  │   ├── chatgpt_mysql_ingest.py (standalone)
  │   ├── cascade_mysql.py (standalone)
  │   │   ├── decrypt_pb
  │   │   ├── scan_trajectory
  │   │   └── export_md
  │   └── Devin_Chat_msql.py (standalone)
  │
  ├── Pipeline 1: Code→DB
  │   ├── _ingest_eyes.py (ingest)
  │   ├── _fix_all.py (repair)
  │   └── VbsScanner (verify)
  │
  ├── Pipeline 2: 8-Graph Workflow
  │   ├── Dom_Graph_Plan.py
  │   ├── Dom_Graph_Spec.py
  │   ├── Dom_Graph_Flow.py
  │   ├── Dom_Graph_Lifecycle.py
  │   ├── Dom_Graph_Dep.py
  │   ├── Dom_Graph_Error.py
  │   ├── Dom_Graph_Orch.py
  │   ├── Dom_Graph_Gap.py
  │   ├── cognitive_loop_walker.py
  │   └── Dom_workflow.py
  │
  └── Pipeline 3: Utilities
      ├── Scheduler
      │   └── Orchestrator
      │       ├── MSearch
      │       ├── Indexer
      │       ├── VbsScanner
      │       ├── VbsTest
      │       ├── Cleaner
      │       ├── Compress
      │       ├── SystemCheck
      │       ├── DomAudit
      │       ├── DiffCheck
      │       ├── StatsReport
      │       ├── PreFlight
      │       ├── ContentExtract
      │       ├── ErrorTracker
      │       ├── ErrorHandler
      │       └── Backup
```

---

## Error Graph — Where They Fail

| Pipeline | Failure Point | Recovery | Status |
|---|---|---|---|
| Chat Ingestion | MySQL not running | Log error, exit 1 | HANDLED |
| Chat Ingestion | .pb decryption fails | Skip file, continue | HANDLED |
| Chat Ingestion | Duplicate content hash | Skip import | HANDLED |
| Chat Ingestion | Qdrant not available | Skip embeddings, continue | HANDLED |
| Code→DB | Ingest syntax error | Skip file, continue | HANDLED |
| Code→DB | Repair breaks file | py_compile catches it | HANDLED |
| Code→DB | File edited outside pipeline | NOT HANDLED (SYNC not built) | **GAP 8** |
| 8-Graph Workflow | Hardcoded data goes stale | NOT HANDLED | **GAP 2** |
| Utilities | Utility crashes | on_fail policy (report/continue/escalate/cancel) | HANDLED |
| Utilities | Scheduler thread dies | NOT HANDLED | **MINOR GAP** |
| Cross-pipeline | Chat references code change | NOT HANDLED | **GAP 4** |
| Cross-pipeline | No unified state tracking | NOT HANDLED | **GAP 5** |

---

## Pipeline 5: Error Capture

| Node | Type | Status |
|---|---|---|
| ErrorCapture (SQLite) | capture | DONE |
| CacheDb (error_knowledge) | storage | DONE |
| ErrorTracker (MySQL query) | lookup | DONE |
| ErrorHandler (runtime) | handler | DONE |
| DomGovernance (policies) | governance | DONE |
| MySQL learned_rules | knowledge | 10,590 rules |
| MySQL know_problems | knowledge | 309 problems |
| MySQL know_solutions | knowledge | 362 solutions |
| MySQL error_knowledge | knowledge | 70 signatures |
| MySQL rule_tokens | rules | 238 tokens |
| Auto-apply fixes | automation | PARTIAL (5 solutions) |
| Cross-domain code import | unified | NOT BUILT |
| ErrorCapture → Code→DB bridge | integration | NOT BUILT |

---

## New Cross-Pipeline Edges (with Pipelines 5-9)

| From | To | Edge Type | Status |
|---|---|---|---|
| Error Capture → Code→DB | FEEDBACK | **NOT BUILT** — captured errors should stamp code_units |
| Error Capture → Utilities | TRIGGER | **PARTIAL** — ErrorHandler exists in Config.TRIGGERS["error"] but not all utilities use it |
| Error Capture → 8-Graph | ERROR_GRAPH | **NOT BUILT** — error_knowledge should feed the error_graph viewer |
| Chat Ingestion → Error Capture | MINE_ERRORS | **NOT BUILT** — chats contain error discussions that should become learned_rules |
| Code→DB → Error Capture | VALIDATE | **PARTIAL** — VbsScanner finds violations but doesn't capture to error_knowledge |
| Utilities → Error Capture | WRAP_ALL | **NOT BUILT** — every utility.Run() should be wrapped by ErrorHandler.consume() |
| BCL Code Graph → Code→DB | FEED_UNITS | **NOT BUILT** — bcl_units should feed into dom_graph.db code_units |
| BCL Code Graph → 8-Graph | SPEC_GRAPH | **NOT BUILT** — bcl_classes/bcl_methods should populate the spec_graph viewer |
| BCL Code Graph → Error Capture | STAMP_ERRORS | **NOT BUILT** — bcl_stamps should link to error_knowledge signatures |
| BCL Code Graph → Garmin | ROADS | **NOT BUILT** — Garmin should show pipeline stages as roads, not just repair routes |
| All 9 Pipelines → Garmin | MAP_DATA | **NOT BUILT** — Garmin needs pipeline_state data to color roads green/red/yellow/gray |
| CLI Safe Exec → Error Capture | FEED_ERRORS | **DONE** — cascade_cli.py queries + writes to error_knowledge and learned_rules |
| CLI Safe Exec → BCL Code Graph | PRE_SCAN | **DONE** — cascade_cli.py scans .py files for VBStyle violations before execution |
| CLI Safe Exec → All Pipelines | EXECUTE | **DONE** — all pipeline scripts run through cascade_cli.py |
| Context Expansion → Chat Ingestion | SOURCE | **DONE** — devin_messages (38K rows) feed context expansion |
| Context Expansion → BCL Code Graph | DOMAINS | **DONE** — domain extraction routes 767/1,445 classes across 75 domains |
| Context Expansion → BCL Template Maker | IDENTITY | **DONE** — chat → graph → domain → BCL identity headers on every file |
| BCL Template Maker → BCL Code Graph | HEADERS | **DONE** — stamped headers parsed by bcl_extractor/BclGenerator |
| BCL Template Maker → Error Capture | COMPLIANCE | **DONE** — vbs_rule_enforcer scans + auto-fixes violations |
| BCL Template Maker → Context Expansion | RULE_TOKENS | **DONE** — 238 rule_tokens govern template generation |
| Context Expansion → 8-Graph | GRAPH_VIEWS | **PARTIAL** — 8 graph views exist in tmp_graph_ingest but not connected to domain_graph.db |
| Context Expansion → Code→DB | IN_RAM_GRAPH | **NOT BUILT** — in-RAM SQLite graph should feed dom_graph.db |
| CLI Safe Exec → Context Expansion | MINE_ERRORS | **NOT BUILT** — execution logs should feed back into context graph as ERROR nodes |
| Config Cascade → BCL Template Maker | CONFIG_HEADERS | **DONE** — generated Config.py files get BCL headers via ConfigCascade._build_config_content |
| Config Cascade → Error Capture | NO_HARDCODE | **PARTIAL** — ConfigCascade extracts hardcoded values but doesn't auto-replace in source yet |
| Config Cascade → All Pipelines | CONFIG | **DONE** — all 26+ domain Config.py files generated/verified by ConfigCascade |
| Config Cascade → Code→DB | CONFIG_UNITS | **NOT BUILT** — extracted config constants should become code_unit metadata in dom_graph.db |
| BCL Template Maker → Config Cascade | HEADER_CHECK | **DONE** — ConfigCascade.verify() checks for BCL headers in Config.py files |

---

## Pipeline 6: BCL Code Graph

| Node | Type | Status |
|---|---|---|
| ingest_bcl.py (AST → SQLite) | ingest | DONE |
| bcl_mysql_ingestor.py (AST → MySQL) | ingest | DONE (54 files, 655 methods) |
| FeatureExtractor | extract | DONE |
| IRCompiler | compile | DONE |
| BCLEngine (LEX→PARSE→VALIDATE→FIX→SERIALIZE) | engine | DONE |
| BclGenerator (AST → BCL headers) | generate | DONE |
| bcl_identity_generator (4-level tokens) | identity | DONE |
| bcl_object_database (SQLite object DB) | storage | DONE |
| BclProjector (IR → .bcl view) | project | DONE |
| BclStampBuilder (reasoning stamps) | stamp | DONE (1 stamp) |
| BclStampStore (stamp CRUD) | stamp | DONE |
| MySQL bcl_codebases | storage | 2 codebases |
| MySQL bcl_classes | storage | 63 classes |
| MySQL bcl_methods | storage | 655 methods |
| MySQL bcl_units | storage | 24 computational units |
| MySQL bcl_edges | graph | 4,147 edges |
| MySQL bcl_stamps | reasoning | 1 stamp |
| MySQL vb_classes | registry | 1,394 classes |
| MySQL vb_methods | registry | 13,818 methods |
| CodeGPS Garmin | navigator | DONE (PyQt6) |
| Garmin help file (pipelines=roads) | config | NOT BUILT |
| Garmin pipeline-as-road mapping | viz | NOT BUILT |

---

## Pipeline 7: CLI Safe Execution

| Node | Type | Status |
|---|---|---|
| State machine (9 states) | engine | DONE |
| Command validation | validate | DONE |
| Command normalization (shlex) | normalize | DONE |
| Subprocess execution | execute | DONE |
| Stuck/freeze/timeout protection | protect | DONE |
| Error pattern detection (12 patterns) | detect | DONE |
| MySQL knowledge base query | query | DONE (10,590 rules) |
| SQLite fallback query | query | DONE |
| Error learning (insert/update) | learn | DONE |
| VBStyle pre-scan | scan | DONE |
| Execution logging (JSONL) | log | DONE |
| Retry with backoff | retry | DONE |
| Dry run mode | dry_run | DONE |
| Process group kill | kill | DONE |

---

## Pipeline 8: Context Expansion

| Node | Type | Status |
|---|---|---|
| GraphEngine (views + algorithms) | engine | DONE |
| CascadeEngine (8-graph gating) | gate | DONE |
| DecisionEngine | decision | DONE |
| AutoGenerator (self-writing graph) | evolve | DONE |
| 8 Graph Views | views | DONE |
| In-RAM SQLite (MemDb) | storage | DONE |
| Node extraction (8 types) | extract | DONE |
| Edge building (7 types) | edges | DONE |
| Graph activation (keyword + semantic + traversal) | activate | DONE |
| Domain extraction (75 domains, 767/1,445 classes) | domain | DONE |
| Domain closure (recursive CTE) | closure | DONE |
| BCL identity headers (every file carries identity) | identity | DONE |
| VBStyle compliance checking | compliance | DONE |
| VBStyle rule enforcement | enforce | DONE |
| Rule token engine (238 tokens) | rules | DONE |
| ContextEngine (gather context) | context | DONE |
| Temporal model (Part 7) | temporal | NOT BUILT |
| Belief/truth tracking (Part 8) | belief | NOT BUILT |
| Open loop detection (Part 9) | loops | NOT BUILT |
| Importance scoring (Part 10) | scoring | PARTIAL |
| Context window assembly (Part 11) | assembly | NOT BUILT |
| Contradiction detection (Part 12) | contradiction | NOT BUILT |
| Source provenance (Part 13) | provenance | PARTIAL |
| Confidence scoring (Part 14) | confidence | PARTIAL |
| Graph compression (Part 15) | compress | NOT BUILT |
| Multi-hop reasoning (Part 16) | reasoning | PARTIAL |
| Entity resolution (Part 17) | resolve | NOT BUILT |
| Graph diff (Part 18) | diff | NOT BUILT |
| Active learning (Part 19) | active | NOT BUILT |
| Graph export (Part 20) | export | DONE |

---

## Pipeline 9: BCL Template Maker

| Node | Type | Status |
|---|---|---|
| BCL Header Editor (PyQt6 GUI) | editor | DONE |
| Template buttons (6 types) | template | DONE |
| BCL syntax highlighter | highlight | DONE |
| Live reload | reload | DONE |
| bcl_header.txt (template file) | template | DONE |
| Stamp engine (inject headers) | stamp | DONE |
| Capsule builder | capsule | DONE |
| VBStyle compliance checking | compliance | DONE |
| VBStyle rule enforcement | enforce | DONE |
| Rule token engine (238 tokens) | rules | DONE |
| Rule cluster graph | graph | DONE |
| Rule coverage graph | graph | DONE |
| Rule gap graph | graph | DONE |
| BclGenerator (AST → BCL header) | generate | DONE |
| BclStampBuilder (reasoning stamps) | stamps | DONE |
| BclStampStore (stamp CRUD) | stamps | DONE |
| All .py files carry identity | identity | MOSTLY DONE |

---

## Pipeline 10: Config Cascade

| Node | Type | Status |
|---|---|---|
| ConfigCascade (scan/extract/generate/read/write/update/verify/catalog) | engine | DONE |
| AST-based constant extraction | extract | DONE |
| Config.py generation with VBStyle headers | generate | DONE |
| Config.py VBStyle compliance verification (11 checks) | verify | DONE |
| Project-wide config catalog | catalog | DONE (26+ files) |
| ConfigEngine (Section 52 — env vars, feature flags, defaults, overrides) | engine | DONE |
| ConfigExtractor (regex-based, no AST) | extract | DONE |
| Gold standard template (BookSystem) | template | DONE (1,703 lines) |
| All domains have Config.py | coverage | DONE (26+ files) |
| All code imports from Config (no hardcode) | compliance | PARTIAL |
| Auto-extract hardcoded values from .py → Config.py | extract | PARTIAL |
| Config diff (what changed between two configs) | diff | NOT BUILT |
| Config merge (merge multiple domain configs) | merge | NOT BUILT |
| Config inheritance (domain inherits from parent) | inherit | NOT BUILT |

---

## Summary: 23 Gaps Found (updated with Pipeline 10 + Garmin)

| # | Gap | Severity | Pipeline | Fix Effort |
|---|---|---|---|---|
| 1 | No MINE_PAST (chat → code lessons) | HIGH | 1←4 | Medium |
| 2 | 8-graph viewers not connected to DB | HIGH | 1↔2 | Medium |
| 3 | No workflow → utility trigger bridge | MEDIUM | 2→3 | Small |
| 4 | Chat import doesn't trigger code_change | MEDIUM | 4→3 | Small |
| 5 | No unified pipeline state | MEDIUM | ALL | Small |
| 6 | REASON stage not built | HIGH | 1 | Large |
| 7 | ARCHIVE stage not built | LOW | 1 | Small |
| 8 | SYNC stage not built | MEDIUM | 1 | Small |
| 9 | Captured errors not stamped on code_units | MEDIUM | 5→1 | Small |
| 10 | Error knowledge not feeding error_graph | MEDIUM | 5→2 | Small |
| 11 | Chat error discussions not mined for learned_rules | HIGH | 4→5 | Medium |
| 12 | Not all utilities wrapped by ErrorHandler | MEDIUM | 3→5 | Small |
| 13 | bcl_units not feeding dom_graph.db code_units | MEDIUM | 6→1 | Small |
| 14 | bcl_classes/methods not populating spec_graph | MEDIUM | 6→2 | Small |
| 15 | Garmin help file missing pipelines=roads concept | HIGH | Garmin | Small |
| 16 | Garmin not showing pipeline stages as roads | HIGH | Garmin | Medium |
| 17 | Context expansion graph not feeding dom_graph.db | MEDIUM | 8→1 | Small |
| 18 | CLI execution logs not feeding context graph | MEDIUM | 7→8 | Small |
| 19 | Context expansion Parts 7-19 not built | HIGH | 8 | Large |
| 20 | Some files may still lack BCL identity headers | LOW | 9 | Small |
| 21 | ConfigCascade doesn't auto-replace hardcoded values in source | HIGH | 10 | Medium |
| 22 | Config constants not feeding dom_graph.db code_units | MEDIUM | 10→1 | Small |
| 23 | Config diff/merge/inheritance not built | LOW | 10 | Medium |

**8 HIGH severity gaps. 9 MEDIUM. 4 LOW.**
