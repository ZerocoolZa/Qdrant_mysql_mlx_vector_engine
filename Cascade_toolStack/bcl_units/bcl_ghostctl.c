//@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_ghostctl.c" date="2026-07-04" author="Devin" session_id="bcl-ghostctl-impl" context="BCL unit - System-wide cleanup controller. Scans cache/temp/logs/build targets via nftw, deletes via unlink, protection list (max 64)."}
//@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//@FILEID]{id="bcl_ghostctl.c" domain="cascade_tools" authority="Ghostctl"}
//@SUMMARY]{summary="System-wide cleanup control. Commands: scan, cleanup, protect, unprotect, list_protected, read_state, set_config. Uses nftw for scanning, unlink for deletion, static protection array (max 64)."}
//@CLASS]{class="Ghostctl" domain="cascade_tools" authority="single"}
//@METHOD]{method="Init" type="command"}
//@METHOD]{method="Run" type="dispatch"}
//@METHOD]{method="Close" type="command"}
//@METHOD]{method="State" type="query"}
//@METHOD]{method="Scan" type="internal"}
//@METHOD]{method="Cleanup" type="internal"}
//@METHOD]{method="Classify" type="internal"}
//@METHOD]{method="RemoveTree" type="internal"}
//@METHOD]{method="IsProtected" type="internal"}
//@METHOD]{method="ParseScope" type="internal"}

/*
 * bcl_ghostctl.c — System-wide cleanup controller BCL unit
 *
 * Scan targets: cache (~/.cache, /tmp, __pycache__), temp (*.tmp/.bak/.swp),
 * logs (*.log > max_log_size), build (*.o/.pyc/.class, dist/build/target dirs).
 * macOS ftw.h lacks FTW_ACTIONRETVAL, so the skip-list only suppresses
 * recording; a depth cap + target cap keep output bounded.
 */

#include "bcl_toolstack.h"
#include <ftw.h>
#include <sys/stat.h>
#include <unistd.h>
#include <pwd.h>

#define GHOST_MAX_PROTECTED   64
#define GHOST_MAX_SCOPE       128
#define GHOST_MAX_DEPTH       8
#define GHOST_MAX_TARGETS     500
#define GHOST_DEFAULT_LOGSZ   (5L * 1024L * 1024L)

static struct {
    int  initialized;
    int  scans_run;
    int  cleanups_run;
    long bytes_reclaimed;
    int  protected_count;
    char last_scope[GHOST_MAX_SCOPE];
    long max_log_size;
    int  dry_run_default;
    char scopes_enabled[GHOST_MAX_SCOPE];
} STATE;

static char PROTECTED[GHOST_MAX_PROTECTED][TOOL_MAX_PATH];

/* ===== SCAN CONTEXT (nftw has no user-data param, use file-scope) ===== */

static struct {
    int  want_cache;
    int  want_temp;
    int  want_logs;
    int  want_build;
    int  target_count;
    long total_bytes;
    int  do_delete;
    int  dry_run;
    int  files_deleted;
    int  dirs_removed;
    long bytes_freed;
    char force_scope[16];
    int  out_offset;
    char *out;
    size_t out_sz;
} CTX;

/* ===== HELPERS ===== */

static const char * ghost_home(void) {
    const char *h = getenv("HOME");
    if (h && h[0]) return h;
    struct passwd *pw = getpwuid(getuid());
    if (pw && pw->pw_dir) return pw->pw_dir;
    return "/tmp";
}

static int ghost_ends_with(const char *s, const char *suf) {
    size_t ls = strlen(s), lf = strlen(suf);
    if (lf > ls) return 0;
    return strcmp(s + ls - lf, suf) == 0;
}

static int ghost_in_skiplist(const char *base) {
    static const char *SKIP[] = {
        "Library", ".git", ".Trash", "node_modules", ".npm", ".cargo",
        "Caches", ".cache", ".venv", "venv", "site-packages", ".config",
        ".ssh", ".mozilla", ".chrome", ".docker", NULL
    };
    for (int i = 0; SKIP[i]; i++) {
        if (strcmp(base, SKIP[i]) == 0) return 1;
    }
    return 0;
}

static int ghost_is_protected(const char *path) {
    for (int i = 0; i < STATE.protected_count; i++) {
        size_t pl = strlen(PROTECTED[i]);
        if (pl > 0 && strncmp(PROTECTED[i], path, pl) == 0) return 1;
    }
    return 0;
}

static void ghost_parse_scope(const char *s) {
    CTX.want_cache = CTX.want_temp = CTX.want_logs = CTX.want_build = 0;
    if (!s || !s[0] || strcmp(s, "all") == 0) {
        CTX.want_cache = CTX.want_temp = CTX.want_logs = CTX.want_build = 1;
        return;
    }
    char buf[GHOST_MAX_SCOPE];
    strncpy(buf, s, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = '\0';
    char *tok = strtok(buf, ",");
    while (tok) {
        while (*tok == ' ') tok++;
        if      (strcmp(tok, "cache") == 0) CTX.want_cache = 1;
        else if (strcmp(tok, "temp")  == 0) CTX.want_temp  = 1;
        else if (strcmp(tok, "logs")  == 0) CTX.want_logs  = 1;
        else if (strcmp(tok, "build") == 0) CTX.want_build = 1;
        tok = strtok(NULL, ",");
    }
    if (!(CTX.want_cache || CTX.want_temp || CTX.want_logs || CTX.want_build)) {
        CTX.want_cache = CTX.want_temp = CTX.want_logs = CTX.want_build = 1;
    }
}

static void ghost_emit_target(const char *path, const char *scope,
                              long size, const char *type) {
    if (CTX.out_offset >= (int)CTX.out_sz - 256) return;
    if (CTX.target_count > GHOST_MAX_TARGETS) return;
    CTX.out_offset += snprintf(
        CTX.out + CTX.out_offset, CTX.out_sz - CTX.out_offset,
        "[@TARGET]{[@PATH]{%s}[@SCOPE]{%s}[@SIZE]{%ld}[@TYPE]{%s}}",
        path, scope, size, type);
}

static void ghost_patch_total(char *out, int total, const char *key) {
    char want[64];
    char repl[64];
    snprintf(want, sizeof(want), "[@%s]{0}", key);
    snprintf(repl, sizeof(repl), "[@%s]{%d}", key, total);
    char *pos = strstr(out, want);
    if (pos) {
        int old_len = (int)strlen(want);
        int new_len = (int)strlen(repl);
        memmove(pos + new_len, pos + old_len, strlen(pos + old_len) + 1);
        memcpy(pos, repl, new_len);
    }
}

/* ===== REMOVE TREE — nested nftw with FTW_DEPTH for dir targets ===== */

static int ghost_remove_cb(const char *fpath, const struct stat *sb,
                           int typeflag, struct FTW *ftwbuf) {
    (void)ftwbuf;
    if (typeflag == FTW_F) {
        if (unlink(fpath) == 0) {
            CTX.files_deleted++;
            CTX.bytes_freed += sb->st_size;
        }
    } else if (typeflag == FTW_DP) {
        if (rmdir(fpath) == 0) CTX.dirs_removed++;
    }
    return 0;
}

static void ghost_remove_tree(const char *path) {
    nftw(path, ghost_remove_cb, 32, FTW_DEPTH | FTW_PHYS);
}

/* ===== CLASSIFY + CALLBACK ===== */

static int ghost_cb(const char *fpath, const struct stat *sb,
                    int typeflag, struct FTW *ftwbuf) {
    if (ftwbuf->level > GHOST_MAX_DEPTH) return 0;
    if (typeflag != FTW_F && typeflag != FTW_D) return 0;

    const char *base = strrchr(fpath, '/');
    base = base ? base + 1 : fpath;

    if (ghost_in_skiplist(base)) return 0;

    const char *scope = NULL;
    long size = (typeflag == FTW_F) ? (long)sb->st_size : 4096L;

    if (CTX.force_scope[0] && typeflag == FTW_F) {
        if (CTX.want_temp && (ghost_ends_with(base, ".tmp") ||
                              ghost_ends_with(base, ".bak") ||
                              ghost_ends_with(base, ".swp"))) {
            scope = "temp";
        } else {
            scope = CTX.force_scope;
        }
    } else if (typeflag == FTW_F) {
        if (CTX.want_temp && (ghost_ends_with(base, ".tmp") ||
                              ghost_ends_with(base, ".bak") ||
                              ghost_ends_with(base, ".swp"))) {
            scope = "temp";
        } else if (CTX.want_logs && ghost_ends_with(base, ".log") &&
                   sb->st_size > STATE.max_log_size) {
            scope = "logs";
        } else if (CTX.want_build && (ghost_ends_with(base, ".o") ||
                                      ghost_ends_with(base, ".pyc") ||
                                      ghost_ends_with(base, ".class"))) {
            scope = "build";
        }
    } else { /* directory */
        if (CTX.want_cache && strcmp(base, "__pycache__") == 0) {
            scope = "cache";
        } else if (CTX.want_build && (strcmp(base, "dist") == 0 ||
                                      strcmp(base, "build") == 0 ||
                                      strcmp(base, "target") == 0)) {
            scope = "build";
        }
    }

    if (!scope) return 0;
    if (ghost_is_protected(fpath)) return 0;

    CTX.target_count++;
    CTX.total_bytes += size;

    if (CTX.do_delete) {
        if (typeflag == FTW_F) {
            if (unlink(fpath) == 0) {
                CTX.files_deleted++;
                CTX.bytes_freed += sb->st_size;
            }
        } else { /* dir target -> remove whole tree */
            ghost_remove_tree(fpath);
        }
    } else {
        ghost_emit_target(fpath, scope, size, typeflag == FTW_F ? "file" : "dir");
    }
    return 0;
}

/* ===== RUN SCAN / CLEANUP (shared walker) ===== */

/* Caller must memset CTX and set CTX.out / CTX.out_sz / CTX.out_offset
 * (the header) before calling. This only parses scope and walks. */
static void ghost_run_walk(const char *scope_str, int do_delete, int dry_run) {
    ghost_parse_scope(scope_str);
    CTX.do_delete = do_delete;
    CTX.dry_run = dry_run;

    const char *home = ghost_home();
    char path[TOOL_MAX_PATH];

    if (CTX.want_cache) {
        snprintf(path, sizeof(path), "%s/.cache", home);
        strncpy(CTX.force_scope, "cache", sizeof(CTX.force_scope) - 1);
        CTX.force_scope[sizeof(CTX.force_scope) - 1] = '\0';
        nftw(path, ghost_cb, 32, FTW_PHYS);
        nftw("/tmp", ghost_cb, 32, FTW_PHYS);
        memset(CTX.force_scope, 0, sizeof(CTX.force_scope));
    }
    nftw(home, ghost_cb, 32, FTW_PHYS);
}

/* ===== UNIT INTERFACE ===== */

int Ghostctl_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    memset(PROTECTED, 0, sizeof(PROTECTED));
    STATE.max_log_size = GHOST_DEFAULT_LOGSZ;
    STATE.dry_run_default = 0;
    strcpy(STATE.scopes_enabled, "cache,temp,logs,build");
    STATE.initialized = 1;
    return 1;
}

int Ghostctl_Run(const char *cmd, const char *bcl_in,
                 char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) Ghostctl_Init();

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{1}[@SCANS_RUN]{%d}[@CLEANUPS_RUN]{%d}"
            "[@BYTES_RECLAIMED]{%ld}[@PROTECTED_COUNT]{%d}"
            "[@LAST_SCOPE]{%s}[@MAX_LOG_SIZE]{%ld}"
            "[@DRY_RUN_DEFAULT]{%d}[@SCOPES_ENABLED]{%s}",
            STATE.scans_run, STATE.cleanups_run, STATE.bytes_reclaimed,
            STATE.protected_count, STATE.last_scope, STATE.max_log_size,
            STATE.dry_run_default, STATE.scopes_enabled);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== SET_CONFIG ===== */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char mls[32] = {0}, drd[16] = {0}, scn[GHOST_MAX_SCOPE] = {0};
        BclParser_Extract(&parse, "MAX_LOG_SIZE", mls, sizeof(mls));
        BclParser_Extract(&parse, "DRY_RUN_DEFAULT", drd, sizeof(drd));
        BclParser_Extract(&parse, "SCOPES_ENABLED", scn, sizeof(scn));
        BclParser_Free(&parse);
        if (mls[0]) STATE.max_log_size = atol(mls);
        if (drd[0]) STATE.dry_run_default = atoi(drd);
        if (scn[0]) {
            strncpy(STATE.scopes_enabled, scn, sizeof(STATE.scopes_enabled) - 1);
            STATE.scopes_enabled[sizeof(STATE.scopes_enabled) - 1] = '\0';
        }
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }

    /* ===== PROTECT ===== */
    if (strcmp(cmd, "protect") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char p[TOOL_MAX_PATH] = {0};
        BclParser_Extract(&parse, "PATH", p, sizeof(p));
        BclParser_Free(&parse);
        if (!p[0]) return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        for (int i = 0; i < STATE.protected_count; i++) {
            if (strcmp(PROTECTED[i], p) == 0)
                return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{already_protected}");
        }
        if (STATE.protected_count >= GHOST_MAX_PROTECTED)
            return BclResult_Err(bcl_out, out_sz, 30, "protection list full");
        strncpy(PROTECTED[STATE.protected_count], p, TOOL_MAX_PATH - 1);
        PROTECTED[STATE.protected_count][TOOL_MAX_PATH - 1] = '\0';
        STATE.protected_count++;
        char body[128];
        snprintf(body, sizeof(body), "[@STATUS]{protected}[@COUNT]{%d}",
                 STATE.protected_count);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== UNPROTECT ===== */
    if (strcmp(cmd, "unprotect") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char p[TOOL_MAX_PATH] = {0};
        BclParser_Extract(&parse, "PATH", p, sizeof(p));
        BclParser_Free(&parse);
        if (!p[0]) return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        for (int i = 0; i < STATE.protected_count; i++) {
            if (strcmp(PROTECTED[i], p) == 0) {
                for (int j = i; j < STATE.protected_count - 1; j++)
                    memcpy(PROTECTED[j], PROTECTED[j + 1], TOOL_MAX_PATH);
                memset(PROTECTED[STATE.protected_count - 1], 0, TOOL_MAX_PATH);
                STATE.protected_count--;
                return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{unprotected}");
            }
        }
        return BclResult_Err(bcl_out, out_sz, 31, "path not in protection list");
    }

    /* ===== LIST_PROTECTED ===== */
    if (strcmp(cmd, "list_protected") == 0) {
        int off = snprintf(bcl_out, out_sz, "[@OK]{[@COUNT]{%d}", STATE.protected_count);
        for (int i = 0; i < STATE.protected_count && off < (int)out_sz - 128; i++) {
            off += snprintf(bcl_out + off, out_sz - off,
                            "[@PATH]{%s}", PROTECTED[i]);
        }
        snprintf(bcl_out + off, out_sz - off, "}");
        return 1;
    }

    /* ===== SCAN ===== */
    if (strcmp(cmd, "scan") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char scope[GHOST_MAX_SCOPE] = {0};
        BclParser_Extract(&parse, "SCOPE", scope, sizeof(scope));
        BclParser_Free(&parse);

        memset(&CTX, 0, sizeof(CTX));
        CTX.out = bcl_out;
        CTX.out_sz = out_sz;
        CTX.out_offset = snprintf(bcl_out, out_sz,
            "[@OK]{[@SCOPE]{%s}[@TOTAL]{0}[@RECLAIMABLE]{0}",
            scope[0] ? scope : "all");

        ghost_run_walk(scope, 0, 0);

        ghost_patch_total(bcl_out, CTX.target_count, "TOTAL");
        /* patch reclaimable bytes */
        char rb[64];
        snprintf(rb, sizeof(rb), "[@RECLAIMABLE]{%ld}", CTX.total_bytes);
        char *pos = strstr(bcl_out, "[@RECLAIMABLE]{0}");
        if (pos) {
            int old_len = (int)strlen("[@RECLAIMABLE]{0}");
            int new_len = (int)strlen(rb);
            memmove(pos + new_len, pos + old_len, strlen(pos + old_len) + 1);
            memcpy(pos, rb, new_len);
        }
        int off = (int)strlen(bcl_out);
        snprintf(bcl_out + off, out_sz - off, "}");

        STATE.scans_run++;
        strncpy(STATE.last_scope, scope[0] ? scope : "all",
                sizeof(STATE.last_scope) - 1);
        STATE.last_scope[sizeof(STATE.last_scope) - 1] = '\0';
        return 1;
    }

    /* ===== CLEANUP ===== */
    if (strcmp(cmd, "cleanup") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char scope[GHOST_MAX_SCOPE] = {0};
        char dry[16] = {0};
        BclParser_Extract(&parse, "SCOPE", scope, sizeof(scope));
        BclParser_Extract(&parse, "DRY_RUN", dry, sizeof(dry));
        BclParser_Free(&parse);

        int is_dry = dry[0] ? atoi(dry) : STATE.dry_run_default;

        memset(&CTX, 0, sizeof(CTX));
        CTX.out = bcl_out;
        CTX.out_sz = out_sz;
        CTX.out_offset = snprintf(bcl_out, out_sz,
            "[@OK]{[@SCOPE]{%s}[@DRY_RUN]{%d}[@TOTAL]{0}",
            scope[0] ? scope : "all", is_dry);

        ghost_run_walk(scope, is_dry ? 0 : 1, is_dry);

        ghost_patch_total(bcl_out, CTX.target_count, "TOTAL");
        int off = (int)strlen(bcl_out);
        off += snprintf(bcl_out + off, out_sz - off,
            "[@FILES_DELETED]{%d}[@DIRS_REMOVED]{%d}[@BYTES_FREED]{%ld}}",
            CTX.files_deleted, CTX.dirs_removed, CTX.bytes_freed);

        if (!is_dry) {
            STATE.cleanups_run++;
            STATE.bytes_reclaimed += CTX.bytes_freed;
        }
        strncpy(STATE.last_scope, scope[0] ? scope : "all",
                sizeof(STATE.last_scope) - 1);
        STATE.last_scope[sizeof(STATE.last_scope) - 1] = '\0';
        return 1;
    }

    return BclResult_Err(bcl_out, out_sz, 40, "unknown command");
}

int Ghostctl_Close(void) {
    STATE.initialized = 0;
    return 1;
}

const char * Ghostctl_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "Ghostctl: initialized=%d scans=%d cleanups=%d reclaimed=%ld protected=%d",
        STATE.initialized, STATE.scans_run, STATE.cleanups_run,
        STATE.bytes_reclaimed, STATE.protected_count);
    return buf;
}
