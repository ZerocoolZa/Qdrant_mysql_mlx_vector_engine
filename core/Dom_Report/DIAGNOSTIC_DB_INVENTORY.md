# Diagnostic Database Inventory — Conceptual Map

## Date: 2026-07-02
## Status: DISCOVERY (no changes made to any database)

---

## 1. DATABASES INVENTORIED

26 databases total. 8 contain diagnostic-related concepts:

| Database | Role | Diagnostic tables | Total rows (approx) |
|---|---|---|---|
| vb_shared | Central knowledge base | 25+ | 160,000+ |
| questions | Question/evidence system | 8 | 1,800,000+ |
| token_registry | Tokenization + QA bridge | 10 | 260,000+ |
| qa_system | QA compliance (mostly empty) | 7 | 4,800 |
| Chat_History | Chat archive + error KB | 1 | 0 (empty) |
| CODEBASE | Code ingestion | 1 | 1 |
| vb_code_test | VBStyle test results | 1 | 44 |
| cascade_intent | Intent patterns | 1 | 84 |

---

## 2. CONCEPTS DISCOVERED

I found **12 distinct concepts** scattered across **35 tables** in **8 databases**.

### Concept 1: PROBLEM
*What went wrong?*

| DB | Table | Rows | Notes |
|---|---|---|---|
| vb_shared | know_problems | 272 | Python exception types (ArithmeticError, AttributeError...) |
| Chat_History | error_knowledge | 0 | Empty — same concept, different schema |

**Overlap:** `Chat_History.error_knowledge` duplicates `vb_shared.error_knowledge` (both have signature, error_type, cause, solution, fix_code, frequency, confidence). Chat_History version is empty.

**Verdict:** `vb_shared.know_problems` is the canonical source. `Chat_History.error_knowledge` is a dead copy.

---

### Concept 2: CAUSE
*Why did it happen?*

| DB | Table | Rows | Notes |
|---|---|---|---|
| vb_shared | know_causes | 153 | Linked to subject_id, has cause_type (root/contributing/runtime/behavioral), severity |
| vb_shared | why_reason_patterns | 12 | Template-based reasoning patterns ("Reduces cognitive load by {mechanism}") |
| vb_shared | error_knowledge.cause | 92 | Embedded column in error_knowledge table |

**Overlap:** Cause appears in 3 places — as a standalone table (`know_causes`), as a column in `error_knowledge`, and as templates in `why_reason_patterns`.

**Verdict:** `vb_shared.know_causes` is the most structured. The `cause` column in `error_knowledge` is redundant. `why_reason_patterns` is a different concept (reasoning templates, not actual causes).

---

### Concept 3: SOLUTION
*How to fix it?*

| DB | Table | Rows | Notes |
|---|---|---|---|
| vb_shared | know_solutions | 348 | Has weight, auto_apply, fault_code, scope, domain_id, rule_id |
| CODEBASE | ingest_solutions | 1 | Single row — file ingestion solutions only |
| vb_shared | know_fixes | 1 | Almost empty — actual applied fixes with file_path, line_range |

**Overlap:** 3 tables for "solution" concept. `know_solutions` is the main one (348 rows, 127 without problem_id). `ingest_solutions` is domain-specific. `know_fixes` is nearly empty but has the richest schema (fix_text, file_path, line_range, applied_at).

**Verdict:** `vb_shared.know_solutions` is canonical. `know_fixes` should be merged into it (it's the "applied" version). `ingest_solutions` is domain-specific and can stay separate.

---

### Concept 4: FIX ATTEMPT
*Did the fix work?*

| DB | Table | Rows | Notes |
|---|---|---|---|
| vb_shared | fix_attempts | 7 | Has attempt_type (auto/manual), result (success/failed/partial) |
| token_registry | applied_repair | 1,016 | Has fix_action, confidence, before_hash, after_hash |
| qa_system | applied_repair | 0 | Empty copy of token_registry.applied_repair |

**Overlap:** 3 tables for "fix attempt" concept. `token_registry.applied_repair` has the most data (1,016 rows). `qa_system.applied_repair` is an empty copy. `vb_shared.fix_attempts` is nearly empty but links to error_id.

**Verdict:** `token_registry.applied_repair` is the most used. The schema should be unified — `fix_attempts` has attempt_type/result which `applied_repair` lacks, and `applied_repair` has before_hash/after_hash which `fix_attempts` lacks.

---

### Concept 5: QUESTION
*What do we want to know?*

| DB | Table | Rows | Notes |
|---|---|---|---|
| vb_shared | know_questions | 111,452 | General knowledge questions (category, question_number) |
| questions | question | 8,868 | Structured questions (family, field_name, is_required, is_knowledge, classification) |
| questions | question_family | 21 | Question groupings (identity, cause, outcome, etc.) |
| questions | question_variant | 0 | Empty — question phrasing variants |
| questions | question_gap | 0 | Empty — unanswered questions |
| questions | question_link | 0 | Empty — question-to-evidence links |
| vb_shared | anti_collapse_questions | 11 | Investigation questions (question_type, channel, status, answer, answer_result) |
| chatgpt_export | Questions | 65,377 | Questions extracted from ChatGPT conversations |

**Overlap:** Massive. 4 databases, 8 tables, 185,000+ rows. `know_questions` is the largest (111K). `questions.question` is the most structured (family, field_name, classification). `anti_collapse_questions` is the most diagnostic (question_type, channel, status, answer_result).

**Verdict:** This is the most fragmented concept. `questions.question` has the best schema (family-based, is_required, is_knowledge). `know_questions` has the most data but weaker structure. `anti_collapse_questions` is the closest to our diagnostic protocol.

---

### Concept 6: ANSWER
*What is the response to a question?*

| DB | Table | Rows | Notes |
|---|---|---|---|
| vb_shared | know_answers | 31,683 | Has confidence, provenance, determinism_mode, is_canonical, version |
| questions | question_evidence | 10,632 | Evidence linked to questions (not direct answers) |

**Overlap:** `know_answers` is the main answer store. `question_evidence` is supporting evidence, not direct answers.

**Verdict:** `vb_shared.know_answers` is canonical. The `question_evidence` table is a different concept (evidence, not answers).

---

### Concept 7: LEARNED RULE
*What pattern have we learned?*

| DB | Table | Rows | Notes |
|---|---|---|---|
| vb_shared | learned_rules | 10,341 | pattern, trigger_condition, fix_action, language, category, severity, success_count, failure_count, confidence |
| vb_shared | rule_patterns | 37 | rule_id, language, kind, pattern, message |
| vb_shared | rules | 281 | rule, description, rule_category, severity |
| vb_shared | conditional_rules | 52 | component_id, rule_type (when/when_not), condition_expression, priority, is_blocking |
| vb_shared | inference_rules | 11 | rule (text only) |
| cascade_intent | intent_patterns | 84 | state_id, pattern, pattern_type, weight, is_active |

**Overlap:** 6 tables for "rule" concept. `learned_rules` is the richest (10K rows, success/failure tracking, confidence). `rules` is the base rule definitions. `rule_patterns` is regex patterns for rules. `conditional_rules` is component-level rules. `inference_rules` is minimal. `intent_patterns` is a different concept (user intent, not code rules).

**Verdict:** `learned_rules` is the operational knowledge. `rules` is the rule definitions. These should be linked but are currently disconnected (learned_rules has no rule_id FK).

---

### Concept 8: EXECUTION LOG
*What ran and what happened?*

| DB | Table | Rows | Notes |
|---|---|---|---|
| vb_shared | execution_log | 396 | run_id, command, status, exit_code, stdout, stderr, duration, error_type, linked_error_id |
| token_registry | execution_runtime | 10 | execution_id, objective_id, status, result, error_message, retry_count, pause_reason |
| vb_code_test | mu_execution_state | 2 | task_id, active_node, execution_path, open_loops, blocked_by, last_error |
| vb_shared | runtime_context | 0 | session_id, active_problem, active_workflow, active_step, status |

**Overlap:** 4 tables for "execution" concept. `execution_log` is the most used (396 rows). `execution_runtime` is more structured (objective_id, retry_count). `mu_execution_state` is graph-specific. `runtime_context` is empty.

**Verdict:** `execution_log` is the operational log. `execution_runtime` is the structured execution tracker. These should be unified — `execution_log` has stdout/stderr which `execution_runtime` lacks, and `execution_runtime` has retry/pause which `execution_log` lacks.

---

### Concept 9: COMPLIANCE / VIOLATION
*Did the code follow the rules?*

| DB | Table | Rows | Notes |
|---|---|---|---|
| qa_system | method_compliance | 0 | method_id, violation_count, last_scanned, autofix_count |
| qa_system | method_violations | 0 | method_id, rule_id, kind, message, pattern, detected_at |
| token_registry | method_compliance | 401 | Same schema as qa_system version |
| token_registry | method_violations | 607 | Same schema as qa_system version |

**Overlap:** Exact schema duplication. `qa_system` versions are empty. `token_registry` versions have data.

**Verdict:** `token_registry.method_compliance` and `token_registry.method_violations` are the live versions. `qa_system` versions are dead copies.

---

### Concept 10: EVIDENCE
*What data supports a conclusion?*

| DB | Table | Rows | Notes |
|---|---|---|---|
| questions | evidence | 253,639 | fingerprint, conversation_id, source_file, source_line, original_text, message_type |
| questions | evidence_context | 1,417,353 | evidence_id, position, context_text, context_author |
| questions | question_evidence | 10,632 | question_id, original_text, source_file, source_line, source_type, context |

**Verdict:** Unique to `questions` database. No overlap. This is the evidence store.

---

### Concept 11: LESSON
*What did we learn from a specific case?*

| DB | Table | Rows | Notes |
|---|---|---|---|
| vb_shared | know_lessons | 168 | file, symbol, dimension, issue_type, severity, description, suggested_fix, code_snapshot, iteration, confirmed, source |

**Verdict:** Unique concept — per-file, per-symbol lessons with code snapshots. No overlap. This is the "postmortem" concept.

---

### Concept 12: EVALUATION / SCORING
*How do we score or evaluate?*

| DB | Table | Rows | Notes |
|---|---|---|---|
| vb_shared | evaluation_report | 36 | table_name, rows_count, entity_type, recommendation, similarity, report_json |
| vb_shared | scoring_model | 4 | component_id, score_expression, base_score, max_score, description |
| token_registry | evaluation_pros_cons | 0 | approach_name, category, pros, cons, effectiveness_score, decision_date, status |
| vbstyle_documents | feature_weights | 0 | Empty |

**Verdict:** 4 tables, all nearly empty. `evaluation_report` has some data (36 rows of table recommendations). `scoring_model` has 4 rows. This concept is underdeveloped.

---

## 3. CROSS-DATABASE OVERLAP SUMMARY

| Concept | Tables | Databases | Total rows | Canonical source |
|---|---|---|---|---|
| PROBLEM | 2 | 2 | 272 | vb_shared.know_problems |
| CAUSE | 3 | 1 | 165 | vb_shared.know_causes |
| SOLUTION | 3 | 2 | 350 | vb_shared.know_solutions |
| FIX ATTEMPT | 3 | 2 | 1,023 | token_registry.applied_repair |
| QUESTION | 8 | 4 | 185,729 | SPLIT (see below) |
| ANSWER | 2 | 1 | 31,683 | vb_shared.know_answers |
| LEARNED RULE | 6 | 2 | 10,836 | vb_shared.learned_rules |
| EXECUTION LOG | 4 | 2 | 408 | vb_shared.execution_log |
| COMPLIANCE | 4 | 2 | 1,008 | token_registry.method_* |
| EVIDENCE | 3 | 1 | 1,681,624 | questions.evidence |
| LESSON | 1 | 1 | 168 | vb_shared.know_lessons |
| EVALUATION | 4 | 2 | 40 | vb_shared.evaluation_report |

**Total: 35 tables, 8 databases, ~1.9M rows of diagnostic data**

---

## 4. DEAD TABLES (empty or near-empty duplicates)

| DB | Table | Rows | Reason |
|---|---|---|---|
| Chat_History | error_knowledge | 0 | Duplicate of vb_shared.error_knowledge |
| qa_system | applied_repair | 0 | Duplicate of token_registry.applied_repair |
| qa_system | method_compliance | 0 | Duplicate of token_registry.method_compliance |
| qa_system | method_violations | 0 | Duplicate of token_registry.method_violations |
| questions | question_gap | 0 | Never populated |
| questions | question_link | 0 | Never populated |
| questions | question_variant | 0 | Never populated |
| vb_shared | know_fixes | 1 | Nearly empty — should merge into know_solutions |
| vb_shared | fix_attempts | 7 | Nearly empty — should merge into applied_repair |
| vb_shared | runtime_context | 0 | Never populated |
| token_registry | evaluation_pros_cons | 0 | Never populated |
| vbstyle_documents | feature_weights | 0 | Never populated |

**12 dead tables across 5 databases.**

---

## 5. PROPOSED UNIFIED CONCEPTUAL MODEL

Based on the inventory, here is the conceptual model. This is NOT a physical schema — it's the concepts that a unified diagnostic database should cover.

```
PROBLEM
  ├── has CAUSES (1:N)
  ├── has SOLUTIONS (1:N)
  │     └── each solution has FIX_ATTEMPTS (1:N)
  │           └── each attempt has result (success/failed/partial)
  ├── has LESSONS (1:N) — per-case postmortems
  └── has EVIDENCE (1:N) — supporting data

QUESTION
  ├── belongs to a FAMILY (identity, cause, outcome, history, repair, prevention)
  ├── has ANSWERS (1:N)
  │     └── each answer has confidence, provenance, is_canonical
  ├── has EVIDENCE (1:N)
  └── maps to a PROBLEM (optional — some questions are knowledge, not diagnostic)

LEARNED_RULE
  ├── has pattern, trigger_condition, fix_action
  ├── has success_count, failure_count, confidence
  └── links to a RULE definition (optional)

EXECUTION
  ├── has command, status, exit_code, duration
  ├── has stdout, stderr, error_type
  └── links to a PROBLEM (if it failed)

COMPLIANCE
  ├── per method: violation_count, last_scanned, autofix_count
  └── has VIOLATIONS (1:N) — kind, message, pattern, detected_at
```

### Key observations:

1. **PROBLEM is the hub.** Causes, solutions, fixes, lessons, and evidence all radiate from it.
2. **QUESTION is parallel to PROBLEM.** Some questions are diagnostic ("why did this fail?"), some are knowledge ("what is a computational unit?"). The `is_knowledge` flag in `questions.question` already distinguishes these.
3. **LEARNED_RULE is operational knowledge.** It's what the system has learned from experience. It should link to PROBLEM (the problem it solves) and to RULE (the rule it enforces).
4. **EXECUTION is the trigger.** When something runs and fails, it creates a PROBLEM. The diagnostic protocol then asks questions about it.
5. **COMPLIANCE is code-quality.** It's not runtime diagnostics — it's static analysis. It can stay separate.

---

## 6. RECOMMENDATION

**Do NOT create a new database yet.**

Instead:

1. **Consolidate within vb_shared first** — it already has 80% of the diagnostic concepts
2. **Merge dead tables** — drop the 12 empty duplicates
3. **Link existing tables** — add foreign keys (know_solutions.problem_id → know_problems.id, learned_rules → know_problems, etc.)
4. **Add the missing concepts** — the diagnostic protocol's 6 categories (identity, outcome, cause, history, repair, prevention) need a table to map questions to categories
5. **Connect the questions database** — `questions.question_family` already has the right idea (identity, cause, etc.) but is disconnected from `vb_shared.know_questions`

The unified diagnostic schema is mostly already there. It's just scattered and unlinked.
