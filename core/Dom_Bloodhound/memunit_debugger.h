/*
 * memunit_debugger.h - C Memory Unit Debugger Master Header
 *[@GHOST]{file_path="core/Dom_Bloodhound/memunit_debugger.h" date="2026-07-04" author="Devin" session_id="memunit-c" context="Master header: types, structs, constants, function declarations for event bus, string interning, LiveState, EventViewer, ClassTester"}
 *[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE lock-free ring-buffer"}
 *[@FILEID]{id="memunit_debugger.h" domain="dom_bloodhound" authority="MemunitDebugger"}
 *[@SUMMARY]{summary="All types, structs, constants, function declarations. EventKind/EventPhase/Severity enums, event_t/event_bus_t/live_state_t for event bus + tester, Event/LiveState/RenderQueue/EventViewer for viewer, class_tester_t for ClassTester."}
 *[@CLASS]{class="MemunitDebugger" domain="dom_bloodhound" authority="master"}
 *[@METHOD]{methods="str_intern,str_lookup,event_bus_init,event_bus_push,event_bus_pop,live_state_init,live_state_emit,live_state_flush,live_state_query_kind,live_state_query_severity_above,live_state_query_phase,live_state_count_kind,live_state_count_severity,live_state_total,live_state_shutdown,viewer_init,viewer_start,viewer_stop,viewer_shutdown,viewer_render_table,viewer_render_summary,viewer_render_errors,viewer_render_tests,viewer_push_event,tester_init,tester_test_imports,tester_test_class,tester_test_all,tester_test_errors"}
 */

#ifndef MEMUNIT_DEBUGGER_H
#define MEMUNIT_DEBUGGER_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include <pthread.h>
#include <unistd.h>
#include <sqlite3.h>

/* ====================================================================
 * Constants
 * ==================================================================== */

#define MU_VERSION          "1.0.0"
#define MEMUNIT_MAX_EVENTS  100000
#define MEMUNIT_MAX_STR     256
#define MAX_EVENTS          100000
#define MAX_EVENTS_INITIAL  1024
#define STR_INTERN_INITIAL  256
#define STR_MAX_LEN         256
#define COMMIT_INTERVAL     500
#define MAX_CLASS_NAME      256
#define MU_MAX_PRODUCER     256
#define MU_DEFAULT_HZ       10
#define MU_QUEUE_SIZE       1024

/* ====================================================================
 * Enums: EventKind, EventPhase, Severity
 * Shared across event_t (event_bus) and Event (viewer)
 * ==================================================================== */

typedef enum {
    MU_KIND_IMPORT   = 0,
    MU_KIND_STATE    = 1,
    MU_KIND_CALL     = 2,
    MU_KIND_RESULT   = 3,
    MU_KIND_ERROR    = 4,
    MU_KIND_TIMING   = 5,
    MU_KIND_VARIABLE = 6,
    MU_KIND_STEP     = 7,
    MU_KIND_FIX      = 8,
    MU_KIND_TRACE    = 9,
    MU_KIND_DEBUG    = 10,
    MU_KIND_INFO     = 11,
    MU_KIND_WARN     = 12,
    MU_KIND_FATAL    = 13,
    MU_KIND_METRIC   = 14,
    MU_KIND_RETURN   = 15,
    MU_KIND_COUNT    = 16
} EventKind;

/* EVENT_* aliases for tester and event_bus */
#define EVENT_IMPORT    MU_KIND_IMPORT
#define EVENT_STATE     MU_KIND_STATE
#define EVENT_CALL      MU_KIND_CALL
#define EVENT_RESULT    MU_KIND_RESULT
#define EVENT_ERROR     MU_KIND_ERROR
#define EVENT_TIMING    MU_KIND_TIMING
#define EVENT_VARIABLE  MU_KIND_VARIABLE
#define EVENT_STEP      MU_KIND_STEP
#define EVENT_FIX       MU_KIND_FIX
#define EVENT_TRACE     MU_KIND_TRACE
#define EVENT_DEBUG     MU_KIND_DEBUG
#define EVENT_INFO      MU_KIND_INFO
#define EVENT_WARN      MU_KIND_WARN
#define EVENT_FATAL     MU_KIND_FATAL
#define EVENT_METRIC    MU_KIND_METRIC
#define EVENT_RETURN    MU_KIND_RETURN

#define KIND_COUNT      MU_KIND_COUNT

typedef enum {
    PHASE_INIT     = 0,
    PHASE_SETUP    = 1,
    PHASE_RUN      = 2,
    PHASE_TEARDOWN = 3,
    PHASE_BEGIN    = 4,
    PHASE_END      = 5,
    PHASE_STEP     = 6,
    PHASE_CHECK    = 7,
    PHASE_RETRY    = 8,
    PHASE_SHUTDOWN = 9,
    PHASE_COUNT    = 10
} EventPhase;

typedef enum {
    MU_SEV_TRACE = 0,
    MU_SEV_DEBUG = 1,
    MU_SEV_INFO  = 2,
    MU_SEV_WARN  = 3,
    MU_SEV_ERROR = 4,
    MU_SEV_FATAL = 5,
    MU_SEV_PANIC = 6,
    MU_SEV_NONE  = 7,
    MU_SEV_COUNT = 8
} Severity;

#define SEV_TRACE   MU_SEV_TRACE
#define SEV_DEBUG   MU_SEV_DEBUG
#define SEV_INFO    MU_SEV_INFO
#define SEV_WARN    MU_SEV_WARN
#define SEV_ERROR   MU_SEV_ERROR
#define SEV_FATAL   MU_SEV_FATAL
#define SEV_PANIC   MU_SEV_PANIC
#define SEV_NONE    MU_SEV_NONE

#define SEVERITY_LEVELS MU_SEV_COUNT

/* ====================================================================
 * event_t / event_bus_t / live_state_t
 * Used by memunit_event_bus.c and memunit_tester.c
 * ==================================================================== */

typedef struct {
    uint64_t    id;
    double      timestamp_ns;
    int         source;       /* interned string ID */
    int         phase;        /* EventPhase */
    int         kind;         /* EventKind */
    int         entity;       /* interned string ID */
    char        name[STR_MAX_LEN];
    char        value[STR_MAX_LEN];
    int         severity;     /* Severity */
    uint64_t    parent_id;
} event_t;

typedef struct {
    event_t        *events;
    uint32_t        capacity;
    uint32_t        mask;
    volatile uint32_t head;
    volatile uint32_t tail;
    pthread_mutex_t lock;
} event_bus_t;

typedef struct {
    event_t        *events;
    uint32_t        event_count;
    uint32_t        event_capacity;
    uint64_t        next_id;
    uint64_t        total_events;
    uint64_t        error_count;
    uint64_t        count_by_kind[KIND_COUNT];
    uint64_t        count_by_phase[PHASE_COUNT];
    uint64_t        count_by_severity[SEVERITY_LEVELS];
    pthread_mutex_t lock;
    int             sqlite_enabled;
    sqlite3        *db;
    sqlite3_stmt   *stmt_insert;
    uint32_t        pending_writes;
    uint32_t        commit_interval;
} live_state_t;

typedef struct {
    live_state_t  *state;
    int            tests_run;
    int            tests_passed;
    int            tests_failed;
} class_tester_t;

/* ====================================================================
 * Event / LiveState / RenderQueue / EventViewer
 * Used by memunit_viewer.c
 * ==================================================================== */

typedef struct {
    int       id;
    double    timestamp;
    int       kind;         /* EventKind */
    int       severity;     /* Severity */
    int       parent_id;
    char      producer[MEMUNIT_MAX_STR];
    char      phase[MEMUNIT_MAX_STR];
    char      entity[MEMUNIT_MAX_STR];
    char      attribute[MEMUNIT_MAX_STR];
    char      value[MEMUNIT_MAX_STR];
    char      reasoning[MEMUNIT_MAX_STR];
} Event;

typedef struct {
    Event           events[MEMUNIT_MAX_EVENTS];
    int             count;
    int             next_id;
    uint64_t        by_kind[MU_KIND_COUNT];
    uint64_t        total;
    uint64_t        errors;
    pthread_mutex_t lock;
} LiveState;

typedef struct {
    Event           *buffer;
    size_t           capacity;
    size_t           head;
    size_t           tail;
    pthread_mutex_t  lock;
    pthread_cond_t   cond;
} RenderQueue;

typedef struct {
    LiveState       *state;
    RenderQueue     *queue;
    int              verbosity;
    int              refresh_hz;
    int              running;
    int              live_mode;
    int              rows_printed;
    pthread_t        thread;
} EventViewer;

/* ====================================================================
 * String Interning
 * ==================================================================== */

int          str_intern(const char *s);
const char  *str_lookup(int id);
void         str_intern_shutdown(void);

/* ====================================================================
 * Ring Buffer Event Bus (SPSC)
 * ==================================================================== */

int  event_bus_init(event_bus_t *bus, uint32_t capacity);
int  event_bus_push(event_bus_t *bus, const event_t *ev);
int  event_bus_pop(event_bus_t *bus, event_t *out);
void event_bus_shutdown(event_bus_t *bus);

/* ====================================================================
 * LiveState (RAM-first with optional SQLite archival)
 * ==================================================================== */

int       live_state_init(live_state_t *ls, int enable_sqlite);
uint64_t  live_state_emit(live_state_t *ls,
                          const char *source,
                          int phase,
                          int kind,
                          const char *entity,
                          const char *name,
                          const char *value,
                          int severity,
                          uint64_t parent_id);
int       live_state_flush(live_state_t *ls);
event_t  *live_state_query_kind(live_state_t *ls, int kind, size_t *count);
event_t  *live_state_query_severity_above(live_state_t *ls, int level, size_t *count);
event_t  *live_state_query_phase(live_state_t *ls, int phase, size_t *count);
uint64_t  live_state_count_kind(live_state_t *ls, int kind);
uint64_t  live_state_count_severity(live_state_t *ls, int level);
uint64_t  live_state_total(live_state_t *ls);
void      live_state_shutdown(live_state_t *ls);

/* ====================================================================
 * ClassTester
 * ==================================================================== */

int  tester_init(class_tester_t *t, live_state_t *ls);
int  tester_test_imports(class_tester_t *t);
int  tester_test_class(class_tester_t *t, const char *class_name);
int  tester_test_all(class_tester_t *t);
int  tester_test_errors(class_tester_t *t);
int  get_unique_classes(live_state_t *ls, uint32_t out[], int max_classes);
int  has_event_kind(live_state_t *ls, uint32_t source, uint32_t kind);
int  has_error_for(live_state_t *ls, uint32_t entity);

/* ====================================================================
 * EventViewer
 * ==================================================================== */

void viewer_init(EventViewer *v, LiveState *st, int verbosity, int refresh_hz);
int  viewer_start(EventViewer *v);
void viewer_stop(EventViewer *v);
void viewer_shutdown(EventViewer *v);
void viewer_render_table(EventViewer *v);
void viewer_render_summary(EventViewer *v);
void viewer_render_errors(EventViewer *v);
void viewer_render_tests(EventViewer *v);
void viewer_push_event(EventViewer *v, const Event *ev);

#endif /* MEMUNIT_DEBUGGER_H */
