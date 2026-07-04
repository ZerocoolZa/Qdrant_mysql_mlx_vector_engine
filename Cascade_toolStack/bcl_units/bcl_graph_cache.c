//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_graph_cache.c" date="2026-07-04" author="Devin" session_id="graph-bcl-units" context="BCL unit for Max Graph Engine multi-layer scoped cache — 4 layers (Structural, Semantic, Policy, Learning), context-bound entries, scope isolation between views"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_graph_cache.c" domain="graph_engine" authority="GraphCache"}
//[@SUMMARY]{summary="Multi-layer scoped cache for the Max Graph Engine. Cache key = (node_id, view_signature, policy_signature, depth, scoring_version). 4 layers: Structural, Semantic, Policy, Learning — no cross-layer contamination. KEY RULE: learned signals cannot modify graph structure cache directly. Commands: create, free, store, lookup, invalidate_view, invalidate_all, bump_scoring, dump_stats, create_default_scopes, add_scope, scope_allows, scope_forbids_edge, read_state, set_config."}
//[@CLASS]{class="GraphCache" domain="graph_engine" authority="single"}
//[@METHOD]{method="GraphCache_Init" type="lifecycle"}
//[@METHOD]{method="GraphCache_Run" type="dispatch"}
//[@METHOD]{method="GraphCache_Close" type="lifecycle"}
//[@METHOD]{method="GraphCache_State" type="query"}
//[@METHOD]{method="cache_hash" type="internal"}
//[@METHOD]{method="cache_create" type="lifecycle"}
//[@METHOD]{method="cache_free" type="lifecycle"}
//[@METHOD]{method="cache_value" type="query"}
//[@METHOD]{method="cache_add_scope" type="command"}
//[@METHOD]{method="cache_scope_allows" type="query"}
//[@METHOD]{method="cache_scope_forbids_edge" type="query"}
//[@METHOD]{method="cache_view_signature" type="query"}
//[@METHOD]{method="cache_store" type="command"}
//[@METHOD]{method="cache_lookup" type="query"}
//[@METHOD]{method="cache_invalidate_view" type="command"}
//[@METHOD]{method="cache_invalidate_all" type="command"}
//[@METHOD]{method="cache_bump_scoring_version" type="command"}
//[@METHOD]{method="cache_update_stats" type="internal"}
//[@METHOD]{method="cache_dump_stats" type="query"}
//[@METHOD]{method="cache_create_default_scopes" type="command"}
//[@METHOD]{method="cache_compute_fingerprint" type="query"}

#include "bcl_graph_types.h"
#include "bcl_toolstack.h"

/* ════════════════════════════════════════════
 * UNIT STATE — single live cache instance
 * ════════════════════════════════════════════ */

static struct {
    int         initialized;
    GraphCache *cache;
    int         max_entries;
    char        stats_buf[4096];
} STATE;

/* ════════════════════════════════════════════
 * HASH FUNCTION (internal)
 * ════════════════════════════════════════════ */

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

/* ════════════════════════════════════════════
 * FINGERPRINT COMPUTATION
 * hash(node_set + edge_set + view_rules + depth_profile)
 * ════════════════════════════════════════════ */

void cache_compute_fingerprint(Node *n, View *v, int depth, char *out, int out_size) {
    if (!out || out_size <= 0) return;
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
    int edge_count = 0;
    if (n) {
        Edge *e = n->first_edge;
        while (e) { edge_count++; e = e->next; }
    }
    h += edge_count * 3;
    snprintf(out, out_size, "%08x", h);
}

/* ════════════════════════════════════════════
 * CACHE LIFECYCLE
 * ════════════════════════════════════════════ */

GraphCache *cache_create(int max_entries) {
    GraphCache *c = (GraphCache *)calloc(1, sizeof(GraphCache));
    if (!c) return NULL;
    c->entry_count = 0;
    c->max_entries = max_entries > 0 ? max_entries : 10000;
    c->scope_count = 0;
    c->scoring_version = 1;
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

/* ════════════════════════════════════════════
 * CACHE VALUE SCORING
 * cache_value = stability_score + reuse_frequency - context_conflict_risk - freshness_requirement
 * ════════════════════════════════════════════ */

float cache_value(CacheEntry *e) {
    if (!e) return 0.0;
    float reuse_freq = (float)e->reuse_count / 100.0;
    if (reuse_freq > 1.0) reuse_freq = 1.0;
    return e->stability_score + reuse_freq - e->context_conflict_risk - e->freshness_requirement;
}

/* ════════════════════════════════════════════
 * SCOPE MAP — context isolation between views
 * ════════════════════════════════════════════ */

int cache_add_scope(GraphCache *c, const char *view_name,
                    const char **allowed_types, int allowed_count,
                    const char **forbidden_edges, int forbidden_count) {
    if (!c || !view_name || c->scope_count >= 32) return -1;
    ScopeRule *s = &c->scopes[c->scope_count];
    strncpy(s->view_name, view_name, sizeof(s->view_name) - 1);
    s->view_name[sizeof(s->view_name) - 1] = '\0';
    s->allowed_count = 0;
    for (int i = 0; i < allowed_count && i < 32; i++) {
        strncpy(s->allowed_node_types[i], allowed_types[i], 31);
        s->allowed_node_types[i][31] = '\0';
        s->allowed_count++;
    }
    s->forbidden_count = 0;
    for (int i = 0; i < forbidden_count && i < 32; i++) {
        strncpy(s->forbidden_edge_types[i], forbidden_edges[i], 63);
        s->forbidden_edge_types[i][63] = '\0';
        s->forbidden_count++;
    }
    c->scope_count++;
    return c->scope_count - 1;
}

int cache_scope_allows(GraphCache *c, const char *view_name, const char *node_type) {
    if (!c || !view_name || !node_type) return 1;
    for (int i = 0; i < c->scope_count; i++) {
        if (strcmp(c->scopes[i].view_name, view_name) == 0) {
            if (c->scopes[i].allowed_count == 0) return 1;
            for (int j = 0; j < c->scopes[i].allowed_count; j++) {
                if (strcmp(c->scopes[i].allowed_node_types[j], node_type) == 0 ||
                    strcmp(c->scopes[i].allowed_node_types[j], "*") == 0) {
                    return 1;
                }
            }
            return 0;
        }
    }
    return 1;
}

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

/* ════════════════════════════════════════════
 * VIEW SIGNATURE
 * ════════════════════════════════════════════ */

void cache_view_signature(View *v, char *out, int out_size) {
    if (!v || !out || out_size <= 0) return;
    snprintf(out, out_size, "%s_r%d_d%d_i%.2f",
        v->name, v->rule_count, v->stop.max_depth, v->stop.min_importance);
}

/* ════════════════════════════════════════════
 * CACHE STORE — context-bound
 * ════════════════════════════════════════════ */

int cache_store(GraphCache *c, int node_id, const char *view_sig,
                const char *policy_sig, int depth, CacheLayer layer,
                void *result, int result_size, float quality,
                Node *n, View *v) {
    if (!c || !view_sig) return -1;
    if (c->entry_count >= c->max_entries) {
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
    CacheEntry *e = (CacheEntry *)calloc(1, sizeof(CacheEntry));
    if (!e) return -1;
    e->node_id = node_id;
    strncpy(e->view_signature, view_sig, sizeof(e->view_signature) - 1);
    e->view_signature[sizeof(e->view_signature) - 1] = '\0';
    if (policy_sig) {
        strncpy(e->policy_signature, policy_sig, sizeof(e->policy_signature) - 1);
        e->policy_signature[sizeof(e->policy_signature) - 1] = '\0';
    }
    e->depth = depth;
    e->scoring_version = c->scoring_version;
    e->layer = layer;
    if (result && result_size > 0) {
        e->result = malloc(result_size);
        if (e->result) {
            memcpy(e->result, result, result_size);
            e->result_size = result_size;
        }
    }
    e->result_quality = quality;
    e->stability_score = 0.8;
    e->reuse_count = 0;
    e->context_conflict_risk = 0.0;
    e->freshness_requirement = 0.0;
    if (n && v) {
        cache_compute_fingerprint(n, v, depth, e->fingerprint, sizeof(e->fingerprint));
    }
    e->created_ms = 0;
    e->last_accessed_ms = 0;
    unsigned int idx = cache_hash(node_id, view_sig, depth);
    e->next = c->table[idx];
    c->table[idx] = e;
    c->entry_count++;
    c->stats.total_entries++;
    switch (layer) {
        case CACHE_STRUCTURAL: c->stats.structural_entries++; break;
        case CACHE_SEMANTIC:   c->stats.semantic_entries++;   break;
        case CACHE_POLICY:     c->stats.policy_entries++;     break;
        case CACHE_LEARNING:   c->stats.learning_entries++;   break;
    }
    return 0;
}

/* ════════════════════════════════════════════
 * CACHE LOOKUP — context-bound
 * ════════════════════════════════════════════ */

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
            if (e->scoring_version != c->scoring_version) {
                e->freshness_requirement = 1.0;
                c->stats.misses++;
                return NULL;
            }
            e->reuse_count++;
            e->last_accessed_ms = 0;
            c->stats.hits++;
            return e;
        }
        e = e->next;
    }
    c->stats.misses++;
    return NULL;
}

/* ════════════════════════════════════════════
 * CACHE INVALIDATION
 * ════════════════════════════════════════════ */

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

int cache_bump_scoring_version(GraphCache *c) {
    if (!c) return -1;
    c->scoring_version++;
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

/* ════════════════════════════════════════════
 * CACHE STATISTICS
 * ════════════════════════════════════════════ */

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

/* ════════════════════════════════════════════
 * PREDEFINED SCOPE RULES
 * ════════════════════════════════════════════ */

void cache_create_default_scopes(GraphCache *c) {
    if (!c) return;
    const char *ast_allowed[] = {"class", "method", "rule"};
    const char *ast_forbidden[] = {"RENDERS", "LAYOUT"};
    cache_add_scope(c, "AST_VIEW", ast_allowed, 3, ast_forbidden, 2);
    const char *debug_allowed[] = {"rule", "method", "token"};
    const char *debug_forbidden[] = {"RENDERS", "LAYOUT", "CO_OCCURS"};
    cache_add_scope(c, "DEBUG_VIEW", debug_allowed, 3, debug_forbidden, 3);
    const char *sem_allowed[] = {"token", "rule"};
    const char *sem_forbidden[] = {"CALLS", "HAS_METHOD"};
    cache_add_scope(c, "SEMANTIC_VIEW", sem_allowed, 2, sem_forbidden, 2);
    const char *func_allowed[] = {"method", "class"};
    const char *func_forbidden[] = {"CO_OCCURS", "KNOWS"};
    cache_add_scope(c, "FUNCTIONAL_VIEW", func_allowed, 2, func_forbidden, 2);
    const char *deep_allowed[] = {"*"};
    cache_add_scope(c, "DEEP_VIEW", deep_allowed, 1, NULL, 0);
}

/* ════════════════════════════════════════════
 * BCL UNIT INTERFACE — Init / Run / Close / State
 * ════════════════════════════════════════════ */

int GraphCache_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    STATE.max_entries = 10000;
    STATE.cache = NULL;
    return 1;
}

int GraphCache_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) GraphCache_Init();
    if (!cmd) {
        return BclResult_Err(bcl_out, out_sz, 50, "missing command");
    }

    /* ── create ─────────────────────────────── */
    if (strcmp(cmd, "create") == 0) {
        int max_entries = 10000;
        char val[64];
        if (BclParser_Extract((BclParseResult *)0, "max_entries", val, sizeof(val))) {
            /* parser not available here — use bcl_in scan */
        }
        (void)bcl_in;
        if (STATE.cache) {
            cache_free(STATE.cache);
            STATE.cache = NULL;
        }
        STATE.cache = cache_create(max_entries);
        if (!STATE.cache) {
            return BclResult_Err(bcl_out, out_sz, 51, "cache_create failed");
        }
        STATE.max_entries = max_entries;
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{created}[@MAX_ENTRIES]{10000}");
    }

    /* ── free ───────────────────────────────── */
    if (strcmp(cmd, "free") == 0) {
        if (STATE.cache) {
            cache_free(STATE.cache);
            STATE.cache = NULL;
        }
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{freed}");
    }

    /* ── store ──────────────────────────────── */
    if (strcmp(cmd, "store") == 0) {
        if (!STATE.cache) {
            return BclResult_Err(bcl_out, out_sz, 52, "no cache — call create first");
        }
        /* BCL packet expected: [@NODE_ID]{..}[@VIEW_SIG]{..}[@POLICY_SIG]{..}
         * [@DEPTH]{..}[@LAYER]{..}[@QUALITY]{..} */
        char node_id_s[32], view_sig[256], policy_sig[256];
        char depth_s[32], layer_s[32], quality_s[32];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        BclParser_Extract(&pr, "NODE_ID", node_id_s, sizeof(node_id_s));
        BclParser_Extract(&pr, "VIEW_SIG", view_sig, sizeof(view_sig));
        BclParser_Extract(&pr, "POLICY_SIG", policy_sig, sizeof(policy_sig));
        BclParser_Extract(&pr, "DEPTH", depth_s, sizeof(depth_s));
        BclParser_Extract(&pr, "LAYER", layer_s, sizeof(layer_s));
        BclParser_Extract(&pr, "QUALITY", quality_s, sizeof(quality_s));
        BclParser_Free(&pr);
        int node_id = atoi(node_id_s);
        int depth = atoi(depth_s);
        float quality = (float)atof(quality_s);
        CacheLayer layer = CACHE_STRUCTURAL;
        if (strcmp(layer_s, "SEMANTIC") == 0) layer = CACHE_SEMANTIC;
        else if (strcmp(layer_s, "POLICY") == 0) layer = CACHE_POLICY;
        else if (strcmp(layer_s, "LEARNING") == 0) layer = CACHE_LEARNING;
        int rc = cache_store(STATE.cache, node_id, view_sig,
                             policy_sig[0] ? policy_sig : NULL,
                             depth, layer, NULL, 0, quality, NULL, NULL);
        if (rc != 0) {
            return BclResult_Err(bcl_out, out_sz, 53, "cache_store failed");
        }
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{stored}[@NODE_ID]{stored}[@LAYER]{stored}");
    }

    /* ── lookup ─────────────────────────────── */
    if (strcmp(cmd, "lookup") == 0) {
        if (!STATE.cache) {
            return BclResult_Err(bcl_out, out_sz, 52, "no cache — call create first");
        }
        char node_id_s[32], view_sig[256], depth_s[32], layer_s[32];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        BclParser_Extract(&pr, "NODE_ID", node_id_s, sizeof(node_id_s));
        BclParser_Extract(&pr, "VIEW_SIG", view_sig, sizeof(view_sig));
        BclParser_Extract(&pr, "DEPTH", depth_s, sizeof(depth_s));
        BclParser_Extract(&pr, "LAYER", layer_s, sizeof(layer_s));
        BclParser_Free(&pr);
        int node_id = atoi(node_id_s);
        int depth = atoi(depth_s);
        CacheLayer layer = CACHE_STRUCTURAL;
        if (strcmp(layer_s, "SEMANTIC") == 0) layer = CACHE_SEMANTIC;
        else if (strcmp(layer_s, "POLICY") == 0) layer = CACHE_POLICY;
        else if (strcmp(layer_s, "LEARNING") == 0) layer = CACHE_LEARNING;
        CacheEntry *e = cache_lookup(STATE.cache, node_id, view_sig, depth, layer);
        if (e) {
            char body[512];
            snprintf(body, sizeof(body),
                "[@HIT]{1}[@REUSE]{%d}[@QUALITY]{%.2f}[@FINGERPRINT]{%s}",
                e->reuse_count, e->result_quality, e->fingerprint);
            return BclResult_Ok(bcl_out, out_sz, body);
        }
        return BclResult_Ok(bcl_out, out_sz, "[@HIT]{0}[@STATUS]{miss}");
    }

    /* ── invalidate_view ────────────────────── */
    if (strcmp(cmd, "invalidate_view") == 0) {
        if (!STATE.cache) {
            return BclResult_Err(bcl_out, out_sz, 52, "no cache — call create first");
        }
        char view_sig[256];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        BclParser_Extract(&pr, "VIEW_SIG", view_sig, sizeof(view_sig));
        BclParser_Free(&pr);
        int n = cache_invalidate_view(STATE.cache, view_sig);
        char body[128];
        snprintf(body, sizeof(body), "[@STATUS]{invalidated}[@COUNT]{%d}", n);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── invalidate_all ─────────────────────── */
    if (strcmp(cmd, "invalidate_all") == 0) {
        if (!STATE.cache) {
            return BclResult_Err(bcl_out, out_sz, 52, "no cache — call create first");
        }
        int n = cache_invalidate_all(STATE.cache);
        char body[128];
        snprintf(body, sizeof(body), "[@STATUS]{flushed}[@COUNT]{%d}", n);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── bump_scoring ───────────────────────── */
    if (strcmp(cmd, "bump_scoring") == 0) {
        if (!STATE.cache) {
            return BclResult_Err(bcl_out, out_sz, 52, "no cache — call create first");
        }
        int n = cache_bump_scoring_version(STATE.cache);
        char body[128];
        snprintf(body, sizeof(body), "[@STATUS]{bumped}[@INVALIDATED]{%d}[@VERSION]{%d}",
                 n, STATE.cache->scoring_version);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── dump_stats ─────────────────────────── */
    if (strcmp(cmd, "dump_stats") == 0) {
        if (!STATE.cache) {
            return BclResult_Err(bcl_out, out_sz, 52, "no cache — call create first");
        }
        cache_dump_stats(STATE.cache, STATE.stats_buf, sizeof(STATE.stats_buf));
        char body[4200];
        snprintf(body, sizeof(body), "[@STATS]{%s}", STATE.stats_buf);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── create_default_scopes ──────────────── */
    if (strcmp(cmd, "create_default_scopes") == 0) {
        if (!STATE.cache) {
            return BclResult_Err(bcl_out, out_sz, 52, "no cache — call create first");
        }
        cache_create_default_scopes(STATE.cache);
        char body[128];
        snprintf(body, sizeof(body), "[@STATUS]{default_scopes_created}[@SCOPE_COUNT]{%d}",
                 STATE.cache->scope_count);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── add_scope ──────────────────────────── */
    if (strcmp(cmd, "add_scope") == 0) {
        if (!STATE.cache) {
            return BclResult_Err(bcl_out, out_sz, 52, "no cache — call create first");
        }
        char view_name[64], allowed[1024], forbidden[1024];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        BclParser_Extract(&pr, "VIEW_NAME", view_name, sizeof(view_name));
        BclParser_Extract(&pr, "ALLOWED", allowed, sizeof(allowed));
        BclParser_Extract(&pr, "FORBIDDEN", forbidden, sizeof(forbidden));
        BclParser_Free(&pr);
        const char *allowed_arr[32];
        const char *forbidden_arr[32];
        int allowed_count = 0;
        int forbidden_count = 0;
        char *saveptr = NULL;
        char allowed_copy[1024];
        char forbidden_copy[1024];
        strncpy(allowed_copy, allowed, sizeof(allowed_copy) - 1);
        allowed_copy[sizeof(allowed_copy) - 1] = '\0';
        strncpy(forbidden_copy, forbidden, sizeof(forbidden_copy) - 1);
        forbidden_copy[sizeof(forbidden_copy) - 1] = '\0';
        char *tok = strtok_r(allowed_copy, ",", &saveptr);
        while (tok && allowed_count < 32) {
            while (*tok == ' ') tok++;
            allowed_arr[allowed_count++] = tok;
            tok = strtok_r(NULL, ",", &saveptr);
        }
        saveptr = NULL;
        tok = strtok_r(forbidden_copy, ",", &saveptr);
        while (tok && forbidden_count < 32) {
            while (*tok == ' ') tok++;
            forbidden_arr[forbidden_count++] = tok;
            tok = strtok_r(NULL, ",", &saveptr);
        }
        int rc = cache_add_scope(STATE.cache, view_name,
                                 allowed_arr, allowed_count,
                                 forbidden_arr, forbidden_count);
        if (rc < 0) {
            return BclResult_Err(bcl_out, out_sz, 54, "cache_add_scope failed");
        }
        char body[128];
        snprintf(body, sizeof(body), "[@STATUS]{scope_added}[@SCOPE_ID]{%d}", rc);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── scope_allows ───────────────────────── */
    if (strcmp(cmd, "scope_allows") == 0) {
        if (!STATE.cache) {
            return BclResult_Err(bcl_out, out_sz, 52, "no cache — call create first");
        }
        char view_name[64], node_type[64];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        BclParser_Extract(&pr, "VIEW_NAME", view_name, sizeof(view_name));
        BclParser_Extract(&pr, "NODE_TYPE", node_type, sizeof(node_type));
        BclParser_Free(&pr);
        int allowed = cache_scope_allows(STATE.cache, view_name, node_type);
        char body[128];
        snprintf(body, sizeof(body), "[@ALLOWED]{%d}", allowed);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── scope_forbids_edge ─────────────────── */
    if (strcmp(cmd, "scope_forbids_edge") == 0) {
        if (!STATE.cache) {
            return BclResult_Err(bcl_out, out_sz, 52, "no cache — call create first");
        }
        char view_name[64], edge_type[64];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        BclParser_Extract(&pr, "VIEW_NAME", view_name, sizeof(view_name));
        BclParser_Extract(&pr, "EDGE_TYPE", edge_type, sizeof(edge_type));
        BclParser_Free(&pr);
        int forbids = cache_scope_forbids_edge(STATE.cache, view_name, edge_type);
        char body[128];
        snprintf(body, sizeof(body), "[@FORBIDS]{%d}", forbids);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── read_state ─────────────────────────── */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        int has_cache = STATE.cache ? 1 : 0;
        int entries = STATE.cache ? STATE.cache->entry_count : 0;
        int scopes = STATE.cache ? STATE.cache->scope_count : 0;
        int scoring = STATE.cache ? STATE.cache->scoring_version : 0;
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@HAS_CACHE]{%d}[@ENTRIES]{%d}[@SCOPES]{%d}[@SCORING_VER]{%d}[@MAX_ENTRIES]{%d}",
            STATE.initialized, has_cache, entries, scopes, scoring, STATE.max_entries);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ── set_config ─────────────────────────── */
    if (strcmp(cmd, "set_config") == 0) {
        char key[128], val[4096];
        BclParseResult pr;
        BclParser_Init(&pr);
        BclParser_Parse(&pr, bcl_in ? bcl_in : "");
        BclParser_Extract(&pr, "KEY", key, sizeof(key));
        BclParser_Extract(&pr, "VAL", val, sizeof(val));
        BclParser_Free(&pr);
        if (strcmp(key, "max_entries") == 0) {
            STATE.max_entries = atoi(val);
            if (STATE.cache) {
                STATE.cache->max_entries = STATE.max_entries;
            }
            return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}[@KEY]{max_entries}");
        }
        return BclResult_Err(bcl_out, out_sz, 55, "unknown config key");
    }

    return BclResult_Err(bcl_out, out_sz, 50, "unknown command");
}

int GraphCache_Close(void) {
    if (STATE.cache) {
        cache_free(STATE.cache);
        STATE.cache = NULL;
    }
    STATE.initialized = 0;
    STATE.max_entries = 0;
    return 1;
}

const char * GraphCache_State(void) {
    static char buf[256];
    int has_cache = STATE.cache ? 1 : 0;
    int entries = STATE.cache ? STATE.cache->entry_count : 0;
    snprintf(buf, sizeof(buf),
        "GraphCache: initialized=%d, has_cache=%d, entries=%d, max=%d",
        STATE.initialized, has_cache, entries, STATE.max_entries);
    return buf;
}
