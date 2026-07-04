-- ============================================================
-- BATCH 6: Semantic population for books 23, 24, 25
-- Book 23: Plf_GraphIngestSpec.md (graph engine domain unification spec)
-- Book 24: Plf_MagneticRadiusSearch.md (cross-chat context retrieval concept)
-- Book 25: Plf_MagneticSearchV3.md (context reconstruction engine v3-v5)
-- ============================================================
-- Validated: WAL checkpointed, 0 orphans, schema confirmed.
-- Starting IDs: nodes=220, links=131, glossary=91, checks=88, provenance=21, connections=42
-- ============================================================

-- ─── BOOK 23: GraphIngestSpec ───

UPDATE books SET core_thesis = 'Unify graph code from 3 folders (dom_compression, efl_brain, code_store_variations) into single VBStyle domain in v20_hybrid_best.db. 8-graph pipeline + CascadeEngine + DEGS + self-writing graph evolution.', status = 'spec', sqlite_backend = 'sqlite' WHERE book_id = 23;

-- Section semantic roles
UPDATE sections SET section_type = 'as_is_inventory' WHERE section_id IN (472,473,474);
UPDATE sections SET section_type = 'to_be_design' WHERE section_id IN (475,476,477,478,479);
UPDATE sections SET section_type = 'dispatch_table' WHERE section_id = 480;
UPDATE sections SET section_type = 'bcl_parsing_flow' WHERE section_id = 481;
UPDATE sections SET section_type = 'verification_checks' WHERE section_id IN (482,483,484);
UPDATE sections SET section_type = 'degs_schema' WHERE section_id = 485;
UPDATE sections SET section_type = 'degs_engine' WHERE section_id = 486;
UPDATE sections SET section_type = 'degs_workspace' WHERE section_id = 487;
UPDATE sections SET section_type = 'degs_gui' WHERE section_id = 488;
UPDATE sections SET section_type = 'degs_autogen' WHERE section_id = 489;
UPDATE sections SET section_type = 'degs_bcl_integration' WHERE section_id = 490;
UPDATE sections SET section_type = 'degs_pipeline_integration' WHERE section_id = 491;
UPDATE sections SET section_type = 'error_modes' WHERE section_id = 492;
UPDATE sections SET section_type = 'cascade_purpose' WHERE section_id = 493;
UPDATE sections SET section_type = 'cascade_schema' WHERE section_id = 494;
UPDATE sections SET section_type = 'cascade_engine' WHERE section_id = 495;
UPDATE sections SET section_type = 'cascade_graphs' WHERE section_id = 496;
UPDATE sections SET section_type = 'cascade_gate' WHERE section_id = 497;
UPDATE sections SET section_type = 'cascade_self_correcting' WHERE section_id = 498;
UPDATE sections SET section_type = 'cascade_flow' WHERE section_id = 499;

-- Nodes for book 23
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(220, 'database', 'v20_hybrid_best.db', 'Unified SQLite DB: 1700+ classes, 14256 methods, 80+ domains, 48 graph_engine classes, 541 methods', 'database', 0.95, 23, 254),
(221, 'tool', 'GraphEngine', 'Single VBStyle MemUnit with Run() dispatch to 8 views + algorithms + search + BCL + status', 'engine', 0.95, 23, 256),
(222, 'tool', 'GraphViewer', 'Shared Tkinter Canvas: nodes, edges, labels, click-to-inspect, filter, drag/drop, zoom, export', 'gui', 0.75, 23, 256),
(223, 'tool', 'CascadeEngine', 'Pre-code validation compiler: validates structure before code generation. HARD GATE on GraphEngine', 'cascade', 0.90, 23, 264),
(224, 'tool', 'DecisionEngine', 'DEGS: decision graph execution with start/step/auto/end. BCL payload parsing. AmIAllowed enforcement', 'decision', 0.90, 23, 261),
(225, 'tool', 'GraphOrchestrator', 'Root MemUnit coordinating all subsystems: cascade, pipeline, degs, sandbox, engine, gui, status', 'engine', 0.85, 23, 257),
(226, 'tool', 'TmpWorkspace', 'Sandbox MemUnit: create/write/read/list/clean/compile. Each AI run gets own tmp folder', 'sandbox', 0.65, 23, 261),
(227, 'tool', 'AutoGenerator', 'Self-writing graph evolution: auto_generate, dedup, merge_runs, promote_path, prune_dead, metrics', 'decision', 0.80, 23, 261),
(228, 'tool', 'Inspect', 'Post-code analysis: parse .py files via AST, build typed graph, compare DB vs real files', 'engine', 0.65, 23, 257),
(229, 'tool', 'Verify', 'Plan vs actual comparison: check, missing, extra, report', 'engine', 0.65, 23, 257),
(230, 'tool', 'Config_graph_engine', 'VBStyle Config: DB_PATH, TMP_DIR, DOMAIN, MAX_RETRY=3, MAX_STEPS=50, PRUNE_THRESHOLD=0.1', 'config', 0.70, 23, 257),
(231, 'concept', '8-Graph Pipeline', 'Plan, Spec, Flow, Lifecycle, Dependency, Error, Orchestration, Gap — 8 views in sequence', 'graph', 0.90, 23, 256),
(232, 'concept', 'DEGS', 'Decision Execution Graph System: ACT → VERIFY → BRANCH → LOG → REPEAT controlled loop', 'decision', 0.85, 23, 261),
(233, 'concept', 'HARD GATE', 'GraphEngine.Run("code") BLOCKED unless cascade_runs.status == "passed"', 'cascade', 0.85, 23, 264),
(234, 'concept', 'BCL Instructions', '11 tokens in bcl_instructions: AddDomCode, CodeStyle, HowToVerify, GraphEnginePipeline, WhereDoesCodeGo, ErrorDecisionTree, KnowledgeCodegraph, AmIAllowed, WhenToAddCode, AlternativeSteps, WhyVBStyle', 'bcl', 0.80, 23, 256),
(235, 'concept', 'spec_data', 'NEW table for domain specs (classes, edges, categories, flows) — one copy, not duplicated 16x', 'database', 0.70, 23, 256),
(236, 'concept', 'No Duplicate Data Rule', 'spec_data stored in DB once, not copied across .py files. CLASSES= copied 16x, EDGES= copied 30x before', 'architecture', 0.80, 23, 255),
(237, 'concept', 'Self-Writing Graph', 'AI generates new nodes+edges from failure logs. Graph gets smarter every run. Dedup, promote, prune', 'decision', 0.75, 23, 261),
(238, 'concept', 'Pipeline as Graph', '10-step pipeline becomes decision graph with recovery paths. MAX_RETRY=3 prevents infinite loops', 'graph', 0.75, 23, 261),
(239, 'concept', 'AmIAllowed Enforcement', 'Before any DB write, check AmIAllowed BCL token. If denied, return Tuple3(0, None, "permission_denied")', 'security', 0.70, 23, 258),
(240, 'data_model', 'DEGS Schema', 'decision_nodes, decision_edges, execution_log, run_state, run_metrics — 5 tables for decision execution', 'database', 0.75, 23, 261),
(241, 'data_model', 'CASCADE Schema', 'cascade_runs, cascade_stage_results, cascade_rules — 3 tables for pre-code validation', 'database', 0.70, 23, 264),
(242, 'concept', '17 Rules', 'No .py files, VBStyle, no print, no decorators, no hardcoded paths, BCL instructions, one copy data/viewer, verify before done, pipeline order, max retry/steps, AmIAllowed, end run, dedup, headless, DB locking', 'governance', 0.75, 23, 258),
(243, 'concept', 'Error Recovery', '18 error modes with detection, recovery, fallback. SyntaxError, missing Run(), missing Tuple3, hardcoded paths, ImportError, VBStyle violations, terminal nodes, deleted nodes, BCL not found, Tkinter fail, dedup, concurrent writes, max retry/steps, permission denied, timeout, cascade blocked', 'error_handling', 0.70, 23, 263);

-- Links for book 23
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(131, 221, 231, 'implements', 1.0, 'GraphEngine implements 8-graph pipeline views'),
(132, 221, 222, 'renders_via', 1.0, 'GraphEngine renders via shared GraphViewer'),
(133, 225, 223, 'routes_through', 1.0, 'GraphOrchestrator routes through CascadeEngine first'),
(134, 225, 221, 'dispatches_to', 1.0, 'GraphOrchestrator dispatches to GraphEngine (gated by cascade)'),
(135, 225, 224, 'dispatches_to', 0.8, 'GraphOrchestrator dispatches to DecisionEngine'),
(136, 223, 221, 'gates', 1.0, 'CascadeEngine HARD GATE blocks GraphEngine code execution'),
(137, 233, 223, 'enforced_by', 1.0, 'HARD GATE enforced by CascadeEngine'),
(138, 224, 234, 'reads', 1.0, 'DecisionEngine reads BCL instructions as decision tree'),
(139, 224, 240, 'uses', 1.0, 'DecisionEngine uses DEGS schema tables'),
(140, 227, 224, 'extends', 0.8, 'AutoGenerator extends DecisionEngine with self-writing'),
(141, 237, 227, 'implemented_by', 1.0, 'Self-writing graph implemented by AutoGenerator'),
(142, 238, 224, 'executed_by', 0.8, 'Pipeline as graph executed by DecisionEngine'),
(143, 239, 234, 'checks', 1.0, 'AmIAllowed checks BCL instructions before writes'),
(144, 235, 220, 'stored_in', 1.0, 'spec_data stored in v20_hybrid_best.db'),
(145, 236, 235, 'motivates', 1.0, 'No duplicate data rule motivates spec_data table'),
(146, 221, 220, 'stored_in', 1.0, 'GraphEngine code stored in v20_hybrid_best.db'),
(147, 230, 221, 'configures', 1.0, 'Config_graph_engine configures GraphEngine'),
(148, 228, 221, 'feeds', 0.7, 'Inspect feeds real code analysis to GraphEngine'),
(149, 229, 221, 'validates', 0.7, 'Verify validates GraphEngine plan vs actual'),
(150, 226, 225, 'supports', 0.6, 'TmpWorkspace supports GraphOrchestrator sandboxed runs'),
(151, 242, 221, 'governs', 0.8, '17 rules govern GraphEngine behavior'),
(152, 243, 224, 'handled_by', 0.7, 'Error recovery handled by DecisionEngine fallbacks'),
(153, 241, 223, 'stores', 1.0, 'CASCADE schema stores CascadeEngine state'),
(154, 231, 222, 'rendered_by', 0.8, '8-graph pipeline rendered by GraphViewer');

-- Glossary terms for book 23
INSERT OR IGNORE INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(91, 'v20_hybrid_best.db', 'Unified SQLite DB with 1700+ classes, 14256 methods across 80+ domains', 'database', 'nodes.node_name=v20_hybrid_best.db'),
(92, 'DEGS', 'Decision Execution Graph System: ACT → VERIFY → BRANCH → LOG → REPEAT loop', 'concept', 'nodes.node_name=DEGS'),
(93, 'HARD GATE', 'CascadeEngine blocks GraphEngine code execution until validation passes', 'concept', 'nodes.node_name=HARD GATE'),
(94, 'Self-Writing Graph', 'AI generates new nodes+edges from failure logs, graph gets smarter every run', 'concept', 'nodes.node_name=Self-Writing Graph'),
(95, 'spec_data', 'DB table for domain specs (classes, edges, categories) — one copy not 16', 'database', 'nodes.node_name=spec_data'),
(96, 'AmIAllowed Enforcement', 'BCL token check before any DB write, returns permission_denied if blocked', 'security', 'nodes.node_name=AmIAllowed Enforcement');

-- Glossary links for book 23
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) VALUES
(91, 23, 255, 474, 'primary'),
(92, 23, 261, 485, 'primary'),
(93, 23, 264, 497, 'primary'),
(94, 23, 261, 489, 'primary'),
(95, 23, 256, 476, 'primary'),
(96, 23, 258, NULL, 'primary');

-- Checks for book 23
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(88, 23, 259, 'Graph code ingestion', 'structure', 'PASS', '48 classes, 541 methods ingested into v20_hybrid_best.db'),
(89, 23, 259, 'BCL instructions created', 'structure', 'PASS', '11 BCL tokens in bcl_instructions table'),
(90, 23, 259, 'VBStyle compliance', 'compliance', 'PARTIAL', '375 VBStyle methods, 109 Tuple3 returns out of 541'),
(91, 23, 262, 'Build order progress', 'structure', 'PARTIAL', 'Steps 1-6 done, steps 7-26 pending (20 steps remaining)'),
(92, 23, 263, 'Error handling completeness', 'structure', 'PASS', '18 error modes documented with detection, recovery, fallback');

-- Provenance for book 23
INSERT INTO provenance (provenance_id, source_path, dest_path, dest_type, book_id, notes) VALUES
(21, 'dom_compression/ + efl_brain/ + code_store_variations/ + v20_hybrid_best.db', 'Plf_GraphIngestSpec.md', 'markdown', 23, 'Unification spec for graph engine domain from 3 separate folders');

-- Pipeline connections for book 23
INSERT INTO pipeline_connections (connection_id, from_book_id, to_book_id, connection_type, description, status) VALUES
(42, 23, 19, 'implemented_by', 'Graph ingest spec implemented by Dom_Graph pipeline', 'active'),
(43, 23, 22, 'uses', 'Graph ingest spec uses codebase inventory for graph_engine classes', 'active'),
(44, 23, 18, 'constrained_by', 'Graph ingest spec constrained by 3-DB storage architecture', 'active'),
(45, 23, 30, 'validated_by', 'Graph ingest spec validated by pipeline gap analysis', 'active');

-- ─── BOOK 24: MagneticRadiusSearch ───

UPDATE books SET core_thesis = 'Cross-chat context retrieval: words magnetically pull ±N lines of context from multiple chats, forming evidence clumps. Three forces: keyword gravity, embedding gravity, graph gravity. Compresses LATE at reasoning time, not at storage time.', status = 'design', sqlite_backend = 'mysql+qdrant+neo4j+elasticsearch' WHERE book_id = 24;

-- Section semantic roles
UPDATE sections SET section_type = 'pipeline_step' WHERE section_id IN (500,501,502,503);
UPDATE sections SET section_type = 'comparison' WHERE section_id = 504;
UPDATE sections SET section_type = 'solution_list' WHERE section_id = 505;
UPDATE sections SET section_type = 'db_mapping' WHERE section_id = 506;
UPDATE sections SET section_type = 'query_flow' WHERE section_id = 507;
UPDATE sections SET section_type = 'parameter_tuning' WHERE section_id = 508;
UPDATE sections SET section_type = 'weighting_factor' WHERE section_id IN (509,510,511);
UPDATE sections SET section_type = 'weight_control' WHERE section_id IN (512,513,514,515,516,517);
UPDATE sections SET section_type = 'data_structure' WHERE section_id IN (518,519);

-- Nodes for book 24
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(244, 'concept', 'Magnetic Radius Search', 'Cross-chat context retrieval: word hits magnetically pull ±N lines of surrounding context from multiple conversations', 'retrieval', 0.95, 24, 265),
(245, 'concept', 'Context Clump', 'Collection of raw conversation fragments from different chats, all magnetically attracted to the same signal', 'retrieval', 0.85, 24, 266),
(246, 'concept', 'Late Compression', 'LLM compresses at reasoning time, not at storage time. Keeps raw text until the LLM sees the full story arc', 'retrieval', 0.85, 24, 267),
(247, 'concept', 'Level 1.5 Retrieval', 'Between word graph (Level 1) and concept graph (Level 2). NOT just word index, NOT yet reasoning graph', 'architecture', 0.80, 24, 269),
(248, 'concept', 'Inverted Index', 'Word → chat_id → line number. Elasticsearch-style lookup. Fast but shallow', 'retrieval', 0.70, 24, 273),
(249, 'concept', 'Window Expansion', '±N lines context around each hit. Context window retrieval used in log systems and RAG pipelines', 'retrieval', 0.75, 24, 274),
(250, 'concept', 'Semantic Cluster', 'Multiple hits across chats merged into a region of meaning. NOT clustering words, clustering contexts', 'retrieval', 0.80, 24, 275),
(251, 'concept', 'Context Field Retrieval', 'Each word creates a gravity field. All occurrences pull in nearby context. Overlapping fields merge into clusters', 'retrieval', 0.85, 24, 276),
(252, 'concept', 'Keyword Force', 'Exact match gravity: word appears or not, frequency in chat, position (title > body). Precision signal', 'retrieval', 0.75, 24, 280),
(253, 'concept', 'Embedding Force', 'Meaning gravity: semantic similarity. SSH fixes login ≈ secure remote access solution. Conceptual similarity signal', 'retrieval', 0.75, 24, 281),
(254, 'concept', 'Graph Force', 'Structural gravity: how connected a node is, centrality in decision chains, leads to outcomes. Reasoning/causality signal', 'retrieval', 0.75, 24, 282),
(255, 'concept', 'Force-Field Memory', 'NOT search, NOT graph, NOT embeddings. A force-field memory system over text history. Chats=mass, words=sensors, embeddings=direction vectors, edges=constraints', 'retrieval', 0.85, 24, 284),
(256, 'concept', 'Magnetic Weight', '7 factors: frequency, recency, co-occurrence, role signal, user confirmation, decision marker, outcome marker', 'retrieval', 0.80, 24, 276),
(257, 'concept', 'Noise Filtering', '47 raw hits → 30 weighted hits above threshold → 17 noise filtered out. Weighting separates signal from noise', 'retrieval', 0.75, 24, 276),
(258, 'concept', 'Dynamic Radius', 'Radius tuned by: hit count (few hits → larger radius), token budget, hit quality (exact → larger, fuzzy → smaller)', 'retrieval', 0.70, 24, 268),
(259, 'concept', 'Tiered Radius', 'Tier 1 (exact+recent): ±200 lines. Tier 2 (exact+old): ±50 lines. Tier 3 (fuzzy): ±20 lines', 'retrieval', 0.65, 24, 268),
(260, 'database', 'Elasticsearch Role', 'Signal detection: find all hits across 14,800 chats. Fast inverted index lookup', 'database', 0.75, 24, 270),
(261, 'database', 'MySQL Role', 'Raw context fetch: grab ±200 lines around each hit. Source records for context windows', 'database', 0.75, 24, 270),
(262, 'database', 'Qdrant Role', 'Semantic expansion: find things with similar meaning. Broader net beyond exact matches', 'database', 0.70, 24, 270),
(263, 'database', 'Neo4j Role', 'Relationship connection: SSH → fixes → RustDesk → failures → decisions. Store extracted knowledge as graph', 'database', 0.70, 24, 270),
(264, 'concept', 'Unified Scoring Model', 'SCORE = keyword×Wk + embedding×We + graph×Wg + recency×Wr + frequency×Wf + context_window×Wc', 'retrieval', 0.85, 24, 283),
(265, 'concept', 'Chat Segment Data Structure', '12 fields: chat_id, line_range, timestamp, word_frequency, embedding_vector, graph_node_id, mention_count, co_occurrence_tags, role_label, decision_linked, outcome_linked, user_confirmed', 'data_model', 0.75, 24, 286);

-- Links for book 24
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(155, 244, 245, 'produces', 1.0, 'Magnetic radius search produces context clumps'),
(156, 244, 246, 'uses', 1.0, 'Magnetic radius uses late compression — LLM reasons at query time'),
(157, 244, 247, 'positioned_as', 1.0, 'Magnetic radius is Level 1.5 retrieval'),
(158, 244, 248, 'step_1', 1.0, 'Step 1: Inverted index finds word hits'),
(159, 244, 249, 'step_2', 1.0, 'Step 2: Window expansion grabs ±N lines'),
(160, 244, 250, 'step_3', 1.0, 'Step 3: Semantic cluster merges contexts'),
(161, 244, 251, 'defined_as', 1.0, 'Magnetic radius = context field retrieval'),
(162, 264, 252, 'includes', 1.0, 'Unified scoring includes keyword force'),
(163, 264, 253, 'includes', 1.0, 'Unified scoring includes embedding force'),
(164, 264, 254, 'includes', 1.0, 'Unified scoring includes graph force'),
(165, 255, 252, 'combines', 1.0, 'Force-field memory combines keyword force'),
(166, 255, 253, 'combines', 1.0, 'Force-field memory combines embedding force'),
(167, 255, 254, 'combines', 1.0, 'Force-field memory combines graph force'),
(168, 256, 257, 'enables', 1.0, 'Magnetic weighting enables noise filtering'),
(169, 244, 258, 'uses', 0.8, 'Magnetic radius uses dynamic radius tuning'),
(170, 258, 259, 'implements', 0.8, 'Dynamic radius implements tiered approach'),
(171, 244, 260, 'uses', 0.8, 'Magnetic radius uses Elasticsearch for signal detection'),
(172, 244, 261, 'uses', 0.8, 'Magnetic radius uses MySQL for context fetch'),
(173, 244, 262, 'uses', 0.8, 'Magnetic radius uses Qdrant for semantic expansion'),
(174, 244, 263, 'uses', 0.8, 'Magnetic radius uses Neo4j for relationship storage'),
(175, 265, 260, 'stored_in', 0.7, 'Chat segment word_frequency stored in Elasticsearch'),
(176, 265, 261, 'stored_in', 0.7, 'Chat segment chat_id/lines/timestamp stored in MySQL'),
(177, 265, 262, 'stored_in', 0.7, 'Chat segment embedding_vector stored in Qdrant'),
(178, 265, 263, 'stored_in', 0.7, 'Chat segment graph_node_id stored in Neo4j');

-- Glossary terms for book 24
INSERT OR IGNORE INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(97, 'Magnetic Radius Search', 'Cross-chat context retrieval where word hits pull ±N lines of surrounding context from multiple conversations', 'retrieval', 'nodes.node_name=Magnetic Radius Search'),
(98, 'Context Clump', 'Collection of raw conversation fragments from different chats attracted to same signal', 'retrieval', 'nodes.node_name=Context Clump'),
(99, 'Late Compression', 'LLM compresses at reasoning time not storage time, keeping raw text until full story arc is visible', 'retrieval', 'nodes.node_name=Late Compression'),
(100, 'Force-Field Memory', 'Memory system where chats=mass, words=sensors, embeddings=direction vectors, edges=constraints', 'retrieval', 'nodes.node_name=Force-Field Memory'),
(101, 'Unified Scoring Model', 'SCORE = keyword×Wk + embedding×We + graph×Wg + recency×Wr + frequency×Wf + context_window×Wc', 'retrieval', 'nodes.node_name=Unified Scoring Model');

-- Glossary links for book 24
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) VALUES
(97, 24, 265, NULL, 'primary'),
(98, 24, 266, 502, 'primary'),
(99, 24, 267, 504, 'primary'),
(100, 24, 284, NULL, 'primary'),
(101, 24, 283, NULL, 'primary');

-- Checks for book 24
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(93, 24, 268, 'Context budget management', 'design', 'PASS', '4 solutions: radius tuning, relevance ranking, context budget, tiered radius'),
(94, 24, 271, '21-component spec alignment', 'design', 'PASS', '5 components directly use magnetic radius: Node Extraction, Graph Activation, Query Planner, Evidence Builder, Observation Engine'),
(95, 24, 287, 'MySQL learned_rules references', 'reference', 'PASS', '3 hits in learned_rules: skip magnetic methods, VS Code GUI magnetic registry, magnetic search testing');

-- Provenance for book 24
INSERT INTO provenance (provenance_id, source_path, dest_path, dest_type, book_id, notes) VALUES
(22, 'User concept + graph engine architecture discussions + MySQL vb_shared.learned_rules', 'Plf_MagneticRadiusSearch.md', 'markdown', 24, 'Concept developed by user during graph engine architecture discussions');

-- Pipeline connections for book 24
INSERT INTO pipeline_connections (connection_id, from_book_id, to_book_id, connection_type, description, status) VALUES
(46, 24, 25, 'evolved_into', 'Magnetic radius concept evolved into Magnetic Search v3 context reconstruction engine', 'active'),
(47, 24, 18, 'uses', 'Magnetic radius uses 3-DB architecture: Elasticsearch, MySQL, Qdrant, Neo4j', 'active'),
(48, 24, 23, 'feeds', 'Magnetic radius feeds observation engine in graph ingest spec', 'active');

-- ─── BOOK 25: MagneticSearchV3 ───

UPDATE books SET core_thesis = 'Context reconstruction engine v3-v5. NOT a search engine. Locates occurrences → expands radius → merges → ranks → returns coherent context packet. v4 adds graph traversal. v5 adds memory cognition (COMPILE/RECALL/UPDATE/EVOLVE).', status = 'active', sqlite_backend = 'mysql+qdrant' WHERE book_id = 25;

-- Section semantic roles
UPDATE sections SET section_type = 'radius_dimensions' WHERE section_id = 520;
UPDATE sections SET section_type = 'chat_radius' WHERE section_id = 521;
UPDATE sections SET section_type = 'primitive_embeddings' WHERE section_id = 522;
UPDATE sections SET section_type = 'primitive_magnetic' WHERE section_id = 523;
UPDATE sections SET section_type = 'primitive_graph' WHERE section_id = 524;
UPDATE sections SET section_type = 'primitive_comparison' WHERE section_id = 525;
UPDATE sections SET section_type = 'memory_lifecycle' WHERE section_id = 526;
UPDATE sections SET section_type = 'performance_metrics' WHERE section_id = 527;
UPDATE sections SET section_type = 'storage_schema' WHERE section_id = 528;

-- Nodes for book 25
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(266, 'tool', 'msearch3', 'C binary magnetic search v6. Searches 215K+ messages across 3 databases. Modes: exact, prefix, contains, regex, magnetic, full, semantic, hybrid', 'retrieval', 0.95, 25, 291),
(267, 'concept', 'Context Reconstruction', 'NOT search. Reconstructs working context around X. Locate → Expand → Merge → Recover → Rank → Return coherent packet', 'retrieval', 0.90, 25, 291),
(268, 'concept', '9-Dimensional Radius', 'Text, AST, Execution, Dependency, Temporal, Conversation, Semantic, BCL, IR — 9 radius expansion types', 'retrieval', 0.85, 25, 294),
(269, 'concept', 'Context Packet', 'JSON packet: authority, bcl, code, weight, graph, rules, chat_context, timeline, related, confidence', 'retrieval', 0.80, 25, 295),
(270, 'concept', 'Three Retrieval Primitives', '1. Embeddings (probabilistic: what is like this?), 2. Magnetic (deterministic: where exactly did this occur?), 3. Graph (relational: what is connected?)', 'retrieval', 0.85, 25, 297),
(271, 'tool', 'MagneticGraph.py', 'v4 graph traversal layer: multi-hop chat→file→class→BCL→rule→chat. Provenance chain. Expand at each hop. Rank by authority+relevance+hop distance', 'retrieval', 0.80, 25, 298),
(272, 'tool', 'MemoryObject.py', 'v5 memory cognition: COMPILE/RECALL/UPDATE/EVOLVE/DIFF/LIST/FORGET. Persistent memory objects with versioned history', 'memory', 0.85, 25, 299),
(273, 'concept', 'COMPILE', 'First query: run magnetic search, build provenance, extract graph edges, store in memory_objects, record v1', 'memory', 0.80, 25, 299),
(274, 'concept', 'RECALL', 'Subsequent query: load from memory_objects, increment access_count, return instantly (16x faster than recompute)', 'memory', 0.85, 25, 299),
(275, 'concept', 'UPDATE', 'New data: run magnetic search again, diff against stored packet, if changes merge+increment version, if no changes return no_changes', 'memory', 0.75, 25, 299),
(276, 'concept', 'EVOLVE', 'History: return full evolution log with versions, change types, deltas', 'memory', 0.70, 25, 299),
(277, 'data_model', 'memory_objects table', 'id, query_key (SHA256), query_text, mode, radius, packet (JSON), provenance (JSON), graph_edges (JSON), section_counts (JSON), version, access_count, created_at, updated_at', 'database', 0.75, 25, 299),
(278, 'data_model', 'memory_object_evolution table', 'id, memory_object_id, version, change_type, change_summary, sections_affected, delta_count, changed_at', 'database', 0.70, 25, 299),
(279, 'concept', 'v4 Graph Layer', 'Adds: Follow relationships → Expand again. Chat→file→class→BCL→rule→chat. Each hop expands radius. Connected neighborhood not isolated windows', 'retrieval', 0.80, 25, 298),
(280, 'concept', 'v5 Memory Cognition', 'Adds: Compile → Store → Recall → Update → Evolve. System is no longer a search engine, it is a memory compiler', 'memory', 0.85, 25, 299),
(281, 'concept', 'Performance: COMPILE vs RECALL', 'COMPILE: 0.267s (full magnetic search 9 dimensions). RECALL: 0.017s (load from MySQL — 16x faster)', 'performance', 0.75, 25, 299);

-- Links for book 25
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(179, 266, 267, 'implements', 1.0, 'msearch3 implements context reconstruction engine'),
(180, 267, 268, 'uses', 1.0, 'Context reconstruction uses 9-dimensional radius expansion'),
(181, 267, 269, 'produces', 1.0, 'Context reconstruction produces context packets'),
(182, 270, 266, 'includes', 1.0, 'Magnetic search primitive implemented by msearch3'),
(183, 271, 266, 'extends', 1.0, 'MagneticGraph.py v4 extends msearch3 with graph traversal'),
(184, 272, 266, 'extends', 1.0, 'MemoryObject.py v5 extends msearch3 with memory cognition'),
(185, 272, 273, 'implements', 1.0, 'MemoryObject implements COMPILE lifecycle'),
(186, 272, 274, 'implements', 1.0, 'MemoryObject implements RECALL lifecycle'),
(187, 272, 275, 'implements', 1.0, 'MemoryObject implements UPDATE lifecycle'),
(188, 272, 276, 'implements', 1.0, 'MemoryObject implements EVOLVE lifecycle'),
(189, 273, 277, 'stores_in', 1.0, 'COMPILE stores in memory_objects table'),
(190, 274, 277, 'reads_from', 1.0, 'RECALL reads from memory_objects table'),
(191, 275, 278, 'logs_to', 0.8, 'UPDATE logs changes to memory_object_evolution'),
(192, 276, 278, 'reads_from', 0.8, 'EVOLVE reads from memory_object_evolution'),
(193, 279, 271, 'implemented_by', 1.0, 'v4 graph layer implemented by MagneticGraph.py'),
(194, 280, 272, 'implemented_by', 1.0, 'v5 memory cognition implemented by MemoryObject.py'),
(195, 281, 273, 'measures', 1.0, 'Performance measures COMPILE at 0.267s'),
(196, 281, 274, 'measures', 1.0, 'Performance measures RECALL at 0.017s (16x faster)'),
(197, 268, 266, 'powers', 0.8, '9-dimensional radius powers msearch3 magnetic mode');

-- Glossary terms for book 25
INSERT OR IGNORE INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(102, 'msearch3', 'C binary magnetic search v6, 215K+ messages across 3 databases, modes: exact/prefix/contains/regex/magnetic/full/semantic/hybrid', 'tool', 'nodes.node_name=msearch3'),
(103, 'Context Reconstruction', 'NOT search. Locate → Expand → Merge → Recover → Rank → Return coherent context packet', 'retrieval', 'nodes.node_name=Context Reconstruction'),
(104, '9-Dimensional Radius', 'Text, AST, Execution, Dependency, Temporal, Conversation, Semantic, BCL, IR radius expansion', 'retrieval', 'nodes.node_name=9-Dimensional Radius'),
(105, 'Memory Cognition (v5)', 'COMPILE/RECALL/UPDATE/EVOLVE lifecycle. System is a memory compiler not a search engine', 'memory', 'nodes.node_name=v5 Memory Cognition');

-- Glossary links for book 25
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) VALUES
(102, 25, 300, NULL, 'primary'),
(103, 25, 291, NULL, 'primary'),
(104, 25, 294, 520, 'primary'),
(105, 25, 299, 526, 'primary');

-- Checks for book 25
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(96, 25, 299, 'COMPILE vs RECALL performance', 'performance', 'PASS', 'COMPILE: 0.267s, RECALL: 0.017s = 16x faster'),
(97, 25, 297, 'Three retrieval primitives defined', 'structure', 'PASS', 'Embeddings (probabilistic), Magnetic (deterministic), Graph (relational) — complementary not competing'),
(98, 25, 294, '9-dimensional radius expansion', 'structure', 'PASS', 'Text, AST, Execution, Dependency, Temporal, Conversation, Semantic, BCL, IR — all 9 dimensions defined');

-- Provenance for book 25
INSERT INTO provenance (provenance_id, source_path, dest_path, dest_type, book_id, notes) VALUES
(23, 'Cascade_toolStack/bin_tools/msearch3.c + MagneticGraph.py + MemoryObject.py', 'Plf_MagneticSearchV3.md', 'markdown', 25, 'Architecture document for magnetic search v3-v5 evolution');

-- Pipeline connections for book 25
INSERT INTO pipeline_connections (connection_id, from_book_id, to_book_id, connection_type, description, status) VALUES
(49, 25, 24, 'evolved_from', 'Magnetic Search v3 evolved from magnetic radius search concept', 'active'),
(50, 25, 18, 'uses', 'Magnetic Search v3 uses MySQL + Qdrant from 3-DB architecture', 'active'),
(51, 25, 23, 'integrates_with', 'Magnetic Search v4 graph layer integrates with graph engine pipeline', 'active');
