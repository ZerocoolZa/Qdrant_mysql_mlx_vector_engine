//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_mdmerge.c" date="2026-07-04" author="Devin" session_id="bcl-mdmerge-impl" context="BCL unit for markdown file merging. Walks dirs, sorts .md files, concatenates with separator, generates TOC. Commands: merge, merge_files, toc, stats, read_state, set_config."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_mdmerge.c" domain="cascade_tools" authority="Mdmerge"}
//[@SUMMARY]{summary="Markdown file merger BCL unit. Walks directory for .md files, sorts by name/date/size, concatenates with separator, generates table of contents. Commands: merge, merge_files, toc, stats, read_state, set_config."}
//[@CLASS]{class="Mdmerge" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}

#include "bcl_toolstack.h"
#include <dirent.h>
#include <sys/stat.h>

#define MDMERGE_MAX_PATH    4096
#define MDMERGE_MAX_FILES   1024
#define MDMERGE_MAX_TOC     8192
#define MDMERGE_DEFAULT_SEP "\n\n---\n\n"

typedef struct {
    char path[MDMERGE_MAX_PATH];
    long size;
    time_t mtime;
} MdEntry;

/* State */
static struct {
    int  initialized;
    int  merges_run;
    int  files_merged;
    long total_lines;
    char last_output[MDMERGE_MAX_PATH];
    char separator[64];
    int  include_toc;
    char sort_order[16];   /* name, date, size */
} STATE;

static char * md_read_file(const char *path, long *out_size) {
    FILE *fp = fopen(path, "rb");
    if (!fp) return NULL;
    fseek(fp, 0, SEEK_END);
    long sz = ftell(fp);
    if (sz < 0) { fclose(fp); return NULL; }
    fseek(fp, 0, SEEK_SET);
    char *buf = (char *)malloc((size_t)sz + 1);
    if (!buf) { fclose(fp); return NULL; }
    size_t n = fread(buf, 1, (size_t)sz, fp);
    fclose(fp);
    buf[n] = '\0';
    if (out_size) *out_size = (long)n;
    return buf;
}

static long md_count_lines(const char *text) {
    long lines = 0;
    if (!text) return 0;
    for (const char *p = text; *p; p++) if (*p == '\n') lines++;
    return lines;
}

static void md_collect(const char *root, MdEntry *list, int *count, int depth) {
    if (depth > 16 || *count >= MDMERGE_MAX_FILES) return;
    DIR *dir = opendir(root);
    if (!dir) return;
    struct dirent *ent;
    while ((ent = readdir(dir)) != NULL && *count < MDMERGE_MAX_FILES) {
        if (ent->d_name[0] == '.') continue;
        char path[MDMERGE_MAX_PATH];
        snprintf(path, sizeof(path), "%s/%s", root, ent->d_name);
        struct stat st;
        if (stat(path, &st) != 0) continue;
        if (S_ISDIR(st.st_mode)) {
            md_collect(path, list, count, depth + 1);
            continue;
        }
        if (!S_ISREG(st.st_mode)) continue;
        const char *dot = strrchr(ent->d_name, '.');
        if (!dot || strcasecmp(dot + 1, "md") != 0) continue;
        MdEntry *e = &list[(*count)++];
        snprintf(e->path, sizeof(e->path), "%s", path);
        e->size = (long)st.st_size;
        e->mtime = st.st_mtime;
    }
    closedir(dir);
}

static int md_cmp_name(const void *a, const void *b) {
    return strcmp(((const MdEntry *)a)->path, ((const MdEntry *)b)->path);
}
static int md_cmp_date(const void *a, const void *b) {
    long da = (long)((const MdEntry *)a)->mtime, db = (long)((const MdEntry *)b)->mtime;
    return (da < db) ? -1 : (da > db) ? 1 : 0;
}
static int md_cmp_size(const void *a, const void *b) {
    long sa = ((const MdEntry *)a)->size, sb = ((const MdEntry *)b)->size;
    return (sa < sb) ? -1 : (sa > sb) ? 1 : 0;
}
static void md_sort(MdEntry *list, int count, const char *order) {
    int (*cmp)(const void *, const void *) = md_cmp_name;
    if (strcmp(order, "date") == 0) cmp = md_cmp_date;
    else if (strcmp(order, "size") == 0) cmp = md_cmp_size;
    qsort(list, count, sizeof(MdEntry), cmp);
}

static void md_scan_headers(const char *text, char *toc, int *toc_off, int toc_sz) {
    const char *p = text;
    while (*p && *toc_off < toc_sz - 256) {
        if (p == text || p[-1] == '\n') {
            if (p[0] != '#') { p++; continue; }
            int level = 0;
            while (p[level] == '#' && level < 6) level++;
            if (p[level] != ' ') { p++; continue; }
            const char *start = p + level + 1;
            const char *end = start;
            while (*end && *end != '\n') end++;
            int hlen = (int)(end - start);
            if (hlen > 0 && hlen < 200 && level <= 3) {
                *toc_off += snprintf(toc + *toc_off, toc_sz - *toc_off,
                    "%*s- %.*s\n", (level - 1) * 2, "", hlen, start);
            }
        }
        p++;
    }
}

static int md_build_toc(const char *text, char *out, int out_sz) {
    int off = snprintf(out, out_sz, "## Table of Contents\n\n");
    md_scan_headers(text, out, &off, out_sz);
    off += snprintf(out + off, out_sz - off, "\n");
    return off;
}

static int md_finish_merge(int count, const char *output, const char *sort_used,
                           char *bcl_out, size_t out_sz) {
    STATE.merges_run++;
    snprintf(STATE.last_output, sizeof(STATE.last_output), "%s", output);
    char body[512];
    if (sort_used) {
        snprintf(body, sizeof(body),
            "[@STATUS]{merged}[@FILES]{%d}[@OUTPUT]{%s}[@SORT]{%s}",
            count, output, sort_used);
    } else {
        snprintf(body, sizeof(body),
            "[@STATUS]{merged}[@FILES]{%d}[@OUTPUT]{%s}", count, output);
    }
    return BclResult_Ok(bcl_out, out_sz, body);
}

static int md_write_merged(MdEntry *list, int count, const char *output) {
    FILE *out = fopen(output, "wb");
    if (!out) return 0;
    long total_lines = 0;
    char toc[MDMERGE_MAX_TOC];

    /* Build TOC by scanning each file's headers */
    if (STATE.include_toc) {
        int toc_off = snprintf(toc, sizeof(toc), "## Table of Contents\n\n");
        for (int i = 0; i < count && toc_off < (int)sizeof(toc) - 512; i++) {
            long sz = 0;
            char *content = md_read_file(list[i].path, &sz);
            if (!content) continue;
            md_scan_headers(content, toc, &toc_off, (int)sizeof(toc));
            free(content);
        }
        toc_off += snprintf(toc + toc_off, sizeof(toc) - toc_off, "\n---\n\n");
        fwrite(toc, 1, toc_off, out);
    }

    for (int i = 0; i < count; i++) {
        long sz = 0;
        char *content = md_read_file(list[i].path, &sz);
        if (!content) continue;
        if (i > 0) {
            fwrite(STATE.separator, 1, strlen(STATE.separator), out);
        }
        fwrite(content, 1, sz, out);
        total_lines += md_count_lines(content);
        free(content);
        STATE.files_merged++;
    }
    fclose(out);
    STATE.total_lines += total_lines;
    return 1;
}

/* ===== UNIT INTERFACE ===== */

int Mdmerge_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    STATE.include_toc = 1;
    strncpy(STATE.separator, MDMERGE_DEFAULT_SEP, sizeof(STATE.separator) - 1);
    strncpy(STATE.sort_order, "name", sizeof(STATE.sort_order) - 1);
    return 1;
}

int Mdmerge_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) Mdmerge_Init();

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@MERGES]{%d}[@FILES]{%d}[@LINES]{%ld}"
            "[@LAST_OUTPUT]{%s}[@SEPARATOR]{%s}[@TOC]{%d}[@SORT]{%s}",
            STATE.initialized, STATE.merges_run, STATE.files_merged,
            STATE.total_lines, STATE.last_output, STATE.separator,
            STATE.include_toc, STATE.sort_order);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== STATS ===== */
    if (strcmp(cmd, "stats") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@MERGES]{%d}[@FILES]{%d}[@LINES]{%ld}[@LAST_OUTPUT]{%s}",
            STATE.merges_run, STATE.files_merged, STATE.total_lines,
            STATE.last_output);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== SET_CONFIG ===== */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char sep[64] = {0};
        char toc[8] = {0};
        char sort[16] = {0};
        BclParser_Extract(&parse, "SEPARATOR", sep, sizeof(sep));
        BclParser_Extract(&parse, "INCLUDE_TOC", toc, sizeof(toc));
        BclParser_Extract(&parse, "SORT_ORDER", sort, sizeof(sort));
        BclParser_Free(&parse);
        if (sep[0]) snprintf(STATE.separator, sizeof(STATE.separator), "%s", sep);
        if (toc[0]) STATE.include_toc = atoi(toc);
        if (sort[0]) snprintf(STATE.sort_order, sizeof(STATE.sort_order), "%s", sort);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }

    /* ===== MERGE — directory walk + sort + concat ===== */
    if (strcmp(cmd, "merge") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[MDMERGE_MAX_PATH] = {0};
        char output[MDMERGE_MAX_PATH] = {0};
        char sort[16] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Extract(&parse, "OUTPUT", output, sizeof(output));
        BclParser_Extract(&parse, "SORT", sort, sizeof(sort));
        BclParser_Free(&parse);
        if (!path[0]) return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        if (!output[0]) return BclResult_Err(bcl_out, out_sz, 21, "no OUTPUT in packet");

        MdEntry *list = (MdEntry *)calloc(MDMERGE_MAX_FILES, sizeof(MdEntry));
        if (!list) return BclResult_Err(bcl_out, out_sz, 50, "out of memory");
        int count = 0;
        md_collect(path, list, &count, 0);
        if (count == 0) {
            free(list);
            return BclResult_Err(bcl_out, out_sz, 30, "no .md files found");
        }
        md_sort(list, count, sort[0] ? sort : STATE.sort_order);
        if (!md_write_merged(list, count, output)) {
            free(list);
            return BclResult_Err(bcl_out, out_sz, 31, "cannot write output file");
        }
        free(list);
        return md_finish_merge(count, output, sort[0] ? sort : STATE.sort_order,
                               bcl_out, out_sz);
    }

    /* ===== MERGE_FILES — explicit file list via multiple FILE tags ===== */
    if (strcmp(cmd, "merge_files") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char output[MDMERGE_MAX_PATH] = {0};
        BclParser_Extract(&parse, "OUTPUT", output, sizeof(output));
        if (!output[0]) {
            BclParser_Free(&parse);
            return BclResult_Err(bcl_out, out_sz, 21, "no OUTPUT in packet");
        }
        MdEntry *list = (MdEntry *)calloc(MDMERGE_MAX_FILES, sizeof(MdEntry));
        if (!list) {
            BclParser_Free(&parse);
            return BclResult_Err(bcl_out, out_sz, 50, "out of memory");
        }
        int count = 0;
        for (int i = 0; i < parse.node_count && count < MDMERGE_MAX_FILES; i++) {
            if (strcmp(parse.nodes[i].tag, "FILE") == 0) {
                MdEntry *e = &list[count++];
                snprintf(e->path, sizeof(e->path), "%s", parse.nodes[i].content);
                struct stat st;
                if (stat(e->path, &st) == 0) {
                    e->size = (long)st.st_size;
                    e->mtime = st.st_mtime;
                }
            }
        }
        BclParser_Free(&parse);
        if (count == 0) {
            free(list);
            return BclResult_Err(bcl_out, out_sz, 30, "no FILE tags in packet");
        }
        md_sort(list, count, STATE.sort_order);
        if (!md_write_merged(list, count, output)) {
            free(list);
            return BclResult_Err(bcl_out, out_sz, 31, "cannot write output file");
        }
        free(list);
        return md_finish_merge(count, output, NULL, bcl_out, out_sz);
    }

    /* ===== TOC — generate table of contents for one file ===== */
    if (strcmp(cmd, "toc") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[MDMERGE_MAX_PATH] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Free(&parse);
        if (!path[0]) return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        long sz = 0;
        char *content = md_read_file(path, &sz);
        if (!content) return BclResult_Err(bcl_out, out_sz, 32, "cannot read file");
        char toc[MDMERGE_MAX_TOC];
        md_build_toc(content, toc, sizeof(toc));
        free(content);
        char body[MDMERGE_MAX_TOC + 128];
        snprintf(body, sizeof(body), "[@STATUS]{toc}[@TOC]{%s}", toc);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    return BclResult_Err(bcl_out, out_sz, 40, "unknown command");
}

int Mdmerge_Close(void) {
    STATE.initialized = 0;
    return 1;
}

const char * Mdmerge_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "Mdmerge: initialized=%d merges=%d files=%d lines=%ld sort=%s toc=%d",
        STATE.initialized, STATE.merges_run, STATE.files_merged,
        STATE.total_lines, STATE.sort_order, STATE.include_toc);
    return buf;
}
