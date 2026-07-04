# [@GHOST]{[@file<MAGNETIC_SEARCH_V3.md>][@domain<Piplines>][@role<architecture>][@auth<cascade>][@date<2026-06-27>][@ver<3.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<architecture>][@return<none>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>]}

# Magnetic Search v3 — Context Reconstruction Engine

## What It Is

Magnetic Search is NOT a search engine. It is a **context reconstruction engine**.

| Traditional search | Vector search | Magnetic Search |
|---|---|---|
| Find rows matching X | Find things semantically similar to X | Reconstruct the working context around X |

## The Pipeline

```
Search Term
    ↓
Locate occurrences (MySQL tables + chat history + files on disk)
    ↓
Expand radius around each occurrence (±200 lines)
    ↓
Merge overlapping regions
    ↓
Recover surrounding context
    ↓
Rank by authority weight + relevance
    ↓
Return a coherent context packet
```

## What msearch --full Already Returns

| Field | Source |
|---|---|
| ID | code_index |
| BCL | bcl_methods (ast_hash, inputs, outputs) |
| BCL IR | bcl_edges (407K edges) |
| IR representation | code_index (evidence JSON) |
| Class code | code_classes (class_code) |
| Methods | code_index (entity_name) |
| Weight | authority_score, survival_score |
| Computational units | code_co_occurrence |
| File | code_classes, code_registry |
| Source | code_registry (code) |

## What v3 Adds — Magnetic Radius

### Multi-Dimensional Radius Expansion

| Radius Type | What It Expands | Source |
|---|---|---|
| Text Radius | ±200 lines around each hit | devin_messages, files on disk |
| AST Radius | Same class, same method, parent, children | DomIndexer |
| Execution Radius | Callers, callees | bcl_edges (CALL edges) |
| Dependency Radius | Imports, uses, used by | bcl_edges (IMPORT, RESOURCE) |
| Temporal Radius | Previous revisions, related commits | execution_log |
| Conversation Radius | Earlier chat, later chat, same topic | devin_messages |
| Semantic Radius | Embedding neighbors | Qdrant |
| BCL Radius | Same capability, same authority | bcl_methods (method_type) |
| IR Radius | Same execution graph | bcl_edges (STATE_READ, STATE_WRITE) |

### Chat History Radius

The key addition in v3. When a keyword is found in chat history:

```
keyword = "MemUnit"
    ↓
Chat #1482, line 812
    ↓
radius ±250 lines (messages before and after)
    ↓
extract context window
    ↓
compress if needed
    ↓
rank by recency + relevance
    ↓
return as part of context packet
```

This is how humans remember conversations:
> "That discussion we had around MemUnit, where we were also talking about Ghost registration and runtime tags."

That's contextual recall, not keyword retrieval.

## The Context Packet

One `msearch "MemUnit" --magnetic` call returns:

```json
{
  "query": "MemUnit",
  "packet": {
    "authority": { "class": "MemUnit", "definition": "..." },
    "bcl": { "stamps": [...], "ir": [...] },
    "code": { "files": [...], "methods": [...], "source": "..." },
    "weight": { "authority_score": 3.0, "survival_score": 0.7 },
    "graph": { "callers": [...], "callees": [...], "dependencies": [...] },
    "rules": [...],
    "chat_context": [
      { "session": "bottled-tarsier", "around_line": 812, "window": "±250 messages", "text": "..." },
      { "session": "mirror-theory", "around_line": 45, "window": "±250 messages", "text": "..." }
    ],
    "timeline": [...],
    "related": [...],
    "confidence": 0.92
  }
}
```

## CLI

```
msearch MemUnit --magnetic              # full magnetic radius (all dimensions)
msearch MemUnit --magnetic --radius 200  # custom radius (±200 lines)
msearch MemUnit --magnetic --chat       # chat history radius only
msearch MemUnit --magnetic --graph      # execution + dependency radius only
msearch MemUnit --full                 # semantic object (12 sections, no radius)
msearch MemUnit                        # standard keyword search
```

## Three Retrieval Primitives — The Distinction

### 1. Embeddings (Probabilistic)

Answers: **"What is like this?"**

```
Query
  │
Similarity search
  │
Top-K nearest neighbours
```

Returns things that are conceptually related but may never mention your exact term.
It guesses. It infers. It says: "I think the house you're looking for is somewhere
in this neighbourhood."

### 2. Magnetic Search (Deterministic)

Answers: **"Where exactly did this occur, and what was happening around it?"**

```
Query
  │
Exact occurrence
  │
Expand blast radius
  │
Return surrounding context
```

It doesn't guess. It doesn't infer. It says: "The word occurred here.
Here's the surrounding evidence. Here's the exact address. Here's the front door.
Here's the rooms next to it."

Pipeline: **Locate → Expand → Collect → Merge → Present**

### 3. Graph Traversal (Relational)

Answers: **"What is connected to this, and what is connected to those?"**

```
Query
  │
Locate occurrence
  │
Expand radius
  │
Follow explicit relationships (edges)
  │
Expand again around each linked entity
  │
Merge
  │
Rank
  │
Present
```

A graph means there are explicit edges:
- Message A → replies_to → Message B
- Class A → calls → Class B
- Chat #421 → references → file.py
- file.py → defines → ClassA
- ClassA → has → BCL stamp
- BCL stamp → references → rule
- rule → originated from → chat #421

Pipeline: **Locate → Expand → Follow relationships → Expand again → Merge → Rank → Present**

### How They Complement Each Other

| Primitive | When to use | What it preserves |
|---|---|---|
| Magnetic Search | Recover precise evidence | Original context around exact match |
| Graph Traversal | Trace relationships across domains | Explicit edges between entities |
| Embeddings | Broaden search beyond exact occurrences | Semantic similarity |

A strong retrieval system uses magnetic search to recover precise evidence first,
then graph traversal to follow relationships, then embeddings only when it needs
to broaden beyond exact occurrences.

## v4 — Graph Layer

v3 does: Locate → Expand → Collect → Merge → Present

v4 adds: **Follow relationships → Expand again**

```
Chat hit mentions "Core_MemUnit.py"
    ↓ follow
Core_MemUnit.py defines class MemUnit
    ↓ follow
MemUnit has BCL stamp [@EXECUTE]
    ↓ follow
[@EXECUTE] references rule "never hardcode"
    ↓ follow
"never hardcode" originated from chat #421
    ↓ expand
±200 messages around chat #421, line 812
    ↓ merge
Full context packet with provenance chain
```

The graph layer links windows together across domains:
- chat → file (chat mentions file path)
- file → class (file defines class)
- class → BCL (class has BCL stamps)
- BCL → rule (BCL references rules)
- rule → chat (rule originated from chat)

Each hop expands the radius again, collecting more context.
The result is a connected neighborhood, not just isolated windows.

## v5 — Memory Cognition Infrastructure

v3 does:  Locate → Expand → Collect → Merge → Present
v4 adds:  Follow relationships → Expand again
v5 adds:  Compile → Store → Recall → Update → Evolve

The system is no longer a search engine. It is a **memory compiler**.

```
First query:  COMPILE  →  run magnetic search  →  store as persistent object
Later query:  RECALL   →  load from storage     →  instant (16x faster)
New data:     UPDATE   →  incremental merge     →  only diff is stored
Over time:    EVOLVE   →  versioned history     →  full provenance chain
```

### Memory Object Lifecycle

```
COMPILE (first time)
  │
  ├─ Run magnetic search (9 sections)
  ├─ Build provenance (where each section came from)
  ├─ Extract graph edges
  ├─ Store in memory_objects table
  └─ Record v1 in evolution log

RECALL (subsequent)
  │
  ├─ Load from memory_objects table
  ├─ Increment access_count
  └─ Return instantly (no recomputation)

UPDATE (new data arrives)
  │
  ├─ Run magnetic search again
  ├─ Diff against stored packet
  ├─ If changes: merge, increment version, record evolution
  └─ If no changes: return "no_changes"

EVOLVE (history)
  │
  └─ Return full evolution log with versions, change types, deltas
```

### Performance

```
COMPILE:  0.267s  (full magnetic search across 9 dimensions)
RECALL:   0.017s  (load from MySQL — 16x faster)
```

### Storage Schema

```sql
memory_objects:
  id, query_key (SHA256), query_text, mode, radius,
  packet (JSON), provenance (JSON), graph_edges (JSON), section_counts (JSON),
  version, access_count, created_at, updated_at

memory_object_evolution:
  id, memory_object_id, version, change_type, change_summary,
  sections_affected, delta_count, changed_at
```

## Architecture

```
msearch.c v5
├── --mode exact       col = 'keyword'
├── --mode prefix      col LIKE 'keyword%'
├── --mode contains    col LIKE '%keyword%' (default)
├── --mode regex       col REGEXP 'keyword'
├── --mode magnetic    locate + expand + reconstruct
├── --full             12-section semantic object
├── --magnetic         context reconstruction with radius
├── --semantic         Qdrant vector search
├── --hybrid           MySQL + Qdrant combined
└── standard           keyword across tables

MagneticGraph.py (v4: graph traversal layer)
├── Multi-hop: chat → file → class → BCL → rule → chat
├── Provenance chain: each hop recorded
├── Expand again at each hop
├── Merge all windows into connected neighborhood
└── Rank by authority + relevance + hop distance

MemoryObject.py (v5: memory cognition infrastructure)
├── COMPILE — first query creates persistent memory object
├── RECALL — load from storage (16x faster than recompute)
├── UPDATE — incremental merge when new data arrives
├── EVOLVE — versioned history with full provenance
├── DIFF — compare versions
├── LIST — all memory objects
└── FORGET — delete memory object
```
