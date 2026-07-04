// GraphTrace — Immutable Truth Log for the Max Graph Engine
// Every graph run produces an immutable log of all decisions made.
// This is the foundation for the learning pipeline (Trace -> Evaluate -> Update -> Apply).

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

// === Trace entry types ===
typedef enum {
    TRACE_VISIT,        // node was visited/expanded
    TRACE_SKIP,         // node was skipped (failed policy check)
    TRACE_PRUNE,        // node was pruned by optimizer
    TRACE_CACHE_HIT,    // node result came from cache
    TRACE_CACHE_MISS,   // node result was not in cache
    TRACE_COST,         // cost was charged
    TRACE_OUTCOME,      // final outcome of the traversal
    TRACE_GUARD_HIT     // execution guard triggered (timeout, budget, etc)
} TraceAction;

// === Trace entry — a single decision record ===
typedef struct TraceEntry {
    int id;                     // sequential entry ID
    TraceAction action;         // what happened
    int node_id;                // which node (if applicable, -1 for global events)
    char node_name[256];        // node name (for readability)
    char reason[256];           // why this decision was made
    float score_at_decision;    // score when the decision was made
    float cost_charged;         // cost charged (if any)
    int depth;                  // depth at this point
    int view_id;                // which view was active
    char view_name[64];         // view name
    long timestamp_ms;          // when this happened
    struct TraceEntry *next;    // linked list (append-only)
} TraceEntry;

// === Trace log — the complete record of a graph run ===
typedef struct TraceLog {
    TraceEntry *first;          // first entry (linked list head)
    TraceEntry *last;           // last entry (for fast append)
    int count;                  // total entries
    int view_id;                // view this trace belongs to
    char view_name[64];         // view name
    long start_time_ms;         // when traversal started
    long end_time_ms;           // when traversal ended
    float total_cost;           // total cost spent
    int nodes_visited;          // total nodes visited
    int nodes_skipped;          // total nodes skipped
    int nodes_pruned;           // total nodes pruned
    float outcome_quality;      // final outcome quality (0.0 to 1.0)
} TraceLog;

// === Timing ===
static long trace_current_time_ms() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}

// === Trace lifecycle ===

TraceLog *trace_create(int view_id, const char *view_name) {
    TraceLog *t = (TraceLog *)calloc(1, sizeof(TraceLog));
    if (!t) return NULL;
    t->first = NULL;
    t->last = NULL;
    t->count = 0;
    t->view_id = view_id;
    if (view_name) strncpy(t->view_name, view_name, sizeof(t->view_name) - 1);
    t->start_time_ms = trace_current_time_ms();
    t->end_time_ms = 0;
    t->total_cost = 0.0;
    t->nodes_visited = 0;
    t->nodes_skipped = 0;
    t->nodes_pruned = 0;
    t->outcome_quality = 0.0;
    return t;
}

void trace_free(TraceLog *t) {
    if (!t) return;
    TraceEntry *e = t->first;
    while (e) {
        TraceEntry *next = e->next;
        free(e);
        e = next;
    }
    free(t);
}

// === Append entries (immutable — never modify existing entries) ===

static TraceEntry *trace_append(TraceLog *t, TraceAction action, int node_id,
                                 const char *node_name, const char *reason,
                                 float score, float cost, int depth) {
    if (!t) return NULL;
    TraceEntry *e = (TraceEntry *)calloc(1, sizeof(TraceEntry));
    if (!e) return NULL;
    e->id = t->count;
    e->action = action;
    e->node_id = node_id;
    if (node_name) strncpy(e->node_name, node_name, sizeof(e->node_name) - 1);
    if (reason) strncpy(e->reason, reason, sizeof(e->reason) - 1);
    e->score_at_decision = score;
    e->cost_charged = cost;
    e->depth = depth;
    e->view_id = t->view_id;
    strncpy(e->view_name, t->view_name, sizeof(e->view_name) - 1);
    e->timestamp_ms = trace_current_time_ms();
    e->next = NULL;
    // Append to linked list
    if (t->last) {
        t->last->next = e;
    } else {
        t->first = e;
    }
    t->last = e;
    t->count++;
    return e;
}

// === Specific trace actions ===

void trace_log_visit(TraceLog *t, Node *n, float score, float cost, int depth) {
    if (!t || !n) return;
    trace_append(t, TRACE_VISIT, n->id, n->name, "expanded", score, cost, depth);
    t->nodes_visited++;
    t->total_cost += cost;
}

void trace_log_skip(TraceLog *t, Node *n, const char *reason, float score, int depth) {
    if (!t || !n) return;
    trace_append(t, TRACE_SKIP, n->id, n->name, reason, score, 0.0, depth);
    t->nodes_skipped++;
}

void trace_log_prune(TraceLog *t, Node *n, const char *reason, float score, int depth) {
    if (!t || !n) return;
    trace_append(t, TRACE_PRUNE, n->id, n->name, reason, score, 0.0, depth);
    t->nodes_pruned++;
}

void trace_log_cache_hit(TraceLog *t, Node *n, int depth) {
    if (!t || !n) return;
    trace_append(t, TRACE_CACHE_HIT, n->id, n->name, "cache hit", 0.0, 0.0, depth);
}

void trace_log_cache_miss(TraceLog *t, Node *n, int depth) {
    if (!t || !n) return;
    trace_append(t, TRACE_CACHE_MISS, n->id, n->name, "cache miss", 0.0, 0.0, depth);
}

void trace_log_cost(TraceLog *t, float cost, const char *reason) {
    if (!t) return;
    trace_append(t, TRACE_COST, -1, "", reason, 0.0, cost, 0);
}

void trace_log_guard_hit(TraceLog *t, const char *reason) {
    if (!t) return;
    trace_append(t, TRACE_GUARD_HIT, -1, "", reason, 0.0, 0.0, 0);
}

void trace_log_outcome(TraceLog *t, float quality, const char *reason) {
    if (!t) return;
    t->end_time_ms = trace_current_time_ms();
    t->outcome_quality = quality;
    trace_append(t, TRACE_OUTCOME, -1, "", reason, quality, t->total_cost, 0);
}

// === Trace evaluation — convert raw trace into learning signals ===

// Learning signal extracted from trace
typedef struct LearningSignal {
    int node_id;
    char node_name[256];
    int view_id;
    float contribution_score;   // how much this node contributed to the outcome
    float success_delta;        // difference between expected and actual success
    float cost_efficiency;      // outcome quality per unit cost
    float redundancy_penalty;   // penalty for redundant expansion
} LearningSignal;

// Evaluate a trace and produce learning signals
// This is the EVALUATION stage of the learning pipeline
int trace_evaluate(TraceLog *t, LearningSignal *signals_out, int max_signals) {
    if (!t || !signals_out || max_signals <= 0) return 0;
    int signal_count = 0;
    // Iterate through trace entries and compute contribution scores
    TraceEntry *e = t->first;
    while (e && signal_count < max_signals) {
        if (e->action == TRACE_VISIT && e->node_id >= 0) {
            LearningSignal *sig = &signals_out[signal_count];
            sig->node_id = e->node_id;
            strncpy(sig->node_name, e->node_name, sizeof(sig->node_name) - 1);
            sig->view_id = e->view_id;
            // Contribution: nodes visited with high score that led to good outcome
            sig->contribution_score = e->score_at_decision * t->outcome_quality;
            // Success delta: difference between score and outcome
            sig->success_delta = t->outcome_quality - e->score_at_decision;
            // Cost efficiency: outcome per cost unit
            sig->cost_efficiency = t->outcome_quality / (e->cost_charged + 1.0);
            // Redundancy penalty: check if this node was visited multiple times
            int visits = 0;
            TraceEntry *e2 = t->first;
            while (e2) {
                if (e2->action == TRACE_VISIT && e2->node_id == e->node_id) visits++;
                e2 = e2->next;
            }
            sig->redundancy_penalty = visits > 1 ? (float)(visits - 1) * 0.1 : 0.0;
            signal_count++;
        }
        e = e->next;
    }
    return signal_count;
}

// === Trace dump (for debugging) ===

void trace_dump(TraceLog *t, char *buf, int buf_size) {
    if (!t || !buf) return;
    int pos = 0;
    pos += snprintf(buf + pos, buf_size - pos, "TraceLog{view=%s, entries=%d}
",
        t->view_name, t->count);
    pos += snprintf(buf + pos, buf_size - pos,
        "  visited=%d, skipped=%d, pruned=%d, cost=%.1f, outcome=%.2f
",
        t->nodes_visited, t->nodes_skipped, t->nodes_pruned, t->total_cost, t->outcome_quality);
    long duration = t->end_time_ms - t->start_time_ms;
    pos += snprintf(buf + pos, buf_size - pos, "  duration=%ldms
", duration);
    TraceEntry *e = t->first;
    int shown = 0;
    while (e && pos < buf_size - 200 && shown < 50) {
        const char *action_str = "UNKNOWN";
        switch (e->action) {
            case TRACE_VISIT: action_str = "VISIT"; break;
            case TRACE_SKIP: action_str = "SKIP"; break;
            case TRACE_PRUNE: action_str = "PRUNE"; break;
            case TRACE_CACHE_HIT: action_str = "CACHE_HIT"; break;
            case TRACE_CACHE_MISS: action_str = "CACHE_MISS"; break;
            case TRACE_COST: action_str = "COST"; break;
            case TRACE_OUTCOME: action_str = "OUTCOME"; break;
            case TRACE_GUARD_HIT: action_str = "GUARD_HIT"; break;
        }
        pos += snprintf(buf + pos, buf_size - pos,
            "  [%d] %s node=%d(%s) reason=%s score=%.2f cost=%.1f depth=%d
",
            e->id, action_str, e->node_id, e->node_name, e->reason,
            e->score_at_decision, e->cost_charged, e->depth);
        e = e->next;
        shown++;
    }
    if (t->count > 50) {
        pos += snprintf(buf + pos, buf_size - pos, "  ... (%d more entries)
", t->count - 50);
    }
}

// Export trace as JSON
void trace_export_json(TraceLog *t, char *buf, int buf_size) {
    if (!t || !buf) return;
    int pos = 0;
    pos += snprintf(buf + pos, buf_size - pos,
        "{\"trace\":{\"view\":\"%s\",\"entries\":%d,\"visited\":%d,\"skipped\":%d,\"pruned\":%d,\"cost\":%.1f,\"outcome\":%.2f,\"events\":[",
        t->view_name, t->count, t->nodes_visited, t->nodes_skipped, t->nodes_pruned,
        t->total_cost, t->outcome_quality);
    TraceEntry *e = t->first;
    int first = 1;
    while (e && pos < buf_size - 200) {
        if (!first) pos += snprintf(buf + pos, buf_size - pos, ",");
        first = 0;
        const char *action_str = "unknown";
        switch (e->action) {
            case TRACE_VISIT: action_str = "visit"; break;
            case TRACE_SKIP: action_str = "skip"; break;
            case TRACE_PRUNE: action_str = "prune"; break;
            case TRACE_CACHE_HIT: action_str = "cache_hit"; break;
            case TRACE_CACHE_MISS: action_str = "cache_miss"; break;
            case TRACE_COST: action_str = "cost"; break;
            case TRACE_OUTCOME: action_str = "outcome"; break;
            case TRACE_GUARD_HIT: action_str = "guard_hit"; break;
        }
        pos += snprintf(buf + pos, buf_size - pos,
            "{\"id\":%d,\"action\":\"%s\",\"node\":%d,\"name\":\"%s\",\"reason\":\"%s\",\"score\":%.2f,\"cost\":%.1f,\"depth\":%d}",
            e->id, action_str, e->node_id, e->node_name, e->reason,
            e->score_at_decision, e->cost_charged, e->depth);
        e = e->next;
    }
    pos += snprintf(buf + pos, buf_size - pos, "]}}");
}

// Get trace summary stats
void trace_summary(TraceLog *t, int *visited, int *skipped, int *pruned,
                   float *cost, float *outcome, long *duration_ms) {
    if (!t) return;
    if (visited) *visited = t->nodes_visited;
    if (skipped) *skipped = t->nodes_skipped;
    if (pruned) *pruned = t->nodes_pruned;
    if (cost) *cost = t->total_cost;
    if (outcome) *outcome = t->outcome_quality;
    if (duration_ms) *duration_ms = t->end_time_ms - t->start_time_ms;
}
