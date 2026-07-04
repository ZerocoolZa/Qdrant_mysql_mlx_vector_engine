//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_graph_expand.c" date="2026-07-04" author="Devin" session_id="graph-bcl-units" context="BCL unit for Max Graph Engine recursive expansion. Nodes expand themselves via function pointers with policy + executor checks. Broken from graph_raw/GraphExpand.c. Commands: expand, query, export_json, register_all, read_state, set_config."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_graph_expand.c" domain="graph_engine" authority="GraphExpand"}
//[@SUMMARY]{summary="Recursive expansion engine for the Max Graph Engine. Nodes expand themselves via ExpandFn function pointers, recursively, with policy checks (should we expand?) and executor checks (can we afford it?). Commands: expand (expand a node by name/type), query (traverse from query string), export_json (dump graph as JSON), register_all (register built-in expanders), read_state, set_config."}
//[@CLASS]{class="GraphExpand" domain="graph_engine" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="expand_register" type="command"}
//[@METHOD]{method="expand_lookup" type="query"}
//[@METHOD]{method="graph_expand" type="command"}
//[@METHOD]{method="expand_class" type="command"}
//[@METHOD]{method="expand_method" type="command"}
//[@METHOD]{method="expand_rule" type="command"}
//[@METHOD]{method="expand_token" type="command"}
//[@METHOD]{method="expand_chat" type="command"}
//[@METHOD]{method="expand_register_all" type="command"}
//[@METHOD]{method="graph_query" type="command"}
//[@METHOD]{method="graph_export_json" type="query"}

/*
 * bcl_graph_expand.c — Recursive expansion engine for the Max Graph Engine
 *
 * This is the core: nodes expand themselves via function pointers, recursively,
 * with policy checks (should we expand?) and executor checks (can we afford it?).
 *
 * BCL IN:  [@RUN]{[@CMD]{expand}[@NODE]{MyClass}[@TYPE]{class}[@DEPTH]{3}}
 *          [@RUN]{[@CMD]{query}[@QUERY]{MyClass}[@DEPTH]{3}}
 *          [@RUN]{[@CMD]{export_json}}
 *          [@RUN]{[@CMD]{register_all}}
 *          [@RUN]{[@CMD]{read_state}}
 *          [@RUN]{[@CMD]{set_config}[@HOST]{localhost}[@USER]{root}[@DB]{vb_shared}[@MAX_DEPTH]{4}}
 * BCL OUT: [@OK]{[@EXPANDED]{N}[@NODES]{N}[@EDGES]{N}}
 *          [@OK]{[@JSON]{...}}
 *          [@ERR]{[@CODE]{N}[@DESC]{...}}
 */

#include "bcl_graph_types.h"
#include "bcl_toolstack.h"
#include <mysql.h>
#include <libgen.h>

/* ════════════════════════════════════════════
 * PRIVATE EXPANSION FUNCTION REGISTRY
 * Maps node type names to expansion functions.
 * Kept private to this unit (not in shared header).
 * ════════════════════════════════════════════ */

typedef struct ExpandRegistry {
    char type_name[32];
    ExpandFn fn;
} ExpandRegistry;

static ExpandRegistry registry[32];
static int registry_count = 0;

/* ════════════════════════════════════════════
 * BCL UNIT STATE
 * ════════════════════════════════════════════ */

#define EXPAND_BUF_SIZE   GRAPH_BUF_SIZE

static struct {
    int   initialized;
    int   registry_registered;
    Graph *graph;
    char  mysql_host[256];
    char  mysql_user[64];
    char  mysql_db[64];
    int   max_depth;
    int   expansions_run;
    int   queries_run;
    int   last_expanded_count;
    char  last_error[256];
} STATE;

/* ════════════════════════════════════════════
 * EXPANSION FUNCTION REGISTRY API
 * ════════════════════════════════════════════ */

/* Register an expansion function for a node type */
int expand_register(const char *node_type, ExpandFn fn) {
    if (!node_type || !fn) return -1;
    if (registry_count >= 32) return -1;
    strncpy(registry[registry_count].type_name, node_type, sizeof(registry[registry_count].type_name) - 1);
    registry[registry_count].fn = fn;
    registry_count++;
    return 0;
}

/* Get the expansion function for a node type */
ExpandFn expand_lookup(const char *node_type) {
    if (!node_type) return NULL;
    for (int i = 0; i < registry_count; i++) {
        if (strcmp(registry[i].type_name, node_type) == 0) {
            return registry[i].fn;
        }
    }
    return NULL;
}

/* ════════════════════════════════════════════
 * CORE RECURSIVE EXPANSION
 * ════════════════════════════════════════════ */

/* Expand a single node: call its expansion function, then recursively expand children.
 * This is THE function that makes the graph recursive and generative. */
int graph_expand(Graph *g, Node *node, int depth_left) {
    if (!g || !node) return 0;

    /* 1. Check executor — can we afford to continue? */
    if (executor_check(&g->executor)) return 0;

    /* 2. Check policy — should this node expand? */
    int nodes_this_hop = 0;  /* simplified — real version would track per-hop count */
    if (!policy_should_expand(&g->policy, node, node->depth, nodes_this_hop, g->node_count)) {
        return 0;
    }

    /* 3. Charge the cost */
    executor_charge(&g->executor, node->cost);

    /* 4. Mark as expanded */
    node->expanded = 1;

    /* 5. If node has no expand function, try to look one up by type */
    if (!node->expand) {
        node->expand = expand_lookup(node->type);
    }

    /* 6. If still no expand function, this is a leaf — stop */
    if (!node->expand) {
        return 0;
    }

    /* 7. Call the node's OWN expansion function.
     *    This is where the magic happens — the node knows how to expand itself. */
    Node **children = NULL;
    int n_children = node->expand(node, g, depth_left - 1, &children);

    if (n_children <= 0 || !children) {
        return 0;
    }

    /* 8. Add children to graph and recursively expand them.
     *    This is LAZY expansion — only expand children that pass the policy check. */
    int expanded_count = 0;
    for (int i = 0; i < n_children; i++) {
        Node *child = children[i];
        child->depth = node->depth + 1;

        /* Add child to graph */
        graph_add_node(g, child);

        /* Create edge from parent to child */
        char rel[64];
        snprintf(rel, sizeof(rel), "EXPANDS_TO");
        Edge *e = edge_create(g->edge_count, node, child, rel, child->importance);
        graph_add_edge(g, e);

        /* Recursively expand the child (if depth allows and policy says yes) */
        if (depth_left > 1) {
            expanded_count += graph_expand(g, child, depth_left - 1);
        }
    }

    /* 9. Free the children pointer array (the nodes themselves are now in the graph) */
    free(children);

    return expanded_count + n_children;
}

/* ════════════════════════════════════════════
 * BUILT-IN EXPANSION FUNCTIONS
 * ════════════════════════════════════════════ */

/* Expand a "class" node: load its methods from MySQL and create child nodes. */
int expand_class(Node *node, Graph *g, int depth_left, Node ***children_out) {
    if (!node || !g || !children_out) return 0;

    MYSQL *conn = mysql_init(NULL);
    if (!conn) { *children_out = NULL; return 0; }
    if (!mysql_real_connect(conn, "localhost", "root", "", "bcl_ir", 3306, NULL, 0)) {
        mysql_close(conn);
        *children_out = NULL;
        return 0;
    }

    char esc_name[GRAPH_MAX_NAME * 2 + 1];
    mysql_real_escape_string(conn, esc_name, node->name, (unsigned long)strlen(node->name));

    char sql[1024];
    snprintf(sql, sizeof(sql),
        "SELECT method_name, method_type FROM bcl_ir.bcl_methods "
        "WHERE class_name = '%s' LIMIT 100", esc_name);

    if (mysql_query(conn, sql)) { mysql_close(conn); *children_out = NULL; return 0; }
    MYSQL_RES *res = mysql_store_result(conn);
    if (!res) { mysql_close(conn); *children_out = NULL; return 0; }

    int count = (int)mysql_num_rows(res);
    if (count <= 0) { mysql_free_result(res); mysql_close(conn); *children_out = NULL; return 0; }

    Node **children = (Node **)calloc(count, sizeof(Node *));
    if (!children) { mysql_free_result(res); mysql_close(conn); *children_out = NULL; return 0; }

    int idx = 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        const char *mname = row[0] ? row[0] : "";
        Node *child = node_create(0, mname, "method", 0.4f);
        if (child) {
            children[idx] = child;
            idx++;
        }
    }
    mysql_free_result(res);
    mysql_close(conn);

    *children_out = children;
    (void)depth_left;
    return idx;
}

/* Expand a "method" node: load its callers and callees from BCL edges */
int expand_method(Node *node, Graph *g, int depth_left, Node ***children_out) {
    if (!node || !g || !children_out) return 0;

    MYSQL *conn = mysql_init(NULL);
    if (!conn) { *children_out = NULL; return 0; }
    if (!mysql_real_connect(conn, "localhost", "root", "", "bcl_ir", 3306, NULL, 0)) {
        mysql_close(conn);
        *children_out = NULL;
        return 0;
    }

    char esc_name[GRAPH_MAX_NAME * 2 + 1];
    mysql_real_escape_string(conn, esc_name, node->name, (unsigned long)strlen(node->name));

    char sql[1024];
    snprintf(sql, sizeof(sql),
        "SELECT target, edge_type, certainty FROM bcl_ir.bcl_edges "
        "WHERE source_method_id LIKE '%%%s' AND edge_type='CALL' LIMIT 50", esc_name);

    if (mysql_query(conn, sql)) { mysql_close(conn); *children_out = NULL; return 0; }
    MYSQL_RES *res = mysql_store_result(conn);
    if (!res) { mysql_close(conn); *children_out = NULL; return 0; }

    int count = (int)mysql_num_rows(res);
    if (count <= 0) { mysql_free_result(res); mysql_close(conn); *children_out = NULL; return 0; }

    Node **children = (Node **)calloc(count, sizeof(Node *));
    if (!children) { mysql_free_result(res); mysql_close(conn); *children_out = NULL; return 0; }

    int idx = 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        const char *target = row[0] ? row[0] : "";
        const char *certainty = row[2] ? row[2] : "";
        float importance = 0.5f;
        if (strcmp(certainty, "CERTAIN") == 0) importance = 0.8f;
        else if (strcmp(certainty, "PROBABLE") == 0) importance = 0.5f;
        Node *child = node_create(0, target, "method", importance);
        if (child) {
            children[idx] = child;
            idx++;
        }
    }
    mysql_free_result(res);
    mysql_close(conn);

    *children_out = children;
    (void)depth_left;
    return idx;
}

/* Expand a "rule" node: find related learned rules by pattern */
int expand_rule(Node *node, Graph *g, int depth_left, Node ***children_out) {
    if (!node || !g || !children_out) return 0;

    MYSQL *conn = mysql_init(NULL);
    if (!conn) { *children_out = NULL; return 0; }
    if (!mysql_real_connect(conn, "localhost", "root", "", "vb_shared", 3306, NULL, 0)) {
        mysql_close(conn);
        *children_out = NULL;
        return 0;
    }

    char esc_name[GRAPH_MAX_NAME * 2 + 1];
    mysql_real_escape_string(conn, esc_name, node->name, (unsigned long)strlen(node->name));

    char sql[1024];
    snprintf(sql, sizeof(sql),
        "SELECT pattern, fix_action, confidence FROM vb_shared.learned_rules "
        "WHERE pattern LIKE '%%%s%%' LIMIT 20", esc_name);

    if (mysql_query(conn, sql)) { mysql_close(conn); *children_out = NULL; return 0; }
    MYSQL_RES *res = mysql_store_result(conn);
    if (!res) { mysql_close(conn); *children_out = NULL; return 0; }

    int count = (int)mysql_num_rows(res);
    if (count <= 0) { mysql_free_result(res); mysql_close(conn); *children_out = NULL; return 0; }

    Node **children = (Node **)calloc(count, sizeof(Node *));
    if (!children) { mysql_free_result(res); mysql_close(conn); *children_out = NULL; return 0; }

    int idx = 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        const char *pattern = row[0] ? row[0] : "";
        float confidence = row[2] ? (float)atof(row[2]) : 0.5f;
        char truncated[257];
        strncpy(truncated, pattern, 256);
        truncated[256] = '\0';
        Node *child = node_create(0, truncated, "rule", confidence);
        if (child) {
            children[idx] = child;
            idx++;
        }
    }
    mysql_free_result(res);
    mysql_close(conn);

    *children_out = children;
    (void)depth_left;
    return idx;
}

/* Expand a "token" node: find co-occurring tokens via graph_edges */
int expand_token(Node *node, Graph *g, int depth_left, Node ***children_out) {
    if (!node || !g || !children_out) return 0;

    MYSQL *conn = mysql_init(NULL);
    if (!conn) { *children_out = NULL; return 0; }
    if (!mysql_real_connect(conn, "localhost", "root", "", "vb_shared", 3306, NULL, 0)) {
        mysql_close(conn);
        *children_out = NULL;
        return 0;
    }

    char esc_name[GRAPH_MAX_NAME * 2 + 1];
    mysql_real_escape_string(conn, esc_name, node->name, (unsigned long)strlen(node->name));

    /* Step 1: find the token's node id in graph_nodes */
    char sql[1024];
    snprintf(sql, sizeof(sql),
        "SELECT id FROM vb_shared.graph_nodes "
        "WHERE name = '%s' AND node_type = 'tokens' LIMIT 1", esc_name);

    if (mysql_query(conn, sql)) { mysql_close(conn); *children_out = NULL; return 0; }
    MYSQL_RES *res = mysql_store_result(conn);
    if (!res) { mysql_close(conn); *children_out = NULL; return 0; }
    MYSQL_ROW row = mysql_fetch_row(res);
    if (!row || !row[0]) {
        mysql_free_result(res);
        mysql_close(conn);
        *children_out = NULL;
        return 0;
    }
    char node_id[64];
    strncpy(node_id, row[0], sizeof(node_id) - 1);
    node_id[sizeof(node_id) - 1] = '\0';
    mysql_free_result(res);

    /* Step 2: find co-occurring nodes via graph_edges */
    char sql2[1024];
    snprintf(sql2, sizeof(sql2),
        "SELECT gn.name, gn.node_type, ge.weight FROM vb_shared.graph_edges ge "
        "JOIN vb_shared.graph_nodes gn ON ge.to_node = gn.id "
        "WHERE ge.from_node = %s AND ge.edge_type = 'co_occurs' LIMIT 50", node_id);

    if (mysql_query(conn, sql2)) { mysql_close(conn); *children_out = NULL; return 0; }
    res = mysql_store_result(conn);
    if (!res) { mysql_close(conn); *children_out = NULL; return 0; }

    int count = (int)mysql_num_rows(res);
    if (count <= 0) { mysql_free_result(res); mysql_close(conn); *children_out = NULL; return 0; }

    Node **children = (Node **)calloc(count, sizeof(Node *));
    if (!children) { mysql_free_result(res); mysql_close(conn); *children_out = NULL; return 0; }

    int idx = 0;
    while ((row = mysql_fetch_row(res))) {
        const char *name = row[0] ? row[0] : "";
        const char *ntype = row[1] ? row[1] : "token";
        float weight = row[2] ? (float)atof(row[2]) : 0.5f;
        Node *child = node_create(0, name, ntype, weight);
        if (child) {
            children[idx] = child;
            idx++;
        }
    }
    mysql_free_result(res);
    mysql_close(conn);

    *children_out = children;
    (void)depth_left;
    return idx;
}

/* Expand a "chat" node: extract file paths mentioned */
int expand_chat(Node *node, Graph *g, int depth_left, Node ***children_out) {
    if (!node || !g || !children_out) return 0;

    MYSQL *conn = mysql_init(NULL);
    if (!conn) { *children_out = NULL; return 0; }
    if (!mysql_real_connect(conn, "localhost", "root", "", "bcl_ir", 3306, NULL, 0)) {
        mysql_close(conn);
        *children_out = NULL;
        return 0;
    }

    char esc_name[GRAPH_MAX_NAME * 2 + 1];
    mysql_real_escape_string(conn, esc_name, node->name, (unsigned long)strlen(node->name));

    char sql[1024];
    snprintf(sql, sizeof(sql),
        "SELECT DISTINCT file_path FROM bcl_ir.bcl_files "
        "WHERE file_path LIKE '%%%s%%' LIMIT 20", esc_name);

    if (mysql_query(conn, sql)) { mysql_close(conn); *children_out = NULL; return 0; }
    MYSQL_RES *res = mysql_store_result(conn);
    if (!res) { mysql_close(conn); *children_out = NULL; return 0; }

    int count = (int)mysql_num_rows(res);
    if (count <= 0) { mysql_free_result(res); mysql_close(conn); *children_out = NULL; return 0; }

    Node **children = (Node **)calloc(count, sizeof(Node *));
    if (!children) { mysql_free_result(res); mysql_close(conn); *children_out = NULL; return 0; }

    int idx = 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        const char *fpath = row[0] ? row[0] : "";
        /* Extract basename */
        char path_copy[GRAPH_MAX_NAME];
        strncpy(path_copy, fpath, sizeof(path_copy) - 1);
        path_copy[sizeof(path_copy) - 1] = '\0';
        char *base = basename(path_copy);
        Node *child = node_create(0, base ? base : fpath, "file", 0.3f);
        if (child) {
            children[idx] = child;
            idx++;
        }
    }
    mysql_free_result(res);
    mysql_close(conn);

    *children_out = children;
    (void)depth_left;
    return idx;
}

/* Register all built-in expansion functions */
void expand_register_all() {
    expand_register("class", expand_class);
    expand_register("method", expand_method);
    expand_register("rule", expand_rule);
    expand_register("token", expand_token);
    expand_register("chat", expand_chat);
}

/* ════════════════════════════════════════════
 * QUERY INTERFACE
 * ════════════════════════════════════════════ */

/* Start a traversal from a query string.
 * 1. Find matching nodes in the graph (or load from MySQL)
 * 2. Expand each matching node recursively
 * 3. Return the resulting subgraph */
int graph_query(Graph *g, const char *query, int max_depth) {
    if (!g || !query) return 0;

    /* Start executor timer */
    executor_start(&g->executor);

    /* Set depth limit */
    if (max_depth > 0) {
        g->policy.hard_limit = max_depth;
    }

    /* Register expansion functions */
    expand_register_all();

    /* Find matching nodes: first search existing graph, then query MySQL.
     * If we find matching nodes in the graph, expand them.
     * If the graph is empty or no matches, query MySQL to create seed nodes. */
    int total_expanded = 0;
    int matched_in_graph = 0;

    /* Phase 1: search existing nodes for substring match */
    int initial_count = g->node_count;
    for (int i = 0; i < initial_count && !executor_is_halted(&g->executor); i++) {
        Node *n = g->nodes[i];
        if (n && !n->expanded && strstr(n->name, query) != NULL) {
            total_expanded += graph_expand(g, n, g->policy.hard_limit);
            matched_in_graph++;
        }
    }

    /* Phase 2: if no matches in graph, query MySQL for seed nodes */
    if (matched_in_graph == 0) {
        MYSQL *conn = mysql_init(NULL);
        if (!conn) return total_expanded;
        if (!mysql_real_connect(conn, "localhost", "root", "", "bcl_ir", 3306, NULL, 0)) {
            mysql_close(conn);
            return total_expanded;
        }
        char esc_query[512];
        mysql_real_escape_string(conn, esc_query, query, (unsigned long)strlen(query));
        char sql[1024];
        snprintf(sql, sizeof(sql),
            "SELECT class_name, 'class' FROM bcl_classes WHERE class_name LIKE '%%%s%%' LIMIT 20",
            esc_query);
        if (mysql_query(conn, sql) == 0) {
            MYSQL_RES *res = mysql_store_result(conn);
            if (res) {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res))) {
                    const char *name = row[0] ? row[0] : "";
                    const char *type = row[1] ? row[1] : "class";
                    Node *seed = node_create(g->node_count, name, type, 0.5f);
                    if (seed) {
                        graph_add_node(g, seed);
                        total_expanded += graph_expand(g, seed, g->policy.hard_limit);
                    }
                }
                mysql_free_result(res);
            }
        }
        mysql_close(conn);
    }

    return total_expanded;
}

/* ════════════════════════════════════════════
 * RESULT EXPORT
 * ════════════════════════════════════════════ */

/* Export the graph as JSON (for Python/IDE to consume) */
void graph_export_json(Graph *g, char *buf, int buf_size) {
    if (!g || !buf) return;
    int pos = 0;
    pos += snprintf(buf + pos, buf_size - pos, "{\"nodes\":[");
    for (int i = 0; i < g->node_count && pos < buf_size - 100; i++) {
        Node *n = g->nodes[i];
        if (i > 0) pos += snprintf(buf + pos, buf_size - pos, ",");
        pos += snprintf(buf + pos, buf_size - pos,
            "{\"id\":%d,\"type\":\"%s\",\"name\":\"%s\",\"importance\":%.2f,\"expanded\":%d,\"depth\":%d}",
            n->id, n->type, n->name, n->importance, n->expanded, n->depth);
    }
    pos += snprintf(buf + pos, buf_size - pos, "],\"edges\":[");
    for (int i = 0; i < g->edge_count && pos < buf_size - 100; i++) {
        Edge *e = g->edges[i];
        if (i > 0) pos += snprintf(buf + pos, buf_size - pos, ",");
        pos += snprintf(buf + pos, buf_size - pos,
            "{\"source\":%d,\"target\":%d,\"rel\":\"%s\",\"weight\":%.2f}",
            e->source->id, e->target->id, e->rel_type, e->weight);
    }
    pos += snprintf(buf + pos, buf_size - pos, "]}");
}

/* ════════════════════════════════════════════
 * BCL DISPATCH LAYER
 * ════════════════════════════════════════════ */

/* Init — create the unit graph and register all built-in expanders */
int GraphExpand_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    strncpy(STATE.mysql_host, "localhost", sizeof(STATE.mysql_host) - 1);
    strncpy(STATE.mysql_user, "root", sizeof(STATE.mysql_user) - 1);
    strncpy(STATE.mysql_db, "vb_shared", sizeof(STATE.mysql_db) - 1);
    STATE.max_depth = GRAPH_MAX_DEPTH;

    STATE.graph = graph_create(256);
    if (!STATE.graph) {
        strncpy(STATE.last_error, "graph_create failed", sizeof(STATE.last_error) - 1);
        STATE.initialized = 1;
        return 0;
    }

    /* Apply MySQL config to the graph */
    strncpy(STATE.graph->mysql_host, STATE.mysql_host, sizeof(STATE.graph->mysql_host) - 1);
    strncpy(STATE.graph->mysql_user, STATE.mysql_user, sizeof(STATE.graph->mysql_user) - 1);
    strncpy(STATE.graph->mysql_db, STATE.mysql_db, sizeof(STATE.graph->mysql_db) - 1);

    /* Register built-in expansion functions */
    expand_register_all();
    STATE.registry_registered = 1;

    STATE.initialized = 1;
    return 1;
}

/* Run — dispatch BCL commands */
int GraphExpand_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) GraphExpand_Init();
    if (!cmd) {
        return BclResult_Err(bcl_out, out_sz, 50, "no command provided");
    }

    /* ===== EXPAND ===== */
    /* Expand a single node by name/type to a given depth. */
    if (strcmp(cmd, "expand") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char node_name[GRAPH_MAX_NAME] = {0};
        char node_type[GRAPH_MAX_TYPE] = {0};
        char depth_str[16] = {0};
        char imp_str[16] = {0};
        BclParser_Extract(&parse, "NODE", node_name, sizeof(node_name));
        BclParser_Extract(&parse, "TYPE", node_type, sizeof(node_type));
        BclParser_Extract(&parse, "DEPTH", depth_str, sizeof(depth_str));
        BclParser_Extract(&parse, "IMPORTANCE", imp_str, sizeof(imp_str));
        BclParser_Free(&parse);

        if (!node_name[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no NODE in packet");
        }
        if (!STATE.graph) {
            return BclResult_Err(bcl_out, out_sz, 10, "no graph allocated");
        }

        int depth = depth_str[0] ? atoi(depth_str) : STATE.max_depth;
        if (depth <= 0) depth = STATE.max_depth;

        /* Find existing node or create a new one */
        Node *n = graph_find_node(STATE.graph, node_name);
        if (!n) {
            int id = STATE.graph->node_count;
            float importance = imp_str[0] ? (float)atof(imp_str) : 0.5f;
            const char *type = node_type[0] ? node_type : "unknown";
            n = node_create(id, node_name, type, importance);
            if (!n) {
                return BclResult_Err(bcl_out, out_sz, 11, "node_create failed");
            }
            graph_add_node(STATE.graph, n);
            n = graph_find_node(STATE.graph, node_name);
            if (!n) {
                return BclResult_Err(bcl_out, out_sz, 12, "node not found after add");
            }
        }

        /* Ensure expanders are registered */
        if (!STATE.registry_registered) {
            expand_register_all();
            STATE.registry_registered = 1;
        }

        /* Start executor + run expansion */
        executor_start(&STATE.graph->executor);
        int expanded = graph_expand(STATE.graph, n, depth);

        STATE.expansions_run++;
        STATE.last_expanded_count = expanded;

        char body[256];
        snprintf(body, sizeof(body),
            "[@EXPANDED]{%d}[@NODES]{%d}[@EDGES]{%d}[@NODE]{%s}[@TYPE]{%s}[@DEPTH]{%d}",
            expanded, STATE.graph->node_count, STATE.graph->edge_count,
            node_name, node_type[0] ? node_type : "unknown", depth);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== QUERY ===== */
    /* Run a traversal from a query string across all matching nodes. */
    if (strcmp(cmd, "query") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[GRAPH_MAX_NAME] = {0};
        char depth_str[16] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "DEPTH", depth_str, sizeof(depth_str));
        BclParser_Free(&parse);

        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        if (!STATE.graph) {
            return BclResult_Err(bcl_out, out_sz, 10, "no graph allocated");
        }

        int depth = depth_str[0] ? atoi(depth_str) : STATE.max_depth;
        if (depth <= 0) depth = STATE.max_depth;

        int expanded = graph_query(STATE.graph, query, depth);

        STATE.queries_run++;
        STATE.last_expanded_count = expanded;

        char body[256];
        snprintf(body, sizeof(body),
            "[@EXPANDED]{%d}[@NODES]{%d}[@EDGES]{%d}[@QUERY]{%s}",
            expanded, STATE.graph->node_count, STATE.graph->edge_count, query);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== EXPORT_JSON ===== */
    /* Dump the current graph as JSON for Python/IDE consumption. */
    if (strcmp(cmd, "export_json") == 0) {
        if (!STATE.graph) {
            return BclResult_Err(bcl_out, out_sz, 10, "no graph allocated");
        }
        char *jsonbuf = (char *)malloc(EXPAND_BUF_SIZE);
        if (!jsonbuf) {
            return BclResult_Err(bcl_out, out_sz, 11, "json buffer alloc failed");
        }
        graph_export_json(STATE.graph, jsonbuf, EXPAND_BUF_SIZE);

        /* Wrap JSON in a BCL OK packet */
        int header_len = snprintf(bcl_out, out_sz, "[@OK]{[@JSON]{");
        int json_len = (int)strlen(jsonbuf);
        int trailer_len = (int)strlen("}}");
        if (header_len + json_len + trailer_len + 1 > (int)out_sz) {
            free(jsonbuf);
            return BclResult_Err(bcl_out, out_sz, 30, "json output too large for packet");
        }
        memcpy(bcl_out + header_len, jsonbuf, json_len);
        memcpy(bcl_out + header_len + json_len, "}}", trailer_len);
        bcl_out[header_len + json_len + trailer_len] = '\0';
        free(jsonbuf);
        return 1;
    }

    /* ===== REGISTER_ALL ===== */
    /* Re-register all built-in expansion functions. */
    if (strcmp(cmd, "register_all") == 0) {
        expand_register_all();
        STATE.registry_registered = 1;
        char body[256];
        snprintf(body, sizeof(body),
            "[@STATUS]{registered}[@COUNT]{%d}[@TYPES]{class,method,rule,token,chat}",
            registry_count);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@GRAPH]{%d}[@NODES]{%d}[@EDGES]{%d}[@REGISTRY]{%d}[@EXPANSIONS]{%d}[@QUERIES]{%d}[@LAST_EXPANDED]{%d}[@MAX_DEPTH]{%d}[@ERROR]{%s}",
            STATE.initialized,
            STATE.graph ? 1 : 0,
            STATE.graph ? STATE.graph->node_count : 0,
            STATE.graph ? STATE.graph->edge_count : 0,
            STATE.registry_registered,
            STATE.expansions_run,
            STATE.queries_run,
            STATE.last_expanded_count,
            STATE.max_depth,
            STATE.last_error[0] ? STATE.last_error : "none");
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== SET_CONFIG ===== */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char host[256] = {0};
        char user[64] = {0};
        char db[64] = {0};
        char depth_str[16] = {0};
        BclParser_Extract(&parse, "HOST", host, sizeof(host));
        BclParser_Extract(&parse, "USER", user, sizeof(user));
        BclParser_Extract(&parse, "DB", db, sizeof(db));
        BclParser_Extract(&parse, "MAX_DEPTH", depth_str, sizeof(depth_str));
        BclParser_Free(&parse);

        if (host[0]) strncpy(STATE.mysql_host, host, sizeof(STATE.mysql_host) - 1);
        if (user[0]) strncpy(STATE.mysql_user, user, sizeof(STATE.mysql_user) - 1);
        if (db[0])   strncpy(STATE.mysql_db, db, sizeof(STATE.mysql_db) - 1);
        if (depth_str[0]) {
            int d = atoi(depth_str);
            if (d > 0) STATE.max_depth = d;
        }

        /* Propagate config to the live graph */
        if (STATE.graph) {
            strncpy(STATE.graph->mysql_host, STATE.mysql_host, sizeof(STATE.graph->mysql_host) - 1);
            strncpy(STATE.graph->mysql_user, STATE.mysql_user, sizeof(STATE.graph->mysql_user) - 1);
            strncpy(STATE.graph->mysql_db, STATE.mysql_db, sizeof(STATE.graph->mysql_db) - 1);
        }

        char body[512];
        snprintf(body, sizeof(body),
            "[@HOST]{%s}[@USER]{%s}[@DB]{%s}[@MAX_DEPTH]{%d}",
            STATE.mysql_host, STATE.mysql_user, STATE.mysql_db, STATE.max_depth);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    return BclResult_Err(bcl_out, out_sz, 404, "unknown command");
}

/* Close — free the unit graph and reset state */
int GraphExpand_Close(void) {
    if (STATE.graph) {
        graph_free(STATE.graph);
        STATE.graph = NULL;
    }
    STATE.registry_registered = 0;
    STATE.initialized = 0;
    STATE.expansions_run = 0;
    STATE.queries_run = 0;
    STATE.last_expanded_count = 0;
    STATE.last_error[0] = '\0';
    return 1;
}

/* State — return a human-readable status string */
const char * GraphExpand_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "GraphExpand: initialized=%d graph=%d nodes=%d edges=%d expansions=%d queries=%d",
        STATE.initialized,
        STATE.graph ? 1 : 0,
        STATE.graph ? STATE.graph->node_count : 0,
        STATE.graph ? STATE.graph->edge_count : 0,
        STATE.expansions_run,
        STATE.queries_run);
    return buf;
}
