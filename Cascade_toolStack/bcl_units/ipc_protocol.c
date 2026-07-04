//[@GHOST]{file_path="Cascade_toolStack/bcl_units/ipc_protocol.c" date="2026-07-04" author="Devin" session_id="cpsd-microkernel" context="CPSD Layer 1: Binary protocol — CDB1 magic, big-endian framing, param serialization"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE no-print binary-protocol"}
//[@FILEID]{id="ipc_protocol.c" domain="cpsd_ipc" authority="CpsdProtocol"}
//[@SUMMARY]{summary="Binary wire protocol. CDB1 magic, big-endian framing. Serializes/deserializes requests and responses. Handles partial reads/writes. Validates magic and version."}
//[@CLASS]{class="CpsdProtocol" domain="cpsd_ipc" authority="single"}
//[@METHOD]{methods="ipc_frame_read,ipc_frame_write,ipc_parse_request,ipc_build_response"}

#include "cpsd.h"
#include <arpa/inet.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <errno.h>

/* ─── Wire format constants ─── */
#define REQ_HEADER_LEN    18
#define RESP_HEADER_LEN   25
#define MAGIC_LEN         4

static const uint8_t CPSD_MAGIC_BYTES[MAGIC_LEN] = { 0x43, 0x44, 0x42, 0x31 };

/* ─── Helpers ─── */

/* Read exactly n bytes from fd into buf, looping over partial reads.
   Returns 0 on success, -1 on error or premature EOF. */
static int ReadFull(int fd, void *buf, size_t n) {
    size_t total = 0;
    while (total < n) {
        ssize_t r = read(fd, (char *)buf + total, n - total);
        if (r < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        if (r == 0) return -1;  /* EOF before full read */
        total += (size_t)r;
    }
    return 0;
}

/* Write exactly n bytes from buf to fd, looping over partial writes.
   Returns 0 on success, -1 on error. */
static int WriteFull(int fd, const void *buf, size_t n) {
    size_t total = 0;
    while (total < n) {
        ssize_t w = write(fd, (const char *)buf + total, n - total);
        if (w < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        total += (size_t)w;
    }
    return 0;
}

/* Read a big-endian uint32 from a possibly-unaligned buffer position. */
static uint32_t ReadBe32(const uint8_t *p) {
    uint32_t v;
    memcpy(&v, p, 4);
    return ntohl(v);
}

/* Read a big-endian uint16 from a possibly-unaligned buffer position. */
static uint16_t ReadBe16(const uint8_t *p) {
    uint16_t v;
    memcpy(&v, p, 2);
    return ntohs(v);
}

/* Write a big-endian uint32 into a buffer. */
static void WriteBe32(uint8_t *p, uint32_t v) {
    uint32_t net = htonl(v);
    memcpy(p, &net, 4);
}

/* Write a big-endian uint16 into a buffer. */
static void WriteBe16(uint8_t *p, uint16_t v) {
    uint16_t net = htons(v);
    memcpy(p, &net, 2);
}

/* ─── ipc_frame_read ─── */
/* Read a full CDB1 frame from fd into the caller-provided buffer.
   First reads the 18-byte header, extracts PAYLOAD_LEN, then reads
   the payload. Validates MAGIC and VERSION.
   Returns 0 on success (frame_len set), -1 on error. */
int ipc_frame_read(int fd, void *frame, size_t frame_size, size_t *frame_len) {
    if (!frame || !frame_len) return -1;
    if (frame_size < REQ_HEADER_LEN) return -1;

    /* Read the 18-byte header */
    if (ReadFull(fd, frame, REQ_HEADER_LEN) != 0) return -1;

    const uint8_t *p = (const uint8_t *)frame;

    /* Validate MAGIC */
    if (memcmp(p, CPSD_MAGIC_BYTES, MAGIC_LEN) != 0) return -1;

    /* Validate VERSION */
    if (p[4] != CPSD_PROTOCOL_VERSION) return -1;

    /* PAYLOAD_LEN at offset 14 (big-endian uint32) */
    uint32_t payload_len = ReadBe32(p + 14);

    /* Total frame = header + payload */
    size_t total = REQ_HEADER_LEN + (size_t)payload_len;
    if (total > frame_size) return -1;

    /* Read the payload (if any) */
    if (payload_len > 0) {
        if (ReadFull(fd, (char *)frame + REQ_HEADER_LEN, payload_len) != 0)
            return -1;
    }

    *frame_len = total;
    return 0;
}

/* ─── ipc_frame_write ─── */
/* Write a full frame to fd, looping over partial writes.
   Returns 0 on success, -1 on error. */
int ipc_frame_write(int fd, const void *frame, size_t frame_len) {
    if (!frame || frame_len == 0) return -1;
    return WriteFull(fd, frame, frame_len);
}

/* ─── ipc_parse_request ─── */
/* Parse a binary frame into a request_t struct.
   Allocates memory for param values (caller must free each
   req->params[i].value via free()).
   Returns 0 on success, -1 on error. */
int ipc_parse_request(const void *frame, size_t len, request_t *req) {
    if (!frame || !req) return -1;
    if (len < REQ_HEADER_LEN) return -1;

    const uint8_t *p = (const uint8_t *)frame;

    /* Validate MAGIC */
    if (memcmp(p, CPSD_MAGIC_BYTES, MAGIC_LEN) != 0) return -1;

    /* Validate VERSION */
    if (p[4] != CPSD_PROTOCOL_VERSION) return -1;

    /* Validate MSG_TYPE = request */
    if (p[5] != (uint8_t)MSG_REQUEST) return -1;

    memset(req, 0, sizeof(request_t));

    req->version = p[4];
    req->msg_type = p[5];

    /* REQUEST_ID at offset 6 (big-endian uint32) */
    req->request_id = ReadBe32(p + 6);

    /* CMD_ID at offset 10 (big-endian uint16) */
    req->cmd_id = ReadBe16(p + 10);

    /* DB_ID at offset 12 */
    req->db_id = p[12];

    /* PARAM_COUNT at offset 13 */
    req->param_count = p[13];
    if (req->param_count > CPSD_MAX_PARAMS) return -1;

    /* PAYLOAD_LEN at offset 14 */
    uint32_t payload_len = ReadBe32(p + 14);
    if (len < REQ_HEADER_LEN + (size_t)payload_len) return -1;

    /* Parse params from the payload starting at offset 18 */
    size_t off = REQ_HEADER_LEN;
    size_t payload_end = REQ_HEADER_LEN + (size_t)payload_len;

    for (int i = 0; i < req->param_count; i++) {
        /* Each param: TYPE[1] + LEN[4] + VALUE[LEN] = 5-byte header */
        if (off + 5 > payload_end) return -1;

        uint8_t ptype = p[off];
        off += 1;

        uint32_t plen = ReadBe32(p + off);
        off += 4;

        if (plen > CPSD_MAX_PARAM_LEN) return -1;
        if (off + plen > payload_end) return -1;

        req->params[i].type = (param_type_t)ptype;
        req->params[i].len = plen;
        req->params[i].value = NULL;

        if (ptype == (uint8_t)PARAM_NULL) {
            /* NULL: no value bytes, len should be 0 */
            if (plen != 0) return -1;
        } else if (ptype == (uint8_t)PARAM_STRING) {
            /* STRING: allocate len+1, null-terminate */
            req->params[i].value = malloc((size_t)plen + 1);
            if (!req->params[i].value) return -1;
            if (plen > 0) memcpy(req->params[i].value, p + off, plen);
            ((char *)req->params[i].value)[plen] = '\0';
        } else {
            /* INT32, INT64, DOUBLE, BLOB, BOOL: allocate len bytes */
            if (plen > 0) {
                req->params[i].value = malloc(plen);
                if (!req->params[i].value) return -1;
                memcpy(req->params[i].value, p + off, plen);
            }
        }

        off += plen;
    }

    /* Any remaining payload bytes after params are SQL text (CMD_QUERY) */
    if (off < payload_end) {
        size_t sql_len = payload_end - off;
        if (sql_len >= CPSD_MAX_SQL) sql_len = CPSD_MAX_SQL - 1;
        memcpy(req->sql, p + off, sql_len);
        req->sql[sql_len] = '\0';
    }

    return 0;
}

/* ─── ipc_build_response ─── */
/* Serialize a response_t into a binary frame.
   Returns 0 on success (frame_len set), -1 on error
   (e.g. frame_size too small). */
int ipc_build_response(void *frame, size_t frame_size, size_t *frame_len,
                       const response_t *resp) {
    if (!frame || !frame_len || !resp) return -1;
    if (frame_size < RESP_HEADER_LEN) return -1;

    uint8_t *p = (uint8_t *)frame;

    /* ── Compute payload size ── */
    size_t payload_len = 0;

    if (resp->status == 1) {
        /* Error payload: LEN[2] + MSG[LEN] */
        size_t msg_len = strlen(resp->error_msg);
        if (msg_len > 0xFFFF) msg_len = 0xFFFF;
        payload_len = 2 + msg_len;
    } else {
        /* OK payload: column names block + rows block */
        for (uint32_t i = 0; i < resp->col_count; i++) {
            size_t name_len = strlen(resp->columns[i]);
            if (name_len > 0xFFFF) name_len = 0xFFFF;
            payload_len += 2 + name_len;
        }
        /* Rows: if rows is NULL or rows_len is 0, write 0 rows */
        if (resp->rows && resp->rows_len > 0) {
            payload_len += resp->rows_len;
        }
    }

    size_t total = RESP_HEADER_LEN + payload_len;
    if (total > frame_size) return -1;

    /* ── Write header (25 bytes) ── */
    memcpy(p, CPSD_MAGIC_BYTES, MAGIC_LEN);   /* offset 0: MAGIC */
    p[4] = CPSD_PROTOCOL_VERSION;              /* offset 4: VERSION */
    p[5] = (uint8_t)MSG_RESPONSE;              /* offset 5: MSG_TYPE = 0x02 */

    /* offset 6: REQUEST_ID — response_t has no request_id field, write 0 */
    WriteBe32(p + 6, 0);

    p[10] = resp->status;                      /* offset 10: STATUS */
    WriteBe16(p + 11, resp->error_code);       /* offset 11: ERROR_CODE */
    WriteBe32(p + 13, resp->row_count);        /* offset 13: ROW_COUNT */
    WriteBe32(p + 17, resp->col_count);        /* offset 17: COL_COUNT */
    WriteBe32(p + 21, (uint32_t)payload_len);  /* offset 21: PAYLOAD_LEN */

    /* ── Write payload starting at offset 25 ── */
    size_t off = RESP_HEADER_LEN;

    if (resp->status == 1) {
        /* Error message: LEN[2] + MSG[LEN] */
        size_t msg_len = strlen(resp->error_msg);
        if (msg_len > 0xFFFF) msg_len = 0xFFFF;
        WriteBe16(p + off, (uint16_t)msg_len);
        off += 2;
        if (msg_len > 0) {
            memcpy(p + off, resp->error_msg, msg_len);
            off += msg_len;
        }
    } else {
        /* Column names: for each column, LEN[2] + NAME[LEN] */
        for (uint32_t i = 0; i < resp->col_count; i++) {
            size_t name_len = strlen(resp->columns[i]);
            if (name_len > 0xFFFF) name_len = 0xFFFF;
            WriteBe16(p + off, (uint16_t)name_len);
            off += 2;
            if (name_len > 0) {
                memcpy(p + off, resp->columns[i], name_len);
                off += name_len;
            }
        }
        /* Rows block: copy pre-serialized row data if present */
        if (resp->rows && resp->rows_len > 0) {
            memcpy(p + off, resp->rows, resp->rows_len);
            off += resp->rows_len;
        }
    }

    *frame_len = total;
    return 0;
}
