//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_smartcli.c" date="2026-07-04" author="Devin" session_id="bcl-toolstack-units" context="BCL unit - Smart CLI executor with error detection. popen shell exec, destruction_guard-aware safe mode, MySQL query exec, batch runner."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="bcl_smartcli.c" domain="cascade_tools" authority="Smartcli"}
//[@SUMMARY]{summary="Smart CLI executor. Commands: exec, exec_safe, exec_mysql, batch, read_state, set_config. Uses popen + gettimeofday for timed shell execution, MySQL for query exec, destruction_guard-style pattern match for safe mode."}
//[@CLASS]{class="Smartcli" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="ExecShell" type="internal"}
//[@METHOD]{method="IsDangerous" type="internal"}
//[@METHOD]{method="EnsureMysql" type="internal"}
//[@METHOD]{method="ExtractAllCmd" type="internal"}
//[@REVIEW]{[@date<2026-07-04>][@reviewer<devin>][@status<implementation>][@notes<Real smart CLI executor. popen for shell, gettimeofday for timing, mysql_real_connect for exec_mysql. No printf/fprintf - errors go to STATE.last_error.>][@todos<>]}

/* BCL IN:  [@CMD]{exec}[@BCL]{[@CMD]{ls -la}[@TIMEOUT]{30}[@CWD]{/path}}
 *          [@CMD]{exec_safe}[@BCL]{[@CMD]{rm -rf /}}
 *          [@CMD]{exec_mysql}[@BCL]{[@QUERY]{SELECT 1}[@DB]{vb_shared}}
 *          [@CMD]{batch}[@BCL]{[@CMD]{echo a}[@CMD]{echo b}}
 * BCL OUT: [@OK]{[@EXIT]{0}[@DURATION]{12}[@OUTPUT]{...}[@ERROR]{0}} */

#include "bcl_toolstack.h"
#include <mysql.h>
#include <sys/time.h>
#include <unistd.h>
#include <sys/wait.h>

/* ===== DIM BLOCK ===== */

#define SMARTCLI_MAX_CMD         4096
#define SMARTCLI_MAX_OUTPUT      32768
#define SMARTCLI_MAX_ERROR       512
#define SMARTCLI_DEFAULT_TIMEOUT 30
#define SMARTCLI_MAX_BATCH       32

/* ===== STATE ===== */

static struct {
    int      initialized;
    int      total_executed;
    int      successes;
    int      failures;
    char     last_cmd[SMARTCLI_MAX_CMD];
    char     last_error[SMARTCLI_MAX_ERROR];
    int      last_exit_code;
    /* config */
    int      default_timeout;
    int      max_output_size;
    int      safe_mode;
    /* mysql config */
    char     mysql_host[128];
    char     mysql_user[64];
    char     mysql_pass[128];
    int      mysql_port;
    char     mysql_socket[256];
    MYSQL   *conn;
    int      mysql_connected;
} STATE;

/* ===== SECTION: HELPERS ===== */

/* Check a command against destruction_guard-style dangerous patterns.
 * Returns 1 if dangerous (matched pattern stored in matched_out), 0 if safe. */
static int is_dangerous(const char *cmd, char *matched_out, size_t matched_sz) {
    static const char *PATTERNS[] = {
        "rm -rf", "rm -fr", "dd ", "dd\t", "mkfs", "shutdown",
        "reboot", "halt", "init 0", "init 6", ":(){", "fork bomb", NULL
    };
    for (int i = 0; PATTERNS[i] != NULL; i++) {
        if (strstr(cmd, PATTERNS[i]) != NULL) {
            snprintf(matched_out, matched_sz, "%s", PATTERNS[i]);
            return 1;
        }
    }
    return 0;
}

/* Execute a shell command via popen, capture stdout+stderr, measure duration.
 * Returns exit code. Output stored in out_buf (truncated to cap). */
static int exec_shell(const char *cmd, const char *cwd, int timeout,
                      char *out_buf, size_t out_sz, long *duration_ms) {
    struct timeval t0, t1;
    gettimeofday(&t0, NULL);
    (void)timeout; /* advisory — popen blocks; recorded in duration */

    char shell_cmd[SMARTCLI_MAX_CMD + 256];
    if (cwd && cwd[0])
        snprintf(shell_cmd, sizeof(shell_cmd), "cd '%s' && %s 2>&1", cwd, cmd);
    else
        snprintf(shell_cmd, sizeof(shell_cmd), "%s 2>&1", cmd);

    FILE *fp = popen(shell_cmd, "r");
    if (!fp) { snprintf(out_buf, out_sz, "popen failed"); *duration_ms = 0; return 127; }

    size_t pos = 0;
    char chunk[1024];
    size_t cap = (size_t)STATE.max_output_size;
    if (cap == 0 || cap > out_sz - 1) cap = out_sz - 1;
    while (fgets(chunk, sizeof(chunk), fp) != NULL) {
        size_t n = strlen(chunk);
        if (pos + n >= cap) {
            size_t room = cap - pos;
            if (room > 0) { memcpy(out_buf + pos, chunk, room); pos += room; }
            if (pos + 3 < cap) { memcpy(out_buf + pos, "...", 3); pos += 3; }
            break;
        }
        memcpy(out_buf + pos, chunk, n);
        pos += n;
    }
    out_buf[pos] = '\0';

    int status = pclose(fp);
    gettimeofday(&t1, NULL);
    *duration_ms = (t1.tv_sec - t0.tv_sec) * 1000L + (t1.tv_usec - t0.tv_usec) / 1000L;

    int exit_code = 127;
    if (WIFEXITED(status)) exit_code = WEXITSTATUS(status);
    else if (WIFSIGNALED(status)) exit_code = 128 + WTERMSIG(status);
    return exit_code;
}

/* Ensure MySQL connection is open. Returns 1 on success, 0 on failure. */
static int ensure_mysql(void) {
    if (STATE.mysql_connected && STATE.conn) return 1;
    if (STATE.conn) { mysql_close(STATE.conn); STATE.conn = NULL; }
    STATE.conn = mysql_init(NULL);
    if (!STATE.conn) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "mysql_init failed");
        STATE.mysql_connected = 0;
        return 0;
    }
    const char *sock = STATE.mysql_socket[0] ? STATE.mysql_socket : NULL;
    if (!mysql_real_connect(STATE.conn, STATE.mysql_host, STATE.mysql_user,
            STATE.mysql_pass[0] ? STATE.mysql_pass : NULL, NULL,
            STATE.mysql_port, sock, 0)) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "connect: %s",
            mysql_error(STATE.conn));
        mysql_close(STATE.conn); STATE.conn = NULL;
        STATE.mysql_connected = 0;
        return 0;
    }
    STATE.mysql_connected = 1;
    return 1;
}

/* ===== SECTION: COMMANDS ===== */

/* Shared runner for exec / exec_safe. guard_mode:
 *   0 = no destruction_guard check (exec without safe_mode)
 *   1 = check only when STATE.safe_mode is on (exec)
 *   2 = always check (exec_safe) */
static int run_one(const char *bcl_in, char *bcl_out, size_t out_sz,
                   int guard_mode, int emit_safe) {
    BclParseResult parse;
    BclParser_Init(&parse);
    BclParser_Parse(&parse, bcl_in);
    char cmd[SMARTCLI_MAX_CMD] = {0};
    char timeout_str[16] = {0};
    char cwd[TOOL_MAX_PATH] = {0};
    BclParser_Extract(&parse, "CMD", cmd, sizeof(cmd));
    BclParser_Extract(&parse, "TIMEOUT", timeout_str, sizeof(timeout_str));
    BclParser_Extract(&parse, "CWD", cwd, sizeof(cwd));
    BclParser_Free(&parse);

    if (!cmd[0]) {
        STATE.failures++;
        snprintf(STATE.last_error, sizeof(STATE.last_error), "no CMD in packet");
        return BclResult_Err(bcl_out, out_sz, 20, "no CMD in packet");
    }

    /* destruction_guard check */
    int do_guard = (guard_mode == 2) || (guard_mode == 1 && STATE.safe_mode);
    if (do_guard) {
        char matched[64];
        if (is_dangerous(cmd, matched, sizeof(matched))) {
            STATE.total_executed++;
            STATE.failures++;
            strncpy(STATE.last_cmd, cmd, sizeof(STATE.last_cmd) - 1);
            snprintf(STATE.last_error, sizeof(STATE.last_error),
                "blocked: %s", matched);
            return BclResult_Err(bcl_out, out_sz, 41,
                "dangerous command blocked by destruction_guard rules");
        }
    }

    int timeout = timeout_str[0] ? atoi(timeout_str) : STATE.default_timeout;
    if (timeout <= 0) timeout = SMARTCLI_DEFAULT_TIMEOUT;

    static char output[SMARTCLI_MAX_OUTPUT];
    long duration = 0;
    int exit_code = exec_shell(cmd, cwd[0] ? cwd : NULL, timeout,
        output, sizeof(output), &duration);

    STATE.total_executed++;
    strncpy(STATE.last_cmd, cmd, sizeof(STATE.last_cmd) - 1);
    STATE.last_exit_code = exit_code;
    int error_detected = (exit_code != 0) ? 1 : 0;
    if (error_detected) {
        STATE.failures++;
        snprintf(STATE.last_error, sizeof(STATE.last_error), "exit %d", exit_code);
    } else {
        STATE.successes++; STATE.last_error[0] = '\0';
    }

    const char *fmt = emit_safe
        ? "[@OK]{[@SAFE]{1}[@EXIT]{%d}[@DURATION]{%ld}[@ERROR]{%d}[@OUTPUT]{"
        : "[@OK]{[@EXIT]{%d}[@DURATION]{%ld}[@ERROR]{%d}[@OUTPUT]{";
    int off = snprintf(bcl_out, out_sz, fmt, exit_code, duration, error_detected);
    size_t out_len = strlen(output);
    size_t room = out_sz - off - 32;
    if (out_len > room) out_len = room;
    memcpy(bcl_out + off, output, out_len);
    off += (int)out_len;
    off += snprintf(bcl_out + off, out_sz - off, "}}");
    (void)off;
    return 1;
}

/* exec — run a shell command, capture output, detect errors */
static int cmd_exec(const char *bcl_in, char *bcl_out, size_t out_sz) {
    return run_one(bcl_in, bcl_out, out_sz, 1, 0);
}

/* exec_safe — always check destruction_guard rules first */
static int cmd_exec_safe(const char *bcl_in, char *bcl_out, size_t out_sz) {
    return run_one(bcl_in, bcl_out, out_sz, 2, 1);
}

/* exec_mysql — execute a MySQL query, return rows as BCL array */
static int cmd_exec_mysql(const char *bcl_in, char *bcl_out, size_t out_sz) {
    BclParseResult parse;
    BclParser_Init(&parse);
    BclParser_Parse(&parse, bcl_in);
    char query[SMARTCLI_MAX_CMD] = {0};
    char db[128] = {0};
    BclParser_Extract(&parse, "QUERY", query, sizeof(query));
    BclParser_Extract(&parse, "DB", db, sizeof(db));
    BclParser_Free(&parse);

    if (!query[0]) {
        STATE.failures++;
        return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
    }
    if (!db[0]) strncpy(db, "vb_shared", sizeof(db) - 1);
    if (!ensure_mysql()) {
        STATE.failures++; STATE.total_executed++;
        return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
    }
    if (mysql_select_db(STATE.conn, db) != 0) {
        STATE.failures++; STATE.total_executed++;
        snprintf(STATE.last_error, sizeof(STATE.last_error),
            "select db: %s", mysql_error(STATE.conn));
        return BclResult_Err(bcl_out, out_sz, 11, STATE.last_error);
    }
    if (mysql_query(STATE.conn, query) != 0) {
        STATE.failures++; STATE.total_executed++;
        strncpy(STATE.last_cmd, query, sizeof(STATE.last_cmd) - 1);
        snprintf(STATE.last_error, sizeof(STATE.last_error),
            "query: %s", mysql_error(STATE.conn));
        return BclResult_Err(bcl_out, out_sz, 12, STATE.last_error);
    }
    MYSQL_RES *res = mysql_store_result(STATE.conn);
    STATE.total_executed++;
    strncpy(STATE.last_cmd, query, sizeof(STATE.last_cmd) - 1);

    /* Non-SELECT queries (INSERT/UPDATE/DELETE) return no result set */
    if (!res) {
        if (mysql_field_count(STATE.conn) == 0) {
            my_ulonglong affected = mysql_affected_rows(STATE.conn);
            STATE.successes++; STATE.last_error[0] = '\0'; STATE.last_exit_code = 0;
            snprintf(bcl_out, out_sz, "[@OK]{[@DB]{%s}[@AFFECTED]{%llu}[@ROWS]{0}}",
                db, (unsigned long long)affected);
            return 1;
        }
        STATE.failures++;
        snprintf(STATE.last_error, sizeof(STATE.last_error),
            "store_result: %s", mysql_error(STATE.conn));
        return BclResult_Err(bcl_out, out_sz, 13, STATE.last_error);
    }

    my_ulonglong row_count = mysql_num_rows(res);
    unsigned int nfields = mysql_num_fields(res);
    int off = snprintf(bcl_out, out_sz,
        "[@OK]{[@DB]{%s}[@ROWS]{%llu}[@FIELDS]{%u}[@DATA]{",
        db, (unsigned long long)row_count, nfields);

    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)) != NULL && off < (int)out_sz - 2048) {
        off += snprintf(bcl_out + off, out_sz - off, "[@R]{");
        for (unsigned int f = 0; f < nfields && off < (int)out_sz - 1024; f++) {
            const char *val = row[f] ? row[f] : "NULL";
            off += snprintf(bcl_out + off, out_sz - off, "[@F]{%s}", val);
        }
        off += snprintf(bcl_out + off, out_sz - off, "}");
    }
    off += snprintf(bcl_out + off, out_sz - off, "}}");
    mysql_free_result(res);

    STATE.successes++; STATE.last_error[0] = '\0'; STATE.last_exit_code = 0;
    (void)off;
    return 1;
}

/* batch — execute multiple [@CMD] tags, return result for each */
static int cmd_batch(const char *bcl_in, char *bcl_out, size_t out_sz) {
    BclParseResult parse;
    BclParser_Init(&parse);
    BclParser_Parse(&parse, bcl_in);

    int off = snprintf(bcl_out, out_sz, "[@OK]{[@TOTAL]{0}[@RESULTS]{");
    int count = 0, successes = 0, failures = 0;

    for (int i = 0; i < parse.node_count && count < SMARTCLI_MAX_BATCH; i++) {
        if (strcmp(parse.nodes[i].tag, "CMD") != 0) continue;
        const char *cmd = parse.nodes[i].content;
        if (!cmd[0]) continue;

        char matched[64];
        if (STATE.safe_mode && is_dangerous(cmd, matched, sizeof(matched))) {
            STATE.total_executed++; STATE.failures++; failures++;
            off += snprintf(bcl_out + off, out_sz - off,
                "[@ITEM]{[@CMD]{%s}[@EXIT]{-1}[@ERROR]{1}[@OUTPUT]{blocked: %s}}",
                cmd, matched);
            count++;
            continue;
        }

        static char output[SMARTCLI_MAX_OUTPUT];
        long duration = 0;
        int exit_code = exec_shell(cmd, NULL, STATE.default_timeout,
            output, sizeof(output), &duration);
        STATE.total_executed++;
        strncpy(STATE.last_cmd, cmd, sizeof(STATE.last_cmd) - 1);
        STATE.last_exit_code = exit_code;
        int error_detected = (exit_code != 0) ? 1 : 0;
        if (error_detected) {
            STATE.failures++; failures++;
            snprintf(STATE.last_error, sizeof(STATE.last_error), "exit %d", exit_code);
        } else {
            STATE.successes++; successes++;
            STATE.last_error[0] = '\0';
        }

        off += snprintf(bcl_out + off, out_sz - off,
            "[@ITEM]{[@CMD]{%s}[@EXIT]{%d}[@DURATION]{%ld}[@ERROR]{%d}[@OUTPUT]{",
            cmd, exit_code, duration, error_detected);
        size_t out_len = strlen(output);
        size_t room = out_sz - off - 256;
        if (out_len > room) out_len = room;
        memcpy(bcl_out + off, output, out_len);
        off += (int)out_len;
        off += snprintf(bcl_out + off, out_sz - off, "}}");
        count++;
    }

    /* patch TOTAL in-place when count is a single digit */
    if (count >= 0 && count <= 9) {
        char *total_pos = strstr(bcl_out, "[@TOTAL]{0}");
        if (total_pos) total_pos[8] = (char)('0' + count);
    }
    off = (int)strlen(bcl_out);
    off += snprintf(bcl_out + off, out_sz - off,
        "}[@SUCCESSES]{%d}[@FAILURES]{%d}}", successes, failures);
    (void)off;
    BclParser_Free(&parse);
    return 1;
}

/* ===== SECTION: UNIT INTERFACE ===== */

int Smartcli_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    STATE.default_timeout = SMARTCLI_DEFAULT_TIMEOUT;
    STATE.max_output_size = SMARTCLI_MAX_OUTPUT;
    STATE.safe_mode = 1;
    strncpy(STATE.mysql_host, "localhost", sizeof(STATE.mysql_host) - 1);
    strncpy(STATE.mysql_user, "root", sizeof(STATE.mysql_user) - 1);
    STATE.mysql_port = 3306;
    return 1;
}

int Smartcli_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) Smartcli_Init();
    if (strcmp(cmd, "exec") == 0)       return cmd_exec(bcl_in, bcl_out, out_sz);
    if (strcmp(cmd, "exec_safe") == 0)  return cmd_exec_safe(bcl_in, bcl_out, out_sz);
    if (strcmp(cmd, "exec_mysql") == 0) return cmd_exec_mysql(bcl_in, bcl_out, out_sz);
    if (strcmp(cmd, "batch") == 0)      return cmd_batch(bcl_in, bcl_out, out_sz);

    if (strcmp(cmd, "read_state") == 0) {
        char body[1024];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@TOTAL]{%d}[@SUCCESSES]{%d}[@FAILURES]{%d}"
            "[@LAST_CMD]{%s}[@LAST_ERROR]{%s}[@LAST_EXIT]{%d}"
            "[@SAFE_MODE]{%d}[@TIMEOUT]{%d}[@MAXOUT]{%d}",
            STATE.initialized, STATE.total_executed, STATE.successes,
            STATE.failures, STATE.last_cmd, STATE.last_error,
            STATE.last_exit_code, STATE.safe_mode, STATE.default_timeout,
            STATE.max_output_size);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char timeout_str[16] = {0}, maxout_str[16] = {0}, safe_str[16] = {0};
        char host[128] = {0}, user[64] = {0}, pass[128] = {0};
        char port_str[16] = {0}, sock[256] = {0};
        BclParser_Extract(&parse, "TIMEOUT", timeout_str, sizeof(timeout_str));
        BclParser_Extract(&parse, "MAXOUT", maxout_str, sizeof(maxout_str));
        BclParser_Extract(&parse, "SAFE", safe_str, sizeof(safe_str));
        BclParser_Extract(&parse, "HOST", host, sizeof(host));
        BclParser_Extract(&parse, "USER", user, sizeof(user));
        BclParser_Extract(&parse, "PASS", pass, sizeof(pass));
        BclParser_Extract(&parse, "PORT", port_str, sizeof(port_str));
        BclParser_Extract(&parse, "SOCKET", sock, sizeof(sock));
        BclParser_Free(&parse);
        if (timeout_str[0]) STATE.default_timeout = atoi(timeout_str);
        if (maxout_str[0]) STATE.max_output_size = atoi(maxout_str);
        if (safe_str[0]) STATE.safe_mode = atoi(safe_str) ? 1 : 0;
        if (host[0]) strncpy(STATE.mysql_host, host, sizeof(STATE.mysql_host) - 1);
        if (user[0]) strncpy(STATE.mysql_user, user, sizeof(STATE.mysql_user) - 1);
        if (pass[0]) strncpy(STATE.mysql_pass, pass, sizeof(STATE.mysql_pass) - 1);
        if (port_str[0]) STATE.mysql_port = atoi(port_str);
        if (sock[0]) strncpy(STATE.mysql_socket, sock, sizeof(STATE.mysql_socket) - 1);
        if (STATE.mysql_connected && STATE.conn) {
            mysql_close(STATE.conn); STATE.conn = NULL; STATE.mysql_connected = 0;
        }
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }
    return BclResult_Err(bcl_out, out_sz, 50, "unknown command");
}

int Smartcli_Close(void) {
    if (STATE.conn) { mysql_close(STATE.conn); STATE.conn = NULL; }
    STATE.mysql_connected = 0;
    STATE.initialized = 0;
    return 1;
}

const char * Smartcli_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "Smartcli: initialized=%d executed=%d ok=%d fail=%d safe=%d",
        STATE.initialized, STATE.total_executed, STATE.successes,
        STATE.failures, STATE.safe_mode);
    return buf;
}
