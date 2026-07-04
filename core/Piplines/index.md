#[@GHOST]{file_path="core/Piplines/index.md" date="2026-07-03" author="cascade" session_id="pipeline-library-index" context="Library-level index of all pipeline books. Entry point into the pipelines knowledge domain."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="index.md" domain="pipelines" authority="Cascade"}
#[@SUMMARY]{summary="Index of indexes. Routes between all PLF books. Each book is a self-contained pipeline with chapters. Each chapter has a mini-index. SQLite is the execution backend."}

---

# Pipelines Library Index

> **Purpose:** Entry point into all pipeline books. Cross-book navigation, comparison, and classification.
> **Model:** Library → Books → Chapters → Mini-Indexes → SQLite execution layer.

---

## Books

| Book | File | Purpose | Chapters | Status |
|---|---|---|---|---|
| Code Ingestion | `Plf_CodeIngestionPipeline.md` | Ingest .py files into SQLite, query method bodies, assemble merged files | 5 | ACTIVE |
| VBStyle DB Fix | `Plf_VBStyleDbFixPipeline.md` | Granular method repair via SQL — 1 method = 1 row = 1 UPDATE | 6 | ACTIVE |
| Code Graph | `Plf_Pipeline.md` | General code-to-DB pipeline: SYNC→INGEST→GRAPH→REASON→REPAIR→EXPORT→VERIFY→ARCHIVE | 12 | ACTIVE |
| BCL Code Graph | `Plf_BclCodeGraphPipeline.md` | Code → AST → BCL identity tokens → MySQL vb_code_test | 7 | ACTIVE |
| BCL Code Lifecycle | `Plf_PipelineBclCodeLifecycle.md` | INGEST→REUSE→WEIGHT→PURGE→RETIRE→SYNC→RECOVER cycle | 7 | ACTIVE |
| Config Cascade | `Plf_ConfigCascadePipeline.md` | Extract hardcoded values → generate Config.py files | 7 | ACTIVE |
| Config Files Manual | `Plf_ConfigFiles.md` | Authoritative reference for Config.py file structure | 16 | ACTIVE |
| Always Learning | `Plf_AlwaysLearningPipeline.md` | Worker generates, supervisor catches, DB records, confidence gate updates | 5 | ACTIVE |
| BCL Template Maker | `Plf_BclTemplateMakerPipeline.md` | Header editor → stamp → capsule → verify identity on files | 6 | ACTIVE |
| BCL Unit Builder | `Plf_BclUnitBuilderPipeline.md` | BCL spec → generate .c unit → compile → register in tool stack | 8 | ACTIVE |
| Cascade PB Reader | `Plf_CascadePbReaderPipeline.md` | Decrypt .pb chat files → parse protobuf → SQLite → search | 5 | ACTIVE |
| ChatMover | `Plf_ChatmoverPipeline.md` | Chats from all sources → MySQL → BCL compression → SQLite | 8 | ACTIVE |
| BCL Chat Compression | `Plf_BclChatCompressionPipeline.rmd.md` | 4,000-line chat → 200-token BCL file with [@CHATSOURCE] link | 7 | ACTIVE |
| Context Expansion | `Plf_ContextExpansionPipeline.md` | Chat → parse → nodes/edges → in-RAM SQLite → graph → domains → BCL identity | 6 | ACTIVE |
| Database Management | `Plf_DatabaseManagement.md` | Reference for MySQL/Neo4j/Qdrant/SQLite/LMDB — start/stop/health | 26 | ACTIVE |
| Database Storage Architecture | `Plf_DatabaseStorageArchitecture.md` | Design doc for 4-layer memory stack (Neo4j+MySQL+Qdrant+LMDB) | 5 | ACTIVE |
| Dom_Graph Pipeline | `Plf_DomGraphPipeline.md` | Auto-generated domain breakdown for Dom_Graph folder (161 files) | 7 | ACTIVE |
| Dom_Mcp Migration | `Plf_DomMcpPipeline.md` | MCP server migration tracker — Node.js → Go binaries | 5 | ACTIVE |
| Error Capture | `Plf_ErrorCapturePipeline.md` | Errors → captured with cause+solution → SQLite+MySQL → prevent recurrence | 5 | ACTIVE |
| Graph Engine Codebase | `Plf_GraphEngineCodebase.md` | Code asset inventory — maps graph engine code in MySQL databases | 4 | ACTIVE |
| Graph Ingest Spec | `Plf_GraphIngestSpec.md` | Spec for unifying 3 graph folders into one VBStyle domain in SQLite | 11 | ACTIVE |
| Magnetic Radius Search | `Plf_MagneticRadiusSearch.md` | Cross-chat context retrieval — word match → ±200 lines radius | 5 | ACTIVE |
| Magnetic Search v3 | `Plf_MagneticSearchV3.md` | Context reconstruction engine — locate→expand→merge→rank→return | 4 | ACTIVE |
| MemUnit BCL Engine | `Plf_MemunitBclEngine.md` | MemUnit base class design — BCL parser in one place | 6 | ACTIVE |
| MemUnit References | `Plf_MemunitReferences.md` | MySQL search results for MemUnit references (1,901 hits) | 3 | REFERENCE |
| Pipeline Gap Analysis | `Plf_PipelineGapAnalysis.md` | Maps all 10 pipelines, finds connections and holes (23 gaps) | 8 | ACTIVE |
| Pipeline Graph Engine | `Plf_PipelineGraphEngine.md` | 14 file manipulation primitives → 221K pipelines → classify → execute | 5 | ACTIVE |
| Provenance | `Plf_ProvenancePipeline.md` | Search → Report → Copy → Track provenance — unified into DomReport | 5 | ACTIVE |
| Scratching My Head | `Plf_ScratchingMyHead.md` | Design ideas for MemUnit composition root + Dom_ modules | 4 | DESIGN |
| Session Graph | `Plf_SessionGraph.md` | Session path tracker — main thread, distractions, completion state | 3 | ACTIVE |
| Utilities | `Plf_UtilitiesPipeline.md` | Config triggers → scheduler → orchestrator → utilities execute | 19 | ACTIVE |
| Workflow 8-Graph | `Plf_Workflow8GraphPipeline.md` | 8-graph reasoning: Idea→Plan→Spec→Flow→Lifecycle→Dep→Error→Orch→Gap→Code | 4 | ACTIVE |
| Word Index Search | `Plf_WordIndexSearch.md` | Word-level index of .md/.py files → SQLite → search → ±N words context | 4 | ACTIVE |
| VBEngine Architecture | `PLF_VBENGINE_ARCHITECTURE.md` | GPU-first Word2Vec training architecture on Apple Silicon | 8 | ACTIVE |
| Cleanup List | `Plf_CleanupList.md` | Tracking doc for deleted temp/junk files | 3 | ARCHIVE |
| Chat Pipeline Results | `Plf_ChatPipelineResults.md` | Graph output from a chat analysis session | 3 | ARCHIVE |
| Pipeline Results | `Plf_PipelineResults.md` | Graph output from a pipeline analysis session | 3 | ARCHIVE |
| CLI Safe Execution | `Plf_CliSafeExecutionPipeline.md` | CLI state machine — validate→execute→capture errors→query KB | 6 | ACTIVE |

---

## Cross-Pipeline Map

```
Chat Ingestion (ChatMover) ──→ Code Ingestion ──→ VBStyle DB Fix
                                    │
                                    ↓
                              BCL Code Graph ──→ Context Expansion
                                    │
                                    ↓
                              Config Cascade ──→ BCL Template Maker
                                    │
                                    ↓
                              Error Capture ←── CLI Safe Execution
                                    │
                                    ↓
                              Pipeline Gap Analysis (meta)
```

---

## How to Use This Index

1. **Find a pipeline** — Scan the Books table for your task
2. **Open the book** — Read its internal index (chapter list)
3. **Navigate to a chapter** — Each chapter has a mini-index
4. **Execute** — Follow the chapter steps; SQLite is the truth layer

---

## See Also

- `glossary.md` — Global glossary with cross-references to all books
