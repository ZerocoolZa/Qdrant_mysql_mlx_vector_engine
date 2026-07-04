//[@GHOST]{file_path="Cascade_toolStack/bcl_units/CPSD_PLAN.md" date="2026-07-04" author="Devin" session_id="cpsd-microkernel" context="CPSD (Cascade Persistent Data Service) — 10-phase build plan for the C microkernel that is the ONLY door into MySQL"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE prepared-statements-only destruction-guard RBAC layered-architecture"}
//[@FILEID]{id="CPSD_PLAN.md" domain="cpsd_kernel" authority="CpsdBuildPlan"}
//[@SUMMARY]{summary="10-phase build plan for CPSD microkernel. ~5,000 lines of C. Enforces prepared statements, destruction guard, RBAC, pooling, query registry, WAL, plugins. Every phase lists nodes, files, key functions, dependencies, line estimates, and verification steps."}
//[@CLASS]{class="CpsdBuildPlan" domain="cpsd_kernel" authority="single"}
//[@METHOD]{methods="phase1_core_kernel,phase2_ipc_transport,phase3_storage_pool,phase4_query_engine,phase5_security,phase6_cache,phase7_log_monitor_wal,phase8_plugin_event,phase9_transactions,phase10_admin_cascadectl"}

# CPSD — Cascade Persistent Data Service
## 10-Phase Build Plan

**CPSD** is a C microkernel that is the ONLY door into MySQL. No process talks to
MySQL directly. Every query goes through CPSD, which enforces:

- **Prepared statements only** — no string-concatenated SQL ever reaches MySQL
- **Destruction guard** — DROP / TRUNCATE / DELETE-WITHOUT-WHERE blocked unless confirmed
- **RBAC** — six roles (admin, writer, reader, ai_agent, cli, internal) with permission matrix
- **Connection pooling** — acquire / release / refcount, no connection storms
- **Query registry** — numeric `cmd_id` → SQL template, 200+ entries for laws + vb_shared tables
- **WAL** — write-ahead log for crash recovery
- **Plugin hooks** — dlopen-based, 10 hook points

Total estimated: **~5,000 lines of C** across 10 phases.

---

## Architecture Overview

```
                    ┌──────────────────────────────────────────┐
                    │              CPSD MICROKERNEL             │
                    │                                          │
  Client ──socket──►│  IPC ──► Security ──► QueryEngine ──►     │──MySQL
  (CLI/AI/Tool)     │  (BND-02) (BND-04)  (BND-07,05,09)       │
                    │                    │                      │
                    │  Cache ◄───────────┘  Storage+Pool        │
                    │  (BND-10)              (BND-06,11)         │
                    │                                          │
                    │  Core Kernel (BND-01,03,18,19)            │
                    │  Log+WAL+Health (BND-13,12,14)            │
                    │  Plugins (BND-15,16)  Admin (BND-17)      │
                    └──────────────────────────────────────────┘
```

### BND (Boundary) Node Reference

| BND  | Name              | Layer  | Phase |
|------|-------------------|--------|-------|
| 01   | Process Lifecycle | Core   | 1     |
| 02   | IPC Transport     | IPC    | 2     |
| 03   | State Machine     | Core   | 1     |
| 04   | Security/RBAC     | Sec    | 5     |
| 05   | Validation        | Query  | 4     |
| 06   | Storage Engine    | Storage| 3     |
| 07   | Query Engine      | Query  | 4     |
| 08   | Transactions      | Query  | 9     |
| 09   | Metadata/Schema   | Query  | 4     |
| 10   | Cache             | Cache  | 6     |
| 11   | Connection Pool   | Storage| 3     |
| 12   | Health Monitor    | Ops    | 7     |
| 13   | Structured Log    | Ops    | 7     |
| 14   | WAL               | Ops    | 7     |
| 15   | Plugin Loader     | Plugin | 8     |
| 16   | Event Hooks       | Plugin | 8     |
| 17   | Admin/CascadeCtl  | Admin  | 10    |
| 18   | Resource Limits   | Core   | 1     |
| 19   | Watchdog          | Core   | 1     |

---

## Build Command

```bash
# Single-file compile (phases 1-3):
cc -Wall -Wextra -O2 -g \
   cpsd_main.c cpsd_state.c cpsd_event.c cpsd_loop.c cpsd_msg.c \
   cpsd_signal.c cpsd_resource.c cpsd_watchdog.c \
   ipc_socket.c ipc_protocol.c ipc_client.c \
   storage.c storage_mysql.c storage_pool.c \
   -o cpsd \
   $(mysql_config --cflags --libs) \
   -lsqlite3 -lpthread

# Full build (all 10 phases):
cc -Wall -Wextra -O2 -g \
   cpsd_main.c cpsd_state.c cpsd_event.c cpsd_loop.c cpsd_msg.c \
   cpsd_signal.c cpsd_resource.c cpsd_watchdog.c \
   ipc_socket.c ipc_protocol.c ipc_client.c \
   storage.c storage_mysql.c storage_pool.c \
   query_engine.c query_registry.c query_validate.c cpsd_schema.c \
   sec_auth.c sec_perm.c sec_role.c sec_audit.c sec_rate.c \
   cache.c cache_lru.c \
   log.c health.c wal.c backup.c \
   plugin.c plugin_hooks.c \
   query_txn.c \
   admin.c admin_ctl.c \
   -o cpsd \
   $(mysql_config --cflags --libs) \
   -lsqlite3 -lpthread -ldl

# CascadeCtl (admin CLI):
cc -Wall -Wextra -O2 -g admin_ctl.c -o cpsd_ctl -lpthread
```

**Linker flags rationale:**
- `$(mysql_config --cflags --libs)` — libmysqlclient for `mysql_stmt_prepare`, `mysql_stmt_bind_param`, `mysql_stmt_execute`
- `-lsqlite3` — local metadata cache, query registry persistence
- `-lpthread` — mutexes, connection pool, watchdog thread
- `-ldl` — `dlopen` / `dlsym` for plugin loading (Phase 8)

---

## Phase 1: Core Kernel (BND-01, 03, 18, 19) — ~900 lines

**Goal:** Process lifecycle, state machine, event bus, event loop (kqueue), message
bus, signal handling, resource limits, watchdog. The foundation every other layer
sits on.

### Nodes Involved
- BND-01: Process Lifecycle (init → loading → ready → draining → stopped)
- BND-03: State Machine (thread-safe transitions, event publication)
- BND-18: Resource Limits (max clients, memory, FDs, query time)
- BND-19: Watchdog (per-module heartbeat, timeout trip)

### Files

| File               | Status      | Lines | Responsibility                                      |
|--------------------|-------------|-------|-----------------------------------------------------|
| `cpsd.h`           | DONE        | ~490  | Master header — all layer interfaces                |
| `cpsd_state.c`     | DONE        | ~82   | State machine, mutex-protected transitions          |
| `cpsd_event.c`     | DONE        | ~110  | Event bus, subscribe/publish                        |
| `cpsd_loop.c`      | DONE        | ~160  | kqueue event loop, timer support                    |
| `cpsd_msg.c`       | DONE        | ~120  | Internal message bus (module-to-module)             |
| `cpsd_signal.c`    | REMAINING   | ~120  | SIGTERM/SIGINT/SIGHUP/SIGPIPE handlers              |
| `cpsd_resource.c`  | REMAINING   | ~130  | Resource limit enforcement (clients, mem, FDs)      |
| `cpsd_watchdog.c`  | REMAINING   | ~150  | Per-module heartbeat, timeout detection             |
| `cpsd_main.c`      | REMAINING   | ~200  | main(), arg parsing, bootstrap sequence, daemonize  |

### Key Functions

**cpsd_signal.c**
- `kern_signal_init()` — install handlers, block SIGPIPE
- `kern_signal_register(int signo, signal_handler_t handler)` — add to handler table
- `kern_signal_shutdown()` — restore default handlers
- Internal: `sig_handler(int signo)` — dispatch to registered handler, publish event

**cpsd_resource.c**
- `kern_resource_init(resource_limits_t *limits)` — set caps from config
- `kern_resource_check_clients(int current)` — reject if > max_clients
- `kern_resource_check_memory(size_t used_bytes)` — reject if > max_memory_mb
- `kern_resource_check_fd(int current_fd_count)` — reject if > max_file_descriptors
- `kern_resource_get()` — return pointer to active limits

**cpsd_watchdog.c**
- `kern_watchdog_init(int timeout_sec, watchdog_callback_t callback)` — spawn monitor thread
- `kern_watchdog_kick(int module_id)` — module reports alive
- `kern_watchdog_check()` — scan all modules, trip if stale
- `kern_watchdog_tick()` — called by monitor thread every 1s
- Internal: `watchdog_thread(void *arg)` — pthread loop

**cpsd_main.c**
- `main(int argc, char **argv)` — parse `--version`, `--config`, `--daemon`
- `bootstrap()` — init order: signal → resource → event → loop → msg → watchdog
- `daemonize()` — fork, setsid, redirect stdio
- `shutdown_sequence()` — drain → stop modules → close socket → exit

### Dependencies on Prior Phases
None — this is the foundation.

### Verification Steps
1. Compile all 9 files together:
   ```bash
   cc -Wall -Wextra -g cpsd_main.c cpsd_state.c cpsd_event.c cpsd_loop.c \
      cpsd_msg.c cpsd_signal.c cpsd_resource.c cpsd_watchdog.c \
      -o cpsd -lpthread
   ```
2. Run `./cpsd --version` → prints `CPSD 1.0.0`
3. Run `./cpsd --daemon` → process backgrounds, writes PID to `/tmp/cpsd.pid`
4. Send `kill -TERM $(cat /tmp/cpsd.pid)` → clean shutdown, state goes READY→DRAINING→STOPPED
5. State machine test: verify `kern_state_transition(KERN_STATE_READY)` from INIT fails (must go through LOADING), succeeds after LOADING
6. Watchdog test: register a module, do NOT kick it, verify callback fires after `timeout_sec`
7. Resource test: set max_clients=2, open 3 connections, verify 3rd rejected

---

## Phase 2: IPC Transport (BND-02) — ~600 lines

**Goal:** Unix domain socket server + binary wire protocol. Clients connect,
send framed requests, receive framed responses.

### Nodes Involved
- BND-02: IPC Transport (socket, framing, protocol versioning)

### Files

| File              | Lines | Responsibility                                  |
|-------------------|-------|-------------------------------------------------|
| `ipc_socket.c`    | ~200  | Unix domain socket create/bind/listen/accept    |
| `ipc_protocol.c`  | ~250  | Binary frame encode/decode, request parse       |
| `ipc_client.c`    | ~150  | Test client library (connect, send, recv)       |

### Binary Protocol

```
Frame layout (little-endian):
┌──────────┬───────────┬──────────┬────────────┬───────────────┐
│ MAGIC    │ VERSION   │ MSG_TYPE │ REQUEST_ID │ PAYLOAD_LEN   │
│ 4 bytes  │ 1 byte    │ 1 byte   │ 4 bytes    │ 4 bytes       │
│ "CDB1"   │ 0x01      │ see enum │ uint32     │ uint32        │
└──────────┴───────────┴──────────┴────────────┴───────────────┘
│ PAYLOAD (PAYLOAD_LEN bytes)                              │
│  cmd_id(2) + db_id(1) + param_count(1) + params[]        │
└──────────────────────────────────────────────────────────┘

Each param:
  type(1) + len(4) + value(len)

MAGIC = "CDB1"
VERSION = 0x01
MSG_TYPE: 0x01=REQUEST, 0x02=RESPONSE, 0x03=ERROR, 0x04=NOTIFY
```

### Key Functions

**ipc_socket.c**
- `ipc_socket_init(const char *path, int backlog)` — create AF_UNIX socket, bind, listen
- `ipc_socket_accept(int *client_fd, pid_t *client_pid)` — accept, get peer creds
- `ipc_socket_close()` — unlink socket file, close fd
- `ipc_socket_get_fd()` — return listen fd for event loop registration

**ipc_protocol.c**
- `ipc_frame_read(int fd, void *frame, size_t frame_size, size_t *frame_len)` — read full frame (handle partial reads)
- `ipc_frame_write(int fd, const void *frame, size_t frame_len)` — write full frame (handle partial writes)
- `ipc_parse_request(const void *frame, size_t len, request_t *req)` — decode binary → request_t
- `ipc_build_response(void *frame, size_t frame_size, size_t *frame_len, const response_t *resp)` — encode response_t → binary
- Internal: `read_n(int fd, void *buf, size_t n)`, `write_n(int fd, const void *buf, size_t n)`

**ipc_client.c**
- `ipc_client_connect(const char *path)` — connect to socket, return fd
- `ipc_client_send_request(int fd, const request_t *req)` — encode + send
- `ipc_client_recv_response(int fd, response_t *resp)` — recv + decode
- `ipc_client_close(int fd)`

### Dependencies on Prior Phases
- Phase 1: uses `kern_loop_add()` to register listen fd, `kern_event_publish()` for connect/disconnect events

### Verification Steps
1. Compile with Phase 1:
   ```bash
   cc -Wall -g cpsd_main.c cpsd_state.c cpsd_event.c cpsd_loop.c \
      cpsd_msg.c cpsd_signal.c cpsd_resource.c cpsd_watchdog.c \
      ipc_socket.c ipc_protocol.c ipc_client.c \
      -o cpsd -lpthread
   ```
2. Start server: `./cpsd`
3. Run test client: send `CMD_PING` (cmd_id=4, no params) → receive `RESPONSE` with status=0
4. Verify MAGIC bytes in frame: `xxd /tmp/cpsd.sock` traffic shows `43 44 42 31` ("CDB1")
5. Send malformed frame (wrong magic) → server closes connection, logs error
6. Send oversized payload (> `CPSD_MAX_REQUEST`) → server rejects with error frame
7. Connect 64 clients (max), 65th rejected with resource limit error

---

## Phase 3: Storage + Pool (BND-06, 11) — ~700 lines

**Goal:** Storage driver abstraction, MySQL driver using libmysqlclient prepared
statements, connection pool with acquire/release/refcount.

### Nodes Involved
- BND-06: Storage Engine (driver registration, backend abstraction)
- BND-11: Connection Pool (acquire, release, refcount, health check)

### Files

| File               | Lines | Responsibility                                      |
|--------------------|-------|-----------------------------------------------------|
| `storage.c`        | ~150  | Driver registry, connect/dispatch                   |
| `storage_mysql.c`  | ~350  | MySQL driver: prepare/bind/execute/fetch            |
| `storage_pool.c`   | ~200  | Connection pool: acquire/release/refcount/health    |

### Key Functions

**storage.c**
- `storage_register(storage_driver_t *driver)` — add driver to registry by backend type
- `storage_connect(storage_backend_t backend, const char *conn_str, void **handle)` — dispatch to driver
- `storage_disconnect(storage_backend_t backend, void *handle)`
- `storage_get_driver(storage_backend_t backend)` — return driver vtable

**storage_mysql.c** (implements `storage_driver_t` for `STORAGE_MYSQL`)
- `mysql_connect(void **handle, const char *conn_str)` — `mysql_init`, `mysql_real_connect`
- `mysql_disconnect(void *handle)` — `mysql_close`
- `mysql_prepare(void *handle, const char *sql, void **stmt)` — `mysql_stmt_init`, `mysql_stmt_prepare`
- `mysql_bind(void *stmt, int idx, param_type_t type, const void *value, uint32_t len)` — `MYSQL_BIND` array fill
- `mysql_execute(void *stmt)` — `mysql_stmt_execute`
- `mysql_fetch(void *stmt, response_t *resp, int max_rows)` — `mysql_stmt_store_result`, `mysql_stmt_fetch`, build response
- `mysql_begin_txn(void *handle)` — `mysql_real_query("START TRANSACTION")`
- `mysql_commit_txn(void *handle)` — `mysql_real_query("COMMIT")`
- `mysql_rollback_txn(void *handle)` — `mysql_real_query("ROLLBACK")`
- `mysql_ping(void *handle)` — `mysql_ping`, reconnect if needed
- `mysql_close_stmt(void *stmt)` — `mysql_stmt_close`
- `mysql_error_msg(void *handle)` — `mysql_error`

**storage_pool.c**
- `pool_init(storage_backend_t backend, int pool_size, const char *conn_str)` — pre-create `pool_size` connections
- `pool_acquire(storage_backend_t backend, void **handle)` — get idle conn, mark in-use, increment refcount
- `pool_release(storage_backend_t backend, void *handle)` — decrement refcount, return to idle if 0
- `pool_health_check(storage_backend_t backend)` — ping all connections, reconnect dead ones
- `pool_stats(storage_backend_t backend, int *total, int *in_use, int *idle)`
- Internal: `pool_entry_t` struct with `handle`, `refcount`, `in_use`, `last_used`

### Dependencies on Prior Phases
- Phase 1: watchdog kicks from pool health check thread
- Phase 2: not directly required, but pool serves query engine which is triggered by IPC

### Verification Steps
1. Compile with mysql_config:
   ```bash
   cc -Wall -g [phase1+phase2 files] storage.c storage_mysql.c storage_pool.c \
      -o cpsd $(mysql_config --cflags --libs) -lsqlite3 -lpthread
   ```
2. Connect to MySQL: `pool_init(STORAGE_MYSQL, 8, "localhost:3306:root::vb_shared")` → 8 connections created
3. Prepare statement: `mysql_prepare(handle, "SELECT id, class_name FROM vb_classes LIMIT ?", &stmt)` → success
4. Bind + execute: `mysql_bind(stmt, 0, PARAM_INT32, &5, 4)`, `mysql_execute(stmt)` → success
5. Fetch rows: `mysql_fetch(stmt, &resp, 100)` → resp.row_count > 0, columns populated
6. Pool acquire/release: acquire 8, 9th blocks (or queues), release 1, 9th succeeds
7. Pool health: kill one MySQL connection externally, run `pool_health_check` → dead conn reconnected
8. Pool stats: verify total=8, in_use + idle = 8

---

## Phase 4: Query Engine + Validation + Metadata (BND-07, 05, 09) — ~1200 lines

**Goal:** Query registry mapping numeric `cmd_id` → SQL template. 200+ entries
for laws + vb_shared tables. Parameter validation (type, range, UTF-8, null-byte,
FK). Schema metadata for FK checking.

### Nodes Involved
- BND-07: Query Engine (execute by cmd_id, batch, result building)
- BND-05: Validation (type-check, range-check, UTF-8, null-byte, FK)
- BND-09: Metadata/Schema (table/column/FK introspection)

### Files

| File                | Lines | Responsibility                                       |
|---------------------|-------|------------------------------------------------------|
| `query_engine.c`    | ~350  | Execute by cmd_id, batch, result → JSON              |
| `query_registry.c`  | ~400  | cmd_id → SQL template map, 200+ entries              |
| `query_validate.c`  | ~300  | Type/range/UTF-8/null-byte/FK validation             |
| `cpsd_schema.c`     | ~150  | Schema introspection (columns, FKs, types)           |

### Key Functions

**query_registry.c**
- `query_registry_init()` — allocate hash table, load from SQLite or hardcoded array
- `query_registry_register(const query_entry_t *entry)` — insert into hash table
- `query_registry_lookup(uint16_t cmd_id)` — return entry or NULL
- `query_registry_size()` — count
- `query_registry_shutdown()` — free all
- Internal: `register_default_queries()` — 200+ entries:
  - `CMD 1001`: `SELECT class_name FROM vb_code_test.vb_classes WHERE class_name LIKE ? LIMIT ?`
  - `CMD 1002`: `SELECT method_name FROM vb_code_test.vb_methods WHERE class_id = ?`
  - `CMD 2001`: `SELECT pattern, fix_action, confidence FROM vb_shared.learned_rules WHERE pattern LIKE ? ORDER BY confidence DESC LIMIT ?`
  - `CMD 2002`: `SELECT problem, description FROM vb_shared.know_problems WHERE problem LIKE ?`
  - ... 200+ entries covering laws, vb_shared, vb_code_test tables

**query_engine.c**
- `query_execute(uint16_t cmd_id, const param_t *params, int param_count, response_t *result)`:
  1. Lookup cmd_id in registry
  2. Validate params against entry's param_types
  3. Check destruction guard if `is_destructive`
  4. Acquire connection from pool
  5. Prepare (or get from cache) statement
  6. Bind params
  7. Execute
  8. Fetch rows → build response (JSON serialized)
  9. Release connection
- `query_batch(uint16_t cmd_id, const param_t *batch, int batch_count, response_t *result)` — loop execute
- Internal: `build_json_response(MYSQL_RES *res, response_t *resp)` — serialize rows as JSON

**query_validate.c**
- `validate_params(const query_entry_t *entry, const param_t *params, int count)` — dispatch all checks
- `validate_string(const char *str, size_t max_len)` — UTF-8 validity, no null bytes, length
- `validate_int(int64_t value, int64_t min, int64_t max)` — range check
- Internal: `is_valid_utf8(const char *s, size_t len)`, `has_null_byte(const void *buf, size_t len)`, `check_fk(const char *table, const char *column, int64_t value)`

**cpsd_schema.c**
- `schema_load(const char *db_name)` — introspect `information_schema.columns`
- `schema_get_columns(const char *table)` — return column list + types
- `schema_get_fks(const char *table)` — return FK constraints
- `schema_check_fk(const char *table, const char *column, int64_t value)` — verify parent row exists

### Dependencies on Prior Phases
- Phase 3: uses `pool_acquire`/`pool_release`, `storage_driver_t` prepare/bind/execute/fetch
- Phase 1: uses `kern_event_publish` for EVT_QUERY_START / EVT_QUERY_END / EVT_QUERY_ERROR

### Verification Steps
1. Compile:
   ```bash
   cc -Wall -g [phase1-3 files] query_engine.c query_registry.c query_validate.c cpsd_schema.c \
      -o cpsd $(mysql_config --cflags --libs) -lsqlite3 -lpthread
   ```
2. Register queries: `query_registry_init()` → `query_registry_size()` returns 200+
3. Execute by cmd_id: send `CMD 2001` with params `["%print%", 5]` → returns learned_rules rows as JSON
4. Type validation: send string where int expected → error code returned
5. Range validation: send `LIMIT -1` → rejected
6. UTF-8 validation: send invalid UTF-8 byte sequence → rejected
7. Null-byte validation: send string with embedded `\0` → rejected
8. FK validation: insert with non-existent FK → rejected
9. Batch: send 10 inserts in one batch → all succeed or all fail
10. Unknown cmd_id: send `CMD 9999` → error "query not registered"

---

## Phase 5: Security (BND-04) — ~500 lines

**Goal:** Token-based authentication, RBAC permission matrix, rate limiting,
audit log. Six roles with distinct capabilities.

### Nodes Involved
- BND-04: Security (auth, RBAC, rate limit, audit)

### Files

| File           | Lines | Responsibility                                  |
|----------------|-------|-------------------------------------------------|
| `sec_auth.c`   | ~120  | Token validation, auth context creation         |
| `sec_perm.c`   | ~120  | Permission matrix: role × db_id × cmd_id × op   |
| `sec_role.c`   | ~100  | Role definitions, role-to-permission mapping    |
| `sec_audit.c`  | ~100  | Audit log writer (append-only file)             |
| `sec_rate.c`   | ~60   | Token bucket rate limiter per client             |

### Key Functions

**sec_auth.c**
- `sec_auth_init()` — load token file / config
- `sec_authenticate(int client_fd, const char *token, auth_context_t *ctx)` — validate token, populate ctx (role, pid, uid)
- `sec_auth_shutdown()` — clear token store
- Internal: `token_lookup(const char *token)` → returns role string

**sec_perm.c**
- `sec_perm_check(const auth_context_t *ctx, uint8_t db_id, uint16_t cmd_id, operation_t op)` — matrix lookup
- `sec_perm_denied_reason(int code)` — human-readable denial reason
- Internal: `PERMISSION_MATRIX[6][6][6]` — role × db_id × operation → allow/deny

**sec_role.c**
- Role definitions:
  - `admin` — all databases, all operations
  - `writer` — all databases, SELECT/INSERT/UPDATE (no DELETE/DROP)
  - `reader` — all databases, SELECT only
  - `ai_agent` — vb_shared + vb_code_test, SELECT + INSERT (learned_rules only)
  - `cli` — all databases, SELECT + limited INSERT
  - `internal` — all databases, all operations (for CPSD itself)
- `sec_role_get_permissions(const char *role, uint8_t db_id)` — return bitmask

**sec_audit.c**
- `sec_audit_log(const auth_context_t *ctx, const char *action, const char *detail)` — append to audit file with timestamp, client info
- Internal: `audit_file` — `/tmp/cpsd_logs/audit.log`, line-buffered, append-only

**sec_rate.c**
- `sec_rate_check(const auth_context_t *ctx, uint16_t cmd_id)` — token bucket: `CPSD_RATE_LIMIT_QPS` sustained, `CPSD_RATE_LIMIT_BURST` burst
- `sec_rate_reset(const auth_context_t *ctx)` — clear bucket on new auth

### Permission Matrix (role × operation)

| Role      | SELECT | INSERT | UPDATE | DELETE | BATCH | ADMIN |
|-----------|--------|--------|--------|--------|-------|-------|
| admin     | Y      | Y      | Y      | Y      | Y     | Y     |
| writer    | Y      | Y      | Y      | N      | Y     | N     |
| reader    | Y      | N      | N      | N      | N     | N     |
| ai_agent  | Y      | Y*     | N      | N      | N     | N     |
| cli       | Y      | Y*     | N      | N      | N     | N     |
| internal  | Y      | Y      | Y      | Y      | Y     | Y     |

`Y*` = restricted to specific tables (e.g., ai_agent can only INSERT into `learned_rules`)

### Dependencies on Prior Phases
- Phase 2: IPC layer passes token in first frame after connect
- Phase 4: query engine calls `sec_perm_check` before executing

### Verification Steps
1. Compile:
   ```bash
   cc -Wall -g [phase1-4 files] sec_auth.c sec_perm.c sec_role.c sec_audit.c sec_rate.c \
      -o cpsd $(mysql_config --cflags --libs) -lsqlite3 -lpthread
   ```
2. Auth: connect with valid token → `ctx.authenticated = true`, role populated
3. Auth fail: connect with invalid token → connection rejected
4. Permission: `reader` role sends `CMD_INSERT` → denied with reason
5. Permission: `ai_agent` sends INSERT to `learned_rules` → allowed; INSERT to `vb_classes` → denied
6. Rate limit: send 250 requests in 1 second (burst=200) → 201st rejected, 202+ rejected
7. Rate limit recovery: wait 2 seconds, send request → allowed
8. Audit: check `/tmp/cpsd_logs/audit.log` has entries for all auth + permission events

---

## Phase 6: Cache (BND-10) — ~300 lines

**Goal:** LRU cache for prepared statements, metadata, objects, query stats.
Reduces prepare overhead and metadata introspection cost.

### Nodes Involved
- BND-10: Cache (LRU, per-type, stats)

### Files

| File           | Lines | Responsibility                                  |
|----------------|-------|-------------------------------------------------|
| `cache.c`      | ~150  | Cache API, per-type hash tables                 |
| `cache_lru.c`  | ~150  | LRU eviction logic, doubly-linked list          |

### Key Functions

**cache.c**
- `cache_init()` — create 4 hash tables (STMT, OBJECT, META, STATS), each with `CPSD_CACHE_MAX_ENTRIES`
- `cache_get(cache_type_t type, const void *key, size_t key_len, void **value, size_t *value_len)` — lookup, move to MRU
- `cache_put(cache_type_t type, const void *key, size_t key_len, const void *value, size_t value_len)` — insert, evict LRU if over limit
- `cache_invalidate(cache_type_t type, const void *key, size_t key_len)` — remove one entry
- `cache_flush(cache_type_t type)` — clear all entries of type
- `cache_stats_get(cache_type_t type, int *entries, size_t *bytes, int *hits, int *misses)`
- `cache_shutdown()` — free all

**cache_lru.c**
- `lru_init(int max_entries, size_t max_bytes)` — create doubly-linked list + hash map
- `lru_get(lru_t *lru, const void *key, size_t key_len, void **value, size_t *value_len)`
- `lru_put(lru_t *lru, const void *key, size_t key_len, const void *value, size_t value_len)` — evict tail if needed
- `lru_remove(lru_t *lru, const void *key, size_t key_len)`
- Internal: `lru_node_t` with `prev`/`next`/`key`/`value`/`size`
- Internal: `evict_lru(lru_t *lru)` — remove tail, update byte count

### Dependencies on Prior Phases
- Phase 3: query engine uses `CACHE_TYPE_STMT` to cache prepared statements
- Phase 4: `CACHE_TYPE_META` for schema introspection results, `CACHE_TYPE_STATS` for query counts

### Verification Steps
1. Compile:
   ```bash
   cc -Wall -g [phase1-5 files] cache.c cache_lru.c \
      -o cpsd $(mysql_config --cflags --libs) -lsqlite3 -lpthread
   ```
2. Put/get: `cache_put(CACHE_TYPE_STMT, "key1", 4, "value1", 6)` then `cache_get` → returns value1
3. Hit/miss stats: 5 gets on existing key → hits=5, misses=0; 3 gets on missing key → misses=3
4. Eviction: insert `max_entries + 10` items → oldest 10 evicted, `entries == max_entries`
5. Byte limit: insert items totaling > `max_bytes` → LRU evicted until under limit
6. Invalidate: `cache_invalidate` on specific key → removed, subsequent get misses
7. Flush: `cache_flush(CACHE_TYPE_META)` → only META cleared, STMT intact
8. Integration: execute same cmd_id twice → second call has cache hit on prepared statement

---

## Phase 7: Log + Monitor + WAL (BND-13, 12, 14) — ~500 lines

**Goal:** Structured logging with channels, health monitoring with metrics,
write-ahead log for crash recovery.

### Nodes Involved
- BND-13: Structured Log (audit, error, perf, security, debug channels)
- BND-12: Health Monitor (per-module health, metrics collection)
- BND-14: WAL (write-ahead log, replay on startup)

### Files

| File       | Lines | Responsibility                                      |
|------------|-------|-----------------------------------------------------|
| `log.c`    | ~150  | Multi-channel structured logger                     |
| `health.c` | ~150  | Health checks, metrics collection, reporting        |
| `wal.c`    | ~120  | Write-ahead log: append, fsync, replay              |
| `backup.c` | ~80   | Backup/restore coordination                         |

### Key Functions

**log.c**
- `log_init(const char *dir)` — create log dir, open channel files
- `log_write(int level, const char *module, const char *msg)` — format: `[ISO8601] [LEVEL] [MODULE] msg`
- Internal channels:
  - `audit.log` — security events (auth, permission, rate limit)
  - `error.log` — errors and faults
  - `perf.log` — query timings, pool stats
  - `security.log` — denied attempts, suspicious patterns
  - `debug.log` — debug-level (gated by config)
- `log_shutdown()` — flush + close all files
- Internal: `log_format(char *buf, size_t size, int level, const char *module, const char *msg)`

**health.c**
- `health_init()` — register health check callbacks for each module
- `health_check_all()` — call all registered checks, aggregate status
- `health_check_module(module_id_t module)` — single module check
- Internal: `health_entry_t` with `module_id`, `check_fn`, `last_status`, `last_check_time`
- Metrics: `metrics_record(module_id_t module, const char *metric, int64_t value)` — in-memory counters
- `metrics_snapshot(response_t *resp)` — serialize all metrics to JSON

**wal.c**
- `wal_init(const char *path)` — open WAL file, read header
- `wal_write(const void *data, size_t len)` — append entry: `[timestamp][len][data]`, fsync
- `wal_replay()` — read entries sequentially, re-apply writes
- `wal_checkpoint()` — truncate WAL after successful checkpoint
- `wal_shutdown()` — close file
- Internal: `wal_entry_t` with `timestamp`, `txn_id`, `op_type`, `data_len`, `data`

**backup.c**
- `admin_backup(const char *path)` — coordinate: flush WAL, snapshot MySQL, copy WAL
- `admin_restore(const char *path)` — restore MySQL snapshot, replay WAL

### Dependencies on Prior Phases
- Phase 1: uses `kern_event_subscribe` to listen for health/error events
- Phase 4: query engine writes to WAL before executing destructive operations
- Phase 5: security audit log uses `log_write` with security channel

### Verification Steps
1. Compile:
   ```bash
   cc -Wall -g [phase1-6 files] log.c health.c wal.c backup.c \
      -o cpsd $(mysql_config --cflags --libs) -lsqlite3 -lpthread
   ```
2. Log: trigger an error → verify `error.log` has timestamped entry
3. Log channels: trigger auth event → verify `audit.log` AND `security.log` have entries
4. Health: call `health_check_all()` → all modules report OK
5. Health: break MySQL connection → `health_check_module(MODULE_STORAGE)` → reports FAIL
6. Metrics: execute 10 queries → `metrics_snapshot` shows query_count=10
7. WAL write: execute an INSERT → WAL file grows by one entry
8. WAL replay: kill CPSD mid-transaction (kill -9), restart → `wal_replay()` re-applies committed writes, skips uncommitted
9. WAL checkpoint: call `wal_checkpoint()` → WAL file truncated to empty
10. Backup: `admin_backup("/tmp/backup")` → backup directory has MySQL dump + WAL copy

---

## Phase 8: Plugin + Event (BND-15, 16) — ~300 lines

**Goal:** dlopen-based plugin loading, hook registration at 10 hook points,
plugins can intercept/modify requests.

### Nodes Involved
- BND-15: Plugin Loader (dlopen, dlsym, lifecycle)
- BND-16: Event Hooks (10 hook points, priority-ordered execution)

### Files

| File               | Lines | Responsibility                                  |
|---------------------|-------|-------------------------------------------------|
| `plugin.c`          | ~180  | dlopen loading, plugin registry, unload         |
| `plugin_hooks.c`    | ~120  | Hook firing, priority sort, chain execution     |

### Key Functions

**plugin.c**
- `plugin_init()` — initialize plugin list
- `plugin_load(const char *path)` — `dlopen`, call plugin's `cpsd_plugin_init()`, register hooks
- `plugin_unload(const char *name)` — call `cpsd_plugin_shutdown()`, `dlclose`
- `plugin_list()` — enumerate loaded plugins
- `plugin_shutdown()` — unload all
- Internal: `plugin_entry_t` with `name`, `handle`, `version`, `hooks[]`
- Plugin ABI: plugin must export `cpsd_plugin_init(void)`, `cpsd_plugin_shutdown(void)`, `cpsd_plugin_info_t`

**plugin_hooks.c**
- `plugin_register(hook_point_t hook, hook_handler_t handler, int priority)` — add to hook chain
- `plugin_unregister(hook_point_t hook, hook_handler_t handler)`
- `plugin_fire(hook_point_t hook, void *context)` — execute chain in priority order; any handler returning non-zero stops chain
- Hook points (from cpsd.h):
  - `HOOK_PRE_QUERY` / `HOOK_POST_QUERY` — intercept before/after query execution
  - `HOOK_PRE_AUTH` / `HOOK_POST_AUTH` — auth interception
  - `HOOK_PRE_WRITE` / `HOOK_POST_WRITE` — destructive operation guard
  - `HOOK_ON_CONNECT` / `HOOK_ON_DISCONNECT` — client lifecycle
  - `HOOK_ON_HEALTH` — health check extension
  - `HOOK_ON_CONFIG_RELOAD` — hot reload

### Dependencies on Prior Phases
- Phase 1: uses `kern_event_publish` for EVT_PLUGIN_LOAD / EVT_PLUGIN_UNLOAD
- Phase 4: query engine fires `HOOK_PRE_QUERY` before execution, `HOOK_POST_QUERY` after
- Phase 5: security fires `HOOK_PRE_AUTH` / `HOOK_POST_AUTH`

### Verification Steps
1. Compile:
   ```bash
   cc -Wall -g [phase1-7 files] plugin.c plugin_hooks.c \
      -o cpsd $(mysql_config --cflags --libs) -lsqlite3 -lpthread -ldl
   ```
2. Create test plugin (`test_plugin.c`):
   ```c
   int cpsd_plugin_init(void) { return 0; }
   void cpsd_plugin_shutdown(void) {}
   static int pre_query_hook(hook_point_t h, void *ctx) { /* log query */ return 0; }
   ```
3. Load: `plugin_load("./test_plugin.so")` → plugin appears in `plugin_list()`
4. Fire hook: execute a query → `HOOK_PRE_QUERY` fires, test plugin logs it
5. Priority: register two plugins at priority 10 and 20 → priority 10 fires first
6. Chain stop: plugin returns 1 from `HOOK_PRE_QUERY` → query not executed, post hook not fired
7. Unload: `plugin_unload("test_plugin")` → hook no longer fires on subsequent queries
8. Bad plugin: `plugin_load("./not_a_plugin.so")` → error returned, CPSD continues running

---

## Phase 9: Transactions (BND-08) — ~200 lines

**Goal:** ACID transactions with savepoints and isolation levels. Client can
begin, execute multiple queries, commit or rollback.

### Nodes Involved
- BND-08: Transactions (begin, savepoint, commit, rollback, isolation)

### Files

| File           | Lines | Responsibility                                  |
|----------------|-------|-------------------------------------------------|
| `query_txn.c`  | ~200  | Transaction lifecycle, savepoints, isolation    |

### Key Functions

**query_txn.c**
- `query_txn_begin(void)` — acquire dedicated connection from pool, `START TRANSACTION`
- `query_txn_execute(uint16_t cmd_id, const param_t *params, int count, response_t *result)` — execute within txn
- `query_txn_savepoint(const char *name)` — `SAVEPOINT name`
- `query_txn_rollback_to(const char *name)` — `ROLLBACK TO SAVEPOINT name`
- `query_txn_commit(void)` — `COMMIT`, release connection
- `query_txn_rollback(void)` — `ROLLBACK`, release connection
- `query_txn_set_isolation(int level)` — `SET TRANSACTION ISOLATION LEVEL ...`
- Internal: `txn_context_t` with `handle`, `savepoints[]`, `isolation_level`, `active`
- Isolation levels: READ_UNCOMMITTED, READ_COMMITTED, REPEATABLE_READ, SERIALIZABLE

### Dependencies on Prior Phases
- Phase 3: uses `pool_acquire` for dedicated transaction connection (held until commit/rollback)
- Phase 4: uses `query_registry_lookup` + `validate_params` for each execute
- Phase 7: WAL writes txn begin/commit/rollback markers

### Verification Steps
1. Compile:
   ```bash
   cc -Wall -g [phase1-8 files] query_txn.c \
      -o cpsd $(mysql_config --cflags --libs) -lsqlite3 -lpthread -ldl
   ```
2. Begin + commit: `query_txn_begin()` → execute INSERT → `query_txn_commit()` → row visible
3. Begin + rollback: `query_txn_begin()` → execute INSERT → `query_txn_rollback()` → row NOT visible
4. Savepoint: begin → insert → savepoint "sp1" → insert → rollback to "sp1" → commit → only first insert visible
5. Isolation: set SERIALIZABLE → concurrent transactions serialize correctly
6. Connection held: during active txn, pool has one fewer idle connection
7. Crash recovery: begin → execute → kill -9 → restart → WAL replay rolls back uncommitted txn

---

## Phase 10: Admin / CascadeCtl (BND-17) — ~400 lines

**Goal:** CLI control tool (`cpsd_ctl`), admin command handling in daemon,
launchd integration for macOS auto-start.

### Nodes Involved
- BND-17: Admin (status, start, stop, restart, reload, metrics, diagnostics)

### Files

| File                       | Lines | Responsibility                                      |
|---------------------------|-------|-----------------------------------------------------|
| `admin.c`                 | ~200  | Admin command handlers in daemon                    |
| `admin_ctl.c`             | ~180  | CLI tool: connects to CPSD, sends admin commands    |
| `com.wws.cpsd.plist`      | ~20   | launchd plist for auto-start on macOS               |

### Key Functions

**admin.c** (in daemon)
- `admin_status(response_t *resp)` — state, uptime, client count, pool stats, cache stats
- `admin_start(void)` — transition to READY (from STOPPED/FAULT)
- `admin_stop(void)` — transition to DRAINING → STOPPED, exit
- `admin_restart(void)` — reload config, re-init modules
- `admin_reload(void)` — hot config reload, fire `HOOK_ON_CONFIG_RELOAD`
- `admin_version(response_t *resp)` — return CPSD version + build info
- `admin_metrics(response_t *resp)` — serialize all metrics to JSON
- `admin_diagnostics(response_t *resp)` — health check all modules, pool ping, cache stats, WAL size
- `admin_backup(const char *path)` — delegate to backup.c
- `admin_restore(const char *path)` — delegate to backup.c

**admin_ctl.c** (standalone CLI)
- `main(int argc, char **argv)` — parse subcommand:
  - `cpsd_ctl status` — connect, send CMD_ADMIN, print status JSON
  - `cpsd_ctl start` — send start command (or launchd load)
  - `cpsd_ctl stop` — send stop command, graceful shutdown
  - `cpsd_ctl restart` — send restart command
  - `cpsd_ctl reload` — send reload command
  - `cpsd_ctl metrics` — print metrics JSON
  - `cpsd_ctl diagnostics` — print diagnostics
  - `cpsd_ctl backup <path>` — trigger backup
  - `cpsd_ctl version` — print version
- Internal: `ctl_connect()`, `ctl_send_admin(uint8_t subcmd, response_t *resp)`, `ctl_print_response(const response_t *resp)`

**com.wws.cpsd.plist**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>          <string>com.wws.cpsd</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/bcl_units/cpsd</string>
    <string>--config</string>
    <string>/tmp/cpsd.conf</string>
    <string>--daemon</string>
  </array>
  <key>RunAtLoad</key>      <true/>
  <key>KeepAlive</key>      <true/>
  <key>StandardOutPath</key>  <string>/tmp/cpsd_logs/cpsd.out</string>
  <key>StandardErrorPath</key> <string>/tmp/cpsd_logs/cpsd.err</string>
</dict>
</plist>
```

### Dependencies on Prior Phases
- Phase 2: admin_ctl uses IPC client to connect to daemon
- Phase 7: `admin_metrics` reads from health.c metrics, `admin_diagnostics` calls `health_check_all`
- Phase 1: `admin_stop` triggers state machine DRAINING → STOPPED

### Verification Steps
1. Compile daemon + CLI:
   ```bash
   cc -Wall -g [all phase1-9 files] admin.c \
      -o cpsd $(mysql_config --cflags --libs) -lsqlite3 -lpthread -ldl
   cc -Wall -g admin_ctl.c -o cpsd_ctl -lpthread
   ```
2. `./cpsd_ctl status` → JSON with state=READY, uptime, client_count, pool stats
3. `./cpsd_ctl metrics` → JSON with per-module metrics (query_count, cache_hits, cache_misses, etc.)
4. `./cpsd_ctl diagnostics` → all modules report OK, MySQL ping succeeds
5. `./cpsd_ctl reload` → config reloaded, `HOOK_ON_CONFIG_RELOAD` fires, no downtime
6. `./cpsd_ctl stop` → graceful shutdown: state DRAINING (wait for in-flight queries) → STOPPED → process exits
7. `./cpsd_ctl start` → if stopped, starts fresh
8. launchd: `launchctl load com.wws.cpsd.plist` → CPSD starts automatically
9. launchd: kill CPSD → launchd restarts it (KeepAlive=true)
10. `./cpsd_ctl version` → prints `CPSD 1.0.0` + build date

---

## Test Plan Summary

### Per-Phase Test Strategy

| Phase | Test Type          | Tool/Method                          | Pass Criteria                          |
|-------|--------------------|--------------------------------------|----------------------------------------|
| 1     | Unit               | Manual + assert macros               | State transitions valid, watchdog trips |
| 2     | Integration        | Custom test client (`ipc_client.c`)  | Ping/pong, framing correct              |
| 3     | Integration        | Direct MySQL queries                 | Prepare/bind/execute/fetch works        |
| 4     | Integration        | cmd_id requests via IPC              | 200+ queries execute, validation blocks |
| 5     | Security           | Role-based test vectors              | All 6 roles enforced, rate limit works  |
| 6     | Unit               | Cache stress test                    | Eviction correct, stats accurate        |
| 7     | Integration        | Crash test (kill -9) + WAL replay    | No data loss on committed writes        |
| 8     | Integration        | Load test plugin .so                 | Hooks fire, priority order correct      |
| 9     | Integration        | Transaction test vectors             | ACID properties hold, savepoints work   |
| 10    | End-to-end         | `cpsd_ctl` commands                  | All subcommands return correct data     |

### Test File Structure
```
tests/
├── test_phase1_kernel.c      — state machine, watchdog, resource limits
├── test_phase2_ipc.c         — socket connect, ping/pong, framing
├── test_phase3_storage.c     — MySQL connect, prepare, execute, fetch
├── test_phase4_query.c       — registry lookup, execute by cmd_id, validation
├── test_phase5_security.c    — auth, RBAC matrix, rate limit, audit
├── test_phase6_cache.c       — put/get, eviction, stats
├── test_phase7_wal.c         — write, crash, replay
├── test_phase8_plugin.c      — load, fire hook, unload
├── test_phase9_txn.c         — begin/commit/rollback/savepoint
├── test_phase10_admin.c      — cpsd_ctl subcommands
└── test_e2e_full.c           — full stack: connect → auth → query → result
```

### Test Execution
```bash
# Compile test harness
cc -Wall -g tests/test_phase1_kernel.c cpsd_state.c cpsd_event.c cpsd_loop.c \
   cpsd_msg.c cpsd_signal.c cpsd_resource.c cpsd_watchdog.c \
   -o tests/test_phase1 -lpthread

# Run all tests
for t in tests/test_phase*; do echo "=== $t ==="; $t; done
```

---

## Integration Milestones

### Milestone 1: End of Phase 3 — "Can talk to MySQL"
- CPSD accepts socket connections, queries MySQL via prepared statements
- No security, no registry, no cache — raw query passthrough
- **Demo:** connect with test client, send raw SQL, get rows back

### Milestone 2: End of Phase 5 — "Secured door"
- Full security stack: auth, RBAC, rate limit, audit
- Query registry with 200+ entries
- **Demo:** authenticate as `reader`, try DELETE → denied; as `admin` → allowed

### Milestone 3: End of Phase 7 — "Production-ready core"
- Cache, WAL, health monitoring, structured logging
- Crash recovery via WAL replay
- **Demo:** kill -9 mid-transaction, restart, verify committed data intact

### Milestone 4: End of Phase 10 — "Fully operational"
- Plugins, transactions, admin CLI, launchd
- Complete microkernel with all 19 BND nodes operational
- **Demo:** `cpsd_ctl status` shows healthy system, load plugin, run transaction, backup

---

## File Inventory (All Phases)

| #  | File                  | Phase | Lines | Status      |
|----|-----------------------|-------|-------|-------------|
| 1  | `cpsd.h`              | 1     | ~490  | DONE        |
| 2  | `cpsd_state.c`        | 1     | ~82   | DONE        |
| 3  | `cpsd_event.c`        | 1     | ~110  | DONE        |
| 4  | `cpsd_loop.c`         | 1     | ~160  | DONE        |
| 5  | `cpsd_msg.c`          | 1     | ~120  | DONE        |
| 6  | `cpsd_signal.c`       | 1     | ~120  | REMAINING   |
| 7  | `cpsd_resource.c`     | 1     | ~130  | REMAINING   |
| 8  | `cpsd_watchdog.c`     | 1     | ~150  | REMAINING   |
| 9  | `cpsd_main.c`         | 1     | ~200  | REMAINING   |
| 10 | `ipc_socket.c`        | 2     | ~200  | REMAINING   |
| 11 | `ipc_protocol.c`      | 2     | ~250  | REMAINING   |
| 12 | `ipc_client.c`        | 2     | ~150  | REMAINING   |
| 13 | `storage.c`           | 3     | ~150  | REMAINING   |
| 14 | `storage_mysql.c`     | 3     | ~350  | REMAINING   |
| 15 | `storage_pool.c`      | 3     | ~200  | REMAINING   |
| 16 | `query_engine.c`      | 4     | ~350  | REMAINING   |
| 17 | `query_registry.c`    | 4     | ~400  | REMAINING   |
| 18 | `query_validate.c`    | 4     | ~300  | REMAINING   |
| 19 | `cpsd_schema.c`       | 4     | ~150  | REMAINING   |
| 20 | `sec_auth.c`          | 5     | ~120  | REMAINING   |
| 21 | `sec_perm.c`          | 5     | ~120  | REMAINING   |
| 22 | `sec_role.c`          | 5     | ~100  | REMAINING   |
| 23 | `sec_audit.c`         | 5     | ~100  | REMAINING   |
| 24 | `sec_rate.c`          | 5     | ~60   | REMAINING   |
| 25 | `cache.c`             | 6     | ~150  | REMAINING   |
| 26 | `cache_lru.c`         | 6     | ~150  | REMAINING   |
| 27 | `log.c`               | 7     | ~150  | REMAINING   |
| 28 | `health.c`            | 7     | ~150  | REMAINING   |
| 29 | `wal.c`               | 7     | ~120  | REMAINING   |
| 30 | `backup.c`            | 7     | ~80   | REMAINING   |
| 31 | `plugin.c`            | 8     | ~180  | REMAINING   |
| 32 | `plugin_hooks.c`      | 8     | ~120  | REMAINING   |
| 33 | `query_txn.c`         | 9     | ~200  | REMAINING   |
| 34 | `admin.c`             | 10    | ~200  | REMAINING   |
| 35 | `admin_ctl.c`         | 10    | ~180  | REMAINING   |
| 36 | `com.wws.cpsd.plist`  | 10    | ~20   | REMAINING   |

**Total: ~5,000 lines of C** (36 files)

---

## Phase Dependency Graph

```
Phase 1 (Core Kernel)
  │
  ├──► Phase 2 (IPC Transport)
  │      │
  │      └──► Phase 10 (Admin/CascadeCtl)
  │
  ├──► Phase 3 (Storage + Pool)
  │      │
  │      └──► Phase 4 (Query Engine)
  │             │
  │             ├──► Phase 5 (Security)
  │             │      │
  │             │      └──► Phase 8 (Plugin + Event)
  │             │
  │             ├──► Phase 6 (Cache)
  │             │
  │             ├──► Phase 7 (Log + Monitor + WAL)
  │             │
  │             └──► Phase 9 (Transactions)
  │
  └──► Phase 7 (Log + Monitor + WAL) [uses event bus from Phase 1]
```

**Critical path:** Phase 1 → 3 → 4 → 7 (crash recovery requires WAL)
**Security path:** Phase 1 → 2 → 4 → 5 (must be in place before production)
**Can parallelize:** Phase 6 (Cache) and Phase 8 (Plugin) after Phase 4

---

## Destruction Guard (Cross-Layer, enforced in Phase 4)

The destruction guard is the safety net that prevents catastrophic data loss.
It is checked in `query_engine.c` before any destructive operation reaches MySQL.

### Guarded Patterns
- `DROP TABLE` / `DROP DATABASE` — blocked unless `confirm=true` AND role=admin
- `TRUNCATE TABLE` — blocked unless `confirm=true` AND role=admin
- `DELETE FROM table` (no WHERE) — blocked unless `confirm=true` AND role=admin
- `UPDATE table SET ...` (no WHERE) — blocked unless `confirm=true` AND role=admin
- `ALTER TABLE ... DROP COLUMN` — blocked unless `confirm=true` AND role=admin

### Key Functions (declared in cpsd.h, implemented in Phase 4)
- `destruction_guard_check(const char *sql, bool confirm)` — returns 0 if safe, -1 if blocked
- `destruction_guard_reason(void)` — returns human-readable reason for last block

### Verification
- Send `DROP TABLE vb_classes` without confirm → blocked, reason returned
- Send `DROP TABLE vb_classes` with confirm=true, role=admin → allowed
- Send `DROP TABLE vb_classes` with confirm=true, role=reader → blocked (permission)
- Send `DELETE FROM learned_rules` (no WHERE) → blocked
- Send `DELETE FROM learned_rules WHERE id = ?` → allowed (has WHERE)

---

*End of CPSD Build Plan — 10 phases, ~5,000 lines, 36 files, 19 BND nodes.*
