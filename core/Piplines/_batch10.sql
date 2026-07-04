-- Batch 10: Books 33 (Provenance), 34 (ScratchingMyHead), 35 (SessionGraph)
-- Starting IDs: nodes=411, links=325, glossary=128, checks=130, provenance=31, connections=77

-- ============================================================
-- BOOK 33: Provenance Pipeline — Search, Report, Copy, Track
-- ============================================================

UPDATE books SET core_thesis = 'Unifies search, report, copy, and provenance tracking for files and code. 5 stages: SEARCH, REPORT, COPY, PROVENANCE, VERIFY. SQLite schema with provenance and file_store tables. Integrates with Dom_Unified package (UnifiedAst, CacheDb, ErrorCapture, DatabaseManager, ConfigCascade, DomReport).', status = 'active', sqlite_backend = 'sqlite' WHERE book_id = 33;

-- Nodes for book 33 (chapters 387-392)
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(411, 'concept', 'Provenance Pipeline', 'Unifies search, report, copy, and provenance tracking for files and code. 5 stages: SEARCH, REPORT, COPY, PROVENANCE, VERIFY. DomReport class is the entry point.', 'pipeline', 0.90, 33, 387),
(412, 'stage', 'SEARCH', 'Find files matching a pattern. Uses glob + os.walk. Returns list of matching file paths with metadata.', 'pipeline', 0.75, 33, 388),
(413, 'stage', 'REPORT', 'Generate markdown report from search results. Lists files found with paths, sizes, and hashes.', 'pipeline', 0.70, 33, 388),
(414, 'stage', 'COPY', 'Copy files to destination. Three modes: copy_to_file (combine sources into one file), copy_to_dir (copy files preserving structure), copy_to_sqlite (store file content in SQLite file_store table).', 'pipeline', 0.80, 33, 388),
(415, 'stage', 'PROVENANCE', 'Query provenance chain for any file. Records source_path, dest_path, source_hash, dest_hash, file_size, copied_at. Enables tracing where any copied file came from.', 'pipeline', 0.85, 33, 388),
(416, 'stage', 'VERIFY', 'Check that copied files still match their original hashes. Returns total, verified, mismatches, missing, integrity status.', 'pipeline', 0.80, 33, 388),
(417, 'schema', 'provenance table', 'id, source_path, dest_path, dest_type (file/folder/sqlite), source_hash, dest_hash, file_size, copied_at, file_store_id (FK to file_store)', 'database', 0.75, 33, 389),
(418, 'schema', 'file_store table', 'id, source_path, file_name, file_size, source_hash, content (TEXT if include_content=True), stored_at', 'database', 0.70, 33, 389),
(419, 'class', 'DomReport', 'VBStyle class with Run() dispatch. Commands: search, report, copy_to_file, copy_to_dir, copy_to_sqlite, provenance, list_copies, verify_lineage. Standard __init__(self, mem=None, db=None, param=None), self.state dict, Tuple3 returns.', 'code', 0.85, 33, 390),
(420, 'concept', 'Dom_Unified Integration', 'DomReport integrates with UnifiedAst (parse before copy), CacheDb (cache AST results), ErrorCapture (capture violations), DatabaseManager (MySQL provenance), ConfigCascade (generate configs for copied code).', 'architecture', 0.75, 33, 391);

-- Links for book 33
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(325, 411, 412, 'stage_1', 1.0, 'SEARCH is first stage'),
(326, 411, 413, 'stage_2', 1.0, 'REPORT is second stage'),
(327, 411, 414, 'stage_3', 1.0, 'COPY is third stage'),
(328, 411, 415, 'stage_4', 1.0, 'PROVENANCE is fourth stage'),
(329, 411, 416, 'stage_5', 1.0, 'VERIFY is fifth stage'),
(330, 415, 417, 'stored_in', 1.0, 'Provenance records in provenance table'),
(331, 414, 418, 'stores_in', 0.8, 'copy_to_sqlite stores in file_store table'),
(332, 419, 411, 'implements', 1.0, 'DomReport implements the pipeline'),
(333, 420, 419, 'integrates_with', 0.7, 'Dom_Unified components use DomReport');

-- Glossary terms for book 33
INSERT INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(128, 'Provenance Chain', 'Sequence of records tracking where a file was copied from, its hash, and destination. Enables full lineage tracing.', 'pipeline', 'nodes.node_name = "PROVENANCE"'),
(129, 'File Store', 'SQLite table storing file content with source path, hash, and metadata. Used by copy_to_sqlite command.', 'database', 'nodes.node_name = "file_store table"');

-- Glossary links for book 33
INSERT INTO glossary_links (term_id, book_id, chapter_id, link_type) VALUES
(128, 33, 388, 'defines'),
(129, 33, 389, 'defines');

-- Checks for book 33
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(130, 33, 392, 'VBStyle: __init__ signature', 'compliance', 'PASS', 'Standard __init__(self, mem=None, db=None, param=None)'),
(131, 33, 392, 'VBStyle: Run() dispatch', 'compliance', 'PASS', 'Run(self, command, params=None) present'),
(132, 33, 392, 'VBStyle: Tuple3 returns', 'compliance', 'PASS', 'All methods return (1, data, None) or (0, None, (code, desc, 0))'),
(133, 33, 392, 'VBStyle: No print, no decorators', 'compliance', 'PASS', 'No print(), no @property, no @staticmethod');

-- Provenance for book 33
INSERT INTO provenance (provenance_id, source_path, dest_path, dest_type, source_hash, book_id, notes) VALUES
(31, 'core/Dom_Unified/DomReport.py', 'core/Piplines/Plf_ProvenancePipeline.md', 'markdown', NULL, 33, 'Pipeline documentation derived from DomReport implementation');

-- Pipeline connections for book 33
INSERT INTO pipeline_connections (connection_id, from_book_id, to_book_id, connection_type, description, status) VALUES
(77, 33, 36, 'related_to', 'Provenance pipeline uses DomIndexer for file indexing before copy', 'active'),
(78, 33, 5, 'related_to', 'Provenance pipeline uses ErrorCapture for violation detection during search', 'active');

-- ============================================================
-- BOOK 34: Scratching My Head — MemUnit + Dom_ Composition Ideas
-- ============================================================

UPDATE books SET core_thesis = 'MemUnit as composition root for domain modules (Dom_IO, Dom_DB, Dom_Graph, etc.). Recursive dispatch via Run(). Capability-based runtime system, not OOP class hierarchies. 3-layer architecture: MemUnit (substrate) -> DomX (capability domains) -> Methods. Devin built C implementation: 6 files, 1672 lines, 3 domains, all tests pass. MEM_Complete_System.py is the original OS architecture spec with 35 classes.', status = 'architecture', sqlite_backend = 'sqlite+mysql' WHERE book_id = 34;

-- Nodes for book 34 (chapters 393-431)
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(421, 'concept', 'MemUnit Composition Root', 'MemUnit as the single composition root for all domain modules. Each Dom_ class is itself a MemUnit with its own self.state. Domains communicate via Run() calls, never direct access. Read shared state directly, write through domain Run().', 'architecture', 0.95, 34, 393),
(422, 'concept', 'Recursive Dispatch', 'Run() dispatch is recursive. Parent MemUnit dispatches to child Dom_ which dispatches to methods. Each level has its own ACTIONS schema and _CommandToMethod mapping. BCL input/output contracts enforced at every level.', 'architecture', 0.90, 34, 395),
(423, 'concept', '3-Layer Architecture', 'Layer 1: MemUnit (substrate) — execution, IO, SQLite/RAM/DB access, dispatch routing (BCL), hardware abstraction. Layer 2: DomX (capability domains) — DomGraph, DomMemory, DomSearch, DomAi, DomIO/DomSystem. Layer 3: Methods inside domains — classify, search, resolve, log, index.', 'architecture', 0.90, 34, 406),
(424, 'concept', 'Domain Isolation', 'Each Dom_ has its own self.state, own ACTIONS. Cannot see parent state unless parent passes params through Run(). Domain-internal state never accessible to other domains. Read shared state directly (fast), write through domain Run() (enforces boundary).', 'architecture', 0.85, 34, 404),
(425, 'concept', 'Shared State Mechanism', 'self.state["identity"], self.state["memory"], self.state["graph"] are explicitly shared. Any domain can READ them. Writes go through owning domain Run(). This is the isolation boundary.', 'architecture', 0.80, 34, 404),
(426, 'concept', 'Domain-Partitioned Execution Kernel', 'The real system name. Not OOP, not microservices, not ECS. A domain-partitioned execution kernel with graph-aware memory. MemUnit is the runtime kernel beneath all domains.', 'architecture', 0.85, 34, 409),
(427, 'concept', 'Cross-Domain Coordination Graph', 'Missing piece. Prevents DomSearch duplicating DomGraph logic, DomMemory leaking into DomLogging, DomAi bypassing DomSystem rules. MemUnit as enforcement + routing authority.', 'architecture', 0.75, 34, 412),
(428, 'concept', 'Devin C Implementation', '6 files, 1672 lines. cascade_toolstack.h (791 lines), memunit.c (290 lines), dom_io.c (130 lines), dom_gpu.c (125 lines), dom_db.c (196 lines), tree_test.c (140 lines). All 3 domains compile, 6 tests pass. Real BCL parser, real ResultsBus (in-RAM SQLite), real domain isolation.', 'implementation', 0.85, 34, 416),
(429, 'concept', 'ResultsBus', 'Central in-RAM SQLite results table. All domains write results to one table. 6 results: DOM_IO.WRITE, DOM_IO.READ, GPU.EXEC, GPU.OPT, DB.STORE, DB.QUERY. MemUnit handles all results writing.', 'implementation', 0.80, 34, 420),
(430, 'concept', 'MEM_Complete_System.py', 'Original OS architecture spec. 1566 lines, 35 classes. MemUnit is gravity center owning MemDB, MemBus, GuiDB, GuiBus. 11-step boot chain. In-RAM SQLite as runtime truth. AI repair built in (Core_ai_fix). GUI from database (GuiDB). Core_orchestrator assembles from [Orc] bracket blocks.', 'architecture', 0.90, 34, 423),
(431, 'concept', 'Boot Chain', '11-step: MemUnit -> core_config -> Core_os -> Core_hw -> Core_io -> Core_ast -> Core_brackets -> Core_rules -> Core_error -> Core_report -> Core_output. Each step depends on previous.', 'architecture', 0.75, 34, 423),
(432, 'concept', 'Controlled Recovery', '9-step: Freeze affected state -> Inspect fault context -> Iteratively attempt fixes -> Validate each fix -> Test each fix -> Write approved fix back -> Update fault/repair state -> Release freeze -> Continue execution.', 'architecture', 0.75, 34, 423),
(433, 'concept', 'Bracket Grammar Operators', 'Operators: >> (emit/flow right), << (pull/flow left), + (merge/combine), | (sibling/separator), : (bind/assign), = (define/equals). Containers: {} (container block), [] (packet block), () (group block). Tokens: , (list separator), ; (end terminator).', 'language', 0.70, 34, 427),
(434, 'concept', 'DOM Explosion Risk', 'If domains grow without constraint: DomX becomes mini-systems, duplication across domains, logic divergence (same function in 3 domains). Need MemUnit as enforcement + routing authority + cross-domain coordination graph.', 'risk', 0.65, 34, 411);

-- Links for book 34
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(334, 421, 422, 'enables', 1.0, 'Composition root enables recursive dispatch'),
(335, 421, 423, 'defines', 1.0, '3-layer architecture from composition root'),
(336, 423, 424, 'enforces', 1.0, '3-layer architecture enforces domain isolation'),
(337, 424, 425, 'complements', 1.0, 'Isolation + shared state = complete boundary'),
(338, 421, 426, 'is_called', 0.8, 'Composition root is the execution kernel'),
(339, 426, 427, 'needs', 0.7, 'Execution kernel needs cross-domain coordination'),
(340, 428, 421, 'implements', 1.0, 'Devin C tree implements MemUnit composition root'),
(341, 428, 429, 'uses', 1.0, 'C implementation uses ResultsBus'),
(342, 430, 421, 'originates_from', 0.9, 'MEM_Complete_System.py is original spec for MemUnit'),
(343, 430, 431, 'defines', 1.0, 'MEM_Complete_System defines 11-step boot chain'),
(344, 430, 432, 'defines', 1.0, 'MEM_Complete_System defines controlled recovery'),
(345, 430, 433, 'defines', 0.8, 'MEM_Complete_System defines bracket grammar'),
(346, 434, 427, 'motivates', 0.7, 'DOM explosion risk motivates cross-domain coordination');

-- Glossary terms for book 34
INSERT INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(130, 'Composition Root', 'MemUnit as the single entry point that composes all domain modules. Domains are isolated executors, MemUnit is the shared substrate.', 'architecture', 'nodes.node_name = "MemUnit Composition Root"'),
(131, 'Domain Isolation', 'Each Dom_ class has its own self.state and cannot see parent state unless params passed through Run(). Read shared state directly, write through domain Run().', 'architecture', 'nodes.node_name = "Domain Isolation"'),
(132, 'ResultsBus', 'Central in-RAM SQLite table where all domains write execution results. MemUnit handles all results writing — domains never write results directly.', 'implementation', 'nodes.node_name = "ResultsBus"'),
(133, 'Gravity Center', 'MemUnit is the first gravity center — everything meaningful routes through memory. Owns MemDB, MemBus, GuiDB, GuiBus.', 'architecture', 'nodes.node_value LIKE "%gravity center%"');

-- Glossary links for book 34
INSERT INTO glossary_links (term_id, book_id, chapter_id, link_type) VALUES
(130, 34, 393, 'defines'),
(131, 34, 404, 'defines'),
(132, 34, 420, 'defines'),
(133, 34, 423, 'defines');

-- Checks for book 34
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(134, 34, 416, 'Devin C: 6 files compile', 'compilation', 'PASS', 'All 6 C files compile successfully'),
(135, 34, 417, 'Devin C: 6 tests pass', 'test', 'PASS', 'DOM_IO.WRITE, DOM_IO.READ, GPU.EXEC, GPU.OPT, DB.STORE, DB.QUERY all pass'),
(136, 34, 422, 'Devin C: What This Proves', 'verification', 'PASS', 'Capability-based runtime in C with real BCL parser, real results bus, real domain isolation'),
(137, 34, 423, 'MEM_Complete_System: 35 classes inventoried', 'inventory', 'PASS', '35 classes from MemUnit to Core_code_hunter catalogued'),
(138, 34, 431, 'Boot chain: 11 steps defined', 'specification', 'PASS', 'MemUnit through Core_output, each step depends on previous');

-- Provenance for book 34
INSERT INTO provenance (provenance_id, source_path, dest_path, dest_type, source_hash, book_id, notes) VALUES
(32, '/Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/Prj_testbed/AA_MEMORIES/MEM_Complete_System.py', 'core/Piplines/Plf_ScratchingMyHead.md', 'markdown', NULL, 34, 'MEM_Complete_System.py is the original 1566-line OS architecture spec analyzed in this book'),
(33, 'Cascade_toolStack/bcl_units/cascade_toolstack.h', 'core/Piplines/Plf_ScratchingMyHead.md', 'markdown', NULL, 34, 'Devin C implementation header file (791 lines) referenced in book');

-- Pipeline connections for book 34
INSERT INTO pipeline_connections (connection_id, from_book_id, to_book_id, connection_type, description, status) VALUES
(79, 34, 33, 'related_to', 'MemUnit composition root relates to Provenance pipeline DomReport class', 'active'),
(80, 34, 36, 'related_to', 'MemUnit substrate relates to Utilities pipeline orchestrator pattern', 'active'),
(81, 34, 39, 'related_to', '8-Graph workflow can reason about MemUnit 3-layer architecture', 'active');

-- ============================================================
-- BOOK 35: Session Graph — Path Tracker
-- ============================================================

UPDATE books SET core_thesis = 'Tracks a session path including main threads, distractions, dead ends, and completion states. Enables resuming work without losing context. Session graph schema for future sessions. Example session: 2026-06-28 Dom_Mcp Migration + Distractions.', status = 'active', sqlite_backend = 'sqlite' WHERE book_id = 35;

-- Nodes for book 35 (chapters 432-434)
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(435, 'concept', 'Session Graph', 'Tracks a session path: main threads, distractions, dead ends, completion states, resume points. Enables resuming work without losing context. A graph of where the session went and what it accomplished.', 'tracking', 0.85, 35, 432),
(436, 'concept', 'Main Thread', 'The primary task or objective of a session. In example: Dom_Mcp Migration. The session graph tracks when the main thread is active vs when distractions pull away.', 'tracking', 0.75, 35, 432),
(437, 'concept', 'Distractions', 'Tasks or side-quests that pull away from the main thread. Tracked in session graph to understand context switching and time allocation. In example: multiple distractions during Dom_Mcp migration.', 'tracking', 0.65, 35, 432),
(438, 'concept', 'Completion State', 'Whether a task in the session was completed, abandoned, or deferred. Tracked per node in the session graph.', 'tracking', 0.70, 35, 432),
(439, 'concept', 'Resume Point', 'Point in the session graph where work can be resumed. Records the state, context, and next steps needed to continue.', 'tracking', 0.80, 35, 432),
(440, 'concept', 'Session Graph Schema', 'Proposed schema for future sessions. Nodes = tasks/states, Edges = transitions between tasks. Attributes: thread_type (main/distraction), status (active/completed/abandoned/deferred), timestamp, context.', 'schema', 0.75, 35, 433);

-- Links for book 35
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(347, 435, 436, 'tracks', 1.0, 'Session graph tracks main thread'),
(348, 435, 437, 'tracks', 0.8, 'Session graph tracks distractions'),
(349, 435, 438, 'tracks', 1.0, 'Session graph tracks completion states'),
(350, 435, 439, 'enables', 1.0, 'Session graph enables resume points'),
(351, 440, 435, 'formalizes', 0.8, 'Schema formalizes the session graph concept');

-- Glossary terms for book 35
INSERT INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(134, 'Session Graph', 'Graph tracking a work session path: main threads, distractions, dead ends, completion states, and resume points', 'tracking', 'nodes.node_name = "Session Graph"'),
(135, 'Resume Point', 'Recorded point in a session where work can be resumed, including state, context, and next steps', 'tracking', 'nodes.node_name = "Resume Point"');

-- Glossary links for book 35
INSERT INTO glossary_links (term_id, book_id, chapter_id, link_type) VALUES
(134, 35, 432, 'defines'),
(135, 35, 432, 'defines');

-- Checks for book 35
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(139, 35, 432, 'Example session documented', 'documentation', 'PASS', '2026-06-28 Dom_Mcp Migration session with distractions tracked'),
(140, 35, 433, 'Session graph schema proposed', 'schema', 'PASS', 'Schema with nodes (tasks/states), edges (transitions), attributes (thread_type, status, timestamp)');

-- Pipeline connections for book 35
INSERT INTO pipeline_connections (connection_id, from_book_id, to_book_id, connection_type, description, status) VALUES
(82, 35, 39, 'related_to', 'Session graph can use 8-Graph workflow for reasoning about session state', 'active'),
(83, 35, 34, 'related_to', 'Session graph relates to MemUnit state tracking via self.state dict', 'active');
