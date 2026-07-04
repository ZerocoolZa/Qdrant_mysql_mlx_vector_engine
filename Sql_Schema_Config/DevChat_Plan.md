# Sql Schema Config — DevChat Plan

> **Module**: `Sql_Schema_Config/`
> **Created**: 2026-06-22
> **Status**: Working — BCL engine complete, schema designed

---

## What Was Built (Session History)

### Session 1 — BCL Engine Audit (history_27d3dcd7f6444d1e)
- Audited BCL engine implementation against aspirational vision
- Verified current state of BCL parser/validator/fixer
- Confirmed BCL "Four C's": Control, Config, Communication, Command

### Session 2 — Schema Design (history_0607855235ce4ff1)
- Evaluated "code in database" pattern
- Built and benchmarked 20 schema variations
- Selected `v20_hybrid_best` for comprehensive features
- Populated with existing code and metadata
- Created computational units, domain assignments
- Defined finite set of domains (57 existing `dom_*.py` files)

### Session 3 — Chat DB Schema
- Built `Database_Schema_config.py` — schema management
- Built `chat_history_schema.sql` — chat history table definitions
- Built `Find_list.py` — list utility
- Built `import_md_files.py` — markdown file importer
- Wrote `PLAN_Chatdb.md` — chat database planning document
- Built `Database_Schema_config_v2.bcl` — BCL-formatted schema config

---

## Current File Inventory

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `Database_Schema_config.py` | ~400 | Schema management | Working |
| `chat_history_schema.sql` | ~200 | Chat history SQL schema | Complete |
| `Find_list.py` | ~100 | List utility | Working |
| `import_md_files.py` | ~200 | Markdown importer | Working |
| `PLAN_Chatdb.md` | — | Chat DB planning document | Complete |
| `Database_Schema_config_v2.bcl` | — | BCL schema config | Complete |

---

## What Works

- BCL-formatted schema configuration
- Chat history schema with SQL definitions
- Markdown file import pipeline
- Schema management via Python

---

## What's Broken / Incomplete

### P1 — Should Fix
1. **Not VBStyle compliant** — needs Run/Tuple3 pattern
2. **Schema not yet applied to Ghost** — the SQLite code-as-filesystem schema (PLAN.md Section 8) uses these definitions but Ghost core doesn't exist yet
3. **No migration path** — existing MySQL data needs migration strategy

### P2 — Nice to Have
4. **No unit tests**
5. **BCL schema config not validated** against BCL engine

---

## Next Steps

1. **Convert to VBStyle** — Run/Tuple3 pattern
2. **Apply schema to Ghost** — create `ghost.db` with methods/classes/domains/config tables
3. **Build migration** — MySQL → SQLite for code storage
4. **Validate BCL config** with BCL engine

---

## Integration with Ghost Core

This module defines the **SQLite-as-filesystem** schema (PLAN.md Section 8):

```
ghost.db tables:
  methods    — each row = one Python method (code + BCL metadata)
  classes    — each row = one VBStyle class
  categories — method categories (service, domain, util, gui, cli)
  types      — method types (Run, helper, init, dispatch)
  domains    — class domains (mlx, qdrant, mysql, api, cli, gui)
  config     — BCL-formatted config values
```

The schema is the foundation for Ghost's code storage. Every method is a row, self-documented with BCL.
