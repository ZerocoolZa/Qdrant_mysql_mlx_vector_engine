# QA Engine Specification — Configurability

## 1. Model Selection

- All models must be configurable.
- No model names may be hardcoded into execution paths.
- Embedding model must be selectable at runtime.
- QA extraction model must be selectable at runtime.
- Optional LLM model must be selectable at runtime.
- Multiple embedding models must be supported.
- Multiple QA models must be supported.
- Model configuration must be stored separately from code.

Examples: BGE, E5, Nomic, MiniLM, CodeBERT, GraphCodeBERT, BERT QA, DistilBERT QA, CoreML QA, Future models.

## 2. Storage Modes

- **Mode A: RAM Only** — Document loaded into RAM, chunks created in RAM, embeddings generated in RAM, search in RAM, QA extraction, results returned, embeddings discarded.
- **Mode B: Persistent Vector Store** — Document loaded, chunks generated, embeddings generated, stored in vector database, future queries reuse stored embeddings.
- **Mode C: Hybrid** — RAM cache first, persistent vector store as backing store, frequently accessed embeddings remain resident.

Storage mode must be configurable.

## 3. Vector Backend Selection

Vector backend must be configurable. Supported: Qdrant, FAISS, SQLite Vector, RAM Index, Future backends. No execution path may assume a specific vector database.

## 4. Embedding Persistence Policy

Options: Never Save, Save On Demand, Always Save, Save Only High Value, Save Only Curated Knowledge, Refresh Existing, Force Rebuild.

## 5. Embedding Refresh Policy

Support: Full rebuild, Incremental rebuild, Changed document rebuild, Manual rebuild, Scheduled rebuild.

## 6. Hardware Awareness

Detect: CPU cores, RAM size, Free RAM, GPU availability, GPU memory, Apple Metal/MPS, Disk capacity, Disk free space. Hardware info must influence execution strategy.

## 7. Execution Modes

- **CPU Mode** — Force CPU execution.
- **GPU Mode** — Force GPU execution.
- **Auto Mode** — Automatically choose best device.
- **Hybrid Mode** — Split workloads across devices.

## 8. Resource Policies

Configurable limits: Max RAM, Max VRAM, Max chunk count, Max embedding count, Max document size, Max retrieval depth, Max QA context size.

## 9. Retrieval Configuration

Configurable: Top-K, Similarity threshold, Distance metric, Chunk size, Chunk overlap, Retrieval depth, Reranking enabled/disabled.

## 10. QA Configuration

Engines: CoreML QA, BERT QA, DistilBERT QA, CodeBERT QA, Future. Config: Confidence threshold, Max answer length, Span extraction mode, Multi-answer mode.

## 11. Pipeline Modes

- **Retrieval Only** — Return evidence only.
- **Retrieval + QA** — Return extracted answer.
- **Retrieval + QA + LLM** — Return extracted answer plus synthesized response.

## 12. Truth Classification

Modes: TRUE, FALSE, UNKNOWN. Classification thresholds must be configurable.

## 13. Performance Metrics

Record: Embed latency, Retrieval latency, QA latency, Total latency, RAM usage, VRAM usage, Disk usage, Retrieval score, QA confidence.

## 14. Failure Attribution

Every failure must identify the stage: DOCUMENT_LOAD, CHUNKING, EMBEDDING, VECTOR_STORE, RETRIEVAL, RERANKING, QA_EXTRACTION, CLASSIFICATION, RESOURCE_LIMIT.

## 15. Future-Proofing Rule

Embedding models, QA models, vector stores, rerankers, LLMs, storage policies — all replaceable components. No component may become a permanent architectural dependency.
