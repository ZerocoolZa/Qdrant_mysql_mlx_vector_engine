-- === BOOK 9: ChatMover Pipeline (book_id=9) ===
UPDATE books SET core_thesis = 'Chat conversations from all sources (ChatGPT, Cascade, Devin, disk) ingested into MySQL, compressed into BCL tokens, stored in SQLite with unresolved/resolved item tracking, queryable for future AI sessions.', sqlite_backend = 'MySQL Chat_History (sessions, messages, prompts) + bcl_chat_store.db (original_chats, bcl_stage1, bcl_stage2, chat_items)', status = 'ACTIVE' WHERE book_id = 9;

INSERT INTO nodes (node_type, node_name, node_value, domain, source_book_id, source_chapter_id) VALUES
  ('tool', 'chat_mover.py', 'Main ingestion pipeline orchestrator. 1779 lines. 8 steps: Connect, Create Schema, Read & Classify, Filter, Exclude Self, Parse & Import, Embed, Verify. Located at chat_mover/.', 'chat_mover', 9, (SELECT chapter_id FROM chapters WHERE book_id=9 AND chapter_title LIKE 'PHASE 1%' LIMIT 1)),
  ('tool', 'chatgpt_mysql_ingest.py', 'ChatGPT JSON export to MySQL standalone ingester.', 'chat_mover', 9, (SELECT chapter_id FROM chapters WHERE book_id=9 AND chapter_title LIKE 'PHASE 1%' LIMIT 1)),
  ('tool', 'cascade_mysql.py', 'Cascade .pb decrypt to MySQL standalone. Also CascadeIngester.py (VBStyle version).', 'chat_mover', 9, (SELECT chapter_id FROM chapters WHERE book_id=9 AND chapter_title LIKE 'PHASE 1%' LIMIT 1)),
  ('tool', 'Devin_Chat_msql.py', 'Devin CLI transcripts to Chat_History MySQL.', 'chat_mover', 9, (SELECT chapter_id FROM chapters WHERE book_id=9 AND chapter_title LIKE 'PHASE 1%' LIMIT 1)),
  ('tool', 'bcl_chat_compressor.py', 'Stage 1 code-based BCL extraction. Regex/dict: USER_SAYS, AI_SAYS, ERROR, FILE, COMMAND_RAN, FRUSTRATION_SIGNAL.', 'chat_mover', 9, (SELECT chapter_id FROM chapters WHERE book_id=9 AND chapter_title LIKE 'PHASE 2%' LIMIT 1)),
  ('tool', 'bcl_chat_ai_prompt.py', 'Stage 2 AI prompt builder for semantic pass. INTENT, MOOD, ROOT_CAUSE, PROBLEM+SOLUTION, LESSON.', 'chat_mover', 9, (SELECT chapter_id FROM chapters WHERE book_id=9 AND chapter_title LIKE 'PHASE 2%' LIMIT 1)),
  ('tool', 'bcl_chat_store.py', 'SQLite storage with Run dispatch and Tuple3. Tables: original_chats, bcl_stage1, bcl_stage2, chat_items.', 'chat_mover', 9, (SELECT chapter_id FROM chapters WHERE book_id=9 AND chapter_title LIKE 'SQLite%' LIMIT 1)),
  ('database', 'Chat_History (MySQL)', 'Unified chat store. Tables: sessions, messages, prompts, pipeline_state, error_knowledge. Destination for all sources.', 'chat_mover', 9, (SELECT chapter_id FROM chapters WHERE book_id=9 AND chapter_title LIKE 'PHASE 1%' LIMIT 1)),
  ('database', 'bcl_chat_store.db', 'SQLite for BCL compressed chats. Tables: original_chats, bcl_stage1, bcl_stage2, chat_items. Item tracking: open/resolved.', 'chat_mover', 9, (SELECT chapter_id FROM chapters WHERE book_id=9 AND chapter_title LIKE 'SQLite%' LIMIT 1)),
  ('concept', 'Two-Phase Architecture', 'Phase 1: Ingestion (sources to MySQL). Phase 2: Compression (MySQL to BCL to SQLite with item tracking).', 'chat_mover', 9, (SELECT chapter_id FROM chapters WHERE book_id=9 AND chapter_title LIKE 'Pipeline%' LIMIT 1)),
  ('process', 'Mapping Dom_Graph Architecture test', 'Proven: 10427 source lines, 1999 Stage 1 tokens, 5.2:1 ratio, 140 Stage 2 items (27 problems, 11 unresolved, 41 decisions, 38 successes, 20 failed, 3 lessons). 58 open, 82 resolved.', 'chat_mover', 9, (SELECT chapter_id FROM chapters WHERE book_id=9 AND chapter_title LIKE 'Compression%' LIMIT 1));

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'produces', 1.0, 'chat_mover.py produces Chat_History MySQL data'
  FROM nodes n1, nodes n2 WHERE n1.node_name='chat_mover.py' AND n2.node_name='Chat_History (MySQL)' AND n1.source_book_id=9;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'produces', 1.0, 'bcl_chat_compressor.py produces bcl_chat_store.db data'
  FROM nodes n1, nodes n2 WHERE n1.node_name='bcl_chat_compressor.py' AND n2.node_name='bcl_chat_store.db' AND n1.source_book_id=9;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'feeds_into', 1.0, 'bcl_chat_compressor.py feeds into bcl_chat_ai_prompt.py'
  FROM nodes n1, nodes n2 WHERE n1.node_name='bcl_chat_compressor.py' AND n2.node_name='bcl_chat_ai_prompt.py' AND n1.source_book_id=9;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'stores_in', 1.0, 'bcl_chat_store.py stores in bcl_chat_store.db'
  FROM nodes n1, nodes n2 WHERE n1.node_name='bcl_chat_store.py' AND n2.node_name='bcl_chat_store.db' AND n1.source_book_id=9;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'proven_result_of', 1.0, 'Mapping Dom_Graph test proven on chat_mover pipeline'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Mapping Dom_Graph Architecture test' AND n2.node_name='Two-Phase Architecture' AND n1.source_book_id=9;

UPDATE binary_artifacts SET artifact_name = 'chat_mover tools (Python)', artifact_type = 'python_tools', source_language = 'Python', source_code = 'chat_mover.py (1779 lines), bcl_chat_compressor.py, bcl_chat_ai_prompt.py, bcl_chat_store.py, ingest_bcl_chat.py', compile_command = 'python3 chat_mover/ingest_bcl_chat.py', compile_status = 'WORKING_NO_COMPILE_NEEDED', file_size_bytes = 0 WHERE book_id = 9;

UPDATE checks SET check_name = 'ingestion_all_sources', check_type = 'functional_verification', check_status = 'PASSING', check_result = 'All 4 sources working: ChatGPT, Cascade, Devin, SQLite/disk' WHERE book_id = 9;
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 9, (SELECT chapter_id FROM chapters WHERE book_id=9 AND chapter_title LIKE 'Current%' LIMIT 1), 'compression_5to1_ratio', 'performance_verification', 'PASSING', 'Mapping Dom_Graph: 10427 lines to 1999 tokens = 5.2:1 compression';
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 9, (SELECT chapter_id FROM chapters WHERE book_id=9 AND chapter_title LIKE 'Current%' LIMIT 1), 'item_tracking_140_items', 'functional_verification', 'PASSING', '140 items extracted: 27 problems, 11 unresolved, 41 decisions, 38 successes, 20 failed, 3 lessons. 58 open, 82 resolved.';

INSERT OR IGNORE INTO glossary_terms (term, definition, sqlite_mapping) VALUES
  ('ChatMover', 'Two-phase pipeline: Phase 1 ingests chats from all sources to MySQL, Phase 2 compresses to BCL tokens in SQLite with item tracking.', 'Chat_History.sessions/messages, bcl_chat_store.db'),
  ('chat_items', 'SQLite table tracking individual extracted items (PROBLEM, UNRESOLVED, DECISION, SUCCESS, FAILED, LESSON) with open/resolved status.', 'chat_items table');

INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes) SELECT file_path, 'pipelines_library.db:books.book_id=9', 'sqlite', file_hash, 9, 'Full markdown ingested (638 lines). 11 nodes, 5 links, 3 checks, 2 glossary terms. Two-phase architecture documented. 27 file register entries.' FROM books WHERE book_id = 9;
INSERT INTO pipeline_connections (from_book_id, to_book_id, connection_type, description, status) VALUES (9, 3, 'feeds_into', 'ChatMover Phase 2 compression is the BCL Chat Compression pipeline', 'ACTIVE');
INSERT INTO pipeline_connections (from_book_id, to_book_id, connection_type, description, status) VALUES (9, 7, 'uses', 'ChatMover uses PB Reader for Cascade .pb decryption', 'ACTIVE');

-- === BOOK 11: CLI Safe Execution Pipeline (book_id=11) ===
UPDATE books SET core_thesis = 'Every command execution goes through a formal state machine that prevents terminal errors, captures failures, learns from them, and queries the knowledge base for fixes before the error reaches the user.', sqlite_backend = 'MySQL vb_shared (learned_rules: 10590, error_knowledge: 70, know_problems: 309, know_solutions: 362) + SQLite fallback', status = 'ACTIVE' WHERE book_id = 11;

INSERT INTO nodes (node_type, node_name, node_value, domain, source_book_id, source_chapter_id) VALUES
  ('tool', 'cascade_cli.py (CEK v3)', 'Cascade Execution Kernel v3. State machine with 9 states. 8 stages: validate, normalize, execute, detect, query KB, learn, pre-scan, log. Located at /Users/wws/Downloads/cascade_cli.py.', 'cli_safe', 11, (SELECT chapter_id FROM chapters WHERE book_id=11 AND chapter_title LIKE 'Pipeline%' LIMIT 1)),
  ('database', 'vb_shared learned_rules', 'MySQL knowledge base. 10590 rules (pattern to fix_action with confidence). Queried on error for known fixes.', 'cli_safe', 11, (SELECT chapter_id FROM chapters WHERE book_id=11 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('database', 'error_knowledge', '70 error signatures with cause, solution, fix_code. Dual write MySQL + SQLite.', 'cli_safe', 11, (SELECT chapter_id FROM chapters WHERE book_id=11 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('concept', '9-state machine', 'States: INIT, RUNNING, STREAMING, STUCK, TIMEOUT, KILLED, FAILED, DONE, BLOCKED, ERROR. Terminal: FAILED, DONE, BLOCKED, ERROR.', 'cli_safe', 11, (SELECT chapter_id FROM chapters WHERE book_id=11 AND chapter_title LIKE 'State%' LIMIT 1)),
  ('concept', '12 error patterns', 'Pattern dictionary: MySQLProgrammingError, MySQLInterfaceError, ImportError, ModuleNotFoundError, SyntaxError, AttributeError, TypeError, ZeroDivisionError, FileNotFoundError, PermissionError, missing_header.', 'cli_safe', 11, (SELECT chapter_id FROM chapters WHERE book_id=11 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('process', 'Triple-layer protection', 'Timeout (hard limit), Stuck detection (no output for N seconds), Freeze detection (2x stuck threshold, force-kill process group).', 'cli_safe', 11, (SELECT chapter_id FROM chapters WHERE book_id=11 AND chapter_title LIKE 'Stages%' LIMIT 1));

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'queries', 1.0, 'cascade_cli.py queries learned_rules on error'
  FROM nodes n1, nodes n2 WHERE n1.node_name='cascade_cli.py (CEK v3)' AND n2.node_name='vb_shared learned_rules' AND n1.source_book_id=11;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'writes_to', 1.0, 'cascade_cli.py writes new errors to error_knowledge (dual write MySQL + SQLite)'
  FROM nodes n1, nodes n2 WHERE n1.node_name='cascade_cli.py (CEK v3)' AND n2.node_name='error_knowledge' AND n1.source_book_id=11;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'implements', 1.0, 'cascade_cli.py implements the 9-state machine'
  FROM nodes n1, nodes n2 WHERE n1.node_name='cascade_cli.py (CEK v3)' AND n2.node_name='9-state machine' AND n1.source_book_id=11;

UPDATE binary_artifacts SET artifact_name = 'cascade_cli.py (Python CLI)', artifact_type = 'python_tool', source_language = 'Python', source_code = '/Users/wws/Downloads/cascade_cli.py', compile_command = 'python3 cascade_cli.py "command" --shell --timeout 30', compile_status = 'WORKING_NO_COMPILE_NEEDED', file_size_bytes = 0 WHERE book_id = 11;

UPDATE checks SET check_name = 'state_machine_9_states', check_type = 'completeness_check', check_status = 'PASSING', check_result = '9 states implemented: INIT, RUNNING, STREAMING, STUCK, TIMEOUT, KILLED, FAILED, DONE, BLOCKED, ERROR' WHERE book_id = 11;
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 11, (SELECT chapter_id FROM chapters WHERE book_id=11 AND chapter_title LIKE 'Current%' LIMIT 1), 'error_patterns_12', 'completeness_check', 'PASSING', '12 error patterns detected: MySQL, Python, VBStyle categories';
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 11, (SELECT chapter_id FROM chapters WHERE book_id=11 AND chapter_title LIKE 'Current%' LIMIT 1), 'kb_query_10590_rules', 'completeness_check', 'PASSING', 'MySQL learned_rules: 10590 rules. error_knowledge: 70 signatures. know_problems: 309. know_solutions: 362.';

INSERT OR IGNORE INTO glossary_terms (term, definition, sqlite_mapping) VALUES
  ('cascade_cli.py', 'Cascade Execution Kernel v3. State machine CLI with 9 states, 8 stages, 12 error patterns, KB queries, dual-write learning.', 'vb_shared.learned_rules, error_knowledge'),
  ('9-state machine', 'CLI execution states: INIT, RUNNING, STREAMING, STUCK, TIMEOUT, KILLED, FAILED, DONE, BLOCKED, ERROR. Terminal: FAILED, DONE, BLOCKED, ERROR.', NULL);

INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes) SELECT file_path, 'pipelines_library.db:books.book_id=11', 'sqlite', file_hash, 11, 'Full markdown ingested (237 lines). 6 nodes, 3 links, 3 checks, 2 glossary terms. 9-state machine documented. 12 error patterns. 10590 learned_rules.' FROM books WHERE book_id = 11;
INSERT INTO pipeline_connections (from_book_id, to_book_id, connection_type, description, status) VALUES (11, 23, 'feeds_into', 'CLI errors feed into Error Capture learned_rules', 'ACTIVE');

-- === BOOK 12: Code Graph (Visual Diagrams) (book_id=12) ===
UPDATE books SET core_thesis = 'Visual diagram of the Code Graph Pipeline. Shows 12-stage flow: SYNC, INGEST, GRAPH, REASON, REGRAPH, VALIDATE, PLAN, REPAIR, CONFIG, EXPORT, VERIFY, ARCHIVE. Database schema with code_files, code_units, code_edges, stamps, config_metadata.', sqlite_backend = 'code_graph.db (SQLite): code_files (134 rows), code_units (2649 rows), code_edges (12558 rows)', status = 'ACTIVE' WHERE book_id = 12;

INSERT INTO nodes (node_type, node_name, node_value, domain, source_book_id, source_chapter_id) VALUES
  ('database', 'code_graph.db', 'SQLite database. code_files: 134 rows. code_units: 2649 rows (1801 METHOD, 501 MODULE_CONST, 134 IMPORT, 121 CLASS, 63 FUNCTION, 29 MAIN_BLOCK). code_edges: 12558 rows (10757 CALLS, 1801 CONTAINS).', 'code_graph', 12, (SELECT chapter_id FROM chapters WHERE book_id=12 AND chapter_title LIKE 'Database%' LIMIT 1)),
  ('concept', '12-stage pipeline', 'SYNC, INGEST, GRAPH, REASON (3a SURFACE, 3b DEEP, 3c MINE), REGRAPH, VALIDATE, PLAN, REPAIR, CONFIG, EXPORT, VERIFY, ARCHIVE.', 'code_graph', 12, (SELECT chapter_id FROM chapters WHERE book_id=12 AND chapter_title LIKE 'Pipeline%' LIMIT 1)),
  ('process', 'Dom_Graph ingestion', 'Proven: 134 files to 2649 units to 12558 edges. Top file: Dom_Graph_Agent.py (122 methods). 228 dead methods (no callers).', 'code_graph', 12, (SELECT chapter_id FROM chapters WHERE book_id=12 AND chapter_title LIKE 'Actual%' LIMIT 1));

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'proven_result_of', 1.0, 'Dom_Graph ingestion proven: 134 files, 2649 units, 12558 edges'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Dom_Graph ingestion' AND n2.node_name='12-stage pipeline' AND n1.source_book_id=12;

UPDATE binary_artifacts SET artifact_name = 'none (visual diagrams)', artifact_type = 'none', source_language = 'none', source_code = 'This is a visual diagram document. No compilable code.', compile_command = '', compile_status = 'NOT_APPLICABLE', file_size_bytes = 0 WHERE book_id = 12;

UPDATE checks SET check_name = 'ingestion_134_files', check_type = 'completeness_check', check_status = 'PASSING', check_result = '134 files ingested: 2649 units, 12558 edges (10757 CALLS, 1801 CONTAINS)' WHERE book_id = 12;
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 12, (SELECT chapter_id FROM chapters WHERE book_id=12 AND chapter_title LIKE 'Actual%' LIMIT 1), 'dead_methods_228', 'completeness_check', 'DETECTED', '228 of 1801 methods have no recorded caller (dead code candidates)';

INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes) SELECT file_path, 'pipelines_library.db:books.book_id=12', 'sqlite', file_hash, 12, 'Full markdown ingested (273 lines). Visual diagram document. 3 nodes, 1 link, 2 checks. 12-stage pipeline flow diagram. Database schema diagram. Dom_Graph ingested data visualization.' FROM books WHERE book_id = 12;
INSERT INTO pipeline_connections (from_book_id, to_book_id, connection_type, description, status) VALUES (12, 28, 'visualizes', 'Code Graph visual diagrams illustrate the Code Graph Pipeline (Plf_Pipeline.md)', 'ACTIVE');
