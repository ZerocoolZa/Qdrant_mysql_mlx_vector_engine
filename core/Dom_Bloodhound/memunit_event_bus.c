/*
 * memunit_event_bus.c - Lock-free SPSC event bus, string interning, LiveState
 *[@GHOST]{file_path="core/Dom_Bloodhound/memunit_event_bus.c" date="2026-07-04" author="Devin" session_id="memunit-c" context="Lock-free event bus, string interning, LiveState RAM-first blackboard"}
 *[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE lock-free ring-buffer"}
 *[@FILEID]{id="memunit_event_bus.c" domain="dom_bloodhound" authority="MemunitEventBus"}
 *[@SUMMARY]{summary="Lock-free SPSC ring buffer event bus. String interning. LiveState with RAM-first storage, cached counters (O(1) stats), optional SQLite archival with batch commits."}
 *[@CLASS]{class="MemunitEventBus" domain="dom_bloodhound" authority="single"}
 *[@METHOD]{methods="str_intern,str_lookup,event_bus_init,event_bus_push,event_bus_pop,live_state_init,live_state_emit,live_state_flush,live_state_query_kind,live_state_query_severity_above,live_state_count_kind,live_state_total,live_state_shutdown"}
 */

#include "memunit_debugger.h"

#include <string.h>
#include <stdlib.h>
#include <time.h>
#include <pthread.h>
#include <stdio.h>
#include <sqlite3.h>

/* ====================================================================
 * 1. STRING INTERNING
 *    Static dynamic array of strdup'd strings, linear search, mutex guard.
 * ==================================================================== */

static char        **g_interned     = NULL;
static int           g_intern_count = 0;
static int           g_intern_cap   = 0;
static pthread_mutex_t g_intern_lock = PTHREAD_MUTEX_INITIALIZER;

int str_intern(const char *s)
{
    if (s == NULL) {
        return -1;
    }

    pthread_mutex_lock(&g_intern_lock);

    /* Lazy init */
    if (g_interned == NULL) {
        g_intern_cap = STR_INTERN_INITIAL;
        g_interned = (char **)calloc((size_t)g_intern_cap, sizeof(char *));
        if (g_interned == NULL) {
            pthread_mutex_unlock(&g_intern_lock);
            return -1;
        }
    }

    /* Linear search for existing entry */
    for (int i = 0; i < g_intern_count; i++) {
        if (strcmp(g_interned[i], s) == 0) {
            pthread_mutex_unlock(&g_intern_lock);
            return i;
        }
    }

    /* Grow if needed */
    if (g_intern_count >= g_intern_cap) {
        int new_cap = g_intern_cap * 2;
        char **tmp = (char **)realloc(g_interned,
                                      (size_t)new_cap * sizeof(char *));
        if (tmp == NULL) {
            pthread_mutex_unlock(&g_intern_lock);
            return -1;
        }
        g_interned = tmp;
        g_intern_cap = new_cap;
    }

    /* strdup and insert */
    char *dup = strdup(s);
    if (dup == NULL) {
        pthread_mutex_unlock(&g_intern_lock);
        return -1;
    }
    int id = g_intern_count;
    g_interned[g_intern_count] = dup;
    g_intern_count++;

    pthread_mutex_unlock(&g_intern_lock);
    return id;
}

const char *str_lookup(int id)
{
    if (id < 0 || id >= g_intern_count) {
        return NULL;
    }
    return g_interned[id];
}

void str_intern_shutdown(void)
{
    pthread_mutex_lock(&g_intern_lock);
    if (g_interned != NULL) {
        for (int i = 0; i < g_intern_count; i++) {
            free(g_interned[i]);
            g_interned[i] = NULL;
        }
        free(g_interned);
        g_interned = NULL;
    }
    g_intern_count = 0;
    g_intern_cap = 0;
    pthread_mutex_unlock(&g_intern_lock);
}

/* ====================================================================
 * 2. RING BUFFER EVENT BUS (SPSC)
 *    Lock-free with __atomic builtins; mutex fallback for safety.
 *    Capacity must be power of 2. head/tail advance via mask.
 * ==================================================================== */

static int is_power_of_two(uint32_t n)
{
    return n > 0 && (n & (n - 1)) == 0;
}

int event_bus_init(event_bus_t *bus, uint32_t capacity)
{
    if (bus == NULL) {
        return -1;
    }
    if (!is_power_of_two(capacity)) {
        return -1;
    }

    bus->events = (event_t *)calloc(capacity, sizeof(event_t));
    if (bus->events == NULL) {
        return -1;
    }
    bus->capacity = capacity;
    bus->mask = capacity - 1;
    bus->head = 0;
    bus->tail = 0;
    if (pthread_mutex_init(&bus->lock, NULL) != 0) {
        free(bus->events);
        bus->events = NULL;
        return -1;
    }
    return 0;
}

int event_bus_push(event_bus_t *bus, const event_t *ev)
{
    if (bus == NULL || ev == NULL) {
        return -1;
    }

    /*
     * SPSC lock-free: use __atomic load/store with acquire/release.
     * Mutex is available as fallback but not used on fast path.
     */
    uint32_t head = __atomic_load_n(&bus->head, __ATOMIC_RELAXED);
    uint32_t tail = __atomic_load_n(&bus->tail, __ATOMIC_ACQUIRE);
    uint32_t next_head = (head + 1) & bus->mask;

    if (next_head == tail) {
        /* Buffer full: drop oldest by advancing tail */
        uint32_t new_tail = (tail + 1) & bus->mask;
        __atomic_store_n(&bus->tail, new_tail, __ATOMIC_RELEASE);
    }

    bus->events[head] = *ev;
    __atomic_store_n(&bus->head, next_head, __ATOMIC_RELEASE);
    return 0;
}

int event_bus_pop(event_bus_t *bus, event_t *out)
{
    if (bus == NULL || out == NULL) {
        return -1;
    }

    uint32_t head = __atomic_load_n(&bus->head, __ATOMIC_ACQUIRE);
    uint32_t tail = __atomic_load_n(&bus->tail, __ATOMIC_RELAXED);

    if (head == tail) {
        /* Empty */
        return -1;
    }

    *out = bus->events[tail];
    uint32_t new_tail = (tail + 1) & bus->mask;
    __atomic_store_n(&bus->tail, new_tail, __ATOMIC_RELEASE);
    return 0;
}

void event_bus_shutdown(event_bus_t *bus)
{
    if (bus == NULL) {
        return;
    }
    if (bus->events != NULL) {
        free(bus->events);
        bus->events = NULL;
    }
    pthread_mutex_destroy(&bus->lock);
    bus->capacity = 0;
    bus->mask = 0;
    bus->head = 0;
    bus->tail = 0;
}

/* ====================================================================
 * 3. LIVESTATE
 *    RAM-first storage with cached O(1) counters.
 *    Optional SQLite :memory: archival with batch commits.
 * ==================================================================== */

static double now_ns(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec * 1e9 + (double)ts.tv_nsec;
}

static int live_state_grow(live_state_t *ls)
{
    uint32_t new_cap = ls->event_capacity * 2;
    if (new_cap > MAX_EVENTS) {
        new_cap = MAX_EVENTS;
    }
    if (new_cap == ls->event_capacity) {
        return -1;  /* at hard cap */
    }
    event_t *tmp = (event_t *)realloc(ls->events,
                                      (size_t)new_cap * sizeof(event_t));
    if (tmp == NULL) {
        return -1;
    }
    ls->events = tmp;
    ls->event_capacity = new_cap;
    return 0;
}

static int live_state_sqlite_open(live_state_t *ls)
{
    int rc = sqlite3_open(":memory:", &ls->db);
    if (rc != SQLITE_OK) {
        return -1;
    }

    /* PRAGMAs for max in-memory speed */
    sqlite3_exec(ls->db, "PRAGMA synchronous=OFF;", NULL, NULL, NULL);
    sqlite3_exec(ls->db, "PRAGMA journal_mode=OFF;", NULL, NULL, NULL);
    sqlite3_exec(ls->db, "PRAGMA temp_store=MEMORY;", NULL, NULL, NULL);
    sqlite3_exec(ls->db, "PRAGMA cache_size=-100000;", NULL, NULL, NULL);
    sqlite3_exec(ls->db, "PRAGMA locking_mode=EXCLUSIVE;", NULL, NULL, NULL);

    /* Event table — INTEGER types for kind/phase/severity */
    const char *schema =
        "CREATE TABLE event ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  timestamp REAL,"
        "  source TEXT,"
        "  phase INTEGER,"
        "  kind INTEGER,"
        "  entity TEXT,"
        "  name TEXT,"
        "  value TEXT,"
        "  severity INTEGER DEFAULT 0,"
        "  parentId INTEGER"
        ");"
        "CREATE INDEX idx_event_kind ON event(kind);"
        "CREATE INDEX idx_event_phase ON event(phase);"
        "CREATE INDEX idx_event_severity ON event(severity);"
        "CREATE INDEX idx_event_source ON event(source);";
    rc = sqlite3_exec(ls->db, schema, NULL, NULL, NULL);
    if (rc != SQLITE_OK) {
        sqlite3_close(ls->db);
        ls->db = NULL;
        return -1;
    }

    /* Precompile INSERT */
    const char *sql =
        "INSERT INTO event "
        "(timestamp, source, phase, kind, entity, name, value, severity, parentId) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)";
    rc = sqlite3_prepare_v2(ls->db, sql, -1, &ls->stmt_insert, NULL);
    if (rc != SQLITE_OK) {
        sqlite3_close(ls->db);
        ls->db = NULL;
        return -1;
    }

    /* Begin transaction for batch commits */
    sqlite3_exec(ls->db, "BEGIN;", NULL, NULL, NULL);

    ls->commit_interval = COMMIT_INTERVAL;
    ls->pending_writes = 0;
    return 0;
}

int live_state_init(live_state_t *ls, int enable_sqlite)
{
    if (ls == NULL) {
        return -1;
    }
    memset(ls, 0, sizeof(live_state_t));

    ls->event_capacity = MAX_EVENTS_INITIAL;
    ls->events = (event_t *)calloc(ls->event_capacity, sizeof(event_t));
    if (ls->events == NULL) {
        return -1;
    }
    ls->event_count = 0;
    ls->next_id = 1;
    ls->total_events = 0;
    ls->error_count = 0;

    if (pthread_mutex_init(&ls->lock, NULL) != 0) {
        free(ls->events);
        ls->events = NULL;
        return -1;
    }

    ls->sqlite_enabled = 0;
    ls->db = NULL;
    ls->stmt_insert = NULL;
    ls->pending_writes = 0;
    ls->commit_interval = COMMIT_INTERVAL;

    if (enable_sqlite) {
        if (live_state_sqlite_open(ls) == 0) {
            ls->sqlite_enabled = 1;
        } else {
            /* Continue without SQLite if open failed */
            ls->sqlite_enabled = 0;
        }
    }

    return 0;
}

static void live_state_sqlite_write(live_state_t *ls, const event_t *ev)
{
    if (!ls->sqlite_enabled || ls->stmt_insert == NULL) {
        return;
    }

    const char *src = str_lookup(ev->source);
    const char *ent = str_lookup(ev->entity);
    if (src == NULL) src = "";
    if (ent == NULL) ent = "";

    sqlite3_bind_double(ls->stmt_insert, 1, ev->timestamp_ns);
    sqlite3_bind_text(ls->stmt_insert, 2, src, -1, SQLITE_STATIC);
    sqlite3_bind_int(ls->stmt_insert, 3, ev->phase);
    sqlite3_bind_int(ls->stmt_insert, 4, ev->kind);
    sqlite3_bind_text(ls->stmt_insert, 5, ent, -1, SQLITE_STATIC);
    sqlite3_bind_text(ls->stmt_insert, 6, ev->name, -1, SQLITE_STATIC);
    sqlite3_bind_text(ls->stmt_insert, 7, ev->value, -1, SQLITE_STATIC);
    sqlite3_bind_int(ls->stmt_insert, 8, ev->severity);
    if (ev->parent_id > 0) {
        sqlite3_bind_int64(ls->stmt_insert, 9, (sqlite3_int64)ev->parent_id);
    } else {
        sqlite3_bind_null(ls->stmt_insert, 9);
    }

    sqlite3_step(ls->stmt_insert);
    sqlite3_reset(ls->stmt_insert);
    ls->pending_writes++;

    if (ls->pending_writes >= ls->commit_interval) {
        live_state_flush(ls);
    }
}

uint64_t live_state_emit(live_state_t *ls,
                         const char *source,
                         int phase,
                         int kind,
                         const char *entity,
                         const char *name,
                         const char *value,
                         int severity,
                         uint64_t parent_id)
{
    if (ls == NULL) {
        return 0;
    }

    pthread_mutex_lock(&ls->lock);

    /* Grow RAM array if needed */
    if (ls->event_count >= ls->event_capacity) {
        if (live_state_grow(ls) != 0) {
            pthread_mutex_unlock(&ls->lock);
            return 0;  /* at capacity */
        }
    }

    uint64_t eid = ls->next_id++;
    double ts = now_ns();

    int src_id = str_intern(source ? source : "");
    int ent_id = str_intern(entity ? entity : "");

    event_t *ev = &ls->events[ls->event_count];
    ev->id = eid;
    ev->timestamp_ns = ts;
    ev->source = src_id;
    ev->phase = phase;
    ev->kind = kind;
    ev->entity = ent_id;
    ev->severity = severity;
    ev->parent_id = parent_id;

    /* Copy name/value safely */
    if (name != NULL) {
        strncpy(ev->name, name, STR_MAX_LEN - 1);
        ev->name[STR_MAX_LEN - 1] = '\0';
    } else {
        ev->name[0] = '\0';
    }
    if (value != NULL) {
        strncpy(ev->value, value, STR_MAX_LEN - 1);
        ev->value[STR_MAX_LEN - 1] = '\0';
    } else {
        ev->value[0] = '\0';
    }

    ls->event_count++;
    ls->total_events++;

    /* Cached counters (O(1) stats) */
    if (kind >= 0 && kind < KIND_COUNT) {
        ls->count_by_kind[kind]++;
    }
    if (phase >= 0 && phase < PHASE_COUNT) {
        ls->count_by_phase[phase]++;
    }
    if (severity >= 0 && severity < SEVERITY_LEVELS) {
        ls->count_by_severity[severity]++;
    }

    /* Error tracking */
    if (kind == EVENT_ERROR || severity >= SEV_ERROR) {
        ls->error_count++;
    }

    /* SQLite archival (batched) */
    if (ls->sqlite_enabled) {
        live_state_sqlite_write(ls, ev);
    }

    pthread_mutex_unlock(&ls->lock);
    return eid;
}

int live_state_flush(live_state_t *ls)
{
    if (ls == NULL || !ls->sqlite_enabled) {
        return 0;
    }
    if (ls->pending_writes == 0) {
        return 0;
    }

    /* Commit current batch, start new transaction */
    sqlite3_exec(ls->db, "COMMIT;", NULL, NULL, NULL);
    sqlite3_exec(ls->db, "BEGIN;", NULL, NULL, NULL);
    ls->pending_writes = 0;
    return 0;
}

event_t *live_state_query_kind(live_state_t *ls, int kind, size_t *count)
{
    if (ls == NULL || count == NULL) {
        if (count) *count = 0;
        return NULL;
    }
    *count = 0;

    /* First pass: count matches */
    size_t n = 0;
    for (uint32_t i = 0; i < ls->event_count; i++) {
        if (ls->events[i].kind == kind) n++;
    }
    if (n == 0) {
        return NULL;
    }

    event_t *arr = (event_t *)malloc(n * sizeof(event_t));
    if (arr == NULL) {
        return NULL;
    }
    size_t j = 0;
    for (uint32_t i = 0; i < ls->event_count; i++) {
        if (ls->events[i].kind == kind) {
            arr[j++] = ls->events[i];
        }
    }
    *count = n;
    return arr;
}

event_t *live_state_query_severity_above(live_state_t *ls, int level, size_t *count)
{
    if (ls == NULL || count == NULL) {
        if (count) *count = 0;
        return NULL;
    }
    *count = 0;

    size_t n = 0;
    for (uint32_t i = 0; i < ls->event_count; i++) {
        if (ls->events[i].severity >= level) n++;
    }
    if (n == 0) {
        return NULL;
    }

    event_t *arr = (event_t *)malloc(n * sizeof(event_t));
    if (arr == NULL) {
        return NULL;
    }
    size_t j = 0;
    for (uint32_t i = 0; i < ls->event_count; i++) {
        if (ls->events[i].severity >= level) {
            arr[j++] = ls->events[i];
        }
    }
    *count = n;
    return arr;
}

event_t *live_state_query_phase(live_state_t *ls, int phase, size_t *count)
{
    if (ls == NULL || count == NULL) {
        if (count) *count = 0;
        return NULL;
    }
    *count = 0;

    size_t n = 0;
    for (uint32_t i = 0; i < ls->event_count; i++) {
        if (ls->events[i].phase == phase) n++;
    }
    if (n == 0) {
        return NULL;
    }

    event_t *arr = (event_t *)malloc(n * sizeof(event_t));
    if (arr == NULL) {
        return NULL;
    }
    size_t j = 0;
    for (uint32_t i = 0; i < ls->event_count; i++) {
        if (ls->events[i].phase == phase) {
            arr[j++] = ls->events[i];
        }
    }
    *count = n;
    return arr;
}

uint64_t live_state_count_kind(live_state_t *ls, int kind)
{
    if (ls == NULL || kind < 0 || kind >= KIND_COUNT) {
        return 0;
    }
    return ls->count_by_kind[kind];
}

uint64_t live_state_count_severity(live_state_t *ls, int level)
{
    if (ls == NULL || level < 0 || level >= SEVERITY_LEVELS) {
        return 0;
    }
    return ls->count_by_severity[level];
}

uint64_t live_state_total(live_state_t *ls)
{
    if (ls == NULL) {
        return 0;
    }
    return ls->total_events;
}

void live_state_shutdown(live_state_t *ls)
{
    if (ls == NULL) {
        return;
    }

    /* Flush pending SQLite writes */
    if (ls->sqlite_enabled) {
        live_state_flush(ls);
    }

    /* Close SQLite */
    if (ls->stmt_insert != NULL) {
        sqlite3_finalize(ls->stmt_insert);
        ls->stmt_insert = NULL;
    }
    if (ls->db != NULL) {
        sqlite3_close(ls->db);
        ls->db = NULL;
    }

    /* Free RAM events array */
    if (ls->events != NULL) {
        free(ls->events);
        ls->events = NULL;
    }
    ls->event_count = 0;
    ls->event_capacity = 0;
    ls->total_events = 0;

    pthread_mutex_destroy(&ls->lock);

    /* Free interned strings */
    str_intern_shutdown();
}
