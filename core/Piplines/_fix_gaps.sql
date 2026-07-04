-- === FIX GAPS BATCH ===

-- === 1. SECTION TYPES FOR UNTYPED SECTIONS ===

-- Book 8 (Plf_ChatPipelineResults.md) - analysis results sections
UPDATE sections SET section_type = 'analysis_capabilities' WHERE section_id = 799;
UPDATE sections SET section_type = 'analysis_classes' WHERE section_id = 800;
UPDATE sections SET section_type = 'analysis_data_flows' WHERE section_id = 801;
UPDATE sections SET section_type = 'analysis_dependencies' WHERE section_id = 802;
UPDATE sections SET section_type = 'analysis_error_modes' WHERE section_id = 803;
UPDATE sections SET section_type = 'analysis_orchestration' WHERE section_id = 804;
UPDATE sections SET section_type = 'analysis_verdict' WHERE section_id = 805;

-- Book 10 (Plf_CleanupList.md) - maintenance sections
UPDATE sections SET section_type = 'maintenance_import' WHERE section_id = 832;
UPDATE sections SET section_type = 'maintenance_deleted' WHERE section_id = 833;
UPDATE sections SET section_type = 'maintenance_pending' WHERE section_id = 834;
UPDATE sections SET section_type = 'maintenance_summary' WHERE section_id = 835;

-- Book 12 (Plf_CodeGraph.md) - pipeline stages
UPDATE sections SET section_type = 'stage_sync' WHERE section_id = 836;
UPDATE sections SET section_type = 'stage_ingest' WHERE section_id = 837;
UPDATE sections SET section_type = 'stage_graph' WHERE section_id = 838;
UPDATE sections SET section_type = 'stage_reason' WHERE section_id = 839;
UPDATE sections SET section_type = 'stage_summary' WHERE section_id = 840;
UPDATE sections SET section_type = 'schema_code_files' WHERE section_id = 841;
UPDATE sections SET section_type = 'schema_code_units' WHERE section_id = 842;
UPDATE sections SET section_type = 'schema_code_edges' WHERE section_id = 843;
UPDATE sections SET section_type = 'query_units_by_type' WHERE section_id = 844;
UPDATE sections SET section_type = 'query_top_files' WHERE section_id = 845;
UPDATE sections SET section_type = 'query_dep_tree' WHERE section_id = 846;
UPDATE sections SET section_type = 'query_dead_methods' WHERE section_id = 847;
UPDATE sections SET section_type = 'query_change_impact' WHERE section_id = 848;

-- Book 32 (Plf_PipelineResults.md) - analysis results
UPDATE sections SET section_type = 'analysis_capabilities' WHERE section_id = 823;
UPDATE sections SET section_type = 'analysis_classes' WHERE section_id = 824;
UPDATE sections SET section_type = 'analysis_flows' WHERE section_id = 825;
UPDATE sections SET section_type = 'analysis_dependencies' WHERE section_id = 826;
UPDATE sections SET section_type = 'analysis_error_modes' WHERE section_id = 827;
UPDATE sections SET section_type = 'analysis_orchestration' WHERE section_id = 828;
UPDATE sections SET section_type = 'analysis_gap_closure' WHERE section_id = 829;
UPDATE sections SET section_type = 'analysis_crud' WHERE section_id = 830;
UPDATE sections SET section_type = 'analysis_verdict' WHERE section_id = 831;

-- === 2. LINKS FOR BOOK 2 (Plf_AlwaysLearningPipeline.md) ===
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT 41, 42, 'detects_for', 1.0, 'ExecutionSession captures failures and passes them to AIRepairSupervisor';

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT 42, 46, 'queries', 1.0, 'AIRepairSupervisor queries repair_patterns for past fixes before deciding';

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT 42, 46, 'writes_to', 1.0, 'AIRepairSupervisor records outcomes to repair_patterns (one SQL INSERT)';

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT 45, 44, 'triggers', 1.0, 'ConfidenceGate triggers CoreMLTrainer when threshold met';

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT 45, 46, 'queries', 1.0, 'ConfidenceGate queries repair_patterns for proven patterns';

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT 42, 43, 'uses', 1.0, 'AIRepairSupervisor uses survivor_ranking.py for SWAP strategy';

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT 48, 47, 'implements', 1.0, 'Database Learning is implemented via learned_rules MySQL table (10540 rows)';

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT 49, 44, 'implements', 1.0, 'Weight Learning is implemented by CoreMLTrainer (gate logic TODO)';

-- === 3. LINKS FOR BOOK 15 (Plf_ConfigFiles.md) ===
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT 114, 115, 'contains', 1.0, '5 Mandatory Sections includes the Config Class API as section 4';

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT 116, 115, 'violates', 1.0, 'Anti-Patterns describe what violates the Config Class API standard';

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT 116, 114, 'contradicts', 1.0, 'Anti-Patterns are the opposite of the 5 Mandatory Sections standard';

-- Add more nodes for book 15 (ConfigFiles)
INSERT INTO nodes (node_type, node_name, node_value, domain, source_book_id) VALUES
  ('tool', 'Config.py', 'The front door to a domain. Single Python file telling you everything about a domain folder: files, classes, methods, VBStyle status, constants, paths, settings.', 'config', 15),
  ('tool', 'Config_*.py', 'Domain-specific config variant. Same structure as Config.py but for specialized sub-domains.', 'config', 15),
  ('concept', 'BCL Headers', 'Mandatory section 1 of config files. Identity headers: @GHOST, @VBSTYLE, @FILEID, @SUMMARY, @CLASS, @METHOD.', 'config', 15),
  ('concept', 'File Inventory', 'Mandatory section 2 of config files. Lists every file in the domain with purpose, classes, methods, VBStyle status.', 'config', 15),
  ('concept', 'Domain Constants', 'Mandatory section 3 of config files. UPPERCASE constants for paths, settings, thresholds.', 'config', 15),
  ('concept', 'README/AI-Graph', 'Mandatory section 5 of config files. Architecture description, data flow, pipeline stages. Machine-readable but human-readable.', 'config', 15),
  ('concept', 'Garmin Navigator', 'Universal content that must NOT be in domain configs. Belongs in core/Dom_Unified/Config.py. Road 12 on CodeGPS Garmin.', 'config', 15),
  ('process', 'Config Validation', 'Checks: missing files, bad tokens, universal content leaks, VBStyle compliance. Runs automatically against the standard.', 'config', 15),
  ('process', 'Config Migration', 'Converting old ad-hoc configs to the 5-section standard. Steps: audit, add headers, add inventory, extract constants, add Config class, add README.', 'config', 15);

-- Now add links for the new nodes
INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'contains', 1.0, '5 Mandatory Sections contains BCL Headers (section 1)'
  FROM nodes n1, nodes n2 WHERE n1.node_name='5 Mandatory Sections' AND n2.node_name='BCL Headers' AND n1.source_book_id=15;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'contains', 1.0, '5 Mandatory Sections contains File Inventory (section 2)'
  FROM nodes n1, nodes n2 WHERE n1.node_name='5 Mandatory Sections' AND n2.node_name='File Inventory' AND n1.source_book_id=15;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'contains', 1.0, '5 Mandatory Sections contains Domain Constants (section 3)'
  FROM nodes n1, nodes n2 WHERE n1.node_name='5 Mandatory Sections' AND n2.node_name='Domain Constants' AND n1.source_book_id=15;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'contains', 1.0, '5 Mandatory Sections contains README/AI-Graph (section 5)'
  FROM nodes n1, nodes n2 WHERE n1.node_name='5 Mandatory Sections' AND n2.node_name='README/AI-Graph' AND n1.source_book_id=15;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'uses', 1.0, 'Config Validation uses the 5 Mandatory Sections as the standard to validate against'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Config Validation' AND n2.node_name='5 Mandatory Sections' AND n1.source_book_id=15;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'produces', 1.0, 'Config Migration produces Config.py with 5 Mandatory Sections'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Config Migration' AND n2.node_name='Config.py' AND n1.source_book_id=15;

INSERT INTO links (from_node_id, to_node_id, link_type, weight, evidence)
  SELECT n1.node_id, n2.node_id, 'excluded_from', 1.0, 'Garmin Navigator is excluded from domain configs — belongs in Dom_Unified/Config.py'
  FROM nodes n1, nodes n2 WHERE n1.node_name='Garmin Navigator' AND n2.node_name='Config.py' AND n1.source_book_id=15;

-- === 4. PROVENANCE FOR MISSING BOOKS ===
INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes)
  SELECT file_path, 'pipelines_library.db:books.book_id=2', 'sqlite', file_hash, 2, 'Full markdown ingested (368 lines). 8 chapters, 11 sections typed. 14 nodes (4 tools, 2 databases, 3 concepts, 4 processes, 1 gate). 8 links. 3 checks (1 implemented, 1 TODO, 1 partial). 8 glossary terms. BCL headers present. ConfidenceGate TODO noted.'
  FROM books WHERE book_id = 2;

INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes)
  SELECT file_path, 'pipelines_library.db:books.book_id=8', 'sqlite', file_hash, 8, 'Analysis results markdown. 5 nodes, 4 links, 4 checks. 7 section types assigned. Documents capabilities, classes, data flows, dependencies, error modes, orchestration, verdict.'
  FROM books WHERE book_id = 8;

INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes)
  SELECT file_path, 'pipelines_library.db:books.book_id=10', 'sqlite', file_hash, 10, 'Maintenance/cleanup list markdown. 8 nodes, 9 links, 5 checks. 4 section types assigned. Documents import details, deleted paths, pending build paths, category summary.'
  FROM books WHERE book_id = 10;

INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes)
  SELECT file_path, 'pipelines_library.db:books.book_id=35', 'sqlite', file_hash, 35, 'Session graph pipeline markdown. 6 nodes, 5 links, 3 checks. Documents session-based graph extraction and analysis.'
  FROM books WHERE book_id = 35;

INSERT INTO provenance (source_path, dest_path, dest_type, source_hash, book_id, notes)
  SELECT file_path, 'pipelines_library.db:books.book_id=38', 'sqlite', file_hash, 38, 'Word index search pipeline markdown. 9 nodes, 7 links, 5 checks. Documents fast word-level indexing and search system.'
  FROM books WHERE book_id = 38;

-- === 5. GLOSSARY TERMS FOR CONFIG FILES ===
INSERT OR IGNORE INTO glossary_terms (term, definition, sqlite_mapping) VALUES
  ('Config File Standard', '5 mandatory sections: BCL Headers, File Inventory, Domain Constants, Config Class, README/AI-Graph. Every domain must follow this.', NULL),
  ('File Inventory', 'Section 2 of config files. Lists every file with purpose, classes, methods, VBStyle status. Replaces needing to ls and read every file.', NULL),
  ('Config Class API', 'Section 4 of config files. Python class with Run() dispatch for programmatic access: read_state, set_config, get_file_list, etc.', NULL),
  ('Universal Content Leak', 'Anti-pattern where domain-specific content (e.g. Garmin Navigator) appears in a domain Config.py instead of Dom_Unified/Config.py.', NULL),
  ('Config Migration', 'Converting old ad-hoc configs to the 5-section standard. Audit, add headers, add inventory, extract constants, add class, add README.', NULL);
