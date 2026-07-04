//[@GHOST]{file_path="Cascade_toolStack/bcl_units/storage_mysql.c" date="2026-07-04" author="Devin" session_id="cpsd-microkernel" context="CPSD Layer 3: MySQL driver — libmysqlclient prepared statements"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE no-print mysql-driver"}
//[@FILEID]{id="storage_mysql.c" domain="cpsd_storage" authority="CpsdMysqlDriver"}
//[@SUMMARY]{summary="MySQL storage driver using libmysqlclient. Prepared statements, transactions, row fetching with binary serialization. Connection string parsing."}
//[@CLASS]{class="CpsdMysqlDriver" domain="cpsd_storage" authority="single"}
//[@METHOD]{methods="mysql_drv_connect,mysql_drv_disconnect,mysql_drv_prepare,mysql_drv_bind,mysql_drv_execute,mysql_drv_fetch,mysql_drv_begin_txn,mysql_drv_commit_txn,mysql_drv_rollback_txn,mysql_drv_ping,mysql_drv_close_stmt,mysql_drv_error,parse_conn_str"}

#include "cpsd.h"
#include <mysql.h>
#include <stdbool.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <arpa/inet.h>

// ═══════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════

#define MYSQL_DRV_COL_BUF   65536
#define MYSQL_DRV_ROW_INIT  4096

// ═══════════════════════════════════════════
// STATEMENT WRAPPER
// ═══════════════════════════════════════════

typedef struct {
    MYSQL_STMT   *stmt;
    MYSQL_BIND    binds[CPSD_MAX_PARAMS];
    unsigned long lengths[CPSD_MAX_PARAMS];
    bool          is_null[CPSD_MAX_PARAMS];
    bool          error[CPSD_MAX_PARAMS];
    // Value storage for bound params (strings/blobs need persistent buffers)
    char          values[CPSD_MAX_PARAMS][CPSD_MAX_PARAM_LEN];
    int           param_count;
} mysql_stmt_wrapper_t;

// ═══════════════════════════════════════════
// CONNECTION STRING PARSER
// Format: "host=localhost;port=3306;user=root;password=;db=laws"
// ═══════════════════════════════════════════

static void parse_conn_str(const char *conn_str,
                           char *host, size_t host_sz,
                           int  *port,
                           char *user, size_t user_sz,
                           char *pass, size_t pass_sz,
                           char *db,   size_t db_sz)
{
    // Defaults
    strncpy(host, "localhost", host_sz - 1);
    host[host_sz - 1] = '\0';
    *port = 3306;
    user[0] = '\0';
    pass[0] = '\0';
    db[0] = '\0';

    if (!conn_str) return;

    // Duplicate so we can tokenize with strtok_r
    char *dup = strdup(conn_str);
    if (!dup) return;

    char *saveptr = NULL;
    char *token = strtok_r(dup, ";", &saveptr);

    while (token != NULL) {
        // Find '=' separator
        char *eq = strchr(token, '=');
        if (eq) {
            *eq = '\0';
            const char *key = token;
            const char *val = eq + 1;

            if (strcmp(key, "host") == 0) {
                strncpy(host, val, host_sz - 1);
                host[host_sz - 1] = '\0';
            } else if (strcmp(key, "port") == 0) {
                *port = atoi(val);
                if (*port <= 0) *port = 3306;
            } else if (strcmp(key, "user") == 0) {
                strncpy(user, val, user_sz - 1);
                user[user_sz - 1] = '\0';
            } else if (strcmp(key, "password") == 0) {
                strncpy(pass, val, pass_sz - 1);
                pass[pass_sz - 1] = '\0';
            } else if (strcmp(key, "db") == 0) {
                strncpy(db, val, db_sz - 1);
                db[db_sz - 1] = '\0';
            }
        }
        token = strtok_r(NULL, ";", &saveptr);
    }

    free(dup);
}

// ═══════════════════════════════════════════
// DRIVER: CONNECT
// ═══════════════════════════════════════════

static int mysql_drv_connect(void **handle, const char *conn_str)
{
    if (!handle) return -1;

    // Safe to call multiple times
    if (mysql_library_init(0, NULL, NULL) != 0) {
        return -1;
    }

    char host[256];
    char user[128];
    char pass[128];
    char db[128];
    int  port;

    parse_conn_str(conn_str,
                   host, sizeof(host),
                   &port,
                   user, sizeof(user),
                   pass, sizeof(pass),
                   db,   sizeof(db));

    MYSQL *conn = mysql_init(NULL);
    if (!conn) {
        return -1;
    }

    // Enable automatic reconnect
    bool reconnect = true;
    mysql_options(conn, MYSQL_OPT_RECONNECT, &reconnect);

    const char *db_arg = (db[0] != '\0') ? db : NULL;
    const char *pass_arg = (pass[0] != '\0') ? pass : NULL;
    const char *user_arg = (user[0] != '\0') ? user : NULL;

    if (!mysql_real_connect(conn, host, user_arg, pass_arg,
                            db_arg, port, NULL, 0)) {
        mysql_close(conn);
        return -1;
    }

    *handle = (void *)conn;
    return 0;
}

// ═══════════════════════════════════════════
// DRIVER: DISCONNECT
// ═══════════════════════════════════════════

static int mysql_drv_disconnect(void *handle)
{
    if (!handle) return -1;
    MYSQL *conn = (MYSQL *)handle;
    mysql_close(conn);
    return 0;
}

// ═══════════════════════════════════════════
// DRIVER: PREPARE
// ═══════════════════════════════════════════

static int mysql_drv_prepare(void *handle, const char *sql, void **stmt)
{
    if (!handle || !sql || !stmt) return -1;

    MYSQL *conn = (MYSQL *)handle;

    MYSQL_STMT *raw_stmt = mysql_stmt_init(conn);
    if (!raw_stmt) {
        return -1;
    }

    if (mysql_stmt_prepare(raw_stmt, sql, (unsigned long)strlen(sql)) != 0) {
        mysql_stmt_close(raw_stmt);
        return -1;
    }

    // Allocate wrapper
    mysql_stmt_wrapper_t *wrap =
        (mysql_stmt_wrapper_t *)calloc(1, sizeof(mysql_stmt_wrapper_t));
    if (!wrap) {
        mysql_stmt_close(raw_stmt);
        return -1;
    }

    wrap->stmt = raw_stmt;
    wrap->param_count = (int)mysql_stmt_param_count(raw_stmt);

    *stmt = (void *)wrap;
    return 0;
}

// ═══════════════════════════════════════════
// DRIVER: BIND
// ═══════════════════════════════════════════

static int mysql_drv_bind(void *stmt, int idx, param_type_t type,
                          const void *value, uint32_t len)
{
    if (!stmt || idx < 0 || idx >= CPSD_MAX_PARAMS) return -1;

    mysql_stmt_wrapper_t *wrap = (mysql_stmt_wrapper_t *)stmt;
    MYSQL_BIND *b = &wrap->binds[idx];

    memset(b, 0, sizeof(MYSQL_BIND));
    b->is_null = &wrap->is_null[idx];
    b->error   = &wrap->error[idx];
    wrap->is_null[idx] = false;
    wrap->error[idx]   = false;

    if (type == PARAM_NULL || value == NULL) {
        b->buffer_type = MYSQL_TYPE_NULL;
        wrap->is_null[idx] = true;
        return 0;
    }

    switch (type) {
    case PARAM_INT32:
        b->buffer_type = MYSQL_TYPE_LONG;
        b->buffer = &wrap->values[idx];
        b->buffer_length = sizeof(int32_t);
        if (len >= sizeof(int32_t)) {
            memcpy(b->buffer, value, sizeof(int32_t));
        } else {
            int32_t v = 0;
            memcpy(&v, value, len);
            memcpy(b->buffer, &v, sizeof(int32_t));
        }
        break;

    case PARAM_INT64:
        b->buffer_type = MYSQL_TYPE_LONGLONG;
        b->buffer = &wrap->values[idx];
        b->buffer_length = sizeof(int64_t);
        if (len >= sizeof(int64_t)) {
            memcpy(b->buffer, value, sizeof(int64_t));
        } else {
            int64_t v = 0;
            memcpy(&v, value, len);
            memcpy(b->buffer, &v, sizeof(int64_t));
        }
        break;

    case PARAM_STRING:
        b->buffer_type = MYSQL_TYPE_STRING;
        if (len >= CPSD_MAX_PARAM_LEN) len = CPSD_MAX_PARAM_LEN - 1;
        memcpy(wrap->values[idx], value, len);
        wrap->values[idx][len] = '\0';
        b->buffer = wrap->values[idx];
        b->buffer_length = len;
        wrap->lengths[idx] = len;
        b->length = &wrap->lengths[idx];
        break;

    case PARAM_DOUBLE:
        b->buffer_type = MYSQL_TYPE_DOUBLE;
        b->buffer = &wrap->values[idx];
        b->buffer_length = sizeof(double);
        if (len >= sizeof(double)) {
            memcpy(b->buffer, value, sizeof(double));
        } else {
            double v = 0.0;
            memcpy(&v, value, len);
            memcpy(b->buffer, &v, sizeof(double));
        }
        break;

    case PARAM_BLOB:
        b->buffer_type = MYSQL_TYPE_BLOB;
        if (len >= CPSD_MAX_PARAM_LEN) len = CPSD_MAX_PARAM_LEN - 1;
        memcpy(wrap->values[idx], value, len);
        b->buffer = wrap->values[idx];
        b->buffer_length = len;
        wrap->lengths[idx] = len;
        b->length = &wrap->lengths[idx];
        break;

    case PARAM_BOOL:
        b->buffer_type = MYSQL_TYPE_TINY;
        b->buffer = &wrap->values[idx];
        b->buffer_length = sizeof(char);
        {
            char v = *(const char *)value;
            memcpy(b->buffer, &v, sizeof(char));
        }
        break;

    default:
        b->buffer_type = MYSQL_TYPE_NULL;
        wrap->is_null[idx] = true;
        break;
    }

    return 0;
}

// ═══════════════════════════════════════════
// DRIVER: EXECUTE
// ═══════════════════════════════════════════

static int mysql_drv_execute(void *stmt)
{
    if (!stmt) return -1;
    mysql_stmt_wrapper_t *wrap = (mysql_stmt_wrapper_t *)stmt;

    // Bind parameters if any were set
    if (wrap->param_count > 0) {
        if (mysql_stmt_bind_param(wrap->stmt, wrap->binds) != 0) {
            return -1;
        }
    }

    if (mysql_stmt_execute(wrap->stmt) != 0) {
        return -1;
    }

    return 0;
}

// ═══════════════════════════════════════════
// DRIVER: FETCH
// Row serialization format:
//   For each row, for each column:
//     1 byte: type (0=null, 3=string)
//     4 bytes: length (big-endian uint32)
//     N bytes: value
//   If NULL: type=0, length=0, no value.
// ═══════════════════════════════════════════

static int mysql_drv_fetch(void *stmt, response_t *resp, int max_rows)
{
    if (!stmt || !resp) return -1;

    mysql_stmt_wrapper_t *wrap = (mysql_stmt_wrapper_t *)stmt;
    MYSQL_STMT *mstmt = wrap->stmt;

    // Initialize response
    resp->status    = 0;
    resp->row_count = 0;
    resp->col_count = 0;
    resp->rows      = NULL;
    resp->rows_len  = 0;
    resp->error_code = 0;
    resp->error_msg[0] = '\0';

    // Get result metadata
    MYSQL_RES *meta = mysql_stmt_result_metadata(mstmt);
    if (!meta) {
        // No result set (INSERT/UPDATE/DELETE/DDL)
        my_ulonglong affected = mysql_stmt_affected_rows(mstmt);
        resp->status    = 0;
        resp->row_count = (uint32_t)affected;
        resp->col_count = 0;
        return 0;
    }

    int col_count = (int)mysql_num_fields(meta);
    if (col_count > CPSD_MAX_COLS) col_count = CPSD_MAX_COLS;
    resp->col_count = (uint32_t)col_count;

    // Copy column names
    for (int i = 0; i < col_count; i++) {
        MYSQL_FIELD *field = mysql_fetch_field_direct(meta, (unsigned int)i);
        if (field && field->name) {
            strncpy(resp->columns[i], field->name, sizeof(resp->columns[i]) - 1);
            resp->columns[i][sizeof(resp->columns[i]) - 1] = '\0';
        } else {
            resp->columns[i][0] = '\0';
        }
    }

    // Allocate result bind structures
    MYSQL_BIND    *result_binds = (MYSQL_BIND *)calloc(col_count, sizeof(MYSQL_BIND));
    unsigned long *result_lens  = (unsigned long *)calloc(col_count, sizeof(unsigned long));
    bool          *result_null  = (bool *)calloc(col_count, sizeof(bool));
    bool          *result_err   = (bool *)calloc(col_count, sizeof(bool));
    char         **result_bufs  = (char **)calloc(col_count, sizeof(char *));

    if (!result_binds || !result_lens || !result_null ||
        !result_err || !result_bufs) {
        free(result_binds); free(result_lens);
        free(result_null);  free(result_err); free(result_bufs);
        mysql_free_result(meta);
        return -1;
    }

    for (int i = 0; i < col_count; i++) {
        result_bufs[i] = (char *)malloc(MYSQL_DRV_COL_BUF);
        if (!result_bufs[i]) {
            for (int j = 0; j < i; j++) free(result_bufs[j]);
            free(result_binds); free(result_lens);
            free(result_null);  free(result_err); free(result_bufs);
            mysql_free_result(meta);
            return -1;
        }

        memset(&result_binds[i], 0, sizeof(MYSQL_BIND));
        result_binds[i].buffer_type  = MYSQL_TYPE_STRING;
        result_binds[i].buffer       = result_bufs[i];
        result_binds[i].buffer_length = MYSQL_DRV_COL_BUF;
        result_binds[i].length       = &result_lens[i];
        result_binds[i].is_null      = &result_null[i];
        result_binds[i].error        = &result_err[i];
    }

    if (mysql_stmt_bind_result(mstmt, result_binds) != 0) {
        for (int i = 0; i < col_count; i++) free(result_bufs[i]);
        free(result_binds); free(result_lens);
        free(result_null);  free(result_err); free(result_bufs);
        mysql_free_result(meta);
        return -1;
    }

    // Allocate rows buffer — grow dynamically
    size_t rows_cap = MYSQL_DRV_ROW_INIT;
    char  *rows_buf = (char *)malloc(rows_cap);
    if (!rows_buf) {
        for (int i = 0; i < col_count; i++) free(result_bufs[i]);
        free(result_binds); free(result_lens);
        free(result_null);  free(result_err); free(result_bufs);
        mysql_free_result(meta);
        return -1;
    }
    size_t rows_len = 0;

    // Fetch rows
    int row_count = 0;
    int fetch_rc;

    while (row_count < max_rows) {
        fetch_rc = mysql_stmt_fetch(mstmt);

        if (fetch_rc == 1) {
            // Error
            break;
        }
        if (fetch_rc == MYSQL_NO_DATA) {
            break;
        }
        // fetch_rc == 0 (ok) or MYSQL_DATA_TRUNCATED (still ok, buffer has data)

        for (int i = 0; i < col_count; i++) {
            uint8_t  cell_type;
            uint32_t cell_len_net;
            uint32_t cell_len;

            // Ensure capacity for type (1) + length (4) minimum
            if (rows_len + 5 > rows_cap) {
                rows_cap *= 2;
                char *nb = (char *)realloc(rows_buf, rows_cap);
                if (!nb) {
                    free(rows_buf);
                    for (int j = 0; j < col_count; j++) free(result_bufs[j]);
                    free(result_binds); free(result_lens);
                    free(result_null);  free(result_err); free(result_bufs);
                    mysql_free_result(meta);
                    return -1;
                }
                rows_buf = nb;
            }

            if (result_null[i]) {
                // NULL cell: type=0, length=0
                cell_type = 0;
                cell_len  = 0;
                rows_buf[rows_len++] = (char)cell_type;
                cell_len_net = htonl(cell_len);
                memcpy(rows_buf + rows_len, &cell_len_net, 4);
                rows_len += 4;
            } else {
                // String cell: type=3, length, value
                cell_type = 3;
                cell_len  = (uint32_t)result_lens[i];
                if (cell_len > MYSQL_DRV_COL_BUF - 1) {
                    cell_len = MYSQL_DRV_COL_BUF - 1;
                }
                // Null-terminate the buffer for safety
                result_bufs[i][cell_len] = '\0';

                // Ensure capacity for type(1) + length(4) + value(cell_len)
                if (rows_len + 5 + cell_len > rows_cap) {
                    while (rows_len + 5 + cell_len > rows_cap) {
                        rows_cap *= 2;
                    }
                    char *nb = (char *)realloc(rows_buf, rows_cap);
                    if (!nb) {
                        free(rows_buf);
                        for (int j = 0; j < col_count; j++) free(result_bufs[j]);
                        free(result_binds); free(result_lens);
                        free(result_null);  free(result_err); free(result_bufs);
                        mysql_free_result(meta);
                        return -1;
                    }
                    rows_buf = nb;
                }

                rows_buf[rows_len++] = (char)cell_type;
                cell_len_net = htonl(cell_len);
                memcpy(rows_buf + rows_len, &cell_len_net, 4);
                rows_len += 4;
                memcpy(rows_buf + rows_len, result_bufs[i], cell_len);
                rows_len += cell_len;
            }
        }

        row_count++;
    }

    // Finalize response
    resp->status    = 0;
    resp->row_count = (uint32_t)row_count;
    resp->col_count = (uint32_t)col_count;
    resp->rows      = rows_buf;
    resp->rows_len  = rows_len;

    // Cleanup
    for (int i = 0; i < col_count; i++) free(result_bufs[i]);
    free(result_bufs);
    free(result_binds);
    free(result_lens);
    free(result_null);
    free(result_err);

    mysql_free_result(meta);
    mysql_stmt_free_result(mstmt);

    return 0;
}

// ═══════════════════════════════════════════
// DRIVER: TRANSACTION CONTROL
// ═══════════════════════════════════════════

static int mysql_drv_begin_txn(void *handle)
{
    if (!handle) return -1;
    MYSQL *conn = (MYSQL *)handle;
    if (mysql_autocommit(conn, 0) != 0) return -1;
    return 0;
}

static int mysql_drv_commit_txn(void *handle)
{
    if (!handle) return -1;
    MYSQL *conn = (MYSQL *)handle;
    if (mysql_commit(conn) != 0) return -1;
    mysql_autocommit(conn, 1);
    return 0;
}

static int mysql_drv_rollback_txn(void *handle)
{
    if (!handle) return -1;
    MYSQL *conn = (MYSQL *)handle;
    if (mysql_rollback(conn) != 0) return -1;
    mysql_autocommit(conn, 1);
    return 0;
}

// ═══════════════════════════════════════════
// DRIVER: PING
// ═══════════════════════════════════════════

static int mysql_drv_ping(void *handle)
{
    if (!handle) return -1;
    MYSQL *conn = (MYSQL *)handle;
    if (mysql_ping(conn) == 0) return 0;
    return -1;
}

// ═══════════════════════════════════════════
// DRIVER: CLOSE STATEMENT
// ═══════════════════════════════════════════

static int mysql_drv_close_stmt(void *stmt)
{
    if (!stmt) return -1;
    mysql_stmt_wrapper_t *wrap = (mysql_stmt_wrapper_t *)stmt;
    if (wrap->stmt) {
        mysql_stmt_close(wrap->stmt);
    }
    free(wrap);
    return 0;
}

// ═══════════════════════════════════════════
// DRIVER: ERROR
// ═══════════════════════════════════════════

static const char *mysql_drv_error(void *handle)
{
    if (!handle) return "no connection";
    MYSQL *conn = (MYSQL *)handle;
    return mysql_error(conn);
}

// ═══════════════════════════════════════════
// GLOBAL DRIVER INSTANCE
// ═══════════════════════════════════════════

storage_driver_t mysql_driver = {
    .backend      = STORAGE_MYSQL,
    .name         = "mysql",
    .connect      = mysql_drv_connect,
    .disconnect   = mysql_drv_disconnect,
    .prepare      = mysql_drv_prepare,
    .bind         = mysql_drv_bind,
    .execute      = mysql_drv_execute,
    .fetch        = mysql_drv_fetch,
    .begin_txn    = mysql_drv_begin_txn,
    .commit_txn   = mysql_drv_commit_txn,
    .rollback_txn = mysql_drv_rollback_txn,
    .ping         = mysql_drv_ping,
    .close_stmt   = mysql_drv_close_stmt,
    .error        = mysql_drv_error,
};
