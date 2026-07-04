/*
 * cognitive_core.c — Multi-provider execution fabric in C
 *
 * Layers:
 *   L1 Transport  — providers (gemini browser, msearch local)
 *   L2 Extraction — raw output capture
 *   L3 Normalization — unified node schema
 *   L4 Merge Engine — dedup, cluster, conflict detection
 *   L5 Cache — SQLite
 *
 * Build: cc cognitive_core.c -o cognitive_core -lsqlite3 -lpthread
 * Run:   ./cognitive_core
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>
#include <time.h>
#include <sqlite3.h>

#define MAX_PROVIDERS 4
#define MAX_CONTENT_LEN 4096

/* --- LAYER 3: UNIFIED NORMALIZATION SCHEMA --- */

typedef enum {
    TYPE_CODE,
    TYPE_EXPLANATION,
    TYPE_SUGGESTION,
    TYPE_FACT
} NodeType;

typedef struct {
    char source[32];
    uint64_t timestamp;
    char content_block[MAX_CONTENT_LEN];
    double system_confidence;
    NodeType type;
    char trace_id[64];
} NormalizedNode;

/* Payload packet passed to each async provider thread */
typedef struct {
    char query[256];
    char trace_id[64];
    NormalizedNode *output_slot;
    int is_done;
} ProviderTask;

/* --- LAYER 5: SQLITE CACHING LAYER --- */

sqlite3* init_cache_db() {
    sqlite3 *db;
    int rc = sqlite3_open("cognitive_cache.db", &db);
    if (rc != SQLITE_OK) return NULL;

    const char *sql = "CREATE TABLE IF NOT EXISTS cache ("
                      "query_hash TEXT PRIMARY KEY, "
                      "serialized_graph TEXT, "
                      "timestamp INTEGER);";
    sqlite3_exec(db, sql, NULL, 0, NULL);
    return db;
}

int check_cache(sqlite3 *db, const char *query, char *output_buffer) {
    sqlite3_stmt *stmt;
    const char *sql = "SELECT serialized_graph FROM cache WHERE query_hash = ?;";
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK) return 0;

    sqlite3_bind_text(stmt, 1, query, -1, SQLITE_STATIC);
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        strcpy(output_buffer, (const char*)sqlite3_column_text(stmt, 0));
        sqlite3_finalize(stmt);
        return 1; /* Cache Hit */
    }
    sqlite3_finalize(stmt);
    return 0; /* Cache Miss */
}

/* --- L1 & L2 REAL PROVIDERS (TRANSPORT & EXTRACTION) --- */

#define GEMINI_SCRIPT "python3 /Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/bin_tools/gemini_cli.py"
#define MSEARCH_BIN   "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/Built_tools/msearch"

/* Run a shell command and capture stdout into provided buffer */
static int run_command(const char *cmd, char *buffer, size_t bufsize) {
    FILE *fp = popen(cmd, "r");
    if (!fp) return -1;
    size_t total = 0;
    char chunk[1024];
    while (fgets(chunk, sizeof(chunk), fp)) {
        size_t len = strlen(chunk);
        if (total + len < bufsize - 1) {
            memcpy(buffer + total, chunk, len);
            total += len;
        }
    }
    buffer[total] = '\0';
    pclose(fp);
    return (int)total;
}

void* exec_gemini_browser(void *arg) {
    ProviderTask *task = (ProviderTask*)arg;

    /* L1: Fire browser CLI automation — real popen to gemini_cli.py */
    char cmd[512];
    snprintf(cmd, sizeof(cmd), "%s \"%s\"", GEMINI_SCRIPT, task->query);

    /* L2: Capture stdout */
    char local_buf[MAX_CONTENT_LEN];
    int len = run_command(cmd, local_buf, MAX_CONTENT_LEN);

    /* L3: Normalize output */
    strcpy(task->output_slot->source, "Gemini_Browser");
    task->output_slot->timestamp = (uint64_t)time(NULL);
    if (len > 0) {
        strncpy(task->output_slot->content_block, local_buf, MAX_CONTENT_LEN - 1);
        task->output_slot->content_block[MAX_CONTENT_LEN - 1] = '\0';
        task->output_slot->system_confidence = 0.80;
        task->output_slot->type = TYPE_EXPLANATION;
    } else {
        snprintf(task->output_slot->content_block, MAX_CONTENT_LEN, "[GEMINI ERROR] no output");
        task->output_slot->system_confidence = 0.0;
        task->output_slot->type = TYPE_EXPLANATION;
    }
    strcpy(task->output_slot->trace_id, task->trace_id);

    task->is_done = 1;
    return NULL;
}

void* exec_msearch_local(void *arg) {
    ProviderTask *task = (ProviderTask*)arg;

    /* L1 & L2: Execute real msearch binary */
    char cmd[512];
    snprintf(cmd, sizeof(cmd), "%s \"%s\"", MSEARCH_BIN, task->query);
    char local_buf[MAX_CONTENT_LEN];
    int len = run_command(cmd, local_buf, MAX_CONTENT_LEN);

    /* L3: Normalize output */
    strcpy(task->output_slot->source, "msearch_DB");
    task->output_slot->timestamp = (uint64_t)time(NULL);
    if (len > 0) {
        strncpy(task->output_slot->content_block, local_buf, MAX_CONTENT_LEN - 1);
        task->output_slot->content_block[MAX_CONTENT_LEN - 1] = '\0';
        task->output_slot->system_confidence = 0.99; /* Deterministic DB = high confidence */
        task->output_slot->type = TYPE_FACT;
    } else {
        snprintf(task->output_slot->content_block, MAX_CONTENT_LEN, "[MSEARCH ERROR] no output");
        task->output_slot->system_confidence = 0.0;
        task->output_slot->type = TYPE_FACT;
    }
    strcpy(task->output_slot->trace_id, task->trace_id);

    task->is_done = 1;
    return NULL;
}

/* --- COGNITIVE MERGE & INJECTION ENGINE --- */

void cognitive_merge(NormalizedNode nodes[], int count) {
    printf("\n[COGNITIVE MERGE ENGINE INITIALIZED]\n");
    printf("----------------------------------------\n");
    for (int i = 0; i < count; i++) {
        const char *type_str;
        switch (nodes[i].type) {
            case TYPE_CODE:        type_str = "CODE"; break;
            case TYPE_EXPLANATION: type_str = "EXPLANATION"; break;
            case TYPE_SUGGESTION:  type_str = "SUGGESTION"; break;
            case TYPE_FACT:        type_str = "FACT"; break;
            default:               type_str = "UNKNOWN"; break;
        }
        printf("[Node %d] Source: %s | Type: %s | Confidence: %.2f\n",
               i, nodes[i].source, type_str, nodes[i].system_confidence);
        printf("Payload: %s\n\n", nodes[i].content_block);
    }
    /*
     * Future execution matrix rules:
     * Step 1: Deduplication (cross-source content hashing)
     * Step 2: Clustering (group nodes via matching trace_ids or shared entities)
     * Step 3: Conflict detection (flag if msearch facts oppose LLM code assumptions)
     */
}

int main() {
    char query[256] = "mutex_lock sync bounds";
    char trace_id[64] = "tr_0192a3bc_x90";
    char cache_payload[MAX_CONTENT_LEN];

    sqlite3 *cache_db = init_cache_db();

    /* Check caching layer first */
    if (cache_db && check_cache(cache_db, query, cache_payload)) {
        printf("[CACHE HIT] Reconstructed cognitive map instantly.\n%s\n", cache_payload);
        sqlite3_close(cache_db);
        return 0;
    }

    printf("[CACHE MISS] Spawning parallel fanout execution fabric...\n");

    pthread_t threads[MAX_PROVIDERS];
    ProviderTask tasks[MAX_PROVIDERS];
    NormalizedNode field_nodes[MAX_PROVIDERS];

    /* Setup Parallel Tasks */
    memset(&tasks[0], 0, sizeof(ProviderTask));
    tasks[0].output_slot = &field_nodes[0];
    tasks[0].is_done = 0;
    strcpy(tasks[0].query, query);
    strcpy(tasks[0].trace_id, trace_id);

    memset(&tasks[1], 0, sizeof(ProviderTask));
    tasks[1].output_slot = &field_nodes[1];
    tasks[1].is_done = 0;
    strcpy(tasks[1].query, query);
    strcpy(tasks[1].trace_id, trace_id);

    /* PARALLEL FANOUT: Fire all provider threads concurrently */
    pthread_create(&threads[0], NULL, exec_gemini_browser, &tasks[0]);
    pthread_create(&threads[1], NULL, exec_msearch_local, &tasks[1]);

    /* Asynchronous collection loop (Join barrier) */
    for (int i = 0; i < 2; i++) {
        pthread_join(threads[i], NULL);
    }

    /* Pass normalized structured blocks to Layer 4 & Cognitive Merger */
    cognitive_merge(field_nodes, 2);

    /* Clean up */
    if (cache_db) sqlite3_close(cache_db);
    return 0;
}
