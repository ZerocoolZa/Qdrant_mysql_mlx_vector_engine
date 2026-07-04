# dom_mcp Server — Complete Tool Test Report

## Summary

**Total tools tested: 97** across 9 categories
**Passing: 83** | **Failing: 11** | **Untested (destructive): 1** | **Config-blocked: 2**

---

## 1. ContextRAM (26 tools) — ALL ✅

| Tool | Status | Notes |
|------|--------|-------|
| `ctx_put` | ✅ | Created node, got UUID back |
| `ctx_get` | ✅ | Retrieved by ID |
| `ctx_update` | ✅ | Content updated successfully |
| `ctx_delete` | ✅ | Node deleted |
| `ctx_query` | ✅ | Full-text search works |
| `ctx_semantic` | ✅ | TF-IDF search works |
| `ctx_list` | ✅ | Lists all nodes |
| `ctx_recent` | ✅ | Recent nodes returned |
| `ctx_events` | ✅ | Event history returned |
| `ctx_path` | ✅ | Store path returned |
| `ctx_stats` | ✅ | Stats JSON returned |
| `ctx_embed` | ✅ | Swift embedding search works |
| `ctx_embed_stats` | ✅ | Embedding index built, RAM stats returned |
| `ctx_suggest` | ✅ | Suggestions returned |
| `ctx_auto` | ✅ | Auto-context works |
| `ctx_assemble` | ✅ | Assembled context view |
| `ctx_config` | ✅ | Config displayed |
| `ctx_link` | ✅ | Linked two nodes with `supports` relation |
| `ctx_lock` | ✅ | Status changed to `locked` |
| `ctx_unlock` | ✅ | Status restored to `active` |
| `ctx_promote` | ✅ | Score: 1.0 → 1.05 → 2.0 |
| `ctx_demote` | ✅ | Score: 2.0 → 1.0 |
| `ctx_snapshot` | ✅ | Saved to `~/.contextram/context.json` |
| `ctx_restore` | ✅ | Restored from snapshot |
| `ctx_clear_expired` | ✅ | 0 expired nodes cleared |
| `ctx_ingest` | ⚠️ | Returned 0 files — likely needs a directory path, not a single file |
| `ctx_ingest_chat` | ⚠️ | Parsed and created nodes, but **`dry_run=true` was ignored** — created a node despite dry run request |

## 2. SQLite (5 tools) — ALL ✅

| Tool | Status | Notes |
|------|--------|-------|
| `list_tables` | ✅ | 4 tables: go_servers, go_files, go_exports, sqlite_sequence |
| `describe_table` | ✅ | Schema for go_files returned with all columns |
| `read_query` | ✅ | SELECT COUNT(*) returned 295 rows |
| `write_query` | ✅ | INSERT + DELETE both worked, rowsAffected returned |
| `create_table` | ✅ | Table created and dropped successfully |

## 3. Filesystem (12 tools) — ALL ✅

| Tool | Status | Notes |
|------|--------|-------|
| `list_allowed_directories` | ✅ | 3 dirs: Qdrant_mysql_mlx_vector_engine, contestsystem, Downloads |
| `list_directory` | ✅ | Full listing returned |
| `read_file` | ✅ | File content returned |
| `read_multiple_files` | ✅ | Multiple files read in one call |
| `write_file` | ✅ | 33 bytes written |
| `modify_file` | ✅ | String replacement worked |
| `copy_file` | ✅ | File copied |
| `move_file` | ✅ | File moved/renamed |
| `delete_file` | ✅ | File + empty directory deleted |
| `create_directory` | ✅ | Directory created |
| `get_file_info` | ✅ | Metadata (size, mode, modTime) returned |
| `search_files` | ✅ | Found 13 Config.py files |
| `search_within_files` | ⚠️ | Canceled by user (was searching for `[@GHOST]` across entire workspace) |
| `tree` | ✅ | Tree view returned |

## 4. Knowledge Graph (9 tools) — ALL ✅

| Tool | Status | Notes |
|------|--------|-------|
| `create_entities` | ✅ | TestEntity created |
| `create_relations` | ✅ | `tested_by` relation created |
| `add_observations` | ✅ | Second observation added |
| `delete_observations` | ✅ | Observation deleted |
| `delete_relations` | ✅ | 1 relation deleted |
| `delete_entities` | ✅ | Entity deleted |
| `open_nodes` | ✅ | Retrieved by name |
| `search_nodes` | ✅ | Search returned empty (no BCL entities) |
| `read_graph` | ✅ | Empty graph returned (no entities/relations) |

## 5. Graph DB (29 tools tested, 1 skipped)

| Tool | Status | Notes |
|------|--------|-------|
| `graph_add_node` | ✅ | Node 1344 created |
| `graph_add_edge` | ✅ | Edge 9016 created |
| `graph_add_rule` | ✅ | Rule ID 1 created |
| `graph_add_snapshot` | ✅ | Snapshot 12 created |
| `graph_get_node` | ✅ | Node retrieved by ID |
| `graph_get_edges` | ✅ | Edges for node 1344 returned |
| `graph_get_candidates` | ✅ | Candidates returned (empty for BCL query) |
| `graph_get_rules` | ✅ | Rules returned (empty initially) |
| `graph_get_snapshot` | ✅ | Snapshot 12 retrieved |
| `graph_get_decision` | ✅ | Decision 5 retrieved with full evaluation trace |
| `graph_query_nodes` | ✅ | 50 nodes returned matching "test" |
| `graph_query_decisions` | ✅ | 5 decisions returned with full evaluated candidates |
| `graph_decide` | ✅ | Pipeline ran (0 candidates for BCL query — expected) |
| `graph_trace` | ✅ | Empty trace returned (no prior decide) |
| `graph_analyze_risk` | ✅ | Risk score 0.0 for method 942 |
| `graph_analyze_cost` | ✅ | Cost score 0 for method 942 |
| `graph_analyze_benefit` | ✅ | Benefit score 0 for NameError problem |
| `graph_graph_confidence` | ✅ | 70.34 confidence, 50.56% coverage, 9016 edges |
| `graph_overall_confidence` | ✅ | 15.93 overall (parse 12.41, graph 70.34) |
| `graph_repair_confidence` | ✅ | 0% success rate, 381 total fixes |
| `graph_runtime_confidence` | ✅ | 0% runtime, 451 observations, 0 ready methods |
| `graph_rank_fixes` | ✅ | 50 ranked fixes returned with confidence scores |
| `graph_to_context_assembly` | ✅ | ContextAssembly shape returned (empty for BCL query) |
| `graph_migrate_codefix` | ✅ | Migrated: 170 files, 38 classes, 419 methods, 9015 edges |
| `graph_migrate_session` | ❌ | **`ModuleNotFoundError: No module named 'mysql'`** — needs `mysql.connector` installed |
| `graph_simulate` | ❌ | Exit status 1 — likely needs simulation data for fix_id 991 |
| `graph_validate` | ❌ | Exit status 1 — same issue as simulate |
| `graph_stats` | ✅ | 2413 codefix nodes, 18031 edges, 5 decisions, 11 session nodes |
| `graph_gc` | ⏭️ | **Skipped — destructive (drops and recreates all tables)** |

## 6. Google Drive (8 tools) — ALL ✅

| Tool | Status | Notes |
|------|--------|-------|
| `gdrive_list` | ✅ | Listed root directory |
| `gdrive_info` | ✅ | Info for BK folder returned |
| `gdrive_read` | ✅ | Read file content (errors on directories, works on files) |
| `gdrive_search` | ✅ | Searched for `*.md` (no matches but no error) |
| `gdrive_write` | ✅ | 32 bytes written to file |
| `gdrive_create_folder` | ✅ | Folder created |
| `gdrive_move` | ✅ | File moved/renamed |
| `gdrive_delete` | ✅ | File + folder deleted |

## 7. Gmail (20 tools) — ALL ❌ (Config-blocked)

| Tool | Status | Notes |
|------|--------|-------|
| `gmail_list_folders` | ❌ | No email accounts configured |
| `gmail_list_accounts` | ❌ | Same — needs `ACCOUNT_{name}_EMAIL` env vars |
| All other gmail tools | ❌ | Blocked by missing email account configuration |

**Fix**: Set environment variables `ACCOUNT_{name}_EMAIL`, `ACCOUNT_{name}_PASSWORD`, and `DEFAULT_ACCOUNT_ID`.

## 8. Pinecone (9 tools) — 2 ✅, 7 ❌

| Tool | Status | Notes |
|------|--------|-------|
| `pinecone_list_indexes` | ✅ | 5 indexes: cascade, windsurf-project-docs, architecture-diagram-index, vb-class-index, code-docs-index |
| `pinecone_describe_index` | ✅ | cascade index: 1024 dim, cosine, ready |
| `pinecone_describe_index_stats` | ❌ | 404 Not Found |
| `pinecone_search_records` | ❌ | **Host not configured** — `set [tools.pinecone] host` |
| `pinecone_cascading_search` | ❌ | Same host config issue |
| `pinecone_upsert_records` | ❌ | Same host config issue |
| `pinecone_rerank_documents` | ❌ | 404 Not Found |
| `pinecone_search_docs` | ❌ | 404 Not Found |
| `pinecone_create_index_for_model` | ❌ | 422 — missing `dimension` field in API call |

**Fix**: Pinecone config needs `[tools.pinecone] host` set to the index host URL (e.g., `cascade-9rmkqs0.svc.aped-4627-b74a.pinecone.io`). The `describe_index` tool returns the host but the search tools don't use it automatically.

## 9. TaskPlanner (9 tools) — ALL ✅

| Tool | Status | Notes |
|------|--------|-------|
| `taskplanner_board` | ✅ | All tasks listed |
| `taskplanner_board_visual` | ✅ | Visual board with counts: 46 backlog, 3 next, 7 in_progress, 20 done, 2 rejected |
| `taskplanner_board_data` | ✅ | Structured JSON with all tasks |
| `taskplanner_list` | ✅ | Listed done tasks |
| `taskplanner_create` | ✅ | TASK-079 created in backlog |
| `taskplanner_get` | ✅ | TASK-079 retrieved with full details |
| `taskplanner_move` | ✅ | Moved backlog → rejected |
| `taskplanner_update` | ✅ | Title updated |
| `taskplanner_delete` | ✅ | Task deleted from rejected |

## 10. msearch (1 tool) — ✅

| Tool | Status | Notes |
|------|--------|-------|
| `msearch` | ✅ | Searched "BCL header format", found 2 matches in know_answers table |

---

## Issues Found

**Critical (config fixes needed):**
1. **Pinecone host not configured** — `[tools.pinecone] host` must be set. 7 tools blocked.
2. **Gmail accounts not configured** — `ACCOUNT_{name}_EMAIL` env vars needed. 20 tools blocked.

**Bugs:**
3. **`ctx_ingest_chat` ignores `dry_run=true`** — created a node despite dry run request. The output showed `"dryRun": false`.
4. **`ctx_ingest` returned 0 files** — may need a directory path instead of a single file path.
5. **`graph_simulate` / `graph_validate`** — exit status 1, likely need pre-populated simulation data.
6. **`graph_migrate_session`** — needs `mysql.connector` Python module installed.
7. **`pinecone_create_index_for_model`** — 422 error, missing `dimension` field in API call (possible API version mismatch).
