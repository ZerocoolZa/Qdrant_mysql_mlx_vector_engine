# Explicit Reasoning Graph — Architecture & Plan

[@GHOST]
[@VBSTYLE]
[@FILEID] /Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Gui/EXPLICIT_REASONING_GRAPH.md
[@SUMMARY] Architecture document for the multi-layer explicit reasoning graph. Documents current state (Stage 1 complete: 5 layers wired), and plans 6 stages: evidence-provenance confidence, executable CUs as verbs, policy layer, common node interface, graph/execution separation, and full brain wiring. Includes the 7-step reasoning loop: question -> operator -> activation -> evidence -> confidence -> CU -> policy -> execution -> learning.
[@CLASS] (document)
[@METHOD] (document)
[@AUTHORITY] architecture
[@DOMAIN] documentation

---

## What This Is

An explicit reasoning graph — NOT a neural network in the ML sense.

Knowledge is:
- explicit (nodes are named, not distributed in weights)
- inspectable (every edge can be traced)
- explainable (you can see WHY any node activated)
- traceable (full path from query to conclusion)

This is a feature, not a limitation. When the system says "ErrorCapture is
relevant to WHY," you can see exactly which edge, which weight, which keyword
match produced that conclusion. You cannot do that with a neural net.

---

## Architectural Principles

### 1. Nouns vs Verbs

The graph contains two fundamental kinds of nodes:

**Nouns** (what exists):
- Law, Class, Method, Question, Graph, Memory, Rule, Problem, Solution

**Verbs** (what does):
- Think, Learn, Ask, Validate, Capture, Generate, Arbitrate, Embed

Nouns are facts. Verbs are behaviors. Activation flows through nouns until
it reaches a verb — at which point reasoning becomes action.

```
WHY (noun: inquiry)
  |
  v
ErrorCapture (noun: BCLIR class)
  |
  v
CU_ErrorCapture (verb: computational unit)
  |
  v
Execute()  -->  New evidence
```

This distinction is structural, not cosmetic. Noun nodes store state.
Verb nodes transform state. The graph routes activation; verbs act on it.

### 2. Evidence Provenance — Never Collapse

Confidence is NOT a single number. It is a vector of independent evidence
streams, each preserved with its source:

```
Evidence {
    structural  = 1.00   (BCLIR: class exists, authority_score)
    semantic    = 0.73   (BCL: rule applies, know_answers confidence)
    topological = 0.92   (Graph: survived versions, survival_score)
    runtime     = 0.61   (Memory: stability_score)
}
```

The overall confidence (e.g. 0.81) is computed from these, but the
individual streams are NEVER discarded. This means:

- "Why is confidence only 0.81?" -> "Runtime confidence is weak (0.61)"
- Conflicting evidence can coexist instead of forcing one answer
- Each stream can be updated independently without touching the others
- Debugging is possible: you can see WHICH evidence source is unreliable

### 3. Capability vs Permission

Two separate questions, two separate layers:

- **Capability** (Computational Units): "I can" — the system has the ability
- **Permission** (Policies): "You may" — the system is allowed to

```
Question: "Delete old files?"
  |
  v
Activate CU_DeleteFiles
  |
  v
Policy check:
    permission = denied   (safety policy blocks destructive ops)
  |
  v
Result: activation stops, execution denied
```

Without the policy layer, any sufficiently activated CU would execute.
That's dangerous. Policies are the guardrail between reasoning and action.

### 4. Graph vs Execution Engine — Keep Them Separate

The graph and the execution engine are different things:

- **Graph** answers: "What is connected?" (knowledge substrate)
- **Execution Engine** answers: "What happens next?" (interpreter)

The graph is the knowledge. The execution engine is the actor that reads
the graph, follows activation, checks policies, and invokes CUs.

This separation makes the system debuggable and evolvable:
- Graph can be inspected without executing anything
- Execution engine can be tested with a fixed graph
- Graph can grow without changing the executor
- Executor can be swapped without touching the graph

### 5. The 7-Step Reasoning Loop

```
1. Question chooses an inquiry operator
       "WHY did this error happen?"
       -> operator = WHY

2. The operator activates relevant graph regions
       WHY -> {PERSON}, {THING}, CAUSE
       WHY -> ErrorCapture (keyword "error")
       WHY -> CU_ErrorCapture (cross-layer)

3. Multiple evidence layers contribute independently
       BCLIR:     ErrorCapture exists (structural = 1.0)
       BCL:       "Tuple3 return pattern" applies (semantic = 0.73)
       Graph:     ErrorCapture survived 3 versions (topological = 0.92)
       Memory:    ErrorCapture stability = 0.61 (runtime = 0.61)

4. Confidence is aggregated while preserving provenance
       overall = weighted_average(structural, semantic, topological, runtime)
       overall = 0.81
       BUT each stream is still individually accessible

5. Activation reaches one or more Computational Units
       CU_ErrorCapture activation = 0.92
       CU_ErrorCapture confidence = 0.81

6. Policies determine whether execution is permitted
       Policy: "error capture is safe" -> permission = allowed
       (If CU_DeleteFiles: "destructive op" -> permission = denied)

7. Execution produces new facts, memories, or graph updates
       CU_ErrorCapture.Execute()
       -> ErrorCapture.Run("capture", {})
       -> (1, {errors_captured: 3, details: [...]}, None)
       -> New facts added to knowledge graph
       -> Memory updated with new stability data
       -> Loop closes: learning from execution
```

This closes the loop: question -> reasoning -> action -> learning.
Each stage remains inspectable. You can see not only the answer but
exactly how it arrived there and why it chose to act.

### 6. Magnetic Clustering — How Computational Units Emerge

Computational Units are not manually declared. They EMERGE through
magnetic attraction between methods. Methods have magnetic signatures
computed from their properties, and compatible methods "snap together"
into clusters. When a cluster seals (no more external calls reaching
out), it becomes a Computational Unit.

#### The Magnetic Signature

Every method carries a magnetic signature — a multi-affinity vector
that determines what it attracts and what it repels:

```
Method A: ErrorCapture.capture
    params:   self, exception, file_path, func_name, line_no
    domain:   error
    role:     runtime
    returns:  Tuple3

Method B: ErrorScanner.scan
    params:   self, exception, file_path
    domain:   error
    role:     runtime
    returns:  Tuple3

MagneticAffinity(A, B) {
    structural  = 0.88   (compatible params: both take Exception)
    behavioral  = 0.94   (called together 14 times, 5 internal calls)
    semantic    = 0.91   (same domain: "error", same role: "runtime")
    historical  = 0.82   (survived 3 versions together)
}
overall = 0.89  -> ATTRACT (above threshold)
```

#### The Four Affinities (parallel to evidence provenance)

| Affinity | Computed from | Source in MySQL |
|---|---|---|
| Structural | params compatibility, return type match | vb_methods.params, vb_classes.return_type |
| Behavioral | called together, internal_calls, co_occurrence | bcl_units.internal_calls, code_co_occurrence |
| Semantic | same domain, same role, description similarity | vb_classes.domain, vb_classes.role |
| Historical | survived versions together | code_index.survival_score |

Same pattern as evidence provenance: 4 independent streams, never
collapsed. The magnetic score is a VECTOR. You can ask "Why did these
methods cluster?" and see: "Behavioral affinity was 0.94 — they're
called together constantly."

#### Attraction vs Repulsion

```
ATTRACTION (methods stick together):
  - compatible parameters (both take Exception)
  - same domain (both "error")
  - same authority (both "runtime")
  - called together frequently (high co_occurrence)
  - high internal_calls (they call each other)
  - survived versions together (historical affinity)

REPULION (methods push apart):
  - incompatible parameters
  - contradictory responsibilities
  - different authorities
  - unrelated domains
  - never called together
  - different evolution history
```

#### The Clustering Process (Emergence)

```
Method (alone, method_count=1)
    |
    | magnetic attraction (internal_calls increase)
    v
Micro capability (2-3 methods sticking, internal_calls > 0)
    |
    | more attraction, external_call_count decreases
    v
Computational Unit (is_closed=1, sealed clump, external_calls=0)
    |
    | CUs attract each other (cross-unit co_occurrence)
    v
Subsystem (multiple classes, high method_count)
    |
    | subsystems cluster
    v
Domain
    |
    | domains connect
    v
Application
```

This is hierarchical emergence. Nobody writes "this is a computational
unit." The system DISCOVERS it: "These 9 methods always travel together.
They share inputs. They share outputs. They share authority. They call
one another. Therefore they emerge as one computational unit."

#### What the Data Shows Right Now

The bcl_units table IS the magnetic clustering result:

```
SEALED CLUMPS (is_closed=1 — magnetic seal complete):
  unit_3:  ZramStorageAdapter   9 methods, 8 internal, 0 external
           -> STRONG clump (8 internal calls = high attraction, 0 external = sealed)

  unit_7:  OSLayer              2 methods, 1 internal, 0 external
           -> small sealed clump

  unit_20: MySQLAdapter         1 method, 0 internal, 0 external
           -> singleton (trivially sealed)

OPEN CLUMPS (is_closed=0 — still attracting):
  unit_2:  ErrorCapture+ErrorScanner   9 methods, 5 internal, 12 external
           -> still reaching out (12 external calls = not yet sealed)

  unit_1:  ClassHW+ClassOS+HWLayer+MySQLAdapter+OSLayer+SQLiteAdapter+ZramStorageAdapter
           24 methods, 4 internal, 5 external
           -> MEGA clump forming (7 classes stuck together, subsystem emerging)

  unit_4:  RuntimeGuard          8 methods, 3 internal, 10 external
           -> still reaching out (10 external calls)
```

unit_1 is the most interesting: 7 classes already magnetically stuck
together. That's a SUBSYSTEM forming through attraction. It hasn't
sealed yet because it's still pulling in more methods.

#### The Magnetic Seal

`is_closed` is the magnetic seal. A cluster seals when:
- internal_calls >> external_call_count (attraction >> repulsion)
- The cluster is self-contained (methods call each other, not outward)
- No new methods are being attracted

Before sealing: the cluster is OPEN (still growing, still attracting).
After sealing: the cluster is a COMPUTATIONAL UNIT (closed, named, executable).

#### Existing Magnetic Classes in the Codebase

The codebase already has magnetic-themed classes (from ChatGPT exports
and VBStyle domains):
- MagneticSearchEngine (domain: dom_search)
- MagneticCluster
- MagneticContextWindow
- MagneticHitExtract
- MagneticQuery
- MagneticRadiusTerms
- MagneticRank
- MagneticSearch

These are the seeds of the magnetic clustering system. MagneticCluster
and MagneticRank could become the engine that computes affinity and
ranks method compatibility.

#### Implication for the Reasoning Graph

CUs in the reasoning graph should carry their magnetic provenance:
- Which methods attracted to form this CU
- What was the affinity score that sealed it
- Is the CU still open (attracting more methods) or sealed

This means the graph is not static — it GROWS through magnetic
clustering. New methods enter, attract compatible methods, form
micro-capabilities, seal into CUs, and connect to the graph. The
brain grows organically.

### 7. The MU Execution Engine — Already Built

The `mu_*` tables in `vb_code_test` are a COMPLETE execution engine —
exactly the "Execution Engine" that should be separate from the graph
(Principle 4). It already exists and has been running.

#### What's There

```
mu_nodes (7 nodes):
  GOAL    -> "Build MemUnit cognitive architecture"
    TASK    -> "Design MemUnit schema"
      TASK    -> "Implement CreateNode method" (bcl_method_id=1)
      DECISION -> "Use 3 tables not 10"
      DECISION -> "Uncertainty field never compressed"
      QUESTION -> "MEMORY engine or InnoDB?"
      QUESTION -> "How to serialize graph as narrative?"

mu_edges (5 edges):
  task    DEPENDS  goal     (CERTAIN)
  subtask DEPENDS  task     (CERTAIN)
  decision PRODUCES task    (CERTAIN)
  decision SUPPORTS task    (CERTAIN)
  question BLOCKS   subtask (PROBABLE)

mu_events (44 events):
  NODE_CREATED, TAG_ADDED, EDGE_CREATED
  with before_state / after_state / cause

mu_execution_state:
  active_node, execution_path, open_loops, blocked_by

mu_packets:
  execution tokens flowing through the graph

mu_semantic_tags:
  node -> tag -> confidence_score (cognition:0.95, event-sourcing:0.90)

mu_node_state (14 nodes):
  Live state: node_type, semantic_tag, current_state, confidence,
  uncertainty, version, last_touch
```

#### What This Means

The Execution Engine from Stage 4 is NOT new work. It EXISTS. The `mu_*`
tables are a running execution engine with:
- Goal/Tasks/Decisions/Questions (node types with hierarchy)
- DEPENDS/PRODUCES/SUPPORTS/BLOCKS (edge types with certainty)
- Event log (before/after state, cause — full audit trail)
- Execution state (active node, open loops, blocked by)
- Semantic tags (with confidence scores)
- Packets (execution tokens)
- Node state (versioned, with uncertainty preserved)

Stage 4 should WIRE INTO this existing engine, not build a new one.

### 8. The Call Graph — 4,147 Behavioral Edges

`bcl_edges` has 4,147 method-to-method call edges with certainty:

```
HWLayer.Run -> self.snapshot           (CALL, CERTAIN)
HWLayer.snapshot -> psutil.virtual_mem (CALL, PROBABLE)
HWLayer.snapshot -> psutil.disk_usage  (CALL, PROBABLE)
```

This is the **behavioral affinity** data for magnetic clustering —
which methods call which, with certainty levels (CERTAIN/PROBABLE).

### 9. The Unit Dependency Graph — CU to CU

`bcl_unit_deps` connects units to units:

```
unit_5  -> unit_1   (unit_5 depends on unit_1)
unit_13 -> unit_14
unit_16 -> unit_17, unit_19
```

This is the **subsystem level** — CUs connecting to CUs. This is how
clumps connect to form bigger clumps (the hierarchical emergence).

### 10. The Architectural Graph — Domain Level

`class_graph` (36 edges) shows architectural relationships:

```
AST       validates_for      BracketParser
AST       feeds_structure_to ClassDB
Bootstrap boots_into         Config
BracketParser produces       Brackets
Brackets  complements        AST
ClassDB   provides_capabilities_to Orchestration
```

This is the **domain level** — higher than methods, higher than CUs.
It shows how classes relate architecturally.

### 11. The Saved Brain State — 148 Learned Weights

`neural_brain_state` has 148 saved edge weights from previous sessions:

```
action:BUILD|interrogative:HOW  = 0.057
action:BUILD|interrogative:WHAT = 0.085
action:BUILD|interrogative:WHY  = 0.009
action:BUILD|modifier:FIRST     = 0.012
```

This is the **Save/Load Brain** feature data — learned weights from
the inquiry basis, persisted across sessions.

### 12. Magnetic Memory Objects

`memory_objects` has `mode="magnetic"` as the DEFAULT mode, with:

```
query_key, query_text, mode="magnetic", radius=200,
packet (JSON), provenance (JSON), graph_edges (JSON),
decay_score, importance_weight, version, access_count
```

Magnetic memory with decay and importance weighting. This is the
memory layer that remembers magnetic search results.

### 13. Anti-Collapse Hypothesis Tracking — Scientific Reasoning

`anti_collapse_hypotheses` tracks scientific falsification:

```
"The .pb encryption key is server-provided"  -> FALSIFIED (0.85)
"The .pb encryption key is statically embedded" -> CONFIRMED (1.00)
```

States: ASSUMED -> TESTING -> UNCONFIRMED -> CONFIRMED | FALSIFIED
Fields: confidence, evidence_channels_checked, falsification_attempted,
falsification_result

This is **scientific reasoning** — hypotheses with falsification. Not
just "is this true?" but "has anyone TRIED to prove it false?"

### 14. Learned Lessons — 240 Code Review Lessons

`know_lessons` has 240 lessons from code review:

```
file: evidence_classifier_vbstyle.py
dimension: error_handling
issue_type: generic_exception
severity: 2
description: "Generic except clause catches all exceptions"
suggested_fix: (present)
code_snapshot: (present)
iteration: 1
confirmed: 0/1
```

This is **learning from mistakes** — each lesson has a suggested fix
and can be confirmed or unconfirmed.

### 15. BCL Stamps — Provenance Tracing

`bcl_stamps` tracks every BCL operation with full provenance:

```
trace_id, goal, intent, source_nodes, changes_applied,
rejected_paths, event_refs, mu_node_id, stamp_status
```

This is the **audit trail** — every BCL operation records what it
intended, what it changed, what it rejected, and which MU node
triggered it.

### 16. Token Links — Cross-Table Graph

`token_links` (37 rows) connects tokens across tables:

```
source_table -> source_token -> link_type -> target_table -> target_token
weight, hit_count
```

This is the **cross-table connector** — tokens in one table linked
to tokens in another, with weights and hit counts.

---

## The Full Connection Map

```
                    Inquiry Basis (62 atoms, 88 cells)
                    + neural_brain_state (148 learned weights)
                              |
                              v
                    Activation Spreading
                              |
              +---------------+---------------+
              v               v               v
          Structure       Semantics       Topology
          (BCLIR)          (BCL)         (Graph)
         60 classes      30 rules      140 nodes
        125 methods      90 edges      200 edges
              |               |               |
              v               v               v
          bcl_edges       know_lessons    class_graph
        (4,147 calls)    (240 lessons)    (36 arch)
              |               |               |
              +-------+-------+-------+-------+
                      v               v
               Magnetic          bcl_units
               Clustering       (24 units,
               (emergence)       is_closed)
                      |               |
                      v               v
               Computational      bcl_unit_deps
               Units (CUs)       (CU -> CU)
                      |
                      v
               MU Execution Engine (ALREADY BUILT)
               mu_nodes: GOAL/TASK/DECISION/QUESTION
               mu_edges: DEPENDS/PRODUCES/SUPPORTS/BLOCKS
               mu_events: before/after/cause
               mu_execution_state: active_node/open_loops/blocked_by
               mu_packets: execution tokens
               mu_semantic_tags: tag + confidence
                      |
                      v
               Policy Layer (PLANNED)
               allowed / confirm / denied
                      |
                      v
               Execution -> New Evidence
                      |
              +-------+-------+-------+
              v               v               v
          know_lessons    memory_objects   anti_collapse
          (learning)      (magnetic mem)   (hypotheses)
          240 entries     mode=magnetic    FALSIFIED/CONFIRMED
                          decay_score      falsification
                          importance
                      |
                      v
               bcl_stamps (provenance)
               trace_id, goal, intent, changes, rejected
                      |
                      v
               token_links (cross-table)
               37 links, weight, hit_count
                      |
                      v
               system_evolution (4 versions)
               features, capabilities, next_steps
```

### What This Changes in the Plan

| Stage | Original Plan | Revised (with existing parts) |
|---|---|---|
| Stage 3 | Build CU executor from scratch | Wire into existing computational_units + bcl_edges (4,147 calls) |
| Stage 3.5 | Build policy engine from scratch | Still needed — no policy table exists yet |
| Stage 4 | Build execution engine from scratch | **WIRE INTO existing mu_* tables** — already has nodes, edges, events, state, packets |
| Stage 4 | Build graph from scratch | **USE existing class_graph (36), bcl_edges (4,147), bcl_unit_deps** |
| Stage 5 | Wire all knowledge | ADD: know_lessons (240), anti_collapse_hypotheses, memory_objects, bcl_stamps, token_links, system_evolution |
| Brain state | Build save/load | **USE existing neural_brain_state (148 weights)** |
| Magnetic | Build from scratch | **USE existing bcl_units (is_closed), bcl_edges (certainty), memory_objects (mode=magnetic)** |

The system is much more built than I thought. Stage 4's "Execution Engine"
is not new construction — it's WIRING INTO the existing mu_* engine.

---

## Current State (Stage 1 — COMPLETE)

### Architecture

```
           Source Code (MySQL)
                |
                v
             BCLIR
        (60 classes + 125 methods)
                |
      +---------+---------+
      v                   v
   BCL Units         Semantic Graph
 (30 rules           (140 nodes
  +90 edges)         +200 edges)
      |                   |
      +---------+---------+
                v
        Inquiry Basis (62 atoms -> 88 cells)
                |
                v
        Activation Spreading = Reasoning
                |
                v
        VBStyle Output
```

### What Is Wired

| Layer | Source | Nodes | Edges | Color |
|---|---|---|---|---|
| Inquiry Basis | 62 semantic atoms | 62 | 1,587 (co-occurrence) | Purple/blue |
| BCLIR Classes | vb_code_test.vb_classes | 60 | 125 (contains) | Blue |
| BCLIR Methods | vb_code_test.vb_methods | 125 | (linked to classes) | Dark blue |
| BCL Rules | vb_shared.rules | 30 | 90 (governs) | Gold |
| Graph Topology | code_co_occurrence | 140 | 200 (co-occurrence) | Green |
| Cross-layer | keyword matching | - | 149 (inquiry->class) | Purple |

**Total: 417 nodes, 2,151 edges, 149 cross-layer connections**

### What Each Layer Answers

| Question | Layer | Example |
|---|---|---|
| "What code exists?" | BCLIR | 60 classes, 125 methods |
| "What does it mean?" | BCL | 30 rules, 90 governance edges |
| "How does it connect?" | Graph | 140 nodes, 200 co-occurrence edges |
| "What questions CAN I ask?" | Inquiry | 62 atoms, 88 cells, 11x8 matrix |
| "Why did X activate?" | Cross-layer | keyword match + weight + edge trace |

### Proven Behavior

Click WHY in the 3D graph:
1. Inquiry: WHY -> {PERSON}, {THING}, CAUSE (semantic neighbors)
2. Cross-layer: WHY -> ErrorCapture, ErrorScanner, ErrorReport (keyword "error")
3. BCLIR: ErrorCapture -> Run, capture, scan (class->method edges)
4. BCL: "Strict Tuple3 return pattern" rule fires (governs those classes)
5. Graph: Co-occurring error-handling nodes fire (topology)

One click. Five layers. All simultaneous.

### Features Implemented

| Feature | Toolbar Button | What It Does |
|---|---|---|
| Activation spreading | Click node | Fires node + spreads to neighbors |
| Hebbian learning | Train | Strengthens co-activated edges |
| Wave dynamics | Wave Mode | Pulses travel along edges over time |
| Backpropagation | Backprop | Dijkstra finds strongest path (right-click = target) |
| Fact graph | Fact Graph | Facts feed activation into question nodes |
| Growth simulation | Grow | Dormant holes become real edges |
| Save/Load brain | Save/Load Brain | Persist weights to MySQL |
| Layer loading | Load Layers | Wire BCLIR + BCL + Graph into neural graph |
| Layer info | ? | Show layer statistics |

### File

`/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Gui/QuestionSpaceExplorerV2.py`

---

## Stage 2 — Evidence-Provenance Confidence (PLANNED)

### Problem

Current activation spreading is binary — a node is either active or not.
Real reasoning requires confidence: "How certain are we that ErrorCapture
is relevant to WHY?" And critically — the confidence must preserve WHICH
evidence source contributed what. A single collapsed number loses
debuggability.

### Principle

Confidence is a VECTOR, not a scalar. Four independent evidence streams,
each preserved with its source. The overall confidence is computed from
them but the individual streams are NEVER discarded.

### What Already Exists in MySQL

| Stream | Source | Field | Range | Meaning |
|---|---|---|---|---|
| structural | code_index | authority_score | 1-10 | Fact authority (normalize /10) |
| structural | code_index | survival_score | 0.3-0.95 | Versioned survival |
| semantic | know_nodes | confidence | 0.0-1.0 | Q&A confidence |
| semantic | know_answers | confidence | 0.85-0.95 | Answer reliability |
| topological | code_co_occurrence | weight | 0-1 | Co-occurrence strength |
| runtime | know_memory_units | stability_score | 0.0-1.0 | Memory stability over time |

### Design

Each node carries an `evidence` dict, NOT a single confidence field:

```python
node["evidence"] = {
    "structural":  1.00,   # from BCLIR authority_score / 10
    "semantic":    0.73,   # from know_answers confidence
    "topological": 0.92,   # from code_index survival_score
    "runtime":     0.61,   # from know_memory_units stability_score
}
node["confidence"] = weighted_average(evidence)  # computed, not stored
```

When activation spreads, evidence propagates per-stream:

```
WHY (activation=1.0, evidence={structural:1.0, semantic:1.0, ...})
  |
  v
ErrorCapture
  Evidence (from MySQL):
    structural  = 1.00   (authority_score=10 / 10)
    semantic    = 0.73   (know_answers confidence=0.73)
    topological = 0.92   (survival_score=0.92)
    runtime     = 0.61   (stability_score=0.61)
  Confidence = 0.81      (weighted average, computed)
  |
  v
Run (method of ErrorCapture)
  Inherits per-stream:
    structural  = 1.00 * edge_weight(0.8) = 0.80
    semantic    = 0.73 * edge_weight(0.8) = 0.58
    topological = 0.92 * edge_weight(0.8) = 0.74
    runtime     = 0.61 * edge_weight(0.8) = 0.49
  Confidence = 0.65
```

### Why Provenance Matters

When you ask "Why is confidence only 0.65?" you can see:
```
  structural  = 0.80  (strong — class exists)
  semantic    = 0.58  (moderate — rule partially applies)
  topological = 0.74  (strong — survived versions)
  runtime     = 0.49  (WEAK — low stability)
  -> Runtime evidence is the weak link
```

Instead of a mystery number, you get a diagnosis.

### Implementation Plan

1. Add `evidence` dict to every node: {structural, semantic, topological, runtime}
2. Add `confidence` as a COMPUTED property (not stored) = weighted_average(evidence)
3. Load evidence from MySQL in OnLoadLayers:
   - BCLIR classes: structural = authority_score/10, topological = survival_score
   - BCL rules: semantic = survival_score
   - Graph nodes: topological = survival_score
   - Know nodes: semantic = confidence field
   - Memory units: runtime = stability_score
4. Modify Activate() to propagate evidence per-stream:
   - Each stream decays independently: `target[stream] = source[stream] * edge_weight`
   - Overall confidence = weighted_average (weights configurable)
5. Add evidence display in HUD:
   ```
   ErrorCapture [act=0.92 conf=0.81]
     struct=1.00  sem=0.73  topo=0.92  rt=0.61
   ```
6. Add "Explain" button — shows full evidence chain with per-stream breakdown
7. Confidence-weighted backprop: path cost = 1/(weight * confidence)
8. Visual: node glow = activation, node border thickness = confidence,
   border color = weakest evidence stream (red=weak, green=strong)

### Files to Modify

- `QuestionSpaceExplorerV2.py` — Activate(), _Tick(), paintEvent, OnLoadLayers

---

## Stage 3 — Executable Computational Units as Verbs (PLANNED)

### Problem

Current CUs are nodes — they light up but don't DO anything.
A CU should be callable: activating CU_ErrorCapture should be able to
actually capture an error. CUs are verbs, not nouns. They are operators
that transform state, not facts that store it.

### Noun/Verb Distinction

```
NOUNS (graph nodes that store facts):
  ErrorCapture, Run, read_state, "Tuple3 return pattern", know_problems

VERBS (CUs that transform state):
  CU_Think, CU_Ask, CU_Learn, CU_Validate, CU_ErrorCapture,
  CU_Generate, CU_Arbitrate, CU_Embed, CU_GraphReason
```

Activation flows through nouns until it reaches a verb. At the verb,
reasoning becomes action:

```
WHY (noun: inquiry operator)
  |
  v
ErrorCapture (noun: BCLIR class — "this exists")
  |
  v
CU_ErrorCapture (verb: computational unit — "this does")
  |
  v
Execute()  -->  transforms state  -->  new evidence
```

### What Already Exists

33 computational units in CODEBASE.computational_units — all verbs:

| CU | Verb | What it does |
|---|---|---|
| CU_Bootstrap | init | Init + load knowledge + embedder + LLM |
| CU_ClassLoader | load | Load class from code_classes via exec |
| CU_AuthorityDispatch | dispatch | Authority instantiation + safe delegate |
| CU_ErrorCapture | capture | Get error capture + capture exceptions |
| CU_QNARetrieval | query | Query QNA + reason with QNA |
| CU_EventSystem | emit | Register handlers + emit + score priority |
| CU_Arbitration | arbitrate | Arbitrate competing events into branches |
| CU_AttractorCollapse | detect | Detect collapse + inject orthogonal |
| CU_EventDrain | drain | Drain event queue with multi-branch |
| CU_Think | think | Single-think reasoning pipeline |
| CU_Generate | generate | Generate LLM response |
| CU_Learn | learn | Learn knowledge into DB |
| CU_Embed | embed | Embed text + retrieve context |
| CU_GraphBuild | build | ReasoningGraph: add_node + add_edge |
| CU_GraphReason | reason | Reason all angles + graph reason |
| CU_GraphLearn | improve | learn_answer + improve_confidence |
| CU_Sensory | sense | Score salience + chain thought + dream |
| CU_MemUnit | bus | CORE_MEMUNIT: shared memory bus |
| CU_Ask | ask | Ask + direct answer + rules + context |
| CU_Validation | validate | Check rule + validate operation |
| + 13 more | | |

### Design

```
Click WHY
  |
  v
ErrorCapture activates (noun: fact, activation=0.92)
  |
  v
CU_ErrorCapture activates (verb: behavior, activation=0.85)
  |
  v
  Is activation > EXEC_THRESHOLD (0.7)?
    YES -> Policy check (Stage 3.5)
      -> If permitted: CU_ErrorCapture.Execute()
         -> Calls ErrorCapture.Run("capture", {})
         -> Returns (1, {errors_captured: 3}, None)
         -> Result feeds back into graph as new evidence
      -> If denied: activation stops, logged
    NO  -> Just lights up (current behavior)
```

### Implementation Plan

1. Load 33 CUs as nodes with layer="comp_unit" and kind="verb"
2. Wire CU -> BCLIR class edges (CU_ErrorCapture -> ErrorCapture class)
3. Create `CuExecutor.py` — VBStyle class that safely invokes CUs:
   - Import the actual Python class by name
   - Instantiate with (mem, db, param)
   - Call Run(command, params)
   - Capture Tuple3 result: (1, data, None) or (0, None, error)
   - Feed result back into graph as new evidence (updates runtime stream)
4. Add EXEC_THRESHOLD slider to toolbar (default 0.7)
5. Add "Execute Mode" toggle — when ON, high-activation CUs can execute
6. Double-click CU node to execute (requires Execute Mode ON + policy check)
7. Log execution results in info panel:
   ```
   EXECUTE: CU_ErrorCapture (verb)
     -> ErrorCapture.Run("capture", {})
     -> (1, {errors_captured: 3}, None)
     -> Feeding back: runtime evidence +0.15 for ErrorCapture
     -> New facts: 3 errors added to know_problems
   ```
8. Safety: execution requires explicit user enable (Execute Mode toggle)
   PLUS policy check (Stage 3.5)

### Risk

- Executing arbitrary code from graph activation is dangerous
- Need sandbox/guard: only execute when user explicitly enables
- CU_Execute should require double-click + Execute Mode ON + policy pass
- CU class may not be importable — handle ImportError gracefully
- Execution may have side effects — dry-run mode for testing

### Files to Modify

- `QuestionSpaceExplorerV2.py` — OnLoadLayers (add CUs as verbs), new OnExecute
- New: `CuExecutor.py` — VBStyle class that safely invokes CUs

---

## Stage 3.5 — Policy Layer: Capability vs Permission (PLANNED)

### Problem

Without a policy layer, any sufficiently activated CU would execute.
That's dangerous. CU_DeleteFiles could delete files. CU_Generate could
call an LLM. Capability ("I can") must be separated from permission
("You may").

### Principle

Policies answer: "Should this execute?"

They are separate from capability. A CU may be highly activated and
fully capable, but if policy says "denied," execution stops.

```
Question: "Delete old files?"
  |
  v
Activate CU_DeleteFiles (capability: yes, activation: 0.85)
  |
  v
Policy check:
    permission = denied   (safety policy blocks destructive ops)
  |
  v
Result: activation stops, execution denied, logged
```

### Design

Three permission levels:

```python
POLICIES = {
    # allowed: execute immediately when activation > threshold
    "CU_ErrorCapture":  {"permission": "allowed", "reason": "safe, read-only"},
    "CU_QNARetrieval":  {"permission": "allowed", "reason": "read-only query"},
    "CU_GraphReason":   {"permission": "allowed", "reason": "reasoning only"},
    "CU_Sensory":       {"permission": "allowed", "reason": "observation only"},

    # confirm: ask user before executing (popup dialog)
    "CU_Generate":      {"permission": "confirm", "reason": "calls LLM, costs tokens"},
    "CU_Learn":         {"permission": "confirm", "reason": "writes to DB"},
    "CU_ClassLoader":   {"permission": "confirm", "reason": "executes arbitrary code"},
    "CU_Ask":           {"permission": "confirm", "reason": "calls LLM"},
    "CU_Embed":         {"permission": "confirm", "reason": "compute intensive"},

    # denied: never execute, log the denial with reason
    "CU_DeleteFiles":   {"permission": "denied",  "reason": "destructive operation"},
    "CU_Autonomous":    {"permission": "denied",  "reason": "autonomous loop, unsafe"},
    "CU_Bootstrap":     {"permission": "denied",  "reason": "system init, manual only"},
}
```

### Implementation Plan

1. Create `PolicyEngine.py` — VBStyle class:
   - Run("check", {"cu_name": "CU_ErrorCapture"}) -> (1, {permission, reason}, None)
   - Run("list", {}) -> all policies
   - Run("set", {"cu_name": "...", "permission": "..."}) -> update policy
   - Run("read_state", {}) / Run("set_config", {})
2. Default policies loaded from a config dict (not hardcoded in CUs)
3. Before any CU executes, call PolicyEngine.Run("check", ...)
4. If "confirm" -> show QInputDialog asking user to approve
5. If "denied" -> log denial, stop execution
6. If "allowed" -> proceed to Execute()
7. Add "Policies" toolbar button -> shows all CU permissions, editable
8. Policy decisions logged in info panel:
   ```
   POLICY CHECK: CU_DeleteFiles
     -> permission = denied
     -> reason: destructive operation
     -> execution blocked
   ```

### Files to Create

- `PolicyEngine.py` — VBStyle class, policy check + management

### Files to Modify

- `QuestionSpaceExplorerV2.py` — wire PolicyEngine into execution path
- `CuExecutor.py` — call PolicyEngine before executing any CU

---

## Stage 4 — Common Node Interface + Graph/Execution Separation (PLANNED)

### Problem

Nodes are currently plain dicts. Every node — regardless of layer — should
have the same VBStyle contract. Additionally, the graph (knowledge) and
the execution engine (actor) must be kept separate for debuggability.

### Principle: Graph vs Execution Engine

- **Graph** answers: "What is connected?" (knowledge substrate)
- **Execution Engine** answers: "What happens next?" (interpreter)

The graph is the knowledge. The execution engine reads the graph, follows
activation, checks policies, and invokes CUs. This separation means:
- Graph can be inspected without executing anything
- Execution engine can be tested with a fixed graph
- Graph can grow without changing the executor
- Executor can be swapped without touching the graph

### Design: Common Node Interface

Every node becomes a VBStyle-compliant object with the same interface:

```python
class ReasoningNode:
    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "id": "",
            "label": "",
            "type": "",
            "kind": "",            # noun|verb
            "layer": "",           # inquiry|bclir_class|bcl_rule|graph|comp_unit|...
            "activation": 0.0,
            "evidence": {          # per-stream provenance (Stage 2)
                "structural": 0.0,
                "semantic": 0.0,
                "topological": 0.0,
                "runtime": 0.0,
            },
            "connections": [],     # [(neighbor_id, weight, dimension)]
        }

    def Run(self, command, params=None):
        # Dispatch: activate|execute|explain|read_state|set_config
        if command == "activate":
            return self._Activate(params)
        elif command == "execute":
            return self._Execute(params)
        elif command == "explain":
            return self._Explain(params)

    def _Activate(self, params):
        strength = params.get("strength", 1.0)
        self.state["activation"] = min(1.0, self.state["activation"] + strength)
        return (1, {"activation": self.state["activation"]}, None)

    def _Explain(self, params):
        # Return WHY this node is active — full evidence chain
        return (1, {
            "activation": self.state["activation"],
            "evidence": self.state["evidence"],
            "confidence": self._Confidence(),
            "connections": self.state["connections"],
        }, None)

    def _Execute(self, params):
        # Nouns: not executable. Verbs: override this.
        return (1, {"executed": False, "reason": "noun node, not executable"}, None)

    def _Confidence(self):
        # Computed from evidence, never stored
        e = self.state["evidence"]
        return (e["structural"] + e["semantic"] + e["topological"] + e["runtime"]) / 4

    def read_state(self):
        return (1, dict(self.state), None)

    def set_config(self, values):
        self.state.update(values)
        return (1, True, None)
```

### Design: Graph vs Execution Engine

```
ReasoningGraph (knowledge substrate):
  - Holds nodes as ReasoningNode objects
  - Holds edges as ReasoningEdge objects
  - Activate(node_id) -> calls node.Run("activate", {})
  - Spread() -> propagates activation across edges
  - Explain(node_id) -> calls node.Run("explain", {})
  - NO execution logic here

ExecutionEngine (interpreter/actor):
  - Reads graph state
  - Finds CUs with activation > EXEC_THRESHOLD
  - Calls PolicyEngine.Run("check", ...) for each
  - If permitted: calls CuExecutor.Run("execute", ...)
  - Feeds results back into graph as new evidence
  - NO graph structure logic here
```

### Implementation Plan

1. Create `ReasoningNode.py` — VBStyle base class (nouns)
2. Create `CompUnitNode.py` — extends ReasoningNode with real Execute() (verbs)
3. Create `ReasoningEdge.py` — VBStyle edge with weight, evidence, dimension
4. Create `ReasoningGraph.py` — graph manager (knowledge substrate only):
   - Holds nodes as ReasoningNode objects
   - Activate(node_id) -> calls node.Run("activate", {})
   - Spread() -> propagates activation + evidence across edges
   - Explain(node_id) -> calls node.Run("explain", {})
   - NO execution logic
5. Create `ExecutionEngine.py` — VBStyle class (interpreter/actor):
   - Reads graph state
   - Finds CUs above threshold
   - Calls PolicyEngine for permission
   - Calls CuExecutor for execution
   - Feeds results back as new evidence
   - NO graph structure logic
6. Refactor QuestionSpaceExplorerV2.py:
   - Replace dict-based state with ReasoningGraph
   - Wire ExecutionEngine for CU execution
   - Add "Explain" button -> node.Run("explain", {}) -> full evidence chain
7. Every node is polymorphic: Activate(), Explain(), Run(), ReadState()

### Files to Create

- `ReasoningNode.py` — base node class (nouns)
- `CompUnitNode.py` — executable CU node (verbs)
- `ReasoningEdge.py` — edge class with evidence
- `ReasoningGraph.py` — graph manager (knowledge substrate)
- `ExecutionEngine.py` — interpreter/actor (separate from graph)

### Files to Modify

- `QuestionSpaceExplorerV2.py` — use ReasoningGraph + ExecutionEngine

---

## Stage 5 — Full Brain Wiring (PLANNED)

### Problem

417 nodes is a start. The full brain has ~2,500+ nodes and ~37,000+ edges
available in MySQL. Wiring them all creates a real-scale reasoning graph.

### What Can Be Wired

| Layer | Source | Nodes | Edges |
|---|---|---|---|
| Computational Units | CODEBASE.computational_units | 33 | CU->class |
| BCL Units | vb_code_test.bcl_units | 24 | unit->class |
| Method Inventory | method_inventory | 173 | method->authority |
| Knowledge Q-Nodes | know_nodes | 1,694 | 1,516 (refines/depends/contradicts) |
| Knowledge Answers | know_answers | 32,741 | answer->question |
| Knowledge Questions | know_questions | 108,037 | question->subject |
| Memory Units | know_memory_units | 16 | (stability-scored) |
| Known Problems | know_problems | 399 | problem->solution |
| Known Solutions | know_solutions | 381 | solution->fix |
| Component Ontology | component_ontology | 19 | component->role |
| Session Graph | graph_nodes + graph_edges | 50 | 33,775 |
| MU Execution | mu_nodes + mu_edges | 7 | 5 (BLOCKS/DEPENDS/PRODUCES) |
| Inference Rules | inference_rules | 11 | rule->conclusion |
| Decision Trees | decision_trees | 9 | tree->decision |

**If all wired: ~2,500 nodes (curated), ~37,000+ edges**

Note: know_questions (108K) and know_answers (32K) are too large for
real-time 3D rendering. Curate: load top 200 by confidence, not all 140K.

### Implementation Plan

1. Add curated loading: top N by confidence/authority/stability
2. Wire Computational Units (33 nodes, CU->class edges)
3. Wire BCL Units (24 nodes, unit->class edges)
4. Wire Method Inventory (173 nodes, method->authority edges)
5. Wire Knowledge Graph (200 curated Q-nodes, 1,516 edges)
6. Wire Memory Units (16 nodes with stability_score as confidence)
7. Wire Problems/Solutions (399+381 nodes, problem->solution edges)
8. Wire Component Ontology (19 nodes)
9. Wire Session Graph (50 nodes, top 500 edges by weight)
10. Wire MU Execution (7 nodes, 5 edges)
11. Wire Inference (11 rules, 9 decision trees)
12. Cross-layer activation: inquiry -> CU -> BCLIR -> BCL -> KnowGraph -> Problem -> Solution

### Scaling Concern

- 417 nodes renders fine at 50ms tick
- 2,500 nodes may need spatial clustering (group by layer in 3D space)
- 37,000 edges will need LOD (level of detail) — only render edges near camera
- Consider: layer-zones in 3D (inquiry=center, BCLIR=ring1, BCL=ring2, etc.)

### Files to Modify

- `QuestionSpaceExplorerV2.py` — OnLoadLayers (add all layers)
- New: `LayerLoader.py` — VBStyle class that loads all layers from MySQL

---

## Stage Summary

| Stage | Status | Nodes | Edges | Key Feature |
|---|---|---|---|---|
| 1. Three-layer wiring | COMPLETE | 417 | 2,151 | BCLIR + BCL + Graph + cross-layer |
| 2. Evidence-provenance confidence | PLANNED | 417 | 2,151 | 4-stream evidence vector, never collapsed |
| 3. Executable CUs as verbs | PLANNED | 450 | 2,200 | CUs are verbs (operators), not nouns (facts) |
| 3.5. Policy layer | PLANNED | 450 | 2,200 | Capability vs permission (allowed/confirm/denied) |
| 4. Common node interface + graph/exec separation | PLANNED | 450 | 2,200 | VBStyle nodes + separate ExecutionEngine |
| 5. Full brain wiring | PLANNED | 2,500 | 37,000 | All MySQL knowledge wired |

---

## The Direction

"Everything is a node.
Every node has meaning.
Every node can activate.
Some nodes can execute.
Some nodes remember.
Some nodes reason.
Some nodes create new nodes."

Stage 1 proves the first three lines (everything is a node, has meaning, activates).
Stage 2 adds evidence-provenance confidence (how certain, with per-stream diagnosis).
Stage 3 proves the fourth line (some nodes execute — verbs, not nouns).
Stage 3.5 adds the guardrail (policies decide whether execution is permitted).
Stage 4 makes it architecturally coherent (common interface + graph/exec separation).
Stage 5 makes it real-scale (all MySQL knowledge wired).

The 7-step reasoning loop closes:
1. Question chooses an inquiry operator
2. Operator activates relevant graph regions
3. Multiple evidence layers contribute independently
4. Confidence is aggregated while preserving provenance
5. Activation reaches Computational Units (verbs)
6. Policies determine whether execution is permitted
7. Execution produces new facts, memories, or graph updates

Each stage remains inspectable. You can see not only the answer but
exactly how it arrived there and why it chose to act.

---

## Glossary

- **BCLIR** — Behavioral Code Intermediate Representation. Structural truth:
  classes, methods, signatures, AST. Source: vb_code_test.vb_classes + vb_methods.
- **BCL** — Behavioral Code Layer. Semantic meaning: what a unit is
  responsible for, what public surface it exposes, what authority it has.
  Source: vb_shared.rules, governance, learned_rules.
- **Graph** — Topology layer: dependencies, co-occurrence, authority flow.
  Source: code_co_occurrence, code_index, graph_nodes, graph_edges.
- **CU** — Computational Unit. Runtime behavior: what the system DOES.
  CUs are VERBS (operators), not nouns (facts). Source: CODEBASE.computational_units.
- **Inquiry Basis** — 62 semantic atoms (11 interrogatives x 6 slots + values)
  forming an 88-cell matrix. The reasoning engine that generates questions.
- **Explicit Reasoning Graph** — The correct term for this system. NOT a
  neural network. Knowledge is explicit, inspectable, explainable, traceable.
- **Nouns vs Verbs** — Nouns are graph nodes that store facts (classes, methods,
  rules, problems). Verbs are CUs that transform state (think, learn, capture,
  generate). Activation flows through nouns until it reaches a verb.
- **Evidence Provenance** — Confidence is a VECTOR of 4 independent streams
  (structural, semantic, topological, runtime), each preserved with its source.
  The overall confidence is computed but the individual streams are never
  discarded. This enables diagnosis: "Why is confidence low?" -> "Runtime
  evidence is the weak link."
- **Capability vs Permission** — Capability ("I can") is whether a CU has the
  ability to execute. Permission ("You may") is whether policy allows it.
  These are separate concerns, handled by separate layers.
- **Policy Layer** — Guardrail between reasoning and action. Three levels:
  allowed (execute immediately), confirm (ask user), denied (never execute).
  Prevents dangerous CUs from executing even when highly activated.
- **Graph vs Execution Engine** — The graph is the knowledge substrate
  ("what is connected?"). The execution engine is the interpreter ("what
  happens next?"). Kept separate for debuggability and evolvability.
- **Activation Spreading** — The reasoning mechanism. Click a node, it fires,
  activation propagates to neighbors via weighted edges. Like a thought
  spreading through a brain, but fully traceable.
- **Cross-layer edges** — Connections between layers (e.g., inquiry->BCLIR).
  These are what make the system multi-representational: activation doesn't
  just spread within one layer, it crosses to other representations.
- **7-Step Reasoning Loop** — question -> operator -> activation -> evidence
  -> confidence -> CU -> policy -> execution -> learning. Closes the loop
  from asking to acting to learning. Each stage inspectable.
- **Magnetic Clustering** — How CUs form. Methods have magnetic signatures
  (4-affinity vectors). Compatible methods attract and snap together into
  clusters. When a cluster seals (internal_calls >> external_calls), it
  becomes a Computational Unit. CUs EMERGE, they are not declared.
- **Magnetic Signature** — A 4-affinity vector for each method: structural
  (params compatibility), behavioral (called together), semantic (same
  domain/role), historical (survived versions together). Parallel to
  evidence provenance — 4 streams, never collapsed.
- **Magnetic Seal** — When a cluster's internal_calls >> external_call_count,
  the cluster is sealed (is_closed=1). Before sealing: open (still attracting).
  After sealing: Computational Unit (closed, named, executable).
- **Emergence** — CUs are discovered, not declared. The system finds:
  "These 9 methods always travel together. They share inputs, outputs,
  authority. They call one another. Therefore they emerge as one CU."
- **Hierarchical Clustering** — Method -> Micro capability -> CU -> Subsystem
  -> Domain -> Application. Each level forms through magnetic attraction
  at the level below.
