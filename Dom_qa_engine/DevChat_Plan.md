# QA Engine — DevChat Plan

> **Module**: `qa_engine/`
> **Created**: 2026-06-22
> **Status**: Working — testing phase, needs cleanup

---

## What Was Built (Session History)

### Session 1 — QA Prototype (history_bbdead3dabf04795)
- Retrieved Pinecone content, validated QA architecture
- Confirmed BERT SQuAD CoreML model exists (`BERTSQUADFP16.mlmodel`, 217MB)
- Found existing `qa_prototype.py` — retrieve-then-extract architecture
- Tested initial pipeline: BGE embed → Qdrant search → BERT QA extraction

### Session 2 — QA Engine Refactor (history_187df81bf0414abf)
- Discovered BERT QA was the bottleneck (57% accuracy)
- Refactored into configurable `GhostQAEngine.py` (1656 lines)
- Built 5 pipeline modes: A (retrieval only), B (BERT QA), C (BERT+LLM format), D (LLM only), E (QA only)
- Benchmarked 28 questions across 10 aspects
- **Result**: Mode D (Qwen 1.5B) = 89% answer accuracy, Mode B (BERT) = 57%
- Built `five_mode_runner.py`, `qa_test_harness.py`, `qa_test_harness_v2.py`

### Session 3 — Fact Store Discovery (history_a80c39e8e8d04aed)
- Integrated `QueryInterpreter` + `ModeRouter` into GhostQAEngine
- Built Mode R (routed auto with BERT fallback)
- Discovered existing Fact Store in MySQL: `know_nodes` (1694), `know_answers` (123), `learned_rules` (10540)
- Designed 3-layer epistemic system (Appendix C in PLAN.md)
- Found epistemic lifecycle: open → answered → stabilized → collapsed

### Session 4 — 6-Mode Harness (history_9ce1db4bc7b74d90)
- Built `six_mode_runner.py` with Mode R
- Ran 6-mode harness, found Mode R issues
- Fixed routing logic, prompt-leak detection
- Built `three_experiment_harness.py` for A/B/C comparison
- Built `pinnacle_harness.py` with curated chat documents

### Session 5 — Config Hardening (history_14ee299cfbc1443e)
- Built `Config_qa_engine.py` (340 lines) — all constants externalized
- Built `qa_engine_config.json` (185 lines) — model registry, storage, retrieval, classification
- Wrote `QA_ENGINE_SPEC.md` — 15 sections covering all configurability rules

---

## Current File Inventory

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `GhostQAEngine.py` | 1656 | Core engine, 6 modes, VBStyle | Working |
| `Config_qa_engine.py` | 340 | Constants, paths, model configs | Working |
| `qa_engine_config.json` | 185 | JSON config (model registry, storage) | Working |
| `QA_ENGINE_SPEC.md` | 79 | 15-section spec document | Complete |
| `pinnacle_harness.py` | 826 | Full pipeline test harness | Working |
| `six_mode_runner.py` | 349 | 6-mode experiment runner | Working |
| `five_mode_runner.py` | 279 | 5-mode experiment runner | Redundant |
| `three_experiment_harness.py` | 402 | 3-experiment comparison | Redundant |
| `qa_test_harness.py` | 456 | Test harness v1 | Redundant |
| `qa_test_harness_v2.py` | 688 | Test harness v2 | Redundant |
| `qa_prototype.py` | 398 | V1 prototype, hardcoded paths | Dead code |
| `Rule_Gui.py` | 678 | VBStyle rule truth GUI | Unrelated |
| `fact_store_mock.py` | 425 | Fact store visualization GUI | Unrelated |
| `BERTSQUADFP16.mlmodel` | 217MB | CoreML BERT SQuAD model | Should be in models/ |
| `pinnacle_harness.db` | 188KB | Test database | Working |

---

## What Works

- 6-mode pipeline graph (A/B/C/D/E/R) with graceful degradation
- BGE embedding → Qdrant search → BERT/Qwen extraction → classification
- Mode R routing with QueryInterpreter + ModeRouter + BERT fallback
- Hardware detection (CPU cores, RAM, GPU, Metal, disk)
- Model registry (embedding, QA, LLM — all configurable, all swappable)
- Vector backend abstraction (Qdrant, FAISS, SQLite Vector, RAM)
- Failure attribution per stage (DOCUMENT_LOAD → CLASSIFICATION)
- VBStyle compliance (Run/Tuple3/state dict, no decorators, no print)
- Config externalized to JSON + Python constants

---

## What's Broken / Incomplete

### P0 — Must Fix
1. **LLM confidence is fake** — uses answer length, not token probabilities:
   ```python
   if len(answer) < 20: confidence = 7.0  # WRONG
   elif len(answer) < 100: confidence = 6.0
   else: confidence = 5.0
   ```
   Should use mlx_lm token logprobs or a calibration table.

2. **5 redundant runners** — `qa_prototype.py`, `qa_test_harness.py`, `qa_test_harness_v2.py`, `five_mode_runner.py`, `three_experiment_harness.py` all do variations of the same thing. Consolidate into one parameterized runner.

3. **`qa_prototype.py` violates spec** — hardcoded paths (QDRANT_URL, model paths). Dead code, should be deleted.

### P1 — Should Fix
4. **Fact Store not wired** — PLAN.md Appendix C describes 3-layer epistemic system (Fact Store → Mode D → Promotion). MySQL tables exist (`know_nodes`, `know_answers`) but GhostQAEngine doesn't read/write them. The 5ms fast path (canonical truth lookup) is not implemented.

5. **`pinnacle_harness.py` duplicates pipeline** — imports `sentence_transformers` directly instead of using `GhostQAEngine.Run("ask", {...})`. Tests a different code path than the engine.

6. **2 unrelated GUIs in this folder** — `Rule_Gui.py` (VBStyle rule truth) and `fact_store_mock.py` (fact store visualization) have nothing to do with the QA engine. Move to a separate `gui/` or `rule_engine/` directory.

7. **217MB model in source tree** — `BERTSQUADFP16.mlmodel` should be in a `models/` directory or gitignored.

### P2 — Nice to Have
8. **No unit tests** — 6,761 lines of Python, zero test files. Need unit tests for HardwareDetector, ModelRegistry, VectorBackend, classification, chunking.

9. **Mode R prompt-leak detection is fragile** — catches "Yes"/"No" but not "Yes, because..." or "No, the evidence says...".

10. **Contradiction resolution protocol** — designed in PLAN.md C.5 but not implemented. When Mode D contradicts canonical truth, no flag/re-validation occurs.

11. **Promotion engine** — PLAN.md C.2 Step 4. After Mode D produces high-confidence answer, should write to `know_answers`, create/update `know_nodes`, set state=answered. Not implemented.

12. **Collapse cycle** — PLAN.md C.2 Step 5. When density threshold reached, run 6-phase collapse algorithm to create memory units. Not implemented.

---

## Next Steps (Priority Order)

1. **Delete `qa_prototype.py`** — dead v1 code
2. **Consolidate 5 runners → 1** — `qa_runner.py --mode A|B|C|D|E|R --questions <file>`
3. **Fix LLM confidence** — use real token probabilities from mlx_lm
4. **Move `Rule_Gui.py` + `fact_store_mock.py`** to separate directory
5. **Move BERT model** to `models/` directory
6. **Wire Fact Store** — implement the 5ms canonical truth lookup path
7. **Wire promotion engine** — Mode D answers → `know_answers` → `know_nodes`
8. **Add unit tests** for core components
9. **Implement contradiction resolution** (PLAN.md C.5)
10. **Implement collapse cycle** (PLAN.md C.4)

---

## Integration with Ghost Core

When the Ghost core is built (PLAN.md build order), this module becomes the **GhostQA service**:

```
ghost/services/qa_service.py
  └── wraps GhostQAEngine.Run("ask", {"question": "..."})
  └── reads config from ghost/config.py
  └── uses ghost/services/qdrant_service.py for vector search
  └── uses ghost/services/mlx_service.py for embeddings + LLM
  └── writes facts to MySQL via ghost/services/mysql_service.py
```

The engine itself stays here as a library. The Ghost core imports it.
