//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_graph_core.c" date="2026-07-04" author="Devin" session_id="graph-bcl-units" context="Core graph lifecycle: graph_create, graph_free, graph_add_node, graph_add_edge, node_create, edge_create. Foundation for all graph BCL units."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_graph_core.c" domain="graph_engine" authority="GraphCore"}
//[@SUMMARY]{summary="Core graph lifecycle functions. Graph create/free, node/edge create, graph search. Included by all graph units as the foundation layer."}
//[@CLASS]{class="GraphCore" domain="graph_engine" authority="foundation"}
//[@METHOD]{method="graph_create" type="lifecycle"}
//[@METHOD]{method="graph_free" type="lifecycle"}
//[@METHOD]{method="node_create" type="command"}
//[@METHOD]{method="edge_create" type="command"}
//[@METHOD]{method="graph_add_node" type="command"}
//[@METHOD]{method="graph_add_edge" type="command"}
//[@METHOD]{method="graph_find_node" type="query"}
//[@METHOD]{method="graph_find_node_by_id" type="query"}

#include "bcl_graph_types.h"
#include <ctype.h>

/* ════════════════════════════════════════════
 * GRAPH LIFECYCLE
 * ════════════════════════════════════════════ */

Graph *graph_create(int initial_capacity) {
    if (initial_capacity <= 0) initial_capacity = 100;
    Graph *g = (Graph *)calloc(1, sizeof(Graph));
    if (!g) return NULL;
    g->node_capacity = initial_capacity;
    g->nodes = (Node **)calloc(g->node_capacity, sizeof(Node *));
    g->edge_capacity = initial_capacity * 2;
    g->edges = (Edge **)calloc(g->edge_capacity, sizeof(Edge *));
    g->node_count = 0;
    g->edge_count = 0;
    /* Default policy */
    g->policy.hard_limit = 6;
    g->policy.context_limit = 0;
    g->policy.attention_threshold = 0.3;
    g->policy.max_nodes_per_hop = 100;
    g->policy.max_total_nodes = 10000;
    /* Default executor */
    g->executor.memory_used = 0;
    g->executor.memory_budget = 512 * 1024 * 1024;
    g->executor.cost_used = 0;
    g->executor.cost_limit = 10000;
    g->executor.timeout_ms = 5000;
    g->executor.start_time_ms = 0;
    g->executor.halted = 0;
    /* Default MySQL settings */
    strncpy(g->mysql_host, "localhost", sizeof(g->mysql_host) - 1);
    strncpy(g->mysql_user, "root", sizeof(g->mysql_user) - 1);
    strncpy(g->mysql_db, "vb_shared", sizeof(g->mysql_db) - 1);
    return g;
}

void graph_free(Graph *g) {
    if (!g) return;
    /* Free nodes */
    for (int i = 0; i < g->node_count; i++) {
        Node *n = g->nodes[i];
        if (!n) continue;
        /* Free edges linked list from this node */
        Edge *e = n->first_edge;
        while (e) {
            Edge *next = e->next;
            /* Don't double-free edges that are in g->edges array */
            e = next;
        }
        if (n->data) free(n->data);
        free(n);
    }
    /* Free edge pointers array (edges themselves freed via nodes or separately) */
    if (g->edges) {
        for (int i = 0; i < g->edge_count; i++) {
            if (g->edges[i]) free(g->edges[i]);
        }
        free(g->edges);
    }
    if (g->nodes) free(g->nodes);
    free(g);
}

int graph_add_node(Graph *g, Node *n) {
    if (!g || !n) return -1;
    if (g->node_count >= g->node_capacity) {
        int new_cap = g->node_capacity * 2;
        Node **new_arr = (Node **)realloc(g->nodes, new_cap * sizeof(Node *));
        if (!new_arr) return -1;
        g->nodes = new_arr;
        g->node_capacity = new_cap;
    }
    n->id = g->node_count;
    g->nodes[g->node_count] = n;
    g->node_count++;
    return n->id;
}

int graph_add_edge(Graph *g, Edge *e) {
    if (!g || !e) return -1;
    if (g->edge_count >= g->edge_capacity) {
        int new_cap = g->edge_capacity * 2;
        Edge **new_arr = (Edge **)realloc(g->edges, new_cap * sizeof(Edge *));
        if (!new_arr) return -1;
        g->edges = new_arr;
        g->edge_capacity = new_cap;
    }
    e->id = g->edge_count;
    g->edges[g->edge_count] = e;
    g->edge_count++;
    /* Also add to source node's edge linked list */
    if (e->source) {
        e->next = e->source->first_edge;
        e->source->first_edge = e;
    }
    return e->id;
}

Node *graph_find_node(Graph *g, const char *name) {
    if (!g || !name) return NULL;
    for (int i = 0; i < g->node_count; i++) {
        if (g->nodes[i] && strcmp(g->nodes[i]->name, name) == 0) {
            return g->nodes[i];
        }
    }
    return NULL;
}

Node *graph_find_node_by_id(Graph *g, int id) {
    if (!g || id < 0 || id >= g->node_count) return NULL;
    return g->nodes[id];
}

int graph_node_count(Graph *g) {
    return g ? g->node_count : 0;
}

int graph_edge_count(Graph *g) {
    return g ? g->edge_count : 0;
}

/* ════════════════════════════════════════════
 * NODE / EDGE CREATION
 * ════════════════════════════════════════════ */

Node *node_create(int id, const char *name, const char *type, float importance) {
    Node *n = (Node *)calloc(1, sizeof(Node));
    if (!n) return NULL;
    n->id = id;
    n->name[0] = '\0';
    n->type[0] = '\0';
    if (name) strncpy(n->name, name, sizeof(n->name) - 1);
    if (type) strncpy(n->type, type, sizeof(n->type) - 1);
    n->importance = importance;
    n->expanded = 0;
    n->depth = 0;
    n->cost = 1.0;
    n->data = NULL;
    n->expand = NULL;
    n->first_edge = NULL;
    return n;
}

Edge *edge_create(int id, Node *source, Node *target, const char *rel, float weight) {
    Edge *e = (Edge *)calloc(1, sizeof(Edge));
    if (!e) return NULL;
    e->id = id;
    e->source = source;
    e->target = target;
    e->rel_type[0] = '\0';
    if (rel) strncpy(e->rel_type, rel, sizeof(e->rel_type) - 1);
    e->weight = weight;
    e->next = NULL;
    return e;
}

/* ════════════════════════════════════════════
 * GLOBAL CONFIG (from bcl_engine.h — needed by GraphStore)
 * Reads bcl_config.json if present, otherwise uses defaults.
 * ════════════════════════════════════════════ */

static int   g_config_initialized = 0;
static char  g_backend[32]   = "mysql";
static char  g_db_path[256]  = "bcl_ir";
static char  g_db_host[64]   = "localhost";
static char  g_db_user[64]   = "root";
static char  g_db_table[64]  = "vb_shared";
static int   g_db_port       = 3306;
static char  g_domain[64]    = "graph_engine";

static void trim_ws(char *s) {
    char *p = s;
    while (*p && isspace((unsigned char)*p)) p++;
    if (p != s) memmove(s, p, strlen(p) + 1);
    int len = (int)strlen(s);
    while (len > 0 && isspace((unsigned char)s[len - 1])) s[--len] = '\0';
}

int config_init_global(const char *path) {
    g_config_initialized = 1;
    if (!path) return 0;
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    char line[512];
    char section[64] = "";
    while (fgets(line, sizeof(line), f)) {
        trim_ws(line);
        if (line[0] == '#' || line[0] == '\0' || line[0] == '[') {
            if (line[0] == '[') {
                strncpy(section, line + 1, sizeof(section) - 1);
                char *close = strchr(section, ']');
                if (close) *close = '\0';
            }
            continue;
        }
        char *eq = strchr(line, '=');
        if (!eq) continue;
        *eq = '\0';
        char *key = line;
        char *val = eq + 1;
        trim_ws(key);
        trim_ws(val);
        if (strcmp(key, "backend") == 0)
            strncpy(g_backend, val, sizeof(g_backend) - 1);
        else if (strcmp(key, "db_path") == 0)
            strncpy(g_db_path, val, sizeof(g_db_path) - 1);
        else if (strcmp(key, "db_host") == 0)
            strncpy(g_db_host, val, sizeof(g_db_host) - 1);
        else if (strcmp(key, "db_user") == 0)
            strncpy(g_db_user, val, sizeof(g_db_user) - 1);
        else if (strcmp(key, "db_table") == 0)
            strncpy(g_db_table, val, sizeof(g_db_table) - 1);
        else if (strcmp(key, "db_port") == 0)
            g_db_port = atoi(val);
        else if (strcmp(key, "domain") == 0)
            strncpy(g_domain, val, sizeof(g_domain) - 1);
    }
    fclose(f);
    return 0;
}

const char *config_global_backend(void) {
    if (!g_config_initialized) config_init_global("bcl_config.json");
    return g_backend;
}

const char *config_global_db_path(void) {
    if (!g_config_initialized) config_init_global("bcl_config.json");
    return g_db_path;
}

const char *config_global_db_host(void) {
    if (!g_config_initialized) config_init_global("bcl_config.json");
    return g_db_host;
}

const char *config_global_db_user(void) {
    if (!g_config_initialized) config_init_global("bcl_config.json");
    return g_db_user;
}

const char *config_global_db_table(void) {
    if (!g_config_initialized) config_init_global("bcl_config.json");
    return g_db_table;
}

int config_global_db_port(void) {
    if (!g_config_initialized) config_init_global("bcl_config.json");
    return g_db_port;
}

const char *config_global_domain(void) {
    if (!g_config_initialized) config_init_global("bcl_config.json");
    return g_domain;
}
