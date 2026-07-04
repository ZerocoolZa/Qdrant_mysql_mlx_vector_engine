//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_codeingest.c" date="2026-07-04" author="Devin" session_id="bcl-codeingest-impl" context="BCL unit for real code file ingestion to MySQL bcl_ir tables. Reads source files, detects language, extracts classes/methods/imports via regex, stores to bcl_files/bcl_classes/bcl_methods. Commands: ingest, ingest_dir, stats, read_state, set_config."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="bcl_codeingest.c" domain="cascade_tools" authority="Codeingest"}
//[@SUMMARY]{summary="Code ingestion engine. Reads code files (.py/.c/.js), extracts metadata via regex (classes, methods, imports, line counts), stores to MySQL bcl_ir.bcl_files/bcl_classes/bcl_methods. Commands: ingest, ingest_dir, stats, read_state, set_config."}
//[@CLASS]{class="Codeingest" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="IngestFile" type="internal"}
//[@METHOD]{method="IngestDir" type="internal"}
//[@METHOD]{method="StoreFile" type="internal"}
//[@METHOD]{method="StoreClasses" type="internal"}
//[@METHOD]{method="StoreMethods" type="internal"}
//[@REVIEW]{[@date<2026-07-04>][@reviewer<devin>][@status<implementation>][@notes<Real code ingestion to MySQL bcl_ir. Regex-based extraction for py/c/js. mysql_real_escape_string for escaping. Errors go to STATE.last_error.>][@todos<>]}

/* bcl_codeingest.c — real code file ingestion to MySQL bcl_ir tables
 * Schema: bcl_codebases, bcl_files, bcl_classes, bcl_methods (existing in bcl_ir db) */

#include "bcl_toolstack.h"
#include <mysql.h>
#include <dirent.h>
#include <sys/stat.h>
#include <regex.h>

#define CI_MAX_PATH      1024
#define CI_MAX_SOURCE    1048576
#define CI_MAX_CLASSES   256
#define CI_MAX_METHODS   1024
#define CI_MAX_IMPORTS   256
#define CI_MAX_NAME      256
#define CI_MAX_LANGS     128

typedef struct { char name[CI_MAX_NAME]; int line_start, line_end, method_count; } CiClass;
typedef struct { char name[CI_MAX_NAME]; char class_name[CI_MAX_NAME]; int line_start, line_end, is_async; } CiMethod;

static struct {
    int  initialized;
    int  files_ingested;
    int  classes_found;
    int  methods_found;
    char last_path[CI_MAX_PATH];
    char last_error[256];
    char db_name[64];
    char codebase_name[128];
    long max_file_size;
    char languages[CI_MAX_LANGS];
    int  py_files, c_files, js_files;
} STATE;

/* ===== HELPERS ===== */

static void escape_str(MYSQL *conn, const char *in, char *out, size_t out_sz) {
    mysql_real_escape_string(conn, out, in, (unsigned long)strlen(in));
    (void)out_sz;
}

static void make_hash(const char *input, char *out) {
    unsigned long h1 = 2166136261UL, h2 = 14695981039346656037UL;
    for (const char *p = input; *p; p++) {
        h1 ^= (unsigned char)*p; h1 *= 16777619UL;
        h2 ^= (unsigned char)*p; h2 *= 1099511628211UL;
    }
    snprintf(out, 17, "%08lx%08lx", h1 & 0xFFFFFFFFUL, h2 & 0xFFFFFFFFUL);
    out[16] = '\0';
}

static const char * detect_language(const char *path) {
    const char *dot = strrchr(path, '.');
    if (!dot) return "unknown";
    if (strcmp(dot, ".py") == 0 || strcmp(dot, ".pyw") == 0) return "python";
    if (strcmp(dot, ".c") == 0 || strcmp(dot, ".h") == 0)    return "c";
    if (strcmp(dot, ".js") == 0 || strcmp(dot, ".mjs") == 0) return "javascript";
    return "unknown";
}

static int count_lines(const char *src) {
    int n = 0;
    for (const char *p = src; *p; p++) if (*p == '\n') n++;
    return n + 1;
}

/* Regex helper: find all matches, extract first capture group, track line numbers */
static int regex_find_all(const char *src, const char *pattern,
                          char names[][CI_MAX_NAME], int *line_starts, int max_count) {
    regex_t re;
    if (regcomp(&re, pattern, REG_EXTENDED) != 0) return 0;
    int count = 0, line = 1;
    const char *cursor = src;
    regmatch_t match[4];
    while (count < max_count && regexec(&re, cursor, 4, match, 0) == 0) {
        for (const char *p = src; p < cursor + match[0].rm_so; p++) if (*p == '\n') line++;
        int gi = (match[1].rm_so >= 0) ? 1 : 0;
        int len = match[gi].rm_eo - match[gi].rm_so;
        if (len <= 0 || len >= CI_MAX_NAME) len = CI_MAX_NAME - 1;
        memcpy(names[count], cursor + match[gi].rm_so, len);
        names[count][len] = '\0';
        if (line_starts) line_starts[count] = line;
        count++;
        cursor += match[0].rm_eo;
        if (match[0].rm_eo == 0) break;
    }
    regfree(&re);
    return count;
}

static int find_classes(const char *src, CiClass *classes, int max_count) {
    char names[CI_MAX_CLASSES][CI_MAX_NAME];
    int lines[CI_MAX_CLASSES];
    int n = regex_find_all(src, "class[ \t]+([A-Za-z_][A-Za-z0-9_]*)", names, lines, max_count);
    for (int i = 0; i < n; i++) {
        memset(&classes[i], 0, sizeof(CiClass));
        strncpy(classes[i].name, names[i], CI_MAX_NAME - 1);
        classes[i].line_start = lines[i];
    }
    return n;
}

static int find_methods(const char *src, const char *lang, CiMethod *methods, int max_count) {
    char names[CI_MAX_METHODS][CI_MAX_NAME];
    int lines[CI_MAX_METHODS];
    int n = 0;
    if (strcmp(lang, "python") == 0)
        n = regex_find_all(src, "def[ \t]+([A-Za-z_][A-Za-z0-9_]*)", names, lines, max_count);
    else if (strcmp(lang, "c") == 0)
        n = regex_find_all(src, "([A-Za-z_][A-Za-z0-9_]*)[ \t]*\\([^;]*$", names, lines, max_count);
    else if (strcmp(lang, "javascript") == 0)
        n = regex_find_all(src, "function[ \t]+([A-Za-z_][A-Za-z0-9_]*)", names, lines, max_count);
    for (int i = 0; i < n; i++) {
        memset(&methods[i], 0, sizeof(CiMethod));
        strncpy(methods[i].name, names[i], CI_MAX_NAME - 1);
        methods[i].line_start = lines[i];
    }
    return n;
}

static int find_imports(const char *src, const char *lang, char imports[][CI_MAX_NAME], int max_count) {
    if (strcmp(lang, "python") == 0)
        return regex_find_all(src, "(?:import|from)[ \t]+([A-Za-z_][A-Za-z0-9_.]*)", imports, NULL, max_count);
    if (strcmp(lang, "c") == 0)
        return regex_find_all(src, "#include[ \t]*[<\"]([^>\"]+)[>\"]", imports, NULL, max_count);
    if (strcmp(lang, "javascript") == 0)
        return regex_find_all(src, "(?:import|require)\\([^'\"]*['\"]([^'\"]+)['\"]", imports, NULL, max_count);
    return 0;
}

/* ===== MYSQL STORE ===== */

static int get_or_create_codebase(MYSQL *conn, const char *cb_name) {
    char sql[512];
    snprintf(sql, sizeof(sql), "SELECT id FROM bcl_codebases WHERE name = '%s'", cb_name);
    if (mysql_query(conn, sql)) return -1;
    MYSQL_RES *res = mysql_store_result(conn);
    if (res && mysql_num_rows(res) > 0) {
        MYSQL_ROW row = mysql_fetch_row(res);
        int id = atoi(row[0]);
        mysql_free_result(res);
        return id;
    }
    if (res) mysql_free_result(res);
    char ename[256];
    escape_str(conn, cb_name, ename, sizeof(ename));
    snprintf(sql, sizeof(sql), "INSERT INTO bcl_codebases (name) VALUES ('%s')", ename);
    if (mysql_query(conn, sql)) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "codebase create: %s", mysql_error(conn));
        return -1;
    }
    return (int)mysql_insert_id(conn);
}

static int store_file(MYSQL *conn, int cb_id, const char *path, const char *fname,
                      const char *hash, int lines, int nc, int nm) {
    char epath[CI_MAX_PATH * 2], ename[CI_MAX_NAME * 2];
    escape_str(conn, path, epath, sizeof(epath));
    escape_str(conn, fname, ename, sizeof(ename));
    char sql[2048];
    snprintf(sql, sizeof(sql),
        "INSERT INTO bcl_files (codebase_id, file_path, file_name, file_hash, "
        "line_count, class_count, method_count) VALUES (%d, '%s', '%s', '%s', %d, %d, %d) "
        "ON DUPLICATE KEY UPDATE file_hash='%s', line_count=%d, class_count=%d, method_count=%d",
        cb_id, epath, ename, hash, lines, nc, nm, hash, lines, nc, nm);
    if (mysql_query(conn, sql)) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "bcl_files: %s", mysql_error(conn));
        return 0;
    }
    return 1;
}

static int store_classes(MYSQL *conn, int cb_id, const char *path, CiClass *classes, int n) {
    for (int i = 0; i < n; i++) {
        char ename[CI_MAX_NAME * 2], epath[CI_MAX_PATH * 2];
        escape_str(conn, classes[i].name, ename, sizeof(ename));
        escape_str(conn, path, epath, sizeof(epath));
        char sql[2048];
        snprintf(sql, sizeof(sql),
            "INSERT IGNORE INTO bcl_classes (codebase_id, class_name, file_path, "
            "bases, method_count, line_start, line_end) VALUES (%d, '%s', '%s', '', %d, %d, %d)",
            cb_id, ename, epath, classes[i].method_count, classes[i].line_start, classes[i].line_end);
        if (mysql_query(conn, sql)) {
            snprintf(STATE.last_error, sizeof(STATE.last_error), "bcl_classes: %s", mysql_error(conn));
            return 0;
        }
        STATE.classes_found++;
    }
    return 1;
}

static int store_methods(MYSQL *conn, int cb_id, const char *path, CiMethod *methods, int n) {
    for (int i = 0; i < n; i++) {
        char method_id[CI_MAX_PATH + CI_MAX_NAME * 2];
        snprintf(method_id, sizeof(method_id), "%s::%s.%s", path,
                 methods[i].class_name[0] ? methods[i].class_name : "<module>", methods[i].name);
        char hash[17];
        make_hash(method_id, hash);
        char ename[CI_MAX_NAME * 2], ecname[CI_MAX_NAME * 2], epath[CI_MAX_PATH * 2], emid[CI_MAX_PATH * 3];
        escape_str(conn, methods[i].name, ename, sizeof(ename));
        escape_str(conn, methods[i].class_name, ecname, sizeof(ecname));
        escape_str(conn, path, epath, sizeof(epath));
        escape_str(conn, method_id, emid, sizeof(emid));
        char sql[4096];
        snprintf(sql, sizeof(sql),
            "INSERT IGNORE INTO bcl_methods (codebase_id, method_id, method_id_hash, "
            "method_name, class_name, file_path, method_type, is_async, line_start, line_end) "
            "VALUES (%d, '%s', '%s', '%s', '%s', '%s', 'LINK', %d, %d, %d)",
            cb_id, emid, hash, ename, ecname, epath,
            methods[i].is_async, methods[i].line_start, methods[i].line_end);
        if (mysql_query(conn, sql)) {
            snprintf(STATE.last_error, sizeof(STATE.last_error), "bcl_methods: %s", mysql_error(conn));
            return 0;
        }
        STATE.methods_found++;
    }
    return 1;
}

/* ===== CORE INGEST ===== */

static int ingest_file(const char *path, const char *codebase_name,
                       char *bcl_out, size_t out_sz) {
    FILE *fp = fopen(path, "r");
    if (!fp) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "cannot open: %s", path);
        return BclResult_Err(bcl_out, out_sz, 10, STATE.last_error);
    }
    fseek(fp, 0, SEEK_END);
    long fsize = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    if (fsize > STATE.max_file_size) {
        fclose(fp);
        snprintf(STATE.last_error, sizeof(STATE.last_error), "file too large: %ld (max %ld)", fsize, STATE.max_file_size);
        return BclResult_Err(bcl_out, out_sz, 11, STATE.last_error);
    }
    char *src = (char *)malloc(fsize + 1);
    if (!src) { fclose(fp); return BclResult_Err(bcl_out, out_sz, 12, "malloc failed"); }
    size_t rd = fread(src, 1, fsize, fp);
    src[rd] = '\0';
    fclose(fp);

    const char *lang = detect_language(path);
    if (strcmp(lang, "unknown") == 0) {
        free(src);
        snprintf(STATE.last_error, sizeof(STATE.last_error), "unsupported type: %s", path);
        return BclResult_Err(bcl_out, out_sz, 13, STATE.last_error);
    }

    int n_lines = count_lines(src);
    CiClass classes[CI_MAX_CLASSES];
    CiMethod methods[CI_MAX_METHODS];
    char imports[CI_MAX_IMPORTS][CI_MAX_NAME];
    int n_classes = find_classes(src, classes, CI_MAX_CLASSES);
    int n_methods = find_methods(src, lang, methods, CI_MAX_METHODS);
    int n_imports = find_imports(src, lang, imports, CI_MAX_IMPORTS);

    char hash_input[CI_MAX_PATH + 64];
    snprintf(hash_input, sizeof(hash_input), "%s:%ld:%d", path, fsize, n_lines);
    char file_hash[17];
    make_hash(hash_input, file_hash);
    const char *base = strrchr(path, '/');
    const char *file_name = base ? base + 1 : path;

    MYSQL *conn = mysql_init(NULL);
    if (!conn) { free(src); return BclResult_Err(bcl_out, out_sz, 14, "mysql_init failed"); }
    if (!mysql_real_connect(conn, "localhost", "root", "", STATE.db_name, 0, NULL, 0)) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "mysql connect: %s", mysql_error(conn));
        mysql_close(conn); free(src);
        return BclResult_Err(bcl_out, out_sz, 15, STATE.last_error);
    }

    int cb_id = get_or_create_codebase(conn, codebase_name);
    if (cb_id < 0) { mysql_close(conn); free(src); return BclResult_Err(bcl_out, out_sz, 16, STATE.last_error); }

    int ok = store_file(conn, cb_id, path, file_name, file_hash, n_lines, n_classes, n_methods);
    if (ok) ok = store_classes(conn, cb_id, path, classes, n_classes);
    if (ok) ok = store_methods(conn, cb_id, path, methods, n_methods);
    mysql_close(conn);
    free(src);
    if (!ok) return BclResult_Err(bcl_out, out_sz, 17, STATE.last_error);

    STATE.files_ingested++;
    strncpy(STATE.last_path, path, CI_MAX_PATH - 1);
    STATE.last_path[CI_MAX_PATH - 1] = '\0';
    if (strcmp(lang, "python") == 0) STATE.py_files++;
    else if (strcmp(lang, "c") == 0) STATE.c_files++;
    else if (strcmp(lang, "javascript") == 0) STATE.js_files++;

    char body[1024];
    snprintf(body, sizeof(body),
        "[@FILE]{%s}[@LANG]{%s}[@LINES]{%d}[@CLASSES]{%d}[@METHODS]{%d}[@IMPORTS]{%d}[@CODEBASE]{%s}",
        path, lang, n_lines, n_classes, n_methods, n_imports, codebase_name);
    return BclResult_Ok(bcl_out, out_sz, body);
}

static int ext_allowed(const char *path, const char *ext_list) {
    const char *dot = strrchr(path, '.');
    if (!dot) return 0;
    const char *ext = dot + 1;
    const char *p = ext_list;
    while (*p) {
        const char *comma = strchr(p, ',');
        size_t len = comma ? (size_t)(comma - p) : strlen(p);
        if (strlen(ext) == len && strncmp(ext, p, len) == 0) return 1;
        if (!comma) break;
        p = comma + 1;
    }
    return 0;
}

static int ingest_dir(const char *dir_path, const char *ext_list,
                      int max_files, char *bcl_out, size_t out_sz) {
    DIR *d = opendir(dir_path);
    if (!d) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "cannot open dir: %s", dir_path);
        return BclResult_Err(bcl_out, out_sz, 20, STATE.last_error);
    }
    int ingested = 0, skipped = 0;
    struct dirent *entry;
    while ((entry = readdir(d)) != NULL && ingested < max_files) {
        if (entry->d_name[0] == '.') { skipped++; continue; }
        char full_path[CI_MAX_PATH];
        snprintf(full_path, sizeof(full_path), "%s/%s", dir_path, entry->d_name);
        struct stat st;
        if (stat(full_path, &st) != 0 || !S_ISREG(st.st_mode)) { skipped++; continue; }
        if (!ext_allowed(full_path, ext_list)) { skipped++; continue; }
        char tmp_out[TOOL_MAX_RESULT];
        if (ingest_file(full_path, STATE.codebase_name, tmp_out, sizeof(tmp_out)) == 1) ingested++;
        else skipped++;
    }
    closedir(d);
    char body[4096];
    snprintf(body, sizeof(body), "[@DIR]{%s}[@EXT]{%s}[@MAX]{%d}[@INGESTED]{%d}[@SKIPPED]{%d}",
        dir_path, ext_list, max_files, ingested, skipped);
    return BclResult_Ok(bcl_out, out_sz, body);
}

/* ===== UNIT INTERFACE ===== */

int Codeingest_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    strncpy(STATE.db_name,       "bcl_ir",  sizeof(STATE.db_name) - 1);
    strncpy(STATE.codebase_name, "default", sizeof(STATE.codebase_name) - 1);
    strncpy(STATE.languages,     "py,c,js", sizeof(STATE.languages) - 1);
    STATE.max_file_size = CI_MAX_SOURCE;
    STATE.initialized = 1;
    return 1;
}

int Codeingest_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) Codeingest_Init();

    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@FILES]{%d}[@CLASSES]{%d}[@METHODS]{%d}"
            "[@LAST_PATH]{%s}[@LAST_ERROR]{%s}[@DB]{%s}[@CODEBASE]{%s}",
            STATE.initialized, STATE.files_ingested, STATE.classes_found,
            STATE.methods_found, STATE.last_path, STATE.last_error,
            STATE.db_name, STATE.codebase_name);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char db_name[64] = {0}, codebase[128] = {0}, max_file[32] = {0}, langs[CI_MAX_LANGS] = {0};
        BclParser_Extract(&parse, "DB",       db_name,  sizeof(db_name));
        BclParser_Extract(&parse, "CODEBASE", codebase, sizeof(codebase));
        BclParser_Extract(&parse, "MAX_FILE", max_file, sizeof(max_file));
        BclParser_Extract(&parse, "LANGS",    langs,    sizeof(langs));
        BclParser_Free(&parse);
        if (db_name[0])  strncpy(STATE.db_name,       db_name,  sizeof(STATE.db_name) - 1);
        if (codebase[0]) strncpy(STATE.codebase_name, codebase, sizeof(STATE.codebase_name) - 1);
        if (max_file[0]) STATE.max_file_size = atol(max_file);
        if (langs[0])    strncpy(STATE.languages,     langs,    sizeof(STATE.languages) - 1);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }

    if (strcmp(cmd, "ingest") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[CI_MAX_PATH] = {0}, codebase[128] = {0};
        BclParser_Extract(&parse, "PATH",     path,     sizeof(path));
        BclParser_Extract(&parse, "CODEBASE", codebase, sizeof(codebase));
        BclParser_Free(&parse);
        if (!path[0]) return BclResult_Err(bcl_out, out_sz, 30, "no PATH in packet");
        return ingest_file(path, codebase[0] ? codebase : STATE.codebase_name, bcl_out, out_sz);
    }

    if (strcmp(cmd, "ingest_dir") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[CI_MAX_PATH] = {0}, ext_list[64] = {0}, max_str[16] = {0};
        BclParser_Extract(&parse, "PATH", path,     sizeof(path));
        BclParser_Extract(&parse, "EXT",  ext_list, sizeof(ext_list));
        BclParser_Extract(&parse, "MAX",  max_str,  sizeof(max_str));
        BclParser_Free(&parse);
        if (!path[0]) return BclResult_Err(bcl_out, out_sz, 40, "no PATH in packet");
        return ingest_dir(path, ext_list[0] ? ext_list : STATE.languages,
                          max_str[0] ? atoi(max_str) : 100, bcl_out, out_sz);
    }

    if (strcmp(cmd, "stats") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@TOTAL_FILES]{%d}[@TOTAL_CLASSES]{%d}[@TOTAL_METHODS]{%d}"
            "[@PY_FILES]{%d}[@C_FILES]{%d}[@JS_FILES]{%d}[@DB]{%s}[@CODEBASE]{%s}",
            STATE.files_ingested, STATE.classes_found, STATE.methods_found,
            STATE.py_files, STATE.c_files, STATE.js_files,
            STATE.db_name, STATE.codebase_name);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    return BclResult_Err(bcl_out, out_sz, 50, "unknown command");
}

int Codeingest_Close(void) {
    STATE.initialized = 0;
    return 1;
}

const char * Codeingest_State(void) {
    static char buf[512];
    snprintf(buf, sizeof(buf),
        "Codeingest: initialized=%d files=%d classes=%d methods=%d db=%s codebase=%s",
        STATE.initialized, STATE.files_ingested, STATE.classes_found,
        STATE.methods_found, STATE.db_name, STATE.codebase_name);
    return buf;
}
