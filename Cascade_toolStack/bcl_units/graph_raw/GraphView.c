// GraphView — View objects as first-class entities for the Max Graph Engine
// A View is a programmable lens: same graph, different views = different realities
// View = (StartNodes, ExpansionRules, StopPolicy, CostModel, OutputShape)

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// === View structures ===

// A single expansion rule within a view
typedef struct ViewRule {
    char from_type[32];      // node type to expand (e.g., "class", "method")
    char to_type[32];        // resulting child type (e.g., "method", "rule")
    char edge_rel[64];       // edge relationship (e.g., "HAS_METHOD", "CALLS")
    int max_children;        // max children per expansion (0 = unlimited)
    float min_importance;    // only expand children above this importance
} ViewRule;

// Stop policy — when to stop expanding
typedef struct StopPolicy {
    int max_depth;           // hard depth limit
    int max_nodes;           // max total nodes in result
    int max_cost;            // max total cost
    float min_importance;    // stop expanding nodes below this importance
} StopPolicy;

// Cost model — how to estimate expansion cost
typedef struct CostModel {
    float base_cost;         // cost per expansion
    float depth_multiplier;  // cost increases with depth (e.g., 1.5 = 50% more per level)
    float fanout_penalty;    // penalty for high-fanout nodes
} CostModel;

// Output shape — what the result looks like
typedef enum {
    OUTPUT_TREE,             // hierarchical tree
    OUTPUT_GRAPH,            // full graph with edges
    OUTPUT_FLAT,             // flat list of nodes
    OUTPUT_JSON              // JSON export
} OutputShape;

// The View itself — a first-class object
typedef struct View {
    int id;
    char name[64];           // view name (e.g., "WALL_VIEW", "MATERIAL_VIEW")
    char description[256];   // what this view shows

    // Start nodes — where traversal begins
    char **start_selectors;  // array of node name patterns or types
    int start_count;
    int start_capacity;      // capacity of start_selectors array

    // Expansion rules — how to expand each node type
    ViewRule *rules;
    int rule_count;
    int rule_capacity;

    // Stop policy
    StopPolicy stop;

    // Cost model
    CostModel cost;

    // Output shape
    OutputShape output;

    // Metadata
    int active;
} View;

// === View registry ===

static View *view_registry[64];
static int view_registry_count = 0;

// === View lifecycle ===

View *view_create(const char *name, const char *description) {
    View *v = (View *)calloc(1, sizeof(View));
    if (!v) return NULL;
    v->id = view_registry_count;
    strncpy(v->name, name, sizeof(v->name) - 1);
    strncpy(v->description, description, sizeof(v->description) - 1);
    v->rule_capacity = 16;
    v->rules = (ViewRule *)calloc(v->rule_capacity, sizeof(ViewRule));
    v->rule_count = 0;
    v->start_capacity = 16;
    v->start_selectors = (char **)calloc(v->start_capacity, sizeof(char *));
    v->start_count = 0;
    // Default stop policy
    v->stop.max_depth = 6;
    v->stop.max_nodes = 10000;
    v->stop.max_cost = 10000;
    v->stop.min_importance = 0.3;
    // Default cost model
    v->cost.base_cost = 1.0;
    v->cost.depth_multiplier = 1.5;
    v->cost.fanout_penalty = 0.1;
    // Default output
    v->output = OUTPUT_JSON;
    v->active = 1;
    return v;
}

void view_free(View *v) {
    if (!v) return;
    if (v->rules) free(v->rules);
    if (v->start_selectors) {
        for (int i = 0; i < v->start_count; i++) {
            if (v->start_selectors[i]) free(v->start_selectors[i]);
        }
        free(v->start_selectors);
    }
    free(v);
}

// === View configuration ===

int view_add_start(View *v, const char *selector) {
    if (!v || !selector) return -1;
    if (v->start_count >= v->start_capacity) {
        int new_cap = v->start_capacity * 2;
        char **new_arr = (char **)realloc(v->start_selectors, new_cap * sizeof(char *));
        if (!new_arr) return -1;
        v->start_selectors = new_arr;
        v->start_capacity = new_cap;
    }
    v->start_selectors[v->start_count] = strdup(selector);
    v->start_count++;
    return 0;
}

int view_add_rule(View *v, const char *from_type, const char *to_type,
                  const char *edge_rel, int max_children, float min_importance) {
    if (!v) return -1;
    if (v->rule_count >= v->rule_capacity) {
        int new_cap = v->rule_capacity * 2;
        ViewRule *new_rules = (ViewRule *)realloc(v->rules, new_cap * sizeof(ViewRule));
        if (!new_rules) return -1;
        v->rules = new_rules;
        v->rule_capacity = new_cap;
    }
    ViewRule *r = &v->rules[v->rule_count];
    strncpy(r->from_type, from_type, sizeof(r->from_type) - 1);
    strncpy(r->to_type, to_type, sizeof(r->to_type) - 1);
    strncpy(r->edge_rel, edge_rel, sizeof(r->edge_rel) - 1);
    r->max_children = max_children;
    r->min_importance = min_importance;
    v->rule_count++;
    return 0;
}

void view_set_depth(View *v, int max_depth) {
    if (v) v->stop.max_depth = max_depth;
}

void view_set_cost(View *v, float base, float depth_mult, float fanout_pen) {
    if (!v) return;
    v->cost.base_cost = base;
    v->cost.depth_multiplier = depth_mult;
    v->cost.fanout_penalty = fanout_pen;
}

void view_set_output(View *v, OutputShape shape) {
    if (v) v->output = shape;
}

void view_set_min_importance(View *v, float min_imp) {
    if (v) v->stop.min_importance = min_imp;
}

// === View registry ===

int view_register(View *v) {
    if (!v) return -1;
    if (view_registry_count >= 64) return -1;
    view_registry[view_registry_count] = v;
    v->id = view_registry_count;
    view_registry_count++;
    return v->id;
}

View *view_lookup(const char *name) {
    if (!name) return NULL;
    for (int i = 0; i < view_registry_count; i++) {
        if (view_registry[i] && strcmp(view_registry[i]->name, name) == 0) {
            return view_registry[i];
        }
    }
    return NULL;
}

// === Find rules for a node type ===

ViewRule *view_find_rules(View *v, const char *node_type, int *count_out) {
    if (!v || !node_type || !count_out) {
        if (count_out) *count_out = 0;
        return NULL;
    }
    // Count matching rules
    int count = 0;
    for (int i = 0; i < v->rule_count; i++) {
        if (strcmp(v->rules[i].from_type, node_type) == 0 ||
            strcmp(v->rules[i].from_type, "*") == 0) {
            count++;
        }
    }
    if (count == 0) {
        *count_out = 0;
        return NULL;
    }
    ViewRule *matches = (ViewRule *)calloc(count, sizeof(ViewRule));
    int idx = 0;
    for (int i = 0; i < v->rule_count; i++) {
        if (strcmp(v->rules[i].from_type, node_type) == 0 ||
            strcmp(v->rules[i].from_type, "*") == 0) {
            matches[idx++] = v->rules[i];
        }
    }
    *count_out = count;
    return matches;
}

// === Compute expansion cost for a node ===

float view_compute_cost(View *v, Node *n, int current_depth) {
    if (!v || !n) return 1.0;
    float cost = v->cost.base_cost;
    // Depth multiplier — deeper = more expensive
    for (int i = 0; i < current_depth; i++) {
        cost *= v->cost.depth_multiplier;
    }
    // Fanout penalty — nodes with many edges are more expensive
    int fanout = 0;
    Edge *e = n->first_edge;
    while (e) {
        fanout++;
        e = e->next;
    }
    cost += fanout * v->cost.fanout_penalty;
    return cost;
}

// === Check if node should be expanded in this view ===

int view_should_expand(View *v, Node *n, int current_depth, int total_nodes, int total_cost) {
    if (!v || !n) return 0;
    if (!v->active) return 0;
    if (n->expanded) return 0;
    // Depth limit
    if (current_depth >= v->stop.max_depth) return 0;
    // Node count limit
    if (total_nodes >= v->stop.max_nodes) return 0;
    // Cost limit
    if (total_cost >= v->stop.max_cost) return 0;
    // Importance threshold
    if (n->importance < v->stop.min_importance) return 0;
    // Check if there are rules for this node type
    int rule_count = 0;
    ViewRule *rules = view_find_rules(v, n->type, &rule_count);
    if (rules) free(rules);
    if (rule_count == 0) return 0;  // no rules = leaf in this view
    return 1;
}

// === Predefined views ===

void view_create_predefined() {
    // SURFACE_VIEW — shallow, just show what things are
    View *surface = view_create("SURFACE_VIEW", "Surface view — what things are");
    view_add_start(surface, "*");  // all nodes
    view_set_depth(surface, 1);
    view_set_output(surface, OUTPUT_FLAT);
    view_register(surface);

    // COMPOSITION_VIEW — what things are made of
    View *composition = view_create("COMPOSITION_VIEW", "What things are made of");
    view_add_rule(composition, "class", "method", "HAS_METHOD", 50, 0.3);
    view_add_rule(composition, "method", "method", "CALLS", 20, 0.4);
    view_set_depth(composition, 3);
    view_register(composition);

    // CAUSAL_VIEW — how things were built / causal chain
    View *causal = view_create("CAUSAL_VIEW", "How things were built — causal chain");
    view_add_rule(causal, "rule", "chat", "ORIGINATED_FROM", 5, 0.5);
    view_add_rule(causal, "class", "rule", "GOVERNED_BY", 10, 0.4);
    view_add_rule(causal, "method", "rule", "FOLLOWS_RULE", 10, 0.4);
    view_set_depth(causal, 4);
    view_register(causal);

    // FUNCTIONAL_VIEW — what things do (call graph)
    View *functional = view_create("FUNCTIONAL_VIEW", "What things do — call graph");
    view_add_rule(functional, "method", "method", "CALLS", 100, 0.2);
    view_add_rule(functional, "class", "method", "HAS_METHOD", 50, 0.3);
    view_set_depth(functional, 5);
    view_set_min_importance(functional, 0.2);
    view_register(functional);

    // SEMANTIC_VIEW — token co-occurrence and knowledge
    View *semantic = view_create("SEMANTIC_VIEW", "Semantic relationships — tokens and knowledge");
    view_add_rule(semantic, "token", "token", "CO_OCCURS", 50, 0.3);
    view_add_rule(semantic, "token", "token", "KNOWS", 50, 0.3);
    view_set_depth(semantic, 3);
    view_register(semantic);

    // DEEP_VIEW — everything, deep
    View *deep = view_create("DEEP_VIEW", "Deep traversal — everything");
    view_add_rule(deep, "*", "*", "*", 100, 0.1);
    view_set_depth(deep, 10);
    view_set_min_importance(deep, 0.1);
    view_register(deep);
}

// === Dump view as string (for debugging) ===

void view_dump(View *v, char *buf, int buf_size) {
    if (!v || !buf) return;
    int pos = 0;
    pos += snprintf(buf + pos, buf_size - pos, "View{%s: %s}
", v->name, v->description);
    pos += snprintf(buf + pos, buf_size - pos, "  start_count=%d, rule_count=%d
", v->start_count, v->rule_count);
    pos += snprintf(buf + pos, buf_size - pos, "  stop: depth=%d, max_nodes=%d, max_cost=%d, min_imp=%.2f
",
        v->stop.max_depth, v->stop.max_nodes, v->stop.max_cost, v->stop.min_importance);
    pos += snprintf(buf + pos, buf_size - pos, "  cost: base=%.1f, depth_mult=%.1f, fanout_pen=%.2f
",
        v->cost.base_cost, v->cost.depth_multiplier, v->cost.fanout_penalty);
    for (int i = 0; i < v->rule_count && pos < buf_size - 100; i++) {
        pos += snprintf(buf + pos, buf_size - pos, "  rule[%d]: %s→%s via %s (max=%d, min_imp=%.2f)
",
            i, v->rules[i].from_type, v->rules[i].to_type, v->rules[i].edge_rel,
            v->rules[i].max_children, v->rules[i].min_importance);
    }
}
