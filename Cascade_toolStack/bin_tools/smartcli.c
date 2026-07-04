/*
 * smartcli.c — VBStyle CliDomain in C
 *
 * This is NOT a router. This is a VBStyle domain controller.
 *
 * VBStyle constraints (enforced by design):
 *   - No decorators, no inheritance, no ABC
 *   - Run() returns Tuple3: (ok, data, err)
 *   - State dict holds all state
 *   - mem param is the inter-domain bus
 *   - Authorities nest inside the domain
 *   - No hardcoded paths (uses BIN_DIR from compile or config)
 *
 * Architecture:
 *
 *   CliDomain
 *     .state = { config, catalog, results, sessions }
 *     .Run(command, params) -> (ok, data, err)
 *     .RegistryAuthority  -- discovers, registers, lists tools
 *     .ExecAuthority       -- runs tools, captures results
 *     .ConfigAuthority     -- reads/writes config
 *
 * SQLite tables (baked in, like wcmd pattern):
 *   cli_command   -- tool registry (name, path, description, category, enabled)
 *   cli_result    -- execution results (stdout, stderr, exit_code, elapsed_ms, hash)
 *   cli_session   -- session tracking
 *   cli_config    -- key/value config store
 *
 * Compile:
 *   cc -O2 -o smartcli smartcli.c -lsqlite3
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>
#include <sys/wait.h>
#include <sys/stat.h>
#include <dirent.h>
#include <time.h>
#include <ctype.h>
#include <sqlite3.h>

/* VBSTYLE CONSTANTS */
#define BIN_DIR       "/Users/wws/bin"
#define CONFIG_DB     "/Users/wws/bin/.smartcli_config.db"
#define MAX_TOOLS     64
#define MAX_BUF       8192
#define MAX_BIGBUF    65536
#define MAX_NAME      256
#define MAX_PATH      1024
#define MAX_DESC      512

#define VB_OK     1
#define VB_FAIL   0

/* VBSTYLE DATA TYPES */

typedef struct {
    int    id;
    char   name[MAX_NAME];
    char   path[MAX_PATH];
    char   description[MAX_DESC];
    char   category[64];
    int    enabled;
} ToolEntry;

typedef struct {
    int    ok;
    char   stdout_text[MAX_BIGBUF];
    char   stderr_text[1024];
    int    exit_code;
    double elapsed_ms;
    char   result_hash[65];
    char   error[512];
} ExecResult;

typedef struct {
    int    id;
    char   label[256];
    char   started_at[64];
    char   summary[512];
} Session;

/* CliDomain state -- the "self.state" dict */
typedef struct {
    sqlite3    *db;
    ToolEntry   tools[MAX_TOOLS];
    int         tool_count;
    Session     session;
    int         session_active;
    char        config_bin_dir[MAX_PATH];
    char        config_mysql_host[128];
    char        config_mysql_user[128];
    char        config_mysql_pass[128];
    int         config_mysql_port;
    char        config_mysql_db[128];
} CliState;

/* SEED SQL */
static const char *SEED_SQL =
"CREATE TABLE IF NOT EXISTS cli_command ("
"  id INTEGER PRIMARY KEY AUTOINCREMENT,"
"  name TEXT UNIQUE NOT NULL,"
"  binary_path TEXT NOT NULL,"
"  description TEXT,"
"  category TEXT DEFAULT 'general',"
"  enabled INTEGER DEFAULT 1,"
"  created_at TEXT DEFAULT (datetime('now'))"
");"
"CREATE TABLE IF NOT EXISTS cli_result ("
"  id INTEGER PRIMARY KEY AUTOINCREMENT,"
"  command_name TEXT NOT NULL,"
"  args_text TEXT,"
"  stdout_text TEXT,"
"  stderr_text TEXT,"
"  exit_code INTEGER,"
"  elapsed_ms REAL,"
"  status TEXT,"
"  result_hash TEXT,"
"  created_at TEXT DEFAULT (datetime('now'))"
");"
"CREATE TABLE IF NOT EXISTS cli_session ("
"  id INTEGER PRIMARY KEY AUTOINCREMENT,"
"  label TEXT NOT NULL,"
"  started_at TEXT NOT NULL,"
"  ended_at TEXT,"
"  summary TEXT"
");"
"CREATE TABLE IF NOT EXISTS cli_config ("
"  key TEXT PRIMARY KEY,"
"  value TEXT"
");"
"INSERT OR IGNORE INTO cli_config (key, value) VALUES ('bin_dir', '" BIN_DIR "');"
"INSERT OR IGNORE INTO cli_config (key, value) VALUES ('mysql_host', 'localhost');"
"INSERT OR IGNORE INTO cli_config (key, value) VALUES ('mysql_user', 'root');"
"INSERT OR IGNORE INTO cli_config (key, value) VALUES ('mysql_pass', '');"
"INSERT OR IGNORE INTO cli_config (key, value) VALUES ('mysql_port', '3306');"
"INSERT OR IGNORE INTO cli_config (key, value) VALUES ('mysql_db', 'vb_shared');"
"INSERT OR IGNORE INTO cli_config (key, value) VALUES ('version', '1.0');"
;

/* UTILITY FUNCTIONS */

static void now_iso(char *buf, size_t sz) {
    time_t t = time(NULL);
    struct tm *tm = localtime(&t);
    strftime(buf, sz, "%Y-%m-%d %H:%M:%S", tm);
}

static void simple_hash(const char *input, char *out, size_t out_sz) {
    unsigned long long h = 1469598103934665603ULL;
    for (const char *p = input; *p; p++) {
        h ^= (unsigned char)*p;
        h *= 1099511628211ULL;
    }
    snprintf(out, out_sz, "%016llx", h);
}

static int is_executable_file(const char *path) {
    struct stat st;
    return stat(path, &st) == 0 && S_ISREG(st.st_mode) && access(path, X_OK) == 0;
}

static int is_python_file(const char *name) {
    const char *dot = strrchr(name, '.');
    return dot && strcmp(dot, ".py") == 0;
}

static void strip_extension(char *name) {
    char *dot = strrchr(name, '.');
    if (dot) *dot = '\0';
}

static const char *guess_category(const char *name) {
    if (strstr(name, "search") || strstr(name, "msearch")) return "database";
    if (strstr(name, "vbcheck") || strstr(name, "enforce")) return "validation";
    if (strstr(name, "ghost")) return "maintenance";
    if (strstr(name, "wcmd") || strstr(name, "cmd")) return "shell";
    if (strstr(name, "dir")) return "shell";
    if (strstr(name, "miner") || strstr(name, "analyzer")) return "analysis";
    if (strstr(name, "ingest")) return "ingestion";
    if (strstr(name, "monitor") || strstr(name, "test")) return "testing";
    return "auto";
}

static const char *guess_description(const char *name) {
    if (strstr(name, "search") || strstr(name, "msearch")) return "MySQL search tool";
    if (strstr(name, "vbcheck")) return "VBStyle enforcer";
    if (strstr(name, "ghost")) return "Ghost maintenance tool";
    if (strstr(name, "wcmd")) return "Windows-style command VM";
    if (strstr(name, "dir")) return "Directory listing tool";
    if (strstr(name, "miner")) return "Chat miner tool";
    if (strstr(name, "analyzer")) return "Analysis tool";
    if (strstr(name, "ingest")) return "Ingestion tool";
    return "Auto-discovered tool";
}

/* REGISTRY AUTHORITY -- discovers, registers, loads tools */

static int registry_scan_dir(CliState *state) {
    DIR *d = opendir(state->config_bin_dir);
    if (!d) return 0;

    int new_count = 0;
    struct dirent *entry;

    while ((entry = readdir(d))) {
        if (entry->d_name[0] == '.') continue;

        const char *dot = strrchr(entry->d_name, '.');
        if (dot && (strcmp(dot, ".c") == 0 || strcmp(dot, ".h") == 0 ||
                    strcmp(dot, ".o") == 0 || strcmp(dot, ".db") == 0))
            continue;

        if (strcmp(entry->d_name, "smartcli") == 0) continue;

        char filepath[MAX_PATH];
        snprintf(filepath, sizeof(filepath), "%s/%s", state->config_bin_dir, entry->d_name);

        if (!is_executable_file(filepath) && !is_python_file(entry->d_name))
            continue;

        char tool_name[MAX_NAME];
        strncpy(tool_name, entry->d_name, sizeof(tool_name) - 1);
        tool_name[sizeof(tool_name) - 1] = '\0';
        strip_extension(tool_name);

        sqlite3_stmt *stmt;
        const char *sql = "SELECT COUNT(*) FROM cli_command WHERE name=?";
        if (sqlite3_prepare_v2(state->db, sql, -1, &stmt, NULL) != SQLITE_OK) continue;
        sqlite3_bind_text(stmt, 1, tool_name, -1, SQLITE_STATIC);
        int exists = 0;
        if (sqlite3_step(stmt) == SQLITE_ROW) exists = sqlite3_column_int(stmt, 0);
        sqlite3_finalize(stmt);

        if (exists > 0) continue;

        const char *cat = guess_category(tool_name);
        const char *desc = guess_description(tool_name);

        sql = "INSERT OR IGNORE INTO cli_command (name, binary_path, description, category) VALUES (?,?,?,?)";
        if (sqlite3_prepare_v2(state->db, sql, -1, &stmt, NULL) == SQLITE_OK) {
            sqlite3_bind_text(stmt, 1, tool_name, -1, SQLITE_STATIC);
            sqlite3_bind_text(stmt, 2, filepath, -1, SQLITE_STATIC);
            sqlite3_bind_text(stmt, 3, desc, -1, SQLITE_STATIC);
            sqlite3_bind_text(stmt, 4, cat, -1, SQLITE_STATIC);
            sqlite3_step(stmt);
            sqlite3_finalize(stmt);
            new_count++;
        }
    }

    closedir(d);
    return new_count;
}

static int registry_load(CliState *state) {
    sqlite3_stmt *stmt;
    const char *sql = "SELECT id, name, binary_path, description, category, enabled "
                      "FROM cli_command WHERE enabled=1 ORDER BY category, name";
    if (sqlite3_prepare_v2(state->db, sql, -1, &stmt, NULL) != SQLITE_OK) return 0;

    state->tool_count = 0;
    while (sqlite3_step(stmt) == SQLITE_ROW && state->tool_count < MAX_TOOLS) {
        ToolEntry *t = &state->tools[state->tool_count];
        t->id = sqlite3_column_int(stmt, 0);
        strncpy(t->name, (const char *)sqlite3_column_text(stmt, 1), MAX_NAME - 1);
        t->name[MAX_NAME - 1] = '\0';
        strncpy(t->path, (const char *)sqlite3_column_text(stmt, 2), MAX_PATH - 1);
        t->path[MAX_PATH - 1] = '\0';
        const char *desc = (const char *)sqlite3_column_text(stmt, 3);
        if (desc) { strncpy(t->description, desc, MAX_DESC - 1); t->description[MAX_DESC - 1] = '\0'; }
        const char *cat = (const char *)sqlite3_column_text(stmt, 4);
        if (cat) { strncpy(t->category, cat, 63); t->category[63] = '\0'; }
        t->enabled = sqlite3_column_int(stmt, 5);
        state->tool_count++;
    }
    sqlite3_finalize(stmt);
    return state->tool_count;
}

static int registry_find(CliState *state, const char *name) {
    for (int i = 0; i < state->tool_count; i++) {
        if (strcasecmp(state->tools[i].name, name) == 0)
            return i;
    }
    return -1;
}

static int registry_add(CliState *state, const char *name, const char *path, const char *desc, const char *cat) {
    sqlite3_stmt *stmt;
    const char *sql = "INSERT OR REPLACE INTO cli_command (name, binary_path, description, category) VALUES (?,?,?,?)";
    if (sqlite3_prepare_v2(state->db, sql, -1, &stmt, NULL) != SQLITE_OK) return VB_FAIL;
    sqlite3_bind_text(stmt, 1, name, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, path, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 3, desc ? desc : "Manual registration", -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 4, cat ? cat : "manual", -1, SQLITE_STATIC);
    int ok = (sqlite3_step(stmt) == SQLITE_DONE);
    sqlite3_finalize(stmt);
    return ok ? VB_OK : VB_FAIL;
}

static int registry_remove(CliState *state, const char *name) {
    sqlite3_stmt *stmt;
    const char *sql = "UPDATE cli_command SET enabled=0 WHERE name=?";
    if (sqlite3_prepare_v2(state->db, sql, -1, &stmt, NULL) != SQLITE_OK) return VB_FAIL;
    sqlite3_bind_text(stmt, 1, name, -1, SQLITE_STATIC);
    int ok = (sqlite3_step(stmt) == SQLITE_DONE);
    sqlite3_finalize(stmt);
    return ok ? VB_OK : VB_FAIL;
}

/* EXEC AUTHORITY -- runs a tool, captures result, stores in cli_result */

static int exec_run_tool(CliState *state, int tool_idx, int argc, char **argv, ExecResult *result) {
    ToolEntry *tool = &state->tools[tool_idx];
    memset(result, 0, sizeof(ExecResult));

    int new_argc = argc - 1;
    char **new_argv = malloc(sizeof(char *) * (new_argc + 1));
    new_argv[0] = tool->path;
    for (int i = 2; i < argc; i++)
        new_argv[i - 1] = argv[i];
    new_argv[new_argc - 1] = NULL;

    int pipefd[2];
    if (pipe(pipefd) != 0) {
        result->ok = VB_FAIL;
        strcpy(result->error, "Failed to create pipe");
        free(new_argv);
        return VB_FAIL;
    }

    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);

    pid_t pid = fork();
    if (pid == 0) {
        close(pipefd[0]);
        dup2(pipefd[1], STDOUT_FILENO);
        dup2(pipefd[1], STDERR_FILENO);
        close(pipefd[1]);

        if (is_python_file(tool->path)) {
            char **py_argv = malloc(sizeof(char *) * (new_argc + 2));
            py_argv[0] = "python3";
            py_argv[1] = tool->path;
            for (int i = 1; i < new_argc; i++)
                py_argv[i + 1] = new_argv[i];
            py_argv[new_argc + 1] = NULL;
            execvp("python3", py_argv);
            perror("execvp python3");
            _exit(127);
        }

        execvp(tool->path, new_argv);
        perror("execvp");
        _exit(127);
    }

    close(pipefd[1]);

    ssize_t n;
    size_t total = 0;
    while ((n = read(pipefd[0], result->stdout_text + total, MAX_BIGBUF - total - 1)) > 0) {
        total += n;
    }
    result->stdout_text[total] = '\0';
    close(pipefd[0]);

    int status;
    waitpid(pid, &status, 0);
    result->exit_code = WIFEXITED(status) ? WEXITSTATUS(status) : -1;

    clock_gettime(CLOCK_MONOTONIC, &t1);
    result->elapsed_ms = (t1.tv_sec - t0.tv_sec) * 1000.0 + (t1.tv_nsec - t0.tv_nsec) / 1000000.0;

    simple_hash(result->stdout_text, result->result_hash, sizeof(result->result_hash));
    result->ok = (result->exit_code == 0) ? VB_OK : VB_FAIL;

    /* Store result in SQLite */
    sqlite3_stmt *stmt;
    const char *sql = "INSERT INTO cli_result (command_name, args_text, stdout_text, stderr_text, "
                      "exit_code, elapsed_ms, status, result_hash) VALUES (?,?,?,?,?,?,?,?)";
    if (sqlite3_prepare_v2(state->db, sql, -1, &stmt, NULL) == SQLITE_OK) {
        sqlite3_bind_text(stmt, 1, tool->name, -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 2, "", -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 3, result->stdout_text, -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 4, result->stderr_text, -1, SQLITE_STATIC);
        sqlite3_bind_int(stmt, 5, result->exit_code);
        sqlite3_bind_double(stmt, 6, result->elapsed_ms);
        sqlite3_bind_text(stmt, 7, result->ok ? "ok" : "fail", -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 8, result->result_hash, -1, SQLITE_STATIC);
        sqlite3_step(stmt);
        sqlite3_finalize(stmt);
    }

    free(new_argv);
    return result->ok;
}

/* CONFIG AUTHORITY */

static void config_load(CliState *state) {
    sqlite3_stmt *stmt;
    const char *sql = "SELECT key, value FROM cli_config";
    if (sqlite3_prepare_v2(state->db, sql, -1, &stmt, NULL) != SQLITE_OK) return;

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        const char *key = (const char *)sqlite3_column_text(stmt, 0);
        const char *val = (const char *)sqlite3_column_text(stmt, 1);
        if (!key || !val) continue;

        if (strcmp(key, "bin_dir") == 0) strncpy(state->config_bin_dir, val, MAX_PATH - 1);
        else if (strcmp(key, "mysql_host") == 0) strncpy(state->config_mysql_host, val, 127);
        else if (strcmp(key, "mysql_user") == 0) strncpy(state->config_mysql_user, val, 127);
        else if (strcmp(key, "mysql_pass") == 0) strncpy(state->config_mysql_pass, val, 127);
        else if (strcmp(key, "mysql_port") == 0) state->config_mysql_port = atoi(val);
        else if (strcmp(key, "mysql_db") == 0) strncpy(state->config_mysql_db, val, 127);
    }
    sqlite3_finalize(stmt);
}

static int config_set(CliState *state, const char *key, const char *value) {
    sqlite3_stmt *stmt;
    const char *sql = "INSERT OR REPLACE INTO cli_config (key, value) VALUES (?,?)";
    if (sqlite3_prepare_v2(state->db, sql, -1, &stmt, NULL) != SQLITE_OK) return VB_FAIL;
    sqlite3_bind_text(stmt, 1, key, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, value, -1, SQLITE_STATIC);
    int ok = (sqlite3_step(stmt) == SQLITE_DONE);
    sqlite3_finalize(stmt);
    return ok ? VB_OK : VB_FAIL;
}

/* SESSION AUTHORITY */

static int session_open(CliState *state, const char *label) {
    char now[64];
    now_iso(now, sizeof(now));

    sqlite3_stmt *stmt;
    const char *sql = "INSERT INTO cli_session (label, started_at) VALUES (?,?)";
    if (sqlite3_prepare_v2(state->db, sql, -1, &stmt, NULL) != SQLITE_OK) return VB_FAIL;
    sqlite3_bind_text(stmt, 1, label, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, now, -1, SQLITE_STATIC);
    int ok = (sqlite3_step(stmt) == SQLITE_DONE);
    if (ok) state->session.id = sqlite3_last_insert_rowid(state->db);
    sqlite3_finalize(stmt);

    if (ok) {
        strncpy(state->session.label, label, 255);
        strncpy(state->session.started_at, now, 63);
        state->session_active = 1;
        return VB_OK;
    }
    return VB_FAIL;
}

static int session_close(CliState *state, const char *summary) {
    if (!state->session_active) return VB_FAIL;

    char now[64];
    now_iso(now, sizeof(now));

    sqlite3_stmt *stmt;
    const char *sql = "UPDATE cli_session SET ended_at=?, summary=? WHERE id=?";
    if (sqlite3_prepare_v2(state->db, sql, -1, &stmt, NULL) != SQLITE_OK) return VB_FAIL;
    sqlite3_bind_text(stmt, 1, now, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, summary, -1, SQLITE_STATIC);
    sqlite3_bind_int(stmt, 3, state->session.id);
    int ok = (sqlite3_step(stmt) == SQLITE_DONE);
    sqlite3_finalize(stmt);

    state->session_active = 0;
    return ok ? VB_OK : VB_FAIL;
}

/* CLIDOMAIN BUILT-IN COMMANDS */

static void cmd_list(CliState *state) {
    printf("=== CLIDOMAIN -- Registered Tools ===\n\n");
    printf("  %-14s %-14s %s\n", "COMMAND", "CATEGORY", "DESCRIPTION");
    printf("  %-14s %-14s %s\n", "-------", "--------", "-----------");

    for (int i = 0; i < state->tool_count; i++) {
        printf("  %-14s %-14s %s\n",
            state->tools[i].name,
            state->tools[i].category,
            state->tools[i].description);
    }

    printf("\n  %d tools registered.\n", state->tool_count);
    printf("  Usage: smartcli <command> [args...]\n");
    printf("  Built-in: list, help, config, add, remove, scan, history, session\n");
}

static void cmd_config(CliState *state) {
    printf("=== CLIDOMAIN -- Configuration ===\n\n");
    printf("  %-16s %s\n", "KEY", "VALUE");
    printf("  %-16s %s\n", "---", "-----");

    sqlite3_stmt *stmt;
    const char *sql = "SELECT key, value FROM cli_config ORDER BY key";
    if (sqlite3_prepare_v2(state->db, sql, -1, &stmt, NULL) != SQLITE_OK) return;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        printf("  %-16s %s\n",
            (const char *)sqlite3_column_text(stmt, 0),
            (const char *)sqlite3_column_text(stmt, 1));
    }
    sqlite3_finalize(stmt);
    printf("\n  Config DB: %s\n", CONFIG_DB);
}

static void cmd_history(CliState *state, int limit) {
    printf("=== CLIDOMAIN -- Execution History ===\n\n");

    sqlite3_stmt *stmt;
    char sql[256];
    snprintf(sql, sizeof(sql),
        "SELECT command_name, status, exit_code, elapsed_ms, result_hash, created_at "
        "FROM cli_result ORDER BY id DESC LIMIT %d", limit);
    if (sqlite3_prepare_v2(state->db, sql, -1, &stmt, NULL) != SQLITE_OK) return;

    printf("  %-14s %-8s %-6s %-10s %s\n", "COMMAND", "STATUS", "EXIT", "ELAPSED", "WHEN");
    printf("  %-14s %-8s %-6s %-10s %s\n", "-------", "------", "----", "-------", "-----");

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        printf("  %-14s %-8s %-6d %-10.1f %s\n",
            (const char *)sqlite3_column_text(stmt, 0),
            (const char *)sqlite3_column_text(stmt, 1),
            sqlite3_column_int(stmt, 2),
            sqlite3_column_double(stmt, 3),
            (const char *)sqlite3_column_text(stmt, 5));
    }
    sqlite3_finalize(stmt);
}

static void cmd_help(void) {
    printf("smartcli -- VBStyle CliDomain v1.0\n\n");
    printf("Usage: smartcli <command> [args...]\n\n");
    printf("Built-in commands:\n");
    printf("  list              Show all registered tools\n");
    printf("  scan              Auto-discover new tools in bin dir\n");
    printf("  config            Show configuration\n");
    printf("  config <k> <v>    Set a config value\n");
    printf("  add <name> <path> Register a new tool\n");
    printf("  remove <name>     Disable a tool\n");
    printf("  history [N]       Show last N execution results\n");
    printf("  session <label>   Open a named session\n");
    printf("  help              Show this help\n");
    printf("\nTool commands:\n");
    printf("  <tool> [args...]  Execute a registered tool\n");
    printf("\nVBStyle: every execution is captured in cli_result with hash.\n");
}

/* CLIDOMAIN INIT -- like __init__(self, mem, db, param) */

static int cli_init(CliState *state) {
    memset(state, 0, sizeof(CliState));

    if (sqlite3_open(CONFIG_DB, &state->db) != SQLITE_OK) {
        fprintf(stderr, "Cannot open config database: %s\n", CONFIG_DB);
        return VB_FAIL;
    }

    sqlite3_exec(state->db, SEED_SQL, NULL, NULL, NULL);
    config_load(state);
    registry_scan_dir(state);
    registry_load(state);

    return VB_OK;
}

static void cli_shutdown(CliState *state) {
    if (state->session_active) {
        char summary[512];
        snprintf(summary, sizeof(summary), "Session ended: %d tools registered",
                 state->tool_count);
        session_close(state, summary);
    }
    if (state->db) sqlite3_close(state->db);
}

/* MAIN -- CliDomain.Run() entry point */

int main(int argc, char **argv) {
    if (argc < 2) {
        cmd_help();
        return 1;
    }

    CliState state;
    if (cli_init(&state) != VB_OK) return 1;

    const char *command = argv[1];

    if (strcmp(command, "list") == 0) {
        cmd_list(&state);
        cli_shutdown(&state);
        return 0;
    }

    if (strcmp(command, "help") == 0) {
        cmd_help();
        cli_shutdown(&state);
        return 0;
    }

    if (strcmp(command, "config") == 0) {
        if (argc >= 4) {
            config_set(&state, argv[2], argv[3]);
            printf("Set %s = %s\n", argv[2], argv[3]);
        } else {
            cmd_config(&state);
        }
        cli_shutdown(&state);
        return 0;
    }

    if (strcmp(command, "scan") == 0) {
        int n = registry_scan_dir(&state);
        registry_load(&state);
        printf("Discovered %d new tools. Total: %d\n", n, state.tool_count);
        cli_shutdown(&state);
        return 0;
    }

    if (strcmp(command, "add") == 0) {
        if (argc < 4) {
            fprintf(stderr, "Usage: smartcli add <name> <path> [description]\n");
            cli_shutdown(&state);
            return 1;
        }
        const char *desc = argc > 4 ? argv[4] : "Manual registration";
        int ok = registry_add(&state, argv[2], argv[3], desc, "manual");
        printf("%s: %s -> %s\n", ok ? "Added" : "Failed", argv[2], argv[3]);
        cli_shutdown(&state);
        return ok ? 0 : 1;
    }

    if (strcmp(command, "remove") == 0) {
        if (argc < 3) {
            fprintf(stderr, "Usage: smartcli remove <name>\n");
            cli_shutdown(&state);
            return 1;
        }
        int ok = registry_remove(&state, argv[2]);
        printf("%s: %s\n", ok ? "Disabled" : "Failed", argv[2]);
        cli_shutdown(&state);
        return ok ? 0 : 1;
    }

    if (strcmp(command, "history") == 0) {
        int limit = argc > 2 ? atoi(argv[2]) : 10;
        cmd_history(&state, limit);
        cli_shutdown(&state);
        return 0;
    }

    if (strcmp(command, "session") == 0) {
        if (argc < 3) {
            fprintf(stderr, "Usage: smartcli session <label>\n");
            cli_shutdown(&state);
            return 1;
        }
        session_open(&state, argv[2]);
        printf("Session opened: %s\n", argv[2]);
        cli_shutdown(&state);
        return 0;
    }

    /* Tool routing -- find tool in registry and execute */
    int tool_idx = registry_find(&state, command);
    if (tool_idx < 0) {
        fprintf(stderr, "Unknown command: '%s'\n", command);
        fprintf(stderr, "Run 'smartcli list' to see available commands.\n");
        cli_shutdown(&state);
        return 1;
    }

    /* Open a session for this execution */
    char session_label[300];
    snprintf(session_label, sizeof(session_label), "exec:%s", command);
    session_open(&state, session_label);

    /* Execute the tool and capture result */
    ExecResult result;
    exec_run_tool(&state, tool_idx, argc, argv, &result);

    /* Print captured output */
    if (result.stdout_text[0]) {
        printf("%s", result.stdout_text);
    }

    /* Close session with summary */
    char summary[512];
    snprintf(summary, sizeof(summary), "Executed %s: exit=%d elapsed=%.1fms hash=%s",
             command, result.exit_code, result.elapsed_ms, result.result_hash);
    session_close(&state, summary);

    cli_shutdown(&state);
    return result.exit_code;
}
