//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_graph_trace.c" date="2026-07-04" author="Devin" session_id="graph-bcl-units" context="BCL unit for GraphTrace — immutable truth log for the Max Graph Engine. Every graph run produces an immutable log of all decisions made. Foundation for the learning pipeline (Trace -> Evaluate -> Update -> Apply)."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_graph_trace.c" domain="graph_engine" authority="GraphTrace"}
//[@SUMMARY]{summary="Immutable trace log for graph engine. Records every decision (visit, skip, prune, cache hit/miss, cost, guard hit, outcome). Evaluates traces into learning signals. Commands: create, free, log_visit, log_skip, log_prune, log_cache_hit, log_cache_miss, log_cost, log_guard_hit, log_outcome, evaluate, dump, export_json, summary, read_state, set_config."}
//[@CLASS]{class="GraphTrace" domain="graph_engine" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="trace_create" type="lifecycle"}
//[@METHOD]{method="trace_free" type="lifecycle"}
//[@METHOD]{method="trace_append" type="internal"}
//[@METHOD]{method="trace_log_visit" type="command"}
//[@METHOD]{method="trace_log_skip" type="command"}
//[@METHOD]{method="trace_log_prune" type="command"}
//[@METHOD]{method="trace_log_cache_hit" type="command"}
//[@METHOD]{method="trace_log_cache_miss" type="command"}
//[@METHOD]{method="trace_log_cost" type="command"}
//[@METHOD]{method="trace_log_guard_hit" type="command"}
//[@METHOD]{method="trace_log_outcome" type="command"}
//[@METHOD]{method="trace_evaluate" type="query"}
//[@METHOD]{method="trace_dump" type="query"}
//[@METHOD]{method="trace_export_json" type="query"}
//[@METHOD]{method="trace_summary" type="query"}
//[@METHOD]{method="trace_current_time_ms" type="internal"}

#include "bcl_graph_types.h"
#include "bcl_toolstack.h"

/* ════════════════════════════════════════════
 * UNIT STATE
 * ════════════════════════════════════════════ */

#define GTRACE_BUF_SIZE     65536
#define GTRACE_MAX_SIGNALS  1024
#define GTRACE_MAX_NAME     256
#define GTRACE_MAX_REASON   256

static struct {
    int        initialized;
    TraceLog  *current;
    int        traces_created;
    int        traces_freed;
    int        entries_logged;
    int        last_signal_count;
    char       last_error[GTRACE_BUF_SIZE];
} STATE;

/* ════════════════════════════════════════════
 * TIMING HELPER
 * ════════════════════════════════════════════ */

static long trace_current_time_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}

/* ════════════════════════════════════════════
 * TRACE LIFECYCLE
 * ════════════════════════════════════════════ */

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

/* ════════════════════════════════════════════
 * APPEND (internal — immutable, never modify existing entries)
 * ════════════════════════════════════════════ */

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
    /* Append to linked list */
    if (t->last) {
        t->last->next = e;
    } else {
        t->first = e;
    }
    t->last = e;
    t->count++;
    return e;
}

/* ════════════════════════════════════════════
 * SPECIFIC TRACE ACTIONS
 * ════════════════════════════════════════════ */

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

/* ════════════════════════════════════════════
 * TRACE EVALUATION — convert raw trace into learning signals
 * This is the EVALUATION stage of the learning pipeline
 * ════════════════════════════════════════════ */

int trace_evaluate(TraceLog *t, LearningSignal *signals_out, int max_signals) {
    if (!t || !signals_out || max_signals <= 0) return 0;
    int signal_count = 0;
    /* Iterate through trace entries and compute contribution scores */
    TraceEntry *e = t->first;
    while (e && signal_count < max_signals) {
        if (e->action == TRACE_VISIT && e->node_id >= 0) {
            LearningSignal *sig = &signals_out[signal_count];
            sig->node_id = e->node_id;
            strncpy(sig->node_name, e->node_name, sizeof(sig->node_name) - 1);
            sig->view_id = e->view_id;
            /* Contribution: nodes visited with high score that led to good outcome */
            sig->contribution_score = e->score_at_decision * t->outcome_quality;
            /* Success delta: difference between score and outcome */
            sig->success_delta = t->outcome_quality - e->score_at_decision;
            /* Cost efficiency: outcome per cost unit */
            sig->cost_efficiency = t->outcome_quality / (e->cost_charged + 1.0);
            /* Redundancy penalty: check if this node was visited multiple times */
            int visits = 0;
            TraceEntry *e2 = t->first;
            while (e2) {
                if (e2->action == TRACE_VISIT && e2->node_id == e->node_id) visits++;
                e2 = e2->next;
            }
            sig->redundancy_penalty = visits > 1 ? (float)(visits - 1) * 0.1f : 0.0f;
            signal_count++;
        }
        e = e->next;
    }
    return signal_count;
}

/* ════════════════════════════════════════════
 * TRACE DUMP (for debugging)
 * ════════════════════════════════════════════ */

void trace_dump(TraceLog *t, char *buf, int buf_size) {
    if (!t || !buf) return;
    int pos = 0;
    pos += snprintf(buf + pos, buf_size - pos, "TraceLog{view=%s, entries=%d}\n",
        t->view_name, t->count);
    pos += snprintf(buf + pos, buf_size - pos,
        "  visited=%d, skipped=%d, pruned=%d, cost=%.1f, outcome=%.2f\n",
        t->nodes_visited, t->nodes_skipped, t->nodes_pruned, t->total_cost, t->outcome_quality);
    long duration = t->end_time_ms - t->start_time_ms;
    pos += snprintf(buf + pos, buf_size - pos, "  duration=%ldms\n", duration);
    TraceEntry *e = t->first;
    int shown = 0;
    while (e && pos < buf_size - 200 && shown < 50) {
        const char *action_str = "UNKNOWN";
        switch (e->action) {
            case TRACE_VISIT:      action_str = "VISIT";      break;
            case TRACE_SKIP:       action_str = "SKIP";       break;
            case TRACE_PRUNE:      action_str = "PRUNE";      break;
            case TRACE_CACHE_HIT:  action_str = "CACHE_HIT";  break;
            case TRACE_CACHE_MISS: action_str = "CACHE_MISS"; break;
            case TRACE_COST:       action_str = "COST";       break;
            case TRACE_OUTCOME:    action_str = "OUTCOME";    break;
            case TRACE_GUARD_HIT:  action_str = "GUARD_HIT";  break;
        }
        pos += snprintf(buf + pos, buf_size - pos,
            "  [%d] %s node=%d(%s) reason=%s score=%.2f cost=%.1f depth=%d\n",
            e->id, action_str, e->node_id, e->node_name, e->reason,
            e->score_at_decision, e->cost_charged, e->depth);
        e = e->next;
        shown++;
    }
    if (t->count > 50) {
        pos += snprintf(buf + pos, buf_size - pos, "  ... (%d more entries)\n", t->count - 50);
    }
}

/* ════════════════════════════════════════════
 * EXPORT JSON
 * ════════════════════════════════════════════ */

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
            case TRACE_VISIT:      action_str = "visit";      break;
            case TRACE_SKIP:       action_str = "skip";       break;
            case TRACE_PRUNE:      action_str = "prune";      break;
            case TRACE_CACHE_HIT:  action_str = "cache_hit";  break;
            case TRACE_CACHE_MISS: action_str = "cache_miss"; break;
            case TRACE_COST:       action_str = "cost";       break;
            case TRACE_OUTCOME:    action_str = "outcome";    break;
            case TRACE_GUARD_HIT:  action_str = "guard_hit";  break;
        }
        pos += snprintf(buf + pos, buf_size - pos,
            "{\"id\":%d,\"action\":\"%s\",\"node\":%d,\"name\":\"%s\",\"reason\":\"%s\",\"score\":%.2f,\"cost\":%.1f,\"depth\":%d}",
            e->id, action_str, e->node_id, e->node_name, e->reason,
            e->score_at_decision, e->cost_charged, e->depth);
        e = e->next;
    }
    pos += snprintf(buf + pos, buf_size - pos, "]}}");
}

/* ════════════════════════════════════════════
 * TRACE SUMMARY
 * ════════════════════════════════════════════ */

void trace_summary(TraceLog *t, int *visited, int *skipped, int *pruned,
                   float *cost, float *outcome, long *duration_ms) {
    if (!t) return;
    if (visited)    *visited    = t->nodes_visited;
    if (skipped)    *skipped    = t->nodes_skipped;
    if (pruned)     *pruned     = t->nodes_pruned;
    if (cost)       *cost       = t->total_cost;
    if (outcome)    *outcome    = t->outcome_quality;
    if (duration_ms) *duration_ms = t->end_time_ms - t->start_time_ms;
}

/* ════════════════════════════════════════════
 * BCL DISPATCH
 * ════════════════════════════════════════════ */

int GraphTrace_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    STATE.current = NULL;
    STATE.traces_created = 0;
    STATE.traces_freed = 0;
    STATE.entries_logged = 0;
    STATE.last_signal_count = 0;
    STATE.last_error[0] = '\0';
    return 1;
}

int GraphTrace_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) GraphTrace_Init();

    /* --- read_state --- */
    if (strcmp(cmd, "read_state") == 0) {
        char buf[512];
        int has_current = STATE.current ? 1 : 0;
        int entry_count = STATE.current ? STATE.current->count : 0;
        snprintf(buf, sizeof(buf),
            "[@INITIALIZED]{%d}[@HAS_CURRENT]{%d}[@ENTRIES]{%d}[@TRACES_CREATED]{%d}[@TRACES_FREED]{%d}[@ENTRIES_LOGGED]{%d}[@LAST_SIGNALS]{%d}",
            STATE.initialized, has_current, entry_count,
            STATE.traces_created, STATE.traces_freed,
            STATE.entries_logged, STATE.last_signal_count);
        return BclResult_Ok(bcl_out, out_sz, buf);
    }

    /* --- set_config --- */
    if (strcmp(cmd, "set_config") == 0) {
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }

    /* --- create --- */
    if (strcmp(cmd, "create") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);

        char view_name[GTRACE_MAX_NAME] = "";
        char view_id_str[32] = "";
        BclParser_Extract(&parse, "view_name", view_name, sizeof(view_name));
        BclParser_Extract(&parse, "view_id", view_id_str, sizeof(view_id_str));
        int view_id = view_id_str[0] ? atoi(view_id_str) : 0;

        /* Free existing current trace if present */
        if (STATE.current) {
            trace_free(STATE.current);
            STATE.traces_freed++;
        }

        STATE.current = trace_create(view_id, view_name);
        BclParser_Free(&parse);

        if (!STATE.current) {
            return BclResult_Err(bcl_out, out_sz, 50, "trace_create failed");
        }
        STATE.traces_created++;
        char buf[256];
        snprintf(buf, sizeof(buf), "[@STATUS]{created}[@VIEW_ID]{%d}[@VIEW_NAME]{%s}",
            STATE.current->view_id, STATE.current->view_name);
        return BclResult_Ok(bcl_out, out_sz, buf);
    }

    /* --- free --- */
    if (strcmp(cmd, "free") == 0) {
        if (!STATE.current) {
            return BclResult_Err(bcl_out, out_sz, 50, "no active trace");
        }
        trace_free(STATE.current);
        STATE.current = NULL;
        STATE.traces_freed++;
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{freed}");
    }

    /* All remaining commands require an active trace */
    if (!STATE.current) {
        return BclResult_Err(bcl_out, out_sz, 50, "no active trace — create first");
    }

    /* --- log_visit --- */
    if (strcmp(cmd, "log_visit") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);

        char node_id_str[32] = "";
        char node_name[GTRACE_MAX_NAME] = "";
        char score_str[32] = "";
        char cost_str[32] = "";
        char depth_str[32] = "";
        BclParser_Extract(&parse, "node_id", node_id_str, sizeof(node_id_str));
        BclParser_Extract(&parse, "node_name", node_name, sizeof(node_name));
        BclParser_Extract(&parse, "score", score_str, sizeof(score_str));
        BclParser_Extract(&parse, "cost", cost_str, sizeof(cost_str));
        BclParser_Extract(&parse, "depth", depth_str, sizeof(depth_str));

        Node n;
        memset(&n, 0, sizeof(n));
        n.id = node_id_str[0] ? atoi(node_id_str) : 0;
        if (node_name[0]) strncpy(n.name, node_name, sizeof(n.name) - 1);
        float score = score_str[0] ? (float)atof(score_str) : 0.0f;
        float cost  = cost_str[0]  ? (float)atof(cost_str)  : 0.0f;
        int   depth = depth_str[0] ? atoi(depth_str)        : 0;

        trace_log_visit(STATE.current, &n, score, cost, depth);
        STATE.entries_logged++;
        BclParser_Free(&parse);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{logged}");
    }

    /* --- log_skip --- */
    if (strcmp(cmd, "log_skip") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);

        char node_id_str[32] = "";
        char node_name[GTRACE_MAX_NAME] = "";
        char reason[GTRACE_MAX_REASON] = "";
        char score_str[32] = "";
        char depth_str[32] = "";
        BclParser_Extract(&parse, "node_id", node_id_str, sizeof(node_id_str));
        BclParser_Extract(&parse, "node_name", node_name, sizeof(node_name));
        BclParser_Extract(&parse, "reason", reason, sizeof(reason));
        BclParser_Extract(&parse, "score", score_str, sizeof(score_str));
        BclParser_Extract(&parse, "depth", depth_str, sizeof(depth_str));

        Node n;
        memset(&n, 0, sizeof(n));
        n.id = node_id_str[0] ? atoi(node_id_str) : 0;
        if (node_name[0]) strncpy(n.name, node_name, sizeof(n.name) - 1);
        const char *reason_ptr = reason[0] ? reason : "skipped";
        float score = score_str[0] ? (float)atof(score_str) : 0.0f;
        int   depth = depth_str[0] ? atoi(depth_str)        : 0;

        trace_log_skip(STATE.current, &n, reason_ptr, score, depth);
        STATE.entries_logged++;
        BclParser_Free(&parse);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{logged}");
    }

    /* --- log_prune --- */
    if (strcmp(cmd, "log_prune") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);

        char node_id_str[32] = "";
        char node_name[GTRACE_MAX_NAME] = "";
        char reason[GTRACE_MAX_REASON] = "";
        char score_str[32] = "";
        char depth_str[32] = "";
        BclParser_Extract(&parse, "node_id", node_id_str, sizeof(node_id_str));
        BclParser_Extract(&parse, "node_name", node_name, sizeof(node_name));
        BclParser_Extract(&parse, "reason", reason, sizeof(reason));
        BclParser_Extract(&parse, "score", score_str, sizeof(score_str));
        BclParser_Extract(&parse, "depth", depth_str, sizeof(depth_str));

        Node n;
        memset(&n, 0, sizeof(n));
        n.id = node_id_str[0] ? atoi(node_id_str) : 0;
        if (node_name[0]) strncpy(n.name, node_name, sizeof(n.name) - 1);
        const char *reason_ptr = reason[0] ? reason : "pruned";
        float score = score_str[0] ? (float)atof(score_str) : 0.0f;
        int   depth = depth_str[0] ? atoi(depth_str)        : 0;

        trace_log_prune(STATE.current, &n, reason_ptr, score, depth);
        STATE.entries_logged++;
        BclParser_Free(&parse);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{logged}");
    }

    /* --- log_cache_hit --- */
    if (strcmp(cmd, "log_cache_hit") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);

        char node_id_str[32] = "";
        char node_name[GTRACE_MAX_NAME] = "";
        char depth_str[32] = "";
        BclParser_Extract(&parse, "node_id", node_id_str, sizeof(node_id_str));
        BclParser_Extract(&parse, "node_name", node_name, sizeof(node_name));
        BclParser_Extract(&parse, "depth", depth_str, sizeof(depth_str));

        Node n;
        memset(&n, 0, sizeof(n));
        n.id = node_id_str[0] ? atoi(node_id_str) : 0;
        if (node_name[0]) strncpy(n.name, node_name, sizeof(n.name) - 1);
        int depth = depth_str[0] ? atoi(depth_str) : 0;

        trace_log_cache_hit(STATE.current, &n, depth);
        STATE.entries_logged++;
        BclParser_Free(&parse);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{logged}");
    }

    /* --- log_cache_miss --- */
    if (strcmp(cmd, "log_cache_miss") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);

        char node_id_str[32] = "";
        char node_name[GTRACE_MAX_NAME] = "";
        char depth_str[32] = "";
        BclParser_Extract(&parse, "node_id", node_id_str, sizeof(node_id_str));
        BclParser_Extract(&parse, "node_name", node_name, sizeof(node_name));
        BclParser_Extract(&parse, "depth", depth_str, sizeof(depth_str));

        Node n;
        memset(&n, 0, sizeof(n));
        n.id = node_id_str[0] ? atoi(node_id_str) : 0;
        if (node_name[0]) strncpy(n.name, node_name, sizeof(n.name) - 1);
        int depth = depth_str[0] ? atoi(depth_str) : 0;

        trace_log_cache_miss(STATE.current, &n, depth);
        STATE.entries_logged++;
        BclParser_Free(&parse);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{logged}");
    }

    /* --- log_cost --- */
    if (strcmp(cmd, "log_cost") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);

        char cost_str[32] = "";
        char reason[GTRACE_MAX_REASON] = "";
        BclParser_Extract(&parse, "cost", cost_str, sizeof(cost_str));
        BclParser_Extract(&parse, "reason", reason, sizeof(reason));

        float cost = cost_str[0] ? (float)atof(cost_str) : 0.0f;
        const char *reason_ptr = reason[0] ? reason : "cost charged";

        trace_log_cost(STATE.current, cost, reason_ptr);
        STATE.entries_logged++;
        BclParser_Free(&parse);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{logged}");
    }

    /* --- log_guard_hit --- */
    if (strcmp(cmd, "log_guard_hit") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);

        char reason[GTRACE_MAX_REASON] = "";
        BclParser_Extract(&parse, "reason", reason, sizeof(reason));
        const char *reason_ptr = reason[0] ? reason : "guard triggered";

        trace_log_guard_hit(STATE.current, reason_ptr);
        STATE.entries_logged++;
        BclParser_Free(&parse);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{logged}");
    }

    /* --- log_outcome --- */
    if (strcmp(cmd, "log_outcome") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);

        char quality_str[32] = "";
        char reason[GTRACE_MAX_REASON] = "";
        BclParser_Extract(&parse, "quality", quality_str, sizeof(quality_str));
        BclParser_Extract(&parse, "reason", reason, sizeof(reason));

        float quality = quality_str[0] ? (float)atof(quality_str) : 0.0f;
        const char *reason_ptr = reason[0] ? reason : "traversal complete";

        trace_log_outcome(STATE.current, quality, reason_ptr);
        STATE.entries_logged++;
        BclParser_Free(&parse);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{logged}");
    }

    /* --- evaluate --- */
    if (strcmp(cmd, "evaluate") == 0) {
        LearningSignal signals[GTRACE_MAX_SIGNALS];
        memset(signals, 0, sizeof(signals));
        int count = trace_evaluate(STATE.current, signals, GTRACE_MAX_SIGNALS);
        STATE.last_signal_count = count;

        /* Build BCL output with signal summaries */
        char buf[GTRACE_BUF_SIZE];
        int pos = 0;
        pos += snprintf(buf + pos, sizeof(buf) - pos,
            "[@SIGNAL_COUNT]{%d}[@SIGNALS]{", count);
        for (int i = 0; i < count && pos < (int)sizeof(buf) - 256; i++) {
            if (i > 0) {
                pos += snprintf(buf + pos, sizeof(buf) - pos, ";");
            }
            pos += snprintf(buf + pos, sizeof(buf) - pos,
                "(%d;%s;%.3f;%.3f;%.3f;%.3f)",
                signals[i].node_id,
                signals[i].node_name,
                signals[i].contribution_score,
                signals[i].success_delta,
                signals[i].cost_efficiency,
                signals[i].redundancy_penalty);
        }
        pos += snprintf(buf + pos, sizeof(buf) - pos, "}");
        return BclResult_Ok(bcl_out, out_sz, buf);
    }

    /* --- dump --- */
    if (strcmp(cmd, "dump") == 0) {
        char buf[GTRACE_BUF_SIZE];
        buf[0] = '\0';
        trace_dump(STATE.current, buf, sizeof(buf));
        return BclResult_Ok(bcl_out, out_sz, buf);
    }

    /* --- export_json --- */
    if (strcmp(cmd, "export_json") == 0) {
        char buf[GTRACE_BUF_SIZE];
        buf[0] = '\0';
        trace_export_json(STATE.current, buf, sizeof(buf));
        return BclResult_Ok(bcl_out, out_sz, buf);
    }

    /* --- summary --- */
    if (strcmp(cmd, "summary") == 0) {
        int visited = 0, skipped = 0, pruned = 0;
        float cost = 0.0f, outcome = 0.0f;
        long duration_ms = 0;
        trace_summary(STATE.current, &visited, &skipped, &pruned,
                      &cost, &outcome, &duration_ms);
        char buf[512];
        snprintf(buf, sizeof(buf),
            "[@VISITED]{%d}[@SKIPPED]{%d}[@PRUNED]{%d}[@COST]{%.1f}[@OUTCOME]{%.2f}[@DURATION_MS]{%ld}",
            visited, skipped, pruned, cost, outcome, duration_ms);
        return BclResult_Ok(bcl_out, out_sz, buf);
    }

    return BclResult_Err(bcl_out, out_sz, 404, "unknown command");
}

int GraphTrace_Close(void) {
    if (STATE.current) {
        trace_free(STATE.current);
        STATE.current = NULL;
        STATE.traces_freed++;
    }
    STATE.initialized = 0;
    return 1;
}

const char * GraphTrace_State(void) {
    static char buf[256];
    int has_current = STATE.current ? 1 : 0;
    int entry_count = STATE.current ? STATE.current->count : 0;
    snprintf(buf, sizeof(buf),
        "GraphTrace: initialized=%d, current=%s, entries=%d, created=%d, freed=%d",
        STATE.initialized, has_current ? "yes" : "no", entry_count,
        STATE.traces_created, STATE.traces_freed);
    return buf;
}
