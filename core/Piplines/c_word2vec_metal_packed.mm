//[@GHOST]{file_path="core/Piplines/c_word2vec_metal_packed.mm" date="2026-06-30" author="cascade" session_id="c-sgns-packed" context="Metal GPU Word2Vec SGNS — configurable pipeline, pre-packed training. One file, ten classes, BCL flow."}
//[@VBSTYLE]{standard="VBStyle" version="2" rules="PascalCase UPPERCASE"}
//[@FILEID]{id="c_word2vec_metal_packed.mm" domain="word_engine" authority="VBEnginePacked"}
//[@SUMMARY]{summary="Configurable Word2Vec SGNS pipeline. Config → DataSource → Tokenizer → VocabBuilder → CorpusBuilder → PairGenerator → Pantry → MetalTrainer → ModelSaver → SimilaritySearch. CLI at bottom wires it all."}

// ============ BCL FLOW ============
//
// [@FLOW]{
//   [@STEP]{1;  "Config";         "Read vbengine.conf — source type, MySQL params, file extensions, training hyperparameters"}
//   [@STEP]{2;  "DataSource";     "Connect to configured source (MySQL/files/SQLite), fetch raw file contents into RAM"}
//   [@STEP]{3;  "Tokenizer";      "Extract identifier tokens [A-Za-z_][A-Za-z0-9_]* from raw content, lowercase"}
//   [@STEP]{4;  "VocabBuilder";   "Count word frequencies, filter by min_count, sort alphabetically for binary search"}
//   [@STEP]{5;  "CorpusBuilder";  "Convert raw content to word-index sequences per file, compute subsampling probabilities"}
//   [@STEP]{6;  "PairGenerator";  "Generate skip-gram pairs with dynamic window + subsampling (the chef — multi-threaded GCD)"}
//   [@STEP]{7;  "Pantry";         "Write packed training.bin — header + vocab + pairs (mise en place — the lunchbox)"}
//   [@STEP]{8;  "MetalTrainer";   "Stream packed pairs to GPU, run SGNS epochs with linear LR decay"}
//   [@STEP]{9;  "ModelSaver";     "L2-normalize embeddings, save model.bin with vocab + float32 weights"}
//   [@STEP]{10; "SimilaritySearch"; "Load model, cosine similarity query for similar words"}
// }
//
// Pipeline CLI:
//   --prepare --config vbengine.conf   → Steps 1-7 (data in → pairs out)
//   --train --pairs training.bin       → Steps 8-9 (pairs in → model out)
//   --model model.bin --similar word   → Step 10 (query)
//
// ============ INCLUDES ============

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <sqlite3.h>
#include <stdint.h>
#include <dispatch/dispatch.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <dirent.h>
#include <mysql/mysql.h>

// ============ CONSTANTS ============

#define MAX_VOCAB         600000
#define NEG_TABLE_SIZE    1000000
#define CHUNK_PAIRS       4000000
#define N_CPU_THREADS     4
#define SOURCE_FILES      1
#define SOURCE_MYSQL      2
#define SOURCE_SQLITE     3
#define MAX_EXTENSIONS    32
#define MAX_PATH          4096

static const char* METAL_SHADER_SOURCE =
#include "metal_shaders_packed.h"
;

// ============ CLASS: Config ============
// Reads vbengine.conf, sets all parameters for the pipeline.
// Struct: CFG — source type, MySQL connection, file scan, token regex
// Struct: STATE — training hyperparameters, vocab/corpus/training state, Metal buffers

static struct {
    int source_type;
    char conf_path[MAX_PATH];
    char mysql_host[256];
    char mysql_user[128];
    char mysql_password[128];
    char mysql_db[128];
    char mysql_table[128];
    char mysql_content_col[64];
    char mysql_path_col[64];
    char files_dir[MAX_PATH];
    int files_recursive;
    char extensions[MAX_EXTENSIONS][16];
    int n_extensions;
    char token_regex[256];
} CFG;

static struct {
    int initialized;
    char db_path[1024];
    char model_path[1024];
    char train_path[1024];
    char init_model_path[1024];
    int use_init_model;
    int dims, epochs, window, neg_samples, min_count;
    double lr_start, lr_end;
    unsigned int seed;
    int verbose;
    int mode;
    int vocab_size, max_word_id;
    char** vocab_words;
    int* vocab_freqs;
    double* vocab_discard_probs;
    int* word_id_to_index;
    __fp16* W_in;
    __fp16* W_out;
    int* neg_table;
    int* corpus;
    int* file_offsets;
    int* file_lengths;
    int total_words, n_files;
    long total_pairs;
    double train_time;
    id<MTLDevice> mtl_device;
    id<MTLCommandQueue> mtl_queue;
    id<MTLComputePipelineState> pipeline_train;
    id<MTLComputePipelineState> pipeline_normalize;
    id<MTLComputePipelineState> pipeline_reset;
    id<MTLBuffer> buf_w_in, buf_w_out, buf_neg_table;
    id<MTLBuffer> buf_pairs;
    id<MTLBuffer> buf_counter;
    int metal_ready;
} STATE;

static unsigned int xorshift32(void) {
    STATE.seed ^= STATE.seed << 13; STATE.seed ^= STATE.seed >> 17; STATE.seed ^= STATE.seed << 5;
    return STATE.seed;
}

static float frand(void) { return (float)(xorshift32() & 0xFFFFFF) / (float)0x1000000; }

static char* Config_Trim(char* s) {
    while (*s == ' ' || *s == '\t' || *s == '\n' || *s == '\r') s++;
    char* end = s + strlen(s) - 1;
    while (end > s && (*end == ' ' || *end == '\t' || *end == '\n' || *end == '\r')) *end-- = 0;
    return s;
}

static int Config_HasExtension(const char* path) {
    const char* dot = strrchr(path, '.');
    if (!dot) return 0;
    for (int i = 0; i < CFG.n_extensions; i++) {
        if (strcmp(dot, CFG.extensions[i]) == 0) return 1;
    }
    return 0;
}

static int Config_Load(const char* path) {
    FILE* f = fopen(path, "r");
    if (!f) { fprintf(stderr, "[CFG] Cannot open %s — using defaults\n", path); return 0; }
    char line[1024];
    while (fgets(line, sizeof(line), f)) {
        char* eq = strchr(line, '=');
        if (!eq) continue;
        *eq = 0;
        char* key = Config_Trim(line);
        char* val = Config_Trim(eq + 1);
        if (strcmp(key, "source") == 0) {
            if (strcmp(val, "mysql") == 0) CFG.source_type = SOURCE_MYSQL;
            else if (strcmp(val, "files") == 0) CFG.source_type = SOURCE_FILES;
            else if (strcmp(val, "sqlite") == 0) CFG.source_type = SOURCE_SQLITE;
        } else if (strcmp(key, "mysql_host") == 0) strncpy(CFG.mysql_host, val, sizeof(CFG.mysql_host)-1);
        else if (strcmp(key, "mysql_user") == 0) strncpy(CFG.mysql_user, val, sizeof(CFG.mysql_user)-1);
        else if (strcmp(key, "mysql_password") == 0) strncpy(CFG.mysql_password, val, sizeof(CFG.mysql_password)-1);
        else if (strcmp(key, "mysql_db") == 0) strncpy(CFG.mysql_db, val, sizeof(CFG.mysql_db)-1);
        else if (strcmp(key, "mysql_table") == 0) strncpy(CFG.mysql_table, val, sizeof(CFG.mysql_table)-1);
        else if (strcmp(key, "mysql_content_col") == 0) strncpy(CFG.mysql_content_col, val, sizeof(CFG.mysql_content_col)-1);
        else if (strcmp(key, "mysql_path_col") == 0) strncpy(CFG.mysql_path_col, val, sizeof(CFG.mysql_path_col)-1);
        else if (strcmp(key, "files_dir") == 0) strncpy(CFG.files_dir, val, sizeof(CFG.files_dir)-1);
        else if (strcmp(key, "files_recursive") == 0) CFG.files_recursive = (strcmp(val, "true") == 0);
        else if (strcmp(key, "extensions") == 0) {
            char* tok = strtok(val, ",");
            while (tok && CFG.n_extensions < MAX_EXTENSIONS) {
                strncpy(CFG.extensions[CFG.n_extensions], Config_Trim(tok), 15);
                CFG.n_extensions++;
                tok = strtok(NULL, ",");
            }
        } else if (strcmp(key, "token_regex") == 0) strncpy(CFG.token_regex, val, sizeof(CFG.token_regex)-1);
        else if (strcmp(key, "dims") == 0) STATE.dims = atoi(val);
        else if (strcmp(key, "window") == 0) STATE.window = atoi(val);
        else if (strcmp(key, "neg_samples") == 0) STATE.neg_samples = atoi(val);
        else if (strcmp(key, "min_count") == 0) STATE.min_count = atoi(val);
        else if (strcmp(key, "epochs") == 0) STATE.epochs = atoi(val);
        else if (strcmp(key, "lr_start") == 0) STATE.lr_start = atof(val);
        else if (strcmp(key, "lr_end") == 0) STATE.lr_end = atof(val);
        else if (strcmp(key, "seed") == 0) STATE.seed = (unsigned int)atol(val);
        else if (strcmp(key, "pairs_file") == 0) strncpy(STATE.train_path, val, sizeof(STATE.train_path)-1);
        else if (strcmp(key, "model_file") == 0) strncpy(STATE.model_path, val, sizeof(STATE.model_path)-1);
    }
    fclose(f);
    if (CFG.source_type == 0) CFG.source_type = SOURCE_MYSQL;
    if (CFG.n_extensions == 0) {
        const char* defaults[] = {".c",".h",".cpp",".hpp",".m",".mm",".py",".md",".txt",".sql",".sh",".json",".yaml",".yml",".bcl"};
        for (int i = 0; i < 15 && CFG.n_extensions < MAX_EXTENSIONS; i++) {
            strncpy(CFG.extensions[CFG.n_extensions], defaults[i], 15);
            CFG.n_extensions++;
        }
    }
    fprintf(stderr, "[CFG] source=%s dims=%d window=%d neg=%d min_count=%d epochs=%d\n",
            CFG.source_type == SOURCE_MYSQL ? "mysql" : CFG.source_type == SOURCE_FILES ? "files" : "sqlite",
            STATE.dims, STATE.window, STATE.neg_samples, STATE.min_count, STATE.epochs);
    return 1;
}

// ============ CLASS: Tokenizer ============
// Extracts identifier tokens from raw text. Simple regex: [A-Za-z_][A-Za-z0-9_]*

static int Tokenizer_IsStart(int c) {
    return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == '_';
}

static int Tokenizer_IsChar(int c) {
    return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_';
}

static void Tokenizer_Lowercase(char* word, int len) {
    for (int k = 0; k < len; k++) if (word[k] >= 'A' && word[k] <= 'Z') word[k] += 32;
}

// ============ CLASS: VocabBuilder ============
// Counts word frequencies across all files, filters by min_count,
// sorts alphabetically for O(log n) binary search lookup.

typedef struct {
    char word[128];
    int freq;
} VocabEntry;

static VocabEntry* VocabBuilder_entries = NULL;
static int VocabBuilder_count = 0;
static int VocabBuilder_capacity = 0;

// --- Hash table for O(1) word lookup during vocab build ---
#define VHASH_SIZE 1048576  // 2^20, power of 2 for fast modulo
#define VHASH_MASK (VHASH_SIZE - 1)
static int* VocabHash_buckets = NULL;   // size VHASH_SIZE, stores first vocab index or -1
static int* VocabHash_next = NULL;      // size VocabBuilder_capacity, chain link

static unsigned int VocabHash_Hash(const char* s) {
    // FNV-1a
    unsigned int h = 2166136261u;
    while (*s) { h ^= (unsigned char)*s++; h *= 16777619u; }
    return h & VHASH_MASK;
}

static void VocabHash_Init(void) {
    VocabHash_buckets = (int*)malloc(VHASH_SIZE * sizeof(int));
    for (int i = 0; i < VHASH_SIZE; i++) VocabHash_buckets[i] = -1;
}

static int VocabBuilder_FindOrAdd(const char* word) {
    if (VocabBuilder_count >= VocabBuilder_capacity) {
        VocabBuilder_capacity = VocabBuilder_capacity ? VocabBuilder_capacity * 2 : 65536;
        VocabBuilder_entries = (VocabEntry*)realloc(VocabBuilder_entries, VocabBuilder_capacity * sizeof(VocabEntry));
        VocabHash_next = (int*)realloc(VocabHash_next, VocabBuilder_capacity * sizeof(int));
    }
    if (!VocabHash_buckets) VocabHash_Init();
    unsigned int h = VocabHash_Hash(word);
    int idx = VocabHash_buckets[h];
    while (idx >= 0) {
        if (strcmp(VocabBuilder_entries[idx].word, word) == 0) {
            VocabBuilder_entries[idx].freq++;
            return idx;
        }
        idx = VocabHash_next[idx];
    }
    // Not found — add new entry
    int newidx = VocabBuilder_count;
    strncpy(VocabBuilder_entries[newidx].word, word, 127);
    VocabBuilder_entries[newidx].word[127] = 0;
    VocabBuilder_entries[newidx].freq = 1;
    VocabHash_next[newidx] = VocabHash_buckets[h];
    VocabHash_buckets[h] = newidx;
    VocabBuilder_count++;
    return newidx;
}

static int VocabBuilder_CompareFreq(const void* a, const void* b) {
    return ((VocabEntry*)b)->freq - ((VocabEntry*)a)->freq;
}

static int VocabBuilder_CompareAlpha(const void* a, const void* b) {
    return strcmp(((VocabEntry*)a)->word, ((VocabEntry*)b)->word);
}

static int VocabBuilder_LookupIndex(const char* word) {
    int lo = 0, hi = STATE.vocab_size - 1;
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;
        int cmp = strcmp(word, STATE.vocab_words[mid]);
        if (cmp == 0) return mid;
        if (cmp < 0) hi = mid - 1; else lo = mid + 1;
    }
    return -1;
}

// ============ CLASS: CorpusBuilder ============
// Converts raw file contents into word-index sequences.
// Builds STATE.corpus[], STATE.file_offsets[], STATE.file_lengths[].
// Also computes subsampling discard probabilities.

static int CorpusBuilder_Build(char** file_contents, int n_files) {
    // Pass 1: tokenize all files, build frequency table
    fprintf(stderr, "[CORPUS] Tokenizing %d files...\n", n_files);
    for (int fi = 0; fi < n_files; fi++) {
        if (fi % 10000 == 0 && fi > 0)
            fprintf(stderr, "[CORPUS]   %d/%d files, vocab=%d\n", fi, n_files, VocabBuilder_count);
        const char* content = file_contents[fi];
        if (!content) continue;
        int len = (int)strlen(content);
        for (int i = 0; i < len; i++) {
            if (!Tokenizer_IsStart(content[i])) continue;
            int j = i + 1;
            while (j < len && Tokenizer_IsChar(content[j])) j++;
            if (j - i >= 2 && j - i < 128) {
                char word[128];
                memcpy(word, content + i, j - i);
                word[j - i] = 0;
                Tokenizer_Lowercase(word, j - i);
                VocabBuilder_FindOrAdd(word);
            }
            i = j - 1;
        }
    }
    fprintf(stderr, "[CORPUS] Raw vocab: %d unique words\n", VocabBuilder_count);

    // Sort by frequency, filter by min_count
    qsort(VocabBuilder_entries, VocabBuilder_count, sizeof(VocabEntry), VocabBuilder_CompareFreq);
    int kept = 0;
    for (int i = 0; i < VocabBuilder_count && kept < MAX_VOCAB; i++) {
        if (VocabBuilder_entries[i].freq >= STATE.min_count) kept++;
        else break;
    }
    fprintf(stderr, "[CORPUS] Filtered vocab: %d words (min_count=%d)\n", kept, STATE.min_count);

    // Sort alphabetically for binary search
    qsort(VocabBuilder_entries, kept, sizeof(VocabEntry), VocabBuilder_CompareAlpha);

    // Build STATE vocab arrays
    STATE.vocab_size = kept;
    STATE.vocab_words = (char**)calloc(kept, sizeof(char*));
    STATE.vocab_freqs = (int*)calloc(kept, sizeof(int));
    STATE.vocab_discard_probs = (double*)calloc(kept, sizeof(double));
    for (int i = 0; i < kept; i++) {
        STATE.vocab_words[i] = strdup(VocabBuilder_entries[i].word);
        STATE.vocab_freqs[i] = VocabBuilder_entries[i].freq;
    }

    // Subsampling discard probabilities
    long tf = 0; for (int i = 0; i < kept; i++) tf += STATE.vocab_freqs[i];
    double t = 1e-4;
    for (int i = 0; i < kept; i++) {
        double fr = (double)STATE.vocab_freqs[i] / tf;
        double p = 1.0 - sqrt(t / fr);
        STATE.vocab_discard_probs[i] = (p > 0) ? p : 0.0;
    }

    // Pass 2: count total words in vocab
    long total = 0;
    for (int fi = 0; fi < n_files; fi++) {
        const char* content = file_contents[fi];
        if (!content) continue;
        int len = (int)strlen(content);
        for (int i = 0; i < len; i++) {
            if (!Tokenizer_IsStart(content[i])) continue;
            int j = i + 1;
            while (j < len && Tokenizer_IsChar(content[j])) j++;
            if (j - i >= 2 && j - i < 128) {
                char word[128];
                memcpy(word, content + i, j - i);
                word[j - i] = 0;
                Tokenizer_Lowercase(word, j - i);
                if (VocabBuilder_LookupIndex(word) >= 0) total++;
            }
            i = j - 1;
        }
    }

    // Pass 3: build corpus array
    STATE.corpus = (int*)malloc(total * sizeof(int));
    STATE.file_offsets = (int*)calloc(n_files, sizeof(int));
    STATE.file_lengths = (int*)calloc(n_files, sizeof(int));
    STATE.n_files = n_files;

    long pos = 0;
    for (int fi = 0; fi < n_files; fi++) {
        STATE.file_offsets[fi] = (int)pos;
        const char* content = file_contents[fi];
        if (!content) continue;
        int len = (int)strlen(content);
        for (int i = 0; i < len; i++) {
            if (!Tokenizer_IsStart(content[i])) continue;
            int j = i + 1;
            while (j < len && Tokenizer_IsChar(content[j])) j++;
            if (j - i >= 2 && j - i < 128) {
                char word[128];
                memcpy(word, content + i, j - i);
                word[j - i] = 0;
                Tokenizer_Lowercase(word, j - i);
                int idx = VocabBuilder_LookupIndex(word);
                if (idx >= 0) { STATE.corpus[pos++] = idx; STATE.file_lengths[fi]++; }
            }
            i = j - 1;
        }
    }
    STATE.total_words = (int)pos;

    // Free file contents and vocab builder temp
    for (int fi = 0; fi < n_files; fi++) free(file_contents[fi]);
    free(file_contents);
    free(VocabBuilder_entries); VocabBuilder_entries = NULL;
    VocabBuilder_count = 0; VocabBuilder_capacity = 0;

    fprintf(stderr, "[CORPUS] Built: %d words, %d files\n", STATE.total_words, STATE.n_files);
    return 1;
}

// ============ CLASS: DataSource ============
// Pluggable data source: MySQL, files, or SQLite (legacy).
// Each source fetches raw file contents into RAM, then hands off to CorpusBuilder.

// --- DataSource: MySQL ---

static int DataSource_Mysql(void) {
    MYSQL* conn = mysql_init(NULL);
    if (!conn) { fprintf(stderr, "[SRC] MySQL init failed\n"); return 0; }
    // Use Unix socket for localhost (NULL host = use socket path)
    const char* host = (strcmp(CFG.mysql_host, "localhost") == 0) ? NULL : CFG.mysql_host;
    const char* pwd = CFG.mysql_password[0] ? CFG.mysql_password : NULL;
    if (!mysql_real_connect(conn, host, CFG.mysql_user, pwd, CFG.mysql_db, 0, "/tmp/mysql.sock", 0)) {
        fprintf(stderr, "[SRC] MySQL connect failed: %s\n", mysql_error(conn));
        mysql_close(conn); return 0;
    }
    fprintf(stderr, "[SRC] MySQL connected: %s/%s\n", CFG.mysql_db, CFG.mysql_table);

    char qcount[512];
    snprintf(qcount, sizeof(qcount), "SELECT COUNT(*) FROM %s", CFG.mysql_table);
    mysql_query(conn, qcount);
    MYSQL_RES* res = mysql_store_result(conn);
    MYSQL_ROW row = mysql_fetch_row(res);
    int n_rows = atoi(row[0]);
    mysql_free_result(res);
    fprintf(stderr, "[SRC] MySQL: %d rows in %s\n", n_rows, CFG.mysql_table);

    char qdata[1024];
    snprintf(qdata, sizeof(qdata), "SELECT %s, %s FROM %s",
             CFG.mysql_content_col, CFG.mysql_path_col, CFG.mysql_table);
    mysql_query(conn, qdata);
    res = mysql_store_result(conn);

    char** file_contents = (char**)malloc(n_rows * sizeof(char*));
    int n_files = 0;
    while ((row = mysql_fetch_row(res)) && n_files < n_rows) {
        unsigned long* lengths = mysql_fetch_lengths(res);
        if (row[0] && lengths[0] > 0) {
            file_contents[n_files] = (char*)malloc(lengths[0] + 1);
            memcpy(file_contents[n_files], row[0], lengths[0]);
            file_contents[n_files][lengths[0]] = 0;
            n_files++;
        }
    }
    mysql_free_result(res);
    mysql_close(conn);
    fprintf(stderr, "[SRC] MySQL: loaded %d files\n", n_files);

    return CorpusBuilder_Build(file_contents, n_files);
}

// --- DataSource: Files ---

static char* DataSource_files_list = NULL;
static int DataSource_files_count = 0;
static int DataSource_files_capacity = 0;
static char** DataSource_files_paths = NULL;

static void DataSource_ScanDir(const char* dir, int recursive) {
    DIR* d = opendir(dir);
    if (!d) return;
    struct dirent* ent;
    while ((ent = readdir(d)) != NULL) {
        if (ent->d_name[0] == '.') continue;
        char fullpath[MAX_PATH];
        snprintf(fullpath, sizeof(fullpath), "%s/%s", dir, ent->d_name);
        struct stat st;
        if (stat(fullpath, &st) != 0) continue;
        if (S_ISDIR(st.st_mode) && recursive) {
            DataSource_ScanDir(fullpath, recursive);
        } else if (S_ISREG(st.st_mode) && Config_HasExtension(fullpath)) {
            if (DataSource_files_count >= DataSource_files_capacity) {
                DataSource_files_capacity = DataSource_files_capacity ? DataSource_files_capacity * 2 : 1024;
                DataSource_files_paths = (char**)realloc(DataSource_files_paths, DataSource_files_capacity * sizeof(char*));
            }
            DataSource_files_paths[DataSource_files_count++] = strdup(fullpath);
        }
    }
    closedir(d);
}

static int DataSource_Files(void) {
    fprintf(stderr, "[SRC] Files: scanning %s\n", CFG.files_dir);
    DataSource_ScanDir(CFG.files_dir, CFG.files_recursive);
    fprintf(stderr, "[SRC] Files: found %d files\n", DataSource_files_count);

    char** file_contents = (char**)malloc(DataSource_files_count * sizeof(char*));
    int n_files = 0;
    for (int i = 0; i < DataSource_files_count; i++) {
        FILE* f = fopen(DataSource_files_paths[i], "r");
        if (!f) continue;
        fseek(f, 0, SEEK_END);
        long sz = ftell(f);
        fseek(f, 0, SEEK_SET);
        file_contents[n_files] = (char*)malloc(sz + 1);
        fread(file_contents[n_files], 1, sz, f);
        file_contents[n_files][sz] = 0;
        fclose(f);
        n_files++;
    }
    for (int i = 0; i < DataSource_files_count; i++) free(DataSource_files_paths[i]);
    free(DataSource_files_paths); DataSource_files_paths = NULL;
    DataSource_files_count = 0; DataSource_files_capacity = 0;

    return CorpusBuilder_Build(file_contents, n_files);
}

// --- DataSource: SQLite (legacy) ---

static int DataSource_SqliteVocab(void) {
    sqlite3* db; sqlite3_stmt* stmt;
    if (sqlite3_open(STATE.db_path, &db) != SQLITE_OK) return 0;
    sqlite3_prepare_v2(db, "SELECT MAX(word_id) FROM vocab", -1, &stmt, NULL);
    if (sqlite3_step(stmt) == SQLITE_ROW) STATE.max_word_id = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);
    const char* sql = "SELECT v.word_id, v.word_lower, COUNT(w.id) as freq "
                      "FROM vocab v JOIN words w ON v.word_id = w.word_id "
                      "GROUP BY v.word_id HAVING freq >= ? ORDER BY freq DESC";
    sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    sqlite3_bind_int(stmt, 1, STATE.min_count);
    STATE.vocab_words = (char**)calloc(MAX_VOCAB, sizeof(char*));
    STATE.vocab_freqs = (int*)calloc(MAX_VOCAB, sizeof(int));
    STATE.word_id_to_index = (int*)malloc((STATE.max_word_id + 1) * sizeof(int));
    memset(STATE.word_id_to_index, -1, (STATE.max_word_id + 1) * sizeof(int));
    while (sqlite3_step(stmt) == SQLITE_ROW && STATE.vocab_size < MAX_VOCAB) {
        int wid = sqlite3_column_int(stmt, 0);
        STATE.vocab_words[STATE.vocab_size] = strdup((const char*)sqlite3_column_text(stmt, 1));
        STATE.vocab_freqs[STATE.vocab_size] = sqlite3_column_int(stmt, 2);
        STATE.word_id_to_index[wid] = STATE.vocab_size++;
    }
    sqlite3_finalize(stmt); sqlite3_close(db);
    STATE.vocab_discard_probs = (double*)calloc(STATE.vocab_size, sizeof(double));
    long tf = 0; for (int i = 0; i < STATE.vocab_size; i++) tf += STATE.vocab_freqs[i];
    double t = 1e-4;
    for (int i = 0; i < STATE.vocab_size; i++) {
        double f = (double)STATE.vocab_freqs[i] / tf;
        double p = 1.0 - sqrt(t / f);
        STATE.vocab_discard_probs[i] = (p > 0) ? p : 0.0;
    }
    if (STATE.verbose) fprintf(stderr, "[SRC] SQLite vocab=%d total_freq=%ld\n", STATE.vocab_size, tf);
    return 1;
}

static int DataSource_SqliteCorpus(void) {
    sqlite3* db; sqlite3_stmt* stmt;
    if (sqlite3_open(STATE.db_path, &db) != SQLITE_OK) return 0;
    sqlite3_prepare_v2(db, "SELECT COUNT(*) FROM words w JOIN vocab v ON w.word_id = v.word_id", -1, &stmt, NULL);
    long total = 0; if (sqlite3_step(stmt) == SQLITE_ROW) total = sqlite3_column_int64(stmt, 0);
    sqlite3_finalize(stmt);
    sqlite3_prepare_v2(db, "SELECT file_id FROM files ORDER BY file_id", -1, &stmt, NULL);
    int* file_ids = (int*)malloc(sizeof(int) * 1000000); int n_files = 0;
    while (sqlite3_step(stmt) == SQLITE_ROW && n_files < 1000000) file_ids[n_files++] = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);
    STATE.corpus = (int*)malloc(total * sizeof(int));
    STATE.file_offsets = (int*)calloc(n_files, sizeof(int));
    STATE.file_lengths = (int*)calloc(n_files, sizeof(int));
    STATE.n_files = n_files;
    const char* sql = "SELECT w.file_id, w.word_id FROM words w JOIN vocab v ON w.word_id = v.word_id ORDER BY w.file_id, w.word_pos";
    sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    int prev_file = -1, file_idx = 0; long pos = 0;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        int fid = sqlite3_column_int(stmt, 0), wid = sqlite3_column_int(stmt, 1);
        if (fid != prev_file) { while (file_idx < n_files && file_ids[file_idx] < fid) file_idx++; if (file_idx < n_files && file_ids[file_idx] == fid) STATE.file_offsets[file_idx] = (int)pos; prev_file = fid; }
        if (wid >= 0 && wid <= STATE.max_word_id) { int idx = STATE.word_id_to_index[wid]; if (idx >= 0) { STATE.corpus[pos] = idx; pos++; if (file_idx < n_files) STATE.file_lengths[file_idx]++; } }
    }
    sqlite3_finalize(stmt); sqlite3_close(db); free(file_ids);
    STATE.total_words = (int)pos;
    if (STATE.verbose) fprintf(stderr, "[SRC] SQLite corpus: %d words, %d files\n", STATE.total_words, STATE.n_files);
    return 1;
}

// --- DataSource: Dispatch ---

static int DataSource_Load(void) {
    if (CFG.source_type == SOURCE_MYSQL) return DataSource_Mysql();
    if (CFG.source_type == SOURCE_FILES) return DataSource_Files();
    // SQLite legacy
    if (!DataSource_SqliteVocab()) return 0;
    if (!DataSource_SqliteCorpus()) return 0;
    return 1;
}

// ============ CLASS: PairGenerator ============
// The chef. Generates skip-gram pairs with dynamic window and subsampling.
// Multi-threaded via Grand Central Dispatch.

typedef struct {
    int* corpus;
    int* file_offsets;
    int* file_lengths;
    double* discard_probs;
    int start_idx, end_idx;
    int window;
    unsigned int rng_seed;
    int* out_pairs;
    int max_pairs;
    int n_generated;
    int n_files;
    int last_idx;
} PairGenTask;

static void PairGenerator_Worker(void* ctx) {
    PairGenTask* task = (PairGenTask*)ctx;
    int* corpus = task->corpus;
    int* out = task->out_pairs;
    int n = 0;
    unsigned int rng = task->rng_seed;
    for (int i = task->start_idx; i < task->end_idx && n < task->max_pairs - 2; i++) {
        task->last_idx = i + 1;
        int center = corpus[i];
        if (center < 0) continue;
        if (task->discard_probs[center] > 0.0) {
            rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
            if ((float)(rng & 0xFFFFFF) / (float)0x1000000 < task->discard_probs[center]) continue;
        }
        int lo = 0, hi = task->n_files - 1;
        while (lo < hi) { int mid = lo + (hi - lo + 1) / 2; if (task->file_offsets[mid] <= i) lo = mid; else hi = mid - 1; }
        int fs = task->file_offsets[lo], fe = fs + task->file_lengths[lo] - 1;
        rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
        int dw = 1 + (int)((float)(rng & 0xFFFFFF) / (float)0x1000000 * (float)task->window);
        if (dw > task->window) dw = task->window;
        int s = i - dw; if (s < fs) s = fs;
        int e = i + dw; if (e > fe) e = fe;
        for (int j = s; j <= e; j++) {
            if (j == i) continue;
            int ctx = corpus[j]; if (ctx < 0) continue;
            if (task->discard_probs[ctx] > 0.0) {
                rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
                if ((float)(rng & 0xFFFFFF) / (float)0x1000000 < task->discard_probs[ctx]) continue;
            }
            out[n * 2] = center; out[n * 2 + 1] = ctx; n++;
            if (n >= task->max_pairs) break;
        }
    }
    task->n_generated = n;
}

// ============ CLASS: Pantry ============
// Writes the packed training.bin file — the lunchbox.
// Format: W2VT magic | dims | vocab_size | neg | window | epochs | lr_start | lr_end
//         | vocab words[] | vocab_freqs[] | pair_count | pairs[]
// Mise en place: everything the GPU chef needs, pre-packed.

static int Pantry_BuildNegTable(void) {
    STATE.neg_table = (int*)calloc(NEG_TABLE_SIZE, sizeof(int));
    double* pf = (double*)calloc(STATE.vocab_size, sizeof(double));
    double tot = 0;
    for (int i = 0; i < STATE.vocab_size; i++) { pf[i] = pow((double)STATE.vocab_freqs[i], 0.75); tot += pf[i]; }
    double cum = 0; int idx = 0;
    for (int i = 0; i < NEG_TABLE_SIZE; i++) {
        double target = (double)i / NEG_TABLE_SIZE;
        while (idx < STATE.vocab_size - 1 && cum / tot < target) { cum += pf[idx]; idx++; }
        STATE.neg_table[i] = idx;
    }
    free(pf); return 1;
}

static int Pantry_Write(void) {
    // Step 2-5: Load data from configured source
    if (!DataSource_Load()) return 0;

    fprintf(stderr, "[PANTRY] Generating training pairs...\n");
    struct timespec ts0; clock_gettime(CLOCK_REALTIME, &ts0);

    FILE* f = fopen(STATE.train_path, "wb");
    if (!f) { fprintf(stderr, "[PANTRY] Cannot create %s\n", STATE.train_path); return 0; }

    // Write header
    const char magic[4] = {'W','2','V','T'};
    fwrite(magic, 1, 4, f);
    int dims = STATE.dims, vsize = STATE.vocab_size, neg = STATE.neg_samples;
    int window = STATE.window, epochs = STATE.epochs;
    fwrite(&dims, 4, 1, f); fwrite(&vsize, 4, 1, f); fwrite(&neg, 4, 1, f);
    fwrite(&window, 4, 1, f); fwrite(&epochs, 4, 1, f);
    fwrite(&STATE.lr_start, 8, 1, f); fwrite(&STATE.lr_end, 8, 1, f);

    // Write vocab
    for (int i = 0; i < vsize; i++) {
        int len = (int)strlen(STATE.vocab_words[i]);
        fwrite(&len, 4, 1, f); fwrite(STATE.vocab_words[i], 1, len, f);
    }
    fwrite(STATE.vocab_freqs, 4, vsize, f);

    // Reserve space for pair count
    long pair_count_offset = ftell(f);
    long total_pairs = 0;
    fwrite(&total_pairs, 8, 1, f);

    // Generate pairs in chunks using all P-cores
    int* chunk_buf = (int*)malloc(CHUNK_PAIRS * 2 * sizeof(int));
    int corpus_pos = 0;

    while (corpus_pos < STATE.total_words) {
        int slice = (STATE.total_words - corpus_pos + N_CPU_THREADS - 1) / N_CPU_THREADS;
        int pairs_per_thread = CHUNK_PAIRS / N_CPU_THREADS;

        PairGenTask* tasks = (PairGenTask*)malloc(N_CPU_THREADS * sizeof(PairGenTask));
        dispatch_queue_t queue = dispatch_get_global_queue(QOS_CLASS_USER_INTERACTIVE, 0);
        dispatch_group_t group = dispatch_group_create();

        for (int t = 0; t < N_CPU_THREADS; t++) {
            int s = corpus_pos + t * slice;
            int e = s + slice; if (e > STATE.total_words) e = STATE.total_words;
            tasks[t].corpus = STATE.corpus;
            tasks[t].file_offsets = STATE.file_offsets;
            tasks[t].file_lengths = STATE.file_lengths;
            tasks[t].discard_probs = STATE.vocab_discard_probs;
            tasks[t].start_idx = s; tasks[t].end_idx = e;
            tasks[t].window = STATE.window;
            tasks[t].rng_seed = STATE.seed + (unsigned int)s * 2654435761u;
            tasks[t].out_pairs = chunk_buf + t * pairs_per_thread * 2;
            tasks[t].max_pairs = pairs_per_thread;
            tasks[t].n_generated = 0;
            tasks[t].n_files = STATE.n_files;
            tasks[t].last_idx = e;

            PairGenTask* tp = &tasks[t];
            dispatch_group_async(group, queue, ^{ PairGenerator_Worker(tp); });
        }
        dispatch_group_wait(group, DISPATCH_TIME_FOREVER);

        // Compact and write
        int chunk_total = 0;
        for (int t = 0; t < N_CPU_THREADS; t++) {
            int n = tasks[t].n_generated;
            if (n > 0) {
                if (t > 0) memmove(chunk_buf + chunk_total * 2, tasks[t].out_pairs, n * 2 * sizeof(int));
                chunk_total += n;
            }
        }

        if (chunk_total > 0) {
            fwrite(chunk_buf, 2 * sizeof(int), chunk_total, f);
            total_pairs += chunk_total;
        }

        int min_pos = STATE.total_words;
        for (int t = 0; t < N_CPU_THREADS; t++) {
            if (tasks[t].last_idx < min_pos) min_pos = tasks[t].last_idx;
        }
        corpus_pos = min_pos;
        if (corpus_pos > STATE.total_words) corpus_pos = STATE.total_words;
        free(tasks);

        if (STATE.verbose && total_pairs % 10000000 < CHUNK_PAIRS) {
            struct timespec tn; clock_gettime(CLOCK_REALTIME, &tn);
            double el = (tn.tv_sec - ts0.tv_sec) + (tn.tv_nsec - ts0.tv_nsec) / 1e9;
            fprintf(stderr, "[PANTRY] %ldM pairs, corpus %.1f%%, time %.1fs\n",
                    total_pairs / 1000000, (double)corpus_pos / STATE.total_words * 100.0, el);
        }
    }

    // Go back and write actual pair count
    fseek(f, pair_count_offset, SEEK_SET);
    fwrite(&total_pairs, 8, 1, f);
    fclose(f);
    free(chunk_buf);

    struct timespec ts1; clock_gettime(CLOCK_REALTIME, &ts1);
    double prep_time = (ts1.tv_sec - ts0.tv_sec) + (ts1.tv_nsec - ts0.tv_nsec) / 1e9;

    fprintf(stderr, "[PANTRY] Done: %ld pairs in %.1fs → %s (%.1f GB)\n",
            total_pairs, prep_time, STATE.train_path,
            (double)(total_pairs * 2 * sizeof(int)) / 1e9);

    // Cleanup corpus (not needed for training)
    free(STATE.corpus); STATE.corpus = NULL;
    free(STATE.file_offsets); STATE.file_offsets = NULL;
    free(STATE.file_lengths); STATE.file_lengths = NULL;

    return 1;
}

// ============ CLASS: MetalTrainer ============
// Streams packed pairs to GPU, runs SGNS epochs with linear LR decay.
// GPU does ONLY: negative sampling + dot product + sigmoid + gradient update.

static int MetalTrainer_Init(void) {
    @autoreleasepool {
        STATE.mtl_device = MTLCreateSystemDefaultDevice();
        if (!STATE.mtl_device) { fprintf(stderr, "[GPU] Metal not available\n"); return 0; }
        STATE.mtl_queue = [STATE.mtl_device newCommandQueue];
        NSError* error = nil;
        NSString* source = [NSString stringWithUTF8String:METAL_SHADER_SOURCE];
        id<MTLLibrary> library = [STATE.mtl_device newLibraryWithSource:source options:nil error:&error];
        if (!library) { fprintf(stderr, "[GPU] Shader error: %s\n", [[error localizedDescription] UTF8String]); return 0; }
        STATE.pipeline_train = [STATE.mtl_device newComputePipelineStateWithFunction:[library newFunctionWithName:@"sgns_train_packed"] error:&error];
        STATE.pipeline_normalize = [STATE.mtl_device newComputePipelineStateWithFunction:[library newFunctionWithName:@"l2_normalize_kernel"] error:&error];
        STATE.pipeline_reset = [STATE.mtl_device newComputePipelineStateWithFunction:[library newFunctionWithName:@"reset_counter"] error:&error];
        if (!STATE.pipeline_train || !STATE.pipeline_normalize || !STATE.pipeline_reset) { fprintf(stderr, "[GPU] Pipeline failed\n"); return 0; }
        STATE.metal_ready = 1;
        if (STATE.verbose) {
            int ew = (int)STATE.pipeline_train.threadExecutionWidth;
            int mt = (int)STATE.pipeline_train.maxTotalThreadsPerThreadgroup;
            fprintf(stderr, "[GPU] %s threadExecWidth=%d maxThreads=%d\n",
                    [[STATE.mtl_device name] UTF8String], ew, mt);
        }
        return 1;
    }
}

static int MetalTrainer_LoadFile(void) {
    FILE* f = fopen(STATE.train_path, "rb");
    if (!f) { fprintf(stderr, "[GPU] Cannot open %s — run with --prepare first\n", STATE.train_path); return 0; }

    char magic[4]; fread(magic, 1, 4, f);
    if (memcmp(magic, "W2VT", 4) != 0) { fprintf(stderr, "[GPU] Bad magic\n"); fclose(f); return 0; }

    fread(&STATE.dims, 4, 1, f);
    fread(&STATE.vocab_size, 4, 1, f);
    fread(&STATE.neg_samples, 4, 1, f);
    fread(&STATE.window, 4, 1, f);
    int file_epochs; fread(&file_epochs, 4, 1, f);  // read but don't override CLI epochs
    double file_lr_start, file_lr_end;
    fread(&file_lr_start, 8, 1, f);
    fread(&file_lr_end, 8, 1, f);
    // Keep CLI-provided epochs/lr if non-zero, otherwise use file values
    if (STATE.epochs <= 0) STATE.epochs = file_epochs;
    if (STATE.lr_start <= 0) STATE.lr_start = file_lr_start;
    if (STATE.lr_end <= 0) STATE.lr_end = file_lr_end;

    STATE.vocab_words = (char**)calloc(STATE.vocab_size, sizeof(char*));
    STATE.vocab_freqs = (int*)calloc(STATE.vocab_size, sizeof(int));
    for (int i = 0; i < STATE.vocab_size; i++) {
        int len; fread(&len, 4, 1, f);
        STATE.vocab_words[i] = (char*)malloc(len + 1);
        fread(STATE.vocab_words[i], 1, len, f);
        STATE.vocab_words[i][len] = 0;
    }
    fread(STATE.vocab_freqs, 4, STATE.vocab_size, f);

    long n_pairs; fread(&n_pairs, 8, 1, f);
    STATE.total_pairs = n_pairs;

    size_t pairs_bytes = (size_t)n_pairs * 2 * sizeof(int);
    fprintf(stderr, "[GPU] Loading %ld pairs (%.1f GB)...\n", n_pairs, (double)pairs_bytes / 1e9);

    fclose(f);
    int fd = open(STATE.train_path, O_RDONLY);
    if (fd < 0) { fprintf(stderr, "[GPU] Cannot open fd\n"); return 0; }

    struct stat st; fstat(fd, &st);
    size_t file_size = st.st_size;

    void* mapped = mmap(NULL, file_size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (mapped == MAP_FAILED) { fprintf(stderr, "[GPU] mmap failed\n"); return 0; }

    size_t offset = 40;  // W2VT header: magic(4)+dims(4)+vsize(4)+neg(4)+window(4)+epochs(4)+lr_start(8)+lr_end(8) = 40
    for (int i = 0; i < STATE.vocab_size; i++) {
        int len = (int)strlen(STATE.vocab_words[i]);
        offset += 4 + len;
    }
    offset += STATE.vocab_size * 4;
    offset += 8;

    STATE.corpus = (int*)((char*)mapped + offset);
    fprintf(stderr, "[GPU] Loaded. pairs=%ld dims=%d vocab=%d\n", n_pairs, STATE.dims, STATE.vocab_size);
    return 1;
}

static int ModelSaver_Load(void);
static int MetalTrainer_InitWeights(void) {
    size_t w_size = (size_t)STATE.vocab_size * STATE.dims;
    STATE.W_in = (__fp16*)calloc(w_size, sizeof(__fp16));
    STATE.W_out = (__fp16*)calloc(w_size, sizeof(__fp16));
    if (STATE.use_init_model && STATE.init_model_path[0]) {
        char saved_model_path[1024];
        strncpy(saved_model_path, STATE.model_path, sizeof(saved_model_path)-1);
        saved_model_path[sizeof(saved_model_path)-1] = 0;
        // Save training params — ModelSaver_Load will clobber them from the init model header
        int saved_dims = STATE.dims, saved_vocab_size = STATE.vocab_size;
        int saved_epochs = STATE.epochs, saved_window = STATE.window, saved_neg = STATE.neg_samples;
        double saved_lr_start = STATE.lr_start, saved_lr_end = STATE.lr_end;
        __fp16* calloc_w_in = STATE.W_in;
        __fp16* calloc_w_out = STATE.W_out;
        fprintf(stderr, "[GPU] Loading init weights from %s\n", STATE.init_model_path);
        strncpy(STATE.model_path, STATE.init_model_path, sizeof(STATE.model_path)-1);
        if (!ModelSaver_Load()) {
            fprintf(stderr, "[GPU] Init model load failed, using random init\n");
            STATE.W_in = calloc_w_in;
            STATE.W_out = calloc_w_out;
            for (size_t i = 0; i < w_size; i++) STATE.W_in[i] = (__fp16)((frand() - 0.5f) * 0.02f);
        } else {
            fprintf(stderr, "[GPU] Init weights loaded (dims=%d vocab=%d)\n", STATE.dims, STATE.vocab_size);
            size_t copy_size = (size_t)STATE.vocab_size * STATE.dims;
            if (copy_size > w_size) copy_size = w_size;
            memcpy(calloc_w_in, STATE.W_in, copy_size * sizeof(__fp16));
            memcpy(calloc_w_out, STATE.W_out, copy_size * sizeof(__fp16));
            free(STATE.W_in);
            free(STATE.W_out);
            STATE.W_in = calloc_w_in;
            STATE.W_out = calloc_w_out;
        }
        // Restore training params
        STATE.dims = saved_dims; STATE.vocab_size = saved_vocab_size;
        STATE.epochs = saved_epochs; STATE.window = saved_window; STATE.neg_samples = saved_neg;
        STATE.lr_start = saved_lr_start; STATE.lr_end = saved_lr_end;
        strncpy(STATE.model_path, saved_model_path, sizeof(STATE.model_path)-1);
    } else {
        for (size_t i = 0; i < w_size; i++) STATE.W_in[i] = (__fp16)((frand() - 0.5f) * 0.02f);
    }
    return 1;
}

static int MetalTrainer_Upload(void) {
    @autoreleasepool {
        size_t w_size = (size_t)STATE.vocab_size * STATE.dims * sizeof(__fp16);
        size_t neg_size = NEG_TABLE_SIZE * sizeof(int);

        STATE.buf_w_in = [STATE.mtl_device newBufferWithBytes:STATE.W_in length:w_size options:MTLResourceStorageModeShared];
        STATE.buf_w_out = [STATE.mtl_device newBufferWithBytes:STATE.W_out length:w_size options:MTLResourceStorageModeShared];

        Pantry_BuildNegTable();
        STATE.buf_neg_table = [STATE.mtl_device newBufferWithBytes:STATE.neg_table length:neg_size options:MTLResourceStorageModeShared];

        size_t pairs_bytes = (size_t)STATE.total_pairs * 2 * sizeof(int);
        STATE.buf_pairs = [STATE.mtl_device newBufferWithBytes:STATE.corpus length:pairs_bytes options:MTLResourceStorageModeShared];
        STATE.buf_counter = [STATE.mtl_device newBufferWithLength:sizeof(uint) options:MTLResourceStorageModeShared];

        if (!STATE.buf_w_in || !STATE.buf_w_out || !STATE.buf_pairs || !STATE.buf_counter) {
            fprintf(stderr, "[GPU] Buffer alloc failed\n"); return 0;
        }

        if (STATE.verbose) {
            size_t total = w_size * 2 + neg_size + pairs_bytes + sizeof(uint);
            fprintf(stderr, "[GPU] Buffers: %zu MB (weights=%zuMB, pairs=%zuMB)\n",
                    total / (1024*1024), w_size * 2 / (1024*1024), pairs_bytes / (1024*1024));
        }
        return 1;
    }
}

static void MetalTrainer_Epoch(float lr, uint rng_seed) {
    @autoreleasepool {
        id<MTLCommandBuffer> cmd_r = [STATE.mtl_queue commandBuffer];
        id<MTLComputeCommandEncoder> enc_r = [cmd_r computeCommandEncoder];
        [enc_r setComputePipelineState:STATE.pipeline_reset];
        [enc_r setBuffer:STATE.buf_counter offset:0 atIndex:0];
        [enc_r dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
        [enc_r endEncoding];
        [cmd_r commit]; [cmd_r waitUntilCompleted];

        int ew = (int)STATE.pipeline_train.threadExecutionWidth;
        int mt = (int)STATE.pipeline_train.maxTotalThreadsPerThreadgroup;
        int tg = ew; if (tg > mt && mt > 0) tg = mt; if (tg < 1) tg = 32;
        int total_persistent = 8 * mt;

        id<MTLCommandBuffer> cmd = [STATE.mtl_queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:STATE.pipeline_train];
        [enc setBuffer:STATE.buf_w_in offset:0 atIndex:0];
        [enc setBuffer:STATE.buf_w_out offset:0 atIndex:1];
        [enc setBuffer:STATE.buf_pairs offset:0 atIndex:2];
        [enc setBuffer:STATE.buf_neg_table offset:0 atIndex:3];
        [enc setBuffer:STATE.buf_counter offset:0 atIndex:4];

        int dims = STATE.dims, neg_samples = STATE.neg_samples;
        int n_pairs = (int)STATE.total_pairs;
        uint nts = NEG_TABLE_SIZE;
        [enc setBytes:&dims length:sizeof(int) atIndex:5];
        [enc setBytes:&n_pairs length:sizeof(int) atIndex:6];
        [enc setBytes:&neg_samples length:sizeof(int) atIndex:7];
        [enc setBytes:&lr length:sizeof(float) atIndex:8];
        [enc setBytes:&nts length:sizeof(uint) atIndex:9];
        [enc setBytes:&rng_seed length:sizeof(uint) atIndex:10];

        [enc dispatchThreads:MTLSizeMake(total_persistent,1,1) threadsPerThreadgroup:MTLSizeMake(tg,1,1)];
        [enc endEncoding];
        [cmd commit]; [cmd waitUntilCompleted];
        if (cmd.status != MTLCommandBufferStatusCompleted) {
            fprintf(stderr, "[GPU] epoch cmd buffer status=%ld error=%s\n",
                    (long)cmd.status, cmd.error ? [[cmd.error localizedDescription] UTF8String] : "none");
        }
    }
}

static void MetalTrainer_Normalize(void) {
    @autoreleasepool {
        int tg = (int)STATE.pipeline_normalize.threadExecutionWidth;
        int mt = (int)STATE.pipeline_normalize.maxTotalThreadsPerThreadgroup;
        if (tg > mt && mt > 0) tg = mt; if (tg < 1) tg = 32;
        id<MTLCommandBuffer> cmd = [STATE.mtl_queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:STATE.pipeline_normalize];
        [enc setBuffer:STATE.buf_w_in offset:0 atIndex:0];
        int dims=STATE.dims, vsize=STATE.vocab_size;
        [enc setBytes:&dims length:sizeof(int) atIndex:1];
        [enc setBytes:&vsize length:sizeof(int) atIndex:2];
        [enc dispatchThreads:MTLSizeMake(vsize,1,1) threadsPerThreadgroup:MTLSizeMake(tg,1,1)];
        [enc endEncoding];
        [cmd commit]; [cmd waitUntilCompleted];
    }
}

static int MetalTrainer_Run(void) {
    if (!MetalTrainer_Init()) return 0;
    if (!MetalTrainer_InitWeights()) return 0;
    if (!MetalTrainer_Upload()) return 0;

    struct timespec ts0; clock_gettime(CLOCK_REALTIME, &ts0);
    fprintf(stderr, "[GPU] starting epoch loop: epochs=%d pairs=%ld dims=%d vocab=%d\n", STATE.epochs, STATE.total_pairs, STATE.dims, STATE.vocab_size);

    for (int epoch = 0; epoch < STATE.epochs; epoch++) {
        double progress = (double)(epoch + 1) / STATE.epochs;
        double lr = STATE.lr_start - (STATE.lr_start - STATE.lr_end) * progress;
        if (lr < STATE.lr_end) lr = STATE.lr_end;
        uint rng_seed = STATE.seed + (uint)epoch * 7919u;

        MetalTrainer_Epoch((float)lr, rng_seed);

        if (STATE.verbose) {
            struct timespec tn; clock_gettime(CLOCK_REALTIME, &tn);
            double el = (tn.tv_sec - ts0.tv_sec) + (tn.tv_nsec - ts0.tv_nsec) / 1e9;
            fprintf(stderr, "[GPU] epoch %d/%d lr=%.5f pairs=%ld time=%.2fs\n",
                    epoch+1, STATE.epochs, lr, STATE.total_pairs, el);
        }
    }

    struct timespec ts1; clock_gettime(CLOCK_REALTIME, &ts1);
    STATE.train_time = (ts1.tv_sec - ts0.tv_sec) + (ts1.tv_nsec - ts0.tv_nsec) / 1e9;
    fprintf(stderr, "[GPU] training done: %.2fs (%.1fM pairs/s)\n",
            STATE.train_time, (double)STATE.total_pairs * STATE.epochs / STATE.train_time / 1e6);

    // Read back weights from Metal buffers to CPU memory
    size_t w_bytes = (size_t)STATE.vocab_size * STATE.dims * sizeof(__fp16);
    memcpy(STATE.W_in, [STATE.buf_w_in contents], w_bytes);
    memcpy(STATE.W_out, [STATE.buf_w_out contents], w_bytes);
    fprintf(stderr, "[GPU] weights read back from Metal buffers\n");
    return 1;
}

// ============ CLASS: ModelSaver ============
// L2-normalizes embeddings, saves model.bin with vocab + float32 weights.

static int ModelSaver_Save(void) {
    MetalTrainer_Normalize();
    size_t w_size = (size_t)STATE.vocab_size * STATE.dims;
    float* W_in_f32 = (float*)malloc(w_size * sizeof(float));
    float* W_out_f32 = (float*)malloc(w_size * sizeof(float));
    for (size_t i = 0; i < w_size; i++) { W_in_f32[i] = (float)STATE.W_in[i]; W_out_f32[i] = (float)STATE.W_out[i]; }
    int dims = STATE.dims, vsize = STATE.vocab_size;
    FILE* f = fopen(STATE.model_path, "wb"); if (!f) return 0;
    const char magic[4] = {'W','2','V','C'};
    fwrite(magic, 1, 4, f); fwrite(&dims, 4, 1, f); fwrite(&vsize, 4, 1, f);
    fwrite(&STATE.epochs, 4, 1, f); fwrite(&STATE.window, 4, 1, f); fwrite(&STATE.neg_samples, 4, 1, f);
    fwrite(&STATE.lr_start, 8, 1, f); fwrite(&STATE.lr_end, 8, 1, f);
    for (int i = 0; i < vsize; i++) { int len = (int)strlen(STATE.vocab_words[i]); fwrite(&len, 4, 1, f); fwrite(STATE.vocab_words[i], 1, len, f); }
    fwrite(STATE.vocab_freqs, 4, vsize, f);
    fwrite(W_in_f32, 4, w_size, f); fwrite(W_out_f32, 4, w_size, f);
    fclose(f); free(W_in_f32); free(W_out_f32);
    fprintf(stderr, "[MODEL] saved: %s\n", STATE.model_path);
    return 1;
}

static int ModelSaver_Load(void) {
    FILE* f = fopen(STATE.model_path, "rb"); if (!f) return 0;
    char magic[4]; fread(magic, 1, 4, f);
    if (memcmp(magic, "W2VC", 4) != 0) { fclose(f); return 0; }
    fread(&STATE.dims, 4, 1, f); fread(&STATE.vocab_size, 4, 1, f);
    fread(&STATE.epochs, 4, 1, f); fread(&STATE.window, 4, 1, f); fread(&STATE.neg_samples, 4, 1, f);
    fread(&STATE.lr_start, 8, 1, f); fread(&STATE.lr_end, 8, 1, f);
    STATE.vocab_words = (char**)calloc(STATE.vocab_size, sizeof(char*));
    STATE.vocab_freqs = (int*)calloc(STATE.vocab_size, sizeof(int));
    for (int i = 0; i < STATE.vocab_size; i++) {
        int len; fread(&len, 4, 1, f);
        STATE.vocab_words[i] = (char*)malloc(len+1);
        fread(STATE.vocab_words[i], 1, len, f);
        STATE.vocab_words[i][len] = 0;
    }
    fread(STATE.vocab_freqs, 4, STATE.vocab_size, f);
    size_t w_size = (size_t)STATE.vocab_size * STATE.dims;
    float* W_in_f32 = (float*)malloc(w_size * sizeof(float));
    float* W_out_f32 = (float*)malloc(w_size * sizeof(float));
    fread(W_in_f32, 4, w_size, f); fread(W_out_f32, 4, w_size, f);
    fclose(f);
    STATE.W_in = (__fp16*)malloc(w_size * sizeof(__fp16));
    STATE.W_out = (__fp16*)malloc(w_size * sizeof(__fp16));
    for (size_t i = 0; i < w_size; i++) { STATE.W_in[i] = (__fp16)W_in_f32[i]; STATE.W_out[i] = (__fp16)W_out_f32[i]; }
    free(W_in_f32); free(W_out_f32);
    return 1;
}

// ============ CLASS: SimilaritySearch ============
// Loads model, computes cosine similarity against all words, prints top-k.

static int SimilaritySearch_Query(const char* word, int top_k) {
    int target = -1;
    for (int i = 0; i < STATE.vocab_size; i++) {
        if (strcmp(STATE.vocab_words[i], word) == 0) { target = i; break; }
    }
    if (target < 0) { fprintf(stderr, "[SEARCH] Word not found: %s\n", word); return 0; }
    int dims = STATE.dims;
    __fp16* tv = STATE.W_in + (size_t)target * dims;
    float tnorm = 0; for (int d = 0; d < dims; d++) { float f = (float)tv[d]; tnorm += f*f; }
    tnorm = sqrtf(tnorm); if (tnorm == 0) tnorm = 1;
    float* scores = (float*)calloc(STATE.vocab_size, sizeof(float));
    for (int i = 0; i < STATE.vocab_size; i++) {
        if (i == target) { scores[i] = -1; continue; }
        __fp16* v = STATE.W_in + (size_t)i * dims;
        float dot = 0, norm = 0;
        for (int d = 0; d < dims; d++) { float f = (float)v[d]; float tf = (float)tv[d]; dot += tf*f; norm += f*f; }
        norm = sqrtf(norm); if (norm == 0) norm = 1;
        scores[i] = dot / (tnorm * norm);
    }
    for (int k = 0; k < top_k; k++) {
        int best = 0; for (int i = 1; i < STATE.vocab_size; i++) if (scores[i] > scores[best]) best = i;
        if (scores[best] < -0.5f) break;
        fprintf(stderr, "  %-30s %.4f\n", STATE.vocab_words[best], scores[best]);
        scores[best] = -2;
    }
    free(scores); return 1;
}

// ============ CLI ============
// Wires the pipeline together. Input source → actions → output destination.
//
//   --prepare --config vbengine.conf   → Steps 1-7 (data in → pairs out)
//   --train --pairs training.bin       → Steps 8-9 (pairs in → model out)
//   --model model.bin --similar word   → Step 10 (query)

static void CLI_ParseArgs(int argc, char** argv) {
    STATE.mode = -1;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--prepare") == 0) STATE.mode = 0;
        else if (strcmp(argv[i], "--train") == 0) STATE.mode = 1;
        else if (strcmp(argv[i], "--config") == 0 && i+1 < argc) {
            strncpy(CFG.conf_path, argv[++i], sizeof(CFG.conf_path)-1);
            Config_Load(CFG.conf_path);
        }
        else if (strcmp(argv[i], "--db") == 0 && i+1 < argc) strncpy(STATE.db_path, argv[++i], sizeof(STATE.db_path)-1);
        else if (strcmp(argv[i], "--model") == 0 && i+1 < argc) strncpy(STATE.model_path, argv[++i], sizeof(STATE.model_path)-1);
        else if (strcmp(argv[i], "--pairs") == 0 && i+1 < argc) strncpy(STATE.train_path, argv[++i], sizeof(STATE.train_path)-1);
        else if (strcmp(argv[i], "--init-model") == 0 && i+1 < argc) { strncpy(STATE.init_model_path, argv[++i], sizeof(STATE.init_model_path)-1); STATE.use_init_model = 1; }
        else if (strcmp(argv[i], "--dims") == 0 && i+1 < argc) STATE.dims = atoi(argv[++i]);
        else if (strcmp(argv[i], "--epochs") == 0 && i+1 < argc) STATE.epochs = atoi(argv[++i]);
        else if (strcmp(argv[i], "--window") == 0 && i+1 < argc) STATE.window = atoi(argv[++i]);
        else if (strcmp(argv[i], "--neg") == 0 && i+1 < argc) STATE.neg_samples = atoi(argv[++i]);
        else if (strcmp(argv[i], "--min-count") == 0 && i+1 < argc) STATE.min_count = atoi(argv[++i]);
        else if (strcmp(argv[i], "--lr") == 0 && i+1 < argc) STATE.lr_start = atof(argv[++i]);
        else if (strcmp(argv[i], "--quiet") == 0) STATE.verbose = 0;
        else if (strcmp(argv[i], "--similar") == 0 && i+1 < argc) {
            if (!ModelSaver_Load()) { fprintf(stderr, "[CLI] Cannot load model %s\n", STATE.model_path); return; }
            SimilaritySearch_Query(argv[++i], 20);
            return;
        }
    }
}

int main(int argc, char** argv) {
    memset((void*)&STATE, 0, sizeof(STATE));
    memset((void*)&CFG, 0, sizeof(CFG));
    STATE.initialized = 1; STATE.dims = 128; STATE.epochs = 5; STATE.window = 5;
    STATE.neg_samples = 5; STATE.min_count = 5; STATE.lr_start = 0.025; STATE.lr_end = 0.0001;
    STATE.seed = 42; STATE.verbose = 1;
    strncpy(STATE.model_path, "word2vec_packed_model.bin", sizeof(STATE.model_path)-1);
    strncpy(STATE.train_path, "training.bin", sizeof(STATE.train_path)-1);
    strncpy(CFG.conf_path, "vbengine.conf", sizeof(CFG.conf_path)-1);

    // Pre-scan for --config to load before other args override
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--config") == 0 && i+1 < argc) {
            strncpy(CFG.conf_path, argv[i+1], sizeof(CFG.conf_path)-1);
            break;
        }
    }
    Config_Load(CFG.conf_path);
    CLI_ParseArgs(argc, argv);

    if (STATE.mode == 0) {
        // PREPARE: Steps 1-7 — data source → tokenizer → vocab → corpus → pairs → pantry
        fprintf(stderr, "=== PREPARE PHASE ===\n");
        fprintf(stderr, "  Input source: %s\n",
                CFG.source_type == SOURCE_MYSQL ? "mysql" : CFG.source_type == SOURCE_FILES ? "files" : "sqlite");
        fprintf(stderr, "  Output pantry: %s\n", STATE.train_path);
        fprintf(stderr, "  dims=%d window=%d neg=%d min_count=%d\n",
                STATE.dims, STATE.window, STATE.neg_samples, STATE.min_count);
        if (!Pantry_Write()) return 1;
        fprintf(stderr, "\nNow run: %s --train --pairs %s --model %s --epochs %d\n",
                argv[0], STATE.train_path, STATE.model_path, STATE.epochs);
    } else if (STATE.mode == 1) {
        // TRAIN: Steps 8-9 — GPU training → model save
        fprintf(stderr, "=== TRAIN PHASE ===\n");
        fprintf(stderr, "  Input pantry: %s\n", STATE.train_path);
        fprintf(stderr, "  Output model: %s\n", STATE.model_path);
        if (!MetalTrainer_LoadFile()) return 1;
        if (!MetalTrainer_Run()) return 1;
        if (!ModelSaver_Save()) return 1;
        fprintf(stderr, "\nDone. Test: %s --model %s --similar word\n", argv[0], STATE.model_path);
    } else {
        fprintf(stderr, "VBEngine — Word2Vec SGNS Pipeline\n\n");
        fprintf(stderr, "Usage:\n");
        fprintf(stderr, "  %s --prepare --config vbengine.conf\n", argv[0]);
        fprintf(stderr, "    Steps 1-7: Config → DataSource → Tokenizer → Vocab → Corpus → Pairs → Pantry\n");
        fprintf(stderr, "    Input:  vbengine.conf (source=mysql|files|sqlite)\n");
        fprintf(stderr, "    Output: training.bin (packed pairs)\n\n");
        fprintf(stderr, "  %s --train --pairs training.bin --model model.bin\n", argv[0]);
        fprintf(stderr, "    Steps 8-9: MetalTrainer → ModelSaver\n");
        fprintf(stderr, "    Input:  training.bin (packed pairs)\n");
        fprintf(stderr, "    Output: model.bin (trained embeddings)\n\n");
        fprintf(stderr, "  %s --model model.bin --similar word\n", argv[0]);
        fprintf(stderr, "    Step 10: SimilaritySearch\n\n");
        fprintf(stderr, "Options: --config FILE --dims N --epochs N --window N --neg N --min-count N --lr F --quiet\n");
    }
    return 0;
}
