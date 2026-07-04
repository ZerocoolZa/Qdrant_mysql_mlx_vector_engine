/*
 * bloodhound.h - Persistent Perception Engine
 *[@GHOST]
 *[@VBSTYLE]
 *[@FILEID] bloodhound.h
 *[@SUMMARY] All types, structs, constants, function declarations for LMDB+Zstd Bloodhound
 *[@CLASS] Bloodhound
 *[@METHOD] Scan, Query, Remember, Sync, Report, Watch, Export, Decay
 */

#ifndef BLOODHOUND_H
#define BLOODHOUND_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include <sys/stat.h>
#include <dirent.h>
#include <ctype.h>
#include <errno.h>
#include <unistd.h>
#include <signal.h>

#include <lmdb.h>
#include <zstd.h>

#ifdef __APPLE__
#include <CommonCrypto/CommonDigest.h>
#endif

/* ---- Constants ---- */

#define BH_DB_DIR          "~/.bloodhound"
#define BH_DB_FILE         "bloodhound.mdb"
#define BH_DRIVE_PATH      "/Users/wws/Library/CloudStorage/GoogleDrive-kautharlodewyk9@gmail.com/My Drive/Bloodhound/"
#define BH_MAX_LINE        4096
#define BH_MAX_TOKEN       256
#define BH_MAX_PATH        1024
#define BH_MAX_SCENTS      10000
#define BH_CONTEXT_LINES   3
#define BH_LMDB_MAP_SIZE   (1ULL << 30)
#define BH_LMDB_MAX_DBS    32
#define BH_ZSTD_LEVEL      3
#define BH_MAX_REL         1000
#define BH_MAX_RESULTS     100
#define BH_WATCH_INTERVAL  5

/* ---- Scent Types ---- */

#define BH_TYPE_FUNCTION   "function"
#define BH_TYPE_CLASS      "class"
#define BH_TYPE_IMPORT     "import"
#define BH_TYPE_SYMBOL     "symbol"
#define BH_TYPE_HEADING    "heading"
#define BH_TYPE_KEYWORD    "keyword"
#define BH_TYPE_BRACKET    "bracket"
#define BH_TYPE_PATH       "path"
#define BH_TYPE_COMMENT    "comment"
#define BH_TYPE_WORD       "word"
#define BH_TYPE_DEFINE     "define"
#define BH_TYPE_INCLUDE    "include"
#define BH_TYPE_STRUCT     "struct"
#define BH_TYPE_KEY        "key"
#define BH_TYPE_TABLE      "table"
#define BH_TYPE_COLUMN     "column"
#define BH_TYPE_ENUM       "enum"
#define BH_TYPE_INTERFACE  "interface"
#define BH_TYPE_PACKAGE    "package"
#define BH_TYPE_VARIABLE   "variable"
#define BH_TYPE_FIELD      "field"
#define BH_TYPE_TAG        "tag"

/* ---- LMDB Sub-DB Names ---- */

#define BH_DB_SCENTS       "scents"
#define BH_DB_FP_INDEX     "fp_index"
#define BH_DB_FILE_SCENTS  "file_scents"
#define BH_DB_TYPE_INDEX   "type_index"
#define BH_DB_LANG_INDEX   "lang_index"
#define BH_DB_WS_INDEX     "ws_index"
#define BH_DB_FILES        "files"
#define BH_DB_FILE_PATHS   "file_paths"
#define BH_DB_FILE_HASHES  "file_hashes"
#define BH_DB_OBSERVATIONS "observations"
#define BH_DB_OBS_RECENT   "obs_recent"
#define BH_DB_RELS         "relationships"
#define BH_DB_REL_FROM     "rel_from"
#define BH_DB_REL_TO       "rel_to"
#define BH_DB_TRAILS       "trails"
#define BH_DB_TRAIL_STEPS  "trail_steps"
#define BH_DB_WORKSPACES   "workspaces"
#define BH_DB_LEARNING     "learning"
#define BH_DB_LEARN_SCENT  "learn_scent"
#define BH_DB_CONTENT      "content_search"
#define BH_DB_META         "meta"

/* ---- Structures ---- */

typedef struct {
    uint64_t scent_id;
    char     fingerprint[33];
    char     type[32];
    char     language[16];
    char     workspace[256];
    char     source_file[BH_MAX_PATH];
    char     relative_path[512];
    uint32_t line;
    uint32_t column;
    uint64_t byte_offset;
    char     content_hash[33];
    double   confidence;
    uint64_t created_at;
    uint64_t updated_at;
    uint32_t seen_count;
    uint32_t ctx_before_len;
    uint32_t ctx_match_len;
    uint32_t ctx_after_len;
} scent_packet;

typedef struct {
    uint64_t file_id;
    char     file_path[BH_MAX_PATH];
    char     relative_path[512];
    char     workspace[256];
    char     language[16];
    uint64_t size;
    uint64_t mtime;
    char     content_hash[33];
    uint64_t scan_time;
    uint32_t compressed_size;
} file_record;

typedef struct {
    uint64_t obs_id;
    uint64_t timestamp;
    char     workspace[256];
    char     file_path[BH_MAX_PATH];
    uint64_t scent_id;
    char     action[16];
    char     observer_version[8];
} observation;

typedef struct {
    uint64_t from_scent;
    uint64_t to_scent;
    char     rel_type[32];
    double   confidence;
    char     evidence[256];
    uint64_t created_at;
} relationship;

typedef struct {
    uint64_t trail_id;
    char     origin[256];
    char     destination[256];
    char     reason[256];
    double   confidence;
    uint64_t created_at;
} trail;

typedef struct {
    uint64_t trail_id;
    uint32_t step_num;
    uint64_t scent_id;
    char     file_path[BH_MAX_PATH];
    char     description[256];
} trail_step;

typedef struct {
    char     name[256];
    char     root_path[BH_MAX_PATH];
    uint32_t file_count;
    uint32_t scent_count;
    char     dominant_topics[512];
    char     fingerprint[33];
    uint64_t last_scan;
    uint64_t created_at;
    uint64_t updated_at;
} workspace_rec;

typedef struct {
    uint64_t learn_id;
    uint64_t scent_id;
    char     event[32];
    double   confidence_delta;
    uint64_t timestamp;
} learning_rec;

typedef struct {
    uint64_t scent_id;
    uint64_t file_id;
    uint32_t line;
    uint32_t offset;
    uint32_t length;
} content_index_entry;

typedef struct {
    uint32_t files;
    uint32_t new_files;
    uint32_t modified_files;
    uint32_t deleted_files;
    uint32_t total_scents;
} scan_result;

typedef struct {
    MDB_env  *env;
    MDB_dbi  dbs[24];
    char     db_path[BH_MAX_PATH];
} bh_db;

/* ---- bh_db.c ---- */

int     bh_db_open(bh_db *db, const char *path);
void    bh_db_close(bh_db *db);
uint64_t bh_db_next_id(bh_db *db, const char *counter_name);

int     bh_db_put_scent(bh_db *db, scent_packet *pkt,
                        const char *ctx_before, const char *ctx_match, const char *ctx_after);
int     bh_db_get_scent(bh_db *db, uint64_t scent_id, scent_packet *pkt,
                        char *ctx_before, size_t before_sz,
                        char *ctx_match, size_t match_sz,
                        char *ctx_after, size_t after_sz);
int     bh_db_find_by_fp(bh_db *db, const char *fingerprint, uint64_t *scent_id);
int     bh_db_update_scent_confidence(bh_db *db, uint64_t scent_id, double conf, uint32_t seen);
int     bh_db_decay_all(bh_db *db, double factor);

int     bh_db_put_file(bh_db *db, file_record *rec, const char *content, size_t content_len);
int     bh_db_get_file(bh_db *db, uint64_t file_id, file_record *rec, char *content, size_t content_sz);
int     bh_db_find_file(bh_db *db, const char *file_path, uint64_t *file_id);
int     bh_db_find_file_by_hash(bh_db *db, const char *hash, uint64_t *file_id);
int     bh_db_delete_file(bh_db *db, uint64_t file_id);
int     bh_db_iter_files(bh_db *db, void *user_data,
                         int (*cb)(file_record *rec, const char *content, size_t content_len, void *user_data));

int     bh_db_put_observation(bh_db *db, observation *obs);
int     bh_db_put_relationship(bh_db *db, relationship *rel);
int     bh_db_put_trail(bh_db *db, trail *t);
int     bh_db_put_trail_step(bh_db *db, trail_step *step);
int     bh_db_put_workspace(bh_db *db, workspace_rec *ws);
int     bh_db_put_learning(bh_db *db, learning_rec *lr);

/* content search */
int     bh_db_content_search(bh_db *db, const char *text, int limit,
                             void *user_data,
                             int (*cb)(uint64_t file_id, const char *file_path, uint32_t line, const char *line_text, void *user_data));

/* cursor-based queries */
typedef int (*scent_callback)(scent_packet *pkt, const char *ctx_before, const char *ctx_match, const char *ctx_after, void *user_data);
int     bh_db_iter_scents(bh_db *db, scent_callback cb, void *user_data);
int     bh_db_iter_file_scents(bh_db *db, const char *file_path, scent_callback cb, void *user_data);
int     bh_db_iter_type_scents(bh_db *db, const char *type, scent_callback cb, void *user_data);
int     bh_db_iter_lang_scents(bh_db *db, const char *lang, scent_callback cb, void *user_data);
int     bh_db_iter_ws_scents(bh_db *db, const char *ws, scent_callback cb, void *user_data);
int     bh_db_iter_recent_obs(bh_db *db, int limit, void *user_data,
                              int (*cb)(observation *obs, void *user_data));

typedef int (*rel_callback)(relationship *rel, void *user_data);
int     bh_db_iter_rels_from(bh_db *db, uint64_t scent_id, rel_callback cb, void *user_data);
int     bh_db_iter_rels_to(bh_db *db, uint64_t scent_id, rel_callback cb, void *user_data);

typedef int (*trail_callback)(trail *t, void *user_data);
int     bh_db_iter_trails(bh_db *db, trail_callback cb, void *user_data);
int     bh_db_get_trail_steps(bh_db *db, uint64_t trail_id, void *user_data,
                              int (*cb)(trail_step *step, void *user_data));

typedef int (*file_callback)(file_record *rec, const char *content, size_t content_len, void *user_data);
int     bh_db_iter_all_files(bh_db *db, file_callback cb, void *user_data);

int     bh_db_count(bh_db *db, const char *dbi_name, uint64_t *count);
int     bh_db_get_workspace(bh_db *db, const char *name, workspace_rec *ws);
int     bh_db_detect_deletions(bh_db *db, const char *workspace, const char *root_path, uint32_t *deleted_count);

/* ---- bh_nose.c ---- */

int     bh_nose_extract(bh_db *db, const char *file_path, const char *rel_path,
                        const char *workspace, const char *content_hash,
                        const char *language);
void    bh_normalize(const char *in, char *out, size_t out_size);
void    bh_compute_fingerprint(const char *normalized, char *out, size_t out_size);
void    bh_compute_file_hash(const char *file_path, char *out, size_t out_size);
const char *bh_detect_language(const char *file_path);
void    bh_nose_build_relationships(bh_db *db, const char *file_path, const char *workspace);
void    bh_nose_build_import_relationships(bh_db *db, const char *workspace);

/* ---- bh_scanner.c ---- */

int     bh_scan_workspace(bh_db *db, const char *root_path, const char *workspace_name, scan_result *result);
int     bh_watch_workspace(bh_db *db, const char *root_path, const char *workspace_name, int interval);

/* ---- bh_query.c ---- */

void    bh_query_text(bh_db *db, const char *text);
void    bh_query_remember(bh_db *db, const char *text);
void    bh_query_similar(bh_db *db, uint64_t scent_id);
void    bh_query_relationships(bh_db *db, uint64_t scent_id);
void    bh_query_trails(bh_db *db);
void    bh_query_trail_detail(bh_db *db, uint64_t trail_id);
void    bh_query_workspace(bh_db *db, const char *name);
void    bh_query_stats(bh_db *db);
void    bh_query_recent(bh_db *db, int limit);
void    bh_query_file_content(bh_db *db, uint64_t file_id);
void    bh_query_content_search(bh_db *db, const char *text, int limit);
void    bh_query_export(bh_db *db, const char *format, const char *output_path);
void    bh_print_status(bh_db *db);

/* ---- bh_sync.c ---- */

int     bh_sync_to_drive(bh_db *db, const char *workspace);
int     bh_restore_from_drive(const char *drive_path);

/* ---- helpers ---- */

void    bh_expand_tilde(const char *in, char *out, size_t out_size);
void    bh_sha256_string(const char *input, size_t len, char *out, size_t out_size);
void    bh_put_le64(uint8_t *buf, uint64_t val);
uint64_t bh_get_le64(const uint8_t *buf);
void    bh_put_le32(uint8_t *buf, uint32_t val);
uint32_t bh_get_le32(const uint8_t *buf);
void    bh_put_le_double(uint8_t *buf, double val);
double  bh_get_le_double(const uint8_t *buf);
void    bh_format_timestamp(uint64_t ts, char *out, size_t out_size);

#endif /* BLOODHOUND_H */
