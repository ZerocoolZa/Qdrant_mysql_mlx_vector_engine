-- ============================================================
-- BATCH POPULATE: Books 5, 6, 7
-- Plf_BclTemplateMakerPipeline.md (book_id=5)
-- Plf_BclUnitBuilderPipeline.md (book_id=6)
-- Plf_CascadePbReaderPipeline.md (book_id=7)
-- ============================================================

-- === BOOK 5: BCL Template Maker ===
UPDATE books SET core_thesis = 'Files without identity dont exist. BCL Template Maker generates, edits, and stamps BCL headers onto files. Every file gets [@GHOST], [@VBSTYLE], [@FILEID], [@SUMMARY], [@CLASS], [@METHOD].', sqlite_backend = 'MySQL vb_shared.rule_tokens (238 tokens) + bcl_header.txt', status = 'ACTIVE' WHERE book_id = 5;

UPDATE sections SET section_type = 'stage_header_editor' WHERE section_id IN (SELECT section_id FROM sections WHERE book_id = 5 AND section_title LIKE 'Stage 1%');
UPDATE sections SET section_type = 'stage_template' WHERE section_id IN (SELECT section_id FROM sections WHERE book_id = 5 AND section_title LIKE 'Stage 2%');
UPDATE sections SET section_type = 'stage_stamp' WHERE section_id IN (SELECT section_id FROM sections WHERE book_id = 5 AND section_title LIKE 'Stage 3%');
UPDATE sections SET section_type = 'stage_capsule' WHERE section_id IN (SELECT section_id FROM sections WHERE book_id = 5 AND section_title LIKE 'Stage 4%');
UPDATE sections SET section_type = 'stage_verify' WHERE section_id IN (SELECT section_id FROM sections WHERE book_id = 5 AND section_title LIKE 'Stage 5%');
UPDATE sections SET section_type = 'stage_rule_tokens' WHERE section_id IN (SELECT section_id FROM sections WHERE book_id = 5 AND section_title LIKE 'Stage 6%');
UPDATE sections SET section_type = 'stage_rule_graphs' WHERE section_id IN (SELECT section_id FROM sections WHERE book_id = 5 AND section_title LIKE 'Stage 7%');

INSERT INTO nodes (node_type, node_name, node_value, domain, source_book_id, source_chapter_id) VALUES
  ('tool', 'BCLEditor (file_header_preview.py)', 'PyQt6 GUI for editing BCL headers. Template buttons for GHOST, VBSTYLE, CLASS, METHOD, FILEID, SUMMARY. BCL syntax highlighter. Live reload. Located at /Users/wws/Downloads/file_header_preview.py.', 'bcl_template', 5, (SELECT chapter_id FROM chapters WHERE book_id=5 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('tool', 'stamp_and_capsule.py', 'Stamps BCL headers onto .py files. Scan, check, extract, generate, inject, write. File types: .py, .sql, .md, .txt, .json, .yaml, .c, .sh.', 'bcl_template', 5, (SELECT chapter_id FROM chapters WHERE book_id=5 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('tool', 'capsule_builder.py', 'Builds self-contained capsule from chat session. Scans chat for file refs, stamps files, compresses with zlib, base64 encodes, builds markdown.', 'bcl_template', 5, (SELECT chapter_id FROM chapters WHERE book_id=5 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('tool', 'vbs_rule_enforcer.py', 'VBStyle rule enforcement. scan_file, scan_folder, auto_fix, check_vbstyle. Located at core/Dom_Vsstyle/.', 'bcl_template', 5, (SELECT chapter_id FROM chapters WHERE book_id=5 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('tool', 'vbs_rule_engine.py', 'Rule token authority. 238 canonical tokens in MySQL vb_shared.rule_tokens. Extract, load, analyse, create, search, propose, edit, fix.', 'bcl_template', 5, (SELECT chapter_id FROM chapters WHERE book_id=5 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('database', 'rule_tokens (MySQL)', 'Canonical BCL rule tokens. 238 tokens. Categories: Architecture, State, Method, Forbidden, Format, Naming, Paths, Database, FileOps, Workflow, Meta, Other.', 'bcl_template', 5, (SELECT chapter_id FROM chapters WHERE book_id=5 AND chapter_title LIKE 'Stages%' LIMIT 1)),
  ('concept', 'BCL Header Identity', '6-field identity block every file carries: [@GHOST] (file_path, identity, purpose, date, version, author, chat_link), [@VBSTYLE] (auth, role, return, orch, no, model), [@FILEID], [@SUMMARY], [@CLASS], [@METHOD].', 'bcl_template', 5, (SELECT chapter_id FROM chapters WHERE book_id=5 AND chapter_title LIKE 'BCL Header%' LIMIT 1));

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'produces', 1.0, 'BCLEditor produces bcl_header.txt template'
  FROM nodes n1, nodes n2 WHERE n1.node_name='BCLEditor (file_header_preview.py)' AND n2.node_name='stamp_and_capsule.py' AND n1.source_book_id=5;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'enforces', 1.0, 'vbs_rule_enforcer.py enforces BCL Header Identity compliance'
  FROM nodes n1, nodes n2 WHERE n1.node_name='vbs_rule_enforcer.py' AND n2.node_name='BCL Header Identity' AND n1.source_book_id=5;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'manages', 1.0, 'vbs_rule_engine.py manages rule_tokens MySQL table'
  FROM nodes n1, nodes n2 WHERE n1.node_name='vbs_rule_engine.py' AND n2.node_name='rule_tokens (MySQL)' AND n1.source_book_id=5;

UPDATE binary_artifacts SET artifact_name = 'none (GUI tool + Python scripts)', artifact_type = 'python_gui', source_language = 'Python', source_code = 'file_header_preview.py (PyQt6 GUI), stamp_and_capsule.py, capsule_builder.py', compile_command = 'python3 file_header_preview.py', compile_status = 'WORKING_NO_COMPILE_NEEDED', file_size_bytes = 0 WHERE book_id = 5;

UPDATE checks SET check_name = 'vbstyle_compliance_12_checks', check_type = 'style_verification', check_status = 'PASSING', check_result = '12 compliance checks: ghost_header, vbstyle_header, tuple3_return, state_dict, pascal_case, uppercase_constants, no_print, no_decorators, no_self_underscore, no_tabs, has_run' WHERE book_id = 5;
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 5, (SELECT chapter_id FROM chapters WHERE book_id=5 AND chapter_title LIKE 'Current%' LIMIT 1), 'all_files_carry_identity', 'completeness_check', 'MOSTLY_DONE', 'Most .py files carry BCL headers. Some may still lack headers.';
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 5, (SELECT chapter_id FROM chapters WHERE book_id=5 AND chapter_title LIKE 'Current%' LIMIT 1), 'rule_token_count', 'completeness_check', 'PASSING', '238 canonical rule tokens in MySQL vb_shared.rule_tokens';

INSERT OR IGNORE INTO glossary_terms (term, definition, sqlite_mapping) VALUES
  ('BCL Header Identity', '6-field identity block: [@GHOST], [@VBSTYLE], [@FILEID], [@SUMMARY], [@CLASS], [@METHOD]. Every file carries identity.', NULL),
  ('rule_tokens', 'Canonical BCL rule tokens in MySQL vb_shared. 238 tokens across 12 categories. Managed by vbs_rule_engine.py.', 'vb_shared.rule_tokens'),
  ('Capsule Builder', 'Builds self-contained archive from chat session. Scans for file refs, stamps, compresses zlib, base64 encodes, outputs markdown.', NULL);

INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes) SELECT file_path, 'pipelines_library.db:books.book_id=5', 'sqlite', file_hash, 5, 'Full markdown ingested (292 lines). 7 nodes, 3 links, 3 checks, 3 glossary terms.' FROM books WHERE book_id = 5;
INSERT INTO pipeline_connections (from_book_id, to_book_id, connection_type, description, status) VALUES (5, 4, 'uses', 'BCL Template Maker uses BCL Code Graph identity tokens and BclGenerator', 'ACTIVE');

-- === BOOK 6: BCL Unit Builder ===
UPDATE books SET core_thesis = 'AI sends a BCL spec, the builder writes a complete .c BCL unit file, checks VBStyle compliance, compiles it, and registers it in the tool stack. New capability = new .c file. Exponentially growable.', sqlite_backend = 'SQLite (in-RAM for build) + Makefile build system', status = 'ACTIVE' WHERE book_id = 6;

UPDATE binary_artifacts SET artifact_name = 'bcl_builder.c + bcl_units', artifact_type = 'native_c_binary', source_language = 'C', source_code = 'Cascade_toolStack/bin_tools/bcl_builder.c (590 lines), bcl_units/bcl_tool_main.c, bcl_units/bcl_pb_reader.c (COMPLETE), 12 stub units', compile_command = 'cd bcl_units && make', compile_status = 'PARTIAL (1 of 17 units complete, 12 stubs)', file_size_bytes = 0 WHERE book_id = 6;

INSERT INTO nodes (node_type, node_name, node_value, domain, source_book_id, source_chapter_id) VALUES
  ('tool', 'bcl_builder.c', 'C CLI that generates .c files from BCL spec. 590 lines. Auto-checks VBStyle compliance, auto-compiles. Located at Cascade_toolStack/bin_tools/.', 'bcl_units', 6, (SELECT chapter_id FROM chapters WHERE book_id=6 AND chapter_title LIKE 'Folder%' LIMIT 1)),
  ('tool', 'bcl_tool_main.c', 'Single entry point for all BCL units. Registers 17 units, CLI dispatch. Located at bcl_units/.', 'bcl_units', 6, (SELECT chapter_id FROM chapters WHERE book_id=6 AND chapter_title LIKE 'Folder%' LIMIT 1)),
  ('tool', 'bcl_pb_reader.c', 'COMPLETE unit: AES-256-GCM decrypt, protobuf parse, in-RAM SQLite. The only fully built unit.', 'bcl_units', 6, (SELECT chapter_id FROM chapters WHERE book_id=6 AND chapter_title LIKE 'Folder%' LIMIT 1)),
  ('database', 'bcl_units Makefile', 'Build system for all BCL C units. Located at bcl_units/Makefile.', 'bcl_units', 6, (SELECT chapter_id FROM chapters WHERE book_id=6 AND chapter_title LIKE 'Folder%' LIMIT 1)),
  ('concept', 'BCL Unit', 'A .c file that implements a capability via BCL dispatch. New capability = new .c file. 28 units planned, 1 complete, 12 stubs, 15 not started.', 'bcl_units', 6, (SELECT chapter_id FROM chapters WHERE book_id=6 AND chapter_title LIKE 'Build%' LIMIT 1));

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'generates', 1.0, 'bcl_builder.c generates BCL Unit .c files from spec'
  FROM nodes n1, nodes n2 WHERE n1.node_name='bcl_builder.c' AND n2.node_name='BCL Unit' AND n1.source_book_id=6;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'registers_in', 1.0, 'bcl_tool_main.c registers all units for CLI dispatch'
  FROM nodes n1, nodes n2 WHERE n1.node_name='bcl_tool_main.c' AND n2.node_name='bcl_units Makefile' AND n1.source_book_id=6;

UPDATE checks SET check_name = 'unit_build_status', check_type = 'completeness_check', check_status = 'PARTIAL', check_result = '1 of 17 units complete (bcl_pb_reader.c). 12 stubs generated. 4 not started. Makefile working.' WHERE book_id = 6;
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 6, (SELECT chapter_id FROM chapters WHERE book_id=6 AND chapter_title LIKE 'Build%' LIMIT 1), 'vbstyle_compliance_c', 'style_verification', 'PASSING', 'bcl_builder.c auto-checks VBStyle compliance before compiling';

INSERT OR IGNORE INTO glossary_terms (term, definition, sqlite_mapping) VALUES
  ('BCL Unit', 'A .c file implementing a capability via BCL dispatch. New capability = new .c file. 28 planned, 1 complete, 12 stubs.', NULL),
  ('bcl_builder', 'C CLI that generates .c BCL unit files from BCL spec. 590 lines. Auto-checks, auto-compiles. Located at Cascade_toolStack/bin_tools/.', NULL);

INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes) SELECT file_path, 'pipelines_library.db:books.book_id=6', 'sqlite', file_hash, 6, 'Full markdown ingested (1385 lines). 5 nodes, 2 links. C binary artifacts: bcl_builder.c (590 lines), 17 unit files (1 complete, 12 stubs). Build system: Makefile.' FROM books WHERE book_id = 6;
INSERT INTO pipeline_connections (from_book_id, to_book_id, connection_type, description, status) VALUES (6, 4, 'related_to', 'BCL Unit Builder extends BCL Code Graph to C language', 'ACTIVE');

-- === BOOK 7: Cascade PB Reader ===
UPDATE books SET core_thesis = 'Cascade should never lose context due to language server restarts. Search encrypted .pb chat files directly — decrypt in RAM, parse protobuf wire-format, query with SQLite, return exact conversation history with 100% recall.', sqlite_backend = 'In-RAM SQLite (:memory:, 6 tables, 5 indexes, no plaintext on disk)', status = 'ACTIVE' WHERE book_id = 7;

INSERT INTO nodes (node_type, node_name, node_value, domain, source_book_id, source_chapter_id) VALUES
  ('tool', 'pb_reader.py', 'VBStyle class for decrypting and searching .pb chat files. AES-256-GCM decrypt, protobuf wire-format parse, in-RAM SQLite. 1041 lines. Located at chat_mover/pb_reader.py.', 'pb_reader', 7, (SELECT chapter_id FROM chapters WHERE book_id=7 AND chapter_title LIKE 'Pipeline%' LIMIT 1)),
  ('database', 'In-RAM SQLite (:memory:)', '6 tables: trajectories, steps, user_messages, assistant_messages, commands, checkpoints. 5 indexes. All in :memory:. Destroyed when process exits. No plaintext on disk.', 'pb_reader', 7, (SELECT chapter_id FROM chapters WHERE book_id=7 AND chapter_title LIKE 'In-RAM%' LIMIT 1)),
  ('concept', 'AES-256-GCM decryption', '32-byte ASCII key extracted from language_server_macos_arm binary. File layout: [12-byte nonce][ciphertext][16-byte GCM tag]. Decrypt only in RAM.', 'pb_reader', 7, (SELECT chapter_id FROM chapters WHERE book_id=7 AND chapter_title LIKE 'Encryption%' LIMIT 1)),
  ('concept', 'Protobuf wire-format parsing', 'No .proto schema needed. Reads raw protobuf: VARINT, 64BIT, LENGTH, 32BIT, GROUP_START, GROUP_END. Empirically discovered variant fields for CortexTrajectoryStep.', 'pb_reader', 7, (SELECT chapter_id FROM chapters WHERE book_id=7 AND chapter_title LIKE 'Protobuf%' LIMIT 1)),
  ('process', 'PB Reader verification', 'Proven: 145 .pb files found (1 cascade, 1 implicit, 143 memories). Decrypted 3507-step conversation. Search found 3 matches for "language server". Export produced 238 markdown rounds.', 'pb_reader', 7, (SELECT chapter_id FROM chapters WHERE book_id=7 AND chapter_title LIKE 'Verified%' LIMIT 1));

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'produces', 1.0, 'pb_reader.py produces In-RAM SQLite with 6 tables'
  FROM nodes n1, nodes n2 WHERE n1.node_name='pb_reader.py' AND n2.node_name='In-RAM SQLite (:memory:)' AND n1.source_book_id=7;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'uses', 1.0, 'pb_reader.py uses AES-256-GCM decryption'
  FROM nodes n1, nodes n2 WHERE n1.node_name='pb_reader.py' AND n2.node_name='AES-256-GCM decryption' AND n1.source_book_id=7;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'uses', 1.0, 'pb_reader.py uses protobuf wire-format parsing'
  FROM nodes n1, nodes n2 WHERE n1.node_name='pb_reader.py' AND n2.node_name='Protobuf wire-format parsing' AND n1.source_book_id=7;
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'proven_result_of', 1.0, 'PB Reader verification: 145 files, 3507 steps, 100% recall'
  FROM nodes n1, nodes n2 WHERE n1.node_name='PB Reader verification' AND n2.node_name='pb_reader.py' AND n1.source_book_id=7;

UPDATE binary_artifacts SET artifact_name = 'pb_reader.py (Python, no compile)', artifact_type = 'python_tool', source_language = 'Python', source_code = 'chat_mover/pb_reader.py (1041 lines, VBStyle compliant)', compile_command = 'python3 pb_reader.py scan', compile_status = 'WORKING_NO_COMPILE_NEEDED', file_size_bytes = 0 WHERE book_id = 7;

UPDATE checks SET check_name = 'pb_scan_145_files', check_type = 'functional_verification', check_status = 'PASSING', check_result = 'Found 145 .pb files (1 cascade, 1 implicit, 143 memories)' WHERE book_id = 7;
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 7, (SELECT chapter_id FROM chapters WHERE book_id=7 AND chapter_title LIKE 'Verified%' LIMIT 1), 'pb_decrypt_3507_steps', 'functional_verification', 'PASSING', 'Decrypted a 3507-step Cascade conversation successfully';
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 7, (SELECT chapter_id FROM chapters WHERE book_id=7 AND chapter_title LIKE 'Verified%' LIMIT 1), 'pb_search_100pct_recall', 'functional_verification', 'PASSING', 'Search found 3 matches for "language server" in user messages. 100% recall vs 65% from checkpoints.';
INSERT INTO checks (book_id, chapter_id, check_name, check_type, check_status, check_result) SELECT 7, (SELECT chapter_id FROM chapters WHERE book_id=7 AND chapter_title LIKE 'VBStyle%' LIMIT 1), 'vbstyle_compliance', 'style_verification', 'PASSING', 'Run dispatch, Tuple3 returns, self.state dict, no print, no decorators, no self._, UPPERCASE constants';

INSERT OR IGNORE INTO glossary_terms (term, definition, sqlite_mapping) VALUES
  ('PB Reader', 'VBStyle tool for decrypting and searching encrypted .pb chat files. AES-256-GCM + protobuf + in-RAM SQLite. 100% recall vs 65% from checkpoints.', 'trajectories, steps, user_messages, assistant_messages, commands, checkpoints'),
  ('Protobuf wire-format', 'Raw protobuf parsing without .proto schema. Wire types: VARINT(0), 64BIT(1), LENGTH(2), 32BIT(5), GROUP_START(3), GROUP_END(4).', NULL);

INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes) SELECT file_path, 'pipelines_library.db:books.book_id=7', 'sqlite', file_hash, 7, 'Full markdown ingested (317 lines). 5 nodes, 4 links, 4 checks, 2 glossary terms. AES-256-GCM encryption details noted. 6-table in-RAM SQLite schema documented.' FROM books WHERE book_id = 7;
INSERT INTO pipeline_connections (from_book_id, to_book_id, connection_type, description, status) VALUES (7, 13, 'related_to', 'PB Reader is a specialized ingestion path for encrypted .pb files', 'ACTIVE');
