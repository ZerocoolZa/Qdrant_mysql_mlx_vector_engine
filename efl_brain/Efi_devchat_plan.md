# EFL Brain — DevChat Plan

> **Module**: `efl_brain/`
> **Created**: 2026-06-22
> **Status**: Working — RAM AI built, needs Ghost integration

---

## What Was Built (Session History)

### Session 1 — EFL Brain Development
- Built `efl.py` — core EFL (Epistemic Foundation Layer) brain
- Built `efl_ram_ai.py` — RAM-based AI with in-memory reasoning
- Built `Efl_config.py` — configuration management
- Built `md_viewer.py` — markdown viewer for brain output
- Built `efl_brain.db` — SQLite brain state database
- Wrote `README.md` — module documentation

### Related Sessions
- EFL brain concept evolved from ContextRAM work (BrainChat v100-v400)
- Influenced by CognitiveBrain (KIMIK2.6) — full reasoning brain with ask/qna_query/reason_all/learn/remember
- Uses MLX embeddings (bge-small-en-v1.5-8bit) and Qwen2.5-Coder LLM
- Entity extraction and graph traversal capabilities

---

## Current File Inventory

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `efl.py` | ~1000 | Core EFL brain | Working |
| `efl_ram_ai.py` | ~800 | RAM-based AI reasoning | Working |
| `Efl_config.py` | ~300 | Configuration | Working |
| `md_viewer.py` | ~400 | Markdown viewer | Working |
| `efl_brain.db` | — | SQLite brain state | Working |
| `efl_brain.db.tmp` | — | Temp database | Cleanup needed |
| `efl_brain_v1_backup.db` | — | V1 backup | Archive |
| `README.md` | — | Module documentation | Complete |

---

## What Works

- RAM-based AI reasoning with in-memory state
- Entity extraction from text
- Graph traversal for knowledge relationships
- MLX embedding integration (BGE)
- Qwen2.5-Coder LLM for generation
- Markdown viewer for output
- SQLite brain state persistence

---

## What's Broken / Incomplete

### P1 — Should Fix
1. **Not VBStyle compliant** — needs Run/Tuple3/state dict pattern
2. **Hardcoded model paths** — should externalize to config
3. **Temp DB file** — `efl_brain.db.tmp` should be cleaned up
4. **V1 backup** — `efl_brain_v1_backup.db` should be archived or deleted

### P2 — Nice to Have
5. **No unit tests**
6. **No connection to QA engine** — EFL brain and GhostQAEngine are separate
7. **No connection to Fact Store** — doesn't read/write MySQL know_* tables

---

## Next Steps

1. **Convert to VBStyle** — Run/Tuple3/state dict pattern
2. **Externalize config** — remove hardcoded model paths
3. **Clean up temp files** — remove .tmp and backup files
4. **Connect to QA engine** — EFL brain → GhostQAEngine pipeline
5. **Connect to Fact Store** — read/write MySQL know_* tables
6. **Add unit tests**

---

## Integration with Ghost Core

EFL brain becomes the **reasoning layer** in Ghost's 3-phase architecture (PLAN.md Appendix B):

```
Phase 1: Grounding (GhostQAEngine) → extract facts
Phase 2: Logic (EFL Brain) → reason over facts
Phase 3: Action (Ghost CLI/API) → generate output

ghost/services/reason_service.py
  └── wraps efl_ram_ai.Run("reason", {"facts": [...], "query": "..."})
  └── reads from Fact Store (MySQL know_* tables)
  └── uses MLX for LLM reasoning
```
