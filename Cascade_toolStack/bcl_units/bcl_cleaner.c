//@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_cleaner.c" date="2026-06-29" author="cascade" session_id="bcl-toolstack-units" context="BCL unit for cache and junk file scanning/cleaning — walks directories with nftw, categorizes junk, deletes on clean. Commands: scan, clean, dry_run, read_state, set_config."}
//@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//@FILEID]{id="bcl_cleaner.c" domain="cascade_tools" authority="Cleaner"}
//@SUMMARY]{summary="Cache and junk cleaner. Scans directories for .pyc, __pycache__, .DS_Store, *.tmp, large *.log, node_modules, .git objects. Deletes on clean. Commands: scan, clean, dry_run, read_state, set_config."}
//@CLASS]{class="Cleaner" domain="cascade_tools" authority="single"}
//@METHOD]{method="Init" type="command"}
//@METHOD]{method="Run" type="dispatch"}
//@METHOD]{method="Close" type="command"}
//@METHOD]{method="State" type="query"}
//@METHOD]{method="ScanDir" type="command"}
//@METHOD]{method="CleanDir" type="command"}
//@METHOD]{method="DryRun" type="query"}
//@METHOD]{method="Classify" type="query"}
//@REVIEW]{[@date<2026-06-29>][@reviewer<cascade>][@status<draft>][@notes<Real implementation using nftw. Categories: pyc, pycache, ds_store, tmp, log, node_modules, git_objects. Config: max_log_size, categories filter.>][@todos<test compile, integration test>]}

#include "bcl_toolstack.h"
#include <ftw.h>
#include <sys/stat.h>
#include <unistd.h>
#include <dirent.h>
#include <errno.h>

/* ===== DIM BLOCK ===== */

#define CLEANER_MAX_PATH    4096
#define CLEANER_MAX_CAT     256
#define CLEANER_MAX_BODY    8192
#define CLEANER_NFTW_FDS    64
#define CLEANER_DEFAULT_MAX_LOG_SIZE  1048576  /* 1 MB */

/* Category bit flags */
#define CAT_PYC         (1 << 0)
#define CAT_PYCACHE     (1 << 1)
#define CAT_DS_STORE    (1 << 2)
#define CAT_TMP         (1 << 3)
#define CAT_LOG         (1 << 4)
#define CAT_NODE_MODULES (1 << 5)
#define CAT_GIT_OBJECTS (1 << 6)
#define CAT_ALL         0x7F

/* State */
static struct {
    int   initialized;
    int   total_scans;
    int   total_cleaned;
    long long bytes_freed;
    char  last_path[CLEANER_MAX_PATH];
    char  last_category[CLEANER_MAX_CAT];
    /* config */
    long long max_log_size;
    int   categories;  /* bitmask of enabled categories */
} STATE;

/* ===== NFTW SCAN CONTEXT (global — nftw has no user-data pointer) ===== */

typedef struct {
    int   cat_counts[8];     /* per-category file/dir count */
    long long cat_sizes[8];  /* per-category total bytes */
    int   categories;        /* filter bitmask */
    long long max_log_size;
    int   do_delete;         /* 1 = actually unlink/rmdir */
    int   deleted_count;
    long long freed_bytes;
    int   errors;
} ScanCtx;

static ScanCtx G_CTX;

/* ===== CATEGORY CLASSIFICATION ===== */

static int category_from_name(const char *fpath, const struct stat *sb,
                              long long max_log_size) {
    const char *base = strrchr(fpath, '/');
    base = base ? base + 1 : fpath;

    /* Directory-based categories */
    if (S_ISDIR(sb->st_mode)) {
        if (strcmp(base, "__pycache__") == 0) return CAT_PYCACHE;
        if (strcmp(base, "node_modules") == 0) return CAT_NODE_MODULES;
        /* .git/objects — check path contains /.git/objects */
        if (strcmp(base, "objects") == 0 && strstr(fpath, "/.git/objects") != NULL)
            return CAT_GIT_OBJECTS;
        return 0;
    }

    /* File-based categories */
    if (S_ISREG(sb->st_mode)) {
        size_t blen = strlen(base);
        if (strcmp(base, ".DS_Store") == 0) return CAT_DS_STORE;
        if (blen > 4 && strcmp(base + blen - 4, ".pyc") == 0) return CAT_PYC;
        if (blen > 4 && strcmp(base + blen - 4, ".tmp") == 0) return CAT_TMP;
        if (blen > 4 && strcmp(base + blen - 4, ".log") == 0) {
            if ((long long)sb->st_size > max_log_size) return CAT_LOG;
            return 0;
        }
        return 0;
    }
    return 0;
}

static int category_index(int cat) {
    switch (cat) {
        case CAT_PYC:          return 0;
        case CAT_PYCACHE:      return 1;
        case CAT_DS_STORE:     return 2;
        case CAT_TMP:          return 3;
        case CAT_LOG:          return 4;
        case CAT_NODE_MODULES: return 5;
        case CAT_GIT_OBJECTS:  return 6;
        default:               return -1;
    }
}

static const char *category_name(int cat) {
    switch (cat) {
        case CAT_PYC:          return "pyc";
        case CAT_PYCACHE:      return "pycache";
        case CAT_DS_STORE:     return "ds_store";
        case CAT_TMP:          return "tmp";
        case CAT_LOG:          return "log";
        case CAT_NODE_MODULES: return "node_modules";
        case CAT_GIT_OBJECTS:  return "git_objects";
        default:               return "unknown";
    }
}

static int category_from_string(const char *s) {
    if (!s || !s[0]) return CAT_ALL;
    if (strcmp(s, "pyc") == 0)          return CAT_PYC;
    if (strcmp(s, "pycache") == 0)      return CAT_PYCACHE;
    if (strcmp(s, "ds_store") == 0)     return CAT_DS_STORE;
    if (strcmp(s, "tmp") == 0)          return CAT_TMP;
    if (strcmp(s, "log") == 0)          return CAT_LOG;
    if (strcmp(s, "node_modules") == 0) return CAT_NODE_MODULES;
    if (strcmp(s, "git_objects") == 0)  return CAT_GIT_OBJECTS;
    if (strcmp(s, "all") == 0)          return CAT_ALL;
    return 0;
}

/* ===== NFTW CALLBACK ===== */

static int nftw_callback(const char *fpath, const struct stat *sb,
                         int typeflag, struct FTW *ftwbuf) {
    (void)ftwbuf;

    const struct stat *stptr = sb;
    struct stat stbuf;
    if (typeflag == FTW_SL) {
        /* symlinks — skip, don't follow */
        return 0;
    }
    if (!stptr) {
        if (stat(fpath, &stbuf) == 0) stptr = &stbuf;
        else return 0;
    }

    int cat = category_from_name(fpath, stptr, G_CTX.max_log_size);
    if (cat == 0) return 0;
    if (!(cat & G_CTX.categories)) return 0;

    int idx = category_index(cat);
    if (idx < 0) return 0;

    long long sz = (long long)stptr->st_size;

    if (G_CTX.do_delete) {
        if (S_ISDIR(stptr->st_mode)) {
            /* For directory categories, delete the whole tree.
             * nftw walks depth-first with FTW_DEPTH, so children
             * are already deleted by the time we hit the dir.
             * Just rmdir it. */
            if (rmdir(fpath) == 0) {
                G_CTX.deleted_count++;
                G_CTX.cat_counts[idx]++;
            } else {
                G_CTX.errors++;
            }
        } else {
            if (unlink(fpath) == 0) {
                G_CTX.deleted_count++;
                G_CTX.freed_bytes += sz;
                G_CTX.cat_counts[idx]++;
                G_CTX.cat_sizes[idx] += sz;
            } else {
                G_CTX.errors++;
            }
        }
    } else {
        /* scan / dry_run — just count */
        G_CTX.cat_counts[idx]++;
        G_CTX.cat_sizes[idx] += sz;
    }

    return 0;
}

/* ===== SCAN / CLEAN / DRY_RUN CORE ===== */

static int walk_path(const char *path, int do_delete, int categories,
                     long long max_log_size, ScanCtx *out) {
    struct stat path_st;
    if (stat(path, &path_st) != 0) {
        return -1;
    }
    if (!S_ISDIR(path_st.st_mode)) {
        return -2;
    }

    memset(&G_CTX, 0, sizeof(G_CTX));
    G_CTX.categories = categories;
    G_CTX.max_log_size = max_log_size;
    G_CTX.do_delete = do_delete;

    int flags = FTW_PHYS | FTW_DEPTH;
    int ret = nftw(path, nftw_callback, CLEANER_NFTW_FDS, flags);
    if (ret != 0 && ret != 1) {
        /* ret == 1 means callback returned non-zero (we don't), so treat as err */
    }

    memcpy(out, &G_CTX, sizeof(G_CTX));
    return 0;
}

static int build_scan_body(char *body, size_t body_sz, ScanCtx *ctx, const char *path) {
    int total_count = 0;
    long long total_size = 0;
    for (int i = 0; i < 7; i++) {
        total_count += ctx->cat_counts[i];
        total_size += ctx->cat_sizes[i];
    }

    int off = 0;
    off += snprintf(body + off, body_sz - off,
        "[@PATH]{%s}[@TOTAL_COUNT]{%d}[@TOTAL_SIZE]{%lld}",
        path, total_count, total_size);

    static const int cats[7] = {
        CAT_PYC, CAT_PYCACHE, CAT_DS_STORE, CAT_TMP,
        CAT_LOG, CAT_NODE_MODULES, CAT_GIT_OBJECTS
    };
    for (int i = 0; i < 7; i++) {
        int idx = category_index(cats[i]);
        off += snprintf(body + off, body_sz - off,
            "[@%s]{[@COUNT]{%d}[@SIZE]{%lld}}",
            category_name(cats[i]),
            ctx->cat_counts[idx],
            ctx->cat_sizes[idx]);
    }
    return off;
}

/* ===== UNIT INTERFACE ===== */

int Cleaner_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    STATE.max_log_size = CLEANER_DEFAULT_MAX_LOG_SIZE;
    STATE.categories = CAT_ALL;
    return 1;
}

int Cleaner_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) Cleaner_Init();

    /* ---- scan ---- */
    if (strcmp(cmd, "scan") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[CLEANER_MAX_PATH] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Free(&parse);
        if (!path[0]) return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");

        ScanCtx ctx;
        int rc = walk_path(path, 0, STATE.categories, STATE.max_log_size, &ctx);
        if (rc == -1) return BclResult_Err(bcl_out, out_sz, 30, "path not found");
        if (rc == -2) return BclResult_Err(bcl_out, out_sz, 31, "path is not a directory");

        STATE.total_scans++;
        strncpy(STATE.last_path, path, sizeof(STATE.last_path) - 1);
        snprintf(STATE.last_category, sizeof(STATE.last_category), "scan");

        char body[CLEANER_MAX_BODY];
        build_scan_body(body, sizeof(body), &ctx, path);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ---- dry_run ---- */
    if (strcmp(cmd, "dry_run") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[CLEANER_MAX_PATH] = {0};
        char cat_str[CLEANER_MAX_CAT] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Extract(&parse, "CATEGORY", cat_str, sizeof(cat_str));
        BclParser_Free(&parse);
        if (!path[0]) return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");

        int cats = cat_str[0] ? (category_from_string(cat_str) & STATE.categories)
                              : STATE.categories;
        if (cats == 0 && cat_str[0])
            return BclResult_Err(bcl_out, out_sz, 32, "unknown category");

        ScanCtx ctx;
        int rc = walk_path(path, 0, cats, STATE.max_log_size, &ctx);
        if (rc == -1) return BclResult_Err(bcl_out, out_sz, 30, "path not found");
        if (rc == -2) return BclResult_Err(bcl_out, out_sz, 31, "path is not a directory");

        STATE.total_scans++;
        strncpy(STATE.last_path, path, sizeof(STATE.last_path) - 1);
        snprintf(STATE.last_category, sizeof(STATE.last_category), "dry_run");

        char body[CLEANER_MAX_BODY];
        int off = build_scan_body(body, sizeof(body), &ctx, path);
        off += snprintf(body + off, sizeof(body) - off,
            "[@MODE]{dry_run}[@WOULD_DELETE]{%d}[@WOULD_FREE]{%lld}",
            ctx.cat_counts[0] + ctx.cat_counts[1] + ctx.cat_counts[2] +
            ctx.cat_counts[3] + ctx.cat_counts[4] + ctx.cat_counts[5] +
            ctx.cat_counts[6],
            ctx.cat_sizes[0] + ctx.cat_sizes[1] + ctx.cat_sizes[2] +
            ctx.cat_sizes[3] + ctx.cat_sizes[4] + ctx.cat_sizes[5] +
            ctx.cat_sizes[6]);
        (void)off;
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ---- clean ---- */
    if (strcmp(cmd, "clean") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[CLEANER_MAX_PATH] = {0};
        char cat_str[CLEANER_MAX_CAT] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Extract(&parse, "CATEGORY", cat_str, sizeof(cat_str));
        BclParser_Free(&parse);
        if (!path[0]) return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");

        int cats = cat_str[0] ? (category_from_string(cat_str) & STATE.categories)
                              : STATE.categories;
        if (cats == 0 && cat_str[0])
            return BclResult_Err(bcl_out, out_sz, 32, "unknown category");

        ScanCtx ctx;
        int rc = walk_path(path, 1, cats, STATE.max_log_size, &ctx);
        if (rc == -1) return BclResult_Err(bcl_out, out_sz, 30, "path not found");
        if (rc == -2) return BclResult_Err(bcl_out, out_sz, 31, "path is not a directory");

        STATE.total_cleaned += ctx.deleted_count;
        STATE.bytes_freed += ctx.freed_bytes;
        strncpy(STATE.last_path, path, sizeof(STATE.last_path) - 1);
        snprintf(STATE.last_category, sizeof(STATE.last_category),
            "%s", cat_str[0] ? cat_str : "all");

        char body[CLEANER_MAX_BODY];
        int off = build_scan_body(body, sizeof(body), &ctx, path);
        off += snprintf(body + off, sizeof(body) - off,
            "[@DELETED]{%d}[@FREED]{%lld}[@ERRORS]{%d}",
            ctx.deleted_count, ctx.freed_bytes, ctx.errors);
        (void)off;
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ---- read_state ---- */
    if (strcmp(cmd, "read_state") == 0) {
        char body[1024];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@TOTAL_SCANS]{%d}[@TOTAL_CLEANED]{%d}"
            "[@BYTES_FREED]{%lld}[@LAST_PATH]{%s}[@LAST_CATEGORY]{%s}"
            "[@MAX_LOG_SIZE]{%lld}[@CATEGORIES]{%d}",
            STATE.initialized, STATE.total_scans, STATE.total_cleaned,
            STATE.bytes_freed,
            STATE.last_path[0] ? STATE.last_path : "none",
            STATE.last_category[0] ? STATE.last_category : "none",
            STATE.max_log_size, STATE.categories);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ---- set_config ---- */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char max_log[64] = {0};
        char cats_str[CLEANER_MAX_CAT] = {0};
        BclParser_Extract(&parse, "MAX_LOG_SIZE", max_log, sizeof(max_log));
        BclParser_Extract(&parse, "CATEGORIES", cats_str, sizeof(cats_str));
        BclParser_Free(&parse);

        if (max_log[0]) {
            long long v = strtoll(max_log, NULL, 10);
            if (v > 0) STATE.max_log_size = v;
        }
        if (cats_str[0]) {
            /* comma-separated list of category names */
            int mask = 0;
            char buf[CLEANER_MAX_CAT];
            strncpy(buf, cats_str, sizeof(buf) - 1);
            buf[sizeof(buf) - 1] = '\0';
            char *tok = strtok(buf, ",");
            while (tok) {
                /* trim leading spaces */
                while (*tok == ' ') tok++;
                mask |= category_from_string(tok);
                tok = strtok(NULL, ",");
            }
            if (mask) STATE.categories = mask;
        }

        char body[512];
        snprintf(body, sizeof(body),
            "[@STATUS]{config_set}[@MAX_LOG_SIZE]{%lld}[@CATEGORIES]{%d}",
            STATE.max_log_size, STATE.categories);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    return BclResult_Err(bcl_out, out_sz, 404, "unknown command");
}

int Cleaner_Close(void) {
    STATE.initialized = 0;
    STATE.total_scans = 0;
    STATE.total_cleaned = 0;
    STATE.bytes_freed = 0;
    STATE.last_path[0] = '\0';
    STATE.last_category[0] = '\0';
    return 1;
}

const char * Cleaner_State(void) {
    static char buf[512];
    snprintf(buf, sizeof(buf),
        "Cleaner: initialized=%d scans=%d cleaned=%d freed=%lld",
        STATE.initialized, STATE.total_scans, STATE.total_cleaned,
        STATE.bytes_freed);
    return buf;
}
