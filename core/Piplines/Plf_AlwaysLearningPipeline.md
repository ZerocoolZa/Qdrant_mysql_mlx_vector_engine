#[@GHOST]{file_path="core/Piplines/Plf_AlwaysLearningPipeline.md" date="2026-06-30" author="cascade" session_id="c-always-learning" context="Always-learning architecture: worker model generates, supervisor model catches failures, database records patterns, confidence-gated weight updates. Derived from design discussion between user and Cascade."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="Plf_AlwaysLearningPipeline.md" domain="learning_architecture" authority="Cascade"}
#[@SUMMARY]{summary="Always-learning pipeline: model generates, supervisor catches, database records, confidence gate triggers weight updates. Not train-then-deploy-then-retrain. Learn while running. Scale by recording one DB row per failure, not by updating billions of weights per interaction."}
#[@CLASS]{class="AlwaysLearningPipeline" domain="learning_architecture" authority="Cascade"}
#[@METHOD]{method="Run" type="command"}
#[@METHOD]{method="Catch" type="command"}
#[@METHOD]{method="Record" type="command"}
#[@METHOD]{method="Gate" type="command"}
#[@METHOD]{method="UpdateWeights" type="command"}

---

# Always-Learning Pipeline — Confidence-Gated Continuous Improvement

> **Core thesis:** The model does not think. It predicts. When prediction
> fails, a supervisor catches the failure. The failure and fix get recorded
> in a database. The database is the live brain — always learning, one row
> at a time. Weight updates only happen when a pattern proves itself:
> success count > 1000 OR success rate > 95%. Not train-then-deploy.
> Learn while running.
>
> "The model predicts. The database learns. The system gets better every
> day even though the model itself never changes." — Cascade, 2026-06-30

---

## The Problem With Big Models

Big models (GPT, Claude, etc.) have **frozen weights** during inference.
They do not learn from interactions. Every session starts fresh.

**Why they say they can't learn in real time:**
- Weight updates require backpropagation across hundreds of billions of parameters
- One bad interaction could corrupt reasoning
- Every user would get a different model — hard to test

**Why that argument is wrong (for database learning):**
- Database learning is ONE SQL INSERT per failure — basically free compute
- Structured tables filter noise — only verified fixes get recorded
- The model doesn't change; the **context** changes (RAG for mistakes)
- This scales to any size — milliseconds per lookup

**The real reason:** Control. Companies want to decide what the model learns.
Always-learning lets the system learn from **reality**, not a training team.

---

## Pipeline Overview

```
┌──────────────────────────────────────────────────────────────┐
│  STAGE 1: GENERATE                                          │
│  Worker model generates code / prediction                    │
│  (frozen weights, no learning, just next-token prediction)   │
└──────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│  STAGE 2: EXECUTE                                           │
│  Run the generated code / prediction                         │
│  (ExecutionSession executes Computation Units)               │
└──────────────────┬───────────────────────────────────────────┘
                   │
          ┌────────┴────────┐
          │                 │
       SUCCESS            FAILURE
          │                 │
          ▼                 ▼
┌──────────────┐  ┌──────────────────────────────────────────┐
│  Done        │  │  STAGE 3: CATCH                           │
│              │  │  Supervisor model detects failure          │
│              │  │  (AIRepairSupervisor.Analyze)             │
│              │  └──────────────────┬───────────────────────┘
│              │                     │
│              │                     ▼
│              │  ┌──────────────────────────────────────────┐
│              │  │  STAGE 4: DECIDE                          │
│              │  │  Supervisor selects fix strategy          │
│              │  │  (AIRepairSupervisor.Decide)              │
│              │  └──────────────────┬───────────────────────┘
│              │                     │
│              │                     ▼
│              │  ┌──────────────────────────────────────────┐
│              │  │  STAGE 5: APPLY                           │
│              │  │  Apply fix, retry execution               │
│              │  │  (AIRepairSupervisor.Apply)               │
│              │  └──────────────────┬───────────────────────┘
│              │                     │
│              │          ┌──────────┴──────────┐
│              │          │                     │
│              │       PASS                  FAIL
│              │          │                     │
│              │          ▼                     ▼
│              │  ┌──────────────┐  ┌──────────────────────┐
│              │  │  STAGE 6:    │  │  Record failure,     │
│              │  │  RECORD      │  │  try different fix   │
│              │  │  SUCCESS     │  │  or abort            │
│              │  └──────┬───────┘  └──────────────────────┘
│              │         │
│              │         ▼
│              │  ┌──────────────────────────────────────────┐
│              │  │  STAGE 7: RECORD                          │
│              │  │  Write to repair_patterns table:          │
│              │  │    pattern, fix_action, success_count     │
│              │  │  (ONE SQL INSERT — basically free)        │
│              │  └──────────────────┬───────────────────────┘
│              │                     │
│              │                     ▼
│              │  ┌──────────────────────────────────────────┐
│              │  │  STAGE 8: GATE CHECK                      │
│              │  │                                          │
│              │  │  IF success_count > 1000                 │
│              │  │     OR success_rate > 95%                │
│              │  │  THEN → trigger weight update             │
│              │  │  ELSE → keep recording, wait             │
│              │  │                                          │
│              │  │  (Confidence-gated — no noisy updates)   │
│              │  └──────────────────┬───────────────────────┘
│              │                     │
│              │          ┌──────────┴──────────┐
│              │          │                     │
│              │     NOT GATED              GATED
│              │          │                     │
│              │          ▼                     ▼
│              │  ┌──────────────┐  ┌──────────────────────┐
│              │  │  Continue     │  │  STAGE 9: UPDATE     │
│              │  │  collecting   │  │  WEIGHTS             │
│              │  │  (always on)  │  │                      │
│              │  └──────────────┘  │  Batch all proven     │
│              │                     │  patterns into one    │
│              │                     │  training pass        │
│              │                     │  (CoreMLTrainer)      │
│              │                     └──────────┬───────────┘
│              │                                │
│              │                                ▼
│              │                     ┌──────────────────────┐
│              │                     │  New model weights   │
│              │                     │  saved + deployed    │
│              │                     │  (better predictions)│
│              │                     └──────────┬───────────┘
│              │                                │
│              │                                ▼
│              └────────────────────────────────┘
│                        LOOP CONTINUES
│                   (always learning, always running)
```

---

## Stage Details

### Stage 1: GENERATE — Worker Model Predicts

**What:** The model generates code, a fix, or a prediction.
**How:** Next-token prediction based on training data + context.
**Key insight:** The model is NOT thinking. It is predicting the most
likely next token. When it gets code right, the pattern was clear.
When it gets it wrong, the context was insufficient.

**Implementation:** `ExecutionSession._ExecuteStep()` runs a
Computation Unit. The CU contains source code that was generated
by a model (or written by a human — same pipeline).

### Stage 2: EXECUTE — Run The Prediction

**What:** Execute the generated code in a controlled environment.
**How:** `ExecutionSession.Execute()` runs each CU step in order.
**Output:** Success or failure (with error type, message, traceback).

### Stage 3: CATCH — Supervisor Detects Failure

**What:** When execution fails, the supervisor model analyzes the error.
**How:** `AIRepairSupervisor.Run("analyze", {...})` creates a repair
context with: error type, error message, traceback, past repair attempts,
survivor candidates.
**Key insight:** This is the "human frustration moment" — the point where
a human developer would stop and rethink. The supervisor forces the
system to pause and reassess.

### Stage 4: DECIDE — Supervisor Selects Strategy

**What:** The supervisor decides how to fix the failure.
**How:** `AIRepairSupervisor.Run("decide", {...})` picks a strategy:
- **SWAP** — replace failed CU with a survivor (proven alternative)
- **PATCH** — modify the CU's code and retry
- **RETRY** — run again with different parameters
- **ABORT** — give up, log the failure

**Pattern lookup:** Before deciding, the supervisor queries
`repair_patterns` table for past fixes that worked on similar errors.
This is the "always learning" part — past successes inform current decisions.

### Stage 5: APPLY — Fix And Retry

**What:** Apply the chosen strategy and re-execute.
**How:** `AIRepairSupervisor.Run("apply", {...})` executes the fix.
If SWAP: load survivor CU, run it. If PATCH: modify code, recompile, run.
If RETRY: run again with adjusted parameters.

### Stage 6: RECORD — Write To Database (Always Learning)

**What:** Record the outcome — success or failure — in the database.
**How:** One SQL INSERT to `repair_patterns` table:
```sql
INSERT OR UPDATE repair_patterns
  (pattern, fix_action, success_count, fail_count, confidence, last_used)
VALUES
  ('SyntaxError:invalid_syntax', 'fix_not_in_to_membership', 1, 0, 1.0, NOW());
```

**Cost:** One SQL operation. Milliseconds. Basically free.
**This is the key:** The system learns on EVERY interaction, not just
during scheduled training runs.

### Stage 7: GATE CHECK — Confidence Threshold

**What:** Check if enough evidence has accumulated to justify a weight update.
**Thresholds (configurable):**
- `success_count > 1000` — pattern has been proven many times
- `success_rate > 95%` — pattern almost always works
- Both conditions are OR — either one triggers the gate

**Why gating matters:**
- A fix that works once might be coincidence
- A fix that works 950/1000 times is a real pattern
- Gating filters noise — only proven patterns become weights
- Batching: collect 1000+ verified examples, do ONE training pass

**Implementation:**
```sql
SELECT pattern, fix_action, success_count, fail_count,
       (success_count * 1.0 / (success_count + fail_count)) as success_rate
FROM repair_patterns
WHERE success_count > 1000
   OR (success_count * 1.0 / (success_count + fail_count)) > 0.95
ORDER BY success_count DESC;
```

### Stage 8: UPDATE WEIGHTS — Confidence-Gated Fine Tuning

**What:** Take all proven patterns and bake them into model weights.
**How:** `CoreMLTrainer` takes accumulated patterns as training data,
runs one training pass, saves new weights.

**Input:** All patterns that passed the gate (success_count > 1000
or success_rate > 95%).
**Output:** New `.mlmodel` or `.weights.bin` file with improved predictions.

**Key difference from big model training:**
- Big models: Train on selected data, on company schedule
- This system: Train on REAL failures, when REAL evidence accumulates

### Stage 9: DEPLOY — Better Model, Same Loop

**What:** Deploy the updated weights. The model now predicts better
for the patterns it learned. The database keeps collecting.
**The loop never stops:** Run → Fail → Catch → Fix → Record → Gate → Update → Run

---

## Two Levels of Learning

### Level 1: Database Learning (Always On, Free)

| Aspect | Detail |
|--------|--------|
| **What changes** | Database tables (repair_patterns, learned_rules) |
| **When** | Every single interaction |
| **Cost** | One SQL INSERT — milliseconds |
| **Effect** | Next request queries past fixes before generating |
| **Mechanism** | RAG for mistakes — retrieve relevant patterns, inject as context |
| **Current status** | ✅ Implemented (AIRepairSupervisor, MySQL learned_rules: 10,540 rows) |

### Level 2: Weight Learning (Gated, Batched)

| Aspect | Detail |
|--------|--------|
| **What changes** | Model weights (neural network parameters) |
| **When** | Only when gate threshold is met (count > 1000 or rate > 95%) |
| **Cost** | One training pass over proven patterns |
| **Effect** | Model inherently predicts better — no context injection needed |
| **Mechanism** | CoreMLTrainer fine-tunes on accumulated proven patterns |
| **Current status** | ⬜ CoreMLTrainer exists, gate logic needs to be added |

---

## Why This Scales

**Big model argument:** "Real-time learning is too expensive"
**Reality:** Database learning is one SQL row. No weight update needed.
The model stays frozen. The database gets smarter. Context injection
(RAG) makes the frozen model perform as if it learned.

**Big model argument:** "Real-time learning is unstable"
**Reality:** Only verified fixes get recorded. The gate adds another
layer — only proven patterns (1000+ successes or 95%+ rate) trigger
weight updates. Noise is filtered at two levels.

**Big model argument:** "Every user gets a different model"
**Reality:** The model is the same for everyone. The **database** is
per-deployment. Each system learns from its own reality. That is a
feature, not a bug.

---

## Implementation Map

| Component | File | Role |
|-----------|------|------|
| Worker | `execution_session.py` | Executes CUs, captures failures |
| Supervisor | `ai_repair_supervisor.py` | Analyzes failures, decides fixes, records patterns |
| Survivor Memory | `survivor_ranking.py` | Tracks which CUs work best for each capability |
| Pattern Store | `repair_patterns` table | Live brain — one row per fix strategy |
| Weight Trainer | `CoreMLTrainer.py` | Bakes proven patterns into model weights |
| Gate Logic | **TODO** | Checks success_count/rate thresholds, triggers trainer |
| Knowledge Base | MySQL `learned_rules` (10,540 rows) | Accumulated patterns from all past sessions |

---

## Gate Logic — TODO

```python
class ConfidenceGate:
    """
    Checks repair_patterns for proven strategies.
    When threshold is met, triggers CoreMLTrainer.
    """

    SUCCESS_COUNT_THRESHOLD = 1000
    SUCCESS_RATE_THRESHOLD = 0.95

    def Run(self, command, params=None):
        if command == "check":
            return self._CheckGate(params)
        elif command == "trigger":
            return self._TriggerUpdate(params)
        return (0, None, ("UNKNOWN_COMMAND", command, 0))

    def _CheckGate(self, params):
        # Query repair_patterns for patterns meeting threshold
        # Return list of proven patterns ready for training
        ...

    def _TriggerUpdate(self, params):
        # Collect proven patterns
        # Format as training data
        # Call CoreMLTrainer.Run("train", {...})
        # Save new weights
        ...
```

---

## Summary

```
The model predicts.        ← Frozen weights, no thinking
The supervisor catches.    ← Failure detection at execution time
The database records.      ← One SQL row, always learning
The gate filters.          ← Only proven patterns (1000+ or 95%+)
The trainer updates.       ← Weight change on gated confidence
The loop continues.        ← Always learning, always running
```

**This is not train-then-deploy-then-retrain.**
**This is learn-while-running, update-when-proven.**
