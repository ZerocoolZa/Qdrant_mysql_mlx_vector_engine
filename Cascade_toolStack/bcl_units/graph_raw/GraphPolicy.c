// GraphPolicy — policy layer for the Max Graph Engine
// Decides whether a node should expand based on hard limit, context, and attention

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

// Get current time in milliseconds
static long current_time_ms() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}

// Check if the executor has exceeded its limits
int executor_check(Executor *ex) {
    if (!ex) return 1;
    if (ex->halted) return 1;
    // Check timeout
    if (ex->start_time_ms > 0) {
        long elapsed = current_time_ms() - ex->start_time_ms;
        if (elapsed > ex->timeout_ms) {
            ex->halted = 1;
            return 1;
        }
    }
    // Check cost
    if (ex->cost_used >= ex->cost_limit) {
        ex->halted = 1;
        return 1;
    }
    // Check memory (rough estimate: node_count * sizeof(Node))
    // This is a simple check — real implementation would track allocations
    return 0;
}

// Charge cost to executor
void executor_charge(Executor *ex, float cost) {
    if (!ex) return;
    ex->cost_used += (int)cost;
}

// Start the executor timer
void executor_start(Executor *ex) {
    if (!ex) return;
    ex->start_time_ms = current_time_ms();
    ex->cost_used = 0;
    ex->halted = 0;
}

// Check if executor is halted
int executor_is_halted(Executor *ex) {
    return ex ? ex->halted : 1;
}

// Get elapsed time in ms
long executor_elapsed_ms(Executor *ex) {
    if (!ex || ex->start_time_ms == 0) return 0;
    return current_time_ms() - ex->start_time_ms;
}

// === Policy checks ===

// Should this node be expanded?
// Returns 1 if yes, 0 if no
int policy_should_expand(Policy *p, Node *n, int current_depth, int nodes_this_hop, int total_nodes) {
    if (!p || !n) return 0;
    
    // 1. Hard depth limit
    int depth_limit = p->hard_limit;
    if (p->context_limit > 0) {
        depth_limit = p->context_limit;  // context overrides hard
    }
    if (current_depth >= depth_limit) return 0;
    
    // 2. Attention threshold — only expand important enough nodes
    if (n->importance < p->attention_threshold) return 0;
    
    // 3. Max nodes per hop
    if (nodes_this_hop >= p->max_nodes_per_hop) return 0;
    
    // 4. Max total nodes
    if (total_nodes >= p->max_total_nodes) return 0;
    
    // 5. Already expanded
    if (n->expanded) return 0;
    
    return 1;
}

// Set context-specific depth limit
void policy_set_context(Policy *p, const char *context_name) {
    if (!p || !context_name) return;
    // Context-specific depth limits
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
        p->context_limit = 0;  // use hard_limit
    }
}

// Compute importance for a node based on frequency, centrality, recency
float policy_compute_importance(Node *n, float frequency, float centrality, float recency) {
    if (!n) return 0.0;
    // Weighted sum: 40% frequency, 30% centrality, 30% recency
    float importance = 0.4 * frequency + 0.3 * centrality + 0.3 * recency;
    if (importance > 1.0) importance = 1.0;
    if (importance < 0.0) importance = 0.0;
    n->importance = importance;
    return importance;
}

// Get effective depth limit (context or hard)
int policy_get_depth_limit(Policy *p) {
    if (!p) return 0;
    return p->context_limit > 0 ? p->context_limit : p->hard_limit;
}

// Print policy state (for debugging)
void policy_dump(Policy *p, char *buf, int buf_size) {
    if (!p || !buf) return;
    snprintf(buf, buf_size,
        "Policy{hard=%d, ctx=%d, attention=%.2f, max_per_hop=%d, max_total=%d}",
        p->hard_limit, p->context_limit, p->attention_threshold,
        p->max_nodes_per_hop, p->max_total_nodes);
}

// Print executor state (for debugging)
void executor_dump(Executor *ex, char *buf, int buf_size) {
    if (!ex || !buf) return;
    snprintf(buf, buf_size,
        "Executor{mem=%zu/%zu, cost=%d/%d, timeout=%dms, elapsed=%ldms, halted=%d}",
        ex->memory_used, ex->memory_budget,
        ex->cost_used, ex->cost_limit,
        ex->timeout_ms, executor_elapsed_ms(ex), ex->halted);
}
