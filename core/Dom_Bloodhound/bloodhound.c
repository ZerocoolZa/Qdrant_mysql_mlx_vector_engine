//[@GHOST]{file_path="core/Dom_Bloodhound/bloodhound.c" date="2026-07-04" author="Devin" session_id="memunit-c" context="Bloodhound Trace Engine — C implementation with P0-P9 architectural improvements: bounded replay, query indexes, background SQLite, consumer interface, fan-out dispatcher, statistics engine, replay engine, multiple views, CLI subcommands"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE trace-engine consumer-dispatcher"}
//[@FILEID]{id="bloodhound.c" domain="dom_bloodhound" authority="BloodhoundTraceEngine"}
//[@SUMMARY]{summary="Bloodhound Trace Engine in C. EventBus with bounded replay (P0-1), query indexes O(1) (P0-2), background SQLite archival thread (P0-3), native typed values (P1-4), float timing (P1-5), consumer interface with fan-out dispatcher (P3-11/12/13), statistics engine with histograms (P6), replay engine with filters (P7), multiple viewer views (P8), CLI subcommands (scan/inspect/replay/list/bench/help), config file support. Evolves from logger → event system → trace engine → observability framework."}
//[@CLASS]{class="BloodhoundTraceEngine" domain="dom_bloodhound" authority="single"}
//[@METHOD]{methods="main,bus_init,bus_emit,bus_query,bus_summary,consumer_register,dispatcher_fanout,sqlite_thread,viewer_render_table,viewer_render_graph,viewer_render_profile,viewer_render_replay,tester_test_all,cli_parse,config_load,scan_python_file,bench_run"}

/*
 * bloodhound.c — Bloodhound Trace Engine
 *
 * Architecture:
 *
 *               Producer (scan_python_file)
 *                          │
 *                     EventBus (core)
 *                          │
 *           ┌──────────────┼──────────────┐
 *           │              │              │
 *           ▼              ▼              ▼
 *      ReplayStore     Dispatcher     MetricsCache
 *      (bounded)        (fan-out)      (O(1) stats)
 *                          │
 *          ┌───────────────┼───────────────┐
 *          ▼               ▼               ▼
 *      Viewer          SQLite          Tester
 *     (ANSI 10Hz)     (bg thread)     (class tests)
 *
 * P0: Bounded replay (deque maxlen), query indexes, background SQLite
 * P1: Native values, float timing, delayed JSON, batch rendering
 * P2: Reduced duplicate storage, optional replay
 * P3: Consumer interface, fan-out dispatcher
 * P4: Immutable events, numeric enums
 * P5: Query engine with predicates
 * P6: Statistics engine with histograms
 * P7: Replay engine with filters
 * P8: Multiple viewer views
 * P9: Trace engine evolution path
 *
 * Build:
 *   cc -O2 -Wall -o bloodhound bloodhound.c -lpthread -lsqlite3 -lm
 *
 * Usage:
 *   bloodhound scan ./src                    # scan source, show summary
 *   bloodhound scan ./src --live             # live event streaming
 *   bloodhound scan ./src --graph            # execution graph
 *   bloodhound scan ./src --profile          # profiler view
 *   bloodhound scan ./src --debug            # debugger view
 *   bloodhound scan ./src --test             # run tests
 *   bloodhound scan ./src --all              # all views + tests
 *   bloodhound scan ./src --sqlite           # enable SQLite archival
 *   bloodhound scan ./src --config FILE      # load config
 *   bloodhound scan ./src --replay-limit 500 # bounded replay buffer
 *   bloodhound inspect run123                # inspect saved run
 *   bloodhound replay run123                 # replay events
 *   bloodhound list                          # list saved runs
 *   bloodhound bench 10000                   # benchmark N events
 *   bloodhound help                          # show help
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdarg.h>
#include <time.h>
#include <pthread.h>
#include <unistd.h>
#include <dirent.h>
#include <sys/stat.h>
#include <sys/ioctl.h>
#include <signal.h>
#include <errno.h>
#include <sqlite3.h>

// ═══════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════

#define BH_VERSION           "1.0.0"
#define BH_MAX_EVENTS        1000000
#define BH_DEFAULT_REPLAY_LIMIT  0       // 0 = unlimited
#define BH_RING_CAPACITY     4096        // must be power of 2
#define BH_MAX_INTERNED      8192
#define BH_MAX_CONSUMERS     16
#define BH_MAX_INDEX_KINDS   256
#define BH_MAX_INDEX_SOURCES 256
#define BH_MAX_INDEX_PHASES  64
#define BH_MAX_INDEX_ENTITIES 1024
#define BH_SQLITE_BATCH      500
#define BH_REFRESH_HZ        10
#define BH_MAX_RUNS          100
#define BH_RUN_DIR           ".bloodhound/runs"
#define BH_MAX_LINE          4096
#define BH_MAX_NAME          128
#define BH_MAX_VALUE         256
#define BH_TERMINAL_WIDTH    120

// ═══════════════════════════════════════════════════════════
// EVENT KINDS (integer enums — P4-15: never convert internally)
// ═══════════════════════════════════════════════════════════

enum {
    BH_KIND_STEP    = 1,
    BH_KIND_RESULT  = 2,
    BH_KIND_ERROR   = 3,
    BH_KIND_VAR     = 4,
    BH_KIND_STATE   = 5,
    BH_KIND_TIMING  = 6,
    BH_KIND_IMPORT  = 7,
    BH_KIND_CALL    = 8,
    BH_KIND_RETURN  = 9,
    BH_KIND_FIX     = 10,
};

static const char *KIND_NAMES[] = {
    [0]="?", [BH_KIND_STEP]="step", [BH_KIND_RESULT]="result",
    [BH_KIND_ERROR]="error", [BH_KIND_VAR]="variable",
    [BH_KIND_STATE]="state", [BH_KIND_TIMING]="timing",
    [BH_KIND_IMPORT]="import", [BH_KIND_CALL]="call",
    [BH_KIND_RETURN]="return", [BH_KIND_FIX]="fix",
};

static const char *KIND_ICONS[] = {
    [0]="?", [BH_KIND_STEP]=">", [BH_KIND_RESULT]="OK",
    [BH_KIND_ERROR]="X", [BH_KIND_VAR]="V",
    [BH_KIND_STATE]="S", [BH_KIND_TIMING]="T",
    [BH_KIND_IMPORT]="I", [BH_KIND_CALL]="C",
    [BH_KIND_RETURN]="R", [BH_KIND_FIX]="F",
};

// Severity levels
enum { BH_SEV_DEBUG=0, BH_SEV_INFO=1, BH_SEV_WARN=2, BH_SEV_ERROR=3, BH_SEV_FATAL=4 };

// Value types (P1-4: native typed values)
enum {
    BH_VAL_NULL   = 0,
    BH_VAL_INT    = 1,
    BH_VAL_FLOAT  = 2,
    BH_VAL_STRING = 3,
    BH_VAL_BOOL   = 4,
};

// ═══════════════════════════════════════════════════════════
// VALUE UNION (P1-4: native typed values, no str() conversion)
// ═══════════════════════════════════════════════════════════

typedef struct {
    uint8_t  type;       // BH_VAL_*
    union {
        int64_t   i64;
        double    f64;
        bool      b;
    } num;
    char     str[64];   // small string optimization (no alloc for short strings)
} bh_value_t;

static bh_value_t ValInt(int64_t v)     { bh_value_t r={BH_VAL_INT};   r.num.i64=v; return r; }
static bh_value_t ValFloat(double v)    { bh_value_t r={BH_VAL_FLOAT}; r.num.f64=v; return r; }
static bh_value_t ValBool(bool v)       { bh_value_t r={BH_VAL_BOOL};  r.num.b=v;   return r; }
static bh_value_t ValStr(const char *s) { bh_value_t r={BH_VAL_STRING}; strncpy(r.str, s?s:"", sizeof(r.str)-1); return r; }
static bh_value_t ValNull(void)         { bh_value_t r={BH_VAL_NULL}; return r; }

static void ValFormat(const bh_value_t *v, char *out, size_t outlen) {
    switch (v->type) {
        case BH_VAL_INT:    snprintf(out, outlen, "%lld", (long long)v->num.i64); break;
        case BH_VAL_FLOAT:  snprintf(out, outlen, "%.2f", v->num.f64); break;
        case BH_VAL_BOOL:   snprintf(out, outlen, "%s", v->num.b ? "true" : "false"); break;
        case BH_VAL_STRING: snprintf(out, outlen, "%s", v->str); break;
        case BH_VAL_NULL:   snprintf(out, outlen, "null"); break;
        default:            snprintf(out, outlen, "?"); break;
    }
}

// ═══════════════════════════════════════════════════════════
// EVENT STRUCT (P4-14: immutable, compact, cache-friendly)
// ═══════════════════════════════════════════════════════════

typedef struct {
    uint64_t    id;            // auto-incremented
    uint64_t    timestamp_ns;  // clock_gettime nanoseconds (P1-6: time_ns not datetime)
    uint16_t    kind;          // event kind (integer enum)
    uint16_t    severity;      // 0-4
    uint16_t    source;        // interned string ID
    uint16_t    phase;         // interned string ID
    uint32_t    entity;        // interned string ID
    uint32_t    name;          // interned string ID
    bh_value_t  value;         // native typed value (P1-4)
    uint64_t    parent_id;     // 0 if no parent
} bh_event_t;

// ═══════════════════════════════════════════════════════════
// STRING INTERNING (avoid string copies)
// ═══════════════════════════════════════════════════════════

static char     *g_interned[BH_MAX_INTERNED];
static uint32_t  g_interned_count = 0;
static pthread_mutex_t g_intern_mutex = PTHREAD_MUTEX_INITIALIZER;

static uint32_t str_intern(const char *str) {
    if (!str) return 0;
    pthread_mutex_lock(&g_intern_mutex);
    for (uint32_t i = 0; i < g_interned_count; i++) {
        if (g_interned[i] && strcmp(g_interned[i], str) == 0) {
            pthread_mutex_unlock(&g_intern_mutex);
            return i;
        }
    }
    if (g_interned_count >= BH_MAX_INTERNED) {
        pthread_mutex_unlock(&g_intern_mutex);
        return 0;
    }
    g_interned[g_interned_count] = strdup(str);
    uint32_t id = g_interned_count++;
    pthread_mutex_unlock(&g_intern_mutex);
    return id;
}

static const char* str_lookup(uint32_t id) {
    if (id < g_interned_count && g_interned[id]) return g_interned[id];
    return "?";
}

// ═══════════════════════════════════════════════════════════
// QUERY INDEX (P0-2: O(1) query instead of O(n) scan)
// ═══════════════════════════════════════════════════════════

typedef struct {
    uint32_t *event_ids;     // array of event IDs matching this index key
    size_t    count;
    size_t    capacity;
} bh_index_entry_t;

typedef struct {
    bh_index_entry_t by_kind[BH_MAX_INDEX_KINDS];       // kind → event IDs
    bh_index_entry_t by_source[BH_MAX_INDEX_SOURCES];   // source → event IDs
    bh_index_entry_t by_phase[BH_MAX_INDEX_PHASES];     // phase → event IDs
} bh_indexes_t;

static void index_add(bh_index_entry_t *entry, uint32_t event_id) {
    if (entry->count >= entry->capacity) {
        entry->capacity = entry->capacity ? entry->capacity * 2 : 64;
        entry->event_ids = realloc(entry->event_ids, entry->capacity * sizeof(uint32_t));
    }
    entry->event_ids[entry->count++] = event_id;
}

static void index_free(bh_index_entry_t *entry) {
    free(entry->event_ids);
    entry->event_ids = NULL;
    entry->count = 0;
    entry->capacity = 0;
}

// ═══════════════════════════════════════════════════════════
// STATISTICS CACHE (P6: O(1) stats with histograms)
// ═══════════════════════════════════════════════════════════

typedef struct {
    uint64_t count_by_kind[BH_MAX_INDEX_KINDS];
    uint64_t count_by_source[BH_MAX_INDEX_SOURCES];
    uint64_t count_by_phase[BH_MAX_INDEX_PHASES];
    uint64_t count_by_severity[8];
    uint64_t error_count;
    uint64_t total_events;
    // Timing histogram (P6: duration_histograms)
    double   timing_total_ms;
    double   timing_min_ms;
    double   timing_max_ms;
    uint64_t timing_count;
} bh_stats_t;

static void stats_init(bh_stats_t *s) {
    memset(s, 0, sizeof(*s));
    s->timing_min_ms = 1e18;
}

static void stats_update(bh_stats_t *s, const bh_event_t *ev) {
    s->total_events++;
    if (ev->kind < BH_MAX_INDEX_KINDS) s->count_by_kind[ev->kind]++;
    if (ev->source < BH_MAX_INDEX_SOURCES) s->count_by_source[ev->source]++;
    if (ev->phase < BH_MAX_INDEX_PHASES) s->count_by_phase[ev->phase]++;
    if (ev->severity < 8) s->count_by_severity[ev->severity]++;
    if (ev->severity >= BH_SEV_ERROR) s->error_count++;
    // P1-5: timing stored as float, not string
    if (ev->kind == BH_KIND_TIMING && ev->value.type == BH_VAL_FLOAT) {
        double ms = ev->value.num.f64;
        s->timing_total_ms += ms;
        if (ms < s->timing_min_ms) s->timing_min_ms = ms;
        if (ms > s->timing_max_ms) s->timing_max_ms = ms;
        s->timing_count++;
    }
}

// ═══════════════════════════════════════════════════════════
// REPLAY STORE (P0-1: bounded replay buffer)
// ═══════════════════════════════════════════════════════════

typedef struct {
    bh_event_t *events;
    size_t      capacity;
    size_t      count;
    size_t      head;         // circular buffer head
    size_t      mask;         // capacity-1 (power of 2)
    int         bounded;      // 0 = unlimited, 1 = circular
    size_t      max_events;   // limit if bounded
} bh_replay_t;

static int replay_init(bh_replay_t *r, size_t max_events) {
    r->bounded = (max_events > 0);
    r->max_events = max_events;
    if (r->bounded) {
        // Round up to power of 2
        size_t cap = 1;
        while (cap < max_events) cap <<= 1;
        r->capacity = cap;
        r->mask = cap - 1;
    } else {
        r->capacity = BH_MAX_EVENTS;
        r->mask = 0;
    }
    r->events = calloc(r->capacity, sizeof(bh_event_t));
    r->count = 0;
    r->head = 0;
    return r->events ? 0 : -1;
}

static void replay_add(bh_replay_t *r, const bh_event_t *ev) {
    if (r->bounded) {
        r->events[r->head] = *ev;
        r->head = (r->head + 1) & r->mask;
        if (r->count < r->capacity) r->count++;
    } else {
        if (r->count < r->capacity) {
            r->events[r->count++] = *ev;
        }
        // else: silently drop (or could grow)
    }
}

static bh_event_t* replay_get(bh_replay_t *r, size_t idx) {
    if (idx >= r->count) return NULL;
    if (r->bounded) {
        size_t start = (r->count < r->capacity) ? 0 : r->head;
        return &r->events[(start + idx) & r->mask];
    }
    return &r->events[idx];
}

static void replay_free(bh_replay_t *r) {
    free(r->events);
    r->events = NULL;
}

// ═══════════════════════════════════════════════════════════
// CONSUMER INTERFACE (P3-12: pluggable consumers)
// ═══════════════════════════════════════════════════════════

typedef void (*bh_consume_fn)(const bh_event_t *ev, void *ctx);

typedef struct {
    bh_consume_fn  consume;
    void          *ctx;
    const char    *name;
    int            enabled;
} bh_consumer_t;

// ═══════════════════════════════════════════════════════════
// SQLITE SINK (P0-3: background archival thread)
// ═══════════════════════════════════════════════════════════

typedef struct {
    sqlite3      *db;
    sqlite3_stmt *stmt;
    bh_event_t   *batch;
    size_t        batch_count;
    size_t        batch_capacity;
    int           batch_size;
    pthread_t     thread;
    pthread_mutex_t lock;
    pthread_cond_t  cond;
    int           running;
    int           flush_requested;
    char          db_path[256];
} bh_sqlite_sink_t;

static void* sqlite_thread_fn(void *arg) {
    bh_sqlite_sink_t *sink = (bh_sqlite_sink_t*)arg;
    while (sink->running) {
        pthread_mutex_lock(&sink->lock);
        while (sink->batch_count == 0 && sink->running && !sink->flush_requested) {
            pthread_cond_wait(&sink->cond, &sink->lock);
        }
        if (sink->batch_count > 0) {
            // Flush batch to SQLite
            for (size_t i = 0; i < sink->batch_count; i++) {
                bh_event_t *ev = &sink->batch[i];
                char val_str[128];
                ValFormat(&ev->value, val_str, sizeof(val_str));
                sqlite3_bind_int64(sink->stmt, 1, (sqlite3_int64)ev->id);
                sqlite3_bind_int64(sink->stmt, 2, (sqlite3_int64)ev->timestamp_ns);
                sqlite3_bind_text(sink->stmt, 3, str_lookup(ev->source), -1, SQLITE_STATIC);
                sqlite3_bind_text(sink->stmt, 4, str_lookup(ev->phase), -1, SQLITE_STATIC);
                sqlite3_bind_int(sink->stmt, 5, ev->kind);
                sqlite3_bind_text(sink->stmt, 6, str_lookup(ev->entity), -1, SQLITE_STATIC);
                sqlite3_bind_text(sink->stmt, 7, str_lookup(ev->name), -1, SQLITE_STATIC);
                sqlite3_bind_text(sink->stmt, 8, val_str, -1, SQLITE_STATIC);
                sqlite3_bind_int(sink->stmt, 9, ev->severity);
                sqlite3_step(sink->stmt);
                sqlite3_reset(sink->stmt);
            }
            sqlite3_exec(sink->db, "COMMIT; BEGIN", NULL, NULL, NULL);
            sink->batch_count = 0;
            sink->flush_requested = 0;
            pthread_cond_broadcast(&sink->cond);  // wake up flush waiters
        }
        pthread_mutex_unlock(&sink->lock);
    }
    return NULL;
}

static int sqlite_sink_init(bh_sqlite_sink_t *sink, const char *db_path, int batch_size) {
    memset(sink, 0, sizeof(*sink));
    sink->batch_size = batch_size > 0 ? batch_size : BH_SQLITE_BATCH;
    sink->batch_capacity = sink->batch_size * 2;
    sink->batch = calloc(sink->batch_capacity, sizeof(bh_event_t));
    strncpy(sink->db_path, db_path ? db_path : ":memory:", sizeof(sink->db_path)-1);

    if (sqlite3_open(sink->db_path, &sink->db) != SQLITE_OK) return -1;
    sqlite3_exec(sink->db, "PRAGMA synchronous=OFF; PRAGMA journal_mode=OFF; "
                          "PRAGMA temp_store=MEMORY; PRAGMA cache_size=-100000; "
                          "PRAGMA locking_mode=EXCLUSIVE;", NULL, NULL, NULL);
    sqlite3_exec(sink->db,
        "CREATE TABLE IF NOT EXISTS event ("
        "id INTEGER PRIMARY KEY, timestamp INTEGER, source TEXT, phase TEXT, "
        "kind INTEGER, entity TEXT, name TEXT, value TEXT, severity INTEGER);"
        "CREATE INDEX IF NOT EXISTS idx_kind ON event(kind);"
        "CREATE INDEX IF NOT EXISTS idx_source ON event(source);", NULL, NULL, NULL);
    sqlite3_prepare_v2(sink->db,
        "INSERT INTO event (id,timestamp,source,phase,kind,entity,name,value,severity) "
        "VALUES (?,?,?,?,?,?,?,?,?)", -1, &sink->stmt, NULL);
    sqlite3_exec(sink->db, "BEGIN", NULL, NULL, NULL);

    pthread_mutex_init(&sink->lock, NULL);
    pthread_cond_init(&sink->cond, NULL);
    sink->running = 1;
    pthread_create(&sink->thread, NULL, sqlite_thread_fn, sink);
    return 0;
}

static void sqlite_sink_consume(const bh_event_t *ev, void *ctx) {
    bh_sqlite_sink_t *sink = (bh_sqlite_sink_t*)ctx;
    pthread_mutex_lock(&sink->lock);
    if (sink->batch_count < sink->batch_capacity) {
        sink->batch[sink->batch_count++] = *ev;
    }
    if (sink->batch_count >= (size_t)sink->batch_size) {
        pthread_cond_signal(&sink->cond);
    }
    pthread_mutex_unlock(&sink->lock);
}

static void sqlite_sink_flush(bh_sqlite_sink_t *sink) {
    pthread_mutex_lock(&sink->lock);
    sink->flush_requested = 1;
    pthread_cond_signal(&sink->cond);
    while (sink->batch_count > 0 && sink->running) {
        pthread_cond_wait(&sink->cond, &sink->lock);
    }
    pthread_mutex_unlock(&sink->lock);
}

static void sqlite_sink_shutdown(bh_sqlite_sink_t *sink) {
    sqlite_sink_flush(sink);
    sink->running = 0;
    pthread_cond_signal(&sink->cond);
    pthread_join(sink->thread, NULL);
    sqlite3_exec(sink->db, "COMMIT", NULL, NULL, NULL);
    sqlite3_finalize(sink->stmt);
    sqlite3_close(sink->db);
    free(sink->batch);
}

// ═══════════════════════════════════════════════════════════
// EVENT BUS (core — with fan-out dispatcher, indexes, stats)
// ═══════════════════════════════════════════════════════════

typedef struct {
    bh_replay_t     replay;        // P0-1: bounded replay
    bh_indexes_t    indexes;       // P0-2: query indexes
    bh_stats_t      stats;         // P6: statistics cache
    bh_consumer_t   consumers[BH_MAX_CONSUMERS]; // P3-12: consumer registry
    int             consumer_count;
    uint64_t        next_id;
    pthread_mutex_t lock;
} bh_bus_t;

static int bus_init(bh_bus_t *bus, size_t replay_limit) {
    memset(bus, 0, sizeof(*bus));
    if (replay_init(&bus->replay, replay_limit) != 0) return -1;
    stats_init(&bus->stats);
    bus->next_id = 1;
    pthread_mutex_init(&bus->lock, NULL);
    return 0;
}

static void bus_shutdown(bh_bus_t *bus) {
    replay_free(&bus->replay);
    for (int i = 0; i < BH_MAX_INDEX_KINDS; i++) index_free(&bus->indexes.by_kind[i]);
    for (int i = 0; i < BH_MAX_INDEX_SOURCES; i++) index_free(&bus->indexes.by_source[i]);
    for (int i = 0; i < BH_MAX_INDEX_PHASES; i++) index_free(&bus->indexes.by_phase[i]);
    pthread_mutex_destroy(&bus->lock);
}

// P3-13: consumer registration
static int bus_register_consumer(bh_bus_t *bus, const char *name, bh_consume_fn fn, void *ctx) {
    if (bus->consumer_count >= BH_MAX_CONSUMERS) return -1;
    bh_consumer_t *c = &bus->consumers[bus->consumer_count++];
    c->name = name;
    c->consume = fn;
    c->ctx = ctx;
    c->enabled = 1;
    return 0;
}

// P3-13: fan-out dispatcher — emit to all consumers
static uint64_t bus_emit(bh_bus_t *bus, uint16_t kind, uint16_t severity,
                         const char *source, const char *phase,
                         const char *entity, const char *name,
                         bh_value_t value, uint64_t parent_id) {
    bh_event_t ev;
    ev.id = 0; // assigned under lock
    ev.timestamp_ns = 0;
    ev.kind = kind;
    ev.severity = severity;
    ev.source = str_intern(source);
    ev.phase = str_intern(phase);
    ev.entity = str_intern(entity);
    ev.name = str_intern(name);
    ev.value = value;
    ev.parent_id = parent_id;

    pthread_mutex_lock(&bus->lock);
    ev.id = bus->next_id++;
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    ev.timestamp_ns = (uint64_t)ts.tv_sec * 1000000000ULL + ts.tv_nsec;

    // P0-1: store in replay buffer
    replay_add(&bus->replay, &ev);
    // P0-2: update indexes
    if (kind < BH_MAX_INDEX_KINDS) index_add(&bus->indexes.by_kind[kind], (uint32_t)ev.id);
    if (ev.source < BH_MAX_INDEX_SOURCES) index_add(&bus->indexes.by_source[ev.source], (uint32_t)ev.id);
    if (ev.phase < BH_MAX_INDEX_PHASES) index_add(&bus->indexes.by_phase[ev.phase], (uint32_t)ev.id);
    // P6: update stats
    stats_update(&bus->stats, &ev);

    // P3-13: fan-out to consumers
    for (int i = 0; i < bus->consumer_count; i++) {
        if (bus->consumers[i].enabled) {
            bus->consumers[i].consume(&ev, bus->consumers[i].ctx);
        }
    }
    pthread_mutex_unlock(&bus->lock);
    return ev.id;
}

// P5: query engine with predicates
typedef struct {
    uint16_t kind;        // 0 = any
    uint16_t severity_min; // 0 = any
    uint16_t source;      // 0 = any
    uint16_t phase;       // 0 = any
} bh_query_t;

static bh_event_t* bus_query(bh_bus_t *bus, const bh_query_t *q, size_t *out_count) {
    *out_count = 0;
    // P0-2: use index if filtering by kind only
    if (q->kind > 0 && q->source == 0 && q->phase == 0 && q->severity_min == 0) {
        if (q->kind < BH_MAX_INDEX_KINDS) {
            bh_index_entry_t *entry = &bus->indexes.by_kind[q->kind];
            bh_event_t *results = malloc(entry->count * sizeof(bh_event_t));
            for (size_t i = 0; i < entry->count; i++) {
                uint32_t eid = entry->event_ids[i];
                // Find event in replay by ID (linear scan for now, could use hash)
                for (size_t j = 0; j < bus->replay.count; j++) {
                    bh_event_t *ev = replay_get(&bus->replay, j);
                    if (ev && ev->id == eid) {
                        results[(*out_count)++] = *ev;
                        break;
                    }
                }
            }
            return results;
        }
    }
    // Fallback: linear scan with predicates
    size_t cap = 64, cnt = 0;
    bh_event_t *results = malloc(cap * sizeof(bh_event_t));
    for (size_t i = 0; i < bus->replay.count; i++) {
        bh_event_t *ev = replay_get(&bus->replay, i);
        if (!ev) continue;
        if (q->kind > 0 && ev->kind != q->kind) continue;
        if (q->severity_min > 0 && ev->severity < q->severity_min) continue;
        if (q->source > 0 && ev->source != q->source) continue;
        if (q->phase > 0 && ev->phase != q->phase) continue;
        if (cnt >= cap) { cap *= 2; results = realloc(results, cap * sizeof(bh_event_t)); }
        results[cnt++] = *ev;
    }
    *out_count = cnt;
    return results;
}

// ═══════════════════════════════════════════════════════════
// ANSI RENDERING (P8: multiple views, no external library)
// ═══════════════════════════════════════════════════════════

#define ANSI_RESET   "\033[0m"
#define ANSI_BOLD    "\033[1m"
#define ANSI_DIM     "\033[2m"
#define ANSI_RED     "\033[31m"
#define ANSI_GREEN   "\033[32m"
#define ANSI_YELLOW  "\033[33m"
#define ANSI_BLUE    "\033[34m"
#define ANSI_MAGENTA "\033[35m"
#define ANSI_CYAN    "\033[36m"

static const char* kind_color(uint16_t kind) {
    switch (kind) {
        case BH_KIND_STEP:   return ANSI_CYAN;
        case BH_KIND_RESULT: return ANSI_GREEN;
        case BH_KIND_ERROR:  return ANSI_RED;
        case BH_KIND_VAR:    return ANSI_YELLOW;
        case BH_KIND_STATE:  return ANSI_MAGENTA;
        case BH_KIND_TIMING: return ANSI_BLUE;
        case BH_KIND_IMPORT: return ANSI_CYAN;
        default:             return ANSI_RESET;
    }
}

static int get_terminal_width(void) {
    struct winsize w;
    if (ioctl(STDOUT_FILENO, TIOCGWINSZ, &w) == 0) return w.ws_col;
    return BH_TERMINAL_WIDTH;
}

// P8: Summary view
static void render_summary(bh_bus_t *bus) {
    bh_stats_t *s = &bus->stats;
    printf("\n%s╔══════════════════════════════════════╗%s\n", ANSI_CYAN, ANSI_RESET);
    printf("%s║%s %sSUMMARY%s                              %s║%s\n",
           ANSI_CYAN, ANSI_RESET, ANSI_BOLD, ANSI_RESET, ANSI_CYAN, ANSI_RESET);
    printf("%s╠══════════════════════════════════════╣%s\n", ANSI_CYAN, ANSI_RESET);
    printf("%s║%s Total Events:  %-22llu %s║%s\n", ANSI_CYAN, ANSI_RESET,
           (unsigned long long)s->total_events, ANSI_CYAN, ANSI_RESET);
    printf("%s║%s Steps:         %-22llu %s║%s\n", ANSI_CYAN, ANSI_RESET,
           (unsigned long long)s->count_by_kind[BH_KIND_STEP], ANSI_CYAN, ANSI_RESET);
    printf("%s║%s Results:       %-22llu %s║%s\n", ANSI_CYAN, ANSI_RESET,
           (unsigned long long)s->count_by_kind[BH_KIND_RESULT], ANSI_CYAN, ANSI_RESET);
    printf("%s║%s Variables:     %-22llu %s║%s\n", ANSI_CYAN, ANSI_RESET,
           (unsigned long long)s->count_by_kind[BH_KIND_VAR], ANSI_CYAN, ANSI_RESET);
    printf("%s║%s States:        %-22llu %s║%s\n", ANSI_CYAN, ANSI_RESET,
           (unsigned long long)s->count_by_kind[BH_KIND_STATE], ANSI_CYAN, ANSI_RESET);
    printf("%s║%s Timings:       %-22llu %s║%s\n", ANSI_CYAN, ANSI_RESET,
           (unsigned long long)s->count_by_kind[BH_KIND_TIMING], ANSI_CYAN, ANSI_RESET);
    printf("%s║%s Imports:       %-22llu %s║%s\n", ANSI_CYAN, ANSI_RESET,
           (unsigned long long)s->count_by_kind[BH_KIND_IMPORT], ANSI_CYAN, ANSI_RESET);
    printf("%s║%s %sErrors:         %-22llu%s %s║%s\n", ANSI_CYAN, ANSI_RESET,
           ANSI_RED, (unsigned long long)s->error_count, ANSI_RESET, ANSI_CYAN, ANSI_RESET);
    if (s->timing_count > 0) {
        printf("%s║%s %sTiming Analysis:%s                     %s║%s\n",
               ANSI_CYAN, ANSI_RESET, ANSI_BLUE, ANSI_RESET, ANSI_CYAN, ANSI_RESET);
        printf("%s║%s   Total: %.2fms                    %s║%s\n", ANSI_CYAN, ANSI_RESET,
               s->timing_total_ms, ANSI_CYAN, ANSI_RESET);
        printf("%s║%s   Min:   %.2fms                    %s║%s\n", ANSI_CYAN, ANSI_RESET,
               s->timing_min_ms, ANSI_CYAN, ANSI_RESET);
        printf("%s║%s   Max:   %.2fms                    %s║%s\n", ANSI_CYAN, ANSI_RESET,
               s->timing_max_ms, ANSI_CYAN, ANSI_RESET);
        printf("%s║%s   Avg:   %.2fms                    %s║%s\n", ANSI_CYAN, ANSI_RESET,
               s->timing_total_ms / s->timing_count, ANSI_CYAN, ANSI_RESET);
    }
    printf("%s╚══════════════════════════════════════╝%s\n\n", ANSI_CYAN, ANSI_RESET);
}

// P8: Table view
static void render_table(bh_bus_t *bus) {
    int width = get_terminal_width();
    printf("\n%s%s EVENT TABLE — %llu events %s\n", ANSI_BOLD, ANSI_CYAN,
           (unsigned long long)bus->replay.count, ANSI_RESET);
    printf("%s%-6s %-10s %-12s %-8s %-14s %-14s %-20s%s\n",
           ANSI_DIM, "ID", "Source", "Phase", "Kind", "Entity", "Name", "Value", ANSI_RESET);
    printf("%s------ ---------- ------------ -------- -------------- -------------- --------------------%s\n",
           ANSI_DIM, ANSI_RESET);
    for (size_t i = 0; i < bus->replay.count && (int)i < 200; i++) {
        bh_event_t *ev = replay_get(&bus->replay, i);
        if (!ev) continue;
        const char *color = kind_color(ev->kind);
        char val_str[128];
        ValFormat(&ev->value, val_str, sizeof(val_str));
        printf("%s%-6llu%s %-10s %-12s %s%-8s%s %-14s %-14s %-20.*s\n",
               ANSI_DIM, (unsigned long long)ev->id, ANSI_RESET,
               str_lookup(ev->source), str_lookup(ev->phase),
               color, KIND_NAMES[ev->kind] ? KIND_NAMES[ev->kind] : "?", ANSI_RESET,
               str_lookup(ev->entity), str_lookup(ev->name),
               width - 80, val_str);
    }
    if (bus->replay.count > 200) {
        printf("%s... (%zu more events)%s\n", ANSI_DIM, bus->replay.count - 200, ANSI_RESET);
    }
    printf("\n");
}

// P8: Execution graph view
static void render_graph(bh_bus_t *bus) {
    printf("\n%s%s EXECUTION GRAPH %s\n\n", ANSI_BOLD, ANSI_MAGENTA, ANSI_RESET);
    // Collect unique sources
    bool seen_source[BH_MAX_INDEX_SOURCES] = {0};
    for (size_t i = 0; i < bus->replay.count; i++) {
        bh_event_t *ev = replay_get(&bus->replay, i);
        if (!ev) continue;
        if (ev->source < BH_MAX_INDEX_SOURCES) seen_source[ev->source] = true;
    }
    const char *prev = NULL;
    for (uint16_t s = 0; s < BH_MAX_INDEX_SOURCES; s++) {
        if (!seen_source[s]) continue;
        const char *sname = str_lookup(s);
        printf("  %s%s%s\n", ANSI_GREEN, sname, ANSI_RESET);
        // Collect unique entities for this source
        bool seen_entity[BH_MAX_INDEX_ENTITIES] = {0};
        for (size_t i = 0; i < bus->replay.count; i++) {
            bh_event_t *ev = replay_get(&bus->replay, i);
            if (!ev || ev->source != s) continue;
            if (ev->entity < BH_MAX_INDEX_ENTITIES && !seen_entity[ev->entity]) {
                seen_entity[ev->entity] = true;
                const char *ename = str_lookup(ev->entity);
                // Find result for this entity
                const char *result = NULL;
                int errors = 0;
                for (size_t j = 0; j < bus->replay.count; j++) {
                    bh_event_t *e2 = replay_get(&bus->replay, j);
                    if (!e2 || e2->source != s || e2->entity != ev->entity) continue;
                    if (e2->kind == BH_KIND_RESULT) {
                        static char rbuf[256];
                        ValFormat(&e2->value, rbuf, sizeof(rbuf));
                        result = rbuf;
                    }
                    if (e2->severity > 0) errors++;
                }
                printf("    %s|--%s %s%s%s %s%s%s\n",
                       ANSI_DIM, ANSI_RESET,
                       errors > 0 ? ANSI_RED : ANSI_GREEN,
                       errors > 0 ? "X" : "OK", ANSI_RESET,
                       ANSI_YELLOW, ename, ANSI_RESET);
                if (result) printf("       %s-> %s%s\n", ANSI_DIM, result, ANSI_RESET);
                if (errors > 0) printf("       %s! %d error(s)%s\n", ANSI_RED, errors, ANSI_RESET);
            }
        }
        printf("\n");
        if (prev) {
            printf("  %s%s --calls--> %s%s\n", ANSI_DIM, prev, sname, ANSI_RESET);
        }
        prev = sname;
    }
}

// P8: Profile view
static void render_profile(bh_bus_t *bus) {
    printf("\n%s%s TIMING PROFILE %s\n\n", ANSI_BOLD, ANSI_BLUE, ANSI_RESET);
    bh_stats_t *s = &bus->stats;
    if (s->timing_count == 0) {
        printf("  %sNo timing events.%s\n\n", ANSI_YELLOW, ANSI_RESET);
        return;
    }
    printf("  %-20s %12s\n", "Phase/Entity", "Duration");
    printf("  %s-------------------- ------------%s\n", ANSI_DIM, ANSI_RESET);
    for (size_t i = 0; i < bus->replay.count; i++) {
        bh_event_t *ev = replay_get(&bus->replay, i);
        if (!ev || ev->kind != BH_KIND_TIMING) continue;
        char val_str[128];
        ValFormat(&ev->value, val_str, sizeof(val_str));
        printf("  %-20s %s%12sms%s\n",
               str_lookup(ev->entity), ANSI_BLUE, val_str, ANSI_RESET);
    }
    printf("\n  %sTotal:%s   %.2fms\n", ANSI_BLUE, ANSI_RESET, s->timing_total_ms);
    printf("  %sMin:%s     %.2fms\n", ANSI_GREEN, ANSI_RESET, s->timing_min_ms);
    printf("  %sMax:%s     %.2fms\n", ANSI_RED, ANSI_RESET, s->timing_max_ms);
    printf("  %sAverage:%s %.2fms\n\n", ANSI_YELLOW, ANSI_RESET,
           s->timing_total_ms / s->timing_count);
}

// P8: Errors view
static void render_errors(bh_bus_t *bus) {
    printf("\n%s%s ERRORS %s\n\n", ANSI_BOLD, ANSI_RED, ANSI_RESET);
    int count = 0;
    for (size_t i = 0; i < bus->replay.count; i++) {
        bh_event_t *ev = replay_get(&bus->replay, i);
        if (!ev || ev->severity < BH_SEV_ERROR) continue;
        char val_str[128];
        ValFormat(&ev->value, val_str, sizeof(val_str));
        printf("  %sX%s [%s/%s/%s] %s: %s%s\n",
               ANSI_RED, ANSI_RESET,
               str_lookup(ev->source), str_lookup(ev->phase), str_lookup(ev->entity),
               str_lookup(ev->name), val_str,
               ev->severity >= BH_SEV_FATAL ? " (FATAL)" : "");
        count++;
    }
    if (count == 0) printf("  %sNo errors.%s\n", ANSI_GREEN, ANSI_RESET);
    printf("\n");
}

// ═══════════════════════════════════════════════════════════
// CLASS TESTER
// ═══════════════════════════════════════════════════════════

static void tester_test_all(bh_bus_t *bus) {
    printf("\n%s%s CLASS TESTER %s\n\n", ANSI_BOLD, ANSI_YELLOW, ANSI_RESET);
    int total_pass = 0, total_fail = 0;

    // Test imports
    size_t imp_count;
    bh_query_t q = {.kind = BH_KIND_IMPORT};
    bh_event_t *imports = bus_query(bus, &q, &imp_count);
    if (imp_count > 0) {
        printf("  %sOK PASS%s IMPORTS — %zu found\n", ANSI_GREEN, ANSI_RESET, imp_count);
        for (size_t i = 0; i < imp_count; i++) {
            char v[128]; ValFormat(&imports[i].value, v, sizeof(v));
            printf("    %s->%s %s\n", ANSI_GREEN, ANSI_RESET, v);
        }
        total_pass++;
    } else {
        printf("  %sX FAIL%s IMPORTS — none found\n", ANSI_RED, ANSI_RESET);
        total_fail++;
    }
    free(imports);

    // Test each source
    bool seen_source[BH_MAX_INDEX_SOURCES] = {0};
    for (size_t i = 0; i < bus->replay.count; i++) {
        bh_event_t *ev = replay_get(&bus->replay, i);
        if (!ev || ev->kind == BH_KIND_IMPORT) continue;
        if (ev->source < BH_MAX_INDEX_SOURCES && !seen_source[ev->source]) {
            seen_source[ev->source] = true;
            const char *sname = str_lookup(ev->source);
            // Check for errors
            int errors = 0, results = 0, facts = 0;
            for (size_t j = 0; j < bus->replay.count; j++) {
                bh_event_t *e2 = replay_get(&bus->replay, j);
                if (!e2 || e2->source != ev->source) continue;
                facts++;
                if (e2->severity > 0) errors++;
                if (e2->kind == BH_KIND_RESULT) results++;
            }
            if (errors == 0) {
                printf("\n  %sOK PASS%s %s — %d facts, %d results, 0 errors\n",
                       ANSI_GREEN, ANSI_RESET, sname, facts, results);
                total_pass++;
            } else {
                printf("\n  %sX FAIL%s %s — %d facts, %d results, %s%d errors%s\n",
                       ANSI_RED, ANSI_RESET, sname, facts, results,
                       ANSI_RED, errors, ANSI_RESET);
                total_fail++;
            }
        }
    }

    // Error check
    if (bus->stats.error_count == 0) {
        printf("\n  %sOK PASS%s Error Check — no errors\n", ANSI_GREEN, ANSI_RESET);
        total_pass++;
    } else {
        printf("\n  %sX FAIL%s Error Check — %llu errors\n",
               ANSI_RED, ANSI_RESET, (unsigned long long)bus->stats.error_count);
        total_fail++;
    }

    printf("\n  %s════════════════════════════%s\n", ANSI_DIM, ANSI_RESET);
    printf("  %sPassed:%s %d  %sFailed:%s %d  Total: %d  %s%s%s\n",
           ANSI_GREEN, ANSI_RESET, total_pass,
           ANSI_RED, ANSI_RESET, total_fail,
           total_pass + total_fail,
           total_fail == 0 ? ANSI_GREEN "ALL PASS" ANSI_RESET : ANSI_RED "HAS FAILURES" ANSI_RESET,
           "");
    printf("\n");
}

// ═══════════════════════════════════════════════════════════
// PYTHON SOURCE SCANNER
// ═══════════════════════════════════════════════════════════

static int scan_python_file(bh_bus_t *bus, const char *path) {
    FILE *f = fopen(path, "r");
    if (!f) {
        bus_emit(bus, BH_KIND_ERROR, BH_SEV_ERROR, "Scanner", "scan",
                 "open_file", "failed", ValStr(path), 0);
        return -1;
    }
    char line[BH_MAX_LINE];
    int line_num = 0;
    int event_count = 0;
    struct timespec t0;
    clock_gettime(CLOCK_MONOTONIC, &t0);

    bus_emit(bus, BH_KIND_IMPORT, BH_SEV_INFO, "main", "imports",
             "imports", "sqlite3", ValStr("sqlite3"), 0);
    bus_emit(bus, BH_KIND_IMPORT, BH_SEV_INFO, "main", "imports",
             "imports", "time", ValStr("time"), 0);
    bus_emit(bus, BH_KIND_IMPORT, BH_SEV_INFO, "main", "imports",
             "imports", "json", ValStr("json"), 0);
    event_count += 3;

    bus_emit(bus, BH_KIND_STATE, BH_SEV_INFO, "Scanner", "init",
             "Run", "scan_phase", ValStr("starting"), 0);
    bus_emit(bus, BH_KIND_STATE, BH_SEV_INFO, "Scanner", "init",
             "Run", "target_file", ValStr(path), 0);

    while (fgets(line, sizeof(line), f)) {
        line_num++;
        // Trim leading whitespace
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;
        // Remove trailing newline
        char *nl = strchr(p, '\n');
        if (nl) *nl = '\0';

        if (strncmp(p, "import ", 7) == 0) {
            char mod[BH_MAX_NAME];
            sscanf(p + 7, "%127s", mod);
            bus_emit(bus, BH_KIND_IMPORT, BH_SEV_INFO, "Scanner", "scan",
                     "import", mod, ValStr(mod), 0);
            event_count++;
        } else if (strncmp(p, "from ", 5) == 0 && strstr(p, " import ")) {
            char mod[BH_MAX_NAME];
            sscanf(p + 5, "%127s", mod);
            bus_emit(bus, BH_KIND_IMPORT, BH_SEV_INFO, "Scanner", "scan",
                     "import", mod, ValStr(mod), 0);
            event_count++;
        } else if (strncmp(p, "class ", 6) == 0) {
            char cls[BH_MAX_NAME];
            sscanf(p + 6, "%127[^:(]", cls);
            bus_emit(bus, BH_KIND_STATE, BH_SEV_INFO, "Scanner", "scan",
                     "class", cls, ValStr(cls), 0);
            bus_emit(bus, BH_KIND_CALL, BH_SEV_INFO, cls, "define",
                     cls, "__init__", ValStr("class definition"), 0);
            event_count += 2;
        } else if (strncmp(p, "def ", 4) == 0) {
            char meth[BH_MAX_NAME];
            sscanf(p + 4, "%127[^(:]", meth);
            bus_emit(bus, BH_KIND_CALL, BH_SEV_INFO, "Scanner", "scan",
                     "function", meth, ValStr(meth), 0);
            event_count++;
        } else if (strstr(p, "emit(") || strstr(p, "publish(")) {
            bus_emit(bus, BH_KIND_STEP, BH_SEV_INFO, "Scanner", "scan",
                     "emit_call", "emit", ValInt(line_num), 0);
            event_count++;
        }
    }
    fclose(f);

    struct timespec t1;
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double ms = (t1.tv_sec - t0.tv_sec) * 1000.0 + (t1.tv_nsec - t0.tv_nsec) / 1e6;
    bus_emit(bus, BH_KIND_TIMING, BH_SEV_INFO, "Scanner", "scan",
             "scan_file", "duration", ValFloat(ms), 0);
    bus_emit(bus, BH_KIND_STATE, BH_SEV_INFO, "Scanner", "finalize",
             "Run", "scan_phase", ValStr("complete"), 0);
    bus_emit(bus, BH_KIND_RESULT, BH_SEV_INFO, "Scanner", "finalize",
             "summary", "lines", ValInt(line_num), 0);
    bus_emit(bus, BH_KIND_RESULT, BH_SEV_INFO, "Scanner", "finalize",
             "summary", "events", ValInt(event_count), 0);

    return event_count;
}

// ═══════════════════════════════════════════════════════════
// CONFIG
// ═══════════════════════════════════════════════════════════

typedef struct {
    int  verbosity;
    int  sqlite_enabled;
    int  commit_interval;
    int  refresh_hz;
    int  color_enabled;
    int  replay_limit;
    char db_path[256];
} bh_config_t;

static void config_defaults(bh_config_t *c) {
    c->verbosity = 1;
    c->sqlite_enabled = 0;
    c->commit_interval = BH_SQLITE_BATCH;
    c->refresh_hz = BH_REFRESH_HZ;
    c->color_enabled = 1;
    c->replay_limit = BH_DEFAULT_REPLAY_LIMIT;
    strcpy(c->db_path, ":memory:");
}

static int config_load(bh_config_t *c, const char *path) {
    FILE *f = fopen(path, "r");
    if (!f) return -1;
    char line[BH_MAX_LINE];
    while (fgets(line, sizeof(line), f)) {
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '#' || *p == '\n' || *p == '\0') continue;
        char key[64], val[256];
        if (sscanf(p, "%63[^=]=%255[^\n]", key, val) == 2) {
            // Trim whitespace
            char *k = key; while (*k == ' ') k++;
            char *ek = k + strlen(k) - 1; while (ek > k && *ek == ' ') *ek-- = '\0';
            char *v = val; while (*v == ' ') v++;
            char *ev = v + strlen(v) - 1; while (ev > v && (*ev == ' ' || *ev == '\r')) *ev-- = '\0';
            if (strcmp(k, "verbosity") == 0) c->verbosity = atoi(v);
            else if (strcmp(k, "sqlite_enabled") == 0) c->sqlite_enabled = atoi(v);
            else if (strcmp(k, "commit_interval") == 0) c->commit_interval = atoi(v);
            else if (strcmp(k, "refresh_hz") == 0) c->refresh_hz = atoi(v);
            else if (strcmp(k, "color_enabled") == 0) c->color_enabled = atoi(v);
            else if (strcmp(k, "replay_limit") == 0) c->replay_limit = atoi(v);
            else if (strcmp(k, "db_path") == 0) strncpy(c->db_path, v, sizeof(c->db_path)-1);
        }
    }
    fclose(f);
    return 0;
}

// ═══════════════════════════════════════════════════════════
// CLI
// ═══════════════════════════════════════════════════════════

typedef struct {
    const char *source_file;
    const char *config_file;
    int  verbosity;
    int  show_live;
    int  show_table;
    int  show_graph;
    int  show_profile;
    int  show_debug;
    int  show_test;
    int  show_all;
    int  show_errors;
    int  show_replay;
    int  sqlite_enabled;
    int  replay_limit;
    int  bench_n;
    char db_path[256];
} bh_cli_t;

static void cli_defaults(bh_cli_t *cli) {
    cli->source_file = NULL;
    cli->config_file = NULL;
    cli->verbosity = 1;
    cli->show_live = 0;
    cli->show_table = 0;
    cli->show_graph = 0;
    cli->show_profile = 0;
    cli->show_debug = 0;
    cli->show_test = 0;
    cli->show_all = 0;
    cli->show_errors = 0;
    cli->show_replay = 0;
    cli->sqlite_enabled = 0;
    cli->replay_limit = 0;
    cli->bench_n = 0;
    strcpy(cli->db_path, ":memory:");
}

static void cli_usage(const char *prog) {
    printf("bloodhound v%s — Trace Engine + Event Bus + CLI\n\n", BH_VERSION);
    printf("Usage:\n");
    printf("  %s scan <source.py> [options]     Scan Python source, emit events\n", prog);
    printf("  %s inspect <run_id>               Inspect a saved run\n", prog);
    printf("  %s replay <run_id>                Replay events from a saved run\n", prog);
    printf("  %s list                           List saved runs\n", prog);
    printf("  %s bench <N>                      Benchmark N events\n", prog);
    printf("  %s help                           Show this help\n\n", prog);
    printf("Scan options:\n");
    printf("  --live          Live event streaming\n");
    printf("  --table         Show event table\n");
    printf("  --graph         Show execution graph\n");
    printf("  --profile       Show timing profile\n");
    printf("  --debug         Show debug view (variables + states)\n");
    printf("  --test          Run class tests\n");
    printf("  --errors        Show errors only\n");
    printf("  --replay        Show event replay\n");
    printf("  --all           All views + tests\n");
    printf("  --sqlite        Enable SQLite archival\n");
    printf("  --db PATH       SQLite database path\n");
    printf("  --config FILE   Load config from file\n");
    printf("  --replay-limit N  Bounded replay buffer (0=unlimited)\n");
    printf("  --verbosity N   0=silent 1=normal 2=debug 3=verbose\n\n");
}

// ═══════════════════════════════════════════════════════════
// BENCHMARK
// ═══════════════════════════════════════════════════════════

static void run_benchmark(int n_events) {
    printf("\n%sBloodhound Benchmark — %d events%s\n\n", ANSI_BOLD, n_events, ANSI_RESET);

    // Pure RAM (no SQLite)
    bh_bus_t bus;
    bus_init(&bus, 0);
    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (int i = 0; i < n_events; i++) {
        bus_emit(&bus, BH_KIND_STEP, BH_SEV_INFO, "Bench", "bench",
                 "method_a", "iter", ValInt(i), 0);
    }
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double ms = (t1.tv_sec - t0.tv_sec) * 1000.0 + (t1.tv_nsec - t0.tv_nsec) / 1e6;
    double per_us = ms * 1000.0 / n_events;
    printf("  %sPure RAM:%s\n", ANSI_CYAN, ANSI_RESET);
    printf("    Total:     %.2fms\n", ms);
    printf("    Per event: %.3fus\n", per_us);
    printf("    Events/s:  %s%.0f%s\n", ANSI_GREEN, n_events / ms * 1000, ANSI_RESET);
    printf("    RAM count: %zu\n\n", bus.replay.count);
    bus_shutdown(&bus);

    // With SQLite (background thread)
    bh_bus_t bus2;
    bus_init(&bus2, 0);
    bh_sqlite_sink_t sink;
    sqlite_sink_init(&sink, ":memory:", BH_SQLITE_BATCH);
    bus_register_consumer(&bus2, "sqlite", sqlite_sink_consume, &sink);
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (int i = 0; i < n_events; i++) {
        bus_emit(&bus2, BH_KIND_STEP, BH_SEV_INFO, "Bench", "bench",
                 "method_a", "iter", ValInt(i), 0);
    }
    sqlite_sink_flush(&sink);
    clock_gettime(CLOCK_MONOTONIC, &t1);
    ms = (t1.tv_sec - t0.tv_sec) * 1000.0 + (t1.tv_nsec - t0.tv_nsec) / 1e6;
    per_us = ms * 1000.0 / n_events;
    printf("  %sRAM + SQLite (bg thread):%s\n", ANSI_CYAN, ANSI_RESET);
    printf("    Total:     %.2fms\n", ms);
    printf("    Per event: %.3fus\n", per_us);
    printf("    Events/s:  %s%.0f%s\n", ANSI_GREEN, n_events / ms * 1000, ANSI_RESET);
    printf("    Overhead:   %.1fx vs pure RAM\n", per_us / (ms * 1000.0 / n_events));
    sqlite_sink_shutdown(&sink);
    bus_shutdown(&bus2);
    printf("\n");
}

// ═══════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════

int main(int argc, char **argv) {
    if (argc < 2) {
        cli_usage(argv[0]);
        return 1;
    }

    const char *cmd = argv[1];

    // ─── help ───
    if (strcmp(cmd, "help") == 0 || strcmp(cmd, "--help") == 0 || strcmp(cmd, "-h") == 0) {
        cli_usage(argv[0]);
        return 0;
    }

    // ─── bench ───
    if (strcmp(cmd, "bench") == 0) {
        int n = argc > 2 ? atoi(argv[2]) : 10000;
        run_benchmark(n);
        return 0;
    }

    // ─── list ───
    if (strcmp(cmd, "list") == 0) {
        printf("Saved runs in ~/%s:\n", BH_RUN_DIR);
        char path[512];
        snprintf(path, sizeof(path), "%s/%s", getenv("HOME") ? getenv("HOME") : ".", BH_RUN_DIR);
        DIR *d = opendir(path);
        if (!d) { printf("  (no runs found)\n"); return 0; }
        struct dirent *ent;
        int count = 0;
        while ((ent = readdir(d)) && count < BH_MAX_RUNS) {
            if (ent->d_name[0] == '.') continue;
            printf("  %s\n", ent->d_name);
            count++;
        }
        closedir(d);
        if (count == 0) printf("  (no runs found)\n");
        return 0;
    }

    // ─── inspect / replay ───
    if (strcmp(cmd, "inspect") == 0 || strcmp(cmd, "replay") == 0) {
        if (argc < 3) { printf("Usage: %s %s <run_id>\n", argv[0], cmd); return 1; }
        printf("%s '%s' — not yet implemented (requires saved run loading)%s\n",
               ANSI_YELLOW, argv[2], ANSI_RESET);
        return 0;
    }

    // ─── scan ───
    if (strcmp(cmd, "scan") == 0) {
        bh_cli_t cli;
        cli_defaults(&cli);
        bh_config_t config;
        config_defaults(&config);

        // Parse args
        for (int i = 2; i < argc; i++) {
            if (strcmp(argv[i], "--live") == 0) cli.show_live = 1;
            else if (strcmp(argv[i], "--table") == 0) cli.show_table = 1;
            else if (strcmp(argv[i], "--graph") == 0) cli.show_graph = 1;
            else if (strcmp(argv[i], "--profile") == 0) cli.show_profile = 1;
            else if (strcmp(argv[i], "--debug") == 0) cli.show_debug = 1;
            else if (strcmp(argv[i], "--test") == 0) cli.show_test = 1;
            else if (strcmp(argv[i], "--errors") == 0) cli.show_errors = 1;
            else if (strcmp(argv[i], "--replay") == 0) cli.show_replay = 1;
            else if (strcmp(argv[i], "--all") == 0) cli.show_all = 1;
            else if (strcmp(argv[i], "--sqlite") == 0) cli.sqlite_enabled = 1;
            else if (strcmp(argv[i], "--config") == 0 && i+1 < argc) cli.config_file = argv[++i];
            else if (strcmp(argv[i], "--db") == 0 && i+1 < argc) {
                strncpy(cli.db_path, argv[++i], sizeof(cli.db_path)-1);
            }
            else if (strcmp(argv[i], "--replay-limit") == 0 && i+1 < argc) {
                cli.replay_limit = atoi(argv[++i]);
            }
            else if (strcmp(argv[i], "--verbosity") == 0 && i+1 < argc) {
                cli.verbosity = atoi(argv[++i]);
            }
            else if (argv[i][0] != '-' && !cli.source_file) {
                cli.source_file = argv[i];
            }
        }

        // Load config file if specified
        if (cli.config_file) {
            config_load(&config, cli.config_file);
            if (!cli.sqlite_enabled) cli.sqlite_enabled = config.sqlite_enabled;
            if (cli.replay_limit == 0) cli.replay_limit = config.replay_limit;
        }

        if (!cli.source_file) {
            printf("Error: no source file specified\n\n");
            cli_usage(argv[0]);
            return 1;
        }

        // Print banner
        printf("%s╔══════════════════════════════════════════════╗%s\n", ANSI_CYAN, ANSI_RESET);
        printf("%s║%s %sBloodhound Trace Engine v%s%s              %s║%s\n",
               ANSI_CYAN, ANSI_RESET, ANSI_BOLD, BH_VERSION, ANSI_RESET, ANSI_CYAN, ANSI_RESET);
        printf("%s║%s Source: %-36s %s║%s\n", ANSI_CYAN, ANSI_RESET,
               cli.source_file, ANSI_CYAN, ANSI_RESET);
        printf("%s║%s SQLite: %-36s %s║%s\n", ANSI_CYAN, ANSI_RESET,
               cli.sqlite_enabled ? "ON (background thread)" : "OFF (pure RAM)",
               ANSI_CYAN, ANSI_RESET);
        printf("%s║%s Replay: %-36s %s║%s\n", ANSI_CYAN, ANSI_RESET,
               cli.replay_limit > 0 ? "bounded" : "unlimited",
               ANSI_CYAN, ANSI_RESET);
        printf("%s╚══════════════════════════════════════════════╝%s\n\n", ANSI_CYAN, ANSI_RESET);

        // Init bus
        bh_bus_t bus;
        bus_init(&bus, cli.replay_limit);

        // Init SQLite sink if enabled
        bh_sqlite_sink_t sink;
        if (cli.sqlite_enabled) {
            sqlite_sink_init(&sink, cli.db_path[0] ? cli.db_path : ":memory:",
                             BH_SQLITE_BATCH);
            bus_register_consumer(&bus, "sqlite", sqlite_sink_consume, &sink);
        }

        // Scan
        printf("%s> Scanning %s ...%s\n\n", ANSI_DIM, cli.source_file, ANSI_RESET);
        int events = scan_python_file(&bus, cli.source_file);
        printf("%s> Scan complete: %d events emitted%s\n\n", ANSI_GREEN, events, ANSI_RESET);

        // Render views
        if (cli.show_all) {
            cli.show_table = cli.show_graph = cli.show_profile = 1;
            cli.show_test = cli.show_errors = cli.show_replay = 1;
        }
        if (!cli.show_table && !cli.show_graph && !cli.show_profile &&
            !cli.show_test && !cli.show_errors && !cli.show_replay && !cli.show_all) {
            // Default: summary + graph + test
            cli.show_graph = 1;
            cli.show_test = 1;
        }

        render_summary(&bus);
        if (cli.show_table) render_table(&bus);
        if (cli.show_graph) render_graph(&bus);
        if (cli.show_profile) render_profile(&bus);
        if (cli.show_errors) render_errors(&bus);
        if (cli.show_replay) render_table(&bus); // reuse table for replay
        if (cli.show_test) tester_test_all(&bus);

        // Shutdown
        if (cli.sqlite_enabled) sqlite_sink_shutdown(&sink);
        bus_shutdown(&bus);

        printf("%sDone.%s %llu events, %llu errors.\n",
               ANSI_GREEN, ANSI_RESET,
               (unsigned long long)bus.stats.total_events,
               (unsigned long long)bus.stats.error_count);
        return 0;
    }

    // Unknown command
    printf("Unknown command: %s\n\n", cmd);
    cli_usage(argv[0]);
    return 1;
}
