//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_graph_policy.c" date="2026-07-04" author="Devin" session_id="graph-bcl-units" context="BCL unit for Max Graph Engine policy layer — decides whether a node should expand based on hard limit, context, and attention; tracks executor resource usage"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_graph_policy.c" domain="graph_engine" authority="GraphPolicy"}
//[@SUMMARY]{summary="GraphPolicy BCL unit. Wraps the raw GraphPolicy.c policy and executor functions behind a BCL dispatch interface. Commands: should_expand, set_context, compute_importance, get_depth_limit, dump, executor_check, executor_charge, executor_start, executor_is_halted, executor_elapsed_ms, executor_dump, read_state, set_config."}
//[@CLASS]{class="GraphPolicy" domain="graph_engine" authority="single"}
//[@METHOD]{method="Init" type="lifecycle"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="lifecycle"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="executor_check" type="command"}
//[@METHOD]{method="executor_charge" type="command"}
//[@METHOD]{method="executor_start" type="command"}
//[@METHOD]{method="executor_is_halted" type="query"}
//[@METHOD]{method="executor_elapsed_ms" type="query"}
//[@METHOD]{method="policy_should_expand" type="query"}
//[@METHOD]{method="policy_set_context" type="command"}
//[@METHOD]{method="policy_compute_importance" type="command"}
//[@METHOD]{method="policy_get_depth_limit" type="query"}
//[@METHOD]{method="policy_dump" type="query"}
//[@METHOD]{method="executor_dump" type="query"}
//[@METHOD]{method="read_state" type="command"}
//[@METHOD]{method="set_config" type="command"}

#include "bcl_graph_types.h"
#include "bcl_toolstack.h"

/* ════════════════════════════════════════════
 * UNIT STATE — a default Policy and Executor
 * instance used by the BCL dispatch layer so
 * callers can exercise policy/executor logic
 * without holding their own Graph struct.
 * ════════════════════════════════════════════ */

static struct {
    int       initialized;
    Policy    policy;
    Executor  executor;
} STATE;

/* ════════════════════════════════════════════
 * HELPER — current time in milliseconds
 * (kept static; used by executor functions)
 * ════════════════════════════════════════════ */

static long current_time_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}

/* ════════════════════════════════════════════
 * CORE C FUNCTIONS — preserved from raw
 * GraphPolicy.c. These operate on caller-owned
 * Policy/Executor instances (e.g. inside a
 * Graph struct) and are unchanged.
 * ════════════════════════════════════════════ */

/* Check if the executor has exceeded its limits */
int executor_check(Executor *ex) {
    if (!ex) return 1;
    if (ex->halted) return 1;
    /* Check timeout */
    if (ex->start_time_ms > 0) {
        long elapsed = current_time_ms() - ex->start_time_ms;
        if (elapsed > ex->timeout_ms) {
            ex->halted = 1;
            return 1;
        }
    }
    /* Check cost */
    if (ex->cost_used >= ex->cost_limit) {
        ex->halted = 1;
        return 1;
    }
    /* Check memory (rough estimate: node_count * sizeof(Node))
     * This is a simple check — real implementation would track allocations */
    return 0;
}

/* Charge cost to executor */
void executor_charge(Executor *ex, float cost) {
    if (!ex) return;
    ex->cost_used += (int)cost;
}

/* Start the executor timer */
void executor_start(Executor *ex) {
    if (!ex) return;
    ex->start_time_ms = current_time_ms();
    ex->cost_used = 0;
    ex->halted = 0;
}

/* Check if executor is halted */
int executor_is_halted(Executor *ex) {
    return ex ? ex->halted : 1;
}

/* Get elapsed time in ms */
long executor_elapsed_ms(Executor *ex) {
    if (!ex || ex->start_time_ms == 0) return 0;
    return current_time_ms() - ex->start_time_ms;
}

/* === Policy checks === */

/* Should this node be expanded?
 * Returns 1 if yes, 0 if no */
int policy_should_expand(Policy *p, Node *n, int current_depth, int nodes_this_hop, int total_nodes) {
    if (!p || !n) return 0;

    /* 1. Hard depth limit */
    int depth_limit = p->hard_limit;
    if (p->context_limit > 0) {
        depth_limit = p->context_limit;  /* context overrides hard */
    }
    if (current_depth >= depth_limit) return 0;

    /* 2. Attention threshold — only expand important enough nodes */
    if (n->importance < p->attention_threshold) return 0;

    /* 3. Max nodes per hop */
    if (nodes_this_hop >= p->max_nodes_per_hop) return 0;

    /* 4. Max total nodes */
    if (total_nodes >= p->max_total_nodes) return 0;

    /* 5. Already expanded */
    if (n->expanded) return 0;

    return 1;
}

/* Set context-specific depth limit */
void policy_set_context(Policy *p, const char *context_name) {
    if (!p || !context_name) return;
    /* Context-specific depth limits */
    if (strcmp(context_name, "engineering") == 0) {
        p->context_limit = 4;
    } else if (strcmp(context_name, "physics") == 0) {
        p->context_limit = 6;
    } else if (strcmp(context_name, "ui") == 0) {
        p->context_limit = 2;
    } else if (strcmp(context_name, "search") == 0) {
        p->context_limit = 3;
    } else if (strcmp(context_name, "deep") == 0) {
        p->context_limit = 10;
    } else {
        p->context_limit = 0;  /* use hard_limit */
    }
}

/* Compute importance for a node based on frequency, centrality, recency */
float policy_compute_importance(Node *n, float frequency, float centrality, float recency) {
    if (!n) return 0.0;
    /* Weighted sum: 40% frequency, 30% centrality, 30% recency */
    float importance = 0.4f * frequency + 0.3f * centrality + 0.3f * recency;
    if (importance > 1.0f) importance = 1.0f;
    if (importance < 0.0f) importance = 0.0f;
    n->importance = importance;
    return importance;
}

/* Get effective depth limit (context or hard) */
int policy_get_depth_limit(Policy *p) {
    if (!p) return 0;
    return p->context_limit > 0 ? p->context_limit : p->hard_limit;
}

/* Print policy state (for debugging) */
void policy_dump(Policy *p, char *buf, int buf_size) {
    if (!p || !buf) return;
    snprintf(buf, buf_size,
        "Policy{hard=%d, ctx=%d, attention=%.2f, max_per_hop=%d, max_total=%d}",
        p->hard_limit, p->context_limit, p->attention_threshold,
        p->max_nodes_per_hop, p->max_total_nodes);
}

/* Print executor state (for debugging) */
void executor_dump(Executor *ex, char *buf, int buf_size) {
    if (!ex || !buf) return;
    snprintf(buf, buf_size,
        "Executor{mem=%zu/%zu, cost=%d/%d, timeout=%dms, elapsed=%ldms, halted=%d}",
        ex->memory_used, ex->memory_budget,
        ex->cost_used, ex->cost_limit,
        ex->timeout_ms, executor_elapsed_ms(ex), ex->halted);
}

/* ════════════════════════════════════════════
 * BCL DISPATCH LAYER
 *
 * GraphPolicy_Run routes BCL commands to the
 * core functions above. The unit holds a default
 * Policy + Executor in STATE so callers can
 * query/modify policy and executor behaviour
 * through BCL packets without owning a Graph.
 *
 * Commands that need numeric parameters read
 * them from the BCL input via simple tag
 * extraction (sscanf on [@TAG]{value}).
 * ════════════════════════════════════════════ */

/* Helper: extract a float value from a BCL tag in bcl_in.
 * Looks for [@TAG]{value}. Returns 1 on success. */
static int extract_float(const char *bcl_in, const char *tag, float *out) {
    if (!bcl_in || !tag || !out) return 0;
    char pattern[96];
    char fmt[96];
    snprintf(pattern, sizeof(pattern), "[@%s]{", tag);
    const char *p = strstr(bcl_in, pattern);
    if (!p) return 0;
    p += strlen(pattern);
    snprintf(fmt, sizeof(fmt), "%%%s", "f");
    if (sscanf(p, fmt, out) != 1) return 0;
    return 1;
}

/* Helper: extract an int value from a BCL tag in bcl_in. */
static int extract_int(const char *bcl_in, const char *tag, int *out) {
    if (!bcl_in || !tag || !out) return 0;
    char pattern[96];
    snprintf(pattern, sizeof(pattern), "[@%s]{", tag);
    const char *p = strstr(bcl_in, pattern);
    if (!p) return 0;
    p += strlen(pattern);
    if (sscanf(p, "%d", out) != 1) return 0;
    return 1;
}

/* Helper: extract a string value from a BCL tag in bcl_in.
 * Copies up to out_sz-1 chars. Returns 1 on success. */
static int extract_string(const char *bcl_in, const char *tag, char *out, size_t out_sz) {
    if (!bcl_in || !tag || !out || out_sz == 0) return 0;
    char pattern[96];
    snprintf(pattern, sizeof(pattern), "[@%s]{", tag);
    const char *p = strstr(bcl_in, pattern);
    if (!p) return 0;
    p += strlen(pattern);
    const char *end = strchr(p, '}');
    if (!end) return 0;
    size_t len = (size_t)(end - p);
    if (len >= out_sz) len = out_sz - 1;
    memcpy(out, p, len);
    out[len] = '\0';
    return 1;
}

int GraphPolicy_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    /* Sensible defaults so the unit is usable immediately */
    STATE.policy.hard_limit          = 8;
    STATE.policy.context_limit       = 0;
    STATE.policy.attention_threshold = 0.1f;
    STATE.policy.max_nodes_per_hop   = 50;
    STATE.policy.max_total_nodes     = 1000;
    STATE.executor.memory_budget     = 268435456UL;  /* 256 MB */
    STATE.executor.memory_used       = 0;
    STATE.executor.cost_limit        = 10000;
    STATE.executor.cost_used         = 0;
    STATE.executor.timeout_ms        = 30000;
    STATE.executor.start_time_ms     = 0;
    STATE.executor.halted            = 0;
    STATE.initialized = 1;
    return 1;
}

int GraphPolicy_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) GraphPolicy_Init();
    if (!cmd) {
        return BclResult_Err(bcl_out, out_sz, 50, "null command");
    }

    /* --- policy commands --- */

    if (strcmp(cmd, "should_expand") == 0) {
        int   current_depth  = 0;
        int   nodes_this_hop = 0;
        int   total_nodes    = 0;
        float importance     = 0.0f;
        int   expanded       = 0;
        extract_int(bcl_in, "DEPTH", &current_depth);
        extract_int(bcl_in, "HOP", &nodes_this_hop);
        extract_int(bcl_in, "TOTAL", &total_nodes);
        extract_float(bcl_in, "IMPORTANCE", &importance);
        extract_int(bcl_in, "EXPANDED", &expanded);
        /* Build a transient Node from BCL fields */
        Node n;
        memset(&n, 0, sizeof(n));
        n.importance = importance;
        n.expanded   = expanded;
        int result = policy_should_expand(&STATE.policy, &n,
                                          current_depth, nodes_this_hop, total_nodes);
        char body[128];
        snprintf(body, sizeof(body), "[@SHOULD_EXPAND]{%d}[@POLICY]{ok}", result);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    if (strcmp(cmd, "set_context") == 0) {
        char context_name[128];
        if (!extract_string(bcl_in, "CONTEXT", context_name, sizeof(context_name))) {
            return BclResult_Err(bcl_out, out_sz, 51, "missing [@CONTEXT]{name}");
        }
        policy_set_context(&STATE.policy, context_name);
        char body[256];
        snprintf(body, sizeof(body),
                 "[@STATUS]{context_set}[@CONTEXT]{%s}[@DEPTH_LIMIT]{%d}",
                 context_name, policy_get_depth_limit(&STATE.policy));
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    if (strcmp(cmd, "compute_importance") == 0) {
        float frequency = 0.0f, centrality = 0.0f, recency = 0.0f;
        extract_float(bcl_in, "FREQUENCY", &frequency);
        extract_float(bcl_in, "CENTRALITY", &centrality);
        extract_float(bcl_in, "RECENCY", &recency);
        /* Use a transient node to receive the computed importance */
        Node n;
        memset(&n, 0, sizeof(n));
        float imp = policy_compute_importance(&n, frequency, centrality, recency);
        char body[256];
        snprintf(body, sizeof(body),
                 "[@IMPORTANCE]{%.4f}[@FREQUENCY]{%.4f}[@CENTRALITY]{%.4f}[@RECENCY]{%.4f}",
                 imp, frequency, centrality, recency);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    if (strcmp(cmd, "get_depth_limit") == 0) {
        int limit = policy_get_depth_limit(&STATE.policy);
        char body[128];
        snprintf(body, sizeof(body), "[@DEPTH_LIMIT]{%d}", limit);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    if (strcmp(cmd, "dump") == 0) {
        char buf[512];
        policy_dump(&STATE.policy, buf, sizeof(buf));
        char body[640];
        snprintf(body, sizeof(body), "[@POLICY]{%s}", buf);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* --- executor commands --- */

    if (strcmp(cmd, "executor_check") == 0) {
        int halted = executor_check(&STATE.executor);
        char body[128];
        snprintf(body, sizeof(body), "[@HALTED]{%d}[@STATUS]{checked}", halted);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    if (strcmp(cmd, "executor_charge") == 0) {
        float cost = 0.0f;
        if (!extract_float(bcl_in, "COST", &cost)) {
            return BclResult_Err(bcl_out, out_sz, 51, "missing [@COST]{value}");
        }
        executor_charge(&STATE.executor, cost);
        char body[256];
        snprintf(body, sizeof(body),
                 "[@STATUS]{charged}[@COST]{%.2f}[@COST_USED]{%d}[@COST_LIMIT]{%d}",
                 cost, STATE.executor.cost_used, STATE.executor.cost_limit);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    if (strcmp(cmd, "executor_start") == 0) {
        executor_start(&STATE.executor);
        char body[128];
        snprintf(body, sizeof(body),
                 "[@STATUS]{started}[@START_TIME]{%ld}[@TIMEOUT]{%d}",
                 STATE.executor.start_time_ms, STATE.executor.timeout_ms);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    if (strcmp(cmd, "executor_is_halted") == 0) {
        int halted = executor_is_halted(&STATE.executor);
        char body[128];
        snprintf(body, sizeof(body), "[@HALTED]{%d}", halted);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    if (strcmp(cmd, "executor_elapsed_ms") == 0) {
        long elapsed = executor_elapsed_ms(&STATE.executor);
        char body[128];
        snprintf(body, sizeof(body), "[@ELAPSED]{%ld}", elapsed);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    if (strcmp(cmd, "executor_dump") == 0) {
        char buf[512];
        executor_dump(&STATE.executor, buf, sizeof(buf));
        char body[640];
        snprintf(body, sizeof(body), "[@EXECUTOR]{%s}", buf);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* --- standard BCL unit commands --- */

    if (strcmp(cmd, "read_state") == 0) {
        char pbuf[512];
        char ebuf[512];
        policy_dump(&STATE.policy, pbuf, sizeof(pbuf));
        executor_dump(&STATE.executor, ebuf, sizeof(ebuf));
        char body[1280];
        snprintf(body, sizeof(body),
                 "[@INITIALIZED]{%d}[@POLICY]{%s}[@EXECUTOR]{%s}",
                 STATE.initialized, pbuf, ebuf);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    if (strcmp(cmd, "set_config") == 0) {
        int   ival   = 0;
        float fval   = 0.0f;
        int   applied = 0;
        char  key[128];

        if (extract_string(bcl_in, "KEY", key, sizeof(key))) {
            if (strcmp(key, "hard_limit") == 0 &&
                extract_int(bcl_in, "VALUE", &ival)) {
                STATE.policy.hard_limit = ival;
                applied = 1;
            } else if (strcmp(key, "context_limit") == 0 &&
                       extract_int(bcl_in, "VALUE", &ival)) {
                STATE.policy.context_limit = ival;
                applied = 1;
            } else if (strcmp(key, "attention_threshold") == 0 &&
                       extract_float(bcl_in, "VALUE", &fval)) {
                STATE.policy.attention_threshold = fval;
                applied = 1;
            } else if (strcmp(key, "max_nodes_per_hop") == 0 &&
                       extract_int(bcl_in, "VALUE", &ival)) {
                STATE.policy.max_nodes_per_hop = ival;
                applied = 1;
            } else if (strcmp(key, "max_total_nodes") == 0 &&
                       extract_int(bcl_in, "VALUE", &ival)) {
                STATE.policy.max_total_nodes = ival;
                applied = 1;
            } else if (strcmp(key, "cost_limit") == 0 &&
                       extract_int(bcl_in, "VALUE", &ival)) {
                STATE.executor.cost_limit = ival;
                applied = 1;
            } else if (strcmp(key, "timeout_ms") == 0 &&
                       extract_int(bcl_in, "VALUE", &ival)) {
                STATE.executor.timeout_ms = ival;
                applied = 1;
            } else if (strcmp(key, "memory_budget") == 0 &&
                       extract_int(bcl_in, "VALUE", &ival)) {
                STATE.executor.memory_budget = (size_t)ival;
                applied = 1;
            }
        }

        if (!applied) {
            return BclResult_Err(bcl_out, out_sz, 52,
                                 "set_config requires [@KEY]{name}[@VALUE]{val} with a known key");
        }
        char body[256];
        snprintf(body, sizeof(body), "[@STATUS]{config_set}[@KEY]{%s}", key);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* --- unknown command --- */
    return BclResult_Err(bcl_out, out_sz, 50, "unknown command");
}

int GraphPolicy_Close(void) {
    STATE.initialized = 0;
    memset(&STATE.policy, 0, sizeof(STATE.policy));
    memset(&STATE.executor, 0, sizeof(STATE.executor));
    return 1;
}

const char * GraphPolicy_State(void) {
    static char buf[1024];
    char pbuf[512];
    char ebuf[512];
    if (!STATE.initialized) {
        snprintf(buf, sizeof(buf), "GraphPolicy: initialized=0");
        return buf;
    }
    policy_dump(&STATE.policy, pbuf, sizeof(pbuf));
    executor_dump(&STATE.executor, ebuf, sizeof(ebuf));
    snprintf(buf, sizeof(buf),
             "GraphPolicy: initialized=%d | %s | %s",
             STATE.initialized, pbuf, ebuf);
    return buf;
}
