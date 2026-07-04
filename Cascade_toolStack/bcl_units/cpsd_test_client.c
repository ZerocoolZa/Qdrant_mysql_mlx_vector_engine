//[@GHOST]{file_path="Cascade_toolStack/bcl_units/cpsd_test_client.c" date="2026-07-04" author="Devin" session_id="cpsd-microkernel" context="CPSD test client — sends CDB1 binary protocol ping to cpsd daemon"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE test-client"}
//[@FILEID]{id="cpsd_test_client.c" domain="cpsd_test" authority="CpsdTestClient"}
//[@SUMMARY]{summary="Test client for CPSD. Connects to Unix socket, sends CDB1 binary ping request, reads response, prints it."}
//[@CLASS]{class="CpsdTestClient" domain="cpsd_test" authority="single"}
//[@METHOD]{methods="main,build_ping,parse_response,print_hex"}

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <arpa/inet.h>

#define MAGIC "CDB1"
#define VERSION 0x01
#define MSG_REQUEST 0x01
#define MSG_RESPONSE 0x02
#define CMD_PING 4

static void PrintHex(const void *data, size_t len) {
    const unsigned char *p = (const unsigned char *)data;
    for (size_t i = 0; i < len; i++) {
        printf("%02x ", p[i]);
        if ((i + 1) % 16 == 0) printf("\n");
    }
    if (len % 16 != 0) printf("\n");
}

int main(int argc, char **argv) {
    const char *socketPath = "/tmp/cpsd_test.sock";
    if (argc > 1) socketPath = argv[1];

    // Connect to Unix socket
    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) {
        perror("socket");
        return 1;
    }

    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, socketPath, sizeof(addr.sun_path) - 1);

    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("connect");
        close(fd);
        return 1;
    }

    printf("Connected to %s\n", socketPath);

    // Build PING request frame
    // Header: MAGIC[4] + VERSION[1] + MSG_TYPE[1] + REQUEST_ID[4] + CMD_ID[2] + DB_ID[1] + PARAM_COUNT[1] + PAYLOAD_LEN[4] = 18 bytes
    unsigned char frame[18];
    memcpy(frame, MAGIC, 4);           // MAGIC
    frame[4] = VERSION;                 // VERSION
    frame[5] = MSG_REQUEST;             // MSG_TYPE
    uint32_t reqId = htonl(1);
    memcpy(frame + 6, &reqId, 4);      // REQUEST_ID
    uint16_t cmdId = htons(CMD_PING);
    memcpy(frame + 10, &cmdId, 2);     // CMD_ID
    frame[12] = 0;                      // DB_ID (0=mysql, doesn't matter for ping)
    frame[13] = 0;                      // PARAM_COUNT
    uint32_t payloadLen = htonl(0);
    memcpy(frame + 14, &payloadLen, 4); // PAYLOAD_LEN=0

    printf("Sending PING frame (%zu bytes):\n", sizeof(frame));
    PrintHex(frame, sizeof(frame));

    if (write(fd, frame, sizeof(frame)) != (ssize_t)sizeof(frame)) {
        perror("write");
        close(fd);
        return 1;
    }

    // Read response header (25 bytes)
    unsigned char respHeader[25];
    ssize_t total = 0;
    while (total < 25) {
        ssize_t n = read(fd, respHeader + total, 25 - total);
        if (n <= 0) {
            perror("read");
            close(fd);
            return 1;
        }
        total += n;
    }

    printf("\nResponse header (%zu bytes):\n", (size_t)25);
    PrintHex(respHeader, 25);

    // Parse response header
    if (memcmp(respHeader, MAGIC, 4) != 0) {
        printf("ERROR: Bad magic in response\n");
        close(fd);
        return 1;
    }
    uint8_t respVersion = respHeader[4];
    uint8_t respMsgType = respHeader[5];
    uint32_t respReqId;
    memcpy(&respReqId, respHeader + 6, 4);
    respReqId = ntohl(respReqId);
    uint8_t status = respHeader[10];
    uint16_t errorCode;
    memcpy(&errorCode, respHeader + 11, 2);
    errorCode = ntohs(errorCode);
    uint32_t rowCount, colCount, respPayloadLen;
    memcpy(&rowCount, respHeader + 13, 4); rowCount = ntohl(rowCount);
    memcpy(&colCount, respHeader + 17, 4); colCount = ntohl(colCount);
    memcpy(&respPayloadLen, respHeader + 21, 4); respPayloadLen = ntohl(respPayloadLen);

    printf("\nParsed response:\n");
    printf("  version=%d msgType=%d reqId=%u\n", respVersion, respMsgType, respReqId);
    printf("  status=%d errorCode=%u\n", status, errorCode);
    printf("  rowCount=%u colCount=%u payloadLen=%u\n", rowCount, colCount, respPayloadLen);

    // Read payload if any
    if (respPayloadLen > 0 && respPayloadLen < 65536) {
        unsigned char *payload = malloc(respPayloadLen);
        total = 0;
        while ((size_t)total < respPayloadLen) {
            ssize_t n = read(fd, payload + total, respPayloadLen - total);
            if (n <= 0) break;
            total += n;
        }
        printf("\nPayload (%zd bytes):\n", total);
        PrintHex(payload, total);

        // If status=ok and colCount>0, try to parse column names
        if (status == 0 && colCount > 0) {
            size_t offset = 0;
            printf("\nColumns:\n");
            for (uint32_t i = 0; i < colCount && offset + 2 <= (size_t)total; i++) {
                uint16_t nameLen;
                memcpy(&nameLen, payload + offset, 2);
                nameLen = ntohs(nameLen);
                offset += 2;
                if (offset + nameLen > (size_t)total) break;
                printf("  [%u] %.*s\n", i, (int)nameLen, payload + offset);
                offset += nameLen;
            }
            // Parse rows
            if (rowCount > 0) {
                printf("\nRows:\n");
                for (uint32_t r = 0; r < rowCount; r++) {
                    printf("  Row %u: ", r);
                    for (uint32_t c = 0; c < colCount && offset + 5 <= (size_t)total; c++) {
                        uint8_t cellType = payload[offset++];
                        uint32_t cellLen;
                        memcpy(&cellLen, payload + offset, 4);
                        cellLen = ntohl(cellLen);
                        offset += 4;
                        if (offset + cellLen > (size_t)total) break;
                        if (cellType == 0) {
                            printf("NULL ");
                        } else if (cellType == 3) {
                            printf("\"%.*s\" ", (int)cellLen, payload + offset);
                        } else {
                            printf("type%d(%u) ", cellType, cellLen);
                        }
                        offset += cellLen;
                    }
                    printf("\n");
                }
            }
        }

        free(payload);
    }

    close(fd);
    printf("\nDONE\n");
    return 0;
}
