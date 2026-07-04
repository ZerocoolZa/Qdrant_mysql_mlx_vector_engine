// GraphExpand — recursive expansion engine for the Max Graph Engine
// This is the core: nodes expand themselves via function pointers, recursively,
// with policy checks (should we expand?) and executor checks (can we afford it?)

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// === Expansion function registry ===
// Maps node type names to expansion functions
typedef struct ExpandRegistry {
    char type_name[32];
    ExpandFn fn;
} ExpandRegistry;

static ExpandRegistry registry[32];
static int registry_count = 0;

// Register an expansion function for a node type
int expand_register(const char *node_type, ExpandFn fn) {
    if (!node_type || !fn) return -1;
    if (registry_count >= 32) return -1;
    strncpy(registry[registry_count].type_name, node_type, sizeof(registry[registry_count].type_name) - 1);
    registry[registry_count].fn = fn;
    registry_count++;
    return 0;
}

// Get the expansion function for a node type
ExpandFn expand_lookup(const char *node_type) {
    if (!node_type) return NULL;
    for (int i = 0; i < registry_count; i++) {
        if (strcmp(registry[i].type_name, node_type) == 0) {
            return registry[i].fn;
        }
    }
    return NULL;
}

// === Core recursive expansion ===

// Expand a single node: call its expansion function, then recursively expand children
// This is THE function that makes the graph recursive and generative
int graph_expand(Graph *g, Node *node, int depth_left) {
    if (!g || !node) return 0;
    
    // 1. Check executor — can we afford to continue?
    if (executor_check(&g->executor)) return 0;
    
    // 2. Check policy — should this node expand?
    int nodes_this_hop = 0;  // simplified — real version would track per-hop count
    if (!policy_should_expand(&g->policy, node, node->depth, nodes_this_hop, g->node_count)) {
        return 0;
    }
    
    // 3. Charge the cost
    executor_charge(&g->executor, node->cost);
    
    // 4. Mark as expanded
    node->expanded = 1;
    
    // 5. If node has no expand function, try to look one up by type
    if (!node->expand) {
        node->expand = expand_lookup(node->type);
    }
    
    // 6. If still no expand function, this is a leaf — stop
    if (!node->expand) {
        return 0;
    }
    
    // 7. Call the node's OWN expansion function
    //    This is where the magic happens — the node knows how to expand itself
    Node *children = NULL;
    int n_children = node->expand(node, g, depth_left - 1, &children);
    
    if (n_children <= 0 || !children) {
        return 0;
    }
    
    // 8. Add children to graph and recursively expand them
    //    This is LAZY expansion — only expand children that pass the policy check
    int expanded_count = 0;
    for (int i = 0; i < n_children; i++) {
        Node *child = &children[i];
        child->depth = node->depth + 1;
        
        // Add child to graph
        graph_add_node(g, child);
        
        // Create edge from parent to child
        char rel[64];
        snprintf(rel, sizeof(rel), "EXPANDS_TO");
        Edge *e = edge_create(g->edge_count, node, child, rel, child->importance);
        graph_add_edge(g, e);
        
        // Recursively expand the child (if depth allows and policy says yes)
        if (depth_left > 1) {
            expanded_count += graph_expand(g, child, depth_left - 1);
        }
    }
    
    // 9. Free the children array (the nodes themselves are now in the graph)
    free(children);
    
    return expanded_count + n_children;
}

// === Built-in expansion functions ===

// Expand a "class" node: load its methods from MySQL and create child nodes
// This is a placeholder — real implementation would query MySQL
int expand_class(Node *node, Graph *g, int depth_left, Node **children_out) {
    if (!node || !g || !children_out) return 0;
    ClassData *data = (ClassData *)node->data;
    if (!data) return 0;
    
    // Placeholder: in real implementation, query MySQL for methods of this class
    // For now, return 0 children (leaf)
    *children_out = NULL;
    return 0;
}

// Expand a "method" node: load its callers and callees from BCL edges
int expand_method(Node *node, Graph *g, int depth_left, Node **children_out) {
    if (!node || !g || !children_out) return 0;
    MethodData *data = (MethodData *)node->data;
    if (!data) return 0;
    
    // Placeholder: in real implementation, query bcl_ir.bcl_edges for CALL edges
    *children_out = NULL;
    return 0;
}

// Expand a "rule" node: find the chat it originated from
int expand_rule(Node *node, Graph *g, int depth_left, Node **children_out) {
    if (!node || !g || !children_out) return 0;
    RuleData *data = (RuleData *)node->data;
    if (!data) return 0;
    
    // Placeholder: query vb_shared.learned_rules for origin chat
    *children_out = NULL;
    return 0;
}

// Expand a "token" node: find co-occurring tokens
int expand_token(Node *node, Graph *g, int depth_left, Node **children_out) {
    if (!node || !g || !children_out) return 0;
    
    // Placeholder: query vb_shared.graph_edges for CO_OCCURS edges
    *children_out = NULL;
    return 0;
}

// Expand a "chat" node: extract file paths and classes mentioned
int expand_chat(Node *node, Graph *g, int depth_left, Node **children_out) {
    if (!node || !g || !children_out) return 0;
    
    // Placeholder: extract file paths from chat content, create file nodes
    *children_out = NULL;
    return 0;
}

// Register all built-in expansion functions
void expand_register_all() {
    expand_register("class", expand_class);
    expand_register("method", expand_method);
    expand_register("rule", expand_rule);
    expand_register("token", expand_token);
    expand_register("chat", expand_chat);
}

// === Query interface ===

// Start a traversal from a query string
// 1. Find matching nodes in the graph (or load from MySQL)
// 2. Expand each matching node recursively
// 3. Return the resulting subgraph
int graph_query(Graph *g, const char *query, int max_depth) {
    if (!g || !query) return 0;
    
    // Start executor timer
    executor_start(&g->executor);
    
    // Set depth limit
    if (max_depth > 0) {
        g->policy.hard_limit = max_depth;
    }
    
    // Register expansion functions
    expand_register_all();
    
    // Find matching nodes (placeholder — real version queries MySQL)
    // For now, just expand all existing nodes
    int total_expanded = 0;
    int initial_count = g->node_count;
    for (int i = 0; i < initial_count && !executor_is_halted(&g->executor); i++) {
        Node *n = g->nodes[i];
        if (n && !n->expanded) {
            total_expanded += graph_expand(g, n, g->policy.hard_limit);
        }
    }
    
    return total_expanded;
}

// === Result export ===

// Export the graph as JSON (for Python/IDE to consume)
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
