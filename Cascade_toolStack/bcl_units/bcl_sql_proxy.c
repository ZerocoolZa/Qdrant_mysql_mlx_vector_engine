//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_sql_proxy.c" date="2026-07-04" author="Devin" session_id="bnd-laws" context="C SQL proxy — SQLite backend, JSON output, destruction_guard, Run() dispatch"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch no-print-to-stdout-except-JSON"}
//[@FILEID]{id="bcl_sql_proxy.c" domain="bcl_c_engine" authority="BclSqlProxy"}
//[@SUMMARY]{summary="C SQL proxy backed by SQLite. Accepts SQL queries via CLI, returns JSON. Destruction guard blocks DROP/DELETE/TRUNCATE/ALTER without --confirm. Run() dispatch matches BCL_UNIT pattern."}
//[@CLASS]{class="BclSqlProxy" domain="bcl_c_engine" authority="single"}
//[@METHOD]{methods="Run,cmd_query,cmd_schema,cmd_tables,cmd_import,cmd_export,destruction_guard,json_escape,json_value"}

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sqlite3.h>
#include <ctype.h>

// ═══════════════════════════════════════════
// UPPERCASE CONSTANTS
// ═══════════════════════════════════════════

#define MAX_SQL 65536
#define MAX_ROWS 10000
#define MAX_COLS 64
#define MAX_VAL 8192
#define MAX_ERR 1024
#define MAX_PATH 4096

#define OK 1
#define FAIL 0

#define ERR_NONE 0
#define ERR_DESTRUCTIVE 1
#define ERR_SQL 2
#define ERR_ARGS 3
#define ERR_FILE 4
#define ERR_MEMORY 5

// Destructive keywords — blocked without --confirm
static const char *DESTRUCTIVE_KEYWORDS[] = {
    "DROP", "DELETE", "TRUNCATE", "ALTER", "ATTACH", "DETACH",
    "VACUUM", "PRAGMA", "REINDEX", NULL
};

// ═══════════════════════════════════════════
// STATE STRUCTURE (VBStyle: self.state dict)
// ═══════════════════════════════════════════

typedef struct {
    char dbPath[MAX_PATH];
    char sql[MAX_SQL];
    char output[MAX_VAL * 4];
    char error[MAX_ERR];
    int  errorCode;
    int  confirm;
    int  jsonOutput;
    int  limit;
    int  rowCount;
    int  colCount;
} ProxyState;

// ═══════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════

static void StateInit(ProxyState *s) {
    memset(s, 0, sizeof(ProxyState));
    s->confirm = 0;
    s->jsonOutput = 1;
    s->limit = MAX_ROWS;
    s->errorCode = ERR_NONE;
}

static int IsDestructive(const char *sql) {
    char upper[MAX_SQL];
    int i;
    size_t len = strlen(sql);
    if (len >= MAX_SQL) len = MAX_SQL - 1;
    for (i = 0; i < (int)len; i++) {
        upper[i] = (char)toupper((unsigned char)sql[i]);
    }
    upper[len] = '\0';

    for (i = 0; DESTRUCTIVE_KEYWORDS[i] != NULL; i++) {
        if (strstr(upper, DESTRUCTIVE_KEYWORDS[i]) != NULL) {
            return 1;
        }
    }
    return 0;
}

static void JsonEscape(char *dst, size_t dstSize, const char *src) {
    size_t i = 0;
    size_t j = 0;
    if (!src) {
        if (dstSize > 4) { dst[0]='n'; dst[1]='u'; dst[2]='l'; dst[3]='l'; dst[4]='\0'; }
        return;
    }
    while (src[i] && j < dstSize - 2) {
        unsigned char c = (unsigned char)src[i];
        if (c == '"' ) { if (j + 2 < dstSize) { dst[j++]='\\'; dst[j++]='"'; } }
        else if (c == '\\') { if (j + 2 < dstSize) { dst[j++]='\\'; dst[j++]='\\'; } }
        else if (c == '\n') { if (j + 2 < dstSize) { dst[j++]='\\'; dst[j++]='n'; } }
        else if (c == '\r') { if (j + 2 < dstSize) { dst[j++]='\\'; dst[j++]='r'; } }
        else if (c == '\t') { if (j + 2 < dstSize) { dst[j++]='\\'; dst[j++]='t'; } }
        else if (c < 32) {
            if (j + 6 < dstSize) {
                j += snprintf(dst + j, dstSize - j, "\\u%04x", c);
            }
        } else {
            dst[j++] = (char)c;
        }
        i++;
    }
    dst[j] = '\0';
}

static const char* JsonType(int sqliteType) {
    switch (sqliteType) {
        case SQLITE_INTEGER: return "integer";
        case SQLITE_FLOAT:   return "real";
        case SQLITE_TEXT:    return "text";
        case SQLITE_BLOB:    return "blob";
        case SQLITE_NULL:    return "null";
        default:             return "text";
    }
}

// ═══════════════════════════════════════════
// DESTRUCTION GUARD
// ═══════════════════════════════════════════

// Returns OK (1) if allowed, FAIL (0) if blocked.
// Sets error in state if blocked.
static int DestructionGuard(ProxyState *s, const char *sql) {
    if (!IsDestructive(sql)) return OK;

    if (!s->confirm) {
        snprintf(s->error, MAX_ERR,
            "DESTRUCTION_GUARD: blocked destructive SQL (requires --confirm): %s",
            sql);
        s->errorCode = ERR_DESTRUCTIVE;
        return FAIL;
    }
    return OK;
}

// ═══════════════════════════════════════════
// COMMAND: query
// ═══════════════════════════════════════════

static int CmdQuery(ProxyState *s) {
    sqlite3 *db;
    sqlite3_stmt *stmt;
    int rc;
    int colCount;
    int rowCount;
    int i;
    char *pos;
    char escaped[MAX_VAL];

    if (!s->dbPath[0]) {
        snprintf(s->error, MAX_ERR, "no database path specified (--db)");
        s->errorCode = ERR_ARGS;
        return FAIL;
    }
    if (!s->sql[0]) {
        snprintf(s->error, MAX_ERR, "no SQL specified (--query or --sql)");
        s->errorCode = ERR_ARGS;
        return FAIL;
    }

    // Destruction guard
    if (!DestructionGuard(s, s->sql)) {
        return FAIL;
    }

    rc = sqlite3_open_v2(s->dbPath, &db, SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE, NULL);
    if (rc != SQLITE_OK) {
        snprintf(s->error, MAX_ERR, "cannot open db '%s': %s", s->dbPath, sqlite3_errmsg(db));
        s->errorCode = ERR_FILE;
        sqlite3_close(db);
        return FAIL;
    }

    rc = sqlite3_prepare_v2(db, s->sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        snprintf(s->error, MAX_ERR, "SQL error: %s", sqlite3_errmsg(db));
        s->errorCode = ERR_SQL;
        sqlite3_close(db);
        return FAIL;
    }

    colCount = sqlite3_column_count(stmt);
    if (colCount > MAX_COLS) colCount = MAX_COLS;
    s->colCount = colCount;

    // Build JSON output
    pos = s->output;
    pos += snprintf(pos, sizeof(s->output) - (pos - s->output),
        "{\"ok\":true,\"columns\":[");
    for (i = 0; i < colCount; i++) {
        const char *colName = sqlite3_column_name(stmt, i);
        JsonEscape(escaped, MAX_VAL, colName);
        pos += snprintf(pos, sizeof(s->output) - (pos - s->output),
            "%s{\"name\":\"%s\",\"type\":\"%s\"}",
            (i > 0) ? "," : "",
            escaped,
            JsonType(sqlite3_column_type(stmt, i)));
    }
    pos += snprintf(pos, sizeof(s->output) - (pos - s->output),
        "],\"rows\":[");

    rowCount = 0;
    while (sqlite3_step(stmt) == SQLITE_ROW && rowCount < s->limit) {
        if (rowCount > 0) {
            pos += snprintf(pos, sizeof(s->output) - (pos - s->output), ",");
        }
        pos += snprintf(pos, sizeof(s->output) - (pos - s->output), "[");
        for (i = 0; i < colCount; i++) {
            const unsigned char *val = sqlite3_column_text(stmt, i);
            int valType = sqlite3_column_type(stmt, i);
            if (i > 0) {
                pos += snprintf(pos, sizeof(s->output) - (pos - s->output), ",");
            }
            if (valType == SQLITE_NULL) {
                pos += snprintf(pos, sizeof(s->output) - (pos - s->output), "null");
            } else if (valType == SQLITE_INTEGER || valType == SQLITE_FLOAT) {
                const char *txt = (const char *)sqlite3_column_text(stmt, i);
                JsonEscape(escaped, MAX_VAL, txt);
                pos += snprintf(pos, sizeof(s->output) - (pos - s->output), "%s", escaped);
            } else {
                JsonEscape(escaped, MAX_VAL, (const char *)val);
                pos += snprintf(pos, sizeof(s->output) - (pos - s->output), "\"%s\"", escaped);
            }
        }
        pos += snprintf(pos, sizeof(s->output) - (pos - s->output), "]");
        rowCount++;
    }
    pos += snprintf(pos, sizeof(s->output) - (pos - s->output),
        "],\"rowCount\":%d}", rowCount);

    s->rowCount = rowCount;
    sqlite3_finalize(stmt);
    sqlite3_close(db);
    return OK;
}

// ═══════════════════════════════════════════
// COMMAND: tables
// ═══════════════════════════════════════════

static int CmdTables(ProxyState *s) {
    strncpy(s->sql,
        "SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY type, name",
        MAX_SQL - 1);
    s->sql[MAX_SQL - 1] = '\0';
    return CmdQuery(s);
}

// ═══════════════════════════════════════════
// COMMAND: schema
// ═══════════════════════════════════════════

static int CmdSchema(ProxyState *s) {
    strncpy(s->sql,
        "SELECT type, name, sql FROM sqlite_master WHERE type IN ('table','view','index') ORDER BY type, name",
        MAX_SQL - 1);
    s->sql[MAX_SQL - 1] = '\0';
    return CmdQuery(s);
}

// ═══════════════════════════════════════════
// RUN DISPATCH (VBStyle)
// ═══════════════════════════════════════════

// Returns Tuple3-like: (ok, output, error)
// ok=1 → output valid
// ok=0 → error valid
static int Run(ProxyState *s, const char *command) {
    if (strcmp(command, "query") == 0) {
        return CmdQuery(s);
    }
    if (strcmp(command, "tables") == 0) {
        return CmdTables(s);
    }
    if (strcmp(command, "schema") == 0) {
        return CmdSchema(s);
    }
    snprintf(s->error, MAX_ERR, "unknown command: %s (use: query, tables, schema)", command);
    s->errorCode = ERR_ARGS;
    return FAIL;
}

// ═══════════════════════════════════════════
// CLI ENTRY POINT
// ═══════════════════════════════════════════

static void PrintUsage(const char *prog) {
    fprintf(stderr,
        "bcl_sql_proxy — SQLite-backed SQL proxy with destruction guard\n\n"
        "Usage:\n"
        "  %s --db PATH --query \"SQL\"          Run SQL query, output JSON\n"
        "  %s --db PATH --tables                List all tables\n"
        "  %s --db PATH --schema                Show schema (CREATE statements)\n"
        "  %s --db PATH --query \"SQL\" --confirm Allow destructive SQL (DROP/DELETE/etc)\n"
        "  %s --db PATH --query \"SQL\" --limit N Limit rows (default 10000)\n"
        "\n"
        "Destruction guard blocks: DROP, DELETE, TRUNCATE, ALTER, ATTACH, DETACH, VACUUM, PRAGMA, REINDEX\n"
        "Use --confirm to override.\n"
        "\n"
        "Output: JSON to stdout, errors to stderr.\n"
        "Exit code: 0=ok, 1=error, 2=destructive_blocked\n",
        prog, prog, prog, prog, prog);
}

int main(int argc, char **argv) {
    ProxyState state;
    StateInit(&state);

    const char *command = "query";
    int i;

    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--db") == 0 && i + 1 < argc) {
            strncpy(state.dbPath, argv[++i], MAX_PATH - 1);
        } else if (strcmp(argv[i], "--query") == 0 && i + 1 < argc) {
            strncpy(state.sql, argv[++i], MAX_SQL - 1);
            command = "query";
        } else if (strcmp(argv[i], "--sql") == 0 && i + 1 < argc) {
            strncpy(state.sql, argv[++i], MAX_SQL - 1);
            command = "query";
        } else if (strcmp(argv[i], "--tables") == 0) {
            command = "tables";
        } else if (strcmp(argv[i], "--schema") == 0) {
            command = "schema";
        } else if (strcmp(argv[i], "--confirm") == 0) {
            state.confirm = 1;
        } else if (strcmp(argv[i], "--limit") == 0 && i + 1 < argc) {
            state.limit = atoi(argv[++i]);
            if (state.limit <= 0) state.limit = MAX_ROWS;
        } else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            PrintUsage(argv[0]);
            return 0;
        } else {
            fprintf(stderr, "unknown arg: %s (use --help)\n", argv[i]);
            return 1;
        }
    }

    if (!state.dbPath[0]) {
        fprintf(stderr, "ERROR: --db PATH is required\n");
        PrintUsage(argv[0]);
        return 1;
    }

    int ok = Run(&state, command);

    if (ok) {
        // JSON to stdout
        printf("%s\n", state.output);
        return 0;
    } else {
        // Error JSON to stderr
        char escapedErr[MAX_ERR];
        JsonEscape(escapedErr, MAX_ERR, state.error);
        if (state.errorCode == ERR_DESTRUCTIVE) {
            fprintf(stderr, "{\"ok\":false,\"error\":\"%s\",\"code\":%d}\n",
                escapedErr, state.errorCode);
            return 2;
        }
        fprintf(stderr, "{\"ok\":false,\"error\":\"%s\",\"code\":%d}\n",
            escapedErr, state.errorCode);
        return 1;
    }
}
