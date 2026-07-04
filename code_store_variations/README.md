# code_store_variations

VBStyle domain closure engine, test runner, and behavioral validation system.

## What This Folder Is

This folder contains the infrastructure for building, testing, and verifying a **closed-world semantic completeness engine** — a system where every domain (io, db, network, etc.) has a finite, verified set of methods that are proven to work under sandbox execution.

The core shift: **truth = correctness under execution, not name matching**.

## Files

### Core Engine

| File | Purpose |
|------|---------|
| `closure_engine.py` | Domain closure engine with behavioral validation. Retrieves candidates from multiple sources, runs them in sandbox, scores by execution behavior, promotes survivors. |
| `test_runner.py` | Sandboxed test VM. Loads test methods from `code_store.db`, executes in isolated namespaces with controlled builtins, writes results to `efl_brain.db` for the learning loop. |
| `Config.py` | Shared config — paths, SQL constants, test counters, assertion helpers. |
| `CodeStore.py` | Code store management — populates `code_store.db` with test classes and methods from domain files. |
| `build_all.py` | Build pipeline — assembles domains, methods, and test infrastructure into `v20_hybrid_best.db`. |
| `vbstyle_adapter.py` | VBStyle compliance adapter — converts non-VBStyle code to VBStyle format (Run dispatch, Tuple3 returns, no decorators, no print). |

### Databases

| DB | Size | Purpose |
|----|------|---------|
| `code_store.db` | 0.6MB | Test classes and test methods (403 tests). Input for `test_runner.py`. |
| `v20_hybrid_best.db` | 71.6MB | Closure engine output. 1379 classes, 873 closure methods, 2717 computational units. |

### Documentation

| File | Purpose |
|------|---------|
| `PLAN.md` | Full architecture plan — problem analysis, 6 approaches, behavioral validation spec, domain extraction agent spec, stress-test rubric. |

## Architecture

### Behavioral Validation Layer (the core)

Three classes replace name-based matching:

1. **`CandidateRetriever`** — pulls ALL candidates from dom files, efl_brain.db, and generator. Returns a list, not a single pick.

2. **`BehavioralValidator`** — runs each candidate in a sandbox. Scores 0-100:
   - AST parse (5pts)
   - VBStyle compliance (5pts)
   - Sandbox execution + Tuple3 return (30pts)
   - Edge case handling (10pts)
   - Historical reward from execution_log (10pts)

3. **`SurvivorRanker`** — ranks all candidates by score, promotes the winner, archives losers to `execution_log`.

### Pipeline

```
1. Define domain closure (what methods must exist)
2. Retrieve candidates (dom files + MySQL + efl_brain + generator)
3. Run all candidates in sandbox
4. Score based on: correctness, contract compliance, runtime behavior
5. Rank results
6. Promote survivor as canonical implementation
7. Log all candidates to execution_log for historical reward
```

### Feedback Loop

```
test_runner.py  →  WriteFeedback()  →  efl_brain.db  →  efl.py feedback
     ↑                                                        |
     └────────── reads reward signals ←──────────────────────┘
```

## VBStyle Rules

All generated code must follow:
- `Run()` dispatch, Tuple3 `(ok, data, error)` returns
- No decorators, no `print`, no hardcoded values
- `self.state` dict (no `self._`)
- PascalCase classes, UPPERCASE constants
- `__init__(self, mem=None, db=None, param=None)`
- `read_state()`, `set_config()`

## How to Run

```bash
# Run the closure engine (processes all 58 domains)
python3 closure_engine.py

# Run the test runner (executes 403 test methods in sandbox)
python3 test_runner.py

# List available tests
python3 test_runner.py --list

# Run tests for a specific domain
python3 test_runner.py --domain io

# Run edge-case tests only
python3 test_runner.py --edge

# View test feedback and repair priorities
python3 efl_brain/efl.py feedback
python3 efl_brain/efl.py feedback io
```

## Connected Systems

- **`efl_brain/`** — EFL Brain. Stores execution_log, test_feedback, learned_fixes, expectation_graph. The learning loop target.
- **MySQL `vb_code_test`** — Historical code database (760TB). Candidate source for the survivor competition model.
- **Domain files** — `dom_*.py` files in `VBSTYLE_MASTER_CORE/VBstyle_Python/Domains/`. Internal truth source for method implementations.

## Current Status

- 58 domains, 873 methods, all 100% closure
- 873/873 verified by behavioral validation (sandbox execution)
- Test runner: 336/403 tests passing in sandbox
- Feedback loop: live (test_runner → efl_brain.db → efl.py)
- Legacy DBs (v01-v19): removed

## Next Steps

See `PLAN.md` for the full roadmap:
- **Phase 1** (done): Behavioral validation layer
- **Phase 2**: Wire MySQL candidates into `CandidateRetriever`
- **Phase 3**: Domain extraction agent — audit and expand `DOMAIN_CLOSURE` with evidence-based extraction
- **Phase 4**: GitHub mining as external candidate source
- **Phase 5**: Domain induction from real code ecosystems (CodeBERT, AST, clustering)
