-- ============================================================
-- BATCH 7: Semantic population for books 26, 27, 29
-- Book 26: Plf_MemunitBclEngine.md (central BCL execution engine base class)
-- Book 27: Plf_MemunitReferences.md (MySQL database search results for MemUnit)
-- Book 29: Plf_PipelineBclCodeLifecycle.md (code lifecycle cycle: ingest→reuse→weight→retire→sync→recover)
-- ============================================================
-- Starting IDs: nodes=282, links=198, glossary=106, checks=99, provenance=24, connections=52
-- ============================================================

-- ─── BOOK 26: MemunitBclEngine ───

UPDATE books SET core_thesis = 'MemUnit: central BCL execution engine base class. Every VBStyle class inherits from it. Owns parser, dispatch, validation, result wrapping, cleanup. Subclasses only define ACTIONS dict + method bodies. Eliminates 224 duplicated dispatch tables.', status = 'design', sqlite_backend = 'mysql+sqlite' WHERE book_id = 26;

-- Section semantic roles
UPDATE sections SET section_type = 'bcl_parser_features' WHERE section_id = 529;
UPDATE sections SET section_type = 'memunit_integration' WHERE section_id = 530;

-- Nodes for book 26
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(282, 'tool', 'MemUnit', 'Base class for all VBStyle classes. Owns BCL parser, dispatch builder, param validator, result wrapper, cleanup. 224 classes inherit from it.', 'engine', 0.95, 26, 301),
(283, 'concept', 'ACTIONS Schema', 'Dict mapping command strings to required param tuples. Subclasses define this instead of dispatch tables. Auto-builds dispatch from ACTIONS.', 'architecture', 0.90, 26, 310),
(284, 'concept', '6-Stage Pipeline', 'PARSE → VALIDATE → DISPATCH → EXECUTE → WRAP → CLEANUP. MemUnit owns all 6 stages. Subclass only provides method body for stage 4.', 'architecture', 0.85, 26, 302),
(285, 'concept', 'Dual Input Forms', 'Form 1: Python Run("search", {"query":"mysql"}). Form 2: BCL Run("[@Run]{(\"command\";\"search\");(\"query\";\"mysql\")}"). Both produce Tuple3.', 'bcl', 0.80, 26, 306),
(286, 'concept', 'Tuple3 Output', 'Always returns (ok, data, error). ok=1 success, ok=0 failure. Optionally wrapped as [@Pass] or [@Fail] BCL token.', 'bcl', 0.85, 26, 308),
(287, 'concept', 'CommandToMethod', 'command.split("_") → capitalize each word → join. "search"→Search(), "add_class"→AddClass(). Simple, deterministic, no explicit mapping needed.', 'architecture', 0.75, 26, 312),
(288, 'concept', 'No Dispatch Table Duplication', 'Before: 224 classes × 224 dispatch tables × 224 copies of same pattern. After: 1 MemUnit base, subclasses only define ACTIONS + methods.', 'architecture', 0.85, 26, 313),
(289, 'concept', 'BCL Input/Output Contract', 'BCL in: [@Run]{("command";"search");("query";"mysql")}. BCL out: [@Pass]{("data";{...})} or [@Fail]{("error";"...")}. Enables inter-system communication.', 'bcl', 0.80, 26, 309),
(290, 'concept', '5-Phase Migration', 'Phase 1: Create MemUnit. Phase 2: Migrate GraphEngine. Phase 3: Migrate remaining engine classes. Phase 4: Auto-migrate 224 vb_code_test classes. Phase 5: Enable BCL I/O.', 'migration', 0.75, 26, 315),
(291, 'database', 'vb_shared.rules (MemUnit)', '6 rules: id=2 state structure, id=15 Run dispatch, id=32 no hidden behavior, id=41 all code in memunit, id=223 MemUnit owner of param validate execute cleanup, id=268 capability metadata', 'database', 0.75, 26, 320),
(292, 'database', 'vb_shared.learned_rules (MemUnit)', '15 learned rules: memunit owner, resolves all binding, must declare memunit authority, do not bypass memunit, do not replace working memunit methods, execution goes through memunit', 'database', 0.75, 26, 321),
(293, 'database', 'vb_shared.tokens (MemUnit)', '2 tokens: [@CascadeSearchMemDb] (VBStyle architecture, MemDB SQLite in-memory), [@bcl-command] (BCL Command form, active, run through MemUnit)', 'database', 0.70, 26, 322),
(294, 'concept', 'Rule 223: MemUnit Owner', 'MemUnit owner of param validate execute cleanup. Must: MemUnit owns all 6 pipeline stages. Subclasses must not reimplement parse/validate/dispatch/wrap/cleanup.', 'governance', 0.85, 26, 323),
(295, 'concept', 'Rule 269: MEMUNIT Resolves Binding', 'No class ever binds itself. No method ever belongs to a class. Everything resolved at runtime by MEMUNIT during orchestration graph construction.', 'governance', 0.80, 26, 323),
(296, 'concept', 'Critical Finding: BCLParser Ready', 'BCL parser from bcl_parser.py already handles MemUnit input parsing. No new parser needed. parse_text() → AST → root.tuples → command + params dict.', 'bcl', 0.75, 26, 324),
(297, 'concept', 'Why Dual Input', 'Python form for development/debugging (direct, fast). BCL form for inter-system communication (serialized, protocol-level). Both produce same Tuple3 result.', 'architecture', 0.70, 26, 325),
(298, 'concept', 'Why ACTIONS Not Decorators', 'Decorators hide structure, require import-time evaluation, hard to introspect. ACTIONS dict is explicit, visible, runtime-queryable, matches VBStyle no-decorators rule.', 'architecture', 0.70, 26, 326),
(299, 'concept', 'Why Not Enums', 'Enums add a layer of indirection, violate VBStyle no-enum rule, require import-time definition. String commands are simpler, match BCL token format, debuggable.', 'architecture', 0.65, 26, 327),
(300, 'concept', 'Why CommandToMethod', 'Avoids explicit mapping dict (another thing to maintain). Convention over configuration. "search"→Search() is deterministic, no ambiguity, no lookup table.', 'architecture', 0.65, 26, 328);

-- Links for book 26
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(198, 282, 283, 'uses', 1.0, 'MemUnit uses ACTIONS schema for auto-dispatch'),
(199, 282, 284, 'implements', 1.0, 'MemUnit implements 6-stage pipeline'),
(200, 282, 285, 'supports', 1.0, 'MemUnit supports dual input forms'),
(201, 282, 286, 'produces', 1.0, 'MemUnit always produces Tuple3 output'),
(202, 282, 287, 'uses', 1.0, 'MemUnit uses CommandToMethod for dispatch'),
(203, 283, 288, 'eliminates', 1.0, 'ACTIONS schema eliminates dispatch table duplication'),
(204, 282, 289, 'enables', 0.8, 'MemUnit enables BCL I/O contract'),
(205, 290, 282, 'creates', 1.0, 'Phase 1 creates MemUnit base class'),
(206, 291, 282, 'governs', 0.8, '6 vb_shared.rules govern MemUnit behavior'),
(207, 292, 282, 'constrains', 0.8, '15 learned_rules constrain MemUnit usage'),
(208, 293, 282, 'documents', 0.6, '2 tokens document MemUnit in BCL format'),
(209, 294, 282, 'mandates', 1.0, 'Rule 223 mandates MemUnit owns all 6 stages'),
(210, 295, 282, 'mandates', 1.0, 'Rule 269 mandates MemUnit resolves all binding'),
(211, 296, 282, 'enables', 0.8, 'BCLParser readiness enables MemUnit BCL input'),
(212, 297, 285, 'justifies', 0.7, 'Dual input justified by dev vs protocol needs'),
(213, 298, 283, 'justifies', 0.7, 'ACTIONS over decorators justified by explicitness'),
(214, 299, 283, 'justifies', 0.6, 'String commands over enums justified by simplicity'),
(215, 300, 287, 'justifies', 0.6, 'CommandToMethod justified by convention over config');

-- Glossary terms for book 26
INSERT OR IGNORE INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(106, 'MemUnit', 'Central BCL execution engine base class. Owns parser, dispatch, validation, result wrapping, cleanup. Every VBStyle class inherits from it.', 'engine', 'nodes.node_name=MemUnit'),
(107, 'ACTIONS Schema', 'Dict mapping command strings to required param tuples. Replaces 224 duplicated dispatch tables with one declarative schema per subclass.', 'architecture', 'nodes.node_name=ACTIONS Schema'),
(108, '6-Stage MemUnit Pipeline', 'PARSE → VALIDATE → DISPATCH → EXECUTE → WRAP → CLEANUP. MemUnit owns all stages, subclass provides only method body.', 'architecture', 'nodes.node_name=6-Stage Pipeline'),
(109, 'CommandToMethod', 'Convention: command.split("_") → capitalize each → join. "search"→Search(), "add_class"→AddClass(). No explicit mapping needed.', 'architecture', 'nodes.node_name=CommandToMethod');

-- Glossary links for book 26
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) VALUES
(106, 26, 301, NULL, 'primary'),
(107, 26, 310, NULL, 'primary'),
(108, 26, 302, NULL, 'primary'),
(109, 26, 312, NULL, 'primary');

-- Checks for book 26
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(99, 26, 324, 'BCLParser integration readiness', 'structure', 'PASS', 'BCL parser from bcl_parser.py handles MemUnit input. parse_text() → AST → tuples → command + params. No new parser needed.'),
(100, 26, 323, 'MySQL knowledge base alignment', 'compliance', 'PASS', '6 rules + 15 learned_rules + 2 tokens in vb_shared govern MemUnit. Rule 223 and 269 are key mandates.'),
(101, 26, 315, 'Migration plan completeness', 'structure', 'PASS', '5 phases: create base, migrate GraphEngine, migrate engine classes, auto-migrate 224 DB classes, enable BCL I/O');

-- Provenance for book 26
INSERT INTO provenance (provenance_id, source_path, dest_path, dest_type, book_id, notes) VALUES
(24, 'core/Dom_Bcl/bcl_parser.py + vb_shared.rules + vb_shared.learned_rules', 'Plf_MemunitBclEngine.md', 'markdown', 26, 'Design document for MemUnit base class, fourth design group');

-- Pipeline connections for book 26
INSERT INTO pipeline_connections (connection_id, from_book_id, to_book_id, connection_type, description, status) VALUES
(52, 26, 23, 'enables', 'MemUnit enables GraphEngine spec: subclasses only define ACTIONS + methods', 'active'),
(53, 26, 29, 'used_by', 'MemUnit dispatch used by BCL code lifecycle pipeline (DomReuse.Run)', 'active'),
(54, 26, 6, 'implements', 'MemUnit implements BCL Code Graph pipeline execution layer', 'active');

-- ─── BOOK 27: MemunitReferences ───

UPDATE books SET core_thesis = 'MySQL database search results for MemUnit references across 4 databases (vb_shared, vb_code_test, CODEBASE, vbstyle_documents). 1901 unique hits across 38 tables. 11335 file paths found. Reference inventory for MemUnit adoption scope.', status = 'reference', sqlite_backend = 'mysql' WHERE book_id = 27;

-- Nodes for book 27
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(301, 'data_model', 'MemUnit Hit Distribution', '1901 total hits: vb_code_test.vb_methods (487), vb_code_test.vb_classes (378), CODEBASE.file_archive (249), vb_shared.code_index (120), vb_shared.chat_ingestions (90), vb_shared.code_classes (87)', 'database', 0.80, 27, 329),
(302, 'database', 'CODEBASE.file_archive', '249 hits — largest CODEBASE source. Historical file archive containing MemUnit references across code versions', 'database', 0.65, 27, 331),
(303, 'database', 'vb_code_test.vb_methods', '487 hits — highest hit count. Methods in VB code test database referencing MemUnit. Indicates broad adoption in method-level code', 'database', 0.75, 27, 331),
(304, 'database', 'vb_code_test.vb_classes', '378 hits — second highest. Classes referencing MemUnit. Indicates class-level inheritance pattern already exists in DB', 'database', 0.75, 27, 331),
(305, 'database', 'vb_shared.code_index', '120 hits — code index entries referencing MemUnit. Cross-domain code registry', 'database', 0.65, 27, 331),
(306, 'database', 'vb_shared.chat_ingestions', '90 hits — chat conversations mentioning MemUnit. Design discussions, usage patterns, troubleshooting', 'database', 0.60, 27, 331),
(307, 'database', 'vb_shared.learned_rules (ref)', '37 hits — learned rules about MemUnit usage. Prohibition: do not bypass memunit, do not replace working memunit methods', 'database', 0.70, 27, 331),
(308, 'database', 'vb_shared.code_co_occurrence', '48 hits — MemUnit co-occurs with other concepts. Shows what MemUnit is discussed alongside', 'database', 0.55, 27, 331),
(309, 'database', 'vb_shared.code_identifier_frequency', '54 hits — MemUnit as identifier in code. Frequency analysis of usage', 'database', 0.55, 27, 331),
(310, 'database', 'vb_shared.designrationale', '29 hits — design rationale documents mentioning MemUnit. Architecture decisions, design discussions', 'database', 0.60, 27, 331),
(311, 'concept', '11335 File Paths', 'File paths found in MySQL rows that also mention MemUnit. Python files, markdown files, SQL/DB files, Swift files across /Users/Shared and project directories', 'reference', 0.65, 27, 330),
(312, 'concept', 'MemUnit Adoption Scope', '1901 hits across 38 tables in 4 databases. MemUnit is not a new concept — it is deeply embedded in the codebase knowledge base already', 'reference', 0.75, 27, 329),
(313, 'concept', 'Key Tables Analysis', 'Top 5 tables by hit count: vb_methods (487), vb_classes (378), file_archive (249), code_index (120), chat_ingestions (90). Method+class dominance shows MemUnit is code-level pattern', 'reference', 0.70, 27, 332),
(314, 'concept', 'Search Methodology', 'Searched 4 databases (vb_shared, vb_code_test, CODEBASE, vbstyle_documents) with 8 search terms: MemUnit, memunit, MEMUNIT, Memunit, Core_MainUnit, core_memunit, CORE_MEMUNIT. 1901 unique hits', 'reference', 0.60, 27, 333);

-- Links for book 27
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(216, 301, 303, 'includes', 1.0, 'Hit distribution includes vb_methods (487 hits)'),
(217, 301, 304, 'includes', 1.0, 'Hit distribution includes vb_classes (378 hits)'),
(218, 301, 302, 'includes', 0.8, 'Hit distribution includes file_archive (249 hits)'),
(219, 301, 305, 'includes', 0.8, 'Hit distribution includes code_index (120 hits)'),
(220, 301, 306, 'includes', 0.7, 'Hit distribution includes chat_ingestions (90 hits)'),
(221, 312, 301, 'summarized_by', 1.0, 'Adoption scope summarized by hit distribution'),
(222, 313, 303, 'highlights', 1.0, 'Key tables analysis highlights vb_methods as top'),
(223, 313, 304, 'highlights', 1.0, 'Key tables analysis highlights vb_classes as second'),
(224, 314, 301, 'produces', 1.0, 'Search methodology produces hit distribution'),
(225, 311, 312, 'evidences', 0.7, '11335 file paths evidence MemUnit adoption scope'),
(226, 307, 292, 'overlaps', 0.8, 'learned_rules references overlap with book 26 MemUnit rules');

-- Glossary terms for book 27
INSERT OR IGNORE INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(110, 'MemUnit Reference Inventory', '1901 unique hits across 38 tables in 4 databases. 11335 file paths. MemUnit is deeply embedded in the codebase knowledge base.', 'reference', 'nodes.node_name=MemUnit Adoption Scope');

-- Glossary links for book 27
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) VALUES
(110, 27, 329, NULL, 'primary');

-- Checks for book 27
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(102, 27, 329, 'Database coverage', 'structure', 'PASS', '4 databases searched: vb_shared, vb_code_test, CODEBASE, vbstyle_documents. 38 tables had hits.'),
(103, 27, 333, 'Search term coverage', 'compliance', 'PASS', '8 search terms used: MemUnit, memunit, MEMUNIT, Memunit, Core_MainUnit, core_memunit, CORE_MEMUNIT. Case-insensitive coverage.');

-- Provenance for book 27
INSERT INTO provenance (provenance_id, source_path, dest_path, dest_type, book_id, notes) VALUES
(25, 'MySQL: vb_shared + vb_code_test + CODEBASE + vbstyle_documents', 'Plf_MemunitReferences.md', 'markdown', 27, 'Auto-generated MySQL database search results for MemUnit references, generated 2026-06-23');

-- Pipeline connections for book 27
INSERT INTO pipeline_connections (connection_id, from_book_id, to_book_id, connection_type, description, status) VALUES
(55, 27, 26, 'informs', 'Reference inventory informs MemUnit base class design about adoption scope', 'active'),
(56, 27, 23, 'supports', 'Reference inventory supports graph ingest spec with MemUnit adoption data', 'active');

-- ─── BOOK 29: PipelineBclCodeLifecycle ───

UPDATE books SET core_thesis = 'BCL Code Lifecycle: INGEST→REUSE→WEIGHT→PURGE→RETIRE→SYNC→RECOVER cycle. DB is source of truth, files are cache. Code never leaves DB. [@clean] mark replaces rm. gc_delete checks DB before deleting. Status: active/retired/superseded/dead.', status = 'design', sqlite_backend = 'mysql+sqlite' WHERE book_id = 29;

-- Nodes for book 29
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(315, 'concept', 'Code Lifecycle Cycle', 'INGEST→REUSE→WEIGHT→PURGE→RETIRE→SYNC→RECOVER. Not a pipeline — a cycle. Code flows around it forever. DB is source of truth, files are cache.', 'lifecycle', 0.95, 29, 351),
(316, 'tool', 'DomReuse', 'Code retrieval before generation. Commands: find, retrieve, deliver, test, fix, reweight, strongest, weakest, purge. Extended with retire_sweep, sync, recover, gc_delete.', 'engine', 0.90, 29, 352),
(317, 'concept', '[@clean] Mark', 'BCL tag wrapping retired code in triple-quoted string. File stays valid Python. BCL headers travel inside string. @bcl_method_id links to DB row. No dumpster table needed.', 'bcl', 0.90, 29, 355),
(318, 'concept', 'gc_delete', 'The rm replacement. Checks if ALL classes/methods in file are in DB. YES→strip defs, trash file, status=retired. NO→BLOCK (code would be lost forever). AI never runs rm directly.', 'security', 0.95, 29, 353),
(319, 'concept', 'retire_sweep', 'Walk codebase, find [@clean:MARK]...[@clean:END] blocks. For each: extract bcl_method_id, UPDATE status=retired, mark edges SUPERSEDED, remove block from file.', 'lifecycle', 0.85, 29, 353),
(320, 'concept', 'sync', 'Detect changed methods in files. Compute AST hash, compare to DB. If different: old row status=superseded, INSERT new row with version+1. Old version kept, recoverable.', 'lifecycle', 0.80, 29, 353),
(321, 'concept', 'recover', 'Restore retired/superseded method from DB to file. SELECT source code, write to file, UPDATE status=active, restore edges from SUPERSEDED to ACTIVE, increment recover_count.', 'lifecycle', 0.80, 29, 353),
(322, 'concept', 'Weighting System', 'Reused +1, Fixed -2/+1, VBStyle compliant +5, Has tests +3, Has BCL +2, No violations +2, High complexity -1, Dead/month -1, Duplicated -3. Purge at -5.', 'lifecycle', 0.75, 29, 352),
(323, 'data_model', 'bcl_methods lifecycle columns', 'ADD: status (active/retired/superseded/dead), version, retired_at, retire_reason, recovered_at, recover_count, superseded_by. Schema migration NOT yet run.', 'database', 0.85, 29, 354),
(324, 'data_model', 'bcl_edges lifecycle column', 'ADD: edge_status (active/superseded/retired). Graph becomes time-aware: query active graph vs full history vs changes since last week.', 'database', 0.75, 29, 354),
(325, 'concept', 'Triple-Quoted String Trick', 'Retired code wrapped in _CLEAN_BCL_ = """...""". File stays valid Python. py_compile always passes. BCL headers inside preserve provenance. GC parser finds string literals with [@clean:MARK].', 'bcl', 0.85, 29, 355),
(326, 'concept', 'No Dumpster Table', 'Existing bcl_methods/bcl_classes ARE the permanent store. Retired method = row with status=retired. No separate trash bin. Less code, more capability.', 'architecture', 0.80, 29, 360),
(327, 'concept', 'Time-Aware Graph', 'With status column: active edges = current relationships, superseded = old (code replaced), retired = code retired but edges preserved. Query: active graph vs full history vs delta.', 'graph', 0.75, 29, 357),
(328, 'concept', 'Tiered Hook Safety', 'gc_delete on file with all code in DB = ALLOW. gc_delete on file with code NOT in DB = BLOCK. rm on [@clean:MARK_FILE] tagged = ALLOW. rm on untagged = BLOCK. Hard delete DB rows = BLOCK.', 'security', 0.85, 29, 358),
(329, 'tool', 'BCL Code Graph Pipeline', '10-stage pipeline: .py→AST→Extract→Computational Units→BCL Identity→MySQL→Code Graph→BCL Stamps→Projection. 655 methods, 63 classes, 4147 edges already ingested.', 'pipeline', 0.80, 29, 352),
(330, 'tool', 'BCL Compiler', 'Reverse direction: BCL IR → plan → AST → code. Deterministic 5-phase compiler. AI only for unknown verbs. Complementary to the lifecycle cycle.', 'bcl', 0.65, 29, 352),
(331, 'tool', 'MagneticGraph', 'Graph traversal engine walking BCL code graph. Finds paths between methods, detects clusters, identifies hotspots. With status column becomes time-aware.', 'graph', 0.65, 29, 357),
(332, 'concept', '7-Step Implementation Order', '1. Schema migration. 2. gc_delete (PRIORITY). 3. retire_sweep. 4. sync. 5. recover. 6. Hook reconfiguration. 7. Verify round-trip (retire→recover, gc_delete→recover).', 'migration', 0.80, 29, 359),
(333, 'concept', 'DB is Source of Truth', 'Code never gets lost because it never leaves the database. When code is retired from a file, it is already in bcl_methods with BCL identity, IR, source, graph edges. Just status: active→retired.', 'architecture', 0.90, 29, 351),
(334, 'concept', 'AI Stops Writing From Scratch', 'Instead of rewriting same method 50 times: search DB (find), retrieve code, deliver to file, test, fix if needed. Cycle: ingest once, reuse forever, retire when obsolete, recover if needed.', 'architecture', 0.85, 29, 351);

-- Links for book 29
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(227, 315, 316, 'executed_by', 1.0, 'Lifecycle cycle executed by DomReuse commands'),
(228, 315, 329, 'starts_with', 1.0, 'Lifecycle starts with INGEST (BCL Code Graph Pipeline)'),
(229, 316, 317, 'uses', 1.0, 'DomReuse uses [@clean] mark for retire_sweep'),
(230, 316, 318, 'implements', 1.0, 'DomReuse implements gc_delete as rm replacement'),
(231, 316, 319, 'implements', 1.0, 'DomReuse implements retire_sweep command'),
(232, 316, 320, 'implements', 1.0, 'DomReuse implements sync command'),
(233, 316, 321, 'implements', 1.0, 'DomReuse implements recover command'),
(234, 316, 322, 'implements', 0.8, 'DomReuse implements weighting system (existing)'),
(235, 317, 325, 'uses', 1.0, '[@clean] mark uses triple-quoted string trick'),
(236, 318, 323, 'checks', 1.0, 'gc_delete checks bcl_methods for code presence'),
(237, 319, 323, 'updates', 1.0, 'retire_sweep updates bcl_methods status to retired'),
(238, 320, 323, 'updates', 1.0, 'sync updates bcl_methods with new versions'),
(239, 321, 323, 'updates', 1.0, 'recover updates bcl_methods status to active'),
(240, 326, 323, 'eliminates', 1.0, 'No dumpster table eliminates need for separate trash'),
(241, 327, 324, 'uses', 1.0, 'Time-aware graph uses edge_status column'),
(242, 328, 318, 'configures', 1.0, 'Tiered hook safety configures gc_delete permissions'),
(243, 332, 323, 'starts_with', 1.0, 'Implementation order starts with schema migration'),
(244, 332, 318, 'prioritizes', 1.0, 'Implementation order prioritizes gc_delete (step 2)'),
(245, 333, 323, 'relies_on', 1.0, 'DB is source of truth relies on bcl_methods table'),
(246, 334, 316, 'enables', 1.0, 'AI stops writing from scratch enabled by DomReuse find/retrieve'),
(247, 329, 323, 'populates', 1.0, 'BCL Code Graph Pipeline populates bcl_methods (INGEST stage)'),
(248, 331, 324, 'traverses', 0.7, 'MagneticGraph traverses bcl_edges with time-aware status'),
(249, 330, 315, 'complements', 0.6, 'BCL Compiler complements lifecycle (reverse direction)'),
(250, 327, 331, 'enables', 0.7, 'Time-aware graph enables MagneticGraph historical queries');

-- Glossary terms for book 29
INSERT OR IGNORE INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(111, 'Code Lifecycle Cycle', 'INGEST→REUSE→WEIGHT→PURGE→RETIRE→SYNC→RECOVER. Not a pipeline — a cycle. DB is source of truth, files are cache.', 'lifecycle', 'nodes.node_name=Code Lifecycle Cycle'),
(112, '[@clean] Mark', 'BCL tag wrapping retired code in triple-quoted string. File stays valid Python. @bcl_method_id links to DB row.', 'bcl', 'nodes.node_name=[@clean] Mark'),
(113, 'gc_delete', 'The rm replacement. Checks if all code in file is in DB. YES→strip+trash. NO→BLOCK. AI never runs rm directly.', 'security', 'nodes.node_name=gc_delete'),
(114, 'DB is Source of Truth', 'Code never leaves the database. Files are cache. Retired code = DB row with status=retired, still queryable, graphable, recoverable.', 'architecture', 'nodes.node_name=DB is Source of Truth');

-- Glossary links for book 29
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) VALUES
(111, 29, 351, NULL, 'primary'),
(112, 29, 355, NULL, 'primary'),
(113, 29, 353, NULL, 'primary'),
(114, 29, 351, NULL, 'primary');

-- Checks for book 29
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(104, 29, 354, 'Schema migration status', 'structure', 'PENDING', 'bcl_methods: 655 rows, 26 columns, NO status/version/retired_at. bcl_classes: 63 rows. bcl_edges: 4147 rows. Migration NOT yet run.'),
(105, 29, 352, 'Existing pipeline verification', 'structure', 'PASS', 'BCL Code Graph Pipeline: 655 methods, 63 classes, 4147 edges ingested. DomReuse: find/retrieve/deliver/test/fix/reweight/purge all working.'),
(106, 29, 359, 'Implementation order defined', 'structure', 'PASS', '7 steps: schema migration, gc_delete (PRIORITY), retire_sweep, sync, recover, hook reconfiguration, verify round-trip'),
(107, 29, 358, 'Hook integration design', 'design', 'PASS', 'Tiered safety: gc_delete+DB has code=ALLOW, gc_delete+no DB=BLOCK, rm+tagged=ALLOW, rm+untagged=BLOCK, hard delete DB=BLOCK');

-- Provenance for book 29
INSERT INTO provenance (provenance_id, source_path, dest_path, dest_type, book_id, notes) VALUES
(26, 'Session mango-maraca (2026-06-28) + GC_PIPELINE.md (project root)', 'Plf_PipelineBclCodeLifecycle.md', 'markdown', 29, 'Moved from GC_PIPELINE.md at project root. Designed during session where destruction-guard hook blocked rm on service_manager.py.');

-- Pipeline connections for book 29
INSERT INTO pipeline_connections (connection_id, from_book_id, to_book_id, connection_type, description, status) VALUES
(57, 29, 6, 'extends', 'Code lifecycle extends BCL Code Graph pipeline with RETIRE/SYNC/RECOVER stages', 'active'),
(58, 29, 26, 'uses', 'Code lifecycle uses MemUnit dispatch for DomReuse.Run commands', 'active'),
(59, 29, 23, 'integrates_with', 'Code lifecycle integrates with graph engine via time-aware bcl_edges', 'active'),
(60, 29, 25, 'integrates_with', 'Code lifecycle integrates with MagneticGraph for time-aware graph traversal', 'active');
