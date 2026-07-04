//[@GHOST]{file_path="Cascade_toolStack/bcl_units/ipc_client.c" date="2026-07-04" author="Devin" session_id="cpsd-microkernel" context="CPSD Layer 1: Per-client handler — read request, dispatch, send response"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE no-print client-handler"}
//[@FILEID]{id="ipc_client.c" domain="cpsd_ipc" authority="CpsdClient"}
//[@SUMMARY]{summary="Per-client connection handler. Reads binary request, dispatches to registered handler, sends binary response. Handles CMD_PING directly. Thread-safe handler registry."}
//[@CLASS]{class="CpsdClient" domain="cpsd_ipc" authority="single"}
//[@METHOD]{methods="ipc_client_handle,ipc_client_register_handler,handle_ping,handle_tables,handle_schema,handle_query,handle_admin,dispatch,free_request"}

#include "cpsd.h"
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <arpa/inet.h>
#include <errno.h>
#include <pthread.h>

// ═══════════════════════════════════════════
// UPPERCASE CONSTANTS
// ═══════════════════════════════════════════

#define ERR_UNKNOWN_COMMAND  0x0001
#define ERR_BAD_REQUEST      0x0002

#define HANDLER_TABLE_SIZE   256
#define RESPONSE_ROWS_BUF    4096
#define RESPONSE_FRAME_BUF   8192
#define REQUEST_FRAME_BUF    131072

#define COL_TYPE_STRING      3   // matches PARAM_STRING

// ═══════════════════════════════════════════
// DISPATCH TABLE
// 256-entry static array of function pointers.
// cmd_id is uint16 but only 0-255 used for built-in.
// ═══════════════════════════════════════════

typedef int (*cmd_handler_t)(const request_t *req, response_t *resp);

static cmd_handler_t g_handlers[HANDLER_TABLE_SIZE];
static pthread_mutex_t g_handler_mutex = PTHREAD_MUTEX_INITIALIZER;

// ═══════════════════════════════════════════
// FORWARD DECLARATIONS
// ═══════════════════════════════════════════

static int HandlePing(const request_t *req, response_t *resp);
static int HandleTables(const request_t *req, response_t *resp);
static int HandleSchema(const request_t *req, response_t *resp);
static int HandleQuery(const request_t *req, response_t *resp);
static int HandleAdmin(const request_t *req, response_t *resp);
static int Dispatch(const request_t *req, response_t *resp);
static void FreeRequest(request_t *req);
static void SendError(int client_fd, uint32_t request_id, uint16_t code, const char *msg);
static void SerializeStringCell(unsigned char *buf, size_t *offset, size_t cap, const char *value);

// ═══════════════════════════════════════════
// HANDLER REGISTRATION (thread-safe)
// Returns 0 on success, -1 on invalid cmd_id.
// ═══════════════════════════════════════════

int ipc_client_register_handler(uint16_t cmd_id, cmd_handler_t handler) {
    if (cmd_id >= HANDLER_TABLE_SIZE) {
        return -1;
    }
    pthread_mutex_lock(&g_handler_mutex);
    g_handlers[cmd_id] = handler;
    pthread_mutex_unlock(&g_handler_mutex);
    return 0;
}

// ═══════════════════════════════════════════
// BUILT-IN HANDLERS
// Each returns 0 on success, -1 on error.
// On success, resp is fully populated.
// ═══════════════════════════════════════════

// CMD_PING (4): return {"ok":true,"ping":"pong"} — no DB access.
// Single row, single column "ping" with string value "pong".
static int HandlePing(const request_t *req, response_t *resp) {
    (void)req;
    memset(resp, 0, sizeof(*resp));
    resp->status    = 0;          // OK
    resp->row_count = 1;
    resp->col_count = 1;
    strncpy(resp->columns[0], "ping", sizeof(resp->columns[0]) - 1);

    unsigned char *buf = (unsigned char *)malloc(RESPONSE_ROWS_BUF);
    if (buf == NULL) {
        resp->status     = 1;
        resp->error_code = 0x000D;  // ERR_INTERNAL
        snprintf(resp->error_msg, sizeof(resp->error_msg), "out of memory");
        return -1;
    }
    size_t offset = 0;
    SerializeStringCell(buf, &offset, RESPONSE_ROWS_BUF, "pong");
    resp->rows     = (char *)buf;
    resp->rows_len = offset;
    return 0;
}

// CMD_TABLES (2): call storage to list tables.
// Storage is a stub for now — return error.
static int HandleTables(const request_t *req, response_t *resp) {
    (void)req;
    memset(resp, 0, sizeof(*resp));
    resp->status     = 1;
    resp->error_code = 0x0008;  // ERR_BACKEND_DOWN
    snprintf(resp->error_msg, sizeof(resp->error_msg), "storage not implemented");
    return -1;
}

// CMD_SCHEMA (3): call storage to get schema.
// Storage is a stub for now — return error.
static int HandleSchema(const request_t *req, response_t *resp) {
    (void)req;
    memset(resp, 0, sizeof(*resp));
    resp->status     = 1;
    resp->error_code = 0x0008;  // ERR_BACKEND_DOWN
    snprintf(resp->error_msg, sizeof(resp->error_msg), "storage not implemented");
    return -1;
}

// CMD_QUERY (1): handled by query engine in Phase 4.
// For now return an error.
static int HandleQuery(const request_t *req, response_t *resp) {
    (void)req;
    memset(resp, 0, sizeof(*resp));
    resp->status     = 1;
    resp->error_code = 0x000D;  // ERR_INTERNAL
    snprintf(resp->error_msg, sizeof(resp->error_msg), "query engine not implemented");
    return -1;
}

// CMD_ADMIN (9): return "admin not implemented" for now.
static int HandleAdmin(const request_t *req, response_t *resp) {
    (void)req;
    memset(resp, 0, sizeof(*resp));
    resp->status     = 1;
    resp->error_code = 0x000D;  // ERR_INTERNAL
    snprintf(resp->error_msg, sizeof(resp->error_msg), "admin not implemented");
    return -1;
}

// ═══════════════════════════════════════════
// DISPATCH
// Looks up the handler in the dispatch table.
// If no handler registered, returns error response
// with error_code=0x0001 (ERR_UNKNOWN_COMMAND).
// Returns 0 on success (handler found and ran),
// -1 if no handler registered.
// ═══════════════════════════════════════════

static int Dispatch(const request_t *req, response_t *resp) {
    cmd_handler_t handler = NULL;

    if (req->cmd_id < HANDLER_TABLE_SIZE) {
        pthread_mutex_lock(&g_handler_mutex);
        handler = g_handlers[req->cmd_id];
        pthread_mutex_unlock(&g_handler_mutex);
    }

    if (handler == NULL) {
        memset(resp, 0, sizeof(*resp));
        resp->status     = 1;
        resp->error_code = ERR_UNKNOWN_COMMAND;
        snprintf(resp->error_msg, sizeof(resp->error_msg),
            "unknown command: cmd_id=%u", (unsigned)req->cmd_id);
        return -1;
    }
    return handler(req, resp);
}

// ═══════════════════════════════════════════
// FREE REQUEST PARAM MEMORY
// ipc_parse_request allocates param->value buffers.
// Free them after handling.
// ═══════════════════════════════════════════

static void FreeRequest(request_t *req) {
    if (req == NULL) {
        return;
    }
    int i;
    for (i = 0; i < CPSD_MAX_PARAMS; i++) {
        if (req->params[i].value != NULL) {
            free(req->params[i].value);
            req->params[i].value = NULL;
            req->params[i].len   = 0;
            req->params[i].type  = PARAM_NULL;
        }
    }
}

// ═══════════════════════════════════════════
// SERIALIZE A STRING CELL INTO ROWS BUFFER
// Format: TYPE[1] + LEN[4] + VALUE[LEN]
// TYPE = COL_TYPE_STRING (3), LEN is big-endian.
// ═══════════════════════════════════════════

static void SerializeStringCell(unsigned char *buf, size_t *offset, size_t cap, const char *value) {
    size_t vlen = strlen(value);
    if (*offset + 1 + 4 + vlen > cap) {
        return;  // bounds check — silently truncate
    }
    buf[*offset] = (unsigned char)COL_TYPE_STRING;
    (*offset)++;
    uint32_t net_len = htonl((uint32_t)vlen);
    memcpy(buf + *offset, &net_len, 4);
    (*offset) += 4;
    memcpy(buf + *offset, value, vlen);
    (*offset) += vlen;
}

// ═══════════════════════════════════════════
// SEND ERROR RESPONSE
// Helper: build and send an error frame for a
// given request_id. Used on parse failure.
// ═══════════════════════════════════════════

static void SendError(int client_fd, uint32_t request_id, uint16_t code, const char *msg) {
    response_t resp;
    memset(&resp, 0, sizeof(resp));
    resp.status     = 1;
    resp.error_code = code;
    if (msg != NULL) {
        snprintf(resp.error_msg, sizeof(resp.error_msg), "%s", msg);
    }

    unsigned char frame[RESPONSE_FRAME_BUF];
    size_t frame_len = 0;
    int rc = ipc_build_response(frame, sizeof(frame), &frame_len, &resp);
    if (rc != 0) {
        fprintf(stderr, "[ipc_client] ipc_build_response failed (code=0x%04X)\n", code);
        return;
    }
    rc = ipc_frame_write(client_fd, frame, frame_len);
    if (rc != 0) {
        fprintf(stderr, "[ipc_client] ipc_frame_write failed: %s\n", strerror(errno));
    }
    (void)request_id;
}

// ═══════════════════════════════════════════
// PER-CLIENT HANDLER
// Called when a new client connects.
// Reads request, dispatches, sends response,
// closes connection (simple mode — one request
// per connection).
// ═══════════════════════════════════════════

void ipc_client_handle(int client_fd, pid_t client_pid) {
    int rc;
    size_t frame_len = 0;
    request_t req;
    response_t resp;

    memset(&req, 0, sizeof(req));
    memset(&resp, 0, sizeof(resp));

    // Step 1: Read the request frame from the client.
    unsigned char *frame = (unsigned char *)malloc(REQUEST_FRAME_BUF);
    if (frame == NULL) {
        fprintf(stderr, "[ipc_client] fd=%d pid=%d: out of memory for frame buffer\n",
            client_fd, (int)client_pid);
        close(client_fd);
        return;
    }

    rc = ipc_frame_read(client_fd, frame, REQUEST_FRAME_BUF, &frame_len);
    if (rc != 0) {
        // Frame read failed — just close, no response.
        fprintf(stderr, "[ipc_client] fd=%d pid=%d: frame read failed: %s\n",
            client_fd, (int)client_pid, strerror(errno));
        free(frame);
        close(client_fd);
        return;
    }

    // Step 2: Parse the frame into request_t.
    rc = ipc_parse_request(frame, frame_len, &req);
    if (rc != 0) {
        // Parse failed — send error response with code 0x0002.
        fprintf(stderr, "[ipc_client] fd=%d pid=%d: parse failed\n",
            client_fd, (int)client_pid);
        SendError(client_fd, 0, ERR_BAD_REQUEST, "malformed request frame");
        free(frame);
        close(client_fd);
        return;
    }

    // Step 3: Dispatch to the registered handler.
    rc = Dispatch(&req, &resp);
    (void)rc;  // resp is populated regardless of handler return

    // Step 4: Build the response frame.
    unsigned char resp_frame[RESPONSE_FRAME_BUF];
    size_t resp_frame_len = 0;
    rc = ipc_build_response(resp_frame, sizeof(resp_frame), &resp_frame_len, &resp);
    if (rc != 0) {
        fprintf(stderr, "[ipc_client] fd=%d pid=%d: build response failed\n",
            client_fd, (int)client_pid);
        // Fall back to a generic internal error.
        SendError(client_fd, req.request_id, 0x000D, "internal error: build response failed");
        FreeRequest(&req);
        free(frame);
        close(client_fd);
        return;
    }

    // Step 5: Write the response frame back to the client.
    rc = ipc_frame_write(client_fd, resp_frame, resp_frame_len);
    if (rc != 0) {
        fprintf(stderr, "[ipc_client] fd=%d pid=%d: write response failed: %s\n",
            client_fd, (int)client_pid, strerror(errno));
    }

    // Step 6: Free allocated param memory and rows buffer.
    FreeRequest(&req);
    if (resp.rows != NULL) {
        free(resp.rows);
        resp.rows = NULL;
    }

    // Step 7: Close the connection (simple mode — one request per connection).
    free(frame);
    close(client_fd);
}

// ═══════════════════════════════════════════
// BUILT-IN HANDLER REGISTRATION
// Called once at startup to register the
// built-in command handlers in the dispatch
// table. Idempotent — safe to call multiple
// times.
// ═══════════════════════════════════════════

void ipc_client_register_builtins(void) {
    ipc_client_register_handler(CMD_PING,   HandlePing);
    ipc_client_register_handler(CMD_TABLES, HandleTables);
    ipc_client_register_handler(CMD_SCHEMA, HandleSchema);
    ipc_client_register_handler(CMD_QUERY,  HandleQuery);
    ipc_client_register_handler(CMD_ADMIN,  HandleAdmin);
}
