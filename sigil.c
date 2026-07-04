/*
 * sigil.c — Reasoning Field Traversal Algorithm (RF-TA) Engine
 *
 * A pre-execution reasoning kernel that sits above the database layer
 * and below the execution layer.
 *
 * Pipeline:
 *   User Request
 *       ↓
 *   Reasoning Field Builder  ← RF-TA traversal (hybrid BFS/DFS)
 *       ↓
 *   Field Synthesis          ← compress graph into actionable insight
 *       ↓
 *   Reasoning Compiler       ← field → intent → plan → safety gates
 *       ↓
 *   Reversible Execution     ← ledger + rollback + replay
 *       ↓
 *   Feedback Loop            ← reward → edge weight + policy updates
 *
 * Architecture:
 *   Layer 1: Field Interpretation  (collapse graph → intent)
 *   Layer 2: Plan Synthesis        (intent → typed execution plan IR)
 *   Layer 3: Safety Injection      (constraints + uncertainty encoding)
 *   Layer 4: Execution Compilation (IR → SQL/code/system actions)
 *   Layer 5: Reversibility         (shadow plan + rollback graph)
 *
 * Compile: cc -O2 -o sigil sigil.c -lm -lmysqlclient -I/opt/homebrew/include/mysql -L/opt/homebrew/opt/mysql-client/lib
 *
 * Loads real data from the `laws` MySQL database:
 *   - law, error, pattern, problem, cause, fix, prevention, solution tables → nodes
 *   - link table → edges (link_type maps to EdgeType)
 *   - domain, status, severity, priority authority tables → node attributes
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <mysql/mysql.h>

/* ========================================================================== */
/*  SECTION 1 — Constants                                                     */
/* ========================================================================== */

#define MAX_NODES          8192
#define MAX_EDGES          32768
#define MAX_FRONTIER         512
#define MAX_SHADOW         2048
#define MAX_INTENTS         128
#define MAX_PLAN_OPS         64
#define MAX_LEDGER          128
#define MAX_DEPTH             6
#define MAX_EDGES_PER_NODE   12
#define STABILITY_EPSILON   0.005
#define STABILITY_WINDOW      3
#define LEARNING_ALPHA      0.15
#define NOVELTY_DECAY       0.85
#define SHADOW_THRESHOLD     0.75

typedef enum {
    EDGE_STRUCTURAL    = 0,   /* FK, schema links — truth anchors      */
    EDGE_SEMANTIC      = 1,   /* concept similarity                     */
    EDGE_AUTHORITY     = 2,   /* governing laws / rules                 */
    EDGE_BEHAVIORAL    = 3,   /* runtime patterns                       */
    EDGE_HISTORICAL    = 4,   /* past fixes / creation context          */
    EDGE_CAUSAL        = 5,   /* what causes it / what it causes        */
    EDGE_PREVENTATIVE  = 6,   /* what blocks it                         */
    EDGE_CONTRADICTORY = 7,   /* conflicts                              */
    EDGE_SIMILARITY    = 8,   /* nearest neighbors (noise-prone)        */
    EDGE_MISSING       = 9,   /* expected but absent — exploration driver */
    /* ── Composite edges (BloodHound-style post-processing) ──
     * These are derived from combinations of base edges.
     * Like BloodHound's DCSync = GetChanges + GetChangesAll,
     * these represent relationships that only exist when multiple
     * base conditions are met simultaneously. */
    EDGE_VIOLATION     = 10,  /* LAW + ERROR → law is violated by error */
    EDGE_CAUSAL_CHAIN  = 11,  /* CAUSE + PROBLEM → causal chain detected */
    EDGE_RESOLUTION    = 12,  /* FIX + PREVENTION → problem is resolved */
    EDGE_ATTACK_PATH   = 13,  /* AUTHORITY + CAUSAL → exploitable path  */
    EDGE_TYPE_COUNT    = 14
} EdgeType;

static const char *EDGE_TYPE_NAMES[] = {
    "structural", "semantic", "authority", "behavioral",
    "historical", "causal", "preventative", "contradictory",
    "similarity", "missing",
    "violation", "causal_chain", "resolution", "attack_path"
};

/* Default edge weights — causal + missing + authority are highest.
 * Composite edges get even higher weights — they represent confirmed
 * multi-condition relationships, so they're the most trustworthy. */
static const double DEFAULT_EDGE_WEIGHTS[] = {
    0.80,  /* structural    */
    0.40,  /* semantic      */
    0.80,  /* authority     */
    0.50,  /* behavioral    */
    0.50,  /* historical    */
    0.95,  /* causal        */
    0.75,  /* preventative  */
    0.85,  /* contradictory */
    0.25,  /* similarity    */
    0.95,  /* missing       */
    0.98,  /* violation — composite, high confidence     */
    0.97,  /* causal_chain — composite, high confidence  */
    0.96,  /* resolution — composite, high confidence    */
    0.99   /* attack_path — composite, highest confidence */
};

typedef enum {
    NODE_ERROR       = 0,
    NODE_LAW         = 1,
    NODE_CLASS       = 2,
    NODE_METHOD      = 3,
    NODE_PATTERN     = 4,
    NODE_RULE        = 5,
    NODE_FACT        = 6,
    NODE_INCIDENT    = 7,
    NODE_REPORT      = 8,
    NODE_PROBLEM     = 9,
    NODE_CAUSE       = 10,
    NODE_FIX         = 11,
    NODE_PREVENTION  = 12,
    NODE_SOLUTION    = 13,
    NODE_UNKNOWN     = 99
} NodeType;

typedef enum {
    ACTION_QUERY      = 0,
    ACTION_MIGRATION  = 1,
    ACTION_CODE       = 2,
    ACTION_SYSTEM     = 3,
    ACTION_NONE       = 99
} ActionType;

static const char *ACTION_TYPE_NAMES[] = {
    "QUERY", "MIGRATION", "CODE", "SYSTEM"
};

typedef enum {
    RISK_NONE   = 0,
    RISK_LOW    = 1,
    RISK_MEDIUM = 2,
    RISK_HIGH   = 3
} RiskLevel;

/* ========================================================================== */
/*  SECTION 2 — Core data structures                                          */
/* ========================================================================== */

typedef struct {
    int      id;
    char     name[256];
    char     domain[64];
    NodeType type;
    double   novelty;        /* decays each visit */
    double   authority;      /* importance weight */
    int      visited;
    int      depth;
    int      cluster_id;     /* assigned during synthesis */
    int      high_value;     /* BloodHound "highvalue" — nodes on attack paths */
    int      has_attack_path;/* has an EDGE_ATTACK_PATH composite edge */
    int      has_violation;  /* has an EDGE_VIOLATION composite edge */
} Node;

typedef struct {
    int       from;
    int       to;
    EdgeType  type;
    double    weight;         /* trainable */
    double    info_gain;      /* computed per traversal */
    int       traversed;      /* how many times this edge was used */
    double    contribution;   /* last-run contribution to outcome */
} Edge;

typedef struct {
    Node  nodes[MAX_NODES];
    int   node_count;
    Edge  edges[MAX_EDGES];
    int   edge_count;
    int   anchor_id;
    double stability;
    int   depth_reached;
    int   new_info_rate;      /* new nodes discovered last layer */
    int   edge_diversity;     /* distinct edge types seen last layer */
    int   frontier_overlap;  /* % of frontier that repeats prior */
} FieldGraph;

/* Frontier priority queue entry */
typedef struct {
    int    node_id;
    double priority;
    int    depth;
    int    is_bfs;            /* 1 = breadth discovery, 0 = depth dive */
    EdgeType incoming_edge;   /* which edge type led here */
} FrontierEntry;

typedef struct {
    FrontierEntry entries[MAX_FRONTIER];
    int count;
} Frontier;

/* Shadow graph — lightweight fingerprint for pruning */
typedef struct {
    int  node_id;
    char fingerprint[64];     /* structural signature hash */
    int  cluster_id;
    int  fully_explored;
} ShadowEntry;

typedef struct {
    ShadowEntry entries[MAX_SHADOW];
    int count;
} ShadowGraph;

/* ========================================================================== */
/*  SECTION 2b — Constraint Language (uncertainty reduction system)          */
/* ========================================================================== */
/*
 * Every clue, fact, or observation is expressed as a typed constraint
 * that deterministically reduces the hypothesis space.
 *
 *   H := {h ∈ H | satisfies(C)}
 *
 * Constraint types:
 *   C_TYPE       — node must be of this type
 *   C_DOMAIN     — node must be in this domain
 *   C_PREFIX     — node name must start with prefix
 *   C_SUFFIX     — node name must end with suffix
 *   C_CONTAINS   — node name must contain substring
 *   C_EXCLUDE    — node must NOT match this name
 *   C_EDGE_HAS   — node must have an edge of this type
 *   C_EDGE_LACKS — node must NOT have an edge of this type
 *   C_AUTHORITY  — node authority must be >= threshold
 *   C_NEIGHBOR   — node must be reachable from this node within N hops
 *   C_REGEX      — node name must match simple pattern (* = wildcard)
 *
 * Each constraint carries a weight (confidence in the constraint itself).
 * Applying a constraint:
 *   1. Prunes candidates that violate it
 *   2. Reweights remaining candidates by constraint weight
 *   3. Updates belief distribution
 */

#define MAX_CONSTRAINTS    128
#define MAX_HYPOTHESES     512
#define CONVERGENCE_THRESH  0.85   /* when top candidate > 85% mass, converged */

typedef enum {
    C_TYPE       = 0,
    C_DOMAIN     = 1,
    C_PREFIX     = 2,
    C_SUFFIX     = 3,
    C_CONTAINS   = 4,
    C_EXCLUDE    = 5,
    C_EDGE_HAS   = 6,
    C_EDGE_LACKS = 7,
    C_AUTHORITY  = 8,
    C_NEIGHBOR   = 9,
    C_REGEX      = 10,
    C_TYPE_COUNT = 11
} ConstraintType;

static const char *CONSTRAINT_TYPE_NAMES[] = {
    "type", "domain", "prefix", "suffix", "contains",
    "exclude", "edge_has", "edge_lacks", "authority",
    "neighbor", "regex"
};

/* A single constraint */
typedef struct {
    ConstraintType type;
    char     value[256];      /* the constraint parameter (string) */
    int      int_value;       /* for int params (node type, edge type, hop count) */
    double   double_value;    /* for double params (authority threshold) */
    double   weight;          /* confidence in this constraint (0.0–1.0) */
    int      source_node;     /* for C_NEIGHBOR: the reference node */
    int      active;          /* 1 = applied, 0 = pending */
    int      hard;            /* 1 = eliminate violators, 0 = soft boost only */
    char     description[128];/* human-readable explanation */
} Constraint;

/* A hypothesis — a candidate node with a probability */
typedef struct {
    int    node_id;
    double probability;       /* normalized belief mass */
    double raw_score;         /* unnormalized score */
    int    eliminated;        /* 1 = pruned by a constraint */
    int    constraints_passed; /* how many constraints this node satisfies */
    int    constraints_total;  /* total constraints evaluated against */
} Hypothesis;

/* The constraint engine state */
typedef struct {
    Constraint  constraints[MAX_CONSTRAINTS];
    int         constraint_count;
    Hypothesis  hypotheses[MAX_HYPOTHESES];
    int         hypothesis_count;
    double      entropy;          /* Shannon entropy of belief distribution */
    double      convergence;      /* max probability mass on top candidate */
    int         converged;        /* 1 if convergence threshold reached */
    int         total_pruned;     /* how many candidates eliminated */
} ConstraintEngine;

/* ========================================================================== */
/*  SECTION 3 — Policy + Learning state                                       */
/* ========================================================================== */

typedef struct {
    double edge_weights[EDGE_TYPE_COUNT];
    double bfs_bias;                /* 0.0 = pure DFS, 1.0 = pure BFS */
    double exploration;             /* 0.0 = exploit, 1.0 = explore   */
    double pruning_aggression;
    double missing_sensitivity;
    int    max_depth;
    int    max_edges_per_node;
    int    max_new_nodes_per_layer;
} Policy;

typedef struct {
    double edge_weight_deltas[EDGE_TYPE_COUNT];
    double edge_success_count[EDGE_TYPE_COUNT];
    double edge_total_count[EDGE_TYPE_COUNT];
    double expected_reward;
    double actual_reward;
    double surprise;               /* unexpected results = missing edges */
    int    total_runs;
    /* Discovered edge type signals */
    int    unknown_co_occurrence[EDGE_TYPE_COUNT];
} LearningState;

/* ========================================================================== */
/*  SECTION 4 — Reasoning Compiler structures                                 */
/* ========================================================================== */

typedef struct {
    int    source_node_id;
    char   intent[256];
    double confidence;
    RiskLevel risk;
    EdgeType dominant_edge;        /* which edge type drove this intent */
} Intent;

typedef struct {
    ActionType  action_type;
    char        target[256];
    char        operation[512];
    double      confidence;
    RiskLevel   risk;
    int         requires_dry_run;
    int         requires_transaction;
    char        rollback_op[512];  /* inverse operation */
} PlanOp;

typedef struct {
    PlanOp  ops[MAX_PLAN_OPS];
    int     op_count;
    double  overall_confidence;
    RiskLevel overall_risk;
    int     requires_transaction;
    int     safety_gate_passed;
} ExecutionPlan;

typedef struct {
    Intent  intents[MAX_INTENTS];
    int     intent_count;
    double  field_confidence;      /* aggregate confidence of the field */
    int     missing_link_count;
    int     contradiction_count;
    int     cluster_count;
} IntentGraph;

/* ========================================================================== */
/*  SECTION 5 — Reversible Execution Ledger                                   */
/* ========================================================================== */

typedef struct {
    int       id;
    int       plan_op_index;
    ActionType action_type;
    char      action[512];
    char      inverse_action[512];
    int       executed;
    int       rolled_back;
    double    execution_time_ms;
    char      timestamp[32];
    int       transaction_id;
} LedgerEntry;

typedef struct {
    LedgerEntry entries[MAX_LEDGER];
    int  count;
    int  current_transaction;
    int  transaction_depth;
} ExecutionLedger;

/* ========================================================================== */
/*  SECTION 6 — Engine context (top-level state)                             */
/* ========================================================================== */

typedef struct {
    FieldGraph       field;
    Frontier         frontier;
    ShadowGraph      shadow;
    Policy           policy;
    LearningState    learning;
    IntentGraph      intents;
    ExecutionPlan    plan;
    ExecutionLedger  ledger;
    ConstraintEngine constraints;   /* uncertainty reduction engine */
    int              verbose;
    /* Session state — BloodHound "owned" equivalent.
     * Tracks which nodes have been "reasoned about" across runs.
     * This persists between runs so the engine learns from previous
     * conclusions. */
    int              owned[MAX_NODES];  /* 1 = this node has been concluded */
    int              owned_count;
    double           session_confidence; /* overall confidence in conclusions */
} RFEngine;

/* ========================================================================== */
/*  SECTION 7 — Utility functions                                             */
/* ========================================================================== */

static double clampd(double v, double lo, double hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

static void timestamp_now(char *buf, int size) {
    time_t t = time(NULL);
    struct tm *tm = localtime(&t);
    strftime(buf, size, "%Y-%m-%d %H:%M:%S", tm);
}

static const char *risk_name(RiskLevel r) {
    switch (r) {
        case RISK_NONE:   return "none";
        case RISK_LOW:    return "low";
        case RISK_MEDIUM: return "medium";
        case RISK_HIGH:   return "high";
        default:          return "unknown";
    }
}

static const char *edge_type_name(EdgeType t) {
    if (t < EDGE_TYPE_COUNT) return EDGE_TYPE_NAMES[t];
    return "unknown";
}

static const char *action_name(ActionType a) {
    if (a < 4) return ACTION_TYPE_NAMES[a];
    return "NONE";
}

/* ========================================================================== */
/*  SECTION 8 — Engine initialization                                         */
/* ========================================================================== */

void rf_engine_init(RFEngine *e, int verbose) {
    memset(e, 0, sizeof(RFEngine));
    e->field.node_count = 0;
    e->field.edge_count = 0;
    e->field.anchor_id = -1;
    e->field.stability = 0.0;
    e->frontier.count = 0;
    e->shadow.count = 0;
    e->verbose = verbose;

    /* Initialize policy with defaults */
    for (int i = 0; i < EDGE_TYPE_COUNT; i++)
        e->policy.edge_weights[i] = DEFAULT_EDGE_WEIGHTS[i];
    e->policy.bfs_bias = 0.6;           /* lean toward breadth early */
    e->policy.exploration = 0.5;
    e->policy.pruning_aggression = 0.5;
    e->policy.missing_sensitivity = 0.8;
    e->policy.max_depth = MAX_DEPTH;
    e->policy.max_edges_per_node = MAX_EDGES_PER_NODE;
    e->policy.max_new_nodes_per_layer = 20;

    /* Initialize learning state */
    e->learning.expected_reward = 0.5;
    e->learning.actual_reward = 0.0;
    e->learning.surprise = 0.0;
    e->learning.total_runs = 0;

    /* Initialize ledger */
    e->ledger.count = 0;
    e->ledger.current_transaction = 0;
    e->ledger.transaction_depth = 0;

    /* Initialize constraint engine */
    e->constraints.constraint_count = 0;
    e->constraints.hypothesis_count = 0;
    e->constraints.entropy = 0.0;
    e->constraints.convergence = 0.0;
    e->constraints.converged = 0;
    e->constraints.total_pruned = 0;

    /* Initialize session state */
    memset(e->owned, 0, sizeof(e->owned));
    e->owned_count = 0;
    e->session_confidence = 0.0;
}

/* ========================================================================== */
/*  SECTION 8b — Constraint Language: constraint creation + evaluation       */
/* ========================================================================== */

/*
 * Create constraints of each type. These are the "clues" — each one
 * deterministically reduces the hypothesis space.
 */

void rf_constraint_type(RFEngine *e, NodeType type, double weight,
                        const char *desc) {
    if (e->constraints.constraint_count >= MAX_CONSTRAINTS) return;
    Constraint *c = &e->constraints.constraints[e->constraints.constraint_count++];
    c->type = C_TYPE;
    c->int_value = type;
    c->weight = weight;
    c->active = 0;
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    strncpy(c->description, desc ? desc : "type constraint", 127);
    c->description[127] = '\0';
}

void rf_constraint_domain(RFEngine *e, const char *domain, double weight,
                          const char *desc) {
    if (e->constraints.constraint_count >= MAX_CONSTRAINTS) return;
    Constraint *c = &e->constraints.constraints[e->constraints.constraint_count++];
    c->type = C_DOMAIN;
    strncpy(c->value, domain ? domain : "", 255);
    c->value[255] = '\0';
    c->weight = weight;
    c->active = 0;
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    strncpy(c->description, desc ? desc : "domain constraint", 127);
    c->description[127] = '\0';
}

void rf_constraint_prefix(RFEngine *e, const char *prefix, double weight,
                          const char *desc) {
    if (e->constraints.constraint_count >= MAX_CONSTRAINTS) return;
    Constraint *c = &e->constraints.constraints[e->constraints.constraint_count++];
    c->type = C_PREFIX;
    strncpy(c->value, prefix ? prefix : "", 255);
    c->value[255] = '\0';
    c->weight = weight;
    c->active = 0;
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    strncpy(c->description, desc ? desc : "prefix constraint", 127);
    c->description[127] = '\0';
}

void rf_constraint_suffix(RFEngine *e, const char *suffix, double weight,
                          const char *desc) {
    if (e->constraints.constraint_count >= MAX_CONSTRAINTS) return;
    Constraint *c = &e->constraints.constraints[e->constraints.constraint_count++];
    c->type = C_SUFFIX;
    strncpy(c->value, suffix ? suffix : "", 255);
    c->value[255] = '\0';
    c->weight = weight;
    c->active = 0;
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    strncpy(c->description, desc ? desc : "suffix constraint", 127);
    c->description[127] = '\0';
}

void rf_constraint_contains(RFEngine *e, const char *substr, double weight,
                            const char *desc) {
    if (e->constraints.constraint_count >= MAX_CONSTRAINTS) return;
    Constraint *c = &e->constraints.constraints[e->constraints.constraint_count++];
    c->type = C_CONTAINS;
    strncpy(c->value, substr ? substr : "", 255);
    c->value[255] = '\0';
    c->weight = weight;
    c->active = 0;
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    strncpy(c->description, desc ? desc : "contains constraint", 127);
    c->description[127] = '\0';
}

void rf_constraint_exclude(RFEngine *e, const char *name, double weight,
                           const char *desc) {
    if (e->constraints.constraint_count >= MAX_CONSTRAINTS) return;
    Constraint *c = &e->constraints.constraints[e->constraints.constraint_count++];
    c->type = C_EXCLUDE;
    strncpy(c->value, name ? name : "", 255);
    c->value[255] = '\0';
    c->weight = weight;
    c->active = 0;
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    strncpy(c->description, desc ? desc : "exclude constraint", 127);
    c->description[127] = '\0';
}

void rf_constraint_edge_has(RFEngine *e, EdgeType etype, double weight,
                            const char *desc) {
    if (e->constraints.constraint_count >= MAX_CONSTRAINTS) return;
    Constraint *c = &e->constraints.constraints[e->constraints.constraint_count++];
    c->type = C_EDGE_HAS;
    c->int_value = etype;
    c->weight = weight;
    c->active = 0;
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    strncpy(c->description, desc ? desc : "edge_has constraint", 127);
    c->description[127] = '\0';
}

void rf_constraint_edge_lacks(RFEngine *e, EdgeType etype, double weight,
                              const char *desc) {
    if (e->constraints.constraint_count >= MAX_CONSTRAINTS) return;
    Constraint *c = &e->constraints.constraints[e->constraints.constraint_count++];
    c->type = C_EDGE_LACKS;
    c->int_value = etype;
    c->weight = weight;
    c->active = 0;
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    strncpy(c->description, desc ? desc : "edge_lacks constraint", 127);
    c->description[127] = '\0';
}

void rf_constraint_authority(RFEngine *e, double threshold, double weight,
                             const char *desc) {
    if (e->constraints.constraint_count >= MAX_CONSTRAINTS) return;
    Constraint *c = &e->constraints.constraints[e->constraints.constraint_count++];
    c->type = C_AUTHORITY;
    c->double_value = threshold;
    c->weight = weight;
    c->active = 0;
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    strncpy(c->description, desc ? desc : "authority constraint", 127);
    c->description[127] = '\0';
}

void rf_constraint_neighbor(RFEngine *e, int source_node, int max_hops,
                            double weight, const char *desc) {
    if (e->constraints.constraint_count >= MAX_CONSTRAINTS) return;
    Constraint *c = &e->constraints.constraints[e->constraints.constraint_count++];
    c->type = C_NEIGHBOR;
    c->source_node = source_node;
    c->int_value = max_hops;
    c->weight = weight;
    c->active = 0;
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    strncpy(c->description, desc ? desc : "neighbor constraint", 127);
    c->description[127] = '\0';
}

void rf_constraint_regex(RFEngine *e, const char *pattern, double weight,
                         const char *desc) {
    if (e->constraints.constraint_count >= MAX_CONSTRAINTS) return;
    Constraint *c = &e->constraints.constraints[e->constraints.constraint_count++];
    c->type = C_REGEX;
    strncpy(c->value, pattern ? pattern : "", 255);
    c->value[255] = '\0';
    c->weight = weight;
    c->active = 0;
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    c->hard = 1;  /* default: hard constraint */
    strncpy(c->description, desc ? desc : "regex constraint", 127);
    c->description[127] = '\0';
}

/* ========================================================================== */
/*  SECTION 8c — Constraint evaluation: does a node satisfy a constraint?    */
/* ========================================================================== */

/*
 * Simple wildcard match: * matches any sequence, ? matches single char.
 * Returns 1 if match, 0 if not.
 */
static int wildcard_match(const char *pattern, const char *text) {
    if (!pattern || !text) return 0;
    if (*pattern == '\0') return *text == '\0';

    if (*pattern == '*') {
        /* Skip consecutive * */
        while (*pattern == '*') pattern++;
        if (*pattern == '\0') return 1;  /* trailing * matches everything */
        for (; *text; text++)
            if (wildcard_match(pattern, text)) return 1;
        return wildcard_match(pattern, text);
    }
    if (*text == '\0') return 0;
    if (*pattern == '?' || *pattern == *text)
        return wildcard_match(pattern + 1, text + 1);
    return 0;
}

/*
 * Check if a node has an edge of the given type (outgoing or incoming).
 */
static int node_has_edge_type(RFEngine *e, int node_id, EdgeType etype) {
    for (int i = 0; i < e->field.edge_count; i++) {
        Edge *ed = &e->field.edges[i];
        if (ed->type != etype) continue;
        if (ed->from == node_id || ed->to == node_id) return 1;
    }
    return 0;
}

/*
 * Check if a node is reachable from source within max_hops (BFS).
 */
static int node_reachable_within(RFEngine *e, int source, int target, int max_hops) {
    if (source == target) return 1;
    if (max_hops <= 0) return 0;

    int visited[MAX_NODES] = {0};
    int queue[MAX_NODES];
    int q_head = 0, q_tail = 0;
    int depths[MAX_NODES];

    queue[q_tail] = source;
    depths[q_tail] = 0;
    q_tail++;
    visited[source] = 1;

    while (q_head < q_tail) {
        int curr = queue[q_head];
        int depth = depths[q_head];
        q_head++;

        if (depth >= max_hops) continue;

        for (int i = 0; i < e->field.edge_count; i++) {
            Edge *ed = &e->field.edges[i];
            int neighbor = -1;
            if (ed->from == curr) neighbor = ed->to;
            else if (ed->to == curr) neighbor = ed->from;
            if (neighbor < 0 || visited[neighbor]) continue;
            if (neighbor == target) return 1;
            visited[neighbor] = 1;
            queue[q_tail] = neighbor;
            depths[q_tail] = depth + 1;
            q_tail++;
        }
    }
    return 0;
}

/*
 * Evaluate whether a node satisfies a single constraint.
 * Returns: 1 = satisfies, 0 = violates, -1 = constraint not applicable
 */
static int evaluate_constraint(RFEngine *e, int node_id, Constraint *c) {
    Node *n = &e->field.nodes[node_id];
    if (n->type == NODE_UNKNOWN) return -1;  /* skip padding nodes */

    switch (c->type) {
        case C_TYPE:
            return (n->type == c->int_value) ? 1 : 0;

        case C_DOMAIN:
            return (strcmp(n->domain, c->value) == 0) ? 1 : 0;

        case C_PREFIX: {
            int len = strlen(c->value);
            if (len == 0) return -1;
            return (strncmp(n->name, c->value, len) == 0) ? 1 : 0;
        }

        case C_SUFFIX: {
            int nlen = strlen(n->name);
            int clen = strlen(c->value);
            if (clen == 0 || clen > nlen) return 0;
            return (strcmp(n->name + nlen - clen, c->value) == 0) ? 1 : 0;
        }

        case C_CONTAINS:
            return (strstr(n->name, c->value) != NULL) ? 1 : 0;

        case C_EXCLUDE:
            return (strcmp(n->name, c->value) == 0) ? 0 : 1;

        case C_EDGE_HAS:
            return node_has_edge_type(e, node_id, c->int_value) ? 1 : 0;

        case C_EDGE_LACKS:
            return node_has_edge_type(e, node_id, c->int_value) ? 0 : 1;

        case C_AUTHORITY:
            return (n->authority >= c->double_value) ? 1 : 0;

        case C_NEIGHBOR:
            return node_reachable_within(e, c->source_node, node_id, c->int_value) ? 1 : 0;

        case C_REGEX:
            return wildcard_match(c->value, n->name) ? 1 : 0;

        default:
            return -1;
    }
}

/* ========================================================================== */
/*  SECTION 8d — Constraint application engine (prune + reweight + converge)  */
/* ========================================================================== */

/*
 * Initialize the hypothesis space from all real (non-padding) nodes.
 * Each node starts with equal probability (uniform prior).
 */
void rf_constraints_init_hypotheses(RFEngine *e) {
    ConstraintEngine *ce = &e->constraints;
    ce->hypothesis_count = 0;
    ce->total_pruned = 0;

    int count = 0;
    for (int i = 0; i < e->field.node_count && count < MAX_HYPOTHESES; i++) {
        if (e->field.nodes[i].type == NODE_UNKNOWN) continue;
        ce->hypotheses[count].node_id = i;
        ce->hypotheses[count].probability = 1.0;
        ce->hypotheses[count].raw_score = 1.0;
        ce->hypotheses[count].eliminated = 0;
        ce->hypotheses[count].constraints_passed = 0;
        ce->hypotheses[count].constraints_total = 0;
        count++;
    }
    ce->hypothesis_count = count;

    /* Normalize to uniform distribution */
    if (count > 0) {
        double uniform = 1.0 / count;
        for (int i = 0; i < count; i++)
            ce->hypotheses[i].probability = uniform;
    }

    /* Compute initial entropy */
    ce->entropy = 0.0;
    for (int i = 0; i < count; i++)
        if (ce->hypotheses[i].probability > 0)
            ce->entropy -= ce->hypotheses[i].probability
                          * log2(ce->hypotheses[i].probability);
    ce->convergence = (count > 0) ? ce->hypotheses[0].probability : 0.0;
    ce->converged = 0;

    if (e->verbose)
        printf("  [constraints] Initialized %d hypotheses, entropy=%.3f bits\n",
               count, ce->entropy);
}

/*
 * Apply a single constraint to the hypothesis space.
 *
 * 1. Evaluate each hypothesis against the constraint
 * 2. Eliminate (prune) hypotheses that violate it
 * 3. Reweight surviving hypotheses by constraint weight
 * 4. Renormalize the probability distribution
 * 5. Update entropy and convergence metrics
 */
void rf_constraints_apply(RFEngine *e, int constraint_idx) {
    ConstraintEngine *ce = &e->constraints;
    if (constraint_idx < 0 || constraint_idx >= ce->constraint_count) return;

    Constraint *c = &ce->constraints[constraint_idx];
    c->active = 1;

    int passed = 0, failed = 0, skipped = 0;

    for (int i = 0; i < ce->hypothesis_count; i++) {
        Hypothesis *h = &ce->hypotheses[i];
        if (h->eliminated) continue;

        h->constraints_total++;
        int result = evaluate_constraint(e, h->node_id, c);

        if (result < 0) {
            skipped++;
            continue;
        }

        if (result == 1) {
            /* Hypothesis satisfies constraint — boost its score */
            h->raw_score *= (1.0 + c->weight);
            h->constraints_passed++;
            passed++;
        } else {
            /* Hypothesis violates constraint */
            if (c->hard) {
                /* Hard constraint: eliminate violator */
                h->eliminated = 1;
                h->probability = 0.0;
                failed++;
                ce->total_pruned++;
            } else {
                /* Soft constraint: penalize but don't eliminate */
                h->raw_score *= (1.0 - c->weight * 0.5);
            }
        }
    }

    /* Renormalize probabilities based on raw scores */
    double total_score = 0.0;
    for (int i = 0; i < ce->hypothesis_count; i++) {
        if (ce->hypotheses[i].eliminated) continue;
        total_score += ce->hypotheses[i].raw_score;
    }
    if (total_score > 0) {
        for (int i = 0; i < ce->hypothesis_count; i++) {
            if (ce->hypotheses[i].eliminated) continue;
            ce->hypotheses[i].probability = ce->hypotheses[i].raw_score / total_score;
        }
    }

    /* Compute entropy */
    ce->entropy = 0.0;
    for (int i = 0; i < ce->hypothesis_count; i++) {
        if (ce->hypotheses[i].eliminated || ce->hypotheses[i].probability <= 0)
            continue;
        ce->entropy -= ce->hypotheses[i].probability
                      * log2(ce->hypotheses[i].probability);
    }

    /* Find max probability (convergence metric) */
    double max_prob = 0.0;
    int top_idx = -1;
    for (int i = 0; i < ce->hypothesis_count; i++) {
        if (ce->hypotheses[i].eliminated) continue;
        if (ce->hypotheses[i].probability > max_prob) {
            max_prob = ce->hypotheses[i].probability;
            top_idx = i;
        }
    }
    ce->convergence = max_prob;
    ce->converged = (max_prob >= CONVERGENCE_THRESH) ? 1 : 0;

    if (e->verbose) {
        printf("  [constraints] Applied %s%s: '%s'\n",
               c->hard ? "HARD " : "soft ",
               CONSTRAINT_TYPE_NAMES[c->type], c->description);
        printf("    passed=%d  failed=%d  skipped=%d  pruned_total=%d\n",
               passed, failed, skipped, ce->total_pruned);
        printf("    entropy=%.3f bits  convergence=%.3f  %s\n",
               ce->entropy, ce->convergence,
               ce->converged ? "→ CONVERGED" : "");
        if (top_idx >= 0) {
            printf("    top candidate: '%s' (p=%.3f)\n",
                   e->field.nodes[ce->hypotheses[top_idx].node_id].name,
                   max_prob);
        }
    }
}

/*
 * Apply all pending constraints in order.
 */
void rf_constraints_apply_all(RFEngine *e) {
    for (int i = 0; i < e->constraints.constraint_count; i++) {
        if (!e->constraints.constraints[i].active)
            rf_constraints_apply(e, i);
        if (e->constraints.converged) break;
    }
}

/*
 * Get the top N candidates by probability.
 * Returns the number of candidates found.
 */
int rf_constraints_top_candidates(RFEngine *e, int *node_ids, double *probs,
                                  int n) {
    ConstraintEngine *ce = &e->constraints;
    int found = 0;

    /* Simple selection: copy non-eliminated, sort by probability */
    int indices[MAX_HYPOTHESES];
    int count = 0;
    for (int i = 0; i < ce->hypothesis_count; i++) {
        if (ce->hypotheses[i].eliminated) continue;
        indices[count++] = i;
    }

    /* Sort by probability descending (insertion sort) */
    for (int i = 1; i < count; i++) {
        int key = indices[i];
        int j = i - 1;
        while (j >= 0 && ce->hypotheses[indices[j]].probability
                          < ce->hypotheses[key].probability) {
            indices[j + 1] = indices[j];
            j--;
        }
        indices[j + 1] = key;
    }

    for (int i = 0; i < n && i < count; i++) {
        node_ids[i] = ce->hypotheses[indices[i]].node_id;
        probs[i] = ce->hypotheses[indices[i]].probability;
        found++;
    }
    return found;
}

/*
 * Print the current state of the constraint engine.
 */
void rf_constraints_print_state(RFEngine *e) {
    ConstraintEngine *ce = &e->constraints;
    printf("\n=== Constraint Engine State ===\n");
    printf("  Constraints:    %d applied\n", ce->constraint_count);
    printf("  Hypotheses:     %d total, %d pruned, %d remaining\n",
           ce->hypothesis_count, ce->total_pruned,
           ce->hypothesis_count - ce->total_pruned);
    printf("  Entropy:        %.3f bits\n", ce->entropy);
    printf("  Convergence:    %.3f %s\n", ce->convergence,
           ce->converged ? "→ CONVERGED" : "");

    printf("  Constraints applied:\n");
    for (int i = 0; i < ce->constraint_count; i++) {
        printf("    [%d] %s: %s (w=%.2f)\n", i,
               CONSTRAINT_TYPE_NAMES[ce->constraints[i].type],
               ce->constraints[i].description,
               ce->constraints[i].weight);
    }

    printf("  Top 5 candidates:\n");
    int ids[5];
    double probs[5];
    int n = rf_constraints_top_candidates(e, ids, probs, 5);
    for (int i = 0; i < n; i++)
        printf("    [%d] p=%.3f  %s\n", i, probs[i],
               e->field.nodes[ids[i]].name);
    printf("\n");
}

/* ========================================================================== */
/*  SECTION 9 — Graph construction API                                       */
/* ========================================================================== */

int rf_add_node(RFEngine *e, const char *name, const char *domain,
                NodeType type, double authority) {
    if (e->field.node_count >= MAX_NODES) return -1;
    int id = e->field.node_count;
    Node *n = &e->field.nodes[id];
    n->id = id;
    strncpy(n->name, name, sizeof(n->name) - 1);
    strncpy(n->domain, domain, sizeof(n->domain) - 1);
    n->type = type;
    n->authority = authority;
    n->novelty = 1.0;          /* fresh = high novelty */
    n->visited = 0;
    n->depth = 0;
    n->cluster_id = -1;
    n->high_value = 0;
    n->has_attack_path = 0;
    n->has_violation = 0;
    e->field.node_count++;
    return id;
}

/* ========================================================================== */
/*  SECTION 9b — Edge schema validation (BloodHound-style)                    */
/* ========================================================================== */
/*
 * BloodHound defines strict edge schemas: each edge type can only connect
 * specific node types. MemberOf can only go User→Group. AdminTo can only
 * go User→Computer. This prevents invalid edges from polluting the graph.
 *
 * RF-TA edge schema:
 *
 *   EDGE_STRUCTURAL    — any → any (schema links, same-domain)
 *   EDGE_SEMANTIC      — any → any (concept similarity)
 *   EDGE_AUTHORITY     — LAW → any (laws govern everything)
 *   EDGE_BEHAVIORAL    — PATTERN → any (patterns describe behavior)
 *   EDGE_HISTORICAL    — ERROR/INCIDENT → any (past events)
 *   EDGE_CAUSAL        — CAUSE → PROBLEM/ERROR (causes produce problems)
 *   EDGE_PREVENTATIVE  — FIX/PREVENTION → ERROR/PROBLEM (fixes prevent problems)
 *   EDGE_CONTRADICTORY — any → any (conflicts)
 *   EDGE_SIMILARITY    — same type → same type (nearest neighbors)
 *   EDGE_MISSING       — synthetic (not a real edge, used for detection)
 *
 * Returns 1 if the edge is valid per schema, 0 if invalid.
 */
static int edge_schema_valid(NodeType from_type, NodeType to_type, EdgeType etype) {
    /* Skip validation for padding nodes */
    if (from_type == NODE_UNKNOWN || to_type == NODE_UNKNOWN) return 1;

    switch (etype) {
        case EDGE_STRUCTURAL:
        case EDGE_SEMANTIC:
        case EDGE_CONTRADICTORY:
        case EDGE_SIMILARITY:
            /* Any → Any */
            return 1;

        case EDGE_AUTHORITY:
            /* LAW → any (laws govern everything below them) */
            return (from_type == NODE_LAW) ? 1 : 0;

        case EDGE_BEHAVIORAL:
            /* PATTERN → any (patterns describe expected behavior) */
            return (from_type == NODE_PATTERN) ? 1 : 0;

        case EDGE_HISTORICAL:
            /* ERROR or INCIDENT → any (past events inform future) */
            return (from_type == NODE_ERROR || from_type == NODE_INCIDENT) ? 1 : 0;

        case EDGE_CAUSAL:
            /* CAUSE → PROBLEM/ERROR, or PROBLEM → ERROR (problems cause errors)
             * Also allow LAW → ERROR (laws cause/violate errors) */
            return (from_type == NODE_LAW || from_type == NODE_PATTERN
                    || from_type == NODE_CAUSE || from_type == NODE_PROBLEM
                    || to_type == NODE_ERROR || to_type == NODE_INCIDENT
                    || to_type == NODE_PROBLEM) ? 1 : 0;

        case EDGE_PREVENTATIVE:
            /* FIX/PREVENTION/SOLUTION → ERROR/PROBLEM (fixes prevent problems)
             * Also allow LAW → ERROR (laws prevent errors) */
            return (from_type == NODE_LAW || from_type == NODE_FIX
                    || from_type == NODE_PREVENTION || from_type == NODE_SOLUTION
                    || to_type == NODE_ERROR || to_type == NODE_PROBLEM
                    || to_type == NODE_INCIDENT) ? 1 : 0;

        case EDGE_MISSING:
            /* Synthetic — always valid */
            return 1;

        /* ── Composite edge schemas ──
         * These have stricter schemas because they represent
         * confirmed multi-condition relationships. */
        case EDGE_VIOLATION:
            /* LAW → ERROR (law is violated by this error) */
            return (from_type == NODE_LAW
                    && (to_type == NODE_ERROR || to_type == NODE_INCIDENT
                        || to_type == NODE_PROBLEM)) ? 1 : 0;

        case EDGE_CAUSAL_CHAIN:
            /* CAUSE → PROBLEM/ERROR (causal chain: cause leads to problem)
             * Or PROBLEM → ERROR (problem causes error) */
            return ((from_type == NODE_CAUSE || from_type == NODE_PROBLEM)
                    && (to_type == NODE_PROBLEM || to_type == NODE_ERROR
                        || to_type == NODE_INCIDENT)) ? 1 : 0;

        case EDGE_RESOLUTION:
            /* FIX/PREVENTION/SOLUTION → PROBLEM/ERROR (problem is resolved) */
            return ((from_type == NODE_FIX || from_type == NODE_PREVENTION
                     || from_type == NODE_SOLUTION)
                    && (to_type == NODE_PROBLEM || to_type == NODE_ERROR
                        || to_type == NODE_INCIDENT)) ? 1 : 0;

        case EDGE_ATTACK_PATH:
            /* LAW → ERROR/PROBLEM (authority + causal = exploitable path)
             * This is the highest-confidence composite — it means a law
             * is connected to a concrete error through a causal chain. */
            return (from_type == NODE_LAW
                    && (to_type == NODE_ERROR || to_type == NODE_INCIDENT
                        || to_type == NODE_PROBLEM)) ? 1 : 0;

        default:
            return 1;  /* permissive for unknown edge types */
    }
}

/*
 * Check if an edge already exists between two nodes with the same type.
 * BloodHound avoids duplicate edges — we should too.
 */
static int edge_exists(RFEngine *e, int from, int to, EdgeType type) {
    for (int i = 0; i < e->field.edge_count; i++) {
        if (e->field.edges[i].from == from
            && e->field.edges[i].to == to
            && e->field.edges[i].type == type)
            return 1;
    }
    return 0;
}

int rf_add_edge(RFEngine *e, int from, int to, EdgeType type) {
    if (e->field.edge_count >= MAX_EDGES) return -1;
    if (from < 0 || from >= e->field.node_count) return -1;
    if (to < 0 || to >= e->field.node_count) return -1;

    /* BloodHound principle: validate against edge schema */
    NodeType from_t = e->field.nodes[from].type;
    NodeType to_t = e->field.nodes[to].type;
    if (!edge_schema_valid(from_t, to_t, type)) return -2;  /* schema violation */

    /* BloodHound principle: no duplicate edges */
    if (edge_exists(e, from, to, type)) return -3;  /* already exists */

    int id = e->field.edge_count;
    Edge *ed = &e->field.edges[id];
    ed->from = from;
    ed->to = to;
    ed->type = type;
    ed->weight = e->policy.edge_weights[type];
    ed->info_gain = 0.0;
    ed->traversed = 0;
    ed->contribution = 0.0;
    e->field.edge_count++;
    return id;
}

void rf_set_anchor(RFEngine *e, int node_id) {
    e->field.anchor_id = node_id;
    e->field.nodes[node_id].visited = 1;
    e->field.nodes[node_id].novelty = 0.0;  /* anchor is known */
    e->field.nodes[node_id].depth = 0;
}

/* Session state — BloodHound "owned" equivalent.
 * Mark a node as "reasoned about" — this persists across runs.
 * Owned nodes get a novelty penalty (we've already concluded about them)
 * but an authority boost (they're confirmed). */
void rf_own_node(RFEngine *e, int node_id) {
    if (node_id < 0 || node_id >= e->field.node_count) return;
    if (!e->owned[node_id]) {
        e->owned[node_id] = 1;
        e->owned_count++;
        /* Owned nodes are confirmed — boost their authority */
        e->field.nodes[node_id].authority = clampd(
            e->field.nodes[node_id].authority * 1.3, 0.0, 1.0);
    }
}

/* Check if a node is owned (already concluded) */
int rf_is_owned(RFEngine *e, int node_id) {
    if (node_id < 0 || node_id >= e->field.node_count) return 0;
    return e->owned[node_id];
}

/* Print session state summary */
void rf_print_session_state(RFEngine *e) {
    printf("\n=== Session State (BloodHound 'owned') ===\n");
    printf("  Owned nodes: %d / %d\n", e->owned_count, e->field.node_count);
    printf("  Session confidence: %.3f\n\n", e->session_confidence);

    if (e->owned_count > 0 && e->owned_count <= 20) {
        printf("  Owned nodes:\n");
        for (int i = 0; i < e->field.node_count; i++) {
            if (e->owned[i])
                printf("    [%d] %s (authority=%.2f)\n",
                       i, e->field.nodes[i].name,
                       e->field.nodes[i].authority);
        }
        printf("\n");
    }
}

/* ========================================================================== */
/*  SECTION 9c — Composite edge generation (BloodHound post-processing)      */
/* ========================================================================== */
/*
 * BloodHound's key innovation: composite edges derived from combinations
 * of base edges during post-processing.
 *
 *   DCSync = GetChanges + GetChangesAll
 *
 * Two non-traversable edges combine to create one traversable edge.
 * The composite only exists when BOTH conditions are met.
 *
 * RF-TA composite edges:
 *
 *   EDGE_VIOLATION = EDGE_AUTHORITY(LAW→X) + X is ERROR/PROBLEM
 *     → "Law X is violated by this error"
 *     → Only when a law has an authority edge to an error-type node
 *
 *   EDGE_CAUSAL_CHAIN = EDGE_CAUSAL(CAUSE→PROBLEM) + EDGE_CAUSAL(PROBLEM→ERROR)
 *     → "Cause leads to problem leads to error"
 *     → Only when a 2-hop causal path exists
 *
 *   EDGE_RESOLUTION = EDGE_PREVENTATIVE(FIX→PROBLEM) + problem has EDGE_CAUSAL
 *     → "Fix resolves this problem"
 *     → Only when a fix targets a problem that has causal connections
 *
 *   EDGE_ATTACK_PATH = EDGE_AUTHORITY(LAW→X) + EDGE_CAUSAL(X→ERROR)
 *     → "Law → X → Error is an exploitable path"
 *     → Only when authority + causal chain forms a 2-hop path
 *
 * These composite edges are TRAVERSABLE — they can be followed in pathfinding.
 * They get the highest edge weights because they represent confirmed
 * multi-condition relationships.
 */

/* Helper: does node A have an outgoing edge of type T to node B? */
static int has_edge(RFEngine *e, int from, int to, EdgeType type) {
    for (int i = 0; i < e->field.edge_count; i++) {
        if (e->field.edges[i].from == from
            && e->field.edges[i].to == to
            && e->field.edges[i].type == type)
            return 1;
    }
    return 0;
}

/* Helper: does node A have ANY outgoing edge of type T? */
static int has_outgoing_edge_type(RFEngine *e, int from, EdgeType type) {
    for (int i = 0; i < e->field.edge_count; i++) {
        if (e->field.edges[i].from == from
            && e->field.edges[i].type == type)
            return 1;
    }
    return 0;
}

/* Helper: does node A have an outgoing edge of type T to ANY node of type NT? */
static int has_edge_to_node_type(RFEngine *e, int from, EdgeType etype, NodeType ntype) {
    for (int i = 0; i < e->field.edge_count; i++) {
        if (e->field.edges[i].from != from) continue;
        if (e->field.edges[i].type != etype) continue;
        int target = e->field.edges[i].to;
        if (e->field.nodes[target].type == ntype) return 1;
    }
    return 0;
}

/*
 * Generate composite edges from base edges.
 * Called after loading from DB, before traversal.
 *
 * Returns the number of composite edges generated.
 */
int rf_generate_composite_edges(RFEngine *e) {
    int generated = 0;
    int violations = 0, chains = 0, resolutions = 0, attack_paths = 0;

    if (e->verbose)
        printf("  [composite] Scanning %d base edges for composite patterns...\n",
               e->field.edge_count);

    /* ── 1. EDGE_VIOLATION: LAW → ERROR/PROBLEM via AUTHORITY edge ──
     * If a LAW has an EDGE_AUTHORITY edge to an ERROR or PROBLEM node,
     * that means the law is being violated by that error. */
    for (int i = 0; i < e->field.edge_count && e->field.edge_count < MAX_EDGES - 1; i++) {
        Edge *ed = &e->field.edges[i];
        if (ed->type != EDGE_AUTHORITY) continue;

        Node *src = &e->field.nodes[ed->from];
        Node *dst = &e->field.nodes[ed->to];
        if (src->type != NODE_LAW) continue;
        if (dst->type != NODE_ERROR && dst->type != NODE_PROBLEM
            && dst->type != NODE_INCIDENT) continue;

        /* Composite: LAW violates ERROR */
        int r = rf_add_edge(e, ed->from, ed->to, EDGE_VIOLATION);
        if (r >= 0) {
            generated++;
            violations++;
            if (e->verbose)
                printf("  [composite] VIOLATION: Law '%s' → Error '%s'\n",
                       src->name, dst->name);
        }
    }

    /* ── 2. EDGE_CAUSAL_CHAIN: CAUSE → PROBLEM → ERROR (2-hop) ──
     * If CAUSE has EDGE_CAUSAL to PROBLEM, and PROBLEM has EDGE_CAUSAL to ERROR,
     * create a composite CAUSAL_CHAIN edge from CAUSE to ERROR.
     * This is the BloodHound "transitive path" principle. */
    for (int i = 0; i < e->field.edge_count && e->field.edge_count < MAX_EDGES - 1; i++) {
        Edge *e1 = &e->field.edges[i];
        if (e1->type != EDGE_CAUSAL) continue;

        Node *mid_node = &e->field.nodes[e1->to];
        if (mid_node->type != NODE_PROBLEM && mid_node->type != NODE_INCIDENT) continue;

        /* Look for second hop: mid → error */
        for (int j = 0; j < e->field.edge_count; j++) {
            if (j == i) continue;
            Edge *e2 = &e->field.edges[j];
            if (e2->type != EDGE_CAUSAL) continue;
            if (e2->from != e1->to) continue;

            Node *end_node = &e->field.nodes[e2->to];
            if (end_node->type != NODE_ERROR && end_node->type != NODE_INCIDENT) continue;

            /* Composite: CAUSE → ERROR (through PROBLEM) */
            int r = rf_add_edge(e, e1->from, e2->to, EDGE_CAUSAL_CHAIN);
            if (r >= 0) {
                generated++;
                chains++;
                if (e->verbose)
                    printf("  [composite] CAUSAL_CHAIN: '%s' → '%s' → '%s'\n",
                           e->field.nodes[e1->from].name,
                           mid_node->name,
                           end_node->name);
            }
            break;  /* only one composite per first hop */
        }
    }

    /* ── 3. EDGE_RESOLUTION: FIX → PROBLEM that has causal edges ──
     * If FIX has EDGE_PREVENTATIVE to PROBLEM, and that PROBLEM has
     * outgoing EDGE_CAUSAL edges, then the fix resolves a real problem.
     * Create composite RESOLUTION edge from FIX to the ERROR that the
     * problem causes. */
    for (int i = 0; i < e->field.edge_count && e->field.edge_count < MAX_EDGES - 1; i++) {
        Edge *ed = &e->field.edges[i];
        if (ed->type != EDGE_PREVENTATIVE) continue;

        Node *fix_node = &e->field.nodes[ed->from];
        if (fix_node->type != NODE_FIX && fix_node->type != NODE_PREVENTION
            && fix_node->type != NODE_SOLUTION) continue;

        Node *target = &e->field.nodes[ed->to];
        if (target->type != NODE_PROBLEM && target->type != NODE_ERROR) continue;

        /* Does the target problem have outgoing causal edges to errors? */
        for (int j = 0; j < e->field.edge_count; j++) {
            Edge *e2 = &e->field.edges[j];
            if (e2->type != EDGE_CAUSAL) continue;
            if (e2->from != ed->to) continue;

            Node *end = &e->field.nodes[e2->to];
            if (end->type != NODE_ERROR && end->type != NODE_INCIDENT) continue;

            /* Composite: FIX → ERROR (resolves the chain) */
            int r = rf_add_edge(e, ed->from, e2->to, EDGE_RESOLUTION);
            if (r >= 0) {
                generated++;
                resolutions++;
                if (e->verbose)
                    printf("  [composite] RESOLUTION: '%s' resolves '%s' → '%s'\n",
                           fix_node->name, target->name, end->name);
            }
            break;
        }
    }

    /* ── 4. EDGE_ATTACK_PATH: LAW → X + X → ERROR = exploitable path ──
     * If LAW has EDGE_AUTHORITY to X, and X has EDGE_CAUSAL to ERROR,
     * then LAW → X → ERROR is an attack path.
     * This is the highest-confidence composite — it connects authority
     * directly to a concrete failure. */
    for (int i = 0; i < e->field.edge_count && e->field.edge_count < MAX_EDGES - 1; i++) {
        Edge *e1 = &e->field.edges[i];
        if (e1->type != EDGE_AUTHORITY) continue;
        if (e->field.nodes[e1->from].type != NODE_LAW) continue;

        /* Look for second hop: e1->to → error via causal */
        for (int j = 0; j < e->field.edge_count; j++) {
            if (j == i) continue;
            Edge *e2 = &e->field.edges[j];
            if (e2->type != EDGE_CAUSAL && e2->type != EDGE_HISTORICAL) continue;
            if (e2->from != e1->to) continue;

            Node *end = &e->field.nodes[e2->to];
            if (end->type != NODE_ERROR && end->type != NODE_INCIDENT
                && end->type != NODE_PROBLEM) continue;

            /* Composite: LAW → ERROR (attack path through X) */
            int r = rf_add_edge(e, e1->from, e2->to, EDGE_ATTACK_PATH);
            if (r >= 0) {
                generated++;
                attack_paths++;
                if (e->verbose)
                    printf("  [composite] ATTACK_PATH: '%s' → '%s' → '%s'\n",
                           e->field.nodes[e1->from].name,
                           e->field.nodes[e1->to].name,
                           end->name);
            }
            break;
        }
    }

    /* Also detect structural authority paths:
     * LAW → ERROR via structural edge + ERROR has causal = attack path */
    for (int i = 0; i < e->field.edge_count && e->field.edge_count < MAX_EDGES - 1; i++) {
        Edge *e1 = &e->field.edges[i];
        if (e1->type != EDGE_STRUCTURAL) continue;
        if (e->field.nodes[e1->from].type != NODE_LAW) continue;
        if (e->field.nodes[e1->to].type != NODE_ERROR
            && e->field.nodes[e1->to].type != NODE_PROBLEM) continue;

        /* Check if there's already an attack_path for this pair */
        if (has_edge(e, e1->from, e1->to, EDGE_ATTACK_PATH)) continue;

        /* LAW → ERROR directly via structural = potential violation */
        int r = rf_add_edge(e, e1->from, e1->to, EDGE_VIOLATION);
        if (r >= 0) {
            generated++;
            violations++;
            if (e->verbose)
                printf("  [composite] VIOLATION (structural): Law '%s' → '%s'\n",
                       e->field.nodes[e1->from].name,
                       e->field.nodes[e1->to].name);
        }
    }

    /* ── 5. Derive edges from co-occurrence under the same LAW ──
     * BloodHound principle: the link table only stores LAW → target.
     * But if LAW 42 → CAUSE 1 and LAW 42 → PROBLEM 1, then
     * CAUSE 1 → PROBLEM 1 is a derived relationship.
     *
     * This is the key post-processing step that makes composite edges
     * possible. Without it, there are no CAUSE→PROBLEM or FIX→ERROR
     * edges to combine.
     *
     * Rules:
     *   LAW → CAUSE + LAW → PROBLEM  ⇒  CAUSE → PROBLEM (causal)
     *   LAW → CAUSE + LAW → ERROR    ⇒  CAUSE → ERROR  (causal)
     *   LAW → PROBLEM + LAW → ERROR  ⇒  PROBLEM → ERROR (causal)
     *   LAW → FIX + LAW → PROBLEM    ⇒  FIX → PROBLEM  (preventative)
     *   LAW → FIX + LAW → ERROR      ⇒  FIX → ERROR    (preventative)
     *   LAW → PREVENTION + LAW → ERROR ⇒ PREVENTION → ERROR (preventative)
     *   LAW → SOLUTION + LAW → PROBLEM ⇒ SOLUTION → PROBLEM (preventative)
     *
     * With entity_link, all targets might be LAW nodes. In that case,
     * we use the edge type to determine the semantic relationship:
     *   EDGE_CAUSAL edge = "cause" role
     *   EDGE_PREVENTATIVE edge = "fix" role
     *   EDGE_HISTORICAL edge = "evidence" role
     *   EDGE_AUTHORITY edge = "law" role
     */
    {
        int derived = 0;
        /* Group edges by source law */
        for (int law_n = 0; law_n < e->field.node_count; law_n++) {
            if (e->field.nodes[law_n].type != NODE_LAW) continue;

            /* Collect all targets of this law */
            int targets[64];
            EdgeType t_types[64];
            NodeType t_node_types[64];
            int tcount = 0;

            for (int i = 0; i < e->field.edge_count; i++) {
                if (e->field.edges[i].from != law_n) continue;
                if (tcount >= 64) break;
                targets[tcount] = e->field.edges[i].to;
                t_types[tcount] = e->field.edges[i].type;
                t_node_types[tcount] = e->field.nodes[targets[tcount]].type;
                tcount++;
            }

            if (tcount < 2) continue;  /* need at least 2 targets */

            /* For each pair of targets, derive an edge if the types match */
            for (int a = 0; a < tcount && e->field.edge_count < MAX_EDGES - 1; a++) {
                for (int b = 0; b < tcount && e->field.edge_count < MAX_EDGES - 1; b++) {
                    if (a == b) continue;
                    int from = targets[a], to = targets[b];
                    if (from == to) continue;  /* skip self-loops */
                    NodeType ft = t_node_types[a], tt = t_node_types[b];
                    EdgeType et_a = t_types[a], et_b = t_types[b];  /* edge types from law to each target */
                    EdgeType derive_type = EDGE_TYPE_COUNT;  /* invalid */

                    /* CAUSE → PROBLEM/ERROR = causal */
                    if (ft == NODE_CAUSE && (tt == NODE_PROBLEM || tt == NODE_ERROR
                                              || tt == NODE_INCIDENT))
                        derive_type = EDGE_CAUSAL;
                    /* PROBLEM → ERROR = causal */
                    else if (ft == NODE_PROBLEM && (tt == NODE_ERROR || tt == NODE_INCIDENT))
                        derive_type = EDGE_CAUSAL;
                    /* FIX → PROBLEM/ERROR = preventative */
                    else if (ft == NODE_FIX && (tt == NODE_PROBLEM || tt == NODE_ERROR
                                                || tt == NODE_INCIDENT))
                        derive_type = EDGE_PREVENTATIVE;
                    /* PREVENTION → ERROR/PROBLEM = preventative */
                    else if (ft == NODE_PREVENTION && (tt == NODE_ERROR || tt == NODE_PROBLEM
                                                       || tt == NODE_INCIDENT))
                        derive_type = EDGE_PREVENTATIVE;
                    /* SOLUTION → PROBLEM/ERROR = preventative */
                    else if (ft == NODE_SOLUTION && (tt == NODE_PROBLEM || tt == NODE_ERROR
                                                     || tt == NODE_INCIDENT))
                        derive_type = EDGE_PREVENTATIVE;

                    /* LAW → LAW case: use edge type to determine semantic role.
                     * If law A is connected via EDGE_CAUSAL and law B via EDGE_PREVENTATIVE,
                     * then A → B is a causal → preventative relationship. */
                    if (derive_type == EDGE_TYPE_COUNT && ft == NODE_LAW && tt == NODE_LAW) {
                        /* cause edge → problem edge = causal */
                        if (et_a == EDGE_CAUSAL && (et_b == EDGE_CAUSAL || et_b == EDGE_HISTORICAL))
                            derive_type = EDGE_CAUSAL;
                        /* fix edge → problem/error edge = preventative */
                        else if (et_a == EDGE_PREVENTATIVE && (et_b == EDGE_CAUSAL || et_b == EDGE_HISTORICAL))
                            derive_type = EDGE_PREVENTATIVE;
                        /* cause edge → fix edge = causal (cause → fix = what this cause leads to fixing) */
                        else if (et_a == EDGE_CAUSAL && et_b == EDGE_PREVENTATIVE)
                            derive_type = EDGE_CAUSAL;
                    }

                    if (derive_type == EDGE_TYPE_COUNT) continue;

                    /* Add the derived edge (rf_add_edge handles dedup + schema) */
                    int r = rf_add_edge(e, from, to, derive_type);
                    if (r >= 0) {
                        derived++;
                        if (e->verbose && derived <= 20)
                            printf("  [composite] DERIVED: '%s' → '%s' (%s, via law %d)\n",
                                   e->field.nodes[from].name,
                                   e->field.nodes[to].name,
                                   EDGE_TYPE_NAMES[derive_type], law_n);
                    }
                }
            }
        }

        if (e->verbose)
            printf("  [composite] Derived %d edges from law co-occurrence\n", derived);

        /* Now re-scan for composite edges using the newly derived edges.
         * This is a second pass — the derived edges enable the composites. */

        /* Re-scan for CAUSAL_CHAIN: CAUSE → PROBLEM → ERROR */
        for (int i = 0; i < e->field.edge_count && e->field.edge_count < MAX_EDGES - 1; i++) {
            Edge *e1 = &e->field.edges[i];
            if (e1->type != EDGE_CAUSAL) continue;
            if (e->field.nodes[e1->from].type != NODE_CAUSE) continue;
            if (e->field.nodes[e1->to].type != NODE_PROBLEM) continue;

            /* Look for second hop: PROBLEM → ERROR */
            for (int j = 0; j < e->field.edge_count; j++) {
                if (j == i) continue;
                Edge *e2 = &e->field.edges[j];
                if (e2->type != EDGE_CAUSAL) continue;
                if (e2->from != e1->to) continue;
                if (e->field.nodes[e2->to].type != NODE_ERROR
                    && e->field.nodes[e2->to].type != NODE_INCIDENT) continue;

                int r = rf_add_edge(e, e1->from, e2->to, EDGE_CAUSAL_CHAIN);
                if (r >= 0) {
                    generated++;
                    chains++;
                    if (e->verbose)
                        printf("  [composite] CAUSAL_CHAIN: '%s' → '%s' → '%s'\n",
                               e->field.nodes[e1->from].name,
                               e->field.nodes[e1->to].name,
                               e->field.nodes[e2->to].name);
                }
                break;
            }
        }

        /* Re-scan for RESOLUTION: FIX → PROBLEM → ERROR */
        for (int i = 0; i < e->field.edge_count && e->field.edge_count < MAX_EDGES - 1; i++) {
            Edge *e1 = &e->field.edges[i];
            if (e1->type != EDGE_PREVENTATIVE) continue;
            if (e->field.nodes[e1->from].type != NODE_FIX
                && e->field.nodes[e1->from].type != NODE_PREVENTION
                && e->field.nodes[e1->from].type != NODE_SOLUTION) continue;
            if (e->field.nodes[e1->to].type != NODE_PROBLEM) continue;

            for (int j = 0; j < e->field.edge_count; j++) {
                if (j == i) continue;
                Edge *e2 = &e->field.edges[j];
                if (e2->type != EDGE_CAUSAL) continue;
                if (e2->from != e1->to) continue;
                if (e->field.nodes[e2->to].type != NODE_ERROR
                    && e->field.nodes[e2->to].type != NODE_INCIDENT) continue;

                int r = rf_add_edge(e, e1->from, e2->to, EDGE_RESOLUTION);
                if (r >= 0) {
                    generated++;
                    resolutions++;
                    if (e->verbose)
                        printf("  [composite] RESOLUTION: '%s' → '%s' → '%s'\n",
                               e->field.nodes[e1->from].name,
                               e->field.nodes[e1->to].name,
                               e->field.nodes[e2->to].name);
                }
                break;
            }
        }

        /* Re-scan for ATTACK_PATH: LAW → CAUSE/PROBLEM → ERROR */
        for (int i = 0; i < e->field.edge_count && e->field.edge_count < MAX_EDGES - 1; i++) {
            Edge *e1 = &e->field.edges[i];
            if (e1->type != EDGE_AUTHORITY && e1->type != EDGE_CAUSAL) continue;
            if (e->field.nodes[e1->from].type != NODE_LAW) continue;
            if (e->field.nodes[e1->to].type != NODE_CAUSE
                && e->field.nodes[e1->to].type != NODE_PROBLEM) continue;

            /* Look for: e1->to → ERROR */
            for (int j = 0; j < e->field.edge_count; j++) {
                if (j == i) continue;
                Edge *e2 = &e->field.edges[j];
                if (e2->type != EDGE_CAUSAL && e2->type != EDGE_CAUSAL_CHAIN) continue;
                if (e2->from != e1->to) continue;
                if (e->field.nodes[e2->to].type != NODE_ERROR
                    && e->field.nodes[e2->to].type != NODE_INCIDENT) continue;

                int r = rf_add_edge(e, e1->from, e2->to, EDGE_ATTACK_PATH);
                if (r >= 0) {
                    generated++;
                    attack_paths++;
                    if (e->verbose)
                        printf("  [composite] ATTACK_PATH: '%s' → '%s' → '%s'\n",
                               e->field.nodes[e1->from].name,
                               e->field.nodes[e1->to].name,
                               e->field.nodes[e2->to].name);
                }
                break;
            }
        }

        /* Re-scan for VIOLATION: LAW → ERROR directly (via any edge type) */
        for (int i = 0; i < e->field.edge_count && e->field.edge_count < MAX_EDGES - 1; i++) {
            Edge *ed = &e->field.edges[i];
            if (e->field.nodes[ed->from].type != NODE_LAW) continue;
            if (e->field.nodes[ed->to].type != NODE_ERROR
                && e->field.nodes[ed->to].type != NODE_PROBLEM
                && e->field.nodes[ed->to].type != NODE_INCIDENT) continue;
            if (ed->type == EDGE_VIOLATION || ed->type == EDGE_ATTACK_PATH) continue;

            int r = rf_add_edge(e, ed->from, ed->to, EDGE_VIOLATION);
            if (r >= 0) {
                generated++;
                violations++;
                if (e->verbose)
                    printf("  [composite] VIOLATION: Law '%s' → '%s'\n",
                           e->field.nodes[ed->from].name,
                           e->field.nodes[ed->to].name);
            }
        }

        /* ── 5b. Simple ATTACK_PATH: LAW with VIOLATION → ERROR ──
         * If a LAW has a VIOLATION edge to an ERROR, it's also an attack path.
         * The law "attacks" the error by being violated. This is simpler than
         * the 2-hop CAUSE→ERROR pattern but works when we only have LAW→LAW links. */
        for (int i = 0; i < e->field.edge_count && e->field.edge_count < MAX_EDGES - 1; i++) {
            Edge *ed = &e->field.edges[i];
            if (ed->type != EDGE_VIOLATION) continue;
            if (e->field.nodes[ed->from].type != NODE_LAW) continue;
            if (e->field.nodes[ed->to].type != NODE_ERROR
                && e->field.nodes[ed->to].type != NODE_PROBLEM
                && e->field.nodes[ed->to].type != NODE_INCIDENT) continue;

            /* Check if this law also has authority edges (governance power) */
            int has_auth = 0;
            for (int j = 0; j < e->field.edge_count; j++) {
                if (e->field.edges[j].from == ed->from
                    && e->field.edges[j].type == EDGE_AUTHORITY) {
                    has_auth = 1;
                    break;
                }
            }

            /* Also check if the law has any causal edges (causal power) */
            int has_causal = 0;
            for (int j = 0; j < e->field.edge_count; j++) {
                if (e->field.edges[j].from == ed->from
                    && (e->field.edges[j].type == EDGE_CAUSAL
                        || e->field.edges[j].type == EDGE_CAUSAL_CHAIN)) {
                    has_causal = 1;
                    break;
                }
            }

            /* If the law has both violation AND authority/causal power,
             * it's on an attack path. */
            if (has_auth || has_causal) {
                int r = rf_add_edge(e, ed->from, ed->to, EDGE_ATTACK_PATH);
                if (r >= 0) {
                    generated++;
                    attack_paths++;
                    if (e->verbose)
                        printf("  [composite] ATTACK_PATH (violation+authority): '%s' → '%s'\n",
                               e->field.nodes[ed->from].name,
                               e->field.nodes[ed->to].name);
                }
            }
        }

        /* ── 6. Transitive composite edge propagation ──
         * BloodHound principle: if A can reach B, and B can reach C,
         * then A can reach C. Transitive closure of composite edges.
         *
         * If LAW A → LAW B (any edge) and LAW B has EDGE_VIOLATION → ERROR,
         * then LAW A → ERROR is a transitive violation.
         *
         * This is critical for entity_link where all links are LAW→LAW.
         * Without this, only the directly-connected law gets composite edges.
         * With this, the entire law chain propagates violations.
         *
         * Limit: only 1 pass, only from laws directly connected to the anchor,
         * and skip meta-law nodes (edge type descriptions, etc.). */
        {
            int trans_count = 0;
            for (int i = 0; i < e->field.edge_count && e->field.edge_count < MAX_EDGES - 1; i++) {
                Edge *e1 = &e->field.edges[i];
                /* Must be LAW → LAW (any edge type except composite) */
                if (e1->type == EDGE_VIOLATION || e1->type == EDGE_ATTACK_PATH
                    || e1->type == EDGE_CAUSAL_CHAIN || e1->type == EDGE_RESOLUTION)
                    continue;
                if (e->field.nodes[e1->from].type != NODE_LAW) continue;
                if (e->field.nodes[e1->to].type != NODE_LAW) continue;

                int law_a = e1->from;
                int law_b = e1->to;

                /* Only propagate from the anchor law or laws directly connected to it.
                 * This prevents the cascade from propagating to every law in the graph. */
                if (law_a != e->field.anchor_id) continue;

                /* Skip meta-law nodes (edge type descriptions, etc.) */
                if (strncmp(e->field.nodes[law_a].name, "Edge:", 5) == 0) continue;
                if (strncmp(e->field.nodes[law_b].name, "Edge:", 5) == 0) continue;
                if (strncmp(e->field.nodes[law_a].name, "Node:", 5) == 0) continue;
                if (strncmp(e->field.nodes[law_b].name, "Node:", 5) == 0) continue;

                /* Check if law_b has any composite edge to an ERROR/PROBLEM */
                for (int j = 0; j < e->field.edge_count; j++) {
                    if (j == i) continue;
                    Edge *e2 = &e->field.edges[j];
                    if (e2->from != law_b) continue;
                    if (e2->type != EDGE_VIOLATION && e2->type != EDGE_ATTACK_PATH)
                        continue;
                    int target = e2->to;

                    /* Propagate: law_a → target gets the same composite type */
                    int r = rf_add_edge(e, law_a, target, e2->type);
                    if (r >= 0) {
                        generated++;
                        if (e2->type == EDGE_ATTACK_PATH) attack_paths++;
                        else if (e2->type == EDGE_VIOLATION) violations++;
                        trans_count++;
                        if (e->verbose && trans_count <= 10)
                            printf("  [composite] TRANSITIVE %s: '%s' → '%s' (via '%s')\n",
                                   EDGE_TYPE_NAMES[e2->type],
                                   e->field.nodes[law_a].name,
                                   e->field.nodes[target].name,
                                   e->field.nodes[law_b].name);
                    }
                }
            }
            if (e->verbose && trans_count > 0)
                printf("  [composite] Propagated %d transitive composite edges (from anchor)\n",
                       trans_count);
        }
    }

    /* Mark nodes with high_value flags (BloodHound "highvalue" equivalent).
     * Nodes on attack paths or with violations are high-value targets. */
    for (int i = 0; i < e->field.edge_count; i++) {
        Edge *ed = &e->field.edges[i];
        if (ed->type == EDGE_ATTACK_PATH) {
            e->field.nodes[ed->from].has_attack_path = 1;
            e->field.nodes[ed->to].has_attack_path = 1;
            e->field.nodes[ed->from].high_value = 1;
            e->field.nodes[ed->to].high_value = 1;
        }
        if (ed->type == EDGE_VIOLATION) {
            e->field.nodes[ed->from].has_violation = 1;
            e->field.nodes[ed->to].has_violation = 1;
            e->field.nodes[ed->from].high_value = 1;
            e->field.nodes[ed->to].high_value = 1;
        }
    }

    int hv_count = 0;
    for (int i = 0; i < e->field.node_count; i++)
        if (e->field.nodes[i].high_value) hv_count++;

    if (e->verbose)
        printf("  [composite] Generated %d composite edges: %d violations, %d chains, "
               "%d resolutions, %d attack_paths\n",
               generated, violations, chains, resolutions, attack_paths);
    if (e->verbose)
        printf("  [composite] Marked %d high-value nodes (on attack paths/violations)\n",
               hv_count);

    return generated;
}

/*
 * Print the edge schema — BloodHound-style documentation.
 * Shows which edge types are valid between which node types.
 */
void rf_print_edge_schema(void) {
    printf("\n=== Edge Schema (BloodHound-style) ===\n\n");

    printf("Base edges:\n");
    printf("  %-18s  any → any\n", "structural");
    printf("  %-18s  any → any\n", "semantic");
    printf("  %-18s  LAW → any\n", "authority");
    printf("  %-18s  PATTERN → any\n", "behavioral");
    printf("  %-18s  ERROR/INCIDENT → any\n", "historical");
    printf("  %-18s  CAUSE/PROBLEM/LAW → ERROR/PROBLEM\n", "causal");
    printf("  %-18s  FIX/PREVENTION/LAW → ERROR/PROBLEM\n", "preventative");
    printf("  %-18s  any → any\n", "contradictory");
    printf("  %-18s  same type → same type\n", "similarity");
    printf("  %-18s  synthetic (not stored)\n", "missing");

    printf("\nComposite edges (post-processing):\n");
    printf("  %-18s  LAW → ERROR/PROBLEM  [authority + error type]\n", "violation");
    printf("  %-18s  CAUSE → ERROR        [causal 2-hop transitive]\n", "causal_chain");
    printf("  %-18s  FIX → ERROR          [preventative + causal chain]\n", "resolution");
    printf("  %-18s  LAW → ERROR          [authority + causal = exploit]\n", "attack_path");

    printf("\nEdge weights:\n");
    for (int t = 0; t < EDGE_TYPE_COUNT; t++)
        printf("  %-18s  %.2f%s\n", EDGE_TYPE_NAMES[t],
               DEFAULT_EDGE_WEIGHTS[t],
               t >= EDGE_VIOLATION ? "  (composite)" : "");
    printf("\n");
}

/* ========================================================================== */
/*  SECTION 9d — Shortest path finder (BloodHound BFS pathfinding)           */
/* ========================================================================== */
/*
 * BloodHound's core feature: find the shortest attack path from node A
 * to node B. Uses BFS over traversable edges.
 *
 * In RF-TA, this finds the shortest reasoning path — the chain of
 * inferences from one concept to another.
 *
 * All edges are traversable in RF-TA (even "non-traversable" base edges
 * can be followed for reasoning, just with lower weight). Composite edges
 * are preferred because they have the highest weights.
 */

#define MAX_PATH_LEN 32

typedef struct {
    int nodes[MAX_PATH_LEN];
    EdgeType edge_types[MAX_PATH_LEN];
    int length;         /* number of edges = number of nodes - 1 */
    double total_weight;
} Path;

/*
 * Dijkstra highest-weight path from `start` to `target`.
 * BloodHound uses weighted pathfinding — we want the MOST CONFIDENT path,
 * not just the fewest hops. A path through composite edges (weight 0.99)
 * is preferred over a path through structural edges (weight 0.80) even
 * if it's longer.
 *
 * We use Dijkstra with "distance" = -log(weight) so that higher weight
 * = shorter distance. This finds the maximum-product path.
 *
 * Returns 1 if a path was found, 0 if not.
 */
static int rf_shortest_path(RFEngine *e, int start, int target, Path *path) {
    if (start < 0 || start >= e->field.node_count) return 0;
    if (target < 0 || target >= e->field.node_count) return 0;
    if (start == target) {
        path->nodes[0] = start;
        path->length = 0;
        path->total_weight = 1.0;
        return 1;
    }

    /* Dijkstra: dist[node] = -log(product of edge weights)
     * We want to minimize this = maximize the product of weights */
    double dist[MAX_NODES];
    int parent[MAX_NODES];
    EdgeType parent_edge[MAX_NODES];
    int visited[MAX_NODES];

    for (int i = 0; i < e->field.node_count; i++) {
        dist[i] = 1e18;
        parent[i] = -1;
        visited[i] = 0;
    }

    dist[start] = 0.0;

    /* Simple O(V²) Dijkstra — fine for our node count */
    for (int iter = 0; iter < e->field.node_count; iter++) {
        /* Find unvisited node with minimum distance */
        double min_dist = 1e18;
        int cur = -1;
        for (int i = 0; i < e->field.node_count; i++) {
            if (!visited[i] && dist[i] < min_dist) {
                min_dist = dist[i];
                cur = i;
            }
        }
        if (cur < 0) break;
        visited[cur] = 1;
        if (cur == target) break;

        /* Relax outgoing edges */
        for (int i = 0; i < e->field.edge_count; i++) {
            if (e->field.edges[i].from != cur) continue;
            int next = e->field.edges[i].to;
            if (visited[next]) continue;

            double w = e->field.edges[i].weight;
            if (w <= 0.0) w = 0.01;  /* avoid log(0) */
            double edge_dist = -log(w);  /* higher weight = lower distance */

            if (dist[cur] + edge_dist < dist[next]) {
                dist[next] = dist[cur] + edge_dist;
                parent[next] = cur;
                parent_edge[next] = e->field.edges[i].type;
            }
        }
    }

    if (parent[target] < 0 && target != start) return 0;

    /* Reconstruct path */
    int node = target;
    int path_nodes[MAX_PATH_LEN];
    EdgeType path_edges[MAX_PATH_LEN];
    int len = 0;

    while (node != start && len < MAX_PATH_LEN) {
        path_edges[len] = parent_edge[node];
        path_nodes[len] = node;
        node = parent[node];
        len++;
        if (node < 0) return 0;
    }
    path_nodes[len] = start;

    /* Reverse into output */
    path->length = len;
    path->total_weight = 1.0;
    for (int i = 0; i <= len; i++) {
        path->nodes[i] = path_nodes[len - i];
    }
    for (int i = 0; i < len; i++) {
        path->edge_types[i] = path_edges[len - 1 - i];
        path->total_weight *= e->policy.edge_weights[path->edge_types[i]];
    }

    return 1;
}

/*
 * Print a path in BloodHound-style format:
 *   Node1 →[edge_type]→ Node2 →[edge_type]→ Node3
 */
static void rf_print_path(RFEngine *e, Path *path) {
    if (path->length == 0) {
        printf("  %s (single node)\n", e->field.nodes[path->nodes[0]].name);
        return;
    }

    for (int i = 0; i < path->length; i++) {
        Node *n = &e->field.nodes[path->nodes[i]];
        printf("  %s", n->name);
        printf(" →[%s]→", EDGE_TYPE_NAMES[path->edge_types[i]]);
    }
    printf("  %s\n", e->field.nodes[path->nodes[path->length]].name);
    printf("  Path weight: %.3f, length: %d hops\n",
           path->total_weight, path->length);
}

/*
 * Find all shortest paths from `start` to all high-value nodes.
 * BloodHound equivalent: "shortest path to Domain Admin".
 *
 * Prints the top N shortest paths to high-value targets.
 */
void rf_find_attack_paths(RFEngine *e, int start, int max_paths) {
    printf("\n=== Attack Path Analysis (BloodHound-style) ===\n");
    printf("  Start node: %s (node %d)\n\n",
           e->field.nodes[start].name, start);

    /* Collect high-value target nodes */
    int targets[MAX_NODES];
    int n_targets = 0;
    for (int i = 0; i < e->field.node_count && n_targets < MAX_NODES; i++) {
        if (i == start) continue;
        if (e->field.nodes[i].high_value) {
            targets[n_targets++] = i;
        }
    }

    if (n_targets == 0) {
        printf("  No high-value targets found.\n\n");
        return;
    }

    printf("  Found %d high-value targets. Finding shortest paths...\n\n", n_targets);

    /* Find paths, sort by weight (highest = most confident) */
    Path paths[64];
    int found = 0;

    for (int t = 0; t < n_targets && found < 64; t++) {
        Path p;
        if (rf_shortest_path(e, start, targets[t], &p)) {
            paths[found++] = p;
        }
    }

    /* Simple sort by total_weight (descending) */
    for (int i = 1; i < found; i++) {
        Path key = paths[i];
        int j = i - 1;
        while (j >= 0 && paths[j].total_weight < key.total_weight) {
            paths[j + 1] = paths[j];
            j--;
        }
        paths[j + 1] = key;
    }

    int show = found < max_paths ? found : max_paths;
    printf("  Top %d attack paths (by confidence weight):\n\n", show);

    for (int i = 0; i < show; i++) {
        printf("  [%d] ", i + 1);
        rf_print_path(e, &paths[i]);
        printf("\n");
    }

    if (found > show)
        printf("  ... and %d more paths\n\n", found - show);
}

/*
 * Find the shortest path between any two nodes by name.
 * Returns the path or NULL if not found.
 */
void rf_find_path_between(RFEngine *e, const char *from_name, const char *to_name) {
    int from = -1, to = -1;

    for (int i = 0; i < e->field.node_count; i++) {
        if (strstr(e->field.nodes[i].name, from_name)) {
            from = i;
            break;
        }
    }
    for (int i = 0; i < e->field.node_count; i++) {
        if (strstr(e->field.nodes[i].name, to_name)) {
            to = i;
            break;
        }
    }

    if (from < 0) {
        printf("  Node '%s' not found.\n", from_name);
        return;
    }
    if (to < 0) {
        printf("  Node '%s' not found.\n", to_name);
        return;
    }

    printf("\n=== Shortest Path ===\n");
    printf("  From: %s (node %d)\n", e->field.nodes[from].name, from);
    printf("  To:   %s (node %d)\n\n", e->field.nodes[to].name, to);

    Path p;
    if (rf_shortest_path(e, from, to, &p)) {
        rf_print_path(e, &p);
    } else {
        printf("  No path found.\n");
    }
    printf("\n");
}

/*
 * Find ALL paths from `start` to `target` up to max_depth hops.
 * BloodHound's "find all paths" feature.
 *
 * Uses DFS with backtracking. Returns paths sorted by weight.
 */
void rf_find_all_paths(RFEngine *e, int start, int target, int max_depth,
                       int max_results) {
    printf("\n=== All Paths (DFS, max %d hops) ===\n", max_depth);
    printf("  From: %s (node %d)\n", e->field.nodes[start].name, start);
    printf("  To:   %s (node %d)\n\n", e->field.nodes[target].name, target);

    Path paths[64];
    int found = 0;

    /* DFS stack */
    int stack_nodes[MAX_PATH_LEN + 1];
    EdgeType stack_edges[MAX_PATH_LEN];
    int stack_edge_idx[MAX_PATH_LEN];  /* which edge index we're at for each level */
    int depth = 0;
    int visited[MAX_NODES];

    memset(visited, 0, sizeof(int) * e->field.node_count);

    stack_nodes[0] = start;
    visited[start] = 1;
    stack_edge_idx[0] = 0;

    while (depth >= 0) {
        if (depth >= max_depth) {
            /* Backtrack */
            visited[stack_nodes[depth]] = 0;
            depth--;
            if (depth >= 0) stack_edge_idx[depth]++;
            continue;
        }

        int cur = stack_nodes[depth];
        int found_edge = 0;

        /* Find next outgoing edge from cur */
        for (int i = stack_edge_idx[depth]; i < e->field.edge_count; i++) {
            if (e->field.edges[i].from != cur) continue;
            int next = e->field.edges[i].to;
            if (visited[next]) continue;

            /* Found an edge to explore */
            stack_edge_idx[depth] = i + 1;  /* next time, start after this */
            stack_edges[depth] = e->field.edges[i].type;
            depth++;
            stack_nodes[depth] = next;
            stack_edge_idx[depth] = 0;
            visited[next] = 1;

            if (next == target) {
                /* Found a path! */
                if (found < 64) {
                    Path *p = &paths[found];
                    p->length = depth;
                    p->total_weight = 1.0;
                    for (int j = 0; j <= depth; j++)
                        p->nodes[j] = stack_nodes[j];
                    for (int j = 0; j < depth; j++) {
                        p->edge_types[j] = stack_edges[j];
                        p->total_weight *= e->policy.edge_weights[stack_edges[j]];
                    }
                    found++;
                }
                /* Backtrack to find more */
                visited[next] = 0;
                depth--;
            }
            found_edge = 1;
            break;
        }

        if (!found_edge) {
            /* No more edges from this node — backtrack */
            visited[stack_nodes[depth]] = 0;
            depth--;
            if (depth >= 0) stack_edge_idx[depth]++;
        }
    }

    if (found == 0) {
        printf("  No paths found.\n\n");
        return;
    }

    /* Sort by weight (descending) */
    for (int i = 1; i < found; i++) {
        Path key = paths[i];
        int j = i - 1;
        while (j >= 0 && paths[j].total_weight < key.total_weight) {
            paths[j + 1] = paths[j];
            j--;
        }
        paths[j + 1] = key;
    }

    int show = found < max_results ? found : max_results;
    printf("  Found %d paths. Top %d by confidence:\n\n", found, show);

    for (int i = 0; i < show; i++) {
        printf("  [%d] ", i + 1);
        rf_print_path(e, &paths[i]);
        printf("\n");
    }

    if (found > show)
        printf("  ... and %d more paths\n\n", found - show);
}

/* ========================================================================== */
/*  SECTION 10 — Shadow graph (pruning)                                      */
/* ========================================================================== */

/* Generate a simple structural fingerprint for a node */
static void compute_fingerprint(RFEngine *e, int node_id, char *buf, int size) {
    /* Fingerprint = node type + domain + degree + edge type distribution */
    Node *n = &e->field.nodes[node_id];
    int degree = 0;
    int edge_type_hist[EDGE_TYPE_COUNT] = {0};

    for (int i = 0; i < e->field.edge_count; i++) {
        Edge *ed = &e->field.edges[i];
        if (ed->from == node_id || ed->to == node_id) {
            degree++;
            edge_type_hist[ed->type]++;
        }
    }

    snprintf(buf, size, "%d:%s:%d", n->type, n->domain, degree);
    /* Append edge type histogram as compact hash */
    for (int t = 0; t < EDGE_TYPE_COUNT; t++) {
        char tmp[8];
        snprintf(tmp, sizeof(tmp), "%d", edge_type_hist[t]);
        strncat(buf, tmp, size - strlen(buf) - 1);
    }
}

static int shadow_lookup(ShadowGraph *sg, int node_id) {
    for (int i = 0; i < sg->count; i++)
        if (sg->entries[i].node_id == node_id) return i;
    return -1;
}

static double shadow_similarity(const char *a, const char *b) {
    /* Simple string-based similarity (Jaccard on chars) */
    int len_a = strlen(a), len_b = strlen(b);
    if (len_a == 0 || len_b == 0) return 0.0;
    int common = 0;
    int min_len = len_a < len_b ? len_a : len_b;
    for (int i = 0; i < min_len; i++)
        if (a[i] == b[i]) common++;
    return (double)common / (double)(len_a > len_b ? len_a : len_b);
}

static int shadow_check(RFEngine *e, int node_id) {
    char fp[64];
    compute_fingerprint(e, node_id, fp, sizeof(fp));

    for (int i = 0; i < e->shadow.count; i++) {
        double sim = shadow_similarity(fp, e->shadow.entries[i].fingerprint);
        if (sim > SHADOW_THRESHOLD && e->shadow.entries[i].fully_explored) {
            if (e->verbose)
                printf("  [shadow] Pruning node %d (sim=%.2f to node %d)\n",
                       node_id, sim, e->shadow.entries[i].node_id);
            return 1;  /* prune — already explored similar region */
        }
    }
    return 0;  /* expand */
}

static void shadow_add(RFEngine *e, int node_id, int fully_explored) {
    if (e->shadow.count >= MAX_SHADOW) return;
    if (shadow_lookup(&e->shadow, node_id) >= 0) return;
    ShadowEntry *s = &e->shadow.entries[e->shadow.count++];
    s->node_id = node_id;
    compute_fingerprint(e, node_id, s->fingerprint, sizeof(s->fingerprint));
    s->cluster_id = e->field.nodes[node_id].cluster_id;
    s->fully_explored = fully_explored;
}

/* ========================================================================== */
/*  SECTION 11 — Information gain scoring                                    */
/* ========================================================================== */

/*
 * Look up a node's probability from the constraint engine.
 * Returns 0.0 if constraints not initialized or node not in hypothesis space.
 * This is the bridge: constraint probabilities guide traversal.
 */
static double constraint_probability(RFEngine *e, int node_id) {
    if (e->constraints.hypothesis_count == 0) return 0.0;
    for (int i = 0; i < e->constraints.hypothesis_count; i++) {
        if (e->constraints.hypotheses[i].node_id == node_id) {
            if (e->constraints.hypotheses[i].eliminated) return -1.0;  /* pruned */
            return e->constraints.hypotheses[i].probability;
        }
    }
    return 0.0;
}

/*
 * IG(node) = novelty + missing_link_score + authority_importance
 *          + causal_potential + constraint_probability
 *          - redundancy_penalty
 *
 * The constraint_probability term is the key integration:
 * nodes that the constraint engine considers more likely get higher
 * information gain, so traversal preferentially expands them.
 * This turns RF-TA into a constraint-guided search.
 */
static double compute_info_gain(RFEngine *e, int node_id,
                                EdgeType incoming_edge, int depth) {
    Node *n = &e->field.nodes[node_id];

    /* Novelty — decays with visits.
     * Owned nodes (previously concluded) have lower novelty — we've
     * already reasoned about them. But their authority is boosted. */
    double novelty = n->novelty;
    if (rf_is_owned(e, node_id)) novelty *= 0.3;  /* less novel if already owned */

    /* Missing-link score — higher for missing edge type */
    double missing_score = 0.0;
    if (incoming_edge == EDGE_MISSING)
        missing_score = e->policy.missing_sensitivity * 1.0;
    else {
        /* Check if this node has missing edges (expected but absent) */
        int has_incoming = 0, has_outgoing = 0;
        for (int i = 0; i < e->field.edge_count; i++) {
            if (e->field.edges[i].to == node_id) has_incoming = 1;
            if (e->field.edges[i].from == node_id) has_outgoing = 1;
        }
        if (!has_incoming || !has_outgoing)
            missing_score = e->policy.missing_sensitivity * 0.5;
    }

    /* Authority importance */
    double authority = n->authority;

    /* Causal potential — higher if connected via causal edges.
     * Composite edges get the highest boost — they represent confirmed
     * multi-condition relationships (BloodHound attack paths). */
    double causal_pot = 0.0;
    if (incoming_edge == EDGE_CAUSAL) causal_pot = 0.5;
    else if (incoming_edge == EDGE_PREVENTATIVE) causal_pot = 0.3;
    else if (incoming_edge == EDGE_ATTACK_PATH) causal_pot = 1.0;  /* highest */
    else if (incoming_edge == EDGE_VIOLATION) causal_pot = 0.8;
    else if (incoming_edge == EDGE_CAUSAL_CHAIN) causal_pot = 0.7;
    else if (incoming_edge == EDGE_RESOLUTION) causal_pot = 0.6;

    /* High-value node boost — BloodHound marks Domain Admins as "highvalue".
     * Nodes on attack paths or with violations get a boost. */
    double high_value_boost = 0.0;
    if (n->high_value) high_value_boost = 0.3;
    if (n->has_attack_path) high_value_boost += 0.2;

    /* Constraint probability — the bridge between constraint engine and traversal.
     * Nodes with higher belief mass are preferentially expanded.
     * Eliminated nodes (return -1.0) are skipped entirely. */
    double cp = constraint_probability(e, node_id);
    double constraint_boost = 0.0;
    if (cp < 0.0) {
        /* Node was eliminated by a hard constraint — skip it */
        return -1.0;
    }
    if (cp > 0.0) {
        /* Scale: a node with 50% belief mass gets +0.5 info gain */
        constraint_boost = cp * 2.0;  /* scale up since probabilities are small */
    }

    /* Redundancy penalty — already visited */
    double redundancy = n->visited ? 0.5 : 0.0;

    /* Depth penalty — deeper = slightly less gain (BFS bias) */
    double depth_penalty = depth * 0.05;

    double ig = novelty + missing_score + authority + causal_pot
              + constraint_boost + high_value_boost
              - redundancy - depth_penalty;

    return clampd(ig, 0.0, 3.0);
}

/*
 * priority_score = edge_weight × information_gain × novelty_factor
 */
static double compute_priority(RFEngine *e, EdgeType edge_type,
                               double info_gain, double novelty) {
    double ew = e->policy.edge_weights[edge_type];
    double nf = clampd(novelty + 0.1, 0.0, 1.5);  /* floor so new nodes get expanded */
    return ew * info_gain * nf;
}

/* ========================================================================== */
/*  SECTION 12 — Frontier management (priority queue)                        */
/* ========================================================================== */

static void frontier_push(Frontier *f, int node_id, double priority,
                          int depth, int is_bfs, EdgeType incoming) {
    if (f->count >= MAX_FRONTIER) {
        /* Replace lowest-priority entry if new one is higher */
        int min_idx = 0;
        for (int i = 1; i < f->count; i++)
            if (f->entries[i].priority < f->entries[min_idx].priority)
                min_idx = i;
        if (priority > f->entries[min_idx].priority) {
            f->entries[min_idx] = (FrontierEntry){
                node_id, priority, depth, is_bfs, incoming
            };
        }
        return;
    }
    f->entries[f->count++] = (FrontierEntry){
        node_id, priority, depth, is_bfs, incoming
    };
}

static FrontierEntry frontier_pop(Frontier *f) {
    /* Pop highest priority entry */
    int best = 0;
    for (int i = 1; i < f->count; i++)
        if (f->entries[i].priority > f->entries[best].priority)
            best = i;
    FrontierEntry e = f->entries[best];
    f->entries[best] = f->entries[--f->count];
    return e;
}

static int frontier_empty(Frontier *f) {
    return f->count == 0;
}

/* ========================================================================== */
/*  SECTION 13 — Edge classification                                         */
/* ========================================================================== */

/*
 * Classify what type of relationship is discovered when expanding.
 * In a real system this would use schema metadata + semantic analysis.
 * Here we use the edge type already stored on the edge.
 */
static EdgeType classify_edge(Edge *ed) {
    return ed->type;
}

/* ========================================================================== */
/*  SECTION 14 — Missing link detector                                       */
/* ========================================================================== */

/*
 * Detect expected-but-absent edges.
 * For each node, check if it should have edges of certain types
 * based on its node type (e.g., an error should have causal + authority).
 */
static int detect_missing_links(RFEngine *e, int node_id,
                                EdgeType *missing_types, int max_missing) {
    Node *n = &e->field.nodes[node_id];
    int found = 0;

    /* Expected edge types per node type */
    EdgeType expected[4];
    int expected_count = 0;

    switch (n->type) {
        case NODE_ERROR:
            expected[0] = EDGE_CAUSAL;
            expected[1] = EDGE_AUTHORITY;
            expected[2] = EDGE_PREVENTATIVE;
            expected_count = 3;
            break;
        case NODE_LAW:
            expected[0] = EDGE_AUTHORITY;
            expected[1] = EDGE_CONTRADICTORY;
            expected_count = 2;
            break;
        case NODE_PATTERN:
            expected[0] = EDGE_CAUSAL;
            expected[1] = EDGE_PREVENTATIVE;
            expected_count = 2;
            break;
        case NODE_INCIDENT:
            expected[0] = EDGE_CAUSAL;
            expected[1] = EDGE_HISTORICAL;
            expected[2] = EDGE_AUTHORITY;
            expected_count = 3;
            break;
        case NODE_PROBLEM:
            expected[0] = EDGE_CAUSAL;
            expected[1] = EDGE_PREVENTATIVE;
            expected[2] = EDGE_AUTHORITY;
            expected_count = 3;
            break;
        case NODE_CAUSE:
            expected[0] = EDGE_CAUSAL;
            expected_count = 1;
            break;
        case NODE_FIX:
        case NODE_PREVENTION:
        case NODE_SOLUTION:
            expected[0] = EDGE_PREVENTATIVE;
            expected_count = 1;
            break;
        default:
            expected[0] = EDGE_STRUCTURAL;
            expected_count = 1;
    }

    for (int ei = 0; ei < expected_count && found < max_missing; ei++) {
        EdgeType want = expected[ei];
        int has_it = 0;
        for (int i = 0; i < e->field.edge_count; i++) {
            Edge *ed = &e->field.edges[i];
            if ((ed->from == node_id || ed->to == node_id) && ed->type == want) {
                has_it = 1;
                break;
            }
        }
        if (!has_it) {
            missing_types[found++] = want;
        }
    }

    return found;
}

/* ========================================================================== */
/*  SECTION 15 — Stability scoring                                            */
/* ========================================================================== */

/*
 * stability = (new_info_rate ↓) + (edge_diversity ↓)
 *           + (frontier_overlap ↑) + (novel_nodes ↓)
 *
 * Returns 1 if stable (should stop), 0 if should continue.
 */
static int compute_stability(RFEngine *e, int layer, int *prev_new_info,
                             int *prev_diversity, int *prev_novel) {
    int new_info = e->field.new_info_rate;
    int diversity = e->field.edge_diversity;
    int overlap = e->field.frontier_overlap;
    int novel = 0;

    for (int i = 0; i < e->field.node_count; i++)
        if (e->field.nodes[i].visited && e->field.nodes[i].novelty > 0.5)
            novel++;

    /* Compute rate of change */
    double info_delta = (layer == 0) ? 1.0 :
        (double)(new_info - *prev_new_info) / (double)(*prev_new_info + 1);
    double div_delta = (layer == 0) ? 1.0 :
        (double)(diversity - *prev_diversity) / (double)(*prev_diversity + 1);
    double novel_delta = (layer == 0) ? 1.0 :
        (double)(novel - *prev_novel) / (double)(*prev_novel + 1);

    /* Stability score: high when things are settling down */
    double stability = (1.0 - clampd(fabs(info_delta), 0.0, 1.0)) * 0.3
                     + (1.0 - clampd(fabs(div_delta), 0.0, 1.0)) * 0.2
                     + clampd((double)overlap / 100.0, 0.0, 1.0) * 0.3
                     + (1.0 - clampd(fabs(novel_delta), 0.0, 1.0)) * 0.2;

    e->field.stability = stability;

    *prev_new_info = new_info;
    *prev_diversity = diversity;
    *prev_novel = novel;

    if (e->verbose && layer > 0)
        printf("  [stability] layer=%d  score=%.3f  info_delta=%.2f  div_delta=%.2f\n",
               layer, stability, info_delta, div_delta);

    /* Stop if stability is high enough or info gain drops below epsilon */
    if (stability > (1.0 - STABILITY_EPSILON)) return 1;
    if (layer > 0 && info_delta < STABILITY_EPSILON && div_delta < STABILITY_EPSILON)
        return 1;
    if (overlap > 90) return 1;  /* 90% of frontier repeats prior */

    return 0;
}

/* ========================================================================== */
/*  SECTION 16 — Traversal engine (hybrid BFS/DFS)                           */
/* ========================================================================== */

/*
 * Main RF-TA traversal loop.
 *
 * 1. Anchor node
 * 2. Initialize frontier = {anchor}
 * 3. while not stable:
 *    A. Select node from frontier (BFS early, DFS when causal/authority dominate)
 *    B. Generate candidate edges
 *    C. Score edges: weight × info_gain × novelty
 *    D. Expand top-K nodes
 *    E. Add missing-link synthesis step
 *    F. Update stability metrics
 * 4. return compressed field graph
 */
void rf_traverse(RFEngine *e) {
    if (e->field.anchor_id < 0) {
        fprintf(stderr, "rf_traverse: no anchor set\n");
        return;
    }

    int anchor = e->field.anchor_id;
    frontier_push(&e->frontier, anchor, 1.0, 0, 1, EDGE_STRUCTURAL);

    int layer = 0;
    int prev_new_info = 0, prev_diversity = 0, prev_novel = 0;
    int total_expanded = 0;
    int total_new_nodes = 0;

    if (e->verbose) {
        printf("\n=== RF-TA Traversal ===\n");
        printf("  Anchor: node %d (%s)\n", anchor, e->field.nodes[anchor].name);
    }

    while (!frontier_empty(&e->frontier) && layer < e->policy.max_depth) {
        int new_nodes_this_layer = 0;
        int edge_types_this_layer[EDGE_TYPE_COUNT] = {0};
        int repeated_frontier = 0;
        int total_frontier = e->frontier.count;

        /* Expand up to max_new_nodes_per_layer nodes this layer (BFS shell) */
        int expand_count = e->policy.max_new_nodes_per_layer;
        if (expand_count > e->frontier.count)
            expand_count = e->frontier.count;

        for (int ex = 0; ex < expand_count && !frontier_empty(&e->frontier); ex++) {
            FrontierEntry fe = frontier_pop(&e->frontier);
            int node_id = fe.node_id;
            Node *n = &e->field.nodes[node_id];

            if (n->visited && fe.depth > 0) {
                repeated_frontier++;
                continue;
            }

            n->visited = 1;
            n->depth = fe.depth;
            total_expanded++;

            if (e->verbose)
                printf("  [expand] node=%d depth=%d mode=%s edge=%s priority=%.3f\n",
                       node_id, fe.depth, fe.is_bfs ? "BFS" : "DFS",
                       edge_type_name(fe.incoming_edge), fe.priority);

            /* Shadow pruning — skip if similar region already explored */
            if (fe.depth > 1 && shadow_check(e, node_id))
                continue;

            /* Find all edges from this node */
            Edge *candidate_edges[MAX_EDGES_PER_NODE];
            double candidate_scores[MAX_EDGES_PER_NODE];
            int candidate_count = 0;

            for (int i = 0; i < e->field.edge_count && candidate_count < MAX_EDGES_PER_NODE; i++) {
                Edge *ed = &e->field.edges[i];
                if (ed->from != node_id) continue;

                int target = ed->to;
                EdgeType et = classify_edge(ed);
                edge_types_this_layer[et]++;

                double ig = compute_info_gain(e, target, et, fe.depth + 1);

                /* Skip nodes eliminated by hard constraints */
                if (ig < 0.0) {
                    if (e->verbose)
                        printf("  [constraint] Skipping node %d (eliminated by hard constraint)\n",
                               target);
                    continue;
                }

                double priority = compute_priority(e, et, ig,
                                                    e->field.nodes[target].novelty);

                ed->info_gain = ig;
                candidate_edges[candidate_count] = ed;
                candidate_scores[candidate_count] = priority;
                candidate_count++;
            }

            /* Sort candidates by score (simple insertion sort) */
            for (int i = 1; i < candidate_count; i++) {
                Edge *key_e = candidate_edges[i];
                double key_s = candidate_scores[i];
                int j = i - 1;
                while (j >= 0 && candidate_scores[j] < key_s) {
                    candidate_edges[j + 1] = candidate_edges[j];
                    candidate_scores[j + 1] = candidate_scores[j];
                    j--;
                }
                candidate_edges[j + 1] = key_e;
                candidate_scores[j + 1] = key_s;
            }

            /* Expand top-K candidates */
            int k = e->policy.max_edges_per_node;
            if (k > candidate_count) k = candidate_count;

            /* Adaptive K: reduce if graph is dense */
            double density = (double)e->field.edge_count / (double)(e->field.node_count + 1);
            if (density > 5.0) k = k * 0.6;
            if (k < 1 && candidate_count > 0) k = 1;
            if (k > candidate_count) k = candidate_count;  /* final safety */

            for (int c = 0; c < k; c++) {
                Edge *ed = candidate_edges[c];
                int target = ed->to;
                ed->traversed++;
                ed->weight = clampd(ed->weight + 0.01, 0.0, 1.0);

                /* Decide BFS vs DFS for this expansion */
                int is_bfs;
                if (ed->type == EDGE_CAUSAL || ed->type == EDGE_AUTHORITY
                    || ed->type == EDGE_CONTRADICTORY) {
                    /* Deep reasoning — DFS dive */
                    is_bfs = (e->policy.bfs_bias < 0.7) ? 0 : 1;
                } else {
                    /* Breadth discovery — BFS shell */
                    is_bfs = (e->policy.bfs_bias > 0.3) ? 1 : 0;
                }

                if (!e->field.nodes[target].visited) {
                    new_nodes_this_layer++;
                    total_new_nodes++;
                    e->field.nodes[target].novelty = 1.0;
                } else {
                    /* Decay novelty on re-visit */
                    e->field.nodes[target].novelty *= NOVELTY_DECAY;
                }

                if (fe.depth + 1 < e->policy.max_depth) {
                    frontier_push(&e->frontier, target,
                                  candidate_scores[c],
                                  fe.depth + 1, is_bfs, ed->type);
                }
            }

            /* Missing-link detection */
            EdgeType missing_types[4];
            int n_missing = detect_missing_links(e, node_id, missing_types, 4);
            if (n_missing > 0 && e->verbose) {
                printf("  [missing] node=%d has %d missing edge types:",
                       node_id, n_missing);
                for (int m = 0; m < n_missing; m++)
                    printf(" %s", edge_type_name(missing_types[m]));
                printf("\n");
            }

            /* Record in shadow graph */
            shadow_add(e, node_id, candidate_count < 2);
        }

        /* Update stability metrics */
        e->field.new_info_rate = new_nodes_this_layer;
        int distinct_types = 0;
        for (int t = 0; t < EDGE_TYPE_COUNT; t++)
            if (edge_types_this_layer[t] > 0) distinct_types++;
        e->field.edge_diversity = distinct_types;
        e->field.frontier_overlap = total_frontier > 0
            ? (repeated_frontier * 100 / total_frontier) : 0;

        if (e->verbose)
            printf("  [layer %d] new=%d  diversity=%d  overlap=%d%%  frontier=%d\n",
                   layer, new_nodes_this_layer, distinct_types,
                   e->field.frontier_overlap, e->frontier.count);

        /* Check stability */
        if (compute_stability(e, layer, &prev_new_info, &prev_diversity, &prev_novel)) {
            if (e->verbose)
                printf("  [stable] Stopping at layer %d (stability=%.3f)\n",
                       layer, e->field.stability);
            break;
        }

        layer++;
        e->field.depth_reached = layer;
    }

    if (e->verbose)
        printf("  Traversal complete: %d nodes expanded, %d new discovered, depth=%d\n\n",
               total_expanded, total_new_nodes, e->field.depth_reached);
}

/* ========================================================================== */
/*  SECTION 17 — Field synthesis                                             */
/* ========================================================================== */

/*
 * Compress raw traversal into:
 * - clusters (group nodes by domain + edge type patterns)
 * - contradictions (contradictory edges)
 * - dependency chains (causal chains)
 * - missing-link signals
 * - risk surfaces (high-authority unvisited nodes)
 */
typedef struct {
    int cluster_count;
    int contradiction_count;
    int missing_link_count;
    int chain_count;
    int risk_surface_count;
    double field_confidence;
} SynthesisResult;

static int assign_cluster(RFEngine *e, int node_id, int next_cluster) {
    Node *n = &e->field.nodes[node_id];
    if (n->cluster_id >= 0) return n->cluster_id;

    n->cluster_id = next_cluster;

    /* Cluster with nodes connected by structural + semantic edges */
    for (int i = 0; i < e->field.edge_count; i++) {
        Edge *ed = &e->field.edges[i];
        if (ed->type != EDGE_STRUCTURAL && ed->type != EDGE_SEMANTIC) continue;
        int neighbor = -1;
        if (ed->from == node_id) neighbor = ed->to;
        else if (ed->to == node_id) neighbor = ed->from;
        if (neighbor >= 0 && e->field.nodes[neighbor].cluster_id < 0)
            assign_cluster(e, neighbor, next_cluster);
    }

    return next_cluster;
}

SynthesisResult rf_synthesize(RFEngine *e) {
    SynthesisResult r = {0};
    int next_cluster = 0;

    /* Cluster assignment */
    for (int i = 0; i < e->field.node_count; i++) {
        if (e->field.nodes[i].visited && e->field.nodes[i].cluster_id < 0) {
            assign_cluster(e, i, next_cluster);
            next_cluster++;
        }
    }
    r.cluster_count = next_cluster;

    /* Count contradictions */
    for (int i = 0; i < e->field.edge_count; i++)
        if (e->field.edges[i].type == EDGE_CONTRADICTORY
            && e->field.nodes[e->field.edges[i].from].visited)
            r.contradiction_count++;

    /* Count missing links */
    for (int i = 0; i < e->field.node_count; i++) {
        if (!e->field.nodes[i].visited) continue;
        EdgeType missing[4];
        int n = detect_missing_links(e, i, missing, 4);
        r.missing_link_count += n;
    }

    /* Count causal chains (depth > 2 causal paths) */
    for (int i = 0; i < e->field.edge_count; i++) {
        if (e->field.edges[i].type != EDGE_CAUSAL) continue;
        int from = e->field.edges[i].from;
        int to = e->field.edges[i].to;
        if (!e->field.nodes[from].visited || !e->field.nodes[to].visited) continue;
        /* Check if 'to' also has outgoing causal edge = chain */
        for (int j = 0; j < e->field.edge_count; j++) {
            if (e->field.edges[j].type == EDGE_CAUSAL
                && e->field.edges[j].from == to) {
                r.chain_count++;
                break;
            }
        }
    }

    /* Risk surface — high-authority real nodes that are unvisited or have missing links */
    for (int i = 0; i < e->field.node_count; i++) {
        if (e->field.nodes[i].type == NODE_UNKNOWN) continue;
        if (e->field.nodes[i].authority > 0.7
            && (!e->field.nodes[i].visited
                || e->field.nodes[i].novelty > 0.5))
            r.risk_surface_count++;
    }

    /* Field confidence — based on coverage, contradictions, missing links.
     * Only count real (non-padding) nodes for coverage.
     * Missing links are expected in sparse graphs — use mild penalty. */
    int visited_count = 0;
    int real_node_count = 0;
    for (int i = 0; i < e->field.node_count; i++) {
        if (e->field.nodes[i].type == NODE_UNKNOWN) continue;
        real_node_count++;
        if (e->field.nodes[i].visited) visited_count++;
    }

    double coverage = (double)visited_count / (double)(real_node_count + 1);
    double contradiction_penalty = r.contradiction_count * 0.1;
    double missing_penalty = r.missing_link_count * 0.005;  /* very mild — missing is signal */
    if (missing_penalty > 0.15) missing_penalty = 0.15;      /* cap at 15% */
    r.field_confidence = clampd(coverage * 0.3 + 0.4  /* base confidence from traversal */
                                - contradiction_penalty - missing_penalty,
                                0.0, 1.0);

    if (e->verbose) {
        printf("=== Field Synthesis ===\n");
        printf("  Clusters:       %d\n", r.cluster_count);
        printf("  Contradictions: %d\n", r.contradiction_count);
        printf("  Missing links:  %d\n", r.missing_link_count);
        printf("  Causal chains:  %d\n", r.chain_count);
        printf("  Risk surface:   %d\n", r.risk_surface_count);
        printf("  Confidence:     %.3f\n\n", r.field_confidence);
    }

    return r;
}

/* ========================================================================== */
/*  SECTION 18 — Reasoning Compiler: Layer 1 — Field → Intent                */
/* ========================================================================== */

/*
 * Convert reasoning field into intent graph.
 * Nodes → intentions, edges → constraints, weights → confidence,
 * missing links → risk flags.
 */
void rf_compile_intents(RFEngine *e, SynthesisResult *syn) {
    IntentGraph *ig = &e->intents;
    ig->intent_count = 0;
    ig->field_confidence = syn->field_confidence;
    ig->missing_link_count = syn->missing_link_count;
    ig->contradiction_count = syn->contradiction_count;
    ig->cluster_count = syn->cluster_count;

    for (int i = 0; i < e->field.node_count && ig->intent_count < MAX_INTENTS; i++) {
        Node *n = &e->field.nodes[i];
        if (!n->visited) continue;

        Intent *it = &ig->intents[ig->intent_count];

        /* Determine intent based on node type + edge patterns */
        switch (n->type) {
            case NODE_ERROR:
                snprintf(it->intent, sizeof(it->intent),
                         "Resolve error: %s", n->name);
                it->dominant_edge = EDGE_CAUSAL;
                break;
            case NODE_LAW:
                snprintf(it->intent, sizeof(it->intent),
                         "Enforce law: %s", n->name);
                it->dominant_edge = EDGE_AUTHORITY;
                break;
            case NODE_PATTERN:
                snprintf(it->intent, sizeof(it->intent),
                         "Apply pattern: %s", n->name);
                it->dominant_edge = EDGE_BEHAVIORAL;
                break;
            case NODE_INCIDENT:
                snprintf(it->intent, sizeof(it->intent),
                         "Investigate incident: %s", n->name);
                it->dominant_edge = EDGE_HISTORICAL;
                break;
            case NODE_RULE:
                snprintf(it->intent, sizeof(it->intent),
                         "Evaluate rule: %s", n->name);
                it->dominant_edge = EDGE_AUTHORITY;
                break;
            case NODE_PROBLEM:
                snprintf(it->intent, sizeof(it->intent),
                         "Resolve problem: %s", n->name);
                it->dominant_edge = EDGE_CAUSAL;
                break;
            case NODE_CAUSE:
                snprintf(it->intent, sizeof(it->intent),
                         "Address cause: %s", n->name);
                it->dominant_edge = EDGE_CAUSAL;
                break;
            case NODE_FIX:
                snprintf(it->intent, sizeof(it->intent),
                         "Apply fix: %s", n->name);
                it->dominant_edge = EDGE_PREVENTATIVE;
                break;
            case NODE_PREVENTION:
                snprintf(it->intent, sizeof(it->intent),
                         "Implement prevention: %s", n->name);
                it->dominant_edge = EDGE_PREVENTATIVE;
                break;
            case NODE_SOLUTION:
                snprintf(it->intent, sizeof(it->intent),
                         "Deploy solution: %s", n->name);
                it->dominant_edge = EDGE_PREVENTATIVE;
                break;
            default:
                snprintf(it->intent, sizeof(it->intent),
                         "Examine: %s", n->name);
                it->dominant_edge = EDGE_STRUCTURAL;
        }

        it->source_node_id = i;
        it->confidence = clampd(n->authority * (1.0 - n->novelty * 0.3), 0.0, 1.0);

        /* Risk from missing links + contradictions near this node */
        int local_risk = 0;
        for (int ei = 0; ei < e->field.edge_count; ei++) {
            if (e->field.edges[ei].from == i
                && e->field.edges[ei].type == EDGE_CONTRADICTORY)
                local_risk++;
        }
        it->risk = (local_risk > 1) ? RISK_HIGH
                  : (local_risk > 0) ? RISK_MEDIUM
                  : (n->authority > 0.7) ? RISK_LOW : RISK_NONE;

        ig->intent_count++;
    }

    if (e->verbose) {
        printf("=== Intent Graph ===\n");
        printf("  %d intents from field (confidence=%.3f)\n",
               ig->intent_count, ig->field_confidence);
        for (int i = 0; i < ig->intent_count; i++)
            printf("  [%d] conf=%.2f risk=%s  %s\n",
                   i, ig->intents[i].confidence,
                   risk_name(ig->intents[i].risk),
                   ig->intents[i].intent);
        printf("\n");
    }
}

/* ========================================================================== */
/*  SECTION 19 — Reasoning Compiler: Layer 2 — Intent → Plan                 */
/* ========================================================================== */

/*
 * Convert intent graph into typed execution plan.
 * This is the IR — not SQL yet, but structured operations.
 */
void rf_compile_plan(RFEngine *e) {
    ExecutionPlan *p = &e->plan;
    p->op_count = 0;
    p->overall_confidence = e->intents.field_confidence;
    p->overall_risk = RISK_NONE;
    p->requires_transaction = 0;
    p->safety_gate_passed = 0;

    for (int i = 0; i < e->intents.intent_count && p->op_count < MAX_PLAN_OPS; i++) {
        Intent *it = &e->intents.intents[i];
        PlanOp *op = &p->ops[p->op_count];

        /* Determine action type from dominant edge */
        switch (it->dominant_edge) {
            case EDGE_CAUSAL:
                op->action_type = ACTION_MIGRATION;
                snprintf(op->operation, sizeof(op->operation),
                         "fix_causal_chain(target='%s')", it->intent);
                snprintf(op->rollback_op, sizeof(op->rollback_op),
                         "revert_fix(target='%s')", it->intent);
                op->requires_transaction = 1;
                break;
            case EDGE_AUTHORITY:
                op->action_type = ACTION_QUERY;
                snprintf(op->operation, sizeof(op->operation),
                         "validate_authority(target='%s')", it->intent);
                snprintf(op->rollback_op, sizeof(op->rollback_op),
                         "noop");
                op->requires_transaction = 0;
                break;
            case EDGE_PREVENTATIVE:
                op->action_type = ACTION_CODE;
                snprintf(op->operation, sizeof(op->operation),
                         "apply_prevention(target='%s')", it->intent);
                snprintf(op->rollback_op, sizeof(op->rollback_op),
                         "revert_prevention(target='%s')", it->intent);
                op->requires_transaction = 1;
                break;
            case EDGE_HISTORICAL:
                op->action_type = ACTION_QUERY;
                snprintf(op->operation, sizeof(op->operation),
                         "lookup_history(target='%s')", it->intent);
                snprintf(op->rollback_op, sizeof(op->rollback_op),
                         "noop");
                op->requires_transaction = 0;
                break;
            case EDGE_MISSING:
                op->action_type = ACTION_SYSTEM;
                snprintf(op->operation, sizeof(op->operation),
                         "create_missing_link(target='%s')", it->intent);
                snprintf(op->rollback_op, sizeof(op->rollback_op),
                         "delete_missing_link(target='%s')", it->intent);
                op->requires_transaction = 1;
                break;
            default:
                op->action_type = ACTION_QUERY;
                snprintf(op->operation, sizeof(op->operation),
                         "inspect(target='%s')", it->intent);
                snprintf(op->rollback_op, sizeof(op->rollback_op),
                         "noop");
                op->requires_transaction = 0;
        }

        snprintf(op->target, sizeof(op->target), "node_%d", it->source_node_id);
        op->confidence = it->confidence;
        op->risk = it->risk;
        op->requires_dry_run = (it->confidence < 0.9 || it->risk >= RISK_HIGH);

        if (op->risk > p->overall_risk) p->overall_risk = op->risk;
        if (op->requires_transaction) p->requires_transaction = 1;

        p->op_count++;
    }

    if (e->verbose) {
        printf("=== Execution Plan (IR) ===\n");
        printf("  %d operations  confidence=%.3f  risk=%s  transaction=%s\n",
               p->op_count, p->overall_confidence,
               risk_name(p->overall_risk),
               p->requires_transaction ? "yes" : "no");
        for (int i = 0; i < p->op_count; i++)
            printf("  [%d] %s  conf=%.2f  risk=%s  dry_run=%s  %s\n",
                   i, action_name(p->ops[i].action_type),
                   p->ops[i].confidence, risk_name(p->ops[i].risk),
                   p->ops[i].requires_dry_run ? "yes" : "no",
                   p->ops[i].operation);
        printf("\n");
    }
}

/* ========================================================================== */
/*  SECTION 20 — Safety gates                                                 */
/* ========================================================================== */

/*
 * Gate 1 — Structural safety: schema validation, type checks, FK integrity
 * Gate 2 — Semantic safety: does action match intent? violates laws?
 * Gate 3 — Reversibility safety: can every action be undone?
 *
 * Returns 1 if all gates pass, 0 if blocked.
 */
int rf_safety_check(RFEngine *e) {
    ExecutionPlan *p = &e->plan;

    /* Gate 1: Structural safety
     * - Every operation must have a valid action type
     * - Every operation must have a target
     * - Transaction required for any write op
     */
    for (int i = 0; i < p->op_count; i++) {
        PlanOp *op = &p->ops[i];
        if (op->action_type == ACTION_NONE) {
            if (e->verbose) printf("  [safety] Gate 1 FAIL: op %d has no action type\n", i);
            return 0;
        }
        if (strlen(op->target) == 0) {
            if (e->verbose) printf("  [safety] Gate 1 FAIL: op %d has no target\n", i);
            return 0;
        }
        if ((op->action_type == ACTION_MIGRATION || op->action_type == ACTION_CODE)
            && !op->requires_transaction) {
            if (e->verbose) printf("  [safety] Gate 1 FAIL: write op %d lacks transaction\n", i);
            return 0;
        }
    }
    if (e->verbose) printf("  [safety] Gate 1 (structural): PASS\n");

    /* Gate 2: Semantic safety
     * - Overall confidence must be above threshold
     * - High-risk plans require dry run
     * - Contradictions in field lower confidence
     */
    if (p->overall_confidence < 0.15) {
        if (e->verbose) printf("  [safety] Gate 2 FAIL: confidence too low (%.3f)\n",
                               p->overall_confidence);
        return 0;
    }
    if (e->intents.contradiction_count > 3) {
        if (e->verbose) printf("  [safety] Gate 2 FAIL: too many contradictions (%d)\n",
                               e->intents.contradiction_count);
        return 0;
    }
    if (p->overall_risk >= RISK_HIGH && !p->requires_transaction) {
        if (e->verbose) printf("  [safety] Gate 2 FAIL: high risk without transaction\n");
        return 0;
    }
    if (e->verbose) printf("  [safety] Gate 2 (semantic): PASS\n");

    /* Gate 3: Reversibility safety
     * - Every operation must have a non-empty rollback
     * - At least one operation must be reversible (not all "noop")
     */
    int reversible_count = 0;
    for (int i = 0; i < p->op_count; i++) {
        PlanOp *op = &p->ops[i];
        if (strlen(op->rollback_op) == 0 || strcmp(op->rollback_op, "noop") == 0)
            continue;
        reversible_count++;
    }
    if (p->requires_transaction && reversible_count == 0) {
        if (e->verbose) printf("  [safety] Gate 3 FAIL: transaction plan with no reversible ops\n");
        return 0;
    }
    if (e->verbose) printf("  [safety] Gate 3 (reversibility): PASS (%d reversible ops)\n\n",
                           reversible_count);

    p->safety_gate_passed = 1;
    return 1;
}

/* ========================================================================== */
/*  SECTION 21 — Reversible Execution Ledger                                 */
/* ========================================================================== */

void rf_ledger_begin_transaction(RFEngine *e) {
    e->ledger.current_transaction++;
    e->ledger.transaction_depth++;
    if (e->verbose)
        printf("  [ledger] BEGIN TRANSACTION %d\n", e->ledger.current_transaction);
}

int rf_ledger_log(RFEngine *e, int plan_op_index, ActionType action_type,
                  const char *action, const char *inverse_action) {
    if (e->ledger.count >= MAX_LEDGER) return -1;
    LedgerEntry *le = &e->ledger.entries[e->ledger.count];
    le->id = e->ledger.count;
    le->plan_op_index = plan_op_index;
    le->action_type = action_type;
    strncpy(le->action, action, sizeof(le->action) - 1);
    strncpy(le->inverse_action, inverse_action, sizeof(le->inverse_action) - 1);
    le->executed = 0;
    le->rolled_back = 0;
    le->execution_time_ms = 0.0;
    timestamp_now(le->timestamp, sizeof(le->timestamp));
    le->transaction_id = e->ledger.current_transaction;
    e->ledger.count++;
    return le->id;
}

void rf_ledger_mark_executed(RFEngine *e, int entry_id, double time_ms) {
    if (entry_id < 0 || entry_id >= e->ledger.count) return;
    e->ledger.entries[entry_id].executed = 1;
    e->ledger.entries[entry_id].execution_time_ms = time_ms;
}

/*
 * Rollback the current transaction by executing inverse actions
 * in reverse order.
 */
void rf_ledger_rollback(RFEngine *e) {
    if (e->ledger.transaction_depth == 0) return;
    int txn = e->ledger.current_transaction;

    if (e->verbose)
        printf("  [ledger] ROLLBACK TRANSACTION %d\n", txn);

    /* Walk backwards through this transaction's entries */
    for (int i = e->ledger.count - 1; i >= 0; i--) {
        LedgerEntry *le = &e->ledger.entries[i];
        if (le->transaction_id != txn) continue;
        if (!le->executed) continue;
        if (le->rolled_back) continue;
        if (strcmp(le->inverse_action, "noop") == 0) continue;

        if (e->verbose)
            printf("    [rollback] exec: %s\n", le->inverse_action);

        le->rolled_back = 1;
    }

    e->ledger.transaction_depth--;
}

void rf_ledger_commit(RFEngine *e) {
    if (e->ledger.transaction_depth == 0) return;
    if (e->verbose)
        printf("  [ledger] COMMIT TRANSACTION %d\n", e->ledger.current_transaction);
    e->ledger.transaction_depth--;
}

/*
 * Replay the ledger from the beginning (for audit / recovery).
 */
void rf_ledger_replay(RFEngine *e) {
    if (e->verbose)
        printf("\n=== Ledger Replay ===\n");

    for (int i = 0; i < e->ledger.count; i++) {
        LedgerEntry *le = &e->ledger.entries[i];
        printf("  [%03d] txn=%d  %s  %s  exec=%d  rollback=%d  %.1fms\n",
               le->id, le->transaction_id, le->timestamp,
               le->action, le->executed, le->rolled_back,
               le->execution_time_ms);
    }
    printf("\n");
}

/* ========================================================================== */
/*  SECTION 22 — Execution engine                                            */
/* ========================================================================== */

/*
 * Execute the plan with full safety + ledger + rollback.
 * Returns reward signal for the learning loop.
 */
double rf_execute(RFEngine *e) {
    ExecutionPlan *p = &e->plan;

    if (!p->safety_gate_passed) {
        if (e->verbose) printf("  [exec] BLOCKED: safety gates not passed\n");
        return -1.0;
    }

    if (p->op_count == 0) {
        if (e->verbose) printf("  [exec] No operations to execute\n");
        return 0.0;
    }

    /* Begin transaction if needed */
    if (p->requires_transaction)
        rf_ledger_begin_transaction(e);

    double total_reward = 0.0;
    int success_count = 0;
    int fail_count = 0;

    if (e->verbose)
        printf("=== Execution ===\n");

    for (int i = 0; i < p->op_count; i++) {
        PlanOp *op = &p->ops[i];

        /* Dry run if required */
        if (op->requires_dry_run && e->verbose)
            printf("  [dry-run] %s\n", op->operation);

        /* Log to ledger */
        int ledger_id = rf_ledger_log(e, i, op->action_type,
                                       op->operation, op->rollback_op);

        /* Simulate execution (in real system, this calls the DB/code/system) */
        clock_t start = clock();

        /* Execution result: success probability based on confidence */
        double roll = (double)rand() / RAND_MAX;
        int success = (roll < op->confidence) ? 1 : 0;

        clock_t end = clock();
        double time_ms = (double)(end - start) / (CLOCKS_PER_SEC / 1000.0);

        rf_ledger_mark_executed(e, ledger_id, time_ms);

        if (success) {
            success_count++;
            total_reward += op->confidence;
            if (e->verbose)
                printf("  [exec %d] OK  %s  (%.1fms)\n", i, op->operation, time_ms);
        } else {
            fail_count++;
            total_reward -= 0.3;  /* failure penalty */
            if (e->verbose)
                printf("  [exec %d] FAIL  %s  (rolled back)\n", i, op->operation);

            /* Rollback this transaction on failure */
            if (p->requires_transaction) {
                rf_ledger_rollback(e);
                break;
            }
        }

        /* Track edge contribution for learning */
        EdgeType dominant = e->intents.intents[i].dominant_edge;
        e->learning.edge_total_count[dominant]++;
        if (success) e->learning.edge_success_count[dominant]++;
    }

    /* Commit if all ops succeeded and transaction was open */
    if (p->requires_transaction && fail_count == 0)
        rf_ledger_commit(e);

    /* Compute final reward */
    double avg_reward = (p->op_count > 0) ? total_reward / p->op_count : 0.0;

    /* Surprise = unexpected failures (missing edges signal) */
    double expected = p->overall_confidence;
    double surprise = clampd(expected - avg_reward, 0.0, 1.0);

    e->learning.actual_reward = avg_reward;
    e->learning.expected_reward = expected;
    e->learning.surprise = surprise;
    e->learning.total_runs++;

    if (e->verbose)
        printf("  Result: %d ok, %d fail, reward=%.3f, surprise=%.3f\n\n",
               success_count, fail_count, avg_reward, surprise);

    return avg_reward;
}

/* ========================================================================== */
/*  SECTION 23 — Learning system: edge weight updates                        */
/* ========================================================================== */

/*
 * Δw(edge_type) = α * (reward - expected_reward) * contribution_score(edge)
 *
 * If causal edges led to success → strengthen causal weight
 * If semantic edges caused noise → weaken semantic weight
 * If missing-link edges revealed critical structure → boost heavily
 */
void rf_learn_edges(RFEngine *e) {
    double reward = e->learning.actual_reward;
    double expected = e->learning.expected_reward;
    double delta = reward - expected;

    if (e->verbose)
        printf("=== Edge Weight Learning ===\n");

    for (int t = 0; t < EDGE_TYPE_COUNT; t++) {
        double total = e->learning.edge_total_count[t];
        double success = e->learning.edge_success_count[t];

        if (total < 1) continue;

        double success_rate = success / total;
        double contribution = success_rate;  /* how much this edge type contributed */

        /* Weight update */
        double dw = LEARNING_ALPHA * delta * contribution;

        /* Missing edges get extra boost from surprise */
        if (t == EDGE_MISSING && e->learning.surprise > 0.2)
            dw += LEARNING_ALPHA * e->learning.surprise * 0.5;

        /* Contradictory edges get boosted when they prevent bad actions */
        if (t == EDGE_CONTRADICTORY && delta < 0)
            dw += LEARNING_ALPHA * fabs(delta) * 0.3;

        e->learning.edge_weight_deltas[t] = dw;
        e->policy.edge_weights[t] = clampd(e->policy.edge_weights[t] + dw, 0.05, 1.0);

        if (e->verbose && fabs(dw) > 0.001)
            printf("  %s: w=%.3f → %.3f (Δ=%+.4f, success_rate=%.2f)\n",
                   edge_type_name(t),
                   e->policy.edge_weights[t] - dw,
                   e->policy.edge_weights[t], dw, success_rate);
    }

    if (e->verbose) printf("\n");
}

/* ========================================================================== */
/*  SECTION 24 — Policy refinement                                           */
/* ========================================================================== */

/*
 * Adjust traversal policy based on outcomes.
 *
 * A. exploration vs exploitation
 * B. BFS vs DFS bias
 * C. pruning aggressiveness
 * D. missing-link sensitivity
 */
void rf_learn_policy(RFEngine *e) {
    double reward = e->learning.actual_reward;
    double expected = e->learning.expected_reward;
    double delta = reward - expected;

    if (e->verbose)
        printf("=== Policy Refinement ===\n");

    /* If deep DFS caused failures → reduce DFS bias (more BFS) */
    /* If missing-link detection improves outcomes → increase sensitivity */
    if (delta < 0) {
        /* Failure — shift toward safer exploration */
        e->policy.bfs_bias = clampd(e->policy.bfs_bias + 0.05, 0.2, 0.9);
        e->policy.pruning_aggression = clampd(e->policy.pruning_aggression + 0.05,
                                               0.2, 0.9);
        e->policy.exploration = clampd(e->policy.exploration - 0.03, 0.1, 0.9);
        if (e->verbose)
            printf("  Failure detected → safer policy (BFS+%.2f prune+%.2f)\n",
                   e->policy.bfs_bias, e->policy.pruning_aggression);
    } else if (delta > 0.1) {
        /* Success — can afford deeper exploration */
        e->policy.bfs_bias = clampd(e->policy.bfs_bias - 0.03, 0.2, 0.9);
        e->policy.exploration = clampd(e->policy.exploration + 0.02, 0.1, 0.9);
        e->policy.missing_sensitivity = clampd(
            e->policy.missing_sensitivity + 0.03, 0.3, 1.0);
        if (e->verbose)
            printf("  Success detected → deeper policy (DFS+%.2f explore+%.2f missing+%.2f)\n",
                   1.0 - e->policy.bfs_bias,
                   e->policy.exploration, e->policy.missing_sensitivity);
    }

    /* Surprise increases missing-link sensitivity */
    if (e->learning.surprise > 0.3) {
        e->policy.missing_sensitivity = clampd(
            e->policy.missing_sensitivity + 0.05, 0.3, 1.0);
        if (e->verbose)
            printf("  High surprise (%.2f) → missing sensitivity +%.2f\n",
                   e->learning.surprise, e->policy.missing_sensitivity);
    }

    if (e->verbose) printf("\n");
}

/* ========================================================================== */
/*  SECTION 25 — Automatic edge type discovery                               */
/* ========================================================================== */

/*
 * Detect unexplained co-occurrences that might indicate new edge types.
 *
 * Step 1: Observe nodes that co-occur without known edge types
 * Step 2: Cluster relationship signatures
 * Step 3: Promote to edge type if stable (recurrence > threshold)
 *
 * In this implementation we track co-occurrence signals.
 * A full implementation would create new EdgeType entries dynamically.
 */
void rf_discover_edges(RFEngine *e) {
    if (e->verbose)
        printf("=== Edge Type Discovery ===\n");

    /* Look for node pairs that co-occur in the same cluster
     * but have no explicit edge between them */
    int discovered = 0;

    for (int i = 0; i < e->field.node_count; i++) {
        if (!e->field.nodes[i].visited) continue;
        for (int j = i + 1; j < e->field.node_count; j++) {
            if (!e->field.nodes[j].visited) continue;
            if (e->field.nodes[i].cluster_id != e->field.nodes[j].cluster_id) continue;

            /* Check if explicit edge exists */
            int has_edge = 0;
            for (int k = 0; k < e->field.edge_count; k++) {
                Edge *ed = &e->field.edges[k];
                if ((ed->from == i && ed->to == j)
                    || (ed->from == j && ed->to == i)) {
                    has_edge = 1;
                    break;
                }
            }

            if (!has_edge) {
                /* Unknown relationship — co-occurrence without edge */
                /* Determine which edge type this might be */
                EdgeType guess = EDGE_MISSING;
                if (e->field.nodes[i].type == e->field.nodes[j].type)
                    guess = EDGE_SIMILARITY;
                else if (e->field.nodes[i].type == NODE_LAW
                         && e->field.nodes[j].type == NODE_ERROR)
                    guess = EDGE_AUTHORITY;

                e->learning.unknown_co_occurrence[guess]++;

                /* Promote if recurrence is high enough */
                if (e->learning.unknown_co_occurrence[guess] > 5) {
                    if (e->verbose)
                        printf("  [discover] Potential new edge type: %s "
                               "(co-occurrence=%d, nodes %d↔%d)\n",
                               edge_type_name(guess),
                               e->learning.unknown_co_occurrence[guess],
                               i, j);
                    discovered++;
                }
            }
        }
    }

    if (e->verbose) {
        if (discovered == 0)
            printf("  No new edge types detected this run\n");
        else
            printf("  %d potential new edge types detected\n", discovered);
        printf("\n");
    }
}

/* ========================================================================== */
/*  SECTION 25b — Constraint-Traversal feedback loop                         */
/* ========================================================================== */

/* Forward declarations — defined in Section 28b */
static void load_constraints_from_db(RFEngine *e);
static void demo_constraint_reduction(RFEngine *e);
/*
 * The feedback loop: traversal discovers structure, which generates
 * new constraints, which guide further traversal.
 *
 *   traverse → discover missing links → generate constraints
 *            → apply constraints → reweight hypotheses
 *            → traverse again (guided by new probabilities)
 *            → repeat until convergence
 *
 * This is the unified loop that makes RF-TA a constraint reduction engine.
 */

/*
 * Generate constraints from traversal results.
 * Called after each traversal+synthesis cycle.
 *
 * What traversal discovers:
 *   - Visited nodes → these are "interesting" → boost their hypothesis probability
 *   - Missing links → these are "uncertain" → add edge_lacks constraints
 *   - Causal chains → these are "connected" → add edge_has constraints
 *   - Clusters → nodes in same cluster get neighbor constraints
 *
 * Returns the number of new constraints generated.
 */
static int generate_constraints_from_traversal(RFEngine *e) {
    if (e->constraints.hypothesis_count == 0) return 0;

    int new_constraints = 0;
    ConstraintEngine *ce = &e->constraints;

    /* 1. Boost visited nodes: they passed the traversal's implicit test.
     *    We don't add a new constraint — we directly boost their raw_score.
     *    High-value nodes (on attack paths) get a bigger boost. */
    int visited_count = 0;
    for (int i = 0; i < ce->hypothesis_count; i++) {
        if (ce->hypotheses[i].eliminated) continue;
        int nid = ce->hypotheses[i].node_id;
        if (e->field.nodes[nid].visited) {
            double boost = 2.0;  /* traversal confirmed relevance */
            if (e->field.nodes[nid].high_value) boost = 3.0;  /* high-value = bigger boost */
            if (e->field.nodes[nid].has_attack_path) boost = 3.5;  /* attack path = biggest */
            ce->hypotheses[i].raw_score *= boost;
            visited_count++;
        }
    }

    if (e->verbose && visited_count > 0)
        printf("  [feedback] Boosted %d visited nodes in hypothesis space\n",
               visited_count);

    /* 2. For nodes with missing causal links, add soft edge_lacks constraint.
     *    But only if we haven't already added one for this node (deduplicate). */
    for (int i = 0; i < e->field.node_count && new_constraints < 10; i++) {
        if (!e->field.nodes[i].visited) continue;
        EdgeType missing[4];
        int n = detect_missing_links(e, i, missing, 4);
        if (n > 0) {
            for (int m = 0; m < n && new_constraints < 10; m++) {
                if (missing[m] == EDGE_CAUSAL) {
                    /* Check if we already have this exact constraint */
                    char expected_desc[128];
                    snprintf(expected_desc, sizeof(expected_desc),
                             "traversal feedback: node %d lacks causal links", i);
                    int already_exists = 0;
                    for (int c = 0; c < e->constraints.constraint_count; c++) {
                        if (e->constraints.constraints[c].type == C_EDGE_LACKS
                            && e->constraints.constraints[c].int_value == EDGE_CAUSAL
                            && strcmp(e->constraints.constraints[c].description,
                                     expected_desc) == 0) {
                            already_exists = 1;
                            break;
                        }
                    }
                    if (already_exists) continue;

                    rf_constraint_edge_lacks(e, EDGE_CAUSAL, 0.15, expected_desc);
                    e->constraints.constraints[e->constraints.constraint_count - 1].hard = 0;
                    new_constraints++;
                }
            }
        }
    }

    /* 3. Renormalize after boosting visited nodes */
    double total_score = 0.0;
    for (int i = 0; i < ce->hypothesis_count; i++) {
        if (ce->hypotheses[i].eliminated) continue;
        total_score += ce->hypotheses[i].raw_score;
    }
    if (total_score > 0) {
        for (int i = 0; i < ce->hypothesis_count; i++) {
            if (ce->hypotheses[i].eliminated) continue;
            ce->hypotheses[i].probability = ce->hypotheses[i].raw_score / total_score;
        }
    }

    /* Recompute entropy and convergence */
    ce->entropy = 0.0;
    double max_prob = 0.0;
    for (int i = 0; i < ce->hypothesis_count; i++) {
        if (ce->hypotheses[i].eliminated || ce->hypotheses[i].probability <= 0)
            continue;
        ce->entropy -= ce->hypotheses[i].probability
                      * log2(ce->hypotheses[i].probability);
        if (ce->hypotheses[i].probability > max_prob)
            max_prob = ce->hypotheses[i].probability;
    }
    ce->convergence = max_prob;
    ce->converged = (max_prob >= CONVERGENCE_THRESH) ? 1 : 0;

    if (e->verbose)
        printf("  [feedback] Generated %d new constraints, entropy=%.3f, convergence=%.3f\n",
               new_constraints, ce->entropy, ce->convergence);

    return new_constraints;
}

/*
 * The unified convergence loop:
 *
 *   1. Initialize hypotheses (uniform prior)
 *   2. Load constraints from DB
 *   3. Apply constraints
 *   4. Traverse (guided by constraint probabilities)
 *   5. Synthesize (discover missing links, clusters)
 *   6. Generate new constraints from traversal results
 *   7. Apply new constraints
 *   8. Repeat 4-7 until convergence or max iterations
 *
 * This is the core of "reasoning = reducing uncertainty by applying
 * accumulated constraints until the remaining action is sufficiently
 * justified."
 */
double rf_convergence_loop(RFEngine *e, int max_iterations) {
    printf("\n");
    printf("╔══════════════════════════════════════════════════════════════╗\n");
    printf("║  CONSTRAINT-TRAVERSAL CONVERGENCE LOOP                      ║\n");
    printf("║  traverse → constrain → traverse → converge                 ║\n");
    printf("╚══════════════════════════════════════════════════════════════╝\n\n");

    /* Step 1: Initialize hypothesis space */
    printf("Step 1: Initialize hypothesis space (uniform prior over all nodes)\n");
    rf_constraints_init_hypotheses(e);
    printf("  %d hypotheses, entropy=%.3f bits\n\n",
           e->constraints.hypothesis_count, e->constraints.entropy);

    /* Step 2: Load constraints from database */
    printf("Step 2: Load constraints from `laws` database\n");
    load_constraints_from_db(e);
    printf("  %d constraints loaded\n\n", e->constraints.constraint_count);

    double last_convergence = 0.0;
    int converged = 0;

    for (int iter = 0; iter < max_iterations; iter++) {
        printf("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
        printf("  ITERATION %d / %d\n", iter + 1, max_iterations);
        printf("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n");

        /* Step 3: Apply any pending constraints */
        printf("  → Applying constraints...\n");
        int applied = 0;
        for (int i = 0; i < e->constraints.constraint_count; i++) {
            if (e->constraints.constraints[i].active) continue;
            rf_constraints_apply(e, i);
            applied++;
            if (e->constraints.converged) break;
        }
        printf("  Applied %d constraints, entropy=%.3f, convergence=%.3f\n\n",
               applied, e->constraints.entropy, e->constraints.convergence);

        if (e->constraints.converged) {
            printf("  → CONVERGED after constraint application\n\n");
            converged = 1;
            break;
        }

        /* Step 4: Traverse (guided by constraint probabilities) */
        printf("  → Traversing reasoning field (constraint-guided)...\n");
        rf_traverse(e);

        /* Step 5: Synthesize (results feed into constraint generation) */
        (void)rf_synthesize(e);  /* synthesis updates field state used by feedback */

        /* Step 6: Generate new constraints from traversal */
        printf("  → Generating constraints from traversal results...\n");
        int new_c = generate_constraints_from_traversal(e);
        printf("  %d new constraints, entropy=%.3f, convergence=%.3f\n\n",
               new_c, e->constraints.entropy, e->constraints.convergence);

        /* Check convergence */
        double delta = e->constraints.convergence - last_convergence;
        printf("  Convergence delta: %.4f (was %.3f, now %.3f)\n\n",
               delta, last_convergence, e->constraints.convergence);

        if (e->constraints.converged) {
            printf("  → CONVERGED: top candidate has %.1f%% belief mass\n\n",
                   e->constraints.convergence * 100.0);
            converged = 1;
            break;
        }

        if (delta < 0.001 && iter > 0) {
            printf("  → Plateau detected (delta < 0.001). Stopping.\n\n");
            break;
        }

        last_convergence = e->constraints.convergence;

        /* Reset traversal state for next iteration */
        for (int i = 0; i < e->field.node_count; i++) {
            e->field.nodes[i].visited = 0;
            e->field.nodes[i].novelty = 1.0;
            e->field.nodes[i].depth = -1;
            e->field.nodes[i].cluster_id = -1;
        }
        e->field.stability = 0.0;
        e->field.depth_reached = 0;
        e->frontier.count = 0;
        e->shadow.count = 0;
        rf_set_anchor(e, e->field.anchor_id);
    }

    /* Final state */
    printf("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
    printf("  CONVERGENCE RESULT\n");
    printf("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n");

    rf_constraints_print_state(e);

    int ids[5];
    double probs[5];
    int n = rf_constraints_top_candidates(e, ids, probs, 5);

    printf("  Final ranking:\n");
    for (int i = 0; i < n; i++)
        printf("    [%d] p=%.3f  %s\n", i, probs[i],
               e->field.nodes[ids[i]].name);
    printf("\n");

    if (n > 0) {
        printf("  → The reasoning field has %s onto '%s' as the most\n",
               converged ? "converged" : "settled",
               e->field.nodes[ids[0]].name);
        printf("    justified candidate (p=%.3f, entropy=%.3f bits).\n\n",
               probs[0], e->constraints.entropy);
        printf("    This is not 'solving' — it is probability distribution\n");
        printf("    collapse under accumulated constraints.\n\n");

        /* Mark top candidates as owned (BloodHound session state) */
        for (int i = 0; i < n && i < 3; i++) {
            if (probs[i] > 0.15) {
                rf_own_node(e, ids[i]);
            }
        }
        e->session_confidence = e->constraints.convergence;
        printf("  Session state: %d nodes owned, confidence=%.3f\n\n",
               e->owned_count, e->session_confidence);
    }

    return e->constraints.convergence;
}

/* ========================================================================== */
/*  SECTION 26 — Full pipeline (single run)                                  */
/* ========================================================================== */

/*
 * Complete RF-TA v2 run:
 *   1. Build Reasoning Field (traverse)
 *   2. Synthesize field
 *   3. Compile to intents
 *   4. Compile to plan
 *   5. Safety check
 *   6. Execute (with ledger)
 *   7. Learn (edge weights + policy)
 *   8. Discover new edges
 */
double rf_run(RFEngine *e) {
    /* Step 1: Traverse */
    rf_traverse(e);

    /* Step 2: Synthesize */
    SynthesisResult syn = rf_synthesize(e);

    /* Step 3: Compile intents */
    rf_compile_intents(e, &syn);

    /* Step 4: Compile plan */
    rf_compile_plan(e);

    /* Step 5: Safety gates */
    if (!rf_safety_check(e)) {
        if (e->verbose)
            printf("  [run] Safety gates blocked execution. Downgrading to simulation.\n\n");
        /* Still learn from what we discovered */
        rf_learn_edges(e);
        rf_learn_policy(e);
        return 0.0;
    }

    /* Step 6: Execute */
    double reward = rf_execute(e);

    /* Step 7: Learn */
    rf_learn_edges(e);
    rf_learn_policy(e);

    /* Step 8: Discover */
    rf_discover_edges(e);

    return reward;
}

/* ========================================================================== */
/*  SECTION 27 — Status / dump functions                                     */
/* ========================================================================== */

void rf_print_policy(RFEngine *e) {
    printf("Policy:\n");
    printf("  BFS bias:       %.2f\n", e->policy.bfs_bias);
    printf("  Exploration:    %.2f\n", e->policy.exploration);
    printf("  Pruning:        %.2f\n", e->policy.pruning_aggression);
    printf("  Missing sens:   %.2f\n", e->policy.missing_sensitivity);
    printf("  Max depth:      %d\n", e->policy.max_depth);
    printf("  Edge weights:\n");
    for (int t = 0; t < EDGE_TYPE_COUNT; t++)
        printf("    %-16s  %.3f\n", edge_type_name(t), e->policy.edge_weights[t]);
}

void rf_print_ledger(RFEngine *e) {
    rf_ledger_replay(e);
}

void rf_print_field_summary(RFEngine *e) {
    int visited = 0;
    for (int i = 0; i < e->field.node_count; i++)
        if (e->field.nodes[i].visited) visited++;

    printf("Field: %d nodes (%d visited), %d edges, depth=%d, stability=%.3f\n",
           e->field.node_count, visited, e->field.edge_count,
           e->field.depth_reached, e->field.stability);
}

/* ========================================================================== */
/*  SECTION 28 — MySQL loader: real data from `laws` database                */
/* ========================================================================== */

/*
 * Node ID mapping:
 *   The `laws` DB uses per-table IDs (law.id=1, error.id=1, etc.)
 *   We map them into a single flat node space:
 *     law nodes:       0 .. 999
 *     error nodes:  1000 .. 1999
 *     pattern:      2000 .. 2999
 *     problem:      3000 .. 3999
 *     cause:        4000 .. 4999
 *     fix:          5000 .. 5999
 *     prevention:   6000 .. 6999
 *     solution:     7000 .. 7999
 */
#define ID_BASE_LAW        0
#define ID_BASE_ERROR   1000
#define ID_BASE_PATTERN 2000
#define ID_BASE_PROBLEM 3000
#define ID_BASE_CAUSE   4000
#define ID_BASE_FIX     5000
#define ID_BASE_PREVENT 6000
#define ID_BASE_SOLUTION 7000

static NodeType table_node_type(const char *table) {
    if (strcmp(table, "law") == 0)        return NODE_LAW;
    if (strcmp(table, "error") == 0)      return NODE_ERROR;
    if (strcmp(table, "pattern") == 0)    return NODE_PATTERN;
    if (strcmp(table, "problem") == 0)    return NODE_PROBLEM;
    if (strcmp(table, "cause") == 0)      return NODE_CAUSE;
    if (strcmp(table, "fix") == 0)        return NODE_FIX;
    if (strcmp(table, "prevention") == 0) return NODE_PREVENTION;
    if (strcmp(table, "solution") == 0)   return NODE_SOLUTION;
    return NODE_UNKNOWN;
}

static int table_id_base(const char *table) {
    if (strcmp(table, "law") == 0)        return ID_BASE_LAW;
    if (strcmp(table, "error") == 0)      return ID_BASE_ERROR;
    if (strcmp(table, "pattern") == 0)    return ID_BASE_PATTERN;
    if (strcmp(table, "problem") == 0)    return ID_BASE_PROBLEM;
    if (strcmp(table, "cause") == 0)      return ID_BASE_CAUSE;
    if (strcmp(table, "fix") == 0)        return ID_BASE_FIX;
    if (strcmp(table, "prevention") == 0) return ID_BASE_PREVENT;
    if (strcmp(table, "solution") == 0)   return ID_BASE_SOLUTION;
    return -1;
}

static int table_id_from_link(const char *link_type) {
    if (strcmp(link_type, "law") == 0)        return ID_BASE_LAW;
    if (strcmp(link_type, "error") == 0)      return ID_BASE_ERROR;
    if (strcmp(link_type, "pattern") == 0)    return ID_BASE_PATTERN;
    if (strcmp(link_type, "problem") == 0)    return ID_BASE_PROBLEM;
    if (strcmp(link_type, "cause") == 0)      return ID_BASE_CAUSE;
    if (strcmp(link_type, "fix") == 0)        return ID_BASE_FIX;
    if (strcmp(link_type, "prevention") == 0) return ID_BASE_PREVENT;
    if (strcmp(link_type, "solution") == 0)   return ID_BASE_SOLUTION;
    if (strcmp(link_type, "fact") == 0)       return ID_BASE_PROBLEM;  /* no fact table */
    if (strcmp(link_type, "rule") == 0)       return ID_BASE_FIX;      /* no rule table */
    if (strcmp(link_type, "answer") == 0)     return ID_BASE_SOLUTION;
    if (strcmp(link_type, "evidence") == 0)   return ID_BASE_CAUSE;
    return -1;
}

/*
 * Map link_type from the `link` table to RF-TA EdgeType.
 */
static EdgeType link_type_to_edge(const char *link_type) {
    if (strcmp(link_type, "cause") == 0)       return EDGE_CAUSAL;
    if (strcmp(link_type, "fix") == 0)         return EDGE_PREVENTATIVE;
    if (strcmp(link_type, "prevention") == 0)  return EDGE_PREVENTATIVE;
    if (strcmp(link_type, "solution") == 0)    return EDGE_PREVENTATIVE;
    if (strcmp(link_type, "error") == 0)       return EDGE_CAUSAL;
    if (strcmp(link_type, "problem") == 0)     return EDGE_CAUSAL;
    if (strcmp(link_type, "evidence") == 0)    return EDGE_HISTORICAL;
    if (strcmp(link_type, "fact") == 0)        return EDGE_HISTORICAL;
    if (strcmp(link_type, "rule") == 0)        return EDGE_AUTHORITY;
    if (strcmp(link_type, "answer") == 0)      return EDGE_SEMANTIC;
    if (strcmp(link_type, "law") == 0)         return EDGE_AUTHORITY;
    if (strcmp(link_type, "pattern") == 0)     return EDGE_BEHAVIORAL;
    /* New link types from entity_link */
    if (strcmp(link_type, "composed_of") == 0)       return EDGE_STRUCTURAL;
    if (strcmp(link_type, "organizes") == 0)         return EDGE_AUTHORITY;
    if (strcmp(link_type, "supported_by") == 0)      return EDGE_HISTORICAL;
    if (strcmp(link_type, "refines") == 0)           return EDGE_SEMANTIC;
    if (strcmp(link_type, "mechanism_of") == 0)      return EDGE_CAUSAL;
    if (strcmp(link_type, "related_concept") == 0)   return EDGE_SIMILARITY;
    if (strcmp(link_type, "formalizes") == 0)        return EDGE_AUTHORITY;
    if (strcmp(link_type, "forces_are") == 0)        return EDGE_CAUSAL;
    if (strcmp(link_type, "implemented_by") == 0)    return EDGE_STRUCTURAL;
    if (strcmp(link_type, "describes_mechanism") == 0) return EDGE_CAUSAL;
    if (strcmp(link_type, "drives") == 0)            return EDGE_CAUSAL;
    if (strcmp(link_type, "explains") == 0)          return EDGE_SEMANTIC;
    if (strcmp(link_type, "deepest_form") == 0)      return EDGE_SIMILARITY;
    if (strcmp(link_type, "is_the_principle_of") == 0) return EDGE_AUTHORITY;
    if (strcmp(link_type, "separates_implementation_from") == 0) return EDGE_STRUCTURAL;
    if (strcmp(link_type, "expands") == 0)           return EDGE_SEMANTIC;
    if (strcmp(link_type, "is_the_weight_form_of") == 0) return EDGE_SIMILARITY;
    if (strcmp(link_type, "grounds") == 0)           return EDGE_HISTORICAL;
    if (strcmp(link_type, "detects_violation_of") == 0) return EDGE_VIOLATION;
    if (strcmp(link_type, "reinforces") == 0)        return EDGE_SIMILARITY;
    if (strcmp(link_type, "constrained_by") == 0)    return EDGE_AUTHORITY;
    return EDGE_STRUCTURAL;
}

/*
 * Load all entity tables as nodes, then load the link table as edges.
 * Returns the node ID of the anchor (first error), or -1 on failure.
 */
static int load_laws_database(RFEngine *e) {
    MYSQL *conn = mysql_init(NULL);
    if (conn == NULL) {
        fprintf(stderr, "mysql_init() failed\n");
        return -1;
    }

    if (mysql_real_connect(conn, "localhost", "root", NULL, "laws",
                           0, NULL, 0) == NULL) {
        fprintf(stderr, "mysql_real_connect() failed: %s\n", mysql_error(conn));
        mysql_close(conn);
        return -1;
    }

    /* ── Load nodes from each entity table ── */
    const char *tables[] = {
        "law", "error", "pattern", "problem",
        "cause", "fix", "prevention", "solution"
    };
    int n_tables = 8;
    int anchor_id = -1;

    for (int t = 0; t < n_tables; t++) {
        const char *tbl = tables[t];
        int id_base = table_id_base(tbl);
        NodeType ntype = table_node_type(tbl);
        char query[256];

        /* Most tables use `name`; pattern uses `triggerText` */
        const char *name_col = (strcmp(tbl, "pattern") == 0) ? "triggerText" : "name";
        snprintf(query, sizeof(query), "SELECT id, %s FROM %s ORDER BY id",
                 name_col, tbl);

        if (mysql_query(conn, query)) {
            if (e->verbose)
                fprintf(stderr, "  [load] SKIP %s: %s\n", tbl, mysql_error(conn));
            continue;
        }

        MYSQL_RES *res = mysql_store_result(conn);
        if (!res) continue;

        int count = 0;
        MYSQL_ROW row;
        while ((row = mysql_fetch_row(res)) && e->field.node_count < MAX_NODES) {
            int db_id = atoi(row[0]);
            const char *name = row[1] ? row[1] : "(unnamed)";
            int node_id = id_base + db_id;

            /* Safety: truncate long text fields */
            char safe_name[256];
            strncpy(safe_name, name, 255);
            safe_name[255] = '\0';

            /* Ensure within range */
            if (node_id < 0 || node_id >= MAX_NODES) continue;

            /* Pad to node_id if there are gaps */
            while (e->field.node_count < node_id) {
                rf_add_node(e, "(padding)", "unknown", NODE_UNKNOWN, 0.0);
            }

            /* Add or update the node */
            if (e->field.node_count == node_id) {
                rf_add_node(e, safe_name, tbl, ntype, 0.7);
            } else if (node_id < e->field.node_count) {
                /* Update existing padding node */
                strncpy(e->field.nodes[node_id].name, safe_name, 255);
                e->field.nodes[node_id].name[255] = '\0';
                strncpy(e->field.nodes[node_id].domain, tbl, 63);
                e->field.nodes[node_id].domain[63] = '\0';
                e->field.nodes[node_id].type = ntype;
                e->field.nodes[node_id].authority = 0.7;
            }

            /* Track first law as anchor candidate (laws have outgoing link edges) */
            if (anchor_id < 0 && strcmp(tbl, "law") == 0 && db_id == 42)
                anchor_id = node_id;

            count++;
        }
        mysql_free_result(res);

        if (e->verbose)
            printf("  [load] %-12s → %d nodes (base=%d)\n", tbl, count, id_base);
    }

    /* ── Load edges from the entity_link table ──
     * entity_link schema: fromTable, fromId, toTable, toId, linkType
     * This is the generic link table — any entity can link to any entity. */
    if (mysql_query(conn, "SELECT fromTable, fromId, toTable, toId, linkType FROM entity_link")) {
        if (e->verbose)
            fprintf(stderr, "  [load] SKIP links: %s\n", mysql_error(conn));
    } else {
        MYSQL_RES *res = mysql_store_result(conn);
        if (res) {
            int edge_count = 0;
            int schema_rejected = 0;
            int duplicate = 0;
            MYSQL_ROW row;
            while ((row = mysql_fetch_row(res)) && e->field.edge_count < MAX_EDGES) {
                /* fromTable/fromId → toTable/toId */
                if (!row[0] || !row[1] || !row[2] || !row[3]) continue;
                const char *from_table = row[0];
                int from_id = atoi(row[1]);
                const char *to_table = row[2];
                int to_id = atoi(row[3]);
                const char *link_type = row[4] ? row[4] : "structural";

                /* Convert table names to ID bases */
                int from_base = table_id_from_link(from_table);
                int to_base = table_id_from_link(to_table);
                if (from_base < 0 || to_base < 0) continue;

                int from = from_base + from_id;
                int to = to_base + to_id;

                if (from < 0 || from >= e->field.node_count) continue;
                if (to < 0 || to >= e->field.node_count) continue;
                if (e->field.nodes[from].type == NODE_UNKNOWN) continue;
                if (e->field.nodes[to].type == NODE_UNKNOWN) continue;

                EdgeType et = link_type_to_edge(link_type);

                /* BloodHound principle: directed edges serve the purpose.
                 * Forward edge: law → target (the law governs the target)
                 * This is the natural direction — laws point to what they govern. */
                int result = rf_add_edge(e, from, to, et);
                if (result >= 0) {
                    edge_count++;
                } else if (result == -2) {
                    schema_rejected++;
                    /* Schema violation — try as structural instead */
                    rf_add_edge(e, from, to, EDGE_STRUCTURAL);
                    edge_count++;
                } else if (result == -3) {
                    duplicate++;
                }

                /* BloodHound principle: no bidirectional edges.
                 * Instead of a blanket reverse, add a structural edge only
                 * if the reverse direction is semantically meaningful.
                 * Target → Law is "this node is governed by this law" — structural. */
                if (e->field.edge_count < MAX_EDGES) {
                    int rev = rf_add_edge(e, to, from, EDGE_STRUCTURAL);
                    if (rev >= 0) edge_count++;
                }
            }
            mysql_free_result(res);
            if (e->verbose)
                printf("  [load] %-12s → %d edges (%d schema-rejected, %d duplicate)\n",
                       "link", edge_count, schema_rejected, duplicate);
        }
    }

    /* ── Generate structural edges from FK relationships ── */
    /* Each entity table has domainId, statusId, severityId, priorityId FKs.
     * We don't load authority tables as nodes (they're lookup tables),
     * but we create structural edges between entities that share the same domain.
     * CAUTION: O(n²) per table — cap at 50 same-domain pairs per table. */
    {
        const char *entity_tables[] = {"law", "error", "pattern", "problem",
                                        "cause", "fix", "prevention"};
        int struct_edges = 0;
        for (int t = 0; t < 7; t++) {
            const char *tbl = entity_tables[t];
            char query[256];
            snprintf(query, sizeof(query),
                     "SELECT id, domainId FROM %s WHERE domainId IS NOT NULL", tbl);
            if (mysql_query(conn, query)) continue;
            MYSQL_RES *res = mysql_store_result(conn);
            if (!res) continue;

            /* Collect nodes by domain */
            int domain_ids[512];
            int node_ids[512];
            int n = 0;
            MYSQL_ROW row;
            while ((row = mysql_fetch_row(res)) && n < 512) {
                domain_ids[n] = atoi(row[1]);
                node_ids[n] = table_id_base(tbl) + atoi(row[0]);
                n++;
            }
            mysql_free_result(res);

            /* Link nodes with same domain (structural) — cap at 50 per table */
            int table_edges = 0;
            for (int i = 0; i < n && table_edges < 50; i++) {
                for (int j = i + 1; j < n && table_edges < 50; j++) {
                    if (domain_ids[i] != domain_ids[j]) continue;
                    if (node_ids[i] >= e->field.node_count) continue;
                    if (node_ids[j] >= e->field.node_count) continue;
                    if (e->field.nodes[node_ids[i]].type == NODE_UNKNOWN) continue;
                    if (e->field.nodes[node_ids[j]].type == NODE_UNKNOWN) continue;
                    rf_add_edge(e, node_ids[i], node_ids[j], EDGE_STRUCTURAL);
                    struct_edges++;
                    table_edges++;
                }
            }
        }
        if (e->verbose)
            printf("  [load] %-12s → %d edges (same-domain links)\n",
                   "structural", struct_edges);
    }

    mysql_close(conn);

    if (e->verbose)
        printf("  [load] Total: %d nodes, %d edges\n\n",
               e->field.node_count, e->field.edge_count);

    return anchor_id;
}

/* ========================================================================== */
/*  SECTION 28b — Load constraints from real DB tables                       */
/* ========================================================================== */
/*
 * The database tables ARE the constraint language. No need to invent one.
 *
 *   law        → "this path is forbidden or required"   (C_EXCLUDE / C_EDGE_HAS)
 *   error      → "this is a known failure mode"          (C_TYPE)
 *   pattern    → "this sequence tends to recur"          (C_CONTAINS)
 *   problem    → "this is a known problem"               (C_TYPE)
 *   cause      → "this causes something"                 (C_EDGE_HAS causal)
 *   fix        → "this fixes something"                  (C_EDGE_HAS preventative)
 *   prevention → "this prevents something"               (C_EDGE_HAS preventative)
 *   domain     → "this belongs to this area"             (C_DOMAIN)
 *
 * Each table contributes a different kind of constraint on the hypothesis space.
 * The reasoning engine reads these constraints, reduces uncertainty, and
 * decides what to do next.
 *
 * "Reasoning is the process of reducing uncertainty by applying accumulated
 *  constraints until the remaining action is sufficiently justified."
 */

/*
 * Load constraints from the `laws` database.
 * Each table becomes a different constraint type on the hypothesis space.
 *
 * This is the bridge between the database (constraint storage) and the
 * constraint engine (uncertainty reduction).
 */
static void load_constraints_from_db(RFEngine *e) {
    MYSQL *conn = mysql_init(NULL);
    if (!conn) return;
    if (!mysql_real_connect(conn, "localhost", "root", NULL, "laws",
                            0, NULL, 0)) {
        if (e->verbose)
            fprintf(stderr, "  [constraints] Cannot connect: %s\n", mysql_error(conn));
        mysql_close(conn);
        return;
    }

    /*
     * Laws are authority constraints — they define what types of nodes
     * are governed. Each law name becomes a "contains" constraint that
     * filters the hypothesis space to nodes whose names relate to that law.
     *
     * In BloodHound terms: laws are like "Tier 0" — they're the highest
     * authority nodes. Everything else is reachable from them.
     */
    if (!mysql_query(conn, "SELECT id, name FROM law LIMIT 20")) {
        MYSQL_RES *res = mysql_store_result(conn);
        if (res) {
            int count = 0;
            MYSQL_ROW row;
            while ((row = mysql_fetch_row(res)) && count < 20) {
                /* Each law constrains: "the answer is related to this law" */
                char desc[128];
                snprintf(desc, sizeof(desc), "law#%s: %s", row[0],
                         row[1] ? row[1] : "?");
                /* Use the first word of the law name as a contains constraint */
                if (row[1]) {
                    char first_word[64];
                    strncpy(first_word, row[1], 63);
                    first_word[63] = '\0';
                    char *space = strchr(first_word, ' ');
                    if (space) *space = '\0';
                    if (strlen(first_word) > 3) {
                        rf_constraint_contains(e, first_word, 0.3, desc);
                        /* Mark as soft — multiple laws can be relevant simultaneously */
                        e->constraints.constraints[e->constraints.constraint_count - 1].hard = 0;
                    }
                }
                count++;
            }
            mysql_free_result(res);
            if (e->verbose)
                printf("  [constraints] Loaded %d law constraints (soft)\n", count);
        }
    }

    /*
     * Type constraints — "the answer is one of these types"
     * These are HARD constraints: eliminate nodes of irrelevant types.
     * But we apply them as soft so we don't eliminate everything at once.
     */
    rf_constraint_type(e, NODE_ERROR, 0.5, "errors are candidate answers");
    e->constraints.constraints[e->constraints.constraint_count - 1].hard = 0;
    rf_constraint_type(e, NODE_LAW, 0.4, "laws are candidate answers");
    e->constraints.constraints[e->constraints.constraint_count - 1].hard = 0;
    rf_constraint_type(e, NODE_INCIDENT, 0.3, "incidents are candidate answers");
    e->constraints.constraints[e->constraints.constraint_count - 1].hard = 0;

    /*
     * Patterns are behavioral constraints — "nodes matching this pattern
     * are more likely to be relevant" (soft — patterns are hints, not rules)
     */
    if (!mysql_query(conn, "SELECT triggerText FROM pattern LIMIT 10")) {
        MYSQL_RES *res = mysql_store_result(conn);
        if (res) {
            int count = 0;
            MYSQL_ROW row;
            while ((row = mysql_fetch_row(res)) && count < 10) {
                if (row[0]) {
                    char desc[128];
                    snprintf(desc, sizeof(desc), "pattern: %.100s", row[0]);
                    /* Use first significant word from triggerText */
                    char word[64];
                    strncpy(word, row[0], 63);
                    word[63] = '\0';
                    char *space = strchr(word, ' ');
                    if (space) *space = '\0';
                    if (strlen(word) > 3) {
                        rf_constraint_contains(e, word, 0.2, desc);
                        e->constraints.constraints[e->constraints.constraint_count - 1].hard = 0;
                    }
                }
                count++;
            }
            mysql_free_result(res);
            if (e->verbose)
                printf("  [constraints] Loaded %d pattern constraints (soft)\n", count);
        }
    }

    /*
     * Edge-type constraints from the link table:
     * If a node has a "cause" edge, it's causally connected.
     * These are HARD structural constraints — a node without any causal
     * edges cannot be part of a causal reasoning chain.
     */
    rf_constraint_edge_has(e, EDGE_CAUSAL, 0.6,
                           "candidate must be causally connected");
    /* Keep this one hard — causal connectivity is a real requirement */
    rf_constraint_edge_has(e, EDGE_AUTHORITY, 0.4,
                           "candidate should have authority links");
    e->constraints.constraints[e->constraints.constraint_count - 1].hard = 0;

    /* Composite edge constraints — BloodHound-style.
     * If a node has an EDGE_ATTACK_PATH, it's on a confirmed exploit path.
     * This is the strongest possible signal. */
    rf_constraint_edge_has(e, EDGE_ATTACK_PATH, 1.5,
                           "candidate is on an attack path (composite)");
    e->constraints.constraints[e->constraints.constraint_count - 1].hard = 0;

    rf_constraint_edge_has(e, EDGE_VIOLATION, 1.0,
                           "candidate represents a law violation (composite)");
    /* Make this HARD — nodes without violations are eliminated.
     * This dramatically reduces the hypothesis space. */
    e->constraints.constraints[e->constraints.constraint_count - 1].hard = 1;

    rf_constraint_edge_has(e, EDGE_CAUSAL_CHAIN, 0.6,
                           "candidate is on a causal chain (composite)");
    e->constraints.constraints[e->constraints.constraint_count - 1].hard = 0;

    rf_constraint_edge_has(e, EDGE_RESOLUTION, 0.5,
                           "candidate is on a resolution path (composite)");
    e->constraints.constraints[e->constraints.constraint_count - 1].hard = 0;

    /* Reachability constraint — BloodHound "owned" principle.
     * Nodes reachable from the anchor (within 3 hops) are more likely
     * to be relevant. This is computed at constraint-load time using BFS
     * from the anchor. */
    {
        int reachable[MAX_NODES];
        memset(reachable, 0, sizeof(int) * e->field.node_count);

        /* BFS from anchor, up to 3 hops */
        int queue[MAX_NODES];
        int head = 0, tail = 0;
        queue[tail++] = e->field.anchor_id;
        reachable[e->field.anchor_id] = 1;

        for (int hop = 0; hop < 3 && head < tail; hop++) {
            int level_size = tail - head;
            for (int k = 0; k < level_size; k++) {
                int cur = queue[head++];
                for (int i = 0; i < e->field.edge_count; i++) {
                    if (e->field.edges[i].from != cur) continue;
                    int next = e->field.edges[i].to;
                    if (reachable[next]) continue;
                    reachable[next] = 1;
                    queue[tail++] = next;
                    if (tail >= MAX_NODES) break;
                }
            }
        }

        /* Count reachable nodes */
        int reach_count = 0;
        for (int i = 0; i < e->field.node_count; i++)
            if (reachable[i]) reach_count++;

        if (e->verbose)
            printf("  [constraints] Reachability: %d nodes reachable from anchor (3 hops)\n",
                   reach_count);

        /* Boost reachable nodes directly in their raw_score.
         * Only high-value reachable nodes get a boost — this prevents
         * the distribution from flattening when too many nodes are reachable.
         * Also add degree centrality boost: nodes with more edges are more
         * important in the graph. */
        /* Count edges per node (degree centrality) */
        int degree[MAX_NODES];
        memset(degree, 0, sizeof(int) * e->field.node_count);
        for (int i = 0; i < e->field.edge_count; i++) {
            degree[e->field.edges[i].from]++;
            degree[e->field.edges[i].to]++;
        }

        for (int i = 0; i < e->constraints.hypothesis_count; i++) {
            if (e->constraints.hypotheses[i].eliminated) continue;
            int nid = e->constraints.hypotheses[i].node_id;
            if (reachable[nid] && e->field.nodes[nid].high_value) {
                e->constraints.hypotheses[i].raw_score *= 2.0;  /* high-value + reachable = 2x */
            }
            /* Degree centrality: nodes with more connections get a boost.
             * Normalized by max degree to keep boost in [1.0, 2.0] range. */
            if (degree[nid] > 0) {
                double deg_boost = 1.0 + 0.5 * (double)degree[nid] / 10.0;
                if (deg_boost > 2.0) deg_boost = 2.0;
                e->constraints.hypotheses[i].raw_score *= deg_boost;
            }
        }
    }

    /*
     * Load constraints from fact, evidence, and answer tables.
     * Instead of using `contains` (which rarely matches node names),
     * we use type-based constraints that boost entire node categories.
     *
     * The count of facts/evidence/problems tells the engine HOW MUCH
     * to weight each type. More facts = laws are more important.
     * More problems = problem nodes are more relevant.
     */
    {
        int fact_count = 0, evidence_count = 0, problem_count = 0;
        int cause_count = 0, fix_count = 0, prevention_count = 0;

        /* Count facts → boost LAW nodes (facts are stored as laws) */
        if (!mysql_query(conn, "SELECT COUNT(*) FROM fact")) {
            MYSQL_RES *res = mysql_store_result(conn);
            if (res) { MYSQL_ROW row = mysql_fetch_row(res); if (row && row[0]) fact_count = atoi(row[0]); mysql_free_result(res); }
        }
        /* Count evidence → boost ERROR nodes (evidence comes from errors) */
        if (!mysql_query(conn, "SELECT COUNT(*) FROM evidence")) {
            MYSQL_RES *res = mysql_store_result(conn);
            if (res) { MYSQL_ROW row = mysql_fetch_row(res); if (row && row[0]) evidence_count = atoi(row[0]); mysql_free_result(res); }
        }
        /* Count problems/causes/fixes/prevention */
        if (!mysql_query(conn, "SELECT COUNT(*) FROM problem")) {
            MYSQL_RES *res = mysql_store_result(conn);
            if (res) { MYSQL_ROW row = mysql_fetch_row(res); if (row && row[0]) problem_count = atoi(row[0]); mysql_free_result(res); }
        }
        if (!mysql_query(conn, "SELECT COUNT(*) FROM cause")) {
            MYSQL_RES *res = mysql_store_result(conn);
            if (res) { MYSQL_ROW row = mysql_fetch_row(res); if (row && row[0]) cause_count = atoi(row[0]); mysql_free_result(res); }
        }
        if (!mysql_query(conn, "SELECT COUNT(*) FROM fix")) {
            MYSQL_RES *res = mysql_store_result(conn);
            if (res) { MYSQL_ROW row = mysql_fetch_row(res); if (row && row[0]) fix_count = atoi(row[0]); mysql_free_result(res); }
        }
        if (!mysql_query(conn, "SELECT COUNT(*) FROM prevention")) {
            MYSQL_RES *res = mysql_store_result(conn);
            if (res) { MYSQL_ROW row = mysql_fetch_row(res); if (row && row[0]) prevention_count = atoi(row[0]); mysql_free_result(res); }
        }

        if (e->verbose)
            printf("  [constraints] DB counts: facts=%d evidence=%d problems=%d causes=%d fixes=%d preventions=%d\n",
                   fact_count, evidence_count, problem_count,
                   cause_count, fix_count, prevention_count);

        /* Load specific problem/cause/fix names as contains constraints
         * — these DO match because problem/cause/fix nodes have the same names */
        if (!mysql_query(conn, "SELECT name FROM problem LIMIT 20")) {
            MYSQL_RES *res = mysql_store_result(conn);
            if (res) {
                int count = 0;
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res)) && row[0]) {
                    char desc[256];
                    snprintf(desc, sizeof(desc), "problem: %s", row[0]);
                    char pattern[128];
                    strncpy(pattern, row[0], 127);
                    pattern[127] = '\0';
                    if (strlen(pattern) > 40) pattern[40] = '\0';
                    rf_constraint_contains(e, pattern, 0.25, desc);
                    e->constraints.constraints[e->constraints.constraint_count - 1].hard = 0;
                    count++;
                }
                mysql_free_result(res);
                if (e->verbose)
                    printf("  [constraints] Loaded %d problem constraints (soft)\n", count);
            }
        }

        if (!mysql_query(conn, "SELECT name FROM cause LIMIT 10")) {
            MYSQL_RES *res = mysql_store_result(conn);
            if (res) {
                int count = 0;
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res)) && row[0]) {
                    char desc[256];
                    snprintf(desc, sizeof(desc), "cause: %s", row[0]);
                    rf_constraint_contains(e, row[0], 0.20, desc);
                    e->constraints.constraints[e->constraints.constraint_count - 1].hard = 0;
                    count++;
                }
                mysql_free_result(res);
                if (e->verbose)
                    printf("  [constraints] Loaded %d cause constraints (soft)\n", count);
            }
        }

        if (!mysql_query(conn, "SELECT name FROM fix LIMIT 10")) {
            MYSQL_RES *res = mysql_store_result(conn);
            if (res) {
                int count = 0;
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res)) && row[0]) {
                    char desc[256];
                    snprintf(desc, sizeof(desc), "fix: %s", row[0]);
                    rf_constraint_contains(e, row[0], 0.20, desc);
                    e->constraints.constraints[e->constraints.constraint_count - 1].hard = 0;
                    count++;
                }
                mysql_free_result(res);
                if (e->verbose)
                    printf("  [constraints] Loaded %d fix constraints (soft)\n", count);
            }
        }

        if (!mysql_query(conn, "SELECT name FROM prevention LIMIT 10")) {
            MYSQL_RES *res = mysql_store_result(conn);
            if (res) {
                int count = 0;
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res)) && row[0]) {
                    char desc[256];
                    snprintf(desc, sizeof(desc), "prevention: %s", row[0]);
                    rf_constraint_contains(e, row[0], 0.20, desc);
                    e->constraints.constraints[e->constraints.constraint_count - 1].hard = 0;
                    count++;
                }
                mysql_free_result(res);
                if (e->verbose)
                    printf("  [constraints] Loaded %d prevention constraints (soft)\n", count);
            }
        }
    }

    mysql_close(conn);
}

/*
 * Demo: constraint-driven uncertainty reduction on real data.
 *
 * This demonstrates the core principle:
 *   "Reasoning is the process of reducing uncertainty by applying
 *    accumulated constraints until the remaining action is sufficiently
 *    justified."
 *
 * We start with all nodes as hypotheses (uniform prior), then apply
 * constraints one by one, watching the probability mass collapse onto
 * the most likely candidates.
 */
static void demo_constraint_reduction(RFEngine *e) {
    printf("\n");
    printf("╔══════════════════════════════════════════════════════════════╗\n");
    printf("║  CONSTRAINT-DRIVEN UNCERTAINTY REDUCTION                   ║\n");
    printf("║  Reasoning = reducing uncertainty by applying constraints   ║\n");
    printf("╚══════════════════════════════════════════════════════════════╝\n\n");

    /* Step 1: Initialize hypothesis space — all real nodes are candidates */
    printf("Step 1: Initialize hypothesis space (uniform prior)\n");
    rf_constraints_init_hypotheses(e);

    int active = 0;
    for (int i = 0; i < e->constraints.hypothesis_count; i++)
        if (!e->constraints.hypotheses[i].eliminated) active++;
    printf("  %d hypotheses, entropy=%.3f bits, convergence=%.4f\n\n",
           active, e->constraints.entropy, e->constraints.convergence);

    /* Step 2: Load constraints from the database */
    printf("Step 2: Load constraints from `laws` database tables\n");
    load_constraints_from_db(e);
    printf("  %d constraints loaded\n\n", e->constraints.constraint_count);

    /* Step 3: Apply constraints one by one, watch uncertainty collapse */
    printf("Step 3: Apply constraints iteratively\n\n");

    for (int i = 0; i < e->constraints.constraint_count; i++) {
        if (e->constraints.converged) {
            printf("  → CONVERGED before all constraints applied (%d/%d used)\n\n",
                   i, e->constraints.constraint_count);
            break;
        }

        rf_constraints_apply(e, i);

        active = 0;
        for (int j = 0; j < e->constraints.hypothesis_count; j++)
            if (!e->constraints.hypotheses[j].eliminated) active++;

        printf("  After constraint %d: %d candidates remain, entropy=%.3f, convergence=%.3f\n",
               i + 1, active, e->constraints.entropy, e->constraints.convergence);
    }

    /* Step 4: Show final state */
    printf("\nStep 4: Final state\n");
    rf_constraints_print_state(e);

    /* Step 5: Show the winner */
    if (e->constraints.converged || e->constraints.convergence > 0.1) {
        int ids[3];
        double probs[3];
        int n = rf_constraints_top_candidates(e, ids, probs, 3);
        printf("  → Top candidate: '%s' (p=%.3f)\n",
               e->field.nodes[ids[0]].name, probs[0]);
        if (n > 1)
            printf("  → Runner up:     '%s' (p=%.3f)\n",
                   e->field.nodes[ids[1]].name, probs[1]);
        if (n > 2)
            printf("  → Third:         '%s' (p=%.3f)\n",
                   e->field.nodes[ids[2]].name, probs[2]);
        printf("\n");
        printf("  Interpretation: Given the constraints from the database,\n");
        printf("  the reasoning field has collapsed onto '%s' as the most\n",
               e->field.nodes[ids[0]].name);
        printf("  justified candidate. This is not 'solving' — it is\n");
        printf("  probability distribution collapse under constraints.\n\n");
    }
}

/* ========================================================================== */
/*  SECTION 29 — Main                                                         */
/* ========================================================================== */

int main(int argc, char **argv) {
    int verbose = 1;
    int runs = 3;
    int anchor_id = -1;
    int constraint_demo = 0;  /* run constraint reduction demo */
    int converge_mode = 0;    /* run convergence loop instead of linear pipeline */
    int paths_mode = 0;       /* run attack path analysis (BloodHound-style) */
    int allpaths_mode = 0;    /* run all-paths analysis (DFS) */

    /* Parse args: sigil [runs] [-q] [anchor=N] [--constraints] [--converge] [--paths] [--allpaths] */
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-q") == 0) verbose = 0;
        else if (strcmp(argv[i], "--constraints") == 0) constraint_demo = 1;
        else if (strcmp(argv[i], "--converge") == 0) converge_mode = 1;
        else if (strcmp(argv[i], "--paths") == 0) paths_mode = 1;
        else if (strcmp(argv[i], "--allpaths") == 0) allpaths_mode = 1;
        else if (strncmp(argv[i], "anchor=", 7) == 0) anchor_id = atoi(argv[i] + 7);
        else runs = atoi(argv[i]);
    }

    srand(42);

    RFEngine *engine = malloc(sizeof(RFEngine));
    if (!engine) {
        fprintf(stderr, "FATAL: Cannot allocate RFEngine (%zu bytes)\n", sizeof(RFEngine));
        return 1;
    }
    rf_engine_init(engine, verbose);

    printf("╔══════════════════════════════════════════════════════════════╗\n");
    printf("║  SIGIL — Reasoning Field Traversal Algorithm (RF-TA v2)     ║\n");
    printf("║  Pre-Execution Reasoning Kernel                             ║\n");
    printf("║  Connected to `laws` database — real data                   ║\n");
    printf("╚══════════════════════════════════════════════════════════════╝\n\n");

    /* Load real data from MySQL */
    printf("Loading knowledge graph from `laws` database...\n\n");
    int auto_anchor = load_laws_database(engine);

    if (engine->field.node_count == 0) {
        fprintf(stderr, "FATAL: No nodes loaded. Is MySQL running? Is `laws` DB populated?\n");
        free(engine);
        return 1;
    }

    /* Use specified anchor or auto-detected first error */
    if (anchor_id < 0) anchor_id = auto_anchor;
    if (anchor_id < 0 || anchor_id >= engine->field.node_count) {
        fprintf(stderr, "No valid anchor found. Using node 0.\n");
        anchor_id = 0;
    }

    rf_set_anchor(engine, anchor_id);

    printf("Anchor: node %d (%s, type=%d)\n",
           anchor_id, engine->field.nodes[anchor_id].name,
           engine->field.nodes[anchor_id].type);
    printf("Graph:  %d nodes, %d edges (base)\n",
           engine->field.node_count, engine->field.edge_count);

    /* BloodHound-style post-processing: generate composite edges */
    printf("\nPost-processing: generating composite edges...\n");
    rf_print_edge_schema();
    int composite = rf_generate_composite_edges(engine);
    printf("Graph after composite: %d nodes, %d edges (%d composite)\n\n",
           engine->field.node_count, engine->field.edge_count, composite);

    if (paths_mode) {
        /* BloodHound-style attack path analysis */
        rf_find_attack_paths(engine, anchor_id, 10);

        /* Also show specific high-value paths */
        printf("=== Key Reasoning Paths ===\n\n");
        rf_find_path_between(engine, "No Agent Interpretation",
                             "Agent fabricated data");
        rf_find_path_between(engine, "Pipeline Steps Must Not",
                             "Agent fabricated data");
        rf_find_path_between(engine, "BCL-only database writes",
                             "Agent fabricated data");
    }

    if (allpaths_mode) {
        /* BloodHound-style all-paths analysis (DFS) */
        /* Find all paths from anchor to the top error (Agent fabricated data) */
        int target = -1;
        for (int i = 0; i < engine->field.node_count; i++) {
            if (strstr(engine->field.nodes[i].name, "Agent fabricated data")) {
                target = i;
                break;
            }
        }
        if (target >= 0)
            rf_find_all_paths(engine, anchor_id, target, 5, 20);
    }

    if (converge_mode) {
        /* Convergence loop mode: traverse → constrain → traverse → converge */
        rf_convergence_loop(engine, runs > 0 ? runs : 5);
    } else {
        rf_print_policy(engine);
        printf("\n");

        /* Run the full RF-TA pipeline */
        for (int r = 0; r < runs; r++) {
            printf("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
            printf("  RUN %d / %d\n", r + 1, runs);
            printf("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n");

            double reward = rf_run(engine);

            printf("  >>> Run %d reward: %.3f\n\n", r + 1, reward);

            if (r == 0 || r == runs - 1) {
                rf_print_policy(engine);
                printf("\n");
            }
        }

        /* Print final state */
        printf("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
        printf("  FINAL STATE\n");
        printf("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n");

        rf_print_field_summary(engine);
        printf("\n");

        rf_print_policy(engine);
        printf("\n");

        printf("Learning: %d total runs, last reward=%.3f, surprise=%.3f\n",
               engine->learning.total_runs,
               engine->learning.actual_reward,
               engine->learning.surprise);
        printf("\n");

        rf_print_ledger(engine);

        /* Constraint-driven uncertainty reduction demo */
        if (constraint_demo) {
            demo_constraint_reduction(engine);
        }
    }

    /* Print session state if any nodes were owned */
    if (engine->owned_count > 0)
        rf_print_session_state(engine);

    free(engine);

    printf("═══════════════════════════════════════════════════════════════\n");
    printf("  SIGIL pipeline complete.\n");
    printf("  Reasoning Field → Intent Graph → Execution Plan → Safety\n");
    printf("  → Execute → Ledger → Learn → Discover → Constraints\n");
    printf("═══════════════════════════════════════════════════════════════\n");

    return 0;
}
