/*
 * bloodhound_bus.h - Reusable Bloodhound Event Bus Library
 *[@GHOST]{file_path="core/Dom_Bloodhound/bloodhound_bus.h" date="2026-07-04" author="Devin" session_id="bloodhound-bus" context="Reusable event bus shared by all Bloodhound tools: scanner, BNQ/BND planner, profiler, debugger, future tools"}
 *[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE lock-free SPSC contiguous-array cache-friendly"}
 *[@FILEID]{id="bloodhound_bus.h" domain="dom_bloodhound" authority="BloodhoundBus"}
 *[@SUMMARY]{summary="Reusable event bus: 48-byte bh_event_t struct, string interning, SPSC ring buffer, RAM-first event store with optional SQLite archival, run management for inspect/replay."}
 *[@CLASS]{class="BloodhoundBus" domain="dom_bloodhound" authority="shared"}
 *[@METHOD]{methods="bh_intern,bh_lookup,bh_bus_init,bh_bus_shutdown,bh_bus_push,bh_bus_pop,bh_store_init,bh_store_shutdown,bh_store_emit,bh_store_flush,bh_store_query_kind,bh_store_query_severity,bh_store_query_entity,bh_store_count_kind,bh_store_count_severity,bh_store_total,bh_store_error_count,bh_run_save,bh_run_load,bh_run_list"}
 */

#ifndef BLOODHOUND_BUS_H
#define BLOODHOUND_BUS_H

#include <stdint.h>
#include <stddef.h>
#include <pthread.h>
#include <sqlite3.h>

/* ---- Constants ---- */

#define BH_MAX_EVENTS              100000
#define BH_MAX_INTERNED            4096
#define BH_DEFAULT_COMMIT_INTERVAL 500
#define BH_RUN_DIR                 "~/.bloodhound/runs"
#define BH_BUS_DEFAULT_CAPACITY    4096
#define BH_STORE_INITIAL_CAPACITY  1024
#define BH_SEVERITY_LEVELS         8
#define BH_KIND_COUNT              256
#define BH_RUN_ID_LEN              32
#define BH_RUN_SOURCE_LEN          256

/* ---- Event Kinds (shared constants) ---- */

#define BH_KIND_STEP    1
#define BH_KIND_RESULT  2
#define BH_KIND_ERROR   3
#define BH_KIND_STATE   4
#define BH_KIND_IMPORT  5
#define BH_KIND_CALL    6
#define BH_KIND_RETURN  7
#define BH_KIND_VAR     8
#define BH_KIND_TIMING  9
#define BH_KIND_SCAN    10
#define BH_KIND_PLAN    11
#define BH_KIND_PROFILE 12
#define BH_KIND_TEST    13

/* ---- Severity levels ---- */

#define BH_SEV_DEBUG 0
#define BH_SEV_INFO  1
#define BH_SEV_WARN  2
#define BH_SEV_ERROR 3
#define BH_SEV_FATAL 4

/* ---- Compact Event Structure (48 bytes, cache-friendly) ---- */

typedef struct {
    uint64_t timestamp;   /* nanoseconds since epoch */
    uint32_t id;          /* auto-incremented */
    uint16_t kind;        /* event kind (tool-specific) */
    uint16_t severity;    /* 0=debug, 1=info, 2=warn, 3=error, 4=fatal */
    uint16_t source;      /* source ID (interned string) */
    uint16_t phase;       /* phase ID */
    uint32_t entity;      /* entity ID (interned string) */
    uint32_t name;        /* name ID (interned string) */
    const char *value;    /* value string (or NULL) */
} bh_event_t;

/* ---- String Interning (shared across all tools) ---- */

uint32_t bh_intern(const char *str);
const char *bh_lookup(uint32_t id);

/* ---- Event Bus (contiguous array, lock-free SPSC) ---- */

typedef struct {
    bh_event_t *events;
    size_t capacity;
    size_t count;
    size_t mask;            /* capacity-1 (power of 2) */
    volatile size_t head;
    volatile size_t tail;
    pthread_mutex_t lock;   /* for multi-producer */
} bh_bus_t;

int  bh_bus_init(bh_bus_t *bus, size_t capacity);
void bh_bus_shutdown(bh_bus_t *bus);
int  bh_bus_push(bh_bus_t *bus, const bh_event_t *evt);
int  bh_bus_pop(bh_bus_t *bus, bh_event_t *out);

/* ---- Event Store (RAM-first, optional SQLite archival) ---- */

typedef struct {
    bh_event_t *events;       /* contiguous RAM array */
    size_t count;
    size_t capacity;
    uint32_t next_id;
    /* Cached counters (O(1) stats, no SQL) */
    uint64_t count_by_kind[BH_KIND_COUNT];
    uint64_t count_by_severity[BH_SEVERITY_LEVELS];
    uint64_t error_count;
    /* Optional SQLite */
    sqlite3 *db;
    int sqlite_enabled;
    int commit_interval;
    int pending_writes;
    pthread_mutex_t lock;
} bh_store_t;

int      bh_store_init(bh_store_t *store, int sqlite_enabled, int commit_interval);
void     bh_store_shutdown(bh_store_t *store);
uint32_t bh_store_emit(bh_store_t *store, uint16_t kind, uint16_t severity,
                       uint16_t source, uint16_t phase, uint32_t entity,
                       uint32_t name, const char *value);
int      bh_store_flush(bh_store_t *store);

/* Query (from RAM, not SQL) */
bh_event_t *bh_store_query_kind(bh_store_t *store, uint16_t kind, size_t *out_count);
bh_event_t *bh_store_query_severity(bh_store_t *store, uint16_t min_sev, size_t *out_count);
bh_event_t *bh_store_query_entity(bh_store_t *store, uint32_t entity, size_t *out_count);

/* Stats (O(1) from cached counters) */
uint64_t bh_store_count_kind(bh_store_t *store, uint16_t kind);
uint64_t bh_store_count_severity(bh_store_t *store, uint16_t severity);
uint64_t bh_store_total(bh_store_t *store);
uint64_t bh_store_error_count(bh_store_t *store);

/* ---- Run Management (for inspect/replay) ---- */

typedef struct {
    char run_id[BH_RUN_ID_LEN];       /* timestamp-based ID */
    char source_file[BH_RUN_SOURCE_LEN];
    time_t started_at;
    time_t ended_at;
    uint64_t event_count;
    uint64_t error_count;
} bh_run_t;

int bh_run_save(bh_store_t *store, const char *run_dir, const char *source_file);
int bh_run_load(bh_store_t *store, const char *run_dir, const char *run_id);
int bh_run_list(const char *run_dir, bh_run_t *runs, int max_runs, int *count);

#endif /* BLOODHOUND_BUS_H */
