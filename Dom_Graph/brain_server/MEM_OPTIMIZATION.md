# [@GHOST]{[@file<brain_server/MEM_OPTIMIZATION.md>][@domain<graph>][@role<storage_api>][@auth<devin>][@date<2026-06-28>][@ver<1.1>]}

# Brain Server Memory Optimization — Summary

Target: `brain_server/server.js` (Node.js Express + better-sqlite3 REST API for the GUI AI Brain).

## Memory issues found

1. **Prepared statements re-created on every request.** Each handler called `db.prepare(...)` inline, allocating a fresh `Statement` object per request. Under load this produces steady heap growth and GC pressure.
2. **No SQLite memory pragmas.** Default journal mode (DELETE) and unbounded page cache raised RSS and read amplification.
3. **No memory introspection endpoint.** No way to observe `process.memoryUsage()` at runtime.
4. **No manual GC hook.** No way to force collection of freed statement/JSON buffers.
5. **No graceful shutdown.** On `SIGINT`/`SIGTERM` the DB handle was never closed and no timers were cleared — file handles and WAL files could leak.
6. **Expensive aggregate endpoint (`/api/stats`) re-ran 8 full scans on every call.** Frontends that poll it drove repeated table scans.
7. **No periodic GC.** Long-running process accumulated fragmented heap.

> Note: the server is essentially stateless (all data lives in SQLite), so there were **no unbounded global arrays/maps, no accumulating event listeners, and no orphaned `setInterval`s** in the original code. The main wins were allocation reduction and bounded caching.

## Changes applied (all functionality preserved)

### 1. Cached prepared statements (module scope)
All `db.prepare(...)` calls moved to a single `stmts` object created once at startup. Handlers now reuse `stmts.<name>`. The batch-insert transaction is also built once via `db.transaction(...)` and reused.

### 2. SQLite pragmas for bounded memory
```
journal_mode = WAL          // lower RSS under concurrent reads
synchronous = NORMAL        // safe with WAL, fewer fsyncs
cache_size = -20000         // 20 MB page-cache ceiling (env: BRAIN_SQLITE_CACHE_KB)
temp_store = MEMORY         // temp tables in RAM, not disk
mmap_size = 268435456       // 256 MB mmap ceiling for large reads
```

### 3. Bounded TTL-LRU cache for `/api/stats`
Added a small `TtlLru` class (max 8 entries, 5s TTL, env-tunable via `BRAIN_STATS_CACHE_TTL_MS`). `/api/stats` serves from cache when fresh; any write endpoint (`POST /api/models`, `/api/templates`, `/api/history`, `/api/history/batch`, `/api/runs`, `/api/layouts`) calls `bustStatsCache()` to invalidate. Cache is hard-capped (evicts oldest on overflow) and self-expiring — cannot grow unbounded.

### 4. `GET /mem-stats` endpoint
Returns `process.memoryUsage()` (rss, heapTotal, heapUsed, external, arrayBuffers) in bytes and MB, plus `gc_exposed`, `stats_cache_size`, and `uptime_sec`.

### 5. `POST /gc` endpoint
Calls `global.gc()` when the process was started with `--expose-gc`. Reports heap/rss before and after, plus `freed_heap_mb`. Returns `400` with guidance if gc is not exposed.

### 6. Periodic GC (optional)
If `--expose-gc` is present, a `setInterval` calls `global.gc()` every `BRAIN_GC_INTERVAL_MS` (default 60000 ms). The timer is `.unref()`-ed so it never keeps the event loop alive, and is cleared on shutdown.

### 7. Graceful shutdown
`SIGINT` / `SIGTERM` / server `error` event trigger `shutdown()`, which:
- clears the GC interval,
- clears the stats cache,
- closes the DB if open,
- then `process.exit(0)`.
A `shuttingDown` guard prevents double-cleanup.

### 8. Env-tunable knobs
| Env var | Default | Purpose |
|---|---|---|
| `BRAIN_PORT` | `7777` | listen port (unchanged) |
| `BRAIN_JSON_LIMIT` | `50mb` | express body limit |
| `BRAIN_SQLITE_CACHE_KB` | `20000` | SQLite page-cache KB budget |
| `BRAIN_STATS_CACHE_TTL_MS` | `5000` | `/api/stats` cache TTL |
| `BRAIN_GC_INTERVAL_MS` | `60000` | periodic gc interval (0 disables) |

## API surface — preserved + added

Preserved (unchanged behavior): `GET /health`, `POST|GET /api/models`, `GET /api/models/:id`, `POST|GET /api/templates`, `GET /api/templates/:name`, `POST /api/history`, `POST /api/history/batch`, `GET /api/history`, `GET /api/history/latest`, `POST|GET /api/runs`, `POST|GET /api/layouts`, `GET /api/layouts/:id`, `GET /api/stats`.

Added: `GET /mem-stats`, `POST /gc`.

## Verification

Started with `BRAIN_PORT=7799 node --expose-gc server.js`:

- `/mem-stats` → `{"rss_mb":52.02,"heap_used_mb":7.11,"gc_exposed":true,...}`
- `POST /gc` → `{"status":"gc_invoked","freed_heap_mb":1.65,...}`
- `/health`, `/api/stats`, `/api/models`, `/api/templates`, `/api/history`, `/api/runs`, `/api/layouts` all return correct data against the existing `brain_storage.db`.

## Recommended run command

```
node --expose-gc server.js
```

This enables `POST /gc` and the periodic GC interval. Without `--expose-gc` the server still runs; `/gc` returns a 400 with guidance and the periodic timer is not installed.
