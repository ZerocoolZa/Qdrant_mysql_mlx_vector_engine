// GraphOptimizer — Optimizer for the Max Graph Engine
// Takes a naive Plan and optimizes it: pruning, dedup, cost reorder, adaptive depth
// Uses 3-part scoring: RuleScore + LearnedScore + StructuralScore
// Execution Plan becomes a PRIORITY QUEUE, not a tree

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// === Scoring weights (configurable) ===
#define RULE_WEIGHT 0.4       // alpha
#define LEARNED_WEIGHT 0.3    // beta
#define STRUCTURAL_WEIGHT 0.3 // gamma

// === Scored step — a plan step with a computed score ===
typedef struct ScoredStep {
    int step_index;           // index into Plan.steps
    float rule_score;         // deterministic constraints
    float learned_score;      // adaptive intelligence (placeholder)
    float structural_score;   // graph topology
    float final_score;        // weighted sum
} ScoredStep;

// === Part 1: RuleScore (deterministic) ===

float score_rule(Node *n, View *v, int depth) {
    if (!n || !v) return 0.0;
    float score = 0.0;
    // Relevance match — does the view have rules for this node type?
    int rule_count = 0;
    ViewRule *rules = view_find_rules(v, n->type, &rule_count);
    if (rules) free(rules);
    if (rule_count > 0) {
        score += 1.0;  // relevant
    } else {
        score -= 0.5;  // not relevant to this view
    }
    // Depth penalty — deeper = lower score
    score -= 0.1 * depth;
    // Cost estimate — expensive = lower score
    float cost = view_compute_cost(v, n, depth);
    score -= cost * 0.05;
    // Importance boost
    score += n->importance * 0.5;
    return score;
}

// === Part 2: LearnedScore (adaptive — placeholder for now) ===

float score_learned(Node *n) {
    if (!n) return 0.0;
    // Placeholder: in real implementation, this would query a learned model
    // For now, use node importance as a proxy
    return n->importance * 0.5;
}

// === Part 3: StructuralScore (graph topology) ===

// Count edges from a node (fanout)
int node_fanout(Node *n) {
    if (!n) return 0;
    int count = 0;
    Edge *e = n->first_edge;
    while (e) {
        count++;
        e = e->next;
    }
    return count;
}

// Check if node is a bridge (connects different parts of the graph)
int node_is_bridge(Node *n, Graph *g) {
    if (!n || !g) return 0;
    // Simple heuristic: if node has edges to multiple different node types
    int type_count = 0;
    char types_seen[32][32];
    Edge *e = n->first_edge;
    while (e) {
        if (e->target) {
            int found = 0;
            for (int i = 0; i < type_count; i++) {
                if (strcmp(types_seen[i], e->target->type) == 0) {
                    found = 1;
                    break;
                }
            }
            if (!found && type_count < 32) {
                strncpy(types_seen[type_count], e->target->type, 31);
                type_count++;
            }
        }
        e = e->next;
    }
    return type_count >= 2;  // connects 2+ different types = bridge
}

float score_structural(Node *n, Graph *g) {
    if (!n) return 0.0;
    float score = 0.0;
    // Betweenness centrality (simplified: bridge nodes are important)
    if (node_is_bridge(n, g)) {
        score += 0.5;
    }
    // Dependency depth — nodes deeper in dependency chains are valuable
    score += (n->depth * 0.1);
    // Fanout penalty — too many children = less focused
    int fanout = node_fanout(n);
    if (fanout > 50) {
        score -= 0.3;  // high fanout = less interesting per child
    } else if (fanout > 0) {
        score += 0.1 * (fanout < 10 ? fanout : 10) / 10.0;  // moderate fanout = good
    }
    // Isolation penalty — nodes with no edges are dead ends
    if (fanout == 0) {
        score -= 0.2;
    }
    return score;
}

// === Final score computation ===

float compute_final_score(Node *n, View *v, Graph *g, int depth,
                          float *rule_out, float *learned_out, float *struct_out) {
    float rs = score_rule(n, v, depth);
    float ls = score_learned(n);
    float ss = score_structural(n, g);
    float final = RULE_WEIGHT * rs + LEARNED_WEIGHT * ls + STRUCTURAL_WEIGHT * ss;
    if (rule_out) *rule_out = rs;
    if (learned_out) *learned_out = ls;
    if (struct_out) *struct_out = ss;
    return final;
}

// === Optimizer operations ===

// Pruning — remove steps with negative final score
int optimize_prune(Plan *p, Graph *g, View *v) {
    if (!p || !g || !v) return 0;
    int pruned = 0;
    for (int i = 0; i < p->step_count; i++) {
        PlanStep *s = &p->steps[i];
        Node *n = graph_find_node_by_id(g, s->node_id);
        if (!n) continue;
        float rs, ls, ss;
        float final = compute_final_score(n, v, g, s->depth, &rs, &ls, &ss);
        if (final < 0.0) {
            // Mark as pruned (set cost to -1 as sentinel)
            s->estimated_cost = -1.0;
            pruned++;
        }
    }
    return pruned;
}

// Deduplication — remove duplicate steps (same node at same depth)
int optimize_dedup(Plan *p) {
    if (!p) return 0;
    int deduped = 0;
    for (int i = 0; i < p->step_count; i++) {
        if (p->steps[i].estimated_cost < 0) continue;  // already pruned
        for (int j = i + 1; j < p->step_count; j++) {
            if (p->steps[j].estimated_cost < 0) continue;
            if (p->steps[i].node_id == p->steps[j].node_id &&
                p->steps[i].depth == p->steps[j].depth) {
                // Duplicate — prune the second one
                p->steps[j].estimated_cost = -1.0;
                deduped++;
            }
        }
    }
    return deduped;
}

// Cost reordering — sort steps by final score (highest first)
int optimize_reorder(Plan *p, Graph *g, View *v) {
    if (!p || !g || !v) return 0;
    // Compute scores for all non-pruned steps
    ScoredStep *scored = (ScoredStep *)calloc(p->step_count, sizeof(ScoredStep));
    if (!scored) return -1;
    int valid_count = 0;
    for (int i = 0; i < p->step_count; i++) {
        if (p->steps[i].estimated_cost < 0) continue;  // pruned
        Node *n = graph_find_node_by_id(g, p->steps[i].node_id);
        if (!n) continue;
        scored[valid_count].step_index = i;
        scored[valid_count].final_score = compute_final_score(n, v, g, p->steps[i].depth,
            &scored[valid_count].rule_score,
            &scored[valid_count].learned_score,
            &scored[valid_count].structural_score);
        valid_count++;
    }
    // Sort by final score (descending — highest first)
    for (int i = 0; i < valid_count - 1; i++) {
        for (int j = i + 1; j < valid_count; j++) {
            if (scored[j].final_score > scored[i].final_score) {
                ScoredStep tmp = scored[i];
                scored[i] = scored[j];
                scored[j] = tmp;
            }
        }
    }
    // Reorder plan steps based on sorted scores
    PlanStep *new_steps = (PlanStep *)calloc(p->step_count, sizeof(PlanStep));
    int new_idx = 0;
    // First: scored steps in priority order
    for (int i = 0; i < valid_count; i++) {
        new_steps[new_idx++] = p->steps[scored[i].step_index];
    }
    // Then: pruned steps (at the end, marked with -1 cost)
    for (int i = 0; i < p->step_count; i++) {
        if (p->steps[i].estimated_cost < 0) {
            new_steps[new_idx++] = p->steps[i];
        }
    }
    // Copy back
    memcpy(p->steps, new_steps, p->step_count * sizeof(PlanStep));
    free(new_steps);
    free(scored);
    return valid_count;
}

// Adaptive depth — increase depth for high-value nodes, decrease for low-value
int optimize_adaptive_depth(Plan *p, Graph *g, View *v) {
    if (!p || !g || !v) return 0;
    int adjusted = 0;
    for (int i = 0; i < p->step_count; i++) {
        if (p->steps[i].estimated_cost < 0) continue;  // pruned
        Node *n = graph_find_node_by_id(g, p->steps[i].node_id);
        if (!n) continue;
        float rs, ls, ss;
        float final = compute_final_score(n, v, g, p->steps[i].depth, &rs, &ls, &ss);
        // High-value nodes get deeper expansion
        if (final > 0.8 && p->steps[i].depth < v->stop.max_depth) {
            p->steps[i].depth = p->steps[i].depth + 1;  // allow one more level
            adjusted++;
        }
        // Low-value nodes get shallower
        if (final < 0.3 && p->steps[i].depth > 1) {
            p->steps[i].depth = p->steps[i].depth - 1;
            adjusted++;
        }
    }
    return adjusted;
}

// === Main optimizer function ===

// optimize_plan: takes a naive plan and returns an optimized one
int optimize_plan(Plan *p, Graph *g, View *v) {
    if (!p || !g || !v) return -1;
    int pruned = optimize_prune(p, g, v);
    int deduped = optimize_dedup(p);
    int reordered = optimize_reorder(p, g, v);
    int depth_adjusted = optimize_adaptive_depth(p, g, v);
    return pruned + deduped + depth_adjusted;
}

// === Priority queue execution ===

// Execute the optimized plan — highest score first
int execute_plan(Plan *p, Graph *g, View *v) {
    if (!p || !g || !v) return -1;
    p->executed = 1;
    int total_expanded = 0;
    // Execute steps in priority order (already sorted by optimize_reorder)
    for (int i = 0; i < p->step_count; i++) {
        // Check guard
        if (plan_check_guard(p)) break;
        // Skip pruned steps
        if (p->steps[i].estimated_cost < 0) continue;
        // Find node
        Node *n = graph_find_node_by_id(g, p->steps[i].node_id);
        if (!n || n->expanded) continue;
        // Charge cost
        p->budget_used += (int)p->steps[i].estimated_cost;
        p->node_count++;
        // Mark as expanded
        n->expanded = 1;
        total_expanded++;
        // In real implementation, call the expansion function here
        // and add children as new steps
    }
    return total_expanded;
}

// === Optimizer dump (for debugging) ===

void optimizer_dump_scores(Plan *p, Graph *g, View *v, char *buf, int buf_size) {
    if (!p || !g || !v || !buf) return;
    int pos = 0;
    pos += snprintf(buf + pos, buf_size - pos, "Optimizer scores:
");
    for (int i = 0; i < p->step_count && pos < buf_size - 200; i++) {
        if (p->steps[i].estimated_cost < 0) {
            pos += snprintf(buf + pos, buf_size - pos, "  step[%d]: PRUNED
", i);
            continue;
        }
        Node *n = graph_find_node_by_id(g, p->steps[i].node_id);
        if (!n) continue;
        float rs, ls, ss;
        float final = compute_final_score(n, v, g, p->steps[i].depth, &rs, &ls, &ss);
        pos += snprintf(buf + pos, buf_size - pos,
            "  step[%d]: %s score=%.2f (rule=%.2f, learned=%.2f, structural=%.2f)
",
            i, n->name, final, rs, ls, ss);
    }
}
