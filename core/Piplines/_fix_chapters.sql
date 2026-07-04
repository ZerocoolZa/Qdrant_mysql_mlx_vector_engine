-- Fix books with no chapters/sections: 8, 10, 12, 32
-- Starting: chapter_id=490, section_id=799

-- ============================================================
-- BOOK 8: Plf_ChatPipelineResults — 8-Graph Chat Analysis
-- ============================================================

INSERT INTO chapters (chapter_id, book_id, chapter_number, chapter_title, body_text) VALUES
(490, 8, 1, 'Graph 1: Plan Graph', 'What are we building? 14 capabilities detected in chat: Gmail MCP, Yahoo Mail MCP, email search, MCP config, OAuth, ChatGPT integration, chat download, complaint docs, graph codebase unification, DEGS, BCL instructions, chat mover, vector search, Qdrant.'),
(491, 8, 2, 'Graph 2: Spec Graph', 'What exactly exists? 22 classes/modules referenced: GraphEngine, GraphViewer, DecisionEngine, TmpWorkspace, GraphOrchestrator, Config, AutoGenerator, Inspect, Verify, VerifyRunner, DecisionGUI, 8 view classes, DomGraph, chat_mover, vscode. Run() and Tuple3 mentioned.'),
(492, 8, 3, 'Graph 3: Flow Graph', 'How does it move? 7 flows: clone->install->build->configure->test, OAuth flow, MCP flow, MySQL flow, import flow, pipeline flow, graph flow (plan->spec->flow->lifecycle->dep->error->orch->gap->code).'),
(493, 8, 4, 'Graph 4: Lifecycle Graph', 'When does it run? 7 lifecycle stages: INSTALL, CONFIG, BUILD, VERIFY, RUN, RECOVER, CLEANUP.'),
(494, 8, 5, 'Graph 5: Dependency Graph', 'Why does it connect? 7 dependencies: Windsurf->MCP, Gmail MCP->OAuth, Yahoo MCP->IMAP/SMTP, Python->MySQL, Qdrant->Embeddings, chat_mover->MySQL, Graph Engine->DEGS.'),
(495, 8, 6, 'Graph 6: Error Graph', 'Where does it fail? 8 error modes: OAuth missing, build failed (Node version), permission denied, import error, timeout, file not found, connection failed, authentication failed.'),
(496, 8, 7, 'Graph 7: Orchestration Graph', 'Who calls who? 6 orchestration paths: User->Cascade, Cascade->MySQL, Cascade->MCP, Cascade->Python, Cascade->git, User->Terminal.'),
(497, 8, 8, 'Graph 8: Gap Graph', 'What is missing? 6 PRESENT items (VBStyle, Config, error handling, testing, docs, schema) and 1 MISSING (file headers). 1 gap total.'),
(498, 8, 9, 'Pipeline Summary', 'Chat file analysis results. File: Codex Chat Cleanup.md (633785 chars, 14652 lines). 8/8 graphs run. 80 OK, 0 WARN, 1 GAP. Verdict: chat file has structure but is NOT a spec.');

INSERT INTO sections (section_id, book_id, chapter_id, section_number, section_title, body_text) VALUES
(799, 8, 490, 1, 'Capabilities Detected', '14 capabilities: Gmail MCP, Yahoo Mail MCP, email search, MCP config, OAuth, ChatGPT, chat download, complaint docs, graph unification, DEGS, BCL, chat mover, vector search, Qdrant.'),
(800, 8, 491, 1, 'Classes/Modules Found', '22 classes: GraphEngine, GraphViewer, DecisionEngine, TmpWorkspace, GraphOrchestrator, Config, AutoGenerator, Inspect, Verify, VerifyRunner, DecisionGUI, PlanView, SpecView, FlowView, LifecycleView, DependencyView, ErrorView, OrchestrationView, GapView, DomGraph, chat_mover, vscode.'),
(801, 8, 492, 1, 'Data Flows', '7 flows detected: clone->install->build->configure->test, OAuth setup, MCP config, MySQL connect->query->insert->verify, import read->parse->dedup->insert->verify, pipeline source->classify->parse->embed->verify, graph plan->spec->...->gap->code.'),
(802, 8, 495, 1, 'Dependency Connections', '7 dependencies: Windsurf hosts MCP, Gmail MCP requires OAuth, Yahoo MCP uses IMAP/SMTP, Python connects MySQL, Qdrant stores embeddings, chat_mover writes MySQL, Graph Engine uses DEGS.'),
(803, 8, 496, 1, 'Error Modes', '8 errors: OAuth credentials missing, build failed (Node version), permission denied, import error, timeout, file not found, connection failed, authentication failed.'),
(804, 8, 497, 1, 'Orchestration Paths', '6 paths: User->Cascade (requests), Cascade->MySQL (queries), Cascade->MCP (tools), Cascade->Python (scripts), Cascade->git (clones), User->Terminal (approves).'),
(805, 8, 498, 1, 'Analysis Verdict', '80 OK, 0 WARN, 1 GAP. Chat file has structure but is NOT a spec. 1 gap detected (file headers) — expected for a chat file.');

-- ============================================================
-- BOOK 10: Plf_CleanupList — Temp/Junk Files
-- ============================================================

INSERT INTO chapters (chapter_id, book_id, chapter_number, chapter_title, body_text) VALUES
(499, 10, 1, 'Deleted — Codex Backups (2,086 MB)', '3 codex backup directories deleted after chat history explored, compared (3-way), imported into codex_chat_history MySQL database (10,569 messages). 83 JSONL session files, 16,790 raw messages, 3,181 noise removed, 3,520 duplicates removed.'),
(500, 10, 2, 'Deleted — Python Pycache (232 MB)', '5 Python pycache directories deleted: Library (183 MB), opt (23 MB), private (15 MB), Users (10 MB), tmp (436 KB). Auto-regenerates.'),
(501, 10, 3, 'Still Here — Build Directories (270 MB)', '4 build directories pending deletion: GhostEmbedder/build (270 MB), SEED_FOR_SQL/build (92 KB), nested SEED_FOR_SQL/build (92 KB), GGUF_Context_Fix/build (128 KB).'),
(502, 10, 4, 'Still Here — Python Cache Directories (152 KB)', '3 Python cache directories pending: gui/__pycache__ (128 KB), ModelForge/__pycache__ (4 KB), my_new_repo/.pytest_cache (20 KB).'),
(503, 10, 5, 'Still Here — Temp Directories (308 KB)', '1 temp directory pending: App_Chat_Memory/temp (308 KB).'),
(504, 10, 6, 'Still Here — Qdrant Snapshots Temp', '1 Qdrant snapshots temp directory pending: .local/bin/qdrant/snapshots/tmp (unknown size).'),
(505, 10, 7, 'Summary', 'Total: Codex Backups 2,086 MB DELETED, Python Pycache 232 MB DELETED. Build Dirs 270 MB pending, Python Cache 152 KB pending, Temp 308 KB pending, Qdrant unknown pending.');

INSERT INTO sections (section_id, book_id, chapter_id, section_number, section_title, body_text) VALUES
(806, 10, 499, 1, 'Import Details', '83 JSONL session files, 16,790 raw messages, 3,181 noise removed (IDE context, environment, AGENTS.md), 3,520 duplicates removed (dual-logging + overlapping backups). 10,569 unique messages in codex_chat_history.chat (970 user, 9,599 assistant). Chronological order verified March 5 to April 16, 2026.'),
(807, 10, 499, 2, 'Deleted Paths', '3 paths: .codex.backup.20260416_101328 (458 MB, 1 session), .codex.backup.deepmerge.20260416_101843 (814 MB, 41 sessions, 831 lines), .codex.backup.deepmerge.20260416_101911 (814 MB, 41 sessions, 843 lines — most complete).'),
(808, 10, 501, 1, 'Pending Build Paths', '4 paths: GhostEmbedder/build (270 MB), SEED_FOR_SQL/build (92 KB), nested SEED_FOR_SQL/SEED_FOR_SQL/build (92 KB), GGUF_Context_Fix/build (128 KB). All NOT DELETED.'),
(809, 10, 505, 1, 'Category Summary', 'Codex Backups 2,086 MB DELETED (chats saved to MySQL), Python Pycache 232 MB DELETED (auto-regenerates), Build Dirs 270 MB pending, Python Cache 152 KB pending, Temp 308 KB pending, Qdrant snapshots unknown pending.');

-- ============================================================
-- BOOK 12: Plf_CodeGraph — Visual Diagrams
-- ============================================================

INSERT INTO chapters (chapter_id, book_id, chapter_number, chapter_title, body_text) VALUES
(506, 12, 1, 'Pipeline Flow', '11-stage code graph pipeline: SYNC, INGEST, GRAPH, REASON (3a SURFACE, 3b DEEP, 3c MINE), REGRAPH, VALIDATE, PLAN, REPAIR, CONFIG, EXPORT, VERIFY, ARCHIVE. Files on disk flow through database as source of truth.'),
(507, 12, 2, 'Database Schema', 'code_graph.db SQLite schema: code_files (134 rows, full source), code_units (2,649 rows, per method), code_edges (12,558 rows, CALLS/CONTAINS/IMPORTS/INHERITS/REFERENCES), stamps (future), config_metadata (future).'),
(508, 12, 3, 'Actual Graph: Dom_Graph Ingested Data', '134 files ingested to 2,649 units and 12,558 edges. Units: 1,801 METHOD, 501 MODULE_CONST, 134 IMPORT, 121 CLASS, 63 FUNCTION, 29 MAIN_BLOCK. Edges: 10,757 CALLS, 1,801 CONTAINS. Top file: Dom_Graph_Agent.py (122 methods).'),
(509, 12, 4, 'Dependency Graph (Event-Sourcing Core)', 'Visual dependency tree: InRamDb (14 methods) -> EventLogStore (12), AstNodeRegistry (13), AstVersionStore (10) -> BclStampStore (11), TraceChainStore (8), DependencyEdgeStore (10) -> ReplayEngine (11) <- RollbackEngine (7) -> SnapshotStore (8).'),
(510, 12, 5, 'Query Examples (Stage 2 — GRAPH)', 'SQL query examples: who calls RollbackTo, what does RollbackEngine.RollbackTo call, dead methods (228 of 1,801 have no caller), most connected methods, VBStyle compliance check.');

INSERT INTO sections (section_id, book_id, chapter_id, section_number, section_title, body_text) VALUES
(810, 12, 506, 1, 'Stage 0: SYNC', 'Compare file hashes vs DB hashes. Detects changed files before re-ingestion.'),
(811, 12, 506, 2, 'Stage 1: INGEST', 'Parse files into code_files (full source), code_units (per method), code_edges (CALLS, CONTAINS).'),
(812, 12, 506, 3, 'Stage 2: GRAPH', 'Build structural edges. CALLS: 10,757, CONTAINS: 1,801.'),
(813, 12, 506, 4, 'Stage 3: REASON (3a/3b/3c)', '3a SURFACE: purpose, signature, callers. 3b DEEP: gotchas, cascades, invariants. 3c MINE: scars from past sessions. Output to stamps table.'),
(814, 12, 506, 5, 'Stages 4-11', 'REGRAPH (semantic edges: DEPENDS_ON, BREAKS, RISKS), VALIDATE (VBStyle, dead code, cycles), PLAN (impact analysis, order, risk), REPAIR (modified code_units, versioned), CONFIG (knobs extracted), EXPORT (new .py files), VERIFY (compile+test+diff), ARCHIVE (old files to archive/).'),
(815, 12, 507, 1, 'code_files Table', 'id (PK), file_path (UNIQUE), file_hash, full_source (LONGTEXT). 134 rows.'),
(816, 12, 507, 2, 'code_units Table', 'id (PK), file_path, class_name, method_name, unit_type (FILE/CLASS/METHOD/FUNCTION/MODULE_CONST/IMPORT/MAIN_BLOCK), source_text, docstring, return_type, dispatch_key, calls (csv), called_by (csv), imports, line_start, line_end, content_hash, parent_class, is_vbstyle, ingested_at. 2,649 rows.'),
(817, 12, 507, 3, 'code_edges Table', 'id (PK), from_class, from_method, to_class, to_method, edge_type (CALLS/CONTAINS/IMPORTS/INHERITS/REFERENCES), evidence_line. 12,558 rows.'),
(818, 12, 508, 1, 'Units by Type', 'METHOD 1,801, MODULE_CONST 501, IMPORT 134, CLASS 121, FUNCTION 63, MAIN_BLOCK 29.'),
(819, 12, 508, 2, 'Top 10 Files by Method Count', 'Dom_Graph_Agent.py (122), Dom_Graph_EngineV2.py (39), ir_extractor.py (37), Dom_Graph_Boot.py (36), Dom_Graph_Plan.py (35), graph_builder.py (35), Dom_Graph_Engine.py (33), knowledge_engine.py (32), Dom_Graph_Gui.py (28), refactor_engine.py (25).'),
(820, 12, 509, 1, 'Event-Sourcing Dependency Tree', 'InRamDb -> EventLogStore, AstNodeRegistry, AstVersionStore -> BclStampStore, TraceChainStore, DependencyEdgeStore -> ReplayEngine <- RollbackEngine -> SnapshotStore. Key calls: append() (durability point), rebuild_at() (replay point).'),
(821, 12, 510, 1, 'Dead Methods Query', '228 of 1,801 methods have no recorded caller. Query: SELECT COUNT(*) FROM code_units WHERE unit_type=METHOD AND (called_by IS NULL OR called_by=empty).'),
(822, 12, 510, 2, 'Change Impact Query', 'Most connected methods by call count. Query: SELECT class_name, method_name, LENGTH(calls) as call_count FROM code_units WHERE unit_type=METHOD ORDER BY call_count DESC LIMIT 10.');

-- ============================================================
-- BOOK 32: Plf_PipelineResults — 8-Graph SPEC Analysis (v2)
-- ============================================================

INSERT INTO chapters (chapter_id, book_id, chapter_number, chapter_title, body_text) VALUES
(511, 32, 1, 'Graph 1: Plan Graph', 'What are we building? 12 capabilities: GraphEngine (single Run() dispatch), GraphViewer (shared Tkinter), DecisionEngine (DEGS loop), TmpWorkspace (safe sandbox), BCL Instructions, AutoGenerator (self-writing), GUI, GraphOrchestrator, Config, Inspect, Verify, VerifyRunner. AutoGenerator is most ambitious.'),
(512, 32, 2, 'Graph 2: Spec Graph', 'What exactly exists? 20 classes defined in SPEC: GraphEngine, GraphViewer, DecisionEngine, TmpWorkspace, GraphOrchestrator, Config_graph_engine, AutoGenerator, Inspect, Verify, VerifyRunner, DecisionGUI, 8 view classes, DomGraph. Dispatch table, view classes, orchestrator, config, inspect, verify, AutoGenerator all defined.'),
(513, 32, 3, 'Graph 3: Flow Graph', 'How does it move? 9 flows: GraphEngine.Run dispatch, DEGS loop (ACT->VERIFY->BRANCH->LOG->REPEAT), DecisionEngine step execution, AutoGenerator failure->fallback, TmpWorkspace lifecycle, BCL parsing, end_run/cleanup, VerifyRunner 10 checks, GUI headless fallback.'),
(514, 32, 4, 'Graph 4: Lifecycle Graph', 'When does it run? 7 lifecycle stages: CREATE (ingest, BCL, seed nodes), READ (search/instructions/status), UPDATE (AutoGenerator fallbacks, promote_path), TRANSFORM (plan/spec/gap views), DESTROY (clean, prune_dead, remove_class), VERIFY (VerifyRunner 10 checks), RECOVER (DEGS fallbacks, pipeline loop max_retry=3).'),
(515, 32, 5, 'Graph 5: Dependency Graph', 'Why does it connect? 18 dependencies: GraphOrchestrator coordinates 3 subsystems, GraphEngine requires GraphViewer and uses DomGraph/Inspect/Verify, DecisionEngine reads/writes 4 tables and checks AmIAllowed, TmpWorkspace supports DecisionEngine, AutoGenerator reads/writes 3 tables, DecisionGUI calls engine, VerifyRunner reads classes and metrics.'),
(516, 32, 6, 'Graph 6: Error Graph', 'Where does it fail? 16 error modes all handled in SPEC: SyntaxError, missing Run(), missing Tuple3, hardcoded path, ImportError, VBStyle violation, no outgoing edges, deleted node reference, bad BCL token, GUI Tkinter fail, duplicate fallback, concurrent DB writes, MAX_RETRY exceeded, MAX_STEPS exceeded, AmIAllowed denied, stale run timeout.'),
(517, 32, 7, 'Graph 7: Orchestration Graph', 'Who calls who? GraphOrchestrator is single root entry point. Forwards to GraphEngine (views), DecisionEngine (DEGS), TmpWorkspace (sandbox), DecisionGUI. GraphEngine dispatches to 8 views, DomGraph, Inspect, Verify, search_idx, bcl_instructions. DecisionEngine executes nodes, parses BCL, checks AmIAllowed, calls AutoGenerator, end_run.'),
(518, 32, 8, 'Graph 8: Gap Graph', 'What is missing? 20/20 previous gaps FIXED: Config class, Orchestrator, Dispatch table, BCL parsing, Inspect, Verify, AutoGenerator, MAX_RETRY, error handling, AmIAllowed, end_run/cleanup, merge_runs, promote_path, prune_dead, VerifyRunner, metrics table, GUI recovery, BCL update, class removal, spec_data table. CRUD coverage verified across 6 tables. 0 remaining gaps.'),
(519, 32, 9, 'Pipeline Summary (v2)', '8/8 graphs run. 145 OK, 6 WARN, 0 GAP. Previous gaps: 20/20 fixed, 0/20 still missing. Error modes: 16/16 handled. Verdict: ALL GAPS CLOSED — SPEC.md is ready for code.');

INSERT INTO sections (section_id, book_id, chapter_id, section_number, section_title, body_text) VALUES
(823, 32, 511, 1, 'Capabilities', '12 capabilities: GraphEngine (Run() dispatch), GraphViewer (Tkinter), DecisionEngine (DEGS), TmpWorkspace (sandbox), BCL Instructions, AutoGenerator (self-writing), GUI, GraphOrchestrator (root), Config_graph_engine, Inspect (post-code analysis), Verify (plan vs actual), VerifyRunner (10 checks).'),
(824, 32, 512, 1, 'Classes in SPEC', '20 classes: GraphEngine, GraphViewer, DecisionEngine, TmpWorkspace, GraphOrchestrator, Config_graph_engine, AutoGenerator, Inspect, Verify, VerifyRunner, DecisionGUI, PlanView, SpecView, FlowView, LifecycleView, DependencyView, ErrorView, OrchestrationView, GapView, DomGraph.'),
(825, 32, 513, 1, 'Key Flows', 'GraphEngine.Run -> dispatch -> view opens -> Tuple3. DEGS: ACT->VERIFY->BRANCH->LOG->REPEAT. AutoGenerator: run fails -> read log -> dedup -> generate fallback -> create edge. TmpWorkspace: create->write->compile->read->clean. BCL: read payload -> query instructions -> parse Pass/Fail -> execute -> Tuple3.'),
(826, 32, 515, 1, 'Key Dependencies', 'GraphOrchestrator -> GraphEngine, DecisionEngine, TmpWorkspace (coordinates). GraphEngine -> GraphViewer (requires), DomGraph (uses), Inspect (uses), Verify (uses). DecisionEngine -> bcl_instructions, decision_nodes, execution_log, run_state, run_metrics, AmIAllowed. AutoGenerator -> execution_log, decision_nodes, run_metrics.'),
(827, 32, 516, 1, 'Error Modes (16/16 Handled)', 'SyntaxError, missing Run(), missing Tuple3, hardcoded path, ImportError, VBStyle violation, no outgoing edges, deleted node reference, bad BCL token, GUI Tkinter fail, duplicate fallback, concurrent DB writes, MAX_RETRY exceeded, MAX_STEPS exceeded, AmIAllowed denied, stale run (1 hour timeout). All handled in SPEC.'),
(828, 32, 517, 1, 'Orchestration Root', 'GraphOrchestrator is the single root entry point. User/AI calls GraphOrchestrator.Run(command, params). It forwards to GraphEngine (views), DecisionEngine (DEGS), TmpWorkspace (sandbox), DecisionGUI. GraphEngine dispatches to 8 views + DomGraph + Inspect + Verify + search_idx + bcl_instructions.'),
(829, 32, 518, 1, 'Gap Closure (20/20 Fixed)', 'All 20 previous gaps fixed: Config class, Orchestrator, Dispatch table, BCL parsing, Inspect, Verify, AutoGenerator, MAX_RETRY=3, error handling (6 modes), AmIAllowed, end_run/cleanup, merge_runs, promote_path (threshold=3), prune_dead (every 10 runs, weight<0.1), VerifyRunner (10 checks), run_metrics table, GUI headless fallback, BCL remove_class, class removal mechanism, spec_data table (build step 20).'),
(830, 32, 518, 2, 'CRUD Coverage', 'decision_nodes: full CRUD. decision_edges: full CRUD. execution_log: CREATE/READ (append-only). run_state: full CRUD. bcl_instructions: CREATE/READ/DELETE (update via re-create). classes: full CRUD. run_metrics: CREATE/READ (append-only). Remaining: spec_data table mentioned but not yet created.'),
(831, 32, 519, 1, 'Final Verdict', '145 OK, 6 WARN, 0 GAP. 20/20 gaps fixed. 16/16 error modes handled. ALL GAPS CLOSED. SPEC.md is ready for code.');
