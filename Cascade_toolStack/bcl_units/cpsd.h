//[@GHOST]{file_path="Cascade_toolStack/bcl_units/cpsd.h" date="2026-07-04" author="Devin" session_id="cpsd-microkernel" context="CPSD master header — all layer interfaces for Cascade Persistent Data Service microkernel"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Run dispatch no-raw-SQL-concatenation layered-architecture"}
//[@FILEID]{id="cpsd.h" domain="cpsd_kernel" authority="CpsdMasterHeader"}
//[@SUMMARY]{summary="Master header for CPSD (Cascade Persistent Data Service). 9-layer microkernel: Core, IPC, Security, Storage, Query, Cache, Plugin, Admin, Client API. All interfaces declared here."}
//[@CLASS]{class="CpsdKernel" domain="cpsd_kernel" authority="single"}
//[@METHOD]{methods="kern_state,kern_event,kern_loop,kern_msg,kern_signal,kern_resource,kern_watchdog,ipc_socket,ipc_protocol,sec_auth,sec_perm,storage,query_engine,cache,plugin,admin"}

#ifndef CPSD_H
#define CPSD_H

#include <stdint.h>
#include <stddef.h>
#include <time.h>
#include <stdbool.h>
#include <sys/types.h>

// ═══════════════════════════════════════════
// CPSD CONFIG CONSTANTS
// ═══════════════════════════════════════════

#define CPSD_VERSION        "1.0.0"
#define CPSD_VERSION_NUM    0x010000

#define CPSD_SOCKET_PATH    "/tmp/cpsd.sock"
#define CPSD_PID_FILE       "/tmp/cpsd.pid"
#define CPSD_LOG_DIR        "/tmp/cpsd_logs"
#define CPSD_WAL_FILE       "/tmp/cpsd_logs/cpsd.wal"
#define CPSD_CONFIG_FILE    "/tmp/cpsd.conf"

#define CPSD_MAX_CLIENTS    64
#define CPSD_MAX_REQUEST    131072
#define CPSD_MAX_RESPONSE   1048576
#define CPSD_MAX_PARAMS     32
#define CPSD_MAX_PARAM_LEN  65536
#define CPSD_MAX_ROWS       10000
#define CPSD_MAX_COLS       64
#define CPSD_MAX_ERR        2048
#define CPSD_MAX_SQL        65536
#define CPSD_MAX_QUERY_REGISTRY 512

#define CPSD_POOL_SIZE      8
#define CPSD_POOL_IDLE_TIMEOUT 300
#define CPSD_CACHE_MAX_ENTRIES 4096
#define CPSD_CACHE_MAX_BYTES  (64 * 1024 * 1024)

#define CPSD_RATE_LIMIT_QPS 100
#define CPSD_RATE_LIMIT_BURST 200

#define CPSD_WATCHDOG_TIMEOUT 30
#define CPSD_HEALTH_INTERVAL  10

#define CPSD_MAGIC          "CDB1"
#define CPSD_MAGIC_LEN      4
#define CPSD_PROTOCOL_VERSION 0x01

// ═══════════════════════════════════════════
// MODULE IDs
// ═══════════════════════════════════════════

typedef enum {
    MODULE_KERNEL    = 0x00,
    MODULE_IPC       = 0x01,
    MODULE_SECURITY  = 0x02,
    MODULE_STORAGE   = 0x03,
    MODULE_QUERY     = 0x04,
    MODULE_CACHE     = 0x05,
    MODULE_PLUGIN    = 0x06,
    MODULE_ADMIN     = 0x07,
    MODULE_HEALTH    = 0x08,
    MODULE_LOG       = 0x09,
    MODULE_WAL       = 0x0A,
    MODULE_BACKUP    = 0x0B,
} module_id_t;

// ═══════════════════════════════════════════
// LAYER 0: KERNEL STATE MACHINE
// ═══════════════════════════════════════════

typedef enum {
    KERN_STATE_INIT     = 0,
    KERN_STATE_LOADING  = 1,
    KERN_STATE_READY    = 2,
    KERN_STATE_RELOAD   = 3,
    KERN_STATE_DRAINING = 4,
    KERN_STATE_STOPPED  = 5,
    KERN_STATE_FAULT    = 6,
} kern_state_t;

const char*  kern_state_name(kern_state_t s);
kern_state_t kern_state_get(void);
int          kern_state_transition(kern_state_t target);
int          kern_state_is_serving(void);

// ═══════════════════════════════════════════
// LAYER 0: EVENT BUS
// ═══════════════════════════════════════════

typedef enum {
    EVT_CLIENT_CONNECT    = 1,
    EVT_CLIENT_DISCONNECT = 2,
    EVT_QUERY_START       = 3,
    EVT_QUERY_END         = 4,
    EVT_QUERY_ERROR       = 5,
    EVT_AUTH_SUCCESS      = 6,
    EVT_AUTH_FAIL         = 7,
    EVT_STORAGE_CONNECT   = 8,
    EVT_STORAGE_DISCONNECT= 9,
    EVT_CACHE_HIT         = 10,
    EVT_CACHE_MISS        = 11,
    EVT_POOL_EXHAUSTED    = 12,
    EVT_HEALTH_OK         = 13,
    EVT_HEALTH_FAIL       = 14,
    EVT_CONFIG_RELOAD     = 15,
    EVT_PLUGIN_LOAD       = 16,
    EVT_PLUGIN_UNLOAD     = 17,
    EVT_BACKUP_START      = 18,
    EVT_BACKUP_END        = 19,
    EVT_WAL_WRITE         = 20,
    EVT_WAL_REPLAY        = 21,
    EVT_STATE_CHANGE      = 22,
    EVT_WATCHDOG_TRIP     = 23,
} event_type_t;

typedef struct {
    event_type_t type;
    uint64_t     timestamp;
    uint32_t     source_module;
    void        *payload;
    size_t       payload_len;
} event_t;

typedef void (*event_handler_t)(const event_t *evt);

int kern_event_init(void);
void kern_event_shutdown(void);
int kern_event_subscribe(event_type_t type, event_handler_t handler);
int kern_event_unsubscribe(event_type_t type, event_handler_t handler);
int kern_event_publish(event_t *evt);

// ═══════════════════════════════════════════
// LAYER 0: EVENT LOOP (kqueue on macOS)
// ═══════════════════════════════════════════

typedef void (*loop_callback_t)(int fd, void *userdata);

int  kern_loop_init(void);
void kern_loop_shutdown(void);
int  kern_loop_add(int fd, int32_t filter, loop_callback_t cb, void *userdata);
int  kern_loop_remove(int fd, int32_t filter);
int  kern_loop_run(void);   // blocks until shutdown
void kern_loop_stop(void);
int  kern_loop_add_timer(int ms, loop_callback_t cb, void *userdata);

// ═══════════════════════════════════════════
// LAYER 0: MESSAGE BUS
// ═══════════════════════════════════════════

typedef enum {
    MSG_REQUEST  = 0x01,
    MSG_RESPONSE = 0x02,
    MSG_ERROR    = 0x03,
    MSG_NOTIFY   = 0x04,
} msg_type_t;

typedef struct {
    uint32_t target_module;
    uint32_t source_module;
    uint16_t msg_type;
    uint16_t flags;
    uint32_t request_id;
    uint32_t payload_len;
    void    *payload;
} message_t;

int kern_msg_init(void);
void kern_msg_shutdown(void);
int kern_msg_send(message_t *msg);
int kern_msg_recv(message_t *msg, int timeout_ms);

// ═══════════════════════════════════════════
// LAYER 0: SIGNAL HANDLING
// ═══════════════════════════════════════════

typedef void (*signal_handler_t)(int signo);

int  kern_signal_init(void);
void kern_signal_shutdown(void);
int  kern_signal_register(int signo, signal_handler_t handler);
int  kern_signal_unregister(int signo);

// ═══════════════════════════════════════════
// LAYER 0: RESOURCE LIMITS
// ═══════════════════════════════════════════

typedef struct {
    int  max_clients;
    int  max_connections_per_backend;
    int  max_memory_mb;
    int  max_file_descriptors;
    int  max_query_time_ms;
    int  max_batch_size;
} resource_limits_t;

int  kern_resource_init(resource_limits_t *limits);
void kern_resource_shutdown(void);
int  kern_resource_check_clients(int current);
int  kern_resource_check_memory(size_t used_bytes);
int  kern_resource_check_fd(int current_fd_count);
const resource_limits_t* kern_resource_get(void);

// ═══════════════════════════════════════════
// LAYER 0: WATCHDOG
// ═══════════════════════════════════════════

typedef void (*watchdog_callback_t)(int module_id, const char *reason);

int  kern_watchdog_init(int timeout_sec, watchdog_callback_t callback);
void kern_watchdog_shutdown(void);
int  kern_watchdog_kick(int module_id);
int  kern_watchdog_check(void);
void kern_watchdog_tick(void);

// ═══════════════════════════════════════════
// LAYER 1: IPC TRANSPORT
// ═══════════════════════════════════════════

typedef enum {
    DB_MYSQL   = 0,
    DB_SQLITE  = 1,
    DB_QDRANT  = 2,
    DB_VECTOR  = 3,
    DB_GRAPH   = 4,
    DB_BLOB    = 5,
} db_id_t;

typedef enum {
    CMD_QUERY    = 1,
    CMD_TABLES   = 2,
    CMD_SCHEMA   = 3,
    CMD_PING     = 4,
    CMD_BATCH    = 5,
    CMD_BEGIN    = 6,
    CMD_COMMIT   = 7,
    CMD_ROLLBACK = 8,
    CMD_ADMIN    = 9,
} cmd_id_t;

typedef enum {
    PARAM_NULL   = 0,
    PARAM_INT32  = 1,
    PARAM_INT64  = 2,
    PARAM_STRING = 3,
    PARAM_DOUBLE = 4,
    PARAM_BLOB   = 5,
    PARAM_BOOL   = 6,
} param_type_t;

typedef struct {
    param_type_t type;
    uint32_t     len;
    void        *value;
} param_t;

typedef struct {
    uint8_t  version;
    uint8_t  msg_type;
    uint32_t request_id;
    uint16_t cmd_id;
    uint8_t  db_id;
    uint8_t  param_count;
    param_t  params[CPSD_MAX_PARAMS];
    char     sql[CPSD_MAX_SQL];  // for CMD_QUERY (must be in registry or ad-hoc)
} request_t;

typedef struct {
    uint8_t  status;     // 0=ok, 1=error
    uint16_t error_code;
    uint32_t row_count;
    uint32_t col_count;
    char     columns[CPSD_MAX_COLS][128];
    char    *rows;       // serialized JSON or binary
    size_t   rows_len;
    char     error_msg[CPSD_MAX_ERR];
} response_t;

int ipc_socket_init(const char *path, int backlog);
int ipc_socket_accept(int *client_fd, pid_t *client_pid);
int ipc_socket_close(void);
int ipc_socket_get_fd(void);

int ipc_frame_read(int fd, void *frame, size_t frame_size, size_t *frame_len);
int ipc_frame_write(int fd, const void *frame, size_t frame_len);
int ipc_parse_request(const void *frame, size_t len, request_t *req);
int ipc_build_response(void *frame, size_t frame_size, size_t *frame_len, const response_t *resp);

// ─── Per-client handler (Layer 1) ───
// Dispatch table — maps cmd_id to handler function.
typedef int (*cmd_handler_t)(const request_t *req, response_t *resp);

// Per-client handler — called when a new client connects.
// Reads request, dispatches, sends response, closes connection.
void ipc_client_handle(int client_fd, pid_t client_pid);

// Register a handler for a cmd_id (thread-safe).
// Returns 0 on success, -1 on invalid cmd_id (>= 256).
int  ipc_client_register_handler(uint16_t cmd_id, cmd_handler_t handler);

// Register the built-in command handlers (CMD_PING, CMD_TABLES,
// CMD_SCHEMA, CMD_QUERY, CMD_ADMIN). Called once at startup.
void ipc_client_register_builtins(void);

// ═══════════════════════════════════════════
// LAYER 2: SECURITY
// ═══════════════════════════════════════════

typedef enum {
    OP_SELECT = 1,
    OP_INSERT = 2,
    OP_UPDATE = 3,
    OP_DELETE = 4,
    OP_BATCH  = 5,
    OP_ADMIN  = 6,
} operation_t;

typedef struct {
    int  client_fd;
    pid_t client_pid;
    uid_t client_uid;
    char token[64];
    char role[32];
    bool authenticated;
} auth_context_t;

int  sec_auth_init(void);
void sec_auth_shutdown(void);
int  sec_authenticate(int client_fd, const char *token, auth_context_t *ctx);
int  sec_perm_check(const auth_context_t *ctx, uint8_t db_id, uint16_t cmd_id, operation_t op);
const char* sec_perm_denied_reason(int code);
int  sec_rate_check(const auth_context_t *ctx, uint16_t cmd_id);
void sec_rate_reset(const auth_context_t *ctx);
int  sec_audit_log(const auth_context_t *ctx, const char *action, const char *detail);

// ═══════════════════════════════════════════
// LAYER 3: STORAGE ENGINE
// ═══════════════════════════════════════════

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
    int (*connect)(void **handle, const char *conn_str);
    int (*disconnect)(void *handle);
    int (*prepare)(void *handle, const char *sql, void **stmt);
    int (*bind)(void *stmt, int idx, param_type_t type, const void *value, uint32_t len);
    int (*execute)(void *stmt);
    int (*fetch)(void *stmt, response_t *resp, int max_rows);
    int (*begin_txn)(void *handle);
    int (*commit_txn)(void *handle);
    int (*rollback_txn)(void *handle);
    int (*ping)(void *handle);
    int (*close_stmt)(void *stmt);
    const char *(*error)(void *handle);
} storage_driver_t;

int storage_register(storage_driver_t *driver);
int storage_connect(storage_backend_t backend, const char *conn_str, void **handle);
int storage_disconnect(storage_backend_t backend, void *handle);
storage_driver_t* storage_get_driver(storage_backend_t backend);

int pool_init(storage_backend_t backend, int pool_size, const char *conn_str);
void pool_shutdown(storage_backend_t backend);
int  pool_acquire(storage_backend_t backend, void **handle);
int  pool_release(storage_backend_t backend, void *handle);
int  pool_health_check(storage_backend_t backend);
int  pool_stats(storage_backend_t backend, int *total, int *in_use, int *idle);

// ═══════════════════════════════════════════
// LAYER 4: QUERY ENGINE
// ═══════════════════════════════════════════

typedef struct {
    uint16_t          cmd_id;
    const char       *name;
    const char       *sql;
    storage_backend_t backend;
    operation_t       operation;
    int               param_count;
    param_type_t      param_types[16];
    void             *prepared_stmt;
    bool              is_destructive;
} query_entry_t;

int  query_registry_init(void);
void query_registry_shutdown(void);
int  query_registry_register(const query_entry_t *entry);
const query_entry_t* query_registry_lookup(uint16_t cmd_id);
int  query_registry_size(void);

int  query_execute(uint16_t cmd_id, const param_t *params, int param_count, response_t *result);
int  query_batch(uint16_t cmd_id, const param_t *batch, int batch_count, response_t *result);
int  query_txn_begin(void);
int  query_txn_commit(void);
int  query_txn_rollback(void);

int  validate_params(const query_entry_t *entry, const param_t *params, int count);
int  validate_string(const char *str, size_t max_len);
int  validate_int(int64_t value, int64_t min, int64_t max);

// ═══════════════════════════════════════════
// LAYER 5: CACHE
// ═══════════════════════════════════════════

typedef enum {
    CACHE_TYPE_STMT  = 1,
    CACHE_TYPE_OBJECT = 2,
    CACHE_TYPE_META  = 3,
    CACHE_TYPE_STATS = 4,
} cache_type_t;

int  cache_init(void);
void cache_shutdown(void);
int  cache_get(cache_type_t type, const void *key, size_t key_len, void **value, size_t *value_len);
int  cache_put(cache_type_t type, const void *key, size_t key_len, const void *value, size_t value_len);
int  cache_invalidate(cache_type_t type, const void *key, size_t key_len);
int  cache_flush(cache_type_t type);
int  cache_stats_get(cache_type_t type, int *entries, size_t *bytes, int *hits, int *misses);

// ═══════════════════════════════════════════
// LAYER 6: PLUGIN / HOOKS
// ═══════════════════════════════════════════

typedef enum {
    HOOK_PRE_QUERY        = 1,
    HOOK_POST_QUERY       = 2,
    HOOK_PRE_AUTH         = 3,
    HOOK_POST_AUTH        = 4,
    HOOK_PRE_WRITE        = 5,
    HOOK_POST_WRITE       = 6,
    HOOK_ON_CONNECT       = 7,
    HOOK_ON_DISCONNECT    = 8,
    HOOK_ON_HEALTH        = 9,
    HOOK_ON_CONFIG_RELOAD = 10,
} hook_point_t;

typedef int (*hook_handler_t)(hook_point_t hook, void *context);

int  plugin_init(void);
void plugin_shutdown(void);
int  plugin_register(hook_point_t hook, hook_handler_t handler, int priority);
int  plugin_unregister(hook_point_t hook, hook_handler_t handler);
int  plugin_fire(hook_point_t hook, void *context);

// ═══════════════════════════════════════════
// LAYER 7: ADMIN
// ═══════════════════════════════════════════

int  admin_status(response_t *resp);
int  admin_start(void);
int  admin_stop(void);
int  admin_restart(void);
int  admin_reload(void);
int  admin_version(response_t *resp);
int  admin_metrics(response_t *resp);
int  admin_diagnostics(response_t *resp);
int  admin_backup(const char *path);
int  admin_restore(const char *path);

// ═══════════════════════════════════════════
// CROSS-LAYER: HEALTH, WAL, LOG
// ═══════════════════════════════════════════

int  health_init(void);
void health_shutdown(void);
int  health_check_all(void);
int  health_check_module(module_id_t module);

int  wal_init(const char *path);
void wal_shutdown(void);
int  wal_write(const void *data, size_t len);
int  wal_replay(void);

int  log_init(const char *dir);
void log_shutdown(void);
int  log_write(int level, const char *module, const char *msg);

#define LOG_DEBUG   0
#define LOG_INFO    1
#define LOG_WARN    2
#define LOG_ERROR   3
#define LOG_FATAL   4

// ═══════════════════════════════════════════
// DESTRUCTION GUARD (Cross-Layer)
// ═══════════════════════════════════════════

int destruction_guard_check(const char *sql, bool confirm);
const char* destruction_guard_reason(void);

#endif // CPSD_H
