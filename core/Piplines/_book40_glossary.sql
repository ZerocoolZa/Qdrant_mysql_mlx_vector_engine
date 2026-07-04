BEGIN TRANSACTION;
INSERT OR IGNORE INTO glossary_terms (term, definition, category, sqlite_mapping) VALUES
('Knowledge Package', 'Canonical implementation-independent output from the compiler containing Identity Evidence Knowledge Relationships Validation Compilation', 'output_format', 'atoms + atom_link tables'),
('Compilation Manifest', 'Reproducibility metadata for each compilation: input count output count warnings errors compiler version elapsed time', 'output_format', 'metadata table'),
('Knowledge Runtime', 'Third product that queries the Knowledge Package. Separate from Compiler and Package. Many AIs share same package', 'system_component', 'query layer'),
('Extraction Contract', 'Formalizes what extractor may emit. Every atom must contain Type Content Evidence Confidence Extraction Rule Compiler Version Source Span', 'core_concept', 'atom schema'),
('Interpret Phase', 'Split from Extract. Takes Candidate Atoms and produces Canonical Atoms. Improves interpretation without changing extraction', 'pipeline_stage', 'phase 3b'),
('Inference Layer', 'Knowledge never explicitly stated but logically derived. Inferred atoms marked differently from extracted atoms', 'core_concept', 'inferred_atom type'),
('Higher-Order Atom', 'Derived artifact from multiple base atoms. Definition Set atom derived from atoms 18 20 21. Does not overwrite existing facts', 'core_concept', 'derived_atom type'),
('Knowledge Hierarchy', 'Compiler builds hierarchies: Fact to Conclusion Decision to Milestone Contradiction to Resolution', 'core_concept', 'hierarchy edges'),
('Reasoning Path', 'SHOW PATH TO DECISION 44 - traverses graph from goal through reasoning to final decision. Explainable AI', 'core_concept', 'graph traversal'),
('Proof Artifact', 'Assembled not extracted. Claim supported by chain of atoms. Different from Fact - proof is something assembled', 'core_concept', 'proof table'),
('Compiler Quality Metrics', 'Coverage Orphans Unresolved Questions Contradictions Average Confidence Compilation Warnings. Enables compiler version comparison', 'statistics_report', 'metrics table'),
('Claim', 'Renamed from Atom. Every atom is a claim that can be supported contradicted superseded verified disproved confidence scored', 'core_concept', 'claim table'),
('Context', 'Bounded reasoning episode with Goal Problem Decision Outcome Evidence. Preserves reasoning without forcing reconstruction', 'core_concept', 'context table'),
('Five Layer Model', 'Layer 0 Evidence Layer 1 Claims Layer 2 Relations Layer 3 Episodes Layer 4 Knowledge. Knowledge is computed not extracted', 'architecture', 'layered schema'),
('The Invariant', 'Explainability is graph traversability. Traverse graph of claims and typed edges to reconstruct explanatory chains without original transcript', 'core_principle', 'graph property'),
('Reproducibility Test', 'Run automatic compiler on raw conversation. Compare output graph to manual graph. Metrics: node match edge match contradiction detection missing reasoning rate', 'future_direction', 'test harness'),
('Computable Epistemology', 'The field this architecture belongs to. Not chatbot improvement not memory systems not summarization. Structured reasoning systems', 'core_concept', 'domain classification'),
('Phase A', 'Design Space Exploration - ontology refinement layer definitions edge typing. Natural attractor: every inconsistency generates another abstraction', 'core_concept', 'design phase'),
('Phase B', 'Compiler Reality Check - input to output transformation deterministic extraction measurable error rates. Forcing function that breaks design loop', 'core_concept', 'execution phase'),
('Minimal Compiler v0', 'Hard cut scope: raw conversation in claims and relations out. No contexts proofs BCL confidence versioning. Naive extractor. Just execution', 'future_direction', 'v0 spec'),
('Prediction Test', 'Give compiler conversation that stops halfway. Ask it to predict likely contradiction before anyone says it. Tests reasoning not memory', 'future_direction', 'test harness'),
('Circling Problem', '8 rounds of let me add one more thing and zero rounds of let me build it. Designing feels safe building feels risky', 'limitations', 'process issue'),
('Evidence Rule', 'Every atom answers 6 questions: Where from What evidence Which compiler version What confidence Still current What superseded me', 'core_principle', 'atom metadata'),
('Package Not Database', 'Compiler produces Knowledge Package not a database. SQLite MySQL JSON BCL Neo4j Qdrant are all just storage backends', 'architecture_principle', 'storage separation');

INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 535, 903, 'defines' FROM glossary_terms WHERE term='Knowledge Package';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 540, 916, 'defines' FROM glossary_terms WHERE term='Compilation Manifest';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 541, 917, 'defines' FROM glossary_terms WHERE term='Knowledge Runtime';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 538, 912, 'defines' FROM glossary_terms WHERE term='Extraction Contract';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 539, 914, 'defines' FROM glossary_terms WHERE term='Interpret Phase';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 543, 920, 'defines' FROM glossary_terms WHERE term='Inference Layer';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 545, 929, 'defines' FROM glossary_terms WHERE term='Higher-Order Atom';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 550, 940, 'defines' FROM glossary_terms WHERE term='Proof Artifact';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 550, 941, 'defines' FROM glossary_terms WHERE term='Compiler Quality Metrics';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 551, 942, 'defines' FROM glossary_terms WHERE term='Claim';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 553, 946, 'defines' FROM glossary_terms WHERE term='Context';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 554, 947, 'defines' FROM glossary_terms WHERE term='Five Layer Model';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 556, 949, 'defines' FROM glossary_terms WHERE term='The Invariant';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 557, 950, 'defines' FROM glossary_terms WHERE term='Reproducibility Test';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 558, 951, 'defines' FROM glossary_terms WHERE term='Computable Epistemology';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 559, 952, 'defines' FROM glossary_terms WHERE term='Circling Problem';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 560, 953, 'defines' FROM glossary_terms WHERE term='Phase A';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 560, 953, 'defines' FROM glossary_terms WHERE term='Phase B';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 561, 955, 'defines' FROM glossary_terms WHERE term='Minimal Compiler v0';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 549, 939, 'defines' FROM glossary_terms WHERE term='Prediction Test';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 536, 907, 'defines' FROM glossary_terms WHERE term='Evidence Rule';
INSERT INTO glossary_links (term_id, book_id, chapter_id, section_id, link_type) 
SELECT term_id, 40, 536, 908, 'defines' FROM glossary_terms WHERE term='Package Not Database';
COMMIT;
