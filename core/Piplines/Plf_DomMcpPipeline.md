# [@GHOST]
# [@VBSTYLE]
# [@FILEID] core/Piplines/DOM_MCP_PIPELINE.md
# [@SUMMARY] Pipeline tracking for Dom_Mcp unified native MCP server migration
# [@CLASS] DomMcpPipeline
# [@METHOD] track
# [@AUTHOR] wws + Devin
# [@DATE] 2026-06-28
# [@SESSION] dom_mcp_migration

# Dom_Mcp Migration Pipeline

> **Status:** PHASE 4 COMPLETE — All Go binaries built and tested. Ready for IDE cutover (Phase 5).
> **Started:** 2026-06-28
> **Updated:** 2026-06-28
> **Goal:** Consolidate all MCP servers into native Go binaries under `Dom_Mcp/`. Source code stored in SQLite DB (go_mcp_store.db) — no file sprawl. Build mode: all-separate OR all-in-one OR grouped OR single.
> **Authority:** Dom_Mcp is the sole MCP authority. No Node.js. No npx. No Docker-for-MCP.
> **Language:** Go (not Rust — Go 1.26.4 already installed, official MCP SDK available)
> **Result:** 9 Go MCP servers in DB (269 files, 42,784 lines). Unified dom_mcp binary: 30 tools, 11 MB RAM. Total savings: ~226 MB.

---

## Pipeline Phases

### PHASE 1: INDEX (read-only) — DONE
- [x] Agent 1: Profiled all node processes — 21 procs, top hogs identified
- [x] Agent 3: Audited all MCP configs across 4 IDEs (Cascade, Devin, Kilo, Rapid-MLX)
- [x] 8 MCP servers documented: contextram, pinecone, filesystem, taskplanner, memory, devin-sqlite, msearch, yahoo-mail
- [x] Language breakdown: 5 Node.js, 2 Go, 1 Python, 1 Docker, 1 Swift

### PHASE 2: PLAN MOVES — DONE
- [x] Go chosen over Rust (Go 1.26.4 already installed, official MCP SDK available)
- [x] Direct Go replacements found online for each Node.js MCP server
- [x] Source code stored in SQLite DB (go_mcp_store.db) — no file sprawl
- [x] Build modes: all-separate, all-in-one, grouped, or single (from DB)

### PHASE 3: CLONE + INGEST — DONE
- [x] Cloned 5 Go MCP repos: sqlite-go, memory-go, memory-alt-go, pinecone-go, taskplanner-go
- [x] Ingested all source into SQLite: 239 files, 38,857 lines total
- [x] go_mcp_store.py provides query/search/update API

### PHASE 4: GO BUILD — COMPLETE
- [x] sqlite-go: BUILT (18 MB binary, 14 MB RAM, 5 tools, MCP works) — replaces Docker
- [x] memory-go: BUILT (19 MB binary, 10 MB RAM, 13 tools, MCP works) — replaces npx memory
- [x] memory-alt-go: BUILT (13 MB binary, 17 MB RAM, 11 tools, MCP works)
- [x] brain_server: OPTIMIZED (node --expose-gc, /mem-stats, /gc endpoints, LRU cache)
- [x] V8 flags research: NODE_OPTIONS can cut heap 94%, RSS 29%
- [x] Agent A: Custom Pinecone Go MCP — BUILT (11 MB binary, 1.3 MB RAM idle, 9 tools, MCP works)
- [x] Agent B: Custom Taskplanner Go MCP — BUILT (8.2 MB binary, 11 MB RAM, 7 tools, MCP works)
- [x] Agent C: ContextRAM Go shim — BUILT (8.2 MB binary, 11 MB RAM, 27 tools, MCP works)
- [x] Agent D: Unified dom_mcp binary — BUILT (17 MB binary, 11 MB RAM, 30 tools from 6 modules, MCP works)

### PHASE 5: IDE CUTOVER
- [ ] Kilo first (lowest risk)
- [ ] Devin second
- [ ] Cascade last (primary IDE)
- [ ] Verify: no Node processes spawn, RAM drops, startup is fast

### PHASE 6: CLEANUP
- [ ] Retire Node.js MCP files (BCL lifecycle `[@clean]` → `retired` status)
- [ ] Remove node_modules from MCP folders
- [ ] Remove Docker MCP image
- [ ] Uninstall npx packages
- [ ] Add VBStyle rules to `rule_tokens`

### PHASE 7: VERIFICATION (final)
- [ ] Graph check: all MCP tools accessible through single `dom_mcp` binary OR separate binaries
- [ ] RAM check: <15 MB per Go binary (vs ~200 MB currently for all Node.js MCP)
- [ ] Startup check: <100ms (vs 3-8 seconds currently)
- [ ] No Node.js processes running for MCP
- [ ] All IDEs functional with new config

---

## INDEX RESULTS

### MCP Server Inventory (verified 2026-06-28)

| # | Server | Language | RAM | Config Location | Go Replacement |
|---|--------|----------|-----|-----------------|----------------|
| 1 | contextram | Node.js | ~50 MB | ~/.codeium/windsurf/mcp_config.json | Agent C: Go shim (wraps Swift ctx) |
| 2 | pinecone | npx Node.js | ~40-70 MB | ~/.codeium/windsurf/mcp_config.json | Agent A: Custom Go MCP |
| 3 | filesystem | Go (already native!) | ~5 MB | ~/.codeium/windsurf/mcp_config.json | Already Go — keep as-is |
| 4 | taskplanner | Node.js | ~50 MB | ~/.codeium/windsurf/mcp_config.json | Agent B: Custom Go MCP |
| 5 | memory | npx Node.js | ~40 MB | ~/.config/kilo/kilo.json | memory-go: BUILT, 10 MB, 13 tools |
| 6 | devin-sqlite | Docker | ~100 MB | ~/.config/kilo/kilo.json | sqlite-go: BUILT, 14 MB, 5 tools |
| 7 | msearch | Python | ~10 MB | ~/.config/devin/config.json | Keep Python (wraps C binary, already efficient) |
| 8 | yahoo-mail | Node.js | ~30 MB | ~/.codeium/windsurf/mcp_config.json (disabled) | Disabled — no replacement needed |

### SQLite Code Store

| Server | Files | Lines | Binary Built | RAM |
|--------|-------|-------|-------------|-----|
| sqlite-go | 19 | 1,347 | 18 MB | 14 MB |
| memory-go | 25 | 9,023 | 19 MB | 10 MB |
| memory-alt-go | 30 | 5,221 | 13 MB | 17 MB |
| pinecone-go | 26 | 2,382 | 30 MB (REST, not MCP) | N/A |
| taskplanner-go | 139 | 20,837 | 9.8 MB (CLI, not MCP) | N/A |
| **Total** | **239** | **38,857** | | |

DB: `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/db/go_mcp_store.db`
API: `Dom_Mcp/db/go_mcp_store.py` (GoMcpStore class)

---

## BUILD PLAN

| # | Tool | Build Mode | Binary | RAM | Status |
|---|------|-----------|--------|-----|--------|
| 1 | sqlite | Separate | sqlite-go-mcp | 14 MB | DONE |
| 2 | memory | Separate | memory-go-mcp | 10 MB | DONE |
| 3 | pinecone | Custom Go MCP | pinecone-custom-mcp | 1.3 MB idle | DONE |
| 4 | taskplanner | Custom Go MCP | taskplanner-custom-mcp | 11 MB | DONE |
| 5 | contextram | Go shim | contextram-go-mcp | 11 MB | DONE |
| 6 | ALL | Unified | dom_mcp | 11 MB | DONE — 30 tools from 6 modules |

---

## VERIFICATION LOG

| Phase | Check | Result | Timestamp |
|-------|-------|--------|-----------|
| 4 | sqlite-go MCP protocol | PASS (initialize + tools/list) | 2026-06-28 |
| 4 | memory-go MCP protocol | PASS (initialize + tools/list, 13 tools) | 2026-06-28 |
| 4 | memory-alt-go MCP protocol | PASS (initialize + tools/list, 11 tools) | 2026-06-28 |
| 4 | sqlite-go RAM | 14 MB (vs 100 MB Docker) | 2026-06-28 |
| 4 | memory-go RAM | 10 MB (vs 40 MB npx) | 2026-06-28 |
| 4 | brain_server optimized | /mem-stats + /gc + LRU cache | 2026-06-28 |
| 4 | V8 flags research | NODE_OPTIONS cuts heap 94% | 2026-06-28 |
| 4 | Go code in SQLite DB | 269 files, 42,784 lines ingested (9 servers) | 2026-06-28 |
| 4 | pinecone-custom MCP protocol | PASS (initialize + tools/list, 9 tools) | 2026-06-28 |
| 4 | pinecone-custom RAM | 1.3 MB idle (vs 40-70 MB npx) | 2026-06-28 |
| 4 | taskplanner-custom MCP protocol | PASS (initialize + tools/list, 7 tools) | 2026-06-28 |
| 4 | taskplanner-custom RAM | 11 MB (vs 50 MB node) | 2026-06-28 |
| 4 | contextram-go MCP protocol | PASS (initialize + tools/list, 27 tools) | 2026-06-28 |
| 4 | contextram-go RAM | 11 MB (vs 50 MB node) | 2026-06-28 |
| 4 | dom_mcp unified MCP protocol | PASS (initialize + tools/list, 30 tools from 6 modules) | 2026-06-28 |
| 4 | dom_mcp unified RAM | 11 MB (vs ~280 MB all Node.js combined) | 2026-06-28 |

---

## Related Documents
- `DOM_MCP_PLAN.md` — Full architecture and migration plan
- `GC_PIPELINE.md` — BCL Code Lifecycle (code retirement process)
- `core/Dom_Unified/Config.py` — DomSystem service definitions
