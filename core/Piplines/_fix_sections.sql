-- Add sections to existing chapters for books 10 and 12
-- Book 10 chapters: 103-109, Book 12 chapters: 116-120
-- Starting section_id: 832

-- Book 10: Cleanup List sections
INSERT INTO sections (section_id, chapter_id, book_id, section_number, section_title, body_text) VALUES
(832, 103, 10, '1', 'Import Details', '83 JSONL session files, 16,790 raw messages, 3,181 noise removed (IDE context, environment, AGENTS.md), 3,520 duplicates removed (dual-logging + overlapping backups). 10,569 unique messages in codex_chat_history.chat (970 user, 9,599 assistant). Chronological order verified March 5 to April 16, 2026.'),
(833, 103, 10, '2', 'Deleted Paths', '3 paths: .codex.backup.20260416_101328 (458 MB, 1 session), .codex.backup.deepmerge.20260416_101843 (814 MB, 41 sessions, 831 lines), .codex.backup.deepmerge.20260416_101911 (814 MB, 41 sessions, 843 lines — most complete).'),
(834, 105, 10, '1', 'Pending Build Paths', '4 paths: GhostEmbedder/build (270 MB), SEED_FOR_SQL/build (92 KB), nested SEED_FOR_SQL/SEED_FOR_SQL/build (92 KB), GGUF_Context_Fix/build (128 KB). All NOT DELETED.'),
(835, 109, 10, '1', 'Category Summary', 'Codex Backups 2,086 MB DELETED (chats saved to MySQL), Python Pycache 232 MB DELETED (auto-regenerates), Build Dirs 270 MB pending, Python Cache 152 KB pending, Temp 308 KB pending, Qdrant snapshots unknown pending.');

-- Book 12: Code Graph sections
INSERT INTO sections (section_id, chapter_id, book_id, section_number, section_title, body_text) VALUES
(836, 116, 12, '1', 'Stage 0: SYNC', 'Compare file hashes vs DB hashes. Detects changed files before re-ingestion.'),
(837, 116, 12, '2', 'Stage 1: INGEST', 'Parse files into code_files (full source), code_units (per method), code_edges (CALLS, CONTAINS).'),
(838, 116, 12, '3', 'Stage 2: GRAPH', 'Build structural edges. CALLS: 10,757, CONTAINS: 1,801.'),
(839, 116, 12, '4', 'Stage 3: REASON (3a/3b/3c)', '3a SURFACE: purpose, signature, callers. 3b DEEP: gotchas, cascades, invariants. 3c MINE: scars from past sessions. Output to stamps table.'),
(840, 116, 12, '5', 'Stages 4-11', 'REGRAPH (semantic edges: DEPENDS_ON, BREAKS, RISKS), VALIDATE (VBStyle, dead code, cycles), PLAN (impact analysis, order, risk), REPAIR (modified code_units, versioned), CONFIG (knobs extracted), EXPORT (new .py files), VERIFY (compile+test+diff), ARCHIVE (old files to archive/).'),
(841, 117, 12, '1', 'code_files Table', 'id (PK), file_path (UNIQUE), file_hash, full_source (LONGTEXT). 134 rows.'),
(842, 117, 12, '2', 'code_units Table', 'id (PK), file_path, class_name, method_name, unit_type (FILE/CLASS/METHOD/FUNCTION/MODULE_CONST/IMPORT/MAIN_BLOCK), source_text, docstring, return_type, dispatch_key, calls (csv), called_by (csv), imports, line_start, line_end, content_hash, parent_class, is_vbstyle, ingested_at. 2,649 rows.'),
(843, 117, 12, '3', 'code_edges Table', 'id (PK), from_class, from_method, to_class, to_method, edge_type (CALLS/CONTAINS/IMPORTS/INHERITS/REFERENCES), evidence_line. 12,558 rows.'),
(844, 118, 12, '1', 'Units by Type', 'METHOD 1,801, MODULE_CONST 501, IMPORT 134, CLASS 121, FUNCTION 63, MAIN_BLOCK 29.'),
(845, 118, 12, '2', 'Top 10 Files by Method Count', 'Dom_Graph_Agent.py (122), Dom_Graph_EngineV2.py (39), ir_extractor.py (37), Dom_Graph_Boot.py (36), Dom_Graph_Plan.py (35), graph_builder.py (35), Dom_Graph_Engine.py (33), knowledge_engine.py (32), Dom_Graph_Gui.py (28), refactor_engine.py (25).'),
(846, 119, 12, '1', 'Event-Sourcing Dependency Tree', 'InRamDb -> EventLogStore, AstNodeRegistry, AstVersionStore -> BclStampStore, TraceChainStore, DependencyEdgeStore -> ReplayEngine <- RollbackEngine -> SnapshotStore. Key calls: append() (durability point), rebuild_at() (replay point).'),
(847, 120, 12, '1', 'Dead Methods Query', '228 of 1,801 methods have no recorded caller. Query: SELECT COUNT(*) FROM code_units WHERE unit_type=METHOD AND (called_by IS NULL OR called_by=empty).'),
(848, 120, 12, '2', 'Change Impact Query', 'Most connected methods by call count. Query: SELECT class_name, method_name, LENGTH(calls) as call_count FROM code_units WHERE unit_type=METHOD ORDER BY call_count DESC LIMIT 10.');
