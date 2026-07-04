/*
 * bh_nose.c - Scent extractor for LMDB Bloodhound
 *[@GHOST]
 *[@VBSTYLE]
 *[@FILEID] bh_nose.c
 *[@SUMMARY] Tokenize by file type, extract scents, compute fingerprints, build relationships
 *[@CLASS] BloodhoundNose
 *[@METHOD] Extract, Normalize, ComputeFingerprint, DetectLanguage
 */

#include "bloodhound.h"

/* ---- Normalize ---- */

void bh_normalize(const char *in, char *out, size_t out_size) {
    size_t j = 0;
    for (size_t i = 0; in[i] && j < out_size - 1; i++) {
        unsigned char c = (unsigned char)in[i];
        if (isspace(c)) {
            if (j > 0 && out[j-1] != '_') out[j++] = '_';
        } else {
            out[j++] = (char)tolower(c);
        }
    }
    while (j > 0 && out[j-1] == '_') j--;
    out[j] = '\0';
    if (j == 0) snprintf(out, out_size, "empty");
}

/* ---- Fingerprint ---- */

void bh_compute_fingerprint(const char *normalized, char *out, size_t out_size) {
    bh_sha256_string(normalized, strlen(normalized), out, out_size);
}

/* ---- File hash ---- */

void bh_compute_file_hash(const char *file_path, char *out, size_t out_size) {
    FILE *f = fopen(file_path, "rb");
    if (!f) { snprintf(out, out_size, "0000000000000000"); return; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *buf = malloc(sz);
    if (!buf) { fclose(f); snprintf(out, out_size, "0000000000000000"); return; }
    fread(buf, 1, sz, f);
    fclose(f);
    bh_sha256_string(buf, sz, out, out_size);
    free(buf);
}

/* ---- Language detection ---- */

const char *bh_detect_language(const char *file_path) {
    const char *ext = strrchr(file_path, '.');
    if (!ext) return "text";
    ext++;
    if (strcmp(ext, "py") == 0) return "python";
    if (strcmp(ext, "c") == 0 || strcmp(ext, "h") == 0) return "c";
    if (strcmp(ext, "cpp") == 0 || strcmp(ext, "hpp") == 0 || strcmp(ext, "cc") == 0) return "cpp";
    if (strcmp(ext, "swift") == 0) return "swift";
    if (strcmp(ext, "md") == 0 || strcmp(ext, "markdown") == 0) return "markdown";
    if (strcmp(ext, "json") == 0) return "json";
    if (strcmp(ext, "sql") == 0) return "sql";
    if (strcmp(ext, "sh") == 0 || strcmp(ext, "bash") == 0) return "shell";
    if (strcmp(ext, "go") == 0) return "go";
    if (strcmp(ext, "rs") == 0) return "rust";
    if (strcmp(ext, "js") == 0 || strcmp(ext, "ts") == 0) return "javascript";
    if (strcmp(ext, "txt") == 0) return "text";
    if (strcmp(ext, "yaml") == 0 || strcmp(ext, "yml") == 0) return "yaml";
    if (strcmp(ext, "toml") == 0) return "toml";
    if (strcmp(ext, "xml") == 0) return "xml";
    if (strcmp(ext, "html") == 0) return "html";
    return "text";
}

/* ---- Helpers ---- */

static int is_ident_start(unsigned char c) { return isalpha(c) || c == '_'; }
static int is_ident_char(unsigned char c) { return isalnum(c) || c == '_'; }

static void skip_whitespace(const char *line, int *pos) {
    while (line[*pos] && isspace((unsigned char)line[*pos])) (*pos)++;
}

static int extract_identifier(const char *line, int start, char *out, size_t out_size) {
    int i = start;
    size_t j = 0;
    while (line[i] && is_ident_char((unsigned char)line[i]) && j < out_size - 1) {
        out[j++] = line[i++];
    }
    out[j] = '\0';
    return i;
}

/* ---- Read file into lines ---- */

static char **read_file_lines(const char *path, int *count) {
    *count = 0;
    FILE *f = fopen(path, "r");
    if (!f) return NULL;
    char **lines = calloc(5000, sizeof(char*));
    if (!lines) { fclose(f); return NULL; }
    char buf[BH_MAX_LINE];
    int n = 0;
    while (fgets(buf, sizeof(buf), f) && n < 5000) {
        size_t len = strlen(buf);
        if (len > 0 && buf[len-1] == '\n') buf[--len] = '\0';
        if (len > 0 && buf[len-1] == '\r') buf[--len] = '\0';
        lines[n] = strdup(buf);
        n++;
    }
    fclose(f);
    *count = n;
    return lines;
}

static void free_lines(char **lines, int count) {
    for (int i = 0; i < count; i++) free(lines[i]);
    free(lines);
}

/* ---- Context extraction ---- */

static void extract_context(char **lines, int line_count, int target_line,
                            char *before, char *match, char *after, size_t buf_size) {
    before[0] = match[0] = after[0] = '\0';
    int idx = target_line - 1;
    if (idx < 0 || idx >= line_count) return;
    snprintf(match, buf_size, "%s", lines[idx]);
    /* before: up to BH_CONTEXT_LINES lines above */
    before[0] = '\0';
    for (int i = (idx - BH_CONTEXT_LINES > 0 ? idx - BH_CONTEXT_LINES : 0); i < idx; i++) {
        strncat(before, lines[i], buf_size - strlen(before) - 2);
        strncat(before, "\n", buf_size - strlen(before) - 1);
    }
    /* after: up to BH_CONTEXT_LINES lines below */
    after[0] = '\0';
    for (int i = idx + 1; i < line_count && i <= idx + BH_CONTEXT_LINES; i++) {
        strncat(after, lines[i], buf_size - strlen(after) - 2);
        strncat(after, "\n", buf_size - strlen(after) - 1);
    }
}

/* ---- Create scent ---- */

static void create_scent(bh_db *db, const char *type, const char *language,
                         const char *workspace, const char *file_path, const char *rel_path,
                         int line, int col, const char *content_hash,
                         char **lines, int line_count, const char *match_text) {
    char normalized[BH_MAX_TOKEN * 2];
    char fingerprint[33];
    bh_normalize(match_text, normalized, sizeof(normalized));
    bh_compute_fingerprint(normalized, fingerprint, sizeof(fingerprint));

    /* Check if scent already exists (by fingerprint) */
    uint64_t existing_id = 0;
    if (bh_db_find_by_fp(db, fingerprint, &existing_id) == 0) {
        /* Scent exists — increment seen_count, boost confidence */
        scent_packet pkt;
        char ctx_b[BH_MAX_LINE], ctx_m[BH_MAX_LINE], ctx_a[BH_MAX_LINE];
        if (bh_db_get_scent(db, existing_id, &pkt, ctx_b, sizeof(ctx_b),
                            ctx_m, sizeof(ctx_m), ctx_a, sizeof(ctx_a)) == 0) {
            pkt.seen_count++;
            pkt.confidence += 0.02;
            if (pkt.confidence > 0.99) pkt.confidence = 0.99;
            pkt.updated_at = time(NULL);
            bh_db_put_scent(db, &pkt, ctx_b, ctx_m, ctx_a);
        }
        return;
    }

    /* New scent */
    char ctx_before[BH_MAX_LINE], ctx_match[BH_MAX_LINE], ctx_after[BH_MAX_LINE];
    extract_context(lines, line_count, line, ctx_before, ctx_match, ctx_after, sizeof(ctx_match));

    scent_packet pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.scent_id = bh_db_next_id(db, "next_scent_id");
    strncpy(pkt.fingerprint, fingerprint, 32);
    strncpy(pkt.type, type, 31);
    strncpy(pkt.language, language, 15);
    strncpy(pkt.workspace, workspace, 255);
    strncpy(pkt.source_file, file_path, BH_MAX_PATH - 1);
    strncpy(pkt.relative_path, rel_path, 511);
    pkt.line = line;
    pkt.column = col;
    pkt.byte_offset = 0;
    strncpy(pkt.content_hash, content_hash, 32);
    pkt.confidence = 0.50;
    pkt.created_at = time(NULL);
    pkt.updated_at = pkt.created_at;
    pkt.seen_count = 1;

    bh_db_put_scent(db, &pkt, ctx_before, ctx_match, ctx_after);
}

/* ---- Python extraction ---- */

static void extract_python(bh_db *db, const char *file_path, const char *rel_path,
                           const char *workspace, const char *content_hash,
                           char **lines, int line_count) {
    for (int i = 0; i < line_count; i++) {
        const char *line = lines[i];
        int lineno = i + 1;
        int pos = 0;
        skip_whitespace(line, &pos);
        if (!line[pos]) continue;

        /* def */
        if (strncmp(line + pos, "def ", 4) == 0) {
            pos += 4;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_FUNCTION, "python", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        /* class */
        else if (strncmp(line + pos, "class ", 6) == 0) {
            pos += 6;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_CLASS, "python", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        /* import / from ... import */
        else if (strncmp(line + pos, "import ", 7) == 0) {
            pos += 7;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_IMPORT, "python", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        else if (strncmp(line + pos, "from ", 5) == 0) {
            pos += 5;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_IMPORT, "python", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        /* bracket patterns [@TAG] */
        else {
            const char *bracket = strstr(line, "[@");
            if (bracket) {
                char tag[64];
                int j = 0;
                bracket += 2;
                while (*bracket && *bracket != ']' && *bracket != ' ' && *bracket != '{' && j < 63) {
                    tag[j++] = *bracket++;
                }
                tag[j] = '\0';
                if (j > 0) create_scent(db, BH_TYPE_BRACKET, "python", workspace, file_path, rel_path, lineno, bracket - line, content_hash, lines, line_count, tag);
            }
        }
    }
}

/* ---- C extraction ---- */

static void extract_c(bh_db *db, const char *file_path, const char *rel_path,
                      const char *workspace, const char *content_hash,
                      char **lines, int line_count) {
    for (int i = 0; i < line_count; i++) {
        const char *line = lines[i];
        int lineno = i + 1;
        int pos = 0;
        skip_whitespace(line, &pos);
        if (!line[pos]) continue;

        if (strncmp(line + pos, "#include", 8) == 0) {
            pos += 8;
            skip_whitespace(line, &pos);
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_INCLUDE, "c", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        else if (strncmp(line + pos, "#define", 7) == 0) {
            pos += 7;
            skip_whitespace(line, &pos);
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_DEFINE, "c", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        else if (strncmp(line + pos, "typedef", 7) == 0) {
            pos += 7;
            skip_whitespace(line, &pos);
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_STRUCT, "c", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        else if (strncmp(line + pos, "struct ", 7) == 0) {
            pos += 7;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_STRUCT, "c", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        /* bracket patterns */
        const char *bracket = strstr(line, "[@");
        if (bracket) {
            char tag[64];
            int j = 0;
            bracket += 2;
            while (*bracket && *bracket != ']' && *bracket != ' ' && *bracket != '{' && j < 63) {
                tag[j++] = *bracket++;
            }
            tag[j] = '\0';
            if (j > 0) create_scent(db, BH_TYPE_BRACKET, "c", workspace, file_path, rel_path, lineno, bracket - line, content_hash, lines, line_count, tag);
        }
    }
}

/* ---- Swift extraction ---- */

static void extract_swift(bh_db *db, const char *file_path, const char *rel_path,
                          const char *workspace, const char *content_hash,
                          char **lines, int line_count) {
    for (int i = 0; i < line_count; i++) {
        const char *line = lines[i];
        int lineno = i + 1;
        int pos = 0;
        skip_whitespace(line, &pos);
        if (!line[pos]) continue;

        if (strncmp(line + pos, "func ", 5) == 0) {
            pos += 5;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_FUNCTION, "swift", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        else if (strncmp(line + pos, "struct ", 7) == 0 || strncmp(line + pos, "class ", 6) == 0 ||
                 strncmp(line + pos, "enum ", 5) == 0 || strncmp(line + pos, "protocol ", 9) == 0) {
            while (line[pos] != ' ') pos++;
            pos++;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_CLASS, "swift", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        else if (strncmp(line + pos, "import ", 7) == 0) {
            pos += 7;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_IMPORT, "swift", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
    }
}

/* ---- Markdown extraction ---- */

static void extract_markdown(bh_db *db, const char *file_path, const char *rel_path,
                             const char *workspace, const char *content_hash,
                             char **lines, int line_count) {
    for (int i = 0; i < line_count; i++) {
        const char *line = lines[i];
        int lineno = i + 1;
        int pos = 0;
        skip_whitespace(line, &pos);
        if (!line[pos]) continue;

        /* Headings */
        if (line[pos] == '#') {
            int level = 0;
            while (line[pos] == '#') { pos++; level++; }
            skip_whitespace(line, &pos);
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_HEADING, "markdown", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        /* Bracket patterns */
        const char *bracket = strstr(line, "[@");
        if (bracket) {
            char tag[64];
            int j = 0;
            bracket += 2;
            while (*bracket && *bracket != ']' && *bracket != ' ' && *bracket != '{' && j < 63) {
                tag[j++] = *bracket++;
            }
            tag[j] = '\0';
            if (j > 0) create_scent(db, BH_TYPE_BRACKET, "markdown", workspace, file_path, rel_path, lineno, bracket - line, content_hash, lines, line_count, tag);
        }
        /* Code block markers */
        if (strncmp(line + pos, "```", 3) == 0) {
            create_scent(db, BH_TYPE_SYMBOL, "markdown", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, "codeblock");
        }
    }
}

/* ---- JSON extraction ---- */

static void extract_json(bh_db *db, const char *file_path, const char *rel_path,
                         const char *workspace, const char *content_hash,
                         char **lines, int line_count) {
    for (int i = 0; i < line_count; i++) {
        const char *line = lines[i];
        int lineno = i + 1;
        const char *quote = strchr(line, '"');
        while (quote) {
            const char *end = strchr(quote + 1, '"');
            if (!end) break;
            char key[BH_MAX_TOKEN];
            size_t klen = end - quote - 1;
            if (klen < sizeof(key) && klen > 0) {
                memcpy(key, quote + 1, klen);
                key[klen] = '\0';
                create_scent(db, BH_TYPE_KEY, "json", workspace, file_path, rel_path, lineno, quote - line, content_hash, lines, line_count, key);
            }
            quote = strchr(end + 1, '"');
        }
    }
}

/* ---- SQL extraction ---- */

static void extract_sql(bh_db *db, const char *file_path, const char *rel_path,
                        const char *workspace, const char *content_hash,
                        char **lines, int line_count) {
    for (int i = 0; i < line_count; i++) {
        const char *line = lines[i];
        int lineno = i + 1;
        int pos = 0;
        skip_whitespace(line, &pos);
        if (!line[pos]) continue;

        char upper[BH_MAX_LINE];
        int j = 0;
        for (; line[pos + j] && j < (int)sizeof(upper) - 1; j++) {
            upper[j] = toupper((unsigned char)line[pos + j]);
        }
        upper[j] = '\0';

        if (strncmp(upper, "CREATE TABLE", 12) == 0) {
            int k = 12;
            while (upper[k] && upper[k] != '(' && !isalnum(upper[k])) k++;
            while (upper[k] && !isalnum(upper[k]) && upper[k] != '_') k++;
            char name[BH_MAX_TOKEN];
            int end = 0;
            while (upper[k + end] && (isalnum(upper[k + end]) || upper[k + end] == '_') && end < 255) {
                name[end] = line[pos + k + end];
                end++;
            }
            name[end] = '\0';
            if (end > 0) create_scent(db, BH_TYPE_TABLE, "sql", workspace, file_path, rel_path, lineno, pos + k, content_hash, lines, line_count, name);
        }
    }
}

/* ---- Go extraction ---- */

static void extract_go(bh_db *db, const char *file_path, const char *rel_path,
                       const char *workspace, const char *content_hash,
                       char **lines, int line_count) {
    for (int i = 0; i < line_count; i++) {
        const char *line = lines[i];
        int lineno = i + 1;
        int pos = 0;
        skip_whitespace(line, &pos);
        if (!line[pos]) continue;

        if (strncmp(line + pos, "func ", 5) == 0) {
            pos += 5;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_FUNCTION, "go", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        else if (strncmp(line + pos, "type ", 5) == 0) {
            pos += 5;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_STRUCT, "go", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        else if (strncmp(line + pos, "package ", 8) == 0) {
            pos += 8;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_PACKAGE, "go", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        else if (strncmp(line + pos, "import ", 7) == 0) {
            pos += 7;
            if (line[pos] == '"') {
                char name[BH_MAX_TOKEN];
                int j = 0; pos++;
                while (line[pos] && line[pos] != '"' && j < 255) name[j++] = line[pos++];
                name[j] = '\0';
                if (j > 0) create_scent(db, BH_TYPE_IMPORT, "go", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
            }
        }
        /* bracket patterns */
        const char *bracket = strstr(line, "[@");
        if (bracket) {
            char tag[64]; int j = 0; bracket += 2;
            while (*bracket && *bracket != ']' && *bracket != ' ' && j < 63) tag[j++] = *bracket++;
            tag[j] = '\0';
            if (j > 0) create_scent(db, BH_TYPE_BRACKET, "go", workspace, file_path, rel_path, lineno, bracket - line, content_hash, lines, line_count, tag);
        }
    }
}

/* ---- Rust extraction ---- */

static void extract_rust(bh_db *db, const char *file_path, const char *rel_path,
                         const char *workspace, const char *content_hash,
                         char **lines, int line_count) {
    for (int i = 0; i < line_count; i++) {
        const char *line = lines[i];
        int lineno = i + 1;
        int pos = 0;
        skip_whitespace(line, &pos);
        if (!line[pos]) continue;

        if (strncmp(line + pos, "fn ", 3) == 0) {
            pos += 3;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_FUNCTION, "rust", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        else if (strncmp(line + pos, "struct ", 7) == 0) {
            pos += 7;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_STRUCT, "rust", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        else if (strncmp(line + pos, "enum ", 5) == 0) {
            pos += 5;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_ENUM, "rust", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        else if (strncmp(line + pos, "trait ", 6) == 0) {
            pos += 6;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_INTERFACE, "rust", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        else if (strncmp(line + pos, "use ", 4) == 0) {
            pos += 4;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_IMPORT, "rust", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        else if (strncmp(line + pos, "mod ", 4) == 0) {
            pos += 4;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_PACKAGE, "rust", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        const char *bracket = strstr(line, "[@");
        if (bracket) {
            char tag[64]; int j = 0; bracket += 2;
            while (*bracket && *bracket != ']' && *bracket != ' ' && j < 63) tag[j++] = *bracket++;
            tag[j] = '\0';
            if (j > 0) create_scent(db, BH_TYPE_BRACKET, "rust", workspace, file_path, rel_path, lineno, bracket - line, content_hash, lines, line_count, tag);
        }
    }
}

/* ---- JavaScript/TypeScript extraction ---- */

static void extract_javascript(bh_db *db, const char *file_path, const char *rel_path,
                               const char *workspace, const char *content_hash,
                               char **lines, int line_count) {
    for (int i = 0; i < line_count; i++) {
        const char *line = lines[i];
        int lineno = i + 1;
        int pos = 0;
        skip_whitespace(line, &pos);
        if (!line[pos]) continue;

        if (strncmp(line + pos, "function ", 9) == 0) {
            pos += 9;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_FUNCTION, "javascript", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        else if (strncmp(line + pos, "class ", 6) == 0) {
            pos += 6;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_CLASS, "javascript", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        else if (strncmp(line + pos, "import ", 7) == 0) {
            pos += 7;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_IMPORT, "javascript", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        else if (strncmp(line + pos, "interface ", 10) == 0) {
            pos += 10;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_INTERFACE, "javascript", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        else if (strncmp(line + pos, "export ", 7) == 0) {
            pos += 7;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_SYMBOL, "javascript", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        const char *bracket = strstr(line, "[@");
        if (bracket) {
            char tag[64]; int j = 0; bracket += 2;
            while (*bracket && *bracket != ']' && *bracket != ' ' && j < 63) tag[j++] = *bracket++;
            tag[j] = '\0';
            if (j > 0) create_scent(db, BH_TYPE_BRACKET, "javascript", workspace, file_path, rel_path, lineno, bracket - line, content_hash, lines, line_count, tag);
        }
    }
}

/* ---- Shell extraction ---- */

static void extract_shell(bh_db *db, const char *file_path, const char *rel_path,
                          const char *workspace, const char *content_hash,
                          char **lines, int line_count) {
    for (int i = 0; i < line_count; i++) {
        const char *line = lines[i];
        int lineno = i + 1;
        int pos = 0;
        skip_whitespace(line, &pos);
        if (!line[pos]) continue;

        /* function definition: name() { */
        if (line[pos] != '#' && strstr(line + pos, "()")) {
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos && line[end] == '(' && line[end+1] == ')') {
                create_scent(db, BH_TYPE_FUNCTION, "shell", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
            }
        }
        /* source/include */
        if (strncmp(line + pos, "source ", 7) == 0) {
            pos += 7;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos) create_scent(db, BH_TYPE_IMPORT, "shell", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
        }
        const char *bracket = strstr(line, "[@");
        if (bracket) {
            char tag[64]; int j = 0; bracket += 2;
            while (*bracket && *bracket != ']' && *bracket != ' ' && j < 63) tag[j++] = *bracket++;
            tag[j] = '\0';
            if (j > 0) create_scent(db, BH_TYPE_BRACKET, "shell", workspace, file_path, rel_path, lineno, bracket - line, content_hash, lines, line_count, tag);
        }
    }
}

/* ---- YAML extraction ---- */

static void extract_yaml(bh_db *db, const char *file_path, const char *rel_path,
                         const char *workspace, const char *content_hash,
                         char **lines, int line_count) {
    for (int i = 0; i < line_count; i++) {
        const char *line = lines[i];
        int lineno = i + 1;
        int pos = 0;
        skip_whitespace(line, &pos);
        if (!line[pos] || line[pos] == '#') continue;

        /* top-level keys only (no leading spaces) */
        if (pos == 0) {
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos && line[end] == ':') {
                create_scent(db, BH_TYPE_KEY, "yaml", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
            }
        }
        const char *bracket = strstr(line, "[@");
        if (bracket) {
            char tag[64]; int j = 0; bracket += 2;
            while (*bracket && *bracket != ']' && *bracket != ' ' && j < 63) tag[j++] = *bracket++;
            tag[j] = '\0';
            if (j > 0) create_scent(db, BH_TYPE_BRACKET, "yaml", workspace, file_path, rel_path, lineno, bracket - line, content_hash, lines, line_count, tag);
        }
    }
}

/* ---- TOML extraction ---- */

static void extract_toml(bh_db *db, const char *file_path, const char *rel_path,
                         const char *workspace, const char *content_hash,
                         char **lines, int line_count) {
    for (int i = 0; i < line_count; i++) {
        const char *line = lines[i];
        int lineno = i + 1;
        int pos = 0;
        skip_whitespace(line, &pos);
        if (!line[pos] || line[pos] == '#') continue;

        /* [section] headers */
        if (line[pos] == '[') {
            pos++;
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos && line[end] == ']') {
                create_scent(db, BH_TYPE_HEADING, "toml", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
            }
        }
        /* key = value */
        else {
            char name[BH_MAX_TOKEN];
            int end = extract_identifier(line, pos, name, sizeof(name));
            if (end > pos && line[end] == ' ' && line[end+1] == '=') {
                create_scent(db, BH_TYPE_KEY, "toml", workspace, file_path, rel_path, lineno, pos, content_hash, lines, line_count, name);
            }
        }
        const char *bracket = strstr(line, "[@");
        if (bracket) {
            char tag[64]; int j = 0; bracket += 2;
            while (*bracket && *bracket != ']' && *bracket != ' ' && j < 63) tag[j++] = *bracket++;
            tag[j] = '\0';
            if (j > 0) create_scent(db, BH_TYPE_BRACKET, "toml", workspace, file_path, rel_path, lineno, bracket - line, content_hash, lines, line_count, tag);
        }
    }
}

/* ---- Relationship building ---- */

typedef struct {
    uint64_t scent_ids[BH_MAX_REL];
    char types[BH_MAX_REL][32];
    char matches[BH_MAX_REL][BH_MAX_LINE];
    int count;
} rel_collect_ctx;

static int collect_scent_cb(scent_packet *pkt, const char *ctx_before, const char *ctx_match, const char *ctx_after, void *user_data) {
    rel_collect_ctx *ctx = (rel_collect_ctx *)user_data;
    if (ctx->count >= BH_MAX_REL) return 1;
    ctx->scent_ids[ctx->count] = pkt->scent_id;
    strncpy(ctx->types[ctx->count], pkt->type, 31);
    ctx->types[ctx->count][31] = '\0';
    strncpy(ctx->matches[ctx->count], ctx_match, BH_MAX_LINE - 1);
    ctx->matches[ctx->count][BH_MAX_LINE - 1] = '\0';
    ctx->count++;
    return 0;
}

void bh_nose_build_relationships(bh_db *db, const char *file_path, const char *workspace) {
    rel_collect_ctx ctx;
    memset(&ctx, 0, sizeof(ctx));
    bh_db_iter_file_scents(db, file_path, collect_scent_cb, &ctx);

    if (ctx.count < 2) return;

    /* same_file: consecutive scents */
    for (int i = 0; i < ctx.count - 1 && i < BH_MAX_REL; i++) {
        relationship rel;
        memset(&rel, 0, sizeof(rel));
        rel.from_scent = ctx.scent_ids[i];
        rel.to_scent = ctx.scent_ids[i + 1];
        strncpy(rel.rel_type, "same_file", 31);
        rel.confidence = 0.5;
        snprintf(rel.evidence, 255, "adjacent in %s", file_path);
        rel.created_at = time(NULL);
        bh_db_put_relationship(db, &rel);
    }

    /* imports → functions/classes in same file */
    for (int i = 0; i < ctx.count; i++) {
        if (strcmp(ctx.types[i], "import") != 0) continue;
        for (int j = 0; j < ctx.count; j++) {
            if (i == j) continue;
            if (strcmp(ctx.types[j], "function") == 0 || strcmp(ctx.types[j], "class") == 0) {
                relationship rel;
                memset(&rel, 0, sizeof(rel));
                rel.from_scent = ctx.scent_ids[i];
                rel.to_scent = ctx.scent_ids[j];
                strncpy(rel.rel_type, "imports", 31);
                rel.confidence = 0.6;
                strncpy(rel.evidence, "import in same file as definition", 255);
                rel.created_at = time(NULL);
                bh_db_put_relationship(db, &rel);
            }
        }
    }

    /* calls: function name appears in another scent's context */
    for (int i = 0; i < ctx.count; i++) {
        if (strcmp(ctx.types[i], "function") != 0) continue;
        char fname[BH_MAX_TOKEN];
        strncpy(fname, ctx.matches[i], BH_MAX_TOKEN - 1);
        fname[BH_MAX_TOKEN - 1] = '\0';
        /* strip "def " or "func " prefix */
        char *fname_p = fname;
        if (strncmp(fname_p, "def ", 4) == 0) fname_p += 4;
        else if (strncmp(fname_p, "func ", 5) == 0) fname_p += 5;
        else if (strncmp(fname_p, "function ", 9) == 0) fname_p += 9;
        /* extract just the identifier */
        char ident[BH_MAX_TOKEN];
        int end = extract_identifier(fname_p, 0, ident, sizeof(ident));
        if (end == 0) continue;

        for (int j = 0; j < ctx.count; j++) {
            if (i == j) continue;
            if (strstr(ctx.matches[j], ident) && strcmp(ctx.types[j], "function") != 0) {
                relationship rel;
                memset(&rel, 0, sizeof(rel));
                rel.from_scent = ctx.scent_ids[i];
                rel.to_scent = ctx.scent_ids[j];
                strncpy(rel.rel_type, "calls", 31);
                rel.confidence = 0.4;
                snprintf(rel.evidence, 255, "%s referenced in %s", ident, ctx.matches[j]);
                rel.created_at = time(NULL);
                bh_db_put_relationship(db, &rel);
            }
        }
    }
}

void bh_nose_build_import_relationships(bh_db *db, const char *workspace) {
    /* Find all import scents, then find matching names in other files */
    /* This is a workspace-wide pass — simplified version */
    rel_collect_ctx imports;
    memset(&imports, 0, sizeof(imports));

    /* Collect all imports in workspace by iterating all scents */
    /* For now, this is a stub that could be expanded */
    (void)db; (void)workspace;
}

/* ---- Main extract entry ---- */

int bh_nose_extract(bh_db *db, const char *file_path, const char *relative_path,
                    const char *workspace, const char *content_hash,
                    const char *language) {
    int line_count = 0;
    char **lines = read_file_lines(file_path, &line_count);
    if (!lines || line_count == 0) {
        if (lines) free_lines(lines, line_count);
        return 0;
    }

    if (strcmp(language, "python") == 0) {
        extract_python(db, file_path, relative_path, workspace, content_hash, lines, line_count);
    } else if (strcmp(language, "c") == 0 || strcmp(language, "cpp") == 0) {
        extract_c(db, file_path, relative_path, workspace, content_hash, lines, line_count);
    } else if (strcmp(language, "swift") == 0) {
        extract_swift(db, file_path, relative_path, workspace, content_hash, lines, line_count);
    } else if (strcmp(language, "markdown") == 0) {
        extract_markdown(db, file_path, relative_path, workspace, content_hash, lines, line_count);
    } else if (strcmp(language, "json") == 0) {
        extract_json(db, file_path, relative_path, workspace, content_hash, lines, line_count);
    } else if (strcmp(language, "sql") == 0) {
        extract_sql(db, file_path, relative_path, workspace, content_hash, lines, line_count);
    } else if (strcmp(language, "go") == 0) {
        extract_go(db, file_path, relative_path, workspace, content_hash, lines, line_count);
    } else if (strcmp(language, "rust") == 0) {
        extract_rust(db, file_path, relative_path, workspace, content_hash, lines, line_count);
    } else if (strcmp(language, "javascript") == 0) {
        extract_javascript(db, file_path, relative_path, workspace, content_hash, lines, line_count);
    } else if (strcmp(language, "shell") == 0) {
        extract_shell(db, file_path, relative_path, workspace, content_hash, lines, line_count);
    } else if (strcmp(language, "yaml") == 0) {
        extract_yaml(db, file_path, relative_path, workspace, content_hash, lines, line_count);
    } else if (strcmp(language, "toml") == 0) {
        extract_toml(db, file_path, relative_path, workspace, content_hash, lines, line_count);
    }

    bh_nose_build_relationships(db, file_path, workspace);
    free_lines(lines, line_count);
    return 0;
}
