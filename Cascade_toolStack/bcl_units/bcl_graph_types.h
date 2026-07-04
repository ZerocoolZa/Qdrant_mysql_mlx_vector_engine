//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_graph_types.h" date="2026-07-04" author="Devin" session_id="graph-bcl-units" context="Shared header for Max Graph Engine BCL units — all graph types, function declarations, constants"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_graph_types.h" domain="graph_engine" authority="GraphTypes"}
//[@SUMMARY]{summary="Shared header for graph engine BCL units. Defines Node, Edge, Graph, Policy, Executor, View, Plan, TraceLog, GraphCache, LearningModel, Config + all function declarations. Included by all bcl_graph_*.c units."}
//[@CLASS]{class="GraphTypes" domain="graph_engine" authority="shared_header"}
//[@METHOD]{method="graph_create" type="lifecycle"}
//[@METHOD]{method="graph_free" type="lifecycle"}
//[@METHOD]{method="graph_add_node" type="command"}
//[@METHOD]{method="graph_add_edge" type="command"}
//[@METHOD]{method="graph_find_node" type="query"}
//[@METHOD]{method="graph_find_node_by_id" type="query"}
//[@METHOD]{method="edge_create" type="command"}
//[@METHOD]{method="node_create" type="command"}

#ifndef BCL_GRAPH_TYPES_H
#define BCL_GRAPH_TYPES_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <math.h>

/* ════════════════════════════════════════════
 * CONSTANTS
 * ════════════════════════════════════════════ */

#define GRAPH_MAX_NAME      256
#define GRAPH_MAX_TYPE       32
#define GRAPH_MAX_REL        64
#define GRAPH_MAX_NODES   10000
#define GRAPH_MAX_EDGES   20000
#define GRAPH_MAX_DEPTH      64
#define GRAPH_BUF_SIZE    65536
#define GRAPH_MAX_RESULT  65536

/* ════════════════════════════════════════════
 * FORWARD DECLARATIONS
 * ════════════════════════════════════════════ */

typedef struct Node Node;
typedef struct Edge Edge;
typedef struct Graph Graph;
typedef struct Policy Policy;
typedef struct Executor Executor;
typedef struct ClassData ClassData;
typedef struct MethodData MethodData;
typedef struct RuleData RuleData;
typedef struct ViewRule ViewRule;
typedef struct StopPolicy StopPolicy;
typedef struct CostModel CostModel;
typedef struct View View;
typedef struct PlanStep PlanStep;
typedef struct PlanGuard PlanGuard;
typedef struct Plan Plan;
typedef struct TraceEntry TraceEntry;
typedef struct TraceLog TraceLog;
typedef struct LearningSignal LearningSignal;
typedef struct GraphCache GraphCache;
typedef struct CacheEntry CacheEntry;
typedef struct ScopeRule ScopeRule;
typedef struct CacheStats CacheStats;
typedef struct LearningModel LearningModel;
typedef struct WeightEntry WeightEntry;
typedef struct RecentPath RecentPath;
typedef struct Config Config;
typedef struct ConfigEntry ConfigEntry;

/* ════════════════════════════════════════════
 * CORE GRAPH TYPES
 * ════════════════════════════════════════════ */

/* Expansion function pointer — nodes expand themselves.
 * children_out is an out-parameter: the function allocates a Node* array
 * (array of pointers) and returns it via *children_out. Caller frees the
 * pointer array only (the nodes themselves are owned by the graph). */
typedef int (*ExpandFn)(Node *node, Graph *g, int depth_left, Node ***children_out);

/* Node data payloads */
struct ClassData {
    char class_name[GRAPH_MAX_NAME];
    char file_path[GRAPH_MAX_NAME];
    int  method_count;
};

struct MethodData {
    char method_name[GRAPH_MAX_NAME];
    char class_name[GRAPH_MAX_NAME];
    char signature[512];
};

struct RuleData {
    char rule_text[GRAPH_MAX_NAME];
    int  rule_id;
};

/* Node — the fundamental unit of the graph */
struct Node {
    int       id;
    char      name[GRAPH_MAX_NAME];
    char      type[GRAPH_MAX_TYPE];
    float     importance;       /* 0.0 to 1.0 */
    int       expanded;         /* 1 if already expanded */
    int       depth;            /* depth in traversal tree */
    float     cost;             /* cost to expand this node */
    void     *data;             /* ClassData, MethodData, RuleData, etc. */
    ExpandFn  expand;           /* node's own expansion function */
    Edge     *first_edge;       /* linked list of edges from this node */
};

/* Edge — relationship between two nodes */
struct Edge {
    int    id;
    Node  *source;
    Node  *target;
    char   rel_type[GRAPH_MAX_REL];   /* "CALLS", "HAS_METHOD", "EXPANDS_TO" */
    float  weight;
    Edge  *next;                      /* linked list (per source node) */
};

/* Policy — decides whether a node should expand */
struct Policy {
    int    hard_limit;            /* hard depth limit */
    int    context_limit;         /* context-specific override (0 = use hard) */
    float  attention_threshold;   /* only expand nodes above this importance */
    int    max_nodes_per_hop;
    int    max_total_nodes;
};

/* Executor — tracks resource usage during traversal */
struct Executor {
    size_t memory_used;
    size_t memory_budget;
    int    cost_used;
    int    cost_limit;
    int    timeout_ms;
    long   start_time_ms;
    int    halted;
};

/* Graph — the complete graph structure */
struct Graph {
    Node    **nodes;
    int       node_count;
    int       node_capacity;
    Edge    **edges;
    int       edge_count;
    int       edge_capacity;
    Policy    policy;
    Executor  executor;
    char      mysql_host[256];
    char      mysql_user[64];
    char      mysql_db[64];
};

/* ════════════════════════════════════════════
 * VIEW TYPES (from GraphView)
 * ════════════════════════════════════════════ */

struct ViewRule {
    char   from_type[GRAPH_MAX_TYPE];
    char   to_type[GRAPH_MAX_TYPE];
    char   edge_rel[GRAPH_MAX_REL];
    int    max_children;
    float  min_importance;
};

struct StopPolicy {
    int    max_depth;
    int    max_nodes;
    int    max_cost;
    float  min_importance;
};

struct CostModel {
    float  base_cost;
    float  depth_multiplier;
    float  fanout_penalty;
};

typedef enum {
    OUTPUT_TREE,
    OUTPUT_GRAPH,
    OUTPUT_FLAT,
    OUTPUT_JSON
} OutputShape;

struct View {
    int          id;
    char         name[64];
    char         description[256];
    char       **start_selectors;
    int          start_count;
    int          start_capacity;
    ViewRule    *rules;
    int          rule_count;
    int          rule_capacity;
    StopPolicy   stop;
    CostModel    cost;
    OutputShape  output;
    int          active;
};

/* ════════════════════════════════════════════
 * PLAN TYPES (from GraphCompiler)
 * ════════════════════════════════════════════ */

struct PlanStep {
    int    node_id;
    char   node_type[GRAPH_MAX_TYPE];
    char   expand_fn_name[64];
    int    depth;
    float  estimated_cost;
    float  estimated_value;
    int    parent_step;
    char   from_type[GRAPH_MAX_TYPE];
    char   to_type[GRAPH_MAX_TYPE];
    char   edge_rel[GRAPH_MAX_REL];
    int    max_children;
    float  min_importance;
};

struct PlanGuard {
    int    max_total_nodes;
    int    max_total_cost;
    int    max_depth;
    float  min_importance;
    long   timeout_ms;
};

struct Plan {
    int        view_id;
    char       view_name[64];
    int       *root_node_ids;
    int        root_count;
    int        root_capacity;
    PlanStep  *steps;
    int        step_count;
    int        step_capacity;
    PlanGuard  guard;
    int        budget_total;
    int        budget_used;
    int        node_count;
    char     **cache_keys;
    int        cache_key_count;
    int        cache_key_capacity;
    int        compiled;
    int        executed;
};

/* ════════════════════════════════════════════
 * TRACE TYPES (from GraphTrace)
 * ════════════════════════════════════════════ */

typedef enum {
    TRACE_VISIT,
    TRACE_SKIP,
    TRACE_PRUNE,
    TRACE_CACHE_HIT,
    TRACE_CACHE_MISS,
    TRACE_COST,
    TRACE_OUTCOME,
    TRACE_GUARD_HIT
} TraceAction;

struct TraceEntry {
    int          id;
    TraceAction  action;
    int          node_id;
    char         node_name[GRAPH_MAX_NAME];
    char         reason[256];
    float        score_at_decision;
    float        cost_charged;
    int          depth;
    int          view_id;
    char         view_name[64];
    long         timestamp_ms;
    TraceEntry  *next;
};

struct TraceLog {
    TraceEntry *first;
    TraceEntry *last;
    int         count;
    int         view_id;
    char        view_name[64];
    long        start_time_ms;
    long        end_time_ms;
    float       total_cost;
    int         nodes_visited;
    int         nodes_skipped;
    int         nodes_pruned;
    float       outcome_quality;
};

struct LearningSignal {
    int    node_id;
    char   node_name[GRAPH_MAX_NAME];
    int    view_id;
    float  contribution_score;
    float  success_delta;
    float  cost_efficiency;
    float  redundancy_penalty;
};

/* ════════════════════════════════════════════
 * CACHE TYPES (from GraphCache)
 * ════════════════════════════════════════════ */

typedef enum {
    CACHE_STRUCTURAL,
    CACHE_SEMANTIC,
    CACHE_POLICY,
    CACHE_LEARNING
} CacheLayer;

struct CacheEntry {
    int          node_id;
    char         view_signature[128];
    char         policy_signature[128];
    int          depth;
    int          scoring_version;
    CacheLayer   layer;
    void        *result;
    int          result_size;
    float        result_quality;
    float        stability_score;
    int          reuse_count;
    float        context_conflict_risk;
    float        freshness_requirement;
    char         fingerprint[64];
    long         created_ms;
    long         last_accessed_ms;
    CacheEntry  *next;
};

struct ScopeRule {
    char  view_name[64];
    char  allowed_node_types[32][32];
    int   allowed_count;
    char  forbidden_edge_types[32][64];
    int   forbidden_count;
};

struct CacheStats {
    int   total_entries;
    int   structural_entries;
    int   semantic_entries;
    int   policy_entries;
    int   learning_entries;
    int   hits;
    int   misses;
    int   evictions;
    float hit_rate;
};

#define CACHE_HASH_SIZE 1024

struct GraphCache {
    CacheEntry  *table[CACHE_HASH_SIZE];
    int          entry_count;
    CacheStats   stats;
    ScopeRule    scopes[32];
    int          scope_count;
    int          max_entries;
    int          scoring_version;
};

/* ════════════════════════════════════════════
 * LEARNING TYPES (from GraphLearning)
 * ════════════════════════════════════════════ */

#define MAX_WEIGHT_ENTRIES  10000
#define MAX_RECENT_PATHS    100

struct WeightEntry {
    int    node_id;
    char   node_name[GRAPH_MAX_NAME];
    float  weight_delta;
    float  current_weight;
    int    signal_count;
    float  last_contribution;
    float  historical_success;
    int    times_visited;
    int    times_wasted;
    int    active;
};

struct RecentPath {
    int    node_ids[64];
    int    node_count;
    char   view_name[64];
    float  outcome_quality;
};

struct LearningModel {
    WeightEntry   weights[MAX_WEIGHT_ENTRIES];
    int           weight_count;
    RecentPath    recent_paths[MAX_RECENT_PATHS];
    int           recent_path_count;
    int           recent_path_head;
    float         learning_rate;
    float         confidence_threshold;
    float         safety_bound;
    float         repetition_penalty;
    float         exploration_bonus;
    int           total_signals_processed;
    int           total_updates_applied;
    int           total_updates_rejected;
    float         avg_contribution;
};

/* ════════════════════════════════════════════
 * AST/PARSE TYPES (from bcl_engine.h — needed by GraphStore)
 * ════════════════════════════════════════════ */

#define VBAST_MAX_CLASSES    256
#define VBAST_MAX_METHODS   2048
#define VBAST_MAX_EDGES     8192
#define VBAST_MAX_IMPORTS    128
#define VBAST_MAX_NAME       128
#define VBAST_MAX_SIG        512
#define VBAST_MAX_LINE      1024

typedef enum {
    LANG_PYTHON = 0,
    LANG_C = 1,
    LANG_UNKNOWN = 2
} Language;

typedef struct {
    char name[VBAST_MAX_NAME];
    char bases[VBAST_MAX_SIG];
    int  line_start;
    int  line_end;
    int  method_count;
    int  has_run;
    int  has_state_dict;
    int  has_mem_param;
    int  has_ghost;
    int  has_vbstyle;
    int  has_decorator;
    int  db_id;
} ClassInfo;

typedef struct {
    char name[VBAST_MAX_NAME];
    char class_name[VBAST_MAX_NAME];
    char signature[VBAST_MAX_SIG];
    int  line_start;
    int  line_end;
    int  has_tuple3;
    int  has_print;
    int  has_decorator;
    int  has_type_hint;
    int  is_async;
    int  db_id;
} MethodInfo;

typedef struct {
    char source[VBAST_MAX_NAME];
    char target[VBAST_MAX_NAME];
    char edge_type[32];
    char certainty[16];
    int  line_number;
} EdgeInfo;

typedef struct {
    char module[VBAST_MAX_NAME];
    char alias[VBAST_MAX_NAME];
    int  line_number;
} ImportInfo;

typedef struct {
    char file_path[VBAST_MAX_LINE];
    char *source;
    size_t source_len;
    Language language;
    ClassInfo  classes[VBAST_MAX_CLASSES];
    int class_count;
    MethodInfo methods[VBAST_MAX_METHODS];
    int method_count;
    EdgeInfo   edges[VBAST_MAX_EDGES];
    int edge_count;
    ImportInfo imports[VBAST_MAX_IMPORTS];
    int import_count;
} ParseResult;

/* ════════════════════════════════════════════
 * CONFIG TYPES (from GraphConfig)
 * ════════════════════════════════════════════ */

struct ConfigEntry {
    char  section[64];
    char  key[64];
    char  value[256];
};

struct Config {
    ConfigEntry  *entries;
    int           count;
    int           capacity;
};

/* ════════════════════════════════════════════
 * FUNCTION DECLARATIONS — GRAPH CORE
 * (implemented in bcl_graph_core.c)
 * ════════════════════════════════════════════ */

Graph *graph_create(int initial_capacity);
void   graph_free(Graph *g);
int    graph_add_node(Graph *g, Node *n);
int    graph_add_edge(Graph *g, Edge *e);
Node  *graph_find_node(Graph *g, const char *name);
Node  *graph_find_node_by_id(Graph *g, int id);
int    graph_node_count(Graph *g);
int    graph_edge_count(Graph *g);
Node  *node_create(int id, const char *name, const char *type, float importance);
Edge  *edge_create(int id, Node *source, Node *target, const char *rel, float weight);

/* ════════════════════════════════════════════
 * FUNCTION DECLARATIONS — POLICY (GraphPolicy)
 * ════════════════════════════════════════════ */

int    executor_check(Executor *ex);
void   executor_charge(Executor *ex, float cost);
void   executor_start(Executor *ex);
int    executor_is_halted(Executor *ex);
long   executor_elapsed_ms(Executor *ex);
int    policy_should_expand(Policy *p, Node *n, int current_depth, int nodes_this_hop, int total_nodes);
void   policy_set_context(Policy *p, const char *context_name);
float  policy_compute_importance(Node *n, float frequency, float centrality, float recency);
int    policy_get_depth_limit(Policy *p);
void   policy_dump(Policy *p, char *buf, int buf_size);
void   executor_dump(Executor *ex, char *buf, int buf_size);

/* ════════════════════════════════════════════
 * FUNCTION DECLARATIONS — VIEW (GraphView)
 * ════════════════════════════════════════════ */

View      *view_create(const char *name, const char *description);
void       view_free(View *v);
int        view_add_start(View *v, const char *selector);
int        view_add_rule(View *v, const char *from_type, const char *to_type,
                         const char *edge_rel, int max_children, float min_importance);
void       view_set_depth(View *v, int max_depth);
void       view_set_cost(View *v, float base, float depth_mult, float fanout_pen);
void       view_set_output(View *v, OutputShape shape);
void       view_set_min_importance(View *v, float min_imp);
int        view_register(View *v);
View      *view_lookup(const char *name);
ViewRule  *view_find_rules(View *v, const char *node_type, int *count_out);
float      view_compute_cost(View *v, Node *n, int current_depth);
int        view_should_expand(View *v, Node *n, int current_depth, int total_nodes, int total_cost);
void       view_create_predefined(void);
void       view_dump(View *v, char *buf, int buf_size);

/* ════════════════════════════════════════════
 * FUNCTION DECLARATIONS — EXPAND (GraphExpand)
 * ════════════════════════════════════════════ */

int        expand_register(const char *node_type, ExpandFn fn);
ExpandFn   expand_lookup(const char *node_type);
int        graph_expand(Graph *g, Node *node, int depth_left);
int        expand_class(Node *node, Graph *g, int depth_left, Node ***children_out);
int        expand_method(Node *node, Graph *g, int depth_left, Node ***children_out);
int        expand_rule(Node *node, Graph *g, int depth_left, Node ***children_out);
int        expand_token(Node *node, Graph *g, int depth_left, Node ***children_out);
int        expand_chat(Node *node, Graph *g, int depth_left, Node ***children_out);
void       expand_register_all(void);
int        graph_query(Graph *g, const char *query, int max_depth);
void       graph_export_json(Graph *g, char *buf, int buf_size);

/* ════════════════════════════════════════════
 * FUNCTION DECLARATIONS — CONFIG (GraphConfig)
 * ════════════════════════════════════════════ */

Config     *config_create(void);
void        config_free(Config *c);
int         config_load(Config *c, const char *path);
const char *config_get(Config *c, const char *section, const char *key);
int         config_get_int(Config *c, const char *section, const char *key, int default_val);
float       config_get_float(Config *c, const char *section, const char *key, float default_val);
int         config_apply_to_graph(Config *c, Graph *g);

/* Global config (from bcl_engine.h — needed by GraphStore) */
int          config_init_global(const char *path);
const char * config_global_backend(void);
const char * config_global_db_path(void);
const char * config_global_db_host(void);
const char * config_global_db_user(void);
const char * config_global_db_table(void);
int          config_global_db_port(void);
const char * config_global_domain(void);

/* ════════════════════════════════════════════
 * FUNCTION DECLARATIONS — STORE (GraphStore)
 * ════════════════════════════════════════════ */

int    store_load_all(Graph *g);
int    store_search_nodes(Graph *g, const char *query, int max_results);
int    store_load_class_graph(Graph *g);
int    store_load_bcl_edges(Graph *g);
int    store_load_token_edges(Graph *g);
int    store_load_know_edges(Graph *g);

/* ════════════════════════════════════════════
 * FUNCTION DECLARATIONS — COMPILER (GraphCompiler)
 * ════════════════════════════════════════════ */

Plan  *plan_create(View *v);
void   plan_free(Plan *p);
int    plan_add_step(Plan *p, int node_id, const char *node_type, int depth,
                     float cost, float value, int parent_step, ViewRule *rule);
int    plan_add_root(Plan *p, int node_id);
int    plan_add_cache_key(Plan *p, const char *key);
int    normalize_start_nodes(Plan *p, View *v, Graph *g);
int    plan_build_traversal(Plan *p, View *v, Graph *g);
Plan  *compile_view(View *v, Graph *g);
int    plan_check_guard(Plan *p);
void   plan_dump(Plan *p, char *buf, int buf_size);

/* ════════════════════════════════════════════
 * FUNCTION DECLARATIONS — OPTIMIZER (GraphOptimizer)
 * ════════════════════════════════════════════ */

float  score_rule(Node *n, View *v, int depth);
float  score_learned(Node *n);
float  score_structural(Node *n, Graph *g);
float  compute_final_score(Node *n, View *v, Graph *g, int depth,
                           float *rule_out, float *learned_out, float *struct_out);
int    node_fanout(Node *n);
int    node_is_bridge(Node *n, Graph *g);
int    optimize_prune(Plan *p, Graph *g, View *v);
int    optimize_dedup(Plan *p);
int    optimize_reorder(Plan *p, Graph *g, View *v);
int    optimize_adaptive_depth(Plan *p, Graph *g, View *v);
int    optimize_plan(Plan *p, Graph *g, View *v);
int    execute_plan(Plan *p, Graph *g, View *v);
void   optimizer_dump_scores(Plan *p, Graph *g, View *v, char *buf, int buf_size);

/* ════════════════════════════════════════════
 * FUNCTION DECLARATIONS — TRACE (GraphTrace)
 * ════════════════════════════════════════════ */

TraceLog *trace_create(int view_id, const char *view_name);
void      trace_free(TraceLog *t);
void      trace_log_visit(TraceLog *t, Node *n, float score, float cost, int depth);
void      trace_log_skip(TraceLog *t, Node *n, const char *reason, float score, int depth);
void      trace_log_prune(TraceLog *t, Node *n, const char *reason, float score, int depth);
void      trace_log_cache_hit(TraceLog *t, Node *n, int depth);
void      trace_log_cache_miss(TraceLog *t, Node *n, int depth);
void      trace_log_cost(TraceLog *t, float cost, const char *reason);
void      trace_log_guard_hit(TraceLog *t, const char *reason);
void      trace_log_outcome(TraceLog *t, float quality, const char *reason);
int       trace_evaluate(TraceLog *t, LearningSignal *signals_out, int max_signals);
void      trace_dump(TraceLog *t, char *buf, int buf_size);
void      trace_export_json(TraceLog *t, char *buf, int buf_size);
void      trace_summary(TraceLog *t, int *visited, int *skipped, int *pruned,
                        float *cost, float *outcome, long *duration_ms);

/* ════════════════════════════════════════════
 * FUNCTION DECLARATIONS — CACHE (GraphCache)
 * ════════════════════════════════════════════ */

GraphCache *cache_create(int max_entries);
void        cache_free(GraphCache *c);
void        cache_compute_fingerprint(Node *n, View *v, int depth, char *out, int out_size);
void        cache_view_signature(View *v, char *out, int out_size);
float       cache_value(CacheEntry *e);
int         cache_add_scope(GraphCache *c, const char *view_name,
                            const char **allowed_types, int allowed_count,
                            const char **forbidden_edges, int forbidden_count);
int         cache_scope_allows(GraphCache *c, const char *view_name, const char *node_type);
int         cache_scope_forbids_edge(GraphCache *c, const char *view_name, const char *edge_type);
int         cache_store(GraphCache *c, int node_id, const char *view_sig,
                        const char *policy_sig, int depth, CacheLayer layer,
                        void *result, int result_size, float quality,
                        Node *n, View *v);
CacheEntry *cache_lookup(GraphCache *c, int node_id, const char *view_sig,
                         int depth, CacheLayer layer);
int         cache_invalidate_view(GraphCache *c, const char *view_sig);
int         cache_invalidate_all(GraphCache *c);
int         cache_bump_scoring_version(GraphCache *c);
void        cache_update_stats(GraphCache *c);
void        cache_dump_stats(GraphCache *c, char *buf, int buf_size);
void        cache_create_default_scopes(GraphCache *c);

/* ════════════════════════════════════════════
 * FUNCTION DECLARATIONS — LEARNING (GraphLearning)
 * ════════════════════════════════════════════ */

LearningModel *learning_create(void);
void           learning_free(LearningModel *m);
int            learning_process_signal(LearningModel *m, LearningSignal *sig);
int            learning_process_trace(LearningModel *m, LearningSignal *signals, int signal_count);
int            learning_apply_updates(LearningModel *m);
int            learning_record_path(LearningModel *m, int *node_ids, int node_count,
                                    const char *view_name, float outcome);
float          learning_path_similarity(LearningModel *m, int node_id);
float          learning_score(LearningModel *m, int node_id);
float          learning_compute_contribution(float downstream_success, float expansion_cost,
                                             float redundancy_overlap);
void           learning_dump(LearningModel *m, char *buf, int buf_size);
void           learning_export_json(LearningModel *m, char *buf, int buf_size);
void           learning_reset(LearningModel *m);

#endif /* BCL_GRAPH_TYPES_H */
