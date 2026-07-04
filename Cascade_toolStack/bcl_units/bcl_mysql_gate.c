//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_mysql_gate.c" date="2026-07-04" author="Devin" session_id="bnd-laws" context="C MySQL gateway — prepared statements only, destruction guard, TCP server + CLI"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Run dispatch no-raw-SQL-concatenation"}
//[@FILEID]{id="bcl_mysql_gate.c" domain="bcl_c_engine" authority="BclMysqlGate"}
//[@SUMMARY]{summary="C MySQL gateway/firewall. Enforces prepared statements for ALL queries. Destruction guard blocks DROP/DELETE/TRUNCATE/ALTER without confirm. TCP server mode + CLI mode. The only door into MySQL."}
//[@CLASS]{class="BclMysqlGate" domain="bcl_c_engine" authority="single"}
//[@METHOD]{methods="Run,cmd_query,cmd_tables,cmd_schema,cmd_ping,cmd_status,destruction_guard,stmt_execute,json_escape,json_value,server_loop,handle_client"}

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <mysql.h>
#include <ctype.h>
#include <errno.h>
#include <stdbool.h>

// ═══════════════════════════════════════════
// UPPERCASE CONSTANTS
// ═══════════════════════════════════════════

#define MAX_SQL 65536
#define MAX_ROWS 10000
#define MAX_COLS 64
#define MAX_VAL 65536
#define MAX_ERR 2048
#define MAX_PATH 4096
#define MAX_PARAMS 32
#define MAX_PARAM_LEN 4096
#define MAX_REQUEST 131072
#define MAX_RESPONSE 1048576
#define DEFAULT_PORT 3307
#define BACKLOG 16

#define OK 1
#define FAIL 0

#define ERR_NONE 0
#define ERR_DESTRUCTIVE 1
#define ERR_SQL 2
#define ERR_ARGS 3
#define ERR_CONN 4
#define ERR_MEMORY 5
#define ERR_JSON 6
#define ERR_PARAM 7

#define MYSQL_HOST "localhost"
#define MYSQL_USER "root"
#define MYSQL_PASSWORD ""
#define MYSQL_PORT 3306

// Destructive keywords — blocked without confirm
static const char *DESTRUCTIVE_KEYWORDS[] = {
    "DROP", "DELETE", "TRUNCATE", "ALTER", "GRANT", "REVOKE",
    "CREATE USER", "DROP USER", "SHUTDOWN", "KILL",
    "LOAD DATA", "LOAD FILE", "OUTFILE", "DUMPFILE",
    "SET PASSWORD", "RENAME USER", "REPLACE INTO",
    NULL
};

// ═══════════════════════════════════════════
// STATE STRUCTURE
// ═══════════════════════════════════════════

typedef struct {
    char host[256];
    char user[128];
    char password[128];
    int  mysqlPort;
    char db[128];
    char sql[MAX_SQL];
    char output[MAX_RESPONSE];
    char error[MAX_ERR];
    int  errorCode;
    int  confirm;
    int  limit;
    int  rowCount;
    int  colCount;
    int  serverMode;
    int  serverPort;
    // Params for prepared statements
    char params[MAX_PARAMS][MAX_PARAM_LEN];
    int  paramTypes[MAX_PARAMS];
    int  paramCount;
} GateState;

// ═══════════════════════════════════════════
// JSON HELPERS (minimal — enough for our protocol)
// ═══════════════════════════════════════════

static void JsonEscape(char *dst, size_t dstSize, const char *src) {
    size_t i = 0, j = 0;
    if (!src) {
        if (dstSize > 4) { dst[0]='n'; dst[1]='u'; dst[2]='l'; dst[3]='l'; dst[4]='\0'; }
        return;
    }
    while (src[i] && j < dstSize - 2) {
        unsigned char c = (unsigned char)src[i];
        if (c == '"') { if (j+2<dstSize){dst[j++]='\\';dst[j++]='"';} }
        else if (c == '\\') { if (j+2<dstSize){dst[j++]='\\';dst[j++]='\\';} }
        else if (c == '\n') { if (j+2<dstSize){dst[j++]='\\';dst[j++]='n';} }
        else if (c == '\r') { if (j+2<dstSize){dst[j++]='\\';dst[j++]='r';} }
        else if (c == '\t') { if (j+2<dstSize){dst[j++]='\\';dst[j++]='t';} }
        else if (c < 32) { if (j+6<dstSize){j+=snprintf(dst+j,dstSize-j,"\\u%04x",c);} }
        else { dst[j++] = (char)c; }
        i++;
    }
    dst[j] = '\0';
}

// Extract string value for a key from JSON: {"key":"value"}
// Returns 1 if found, 0 if not. Writes to dst.
static int JsonGetString(const char *json, const char *key, char *dst, size_t dstSize) {
    char pattern[256];
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    const char *p = strstr(json, pattern);
    if (!p) return 0;
    p += strlen(pattern);
    // skip whitespace and colon
    while (*p && (*p == ' ' || *p == ':' || *p == '\t')) p++;
    if (*p != '"') return 0;
    p++; // skip opening quote
    size_t j = 0;
    while (*p && *p != '"' && j < dstSize - 1) {
        if (*p == '\\' && *(p+1)) {
            char next = *(p+1);
            if (next == 'n') dst[j++] = '\n';
            else if (next == 't') dst[j++] = '\t';
            else if (next == 'r') dst[j++] = '\r';
            else if (next == '"') dst[j++] = '"';
            else if (next == '\\') dst[j++] = '\\';
            else dst[j++] = next;
            p += 2;
        } else {
            dst[j++] = *p++;
        }
    }
    dst[j] = '\0';
    return 1;
}

// Extract int value for a key from JSON: {"key":123}
static int JsonGetInt(const char *json, const char *key, int defaultVal) {
    char pattern[256];
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    const char *p = strstr(json, pattern);
    if (!p) return defaultVal;
    p += strlen(pattern);
    while (*p && (*p == ' ' || *p == ':' || *p == '\t')) p++;
    if (*p == '"') return defaultVal; // it's a string, not int
    return atoi(p);
}

// Extract boolean: {"key":true}
static int JsonGetBool(const char *json, const char *key, int defaultVal) {
    char pattern[256];
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    const char *p = strstr(json, pattern);
    if (!p) return defaultVal;
    p += strlen(pattern);
    while (*p && (*p == ' ' || *p == ':' || *p == '\t')) p++;
    if (strncmp(p, "true", 4) == 0) return 1;
    if (strncmp(p, "false", 5) == 0) return 0;
    return defaultVal;
}

// Extract params array: "params":["val1","val2",123]
static int JsonGetParams(const char *json, GateState *s) {
    s->paramCount = 0;
    const char *p = strstr(json, "\"params\"");
    if (!p) return 0;
    p += 8;
    while (*p && (*p == ' ' || *p == ':' || *p == '\t')) p++;
    if (*p != '[') return 0;
    p++; // skip [
    while (*p && *p != ']' && s->paramCount < MAX_PARAMS) {
        while (*p && (*p == ' ' || *p == ',' || *p == '\t' || *p == '\n')) p++;
        if (*p == ']') break;
        if (*p == '"') {
            // String param
            p++;
            size_t j = 0;
            while (*p && *p != '"' && j < MAX_PARAM_LEN - 1) {
                if (*p == '\\' && *(p+1)) {
                    char next = *(p+1);
                    if (next == 'n') s->params[s->paramCount][j++] = '\n';
                    else if (next == 't') s->params[s->paramCount][j++] = '\t';
                    else if (next == '"') s->params[s->paramCount][j++] = '"';
                    else if (next == '\\') s->params[s->paramCount][j++] = '\\';
                    else s->params[s->paramCount][j++] = next;
                    p += 2;
                } else {
                    s->params[s->paramCount][j++] = *p++;
                }
            }
            s->params[s->paramCount][j] = '\0';
            s->paramTypes[s->paramCount] = MYSQL_TYPE_STRING;
            if (*p == '"') p++;
        } else {
            // Numeric param
            size_t j = 0;
            while (*p && *p != ',' && *p != ']' && *p != ' ' && j < MAX_PARAM_LEN - 1) {
                s->params[s->paramCount][j++] = *p++;
            }
            s->params[s->paramCount][j] = '\0';
            if (strchr(s->params[s->paramCount], '.') != NULL) {
                s->paramTypes[s->paramCount] = MYSQL_TYPE_DOUBLE;
            } else {
                s->paramTypes[s->paramCount] = MYSQL_TYPE_LONG;
            }
        }
        s->paramCount++;
    }
    return s->paramCount;
}

// ═══════════════════════════════════════════
// STATE INIT
// ═══════════════════════════════════════════

static void StateInit(GateState *s) {
    memset(s, 0, sizeof(GateState));
    strncpy(s->host, MYSQL_HOST, sizeof(s->host) - 1);
    strncpy(s->user, MYSQL_USER, sizeof(s->user) - 1);
    s->mysqlPort = MYSQL_PORT;
    s->confirm = 0;
    s->limit = MAX_ROWS;
    s->errorCode = ERR_NONE;
    s->serverPort = DEFAULT_PORT;
}

// ═══════════════════════════════════════════
// DESTRUCTION GUARD
// ═══════════════════════════════════════════

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

static int DestructionGuard(GateState *s, const char *sql) {
    if (!IsDestructive(sql)) return OK;
    if (!s->confirm) {
        snprintf(s->error, MAX_ERR,
            "DESTRUCTION_GUARD: blocked destructive SQL (requires confirm=true): %.200s",
            sql);
        s->errorCode = ERR_DESTRUCTIVE;
        return FAIL;
    }
    return OK;
}

// ═══════════════════════════════════════════
// PREPARED STATEMENT EXECUTION
// ═══════════════════════════════════════════

static int StmtExecute(MYSQL *conn, GateState *s, const char *sql) {
    MYSQL_STMT *stmt;
    MYSQL_BIND bindParams[MAX_PARAMS];
    MYSQL_BIND bindResults[MAX_COLS];
    MYSQL_RES *prepareMeta;
    unsigned long paramLen[MAX_PARAMS];
    unsigned long resultLen[MAX_COLS];
    int colCount, rowCount, i;
    char *pos;
    char escaped[MAX_VAL];
    char resultBufs[MAX_COLS][MAX_VAL];
    bool resultIsNull[MAX_COLS];
    bool resultError[MAX_COLS];

    stmt = mysql_stmt_init(conn);
    if (!stmt) {
        snprintf(s->error, MAX_ERR, "mysql_stmt_init failed: out of memory");
        s->errorCode = ERR_MEMORY;
        return FAIL;
    }

    if (mysql_stmt_prepare(stmt, sql, strlen(sql)) != 0) {
        snprintf(s->error, MAX_ERR, "prepare: %s", mysql_stmt_error(stmt));
        s->errorCode = ERR_SQL;
        mysql_stmt_close(stmt);
        return FAIL;
    }

    // Bind parameters if any
    if (s->paramCount > 0) {
        memset(bindParams, 0, sizeof(bindParams));
        for (i = 0; i < s->paramCount && i < MAX_PARAMS; i++) {
            bindParams[i].buffer_type = s->paramTypes[i];
            bindParams[i].buffer = s->params[i];
            paramLen[i] = strlen(s->params[i]);
            bindParams[i].buffer_length = MAX_PARAM_LEN;
            bindParams[i].length = &paramLen[i];
        }
        if (mysql_stmt_bind_param(stmt, bindParams) != 0) {
            snprintf(s->error, MAX_ERR, "bind_param: %s", mysql_stmt_error(stmt));
            s->errorCode = ERR_PARAM;
            mysql_stmt_close(stmt);
            return FAIL;
        }
    }

    if (mysql_stmt_execute(stmt) != 0) {
        snprintf(s->error, MAX_ERR, "execute: %s", mysql_stmt_error(stmt));
        s->errorCode = ERR_SQL;
        mysql_stmt_close(stmt);
        return FAIL;
    }

    // Get result metadata
    prepareMeta = mysql_stmt_result_metadata(stmt);
    if (!prepareMeta) {
        // No result set (INSERT/UPDATE/DELETE/DDL)
        my_ulonglong affected = mysql_stmt_affected_rows(stmt);
        pos = s->output;
        pos += snprintf(pos, sizeof(s->output) - (pos - s->output),
            "{\"ok\":true,\"affectedRows\":%llu,\"insertId\":%llu}",
            (unsigned long long)affected,
            (unsigned long long)mysql_stmt_insert_id(stmt));
        mysql_stmt_close(stmt);
        return OK;
    }

    colCount = mysql_num_fields(prepareMeta);
    if (colCount > MAX_COLS) colCount = MAX_COLS;
    s->colCount = colCount;

    // Bind results
    memset(bindResults, 0, sizeof(bindResults));
    for (i = 0; i < colCount; i++) {
        bindResults[i].buffer_type = MYSQL_TYPE_STRING;
        bindResults[i].buffer = resultBufs[i];
        bindResults[i].buffer_length = MAX_VAL;
        bindResults[i].length = &resultLen[i];
        bindResults[i].is_null = &resultIsNull[i];
        bindResults[i].error = &resultError[i];
    }

    if (mysql_stmt_bind_result(stmt, bindResults) != 0) {
        snprintf(s->error, MAX_ERR, "bind_result: %s", mysql_stmt_error(stmt));
        s->errorCode = ERR_SQL;
        mysql_free_result(prepareMeta);
        mysql_stmt_close(stmt);
        return FAIL;
    }

    // Build JSON
    pos = s->output;
    pos += snprintf(pos, sizeof(s->output) - (pos - s->output),
        "{\"ok\":true,\"columns\":[");
    for (i = 0; i < colCount; i++) {
        MYSQL_FIELD *field = mysql_fetch_field_direct(prepareMeta, i);
        JsonEscape(escaped, MAX_VAL, field ? field->name : "");
        pos += snprintf(pos, sizeof(s->output) - (pos - s->output),
            "%s\"%s\"",
            (i > 0) ? "," : "",
            escaped);
    }
    pos += snprintf(pos, sizeof(s->output) - (pos - s->output), "],\"rows\":[");

    rowCount = 0;
    while (mysql_stmt_fetch(stmt) == 0 && rowCount < s->limit) {
        if (rowCount > 0) {
            pos += snprintf(pos, sizeof(s->output) - (pos - s->output), ",");
        }
        pos += snprintf(pos, sizeof(s->output) - (pos - s->output), "[");
        for (i = 0; i < colCount; i++) {
            if (i > 0) {
                pos += snprintf(pos, sizeof(s->output) - (pos - s->output), ",");
            }
            if (resultIsNull[i]) {
                pos += snprintf(pos, sizeof(s->output) - (pos - s->output), "null");
            } else {
                resultBufs[i][resultLen[i] < MAX_VAL ? resultLen[i] : MAX_VAL - 1] = '\0';
                JsonEscape(escaped, MAX_VAL, resultBufs[i]);
                pos += snprintf(pos, sizeof(s->output) - (pos - s->output), "\"%s\"", escaped);
            }
        }
        pos += snprintf(pos, sizeof(s->output) - (pos - s->output), "]");
        rowCount++;
    }
    pos += snprintf(pos, sizeof(s->output) - (pos - s->output),
        "],\"rowCount\":%d}", rowCount);

    s->rowCount = rowCount;
    mysql_free_result(prepareMeta);
    mysql_stmt_close(stmt);
    return OK;
}

// ═══════════════════════════════════════════
// COMMAND: query
// ═══════════════════════════════════════════

static int CmdQuery(GateState *s) {
    MYSQL *conn;
    int rc;

    if (!s->sql[0]) {
        snprintf(s->error, MAX_ERR, "no SQL specified (--query or --sql)");
        s->errorCode = ERR_ARGS;
        return FAIL;
    }

    if (!DestructionGuard(s, s->sql)) {
        return FAIL;
    }

    conn = mysql_init(NULL);
    if (!conn) {
        snprintf(s->error, MAX_ERR, "mysql_init failed");
        s->errorCode = ERR_MEMORY;
        return FAIL;
    }

    if (!mysql_real_connect(conn, s->host, s->user, s->password[0] ? s->password : NULL,
                            s->db[0] ? s->db : NULL, s->mysqlPort, NULL, 0)) {
        snprintf(s->error, MAX_ERR, "connect: %s", mysql_error(conn));
        s->errorCode = ERR_CONN;
        mysql_close(conn);
        return FAIL;
    }

    rc = StmtExecute(conn, s, s->sql);
    mysql_close(conn);
    return rc;
}

// ═══════════════════════════════════════════
// COMMAND: tables
// ═══════════════════════════════════════════

static int CmdTables(GateState *s) {
    strncpy(s->sql, "SELECT TABLE_NAME, TABLE_TYPE FROM information_schema.tables WHERE TABLE_SCHEMA = ? ORDER BY TABLE_TYPE, TABLE_NAME", MAX_SQL - 1);
    // Use current db as param
    s->paramCount = 1;
    strncpy(s->params[0], s->db, MAX_PARAM_LEN - 1);
    s->paramTypes[0] = MYSQL_TYPE_STRING;
    return CmdQuery(s);
}

// ═══════════════════════════════════════════
// COMMAND: schema
// ═══════════════════════════════════════════

static int CmdSchema(GateState *s) {
    snprintf(s->sql, MAX_SQL,
        "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY, COLUMN_DEFAULT "
        "FROM information_schema.columns WHERE TABLE_SCHEMA = ? ORDER BY TABLE_NAME, ORDINAL_POSITION");
    s->paramCount = 1;
    strncpy(s->params[0], s->db, MAX_PARAM_LEN - 1);
    s->paramTypes[0] = MYSQL_TYPE_STRING;
    return CmdQuery(s);
}

// ═══════════════════════════════════════════
// COMMAND: ping
// ═══════════════════════════════════════════

static int CmdPing(GateState *s) {
    MYSQL *conn = mysql_init(NULL);
    if (!conn) {
        snprintf(s->error, MAX_ERR, "mysql_init failed");
        s->errorCode = ERR_MEMORY;
        return FAIL;
    }
    if (!mysql_real_connect(conn, s->host, s->user, s->password[0] ? s->password : NULL,
                            NULL, s->mysqlPort, NULL, 0)) {
        snprintf(s->error, MAX_ERR, "connect: %s", mysql_error(conn));
        s->errorCode = ERR_CONN;
        mysql_close(conn);
        return FAIL;
    }
    unsigned long ver = mysql_get_server_version(conn);
    const char *serverInfo = mysql_get_server_info(conn);
    snprintf(s->output, sizeof(s->output),
        "{\"ok\":true,\"ping\":\"pong\",\"serverVersion\":\"%s\",\"serverVersionNum\":%lu,\"host\":\"%s\",\"port\":%d}",
        serverInfo, ver, s->host, s->mysqlPort);
    mysql_close(conn);
    return OK;
}

// ═══════════════════════════════════════════
// RUN DISPATCH
// ═══════════════════════════════════════════

static int Run(GateState *s, const char *command) {
    if (strcmp(command, "query") == 0) return CmdQuery(s);
    if (strcmp(command, "tables") == 0) return CmdTables(s);
    if (strcmp(command, "schema") == 0) return CmdSchema(s);
    if (strcmp(command, "ping") == 0) return CmdPing(s);
    snprintf(s->error, MAX_ERR, "unknown command: %s (use: query, tables, schema, ping)", command);
    s->errorCode = ERR_ARGS;
    return FAIL;
}

// ═══════════════════════════════════════════
// SERVER MODE — TCP JSON API
// ═══════════════════════════════════════════

static void HandleClient(int clientFd) {
    char request[MAX_REQUEST];
    ssize_t n;
    GateState state;
    StateInit(&state);

    // Read request
    n = read(clientFd, request, sizeof(request) - 1);
    if (n <= 0) {
        close(clientFd);
        return;
    }
    request[n] = '\0';

    // Parse JSON request
    JsonGetString(request, "db", state.db, sizeof(state.db));
    JsonGetString(request, "query", state.sql, sizeof(state.sql));
    JsonGetString(request, "sql", state.sql, sizeof(state.sql));
    JsonGetString(request, "host", state.host, sizeof(state.host));
    JsonGetString(request, "user", state.user, sizeof(state.user));
    JsonGetString(request, "password", state.password, sizeof(state.password));
    state.confirm = JsonGetBool(request, "confirm", 0);
    state.limit = JsonGetInt(request, "limit", MAX_ROWS);
    state.mysqlPort = JsonGetInt(request, "mysql_port", MYSQL_PORT);

    // Get params for prepared statements
    JsonGetParams(request, &state);

    // Determine command
    char command[32];
    if (!JsonGetString(request, "cmd", command, sizeof(command))) {
        if (state.sql[0]) {
            strncpy(command, "query", sizeof(command) - 1);
        } else {
            strncpy(command, "ping", sizeof(command) - 1);
        }
    }
    command[sizeof(command)-1] = '\0';

    // Execute
    int ok = Run(&state, command);

    // Send response
    char response[MAX_RESPONSE];
    if (ok) {
        snprintf(response, sizeof(response), "%s\n", state.output);
    } else {
        char escapedErr[MAX_ERR];
        JsonEscape(escapedErr, MAX_ERR, state.error);
        snprintf(response, sizeof(response),
            "{\"ok\":false,\"error\":\"%s\",\"code\":%d}\n",
            escapedErr, state.errorCode);
    }

    write(clientFd, response, strlen(response));
    close(clientFd);
}

static int ServerLoop(GateState *s) {
    int serverFd, clientFd;
    struct sockaddr_in addr;
    int opt = 1;

    signal(SIGPIPE, SIG_IGN);

    serverFd = socket(AF_INET, SOCK_STREAM, 0);
    if (serverFd < 0) {
        snprintf(s->error, MAX_ERR, "socket: %s", strerror(errno));
        s->errorCode = ERR_CONN;
        return FAIL;
    }

    setsockopt(serverFd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = inet_addr("127.0.0.1"); // localhost only
    addr.sin_port = htons(s->serverPort);

    if (bind(serverFd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        snprintf(s->error, MAX_ERR, "bind port %d: %s", s->serverPort, strerror(errno));
        s->errorCode = ERR_CONN;
        close(serverFd);
        return FAIL;
    }

    if (listen(serverFd, BACKLOG) < 0) {
        snprintf(s->error, MAX_ERR, "listen: %s", strerror(errno));
        s->errorCode = ERR_CONN;
        close(serverFd);
        return FAIL;
    }

    fprintf(stderr, "bcl_mysql_gate listening on 127.0.0.1:%d (MySQL %s@%s:%d)\n",
        s->serverPort, s->user, s->host, s->mysqlPort);
    fprintf(stderr, "Destruction guard: ACTIVE (blocks DROP/DELETE/TRUNCATE/ALTER without confirm=true)\n");
    fprintf(stderr, "Prepared statements: ENFORCED (all queries use mysql_stmt_prepare)\n");

    while (1) {
        clientFd = accept(serverFd, NULL, NULL);
        if (clientFd < 0) {
            if (errno == EINTR) continue;
            fprintf(stderr, "accept: %s\n", strerror(errno));
            continue;
        }
        HandleClient(clientFd);
    }

    close(serverFd);
    return OK;
}

// ═══════════════════════════════════════════
// CLI ENTRY POINT
// ═══════════════════════════════════════════

static void PrintUsage(const char *prog) {
    fprintf(stderr,
        "bcl_mysql_gate — C MySQL gateway with prepared statements + destruction guard\n\n"
        "CLI mode:\n"
        "  %s --db laws --query \"SELECT * FROM law LIMIT 5\"\n"
        "  %s --db laws --tables\n"
        "  %s --db laws --schema\n"
        "  %s --ping\n"
        "  %s --db laws --query \"DELETE FROM law WHERE id=?\" --param 999 --confirm\n"
        "\n"
        "Server mode (TCP JSON API on 127.0.0.1):\n"
        "  %s --server --port 3307\n"
        "  Then send JSON: {\"db\":\"laws\",\"query\":\"SELECT * FROM law LIMIT 5\"}\n"
        "  With params:    {\"db\":\"laws\",\"query\":\"SELECT * FROM law WHERE id=?\",\"params\":[1]}\n"
        "  Destructive:    {\"db\":\"laws\",\"query\":\"DELETE FROM x\",\"confirm\":true}\n"
        "\n"
        "Options:\n"
        "  --db NAME        MySQL database name\n"
        "  --query SQL      SQL query (uses prepared statements)\n"
        "  --tables         List tables in database\n"
        "  --schema         Show schema for database\n"
        "  --ping           Test MySQL connection\n"
        "  --param VAL      Bind parameter (repeatable, in order)\n"
        "  --confirm        Allow destructive SQL (DROP/DELETE/TRUNCATE/ALTER)\n"
        "  --limit N        Max rows (default 10000)\n"
        "  --host H         MySQL host (default localhost)\n"
        "  --user U         MySQL user (default root)\n"
        "  --password P     MySQL password\n"
        "  --mysql-port P   MySQL port (default 3306)\n"
        "  --server         Run as TCP server\n"
        "  --port P         Server listen port (default 3307)\n"
        "\n"
        "Destruction guard blocks: DROP, DELETE, TRUNCATE, ALTER, GRANT, REVOKE,\n"
        "  CREATE USER, DROP USER, SHUTDOWN, KILL, LOAD DATA, OUTFILE, DUMPFILE\n"
        "\n"
        "ALL queries use mysql_stmt_prepare — no raw SQL concatenation.\n"
        "Output: JSON to stdout, errors to stderr.\n"
        "Exit: 0=ok, 1=error, 2=destructive_blocked\n",
        prog, prog, prog, prog, prog, prog);
}

int main(int argc, char **argv) {
    GateState *state = (GateState *)calloc(1, sizeof(GateState));
    if (!state) {
        fprintf(stderr, "out of memory\n");
        return 1;
    }
    StateInit(state);
    const char *command = "query";
    int i;

    mysql_library_init(0, NULL, NULL);

    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--db") == 0 && i+1 < argc) {
            strncpy(state->db, argv[++i], sizeof(state->db) - 1);
        } else if (strcmp(argv[i], "--query") == 0 && i+1 < argc) {
            strncpy(state->sql, argv[++i], sizeof(state->sql) - 1);
            command = "query";
        } else if (strcmp(argv[i], "--sql") == 0 && i+1 < argc) {
            strncpy(state->sql, argv[++i], sizeof(state->sql) - 1);
            command = "query";
        } else if (strcmp(argv[i], "--tables") == 0) {
            command = "tables";
        } else if (strcmp(argv[i], "--schema") == 0) {
            command = "schema";
        } else if (strcmp(argv[i], "--ping") == 0) {
            command = "ping";
        } else if (strcmp(argv[i], "--param") == 0 && i+1 < argc) {
            if (state->paramCount < MAX_PARAMS) {
                strncpy(state->params[state->paramCount], argv[++i], MAX_PARAM_LEN - 1);
                state->paramTypes[state->paramCount] = MYSQL_TYPE_STRING;
                state->paramCount++;
            }
        } else if (strcmp(argv[i], "--confirm") == 0) {
            state->confirm = 1;
        } else if (strcmp(argv[i], "--limit") == 0 && i+1 < argc) {
            state->limit = atoi(argv[++i]);
            if (state->limit <= 0) state->limit = MAX_ROWS;
        } else if (strcmp(argv[i], "--host") == 0 && i+1 < argc) {
            strncpy(state->host, argv[++i], sizeof(state->host) - 1);
        } else if (strcmp(argv[i], "--user") == 0 && i+1 < argc) {
            strncpy(state->user, argv[++i], sizeof(state->user) - 1);
        } else if (strcmp(argv[i], "--password") == 0 && i+1 < argc) {
            strncpy(state->password, argv[++i], sizeof(state->password) - 1);
        } else if (strcmp(argv[i], "--mysql-port") == 0 && i+1 < argc) {
            state->mysqlPort = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--server") == 0) {
            state->serverMode = 1;
        } else if (strcmp(argv[i], "--port") == 0 && i+1 < argc) {
            state->serverPort = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            PrintUsage(argv[0]);
            return 0;
        } else {
            fprintf(stderr, "unknown arg: %s (use --help)\n", argv[i]);
            return 1;
        }
    }

    // Server mode
    if (state->serverMode) {
        return ServerLoop(state) == OK ? 0 : 1;
    }

    // CLI mode
    int ok = Run(state, command);

    if (ok) {
        printf("%s\n", state->output);
        return 0;
    } else {
        char escapedErr[MAX_ERR];
        JsonEscape(escapedErr, MAX_ERR, state->error);
        fprintf(stderr, "{\"ok\":false,\"error\":\"%s\",\"code\":%d}\n",
            escapedErr, state->errorCode);
        return (state->errorCode == ERR_DESTRUCTIVE) ? 2 : 1;
    }
}
