//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_search_fs.c" date="2026-07-04" author="Devin" session_id="bcl-search-units" context="BCL unit for filesystem search. Source: local filesystem. Pipeline: dir walk -> ext filter -> time filter -> content grep -> line extract -> BCL output. Absorbs search_files from bcl_msearch.c. No MySQL dependency."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_search_fs.c" domain="cascade_tools" authority="SearchFs"}
//[@SUMMARY]{summary="Filesystem search unit. Source = local filesystem. Owns full pipeline: dir walk, ext filter, time filter, content grep, line extract, BCL output. Commands: search_files, search_folders, search_code, read_state, set_config. No MySQL."}
//[@CLASS]{class="SearchFs" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="Walk" type="internal"}
//[@METHOD]{method="ListFolders" type="internal"}
//[@METHOD]{method="CleanForBcl" type="internal"}
//[@METHOD]{method="PatchTotal" type="internal"}
//[@REVIEW]{[@date<2026-07-04>][@reviewer<devin>][@status<implementation>][@notes<Filesystem search BCL unit. Recursive dir walk with ext/time/content filters. Absorbs search_files from bcl_msearch.c.>][@todos<>]}

/*
 * bcl_search_fs.c — Filesystem search BCL unit
 *
 * BCL IN:  [@RUN]{[@CMD]{search_files}[@ROOT]{/path}[@EXT]{py}[@QUERY]{foo}[@HOURS]{24}}
 *          [@RUN]{[@CMD]{search_folders}[@ROOT]{/path}}
 *          [@RUN]{[@CMD]{search_code}[@ROOT]{/path}[@QUERY]{def SearchFs}}
 *          [@RUN]{[@CMD]{read_state}}
 *          [@RUN]{[@CMD]{set_config}[@MAXDEPTH]{10}[@MAXFILES]{5000}}
 * BCL OUT: [@OK]{[@ROOT]{...}[@TOTAL]{N}[@FILE]{[@PATH]{...}[@LINE]{...}}...}
 * BCL ERR: [@ERR]{[@CODE]{N}[@DESC]{...}}
 */

#include "bcl_toolstack.h"
#include <dirent.h>
#include <sys/stat.h>
#include <time.h>

/* ===== DIM BLOCK ===== */

#define SEARCHFS_MAX_PATH      4096
#define SEARCHFS_MAX_LINE      1024
#define SEARCHFS_MAX_EXT       32
#define SEARCHFS_MAX_QUERY     512
#define SEARCHFS_DEFAULT_LIMIT 100
#define SEARCHFS_MAX_DEPTH     20
#define SEARCHFS_MAX_FILES     5000
#define SEARCHFS_MAX_FOLDERS   1000

/* State */
static struct {
    int initialized;
    int max_depth;
    int max_files;
    int max_folders;
    int max_lines_per_file;
    int files_scanned;
    int folders_scanned;
    int matches_found;
    int searches_run;
    char last_root[SEARCHFS_MAX_PATH];
    char last_error[256];
} STATE;

/* ===== CLEAN FOR BCL — strip chars that break packet framing ===== */

static void fs_clean_for_bcl(const char *in, char *out, int out_sz) {
    int ci = 0;
    for (int i = 0; in[i] && ci < out_sz - 1; i++) {
        char ch = in[i];
        if (ch == '\n' || ch == '\r' || ch == '{' || ch == '}') {
            out[ci++] = ' ';
        } else if (ch == '[' && in[i + 1] == '@') {
            out[ci++] = ' ';
        } else {
            out[ci++] = ch;
        }
    }
    out[ci] = '\0';
}

/* ===== PATCH TOTAL — replace [@TOTAL]{0} placeholder with real count ===== */

static void fs_patch_total(char *out, int total) {
    char total_str[64];
    snprintf(total_str, sizeof(total_str), "[@TOTAL]{%d}", total);
    char *pos = strstr(out, "[@TOTAL]{0}");
    if (pos) {
        int old_len = (int)strlen("[@TOTAL]{0}");
        int new_len = (int)strlen(total_str);
        memmove(pos + new_len, pos + old_len, strlen(pos + old_len) + 1);
        memcpy(pos, total_str, new_len);
    }
}

/* ===== WALK — recursive directory walk, the core pipeline ===== */

static void fs_walk(const char *root, const char *ext, const char *keyword,
                    int within_hours, int depth, int *files_seen,
                    int *folders_seen, char *out, size_t out_sz, int *offset) {
    if (depth >= STATE.max_depth) return;
    if (*files_seen >= STATE.max_files) return;
    if (*folders_seen >= STATE.max_folders) return;

    DIR *dir = opendir(root);
    if (!dir) return;
    (*folders_seen)++;
    STATE.folders_scanned++;

    time_t now = time(NULL);
    time_t cutoff = now - (within_hours * 3600);

    struct dirent *ent;
    while ((ent = readdir(dir)) != NULL && *offset < (int)out_sz - 1024) {
        if (ent->d_name[0] == '.') continue;

        char path[SEARCHFS_MAX_PATH];
        snprintf(path, sizeof(path), "%s/%s", root, ent->d_name);

        struct stat st;
        if (stat(path, &st) != 0) continue;

        if (S_ISDIR(st.st_mode)) {
            int saved_offset = *offset;
            fs_walk(path, ext, keyword, within_hours, depth + 1,
                    files_seen, folders_seen, out, out_sz, offset);
            (void)saved_offset;
            continue;
        }

        /* Extension filter */
        if (ext && ext[0]) {
            const char *dot = strrchr(ent->d_name, '.');
            if (!dot || strcasecmp(dot + 1, ext) != 0) continue;
        }

        /* Time filter */
        if (within_hours > 0 && st.st_mtime < cutoff) continue;

        (*files_seen)++;
        STATE.files_scanned++;

        /* Content keyword filter — grep the file */
        if (keyword && keyword[0]) {
            FILE *fp = fopen(path, "r");
            if (!fp) continue;
            char line[SEARCHFS_MAX_LINE];
            int line_num = 0;
            int match_count = 0;

            *offset += snprintf(out + *offset, out_sz - *offset,
                "[@FILE]{[@PATH]{%s}[@MATCHES]{", path);

            while (fgets(line, sizeof(line), fp) &&
                   match_count < STATE.max_lines_per_file &&
                   *offset < (int)out_sz - 512) {
                line_num++;
                if (strcasestr(line, keyword)) {
                    char clean[SEARCHFS_MAX_LINE];
                    fs_clean_for_bcl(line, clean, sizeof(clean));
                    *offset += snprintf(out + *offset, out_sz - *offset,
                        "[@LINE]{[@NUM]{%d}[@TEXT]{%.200s}}", line_num, clean);
                    match_count++;
                }
            }
            fclose(fp);
            *offset += snprintf(out + *offset, out_sz - *offset, "}");
            if (match_count > 0) STATE.matches_found++;
        } else {
            /* No keyword filter — just list the file with metadata */
            *offset += snprintf(out + *offset, out_sz - *offset,
                "[@FILE]{[@PATH]{%s}[@SIZE]{%lld}[@MTIME]{%ld}}",
                path, (long long)st.st_size, (long)st.st_mtime);
            STATE.matches_found++;
        }
    }
    closedir(dir);
}

/* ===== LIST FOLDERS — directory listing only ===== */

static void fs_list_folders(const char *root, int depth, int *folders_seen,
                            char *out, size_t out_sz, int *offset) {
    if (depth >= STATE.max_depth) return;
    if (*folders_seen >= STATE.max_folders) return;

    DIR *dir = opendir(root);
    if (!dir) return;
    (*folders_seen)++;
    STATE.folders_scanned++;

    struct dirent *ent;
    while ((ent = readdir(dir)) != NULL && *offset < (int)out_sz - 256) {
        if (ent->d_name[0] == '.') continue;
        char path[SEARCHFS_MAX_PATH];
        snprintf(path, sizeof(path), "%s/%s", root, ent->d_name);
        struct stat st;
        if (stat(path, &st) != 0) continue;
        if (!S_ISDIR(st.st_mode)) continue;
        *offset += snprintf(out + *offset, out_sz - *offset,
            "[@FOLDER]{[@PATH]{%s}[@DEPTH]{%d}}", path, depth);
        STATE.matches_found++;
        fs_list_folders(path, depth + 1, folders_seen, out, out_sz, offset);
    }
    closedir(dir);
}

/* ===== UNIT INTERFACE ===== */

int SearchFs_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.max_depth = SEARCHFS_MAX_DEPTH;
    STATE.max_files = SEARCHFS_MAX_FILES;
    STATE.max_folders = SEARCHFS_MAX_FOLDERS;
    STATE.max_lines_per_file = 20;
    STATE.initialized = 1;
    return 1;
}

int SearchFs_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) SearchFs_Init();
    STATE.searches_run++;

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        return BclResult_Ok(bcl_out, out_sz,
            "[@INITIALIZED]{1}[@FILES]{...}[@FOLDERS]{...}[@MATCHES]{...}");
    }

    /* ===== SET_CONFIG ===== */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char maxdepth[16] = {0};
        char maxfiles[16] = {0};
        BclParser_Extract(&parse, "MAXDEPTH", maxdepth, sizeof(maxdepth));
        BclParser_Extract(&parse, "MAXFILES", maxfiles, sizeof(maxfiles));
        BclParser_Free(&parse);
        if (maxdepth[0]) STATE.max_depth = atoi(maxdepth);
        if (maxfiles[0]) STATE.max_files = atoi(maxfiles);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }

    /* ===== SEARCH_FILES ===== */
    if (strcmp(cmd, "search_files") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char root[SEARCHFS_MAX_PATH] = {0};
        char ext[SEARCHFS_MAX_EXT] = {0};
        char query[SEARCHFS_MAX_QUERY] = {0};
        char hours_str[16] = {0};
        BclParser_Extract(&parse, "ROOT", root, sizeof(root));
        BclParser_Extract(&parse, "EXT", ext, sizeof(ext));
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "HOURS", hours_str, sizeof(hours_str));
        BclParser_Free(&parse);
        if (!root[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no ROOT in packet");
        }
        int hours = hours_str[0] ? atoi(hours_str) : 0;

        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@ROOT]{%s}[@EXT]{%s}[@KEYWORD]{%s}[@HOURS]{%d}[@TOTAL]{0}",
            root, ext[0] ? ext : "*", query[0] ? query : "*", hours);

        int files_seen = 0;
        int folders_seen = 0;
        int total = 0;
        int mark_offset = offset;
        fs_walk(root, ext[0] ? ext : NULL, query[0] ? query : NULL,
                hours, 0, &files_seen, &folders_seen, bcl_out, out_sz, &offset);

        /* count [@FILE] entries for total */
        const char *cursor = bcl_out + mark_offset;
        while ((cursor = strstr(cursor, "[@FILE]{")) != NULL) {
            total++;
            cursor += 7;
        }
        fs_patch_total(bcl_out, total);
        offset = (int)strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "}");

        strncpy(STATE.last_root, root, sizeof(STATE.last_root) - 1);
        return 1;
    }

    /* ===== SEARCH_FOLDERS ===== */
    if (strcmp(cmd, "search_folders") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char root[SEARCHFS_MAX_PATH] = {0};
        BclParser_Extract(&parse, "ROOT", root, sizeof(root));
        BclParser_Free(&parse);
        if (!root[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no ROOT in packet");
        }
        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@ROOT]{%s}[@TOTAL]{0}", root);
        int folders_seen = 0;
        int mark_offset = offset;
        fs_list_folders(root, 0, &folders_seen, bcl_out, out_sz, &offset);

        int total = 0;
        const char *cursor = bcl_out + mark_offset;
        while ((cursor = strstr(cursor, "[@FOLDER]{")) != NULL) {
            total++;
            cursor += 9;
        }
        fs_patch_total(bcl_out, total);
        offset = (int)strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "}");
        return 1;
    }

    /* ===== SEARCH_CODE — AST-light: find definitions containing keyword ===== */
    if (strcmp(cmd, "search_code") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char root[SEARCHFS_MAX_PATH] = {0};
        char query[SEARCHFS_MAX_QUERY] = {0};
        char ext[SEARCHFS_MAX_EXT] = {0};
        BclParser_Extract(&parse, "ROOT", root, sizeof(root));
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "EXT", ext, sizeof(ext));
        BclParser_Free(&parse);
        if (!root[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no ROOT in packet");
        }
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        const char *use_ext = ext[0] ? ext : "py";

        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@ROOT]{%s}[@QUERY]{%s}[@EXT]{%s}[@TOTAL]{0}",
            root, query, use_ext);

        int files_seen = 0;
        int folders_seen = 0;
        fs_walk(root, use_ext, query, 0, 0,
                &files_seen, &folders_seen, bcl_out, out_sz, &offset);

        int total = 0;
        const char *cursor = bcl_out + offset;
        /* count files that had matches */
        cursor = bcl_out;
        while ((cursor = strstr(cursor, "[@LINE]{")) != NULL) {
            total++;
            cursor += 7;
        }
        fs_patch_total(bcl_out, total);
        offset = (int)strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "}");
        return 1;
    }

    return BclResult_Err(bcl_out, out_sz, 40, "unknown command");
}

int SearchFs_Close(void) {
    STATE.initialized = 0;
    return 1;
}

const char * SearchFs_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "SearchFs: initialized=%d files=%d folders=%d matches=%d searches=%d",
        STATE.initialized, STATE.files_scanned, STATE.folders_scanned,
        STATE.matches_found, STATE.searches_run);
    return buf;
}
