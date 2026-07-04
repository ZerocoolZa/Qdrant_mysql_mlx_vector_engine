-- === BOOK 14: Config Cascade Pipeline (book_id=14) ===
UPDATE books SET core_thesis = 'No hardcoded values. Every path, port, timeout, DB path, threshold, and constant lives in a Config.py file. ConfigCascade scans .py files, extracts config-like data, generates/updates config files, and verifies compliance.', sqlite_backend = 'Config.py files (file-based, 26+ files) + ConfigEngine (Section 52)', status = 'ACTIVE' WHERE book_id = 14;

INSERT INTO nodes (node_type, node_name, node_value, domain, source_book_id, source_chapter_id) VALUES
  ('tool', 'ConfigCascade.py', 'Config authority. 12 Run commands: scan, extract, regex_extract, generate, read, write, update, verify, catalog, scan_files, file_index, full_run. 1209 lines. Located at core/Dom_Unified/.', 'config', 14, (SELECT chapter_id FROM chapters WHERE book_id=14 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('tool', 'ConfigEngine (config_engine.py)', 'Section 52 config engine. 11 commands: scan_config, get_constants, find_env_vars, find_feature_flags, get_defaults, get_overrides, validate_config, get_config, set_config, set_constant, get_environment. Located at Dom_Graph/.', 'config', 14, (SELECT chapter_id FROM chapters WHERE book_id=14 AND chapter_title LIKE 'Companion%Section%' LIMIT 1)),
  ('tool', 'config_extractor.py', 'Regex-based config extractor. Works even with syntax errors (no AST needed). Located at gui_engine/.', 'config', 14, (SELECT chapter_id FROM chapters WHERE book_id=14 AND chapter_title LIKE 'Companion%Regex%' LIMIT 1)),
  ('concept', 'Gold Standard (BookSystem)', 'Config_BookSystem.py: 1703 lines. Template for generated Config.py files. 22 sections: headers, AI guide, Config class, BASE_DIR, paths, versions, colors, tooltips, themes, icons, shortcuts, schema SQL, static resources, documentation, getters, singleton.', 'config', 14, (SELECT chapter_id FROM chapters WHERE book_id=14 AND chapter_title LIKE 'Gold%' LIMIT 1)),
  ('process', 'ConfigCascade merge', '3 files merged into 1: ConfigCascade.py (519 lines) + Prj_VBScanner.py (730 lines) + config_extractor.py (274 lines) = 1209 lines, 39 methods, 12 Run commands. Used SQLite Fast Method. Date: 2026-06-28.', 'config', 14, (SELECT chapter_id FROM chapters WHERE book_id=14 AND chapter_title LIKE 'Merge%' LIMIT 1));

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'merged_into', 1.0, 'ConfigCascade merge: 3 files merged into ConfigCascade.py'
  FROM nodes n1, nodes n2 WHERE n1.node_name='ConfigCascade merge' AND n2.node_name='ConfigCascade.py' AND n1.source_book_id=14;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'template_for', 1.0, 'Gold Standard BookSystem is the template for generated configs'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Gold Standard (BookSystem)' AND n2.node_name='ConfigCascade.py' AND n1.source_book_id=14;

UPDATE binary_artifacts SET artifact_name = 'ConfigCascade.py (Python)', artifact_type = 'python_tool', source_language = 'Python', source_code = 'core/Dom_Unified/ConfigCascade.py (1209 lines, 39 methods, 12 Run commands)', compile_command = 'python3 ConfigCascade.py', compile_status = 'WORKING_NO_COMPILE_NEEDED', file_size_bytes = 0 WHERE book_id = 14;

UPDATE checks SET check_name = 'config_catalog_26_files', check_type = 'completeness_check', check_status = 'PASSING', check_result = '26+ Config.py files across all domains. All have BCL headers, Config class, Run() dispatch.' WHERE book_id = 14;
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 14, (SELECT chapter_id FROM chapters WHERE book_id=14 AND chapter_title LIKE 'Current%' LIMIT 1), 'vbstyle_11_checks', 'style_verification', 'PASSING', '11 compliance checks: has_ghost, has_vbstyle, has_summary, has_class, has_run, has_tuple3, no_print, no_decorators, no_self_underscore, no_tabs, has_state_dict';
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 14, (SELECT chapter_id FROM chapters WHERE book_id=14 AND chapter_title LIKE 'Current%' LIMIT 1), 'no_hardcode_partial', 'completeness_check', 'PARTIAL', 'Some files still have hardcoded values. ConfigCascade can scan+extract but not yet auto-replace in source.';

INSERT OR IGNORE INTO glossary_terms (term, definition, sqlite_mapping) VALUES
  ('ConfigCascade', 'Config authority tool. 12 Run commands. Scans .py for constants, generates Config.py with VBStyle headers, verifies compliance. 1209 lines, 39 methods.', 'Config.py files (file-based)'),
  ('Gold Standard Config', 'BookSystem/Config_BookSystem.py: 1703 lines, 22 sections. The template all generated Config.py files should follow.', NULL);

INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes) SELECT file_path, 'pipelines_library.db:books.book_id=14', 'sqlite', file_hash, 14, 'Full markdown ingested (393 lines). 5 nodes, 2 links, 3 checks, 2 glossary terms. 3-file merge history documented. 26+ config files catalogued.' FROM books WHERE book_id = 14;
INSERT INTO pipeline_connections (from_book_id, to_book_id, connection_type, description, status) VALUES (14, 13, 'uses', 'ConfigCascade merge used Code Ingestion Pipeline SQLite Fast Method', 'ACTIVE');

-- === BOOK 15: Config Files Manual (book_id=15) ===
UPDATE books SET core_thesis = 'Authoritative reference for every Config.py and Config_*.py file. Every config file follows the same structure, same order, same rules. 22 chapters covering what, why, where, how, mandatory sections, optional sections, templates, anti-patterns, migration.', sqlite_backend = 'File-based (Config.py per domain, 26+ files)', status = 'ACTIVE' WHERE book_id = 15;

INSERT INTO nodes (node_type, node_name, node_value, domain, source_book_id, source_chapter_id) VALUES
  ('concept', '5 Mandatory Sections', 'Every Config.py must have: (1) BCL Headers, (2) File Inventory, (3) Constants, (4) Config Class with Run(), (5) README/Architecture description.', 'config_manual', 15, (SELECT chapter_id FROM chapters WHERE book_id=15 AND chapter_title LIKE 'Chapter 5%' LIMIT 1)),
  ('concept', 'Config Class API', 'Config class with __init__(mem,db,param), Run(get/set), read_state, set_config. Programmatic access to all config values.', 'config_manual', 15, (SELECT chapter_id FROM chapters WHERE book_id=15 AND chapter_title LIKE 'Chapter 8%' LIMIT 1)),
  ('concept', 'Anti-Patterns', 'What NOT to do: no flat constants without class, no universal content in domain configs, no missing file inventory, no headers that lie, no missing Run() method.', 'config_manual', 15, (SELECT chapter_id FROM chapters WHERE book_id=15 AND chapter_title LIKE 'Chapter 15%' LIMIT 1));

UPDATE binary_artifacts SET artifact_name = 'none (reference manual)', artifact_type = 'none', source_language = 'none', source_code = 'This is a reference manual. No compilable code.', compile_command = '', compile_status = 'NOT_APPLICABLE', file_size_bytes = 0 WHERE book_id = 15;

UPDATE checks SET check_name = 'config_manual_22_chapters', check_type = 'completeness_check', check_status = 'PASSING', check_result = '22 chapters covering all aspects of Config.py files' WHERE book_id = 15;

INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes) SELECT file_path, 'pipelines_library.db:books.book_id=15', 'sqlite', file_hash, 15, 'Full markdown ingested (663 lines). 3 nodes. Reference manual with 22 chapters. No binary artifacts.' FROM books WHERE book_id = 15;
INSERT INTO pipeline_connections (from_book_id, to_book_id, connection_type, description, status) VALUES (15, 14, 'governs', 'Config Files Manual defines the standard that ConfigCascade enforces', 'ACTIVE');

-- === BOOK 16: Context Expansion Pipeline (book_id=16) ===
UPDATE books SET core_thesis = 'Chats are not just conversations — they are the raw material from which domains, graphs, and file identities are forged. Chat content is expanded into in-RAM SQLite, mined for structure, and extracted knowledge becomes the identity every file carries.', sqlite_backend = 'In-RAM SQLite (:memory:) + MySQL devin_messages (38K rows) + dom_graph.db + Qdrant embeddings', status = 'ACTIVE' WHERE book_id = 16;

INSERT INTO nodes (node_type, node_name, node_value, domain, source_book_id, source_chapter_id) VALUES
  ('tool', 'GraphEngine.py', 'Graph views + algorithms executor. search, bfs, dfs, cycle, path, topology. Located at tmp_graph_ingest/.', 'context_expansion', 16, (SELECT chapter_id FROM chapters WHERE book_id=16 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('tool', 'CascadeEngine.py', 'Pre-code validation compiler. 8-graph gating. Located at tmp_graph_ingest/.', 'context_expansion', 16, (SELECT chapter_id FROM chapters WHERE book_id=16 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('tool', 'AutoGenerator.py', 'Self-writing graph evolution. Reads failures, creates fallback nodes, deduplicates, promotes/prunes paths.', 'context_expansion', 16, (SELECT chapter_id FROM chapters WHERE book_id=16 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('tool', 'MemDb (memdb_real.py)', 'In-RAM SQLite for fast graph operations. Tables: command_queue, state_cache, routing_map. Located at Cascade_toolStack/arch_test/.', 'context_expansion', 16, (SELECT chapter_id FROM chapters WHERE book_id=16 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('database', 'domain_graph.db', 'Domain engine. Pure SQL, reads v20_hybrid_best.db. Tables: domain_nodes, domain_connections, domain_classes, domain_identity, class_routing, domain_closure VIEW.', 'context_expansion', 16, (SELECT chapter_id FROM chapters WHERE book_id=16 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('concept', '8 Node Types', 'CONCEPT, FILE, TOOL, INTENT, ENTITY, ERROR, DECISION, VALUE. Extracted from chat content during Stage 1.', 'context_expansion', 16, (SELECT chapter_id FROM chapters WHERE book_id=16 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('concept', '7 Edge Types', 'REFERENCES, DEPENDS_ON, CONTRADICTS, RESOLVES, CAUSED_BY, PART_OF, RELATED_TO. Built during Stage 2.', 'context_expansion', 16, (SELECT chapter_id FROM chapters WHERE book_id=16 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('concept', '20-Component Spec', 'Parts 1-6 done (extraction, storage). Parts 7-20 mostly NOT BUILT: temporal, belief, open loops, importance, context window, contradiction, provenance, confidence, compression, multi-hop, entity resolution, graph diff, active learning, export.', 'context_expansion', 16, (SELECT chapter_id FROM chapters WHERE book_id=16 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('process', 'Domain Extraction', 'Proven: 767/1445 classes (53%) routed across 75 domains, 0 conflicts. Routing: name match (483), BCL self-declared (9), method vote (165), code content (110).', 'context_expansion', 16, (SELECT chapter_id FROM chapters WHERE book_id=16 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('concept', 'Chat to Identity Chain', 'Chat -> Parse -> Nodes/Edges -> In-RAM SQLite -> Graph Activation -> Domain Extraction -> BCL Identity -> Every file carries identity. This is why BCL headers exist.', 'context_expansion', 16, (SELECT chapter_id FROM chapters WHERE book_id=16 AND chapter_title LIKE 'Vital%' LIMIT 1));

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'uses', 1.0, 'GraphEngine.py uses MemDb for in-RAM graph operations'
  FROM nodes n1, nodes n2 WHERE n1.node_name='GraphEngine.py' AND n2.node_name='MemDb (memdb_real.py)' AND n1.source_book_id=16;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'produces', 1.0, 'Domain Extraction produces domain_graph.db with 75 domains'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Domain Extraction' AND n2.node_name='domain_graph.db' AND n1.source_book_id=16;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'implements', 1.0, 'GraphEngine.py implements 8 Node Types extraction'
  FROM nodes n1, nodes n2 WHERE n1.node_name='GraphEngine.py' AND n2.node_name='8 Node Types' AND n1.source_book_id=16;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'implements', 1.0, 'GraphEngine.py implements 7 Edge Types building'
  FROM nodes n1, nodes n2 WHERE n1.node_name='GraphEngine.py' AND n2.node_name='7 Edge Types' AND n1.source_book_id=16;

UPDATE binary_artifacts SET artifact_name = 'GraphEngine + CascadeEngine + AutoGenerator', artifact_type = 'python_tools', source_language = 'Python', source_code = 'tmp_graph_ingest/GraphEngine.py, CascadeEngine.py, AutoGenerator.py, DecisionEngine.py + 8 graph view files', compile_command = 'python3 GraphEngine.py', compile_status = 'WORKING_NO_COMPILE_NEEDED', file_size_bytes = 0 WHERE book_id = 16;

UPDATE checks SET check_name = 'domain_extraction_75_domains', check_type = 'completeness_check', check_status = 'PASSING', check_result = '767/1445 classes (53%) routed across 75 domains, 0 conflicts' WHERE book_id = 16;
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 16, (SELECT chapter_id FROM chapters WHERE book_id=16 AND chapter_title LIKE 'Current%' LIMIT 1), 'parts_1_6_done', 'completeness_check', 'PASSING', 'Parts 1-6 (extraction, storage, activation, persistence, LLM integration, iteration) all DONE';
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 16, (SELECT chapter_id FROM chapters WHERE book_id=16 AND chapter_title LIKE 'Current%' LIMIT 1), 'parts_7_20_missing', 'completeness_check', 'NOT_BUILT', 'Parts 7-20 mostly NOT BUILT: temporal, belief, open loops, context window, contradiction, compression, entity resolution, graph diff, active learning';

INSERT OR IGNORE INTO glossary_terms (term, definition, sqlite_mapping) VALUES
  ('Context Expansion', 'Pipeline: Chat -> Parse -> Nodes/Edges -> In-RAM SQLite -> Graph Activation -> Domain Extraction -> BCL Identity. 8 node types, 7 edge types, 75 domains.', 'nodes, edges tables (:memory:)'),
  ('Domain Extraction', 'Clusters of connected concepts form domains. 767/1445 classes routed across 75 domains. Routing by name match, BCL self-declared, method vote, code content.', 'domain_graph.db');

INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes) SELECT file_path, 'pipelines_library.db:books.book_id=16', 'sqlite', file_hash, 16, 'Full markdown ingested (360 lines). 10 nodes, 4 links, 3 checks, 2 glossary terms. 8 stages. 20-component spec (6 done, 14 not built). Chat-to-Identity chain documented.' FROM books WHERE book_id = 16;
INSERT INTO pipeline_connections (from_book_id, to_book_id, connection_type, description, status) VALUES (16, 9, 'source', 'Context Expansion reads chat messages from ChatMover MySQL devin_messages (38K rows)', 'ACTIVE');
INSERT INTO pipeline_connections (from_book_id, to_book_id, connection_type, description, status) VALUES (16, 5, 'produces', 'Context Expansion produces BCL identity headers that BCL Template Maker stamps', 'ACTIVE');
