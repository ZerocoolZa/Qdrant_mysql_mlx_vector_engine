// GraphLearning — 3-Stage Learning Pipeline for the Max Graph Engine
// Pipeline: TRACE -> EVALUATION -> UPDATE -> POLICY APPLY
// Prevents feedback collapse via anti-reinforcement (exploration pressure)
// KEY: learned signals update scoring model only, NEVER graph structure

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

// === Learning configuration ===
#define MAX_WEIGHT_ENTRIES 10000
#define MAX_RECENT_PATHS 100
#define LEARNING_RATE 0.01
#define CONFIDENCE_THRESHOLD 3      // need 3+ repeated signals to apply
#define SAFETY_BOUND 0.5            // max weight change per update
#define REPETITION_PENALTY 0.1      // penalty for reusing same paths
#define EXPLORATION_BONUS 0.2       // bonus for exploring new paths

// === Weight entry — accumulated learning signal for a node ===
typedef struct WeightEntry {
    int node_id;
    char node_name[256];
    float weight_delta;         // accumulated gradient (not yet applied)
    float current_weight;       // current applied weight
    int signal_count;           // how many signals accumulated
    float last_contribution;    // most recent contribution score
    float historical_success;   // running average of success
    int times_visited;          // total times this node was visited
    int times_wasted;           // times this node led to wasted expansion
    int active;                 // 1 if this entry is in use
} WeightEntry;

// === Recent path — for anti-reinforcement ===
typedef struct RecentPath {
    int node_ids[64];           // sequence of node IDs in this path
    int node_count;
    char view_name[64];         // which view produced this path
    float outcome_quality;      // outcome of this path
} RecentPath;

// === Learning model — the complete learning state ===
typedef struct LearningModel {
    WeightEntry weights[MAX_WEIGHT_ENTRIES];
    int weight_count;
    
    // Recent paths for anti-reinforcement
    RecentPath recent_paths[MAX_RECENT_PATHS];
    int recent_path_count;
    int recent_path_head;       // circular buffer index
    
    // Configuration
    float learning_rate;
    float confidence_threshold;
    float safety_bound;
    float repetition_penalty;
    float exploration_bonus;
    
    // Statistics
    int total_signals_processed;
    int total_updates_applied;
    int total_updates_rejected;
    float avg_contribution;
} LearningModel;

// === Learning model lifecycle ===

LearningModel *learning_create() {
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

// === Find or create weight entry ===

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
    w->current_weight = 0.5;  // start neutral
    w->signal_count = 0;
    w->last_contribution = 0.0;
    w->historical_success = 0.5;
    w->times_visited = 0;
    w->times_wasted = 0;
    w->active = 1;
    m->weight_count++;
    return w;
}

// === Stage 1: EVALUATION — process trace into learning signals ===
// (trace_evaluate in GraphTrace already does this, here we consume the signals)

// === Stage 2: UPDATE — accumulate gradients in buffer ===

// Process a single learning signal from a trace
int learning_process_signal(LearningModel *m, LearningSignal *sig) {
    if (!m || !sig) return -1;
    
    // Find or create weight entry
    WeightEntry *w = learning_find_weight(m, sig->node_id);
    if (!w) {
        w = learning_create_weight(m, sig->node_id, sig->node_name);
        if (!w) return -1;
    }
    
    // Accumulate gradient (DO NOT apply directly)
    float gradient = m->learning_rate * sig->contribution_score;
    w->weight_delta += gradient;
    w->signal_count++;
    w->last_contribution = sig->contribution_score;
    
    // Update historical success (exponential moving average)
    float success = sig->contribution_score > 0 ? 1.0 : 0.0;
    w->historical_success = 0.9 * w->historical_success + 0.1 * success;
    
    // Track wasted expansions
    if (sig->contribution_score < 0) {
        w->times_wasted++;
    }
    w->times_visited++;
    
    m->total_signals_processed++;
    
    // Update average contribution
    m->avg_contribution = (m->avg_contribution * 0.99) + (sig->contribution_score * 0.01);
    
    return 0;
}

// Process all signals from a trace evaluation
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

// === Stage 3: POLICY APPLY — slow integration with safety bounds ===

// Apply accumulated weight updates if confidence threshold is met
int learning_apply_updates(LearningModel *m) {
    if (!m) return 0;
    int applied = 0;
    int rejected = 0;
    
    for (int i = 0; i < m->weight_count; i++) {
        WeightEntry *w = &m->weights[i];
        if (!w->active) continue;
        
        // Check confidence threshold — need enough repeated signals
        if (w->signal_count < m->confidence_threshold) {
            rejected++;
            continue;
        }
        
        // Compute average delta
        float avg_delta = w->weight_delta / (float)w->signal_count;
        
        // Clip by safety bound
        if (avg_delta > m->safety_bound) avg_delta = m->safety_bound;
        if (avg_delta < -m->safety_bound) avg_delta = -m->safety_bound;
        
        // Check if delta is significant enough
        if (fabsf(avg_delta) < 0.01) {
            rejected++;
            continue;
        }
        
        // Apply slow update
        w->current_weight += avg_delta;
        
        // Clamp weight to [0, 1]
        if (w->current_weight > 1.0) w->current_weight = 1.0;
        if (w->current_weight < 0.0) w->current_weight = 0.0;
        
        // Reset accumulator
        w->weight_delta = 0.0;
        w->signal_count = 0;
        
        applied++;
    }
    
    m->total_updates_applied += applied;
    m->total_updates_rejected += rejected;
    return applied;
}

// === Anti-reinforcement — prevent feedback loops ===

// Record a path in recent paths (for anti-reinforcement)
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
    // Advance circular buffer
    m->recent_path_head = (m->recent_path_head + 1) % MAX_RECENT_PATHS;
    if (m->recent_path_count < MAX_RECENT_PATHS) m->recent_path_count++;
    return 0;
}

// Compute similarity of a node to recent paths
// Returns 0.0 (completely novel) to 1.0 (in every recent path)
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

// === LearnedScore computation ===
// LearnedScore(node) = historical_success + contribution_weight + exploration_bonus
//                      - repetition_penalty - wasted_expansion_penalty

float learning_score(LearningModel *m, int node_id) {
    if (!m) return 0.5;
    WeightEntry *w = learning_find_weight(m, node_id);
    if (!w) {
        // New node — give exploration bonus
        return 0.5 + m->exploration_bonus;
    }
    
    float score = 0.0;
    
    // Historical success
    score += w->historical_success;
    
    // Contribution weight (current applied weight)
    score += w->current_weight * 0.3;
    
    // Exploration bonus — nodes not in recent paths get bonus
    float similarity = learning_path_similarity(m, node_id);
    if (similarity < 0.1) {
        score += m->exploration_bonus;
    }
    
    // Repetition penalty — nodes in many recent paths get penalized
    score -= similarity * m->repetition_penalty;
    
    // Wasted expansion penalty
    if (w->times_visited > 0) {
        float waste_ratio = (float)w->times_wasted / (float)w->times_visited;
        score -= waste_ratio * 0.2;
    }
    
    // Clamp to [0, 1]
    if (score > 1.0) score = 1.0;
    if (score < 0.0) score = 0.0;
    
    return score;
}

// === Credit assignment ===
// contribution(node) = downstream_success_impact - expansion_cost_penalty - redundancy_overlap_penalty

float learning_compute_contribution(float downstream_success, float expansion_cost,
                                     float redundancy_overlap) {
    return downstream_success - expansion_cost * 0.1 - redundancy_overlap * 0.2;
}

// === Learning model dump (for debugging) ===

void learning_dump(LearningModel *m, char *buf, int buf_size) {
    if (!m || !buf) return;
    int pos = 0;
    pos += snprintf(buf + pos, buf_size - pos,
        "LearningModel{weights=%d, paths=%d, signals=%d, applied=%d, rejected=%d, avg_contrib=%.3f}
",
        m->weight_count, m->recent_path_count,
        m->total_signals_processed, m->total_updates_applied, m->total_updates_rejected,
        m->avg_contribution);
    // Show top 10 weights by absolute delta
    int shown = 0;
    for (int i = 0; i < m->weight_count && shown < 10 && pos < buf_size - 200; i++) {
        WeightEntry *w = &m->weights[i];
        if (!w->active) continue;
        if (w->signal_count == 0 && w->current_weight == 0.5) continue;  // skip inactive
        pos += snprintf(buf + pos, buf_size - pos,
            "  weight[%d]: node=%d(%s) current=%.3f delta=%.3f signals=%d success=%.2f visited=%d wasted=%d
",
            i, w->node_id, w->node_name, w->current_weight, w->weight_delta,
            w->signal_count, w->historical_success, w->times_visited, w->times_wasted);
        shown++;
    }
}

// Export learning model as JSON
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

// Reset learning model (clear all weights)
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
