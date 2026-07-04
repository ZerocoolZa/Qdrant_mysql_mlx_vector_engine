/*
 * memunit_viewer.c - ANSI terminal viewer + worker thread for C memory unit debugger
 *[@GHOST]{file_path="core/Dom_Bloodhound/memunit_viewer.c" date="2026-07-04" author="Devin" session_id="memunit-c" context="ANSI terminal viewer with worker thread, decoupled rendering at configurable Hz"}
 *[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE ANSI-rendering worker-thread"}
 *[@FILEID]{id="memunit_viewer.c" domain="dom_bloodhound" authority="MemunitViewer"}
 *[@SUMMARY]{summary="ANSI terminal viewer. Worker thread renders at configurable Hz. Decoupled from execution via ring buffer. Color-coded by severity/kind. Terminal width detection."}
 *[@CLASS]{class="MemunitViewer" domain="dom_bloodhound" authority="single"}
 *[@METHOD]{methods="viewer_init,viewer_start,viewer_stop,viewer_shutdown,viewer_render_table,viewer_render_summary,viewer_render_errors,viewer_render_tests,viewer_push_event,render_worker,ansi_color,ansi_reset,get_terminal_width"}
 */

#include "memunit_debugger.h"

#include <string.h>
#include <stdlib.h>
#include <pthread.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <time.h>

/* =====================================================================
 * ANSI escape codes (replacing Rich library)
 * ===================================================================== */

#define ANSI_RESET      "\033[0m"
#define ANSI_RED        "\033[31m"
#define ANSI_GREEN      "\033[32m"
#define ANSI_YELLOW     "\033[33m"
#define ANSI_BLUE       "\033[34m"
#define ANSI_MAGENTA    "\033[35m"
#define ANSI_CYAN       "\033[36m"
#define ANSI_BOLD       "\033[1m"
#define ANSI_DIM        "\033[2m"

#define ANSI_CLEAR_LINE "\033[2K"
#define ANSI_CURSOR_HOME "\033[H"
#define ANSI_HIDE_CURSOR "\033[?25l"
#define ANSI_SHOW_CURSOR "\033[?25h"

/* Move cursor to row,col: \033[<row>;<col>H */
#define ANSI_CURSOR_FMT "\033[%d;%dH"

/* UTF-8 box drawing horizontal line */
#define BOX_H_LINE "\xE2\x94\x80"

/* ---- kind names ---- */

static const char *KIND_NAMES[] = {
    "step", "result", "error", "variable", "state", "timing", "import"
};

static const char KIND_ICONS[] = {
    '>', 'X', '!', 'V', 'S', 'T', 'D'
};

/* ---- helpers ---- */

static const char *ansi_color(int severity, int kind)
{
    /* severity takes priority for row coloring */
    if (severity >= MU_SEV_ERROR) return ANSI_RED;
    if (severity == MU_SEV_WARN)  return ANSI_YELLOW;
    if (severity == MU_SEV_INFO)  return ANSI_GREEN;
    if (severity == MU_SEV_DEBUG) return ANSI_CYAN;
    /* fall back to kind coloring when severity == 0 */
    switch (kind) {
        case MU_KIND_STEP:     return ANSI_CYAN;
        case MU_KIND_RESULT:   return ANSI_GREEN;
        case MU_KIND_ERROR:    return ANSI_RED;
        case MU_KIND_STATE:    return ANSI_MAGENTA;
        case MU_KIND_VARIABLE: return ANSI_YELLOW;
        case MU_KIND_TIMING:   return ANSI_BLUE;
        case MU_KIND_IMPORT:   return ANSI_CYAN;
        default:               return ANSI_RESET;
    }
}

static const char *ansi_reset(void)
{
    return ANSI_RESET;
}

static int get_terminal_width(void)
{
    struct winsize ws;
    if (ioctl(STDOUT_FILENO, TIOCGWINSZ, &ws) == 0 && ws.ws_col > 0) {
        return (int)ws.ws_col;
    }
    if (ioctl(STDERR_FILENO, TIOCGWINSZ, &ws) == 0 && ws.ws_col > 0) {
        return (int)ws.ws_col;
    }
    return 80;  /* sensible default */
}

/* truncate a string to max_len, writing "..." suffix if truncated */
static void truncate_str(const char *src, char *dst, size_t max_len)
{
    size_t n = strlen(src);
    if (n <= max_len) {
        strncpy(dst, src, max_len + 1);
        return;
    }
    if (max_len < 4) {
        strncpy(dst, src, max_len);
        dst[max_len] = '\0';
        return;
    }
    strncpy(dst, src, max_len - 3);
    dst[max_len - 3] = '.';
    dst[max_len - 2] = '.';
    dst[max_len - 1] = '.';
    dst[max_len] = '\0';
}

/* print a horizontal separator line of box-drawing chars */
static void print_separator(int total_width)
{
    fputs(ANSI_DIM, stdout);
    for (int i = 0; i < total_width; i++) {
        fputs(BOX_H_LINE, stdout);
    }
    fputs(ANSI_RESET "\n", stdout);
}

/* =====================================================================
 * Render queue ring buffer
 * ===================================================================== */

static RenderQueue *queue_create(size_t capacity)
{
    RenderQueue *q = (RenderQueue *)calloc(1, sizeof(RenderQueue));
    if (!q) return NULL;
    q->buffer = (Event *)calloc(capacity, sizeof(Event));
    if (!q->buffer) { free(q); return NULL; }
    q->head = 0;
    q->tail = 0;
    q->capacity = capacity;
    pthread_mutex_init(&q->lock, NULL);
    pthread_cond_init(&q->cond, NULL);
    return q;
}

static void queue_destroy(RenderQueue *q)
{
    if (!q) return;
    pthread_mutex_destroy(&q->lock);
    pthread_cond_destroy(&q->cond);
    free(q->buffer);
    free(q);
}

/* returns 1 on success, 0 if full (dropped) */
static int queue_push(RenderQueue *q, const Event *ev)
{
    int ok = 0;
    pthread_mutex_lock(&q->lock);
    size_t next = (q->head + 1) % q->capacity;
    if (next != q->tail) {
        q->buffer[q->head] = *ev;
        q->head = next;
        ok = 1;
        pthread_cond_signal(&q->cond);
    }
    pthread_mutex_unlock(&q->lock);
    return ok;
}

/* returns 1 on success, 0 if empty */
static int queue_pop(RenderQueue *q, Event *out)
{
    int ok = 0;
    pthread_mutex_lock(&q->lock);
    if (q->tail != q->head) {
        *out = q->buffer[q->tail];
        q->tail = (q->tail + 1) % q->capacity;
        ok = 1;
    }
    pthread_mutex_unlock(&q->lock);
    return ok;
}

/* drain all available events into a caller buffer, returns count */
static int queue_drain(RenderQueue *q, Event *out, int max)
{
    int n = 0;
    pthread_mutex_lock(&q->lock);
    while (n < max && q->tail != q->head) {
        out[n] = q->buffer[q->tail];
        q->tail = (q->tail + 1) % q->capacity;
        n++;
    }
    pthread_mutex_unlock(&q->lock);
    return n;
}

/* =====================================================================
 * Verbosity gate: decide whether an event should be shown
 * ===================================================================== */

static int verbosity_show(int verbosity, const Event *ev)
{
    /* 0 = errors only */
    if (verbosity == 0) {
        return (ev->severity >= MU_SEV_ERROR || ev->kind == MU_KIND_ERROR);
    }
    /* 1 = normal (steps, results, errors, state) */
    if (verbosity == 1) {
        if (ev->kind == MU_KIND_VARIABLE || ev->kind == MU_KIND_TIMING ||
            ev->kind == MU_KIND_IMPORT) {
            return 0;
        }
        return 1;
    }
    /* 2 = + variables */
    if (verbosity == 2) {
        if (ev->kind == MU_KIND_TIMING || ev->kind == MU_KIND_IMPORT) {
            return 0;
        }
        return 1;
    }
    /* 3 = everything */
    return 1;
}

/* =====================================================================
 * Rendering functions (all ANSI, no external library)
 * ===================================================================== */

/* column widths */
#define COL_ID     6
#define COL_SRC    14
#define COL_PHASE  14
#define COL_KIND   10
#define COL_ENTITY 16
#define COL_NAME   18
#define COL_VALUE  25
#define COL_SEV    5

static int total_table_width(void)
{
    return COL_ID + COL_SRC + COL_PHASE + COL_KIND +
           COL_ENTITY + COL_NAME + COL_VALUE + COL_SEV;
}

static void print_table_header(void)
{
    fputs(ANSI_BOLD ANSI_CYAN, stdout);
    printf("%-*s %-*s %-*s %-*s %-*s %-*s %-*s %-*s\n",
           COL_ID,     "ID",
           COL_SRC,    "Source",
           COL_PHASE,  "Phase",
           COL_KIND,   "Kind",
           COL_ENTITY, "Entity",
           COL_NAME,   "Name",
           COL_VALUE,  "Value",
           COL_SEV,    "Sev");
    fputs(ANSI_RESET, stdout);
    print_separator(total_table_width());
}

static void render_event_row(const Event *ev)
{
    const char *color = ansi_color(ev->severity, ev->kind);
    char eid[16], src[COL_SRC + 1], phase[COL_PHASE + 1], kind[COL_KIND + 1];
    char entity[COL_ENTITY + 1], name[COL_NAME + 1], value[COL_VALUE + 1];

    snprintf(eid, sizeof(eid), "%llu", (unsigned long long)ev->id);
    truncate_str(ev->producer,  src,    COL_SRC);
    truncate_str(ev->phase,     phase,  COL_PHASE);
    snprintf(kind, sizeof(kind), "%c %s", KIND_ICONS[ev->kind % 7],
             KIND_NAMES[ev->kind % 7]);
    truncate_str(ev->entity,    entity, COL_ENTITY);
    truncate_str(ev->attribute, name,   COL_NAME);
    truncate_str(ev->value,     value,  COL_VALUE);

    fputs(color, stdout);
    printf("%-*s %-*s %-*s %-*s %-*s %-*s %-*s %d\n",
           COL_ID,     eid,
           COL_SRC,    src,
           COL_PHASE,  phase,
           COL_KIND,   kind,
           COL_ENTITY, entity,
           COL_NAME,   name,
           COL_VALUE,  value,
           ev->severity);
    fputs(ANSI_RESET, stdout);
}

void viewer_render_table(EventViewer *v)
{
    if (!v || !v->state) return;
    int term_w = get_terminal_width();
    (void)term_w;

    fputs(ANSI_BOLD, stdout);
    printf("Fact Report  %s(verbosity=%d hz=%d)%s\n",
           ANSI_DIM, v->verbosity, v->refresh_hz, ANSI_RESET);
    print_table_header();

    pthread_mutex_lock(&v->state->lock);
    for (size_t i = 0; i < v->state->count; i++) {
        const Event *ev = &v->state->events[i];
        if (!verbosity_show(v->verbosity, ev)) continue;
        render_event_row(ev);
    }
    pthread_mutex_unlock(&v->state->lock);
    fputc('\n', stdout);
}

void viewer_render_summary(EventViewer *v)
{
    if (!v || !v->state) return;
    LiveState *st = v->state;

    pthread_mutex_lock(&st->lock);
    fputs(ANSI_BOLD ANSI_CYAN "SUMMARY\n" ANSI_RESET, stdout);
    printf("  Total Events : %s%llu%s\n",
           ANSI_BOLD, (unsigned long long)st->total, ANSI_RESET);
    printf("  Errors       : %s%llu%s\n",
           ANSI_RED, (unsigned long long)st->errors, ANSI_RESET);
    fputc('\n', stdout);

    fputs(ANSI_BOLD "By Kind:\n" ANSI_RESET, stdout);
    for (int k = 0; k < 7; k++) {
        const char *c = (k == MU_KIND_ERROR) ? ANSI_RED :
                        (k == MU_KIND_RESULT) ? ANSI_GREEN :
                        (k == MU_KIND_STEP) ? ANSI_CYAN :
                        (k == MU_KIND_STATE) ? ANSI_MAGENTA :
                        (k == MU_KIND_VARIABLE) ? ANSI_YELLOW :
                        (k == MU_KIND_TIMING) ? ANSI_BLUE : ANSI_CYAN;
        printf("  %s%-10s%s %llu\n", c, KIND_NAMES[k], ANSI_RESET,
               (unsigned long long)st->by_kind[k]);
    }
    pthread_mutex_unlock(&st->lock);
    fputc('\n', stdout);
}

void viewer_render_errors(EventViewer *v)
{
    if (!v || !v->state) return;
    fputs(ANSI_BOLD ANSI_RED "ERRORS (full detail)\n" ANSI_RESET, stdout);
    print_separator(total_table_width());

    int found = 0;
    pthread_mutex_lock(&v->state->lock);
    for (size_t i = 0; i < v->state->count; i++) {
        const Event *ev = &v->state->events[i];
        if (ev->severity < MU_SEV_ERROR && ev->kind != MU_KIND_ERROR) continue;
        found++;
        fputs(ANSI_RED, stdout);
        printf("#%llu [%s/%s] %s/%s  %s=%s  sev=%d",
               (unsigned long long)ev->id,
               ev->producer, ev->phase, KIND_NAMES[ev->kind],
               ev->entity, ev->attribute, ev->value, ev->severity);
        if (ev->reasoning[0]) {
            printf("  %sreasoning: %s%s", ANSI_DIM, ev->reasoning, ANSI_RESET);
        }
        printf("\n");
        fputs(ANSI_RESET, stdout);
    }
    pthread_mutex_unlock(&v->state->lock);

    if (!found) {
        printf("%s(no errors)%s\n", ANSI_DIM, ANSI_RESET);
    }
    fputc('\n', stdout);
}

void viewer_render_tests(EventViewer *v)
{
    if (!v || !v->state) return;
    LiveState *st = v->state;

    pthread_mutex_lock(&st->lock);
    uint64_t total = st->total;
    uint64_t errors = st->errors;
    uint64_t results = st->by_kind[MU_KIND_RESULT];
    uint64_t steps = st->by_kind[MU_KIND_STEP];
    uint64_t states = st->by_kind[MU_KIND_STATE];

    fputs(ANSI_BOLD ANSI_YELLOW "TEST RESULTS\n" ANSI_RESET, stdout);
    print_separator(40);

    int pass = (errors == 0);
    printf("  %s%s PASS%s  Error Check   %s(%llu errors)%s\n",
           pass ? ANSI_GREEN : ANSI_RED,
           pass ? "\xE2\x9C\x93" : "\xE2\x9C\x97",
           ANSI_RESET,
           ANSI_DIM, (unsigned long long)errors, ANSI_RESET);

    int state_ok = (states > 0);
    printf("  %s%s PASS%s  State Check   %s(%llu state facts)%s\n",
           state_ok ? ANSI_GREEN : ANSI_RED,
           state_ok ? "\xE2\x9C\x93" : "\xE2\x9C\x97",
           ANSI_RESET,
           ANSI_DIM, (unsigned long long)states, ANSI_RESET);

    int result_ok = (results > 0);
    printf("  %s%s PASS%s  Result Check  %s(%llu results)%s\n",
           result_ok ? ANSI_GREEN : ANSI_RED,
           result_ok ? "\xE2\x9C\x93" : "\xE2\x9C\x97",
           ANSI_RESET,
           ANSI_DIM, (unsigned long long)results, ANSI_RESET);

    fputc('\n', stdout);
    fputs(ANSI_BOLD "Per-class results:\n" ANSI_RESET, stdout);

    /* aggregate by producer (class) */
    char classes[64][MU_MAX_PRODUCER];
    uint64_t c_count[64] = {0};
    uint64_t c_errors[64] = {0};
    int nclass = 0;

    for (size_t i = 0; i < st->count; i++) {
        const Event *ev = &st->events[i];
        int idx = -1;
        for (int c = 0; c < nclass; c++) {
            if (strncmp(classes[c], ev->producer, MU_MAX_PRODUCER) == 0) {
                idx = c; break;
            }
        }
        if (idx < 0) {
            if (nclass >= 64) continue;
            idx = nclass++;
            strncpy(classes[idx], ev->producer, MU_MAX_PRODUCER - 1);
            classes[idx][MU_MAX_PRODUCER - 1] = '\0';
        }
        c_count[idx]++;
        if (ev->severity >= MU_SEV_ERROR || ev->kind == MU_KIND_ERROR) {
            c_errors[idx]++;
        }
    }

    for (int c = 0; c < nclass; c++) {
        int ok = (c_errors[c] == 0);
        printf("  %s%s%s %s%-16s%s  facts=%llu errors=%llu\n",
               ok ? ANSI_GREEN : ANSI_RED,
               ok ? "\xE2\x9C\x93" : "\xE2\x9C\x97",
               ANSI_RESET,
               ANSI_YELLOW, classes[c], ANSI_RESET,
               (unsigned long long)c_count[c],
               (unsigned long long)c_errors[c]);
    }

    fputc('\n', stdout);
    int total_passed = (errors == 0 ? 1 : 0) + (state_ok ? 1 : 0) + (result_ok ? 1 : 0);
    int total_failed = 3 - total_passed;
    printf("  %sPassed:%s %d   %sFailed:%s %d   Total Tests: %d\n",
           ANSI_GREEN, ANSI_RESET, total_passed,
           ANSI_RED, ANSI_RESET, total_failed, 3);
    printf("  %sOverall:%s %s%s%s\n",
           ANSI_BOLD, ANSI_RESET,
           total_failed == 0 ? ANSI_GREEN "ALL PASS" ANSI_RESET
                             : ANSI_BOLD ANSI_RED "HAS FAILURES" ANSI_RESET,
           "", "");
    (void)total; (void)steps;
    pthread_mutex_unlock(&st->lock);
    fputc('\n', stdout);
}

/* =====================================================================
 * Live rendering worker thread
 * ===================================================================== */

static void render_live_frame(EventViewer *v)
{
    Event batch[64];
    int n = queue_drain(v->queue, batch, 64);
    if (n == 0) return;

    /* move cursor up to overwrite previous frame rows */
    if (v->live_mode && v->rows_printed > 0) {
        for (int i = 0; i < v->rows_printed; i++) {
            printf("\033[1A" ANSI_CLEAR_LINE);  /* up one line + clear */
        }
        v->rows_printed = 0;
    }

    struct timespec now;
    clock_gettime(CLOCK_REALTIME, &now);
    char ts[32];
    struct tm tmv;
    time_t sec = (time_t)now.tv_sec;
    localtime_r(&sec, &tmv);
    snprintf(ts, sizeof(ts), "%02d:%02d:%02d.%03ld",
             tmv.tm_hour, tmv.tm_min, tmv.tm_sec, now.tv_nsec / 1000000);

    fputs(ANSI_BOLD, stdout);
    printf("%s[LIVE]%s %s  events=%d  total=%llu\n",
           ANSI_CYAN, ANSI_RESET, ts, n,
           (unsigned long long)v->state->total);
    v->rows_printed++;

    for (int i = 0; i < n; i++) {
        if (!verbosity_show(v->verbosity, &batch[i])) continue;
        render_event_row(&batch[i]);
        v->rows_printed++;
    }
    fflush(stdout);
}

static void *render_worker(void *arg)
{
    EventViewer *v = (EventViewer *)arg;
    long interval_us = 0;
    if (v->refresh_hz > 0) {
        interval_us = 1000000L / v->refresh_hz;
    } else {
        interval_us = 100000L;  /* 10Hz default */
    }

    if (v->live_mode) {
        fputs(ANSI_HIDE_CURSOR, stdout);
        fflush(stdout);
    }

    while (v->running) {
        render_live_frame(v);
        usleep((useconds_t)interval_us);
    }

    /* final drain */
    render_live_frame(v);

    if (v->live_mode) {
        fputs(ANSI_SHOW_CURSOR, stdout);
        fflush(stdout);
    }
    return NULL;
}

/* =====================================================================
 * Public API
 * ===================================================================== */

void viewer_init(EventViewer *v, LiveState *st, int verbosity, int refresh_hz)
{
    memset(v, 0, sizeof(EventViewer));
    v->verbosity = verbosity;
    v->refresh_hz = (refresh_hz > 0) ? refresh_hz : MU_DEFAULT_HZ;
    v->state = st;
    v->queue = queue_create(MU_QUEUE_SIZE);
    v->running = 0;
    v->live_mode = isatty(STDOUT_FILENO) ? 1 : 0;
    v->rows_printed = 0;
}

int viewer_start(EventViewer *v)
{
    if (!v || !v->queue) return 0;
    if (v->running) return 1;
    v->running = 1;
    v->rows_printed = 0;
    if (pthread_create(&v->thread, NULL, render_worker, v) != 0) {
        v->running = 0;
        return 0;
    }
    return 1;
}

void viewer_stop(EventViewer *v)
{
    if (!v) return;
    if (!v->running) return;
    v->running = 0;
    pthread_join(v->thread, NULL);
}

void viewer_shutdown(EventViewer *v)
{
    if (!v) return;
    viewer_stop(v);
    queue_destroy(v->queue);
    v->queue = NULL;
    v->state = NULL;
}

void viewer_push_event(EventViewer *v, const Event *ev)
{
    if (!v || !v->queue || !ev) return;
    queue_push(v->queue, ev);
}
