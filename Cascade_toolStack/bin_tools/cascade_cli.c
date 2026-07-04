/*
 * [@GHOST]{[@file<cascade_cli.c>][@domain<CascadeToolStack>][@role<execution_kernel>][@auth<cascade>][@date<2026-06-28>][@ver<5.0>]}
 * [@VBSTYLE]{[@auth<cascade>][@role<tool>][@return<exit_code>][@no<hardcoded|tabs|decorators|enums>][@model<one_tool_one_purpose_complete>]}
 * [@SUMMARY]{Cascade Execution Kernel (CEK) v5 — Anti-stuck command runner with persistent pattern DB. C native.}
 * [@CLASS]{CascadeCli}
 * [@METHOD]{Run,DbLoad,DbSave,DbAdd,DbRemove,DbList,ValidateCommand,RunExec,RunWithRetry,ParseArgs,PrintResult,PrintJson,DetectErrors,ExtractTraceback,PrintHelp,PrintDryRun}
 *
 * Cascade Execution Kernel (CEK) v5 — C Implementation
 *
 * Merges v4 execution engine (fork/exec/select, non-blocking I/O,
 * timeout, stuck detection, process group kill) with v5 persistent
 * pattern database (blocked/allowed rules, CLI-managed, file-backed).
 *
 * State machine: INIT -> RUNNING -> STREAMING -> DONE/FAILED/STUCK/TIMEOUT/KILLED/BLOCKED/ERROR
 *
 * Compile:
 *   cc -O2 -Wall -o cascade_cli cascade_cli.c
 *
 * Usage:
 *   ./cascade_cli run "command here" [options]
 *   ./cascade_cli run "command here" --timeout 30
 *   ./cascade_cli run "command here" --shell          # pipes/redirections
 *   ./cascade_cli run "command here" --json           # JSON output
 *   ./cascade_cli run "command here" --no-stuck       # long queries
 *   ./cascade_cli run "command here" --cwd /path
 *   ./cascade_cli run "command here" --retry 2
 *   ./cascade_cli run "command here" --dry-run
 *   ./cascade_cli add-block "sudo"                    # block pattern
 *   ./cascade_cli add-allow "rm -rf /tmp"             # allow override
 *   ./cascade_cli rm-block "sudo"                     # remove block
 *   ./cascade_cli rm-allow "rm -rf /tmp"              # remove allow
 *   ./cascade_cli list                                # show all patterns
 *   ./cascade_cli --version
 *   ./cascade_cli --help
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <time.h>
#include <ctype.h>
#include <math.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/select.h>
#include <sys/time.h>
#include <getopt.h>
#include <mach-o/dyld.h>
#include <sys/stat.h>

/* ════════════════════════════════════════════
 * VBSTYLE CONSTANTS (UPPERCASE, no enums)
 * ════════════════════════════════════════════ */

#define VERSION          "5.0"
#define DEFAULT_TIMEOUT  60
#define DEFAULT_STUCK    10
#define DEFAULT_MAX_OUT  1048576
#define MAX_CMD          65536
#define MAX_BUF          8192
#define MAX_ENV_VARS     32
#define MAX_ENV_LEN      1024
#define MAX_PATTERNS     4096
#define MAX_PATTERN_LEN  256
#define DB_FILENAME      ".cascade_pattern_db"

/* Pattern types — no enum, use #define */
#define PAT_BLOCKED      0
#define PAT_ALLOWED      1

/* Exit codes */
#define EXIT_DONE        0
#define EXIT_FAILED      1
#define EXIT_KILLED      123
#define EXIT_TIMEOUT     124
#define EXIT_STUCK       125
#define EXIT_ERROR       126
#define EXIT_BLOCKED     127

/* State machine states */
#define ST_INIT          0
#define ST_RUNNING       1
#define ST_STREAMING     2
#define ST_STUCK         3
#define ST_TIMEOUT       4
#define ST_FAILED        5
#define ST_DONE          6
#define ST_BLOCKED       7
#define ST_ERROR         8
#define ST_KILLED        9

/* Run() dispatch keys */
#define CMD_RUN          "run"
#define CMD_ADD_BLOCK    "add-block"
#define CMD_ADD_ALLOW    "add-allow"
#define CMD_RM_BLOCK     "rm-block"
#define CMD_RM_ALLOW     "rm-allow"
#define CMD_LIST         "list"
#define CMD_REPORT       "report"
#define CMD_CLEAR_BLOCK  "clear-block"
#define CMD_CLEAR_ALLOW  "clear-allow"
#define CMD_ADD_FIX      "add-fix"
#define CMD_LIST_FIX     "list-fix"
#define MAX_LOG_SIZE     1048576
#define LOG_FILENAME     ".cascade_exec_log"
#define AI_FIX_WEIGHTS   ".cascade_fix_weights.bin"
#define MAX_FIX_MSG      4096

/* Neural model dimensions — must match ErrorFixTrainer.py */
#define FIX_INPUT_DIM    40
#define FIX_HIDDEN_DIM   64
#define FIX_OUTPUT_DIM   16

/* Fix action names — index matches output neuron */
static const char *FIX_ACTIONS[FIX_OUTPUT_DIM] = {
    "check_import", "check_import_name", "check_path", "check_attribute",
    "use_get_or_check", "check_length", "fix_indentation", "check_name",
    "validate_input", "check_type", "fix_syntax", "check_permissions",
    "check_connection", "add_base_case", "specify_encoding", "custom",
};

/* Fix descriptions — index matches output neuron */
static const char *FIX_DESCRIPTIONS[FIX_OUTPUT_DIM] = {
    "Module not installed or wrong name. Try: pip install <module> or check import spelling.",
    "Name does not exist in the module. Check the module's exports or API docs.",
    "File or directory does not exist. Check path spelling, use absolute paths, or create the file first.",
    "Object does not have that attribute. Check the class API or use getattr() with a default.",
    "Key not in dictionary. Use dict.get(key) with a default or check key existence first.",
    "List index too large. Check len() before indexing or use try/except.",
    "Missing indentation after a colon. Add 4 spaces after if/for/while/def/class lines.",
    "Variable or function name not defined. Check spelling, imports, or define before use.",
    "Cannot convert value to the requested type. Validate input before conversion.",
    "Wrong type for operation. Check types with isinstance() or convert before use.",
    "Python syntax error. Check for missing colons, parens, quotes, or wrong operators.",
    "No permission for the operation. Check file permissions or use sudo (with caution).",
    "Cannot connect to service. Check if the service is running and the port is correct.",
    "Infinite recursion. Add a base case or increase recursion limit with care.",
    "Encoding mismatch. Specify encoding explicitly when opening files.",
    "Unknown error type. Check the error message for clues.",
};

/* Error type names for display — index matches input neuron 0-15 */
static const char *ERROR_TYPE_NAMES[FIX_INPUT_DIM] = {
    "ModuleNotFoundError", "ImportError", "FileNotFoundError", "AttributeError",
    "KeyError", "IndexError", "IndentationError", "NameError",
    "ValueError", "TypeError", "SyntaxError", "RuntimeError",
    "ConnectionError", "PermissionError", "RecursionError", "UnicodeDecodeError",
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
};

/* Category keywords for features 16-29 */
static const char *CATEGORY_KEYWORDS[14][4] = {
    {"import", "module", "modulenotfound", NULL},
    {"syntax", "indent", "eol", "closed"},
    {"runtime", "recursion", "maximum", NULL},
    {"type", "operand", "concatenate", "iterable"},
    {"filenotfounderror", "no such file", "errno 2", NULL},
    {"attribute", "object", NULL, NULL},
    {"keyerror", "key", NULL, NULL},
    {"index", "range", NULL, NULL},
    {"name", "defined", NULL, NULL},
    {"value", "literal", "convert", NULL},
    {"permission", "errno 13", NULL, NULL},
    {"connection", "refused", "errno 61", NULL},
    {"codec", "decode", "unicode", "byte"},
    {"division", "zero", "divide", NULL},
};

/* ════════════════════════════════════════════
 * VBSTYLE DATA TYPES (PascalCase structs)
 * ════════════════════════════════════════════ */

typedef struct {
    char pattern[MAX_PATTERN_LEN];
    int  type;
    int  severity;
} PatternEntry;

typedef struct {
    PatternEntry entries[MAX_PATTERNS];
    int count;
} PatternList;

typedef struct {
    PatternList blocked;
    PatternList allowed;
    char        db_path[MAX_BUF];
} PatternDb;

typedef struct {
    int    timeout;
    int    stuck_threshold;
    int    no_stuck;
    int    allow_dangerous;
    int    force;
    int    shell;
    int    json;
    int    quiet;
    int    dry_run;
    int    retry;
    int    max_output;
    char   cwd[MAX_BUF];
    char   stdin_data[MAX_BUF];
    int    has_stdin;
    int    ai_fix;
    char   env_vars[MAX_ENV_VARS][MAX_ENV_LEN];
    int    env_count;
    char   command[MAX_CMD];
} CliArgs;

typedef struct {
    int    state;
    int    exit_code;
    double duration;
    char   stdout_buf[1048576 + 64];
    char   stderr_buf[1048576 + 64];
    int    stdout_len;
    int    stderr_len;
    int    stdout_truncated;
    int    stderr_truncated;
    int    attempt;
    int    total_attempts;
    pid_t  pid;
    struct timespec start_time;
} ExecResult;

typedef struct {
    PatternDb  db;
    CliArgs    args;
    ExecResult result;
    char       db_path[MAX_BUF];
} CascadeCli;

/* ════════════════════════════════════════════
 * STATE NAMES
 * ════════════════════════════════════════════ */

static const char *STATE_NAMES[] = {
    "INIT", "RUNNING", "STREAMING", "STUCK", "TIMEOUT",
    "FAILED", "DONE", "BLOCKED", "ERROR", "KILLED"
};

static const char *STATE_ICONS[] = {
    "?", "?", "?", "FROZEN", "TIMEOUT",
    "FAIL", "OK", "BLOCKED", "ERROR", "KILLED"
};

/* ════════════════════════════════════════════
 * ERROR PATTERN TABLE
 * ════════════════════════════════════════════ */

typedef struct {
    const char *name;
    const char *type;
    const char *keyword;
    int priority;
} ErrorDef;

static const ErrorDef ERROR_TABLE[] = {
    {"ModuleNotFoundError",   "import",    "modulenotfounderror",      3},
    {"ImportError",           "import",    "cannot import name",        3},
    {"FileNotFoundError",     "file",      "no such file or directory", 3},
    {"AttributeError",        "attribute", "has no attribute",          3},
    {"KeyError",              "key",       "keyerror",                  3},
    {"IndexError",            "index",     "list index out of range",   3},
    {"IndentationError",      "syntax",    "expected an indented block",3},
    {"UnicodeDecodeError",    "encoding",  "codec can't decode",        3},
    {"NameError",             "name",      "is not defined",            3},
    {"ValueError",            "value",     "invalid literal for",       3},
    {"RecursionError",        "runtime",   "maximum recursion depth",   3},
    {"TypeError",             "type",      "unsupported operand type",  2},
    {"SyntaxError",           "syntax",    "invalid syntax",            2},
    {"RuntimeError",          "runtime",   "runtimeerror",              2},
    {"ConnectionError",       "connection","connection refused",        2},
    {"PermissionError",       "permission","permission denied",         2},
    {NULL, NULL, NULL, 0}
};

/* ════════════════════════════════════════════
 * TIMING HELPERS
 * ════════════════════════════════════════════ */

static double elapsed_sec(struct timespec *start) {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (now.tv_sec - start->tv_sec) + (now.tv_nsec - start->tv_nsec) / 1e9;
}

static void sleep_ms(int ms) {
    struct timespec ts;
    ts.tv_sec = ms / 1000;
    ts.tv_nsec = (ms % 1000) * 1000000L;
    nanosleep(&ts, NULL);
}

/* ════════════════════════════════════════════
 * STRING HELPERS
 * ════════════════════════════════════════════ */

static void str_to_lower(char *s, int maxlen) {
    int i;
    for (i = 0; s[i] && i < maxlen; i++)
        s[i] = tolower((unsigned char)s[i]);
}

static void safe_copy(char *dst, const char *src, int maxlen) {
    strncpy(dst, src, maxlen - 1);
    dst[maxlen - 1] = '\0';
}

/* ════════════════════════════════════════════
 * PATTERN DATABASE — DbLoad, DbSave, DbAdd, DbRemove, DbList
 * File format: B|pattern|severity  or  A|pattern|severity
 * File lives next to the binary: DB_FILENAME
 * ════════════════════════════════════════════ */

static void DbInit(PatternDb *db, const char *path) {
    memset(db, 0, sizeof(PatternDb));
    safe_copy(db->db_path, path, MAX_BUF);
}

static void DbLoad(PatternDb *db) {
    FILE *f = fopen(db->db_path, "r");
    if (!f) return;

    char line[512];
    while (fgets(line, sizeof(line), f)) {
        char type_char;
        char pattern[MAX_PATTERN_LEN];
        int severity = 1;

        if (sscanf(line, "%c|%255[^|]|%d", &type_char, pattern, &severity) >= 2) {
            if (type_char == 'B' && db->blocked.count < MAX_PATTERNS) {
                safe_copy(db->blocked.entries[db->blocked.count].pattern, pattern, MAX_PATTERN_LEN);
                db->blocked.entries[db->blocked.count].type = PAT_BLOCKED;
                db->blocked.entries[db->blocked.count].severity = severity;
                db->blocked.count++;
            }
            if (type_char == 'A' && db->allowed.count < MAX_PATTERNS) {
                safe_copy(db->allowed.entries[db->allowed.count].pattern, pattern, MAX_PATTERN_LEN);
                db->allowed.entries[db->allowed.count].type = PAT_ALLOWED;
                db->allowed.entries[db->allowed.count].severity = severity;
                db->allowed.count++;
            }
        }
    }
    fclose(f);
}

static void DbSave(PatternDb *db) {
    FILE *f = fopen(db->db_path, "w");
    if (!f) return;

    int i;
    for (i = 0; i < db->blocked.count; i++)
        fprintf(f, "B|%s|%d\n", db->blocked.entries[i].pattern, db->blocked.entries[i].severity);
    for (i = 0; i < db->allowed.count; i++)
        fprintf(f, "A|%s|%d\n", db->allowed.entries[i].pattern, db->allowed.entries[i].severity);

    fclose(f);
}

static int DbAdd(PatternDb *db, int type, const char *pattern, int severity) {
    PatternList *list = (type == PAT_BLOCKED) ? &db->blocked : &db->allowed;
    if (list->count >= MAX_PATTERNS)
        return 0;

    /* Reject empty or oversized patterns */
    int plen = strlen(pattern);
    if (plen == 0 || plen >= MAX_PATTERN_LEN)
        return 0;

    /* Reject patterns with pipe or newline — they corrupt the DB format */
    if (strchr(pattern, '|') || strchr(pattern, '\n'))
        return 0;

    int i;
    for (i = 0; i < list->count; i++) {
        if (strcmp(list->entries[i].pattern, pattern) == 0)
            return 0;
    }

    safe_copy(list->entries[list->count].pattern, pattern, MAX_PATTERN_LEN);
    list->entries[list->count].type = type;
    list->entries[list->count].severity = severity;
    list->count++;
    DbSave(db);
    return 1;
}

static int DbRemove(PatternDb *db, int type, const char *pattern) {
    PatternList *list = (type == PAT_BLOCKED) ? &db->blocked : &db->allowed;
    int i;
    for (i = 0; i < list->count; i++) {
        if (strcmp(list->entries[i].pattern, pattern) == 0) {
            int j;
            for (j = i; j < list->count - 1; j++)
                list->entries[j] = list->entries[j + 1];
            list->count--;
            DbSave(db);
            return 1;
        }
    }
    return 0;
}

static void DbList(PatternDb *db) {
    printf("\n--- BLOCKED PATTERNS (%d) ---\n", db->blocked.count);
    int i;
    for (i = 0; i < db->blocked.count; i++)
        printf("  [%d] %s (sev=%d)\n", i + 1, db->blocked.entries[i].pattern, db->blocked.entries[i].severity);

    printf("\n--- ALLOWED PATTERNS (%d) ---\n", db->allowed.count);
    for (i = 0; i < db->allowed.count; i++)
        printf("  [%d] %s (sev=%d)\n", i + 1, db->allowed.entries[i].pattern, db->allowed.entries[i].severity);
    printf("\n");
}

static void DbReport(PatternDb *db, const char *db_path, const char *log_dir) {
    printf("========================================\n");
    printf("  CASCADE CLI REPORT — CEK v%s\n", VERSION);
    printf("========================================\n\n");

    /* DB info */
    printf("Pattern DB: %s\n", db_path);
    printf("  Blocked patterns: %d / %d\n", db->blocked.count, MAX_PATTERNS);
    printf("  Allowed patterns: %d / %d\n\n", db->allowed.count, MAX_PATTERNS);

    /* Severity breakdown */
    int sev_low = 0, sev_mid = 0, sev_high = 0;
    int i;
    for (i = 0; i < db->blocked.count; i++) {
        if (db->blocked.entries[i].severity >= 5) sev_high++;
        else if (db->blocked.entries[i].severity >= 3) sev_mid++;
        else sev_low++;
    }
    printf("Blocked severity: low=%d  mid=%d  high=%d\n\n", sev_low, sev_mid, sev_high);

    /* All blocked patterns */
    if (db->blocked.count > 0) {
        printf("--- BLOCKED ---\n");
        for (i = 0; i < db->blocked.count; i++)
            printf("  [%d] %s (sev=%d)\n", i + 1, db->blocked.entries[i].pattern, db->blocked.entries[i].severity);
        printf("\n");
    }

    /* All allowed patterns */
    if (db->allowed.count > 0) {
        printf("--- ALLOWED ---\n");
        for (i = 0; i < db->allowed.count; i++)
            printf("  [%d] %s (sev=%d)\n", i + 1, db->allowed.entries[i].pattern, db->allowed.entries[i].severity);
        printf("\n");
    }

    /* Exec log stats */
    char log_path[MAX_BUF];
    snprintf(log_path, sizeof(log_path), "%s/%s", log_dir, LOG_FILENAME);
    struct stat st;
    if (stat(log_path, &st) == 0) {
        printf("Exec Log: %s\n", log_path);
        printf("  Size: %ld bytes\n", (long)st.st_size);

        FILE *f = fopen(log_path, "r");
        if (f) {
            char line[512];
            int total = 0, done = 0, failed = 0, timeout = 0, stuck = 0, killed = 0, other = 0;
            while (fgets(line, sizeof(line), f)) {
                total++;
                if (strstr(line, "|DONE|")) done++;
                else if (strstr(line, "|FAILED|")) failed++;
                else if (strstr(line, "|TIMEOUT|")) timeout++;
                else if (strstr(line, "|STUCK|")) stuck++;
                else if (strstr(line, "|KILLED|")) killed++;
                else other++;
            }
            fclose(f);
            printf("  Total runs: %d\n", total);
            printf("  Done: %d  Failed: %d  Timeout: %d  Stuck: %d  Killed: %d  Other: %d\n",
                   done, failed, timeout, stuck, killed, other);
            if (total > 0)
                printf("  Success rate: %.1f%%\n", (double)done / total * 100.0);
        }
    } else {
        printf("Exec Log: (none yet)\n");
    }

    /* Old log if rotated */
    char old_path[MAX_BUF];
    snprintf(old_path, sizeof(old_path), "%s/%s.old", log_dir, LOG_FILENAME);
    if (stat(old_path, &st) == 0)
        printf("  Rotated log: %s (%ld bytes)\n", old_path, (long)st.st_size);

    printf("\n========================================\n");
}

static int DbClear(PatternDb *db, int type) {
    PatternList *list = (type == PAT_BLOCKED) ? &db->blocked : &db->allowed;
    int cleared = list->count;
    list->count = 0;
    DbSave(db);
    return cleared;
}

/* ════════════════════════════════════════════
 * COMMAND VALIDATION (DB-DRIVEN)
 * Checks blocked patterns first, then allowed overrides
 * ════════════════════════════════════════════ */

static int ValidateCommand(PatternDb *db, const char *cmd, int allow_override) {
    char lower_cmd[MAX_CMD];
    safe_copy(lower_cmd, cmd, MAX_CMD);
    str_to_lower(lower_cmd, MAX_CMD);

    int i;
    for (i = 0; i < db->blocked.count; i++) {
        char lower_pat[MAX_PATTERN_LEN];
        safe_copy(lower_pat, db->blocked.entries[i].pattern, MAX_PATTERN_LEN);
        str_to_lower(lower_pat, MAX_PATTERN_LEN);
        if (strstr(lower_cmd, lower_pat)) {
            if (allow_override) {
                int overridden = 0;
                int j;
                for (j = 0; j < db->allowed.count; j++) {
                    char lower_allow[MAX_PATTERN_LEN];
                    safe_copy(lower_allow, db->allowed.entries[j].pattern, MAX_PATTERN_LEN);
                    str_to_lower(lower_allow, MAX_PATTERN_LEN);
                    if (strstr(lower_cmd, lower_allow)) {
                        overridden = 1;
                        break;
                    }
                }
                if (overridden)
                    continue;
            }
            fprintf(stderr, "[BLOCKED] matched rule: %s\n", db->blocked.entries[i].pattern);
            return 0;
        }
    }
    return 1;
}

/* ════════════════════════════════════════════
 * STRUCTURAL VALIDATION (anti-stuck)
 * Detects command patterns that cause terminal
 * feedback loops, shell parsing corruption, and
 * stuck states — NOT blocked patterns, but
 * structural dangers in the command string itself.
 *
 * Returns: 1 = safe to run, 0 = blocked
 * Severity: 0 = info/warning, 1 = block
 * ════════════════════════════════════════════ */

#define STRUCT_WARN    0
#define STRUCT_BLOCK   1

static int ValidateStructure(const char *cmd, int force) {
    int len = (int)strlen(cmd);
    int warnings = 0;
    int blocks = 0;

    /* 1. Unbalanced single quotes — shell will hang waiting for closing quote */
    int in_single = 0, in_double = 0;
    int i;
    for (i = 0; i < len; i++) {
        char c = cmd[i];
        if (c == '\\' && i + 1 < len) { i++; continue; }
        if (!in_double && c == '\'') { in_single = !in_single; }
        if (!in_single && c == '"')  { in_double = !in_double; }
    }
    if (in_single) {
        fprintf(stderr, "[STRUCTURE-WARN] Unbalanced single quote — shell may hang waiting for closing quote\n");
        warnings++;
    }
    if (in_double) {
        fprintf(stderr, "[STRUCTURE-WARN] Unbalanced double quote — shell may hang waiting for closing quote\n");
        warnings++;
    }

    /* 2. Backticks in command — shell command substitution can cause feedback loops */
    int backticks = 0;
    for (i = 0; i < len; i++) {
        if (cmd[i] == '`') backticks++;
    }
    if (backticks > 0 && backticks % 2 != 0) {
        fprintf(stderr, "[STRUCTURE-BLOCK] Odd number of backticks (%d) — unbalanced command substitution, terminal will hang\n", backticks);
        blocks++;
    } else if (backticks >= 2) {
        fprintf(stderr, "[STRUCTURE-WARN] %d backticks in command — shell command substitution active, verify intent\n", backticks);
        warnings++;
    }

    /* 3. Long python3 -c commands — suggest temp file instead */
    char lower_cmd[MAX_CMD];
    safe_copy(lower_cmd, cmd, MAX_CMD);
    str_to_lower(lower_cmd, MAX_CMD);
    char *py_c = strstr(lower_cmd, "python3 -c");
    if (!py_c) py_c = strstr(lower_cmd, "python -c");
    if (py_c) {
        int py_len = len - (int)(py_c - lower_cmd);
        if (py_len > 2000) {
            fprintf(stderr, "[STRUCTURE-WARN] python3 -c command is %d chars — consider writing to temp .py file instead\n", py_len);
            warnings++;
        }
        if (py_len > 5000) {
            fprintf(stderr, "[STRUCTURE-BLOCK] python3 -c command is %d chars — too long for safe shell execution, use a temp file\n", py_len);
            blocks++;
        }
        /* Check for embedded newlines in python3 -c (causes shell re-interpretation) */
        int embedded_newlines = 0;
        const char *py_start = cmd + (py_c - lower_cmd);
        for (i = 0; py_start[i] && i < py_len; i++) {
            if (py_start[i] == '\n') embedded_newlines++;
        }
        if (embedded_newlines > 5) {
            fprintf(stderr, "[STRUCTURE-WARN] python3 -c has %d embedded newlines — shell may misparse, consider temp file\n", embedded_newlines);
            warnings++;
        }
    }

    /* 4. Non-ASCII control characters (unicode box-drawing corrupts terminal) */
    int non_ascii = 0;
    for (i = 0; i < len; i++) {
        unsigned char uc = (unsigned char)cmd[i];
        if (uc > 127) non_ascii++;
    }
    if (non_ascii > 50) {
        fprintf(stderr, "[STRUCTURE-WARN] %d non-ASCII bytes in command — may corrupt terminal display\n", non_ascii);
        warnings++;
    }

    /* 5. Repeated patterns (feedback loop indicator) — same 20+ char substring 3+ times */
    if (len > 200) {
        int repeats = 0;
        char sample[21];
        safe_copy(sample, cmd, 21);
        const char *p = cmd;
        while ((p = strstr(p + 1, sample)) != NULL) {
            repeats++;
            if (repeats >= 3) break;
        }
        if (repeats >= 3) {
            fprintf(stderr, "[STRUCTURE-BLOCK] First 20 chars repeated %d+ times — likely a feedback loop, aborting\n", repeats);
            blocks++;
        }
    }

    /* 6. Command length sanity */
    if (len > 50000) {
        fprintf(stderr, "[STRUCTURE-BLOCK] Command is %d chars — exceeds 50KB limit, use a temp file\n", len);
        blocks++;
    }

    /* Report summary */
    if (warnings > 0 || blocks > 0) {
        fprintf(stderr, "[STRUCTURE] %d warning(s), %d block(s)%s\n", warnings, blocks, force ? " (force=on)" : "");
    }

    /* Blocks prevent execution unless --force is set */
    if (blocks > 0 && !force) {
        fprintf(stderr, "[STRUCTURE] Command blocked by structural validation. Use --force to override at your own risk.\n");
        return 0;
    }

    return 1;
}

/* ════════════════════════════════════════════
 * ERROR DETECTION + TRACEBACK EXTRACTION
 * ════════════════════════════════════════════ */

static void DetectErrors(const char *stderr_text, const char *stdout_text) {
    int stderr_len = strlen(stderr_text);
    int stdout_len = strlen(stdout_text);
    int combined_len = stderr_len + stdout_len + 2;
    if (combined_len > 65536) combined_len = 65536;
    char combined[65536];
    snprintf(combined, combined_len, "%s %s", stderr_text, stdout_text);
    str_to_lower(combined, combined_len);

    int found = 0;
    int i;
    for (i = 0; ERROR_TABLE[i].name; i++) {
        if (strstr(combined, ERROR_TABLE[i].keyword)) {
            if (!found) {
                printf("\n--- Error Detection ---\n");
                found = 1;
            }
            printf("  [%s] type=%s\n", ERROR_TABLE[i].name, ERROR_TABLE[i].type);
        }
    }
    if (found) printf("\n");
}

static void ExtractTraceback(const char *stderr_text) {
    const char *p = stderr_text;
    const char *needle = "File \"";
    int found = 0;

    while ((p = strstr(p, needle)) != NULL) {
        p += strlen(needle);
        const char *q = strchr(p, '"');
        if (!q) break;

        char filepath[1024];
        int len = q - p;
        if (len >= 1024) len = 1023;
        memcpy(filepath, p, len);
        filepath[len] = '\0';

        q++;
        if (*q == ',') q++;
        while (*q == ' ') q++;

        int lineno = 0;
        if (strncmp(q, "line ", 5) == 0)
            lineno = atoi(q + 5);

        const char *func_start = strstr(q, "in ");
        char func[256] = "<module>";
        if (func_start) {
            func_start += 3;
            const char *func_end = func_start;
            while (*func_end && *func_end != '\n' && *func_end != '\r') func_end++;
            int flen = func_end - func_start;
            if (flen >= 256) flen = 255;
            memcpy(func, func_start, flen);
            func[flen] = '\0';
        }

        if (!found) {
            printf("\n--- Error Location ---\n");
            found = 1;
        }
        printf("  %s:%d in %s()\n", filepath, lineno, func);
    }
    if (found) printf("\n");
}

/* ════════════════════════════════════════════
 * NON-BLOCKING I/O HELPER
 * ════════════════════════════════════════════ */

static int set_nonblock(int fd) {
    int flags = fcntl(fd, F_GETFL, 0);
    if (flags < 0) return -1;
    return fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}

/* ════════════════════════════════════════════
 * CORE EXECUTION ENGINE — RunExec
 * fork/exec/select with non-blocking I/O
 * Triple-layer protection: timeout + stuck + hard freeze
 * Process group isolation via setsid() + killpg()
 * ════════════════════════════════════════════ */

static ExecResult RunExec(CliArgs *args) {
    ExecResult r;
    memset(&r, 0, sizeof(r));
    r.state = ST_INIT;
    r.attempt = 1;
    r.total_attempts = 1;
    clock_gettime(CLOCK_MONOTONIC, &r.start_time);

    int stdout_pipe[2] = {-1, -1};
    int stderr_pipe[2] = {-1, -1};
    int stdin_pipe[2] = {-1, -1};

    if (pipe(stdout_pipe) < 0 || pipe(stderr_pipe) < 0) {
        r.state = ST_ERROR;
        r.exit_code = EXIT_ERROR;
        snprintf(r.stderr_buf, sizeof(r.stderr_buf), "pipe() failed: %s", strerror(errno));
        return r;
    }

    if (args->has_stdin && pipe(stdin_pipe) < 0) {
        r.state = ST_ERROR;
        r.exit_code = EXIT_ERROR;
        snprintf(r.stderr_buf, sizeof(r.stderr_buf), "stdin pipe() failed: %s", strerror(errno));
        close(stdout_pipe[0]); close(stdout_pipe[1]);
        close(stderr_pipe[0]); close(stderr_pipe[1]);
        return r;
    }

    /* Validate timeout and stuck thresholds */
    if (args->timeout < 1)
        args->timeout = DEFAULT_TIMEOUT;
    if (args->stuck_threshold < 1)
        args->stuck_threshold = DEFAULT_STUCK;
    if (args->retry < 0)
        args->retry = 0;
    if (args->max_output < 1024)
        args->max_output = 1024;

    r.pid = fork();

    if (r.pid < 0) {
        r.state = ST_ERROR;
        r.exit_code = EXIT_ERROR;
        snprintf(r.stderr_buf, sizeof(r.stderr_buf), "fork() failed: %s", strerror(errno));
        close(stdout_pipe[0]); close(stdout_pipe[1]);
        close(stderr_pipe[0]); close(stderr_pipe[1]);
        if (args->has_stdin) { close(stdin_pipe[0]); close(stdin_pipe[1]); }
        return r;
    }

    if (r.pid == 0) {
        /* ── CHILD PROCESS ── */
        setsid();

        /* Reset signals to defaults */
        signal(SIGPIPE, SIG_DFL);
        signal(SIGINT, SIG_DFL);
        signal(SIGTERM, SIG_DFL);

        dup2(stdout_pipe[1], STDOUT_FILENO);
        dup2(stderr_pipe[1], STDERR_FILENO);
        close(stdout_pipe[0]); close(stdout_pipe[1]);
        close(stderr_pipe[0]); close(stderr_pipe[1]);

        if (args->has_stdin) {
            dup2(stdin_pipe[0], STDIN_FILENO);
            close(stdin_pipe[0]); close(stdin_pipe[1]);
        } else {
            int devnull = open("/dev/null", O_RDONLY);
            if (devnull >= 0) {
                dup2(devnull, STDIN_FILENO);
                close(devnull);
            }
        }

        if (args->cwd[0]) {
            if (chdir(args->cwd) < 0) {
                fprintf(stderr, "chdir(%s) failed: %s\n", args->cwd, strerror(errno));
                _exit(127);
            }
        }

        int i;
        for (i = 0; i < args->env_count; i++) {
            char key[512];
            char *eq = strchr(args->env_vars[i], '=');
            if (eq) {
                int klen = eq - args->env_vars[i];
                if (klen >= 512) klen = 511;
                memcpy(key, args->env_vars[i], klen);
                key[klen] = '\0';
                setenv(key, eq + 1, 1);
            }
        }

        if (args->shell) {
            execl("/bin/sh", "sh", "-c", args->command, (char *)NULL);
        } else {
            char *argv[256];
            char cmd_copy[MAX_CMD];
            safe_copy(cmd_copy, args->command, MAX_CMD);

            int argc = 0;
            char *tok = strtok(cmd_copy, " \t");
            while (tok && argc < 255) {
                argv[argc++] = tok;
                tok = strtok(NULL, " \t");
            }
            argv[argc] = NULL;

            if (argc == 0) {
                fprintf(stderr, "Empty command\n");
                _exit(127);
            }
            execvp(argv[0], argv);
        }

        fprintf(stderr, "exec failed: %s\n", strerror(errno));
        _exit(127);
    }

    /* ── PARENT PROCESS ── */
    close(stdout_pipe[1]);
    close(stderr_pipe[1]);
    if (args->has_stdin) {
        close(stdin_pipe[0]);
        int wlen = (int)write(stdin_pipe[1], args->stdin_data, strlen(args->stdin_data));
        if (wlen < 0)
            snprintf(r.stderr_buf, sizeof(r.stderr_buf), "stdin write failed: %s", strerror(errno));
        close(stdin_pipe[1]);
    }

    set_nonblock(stdout_pipe[0]);
    set_nonblock(stderr_pipe[0]);

    r.state = ST_RUNNING;

    struct timespec last_output;
    clock_gettime(CLOCK_MONOTONIC, &last_output);

    char read_buf[MAX_BUF];
    int running = 1;
    int killed = 0;

    while (running) {
        fd_set rfds;
        FD_ZERO(&rfds);
        int maxfd = -1;
        if (stdout_pipe[0] >= 0) { FD_SET(stdout_pipe[0], &rfds); if (stdout_pipe[0] > maxfd) maxfd = stdout_pipe[0]; }
        if (stderr_pipe[0] >= 0) { FD_SET(stderr_pipe[0], &rfds); if (stderr_pipe[0] > maxfd) maxfd = stderr_pipe[0]; }

        struct timeval tv;
        tv.tv_sec = 0;
        tv.tv_usec = 200000;

        int ready = (maxfd >= 0) ? select(maxfd + 1, &rfds, NULL, NULL, &tv) : 0;

        /* Handle select interrupted by signal */
        if (ready < 0) {
            if (errno == EINTR)
                continue;
            r.state = ST_ERROR;
            r.exit_code = EXIT_ERROR;
            snprintf(r.stderr_buf, sizeof(r.stderr_buf), "select() failed: %s", strerror(errno));
            killpg(r.pid, SIGKILL);
            killed = 1;
            break;
        }

        double now = elapsed_sec(&r.start_time);
        double since_output = elapsed_sec(&last_output);

        if (ready > 0) {
            if (stdout_pipe[0] >= 0 && FD_ISSET(stdout_pipe[0], &rfds)) {
                ssize_t n = read(stdout_pipe[0], read_buf, sizeof(read_buf) - 1);
                if (n < 0) {
                    if (errno == EINTR || errno == EAGAIN)
                        n = 0;
                    else {
                        close(stdout_pipe[0]);
                        stdout_pipe[0] = -1;
                        continue;
                    }
                }
                if (n > 0) {
                    read_buf[n] = '\0';
                    if (r.stdout_len + n < args->max_output) {
                        memcpy(r.stdout_buf + r.stdout_len, read_buf, n);
                        r.stdout_len += n;
                        r.stdout_buf[r.stdout_len] = '\0';
                    } else if (!r.stdout_truncated) {
                        r.stdout_truncated = 1;
                        int remain = args->max_output - r.stdout_len;
                        if (remain > 0) {
                            memcpy(r.stdout_buf + r.stdout_len, read_buf, remain);
                            r.stdout_len += remain;
                        }
                        const char *msg = "\n...[output truncated]";
                        int mlen = strlen(msg);
                        if (r.stdout_len + mlen < (int)sizeof(r.stdout_buf)) {
                            memcpy(r.stdout_buf + r.stdout_len, msg, mlen);
                            r.stdout_len += mlen;
                            r.stdout_buf[r.stdout_len] = '\0';
                        }
                    }
                    r.state = ST_STREAMING;
                    clock_gettime(CLOCK_MONOTONIC, &last_output);
                } else if (n == 0) {
                    close(stdout_pipe[0]);
                    stdout_pipe[0] = -1;
                }
            }
            if (stderr_pipe[0] >= 0 && FD_ISSET(stderr_pipe[0], &rfds)) {
                ssize_t n = read(stderr_pipe[0], read_buf, sizeof(read_buf) - 1);
                if (n < 0) {
                    if (errno == EINTR || errno == EAGAIN)
                        n = 0;
                    else {
                        close(stderr_pipe[0]);
                        stderr_pipe[0] = -1;
                        continue;
                    }
                }
                if (n > 0) {
                    read_buf[n] = '\0';
                    if (r.stderr_len + n < args->max_output) {
                        memcpy(r.stderr_buf + r.stderr_len, read_buf, n);
                        r.stderr_len += n;
                        r.stderr_buf[r.stderr_len] = '\0';
                    } else if (!r.stderr_truncated) {
                        r.stderr_truncated = 1;
                        int remain = args->max_output - r.stderr_len;
                        if (remain > 0) {
                            memcpy(r.stderr_buf + r.stderr_len, read_buf, remain);
                            r.stderr_len += remain;
                        }
                        const char *msg = "\n...[output truncated]";
                        int mlen = strlen(msg);
                        if (r.stderr_len + mlen < (int)sizeof(r.stderr_buf)) {
                            memcpy(r.stderr_buf + r.stderr_len, msg, mlen);
                            r.stderr_len += mlen;
                            r.stderr_buf[r.stderr_len] = '\0';
                        }
                    }
                    r.state = ST_STREAMING;
                    clock_gettime(CLOCK_MONOTONIC, &last_output);
                } else if (n == 0) {
                    close(stderr_pipe[0]);
                    stderr_pipe[0] = -1;
                }
            }
        }

        /* Both pipes closed — collect exit code */
        if (stdout_pipe[0] < 0 && stderr_pipe[0] < 0) {
            int status;
            pid_t wret = waitpid(r.pid, &status, 0);
            if (wret == r.pid) {
                if (WIFEXITED(status))
                    r.exit_code = WEXITSTATUS(status);
                else if (WIFSIGNALED(status))
                    r.exit_code = 128 + WTERMSIG(status);
            }
            running = 0;
            break;
        }

        /* Non-blocking waitpid check */
        int status;
        pid_t wret = waitpid(r.pid, &status, WNOHANG);
        if (wret == r.pid) {
            if (WIFEXITED(status))
                r.exit_code = WEXITSTATUS(status);
            else if (WIFSIGNALED(status))
                r.exit_code = 128 + WTERMSIG(status);
            running = 0;
            break;
        }

        /* Layer 1: timeout */
        if (now > args->timeout) {
            r.state = ST_TIMEOUT;
            killpg(r.pid, SIGKILL);
            killed = 1;
            break;
        }

        /* Layer 2: stuck detection (no output for stuck_threshold seconds) */
        if (!args->no_stuck && r.state != ST_KILLED) {
            if (since_output > args->stuck_threshold && r.state != ST_STUCK) {
                r.state = ST_STUCK;
            }
            /* Reset stuck if output resumed */
            if (r.state == ST_STUCK && since_output < 1.0) {
                r.state = ST_STREAMING;
            }
        }

        /* Layer 3: hard freeze (2x stuck threshold — kill it) */
        if (!args->no_stuck && since_output > args->stuck_threshold * 2) {
            r.state = ST_KILLED;
            killpg(r.pid, SIGKILL);
            killed = 1;
            break;
        }
    }

    /* Reap if we killed it */
    if (killed) {
        int status;
        waitpid(r.pid, &status, 0);
        if (r.exit_code == 0)
            r.exit_code = EXIT_KILLED;
    }

    /* Clean up any remaining open pipes */
    if (stdout_pipe[0] >= 0) close(stdout_pipe[0]);
    if (stderr_pipe[0] >= 0) close(stderr_pipe[0]);

    r.duration = elapsed_sec(&r.start_time);

    /* Finalize state */
    if (r.state == ST_RUNNING || r.state == ST_STREAMING) {
        if (r.exit_code == 0)
            r.state = ST_DONE;
        else
            r.state = ST_FAILED;
    }

    return r;
}

/* ════════════════════════════════════════════
 * RETRY WRAPPER — RunWithRetry
 * Linear backoff: attempt * 1000ms
 * ════════════════════════════════════════════ */

static ExecResult RunWithRetry(CliArgs *args) {
    ExecResult r;
    memset(&r, 0, sizeof(r));
    int retry = args->retry;
    if (retry < 0) retry = 0;
    int max_attempts = retry + 1;
    int attempt;

    for (attempt = 1; attempt <= max_attempts; attempt++) {
        r = RunExec(args);
        r.attempt = attempt;
        r.total_attempts = max_attempts;

        if (r.state == ST_DONE || r.state == ST_BLOCKED || r.state == ST_ERROR)
            break;

        if (attempt < max_attempts) {
            sleep_ms(attempt * 1000);
        }
    }
    return r;
}

/* ════════════════════════════════════════════
 * JSON OUTPUT — PrintJson
 * ════════════════════════════════════════════ */

static void json_escape(const char *in, char *out, size_t out_sz) {
    size_t j = 0;
    size_t i;
    for (i = 0; in[i] && j + 6 < out_sz; i++) {
        unsigned char c = (unsigned char)in[i];
        if (c == '"')       { out[j++] = '\\'; out[j++] = '"'; }
        else if (c == '\\') { out[j++] = '\\'; out[j++] = '\\'; }
        else if (c == '\n') { out[j++] = '\\'; out[j++] = 'n'; }
        else if (c == '\r') { out[j++] = '\\'; out[j++] = 'r'; }
        else if (c == '\t') { out[j++] = '\\'; out[j++] = 't'; }
        else if (c < 32)    { j += snprintf(out + j, out_sz - j, "\\u%04x", c); }
        else                { out[j++] = c; }
    }
    out[j] = '\0';
}

static void PrintJson(ExecResult *r, CliArgs *args) {
    /* Use static buffers for escaped output */
    static char stdout_esc[2097152];
    static char stderr_esc[2097152];

    json_escape(r->stdout_buf, stdout_esc, sizeof(stdout_esc));
    json_escape(r->stderr_buf, stderr_esc, sizeof(stderr_esc));

    static char cmd_esc[MAX_CMD * 2];
    json_escape(args->command, cmd_esc, sizeof(cmd_esc));

    printf("{\n");
    printf("  \"command\": \"%s\",\n", cmd_esc);
    printf("  \"status\": \"%s\",\n", STATE_NAMES[r->state]);
    printf("  \"exit_code\": %d,\n", r->exit_code);
    printf("  \"duration\": %.2f,\n", r->duration);
    printf("  \"stdout\": \"%s\",\n", stdout_esc);
    printf("  \"stderr\": \"%s\",\n", stderr_esc);
    printf("  \"stdout_truncated\": %s,\n", r->stdout_truncated ? "true" : "false");
    printf("  \"stderr_truncated\": %s,\n", r->stderr_truncated ? "true" : "false");
    printf("  \"attempt\": %d,\n", r->attempt);
    printf("  \"total_attempts\": %d,\n", r->total_attempts);

    /* Error detection in JSON mode too */
    if (r->state != ST_DONE && r->state != ST_BLOCKED && r->stderr_len > 0) {
        int stderr_len = strlen(r->stderr_buf);
        int stdout_len = strlen(r->stdout_buf);
        int combined_len = stderr_len + stdout_len + 2;
        if (combined_len > 65536) combined_len = 65536;
        char combined[65536];
        snprintf(combined, combined_len, "%s %s", r->stderr_buf, r->stdout_buf);
        str_to_lower(combined, combined_len);

        /* First pass: count matches */
        int match_count = 0;
        int j;
        for (j = 0; ERROR_TABLE[j].name; j++) {
            if (strstr(combined, ERROR_TABLE[j].keyword))
                match_count++;
        }

        if (match_count > 0) {
            printf("  \"errors_detected\": [\n");
            int printed = 0;
            for (j = 0; ERROR_TABLE[j].name; j++) {
                if (strstr(combined, ERROR_TABLE[j].keyword)) {
                    printed++;
                    printf("    {\"name\": \"%s\", \"type\": \"%s\"}%s\n",
                           ERROR_TABLE[j].name, ERROR_TABLE[j].type,
                           (printed < match_count) ? "," : "");
                }
            }
            printf("  ]\n");
        } else {
            printf("  \"errors_detected\": []\n");
        }
    } else {
        printf("  \"errors_detected\": []\n");
    }

    printf("}\n");
}

/* ════════════════════════════════════════════
 * HUMAN-READABLE OUTPUT — PrintResult
 * ════════════════════════════════════════════ */

static void PrintResult(ExecResult *r, CliArgs *args) {
    if (args->quiet) {
        printf("%s", r->stdout_buf);
        return;
    }

    const char *icon = STATE_ICONS[r->state];
    const char *status = STATE_NAMES[r->state];

    char retry_info[64] = "";
    if (r->total_attempts > 1)
        snprintf(retry_info, sizeof(retry_info), " attempt=%d/%d", r->attempt, r->total_attempts);

    char trunc_info[32] = "";
    if (r->stdout_truncated || r->stderr_truncated)
        snprintf(trunc_info, sizeof(trunc_info), " [output truncated]");

    printf("[%s] %s exit=%d time=%.2fs%s%s\n",
           icon, status, r->exit_code, r->duration, retry_info, trunc_info);

    if (r->stdout_len > 0) {
        printf("\n--- stdout ---\n");
        printf("%s", r->stdout_buf);
        if (r->stdout_len > 0 && r->stdout_buf[r->stdout_len - 1] != '\n')
            printf("\n");
    }

    if (r->stderr_len > 0 && r->state != ST_DONE) {
        printf("\n--- stderr ---\n");
        printf("%s", r->stderr_buf);
        if (r->stderr_len > 0 && r->stderr_buf[r->stderr_len - 1] != '\n')
            printf("\n");
    }

    if (r->state != ST_DONE && r->state != ST_BLOCKED && r->stderr_len > 0) {
        ExtractTraceback(r->stderr_buf);
        DetectErrors(r->stderr_buf, r->stdout_buf);
    }
}

/* ════════════════════════════════════════════
 * AI FIX SUGGESTION — Pure C neural model
 * Loads trained weights, extracts features, forward pass, suggests fix
 * ════════════════════════════════════════════ */

static void str_to_lower_buf(char *dst, const char *src, int max) {
    int i;
    for (i = 0; i < max - 1 && src[i]; i++)
        dst[i] = tolower((unsigned char)src[i]);
    dst[i] = '\0';
}

static int contains_str(const char *haystack, const char *needle) {
    return strstr(haystack, needle) != NULL;
}

static int has_digit(const char *s) {
    for (; *s; s++)
        if (*s >= '0' && *s <= '9')
            return 1;
    return 0;
}

/* Extract the error line from a traceback — first line containing "error" or "exception" */
static void extract_error_line(char *out, int out_max, const char *text_lower_src) {
    char text_copy[MAX_CMD];
    safe_copy(text_copy, text_lower_src, MAX_CMD);
    int len = strlen(text_copy);
    int start = 0;
    int i;
    for (i = 0; i <= len; i++) {
        if (text_copy[i] == '\n' || text_copy[i] == '\0') {
            int line_len = i - start;
            if (line_len > 0 && line_len < out_max) {
                text_copy[i] = '\0';
                char *line_start = text_copy + start;
                if (strstr(line_start, "error") || strstr(line_start, "exception") || strstr(line_start, "refused")) {
                    while (*line_start == ' ' || *line_start == '\t')
                        line_start++;
                    snprintf(out, out_max, "%s", line_start);
                    return;
                }
            }
            start = i + 1;
        }
    }
    snprintf(out, out_max, "%s", text_copy);
}

/* Extract 40D feature vector from error text */
static void FixExtractFeatures(float *features, const char *stderr_text) {
    char text_lower[MAX_CMD];
    str_to_lower_buf(text_lower, stderr_text, MAX_CMD);

    char error_line[MAX_CMD];
    extract_error_line(error_line, MAX_CMD, text_lower);

    int i, j;
    for (i = 0; i < FIX_INPUT_DIM; i++)
        features[i] = 0.0f;

    /* Features 0-15: error type one-hot */
    for (i = 0; i < 16; i++) {
        if (ERROR_TYPE_NAMES[i]) {
            char type_lower[64];
            str_to_lower_buf(type_lower, ERROR_TYPE_NAMES[i], 64);
            if (contains_str(error_line, type_lower))
                features[i] = 1.0f;
        }
    }

    /* Features 16-29: category presence */
    for (j = 0; j < 14; j++) {
        for (i = 0; i < 4; i++) {
            if (CATEGORY_KEYWORDS[j][i] && contains_str(error_line, CATEGORY_KEYWORDS[j][i])) {
                features[16 + j] = 1.0f;
                break;
            }
        }
    }

    /* Features 30-39: text properties */
    features[30] = contains_str(text_lower, "traceback") ? 1.0f : 0.0f;
    features[31] = (contains_str(error_line, "errno 2") || contains_str(error_line, "no such file")) ? 1.0f : 0.0f;
    features[32] = contains_str(text_lower, "line") ? 1.0f : 0.0f;
    int elen = strlen(error_line);
    features[33] = (elen > 500) ? 1.0f : (float)elen / 500.0f;
    int nl_count = 0;
    for (i = 0; text_lower[i]; i++)
        if (text_lower[i] == '\n')
            nl_count++;
    features[34] = (nl_count > 20) ? 1.0f : (float)nl_count / 20.0f;
    features[35] = contains_str(error_line, "error") ? 1.0f : 0.0f;
    features[36] = contains_str(error_line, "exception") ? 1.0f : 0.0f;
    features[37] = contains_str(error_line, "warning") ? 1.0f : 0.0f;
    features[38] = has_digit(error_line) ? 1.0f : 0.0f;
    features[39] = 1.0f;
}

/* Load trained weights from flat binary file (no header — raw float32)
 * Layout: W0[64*40], B0[64], W2[16*64], B2[16] = 3664 floats = 14656 bytes
 * Trained by coretotch_fix.c, same format as coretotch.c */
static int FixLoadWeights(const char *path, float *w1, float *b1, float *w2, float *b2) {
    FILE *f = fopen(path, "rb");
    if (!f)
        return 0;

    /* Flat binary: no dimension header, just raw float32 weights */
    if (fread(w1, sizeof(float), FIX_HIDDEN_DIM * FIX_INPUT_DIM, f) != FIX_HIDDEN_DIM * FIX_INPUT_DIM) {
        fclose(f);
        return 0;
    }
    if (fread(b1, sizeof(float), FIX_HIDDEN_DIM, f) != FIX_HIDDEN_DIM) {
        fclose(f);
        return 0;
    }
    if (fread(w2, sizeof(float), FIX_OUTPUT_DIM * FIX_HIDDEN_DIM, f) != FIX_OUTPUT_DIM * FIX_HIDDEN_DIM) {
        fclose(f);
        return 0;
    }
    if (fread(b2, sizeof(float), FIX_OUTPUT_DIM, f) != FIX_OUTPUT_DIM) {
        fclose(f);
        return 0;
    }
    fclose(f);
    return 1;
}

/* Forward pass: 40 -> ReLU(64) -> softmax(16) */
static int FixForwardPass(const float *features, const float *w1, const float *b1,
                          const float *w2, const float *b2, float *output) {
    float hidden[FIX_HIDDEN_DIM];
    int j, k;

    /* Layer 1: W1 @ x + b1, then ReLU */
    for (j = 0; j < FIX_HIDDEN_DIM; j++) {
        float s = b1[j];
        for (k = 0; k < FIX_INPUT_DIM; k++)
            s += w1[j * FIX_INPUT_DIM + k] * features[k];
        hidden[j] = (s > 0.0f) ? s : 0.0f;
    }

    /* Layer 2: W2 @ h + b2, then softmax */
    float maxLogit = -1e30f;
    for (k = 0; k < FIX_OUTPUT_DIM; k++) {
        float s = b2[k];
        for (j = 0; j < FIX_HIDDEN_DIM; j++)
            s += w2[k * FIX_HIDDEN_DIM + j] * hidden[j];
        output[k] = s;
        if (s > maxLogit)
            maxLogit = s;
    }

    float sumExp = 0.0f;
    for (k = 0; k < FIX_OUTPUT_DIM; k++) {
        output[k] = expf(output[k] - maxLogit);
        sumExp += output[k];
    }
    for (k = 0; k < FIX_OUTPUT_DIM; k++)
        output[k] /= sumExp;

    /* Return argmax */
    int bestIdx = 0;
    float bestVal = output[0];
    for (k = 1; k < FIX_OUTPUT_DIM; k++) {
        if (output[k] > bestVal) {
            bestVal = output[k];
            bestIdx = k;
        }
    }
    return bestIdx;
}

static void AiFixSuggest(ExecResult *r, const char *exe_dir) {
    if (r->stderr_len == 0)
        return;

    /* Load weights */
    char weights_path[MAX_BUF];
    snprintf(weights_path, sizeof(weights_path), "%s/%s", exe_dir, AI_FIX_WEIGHTS);

    static float w1[FIX_HIDDEN_DIM * FIX_INPUT_DIM];
    static float b1[FIX_HIDDEN_DIM];
    static float w2[FIX_OUTPUT_DIM * FIX_HIDDEN_DIM];
    static float b2[FIX_OUTPUT_DIM];

    if (!FixLoadWeights(weights_path, w1, b1, w2, b2))
        return;

    /* Extract features */
    float features[FIX_INPUT_DIM];
    FixExtractFeatures(features, r->stderr_buf);

    /* Forward pass */
    float output[FIX_OUTPUT_DIM];
    int bestIdx = FixForwardPass(features, w1, b1, w2, b2, output);
    float confidence = output[bestIdx];

    /* Find matching error type name for display */
    const char *errorName = "Unknown";
    int i;
    char text_lower[MAX_CMD];
    str_to_lower_buf(text_lower, r->stderr_buf, MAX_CMD);
    char error_line[MAX_CMD];
    extract_error_line(error_line, MAX_CMD, text_lower);
    for (i = 0; i < 16; i++) {
        if (ERROR_TYPE_NAMES[i]) {
            char type_lower[64];
            str_to_lower_buf(type_lower, ERROR_TYPE_NAMES[i], 64);
            if (contains_str(error_line, type_lower)) {
                errorName = ERROR_TYPE_NAMES[i];
                break;
            }
        }
    }

    printf("\n--- AI Fix Suggestion ---\n");
    printf("SUGGESTION:\n");
    printf("  Error: %s\n", errorName);
    printf("  Fix:   %s\n", FIX_DESCRIPTIONS[bestIdx]);
    printf("  Action: %s\n", FIX_ACTIONS[bestIdx]);
    printf("  Confidence: %.1f%% (neural model)\n", confidence * 100.0f);
    printf("\n");
}

/* ════════════════════════════════════════════
 * EXECUTION LOG — ExecLog
 * Appends execution results to a log file for learning
 * Format: timestamp|state|exit_code|duration|command
 * ════════════════════════════════════════════ */

static void ExecLog(ExecResult *r, CliArgs *args, const char *db_dir) {
    char log_path[MAX_BUF];
    snprintf(log_path, sizeof(log_path), "%s/%s", db_dir, LOG_FILENAME);

    /* Cap log size — rotate if too large */
    struct stat st;
    if (stat(log_path, &st) == 0 && st.st_size > MAX_LOG_SIZE) {
        char old_path[MAX_BUF];
        snprintf(old_path, sizeof(old_path), "%s.old", log_path);
        rename(log_path, old_path);
    }

    FILE *f = fopen(log_path, "a");
    if (!f) return;

    time_t now = time(NULL);
    struct tm *tm_info = localtime(&now);
    char ts[32];
    strftime(ts, sizeof(ts), "%Y-%m-%d %H:%M:%S", tm_info);

    /* Truncate command in log to 256 chars */
    char cmd_short[257];
    safe_copy(cmd_short, args->command, 257);

    fprintf(f, "%s|%s|%d|%.2f|%s\n",
            ts, STATE_NAMES[r->state], r->exit_code, r->duration, cmd_short);
    fclose(f);
}

/* ════════════════════════════════════════════
 * DRY RUN PREVIEW — PrintDryRun
 * ════════════════════════════════════════════ */

static void PrintDryRun(CliArgs *args) {
    printf("{\n");
    printf("  \"command\": \"%s\",\n", args->command);
    printf("  \"cwd\": \"%s\",\n", args->cwd[0] ? args->cwd : "(default)");
    printf("  \"timeout\": %d,\n", args->timeout);
    printf("  \"shell\": %s,\n", args->shell ? "true" : "false");
    printf("  \"retry\": %d,\n", args->retry);
    printf("  \"max_output\": %d,\n", args->max_output);
    printf("  \"no_stuck\": %s,\n", args->no_stuck ? "true" : "false");
    printf("  \"force\": %s,\n", args->force ? "true" : "false");
    printf("  \"allow_dangerous\": %s,\n", args->allow_dangerous ? "true" : "false");
    printf("  \"stdin\": %s,\n", args->has_stdin ? "true" : "false");
    printf("  \"env_count\": %d\n", args->env_count);
    printf("}\n");
}

/* ════════════════════════════════════════════
 * HELP — PrintHelp
 * ════════════════════════════════════════════ */

static void PrintHelp(void) {
    printf("Cascade Execution Kernel (CEK) v%s\n\n", VERSION);
    printf("Usage:\n");
    printf("  cascade_cli run \"command\" [options]\n");
    printf("  cascade_cli add-block \"pattern\" [severity]\n");
    printf("  cascade_cli add-allow \"pattern\" [severity]\n");
    printf("  cascade_cli rm-block \"pattern\"\n");
    printf("  cascade_cli rm-allow \"pattern\"\n");
    printf("  cascade_cli list\n");
    printf("  cascade_cli report\n");
    printf("  cascade_cli add-fix \"error_name\" \"error_keyword\" \"fix_description\"\n");
    printf("  cascade_cli list-fix\n");
    printf("  cascade_cli clear-block\n");
    printf("  cascade_cli clear-allow\n\n");
    printf("Run options:\n");
    printf("  -t, --timeout N       Timeout in seconds (default: %d)\n", DEFAULT_TIMEOUT);
    printf("  -C, --cwd PATH        Working directory\n");
    printf("  -j, --json            JSON output\n");
    printf("  -q, --quiet           Only show stdout\n");
    printf("  -s, --shell           Use /bin/sh -c (pipes, redirections)\n");
    printf("  -S, --no-stuck        Disable stuck detection (long queries)\n");
    printf("  -D, --allow-dangerous Allow blocked patterns via allow overrides\n");
    printf("  -X, --force           Override structural validation blocks (dangerous)\n");
    printf("  -r, --retry N         Retry N times on failure/timeout\n");
    printf("  -m, --max-output N    Max output chars per stream (default: %d)\n", DEFAULT_MAX_OUT);
    printf("  -e, --env KEY=VAL     Set env var (repeatable)\n");
    printf("  -i, --stdin TEXT      Pipe string to stdin\n");
    printf("  -d, --dry-run         Preview without executing\n");
    printf("  -F, --ai-fix          Suggest fix when error detected\n");
    printf("  -N, --max-no-output N Seconds without output before STUCK (default: %d)\n", DEFAULT_STUCK);
    printf("  -v, --version         Show version\n");
    printf("  -h, --help            Show this help\n\n");
    printf("Exit codes:\n");
    printf("  0=DONE  1=FAILED  123=KILLED  124=TIMEOUT  125=STUCK\n");
    printf("  126=ERROR  127=BLOCKED\n\n");
    printf("Pattern DB:\n");
    printf("  Patterns persist in %s next to the binary.\n", DB_FILENAME);
    printf("  Blocked patterns block matching commands.\n");
    printf("  Allowed patterns override blocked matches (with --allow-dangerous).\n");
}

/* ════════════════════════════════════════════
 * ARGUMENT PARSING — ParseArgs
 * Parses options after the subcommand (run)
 * ════════════════════════════════════════════ */

static void ParseArgs(int argc, char **argv, CliArgs *args) {
    memset(args, 0, sizeof(CliArgs));
    optind = 1;
    args->timeout = DEFAULT_TIMEOUT;
    args->stuck_threshold = DEFAULT_STUCK;
    args->max_output = DEFAULT_MAX_OUT;
    args->retry = 0;

    static struct option long_opts[] = {
        {"timeout",         required_argument, 0, 't'},
        {"cwd",             required_argument, 0, 'C'},
        {"json",            no_argument,       0, 'j'},
        {"quiet",           no_argument,       0, 'q'},
        {"shell",           no_argument,       0, 's'},
        {"no-stuck",        no_argument,       0, 'S'},
        {"allow-dangerous", no_argument,       0, 'D'},
        {"force",           no_argument,       0, 'X'},
        {"retry",           required_argument, 0, 'r'},
        {"max-output",      required_argument, 0, 'm'},
        {"env",             required_argument, 0, 'e'},
        {"stdin",           required_argument, 0, 'i'},
        {"dry-run",         no_argument,       0, 'd'},
        {"ai-fix",          no_argument,       0, 'F'},
        {"max-no-output",   required_argument, 0, 'N'},
        {"version",         no_argument,       0, 'v'},
        {"help",            no_argument,       0, 'h'},
        {0, 0, 0, 0}
    };

    const char *short_opts = "t:C:jqsSDXr:m:e:i:dvFN:h";

    int opt;
    while ((opt = getopt_long(argc, argv, short_opts, long_opts, NULL)) != -1) {
        switch (opt) {
            case 't': args->timeout = atoi(optarg); break;
            case 'C': safe_copy(args->cwd, optarg, MAX_BUF); break;
            case 'j': args->json = 1; break;
            case 'q': args->quiet = 1; break;
            case 's': args->shell = 1; break;
            case 'S': args->no_stuck = 1; break;
            case 'D': args->allow_dangerous = 1; break;
            case 'X': args->force = 1; break;
            case 'r': args->retry = atoi(optarg); break;
            case 'm': args->max_output = atoi(optarg); break;
            case 'e':
                if (args->env_count < MAX_ENV_VARS) {
                    safe_copy(args->env_vars[args->env_count], optarg, MAX_ENV_LEN);
                    args->env_count++;
                }
                break;
            case 'i':
                safe_copy(args->stdin_data, optarg, MAX_BUF);
                args->has_stdin = 1;
                break;
            case 'd': args->dry_run = 1; break;
            case 'F': args->ai_fix = 1; break;
            case 'N': args->stuck_threshold = atoi(optarg); break;
            case 'v':
                printf("cascade_cli v%s (CEK v5)\n", VERSION);
                exit(0);
            case 'h':
                PrintHelp();
                exit(0);
            default:
                fprintf(stderr, "Unknown option. Use --help.\n");
                exit(EXIT_ERROR);
        }
    }

    if (optind >= argc) {
        fprintf(stderr, "Error: no command specified. Use --help.\n");
        exit(EXIT_ERROR);
    }

    int cmd_len = 0;
    int i;
    for (i = optind; i < argc; i++) {
        int word_len = strlen(argv[i]);
        if (cmd_len + word_len + 2 >= MAX_CMD) break;
        if (cmd_len > 0)
            args->command[cmd_len++] = ' ';
        memcpy(args->command + cmd_len, argv[i], word_len);
        cmd_len += word_len;
    }
    args->command[cmd_len] = '\0';

    /* Reject empty commands */
    if (cmd_len == 0) {
        fprintf(stderr, "Error: empty command. Use --help.\n");
        exit(EXIT_ERROR);
    }
}

/* ════════════════════════════════════════════
 * DB PATH RESOLVER
 * Resolves DB path relative to the executable
 * ════════════════════════════════════════════ */

static void resolve_db_path(char *out, size_t out_sz) {
    char exe_path[MAX_BUF];
    uint32_t buf_size = sizeof(exe_path);

    /* macOS: _NSGetExecutablePath returns path to the binary */
    if (_NSGetExecutablePath(exe_path, &buf_size) == 0) {
        char *slash = strrchr(exe_path, '/');
        if (slash) {
            slash[1] = '\0';
            snprintf(out, out_sz, "%s%s", exe_path, DB_FILENAME);
            return;
        }
    }

    /* Fallback: current working directory */
    getcwd(out, out_sz);
    int dlen = strlen(out);
    snprintf(out + dlen, out_sz - dlen, "/%s", DB_FILENAME);
}

/* ════════════════════════════════════════════
 * Run() — MAIN DISPATCH
 * Routes subcommands to the right handler
 * Returns exit code
 * ════════════════════════════════════════════ */

static int Run(CascadeCli *self, int argc, char **argv) {
    signal(SIGPIPE, SIG_IGN);

    /* Resolve DB path */
    resolve_db_path(self->db_path, MAX_BUF);
    DbInit(&self->db, self->db_path);
    DbLoad(&self->db);

    if (argc < 2) {
        PrintHelp();
        return EXIT_ERROR;
    }

    /* ── DB COMMANDS ── */

    if (strcmp(argv[1], CMD_ADD_BLOCK) == 0) {
        if (argc < 3) {
            fprintf(stderr, "Usage: cascade_cli add-block \"pattern\" [severity]\n");
            return EXIT_ERROR;
        }
        int severity = (argc >= 4) ? atoi(argv[3]) : 3;
        int ok = DbAdd(&self->db, PAT_BLOCKED, argv[2], severity);
        if (ok)
            printf("[OK] Blocked pattern added: %s (sev=%d)\n", argv[2], severity);
        else
            printf("[FAIL] Pattern already exists or DB full\n");
        return ok ? EXIT_DONE : EXIT_FAILED;
    }

    if (strcmp(argv[1], CMD_ADD_ALLOW) == 0) {
        if (argc < 3) {
            fprintf(stderr, "Usage: cascade_cli add-allow \"pattern\" [severity]\n");
            return EXIT_ERROR;
        }
        int severity = (argc >= 4) ? atoi(argv[3]) : 1;
        int ok = DbAdd(&self->db, PAT_ALLOWED, argv[2], severity);
        if (ok)
            printf("[OK] Allowed pattern added: %s (sev=%d)\n", argv[2], severity);
        else
            printf("[FAIL] Pattern already exists or DB full\n");
        return ok ? EXIT_DONE : EXIT_FAILED;
    }

    if (strcmp(argv[1], CMD_RM_BLOCK) == 0) {
        if (argc < 3) {
            fprintf(stderr, "Usage: cascade_cli rm-block \"pattern\"\n");
            return EXIT_ERROR;
        }
        int ok = DbRemove(&self->db, PAT_BLOCKED, argv[2]);
        if (ok)
            printf("[OK] Blocked pattern removed: %s\n", argv[2]);
        else
            printf("[FAIL] Pattern not found\n");
        return ok ? EXIT_DONE : EXIT_FAILED;
    }

    if (strcmp(argv[1], CMD_RM_ALLOW) == 0) {
        if (argc < 3) {
            fprintf(stderr, "Usage: cascade_cli rm-allow \"pattern\"\n");
            return EXIT_ERROR;
        }
        int ok = DbRemove(&self->db, PAT_ALLOWED, argv[2]);
        if (ok)
            printf("[OK] Allowed pattern removed: %s\n", argv[2]);
        else
            printf("[FAIL] Pattern not found\n");
        return ok ? EXIT_DONE : EXIT_FAILED;
    }

    if (strcmp(argv[1], CMD_LIST) == 0) {
        DbList(&self->db);
        return EXIT_DONE;
    }

    if (strcmp(argv[1], CMD_ADD_FIX) == 0) {
        if (argc < 5) {
            fprintf(stderr, "Usage: cascade_cli add-fix \"error_name\" \"error_keyword\" \"fix_description\"\n");
            fprintf(stderr, "Note: fix rules are compiled into the neural model. Use ErrorFixTrainer.py to retrain.\n");
            return EXIT_ERROR;
        }
        printf("[INFO] Fix rules are compiled into the neural model weights.\n");
        printf("[INFO] To add a new rule, add it to ErrorFixTrainer.py RULES and run: python3 ErrorFixTrainer.py train\n");
        printf("[INFO] Then copy .cascade_fix_weights.bin next to cascade_cli.\n");
        printf("[INFO] Rule: %s -> %s -> %s\n", argv[2], argv[3], argv[4]);
        return EXIT_DONE;
    }

    if (strcmp(argv[1], CMD_LIST_FIX) == 0) {
        char db_dir[MAX_BUF];
        safe_copy(db_dir, self->db_path, MAX_BUF);
        char *slash = strrchr(db_dir, '/');
        if (slash) slash[1] = '\0';
        else db_dir[0] = '\0';
        char weights_path[MAX_BUF];
        snprintf(weights_path, sizeof(weights_path), "%s/%s", db_dir, AI_FIX_WEIGHTS);
        struct stat st;
        if (stat(weights_path, &st) == 0) {
            long expected = (FIX_HIDDEN_DIM * FIX_INPUT_DIM + FIX_HIDDEN_DIM + FIX_OUTPUT_DIM * FIX_HIDDEN_DIM + FIX_OUTPUT_DIM) * 4;
            printf("Neural Fix Model: %d->%d->%d (flat binary)\n", FIX_INPUT_DIM, FIX_HIDDEN_DIM, FIX_OUTPUT_DIM);
            printf("Weights: %s (%lld bytes, expected %ld)\n\n", weights_path, (long long)st.st_size, expected);
            printf("Fix Actions:\n");
            int i;
            for (i = 0; i < FIX_OUTPUT_DIM; i++) {
                printf("  [%2d] %-20s  %s\n", i, FIX_ACTIONS[i], FIX_DESCRIPTIONS[i]);
            }
            printf("\nStatus: %s\n", (st.st_size == expected) ? "loaded" : "SIZE MISMATCH");
            return EXIT_DONE;
        }
        printf("No trained model found at %s\n", weights_path);
        printf("Train with: ./ai_fix_data_gen > data.json && ./coretotch_fix train data.json %s\n", AI_FIX_WEIGHTS);
        return EXIT_FAILED;
    }

    if (strcmp(argv[1], CMD_REPORT) == 0) {
        char log_dir[MAX_BUF];
        safe_copy(log_dir, self->db_path, MAX_BUF);
        char *slash = strrchr(log_dir, '/');
        if (slash) slash[1] = '\0';
        else log_dir[0] = '\0';
        DbReport(&self->db, self->db_path, log_dir);
        return EXIT_DONE;
    }

    if (strcmp(argv[1], CMD_CLEAR_BLOCK) == 0) {
        int n = DbClear(&self->db, PAT_BLOCKED);
        printf("[OK] Cleared %d blocked patterns\n", n);
        return EXIT_DONE;
    }

    if (strcmp(argv[1], CMD_CLEAR_ALLOW) == 0) {
        int n = DbClear(&self->db, PAT_ALLOWED);
        printf("[OK] Cleared %d allowed patterns\n", n);
        return EXIT_DONE;
    }

    /* ── EXECUTION MODE ── */

    if (strcmp(argv[1], CMD_RUN) == 0) {
        /* Parse remaining args as run options + command */
        ParseArgs(argc - 1, argv + 1, &self->args);

        if (!ValidateStructure(self->args.command, self->args.force)) {
            printf("[STRUCTURE-BLOCKED] exit=%d time=0.00s\n", EXIT_BLOCKED);
            return EXIT_BLOCKED;
        }

        if (!ValidateCommand(&self->db, self->args.command, self->args.allow_dangerous)) {
            printf("[BLOCKED] exit=%d time=0.00s\n", EXIT_BLOCKED);
            return EXIT_BLOCKED;
        }

        if (self->args.dry_run) {
            PrintDryRun(&self->args);
            return EXIT_DONE;
        }

        self->result = RunWithRetry(&self->args);

        /* Log execution result for learning */
        char db_dir[MAX_BUF];
        safe_copy(db_dir, self->db_path, MAX_BUF);
        char *slash = strrchr(db_dir, '/');
        if (slash) slash[1] = '\0';
        else db_dir[0] = '\0';
        ExecLog(&self->result, &self->args, db_dir);

        if (self->args.json)
            PrintJson(&self->result, &self->args);
        else
            PrintResult(&self->result, &self->args);

        /* AI fix suggestion if enabled and error detected */
        if (self->args.ai_fix && !self->args.json &&
            self->result.state != ST_DONE && self->result.state != ST_BLOCKED &&
            self->result.stderr_len > 0) {
            AiFixSuggest(&self->result, db_dir);
        }

        int exit_map[] = {
            EXIT_DONE, EXIT_FAILED, EXIT_FAILED, EXIT_STUCK, EXIT_TIMEOUT,
            EXIT_FAILED, EXIT_DONE, EXIT_BLOCKED, EXIT_ERROR, EXIT_KILLED
        };
        int state_idx = self->result.state;
        if (state_idx < 0 || state_idx >= (int)(sizeof(exit_map) / sizeof(exit_map[0])))
            return EXIT_ERROR;
        return exit_map[state_idx];
    }

    /* ── VERSION / HELP ── */

    if (strcmp(argv[1], "--version") == 0 || strcmp(argv[1], "-v") == 0) {
        printf("cascade_cli v%s (CEK v5)\n", VERSION);
        return EXIT_DONE;
    }

    if (strcmp(argv[1], "--help") == 0 || strcmp(argv[1], "-h") == 0) {
        PrintHelp();
        return EXIT_DONE;
    }

    /* Unknown command */
    fprintf(stderr, "Unknown command: %s\n", argv[1]);
    PrintHelp();
    return EXIT_ERROR;
}

/* ════════════════════════════════════════════
 * MAIN ENTRY POINT
 * ════════════════════════════════════════════ */

int main(int argc, char **argv) {
    static CascadeCli cli;
    memset(&cli, 0, sizeof(cli));
    optind = 1;
    return Run(&cli, argc, argv);
}
