//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_graph_learning.c" date="2026-07-04" author="Devin" session_id="graph-bcl-units" context="3-Stage Learning Pipeline for the Max Graph Engine. Pipeline: TRACE -> EVALUATION -> UPDATE -> POLICY APPLY. Prevents feedback collapse via anti-reinforcement (exploration pressure). Learned signals update scoring model only, NEVER graph structure. Converted from graph_raw/GraphLearning.c."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_graph_learning.c" domain="graph_engine" authority="GraphLearning"}
//[@SUMMARY]{summary="3-Stage Learning Pipeline. Accumulates gradients from trace signals, applies slow weight updates with confidence thresholds and safety bounds. Anti-reinforcement via recent path tracking prevents feedback loops. Commands: create, free, process_signal, process_trace, apply_updates, record_path, score, compute_contribution, dump, export_json, reset, read_state, set_config."}
//[@CLASS]{class="GraphLearning" domain="graph_engine" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="learning_create" type="lifecycle"}
//[@METHOD]{method="learning_free" type="lifecycle"}
//[@METHOD]{method="learning_find_weight" type="query"}
//[@METHOD]{method="learning_create_weight" type="command"}
//[@METHOD]{method="learning_process_signal" type="command"}
//[@METHOD]{method="learning_process_trace" type="command"}
//[@METHOD]{method="learning_apply_updates" type="command"}
//[@METHOD]{method="learning_record_path" type="command"}
//[@METHOD]{method="learning_path_similarity" type="query"}
//[@METHOD]{method="learning_score" type="query"}
//[@METHOD]{method="learning_compute_contribution" type="query"}
//[@METHOD]{method="learning_dump" type="query"}
//[@METHOD]{method="learning_export_json" type="query"}
//[@METHOD]{method="learning_reset" type="command"}

/*
 * bcl_graph_learning.c — 3-Stage Learning Pipeline for the Max Graph Engine
 *
 * Pipeline: TRACE -> EVALUATION -> UPDATE -> POLICY APPLY
 * Prevents feedback collapse via anti-reinforcement (exploration pressure)
 * KEY: learned signals update scoring model only, NEVER graph structure
 *
 * BCL IN:  [@RUN]{[@CMD]{create}}
 *          [@RUN]{[@CMD]{process_signal}[@NODE_ID]{42}[@NODE_NAME]{MyClass}[@VIEW_ID]{1}[@CONTRIBUTION]{0.75}[@SUCCESS_DELTA]{0.5}[@COST_EFFICIENCY]{0.8}[@REDUNDANCY]{0.1}}
 *          [@RUN]{[@CMD]{process_trace}[@SIGNAL_COUNT]{3}...}
 *          [@RUN]{[@CMD]{apply_updates}}
 *          [@RUN]{[@CMD]{record_path}[@NODE_IDS]{1,2,3,4}[@VIEW_NAME]{default}[@OUTCOME]{0.85}}
 *          [@RUN]{[@CMD]{score}[@NODE_ID]{42}}
 *          [@RUN]{[@CMD]{compute_contribution}[@DOWNSTREAM]{0.9}[@COST]{1.5}[@REDUNDANCY]{0.2}}
 *          [@RUN]{[@CMD]{dump}}
 *          [@RUN]{[@CMD]{export_json}}
 *          [@RUN]{[@CMD]{reset}}
 *          [@RUN]{[@CMD]{read_state}}
 *          [@RUN]{[@CMD]{set_config}[@LEARNING_RATE]{0.02}[@CONFIDENCE_THRESHOLD]{5}}
 * BCL OUT: [@OK]{[@WEIGHTS]{N}[@SIGNALS]{N}...}
 * BCL ERR: [@ERR]{[@CODE]{N}[@DESC]{...}}
 */

#include "bcl_graph_types.h"
#include "bcl_toolstack.h"

/* ════════════════════════════════════════════
 * PRIVATE CONSTANTS (not in shared header)
 * ════════════════════════════════════════════ */

#define LEARNING_RATE         0.01
#define CONFIDENCE_THRESHOLD  3       /* need 3+ repeated signals to apply */
#define SAFETY_BOUND          0.5     /* max weight change per update */
#define REPETITION_PENALTY    0.1     /* penalty for reusing same paths */
#define EXPLORATION_BONUS     0.2     /* bonus for exploring new paths */

/* ════════════════════════════════════════════
 * BCL UNIT STATE
 * ════════════════════════════════════════════ */

static struct {
    int            initialized;
    LearningModel *model;
    int            model_created;
} STATE;

/* ════════════════════════════════════════════
 * LEARNING MODEL LIFECYCLE
 * ════════════════════════════════════════════ */

LearningModel *learning_create(void) {
    LearningModel *m = (LearningModel *)calloc(1, sizeof(LearningModel));
    if (!m) return NULL;
    m->weight_count = 0;
    m->recent_path_count = 0;
    m->recent_path_head = 0;
    m->learning_rate = LEARNING_RATE;
    m->confidence_threshold = CONFIDENCE_THRESHOLD;
    m->safety_bound = SAFETY_BOUND;
    m->repetition_penalty = REPETITION_PENALTY;
    m->exploration_bonus = EXPLORATION_BONUS;
    m->total_signals_processed = 0;
    m->total_updates_applied = 0;
    m->total_updates_rejected = 0;
    m->avg_contribution = 0.0;
    return m;
}

void learning_free(LearningModel *m) {
    if (m) free(m);
}

/* ════════════════════════════════════════════
 * FIND OR CREATE WEIGHT ENTRY
 * ════════════════════════════════════════════ */

static WeightEntry *learning_find_weight(LearningModel *m, int node_id) {
    if (!m) return NULL;
    for (int i = 0; i < m->weight_count; i++) {
        if (m->weights[i].active && m->weights[i].node_id == node_id) {
            return &m->weights[i];
        }
    }
    return NULL;
}

static WeightEntry *learning_create_weight(LearningModel *m, int node_id, const char *node_name) {
    if (!m || m->weight_count >= MAX_WEIGHT_ENTRIES) return NULL;
    WeightEntry *w = &m->weights[m->weight_count];
    memset(w, 0, sizeof(WeightEntry));
    w->node_id = node_id;
    if (node_name) strncpy(w->node_name, node_name, sizeof(w->node_name) - 1);
    w->weight_delta = 0.0;
    w->current_weight = 0.5;  /* start neutral */
    w->signal_count = 0;
    w->last_contribution = 0.0;
    w->historical_success = 0.5;
    w->times_visited = 0;
    w->times_wasted = 0;
    w->active = 1;
    m->weight_count++;
    return w;
}

/* ════════════════════════════════════════════
 * STAGE 2: UPDATE — accumulate gradients in buffer
 * ════════════════════════════════════════════ */

/* Process a single learning signal from a trace */
int learning_process_signal(LearningModel *m, LearningSignal *sig) {
    if (!m || !sig) return -1;

    /* Find or create weight entry */
    WeightEntry *w = learning_find_weight(m, sig->node_id);
    if (!w) {
        w = learning_create_weight(m, sig->node_id, sig->node_name);
        if (!w) return -1;
    }

    /* Accumulate gradient (DO NOT apply directly) */
    float gradient = m->learning_rate * sig->contribution_score;
    w->weight_delta += gradient;
    w->signal_count++;
    w->last_contribution = sig->contribution_score;

    /* Update historical success (exponential moving average) */
    float success = sig->contribution_score > 0 ? 1.0 : 0.0;
    w->historical_success = 0.9 * w->historical_success + 0.1 * success;

    /* Track wasted expansions */
    if (sig->contribution_score < 0) {
        w->times_wasted++;
    }
    w->times_visited++;

    m->total_signals_processed++;

    /* Update average contribution */
    m->avg_contribution = (m->avg_contribution * 0.99) + (sig->contribution_score * 0.01);

    return 0;
}

/* Process all signals from a trace evaluation */
int learning_process_trace(LearningModel *m, LearningSignal *signals, int signal_count) {
    if (!m || !signals) return -1;
    int processed = 0;
    for (int i = 0; i < signal_count; i++) {
        if (learning_process_signal(m, &signals[i]) == 0) {
            processed++;
        }
    }
    return processed;
}

/* ════════════════════════════════════════════
 * STAGE 3: POLICY APPLY — slow integration with safety bounds
 * ════════════════════════════════════════════ */

/* Apply accumulated weight updates if confidence threshold is met */
int learning_apply_updates(LearningModel *m) {
    if (!m) return 0;
    int applied = 0;
    int rejected = 0;

    for (int i = 0; i < m->weight_count; i++) {
        WeightEntry *w = &m->weights[i];
        if (!w->active) continue;

        /* Check confidence threshold — need enough repeated signals */
        if (w->signal_count < m->confidence_threshold) {
            rejected++;
            continue;
        }

        /* Compute average delta */
        float avg_delta = w->weight_delta / (float)w->signal_count;

        /* Clip by safety bound */
        if (avg_delta > m->safety_bound) avg_delta = m->safety_bound;
        if (avg_delta < -m->safety_bound) avg_delta = -m->safety_bound;

        /* Check if delta is significant enough */
        if (fabsf(avg_delta) < 0.01) {
            rejected++;
            continue;
        }

        /* Apply slow update */
        w->current_weight += avg_delta;

        /* Clamp weight to [0, 1] */
        if (w->current_weight > 1.0) w->current_weight = 1.0;
        if (w->current_weight < 0.0) w->current_weight = 0.0;

        /* Reset accumulator */
        w->weight_delta = 0.0;
        w->signal_count = 0;

        applied++;
    }

    m->total_updates_applied += applied;
    m->total_updates_rejected += rejected;
    return applied;
}

/* ════════════════════════════════════════════
 * ANTI-REINFORCEMENT — prevent feedback loops
 * ════════════════════════════════════════════ */

/* Record a path in recent paths (for anti-reinforcement) */
int learning_record_path(LearningModel *m, int *node_ids, int node_count,
                         const char *view_name, float outcome) {
    if (!m || !node_ids || node_count <= 0) return -1;
    RecentPath *p = &m->recent_paths[m->recent_path_head];
    p->node_count = node_count > 64 ? 64 : node_count;
    for (int i = 0; i < p->node_count; i++) {
        p->node_ids[i] = node_ids[i];
    }
    if (view_name) strncpy(p->view_name, view_name, sizeof(p->view_name) - 1);
    p->outcome_quality = outcome;
    /* Advance circular buffer */
    m->recent_path_head = (m->recent_path_head + 1) % MAX_RECENT_PATHS;
    if (m->recent_path_count < MAX_RECENT_PATHS) m->recent_path_count++;
    return 0;
}

/* Compute similarity of a node to recent paths */
/* Returns 0.0 (completely novel) to 1.0 (in every recent path) */
float learning_path_similarity(LearningModel *m, int node_id) {
    if (!m || m->recent_path_count == 0) return 0.0;
    int occurrences = 0;
    for (int i = 0; i < m->recent_path_count; i++) {
        RecentPath *p = &m->recent_paths[i];
        for (int j = 0; j < p->node_count; j++) {
            if (p->node_ids[j] == node_id) {
                occurrences++;
                break;
            }
        }
    }
    return (float)occurrences / (float)m->recent_path_count;
}

/* ════════════════════════════════════════════
 * LEARNED SCORE COMPUTATION
 * LearnedScore(node) = historical_success + contribution_weight + exploration_bonus
 *                      - repetition_penalty - wasted_expansion_penalty
 * ════════════════════════════════════════════ */

float learning_score(LearningModel *m, int node_id) {
    if (!m) return 0.5;
    WeightEntry *w = learning_find_weight(m, node_id);
    if (!w) {
        /* New node — give exploration bonus */
        return 0.5 + m->exploration_bonus;
    }

    float score = 0.0;

    /* Historical success */
    score += w->historical_success;

    /* Contribution weight (current applied weight) */
    score += w->current_weight * 0.3;

    /* Exploration bonus — nodes not in recent paths get bonus */
    float similarity = learning_path_similarity(m, node_id);
    if (similarity < 0.1) {
        score += m->exploration_bonus;
    }

    /* Repetition penalty — nodes in many recent paths get penalized */
    score -= similarity * m->repetition_penalty;

    /* Wasted expansion penalty */
    if (w->times_visited > 0) {
        float waste_ratio = (float)w->times_wasted / (float)w->times_visited;
        score -= waste_ratio * 0.2;
    }

    /* Clamp to [0, 1] */
    if (score > 1.0) score = 1.0;
    if (score < 0.0) score = 0.0;

    return score;
}

/* ════════════════════════════════════════════
 * CREDIT ASSIGNMENT
 * contribution(node) = downstream_success_impact - expansion_cost_penalty - redundancy_overlap_penalty
 * ════════════════════════════════════════════ */

float learning_compute_contribution(float downstream_success, float expansion_cost,
                                     float redundancy_overlap) {
    return downstream_success - expansion_cost * 0.1 - redundancy_overlap * 0.2;
}

/* ════════════════════════════════════════════
 * LEARNING MODEL DUMP (for debugging)
 * ════════════════════════════════════════════ */

void learning_dump(LearningModel *m, char *buf, int buf_size) {
    if (!m || !buf) return;
    int pos = 0;
    pos += snprintf(buf + pos, buf_size - pos,
        "LearningModel{weights=%d, paths=%d, signals=%d, applied=%d, rejected=%d, avg_contrib=%.3f}\n",
        m->weight_count, m->recent_path_count,
        m->total_signals_processed, m->total_updates_applied, m->total_updates_rejected,
        m->avg_contribution);
    /* Show top 10 weights by absolute delta */
    int shown = 0;
    for (int i = 0; i < m->weight_count && shown < 10 && pos < buf_size - 200; i++) {
        WeightEntry *w = &m->weights[i];
        if (!w->active) continue;
        if (w->signal_count == 0 && w->current_weight == 0.5) continue;  /* skip inactive */
        pos += snprintf(buf + pos, buf_size - pos,
            "  weight[%d]: node=%d(%s) current=%.3f delta=%.3f signals=%d success=%.2f visited=%d wasted=%d\n",
            i, w->node_id, w->node_name, w->current_weight, w->weight_delta,
            w->signal_count, w->historical_success, w->times_visited, w->times_wasted);
        shown++;
    }
}

/* Export learning model as JSON */
void learning_export_json(LearningModel *m, char *buf, int buf_size) {
    if (!m || !buf) return;
    int pos = 0;
    pos += snprintf(buf + pos, buf_size - pos,
        "{\"learning\":{\"weights\":%d,\"signals\":%d,\"applied\":%d,\"rejected\":%d,\"avg_contrib\":%.3f,\"entries\":[",
        m->weight_count, m->total_signals_processed, m->total_updates_applied,
        m->total_updates_rejected, m->avg_contribution);
    int first = 1;
    for (int i = 0; i < m->weight_count && pos < buf_size - 200; i++) {
        WeightEntry *w = &m->weights[i];
        if (!w->active) continue;
        if (w->signal_count == 0 && w->current_weight == 0.5) continue;
        if (!first) pos += snprintf(buf + pos, buf_size - pos, ",");
        first = 0;
        pos += snprintf(buf + pos, buf_size - pos,
            "{\"node\":%d,\"name\":\"%s\",\"weight\":%.3f,\"delta\":%.3f,\"signals\":%d,\"success\":%.2f}",
            w->node_id, w->node_name, w->current_weight, w->weight_delta,
            w->signal_count, w->historical_success);
    }
    pos += snprintf(buf + pos, buf_size - pos, "]}}");
}

/* Reset learning model (clear all weights) */
void learning_reset(LearningModel *m) {
    if (!m) return;
    m->weight_count = 0;
    m->recent_path_count = 0;
    m->recent_path_head = 0;
    m->total_signals_processed = 0;
    m->total_updates_applied = 0;
    m->total_updates_rejected = 0;
    m->avg_contribution = 0.0;
}

/* ════════════════════════════════════════════
 * BCL DISPATCH FUNCTIONS
 * ════════════════════════════════════════════ */

int GraphLearning_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    STATE.model = NULL;
    STATE.model_created = 0;
    return 1;
}

int GraphLearning_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) GraphLearning_Init();

    /* ===== CREATE — allocate a new learning model ===== */
    if (strcmp(cmd, "create") == 0) {
        if (STATE.model && STATE.model_created) {
            learning_free(STATE.model);
        }
        STATE.model = learning_create();
        if (!STATE.model) {
            return BclResult_Err(bcl_out, out_sz, 10, "failed to create learning model");
        }
        STATE.model_created = 1;
        char body[256];
        snprintf(body, sizeof(body),
            "[@STATUS]{created}[@LEARNING_RATE]{%.4f}[@CONFIDENCE_THRESHOLD]{%d}"
            "[@SAFETY_BOUND]{%.2f}[@REPETITION_PENALTY]{%.2f}[@EXPLORATION_BONUS]{%.2f}",
            STATE.model->learning_rate, (int)STATE.model->confidence_threshold,
            STATE.model->safety_bound, STATE.model->repetition_penalty,
            STATE.model->exploration_bonus);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== FREE — release the learning model ===== */
    if (strcmp(cmd, "free") == 0) {
        if (STATE.model && STATE.model_created) {
            learning_free(STATE.model);
            STATE.model = NULL;
            STATE.model_created = 0;
        }
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{freed}");
    }

    /* ===== PROCESS_SIGNAL — process a single learning signal ===== */
    if (strcmp(cmd, "process_signal") == 0) {
        if (!STATE.model || !STATE.model_created) {
            return BclResult_Err(bcl_out, out_sz, 20, "no learning model — call create first");
        }
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char node_id_str[32] = {0};
        char node_name[GRAPH_MAX_NAME] = {0};
        char view_id_str[32] = {0};
        char contribution_str[32] = {0};
        char success_delta_str[32] = {0};
        char cost_efficiency_str[32] = {0};
        char redundancy_str[32] = {0};
        BclParser_Extract(&parse, "NODE_ID", node_id_str, sizeof(node_id_str));
        BclParser_Extract(&parse, "NODE_NAME", node_name, sizeof(node_name));
        BclParser_Extract(&parse, "VIEW_ID", view_id_str, sizeof(view_id_str));
        BclParser_Extract(&parse, "CONTRIBUTION", contribution_str, sizeof(contribution_str));
        BclParser_Extract(&parse, "SUCCESS_DELTA", success_delta_str, sizeof(success_delta_str));
        BclParser_Extract(&parse, "COST_EFFICIENCY", cost_efficiency_str, sizeof(cost_efficiency_str));
        BclParser_Extract(&parse, "REDUNDANCY", redundancy_str, sizeof(redundancy_str));
        BclParser_Free(&parse);

        if (!node_id_str[0]) {
            return BclResult_Err(bcl_out, out_sz, 21, "no NODE_ID in packet");
        }

        LearningSignal sig;
        memset(&sig, 0, sizeof(sig));
        sig.node_id = atoi(node_id_str);
        if (node_name[0]) strncpy(sig.node_name, node_name, sizeof(sig.node_name) - 1);
        sig.view_id = view_id_str[0] ? atoi(view_id_str) : 0;
        sig.contribution_score = contribution_str[0] ? (float)atof(contribution_str) : 0.0;
        sig.success_delta = success_delta_str[0] ? (float)atof(success_delta_str) : 0.0;
        sig.cost_efficiency = cost_efficiency_str[0] ? (float)atof(cost_efficiency_str) : 0.0;
        sig.redundancy_penalty = redundancy_str[0] ? (float)atof(redundancy_str) : 0.0;

        int rc = learning_process_signal(STATE.model, &sig);
        if (rc != 0) {
            return BclResult_Err(bcl_out, out_sz, 22, "failed to process signal");
        }
        char body[256];
        snprintf(body, sizeof(body),
            "[@STATUS]{processed}[@NODE_ID]{%d}[@TOTAL_SIGNALS]{%d}[@AVG_CONTRIB]{%.4f}",
            sig.node_id, STATE.model->total_signals_processed, STATE.model->avg_contribution);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== PROCESS_TRACE — process multiple signals from a trace ===== */
    if (strcmp(cmd, "process_trace") == 0) {
        if (!STATE.model || !STATE.model_created) {
            return BclResult_Err(bcl_out, out_sz, 20, "no learning model — call create first");
        }
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char count_str[32] = {0};
        BclParser_Extract(&parse, "SIGNAL_COUNT", count_str, sizeof(count_str));

        /* Extract up to 64 individual signals */
        int signal_count = count_str[0] ? atoi(count_str) : 0;
        if (signal_count <= 0) {
            BclParser_Free(&parse);
            return BclResult_Err(bcl_out, out_sz, 23, "no SIGNAL_COUNT or count is zero");
        }
        if (signal_count > 64) signal_count = 64;

        LearningSignal signals[64];
        memset(signals, 0, sizeof(signals));
        int valid = 0;
        for (int i = 0; i < signal_count; i++) {
            char tag[32];
            snprintf(tag, sizeof(tag), "SIG%d_NODE_ID", i);
            char node_id_str[32] = {0};
            BclParser_Extract(&parse, tag, node_id_str, sizeof(node_id_str));
            if (!node_id_str[0]) continue;

            signals[valid].node_id = atoi(node_id_str);

            snprintf(tag, sizeof(tag), "SIG%d_NODE_NAME", i);
            char node_name[GRAPH_MAX_NAME] = {0};
            BclParser_Extract(&parse, tag, node_name, sizeof(node_name));
            if (node_name[0]) strncpy(signals[valid].node_name, node_name, sizeof(signals[valid].node_name) - 1);

            snprintf(tag, sizeof(tag), "SIG%d_VIEW_ID", i);
            char view_id_str[32] = {0};
            BclParser_Extract(&parse, tag, view_id_str, sizeof(view_id_str));
            signals[valid].view_id = view_id_str[0] ? atoi(view_id_str) : 0;

            snprintf(tag, sizeof(tag), "SIG%d_CONTRIBUTION", i);
            char contrib_str[32] = {0};
            BclParser_Extract(&parse, tag, contrib_str, sizeof(contrib_str));
            signals[valid].contribution_score = contrib_str[0] ? (float)atof(contrib_str) : 0.0;

            snprintf(tag, sizeof(tag), "SIG%d_SUCCESS_DELTA", i);
            char succ_str[32] = {0};
            BclParser_Extract(&parse, tag, succ_str, sizeof(succ_str));
            signals[valid].success_delta = succ_str[0] ? (float)atof(succ_str) : 0.0;

            snprintf(tag, sizeof(tag), "SIG%d_COST_EFFICIENCY", i);
            char cost_str[32] = {0};
            BclParser_Extract(&parse, tag, cost_str, sizeof(cost_str));
            signals[valid].cost_efficiency = cost_str[0] ? (float)atof(cost_str) : 0.0;

            snprintf(tag, sizeof(tag), "SIG%d_REDUNDANCY", i);
            char red_str[32] = {0};
            BclParser_Extract(&parse, tag, red_str, sizeof(red_str));
            signals[valid].redundancy_penalty = red_str[0] ? (float)atof(red_str) : 0.0;

            valid++;
        }
        BclParser_Free(&parse);

        if (valid == 0) {
            return BclResult_Err(bcl_out, out_sz, 24, "no valid signals found in packet");
        }

        int processed = learning_process_trace(STATE.model, signals, valid);
        char body[256];
        snprintf(body, sizeof(body),
            "[@STATUS]{processed}[@PROCESSED]{%d}[@TOTAL_SIGNALS]{%d}[@AVG_CONTRIB]{%.4f}",
            processed, STATE.model->total_signals_processed, STATE.model->avg_contribution);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== APPLY_UPDATES — apply accumulated weight updates ===== */
    if (strcmp(cmd, "apply_updates") == 0) {
        if (!STATE.model || !STATE.model_created) {
            return BclResult_Err(bcl_out, out_sz, 20, "no learning model — call create first");
        }
        int applied = learning_apply_updates(STATE.model);
        char body[256];
        snprintf(body, sizeof(body),
            "[@STATUS]{applied}[@APPLIED]{%d}[@TOTAL_APPLIED]{%d}[@TOTAL_REJECTED]{%d}",
            applied, STATE.model->total_updates_applied, STATE.model->total_updates_rejected);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== RECORD_PATH — record a path for anti-reinforcement ===== */
    if (strcmp(cmd, "record_path") == 0) {
        if (!STATE.model || !STATE.model_created) {
            return BclResult_Err(bcl_out, out_sz, 20, "no learning model — call create first");
        }
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char node_ids_str[4096] = {0};
        char view_name[64] = {0};
        char outcome_str[32] = {0};
        BclParser_Extract(&parse, "NODE_IDS", node_ids_str, sizeof(node_ids_str));
        BclParser_Extract(&parse, "VIEW_NAME", view_name, sizeof(view_name));
        BclParser_Extract(&parse, "OUTCOME", outcome_str, sizeof(outcome_str));
        BclParser_Free(&parse);

        if (!node_ids_str[0]) {
            return BclResult_Err(bcl_out, out_sz, 25, "no NODE_IDS in packet");
        }

        /* Parse comma-separated node IDs */
        int node_ids[64];
        int node_count = 0;
        char *tok = strtok(node_ids_str, ",");
        while (tok && node_count < 64) {
            node_ids[node_count++] = atoi(tok);
            tok = strtok(NULL, ",");
        }

        if (node_count == 0) {
            return BclResult_Err(bcl_out, out_sz, 26, "no valid node IDs in NODE_IDS");
        }

        float outcome = outcome_str[0] ? (float)atof(outcome_str) : 0.0;
        int rc = learning_record_path(STATE.model, node_ids, node_count,
                                       view_name[0] ? view_name : NULL, outcome);
        if (rc != 0) {
            return BclResult_Err(bcl_out, out_sz, 27, "failed to record path");
        }
        char body[256];
        snprintf(body, sizeof(body),
            "[@STATUS]{recorded}[@NODE_COUNT]{%d}[@VIEW_NAME]{%s}[@OUTCOME]{%.3f}"
            "[@TOTAL_PATHS]{%d}",
            node_count, view_name[0] ? view_name : "none", outcome,
            STATE.model->recent_path_count);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== SCORE — compute learned score for a node ===== */
    if (strcmp(cmd, "score") == 0) {
        if (!STATE.model || !STATE.model_created) {
            return BclResult_Err(bcl_out, out_sz, 20, "no learning model — call create first");
        }
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char node_id_str[32] = {0};
        BclParser_Extract(&parse, "NODE_ID", node_id_str, sizeof(node_id_str));
        BclParser_Free(&parse);

        if (!node_id_str[0]) {
            return BclResult_Err(bcl_out, out_sz, 28, "no NODE_ID in packet");
        }

        int node_id = atoi(node_id_str);
        float score = learning_score(STATE.model, node_id);
        float similarity = learning_path_similarity(STATE.model, node_id);
        char body[256];
        snprintf(body, sizeof(body),
            "[@NODE_ID]{%d}[@SCORE]{%.4f}[@SIMILARITY]{%.4f}",
            node_id, score, similarity);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== COMPUTE_CONTRIBUTION — credit assignment ===== */
    if (strcmp(cmd, "compute_contribution") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char downstream_str[32] = {0};
        char cost_str[32] = {0};
        char redundancy_str[32] = {0};
        BclParser_Extract(&parse, "DOWNSTREAM", downstream_str, sizeof(downstream_str));
        BclParser_Extract(&parse, "COST", cost_str, sizeof(cost_str));
        BclParser_Extract(&parse, "REDUNDANCY", redundancy_str, sizeof(redundancy_str));
        BclParser_Free(&parse);

        if (!downstream_str[0]) {
            return BclResult_Err(bcl_out, out_sz, 29, "no DOWNSTREAM in packet");
        }

        float downstream = (float)atof(downstream_str);
        float cost = cost_str[0] ? (float)atof(cost_str) : 0.0;
        float redundancy = redundancy_str[0] ? (float)atof(redundancy_str) : 0.0;
        float contribution = learning_compute_contribution(downstream, cost, redundancy);
        char body[256];
        snprintf(body, sizeof(body),
            "[@DOWNSTREAM]{%.4f}[@COST]{%.4f}[@REDUNDANCY]{%.4f}[@CONTRIBUTION]{%.4f}",
            downstream, cost, redundancy, contribution);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== DUMP — dump learning model state (text) ===== */
    if (strcmp(cmd, "dump") == 0) {
        if (!STATE.model || !STATE.model_created) {
            return BclResult_Err(bcl_out, out_sz, 20, "no learning model — call create first");
        }
        char dump_buf[GRAPH_BUF_SIZE];
        dump_buf[0] = '\0';
        learning_dump(STATE.model, dump_buf, sizeof(dump_buf));
        return BclResult_Ok(bcl_out, out_sz, dump_buf);
    }

    /* ===== EXPORT_JSON — export learning model as JSON ===== */
    if (strcmp(cmd, "export_json") == 0) {
        if (!STATE.model || !STATE.model_created) {
            return BclResult_Err(bcl_out, out_sz, 20, "no learning model — call create first");
        }
        char json_buf[GRAPH_BUF_SIZE];
        json_buf[0] = '\0';
        learning_export_json(STATE.model, json_buf, sizeof(json_buf));
        return BclResult_Ok(bcl_out, out_sz, json_buf);
    }

    /* ===== RESET — clear all weights and statistics ===== */
    if (strcmp(cmd, "reset") == 0) {
        if (!STATE.model || !STATE.model_created) {
            return BclResult_Err(bcl_out, out_sz, 20, "no learning model — call create first");
        }
        learning_reset(STATE.model);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{reset}");
    }

    /* ===== READ_STATE — return current BCL unit state ===== */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        if (STATE.model && STATE.model_created) {
            snprintf(body, sizeof(body),
                "[@INITIALIZED]{%d}[@MODEL_CREATED]{1}[@WEIGHTS]{%d}[@PATHS]{%d}"
                "[@SIGNALS]{%d}[@APPLIED]{%d}[@REJECTED]{%d}[@AVG_CONTRIB]{%.4f}"
                "[@LEARNING_RATE]{%.4f}[@CONFIDENCE_THRESHOLD]{%d}",
                STATE.initialized,
                STATE.model->weight_count, STATE.model->recent_path_count,
                STATE.model->total_signals_processed,
                STATE.model->total_updates_applied,
                STATE.model->total_updates_rejected,
                STATE.model->avg_contribution,
                STATE.model->learning_rate,
                (int)STATE.model->confidence_threshold);
        } else {
            snprintf(body, sizeof(body),
                "[@INITIALIZED]{%d}[@MODEL_CREATED]{0}",
                STATE.initialized);
        }
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== SET_CONFIG — configure learning parameters ===== */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char lr_str[32] = {0};
        char ct_str[32] = {0};
        char sb_str[32] = {0};
        char rp_str[32] = {0};
        char eb_str[32] = {0};
        BclParser_Extract(&parse, "LEARNING_RATE", lr_str, sizeof(lr_str));
        BclParser_Extract(&parse, "CONFIDENCE_THRESHOLD", ct_str, sizeof(ct_str));
        BclParser_Extract(&parse, "SAFETY_BOUND", sb_str, sizeof(sb_str));
        BclParser_Extract(&parse, "REPETITION_PENALTY", rp_str, sizeof(rp_str));
        BclParser_Extract(&parse, "EXPLORATION_BONUS", eb_str, sizeof(eb_str));
        BclParser_Free(&parse);

        if (STATE.model && STATE.model_created) {
            if (lr_str[0])  STATE.model->learning_rate = (float)atof(lr_str);
            if (ct_str[0])  STATE.model->confidence_threshold = (float)atof(ct_str);
            if (sb_str[0])  STATE.model->safety_bound = (float)atof(sb_str);
            if (rp_str[0])  STATE.model->repetition_penalty = (float)atof(rp_str);
            if (eb_str[0])  STATE.model->exploration_bonus = (float)atof(eb_str);
        }

        char body[512];
        if (STATE.model && STATE.model_created) {
            snprintf(body, sizeof(body),
                "[@LEARNING_RATE]{%.4f}[@CONFIDENCE_THRESHOLD]{%d}"
                "[@SAFETY_BOUND]{%.2f}[@REPETITION_PENALTY]{%.2f}"
                "[@EXPLORATION_BONUS]{%.2f}",
                STATE.model->learning_rate, (int)STATE.model->confidence_threshold,
                STATE.model->safety_bound, STATE.model->repetition_penalty,
                STATE.model->exploration_bonus);
        } else {
            snprintf(body, sizeof(body),
                "[@STATUS]{config_set_no_model}[@LEARNING_RATE]{%s}"
                "[@CONFIDENCE_THRESHOLD]{%s}[@SAFETY_BOUND]{%s}"
                "[@REPETITION_PENALTY]{%s}[@EXPLORATION_BONUS]{%s}",
                lr_str[0] ? lr_str : "default",
                ct_str[0] ? ct_str : "default",
                sb_str[0] ? sb_str : "default",
                rp_str[0] ? rp_str : "default",
                eb_str[0] ? eb_str : "default");
        }
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    return BclResult_Err(bcl_out, out_sz, 404, "unknown command");
}

int GraphLearning_Close(void) {
    if (STATE.model && STATE.model_created) {
        learning_free(STATE.model);
        STATE.model = NULL;
        STATE.model_created = 0;
    }
    STATE.initialized = 0;
    return 1;
}

const char * GraphLearning_State(void) {
    static char buf[256];
    if (STATE.model && STATE.model_created) {
        snprintf(buf, sizeof(buf),
            "GraphLearning: initialized=%d model=active weights=%d signals=%d applied=%d",
            STATE.initialized, STATE.model->weight_count,
            STATE.model->total_signals_processed, STATE.model->total_updates_applied);
    } else {
        snprintf(buf, sizeof(buf),
            "GraphLearning: initialized=%d model=none",
            STATE.initialized);
    }
    return buf;
}
