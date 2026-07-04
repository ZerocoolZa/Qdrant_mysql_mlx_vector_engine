//[@GHOST]{file_path="Cascade_toolStack/bcl_units/CPSD_SPEC.md" date="2026-07-04" author="Devin" session_id="cpsd-microkernel" context="CPSD engineering specification — comprehensive reference for building the Cascade Persistent Data Service microkernel"}

# CPSD — Cascade Persistent Data Service

**Engineering Specification v1.0.0**
**Date:** 2026-07-04
**Author:** Devin
**Session:** cpsd-microkernel
**Status:** Active — reference for phased build

---

## Table of Contents

1. [Overview](#1-overview)
2. [9-Layer Architecture](#2-9-layer-architecture)
3. [20 BND Nodes](#3-20-bnd-nodes)
4. [Dependency Matrix](#4-dependency-matrix)
5. [Build Order](#5-build-order)
6. [Protocol](#6-protocol)
7. [Security Model](#7-security-model)
8. [Storage Driver Interface](#8-storage-driver-interface)
9. [Query Registry](#9-query-registry)
10. [State Machines](#10-state-machines)
11. [File Structure](#11-file-structure)
12. [Config](#12-config)

---

## 1. Overview

### 1.1 What CPSD Is

CPSD (Cascade Persistent Data Service) is a C microkernel that serves as the **single door** into MySQL and all future data backends. It is a long-running daemon process that accepts client connections over a Unix domain socket, authenticates them, validates and executes only registered prepared statements, and returns results. No client ever sends raw SQL. No client ever touches a backend connection directly.

CPSD is the gatekeeper. Every read, every write, every schema inspection, every administrative action passes through its layered pipeline. It is the chokepoint where security, validation, logging, caching, and destruction-guard enforcement all converge.

### 1.2 Why CPSD Exists

The Cascade toolstack accumulated dozens of BCL units that each independently connected to MySQL using ad-hoc SQL strings. This created three critical problems:

1. **SQL injection surface.** String-concatenated SQL scattered across 40+ C files. Any unit could issue `DROP TABLE` or `DELETE FROM` with no guard. A single typo or malicious input could destroy the knowledge base.

2. **No central security.** Every unit connected with root credentials. There was no role separation, no rate limiting, no audit trail. Any process could do anything to the database.

3. **No observability.** Queries were fire-and-forget. No registry of what SQL existed, no query log, no WAL for recovery, no metrics on which queries ran and how long they took.

CPSD solves all three by being the **only door**:

- **Prepared statements only.** Clients send a numeric `cmd_id` and typed parameters. CPSD looks up the SQL template from an internal registry, prepares it, binds the parameters, and executes. SQL injection is structurally impossible — the client never controls the SQL text.

- **Destruction guard.** Every query passes through `destruction_guard_check()` before execution. Destructive operations (`DROP`, `TRUNCATE`, `DELETE` without `WHERE`, `ALTER` dropping columns) require an explicit `confirm` flag. Even admin role cannot bypass this without the guard acknowledging the destruction.

- **RBAC security.** Six roles (admin, writer, reader, ai_agent, cli, internal) with a permission matrix mapping role × backend × operation. Clients authenticate with a token file on disk; the token maps to a role. Rate limiting per-client. Every action audit-logged.

- **Connection pooling.** CPSD maintains a pool of backend connections. Clients do not open their own. The pool is sized, health-checked, and recycled. This caps the total connection count to the backend regardless of how many CPSD clients exist.

- **Query registry.** All SQL is registered at startup with a numeric ID, a name, the SQL template, the backend, the operation type, and parameter type signatures. Clients reference queries by ID. The registry is the single source of truth for what SQL the system can run.

- **WAL.** Every write operation is written to a write-ahead log before execution. On crash recovery, the WAL is replayed. This gives durability without relying on the backend's own binary log.

- **Plugin system.** Hook points (pre-query, post-query, pre-auth, post-auth, pre-write, post-write, on-connect, on-disconnect, on-health, on-config-reload) allow plugins to intercept and modify behavior without modifying the kernel.

### 1.3 Design Principles

- **Single door.** One process, one socket, one set of credentials. No backdoors.
- **Prepared statements only.** No raw SQL from clients. Ever.
- **Destruction guard.** Destructive operations require explicit confirmation. The guard is a hard gate, not advisory.
- **Layered.** Nine layers, each with a narrow responsibility. Layers depend downward only.
- **BND decomposition.** Twenty Behavioral Node Diagram nodes, each independently testable.
- **C, not C++.** The kernel is pure C (C11). No exceptions, no RTTI, no hidden allocations. Every byte is accounted for.
- **kqueue on macOS.** The event loop uses kqueue. On Linux, this would be epoll; the interface is abstracted so the backend can be swapped.
- **Thread-safe.** All shared state is protected by mutexes. The event loop is single-threaded; worker threads handle query execution.
- **No print().** All output goes through the log system. The kernel never writes to stdout/stderr directly.

---

## 2. 9-Layer Architecture

CPSD is organized into nine layers. Each layer depends only on layers below it. The layer number is a build order hint — lower layers are built first.

```
┌─────────────────────────────────────────────────┐
│  Layer 8: Client API                            │  cpsd_client.c / cpsd_cli.c
│  - Client library, CLI tool                     │
├─────────────────────────────────────────────────┤
│  Layer 7: Admin                                 │  cpsd_admin.c
│  - Status, metrics, reload, backup, restore     │
├─────────────────────────────────────────────────┤
│  Layer 6: Plugin / Hooks                        │  cpsd_plugin.c
│  - Hook registration, hook firing               │
├─────────────────────────────────────────────────┤
│  Layer 5: Cache                                 │  cpsd_cache.c
│  - Statement cache, object cache, metadata      │
├─────────────────────────────────────────────────┤
│  Layer 4: Query Engine                          │  cpsd_query.c
│  - Registry lookup, param binding, execution    │
├─────────────────────────────────────────────────┤
│  Layer 3: Storage Engine                        │  cpsd_storage.c / cpsd_pool.c
│  - Driver interface, connection pooling         │
├─────────────────────────────────────────────────┤
│  Layer 2: Security                              │  cpsd_security.c
│  - Auth, RBAC, rate limit, audit                │
├─────────────────────────────────────────────────┤
│  Layer 1: IPC Transport                         │  cpsd_ipc.c / cpsd_protocol.c
│  - Socket, frame read/write, request parsing    │
├─────────────────────────────────────────────────┤
│  Layer 0: Core Kernel                           │  cpsd_state.c / cpsd_loop.c
│  - State machine, event loop, event bus,        │  cpsd_event.c / cpsd_msg.c
│  message bus, signals, resources, watchdog      │  cpsd_signal.c / cpsd_resource.c
│                                                 │  cpsd_watchdog.c
├─────────────────────────────────────────────────┤
│  Cross-Layer: Health, WAL, Log, DestructionGuard│  cpsd_health.c / cpsd_wal.c
│                                                 │  cpsd_log.c / cpsd_guard.c
└─────────────────────────────────────────────────┘
```

### Layer 0: Core Kernel

The foundation. Contains the process state machine (`INIT → LOADING → READY → RELOAD → DRAINING → STOPPED → FAULT`), the kqueue-based event loop, the internal event bus (publish/subscribe), the inter-module message bus (typed queue), signal handling, resource limits, and the watchdog timer. Everything else builds on this.

**Files:** `cpsd_state.c`, `cpsd_loop.c`, `cpsd_event.c`, `cpsd_msg.c`, `cpsd_signal.c`, `cpsd_resource.c`, `cpsd_watchdog.c`

### Layer 1: IPC Transport

The Unix domain socket server. Listens on `/tmp/cpsd.sock`, accepts client connections, reads and writes binary frames, parses incoming requests into the `request_t` struct, and serializes `response_t` into outgoing frames. This is the only network-facing layer.

**Files:** `cpsd_ipc.c`, `cpsd_protocol.c`

### Layer 2: Security

Authentication (token → role mapping), RBAC permission checks (role × backend × operation), rate limiting (token bucket per client), and audit logging (every action recorded with timestamp, client, role, action, detail). The destruction guard is cross-layer but security-adjacent.

**Files:** `cpsd_security.c`, `cpsd_guard.c`

### Layer 3: Storage Engine

The pluggable storage driver interface and connection pooling. Drivers are registered at startup (MySQL, SQLite, Qdrant, Vector, Graph, Blob). The pool manages a set of connections per backend, with acquire/release, health checks, and idle timeout recycling.

**Files:** `cpsd_storage.c`, `cpsd_pool.c`, `cpsd_mysql.c`, `cpsd_sqlite.c`

### Layer 4: Query Engine

The query registry and execution engine. Queries are registered with a numeric `cmd_id`, a name, an SQL template, a backend, an operation type, and parameter type signatures. On execution, the engine looks up the query, validates parameters, acquires a connection from the pool, prepares the statement, binds parameters, executes, fetches results, and releases the connection. Transactions are supported (begin/commit/rollback).

**Files:** `cpsd_query.c`, `cpsd_registry.c`, `cpsd_validate.c`

### Layer 5: Cache

Four cache types: statement cache (prepared statement reuse), object cache (query result sets), metadata cache (schema, table lists), and stats cache (row counts, index info). LRU eviction with byte and entry limits.

**Files:** `cpsd_cache.c`

### Layer 6: Plugin / Hooks

Ten hook points allow plugins to intercept the request lifecycle. Plugins register a handler function with a priority. Hooks fire in priority order. A plugin can veto an action by returning non-zero from a pre-hook.

**Files:** `cpsd_plugin.c`

### Layer 7: Admin

Administrative commands: status (kernel state, pool stats, cache stats, query count), metrics (counters and gauges), reload (re-read config, re-register queries), backup (snapshot of WAL + config), restore (replay from backup), diagnostics (health check of all modules). Admin commands require the `admin` role.

**Files:** `cpsd_admin.c`

### Layer 8: Client API

The client-side library and CLI tool. The library (`cpsd_client.c`) connects to the socket, sends requests, reads responses. The CLI (`cpsd_cli.c`) is a command-line tool for ad-hoc queries, table listing, schema inspection, and admin commands. This layer runs in the client process, not in CPSD itself, but is part of the CPSD project.

**Files:** `cpsd_client.c`, `cpsd_cli.c`

### Cross-Layer Services

These span all layers and are not assigned to a single one:

- **Health** (`cpsd_health.c`): periodic health checks of all modules.
- **WAL** (`cpsd_wal.c`): write-ahead log for durability.
- **Log** (`cpsd_log.c`): leveled logging (DEBUG/INFO/WARN/ERROR/FATAL).
- **Destruction Guard** (`cpsd_guard.c`): SQL inspection gate for destructive operations.

---

## 3. 20 BND Nodes

BND (Behavioral Node Diagram) decomposes CPSD into twenty nodes. Each node is a cohesive unit of behavior with defined responsibilities, interfaces, dependencies, failure modes, state transitions, and owning files.

### BND-01: Identity

**Responsibilities:** Process identity, PID file management, instance naming, version reporting.

**Key Interfaces:**
```c
int  cpsd_identity_init(const char *instance_name);
const char* cpsd_identity_name(void);
const char* cpsd_identity_version(void);
pid_t cpsd_identity_pid(void);
int  cpsd_identity_write_pid(const char *path);
int  cpsd_identity_remove_pid(const char *path);
```

**Dependencies:** Layer 0 (log).

**Failure modes:** PID file write failure (permissions, disk full), stale PID file from previous crash.

**State transitions:** `UNINIT → IDENTIFIED → PID_WRITTEN → (crash) → STALE_PID → IDENTIFIED`

**Files:** `cpsd_identity.c`, `cpsd_identity.h`

---

### BND-02: Inputs

**Responsibilities:** Configuration file parsing, command-line argument parsing, environment variable overrides, token file loading. All external inputs enter through this node.

**Key Interfaces:**
```c
int  cpsd_config_load(const char *path);
void cpsd_config_free(void);
const char* cpsd_config_get(const char *key);
int  cpsd_config_get_int(const char *key, int default_val);
int  cpsd_config_reload(void);
int  cpsd_config_validate(void);
```

**Dependencies:** Layer 0 (log).

**Failure modes:** Missing config file, malformed config, unknown keys, token file unreadable.

**State transitions:** `EMPTY → LOADING → LOADED → VALIDATED → (reload) → LOADING`

**Files:** `cpsd_config.c`, `cpsd_config.h`

---

### BND-03: Core Kernel

**Responsibilities:** Process lifecycle state machine, boot sequence orchestration, shutdown sequence, fault handling. This is the master node that drives all others.

**Key Interfaces:**
```c
kern_state_t kern_state_get(void);
int          kern_state_transition(kern_state_t target);
int          kern_state_is_serving(void);
const char*  kern_state_name(kern_state_t s);
int          cpsd_boot(void);
int          cpsd_shutdown(void);
```

**Dependencies:** BND-01 (Identity), BND-02 (Inputs), BND-05 (Event System), BND-14 (Recovery).

**Failure modes:** Illegal state transition, boot step failure, watchdog trip.

**State transitions:** `INIT → LOADING → READY → RELOAD → DRAINING → STOPPED`; any state → `FAULT`.

**Files:** `cpsd_state.c`, `cpsd_main.c`

---

### BND-04: Security

**Responsibilities:** Token-based authentication, role mapping, RBAC permission matrix, rate limiting (token bucket), audit log writing.

**Key Interfaces:**
```c
int  sec_auth_init(void);
int  sec_authenticate(int client_fd, const char *token, auth_context_t *ctx);
int  sec_perm_check(const auth_context_t *ctx, uint8_t db_id, uint16_t cmd_id, operation_t op);
int  sec_rate_check(const auth_context_t *ctx, uint16_t cmd_id);
int  sec_audit_log(const auth_context_t *ctx, const char *action, const char *detail);
```

**Dependencies:** BND-02 (Inputs — token files, role definitions), BND-13 (Logging).

**Failure modes:** Token file missing, unknown role, rate limit exceeded, audit log write failure.

**State transitions:** `UNINIT → LOADED → AUTHENTICATING → (success) → AUTHORIZED / (fail) → DENIED`

**Files:** `cpsd_security.c`, `cpsd_security.h`

---

### BND-05: Validation

**Responsibilities:** Parameter type checking against query registry signatures, string length limits, integer range checks, blob size limits, SQL injection heuristic checks (defense in depth — even though prepared statements prevent injection, validate input shapes).

**Key Interfaces:**
```c
int  validate_params(const query_entry_t *entry, const param_t *params, int count);
int  validate_string(const char *str, size_t max_len);
int  validate_int(int64_t value, int64_t min, int64_t max);
int  validate_blob(const void *data, size_t len, size_t max_len);
int  validate_cmd_id(uint16_t cmd_id);
```

**Dependencies:** BND-07 (Query Engine — registry signatures).

**Failure modes:** Type mismatch, length exceeded, invalid cmd_id, null where non-null required.

**State transitions:** `IDLE → VALIDATING → (ok) → VALID / (fail) → INVALID → IDLE`

**Files:** `cpsd_validate.c`, `cpsd_validate.h`

---

### BND-06: Storage

**Responsibilities:** Storage driver registration, backend connection management, driver dispatch. Abstracts the actual database behind a uniform function-pointer interface.

**Key Interfaces:**
```c
int  storage_register(storage_driver_t *driver);
int  storage_connect(storage_backend_t backend, const char *conn_str, void **handle);
int  storage_disconnect(storage_backend_t backend, void *handle);
storage_driver_t* storage_get_driver(storage_backend_t backend);
```

**Dependencies:** BND-02 (Inputs — connection strings), BND-13 (Logging).

**Failure modes:** Driver not registered, connection refused, auth failure to backend, backend timeout.

**State transitions:** `EMPTY → REGISTERED → CONNECTING → CONNECTED → (error) → DISCONNECTED`

**Files:** `cpsd_storage.c`, `cpsd_storage.h`

---

### BND-07: Query Engine

**Responsibilities:** Query registry management (register, lookup, size), query execution (prepare, bind, execute, fetch), batch execution, transaction control (begin/commit/rollback).

**Key Interfaces:**
```c
int  query_registry_init(void);
int  query_registry_register(const query_entry_t *entry);
const query_entry_t* query_registry_lookup(uint16_t cmd_id);
int  query_execute(uint16_t cmd_id, const param_t *params, int param_count, response_t *result);
int  query_batch(uint16_t cmd_id, const param_t *batch, int batch_count, response_t *result);
int  query_txn_begin(void);
int  query_txn_commit(void);
int  query_txn_rollback(void);
```

**Dependencies:** BND-06 (Storage), BND-05 (Validation), BND-08 (Transactions), BND-09 (Metadata), BND-10 (Cache).

**Failure modes:** Unknown cmd_id, param count mismatch, param type mismatch, backend execution error, transaction conflict.

**State transitions:** `IDLE → PREPARING → BINDING → EXECUTING → FETCHING → COMPLETE / (error) → FAILED`

**Files:** `cpsd_query.c`, `cpsd_registry.c`, `cpsd_query.h`

---

### BND-08: Transactions

**Responsibilities:** Transaction lifecycle management, per-client transaction context, nested transaction emulation (savepoints), deadlock detection and retry.

**Key Interfaces:**
```c
int  query_txn_begin(void);
int  query_txn_commit(void);
int  query_txn_rollback(void);
int  query_txn_savepoint(const char *name);
int  query_txn_rollback_to(const char *name);
int  query_txn_in_progress(void);
```

**Dependencies:** BND-06 (Storage), BND-07 (Query Engine).

**Failure modes:** Deadlock, timeout, commit failure, rollback failure.

**State transitions:** `NONE → BEGIN → ACTIVE → (commit) → COMMITTED / (rollback) → ROLLED_BACK → NONE`

**Files:** `cpsd_txn.c`, `cpsd_txn.h`

---

### BND-09: Metadata

**Responsibilities:** Schema introspection (table list, column list, index info, type info), metadata caching, schema change detection.

**Key Interfaces:**
```c
int  meta_tables(uint8_t db_id, response_t *resp);
int  meta_schema(uint8_t db_id, const char *table, response_t *resp);
int  meta_indexes(uint8_t db_id, const char *table, response_t *resp);
int  meta_invalidate(uint8_t db_id, const char *table);
```

**Dependencies:** BND-06 (Storage), BND-10 (Cache).

**Failure modes:** Backend metadata query failure, stale cache.

**State transitions:** `EMPTY → LOADING → CACHED → (invalidate) → EMPTY`

**Files:** `cpsd_meta.c`, `cpsd_meta.h`

---

### BND-10: Cache

**Responsibilities:** Four cache types (statement, object, metadata, stats), LRU eviction, byte and entry limits, hit/miss counters, cache invalidation by key and by type.

**Key Interfaces:**
```c
int  cache_init(void);
int  cache_get(cache_type_t type, const void *key, size_t key_len, void **value, size_t *value_len);
int  cache_put(cache_type_t type, const void *key, size_t key_len, const void *value, size_t value_len);
int  cache_invalidate(cache_type_t type, const void *key, size_t key_len);
int  cache_flush(cache_type_t type);
int  cache_stats_get(cache_type_t type, int *entries, size_t *bytes, int *hits, int *misses);
```

**Dependencies:** None (leaf node, depends only on Layer 0 log).

**Failure modes:** Cache full (eviction), memory allocation failure, key hash collision.

**State transitions:** `EMPTY → POPULATED → (evict) → POPULATED / (flush) → EMPTY`

**Files:** `cpsd_cache.c`, `cpsd_cache.h`

---

### BND-11: Connection Management

**Responsibilities:** Connection pool per backend, acquire/release semantics, idle timeout recycling, health checking, pool statistics.

**Key Interfaces:**
```c
int  pool_init(storage_backend_t backend, int pool_size, const char *conn_str);
void pool_shutdown(storage_backend_t backend);
int  pool_acquire(storage_backend_t backend, void **handle);
int  pool_release(storage_backend_t backend, void *handle);
int  pool_health_check(storage_backend_t backend);
int  pool_stats(storage_backend_t backend, int *total, int *in_use, int *idle);
```

**Dependencies:** BND-06 (Storage).

**Failure modes:** Pool exhausted (all connections in use), connection died (health check fails), pool init failure.

**State transitions (per connection):** `IDLE → ACQUIRED → IN_USE → RELEASED → IDLE → (timeout) → CLOSED`

**State transitions (pool):** `UNINIT → INITIALIZED → (exhausted) → EXPANDING → INITIALIZED / (shutdown) → DRAINED`

**Files:** `cpsd_pool.c`, `cpsd_pool.h`

---

### BND-12: Monitoring

**Responsibilities:** Metrics collection (counters, gauges, histograms), health check orchestration, watchdog integration, performance counters per query.

**Key Interfaces:**
```c
int  health_init(void);
int  health_check_all(void);
int  health_check_module(module_id_t module);
int  metrics_increment(const char *name, uint64_t value);
int  metrics_set(const char *name, uint64_t value);
int  metrics_get(const char *name, uint64_t *value);
int  metrics_dump(response_t *resp);
```

**Dependencies:** BND-03 (Core), BND-13 (Logging).

**Failure modes:** Health check timeout, metrics buffer overflow.

**State transitions:** `IDLE → CHECKING → (ok) → HEALTHY / (fail) → UNHEALTHY → IDLE`

**Files:** `cpsd_health.c`, `cpsd_metrics.c`, `cpsd_health.h`

---

### BND-13: Logging

**Responsibilities:** Leveled logging (DEBUG/INFO/WARN/ERROR/FATAL), log file rotation, structured log format (timestamp, level, module, message), log buffering and flush.

**Key Interfaces:**
```c
int  log_init(const char *dir);
void log_shutdown(void);
int  log_write(int level, const char *module, const char *msg);
int  log_rotate(void);
int  log_set_level(int level);
```

**Dependencies:** None (leaf node).

**Failure modes:** Log dir missing, disk full, rotation failure.

**State transitions:** `UNINIT → INITIALIZED → WRITING → (rotate) → INITIALIZED / (shutdown) → UNINIT`

**Files:** `cpsd_log.c`, `cpsd_log.h`

---

### BND-14: Recovery

**Responsibilities:** Write-ahead log (WAL) for all write operations, crash recovery via WAL replay, backup creation, restore from backup.

**Key Interfaces:**
```c
int  wal_init(const char *path);
void wal_shutdown(void);
int  wal_write(const void *data, size_t len);
int  wal_replay(void);
int  wal_checkpoint(void);
int  admin_backup(const char *path);
int  admin_restore(const char *path);
```

**Dependencies:** BND-03 (Core), BND-13 (Logging).

**Failure modes:** WAL write failure (disk full), WAL corruption, replay failure.

**State transitions:** `CLOSED → OPEN → WRITING → (crash) → REPLAYING → (ok) → OPEN / (corrupt) → FAULT`

**Files:** `cpsd_wal.c`, `cpsd_wal.h`

---

### BND-15: Event System

**Responsibilities:** Internal event bus (publish/subscribe), event dispatch, event type registry. Synchronous dispatch — handlers run in the publisher's thread.

**Key Interfaces:**
```c
int  kern_event_init(void);
int  kern_event_subscribe(event_type_t type, event_handler_t handler);
int  kern_event_unsubscribe(event_type_t type, event_handler_t handler);
int  kern_event_publish(event_t *evt);
```

**Dependencies:** BND-03 (Core).

**Failure modes:** Handler exception (logs and continues), subscriber overflow (max 8 per type).

**State transitions:** `UNINIT → INITIALIZED → SUBSCRIBING → PUBLISHING → INITIALIZED`

**Files:** `cpsd_event.c`, `cpsd_event.h`

---

### BND-16: Plugin System

**Responsibilities:** Hook point registration, plugin load/unload, hook firing in priority order, plugin veto (pre-hooks can block actions).

**Key Interfaces:**
```c
int  plugin_init(void);
int  plugin_register(hook_point_t hook, hook_handler_t handler, int priority);
int  plugin_unregister(hook_point_t hook, hook_handler_t handler);
int  plugin_fire(hook_point_t hook, void *context);
```

**Dependencies:** BND-15 (Event System).

**Failure modes:** Plugin load failure, hook handler crash, too many plugins per hook point.

**State transitions:** `UNINIT → INITIALIZED → LOADING → ACTIVE → (unload) → INITIALIZED`

**Files:** `cpsd_plugin.c`, `cpsd_plugin.h`

---

### BND-17: Administration

**Responsibilities:** Admin command handling (status, metrics, reload, backup, restore, diagnostics, version), admin command authorization (requires admin role).

**Key Interfaces:**
```c
int  admin_status(response_t *resp);
int  admin_reload(void);
int  admin_metrics(response_t *resp);
int  admin_diagnostics(response_t *resp);
int  admin_backup(const char *path);
int  admin_restore(const char *path);
int  admin_version(response_t *resp);
```

**Dependencies:** BND-03 (Core), BND-04 (Security), BND-12 (Monitoring), BND-14 (Recovery).

**Failure modes:** Unauthorized caller, reload failure, backup write failure.

**State transitions:** `IDLE → PROCESSING → COMPLETE / (error) → FAILED → IDLE`

**Files:** `cpsd_admin.c`, `cpsd_admin.h`

---

### BND-18: Service Lifecycle

**Responsibilities:** Boot sequence (init all layers in order), shutdown sequence (drain connections, flush WAL, close sockets), graceful reload (re-read config, re-register queries, swap atomically).

**Key Interfaces:**
```c
int  cpsd_boot(void);
int  cpsd_shutdown(void);
int  cpsd_reload(void);
int  cpsd_drain(int timeout_sec);
```

**Dependencies:** All BND nodes (orchestrates them).

**Failure modes:** Boot step failure (aborts, transitions to FAULT), shutdown timeout (force kill).

**State transitions:** Maps directly to kernel state machine (see Section 10).

**Files:** `cpsd_main.c`, `cpsd_lifecycle.c`, `cpsd_lifecycle.h`

---

### BND-19: OS Integration

**Responsibilities:** Signal handling (SIGTERM → graceful shutdown, SIGINT → graceful, SIGHUP → reload, SIGUSR1 → WAL checkpoint), resource limits (RLIMIT_NOFILE, RLIMIT_NPROC), daemonization, kqueue event loop.

**Key Interfaces:**
```c
int  kern_signal_init(void);
int  kern_signal_register(int signo, signal_handler_t handler);
int  kern_resource_init(resource_limits_t *limits);
int  kern_resource_check_clients(int current);
int  kern_resource_check_memory(size_t used_bytes);
int  kern_loop_init(void);
int  kern_loop_run(void);
```

**Dependencies:** BND-03 (Core), BND-15 (Event System).

**Failure modes:** Signal handler reentrancy, resource limit exceeded, kqueue creation failure.

**State transitions:** `RAW → SIGNALS_INSTALLED → RESOURCES_SET → LOOP_RUNNING → (signal) → LOOP_STOPPED`

**Files:** `cpsd_signal.c`, `cpsd_resource.c`, `cpsd_loop.c`, `cpsd_os.h`

---

### BND-20: Future Expansion

**Responsibilities:** Reserved node for future capabilities: replication (read replicas), sharding (query routing by key), vector search (Qdrant integration), graph queries, blob storage, HTTP gateway, REST adapter, Prometheus metrics endpoint.

**Key Interfaces:** (Reserved — not yet defined)

**Dependencies:** All layers (future).

**Failure modes:** N/A.

**State transitions:** `RESERVED → PLANNED → (future) → ACTIVE`

**Files:** (Reserved — `cpsd_replica.c`, `cpsd_shard.c`, `cpsd_vector.c`, `cpsd_graph.c`, `cpsd_blob.c`, `cpsd_http.c`)

---

## 4. Dependency Matrix

This matrix shows which BND nodes depend on which. A `D` in cell (row, col) means row depends on col. Diagonal is self (excluded). Read row → depends on → column.

| BND \ BND | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 |
|-----------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| 01 Identity | | | | | | | | | | | | | D | | | | | | | |
| 02 Inputs | | | | | | | | | | | | | D | | | | | | | |
| 03 Core | D | D | | | | | | | | | | | | D | D | | | | | |
| 04 Security | | D | | | | | | | | | | | D | | | | | | | |
| 05 Validation | | | | | | | D | | | | | | | | | | | | | |
| 06 Storage | | D | | | | | | | | | | | D | | | | | | | |
| 07 Query | | | | | D | D | | D | D | D | | | | | | | | | | |
| 08 Txn | | | | | | D | D | | | | | | | | | | | | | |
| 09 Metadata | | | | | | D | | | | D | | | | | | | | | | |
| 10 Cache | | | | | | | | | | | | | D | | | | | | | |
| 11 Pool | | | | | | D | | | | | | | | | | | | | | |
| 12 Monitor | | | D | | | | | | | | | | D | | | | | | | |
| 13 Logging | | | | | | | | | | | | | | | | | | | | |
| 14 Recovery | | | D | | | | | | | | | | D | | | | | | | |
| 15 Event | | | D | | | | | | | | | | | | | | | | | |
| 16 Plugin | | | | | | | | | | | | | | | D | | | | | |
| 17 Admin | | | D | D | | | | | | | | | | D | | | | | | |
| 18 Lifecycle| D | D | D | D | | D | D | D | | D | D | D | D | D | D | D | D | | D | |
| 19 OS | | | D | | | | | | | | | | | | D | | | | | |
| 20 Future | | | | | | | | | | | | | | | | | | | | |

**Key observations:**

- **BND-13 (Logging)** is a leaf — everything depends on it, it depends on nothing.
- **BND-03 (Core)** is the root — it depends on Identity, Inputs, Recovery, and Event.
- **BND-18 (Lifecycle)** is the orchestrator — it depends on almost everything (it calls boot/shutdown on each).
- **BND-07 (Query Engine)** has the most internal dependencies (Storage, Validation, Txn, Metadata, Cache) — it is the central pipeline.
- **BND-20 (Future)** depends on nothing yet — it is reserved.

---

## 5. Build Order

Ten phases. Each phase produces a compilable, testable increment. Lines are estimates for the `.c` files only (headers excluded).

### Phase 1: Core Kernel (Layer 0 — State, Event, Loop, Msg)

**Goal:** Process boots, state machine works, event loop runs, events publish/subscribe, message queue works.

**BNDs:** 03 (Core), 15 (Event), 19 (OS — loop/signals partial)

**Files:**
- `cpsd.h` — master header (all declarations)
- `cpsd_state.c` — state machine
- `cpsd_event.c` — event bus
- `cpsd_loop.c` — kqueue event loop
- `cpsd_msg.c` — message bus
- `cpsd_main.c` — entry point (boots, runs loop, shuts down)

**Estimated lines:** ~600

**Exit criteria:** `./cpsd` starts, enters READY state, handles SIGTERM gracefully, logs state transitions.

---

### Phase 2: OS Integration (Signals, Resources, Watchdog)

**Goal:** Signal handling, resource limits, watchdog timer operational.

**BNDs:** 19 (OS — complete), 12 (Monitor — watchdog partial)

**Files:**
- `cpsd_signal.c` — signal registration
- `cpsd_resource.c` — RLIMIT checks
- `cpsd_watchdog.c` — watchdog timer

**Estimated lines:** ~400

**Exit criteria:** SIGTERM → DRAINING → STOPPED. SIGHUP → RELOAD → READY. SIGUSR1 → WAL checkpoint (stub). Watchdog trips if a module doesn't kick.

---

### Phase 3: Logging & Config (Inputs, Logging)

**Goal:** Config file parsing, leveled logging to files with rotation.

**BNDs:** 01 (Identity), 02 (Inputs), 13 (Logging)

**Files:**
- `cpsd_config.c` — config parser
- `cpsd_log.c` — logging
- `cpsd_identity.c` — PID file, version

**Estimated lines:** ~500

**Exit criteria:** Reads `/tmp/cpsd.conf`, logs to `/tmp/cpsd_logs/cpsd.log` with levels, rotates on SIGHUP.

---

### Phase 4: IPC Transport (Layer 1 — Socket, Protocol)

**Goal:** Unix socket server accepts connections, reads frames, parses requests, writes responses.

**BNDs:** (IPC layer — not a named BND, part of Layer 1)

**Files:**
- `cpsd_ipc.c` — socket init, accept, close
- `cpsd_protocol.c` — frame read/write, request parse, response build

**Estimated lines:** ~700

**Exit criteria:** Client connects, sends a PING frame, gets a PONG response. Frame parsing validates MAGIC, version, sizes.

---

### Phase 5: Security (Layer 2 — Auth, RBAC, Rate Limit, Audit, Guard)

**Goal:** Token authentication, role mapping, permission checks, rate limiting, audit log, destruction guard.

**BNDs:** 04 (Security), 05 (Validation — partial, param validation)

**Files:**
- `cpsd_security.c` — auth, perm, rate, audit
- `cpsd_guard.c` — destruction guard
- `cpsd_validate.c` — param validation

**Estimated lines:** ~800

**Exit criteria:** Client without token is rejected. Client with `reader` token cannot INSERT. Client with `writer` token cannot DROP. Rate limit triggers after burst. Destruction guard blocks `DROP TABLE` without confirm.

---

### Phase 6: Storage & Pool (Layer 3 — Driver Interface, Pool, MySQL Driver)

**Goal:** Storage driver interface, connection pool, MySQL driver registered and working.

**BNDs:** 06 (Storage), 11 (Pool)

**Files:**
- `cpsd_storage.c` — driver registry
- `cpsd_pool.c` — connection pool
- `cpsd_mysql.c` — MySQL driver implementation

**Estimated lines:** ~900

**Exit criteria:** Pool connects to MySQL, acquires/releases connections, health check detects dead connections, pool stats report correctly.

---

### Phase 7: Query Engine (Layer 4 — Registry, Execute, Txn)

**Goal:** Query registry loaded from config, query execution via prepared statements, transactions.

**BNDs:** 07 (Query), 08 (Txn), 09 (Metadata)

**Files:**
- `cpsd_registry.c` — query registry
- `cpsd_query.c` — execution engine
- `cpsd_txn.c` — transaction management
- `cpsd_meta.c` — schema introspection

**Estimated lines:** ~1000

**Exit criteria:** Client sends `cmd_id=1` with params, gets results. `CMD_TABLES` returns table list. `CMD_BEGIN`/`CMD_COMMIT` works. Unknown `cmd_id` returns error.

---

### Phase 8: Cache & Plugin (Layer 5, Layer 6)

**Goal:** Statement/object/metadata/stats cache with LRU. Plugin hook system with priority firing.

**BNDs:** 10 (Cache), 16 (Plugin)

**Files:**
- `cpsd_cache.c` — LRU cache
- `cpsd_plugin.c` — hook system

**Estimated lines:** ~600

**Exit criteria:** Repeated query hits cache (miss counter increments first time, hit second time). Plugin registered on `HOOK_PRE_QUERY` fires and can veto.

---

### Phase 9: Admin & Recovery (Layer 7, Cross-Layer — WAL, Health, Backup)

**Goal:** WAL writes and replays. Admin commands work. Health checks run periodically.

**BNDs:** 12 (Monitor — complete), 14 (Recovery), 17 (Admin)

**Files:**
- `cpsd_wal.c` — write-ahead log
- `cpsd_health.c` — health checks
- `cpsd_metrics.c` — metrics counters
- `cpsd_admin.c` — admin commands

**Estimated lines:** ~800

**Exit criteria:** Write query produces WAL entry. Kill -9 then restart → WAL replays. `admin_status` returns JSON with state, pool, cache stats. `admin_backup` writes snapshot.

---

### Phase 10: Client API & CLI (Layer 8)

**Goal:** Client library and CLI tool for ad-hoc access.

**BNDs:** 18 (Lifecycle — complete), 20 (Future — stubs)

**Files:**
- `cpsd_client.c` — client library
- `cpsd_cli.c` — CLI tool
- `cpsd_lifecycle.c` — boot/shutdown orchestration (finalized)

**Estimated lines:** ~700

**Exit criteria:** `cpsd_cli ping` → pong. `cpsd_cli query 1 --params "42"` → results. `cpsd_cli tables` → table list. `cpsd_cli admin status` → status JSON.

---

**Total estimated lines:** ~7,000 (C code only, excluding headers)

---

## 6. Protocol

CPSD uses a binary wire protocol over a Unix domain socket. All multi-byte integers are **big-endian (network byte order)**. The protocol is designed to be simple, fast to parse, and impossible to inject SQL through.

### 6.1 Frame Layout

Every frame on the wire has this layout:

```
Offset  Size  Field           Description
──────  ────  ──────────────  ─────────────────────────────────
0       4     MAGIC           ASCII "CDB1" (0x43 0x44 0x42 0x31)
4       1     VERSION         Protocol version (0x01)
5       1     MSG_TYPE        0x01=REQUEST, 0x02=RESPONSE, 0x03=ERROR, 0x04=NOTIFY
6       4     REQUEST_ID      Unique per request (client-chosen, echoed in response)
10      2     CMD_ID          Numeric query ID (from registry) — see Section 9
12      1     DB_ID           Backend ID (0=MySQL, 1=SQLite, 2=Qdrant, ...)
13      1     PARAM_COUNT     Number of parameters (0..32)
14      2     FLAGS           Bit 0: confirm_destructive, Bit 1: want_cache, Bits 2-15: reserved
16      N     PAYLOAD         Parameter data (see 6.2)
```

**Header size:** 16 bytes (before payload).

### 6.2 Payload — Parameter Encoding

Following the 16-byte header, parameters are encoded sequentially. Each parameter:

```
Offset  Size  Field           Description
──────  ────  ──────────────  ─────────────────────────────────
0       1     PARAM_TYPE      0=NULL, 1=INT32, 2=INT64, 3=STRING, 4=DOUBLE, 5=BLOB, 6=BOOL
1       4     PARAM_LEN       Length of value in bytes (0 for NULL)
5       L     PARAM_VALUE     Raw bytes (L = PARAM_LEN)
```

For `PARAM_NULL`, `PARAM_LEN` is 0 and no value bytes follow.
For `PARAM_INT32`, `PARAM_LEN` is 4 and value is big-endian int32.
For `PARAM_INT64`, `PARAM_LEN` is 8 and value is big-endian int64.
For `PARAM_STRING`, `PARAM_LEN` is the byte length of the UTF-8 string (not null-terminated on wire).
For `PARAM_DOUBLE`, `PARAM_LEN` is 8 and value is IEEE 754 double big-endian.
For `PARAM_BLOB`, `PARAM_LEN` is the byte length of the blob.
For `PARAM_BOOL`, `PARAM_LEN` is 1 and value is 0x00 or 0x01.

### 6.3 Response Frame

```
Offset  Size  Field           Description
──────  ────  ──────────────  ─────────────────────────────────
0       4     MAGIC           "CDB1"
4       1     VERSION         0x01
5       1     MSG_TYPE        0x02 (RESPONSE) or 0x03 (ERROR)
6       4     REQUEST_ID      Echoed from request
10      1     STATUS          0=OK, 1=ERROR
11      2     ERROR_CODE      0 if OK, specific code if error
13      4     ROW_COUNT       Number of rows in result
17      2     COL_COUNT       Number of columns
19      2     ROWS_LEN        Length of serialized rows block
21      R     ROWS            Serialized rows (see 6.4)
21+R    E     ERROR_MSG       Error message string (null-terminated, max 2048 bytes)
```

### 6.4 Row Serialization

Rows are serialized as a sequence of rows. Each row is a sequence of column values. Each column value:

```
Offset  Size  Field           Description
──────  ────  ──────────────  ─────────────────────────────────
0       1     COL_TYPE        Same as PARAM_TYPE encoding
1       4     COL_LEN         Length of value
5       L     COL_VALUE       Raw bytes
```

Column names are sent once in a header block before the rows (not per-row). The column name block:

```
Offset  Size  Field           Description
──────  ────  ──────────────  ─────────────────────────────────
0       2     COL_NAME_LEN    Length of column name
2       N     COL_NAME        Column name string (not null-terminated)
```

Repeated for each column, then the rows follow.

### 6.5 C Structures

```c
// Wire frame header (16 bytes)
typedef struct {
    char     magic[4];       // "CDB1"
    uint8_t  version;        // 0x01
    uint8_t  msg_type;       // MSG_REQUEST / MSG_RESPONSE / MSG_ERROR / MSG_NOTIFY
    uint32_t request_id;     // client-chosen, echoed in response
    uint16_t cmd_id;         // query registry ID
    uint8_t  db_id;          // backend ID
    uint8_t  param_count;    // 0..32
    uint16_t flags;          // bit 0: confirm_destructive
} __attribute__((packed)) frame_header_t;

// Parameter on wire
typedef struct {
    uint8_t  type;           // param_type_t
    uint32_t len;            // value length in bytes
    // followed by `len` bytes of value
} __attribute__((packed)) wire_param_t;

// Parsed request (in-memory)
typedef struct {
    uint8_t  version;
    uint8_t  msg_type;
    uint32_t request_id;
    uint16_t cmd_id;
    uint8_t  db_id;
    uint8_t  param_count;
    uint16_t flags;
    param_t  params[CPSD_MAX_PARAMS];
    char     sql[CPSD_MAX_SQL];  // only for CMD_QUERY ad-hoc (admin only)
} request_t;

// Parsed response (in-memory)
typedef struct {
    uint8_t  status;         // 0=ok, 1=error
    uint16_t error_code;
    uint32_t row_count;
    uint32_t col_count;
    char     columns[CPSD_MAX_COLS][128];
    char    *rows;           // serialized binary
    size_t   rows_len;
    char     error_msg[CPSD_MAX_ERR];
} response_t;
```

### 6.6 Protocol Functions

```c
int ipc_frame_read(int fd, void *frame, size_t frame_size, size_t *frame_len);
int ipc_frame_write(int fd, const void *frame, size_t frame_len);
int ipc_parse_request(const void *frame, size_t len, request_t *req);
int ipc_build_response(void *frame, size_t frame_size, size_t *frame_len, const response_t *resp);
```

### 6.7 Error Codes

```
0x0000  OK
0x0001  ERR_AUTH_REQUIRED        No token / invalid token
0x0002  ERR_PERMISSION_DENIED    Role lacks permission for this op
0x0003  ERR_RATE_LIMITED         Rate limit exceeded
0x0004  ERR_UNKNOWN_CMD          cmd_id not in registry
0x0005  ERR_PARAM_MISMATCH       Wrong param count or type
0x0006  ERR_PARAM_INVALID        Value out of range / too long
0x0007  ERR_DESTRUCTION_GUARD    Destructive op without confirm flag
0x0008  ERR_BACKEND_DOWN         Storage backend unreachable
0x0009  ERR_POOL_EXHAUSTED       No connections available
0x000A  ERR_QUERY_FAILED         Backend returned error
0x000B  ERR_TXN_CONFLICT         Deadlock / serialization failure
0x000C  ERR_TXN_ABORTED          Transaction rolled back
0x000D  ERR_INTERNAL             Internal kernel error
0x000E  ERR_OVERLOADED           Kernel in DRAINING or FAULT state
0x000F  ERR_PROTOCOL             Malformed frame / bad magic
0x0010  ERR_TOO_LARGE            Frame exceeds CPSD_MAX_REQUEST
```

---

## 7. Security Model

### 7.1 Roles

Six roles, each with a distinct permission set. Roles are assigned via token files (see Section 12.3).

| Role | Description |
|------|-------------|
| `admin` | Full access including admin commands, schema changes, destruction (with guard). |
| `writer` | Read and write on all backends. No admin commands. No schema changes. |
| `reader` | Read-only on all backends. No writes, no admin. |
| `ai_agent` | Read on all backends, write only to designated AI tables. Rate-limited harder. |
| `cli` | Interactive CLI access. Read on all, write on designated tables. |
| `internal` | CPSD internal use (health checks, metrics). Cannot be assigned to external clients. |

### 7.2 Permission Matrix

Rows are roles. Columns are `operation_t` × `db_id`. `Y` = allowed, `N` = denied, `G` = allowed with destruction guard.

| Role \ Operation | SELECT | INSERT | UPDATE | DELETE | BATCH | ADMIN | DROP/ALTER |
|-------------------|--------|--------|--------|--------|-------|-------|------------|
| admin | Y | Y | Y | Y | Y | Y | G |
| writer | Y | Y | Y | Y | Y | N | N |
| reader | Y | N | N | N | N | N | N |
| ai_agent | Y | Y* | N | N | Y | N | N |
| cli | Y | Y** | Y** | N | N | N | N |
| internal | Y | N | N | N | N | Y*** | N |

`*` ai_agent INSERT only on tables with prefix `ai_`.
`**` cli write only on tables with prefix `cli_`.
`***` internal ADMIN only for status/metrics/health, not reload/backup/restore.

### 7.3 Rate Limiting

Token bucket per client (identified by `client_fd` + `client_pid`).

- **Default:** 100 queries/sec, burst 200.
- **ai_agent:** 50 queries/sec, burst 100.
- **cli:** 20 queries/sec, burst 40.
- **admin:** 200 queries/sec, burst 500.

When rate limited, CPSD returns `ERR_RATE_LIMITED` (0x0003). The bucket refills at the QPS rate.

```c
int sec_rate_check(const auth_context_t *ctx, uint16_t cmd_id);
void sec_rate_reset(const auth_context_t *ctx);
```

### 7.4 Audit Log

Every authenticated action is written to the audit log at `/tmp/cpsd_logs/cpsd_audit.log`. Format:

```
TIMESTAMP | CLIENT_PID | CLIENT_UID | ROLE | DB_ID | CMD_ID | OPERATION | DETAIL | RESULT
```

Example:
```
2026-07-04T10:23:45Z | 48291 | 501 | writer | 0 | 12 | UPDATE | "UPDATE users SET active=1 WHERE id=42" | OK
2026-07-04T10:23:46Z | 48291 | 501 | writer | 0 | 5 | DELETE | "DELETE FROM sessions WHERE expired" | GUARDED
2026-07-04T10:23:47Z | 48302 | 501 | reader | 0 | 1 | SELECT | "SELECT * FROM users LIMIT 10" | OK
```

```c
int sec_audit_log(const auth_context_t *ctx, const char *action, const char *detail);
```

### 7.5 Destruction Guard

The destruction guard inspects every query before execution. It checks for destructive patterns:

- `DROP TABLE`, `DROP DATABASE`
- `TRUNCATE TABLE`
- `DELETE FROM` without `WHERE`
- `ALTER TABLE ... DROP COLUMN`
- `UPDATE ... SET ... ` without `WHERE`

If a destructive pattern is detected and the request frame does not have `flags & 0x0001` (confirm_destructive) set, the query is rejected with `ERR_DESTRUCTION_GUARD` (0x0007). Even with the confirm flag, the action is audit-logged with `GUARDED` result.

```c
int destruction_guard_check(const char *sql, bool confirm);
const char* destruction_guard_reason(void);
```

The guard is a **hard gate** — it cannot be bypassed by any role. The `admin` role can set the confirm flag, but the guard still runs and still logs.

---

## 8. Storage Driver Interface

Backends are pluggable. Each backend implements the `storage_driver_t` interface — a struct of function pointers. The kernel calls through these pointers and never touches backend-specific APIs directly.

### 8.1 Driver Struct

```c
typedef enum {
    STORAGE_MYSQL   = 0,
    STORAGE_SQLITE  = 1,
    STORAGE_QDRANT  = 2,
    STORAGE_VECTOR  = 3,
    STORAGE_GRAPH   = 4,
    STORAGE_BLOB    = 5,
    STORAGE_CUSTOM  = 99,
} storage_backend_t;

typedef struct {
    storage_backend_t backend;
    const char *name;

    int  (*connect)(void **handle, const char *conn_str);
    int  (*disconnect)(void *handle);

    int  (*prepare)(void *handle, const char *sql, void **stmt);
    int  (*bind)(void *stmt, int idx, param_type_t type, const void *value, uint32_t len);
    int  (*execute)(void *stmt);
    int  (*fetch)(void *stmt, response_t *resp, int max_rows);
    int  (*close_stmt)(void *stmt);

    int  (*begin_txn)(void *handle);
    int  (*commit_txn)(void *handle);
    int  (*rollback_txn)(void *handle);

    int  (*ping)(void *handle);

    const char *(*error)(void *handle);
} storage_driver_t;
```

### 8.2 Registration and Lookup

```c
int  storage_register(storage_driver_t *driver);
int  storage_connect(storage_backend_t backend, const char *conn_str, void **handle);
int  storage_disconnect(storage_backend_t backend, void *handle);
storage_driver_t* storage_get_driver(storage_backend_t backend);
```

At boot, each driver calls `storage_register()` with its struct. The kernel stores these in a registry indexed by `storage_backend_t`. When a query targets `db_id=0` (MySQL), the kernel looks up the MySQL driver and calls through its function pointers.

### 8.3 Backend Implementations

| Backend | ID | Driver File | Notes |
|---------|----|-----------|-------|
| MySQL | 0 | `cpsd_mysql.c` | Primary backend. Uses `mysql_real_connect`, `mysql_stmt_prepare`, `mysql_stmt_bind_param`, `mysql_stmt_execute`, `mysql_stmt_fetch`. |
| SQLite | 1 | `cpsd_sqlite.c` | Embedded fallback. Uses `sqlite3_prepare_v2`, `sqlite3_bind_*`, `sqlite3_step`. |
| Qdrant | 2 | `cpsd_qdrant.c` | Vector search. HTTP API to Qdrant server. (Future) |
| Vector | 3 | `cpsd_vector.c` | MLX vector engine. In-process. (Future) |
| Graph | 4 | `cpsd_graph.c` | Graph DB. (Future) |
| Blob | 5 | `cpsd_blob.c` | File/blob storage. (Future) |

### 8.4 Connection String Format

Each backend has its own connection string format, passed to `connect()`:

- **MySQL:** `mysql://user:pass@host:3306/dbname`
- **SQLite:** `sqlite:///path/to/database.db`
- **Qdrant:** `qdrant://localhost:6333/collection_name`
- **Vector:** `vector://mlx://path/to/index`
- **Graph:** `graph://localhost:7687`
- **Blob:** `blob:///path/to/storage/dir`

### 8.5 MySQL Driver Example

```c
static int mysql_connect(void **handle, const char *conn_str) {
    MYSQL *m = mysql_init(NULL);
    if (!m) return -1;
    // Parse conn_str: mysql://user:pass@host:port/db
    // ...
    if (!mysql_real_connect(m, host, user, pass, db, port, NULL, 0)) {
        mysql_close(m);
        return -1;
    }
    *handle = m;
    return 0;
}

static int mysql_prepare(void *handle, const char *sql, void **stmt) {
    MYSQL_STMT *s = mysql_stmt_init((MYSQL *)handle);
    if (!s) return -1;
    if (mysql_stmt_prepare(s, sql, strlen(sql))) {
        mysql_stmt_close(s);
        return -1;
    }
    *stmt = s;
    return 0;
}

static int mysql_bind(void *stmt, int idx, param_type_t type,
                      const void *value, uint32_t len) {
    MYSQL_BIND bind;
    memset(&bind, 0, sizeof(bind));
    bind.buffer = (void *)value;
    bind.buffer_length = len;
    // Map param_type_t to MySQL types...
    return mysql_stmt_bind_param((MYSQL_STMT *)stmt, &bind);
}

// ... execute, fetch, close_stmt, begin_txn, commit_txn, rollback_txn, ping, error
```

---

## 9. Query Registry

### 9.1 Principle

**No raw SQL from clients.** Clients send a numeric `cmd_id` and typed parameters. CPSD looks up the SQL template from an internal registry, prepares it, binds the parameters, and executes. The registry is loaded at boot from config (see Section 12.4) and can be reloaded via `admin_reload`.

### 9.2 Registry Entry

```c
typedef struct {
    uint16_t          cmd_id;           // Numeric ID (1..511)
    const char       *name;             // Human-readable name
    const char       *sql;              // SQL template with ? placeholders
    storage_backend_t backend;          // Which backend to use
    operation_t       operation;        // OP_SELECT / OP_INSERT / etc.
    int               param_count;      // Expected parameter count
    param_type_t      param_types[16];  // Expected parameter types
    void             *prepared_stmt;    // Cached prepared statement (if any)
    bool              is_destructive;   // Pre-flagged for destruction guard
} query_entry_t;
```

### 9.3 Registry API

```c
int  query_registry_init(void);
void query_registry_shutdown(void);
int  query_registry_register(const query_entry_t *entry);
const query_entry_t* query_registry_lookup(uint16_t cmd_id);
int  query_registry_size(void);
int  query_registry_load_from_file(const char *path);
```

### 9.4 Built-in Command IDs

These are defined in the protocol and always available:

| cmd_id | Name | Description |
|--------|------|-------------|
| 1 | CMD_QUERY | Execute a registered query (param[0] = sub-cmd_id, rest = params) |
| 2 | CMD_TABLES | List tables on the specified backend |
| 3 | CMD_SCHEMA | Get schema for a table (param[0] = table name) |
| 4 | CMD_PING | Health check (no params, returns pong) |
| 5 | CMD_BATCH | Execute a query in batch mode (multiple param sets) |
| 6 | CMD_BEGIN | Begin transaction |
| 7 | CMD_COMMIT | Commit transaction |
| 8 | CMD_ROLLBACK | Rollback transaction |
| 9 | CMD_ADMIN | Admin command (param[0] = admin sub-command) |

### 9.5 User-Defined Command IDs

User queries are registered with `cmd_id` values 100..511. Example registry entries:

```
cmd_id=100  name="get_user_by_id"
    sql="SELECT id, name, email FROM users WHERE id = ?"
    backend=MySQL  operation=OP_SELECT  param_count=1  param_types=[INT64]

cmd_id=101  name="insert_session"
    sql="INSERT INTO sessions (user_id, token, expires) VALUES (?, ?, ?)"
    backend=MySQL  operation=OP_INSERT  param_count=3
    param_types=[INT64, STRING, INT64]

cmd_id=200  name="delete_expired_sessions"
    sql="DELETE FROM sessions WHERE expires < ?"
    backend=MySQL  operation=OP_DELETE  param_count=1  param_types=[INT64]
    is_destructive=true

cmd_id=300  name="vector_search"
    sql="SEARCH collection=embeddings LIMIT 10"
    backend=Qdrant  operation=OP_SELECT  param_count=1  param_types=[BLOB]
```

### 9.6 Execution Flow

```
Client sends frame: cmd_id=100, params=[42]
    ↓
IPC layer parses frame → request_t
    ↓
Security: authenticate token → role=reader
    ↓
Security: perm_check(reader, MySQL, cmd_id=100, OP_SELECT) → OK
    ↓
Security: rate_check → OK
    ↓
Query Engine: registry_lookup(100) → query_entry_t
    ↓
Validation: validate_params(entry, params, 1) → OK
    ↓
Destruction Guard: check(sql, confirm) → OK (not destructive)
    ↓
Plugin: fire(HOOK_PRE_QUERY) → OK
    ↓
Cache: check(stmt cache for cmd_id=100) → hit or miss
    ↓
Pool: acquire(MySQL) → connection handle
    ↓
Storage: prepare(handle, sql) → stmt (or reuse cached)
    ↓
Storage: bind(stmt, 0, INT64, &42, 8)
    ↓
Storage: execute(stmt)
    ↓
Storage: fetch(stmt, resp, 10000) → rows
    ↓
Pool: release(MySQL, handle)
    ↓
Plugin: fire(HOOK_POST_QUERY) → OK
    ↓
Cache: put(result in object cache)
    ↓
IPC: build_response → frame
    ↓
IPC: frame_write → client
```

---

## 10. State Machines

### 10.1 Kernel State Machine

The kernel is always in exactly one state. Transitions are validated — illegal transitions return -1.

```
INIT ──────→ LOADING ──────→ READY
  │             │              │
  │             │              ├──→ RELOAD ──→ READY
  │             │              │
  │             │              ├──→ DRAINING ──→ STOPPED
  │             │              │
  │             ↓              ↓
  └──────→ FAULT ←─────────────┘
               │
               ├──→ DRAINING ──→ STOPPED
               │
               └──→ STOPPED
                                    │
                          STOPPED ──→ INIT (restart)
```

**States:**

| State | Description | Accepts new clients? | Processes queries? |
|-------|-------------|---------------------|---------------------|
| INIT | Just started, nothing loaded | No | No |
| LOADING | Loading config, registry, drivers | No | No |
| READY | Fully operational | Yes | Yes |
| RELOAD | Re-loading config/registry, serving existing | No (new queued) | Yes (existing) |
| DRAINING | Shutting down, waiting for in-flight queries | No | No (waiting for complete) |
| STOPPED | Process exited or about to exit | No | No |
| FAULT | Critical error, must drain and stop | No | No |

**Transition rules (from `can_transition` in `cpsd_state.c`):**

```c
INIT     → LOADING, FAULT, STOPPED
LOADING  → READY, FAULT, STOPPED
READY    → RELOAD, DRAINING, FAULT
RELOAD   → READY, FAULT, DRAINING
DRAINING → STOPPED, FAULT
STOPPED  → INIT
FAULT    → STOPPED, DRAINING
```

**C signatures:**
```c
kern_state_t kern_state_get(void);
int          kern_state_transition(kern_state_t target);
int          kern_state_is_serving(void);  // returns 1 if READY or RELOAD
const char*  kern_state_name(kern_state_t s);
```

### 10.2 Service Lifecycle State Machine

The lifecycle node drives the kernel state through boot and shutdown.

```
POWER_OFF → STARTING → BOOTING → RUNNING → STOPPING → POWER_OFF
                         │          │
                         ↓          ↓
                       BOOT_FAIL  FAULT → RECOVERY → RUNNING (or STOPPING)
```

| Lifecycle State | Kernel State | Action |
|-----------------|-------------|--------|
| POWER_OFF | STOPPED | Process not running |
| STARTING | INIT | `cpsd_boot()` called |
| BOOTING | LOADING | Loading config, registry, drivers, pool |
| RUNNING | READY | Normal operation |
| STOPPING | DRAINING | `cpsd_drain()` called, waiting for queries |
| BOOT_FAIL | FAULT | Boot step failed |
| RECOVERY | LOADING | WAL replay after crash |

### 10.3 Connection Pool State Machine

Per-connection state within a pool:

```
IDLE ──acquire──→ ACQUIRED ──prepare──→ IN_USE ──release──→ IDLE
  │                                              │
  │                                              ↓
  └──health_fail──→ DEAD ──cleanup──→ CLOSED     │
                                                 │
  IDLE ──idle_timeout──→ CLOSED                  │
                                                 │
  IN_USE ──query_error──→ ERROR ──release──→ DEAD ──cleanup──→ CLOSED
```

Pool-level state:

```
UNINIT → INITIALIZING → ACTIVE ⇄ EXPANDING → DRAINING → CLOSED
                              │
                              ↓
                         EXHAUSTED (all in use, waiting)
```

**C signatures:**
```c
int  pool_init(storage_backend_t backend, int pool_size, const char *conn_str);
void pool_shutdown(storage_backend_t backend);
int  pool_acquire(storage_backend_t backend, void **handle);
int  pool_release(storage_backend_t backend, void *handle);
int  pool_health_check(storage_backend_t backend);
int  pool_stats(storage_backend_t backend, int *total, int *in_use, int *idle);
```

### 10.4 Transaction State Machine

Per-client transaction context:

```
NONE ──begin──→ ACTIVE ──commit──→ COMMITTED ──→ NONE
                   │
                   ├───rollback──→ ROLLED_BACK ──→ NONE
                   │
                   ├───savepoint──→ SAVEPOINT_SET
                   │                    │
                   │                    ├───rollback_to──→ ACTIVE
                   │                    └───release──→ ACTIVE
                   │
                   └───error──→ FAILED ──→ rollback ──→ NONE
```

**C signatures:**
```c
int  query_txn_begin(void);
int  query_txn_commit(void);
int  query_txn_rollback(void);
int  query_txn_savepoint(const char *name);
int  query_txn_rollback_to(const char *name);
int  query_txn_in_progress(void);
```

---

## 11. File Structure

All CPSD files live in `Cascade_toolStack/bcl_units/`. The naming convention is `cpsd_<module>.c` / `cpsd_<module>.h`.

### 11.1 Header Files

| File | Layer | Purpose |
|------|-------|---------|
| `cpsd.h` | All | Master header — all constants, types, function declarations |
| `cpsd_state.h` | 0 | Kernel state machine declarations |
| `cpsd_event.h` | 0 | Event bus declarations |
| `cpsd_loop.h` | 0 | Event loop (kqueue) declarations |
| `cpsd_msg.h` | 0 | Message bus declarations |
| `cpsd_signal.h` | 0 | Signal handling declarations |
| `cpsd_resource.h` | 0 | Resource limits declarations |
| `cpsd_watchdog.h` | 0 | Watchdog timer declarations |
| `cpsd_ipc.h` | 1 | IPC socket declarations |
| `cpsd_protocol.h` | 1 | Wire protocol declarations |
| `cpsd_security.h` | 2 | Security (auth, RBAC, rate, audit) declarations |
| `cpsd_guard.h` | 2 | Destruction guard declarations |
| `cpsd_validate.h` | 2 | Parameter validation declarations |
| `cpsd_storage.h` | 3 | Storage driver interface declarations |
| `cpsd_pool.h` | 3 | Connection pool declarations |
| `cpsd_mysql.h` | 3 | MySQL driver declarations |
| `cpsd_sqlite.h` | 3 | SQLite driver declarations |
| `cpsd_query.h` | 4 | Query engine declarations |
| `cpsd_registry.h` | 4 | Query registry declarations |
| `cpsd_txn.h` | 4 | Transaction management declarations |
| `cpsd_meta.h` | 4 | Metadata introspection declarations |
| `cpsd_cache.h` | 5 | Cache declarations |
| `cpsd_plugin.h` | 6 | Plugin/hook declarations |
| `cpsd_admin.h` | 7 | Admin command declarations |
| `cpsd_health.h` | Cross | Health check declarations |
| `cpsd_metrics.h` | Cross | Metrics declarations |
| `cpsd_wal.h` | Cross | WAL declarations |
| `cpsd_log.h` | Cross | Logging declarations |
| `cpsd_config.h` | Cross | Config parser declarations |
| `cpsd_identity.h` | Cross | Process identity declarations |
| `cpsd_lifecycle.h` | Cross | Boot/shutdown orchestration declarations |
| `cpsd_client.h` | 8 | Client library declarations |
| `cpsd_os.h` | 0 | OS-specific abstractions |

### 11.2 Source Files

| File | Layer | BND | Phase | Lines (est) | Purpose |
|------|-------|-----|-------|-------------|---------|
| `cpsd.h` | All | — | 1 | ~500 | Master header |
| `cpsd_main.c` | 0 | 03,18 | 1 | ~150 | Entry point: `main()`, boot, loop, shutdown |
| `cpsd_state.c` | 0 | 03 | 1 | ~80 | Kernel state machine (exists) |
| `cpsd_event.c` | 0 | 15 | 1 | ~110 | Event bus pub/sub (exists) |
| `cpsd_loop.c` | 0 | 19 | 1 | ~170 | kqueue event loop (exists) |
| `cpsd_msg.c` | 0 | — | 1 | ~140 | Message bus queue (exists) |
| `cpsd_signal.c` | 0 | 19 | 2 | ~120 | Signal handling |
| `cpsd_resource.c` | 0 | 19 | 2 | ~100 | Resource limits (RLIMIT) |
| `cpsd_watchdog.c` | 0 | 12 | 2 | ~130 | Watchdog timer |
| `cpsd_config.c` | Cross | 02 | 3 | ~200 | Config file parser |
| `cpsd_log.c` | Cross | 13 | 3 | ~180 | Leveled logging with rotation |
| `cpsd_identity.c` | Cross | 01 | 3 | ~80 | PID file, version |
| `cpsd_ipc.c` | 1 | — | 4 | ~250 | Unix socket server |
| `cpsd_protocol.c` | 1 | — | 4 | ~350 | Frame read/write/parse/build |
| `cpsd_security.c` | 2 | 04 | 5 | ~350 | Auth, RBAC, rate limit, audit |
| `cpsd_guard.c` | 2 | 04 | 5 | ~150 | Destruction guard |
| `cpsd_validate.c` | 2 | 05 | 5 | ~200 | Parameter validation |
| `cpsd_storage.c` | 3 | 06 | 6 | ~200 | Driver registry |
| `cpsd_pool.c` | 3 | 11 | 6 | ~250 | Connection pool |
| `cpsd_mysql.c` | 3 | 06 | 6 | ~400 | MySQL driver |
| `cpsd_sqlite.c` | 3 | 06 | 6 | ~300 | SQLite driver |
| `cpsd_registry.c` | 4 | 07 | 7 | ~200 | Query registry |
| `cpsd_query.c` | 4 | 07 | 7 | ~350 | Query execution engine |
| `cpsd_txn.c` | 4 | 08 | 7 | ~200 | Transaction management |
| `cpsd_meta.c` | 4 | 09 | 7 | ~200 | Metadata introspection |
| `cpsd_cache.c` | 5 | 10 | 8 | ~350 | LRU cache |
| `cpsd_plugin.c` | 6 | 16 | 8 | ~200 | Hook system |
| `cpsd_wal.c` | Cross | 14 | 9 | ~250 | Write-ahead log |
| `cpsd_health.c` | Cross | 12 | 9 | ~150 | Health checks |
| `cpsd_metrics.c` | Cross | 12 | 9 | ~150 | Metrics counters |
| `cpsd_admin.c` | 7 | 17 | 9 | ~300 | Admin commands |
| `cpsd_client.c` | 8 | — | 10 | ~300 | Client library |
| `cpsd_cli.c` | 8 | — | 10 | ~300 | CLI tool |
| `cpsd_lifecycle.c` | Cross | 18 | 10 | ~150 | Boot/shutdown orchestration |

### 11.3 Build

The `Makefile` in `Cascade_toolStack/bcl_units/` compiles all `cpsd_*.c` files into the `cpsd` binary and `cpsd_cli` into the CLI tool.

```makefile
CPSD_SRCS = cpsd_main.c cpsd_state.c cpsd_event.c cpsd_loop.c cpsd_msg.c \
            cpsd_signal.c cpsd_resource.c cpsd_watchdog.c \
            cpsd_config.c cpsd_log.c cpsd_identity.c \
            cpsd_ipc.c cpsd_protocol.c \
            cpsd_security.c cpsd_guard.c cpsd_validate.c \
            cpsd_storage.c cpsd_pool.c cpsd_mysql.c cpsd_sqlite.c \
            cpsd_registry.c cpsd_query.c cpsd_txn.c cpsd_meta.c \
            cpsd_cache.c cpsd_plugin.c \
            cpsd_wal.c cpsd_health.c cpsd_metrics.c cpsd_admin.c \
            cpsd_lifecycle.c

CPSD_OBJS = $(CPSD_SRCS:.c=.o)

cpsd: $(CPSD_OBJS)
	$(CC) $(CFLAGS) -o $@ $(CPSD_OBJS) $(LDFLAGS) -lmysqlclient -lpthread

cpsd_cli: cpsd_cli.c cpsd_client.c
	$(CC) $(CFLAGS) -o $@ cpsd_cli.c cpsd_client.c -lpthread
```

---

## 12. Config

### 12.1 Config File

CPSD reads its configuration from `/tmp/cpsd.conf` at boot. On `SIGHUP` or `admin_reload`, it re-reads the file and applies changes (where hot-reloadable).

Format is `key = value` (INI-style, no sections — flat namespace). Lines starting with `#` are comments. Blank lines ignored.

```
# CPSD Configuration File
# /tmp/cpsd.conf

# ── General ──
instance_name   = cpsd_prod
socket_path     = /tmp/cpsd.sock
pid_file        = /tmp/cpsd.pid
log_dir         = /tmp/cpsd_logs
log_level       = INFO
wal_file        = /tmp/cpsd_logs/cpsd.wal
config_reload   = true

# ── Limits ──
max_clients     = 64
max_request     = 131072
max_response    = 1048576
max_params      = 32
max_param_len   = 65536
max_rows        = 10000
max_cols        = 64

# ── Pool ──
pool_size       = 8
pool_idle_timeout = 300

# ── Cache ──
cache_max_entries = 4096
cache_max_bytes   = 67108864

# ── Rate Limiting ──
rate_limit_qps    = 100
rate_limit_burst  = 200

# ── Watchdog ──
watchdog_timeout  = 30
health_interval   = 10

# ── Backends ──
backend_mysql_conn  = mysql://root@localhost:3306/vb_shared
backend_sqlite_conn = sqlite:///tmp/cpsd_data.db
backend_qdrant_conn = qdrant://localhost:6333/cascade

# ── Security ──
token_dir       = /tmp/cpsd_tokens
audit_log       = /tmp/cpsd_logs/cpsd_audit.log
role_file       = /tmp/cpsd_tokens/roles.conf
acl_file        = /tmp/cpsd_tokens/acl.conf

# ── Query Registry ──
query_registry_file = /tmp/cpsd_queries.conf
```

### 12.2 Config API

```c
int  cpsd_config_load(const char *path);
void cpsd_config_free(void);
const char* cpsd_config_get(const char *key);
int  cpsd_config_get_int(const char *key, int default_val);
int  cpsd_config_reload(void);
int  cpsd_config_validate(void);
```

### 12.3 Token Files

Tokens are how clients authenticate. Each token is a file in `/tmp/cpsd_tokens/`. The filename is the token string. The file contents specify the role.

**Token file:** `/tmp/cpsd_tokens/<token_string>`
**Contents:**
```
role = writer
client_pid = 0
description = BCL unit bcl_search_db.c
```

When a client connects, it sends its token string in the first frame (a special `MSG_REQUEST` with `cmd_id=0` and `param[0]` = token string). CPSD looks up `/tmp/cpsd_tokens/<token>`, reads the role, and creates an `auth_context_t`.

Example token files:

```
/tmp/cpsd_tokens/admin_7f3a2b9e1c
    role = admin
    description = Cascade admin CLI

/tmp/cpsd_tokens/writer_bcl_4d8e1f2a3b
    role = writer
    description = BCL unit bcl_search_db.c

/tmp/cpsd_tokens/reader_ai_9c2d4e7f1a
    role = ai_agent
    description = AI agent read-only access
```

Token files are created by the admin and must have `0600` permissions (owner read/write only). CPSD refuses to load world-readable token files.

### 12.4 Role Definitions

The role file `/tmp/cpsd_tokens/roles.conf` defines the six roles and their base permissions. This is loaded at boot and validated.

```
# /tmp/cpsd_tokens/roles.conf
# Role definitions — base permission sets

role = admin
    select = true
    insert = true
    update = true
    delete = true
    batch = true
    admin = true
    destructive = guard    # allowed but destruction guard still runs

role = writer
    select = true
    insert = true
    update = true
    delete = true
    batch = true
    admin = false
    destructive = deny

role = reader
    select = true
    insert = false
    update = false
    delete = false
    batch = false
    admin = false
    destructive = deny

role = ai_agent
    select = true
    insert = true
    insert_prefix = ai_    # can only insert into tables starting with ai_
    update = false
    delete = false
    batch = true
    admin = false
    destructive = deny
    rate_qps = 50
    rate_burst = 100

role = cli
    select = true
    insert = true
    insert_prefix = cli_
    update = true
    update_prefix = cli_
    delete = false
    batch = false
    admin = false
    destructive = deny
    rate_qps = 20
    rate_burst = 40

role = internal
    select = true
    insert = false
    update = false
    delete = false
    batch = false
    admin = status_only    # only status/metrics/health
    destructive = deny
```

### 12.5 ACL (Access Control List)

The ACL file `/tmp/cpsd_tokens/acl.conf` provides fine-grained per-table, per-query overrides on top of the role definitions. This is where specific tables can be locked down or opened up beyond the role default.

```
# /tmp/cpsd_tokens/acl.conf
# Fine-grained access control
# Format: allow|deny role backend table operation

# AI agent can read from users table (override: normally reader-level)
allow ai_agent mysql users select

# AI agent can write to ai_memory table (explicit)
allow ai_agent mysql ai_memory insert
allow ai_agent mysql ai_memory update

# CLI can read from learned_rules
allow cli mysql learned_rules select

# Writer cannot delete from governance table (override: normally allowed)
deny writer mysql governance delete

# Reader can access metadata queries
allow reader mysql * select

# Internal can run health check queries
allow internal mysql * select
allow internal mysqlcpsd_health select
```

### 12.6 Query Registry File

The query registry file `/tmp/cpsd_queries.conf` defines all user-registered queries. This is loaded at boot and can be reloaded via `admin_reload`.

```
# /tmp/cpsd_queries.conf
# Query registry — numeric cmd_id → SQL template mapping
# Format:
#   [cmd_id]
#   name = <name>
#   sql = <sql with ? placeholders>
#   backend = mysql|sqlite|qdrant|vector|graph|blob
#   operation = select|insert|update|delete|batch|admin
#   param_count = <n>
#   param_types = <type1>,<type2>,...
#   destructive = true|false

[100]
name = get_user_by_id
sql = SELECT id, name, email FROM users WHERE id = ?
backend = mysql
operation = select
param_count = 1
param_types = int64
destructive = false

[101]
name = insert_session
sql = INSERT INTO sessions (user_id, token, expires) VALUES (?, ?, ?)
backend = mysql
operation = insert
param_count = 3
param_types = int64,string,int64
destructive = false

[200]
name = delete_expired_sessions
sql = DELETE FROM sessions WHERE expires < ?
backend = mysql
operation = delete
param_count = 1
param_types = int64
destructive = true

[300]
name = get_learned_rules
sql = SELECT pattern, fix_action, confidence FROM learned_rules WHERE pattern LIKE ? ORDER BY confidence DESC LIMIT ?
backend = mysql
operation = select
param_count = 2
param_types = string,int32
destructive = false

[400]
name = vector_search
sql = SEARCH collection=embeddings LIMIT 10
backend = qdrant
operation = select
param_count = 1
param_types = blob
destructive = false
```

### 12.7 Directory Layout

```
/tmp/
├── cpsd.conf                          # Main config
├── cpsd.sock                          # Unix socket (created at boot)
├── cpsd.pid                           # PID file (created at boot)
├── cpsd_tokens/                       # Token files
│   ├── roles.conf                     # Role definitions
│   ├── acl.conf                       # Access control list
│   ├── admin_7f3a2b9e1c               # Admin token
│   ├── writer_bcl_4d8e1f2a3b          # Writer token (BCL unit)
│   └── reader_ai_9c2d4e7f1a           # AI agent token
├── cpsd_queries.conf                  # Query registry
└── cpsd_logs/
    ├── cpsd.log                       # Main log
    ├── cpsd_audit.log                 # Audit log
    └── cpsd.wal                       # Write-ahead log
```

---

## Appendix A: VBStyle Compliance

All CPSD files carry VBStyle headers:

```c
//[@GHOST]{file_path="Cascade_toolStack/bcl_units/cpsd_state.c" date="2026-07-04" author="Devin" session_id="cpsd-microkernel" context="CPSD Layer 0: Kernel state machine"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE no-print state-machine"}
//[@FILEID]{id="cpsd_state.c" domain="cpsd_kernel" authority="CpsdState"}
//[@SUMMARY]{summary="Kernel state machine. Tracks process lifecycle."}
//[@CLASS]{class="CpsdState" domain="cpsd_kernel" authority="single"}
//[@METHOD]{methods="kern_state_name,kern_state_get,kern_state_transition,kern_state_is_serving"}
```

Rules enforced:
- PascalCase for functions and types
- UPPERCASE for constants and macros
- No `printf()` — all output via `log_write()`
- No `@property`, `@staticmethod`, `@classmethod` (C has no such concepts, but the rule carries)
- No tabs — spaces only
- No trailing whitespace
- Every file has identity headers

---

## Appendix B: Existing Implementation Status

As of this spec, the following files exist and are functional:

| File | Status | Notes |
|------|--------|-------|
| `cpsd.h` | Complete | Master header with all 9-layer declarations |
| `cpsd_state.c` | Complete | Kernel state machine with mutex, transition validation, event publish |
| `cpsd_event.c` | Complete | Event bus with subscribe/unsubscribe/publish, 8 handlers per type |
| `cpsd_loop.c` | Partial | kqueue loop works; `kern_loop_remove` needs fd→slot mapping fix |
| `cpsd_msg.c` | Complete | Message bus with timeout recv, deep copy payload |

**Next files to build:** `cpsd_signal.c`, `cpsd_resource.c`, `cpsd_watchdog.c` (Phase 2), then `cpsd_config.c`, `cpsd_log.c`, `cpsd_identity.c` (Phase 3).

---

*End of CPSD Engineering Specification v1.0.0*
