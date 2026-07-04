# DUPLICATES TO CLEANUP — Standalone Go MCP Binaries

> **Purpose:** This report identifies standalone Go MCP binaries in the `Dom_Mcp/` directory
> that are **already integrated** into the unified `dom_mcp` binary at
> `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/dom_mcp/dom_mcp`.
>
> **No files were deleted or moved.** This is a reference document for the user to decide
> what to archive or remove.
>
> **Generated:** 2025-06-29
> **Unified binary size:** 17,943,698 bytes (~17.1 MB) — contains ALL 7 modules in one binary.

---

## Summary Table

| # | Duplicate Binary | Size | dom_mcp Module | Unique Features? | Recommended Action |
|---|---|---|---|---|---|
| 1 | `contextram-go/contextram-go-mcp` | 8,622,210 (8.2 MB) | `contextram` | Minor — richer schemas/config flags | Archive source, delete binary |
| 2 | `memory-go/memory-go-mcp` | 19,356,802 (18.5 MB) | `memory` | **YES — 4 extra tools, SQLite/FTS5, OAuth, Resources/Prompts** | **DO NOT DELETE — port features first** |
| 3 | `memory-go/memory-mcp` | 19,356,802 (18.5 MB) | `memory` | Identical to #2 (same binary, different name) | Delete binary (duplicate of #2) |
| 4 | `memory-alt-go/memory-alt-go-mcp` | 13,215,714 (12.6 MB) | `memory` | **YES — FTS5 search, list_entity_names/types** | **DO NOT DELETE — port features first** |
| 5 | `memory-alt-go/memory-mcp` | 13,215,714 (12.6 MB) | `memory` | Identical to #4 (same binary, different name) | Delete binary (duplicate of #4) |
| 6 | `pinecone-custom/pinecone-custom-mcp` | 11,388,882 (10.9 MB) | `pinecone` | **YES — auto host resolution, richer create-index** | **DO NOT DELETE — port features first** |
| 7 | `pinecone-go/pinecone-go-mcp` | 31,517,954 (30.1 MB) | `pinecone` | **YES — completely different: GitHub repo indexer + HTTP REST API** | **DO NOT DELETE — not a true duplicate** |
| 8 | `pinecone-go/pinecone-mcp` | 31,517,954 (30.1 MB) | `pinecone` | Identical to #7 (same binary, different name) | Delete binary (duplicate of #7) |
| 9 | `sqlite-go/sqlite-go-mcp` | 18,404,466 (17.5 MB) | `sqlite` | **YES — multi-statement + transaction support** | **DO NOT DELETE — port features first** |
| 10 | `sqlite-go/sqlite-mcp` | 18,404,466 (17.5 MB) | `sqlite` | Identical to #9 (same binary, different name) | Delete binary (duplicate of #9) |

**Total disk space consumed by duplicate binaries:** ~185 MB
**Total disk space if only unique-source binaries kept:** ~93 MB
**Unified dom_mcp binary (replaces all):** ~17.1 MB

---

## Detailed Analysis Per Duplicate

---

### 1. contextram-go/contextram-go-mcp

- **Binary path:** `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/contextram-go/contextram-go-mcp`
- **Binary size:** 8,622,210 bytes (8.2 MB)
- **Source:** `contextram-go/main.go` (566 lines)
- **dom_mcp module:** `dom_mcp/tools/contextram.go` (360 lines)
- **Replaced by:** dom_mcp `contextram` module

#### What It Does
Both the standalone `contextram-go-mcp` and the dom_mcp `contextram` module are **protocol
adapters** that wrap the same Swift `ctx` binary as a subprocess. Neither implements
ContextRAM logic — they both spawn `/Users/wws/contestsystem/ContextRAMSwift/.build/release/ctx`
and map MCP tool calls to `ctx` subcommand argv.

#### Tool Comparison
Both expose the same **27 tools**: `ctx_put`, `ctx_get`, `ctx_update`, `ctx_delete`,
`ctx_list`, `ctx_query`, `ctx_link`, `ctx_promote`, `ctx_demote`, `ctx_lock`, `ctx_unlock`,
`ctx_stats`, `ctx_events`, `ctx_assemble`, `ctx_snapshot`, `ctx_restore`, `ctx_recent`,
`ctx_clear_expired`, `ctx_path`, `ctx_ingest`, `ctx_ingest_chat`, `ctx_semantic`,
`ctx_embed`, `ctx_embed_stats`, `ctx_auto`, `ctx_suggest`, `ctx_config`.

#### Unique Features in Standalone (NOT in dom_mcp)
1. **Richer JSON schemas** — the standalone has `enum` constraints for `type`, `status`,
   `authority` fields, and documents valid values. dom_mcp uses free-form strings.
2. **More config options** for `ctx_config`: `store_path`, `coreml_dir`, `mysql_table`,
   `mysql_text_column`, `mysql_password_env` — dom_mcp is missing these 5 config flags.
3. **`--score` and `--source` flags** for `ctx_put` and `ctx_update` — dom_mcp does not
   expose `score` or `source` parameters.
4. **`--chunk-size`, `--chunk-overlap`, `--max-file-size`** for `ctx_ingest` — dom_mcp
   is missing these 3 ingest parameters.
5. **`--min-chars`** for `ctx_ingest_chat` — dom_mcp is missing this parameter.
6. **`--dimensions`, `--min-token-length`, `--no-ngrams`, `--json`** for `ctx_embed` —
   dom_mcp only passes `--limit`, `--tag`, `--type`.
7. **`--dimensions`, `--min-token-length`, `--no-ngrams`** for `ctx_embed_stats` —
   dom_mcp only passes `--tag`, `--type`.

#### Unique Features in dom_mcp (NOT in standalone)
1. **Configurable timeout** — dom_mcp supports a configurable timeout (default 10s) with
   `context.DeadlineExceeded` handling. The standalone has no explicit timeout.
2. **stderr capture** — dom_mcp captures stderr separately for better error messages.

#### Verdict
The standalone has **minor schema/parameter richness** that dom_mcp lacks. The missing
parameters (`score`, `source`, chunk sizing, embedding dimensions) could be useful but
are not critical. The core functionality is identical.

**Recommended Action:** Port the missing config flags and parameters to dom_mcp, then
archive the standalone source and delete the binary.

---

### 2. memory-go/memory-go-mcp

- **Binary path:** `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/memory-go/memory-go-mcp`
- **Binary size:** 19,356,802 bytes (18.5 MB)
- **Source:** `memory-go/main.go` (1,645 lines) + `storage/` (6 files) + `auth/` (5 files)
- **dom_mcp module:** `dom_mcp/tools/memory.go` (544 lines)
- **Replaced by:** dom_mcp `memory` module

#### What It Does
A full-featured Memory MCP server with knowledge graph storage. The standalone is a
mature, production-grade implementation with layered storage architecture.

#### Tool Comparison

| Tool | dom_mcp | memory-go |
|------|---------|-----------|
| create_entities | YES | YES |
| create_relations | YES | YES |
| add_observations | YES | YES |
| delete_entities | YES | YES |
| delete_observations | YES | YES |
| delete_relations | YES | YES |
| read_graph | YES | YES (with summary/full modes) |
| search_nodes | YES | YES (FTS5 with snippets) |
| open_nodes | YES | YES |
| **merge_entities** | NO | **YES** |
| **update_entities** | NO | **YES** (update entity type) |
| **update_observations** | NO | **YES** (replace observation text) |
| **detect_conflicts** | NO | **YES** (find duplicates/contradictions) |

#### Unique Features in Standalone (NOT in dom_mcp)
1. **4 extra tools:** `merge_entities`, `update_entities`, `update_observations`,
   `detect_conflicts` — these are significant knowledge graph management features.
2. **SQLite storage backend** with WAL mode, FTS5 full-text search, BM25 ranking,
   caching, busy timeout, foreign key constraints, cascading deletes.
3. **JSONL storage backend** with automatic migration to SQLite.
4. **FTS5 full-text search** with BM25 ranking and automatic LIKE-based fallback.
   dom_mcp uses simple substring matching.
5. **Search priority ranking:** name exact match (100) > name partial (80) > type (50) >
   observation content (20). dom_mcp has basic ranking (100/50/20) but no FTS5.
6. **Search results with snippets** — matched observation snippets (max 2 per entity),
   observation counts, relation counts, 1-hop related entities.
7. **Graph summary mode** — `read_graph` supports "summary" mode returning entity/relation
   counts, type distribution, entity name list (with pagination). dom_mcp returns full graph only.
8. **OAuth 2.1 authentication** — full OAuth server with PKCE, dynamic client registration,
   token rotation, refresh token replay grace window, persistent SQLite store.
9. **SSE and Streamable HTTP transports** — dom_mcp only supports stdio.
10. **MCP Resources:** `memory://graph/summary`, `memory://graph/types`,
    `memory://entities/{name}` template — allows AI clients to passively load memory context.
11. **MCP Prompts:** `memory-recall`, `memory-save`, `memory-review` — standardized memory
    operation templates that appear as clickable actions in Claude Desktop / VS Code.
12. **CORS support** for HTTP/SSE transports.
13. **Streamable HTTP compatibility** — handles JSON-RPC client responses with 202 Accepted.
14. **Config file support** via command-line flags and environment variables.
15. **Migration tool** — `--migrate` command for JSONL to SQLite migration with dry-run,
    force, and progress reporting.

#### Unique Features in dom_mcp (NOT in standalone)
None — dom_mcp memory is a strict subset of functionality.

#### Verdict
The standalone `memory-go` is **significantly more feature-rich** than the dom_mcp memory
module. It has 4 extra tools, SQLite/FTS5 storage, OAuth, SSE/HTTP transports, MCP
Resources, and MCP Prompts. This is the most feature-divergent duplicate.

**Recommended Action:** **DO NOT DELETE.** Port the 4 extra tools (`merge_entities`,
`update_entities`, `update_observations`, `detect_conflicts`), FTS5 search, and graph
summary mode to dom_mcp first. Consider also porting MCP Resources/Prompts. After porting,
archive the standalone source and delete the binary.

---

### 3. memory-go/memory-mcp

- **Binary path:** `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/memory-go/memory-mcp`
- **Binary size:** 19,356,802 bytes (18.5 MB)
- **Source:** Same as #2 — this is a renamed copy of the same binary.
- **Replaced by:** dom_mcp `memory` module

#### Verdict
This is a **byte-identical copy** of `memory-go-mcp` (same size, same timestamp pattern).
It exists as a convenience alias.

**Recommended Action:** Delete this binary (it's a duplicate of #2). Keep #2 until features
are ported to dom_mcp.

---

### 4. memory-alt-go/memory-alt-go-mcp

- **Binary path:** `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/memory-alt-go/memory-alt-go-mcp`
- **Binary size:** 13,215,714 bytes (12.6 MB)
- **Source:** `memory-alt-go/main.go` (212 lines) + `tools.go` (569 lines) + `sql.go` +
  `internal/dbstore/` + `sql/` migrations
- **dom_mcp module:** `dom_mcp/tools/memory.go` (544 lines)
- **Replaced by:** dom_mcp `memory` module

#### What It Does
An alternative Memory MCP server implementation using SQLite with sqlc-generated queries
and FTS5 full-text search. This is a different, independent implementation from memory-go.

#### Tool Comparison

| Tool | dom_mcp | memory-alt-go |
|------|---------|---------------|
| create_entities | YES | YES |
| create_relations | YES | YES |
| add_observations | YES | YES (single entity per call) |
| delete_entities | YES | YES |
| delete_observations | YES | YES (single entity per call) |
| delete_relations | YES | YES |
| read_graph | YES | YES |
| search_nodes | YES | **search_entities_by_observation** (FTS5) |
| open_nodes | YES | **get_entities** (with relations) |
| **list_entity_names** | NO | **YES** |
| **list_entity_types** | NO | **YES** |

#### Unique Features in Standalone (NOT in dom_mcp)
1. **2 extra tools:** `list_entity_names`, `list_entity_types` — useful for graph
   exploration and schema discovery.
2. **FTS5 full-text search** via `search_entities_by_observation` — uses SQLite FTS5
   for observation-based search. dom_mcp uses simple substring matching.
3. **sqlc-generated database queries** — type-safe SQL queries generated from SQL files,
   with a proper migration system (`sql/` directory with migration files).
4. **Search returns related relations** — `search_entities_by_observation` returns both
   matching entities AND their relations in one call.
5. **Structured logging** with `slog` (Go 1.21+ structured logging).
6. **MCP server instructions** — provides a detailed system prompt to the AI client
   explaining available tools and best practices.
7. **Output schemas** — uses `mcp.WithOutputSchema` for typed results.

#### Unique Features in dom_mcp (NOT in standalone)
1. **Batch operations** — dom_mcp's `add_observations` and `delete_observations` accept
   arrays of entities. The standalone only handles one entity per call.
2. **Search ranking** — dom_mcp ranks search results (name=100, type=50, obs=20).
   The standalone returns unranked FTS5 results.

#### Verdict
The standalone `memory-alt-go` has unique tools (`list_entity_names`, `list_entity_types`)
and FTS5 search. It's a cleaner, more minimal implementation than memory-go but lacks
batch operations.

**Recommended Action:** **DO NOT DELETE.** Port `list_entity_names` and `list_entity_types`
to dom_mcp. Consider FTS5 search upgrade. After porting, archive source and delete binary.

---

### 5. memory-alt-go/memory-mcp

- **Binary path:** `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/memory-alt-go/memory-mcp`
- **Binary size:** 13,215,714 bytes (12.6 MB)
- **Source:** Same as #4 — this is a renamed copy of the same binary.

#### Verdict
**Byte-identical copy** of `memory-alt-go-mcp`.

**Recommended Action:** Delete this binary (duplicate of #4). Keep #4 until features are ported.

---

### 6. pinecone-custom/pinecone-custom-mcp

- **Binary path:** `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/pinecone-custom/pinecone-custom-mcp`
- **Binary size:** 11,388,882 bytes (10.9 MB)
- **Source:** `pinecone-custom/main.go` (510 lines)
- **dom_mcp module:** `dom_mcp/tools/pinecone.go` (431 lines)
- **Replaced by:** dom_mcp `pinecone` module

#### What It Does
Both are native Go MCP servers for the Pinecone vector database API. Both make HTTP
calls to `https://api.pinecone.io` and index data-plane hosts.

#### Tool Comparison
Both expose the same **9 tools**: `list-indexes`, `describe-index`, `describe-index-stats`,
`search-docs`, `create-index-for-model`, `upsert-records`, `search-records`,
`cascading-search`, `rerank-documents`.

#### Unique Features in Standalone (NOT in dom_mcp)
1. **Auto host resolution** — `resolveHost(indexName)` fetches the index description and
   extracts the `host` field automatically. dom_mcp requires explicit `host` config.
   This is a **significant usability advantage** — users don't need to manually configure
   the index host URL.
2. **Richer `create-index-for-model`** — supports `dimension`, `cloud`, `region`,
   `deletionProtection`, `namespace`, `modelType`, `modelProvider`, and field mapping
   (`field: {type: "text", name: "chunk_text"}`). dom_mcp only supports `name`, `model`,
   `metric` and uses a simple `embed` object.
3. **Serverless spec** — the standalone creates indexes with `spec.serverless.cloud` and
   `spec.serverless.region`. dom_mcp doesn't set spec at all.
4. **`returnDocuments`** option for `rerank-documents` — dom_mcp doesn't expose this.
5. **`region`** option for `search-docs` — dom_mcp doesn't expose this.
6. **Flexible `search-records` query** — accepts a raw `query` object map, allowing
   arbitrary Pinecone query structures. dom_mcp hardcodes the query format.
7. **Flexible `cascading-search`** — accepts raw `query` and `rerank` object maps.
   dom_mcp hardcodes the rerank model as `bge-reranker-v2-m3`.
8. **Error truncation** — error responses are truncated to 500 chars for readability.
9. **Pretty-printed JSON output** — `jsonText()` pretty-prints all API responses.
   dom_mcp returns raw response strings.

#### Unique Features in dom_mcp (NOT in standalone)
1. **Configurable API key from env or config** — dom_mcp supports `api_key_env` (env var
   name) with fallback to `api_key` config value. The standalone only reads
   `PINECONE_API_KEY` env var.
2. **Configurable timeout** — dom_mcp supports configurable timeout (default 30s).
   The standalone uses fixed 60s timeout.
3. **Context-aware HTTP requests** — dom_mcp uses `http.NewRequestWithContext` for
   proper context cancellation. The standalone uses `http.NewRequest` without context.

#### Verdict
The standalone `pinecone-custom` has **auto host resolution** (a major usability feature)
and significantly richer `create-index-for-model` options. dom_mcp has better config
flexibility for API key and timeout.

**Recommended Action:** **DO NOT DELETE.** Port `resolveHost()` auto-resolution and the
richer `create-index-for-model` parameters to dom_mcp. After porting, archive source and
delete binary.

---

### 7. pinecone-go/pinecone-go-mcp

- **Binary path:** `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/pinecone-go/pinecone-go-mcp`
- **Binary size:** 31,517,954 bytes (30.1 MB)
- **Source:** `pinecone-go/` — full project with `main.go`, `config/`, `database/`,
  `domain/`, `handlers/`, `helper/`, `middleware/`, `models/`, `repository/`, `response/`,
  `router/`, `usecase/`
- **dom_mcp module:** `dom_mcp/tools/pinecone.go` (431 lines)
- **Replaced by:** dom_mcp `pinecone` module (partially)

#### What It Does
**This is NOT a standard Pinecone MCP server.** It is a **GitHub repository indexer and
code search HTTP REST API** that uses Pinecone as its vector backend. It runs as a Gin
HTTP web server (not MCP stdio) on port 8081.

#### Architecture
- **Gin HTTP REST API** — not MCP protocol at all
- **OAuth authentication** with GitHub (login/callback flow)
- **Pinecone vector database** as backend for code embeddings
- **PostgreSQL/MySQL** for user/repository metadata

#### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/auth/login` | GET | GitHub OAuth login |
| `/auth/callback` | GET | OAuth callback |
| `/search` | POST | Vector search on indexed repositories |
| `/search/summary` | POST | Vector search with AI-generated summary |
| `/index` | POST | Index a GitHub repository (clones, parses, embeds) |
| `/repositories` | GET | List indexed repositories |
| `/profile` | GET | Get user profile |

#### Unique Features (NOT in dom_mcp)
1. **GitHub repository indexing** — clones repos, parses code files, creates embeddings,
   and stores in Pinecone. dom_mcp has no indexing capability.
2. **AI-powered search summaries** — `/search/summary` generates AI summaries of search
   results. dom_mcp has no summarization.
3. **OAuth authentication** with GitHub.
4. **User management** — multi-user with per-user repository tracking.
5. **Repository management** — track and list indexed repositories.
6. **HTTP REST API** — accessible via HTTP, not just MCP stdio.
7. **CORS support** for web UI integration.
8. **Clean architecture** — config, database, domain, handlers, middleware, models,
   repository, response, router, usecase layers.

#### Verdict
**This is NOT a true duplicate of the dom_mcp pinecone module.** It's a completely
different application — a GitHub code search and indexing platform that happens to use
Pinecone as its vector backend. The dom_mcp pinecone module provides direct Pinecone API
access (list indexes, search records, upsert, etc.), while this provides higher-level
code search functionality.

**Recommended Action:** **DO NOT DELETE.** This is a separate application, not a duplicate.
Reclassify it as a standalone project. Consider renaming the directory to avoid confusion
with the actual Pinecone MCP duplicates.

---

### 8. pinecone-go/pinecone-mcp

- **Binary path:** `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/pinecone-go/pinecone-mcp`
- **Binary size:** 31,517,954 bytes (30.1 MB)
- **Source:** Same as #7 — this is a renamed copy of the same binary.

#### Verdict
**Byte-identical copy** of `pinecone-go-mcp`.

**Recommended Action:** Delete this binary (duplicate of #7). Keep #7 as it's a unique
application, not a true duplicate.

---

### 9. sqlite-go/sqlite-go-mcp

- **Binary path:** `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/sqlite-go/sqlite-go-mcp`
- **Binary size:** 18,404,466 bytes (17.5 MB)
- **Source:** `sqlite-go/` — `main.go` + `server/` (server.go, sqlite.go, tools/) +
  `config/` + `logger/`
- **dom_mcp module:** `dom_mcp/tools/sqlite.go` (236 lines)
- **Replaced by:** dom_mcp `sqlite` module

#### What It Does
Both are SQLite MCP servers providing query tools. The standalone is based on
`github.com/cnosuke/mcp-sqlite` with a clean architecture.

#### Tool Comparison
Both expose the same **5 tools**: `read_query`, `write_query`, `create_table`,
`list_tables`, `describe_table`.

#### Unique Features in Standalone (NOT in dom_mcp)
1. **Multi-statement support** — `write_query` splits queries by semicolons and executes
   each statement sequentially, reporting per-statement results. dom_mcp executes a single
   statement only.
2. **Transaction support** — `write_query` supports `BEGIN`, `COMMIT`, `ROLLBACK` within
   multi-statement queries, with automatic rollback on error. dom_mcp has no transaction
   support.
3. **Per-statement result reporting** — each statement gets its own result with
   `Statement`, `Operation`, `Success`, `RowsAffected`, `LastInsertID`, `Error`.
4. **Structured logging** with `go.uber.org/zap` — debug, info, warn, error levels.
   dom_mcp has no logging.
5. **Config file support** — reads `config.yml` for database path, debug mode, log config.
   dom_mcp takes path via config only.
6. **Docker support** — includes `Dockerfile` and `.dockerignore`.
7. **MCP error hooks** — registers `hooks.AddOnError` for structured error logging.
8. **CLI framework** — uses `urfave/cli/v2` for clean CLI with `server` subcommand.
9. **WITH query support** — dom_mcp supports `WITH` in `read_query` but the standalone
   only checks for `SELECT` prefix. (This is actually a dom_mcp advantage.)

#### Unique Features in dom_mcp (NOT in standalone)
1. **WITH/CTE query support** — dom_mcp's `read_query` accepts both `SELECT` and `WITH`
   prefixed queries. The standalone only accepts `SELECT`.
2. **Identifier quoting** — dom_mcp has `quoteIdent()` for safe table name interpolation
   in `describe_table`. The standalone uses `fmt.Sprintf` without quoting.
3. **Column type details** — dom_mcp's `describe_table` returns `cid`, `notnull`,
   `default`, `pk` as structured JSON. The standalone returns similar but with slightly
   different formatting.
4. **JSON result format** — dom_mcp returns structured JSON with `columns`, `rows`,
   `rowCount`. The standalone returns a JSON array of row maps.

#### Verdict
The standalone `sqlite-go` has **critical multi-statement and transaction support** that
dom_mcp lacks. This is important for complex database operations. dom_mcp has better
`WITH` query support and identifier quoting.

**Recommended Action:** **DO NOT DELETE.** Port multi-statement support and transaction
handling (BEGIN/COMMIT/ROLLBACK) to dom_mcp. Also add `WITH` query support to the
standalone's read_query if keeping it. After porting, archive source and delete binary.

---

### 10. sqlite-go/sqlite-mcp

- **Binary path:** `/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/sqlite-go/sqlite-mcp`
- **Binary size:** 18,404,466 bytes (17.5 MB)
- **Source:** Same as #9 — this is a renamed copy of the same binary.

#### Verdict
**Byte-identical copy** of `sqlite-go-mcp`.

**Recommended Action:** Delete this binary (duplicate of #9). Keep #9 until features are ported.

---

## Action Plan

### Phase 1: Safe to Delete Immediately (Byte-Identical Duplicates)

These are renamed copies of the same binary — no unique content:

| Binary | Duplicate Of | Size | Action |
|--------|-------------|------|--------|
| `memory-go/memory-mcp` | `memory-go/memory-go-mcp` | 18.5 MB | **Delete** |
| `memory-alt-go/memory-mcp` | `memory-alt-go/memory-alt-go-mcp` | 12.6 MB | **Delete** |
| `pinecone-go/pinecone-mcp` | `pinecone-go/pinecone-go-mcp` | 30.1 MB | **Delete** |
| `sqlite-go/sqlite-mcp` | `sqlite-go/sqlite-go-mcp` | 17.5 MB | **Delete** |

**Total space recovered:** ~78.7 MB

### Phase 2: Port Features Before Deleting

These have unique features that should be ported to dom_mcp first:

| Binary | Unique Features to Port | Priority |
|--------|------------------------|----------|
| `memory-go/memory-go-mcp` | 4 extra tools (merge/update/detect_conflicts), FTS5, OAuth, Resources/Prompts | **HIGH** |
| `memory-alt-go/memory-alt-go-mcp` | list_entity_names, list_entity_types, FTS5 search | **MEDIUM** |
| `pinecone-custom/pinecone-custom-mcp` | Auto host resolution, richer create-index | **HIGH** |
| `sqlite-go/sqlite-go-mcp` | Multi-statement + transaction support | **HIGH** |
| `contextram-go/contextram-go-mcp` | Missing config flags & parameters | **LOW** |

### Phase 3: Reclassify (Not a True Duplicate)

| Binary | Reason | Action |
|--------|--------|--------|
| `pinecone-go/pinecone-go-mcp` | GitHub repo indexer HTTP API, not a Pinecone MCP | **Keep as separate project** |

### Phase 4: Archive Source After Porting

After porting unique features to dom_mcp, archive the standalone source directories
(not just binaries) to preserve history:

```
contextram-go/     → archive
memory-go/         → archive (after porting 4 tools + FTS5 + OAuth)
memory-alt-go/     → archive (after porting list_entity_names/types)
pinecone-custom/   → archive (after porting resolveHost + richer create-index)
sqlite-go/         → archive (after porting multi-statement + transactions)
```

---

## Feature Porting Checklist

### dom_mcp memory module needs:
- [ ] `merge_entities` tool (merge two entities, migrate observations + relations)
- [ ] `update_entities` tool (update entity type)
- [ ] `update_observations` tool (replace observation text)
- [ ] `detect_conflicts` tool (find duplicate/contradictory observations)
- [ ] `list_entity_names` tool (from memory-alt-go)
- [ ] `list_entity_types` tool (from memory-alt-go)
- [ ] FTS5 full-text search (from memory-go or memory-alt-go)
- [ ] Graph summary mode for `read_graph` (summary vs full)
- [ ] Search result snippets and related entities
- [ ] Consider: SQLite storage backend, MCP Resources, MCP Prompts

### dom_mcp pinecone module needs:
- [ ] `resolveHost(indexName)` — auto-resolve index host from index name
- [ ] Richer `create-index-for-model`: dimension, cloud, region, deletionProtection,
      namespace, modelType, modelProvider, field mapping
- [ ] `returnDocuments` option for `rerank-documents`
- [ ] `region` option for `search-docs`
- [ ] Flexible query/rerank object maps for `search-records` and `cascading-search`
- [ ] Pretty-printed JSON output

### dom_mcp sqlite module needs:
- [ ] Multi-statement support (semicolon splitting in `write_query`)
- [ ] Transaction support (BEGIN/COMMIT/ROLLBACK in `write_query`)
- [ ] Per-statement result reporting

### dom_mcp contextram module needs:
- [ ] Missing config flags: `store_path`, `coreml_dir`, `mysql_table`,
      `mysql_text_column`, `mysql_password_env`
- [ ] Missing `ctx_put` parameters: `score`, `source`
- [ ] Missing `ctx_update` parameters: `score`, `source`
- [ ] Missing `ctx_ingest` parameters: `chunk_size`, `chunk_overlap`, `max_file_size`
- [ ] Missing `ctx_ingest_chat` parameter: `min_chars`
- [ ] Missing `ctx_embed` parameters: `dimensions`, `min_token_length`, `no_ngrams`, `json`
- [ ] Missing `ctx_embed_stats` parameters: `dimensions`, `min_token_length`, `no_ngrams`

---

## Conclusion

The unified `dom_mcp` binary (17.1 MB) successfully replaces the core functionality of
all standalone binaries. However, **5 of the 10 duplicate binaries have unique features**
that should be ported to dom_mcp before deletion:

1. **memory-go** — 4 extra tools + SQLite/FTS5 + OAuth + Resources/Prompts (most critical)
2. **memory-alt-go** — 2 extra tools + FTS5 search
3. **pinecone-custom** — auto host resolution + richer index creation
4. **sqlite-go** — multi-statement + transaction support
5. **contextram-go** — missing parameters (low priority)

**pinecone-go** is not a true duplicate — it's a GitHub repository indexing platform
and should be kept as a separate project.

**4 binaries are byte-identical renamed copies** and can be safely deleted immediately,
recovering ~78.7 MB.
