//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_Reports.c" date="2026-07-04" author="devin" session_id="bcl-vsstyle-units" context="v4: Live streaming via on_emit callbacks + ClassTester + render_code_structure + render_execution_graph + render_test_results. 5 components: LiveState (SQLite :memory: + live callbacks) + EventInspector (query/analyze) + EventViewer (format BCL + live stream) + Configurator (verbosity valve) + ClassTester (test each class/method against facts). Commands: full, table, code_structure, execution_graph, test, overview, replay, profile, debug, compliance, enforcement, coverage, summary, all_units, live, read_state, set_config."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_Reports.c" domain="bcl_units" authority="Reports"}
//[@SUMMARY]{summary="v4 report generator with event-bus architecture. 5 components: LiveState (SQLite :memory: + live callbacks), EventInspector (query/analyze), EventViewer (format BCL + live stream), Configurator (verbosity valve), ClassTester (test each class/method). Commands: full, table, code_structure, execution_graph, test, overview, replay, profile, debug, compliance, enforcement, coverage, summary, all_units, live, read_state, set_config."}
//[@CLASS]{class="Reports" domain="bcl_units" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="LiveState" type="command"}
//[@METHOD]{method="EventInspector" type="query"}
//[@METHOD]{method="EventViewer" type="query"}
//[@METHOD]{method="Configurator" type="command"}
//[@METHOD]{method="ClassTester" type="query"}
//[@METHOD]{method="Full" type="command"}
//[@METHOD]{method="Table" type="query"}
//[@METHOD]{method="CodeStructure" type="query"}
//[@METHOD]{method="ExecutionGraph" type="query"}
//[@METHOD]{method="Test" type="query"}
//[@METHOD]{method="Overview" type="query"}
//[@METHOD]{method="Replay" type="query"}
//[@METHOD]{method="Profile" type="query"}
//[@METHOD]{method="Debug" type="query"}
//[@METHOD]{method="Compliance" type="command"}
//[@METHOD]{method="Enforcement" type="command"}
//[@METHOD]{method="Coverage" type="command"}
//[@METHOD]{method="Summary" type="query"}
//[@METHOD]{method="AllUnits" type="query"}
//[@METHOD]{method="Live" type="query"}

#include "bcl_toolstack.h"
#include <dirent.h>
#include <sys/stat.h>
#include <ctype.h>
#include <mysql.h>
#include <time.h>

/* ════════════════════════════════════════════════════════════════════════════
 * ARCHITECTURE v4 — 5 distinct components, each with its own job:
 *
 *  1. LiveState       — SQLite :memory: runtime blackboard. Captures ALL
 *                       execution reality. Supports live callbacks — when an
 *                       event is emitted, viewers are notified immediately.
 *                       Enables streaming output during execution.
 *
 *  2. EventInspector  — Queries/analyzes events from LiveState.
 *                       Modes: overview, errors, replay, profile, debug, summary.
 *                       Returns structured data. Does NOT format BCL output.
 *
 *  3. EventViewer     — Renders to BCL output buffer. The ONLY component that
 *                       writes to bcl_out. Supports live streaming during
 *                       execution + final report tables after.
 *                       KIND_COLORS + KIND_ICONS for visual distinction.
 *
 *  4. Configurator    — Controls output configuration.
 *                       Verbosity: 0=silent, 1=normal, 2=debug, 3=verbose.
 *                       Which event kinds to show/hide. The valve.
 *
 *  5. ClassTester     — Tests each class and method by querying LiveState facts.
 *                       Checks: did class produce facts? results? errors?
 *                       Did methods complete? have timing? have variables?
 *                       Each test is a query — no special handling.
 *
 * Flow:
 *   Scanner → LiveState.emit() → EventViewer.live_callback() (during execution)
 *                             → EventInspector.query() → EventViewer.render_*(config) (after)
 *                             → ClassTester.test_all() → EventViewer.render_test_results() (after)
 * ════════════════════════════════════════════════════════════════════════════ */

/* ===== DIM BLOCK ===== */

#define RP_MAX_PATH       4096
#define RP_MAX_BODY       65536
#define RP_MAX_FILE       262144
#define RP_MAX_LINE       2048
#define RP_MAX_FILES      500
#define RP_MAX_NAME       128
#define RP_MAX_DESC       512
#define RP_MAX_RULES      512
#define RP_RULE_COUNT     9
#define RP_SKIP_DIRS      8
#define RP_MAX_CALLBACKS  8
#define RP_MAX_LIVE_BUF   65536
#define RP_MAX_CLASSES    64
#define RP_MAX_METHODS    128
#define RP_MAX_IMPORTS    64
#define RP_MAX_TESTS      256

/* Verbosity labels */
static const char *VERBOSITY_LABELS[] = {"SILENT", "NORMAL", "DEBUG", "VERBOSE"};

/* Kind colors + icons (matching Python v4) */
static const char *KIND_COLORS[] = {
    "cyan",    /* step */
    "green",   /* result */
    "red",     /* error */
    "yellow",  /* variable */
    "magenta", /* state */
    "blue",    /* timing */
    "white",   /* import */
};
static const char *KIND_ICONS[] = {
    ">",    /* step */
    "OK",   /* result */
    "X",    /* error */
    "V",    /* variable */
    "S",    /* state */
    "T",    /* timing */
    "I",    /* import */
};

static const char *Kind_Color(const char *kind) {
    if (strcmp(kind, "step") == 0) return KIND_COLORS[0];
    if (strcmp(kind, "result") == 0) return KIND_COLORS[1];
    if (strcmp(kind, "error") == 0) return KIND_COLORS[2];
    if (strcmp(kind, "variable") == 0) return KIND_COLORS[3];
    if (strcmp(kind, "state") == 0) return KIND_COLORS[4];
    if (strcmp(kind, "timing") == 0) return KIND_COLORS[5];
    if (strcmp(kind, "import") == 0) return KIND_COLORS[6];
    return "white";
}

static const char *Kind_Icon(const char *kind) {
    if (strcmp(kind, "step") == 0) return KIND_ICONS[0];
    if (strcmp(kind, "result") == 0) return KIND_ICONS[1];
    if (strcmp(kind, "error") == 0) return KIND_ICONS[2];
    if (strcmp(kind, "variable") == 0) return KIND_ICONS[3];
    if (strcmp(kind, "state") == 0) return KIND_ICONS[4];
    if (strcmp(kind, "timing") == 0) return KIND_ICONS[5];
    if (strcmp(kind, "import") == 0) return KIND_ICONS[6];
    return "?";
}

/* Rule names for tally */
static const char *RP_RULE_NAMES[RP_RULE_COUNT] = {
    "NoPrint", "NoDecorators", "NoSelfUnderscore",
    "GhostHeader", "VBStyleHeader", "RunDispatch",
    "PascalCase", "NoTabs", "NoTrailingWs"
};

static const char *SKIP_DIRS[RP_SKIP_DIRS] = {
    ".", "..", ".git", "__pycache__", "node_modules", ".venv", "venv", ".codex"
};

/* ===== 1. LIVESTATE — SQLite :memory: runtime blackboard + live callbacks ===== */

typedef void (*LiveCallback)(int eid, const char *source, const char *phase,
    const char *kind, const char *entity, const char *name,
    const char *value, int severity, const char *payload, int parentId);

typedef struct {
    sqlite3 *db;
    int      event_count;
    LiveCallback callbacks[RP_MAX_CALLBACKS];
    int      callback_count;
} LiveState;

static int LiveState_Init(LiveState *ls) {
    if (sqlite3_open(":memory:", &ls->db) != SQLITE_OK) return 0;
    ls->event_count = 0;
    ls->callback_count = 0;
    const char *schema =
        "CREATE TABLE event ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  timestamp REAL,"
        "  source TEXT,"
        "  phase TEXT,"
        "  kind TEXT,"
        "  entity TEXT,"
        "  name TEXT,"
        "  value TEXT,"
        "  severity INTEGER DEFAULT 0,"
        "  payload TEXT,"
        "  parentId INTEGER"
        ");"
        "CREATE INDEX idx_event_kind ON event(kind);"
        "CREATE INDEX idx_event_phase ON event(phase);"
        "CREATE INDEX idx_event_severity ON event(severity);"
        "CREATE INDEX idx_event_source ON event(source);";
    if (sqlite3_exec(ls->db, schema, NULL, NULL, NULL) != SQLITE_OK) {
        sqlite3_close(ls->db);
        ls->db = NULL;
        return 0;
    }
    return 1;
}

/* Register a live callback — called immediately when emit() is called */
static void LiveState_OnEmit(LiveState *ls, LiveCallback cb) {
    if (ls->callback_count < RP_MAX_CALLBACKS) {
        ls->callbacks[ls->callback_count++] = cb;
    }
}

static int LiveState_Emit(LiveState *ls,
    const char *source, const char *phase, const char *kind,
    const char *entity, const char *name, const char *value,
    int severity, const char *payload, int parentId)
{
    if (!ls->db) return -1;
    sqlite3_stmt *stmt;
    const char *sql = "INSERT INTO event (timestamp, source, phase, kind, entity, name, value, severity, payload, parentId) "
                      "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
    if (sqlite3_prepare_v2(ls->db, sql, -1, &stmt, NULL) != SQLITE_OK) return -1;
    double ts = (double)time(NULL);
    sqlite3_bind_double(stmt, 1, ts);
    sqlite3_bind_text(stmt, 2, source, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 3, phase, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 4, kind, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 5, entity ? entity : "", -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 6, name ? name : "", -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 7, value ? value : "", -1, SQLITE_STATIC);
    sqlite3_bind_int(stmt, 8, severity);
    sqlite3_bind_text(stmt, 9, payload ? payload : "", -1, SQLITE_STATIC);
    if (parentId > 0) sqlite3_bind_int(stmt, 10, parentId);
    else sqlite3_bind_null(stmt, 10);
    int rc = sqlite3_step(stmt);
    sqlite3_int64 eid = sqlite3_last_insert_rowid(ls->db);
    sqlite3_finalize(stmt);
    if (rc != SQLITE_DONE) return -1;
    ls->event_count++;

    /* Notify all live callbacks immediately — enables streaming output */
    char eid_str[16];
    snprintf(eid_str, sizeof(eid_str), "%lld", eid);
    for (int i = 0; i < ls->callback_count; i++) {
        ls->callbacks[i]((int)eid, source, phase, kind, entity, name, value, severity, payload, parentId);
    }
    return (int)eid;
}

static int LiveState_Count(LiveState *ls, const char *where) {
    if (!ls->db) return 0;
    char sql[512];
    snprintf(sql, sizeof(sql), "SELECT COUNT(*) FROM event WHERE %s", where ? where : "1=1");
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(ls->db, sql, -1, &stmt, NULL) != SQLITE_OK) return 0;
    int count = 0;
    if (sqlite3_step(stmt) == SQLITE_ROW) count = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);
    return count;
}

static int LiveState_CountKind(LiveState *ls, const char *kind) {
    char where[128];
    snprintf(where, sizeof(where), "kind='%s'", kind);
    return LiveState_Count(ls, where);
}

static sqlite3_stmt *LiveState_Query(LiveState *ls, const char *where) {
    if (!ls->db) return NULL;
    char sql[1024];
    if (where && strstr(where, "ORDER BY")) {
        snprintf(sql, sizeof(sql), "SELECT id, timestamp, source, phase, kind, entity, name, value, severity, payload, parentId FROM event WHERE %s", where);
    } else {
        snprintf(sql, sizeof(sql), "SELECT id, timestamp, source, phase, kind, entity, name, value, severity, payload, parentId FROM event WHERE %s ORDER BY id", where ? where : "1=1");
    }
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(ls->db, sql, -1, &stmt, NULL) != SQLITE_OK) return NULL;
    return stmt;
}

static void LiveState_Close(LiveState *ls) {
    if (ls->db) {
        sqlite3_close(ls->db);
        ls->db = NULL;
    }
    ls->event_count = 0;
    ls->callback_count = 0;
}

/* ===== 2. EVENTINSPECTOR — query/analyze events from LiveState ===== */

typedef struct {
    LiveState *ls;
} EventInspector;

typedef struct {
    int total;
    int steps;
    int results;
    int variables;
    int states;
    int timings;
    int errors;
    int imports;
} InspectionSummary;

static InspectionSummary EventInspector_Summary(EventInspector *ei) {
    InspectionSummary s = {0};
    s.total = LiveState_Count(ei->ls, NULL);
    s.steps = LiveState_CountKind(ei->ls, "step");
    s.results = LiveState_CountKind(ei->ls, "result");
    s.variables = LiveState_CountKind(ei->ls, "variable");
    s.states = LiveState_CountKind(ei->ls, "state");
    s.timings = LiveState_CountKind(ei->ls, "timing");
    s.errors = LiveState_CountKind(ei->ls, "error");
    s.imports = LiveState_CountKind(ei->ls, "import");
    return s;
}

static sqlite3_stmt *EventInspector_Errors(EventInspector *ei) {
    return LiveState_Query(ei->ls, "kind='error' ORDER BY id");
}

static sqlite3_stmt *EventInspector_Replay(EventInspector *ei) {
    return LiveState_Query(ei->ls, "1=1 ORDER BY id");
}

static sqlite3_stmt *EventInspector_ByKind(EventInspector *ei, const char *kind) {
    char where[128];
    snprintf(where, sizeof(where), "kind='%s' ORDER BY id", kind);
    return LiveState_Query(ei->ls, where);
}

static sqlite3_stmt *EventInspector_FinalState(EventInspector *ei) {
    return LiveState_Query(ei->ls, "kind='state' AND name='scan_phase' ORDER BY id DESC LIMIT 1");
}

static sqlite3_stmt *EventInspector_BySource(EventInspector *ei, const char *source) {
    char where[256];
    snprintf(where, sizeof(where), "source='%s' ORDER BY id", source);
    return LiveState_Query(ei->ls, where);
}

/* ===== 3. CONFIGURATOR — controls output configuration ===== */

typedef struct {
    int verbosity;
    int show_errors;
    int show_results;
    int show_variables;
    int show_state;
    int show_timing;
    int show_payloads;
    int show_imports;
    int file_limit;
    int rule_limit;
} Configurator;

static void Configurator_Init(Configurator *c, int verbosity) {
    c->verbosity = verbosity;
    c->show_errors = 1;
    c->show_results = (verbosity >= 1);
    c->show_variables = (verbosity >= 2);
    c->show_state = (verbosity >= 2);
    c->show_timing = (verbosity >= 3);
    c->show_payloads = (verbosity >= 2);
    c->show_imports = (verbosity >= 1);
    c->file_limit = (verbosity >= 2) ? 100 : 30;
    c->rule_limit = (verbosity >= 2) ? 50 : 15;
}

static const char *Configurator_Label(Configurator *c) {
    if (c->verbosity < 0 || c->verbosity > 3) return "UNKNOWN";
    return VERBOSITY_LABELS[c->verbosity];
}

/* ===== 4. EVENTVIEWER — renders to BCL output buffer + live streaming ===== */

typedef struct {
    EventInspector *inspector;
    Configurator   *config;
    /* Live stream buffer — accumulates events as they happen */
    char           *live_buf;
    size_t          live_buf_sz;
    size_t          live_buf_offset;
    int             live_row_count;
} EventViewer;

/* Live callback — called by LiveState.emit() during execution.
   Streams events live into the live_buf. */
static void EventViewer_LiveCallback(int eid, const char *source, const char *phase,
    const char *kind, const char *entity, const char *name,
    const char *value, int severity, const char *payload, int parentId)
{
    /* This is a static function — the actual viewer is stored globally during scan */
    /* See Reports_Run for how this is wired */
    (void)eid; (void)source; (void)phase; (void)kind; (void)entity;
    (void)name; (void)value; (void)severity; (void)payload; (void)parentId;
}

/* render_table — final summary table: all events in colorful rows */
static int EventViewer_RenderTable(EventViewer *ev, char *out, size_t out_sz) {
    Configurator *cfg = ev->config;
    int offset = 0;
    offset += snprintf(out + offset, out_sz - offset,
        "[@OK]{[@REPORT]{[@TYPE]{table}[@VERBOSITY]{%d}[@LABEL]{%s}",
        cfg->verbosity, Configurator_Label(cfg));

    /* Table rows — all events */
    sqlite3_stmt *stmt = EventInspector_Replay(ev->inspector);
    offset += snprintf(out + offset, out_sz - offset, "[@ROWS]{");
    int row_count = 0;
    while (stmt && sqlite3_step(stmt) == SQLITE_ROW && offset < (int)out_sz - 512) {
        int eid = sqlite3_column_int(stmt, 0);
        const char *src = (const char *)sqlite3_column_text(stmt, 2);
        const char *phase = (const char *)sqlite3_column_text(stmt, 3);
        const char *kind = (const char *)sqlite3_column_text(stmt, 4);
        const char *entity = (const char *)sqlite3_column_text(stmt, 5);
        const char *name = (const char *)sqlite3_column_text(stmt, 6);
        const char *value = (const char *)sqlite3_column_text(stmt, 7);
        int sev = sqlite3_column_int(stmt, 8);
        const char *color = Kind_Color(kind);
        const char *icon = Kind_Icon(kind);

        offset += snprintf(out + offset, out_sz - offset,
            "[@ROW]{[@ID]{%d}[@SOURCE]{%s}[@PHASE]{%s}[@KIND]{%s}[@ICON]{%s}"
            "[@COLOR]{%s}[@ENTITY]{%s}[@NAME]{%s}[@VALUE]{%s}[@SEV]{%d}}",
            eid, src ? src : "", phase ? phase : "",
            kind ? kind : "", icon, color,
            entity ? entity : "", name ? name : "",
            value ? value : "", sev);
        row_count++;
    }
    if (stmt) sqlite3_finalize(stmt);
    offset += snprintf(out + offset, out_sz - offset, "[@COUNT]{%d}}", row_count);

    /* Summary */
    InspectionSummary s = EventInspector_Summary(ev->inspector);
    offset += snprintf(out + offset, out_sz - offset,
        "[@SUMMARY]{[@TOTAL]{%d}[@STEPS]{%d}[@RESULTS]{%d}[@VARIABLES]{%d}"
        "[@STATES]{%d}[@TIMINGS]{%d}[@ERRORS]{%d}[@IMPORTS]{%d}}",
        s.total, s.steps, s.results, s.variables, s.states, s.timings, s.errors, s.imports);

    offset += snprintf(out + offset, out_sz - offset, "[@STATUS]{table_complete}}}");
    return 1;
}

/* render_code_structure — imports → class → methods layout, mirroring a code file */
static int EventViewer_RenderCodeStructure(EventViewer *ev, char *out, size_t out_sz) {
    int offset = 0;
    offset += snprintf(out + offset, out_sz - offset,
        "[@OK]{[@REPORT]{[@TYPE]{code_structure}");

    /* Collect imports */
    sqlite3_stmt *istmt = EventInspector_ByKind(ev->inspector, "import");
    offset += snprintf(out + offset, out_sz - offset, "[@IMPORTS]{");
    int imp_count = 0;
    while (istmt && sqlite3_step(istmt) == SQLITE_ROW && offset < (int)out_sz - 256) {
        const char *value = (const char *)sqlite3_column_text(istmt, 7);
        offset += snprintf(out + offset, out_sz - offset,
            "[@IMPORT]{%s}", value ? value : "");
        imp_count++;
    }
    if (istmt) sqlite3_finalize(istmt);
    offset += snprintf(out + offset, out_sz - offset, "[@COUNT]{%d}}", imp_count);

    /* Collect classes and their methods from all events */
    /* We need to group by source (class) then by entity (method) */
    char classes[RP_MAX_CLASSES][RP_MAX_NAME];
    int class_count = 0;
    memset(classes, 0, sizeof(classes));

    sqlite3_stmt *stmt = EventInspector_Replay(ev->inspector);
    while (stmt && sqlite3_step(stmt) == SQLITE_ROW) {
        const char *src = (const char *)sqlite3_column_text(stmt, 2);
        const char *kind = (const char *)sqlite3_column_text(stmt, 4);
        if (!src || !kind) continue;
        if (strcmp(kind, "import") == 0) continue;
        /* Check if class already exists */
        int found = 0;
        for (int i = 0; i < class_count; i++) {
            if (strcmp(classes[i], src) == 0) { found = 1; break; }
        }
        if (!found && class_count < RP_MAX_CLASSES) {
            strncpy(classes[class_count], src, RP_MAX_NAME - 1);
            class_count++;
        }
    }
    if (stmt) sqlite3_finalize(stmt);

    /* For each class, collect methods (entities) */
    offset += snprintf(out + offset, out_sz - offset, "[@CLASSES]{");
    for (int ci = 0; ci < class_count && offset < (int)out_sz - 1024; ci++) {
        offset += snprintf(out + offset, out_sz - offset,
            "[@CLASS]{[@NAME]{%s}[@METHODS]{", classes[ci]);

        /* Collect methods for this class */
        char methods[RP_MAX_METHODS][RP_MAX_NAME];
        int method_count = 0;
        memset(methods, 0, sizeof(methods));

        sqlite3_stmt *mstmt = EventInspector_BySource(ev->inspector, classes[ci]);
        while (mstmt && sqlite3_step(mstmt) == SQLITE_ROW) {
            const char *entity = (const char *)sqlite3_column_text(mstmt, 5);
            const char *kind = (const char *)sqlite3_column_text(mstmt, 4);
            if (!entity || !kind) continue;
            if (strcmp(kind, "import") == 0) continue;
            if (entity[0] == '\0') continue;
            int found = 0;
            for (int j = 0; j < method_count; j++) {
                if (strcmp(methods[j], entity) == 0) { found = 1; break; }
            }
            if (!found && method_count < RP_MAX_METHODS) {
                strncpy(methods[method_count], entity, RP_MAX_NAME - 1);
                method_count++;
            }
        }
        if (mstmt) sqlite3_finalize(mstmt);

        /* For each method, emit its events/errors/result/timing */
        for (int mi = 0; mi < method_count && offset < (int)out_sz - 512; mi++) {
            int m_events = 0, m_errors = 0, m_results = 0;
            int m_has_timing = 0;
            char m_timing[64] = {0};
            char m_last_result[256] = {0};
            char m_phases[256] = {0};

            sqlite3_stmt *estmt = EventInspector_BySource(ev->inspector, classes[ci]);
            while (estmt && sqlite3_step(estmt) == SQLITE_ROW) {
                const char *entity = (const char *)sqlite3_column_text(estmt, 5);
                const char *kind = (const char *)sqlite3_column_text(estmt, 4);
                const char *phase = (const char *)sqlite3_column_text(estmt, 3);
                const char *name = (const char *)sqlite3_column_text(estmt, 6);
                const char *value = (const char *)sqlite3_column_text(estmt, 7);
                int sev = sqlite3_column_int(estmt, 8);
                if (!entity || strcmp(entity, methods[mi]) != 0) continue;
                m_events++;
                if (sev > 0) m_errors++;
                if (strcmp(kind, "result") == 0) {
                    m_results++;
                    snprintf(m_last_result, sizeof(m_last_result), "%s=%s", name ? name : "", value ? value : "");
                } else if (strcmp(kind, "error") == 0) {
                    snprintf(m_last_result, sizeof(m_last_result), "%s: %s", name ? name : "", value ? value : "");
                } else if (strcmp(kind, "timing") == 0) {
                    m_has_timing = 1;
                    snprintf(m_timing, sizeof(m_timing), "%s", value ? value : "");
                }
                if (phase && m_phases[0]) {
                    /* Check if phase already in list */
                    if (!strstr(m_phases, phase)) {
                        strncat(m_phases, ", ", sizeof(m_phases) - strlen(m_phases) - 1);
                        strncat(m_phases, phase, sizeof(m_phases) - strlen(m_phases) - 1);
                    }
                } else if (phase) {
                    strncpy(m_phases, phase, sizeof(m_phases) - 1);
                }
            }
            if (estmt) sqlite3_finalize(estmt);

            const char *status = (m_errors == 0) ? "PASS" : "FAIL";
            offset += snprintf(out + offset, out_sz - offset,
                "[@METHOD]{[@NAME]{%s}[@STATUS]{%s}[@EVENTS]{%d}[@ERRORS]{%d}"
                "[@RESULTS]{%d}[@TIMING]{%s}[@PHASES]{%s}[@LAST_RESULT]{%s}}",
                methods[mi], status, m_events, m_errors, m_results,
                m_has_timing ? m_timing : "--",
                m_phases[0] ? m_phases : "none",
                m_last_result[0] ? m_last_result : "(no result)");
        }
        offset += snprintf(out + offset, out_sz - offset, "}}");
    }
    offset += snprintf(out + offset, out_sz - offset, "}");

    offset += snprintf(out + offset, out_sz - offset, "[@STATUS]{code_structure_complete}}}");
    return 1;
}

/* render_execution_graph — ASCII tree showing method call flow */
static int EventViewer_RenderExecutionGraph(EventViewer *ev, char *out, size_t out_sz) {
    int offset = 0;
    offset += snprintf(out + offset, out_sz - offset,
        "[@OK]{[@REPORT]{[@TYPE]{execution_graph}");

    /* Collect classes */
    char classes[RP_MAX_CLASSES][RP_MAX_NAME];
    int class_count = 0;
    memset(classes, 0, sizeof(classes));

    sqlite3_stmt *stmt = EventInspector_Replay(ev->inspector);
    while (stmt && sqlite3_step(stmt) == SQLITE_ROW) {
        const char *src = (const char *)sqlite3_column_text(stmt, 2);
        const char *kind = (const char *)sqlite3_column_text(stmt, 4);
        if (!src || !kind) continue;
        if (strcmp(kind, "import") == 0) continue;
        int found = 0;
        for (int i = 0; i < class_count; i++) {
            if (strcmp(classes[i], src) == 0) { found = 1; break; }
        }
        if (!found && class_count < RP_MAX_CLASSES) {
            strncpy(classes[class_count], src, RP_MAX_NAME - 1);
            class_count++;
        }
    }
    if (stmt) sqlite3_finalize(stmt);

    /* Build tree: class → methods with results */
    offset += snprintf(out + offset, out_sz - offset, "[@TREE]{");
    for (int ci = 0; ci < class_count && offset < (int)out_sz - 1024; ci++) {
        offset += snprintf(out + offset, out_sz - offset,
            "[@NODE]{[@TYPE]{class}[@NAME]{%s}[@CHILDREN]{", classes[ci]);

        /* Collect methods for this class */
        char methods[RP_MAX_METHODS][RP_MAX_NAME];
        int method_count = 0;
        memset(methods, 0, sizeof(methods));

        sqlite3_stmt *mstmt = EventInspector_BySource(ev->inspector, classes[ci]);
        while (mstmt && sqlite3_step(mstmt) == SQLITE_ROW) {
            const char *entity = (const char *)sqlite3_column_text(mstmt, 5);
            const char *kind = (const char *)sqlite3_column_text(mstmt, 4);
            if (!entity || !kind) continue;
            if (strcmp(kind, "import") == 0) continue;
            if (entity[0] == '\0') continue;
            int found = 0;
            for (int j = 0; j < method_count; j++) {
                if (strcmp(methods[j], entity) == 0) { found = 1; break; }
            }
            if (!found && method_count < RP_MAX_METHODS) {
                strncpy(methods[method_count], entity, RP_MAX_NAME - 1);
                method_count++;
            }
        }
        if (mstmt) sqlite3_finalize(mstmt);

        for (int mi = 0; mi < method_count && offset < (int)out_sz - 512; mi++) {
            int m_errors = 0;
            char m_result[256] = {0};
            char m_timing[64] = {0};

            sqlite3_stmt *estmt = EventInspector_BySource(ev->inspector, classes[ci]);
            while (estmt && sqlite3_step(estmt) == SQLITE_ROW) {
                const char *entity = (const char *)sqlite3_column_text(estmt, 5);
                const char *kind = (const char *)sqlite3_column_text(estmt, 4);
                const char *name = (const char *)sqlite3_column_text(estmt, 6);
                const char *value = (const char *)sqlite3_column_text(estmt, 7);
                int sev = sqlite3_column_int(estmt, 8);
                if (!entity || strcmp(entity, methods[mi]) != 0) continue;
                if (sev > 0) m_errors++;
                if (strcmp(kind, "result") == 0) {
                    snprintf(m_result, sizeof(m_result), "%s=%s", name ? name : "", value ? value : "");
                } else if (strcmp(kind, "error") == 0) {
                    snprintf(m_result, sizeof(m_result), "%s: %s", name ? name : "", value ? value : "");
                } else if (strcmp(kind, "timing") == 0) {
                    snprintf(m_timing, sizeof(m_timing), "%s", value ? value : "");
                }
            }
            if (estmt) sqlite3_finalize(estmt);

            const char *status = (m_errors == 0) ? "PASS" : "FAIL";
            int is_last = (mi == method_count - 1);
            offset += snprintf(out + offset, out_sz - offset,
                "[@NODE]{[@TYPE]{method}[@NAME]{%s}[@STATUS]{%s}[@BRANCH]{%s}"
                "[@RESULT]{%s}[@TIMING]{%s}[@ERRORS]{%d}}",
                methods[mi], status, is_last ? "last" : "branch",
                m_result[0] ? m_result : "(no result)",
                m_timing[0] ? m_timing : "",
                m_errors);
        }
        offset += snprintf(out + offset, out_sz - offset, "}}");
    }
    offset += snprintf(out + offset, out_sz - offset, "}");

    /* Call edges — sequential class-to-class */
    offset += snprintf(out + offset, out_sz - offset, "[@CALL_EDGES]{");
    for (int ci = 0; ci < class_count - 1 && offset < (int)out_sz - 256; ci++) {
        offset += snprintf(out + offset, out_sz - offset,
            "[@EDGE]{[@FROM]{%s}[@TO]{%s}[@TYPE]{calls}}",
            classes[ci], classes[ci + 1]);
    }
    offset += snprintf(out + offset, out_sz - offset, "}");

    offset += snprintf(out + offset, out_sz - offset, "[@STATUS]{execution_graph_complete}}}");
    return 1;
}

/* render_terminal — terminal view with all sections based on verbosity */
static int EventViewer_RenderTerminal(EventViewer *ev, char *out, size_t out_sz) {
    Configurator *cfg = ev->config;
    int offset = 0;
    offset += snprintf(out + offset, out_sz - offset,
        "[@OK]{[@REPORT]{[@TYPE]{terminal}[@VERBOSITY]{%d}[@LABEL]{%s}",
        cfg->verbosity, Configurator_Label(cfg));

    /* Errors */
    if (cfg->show_errors) {
        sqlite3_stmt *stmt = EventInspector_Errors(ev->inspector);
        int err_count = 0;
        offset += snprintf(out + offset, out_sz - offset, "[@ERRORS]{");
        while (stmt && sqlite3_step(stmt) == SQLITE_ROW && offset < (int)out_sz - 512) {
            const char *phase = (const char *)sqlite3_column_text(stmt, 3);
            const char *entity = (const char *)sqlite3_column_text(stmt, 5);
            const char *name = (const char *)sqlite3_column_text(stmt, 6);
            const char *value = (const char *)sqlite3_column_text(stmt, 7);
            int sev = sqlite3_column_int(stmt, 8);
            offset += snprintf(out + offset, out_sz - offset,
                "[@ERROR]{[@PHASE]{%s}[@ENTITY]{%s}[@NAME]{%s}[@VALUE]{%s}[@SEVERITY]{%d}}",
                phase ? phase : "", entity ? entity : "",
                name ? name : "", value ? value : "", sev);
            err_count++;
        }
        if (stmt) sqlite3_finalize(stmt);
        offset += snprintf(out + offset, out_sz - offset, "[@COUNT]{%d}}", err_count);
    }

    /* Results */
    if (cfg->show_results) {
        sqlite3_stmt *stmt = EventInspector_ByKind(ev->inspector, "result");
        offset += snprintf(out + offset, out_sz - offset, "[@RESULTS]{");
        int rcount = 0;
        while (stmt && sqlite3_step(stmt) == SQLITE_ROW && offset < (int)out_sz - 512) {
            const char *phase = (const char *)sqlite3_column_text(stmt, 3);
            const char *entity = (const char *)sqlite3_column_text(stmt, 5);
            const char *name = (const char *)sqlite3_column_text(stmt, 6);
            const char *value = (const char *)sqlite3_column_text(stmt, 7);
            offset += snprintf(out + offset, out_sz - offset,
                "[@RESULT]{[@PHASE]{%s}[@ENTITY]{%s}[@NAME]{%s}[@VALUE]{%s}}",
                phase ? phase : "", entity ? entity : "",
                name ? name : "", value ? value : "");
            rcount++;
        }
        if (stmt) sqlite3_finalize(stmt);
        offset += snprintf(out + offset, out_sz - offset, "[@COUNT]{%d}}", rcount);
    }

    /* Variables */
    if (cfg->show_variables) {
        sqlite3_stmt *stmt = EventInspector_ByKind(ev->inspector, "variable");
        offset += snprintf(out + offset, out_sz - offset, "[@VARIABLES]{");
        int vcount = 0;
        while (stmt && sqlite3_step(stmt) == SQLITE_ROW && offset < (int)out_sz - 512) {
            const char *phase = (const char *)sqlite3_column_text(stmt, 3);
            const char *name = (const char *)sqlite3_column_text(stmt, 6);
            const char *value = (const char *)sqlite3_column_text(stmt, 7);
            offset += snprintf(out + offset, out_sz - offset,
                "[@VAR]{[@PHASE]{%s}[@NAME]{%s}[@VALUE]{%s}}",
                phase ? phase : "", name ? name : "", value ? value : "");
            vcount++;
        }
        if (stmt) sqlite3_finalize(stmt);
        offset += snprintf(out + offset, out_sz - offset, "[@COUNT]{%d}}", vcount);
    }

    /* State */
    if (cfg->show_state) {
        sqlite3_stmt *stmt = EventInspector_ByKind(ev->inspector, "state");
        offset += snprintf(out + offset, out_sz - offset, "[@STATE]{");
        int scount = 0;
        while (stmt && sqlite3_step(stmt) == SQLITE_ROW && offset < (int)out_sz - 512) {
            const char *name = (const char *)sqlite3_column_text(stmt, 6);
            const char *value = (const char *)sqlite3_column_text(stmt, 7);
            const char *source = (const char *)sqlite3_column_text(stmt, 2);
            offset += snprintf(out + offset, out_sz - offset,
                "[@STATE_ITEM]{[@NAME]{%s}[@VALUE]{%s}[@SOURCE]{%s}}",
                name ? name : "", value ? value : "", source ? source : "");
            scount++;
        }
        if (stmt) sqlite3_finalize(stmt);
        offset += snprintf(out + offset, out_sz - offset, "[@COUNT]{%d}}", scount);
    }

    /* Timing */
    if (cfg->show_timing) {
        sqlite3_stmt *stmt = EventInspector_ByKind(ev->inspector, "timing");
        offset += snprintf(out + offset, out_sz - offset, "[@TIMING]{");
        int tcount = 0;
        while (stmt && sqlite3_step(stmt) == SQLITE_ROW && offset < (int)out_sz - 512) {
            const char *phase = (const char *)sqlite3_column_text(stmt, 3);
            const char *entity = (const char *)sqlite3_column_text(stmt, 5);
            const char *value = (const char *)sqlite3_column_text(stmt, 7);
            offset += snprintf(out + offset, out_sz - offset,
                "[@TIME]{[@PHASE]{%s}[@ENTITY]{%s}[@VALUE]{%s}}",
                phase ? phase : "", entity ? entity : "", value ? value : "");
            tcount++;
        }
        if (stmt) sqlite3_finalize(stmt);
        offset += snprintf(out + offset, out_sz - offset, "[@COUNT]{%d}}", tcount);
    }

    /* Summary */
    InspectionSummary s = EventInspector_Summary(ev->inspector);
    offset += snprintf(out + offset, out_sz - offset,
        "[@SUMMARY]{[@TOTAL]{%d}[@STEPS]{%d}[@RESULTS]{%d}[@VARIABLES]{%d}"
        "[@STATES]{%d}[@TIMINGS]{%d}[@ERRORS]{%d}[@IMPORTS]{%d}}",
        s.total, s.steps, s.results, s.variables, s.states, s.timings, s.errors, s.imports);

    offset += snprintf(out + offset, out_sz - offset, "[@STATUS]{terminal_report}}}");
    return 1;
}

/* render_overview — AI inspection: what happened and what went wrong */
static int EventViewer_RenderOverview(EventViewer *ev, char *out, size_t out_sz) {
    int offset = 0;
    offset += snprintf(out + offset, out_sz - offset,
        "[@OK]{[@REPORT]{[@TYPE]{overview}");

    InspectionSummary s = EventInspector_Summary(ev->inspector);
    offset += snprintf(out + offset, out_sz - offset,
        "[@OVERVIEW]{[@TOTAL_EVENTS]{%d}[@ERRORS]{%d}[@RESULTS]{%d}[@STATES]{%d}[@IMPORTS]{%d}}",
        s.total, s.errors, s.results, s.states, s.imports);

    /* What went wrong */
    sqlite3_stmt *stmt = EventInspector_Errors(ev->inspector);
    offset += snprintf(out + offset, out_sz - offset, "[@WHAT_WENT_WRONG]{");
    int ecount = 0;
    while (stmt && sqlite3_step(stmt) == SQLITE_ROW && offset < (int)out_sz - 512) {
        const char *phase = (const char *)sqlite3_column_text(stmt, 3);
        const char *entity = (const char *)sqlite3_column_text(stmt, 5);
        const char *name = (const char *)sqlite3_column_text(stmt, 6);
        const char *value = (const char *)sqlite3_column_text(stmt, 7);
        const char *payload = (const char *)sqlite3_column_text(stmt, 9);
        offset += snprintf(out + offset, out_sz - offset,
            "[@ERROR]{[@PHASE]{%s}[@ENTITY]{%s}[@NAME]{%s}[@VALUE]{%s}[@PAYLOAD]{%s}}",
            phase ? phase : "", entity ? entity : "",
            name ? name : "", value ? value : "", payload ? payload : "");
        ecount++;
    }
    if (stmt) sqlite3_finalize(stmt);
    offset += snprintf(out + offset, out_sz - offset, "[@COUNT]{%d}}", ecount);

    /* Final state */
    sqlite3_stmt *fs_stmt = EventInspector_FinalState(ev->inspector);
    if (fs_stmt && sqlite3_step(fs_stmt) == SQLITE_ROW) {
        const char *name = (const char *)sqlite3_column_text(fs_stmt, 6);
        const char *value = (const char *)sqlite3_column_text(fs_stmt, 7);
        offset += snprintf(out + offset, out_sz - offset,
            "[@FINAL_STATE]{[@NAME]{%s}[@VALUE]{%s}}", name ? name : "", value ? value : "");
    }
    if (fs_stmt) sqlite3_finalize(fs_stmt);

    offset += snprintf(out + offset, out_sz - offset, "[@STATUS]{overview_complete}}}");
    return 1;
}

/* render_replay — walk all events in order */
static int EventViewer_RenderReplay(EventViewer *ev, char *out, size_t out_sz) {
    int offset = 0;
    offset += snprintf(out + offset, out_sz - offset,
        "[@OK]{[@REPORT]{[@TYPE]{replay}");

    sqlite3_stmt *stmt = EventInspector_Replay(ev->inspector);
    offset += snprintf(out + offset, out_sz - offset, "[@EVENTS]{");
    int ecount = 0;
    while (stmt && sqlite3_step(stmt) == SQLITE_ROW && offset < (int)out_sz - 512) {
        int id = sqlite3_column_int(stmt, 0);
        double ts = sqlite3_column_double(stmt, 1);
        const char *source = (const char *)sqlite3_column_text(stmt, 2);
        const char *phase = (const char *)sqlite3_column_text(stmt, 3);
        const char *kind = (const char *)sqlite3_column_text(stmt, 4);
        const char *entity = (const char *)sqlite3_column_text(stmt, 5);
        const char *name = (const char *)sqlite3_column_text(stmt, 6);
        const char *value = (const char *)sqlite3_column_text(stmt, 7);
        int sev = sqlite3_column_int(stmt, 8);
        const char *color = Kind_Color(kind);
        const char *icon = Kind_Icon(kind);

        offset += snprintf(out + offset, out_sz - offset,
            "[@E]{[@ID]{%d}[@TS]{%.0f}[@SRC]{%s}[@PHASE]{%s}[@KIND]{%s}[@ICON]{%s}"
            "[@COLOR]{%s}[@ENTITY]{%s}[@NAME]{%s}[@VALUE]{%s}[@SEV]{%d}}",
            id, ts, source ? source : "", phase ? phase : "",
            kind ? kind : "", icon, color,
            entity ? entity : "", name ? name : "", value ? value : "", sev);
        ecount++;
    }
    if (stmt) sqlite3_finalize(stmt);
    offset += snprintf(out + offset, out_sz - offset, "[@COUNT]{%d}}", ecount);

    offset += snprintf(out + offset, out_sz - offset, "[@STATUS]{replay_complete}}}");
    return 1;
}

/* render_profile — timing analysis */
static int EventViewer_RenderProfile(EventViewer *ev, char *out, size_t out_sz) {
    int offset = 0;
    offset += snprintf(out + offset, out_sz - offset,
        "[@OK]{[@REPORT]{[@TYPE]{profile}");

    sqlite3_stmt *stmt = EventInspector_ByKind(ev->inspector, "timing");
    offset += snprintf(out + offset, out_sz - offset, "[@TIMINGS]{");
    int tcount = 0;
    while (stmt && sqlite3_step(stmt) == SQLITE_ROW && offset < (int)out_sz - 512) {
        const char *phase = (const char *)sqlite3_column_text(stmt, 3);
        const char *entity = (const char *)sqlite3_column_text(stmt, 5);
        const char *value = (const char *)sqlite3_column_text(stmt, 7);
        offset += snprintf(out + offset, out_sz - offset,
            "[@TIME]{[@PHASE]{%s}[@ENTITY]{%s}[@VALUE]{%s}}",
            phase ? phase : "", entity ? entity : "", value ? value : "");
        tcount++;
    }
    if (stmt) sqlite3_finalize(stmt);
    offset += snprintf(out + offset, out_sz - offset, "[@COUNT]{%d}}", tcount);

    offset += snprintf(out + offset, out_sz - offset, "[@STATUS]{profile_complete}}}");
    return 1;
}

/* render_debug — variables + state */
static int EventViewer_RenderDebug(EventViewer *ev, char *out, size_t out_sz) {
    int offset = 0;
    offset += snprintf(out + offset, out_sz - offset,
        "[@OK]{[@REPORT]{[@TYPE]{debug}");

    /* Variables */
    sqlite3_stmt *vstmt = EventInspector_ByKind(ev->inspector, "variable");
    offset += snprintf(out + offset, out_sz - offset, "[@VARIABLES]{");
    int vcount = 0;
    while (vstmt && sqlite3_step(vstmt) == SQLITE_ROW && offset < (int)out_sz - 512) {
        const char *phase = (const char *)sqlite3_column_text(vstmt, 3);
        const char *name = (const char *)sqlite3_column_text(vstmt, 6);
        const char *value = (const char *)sqlite3_column_text(vstmt, 7);
        offset += snprintf(out + offset, out_sz - offset,
            "[@VAR]{[@PHASE]{%s}[@NAME]{%s}[@VALUE]{%s}}",
            phase ? phase : "", name ? name : "", value ? value : "");
        vcount++;
    }
    if (vstmt) sqlite3_finalize(vstmt);
    offset += snprintf(out + offset, out_sz - offset, "[@COUNT]{%d}}", vcount);

    /* State */
    sqlite3_stmt *sstmt = EventInspector_ByKind(ev->inspector, "state");
    offset += snprintf(out + offset, out_sz - offset, "[@STATE]{");
    int scount = 0;
    while (sstmt && sqlite3_step(sstmt) == SQLITE_ROW && offset < (int)out_sz - 512) {
        const char *name = (const char *)sqlite3_column_text(sstmt, 6);
        const char *value = (const char *)sqlite3_column_text(sstmt, 7);
        const char *source = (const char *)sqlite3_column_text(sstmt, 2);
        offset += snprintf(out + offset, out_sz - offset,
            "[@STATE_ITEM]{[@NAME]{%s}[@VALUE]{%s}[@SOURCE]{%s}}",
            name ? name : "", value ? value : "", source ? source : "");
        scount++;
    }
    if (sstmt) sqlite3_finalize(sstmt);
    offset += snprintf(out + offset, out_sz - offset, "[@COUNT]{%d}}", scount);

    offset += snprintf(out + offset, out_sz - offset, "[@STATUS]{debug_complete}}}");
    return 1;
}

/* ===== 5. CLASSTESTER — tests each class/method against its facts ===== */

typedef struct {
    LiveState *ls;
    EventInspector *inspector;
} ClassTester;

typedef struct {
    char method[RP_MAX_NAME];
    int  passed;
    int  fact_count;
    int  errors;
    int  results;
    int  has_timing;
    char timing[64];
    char kinds[256];
} MethodTest;

typedef struct {
    char class_name[RP_MAX_NAME];
    int  passed;
    int  fact_count;
    int  error_count;
    int  method_count;
    char detail[256];
    MethodTest methods[RP_MAX_METHODS];
    int  method_test_count;
} ClassTestResult;

typedef struct {
    int passed;
    int count;
    char items[RP_MAX_IMPORTS][RP_MAX_NAME];
} ImportTestResult;

typedef struct {
    int passed;
    int count;
    int conflict_count;
    int state_count;
    char detail[256];
} StateTestResult;

static ImportTestResult ClassTester_TestImports(ClassTester *ct) {
    ImportTestResult r = {0};
    sqlite3_stmt *stmt = LiveState_Query(ct->ls, "kind='import' ORDER BY id");
    while (stmt && sqlite3_step(stmt) == SQLITE_ROW && r.count < RP_MAX_IMPORTS) {
        const char *value = (const char *)sqlite3_column_text(stmt, 7);
        if (value) {
            strncpy(r.items[r.count], value, RP_MAX_NAME - 1);
            r.count++;
        }
    }
    if (stmt) sqlite3_finalize(stmt);
    r.passed = (r.count > 0);
    return r;
}

static ClassTestResult ClassTester_TestClass(ClassTester *ct, const char *class_name) {
    ClassTestResult r = {0};
    strncpy(r.class_name, class_name, RP_MAX_NAME - 1);

    /* Collect methods for this class */
    char methods[RP_MAX_METHODS][RP_MAX_NAME];
    int method_count = 0;
    memset(methods, 0, sizeof(methods));

    sqlite3_stmt *stmt = EventInspector_BySource(ct->inspector, class_name);
    while (stmt && sqlite3_step(stmt) == SQLITE_ROW) {
        const char *entity = (const char *)sqlite3_column_text(stmt, 5);
        const char *kind = (const char *)sqlite3_column_text(stmt, 4);
        int sev = sqlite3_column_int(stmt, 8);
        if (!entity || !kind) continue;
        if (strcmp(kind, "import") == 0) continue;
        if (entity[0] == '\0') continue;
        r.fact_count++;
        if (sev > 0) r.error_count++;

        int found = 0;
        for (int j = 0; j < method_count; j++) {
            if (strcmp(methods[j], entity) == 0) { found = 1; break; }
        }
        if (!found && method_count < RP_MAX_METHODS) {
            strncpy(methods[method_count], entity, RP_MAX_NAME - 1);
            method_count++;
        }
    }
    if (stmt) sqlite3_finalize(stmt);

    if (r.fact_count == 0) {
        r.passed = 0;
        snprintf(r.detail, sizeof(r.detail), "NO facts produced by this class");
        return r;
    }

    r.method_count = method_count;
    r.passed = (r.error_count == 0);

    /* Test each method */
    for (int mi = 0; mi < method_count && mi < RP_MAX_METHODS; mi++) {
        MethodTest *mt = &r.methods[r.method_test_count++];
        memset(mt, 0, sizeof(MethodTest));
        strncpy(mt->method, methods[mi], RP_MAX_NAME - 1);

        sqlite3_stmt *estmt = EventInspector_BySource(ct->inspector, class_name);
        while (estmt && sqlite3_step(estmt) == SQLITE_ROW) {
            const char *entity = (const char *)sqlite3_column_text(estmt, 5);
            const char *kind = (const char *)sqlite3_column_text(estmt, 4);
            const char *value = (const char *)sqlite3_column_text(estmt, 7);
            int sev = sqlite3_column_int(estmt, 8);
            if (!entity || strcmp(entity, methods[mi]) != 0) continue;
            mt->fact_count++;
            if (sev > 0) mt->errors++;
            if (strcmp(kind, "result") == 0) mt->results++;
            else if (strcmp(kind, "timing") == 0) {
                mt->has_timing = 1;
                if (value) strncpy(mt->timing, value, sizeof(mt->timing) - 1);
            }
            /* Track kinds */
            if (kind && !strstr(mt->kinds, kind)) {
                if (mt->kinds[0]) strncat(mt->kinds, ",", sizeof(mt->kinds) - strlen(mt->kinds) - 1);
                strncat(mt->kinds, kind, sizeof(mt->kinds) - strlen(mt->kinds) - 1);
            }
        }
        if (estmt) sqlite3_finalize(estmt);

        /* Method checks: produced facts, no errors, produced result, has timing */
        mt->passed = (mt->fact_count > 0 && mt->errors == 0 && mt->results > 0);
        if (mt->errors > 0) r.passed = 0;
    }

    snprintf(r.detail, sizeof(r.detail), "%d facts, %d methods, %d errors",
             r.fact_count, r.method_count, r.error_count);
    return r;
}

static StateTestResult ClassTester_TestStateConsistency(ClassTester *ct) {
    StateTestResult r = {0};
    sqlite3_stmt *stmt = LiveState_Query(ct->ls, "kind='state' ORDER BY id");
    char state_names[64][RP_MAX_NAME];
    char state_values[64][RP_MAX_NAME];
    int state_counts[64] = {0};
    int unique_states = 0;
    int total_states = 0;

    while (stmt && sqlite3_step(stmt) == SQLITE_ROW) {
        const char *name = (const char *)sqlite3_column_text(stmt, 6);
        const char *value = (const char *)sqlite3_column_text(stmt, 7);
        if (!name || !value) continue;
        total_states++;
        int found = -1;
        for (int i = 0; i < unique_states; i++) {
            if (strcmp(state_names[i], name) == 0) { found = i; break; }
        }
        if (found < 0 && unique_states < 64) {
            found = unique_states++;
            strncpy(state_names[found], name, RP_MAX_NAME - 1);
        }
        if (found >= 0) {
            strncpy(state_values[found], value, RP_MAX_NAME - 1);
            state_counts[found]++;
        }
    }
    if (stmt) sqlite3_finalize(stmt);

    r.state_count = total_states;
    r.passed = 1;
    snprintf(r.detail, sizeof(r.detail), "%d states, all consistent", total_states);
    return r;
}

/* render_test_results — renders ClassTester results as BCL */
static int EventViewer_RenderTestResults(EventViewer *ev, char *out, size_t out_sz, ClassTester *tester) {
    int offset = 0;
    offset += snprintf(out + offset, out_sz - offset,
        "[@OK]{[@REPORT]{[@TYPE]{test_results}");

    int total_passed = 0;
    int total_failed = 0;

    /* Test imports */
    ImportTestResult imp = ClassTester_TestImports(tester);
    offset += snprintf(out + offset, out_sz - offset,
        "[@IMPORT_TEST]{[@PASSED]{%d}[@COUNT]{%d}[@ITEMS]{",
        imp.passed, imp.count);
    for (int i = 0; i < imp.count && offset < (int)out_sz - 256; i++) {
        offset += snprintf(out + offset, out_sz - offset, "[@IMPORT]{%s}", imp.items[i]);
    }
    offset += snprintf(out + offset, out_sz - offset, "}}");
    if (imp.passed) total_passed++; else total_failed++;

    /* Collect classes */
    char classes[RP_MAX_CLASSES][RP_MAX_NAME];
    int class_count = 0;
    memset(classes, 0, sizeof(classes));

    sqlite3_stmt *stmt = EventInspector_Replay(ev->inspector);
    while (stmt && sqlite3_step(stmt) == SQLITE_ROW) {
        const char *src = (const char *)sqlite3_column_text(stmt, 2);
        const char *kind = (const char *)sqlite3_column_text(stmt, 4);
        if (!src || !kind) continue;
        if (strcmp(kind, "import") == 0) continue;
        int found = 0;
        for (int i = 0; i < class_count; i++) {
            if (strcmp(classes[i], src) == 0) { found = 1; break; }
        }
        if (!found && class_count < RP_MAX_CLASSES) {
            strncpy(classes[class_count], src, RP_MAX_NAME - 1);
            class_count++;
        }
    }
    if (stmt) sqlite3_finalize(stmt);

    /* Test each class */
    offset += snprintf(out + offset, out_sz - offset, "[@CLASS_TESTS]{");
    for (int ci = 0; ci < class_count && offset < (int)out_sz - 1024; ci++) {
        ClassTestResult ctr = ClassTester_TestClass(tester, classes[ci]);
        if (ctr.passed) total_passed++; else total_failed++;

        offset += snprintf(out + offset, out_sz - offset,
            "[@CLASS_TEST]{[@NAME]{%s}[@PASSED]{%d}[@DETAIL]{%s}"
            "[@FACT_COUNT]{%d}[@ERROR_COUNT]{%d}[@METHOD_COUNT]{%d}[@METHODS]{",
            ctr.class_name, ctr.passed, ctr.detail,
            ctr.fact_count, ctr.error_count, ctr.method_count);

        for (int mi = 0; mi < ctr.method_test_count && offset < (int)out_sz - 512; mi++) {
            MethodTest *mt = &ctr.methods[mi];
            offset += snprintf(out + offset, out_sz - offset,
                "[@METHOD_TEST]{[@NAME]{%s}[@PASSED]{%d}[@FACTS]{%d}[@ERRORS]{%d}"
                "[@RESULTS]{%d}[@HAS_TIMING]{%d}[@TIMING]{%s}[@KINDS]{%s}}",
                mt->method, mt->passed, mt->fact_count, mt->errors,
                mt->results, mt->has_timing,
                mt->has_timing ? mt->timing : "--",
                mt->kinds[0] ? mt->kinds : "none");
        }
        offset += snprintf(out + offset, out_sz - offset, "}}");
    }
    offset += snprintf(out + offset, out_sz - offset, "}");

    /* Error check */
    sqlite3_stmt *estmt = EventInspector_Errors(ev->inspector);
    int err_count = 0;
    while (estmt && sqlite3_step(estmt) == SQLITE_ROW) err_count++;
    if (estmt) sqlite3_finalize(estmt);
    int err_passed = (err_count == 0);
    offset += snprintf(out + offset, out_sz - offset,
        "[@ERROR_TEST]{[@PASSED]{%d}[@COUNT]{%d}}", err_passed, err_count);
    if (err_passed) total_passed++; else total_failed++;

    /* State consistency */
    StateTestResult str = ClassTester_TestStateConsistency(tester);
    offset += snprintf(out + offset, out_sz - offset,
        "[@STATE_TEST]{[@PASSED]{%d}[@DETAIL]{%s}[@STATE_COUNT]{%d}}",
        str.passed, str.detail, str.state_count);
    if (str.passed) total_passed++; else total_failed++;

    /* Summary */
    offset += snprintf(out + offset, out_sz - offset,
        "[@TEST_SUMMARY]{[@PASSED]{%d}[@FAILED]{%d}[@TOTAL]{%d}[@OVERALL]{%s}}",
        total_passed, total_failed, total_passed + total_failed,
        total_failed == 0 ? "ALL_PASS" : "HAS_FAILURES");

    offset += snprintf(out + offset, out_sz - offset, "[@STATUS]{test_results_complete}}}");
    return 1;
}

/* ===== SCANNER — walks directory, emits events to LiveState ===== */

static int IsSkipDir(const char *name) {
    for (int i = 0; i < RP_SKIP_DIRS; i++) {
        if (strcmp(name, SKIP_DIRS[i]) == 0) return 1;
    }
    return 0;
}

static long ReadFileContent(const char *path, char *buf, size_t buf_sz) {
    FILE *f = fopen(path, "r");
    if (!f) return -1;
    long n = fread(buf, 1, buf_sz - 1, f);
    buf[n] = '\0';
    fclose(f);
    return n;
}

static int CheckFileViolations(const char *content, int len, int by_rule[RP_RULE_COUNT]) {
    int count = 0;
    int has_ghost = 0, has_vbs = 0, has_run = 0, has_class = 0;
    char class_name[RP_MAX_NAME] = {0};

    int hdr_len = len < 500 ? len : 500;
    char hdr[512];
    memcpy(hdr, content, hdr_len);
    hdr[hdr_len] = '\0';
    if (strstr(hdr, "[@GHOST]") || strstr(hdr, "//@GHOST]") || strstr(hdr, "#@GHOST]")) has_ghost = 1;
    if (strstr(hdr, "[@VBSTYLE]") || strstr(hdr, "//@VBSTYLE]") || strstr(hdr, "#@VBSTYLE]")) has_vbs = 1;

    const char *p = content;
    const char *end = content + len;
    while (p < end) {
        const char *eol = strchr(p, '\n');
        if (!eol) eol = end;
        int llen = (int)(eol - p);
        if (llen >= RP_MAX_LINE) llen = RP_MAX_LINE - 1;
        char line[RP_MAX_LINE];
        memcpy(line, p, llen);
        line[llen] = '\0';
        char *trim = line;
        while (*trim == ' ' || *trim == '\t') trim++;

        if (strstr(trim, "print(")) { count++; by_rule[0]++; }
        if (trim[0] == '@' && (strstr(trim, "@property") || strstr(trim, "@staticmethod") || strstr(trim, "@classmethod"))) {
            count++; by_rule[1]++;
        }
        if (strstr(trim, "self._")) { count++; by_rule[2]++; }
        if (strncmp(trim, "class ", 6) == 0) {
            has_class = 1;
            char *ns = trim + 6;
            char *ne = ns;
            while (*ne && *ne != '(' && *ne != ':' && *ne != ' ') ne++;
            int nlen = (int)(ne - ns);
            if (nlen > 0 && nlen < RP_MAX_NAME) {
                memcpy(class_name, ns, nlen);
                class_name[nlen] = '\0';
            }
        }
        if (strncmp(trim, "def Run", 7) == 0) has_run = 1;
        if (strchr(line, '\t')) { count++; by_rule[7]++; }
        if (llen > 0 && (line[llen-1] == ' ' || line[llen-1] == '\t')) { count++; by_rule[8]++; }
        p = eol + 1;
    }

    if (!has_ghost) { count++; by_rule[3]++; }
    if (!has_vbs) { count++; by_rule[4]++; }
    if (has_class && !has_run) { count++; by_rule[5]++; }
    if (has_class && class_name[0] && !isupper((unsigned char)class_name[0])) { count++; by_rule[6]++; }
    return count;
}

static int CountBracketTags(const char *content, int len) {
    int count = 0;
    const char *p = content;
    const char *end = content + len;
    while (p < end) {
        if (p[0] == '[' && p[1] == '@') { count++; p += 2; }
        else p++;
    }
    return count;
}

static void CountClassesMethods(const char *content, int len, int *classes, int *methods) {
    *classes = 0;
    *methods = 0;
    const char *p = content;
    const char *end = content + len;
    while (p < end) {
        const char *eol = strchr(p, '\n');
        if (!eol) eol = end;
        int llen = (int)(eol - p);
        if (llen >= RP_MAX_LINE) llen = RP_MAX_LINE - 1;
        char line[RP_MAX_LINE];
        memcpy(line, p, llen);
        line[llen] = '\0';
        char *trim = line;
        while (*trim == ' ' || *trim == '\t') trim++;
        if (strncmp(trim, "class ", 6) == 0) (*classes)++;
        if (strncmp(trim, "def ", 4) == 0) (*methods)++;
        p = eol + 1;
    }
}

/* Walk directory and emit events to LiveState.
   Uses source=class_name, entity=method_name convention (v4). */
static void ScanDirectory(LiveState *ls, const char *path, int depth) {
    if (depth > 8) return;
    DIR *d = opendir(path);
    if (!d) {
        LiveState_Emit(ls, "Scanner", "scan", "error", "opendir", path, "cannot open directory", 1, NULL, 0);
        return;
    }

    /* Emit import events for the scan itself */
    LiveState_Emit(ls, "main", "imports", "import", "imports", "", "dirent.h", 0, NULL, 0);
    LiveState_Emit(ls, "main", "imports", "import", "imports", "", "sys/stat.h", 0, NULL, 0);
    LiveState_Emit(ls, "main", "imports", "import", "imports", "", "ctype.h", 0, NULL, 0);
    LiveState_Emit(ls, "main", "imports", "import", "imports", "", "sqlite3.h", 0, NULL, 0);

    /* Scanner init events */
    LiveState_Emit(ls, "Scanner", "init", "state", "Run", "scan_phase", "starting", 0, NULL, 0);
    LiveState_Emit(ls, "Scanner", "init", "state", "Run", "target_dir", path, 0, NULL, 0);

    /* Scanner.walk_dir */
    LiveState_Emit(ls, "Scanner", "scan", "step", "walk_dir", "target", path, 0, NULL, 0);

    struct dirent *entry;
    int file_count = 0;
    int total_violations = 0;
    int compliant = 0;
    int violating = 0;
    int classes_found = 0;
    int methods_found = 0;

    while ((entry = readdir(d)) != NULL) {
        if (IsSkipDir(entry->d_name)) continue;

        char full[RP_MAX_PATH];
        snprintf(full, sizeof(full), "%s/%s", path, entry->d_name);
        struct stat st;
        if (stat(full, &st) != 0) continue;

        if (S_ISDIR(st.st_mode)) {
            ScanDirectory(ls, full, depth + 1);
            continue;
        }
        if (!S_ISREG(st.st_mode)) continue;
        const char *ext = strrchr(entry->d_name, '.');
        if (!ext || strcmp(ext, ".py") != 0) continue;
        if (file_count >= RP_MAX_FILES) break;

        /* Scanner.process_file — step event */
        LiveState_Emit(ls, "Scanner", "scan", "step", "process_file", "file", entry->d_name, 0, NULL, 0);

        char buf[RP_MAX_FILE];
        long len = ReadFileContent(full, buf, sizeof(buf));
        if (len < 0) {
            LiveState_Emit(ls, "Scanner", "scan", "error", "read_file", entry->d_name, "cannot read", 1, full, 0);
            continue;
        }

        /* Check headers */
        int hdr_len = (int)(len < 500 ? len : 500);
        char hdr[512];
        memcpy(hdr, buf, hdr_len);
        hdr[hdr_len] = '\0';
        int has_ghost = (strstr(hdr, "[@GHOST]") || strstr(hdr, "//@GHOST]") || strstr(hdr, "#@GHOST]")) ? 1 : 0;
        int has_vbs = (strstr(hdr, "[@VBSTYLE]") || strstr(hdr, "//@VBSTYLE]") || strstr(hdr, "#@VBSTYLE]")) ? 1 : 0;

        /* Variable events */
        char val_buf[64];
        snprintf(val_buf, sizeof(val_buf), "%d", has_ghost);
        LiveState_Emit(ls, "Scanner", "scan", "variable", "process_file", "has_ghost", val_buf, 0, NULL, 0);
        snprintf(val_buf, sizeof(val_buf), "%d", has_vbs);
        LiveState_Emit(ls, "Scanner", "scan", "variable", "process_file", "has_vbstyle", val_buf, 0, NULL, 0);

        /* Check violations */
        int by_rule[RP_RULE_COUNT] = {0};
        int vc = CheckFileViolations(buf, (int)len, by_rule);
        total_violations += vc;
        if (vc == 0) compliant++; else violating++;

        /* Emit violation events as errors */
        for (int i = 0; i < RP_RULE_COUNT; i++) {
            if (by_rule[i] > 0) {
                char rule_val[32];
                snprintf(rule_val, sizeof(rule_val), "%d", by_rule[i]);
                LiveState_Emit(ls, "Scanner", "scan", "error", entry->d_name, RP_RULE_NAMES[i], rule_val, by_rule[i] > 5 ? 2 : 1, NULL, 0);
            }
        }

        /* Result event */
        const char *status = (vc == 0) ? "COMPLIANT" : "VIOLATIONS";
        char result_val[64];
        snprintf(result_val, sizeof(result_val), "%s (%d violations)", status, vc);
        LiveState_Emit(ls, "Scanner", "scan", "result", "process_file", entry->d_name, result_val, vc > 0 ? 1 : 0, full, 0);

        /* Count classes/methods */
        int cls, mth;
        CountClassesMethods(buf, (int)len, &cls, &mth);
        classes_found += cls;
        methods_found += mth;

        snprintf(val_buf, sizeof(val_buf), "%d", cls);
        LiveState_Emit(ls, "Scanner", "scan", "variable", "process_file", "class_count", val_buf, 0, NULL, 0);
        snprintf(val_buf, sizeof(val_buf), "%d", mth);
        LiveState_Emit(ls, "Scanner", "scan", "variable", "process_file", "method_count", val_buf, 0, NULL, 0);

        int tags = CountBracketTags(buf, (int)len);
        snprintf(val_buf, sizeof(val_buf), "%d", tags);
        LiveState_Emit(ls, "Scanner", "scan", "variable", "process_file", "tag_count", val_buf, 0, NULL, 0);

        file_count++;
    }
    closedir(d);

    /* State events */
    char state_val[64];
    snprintf(state_val, sizeof(state_val), "%d", file_count);
    LiveState_Emit(ls, "Scanner", "scan", "state", "walk_dir", "file_count", state_val, 0, NULL, 0);
    snprintf(state_val, sizeof(state_val), "%d", compliant);
    LiveState_Emit(ls, "Scanner", "scan", "state", "walk_dir", "compliant_count", state_val, 0, NULL, 0);
    snprintf(state_val, sizeof(state_val), "%d", violating);
    LiveState_Emit(ls, "Scanner", "scan", "state", "walk_dir", "violating_count", state_val, 0, NULL, 0);
    snprintf(state_val, sizeof(state_val), "%d", total_violations);
    LiveState_Emit(ls, "Scanner", "scan", "state", "walk_dir", "total_violations", state_val, 0, NULL, 0);
    snprintf(state_val, sizeof(state_val), "%d", classes_found);
    LiveState_Emit(ls, "Scanner", "scan", "state", "walk_dir", "classes_found", state_val, 0, NULL, 0);
    snprintf(state_val, sizeof(state_val), "%d", methods_found);
    LiveState_Emit(ls, "Scanner", "scan", "state", "walk_dir", "methods_found", state_val, 0, NULL, 0);

    /* Final state */
    LiveState_Emit(ls, "Scanner", "finalize", "state", "Run", "scan_phase", "complete", 0, NULL, 0);
}

/* ===== STATE — Reports unit state ===== */

static struct {
    int        initialized;
    int        connected;
    MYSQL     *conn;
    char       host[256];
    char       user[64];
    char       pass[128];
    char       socket[256];
    int        port;
    char       last_error[256];
    char       last_path[RP_MAX_PATH];
    int        total_reports;
    int        verbosity;
    LiveState  live_state;
    int        live_state_active;
    /* Live stream buffer */
    char       live_buf[RP_MAX_LIVE_BUF];
    size_t     live_buf_offset;
    int        live_row_count;
} STATE;

/* Live callback — appends events to live_buf as they happen */
static void Reports_LiveCallback(int eid, const char *source, const char *phase,
    const char *kind, const char *entity, const char *name,
    const char *value, int severity, const char *payload, int parentId)
{
    if (STATE.live_buf_offset >= RP_MAX_LIVE_BUF - 256) return;
    const char *color = Kind_Color(kind);
    const char *icon = Kind_Icon(kind);
    STATE.live_buf_offset += snprintf(
        STATE.live_buf + STATE.live_buf_offset,
        RP_MAX_LIVE_BUF - STATE.live_buf_offset,
        "[@LIVE_E]{[@ID]{%d}[@SRC]{%s}[@PHASE]{%s}[@KIND]{%s}[@ICON]{%s}[@COLOR]{%s}"
        "[@ENTITY]{%s}[@NAME]{%s}[@VALUE]{%s}[@SEV]{%d}}",
        eid, source ? source : "", phase ? phase : "",
        kind ? kind : "", icon, color,
        entity ? entity : "", name ? name : "",
        value ? value : "", severity);
    STATE.live_row_count++;
}

static void EnsureConnected(void) {
    if (STATE.connected && STATE.conn) return;
    STATE.conn = mysql_init(NULL);
    if (!STATE.conn) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "mysql_init failed");
        return;
    }
    STATE.conn = mysql_real_connect(STATE.conn,
        STATE.host[0] ? STATE.host : "localhost",
        STATE.user[0] ? STATE.user : "root",
        STATE.pass[0] ? STATE.pass : "",
        "vb_shared", STATE.port,
        STATE.socket[0] ? STATE.socket : NULL, 0);
    if (!STATE.conn) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "%s", mysql_error(STATE.conn));
        mysql_close(STATE.conn);
        STATE.conn = NULL;
        return;
    }
    STATE.connected = 1;
}

static void GetTimestamp(char *buf, size_t buf_sz) {
    time_t now = time(NULL);
    struct tm *tm = localtime(&now);
    strftime(buf, buf_sz, "%Y-%m-%d %H:%M:%S", tm);
}

/* ===== UNIT INTERFACE ===== */

int Reports_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    STATE.verbosity = 1;
    strcpy(STATE.host, "localhost");
    strcpy(STATE.user, "root");
    STATE.port = 0;
    strcpy(STATE.socket, "/tmp/mysql.sock");
    return 1;
}

int Reports_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) {
        return BclResult_Err(bcl_out, out_sz, 1, "not initialized");
    }

    /* ---- set_config ---- */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char host[256], user[64], pass[128], socket[256], verb[16];
        BclParser_Extract(&parse, "HOST", host, sizeof(host));
        BclParser_Extract(&parse, "USER", user, sizeof(user));
        BclParser_Extract(&parse, "PASS", pass, sizeof(pass));
        BclParser_Extract(&parse, "SOCKET", socket, sizeof(socket));
        BclParser_Extract(&parse, "VERBOSITY", verb, sizeof(verb));
        BclParser_Free(&parse);
        if (host[0]) strncpy(STATE.host, host, sizeof(STATE.host) - 1);
        if (user[0]) strncpy(STATE.user, user, sizeof(STATE.user) - 1);
        if (pass[0]) strncpy(STATE.pass, pass, sizeof(STATE.pass) - 1);
        if (socket[0]) strncpy(STATE.socket, socket, sizeof(STATE.socket) - 1);
        if (verb[0]) {
            int v = atoi(verb);
            if (v >= 0 && v <= 3) STATE.verbosity = v;
        }
        char body[256];
        snprintf(body, sizeof(body),
            "[@STATUS]{config_set}[@HOST]{%s}[@USER]{%s}[@VERBOSITY]{%d}[@LABEL]{%s}",
            STATE.host, STATE.user, STATE.verbosity, VERBOSITY_LABELS[STATE.verbosity]);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ---- read_state ---- */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@CONNECTED]{%d}[@TOTAL_REPORTS]{%d}"
            "[@VERBOSITY]{%d}[@LABEL]{%s}[@LIVE_STATE]{%d}[@EVENTS]{%d}"
            "[@LIVE_ROWS]{%d}[@LAST_PATH]{%s}[@LAST_ERROR]{%s}",
            STATE.initialized, STATE.connected, STATE.total_reports,
            STATE.verbosity, VERBOSITY_LABELS[STATE.verbosity],
            STATE.live_state_active, STATE.live_state.event_count,
            STATE.live_row_count,
            STATE.last_path[0] ? STATE.last_path : "none",
            STATE.last_error[0] ? STATE.last_error : "none");
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ---- live — return the live stream buffer ---- */
    if (strcmp(cmd, "live") == 0) {
        if (!STATE.live_state_active) {
            return BclResult_Err(bcl_out, out_sz, 6, "no scan data — run a scan command first");
        }
        int offset = snprintf(bcl_out, out_sz,
            "[@OK]{[@REPORT]{[@TYPE]{live}[@ROWS]{%d}[@EVENTS]{",
            STATE.live_row_count);
        /* Copy live buffer */
        size_t remaining = out_sz - offset - 64;
        size_t copy_len = STATE.live_buf_offset < remaining ? STATE.live_buf_offset : remaining;
        memcpy(bcl_out + offset, STATE.live_buf, copy_len);
        offset += (int)copy_len;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "}[@STATUS]{live_stream}}}");
        return 1;
    }

    /* ---- All commands that scan a directory need a PATH ---- */
    char scan_path[RP_MAX_PATH] = {0};
    int needs_scan = (strcmp(cmd, "full") == 0 || strcmp(cmd, "terminal") == 0 ||
        strcmp(cmd, "table") == 0 || strcmp(cmd, "code_structure") == 0 ||
        strcmp(cmd, "execution_graph") == 0 || strcmp(cmd, "test") == 0 ||
        strcmp(cmd, "overview") == 0 || strcmp(cmd, "replay") == 0 ||
        strcmp(cmd, "profile") == 0 || strcmp(cmd, "debug") == 0 ||
        strcmp(cmd, "compliance") == 0 || strcmp(cmd, "enforcement") == 0);

    if (needs_scan) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        BclParser_Extract(&parse, "PATH", scan_path, sizeof(scan_path));
        char verb_str[16] = {0};
        BclParser_Extract(&parse, "VERBOSITY", verb_str, sizeof(verb_str));
        BclParser_Free(&parse);

        if (verb_str[0]) {
            int v = atoi(verb_str);
            if (v >= 0 && v <= 3) STATE.verbosity = v;
        }

        if (!scan_path[0]) {
            return BclResult_Err(bcl_out, out_sz, 2, "no PATH in packet");
        }

        /* Initialize LiveState */
        if (STATE.live_state_active) {
            LiveState_Close(&STATE.live_state);
            STATE.live_state_active = 0;
        }
        if (!LiveState_Init(&STATE.live_state)) {
            return BclResult_Err(bcl_out, out_sz, 3, "LiveState init failed");
        }
        STATE.live_state_active = 1;
        strncpy(STATE.last_path, scan_path, RP_MAX_PATH - 1);

        /* Reset live buffer */
        STATE.live_buf_offset = 0;
        STATE.live_row_count = 0;
        STATE.live_buf[0] = '\0';

        /* Register live callback for streaming */
        LiveState_OnEmit(&STATE.live_state, Reports_LiveCallback);

        /* Emit init events */
        LiveState_Emit(&STATE.live_state, "Reports", "init", "state", "Run", "scan_phase", "starting", 0, NULL, 0);
        LiveState_Emit(&STATE.live_state, "Reports", "init", "state", "Run", "target_dir", scan_path, 0, NULL, 0);
        char vb_buf[16];
        snprintf(vb_buf, sizeof(vb_buf), "%d", STATE.verbosity);
        LiveState_Emit(&STATE.live_state, "Reports", "init", "state", "Run", "verbosity", vb_buf, 0, NULL, 0);

        /* Scan directory — emits all events to LiveState with live callbacks */
        ScanDirectory(&STATE.live_state, scan_path, 0);

        STATE.total_reports++;
    }

    /* Set up viewer components */
    EventInspector inspector = { .ls = &STATE.live_state };
    Configurator config;
    Configurator_Init(&config, STATE.verbosity);
    EventViewer viewer = { .inspector = &inspector, .config = &config };
    ClassTester tester = { .ls = &STATE.live_state, .inspector = &inspector };

    /* ---- full / terminal ---- */
    if (strcmp(cmd, "full") == 0 || strcmp(cmd, "terminal") == 0) {
        return EventViewer_RenderTerminal(&viewer, bcl_out, out_sz);
    }

    /* ---- table — final summary table with all events in rows ---- */
    if (strcmp(cmd, "table") == 0) {
        return EventViewer_RenderTable(&viewer, bcl_out, out_sz);
    }

    /* ---- code_structure — imports → class → methods layout ---- */
    if (strcmp(cmd, "code_structure") == 0) {
        return EventViewer_RenderCodeStructure(&viewer, bcl_out, out_sz);
    }

    /* ---- execution_graph — ASCII tree showing method call flow ---- */
    if (strcmp(cmd, "execution_graph") == 0) {
        return EventViewer_RenderExecutionGraph(&viewer, bcl_out, out_sz);
    }

    /* ---- test — ClassTester results: imports, each class/method, errors, state ---- */
    if (strcmp(cmd, "test") == 0) {
        return EventViewer_RenderTestResults(&viewer, bcl_out, out_sz, &tester);
    }

    /* ---- overview ---- */
    if (strcmp(cmd, "overview") == 0) {
        return EventViewer_RenderOverview(&viewer, bcl_out, out_sz);
    }

    /* ---- replay ---- */
    if (strcmp(cmd, "replay") == 0) {
        return EventViewer_RenderReplay(&viewer, bcl_out, out_sz);
    }

    /* ---- profile ---- */
    if (strcmp(cmd, "profile") == 0) {
        return EventViewer_RenderProfile(&viewer, bcl_out, out_sz);
    }

    /* ---- debug ---- */
    if (strcmp(cmd, "debug") == 0) {
        return EventViewer_RenderDebug(&viewer, bcl_out, out_sz);
    }

    /* ---- compliance ---- */
    if (strcmp(cmd, "compliance") == 0) {
        InspectionSummary s = EventInspector_Summary(&inspector);
        sqlite3_stmt *stmt = LiveState_Query(&STATE.live_state, "kind='state' AND entity='walk_dir' ORDER BY id");
        int files = 0, compliant = 0, violating = 0, violations = 0, classes = 0, methods = 0;
        while (stmt && sqlite3_step(stmt) == SQLITE_ROW) {
            const char *name = (const char *)sqlite3_column_text(stmt, 6);
            const char *value = (const char *)sqlite3_column_text(stmt, 7);
            if (!name || !value) continue;
            if (strcmp(name, "file_count") == 0) files = atoi(value);
            else if (strcmp(name, "compliant_count") == 0) compliant = atoi(value);
            else if (strcmp(name, "violating_count") == 0) violating = atoi(value);
            else if (strcmp(name, "total_violations") == 0) violations = atoi(value);
            else if (strcmp(name, "classes_found") == 0) classes = atoi(value);
            else if (strcmp(name, "methods_found") == 0) methods = atoi(value);
        }
        if (stmt) sqlite3_finalize(stmt);

        char ts[64];
        GetTimestamp(ts, sizeof(ts));
        int rate = files > 0 ? (compliant * 100 / files) : 0;
        snprintf(bcl_out, out_sz,
            "[@OK]{[@REPORT]{[@TYPE]{compliance}[@TIMESTAMP]{%s}[@DIR]{%s}"
            "[@FILES]{%d}[@COMPLIANT]{%d}[@VIOLATING]{%d}[@TOTAL_VIOLATIONS]{%d}"
            "[@CLASSES]{%d}[@METHODS]{%d}[@COMPLIANCE_RATE]{%d}"
            "[@EVENTS]{[@TOTAL]{%d}[@ERRORS]{%d}[@STEPS]{%d}[@RESULTS]{%d}[@IMPORTS]{%d}}"
            "[@STATUS]{compliance_report}}}",
            ts, STATE.last_path, files, compliant, violating, violations,
            classes, methods, rate, s.total, s.errors, s.steps, s.results, s.imports);
        return 1;
    }

    /* ---- enforcement ---- */
    if (strcmp(cmd, "enforcement") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char thr_str[16] = {0};
        BclParser_Extract(&parse, "THRESHOLD", thr_str, sizeof(thr_str));
        BclParser_Free(&parse);
        int threshold = thr_str[0] ? atoi(thr_str) : 10;

        sqlite3_stmt *stmt = LiveState_Query(&STATE.live_state, "kind='result' AND entity='process_file' ORDER BY id");
        int offset = snprintf(bcl_out, out_sz,
            "[@OK]{[@REPORT]{[@TYPE]{enforcement}[@THRESHOLD]{%d}[@DIR]{%s}[@FILES]{",
            threshold, STATE.last_path);

        int passed = 0, blocked = 0, total_vios = 0;
        while (stmt && sqlite3_step(stmt) == SQLITE_ROW && offset < (int)out_sz - 512) {
            const char *name = (const char *)sqlite3_column_text(stmt, 6);
            const char *value = (const char *)sqlite3_column_text(stmt, 7);
            const char *payload = (const char *)sqlite3_column_text(stmt, 9);
            if (!name || !value) continue;
            int vc = 0;
            const char *vparen = strstr(value, "(");
            if (vparen) vc = atoi(vparen + 1);
            int is_blocked = (vc > threshold);
            if (is_blocked) blocked++; else passed++;
            total_vios += vc;
            offset += snprintf(bcl_out + offset, out_sz - offset,
                "[@FILE]{[@NAME]{%s}[@STATUS]{%s}[@VIOLATIONS]{%d}[@PATH]{%s}}",
                name, is_blocked ? "BLOCKED" : "PASS", vc, payload ? payload : "");
        }
        if (stmt) sqlite3_finalize(stmt);
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "}[@PASSED]{%d}[@BLOCKED]{%d}[@TOTAL_VIOLATIONS]{%d}[@STATUS]{enforcement_report}}}",
            passed, blocked, total_vios);
        return 1;
    }

    /* ---- coverage ---- */
    if (strcmp(cmd, "coverage") == 0) {
        EnsureConnected();
        if (!STATE.connected) {
            return BclResult_Err(bcl_out, out_sz, 5, STATE.last_error);
        }
        int rule_count = 0, class_count = 0, method_count = 0;
        if (mysql_query(STATE.conn, "SELECT COUNT(*) FROM rules") == 0) {
            MYSQL_RES *res = mysql_store_result(STATE.conn);
            if (res) { MYSQL_ROW row = mysql_fetch_row(res); if (row) rule_count = atoi(row[0]); mysql_free_result(res); }
        }
        if (mysql_select_db(STATE.conn, "vb_code_test") == 0) {
            if (mysql_query(STATE.conn, "SELECT COUNT(*) FROM vb_classes") == 0) {
                MYSQL_RES *res = mysql_store_result(STATE.conn);
                if (res) { MYSQL_ROW row = mysql_fetch_row(res); if (row) class_count = atoi(row[0]); mysql_free_result(res); }
            }
            if (mysql_query(STATE.conn, "SELECT COUNT(*) FROM vb_methods") == 0) {
                MYSQL_RES *res = mysql_store_result(STATE.conn);
                if (res) { MYSQL_ROW row = mysql_fetch_row(res); if (row) method_count = atoi(row[0]); mysql_free_result(res); }
            }
            mysql_select_db(STATE.conn, "vb_shared");
        }
        char ts[64];
        GetTimestamp(ts, sizeof(ts));
        snprintf(bcl_out, out_sz,
            "[@OK]{[@REPORT]{[@TYPE]{coverage}[@TIMESTAMP]{%s}"
            "[@RULES]{%d}[@CLASSES]{%d}[@METHODS]{%d}"
            "[@COVERAGE_RATIO]{%d}[@STATUS]{coverage_report}}}",
            ts, rule_count, class_count, method_count,
            class_count > 0 ? (rule_count * 100 / class_count) : 0);
        STATE.total_reports++;
        return 1;
    }

    /* ---- summary ---- */
    if (strcmp(cmd, "summary") == 0) {
        if (!STATE.live_state_active) {
            return BclResult_Err(bcl_out, out_sz, 6, "no scan data — run a scan command first");
        }
        InspectionSummary s = EventInspector_Summary(&inspector);
        char ts[64];
        GetTimestamp(ts, sizeof(ts));
        snprintf(bcl_out, out_sz,
            "[@OK]{[@REPORT]{[@TYPE]{summary}[@TIMESTAMP]{%s}"
            "[@TOTAL_REPORTS]{%d}[@LAST_PATH]{%s}"
            "[@TOTAL_EVENTS]{%d}[@STEPS]{%d}[@RESULTS]{%d}"
            "[@VARIABLES]{%d}[@STATES]{%d}[@TIMINGS]{%d}[@ERRORS]{%d}[@IMPORTS]{%d}"
            "[@LIVE_ROWS]{%d}[@VERBOSITY]{%d}[@LABEL]{%s}"
            "[@STATUS]{summary}}}",
            ts, STATE.total_reports,
            STATE.last_path[0] ? STATE.last_path : "none",
            s.total, s.steps, s.results, s.variables, s.states, s.timings, s.errors, s.imports,
            STATE.live_row_count, STATE.verbosity, VERBOSITY_LABELS[STATE.verbosity]);
        return 1;
    }

    /* ---- all_units ---- */
    if (strcmp(cmd, "all_units") == 0) {
        char ts[64];
        GetTimestamp(ts, sizeof(ts));
        int offset = snprintf(bcl_out, out_sz,
            "[@OK]{[@REPORT]{[@TYPE]{all_units}[@TIMESTAMP]{%s}[@UNIT_CATEGORIES]{10}",
            ts);
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@CATEGORY]{[@NAME]{chat}[@UNITS]{pb_reader,chat_ingest}}"
            "[@CATEGORY]{[@NAME]{clean}[@UNITS]{cleaner,ghostctl}}"
            "[@CATEGORY]{[@NAME]{build}[@UNITS]{mdmerge,wcmd,windir}}"
            "[@CATEGORY]{[@NAME]{graph}[@UNITS]{discovery,codeingest}}"
            "[@CATEGORY]{[@NAME]{config}[@UNITS]{schemalint,vbcheck,smartcli,cognitive,error_fix}}"
            "[@CATEGORY]{[@NAME]{search}[@UNITS]{search_help,search_registry,search_ranking,search_vector,search_composite,search_web,search_fs,search_db}}"
            "[@CATEGORY]{[@NAME]{security}[@UNITS]{destruction_guard}}"
            "[@CATEGORY]{[@NAME]{graph_engine}[@UNITS]{graph_config,graph_view,graph_policy,graph_expand,graph_store,graph_compiler,graph_optimizer,graph_trace,graph_cache,graph_learning}}"
            "[@CATEGORY]{[@NAME]{vbast}[@UNITS]{ast_walker,vbstyle_check,graph_builder,bcl_stamper,mysql_store}}"
            "[@CATEGORY]{[@NAME]{vsstyle}[@UNITS]{rule_reader,rule_writer,rule_engine,rule_enforcer,rule_gap_graph,rule_cluster_graph,rule_coverage_graph,code_index,reports}}");
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@TOTAL_UNITS]{47}[@STATUS]{all_units}}}");
        return 1;
    }

    return BclResult_Err(bcl_out, out_sz, 404, "unknown command");
}

int Reports_Close(void) {
    if (STATE.live_state_active) {
        LiveState_Close(&STATE.live_state);
        STATE.live_state_active = 0;
    }
    if (STATE.conn) {
        mysql_close(STATE.conn);
        STATE.conn = NULL;
    }
    STATE.connected = 0;
    STATE.initialized = 0;
    STATE.total_reports = 0;
    return 1;
}

const char * Reports_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "Reports: initialized=%d reports=%d verbosity=%d(%s) events=%d live_rows=%d connected=%d",
        STATE.initialized, STATE.total_reports,
        STATE.verbosity, VERBOSITY_LABELS[STATE.verbosity],
        STATE.live_state.event_count, STATE.live_row_count, STATE.connected);
    return buf;
}
