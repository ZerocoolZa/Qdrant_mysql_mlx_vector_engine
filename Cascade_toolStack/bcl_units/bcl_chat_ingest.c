//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_chat_ingest.c" date="2026-07-04" author="Devin" session_id="bcl-chat-ingest-impl" context="BCL unit for AST-based chat file ingestion — parse JSON/markdown chat exports, extract code blocks, store to MySQL vb_shared.chat_ingestions. Converted from stub to real implementation."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="bcl_chat_ingest.c" domain="cascade_tools" authority="ChatIngest"}
//[@SUMMARY]{summary="AST-based chat file ingester. Parses JSON or markdown chat exports, extracts fenced code blocks (```python, ```c, etc.), stores to MySQL vb_shared.chat_ingestions table. Commands: ingest, ingest_dir, stats, read_state, set_config."}
//[@CLASS]{class="ChatIngest" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="IngestFile" type="internal"}
//[@METHOD]{method="IngestDir" type="internal"}
//[@METHOD]{method="ExtractCodeBlocks" type="internal"}
//[@METHOD]{method="ExtractJsonContent" type="internal"}
//[@METHOD]{method="ConnectMysql" type="internal"}
//[@METHOD]{method="EnsureTable" type="internal"}
//[@METHOD]{method="StoreBlock" type="internal"}
//[@REVIEW]{[@date<2026-07-04>][@reviewer<devin>][@status<implementation>][@notes<Real implementation. MySQL connect localhost/root/no-pass. Simple string-search JSON + markdown fence parsing. No printf/fprintf — errors go to STATE.last_error.>][@todos<>]}

/*
 * bcl_chat_ingest.c — AST-based chat file ingester
 *
 * BCL IN:  [@RUN]{[@CMD]{ingest}[@PATH]{/path/to/chat.json}[@DB]{vb_shared}}
 *          [@RUN]{[@CMD]{ingest_dir}[@PATH]{/path/to/chats/}[@DB]{vb_shared}}
 *          [@RUN]{[@CMD]{stats}[@DB]{vb_shared}}
 *          [@RUN]{[@CMD]{read_state}}
 *          [@RUN]{[@CMD]{set_config}[@DB]{...}[@MAX_BLOCK]{...}[@LANGS]{python,c}}
 * BCL OUT: [@OK]{[@FILE]{...}[@BLOCKS]{N}[@DB]{...}}
 * BCL ERR: [@ERR]{[@CODE]{N}[@DESC]{...}}
 *
 * Table schema (created if not exists):
 *   chat_ingestions (
 *     id INT AUTO_INCREMENT PRIMARY KEY,
 *     source_file TEXT,
 *     message_role VARCHAR(32),
 *     code_block LONGTEXT,
 *     language VARCHAR(32),
 *     timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
 */

#include "bcl_toolstack.h"
#include <mysql.h>
#include <dirent.h>
#include <sys/stat.h>

/* ===== DIM BLOCK ===== */

#define CHAT_MAX_FILE     1048576      /* 1 MB max file size */
#define CHAT_MAX_BLOCK    65536        /* max single code block size */
#define CHAT_MAX_LANGS    256          /* languages filter buffer */
#define CHAT_MAX_ROLE     32           /* message role buffer */

/* ===== STATE ===== */

static struct {
    int  initialized;
    int  files_ingested;
    int  blocks_extracted;
    char last_path[TOOL_MAX_PATH];
    char last_error[256];
    char db_name[64];
    int  max_block_size;
    char languages[CHAT_MAX_LANGS];    /* comma-separated filter, empty = all */
} STATE;

/* ===== SECTION: MYSQL CONNECTION ===== */

static MYSQL *connect_mysql(const char *db_name) {
    MYSQL *conn = mysql_init(NULL);
    if (!conn) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "mysql_init failed");
        return NULL;
    }
    if (!mysql_real_connect(conn, "localhost", "root", "", db_name,
                            0, NULL, 0)) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
            "mysql connect: %s", mysql_error(conn));
        mysql_close(conn);
        return NULL;
    }
    return conn;
}

static int ensure_table(MYSQL *conn) {
    const char *sql =
        "CREATE TABLE IF NOT EXISTS chat_ingestions ("
        "  id INT AUTO_INCREMENT PRIMARY KEY,"
        "  source_file TEXT,"
        "  message_role VARCHAR(32),"
        "  code_block LONGTEXT,"
        "  language VARCHAR(32),"
        "  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4";
    if (mysql_query(conn, sql)) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
            "create table: %s", mysql_error(conn));
        return 0;
    }
    return 1;
}

/* ===== SECTION: CODE BLOCK EXTRACTION ===== */

/* Check if a language is allowed by the filter. Empty filter = all allowed. */
static int lang_allowed(const char *lang) {
    if (!STATE.languages[0]) return 1;
    if (!lang[0]) return 1;  /* unlabeled blocks pass if filter empty */
    char needle[64];
    snprintf(needle, sizeof(needle), ",%s,", lang);
    char haystack[CHAT_MAX_LANGS + 2];
    snprintf(haystack, sizeof(haystack), ",%s,", STATE.languages);
    return strstr(haystack, needle) != NULL;
}

/* Extract fenced code blocks from a text buffer.
   Calls cb(userdata, lang, code) for each block found.
   Returns count of blocks extracted. */
typedef void (*BlockCallback)(void *ud, const char *lang, const char *code);

static int extract_code_blocks(const char *text, size_t text_len,
                                BlockCallback cb, void *ud) {
    int count = 0;
    size_t i = 0;
    while (i < text_len) {
        /* find ``` marker at start of line */
        if (text[i] == '`' && i + 2 < text_len &&
            text[i + 1] == '`' && text[i + 2] == '`') {
            /* extract language tag after ``` */
            size_t lang_start = i + 3;
            size_t lang_end = lang_start;
            while (lang_end < text_len && text[lang_end] != '\n' &&
                   text[lang_end] != '\r' && text[lang_end] != ' ' &&
                   (lang_end - lang_start) < 31) {
                lang_end++;
            }
            char lang[32] = {0};
            size_t lang_len = lang_end - lang_start;
            if (lang_len > 0 && lang_len < 32) {
                memcpy(lang, text + lang_start, lang_len);
                lang[lang_len] = '\0';
            }
            /* advance to end of line (language line) */
            size_t code_start = lang_end;
            while (code_start < text_len && text[code_start] != '\n') code_start++;
            if (code_start < text_len) code_start++;  /* skip the newline */

            /* find closing ``` */
            size_t code_end = code_start;
            int found_close = 0;
            while (code_end < text_len) {
                if (text[code_end] == '`' && code_end + 2 < text_len &&
                    text[code_end + 1] == '`' && text[code_end + 2] == '`') {
                    found_close = 1;
                    break;
                }
                code_end++;
            }
            if (!found_close) break;  /* unterminated block, stop */

            size_t code_len = code_end - code_start;
            if (code_len > CHAT_MAX_BLOCK - 1) code_len = CHAT_MAX_BLOCK - 1;
            if (code_len > 0 && code_len <= (size_t)STATE.max_block_size) {
                char code[CHAT_MAX_BLOCK];
                memcpy(code, text + code_start, code_len);
                code[code_len] = '\0';
                if (lang_allowed(lang)) {
                    cb(ud, lang, code);
                    count++;
                }
            }
            /* advance past closing ``` */
            i = code_end + 3;
        } else {
            i++;
        }
    }
    return count;
}

/* ===== SECTION: JSON CONTENT EXTRACTION ===== */

/* Simple JSON string-value extractor: find "key" : "value" pairs.
   Calls cb(userdata, value) for each "content" field value found.
   This is a naive scanner — not a real JSON parser, but sufficient for
   chat export formats that embed text in "content" fields. */
typedef void (*ContentCallback)(void *ud, const char *content, size_t len);

static void extract_json_content(const char *json, size_t json_len,
                                  ContentCallback cb, void *ud) {
    const char *p = json;
    const char *end = json + json_len;
    while (p < end) {
        /* find "content" key */
        const char *key = strstr(p, "\"content\"");
        if (!key || key >= end) break;
        p = key + 9;
        /* skip whitespace and colon */
        while (p < end && (*p == ' ' || *p == '\t' || *p == ':' )) p++;
        if (p >= end) break;
        /* expect opening quote */
        if (*p != '"') continue;
        p++;  /* skip opening quote */
        const char *val_start = p;
        /* find closing quote (handle escapes) */
        while (p < end) {
            if (*p == '\\' && p + 1 < end) { p += 2; continue; }
            if (*p == '"') break;
            p++;
        }
        if (p >= end) break;
        size_t val_len = p - val_start;
        if (val_len > 0) {
            cb(ud, val_start, val_len);
        }
        p++;  /* skip closing quote */
    }
}

/* ===== SECTION: INGEST ONE FILE ===== */

/* Callback context for block storage */
typedef struct {
    MYSQL *conn;
    const char *source_file;
    const char *role;
    int stored;
} BlockCtx;

static void store_block_cb(void *ud, const char *lang, const char *code) {
    BlockCtx *ctx = (BlockCtx *)ud;
    char elang[64];
    mysql_real_escape_string(ctx->conn, elang, lang,
                              (unsigned long)strlen(lang));
    char ecode[CHAT_MAX_BLOCK * 2];
    mysql_real_escape_string(ctx->conn, ecode, code,
                              (unsigned long)strlen(code));
    char esrc[TOOL_MAX_PATH * 2];
    mysql_real_escape_string(ctx->conn, esrc, ctx->source_file,
                              (unsigned long)strlen(ctx->source_file));
    char erole[64];
    mysql_real_escape_string(ctx->conn, erole, ctx->role,
                              (unsigned long)strlen(ctx->role));
    char sql[CHAT_MAX_BLOCK * 2 + 1024];
    snprintf(sql, sizeof(sql),
        "INSERT INTO chat_ingestions (source_file, message_role, code_block, language) "
        "VALUES ('%s', '%s', '%s', '%s')",
        esrc, erole, ecode, elang);
    if (mysql_query(ctx->conn, sql) == 0) {
        ctx->stored++;
    }
}

/* Callback context for JSON content collection */
typedef struct {
    char *buf;
    size_t buf_len;
    size_t buf_used;
} ContentCtx;

static void collect_content_cb(void *ud, const char *content, size_t len) {
    ContentCtx *ctx = (ContentCtx *)ud;
    if (ctx->buf_used + len + 2 < ctx->buf_len) {
        memcpy(ctx->buf + ctx->buf_used, content, len);
        ctx->buf_used += len;
        ctx->buf[ctx->buf_used++] = '\n';
        ctx->buf[ctx->buf_used] = '\0';
    }
}

static int ingest_file(MYSQL *conn, const char *path) {
    /* read file into memory */
    FILE *f = fopen(path, "rb");
    if (!f) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
            "cannot open: %s", path);
        return 0;
    }
    fseek(f, 0, SEEK_END);
    long fsize = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (fsize <= 0 || fsize > CHAT_MAX_FILE) {
        fclose(f);
        snprintf(STATE.last_error, sizeof(STATE.last_error),
            "file too large or empty: %s", path);
        return 0;
    }
    char *raw = malloc(fsize + 1);
    if (!raw) { fclose(f); return 0; }
    fread(raw, 1, fsize, f);
    raw[fsize] = '\0';
    fclose(f);

    /* determine file type by extension */
    int is_json = 0;
    const char *ext = strrchr(path, '.');
    if (ext && (strcmp(ext, ".json") == 0 || strcmp(ext, ".JSON") == 0)) {
        is_json = 1;
    }

    /* For JSON: extract all "content" field values into one big text buffer,
       then scan that buffer for fenced code blocks.
       For markdown: scan the raw text directly. */
    char *scan_text;
    size_t scan_len;
    char *json_buf = NULL;

    if (is_json) {
        json_buf = malloc(CHAT_MAX_FILE);
        if (!json_buf) { free(raw); return 0; }
        ContentCtx cctx = { json_buf, CHAT_MAX_FILE, 0 };
        json_buf[0] = '\0';
        extract_json_content(raw, (size_t)fsize, collect_content_cb, &cctx);
        scan_text = json_buf;
        scan_len = cctx.buf_used;
    } else {
        scan_text = raw;
        scan_len = (size_t)fsize;
    }

    /* extract and store code blocks */
    BlockCtx bctx = { conn, path, "assistant", 0 };
    int blocks = extract_code_blocks(scan_text, scan_len,
                                      store_block_cb, &bctx);

    STATE.files_ingested++;
    STATE.blocks_extracted += blocks;
    strncpy(STATE.last_path, path, sizeof(STATE.last_path) - 1);
    STATE.last_path[sizeof(STATE.last_path) - 1] = '\0';

    free(raw);
    if (json_buf) free(json_buf);
    return blocks;
}

/* ===== SECTION: INGEST DIRECTORY ===== */

static int ingest_dir(MYSQL *conn, const char *dir_path) {
    DIR *d = opendir(dir_path);
    if (!d) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
            "cannot open dir: %s", dir_path);
        return -1;
    }
    int total_blocks = 0;
    struct dirent *ent;
    while ((ent = readdir(d)) != NULL) {
        if (ent->d_name[0] == '.') continue;
        const char *ext = strrchr(ent->d_name, '.');
        if (!ext) continue;
        if (strcmp(ext, ".json") != 0 && strcmp(ext, ".JSON") != 0 &&
            strcmp(ext, ".md") != 0 && strcmp(ext, ".MD") != 0 &&
            strcmp(ext, ".markdown") != 0) continue;
        char full[TOOL_MAX_PATH];
        snprintf(full, sizeof(full), "%s/%s", dir_path, ent->d_name);
        int b = ingest_file(conn, full);
        if (b >= 0) {
            total_blocks += b;
        }
    }
    closedir(d);
    return total_blocks;
}

/* ===== SECTION: UNIT INTERFACE ===== */

int ChatIngest_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    strncpy(STATE.db_name, "vb_shared", sizeof(STATE.db_name) - 1);
    STATE.max_block_size = CHAT_MAX_BLOCK - 1;
    STATE.languages[0] = '\0';
    return 1;
}

int ChatIngest_Run(const char *cmd, const char *bcl_in,
                    char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) ChatIngest_Init();

    if (strcmp(cmd, "ingest") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[TOOL_MAX_PATH] = {0};
        char db[64] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Extract(&parse, "DB", db, sizeof(db));
        BclParser_Free(&parse);
        if (!path[0]) return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        if (db[0]) strncpy(STATE.db_name, db, sizeof(STATE.db_name) - 1);

        MYSQL *conn = connect_mysql(STATE.db_name);
        if (!conn) return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
        if (!ensure_table(conn)) {
            mysql_close(conn);
            return BclResult_Err(bcl_out, out_sz, 11, STATE.last_error);
        }
        int blocks = ingest_file(conn, path);
        mysql_close(conn);
        if (blocks < 0) return BclResult_Err(bcl_out, out_sz, 12, STATE.last_error);
        char body[TOOL_MAX_PATH + 128];
        snprintf(body, sizeof(body), "[@FILE]{%s}[@BLOCKS]{%d}[@DB]{%s}",
            path, blocks, STATE.db_name);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    if (strcmp(cmd, "ingest_dir") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[TOOL_MAX_PATH] = {0};
        char db[64] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Extract(&parse, "DB", db, sizeof(db));
        BclParser_Free(&parse);
        if (!path[0]) return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        if (db[0]) strncpy(STATE.db_name, db, sizeof(STATE.db_name) - 1);

        MYSQL *conn = connect_mysql(STATE.db_name);
        if (!conn) return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
        if (!ensure_table(conn)) {
            mysql_close(conn);
            return BclResult_Err(bcl_out, out_sz, 11, STATE.last_error);
        }
        int blocks = ingest_dir(conn, path);
        mysql_close(conn);
        if (blocks < 0) return BclResult_Err(bcl_out, out_sz, 13, STATE.last_error);
        char body[TOOL_MAX_PATH + 128];
        snprintf(body, sizeof(body), "[@DIR]{%s}[@BLOCKS]{%d}[@DB]{%s}",
            path, blocks, STATE.db_name);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    if (strcmp(cmd, "stats") == 0) {
        MYSQL *conn = connect_mysql(STATE.db_name);
        if (!conn) return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
        char sql[256];
        snprintf(sql, sizeof(sql),
            "SELECT COUNT(*), COUNT(DISTINCT source_file) FROM chat_ingestions");
        int total_blocks = 0;
        int total_files = 0;
        if (mysql_query(conn, sql) == 0) {
            MYSQL_RES *res = mysql_store_result(conn);
            if (res) {
                MYSQL_ROW row = mysql_fetch_row(res);
                if (row) {
                    total_blocks = atoi(row[0]);
                    total_files = atoi(row[1]);
                }
                mysql_free_result(res);
            }
        }
        /* language breakdown */
        char lang_body[1024] = {0};
        snprintf(sql, sizeof(sql),
            "SELECT language, COUNT(*) FROM chat_ingestions GROUP BY language");
        if (mysql_query(conn, sql) == 0) {
            MYSQL_RES *res = mysql_store_result(conn);
            if (res) {
                MYSQL_ROW row;
                int off = 0;
                while ((row = mysql_fetch_row(res)) && off < 900) {
                    off += snprintf(lang_body + off, sizeof(lang_body) - off,
                        "[@LANG]{[@NAME]{%s}[@COUNT]{%s}}",
                        row[0] ? row[0] : "", row[1] ? row[1] : "0");
                }
                mysql_free_result(res);
            }
        }
        mysql_close(conn);
        char body[2048];
        snprintf(body, sizeof(body),
            "[@FILES]{%d}[@BLOCKS]{%d}[@DB]{%s}[@INGESTED]{%d}[@EXTRACTED]{%d}%s",
            total_files, total_blocks, STATE.db_name,
            STATE.files_ingested, STATE.blocks_extracted, lang_body);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    if (strcmp(cmd, "read_state") == 0) {
        char body[TOOL_MAX_PATH + 512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@FILES]{%d}[@BLOCKS]{%d}[@LAST_PATH]{%s}"
            "[@DB]{%s}[@ERROR]{%s}[@MAX_BLOCK]{%d}[@LANGS]{%s}",
            STATE.initialized, STATE.files_ingested, STATE.blocks_extracted,
            STATE.last_path[0] ? STATE.last_path : "none",
            STATE.db_name,
            STATE.last_error[0] ? STATE.last_error : "none",
            STATE.max_block_size,
            STATE.languages[0] ? STATE.languages : "all");
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char db[64] = {0};
        char max_block[32] = {0};
        char langs[CHAT_MAX_LANGS] = {0};
        BclParser_Extract(&parse, "DB", db, sizeof(db));
        BclParser_Extract(&parse, "MAX_BLOCK", max_block, sizeof(max_block));
        BclParser_Extract(&parse, "LANGS", langs, sizeof(langs));
        BclParser_Free(&parse);
        if (db[0]) strncpy(STATE.db_name, db, sizeof(STATE.db_name) - 1);
        if (max_block[0]) STATE.max_block_size = atoi(max_block);
        if (langs[0]) strncpy(STATE.languages, langs, sizeof(STATE.languages) - 1);
        char body[512];
        snprintf(body, sizeof(body),
            "[@DB]{%s}[@MAX_BLOCK]{%d}[@LANGS]{%s}",
            STATE.db_name, STATE.max_block_size,
            STATE.languages[0] ? STATE.languages : "all");
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    return BclResult_Err(bcl_out, out_sz, 404, "unknown command");
}

int ChatIngest_Close(void) {
    STATE.initialized = 0;
    return 1;
}

const char * ChatIngest_State(void) {
    static char buf[512];
    snprintf(buf, sizeof(buf),
        "ChatIngest: initialized=%d files=%d blocks=%d db=%s",
        STATE.initialized, STATE.files_ingested, STATE.blocks_extracted,
        STATE.db_name);
    return buf;
}
