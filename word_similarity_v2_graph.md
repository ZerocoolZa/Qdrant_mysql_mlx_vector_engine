# CoreMLSemanticSearch v2.0 — Dependency Graph

```
                    ┌─────────────────────────────────────────────────┐
                    │                   INPUT SOURCES                   │
                    └─────────────────────────────────────────────────┘
                                           │
              ┌──────────┬──────────┬──────┴───────┬──────────┐
              │          │          │              │          │
         Filesystem    MySQL    ChatHistory    Dictionary   (future)
              │          │          │              │
              └──────────┴────┬─────┴──────────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │  SemanticExtractor   │
                   │  ┌───────────────┐  │
                   │  │ extract_python │  │  AST: ClassDef, FunctionDef,
                   │  │ extract_md     │  │  Import, Assign, Expr
                   │  │ extract_json   │  │  Headers, Bold, CodeRef, BCL
                   │  │ extract_generic│  │  WalkKeys, DictKey
                   │  └───────────────┘  │  Regex fallback
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │     Normalizer       │
                   │  normalize           │  LowerCase, Unicode,
                   │  canonical           │  CamelSplit, SnakeSplit
                   │  split_camel         │  LengthFilter, DigitFilter
                   │  split_snake         │
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │    Deduplicate       │  Set-based, O(1) lookup
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │ EmbeddingPipeline    │
                   │  ┌───────────────┐  │
                   │  │  CoreMLModel   │  │  all-MiniLM-L6-v2
                   │  │  Tokenizer     │  │  HuggingFace BERT
                   │  │  BatchPredict  │  │  ~850 embeds/s
                   │  │  Progress      │  │  ETA tracking
                   │  └───────────────┘  │
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │    VectorStore       │  SQLite
                   │  ┌───────────────┐  │
                   │  │ term_norm      │  │  TEXT UNIQUE
                   │  │ vector_blob    │  │  BLOB (1536 bytes)
                   │  │ source         │  │  TEXT
                   │  │ file_path      │  │  TEXT
                   │  │ line_number    │  │  INTEGER
                   │  │ symbol_type    │  │  TEXT
                   │  │ term_hash      │  │  TEXT (md5)
                   │  │ domain         │  │  TEXT
                   │  │ tags           │  │  TEXT
                   │  │ created_at     │  │  REAL
                   │  └───────────────┘  │
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │   LoadVectors →      │  np.frombuffer → stack
                   │   Matrix[N, 384]     │  ~0.1s for 50K
                   └──────────┬──────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
    ┌─────────────────┐ ┌───────────┐ ┌───────────────┐
    │ SimilarityEngine│ │ ANNIndex  │ │ ClusterEngine │
    │                 │ │           │ │               │
    │ cosine          │ │ argparti- │ │ KMeans        │
    │ dot_product     │ │ tion fast │ │ get_clusters  │
    │ euclidean       │ │ insert    │ │ find_cluster  │
    │ hybrid          │ │           │ │               │
    │ lexical_boost   │ │           │ │               │
    └────────┬────────┘ └─────┬─────┘ └───────┬───────┘
             │                │               │
             └────────────────┼───────────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │  KnowledgeGraph      │
                   │  nodes + edges       │  SimMatrix → Threshold
                   │  adjacency list      │  TopK per node
                   │  BFS neighbors       │  depth-limited
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │    QueryEngine       │
                   │  embed query         │
                   │  rank results        │
                   │  reverse search      │  group by type
                   │  explain ranking     │
                   └──────────┬──────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │     API     │  │     CLI     │  │ BCLExporter │
    │             │  │             │  │             │
    │ search      │  │ <phrase>    │  │ BCL         │
    │ embed       │  │ ann         │  │ JSON        │
    │ add         │  │ hybrid      │  │ Graph JSON  │
    │ delete      │  │ boost       │  │ Results BCL │
    │ rebuild     │  │ rev         │  │             │
    │ cluster     │  │ cluster     │  │             │
    │ graph       │  │ graph       │  │             │
    │ stats       │  │ stats       │  │             │
    │             │  │ export      │  │             │
    │             │  │ add         │  │             │
    │             │  │ rebuild     │  │             │
    │             │  │ bcl         │  │             │
    │             │  │ quit        │  │             │
    └─────────────┘  └─────────────┘  └─────────────┘
```

## Upgrade Diff Graph: v1.0 → v2.0

```
v1.0                              v2.0
─────                             ─────
RegexExtractor           ──REPLACE──→ SemanticExtractor (AST)
  regex patterns                       ast.walk, ClassDef, FunctionDef
                                        Import, Assign, Expr
                                        JSON keys, MD headers
                                        BCL tokens

(no normalizer)          ──ADD─────→ Normalizer
                                        Unicode, LowerCase
                                        CamelSplit, SnakeSplit
                                        Canonical filter

SQLiteBlob                ──REPLACE──→ VectorStore
  term + vector             (12 columns)
                              term_normalized, source, file_path,
                              line_number, symbol_type, term_hash,
                              domain, tags, created_at

Cosine only               ──ADD─────→ SimilarityEngine
                                        cosine, dot, euclidean
                                        hybrid (weighted)
                                        lexical_boost

(no ANN)                  ──ADD─────→ ANNIndex
                                        argpartition (fast top-N)
                                        incremental insert

(no cluster)              ──ADD─────→ ClusterEngine
                                        KMeans
                                        concept families
                                        find_cluster

(no graph)                ──ADD─────→ KnowledgeGraph
                                        nodes + edges
                                        adjacency list
                                        BFS neighbors

(no stats)                ──ADD─────→ Statistics
                                        count, by_source, by_domain
                                        matrix shape, RAM, clusters

(no export)               ──ADD─────→ BCLExporter
                                        BCL, JSON, Graph JSON
                                        Results BCL

(search only)             ──ADD─────→ ReverseSearch
                                        group by symbol_type
                                        rank within type

(no domain)               ──ADD─────→ DomainGuess
                                        keyword → domain mapping
```

## Data Flow Graph

```
Text Input
    │
    ▼
Tokenizer (BERT)
    │
    ▼
input_ids[1,128] + attention_mask[1,128]
    │
    ▼
CoreML Model (Neural Engine)
    │
    ▼
sentence_embedding[1,384]
    │
    ▼
np.float32[384]
    │
    ├──────────────────────┐
    │                      │
    ▼                      ▼
VectorStore           SimilarityEngine
  (SQLite)              cosine / dot /
  store()               euclidean / hybrid
    │                      │
    │                      ▼
    │                  argsort → top-N
    │                      │
    ▼                      ▼
load_all_vectors()    RankedResults
    │                      │
    ▼                      ├──→ CLI print
Matrix[N,384]              ├──→ BCL export
    │                      ├──→ JSON export
    ├──→ ANNIndex          └──→ Graph export
    │
    ├──→ ClusterEngine
    │      KMeans
    │      labels[N]
    │
    └──→ KnowledgeGraph
           SimMatrix[N,N]
           threshold → edges
           adjacency
```
