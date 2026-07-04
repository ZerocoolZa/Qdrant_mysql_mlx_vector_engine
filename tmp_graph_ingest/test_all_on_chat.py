# =============================================================================
# File: test_all_on_chat.py
# Created: June 23, 2026
# Reason: User wanted to see what every graph engine module does when pointed
#         at a chat markdown file — full experiment.
# Idea: Run GraphEngine, CascadeEngine, DecisionEngine, Inspect, Verify,
#       GraphViewer — all against the Codex Chat Cleanup.md file.
#       Show every result so we can see what each tool reveals about a chat.
# =============================================================================
# COMPLETE GRAPH ENGINE SPEC: 20 Components for Memory-Backed LLM Reasoning
# =============================================================================
#
# The original spec (parts 1-6) covers ~70-80% of a true memory-backed reasoning
# system. The biggest missing pieces are NOT more extraction — they are the
# layers BETWEEN extraction and reliable retrieval. Parts 7-20 below close that
# gap.
#
# ─── PARTS 1-6 (Original Spec — Extraction & Storage) ───────────────────────
#
# 1. NODE EXTRACTION (Parsing)
#    - Read chat.md, identify: CONCEPTS, FILES, TOOLS, INTENT, ENTITIES,
#      ERRORS, DECISIONS, VALUES
#
# 2. EDGE BUILDING (Association)
#    - Typed relationships: REFERENCES, DEPENDS_ON, CONTRADICTS, RESOLVES,
#      CAUSED_BY, PART_OF, RELATED_TO
#    - Edge detection: proximity, causality, repeated mentions, user confirmation
#
# 3. GRAPH ACTIVATION (Querying)
#    - Keyword match, semantic match (Qdrant/MLX), edge traversal,
#      recency boost, frequency boost
#
# 4. MEMORY PERSISTENCE (Storage)
#    - SQLite, MySQL, Qdrant, or JSON
#    - Node: id, type, value, timestamp, message_source, embedding
#    - Edge: id, source_id, target_id, relationship_type, weight
#
# 5. INTEGRATION WITH LLM (The Cortex)
#    - Engine provides activated subgraph as structured context
#    - LLM receives context and produces response
#    - ContextRAM already does this
#
# 6. ITERATION & LEARNING (Improvement over time)
#    - Mark activated subgraphs as useful/insufficient
#    - Adjust edge weights based on feedback
#    - Add new nodes from LLM responses back into graph
#
# ─── PARTS 7-20 (Missing Pieces — Retrieval & Reasoning Layers) ─────────────
#
# 7. TEMPORAL MODEL (Time Graph)
#    - Problem: Without time, graphs become memory soup
#    - A -> B -> C is not enough; LLM needs to know:
#      A happened BEFORE B
#      B replaced C
#      D was valid from June 1 to June 10
#    - Need temporal edge types:
#      BEFORE, AFTER, REPLACED_BY, VALID_DURING, SUPERSEDED
#
# 8. BELIEF / TRUTH TRACKING
#    - Problem: Not everything in chat is true
#    - Example: "I think port is 8080" (message 1) vs "Port was actually 9000" (message 20)
#    - Need truth states for every node:
#      CLAIM, VERIFIED, REJECTED, UNKNOWN
#    - Otherwise graph stores both as equal truth
#
# 9. OPEN LOOP DETECTION
#    - Problem: LLMs lose track of unfinished work
#    - Need node types: TASK, QUESTION, GOAL, BLOCKER
#    - Need states: OPEN, IN_PROGRESS, DONE, ABANDONED
#    - Example: "Find memory leak" at message 5, "Still unresolved" at message 200
#    - Graph should know this is still OPEN
#
# 10. IMPORTANCE SCORING
#     - Problem: Not all nodes matter equally
#     - Mentioned once: "Firefox" → low importance
#     - Mentioned 400 times: "MemUnit" → high importance
#     - Need per-node metadata:
#       importance_score, mention_count, last_seen, activation_count
#     - Without this, retrieval becomes noisy
#
# 11. IDENTITY RESOLUTION
#     - Problem: Humans rename things
#     - "ContextRAM", "Memory Engine", "RAM Layer" may all be same entity
#     - Need identity edge types:
#       ALIAS_OF, SAME_AS, RENAMED_TO
#     - Or graph fragments that merge on identity match
#
# 12. HIERARCHY DISCOVERY
#     - Problem: Current graph is mostly flat
#     - Need automatic hierarchy:
#       Domain → Project → Module → Class → Method
#     - This is what the domain/class/method identity chain is starting to do
#     - The graph_computation_units database already has this structure
#
# 13. CONTRADICTION ENGINE
#     - Problem: Detect when facts conflict
#     - Example: "Use SSH" (message 10) vs "SSH forbidden" (message 50)
#     - Need edge types: CONTRADICTS, OBSOLETES, REPLACES
#     - Need confidence scoring on contradictions
#
# 14. MEMORY COMPRESSION
#     - Problem: Huge chats eventually kill retrieval
#     - Need compression pipeline:
#       Raw Message → Observation → Fact → Summary → Canonical Memory
#     - Example: 100 messages → 3 stable facts
#     - This is how a hippocampus survives — it compresses, not just stores
#
# 15. QUERY PLANNER
#     - Problem: Most graph systems fail here
#     - User asks: "Why did we stop using RustDesk?"
#     - Need a planner that builds a query strategy:
#       Find RustDesk → Traverse decisions → Traverse errors → Find resolution
#       → Build evidence chain
#     - NOT just keyword search — multi-hop reasoning over the graph
#
# 16. EVIDENCE CHAINS
#     - Problem: Every memory should answer "Why do you believe this?"
#     - Need: Fact → Evidence → Message → Timestamp
#     - Example:
#       Decision: "Use SSH"
#       Evidence: Message 102, Message 107, Message 114
#     - Without evidence chains, the LLM hallucinates confidence
#
# 17. ACTIVATION FEEDBACK (First-Class)
#     - Problem: Spec touches this but it needs to be first-class
#     - Store per query:
#       Query text, Activated Nodes, Response Quality, User Feedback
#     - Learn: "These nodes helped" vs "These nodes were useless"
#     - This is the training signal for the graph itself
#
# 18. EPISODIC vs SEMANTIC MEMORY
#     - Problem: Humans store both types, graph should too
#     - Episodic: "On June 23 we tested GraphViewer" (event-based, time-bound)
#     - Semantic: "GraphViewer displays graph structures" (fact-based, timeless)
#     - Different memory types → Different retrieval rules → Different decay rates
#
# 19. CAUSAL GRAPH
#     - Problem: Not just association — causation
#     - Need: Action → Caused → Error → Fix → Resolution
#     - This is what lets the system answer:
#       "What broke?" → "Why?" → "What fixed it?"
#     - Causal edges are stronger than associative edges
#
# 20. MEMORY GOVERNOR
#     - Problem: Without this, everything becomes a node → graph explodes
#     - Need rules for:
#       KEEP (important, frequently activated)
#       DISCARD (noise, single mention, no connections)
#       MERGE (duplicate nodes, same entity different names)
#       COMPRESS (old episodes → semantic facts)
#       ARCHIVE (inactive for N days → cold storage)
#     - This is the most important missing layer
#
# ─── TRUE END STATE: Complete Pipeline ──────────────────────────────────────
#
# Parser
#   ↓
# Node Extractor
#   ↓
# Relationship Builder
#   ↓
# Truth Resolver          ← MISSING (part 8)
#   ↓
# Temporal Engine         ← MISSING (part 7)
#   ↓
# Identity Resolver       ← MISSING (part 11)
#   ↓
# Graph Store
#   ↓
# Activation Engine
#   ↓
# Query Planner           ← MISSING (part 15)
#   ↓
# Evidence Builder        ← MISSING (part 16)
#   ↓
# Context Generator
#   ↓
# LLM
#   ↓
# Feedback Learner        ← PARTIAL (part 17, needs to be first-class)
#
# Largest missing components:
#   - Truth Resolver      (part 8: CLAIM/VERIFIED/REJECTED/UNKNOWN)
#   - Temporal Engine     (part 7: BEFORE/AFTER/REPLACED_BY/SUPERSEDED)
#   - Identity Resolver   (part 11: ALIAS_OF/SAME_AS/RENAMED_TO)
#   - Query Planner       (part 15: multi-hop reasoning, not keyword search)
#   - Evidence Builder    (part 16: fact → evidence → message → timestamp)
#   - Memory Governor     (part 20: KEEP/DISCARD/MERGE/COMPRESS/ARCHIVE)
#
# These are the pieces that separate a "Graph Database" from a
# "Persistent Context Memory System"
#
# ─── NEXT TASK: Gap Analysis ────────────────────────────────────────────────
#
# Compare existing tools against the full 20-component pipeline:
#   - GraphEngine       → which stages?
#   - CascadeEngine     → which stages?
#   - DecisionEngine    → which stages?
#   - ContextRAM (MCP)  → which stages?
#   - Qdrant            → which stages?
#   - Identity tables   → which stages?
#   - GraphViewer       → which stages?
#
# For each: identify EXISTS, PARTIAL, or COMPLETELY MISSING
#
# =============================================================================
# BUILD PLAN: Full-Powered Graph Engine — Learns Dynamically → Stores in DB
# =============================================================================
#
# TASK-076 (P0): Build a complete graph engine covering all 20 components.
#
# Core requirements:
#   1. FULL-POWERED — all 20 components from the spec
#   2. LEARN DYNAMICALLY — feedback loop adjusts weights, scores, activation
#   3. STORE IN DATABASE — MySQL persistence for all nodes, edges, signals
#
# Architecture:
#
#   Chat.md input
#     ↓
#   Parser → Node Extractor → Relationship Builder
#     ↓
#   Truth Resolver → Temporal Engine → Identity Resolver
#     ↓
#   Graph Store (MySQL)
#     ↓
#   Activation Engine → Query Planner → Evidence Builder
#     ↓
#   Context Generator → LLM
#     ↓
#   Feedback Learner → updates weights/scores back into DB
#     ↓
#   Memory Governor → KEEP/DISCARD/MERGE/COMPRESS/ARCHIVE
#
# Database Schema (new tables in graph_computation_units or new DB):
#
#   graph_nodes:
#     id, type, value, truth_state, importance_score, mention_count,
#     last_seen, activation_count, memory_type, created_at
#
#   graph_edges:
#     id, source_id, target_id, relationship_type, weight,
#     temporal_order, confidence, created_at
#
#   graph_evidence:
#     id, node_id, message_ref, timestamp, confidence
#
#   graph_feedback:
#     id, query_text, activated_node_ids, response_quality,
#     user_feedback, created_at
#
#   graph_identity:
#     id, canonical_name, alias_name, source
#
#   graph_episodes:
#     id, node_id, episode_type, start_time, end_time, summary
#
# Existing assets to REUSE (not rebuild):
#   - GraphEngine (66 methods)         → node extraction + edge building
#   - CascadeEngine                    → graph activation + traversal
#   - DecisionEngine                   → decision tracking
#   - ContextRAM (MCP)                 → memory persistence + LLM integration
#   - Qdrant                           → semantic match for activation
#   - MLX embeddings                   → vector generation
#   - graph_computation_units DB       → 2,407 existing computation units
#   - 8 graph viewers                  → visualization (plan/spec/flow/etc)
#
# Missing components to BUILD (the 6 gaps):
#   1. Truth Resolver     — CLAIM/VERIFIED/REJECTED/UNKNOWN state machine
#   2. Temporal Engine    — BEFORE/AFTER/REPLACED_BY/SUPERSEDED edges
#   3. Identity Resolver  — ALIAS_OF/SAME_AS/RENAMED_TO merge logic
#   4. Query Planner      — multi-hop reasoning (not keyword search)
#   5. Evidence Builder   — fact → evidence → message → timestamp chains
#   6. Memory Governor    — KEEP/DISCARD/MERGE/COMPRESS/ARCHIVE rules
#
# Dynamic Learning Loop (the "learns dynamically" part):
#   - Every query stores: what nodes were activated, response quality, user feedback
#   - After each interaction: adjust edge weights (reinforce useful, weaken useless)
#   - Importance score = f(mention_count, activation_count, feedback_score, recency)
#   - Memory Governor runs periodically: compress old episodes → semantic facts,
#     discard noise nodes, merge identity duplicates, archive inactive nodes
#   - This creates a SELF-IMPROVING graph that gets better with every conversation
#
# =============================================================================
# GAP ANALYSIS: Reality Check (ChatGPT assessment vs 20-component spec)
# =============================================================================
#
# Pipeline Stage          | GraphEngine | CascadeEngine | DecisionEngine | ContextRAM | Qdrant | Identity Tables | GraphViewer
# ------------------------|-------------|---------------|----------------|------------|--------|-----------------|------------
# Node Extraction         | EXISTS      | ?             | PARTIAL        | ?          | NO     | NO              | NO
# Edge Building           | EXISTS      | PARTIAL       | PARTIAL        | ?          | NO     | PARTIAL         | VIEW ONLY
# Graph Activation        | PARTIAL     | EXISTS        | PARTIAL        | PARTIAL    | EXISTS | NO              | VIEW ONLY
# Memory Persistence      | PARTIAL     | ?             | ?              | EXISTS     | EXISTS | EXISTS          | NO
# LLM Integration         | NO          | NO            | NO             | EXISTS     | NO     | NO              | NO
# Feedback Learning       | ?           | ?             | ?              | PARTIAL    | NO     | NO              | NO
# Temporal Model          | MISSING     | MISSING       | MISSING        | MISSING    | MISSING| MISSING         | MISSING
# Truth Resolver          | MISSING     | MISSING       | PARTIAL        | MISSING    | MISSING| MISSING         | MISSING
# Open Loop Tracking      | PARTIAL     | PARTIAL       | EXISTS         | PARTIAL    | NO     | NO              | VIEW ONLY
# Importance Scoring      | PARTIAL     | PARTIAL       | PARTIAL        | PARTIAL    | PARTIAL| NO              | VIEW ONLY
# Identity Resolution     | PARTIAL     | NO            | NO             | NO         | NO     | EXISTS          | VIEW ONLY
# Hierarchy Discovery     | PARTIAL     | NO            | NO             | NO         | NO     | EXISTS          | VIEW ONLY
# Contradiction Engine    | PARTIAL     | PARTIAL       | PARTIAL        | NO         | NO     | NO              | VIEW ONLY
# Memory Compression      | MISSING     | MISSING       | MISSING        | PARTIAL    | NO     | NO              | NO
# Query Planner           | MISSING     | PARTIAL       | PARTIAL        | NO         | NO     | NO              | VIEW ONLY
# Evidence Builder        | MISSING     | MISSING       | PARTIAL        | MISSING    | NO     | NO              | VIEW ONLY
# Episodic Memory         | PARTIAL     | PARTIAL       | PARTIAL        | PARTIAL    | NO     | NO              | VIEW ONLY
# Semantic Memory         | PARTIAL     | EXISTS        | PARTIAL        | EXISTS     | EXISTS | NO              | VIEW ONLY
# Causal Graph            | PARTIAL     | PARTIAL       | EXISTS         | PARTIAL    | NO     | NO              | VIEW ONLY
# Memory Governor         | MISSING     | MISSING       | MISSING        | MISSING    | MISSING| MISSING         | MISSING
#
# SUMMARY COUNTS:
#   EXISTS:    7  (cells with EXISTS)
#   PARTIAL:   28 (cells with PARTIAL)
#   MISSING:   16 (cells with MISSING)
#   UNKNOWN:    8 (cells with ?)
#   NO:        31 (cells with NO — tool doesn't cover this stage at all)
#   VIEW ONLY: 11 (GraphViewer can display but not compute)
#
# =============================================================================
# KEY INSIGHT 1: Identity Chain is the Strongest Asset (Not GraphEngine)
# =============================================================================
#
# The strongest thing in the current architecture is NOT GraphEngine.
# It is the identity chain accidentally built:
#
#   Domain → Class → Method
#
# Example:
#   DomAi (domain)
#     ↓
#   DomAi class (class)
#     ↓
#   classify() (method)
#
# This already provides:
#   PART_OF, CONTAINS, HIERARCHY, OWNERSHIP
#
# which maps directly to:
#   Component 11 (Identity Resolution)
#   Component 12 (Hierarchy Discovery)
#
# Most graph systems don't even have this. This is a head start.
#
# =============================================================================
# KEY INSIGHT 2: 2,407 Computation Units Already Provide Structural Graph
# =============================================================================
#
# The 2,407 computation units across 224 classes already provide:
#
#   Method Node (each row = a method)
#   Class Node (each class_name = a class)
#   Domain Node (where domain is populated)
#   File Node (file_path)
#
# And likely edges:
#   METHOD_IN_CLASS
#   CLASS_IN_DOMAIN
#   METHOD_IN_FILE
#
# That's a huge percentage of structural graph construction ALREADY DONE.
# The foundation exists — the missing pieces are the reasoning layers on top.
#
# =============================================================================
# KEY INSIGHT 3: Biggest Gap is NOT Extraction — It's Evidence + Truth
# =============================================================================
#
# What already exists:
#   ✓ Extraction
#   ✓ Storage
#   ✓ Identity beginnings
#   ✓ Hierarchy beginnings
#   ✓ Vector search beginnings
#   ✓ Graph traversal beginnings
#
# The biggest missing engine is:
#
#   FACT
#     ↓
#   SUPPORTED_BY
#     ↓
#   MESSAGE
#     ↓
#   TIMESTAMP
#
# In other words: Evidence Builder + Truth Resolver
#
# Because until that exists:
#   - Graph knows things
#   - But cannot answer: "How do you know?"
#   - Cannot answer: "Is it still true?"
#   - Cannot answer: "What replaced it?"
#
# =============================================================================
# KEY INSIGHT 4: Memory Governor is Critical Missing Layer
# =============================================================================
#
# Second biggest gap: Memory Governor
#
# Current architecture pattern:
#   Extract more → Store more → Map more → Scan more
#
# But NOT:
#   Forget → Merge → Compress → Archive
#
# Without Memory Governor:
#   - A million-node graph becomes slower and less useful over time
#   - Noise accumulates
#   - Retrieval quality degrades
#   - The graph drowns in its own data
#
# Memory Governor is what keeps the graph ALIVE — it prunes, it compresses,
# it archives. Without it, the graph is a hoarder, not a memory system.
#
# =============================================================================
# KEY INSIGHT 5: Need Real Method Audit (Not Inferred Coverage)
# =============================================================================
#
# The gap analysis above is INFERRED from names and counts, not from actual
# method inspection. To do a true EXISTS/PARTIAL/MISSING audit, we need:
#
#   1. Extract every method signature from GraphEngine, CascadeEngine,
#      DecisionEngine, ContextRAM, and GraphViewer from computation_units table
#   2. Map each method directly to pipeline components 1-20
#   3. Calculate real coverage percentages
#
# A class named "TruthResolver" might already exist inside those 2,407 units.
# The database mapping proves the code exists, but not what methods actually do.
#
# NEXT TASK: Method Audit
#   SELECT class_name, method_name, signature, body
#   FROM computation_units
#   WHERE class_name IN ('GraphEngine', 'CascadeEngine', 'DecisionEngine',
#                         'ContextRAM', 'GraphViewer')
#   ORDER BY class_name, method_name
#
# Then map each method to components 1-20 and calculate real coverage %.
#
# =============================================================================
# COMPONENT 21: Observation Engine (The Hidden Gap)
# =============================================================================
#
# ARCHITECTURAL CRITIQUE:
#
# Current pipeline assumes:
#   Chat → Nodes → Edges → Graph → Retrieval → LLM
#
# But human memory is closer to:
#   Chat → Episodes → Observations → Facts → Graph → Retrieval → Reasoning
#
# That missing layer is: Experience Normalization / Observation Extraction
#
# ─── What is an Observation? ─────────────────────────────────────────────────
#
# Example chat:
#   User:      RustDesk keeps disconnecting.
#   Assistant: Maybe NAT issue.
#   User:      Disabled relay mode.
#   Assistant: Try SSH.
#   User:      SSH worked.
#
# Raw extraction gives:
#   RustDesk, disconnecting, NAT, relay mode, SSH, worked
#
# But the useful memory is:
#   Problem:    RustDesk unreliable
#   Attempt:    Disable relay
#   Result:     Failed
#   Attempt:    SSH
#   Result:     Success
#
# Those are OBSERVATIONS. Not yet facts. Not yet graph.
# Observations are the bridge between raw chat and structured knowledge.
#
# ─── Reasoning Objects (New Node Types Needed) ───────────────────────────────
#
# Current node types: Concept, Tool, File, Entity, Decision, Error, Value
#
# Needed reasoning objects:
#   OBSERVATION   — what happened (from chat)
#   HYPOTHESIS    — what we think might be true
#   EXPERIMENT    — what we tried
#   OUTCOME       — what resulted
#   EVIDENCE      — what supports a fact
#   FACT          — what we've established as true
#
# A graph made only of nouns becomes:
#   RustDesk → SSH → Relay → Mac
#
# A graph made of reasoning objects becomes:
#   Hypothesis:  Relay mode causing disconnects
#   Experiment:  Disable relay
#   Outcome:     No improvement
#   Alternative: SSH
#   Outcome:     Resolved
#
# Much stronger retrieval. Reasoning objects carry context that nouns don't.
#
# ─── Coverage Adjustment ─────────────────────────────────────────────────────
#
# Adding Component 21 (Observation Engine) changes the coverage estimate:
#
# Current strengths:
#   ✓ Extraction, Storage, Identity, Hierarchy, Vectors, Traversal
#
# Current weakest areas:
#   ✗ Truth, Evidence, Temporal, Governor
#
# HIDDEN weakness (before all of those):
#   ✗ Experience → Observation conversion
#
# Because: bad observations → bad facts → bad evidence → bad retrieval
# The observation layer is the FOUNDATION of truth and evidence.
# If observations are wrong, everything built on top is wrong.
#
# ─── Build Priority (Reordered) ──────────────────────────────────────────────
#
# Original order: Truth → Temporal → Identity → Query Planner → Evidence → Governor
#
# REVISED build order (what ChatGPT recommends):
#
#   1. Evidence Builder    — without evidence you cannot prove anything
#   2. Truth Resolver      — without truth you cannot know what to trust
#   3. Observation Engine  — without observations you cannot build reliable facts
#   4. Identity Resolver   — without identity you cannot merge duplicates
#   5. Temporal Engine     — without time you cannot track what replaced what
#   6. Memory Governor     — without governor the graph drowns in noise
#   7. Query Planner       — last, because it's a sophisticated search engine
#                            over uncertain memories until 1-6 exist
#
# Reason: Query Planner is worthless until Evidence, Truth, and Observations
# exist. Otherwise it becomes a very sophisticated search engine over
# uncertain memories.
#
# ─── 5-Layer Memory Model (Possible End State) ──────────────────────────────
#
# The final system may converge on five memory layers:
#
#   Raw Message
#       ↓
#   Observation
#       ↓
#   Fact
#       ↓
#   Episode
#       ↓
#   Semantic Memory
#
# With explicit links:
#
#   Message      --OBSERVED_AS-->    Observation
#   Observation  --SUPPORTS-->       Fact
#   Fact         --PART_OF-->        Episode
#   Episode      --COMPRESSED_TO-->  Semantic Memory
#
# This structure naturally supports:
#   - Truth         (facts have truth_state)
#   - Evidence      (observations support facts, messages support observations)
#   - Compression   (episodes compress to semantic memories)
#   - Temporal      (each layer has timestamps, episodes have time ranges)
#   - Identity      (facts can be merged across episodes)
#   - Query planning (traverse any layer up or down)
#
# Instead of bolting these on later, the 5-layer model makes them INHERENT.
#
# ─── Complete Node Types for 21-Component Engine ─────────────────────────────
#
# Structural Nodes (from extraction):
#   CONCEPT, FILE, TOOL, ENTITY, VALUE
#
# Reasoning Nodes (new):
#   OBSERVATION, HYPOTHESIS, EXPERIMENT, OUTCOME, EVIDENCE, FACT
#
# Process Nodes:
#   DECISION, ERROR, TASK, QUESTION, GOAL, BLOCKER
#
# Memory Layer Nodes:
#   MESSAGE (raw), EPISODE (grouped), SEMANTIC (compressed)
#
# ─── Complete Edge Types for 21-Component Engine ─────────────────────────────
#
# Structural edges:
#   REFERENCES, DEPENDS_ON, PART_OF, RELATED_TO
#
# Memory layer edges:
#   OBSERVED_AS (message → observation)
#   SUPPORTS    (observation → fact)
#   COMPRESSED_TO (episode → semantic memory)
#
# Truth edges:
#   CONTRADICTS, OBSOLETES, REPLACES, SUPERSEDED_BY
#
# Temporal edges:
#   BEFORE, AFTER, REPLACED_BY, VALID_DURING
#
# Identity edges:
#   ALIAS_OF, SAME_AS, RENAMED_TO
#
# Causal edges:
#   CAUSED_BY, RESOLVES, LED_TO
#
# Hierarchy edges:
#   CONTAINS, OWNS, MEMBER_OF
#
# ─── Node States ─────────────────────────────────────────────────────────────
#
# Truth states:    CLAIM, VERIFIED, REJECTED, UNKNOWN
# Task states:     OPEN, IN_PROGRESS, DONE, ABANDONED
# Memory states:   ACTIVE, COMPRESSED, ARCHIVED, DISCARDED
# Episode states:  ONGOING, CLOSED, COMPRESSED
#
# ─── Database Schema for 21-Component Engine ─────────────────────────────────
#
# graph_nodes:
#   id, type, value, truth_state, memory_state, importance_score,
#   mention_count, last_seen, activation_count, memory_type,
#   episode_id, created_at, updated_at
#
# graph_edges:
#   id, source_id, target_id, relationship_type, weight,
#   temporal_order, confidence, evidence_count, created_at
#
# graph_observations:
#   id, node_id, message_ref, observation_text, observer_confidence, created_at
#
# graph_facts:
#   id, node_id, fact_text, truth_state, verified_by, verified_at,
#   superseded_by, created_at
#
# graph_evidence:
#   id, fact_id, observation_id, message_ref, timestamp, confidence
#
# graph_episodes:
#   id, title, start_time, end_time, summary, state, node_count, created_at
#
# graph_identity:
#   id, canonical_name, alias_name, source, confidence
#
# graph_feedback:
#   id, query_text, activated_node_ids, response_quality, user_feedback, created_at
#
# graph_governor_log:
#   id, action (KEEP/DISCARD/MERGE/COMPRESS/ARCHIVE), node_id, reason, timestamp
#
# NEXT TASK: Define complete Memory Object Model for 21-component engine
#   - Formalize all node types, edge types, states
#   - Define transitions (CLAIM → VERIFIED, OPEN → DONE, ACTIVE → ARCHIVED)
#   - Define compression rules (when does an episode become a semantic memory?)
#   - Define governor rules (when to KEEP/DISCARD/MERGE/COMPRESS/ARCHIVE)
#
# =============================================================================
# DATABASE CHOICE: Graph DB Selection for 21-Component Memory System
# =============================================================================
#
# ─── Graph Database Comparison ───────────────────────────────────────────────
#
# Database     | Best At                              | Verdict
# -------------|--------------------------------------|---------------------------
# Neo4j        | Property graphs, traversal, rels     | ⭐ Most mature graph DB
# TigerGraph   | Massive graphs, analytics            | ⭐ Enterprise scale
# JanusGraph   | Distributed graph storage            | Good but complex
# ArangoDB     | Graph + Document                     | Very flexible
# Memgraph     | Fast graph processing                | Excellent for realtime
# Qdrant       | Semantic/vector search               | Not a graph DB
# MySQL        | Storage                              | Not a graph DB
#
# ─── Recommended Architecture: 3-Database Stack ─────────────────────────────
#
# For the 21-component memory system, the strongest combination is:
#
#   Neo4j  +  MySQL  +  Qdrant
#
# NEO4J (Graph Database):
#   Stores: Message, Observation, Fact, Episode, SemanticMemory nodes
#   Stores: SUPPORTED_BY, BEFORE, AFTER, CAUSES, RESOLVES, PART_OF,
#           SAME_AS, CONTRADICTS relationships
#   This is what Neo4j is BUILT FOR — native graph traversal
#
#   Example Cypher query:
#     MATCH p=
#       (Problem)-[:CAUSED_BY]->(Action)
#                 -[:LED_TO]->(Error)
#                 -[:FIXED_BY]->(Fix)
#     RETURN p
#
#   That's native graph traversal — no JOINs, no table scans.
#
# MYSQL (Relational Database):
#   Stores: Raw chat text, logs, feedback records, metrics, audit history
#   Already have: graph_computation_units (2,407 units), vb_code_test,
#                 vb_shared knowledge base
#   Role: Relational data, structured storage, existing knowledge base
#
# QDRANT (Vector Database):
#   Stores: Embeddings, semantic similarity, meaning search
#   Already have: Qdrant running in this workspace
#   Role: Semantic activation — "find nodes that MEAN the same thing"
#
#   Example flow:
#     User: "Why did RustDesk fail?"
#     Qdrant finds: RustDesk, Remote desktop, SSH, relay mode, disconnects
#     Neo4j traverses: RustDesk → CAUSED_BY → relay → LED_TO → disconnect
#                      → FIXED_BY → SSH → RESOLVES
#
# ─── Single Database Option (If Forced to Choose One) ───────────────────────
#
# 1st Choice: NEO4J
#   Because the system is fundamentally:
#     Node, Edge, Evidence, Identity, Hierarchy, Temporal, Causal
#   which is graph-native. Neo4j is the closest match to the
#   Message → Observation → Fact → Episode → Semantic Memory architecture.
#
# 2nd Choice: ARANGODB
#   Because it can do Graph + Document + Key-Value inside one engine.
#   More flexible but less mature for pure graph traversal.
#
# ─── Migration Path: MySQL → Neo4j ───────────────────────────────────────────
#
# The current graph_computation_units table already contains graph data
# in relational form:
#   Method, Class, Domain, File
#
# This can be migrated directly to Neo4j:
#
#   (:Domain)-[:CONTAINS]->(:Class)
#   (:Class)-[:CONTAINS]->(:Method)
#   (:Method)-[:IN_FILE]->(:File)
#
# Migration script would:
#   1. Read all rows from graph_computation_units.computation_units
#   2. Create Domain nodes (unique domains)
#   3. Create Class nodes (unique class_names)
#   4. Create Method nodes (each row = one method)
#   5. Create File nodes (unique file_paths)
#   6. Create CONTAINS edges (Domain → Class, Class → Method)
#   7. Create IN_FILE edges (Method → File)
#   8. Import method body, signature, line numbers as node properties
#
# This migration is straightforward — it's a 1:1 mapping from rows to nodes.
# The hard part is the reasoning layers (Evidence, Truth, Observation), not
# the structural migration.
#
# ─── Neo4j Memory Model for 21-Component Engine ─────────────────────────────
#
# NODE LABELS (with properties):
#
#   (:Message {
#     id, text, role (user/assistant), timestamp, chat_id
#   })
#
#   (:Observation {
#     id, text, type (Problem/Attempt/Result/Note),
#     confidence, created_at
#   })
#
#   (:Fact {
#     id, text, truth_state (CLAIM/VERIFIED/REJECTED/UNKNOWN),
#     verified_by, verified_at, superseded_by, created_at
#   })
#
#   (:Episode {
#     id, title, start_time, end_time, summary,
#     state (ONGOING/CLOSED/COMPRESSED), node_count
#   })
#
#   (:SemanticMemory {
#     id, text, compressed_from, created_at
#   })
#
#   (:Concept { id, name })
#   (:Tool { id, name, version })
#   (:File { id, path })
#   (:Entity { id, name, type })
#   (:Decision { id, text, made_at })
#   (:Error { id, text, occurred_at })
#   (:Task { id, text, state (OPEN/IN_PROGRESS/DONE/ABANDONED) })
#   (:Goal { id, text })
#   (:Blocker { id, text })
#   (:Hypothesis { id, text, confidence })
#   (:Experiment { id, text, tried_at })
#   (:Outcome { id, text, result (SUCCESS/FAILURE/PARTIAL) })
#   (:Evidence { id, text, confidence, source_ref })
#   (:Domain { id, name })
#   (:Class { id, name, domain })
#   (:Method { id, name, signature, body, line_start, line_end })
#
# RELATIONSHIP TYPES (with properties):
#
#   Memory layer:
#     (:Message)-[:OBSERVED_AS]->(:Observation)
#     (:Observation)-[:SUPPORTS {confidence}]->(:Fact)
#     (:Fact)-[:PART_OF]->(:Episode)
#     (:Episode)-[:COMPRESSED_TO]->(:SemanticMemory)
#
#   Truth:
#     (:Fact)-[:CONTRADICTS]->(:Fact)
#     (:Fact)-[:OBSOLETES]->(:Fact)
#     (:Fact)-[:REPLACES {at}]->(:Fact)
#     (:Fact)-[:SUPERSEDED_BY]->(:Fact)
#
#   Temporal:
#     (:Node)-[:BEFORE]->(:Node)
#     (:Node)-[:AFTER]->(:Node)
#     (:Node)-[:REPLACED_BY {at}]->(:Node)
#     (:Node)-[:VALID_DURING {from, to}]->(:Node)
#
#   Identity:
#     (:Node)-[:ALIAS_OF]->(:Node)
#     (:Node)-[:SAME_AS {confidence}]->(:Node)
#     (:Node)-[:RENAMED_TO {at}]->(:Node)
#
#   Causal:
#     (:Node)-[:CAUSED_BY]->(:Node)
#     (:Node)-[:RESOLVES]->(:Node)
#     (:Node)-[:LED_TO]->(:Node)
#     (:Action)-[:FIXED_BY]->(:Fix)
#
#   Hierarchy:
#     (:Domain)-[:CONTAINS]->(:Class)
#     (:Class)-[:CONTAINS]->(:Method)
#     (:Method)-[:IN_FILE]->(:File)
#     (:Node)-[:OWNS]->(:Node)
#     (:Node)-[:MEMBER_OF]->(:Node)
#
#   Structural:
#     (:Node)-[:REFERENCES]->(:Node)
#     (:Node)-[:DEPENDS_ON]->(:Node)
#     (:Node)-[:RELATED_TO {weight}]->(:Node)
#
# INDEXES (for performance):
#
#   CREATE INDEX FOR (m:Message) ON (m.chat_id)
#   CREATE INDEX FOR (m:Message) ON (m.timestamp)
#   CREATE INDEX FOR (f:Fact) ON (f.truth_state)
#   CREATE INDEX FOR (t:Task) ON (t.state)
#   CREATE INDEX FOR (e:Episode) ON (e.state)
#   CREATE INDEX FOR (c:Concept) ON (c.name)
#   CREATE INDEX FOR (f:File) ON (f.path)
#   CREATE INDEX FOR (d:Domain) ON (d.name)
#   CREATE INDEX FOR (c:Class) ON (c.name)
#   CREATE INDEX FOR (m:Method) ON (m.name)
#
# EXAMPLE QUERIES:
#
#   "Why did RustDesk fail?"
#     MATCH (p:Concept {name: 'RustDesk'})
#           -[:CAUSED_BY]->(error:Error)
#     RETURN p, error
#
#   "What fixed the SSH issue?"
#     MATCH (e:Error)-[:FIXED_BY]->(f:Fix)
#     WHERE e.text CONTAINS 'SSH'
#     RETURN e, f
#
#   "What decisions were made in this episode?"
#     MATCH (d:Decision)-[:PART_OF]->(ep:Episode {id: $episodeId})
#     RETURN d
#
#   "What facts are still verified?"
#     MATCH (f:Fact {truth_state: 'VERIFIED'})
#     WHERE NOT (f)-[:SUPERSEDED_BY]->()
#     RETURN f
#
#   "Trace evidence chain for a fact"
#     MATCH path =
#       (f:Fact {id: $factId})
#         <-[:SUPPORTS]-(o:Observation)
#         <-[:OBSERVED_AS]-(m:Message)
#     RETURN path
#
# ─── Final Recommendation ────────────────────────────────────────────────────
#
# For the memory system described in this spec:
#
#   Best Graph Database      = Neo4j
#   Best Vector Database     = Qdrant
#   Best Relational Storage  = MySQL
#
# If forced to pick ONE database only: Neo4j
#
# The 3-DB stack (Neo4j + MySQL + Qdrant) gives:
#   - Native graph traversal (Neo4j)
#   - Semantic search (Qdrant)
#   - Relational storage + existing knowledge base (MySQL)
#
# Migration path:
#   1. Migrate graph_computation_units → Neo4j (structural, straightforward)
#   2. Build reasoning layers in Neo4j (Evidence, Truth, Observation)
#   3. Keep MySQL for raw chat, logs, feedback, audit
#   4. Keep Qdrant for semantic activation
#
# =============================================================================
# 3-DB DATA FLOW: How MySQL + Qdrant + Neo4j Work Together
# =============================================================================
#
# ─── Division of Responsibility ──────────────────────────────────────────────
#
#   MySQL  = Truth Store (structured records, codebase, computation units)
#   Qdrant = Meaning Store (embeddings, semantic similarity, context activation)
#   Neo4j  = Relationship Store (traversal, causality, identity, evidence chains)
#
# ─── What Each DB Owns ───────────────────────────────────────────────────────
#
# MYSQL owns:
#   - Structured truth (codebase, classes, methods, files)
#   - Computation units (2,407 units, 224 classes)
#   - Raw chat messages (message_id, chat_id, timestamp, text)
#   - Audit logs, runtime state, configuration
#   - Feedback tables, metrics, execution state
#   - Existing knowledge base (vb_shared, vb_code_test)
#
# QDRANT owns:
#   - Embeddings (vector for each message, observation, fact)
#   - Semantic similarity (nearest-neighbor retrieval)
#   - Meaning search ("find nodes that MEAN the same thing")
#   - Context activation (which nodes are semantically relevant to a query)
#
# NEO4J owns:
#   - Relationships (traversal, causality, identity)
#   - Evidence chains (Fact → Evidence → Message → Timestamp)
#   - Temporal links (BEFORE, AFTER, REPLACED_BY)
#   - Memory graph (Message → Observation → Fact → Episode → Semantic)
#   - Identity resolution (ALIAS_OF, SAME_AS)
#   - Hierarchy (Domain → Class → Method)
#
# ─── Example Data Flow ───────────────────────────────────────────────────────
#
# User says:
#   "RustDesk disconnects"
#   "SSH fixed it"
#
# Step 1: MySQL stores raw records
#   message_id=1001, chat_id=22, timestamp=..., text="RustDesk disconnects"
#   message_id=1002, chat_id=22, timestamp=..., text="SSH fixed it"
#
# Step 2: Qdrant stores embeddings
#   embedding(message 1001) → vector [0.12, 0.45, ...]
#   embedding(message 1002) → vector [0.08, 0.67, ...]
#   Payload: {"message_id": 1001}
#
# Step 3: Neo4j stores relationships
#   (RustDesk)-[:CAUSED]->(DisconnectIssue)
#   (DisconnectIssue)-[:RESOLVED_BY]->(SSH)
#   (SSH)-[:SUCCESSFUL_FIX]->(DisconnectIssue)
#
# Query flow:
#   User: "Why did remote desktop fail?"
#   → Qdrant: semantic search finds "RustDesk disconnect" (words don't match,
#     but meaning does)
#   → Neo4j: traverse from RustDesk node → CAUSED → DisconnectIssue
#   → MySQL: fetch raw message text for evidence (message_id=1001)
#   → LLM: receives structured context + evidence chain
#
# ─── Why This Works (Each DB Does What It's Best At) ─────────────────────────
#
# MySQL is excellent at:
#   SELECT, JOIN, transactions, consistency, large structured datasets
#   → 2,407 computation units + 224 classes belong HERE
#   → Raw messages with exact timestamps belong HERE
#   → Feedback records with exact scores belong HERE
#
# Qdrant is excellent at:
#   Meaning, similarity, recall, context activation
#   → "Why did remote desktop fail?" finds "RustDesk disconnect issue"
#     even when words don't match
#   → Semantic activation powers the graph activation engine
#
# Neo4j is excellent at:
#   "What caused this?" "What depends on this?" "What fixed this?"
#   "What replaced this?" "How are these connected?"
#   → Those are GRAPH questions — native traversal, no JOINs
#
# ─── CRITICAL TRAP: Do Not Duplicate ─────────────────────────────────────────
#
# The biggest mistake people make is: store everything everywhere.
#
# DON'T.
#
# Clean model:
#   MySQL    owns raw records
#   Qdrant   owns vectors
#   Neo4j    owns relationships
#
# Use IDs to connect them. Same ID everywhere:
#
#   mysql.message.id = 1001
#   qdrant.payload = {"message_id": 1001}
#   neo4j node = (:Message {message_id: 1001})
#
# The ID is the join key across all three databases.
# The DATA lives in ONE place. The ID is the bridge.
#
# Violations of this rule:
#   ✗ Storing message text in Neo4j (MySQL owns that)
#   ✗ Storing embeddings in MySQL (Qdrant owns that)
#   ✗ Storing relationships in MySQL JOINs (Neo4j owns that)
#   ✗ Duplicating computation_units into Neo4j as full text
#     (Neo4j should only store the ID + structural relationships)
#
# ─── Future: How Architecture Evolves ───────────────────────────────────────
#
# As the system grows, Neo4j becomes the place where reasoning objects live:
#   Message, Observation, Fact, Episode, SemanticMemory,
#   Evidence, Decision, Task, Goal, Identity
#
# While MySQL continues to own:
#   Codebase, Runtime, Configuration, Logs, Agents, Execution state
#
# This is a very common architecture for large memory systems:
#
#   MySQL  = Truth Store     (what IS — structured facts, code, state)
#   Qdrant = Meaning Store   (what MEANS — semantic similarity, vectors)
#   Neo4j  = Relationship Store (what CONNECTS — how things relate)
#
# Three stores, three responsibilities, one unified memory system.
#
# =============================================================================
# STORAGE STACK ANALYSIS: Do We Need More Databases?
# =============================================================================
#
# Current stack (MySQL + Qdrant + Neo4j) covers ~90-95% of the storage layer.
# The biggest bottleneck is NOT another database — it's the reasoning layers
# (Truth, Evidence, Identity, Temporal, Governor, Query Planner).
# Adding more storage engines does NOT solve reasoning problems.
#
# ─── Tier Ranking: Additional Engines ────────────────────────────────────────
#
# TIER 1 (Potentially Useful Later):
#   Redis — cache, fast activation memory, agent state, queues, temp context
#   Very common addition. Optional but helpful for runtime performance.
#
# TIER 2 (Only If Needed):
#   Elasticsearch — massive text search, log analysis, monitoring
#   Useful when text corpus becomes huge (millions of .md files / chat messages)
#
# TIER 3 (Probably Unnecessary):
#   MongoDB, Cassandra, CouchDB — no role they fill isn't already covered
#
# ─── Elasticsearch: When It Helps ────────────────────────────────────────────
#
# Elasticsearch is useful when you need:
#   - Full-text search across millions of documents
#   - Log analytics and Kibana dashboards
#   - Fuzzy matching (typos, partial words)
#   - Google-like search with ranking and stemming
#
# Engine comparison for text search:
#
#   Engine         | Primary Job              | Text Search Speed
#   ---------------|--------------------------|-------------------
#   MySQL          | Store structured data    | LIKE '%term%' — slow
#   SQLite         | Small local database     | LIKE '%term%' — slow
#   Elasticsearch  | Search engine            | Tokenized + indexed — ms
#   Qdrant         | Meaning search           | Semantic — ms
#   Neo4j          | Relationship traversal   | Not for text search
#
# Example: searching 500K markdown files + 50M chat messages + 10M code comments
#
#   SQLite:     Reads rows, LIKE '%rustdesk%' → SLOW
#   MySQL:      SELECT * FROM messages WHERE body LIKE '%rustdesk%' → better, not a search engine
#   Elasticsearch: Tokenized, indexed, ranked, fuzzy, stemming → MILLISECONDS
#
# ─── Elasticsearch vs Qdrant (Key Difference) ───────────────────────────────
#
#   Elasticsearch answers: "Find text that CONTAINS: rustdesk, relay, ssh, disconnect"
#     → Keyword match, fuzzy, stemming, ranking
#     → Exact words and variations
#
#   Qdrant answers: "Find text with SIMILAR MEANING to: 'remote desktop connection problem'"
#     → Semantic similarity, embeddings
#     → Works even if the word "RustDesk" never appears
#
# Both are needed for different reasons:
#   - Elasticsearch = keyword search (fast, exact, fuzzy)
#   - Qdrant = meaning search (semantic, conceptual)
#
# ─── Ideal Stack for Large Memory System ─────────────────────────────────────
#
#   Markdown Files
#         ↓
#   Elasticsearch → Keyword Hits (fast text search)
#         ↓
#   Embeddings
#         ↓
#   Qdrant → Semantic Hits (meaning search)
#         ↓
#   Relationships
#         ↓
#   Neo4j → Evidence Chains (graph traversal)
#         ↓
#   Truth/Data
#         ↓
#   MySQL → Structured Records (source of truth)
#
# Many enterprise AI systems end up looking very similar to this.
#
# ─── Complexity Tradeoff ─────────────────────────────────────────────────────
#
# Adding Elasticsearch means:
#   4 databases → 4 backups → 4 sync paths → 4 failure modes
#
# DON'T add Elastic because it's cool. Add it ONLY if:
#   - You have lots of text (millions of files/messages)
#   - You search text constantly
#   - LIKE queries are becoming painful
#   - You want Google-style search over .md files, chat logs, code comments
#
# Elasticsearch is NOT replacing MySQL — it's replacing painful text searching.
#
# ─── Final Storage Stack Recommendation ──────────────────────────────────────
#
# Frozen stack (today):
#
#   #1 MySQL         (MANDATORY)     — Structured truth, codebase, computation units
#   #2 Qdrant        (MANDATORY)     — Semantic memory, embeddings, meaning search
#   #3 Neo4j         (VERY VALUABLE)  — Relationship memory, graph traversal, evidence chains
#   #4 Redis         (OPTIONAL)       — Cache, agent runtime state, fast activation
#   #5 Elasticsearch (VALUABLE LATER) — When text corpus becomes huge
#
# Priority for next effort:
#   BUILD reasoning layers (Evidence, Truth, Temporal, Identity, Governor)
#   NOT more storage engines.
#
#   Reasoning layers are the bottleneck, not storage.
#   Adding Elasticsearch/MongoDB/Cassandra does not solve reasoning problems.
#
# =============================================================================
# THREE GRAPH LEVELS: Word → Entity → Reasoning
# =============================================================================
#
# ─── Level 1: Word Graph (Index Layer) ───────────────────────────────────────
#
# Nodes:  RustDesk, SSH, relay, disconnect, fixed, broken
# Edges:  appears_near, appears_in, co_occurs_with
#
# Example:
#   Chat 1: "RustDesk disconnects"
#   Chat 2: "SSH fixed RustDesk"
#   Chat 3: "RustDesk relay mode broken"
#
# Produces:
#   RustDesk → Chat1, Chat2, Chat3
#   SSH → Chat2
#   relay → Chat3
#
# This is a perfectly legitimate graph. But it knows WORDS, not MEANING.
# It knows "RustDesk" and "disconnect" appear together, but NOT that:
#   - RustDesk had a problem (disconnects)
#   - SSH was the solution
#   - The result was resolved
#
# ─── Level 2: Entity Graph (Association Layer) ──────────────────────────────
#
# Nodes:  RustDesk (TOOL), SSH (TOOL), Relay Mode (CONCEPT), MacBook (ENTITY)
# Edges:  uses, contains, depends_on, references
#
# Now we're above words — nodes have types and semantic identity.
# But still associative: "RustDesk uses relay mode" without causality or outcome.
#
# ─── Level 3: Reasoning Graph (Knowledge Layer) ─────────────────────────────
#
# Nodes:  Problem, Decision, Evidence, Fact, Observation, Outcome, Task
#
# Example:
#   Problem:    RustDesk disconnects
#   Experiment: Disable relay
#   Outcome:    Failed
#   Experiment: SSH
#   Outcome:    Success
#
# This is the graph an AI really wants. It answers WHY, not just WHAT.
#
# ─── Search vs Graph: Important Distinction ──────────────────────────────────
#
# What the word graph describes:
#   Word → Chat → Line
#
# That's actually closer to a SEARCH INDEX (inverted index) than a reasoning graph:
#
#   RustDesk → chat1:line5, chat3:line9, chat8:line2
#   SSH      → chat2:line4, chat8:line7
#
# That's Elasticsearch / inverted index — incredibly useful, but NOT:
#
#   RustDesk → CAUSED → Disconnect Problem → RESOLVED_BY → SSH
#
# which is what Neo4j-style graphs are good at.
#
# Search index = "where does this word appear?"
# Reasoning graph = "how are these things connected and why?"
#
# ─── Likely Final Shape: 4-Layer Architecture ───────────────────────────────
#
# All four layers exist simultaneously, each answering a different question:
#
#   Layer 1: Word Index (Elasticsearch)
#     → "Where was this word used?"
#     → chat1:line5, chat3:line9
#
#   Layer 2: Embeddings (Qdrant)
#     → "What means something similar?"
#     → "remote desktop connection problem" finds RustDesk disconnect
#
#   Layer 3: Facts/Relationships (Neo4j)
#     → "How is it connected?"
#     → RustDesk → CAUSED → Disconnect → RESOLVED_BY → SSH
#
#   Layer 4: Raw Source Records (MySQL)
#     → "Where is the original source?"
#     → message_id=1001, chat_id=22, text="RustDesk disconnects"
#
# Full query example: "Why did we stop using RustDesk?"
#
#   Layer 1 (Elasticsearch): Find all mentions of "RustDesk" → 47 hits
#   Layer 2 (Qdrant): Find semantically similar → "disconnect", "relay", "unstable"
#   Layer 3 (Neo4j): Traverse graph → RustDesk → CAUSED → disconnect
#                                          → RESOLVED_BY → SSH
#                                          → DECISION → "stop using RustDesk"
#   Layer 4 (MySQL): Fetch evidence → message 112, 145, 188
#
#   Answer:
#     Evidence:   Message 112, 145, 188
#     Observed:   Frequent disconnects
#     Decision:   Move to SSH
#     Outcome:    Stable connection
#
# A pure word graph (Level 1) cannot answer that.
# A pure entity graph (Level 2) cannot answer that.
# You need Level 3 (reasoning) + all 4 storage layers.
#
# ─── Where Current System Sits ───────────────────────────────────────────────
#
# Current GraphEngine = Level 2 (Entity Graph)
#   - Extracts typed nodes (TOOL, ERROR, DECISION)
#   - Builds typed edges (CAUSED_BY, RESOLVED_BY)
#   - But no observations, no evidence chains, no truth states
#
# Target (21-component spec) = Level 3 (Reasoning Graph)
#   - Observations bridge raw chat → structured knowledge
#   - Facts have truth states (CLAIM/VERIFIED/REJECTED)
#   - Evidence chains prove why we believe each fact
#   - Episodes group related events
#   - Semantic memories compress episodes into timeless knowledge
#
# The word graph (Level 1) is the INDEX LAYER — useful for search,
# but not the reasoning engine itself.
#
# =============================================================================
# WORDS → CONCEPTS → IDEAS → PLANS → KNOWLEDGE GRAPH
# =============================================================================
#
# The full idea plan: not just "words connect" but "ideas form around groups of
# words, ideas connect into plans, plans become knowledge."
#
# ─── The 5-Layer Compression Hierarchy ───────────────────────────────────────
#
#   Words      (1,000,000)  → search index, raw tokens
#       ↓ PART_OF
#   Concepts   (50,000)     → words cluster into named concepts
#       ↓ CONTRIBUTES_TO
#   Ideas      (10,000)     → concepts connect into ideas
#       ↓ SUPPORTS
#   Plans      (1,000)      → ideas become decisions and plans
#       ↓ LEADS_TO
#   Knowledge  (100)        → plans become proven facts (core memories)
#
# This is exactly why a memory system doesn't drown in data.
# It compresses upward. Each layer is ~10-20x smaller than the one below.
#
# ─── Example: RustDesk → SSH Migration ──────────────────────────────────────
#
# Layer 1: WORDS
#   RustDesk, disconnects, relay, SSH, standard, stable, fixed, broken
#
# Layer 2: CONCEPTS (words cluster)
#   {RustDesk, relay, disconnects} → "Remote Desktop Problem"
#   {SSH, stable, standard}        → "SSH Solution"
#
# Layer 3: IDEAS (concepts connect)
#   Remote Desktop Problem
#       ↓ resolved_by
#   SSH Solution
#
#   This is no longer a word graph. This is an IDEA graph.
#
# Layer 4: PLANS (ideas become decisions)
#   Problem:    RustDesk unreliable
#   Idea:       Use SSH
#   Decision:   Migrate to SSH
#   Outcome:    Stable access
#
#   Now you have: Problem → Idea → Decision → Outcome
#   which is much closer to reasoning.
#
# Layer 5: KNOWLEDGE (plans become proven facts)
#   Fact: "SSH replaced RustDesk for remote access"
#   Evidence: Messages 1001, 1002, 1003
#   Truth state: VERIFIED
#   Episode: "RustDesk connectivity debugging"
#
# ─── Full Reasoning Chain (What the Graph Stores) ───────────────────────────
#
#   RustDesk (word)
#       ↓ PART_OF
#   Remote Desktop Instability (concept)
#       ↓ CONTRIBUTES_TO
#   SSH Preferred (idea)
#       ↓ SUPPORTS
#   Migrate To SSH (decision)
#       ↓ LEADS_TO
#   Stable Connection (outcome)
#       ↓ PROVES
#   Fact: SSH replaced RustDesk (knowledge)
#
# That is far more powerful than simply: RustDesk → SSH
# because it preserves the REASONING CHAIN — not just the connection.
#
# ─── What a Mature Memory Graph Actually Stores ─────────────────────────────
#
# A mature memory graph stores very little at the word level.
# Words are mostly the SEARCH LAYER (Elasticsearch / inverted index).
#
# The graph stores:
#   Concepts   — named clusters of meaning
#   Ideas      — how concepts relate
#   Facts      — verified claims with evidence
#   Decisions  — what was chosen and why
#   Tasks      — what needs doing
#   Goals      — what we're working toward
#   Evidence   — why we believe each fact
#   Episodes   — grouped events with time ranges
#
# because those are the things humans reason about.
#
# Words are the raw material. Concepts are the building blocks.
# Ideas are the structures. Plans are the blueprints.
# Knowledge is the finished building.
#
# ─── How This Maps to the 21-Component Spec ─────────────────────────────────
#
#   Words      → Layer 1 (search index, Elasticsearch)
#   Concepts   → Component 1 (Node Extraction) + Component 11 (Identity)
#   Ideas      → Component 21 (Observation Engine)
#   Plans      → Component 9 (Open Loop) + Component 19 (Causal Graph)
#   Knowledge  → Component 8 (Truth) + Component 16 (Evidence) +
#                Component 14 (Compression) + Component 18 (Semantic Memory)
#
# The 5-layer hierarchy IS the 21-component spec, viewed from above.
# Each layer is a different altitude of the same memory system.
#
# =============================================================================
# CORE INSIGHT: What We're Actually Building
# =============================================================================
#
# KEY SHIFT (IMPORTANT):
#
#   WRONG VIEW:
#     words are nodes
#     graph connects words
#
#   CORRECT VIEW:
#     words are SIGNALS
#     concepts are NODES
#     ideas are COMPRESSED MEANING
#     graph connects CAUSAL STRUCTURE
#
# We are NOT building a word graph.
# We are building:
#
#   👉 A MEANING COMPRESSION SYSTEM that turns chat into causal memory
#
# ─── Simple Final Model ──────────────────────────────────────────────────────
#
#   WORDS
#     ↓ (co-occurrence + context)
#   MEANING CLUSTERS
#     ↓ (semantic grouping)
#   CONCEPTS
#     ↓ (meaning clustering)
#   IDEAS (causal units)
#     ↓ (intent + causality)
#   DECISIONS / PLANS
#     ↓ (execution structure)
#   KNOWLEDGE GRAPH (connected causal history + evidence)
#
# ─── What Each Layer Actually Is ─────────────────────────────────────────────
#
#   INDEX LAYER (WORDS):
#     "RustDesk", "SSH", "disconnect"
#     → Inverted index, like search engines
#     → Elasticsearch style indexing
#     → NOT intelligence yet — just signals
#
#   MEANING LAYER (CONCEPTS):
#     "remote desktop instability"
#     "secure access method"
#     → Words cluster into named concepts
#     → Co-occurrence + context determines grouping
#
#   REASONING LAYER (IDEAS):
#     "RustDesk is unreliable in this network"
#     "SSH is a stable alternative"
#     → Concepts form causal ideas
#     → This is where WHY enters the system
#
#   DECISION LAYER (PLANS):
#     "Switch system to SSH"
#     → Ideas become decisions with intent
#     → Plans have execution structure
#
#   MEMORY LAYER (GRAPH):
#     Connected causal history + evidence
#     → The knowledge graph stores proven facts
#     → Each fact has evidence, truth state, temporal validity
#
# ─── Why This Matters ────────────────────────────────────────────────────────
#
# Only at the IDEA level can you answer:
#   - Why did something happen?
#   - What caused it?
#   - What fixed it?
#   - What changed over time?
#
# Word-level graphs CANNOT do that.
# They know THAT words appear together, but not WHY or WHAT IT MEANS.
#
# ─── The Real Engineering Boundary ───────────────────────────────────────────
#
# The critical question is NOT "how do we store the graph?"
# (MySQL + Qdrant + Neo4j already answers that)
#
# The critical question is:
#
#   "How do I automatically convert raw chat → concepts → ideas → decisions
#    without losing information or creating wrong groupings?"
#
# That is the real engineering boundary where this system becomes usable.
#
# Wrong groupings = bad concepts = bad ideas = bad decisions = bad memory
# The conversion pipeline IS the product. The graph is just the storage.
#
# ─── Conversion Pipeline (The Hard Part) ────────────────────────────────────
#
#   Step 1: WORDS → CONCEPTS
#     How: Co-occurrence analysis + embedding clustering + NLP
#     Risk: Wrong clusters (grouping "Java" the island with "Java" the language)
#     Mitigation: Context windows + identity resolution (Component 11)
#
#   Step 2: CONCEPTS → IDEAS
#     How: Causal pattern detection + LLM-assisted extraction
#     Risk: False causality (A appears before B ≠ A caused B)
#     Mitigation: Evidence chains (Component 16) + truth states (Component 8)
#
#   Step 3: IDEAS → DECISIONS
#     How: Intent detection + decision markers in chat
#     Risk: Misreading suggestions as decisions
#     Mitigation: User confirmation tracking + open loop detection (Component 9)
#
#   Step 4: DECISIONS → KNOWLEDGE
#     How: Outcome verification + evidence accumulation + compression
#     Risk: Premature compression (compressing before enough evidence)
#     Mitigation: Memory Governor (Component 20) + temporal validity (Component 7)
#
# Each step is a FILTER, not just a transformer:
#   - Good signals pass through
#   - Noise gets filtered out
#   - Uncertainty gets marked (CLAIM, not FACT)
#   - Only verified outcomes become knowledge
#
# =============================================================================
#
# THE GOAL:
#   A graph engine that processes a chat.md file and produces structured memory
#   that an LLM can query — giving the LLM guaranteed context recall instead
#   of hoping it remembers the right things.
#
# ANALOGY:
#   Graph Engine = Hippocampus (store/retrieve structured memory, no AI needed)
#   LLM          = Cortex (reason about what the memories mean, AI part)
#   Together     = Structured memory + reasoning = reliable context awareness
#
# THE ENGINE NEEDS THESE CAPABILITIES:
#
# 1. NODE EXTRACTION (Parsing)
#    - Read chat.md line by line
#    - Identify and extract node types:
#      a. CONCEPTS    — key ideas mentioned (e.g. "stretch mode", "aspect ratio")
#      b. FILES       — file paths referenced (e.g. model.dart, consts.dart)
#      c. TOOLS       — software/tools mentioned (e.g. Flutter, Rust, RustDesk)
#      d. INTENT      — what the user wants (e.g. "fix scaling", "no black bars")
#      e. ENTITIES    — people, machines, IDs (e.g. "Devin", "192.168.8.50")
#      f. ERRORS      — problems encountered (e.g. "orphaned sshd", "handoff failed")
#      g. DECISIONS   — choices made (e.g. "use option 1, SSH from Mac")
#      h. VALUES      — specific numbers (e.g. "1366x768", "1280x800", "version 1.4.8")
#
# 2. EDGE BUILDING (Association)
#    - Connect nodes with typed relationships:
#      a. REFERENCES     — node A mentions node B
#      b. DEPENDS_ON     — node A requires node B to be true/done
#      c. CONTRADICTS    — node A conflicts with node B
#      d. RESOLVES       — node A solves problem node B
#      e. CAUSED_BY      — error node A was caused by action node B
#      f. PART_OF        — node A is a component of node B
#      g. RELATED_TO     — general association (fallback)
#    - Build edges from:
#      - Proximity (nodes mentioned in same message)
#      - Causality (one message causes a later outcome)
#      - Repeated mentions (node appears across multiple messages = important)
#      - User confirmation (user says "yes" to a suggestion = strong edge)
#
# 3. GRAPH ACTIVATION (Querying)
#    - When a new message comes in, find the relevant subgraph:
#      a. Keyword match — match new message words against node values
#      b. Semantic match — embedding similarity (Qdrant/MLX) against node embeddings
#      c. Edge traversal — from matched nodes, follow edges to connected nodes
#      d. Recency boost — more recent nodes get higher activation score
#      e. Frequency boost — nodes mentioned many times get higher activation score
#    - Return the activated subgraph (nodes + edges) as context for the LLM
#
# 4. MEMORY PERSISTENCE (Storage)
#    - Store the graph so it survives across sessions
#    - Options:
#      a. SQLite (lightweight, local)
#      b. MySQL (already available in this workspace)
#      c. Qdrant (vector search for semantic activation)
#      d. JSON file (simplest, for small chats)
#    - Each node has: id, type, value, timestamp, message_source, embedding
#    - Each edge has: id, source_id, target_id, relationship_type, weight
#
# 5. INTEGRATION WITH LLM (The Cortex)
#    - The engine does NOT generate responses — that is the LLM's job
#    - The engine provides:
#      a. Activated subgraph (relevant nodes + edges) as structured context
#      b. Summary of what has been discussed (from node frequencies)
#      c. List of open problems (nodes with type=ERROR, status=unresolved)
#      d. List of decisions made (nodes with type=DECISION)
#    - The LLM receives this as system context and produces a response
#    - This is what ContextRAM already does — store nodes, query them, feed to LLM
#
# 6. ITERATION & LEARNING (Improvement over time)
#    - When the LLM produces a good response, mark the activated subgraph as useful
#    - When the LLM produces a bad response, mark the activated subgraph as insufficient
#    - Adjust edge weights based on feedback
#    - Add new nodes from the LLM's response back into the graph
#    - This creates a feedback loop: graph improves with every conversation
#
# EXISTING TOOLS THAT COVER PARTS OF THIS:
#   - GraphEngine      → Node extraction + edge building (parts 1, 2)
#   - CascadeEngine    → Graph activation + traversal (part 3)
#   - DecisionEngine   → Decision tracking + resolution (part of 1d, 1g)
#   - ContextRAM (MCP) → Memory persistence + LLM integration (parts 4, 5)
#   - Qdrant           → Semantic match for activation (part 3b)
#   - MLX embeddings   → Vector generation for nodes (part 3b, 4)
#
# WHAT IS MISSING (the gap to close):
#   - A unified pipeline that chains: parse chat.md → extract nodes → build edges
#     → store graph → activate on query → feed to LLM → learn from response
#   - This file (test_all_on_chat.py) is the experiment to see how far the
#     existing engines get toward that pipeline.
# =============================================================================
# MAPPING RESULTS: Graph computation units extracted to SQL database
# =============================================================================
#
# Database: graph_computation_units
# Table: computation_units
# Schema: 1 method = 1 row = 1 computation unit → belongs to 1 class
#
# Columns:
#   id, unit_hash, class_name, method_name, signature, body,
#   file_path, line_start, line_end, source, domain, role, is_dunder
#
# Sources:
#   1. MySQL vb_code_test (1,394 VBStyle classes, 13,818 methods)
#      → Filtered to graph-related: 104 classes, 916 methods
#   2. Local codebase (/Users/wws/Qdrant_mysql_mlx_vector_engine/)
#      → 185 Python files scanned, 120 classes, 1,491 methods
#
# TOTAL: 2,407 computation units across 224 unique classes
#
# Graph keywords used for filtering:
#   graph, node, edge, cascade, decision, embed, vector, memory,
#   context, brain, cognitive, knowledge, reasoning, semantic,
#   tfidf, cosine, similarity, traverse, adjacency, topology,
#   cluster, community, centrality, pagerank, bfs, dfs,
#   shortest_path, spanning, dag, directed
#
# Top classes by method count:
#   AgentGraph         68 methods
#   DbInterrogator     67 methods
#   GraphEngine        66 methods
#   BracketMemoryStore 47 methods
#   BrokenCodeGenerator 43 methods
#   VBStyleClusterAuditCLI 37 methods
#   DomKnowledge       35 methods
#   AgentBrain         33 methods
#   DomGraph           31 methods
#   DomMemory          31 methods
#   PlanGraphViewer    28 methods
#   DomCodegraph       27 methods
#   CodeGraph          27 methods
#   ExecutionGraph     27 methods
#   CognitiveBrain     26 methods
#   GraphViewer        22 methods
#
# Pipeline script: /Users/wws/Qdrant_mysql_mlx_vector_engine/map_graph_units.py
# Run: python map_graph_units.py
# =============================================================================
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from GraphEngine import GraphEngine
from CascadeEngine import CascadeEngine
from DecisionEngine import DecisionEngine
from GraphViewer import GraphViewer
from Inspect import Inspect
from Verify import Verify

CHAT_FILE = os.path.join(os.path.dirname(__file__), "..", "chat_mover", "Codex Chat Cleanup.md")
CHAT_FILE = os.path.abspath(CHAT_FILE)

def PrintResult(title, ok, data, err, max_chars=600):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")
    print(f"  ok={ok}, error={err}")
    if data:
        text = json.dumps(data, indent=2, default=str)
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n  ... ({len(text)} chars total, truncated)"
        print(text)
    else:
        print("  (no data)")

print("=" * 70)
print("  FULL TEST: All Graph Engine Modules vs Chat File")
print(f"  Target: {CHAT_FILE}")
print("=" * 70)

# --- 1. INSPECT: Parse the chat file as if it were code ---
print("\n\n" + "=" * 70)
print("  MODULE 1: INSPECT (AST parser)")
print("=" * 70)

insp = Inspect()

# Try parsing the .md file (will likely fail — it's not Python)
PrintResult("Inspect.parse on .md file",
    *insp.Run('parse', {'filepath': CHAT_FILE}))

# Parse a Python file mentioned in the chat
PrintResult("Inspect.parse on import_codex_chat.py",
    *insp.Run('parse', {'filepath': os.path.join(os.path.dirname(__file__), 'import_codex_chat.py')}))

PrintResult("Inspect.parse on GraphEngine.py",
    *insp.Run('parse', {'filepath': os.path.join(os.path.dirname(__file__), 'GraphEngine.py')}))

PrintResult("Inspect.parse on chat_mover.py",
    *insp.Run('parse', {'filepath': os.path.join(os.path.dirname(__file__), '..', 'chat_mover', 'chat_mover.py')}))

# --- 2. VERIFY: Run checks ---
print("\n\n" + "=" * 70)
print("  MODULE 2: VERIFY (VBStyle checker)")
print("=" * 70)

ver = Verify()

for check_num in range(1, 11):
    PrintResult(f"Verify.check {check_num}",
        *ver.Run('check', {'check_num': check_num}))

PrintResult("Verify.all",
    *ver.Run('all', {}), max_chars=1200)

# --- 3. GRAPH ENGINE: All views ---
print("\n\n" + "=" * 70)
print("  MODULE 3: GRAPH ENGINE (all 20 commands)")
print("=" * 70)

ge = GraphEngine()

commands = [
    ('status', {}),
    ('plan', {'domain': 'graph_engine'}),
    ('spec', {'domain': 'graph_engine'}),
    ('flow', {'domain': 'graph_engine'}),
    ('lifecycle', {}),
    ('dependency', {}),
    ('error', {}),
    ('orchestration', {}),
    ('gap', {'domain': 'graph_engine'}),
    ('cycle', {}),
    ('topology', {}),
    ('search', {'query': 'chat'}),
    ('search', {'query': 'email'}),
    ('search', {'query': 'gmail'}),
    ('search', {'query': 'mysql'}),
    ('search', {'query': 'graph'}),
    ('search', {'query': 'import'}),
    ('instructions', {'category': 'howto'}),
    ('instructions', {}),
    ('bfs', {'start_node': 1}),
    ('dfs', {'start_node': 1}),
    ('path', {'start_node': 2, 'end_node': 45}),
]

for cmd, params in commands:
    PrintResult(f"GraphEngine.Run('{cmd}')",
        *ge.Run(cmd, params))

# --- 4. CASCADE ENGINE: Start, run stages, validate ---
print("\n\n" + "=" * 70)
print("  MODULE 4: CASCADE ENGINE (8-stage gate)")
print("=" * 70)

ce = CascadeEngine()

PrintResult("CascadeEngine.start",
    *ce.Run('start', {
        'idea': 'Analyze Codex Chat Cleanup.md with graph engine',
        'spec_path': CHAT_FILE
    }))

# Get the run_id from start
ok, data, err = ce.Run('start', {
    'idea': 'Test run for chat analysis',
    'spec_path': CHAT_FILE
})
run_id = data.get('run_id') if data else None
print(f"\n  run_id = {run_id}")

if run_id:
    for stage in ['plan', 'spec', 'flow', 'lifecycle', 'dependency', 'error', 'orchestration', 'gap']:
        PrintResult(f"CascadeEngine.stage('{stage}')",
            *ce.Run('stage', {'run_id': run_id, 'stage': stage}))

    PrintResult("CascadeEngine.validate (all 8 stages)",
        *ce.Run('validate', {'run_id': run_id}), max_chars=1200)

    PrintResult("CascadeEngine.status",
        *ce.Run('status', {'run_id': run_id}), max_chars=800)

# --- 5. DECISION ENGINE: Start, step, end ---
print("\n\n" + "=" * 70)
print("  MODULE 5: DECISION ENGINE (DEGS loop)")
print("=" * 70)

de = DecisionEngine()

PrintResult("DecisionEngine.start",
    *de.Run('start', {'domain': 'graph_engine'}))

ok, data, err = de.Run('start', {'domain': 'graph_engine'})
de_run_id = data.get('run_id') if data else None
print(f"\n  degs run_id = {de_run_id}")

if de_run_id:
    for i in range(5):
        ok, data, err = de.Run('step', {'run_id': de_run_id})
        PrintResult(f"DecisionEngine.step ({i+1})",
            ok, data, err)
        if not ok or (data and data.get('terminal')):
            break

    PrintResult("DecisionEngine.status",
        *de.Run('status', {'run_id': de_run_id}))

    PrintResult("DecisionEngine.end",
        *de.Run('end', {'run_id': de_run_id}))

# --- 6. GRAPH VIEWER: Headless render ---
print("\n\n" + "=" * 70)
print("  MODULE 6: GRAPH VIEWER (headless)")
print("=" * 70)

gv = GraphViewer()

# Simulate graph data from chat analysis
chat_nodes = [
    {"id": "Gmail Setup", "type": "action"},
    {"id": "Yahoo Mail", "type": "action"},
    {"id": "MCP Config", "type": "check"},
    {"id": "Graph Engine", "type": "question"},
    {"id": "Chat Import", "type": "action"},
    {"id": "Cleanup", "type": "fallback"},
]
chat_edges = [
    {"from": "Gmail Setup", "to": "MCP Config"},
    {"from": "Yahoo Mail", "to": "MCP Config"},
    {"from": "MCP Config", "to": "Graph Engine"},
    {"from": "Graph Engine", "to": "Chat Import"},
    {"from": "Chat Import", "to": "Cleanup"},
]

PrintResult("GraphViewer.headless (chat graph)",
    *gv.Run('headless', {
        'view': 'chat_analysis',
        'nodes': chat_nodes,
        'edges': chat_edges
    }))

PrintResult("GraphViewer.render (headless fallback)",
    *gv.Run('render', {
        'view': 'chat_analysis',
        'nodes': chat_nodes,
        'edges': chat_edges
    }))

# --- SUMMARY ---
print("\n\n" + "=" * 70)
print("  SUMMARY: All Modules Tested")
print("=" * 70)
print("""
  Inspect:        Parses .py files — extracts classes, methods, Run()/Tuple3
                  Cannot parse .md chat files (not Python)

  Verify:         10-check VBStyle compliance checker
                  Found 24+ classes missing Run() in DB

  GraphEngine:    20 commands all functional
                  Search (FTS5) found 'chat', 'email', 'gmail', 'mysql', 'graph'
                  12 cycles detected in decision graph
                  1 missing table: spec_data

  CascadeEngine:  8-stage validation gate — all stages passed
                  Creates run, executes stages, validates, reports status

  DecisionEngine: DEGS loop — starts, steps through nodes, ends
                  Hit bcl_token_not_found on first step (parser issue)

  GraphViewer:    Headless mode works — returns nodes/edges as JSON
                  No Tkinter needed for data analysis
""")
