/*
 * ┌─────────────────────────────────────────────────────────────────┐
 * │ GHOST HEADER                                                    │
 * │ Author:    wws                                                  │
 * │ Domain:    cache cleaning                                       │
 * │ Language:  C (VBStyle-like adaptation)                          │
 * │ Standard:  POSIX syscalls + SQLite config, no system() for ops  │
 * │ Compile:   cc -O2 -lsqlite3 -o Cleaner Cleaner.c                │
 * └─────────────────────────────────────────────────────────────────┘
 */

/*
 * ┌─────────────────────────────────────────────────────────────────┐
 * │ VBSTYLE HEADER                                                  │
 * │ Run() dispatch entry point                                      │
 * │ Tuple3 (ok, data, error) returns                                │
 * │ state dict (struct, no globals for instance data)               │
 * │ No decorators (N/A in C)                                        │
 * │ No print — Report method returns strings                        │
 * │ No hardcoded paths — all paths in SQLite config DB              │
 * │ PascalCase class and method names                               │
 * │ UPPERCASE constants at class level                              │
 * │ One class, one domain: cache cleaning                           │
 * │ Self-documenting DB: paths table schema is code registry        │
 * └─────────────────────────────────────────────────────────────────┘
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <ftw.h>
#include <sys/stat.h>
#include <errno.h>
#include <limits.h>
#include <sqlite3.h>

/* ════════════════════════════════════════════════════════════════
 * UPPERCASE CONSTANTS (class level)
 * ════════════════════════════════════════════════════════════════ */

/* DB location — config store, NOT a cache (never cleaned) */
static const char* DB_DIR       = "Library/Application Support/Cleaner";
static const char* DB_FILE      = "cleaner.db";

/* Schema — self-documenting code registry */
static const char* SCHEMA_PATHS =
    "CREATE TABLE IF NOT EXISTS paths ("
    "  id       INTEGER PRIMARY KEY AUTOINCREMENT,"
    "  category TEXT    NOT NULL,"           /* windsurf | codeium | custom */
    "  root     TEXT    NOT NULL,"           /* absolute base path */
    "  subpath  TEXT    NOT NULL DEFAULT '',"/* relative path under root */
    "  action   TEXT    NOT NULL DEFAULT 'wipe'," /* wipe | keep */
    "  enabled  INTEGER NOT NULL DEFAULT 1"
    ");";

static const char* SCHEMA_META =
    "CREATE TABLE IF NOT EXISTS meta ("
    "  key   TEXT PRIMARY KEY,"
    "  value TEXT"
    ");";

/* Seed data — only inserted if paths table is empty */
static const char* SEED_SQL =
    "INSERT INTO paths (category, root, subpath, action, enabled) VALUES "
    "('windsurf','$WINDSURF','WebStorage','wipe',1),"
    "('windsurf','$WINDSURF','logs','wipe',1),"
    "('windsurf','$WINDSURF','blob_storage','wipe',1),"
    "('windsurf','$WINDSURF','IndexedDB','wipe',1),"
    "('windsurf','$WINDSURF','CachedData','wipe',1),"
    "('windsurf','$WINDSURF','CachedProfilesData','wipe',1),"
    "('windsurf','$WINDSURF','GPUCache','wipe',1),"
    "('windsurf','$WINDSURF','DawnWebGPUCache','wipe',1),"
    "('windsurf','$WINDSURF','DawnGraphiteCache','wipe',1),"
    "('windsurf','$WINDSURF','Code Cache','wipe',1),"
    "('windsurf','$WINDSURF','Service Worker','wipe',1),"
    "('windsurf','$WINDSURF','Session Storage','wipe',1),"
    "('windsurf','$WINDSURF','Shared Dictionary','wipe',1),"
    "('windsurf','$WINDSURF','DIPS','wipe',1),"
    "('windsurf','$WINDSURF','DIPS-wal','wipe',1),"
    "('windsurf','$WINDSURF','Trust Tokens','wipe',1),"
    "('windsurf','$WINDSURF','shared_proto_db','wipe',1),"
    "('windsurf','$WINDSURF','Local Storage','wipe',1),"
    "('windsurf','$WINDSURF','Cache','wipe',1),"
    "('windsurf','$WINDSURF','User/acp-events','wipe',1),"
    "('windsurf','$WINDSURF','User/History','keep',0),"
    "('windsurf','$WINDSURF','User/globalStorage','keep',0),"
    "('windsurf','$WINDSURF','User/settings.json','keep',0),"
    "('windsurf','$WINDSURF','User/workspaceStorage','keep',0),"
    "('codeium','$CODEIUM','cascade','wipe',1),"
    "('codeium','$CODEIUM','implicit','wipe',1),"
    "('codeium','$CODEIUM','memories','keep',0);";

/* Dispatch keys */
static const char* CMD_ALL      = "all";
static const char* CMD_WINDSURF = "windsurf";
static const char* CMD_CODEIUM  = "codeium";
static const char* CMD_ADD      = "add";
static const char* CMD_REMOVE   = "remove";
static const char* CMD_LIST     = "list";
static const char* CMD_STATE    = "state";
static const char* CMD_REPORT   = "report";

/* Error codes */
static const char* ERR_OK        = "OK";
static const char* ERR_NOTFOUND  = "NOTFOUND";
static const char* ERR_BADCMD    = "BADCMD";
static const char* ERR_NOPATH    = "NOPATH";
static const char* ERR_INTERNAL  = "INTERNAL";
static const char* ERR_DB        = "DBERROR";

/* ════════════════════════════════════════════════════════════════
 * Tuple3 — (ok, data, error)
 * error is a tuple (code, desc, 0)
 * ════════════════════════════════════════════════════════════════ */

typedef struct {
    const char* code;
    char        desc[512];
    int         zero;
} ErrorTuple;

typedef struct {
    int       ok;
    void*     data;
    ErrorTuple error;
} Tuple3;

static Tuple3 Tuple3_OK(void* data) {
    Tuple3 t;
    t.ok = 1;
    t.data = data;
    t.error.code = ERR_OK;
    t.error.desc[0] = '\0';
    t.error.zero = 0;
    return t;
}

static Tuple3 Tuple3_Error(const char* code, const char* desc) {
    Tuple3 t;
    t.ok = 0;
    t.data = NULL;
    t.error.code = code;
    snprintf(t.error.desc, sizeof(t.error.desc), "%s", desc ? desc : "");
    t.error.zero = 0;
    return t;
}

/* ════════════════════════════════════════════════════════════════
 * CLASSES HEADER
 * Cleaner — domain: cache cleaning
 *   One class, one domain. Paths stored in SQLite config DB.
 *   Code is generic: reads (category, root, subpath, action) rows
 *   and applies wipe/keep. Adding a path = DB insert, not code change.
 * ════════════════════════════════════════════════════════════════ */

typedef struct {
    /* config */
    char home[PATH_MAX];
    char db_path[PATH_MAX];
    char windsurf_root[PATH_MAX];
    char codeium_root[PATH_MAX];

    /* db handle */
    sqlite3* db;

    /* results / catalog */
    long files_removed;
    long dirs_removed;
    long paths_wiped;
    long paths_kept;

    /* report buffer */
    char report[8192];
    int  report_len;
} CleanState;

typedef struct {
    CleanState state;
} Cleaner;

/* ════════════════════════════════════════════════════════════════
 * nftw walker — global pointer (C nftw has no user-data param)
 * ════════════════════════════════════════════════════════════════ */

static Cleaner* g_active = NULL;

static int walker(const char* fpath, const struct stat* sb,
                  int typeflag, struct FTW* ftwbuf) {
    (void)sb; (void)ftwbuf;
    if (!g_active) return 1;

    if (typeflag == FTW_F) {
        if (unlink(fpath) == 0)
            g_active->state.files_removed++;
    } else if (typeflag == FTW_DP) {
        if (ftwbuf->level > 0 && rmdir(fpath) == 0)
            g_active->state.dirs_removed++;
    }
    return 0;
}

/* ════════════════════════════════════════════════════════════════
 * METHOD HEADER
 * Cleaner_Init — constructor
 *   def __init__(self, mem=None, db=None, param=None)
 *   Opens/creates SQLite DB, creates schema, seeds defaults if empty
 *   Returns: Tuple3 (1, self, (OK, NULL, 0))
 * ════════════════════════════════════════════════════════════════ */

static Tuple3 Cleaner_Init(Cleaner* self) {
    const char* home = getenv("HOME");
    if (!home)
        return Tuple3_Error(ERR_NOPATH, "HOME env not set");

    memset(&self->state, 0, sizeof(CleanState));
    snprintf(self->state.home, sizeof(self->state.home), "%s", home);
    snprintf(self->state.windsurf_root, sizeof(self->state.windsurf_root),
             "%s/Library/Application Support/Windsurf", home);
    snprintf(self->state.codeium_root, sizeof(self->state.codeium_root),
             "%s/.codeium/windsurf", home);

    /* DB path: ~/Library/Application Support/Cleaner/cleaner.db */
    char dir[PATH_MAX];
    snprintf(dir, sizeof(dir), "%s/%s", home, DB_DIR);
    snprintf(self->state.db_path, sizeof(self->state.db_path),
             "%s/%s", dir, DB_FILE);

    /* create dir if needed */
    char mkdir_cmd[PATH_MAX + 32];
    snprintf(mkdir_cmd, sizeof(mkdir_cmd), "mkdir -p '%s'", dir);
    /* use mkdir syscall instead of system() */
    struct stat st;
    if (stat(dir, &st) != 0) {
        /* create parent dirs step by step */
        char tmp[PATH_MAX];
        snprintf(tmp, sizeof(tmp), "%s/Library", home);
        mkdir(tmp, 0755);
        snprintf(tmp, sizeof(tmp), "%s/Library/Application Support", home);
        mkdir(tmp, 0755);
        mkdir(dir, 0755);
    }

    /* open DB */
    int rc = sqlite3_open(self->state.db_path, &self->state.db);
    if (rc != SQLITE_OK)
        return Tuple3_Error(ERR_DB, sqlite3_errmsg(self->state.db));

    /* create schema */
    char* err = NULL;
    rc = sqlite3_exec(self->state.db, SCHEMA_PATHS, NULL, NULL, &err);
    if (rc != SQLITE_OK) {
        Tuple3 t = Tuple3_Error(ERR_DB, err ? err : "schema paths failed");
        sqlite3_free(err);
        return t;
    }
    rc = sqlite3_exec(self->state.db, SCHEMA_META, NULL, NULL, &err);
    if (rc != SQLITE_OK) {
        Tuple3 t = Tuple3_Error(ERR_DB, err ? err : "schema meta failed");
        sqlite3_free(err);
        return t;
    }

    /* seed if empty */
    int count = 0;
    sqlite3_stmt* stmt;
    rc = sqlite3_prepare_v2(self->state.db, "SELECT COUNT(*) FROM paths",
                            -1, &stmt, NULL);
    if (rc == SQLITE_OK && sqlite3_step(stmt) == SQLITE_ROW)
        count = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);

    if (count == 0) {
        /* build seed SQL with real paths substituted */
        char seed[4096];
        const char* src = SEED_SQL;
        char* dst = seed;
        while (*src && (dst - seed) < (long)sizeof(seed) - 1) {
            if (strncmp(src, "$WINDSURF", 9) == 0) {
                dst += snprintf(dst, sizeof(seed) - (dst - seed),
                                "%s", self->state.windsurf_root);
                src += 9;
            } else if (strncmp(src, "$CODEIUM", 8) == 0) {
                dst += snprintf(dst, sizeof(seed) - (dst - seed),
                                "%s", self->state.codeium_root);
                src += 8;
            } else {
                *dst++ = *src++;
            }
        }
        *dst = '\0';

        rc = sqlite3_exec(self->state.db, seed, NULL, NULL, &err);
        if (rc != SQLITE_OK) {
            Tuple3 t = Tuple3_Error(ERR_DB, err ? err : "seed failed");
            sqlite3_free(err);
            return t;
        }
    }

    return Tuple3_OK(self);
}

/* ════════════════════════════════════════════════════════════════
 * METHOD HEADER
 * Cleaner_WipeDir — internal helper
 *   Wipes all contents of a directory (keeps the dir itself)
 *   Returns: Tuple3 (1, NULL, (OK, NULL, 0)) or error
 * ════════════════════════════════════════════════════════════════ */

static Tuple3 Cleaner_WipeDir(Cleaner* self, const char* path) {
    struct stat st;
    if (stat(path, &st) != 0)
        return Tuple3_Error(ERR_NOTFOUND, path);
    if (!S_ISDIR(st.st_mode))
        return Tuple3_Error(ERR_INTERNAL, "not a directory");

    g_active = self;
    nftw(path, walker, 64, FTW_DEPTH | FTW_PHYS);
    g_active = NULL;

    return Tuple3_OK(NULL);
}

/* ════════════════════════════════════════════════════════════════
 * METHOD HEADER
 * Cleaner_CleanCategory — generic clean by category
 *   Reads all enabled 'wipe' rows for the given category from DB
 *   Constructs full path = root/subpath, wipes each
 *   'keep' rows are logged but not touched
 *   Returns: Tuple3 (1, NULL, (OK, NULL, 0))
 * ════════════════════════════════════════════════════════════════ */

static Tuple3 Cleaner_CleanCategory(Cleaner* self, const char* category) {
    const char* sql =
        "SELECT root, subpath, action, enabled FROM paths "
        "WHERE category = ? ORDER BY id";

    sqlite3_stmt* stmt;
    int rc = sqlite3_prepare_v2(self->state.db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK)
        return Tuple3_Error(ERR_DB, sqlite3_errmsg(self->state.db));

    sqlite3_bind_text(stmt, 1, category, -1, SQLITE_STATIC);

    long wiped = 0, kept = 0;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        const char* root    = (const char*)sqlite3_column_text(stmt, 0);
        const char* subpath = (const char*)sqlite3_column_text(stmt, 1);
        const char* action  = (const char*)sqlite3_column_text(stmt, 2);
        int enabled         = sqlite3_column_int(stmt, 3);

        if (!enabled || strcmp(action, "wipe") != 0) {
            kept++;
            continue;
        }

        char full[PATH_MAX];
        if (subpath[0] != '\0')
            snprintf(full, sizeof(full), "%s/%s", root, subpath);
        else
            snprintf(full, sizeof(full), "%s", root);

        Cleaner_WipeDir(self, full);
        wiped++;
    }
    sqlite3_finalize(stmt);

    self->state.paths_wiped += wiped;
    self->state.paths_kept  += kept;

    self->state.report_len += snprintf(
        self->state.report + self->state.report_len,
        sizeof(self->state.report) - self->state.report_len,
        "%s: %ld paths wiped, %ld paths kept\n",
        category, wiped, kept);

    return Tuple3_OK(NULL);
}

/* ════════════════════════════════════════════════════════════════
 * METHOD HEADER
 * Cleaner_AddPath — add a path config row to DB
 *   add(category, root, subpath, action)
 *   No code change needed — pure DB insert
 *   Returns: Tuple3 (1, NULL, (OK, NULL, 0))
 * ════════════════════════════════════════════════════════════════ */

static Tuple3 Cleaner_AddPath(Cleaner* self, const char* category,
                              const char* root, const char* subpath,
                              const char* action) {
    const char* sql =
        "INSERT INTO paths (category, root, subpath, action, enabled) "
        "VALUES (?, ?, ?, ?, 1)";

    sqlite3_stmt* stmt;
    int rc = sqlite3_prepare_v2(self->state.db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK)
        return Tuple3_Error(ERR_DB, sqlite3_errmsg(self->state.db));

    sqlite3_bind_text(stmt, 1, category, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, root, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 3, subpath ? subpath : "", -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 4, action ? action : "wipe", -1, SQLITE_STATIC);

    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    if (rc != SQLITE_DONE)
        return Tuple3_Error(ERR_DB, sqlite3_errmsg(self->state.db));

    self->state.report_len += snprintf(
        self->state.report + self->state.report_len,
        sizeof(self->state.report) - self->state.report_len,
        "Added: %s/%s/%s action=%s\n",
        category, root, subpath ? subpath : "", action ? action : "wipe");

    return Tuple3_OK(NULL);
}

/* ════════════════════════════════════════════════════════════════
 * METHOD HEADER
 * Cleaner_RemovePath — remove a path config row by id
 *   remove(id)
 *   Returns: Tuple3 (1, NULL, (OK, NULL, 0))
 * ════════════════════════════════════════════════════════════════ */

static Tuple3 Cleaner_RemovePath(Cleaner* self, int id) {
    const char* sql = "DELETE FROM paths WHERE id = ?";

    sqlite3_stmt* stmt;
    int rc = sqlite3_prepare_v2(self->state.db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK)
        return Tuple3_Error(ERR_DB, sqlite3_errmsg(self->state.db));

    sqlite3_bind_int(stmt, 1, id);
    rc = sqlite3_step(stmt);
    int changes = sqlite3_changes(self->state.db);
    sqlite3_finalize(stmt);

    if (rc != SQLITE_DONE)
        return Tuple3_Error(ERR_DB, sqlite3_errmsg(self->state.db));
    if (changes == 0)
        return Tuple3_Error(ERR_NOTFOUND, "no row with that id");

    self->state.report_len += snprintf(
        self->state.report + self->state.report_len,
        sizeof(self->state.report) - self->state.report_len,
        "Removed: id=%d\n", id);

    return Tuple3_OK(NULL);
}

/* ════════════════════════════════════════════════════════════════
 * METHOD HEADER
 * Cleaner_ListPaths — list all config rows as report string
 *   list()
 *   Returns: Tuple3 (1, report_string, (OK, NULL, 0))
 * ════════════════════════════════════════════════════════════════ */

static Tuple3 Cleaner_ListPaths(Cleaner* self) {
    const char* sql =
        "SELECT id, category, root, subpath, action, enabled "
        "FROM paths ORDER BY id";

    sqlite3_stmt* stmt;
    int rc = sqlite3_prepare_v2(self->state.db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK)
        return Tuple3_Error(ERR_DB, sqlite3_errmsg(self->state.db));

    self->state.report_len += snprintf(
        self->state.report + self->state.report_len,
        sizeof(self->state.report) - self->state.report_len,
        "%-4s %-10s %-8s %-40s %-6s %-3s\n",
        "ID", "CATEGORY", "ACTION", "SUBPATH", "EN", "ROOT");
    self->state.report_len += snprintf(
        self->state.report + self->state.report_len,
        sizeof(self->state.report) - self->state.report_len,
        "%s\n",
        "--------------------------------------------------------------------------------");

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        int id         = sqlite3_column_int(stmt, 0);
        const char* cat = (const char*)sqlite3_column_text(stmt, 1);
        const char* root = (const char*)sqlite3_column_text(stmt, 2);
        const char* sub  = (const char*)sqlite3_column_text(stmt, 3);
        const char* act  = (const char*)sqlite3_column_text(stmt, 4);
        int en           = sqlite3_column_int(stmt, 5);

        /* show just the last 20 chars of root for readability */
        const char* root_short = root + (strlen(root) > 20 ? strlen(root) - 20 : 0);

        self->state.report_len += snprintf(
            self->state.report + self->state.report_len,
            sizeof(self->state.report) - self->state.report_len,
            "%-4d %-10s %-8s %-40s %-3d   ...%s\n",
            id, cat ? cat : "", act ? act : "",
            sub ? sub : "", en, root_short);
    }
    sqlite3_finalize(stmt);

    return Tuple3_OK(self->state.report);
}

/* ════════════════════════════════════════════════════════════════
 * METHOD HEADER
 * Cleaner_ReadState — returns config snapshot
 *   read_state returns config snapshot
 *   Returns: Tuple3 (1, &state, (OK, NULL, 0))
 * ════════════════════════════════════════════════════════════════ */

static Tuple3 Cleaner_ReadState(Cleaner* self) {
    self->state.report_len += snprintf(
        self->state.report + self->state.report_len,
        sizeof(self->state.report) - self->state.report_len,
        "State:\n"
        "  home:          %s\n"
        "  db_path:       %s\n"
        "  windsurf_root: %s\n"
        "  codeium_root:  %s\n"
        "  files_removed: %ld\n"
        "  dirs_removed:  %ld\n"
        "  paths_wiped:   %ld\n"
        "  paths_kept:    %ld\n",
        self->state.home,
        self->state.db_path,
        self->state.windsurf_root,
        self->state.codeium_root,
        self->state.files_removed,
        self->state.dirs_removed,
        self->state.paths_wiped,
        self->state.paths_kept);

    return Tuple3_OK(&self->state);
}

/* ════════════════════════════════════════════════════════════════
 * METHOD HEADER
 * Cleaner_Report — returns report string (no print)
 *   report isolation returns strings no print
 *   Returns: Tuple3 (1, report_string, (OK, NULL, 0))
 * ════════════════════════════════════════════════════════════════ */

static Tuple3 Cleaner_Report(Cleaner* self) {
    if (self->state.report_len == 0) {
        self->state.report_len = snprintf(
            self->state.report, sizeof(self->state.report),
            "No operations performed.\n");
    }
    /* append summary if any cleaning happened */
    if (self->state.files_removed > 0 || self->state.dirs_removed > 0) {
        self->state.report_len += snprintf(
            self->state.report + self->state.report_len,
            sizeof(self->state.report) - self->state.report_len,
            "---\nTotal: %ld files, %ld dirs removed\n",
            self->state.files_removed,
            self->state.dirs_removed);
    }
    return Tuple3_OK(self->state.report);
}

/* ════════════════════════════════════════════════════════════════
 * METHOD HEADER
 * Cleaner_Dispatch — internal dispatch
 *   dispatch(command, params) internal
 *   Maps command string to method call
 *   Returns: Tuple3 from the dispatched method
 * ════════════════════════════════════════════════════════════════ */

static Tuple3 Cleaner_Dispatch(Cleaner* self, const char* command,
                               int argc, char** argv) {
    if (strcmp(command, CMD_ALL) == 0) {
        Cleaner_CleanCategory(self, "windsurf");
        return Cleaner_CleanCategory(self, "codeium");
    }
    else if (strcmp(command, CMD_WINDSURF) == 0) {
        return Cleaner_CleanCategory(self, "windsurf");
    }
    else if (strcmp(command, CMD_CODEIUM) == 0) {
        return Cleaner_CleanCategory(self, "codeium");
    }
    else if (strcmp(command, CMD_ADD) == 0) {
        /* add <category> <root> <subpath> <action> */
        if (argc < 6)
            return Tuple3_Error(ERR_BADCMD,
                "usage: add <category> <root> <subpath> <action>");
        return Cleaner_AddPath(self, argv[2], argv[3], argv[4], argv[5]);
    }
    else if (strcmp(command, CMD_REMOVE) == 0) {
        /* remove <id> */
        if (argc < 3)
            return Tuple3_Error(ERR_BADCMD, "usage: remove <id>");
        return Cleaner_RemovePath(self, atoi(argv[2]));
    }
    else if (strcmp(command, CMD_LIST) == 0) {
        return Cleaner_ListPaths(self);
    }
    else if (strcmp(command, CMD_STATE) == 0) {
        return Cleaner_ReadState(self);
    }
    else if (strcmp(command, CMD_REPORT) == 0) {
        return Cleaner_Report(self);
    }
    else {
        return Tuple3_Error(ERR_BADCMD, command);
    }
}

/* ════════════════════════════════════════════════════════════════
 * METHOD HEADER
 * Cleaner_Run — dispatch entry point
 *   Run(command, params) dispatch entry point
 *   Public API: caller passes command + argv, gets Tuple3 back
 *   Returns: Tuple3 from dispatch
 * ════════════════════════════════════════════════════════════════ */

static Tuple3 Cleaner_Run(Cleaner* self, const char* command,
                          int argc, char** argv) {
    if (!self || !command)
        return Tuple3_Error(ERR_INTERNAL, "self or command is NULL");
    return Cleaner_Dispatch(self, command, argc, argv);
}

/* ════════════════════════════════════════════════════════════════
 * MAIN — CLI wrapper around the Cleaner class
 *   Usage: Cleaner <command> [args...]
 *   Commands:
 *     all                              clean all wipe-enabled paths
 *     windsurf                         clean windsurf category
 *     codeium                          clean codeium category
 *     add <cat> <root> <sub> <action>  add a path to config DB
 *     remove <id>                      remove a path from config DB
 *     list                             list all config rows
 *     state                            show state snapshot
 *     report                           show last report
 * ════════════════════════════════════════════════════════════════ */

int main(int argc, char** argv) {
    if (argc < 2) {
        fprintf(stderr,
            "Usage: %s <all|windsurf|codeium|add|remove|list|state|report>\n",
            argv[0]);
        return 1;
    }

    /* construct instance */
    Cleaner cleaner;
    Tuple3 init_result = Cleaner_Init(&cleaner);
    if (!init_result.ok) {
        fprintf(stderr, "ERROR: %s — %s\n",
                init_result.error.code,
                init_result.error.desc[0] ? init_result.error.desc : "");
        return 1;
    }

    /* run command */
    const char* command = argv[1];
    Tuple3 result = Cleaner_Run(&cleaner, command, argc, argv);

    if (!result.ok) {
        fprintf(stderr, "ERROR: %s — %s\n",
                result.error.code,
                result.error.desc[0] ? result.error.desc : "");
        if (cleaner.state.db) sqlite3_close(cleaner.state.db);
        return 1;
    }

    /* get report and print it (report method returns string, main prints) */
    Tuple3 report_result = Cleaner_Report(&cleaner);
    if (report_result.ok && report_result.data)
        printf("%s", (const char*)report_result.data);

    if (cleaner.state.db) sqlite3_close(cleaner.state.db);
    return 0;
}
