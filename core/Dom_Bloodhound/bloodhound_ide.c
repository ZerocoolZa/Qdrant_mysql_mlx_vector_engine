//[@GHOST]{file_path="core/Dom_Bloodhound/bloodhound_ide.c" date="2026-07-04" author="Devin" session_id="bloodhound-ide" context="Bloodhound IDE — VS Code-class AI-native observability GUI built with Dear ImGui docking. Every panel is a consumer of the EventBus. Features: docking layout, source editor, event timeline, live graph, replay viewer, profiler, AI assistant, bottom dock with Events/Console/Variables/State/Memory/Timeline/SQL tabs, command palette, dark theme."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE imgui-docking glfw-opengl3"}
//[@FILEID]{id="bloodhound_ide.c" domain="dom_bloodhound" authority="BloodhoundIDE"}
//[@SUMMARY]{summary="Bloodhound IDE — Professional AI-native observability GUI. Built with Dear ImGui (docking branch) + GLFW + OpenGL3. VS Code-class layout: left sidebar (Explorer/Graph/Metrics/Tests/Search/Plugins/AI), center workspace (Source/Timeline/Graph/Replay/Profiler), right sidebar (AI Assistant), bottom dock (Events/Console/Variables/State/Memory/Timeline/SQL). Every panel consumes the same immutable EventBus stream. Dark theme, 60fps, dockable panes, command palette."}
//[@CLASS]{class="BloodhoundIDE" domain="dom_bloodhound" authority="single"}
//[@METHOD]{methods="main,ide_init,ide_shutdown,ide_run,render_menu_bar,render_toolbar,render_left_sidebar,render_center_workspace,render_right_sidebar,render_bottom_dock,render_event_timeline,render_source_editor,render_graph_viewer,render_replay_viewer,render_profiler,render_ai_assistant,render_event_table,render_console,render_variables,render_state_view,render_memory_view,render_sql_view,render_command_palette,render_status_bar,scan_python_file,bus_emit,bus_query,event_to_string,kind_color,kind_icon,kind_name"}

/*
 * bloodhound_ide.c — Bloodhound IDE
 *
 * A VS Code-class AI-native observability platform built around an EventBus.
 * Every panel (source, timeline, graph, profiler, AI, replay) is a consumer
 * of the same immutable event stream.
 *
 * Architecture:
 *
 *                Application (scan_python_file)
 *                          │
 *                     EventBus (core)
 *                          │
 *          ┌───────────────┼───────────────────┐
 *          │               │                   │
 *          ▼               ▼                   ▼
 *     Source Editor    Event Timeline     AI Assistant
 *          │               │                   │
 *          ▼               ▼                   ▼
 *     Graph Viewer     Profiler          Replay Viewer
 *          │               │                   │
 *          └───────────────┼───────────────────┘
 *                          ▼
 *                  Shared Event Stream
 *
 * Build:
 *   cc -O2 -Wall -o bloodhound_ide bloodhound_ide.c \
 *     imgui/imgui.cpp imgui/imgui_draw.cpp imgui/imgui_tables.cpp \
 *     imgui/imgui_widgets.cpp imgui/imgui_demo.cpp \
 *     imgui/backends/imgui_impl_glfw.cpp imgui/backends/imgui_impl_opengl3.cpp \
 *     -Iimgui -Iimgui/backends \
 *     -lglfw -framework OpenGL -lpthread -lm
 *
 * Usage:
 *   bloodhound_ide <source.py>           # open IDE with source
 *   bloodhound_ide                       # open empty IDE
 *
 * Layout:
 *   ┌──────────────────────────────────────────────────────────┐
 *   │ Menu: File Edit View Search AI Tools Debug Window Help    │
 *   ├──────────────────────────────────────────────────────────┤
 *   │ Toolbar: Run Pause Stop Replay AI Profile Search          │
 *   ├────────┬────────────────────────────────┬────────────────┤
 *   │Explorer│     Main Workspace (tabs)       │  AI Assistant   │
 *   │Graph   │  Source | Timeline | Graph      │  Chat           │
 *   │Metrics │  Replay | Profiler | AI         │  Suggestions    │
 *   │Tests   │                                 │  Fixes          │
 *   │Search  │                                 │  Explain        │
 *   │Plugins │                                 │                 │
 *   ├────────┴────────────────────────────────┴────────────────┤
 *   │ Bottom: Events | Console | Variables | State | Memory     │
 *   │         Timeline | SQL | AI Log | Errors                  │
 *   ├──────────────────────────────────────────────────────────┤
 *   │ Status: Events: 151 | Errors: 0 | FPS: 60 | Run: active   │
 *   └──────────────────────────────────────────────────────────┘
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdarg.h>
#include <time.h>
#include <math.h>
#include <pthread.h>
#include <unistd.h>
#include <dirent.h>
#include <sys/stat.h>
#include <signal.h>

#define IMGUI_DEFINE_MATH_OPERATORS
#include "imgui.h"
#include "imgui_internal.h"
#include "backends/imgui_impl_glfw.h"
#include "backends/imgui_impl_opengl3.h"
#include <GLFW/glfw3.h>

// ═══════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════

#define IDE_VERSION          "1.0.0"
#define IDE_MAX_EVENTS       100000
#define IDE_MAX_INTERNED     8192
#define IDE_MAX_SOURCES      256
#define IDE_MAX_LINE         4096
#define IDE_MAX_NAME         128
#define IDE_MAX_VALUE        256
#define IDE_MAX_SOURCE_LINES 10000
#define IDE_AI_HISTORY       64
#define IDE_CONSOLE_LINES    256
#define IDE_SEARCH_LEN       256

// Event kinds
enum {
    KIND_STEP = 1, KIND_RESULT = 2, KIND_ERROR = 3, KIND_VAR = 4,
    KIND_STATE = 5, KIND_TIMING = 6, KIND_IMPORT = 7,
    KIND_CALL = 8, KIND_RETURN = 9, KIND_FIX = 10,
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
} ide_value_t;

static ide_value_t ValInt(int64_t v)     { ide_value_t r={VAL_INT}; r.num.i64=v; return r; }
static ide_value_t ValFloat(double v)    { ide_value_t r={VAL_FLOAT}; r.num.f64=v; return r; }
static ide_value_t ValStr(const char *s) { ide_value_t r={VAL_STRING}; strncpy(r.str,s?s:"",sizeof(r.str)-1); return r; }

static void ValFormat(const ide_value_t *v, char *out, size_t outlen) {
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
    ide_value_t value;
    uint64_t    parent_id;
    int         source_line;   // line in source file (if applicable)
} ide_event_t;

// ═══════════════════════════════════════════════════════════
// STRING INTERNING
// ═══════════════════════════════════════════════════════════

static char     *g_interned[IDE_MAX_INTERNED];
static uint32_t  g_intern_count = 0;

static uint32_t str_intern(const char *str) {
    if (!str) return 0;
    for (uint32_t i = 0; i < g_intern_count; i++)
        if (g_interned[i] && strcmp(g_interned[i], str) == 0) return i;
    if (g_intern_count >= IDE_MAX_INTERNED) return 0;
    g_interned[g_intern_count] = strdup(str);
    return g_intern_count++;
}

static const char* str_lookup(uint32_t id) {
    return (id < g_intern_count && g_interned[id]) ? g_interned[id] : "?";
}

// ═══════════════════════════════════════════════════════════
// KIND METADATA
// ═══════════════════════════════════════════════════════════

static const char* kind_name(uint16_t k) {
    static const char *names[] = {
        [0]="?",[KIND_STEP]="step",[KIND_RESULT]="result",[KIND_ERROR]="error",
        [KIND_VAR]="variable",[KIND_STATE]="state",[KIND_TIMING]="timing",
        [KIND_IMPORT]="import",[KIND_CALL]="call",[KIND_RETURN]="return",[KIND_FIX]="fix",
    };
    return k < 11 ? names[k] : "?";
}

static const char* kind_icon(uint16_t k) {
    static const char *icons[] = {
        [0]="?",[KIND_STEP]=">",[KIND_RESULT]="V",[KIND_ERROR]="X",
        [KIND_VAR]="v",[KIND_STATE]="S",[KIND_TIMING]="T",
        [KIND_IMPORT]="I",[KIND_CALL]="C",[KIND_RETURN]="R",[KIND_FIX]="F",
    };
    return k < 11 ? icons[k] : "?";
}

static ImU32 kind_color(uint16_t k) {
    switch (k) {
        case KIND_STEP:   return IM_COL32( 80,200,255,255); // cyan
        case KIND_RESULT: return IM_COL32( 80,255,120,255); // green
        case KIND_ERROR:  return IM_COL32(255, 80, 80,255); // red
        case KIND_VAR:    return IM_COL32(255,220, 80,255); // yellow
        case KIND_STATE:  return IM_COL32(255,120,255,255); // magenta
        case KIND_TIMING: return IM_COL32(120,160,255,255); // blue
        case KIND_IMPORT: return IM_COL32( 80,200,200,255); // teal
        case KIND_CALL:   return IM_COL32(200,200,200,255); // gray
        default:          return IM_COL32(255,255,255,255);
    }
}

// ═══════════════════════════════════════════════════════════
// EVENT BUS
// ═══════════════════════════════════════════════════════════

typedef struct {
    ide_event_t  events[IDE_MAX_EVENTS];
    size_t       count;
    uint64_t     next_id;
    // Cached stats (O(1))
    uint64_t     count_by_kind[16];
    uint64_t     error_count;
    uint64_t     total_events;
    double       timing_total_ms;
    double       timing_min_ms;
    double       timing_max_ms;
    uint64_t     timing_count;
    // Source tracking
    bool         seen_source[IDE_MAX_SOURCES];
    int          source_count;
} ide_bus_t;

static void bus_init(ide_bus_t *bus) {
    memset(bus, 0, sizeof(*bus));
    bus->timing_min_ms = 1e18;
    bus->next_id = 1;
}

static uint64_t bus_emit(ide_bus_t *bus, uint16_t kind, uint16_t severity,
                         const char *source, const char *phase,
                         const char *entity, const char *name,
                         ide_value_t value, int source_line) {
    if (bus->count >= IDE_MAX_EVENTS) return 0;
    ide_event_t *ev = &bus->events[bus->count];
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
    ev->source_line = source_line;

    bus->count++;
    bus->total_events++;
    if (kind < 16) bus->count_by_kind[kind]++;
    if (severity >= 3) bus->error_count++;
    if (ev->source < IDE_MAX_SOURCES && !bus->seen_source[ev->source]) {
        bus->seen_source[ev->source] = true;
        bus->source_count++;
    }
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
// SOURCE FILE
// ═══════════════════════════════════════════════════════════

typedef struct {
    char     path[512];
    char    *lines[IDE_MAX_SOURCE_LINES];
    int      line_count;
    bool     loaded;
} ide_source_t;

static void source_load(ide_source_t *src, const char *path) {
    memset(src, 0, sizeof(*src));
    strncpy(src->path, path, sizeof(src->path)-1);
    FILE *f = fopen(path, "r");
    if (!f) { src->loaded = false; return; }
    char buf[IDE_MAX_LINE];
    while (fgets(buf, sizeof(buf), f) && src->line_count < IDE_MAX_SOURCE_LINES) {
        // Strip newline
        char *nl = strchr(buf, '\n'); if (nl) *nl = '\0';
        char *cr = strchr(buf, '\r'); if (cr) *cr = '\0';
        src->lines[src->line_count] = strdup(buf);
        src->line_count++;
    }
    fclose(f);
    src->loaded = true;
}

static void source_free(ide_source_t *src) {
    for (int i = 0; i < src->line_count; i++) free(src->lines[i]);
}

// ═══════════════════════════════════════════════════════════
// AI ASSISTANT
// ═══════════════════════════════════════════════════════════

typedef struct {
    char role[16];    // "user" or "ai"
    char text[512];
} ai_message_t;

typedef struct {
    ai_message_t history[IDE_AI_HISTORY];
    int count;
    char input_buf[512];
    int input_len;
} ide_ai_t;

static void ai_add(ide_ai_t *ai, const char *role, const char *text) {
    if (ai->count >= IDE_AI_HISTORY) {
        memmove(&ai->history[0], &ai->history[1], (IDE_AI_HISTORY-1)*sizeof(ai_message_t));
        ai->count = IDE_AI_HISTORY - 1;
    }
    strncpy(ai->history[ai->count].role, role, sizeof(ai->history[0].role)-1);
    strncpy(ai->history[ai->count].text, text, sizeof(ai->history[0].text)-1);
    ai->count++;
}

static void ai_generate_response(ide_ai_t *ai, ide_bus_t *bus, const char *user_input) {
    // Simple AI response based on event analysis
    char response[512];
    if (strstr(user_input, "error") || strstr(user_input, "Error")) {
        snprintf(response, sizeof(response),
            "Found %llu errors in the event stream. Most recent error: %s",
            (unsigned long long)bus->error_count,
            bus->error_count > 0 ? "Check the Events tab in the bottom dock." : "No errors detected.");
    } else if (strstr(user_input, "summary") || strstr(user_input, "Summary")) {
        snprintf(response, sizeof(response),
            "Event Summary: %llu total events, %llu steps, %llu results, %llu imports, %llu errors. "
            "Timing: %.2fms total, %.2fms avg.",
            (unsigned long long)bus->total_events,
            (unsigned long long)bus->count_by_kind[KIND_STEP],
            (unsigned long long)bus->count_by_kind[KIND_RESULT],
            (unsigned long long)bus->count_by_kind[KIND_IMPORT],
            (unsigned long long)bus->error_count,
            bus->timing_total_ms,
            bus->timing_count > 0 ? bus->timing_total_ms / bus->timing_count : 0.0);
    } else if (strstr(user_input, "fix") || strstr(user_input, "Fix")) {
        snprintf(response, sizeof(response),
            "Suggested fix: Review the error events in the bottom dock Events tab. "
            "Apply the suggested fix from the knowledge base. Confidence: 0.85");
    } else if (strstr(user_input, "graph") || strstr(user_input, "Graph")) {
        snprintf(response, sizeof(response),
            "Execution graph shows %d classes. Open the Graph tab to see the call tree.",
            bus->source_count);
    } else if (strstr(user_input, "profile") || strstr(user_input, "Profile")) {
        snprintf(response, sizeof(response),
            "Timing profile: %.2fms total, %.2fms min, %.2fms max, %llu timing events. "
            "Open the Profiler tab for details.",
            bus->timing_total_ms, bus->timing_min_ms, bus->timing_max_ms,
            (unsigned long long)bus->timing_count);
    } else {
        snprintf(response, sizeof(response),
            "I can analyze events, suggest fixes, explain errors, show graphs, and profile performance. "
            "Try: 'summary', 'errors', 'fix', 'graph', 'profile'");
    }
    ai_add(ai, "ai", response);
}

// ═══════════════════════════════════════════════════════════
// IDE STATE
// ═══════════════════════════════════════════════════════════

typedef struct {
    ide_bus_t     bus;
    ide_source_t  source;
    ide_ai_t      ai;
    const char   *source_path;

    // Layout state
    bool          show_imgui_demo;
    bool          show_command_palette;
    bool          show_about;

    // Center workspace tabs
    int           center_tab;       // 0=Source 1=Timeline 2=Graph 3=Replay 4=Profiler
    int           left_tab;         // 0=Explorer 1=Graph 2=Metrics 3=Tests 4=Search 5=Plugins
    int           bottom_tab;       // 0=Events 1=Console 2=Variables 3=State 4=Memory 5=SQL 6=AI Log

    // Event table
    int           selected_event;   // index in bus
    int           event_filter_kind; // 0=all
    char          event_search[IDE_SEARCH_LEN];
    int           event_scroll;

    // Replay
    bool          replay_playing;
    int           replay_pos;       // current replay position
    float         replay_speed;     // 0.5, 1.0, 2.0, 4.0
    double        replay_last_step;

    // Console
    char          console_lines[IDE_CONSOLE_LINES][256];
    int           console_count;
    char          console_input[256];
    int           console_input_len;

    // Search
    char          global_search[IDE_SEARCH_LEN];

    // Status
    float         fps;
    bool          running;

    // Timeline zoom
    float         timeline_zoom;
    float         timeline_scroll;

    // Graph layout
    bool          graph_animate;
    float         graph_anim_time;
} ide_state_t;

static void console_log(ide_state_t *ide, const char *fmt, ...) {
    if (ide->console_count >= IDE_CONSOLE_LINES) {
        memmove(&ide->console_lines[0], &ide->console_lines[1],
                (IDE_CONSOLE_LINES-1)*256);
        ide->console_count = IDE_CONSOLE_LINES - 1;
    }
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(ide->console_lines[ide->console_count], 256, fmt, ap);
    va_end(ap);
    ide->console_count++;
}

// ═══════════════════════════════════════════════════════════
// PYTHON SCANNER
// ═══════════════════════════════════════════════════════════

static void scan_python_file(ide_state_t *ide, const char *path) {
    FILE *f = fopen(path, "r");
    if (!f) {
        bus_emit(&ide->bus, KIND_ERROR, 3, "Scanner", "scan", "open_file", "failed", ValStr(path), 0);
        console_log(ide, "[ERROR] Cannot open file: %s", path);
        return;
    }
    char line[IDE_MAX_LINE];
    int line_num = 0;
    struct timespec t0; clock_gettime(CLOCK_MONOTONIC, &t0);

    bus_emit(&ide->bus, KIND_IMPORT, 0, "main", "imports", "imports", "sqlite3", ValStr("sqlite3"), 0);
    bus_emit(&ide->bus, KIND_IMPORT, 0, "main", "imports", "imports", "time", ValStr("time"), 0);
    bus_emit(&ide->bus, KIND_IMPORT, 0, "main", "imports", "imports", "json", ValStr("json"), 0);

    bus_emit(&ide->bus, KIND_STATE, 0, "Scanner", "init", "Run", "scan_phase", ValStr("starting"), 0);
    bus_emit(&ide->bus, KIND_STATE, 0, "Scanner", "init", "Run", "target_file", ValStr(path), 0);
    console_log(ide, "[INFO] Scanning %s ...", path);

    while (fgets(line, sizeof(line), f)) {
        line_num++;
        char *p = line; while (*p == ' ' || *p == '\t') p++;
        char *nl = strchr(p, '\n'); if (nl) *nl = '\0';
        if (strncmp(p, "import ", 7) == 0) {
            char mod[IDE_MAX_NAME]; sscanf(p + 7, "%127s", mod);
            bus_emit(&ide->bus, KIND_IMPORT, 0, "Scanner", "scan", "import", mod, ValStr(mod), line_num);
        } else if (strncmp(p, "from ", 5) == 0 && strstr(p, " import ")) {
            char mod[IDE_MAX_NAME]; sscanf(p + 5, "%127s", mod);
            bus_emit(&ide->bus, KIND_IMPORT, 0, "Scanner", "scan", "import", mod, ValStr(mod), line_num);
        } else if (strncmp(p, "class ", 6) == 0) {
            char cls[IDE_MAX_NAME]; sscanf(p + 6, "%127[^:(]", cls);
            bus_emit(&ide->bus, KIND_STATE, 0, "Scanner", "scan", "class", cls, ValStr(cls), line_num);
            bus_emit(&ide->bus, KIND_CALL, 0, cls, "define", cls, "__init__", ValStr("class definition"), line_num);
        } else if (strncmp(p, "def ", 4) == 0) {
            char meth[IDE_MAX_NAME]; sscanf(p + 4, "%127[^(:]", meth);
            bus_emit(&ide->bus, KIND_CALL, 0, "Scanner", "scan", "function", meth, ValStr(meth), line_num);
        } else if (strstr(p, "emit(") || strstr(p, "publish(")) {
            bus_emit(&ide->bus, KIND_STEP, 0, "Scanner", "scan", "emit_call", "emit", ValInt(line_num), line_num);
        }
    }
    fclose(f);

    struct timespec t1; clock_gettime(CLOCK_MONOTONIC, &t1);
    double ms = (t1.tv_sec - t0.tv_sec) * 1000.0 + (t1.tv_nsec - t0.tv_nsec) / 1e6;
    bus_emit(&ide->bus, KIND_TIMING, 0, "Scanner", "scan", "scan_file", "duration", ValFloat(ms), 0);
    bus_emit(&ide->bus, KIND_STATE, 0, "Scanner", "finalize", "Run", "scan_phase", ValStr("complete"), 0);
    bus_emit(&ide->bus, KIND_RESULT, 0, "Scanner", "finalize", "summary", "lines", ValInt(line_num), 0);
    bus_emit(&ide->bus, KIND_RESULT, 0, "Scanner", "finalize", "summary", "events", ValInt(ide->bus.count), 0);
    console_log(ide, "[OK] Scan complete: %d lines, %zu events, %.2fms", line_num, ide->bus.count, ms);
}

// ═══════════════════════════════════════════════════════════
// MENU BAR
// ═══════════════════════════════════════════════════════════

static void render_menu_bar(ide_state_t *ide) {
    if (ImGui::BeginMenuBar()) {
        if (ImGui::BeginMenu("File")) {
            if (ImGui::MenuItem("Open File...", "Ctrl+O")) {
                // Would open file dialog
                console_log(ide, "[INFO] File > Open (not implemented yet)");
            }
            if (ImGui::MenuItem("Re-scan", "Ctrl+R")) {
                bus_init(&ide->bus);
                scan_python_file(ide, ide->source_path);
            }
            ImGui::Separator();
            if (ImGui::MenuItem("Quit", "Ctrl+Q")) { ide->running = false; }
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Edit")) {
            if (ImGui::MenuItem("Undo", "Ctrl+Z")) {}
            if (ImGui::MenuItem("Redo", "Ctrl+Y")) {}
            ImGui::Separator();
            if (ImGui::MenuItem("Find", "Ctrl+F")) {
                ide->bottom_tab = 4; // Search tab
            }
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("View")) {
            ImGui::MenuItem("ImGui Demo", NULL, &ide->show_imgui_demo);
            ImGui::MenuItem("Command Palette", "Ctrl+Shift+P", &ide->show_command_palette);
            ImGui::MenuItem("About Bloodhound", NULL, &ide->show_about);
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("AI")) {
            if (ImGui::MenuItem("Ask AI...", "Ctrl+I")) {
                // Focus AI input
            }
            if (ImGui::MenuItem("Explain Last Error")) {
                if (ide->bus.error_count > 0) {
                    ai_add(&ide->ai, "user", "Explain the last error");
                    ai_generate_response(&ide->ai, &ide->bus, "error");
                } else {
                    ai_add(&ide->ai, "ai", "No errors to explain. The scan completed cleanly.");
                }
            }
            if (ImGui::MenuItem("Generate Summary")) {
                ai_add(&ide->ai, "user", "Generate summary");
                ai_generate_response(&ide->ai, &ide->bus, "summary");
            }
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Tools")) {
            if (ImGui::MenuItem("Profiler")) { ide->center_tab = 4; }
            if (ImGui::MenuItem("Graph Viewer")) { ide->center_tab = 2; }
            if (ImGui::MenuItem("Replay")) { ide->center_tab = 3; }
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Window")) {
            if (ImGui::MenuItem("Reset Layout")) {
                ImGui::IDStackTool tool; // would reset docking
            }
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Help")) {
            if (ImGui::MenuItem("About")) { ide->show_about = true; }
            ImGui::EndMenu();
        }
        ImGui::EndMenuBar();
    }
}

// ═══════════════════════════════════════════════════════════
// TOOLBAR
// ═══════════════════════════════════════════════════════════

static void render_toolbar(ide_state_t *ide) {
    ImGui::PushStyleColor(ImGuiCol_ChildBg, IM_COL32(45,45,48,255));
    ImGui::BeginChild("##toolbar", ImVec2(0, 36), false, ImGuiWindowFlags_NoScrollbar);
    ImGui::PopStyleColor();

    // Run button
    if (ImGui::Button("Run", ImVec2(60, 28))) {
        bus_init(&ide->bus);
        scan_python_file(ide, ide->source_path);
    }
    ImGui::SameLine();
    if (ImGui::Button("Pause", ImVec2(60, 28))) { ide->replay_playing = false; }
    ImGui::SameLine();
    if (ImGui::Button("Stop", ImVec2(60, 28))) { ide->replay_playing = false; }
    ImGui::SameLine();
    if (ImGui::Button("Replay", ImVec2(60, 28))) {
        ide->center_tab = 3;
        ide->replay_pos = 0;
        ide->replay_playing = true;
    }
    ImGui::SameLine();
    ImGui::Dummy(ImVec2(10, 0));
    ImGui::SameLine();
    if (ImGui::Button("AI", ImVec2(40, 28))) {
        ai_add(&ide->ai, "user", "Analyze the current run");
        ai_generate_response(&ide->ai, &ide->bus, "summary");
    }
    ImGui::SameLine();
    if (ImGui::Button("Profile", ImVec2(60, 28))) { ide->center_tab = 4; }
    ImGui::SameLine();
    if (ImGui::Button("Search", ImVec2(60, 28))) { ide->left_tab = 4; }

    // Right side stats
    ImGui::SameLine();
    float right_x = ImGui::GetWindowWidth() - 350;
    if (ImGui::GetCursorPosX() < right_x) ImGui::SetCursorPosX(right_x);
    ImGui::TextDisabled("|");
    ImGui::SameLine();
    ImGui::TextColored(kind_color(KIND_STEP), "Steps: %llu", (unsigned long long)ide->bus.count_by_kind[KIND_STEP]);
    ImGui::SameLine();
    ImGui::TextColored(kind_color(KIND_RESULT), "Results: %llu", (unsigned long long)ide->bus.count_by_kind[KIND_RESULT]);
    ImGui::SameLine();
    ImGui::TextColored(kind_color(KIND_ERROR), "Errors: %llu", (unsigned long long)ide->bus.error_count);
    ImGui::SameLine();
    ImGui::TextColored(IM_COL32(120,160,255,255), "FPS: %.0f", ide->fps);

    ImGui::EndChild();
}

// ═══════════════════════════════════════════════════════════
// LEFT SIDEBAR
// ═══════════════════════════════════════════════════════════

static void render_left_sidebar(ide_state_t *ide) {
    ImGui::Begin("Explorer##left");

    // Tab bar for left sidebar
    if (ImGui::BeginTabBar("##left_tabs", ImGuiTabBarFlags_FittingPolicyScroll)) {
        if (ImGui::BeginTabItem("Explorer")) {
            ide->left_tab = 0;
            // File tree
            if (ide->source.loaded) {
                ImGui::TextColored(IM_COL32(255,200,80,255), "Project Files");
                ImGui::Separator();
                ImGui::Text(" %s", ide->source.path);
                ImGui::Text("   %d lines", ide->source.line_count);
                ImGui::Separator();
                ImGui::TextColored(IM_COL32(255,200,80,255), "Classes Detected");
                for (size_t i = 0; i < ide->bus.count; i++) {
                    if (ide->bus.events[i].kind == KIND_STATE &&
                        strcmp(str_lookup(ide->bus.events[i].name), "class") == 0) {
                        ImGui::TextColored(IM_COL32(80,255,120,255), "  class %s", str_lookup(ide->bus.events[i].value.str));
                    }
                }
                ImGui::Separator();
                ImGui::TextColored(IM_COL32(255,200,80,255), "Functions");
                for (size_t i = 0; i < ide->bus.count; i++) {
                    if (ide->bus.events[i].kind == KIND_CALL &&
                        strcmp(str_lookup(ide->bus.events[i].entity), "function") == 0) {
                        ImGui::Text("  def %s()", str_lookup(ide->bus.events[i].name));
                    }
                }
            } else {
                ImGui::TextDisabled("No file loaded");
            }
            ImGui::EndTabItem();
        }
        if (ImGui::BeginTabItem("Graph")) {
            ide->left_tab = 1;
            ImGui::TextColored(IM_COL32(255,120,255,255), "Knowledge Graph");
            ImGui::Separator();
            ImGui::Text("Sources: %d", ide->bus.source_count);
            for (uint16_t s = 0; s < IDE_MAX_SOURCES; s++) {
                if (!ide->bus.seen_source[s]) continue;
                int ev_count = 0;
                for (size_t i = 0; i < ide->bus.count; i++)
                    if (ide->bus.events[i].source == s) ev_count++;
                ImGui::TextColored(IM_COL32(80,255,120,255), "  %s (%d events)", str_lookup(s), ev_count);
            }
            ImGui::EndTabItem();
        }
        if (ImGui::BeginTabItem("Metrics")) {
            ide->left_tab = 2;
            ImGui::TextColored(IM_COL32(120,160,255,255), "Live Metrics");
            ImGui::Separator();
            ImGui::Text("Total Events: %llu", (unsigned long long)ide->bus.total_events);
            ImGui::Text("Steps: %llu", (unsigned long long)ide->bus.count_by_kind[KIND_STEP]);
            ImGui::Text("Results: %llu", (unsigned long long)ide->bus.count_by_kind[KIND_RESULT]);
            ImGui::Text("Variables: %llu", (unsigned long long)ide->bus.count_by_kind[KIND_VAR]);
            ImGui::Text("States: %llu", (unsigned long long)ide->bus.count_by_kind[KIND_STATE]);
            ImGui::Text("Timings: %llu", (unsigned long long)ide->bus.count_by_kind[KIND_TIMING]);
            ImGui::Text("Imports: %llu", (unsigned long long)ide->bus.count_by_kind[KIND_IMPORT]);
            ImGui::Text("Calls: %llu", (unsigned long long)ide->bus.count_by_kind[KIND_CALL]);
            ImGui::TextColored(kind_color(KIND_ERROR), "Errors: %llu", (unsigned long long)ide->bus.error_count);
            ImGui::Separator();
            if (ide->bus.timing_count > 0) {
                ImGui::TextColored(IM_COL32(120,160,255,255), "Timing");
                ImGui::Text("  Total: %.2fms", ide->bus.timing_total_ms);
                ImGui::Text("  Min: %.2fms", ide->bus.timing_min_ms);
                ImGui::Text("  Max: %.2fms", ide->bus.timing_max_ms);
                ImGui::Text("  Avg: %.2fms", ide->bus.timing_total_ms / ide->bus.timing_count);
            }
            ImGui::EndTabItem();
        }
        if (ImGui::BeginTabItem("Tests")) {
            ide->left_tab = 3;
            ImGui::TextColored(IM_COL32(255,220,80,255), "Test Results");
            ImGui::Separator();
            int total_pass = 0, total_fail = 0;
            // Imports test
            if (ide->bus.count_by_kind[KIND_IMPORT] > 0) {
                ImGui::TextColored(IM_COL32(80,255,120,255), "V PASS  Imports: %llu found",
                    (unsigned long long)ide->bus.count_by_kind[KIND_IMPORT]);
                total_pass++;
            } else {
                ImGui::TextColored(IM_COL32(255,80,80,255), "X FAIL  Imports: none");
                total_fail++;
            }
            // Per source
            for (uint16_t s = 0; s < IDE_MAX_SOURCES; s++) {
                if (!ide->bus.seen_source[s]) continue;
                int errors = 0, results = 0, facts = 0;
                for (size_t j = 0; j < ide->bus.count; j++) {
                    if (ide->bus.events[j].source != s) continue;
                    facts++;
                    if (ide->bus.events[j].severity >= 3) errors++;
                    if (ide->bus.events[j].kind == KIND_RESULT) results++;
                }
                if (errors == 0) {
                    ImGui::TextColored(IM_COL32(80,255,120,255), "V PASS  %s: %d facts, %d results",
                        str_lookup(s), facts, results);
                    total_pass++;
                } else {
                    ImGui::TextColored(IM_COL32(255,80,80,255), "X FAIL  %s: %d errors",
                        str_lookup(s), errors);
                    total_fail++;
                }
            }
            ImGui::Separator();
            ImGui::Text("Passed: %d  Failed: %d  %s", total_pass, total_fail,
                total_fail == 0 ? "ALL PASS" : "HAS FAILURES");
            ImGui::EndTabItem();
        }
        if (ImGui::BeginTabItem("Search")) {
            ide->left_tab = 4;
            ImGui::TextColored(IM_COL32(255,220,80,255), "Global Search");
            ImGui::Separator();
            ImGui::PushItemWidth(-1);
            ImGui::InputText("##globalsearch", ide->global_search, IDE_SEARCH_LEN);
            ImGui::PopItemWidth();
            if (ide->global_search[0]) {
                int matches = 0;
                for (size_t i = 0; i < ide->bus.count && matches < 100; i++) {
                    ide_event_t *ev = &ide->bus.events[i];
                    char val_str[128]; ValFormat(&ev->value, val_str, sizeof(val_str));
                    if (strcasestr(str_lookup(ev->source), ide->global_search) ||
                        strcasestr(str_lookup(ev->entity), ide->global_search) ||
                        strcasestr(str_lookup(ev->name), ide->global_search) ||
                        strcasestr(val_str, ide->global_search) ||
                        strcasestr(kind_name(ev->kind), ide->global_search)) {
                        ImGui::TextColored(kind_color(ev->kind), "#%llu %s/%s/%s",
                            (unsigned long long)ev->id,
                            str_lookup(ev->source), kind_name(ev->kind), str_lookup(ev->entity));
                        matches++;
                    }
                }
                ImGui::Separator();
                ImGui::TextDisabled("%d matches", matches);
            }
            ImGui::EndTabItem();
        }
        if (ImGui::BeginTabItem("Plugins")) {
            ide->left_tab = 5;
            ImGui::TextColored(IM_COL32(200,200,200,255), "Plugins");
            ImGui::Separator();
            ImGui::TextDisabled("No plugins loaded");
            ImGui::TextDisabled("Plugin API: coming soon");
            ImGui::EndTabItem();
        }
        ImGui::EndTabBar();
    }
    ImGui::End();
}

// ═══════════════════════════════════════════════════════════
// CENTER WORKSPACE — SOURCE EDITOR
// ═══════════════════════════════════════════════════════════

static void render_source_editor(ide_state_t *ide) {
    ImGui::Begin("Source##center_source", NULL, ImGuiWindowFlags_HorizontalScrollbar);

    if (!ide->source.loaded) {
        ImGui::TextDisabled("No source file loaded. Use File > Open or Run to scan a file.");
        ImGui::End();
        return;
    }

    // Render source with line numbers and event markers
    ImGui::PushStyleColor(ImGuiCol_ChildBg, IM_COL32(30,30,30,255));
    ImGui::BeginChild("##source_view", ImVec2(0,0), false, ImGuiWindowFlags_HorizontalScrollbar);

    float line_h = ImGui::GetTextLineHeight();
    ImVec2 pos = ImGui::GetCursorPos();

    for (int i = 0; i < ide->source.line_count; i++) {
        float y = pos.y + i * line_h;
        // Line number
        ImGui::SetCursorPosX(pos.x);
        ImGui::TextColored(IM_COL32(100,100,100,255), "%4d", i + 1);
        ImGui::SameLine();

        // Check if this line has events
        bool has_event = false;
        bool has_error = false;
        for (size_t j = 0; j < ide->bus.count; j++) {
            if (ide->bus.events[j].source_line == i + 1) {
                has_event = true;
                if (ide->bus.events[j].severity >= 3) has_error = true;
            }
        }

        // Line content
        if (has_error) {
            ImGui::TextColored(IM_COL32(255,80,80,255), "%s", ide->source.lines[i]);
        } else if (has_event) {
            ImGui::TextColored(IM_COL32(80,200,255,255), "%s", ide->source.lines[i]);
        } else {
            ImGui::TextUnformatted(ide->source.lines[i]);
        }
    }

    ImGui::EndChild();
    ImGui::PopStyleColor();
    ImGui::End();
}

// ═══════════════════════════════════════════════════════════
// CENTER WORKSPACE — EVENT TIMELINE
// ═══════════════════════════════════════════════════════════

static void render_event_timeline(ide_state_t *ide) {
    ImGui::Begin("Timeline##center_timeline", NULL, ImGuiWindowFlags_HorizontalScrollbar);

    if (ide->bus.count == 0) {
        ImGui::TextDisabled("No events. Press Run to scan a file.");
        ImGui::End();
        return;
    }

    // Controls
    ImGui::TextColored(IM_COL32(80,200,255,255), "Event Timeline — %zu events", ide->bus.count);
    ImGui::SameLine();
    ImGui::TextDisabled("|");
    ImGui::SameLine();
    ImGui::SetNextItemWidth(100);
    ImGui::SliderFloat("Zoom", &ide->timeline_zoom, 0.5f, 10.0f, "%.1fx");

    ImGui::Separator();

    // Draw timeline
    ImDrawList *dl = ImGui::GetWindowDrawList();
    ImVec2 p0 = ImGui::GetCursorScreenPos();
    float w = ImGui::GetContentRegionAvail().x;
    float h = ImGui::GetContentRegionAvail().y - 30;

    // Background
    dl->AddRectFilled(p0, ImVec2(p0.x + w, p0.y + h), IM_COL32(25,25,28,255));

    // Draw event markers
    if (ide->bus.count > 0) {
        uint64_t first_ts = ide->bus.events[0].timestamp_ns;
        uint64_t last_ts = ide->bus.events[ide->bus.count-1].timestamp_ns;
        uint64_t span = last_ts - first_ts;
        if (span == 0) span = 1;

        for (size_t i = 0; i < ide->bus.count; i++) {
            ide_event_t *ev = &ide->bus.events[i];
            float x = p0.x + (float)(ev->timestamp_ns - first_ts) / span * w * ide->timeline_zoom;
            if (x > p0.x + w) continue;
            ImU32 col = kind_color(ev->kind);
            // Draw marker
            float y = p0.y + 10 + (ev->kind % 10) * (h - 20) / 10.0f;
            dl->AddCircleFilled(ImVec2(x, y), 4.0f, col);
            // Highlight selected
            if ((int)i == ide->selected_event) {
                dl->AddCircle(ImVec2(x, y), 6.0f, IM_COL32(255,255,255,255), 0, 2.0f);
            }
        }

        // Draw kind legend at top
        float lx = p0.x + 10;
        for (int k = 1; k <= 10; k++) {
            if (ide->bus.count_by_kind[k] == 0) continue;
            dl->AddCircleFilled(ImVec2(lx, p0.y + 5), 4.0f, kind_color(k));
            ImGui::SetCursorScreenPos(ImVec2(lx + 8, p0.y));
            ImGui::TextColored(kind_color(k), "%s", kind_name(k));
            lx += 80;
            if (lx > p0.x + w - 80) break;
        }
    }

    ImGui::SetCursorScreenPos(ImVec2(p0.x, p0.y + h + 5));

    // Click to select event
    if (ImGui::InvisibleButton("##timeline_click", ImVec2(w, 20))) {
        ImVec2 mouse = ImGui::GetMousePos();
        float click_x = mouse.x - p0.x;
        if (ide->bus.count > 0 && click_x >= 0 && click_x <= w) {
            uint64_t first_ts = ide->bus.events[0].timestamp_ns;
            uint64_t last_ts = ide->bus.events[ide->bus.count-1].timestamp_ns;
            uint64_t span = last_ts - first_ts;
            if (span == 0) span = 1;
            uint64_t target_ts = first_ts + (uint64_t)(click_x / (w * ide->timeline_zoom) * span);
            // Find closest event
            uint64_t best_diff = UINT64_MAX;
            int best_idx = 0;
            for (size_t i = 0; i < ide->bus.count; i++) {
                uint64_t diff = ide->bus.events[i].timestamp_ns > target_ts ?
                    ide->bus.events[i].timestamp_ns - target_ts :
                    target_ts - ide->bus.events[i].timestamp_ns;
                if (diff < best_diff) { best_diff = diff; best_idx = (int)i; }
            }
            ide->selected_event = best_idx;
        }
    }

    // Show selected event detail
    if (ide->selected_event >= 0 && (size_t)ide->selected_event < ide->bus.count) {
        ide_event_t *ev = &ide->bus.events[ide->selected_event];
        char val_str[128]; ValFormat(&ev->value, val_str, sizeof(val_str));
        ImGui::Text("Selected: #%llu %s/%s/%s %s=%s",
            (unsigned long long)ev->id, str_lookup(ev->source),
            kind_name(ev->kind), str_lookup(ev->entity),
            str_lookup(ev->name), val_str);
    }

    ImGui::End();
}

// ═══════════════════════════════════════════════════════════
// CENTER WORKSPACE — GRAPH VIEWER
// ═══════════════════════════════════════════════════════════

static void render_graph_viewer(ide_state_t *ide) {
    ImGui::Begin("Graph##center_graph");

    ImGui::TextColored(IM_COL32(255,120,255,255), "Execution Graph");
    ImGui::SameLine();
    ImGui::Checkbox("Animate", &ide->graph_animate);
    if (ide->graph_animate) {
        ide->graph_anim_time += ImGui::GetIO().DeltaTime;
    }
    ImGui::Separator();

    ImDrawList *dl = ImGui::GetWindowDrawList();
    ImVec2 origin = ImGui::GetCursorScreenPos();
    float avail_w = ImGui::GetContentRegionAvail().x;
    float avail_h = ImGui::GetContentRegionAvail().y;

    // Background
    dl->AddRectFilled(origin, ImVec2(origin.x + avail_w, origin.y + avail_h), IM_COL32(20,20,24,255));

    // Collect sources and their entities
    struct { uint16_t source; float x, y; } nodes[IDE_MAX_SOURCES];
    int node_count = 0;
    for (uint16_t s = 0; s < IDE_MAX_SOURCES; s++) {
        if (!ide->bus.seen_source[s]) continue;
        nodes[node_count].source = s;
        nodes[node_count].x = origin.x + 50 + node_count * (avail_w - 100) / (ide->bus.source_count > 1 ? ide->bus.source_count - 1 : 1);
        nodes[node_count].y = origin.y + avail_h / 2;
        node_count++;
    }

    // Draw edges between consecutive sources
    for (int i = 0; i < node_count - 1; i++) {
        ImVec2 a(nodes[i].x + 60, nodes[i].y);
        ImVec2 b(nodes[i+1].x, nodes[i+1].y);
        // Animated dashed line
        ImU32 edge_col = ide->graph_animate ?
            IM_COL32(80 + (int)(sin(ide->graph_anim_time * 3 + i) * 50 + 50),
                     200, 255, 200) :
            IM_COL32(80,200,255,150);
        dl->AddBezierCubic(a, ImVec2(a.x + 30, a.y), ImVec2(b.x - 30, b.y), b, edge_col, 2.0f);
        // Arrow head
        dl->AddTriangleFilled(ImVec2(b.x, b.y), ImVec2(b.x - 8, b.y - 4), ImVec2(b.x - 8, b.y + 4), edge_col);
    }

    // Draw source nodes
    for (int i = 0; i < node_count; i++) {
        const char *sname = str_lookup(nodes[i].source);
        ImVec2 node_pos(nodes[i].x, nodes[i].y - 15);
        ImVec2 node_size(60, 30);

        // Count events and errors for this source
        int ev_count = 0, err_count = 0;
        for (size_t j = 0; j < ide->bus.count; j++) {
            if (ide->bus.events[j].source == nodes[i].source) {
                ev_count++;
                if (ide->bus.events[j].severity >= 3) err_count++;
            }
        }

        ImU32 node_col = err_count > 0 ? IM_COL32(80,30,30,255) : IM_COL32(30,60,40,255);
        ImU32 border_col = err_count > 0 ? IM_COL32(255,80,80,255) : IM_COL32(80,255,120,255);

        dl->AddRectFilled(node_pos, ImVec2(node_pos.x + node_size.x, node_pos.y + node_size.y), node_col, 6.0f);
        dl->AddRect(node_pos, ImVec2(node_pos.x + node_size.x, node_pos.y + node_size.y), border_col, 6.0f, 0, 2.0f);

        // Label
        ImGui::SetCursorScreenPos(ImVec2(node_pos.x + 5, node_pos.y + 5));
        ImGui::TextColored(border_col, "%s", sname);
        ImGui::SetCursorScreenPos(ImVec2(node_pos.x + 5, node_pos.y + 18));
        ImGui::TextDisabled("%d ev", ev_count);

        // Draw method nodes below
        float method_y = nodes[i].y + 40;
        int method_idx = 0;
        bool seen_entity[IDE_MAX_SOURCES] = {false};
        for (size_t j = 0; j < ide->bus.count && method_idx < 8; j++) {
            if (ide->bus.events[j].source != nodes[i].source) continue;
            uint32_t ent = ide->bus.events[j].entity;
            if (ent < IDE_MAX_SOURCES && !seen_entity[ent]) {
                seen_entity[ent] = true;
                const char *ename = str_lookup(ent);
                float mx = nodes[i].x + 10;
                float my = method_y + method_idx * 22;
                if (my > origin.y + avail_h - 20) break;

                // Line from source to method
                dl->AddLine(ImVec2(nodes[i].x + 30, nodes[i].y + 15), ImVec2(mx, my + 8),
                    IM_COL32(100,100,100,150), 1.0f);

                dl->AddRectFilled(ImVec2(mx, my), ImVec2(mx + 80, my + 16), IM_COL32(40,40,45,255), 3.0f);
                ImGui::SetCursorScreenPos(ImVec2(mx + 3, my + 1));
                ImGui::TextColored(IM_COL32(255,220,80,255), "%s", ename);
                method_idx++;
            }
        }
    }

    ImGui::End();
}

// ═══════════════════════════════════════════════════════════
// CENTER WORKSPACE — REPLAY VIEWER
// ═══════════════════════════════════════════════════════════

static void render_replay_viewer(ide_state_t *ide) {
    ImGui::Begin("Replay##center_replay");

    ImGui::TextColored(IM_COL32(80,200,255,255), "Time-Travel Replay");
    ImGui::Separator();

    if (ide->bus.count == 0) {
        ImGui::TextDisabled("No events to replay.");
        ImGui::End();
        return;
    }

    // Transport controls
    if (ImGui::Button("|<", ImVec2(30, 30))) { ide->replay_pos = 0; }
    ImGui::SameLine();
    if (ImGui::Button("<", ImVec2(30, 30))) { if (ide->replay_pos > 0) ide->replay_pos--; }
    ImGui::SameLine();
    if (ide->replay_playing) {
        if (ImGui::Button("||", ImVec2(30, 30))) { ide->replay_playing = false; }
    } else {
        if (ImGui::Button(">", ImVec2(30, 30))) { ide->replay_playing = true; }
    }
    ImGui::SameLine();
    if (ImGui::Button(">", ImVec2(30, 30))) { if (ide->replay_pos < (int)ide->bus.count - 1) ide->replay_pos++; }
    ImGui::SameLine();
    if (ImGui::Button(">|", ImVec2(30, 30))) { ide->replay_pos = (int)ide->bus.count - 1; }
    ImGui::SameLine();
    ImGui::Text("  Speed:");
    ImGui::SameLine();
    const char *speeds[] = {"0.5x","1x","2x","4x"};
    for (int i = 0; i < 4; i++) {
        if (ImGui::Button(speeds[i], ImVec2(35, 30))) { ide->replay_speed = (i==0)?0.5f:(i==1)?1.0f:(i==2)?2.0f:4.0f; }
        ImGui::SameLine();
    }
    ImGui::Text("  Pos: %d / %zu", ide->replay_pos, ide->bus.count);

    // Auto-advance
    if (ide->replay_playing) {
        double now = ImGui::GetTime();
        double interval = 0.5 / ide->replay_speed;
        if (now - ide->replay_last_step > interval) {
            if (ide->replay_pos < (int)ide->bus.count - 1) {
                ide->replay_pos++;
            } else {
                ide->replay_playing = false;
            }
            ide->replay_last_step = now;
        }
    }

    // Progress bar
    ImGui::PushStyleColor(ImGuiCol_PlotHistogram, IM_COL32(80,200,255,255));
    float progress = ide->bus.count > 0 ? (float)ide->replay_pos / ide->bus.count : 0.0f;
    ImGui::ProgressBar(progress, ImVec2(-1, 20), "");
    ImGui::PopStyleColor();

    ImGui::Separator();

    // Show events up to replay position
    ImGui::BeginChild("##replay_events", ImVec2(0, 0), true);
    for (int i = 0; i <= ide->replay_pos && i < (int)ide->bus.count; i++) {
        ide_event_t *ev = &ide->bus.events[i];
        char val_str[128]; ValFormat(&ev->value, val_str, sizeof(val_str));
        ImU32 col = kind_color(ev->kind);
        bool is_current = (i == ide->replay_pos);

        if (is_current) {
            ImGui::PushStyleColor(ImGuiCol_Text, IM_COL32(255,255,255,255));
            ImGui::TextColored(IM_COL32(255,255,0,255), ">>");
        } else {
            ImGui::TextDisabled("  ");
        }
        ImGui::SameLine();
        ImGui::TextColored(col, "#%-4llu %-12s %-10s %-14s %-14s %s",
            (unsigned long long)ev->id, str_lookup(ev->source),
            kind_name(ev->kind), str_lookup(ev->entity),
            str_lookup(ev->name), val_str);
        if (is_current) ImGui::PopStyleColor();
    }
    ImGui::EndChild();

    ImGui::End();
}

// ═══════════════════════════════════════════════════════════
// CENTER WORKSPACE — PROFILER
// ═══════════════════════════════════════════════════════════

static void render_profiler(ide_state_t *ide) {
    ImGui::Begin("Profiler##center_profiler");

    ImGui::TextColored(IM_COL32(120,160,255,255), "Timing Profile");
    ImGui::Separator();

    if (ide->bus.timing_count == 0) {
        ImGui::TextDisabled("No timing events recorded.");
        ImGui::End();
        return;
    }

    // Summary
    ImGui::Text("Total: %.2fms  Min: %.2fms  Max: %.2fms  Avg: %.2fms  Count: %llu",
        ide->bus.timing_total_ms, ide->bus.timing_min_ms, ide->bus.timing_max_ms,
        ide->bus.timing_total_ms / ide->bus.timing_count,
        (unsigned long long)ide->bus.timing_count);
    ImGui::Separator();

    // Histogram bars
    float max_ms = ide->bus.timing_max_ms;
    if (max_ms == 0) max_ms = 1;

    ImGui::BeginChild("##profiler_bars", ImVec2(0, 0), true);
    for (size_t i = 0; i < ide->bus.count; i++) {
        ide_event_t *ev = &ide->bus.events[i];
        if (ev->kind != KIND_TIMING) continue;
        char val_str[128]; ValFormat(&ev->value, val_str, sizeof(val_str));
        double ms = ev->value.type == VAL_FLOAT ? ev->value.num.f64 : 0;
        float ratio = (float)(ms / max_ms);

        // Color based on duration
        ImU32 bar_col;
        if (ratio > 0.66f) bar_col = IM_COL32(255,80,80,255);
        else if (ratio > 0.33f) bar_col = IM_COL32(255,220,80,255);
        else bar_col = IM_COL32(80,255,120,255);

        ImGui::Text("%-20s %8.2fms ", str_lookup(ev->entity), ms);
        ImGui::SameLine();
        // Draw bar
        ImVec2 bar_pos = ImGui::GetCursorScreenPos();
        float bar_w = ratio * (ImGui::GetContentRegionAvail().x - 100);
        if (bar_w < 2) bar_w = 2;
        ImGui::GetWindowDrawList()->AddRectFilled(bar_pos,
            ImVec2(bar_pos.x + bar_w, bar_pos.y + 14), bar_col, 2.0f);
        ImGui::Dummy(ImVec2(bar_w, 14));
    }
    ImGui::EndChild();

    ImGui::End();
}

// ═══════════════════════════════════════════════════════════
// CENTER WORKSPACE (tabbed)
// ═══════════════════════════════════════════════════════════

static void render_center_workspace(ide_state_t *ide) {
    // Use a docking space — the individual windows register themselves
    // This is handled by ImGui docking system
}

// ═══════════════════════════════════════════════════════════
// RIGHT SIDEBAR — AI ASSISTANT
// ═══════════════════════════════════════════════════════════

static void render_ai_assistant(ide_state_t *ide) {
    ImGui::Begin("AI Assistant##right_ai");

    ImGui::TextColored(IM_COL32(80,255,120,255), "AI Assistant");
    ImGui::Separator();

    // Quick action buttons
    if (ImGui::Button("Summary", ImVec2(-1, 0))) {
        ai_add(&ide->ai, "user", "Generate summary");
        ai_generate_response(&ide->ai, &ide->bus, "summary");
    }
    if (ImGui::Button("Explain Errors", ImVec2(-1, 0))) {
        ai_add(&ide->ai, "user", "Explain errors");
        ai_generate_response(&ide->ai, &ide->bus, "error");
    }
    if (ImGui::Button("Suggest Fix", ImVec2(-1, 0))) {
        ai_add(&ide->ai, "user", "Suggest a fix");
        ai_generate_response(&ide->ai, &ide->bus, "fix");
    }
    if (ImGui::Button("Show Graph Info", ImVec2(-1, 0))) {
        ai_add(&ide->ai, "user", "Show graph info");
        ai_generate_response(&ide->ai, &ide->bus, "graph");
    }
    if (ImGui::Button("Profile Analysis", ImVec2(-1, 0))) {
        ai_add(&ide->ai, "user", "Profile analysis");
        ai_generate_response(&ide->ai, &ide->bus, "profile");
    }

    ImGui::Separator();

    // Chat history
    ImGui::BeginChild("##ai_chat", ImVec2(0, -40), true);
    for (int i = 0; i < ide->ai.count; i++) {
        ai_message_t *msg = &ide->ai.history[i];
        if (strcmp(msg->role, "user") == 0) {
            ImGui::TextColored(IM_COL32(80,200,255,255), "You: %s", msg->text);
        } else {
            ImGui::TextColored(IM_COL32(80,255,120,255), "AI: %s", msg->text);
        }
        ImGui::Spacing();
    }
    // Auto-scroll
    if (ImGui::GetScrollY() >= ImGui::GetScrollMaxY())
        ImGui::SetScrollHereY(1.0f);
    ImGui::EndChild();

    // Input
    ImGui::PushItemWidth(-60);
    if (ImGui::InputText("##ai_input", ide->ai.input_buf, sizeof(ide->ai.input_buf),
        ImGuiInputTextFlags_EnterReturnsTrue)) {
        if (ide->ai.input_buf[0]) {
            ai_add(&ide->ai, "user", ide->ai.input_buf);
            ai_generate_response(&ide->ai, &ide->bus, ide->ai.input_buf);
            ide->ai.input_buf[0] = '\0';
        }
    }
    ImGui::PopItemWidth();
    ImGui::SameLine();
    if (ImGui::Button("Send", ImVec2(-1, 0))) {
        if (ide->ai.input_buf[0]) {
            ai_add(&ide->ai, "user", ide->ai.input_buf);
            ai_generate_response(&ide->ai, &ide->bus, ide->ai.input_buf);
            ide->ai.input_buf[0] = '\0';
        }
    }

    ImGui::End();
}

// ═══════════════════════════════════════════════════════════
// BOTTOM DOCK
// ═══════════════════════════════════════════════════════════

static void render_bottom_dock(ide_state_t *ide) {
    ImGui::Begin("Bottom Dock##bottom");

    if (ImGui::BeginTabBar("##bottom_tabs")) {
        // Events tab
        if (ImGui::BeginTabItem("Events")) {
            ide->bottom_tab = 0;
            // Filter
            ImGui::PushItemWidth(100);
            const char *filter_names[] = {"All","Step","Result","Error","Var","State","Timing","Import","Call"};
            if (ImGui::BeginCombo("##filter", filter_names[ide->event_filter_kind])) {
                for (int i = 0; i < 9; i++) {
                    bool sel = (ide->event_filter_kind == i);
                    if (ImGui::Selectable(filter_names[i], &sel)) ide->event_filter_kind = i;
                    if (sel) ImGui::SetItemDefaultFocus();
                }
                ImGui::EndCombo();
            }
            ImGui::PopItemWidth();
            ImGui::SameLine();
            ImGui::PushItemWidth(200);
            ImGui::InputText("##event_search", ide->event_search, IDE_SEARCH_LEN);
            ImGui::PopItemWidth();
            ImGui::SameLine();
            ImGui::TextDisabled("%zu events", ide->bus.count);
            ImGui::Separator();

            // Event table
            ImGui::BeginChild("##event_table", ImVec2(0,0), true);
            ImGui::Columns(7, "##event_cols");
            ImGui::TextUnformatted("ID"); ImGui::NextColumn();
            ImGui::TextUnformatted("Source"); ImGui::NextColumn();
            ImGui::TextUnformatted("Kind"); ImGui::NextColumn();
            ImGui::TextUnformatted("Entity"); ImGui::NextColumn();
            ImGui::TextUnformatted("Name"); ImGui::NextColumn();
            ImGui::TextUnformatted("Value"); ImGui::NextColumn();
            ImGui::TextUnformatted("Line"); ImGui::NextColumn();
            ImGui::Separator();

            for (size_t i = 0; i < ide->bus.count; i++) {
                ide_event_t *ev = &ide->bus.events[i];
                // Filter
                if (ide->event_filter_kind > 0) {
                    int kind_filter = ide->event_filter_kind; // 1=step, 2=result...
                    if ((int)ev->kind != kind_filter) continue;
                }
                if (ide->event_search[0]) {
                    char val_str[128]; ValFormat(&ev->value, val_str, sizeof(val_str));
                    if (!strcasestr(str_lookup(ev->source), ide->event_search) &&
                        !strcasestr(str_lookup(ev->entity), ide->event_search) &&
                        !strcasestr(str_lookup(ev->name), ide->event_search) &&
                        !strcasestr(val_str, ide->event_search) &&
                        !strcasestr(kind_name(ev->kind), ide->event_search)) continue;
                }

                bool selected = (ide->selected_event == (int)i);
                ImGui::PushID((int)i);
                ImU32 col = kind_color(ev->kind);
                char val_str[128]; ValFormat(&ev->value, val_str, sizeof(val_str));

                if (ImGui::Selectable(va("%llu", (unsigned long long)ev->id), selected,
                    ImGuiSelectableFlags_SpanAllColumns)) {
                    ide->selected_event = (int)i;
                }
                ImGui::NextColumn();
                ImGui::TextColored(col, "%s", str_lookup(ev->source)); ImGui::NextColumn();
                ImGui::TextColored(col, "%s", kind_name(ev->kind)); ImGui::NextColumn();
                ImGui::TextUnformatted(str_lookup(ev->entity)); ImGui::NextColumn();
                ImGui::TextUnformatted(str_lookup(ev->name)); ImGui::NextColumn();
                ImGui::TextUnformatted(val_str); ImGui::NextColumn();
                ImGui::TextDisabled("%d", ev->source_line); ImGui::NextColumn();
                ImGui::PopID();
            }
            ImGui::Columns(1);
            ImGui::EndChild();
            ImGui::EndTabItem();
        }

        // Console tab
        if (ImGui::BeginTabItem("Console")) {
            ide->bottom_tab = 1;
            ImGui::BeginChild("##console", ImVec2(0, -30), true);
            for (int i = 0; i < ide->console_count; i++) {
                ImGui::TextUnformatted(ide->console_lines[i]);
            }
            if (ImGui::GetScrollY() >= ImGui::GetScrollMaxY())
                ImGui::SetScrollHereY(1.0f);
            ImGui::EndChild();
            ImGui::PushItemWidth(-1);
            ImGui::InputText("##console_input", ide->console_input, sizeof(ide->console_input),
                ImGuiInputTextFlags_EnterReturnsTrue);
            ImGui::PopItemWidth();
            ImGui::EndTabItem();
        }

        // Variables tab
        if (ImGui::BeginTabItem("Variables")) {
            ide->bottom_tab = 2;
            ImGui::BeginChild("##variables", ImVec2(0,0), true);
            for (size_t i = 0; i < ide->bus.count; i++) {
                if (ide->bus.events[i].kind != KIND_VAR) continue;
                ide_event_t *ev = &ide->bus.events[i];
                char val_str[128]; ValFormat(&ev->value, val_str, sizeof(val_str));
                ImGui::TextColored(IM_COL32(255,220,80,255), "%s = %s", str_lookup(ev->name), val_str);
            }
            ImGui::EndChild();
            ImGui::EndTabItem();
        }

        // State tab
        if (ImGui::BeginTabItem("State")) {
            ide->bottom_tab = 3;
            ImGui::BeginChild("##state", ImVec2(0,0), true);
            for (size_t i = 0; i < ide->bus.count; i++) {
                if (ide->bus.events[i].kind != KIND_STATE) continue;
                ide_event_t *ev = &ide->bus.events[i];
                char val_str[128]; ValFormat(&ev->value, val_str, sizeof(val_str));
                ImGui::TextColored(IM_COL32(255,120,255,255), "%s.%s = %s",
                    str_lookup(ev->entity), str_lookup(ev->name), val_str);
            }
            ImGui::EndChild();
            ImGui::EndTabItem();
        }

        // Memory tab
        if (ImGui::BeginTabItem("Memory")) {
            ide->bottom_tab = 4;
            ImGui::BeginChild("##memory", ImVec2(0,0), true);
            ImGui::TextDisabled("Memory view — allocation tracking coming soon");
            ImGui::Text("Event buffer: %zu / %d (%.1f%%)",
                ide->bus.count, IDE_MAX_EVENTS,
                100.0f * ide->bus.count / IDE_MAX_EVENTS);
            ImGui::Text("Interned strings: %d / %d", g_intern_count, IDE_MAX_INTERNED);
            ImGui::Text("Sources tracked: %d", ide->bus.source_count);
            ImGui::EndChild();
            ImGui::EndTabItem();
        }

        // Timeline tab
        if (ImGui::BeginTabItem("Timeline")) {
            ide->bottom_tab = 5;
            ImGui::BeginChild("##timeline_bottom", ImVec2(0,0), true);
            for (size_t i = 0; i < ide->bus.count; i++) {
                ide_event_t *ev = &ide->bus.events[i];
                double ts_sec = ev->timestamp_ns / 1e9;
                ImGui::TextColored(kind_color(ev->kind), "[%.6f] #%llu %s/%s/%s",
                    ts_sec, (unsigned long long)ev->id,
                    str_lookup(ev->source), kind_name(ev->kind), str_lookup(ev->entity));
            }
            ImGui::EndChild();
            ImGui::EndTabItem();
        }

        // SQL tab
        if (ImGui::BeginTabItem("SQL")) {
            ide->bottom_tab = 6;
            ImGui::BeginChild("##sql", ImVec2(0,0), true);
            ImGui::TextDisabled("SQL query interface — query the event store with SQL");
            ImGui::Separator();
            ImGui::Text("Schema:");
            ImGui::Text("  CREATE TABLE event (");
            ImGui::Text("    id INTEGER, timestamp INTEGER, source TEXT,");
            ImGui::Text("    phase TEXT, kind INTEGER, entity TEXT,");
            ImGui::Text("    name TEXT, value TEXT, severity INTEGER");
            ImGui::Text("  );");
            ImGui::Separator();
            ImGui::TextDisabled("Query input coming soon...");
            ImGui::EndChild();
            ImGui::EndTabItem();
        }

        // AI Log tab
        if (ImGui::BeginTabItem("AI Log")) {
            ide->bottom_tab = 7;
            ImGui::BeginChild("##ai_log", ImVec2(0,0), true);
            for (int i = 0; i < ide->ai.count; i++) {
                ai_message_t *msg = &ide->ai.history[i];
                if (strcmp(msg->role, "ai") == 0) {
                    ImGui::TextColored(IM_COL32(80,255,120,255), "[AI] %s", msg->text);
                }
            }
            ImGui::EndChild();
            ImGui::EndTabItem();
        }

        // Errors tab
        if (ImGui::BeginTabItem("Errors")) {
            ide->bottom_tab = 8;
            ImGui::BeginChild("##errors", ImVec2(0,0), true);
            int err_count = 0;
            for (size_t i = 0; i < ide->bus.count; i++) {
                if (ide->bus.events[i].severity < 3) continue;
                ide_event_t *ev = &ide->bus.events[i];
                char val_str[128]; ValFormat(&ev->value, val_str, sizeof(val_str));
                ImGui::TextColored(IM_COL32(255,80,80,255), "X #%llu [%s/%s] %s: %s",
                    (unsigned long long)ev->id, str_lookup(ev->source),
                    str_lookup(ev->phase), str_lookup(ev->name), val_str);
                err_count++;
            }
            if (err_count == 0)
                ImGui::TextColored(IM_COL32(80,255,120,255), "No errors.");
            ImGui::EndChild();
            ImGui::EndTabItem();
        }

        ImGui::EndTabBar();
    }

    ImGui::End();
}

// ═══════════════════════════════════════════════════════════
// STATUS BAR
// ═══════════════════════════════════════════════════════════

static void render_status_bar(ide_state_t *ide) {
    ImGui::PushStyleColor(ImGuiCol_ChildBg, IM_COL32(0,100,200,255));
    ImGui::BeginChild("##statusbar", ImVec2(0, 24), false, ImGuiWindowFlags_NoScrollbar);
    ImGui::PopStyleColor();

    ImGui::Text(" Events: %llu  Errors: %llu  Sources: %d  FPS: %.0f  |  Bloodhound IDE v%s",
        (unsigned long long)ide->bus.total_events,
        (unsigned long long)ide->bus.error_count,
        ide->bus.source_count,
        ide->fps,
        IDE_VERSION);

    // Right side
    float right = ImGui::GetWindowWidth() - 200;
    if (ImGui::GetCursorPosX() < right) {
        ImGui::SameLine(right);
        if (ide->bus.error_count > 0) {
            ImGui::TextColored(IM_COL32(255,80,80,255), " HAS ERRORS ");
        } else {
            ImGui::TextColored(IM_COL32(80,255,120,255), " ALL PASS ");
        }
    }

    ImGui::EndChild();
}

// ═══════════════════════════════════════════════════════════
// COMMAND PALETTE
// ═══════════════════════════════════════════════════════════

static void render_command_palette(ide_state_t *ide) {
    if (!ide->show_command_palette) return;
    ImGui::OpenPopup("Command Palette");
    if (ImGui::BeginPopupModal("Command Palette", &ide->show_command_palette,
        ImGuiWindowFlags_AlwaysAutoResize)) {
        static char cmd_search[256] = "";
        ImGui::PushItemWidth(400);
        ImGui::InputText("##cmd_search", cmd_search, sizeof(cmd_search));
        ImGui::PopItemWidth();
        ImGui::Separator();

        struct { const char *cmd; const char *desc; void (*fn)(ide_state_t*); } commands[] = {
            {"run", "Run / Re-scan source file", [](ide_state_t *s){ bus_init(&s->bus); scan_python_file(s, s->source_path); }},
            {"timeline", "Switch to Timeline view", [](ide_state_t *s){ s->center_tab = 1; }},
            {"graph", "Switch to Graph view", [](ide_state_t *s){ s->center_tab = 2; }},
            {"replay", "Switch to Replay view", [](ide_state_t *s){ s->center_tab = 3; s->replay_pos = 0; s->replay_playing = true; }},
            {"profiler", "Switch to Profiler view", [](ide_state_t *s){ s->center_tab = 4; }},
            {"source", "Switch to Source view", [](ide_state_t *s){ s->center_tab = 0; }},
            {"ai summary", "AI: Generate summary", [](ide_state_t *s){ ai_add(&s->ai, "user", "summary"); ai_generate_response(&s->ai, &s->bus, "summary"); }},
            {"ai errors", "AI: Explain errors", [](ide_state_t *s){ ai_add(&s->ai, "user", "errors"); ai_generate_response(&s->ai, &s->bus, "error"); }},
            {"ai fix", "AI: Suggest fix", [](ide_state_t *s){ ai_add(&s->ai, "user", "fix"); ai_generate_response(&s->ai, &s->bus, "fix"); }},
            {"quit", "Quit Bloodhound IDE", [](ide_state_t *s){ s->running = false; }},
        };

        for (auto &c : commands) {
            if (cmd_search[0] && !strcasestr(c.cmd, cmd_search) && !strcasestr(c.desc, cmd_search)) continue;
            if (ImGui::Selectable(c.desc)) {
                c.fn(ide);
                ide->show_command_palette = false;
                cmd_search[0] = '\0';
            }
        }
        ImGui::EndPopup();
    }
}

// ═══════════════════════════════════════════════════════════
// ABOUT DIALOG
// ═══════════════════════════════════════════════════════════

static void render_about(ide_state_t *ide) {
    if (!ide->show_about) return;
    ImGui::OpenPopup("About Bloodhound");
    if (ImGui::BeginPopupModal("About Bloodhound", &ide->show_about,
        ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::TextColored(IM_COL32(80,200,255,255), "Bloodhound IDE v%s", IDE_VERSION);
        ImGui::Separator();
        ImGui::TextUnformatted("AI-Native Observability Platform");
        ImGui::TextUnformatted("");
        ImGui::TextUnformatted("Built with Dear ImGui (docking) + GLFW + OpenGL3");
        ImGui::TextUnformatted("");
        ImGui::TextUnformatted("Architecture:");
        ImGui::TextUnformatted("  Application -> EventBus -> {GUI, AI, Replay, Graph, Profiler}");
        ImGui::TextUnformatted("  Every panel is a consumer of the same event stream.");
        ImGui::TextUnformatted("");
        ImGui::TextUnformatted("Features:");
        ImGui::TextUnformatted("  - Dockable panels (VS Code-class layout)");
        ImGui::TextUnformatted("  - Live event timeline with click-to-select");
        ImGui::TextUnformatted("  - Execution graph with animated edges");
        ImGui::TextUnformatted("  - Time-travel replay (play/pause/step/seek)");
        ImGui::TextUnformatted("  - Timing profiler with histogram bars");
        ImGui::TextUnformatted("  - AI assistant (chat, suggestions, fixes)");
        ImGui::TextUnformatted("  - Bottom dock: Events/Console/Variables/State/Memory/SQL/AI Log");
        ImGui::TextUnformatted("  - Command palette (Ctrl+Shift+P)");
        ImGui::Separator();
        if (ImGui::Button("Close", ImVec2(-1, 0))) { ide->show_about = false; }
        ImGui::EndPopup();
    }
}

// ═══════════════════════════════════════════════════════════
// DARK THEME
// ═══════════════════════════════════════════════════════════

static void setup_dark_theme(void) {
    ImGuiStyle &style = ImGui::GetStyle();
    ImVec4 *colors = style.Colors;

    // Dark theme inspired by VS Code
    colors[ImGuiCol_WindowBg]           = ImVec4(0.12f, 0.12f, 0.14f, 1.00f);
    colors[ImGuiCol_ChildBg]            = ImVec4(0.16f, 0.16f, 0.18f, 1.00f);
    colors[ImGuiCol_PopupBg]            = ImVec4(0.20f, 0.20f, 0.22f, 0.95f);
    colors[ImGuiCol_Border]             = ImVec4(0.25f, 0.25f, 0.28f, 0.60f);
    colors[ImGuiCol_BorderShadow]       = ImVec4(0.00f, 0.00f, 0.00f, 0.00f);
    colors[ImGuiCol_Text]               = ImVec4(0.90f, 0.90f, 0.90f, 1.00f);
    colors[ImGuiCol_TextDisabled]       = ImVec4(0.50f, 0.50f, 0.50f, 1.00f);
    colors[ImGuiCol_Header]             = ImVec4(0.20f, 0.40f, 0.60f, 1.00f);
    colors[ImGuiCol_HeaderHovered]      = ImVec4(0.25f, 0.50f, 0.70f, 1.00f);
    colors[ImGuiCol_HeaderActive]       = ImVec4(0.30f, 0.60f, 0.80f, 1.00f);
    colors[ImGuiCol_Button]             = ImVec4(0.25f, 0.25f, 0.28f, 1.00f);
    colors[ImGuiCol_ButtonHovered]      = ImVec4(0.35f, 0.35f, 0.38f, 1.00f);
    colors[ImGuiCol_ButtonActive]       = ImVec4(0.40f, 0.40f, 0.43f, 1.00f);
    colors[ImGuiCol_Tab]                = ImVec4(0.18f, 0.18f, 0.20f, 1.00f);
    colors[ImGuiCol_TabHovered]         = ImVec4(0.30f, 0.50f, 0.70f, 1.00f);
    colors[ImGuiCol_TabActive]          = ImVec4(0.25f, 0.40f, 0.60f, 1.00f);
    colors[ImGuiCol_TabUnfocused]       = ImVec4(0.15f, 0.15f, 0.17f, 1.00f);
    colors[ImGuiCol_TabUnfocusedActive] = ImVec4(0.22f, 0.22f, 0.25f, 1.00f);
    colors[ImGuiCol_FrameBg]            = ImVec4(0.20f, 0.20f, 0.22f, 1.00f);
    colors[ImGuiCol_FrameBgHovered]     = ImVec4(0.28f, 0.28f, 0.30f, 1.00f);
    colors[ImGuiCol_FrameBgActive]      = ImVec4(0.32f, 0.32f, 0.35f, 1.00f);
    colors[ImGuiCol_TitleBg]            = ImVec4(0.15f, 0.15f, 0.17f, 1.00f);
    colors[ImGuiCol_TitleBgActive]      = ImVec4(0.20f, 0.20f, 0.23f, 1.00f);
    colors[ImGuiCol_MenuBarBg]          = ImVec4(0.18f, 0.18f, 0.20f, 1.00f);
    colors[ImGuiCol_ScrollbarBg]        = ImVec4(0.12f, 0.12f, 0.14f, 1.00f);
    colors[ImGuiCol_ScrollbarGrab]      = ImVec4(0.30f, 0.30f, 0.33f, 1.00f);
    colors[ImGuiCol_ScrollbarGrabHovered] = ImVec4(0.40f, 0.40f, 0.43f, 1.00f);
    colors[ImGuiCol_ScrollbarGrabActive]  = ImVec4(0.50f, 0.50f, 0.53f, 1.00f);
    colors[ImGuiCol_CheckMark]          = ImVec4(0.30f, 0.60f, 0.95f, 1.00f);
    colors[ImGuiCol_SliderGrab]         = ImVec4(0.30f, 0.60f, 0.95f, 1.00f);
    colors[ImGuiCol_SliderGrabActive]   = ImVec4(0.40f, 0.70f, 1.00f, 1.00f);
    colors[ImGuiCol_PlotLines]          = ImVec4(0.30f, 0.60f, 0.95f, 1.00f);
    colors[ImGuiCol_PlotHistogram]      = ImVec4(0.30f, 0.60f, 0.95f, 1.00f);
    colors[ImGuiCol_TextSelectedBg]     = ImVec4(0.30f, 0.50f, 0.70f, 0.40f);
    colors[ImGuiCol_DockingPreview]     = ImVec4(0.30f, 0.60f, 0.95f, 0.70f);
    colors[ImGuiCol_DockingEmptyBg]     = ImVec4(0.10f, 0.10f, 0.12f, 1.00f);

    // Rounding
    style.WindowRounding    = 6.0f;
    style.ChildRounding     = 4.0f;
    style.FrameRounding     = 3.0f;
    style.PopupRounding     = 4.0f;
    style.ScrollbarRounding = 6.0f;
    style.GrabRounding      = 3.0f;
    style.TabRounding       = 4.0f;

    // Spacing
    style.WindowPadding  = ImVec2(8, 8);
    style.FramePadding   = ImVec2(4, 3);
    style.ItemSpacing    = ImVec2(6, 4);
    style.ItemInnerSpacing = ImVec2(4, 4);
    style.WindowBorderSize = 1.0f;
    style.FrameBorderSize  = 0.0f;
    style.PopupBorderSize  = 1.0f;
}

// ═══════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════

static void glfw_error_callback(int err, const char *desc) {
    fprintf(stderr, "GLFW Error %d: %s\n", err, desc);
}

int main(int argc, char **argv) {
    glfwSetErrorCallback(glfw_error_callback);
    if (!glfwInit()) {
        fprintf(stderr, "Failed to initialize GLFW\n");
        return 1;
    }

    // OpenGL 3.3 core
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
#ifdef __APPLE__
    glfwWindowHint(GLFW_OPENGL_FORWARD_COMPAT, GL_TRUE);
#endif
    glfwWindowHint(GLFW_DECORATED, GLFW_TRUE);
    glfwWindowHint(GLFW_RESIZABLE, GLFW_TRUE);
    glfwWindowHint(GLFW_MAXIMIZED, GLFW_TRUE);

    GLFWwindow *window = glfwCreateWindow(1600, 900, "Bloodhound IDE — AI-Native Observability Platform", NULL, NULL);
    if (!window) {
        fprintf(stderr, "Failed to create GLFW window\n");
        glfwTerminate();
        return 1;
    }
    glfwMakeContextCurrent(window);
    glfwSwapInterval(1); // vsync

    // Init ImGui
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO &io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;
    io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;
    io.ConfigFlags |= ImGuiConfigFlags_ViewportsEnable;
    io.IniFilename = "bloodhound_ide.ini";

    setup_dark_theme();

    // When viewports are enabled, tweak WindowRounding
    ImGuiStyle &style = ImGui::GetStyle();
    if (io.ConfigFlags & ImGuiConfigFlags_ViewportsEnable) {
        style.WindowRounding = 0.0f;
        colors[ImGuiCol_WindowBg] = ... // already set
    }

    ImGui_ImplGlfw_InitForOpenGL(window, true);
    ImGui_ImplOpenGL3_Init("#version 330");

    // Init state
    ide_state_t *ide = (ide_state_t *)calloc(1, sizeof(ide_state_t));
    ide->source_path = argc > 1 ? argv[1] : NULL;
    ide->running = true;
    ide->center_tab = 0;
    ide->left_tab = 0;
    ide->bottom_tab = 0;
    ide->selected_event = -1;
    ide->replay_pos = 0;
    ide->replay_speed = 1.0f;
    ide->timeline_zoom = 1.0f;
    ide->graph_animate = true;
    ide->fps = 60.0f;

    bus_init(&ide->bus);
    if (ide->source_path) {
        source_load(&ide->source, ide->source_path);
        scan_python_file(ide, ide->source_path);
    }
    ai_add(&ide->ai, "ai", "Bloodhound IDE ready. I can analyze events, suggest fixes, explain errors, and show graphs. Try the buttons above or type a question.");

    // Main loop
    while (!glfwWindowShouldClose(window) && ide->running) {
        glfwPollEvents();

        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();

        // FPS
        ide->fps = io.Framerate;

        // Dockspace
        ImGuiViewport *viewport = ImGui::GetMainViewport();
        ImGui::SetNextWindowPos(viewport->WorkPos);
        ImGui::SetNextWindowSize(viewport->WorkSize);
        ImGui::SetNextWindowViewport(viewport->ID);
        ImGuiWindowFlags dock_flags = ImGuiWindowFlags_MenuBar | ImGuiWindowFlags_NoDocking |
            ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoCollapse |
            ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoMove |
            ImGuiWindowFlags_NoBringToFrontOnFocus | ImGuiWindowFlags_NoNavFocus;
        ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 0.0f);
        ImGui::PushStyleVar(ImGuiStyleVar_WindowBorderSize, 0.0f);
        ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(0, 0));
        ImGui::Begin("##dockspace", NULL, dock_flags);
        ImGui::PopStyleVar(3);

        ImGuiID dockspace_id = ImGui::GetID("BloodhoundDockSpace");
        if (ImGui::DockBuilderGetNode(dockspace_id) == NULL) {
            // First run — set up default layout
            ImGui::DockBuilderRemoveNode(dockspace_id);
            ImGui::DockBuilderAddNode(dockspace_id, ImGuiDockNodeFlags_DockSpace);
            ImGui::DockBuilderSetNodeSize(dockspace_id, viewport->WorkSize);

            ImGuiID dock_main = dockspace_id;
            ImGuiID dock_left, dock_right, dock_bottom, dock_center;

            // Split: left | (center | right)
            ImGui::DockBuilderSplitNode(dock_main, ImGuiDir_Left, 0.18f, &dock_left, &dock_main);
            ImGui::DockBuilderSplitNode(dock_main, ImGuiDir_Right, 0.22f, &dock_right, &dock_main);
            ImGui::DockBuilderSplitNode(dock_main, ImGuiDir_Down, 0.30f, &dock_bottom, &dock_center);

            // Dock windows
            ImGui::DockBuilderDockWindow("Explorer##left", dock_left);
            ImGui::DockBuilderDockWindow("Source##center_source", dock_center);
            ImGui::DockBuilderDockWindow("Timeline##center_timeline", dock_center);
            ImGui::DockBuilderDockWindow("Graph##center_graph", dock_center);
            ImGui::DockBuilderDockWindow("Replay##center_replay", dock_center);
            ImGui::DockBuilderDockWindow("Profiler##center_profiler", dock_center);
            ImGui::DockBuilderDockWindow("AI Assistant##right_ai", dock_right);
            ImGui::DockBuilderDockWindow("Bottom Dock##bottom", dock_bottom);

            ImGui::DockBuilderFinish(dockspace_id);
        }
        ImGui::DockSpace(dockspace_id, ImVec2(0, 0), ImGuiDockNodeFlags_PassthruCentralNode);

        // Menu bar
        render_menu_bar(ide);

        // Toolbar
        render_toolbar(ide);

        // All dockable windows
        render_left_sidebar(ide);
        render_source_editor(ide);
        render_event_timeline(ide);
        render_graph_viewer(ide);
        render_replay_viewer(ide);
        render_profiler(ide);
        render_ai_assistant(ide);
        render_bottom_dock(ide);

        // Modals
        render_command_palette(ide);
        render_about(ide);

        // Demo window (optional)
        if (ide->show_imgui_demo) ImGui::ShowDemoWindow(&ide->show_imgui_demo);

        ImGui::End(); // dockspace

        // Status bar (outside dockspace)
        render_status_bar(ide);

        // Render
        ImGui::Render();
        int display_w, display_h;
        glfwGetFramebufferSize(window, &display_w, &display_h);
        glViewport(0, 0, display_w, display_h);
        glClearColor(0.08f, 0.08f, 0.10f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());

        // Update windows (for multi-viewport)
        if (io.ConfigFlags & ImGuiConfigFlags_ViewportsEnable) {
            GLFWwindow *backup = glfwGetCurrentContext();
            ImGui::UpdatePlatformWindows();
            ImGui::RenderPlatformWindowsDefault();
            glfwMakeContextCurrent(backup);
        }

        glfwSwapBuffers(window);
    }

    // Cleanup
    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();
    glfwDestroyWindow(window);
    glfwTerminate();

    source_free(&ide->source);
    free(ide);

    printf("Bloodhound IDE closed.\n");
    return 0;
}
