-- Batch 11: Books 36 (Utilities), 38 (WordIndexSearch), 39 (Workflow8Graph)
-- Starting IDs: nodes=441, links=352, glossary=136, checks=141, provenance=34, connections=84

-- ============================================================
-- BOOK 36: Utilities Pipeline — Index, Audit, Verify, Orchestrate
-- ============================================================

UPDATE books SET core_thesis = 'Event-driven utility orchestration system. Config defines TRIGGERS and SCHEDULES. Scheduler fires triggers (timer or event). Orchestrator dispatches to 20 utilities in order with on_fail policies. 5 triggers: startup, code_change, error, scheduled, db_change. Utilities: SystemCheck, DomIndexer, VbsScanner, VbsTest, Cleaner, Compress, DomAudit, DiffCheck, StatsReport, ContentExtract, PreFlight, ErrorHandler, ErrorTracker, MSearch, Backup, Credentials.', status = 'active', sqlite_backend = 'sqlite+mysql' WHERE book_id = 36;

-- Nodes for book 36 (chapters 435-458)
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(441, 'concept', 'Utilities Pipeline', 'Event-driven utility orchestration. Config defines triggers and schedules. Scheduler fires triggers. Orchestrator dispatches to 20 utilities in order with on_fail policies. Replaces manual utility execution with automated, config-driven pipeline.', 'pipeline', 0.95, 36, 436),
(442, 'component', 'Config — The Brain', 'core/utility/Config.py. Defines TRIGGERS (startup, code_change, error, scheduled, db_change), SCHEDULES (intervals), TARGETS (paths), ON_FAIL_ACTIONS. Per-utility config constants. ConfigReport class for pass/fail summaries.', 'config', 0.90, 36, 437),
(443, 'component', 'Scheduler', 'core/utility/scheduler.py. Timer-based (interval > 0, background thread) or event-based (interval = 0, fire_event()). Reads Config.SCHEDULES, fires triggers to Orchestrator.', 'orchestration', 0.80, 36, 438),
(444, 'component', 'Orchestrator', 'core/utility/orchestrator.py. Instantiates all utilities on init. Reads Config.TRIGGERS, executes utilities in order sequence. Handles failures per on_fail policy (report, continue, escalate, cancel). Returns aggregated Tuple3.', 'orchestration', 0.85, 36, 439),
(445, 'component', 'DomIndexer', 'core/Dom_Unified/DomIndexer.py. In-RAM SQLite code index with AI reasoning. 7 tables: files, classes, methods, functions, bcl_stamps, edges, reasoning. vbast C binary or Python ast fallback. Incremental indexing. Graph queries. Export/import.', 'indexing', 0.85, 36, 440),
(446, 'component', 'VbsScanner', 'core/utility/vbs_scanner.py. VBStyle violation detector using AST. Checks: print(), decorators, self._, missing headers, missing Run(), non-Tuple3 returns, class naming, tabs, trailing whitespace.', 'compliance', 0.75, 36, 441),
(447, 'component', 'VbsTest', 'core/utility/vbs_test.py. Combined compliance checker and test engine. VBStyle checks, assertions (eq/ne/gt/gte/lt/lte/in/not_in/is_none/is_not_none/is_true/is_false), unit tests, integration tests, benchmarks, mocks, fixtures, coverage, compile, report.', 'testing', 0.75, 36, 442),
(448, 'component', 'SystemCheck', 'core/utility/system_check.py. Integrity verification. Index scan, compress roundtrip, py_compile, importability, domain integrity. Runs first at startup.', 'verification', 0.70, 36, 443),
(449, 'component', 'DomAudit', 'core/utility/dom_audit.py. Baseline, drift detection, compliance rules, diff, flag/violation/fix/escalate, trace, report. SHA-256 baselines.', 'audit', 0.70, 36, 444),
(450, 'component', 'DiffCheck', 'core/utility/diff_check.py. Before/after index comparison. Files, classes, methods, domains added/removed.', 'analysis', 0.60, 36, 445),
(451, 'component', 'StatsReport', 'core/utility/stats_report.py. Markdown report from file index. Domain summary, class inventory, cross-domain imports, method index.', 'reporting', 0.60, 36, 446),
(452, 'component', 'ContentExtract', 'core/utility/content_extract.py. Regex-based source analysis. Classes, methods, functions, imports, BCL headers, violations, SQL calls, file I/O, error handling, Tuple3, config mentions.', 'analysis', 0.55, 36, 447),
(453, 'component', 'PreFlight', 'core/utility/preflight.py. Database integrity checks. Constraint violations, orphan rows, type overflow, FK resolution.', 'verification', 0.65, 36, 448),
(454, 'component', 'ErrorHandler', 'core/utility/error_handler.py. Most complex utility (561 lines, 20+ methods). Capture, classify, recover. Circuit breaker, bulkhead, timeout, retry with backoff, fallback. SQLite schema: error_definitions, error_log, recovery_policies.', 'error', 0.85, 36, 449),
(455, 'component', 'ErrorTracker', 'core/utility/error_tracker.py. MySQL lessons lookup. Queries vb_shared.learned_rules (10,540), know_problems (218), know_solutions (336). Local SQLite error_log.db. Graceful degradation if MySQL unavailable.', 'error', 0.80, 36, 450),
(456, 'component', 'MSearch', 'core/utility/msearch.py. MySQL + Qdrant search wrapper. Keyword, semantic, hybrid modes. Auto-query on startup, error, change events.', 'search', 0.65, 36, 451),
(457, 'component', 'Cleaner', 'core/utility/cleaner.py. Artifact removal. Removes __pycache__, .pyc, .pyo, .tmp, .DS_Store. Skips .git, .venv, node_modules.', 'maintenance', 0.50, 36, 452),
(458, 'component', 'Compress', 'core/utility/compress.py. zlib + base64 compression. encode, decode, roundtrip. Used by SystemCheck for integrity verification.', 'utility', 0.45, 36, 453),
(459, 'component', 'Backup', 'core/utility/backup.py. Full redundancy: ZIP, S3, Email, Git. Configurable via Config.BACKUP_STEPS. Uses Credentials for secrets.', 'backup', 0.60, 36, 454),
(460, 'component', 'Credentials', 'core/utility/credentials.py. Secret management. Three sources: env vars (highest), .credentials file (base64 JSON), fallback defaults. Gmail, Yahoo, S3, Git, MySQL, API keys.', 'security', 0.65, 36, 455),
(461, 'concept', '5 Pipeline Triggers', 'startup (SystemCheck, DomIndexer, VbsScanner, Cleaner), code_change (VbsTest, ContentExtract), error (ErrorHandler, ErrorTracker, recovery), scheduled (StatsReport, DomAudit, ErrorHandler stats, Backup), db_change (PreFlight).', 'orchestration', 0.85, 36, 456),
(462, 'concept', 'on_fail Policies', 'report (log but continue), continue (ignore failure), escalate (raise severity), cancel (stop pipeline). Each utility in a trigger has its own on_fail policy.', 'orchestration', 0.75, 36, 456);

-- Links for book 36
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(352, 441, 442, 'configured_by', 1.0, 'Config defines all triggers and schedules'),
(353, 441, 443, 'triggered_by', 1.0, 'Scheduler fires triggers'),
(354, 441, 444, 'dispatched_by', 1.0, 'Orchestrator dispatches to utilities'),
(355, 443, 444, 'fires', 1.0, 'Scheduler fires triggers to Orchestrator'),
(356, 444, 445, 'dispatches_to', 0.8, 'Orchestrator dispatches to DomIndexer at startup'),
(357, 444, 446, 'dispatches_to', 0.7, 'Orchestrator dispatches to VbsScanner at startup'),
(358, 444, 448, 'dispatches_to', 0.8, 'SystemCheck runs first at startup'),
(359, 444, 454, 'dispatches_to', 0.8, 'ErrorHandler runs on error trigger'),
(360, 444, 455, 'dispatches_to', 0.8, 'ErrorTracker runs on error trigger'),
(361, 454, 455, 'complements', 0.7, 'ErrorHandler captures, ErrorTracker looks up lessons'),
(362, 459, 460, 'depends_on', 0.8, 'Backup uses Credentials for secrets'),
(363, 448, 445, 'uses_internally', 0.7, 'SystemCheck uses DomIndexer for index scan'),
(364, 448, 458, 'uses_internally', 0.6, 'SystemCheck uses Compress for roundtrip test'),
(365, 441, 461, 'defined_by', 1.0, '5 triggers define the pipeline behavior'),
(366, 441, 462, 'governed_by', 0.8, 'on_fail policies govern failure handling');

-- Glossary terms for book 36
INSERT INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(136, 'Utility Trigger', 'Config-defined event that fires a sequence of utilities. 5 triggers: startup, code_change, error, scheduled, db_change.', 'orchestration', 'nodes.node_name = "5 Pipeline Triggers"'),
(137, 'on_fail Policy', 'Failure handling strategy per utility in a trigger sequence: report (log), continue (ignore), escalate (raise), cancel (stop).', 'orchestration', 'nodes.node_name = "on_fail Policies"'),
(138, 'In-RAM SQLite Index', 'DomIndexer uses :memory: SQLite with 7 tables for microsecond code queries. Files, classes, methods, functions, bcl_stamps, edges, reasoning.', 'indexing', 'nodes.node_name = "DomIndexer"'),
(139, 'Circuit Breaker', 'Resilience pattern in ErrorHandler: open/closed/half-open state machine with failure threshold. Prevents cascading failures.', 'error', 'nodes.node_value LIKE "%circuit_breaker%"');

-- Glossary links for book 36
INSERT INTO glossary_links (term_id, book_id, chapter_id, link_type) VALUES
(136, 36, 456, 'defines'),
(137, 36, 456, 'defines'),
(138, 36, 440, 'defines'),
(139, 36, 449, 'defines');

-- Checks for book 36
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(141, 36, 437, 'Config defines 5 triggers', 'specification', 'PASS', 'startup, code_change, error, scheduled, db_change'),
(142, 36, 440, 'DomIndexer: 7 in-RAM tables', 'schema', 'PASS', 'files, classes, methods, functions, bcl_stamps, edges, reasoning'),
(143, 36, 441, 'VbsScanner: 9 violation checks', 'compliance', 'PASS', 'print, decorators, self._, headers, Run(), Tuple3, naming, tabs, trailing whitespace'),
(144, 36, 449, 'ErrorHandler: 561 lines, 20+ methods', 'complexity', 'PASS', 'Most complex utility with capture, classify, recover, retry, circuit breaker, bulkhead, timeout'),
(145, 36, 450, 'ErrorTracker: 3 MySQL knowledge stores', 'database', 'PASS', 'learned_rules (10,540), know_problems (218), know_solutions (336)'),
(146, 36, 458, 'How to Extend: add utility', 'documentation', 'PASS', '6-step process: create file, VBStyle headers, add to Config.TRIGGERS, import, export, test');

-- Provenance for book 36
INSERT INTO provenance (provenance_id, source_path, dest_path, dest_type, source_hash, book_id, notes) VALUES
(34, 'core/utility/Config.py', 'core/Piplines/Plf_UtilitiesPipeline.md', 'markdown', NULL, 36, 'Config.py defines all triggers, schedules, and per-utility constants documented in this book'),
(35, 'core/utility/orchestrator.py', 'core/Piplines/Plf_UtilitiesPipeline.md', 'markdown', NULL, 36, 'Orchestrator dispatch logic documented in chapter 4');

-- Pipeline connections for book 36
INSERT INTO pipeline_connections (connection_id, from_book_id, to_book_id, connection_type, description, status) VALUES
(84, 36, 5, 'related_to', 'Utilities ErrorHandler and ErrorTracker connect to Error Capture pipeline', 'active'),
(85, 36, 33, 'related_to', 'DomIndexer used by Provenance pipeline for file indexing', 'active'),
(86, 36, 34, 'related_to', 'Utilities Orchestrator pattern relates to MemUnit composition root', 'active'),
(87, 36, 10, 'executes', 'Cleaner utility in Utilities pipeline handles cleanup list items', 'active');

-- ============================================================
-- BOOK 38: Word Index Search Pipeline — Index, Search, Context
-- ============================================================

UPDATE books SET core_thesis = 'Simple and fast word-based search. Indexes files into SQLite, retrieves words with plus or minus N words of context. Contrasts with semantic search (probabilistic) and magnetic search (deterministic radius). Stages: INDEX, SEARCH, CONTEXT, DISPLAY. CLI and Python API.', status = 'active', sqlite_backend = 'sqlite' WHERE book_id = 38;

-- Nodes for book 38 (chapters 469-479)
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(463, 'concept', 'Word Index Search Pipeline', 'Simple and fast word-based search. Indexes files into SQLite, retrieves words with plus or minus N words of context. Not semantic, not magnetic — exact word matching with context window.', 'search', 0.85, 38, 469),
(464, 'stage', 'INDEX', 'Index files into SQLite. Parse files into words, store with file path, line number, word position. Creates word_index table.', 'pipeline', 0.75, 38, 471),
(465, 'stage', 'SEARCH', 'Search for exact word in the index. Returns all occurrences with file path, line number, word position.', 'pipeline', 0.75, 38, 471),
(466, 'stage', 'CONTEXT', 'Retrieve plus or minus N words of context around each search hit. Configurable radius. Returns word sequence around the match.', 'pipeline', 0.80, 38, 471),
(467, 'stage', 'DISPLAY', 'Format and display search results with context. CLI output or Python API return.', 'pipeline', 0.60, 38, 471),
(468, 'concept', 'Radius = Word Chunking', 'Context radius is measured in words, not characters or lines. plus or minus N words around the search term. Natural word boundary expansion.', 'search', 0.70, 38, 473),
(469, 'schema', 'word_index SQLite Schema', 'SQLite table storing indexed words with file_path, line_number, word_position, word_text. Enables fast exact word lookup with position tracking.', 'database', 0.70, 38, 475),
(470, 'concept', 'When to Use Word Index Search', 'Use when: exact word matching needed, fast indexing required, context around matches needed, no semantic understanding required. Good for code search, log analysis, documentation search.', 'guidance', 0.65, 38, 476),
(471, 'concept', 'When NOT to Use', 'Do NOT use when: semantic similarity needed (use embeddings), context reconstruction needed (use magnetic search), multi-hop traversal needed (use graph search). Word index is exact match only.', 'guidance', 0.65, 38, 477);

-- Links for book 38
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(367, 463, 464, 'stage_1', 1.0, 'INDEX is first stage'),
(368, 463, 465, 'stage_2', 1.0, 'SEARCH is second stage'),
(369, 463, 466, 'stage_3', 1.0, 'CONTEXT is third stage'),
(370, 463, 467, 'stage_4', 0.8, 'DISPLAY is fourth stage'),
(371, 466, 468, 'configured_by', 1.0, 'Context stage uses word chunking radius'),
(372, 464, 469, 'stores_in', 1.0, 'INDEX stores in word_index SQLite table'),
(373, 470, 471, 'complemented_by', 0.7, 'When NOT to use complements When to Use guidance');

-- Glossary terms for book 38
INSERT INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(140, 'Word Index Search', 'Exact word-based search with configurable context radius. Indexes files into SQLite, returns matches with plus or minus N words of context.', 'search', 'nodes.node_name = "Word Index Search Pipeline"'),
(141, 'Context Radius', 'Number of words before and after a search match to include in results. Measured in words, not characters or lines.', 'search', 'nodes.node_name = "Radius = Word Chunking"');

-- Glossary links for book 38
INSERT INTO glossary_links (term_id, book_id, chapter_id, link_type) VALUES
(140, 38, 469, 'defines'),
(141, 38, 473, 'defines');

-- Checks for book 38
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(147, 38, 471, '4 stages defined', 'specification', 'PASS', 'INDEX, SEARCH, CONTEXT, DISPLAY'),
(148, 38, 475, 'SQLite schema for word_index', 'schema', 'PASS', 'Table with file_path, line_number, word_position, word_text'),
(149, 38, 476, 'When to Use guidance', 'documentation', 'PASS', 'Exact word matching, fast indexing, context needed, no semantics required'),
(150, 38, 477, 'When NOT to Use guidance', 'documentation', 'PASS', 'Use embeddings for semantics, magnetic search for context reconstruction, graph for multi-hop');

-- Pipeline connections for book 38
INSERT INTO pipeline_connections (connection_id, from_book_id, to_book_id, connection_type, description, status) VALUES
(88, 38, 36, 'related_to', 'Word Index Search is a simpler alternative to DomIndexer for exact word matching', 'active'),
(89, 38, 33, 'related_to', 'Word Index Search can index files before Provenance pipeline copies them', 'active');

-- ============================================================
-- BOOK 39: 8-Graph Workflow Pipeline — Reason Before You Code
-- ============================================================

UPDATE books SET core_thesis = 'Reasoning process using 8 graph views before writing code. 8 graphs: Plan, Spec, Flow, Lifecycle, Dependencies, Error, Orchestration, Gap. Prevents costly rework by exposing gaps before implementation. 15-20 minutes of reasoning. Companion: Cognitive Loop reasoning engine. Workflow Domain: project management layer.', status = 'active', sqlite_backend = 'sqlite' WHERE book_id = 39;

-- Nodes for book 39 (chapters 480-489)
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(472, 'concept', '8-Graph Workflow Pipeline', 'Reasoning process using 8 graph views before writing code. Prevents costly rework by exposing gaps before implementation. 15-20 minutes of reasoning saves hours of debugging.', 'workflow', 0.95, 39, 480),
(473, 'graph', 'Plan Graph', 'What are we building? High-level plan, goals, scope, deliverables. First graph in the sequence.', 'planning', 0.85, 39, 481),
(474, 'graph', 'Spec Graph', 'What are the requirements? Detailed specification of inputs, outputs, constraints, interfaces.', 'specification', 0.85, 39, 481),
(475, 'graph', 'Flow Graph', 'How does data flow? Data movement, transformations, pipelines, data lifecycle.', 'flow', 0.80, 39, 481),
(476, 'graph', 'Lifecycle Graph', 'What states does each component go through? State machines, transitions, lifecycle stages.', 'lifecycle', 0.75, 39, 481),
(477, 'graph', 'Dependencies Graph', 'What depends on what? Component dependencies, build order, deployment order, coupling analysis.', 'dependency', 0.80, 39, 481),
(478, 'graph', 'Error Graph', 'What can go wrong? Failure modes, error paths, recovery strategies, resilience patterns.', 'error', 0.80, 39, 481),
(479, 'graph', 'Orchestration Graph', 'Who calls whom? Component orchestration, dispatch patterns, control flow, routing.', 'orchestration', 0.75, 39, 481),
(480, 'graph', 'Gap Graph', 'What is missing? Gaps between plan and spec, missing error handling, missing dependencies, missing lifecycle states. The most valuable graph.', 'gap', 0.90, 39, 481),
(481, 'concept', 'Key Principles', 'Reason before code. 8 perspectives catch what 1 perspective misses. Gaps are cheaper to fix on paper than in code. 15-20 minutes of reasoning saves hours of debugging. Each graph exposes different blind spots.', 'philosophy', 0.85, 39, 482),
(482, 'concept', 'Mental Models', 'Plan = architect blueprint. Spec = contract. Flow = plumbing. Lifecycle = birth to death. Dependencies = supply chain. Error = safety net. Orchestration = conductor. Gap = inspector. Each model makes the graph intuitive.', 'philosophy', 0.70, 39, 483),
(483, 'concept', 'Cognitive Loop', 'Companion reasoning engine to the 8-Graph Workflow. Iterates: observe, orient, decide, act. Provides the reasoning substrate that the 8 graphs populate.', 'reasoning', 0.75, 39, 487),
(484, 'concept', 'Workflow Domain', 'Project management layer. Wraps 8-Graph Workflow with task tracking, progress monitoring, and multi-session continuity. The workflow domain manages the reasoning process across sessions.', 'management', 0.70, 39, 488),
(485, 'concept', '15-20 Minutes Total', 'Total reasoning time for all 8 graphs: 15-20 minutes. Plan (2-3 min), Spec (3-4 min), Flow (2-3 min), Lifecycle (1-2 min), Dependencies (2-3 min), Error (2-3 min), Orchestration (1-2 min), Gap (2-3 min).', 'metric', 0.65, 39, 489);

-- Links for book 39
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(374, 472, 473, 'graph_1', 1.0, 'Plan Graph is first'),
(375, 472, 474, 'graph_2', 1.0, 'Spec Graph is second'),
(376, 472, 475, 'graph_3', 1.0, 'Flow Graph is third'),
(377, 472, 476, 'graph_4', 1.0, 'Lifecycle Graph is fourth'),
(378, 472, 477, 'graph_5', 1.0, 'Dependencies Graph is fifth'),
(379, 472, 478, 'graph_6', 1.0, 'Error Graph is sixth'),
(380, 472, 479, 'graph_7', 1.0, 'Orchestration Graph is seventh'),
(381, 472, 480, 'graph_8', 1.0, 'Gap Graph is eighth — most valuable'),
(382, 472, 481, 'governed_by', 0.9, 'Key principles govern the workflow'),
(383, 472, 482, 'explained_by', 0.7, 'Mental models make graphs intuitive'),
(384, 472, 483, 'companion_to', 0.8, 'Cognitive Loop is companion reasoning engine'),
(385, 472, 484, 'wrapped_by', 0.7, 'Workflow Domain wraps the 8-Graph process'),
(386, 472, 485, 'measured_by', 0.6, '15-20 minutes total reasoning time'),
(387, 480, 473, 'diffs_against', 0.8, 'Gap Graph diffs Plan against Spec to find missing items');

-- Glossary terms for book 39
INSERT INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(142, '8-Graph Workflow', 'Reasoning process using 8 graph views (Plan, Spec, Flow, Lifecycle, Dependencies, Error, Orchestration, Gap) before writing code. Prevents costly rework.', 'workflow', 'nodes.node_name = "8-Graph Workflow Pipeline"'),
(143, 'Gap Graph', 'Eighth and most valuable graph. Diffs plan against spec to find missing items: missing error handling, missing dependencies, missing lifecycle states.', 'workflow', 'nodes.node_name = "Gap Graph"'),
(144, 'Cognitive Loop', 'Companion reasoning engine to 8-Graph Workflow. Iterates: observe, orient, decide, act. Provides reasoning substrate that 8 graphs populate.', 'reasoning', 'nodes.node_name = "Cognitive Loop"');

-- Glossary links for book 39
INSERT INTO glossary_links (term_id, book_id, chapter_id, link_type) VALUES
(142, 39, 480, 'defines'),
(143, 39, 481, 'defines'),
(144, 39, 487, 'defines');

-- Checks for book 39
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(151, 39, 481, '8 graphs defined in order', 'specification', 'PASS', 'Plan, Spec, Flow, Lifecycle, Dependencies, Error, Orchestration, Gap'),
(152, 39, 482, 'Key principles documented', 'documentation', 'PASS', 'Reason before code, 8 perspectives catch what 1 misses, gaps cheaper on paper'),
(153, 39, 489, 'Total time: 15-20 minutes', 'metric', 'PASS', 'Plan 2-3, Spec 3-4, Flow 2-3, Lifecycle 1-2, Dep 2-3, Error 2-3, Orch 1-2, Gap 2-3 min'),
(154, 39, 487, 'Cognitive Loop companion documented', 'documentation', 'PASS', 'Observe, orient, decide, act iteration pattern');

-- Provenance for book 39
INSERT INTO provenance (provenance_id, source_path, dest_path, dest_type, source_hash, book_id, notes) VALUES
(36, 'dom_compression/add_workflow_cognitive_loop.py', 'core/Piplines/Plf_Workflow8GraphPipeline.md', 'markdown', NULL, 39, 'Cognitive loop implementation referenced in book'),
(37, 'dom_compression/Dom_workflow.py', 'core/Piplines/Plf_Workflow8GraphPipeline.md', 'markdown', NULL, 39, 'Workflow domain implementation referenced in book');

-- Pipeline connections for book 39
INSERT INTO pipeline_connections (connection_id, from_book_id, to_book_id, connection_type, description, status) VALUES
(90, 39, 8, 'produced', '8-Graph Workflow produced the Chat Pipeline Results analysis in book 8', 'active'),
(91, 39, 34, 'can_analyze', '8-Graph Workflow can reason about MemUnit 3-layer architecture', 'active'),
(92, 39, 36, 'can_analyze', '8-Graph Workflow can reason about Utilities Pipeline orchestration', 'active'),
(93, 39, 35, 'can_analyze', '8-Graph Workflow can reason about Session Graph tracking', 'active');
