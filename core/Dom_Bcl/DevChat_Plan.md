# BCL — DevChat Plan

> **Module**: `BCL/`
> **Created**: 2026-06-22
> **Status**: Complete — 3 tasks done, engine hardened

---

## What Was Built (Session History)

### Session 1 — BCL Definition (history_27d3dcd7f6444d1e, history_dfa6bf58339f4fb6)
- Renamed VBLang/VBBracketLang → BCL across book databases
- Added "BCL: Bracket Command Language" chapter to VBStyle book
- Documented the "Four C's": Control, Config, Communication, Command
- Created glossary entries in `book.db` and `vbstyle_book_v2.db`

### Session 2 — BCL Converter (history_e3e403026d274e23, history_9f12dfeddd0e40c1)
- Built `txt_to_bcl_v3.py` → `txt_to_bcl_v4.py` converter
- Parses markdown, chat, Python code, JSON → BCL tokens
- Stores tokens in MySQL
- Added conceptual moment detection (ideas, decisions, problems, plans)
- Added question detection

### Session 3 — BCL Engine Hardening (history_22c6487657b84af5)
- Built `DOM_REGISTRY.md` documenting all `dom_*.py` files
- Fixed VBStyle violations in BCL code (INTSTATE, print, decorators)
- Bulk fix attempt caused data corruption → established "one method at a time" rule

### Session 4 — Engine Invariants (TASK-002, TASK-003, TASK-004)
- Replaced `ast_hash` with full structural walk (format-independent)
- Added strict FSM for stage transitions (`ALLOWED_TRANSITIONS`)
- Collapsed VALIDATE/REVALIDATE into single VALIDATE stage
- Added stall detection with structural hash comparison
- Added `text_mode` field to EngineResult (PASS/DIAGNOSTIC)
- Fixed 8 correctness bugs:
  - Duplicate sibling detection (Rule 10)
  - Branch pair requirement (Rule 11)
  - Circular reference detection (Rule 12)
  - Recursion depth guard (MAX_DEPTH=256)
  - Fix ordering (structural before cosmetic)
  - Undo/rollback with snapshot
  - Orphan detection after cleanup
  - Regression check in convergence loop

---

## Current File Inventory

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `bcl_engine.py` | ~800 | Pipeline orchestrator (FSM: PARSE→VALIDATE→FIX→SERIALIZE) | Complete |
| `bcl_parser.py` | ~600 | AST parser for BCL bracket notation | Complete |
| `bcl_lexer.py` | ~400 | Tokenizer for BCL syntax | Complete |
| `bcl_validator.py` | ~500 | 12 validation rules + depth guard | Complete |
| `bcl_fixer.py` | ~400 | Auto-fix with undo/rollback + orphan detection | Complete |
| `bcl_config.py` | ~300 | BCL configuration management | Complete |
| `bcl_crud.py` | ~500 | Create/Read/Update/Delete operations on BCL AST | Complete |
| `config.py` | ~300 | Constants and paths | Complete |
| `BCL_DECISION_TREES.md` | — | Decision tree documentation | Complete |

---

## What Works

- Complete BCL pipeline: PARSE → VALIDATE → FIX → SERIALIZE
- 12 validation rules with deterministic ordering
- Auto-fix with undo/rollback and orphan re-linking
- CRUD operations on BCL AST with clone-based safety
- Strict FSM prevents out-of-order stage execution
- Stall detection via structural hash comparison
- All 13 CRUD tests pass, deterministic across 3 runs
- VBStyle compliant (Run/Tuple3/state dict)

---

## What's Broken / Incomplete

### P2 — Nice to Have
1. **No unit test file** — tests are embedded in `bcl_crud.py demo`. Should extract into `test_bcl.py`.
2. **No BCL schema DSL** — category 3 language features (comments, imports, schema) not implemented per spec.
3. **Tuple structure validation** — free-form, only Rule 999 constrains. May need schema-driven validation later.

---

## Next Steps

1. **Extract tests** into standalone `test_bcl.py`
2. **Add BCL schema DSL** if needed by Ghost config system
3. **Integrate with Ghost core** — BCL becomes the config format for `ghost/config.py`

---

## Integration with Ghost Core

BCL is the **config persistence format** for Ghost (PLAN.md Decision 5):

```
ghost/config.py
  └── reads/writes BCL-formatted config values to SQLite
  └── uses BCL engine for parse/validate/fix/serialize
  └── BCL values stored in config table: [@key]{("value"; "...")}
```

The BCL engine also serves as the **documentation format** for methods stored in the SQLite code-as-filesystem (PLAN.md Section 8).
