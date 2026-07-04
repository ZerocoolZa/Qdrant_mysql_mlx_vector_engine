# Database & Storage Architecture: The 4-Layer Memory Stack

## Origin

This document is the third design group — the **storage and database architecture**
for the 21-component graph engine memory system. It covers database selection,
data flow, ownership rules, the storage stack analysis, and MySQL references.

Extracted from the design sections in `test_all_on_chat.py` (sections 10-12).

---

# Graph Database Comparison

| Database | Best At | Verdict |
|----------|---------|---------|
| Neo4j | Property graphs, traversal, relationships | Most mature graph DB |
| TigerGraph | Massive graphs, analytics | Enterprise scale |
| JanusGraph | Distributed graph storage | Good but complex |
| ArangoDB | Graph + Document | Very flexible |
| Memgraph | Fast graph processing | Excellent for realtime |
| Qdrant | Semantic/vector search | Not a graph DB |
| MySQL | Structured storage | Not a graph DB |

---

# Recommended Architecture: 3-Database Stack

For the 21-component memory system:

```
Neo4j  +  MySQL  +  Qdrant
```

## Neo4j (Graph Database)

**Stores:** Message, Observation, Fact, Episode, SemanticMemory nodes
**Stores:** SUPPORTED_BY, BEFORE, AFTER, CAUSES, RESOLVES, PART_OF,
SAME_AS, CONTRADICTS relationships

This is what Neo4j is BUILT FOR — native graph traversal.

Example Cypher query:
```cypher
MATCH p=
  (Problem)-[:CAUSED_BY]->(Action)
            -[:LED_TO]->(Error)
            -[:FIXED_BY]->(Fix)
RETURN p
```

That's native graph traversal — no JOINs, no table scans.

## MySQL (Relational Database)

**Stores:** Raw chat text, logs, feedback records, metrics, audit history
**Already have:** graph_computation_units (2,407 units), vb_code_test,
vb_shared knowledge base
**Role:** Relational data, structured storage, existing knowledge base

## Qdrant (Vector Database)

**Stores:** Embeddings, semantic similarity, meaning search
**Already have:** Qdrant running in this workspace
**Role:** Semantic activation — "find nodes that MEAN the same thing"

Example flow:
```
User: "Why did RustDesk fail?"
Qdrant finds: RustDesk, Remote desktop, SSH, relay mode, disconnects
Neo4j traverses: RustDesk -> CAUSED_BY -> relay -> LED_TO -> disconnect
                 -> FIXED_BY -> SSH -> RESOLVES
```

---

# Single Database Option (If Forced to Choose One)

**1st Choice: Neo4j**
Because the system is fundamentally:
- Node, Edge, Evidence, Identity, Hierarchy, Temporal, Causal
- which is graph-native
- Neo4j is the closest match to the
  Message -> Observation -> Fact -> Episode -> Semantic Memory architecture

**2nd Choice: ArangoDB**
Because it can do Graph + Document + Key-Value inside one engine.
More flexible but less mature for pure graph traversal.

---

# Migration Path: MySQL to Neo4j

The current `graph_computation_units` table already contains graph data
in relational form: Method, Class, Domain, File.

This can be migrated directly to Neo4j:

```cypher
(:Domain)-[:CONTAINS]->(:Class)
(:Class)-[:CONTAINS]->(:Method)
(:Method)-[:IN_FILE]->(:File)
```

### Migration Steps

1. Read all rows from `graph_computation_units.computation_units`
2. Create Domain nodes (unique domains)
3. Create Class nodes (unique class_names)
4. Create Method nodes (each row = one method)
5. Create File nodes (unique file_paths)
6. Create CONTAINS edges (Domain -> Class, Class -> Method)
7. Create IN_FILE edges (Method -> File)
8. Import method body, signature, line numbers as node properties

This migration is straightforward — it's a 1:1 mapping from rows to nodes.
The hard part is the reasoning layers (Evidence, Truth, Observation), not
the structural migration.

---

# Neo4j Memory Model for 21-Component Engine

## Node Labels (with properties)

```
(:Message {
  id, text, role (user/assistant), timestamp, chat_id
})

(:Observation {
  id, text, type (Problem/Attempt/Result/Note),
  confidence, created_at
})

(:Fact {
  id, text, truth_state (CLAIM/VERIFIED/REJECTED/UNKNOWN),
  verified_by, verified_at, superseded_by, created_at
})

(:Episode {
  id, title, start_time, end_time, summary,
  state (ONGOING/CLOSED/COMPRESSED), node_count
})

(:SemanticMemory {
  id, text, compressed_from, created_at
})

(:Concept { id, name })
(:Tool { id, name, version })
(:File { id, path })
(:Entity { id, name, type })
(:Decision { id, text, made_at })
(:Error { id, text, occurred_at })
(:Task { id, text, state (OPEN/IN_PROGRESS/DONE/ABANDONED) })
(:Goal { id, text })
(:Blocker { id, text })
(:Hypothesis { id, text, confidence })
(:Experiment { id, text, tried_at })
(:Outcome { id, text, result (SUCCESS/FAILURE/PARTIAL) })
(:Evidence { id, text, confidence, source_ref })
(:Domain { id, name })
(:Class { id, name, domain })
(:Method { id, name, signature, body, line_start, line_end })
```

## Relationship Types (with properties)

### Memory Layer
```
(:Message)-[:OBSERVED_AS]->(:Observation)
(:Observation)-[:SUPPORTS {confidence}]->(:Fact)
(:Fact)-[:PART_OF]->(:Episode)
(:Episode)-[:COMPRESSED_TO]->(:SemanticMemory)
```

### Truth
```
(:Fact)-[:CONTRADICTS]->(:Fact)
(:Fact)-[:OBSOLETES]->(:Fact)
(:Fact)-[:REPLACES {at}]->(:Fact)
(:Fact)-[:SUPERSEDED_BY]->(:Fact)
```

### Temporal
```
(:Node)-[:BEFORE]->(:Node)
(:Node)-[:AFTER]->(:Node)
(:Node)-[:REPLACED_BY {at}]->(:Node)
(:Node)-[:VALID_DURING {from, to}]->(:Node)
```

### Identity
```
(:Node)-[:ALIAS_OF]->(:Node)
(:Node)-[:SAME_AS {confidence}]->(:Node)
(:Node)-[:RENAMED_TO {at}]->(:Node)
```

### Causal
```
(:Node)-[:CAUSED_BY]->(:Node)
(:Node)-[:RESOLVES]->(:Node)
(:Node)-[:LED_TO]->(:Node)
(:Action)-[:FIXED_BY]->(:Fix)
```

### Hierarchy
```
(:Domain)-[:CONTAINS]->(:Class)
(:Class)-[:CONTAINS]->(:Method)
(:Method)-[:IN_FILE]->(:File)
(:Node)-[:OWNS]->(:Node)
(:Node)-[:MEMBER_OF]->(:Node)
```

### Structural
```
(:Node)-[:REFERENCES]->(:Node)
(:Node)-[:DEPENDS_ON]->(:Node)
(:Node)-[:RELATED_TO {weight}]->(:Node)
```

## Indexes (for performance)

```cypher
CREATE INDEX FOR (m:Message) ON (m.chat_id)
CREATE INDEX FOR (m:Message) ON (m.timestamp)
CREATE INDEX FOR (f:Fact) ON (f.truth_state)
CREATE INDEX FOR (t:Task) ON (t.state)
CREATE INDEX FOR (e:Episode) ON (e.state)
CREATE INDEX FOR (c:Concept) ON (c.name)
CREATE INDEX FOR (f:File) ON (f.path)
CREATE INDEX FOR (d:Domain) ON (d.name)
CREATE INDEX FOR (c:Class) ON (c.name)
CREATE INDEX FOR (m:Method) ON (m.name)
```

## Example Queries

```cypher
// "Why did RustDesk fail?"
MATCH (p:Concept {name: 'RustDesk'})
      -[:CAUSED_BY]->(error:Error)
RETURN p, error

// "What fixed the SSH issue?"
MATCH (e:Error)-[:FIXED_BY]->(f:Fix)
WHERE e.text CONTAINS 'SSH'
RETURN e, f

// "What decisions were made in this episode?"
MATCH (d:Decision)-[:PART_OF]->(ep:Episode {id: $episodeId})
RETURN d

// "What facts are still verified?"
MATCH (f:Fact {truth_state: 'VERIFIED'})
WHERE NOT (f)-[:SUPERSEDED_BY]->()
RETURN f

// "Trace evidence chain for a fact"
MATCH path =
  (f:Fact {id: $factId})
    <-[:SUPPORTS]-(o:Observation)
    <-[:OBSERVED_AS]-(m:Message)
RETURN path
```

---

# 3-DB Data Flow: How They Work Together

## Division of Responsibility

```
MySQL  = Truth Store (structured records, codebase, computation units)
Qdrant = Meaning Store (embeddings, semantic similarity, context activation)
Neo4j  = Relationship Store (traversal, causality, identity, evidence chains)
```

## What Each DB Owns

### MySQL owns:
- Structured truth (codebase, classes, methods, files)
- Computation units (2,407 units, 224 classes)
- Raw chat messages (message_id, chat_id, timestamp, text)
- Audit logs, runtime state, configuration
- Feedback tables, metrics, execution state
- Existing knowledge base (vb_shared, vb_code_test)

### Qdrant owns:
- Embeddings (vector for each message, observation, fact)
- Semantic similarity (nearest-neighbor retrieval)
- Meaning search ("find nodes that MEAN the same thing")
- Context activation (which nodes are semantically relevant to a query)

### Neo4j owns:
- Relationships (traversal, causality, identity)
- Evidence chains (Fact -> Evidence -> Message -> Timestamp)
- Temporal links (BEFORE, AFTER, REPLACED_BY)
- Memory graph (Message -> Observation -> Fact -> Episode -> Semantic)
- Identity resolution (ALIAS_OF, SAME_AS)
- Hierarchy (Domain -> Class -> Method)

## Example Data Flow

User says: "RustDesk disconnects" / "SSH fixed it"

```
Step 1: MySQL stores raw records
  message_id=1001, chat_id=22, timestamp=..., text="RustDesk disconnects"
  message_id=1002, chat_id=22, timestamp=..., text="SSH fixed it"

Step 2: Qdrant stores embeddings
  embedding(message 1001) -> vector [0.12, 0.45, ...]
  embedding(message 1002) -> vector [0.08, 0.67, ...]
  Payload: {"message_id": 1001}

Step 3: Neo4j stores relationships
  (RustDesk)-[:CAUSED]->(DisconnectIssue)
  (DisconnectIssue)-[:RESOLVED_BY]->(SSH)
  (SSH)-[:SUCCESSFUL_FIX]->(DisconnectIssue)
```

Query flow:
```
User: "Why did remote desktop fail?"
-> Qdrant: semantic search finds "RustDesk disconnect" (words don't match, meaning does)
-> Neo4j: traverse from RustDesk node -> CAUSED -> DisconnectIssue
-> MySQL: fetch raw message text for evidence (message_id=1001)
-> LLM: receives structured context + evidence chain
```

## Why This Works (Each DB Does What It's Best At)

**MySQL** is excellent at:
- SELECT, JOIN, transactions, consistency, large structured datasets
- 2,407 computation units + 224 classes belong HERE
- Raw messages with exact timestamps belong HERE
- Feedback records with exact scores belong HERE

**Qdrant** is excellent at:
- Meaning, similarity, recall, context activation
- "Why did remote desktop fail?" finds "RustDesk disconnect issue"
  even when words don't match
- Semantic activation powers the graph activation engine

**Neo4j** is excellent at:
- "What caused this?" "What depends on this?" "What fixed this?"
- "What replaced this?" "How are these connected?"
- Those are GRAPH questions — native traversal, no JOINs

---

# CRITICAL TRAP: Do Not Duplicate

The biggest mistake people make is: store everything everywhere.

**DON'T.**

### Clean Model
```
MySQL    owns raw records
Qdrant   owns vectors
Neo4j    owns relationships
```

### ID Bridge
Use IDs to connect them. Same ID everywhere:
```
mysql.message.id = 1001
qdrant.payload = {"message_id": 1001}
neo4j node = (:Message {message_id: 1001})
```

The ID is the join key across all three databases.
The DATA lives in ONE place. The ID is the bridge.

### Violations of This Rule
- Storing message text in Neo4j (MySQL owns that)
- Storing embeddings in MySQL (Qdrant owns that)
- Storing relationships in MySQL JOINs (Neo4j owns that)
- Duplicating computation_units into Neo4j as full text
  (Neo4j should only store the ID + structural relationships)

---

# Future: How Architecture Evolves

As the system grows, Neo4j becomes the place where reasoning objects live:
```
Message, Observation, Fact, Episode, SemanticMemory,
Evidence, Decision, Task, Goal, Identity
```

While MySQL continues to own:
```
Codebase, Runtime, Configuration, Logs, Agents, Execution state
```

This is a very common architecture for large memory systems:

```
MySQL  = Truth Store      (what IS — structured facts, code, state)
Qdrant = Meaning Store    (what MEANS — semantic similarity, vectors)
Neo4j  = Relationship Store (what CONNECTS — how things relate)
```

Three stores, three responsibilities, one unified memory system.

---

# Storage Stack Analysis: Do We Need More Databases?

Current stack (MySQL + Qdrant + Neo4j) covers ~90-95% of the storage layer.
The biggest bottleneck is NOT another database — it's the reasoning layers
(Truth, Evidence, Identity, Temporal, Governor, Query Planner).
**Adding more storage engines does NOT solve reasoning problems.**

## Tier Ranking: Additional Engines

### TIER 1 (Potentially Useful Later)
**Redis** — cache, fast activation memory, agent state, queues, temp context
Very common addition. Optional but helpful for runtime performance.

### TIER 2 (Only If Needed)
**Elasticsearch** — massive text search, log analysis, monitoring
Useful when text corpus becomes huge (millions of .md files / chat messages)

### TIER 3 (Probably Unnecessary)
MongoDB, Cassandra, CouchDB — no role they fill isn't already covered

## Elasticsearch: When It Helps

Elasticsearch is useful when you need:
- Full-text search across millions of documents
- Log analytics and Kibana dashboards
- Fuzzy matching (typos, partial words)
- Google-like search with ranking and stemming

### Engine Comparison for Text Search

| Engine | Primary Job | Text Search Speed |
|--------|-------------|-------------------|
| MySQL | Store structured data | LIKE '%term%' — slow |
| SQLite | Small local database | LIKE '%term%' — slow |
| Elasticsearch | Search engine | Tokenized + indexed — ms |
| Qdrant | Meaning search | Semantic — ms |
| Neo4j | Relationship traversal | Not for text search |

Example: searching 500K markdown files + 50M chat messages + 10M code comments
```
SQLite:       Reads rows, LIKE '%rustdesk%' -> SLOW
MySQL:        SELECT * FROM messages WHERE body LIKE '%rustdesk%' -> better, not a search engine
Elasticsearch: Tokenized, indexed, ranked, fuzzy, stemming -> MILLISECONDS
```

## Elasticsearch vs Qdrant (Key Difference)

```
Elasticsearch answers: "Find text that CONTAINS: rustdesk, relay, ssh, disconnect"
  -> Keyword match, fuzzy, stemming, ranking
  -> Exact words and variations

Qdrant answers: "Find text with SIMILAR MEANING to: 'remote desktop connection problem'"
  -> Semantic similarity, embeddings
  -> Works even if the word "RustDesk" never appears
```

Both are needed for different reasons:
- Elasticsearch = keyword search (fast, exact, fuzzy)
- Qdrant = meaning search (semantic, conceptual)

## Ideal Stack for Large Memory System

```
Markdown Files
      |
      v
Elasticsearch -> Keyword Hits (fast text search)
      |
      v
Embeddings
      |
      v
Qdrant -> Semantic Hits (meaning search)
      |
      v
Relationships
      |
      v
Neo4j -> Evidence Chains (graph traversal)
      |
      v
Truth/Data
      |
      v
MySQL -> Structured Records (source of truth)
```

Many enterprise AI systems end up looking very similar to this.

## Complexity Tradeoff

Adding Elasticsearch means:
```
4 databases -> 4 backups -> 4 sync paths -> 4 failure modes
```

DON'T add Elastic because it's cool. Add it ONLY if:
- You have lots of text (millions of files/messages)
- You search text constantly
- LIKE queries are becoming painful
- You want Google-style search over .md files, chat logs, code comments

Elasticsearch is NOT replacing MySQL — it's replacing painful text searching.

---

# Final Storage Stack Recommendation

## Frozen Stack (Today)

| Priority | Database | Status | Role |
|----------|----------|--------|------|
| #1 | MySQL | MANDATORY | Structured truth, codebase, computation units |
| #2 | Qdrant | MANDATORY | Semantic memory, embeddings, meaning search |
| #3 | Neo4j | VERY VALUABLE | Relationship memory, graph traversal, evidence chains |
| #4 | Redis | OPTIONAL | Cache, agent runtime state, fast activation |
| #5 | Elasticsearch | VALUABLE LATER | When text corpus becomes huge |

## Priority for Next Effort

```
BUILD reasoning layers (Evidence, Truth, Temporal, Identity, Governor)
NOT more storage engines.

Reasoning layers are the bottleneck, not storage.
Adding Elasticsearch/MongoDB/Cassandra does not solve reasoning problems.
```

---

# MySQL References: Storage & Database in the Knowledge Base

## vb_shared.learned_rules (20 hits)

| id | pattern | fix_action |
|----|---------|------------|
| 147 | forbid: SQLite pages used as semantic storage | Separate execution storage from semantic registry |
| 149 | forbid: embeddings as primary storage | Use fact DB as primary, embeddings as search index only |
| 13623 | become truth storage | Follow rule: prohibition |
| 13650 | introduce json as a storage or architecture format | Follow rule: prohibition |
| 13827 | replace memdb row storage | Follow rule: prohibition |
| 13874 | be treated as truth storage | Follow rule: prohibition |
| 13953 | need to know the underlying storage mechanism | Follow rule: prohibition |
| 14812 | interfere with primary storage | Follow rule: prohibition |
| 15299 | become hidden truth storage | Follow rule: prohibition |
| 16151 | recursive search can hang on macos cloudstorage | Follow rule: requirement |
| 16201 | full conversation ingestion with permanent storage and reuse | Follow rule: requirement |
| 16209 | learning is concrete: correction -> storage -> reuse | Follow rule: requirement |
| 16620 | use files as source storage | Follow rule: prohibition |
| 18819 | recursive search can hang on macos cloudstorage | Follow rule: bug |
| 18937 | manage domain: storage | Follow rule: requirement |
| 19113 | be the primary storage | Follow rule: prohibition |
| 19177 | blame storage first. meanwhile the database is being asked the same question ten million times | Follow rule: requirement |
| 20910 | be treated as dead storage | Follow rule: prohibition |
| 25335 | python file scanner and database storage system | Follow rule: requirement |
| 25337 | parameters for file storage | Follow rule: requirement |

## vb_shared.tokens (6 hits)

| id | name | meaning |
|----|------|---------|
| 153 | [@Writeback] | Write-back operation for persisting changes to storage |
| 1790 | Self-Documenting Database | Database stores DATA, BEHAVIOR, KNOWLEDGE, DEPENDENCIES, EXECUTION, MEMORY |
| 1879 | [@ALWAYS_BACKUP_DATABASE_BEFORE_MODIFICATIONS] | Always backup database before modifications |
| 2115 | [@CLASSIFY_SETTINGS_DATABASES_AS_NON_CHAT] | Classify settings databases as non_chat |
| 2116 | [@CLASSIFY_TEST_DATABASES_AS_NON_CHAT] | Classify test databases as non_chat |
| 2229 | [@USE_DATABASE_OVER_FILE] | use_database_over_file |

## Key Database Principles from learned_rules

1. **Database over file** (id=2229, id=16620) — always prefer database storage over files
2. **Embeddings are index, not primary** (id=149) — fact DB is primary, embeddings are search
3. **No JSON as architecture** (id=13650) — use proper database schemas, not JSON blobs
4. **No hidden truth storage** (id=15299) — all truth storage must be explicit and structured
5. **Backup before modifications** (id=1879) — always backup database before changes
6. **Learning requires storage** (id=16209) — correction -> storage -> reuse is the learning cycle
7. **Don't blame storage first** (id=19177) — check query patterns before blaming the database
