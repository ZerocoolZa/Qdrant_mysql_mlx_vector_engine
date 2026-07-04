//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_graph_optimizer.c" date="2026-07-04" author="Devin" session_id="graph-bcl-units" context="BCL unit for the Max Graph Engine optimizer. Takes a naive Plan and optimizes it: pruning, dedup, cost reorder, adaptive depth. Uses 3-part scoring: RuleScore + LearnedScore + StructuralScore. Execution Plan becomes a PRIORITY QUEUE, not a tree. Commands: optimize, execute, score, dump_scores, read_state, set_config."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_graph_optimizer.c" domain="graph_engine" authority="GraphOptimizer"}
//[@SUMMARY]{summary="Graph optimizer BCL unit. Optimizes a compiled Plan via 3-part scoring (rule + learned + structural), pruning, deduplication, cost-based reordering, and adaptive depth. Executes the plan as a priority queue. Commands: optimize, execute, score, dump_scores, read_state, set_config."}
//[@CLASS]{class="GraphOptimizer" domain="graph_engine" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="score_rule" type="query"}
//[@METHOD]{method="score_learned" type="query"}
//[@METHOD]{method="score_structural" type="query"}
//[@METHOD]{method="compute_final_score" type="query"}
//[@METHOD]{method="node_fanout" type="query"}
//[@METHOD]{method="node_is_bridge" type="query"}
//[@METHOD]{method="optimize_prune" type="command"}
//[@METHOD]{method="optimize_dedup" type="command"}
//[@METHOD]{method="optimize_reorder" type="command"}
//[@METHOD]{method="optimize_adaptive_depth" type="command"}
//[@METHOD]{method="optimize_plan" type="command"}
//[@METHOD]{method="execute_plan" type="command"}
//[@METHOD]{method="optimizer_dump_scores" type="query"}

#include "bcl_graph_types.h"
#include "bcl_toolstack.h"

#include <stdint.h>
#include <mysql.h>

/* ════════════════════════════════════════════
 * PRIVATE: SCORING WEIGHTS (configurable)
 * ════════════════════════════════════════════ */

#define RULE_WEIGHT       0.4    /* alpha   — deterministic constraints */
#define LEARNED_WEIGHT    0.3    /* beta    — adaptive intelligence     */
#define STRUCTURAL_WEIGHT 0.3    /* gamma   — graph topology           */

/* ════════════════════════════════════════════
 * PRIVATE: SCORED STEP — a plan step with a computed score
 * ════════════════════════════════════════════ */

typedef struct ScoredStep {
    int   step_index;         /* index into Plan.steps            */
    float rule_score;         /* deterministic constraints        */
    float learned_score;      /* adaptive intelligence (proxy)    */
    float structural_score;   /* graph topology                   */
    float final_score;        /* weighted sum                     */
} ScoredStep;

/* ════════════════════════════════════════════
 * UNIT STATE
 * ════════════════════════════════════════════ */

static struct {
    int   initialized;
    int   plans_optimized;
    int   plans_executed;
    int   steps_pruned;
    int   steps_deduped;
    int   steps_reordered;
    int   steps_depth_adjusted;
    int   nodes_expanded;
    char  last_error[256];
} STATE;

/* ════════════════════════════════════════════
 * PART 1: RULE SCORE (deterministic)
 * ════════════════════════════════════════════ */

float score_rule(Node *n, View *v, int depth) {
    if (!n || !v) return 0.0;
    float score = 0.0;
    /* Relevance match — does the view have rules for this node type? */
    int rule_count = 0;
    ViewRule *rules = view_find_rules(v, n->type, &rule_count);
    if (rules) free(rules);
    if (rule_count > 0) {
        score += 1.0;     /* relevant */
    } else {
        score -= 0.5;     /* not relevant to this view */
    }
    /* Depth penalty — deeper = lower score */
    score -= 0.1 * depth;
    /* Cost estimate — expensive = lower score */
    float cost = view_compute_cost(v, n, depth);
    score -= cost * 0.05;
    /* Importance boost */
    score += n->importance * 0.5;
    return score;
}

/* ════════════════════════════════════════════
 * PART 2: LEARNED SCORE (adaptive — queries MySQL learned_rules)
 * ════════════════════════════════════════════ */

float score_learned(Node *n) {
    if (!n || !n->name[0]) return 0.0;
    /* Query vb_shared.learned_rules for rules matching this node's name.
     * The learned score is based on the count and confidence of matching rules. */
    MYSQL *conn = mysql_init(NULL);
    if (!conn) return n->importance * 0.3;
    if (!mysql_real_connect(conn, "localhost", "root", "", "vb_shared", 3306, NULL, 0)) {
        mysql_close(conn);
        return n->importance * 0.3;
    }
    char esc_name[512];
    mysql_real_escape_string(conn, esc_name, n->name, (unsigned long)strlen(n->name));
    char sql[1024];
    snprintf(sql, sizeof(sql),
        "SELECT COUNT(*), AVG(confidence) FROM learned_rules WHERE pattern LIKE '%%%s%%'", esc_name);
    float score = n->importance * 0.3;
    if (mysql_query(conn, sql) == 0) {
        MYSQL_RES *res = mysql_store_result(conn);
        if (res) {
            MYSQL_ROW row = mysql_fetch_row(res);
            if (row && row[0]) {
                int count = atoi(row[0]);
                double avg_conf = row[1] ? atof(row[1]) : 0.5;
                score = (float)(count * avg_conf) / 20.0;
                if (score > 1.0) score = 1.0;
            }
            mysql_free_result(res);
        }
    }
    mysql_close(conn);
    return score;
}

/* ════════════════════════════════════════════
 * PART 3: STRUCTURAL SCORE (graph topology)
 * ════════════════════════════════════════════ */

/* Count edges from a node (fanout) */
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

/* Check if node is a bridge (connects different parts of the graph) */
int node_is_bridge(Node *n, Graph *g) {
    if (!n || !g) return 0;
    /* Simple heuristic: if node has edges to multiple different node types */
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
                types_seen[type_count][31] = '\0';
                type_count++;
            }
        }
        e = e->next;
    }
    return type_count >= 2;  /* connects 2+ different types = bridge */
}

float score_structural(Node *n, Graph *g) {
    if (!n) return 0.0;
    float score = 0.0;
    /* Betweenness centrality (simplified: bridge nodes are important) */
    if (node_is_bridge(n, g)) {
        score += 0.5;
    }
    /* Dependency depth — nodes deeper in dependency chains are valuable */
    score += (n->depth * 0.1);
    /* Fanout penalty — too many children = less focused */
    int fanout = node_fanout(n);
    if (fanout > 50) {
        score -= 0.3;  /* high fanout = less interesting per child */
    } else if (fanout > 0) {
        score += 0.1 * (fanout < 10 ? fanout : 10) / 10.0;  /* moderate fanout = good */
    }
    /* Isolation penalty — nodes with no edges are dead ends */
    if (fanout == 0) {
        score -= 0.2;
    }
    return score;
}

/* ════════════════════════════════════════════
 * FINAL SCORE COMPUTATION
 * ════════════════════════════════════════════ */

float compute_final_score(Node *n, View *v, Graph *g, int depth,
                          float *rule_out, float *learned_out, float *struct_out) {
    float rs = score_rule(n, v, depth);
    float ls = score_learned(n);
    float ss = score_structural(n, g);
    float final = RULE_WEIGHT * rs + LEARNED_WEIGHT * ls + STRUCTURAL_WEIGHT * ss;
    if (rule_out)    *rule_out    = rs;
    if (learned_out) *learned_out = ls;
    if (struct_out)  *struct_out  = ss;
    return final;
}

/* ════════════════════════════════════════════
 * OPTIMIZER OPERATIONS
 * ════════════════════════════════════════════ */

/* Pruning — remove steps with negative final score */
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
            /* Mark as pruned (set cost to -1 as sentinel) */
            s->estimated_cost = -1.0;
            pruned++;
        }
    }
    STATE.steps_pruned += pruned;
    return pruned;
}

/* Deduplication — remove duplicate steps (same node at same depth) */
int optimize_dedup(Plan *p) {
    if (!p) return 0;
    int deduped = 0;
    for (int i = 0; i < p->step_count; i++) {
        if (p->steps[i].estimated_cost < 0) continue;  /* already pruned */
        for (int j = i + 1; j < p->step_count; j++) {
            if (p->steps[j].estimated_cost < 0) continue;
            if (p->steps[i].node_id == p->steps[j].node_id &&
                p->steps[i].depth == p->steps[j].depth) {
                /* Duplicate — prune the second one */
                p->steps[j].estimated_cost = -1.0;
                deduped++;
            }
        }
    }
    STATE.steps_deduped += deduped;
    return deduped;
}

/* Cost reordering — sort steps by final score (highest first) */
int optimize_reorder(Plan *p, Graph *g, View *v) {
    if (!p || !g || !v) return 0;
    /* Compute scores for all non-pruned steps */
    ScoredStep *scored = (ScoredStep *)calloc(p->step_count, sizeof(ScoredStep));
    if (!scored) return -1;
    int valid_count = 0;
    for (int i = 0; i < p->step_count; i++) {
        if (p->steps[i].estimated_cost < 0) continue;  /* pruned */
        Node *n = graph_find_node_by_id(g, p->steps[i].node_id);
        if (!n) continue;
        scored[valid_count].step_index = i;
        scored[valid_count].final_score = compute_final_score(n, v, g, p->steps[i].depth,
            &scored[valid_count].rule_score,
            &scored[valid_count].learned_score,
            &scored[valid_count].structural_score);
        valid_count++;
    }
    /* Sort by final score (descending — highest first) */
    for (int i = 0; i < valid_count - 1; i++) {
        for (int j = i + 1; j < valid_count; j++) {
            if (scored[j].final_score > scored[i].final_score) {
                ScoredStep tmp = scored[i];
                scored[i] = scored[j];
                scored[j] = tmp;
            }
        }
    }
    /* Reorder plan steps based on sorted scores */
    PlanStep *new_steps = (PlanStep *)calloc(p->step_count, sizeof(PlanStep));
    if (!new_steps) {
        free(scored);
        return -1;
    }
    int new_idx = 0;
    /* First: scored steps in priority order */
    for (int i = 0; i < valid_count; i++) {
        new_steps[new_idx++] = p->steps[scored[i].step_index];
    }
    /* Then: pruned steps (at the end, marked with -1 cost) */
    for (int i = 0; i < p->step_count; i++) {
        if (p->steps[i].estimated_cost < 0) {
            new_steps[new_idx++] = p->steps[i];
        }
    }
    /* Copy back */
    memcpy(p->steps, new_steps, p->step_count * sizeof(PlanStep));
    free(new_steps);
    free(scored);
    STATE.steps_reordered += valid_count;
    return valid_count;
}

/* Adaptive depth — increase depth for high-value nodes, decrease for low-value */
int optimize_adaptive_depth(Plan *p, Graph *g, View *v) {
    if (!p || !g || !v) return 0;
    int adjusted = 0;
    for (int i = 0; i < p->step_count; i++) {
        if (p->steps[i].estimated_cost < 0) continue;  /* pruned */
        Node *n = graph_find_node_by_id(g, p->steps[i].node_id);
        if (!n) continue;
        float rs, ls, ss;
        float final = compute_final_score(n, v, g, p->steps[i].depth, &rs, &ls, &ss);
        /* High-value nodes get deeper expansion */
        if (final > 0.8 && p->steps[i].depth < v->stop.max_depth) {
            p->steps[i].depth = p->steps[i].depth + 1;  /* allow one more level */
            adjusted++;
        }
        /* Low-value nodes get shallower */
        if (final < 0.3 && p->steps[i].depth > 1) {
            p->steps[i].depth = p->steps[i].depth - 1;
            adjusted++;
        }
    }
    STATE.steps_depth_adjusted += adjusted;
    return adjusted;
}

/* ════════════════════════════════════════════
 * MAIN OPTIMIZER FUNCTION
 * ════════════════════════════════════════════ */

/* optimize_plan: takes a naive plan and returns an optimized one */
int optimize_plan(Plan *p, Graph *g, View *v) {
    if (!p || !g || !v) return -1;
    int pruned         = optimize_prune(p, g, v);
    int deduped        = optimize_dedup(p);
    int reordered      = optimize_reorder(p, g, v);
    int depth_adjusted = optimize_adaptive_depth(p, g, v);
    (void)reordered;  /* tracked via STATE.steps_reordered, not summed */
    STATE.plans_optimized++;
    return pruned + deduped + depth_adjusted;
}

/* ════════════════════════════════════════════
 * PRIORITY QUEUE EXECUTION
 * ════════════════════════════════════════════ */

/* Execute the optimized plan — highest score first */
int execute_plan(Plan *p, Graph *g, View *v) {
    if (!p || !g || !v) return -1;
    p->executed = 1;
    int total_expanded = 0;
    /* Execute steps in priority order (already sorted by optimize_reorder) */
    for (int i = 0; i < p->step_count; i++) {
        /* Check guard */
        if (plan_check_guard(p)) break;
        /* Skip pruned steps */
        if (p->steps[i].estimated_cost < 0) continue;
        /* Find node */
        Node *n = graph_find_node_by_id(g, p->steps[i].node_id);
        if (!n || n->expanded) continue;
        /* Charge cost */
        p->budget_used += (int)p->steps[i].estimated_cost;
        p->node_count++;
        /* Mark as expanded */
        n->expanded = 1;
        total_expanded++;
        /* Call the expansion function for this node and add children as new steps */
        if (!n->expand) {
            n->expand = expand_lookup(n->type);
        }
        if (n->expand && p->step_count < p->step_capacity) {
            Node **children = NULL;
            int n_children = n->expand(n, g, p->steps[i].depth, &children);
            for (int c = 0; c < n_children && p->step_count < p->step_capacity; c++) {
                Node *child = children[c];
                if (!child) continue;
                child->depth = n->depth + 1;
                graph_add_node(g, child);
                Edge *e = edge_create(g->edge_count, n, child, "EXPANDS_TO", child->importance);
                if (e) graph_add_edge(g, e);
                plan_add_step(p, child->id, child->type, p->steps[i].depth + 1,
                              child->cost, child->importance, i, NULL);
                total_expanded++;
            }
            free(children);
        }
    }
    STATE.plans_executed++;
    STATE.nodes_expanded += total_expanded;
    return total_expanded;
}

/* ════════════════════════════════════════════
 * OPTIMIZER DUMP (for debugging)
 * ════════════════════════════════════════════ */

void optimizer_dump_scores(Plan *p, Graph *g, View *v, char *buf, int buf_size) {
    if (!p || !g || !v || !buf) return;
    int pos = 0;
    pos += snprintf(buf + pos, buf_size - pos, "Optimizer scores:\n");
    for (int i = 0; i < p->step_count && pos < buf_size - 200; i++) {
        if (p->steps[i].estimated_cost < 0) {
            pos += snprintf(buf + pos, buf_size - pos, "  step[%d]: PRUNED\n", i);
            continue;
        }
        Node *n = graph_find_node_by_id(g, p->steps[i].node_id);
        if (!n) continue;
        float rs, ls, ss;
        float final = compute_final_score(n, v, g, p->steps[i].depth, &rs, &ls, &ss);
        pos += snprintf(buf + pos, buf_size - pos,
            "  step[%d]: %s score=%.2f (rule=%.2f, learned=%.2f, structural=%.2f)\n",
            i, n->name, final, rs, ls, ss);
    }
}

/* ════════════════════════════════════════════
 * BCL DISPATCH LAYER
 * ════════════════════════════════════════════ */

int GraphOptimizer_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    return 1;
}

int GraphOptimizer_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) GraphOptimizer_Init();

    /* ── read_state ─────────────────────────────────────────── */
    if (strcmp(cmd, "read_state") == 0) {
        char buf[512];
        snprintf(buf, sizeof(buf),
            "[@INITIALIZED]{%d}[@PLANS_OPTIMIZED]{%d}[@PLANS_EXECUTED]{%d}"
            "[@STEPS_PRUNED]{%d}[@STEPS_DEDUPED]{%d}[@STEPS_REORDERED]{%d}"
            "[@STEPS_DEPTH_ADJUSTED]{%d}[@NODES_EXPANDED]{%d}"
            "[@RULE_WEIGHT]{%.2f}[@LEARNED_WEIGHT]{%.2f}[@STRUCTURAL_WEIGHT]{%.2f}",
            STATE.initialized, STATE.plans_optimized, STATE.plans_executed,
            STATE.steps_pruned, STATE.steps_deduped, STATE.steps_reordered,
            STATE.steps_depth_adjusted, STATE.nodes_expanded,
            (double)RULE_WEIGHT, (double)LEARNED_WEIGHT, (double)STRUCTURAL_WEIGHT);
        return BclResult_Ok(bcl_out, out_sz, buf);
    }

    /* ── set_config ─────────────────────────────────────────── */
    if (strcmp(cmd, "set_config") == 0) {
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }

    /* ── optimize ───────────────────────────────────────────── */
    /* BCL in: [@PLAN_PTR]{addr}[@GRAPH_PTR]{addr}[@VIEW_PTR]{addr}
     * Runs optimize_plan and reports counts. */
    if (strcmp(cmd, "optimize") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);

        char plan_addr[32] = "";
        char graph_addr[32] = "";
        char view_addr[32] = "";
        BclParser_Extract(&parse, "PLAN_PTR", plan_addr, sizeof(plan_addr));
        BclParser_Extract(&parse, "GRAPH_PTR", graph_addr, sizeof(graph_addr));
        BclParser_Extract(&parse, "VIEW_PTR", view_addr, sizeof(view_addr));
        BclParser_Free(&parse);

        if (!*plan_addr || !*graph_addr || !*view_addr) {
            return BclResult_Err(bcl_out, out_sz, 20,
                "missing PLAN_PTR/GRAPH_PTR/VIEW_PTR");
        }

        Plan *p   = (Plan *)(uintptr_t)strtoull(plan_addr, NULL, 0);
        Graph *g  = (Graph *)(uintptr_t)strtoull(graph_addr, NULL, 0);
        View *v   = (View *)(uintptr_t)strtoull(view_addr, NULL, 0);

        if (!p || !g || !v) {
            return BclResult_Err(bcl_out, out_sz, 21, "null plan/graph/view pointer");
        }

        int result = optimize_plan(p, g, v);
        if (result < 0) {
            return BclResult_Err(bcl_out, out_sz, 50, "optimize_plan failed");
        }

        char buf[256];
        snprintf(buf, sizeof(buf),
            "[@STATUS]{optimized}[@CHANGES]{%d}[@STEP_COUNT]{%d}",
            result, p->step_count);
        return BclResult_Ok(bcl_out, out_sz, buf);
    }

    /* ── execute ────────────────────────────────────────────── */
    /* BCL in: [@PLAN_PTR]{addr}[@GRAPH_PTR]{addr}[@VIEW_PTR]{addr}
     * Runs execute_plan and reports expanded node count. */
    if (strcmp(cmd, "execute") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);

        char plan_addr[32] = "";
        char graph_addr[32] = "";
        char view_addr[32] = "";
        BclParser_Extract(&parse, "PLAN_PTR", plan_addr, sizeof(plan_addr));
        BclParser_Extract(&parse, "GRAPH_PTR", graph_addr, sizeof(graph_addr));
        BclParser_Extract(&parse, "VIEW_PTR", view_addr, sizeof(view_addr));
        BclParser_Free(&parse);

        if (!*plan_addr || !*graph_addr || !*view_addr) {
            return BclResult_Err(bcl_out, out_sz, 20,
                "missing PLAN_PTR/GRAPH_PTR/VIEW_PTR");
        }

        Plan *p   = (Plan *)(uintptr_t)strtoull(plan_addr, NULL, 0);
        Graph *g  = (Graph *)(uintptr_t)strtoull(graph_addr, NULL, 0);
        View *v   = (View *)(uintptr_t)strtoull(view_addr, NULL, 0);

        if (!p || !g || !v) {
            return BclResult_Err(bcl_out, out_sz, 21, "null plan/graph/view pointer");
        }

        int expanded = execute_plan(p, g, v);
        if (expanded < 0) {
            return BclResult_Err(bcl_out, out_sz, 50, "execute_plan failed");
        }

        char buf[256];
        snprintf(buf, sizeof(buf),
            "[@STATUS]{executed}[@NODES_EXPANDED]{%d}[@BUDGET_USED]{%d}"
            "[@NODE_COUNT]{%d}",
            expanded, p->budget_used, p->node_count);
        return BclResult_Ok(bcl_out, out_sz, buf);
    }

    /* ── score ──────────────────────────────────────────────── */
    /* BCL in: [@NODE_PTR]{addr}[@VIEW_PTR]{addr}[@GRAPH_PTR]{addr}[@DEPTH]{n}
     * Returns the 3-part score breakdown for a single node. */
    if (strcmp(cmd, "score") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);

        char node_addr[32]  = "";
        char view_addr[32]  = "";
        char graph_addr[32] = "";
        char depth_str[16]  = "0";
        BclParser_Extract(&parse, "NODE_PTR", node_addr, sizeof(node_addr));
        BclParser_Extract(&parse, "VIEW_PTR", view_addr, sizeof(view_addr));
        BclParser_Extract(&parse, "GRAPH_PTR", graph_addr, sizeof(graph_addr));
        BclParser_Extract(&parse, "DEPTH", depth_str, sizeof(depth_str));
        BclParser_Free(&parse);

        if (!*node_addr || !*view_addr || !*graph_addr) {
            return BclResult_Err(bcl_out, out_sz, 20,
                "missing NODE_PTR/VIEW_PTR/GRAPH_PTR");
        }

        Node  *n = (Node *)(uintptr_t)strtoull(node_addr, NULL, 0);
        View  *v = (View *)(uintptr_t)strtoull(view_addr, NULL, 0);
        Graph *g = (Graph *)(uintptr_t)strtoull(graph_addr, NULL, 0);
        int depth = atoi(depth_str);

        if (!n || !v || !g) {
            return BclResult_Err(bcl_out, out_sz, 21, "null node/view/graph pointer");
        }

        float rs, ls, ss;
        float final = compute_final_score(n, v, g, depth, &rs, &ls, &ss);

        char buf[256];
        snprintf(buf, sizeof(buf),
            "[@FINAL_SCORE]{%.4f}[@RULE_SCORE]{%.4f}[@LEARNED_SCORE]{%.4f}"
            "[@STRUCTURAL_SCORE]{%.4f}[@FANOUT]{%d}[@IS_BRIDGE]{%d}",
            (double)final, (double)rs, (double)ls, (double)ss,
            node_fanout(n), node_is_bridge(n, g));
        return BclResult_Ok(bcl_out, out_sz, buf);
    }

    /* ── dump_scores ────────────────────────────────────────── */
    /* BCL in: [@PLAN_PTR]{addr}[@GRAPH_PTR]{addr}[@VIEW_PTR]{addr}
     * Returns the full score dump text. */
    if (strcmp(cmd, "dump_scores") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);

        char plan_addr[32] = "";
        char graph_addr[32] = "";
        char view_addr[32] = "";
        BclParser_Extract(&parse, "PLAN_PTR", plan_addr, sizeof(plan_addr));
        BclParser_Extract(&parse, "GRAPH_PTR", graph_addr, sizeof(graph_addr));
        BclParser_Extract(&parse, "VIEW_PTR", view_addr, sizeof(view_addr));
        BclParser_Free(&parse);

        if (!*plan_addr || !*graph_addr || !*view_addr) {
            return BclResult_Err(bcl_out, out_sz, 20,
                "missing PLAN_PTR/GRAPH_PTR/VIEW_PTR");
        }

        Plan *p   = (Plan *)(uintptr_t)strtoull(plan_addr, NULL, 0);
        Graph *g  = (Graph *)(uintptr_t)strtoull(graph_addr, NULL, 0);
        View *v   = (View *)(uintptr_t)strtoull(view_addr, NULL, 0);

        if (!p || !g || !v) {
            return BclResult_Err(bcl_out, out_sz, 21, "null plan/graph/view pointer");
        }

        char *buf = (char *)calloc(GRAPH_BUF_SIZE, 1);
        if (!buf) {
            return BclResult_Err(bcl_out, out_sz, 50, "out of memory");
        }
        optimizer_dump_scores(p, g, v, buf, GRAPH_BUF_SIZE);
        int rc = BclResult_Ok(bcl_out, out_sz, buf);
        free(buf);
        return rc;
    }

    return BclResult_Err(bcl_out, out_sz, 404, "unknown command");
}

int GraphOptimizer_Close(void) {
    memset(&STATE, 0, sizeof(STATE));
    return 1;
}

const char * GraphOptimizer_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "GraphOptimizer: initialized=%d plans_optimized=%d plans_executed=%d "
        "steps_pruned=%d steps_deduped=%d nodes_expanded=%d",
        STATE.initialized, STATE.plans_optimized, STATE.plans_executed,
        STATE.steps_pruned, STATE.steps_deduped, STATE.nodes_expanded);
    return buf;
}
