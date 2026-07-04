/*
 * memunit_main.c - CLI entry point, config parser, Python source scanner, main orchestration
 *[@GHOST]{file_path="core/Dom_Bloodhound/memunit_main.c" date="2026-07-04" author="Devin" session_id="memunit-c" context="CLI entry point, config parser, Python source scanner, main orchestration"}
 *[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE CLI config-parser"}
 *[@FILEID]{id="memunit_main.c" domain="dom_bloodhound" authority="MemunitMain"}
 *[@SUMMARY]{summary="CLI entry point. Parses args, loads config, scans Python source, runs tests, renders views. Orchestrates LiveState, Viewer, Tester."}
 *[@CLASS]{class="MemunitMain" domain="dom_bloodhound" authority="single"}
 *[@METHOD]{methods="main,cli_parse,cli_print_usage,config_load_file,scan_python_file,config_init,config_set_verbosity,config_parse_args"}
 */

#include "memunit_debugger.h"

#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <pthread.h>
#include <time.h>
#include <ctype.h>

/* ====================================================================
 * STRING INTERNING
 * Maps strings to uint32_t IDs for compact event storage.
 * ==================================================================== */

typedef struct {
    char     str[MAX_INTERNED_STRINGS][256];
    uint32_t count;
    pthread_mutex_t lock;
} intern_table_t;

static intern_table_t g_intern_table;

uint32_t str_intern(const char *str)
{
    if (str == NULL) {
        return 0;
    }

    pthread_mutex_lock(&g_intern_table.lock);

    /* Search for existing entry */
    for (uint32_t i = 0; i < g_intern_table.count; i++) {
        if (strcmp(g_intern_table.str[i], str) == 0) {
            pthread_mutex_unlock(&g_intern_table.lock);
            return i;
        }
    }

    /* Add new entry */
    if (g_intern_table.count >= MAX_INTERNED_STRINGS) {
        pthread_mutex_unlock(&g_intern_table.lock);
        return 0;
    }

    uint32_t id = g_intern_table.count;
    strncpy(g_intern_table.str[id], str, 255);
    g_intern_table.str[id][255] = '\0';
    g_intern_table.count++;

    pthread_mutex_unlock(&g_intern_table.lock);
    return id;
}

const char *str_lookup(uint32_t id)
{
    if (id >= g_intern_table.count) {
        return "";
    }
    return g_intern_table.str[id];
}

void str_intern_shutdown(void)
{
    pthread_mutex_destroy(&g_intern_table.lock);
    g_intern_table.count = 0;
}

/* ====================================================================
 * CONFIGURATOR
 * Controls what EventViewer is allowed to show.
 * ==================================================================== */

void config_init(configurator_t *c, int verbosity)
{
    if (c == NULL) {
        return;
    }
    memset(c, 0, sizeof(configurator_t));
    config_set_verbosity(c, verbosity);
}

void config_set_verbosity(configurator_t *c, int level)
{
    if (c == NULL) {
        return;
    }
    if (level < 0) {
        level = 0;
    }
    if (level > 3) {
        level = 3;
    }

    c->verbosity = level;

    switch (level) {
    case 0:
        /* Silent: errors only, minimal structure */
        c->show_variables = 0;
        c->show_timing    = 0;
        c->show_graph     = 0;
        c->show_tests     = 1;
        c->show_structure = 0;
        c->color_enabled  = 1;
        break;

    case 1:
        /* Normal: timing, graph, tests, structure */
        c->show_variables = 0;
        c->show_timing    = 1;
        c->show_graph     = 1;
        c->show_tests     = 1;
        c->show_structure = 1;
        c->color_enabled  = 1;
        break;

    case 2:
        /* Debug: variables, all details */
        c->show_variables = 1;
        c->show_timing    = 1;
        c->show_graph     = 1;
        c->show_tests     = 1;
        c->show_structure = 1;
        c->color_enabled  = 1;
        break;

    case 3:
        /* Verbose: everything on */
        c->show_variables = 1;
        c->show_timing    = 1;
        c->show_graph     = 1;
        c->show_tests     = 1;
        c->show_structure = 1;
        c->color_enabled  = 1;
        break;

    default:
        break;
    }
}

int config_parse_args(configurator_t *c, int argc, char **argv)
{
    if (c == NULL || argv == NULL) {
        return -1;
    }

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--verbosity") == 0 && i + 1 < argc) {
            int v = atoi(argv[i + 1]);
            config_set_verbosity(c, v);
            i++;
        }
        else if (strcmp(argv[i], "--no-color") == 0) {
            c->color_enabled = 0;
        }
    }

    return 0;
}

/* ====================================================================
 * CONFIG FILE PARSER (INI-style)
 * Format: key=value, # comments, empty lines skipped
 * ==================================================================== */

static void trim_whitespace(char *str)
{
    if (str == NULL) {
        return;
    }

    /* Trim leading */
    char *start = str;
    while (*start && isspace((unsigned char)*start)) {
        start++;
    }
    if (start != str) {
        memmove(str, start, strlen(start) + 1);
    }

    /* Trim trailing */
    size_t len = strlen(str);
    while (len > 0 && isspace((unsigned char)str[len - 1])) {
        str[len - 1] = '\0';
        len--;
    }
}

static int parse_bool(const char *value)
{
    if (value == NULL) {
        return 0;
    }
    if (strcmp(value, "1") == 0 || strcmp(value, "true") == 0 ||
        strcmp(value, "True") == 0 || strcmp(value, "TRUE") == 0 ||
        strcmp(value, "yes") == 0 || strcmp(value, "on") == 0) {
        return 1;
    }
    return 0;
}

int config_load_file(configurator_t *c, const char *path)
{
    if (c == NULL || path == NULL) {
        return -1;
    }

    FILE *fp = fopen(path, "r");
    if (fp == NULL) {
        return -1;
    }

    char line[4096];
    int line_num = 0;

    while (fgets(line, sizeof(line), fp) != NULL) {
        line_num++;

        /* Strip newline */
        size_t len = strlen(line);
        while (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r')) {
            line[len - 1] = '\0';
            len--;
        }

        /* Trim whitespace */
        trim_whitespace(line);

        /* Skip empty lines */
        if (line[0] == '\0') {
            continue;
        }

        /* Skip comments */
        if (line[0] == '#') {
            continue;
        }

        /* Parse key=value */
        char *eq = strchr(line, '=');
        if (eq == NULL) {
            fprintf(stderr, "Warning: config line %d: no '=' found, skipping\n", line_num);
            continue;
        }

        /* Split into key and value */
        *eq = '\0';
        char *key = line;
        char *value = eq + 1;

        trim_whitespace(key);
        trim_whitespace(value);

        if (key[0] == '\0') {
            fprintf(stderr, "Warning: config line %d: empty key, skipping\n", line_num);
            continue;
        }

        /* Apply known keys */
        if (strcmp(key, "verbosity") == 0) {
            int v = atoi(value);
            if (v >= 0 && v <= 3) {
                config_set_verbosity(c, v);
            }
        }
        else if (strcmp(key, "color_enabled") == 0) {
            c->color_enabled = parse_bool(value);
        }
        else if (strcmp(key, "show_variables") == 0) {
            c->show_variables = parse_bool(value);
        }
        else if (strcmp(key, "show_timing") == 0) {
            c->show_timing = parse_bool(value);
        }
        else if (strcmp(key, "show_graph") == 0) {
            c->show_graph = parse_bool(value);
        }
        else if (strcmp(key, "show_tests") == 0) {
            c->show_tests = parse_bool(value);
        }
        else if (strcmp(key, "show_structure") == 0) {
            c->show_structure = parse_bool(value);
        }
        else {
            fprintf(stderr, "Warning: config line %d: unknown key '%s'\n", line_num, key);
        }
    }

    fclose(fp);
    return 0;
}

/* ====================================================================
 * CLI ARGUMENT PARSING
 * Usage: memunit_debugger [options] <source_file.py>
 * ==================================================================== */

void cli_print_usage(const char *prog)
{
    if (prog == NULL) {
        prog = "memunit_debugger";
    }

    fprintf(stderr, "\n");
    fprintf(stderr, "Usage: %s [options] <source_file.py>\n", prog);
    fprintf(stderr, "\n");
    fprintf(stderr, "Options:\n");
    fprintf(stderr, "  --verbosity N      Set verbosity (0=silent, 1=normal, 2=debug, 3=verbose)\n");
    fprintf(stderr, "  --test             Run tests only\n");
    fprintf(stderr, "  --table            Show final summary table\n");
    fprintf(stderr, "  --overview         Show AI inspection overview\n");
    fprintf(stderr, "  --replay           Show replay inspection\n");
    fprintf(stderr, "  --profile          Show profiler inspection\n");
    fprintf(stderr, "  --debug            Show debugger inspection\n");
    fprintf(stderr, "  --all              Show all inspections + tests\n");
    fprintf(stderr, "  --sqlite           Enable SQLite archival (default: off)\n");
    fprintf(stderr, "  --commit-interval N  SQLite batch commit interval (default: 500)\n");
    fprintf(stderr, "  --refresh-hz N     Terminal refresh rate (default: 10)\n");
    fprintf(stderr, "  --config FILE      Load config from file\n");
    fprintf(stderr, "  --no-color         Disable ANSI colors\n");
    fprintf(stderr, "  --help, -h         Show this help\n");
    fprintf(stderr, "\n");
    fprintf(stderr, "Verbosity levels:\n");
    fprintf(stderr, "  0  Silent   - errors only, minimal output\n");
    fprintf(stderr, "  1  Normal   - timing, graph, tests, structure (default)\n");
    fprintf(stderr, "  2  Debug    - variables, state, all details\n");
    fprintf(stderr, "  3  Verbose  - everything\n");
    fprintf(stderr, "\n");
}

int cli_parse(cli_args_t *args, int argc, char **argv)
{
    if (args == NULL || argv == NULL) {
        return -1;
    }

    /* Set defaults */
    memset(args, 0, sizeof(cli_args_t));
    args->verbosity       = 1;
    args->commit_interval = DEFAULT_COMMIT_INTERVAL;
    args->refresh_hz      = DEFAULT_REFRESH_HZ;
    args->sqlite_enabled  = 0;
    args->color_enabled   = 1;
    args->source_file     = NULL;
    args->config_file     = NULL;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            cli_print_usage(argv[0]);
            return 1;
        }
        else if (strcmp(argv[i], "--verbosity") == 0 && i + 1 < argc) {
            args->verbosity = atoi(argv[i + 1]);
            if (args->verbosity < 0) args->verbosity = 0;
            if (args->verbosity > 3) args->verbosity = 3;
            i++;
        }
        else if (strcmp(argv[i], "--test") == 0) {
            args->run_tests = 1;
        }
        else if (strcmp(argv[i], "--table") == 0) {
            args->show_table = 1;
        }
        else if (strcmp(argv[i], "--overview") == 0) {
            args->show_overview = 1;
        }
        else if (strcmp(argv[i], "--replay") == 0) {
            args->show_replay = 1;
        }
        else if (strcmp(argv[i], "--profile") == 0) {
            args->show_profile = 1;
        }
        else if (strcmp(argv[i], "--debug") == 0) {
            args->show_debug = 1;
        }
        else if (strcmp(argv[i], "--all") == 0) {
            args->show_all = 1;
        }
        else if (strcmp(argv[i], "--sqlite") == 0) {
            args->sqlite_enabled = 1;
        }
        else if (strcmp(argv[i], "--commit-interval") == 0 && i + 1 < argc) {
            args->commit_interval = atoi(argv[i + 1]);
            if (args->commit_interval < 1) args->commit_interval = 1;
            i++;
        }
        else if (strcmp(argv[i], "--refresh-hz") == 0 && i + 1 < argc) {
            args->refresh_hz = atoi(argv[i + 1]);
            if (args->refresh_hz < 1) args->refresh_hz = 1;
            i++;
        }
        else if (strcmp(argv[i], "--config") == 0 && i + 1 < argc) {
            args->config_file = argv[i + 1];
            i++;
        }
        else if (strcmp(argv[i], "--no-color") == 0) {
            args->color_enabled = 0;
        }
        else if (argv[i][0] == '-' && argv[i][1] == '-') {
            fprintf(stderr, "Warning: unknown option '%s'\n", argv[i]);
        }
        else if (argv[i][0] == '-' && argv[i][1] != '\0') {
            fprintf(stderr, "Warning: unknown option '%s'\n", argv[i]);
        }
        else {
            /* Positional argument - source file (last one wins) */
            args->source_file = argv[i];
        }
    }

    return 0;
}

/* ====================================================================
 * EVENT BUS (lock-free SPSC ring buffer)
 * ==================================================================== */

int event_bus_init(event_bus_t *bus, size_t capacity)
{
    if (bus == NULL || capacity == 0) {
        return -1;
    }

    /* Round up to power of 2 */
    size_t cap = 1;
    while (cap < capacity) {
        cap <<= 1;
    }

    bus->events = (event_t *)calloc(cap, sizeof(event_t));
    if (bus->events == NULL) {
        return -1;
    }

    bus->capacity = cap;
    bus->mask = cap - 1;
    bus->head = 0;
    bus->tail = 0;
    pthread_mutex_init(&bus->lock, NULL);

    return 0;
}

void event_bus_shutdown(event_bus_t *bus)
{
    if (bus == NULL) {
        return;
    }
    free(bus->events);
    bus->events = NULL;
    pthread_mutex_destroy(&bus->lock);
}

int event_bus_push(event_bus_t *bus, const event_t *evt)
{
    if (bus == NULL || evt == NULL) {
        return -1;
    }

    pthread_mutex_lock(&bus->lock);

    size_t next_head = (bus->head + 1) & bus->mask;
    if (next_head == bus->tail) {
        /* Buffer full */
        pthread_mutex_unlock(&bus->lock);
        return -1;
    }

    bus->events[bus->head] = *evt;
    bus->head = next_head;

    pthread_mutex_unlock(&bus->lock);
    return 0;
}

int event_bus_pop(event_bus_t *bus, event_t *out)
{
    if (bus == NULL || out == NULL) {
        return -1;
    }

    pthread_mutex_lock(&bus->lock);

    if (bus->tail == bus->head) {
        /* Buffer empty */
        pthread_mutex_unlock(&bus->lock);
        return -1;
    }

    *out = bus->events[bus->tail];
    bus->tail = (bus->tail + 1) & bus->mask;

    pthread_mutex_unlock(&bus->lock);
    return 0;
}

size_t event_bus_count(event_bus_t *bus)
{
    if (bus == NULL) {
        return 0;
    }
    return (bus->head - bus->tail) & bus->mask;
}

/* ====================================================================
 * LIVE STATE (RAM-first blackboard + optional SQLite)
 * ==================================================================== */

int live_state_init(live_state_t *ls, int sqlite_enabled, int commit_interval)
{
    if (ls == NULL) {
        return -1;
    }

    memset(ls, 0, sizeof(live_state_t));

    ls->event_capacity = MAX_EVENTS;
    ls->events = (event_t *)calloc(ls->event_capacity, sizeof(event_t));
    if (ls->events == NULL) {
        return -1;
    }

    ls->event_count = 0;
    ls->next_id = 1;
    ls->sqlite_enabled = sqlite_enabled;
    ls->commit_interval = commit_interval;
    ls->pending_writes = 0;
    ls->db = NULL;
    ls->insert_stmt = NULL;

    pthread_mutex_init(&ls->lock, NULL);
    pthread_mutex_init(&g_intern_table.lock, NULL);
    g_intern_table.count = 0;

    /* Reserve ID 0 as empty string */
    str_intern("");

    /* Optional SQLite */
    if (sqlite_enabled) {
        int rc = sqlite3_open(":memory:", &ls->db);
        if (rc == SQLITE_OK) {
            const char *schema =
                "CREATE TABLE IF NOT EXISTS event ("
                "  id INTEGER PRIMARY KEY,"
                "  timestamp_ns INTEGER,"
                "  source TEXT,"
                "  phase INTEGER,"
                "  kind INTEGER,"
                "  entity TEXT,"
                "  name TEXT,"
                "  value TEXT,"
                "  severity INTEGER,"
                "  payload TEXT,"
                "  parent_id INTEGER"
                ");";
            sqlite3_exec(ls->db, schema, NULL, NULL, NULL);

            const char *sql =
                "INSERT INTO event (id, timestamp_ns, source, phase, kind, entity, "
                "name, value, severity, payload, parent_id) "
                "VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11)";
            sqlite3_prepare_v2(ls->db, sql, -1, &ls->insert_stmt, NULL);
        }
    }

    return 0;
}

void live_state_shutdown(live_state_t *ls)
{
    if (ls == NULL) {
        return;
    }

    if (ls->insert_stmt) {
        sqlite3_finalize(ls->insert_stmt);
        ls->insert_stmt = NULL;
    }
    if (ls->db) {
        sqlite3_close(ls->db);
        ls->db = NULL;
    }

    free(ls->events);
    ls->events = NULL;
    ls->event_count = 0;

    pthread_mutex_destroy(&ls->lock);
    str_intern_shutdown();
}

uint64_t live_state_emit(live_state_t *ls, uint32_t source, uint32_t phase,
                         uint32_t kind, uint32_t entity,
                         const char *name, const char *value,
                         uint32_t severity, const char *payload,
                         uint64_t parent_id)
{
    if (ls == NULL) {
        return 0;
    }

    pthread_mutex_lock(&ls->lock);

    if (ls->event_count >= ls->event_capacity) {
        pthread_mutex_unlock(&ls->lock);
        return 0;
    }

    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    uint64_t ns = (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;

    event_t *ev = &ls->events[ls->event_count];
    ev->id = ls->next_id++;
    ev->timestamp_ns = ns;
    ev->source = source;
    ev->phase = phase;
    ev->kind = kind;
    ev->entity = entity;
    ev->name = name;
    ev->value = value;
    ev->severity = severity;
    ev->payload = payload;
    ev->parent_id = parent_id;

    ls->event_count++;

    /* Update cached counters */
    if (kind < 16) {
        ls->count_by_kind[kind]++;
    }
    if (phase < 8) {
        ls->count_by_phase[phase]++;
    }
    if (severity < 8) {
        ls->count_by_severity[severity]++;
    }
    if (severity >= SEV_ERROR) {
        ls->error_count++;
    }
    ls->total_events++;

    /* Optional SQLite archival */
    if (ls->sqlite_enabled && ls->insert_stmt && ls->db) {
        sqlite3_bind_int64(ls->insert_stmt, 1, (sqlite3_int64)ev->id);
        sqlite3_bind_int64(ls->insert_stmt, 2, (sqlite3_int64)ns);
        sqlite3_bind_text(ls->insert_stmt, 3, str_lookup(source), -1, SQLITE_TRANSIENT);
        sqlite3_bind_int(ls->insert_stmt, 4, (int)phase);
        sqlite3_bind_int(ls->insert_stmt, 5, (int)kind);
        sqlite3_bind_text(ls->insert_stmt, 6, str_lookup(entity), -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(ls->insert_stmt, 7, name ? name : "", -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(ls->insert_stmt, 8, value ? value : "", -1, SQLITE_TRANSIENT);
        sqlite3_bind_int(ls->insert_stmt, 9, (int)severity);
        sqlite3_bind_text(ls->insert_stmt, 10, payload ? payload : NULL, -1, SQLITE_TRANSIENT);
        sqlite3_bind_int64(ls->insert_stmt, 11, (sqlite3_int64)parent_id);

        sqlite3_step(ls->insert_stmt);
        sqlite3_reset(ls->insert_stmt);

        ls->pending_writes++;
        if (ls->pending_writes >= ls->commit_interval) {
            sqlite3_exec(ls->db, "COMMIT; BEGIN;", NULL, NULL, NULL);
            ls->pending_writes = 0;
        }
    }

    uint64_t id = ev->id;
    pthread_mutex_unlock(&ls->lock);
    return id;
}

int live_state_flush(live_state_t *ls)
{
    if (ls == NULL || ls->db == NULL) {
        return -1;
    }
    sqlite3_exec(ls->db, "COMMIT; BEGIN;", NULL, NULL, NULL);
    ls->pending_writes = 0;
    return 0;
}

/* Query functions (from RAM) */
event_t *live_state_query_kind(live_state_t *ls, uint32_t kind, size_t *count)
{
    if (ls == NULL || count == NULL) {
        if (count) *count = 0;
        return NULL;
    }

    /* Return pointer to first matching event and count total */
    *count = 0;
    event_t *first = NULL;

    for (size_t i = 0; i < ls->event_count; i++) {
        if (ls->events[i].kind == kind) {
            if (first == NULL) {
                first = &ls->events[i];
            }
            (*count)++;
        }
    }

    return first;
}

event_t *live_state_query_severity_above(live_state_t *ls, uint32_t level, size_t *count)
{
    if (ls == NULL || count == NULL) {
        if (count) *count = 0;
        return NULL;
    }

    *count = 0;
    event_t *first = NULL;

    for (size_t i = 0; i < ls->event_count; i++) {
        if (ls->events[i].severity > level) {
            if (first == NULL) {
                first = &ls->events[i];
            }
            (*count)++;
        }
    }

    return first;
}

event_t *live_state_query_phase(live_state_t *ls, uint32_t phase, size_t *count)
{
    if (ls == NULL || count == NULL) {
        if (count) *count = 0;
        return NULL;
    }

    *count = 0;
    event_t *first = NULL;

    for (size_t i = 0; i < ls->event_count; i++) {
        if (ls->events[i].phase == phase) {
            if (first == NULL) {
                first = &ls->events[i];
            }
            (*count)++;
        }
    }

    return first;
}

event_t *live_state_query_entity(live_state_t *ls, uint32_t entity, size_t *count)
{
    if (ls == NULL || count == NULL) {
        if (count) *count = 0;
        return NULL;
    }

    *count = 0;
    event_t *first = NULL;

    for (size_t i = 0; i < ls->event_count; i++) {
        if (ls->events[i].entity == entity) {
            if (first == NULL) {
                first = &ls->events[i];
            }
            (*count)++;
        }
    }

    return first;
}

/* Stats (O(1) from cached counters) */
uint64_t live_state_count_kind(live_state_t *ls, uint32_t kind)
{
    if (ls == NULL || kind >= 16) {
        return 0;
    }
    return ls->count_by_kind[kind];
}

uint64_t live_state_count_severity(live_state_t *ls, uint32_t level)
{
    if (ls == NULL || level >= 8) {
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

uint64_t live_state_error_count(live_state_t *ls)
{
    if (ls == NULL) {
        return 0;
    }
    return ls->error_count;
}

/* ====================================================================
 * EVENT VIEWER (ANSI terminal, worker thread)
 * ==================================================================== */

/* ANSI color helpers */
static const char *color_for_kind(uint32_t kind)
{
    switch (kind) {
    case EVENT_STEP:    return "\033[36m";   /* cyan */
    case EVENT_RESULT:  return "\033[32m";   /* green */
    case EVENT_ERROR:   return "\033[31m";   /* red */
    case EVENT_STATE:   return "\033[35m";   /* magenta */
    case EVENT_IMPORT:  return "\033[36m";   /* cyan */
    case EVENT_CALL:    return "\033[1m";    /* bold */
    case EVENT_VAR:     return "\033[33m";   /* yellow */
    case EVENT_TIMING:  return "\033[34m";   /* blue */
    default:            return "";
    }
}

static const char *kind_name(uint32_t kind)
{
    switch (kind) {
    case EVENT_STEP:    return "step";
    case EVENT_RESULT:  return "result";
    case EVENT_ERROR:   return "error";
    case EVENT_STATE:   return "state";
    case EVENT_IMPORT:  return "import";
    case EVENT_CALL:    return "call";
    case EVENT_RETURN:  return "return";
    case EVENT_VAR:     return "variable";
    case EVENT_TIMING:  return "timing";
    case EVENT_FIX:     return "fix";
    default:            return "unknown";
    }
}

static void *viewer_worker(void *arg)
{
    event_viewer_t *v = (event_viewer_t *)arg;
    if (v == NULL) {
        return NULL;
    }

    while (v->running) {
        usleep(1000000 / (v->refresh_hz > 0 ? v->refresh_hz : 10));
    }

    return NULL;
}

int viewer_init(event_viewer_t *v, live_state_t *ls, int verbosity, int refresh_hz)
{
    if (v == NULL) {
        return -1;
    }

    memset(v, 0, sizeof(event_viewer_t));
    v->state = ls;
    v->verbosity = verbosity;
    v->refresh_hz = refresh_hz > 0 ? refresh_hz : DEFAULT_REFRESH_HZ;
    v->running = 0;
    v->color_enabled = 1;

    /* Allocate render queue */
    v->render_queue = (event_bus_t *)calloc(1, sizeof(event_bus_t));
    if (v->render_queue == NULL) {
        return -1;
    }
    if (event_bus_init(v->render_queue, RING_BUFFER_CAPACITY) != 0) {
        free(v->render_queue);
        v->render_queue = NULL;
        return -1;
    }

    return 0;
}

void viewer_shutdown(event_viewer_t *v)
{
    if (v == NULL) {
        return;
    }
    viewer_stop(v);
    if (v->render_queue) {
        event_bus_shutdown(v->render_queue);
        free(v->render_queue);
        v->render_queue = NULL;
    }
}

int viewer_start(event_viewer_t *v)
{
    if (v == NULL) {
        return -1;
    }
    v->running = 1;
    if (pthread_create(&v->worker_tid, NULL, viewer_worker, v) != 0) {
        v->running = 0;
        return -1;
    }
    return 0;
}

void viewer_stop(event_viewer_t *v)
{
    if (v == NULL || !v->running) {
        return;
    }
    v->running = 0;
    pthread_join(v->worker_tid, NULL);
}

void viewer_push_event(event_viewer_t *v, const event_t *evt)
{
    if (v == NULL || evt == NULL || v->render_queue == NULL) {
        return;
    }
    event_bus_push(v->render_queue, evt);
}

void viewer_render_table(event_viewer_t *v)
{
    if (v == NULL || v->state == NULL) {
        return;
    }

    live_state_t *ls = v->state;
    const char *bold = v->color_enabled ? "\033[1m" : "";
    const char *reset = v->color_enabled ? "\033[0m" : "";

    printf("\n");
    printf("%s=== Summary Table ===%s\n", bold, reset);
    printf("  %-18s %llu\n", "imports",  (unsigned long long)live_state_count_kind(ls, EVENT_IMPORT));
    printf("  %-18s %llu\n", "classes (state)", (unsigned long long)live_state_count_kind(ls, EVENT_STATE));
    printf("  %-18s %llu\n", "methods (call)", (unsigned long long)live_state_count_kind(ls, EVENT_CALL));
    printf("  %-18s %llu\n", "steps", (unsigned long long)live_state_count_kind(ls, EVENT_STEP));
    printf("  %-18s %llu\n", "errors", (unsigned long long)live_state_error_count(ls));
    printf("  %-18s %llu\n", "total", (unsigned long long)live_state_total(ls));
    printf("\n");
}

void viewer_render_summary(event_viewer_t *v)
{
    if (v == NULL || v->state == NULL) {
        return;
    }

    live_state_t *ls = v->state;
    const char *bold = v->color_enabled ? "\033[1m" : "";
    const char *reset = v->color_enabled ? "\033[0m" : "";
    const char *green = v->color_enabled ? "\033[32m" : "";
    const char *redc = v->color_enabled ? "\033[31m" : "";

    uint64_t total = live_state_total(ls);
    uint64_t errors = live_state_error_count(ls);
    uint64_t imports = live_state_count_kind(ls, EVENT_IMPORT);
    uint64_t states = live_state_count_kind(ls, EVENT_STATE);

    printf("\n%s=== AI Inspection Overview ===%s\n", bold, reset);
    printf("Total events:     %llu\n", (unsigned long long)total);
    printf("Imports found:    %llu\n", (unsigned long long)imports);
    printf("Classes found:    %llu\n", (unsigned long long)states);
    printf("Errors detected:  %s%llu%s\n",
           errors > 0 ? redc : green,
           (unsigned long long)errors, reset);

    if (errors > 0) {
        printf("\n%sError events:%s\n", redc, reset);
        for (size_t i = 0; i < ls->event_count; i++) {
            if (ls->events[i].severity >= SEV_ERROR) {
                printf("  [%llu] %s/%s: %s\n",
                       (unsigned long long)ls->events[i].id,
                       str_lookup(ls->events[i].source),
                       str_lookup(ls->events[i].entity),
                       ls->events[i].value ? ls->events[i].value : "");
            }
        }
    }
    printf("\n");
}

void viewer_render_errors(event_viewer_t *v)
{
    if (v == NULL || v->state == NULL) {
        return;
    }

    live_state_t *ls = v->state;
    const char *bold = v->color_enabled ? "\033[1m" : "";
    const char *reset = v->color_enabled ? "\033[0m" : "";

    printf("\n%s=== Replay Inspection ===%s\n", bold, reset);
    printf("%-6s %-14s %-12s %-12s %-20s %s\n",
           "ID", "Source", "Phase", "Kind", "Entity", "Value");
    printf("%s\n", "------ ------------ ------------ ------------ -------------------- ----------");

    for (size_t i = 0; i < ls->event_count; i++) {
        event_t *e = &ls->events[i];
        const char *c = v->color_enabled ? color_for_kind(e->kind) : "";
        const char *r = v->color_enabled ? reset : "";

        const char *phase_str = "";
        switch (e->phase) {
        case PHASE_INIT:    phase_str = "init"; break;
        case PHASE_RUN:     phase_str = "run"; break;
        case PHASE_TEST:    phase_str = "test"; break;
        case PHASE_CLEANUP: phase_str = "cleanup"; break;
        default:            phase_str = "?"; break;
        }

        printf("%s%-6llu %-14s %-12s %-12s %-20s %s%s\n",
               c,
               (unsigned long long)e->id,
               str_lookup(e->source),
               phase_str,
               kind_name(e->kind),
               str_lookup(e->entity),
               e->value ? e->value : "",
               r);
    }
    printf("\n");
}

void viewer_render_tests(event_viewer_t *v)
{
    if (v == NULL || v->state == NULL) {
        return;
    }

    live_state_t *ls = v->state;
    const char *bold = v->color_enabled ? "\033[1m" : "";
    const char *yellow = v->color_enabled ? "\033[33m" : "";
    const char *magenta = v->color_enabled ? "\033[35m" : "";
    const char *reset = v->color_enabled ? "\033[0m" : "";

    printf("\n%s=== Debugger Inspection ===%s\n", bold, reset);

    /* Variables */
    printf("\n%sVariables:%s\n", yellow, reset);
    size_t var_count = 0;
    for (size_t i = 0; i < ls->event_count; i++) {
        if (ls->events[i].kind == EVENT_VAR) {
            printf("  [%llu] %s/%s: %s = %s\n",
                   (unsigned long long)ls->events[i].id,
                   str_lookup(ls->events[i].source),
                   str_lookup(ls->events[i].entity),
                   ls->events[i].name ? ls->events[i].name : "",
                   ls->events[i].value ? ls->events[i].value : "");
            var_count++;
        }
    }
    if (var_count == 0) {
        printf("  (none)\n");
    }

    /* States */
    printf("\n%sStates:%s\n", magenta, reset);
    size_t state_count = 0;
    for (size_t i = 0; i < ls->event_count; i++) {
        if (ls->events[i].kind == EVENT_STATE) {
            printf("  [%llu] %s/%s: %s = %s\n",
                   (unsigned long long)ls->events[i].id,
                   str_lookup(ls->events[i].source),
                   str_lookup(ls->events[i].entity),
                   ls->events[i].name ? ls->events[i].name : "",
                   ls->events[i].value ? ls->events[i].value : "");
            state_count++;
        }
    }
    if (state_count == 0) {
        printf("  (none)\n");
    }

    /* Timing */
    printf("\n%sTiming:%s\n", v->color_enabled ? "\033[34m" : "", reset);
    size_t timing_count = 0;
    double total_ms = 0.0;
    for (size_t i = 0; i < ls->event_count; i++) {
        if (ls->events[i].kind == EVENT_TIMING) {
            printf("  [%llu] %s/%s: %s\n",
                   (unsigned long long)ls->events[i].id,
                   str_lookup(ls->events[i].source),
                   str_lookup(ls->events[i].entity),
                   ls->events[i].value ? ls->events[i].value : "");
            if (ls->events[i].value) {
                total_ms += atof(ls->events[i].value);
            }
            timing_count++;
        }
    }
    if (timing_count > 0) {
        printf("  Total: %.2fms across %zu timing events\n", total_ms, timing_count);
    } else {
        printf("  (none)\n");
    }
    printf("\n");
}

/* ====================================================================
 * CLASS TESTER
 * ==================================================================== */

int tester_init(class_tester_t *t, live_state_t *ls)
{
    if (t == NULL) {
        return -1;
    }
    memset(t, 0, sizeof(class_tester_t));
    t->state = ls;
    return 0;
}

int tester_test_imports(class_tester_t *t)
{
    if (t == NULL || t->state == NULL) {
        return 0;
    }

    uint64_t import_count = live_state_count_kind(t->state, EVENT_IMPORT);
    t->tests_run++;

    if (import_count > 0) {
        t->tests_passed++;
        printf("  [PASS] imports: %llu imports found\n",
               (unsigned long long)import_count);
        return 1;
    } else {
        t->tests_failed++;
        printf("  [FAIL] imports: NO imports found\n");
        return 0;
    }
}

int tester_test_class(class_tester_t *t, const char *class_name)
{
    if (t == NULL || t->state == NULL || class_name == NULL) {
        return 0;
    }

    uint32_t source_id = str_intern(class_name);
    int fact_count = 0;
    int error_count = 0;
    int method_count = 0;

    /* Track unique methods */
    uint32_t methods[512];
    int method_idx = 0;

    for (size_t i = 0; i < t->state->event_count; i++) {
        event_t *e = &t->state->events[i];
        if (e->source != source_id) {
            continue;
        }
        fact_count++;
        if (e->severity >= SEV_ERROR) {
            error_count++;
        }

        /* Track unique entities (methods) */
        int found = 0;
        for (int m = 0; m < method_idx; m++) {
            if (methods[m] == e->entity) {
                found = 1;
                break;
            }
        }
        if (!found && method_idx < 512) {
            methods[method_idx] = e->entity;
            method_idx++;
        }
    }
    method_count = method_idx;

    t->tests_run++;

    int passed = (fact_count > 0) && (error_count == 0);
    if (passed) {
        t->tests_passed++;
    } else {
        t->tests_failed++;
    }

    printf("  [%s] %s: %d facts, %d methods, %d errors\n",
           passed ? "PASS" : "FAIL",
           class_name, fact_count, method_count, error_count);

    return passed ? 1 : 0;
}

int tester_test_all(class_tester_t *t)
{
    if (t == NULL || t->state == NULL) {
        return 0;
    }

    printf("\n=== Test Results ===\n");

    /* Test imports */
    tester_test_imports(t);

    /* Collect unique sources (classes) */
    uint32_t classes[MAX_CLASS_NAME];
    int class_count = get_unique_classes(t->state, classes, MAX_CLASS_NAME);

    /* Test each class */
    for (int c = 0; c < class_count; c++) {
        const char *name = str_lookup(classes[c]);
        if (name && name[0] != '\0') {
            tester_test_class(t, name);
        }
    }

    /* Error check */
    tester_test_errors(t);

    printf("\nTotal tests: %d, Passed: %d, Failed: %d\n",
           t->tests_run, t->tests_passed, t->tests_failed);

    return t->tests_failed == 0 ? 1 : 0;
}

int tester_test_errors(class_tester_t *t)
{
    if (t == NULL || t->state == NULL) {
        return 0;
    }

    uint64_t errors = live_state_error_count(t->state);
    t->tests_run++;

    if (errors == 0) {
        t->tests_passed++;
        printf("  [PASS] error_check: no errors\n");
        return 1;
    } else {
        t->tests_failed++;
        printf("  [FAIL] error_check: %llu errors found\n",
               (unsigned long long)errors);
        return 0;
    }
}

/* ====================================================================
 * HELPER FUNCTIONS (for ClassTester)
 * ==================================================================== */

int get_unique_classes(live_state_t *ls, uint32_t out[], int max_classes)
{
    if (ls == NULL || out == NULL || max_classes <= 0) {
        return 0;
    }

    int count = 0;
    for (size_t i = 0; i < ls->event_count; i++) {
        if (ls->events[i].kind == EVENT_IMPORT) {
            continue;
        }

        uint32_t src = ls->events[i].source;
        int found = 0;
        for (int j = 0; j < count; j++) {
            if (out[j] == src) {
                found = 1;
                break;
            }
        }
        if (!found && count < max_classes) {
            out[count] = src;
            count++;
        }
    }

    return count;
}

int has_event_kind(live_state_t *ls, uint32_t source, uint32_t kind)
{
    if (ls == NULL) {
        return 0;
    }

    for (size_t i = 0; i < ls->event_count; i++) {
        if (ls->events[i].source == source && ls->events[i].kind == kind) {
            return 1;
        }
    }
    return 0;
}

int has_error_for(live_state_t *ls, uint32_t entity)
{
    if (ls == NULL) {
        return 0;
    }

    for (size_t i = 0; i < ls->event_count; i++) {
        if (ls->events[i].entity == entity && ls->events[i].severity >= SEV_ERROR) {
            return 1;
        }
    }
    return 0;
}

/* ====================================================================
 * PYTHON SOURCE FILE SCANNER
 * Simple line-by-line tokenizer to extract structure events.
 * ==================================================================== */

/* Check if line starts with a prefix (after optional leading whitespace) */
static int starts_with(const char *line, const char *prefix)
{
    while (*line && isspace((unsigned char)*line)) {
        line++;
    }
    return strncmp(line, prefix, strlen(prefix)) == 0;
}

/* Extract the first token after a prefix (e.g., class name after "class ") */
static void extract_first_token(const char *line, const char *prefix,
                                char *out, size_t out_sz)
{
    if (out == NULL || out_sz == 0) {
        return;
    }
    out[0] = '\0';

    while (*line && isspace((unsigned char)*line)) {
        line++;
    }
    line += strlen(prefix);
    while (*line && isspace((unsigned char)*line)) {
        line++;
    }

    size_t i = 0;
    while (*line && !isspace((unsigned char)*line) &&
           *line != '(' && *line != ':' && *line != ',' &&
           *line != ';' && i < out_sz - 1) {
        out[i] = *line;
        i++;
        line++;
    }
    out[i] = '\0';
}

/* Extract the module name from an import line.
   "import os" -> "os"
   "from rich.console import Console" -> "rich.console" */
static void extract_import_module(const char *line, char *out, size_t out_sz)
{
    if (out == NULL || out_sz == 0) {
        return;
    }
    out[0] = '\0';

    while (*line && isspace((unsigned char)*line)) {
        line++;
    }

    if (strncmp(line, "from ", 5) == 0) {
        line += 5;
        while (*line && isspace((unsigned char)*line)) {
            line++;
        }
        size_t i = 0;
        while (*line && !isspace((unsigned char)*line) &&
               *line != '(' && *line != ':' && i < out_sz - 1) {
            out[i] = *line;
            i++;
            line++;
        }
        out[i] = '\0';
    }
    else if (strncmp(line, "import ", 7) == 0) {
        line += 7;
        while (*line && isspace((unsigned char)*line)) {
            line++;
        }
        size_t i = 0;
        while (*line && !isspace((unsigned char)*line) &&
               *line != ',' && *line != ';' && i < out_sz - 1) {
            out[i] = *line;
            i++;
            line++;
        }
        out[i] = '\0';
    }
}

/* Extract method name from "def X(...):" or "    def X(...):" */
static void extract_method_name(const char *line, char *out, size_t out_sz)
{
    if (out == NULL || out_sz == 0) {
        return;
    }
    out[0] = '\0';

    while (*line && isspace((unsigned char)*line)) {
        line++;
    }

    if (strncmp(line, "def ", 4) != 0) {
        return;
    }
    line += 4;

    while (*line && isspace((unsigned char)*line)) {
        line++;
    }

    size_t i = 0;
    while (*line && *line != '(' && !isspace((unsigned char)*line) &&
           i < out_sz - 1) {
        out[i] = *line;
        i++;
        line++;
    }
    out[i] = '\0';
}

int scan_python_file(live_state_t *ls, const char *path)
{
    if (ls == NULL || path == NULL) {
        return -1;
    }

    FILE *fp = fopen(path, "r");
    if (fp == NULL) {
        fprintf(stderr, "Error: cannot open source file '%s'\n", path);
        return -1;
    }

    char line[4096];
    int line_num = 0;
    int events_emitted = 0;
    char current_class[256] = "";
    char name_buf[256];
    char value_buf[1024];

    uint32_t source_scanner = str_intern("scanner");

    while (fgets(line, sizeof(line), fp) != NULL) {
        line_num++;

        /* Strip newline */
        size_t len = strlen(line);
        while (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r')) {
            line[len - 1] = '\0';
            len--;
        }

        /* Trim and check for empty/comment */
        char tmp[4096];
        strncpy(tmp, line, sizeof(tmp) - 1);
        tmp[sizeof(tmp) - 1] = '\0';
        trim_whitespace(tmp);
        if (tmp[0] == '\0' || tmp[0] == '#') {
            /* Still check for emit() in comment lines? No, skip. */
            continue;
        }

        /* Check for import statements */
        if (starts_with(line, "import ") || starts_with(line, "from ")) {
            extract_import_module(line, name_buf, sizeof(name_buf));
            if (name_buf[0] != '\0') {
                snprintf(value_buf, sizeof(value_buf), "line %d: %s",
                         line_num, name_buf);
                uint32_t entity_id = str_intern(name_buf);
                live_state_emit(ls, source_scanner, PHASE_RUN, EVENT_IMPORT,
                                entity_id, "import", value_buf,
                                SEV_INFO, NULL, 0);
                events_emitted++;
            }
        }
        /* Check for class definitions */
        else if (starts_with(line, "class ")) {
            extract_first_token(line, "class ", name_buf, sizeof(name_buf));
            if (name_buf[0] != '\0') {
                strncpy(current_class, name_buf, sizeof(current_class) - 1);
                current_class[sizeof(current_class) - 1] = '\0';

                snprintf(value_buf, sizeof(value_buf), "line %d: class %s",
                         line_num, name_buf);
                uint32_t entity_id = str_intern(name_buf);
                live_state_emit(ls, source_scanner, PHASE_RUN, EVENT_STATE,
                                entity_id, "class", value_buf,
                                SEV_INFO, NULL, 0);
                events_emitted++;
            }
        }
        /* Check for method/function definitions */
        else if (starts_with(line, "def ") || starts_with(line, "    def ") ||
                 starts_with(line, "\tdef ")) {
            extract_method_name(line, name_buf, sizeof(name_buf));
            if (name_buf[0] != '\0') {
                char entity_buf[512];
                if (current_class[0] != '\0') {
                    snprintf(entity_buf, sizeof(entity_buf), "%s.%s",
                             current_class, name_buf);
                } else {
                    snprintf(entity_buf, sizeof(entity_buf), "%s", name_buf);
                }

                snprintf(value_buf, sizeof(value_buf), "line %d: def %s",
                         line_num, entity_buf);
                uint32_t entity_id = str_intern(entity_buf);
                live_state_emit(ls, source_scanner, PHASE_RUN, EVENT_CALL,
                                entity_id, "method", value_buf,
                                SEV_INFO, NULL, 0);
                events_emitted++;
            }
        }

        /* Check for emit() calls anywhere in the line */
        if (strstr(line, "emit(") != NULL) {
            snprintf(value_buf, sizeof(value_buf), "line %d: emit() call",
                     line_num);
            uint32_t entity_id = str_intern("emit_call");
            live_state_emit(ls, source_scanner, PHASE_RUN, EVENT_STEP,
                            entity_id, "emit", value_buf,
                            SEV_DEBUG, NULL, 0);
            events_emitted++;
        }
    }

    fclose(fp);
    return events_emitted;
}

/* ====================================================================
 * MAIN FUNCTION
 * ==================================================================== */

int main(int argc, char *argv[])
{
    struct timespec ts_start;
    clock_gettime(CLOCK_MONOTONIC, &ts_start);

    /* 1. Print banner */
    printf("memunit_debugger v1.0.0 - C Enhanced Memory Unit Debugger\n");
    printf("\n");

    /* 2. Parse CLI args */
    cli_args_t args;
    int parse_result = cli_parse(&args, argc, argv);

    if (parse_result == 1) {
        /* --help was requested, usage already printed */
        return 0;
    }

    if (parse_result < 0) {
        cli_print_usage(argv[0]);
        return 1;
    }

    /* 3. If no source file and no flags, print usage and exit 1 */
    if (args.source_file == NULL && !args.show_all && !args.run_tests &&
        !args.show_table && !args.show_overview && !args.show_replay &&
        !args.show_profile && !args.show_debug) {
        fprintf(stderr, "Error: no source file specified\n");
        cli_print_usage(argv[0]);
        return 1;
    }

    /* 4. Initialize Configurator */
    configurator_t config;
    config_init(&config, args.verbosity);

    /* Apply --no-color from CLI */
    if (!args.color_enabled) {
        config.color_enabled = 0;
    }

    /* Parse additional config from args */
    config_parse_args(&config, argc, argv);

    /* 5. Load config file if specified */
    if (args.config_file != NULL) {
        int rc = config_load_file(&config, args.config_file);
        if (rc != 0) {
            fprintf(stderr, "Warning: config file '%s' not found, using defaults\n",
                    args.config_file);
        } else {
            if (config.verbosity >= 2) {
                printf("Config loaded from: %s\n", args.config_file);
            }
        }
    }

    /* 6. Initialize LiveState */
    live_state_t ls;
    if (live_state_init(&ls, args.sqlite_enabled, args.commit_interval) != 0) {
        fprintf(stderr, "Error: failed to initialize LiveState\n");
        return 1;
    }

    /* 7. Initialize EventViewer */
    event_viewer_t viewer;
    if (viewer_init(&viewer, &ls, args.verbosity, args.refresh_hz) != 0) {
        fprintf(stderr, "Warning: viewer init failed, continuing without live view\n");
    }

    /* Start viewer worker thread */
    viewer_start(&viewer);

    /* 8. If source file specified, scan it */
    int scan_events = 0;
    if (args.source_file != NULL) {
        if (config.verbosity >= 1) {
            printf("Scanning source file: %s\n", args.source_file);
        }

        scan_events = scan_python_file(&ls, args.source_file);
        if (scan_events < 0) {
            fprintf(stderr, "Error: failed to scan source file\n");
            viewer_shutdown(&viewer);
            live_state_shutdown(&ls);
            return 1;
        }

        if (config.verbosity >= 1) {
            printf("Scan complete: %d events emitted\n", scan_events);
        }

        /* Push events to viewer render queue */
        for (size_t i = 0; i < ls.event_count; i++) {
            viewer_push_event(&viewer, &ls.events[i]);
        }
    }

    printf("\n");

    /* 9. Run ClassTester if --test or --all */
    class_tester_t tester;
    tester_init(&tester, &ls);

    if (args.run_tests || args.show_all) {
        if (config.verbosity >= 1) {
            printf("Running ClassTester...\n");
        }
        tester_test_all(&tester);
    }

    /* 10. Render requested views */
    if (args.show_all) {
        viewer_render_summary(&viewer);
        viewer_render_errors(&viewer);
        viewer_render_tests(&viewer);
        viewer_render_table(&viewer);
    }
    else {
        if (args.show_table) {
            viewer_render_table(&viewer);
        }
        if (args.show_overview) {
            viewer_render_summary(&viewer);
        }
        if (args.show_replay) {
            viewer_render_errors(&viewer);
        }
        if (args.show_profile) {
            viewer_render_tests(&viewer);
        }
        if (args.show_debug) {
            viewer_render_tests(&viewer);
        }
        if (args.run_tests) {
            /* Tests already run above */
        }
    }

    /* 11. Stop viewer */
    viewer_shutdown(&viewer);

    /* 12. Print final summary */
    uint64_t total_events = live_state_total(&ls);
    uint64_t total_errors = live_state_error_count(&ls);

    struct timespec ts_end;
    clock_gettime(CLOCK_MONOTONIC, &ts_end);
    double elapsed_ms = (ts_end.tv_sec - ts_start.tv_sec) * 1000.0 +
                        (ts_end.tv_nsec - ts_start.tv_nsec) / 1000000.0;

    const char *bold = config.color_enabled ? "\033[1m" : "";
    const char *reset = config.color_enabled ? "\033[0m" : "";

    printf("%s=== Final Summary ===%s\n", bold, reset);
    printf("Total events: %llu, Errors: %llu, Time: %.2fms\n",
           (unsigned long long)total_events,
           (unsigned long long)total_errors,
           elapsed_ms);

    /* 13. Shutdown LiveState */
    live_state_shutdown(&ls);

    /* 14. Return 0 on success, 1 if errors were found */
    return (total_errors > 0) ? 1 : 0;
}
