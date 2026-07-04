# VBStyle Rule Engine — Session Context

## What Was Built

### RuleEngine Class (`vbs_rule_engine.py`)
- Authority over VBStyle rules with full CRUD
- Extracts rules from `.md` source files: `obey.md`, `vbstyle_rules.md`, `config_file_rule.md`
- Loads canonical tokens from MySQL `vb_shared.rule_tokens`
- Analyzes gaps (COVERED / WEAK / MISSING)
- Detects duplicates and conflicts
- Searches, proposes, creates, edits, fixes tokens
- Safety: dry-run by default, `commit=True` to execute
- Dedup gate: blocks new tokens that overlap existing ones by distinctive word count + score threshold

### Config Updates (`Config_Vbs_Code_Verifiation.py`)
- Added `RULE_ENGINE` config block: table name, categories, stopwords, thresholds, conflicts
- Registered `vbs_rule_engine.py` in FILE_REGISTER, CLASS_INDEX, BOOT_SPINE, DEPENDENCY_GRAPH
- Updated DOMAIN_SUMMARY counts

## Canonical Store

- **Table:** `vb_shared.rule_tokens` (schema: id, name, bracket_body, category, created_at)
- **Format:** `name=[@ConceptName]`, `bracket_body=("detail...";92)`, `category` in {Architecture, State, Method, Forbidden, Format, Naming, Paths, Database, FileOps, Workflow, Meta, Other}
- **238 tokens**, zero duplicate bodies
- **Meta-tokens:** `[@MetaOneConcept]`, `[@MetaCheckFirst]`, `[@MetaNoDupBody]`, `[@MetaGroupDomain]`, `[@MetaNameIsConcept]`, `[@MetaNoPrefix]`
- **Do NOT use** legacy `rules` table (282 prose rows, messy) or general `tokens` table (303 rows, inconsistent)

## Rule Source Files

1. `/Users/wws/contestsystem/.devin/rules/obey.md` — VBStyle compliance rules, architectural standards, process gates
2. `/Users/wws/Qdrant_mysql_mlx_vector_engine/.devin/rules/vbstyle_rules.md` — detailed code rules (naming, format, architecture, error handling, SQL, security, BCL tokens, pipeline)
3. `/Users/wws/Qdrant_mysql_mlx_vector_engine/.devin/rules/config_file_rule.md` — 20 config file rules (R1-R20)

## Gap Analysis Results

- Process/governance rules from `obey.md` missing from `rule_tokens`: `@precode`, `@postcode`, `@noexec`, `@nobulk`
- Various technical tokens from `vbstyle_rules.md` and `config_file_rule.md` also missing
- Gap analysis script was at `/tmp/rule_gap_analysis.py` (read-only, symmetric scoring + distinctive word bonus)

## Dedup Logic

- Stopwords expanded to filter generic prose words
- `RULE_DEDUP_BLOCK` threshold separate from coverage threshold
- `RULE_DEDUP_MIN_DISTINCTIVE` requires sufficient distinctive shared words to block
- Prevents false positives from generic overlap

## Test Script

- `/tmp/test_rule_engine.py` — tested open/close, extract, load, analyze, duplicates, conflicts, search, dry-run create
- All tests passed against live MySQL

## Pending Work

- Add missing process/governance tokens to `rule_tokens` (dry-run SQL for review before execution)
- Token names to add: `@precode`, `@postcode`, `@noexec`, `@nobulk`, and other missing technical tokens from gap analysis
