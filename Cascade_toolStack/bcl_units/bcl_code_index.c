//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_code_index.c" date="2026-07-04" author="devin" session_id="bcl-vsstyle-units" context="BCL unit for indexing code files into MySQL vb_code_test tables. Source: core/Dom_Vsstyle/vbs_code_index.py. Commands: open, index_file, index_dir, close_db, read_state, set_config."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_code_index.c" domain="bcl_units" authority="CodeIndex"}
//[@SUMMARY]{summary="Code indexer. Parses .py files, extracts classes/methods and VBStyle bracket tags, writes to MySQL vb_code_test.vb_classes and vb_methods. Commands: open, index_file, index_dir, close_db, read_state, set_config, stats, scan_headers."}
//[@CLASS]{class="CodeIndex" domain="bcl_units" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="Open" type="command"}
//[@METHOD]{method="IndexFile" type="command"}
//[@METHOD]{method="IndexDir" type="command"}
//[@METHOD]{method="CloseDb" type="command"}
//[@METHOD]{method="Stats" type="query"}
//[@METHOD]{method="ScanHeaders" type="command"}

#include "bcl_toolstack.h"
#include <mysql.h>
#include <dirent.h>
#include <sys/stat.h>
#include <ctype.h>

/* ===== DIM BLOCK ===== */

#define CI_MAX_PATH         4096
#define CI_MAX_FILE         262144
#define CI_MAX_CLASSES      128
#define CI_MAX_METHODS      512
#define CI_MAX_NAME         128
#define CI_MAX_DESC         512
#define CI_MAX_BODY         16384
#define CI_MAX_QUERY        4096
#define CI_MAX_FILES        500
#define CI_MAX_LINE         1024
#define CI_SKIP_DIRS        8

typedef struct {
    char name[CI_MAX_NAME];
    int  method_count;
    int  has_run;
    int  has_ghost;
    int  has_vbs;
} ClassEntry;

typedef struct {
    char name[CI_MAX_NAME];
    char class_name[CI_MAX_NAME];
} MethodEntry;

typedef struct {
    char tag[64];
    int  count;
} BracketTag;

static struct {
    int        initialized;
    int        connected;
    MYSQL     *conn;
    char       host[256];
    char       user[64];
    char       pass[128];
    char       socket[256];
    int        port;
    int        files_indexed;
    int        classes_indexed;
    int        methods_indexed;
    char       last_error[256];
    char       last_file[CI_MAX_NAME];
    ClassEntry classes[CI_MAX_CLASSES];
    MethodEntry methods[CI_MAX_METHODS];
    int        class_count;
    int        method_count;
    BracketTag tags[64];
    int        tag_count;
} STATE;

static const char *SKIP_DIRS[CI_SKIP_DIRS] = {
    ".", "..", ".git", "__pycache__", "node_modules", ".venv", "venv", ".codex"
};

static int IsSkipDir(const char *name) {
    for (int i = 0; i < CI_SKIP_DIRS; i++) {
        if (strcmp(name, SKIP_DIRS[i]) == 0) return 1;
    }
    return 0;
}

static void EnsureConnected(void) {
    if (STATE.connected && STATE.conn) return;
    STATE.conn = mysql_init(NULL);
    if (!STATE.conn) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "mysql_init failed");
        return;
    }
    STATE.conn = mysql_real_connect(STATE.conn,
        STATE.host[0] ? STATE.host : "localhost",
        STATE.user[0] ? STATE.user : "root",
        STATE.pass[0] ? STATE.pass : "",
        "vb_code_test", STATE.port,
        STATE.socket[0] ? STATE.socket : NULL, 0);
    if (!STATE.conn) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "%s", mysql_error(STATE.conn));
        mysql_close(STATE.conn);
        STATE.conn = NULL;
        return;
    }
    STATE.connected = 1;
}

static int EscapeString(MYSQL *conn, char *out, size_t out_sz, const char *in) {
    if (!in || !in[0]) {
        out[0] = '\0';
        return 0;
    }
    return mysql_real_escape_string(conn, out, in, (unsigned long)strlen(in));
}

/* Register or increment a bracket tag in STATE.tags (max 64 unique tags) */
static void RegisterBracketTag(const char *tag) {
    if (!tag || !tag[0]) return;
    for (int i = 0; i < STATE.tag_count; i++) {
        if (strcmp(STATE.tags[i].tag, tag) == 0) {
            STATE.tags[i].count++;
            return;
        }
    }
    if (STATE.tag_count < 64) {
        strncpy(STATE.tags[STATE.tag_count].tag, tag, 63);
        STATE.tags[STATE.tag_count].tag[63] = '\0';
        STATE.tags[STATE.tag_count].count = 1;
        STATE.tag_count++;
    }
}

/* Scan content for [@TAG] patterns (TAG = uppercase letters/digits/underscore) */
static void ScanBracketTags(const char *content, int len) {
    const char *p = content;
    const char *end = content + len;
    while (p < end) {
        const char *at = memchr(p, '[', (size_t)(end - p));
        if (!at) break;
        if (at + 1 < end && at[1] == '@') {
            const char *tag_start = at + 2;
            const char *tag_end = tag_start;
            while (tag_end < end) {
                char c = *tag_end;
                if ((c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_') {
                    tag_end++;
                } else {
                    break;
                }
            }
            int tlen = (int)(tag_end - tag_start);
            if (tlen > 0 && tlen < 64 && tag_end < end && *tag_end == ']') {
                char tag[64];
                memcpy(tag, tag_start, tlen);
                tag[tlen] = '\0';
                RegisterBracketTag(tag);
            }
            p = tag_end;
        } else {
            p = at + 1;
        }
    }
}

/* Parse Python source: extract classes and methods */
static void ParsePython(const char *content, int len) {
    STATE.class_count = 0;
    STATE.method_count = 0;
    STATE.tag_count = 0;
    memset(STATE.tags, 0, sizeof(STATE.tags));
    
    int has_ghost = (strstr(content, "[@GHOST]") != NULL && (strstr(content, "[@GHOST]") - content) < 500);
    int has_vbs = (strstr(content, "[@VBSTYLE]") != NULL && (strstr(content, "[@VBSTYLE]") - content) < 500);
    
    char current_class[CI_MAX_NAME] = {0};
    const char *p = content;
    const char *end = content + len;
    int line_num = 1;
    
    while (p < end) {
        /* Find end of line */
        const char *eol = strchr(p, '\n');
        if (!eol) eol = end;
        int line_len = (int)(eol - p);
        if (line_len >= CI_MAX_LINE) line_len = CI_MAX_LINE - 1;
        
        char line[CI_MAX_LINE];
        memcpy(line, p, line_len);
        line[line_len] = '\0';
        
        /* Trim leading whitespace */
        char *trimmed = line;
        while (*trimmed == ' ' || *trimmed == '\t') trimmed++;
        
        /* Check for class definition */
        if (strncmp(trimmed, "class ", 6) == 0) {
            char *name_start = trimmed + 6;
            char *name_end = name_start;
            while (*name_end && *name_end != '(' && *name_end != ':' && *name_end != ' ' && *name_end != '\n') {
                name_end++;
            }
            int nlen = (int)(name_end - name_start);
            if (nlen > 0 && nlen < CI_MAX_NAME && STATE.class_count < CI_MAX_CLASSES) {
                memcpy(STATE.classes[STATE.class_count].name, name_start, nlen);
                STATE.classes[STATE.class_count].name[nlen] = '\0';
                STATE.classes[STATE.class_count].method_count = 0;
                STATE.classes[STATE.class_count].has_run = 0;
                STATE.classes[STATE.class_count].has_ghost = has_ghost;
                STATE.classes[STATE.class_count].has_vbs = has_vbs;
                strncpy(current_class, STATE.classes[STATE.class_count].name, CI_MAX_NAME - 1);
                current_class[CI_MAX_NAME - 1] = '\0';
                STATE.class_count++;
            }
        }
        
        /* Check for method definition */
        if (strncmp(trimmed, "def ", 4) == 0) {
            char *name_start = trimmed + 4;
            char *name_end = name_start;
            while (*name_end && *name_end != '(' && *name_end != ' ' && *name_end != '\n') {
                name_end++;
            }
            int nlen = (int)(name_end - name_start);
            if (nlen > 0 && nlen < CI_MAX_NAME && STATE.method_count < CI_MAX_METHODS) {
                memcpy(STATE.methods[STATE.method_count].name, name_start, nlen);
                STATE.methods[STATE.method_count].name[nlen] = '\0';
                strncpy(STATE.methods[STATE.method_count].class_name, current_class, CI_MAX_NAME - 1);
                STATE.methods[STATE.method_count].class_name[CI_MAX_NAME - 1] = '\0';
                
                /* Track Run() and method count for current class */
                if (current_class[0]) {
                    for (int i = 0; i < STATE.class_count; i++) {
                        if (strcmp(STATE.classes[i].name, current_class) == 0) {
                            STATE.classes[i].method_count++;
                            if (strcmp(STATE.methods[STATE.method_count].name, "Run") == 0) {
                                STATE.classes[i].has_run = 1;
                            }
                            break;
                        }
                    }
                }
                STATE.method_count++;
            }
        }
        
        p = eol + 1;
        line_num++;
    }
    
    /* Scan for VBStyle bracket tags [@TAG] */
    ScanBracketTags(content, len);
}

/* Index a single file into MySQL */
static int IndexFileToDb(const char *path) {
    if (!STATE.connected) return 0;
    
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    char buf[CI_MAX_FILE];
    int n = (int)fread(buf, 1, sizeof(buf) - 1, f);
    buf[n] = '\0';
    fclose(f);
    
    ParsePython(buf, n);
    
    int classes_written = 0;
    int methods_written = 0;
    
    for (int i = 0; i < STATE.class_count; i++) {
        char ename[CI_MAX_NAME * 2];
        char edesc[CI_MAX_DESC * 2];
        EscapeString(STATE.conn, ename, sizeof(ename), STATE.classes[i].name);
        snprintf(edesc, sizeof(edesc), "has_run=%d has_ghost=%d has_vbs=%d methods=%d",
            STATE.classes[i].has_run, STATE.classes[i].has_ghost,
            STATE.classes[i].has_vbs, STATE.classes[i].method_count);
        
        char query[CI_MAX_QUERY];
        snprintf(query, sizeof(query),
            "INSERT INTO vb_classes (class_name, description, source_db) VALUES ('%s', '%s', 'bcl_code_index') ON DUPLICATE KEY UPDATE description='%s'",
            ename, edesc, edesc);
        if (mysql_query(STATE.conn, query) == 0) {
            classes_written++;
            my_ulonglong class_id = mysql_insert_id(STATE.conn);
            if (class_id == 0) {
                /* Already existed — find it */
                snprintf(query, sizeof(query), "SELECT id FROM vb_classes WHERE class_name='%s'", ename);
                if (mysql_query(STATE.conn, query) == 0) {
                    MYSQL_RES *res = mysql_store_result(STATE.conn);
                    if (res) {
                        MYSQL_ROW row = mysql_fetch_row(res);
                        if (row) class_id = strtoull(row[0], NULL, 10);
                        mysql_free_result(res);
                    }
                }
            }
            
            /* Insert methods for this class */
            for (int j = 0; j < STATE.method_count; j++) {
                if (strcmp(STATE.methods[j].class_name, STATE.classes[i].name) != 0) continue;
                char emname[CI_MAX_NAME * 2];
                EscapeString(STATE.conn, emname, sizeof(emname), STATE.methods[j].name);
                snprintf(query, sizeof(query),
                    "INSERT INTO vb_methods (method_name, class_id, params) VALUES ('%s', %llu, '') ON DUPLICATE KEY UPDATE params=''",
                    emname, (unsigned long long)class_id);
                if (mysql_query(STATE.conn, query) == 0) {
                    methods_written++;
                }
            }
        }
    }
    
    STATE.classes_indexed += classes_written;
    STATE.methods_indexed += methods_written;
    STATE.files_indexed++;
    return classes_written;
}

/* Recursively walk directory */
static int WalkDir(const char *path, int *file_count) {
    DIR *d = opendir(path);
    if (!d) return 0;
    
    struct dirent *entry;
    while ((entry = readdir(d)) != NULL && *file_count < CI_MAX_FILES) {
        if (IsSkipDir(entry->d_name)) continue;
        
        char fullpath[CI_MAX_PATH];
        snprintf(fullpath, sizeof(fullpath), "%s/%s", path, entry->d_name);
        
        struct stat st;
        if (stat(fullpath, &st) != 0) continue;
        
        if (S_ISDIR(st.st_mode)) {
            WalkDir(fullpath, file_count);
        } else if (S_ISREG(st.st_mode)) {
            const char *ext = strrchr(entry->d_name, '.');
            if (ext && strcmp(ext, ".py") == 0) {
                IndexFileToDb(fullpath);
                (*file_count)++;
            }
        }
    }
    closedir(d);
    return 1;
}

/* ===== UNIT INTERFACE ===== */

int CodeIndex_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    strcpy(STATE.host, "localhost");
    strcpy(STATE.user, "root");
    STATE.port = 0;
    strcpy(STATE.socket, "/tmp/mysql.sock");
    return 1;
}

int CodeIndex_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) {
        return BclResult_Err(bcl_out, out_sz, 1, "not initialized");
    }
    
    /* ---- open (connect to MySQL) ---- */
    if (strcmp(cmd, "open") == 0) {
        EnsureConnected();
        if (!STATE.connected) {
            return BclResult_Err(bcl_out, out_sz, 2, STATE.last_error);
        }
        char body[256];
        snprintf(body, sizeof(body), "[@STATUS]{connected}[@HOST]{%s}[@DB]{vb_code_test}", STATE.host);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    /* ---- index_file ---- */
    if (strcmp(cmd, "index_file") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[CI_MAX_PATH];
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 3, "no PATH in packet");
        }
        if (!STATE.connected) {
            EnsureConnected();
            if (!STATE.connected) {
                return BclResult_Err(bcl_out, out_sz, 2, STATE.last_error);
            }
        }
        FILE *f = fopen(path, "r");
        if (!f) {
            return BclResult_Err(bcl_out, out_sz, 4, "cannot open file");
        }
        char buf[CI_MAX_FILE];
        int n = (int)fread(buf, 1, sizeof(buf) - 1, f);
        buf[n] = '\0';
        fclose(f);
        strncpy(STATE.last_file, path, CI_MAX_NAME - 1);
        ParsePython(buf, n);
        int cw = IndexFileToDb(path);
        char body[512];
        snprintf(body, sizeof(body),
            "[@FILE]{%s}[@CLASSES]{%d}[@METHODS]{%d}[@STATUS]{indexed}",
            path, STATE.class_count, STATE.method_count);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    /* ---- index_dir ---- */
    if (strcmp(cmd, "index_dir") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[CI_MAX_PATH];
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 5, "no PATH in packet");
        }
        if (!STATE.connected) {
            EnsureConnected();
            if (!STATE.connected) {
                return BclResult_Err(bcl_out, out_sz, 2, STATE.last_error);
            }
        }
        int file_count = 0;
        WalkDir(path, &file_count);
        char body[512];
        snprintf(body, sizeof(body),
            "[@DIR]{%s}[@FILES]{%d}[@CLASSES]{%d}[@METHODS]{%d}[@STATUS]{indexed}",
            path, file_count, STATE.classes_indexed, STATE.methods_indexed);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    /* ---- close_db ---- */
    if (strcmp(cmd, "close_db") == 0) {
        if (STATE.conn) {
            mysql_close(STATE.conn);
            STATE.conn = NULL;
        }
        STATE.connected = 0;
        char body[128];
        snprintf(body, sizeof(body), "[@STATUS]{disconnected}");
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    /* ---- read_state ---- */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@CONNECTED]{%d}[@FILES]{%d}[@CLASSES]{%d}[@METHODS]{%d}[@LAST_FILE]{%s}[@LAST_ERROR]{%s}",
            STATE.initialized, STATE.connected, STATE.files_indexed,
            STATE.classes_indexed, STATE.methods_indexed,
            STATE.last_file[0] ? STATE.last_file : "none",
            STATE.last_error[0] ? STATE.last_error : "none");
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    /* ---- set_config ---- */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char host[256], user[64], pass[128], socket[256];
        BclParser_Extract(&parse, "HOST", host, sizeof(host));
        BclParser_Extract(&parse, "USER", user, sizeof(user));
        BclParser_Extract(&parse, "PASS", pass, sizeof(pass));
        BclParser_Extract(&parse, "SOCKET", socket, sizeof(socket));
        BclParser_Free(&parse);
        if (host[0]) strncpy(STATE.host, host, sizeof(STATE.host) - 1);
        if (user[0]) strncpy(STATE.user, user, sizeof(STATE.user) - 1);
        if (pass[0]) strncpy(STATE.pass, pass, sizeof(STATE.pass) - 1);
        if (socket[0]) strncpy(STATE.socket, socket, sizeof(STATE.socket) - 1);
        char body[256];
        snprintf(body, sizeof(body), "[@STATUS]{config_set}[@HOST]{%s}[@USER]{%s}", STATE.host, STATE.user);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    /* ---- stats ---- */
    if (strcmp(cmd, "stats") == 0) {
        char body[4096];
        int off = 0;
        off += snprintf(body + off, sizeof(body) - off, "[@TAGS]{%d}", STATE.tag_count);
        for (int i = 0; i < STATE.tag_count && off < (int)sizeof(body) - 128; i++) {
            off += snprintf(body + off, sizeof(body) - off,
                "[@TAG]{[@NAME]{%s}[@COUNT]{%d}}", STATE.tags[i].tag, STATE.tags[i].count);
        }
        off += snprintf(body + off, sizeof(body) - off,
            "[@CLASSES]{%d}[@METHODS]{%d}[@STATUS]{stats}",
            STATE.class_count, STATE.method_count);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    /* ---- scan_headers ---- */
    if (strcmp(cmd, "scan_headers") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[CI_MAX_PATH];
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 6, "no PATH in packet");
        }
        FILE *f = fopen(path, "r");
        if (!f) {
            return BclResult_Err(bcl_out, out_sz, 4, "cannot open file");
        }
        char buf[CI_MAX_FILE];
        int n = (int)fread(buf, 1, sizeof(buf) - 1, f);
        buf[n] = '\0';
        fclose(f);
        
        /* Check first 500 chars for [@GHOST] and [@VBSTYLE] */
        int check_len = n < 500 ? n : 500;
        char head[512];
        memcpy(head, buf, check_len);
        head[check_len] = '\0';
        int has_ghost = (strstr(head, "[@GHOST]") != NULL) ? 1 : 0;
        int has_vbs = (strstr(head, "[@VBSTYLE]") != NULL) ? 1 : 0;
        
        /* Extract all bracket tags + classes/methods from the file (no MySQL) */
        ParsePython(buf, n);
        
        char body[4096];
        int off = 0;
        off += snprintf(body + off, sizeof(body) - off,
            "[@FILE]{%s}[@HAS_GHOST]{%d}[@HAS_VBSTYLE]{%d}[@TAGS]{%d}",
            path, has_ghost, has_vbs, STATE.tag_count);
        for (int i = 0; i < STATE.tag_count && off < (int)sizeof(body) - 128; i++) {
            off += snprintf(body + off, sizeof(body) - off,
                "[@TAG]{[@NAME]{%s}[@COUNT]{%d}}", STATE.tags[i].tag, STATE.tags[i].count);
        }
        off += snprintf(body + off, sizeof(body) - off,
            "[@CLASSES]{%d}[@METHODS]{%d}[@STATUS]{scanned}",
            STATE.class_count, STATE.method_count);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    return BclResult_Err(bcl_out, out_sz, 404, "unknown command");
}

int CodeIndex_Close(void) {
    if (STATE.conn) {
        mysql_close(STATE.conn);
        STATE.conn = NULL;
    }
    STATE.connected = 0;
    STATE.initialized = 0;
    STATE.files_indexed = 0;
    STATE.classes_indexed = 0;
    STATE.methods_indexed = 0;
    return 1;
}

const char * CodeIndex_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "CodeIndex: initialized=%d connected=%d files=%d classes=%d methods=%d",
        STATE.initialized, STATE.connected, STATE.files_indexed,
        STATE.classes_indexed, STATE.methods_indexed);
    return buf;
}
