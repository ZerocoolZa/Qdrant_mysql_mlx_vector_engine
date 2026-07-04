# Graph Engine & Codebase: Existing Code Assets

## Origin

This document maps the existing graph engine code found in the MySQL databases
and local codebase. It is the second design group — the **code asset inventory**
that complements the magnetic radius retrieval design.

The data comes from:
- `graph_computation_units.computation_units` — 2,407 methods across 224 classes
- `vb_code_test.vb_classes` — 1,394 VBStyle classes in MySQL
- `CODEBASE.python_files` — 389K python files ingested
- `vb_shared.learned_rules` — learned rules mentioning "graph"

---

# Database: graph_computation_units

## Overview

```
Database: graph_computation_units
Table:    computation_units
Schema:   1 method = 1 row = 1 computation unit → belongs to 1 class

Columns:
  id, unit_hash, class_name, method_name, signature, body,
  file_path, line_start, line_end, source, domain, role, is_dunder

Sources:
  1. MySQL vb_code_test (1,394 VBStyle classes, 13,818 methods)
     → Filtered to graph-related: 104 classes, 916 methods
  2. Local codebase (/Users/wws/Qdrant_mysql_mlx_vector_engine/)
     → 185 Python files scanned, 120 classes, 1,491 methods

TOTAL: 2,407 computation units across 224 unique classes
```

## Source Breakdown

| Source | Units | Classes |
|--------|-------|---------|
| local | 1,491 | 126 |
| mysql_vb_code_test | 916 | 104 |

## Graph Keywords Used for Filtering

```
graph, node, edge, cascade, decision, embed, vector, memory,
context, brain, cognitive, knowledge, reasoning, semantic,
tfidf, cosine, similarity, traverse, adjacency, topology,
cluster, community, centrality, pagerank, bfs, dfs,
shortest_path, spanning, dag, directed
```

---

# Top 30 Classes by Method Count

| Class | Methods | Source | Domain |
|-------|---------|--------|--------|
| __top_level__ | 129 | local | — |
| AgentGraph | 68 | local | — |
| DbInterrogator | 67 | local | — |
| GraphEngine | 66 | local | — |
| BracketMemoryStore | 47 | mysql_vb_code_test | — |
| BrokenCodeGenerator | 43 | local | — |
| VBStyleClusterAuditCLI | 37 | mysql_vb_code_test | — |
| DomKnowledge | 35 | local + mysql | knowledge |
| AgentBrain | 33 | local | — |
| DomGraph | 31 | local + mysql | graph |
| DomMemory | 31 | local + mysql | memory |
| PlanGraphViewer | 28 | local | — |
| CodeGraph | 27 | mysql_vb_code_test | — |
| DomCodegraph | 27 | local + mysql | codegraph |
| ExecutionGraph | 27 | local | — |
| CognitiveBrain | 26 | mysql_vb_code_test | — |
| DomCryptography | 25 | local + mysql | cryptography |
| GraphViewer | 22 | local | — |
| DBArchitectureGUI | 21 | local | — |
| SmartClassifier | 21 | local | — |
| GuiDecisionEngine | 21 | local + mysql | — |
| DomSearch | 20 | local | — |
| CodeClusterEngine | 20 | mysql_vb_code_test | — |
| DomAnalytics | 20 | local | — |
| Config | 20 | local | — |
| Verify | 19 | local | — |
| CascadeCLI | 19 | mysql_vb_code_test | — |
| ClusterCaptureEngine | 18 | mysql_vb_code_test | — |
| DomLogging | 18 | local | — |
| BrainDb | 17 | local | — |

---

# Core Engine Classes: Method Inventory

## GraphEngine (66 methods)

### Graph Views (the 8-graph pipeline)
| Method | Purpose |
|--------|---------|
| PlanView | Level 1: What are we building? |
| SpecView | Level 2: What exactly exists? |
| FlowView | Level 3: How does it move? |
| LifecycleView | Level 4: When does it run? |
| DependencyView | Level 5: Why does it connect? |
| ErrorView | Level 6: Where does it fail? |
| OrchestrationView | Level 7: Who calls who? |
| GapView | Level 8: What's missing? |

### Graph Operations
| Method | Purpose |
|--------|---------|
| Status | Graph status (nodes, edges counts) |
| Search | Full-text search across graph |
| Bfs | Breadth-first traversal |
| Dfs | Depth-first traversal |
| Path | Shortest path between nodes |
| Cycle | Cycle detection |
| Topology | Topological ordering |
| Instructions | BCL instruction retrieval |

### Class Management
| Method | Purpose |
|--------|---------|
| AddClass | Add class to graph |
| RemoveClass | Remove class from graph |
| InspectCmd | AST inspection |
| VerifyCmd | VBStyle verification |

### Internal Checks
| Method | Purpose |
|--------|---------|
| _check_bcl_completeness | BCL token completeness |
| _check_bcl_coverage | BCL coverage check |
| _check_bcl_method_coverage | BCL method-level coverage |
| _check_closure | CRUD closure check |
| _check_column_docs | Column documentation check |
| _check_crud_coverage | CRUD operation coverage |
| _check_cu_orphans | Orphan computation units |
| _check_db_meta | Database metadata check |
| _check_domain_orchestration | Domain orchestration check |
| _check_empty_table | Empty table detection |
| _check_execution | Execution path check |
| _check_method_pairs | Method pair validation |
| _check_nulls | Null value detection |
| _check_parent_chain | Parent chain validation |
| _check_plan_count | Plan count check |
| _check_status_values | Status value validation |
| _check_table_registry | Table registry check |
| _check_vbstyle_coverage | VBStyle coverage check |
| _check_violations | Violation detection |

### Dispatch
| Method | Purpose |
|--------|---------|
| Run | Main dispatch entry point |
| _GetDb | Database connection |

## AgentGraph (68 methods)

### Graph Building
| Method | Purpose |
|--------|---------|
| Build | Build graph from source |
| BuildCallEdges | Build call relationship edges |
| BuildImportEdges | Build import relationship edges |
| BuildTypedGraph | Build typed graph structure |
| ParsePythonFile | Parse Python file into nodes |
| AddNode | Add node to graph |
| AddEdge | Add edge to graph |

### Graph Analysis
| Method | Purpose |
|--------|---------|
| Centrality | Centrality calculation |
| BetweennessCentrality | Betweenness centrality |
| InfluenceRanking | Influence ranking |
| DetectCommunities | Community detection |
| DetectCycles | Cycle detection |
| GetIslands | Isolated component detection |
| AllPaths | All paths between nodes |
| PathToTarget | Path to target node |
| FindNearestNodeOfType | Nearest node of type |
| FindCallerClass | Find calling class |
| BlastRadius | Impact radius analysis |

### Simulation
| Method | Purpose |
|--------|---------|
| FullSimulate | Full graph simulation |
| PredictNext | Next node prediction |
| MultiStepPlan | Multi-step planning |
| AttendTo | Attention mechanism |
| BootSequence | Boot initialization |
| InitializeSensors | Sensor initialization |

### Persistence
| Method | Purpose |
|--------|---------|
| ReadFromDb | Read graph from database |
| SeedFromMysql | Seed from MySQL |
| Export | Export graph |
| RunWriteDb | Write to database |

### Run Commands (dispatch)
Run, RunAllPaths, RunAttend, RunBlastRadius, RunBootSequence,
RunCentrality, RunCommunities, RunConsolidation, RunCycles,
RunEmotion, RunExport, RunFullSimulate, RunGoals, RunInfluence,
RunIslands, RunPlan, RunPredict, RunReaches, RunReadDb,
RunSeedMysql, RunSelfModify, RunShortestPath, RunSimulate,
RunStructural, RunValidateBoot, RunWorldModel, RunWriteDb, RunYinYang

## CascadeEngine (10 methods)

| Method | Purpose |
|--------|---------|
| Run | Main dispatch |
| Start | Start cascade |
| NextStage | Advance to next stage |
| Stage | Get/set current stage |
| Validate | Validate stage |
| Rewrite | Rewrite stage |
| Rules | Get rules |
| Commit | Commit stage |
| Status | Get status |

## DecisionEngine (13 methods)

| Method | Purpose |
|--------|---------|
| Run | Main dispatch |
| Start | Start decision loop |
| Step | Execute one step |
| End | End decision loop |
| Auto | Automatic mode |
| ExecuteNode | Execute a node |
| GetNode | Get node by ID |
| GetEdges | Get edges |
| MatchesCondition | Check condition |
| History | Get history |
| Log | Log event |
| WriteLog | Write to log |
| Status | Get status |

## GraphViewer (22 methods)

| Method | Purpose |
|--------|---------|
| Run | Main dispatch |
| Headless | Headless mode (no GUI) |
| Render | Render graph |
| DrawGraph | Draw graph on canvas |
| RenderNodes | Render nodes |
| RenderEdges | Render edges |
| LayoutNodes | Position nodes |
| LoadGraph | Load graph data |
| LoadAgentGraphLive | Load from AgentGraph |
| BuildUI | Build UI |
| InitTk | Initialize Tkinter |
| Show | Show viewer |
| ShowDetail | Show node detail |
| OnClick | Click handler |
| OnMotion | Mouse motion handler |
| OnResize | Resize handler |
| ToggleFilter | Toggle filter |
| Reload | Reload graph |
| GetNodeAt | Get node at position |
| Close | Close viewer |

---

# VBStyle Classes in vb_code_test (Graph-Related)

## Graph Classes (20 found)

| Class | id |
|-------|-----|
| ASTCodeGraph | 980 |
| CallGraphLayer | 1021 |
| CodeGraph | 1102 |
| CodeGraphBuilder | 1103 |
| DependencyGraphEngine | 1181 |
| DomCodegraph | 1709 |
| DomGraph | 1755 |
| GraphAuthority | 150 |
| GraphBrain | 15 |
| GraphBuilder | 149 |
| GraphConfig | 142 |
| GraphDomain | 151 |
| GraphLoader | 1246 |
| GraphMaintenance | 1247 |
| GraphStore | 148 |
| ImportGraphLayer | 1272 |
| PatternGraphEngine | 1356 |
| PersistedGraphEngine | 1361 |
| ReasoningGraph | 19 |
| ReasoningGraphV3 | 1408 |

## Brain/Cognitive Classes (10 found)

| Class | id |
|-------|-----|
| CognitiveBrain | 13 |
| CognitiveLoadTracker | 213 |
| CognitiveMemory | 1119 |
| CognitiveSwarm | 1120 |
| DatabaseBrain | 12 |
| GraphBrain | 15 |
| GuiBrain | 1250 |
| LearningBrain | 14 |
| BrainChat | 1014 |
| UltimateCognitiveAI | 694 |

## Memory Classes (10 found)

| Class | id |
|-------|-----|
| AdaptiveMemory | 945 |
| BracketMemoryStore | 1012 |
| ChatMemoryStep1 | 1043 |
| CognitiveMemory | 1119 |
| CorrectionMemoryEngine | 1156 |
| DomMemory | 1761 |
| LongTermMemory | 232 |
| Memory | 230 |
| MemoryConsolidator | 214 |
| MemoryEntry | 1316 |
| MemoryExtractor | 298 |
| MemoryTraceProbe | 510 |
| SessionMemory | 231 |

## Decision Classes (12 found)

| Class | id |
|-------|-----|
| App_GoldGapDecisionPlanner | 960 |
| ApprovalDecisionBuilder | 974 |
| ApprovalDecisionEngine | 975 |
| AuthorityDecisionEngine | 988 |
| DecisionGate | 1170 |
| DecisionPlanner | 1171 |
| DecisionReader | 1172 |
| DecisionSchema | 1173 |
| GuiDecisionEngine | 445 |
| RepairDecisionEngine | 1412 |
| UnitBrkDecisionReporter | 1569 |
| UnitClosureDecision | 1576 |
| UnitDecisionChoiceReader | 1577 |
| UnitGapDecisionPlanner | 1583 |
| UnitOutcomeDecision | 1588 |
| VirtualDecisionExecutor | 1639 |
| VirtualDecisionPersistenceIntegrator | 1640 |

## Cascade Classes (2 found)

| Class | id |
|-------|-----|
| CascadeCLI | 1023 |
| CascadeDeterminismEngine | 346 |

## Agent Classes (7 found)

| Class | id |
|-------|-----|
| Agent | 946 |
| AgentCore | 947 |
| AgentSwarm | 948 |
| AgentSwarmGUI | 949 |
| MultiAgentLearning | 1331 |
| SSHAgent | 1482 |
| ZramAgentLayer | 1667 |

---

# MySQL References: "Graph" in the Database

## vb_shared.learned_rules (15 hits)

| id | pattern | fix_action |
|----|---------|------------|
| 23 | no_cleanup: self.state["graph"] = G | Add clear command to free graph memory |
| 16996 | change the decision graph engine | Follow rule: prohibition |
| 17001 | affect graph behavior | Follow rule: prohibition |
| 17004 | store the entire graph as one text blob in one row | Follow rule: prohibition |
| 17006 | replace the graph with it | Follow rule: prohibition |
| 17008 | creates more questions forever, the graph never ends | Follow rule: requirement |
| 17944 | qgraphicsscene rendering failure | Follow rule: bug |
| 18913 | manage domain: graphics | Follow rule: requirement |
| 18990 | manage domain: graphql | Follow rule: requirement |
| 19158 | produce a deterministic execution graph | Follow rule: requirement |
| 20008 | replace the ledger or graph | Follow rule: prohibition |
| 20616 | refer to your knowledge graph as your | Follow rule: requirement |
| 22229 | the central awareness graph | Follow rule: requirement |
| 22414 | exist in the code, and persist them to an atomicviz graph file | Follow rule: prohibition |
| 22646 | successfully identify the problematic subgraph | Follow rule: requirement |

## vb_shared.tokens (2 hits)

| id | name | meaning |
|----|------|---------|
| 2044 | [@BuildDepGraph] | Create dependency graph from mappings |
| 2154 | [@ClassificationMode] | ("{("Fingerprint source";"Load token graph";"Assign fixed labels")}") |

## Notable Rules

- **id=23**: Graph memory cleanup rule — "Add clear command to free graph memory"
- **id=16996**: Prohibition on changing the decision graph engine
- **id=17004**: Prohibition on storing graph as text blob — must be structured
- **id=17008**: Requirement — graph should not create infinite questions
- **id=20616**: Requirement — refer to knowledge graph by name
- **id=22229**: Requirement — central awareness graph concept
- **id=22646**: Requirement — identify problematic subgraphs

---

# Coverage Assessment: Existing Code vs 21-Component Spec

| Component | Existing Code | Coverage |
|-----------|--------------|----------|
| 1. Node Extraction | GraphEngine.AddClass, AgentGraph.ParsePythonFile, AgentGraph.AddNode | EXISTS |
| 2. Edge Building | AgentGraph.BuildCallEdges, AgentGraph.BuildImportEdges, AgentGraph.BuildTypedGraph | EXISTS |
| 3. Graph Activation | GraphEngine.Search, GraphEngine.Bfs, GraphEngine.Dfs | EXISTS |
| 4. Memory Persistence | AgentGraph.ReadFromDb, AgentGraph.RunWriteDb, BracketMemoryStore | PARTIAL |
| 5. LLM Integration | (none found) | MISSING |
| 6. Iteration/Learning | AgentGraph.RunSelfModify, AgentGraph.SelfModify | PARTIAL |
| 7. Temporal Model | (none found) | MISSING |
| 8. Belief/Truth Tracking | (none found) | MISSING |
| 9. Open Loop Detection | GraphEngine.GapView | PARTIAL |
| 10. Importance Scoring | AgentGraph.InfluenceRanking, AgentGraph.Centrality | PARTIAL |
| 11. Identity Resolution | (in identity tables, not in graph code) | PARTIAL |
| 12. Hierarchy Discovery | GraphEngine.Topology, AgentGraph.BootSequence | PARTIAL |
| 13. Contradiction Engine | (none found) | MISSING |
| 14. Memory Compression | MemoryConsolidator, AgentGraph.RunConsolidation | PARTIAL |
| 15. Query Planner | (none found) | MISSING |
| 16. Evidence Builder | (none found) | MISSING |
| 17. Activation Feedback | AgentGraph.AttendTo, AgentGraph.RunAttend | PARTIAL |
| 18. Episodic/Semantic | SessionMemory, LongTermMemory, DomMemory | PARTIAL |
| 19. Causal Graph | ReasoningGraph, ReasoningGraphV3 (exist in DB) | PARTIAL |
| 20. Memory Governor | (none found) | MISSING |
| 21. Observation Engine | (none found) | MISSING |

## Summary

- **EXISTS**: 3 components (Node Extraction, Edge Building, Graph Activation)
- **PARTIAL**: 10 components (Memory, Learning, Open Loops, Importance, Hierarchy, Compression, Feedback, Episodic, Causal, Identity)
- **MISSING**: 8 components (LLM Integration, Temporal, Truth, Contradiction, Query Planner, Evidence, Governor, Observation)

**Existing code covers ~30% of the 21-component spec fully, ~50% partially, ~20% is completely missing.**

---

# Key Findings

1. **AgentGraph is the richest class** (68 methods) — has simulation, prediction, attention, self-modification, and persistence. This is the closest thing to a "brain" in the codebase.

2. **GraphEngine is the validator** (66 methods) — mostly checks and views. It validates structure but doesn't reason.

3. **ReasoningGraph and ReasoningGraphV3 exist in vb_code_test** but are NOT in the local codebase — they were ingested from MySQL but may not be actively used.

4. **17 graph-related classes exist in vb_code_test** that are NOT in the local codebase — potential reuse candidates.

5. **The 8-graph pipeline** (Plan → Spec → Flow → Lifecycle → Dependency → Error → Orchestration → Gap) is fully implemented in GraphEngine as view methods.

6. **Memory classes exist** (SessionMemory, LongTermMemory, MemoryConsolidator, CognitiveMemory) but are fragmented — no unified memory interface.

7. **Decision classes are scattered** — 17 decision-related classes across different domains, no single decision framework.

8. **The learned_rules reveal** that graph storage as text blob is prohibited (id=17004), graph cleanup is required (id=23), and the graph should not create infinite questions (id=17008).
