# Magnetic Radius Search: Cross-Chat Context Retrieval

## Origin

Concept developed by the user during graph engine architecture discussions.
The user described a retrieval method where a word (e.g. "RustDesk") magnetically
pulls context from multiple chats across thousands of conversations, grabbing
not just the word match but ±200 lines of surrounding context to form a "clump"
of related conversation fragments.

The user called this "magnetic radius search" — where things are tracked to
each other magnetically, and context is collected in a radius around each hit.

---

## How It Works

### Step 1: Signal Detection

A word or phrase appears across many chats:

```
Chat 1:     "RustDesk disconnects"           (line 15)
Chat 5:     "relay mode broken"              (line 42)
Chat 332:   "SSH is stable"                  (line 8)
Chat 795:   "stopped using RustDesk"         (line 3)
Chat 14800: "remote desktop unreliable"      (line 22)
```

### Step 2: Magnetic Radius Expansion

For each hit, grab ±N lines of surrounding context:

```
Chat 1, lines 1-215:      full context around "RustDesk disconnects"
Chat 5, lines 1-242:      full context around "relay mode broken"
Chat 332, lines 1-208:    full context around "SSH is stable"
Chat 795, lines 1-203:    full context around "stopped using RustDesk"
Chat 14800, lines 1-222:  full context around "remote desktop unreliable"
```

### Step 3: Context Clump Formation

The 5 context windows form a "clump" — a collection of raw conversation
fragments from different chats, all magnetically attracted to the same signal.

### Step 4: LLM Reasoning Over Clump

The LLM receives all context windows and reads the full story arc:

- Chat 1: user was frustrated, tried relay fix
- Chat 5: relay didn't work, tried SSH
- Chat 332: SSH was stable, decision made
- Chat 795: confirmed RustDesk abandoned
- Chat 14800: someone asked why, referred back

The LLM compresses at reasoning time, not at storage time.

---

## Magnetic Radius vs Clustering

| Aspect              | Semantic Clustering              | Magnetic Radius Search              |
|---------------------|----------------------------------|-------------------------------------|
| What it groups      | Words by semantic similarity     | Context windows around word hits    |
| How it finds things | Embedding distance               | Word match + proximity radius       |
| What you get        | A named concept ("Remote Desktop Problem") | 5 chunks of real chat text, each ~200 lines |
| Cross-chat?         | Maybe, if embeddings are similar | YES — that's the whole point         |
| Preserves raw text? | No — compressed into a label     | YES — you get the actual conversation |
| Compression timing  | Early (at storage time)          | Late (at LLM reasoning time)        |

### Key Difference

Clustering compresses EARLY — it turns 47 chats into one label
("Remote Desktop Problem"). That loses detail.

Magnetic radius compresses LATE — it keeps all 47 chunks of raw text and
lets the LLM do the compression at reasoning time. The LLM sees the full
story arc across 14,800 chats, not a compressed label.

---

## Context Budget Problem

47 hits × 200 lines = 9,400 lines of text. That exceeds most LLM context windows.

### Solutions

1. **Radius tuning**
   - 200 lines for sparse hits (word appears in only 5 chats)
   - 20 lines for frequent words (word appears in 500 chats)

2. **Relevance ranking**
   - Not all 47 hits matter equally
   - Rank by: recency, frequency, semantic similarity, user confirmation

3. **Context budget management**
   - "I have 100K tokens, 47 hits, so ~2K tokens each = ~50 lines each"
   - Dynamically adjust radius based on hit count and token budget

4. **Tiered radius**
   - Tier 1 hits (exact match + recent): ±200 lines
   - Tier 2 hits (exact match + old): ±50 lines
   - Tier 3 hits (fuzzy match): ±20 lines

---

## Where It Sits in the Architecture

Magnetic Radius Search is **Level 1.5** — between word graph (Level 1) and
concept graph (Level 2).

- It's NOT just a word index because it grabs context windows, not just line numbers
- It's NOT yet a reasoning graph because it doesn't build typed edges (CAUSED_BY, RESOLVED_BY)

It is the **retrieval layer** that feeds the reasoning graph:

```
Magnetic Radius Search (retrieval)
  ↓ collects raw context windows
Observation Engine (Component 21)
  ↓ converts context windows → observations
Truth Resolver (Component 8)
  ↓ verifies observations → facts
Evidence Builder (Component 16)
  ↓ chains facts → evidence chains
Reasoning Graph (Neo4j)
  ↓ stores proven knowledge
```

The magnetic radius GATHERS the evidence.
The reasoning graph CONNECTS it.
You need both.

---

## Implementation Notes

### Database Mapping

- **Elasticsearch**: Word index → find all hits across all chats (fast)
- **MySQL**: Raw chat storage → fetch ±N lines around each hit (source records)
- **Qdrant**: Semantic expansion → find words with similar meaning (broader net)
- **Neo4j**: Store the resulting observations/facts/evidence as a graph

### Query Flow

```
User: "Why did we stop using RustDesk?"

1. Elasticsearch: Find "RustDesk" across 14,800 chats → 47 hits
2. MySQL: For each hit, fetch ±200 lines → 47 context windows
3. Qdrant: Expand search → "remote desktop", "disconnect", "relay" → 12 more hits
4. Rank all 59 hits by recency + relevance
5. Apply context budget (100K tokens → ~50 lines per hit)
6. Feed top 30 context windows to LLM
7. LLM extracts: observations, facts, decisions, evidence
8. Store extracted knowledge in Neo4j as reasoning graph
```

### Radius Parameter

The radius (N lines) is the key tuning parameter:

- **Small radius (10-20 lines)**: Gets the immediate sentence/context. Fast, cheap, but may miss the full story.
- **Medium radius (50-100 lines)**: Gets the conversation thread. Good balance.
- **Large radius (200+ lines)**: Gets the full discussion section. Expensive but comprehensive.

The radius should be DYNAMIC based on:
- Hit count (few hits → larger radius, many hits → smaller radius)
- Token budget (more budget → larger radius)
- Hit quality (exact match → larger radius, fuzzy match → smaller radius)

---

## Relationship to the 21-Component Spec

| Component | Role | Magnetic Radius? |
|-----------|------|-----------------|
| 1. Node Extraction | Extract nodes from chat | YES — radius provides the raw text |
| 3. Graph Activation | Find relevant subgraph | YES — magnetic radius IS activation |
| 15. Query Planner | Plan multi-hop queries | YES — planner decides radius size |
| 16. Evidence Builder | Build evidence chains | YES — radius windows ARE the evidence |
| 21. Observation Engine | Extract observations | YES — observations come from radius windows |

Magnetic Radius Search is the RETRIEVAL MECHANISM that makes the
21-component pipeline work. Without it, the graph has no way to
gather raw evidence from across thousands of chats.

---

## Summary

The user's intuition was correct:

- Words connect across chats (Level 1)
- But you don't just grab the word — you grab the CONTEXT around it
- The context windows from multiple chats form a "clump"
- The clump is fed to the LLM for reasoning
- The LLM compresses at reasoning time, not at storage time

This is "magnetic radius search" — a retrieval method where signals
attract context windows from across many conversations, creating
cross-chat evidence clumps that the LLM can reason over.

It sits between search (Elasticsearch) and reasoning (Neo4j):
- Search finds the signals
- Magnetic radius expands them into context windows
- Reasoning graph connects the extracted knowledge

---

# Formal Breakdown: Three Systems in One Idea

The "magnetic radius" concept actually combines three distinct retrieval systems
that most "graph vs search" explanations hide.

## A. Inverted Index (Word → Location)

```
word → chat_id
word → line number
```

Example:
- "SSH" → chat 14, 88, 900, 14,800

This is Elasticsearch-style indexing. Pure lookup. Fast but shallow.

## B. Window Expansion (±N Lines Context)

Once you find a hit, you also pull surrounding context:

```
hit at line 500
return lines 300–700
```

This is **context window retrieval** — used in log systems, code search,
and LLM RAG pipelines. This is the "200 lines above/below" part.

## C. Cluster / Semantic Grouping (Magnetic Clump)

Multiple hits across chats, all pulled together into a "region of meaning":

```
SSH appears in 200 chats
→ all those chats form an "SSH cluster"
```

This is a **retrieval cluster** (semantic or usage cluster).

## What the Magnetic Radius Actually Is

The magnetic radius is ALL THREE combined:

1. Inverted index finds the word hits
2. Window expansion grabs context around each hit
3. Cluster grouping merges overlapping contexts into a field

---

# Word Clustering vs Context Clustering

**Wrong idea**: clustering words ("SSH" as a word)

**Real system**: clustering contexts where words behave similarly

So you are NOT clustering "SSH" as a token.
You ARE clustering all situations where SSH appears in similar roles:
- fixing disconnects
- replacing RustDesk
- solving remote access issues

That becomes a **concept cluster** — not a word cluster.

---

# Formal Definition: Multi-Hop Weighted Retrieval

The "magnetic pull of related chats" is formally:

1. Find word match (SSH)
2. Expand to all occurrences across all chats
3. Score by relevance (frequency, recency, co-occurrence)
4. Pull surrounding context windows (±N lines)
5. Merge overlapping contexts
6. Form a retrieval cluster

That cluster becomes the context input for the LLM.

---

# Context Field Retrieval (The Real Concept)

What the user discovered is **Context Field Retrieval**:

```
each word creates a "gravity field"
      ↓
all occurrences pull in nearby context
      ↓
overlapping fields merge into clusters
      ↓
clusters become memory units
```

Where:
- **words** = anchors (signal points)
- **lines** = local context (±N around each anchor)
- **chats** = global context (which conversations contain the anchor)
- **cluster** = merged relevance field (the final context clump)

---

# Database Mapping for Magnetic Radius

The magnetic cluster is NOT one database. It is the result of combining all three:

| Database | Role in Magnetic Radius | What It Does |
|----------|------------------------|--------------|
| Elasticsearch | Signal detection | Find "SSH" everywhere across 14,800 chats |
| Qdrant | Semantic expansion | Find "things like SSH problems" (meaning search) |
| Neo4j | Relationship connection | SSH → fixes → RustDesk → failures → decisions |
| MySQL | Raw context fetch | Grab ±200 lines around each hit (source records) |

Full flow:
```
Elasticsearch → finds all "SSH" hits (47 matches)
Qdrant → expands to similar meanings (12 more hits: "secure shell", "remote access")
MySQL → fetches ±200 lines around each of 59 hits
Neo4j → connects extracted knowledge into reasoning graph
```

---

# The Key Question: Weighting

The most important next step:

**"How do I assign weights to each word occurrence so the 'magnetic pull'
correctly prioritizes important chats without pulling noise?"**

Not every "SSH" mention matters equally. A passing mention in chat 9,000
("yeah SSH exists") should not have the same magnetic pull as a detailed
debugging session in chat 5 ("SSH fixed the RustDesk disconnect").

### Weighting Factors

| Factor | Description | Effect |
|--------|-------------|--------|
| Frequency | How often the word appears in a single chat | More mentions = stronger pull |
| Recency | How recent the chat is | Recent chats = stronger pull |
| Co-occurrence | What other important words appear nearby | "SSH" + "RustDesk" + "fixed" = strong |
| Role signal | Is the word used as a solution, problem, or passing mention? | Solution/problem = strong, passing = weak |
| User confirmation | Did the user confirm or act on this? | "yes, use SSH" = strongest pull |
| Decision marker | Is there a decision associated? | "decided to use SSH" = strong |
| Outcome marker | Was there a result? | "SSH worked" = strong |

### Weighting Formula (Conceptual)

```
magnetic_weight(hit) =
    frequency_score × W1
  + recency_score × W2
  + co_occurrence_score × W3
  + role_score × W4
  + confirmation_score × W5
  + decision_score × W6
  + outcome_score × W7
```

Hits below a threshold are noise — excluded from the cluster.
Hits above the threshold form the magnetic clump.

### Noise Filtering

The weighting system is what separates signal from noise:
- 47 raw hits → 30 weighted hits above threshold → 17 noise hits filtered out
- The 30 surviving hits form the context cluster
- The 17 noise hits are indexed but not pulled into the magnetic radius

This is why weighting is the critical engineering boundary:
- Too loose = noise floods the LLM context
- Too tight = important evidence is missed
- Just right = the LLM gets exactly the context it needs

---

# Summary: The Full Picture

```
WORDS (anchors)
  ↓ inverted index (Elasticsearch)
HITS (locations across chats)
  ↓ window expansion (MySQL ±N lines)
CONTEXT WINDOWS (raw text fragments)
  ↓ semantic expansion (Qdrant)
EXPANDED HITS (similar meanings included)
  ↓ weighting + ranking
FILTERED CLUSTER (noise removed)
  ↓ merge overlapping contexts
MAGNETIC CLUMP (cross-chat evidence field)
  ↓ LLM reasoning
OBSERVATIONS + FACTS + DECISIONS
  ↓ store in Neo4j
REASONING GRAPH (connected knowledge)
```

The magnetic radius is the RETRIEVAL mechanism.
The reasoning graph is the STORAGE mechanism.
Weighting is the FILTER that makes it usable.
The LLM is the COMPRESSOR that turns raw context into knowledge.

---

# Embeddings vs Magnetic System: The Key Distinction

## What Embeddings Actually Are

An embedding is just: **a vector that represents the meaning of a piece of text.**

- "SSH fixed the issue" → becomes a point in high-dimensional space
- Similar meanings = close vectors

Embeddings answer ONE question: **"what is semantically similar?"**

## What the Magnetic System Is

The magnetic system is bigger: **a system that pulls context across many chats
using weighted attraction.**

It includes:
- Word matches (exact)
- Frequency across chats
- Line proximity (±N lines)
- Recency
- Co-occurrence
- Surrounding context windows
- Cluster merging across sessions
- Graph structure (causality, decisions)
- Repetition history

So it is a **full retrieval architecture**, not just similarity.

## The Key Difference

| Aspect | Embeddings Alone | Magnetic System |
|--------|-----------------|-----------------|
| What it does | text → vector → nearest neighbors | multi-force weighted retrieval |
| Output | Similar meaning chunks | Cross-chat evidence clusters |
| Chat structure | No explicit structure | Yes — chat boundaries, line-level grounding |
| Causal linking | No | Yes — graph edges |
| Importance | No | Yes — frequency, recency, role signals |
| Time awareness | No | Yes — recency boost, temporal validity |
| Repetition history | No | Yes — frequency memory |

**Embeddings are NOT the system. They are ONE measurement inside the scoring function.**

- Embeddings = semantic similarity axis
- Not memory itself
- Not graph
- Not retrieval logic

---

# The Three Forces (Correct Decomposition)

## A. Keyword Force (Exact Match Gravity)

- Word appears or not
- Frequency in chat
- Position (title > body)

This is a **precision signal** — exact word matches anchor the retrieval.

## B. Embedding Force (Meaning Gravity)

- Semantic similarity
- "SSH fixes login" ≈ "secure remote access solution"

This is a **conceptual similarity signal** — finds meaning even when
words don't match.

## C. Graph Force (Structural Gravity)

- How connected a node is
- How central it is in decision chains
- How often it leads to outcomes

This is a **reasoning/causality signal** — follows causal chains
through the graph.

---

# Unified Scoring Model

Each candidate node/chat segment gets a score:

```
SCORE =
    (keyword_strength     × Wk)   ← exact match gravity
  + (embedding_similarity × We)   ← meaning gravity
  + (graph_centrality     × Wg)   ← structural gravity
  + (recency_boost        × Wr)   ← time gravity
  + (frequency_boost      × Wf)   ← repetition gravity
  + (context_window_bonus × Wc)   ← proximity gravity
```

## What Each Weight Controls

### Wk (keyword weight)
- Controls: exact matches dominate or not
- Too high: system becomes brittle (misses paraphrases)
- Too low: system becomes fuzzy (can't find exact things)

### We (embedding weight)
- Controls: semantic intelligence
- Too high: system drifts into "vibes only" (loses precision)
- Too low: system misses meaning connections

### Wg (graph weight)
- Controls: causal reasoning
- This is what makes "why did this happen?" and "what caused this?" work
- Too high: system over-connects unrelated things through long paths
- Too low: system can't answer causal questions

### Wr (recency weight)
- Controls: recent chats matter more
- Prevents old noise from dominating
- Too high: system forgets old but important facts
- Too low: system drowns in ancient history

### Wf (frequency weight)
- Controls: repeated topics become "important memory"
- This is the "magnetic persistence" — things mentioned often stick
- Too high: common but unimportant topics dominate
- Too low: rare but critical events get lost

### Wc (context window bonus)
- Controls: pulling surrounding lines (the ±200 line idea)
- Too high: everything gets pulled in (noise flood)
- Too low: fragments without context (meaning loss)

---

# Force-Field Memory System (The Breakthrough)

## The Mental Model

The magnetic system is NOT search, NOT graph, NOT embeddings.

It is: **a force-field memory system over text history**

Where:
- Each chat is a **mass** (heavier = more content, more important)
- Each word is a **sensor** (detects signals in the query)
- Each embedding is a **direction vector** (points toward similar meaning)
- Each graph edge is a **constraint** (connects things causally)
- Retrieval is **physics-like interaction** (fields overlap, clusters form)

## How It Works

```
query enters the field
      ↓
each chat segment emits a "gravity field" based on signals
      ↓
fields overlap where multiple signals agree
      ↓
overlapping fields form clusters
      ↓
clusters become the retrieval result
```

This is EXACTLY the magnetic system: query → activates fields →
fields overlap → cluster forms.

## Why This Is Stronger Than Embeddings Alone

Embeddings fail at:
- Importance (all chunks are equal)
- Causality (no structural connections)
- Time (no temporal awareness)
- Structure (no chat boundaries)
- Repetition history (no frequency memory)

The magnetic system adds ALL of these as separate forces.

That is the difference between **similarity search** and **memory retrieval system**.

---

# The Final Pipeline (Clean)

```
1. Keyword match     → anchor (exact word hits)
2. Embedding match   → meaning pull (semantic similarity)
3. Graph traversal   → reasoning pull (causal chains)
4. Context expansion → window pull (±N lines around hits)
5. Weighting system  → control layer (score and rank)
6. Clustering        → final assembly (merge overlapping fields)
```

Each step adds a different force. The final cluster is the weighted
combination of all forces.

---

# Implementation Question: Data Structure

The key missing piece for implementation:

**"What exact data structure do I store per chat segment so I can compute
all these weights (keyword, embedding, graph, recency) efficiently at scale?"**

### What Each Chat Segment Needs

| Field | Source | Used For |
|-------|--------|----------|
| chat_id | MySQL | Identity, grouping |
| line_start, line_end | MySQL | Context window boundaries |
| timestamp | MySQL | Recency score (Wr) |
| word_frequency | Elasticsearch index | Keyword score (Wk) |
| embedding_vector | Qdrant | Embedding score (We) |
| graph_node_id | Neo4j | Graph centrality score (Wg) |
| mention_count | MySQL/ES | Frequency score (Wf) |
| co_occurrence_tags | Elasticsearch | Context window bonus (Wc) |
| role_label | Observation Engine | Role signal (solution/problem/passing) |
| decision_linked | Neo4j | Decision marker weight |
| outcome_linked | Neo4j | Outcome marker weight |
| user_confirmed | MySQL | Confirmation weight |

### Storage Division

```
MySQL:     chat_id, line_range, timestamp, role_label, user_confirmed, mention_count
Elasticsearch: word_frequency, co_occurrence_tags, inverted index
Qdrant:    embedding_vector (one per segment)
Neo4j:     graph_node_id, edges to decisions/outcomes/evidence
```

The chat segment ID is the join key across all four databases —
same principle as the 3-DB architecture: data lives in ONE place,
ID is the bridge.

---

# MySQL References: "Magnetic" in the Database

Searched all MySQL databases (vb_shared, vb_code_test, CODEBASE) for the word "magnetic".

## vb_shared.learned_rules (3 hits)

| id | pattern | fix_action |
|----|---------|------------|
| 14717 | skip magnetic methods | Follow rule: prohibition |
| 15432 | the vs code gui is not using the magnetic registry system | Follow rule: bug |
| 19260 | do okay that magnetic search can you go test it out and see if it's working | Follow rule: prohibition |

## CODEBASE.python_files (20 hits)

All files contain the word "magnetic" in their content:

| id | filename | full_path |
|----|----------|-----------|
| 160 | unified_project_db_windsurf_conversation_messages_85ded07e.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/COMPLETE_RESTORATION/EXISTING/PYTHON/ |
| 184 | windsurf_data_1_conversation_messages_4c8b28ac.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/COMPLETE_RESTORATION/EXISTING/PYTHON/ |
| 187 | unified_project_db_windsurf_conversation_messages_9a00196d.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/COMPLETE_RESTORATION/EXISTING/PYTHON/ |
| 202 | windsurf_data_1_conversation_messages_5c896343.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/COMPLETE_RESTORATION/EXISTING/PYTHON/ |
| 208 | windsurf_data_1_conversation_messages_2459c0ca.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/COMPLETE_RESTORATION/EXISTING/PYTHON/ |
| 209 | windsurf_data_1_conversation_messages_d605c608.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/COMPLETE_RESTORATION/EXISTING/PYTHON/ |
| 214 | unified_project_db_windsurf_conversation_messages_afaf4882.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/COMPLETE_RESTORATION/EXISTING/PYTHON/ |
| 228 | unified_project_db_windsurf_conversation_messages_a12d1e2d.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/COMPLETE_RESTORATION/EXISTING/PYTHON/ |
| 250 | windsurf_data_1_conversation_messages_57264271.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/COMPLETE_RESTORATION/EXISTING/PYTHON/ |
| 251 | unified_project_db_windsurf_conversation_messages_f4adb1cf.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/COMPLETE_RESTORATION/EXISTING/PYTHON/ |
| 364 | windsurf_data_1_conversation_messages_b9d107bb.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/COMPLETE_RESTORATION/EXISTING/PYTHON/ |
| 370 | unified_project_db_windsurf_conversation_messages_d0e4fa62.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/COMPLETE_RESTORATION/EXISTING/PYTHON/ |
| 378 | windsurf_data_1_conversation_messages_a15d3b86.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/COMPLETE_RESTORATION/EXISTING/PYTHON/ |
| 384 | windsurf_data_1_conversation_messages_f4b20860.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/COMPLETE_RESTORATION/EXISTING/PYTHON/ |
| 387 | windsurf_data_1_conversation_messages_48a9fe53.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/COMPLETE_RESTORATION/EXISTING/PYTHON/ |
| 390 | unified_project_db_windsurf_conversation_messages_e91bbe7b.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/COMPLETE_RESTORATION/EXISTING/PYTHON/ |
| 399 | windsurf_data_1_conversation_messages_44143b38.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/COMPLETE_RESTORATION/EXISTING/PYTHON/ |
| 409 | windsurf_data_1_conversation_messages_ddbc935c.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/COMPLETE_RESTORATION/EXISTING/PYTHON/ |
| 671 | Lib_python_chat357_138887b1_VB_v1.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/Libs/Py/Validation/ |
| 715 | Lib_python_chat272_cce0ab09_VB_v1.py | /Users/Shared/VB_ai_Dec/Project_PropPanel/Libs/Py/Validation/ |

## Tables Searched With No Hits

| Database | Table | Result |
|----------|-------|--------|
| vb_shared | tokens | No hits |
| vb_shared | rules | No hits |
| vb_shared | know_problems | No hits |
| vb_shared | know_solutions | No hits |
| vb_shared | know_lessons | No hits |
| vb_shared | instructions | No hits |
| vb_shared | inference_rules | No hits |
| vb_shared | design_patterns | No hits |
| vb_code_test | vb_classes | No hits |
| vb_code_test | vb_methods | No hits |
| CODEBASE | computational_units | No hits |

## Notes

- The 20 Python files in CODEBASE are conversation message exports and validation library files from the VB_ai_Dec project
- The 3 learned_rules entries show "magnetic" was discussed in the context of: skipping magnetic methods, VS Code GUI magnetic registry, and magnetic search testing
- Rule id=15432 is notable: "the vs code gui is not using the magnetic registry system" — suggests a magnetic registry concept was discussed but not implemented in VS Code GUI
- Rule id=19260: "magnetic search can you go test it out" — directly references magnetic search as a concept being tested
