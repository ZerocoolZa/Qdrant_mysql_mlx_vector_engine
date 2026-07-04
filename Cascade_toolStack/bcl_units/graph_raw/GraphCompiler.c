// GraphCompiler — View Compiler for the Max Graph Engine
// Converts a declarative View into an executable Plan (like SQL query plan → IR)
// Pipeline: View → Normalizer → Planner → Execution Plan

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// === Plan structures ===

// A single traversal step in the execution plan
typedef struct PlanStep {
    int node_id;              // node to expand
    char node_type[32];       // node type
    char expand_fn_name[64];  // expansion function to call
    int depth;                // depth at this step
    float estimated_cost;     // estimated cost of this step
    float estimated_value;    // estimated value (importance)
    int parent_step;          // parent step index (-1 for root)

    // Rule that triggered this step
    char from_type[32];
    char to_type[32];
    char edge_rel[64];
    int max_children;
    float min_importance;
} PlanStep;

// Guard — a condition that must be true to continue execution
typedef struct PlanGuard {
    int max_total_nodes;      // stop if node count exceeds this
    int max_total_cost;       // stop if total cost exceeds this
    int max_depth;            // stop if depth exceeds this
    float min_importance;     // stop if importance below this
    long timeout_ms;          // stop if time exceeds this
} PlanGuard;

// The Execution Plan — compiled from a View
typedef struct Plan {
    int view_id;              // which view this plan was compiled from
    char view_name[64];       // view name for reference

    // Root nodes — where traversal starts
    int *root_node_ids;       // node IDs to start from
    int root_count;
    int root_capacity;        // capacity of root_node_ids array

    // Traversal steps — the actual execution plan
    PlanStep *steps;          // array of steps
    int step_count;
    int step_capacity;

    // Guards — execution constraints
    PlanGuard guard;

    // Budget tracking
    int budget_total;         // total budget
    int budget_used;          // budget used so far
    int node_count;           // nodes expanded so far

    // Cache keys — for result caching
    char **cache_keys;        // cache key strings
    int cache_key_count;
    int cache_key_capacity;   // capacity of cache_keys array

    // Metadata
    int compiled;             // 1 if plan has been compiled
    int executed;             // 1 if plan has been executed
} Plan;

// === Plan lifecycle ===

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
    // Copy guard from view's stop policy
    p->guard.max_total_nodes = v->stop.max_nodes;
    p->guard.max_total_cost = v->stop.max_cost;
    p->guard.max_depth = v->stop.max_depth;
    p->guard.min_importance = v->stop.min_importance;
    p->guard.timeout_ms = 5000;  // default 5s
    p->budget_total = v->stop.max_cost;
    p->budget_used = 0;
    p->node_count = 0;
    p->compiled = 0;
    p->executed = 0;
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
}

// === Plan step management ===

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
    // Set expansion function name based on node type
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
    return p->step_count - 1;  // return step index
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

// === Cache key management ===

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

// === Normalizer — makes view computable ===

// Resolve start selectors to actual node IDs in the graph
int normalize_start_nodes(Plan *p, View *v, Graph *g) {
    if (!p || !v || !g) return -1;
    int count = 0;
    for (int i = 0; i < v->start_count; i++) {
        const char *selector = v->start_selectors[i];
        if (strcmp(selector, "*") == 0) {
            // All nodes — add all as roots
            for (int j = 0; j < g->node_count && j < 100; j++) {
                if (g->nodes[j]) {
                    plan_add_root(p, g->nodes[j]->id);
                    count++;
                }
            }
        } else {
            // Specific node name
            Node *n = graph_find_node(g, selector);
            if (n) {
                plan_add_root(p, n->id);
                count++;
            }
        }
    }
    return count;
}

// === Planner — builds naive traversal tree ===

// Build traversal steps from root nodes, following view rules
int plan_build_traversal(Plan *p, View *v, Graph *g) {
    if (!p || !v || !g) return -1;
    int steps_added = 0;

    // For each root node, create initial steps
    for (int i = 0; i < p->root_count; i++) {
        Node *root = graph_find_node_by_id(g, p->root_node_ids[i]);
        if (!root) continue;

        // Find rules for this node type
        int rule_count = 0;
        ViewRule *rules = view_find_rules(v, root->type, &rule_count);

        if (rule_count > 0) {
            // Add a step for this root
            float cost = view_compute_cost(v, root, 0);
            int step_idx = plan_add_step(p, root->id, root->type, 0, cost, root->importance, -1, &rules[0]);
            steps_added++;

            // Generate cache key
            char cache_key[256];
            snprintf(cache_key, sizeof(cache_key), "%s:%s:%d", v->name, root->name, 0);
            plan_add_cache_key(p, cache_key);
        }

        if (rules) free(rules);
    }

    return steps_added;
}

// === Main compiler function ===

// compile_view: View → Plan
// Pipeline: normalize → plan → (optimizer runs separately)
Plan *compile_view(View *v, Graph *g) {
    if (!v || !g) return NULL;

    // 1. Create plan from view
    Plan *p = plan_create(v);
    if (!p) return NULL;

    // 2. Normalize: resolve start selectors to node IDs
    int root_count = normalize_start_nodes(p, v, g);
    if (root_count == 0) {
        plan_free(p);
        return NULL;
    }

    // 3. Plan: build naive traversal steps
    int steps = plan_build_traversal(p, v, g);

    // 4. Mark as compiled
    p->compiled = 1;

    return p;
}

// === Guard checks ===

int plan_check_guard(Plan *p) {
    if (!p) return 1;  // halt
    if (p->node_count >= p->guard.max_total_nodes) return 1;
    if (p->budget_used >= p->guard.max_total_cost) return 1;
    if (p->budget_used >= p->budget_total) return 1;
    return 0;
}

// === Plan dump (for debugging) ===

void plan_dump(Plan *p, char *buf, int buf_size) {
    if (!p || !buf) return;
    int pos = 0;
    pos += snprintf(buf + pos, buf_size - pos, "Plan{view=%s, compiled=%d, executed=%d}
",
        p->view_name, p->compiled, p->executed);
    pos += snprintf(buf + pos, buf_size - pos, "  roots=%d, steps=%d, cache_keys=%d
",
        p->root_count, p->step_count, p->cache_key_count);
    pos += snprintf(buf + pos, buf_size - pos, "  budget: %d/%d, nodes: %d
",
        p->budget_used, p->budget_total, p->node_count);
    pos += snprintf(buf + pos, buf_size - pos, "  guard: max_nodes=%d, max_cost=%d, max_depth=%d, min_imp=%.2f
",
        p->guard.max_total_nodes, p->guard.max_total_cost, p->guard.max_depth, p->guard.min_importance);
    for (int i = 0; i < p->step_count && pos < buf_size - 200; i++) {
        PlanStep *s = &p->steps[i];
        pos += snprintf(buf + pos, buf_size - pos,
            "  step[%d]: node=%d type=%s depth=%d cost=%.1f val=%.2f fn=%s parent=%d
",
            i, s->node_id, s->node_type, s->depth, s->estimated_cost, s->estimated_value,
            s->expand_fn_name, s->parent_step);
    }
}
