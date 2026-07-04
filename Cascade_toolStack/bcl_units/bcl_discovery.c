//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_discovery.c" date="2026-07-04" author="Devin" session_id="bcl-discovery-impl" context="BCL unit for code discovery and analysis. Walks directory trees with nftw, finds code files by extension, analyzes single files for lines/classes/functions/imports, renders directory trees, tracks discovery stats by language."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_discovery.c" domain="cascade_tools" authority="Discovery"}
//[@SUMMARY]{summary="Code discovery and analysis unit. Commands: discover, analyze, tree, stats, read_state, set_config. Uses nftw for directory walking, strstr for class/function detection, stat for file sizes. Tracks files_by_lang across 10 languages."}
//[@CLASS]{class="Discovery" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="Discover" type="internal"}
//[@METHOD]{method="Analyze" type="internal"}
//[@METHOD]{method="Tree" type="internal"}
//[@METHOD]{method="LangIndex" type="internal"}
//[@METHOD]{method="IsIgnored" type="internal"}
//[@REVIEW]{[@date<2026-07-04>][@reviewer<devin>][@status<implementation>][@notes<Full discovery unit. nftw walk, per-language stats, single-file analyze with strstr-based class/function/import detection.>][@todos<>]}

/*
 * bcl_discovery.c — Code discovery and analysis BCL unit
 * BCL IN:  discover  [@PATH]{/dir}[@EXT]{py,c,h}[@MAX]{100}
 *          analyze   [@PATH]{file.py}
 *          tree      [@PATH]{/path}[@DEPTH]{3}
 *          stats | read_state | set_config [@EXTENSIONS]{..}[@MAXDEPTH]{N}[@IGNOREDIRS]{..}
 * BCL OUT: [@OK]{[@TOTAL]{N}[@FILE]{[@PATH]{..}[@LANG]{py}[@SIZE]{..}}...}
 * BCL ERR: [@ERR]{[@CODE]{N}[@DESC]{..}}
 */

#include "bcl_toolstack.h"
#include <ftw.h>
#include <sys/stat.h>
#include <dirent.h>
#include <fnmatch.h>

#define DISC_MAX_PATH     4096
#define DISC_MAX_LINE     1024
#define DISC_MAX_EXT      256
#define DISC_MAX_IGNORE   64
#define DISC_MAX_IGNORES  16
#define DISC_MAX_DEPTH    20
#define DISC_MAX_FILES    5000
#define DISC_LANG_COUNT   10
#define DISC_MAX_BUF      65536

/* Language table — index matches files_by_lang slot */
static const char *LANG_EXT[DISC_LANG_COUNT] = {
    "py", "c", "h", "js", "ts", "swift", "rs", "go", "java", "rb"
};
static const char *LANG_NAME[DISC_LANG_COUNT] = {
    "python", "c", "h", "javascript", "typescript",
    "swift", "rust", "go", "java", "ruby"
};

/* State */
static struct {
    int  initialized;
    int  total_discovered;
    int  total_analyzed;
    int  files_by_lang[DISC_LANG_COUNT];
    char last_path[DISC_MAX_PATH];
    char ignore_dirs[DISC_MAX_IGNORES][DISC_MAX_IGNORE];
    int  ignore_count;
    int  max_depth;
} STATE;
/* nftw walk context (file-scope — nftw callback takes no user data) */
static struct {
    char ext_filter[DISC_MAX_EXT];
    int  max_files;
    int  files_emitted;
    int  total;
    int  offset;
    char *out;
    size_t out_sz;
} WALK;
/* LANG INDEX — map extension to language slot, -1 if unknown */
static int disc_lang_index(const char *ext) {
    if (!ext || !ext[0]) return -1;
    for (int i = 0; i < DISC_LANG_COUNT; i++) {
        if (strcasecmp(ext, LANG_EXT[i]) == 0) return i;
    }
    return -1;
}
/* IS IGNORED — check basename against ignore_dirs list */
static int disc_is_ignored(const char *name) {
    for (int i = 0; i < STATE.ignore_count; i++) {
        if (strcmp(name, STATE.ignore_dirs[i]) == 0) return 1;
    }
    return 0;
}
/* EXT MATCHES — check a file extension against the comma filter */
static int disc_ext_matches(const char *ext) {
    if (!WALK.ext_filter[0]) return disc_lang_index(ext) >= 0;
    char buf[DISC_MAX_EXT];
    strncpy(buf, WALK.ext_filter, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = '\0';
    char *tok = strtok(buf, ",");
    while (tok) {
        while (*tok == ' ') tok++;
        if (strcasecmp(ext, tok) == 0) return 1;
        tok = strtok(NULL, ",");
    }
    return 0;
}

/* DISCOVER WALK — opendir/readdir recursion (portable, supports ignore_dirs) */
static void disc_walk(const char *root, int depth) {
    if (WALK.files_emitted >= WALK.max_files) return;
    if (WALK.offset >= (int)WALK.out_sz - 512) return;
    if (depth > STATE.max_depth) return;

    DIR *dir = opendir(root);
    if (!dir) return;

    struct dirent *ent;
    while ((ent = readdir(dir)) != NULL &&
           WALK.files_emitted < WALK.max_files &&
           WALK.offset < (int)WALK.out_sz - 512) {
        if (ent->d_name[0] == '.') continue;
        char path[DISC_MAX_PATH];
        snprintf(path, sizeof(path), "%s/%s", root, ent->d_name);
        struct stat st;
        if (stat(path, &st) != 0) continue;

        if (S_ISDIR(st.st_mode)) {
            if (disc_is_ignored(ent->d_name)) continue;
            disc_walk(path, depth + 1);
            continue;
        }
        if (!S_ISREG(st.st_mode)) continue;

        const char *dot = strrchr(ent->d_name, '.');
        if (!dot || !disc_ext_matches(dot + 1)) continue;
        int lang = disc_lang_index(dot + 1);
        const char *lang_name = (lang >= 0) ? LANG_NAME[lang] : "unknown";

        WALK.offset += snprintf(WALK.out + WALK.offset, WALK.out_sz - WALK.offset,
            "[@FILE]{[@PATH]{%s}[@LANG]{%s}[@SIZE]{%lld}}",
            path, lang_name, (long long)st.st_size);
        WALK.files_emitted++;
        WALK.total++;
        STATE.total_discovered++;
        if (lang >= 0) STATE.files_by_lang[lang]++;
    }
    closedir(dir);
}

/* TREE WALK — opendir/readdir recursion with depth-limited code files */
static struct {
    int  max_depth;
    int  offset;
    char *out;
    size_t out_sz;
    int  total;
} TREE_WALK;

static void disc_tree_walk(const char *root, int depth) {
    if (TREE_WALK.offset >= (int)TREE_WALK.out_sz - 512) return;
    if (depth > TREE_WALK.max_depth) return;

    DIR *dir = opendir(root);
    if (!dir) return;

    struct dirent *ent;
    while ((ent = readdir(dir)) != NULL &&
           TREE_WALK.offset < (int)TREE_WALK.out_sz - 512) {
        if (ent->d_name[0] == '.') continue;
        char path[DISC_MAX_PATH];
        snprintf(path, sizeof(path), "%s/%s", root, ent->d_name);
        struct stat st;
        if (stat(path, &st) != 0) continue;

        if (S_ISDIR(st.st_mode)) {
            if (disc_is_ignored(ent->d_name)) continue;
            TREE_WALK.offset += snprintf(
                TREE_WALK.out + TREE_WALK.offset,
                TREE_WALK.out_sz - TREE_WALK.offset,
                "[@NODE]{[@PATH]{%s}[@TYPE]{dir}[@DEPTH]{%d}}", path, depth);
            TREE_WALK.total++;
            disc_tree_walk(path, depth + 1);
            continue;
        }
        if (!S_ISREG(st.st_mode)) continue;

        const char *dot = strrchr(ent->d_name, '.');
        if (!dot) continue;
        int lang = disc_lang_index(dot + 1);
        if (lang < 0) continue;

        TREE_WALK.offset += snprintf(
            TREE_WALK.out + TREE_WALK.offset,
            TREE_WALK.out_sz - TREE_WALK.offset,
            "[@NODE]{[@PATH]{%s}[@TYPE]{file}[@LANG]{%s}[@SIZE]{%lld}[@DEPTH]{%d}}",
            path, LANG_NAME[lang], (long long)st.st_size, depth);
        TREE_WALK.total++;
    }
    closedir(dir);
}

/* helper: does p start with token (prefix match) */
static int disc_starts(const char *p, const char *tok) {
    return strstr(p, tok) == p;
}

/* patch [@TOTAL]{0} placeholder with real count */
static void disc_patch_total(char *out, int total) {
    char total_str[32];
    snprintf(total_str, sizeof(total_str), "[@TOTAL]{%d}", total);
    char *pos = strstr(out, "[@TOTAL]{0}");
    if (!pos) return;
    int old_len = (int)strlen("[@TOTAL]{0}");
    int new_len = (int)strlen(total_str);
    memmove(pos + new_len, pos + old_len, strlen(pos + old_len) + 1);
    memcpy(pos, total_str, new_len);
}

/* render per-language counts into a BCL fragment */
static void disc_lang_bcl(char *buf, size_t buf_sz) {
    int off = 0;
    for (int i = 0; i < DISC_LANG_COUNT; i++) {
        off += snprintf(buf + off, buf_sz - off, "[@%s]{%d}",
                        LANG_NAME[i], STATE.files_by_lang[i]);
    }
}

/* ANALYZE — single file: lines, classes, functions, imports */
static int disc_analyze_file(const char *path, char *out, size_t out_sz) {
    FILE *fp = fopen(path, "r");
    if (!fp) return 0;
    const char *dot = strrchr(path, '.');
    int lang = disc_lang_index(dot ? dot + 1 : "");
    const char *lang_name = (lang >= 0) ? LANG_NAME[lang] : "unknown";
    char line[DISC_MAX_LINE];
    int line_count = 0, class_count = 0, function_count = 0, import_count = 0;

    while (fgets(line, sizeof(line), fp)) {
        line_count++;
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;  /* strip leading whitespace */
        if (disc_starts(p, "class ") || disc_starts(p, "struct ") ||
            disc_starts(p, "class\t")) class_count++;
        if (disc_starts(p, "def ") || disc_starts(p, "int ") ||
            disc_starts(p, "void ") || disc_starts(p, "static ") ||
            disc_starts(p, "func ") || disc_starts(p, "fn ") ||
            disc_starts(p, "public ") || disc_starts(p, "private "))
            function_count++;
        if (disc_starts(p, "import ") || disc_starts(p, "#include") ||
            disc_starts(p, "from ") || disc_starts(p, "require(") ||
            disc_starts(p, "use ")) import_count++;
    }
    fclose(fp);
    struct stat st;
    long long size = (stat(path, &st) == 0) ? (long long)st.st_size : 0;
    snprintf(out, out_sz,
        "[@OK]{[@PATH]{%s}[@LANG]{%s}[@LINES]{%d}[@CLASSES]{%d}"
        "[@FUNCTIONS]{%d}[@IMPORTS]{%d}[@SIZE]{%lld}}",
        path, lang_name, line_count, class_count, function_count, import_count, size);
    STATE.total_analyzed++;
    if (lang >= 0) STATE.files_by_lang[lang]++;
    return 1;
}

/* UNIT INTERFACE */
int Discovery_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.max_depth = DISC_MAX_DEPTH;
    /* default ignore dirs */
    const char *defaults[] = {".git", "node_modules", "__pycache__", "venv"};
    for (int i = 0; i < 4 && STATE.ignore_count < DISC_MAX_IGNORES; i++) {
        strncpy(STATE.ignore_dirs[STATE.ignore_count], defaults[i],
                DISC_MAX_IGNORE - 1);
        STATE.ignore_count++;
    }
    STATE.initialized = 1;
    return 1;
}

int Discovery_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) Discovery_Init();

    /* READ_STATE */
    if (strcmp(cmd, "read_state") == 0) {
        char lang_buf[256];
        disc_lang_bcl(lang_buf, sizeof(lang_buf));
        char body[DISC_MAX_BUF];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{1}[@TOTAL_DISCOVERED]{%d}[@TOTAL_ANALYZED]{%d}"
            "[@LAST_PATH]{%s}[@MAXDEPTH]{%d}[@IGNORES]{%d}%s",
            STATE.total_discovered, STATE.total_analyzed,
            STATE.last_path, STATE.max_depth, STATE.ignore_count, lang_buf);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* SET_CONFIG */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char maxdepth[16] = {0};
        char ignores[DISC_MAX_EXT] = {0};
        BclParser_Extract(&parse, "MAXDEPTH", maxdepth, sizeof(maxdepth));
        BclParser_Extract(&parse, "IGNOREDIRS", ignores, sizeof(ignores));
        BclParser_Free(&parse);
        if (maxdepth[0]) STATE.max_depth = atoi(maxdepth);
        if (ignores[0]) {
            STATE.ignore_count = 0;
            char *tok = strtok(ignores, ",");
            while (tok && STATE.ignore_count < DISC_MAX_IGNORES) {
                while (*tok == ' ') tok++;
                strncpy(STATE.ignore_dirs[STATE.ignore_count], tok,
                        DISC_MAX_IGNORE - 1);
                STATE.ignore_count++;
                tok = strtok(NULL, ",");
            }
        }
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }

    /* DISCOVER */
    if (strcmp(cmd, "discover") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[DISC_MAX_PATH] = {0};
        char ext[DISC_MAX_EXT] = {0};
        char max_str[16] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Extract(&parse, "EXT", ext, sizeof(ext));
        BclParser_Extract(&parse, "MAX", max_str, sizeof(max_str));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        }
        struct stat st;
        if (stat(path, &st) != 0 || !S_ISDIR(st.st_mode)) {
            return BclResult_Err(bcl_out, out_sz, 21, "PATH is not a directory");
        }
        int max_files = max_str[0] ? atoi(max_str) : 100;
        if (max_files <= 0 || max_files > DISC_MAX_FILES) max_files = DISC_MAX_FILES;

        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@PATH]{%s}[@EXT]{%s}[@MAX]{%d}[@TOTAL]{0}",
            path, ext[0] ? ext : "*", max_files);

        memset(&WALK, 0, sizeof(WALK));
        strncpy(WALK.ext_filter, ext, sizeof(WALK.ext_filter) - 1);
        WALK.max_files = max_files;
        WALK.out = bcl_out;
        WALK.out_sz = out_sz;
        WALK.offset = offset;

        disc_walk(path, 0);

        disc_patch_total(bcl_out, WALK.total);
        offset = (int)strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "}");

        strncpy(STATE.last_path, path, sizeof(STATE.last_path) - 1);
        return 1;
    }

    /* ANALYZE */
    if (strcmp(cmd, "analyze") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[DISC_MAX_PATH] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        }
        struct stat st;
        if (stat(path, &st) != 0) {
            return BclResult_Err(bcl_out, out_sz, 22, "file not found");
        }
        if (!S_ISREG(st.st_mode)) {
            return BclResult_Err(bcl_out, out_sz, 23, "PATH is not a regular file");
        }
        if (!disc_analyze_file(path, bcl_out, out_sz)) {
            return BclResult_Err(bcl_out, out_sz, 24, "cannot open file");
        }
        strncpy(STATE.last_path, path, sizeof(STATE.last_path) - 1);
        return 1;
    }

    /* TREE */
    if (strcmp(cmd, "tree") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[DISC_MAX_PATH] = {0};
        char depth_str[16] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Extract(&parse, "DEPTH", depth_str, sizeof(depth_str));
        BclParser_Free(&parse);
        if (!path[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        }
        struct stat st;
        if (stat(path, &st) != 0 || !S_ISDIR(st.st_mode)) {
            return BclResult_Err(bcl_out, out_sz, 21, "PATH is not a directory");
        }
        int depth = depth_str[0] ? atoi(depth_str) : 3;
        if (depth <= 0 || depth > DISC_MAX_DEPTH) depth = DISC_MAX_DEPTH;

        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset,
            "[@OK]{[@PATH]{%s}[@DEPTH]{%d}[@TOTAL]{0}", path, depth);

        memset(&TREE_WALK, 0, sizeof(TREE_WALK));
        TREE_WALK.max_depth = depth;
        TREE_WALK.out = bcl_out;
        TREE_WALK.out_sz = out_sz;
        TREE_WALK.offset = offset;

        disc_tree_walk(path, 0);

        disc_patch_total(bcl_out, TREE_WALK.total);
        offset = (int)strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "}");

        strncpy(STATE.last_path, path, sizeof(STATE.last_path) - 1);
        return 1;
    }

    /* STATS */
    if (strcmp(cmd, "stats") == 0) {
        char lang_buf[512];
        disc_lang_bcl(lang_buf, sizeof(lang_buf));
        char body[DISC_MAX_BUF];
        snprintf(body, sizeof(body),
            "[@TOTAL_DISCOVERED]{%d}[@TOTAL_ANALYZED]{%d}"
            "[@LAST_PATH]{%s}[@MAXDEPTH]{%d}%s",
            STATE.total_discovered, STATE.total_analyzed,
            STATE.last_path, STATE.max_depth, lang_buf);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    return BclResult_Err(bcl_out, out_sz, 40, "unknown command");
}

int Discovery_Close(void) {
    STATE.initialized = 0;
    STATE.ignore_count = 0;
    return 1;
}

const char * Discovery_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "Discovery: initialized=%d discovered=%d analyzed=%d ignores=%d",
        STATE.initialized, STATE.total_discovered, STATE.total_analyzed,
        STATE.ignore_count);
    return buf;
}
