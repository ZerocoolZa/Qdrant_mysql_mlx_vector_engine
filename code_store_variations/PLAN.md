# PLAN — Domain Closure Engine: Candidate → Test → Survive → Promote

## Problem

The current closure engine (`closure_engine.py`) resolves methods by **name matching only**.

```
find method named "connect" → use it → hope it works
```

This is fundamentally broken because:

- A method called `connect` in `dom_network.py` and one called `connect` in `dom_db.py` are completely different things
- Name does not imply correct behavior
- No verification that the method actually does what the domain needs
- A name match is "changing the sticker on a noodle — open it and it's a bomb"

The resolution pipeline (`dom_file → mysql → generator`) picks the first name match and assumes it works. No testing. No ranking. No proof.

---

## What We Already Have

### `efl_brain.db` tables (infrastructure exists, not connected in a loop)

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `execution_log` | Runtime execution records | `success`, `reward`, `error_msg` |
| `unit_rankings` | Method/unit rankings | ranking scores |
| `learned_fixes` | Fix pattern tracking | `success_count`, `failure_count`, `confidence` |
| `diff_results` | Gap tracking | `status`, `priority`, `suggested_action` |
| `expectation_graph` | Behavioral contracts | `purpose`, `expected_returns`, `required_methods` |
| `test_feedback` | Test runner results (NEW) | `domain`, `method_name`, `status`, `error_type` |

### `test_runner.py` (already working)

- `ExecutionSandbox` — isolated namespace, stripped unsafe builtins
- `TestResult` — structured PASS/FAIL/ERROR/SKIP
- `WriteFeedback` — auto-writes results to `efl_brain.db`
- 403 tests, 336 passing, 67 failing

### `efl.py` (already working)

- `cmd_diff` — expectation vs existing gap analysis
- `cmd_feedback` — reads test failures, shows repair priorities
- `cmd_reuse` — find units matching a pattern
- `cmd_assemble` — assemble pipelines from proven units

---

## The Model: Candidate → Test → Survive → Promote

### 1. Discovery (find candidates, not matches)

Instead of searching by name, search by **behavioral contract**:

- What signature does it need? (params, return type)
- What domain context? (db vs network vs io)
- What should it do? (the `expectation_graph` already has this — purpose, expected_returns)

Instead of "find method named `connect`", it's:

> "Find all methods that claim to connect to something and return Tuple3"

### 2. Sandbox Testing (prove it works)

Each candidate gets run through `ExecutionSandbox`:

- Does it return `(1, data, None)`?
- Does it handle edge cases?
- Does it crash?

No assumptions. Run it. Prove it.

### 3. Survivor Selection (only proven code advances)

- Candidates that pass → **survivors**
- Candidates that fail → **rejected** with error recorded in `test_feedback`

### 4. Ranking (score survivors by quality)

Survivors get scored on:

- **Correctness** — does it return the right Tuple3 shape?
- **Completeness** — does it handle edge cases?
- **Provenance** — where did it come from? (dom file > MySQL > generated)
- **History** — how many times has it succeeded before? (`execution_log.reward`)

### 5. Promotion (best survivor becomes canonical)

Top-ranked survivor gets promoted:

- Stored as the **trusted implementation** for that domain + method
- Next time, it gets picked first
- Lower-ranked survivors remain as fallbacks

### 6. Proof Accumulation (trust grows over time)

- Every successful execution → confidence increases
- Every failure → confidence decreases
- Tracked in `learned_fixes` table (`success_count`, `failure_count`, `confidence`)
- Over time, the system learns which code patterns produce working methods

---

## Three Paths Forward

### Option A — Lightweight (wire reward signals now)

Wire `test_runner.py` results into `execution_log` as reward signals:

- Pass = +1 reward
- Fail = -1 reward
- The brain can then rank methods by accumulated reward
- No new architecture, just connect existing tables
- **Effort**: 1-2 hours
- **Value**: immediate feedback loop, data collection starts

### Option B — Medium (candidate selection pipeline)

Change the resolution pipeline from "find by name" to "find all candidates → test each → pick best":

- `resolve_method` becomes: query `efl_brain.db` for all methods matching a behavioral contract
- Run each candidate through `ExecutionSandbox`
- Promote the winner based on test results + historical reward
- **Effort**: 1-2 days
- **Value**: real behavioral verification, no more name-matching bombs

### Option C — Full evolutionary (survivors get promoted system)

Multiple rounds of:

1. Generate candidates (from dom files, MySQL, generator, mutations)
2. Test all candidates in sandbox
3. Survivors mutate/combine
4. Test again
5. Best survives, gets promoted
6. `learned_fixes` tracks which fix patterns work across generations
7. Over time, the system learns which code patterns produce working methods for each domain

- **Effort**: 1-2 weeks
- **Value**: self-improving system, learns from failures, gets better over time

---

## The Core Problem: Lexical Retrieval vs Semantic Verification

The system is doing **lexical retrieval, not semantic verification**.

- It searches by string similarity (name match)
- Not by behavior
- Not by contract
- Not by effect
- Not by proof of correctness

Current flow:

```
NAME → RESULT
```

What we actually want:

```
CONSTRAINTS → CANDIDATES → EXECUTION → SURVIVAL → PROMOTION
```

The system assumes "truth is stored in names". Real systems assume "truth is proven by execution under constraints". That's the shift.

Methods are not "found" — they are "competed for".

---

## Four Upgrade Options (Full Analysis)

### OPTION 1 — Contract-First System

Instead of "find function called `write`", define what `write` MUST DO:

- **input**: file path + data
- **output**: Tuple3 success
- **side effect**: file content changed
- **constraints**: no print, VBStyle safe

The system doesn't care about name first — it checks whether a candidate satisfies the contract.

```
name match → accept    (BROKEN)
behavior match → accept (CORRECT)
```

This is already a huge shift. Simplest conceptual upgrade.

### OPTION 2 — Survivor Model (competition-based)

You don't "choose a method because it matches". You:

1. Collect multiple candidates (from dom files, MySQL, generation)
2. Run them in sandbox
3. Score them
4. Only keep the ones that survive tests

```
candidate pool → execution → scoring → survival selection
```

Not lookup. Competition.

### OPTION 3 — Behavioral Hashing (stronger but heavier)

Instead of method names, define a "behavior fingerprint":

`write(file, data)` might be defined as:
- opens file
- writes bytes
- closes file
- no exception
- returns Tuple3

Every candidate is tested and assigned a "behavior signature". Matching becomes:

```
signature match > name match
```

This removes the "wrong wrapper, right name" problem completely.

### OPTION 4 — Hybrid Search (fix the existing MySQL system, don't throw it away)

Don't throw away the MySQL / 760TB system. Change the retrieval logic:

Instead of "search by `method_name`", do:

> "search by semantic cluster + behavior tags + usage context"

MySQL becomes:
- Not a dictionary
- But a **ranked candidate pool**

Filter using:
- Domain
- Expected IO patterns
- AST structure
- Dependency shape
- Previous success rate

---

## Unified Pipeline (merging all options)

```
1. Define domain closure (what must exist)
2. Retrieve candidates (dom + MySQL + generated)
3. Run all candidates in sandbox
4. Score based on:
   - correctness
   - runtime success
   - contract compliance
5. Rank results
6. Promote survivors into DB as "verified implementations"
```

---

## Key Design Question

Should the system rank and promote methods **purely based on execution survival** (competition model), or should it also **enforce strict behavioral contracts** before anything is allowed to compete?

- **Survival-only**: anything can compete, best execution wins
- **Contract-gated**: must pass contract check before entering competition
- **Hybrid (recommended)**: contract gates entry, then survival ranks among compliant candidates

---

## Recommended Sequence

```
A (now) → B (next) → C (eventually)
```

1. **A first** — start collecting reward data, prove the loop works
2. **B second** — replace name matching with behavioral selection (Option 1 + Option 2)
3. **C third** — add mutation/combination loop for self-improvement (Option 3 + Option 4)

Each step builds on the previous. No throwaway work. The MySQL system stays — it becomes the ranked candidate pool instead of a name dictionary.

---

## Five Additional Architectural Approaches

Ranked by how close they get to "truth = correctness, not label".

### 1. Contract + Specification Verification (strong baseline upgrade)

Every function is validated against a formal spec:

- **inputs**
- **outputs** (Tuple3 contract)
- **side effects allowed**
- **invariants**
- **forbidden behaviors**

Candidates are accepted only if they satisfy the contract.

> "Does it obey the rule?" not "What is it called?"

Cleanest replacement for name-based matching.

### 2. Execution Trace Matching (behavior fingerprinting)

Check what actually happens when it runs, not code structure.

Each method produces a trace:

- file opened → yes
- file written → yes
- exception → no
- return shape → correct

Compare that trace against an expected "ideal trace".

> Matching is based on behavior sequence, not identity.

Kills the "wrong wrapper, correct name" problem.

### 3. Multi-Candidate Ranking (survivor tournament model)

Instead of picking 1 method from MySQL or files:

1. Collect ALL candidates
2. Run them in sandbox
3. Score them

Scoring factors:
- correctness
- stability
- runtime efficiency
- contract compliance

Top score wins. Others are discarded or archived.

> Turns the system into a competition engine.

### 4. Embedding + Semantic Retrieval (meaning-based search)

Instead of searching `method_name == write`, embed meaning:

- "write file safely with error handling"
- "persist bytes to disk"

Search using vector similarity across:
- MySQL code
- dom files
- generated methods

> Replaces names with "intent space".

First step toward true semantic retrieval. (Note: the `Qdrant_mysql_mlx_vector_engine` workspace already has vector search infrastructure.)

### 5. Type-Theory / Interface-Driven System (strict structural correctness)

Define each domain as a type contract system:

```
write :: (Path, Data) → Result(Tuple3)
```

Any method must match:
- input shape
- output shape
- allowed effects

No match = rejected automatically.

> Most rigid but also most reliable system.

---

## Comparison Table

| Approach | What it trusts |
|----------|---------------|
| Name lookup (current) | labels (bad) |
| Contract verification | rules |
| Execution trace matching | behavior |
| Survivor ranking | competition outcome |
| Embedding retrieval | semantic meaning |
| Type system | formal structure |

---

## The Key Insight

Current system assumes:

> "If I find the right word, I found the right function"

All approaches replace that with:

> "Only behavior under execution determines truth"

---

## Strongest Direction

The most powerful modern hybrid is:

**Contract system + execution trace + survivor ranking**

This gives:
- **correctness** (contracts)
- **reality check** (execution)
- **optimization** (ranking)

This replaces the current MySQL + dom lookup entirely with a verified, ranked, proven pipeline.

---

## 6. Live Code Mining (GitHub / Open-Source Retrieval)

GitHub isn't just "another source" — it's a live, external, human-written code universe.

### What it gives you

| Source | Nature |
|--------|--------|
| dom files | your system's known implementations |
| MySQL | stored historical knowledge |
| generator | synthetic guesses |
| GitHub | real-world working implementations |

GitHub becomes the **external reality injection layer**.

### How it fits into the pipeline

Instead of:

```
method_name → dom → mysql → generate
```

You get:

```
method intent → retrieval from multiple universes:
  1. dom files (your system)
  2. MySQL (your memory bank)
  3. generator (fallback brain)
  4. GitHub (real-world truth source)

→ all candidates compete in sandbox execution
```

### Why GitHub is powerful

Solves 3 big problems:

1. **Fake correctness problem** — generator produces something that looks right but is wrong. GitHub gives production-tested patterns, edge-case handling, real usage context.

2. **Coverage gap problem** — domain closure list might miss real-world variants. GitHub fills alternate implementations, idiomatic patterns, language-specific quirks.

3. **Evolution signal** — detect what patterns are common in real code, what APIs people actually use, what fails in practice (via issues/tests).

### Updated pipeline with GitHub

```
Step 1 — Intent: "What does this method need to do?"
Step 2 — Candidate harvest: dom files + MySQL + generator + GitHub search
Step 3 — Normalization: convert all candidates into same interface shape
Step 4 — Sandbox execution: run all candidates
Step 5 — Survival ranking: score on correctness, contract compliance, stability, runtime behavior
Step 6 — Promotion: best candidate becomes canonical
```

### Reality check (critical)

GitHub is powerful but dangerous:

1. **Noise problem** — much code is incomplete, outdated, context-dependent
2. **Overfitting to examples** — might pick "most common code" instead of "correct code"
3. **Dependency blindness** — GitHub code assumes libraries you may not have

**GitHub must NEVER be final authority. It is a candidate generator only.**

### Clean hierarchy including GitHub

```
1. Contract/spec definition (truth rule)
2. Execution sandbox (reality test)
3. Survivor ranking (selection mechanism)

Sources feeding it:
  - dom files (internal truth)
  - MySQL (historical truth)
  - generator (synthetic fallback)
  - GitHub (external real-world truth)
```

---

## Final Insight

What we are actually building is not a "code lookup system".

We are building a **multi-source evolutionary code synthesis engine**.

- dom files = internal truth
- MySQL = historical truth
- generator = synthetic fallback
- GitHub = wild population gene pool

All sources feed into the same survival pipeline. Only proven code survives.

---

## Domain Completeness vs Existing Language Ecosystems

### Do languages already have "VB-style domain libraries"?

Yes — but not in the structured "closure + domain completeness" way we're building. They exist in a more chaotic form.

### Python: std lib + ecosystem modules (closest match)

- `os` → file system / OS domain
- `io` → input/output domain
- `sqlite3` → database domain
- `socket` → networking domain
- `asyncio` → concurrency domain
- `json`, `csv`, `xml` → data transformation domain
- `logging` → observability domain

Python already has domain clusters of functionality. BUT:
- Not enforced as a "complete closure set"
- Not validated or ranked
- Not "truth systems"

They are just toolkits.

### JavaScript / Node.js: domain packages

Same idea, more fragmented:

- `fs` → file system domain
- `http` → network domain
- `crypto` → security domain
- `stream` → IO streaming domain

npm ecosystem expands it massively. BUT:
- No closure guarantee
- No completeness model
- No correctness ranking system

Just modules.

### Java / .NET: enterprise domain libraries

Closer conceptually:

- Spring (Java) → dependency injection + domain services
- Hibernate → database abstraction domain
- .NET `System.IO`, `System.Net`, etc.

Here you start seeing structured "domain layers". BUT still missing:
- No full closure completeness model
- No survivor ranking system
- No multi-source resolution (MySQL + GitHub + generated)

### The important reality

What we're building (the VB system) is NOT standard in any language ecosystem.

**Normal programming languages:**
> "Here are tools grouped by category"

**Our system:**
> "Every domain must be COMPLETE, VERIFIED, and CLOSED under a method set"

That's a mathematical completeness model, not a library system.

### The closest existing ideas

**A. Type systems (Haskell, Rust)** — enforce correctness rules at compile time. But don't enforce domain completeness.

**B. Formal verification systems** — prove correctness mathematically. But very narrow scope, not general code ecosystems.

**C. Search-based software engineering (SBSE)** — closest to the survivor model. Generates many solutions, tests them, selects best. But not structured by domains, not closure-based.

### Key insight (breakthrough moment)

We are not building a library system.

We are building a **closed-world semantic completeness engine**.

That is why:
- name-based lookup feels wrong
- GitHub feels necessary
- survival testing feels right
- MySQL feels like memory
- generators feel like mutation

### The missing piece in all languages

No mainstream language gives you:

- ❌ Domain closure completeness
- ❌ Cross-source candidate fusion (DB + Git + local + generator)
- ❌ Survival-based promotion system
- ❌ Behavioral correctness ranking

The shift we're making:

```
tooling → ecosystem → system-of-truth
```

---

## Domain Induction from Real Code Ecosystems

### The key correction

Standard libraries are not "complete domains". They are:

> practical approximations of domain coverage shaped by engineering needs

- Python `os` ≠ full IO domain
- Java `nio` ≠ full IO domain
- C `stdio.h` ≠ full IO domain

They are partial, curated closures of real-world needs. But that's still extremely valuable.

### What we're actually proposing

```
Step 1 — Take real libraries (C stdlib, Python stdlib, Java SDK, .NET BCL)
Step 2 — Extract structure (functions, classes, modules, signatures, docs, AST)
Step 3 — Understand meaning (embeddings, AST structure, docstrings, call graphs)
Step 4 — Cluster into "domains" (IO cluster, Network cluster, Security cluster)
```

This is **automatic domain induction from real code ecosystems**.

### Embedding Layer (CodeBERT / GraphCodeBERT)

Embedding models convert function names, docstrings, and code bodies into vectors:

```
write_file ≈ store_bytes ≈ persist_data ≈ fwrite
```

This enables semantic grouping, not name-based grouping.

### AST + TreeSitter Layer (critical)

Embeddings alone are not enough. Also need:

- **AST extraction** — function inputs, outputs, imports, side effects
- **TreeSitter** — language-agnostic parsing, structural understanding

This gives: "what does this function DO structurally?" not just "what is it called?"

### The real architecture (6 layers)

```
LAYER 1 — SOURCE COLLECTION
  Python stdlib, C headers, Java SDK, GitHub repos

LAYER 2 — STRUCTURAL PARSING
  AST (function boundaries), TreeSitter (cross-language parsing)

LAYER 3 — SEMANTIC EMBEDDING
  CodeBERT / GraphCodeBERT, function → vector space

LAYER 4 — CLUSTERING
  Group similar functions, form "proto-domains"
  Cluster A → IO, Cluster B → Network, Cluster C → Security

LAYER 5 — DOMAIN INDUCTION
  Derive "this is what IO actually is in real systems"
  Not predefined — empirically learned

LAYER 6 — CLOSURE SYSTEM
  Validate real domain completeness
  Compare against induced real-world domain
  Fill missing gaps
```

### The important shift

Flipping from:

- ❌ **Manually defined closure** (`DOMAIN_CLOSURE` dict)

to:

- ✅ **Empirically learned closure** (from real code ecosystems)

This is a major upgrade.

### What this becomes (in simple terms)

A **"reverse compiler of programming knowledge"**:

- reads all major libraries
- extracts behavior
- builds domain maps
- defines what "complete IO" actually looks like
- then tests our system against it

### Important limitation

No single model (even CodeBERT) "understands domains". What we get is:
- similarity signals
- clustering structure
- probabilistic meaning

Must combine: **embeddings + AST + execution traces** (best signal).

### The strongest version

```
Mine real-world libraries → extract structure → embed semantics
→ cluster domains → define empirical closures
→ use as ground truth for generation + testing
```

### How this connects to existing workspace

The `Qdrant_mysql_mlx_vector_engine` workspace already has:
- Qdrant vector database for semantic search
- MLX embedding infrastructure
- MySQL for historical code storage
- `efl_brain` for code graph + expectations

These are the exact components needed for layers 1-4. The missing piece is the induction pipeline (layers 5-6) that converts mined code into empirical domain closures.

---

## Implementation Spec: Behavioral Validation Layer

### Two problems, clearly separated

1. **Ontology** ("what exists in a domain?") — SOLVED. `DOMAIN_CLOSURE` dict + `expectation_graph` define this.
2. **Truth** ("which implementation is correct?") — BROKEN. This is what we're fixing.

### The missing core: behavioral validation

Every candidate (dom / MySQL / generated / GitHub) must pass:

1. **Contract check** — Tuple3 format, input schema, output schema
2. **Execution test** — run in sandbox, no crash, deterministic output
3. **Property tests** — does `write → read → equals` hold? does `delete → exists == false` hold?
4. **Side-effect correctness** — no forbidden writes, no unexpected state mutation

### Corrected architecture

```
STEP 1 — Retrieve candidates (dom files, MySQL, GitHub, generator)
STEP 2 — Normalize (AST parse, unify signatures, standard wrapper)
STEP 3 — Execute in sandbox (real run, controlled inputs)
STEP 4 — Score behavior (pass/fail, contract match, invariants)
STEP 5 — Survivor selection (highest behavioral score wins)
```

### What already exists

| Component | Status | Location |
|-----------|--------|----------|
| ExecutionSandbox | ✅ working | `test_runner.py` |
| Contract definitions | ✅ exists | `efl_brain.db` `expectation_graph` |
| Feedback loop | ✅ live | `test_runner.py` → `WriteFeedback` → `efl_brain.db` |
| Test results | ✅ 336/403 passing | `code_store.db` `test_results` |
| Learned fixes table | ✅ schema ready | `efl_brain.db` `learned_fixes` |
| Execution log | ✅ schema ready | `efl_brain.db` `execution_log` |

### What needs building

| Component | Priority | Description |
|-----------|----------|-------------|
| `BehavioralValidator` | P0 | Contract check + sandbox execution + scoring |
| `CandidateRetriever` | P0 | Query all sources for candidates matching domain+method |
| `SurvivorRanker` | P0 | Score candidates, promote best, archive rest |
| `PropertyTestEngine` | P1 | Run property-based tests (write→read→equals) |
| `SideEffectChecker` | P1 | Verify no forbidden state mutations |
| `ExecutionTracer` | P2 | Record behavior trace for fingerprinting |

### Implementation plan

#### Phase 1 — BehavioralValidator (replace name matching)

```python
class BehavioralValidator:
    """Validates candidates against contracts via sandbox execution."""

    def Validate(self, candidate_code, method_name, contract):
        """
        Returns (ok, score, detail).
        score = weighted combination of:
          - contract_compliance (0-40): Tuple3 shape, return type
          - execution_success (0-30): no crash, runs to completion
          - edge_case_handling (0-20): empty input, bad params
          - historical_reward (0-10): past success rate from execution_log
        """
```

#### Phase 2 — CandidateRetriever (replace single-source lookup)

```python
class CandidateRetriever:
    """Retrieves all candidates for a domain+method from multiple sources."""

    def Retrieve(self, domain, method):
        """
        Returns list of (code, source, confidence) tuples.
        Sources: dom files, MySQL, efl_brain.db, generator.
        Does NOT pick one — returns ALL candidates for competition.
        """
```

#### Phase 3 — SurvivorRanker (replace first-match acceptance)

```python
class SurvivorRanker:
    """Runs all candidates through validator, promotes best."""

    def Compete(self, candidates, contract):
        """
        Returns (winner, ranked_results).
        winner = highest scoring candidate
        ranked_results = all candidates with scores
        Losers archived in execution_log with failure detail.
        Winner promoted to closure_methods as canonical.
        """
```

### The shift in one sentence

From: **lexical retrieval system** (name-based)
To: **behavioral verification system** (execution-based truth engine)

---

## Phase 3: Domain Extraction Agent Spec

### Purpose

Audit and expand `DOMAIN_CLOSURE` using evidence-based extraction from real sources. Currently `DOMAIN_CLOSURE` is a hand-written dict — likely incomplete. This spec produces structured, traceable domain models.

### Strict VBStyle Domain Agent Prompt

```
Build a DOMAIN CLOSURE SPECIFICATION for: {DOMAIN}

Constraints:
- Only include operations verified from official or documented sources
- Each method must map to a real API/function/system call
- No invented functions allowed
- Output must be structured as a closure set

Return:

DOMAIN_CLOSURE = {
    "core": [],
    "extended": [],
    "control": [],
    "edge": [],
    "sources": []
}

Also return:
- missing_categories[]
- confidence_score (0-1)
```

### Source collection rules

Agent must consult:
- official documentation (primary source)
- standard libraries (Python / C / Java / .NET if applicable)
- OS-level APIs if relevant
- widely used SDK references

Agent must NOT infer or guess missing functions.

### Function extraction rules

Each item must include:
- name
- purpose (short)
- layer (OS / library / network / app)
- source reference

### Domain structure

Organize results into:
- Core primitives
- Extended utilities
- Edge-case / rare operations
- Control / management operations

### Completeness check

Agent must:
- compare against official library index (if available)
- identify missing categories
- explicitly mark gaps as "not found in source"
- NOT fill gaps with assumptions

### Output format

```
DOMAIN: {DOMAIN_NAME}

CORE OPERATIONS
  - ...

EXTENDED OPERATIONS
  - ...

CONTROL / MANAGEMENT
  - ...

EDGE / SPECIAL CASES
  - ...

SOURCE SUMMARY
  - list all sources used

COMPLETENESS STATUS
  - COMPLETE / INCOMPLETE (with missing areas)
```

### What this solves

- ❌ name matching, assumed completeness, guessed domain boundaries
- ✅ evidence-based extraction, structured ontology, explicit gaps, traceable sources

### How to use

Run Devin with this prompt for each of the 58 domains. Compare output against existing `DOMAIN_CLOSURE` dict. Fill gaps with evidence. Update `DOMAIN_CLOSURE` with verified, sourced methods.

### Key insight

We are not building "a method list system". We are building a **verified semantic map of real-world computational capabilities**. Every domain must have:
- evidence
- structure
- completeness check
- traceability

---

## Domain Extraction: Stress-Test & Evaluation

### Three possible failure modes

1. **Overconfident fake completeness** (most common) — looks clean, nicely grouped, no real citations. Still hallucinated structure.

2. **Semi-accurate but shallow** — pulls obvious stdlib/API names, misses deeper system calls or edge behavior. No real layering correctness.

3. **Actually useful structured ontology** (rare but gold) — clear grouping by layer, explicit gaps, references to real docs, separation of core vs edge vs control. **This is what we want.**

### The real test

Don't judge output by "does it look smart". Judge it by:

> **Can I execute against it?**

- Can the system compare implementations against it?
- Can missing methods be detected reliably?
- Can it prevent wrong selection (our current core problem)?

If not → it's still just descriptive text.

### Evaluation checklist when results come in

1. **Grounding** — does every item map to real docs, real SDK, real system call?
2. **Structure integrity** — is it layered (not flat list), behavior-based (not name-based only)?
3. **Closure validity** — does it explicitly say what is missing, what is uncertain, what is out of scope?

If it doesn't do all three → it failed the real requirement.

### Critical warning

Even a "perfect-looking domain extraction model" will still:

> confuse documentation coverage with system completeness

- docs ≠ full system behavior
- APIs ≠ full runtime semantics
- lists ≠ true closure

That gap is exactly where the current engine is fragile. The behavioral validation layer (sandbox execution) is what closes that gap — docs say it should work, execution proves it does.

### Scoring rubric for extraction output

| Criterion | Weight | Pass | Fail |
|-----------|--------|------|------|
| Every item has source reference | 25% | real doc/SDK link | no citation |
| Layered structure (core/extended/control/edge) | 20% | 4 distinct layers | flat list |
| Explicit gaps marked | 20% | "not found in source" sections | claims completeness |
| Methods map to real APIs | 20% | verifiable function exists | invented names |
| Confidence score < 1.0 for uncertain areas | 15% | honest uncertainty | claims 100% |

**Minimum acceptable score: 70%.** Below that, the extraction is discarded and re-run.

### What we're really testing

Not a prompt. We're stress-testing a shift toward:

> **evidence-grounded computational ontology generation**

That sits underneath everything else:
- closure engine
- survivor ranking
- MySQL + GitHub fusion
- behavioral validation

### Automated grading

Future: design a scoring function that automatically grades extraction output against the rubric above, so we don't manually judge each domain. The scoring function would:
- check for source references (regex for URLs/doc names)
- verify layer count (parse for core/extended/control/edge sections)
- detect gap markers ("not found", "missing", "unknown")
- cross-check method names against Python stdlib index
- flag any item with no verifiable source
