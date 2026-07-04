// GraphCache — Multi-Layer Scoped Cache for the Max Graph Engine
// Cache key = (node_id, view_signature, policy_signature, depth, scoring_version)
// 4 layers: Structural, Semantic, Policy, Learning — no cross-layer contamination
// KEY RULE: learned signals cannot modify graph structure cache directly

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// === Cache layer types ===
typedef enum {
    CACHE_STRUCTURAL,    // pure graph expansions, deterministic
    CACHE_SEMANTIC,      // view-specific, includes traversal rules
    CACHE_POLICY,        // execution behavior, budget/constraints
    CACHE_LEARNING       // isolated, contribution signals only
} CacheLayer;

// === Cache entry — context-bound ===
typedef struct CacheEntry {
    int node_id;                 // which node
    char view_signature[128];    // view name + hash of rules
    char policy_signature[128];  // policy hash
    int depth;                   // depth at which this was cached
    int scoring_version;         // scoring model version
    CacheLayer layer;            // which cache layer
    
    // Cached result
    void *result;                // cached result (subgraph, score, etc.)
    int result_size;             // size of cached result
    float result_quality;        // quality score of cached result
    
    // Metadata
    float stability_score;       // how stable is this cache entry (0-1)
    int reuse_count;             // how many times this entry was reused
    float context_conflict_risk; // risk of context conflict (0-1)
    float freshness_requirement; // how fresh must this be (0=never expire, 1=always fresh)
    
    // Subgraph fingerprint
    char fingerprint[64];        // hash of (node_set + edge_set + view_rules + depth_profile)
    
    // Timestamps
    long created_ms;             // when created
    long last_accessed_ms;       // when last accessed
    
    struct CacheEntry *next;     // hash table chaining
} CacheEntry;

// === Scope map — context isolation between views ===
typedef struct ScopeRule {
    char view_name[64];
    char allowed_node_types[32][32];  // node types this view can access
    int allowed_count;
    char forbidden_edge_types[32][64]; // edge types this view cannot traverse
    int forbidden_count;
} ScopeRule;

// === Cache statistics ===
typedef struct CacheStats {
    int total_entries;
    int structural_entries;
    int semantic_entries;
    int policy_entries;
    int learning_entries;
    int hits;
    int misses;
    int evictions;
    float hit_rate;
} CacheStats;

// === Cache hash table ===
#define CACHE_HASH_SIZE 1024

typedef struct GraphCache {
    CacheEntry *table[CACHE_HASH_SIZE];  // hash table
    int entry_count;
    CacheStats stats;
    ScopeRule scopes[32];                // view scope rules
    int scope_count;
    int max_entries;                     // eviction threshold
    int scoring_version;                 // current scoring model version
} GraphCache;

// === Hash function ===
static unsigned int cache_hash(int node_id, const char *view_sig, int depth) {
    unsigned int h = (unsigned int)node_id * 31;
    h += (unsigned int)depth * 7;
    if (view_sig) {
        for (int i = 0; view_sig[i]; i++) {
            h = h * 31 + (unsigned char)view_sig[i];
        }
    }
    return h % CACHE_HASH_SIZE;
}

// === Fingerprint computation ===
// hash(node_set + edge_set + view_rules + depth_profile)
void cache_compute_fingerprint(Node *n, View *v, int depth, char *out, int out_size) {
    if (!out || out_size <= 0) return;
    // Simple hash: combine node name, view name, depth, edge count
    unsigned int h = 0;
    if (n) {
        for (int i = 0; n->name[i]; i++) h = h * 31 + (unsigned char)n->name[i];
        h += n->id * 17;
    }
    if (v) {
        for (int i = 0; v->name[i]; i++) h = h * 31 + (unsigned char)v->name[i];
        h += v->rule_count * 13;
    }
    h += depth * 7;
    // Count edges
    int edge_count = 0;
    if (n) {
        Edge *e = n->first_edge;
        while (e) { edge_count++; e = e->next; }
    }
    h += edge_count * 3;
    snprintf(out, out_size, "%08x", h);
}

// === Cache lifecycle ===

GraphCache *cache_create(int max_entries) {
    GraphCache *c = (GraphCache *)calloc(1, sizeof(GraphCache));
    if (!c) return NULL;
    c->entry_count = 0;
    c->max_entries = max_entries > 0 ? max_entries : 10000;
    c->scope_count = 0;
    c->scoring_version = 1;
    // Clear hash table
    for (int i = 0; i < CACHE_HASH_SIZE; i++) {
        c->table[i] = NULL;
    }
    return c;
}

void cache_free(GraphCache *c) {
    if (!c) return;
    for (int i = 0; i < CACHE_HASH_SIZE; i++) {
        CacheEntry *e = c->table[i];
        while (e) {
            CacheEntry *next = e->next;
            if (e->result) free(e->result);
            free(e);
            e = next;
        }
    }
    free(c);
}

// === Cache value scoring ===
// cache_value = stability_score + reuse_frequency - context_conflict_risk - freshness_requirement
float cache_value(CacheEntry *e) {
    if (!e) return 0.0;
    float reuse_freq = (float)e->reuse_count / 100.0;
    if (reuse_freq > 1.0) reuse_freq = 1.0;
    return e->stability_score + reuse_freq - e->context_conflict_risk - e->freshness_requirement;
}

// === Scope map — context isolation ===

int cache_add_scope(GraphCache *c, const char *view_name,
                    const char **allowed_types, int allowed_count,
                    const char **forbidden_edges, int forbidden_count) {
    if (!c || !view_name || c->scope_count >= 32) return -1;
    ScopeRule *s = &c->scopes[c->scope_count];
    strncpy(s->view_name, view_name, sizeof(s->view_name) - 1);
    s->allowed_count = 0;
    for (int i = 0; i < allowed_count && i < 32; i++) {
        strncpy(s->allowed_node_types[i], allowed_types[i], 31);
        s->allowed_count++;
    }
    s->forbidden_count = 0;
    for (int i = 0; i < forbidden_count && i < 32; i++) {
        strncpy(s->forbidden_edge_types[i], forbidden_edges[i], 63);
        s->forbidden_count++;
    }
    c->scope_count++;
    return c->scope_count - 1;
}

// Check if a view is allowed to access a node type
int cache_scope_allows(GraphCache *c, const char *view_name, const char *node_type) {
    if (!c || !view_name || !node_type) return 1;  // allow by default
    for (int i = 0; i < c->scope_count; i++) {
        if (strcmp(c->scopes[i].view_name, view_name) == 0) {
            // Found scope rule — check allowed types
            if (c->scopes[i].allowed_count == 0) return 1;  // no restrictions
            for (int j = 0; j < c->scopes[i].allowed_count; j++) {
                if (strcmp(c->scopes[i].allowed_node_types[j], node_type) == 0 ||
                    strcmp(c->scopes[i].allowed_node_types[j], "*") == 0) {
                    return 1;
                }
            }
            return 0;  // not in allowed list
        }
    }
    return 1;  // no scope rule for this view = allow
}

// Check if a view is forbidden from traversing an edge type
int cache_scope_forbids_edge(GraphCache *c, const char *view_name, const char *edge_type) {
    if (!c || !view_name || !edge_type) return 0;
    for (int i = 0; i < c->scope_count; i++) {
        if (strcmp(c->scopes[i].view_name, view_name) == 0) {
            for (int j = 0; j < c->scopes[i].forbidden_count; j++) {
                if (strcmp(c->scopes[i].forbidden_edge_types[j], edge_type) == 0) {
                    return 1;
                }
            }
            return 0;
        }
    }
    return 0;
}

// === Cache store — context-bound ===

// Build a view signature from a View
void cache_view_signature(View *v, char *out, int out_size) {
    if (!v || !out || out_size <= 0) return;
    // Simple signature: view name + rule count + depth + min_importance
    snprintf(out, out_size, "%s_r%d_d%d_i%.2f",
        v->name, v->rule_count, v->stop.max_depth, v->stop.min_importance);
}

int cache_store(GraphCache *c, int node_id, const char *view_sig,
                const char *policy_sig, int depth, CacheLayer layer,
                void *result, int result_size, float quality,
                Node *n, View *v) {
    if (!c || !view_sig) return -1;
    // Check eviction
    if (c->entry_count >= c->max_entries) {
        // Evict lowest-value entry (simplified — just clear a bucket)
        for (int i = 0; i < CACHE_HASH_SIZE; i++) {
            if (c->table[i]) {
                CacheEntry *e = c->table[i];
                c->table[i] = e->next;
                if (e->result) free(e->result);
                free(e);
                c->entry_count--;
                c->stats.evictions++;
                break;
            }
        }
    }
    // Create entry
    CacheEntry *e = (CacheEntry *)calloc(1, sizeof(CacheEntry));
    if (!e) return -1;
    e->node_id = node_id;
    strncpy(e->view_signature, view_sig, sizeof(e->view_signature) - 1);
    if (policy_sig) strncpy(e->policy_signature, policy_sig, sizeof(e->policy_signature) - 1);
    e->depth = depth;
    e->scoring_version = c->scoring_version;
    e->layer = layer;
    // Copy result
    if (result && result_size > 0) {
        e->result = malloc(result_size);
        if (e->result) {
            memcpy(e->result, result, result_size);
            e->result_size = result_size;
        }
    }
    e->result_quality = quality;
    e->stability_score = 0.8;  // default high stability
    e->reuse_count = 0;
    e->context_conflict_risk = 0.0;
    e->freshness_requirement = 0.0;
    // Compute fingerprint
    if (n && v) {
        cache_compute_fingerprint(n, v, depth, e->fingerprint, sizeof(e->fingerprint));
    }
    e->created_ms = 0;  // would use clock_gettime in real impl
    e->last_accessed_ms = 0;
    // Insert into hash table
    unsigned int idx = cache_hash(node_id, view_sig, depth);
    e->next = c->table[idx];
    c->table[idx] = e;
    c->entry_count++;
    // Update stats
    c->stats.total_entries++;
    switch (layer) {
        case CACHE_STRUCTURAL: c->stats.structural_entries++; break;
        case CACHE_SEMANTIC: c->stats.semantic_entries++; break;
        case CACHE_POLICY: c->stats.policy_entries++; break;
        case CACHE_LEARNING: c->stats.learning_entries++; break;
    }
    return 0;
}

// === Cache lookup — context-bound ===

CacheEntry *cache_lookup(GraphCache *c, int node_id, const char *view_sig,
                         int depth, CacheLayer layer) {
    if (!c || !view_sig) return NULL;
    unsigned int idx = cache_hash(node_id, view_sig, depth);
    CacheEntry *e = c->table[idx];
    while (e) {
        if (e->node_id == node_id &&
            strcmp(e->view_signature, view_sig) == 0 &&
            e->depth == depth &&
            e->layer == layer) {
            // Check scoring version — invalidate if changed
            if (e->scoring_version != c->scoring_version) {
                // Stale — mark for eviction
                e->freshness_requirement = 1.0;
                c->stats.misses++;
                return NULL;
            }
            e->reuse_count++;
            e->last_accessed_ms = 0;  // would update timestamp
            c->stats.hits++;
            return e;
        }
        e = e->next;
    }
    c->stats.misses++;
    return NULL;
}

// === Cache invalidation ===

// Invalidate all entries for a specific view
int cache_invalidate_view(GraphCache *c, const char *view_sig) {
    if (!c || !view_sig) return 0;
    int invalidated = 0;
    for (int i = 0; i < CACHE_HASH_SIZE; i++) {
        CacheEntry *prev = NULL;
        CacheEntry *e = c->table[i];
        while (e) {
            if (strcmp(e->view_signature, view_sig) == 0) {
                CacheEntry *to_free = e;
                if (prev) {
                    prev->next = e->next;
                } else {
                    c->table[i] = e->next;
                }
                e = e->next;
                if (to_free->result) free(to_free->result);
                free(to_free);
                c->entry_count--;
                invalidated++;
            } else {
                prev = e;
                e = e->next;
            }
        }
    }
    return invalidated;
}

// Invalidate all entries (full flush)
int cache_invalidate_all(GraphCache *c) {
    if (!c) return 0;
    int invalidated = 0;
    for (int i = 0; i < CACHE_HASH_SIZE; i++) {
        CacheEntry *e = c->table[i];
        while (e) {
            CacheEntry *next = e->next;
            if (e->result) free(e->result);
            free(e);
            invalidated++;
            e = next;
        }
        c->table[i] = NULL;
    }
    c->entry_count = 0;
    return invalidated;
}

// Bump scoring version — invalidates all learning cache entries
int cache_bump_scoring_version(GraphCache *c) {
    if (!c) return -1;
    c->scoring_version++;
    // Invalidate all learning cache entries
    int invalidated = 0;
    for (int i = 0; i < CACHE_HASH_SIZE; i++) {
        CacheEntry *prev = NULL;
        CacheEntry *e = c->table[i];
        while (e) {
            if (e->layer == CACHE_LEARNING) {
                CacheEntry *to_free = e;
                if (prev) {
                    prev->next = e->next;
                } else {
                    c->table[i] = e->next;
                }
                e = e->next;
                if (to_free->result) free(to_free->result);
                free(to_free);
                c->entry_count--;
                invalidated++;
            } else {
                prev = e;
                e = e->next;
            }
        }
    }
    return invalidated;
}

// === Cache statistics ===

void cache_update_stats(GraphCache *c) {
    if (!c) return;
    int total = c->stats.hits + c->stats.misses;
    c->stats.hit_rate = total > 0 ? (float)c->stats.hits / (float)total : 0.0;
    c->stats.total_entries = c->entry_count;
}

void cache_dump_stats(GraphCache *c, char *buf, int buf_size) {
    if (!c || !buf) return;
    cache_update_stats(c);
    snprintf(buf, buf_size,
        "Cache{entries=%d, struct=%d, sem=%d, pol=%d, learn=%d, hits=%d, misses=%d, hit_rate=%.2f, evictions=%d, scoring_ver=%d}",
        c->stats.total_entries, c->stats.structural_entries, c->stats.semantic_entries,
        c->stats.policy_entries, c->stats.learning_entries,
        c->stats.hits, c->stats.misses, c->stats.hit_rate,
        c->stats.evictions, c->scoring_version);
}

// === Predefined scope rules ===

void cache_create_default_scopes(GraphCache *c) {
    if (!c) return;
    // AST_VIEW — allowed: class, method. Forbidden: UI edges
    const char *ast_allowed[] = {"class", "method", "rule"};
    const char *ast_forbidden[] = {"RENDERS", "LAYOUT"};
    cache_add_scope(c, "AST_VIEW", ast_allowed, 3, ast_forbidden, 2);
    // DEBUG_VIEW — allowed: rule, error, method. Forbidden: UI edges
    const char *debug_allowed[] = {"rule", "method", "token"};
    const char *debug_forbidden[] = {"RENDERS", "LAYOUT", "CO_OCCURS"};
    cache_add_scope(c, "DEBUG_VIEW", debug_allowed, 3, debug_forbidden, 3);
    // SEMANTIC_VIEW — allowed: token. Forbidden: CALLS edges
    const char *sem_allowed[] = {"token", "rule"};
    const char *sem_forbidden[] = {"CALLS", "HAS_METHOD"};
    cache_add_scope(c, "SEMANTIC_VIEW", sem_allowed, 2, sem_forbidden, 2);
    // FUNCTIONAL_VIEW — allowed: method, class. Forbidden: CO_OCCURS
    const char *func_allowed[] = {"method", "class"};
    const char *func_forbidden[] = {"CO_OCCURS", "KNOWS"};
    cache_add_scope(c, "FUNCTIONAL_VIEW", func_allowed, 2, func_forbidden, 2);
    // DEEP_VIEW — allowed everything, forbidden nothing
    const char *deep_allowed[] = {"*"};
    cache_add_scope(c, "DEEP_VIEW", deep_allowed, 1, NULL, 0);
}
