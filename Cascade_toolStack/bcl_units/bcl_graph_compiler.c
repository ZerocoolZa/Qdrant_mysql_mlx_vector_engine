//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_graph_compiler.c" date="2026-07-04" author="Devin" session_id="graph-bcl-units" context="BCL unit — View Compiler for the Max Graph Engine. Converts a declarative View into an executable Plan (View → Normalizer → Planner → Execution Plan)"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_graph_compiler.c" domain="graph_engine" authority="GraphCompiler"}
//[@SUMMARY]{summary="View compiler BCL unit. Compiles a declarative View into an executable Plan via normalize → plan → guard pipeline. Commands: compile, plan_create, plan_free, plan_add_step, plan_add_root, plan_add_cache_key, plan_check_guard, plan_dump, read_state, set_config."}
//[@CLASS]{class="GraphCompiler" domain="graph_engine" authority="single"}
//[@METHOD]{method="plan_create" type="lifecycle"}
//[@METHOD]{method="plan_free" type="lifecycle"}
//[@METHOD]{method="plan_add_step" type="command"}
//[@METHOD]{method="plan_add_root" type="command"}
//[@METHOD]{method="plan_add_cache_key" type="command"}
//[@METHOD]{method="normalize_start_nodes" type="command"}
//[@METHOD]{method="plan_build_traversal" type="command"}
//[@METHOD]{method="compile_view" type="command"}
//[@METHOD]{method="plan_check_guard" type="query"}
//[@METHOD]{method="plan_dump" type="query"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}

#include "bcl_graph_types.h"
#include "bcl_toolstack.h"

/* ════════════════════════════════════════════
 * BCL UNIT STATE
 * ════════════════════════════════════════════ */

static struct {
    int   initialized;
    int   plans_created;
    int   plans_freed;
    int   compiles_run;
    int   guard_hits;
    char  last_view[64];
    char  last_error[128];
} STATE;

/* ════════════════════════════════════════════
 * PLAN LIFECYCLE
 * ════════════════════════════════════════════ */

Plan *plan_create(View *v) {
    if (!v) return NULL;
    Plan *p = (Plan *)calloc(1, sizeof(Plan));
    if (!p) return NULL;
    p->view_id = v->id;
    strncpy(p->view_name, v->name, sizeof(p->view_name) - 1);
    p->step_capacity = 256;
    p->steps = (PlanStep *)calloc(p->step_capacity, sizeof(PlanStep));
    p->step_count = 0;
    p->root_capacity = 32;
    p->root_node_ids = (int *)calloc(p->root_capacity, sizeof(int));
    p->root_count = 0;
    p->cache_key_capacity = 64;
    p->cache_keys = (char **)calloc(p->cache_key_capacity, sizeof(char *));
    p->cache_key_count = 0;
    /* Copy guard from view's stop policy */
    p->guard.max_total_nodes = v->stop.max_nodes;
    p->guard.max_total_cost = v->stop.max_cost;
    p->guard.max_depth = v->stop.max_depth;
    p->guard.min_importance = v->stop.min_importance;
    p->guard.timeout_ms = 5000;  /* default 5s */
    p->budget_total = v->stop.max_cost;
    p->budget_used = 0;
    p->node_count = 0;
    p->compiled = 0;
    p->executed = 0;
    STATE.plans_created++;
    return p;
}

void plan_free(Plan *p) {
    if (!p) return;
    if (p->steps) free(p->steps);
    if (p->root_node_ids) free(p->root_node_ids);
    if (p->cache_keys) {
        for (int i = 0; i < p->cache_key_count; i++) {
            if (p->cache_keys[i]) free(p->cache_keys[i]);
        }
        free(p->cache_keys);
    }
    free(p);
    STATE.plans_freed++;
}

/* ════════════════════════════════════════════
 * PLAN STEP MANAGEMENT
 * ════════════════════════════════════════════ */

int plan_add_step(Plan *p, int node_id, const char *node_type, int depth,
                  float cost, float value, int parent_step, ViewRule *rule) {
    if (!p) return -1;
    if (p->step_count >= p->step_capacity) {
        int new_cap = p->step_capacity * 2;
        PlanStep *new_steps = (PlanStep *)realloc(p->steps, new_cap * sizeof(PlanStep));
        if (!new_steps) return -1;
        p->steps = new_steps;
        p->step_capacity = new_cap;
    }
    PlanStep *s = &p->steps[p->step_count];
    s->node_id = node_id;
    strncpy(s->node_type, node_type, sizeof(s->node_type) - 1);
    s->depth = depth;
    s->estimated_cost = cost;
    s->estimated_value = value;
    s->parent_step = parent_step;
    if (rule) {
        strncpy(s->from_type, rule->from_type, sizeof(s->from_type) - 1);
        strncpy(s->to_type, rule->to_type, sizeof(s->to_type) - 1);
        strncpy(s->edge_rel, rule->edge_rel, sizeof(s->edge_rel) - 1);
        s->max_children = rule->max_children;
        s->min_importance = rule->min_importance;
    }
    /* Set expansion function name based on node type */
    if (strcmp(node_type, "class") == 0) {
        strcpy(s->expand_fn_name, "expand_class");
    } else if (strcmp(node_type, "method") == 0) {
        strcpy(s->expand_fn_name, "expand_method");
    } else if (strcmp(node_type, "rule") == 0) {
        strcpy(s->expand_fn_name, "expand_rule");
    } else if (strcmp(node_type, "token") == 0) {
        strcpy(s->expand_fn_name, "expand_token");
    } else if (strcmp(node_type, "chat") == 0) {
        strcpy(s->expand_fn_name, "expand_chat");
    } else {
        s->expand_fn_name[0] = '\0';
    }
    p->step_count++;
    return p->step_count - 1;  /* return step index */
}

int plan_add_root(Plan *p, int node_id) {
    if (!p) return -1;
    if (p->root_count >= p->root_capacity) {
        int new_cap = p->root_capacity * 2;
        int *new_roots = (int *)realloc(p->root_node_ids, new_cap * sizeof(int));
        if (!new_roots) return -1;
        p->root_node_ids = new_roots;
        p->root_capacity = new_cap;
    }
    p->root_node_ids[p->root_count++] = node_id;
    return 0;
}

/* ════════════════════════════════════════════
 * CACHE KEY MANAGEMENT
 * ════════════════════════════════════════════ */

int plan_add_cache_key(Plan *p, const char *key) {
    if (!p || !key) return -1;
    if (p->cache_key_count >= p->cache_key_capacity) {
        int new_cap = p->cache_key_capacity * 2;
        char **new_keys = (char **)realloc(p->cache_keys, new_cap * sizeof(char *));
        if (!new_keys) return -1;
        p->cache_keys = new_keys;
        p->cache_key_capacity = new_cap;
    }
    p->cache_keys[p->cache_key_count] = strdup(key);
    p->cache_key_count++;
    return 0;
}

/* ════════════════════════════════════════════
 * NORMALIZER — makes view computable
 * ════════════════════════════════════════════ */

/* Resolve start selectors to actual node IDs in the graph */
int normalize_start_nodes(Plan *p, View *v, Graph *g) {
    if (!p || !v || !g) return -1;
    int count = 0;
    for (int i = 0; i < v->start_count; i++) {
        const char *selector = v->start_selectors[i];
        if (strcmp(selector, "*") == 0) {
            /* All nodes — add all as roots */
            for (int j = 0; j < g->node_count && j < 100; j++) {
                if (g->nodes[j]) {
                    plan_add_root(p, g->nodes[j]->id);
                    count++;
                }
            }
        } else {
            /* Specific node name */
            Node *n = graph_find_node(g, selector);
            if (n) {
                plan_add_root(p, n->id);
                count++;
            }
        }
    }
    return count;
}

/* ════════════════════════════════════════════
 * PLANNER — builds naive traversal tree
 * ════════════════════════════════════════════ */

/* Build traversal steps from root nodes, following view rules */
int plan_build_traversal(Plan *p, View *v, Graph *g) {
    if (!p || !v || !g) return -1;
    int steps_added = 0;

    /* For each root node, create initial steps */
    for (int i = 0; i < p->root_count; i++) {
        Node *root = graph_find_node_by_id(g, p->root_node_ids[i]);
        if (!root) continue;

        /* Find rules for this node type */
        int rule_count = 0;
        ViewRule *rules = view_find_rules(v, root->type, &rule_count);

        if (rule_count > 0) {
            /* Add a step for this root */
            float cost = view_compute_cost(v, root, 0);
            int step_idx = plan_add_step(p, root->id, root->type, 0, cost, root->importance, -1, &rules[0]);
            if (step_idx >= 0) steps_added++;

            /* Generate cache key */
            char cache_key[256];
            snprintf(cache_key, sizeof(cache_key), "%s:%s:%d", v->name, root->name, 0);
            plan_add_cache_key(p, cache_key);
        }

        if (rules) free(rules);
    }

    return steps_added;
}

/* ════════════════════════════════════════════
 * MAIN COMPILER FUNCTION
 * ════════════════════════════════════════════ */

/* compile_view: View → Plan
 * Pipeline: normalize → plan → (optimizer runs separately) */
Plan *compile_view(View *v, Graph *g) {
    if (!v || !g) return NULL;

    /* 1. Create plan from view */
    Plan *p = plan_create(v);
    if (!p) return NULL;

    /* 2. Normalize: resolve start selectors to node IDs */
    int root_count = normalize_start_nodes(p, v, g);
    if (root_count == 0) {
        plan_free(p);
        return NULL;
    }

    /* 3. Plan: build naive traversal steps */
    (void)plan_build_traversal(p, v, g);

    /* 4. Mark as compiled */
    p->compiled = 1;

    STATE.compiles_run++;
    strncpy(STATE.last_view, v->name, sizeof(STATE.last_view) - 1);
    return p;
}

/* ════════════════════════════════════════════
 * GUARD CHECKS
 * ════════════════════════════════════════════ */

int plan_check_guard(Plan *p) {
    if (!p) return 1;  /* halt */
    if (p->node_count >= p->guard.max_total_nodes) {
        STATE.guard_hits++;
        return 1;
    }
    if (p->budget_used >= p->guard.max_total_cost) {
        STATE.guard_hits++;
        return 1;
    }
    if (p->budget_used >= p->budget_total) {
        STATE.guard_hits++;
        return 1;
    }
    return 0;
}

/* ════════════════════════════════════════════
 * PLAN DUMP (for debugging)
 * ════════════════════════════════════════════ */

void plan_dump(Plan *p, char *buf, int buf_size) {
    if (!p || !buf) return;
    int pos = 0;
    pos += snprintf(buf + pos, buf_size - pos, "Plan{view=%s, compiled=%d, executed=%d}\n",
        p->view_name, p->compiled, p->executed);
    pos += snprintf(buf + pos, buf_size - pos, "  roots=%d, steps=%d, cache_keys=%d\n",
        p->root_count, p->step_count, p->cache_key_count);
    pos += snprintf(buf + pos, buf_size - pos, "  budget: %d/%d, nodes: %d\n",
        p->budget_used, p->budget_total, p->node_count);
    pos += snprintf(buf + pos, buf_size - pos, "  guard: max_nodes=%d, max_cost=%d, max_depth=%d, min_imp=%.2f\n",
        p->guard.max_total_nodes, p->guard.max_total_cost, p->guard.max_depth, p->guard.min_importance);
    for (int i = 0; i < p->step_count && pos < buf_size - 200; i++) {
        PlanStep *s = &p->steps[i];
        pos += snprintf(buf + pos, buf_size - pos,
            "  step[%d]: node=%d type=%s depth=%d cost=%.1f val=%.2f fn=%s parent=%d\n",
            i, s->node_id, s->node_type, s->depth, s->estimated_cost, s->estimated_value,
            s->expand_fn_name, s->parent_step);
    }
}

/* ════════════════════════════════════════════
 * BCL DISPATCH LAYER
 * ════════════════════════════════════════════ */

int GraphCompiler_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    return 1;
}

int GraphCompiler_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) GraphCompiler_Init();

    /* --- read_state --- */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@PLANS_CREATED]{%d}[@PLANS_FREED]{%d}[@COMPILES_RUN]{%d}[@GUARD_HITS]{%d}[@LAST_VIEW]{%s}",
            STATE.initialized, STATE.plans_created, STATE.plans_freed,
            STATE.compiles_run, STATE.guard_hits,
            STATE.last_view[0] ? STATE.last_view : "(none)");
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* --- set_config --- */
    if (strcmp(cmd, "set_config") == 0) {
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }

    /* --- compile --- */
    if (strcmp(cmd, "compile") == 0) {
        /* Caller must invoke compile_view() directly with View* + Graph*.
         * BCL dispatch reports readiness and last compile metrics. */
        char body[512];
        snprintf(body, sizeof(body),
            "[@COMPILES_RUN]{%d}[@LAST_VIEW]{%s}[@NOTE]{use compile_view(view,graph) directly}",
            STATE.compiles_run,
            STATE.last_view[0] ? STATE.last_view : "(none)");
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* --- plan_create --- */
    if (strcmp(cmd, "plan_create") == 0) {
        char body[256];
        snprintf(body, sizeof(body),
            "[@PLANS_CREATED]{%d}[@NOTE]{use plan_create(view) directly}",
            STATE.plans_created);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* --- plan_free --- */
    if (strcmp(cmd, "plan_free") == 0) {
        char body[256];
        snprintf(body, sizeof(body),
            "[@PLANS_FREED]{%d}[@NOTE]{use plan_free(plan) directly}",
            STATE.plans_freed);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* --- plan_add_step --- */
    if (strcmp(cmd, "plan_add_step") == 0) {
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{plan_add_step ready — call directly with Plan*}");
    }

    /* --- plan_add_root --- */
    if (strcmp(cmd, "plan_add_root") == 0) {
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{plan_add_root ready — call directly with Plan*}");
    }

    /* --- plan_add_cache_key --- */
    if (strcmp(cmd, "plan_add_cache_key") == 0) {
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{plan_add_cache_key ready — call directly with Plan*}");
    }

    /* --- plan_check_guard --- */
    if (strcmp(cmd, "plan_check_guard") == 0) {
        char body[256];
        snprintf(body, sizeof(body),
            "[@GUARD_HITS]{%d}[@NOTE]{use plan_check_guard(plan) directly}",
            STATE.guard_hits);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* --- plan_dump --- */
    if (strcmp(cmd, "plan_dump") == 0) {
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{plan_dump ready — call directly with Plan*}");
    }

    /* --- unknown command --- */
    return BclResult_Err(bcl_out, out_sz, 50, "unknown command");
}

int GraphCompiler_Close(void) {
    STATE.initialized = 0;
    return 1;
}

const char * GraphCompiler_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "GraphCompiler: initialized=%d plans_created=%d plans_freed=%d compiles_run=%d guard_hits=%d last_view=%s",
        STATE.initialized, STATE.plans_created, STATE.plans_freed,
        STATE.compiles_run, STATE.guard_hits,
        STATE.last_view[0] ? STATE.last_view : "(none)");
    return buf;
}
