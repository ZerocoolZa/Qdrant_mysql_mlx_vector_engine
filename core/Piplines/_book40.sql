BEGIN TRANSACTION;

-- ===== BOOK =====
INSERT INTO books (book_id, file_name, title, file_path, core_thesis, status, line_count, ingested_at)
VALUES (40, 'PLF_Chat_processing.md', 'Chat Processing Pipeline - Conversation Knowledge Compiler',
        'core/Piplines/PLF_Chat_processing.md',
        'Specification for compiling conversations into deterministic knowledge: Chat -> BCL -> Atoms -> Graph -> Reasoning. 9-stage pipeline with traceability, confidence metadata, and multi-input Knowledge Compiler vision.',
        'ACTIVE', 2616, datetime('now'));

-- ===== CHAPTERS (520-534) =====
INSERT INTO chapters (chapter_id, book_id, chapter_number, chapter_title, line_start, line_end) VALUES
(520, 40, 1,  'Pipeline Overview - Knowledge Compiler Architecture', 1, 162),
(521, 40, 2,  'Stage 0 - Capture (Message Layer)', 472, 487),
(522, 40, 3,  'Stage 1 - Atomic Knowledge Extraction', 489, 528),
(523, 40, 4,  'Stage 2 - Relationship Extraction', 530, 556),
(524, 40, 5,  'Stage 3 - Reasoning Episodes (Block Layer)', 558, 582),
(525, 40, 6,  'Stage 4 - Sections (Section Layer)', 584, 597),
(526, 40, 7,  'Stage 5 - Session (Session Layer)', 599, 616),
(527, 40, 8,  'Stage 6 - Project Evolution (Cross-Session)', 618, 634),
(528, 40, 9,  'Stage 7 - Validation', 636, 653),
(529, 40, 10, 'Stage 8 - Report Generation', 655, 676),
(530, 40, 11, 'Governing Principles and Compiler Layers', 678, 903),
(531, 40, 12, 'BCL Packet Protocol and Database Schema', 904, 1520),
(532, 40, 13, 'Working Demo - Devin_Moseimport.db Proof of Concept', 1521, 1948),
(533, 40, 14, 'Knowledge Audit and Critical Analysis', 1949, 2436),
(534, 40, 15, 'Knowledge Compiler Vision - Multi-Input Architecture', 2437, 2616);

-- ===== SECTIONS (849+) =====
INSERT INTO sections (section_id, book_id, chapter_id, section_number, section_title, line_start, line_end, section_type) VALUES
(849, 40, 520, '1.1', 'Conversation Knowledge Pipeline - Input', 9, 16, 'input_spec'),
(850, 40, 520, '1.2', 'Stage 1 - Message Layer (Original)', 19, 32, 'pipeline_stage'),
(851, 40, 520, '1.3', 'Stage 2 - Block Layer (Original)', 35, 58, 'pipeline_stage'),
(852, 40, 520, '1.4', 'Stage 3-7 - Section/Session/Cross-Session/Graph/Validation (Original)', 61, 147, 'pipeline_stage'),
(853, 40, 520, '1.5', 'Never Summarize Twice - Build Upward', 149, 161, 'core_principle'),
(854, 40, 521, '2.1', 'Purpose - Capture Conversation Exactly', 472, 477, 'pipeline_stage'),
(855, 40, 521, '2.2', 'Output - Messages, Speaker, Timestamp, Attachments', 478, 486, 'output_format'),
(856, 40, 522, '3.1', 'Purpose - Extract Every Durable Piece of Knowledge', 489, 493, 'pipeline_stage'),
(857, 40, 522, '3.2', 'Output - 27 Atomic Knowledge Types', 494, 524, 'output_format'),
(858, 40, 522, '3.3', 'Every Extracted Item Receives Its Own ID', 525, 527, 'core_principle'),
(859, 40, 523, '4.1', 'Purpose - Connect the Atomic Knowledge', 530, 534, 'pipeline_stage'),
(860, 40, 523, '4.2', 'Relationship Examples - 13 Connection Types', 535, 555, 'output_format'),
(861, 40, 524, '5.1', 'Purpose - Build One Coherent Reasoning Episode', 558, 564, 'pipeline_stage'),
(862, 40, 524, '5.2', 'Episode Contents - 10 Fields', 565, 577, 'output_format'),
(863, 40, 524, '5.3', 'Block Ends When Reasoning Ends - Not Fixed Count', 578, 581, 'core_principle'),
(864, 40, 525, '6.1', 'Purpose - Group Related Reasoning Episodes', 584, 588, 'pipeline_stage'),
(865, 40, 525, '6.2', 'Section Examples - Database, BCL, SQL, Runtime', 589, 596, 'output_format'),
(866, 40, 526, '7.1', 'Purpose - Determine What Changed', 599, 603, 'pipeline_stage'),
(867, 40, 526, '7.2', 'Output - 9 Session-Level Artifacts', 604, 615, 'output_format'),
(868, 40, 527, '8.1', 'Purpose - Merge Session into Long-Term Project', 618, 623, 'pipeline_stage'),
(869, 40, 527, '8.2', 'Track 6 Evolution Types - Every Concept Versioned', 624, 633, 'output_format'),
(870, 40, 528, '9.1', 'Purpose - Check Completeness', 636, 640, 'pipeline_stage'),
(871, 40, 528, '9.2', '8 Validation Rules - Every Artifact Has Required Links', 641, 652, 'validation'),
(872, 40, 529, '10.1', 'Purpose - Reports Created From Structured Knowledge', 655, 660, 'pipeline_stage'),
(873, 40, 529, '10.2', '10 Report Types - All Generated, Never Stored as Truth', 661, 675, 'output_format'),
(874, 40, 530, '11.1', '10 Governing Principles of the Pipeline', 678, 693, 'core_principle'),
(875, 40, 530, '11.2', 'Knowledge Compiler - Chat is Source Code', 695, 702, 'core_concept'),
(876, 40, 530, '11.3', 'Layer 0 - Transcript (Immutable Evidence)', 705, 718, 'architecture'),
(877, 40, 530, '11.4', 'Layer 1 - Reasoning Episodes (Semantic Blocks)', 720, 740, 'architecture'),
(878, 40, 530, '11.5', 'Layer 2 - Artifact Extraction (Many Independent Artifacts)', 742, 764, 'architecture'),
(879, 40, 530, '11.6', 'Layer 3 - Evolution (Versioned Concepts)', 766, 795, 'architecture'),
(880, 40, 530, '11.7', 'Layer 4 - Relationships (Reasoning Graph)', 797, 814, 'architecture'),
(881, 40, 530, '11.8', 'Traceability - Decision to Reasoning to Evidence to Messages', 856, 877, 'core_principle'),
(882, 40, 531, '12.1', 'Database Schema - Transcript, Episodes, Artifacts, Relationships, Evolution', 904, 1001, 'schema_spec'),
(883, 40, 531, '12.2', 'Knowledge Tree - Project to Session to Section to Episode to Messages', 1002, 1025, 'architecture'),
(884, 40, 531, '12.3', 'Message Fan-Out - Every Message Extracts Knowledge Branches', 1026, 1138, 'architecture'),
(885, 40, 531, '12.4', 'Conversation Pairs - User + AI = One Reasoning Exchange', 1140, 1251, 'core_concept'),
(886, 40, 531, '12.5', 'BCL Packet Format - BLOCK MESSAGE FACT DECISION', 1455, 1626, 'bcl_format'),
(887, 40, 531, '12.6', 'BCL as Compiled Representation - Chat = Evidence, BCL = Working Knowledge', 1627, 1733, 'core_concept'),
(888, 40, 532, '13.1', 'Demo Query - Load BCL Packets from Devin_Moseimport.db', 1876, 1907, 'benchmark_results'),
(889, 40, 532, '13.2', 'System In Action - Decisions, Facts, Contradictions, Open Questions', 1908, 1947, 'benchmark_results'),
(890, 40, 533, '14.1', 'What the System Demonstrated - 5 Proven Capabilities', 1953, 1966, 'benchmark_results'),
(891, 40, 533, '14.2', 'Confidence Caution - Compiler Rediscovery vs Extraction Correctness', 1969, 1982, 'core_principle'),
(892, 40, 533, '14.3', 'Entity vs Type Distinction - What Exists vs What Kind', 1985, 1997, 'core_concept'),
(893, 40, 533, '14.4', 'Authority Definition - Controlled Source of Truth', 2000, 2018, 'core_concept'),
(894, 40, 533, '14.5', 'Stage 8 - Knowledge Audit (11 Checks)', 2091, 2107, 'pipeline_stage'),
(895, 40, 533, '14.6', 'Traditional AI vs Knowledge Compiler Architecture', 2108, 2153, 'architecture'),
(896, 40, 533, '14.7', 'Chat as Permanent Evidence - Not Disposable', 2155, 2217, 'core_principle'),
(897, 40, 534, '15.1', 'Threshold Crossed - Summarizer to Knowledge Compiler', 2438, 2449, 'vision'),
(898, 40, 534, '15.2', 'Multiple Compiler Outputs - 9 Artifact Types', 2450, 2517, 'output_format'),
(899, 40, 534, '15.3', 'Confidence Metadata - Every Atom Carries Provenance', 2520, 2548, 'core_concept'),
(900, 40, 534, '15.4', 'Supersede Pattern - Evolution Not Replacement', 2539, 2548, 'core_concept'),
(901, 40, 534, '15.5', 'Knowledge Compiler - Multi-Input Frontend Architecture', 2551, 2574, 'architecture'),
(902, 40, 534, '15.6', 'Proof of Concept Summary - 105 Atoms, 71 Links, 22 BCL Packets', 2577, 2616, 'benchmark_results');

-- ===== NODES (536+) =====
INSERT INTO nodes (node_id, node_type, node_name, node_value, domain, importance_score, source_book_id, source_chapter_id) VALUES
(536, 'pipeline', 'Knowledge Compiler', 'Compiles conversations into deterministic knowledge representation', 'chat_processing', 1.0, 40, 530),
(537, 'pipeline', 'BCL Compiler', 'Converts chat pairs into BCL packets', 'chat_processing', 0.95, 40, 531),
(538, 'pipeline', 'Atom Extractor', 'Extracts 27 atomic knowledge types from reasoning episodes', 'chat_processing', 0.9, 40, 522),
(539, 'pipeline', 'Relationship Builder', 'Connects atomic knowledge into reasoning graph', 'chat_processing', 0.85, 40, 523),
(540, 'pipeline', 'Validation Engine', 'Checks completeness - every artifact has required links', 'chat_processing', 0.8, 40, 528),
(541, 'pipeline', 'Audit Engine', 'Stage 8 - orphan atoms, contradictions, confidence gaps', 'chat_processing', 0.8, 40, 533),
(542, 'artifact', 'BCL Packet', 'BLOCK containing MESSAGE FACT DECISION - compiled representation of chat pair', 'chat_processing', 0.95, 40, 531),
(543, 'artifact', 'Knowledge Atom', 'Normalized reusable knowledge - fact, decision, rule, law, etc.', 'chat_processing', 0.95, 40, 522),
(544, 'artifact', 'Conversation Pair', 'User message + AI response = one reasoning exchange', 'chat_processing', 0.85, 40, 531),
(545, 'artifact', 'Reasoning Episode', 'One complete thought cycle - goal through outcome', 'chat_processing', 0.9, 40, 524),
(546, 'artifact', 'Evidence Chain', 'Decision to Reasoning to Evidence to Messages traceability', 'chat_processing', 0.9, 40, 530),
(547, 'concept', 'Confidence Metadata', 'Every atom carries confidence score, evidence, compiler version, status', 'chat_processing', 0.9, 40, 534),
(548, 'concept', 'Supersede Pattern', 'New compiler disagrees without deleting - old atom superseded, new created', 'chat_processing', 0.85, 40, 534),
(549, 'concept', 'Knowledge Evolution', 'Every concept versioned - old to new with reason for change', 'chat_processing', 0.85, 40, 527),
(550, 'concept', 'Recompilation Path', 'Raw messages preserved - future BCL versions can re-extract without loss', 'chat_processing', 0.8, 40, 533),
(551, 'architecture', 'Evidence Layer', 'Raw chat - user messages + AI messages - immutable permanent evidence', 'chat_processing', 0.9, 40, 530),
(552, 'architecture', 'Compilation Layer', 'BCL compiler converts evidence into BCL packets', 'chat_processing', 0.9, 40, 530),
(553, 'architecture', 'Knowledge Layer', 'Atoms + relationships + graph - normalized reusable knowledge', 'chat_processing', 0.9, 40, 530),
(554, 'architecture', 'Reasoning Layer', 'LLM reasons over compiled knowledge structure, not flat transcript', 'chat_processing', 0.85, 40, 533),
(555, 'input_type', 'Chat Input', 'Conversations - the primary front-end for the Knowledge Compiler', 'chat_processing', 0.7, 40, 534),
(556, 'input_type', 'PDF Input', 'Documents - future front-end for Knowledge Compiler', 'chat_processing', 0.5, 40, 534),
(557, 'input_type', 'Source Code Input', 'Code files - future front-end for Knowledge Compiler', 'chat_processing', 0.5, 40, 534),
(558, 'input_type', 'Email Input', 'Email messages - future front-end for Knowledge Compiler', 'chat_processing', 0.5, 40, 534),
(559, 'input_type', 'SQL Schema Input', 'Database schemas - future front-end for Knowledge Compiler', 'chat_processing', 0.5, 40, 534),
(560, 'input_type', 'Audio Transcript Input', 'Transcribed audio - future front-end for Knowledge Compiler', 'chat_processing', 0.4, 40, 534),
(561, 'artifact', 'Compiler Output Set', '9 outputs: messages, bcl, atoms, links, audit, validation, summary, timeline, index', 'chat_processing', 0.85, 40, 534),
(562, 'concept', 'Never Summarize Twice', 'Build upward - each layer built only from layer below, never reread original chat', 'chat_processing', 0.9, 40, 520),
(563, 'concept', '10 Governing Principles', 'Capture once, extract once, identify once, relate once, group upward, never duplicate, every artifact has ID, every relationship explicit, every conclusion traceable, reports are views', 'chat_processing', 0.9, 40, 530);

-- ===== LINKS (478+) =====
INSERT INTO links (link_id, from_node_id, to_node_id, link_type, weight, evidence) VALUES
(478, 536, 537, 'orchestrates', 1.0, 'Knowledge Compiler orchestrates BCL Compiler'),
(479, 537, 542, 'produces', 1.0, 'BCL Compiler produces BCL Packets'),
(480, 537, 543, 'extracts', 1.0, 'BCL Compiler extracts Knowledge Atoms'),
(481, 543, 539, 'connected_by', 1.0, 'Atoms connected by Relationship Builder'),
(482, 539, 553, 'forms', 1.0, 'Relationships form Knowledge Layer'),
(483, 553, 554, 'feeds', 1.0, 'Knowledge Layer feeds Reasoning Layer'),
(484, 543, 551, 'traces_to', 1.0, 'Every atom traces to Evidence Layer'),
(485, 542, 544, 'compiles', 1.0, 'BCL Packet compiles one Conversation Pair'),
(486, 544, 545, 'contains', 1.0, 'Conversation Pair contains one Reasoning Episode'),
(487, 545, 543, 'produces', 1.0, 'Reasoning Episode produces Knowledge Atoms'),
(488, 547, 543, 'annotates', 1.0, 'Confidence Metadata annotates every Atom'),
(489, 548, 543, 'supersedes', 0.9, 'Supersede Pattern replaces old atoms without deleting'),
(490, 549, 543, 'versions', 0.9, 'Knowledge Evolution versions every concept'),
(491, 550, 551, 'requires', 0.8, 'Recompilation requires raw evidence preserved'),
(492, 551, 552, 'feeds', 1.0, 'Evidence Layer feeds Compilation Layer'),
(493, 552, 553, 'feeds', 1.0, 'Compilation Layer feeds Knowledge Layer'),
(494, 540, 543, 'validates', 0.8, 'Validation Engine validates atom completeness'),
(495, 541, 543, 'audits', 0.8, 'Audit Engine finds orphan atoms and contradictions'),
(496, 536, 555, 'accepts_input', 0.7, 'Knowledge Compiler accepts Chat Input'),
(497, 536, 556, 'accepts_input', 0.5, 'Knowledge Compiler accepts PDF Input (future)'),
(498, 536, 557, 'accepts_input', 0.5, 'Knowledge Compiler accepts Source Code Input (future)'),
(499, 536, 558, 'accepts_input', 0.5, 'Knowledge Compiler accepts Email Input (future)'),
(500, 536, 559, 'accepts_input', 0.5, 'Knowledge Compiler accepts SQL Schema Input (future)'),
(501, 536, 560, 'accepts_input', 0.4, 'Knowledge Compiler accepts Audio Transcript Input (future)'),
(502, 536, 561, 'produces', 0.85, 'Knowledge Compiler produces 9 output types'),
(503, 562, 536, 'governs', 0.9, 'Never Summarize Twice governs Knowledge Compiler'),
(504, 563, 536, 'governs', 0.9, '10 Governing Principles govern Knowledge Compiler'),
(505, 546, 551, 'traces_to', 1.0, 'Evidence Chain traces to Evidence Layer'),
(506, 538, 543, 'extracts', 0.9, 'Atom Extractor extracts Knowledge Atoms'),
(507, 545, 545, 'semantic_boundary', 0.8, 'Episode ends when reasoning ends not after fixed message count');

-- ===== GLOSSARY (160+) =====
INSERT OR IGNORE INTO glossary_terms (term_id, term, definition, category, sqlite_mapping) VALUES
(160, 'Knowledge Compiler', 'Compiles conversations and other inputs into deterministic knowledge representation. Not a summarizer - a compiler. Chat = source code, BCL = compiled output.', 'pipeline', 'bcl_packets.atom_link.messages'),
(161, 'BCL Packet', 'BLOCK containing MESSAGE FACT DECISION - compiled representation of a conversation pair. Contains references to knowledge atoms not text.', 'format', 'bcl_packets.bcl_packet'),
(162, 'Knowledge Atom', 'Normalized reusable knowledge - fact decision rule law question answer etc. Each has its own ID and traces to evidence.', 'artifact', 'atom.content'),
(163, 'Reasoning Episode', 'One complete thought cycle - goal through outcome. Replaces arbitrary 5-10 message blocks. Ends when reasoning ends.', 'artifact', 'bcl_packets.pair_id'),
(164, 'Conversation Pair', 'User message + AI response = one reasoning exchange. The unit of compilation.', 'artifact', 'bcl_packets.pair_id'),
(165, 'Evidence Chain', 'Decision to Reasoning to Evidence to Messages. Traceability from any atom back to original chat.', 'concept', 'atom_link.source_msg'),
(166, 'Confidence Metadata', 'Every atom carries confidence score evidence messages reasoning chain compiler version status', 'concept', 'atom.confidence'),
(167, 'Supersede Pattern', 'New compiler disagrees with old atom without deleting it. Old atom marked superseded new atom created with reason.', 'concept', 'atom.status'),
(168, 'Knowledge Evolution', 'Every concept versioned. Old value to new value with reason for change. Knowledge base evolves does not replace.', 'concept', 'atom.version'),
(169, 'Recompilation', 'Raw messages preserved so future BCL versions can re-extract without losing original reasoning', 'concept', 'messages table permanent'),
(170, 'Knowledge Audit', 'Stage 8 - checks orphan atoms orphan decisions missing reasoning circular reasoning conflicting definitions duplicate concepts dead concepts unused laws confidence gaps', 'pipeline', 'audit_report'),
(171, 'Multi-Input Frontend', 'Knowledge Compiler accepts chat PDF source code email SQL schema audio transcripts - same compiler core different front-end per input type', 'architecture', NULL);

-- ===== CHECKS (175+) =====
INSERT INTO checks (check_id, book_id, chapter_id, check_name, check_type, check_status, check_result) VALUES
(175, 40, 528, 'Stage 7 Validation - Every Question has Answer or Open', 'completeness_check', 'PASS', '8 validation rules defined'),
(176, 40, 533, 'Stage 8 Knowledge Audit - Orphan Atom Detection', 'audit_check', 'PASS', '11 audit checks defined'),
(177, 40, 531, 'BCL Packet Format Validation', 'format_check', 'PASS', 'BLOCK MESSAGE FACT DECISION verified in demo'),
(178, 40, 532, 'Atom-to-Message Traceability', 'traceability_check', 'PASS', 'Decision 22 to Reasoning 7 to Message 128 confirmed in demo'),
(179, 40, 534, 'Confidence Metadata Presence', 'completeness_check', 'PENDING', 'Confidence field defined in spec not yet implemented in all atoms');

-- ===== PROVENANCE (43) =====
INSERT INTO provenance (provenance_id, source_path, dest_path, dest_type, book_id, notes)
VALUES (43, 'core/Piplines/PLF_Chat_processing.md', 'pipelines_library.db', 'sqlite', 40,
        'Book 40 - Chat Processing Pipeline. 2616 lines. 15 chapters 54 sections 28 nodes 30 links 12 glossary terms 5 checks. Full Knowledge Compiler specification with working demo proof.');

-- ===== PIPELINE CONNECTIONS =====
INSERT INTO pipeline_connections (from_book_id, to_book_id, connection_type, description, status) VALUES
(40, 9, 'feeds_from', 'ChatMover Pipeline (book 9) ingests raw chats then Chat Processing Pipeline (book 40) compiles them', 'active'),
(40, 17, 'writes_to', 'Chat Processing Pipeline stores atoms in MySQL tables documented in Database Management (book 17)', 'active'),
(40, 6, 'uses_format', 'Chat Processing Pipeline uses BCL packet format from BCL Unit Builder Pipeline (book 6)', 'active'),
(40, 16, 'feeds', 'Context Expansion Pipeline (book 16) uses compiled knowledge atoms from Chat Processing Pipeline', 'planned');

COMMIT;
