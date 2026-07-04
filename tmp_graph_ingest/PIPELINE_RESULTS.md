
======================================================================
GRAPH 1: PLAN GRAPH
Question: What are we building?
======================================================================

  + Capability: GraphEngine — single Run() dispatch to all graph views
  + Capability: GraphViewer — shared Tkinter rendering
  + Capability: DecisionEngine — DEGS execution loop (ACT -> VERIFY -> BRANCH -> LOG)
  + Capability: TmpWorkspace — safe sandbox for AI runs
  + Capability: BCL Instructions — decision tree for AI agents
  + Capability: AutoGenerator — self-writing graph from failures
  + Capability: GUI — visualize and manage graph codegraph
  + Capability: GraphOrchestrator — root coordinator for all subsystems
  + Capability: Config_graph_engine — VBStyle config for all paths/constants
  + Capability: Inspect — post-code analysis bridge to efl_brain
  + Capability: Verify — plan vs actual comparison
  + Capability: VerifyRunner — automated 10-check verification
  + Plan check: 12 capabilities defined, all map to Run() commands
  ! Plan risk: AutoGenerator (self-writing) is most ambitious — has dedup + triggers defined

======================================================================
GRAPH 2: SPEC GRAPH
Question: What exactly exists?
======================================================================

  + Class: GraphEngine
  + Class: GraphViewer
  + Class: DecisionEngine
  + Class: TmpWorkspace
  + Class: GraphOrchestrator
  + Class: Config_graph_engine
  + Class: AutoGenerator
  + Class: Inspect
  + Class: Verify
  + Class: VerifyRunner
  + Class: DecisionGUI
  + Class: PlanView
  + Class: SpecView
  + Class: FlowView
  + Class: LifecycleView
  + Class: DependencyView
  + Class: ErrorView
  + Class: OrchestrationView
  + Class: GapView
  + Class: DomGraph
  Class count: 20 classes defined in SPEC
  + Dispatch table: Dispatch dictionary defined in SPEC (section 4.1)
  + View classes: All 8 view classes present in SPEC
  + Orchestrator: GraphOrchestrator class defined — coordinates all subsystems
  + Config: Config_graph_engine class defined — VBStyle config
  + Inspect: Inspect class defined with parse/build_graph/compare commands
  + Verify: Verify class defined with check/missing/extra/report commands
  + AutoGenerator: AutoGenerator class defined with auto_generate/dedup/merge/promote/prune/metrics

======================================================================
GRAPH 3: FLOW GRAPH
Question: How does it move?
======================================================================

  + Flow: GraphEngine.Run(command, params) -> dispatch table -> view opens -> returns Tuple3
  + Flow: DEGS loop: ACT -> VERIFY -> BRANCH -> LOG -> REPEAT
  + Flow: DecisionEngine: start -> step -> execute_node -> get_edges -> branch -> log -> update run_state
  + Flow: AutoGenerator: run fails -> read execution_log -> dedup check -> generate fallback -> create edge
  + Flow: TmpWorkspace: create -> write -> compile -> read -> clean
  + Flow: BCL parsing: read payload -> query bcl_instructions -> parse [@Pass]/[@Fail] -> execute -> return Tuple3
  + Flow: End run: set state=completed -> write run_metrics -> keep execution_log -> return Tuple3
  + Flow: VerifyRunner: Run('all') -> 10 checks -> JSON report with pass/fail counts
  + Flow check: BCL payload parsing flow defined (section 4.2)
  + Flow check: end_run/cleanup flow defined
  + Flow check: GUI headless fallback defined

======================================================================
GRAPH 4: LIFECYCLE GRAPH
Question: When does it run?
======================================================================

  + CREATE: Ingest graph code, create BCL instructions, seed decision_nodes
  + READ: GraphEngine.Run('search'/'instructions'/'status') — read from DB
  + UPDATE: AutoGenerator creates fallback nodes, promote_path adjusts weights
  + TRANSFORM: GraphEngine.Run('plan'/'spec'/'gap') transforms data into views
  + DESTROY: TmpWorkspace.Run('clean'), prune_dead, remove_class
  + VERIFY: VerifyRunner.Run('all') 10 checks, Verify.Run('check') plan vs actual
  + RECOVER: DEGS fallback nodes, pipeline loop back to Plan (max_retry=3)
  + Lifecycle check: MAX_RETRY defined — pipeline loop limited
  + Lifecycle check: end_run writes run_metrics before cleanup
  + Lifecycle check: Auto-cleanup for stale runs (1 hour timeout)

======================================================================
GRAPH 5: DEPENDENCY GRAPH
Question: Why does it connect?
======================================================================

  + GraphOrchestrator -> GraphEngine: COORDINATES — root entry point forwards engine commands
  + GraphOrchestrator -> DecisionEngine: COORDINATES — root entry point starts DEGS loop
  + GraphOrchestrator -> TmpWorkspace: COORDINATES — root entry point manages sandbox
  + GraphEngine -> GraphViewer: REQUIRES — needs shared rendering for all views
  + GraphEngine -> DomGraph: USES — BFS/DFS/cycle/path algorithms
  + GraphEngine -> Inspect: USES — AST parse real files (bridge to efl_brain)
  + GraphEngine -> Verify: USES — compare plan vs actual
  + DecisionEngine -> bcl_instructions: READS — BCL payload parsing flow (section 4.2)
  + DecisionEngine -> decision_nodes: READS/WRITES — loads nodes, logs execution
  + DecisionEngine -> execution_log: WRITES — logs every step
  + DecisionEngine -> run_state: READS/WRITES — tracks current node
  + DecisionEngine -> run_metrics: WRITES — end_run writes metrics
  + DecisionEngine -> AmIAllowed: CHECKS — pre-write permission enforcement
  + TmpWorkspace -> DecisionEngine: SUPPORTS — provides safe folder for each run
  + AutoGenerator -> execution_log: READS — finds failures to learn from
  + AutoGenerator -> decision_nodes: WRITES — creates fallback nodes (with dedup)
  + AutoGenerator -> run_metrics: READS — counts successes for promote_path
  + DecisionGUI -> DecisionEngine: CALLS — start, step, auto, end buttons
  + DecisionGUI -> decision_nodes: READS — displays graph
  + VerifyRunner -> classes: READS — checks Run(), Tuple3, print(), decorators
  + VerifyRunner -> run_metrics: READS — check 10 success rate
  + Dependency check: GraphViewer has headless fallback — can run without Tkinter
  + Dependency check: DecisionEngine -> bcl_instructions dependency wired (section 4.2)
  + Dependency check: Inspect bridges to efl_brain (parse/build_graph/compare)

======================================================================
GRAPH 6: ERROR GRAPH
Question: Where does it fail?
======================================================================

  + SyntaxError in ingested code: Handled in SPEC
  + Missing Run() method: Handled in SPEC
  + Missing Tuple3 return: Handled in SPEC
  + Hardcoded path found: Handled in SPEC
  + ImportError: Handled in SPEC
  + VBStyle violation: Handled in SPEC
  + Decision node has no outgoing edges: Handled in SPEC
  + Run state points to deleted node: Handled in SPEC
  + BCL payload references non-existent token: Handled in SPEC
  + GUI Tkinter fails to initialize: Handled in SPEC
  + auto_generate creates duplicate fallback: Handled in SPEC
  + Concurrent runs writing to same DB: Handled in SPEC
  + Pipeline loop exceeds MAX_RETRY: Handled in SPEC
  + DEGS auto-run exceeds MAX_STEPS: Handled in SPEC
  + Permission denied by AmIAllowed: Handled in SPEC
  + Run not ended after 1 hour: Handled in SPEC

======================================================================
GRAPH 7: ORCHESTRATION GRAPH
Question: Who calls who?
======================================================================

  + User/AI -> GraphOrchestrator.Run(command, params): Root — single entry point
  + GraphOrchestrator -> GraphEngine.Run(command, params): Forwards engine commands
  + GraphOrchestrator -> DecisionEngine.Run(start/step/auto/end): Coordinates DEGS
  + GraphOrchestrator -> TmpWorkspace.Run(create/write/compile): Manages sandbox
  + GraphOrchestrator -> DecisionGUI: Launches GUI
  + GraphEngine -> PlanView / SpecView / ... / GapView: Dispatches to view via DISPATCH table
  + GraphEngine -> DomGraph.Run(bfs/dfs/cycle/path): Dispatches to graph algorithms
  + GraphEngine -> Inspect.Run(parse/build_graph/compare): Dispatches to post-code analysis
  + GraphEngine -> Verify.Run(check/missing/extra/report): Dispatches to verification
  + GraphEngine -> search_idx (FTS5): Dispatches search to DB query
  + GraphEngine -> bcl_instructions table: Dispatches instructions to DB query
  + DecisionEngine -> execute_node(node): Steps through decision graph
  + DecisionEngine -> bcl_instructions (BCL parsing): Reads BCL payload per section 4.2
  + DecisionEngine -> AmIAllowed check: Pre-write permission enforcement
  + DecisionEngine -> AutoGenerator.Run(auto_generate): Self-writes new nodes from failures
  + DecisionEngine -> end_run(run_id): Cleans up run_state, writes run_metrics
  + AutoGenerator -> execution_log + decision_nodes + decision_edges: Reads failures, writes fallbacks
  + VerifyRunner -> classes + methods + run_metrics: Runs 10 automated checks
  + DecisionGUI -> DecisionEngine (start/step/auto/end): GUI calls engine
  + Orchestration root: GraphOrchestrator is the single root entry point
  + Orchestration check: DecisionEngine has end command for cleanup

======================================================================
GRAPH 8: GAP GRAPH
Question: What's missing?
======================================================================

  + FIXED: Config class: Config_graph_engine defined with DB_PATH, TMP_DIR, MAX_RETRY, MAX_STEPS, etc.
  + FIXED: Orchestrator class: GraphOrchestrator coordinates all subsystems
  + FIXED: Dispatch table implementation: Dispatch dictionary defined in section 4.1
  + FIXED: BCL payload parsing flow: Section 4.2 defines full BCL parsing flow
  + FIXED: Inspect class: Inspect defined with parse/build_graph/compare
  + FIXED: Verify class: Verify defined with check/missing/extra/report
  + FIXED: AutoGenerator class: AutoGenerator defined with auto_generate/dedup/merge/promote/prune/metrics
  + FIXED: Max retry (infinite loop): MAX_RETRY=3, loop_count check, pause on exceed
  + FIXED: Error handling completeness: All 6 previously missing error modes now handled
  + FIXED: AmIAllowed enforcement: Pre-write check, returns Tuple3(0, None, permission_denied)
  + FIXED: end_run/cleanup: end_run command + auto-cleanup after 1 hour
  + FIXED: merge_runs trigger: On explicit call, compares failure patterns
  + FIXED: promote_path trigger: After PROMOTE_THRESHOLD=3 successes, weight +0.5
  + FIXED: prune_dead trigger: Every 10 runs, weight < 0.1, not traversed in last 10
  + FIXED: Automated verification runner: VerifyRunner.Run(all) with 10 checks
  + FIXED: Metrics table: run_metrics table defined with success/failure tracking
  + FIXED: GUI init error recovery: Headless mode returns Tuple3(0, None, tkinter_unavailable)
  + FIXED: BCL instruction update: remove_class command allows removing bad code
  + FIXED: Class removal mechanism: GraphEngine.Run(remove_class, {class_id})
  + FIXED: spec_data table: Mentioned in architecture, build step 20 creates it
  ! CRUD: decision_nodes: CREATE/READ/UPDATE/DELETE all present
  ! CRUD: decision_edges: CREATE/READ/UPDATE/DELETE all present
  + CRUD: execution_log: CREATE/READ present (append-only by design)
  + CRUD: run_state: CREATE/READ/UPDATE/DELETE (end_run) all present
  ! CRUD: bcl_instructions: CREATE/READ/DELETE present (update via re-create)
  ! CRUD: classes: CREATE/READ/UPDATE/DELETE all present
  + CRUD: run_metrics: CREATE/READ present (append-only by design)
  ! Remaining: spec_data table: Mentioned but not yet created — build step 20

======================================================================
PIPELINE SUMMARY (v2 — dynamic detection)
======================================================================

Graphs run: 8/8

Severity breakdown:
  + OK:    145
  ! WARN:  6
  X GAP:   0

Previous gaps status:
  Fixed:          20/20
  Still missing:  0/20

Error modes handled: 16/16

VERDICT: ALL GAPS CLOSED — SPEC.md is ready for code.

Time: 0.0s
