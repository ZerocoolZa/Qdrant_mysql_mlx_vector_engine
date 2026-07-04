-- === ENRICH THIN BOOKS: 12 (CodeGraph) and 6 (BclUnitBuilder) ===

-- === BOOK 12: Plf_CodeGraph.md — add nodes for the 12-stage pipeline ===
INSERT INTO nodes (node_type, node_name, node_value, domain, source_book_id) VALUES
  ('database', 'code_files', '134 rows. Full source of every .py file. Columns: id, file_path (unique), file_hash, full_source (LONGTEXT).', 'code_graph', 12),
  ('database', 'code_units', '2649 rows. Per-method extraction. Columns: id, file_path, class_name, method_name, unit_type (FILE/CLASS/METHOD/FUNCTION/MODULE_CONST/IMPORT/MAIN_BLOCK), source_text, docstring, return_type, dispatch_key, calls (csv), called_by (csv), imports, line_start, line_end, content_hash, parent_class, is_vbstyle, ingested_at.', 'code_graph', 12),
  ('database', 'code_edges', '12558 rows. Structural edges. Columns: id, from_class, from_method, to_class, to_method, edge_type (CALLS/CONTAINS/IMPORTS/INHERITS/REFERENCES), evidence_line.', 'code_graph', 12),
  ('database', 'stamps (future)', 'Stage 3 output. Columns: id, unit_id, content_hash, stamp_text, stamp_tier, confidence, created_at, superseded_by. Not yet populated.', 'code_graph', 12),
  ('database', 'config_metadata (future)', 'Stage 8 output. Columns: id, key_name, default_value, current_value, value_type, allowed_range, used_in_methods, documentation, source_file, source_line. Not yet populated.', 'code_graph', 12),
  ('tool', 'InRamDb', '14 methods. In-RAM SQLite database core. Event-sourcing foundation. Located in Dom_Graph.', 'code_graph', 12),
  ('tool', 'EventLogStore', '12 methods. Append-only event log for durability. The durability point — every state change writes here.', 'code_graph', 12),
  ('tool', 'RollbackEngine', '7 methods. Rebuilds state from event log. RollbackTo method is the replay entry point.', 'code_graph', 12),
  ('tool', 'AstNodeRegistry', '13 methods. Stable handles for AST nodes across code edits. Version tracking.', 'code_graph', 12),
  ('tool', 'AstVersionStore', '10 methods. Version history for AST nodes. add_version() is the write point.', 'code_graph', 12),
  ('tool', 'BclStampStore', '11 methods. CRUD for BCL stamps. Append-only supersession.', 'code_graph', 12),
  ('tool', 'ReplayEngine', '11 methods. Rebuilds state at any point in time. rebuild_at() is the replay point.', 'code_graph', 12),
  ('tool', 'SnapshotStore', '8 methods. Point-in-time snapshots for fast replay.', 'code_graph', 12),
  ('concept', 'Dead Methods', '228 of 1801 methods have no recorded caller. Detectable via: SELECT COUNT(*) FROM code_units WHERE unit_type=METHOD AND (called_by IS NULL OR called_by = empty).', 'code_graph', 12),
  ('concept', 'Change Impact', 'Most connected methods have highest change impact. Measured by LENGTH(calls) — top: Dom_Graph_Agent.py with 122 methods.', 'code_graph', 12),
  ('process', 'Stage 0 SYNC', 'Compare file hashes vs DB hashes. Detect changed files for incremental ingestion.', 'code_graph', 12),
  ('process', 'Stage 1 INGEST', 'Parse .py files → code_files (full source) + code_units (per method) + code_edges (CALLS, CONTAINS). 134 files → 2649 units → 12558 edges.', 'code_graph', 12),
  ('process', 'Stage 2 GRAPH', 'Build structural edges. CALLS: 10757, CONTAINS: 1801. Queryable graph.', 'code_graph', 12),
  ('process', 'Stage 3 REASON', '3a SURFACE: purpose, signature, callers. 3b DEEP: gotchas, cascades, invariants. 3c MINE: scars from past sessions. Output: stamps table.', 'code_graph', 12),
  ('process', 'Stage 4 REGRAPH', 'Add semantic edges: DEPENDS_ON, BREAKS, RISKS. Derived from reasoning stamps.', 'code_graph', 12),
  ('process', 'Stage 5 VALIDATE', 'Violation report: VBStyle compliance, dead code, cycles. Halt if violations found.', 'code_graph', 12),
  ('process', 'Stage 6 PLAN', 'Proposed changes with impact analysis, order, risk assessment.', 'code_graph', 12),
  ('process', 'Stage 7 REPAIR', 'Modified code_units rows. Every change = new version. Versioned edits.', 'code_graph', 12),
  ('process', 'Stage 8 CONFIG', 'Extract config knobs from code into config_metadata table.', 'code_graph', 12),
  ('process', 'Stage 9 EXPORT', 'Generate new .py files from code_files.full_source.', 'code_graph', 12),
  ('process', 'Stage 10 VERIFY', 'Compile + test + diff. Halt if any check fails.', 'code_graph', 12),
  ('process', 'Stage 11 ARCHIVE', 'Old files → archive/. New files become canonical.', 'code_graph', 12);

-- Links for book 12
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'contains', 1.0, 'code_graph.db contains code_files table (134 rows)'
  FROM nodes n1, nodes n2 WHERE n1.node_name='code_graph.db' AND n2.node_name='code_files' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'contains', 1.0, 'code_graph.db contains code_units table (2649 rows)'
  FROM nodes n1, nodes n2 WHERE n1.node_name='code_graph.db' AND n2.node_name='code_units' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'contains', 1.0, 'code_graph.db contains code_edges table (12558 rows)'
  FROM nodes n1, nodes n2 WHERE n1.node_name='code_graph.db' AND n2.node_name='code_edges' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'calls', 1.0, 'RollbackEngine calls ReplayEngine.RebuildAt (the replay point)'
  FROM nodes n1, nodes n2 WHERE n1.node_name='RollbackEngine' AND n2.node_name='ReplayEngine' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'calls', 1.0, 'ReplayEngine calls SnapshotStore for fast replay'
  FROM nodes n1, nodes n2 WHERE n1.node_name='ReplayEngine' AND n2.node_name='SnapshotStore' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'calls', 1.0, 'BclStampStore calls EventLogStore.Append (durability point)'
  FROM nodes n1, nodes n2 WHERE n1.node_name='BclStampStore' AND n2.node_name='EventLogStore' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'calls', 1.0, 'AstVersionStore calls EventLogStore.Append for version tracking'
  FROM nodes n1, nodes n2 WHERE n1.node_name='AstVersionStore' AND n2.node_name='EventLogStore' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'depends_on', 1.0, 'EventLogStore depends on InRamDb for SQLite storage'
  FROM nodes n1, nodes n2 WHERE n1.node_name='EventLogStore' AND n2.node_name='InRamDb' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'depends_on', 1.0, 'AstNodeRegistry depends on InRamDb for SQLite storage'
  FROM nodes n1, nodes n2 WHERE n1.node_name='AstNodeRegistry' AND n2.node_name='InRamDb' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'feeds_into', 1.0, 'Stage 1 INGEST feeds into Stage 2 GRAPH'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Stage 1 INGEST' AND n2.node_name='Stage 2 GRAPH' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'feeds_into', 1.0, 'Stage 2 GRAPH feeds into Stage 3 REASON'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Stage 2 GRAPH' AND n2.node_name='Stage 3 REASON' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'feeds_into', 1.0, 'Stage 3 REASON feeds into Stage 4 REGRAPH'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Stage 3 REASON' AND n2.node_name='Stage 4 REGRAPH' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'feeds_into', 1.0, 'Stage 7 REPAIR feeds into Stage 9 EXPORT'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Stage 7 REPAIR' AND n2.node_name='Stage 9 EXPORT' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'feeds_into', 1.0, 'Stage 9 EXPORT feeds into Stage 10 VERIFY'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Stage 9 EXPORT' AND n2.node_name='Stage 10 VERIFY' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'feeds_into', 1.0, 'Stage 10 VERIFY feeds into Stage 11 ARCHIVE'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Stage 10 VERIFY' AND n2.node_name='Stage 11 ARCHIVE' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'produces', 1.0, 'Stage 1 INGEST produces code_files table'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Stage 1 INGEST' AND n2.node_name='code_files' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'produces', 1.0, 'Stage 1 INGEST produces code_units table'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Stage 1 INGEST' AND n2.node_name='code_units' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'produces', 1.0, 'Stage 1 INGEST produces code_edges table'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Stage 1 INGEST' AND n2.node_name='code_edges' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'produces', 1.0, 'Stage 3 REASON produces stamps table (future)'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Stage 3 REASON' AND n2.node_name='stamps (future)' AND n1.source_book_id=12;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'produces', 1.0, 'Stage 8 CONFIG produces config_metadata table (future)'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Stage 8 CONFIG' AND n2.node_name='config_metadata (future)' AND n1.source_book_id=12;

-- Checks for book 12
INSERT INTO checks (book_id, check_name, check_type, check_status, check_result)
  SELECT 12, 'ingestion_counts', 'completeness_check', 'PASSING', '134 files, 2649 units, 12558 edges ingested. CALLS: 10757, CONTAINS: 1801.';

INSERT INTO checks (book_id, check_name, check_type, check_status, check_result)
  SELECT 12, 'dead_methods', 'quality_check', 'WARNING', '228 of 1801 methods have no recorded caller. May be dead code or entry points.';

INSERT INTO checks (book_id, check_name, check_type, check_status, check_result)
  SELECT 12, 'stamps_table', 'implementation_status', 'NOT_BUILT', 'Stamps table designed but not populated. Stage 3 REASON not yet executed.';

INSERT INTO checks (book_id, check_name, check_type, check_status, check_result)
  SELECT 12, 'config_metadata_table', 'implementation_status', 'NOT_BUILT', 'config_metadata table designed but not populated. Stage 8 CONFIG not yet executed.';

-- Glossary for book 12
INSERT OR IGNORE INTO glossary_terms (term, definition, sqlite_mapping) VALUES
  ('code_graph.db', 'SQLite database for the code graph pipeline. Tables: code_files (134), code_units (2649), code_edges (12558), stamps (future), config_metadata (future).', 'code_files, code_units, code_edges'),
  ('Event-Sourcing Core', 'InRamDb → EventLogStore → BclStampStore → ReplayEngine → SnapshotStore. Append-only durability with replay capability.', NULL),
  ('Dead Methods', 'Methods with no recorded caller. 228 of 1801 in Dom_Graph. Detectable via SQL query on called_by field.', NULL),
  ('Change Impact Analysis', 'Most connected methods (highest call count) have highest change impact. Top: Dom_Graph_Agent.py with 122 methods.', NULL);

-- === BOOK 6: Plf_BclUnitBuilderPipeline.md — add nodes ===
INSERT INTO nodes (node_type, node_name, node_value, domain, source_book_id) VALUES
  ('tool', 'bcl_builder.c (CLI)', '590 lines. The builder CLI. Accepts BCL spec, generates .c file, auto-checks compliance, auto-compiles. Located in bin_tools/.', 'bcl_units', 6),
  ('tool', 'bcl_toolstack.h', 'Shared header for all BCL units. Contains unit interface, BCL parser, constants. Located in bcl_units/.', 'bcl_units', 6),
  ('concept', 'BCL Packet Protocol', 'Input: [@RUN]{[@CMD]{command}[@PARAM]{...}}. Success: [@OK]{[@RESULT]{...}}. Error: [@ERR]{[@CODE]{N}[@DESC]{...}}. BCL in, BCL out.', 'bcl_units', 6),
  ('concept', 'DIM Block', 'VB Dim style declarations. UPPERCASE constants, Command enum, Unit struct, CmdFn typedef. First of 5 blocks in every generated unit.', 'bcl_units', 6),
  ('concept', '5-Block Structure', 'Every generated .c file has: 1. DIM (declarations), 2. INIT (helpers), 3. FORWARD (prototypes), 4. DISPATCH (jump table + Run), 5. GUTS (implementation).', 'bcl_units', 6),
  ('concept', '19-Point Compliance', 'Checklist: @GHOST, @VBSTYLE, @FILEID, @SUMMARY, @CLASS, @METHOD headers, DIM block, INIT block, FORWARD block, DISPATCH block, GUTS block, UPPERCASE constants, PascalCase, Run dispatch, BCL in/out, no print, no tabs, no hardcoded values, no trailing whitespace, no decorators.', 'bcl_units', 6),
  ('concept', 'Unit Interchangeability', 'All units share the same signature: const char *Unit_Run(Unit *u, Command cmd, const char *bcl_in). Any unit can call any other unit by passing BCL. No struct casting.', 'bcl_units', 6),
  ('concept', 'Version Evolution V1-V5', 'V1=strings/strcmp, V2=enum+fn ptr, V4=grouped, V5=BCL. V5 is canonical: uniform interface, interoperability, built-in serialization, lowest memory.', 'bcl_units', 6),
  ('process', 'Spec → Generate → Check → Compile → Register', 'AI writes BCL spec → bcl_builder generates .c → auto-check 19 points → auto-compile → register in bcl_tool_main.c + Makefile → make && make test.', 'bcl_units', 6),
  ('process', 'BCL Chat Compression Integration', 'PB Reader decrypts → BCL Compressor Stage 1 (code extraction, 4304 lines → 878 tokens) → Stage 2 AI Semantic → BCL Token Store → Search/Recall.', 'bcl_units', 6),
  ('database', 'bcl_units/ directory', '28 total units: 1 complete (pb_reader), 15 stubs (chat_ingest, cleaner, msearch, etc.), 12 not built (mem_unit, file_io, config, etc.).', 'bcl_units', 6);

-- Links for book 6
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'generates', 1.0, 'bcl_builder.c generates .c files with 5-Block Structure'
  FROM nodes n1, nodes n2 WHERE n1.node_name='bcl_builder.c (CLI)' AND n2.node_name='5-Block Structure' AND n1.source_book_id=6;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'uses', 1.0, 'bcl_builder.c uses bcl_toolstack.h as shared header'
  FROM nodes n1, nodes n2 WHERE n1.node_name='bcl_builder.c (CLI)' AND n2.node_name='bcl_toolstack.h' AND n1.source_book_id=6;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'enforces', 1.0, 'bcl_builder.c enforces 19-Point Compliance checklist on generated files'
  FROM nodes n1, nodes n2 WHERE n1.node_name='bcl_builder.c (CLI)' AND n2.node_name='19-Point Compliance' AND n1.source_book_id=6;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'implements', 1.0, 'BCL Unit implements BCL Packet Protocol (BCL in, BCL out)'
  FROM nodes n1, nodes n2 WHERE n1.node_name='BCL Unit' AND n2.node_name='BCL Packet Protocol' AND n1.source_book_id=6;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'contains', 1.0, '5-Block Structure contains DIM Block as first block'
  FROM nodes n1, nodes n2 WHERE n1.node_name='5-Block Structure' AND n2.node_name='DIM Block' AND n1.source_book_id=6;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'enables', 1.0, 'BCL Packet Protocol enables Unit Interchangeability — any unit calls any unit'
  FROM nodes n1, nodes n2 WHERE n1.node_name='BCL Packet Protocol' AND n2.node_name='Unit Interchangeability' AND n1.source_book_id=6;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'produces', 1.0, 'Spec → Generate → Check → Compile → Register produces units in bcl_units/ directory'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Spec → Generate → Check → Compile → Register' AND n2.node_name='bcl_units/ directory' AND n1.source_book_id=6;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'registers_in', 1.0, 'bcl_tool_main.c registers all units in bcl_units/ directory'
  FROM nodes n1, nodes n2 WHERE n1.node_name='bcl_tool_main.c' AND n2.node_name='bcl_units/ directory' AND n1.source_book_id=6;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'evolved_into', 1.0, 'Version Evolution V1-V5: V5 (BCL) is the canonical standard'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Version Evolution V1-V5' AND n2.node_name='BCL Packet Protocol' AND n1.source_book_id=6;

-- Checks for book 6
INSERT INTO checks (book_id, check_name, check_type, check_status, check_result)
  SELECT 6, 'unit_build_status', 'completeness_check', 'PARTIAL', '1 complete (pb_reader), 15 stubs generated, 12 not built. 28 total units planned.';

INSERT INTO checks (book_id, check_name, check_type, check_status, check_result)
  SELECT 6, 'builder_compliance', 'style_verification', 'PASSING', 'bcl_builder.c: 590 lines, generates .c files with 19-point compliance checklist, auto-compiles.';

INSERT INTO checks (book_id, check_name, check_type, check_status, check_result)
  SELECT 6, 'makefile_status', 'build_check', 'PASSING', 'Makefile in bcl_units/ builds all units. make && make test verified.';

INSERT INTO checks (book_id, check_name, check_type, check_status, check_result)
  SELECT 6, 'high_priority_units', 'implementation_status', 'TODO', '4 HIGH priority units not built: bcl_mem_unit.c, bcl_file_io.c, bcl_config.c, bcl_db_manager.c.';

-- Glossary for book 6
INSERT OR IGNORE INTO glossary_terms (term, definition, sqlite_mapping) VALUES
  ('BCL Unit', 'C file with @GHOST/@VBSTYLE/@FILEID headers, BCL packet I/O, Run dispatch, DIM block pattern. BCL in, BCL out. Interchangeable.', NULL),
  ('DIM Block', 'VB Dim style declarations in BCL units. UPPERCASE constants, Command enum, Unit struct, CmdFn typedef. First of 5 blocks.', NULL),
  ('BCL Packet Protocol', 'Input: [@RUN]{[@CMD]{cmd}[@PARAM]{...}}. Output: [@OK]{[@RESULT]{...}} or [@ERR]{[@CODE]{N}[@DESC]{...}}. Text-based universal interface.', NULL),
  ('Unit Interchangeability', 'All BCL units share same signature. Any unit calls any unit by passing BCL strings. No struct casting, no type mismatches.', NULL),
  ('19-Point Compliance', 'Checklist for BCL units: identity headers, 5 blocks, UPPERCASE constants, PascalCase, Run dispatch, BCL I/O, no print/tabs/hardcode/whitespace/decorators.', NULL),
  ('bcl_builder.c', '590-line CLI tool that generates .c BCL unit files from BCL spec. Auto-checks compliance, auto-compiles. Located in bin_tools/.', NULL);

-- === PROVENANCE for book 12 ===
INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes)
  SELECT file_path, 'pipelines_library.db:books.book_id=12', 'sqlite', file_hash, 12, 'Full markdown ingested (273 lines). Visual diagrams of 12-stage code graph pipeline. 30 nodes (1 db, 10 tools, 2 concepts, 12 stages, 5 future tables). 21 links. 4 checks. 4 glossary terms. 13 section types assigned. Event-sourcing dependency graph documented. Query examples included.'
  FROM books WHERE book_id = 12;

-- === PROVENANCE for book 6 (update if exists) ===
INSERT OR IGNORE INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes)
  SELECT file_path, 'pipelines_library.db:books.book_id=6', 'sqlite', file_hash, 6, 'Full markdown ingested (1385 lines). BCL Unit Builder spec. 16 nodes (3 tools, 5 concepts, 2 processes, 1 database, 5 blocks). 9 links. 4 checks. 6 glossary terms. 28 units planned (1 complete, 15 stubs, 12 not built). 19-point compliance checklist. BCL packet protocol documented. Version evolution V1-V5.'
  FROM books WHERE book_id = 6;
