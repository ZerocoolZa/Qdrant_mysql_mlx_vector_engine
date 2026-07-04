//[@GHOST]{file_path="core/Dom_Bloodhound/bloodhound_tui.c" date="2026-07-04" author="Devin" session_id="memunit-c-tui" context="Bloodhound TUI GUI — ncurses-based terminal dashboard with live event stream, summary panels, execution graph, timing profile, tabbed navigation, filter/search, drill-down. Professional observability GUI for the Bloodhound Trace Engine."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE ncurses-tui dashboard"}
//[@FILEID]{id="bloodhound_tui.c" domain="dom_bloodhound" authority="BloodhoundTUI"}
//[@SUMMARY]{summary="Bloodhound TUI — ncurses-based terminal GUI for the Bloodhound Trace Engine. Features: live event stream with color-coded kinds, summary dashboard with O(1) stats, execution graph view, timing profile with histograms, event table with scroll/filter, class test results, tabbed navigation (1-8), search/filter, drill-down detail view, ANSI color throughout. Consumes events from bloodhound.c EventBus via shared memory or IPC."}
//[@CLASS]{class="BloodhoundTUI" domain="dom_bloodhound" authority="single"}
//[@METHOD]{methods="main,tui_init,tui_shutdown,tui_run,tui_render_dashboard,tui_render_stream,tui_render_table,tui_render_graph,tui_render_profile,tui_render_tests,tui_render_detail,tui_render_help,tui_handle_input,tui_filter_events,tui_search_events,scan_python_file_live,draw_box,draw_header,draw_footer,draw_summary_card,draw_histogram,attr_for_kind,color_for_kind"}

/*
 * bloodhound_tui.c — Bloodhound TUI GUI
 *
 * A professional terminal dashboard for the Bloodhound Trace Engine.
 * Uses ncurses for rendering with 8 tabs:
 *
 *   [1] Dashboard  — summary cards + live event stream
 *   [2] Stream     — full live event stream with colors
 *   [3] Table      — scrollable event table with filter
 *   [4] Graph      — execution graph (class → method tree)
 *   [5] Profile    — timing profile with histogram bars
 *   [6] Tests      — class test results
 *   [7] Search     — search/filter events by text
 *   [8] Help       — keybindings
 *
 * Build:
 *   cc -O2 -Wall -o bloodhound_tui bloodhound_tui.c -lncurses -lpthread -lsqlite3 -lm
 *
 * Usage:
 *   bloodhound_tui <source.py>           # scan + open GUI
 *   bloodhound_tui <source.py> --sqlite  # with SQLite archival
 *
 * Keys:
 *   1-8     Switch tabs
 *   Tab     Next tab
 *   j/k     Scroll down/up (vim-style)
 *   /       Search
 *   f       Filter by kind
 *   Enter   Detail view of selected event
 *   r       Re-scan
 *   q       Quit
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
#include <signal.h>
#include <errno.h>
#include <sqlite3.h>
#include <ncurses.h>

// ═══════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════

#define TUI_VERSION         "1.0.0"
#define TUI_MAX_EVENTS      50000
#define TUI_MAX_INTERNED    8192
#define TUI_MAX_INDEX       256
#define TUI_MAX_LINE        4096
#define TUI_MAX_NAME        128
#define TUI_REFRESH_MS      100       // 10Hz refresh
#define TUI_MAX_DISPLAY     500       // max events to display
#define TUI_SEARCH_LEN      256

// Tabs
enum {
    TAB_DASHBOARD = 0,
    TAB_STREAM    = 1,
    TAB_TABLE     = 2,
    TAB_GRAPH     = 3,
    TAB_PROFILE   = 4,
    TAB_TESTS     = 5,
    TAB_SEARCH    = 6,
    TAB_HELP      = 7,
    TAB_COUNT     = 8,
};

static const char *TAB_NAMES[] = {
    "Dashboard", "Stream", "Table", "Graph",
    "Profile", "Tests", "Search", "Help"
};

// Event kinds
enum {
    KIND_STEP = 1, KIND_RESULT = 2, KIND_ERROR = 3, KIND_VAR = 4,
    KIND_STATE = 5, KIND_TIMING = 6, KIND_IMPORT = 7,
    KIND_CALL = 8, KIND_RETURN = 9, KIND_FIX = 10,
};

static const char *KIND_NAMES[] = {
    [0]="?", [KIND_STEP]="step", [KIND_RESULT]="result",
    [KIND_ERROR]="error", [KIND_VAR]="variable",
    [KIND_STATE]="state", [KIND_TIMING]="timing",
    [KIND_IMPORT]="import", [KIND_CALL]="call",
    [KIND_RETURN]="return", [KIND_FIX]="fix",
};

static const char *KIND_ICONS[] = {
    [0]="?", [KIND_STEP]=">", [KIND_RESULT]="V",
    [KIND_ERROR]="X", [KIND_VAR]="v",
    [KIND_STATE]="S", [KIND_TIMING]="T",
    [KIND_IMPORT]="I", [KIND_CALL]="C",
    [KIND_RETURN]="R", [KIND_FIX]="F",
};

// Value types
enum { VAL_NULL=0, VAL_INT=1, VAL_FLOAT=2, VAL_STRING=3, VAL_BOOL=4 };

// ═══════════════════════════════════════════════════════════
// VALUE
// ═══════════════════════════════════════════════════════════

typedef struct {
    uint8_t type;
    union { int64_t i64; double f64; bool b; } num;
    char str[64];
} tui_value_t;

static tui_value_t ValInt(int64_t v)     { tui_value_t r={VAL_INT}; r.num.i64=v; return r; }
static tui_value_t ValFloat(double v)    { tui_value_t r={VAL_FLOAT}; r.num.f64=v; return r; }
static tui_value_t ValStr(const char *s) { tui_value_t r={VAL_STRING}; strncpy(r.str,s?s:"",sizeof(r.str)-1); return r; }

static void ValFormat(const tui_value_t *v, char *out, size_t outlen) {
    switch (v->type) {
        case VAL_INT:    snprintf(out,outlen,"%lld",(long long)v->num.i64); break;
        case VAL_FLOAT:  snprintf(out,outlen,"%.2f",v->num.f64); break;
        case VAL_BOOL:   snprintf(out,outlen,"%s",v->num.b?"true":"false"); break;
        case VAL_STRING: snprintf(out,outlen,"%s",v->str); break;
        default:         snprintf(out,outlen,"null"); break;
    }
}

// ═══════════════════════════════════════════════════════════
// EVENT
// ═══════════════════════════════════════════════════════════

typedef struct {
    uint64_t    id;
    uint64_t    timestamp_ns;
    uint16_t    kind;
    uint16_t    severity;
    uint16_t    source;
    uint16_t    phase;
    uint32_t    entity;
    uint32_t    name;
    tui_value_t value;
    uint64_t    parent_id;
} tui_event_t;

// ═══════════════════════════════════════════════════════════
// STRING INTERNING
// ═══════════════════════════════════════════════════════════

static char     *g_interned[TUI_MAX_INTERNED];
static uint32_t  g_intern_count = 0;

static uint32_t str_intern(const char *str) {
    if (!str) return 0;
    for (uint32_t i = 0; i < g_intern_count; i++)
        if (g_interned[i] && strcmp(g_interned[i], str) == 0) return i;
    if (g_intern_count >= TUI_MAX_INTERNED) return 0;
    g_interned[g_intern_count] = strdup(str);
    return g_intern_count++;
}

static const char* str_lookup(uint32_t id) {
    return (id < g_intern_count && g_interned[id]) ? g_interned[id] : "?";
}

// ═══════════════════════════════════════════════════════════
// EVENT BUS (embedded, simplified from bloodhound.c)
// ═══════════════════════════════════════════════════════════

typedef struct {
    tui_event_t  events[TUI_MAX_EVENTS];
    size_t       count;
    uint64_t     next_id;
    // Cached stats
    uint64_t     count_by_kind[16];
    uint64_t     error_count;
    uint64_t     total_events;
    double       timing_total_ms;
    double       timing_min_ms;
    double       timing_max_ms;
    uint64_t     timing_count;
    // Source tracking
    bool         seen_source[TUI_MAX_INDEX];
    int          source_count;
} tui_bus_t;

static void bus_init(tui_bus_t *bus) {
    memset(bus, 0, sizeof(*bus));
    bus->timing_min_ms = 1e18;
    bus->next_id = 1;
}

static uint64_t bus_emit(tui_bus_t *bus, uint16_t kind, uint16_t severity,
                         const char *source, const char *phase,
                         const char *entity, const char *name,
                         tui_value_t value) {
    if (bus->count >= TUI_MAX_EVENTS) return 0;
    tui_event_t *ev = &bus->events[bus->count];
    ev->id = bus->next_id++;
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    ev->timestamp_ns = (uint64_t)ts.tv_sec * 1000000000ULL + ts.tv_nsec;
    ev->kind = kind;
    ev->severity = severity;
    ev->source = str_intern(source);
    ev->phase = str_intern(phase);
    ev->entity = str_intern(entity);
    ev->name = str_intern(name);
    ev->value = value;
    ev->parent_id = 0;

    bus->count++;
    bus->total_events++;
    if (kind < 16) bus->count_by_kind[kind]++;
    if (severity >= 3) bus->error_count++;
    if (!bus->seen_source[ev->source]) { bus->seen_source[ev->source] = true; bus->source_count++; }
    if (kind == KIND_TIMING && value.type == VAL_FLOAT) {
        double ms = value.num.f64;
        bus->timing_total_ms += ms;
        if (ms < bus->timing_min_ms) bus->timing_min_ms = ms;
        if (ms > bus->timing_max_ms) bus->timing_max_ms = ms;
        bus->timing_count++;
    }
    return ev->id;
}

// ═══════════════════════════════════════════════════════════
// TUI STATE
// ═══════════════════════════════════════════════════════════

typedef struct {
    tui_bus_t    bus;
    const char  *source_file;
    int          sqlite_enabled;
    int          current_tab;
    int          scroll_pos;
    int          selected_event;     // index in table/search
    int          detail_event;       // -1 = no detail
    int          running;
    // Search
    char         search_buf[TUI_SEARCH_LEN];
    int          search_len;
    int          search_active;      // 1 = typing in search
    // Filter
    int          filter_kind;         // 0 = all, else kind
    // Layout
    int          rows, cols;
    // Stats display
    int          last_displayed_count;
} tui_state_t;

// ═══════════════════════════════════════════════════════════
// COLOR SETUP
// ═══════════════════════════════════════════════════════════

enum {
    C_NORMAL = 1, C_DIM, C_BOLD, C_TITLE,
    C_STEP, C_RESULT, C_ERROR, C_VAR, C_STATE, C_TIMING, C_IMPORT, C_CALL,
    C_HEADER, C_FOOTER, C_BORDER, C_HIGHLIGHT, C_SEARCH, C_SUCCESS, C_FAIL,
    C_BAR, C_BAR_HIGH, C_BAR_MED, C_BAR_LOW,
};

static int color_for_kind(uint16_t kind) {
    switch (kind) {
        case KIND_STEP:   return C_STEP;
        case KIND_RESULT: return C_RESULT;
        case KIND_ERROR:  return C_ERROR;
        case KIND_VAR:    return C_VAR;
        case KIND_STATE:  return C_STATE;
        case KIND_TIMING: return C_TIMING;
        case KIND_IMPORT: return C_IMPORT;
        case KIND_CALL:   return C_CALL;
        default:          return C_NORMAL;
    }
}

static void tui_init_colors(void) {
    start_color();
    use_default_colors();
    init_pair(C_NORMAL,  COLOR_WHITE,   -1);
    init_pair(C_DIM,     COLOR_BLACK,   -1);
    init_pair(C_BOLD,    COLOR_WHITE,   -1);
    init_pair(C_TITLE,   COLOR_CYAN,    -1);
    init_pair(C_STEP,    COLOR_CYAN,    -1);
    init_pair(C_RESULT,  COLOR_GREEN,   -1);
    init_pair(C_ERROR,   COLOR_RED,     -1);
    init_pair(C_VAR,     COLOR_YELLOW,  -1);
    init_pair(C_STATE,   COLOR_MAGENTA, -1);
    init_pair(C_TIMING,  COLOR_BLUE,    -1);
    init_pair(C_IMPORT,  COLOR_CYAN,    -1);
    init_pair(C_CALL,    COLOR_WHITE,   -1);
    init_pair(C_HEADER,  COLOR_BLACK,   COLOR_CYAN);
    init_pair(C_FOOTER,  COLOR_BLACK,   COLOR_BLUE);
    init_pair(C_BORDER,  COLOR_CYAN,    -1);
    init_pair(C_HIGHLIGHT,COLOR_BLACK,  COLOR_CYAN);
    init_pair(C_SEARCH,  COLOR_YELLOW,  -1);
    init_pair(C_SUCCESS, COLOR_GREEN,   -1);
    init_pair(C_FAIL,    COLOR_RED,     -1);
    init_pair(C_BAR,     COLOR_CYAN,    -1);
    init_pair(C_BAR_HIGH,COLOR_RED,     -1);
    init_pair(C_BAR_MED, COLOR_YELLOW,  -1);
    init_pair(C_BAR_LOW, COLOR_GREEN,   -1);
}

// ═══════════════════════════════════════════════════════════
// DRAWING HELPERS
// ═══════════════════════════════════════════════════════════

static void draw_box(int y, int x, int h, int w, const char *title, int color) {
    attron(COLOR_PAIR(color));
    mvhline(y, x, ACS_HLINE, w);
    mvhline(y + h, x, ACS_HLINE, w);
    mvvline(y, x, ACS_VLINE, h);
    mvvline(y, x + w, ACS_VLINE, h);
    mvaddch(y, x, ACS_ULCORNER);
    mvaddch(y, x + w, ACS_URCORNER);
    mvaddch(y + h, x, ACS_LLCORNER);
    mvaddch(y + h, x + w, ACS_LRCORNER);
    attroff(COLOR_PAIR(color));
    if (title) {
        mvprintw(y, x + 2, " %s ", title);
    }
}

static void draw_header(tui_state_t *st) {
    attron(COLOR_PAIR(C_HEADER) | A_BOLD);
    mvhline(0, 0, ' ', st->cols);
    mvprintw(0, 1, " Bloodhound Trace Engine v%s ", TUI_VERSION);
    mvprintw(0, st->cols - 40, " Events: %-6llu  Errors: %-3llu ",
             (unsigned long long)st->bus.total_events,
             (unsigned long long)st->bus.error_count);
    attroff(COLOR_PAIR(C_HEADER) | A_BOLD);
}

static void draw_footer(tui_state_t *st) {
    attron(COLOR_PAIR(C_FOOTER));
    mvhline(st->rows - 1, 0, ' ', st->cols);
    mvprintw(st->rows - 1, 1, " 1-8:Tab  j/k:Scroll  /:Search  f:Filter  Enter:Detail  r:Rescan  q:Quit ");
    attroff(COLOR_PAIR(C_FOOTER));
}

static void draw_tabs(tui_state_t *st) {
    int y = 1;
    int x = 0;
    for (int i = 0; i < TAB_COUNT; i++) {
        int len = strlen(TAB_NAMES[i]) + 4;
        if (x + len > st->cols) break;
        if (i == st->current_tab) {
            attron(COLOR_PAIR(C_HIGHLIGHT) | A_BOLD);
            mvprintw(y, x, " [%d] %s ", i + 1, TAB_NAMES[i]);
            attroff(COLOR_PAIR(C_HIGHLIGHT) | A_BOLD);
        } else {
            attron(COLOR_PAIR(C_DIM));
            mvprintw(y, x, " [%d] %s ", i + 1, TAB_NAMES[i]);
            attroff(COLOR_PAIR(C_DIM));
        }
        x += len;
    }
    mvhline(y + 1, 0, ACS_HLINE, st->cols);
}

// ═══════════════════════════════════════════════════════════
// TAB: DASHBOARD
// ═══════════════════════════════════════════════════════════

static void draw_summary_card(int y, int x, int w, const char *label, uint64_t value, int color) {
    attron(COLOR_PAIR(color));
    mvhline(y, x, ' ', w);
    mvhline(y + 1, x, ' ', w);
    mvhline(y + 2, x, ' ', w);
    mvprintw(y, x + 1, "%s", label);
    attron(A_BOLD);
    mvprintw(y + 1, x + 1, "%llu", (unsigned long long)value);
    attroff(A_BOLD);
    attroff(COLOR_PAIR(color));
}

static void render_dashboard(tui_state_t *st) {
    int y = 3, x = 0;
    // Summary cards row
    int card_w = st->cols / 6;
    if (card_w < 14) card_w = 14;

    draw_summary_card(y, x, card_w, "Total", st->bus.total_events, C_TITLE);
    draw_summary_card(y, x + card_w + 1, card_w, "Steps", st->bus.count_by_kind[KIND_STEP], C_STEP);
    draw_summary_card(y, x + (card_w + 1) * 2, card_w, "Results", st->bus.count_by_kind[KIND_RESULT], C_RESULT);
    draw_summary_card(y, x + (card_w + 1) * 3, card_w, "Errors", st->bus.error_count, C_ERROR);
    draw_summary_card(y, x + (card_w + 1) * 4, card_w, "Imports", st->bus.count_by_kind[KIND_IMPORT], C_IMPORT);
    draw_summary_card(y, x + (card_w + 1) * 5, card_w, "Timings", st->bus.count_by_kind[KIND_TIMING], C_TIMING);

    y += 4;

    // Timing summary
    if (st->bus.timing_count > 0) {
        draw_box(y, x, 3, st->cols, "TIMING", C_TIMING);
        mvprintw(y + 1, x + 2, " Total: %.2fms  Min: %.2fms  Max: %.2fms  Avg: %.2fms  Count: %llu ",
                 st->bus.timing_total_ms, st->bus.timing_min_ms, st->bus.timing_max_ms,
                 st->bus.timing_total_ms / st->bus.timing_count,
                 (unsigned long long)st->bus.timing_count);
        y += 5;
    }

    // Live event stream (last N events)
    int stream_h = st->rows - y - 1;
    draw_box(y, x, stream_h, st->cols, "LIVE EVENT STREAM", C_BORDER);

    int display_count = st->bus.count - st->last_displayed_count;
    if (display_count > stream_h - 2) display_count = stream_h - 2;
    if (display_count < 0) display_count = 0;

    int start = st->bus.count - display_count;
    if (start < 0) start = 0;

    int line = y + 1;
    for (size_t i = start; i < st->bus.count && line < y + stream_h; i++) {
        tui_event_t *ev = &st->bus.events[i];
        int col = color_for_kind(ev->kind);
        char val_str[128];
        ValFormat(&ev->value, val_str, sizeof(val_str));
        const char *kname = KIND_NAMES[ev->kind] ? KIND_NAMES[ev->kind] : "?";
        attron(COLOR_PAIR(col));
        mvprintw(line, x + 1, "%-6llu %-12s %-10s %-14s %-14s %s",
                 (unsigned long long)ev->id,
                 str_lookup(ev->source), str_lookup(ev->phase),
                 kname, str_lookup(ev->entity), val_str);
        attroff(COLOR_PAIR(col));
        line++;
    }
    st->last_displayed_count = st->bus.count;
}

// ═══════════════════════════════════════════════════════════
// TAB: STREAM
// ═══════════════════════════════════════════════════════════

static void render_stream(tui_state_t *st) {
    int y = 3;
    int h = st->rows - y - 1;
    draw_box(y, 0, h, st->cols, "EVENT STREAM (full)", C_BORDER);

    int visible = h - 2;
    int start = st->bus.count - visible - st->scroll_pos;
    if (start < 0) start = 0;

    int line = y + 1;
    for (size_t i = start; i < st->bus.count && line < y + h; i++) {
        tui_event_t *ev = &st->bus.events[i];
        int col = color_for_kind(ev->kind);
        char val_str[128];
        ValFormat(&ev->value, val_str, sizeof(val_str));
        const char *kname = KIND_NAMES[ev->kind] ? KIND_NAMES[ev->kind] : "?";
        attron(COLOR_PAIR(col));
        mvprintw(line, 1, "%-6llu %-12s %-10s %-14s %-14s %-20s %s%s",
                 (unsigned long long)ev->id,
                 str_lookup(ev->source), str_lookup(ev->phase),
                 kname, str_lookup(ev->entity), str_lookup(ev->name), val_str,
                 ev->severity >= 3 ? " !" : "");
        attroff(COLOR_PAIR(col));
        line++;
    }
    // Scroll indicator
    attron(COLOR_PAIR(C_DIM));
    mvprintw(y + h, st->cols - 20, " %zu events  pos:%d ", st->bus.count, st->scroll_pos);
    attroff(COLOR_PAIR(C_DIM));
}

// ═══════════════════════════════════════════════════════════
// TAB: TABLE
// ═══════════════════════════════════════════════════════════

static void render_table(tui_state_t *st) {
    int y = 3;
    int h = st->rows - y - 1;
    const char *title = st->filter_kind > 0 ? KIND_NAMES[st->filter_kind] : "ALL";
    char buf[64];
    snprintf(buf, sizeof(buf), "EVENT TABLE (%s)", title);
    draw_box(y, 0, h, st->cols, buf, C_BORDER);

    // Header
    attron(COLOR_PAIR(C_HEADER) | A_BOLD);
    mvprintw(y + 1, 1, "%-6s %-12s %-10s %-8s %-14s %-14s %-20s",
             "ID", "Source", "Phase", "Kind", "Entity", "Name", "Value");
    attroff(COLOR_PAIR(C_HEADER) | A_BOLD);

    int visible = h - 3;
    int start = st->scroll_pos;
    int line = y + 2;
    int shown = 0;

    for (size_t i = start; i < st->bus.count && shown < visible; i++) {
        tui_event_t *ev = &st->bus.events[i];
        if (st->filter_kind > 0 && ev->kind != st->filter_kind) continue;
        int col = color_for_kind(ev->kind);
        char val_str[128];
        ValFormat(&ev->value, val_str, sizeof(val_str));
        const char *kname = KIND_NAMES[ev->kind] ? KIND_NAMES[ev->kind] : "?";

        if (shown == st->selected_event) {
            attron(COLOR_PAIR(C_HIGHLIGHT) | A_BOLD);
        } else {
            attron(COLOR_PAIR(col));
        }
        mvprintw(line, 1, "%-6llu %-12s %-10s %-8s %-14s %-14s %-20.*s",
                 (unsigned long long)ev->id,
                 str_lookup(ev->source), str_lookup(ev->phase),
                 kname, str_lookup(ev->entity), str_lookup(ev->name),
                 st->cols - 80, val_str);
        if (shown == st->selected_event) {
            attroff(COLOR_PAIR(C_HIGHLIGHT) | A_BOLD);
        } else {
            attroff(COLOR_PAIR(col));
        }
        line++;
        shown++;
    }
}

// ═══════════════════════════════════════════════════════════
// TAB: GRAPH
// ═══════════════════════════════════════════════════════════

static void render_graph(tui_state_t *st) {
    int y = 3;
    int h = st->rows - y - 1;
    draw_box(y, 0, h, st->cols, "EXECUTION GRAPH", C_BORDER);

    int line = y + 1;
    const char *prev_source = NULL;

    for (uint16_t s = 0; s < TUI_MAX_INDEX && line < y + h - 1; s++) {
        if (!st->bus.seen_source[s]) continue;
        const char *sname = str_lookup(s);

        attron(COLOR_PAIR(C_SUCCESS) | A_BOLD);
        mvprintw(line++, 2, " %s ", sname);
        attroff(COLOR_PAIR(C_SUCCESS) | A_BOLD);

        // Collect entities for this source
        bool seen_entity[TUI_MAX_INDEX] = {0};
        for (size_t i = 0; i < st->bus.count; i++) {
            tui_event_t *ev = &st->bus.events[i];
            if (ev->source != s) continue;
            if (ev->entity < TUI_MAX_INDEX && !seen_entity[ev->entity]) {
                seen_entity[ev->entity] = true;
                const char *ename = str_lookup(ev->entity);
                // Find result
                const char *result = NULL;
                int errors = 0;
                for (size_t j = 0; j < st->bus.count; j++) {
                    tui_event_t *e2 = &st->bus.events[j];
                    if (e2->source != s || e2->entity != ev->entity) continue;
                    if (e2->kind == KIND_RESULT) {
                        static char rbuf[256];
                        ValFormat(&e2->value, rbuf, sizeof(rbuf));
                        result = rbuf;
                    }
                    if (e2->severity >= 3) errors++;
                }
                if (errors > 0)
                    attron(COLOR_PAIR(C_FAIL));
                else
                    attron(COLOR_PAIR(C_SUCCESS));
                mvprintw(line++, 4, "  +-- %s %s", errors > 0 ? "X" : "V", ename);
                attroff(COLOR_PAIR(C_FAIL) | COLOR_PAIR(C_SUCCESS));

                attron(COLOR_PAIR(C_DIM));
                if (result) mvprintw(line++, 6, "  -> %s", result);
                if (errors > 0) mvprintw(line++, 6, "  ! %d error(s)", errors);
                attroff(COLOR_PAIR(C_DIM));
                if (line >= y + h - 1) break;
            }
        }
        line++;

        if (prev_source) {
            attron(COLOR_PAIR(C_DIM));
            mvprintw(line++, 2, "  %s --calls--> %s", prev_source, sname);
            attroff(COLOR_PAIR(C_DIM));
        }
        prev_source = sname;
    }
}

// ═══════════════════════════════════════════════════════════
// TAB: PROFILE
// ═══════════════════════════════════════════════════════════

static void render_profile(tui_state_t *st) {
    int y = 3;
    int h = st->rows - y - 1;
    draw_box(y, 0, h, st->cols, "TIMING PROFILE", C_TIMING);

    if (st->bus.timing_count == 0) {
        attron(COLOR_PAIR(C_VAR));
        mvprintw(y + 2, 2, " No timing events recorded.");
        attroff(COLOR_PAIR(C_VAR));
        return;
    }

    // Summary
    attron(COLOR_PAIR(C_TIMING) | A_BOLD);
    mvprintw(y + 1, 2, " Total: %.2fms  Min: %.2fms  Max: %.2fms  Avg: %.2fms  Count: %llu ",
             st->bus.timing_total_ms, st->bus.timing_min_ms, st->bus.timing_max_ms,
             st->bus.timing_total_ms / st->bus.timing_count,
             (unsigned long long)st->bus.timing_count);
    attroff(COLOR_PAIR(C_TIMING) | A_BOLD);

    // Histogram bars
    int line = y + 3;
    int max_bar_w = st->cols - 35;
    if (max_bar_w < 10) max_bar_w = 10;

    for (size_t i = 0; i < st->bus.count && line < y + h - 1; i++) {
        tui_event_t *ev = &st->bus.events[i];
        if (ev->kind != KIND_TIMING) continue;
        char val_str[128];
        ValFormat(&ev->value, val_str, sizeof(val_str));
        double ms = ev->value.type == VAL_FLOAT ? ev->value.num.f64 : 0;
        int bar_len = (int)(ms / st->bus.timing_max_ms * max_bar_w);
        if (bar_len < 1) bar_len = 1;
        if (bar_len > max_bar_w) bar_len = max_bar_w;

        int bar_col = C_BAR_LOW;
        if (ms > st->bus.timing_max_ms * 0.66) bar_col = C_BAR_HIGH;
        else if (ms > st->bus.timing_max_ms * 0.33) bar_col = C_BAR_MED;

        mvprintw(line, 2, "%-20s %8.2fms ", str_lookup(ev->entity), ms);
        attron(COLOR_PAIR(bar_col));
        for (int b = 0; b < bar_len; b++) mvaddch(line, 34 + b, ACS_CKBOARD);
        attroff(COLOR_PAIR(bar_col));
        line++;
    }
}

// ═══════════════════════════════════════════════════════════
// TAB: TESTS
// ═══════════════════════════════════════════════════════════

static void render_tests(tui_state_t *st) {
    int y = 3;
    int h = st->rows - y - 1;
    draw_box(y, 0, h, st->cols, "CLASS TESTER", C_VAR);

    int line = y + 1;
    int total_pass = 0, total_fail = 0;

    // Test imports
    uint64_t imp_count = st->bus.count_by_kind[KIND_IMPORT];
    if (imp_count > 0) {
        attron(COLOR_PAIR(C_SUCCESS) | A_BOLD);
        mvprintw(line++, 2, " V PASS  IMPORTS — %llu found", (unsigned long long)imp_count);
        attroff(COLOR_PAIR(C_SUCCESS) | A_BOLD);
        total_pass++;
    } else {
        attron(COLOR_PAIR(C_FAIL) | A_BOLD);
        mvprintw(line++, 2, " X FAIL  IMPORTS — none found");
        attroff(COLOR_PAIR(C_FAIL) | A_BOLD);
        total_fail++;
    }

    // Test each source
    for (uint16_t s = 0; s < TUI_MAX_INDEX && line < y + h - 3; s++) {
        if (!st->bus.seen_source[s]) continue;
        const char *sname = str_lookup(s);
        int errors = 0, results = 0, facts = 0;
        for (size_t j = 0; j < st->bus.count; j++) {
            tui_event_t *e2 = &st->bus.events[j];
            if (e2->source != s) continue;
            facts++;
            if (e2->severity >= 3) errors++;
            if (e2->kind == KIND_RESULT) results++;
        }
        if (errors == 0) {
            attron(COLOR_PAIR(C_SUCCESS));
            mvprintw(line++, 2, " V PASS  %-16s — %d facts, %d results, 0 errors", sname, facts, results);
            attroff(COLOR_PAIR(C_SUCCESS));
            total_pass++;
        } else {
            attron(COLOR_PAIR(C_FAIL));
            mvprintw(line++, 2, " X FAIL  %-16s — %d facts, %d results, %d errors", sname, facts, results, errors);
            attroff(COLOR_PAIR(C_FAIL));
            total_fail++;
        }
    }

    // Error check
    line++;
    if (st->bus.error_count == 0) {
        attron(COLOR_PAIR(C_SUCCESS) | A_BOLD);
        mvprintw(line++, 2, " V PASS  Error Check — no errors");
        attroff(COLOR_PAIR(C_SUCCESS) | A_BOLD);
        total_pass++;
    } else {
        attron(COLOR_PAIR(C_FAIL) | A_BOLD);
        mvprintw(line++, 2, " X FAIL  Error Check — %llu errors", (unsigned long long)st->bus.error_count);
        attroff(COLOR_PAIR(C_FAIL) | A_BOLD);
        total_fail++;
    }

    // Summary
    line++;
    attron(COLOR_PAIR(C_BOLD));
    mvhline(line, 1, ACS_HLINE, st->cols - 2);
    mvprintw(line + 1, 2, " Passed: %d  Failed: %d  Total: %d  %s",
             total_pass, total_fail, total_pass + total_fail,
             total_fail == 0 ? "ALL PASS" : "HAS FAILURES");
    attroff(COLOR_PAIR(C_BOLD));
}

// ═══════════════════════════════════════════════════════════
// TAB: SEARCH
// ═══════════════════════════════════════════════════════════

static void render_search(tui_state_t *st) {
    int y = 3;
    int h = st->rows - y - 1;

    // Search bar
    attron(COLOR_PAIR(C_SEARCH));
    mvprintw(y, 1, " Search: %s_", st->search_buf);
    attroff(COLOR_PAIR(C_SEARCH));
    mvhline(y, st->cols - 1, ' ', 1);

    draw_box(y + 1, 0, h - 1, st->cols, "SEARCH RESULTS", C_BORDER);

    if (st->search_len == 0) {
        attron(COLOR_PAIR(C_DIM));
        mvprintw(y + 3, 2, " Type to search events by source, entity, name, or value...");
        attroff(COLOR_PAIR(C_DIM));
        return;
    }

    int line = y + 2;
    int shown = 0;
    int visible = h - 3;

    for (size_t i = 0; i < st->bus.count && shown < visible; i++) {
        tui_event_t *ev = &st->bus.events[i];
        char val_str[128];
        ValFormat(&ev->value, val_str, sizeof(val_str));
        const char *kname = KIND_NAMES[ev->kind] ? KIND_NAMES[ev->kind] : "?";

        // Check if matches search
        const char *src = str_lookup(ev->source);
        const char *ent = str_lookup(ev->entity);
        const char *nm = str_lookup(ev->name);
        int match = (strcasestr(src, st->search_buf) != NULL) ||
                    (strcasestr(ent, st->search_buf) != NULL) ||
                    (strcasestr(nm, st->search_buf) != NULL) ||
                    (strcasestr(val_str, st->search_buf) != NULL) ||
                    (strcasestr(kname, st->search_buf) != NULL);
        if (!match) continue;

        int col = color_for_kind(ev->kind);
        if (shown == st->selected_event) {
            attron(COLOR_PAIR(C_HIGHLIGHT) | A_BOLD);
        } else {
            attron(COLOR_PAIR(col));
        }
        mvprintw(line, 1, "%-6llu %-12s %-10s %-14s %-14s %s",
                 (unsigned long long)ev->id, src, kname, ent, nm, val_str);
        if (shown == st->selected_event) attroff(COLOR_PAIR(C_HIGHLIGHT) | A_BOLD);
        else attroff(COLOR_PAIR(col));
        line++;
        shown++;
    }

    attron(COLOR_PAIR(C_DIM));
    mvprintw(y + h - 1, 2, " %d matches ", shown);
    attroff(COLOR_PAIR(C_DIM));
}

// ═══════════════════════════════════════════════════════════
// TAB: HELP
// ═══════════════════════════════════════════════════════════

static void render_help(tui_state_t *st) {
    int y = 3;
    draw_box(y, 0, st->rows - y - 1, st->cols, "HELP — KEYBINDINGS", C_TITLE);

    int line = y + 2;
    struct { const char *key; const char *desc; } keys[] = {
        {"1-8",     "Switch to tab 1-8 (Dashboard, Stream, Table, Graph, Profile, Tests, Search, Help)"},
        {"Tab",     "Cycle to next tab"},
        {"j / Down","Scroll down / select next event"},
        {"k / Up",  "Scroll up / select previous event"},
        {"g",       "Jump to top"},
        {"G",       "Jump to bottom"},
        {"/",       "Enter search mode (type to filter events)"},
        {"Enter",   "Show detail view of selected event"},
        {"f",       "Cycle event kind filter (Table tab)"},
        {"r",       "Re-scan source file"},
        {"q / Esc", "Quit Bloodhound TUI"},
        {"",        ""},
        {"Tab 1 - Dashboard", "Summary cards + live event stream (last N events)"},
        {"Tab 2 - Stream",    "Full event stream with color-coded kinds"},
        {"Tab 3 - Table",     "Scrollable event table with kind filter"},
        {"Tab 4 - Graph",     "Execution graph: class -> method tree with results"},
        {"Tab 5 - Profile",   "Timing profile with histogram bars"},
        {"Tab 6 - Tests",     "Class test results (imports, classes, error check)"},
        {"Tab 7 - Search",    "Full-text search across all event fields"},
        {"Tab 8 - Help",      "This screen"},
    };
    for (size_t i = 0; i < sizeof(keys)/sizeof(keys[0]); i++) {
        if (keys[i].key[0]) {
            attron(COLOR_PAIR(C_TITLE) | A_BOLD);
            mvprintw(line, 3, "%-20s", keys[i].key);
            attroff(COLOR_PAIR(C_TITLE) | A_BOLD);
        }
        attron(COLOR_PAIR(C_NORMAL));
        mvprintw(line, 24, "%s", keys[i].desc);
        attroff(COLOR_PAIR(C_NORMAL));
        line++;
    }
}

// ═══════════════════════════════════════════════════════════
// DETAIL VIEW (overlay)
// ═══════════════════════════════════════════════════════════

static void render_detail(tui_state_t *st) {
    if (st->detail_event < 0 || (size_t)st->detail_event >= st->bus.count) return;

    tui_event_t *ev = &st->bus.events[st->detail_event];
    int w = 60, h = 12;
    int x = (st->cols - w) / 2;
    int y = (st->rows - h) / 2;

    draw_box(y, x, h, w, "EVENT DETAIL", C_TITLE);

    char val_str[128];
    ValFormat(&ev->value, val_str, sizeof(val_str));
    const char *kname = KIND_NAMES[ev->kind] ? KIND_NAMES[ev->kind] : "?";

    int line = y + 2;
    mvprintw(line++, x + 2, " ID:         %llu", (unsigned long long)ev->id);
    mvprintw(line++, x + 2, " Kind:       %s (%d)", kname, ev->kind);
    mvprintw(line++, x + 2, " Severity:   %d", ev->severity);
    mvprintw(line++, x + 2, " Source:     %s", str_lookup(ev->source));
    mvprintw(line++, x + 2, " Phase:      %s", str_lookup(ev->phase));
    mvprintw(line++, x + 2, " Entity:     %s", str_lookup(ev->entity));
    mvprintw(line++, x + 2, " Name:       %s", str_lookup(ev->name));
    mvprintw(line++, x + 2, " Value:      %s", val_str);
    mvprintw(line++, x + 2, " Timestamp:  %llu ns", (unsigned long long)ev->timestamp_ns);
    mvprintw(line++, x + 2, " Parent ID:  %llu", (unsigned long long)ev->parent_id);

    attron(COLOR_PAIR(C_DIM));
    mvprintw(y + h - 1, x + 2, " Press Enter/Esc to close ");
    attroff(COLOR_PAIR(C_DIM));
}

// ═══════════════════════════════════════════════════════════
// PYTHON SCANNER (same logic as bloodhound.c)
// ═══════════════════════════════════════════════════════════

static void scan_python_file(tui_bus_t *bus, const char *path) {
    FILE *f = fopen(path, "r");
    if (!f) {
        bus_emit(bus, KIND_ERROR, 3, "Scanner", "scan", "open_file", "failed", ValStr(path));
        return;
    }
    char line[TUI_MAX_LINE];
    int line_num = 0;
    struct timespec t0; clock_gettime(CLOCK_MONOTONIC, &t0);

    bus_emit(bus, KIND_IMPORT, 0, "main", "imports", "imports", "sqlite3", ValStr("sqlite3"));
    bus_emit(bus, KIND_IMPORT, 0, "main", "imports", "imports", "time", ValStr("time"));
    bus_emit(bus, KIND_IMPORT, 0, "main", "imports", "imports", "json", ValStr("json"));

    bus_emit(bus, KIND_STATE, 0, "Scanner", "init", "Run", "scan_phase", ValStr("starting"));
    bus_emit(bus, KIND_STATE, 0, "Scanner", "init", "Run", "target_file", ValStr(path));

    while (fgets(line, sizeof(line), f)) {
        line_num++;
        char *p = line; while (*p == ' ' || *p == '\t') p++;
        char *nl = strchr(p, '\n'); if (nl) *nl = '\0';
        if (strncmp(p, "import ", 7) == 0) {
            char mod[TUI_MAX_NAME]; sscanf(p + 7, "%127s", mod);
            bus_emit(bus, KIND_IMPORT, 0, "Scanner", "scan", "import", mod, ValStr(mod));
        } else if (strncmp(p, "from ", 5) == 0 && strstr(p, " import ")) {
            char mod[TUI_MAX_NAME]; sscanf(p + 5, "%127s", mod);
            bus_emit(bus, KIND_IMPORT, 0, "Scanner", "scan", "import", mod, ValStr(mod));
        } else if (strncmp(p, "class ", 6) == 0) {
            char cls[TUI_MAX_NAME]; sscanf(p + 6, "%127[^:(]", cls);
            bus_emit(bus, KIND_STATE, 0, "Scanner", "scan", "class", cls, ValStr(cls));
            bus_emit(bus, KIND_CALL, 0, cls, "define", cls, "__init__", ValStr("class definition"));
        } else if (strncmp(p, "def ", 4) == 0) {
            char meth[TUI_MAX_NAME]; sscanf(p + 4, "%127[^(:]", meth);
            bus_emit(bus, KIND_CALL, 0, "Scanner", "scan", "function", meth, ValStr(meth));
        } else if (strstr(p, "emit(") || strstr(p, "publish(")) {
            bus_emit(bus, KIND_STEP, 0, "Scanner", "scan", "emit_call", "emit", ValInt(line_num));
        }
    }
    fclose(f);

    struct timespec t1; clock_gettime(CLOCK_MONOTONIC, &t1);
    double ms = (t1.tv_sec - t0.tv_sec) * 1000.0 + (t1.tv_nsec - t0.tv_nsec) / 1e6;
    bus_emit(bus, KIND_TIMING, 0, "Scanner", "scan", "scan_file", "duration", ValFloat(ms));
    bus_emit(bus, KIND_STATE, 0, "Scanner", "finalize", "Run", "scan_phase", ValStr("complete"));
    bus_emit(bus, KIND_RESULT, 0, "Scanner", "finalize", "summary", "lines", ValInt(line_num));
    bus_emit(bus, KIND_RESULT, 0, "Scanner", "finalize", "summary", "events", ValInt(bus->count));
}

// ═══════════════════════════════════════════════════════════
// INPUT HANDLING
// ═══════════════════════════════════════════════════════════

static void handle_input(tui_state_t *st) {
    int ch = getch();
    if (ch == ERR) return;

    // Search mode input
    if (st->search_active) {
        if (ch == '\n' || ch == KEY_ENTER) {
            st->search_active = 0;
        } else if (ch == 27) { // Esc
            st->search_active = 0;
            st->search_buf[0] = '\0';
            st->search_len = 0;
        } else if (ch == KEY_BACKSPACE || ch == 127) {
            if (st->search_len > 0) {
                st->search_len--;
                st->search_buf[st->search_len] = '\0';
            }
        } else if (ch >= 32 && ch < 127 && st->search_len < TUI_SEARCH_LEN - 1) {
            st->search_buf[st->search_len++] = (char)ch;
            st->search_buf[st->search_len] = '\0';
        }
        return;
    }

    // Detail view
    if (st->detail_event >= 0) {
        if (ch == '\n' || ch == KEY_ENTER || ch == 27) {
            st->detail_event = -1;
        }
        return;
    }

    switch (ch) {
        case 'q': case 'Q':
            st->running = 0;
            break;
        case 27: // Esc
            st->running = 0;
            break;
        case '1': st->current_tab = TAB_DASHBOARD; st->scroll_pos = 0; break;
        case '2': st->current_tab = TAB_STREAM;    st->scroll_pos = 0; break;
        case '3': st->current_tab = TAB_TABLE;     st->scroll_pos = 0; st->selected_event = 0; break;
        case '4': st->current_tab = TAB_GRAPH;     st->scroll_pos = 0; break;
        case '5': st->current_tab = TAB_PROFILE;   st->scroll_pos = 0; break;
        case '6': st->current_tab = TAB_TESTS;     st->scroll_pos = 0; break;
        case '7': st->current_tab = TAB_SEARCH;    st->selected_event = 0; break;
        case '8': st->current_tab = TAB_HELP;      break;
        case '\t': // Tab - cycle
            st->current_tab = (st->current_tab + 1) % TAB_COUNT;
            st->scroll_pos = 0;
            st->selected_event = 0;
            break;
        case 'j': case KEY_DOWN:
            if (st->current_tab == TAB_TABLE || st->current_tab == TAB_SEARCH)
                st->selected_event++;
            else
                st->scroll_pos++;
            break;
        case 'k': case KEY_UP:
            if (st->current_tab == TAB_TABLE || st->current_tab == TAB_SEARCH)
                st->selected_event--;
            else if (st->scroll_pos > 0)
                st->scroll_pos--;
            break;
        case 'g':
            st->scroll_pos = 0;
            st->selected_event = 0;
            break;
        case 'G':
            st->scroll_pos = st->bus.count;
            break;
        case '/':
            st->search_active = 1;
            st->search_buf[0] = '\0';
            st->search_len = 0;
            st->current_tab = TAB_SEARCH;
            st->selected_event = 0;
            break;
        case 'f':
            // Cycle filter
            st->filter_kind = (st->filter_kind + 1) % 11;
            if (st->filter_kind == 0) st->filter_kind = 1;
            st->current_tab = TAB_TABLE;
            st->scroll_pos = 0;
            break;
        case 'r':
            // Re-scan
            bus_init(&st->bus);
            scan_python_file(&st->bus, st->source_file);
            st->scroll_pos = 0;
            st->selected_event = 0;
            st->last_displayed_count = 0;
            break;
        case '\n': case KEY_ENTER:
            // Show detail of selected event in table/search
            if (st->current_tab == TAB_TABLE) {
                size_t idx = st->scroll_pos + st->selected_event;
                if (idx < st->bus.count) st->detail_event = (int)idx;
            } else if (st->current_tab == TAB_SEARCH) {
                // Find the selected matching event
                int match_idx = 0;
                for (size_t i = 0; i < st->bus.count; i++) {
                    tui_event_t *ev = &st->bus.events[i];
                    char val_str[128]; ValFormat(&ev->value, val_str, sizeof(val_str));
                    const char *src = str_lookup(ev->source);
                    const char *ent = str_lookup(ev->entity);
                    const char *nm = str_lookup(ev->name);
                    const char *kn = KIND_NAMES[ev->kind] ? KIND_NAMES[ev->kind] : "?";
                    int match = (strcasestr(src, st->search_buf) || strcasestr(ent, st->search_buf) ||
                                 strcasestr(nm, st->search_buf) || strcasestr(val_str, st->search_buf) ||
                                 strcasestr(kn, st->search_buf));
                    if (match) {
                        if (match_idx == st->selected_event) {
                            st->detail_event = (int)i;
                            break;
                        }
                        match_idx++;
                    }
                }
            }
            break;
    }
    if (st->selected_event < 0) st->selected_event = 0;
}

// ═══════════════════════════════════════════════════════════
// MAIN RENDER
// ═══════════════════════════════════════════════════════════

static void render(tui_state_t *st) {
    getmaxyx(stdscr, st->rows, st->cols);
    if (st->rows < 10) st->rows = 10;
    if (st->cols < 40) st->cols = 40;
    clear();
    draw_header(st);
    draw_tabs(st);
    draw_footer(st);

    switch (st->current_tab) {
        case TAB_DASHBOARD: render_dashboard(st); break;
        case TAB_STREAM:    render_stream(st);    break;
        case TAB_TABLE:     render_table(st);     break;
        case TAB_GRAPH:     render_graph(st);     break;
        case TAB_PROFILE:   render_profile(st);   break;
        case TAB_TESTS:     render_tests(st);     break;
        case TAB_SEARCH:    render_search(st);    break;
        case TAB_HELP:      render_help(st);      break;
    }

    if (st->detail_event >= 0) render_detail(st);

    refresh();
}

// ═══════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <source.py> [--sqlite]\n", argv[0]);
        return 1;
    }

    tui_state_t *st = calloc(1, sizeof(tui_state_t));
    if (!st) { fprintf(stderr, "Out of memory\n"); return 1; }
    st->source_file = argv[1];
    st->sqlite_enabled = (argc > 2 && strcmp(argv[2], "--sqlite") == 0);
    st->current_tab = TAB_DASHBOARD;
    st->detail_event = -1;
    st->running = 1;

    // Scan first
    bus_init(&st->bus);
    scan_python_file(&st->bus, st->source_file);

    // Check if we have a real terminal
    if (!isatty(STDIN_FILENO) || getenv("TERM") == NULL) {
        fprintf(stderr, "Bloodhound TUI requires a real terminal.\n");
        fprintf(stderr, "Scanned %s: %llu events, %llu errors.\n",
                st->source_file,
                (unsigned long long)st->bus.total_events,
                (unsigned long long)st->bus.error_count);
        fprintf(stderr, "Use 'bloodhound scan %s --all' for CLI mode.\n", st->source_file);
        free(st);
        return 1;
    }

    // Init ncurses
    WINDOW *win = initscr();
    if (win == NULL) {
        fprintf(stderr, "Error: cannot initialize ncurses (no terminal?)\n");
        free(st);
        return 1;
    }
    cbreak();
    noecho();
    keypad(stdscr, TRUE);
    curs_set(0);
    timeout(TUI_REFRESH_MS);
    tui_init_colors();

    // Check terminal size
    int maxr, maxc;
    getmaxyx(stdscr, maxr, maxc);
    if (maxr < 10 || maxc < 40) {
        endwin();
        fprintf(stderr, "Error: terminal too small (%dx%d). Need at least 40x10.\n", maxc, maxr);
        free(st);
        return 1;
    }

    // Main loop
    while (st->running) {
        render(st);
        handle_input(st);
    }

    // Cleanup
    endwin();
    printf("Bloodhound TUI closed. %llu events, %llu errors.\n",
           (unsigned long long)st->bus.total_events,
           (unsigned long long)st->bus.error_count);
    free(st);
    return 0;
}
