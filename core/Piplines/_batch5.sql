-- ============================================================
-- BATCH 5: Semantic population for books 18, 19, 22
-- Book 18: Plf_DatabaseStorageArchitecture.md (3-DB stack design)
-- Book 19: Plf_DomGraphPipeline.md (Dom_Graph domain breakdown)
-- Book 22: Plf_GraphEngineCodebase.md (graph code asset inventory)
-- ============================================================
-- Validated: WAL checkpointed, 0 orphans, schema confirmed.
-- Starting IDs: nodes=151, links=70, glossary=76, checks=77, provenance=18, connections=32
-- ============================================================

-- ─── BOOK 18: DatabaseStorageArchitecture ───

-- Book metadata update
UPDATE books SET core_thesis = '3-database stack (Neo4j + MySQL + Qdrant) with clean ownership: MySQL=truth, Qdrant=meaning, Neo4j=relationships. ID bridge connects them without duplication.', status = 'design', sqlite_backend = 'mysql+qdrant+neo4j' WHERE book_id = 18;

-- Section semantic roles
UPDATE sections SET section_type = 'migration_steps' WHERE section_id = 400;
UPDATE sections SET section_type = 'relationship_category' WHERE section_id IN (401,402,403,404,405,406,407);
UPDATE sections SET section_type = 'ownership_list' WHERE section_id IN (408,409,410);
UPDATE sections SET section_type = 'architecture_rule' WHERE section_id IN (411,412,413);
UPDATE sections SET section_type = 'tier_ranking' WHERE section_id IN (414,415,416);
UPDATE sections SET section_type = 'engine_comparison' WHERE section_id = 417;

-- Nodes for book 18
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(151, 'database', 'Neo4j', 'Graph database for relationship storage, traversal, evidence chains', 'storage', 0.95, 18, 190),
(152, 'database', 'MySQL', 'Relational database for structured truth, codebase, computation units', 'storage', 0.95, 18, 191),
(153, 'database', 'Qdrant', 'Vector database for embeddings, semantic similarity, meaning search', 'storage', 0.95, 18, 192),
(154, 'database', 'Redis', 'Optional cache, agent runtime state, fast activation', 'storage', 0.50, 18, 201),
(155, 'database', 'Elasticsearch', 'Full-text search engine for large text corpora, keyword matching', 'storage', 0.60, 18, 202),
(156, 'database', 'ArangoDB', 'Graph + Document + Key-Value multi-model database', 'storage', 0.40, 18, 190),
(157, 'concept', '3-Database Stack', 'Neo4j + MySQL + Qdrant architecture for graph engine memory', 'architecture', 0.90, 18, 197),
(158, 'concept', 'ID Bridge', 'Same ID across all 3 databases to connect records without duplicating data', 'architecture', 0.85, 18, 200),
(159, 'concept', 'Truth Store', 'MySQL role: structured facts, codebase, computation units, raw records', 'architecture', 0.85, 18, 197),
(160, 'concept', 'Meaning Store', 'Qdrant role: embeddings, semantic similarity, context activation', 'architecture', 0.85, 18, 197),
(161, 'concept', 'Relationship Store', 'Neo4j role: graph traversal, causality, identity, evidence chains', 'architecture', 0.85, 18, 197),
(162, 'concept', 'No Duplicate Storage Rule', 'Data lives in ONE place; ID is the bridge. Storing data in multiple DBs is forbidden.', 'architecture', 0.90, 18, 200),
(163, 'concept', 'Graph Traversal', 'Native relationship traversal without JOINs - Neo4j core strength', 'graph', 0.80, 18, 190),
(164, 'concept', 'Semantic Similarity', 'Finding nodes that MEAN the same thing via vector embeddings', 'vector', 0.80, 18, 192),
(165, 'concept', 'Evidence Chain', 'Fact -> Evidence -> Message -> Timestamp traversal in Neo4j', 'graph', 0.75, 18, 194),
(166, 'concept', 'Causal Graph', 'CAUSED_BY, RESOLVES, LED_TO relationships in Neo4j', 'graph', 0.70, 18, 194),
(167, 'concept', 'Identity Resolution', 'ALIAS_OF, SAME_AS, RENAMED_TO relationships in Neo4j', 'graph', 0.70, 18, 194),
(168, 'process', 'MySQL to Neo4j Migration', '1:1 mapping from graph_computation_units rows to Neo4j nodes', 'migration', 0.70, 18, 192),
(169, 'data_model', 'Neo4j Node Labels', 'Message, Observation, Fact, Episode, SemanticMemory, Concept, Tool, Entity, Decision, Error, Task, Goal, Blocker, Hypothesis, Experiment, Outcome, Evidence, Domain, Class, Method', 'graph', 0.80, 18, 193),
(170, 'data_model', 'Neo4j Relationship Types', 'OBSERVED_AS, SUPPORTS, PART_OF, COMPRESSED_TO, CONTRADICTS, OBSOLETES, REPLACES, SUPERSEDED_BY, BEFORE, AFTER, ALIAS_OF, SAME_AS, CAUSED_BY, RESOLVES, LED_TO, FIXED_BY, CONTAINS, IN_FILE, REFERENCES, DEPENDS_ON', 'graph', 0.80, 18, 194),
(171, 'concept', 'Memory Compression', 'Episode -> COMPRESSED_TO -> SemanticMemory in Neo4j memory model', 'memory', 0.60, 18, 193);

-- Links for book 18
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(70, 151, 163, 'optimized_for', 1.0, 'Native graph traversal without JOINs'),
(71, 152, 159, 'owns_role', 1.0, 'MySQL = Truth Store'),
(72, 153, 160, 'owns_role', 1.0, 'Qdrant = Meaning Store'),
(73, 151, 161, 'owns_role', 1.0, 'Neo4j = Relationship Store'),
(74, 157, 151, 'contains', 1.0, '3-DB stack includes Neo4j'),
(75, 157, 152, 'contains', 1.0, '3-DB stack includes MySQL'),
(76, 157, 153, 'contains', 1.0, '3-DB stack includes Qdrant'),
(77, 158, 151, 'connects', 1.0, 'ID bridge links all 3 DBs'),
(78, 158, 152, 'connects', 1.0, 'ID bridge links all 3 DBs'),
(79, 158, 153, 'connects', 1.0, 'ID bridge links all 3 DBs'),
(80, 162, 157, 'governs', 1.0, 'No duplicate rule governs the 3-DB stack'),
(81, 168, 152, 'reads_from', 1.0, 'Migration reads MySQL computation_units'),
(82, 168, 151, 'produces', 1.0, 'Migration produces Neo4j nodes and edges'),
(83, 155, 153, 'contrasts_with', 0.8, 'Elasticsearch=keyword search vs Qdrant=semantic search'),
(84, 154, 157, 'optional_addition', 0.5, 'Redis optional cache layer'),
(85, 169, 151, 'defines', 1.0, 'Node labels define Neo4j schema'),
(86, 170, 151, 'defines', 1.0, 'Relationship types define Neo4j schema'),
(87, 165, 151, 'stored_in', 1.0, 'Evidence chains stored in Neo4j'),
(88, 166, 151, 'stored_in', 1.0, 'Causal graph stored in Neo4j'),
(89, 167, 151, 'stored_in', 1.0, 'Identity resolution stored in Neo4j'),
(90, 164, 153, 'stored_in', 1.0, 'Semantic similarity stored in Qdrant'),
(91, 171, 151, 'stored_in', 0.8, 'Memory compression uses Neo4j COMPRESSED_TO');

-- Glossary terms for book 18
INSERT OR IGNORE INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(76, 'Neo4j', 'Graph database for relationship storage, traversal, and evidence chains', 'database', 'nodes table'),
(77, 'ID Bridge', 'Using same ID across MySQL, Qdrant, Neo4j to connect records without duplicating data', 'architecture', 'nodes.source_book_id'),
(78, 'Truth Store', 'MySQL role: structured facts, codebase, computation units, raw records', 'architecture', 'books table'),
(79, 'Meaning Store', 'Qdrant role: embeddings, semantic similarity, context activation', 'architecture', 'nodes.domain=vector'),
(80, 'Relationship Store', 'Neo4j role: graph traversal, causality, identity, evidence chains', 'architecture', 'links table'),
(81, 'No Duplicate Storage Rule', 'Data lives in ONE place; ID is the bridge across databases', 'principle', 'links.link_type');

-- Glossary links for book 18
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) VALUES
(76, 18, 190, NULL, 'primary'),
(77, 18, 200, 412, 'primary'),
(78, 18, 197, 408, 'primary'),
(79, 18, 197, 409, 'primary'),
(80, 18, 197, 410, 'primary'),
(81, 18, 200, 413, 'primary');

-- Checks for book 18
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(77, 18, 200, 'No data duplication across databases', 'architecture', 'PASS', 'Each DB owns one role, ID bridge connects'),
(78, 18, 200, 'ID bridge consistency', 'architecture', 'PASS', 'Same ID used across MySQL, Qdrant, Neo4j'),
(79, 18, 198, 'Clean ownership boundaries', 'architecture', 'PASS', 'MySQL=truth, Qdrant=meaning, Neo4j=relationships');

-- Provenance for book 18
INSERT INTO provenance (provenance_id, source_path, dest_path, dest_type, book_id, notes) VALUES
(18, 'test_all_on_chat.py (sections 10-12)', 'Plf_DatabaseStorageArchitecture.md', 'markdown', 18, 'Extracted from design sections in test_all_on_chat.py');

-- Pipeline connections for book 18
INSERT INTO pipeline_connections (connection_id, from_book_id, to_book_id, connection_type, description, status) VALUES
(32, 18, 22, 'informs', 'Storage architecture informs graph engine codebase design', 'active'),
(33, 18, 24, 'governs', 'Storage architecture governs magnetic radius search design', 'active'),
(34, 18, 23, 'related', 'Storage architecture related to graph ingestion spec', 'active');

-- ─── BOOK 19: DomGraphPipeline ───

-- Book metadata update
UPDATE books SET core_thesis = 'Full domain breakdown of Dom_Graph: 161 files, 157 classes, 2336 methods. Pipeline stages: Config -> Ingest -> Engine -> Bridge -> Viewers -> Tests -> Pipeline Doc.', status = 'active', sqlite_backend = 'sqlite' WHERE book_id = 19;

-- Section semantic roles
UPDATE sections SET section_type = 'entry_point_cli' WHERE section_id = 418;
UPDATE sections SET section_type = 'entry_point_python' WHERE section_id = 419;
UPDATE sections SET section_type = 'entry_point_gui' WHERE section_id = 420;
UPDATE sections SET section_type = 'entry_point_tests' WHERE section_id = 421;
UPDATE sections SET section_type = 'entry_point_eyes' WHERE section_id = 422;
UPDATE sections SET section_type = 'file_category_brain' WHERE section_id IN (423,431);
UPDATE sections SET section_type = 'file_category_config' WHERE section_id IN (424,432);
UPDATE sections SET section_type = 'file_category_engine' WHERE section_id IN (425,433);
UPDATE sections SET section_type = 'file_category_graph' WHERE section_id IN (426,434);
UPDATE sections SET section_type = 'file_category_gui' WHERE section_id IN (427,435);
UPDATE sections SET section_type = 'file_category_storage' WHERE section_id IN (428,436);
UPDATE sections SET section_type = 'file_category_test' WHERE section_id IN (429,437);
UPDATE sections SET section_type = 'file_category_unknown' WHERE section_id IN (430,438);

-- Nodes for book 19
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(172, 'tool', 'DomGraphEngine', 'Unified decision graph engine with 40+ Run commands, 1859 lines, 54 methods', 'engine', 0.95, 19, 211),
(173, 'tool', 'Dom_Graph_Ingest', 'MySQL to SQLite graph ingestion script', 'graph', 0.80, 19, 211),
(174, 'tool', 'dom_graph_bridge', 'CLI to JSON bridge for ContextRAM Swift integration', 'bridge', 0.75, 19, 211),
(175, 'tool', 'AgentNode', 'Agent graph engine with 120 methods, auto-discovers architecture from codebase', 'graph', 0.90, 19, 223),
(176, 'tool', 'GraphViewer', 'GUI graph viewer, 409 lines, renders typed-state format graphs', 'gui', 0.60, 19, 212),
(177, 'tool', 'Dom_Graph_Gui', 'DB Architecture GUI with visual graphics, 1836 lines', 'gui', 0.65, 19, 212),
(178, 'tool', 'ir_extractor', 'IR extractor, 1212 lines, 34 methods', 'engine', 0.70, 19, 211),
(179, 'tool', 'Config.py', 'Schema, constants, primitive costs, file registry for Dom_Graph', 'config', 0.75, 19, 211),
(180, 'concept', '8-Graph Pipeline', 'Plan, Spec, Flow, Lifecycle, Dependency, Error, Orchestration, Gap viewers', 'graph', 0.85, 19, 211),
(181, 'concept', 'ContextRAM Integration', 'Swift integration via dom_graph_bridge CLI to JSON', 'bridge', 0.70, 19, 221),
(182, 'tool', '26 Eyes Analysis', 'codegraph_26eyes module for deep graph analysis', 'graph', 0.65, 19, 222),
(183, 'tool', 'EventSourcedMemUnit', 'Version 2 MemUnit, event-driven reasoning state store, 780 lines', 'storage', 0.75, 19, 218),
(184, 'tool', 'MemUnit', 'Reasoning state store for LLM cognitive architecture, 487 lines', 'storage', 0.70, 19, 218),
(185, 'tool', 'MagneticGraph', 'Graph traversal layer v4, 803 lines, traverse/rank/class_graph/callers', 'graph', 0.75, 19, 218),
(186, 'tool', 'GraphBuilder', 'Authority for building all graph types, 820 lines, 33 methods', 'graph', 0.75, 19, 218),
(187, 'tool', 'GraphPhysics', 'Shake-the-bowl simulated annealing for GUI layout, 696 lines', 'graph', 0.60, 19, 218),
(188, 'tool', 'EnergyFieldGraph', 'Dual-state energy field optimizer with signal gradient, 478 lines', 'graph', 0.60, 19, 218),
(189, 'tool', 'GuiAiBrain', 'AI brain that learns GUI layout, 889 lines, 8 layers', 'gui', 0.70, 19, 218),
(190, 'tool', 'ReplayEngine', 'Deterministic replay of event log into in-RAM SQLite, 488 lines', 'engine', 0.65, 19, 218),
(191, 'tool', 'RollbackEngine', 'Append-only rollback, never deletes history, 175 lines', 'engine', 0.60, 19, 218),
(192, 'tool', 'PreExecutionGate', 'Enforces BCL stamp validation before code execution, 388 lines', 'storage', 0.65, 19, 218),
(193, 'tool', 'SnapshotStore', 'Materialized rebuild checkpoints (CACHE not truth), 193 lines', 'storage', 0.60, 19, 218),
(194, 'tool', 'InRamDb', 'In-RAM SQLite working projection for MemUnit event-sourcing, 391 lines', 'storage', 0.70, 19, 218),
(195, 'tool', 'BclStampStore', 'Reasoning layer for MemUnit event-sourcing, BCL stamps, 394 lines', 'storage', 0.65, 19, 218),
(196, 'tool', 'AstNodeRegistry', 'AST node identity registry, immutable node identity, 273 lines', 'storage', 0.65, 19, 218),
(197, 'tool', 'AstVersionStore', 'Versioned AST content store, content-addressed, 227 lines', 'storage', 0.60, 19, 218),
(198, 'tool', 'DependencyEdgeStore', 'Versioned dependency graph edges, 203 lines', 'storage', 0.60, 19, 218),
(199, 'tool', 'EventLogStore', 'Append-only JSON Lines event log on disk, 245 lines', 'storage', 0.60, 19, 218),
(200, 'tool', 'TraceChainStore', 'Deterministic replay trace chains, 192 lines', 'storage', 0.55, 19, 218),
(201, 'tool', 'ContextCompiler', 'Assembles narrative context packets from MemUnit + BCL, 300 lines', 'engine', 0.65, 19, 218),
(202, 'tool', 'ContextReconstructor', 'Version 2 packet builder, reconstructs context from events, 408 lines', 'engine', 0.65, 19, 218),
(203, 'concept', 'VBStyle Compliance', '0 pass, 161 fail — entire domain needs VBStyle remediation', 'compliance', 0.50, 19, 217);

-- Links for book 19
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(92, 172, 173, 'depends_on', 1.0, 'DomGraphEngine depends on ingested data from Dom_Graph_Ingest'),
(93, 172, 174, 'feeds_into', 1.0, 'Engine output bridged to ContextRAM via dom_graph_bridge'),
(94, 174, 181, 'enables', 1.0, 'Bridge enables ContextRAM Swift integration'),
(95, 180, 176, 'rendered_by', 0.8, '8-graph pipeline rendered by GraphViewer and GUI viewers'),
(96, 175, 186, 'uses', 0.8, 'AgentNode uses GraphBuilder for graph construction'),
(97, 183, 184, 'supersedes', 0.9, 'EventSourcedMemUnit v2 supersedes original MemUnit'),
(98, 194, 183, 'hosts', 1.0, 'InRamDb hosts EventSourcedMemUnit event-sourcing'),
(99, 190, 194, 'replays_into', 1.0, 'ReplayEngine replays event log into InRamDb'),
(100, 191, 190, 'complements', 0.8, 'RollbackEngine complements ReplayEngine'),
(101, 192, 195, 'validates', 1.0, 'PreExecutionGate validates BCL stamps from BclStampStore'),
(102, 193, 190, 'checkpoints', 0.8, 'SnapshotStore materializes replay checkpoints'),
(103, 196, 197, 'pairs_with', 0.8, 'AstNodeRegistry pairs with AstVersionStore for identity+content'),
(104, 198, 196, 'references', 0.8, 'DependencyEdgeStore references AstNodeRegistry nodes'),
(105, 199, 190, 'logs_for', 0.8, 'EventLogStore provides log for ReplayEngine'),
(106, 200, 190, 'traces_for', 0.8, 'TraceChainStore provides trace chains for replay verification'),
(107, 201, 183, 'reads_from', 0.8, 'ContextCompiler reads from EventSourcedMemUnit'),
(108, 202, 201, 'supersedes', 0.7, 'ContextReconstructor v2 supersedes ContextCompiler'),
(109, 185, 186, 'uses', 0.7, 'MagneticGraph uses GraphBuilder infrastructure'),
(110, 187, 188, 'related_to', 0.7, 'GraphPhysics and EnergyFieldGraph both optimize layout'),
(111, 189, 187, 'uses', 0.7, 'GuiAiBrain uses GraphPhysics for layout annealing'),
(112, 172, 175, 'dispatches_to', 0.7, 'DomGraphEngine can dispatch to AgentNode graph'),
(113, 179, 172, 'configures', 1.0, 'Config.py configures DomGraphEngine'),
(114, 178, 173, 'feeds', 0.8, 'ir_extractor feeds Dom_Graph_Ingest'),
(115, 182, 172, 'analyzes', 0.7, '26 Eyes analyzes DomGraphEngine output');

-- Glossary terms for book 19
INSERT OR IGNORE INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(82, 'DomGraphEngine', 'Unified decision graph engine with 40+ Run commands for codefix domain', 'tool', 'nodes.source_book_id=19'),
(83, '8-Graph Pipeline', 'Plan, Spec, Flow, Lifecycle, Dependency, Error, Orchestration, Gap graph viewers', 'concept', 'nodes.domain=graph'),
(84, 'EventSourcedMemUnit', 'Version 2 MemUnit with event-driven reasoning state store', 'tool', 'nodes.node_name=EventSourcedMemUnit'),
(85, 'ContextRAM Integration', 'Swift integration via dom_graph_bridge CLI to JSON pipeline', 'bridge', 'nodes.domain=bridge'),
(86, '26 Eyes Analysis', 'Deep graph analysis module for codegraph inspection', 'tool', 'nodes.node_name=26 Eyes Analysis');

-- Glossary links for book 19
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) VALUES
(82, 19, 211, NULL, 'primary'),
(83, 19, 211, NULL, 'primary'),
(84, 19, 218, 425, 'primary'),
(85, 19, 221, NULL, 'primary'),
(86, 19, 222, 422, 'primary');

-- Checks for book 19
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(80, 19, 217, 'VBStyle compliance scan', 'compliance', 'FAIL', '0 pass, 161 fail — entire domain needs remediation'),
(81, 19, 211, 'Pipeline stage coverage', 'structure', 'PASS', 'All 7 stages present: Config, Ingest, Engine, Bridge, Viewers, Tests, Pipeline Doc'),
(82, 19, 213, 'File register completeness', 'structure', 'PASS', '161 files, 157 classes, 2336 methods, 70176 lines catalogued'),
(83, 19, 216, 'Dependency graph integrity', 'structure', 'PASS', 'Boot spine and load order documented');

-- Provenance for book 19
INSERT INTO provenance (provenance_id, source_path, dest_path, dest_type, book_id, notes) VALUES
(19, 'Dom_Graph/ folder scan', 'Plf_DomGraphPipeline.md', 'markdown', 19, 'Auto-generated by turbo scanner 2026-06-28');

-- Pipeline connections for book 19
INSERT INTO pipeline_connections (connection_id, from_book_id, to_book_id, connection_type, description, status) VALUES
(35, 19, 22, 'related', 'Dom_Graph domain breakdown related to graph engine codebase inventory', 'active'),
(36, 19, 23, 'implements', 'Dom_Graph pipeline implements the graph ingestion spec', 'active'),
(37, 19, 28, 'part_of', 'Dom_Graph pipeline is part of the overall pipeline system', 'active');

-- ─── BOOK 22: GraphEngineCodebase ───

-- Book metadata update
UPDATE books SET core_thesis = 'Code asset inventory: graph_computation_units DB with 2407 methods across 224 classes. Coverage assessment vs 21-component spec: 30% exists, 50% partial, 20% missing.', status = 'reference', sqlite_backend = 'mysql+sqlite' WHERE book_id = 22;

-- Section semantic roles
UPDATE sections SET section_type = 'method_inventory' WHERE section_id IN (462,463,464,465,466);
UPDATE sections SET section_type = 'method_inventory' WHERE section_id IN (467,468,469,470,471);

-- Nodes for book 22
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(204, 'database', 'graph_computation_units', 'MySQL DB with computation_units table: 2407 methods, 224 classes, 1 method = 1 row', 'database', 0.95, 22, 236),
(205, 'tool', 'GraphEngine', '66 methods: 8 graph views, graph operations, class management, 20 internal checks, dispatch', 'graph', 0.90, 22, 239),
(206, 'tool', 'AgentGraph', '68 methods: graph building, analysis, simulation, persistence, 27 Run commands', 'graph', 0.95, 22, 240),
(207, 'tool', 'CascadeEngine', '10 methods: Start, NextStage, Stage, Validate, Rewrite, Rules, Commit, Status', 'cascade', 0.70, 22, 241),
(208, 'tool', 'DecisionEngine', '13 methods: Start, Step, End, Auto, ExecuteNode, GetNode, GetEdges, MatchesCondition', 'decision', 0.75, 22, 242),
(209, 'tool', 'GraphViewer', '22 methods: Render, DrawGraph, LayoutNodes, LoadGraph, BuildUI, Show, OnClick, OnResize', 'gui', 0.60, 22, 243),
(210, 'concept', '8-Graph Pipeline Views', 'PlanView, SpecView, FlowView, LifecycleView, DependencyView, ErrorView, OrchestrationView, GapView', 'graph', 0.85, 22, 239),
(211, 'concept', 'Coverage Assessment', '21-component spec: 3 EXISTS, 10 PARTIAL, 8 MISSING = 30% full coverage', 'assessment', 0.85, 22, 253),
(212, 'concept', 'Missing Components', 'LLM Integration, Temporal Model, Truth Tracking, Contradiction Engine, Query Planner, Evidence Builder, Memory Governor, Observation Engine', 'gap', 0.80, 22, 253),
(213, 'class_collection', 'Graph Classes (20)', '20 graph-related classes in vb_code_test: CodeGraph, DomGraph, GraphBrain, GraphStore, ReasoningGraph, etc.', 'graph', 0.75, 22, 244),
(214, 'class_collection', 'Brain/Cognitive Classes (10)', '10 brain classes: CognitiveBrain, DatabaseBrain, GraphBrain, LearningBrain, UltimateCognitiveAI', 'brain', 0.70, 22, 245),
(215, 'class_collection', 'Memory Classes (10)', '10 memory classes: AdaptiveMemory, BracketMemoryStore, LongTermMemory, SessionMemory, MemoryConsolidator', 'memory', 0.70, 22, 246),
(216, 'class_collection', 'Decision Classes (12)', '12 decision classes: DecisionGate, DecisionPlanner, GuiDecisionEngine, RepairDecisionEngine', 'decision', 0.70, 22, 247),
(217, 'class_collection', 'Agent Classes (7)', '7 agent classes: Agent, AgentCore, AgentSwarm, MultiAgentLearning, SSHAgent', 'agent', 0.65, 22, 249),
(218, 'concept', 'Graph Keywords Filter', 'graph, node, edge, cascade, decision, embed, vector, memory, context, brain, cognitive, knowledge, reasoning, semantic, tfidf, cosine, similarity, traverse, adjacency, topology, cluster, community, centrality, pagerank, bfs, dfs, shortest_path, spanning, dag, directed', 'graph', 0.60, 22, 238),
(219, 'concept', 'Source Breakdown', 'local: 1491 units/126 classes, mysql_vb_code_test: 916 units/104 classes = 2407 total', 'database', 0.75, 22, 237);

-- Links for book 22
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(116, 204, 219, 'contains', 1.0, 'graph_computation_units contains both local and mysql sources'),
(117, 205, 210, 'implements', 1.0, 'GraphEngine implements 8-graph pipeline views'),
(118, 206, 205, 'complements', 0.8, 'AgentGraph complements GraphEngine - simulation vs validation'),
(119, 207, 208, 'pairs_with', 0.7, 'CascadeEngine pairs with DecisionEngine for staged decisions'),
(120, 211, 212, 'identifies', 1.0, 'Coverage assessment identifies 8 missing components'),
(121, 213, 204, 'stored_in', 0.8, 'Graph classes stored in graph_computation_units'),
(122, 214, 204, 'stored_in', 0.8, 'Brain classes stored in graph_computation_units'),
(123, 215, 204, 'stored_in', 0.8, 'Memory classes stored in graph_computation_units'),
(124, 216, 204, 'stored_in', 0.8, 'Decision classes stored in graph_computation_units'),
(125, 217, 204, 'stored_in', 0.8, 'Agent classes stored in graph_computation_units'),
(126, 218, 204, 'filters', 1.0, 'Graph keywords filter used to populate computation_units'),
(127, 206, 213, 'uses', 0.7, 'AgentGraph uses graph classes from vb_code_test'),
(128, 205, 213, 'uses', 0.7, 'GraphEngine uses graph classes from vb_code_test'),
(129, 211, 205, 'assesses', 1.0, 'Coverage assessment evaluates GraphEngine capabilities'),
(130, 211, 206, 'assesses', 1.0, 'Coverage assessment evaluates AgentGraph capabilities');

-- Glossary terms for book 22
INSERT OR IGNORE INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(87, 'graph_computation_units', 'MySQL DB: 1 method = 1 row = 1 computation unit, 2407 total across 224 classes', 'database', 'nodes.node_name=graph_computation_units'),
(88, '8-Graph Pipeline Views', 'PlanView, SpecView, FlowView, LifecycleView, DependencyView, ErrorView, OrchestrationView, GapView', 'concept', 'nodes.domain=graph'),
(89, 'Coverage Assessment', '21-component spec evaluation: 30% EXISTS, 50% PARTIAL, 20% MISSING', 'assessment', 'nodes.node_name=Coverage Assessment'),
(90, 'Graph Keywords Filter', '30 keywords used to filter graph-related methods from codebase', 'graph', 'nodes.node_name=Graph Keywords Filter');

-- Glossary links for book 22
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) VALUES
(87, 22, 236, NULL, 'primary'),
(88, 22, 239, 462, 'primary'),
(89, 22, 253, NULL, 'primary'),
(90, 22, 238, NULL, 'primary');

-- Checks for book 22
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(84, 22, 253, '21-component spec coverage', 'assessment', 'PARTIAL', '3 EXISTS, 10 PARTIAL, 8 MISSING = 30% full coverage'),
(85, 22, 236, 'Computation units completeness', 'structure', 'PASS', '2407 units across 224 classes from 2 sources'),
(86, 22, 239, 'GraphEngine method inventory', 'structure', 'PASS', '66 methods catalogued across 5 categories'),
(87, 22, 240, 'AgentGraph method inventory', 'structure', 'PASS', '68 methods catalogued across 5 categories');

-- Provenance for book 22
INSERT INTO provenance (provenance_id, source_path, dest_path, dest_type, book_id, notes) VALUES
(20, 'graph_computation_units.computation_units + vb_code_test.vb_classes + CODEBASE.python_files', 'Plf_GraphEngineCodebase.md', 'markdown', 22, 'Code asset inventory from MySQL databases and local codebase scan');

-- Pipeline connections for book 22
INSERT INTO pipeline_connections (connection_id, from_book_id, to_book_id, connection_type, description, status) VALUES
(38, 22, 19, 'informs', 'Codebase inventory informs Dom_Graph pipeline domain breakdown', 'active'),
(39, 22, 23, 'feeds', 'Codebase inventory feeds graph ingestion spec', 'active'),
(40, 22, 18, 'constrained_by', 'Codebase inventory constrained by storage architecture decisions', 'active'),
(41, 22, 30, 'validated_by', 'Codebase coverage validated by pipeline gap analysis', 'active');
