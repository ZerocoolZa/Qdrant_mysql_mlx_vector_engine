-- === BOOK 17: Database Management (book_id=17) ===
UPDATE books SET core_thesis = 'Comprehensive reference for all databases managed by core/Dom_Unified/ stack. MySQL (truth store), Neo4j (graph), Qdrant (vector), SQLite (local), LMDB (RAM vector). DomSystem is the single lifecycle authority replacing macOS launchd/brew.', sqlite_backend = 'MySQL 8.0.46 + Neo4j + Qdrant + SQLite (multiple .db files) + LMDB/Word2Vec', status = 'ACTIVE' WHERE book_id = 17;

INSERT INTO nodes (node_type, node_name, node_value, domain, source_book_id, source_chapter_id) VALUES
  ('tool', 'DomSystem', 'Service lifecycle authority for MySQL, Neo4j, Qdrant. Replaces macOS launchd/brew. Run() dispatch. Located at core/Dom_Unified/DomSystem.py.', 'db_management', 17, (SELECT chapter_id FROM chapters WHERE book_id=17 AND chapter_title LIKE '%Service%' LIMIT 1)),
  ('database', 'MySQL 8.0.46', 'Primary relational store. Truth Store. Structured records, codebase, classes, methods, chat history, knowledge base, learned rules, BCL tokens, execution logs.', 'db_management', 17, (SELECT chapter_id FROM chapters WHERE book_id=17 AND chapter_title LIKE '%MySQL%' LIMIT 1)),
  ('database', 'Neo4j', 'Graph database. Relationship Store. Graph traversal, causality, identity, evidence chains, node/edge relationships.', 'db_management', 17, (SELECT chapter_id FROM chapters WHERE book_id=17 AND chapter_title LIKE '%Neo4j%' LIMIT 1)),
  ('database', 'Qdrant', 'Vector database. Meaning Store. Vector embeddings, semantic similarity, nearest-neighbor retrieval, context activation.', 'db_management', 17, (SELECT chapter_id FROM chapters WHERE book_id=17 AND chapter_title LIKE '%Qdrant%' LIMIT 1)),
  ('database', 'SQLite', 'Local store. Per-domain work databases, in-RAM execution buses, caches, pipeline state. File-based, no process management.', 'db_management', 17, (SELECT chapter_id FROM chapters WHERE book_id=17 AND chapter_title LIKE '%SQLite%' LIMIT 1)),
  ('database', 'LMDB + Word2Vec', 'RAM vector store. Word2Vec embeddings, full model tensors, real-time ANN similarity search, incremental training updates.', 'db_management', 17, (SELECT chapter_id FROM chapters WHERE book_id=17 AND chapter_title LIKE '%LMDB%' LIMIT 1)),
  ('concept', '4+1 Database Stack', 'MySQL (Truth) + Neo4j (Graph) + Qdrant (Meaning) + SQLite (Local) + LMDB (RAM Vector). DomSystem manages all lifecycle.', 'db_management', 17, (SELECT chapter_id FROM chapters WHERE book_id=17 AND chapter_title LIKE '%Architecture%' LIMIT 1));

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'manages', 1.0, 'DomSystem manages MySQL lifecycle'
  FROM nodes n1, nodes n2 WHERE n1.node_name='DomSystem' AND n2.node_name='MySQL 8.0.46' AND n1.source_book_id=17;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'manages', 1.0, 'DomSystem manages Neo4j lifecycle'
  FROM nodes n1, nodes n2 WHERE n1.node_name='DomSystem' AND n2.node_name='Neo4j' AND n1.source_book_id=17;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'manages', 1.0, 'DomSystem manages Qdrant lifecycle'
  FROM nodes n1, nodes n2 WHERE n1.node_name='DomSystem' AND n2.node_name='Qdrant' AND n1.source_book_id=17;

UPDATE binary_artifacts SET artifact_name = 'none (reference document)', artifact_type = 'none', source_language = 'none', source_code = 'Reference document for 4+1 database stack. No compilable code.', compile_command = '', compile_status = 'NOT_APPLICABLE', file_size_bytes = 0 WHERE book_id = 17;

UPDATE checks SET check_name = '4plus1_stack_complete', check_type = 'completeness_check', check_status = 'PASSING', check_result = 'All 5 databases operational: MySQL, Neo4j, Qdrant, SQLite, LMDB. DomSystem manages 3 process-based (MySQL/Neo4j/Qdrant), 2 file-based (SQLite/LMDB).' WHERE book_id = 17;

INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes) SELECT file_path, 'pipelines_library.db:books.book_id=17', 'sqlite', file_hash, 17, 'Full markdown ingested (3066 lines). 7 nodes, 3 links, 1 check. 26-chapter reference manual. 4+1 database stack documented.' FROM books WHERE book_id = 17;

-- === BOOK 20: Dom_Mcp Migration (book_id=20) ===
UPDATE books SET core_thesis = 'Consolidate all MCP servers into native Go binaries under Dom_Mcp/. Source code stored in SQLite DB (go_mcp_store.db). No Node.js, no npx, no Docker. 9 Go MCP servers, unified dom_mcp binary: 30 tools, 11 MB RAM. Total savings: ~226 MB.', sqlite_backend = 'go_mcp_store.db (269 files, 42784 lines of Go source)', status = 'ACTIVE' WHERE book_id = 20;

INSERT INTO nodes (node_type, node_name, node_value, domain, source_book_id, source_chapter_id) VALUES
  ('tool', 'dom_mcp (unified binary)', 'Unified Go MCP binary. 17 MB, 11 MB RAM, 30 tools from 6 modules. Replaces ~280 MB of Node.js MCP processes.', 'dom_mcp', 20, (SELECT chapter_id FROM chapters WHERE book_id=20 AND chapter_title LIKE '%PHASE 4%' LIMIT 1)),
  ('tool', 'sqlite-go-mcp', 'Go MCP for SQLite. 18 MB binary, 14 MB RAM, 5 tools. Replaces Docker devin-sqlite (100 MB).', 'dom_mcp', 20, (SELECT chapter_id FROM chapters WHERE book_id=20 AND chapter_title LIKE '%PHASE 4%' LIMIT 1)),
  ('tool', 'memory-go-mcp', 'Go MCP for memory. 19 MB binary, 10 MB RAM, 13 tools. Replaces npx memory (40 MB).', 'dom_mcp', 20, (SELECT chapter_id FROM chapters WHERE book_id=20 AND chapter_title LIKE '%PHASE 4%' LIMIT 1)),
  ('tool', 'pinecone-custom-mcp', 'Custom Go MCP for Pinecone. 11 MB binary, 1.3 MB idle RAM, 9 tools. Replaces npx pinecone (40-70 MB).', 'dom_mcp', 20, (SELECT chapter_id FROM chapters WHERE book_id=20 AND chapter_title LIKE '%PHASE 4%' LIMIT 1)),
  ('tool', 'taskplanner-custom-mcp', 'Custom Go MCP for taskplanner. 8.2 MB binary, 11 MB RAM, 7 tools. Replaces Node.js taskplanner (50 MB).', 'dom_mcp', 20, (SELECT chapter_id FROM chapters WHERE book_id=20 AND chapter_title LIKE '%PHASE 4%' LIMIT 1)),
  ('tool', 'contextram-go-mcp', 'Go shim for ContextRAM. 8.2 MB binary, 11 MB RAM, 27 tools. Wraps Swift context engine.', 'dom_mcp', 20, (SELECT chapter_id FROM chapters WHERE book_id=20 AND chapter_title LIKE '%PHASE 4%' LIMIT 1)),
  ('database', 'go_mcp_store.db', 'SQLite DB storing all Go MCP source code. 269 files, 42784 lines. API: go_mcp_store.py (GoMcpStore class).', 'dom_mcp', 20, (SELECT chapter_id FROM chapters WHERE book_id=20 AND chapter_title LIKE '%SQLite%' LIMIT 1)),
  ('process', 'MCP migration Phase 4', 'All 6 Go MCP binaries built and tested. MCP protocol PASS for all. RAM: 11 MB unified vs ~280 MB Node.js combined. Savings: ~226 MB.', 'dom_mcp', 20, (SELECT chapter_id FROM chapters WHERE book_id=20 AND chapter_title LIKE '%PHASE 4%' LIMIT 1));

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'unifies', 1.0, 'dom_mcp unified binary combines all 6 Go MCP modules'
  FROM nodes n1, nodes n2 WHERE n1.node_name='dom_mcp (unified binary)' AND n2.node_name='sqlite-go-mcp' AND n1.source_book_id=20;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'stores_in', 1.0, 'All Go MCP source stored in go_mcp_store.db'
  FROM nodes n1, nodes n2 WHERE n1.node_name='dom_mcp (unified binary)' AND n2.node_name='go_mcp_store.db' AND n1.source_book_id=20;

UPDATE binary_artifacts SET artifact_name = '6 Go MCP binaries', artifact_type = 'native_go_binaries', source_language = 'Go', source_code = '9 Go MCP servers in SQLite DB (269 files, 42784 lines). Binaries: dom_mcp (17MB), sqlite-go (18MB), memory-go (19MB), pinecone (11MB), taskplanner (8.2MB), contextram (8.2MB)', compile_command = 'go build -o dom_mcp', compile_status = 'COMPILED_WORKING', file_size_bytes = 0 WHERE book_id = 20;

UPDATE checks SET check_name = 'mcp_protocol_all_pass', check_type = 'functional_verification', check_status = 'PASSING', check_result = 'All 6 Go MCP binaries PASS MCP protocol (initialize + tools/list). dom_mcp: 30 tools, sqlite: 5, memory: 13, pinecone: 9, taskplanner: 7, contextram: 27.' WHERE book_id = 20;
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 20, (SELECT chapter_id FROM chapters WHERE book_id=20 AND chapter_title LIKE '%PHASE 4%' LIMIT 1), 'ram_savings_226mb', 'performance_verification', 'PASSING', 'Total RAM: 11 MB unified vs ~280 MB Node.js. Savings: ~226 MB. pinecone: 1.3 MB idle vs 40-70 MB npx.';
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 20, (SELECT chapter_id FROM chapters WHERE book_id=20 AND chapter_title LIKE '%PHASE 5%' LIMIT 1), 'ide_cutover', 'implementation_status', 'NOT_STARTED', 'Phase 5 IDE cutover not started. Kilo first, Devin second, Cascade last.';

INSERT OR IGNORE INTO glossary_terms (term, definition, sqlite_mapping) VALUES
  ('dom_mcp', 'Unified Go MCP binary. 30 tools from 6 modules, 11 MB RAM. Replaces ~280 MB of Node.js MCP processes. Savings: ~226 MB.', 'go_mcp_store.db');

INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes) SELECT file_path, 'pipelines_library.db:books.book_id=20', 'sqlite', file_hash, 20, 'Full markdown ingested (146 lines). 8 nodes, 2 links, 3 checks, 1 glossary term. 6 Go MCP binaries built. Phase 4 complete, Phase 5 (IDE cutover) not started.' FROM books WHERE book_id = 20;

-- === BOOK 21: Error Capture Pipeline (book_id=21) ===
UPDATE books SET core_thesis = 'Every error is a lesson. When code fails, the error is captured into a database with cause, solution, and frequency. Next time same error pattern appears, system already knows the fix. Errors become data. Data prevents errors.', sqlite_backend = 'MySQL vb_shared (learned_rules: 10590, know_problems: 309, know_solutions: 362, error_knowledge: 70, governance: 58, rule_tokens: 238) + SQLite (unified_cache.db, error_log.db, error_handler.db)', status = 'ACTIVE' WHERE book_id = 21;

INSERT INTO nodes (node_type, node_name, node_value, domain, source_book_id, source_chapter_id) VALUES
  ('tool', 'ErrorCapture.py', 'Capture engine. Commands: capture, capture_batch, query, top_errors, prevent, stats. Runs during AST parsing. Located at core/Dom_Unified/.', 'error_capture', 21, (SELECT chapter_id FROM chapters WHERE book_id=21 AND chapter_title LIKE '%Components%' LIMIT 1)),
  ('tool', 'CacheDb.py', 'SQLite storage for AST cache + error knowledge. Keyed by file_path + mtime. capture_error, query_errors. Located at core/Dom_Unified/.', 'error_capture', 21, (SELECT chapter_id FROM chapters WHERE book_id=21 AND chapter_title LIKE '%Components%' LIMIT 1)),
  ('tool', 'error_tracker.py', 'MySQL learned_rules/know_problems/know_solutions query engine. Commands: search, lookup_problem, lookup_solution, record, save_lesson, recall, match. Located at core/utility/.', 'error_capture', 21, (SELECT chapter_id FROM chapters WHERE book_id=21 AND chapter_title LIKE '%Components%' LIMIT 1)),
  ('tool', 'error_handler.py', 'Runtime error handler. Capture, classify (info/warning/error/critical), recover (ignore/retry/rollback/fallback/circuit_break), retry with backoff, circuit breaker, learn. Located at core/utility/.', 'error_capture', 21, (SELECT chapter_id FROM chapters WHERE book_id=21 AND chapter_title LIKE '%Components%' LIMIT 1)),
  ('tool', 'impl_governance.py', 'Governance engine. Policies, rules, approvals, reviews, violations, waivers. 13 commands. Located at code_store_variations/.', 'error_capture', 21, (SELECT chapter_id FROM chapters WHERE book_id=21 AND chapter_title LIKE '%Components%' LIMIT 1)),
  ('database', 'learned_rules (MySQL)', '10590 rules. Pattern to fix_action with confidence. Columns: pattern, trigger_condition, fix_action, language, category, severity, success_count, failure_count, confidence, source.', 'error_capture', 21, (SELECT chapter_id FROM chapters WHERE book_id=21 AND chapter_title LIKE '%Tier 2%' LIMIT 1)),
  ('database', 'know_problems + know_solutions', '309 known problems + 362 solutions. Problem-solution chain with weight and auto_apply flag. 5 solutions have auto_apply=1.', 'error_capture', 21, (SELECT chapter_id FROM chapters WHERE book_id=21 AND chapter_title LIKE '%Tier 2%' LIMIT 1)),
  ('concept', 'Two Storage Tiers', 'Tier 1: SQLite (local, fast, session-level) - unified_cache.db, error_log.db, error_handler.db. Tier 2: MySQL (global, shared, cross-session) - vb_shared with 6 tables.', 'error_capture', 21, (SELECT chapter_id FROM chapters WHERE book_id=21 AND chapter_title LIKE '%Two%' LIMIT 1)),
  ('concept', 'Prevention hints', 'Built-in for each VBStyle rule: no_type_hints, no_decorators, no_print_outside_main, must_return_tuple3, must_have_run, no_self_underscore, ghost_tag, vbstyle_tag.', 'error_capture', 21, (SELECT chapter_id FROM chapters WHERE book_id=21 AND chapter_title LIKE '%Components%' LIMIT 1));

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'writes_to', 1.0, 'ErrorCapture writes to CacheDb SQLite'
  FROM nodes n1, nodes n2 WHERE n1.node_name='ErrorCapture.py' AND n2.node_name='CacheDb.py' AND n1.source_book_id=21;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'queries', 1.0, 'error_tracker.py queries MySQL learned_rules and know_problems/solutions'
  FROM nodes n1, nodes n2 WHERE n1.node_name='error_tracker.py' AND n2.node_name='learned_rules (MySQL)' AND n1.source_book_id=21;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'queries', 1.0, 'error_tracker.py queries know_problems + know_solutions'
  FROM nodes n1, nodes n2 WHERE n1.node_name='error_tracker.py' AND n2.node_name='know_problems + know_solutions' AND n1.source_book_id=21;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'uses', 1.0, 'error_handler.py uses error_tracker.py for MySQL lookups'
  FROM nodes n1, nodes n2 WHERE n1.node_name='error_handler.py' AND n2.node_name='error_tracker.py' AND n1.source_book_id=21;

UPDATE binary_artifacts SET artifact_name = 'vbast C binary + Python tools', artifact_type = 'mixed_c_python', source_language = 'C+Python', source_code = 'Cascade_toolStack/vbast/vbast (C binary for AST parsing) + ErrorCapture.py, CacheDb.py, error_tracker.py, error_handler.py, impl_governance.py', compile_command = 'cc -O2 -o vbast vbast.c -lsqlite3', compile_status = 'COMPILED_WORKING', file_size_bytes = 0 WHERE book_id = 21;

UPDATE checks SET check_name = 'mysql_kb_10590_rules', check_type = 'completeness_check', check_status = 'PASSING', check_result = 'learned_rules: 10590. know_problems: 309. know_solutions: 362. error_knowledge: 70. governance: 58. rule_tokens: 238.' WHERE book_id = 21;
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 21, (SELECT chapter_id FROM chapters WHERE book_id=21 AND chapter_title LIKE '%Current%' LIMIT 1), 'auto_apply_partial', 'implementation_status', 'PARTIAL', '5 solutions have auto_apply=1. Cross-domain code import NOT BUILT.';
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 21, (SELECT chapter_id FROM chapters WHERE book_id=21 AND chapter_title LIKE '%Current%' LIMIT 1), 'all_components_done', 'completeness_check', 'PASSING', 'All 5 components DONE: ErrorCapture, CacheDb, ErrorTracker, ErrorHandler, DomGovernance. vbast C binary DONE.';

INSERT OR IGNORE INTO glossary_terms (term, definition, sqlite_mapping) VALUES
  ('ErrorCapture', 'Capture engine for VBStyle violations during AST parsing. Commands: capture, query, top_errors, prevent. Located at core/Dom_Unified/ErrorCapture.py.', 'unified_cache.db error_knowledge table'),
  ('learned_rules', 'MySQL vb_shared table. 10590 rules with pattern, fix_action, confidence, success/failure counts. Cross-session error knowledge.', 'vb_shared.learned_rules'),
  ('ErrorHandler', 'Runtime error handler. Capture, classify, recover (retry/rollback/fallback/circuit_break), learn. Wraps every Tuple3 result.', 'error_handler.db');

INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes) SELECT file_path, 'pipelines_library.db:books.book_id=21', 'sqlite', file_hash, 21, 'Full markdown ingested (382 lines). 9 nodes, 4 links, 3 checks, 3 glossary terms. 5 components. 2 storage tiers. 5 scenarios documented. MySQL KB: 10590 rules, 309 problems, 362 solutions.' FROM books WHERE book_id = 21;
INSERT INTO pipeline_connections (from_book_id, to_book_id, connection_type, description, status) VALUES (21, 11, 'feeds_into', 'CLI Safe Execution queries Error Capture learned_rules on failure', 'ACTIVE');
INSERT INTO pipeline_connections (from_book_id, to_book_id, connection_type, description, status) VALUES (21, 2, 'related_to', 'Always Learning pipeline uses same learned_rules for confidence-gated updates', 'ACTIVE');
