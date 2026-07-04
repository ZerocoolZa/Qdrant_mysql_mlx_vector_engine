//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_graph_view.c" date="2026-07-04" author="Devin" session_id="graph-bcl-units" context="View objects as first-class entities for the Max Graph Engine. A View is a programmable lens: same graph, different views = different realities. View = (StartNodes, ExpansionRules, StopPolicy, CostModel, OutputShape). BCL unit wrapping the raw GraphView.c implementation."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_graph_view.c" domain="graph_engine" authority="GraphView"}
//[@SUMMARY]{summary="View objects for the Max Graph Engine. A View is a programmable lens over the same graph. Implements view_create, view_free, view_add_start, view_add_rule, view_set_depth, view_set_cost, view_set_output, view_set_min_importance, view_register, view_lookup, view_find_rules, view_compute_cost, view_should_expand, view_create_predefined, view_dump. BCL dispatch via GraphView_Init/Run/Close/State."}
//[@CLASS]{class="GraphView" domain="graph_engine" authority="single"}
//[@METHOD]{method="view_create" type="lifecycle"}
//[@METHOD]{method="view_free" type="lifecycle"}
//[@METHOD]{method="view_add_start" type="command"}
//[@METHOD]{method="view_add_rule" type="command"}
//[@METHOD]{method="view_set_depth" type="command"}
//[@METHOD]{method="view_set_cost" type="command"}
//[@METHOD]{method="view_set_output" type="command"}
//[@METHOD]{method="view_set_min_importance" type="command"}
//[@METHOD]{method="view_register" type="command"}
//[@METHOD]{method="view_lookup" type="query"}
//[@METHOD]{method="view_find_rules" type="query"}
//[@METHOD]{method="view_compute_cost" type="query"}
//[@METHOD]{method="view_should_expand" type="query"}
//[@METHOD]{method="view_create_predefined" type="command"}
//[@METHOD]{method="view_dump" type="query"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}

#include "bcl_graph_types.h"
#include "bcl_toolstack.h"

/* ════════════════════════════════════════════
 * VIEW REGISTRY
 * ════════════════════════════════════════════ */

static View *view_registry[64];
static int view_registry_count = 0;

/* ════════════════════════════════════════════
 * VIEW LIFECYCLE
 * ════════════════════════════════════════════ */

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
    /* Default stop policy */
    v->stop.max_depth = 6;
    v->stop.max_nodes = 10000;
    v->stop.max_cost = 10000;
    v->stop.min_importance = 0.3;
    /* Default cost model */
    v->cost.base_cost = 1.0;
    v->cost.depth_multiplier = 1.5;
    v->cost.fanout_penalty = 0.1;
    /* Default output */
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

/* ════════════════════════════════════════════
 * VIEW CONFIGURATION
 * ════════════════════════════════════════════ */

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

/* ════════════════════════════════════════════
 * VIEW REGISTRY OPERATIONS
 * ════════════════════════════════════════════ */

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

/* ════════════════════════════════════════════
 * FIND RULES FOR A NODE TYPE
 * ════════════════════════════════════════════ */

ViewRule *view_find_rules(View *v, const char *node_type, int *count_out) {
    if (!v || !node_type || !count_out) {
        if (count_out) *count_out = 0;
        return NULL;
    }
    /* Count matching rules */
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

/* ════════════════════════════════════════════
 * COMPUTE EXPANSION COST FOR A NODE
 * ════════════════════════════════════════════ */

float view_compute_cost(View *v, Node *n, int current_depth) {
    if (!v || !n) return 1.0;
    float cost = v->cost.base_cost;
    /* Depth multiplier — deeper = more expensive */
    for (int i = 0; i < current_depth; i++) {
        cost *= v->cost.depth_multiplier;
    }
    /* Fanout penalty — nodes with many edges are more expensive */
    int fanout = 0;
    Edge *e = n->first_edge;
    while (e) {
        fanout++;
        e = e->next;
    }
    cost += fanout * v->cost.fanout_penalty;
    return cost;
}

/* ════════════════════════════════════════════
 * CHECK IF NODE SHOULD BE EXPANDED IN THIS VIEW
 * ════════════════════════════════════════════ */

int view_should_expand(View *v, Node *n, int current_depth, int total_nodes, int total_cost) {
    if (!v || !n) return 0;
    if (!v->active) return 0;
    if (n->expanded) return 0;
    /* Depth limit */
    if (current_depth >= v->stop.max_depth) return 0;
    /* Node count limit */
    if (total_nodes >= v->stop.max_nodes) return 0;
    /* Cost limit */
    if (total_cost >= v->stop.max_cost) return 0;
    /* Importance threshold */
    if (n->importance < v->stop.min_importance) return 0;
    /* Check if there are rules for this node type */
    int rule_count = 0;
    ViewRule *rules = view_find_rules(v, n->type, &rule_count);
    if (rules) free(rules);
    if (rule_count == 0) return 0;  /* no rules = leaf in this view */
    return 1;
}

/* ════════════════════════════════════════════
 * PREDEFINED VIEWS
 * ════════════════════════════════════════════ */

void view_create_predefined(void) {
    /* SURFACE_VIEW — shallow, just show what things are */
    View *surface = view_create("SURFACE_VIEW", "Surface view — what things are");
    view_add_start(surface, "*");  /* all nodes */
    view_set_depth(surface, 1);
    view_set_output(surface, OUTPUT_FLAT);
    view_register(surface);

    /* COMPOSITION_VIEW — what things are made of */
    View *composition = view_create("COMPOSITION_VIEW", "What things are made of");
    view_add_rule(composition, "class", "method", "HAS_METHOD", 50, 0.3);
    view_add_rule(composition, "method", "method", "CALLS", 20, 0.4);
    view_set_depth(composition, 3);
    view_register(composition);

    /* CAUSAL_VIEW — how things were built / causal chain */
    View *causal = view_create("CAUSAL_VIEW", "How things were built — causal chain");
    view_add_rule(causal, "rule", "chat", "ORIGINATED_FROM", 5, 0.5);
    view_add_rule(causal, "class", "rule", "GOVERNED_BY", 10, 0.4);
    view_add_rule(causal, "method", "rule", "FOLLOWS_RULE", 10, 0.4);
    view_set_depth(causal, 4);
    view_register(causal);

    /* FUNCTIONAL_VIEW — what things do (call graph) */
    View *functional = view_create("FUNCTIONAL_VIEW", "What things do — call graph");
    view_add_rule(functional, "method", "method", "CALLS", 100, 0.2);
    view_add_rule(functional, "class", "method", "HAS_METHOD", 50, 0.3);
    view_set_depth(functional, 5);
    view_set_min_importance(functional, 0.2);
    view_register(functional);

    /* SEMANTIC_VIEW — token co-occurrence and knowledge */
    View *semantic = view_create("SEMANTIC_VIEW", "Semantic relationships — tokens and knowledge");
    view_add_rule(semantic, "token", "token", "CO_OCCURS", 50, 0.3);
    view_add_rule(semantic, "token", "token", "KNOWS", 50, 0.3);
    view_set_depth(semantic, 3);
    view_register(semantic);

    /* DEEP_VIEW — everything, deep */
    View *deep = view_create("DEEP_VIEW", "Deep traversal — everything");
    view_add_rule(deep, "*", "*", "*", 100, 0.1);
    view_set_depth(deep, 10);
    view_set_min_importance(deep, 0.1);
    view_register(deep);
}

/* ════════════════════════════════════════════
 * DUMP VIEW AS STRING (for debugging)
 * ════════════════════════════════════════════ */

void view_dump(View *v, char *buf, int buf_size) {
    if (!v || !buf) return;
    int pos = 0;
    pos += snprintf(buf + pos, buf_size - pos, "View{%s: %s}\n", v->name, v->description);
    pos += snprintf(buf + pos, buf_size - pos, "  start_count=%d, rule_count=%d\n",
                    v->start_count, v->rule_count);
    pos += snprintf(buf + pos, buf_size - pos,
                    "  stop: depth=%d, max_nodes=%d, max_cost=%d, min_imp=%.2f\n",
                    v->stop.max_depth, v->stop.max_nodes, v->stop.max_cost, v->stop.min_importance);
    pos += snprintf(buf + pos, buf_size - pos,
                    "  cost: base=%.1f, depth_mult=%.1f, fanout_pen=%.2f\n",
                    v->cost.base_cost, v->cost.depth_multiplier, v->cost.fanout_penalty);
    for (int i = 0; i < v->rule_count && pos < buf_size - 100; i++) {
        pos += snprintf(buf + pos, buf_size - pos,
                        "  rule[%d]: %s->%s via %s (max=%d, min_imp=%.2f)\n",
                        i, v->rules[i].from_type, v->rules[i].to_type, v->rules[i].edge_rel,
                        v->rules[i].max_children, v->rules[i].min_importance);
    }
}

/* ════════════════════════════════════════════════════════════════════════════
 * BCL UNIT DISPATCH LAYER
 * Init / Run / Close / State — the BCL packet interface
 * ════════════════════════════════════════════════════════════════════════════ */

static struct {
    int initialized;
    int predefined_created;
} GV_STATE;

int GraphView_Init(void) {
    memset(&GV_STATE, 0, sizeof(GV_STATE));
    /* Reset registry */
    view_registry_count = 0;
    memset(view_registry, 0, sizeof(view_registry));
    /* Create predefined views */
    view_create_predefined();
    GV_STATE.predefined_created = 1;
    GV_STATE.initialized = 1;
    return 1;
}

int GraphView_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!GV_STATE.initialized) GraphView_Init();

    /* ── read_state ─────────────────────────────────────────── */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
                 "[@INITIALIZED]{%d}[@PREDEFINED]{%d}[@VIEW_COUNT]{%d}",
                 GV_STATE.initialized, GV_STATE.predefined_created, view_registry_count);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── set_config ─────────────────────────────────────────── */
    if (strcmp(cmd, "set_config") == 0) {
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }

    /* ── create ─────────────────────────────────────────────── */
    if (strcmp(cmd, "create") == 0) {
        char name[64];
        char description[256];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        name[0] = '\0';
        description[0] = '\0';
        BclParser_Extract(&pr, "NAME", name, sizeof(name));
        BclParser_Extract(&pr, "DESCRIPTION", description, sizeof(description));
        BclParser_Free(&pr);
        if (name[0] == '\0') {
            return BclResult_Err(bcl_out, out_sz, 51, "create: NAME tag required");
        }
        View *v = view_create(name, description);
        if (!v) {
            return BclResult_Err(bcl_out, out_sz, 52, "create: view_create failed");
        }
        char body[256];
        snprintf(body, sizeof(body), "[@VIEW_ID]{%d}[@VIEW_NAME]{%s}", v->id, v->name);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── free ───────────────────────────────────────────────── */
    if (strcmp(cmd, "free") == 0) {
        char name[64];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        name[0] = '\0';
        BclParser_Extract(&pr, "NAME", name, sizeof(name));
        BclParser_Free(&pr);
        if (name[0] == '\0') {
            return BclResult_Err(bcl_out, out_sz, 51, "free: NAME tag required");
        }
        View *v = view_lookup(name);
        if (!v) {
            return BclResult_Err(bcl_out, out_sz, 53, "free: view not found");
        }
        view_free(v);
        /* Remove from registry */
        for (int i = 0; i < view_registry_count; i++) {
            if (view_registry[i] == v) {
                view_registry[i] = NULL;
                break;
            }
        }
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{freed}");
    }

    /* ── add_start ──────────────────────────────────────────── */
    if (strcmp(cmd, "add_start") == 0) {
        char name[64];
        char selector[256];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        name[0] = '\0';
        selector[0] = '\0';
        BclParser_Extract(&pr, "NAME", name, sizeof(name));
        BclParser_Extract(&pr, "SELECTOR", selector, sizeof(selector));
        BclParser_Free(&pr);
        if (name[0] == '\0' || selector[0] == '\0') {
            return BclResult_Err(bcl_out, out_sz, 51, "add_start: NAME and SELECTOR tags required");
        }
        View *v = view_lookup(name);
        if (!v) {
            return BclResult_Err(bcl_out, out_sz, 53, "add_start: view not found");
        }
        int rc = view_add_start(v, selector);
        if (rc != 0) {
            return BclResult_Err(bcl_out, out_sz, 54, "add_start: view_add_start failed");
        }
        char body[256];
        snprintf(body, sizeof(body), "[@STATUS]{added}[@START_COUNT]{%d}", v->start_count);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── add_rule ───────────────────────────────────────────── */
    if (strcmp(cmd, "add_rule") == 0) {
        char name[64];
        char from_type[32];
        char to_type[32];
        char edge_rel[64];
        char max_children_str[16];
        char min_imp_str[16];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        name[0] = '\0'; from_type[0] = '\0'; to_type[0] = '\0';
        edge_rel[0] = '\0'; max_children_str[0] = '\0'; min_imp_str[0] = '\0';
        BclParser_Extract(&pr, "NAME", name, sizeof(name));
        BclParser_Extract(&pr, "FROM_TYPE", from_type, sizeof(from_type));
        BclParser_Extract(&pr, "TO_TYPE", to_type, sizeof(to_type));
        BclParser_Extract(&pr, "EDGE_REL", edge_rel, sizeof(edge_rel));
        BclParser_Extract(&pr, "MAX_CHILDREN", max_children_str, sizeof(max_children_str));
        BclParser_Extract(&pr, "MIN_IMPORTANCE", min_imp_str, sizeof(min_imp_str));
        BclParser_Free(&pr);
        if (name[0] == '\0' || from_type[0] == '\0' || to_type[0] == '\0' || edge_rel[0] == '\0') {
            return BclResult_Err(bcl_out, out_sz, 51,
                                 "add_rule: NAME, FROM_TYPE, TO_TYPE, EDGE_REL tags required");
        }
        View *v = view_lookup(name);
        if (!v) {
            return BclResult_Err(bcl_out, out_sz, 53, "add_rule: view not found");
        }
        int max_children = max_children_str[0] ? atoi(max_children_str) : 0;
        float min_imp = min_imp_str[0] ? (float)atof(min_imp_str) : 0.0;
        int rc = view_add_rule(v, from_type, to_type, edge_rel, max_children, min_imp);
        if (rc != 0) {
            return BclResult_Err(bcl_out, out_sz, 54, "add_rule: view_add_rule failed");
        }
        char body[256];
        snprintf(body, sizeof(body), "[@STATUS]{added}[@RULE_COUNT]{%d}", v->rule_count);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── set_depth ──────────────────────────────────────────── */
    if (strcmp(cmd, "set_depth") == 0) {
        char name[64];
        char depth_str[16];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        name[0] = '\0'; depth_str[0] = '\0';
        BclParser_Extract(&pr, "NAME", name, sizeof(name));
        BclParser_Extract(&pr, "MAX_DEPTH", depth_str, sizeof(depth_str));
        BclParser_Free(&pr);
        if (name[0] == '\0' || depth_str[0] == '\0') {
            return BclResult_Err(bcl_out, out_sz, 51, "set_depth: NAME and MAX_DEPTH tags required");
        }
        View *v = view_lookup(name);
        if (!v) {
            return BclResult_Err(bcl_out, out_sz, 53, "set_depth: view not found");
        }
        view_set_depth(v, atoi(depth_str));
        char body[256];
        snprintf(body, sizeof(body), "[@STATUS]{set}[@MAX_DEPTH]{%d}", v->stop.max_depth);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── set_cost ───────────────────────────────────────────── */
    if (strcmp(cmd, "set_cost") == 0) {
        char name[64];
        char base_str[16];
        char depth_mult_str[16];
        char fanout_pen_str[16];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        name[0] = '\0'; base_str[0] = '\0';
        depth_mult_str[0] = '\0'; fanout_pen_str[0] = '\0';
        BclParser_Extract(&pr, "NAME", name, sizeof(name));
        BclParser_Extract(&pr, "BASE_COST", base_str, sizeof(base_str));
        BclParser_Extract(&pr, "DEPTH_MULT", depth_mult_str, sizeof(depth_mult_str));
        BclParser_Extract(&pr, "FANOUT_PEN", fanout_pen_str, sizeof(fanout_pen_str));
        BclParser_Free(&pr);
        if (name[0] == '\0') {
            return BclResult_Err(bcl_out, out_sz, 51, "set_cost: NAME tag required");
        }
        View *v = view_lookup(name);
        if (!v) {
            return BclResult_Err(bcl_out, out_sz, 53, "set_cost: view not found");
        }
        float base = base_str[0] ? (float)atof(base_str) : 1.0;
        float depth_mult = depth_mult_str[0] ? (float)atof(depth_mult_str) : 1.5;
        float fanout_pen = fanout_pen_str[0] ? (float)atof(fanout_pen_str) : 0.1;
        view_set_cost(v, base, depth_mult, fanout_pen);
        char body[256];
        snprintf(body, sizeof(body),
                 "[@STATUS]{set}[@BASE]{%.2f}[@DEPTH_MULT]{%.2f}[@FANOUT_PEN]{%.2f}",
                 v->cost.base_cost, v->cost.depth_multiplier, v->cost.fanout_penalty);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── set_output ─────────────────────────────────────────── */
    if (strcmp(cmd, "set_output") == 0) {
        char name[64];
        char shape_str[32];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        name[0] = '\0'; shape_str[0] = '\0';
        BclParser_Extract(&pr, "NAME", name, sizeof(name));
        BclParser_Extract(&pr, "OUTPUT_SHAPE", shape_str, sizeof(shape_str));
        BclParser_Free(&pr);
        if (name[0] == '\0' || shape_str[0] == '\0') {
            return BclResult_Err(bcl_out, out_sz, 51, "set_output: NAME and OUTPUT_SHAPE tags required");
        }
        View *v = view_lookup(name);
        if (!v) {
            return BclResult_Err(bcl_out, out_sz, 53, "set_output: view not found");
        }
        OutputShape shape = OUTPUT_JSON;
        if (strcmp(shape_str, "TREE") == 0) shape = OUTPUT_TREE;
        else if (strcmp(shape_str, "GRAPH") == 0) shape = OUTPUT_GRAPH;
        else if (strcmp(shape_str, "FLAT") == 0) shape = OUTPUT_FLAT;
        else if (strcmp(shape_str, "JSON") == 0) shape = OUTPUT_JSON;
        view_set_output(v, shape);
        const char *shape_names[] = {"TREE", "GRAPH", "FLAT", "JSON"};
        const char *sname = (shape >= 0 && shape <= 3) ? shape_names[shape] : "UNKNOWN";
        char body[256];
        snprintf(body, sizeof(body), "[@STATUS]{set}[@OUTPUT_SHAPE]{%s}", sname);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── set_min_importance ─────────────────────────────────── */
    if (strcmp(cmd, "set_min_importance") == 0) {
        char name[64];
        char min_imp_str[16];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        name[0] = '\0'; min_imp_str[0] = '\0';
        BclParser_Extract(&pr, "NAME", name, sizeof(name));
        BclParser_Extract(&pr, "MIN_IMPORTANCE", min_imp_str, sizeof(min_imp_str));
        BclParser_Free(&pr);
        if (name[0] == '\0' || min_imp_str[0] == '\0') {
            return BclResult_Err(bcl_out, out_sz, 51,
                                 "set_min_importance: NAME and MIN_IMPORTANCE tags required");
        }
        View *v = view_lookup(name);
        if (!v) {
            return BclResult_Err(bcl_out, out_sz, 53, "set_min_importance: view not found");
        }
        view_set_min_importance(v, (float)atof(min_imp_str));
        char body[256];
        snprintf(body, sizeof(body), "[@STATUS]{set}[@MIN_IMPORTANCE]{%.2f}", v->stop.min_importance);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── register ───────────────────────────────────────────── */
    if (strcmp(cmd, "register") == 0) {
        char name[64];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        name[0] = '\0';
        BclParser_Extract(&pr, "NAME", name, sizeof(name));
        BclParser_Free(&pr);
        if (name[0] == '\0') {
            return BclResult_Err(bcl_out, out_sz, 51, "register: NAME tag required");
        }
        View *v = view_lookup(name);
        if (!v) {
            return BclResult_Err(bcl_out, out_sz, 53, "register: view not found (create first)");
        }
        /* If already registered, return existing id */
        if (v->id >= 0 && v->id < view_registry_count && view_registry[v->id] == v) {
            char body[128];
            snprintf(body, sizeof(body), "[@VIEW_ID]{%d}[@STATUS]{already_registered}", v->id);
            return BclResult_Ok(bcl_out, out_sz, body);
        }
        int id = view_register(v);
        if (id < 0) {
            return BclResult_Err(bcl_out, out_sz, 55, "register: registry full (max 64)");
        }
        char body[128];
        snprintf(body, sizeof(body), "[@VIEW_ID]{%d}[@STATUS]{registered}", id);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── lookup ─────────────────────────────────────────────── */
    if (strcmp(cmd, "lookup") == 0) {
        char name[64];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        name[0] = '\0';
        BclParser_Extract(&pr, "NAME", name, sizeof(name));
        BclParser_Free(&pr);
        if (name[0] == '\0') {
            return BclResult_Err(bcl_out, out_sz, 51, "lookup: NAME tag required");
        }
        View *v = view_lookup(name);
        if (!v) {
            return BclResult_Err(bcl_out, out_sz, 53, "lookup: view not found");
        }
        char body[512];
        snprintf(body, sizeof(body),
                 "[@VIEW_ID]{%d}[@VIEW_NAME]{%s}[@DESCRIPTION]{%s}[@RULE_COUNT]{%d}[@START_COUNT]{%d}[@ACTIVE]{%d}",
                 v->id, v->name, v->description, v->rule_count, v->start_count, v->active);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── find_rules ─────────────────────────────────────────── */
    if (strcmp(cmd, "find_rules") == 0) {
        char name[64];
        char node_type[32];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        name[0] = '\0'; node_type[0] = '\0';
        BclParser_Extract(&pr, "NAME", name, sizeof(name));
        BclParser_Extract(&pr, "NODE_TYPE", node_type, sizeof(node_type));
        BclParser_Free(&pr);
        if (name[0] == '\0' || node_type[0] == '\0') {
            return BclResult_Err(bcl_out, out_sz, 51, "find_rules: NAME and NODE_TYPE tags required");
        }
        View *v = view_lookup(name);
        if (!v) {
            return BclResult_Err(bcl_out, out_sz, 53, "find_rules: view not found");
        }
        int count = 0;
        ViewRule *rules = view_find_rules(v, node_type, &count);
        char body[4096];
        int pos = 0;
        pos += snprintf(body + pos, sizeof(body) - pos, "[@RULE_COUNT]{%d}", count);
        for (int i = 0; i < count && pos < (int)sizeof(body) - 128; i++) {
            pos += snprintf(body + pos, sizeof(body) - pos,
                            "[@RULE%d]{%s->%s via %s max=%d min_imp=%.2f}",
                            i, rules[i].from_type, rules[i].to_type, rules[i].edge_rel,
                            rules[i].max_children, rules[i].min_importance);
        }
        if (rules) free(rules);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── compute_cost ───────────────────────────────────────── */
    if (strcmp(cmd, "compute_cost") == 0) {
        char name[64];
        char depth_str[16];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        name[0] = '\0'; depth_str[0] = '\0';
        BclParser_Extract(&pr, "NAME", name, sizeof(name));
        BclParser_Extract(&pr, "DEPTH", depth_str, sizeof(depth_str));
        BclParser_Free(&pr);
        if (name[0] == '\0') {
            return BclResult_Err(bcl_out, out_sz, 51, "compute_cost: NAME tag required");
        }
        View *v = view_lookup(name);
        if (!v) {
            return BclResult_Err(bcl_out, out_sz, 53, "compute_cost: view not found");
        }
        int depth = depth_str[0] ? atoi(depth_str) : 0;
        /* Compute cost for a synthetic node at given depth (no real node available via BCL) */
        float cost = v->cost.base_cost;
        for (int i = 0; i < depth; i++) {
            cost *= v->cost.depth_multiplier;
        }
        char body[256];
        snprintf(body, sizeof(body), "[@COST]{%.4f}[@DEPTH]{%d}[@BASE]{%.2f}[@DEPTH_MULT]{%.2f}",
                 cost, depth, v->cost.base_cost, v->cost.depth_multiplier);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── should_expand ──────────────────────────────────────── */
    if (strcmp(cmd, "should_expand") == 0) {
        char name[64];
        char depth_str[16];
        char total_nodes_str[16];
        char total_cost_str[16];
        char importance_str[16];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        name[0] = '\0'; depth_str[0] = '\0';
        total_nodes_str[0] = '\0'; total_cost_str[0] = '\0'; importance_str[0] = '\0';
        BclParser_Extract(&pr, "NAME", name, sizeof(name));
        BclParser_Extract(&pr, "DEPTH", depth_str, sizeof(depth_str));
        BclParser_Extract(&pr, "TOTAL_NODES", total_nodes_str, sizeof(total_nodes_str));
        BclParser_Extract(&pr, "TOTAL_COST", total_cost_str, sizeof(total_cost_str));
        BclParser_Extract(&pr, "IMPORTANCE", importance_str, sizeof(importance_str));
        BclParser_Free(&pr);
        if (name[0] == '\0') {
            return BclResult_Err(bcl_out, out_sz, 51, "should_expand: NAME tag required");
        }
        View *v = view_lookup(name);
        if (!v) {
            return BclResult_Err(bcl_out, out_sz, 53, "should_expand: view not found");
        }
        int depth = depth_str[0] ? atoi(depth_str) : 0;
        int total_nodes = total_nodes_str[0] ? atoi(total_nodes_str) : 0;
        int total_cost = total_cost_str[0] ? atoi(total_cost_str) : 0;
        float importance = importance_str[0] ? (float)atof(importance_str) : 0.5;
        /* Build a temporary node to test the policy */
        Node testnode;
        memset(&testnode, 0, sizeof(testnode));
        testnode.importance = importance;
        testnode.expanded = 0;
        testnode.first_edge = NULL;
        /* Check stop-policy conditions without requiring rules */
        int should = 1;
        if (!v->active) should = 0;
        if (depth >= v->stop.max_depth) should = 0;
        if (total_nodes >= v->stop.max_nodes) should = 0;
        if (total_cost >= v->stop.max_cost) should = 0;
        if (importance < v->stop.min_importance) should = 0;
        char body[256];
        snprintf(body, sizeof(body),
                 "[@SHOULD_EXPAND]{%d}[@DEPTH]{%d}[@MAX_DEPTH]{%d}[@IMPORTANCE]{%.2f}[@MIN_IMPORTANCE]{%.2f}",
                 should, depth, v->stop.max_depth, importance, v->stop.min_importance);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── create_predefined ──────────────────────────────────── */
    if (strcmp(cmd, "create_predefined") == 0) {
        if (GV_STATE.predefined_created) {
            char body[128];
            snprintf(body, sizeof(body),
                     "[@STATUS]{already_created}[@VIEW_COUNT]{%d}", view_registry_count);
            return BclResult_Ok(bcl_out, out_sz, body);
        }
        view_create_predefined();
        GV_STATE.predefined_created = 1;
        char body[128];
        snprintf(body, sizeof(body), "[@STATUS]{created}[@VIEW_COUNT]{%d}", view_registry_count);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── dump ───────────────────────────────────────────────── */
    if (strcmp(cmd, "dump") == 0) {
        char name[64];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        name[0] = '\0';
        BclParser_Extract(&pr, "NAME", name, sizeof(name));
        BclParser_Free(&pr);
        if (name[0] == '\0') {
            return BclResult_Err(bcl_out, out_sz, 51, "dump: NAME tag required");
        }
        View *v = view_lookup(name);
        if (!v) {
            return BclResult_Err(bcl_out, out_sz, 53, "dump: view not found");
        }
        char dumpbuf[4096];
        view_dump(v, dumpbuf, sizeof(dumpbuf));
        char body[4200];
        snprintf(body, sizeof(body), "[@VIEW_DUMP]{%s}", dumpbuf);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── list ───────────────────────────────────────────────── */
    if (strcmp(cmd, "list") == 0) {
        char body[4096];
        int pos = 0;
        pos += snprintf(body + pos, sizeof(body) - pos, "[@VIEW_COUNT]{%d}", view_registry_count);
        for (int i = 0; i < view_registry_count && pos < (int)sizeof(body) - 128; i++) {
            if (!view_registry[i]) continue;
            pos += snprintf(body + pos, sizeof(body) - pos,
                            "[@VIEW%d]{id=%d name=%s rules=%d starts=%d}",
                            i, view_registry[i]->id, view_registry[i]->name,
                            view_registry[i]->rule_count, view_registry[i]->start_count);
        }
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── unknown command ────────────────────────────────────── */
    char errbuf[256];
    snprintf(errbuf, sizeof(errbuf), "unknown command: %s", cmd);
    return BclResult_Err(bcl_out, out_sz, 50, errbuf);
}

int GraphView_Close(void) {
    /* Free all registered views */
    for (int i = 0; i < view_registry_count; i++) {
        if (view_registry[i]) {
            view_free(view_registry[i]);
            view_registry[i] = NULL;
        }
    }
    view_registry_count = 0;
    GV_STATE.initialized = 0;
    GV_STATE.predefined_created = 0;
    return 1;
}

const char * GraphView_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
             "GraphView: initialized=%d predefined=%d views=%d",
             GV_STATE.initialized, GV_STATE.predefined_created, view_registry_count);
    return buf;
}
