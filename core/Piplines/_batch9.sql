-- Batch 9: Books 1 (VBEngine), 8 (ChatPipelineResults), 10 (CleanupList)
-- Starting IDs: nodes=386, links=302, glossary=121, checks=117, provenance=30, connections=72

-- ============================================================
-- BOOK 1: VBEngine — GPU-First Training Architecture
-- ============================================================

UPDATE books SET core_thesis = 'GPU-first Word2Vec SGNS training on Apple Silicon. Two-phase: Dataset Builder (CPU) + GPU Training Engine. Packed version wins at 214M pairs/s, 0.86 quality. Pantry system for versioned training cache. Correction system for surgical model updates via MySQL learned_rules.', status = 'architecture', sqlite_backend = 'sqlite+mysql' WHERE book_id = 1;

-- Nodes for book 1 (chapters 1-11, IDs 1-11)
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(386, 'concept', 'VBEngine GPU-First Architecture', 'GPU-first Word2Vec SGNS training on Apple Silicon. Two-phase system: Dataset Builder (CPU) generates training pairs, GPU Training Engine streams them via mmap. Not optimized Word2Vec — a GPU-first training engine with versioned cache and surgical correction.', 'architecture', 0.95, 1, 1),
(387, 'concept', 'Packed Training Version', 'c_word2vec_metal_packed.mm + metal_shaders_packed.h. Best version: 160M pairs, 0.75s/epoch (214M pairs/s), quality 0.86. Two-phase: --prepare builds training.bin (1.3GB, 7.1s), --train streams to GPU. Negatives stay on GPU as 4MB lookup table.', 'gpu', 0.95, 1, 2),
(388, 'concept', 'Two-Phase System', 'Phase 1: Dataset Builder (CPU) — multi-threaded pair generation with GCD, writes packed training.bin. Phase 2: GPU Training Engine — mmap zero-copy GPU access, persistent threads, atomic work stealing, fp16 weights with float accumulation.', 'architecture', 0.90, 1, 3),
(389, 'concept', 'GPU Optimizations', 'fp16 weights with float accumulation, half4 vectorized loads/stores, persistent threads with atomic work stealing, dynamic Metal pipeline querying (threadExecutionWidth=32, maxTotalThreadsPerThreadgroup=1024), wall-clock timing (clock_gettime), mmap zero-copy GPU access.', 'gpu', 0.85, 1, 2),
(390, 'concept', 'Pantry System', 'Versioned append-only training cache. Immutable sealed batches. LMDB-based. Multiple recipes (window/neg/min_count) coexist. Incremental growth — new corpus creates new batch, old untouched. Vocab versioning with forward ID mapping. Manifest as truth.', 'storage', 0.85, 1, 4),
(391, 'concept', 'Correction System', 'Surgical model updates via correction lunchboxes. When MySQL learned_rules pattern reaches threshold (100 occurrences), generate tiny targeted training batch (~5000 pairs), train on GPU in milliseconds, verify fix, log outcome back to MySQL. Connects ErrorTracker + Dom_Graph_Agent + Efi_ram_ai to GPU.', 'training', 0.90, 1, 5),
(392, 'concept', 'Correction Flow', 'DETECT: ErrorTracker.match -> THRESHOLD: pattern occurrence >= 100 -> BUILD: generate correction lunchbox from error/solution pairs -> TRAIN: load weights, train on lunchbox only -> VERIFY: re-run error case -> LOG: record outcome to MySQL (success_count++, failure_count++, update confidence).', 'training', 0.80, 1, 5),
(393, 'concept', 'MySQL Knowledge Base Integration', 'learned_rules (10,540 rows), know_problems (218), know_solutions (336), governance (58), rules (281), vb_classes (1,394), vb_methods (13,818). Correction system connects these existing pieces to the GPU training engine.', 'database', 0.75, 1, 5),
(394, 'concept', 'Implementation Roadmap', 'Completed: fp16, half4, persistent threads, dynamic pipeline querying, wall-clock timing, pre-packed data, mmap, multi-threaded CPU, fully packed experiment, chunked streaming, model save/load, quality verification. Next: LMDB pantry, --append mode, manifest, vocab versioning. Future: multi-recipe curriculum learning.', 'planning', 0.70, 1, 6),
(395, 'concept', 'File Inventory', 'Production: c_word2vec_metal_packed.mm, metal_shaders_packed.h. Experimental: c_word2vec_metal_fully_packed.mm, metal_shaders_fully_packed.h. Superseded: persist, pipeline, fp16, saturated, original fp32 versions. 14 files total.', 'inventory', 0.60, 1, 7),
(396, 'concept', 'Key Numbers', 'Corpus: 21.3M words, 23,434 files. Vocab: 162,612 words (min_count=5). Pairs: 160,818,661 (window=5). Embed dim: 128. Neg samples: 5. Training file: 1.3GB packed. GPU weights: 79MB fp16. Neg table: ~400KB. Speed: 214M pairs/s. Hardware: Apple M1, 8-core GPU, 16GB unified.', 'metrics', 0.75, 1, 8),
(397, 'concept', 'Design Philosophy', 'Separation of concerns (builder independent from trainer), Immutability (sealed batches never change), Surgical corrections (fix specific errors without full retraining), GPU purity (only math), Reuse over rebuild, Versioned growth (pantry grows, remembers, processes only new info).', 'philosophy', 0.70, 1, 9);

-- Links for book 1
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(302, 386, 387, 'best_version', 1.0, 'Packed version is the production winner'),
(303, 386, 388, 'implements', 1.0, 'Two-phase architecture'),
(304, 388, 389, 'optimizes', 1.0, 'GPU optimizations applied to training engine'),
(305, 386, 390, 'plans', 0.8, 'Pantry system is next implementation phase'),
(306, 386, 391, 'plans', 0.8, 'Correction system is next implementation phase'),
(307, 391, 392, 'executes', 1.0, 'Correction flow is the execution path'),
(308, 391, 393, 'depends_on', 1.0, 'Correction system reads MySQL learned_rules'),
(309, 390, 387, 'evolves', 0.7, 'Pantry replaces training.bin with versioned cache'),
(310, 394, 390, 'next_step', 0.8, 'Pantry system is next in roadmap'),
(311, 394, 391, 'next_step', 0.8, 'Correction system is next in roadmap');

-- Glossary terms for book 1
INSERT INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(121, 'SGNS', 'Skip-gram with Negative Sampling — the Word2Vec training algorithm used by VBEngine', 'algorithm', 'nodes.node_value LIKE "%SGNS%"'),
(122, 'Pantry', 'Versioned append-only training cache for GPU-ready work units. Immutable sealed batches. LMDB-based.', 'storage', 'nodes.node_name = "Pantry System"'),
(123, 'Correction Lunchbox', 'Tiny targeted training batch (~5000 pairs) generated from MySQL error patterns above threshold. Surgical GPU training in milliseconds.', 'training', 'nodes.node_name = "Correction System"'),
(124, 'Packed Pairs', 'Training data format where (center, context) pairs are pre-packed into a binary file for zero-copy GPU streaming', 'gpu', 'nodes.node_name = "Packed Training Version"'),
(125, 'fp16 Accumulation', 'GPU optimization: weights stored as fp16 but gradient accumulation in float32 for numerical stability', 'gpu', 'nodes.node_value LIKE "%fp16%"');

-- Glossary links for book 1
INSERT INTO glossary_links (term_id, book_id, chapter_id, link_type) VALUES
(121, 1, 1, 'defines'),
(122, 1, 4, 'defines'),
(123, 1, 5, 'defines'),
(124, 1, 2, 'defines'),
(125, 1, 2, 'defines');

-- Checks for book 1
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(117, 1, 2, 'Benchmark: 214M pairs/s', 'performance', 'PASS', '0.75s/epoch for 160M pairs on Apple M1'),
(118, 1, 2, 'Quality: 0.86 cosine similarity', 'quality', 'PASS', 'Verified for sqlite-related terms'),
(119, 1, 8, 'Corpus size: 21.3M words', 'metric', 'PASS', '23,434 files indexed'),
(120, 1, 8, 'Vocabulary: 162,612 words', 'metric', 'PASS', 'min_count=5 filter applied'),
(121, 1, 7, 'Production files compile', 'compilation', 'PASS', 'c_word2vec_metal_packed.mm compiles and runs'),
(122, 1, 6, 'Roadmap: 12 items completed', 'progress', 'PASS', 'fp16, half4, persistent threads, dynamic pipeline, timing, pre-packed, mmap, multi-threaded, fully packed experiment, chunked streaming, save/load, quality verification');

-- Provenance for book 1
INSERT INTO provenance (provenance_id, source_path, dest_path, dest_type, source_hash, book_id, notes) VALUES
(30, '/Users/wws/Downloads/Optimizing Word2Vec Metal Trainer.md', 'core/Piplines/PLF_VBENGINE_ARCHITECTURE.md', 'markdown', 'c49864ce05e933136939830bb64cb8ef', 1, 'Full conversation between WWS and Cascade that designed VBEngine. 429KB original, 107KB compressed, 143KB base64. Embedded in appendix.');

-- Pipeline connections for book 1
INSERT INTO pipeline_connections (connection_id, from_book_id, to_book_id, connection_type, description, status) VALUES
(72, 1, 5, 'depends_on', 'Correction system reads MySQL learned_rules and know_solutions from Error Capture pipeline', 'planned'),
(73, 1, 33, 'related_to', 'Both use SQLite for storage. VBEngine pantry and Provenance pipeline share SQLite patterns', 'active');

-- ============================================================
-- BOOK 8: Plf_ChatPipelineResults — 8-Graph Analysis of Chat File
-- ============================================================

UPDATE books SET core_thesis = '8-graph analysis results of a chat file (Codex Chat Cleanup.md, 633785 chars, 14652 lines). 14 capabilities, 22 classes/modules detected. 80 OK, 0 WARN, 1 GAP. Verdict: chat file has structure but is NOT a spec. Graph engine detected capabilities, flows, dependencies from conversation content.', status = 'analysis', sqlite_backend = 'sqlite' WHERE book_id = 8;

-- Nodes for book 8 (chapter IDs 103-102 range — need to check, using book_id=8)
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(398, 'concept', 'Chat Pipeline 8-Graph Analysis', '8-graph analysis of Codex Chat Cleanup.md (633785 chars, 14652 lines). Graphs run: 8/8. Results: 80 OK, 0 WARN, 1 GAP. Verdict: chat file has structure but is NOT a spec.', 'analysis', 0.85, 8, 103),
(399, 'concept', '14 Capabilities Detected', 'Graph engine detected 14 capabilities from chat content including search, indexing, scheduling, orchestration, error handling, compliance checking, reporting, backup, compression, credential management.', 'capability', 0.75, 8, 103),
(400, 'concept', '22 Classes/Modules Detected', '22 classes/modules identified in chat content: SearchEngine, Indexer, Scheduler, Orchestrator, VbsScanner, VbsTest, SystemCheck, DomAudit, DiffCheck, StatsReport, ContentExtract, PreFlight, ErrorHandler, ErrorTracker, MSearch, Cleaner, Compress, Backup, Credentials, ConfigReport, DomIndexer, UnifiedAst.', 'inventory', 0.70, 8, 103),
(401, 'concept', 'Chat File vs Spec File', 'Chat file has structure but is NOT a spec. Graph engine detected capabilities, flows, dependencies from conversation content but cannot verify completeness the way it does for structured SPEC.md. 1 gap detected — expected for chat file.', 'analysis', 0.80, 8, 103),
(402, 'concept', 'Gap: Missing File Headers', 'Only gap detected: file documentation headers present but not complete. Expected for a chat file — not a spec.', 'gap', 0.50, 8, 103);

-- Links for book 8
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(312, 398, 399, 'detected', 1.0, '14 capabilities found by graph engine'),
(313, 398, 400, 'detected', 1.0, '22 classes/modules found by graph engine'),
(314, 398, 401, 'concluded', 1.0, 'Verdict: chat file is not a spec'),
(315, 398, 402, 'found_gap', 0.5, 'Only 1 gap — file headers');

-- Glossary terms for book 8
INSERT INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(126, 'Chat File Analysis', 'Running 8-graph analysis on a chat conversation file to extract structure, capabilities, and flows from unstructured content', 'analysis', 'nodes.node_name = "Chat Pipeline 8-Graph Analysis"');

-- Glossary links for book 8
INSERT INTO glossary_links (term_id, book_id, chapter_id, link_type) VALUES
(126, 8, 103, 'defines');

-- Checks for book 8
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(123, 8, 103, 'Graphs run: 8/8', 'completeness', 'PASS', 'All 8 graphs executed successfully'),
(124, 8, 103, 'OK count: 80', 'quality', 'PASS', '80 items passed graph checks'),
(125, 8, 103, 'GAP count: 1', 'gap', 'PASS', '1 gap detected — expected for chat file (not a spec)');

-- Pipeline connections for book 8
INSERT INTO pipeline_connections (connection_id, from_book_id, to_book_id, connection_type, description, status) VALUES
(74, 8, 39, 'produced_by', 'Chat pipeline results generated by 8-Graph Workflow Pipeline', 'active'),
(75, 8, 36, 'analyzes', 'Chat file analysis detected utilities pipeline components', 'active');

-- ============================================================
-- BOOK 10: Cleanup List — Temp/Junk Files
-- ============================================================

UPDATE books SET core_thesis = 'Cleanup list for temporary and junk files. DELETED: Codex backups (2,086 MB), Python pycache (232 MB). STILL HERE: build directories (270 MB), Python cache (152 KB), temp directories (308 KB), Qdrant snapshots. Total freed: ~2.3 GB. Remaining to delete: ~270 MB.', status = 'maintenance', sqlite_backend = 'sqlite' WHERE book_id = 10;

-- Nodes for book 10 (chapter IDs 103-109)
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(403, 'concept', 'Cleanup List', 'Temporary and junk file cleanup tracking. DELETED: Codex backups (2,086 MB), Python pycache (232 MB). STILL HERE: build directories, Python cache, temp directories, Qdrant snapshots.', 'maintenance', 0.70, 10, 103),
(404, 'concept', 'DELETED: Codex Backups', '2,086 MB freed. Codex backup directories deleted successfully.', 'cleanup', 0.60, 10, 103),
(405, 'concept', 'DELETED: Python Pycache', '232 MB freed. Python __pycache__ directories deleted.', 'cleanup', 0.60, 10, 104),
(406, 'concept', 'STILL HERE: Build Directories', '270 MB remaining. Build directories still present, need manual deletion. Includes mdmerge_debug.dSYM, mdmerge_modular, other build artifacts.', 'cleanup', 0.50, 10, 105),
(407, 'concept', 'STILL HERE: Python Cache', '152 KB remaining. Python cache directories still present.', 'cleanup', 0.40, 10, 106),
(408, 'concept', 'STILL HERE: Temp Directories', '308 KB remaining. Temporary directories still present.', 'cleanup', 0.40, 10, 107),
(409, 'concept', 'STILL HERE: Qdrant Snapshots', 'Qdrant snapshots temp directory still present. Needs cleanup.', 'cleanup', 0.40, 10, 108),
(410, 'concept', 'Cleanup Summary', 'Total freed: ~2.3 GB (2,086 + 232 MB). Remaining to delete: ~270 MB (build dirs + cache + temp + Qdrant).', 'summary', 0.65, 10, 109);

-- Links for book 10
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(316, 403, 404, 'deleted', 1.0, 'Codex backups deleted (2,086 MB)'),
(317, 403, 405, 'deleted', 1.0, 'Python pycache deleted (232 MB)'),
(318, 403, 406, 'pending', 0.5, 'Build directories still here (270 MB)'),
(319, 403, 407, 'pending', 0.3, 'Python cache still here (152 KB)'),
(320, 403, 408, 'pending', 0.3, 'Temp directories still here (308 KB)'),
(321, 403, 409, 'pending', 0.3, 'Qdrant snapshots still here'),
(322, 410, 404, 'summarizes', 0.8, 'Part of total freed'),
(323, 410, 405, 'summarizes', 0.8, 'Part of total freed'),
(324, 410, 406, 'summarizes', 0.5, 'Part of remaining');

-- Glossary terms for book 10
INSERT INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(127, 'Cleanup List', 'Tracking document for temporary and junk file deletion with status (DELETED or STILL HERE) and sizes', 'maintenance', 'nodes.node_name = "Cleanup List"');

-- Glossary links for book 10
INSERT INTO glossary_links (term_id, book_id, chapter_id, link_type) VALUES
(127, 10, 103, 'defines');

-- Checks for book 10
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(126, 10, 103, 'Codex backups deleted', 'cleanup', 'PASS', '2,086 MB freed'),
(127, 10, 104, 'Python pycache deleted', 'cleanup', 'PASS', '232 MB freed'),
(128, 10, 105, 'Build directories pending', 'cleanup', 'PENDING', '270 MB still here'),
(129, 10, 109, 'Total freed: ~2.3 GB', 'summary', 'PASS', '2,086 + 232 MB = 2,318 MB freed');

-- Pipeline connections for book 10
INSERT INTO pipeline_connections (connection_id, from_book_id, to_book_id, connection_type, description, status) VALUES
(76, 10, 36, 'related_to', 'Cleanup list tracks artifacts that Utilities pipeline Cleaner utility should remove', 'active');
