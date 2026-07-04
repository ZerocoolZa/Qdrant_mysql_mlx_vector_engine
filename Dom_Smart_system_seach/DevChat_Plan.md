# Smart System Search — DevChat Plan

> **Module**: `Smart_system_seach/`
> **Created**: 2026-06-22
> **Status**: Working — built, needs Ghost integration

---

## What Was Built (Session History)

### Session 1 — msearch + Qdrant Integration (history_cf2f061009ac4c3f)
- Integrated Qdrant vector search into `msearch.c` binary
- Enabled hybrid MySQL + Qdrant searches
- Used upgraded tool to find real data for VBStyle book chapters
- Built `--hybrid`, `--qstats`, `--where`, `--vbstyle` flags

### Session 2 — Mini Search GUI (history_9ad21620c44b4f54)
- Built PyQt6 mini GUI with bottom search bar, top results
- Always-on-top behavior, minimize-to-ball on macOS
- Debugged minimize-to-ball feature extensively

### Session 3 — Smart System Search Module
- Built `Classifier_smart_system.py` — query classification
- Built `Engine_smart_search.py` — search engine abstraction
- Built `Config_smart_system.py` — configuration
- Built `Extract_qa_pairs.py` — QA pair extraction from chats
- Built `Extract_user_questions.py` — question extraction
- Built `View_user_questions.py` — question viewer
- Built `Gui_Smart_search.py` — PyQt6 search GUI
- Built `dot_command_bar.py` — command bar widget
- Built `autocomplete.db` — autocomplete index

---

## Current File Inventory

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `Engine_smart_search.py` | ~800 | Search engine abstraction (MySQL + Qdrant) | Working |
| `Classifier_smart_system.py` | ~600 | Query intent classification | Working |
| `Config_smart_system.py` | ~300 | Configuration | Working |
| `Gui_Smart_search.py` | ~700 | PyQt6 search GUI | Working |
| `Extract_qa_pairs.py` | ~500 | Extract QA pairs from chat history | Working |
| `Extract_user_questions.py` | ~400 | Extract user questions from chats | Working |
| `View_user_questions.py` | ~300 | View extracted questions | Working |
| `dot_command_bar.py` | ~400 | Command bar widget with autocomplete | Working |
| `autocomplete.db` | — | SQLite autocomplete index | Working |
| `README.md` | — | Module documentation | Complete |

---

## What Works

- Hybrid search (MySQL keywords + Qdrant vectors)
- Query classification and intent detection
- QA pair extraction from chat history
- PyQt6 GUI with command bar and autocomplete
- Configurable search parameters

---

## What's Broken / Incomplete

### P1 — Should Fix
1. **Not VBStyle compliant** — needs Run/Tuple3/state dict pattern
2. **Hardcoded paths** — should externalize to config
3. **No connection to QA engine** — search results don't feed into GhostQAEngine

### P2 — Nice to Have
4. **No unit tests**
5. **Autocomplete index not auto-updated**

---

## Next Steps

1. **Convert to VBStyle** — Run/Tuple3/state dict pattern
2. **Externalize config** — remove hardcoded paths
3. **Connect to QA engine** — search results → GhostQAEngine pipeline
4. **Add unit tests**

---

## Integration with Ghost Core

Becomes the **SearchService** in Ghost:

```
ghost/services/search_service.py
  └── wraps Engine_smart_search.Run("search", {"query": "..."})
  └── uses ghost/services/qdrant_service.py for vectors
  └── uses ghost/services/mysql_service.py for keywords
  └── feeds results to ghost/services/qa_service.py
```
