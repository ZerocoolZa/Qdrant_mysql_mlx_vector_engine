//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_windir.c" date="2026-07-04" author="Devin" session_id="bcl-windir-impl" context="BCL unit for window directory management. Full implementation: list, create, move, copy, delete, size, read_state, set_config. Uses nftw for tree walks."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_windir.c" domain="cascade_tools" authority="Windir"}
//[@SUMMARY]{summary="Window directory manager BCL unit. Commands: list (walk tree to DEPTH), create (mkdir -p), move (rename), copy (recursive nftw), delete (nftw + unlink + rmdir, CONFIRM required), size (sum file sizes), read_state, set_config. Uses nftw() for directory operations."}
//[@CLASS]{class="Windir" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="ListWalk" type="internal"}
//[@METHOD]{method="DeleteWalk" type="internal"}
//[@METHOD]{method="CopyWalk" type="internal"}
//[@METHOD]{method="SizeWalk" type="internal"}
//[@METHOD]{method="MkdirP" type="internal"}
//[@METHOD]{method="CopyFile" type="internal"}
//[@REVIEW]{[@date<2026-07-04>][@reviewer<devin>][@status<implementation>][@notes<Window directory manager. nftw-based tree walks for list/copy/delete/size. mkdir -p for create. rename for move.>][@todos<>]}
/* bcl_windir.c — Window directory manager BCL unit
 * BCL IN:  list/create/move/copy/delete/size/read_state/set_config
 * BCL OUT: [@OK]{[@STATUS]{...}...}  |  [@ERR]{[@CODE]{N}[@DESC]{...}} */
#include "bcl_toolstack.h"
#include <ftw.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>
#include <dirent.h>
#include <limits.h>
#include <stdarg.h>

#define WINDIR_MAX_PATH      4096
#define WINDIR_MAX_OUT       65536
#define WINDIR_DEFAULT_DEPTH 3
#define WINDIR_MAX_DEPTH     20
#define WINDIR_MAX_DIRS      2000
#define WINDIR_COPY_BUF      65536
static struct {
    int  initialized;
    int  dirs_listed;
    int  dirs_created;
    int  dirs_moved;
    int  dirs_deleted;
    long bytes_copied;
    char last_path[WINDIR_MAX_PATH];
    int  default_depth;
    int  confirm_required;
    int  follow_symlinks;
} STATE;
static char  g_out_buf[WINDIR_MAX_OUT];
static int   g_out_offset;
static int   g_dir_count;
static int   g_max_depth;
static long  g_total_bytes;
static int   g_file_count;
static char  g_copy_dest[WINDIR_MAX_PATH];
static char  g_copy_src[WINDIR_MAX_PATH];
static int   g_copy_src_len;
static int   g_walk_error;
static void windir_clean_for_bcl(const char *in, char *out, int out_sz) {
    int ci = 0;
    for (int i = 0; in[i] && ci < out_sz - 1; i++) {
        char ch = in[i];
        if (ch == '\n' || ch == '\r' || ch == '{' || ch == '}') out[ci++] = ' ';
        else if (ch == '[' && in[i + 1] == '@') out[ci++] = ' ';
        else out[ci++] = ch;
    }
    out[ci] = '\0';
}

static void windir_append(const char *fmt, ...) {
    if (g_out_offset >= WINDIR_MAX_OUT - 1024) return;
    va_list ap;
    va_start(ap, fmt);
    g_out_offset += vsnprintf(g_out_buf + g_out_offset,
                              WINDIR_MAX_OUT - g_out_offset, fmt, ap);
    va_end(ap);
}

/* LIST WALK — nftw callback, emit [@DIR] for each directory */
static int windir_list_cb(const char *fpath, const struct stat *sb,
                          int typeflag, struct FTW *ftwbuf) {
    (void)sb;
    if (g_dir_count >= WINDIR_MAX_DIRS) return 1;
    if (ftwbuf->level > g_max_depth) return 0;
    if (typeflag == FTW_D && ftwbuf->level > 0) {
        char clean[WINDIR_MAX_PATH];
        windir_clean_for_bcl(fpath, clean, sizeof(clean));
        windir_append("[@DIR]{[@PATH]{%s}[@DEPTH]{%d}}", clean, ftwbuf->level);
        g_dir_count++;
    }
    return 0;
}

/* DELETE WALK — nftw with FTW_DEPTH: unlink files, rmdir dirs */
static int windir_delete_cb(const char *fpath, const struct stat *sb,
                            int typeflag, struct FTW *ftwbuf) {
    (void)sb; (void)ftwbuf;
    if (typeflag == FTW_F || typeflag == FTW_SL) {
        if (unlink(fpath) != 0) { g_walk_error = errno; return 1; }
    } else if (typeflag == FTW_DP) {
        if (rmdir(fpath) != 0) { g_walk_error = errno; return 1; }
        STATE.dirs_deleted++;
    }
    return 0;
}

/* SIZE WALK — nftw callback, sum file sizes */
static int windir_size_cb(const char *fpath, const struct stat *sb,
                          int typeflag, struct FTW *ftwbuf) {
    (void)fpath; (void)ftwbuf;
    if (typeflag == FTW_F) {
        g_total_bytes += (long)sb->st_size;
        g_file_count++;
    }
    return 0;
}

/* COPY FILE — single file copy via fopen/fwrite */
static int windir_copy_file(const char *src, const char *dst) {
    FILE *in = fopen(src, "rb");
    if (!in) return -1;
    FILE *out = fopen(dst, "wb");
    if (!out) { fclose(in); return -1; }
    char buf[WINDIR_COPY_BUF];
    size_t n;
    while ((n = fread(buf, 1, sizeof(buf), in)) > 0) {
        size_t w = fwrite(buf, 1, n, out);
        if (w != n) { fclose(in); fclose(out); return -1; }
        STATE.bytes_copied += (long)w;
    }
    int ok = ferror(in) ? -1 : 0;
    fclose(in);
    fclose(out);
    struct stat st;
    if (stat(src, &st) == 0) chmod(dst, st.st_mode & 0777);
    return ok;
}

/* COPY WALK — nftw callback, recreate tree under dest */
static int windir_copy_cb(const char *fpath, const struct stat *sb,
                          int typeflag, struct FTW *ftwbuf) {
    (void)sb; (void)ftwbuf;
    const char *rel = fpath + g_copy_src_len;
    while (*rel == '/') rel++;
    char dst[WINDIR_MAX_PATH];
    snprintf(dst, sizeof(dst), "%s/%s", g_copy_dest, rel);
    if (typeflag == FTW_D) {
        if (mkdir(dst, 0755) != 0 && errno != EEXIST) { g_walk_error = errno; return 1; }
    } else if (typeflag == FTW_F) {
        if (windir_copy_file(fpath, dst) != 0) { g_walk_error = errno; return 1; }
    } else if (typeflag == FTW_SL) {
        char target[WINDIR_MAX_PATH];
        ssize_t tlen = readlink(fpath, target, sizeof(target) - 1);
        if (tlen > 0) { target[tlen] = '\0'; symlink(target, dst); }
    }
    return 0;
}

/* MKDIR P — create directory and parents (like mkdir -p) */
static int windir_mkdir_p(const char *path) {
    char tmp[WINDIR_MAX_PATH];
    snprintf(tmp, sizeof(tmp), "%s", path);
    int len = (int)strlen(tmp);
    if (len <= 0) return -1;
    if (tmp[len - 1] == '/') tmp[len - 1] = '\0';
    for (char *p = tmp + 1; *p; p++) {
        if (*p == '/') {
            *p = '\0';
            if (mkdir(tmp, 0755) != 0 && errno != EEXIST) return -1;
            *p = '/';
        }
    }
    if (mkdir(tmp, 0755) != 0 && errno != EEXIST) return -1;
    return 0;
}
int Windir_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.default_depth = WINDIR_DEFAULT_DEPTH;
    STATE.confirm_required = 1;
    STATE.follow_symlinks = 0;
    STATE.initialized = 1;
    return 1;
}

int Windir_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) Windir_Init();

    /* READ_STATE */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{1}[@DIRS_LISTED]{%d}[@DIRS_CREATED]{%d}"
            "[@DIRS_MOVED]{%d}[@DIRS_DELETED]{%d}[@BYTES_COPIED]{%ld}"
            "[@LAST_PATH]{%s}[@DEFAULT_DEPTH]{%d}[@CONFIRM_REQUIRED]{%d}"
            "[@FOLLOW_SYMLINKS]{%d}",
            STATE.dirs_listed, STATE.dirs_created, STATE.dirs_moved,
            STATE.dirs_deleted, STATE.bytes_copied,
            STATE.last_path[0] ? STATE.last_path : "(none)",
            STATE.default_depth, STATE.confirm_required, STATE.follow_symlinks);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* SET_CONFIG */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char depth[16] = {0}, confirm[16] = {0}, symlinks[16] = {0};
        BclParser_Extract(&parse, "DEFAULT_DEPTH", depth, sizeof(depth));
        BclParser_Extract(&parse, "CONFIRM_REQUIRED", confirm, sizeof(confirm));
        BclParser_Extract(&parse, "FOLLOW_SYMLINKS", symlinks, sizeof(symlinks));
        BclParser_Free(&parse);
        if (depth[0]) STATE.default_depth = atoi(depth);
        if (confirm[0]) STATE.confirm_required = atoi(confirm);
        if (symlinks[0]) STATE.follow_symlinks = atoi(symlinks);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }

    /* LIST — walk directory tree up to DEPTH levels */
    if (strcmp(cmd, "list") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[WINDIR_MAX_PATH] = {0}, depth_str[16] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Extract(&parse, "DEPTH", depth_str, sizeof(depth_str));
        BclParser_Free(&parse);
        if (!path[0]) return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        int depth = depth_str[0] ? atoi(depth_str) : STATE.default_depth;
        if (depth <= 0 || depth > WINDIR_MAX_DEPTH) depth = STATE.default_depth;
        g_out_offset = 0;
        g_dir_count = 0;
        g_max_depth = depth;
        windir_append("[@OK]{[@ROOT]{%s}[@DEPTH]{%d}[@TOTAL]{0}", path, depth);
        int flags = STATE.follow_symlinks ? 0 : FTW_PHYS;
        nftw(path, windir_list_cb, 512, flags);
        /* patch total */
        char total_str[32];
        snprintf(total_str, sizeof(total_str), "[@TOTAL]{%d}", g_dir_count);
        char *pos = strstr(g_out_buf, "[@TOTAL]{0}");
        if (pos) {
            int old_len = (int)strlen("[@TOTAL]{0}");
            int new_len = (int)strlen(total_str);
            memmove(pos + new_len, pos + old_len, strlen(pos + old_len) + 1);
            memcpy(pos, total_str, new_len);
        }
        g_out_offset = (int)strlen(g_out_buf);
        windir_append("}");
        snprintf(bcl_out, out_sz, "%s", g_out_buf);
        STATE.dirs_listed += g_dir_count;
        strncpy(STATE.last_path, path, sizeof(STATE.last_path) - 1);
        return 1;
    }

    /* CREATE — mkdir -p style */
    if (strcmp(cmd, "create") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[WINDIR_MAX_PATH] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Free(&parse);
        if (!path[0]) return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        if (windir_mkdir_p(path) != 0) {
            char err[256];
            snprintf(err, sizeof(err), "mkdir failed: %s", strerror(errno));
            return BclResult_Err(bcl_out, out_sz, 21, err);
        }
        STATE.dirs_created++;
        strncpy(STATE.last_path, path, sizeof(STATE.last_path) - 1);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{created}[@PATH]{set}");
    }

    /* MOVE — rename() with system("mv") fallback for cross-device */
    if (strcmp(cmd, "move") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char from[WINDIR_MAX_PATH] = {0}, to[WINDIR_MAX_PATH] = {0};
        BclParser_Extract(&parse, "FROM", from, sizeof(from));
        BclParser_Extract(&parse, "TO", to, sizeof(to));
        BclParser_Free(&parse);
        if (!from[0] || !to[0]) return BclResult_Err(bcl_out, out_sz, 20, "no FROM/TO in packet");
        if (rename(from, to) != 0) {
            char cmd_buf[WINDIR_MAX_PATH * 2 + 16];
            snprintf(cmd_buf, sizeof(cmd_buf), "mv \"%s\" \"%s\"", from, to);
            if (system(cmd_buf) != 0) {
                char err[256];
                snprintf(err, sizeof(err), "move failed: %s", strerror(errno));
                return BclResult_Err(bcl_out, out_sz, 22, err);
            }
        }
        STATE.dirs_moved++;
        strncpy(STATE.last_path, to, sizeof(STATE.last_path) - 1);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{moved}[@TO]{set}");
    }

    /* COPY — recursive copy via nftw + fopen/fwrite */
    if (strcmp(cmd, "copy") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char from[WINDIR_MAX_PATH] = {0}, to[WINDIR_MAX_PATH] = {0};
        BclParser_Extract(&parse, "FROM", from, sizeof(from));
        BclParser_Extract(&parse, "TO", to, sizeof(to));
        BclParser_Free(&parse);
        if (!from[0] || !to[0]) return BclResult_Err(bcl_out, out_sz, 20, "no FROM/TO in packet");
        struct stat st;
        if (stat(from, &st) != 0) return BclResult_Err(bcl_out, out_sz, 23, "source not found");
        windir_mkdir_p(to);
        long before = STATE.bytes_copied;
        snprintf(g_copy_src, sizeof(g_copy_src), "%s", from);
        g_copy_src_len = (int)strlen(g_copy_src);
        snprintf(g_copy_dest, sizeof(g_copy_dest), "%s", to);
        g_walk_error = 0;
        int flags = STATE.follow_symlinks ? 0 : FTW_PHYS;
        if (S_ISDIR(st.st_mode)) nftw(from, windir_copy_cb, 512, flags);
        else windir_copy_file(from, to);
        if (g_walk_error) {
            char err[256];
            snprintf(err, sizeof(err), "copy failed: %s", strerror(g_walk_error));
            return BclResult_Err(bcl_out, out_sz, 24, err);
        }
        long copied = STATE.bytes_copied - before;
        char body[256];
        snprintf(body, sizeof(body), "[@STATUS]{copied}[@BYTES]{%ld}", copied);
        strncpy(STATE.last_path, to, sizeof(STATE.last_path) - 1);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* DELETE — nftw + unlink + rmdir, requires CONFIRM=1 */
    if (strcmp(cmd, "delete") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[WINDIR_MAX_PATH] = {0}, confirm[16] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Extract(&parse, "CONFIRM", confirm, sizeof(confirm));
        BclParser_Free(&parse);
        if (!path[0]) return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        int confirmed = confirm[0] ? atoi(confirm) : 0;
        if (STATE.confirm_required && confirmed != 1)
            return BclResult_Err(bcl_out, out_sz, 25, "delete requires CONFIRM=1");
        struct stat st;
        if (stat(path, &st) != 0) return BclResult_Err(bcl_out, out_sz, 26, "path not found");
        g_walk_error = 0;
        if (S_ISDIR(st.st_mode)) {
            nftw(path, windir_delete_cb, 512, FTW_DEPTH | FTW_PHYS);
            if (g_walk_error == 0 && rmdir(path) != 0 && errno != ENOENT)
                g_walk_error = errno;
        } else {
            if (unlink(path) != 0) g_walk_error = errno;
        }
        if (g_walk_error) {
            char err[256];
            snprintf(err, sizeof(err), "delete failed: %s", strerror(g_walk_error));
            return BclResult_Err(bcl_out, out_sz, 27, err);
        }
        STATE.dirs_deleted++;
        strncpy(STATE.last_path, path, sizeof(STATE.last_path) - 1);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{deleted}");
    }

    /* SIZE — walk tree, sum file sizes, return total + file count */
    if (strcmp(cmd, "size") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char path[WINDIR_MAX_PATH] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Free(&parse);
        if (!path[0]) return BclResult_Err(bcl_out, out_sz, 20, "no PATH in packet");
        struct stat st;
        if (stat(path, &st) != 0) return BclResult_Err(bcl_out, out_sz, 28, "path not found");
        g_total_bytes = 0;
        g_file_count = 0;
        int flags = STATE.follow_symlinks ? 0 : FTW_PHYS;
        if (S_ISDIR(st.st_mode)) nftw(path, windir_size_cb, 512, flags);
        else { g_total_bytes = (long)st.st_size; g_file_count = 1; }
        char body[256];
        snprintf(body, sizeof(body), "[@STATUS]{ok}[@BYTES]{%ld}[@FILES]{%d}",
                 g_total_bytes, g_file_count);
        strncpy(STATE.last_path, path, sizeof(STATE.last_path) - 1);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    return BclResult_Err(bcl_out, out_sz, 40, "unknown command");
}
int Windir_Close(void) {
    STATE.initialized = 0;
    return 1;
}

const char * Windir_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "Windir: initialized=%d listed=%d created=%d moved=%d deleted=%d bytes=%ld",
        STATE.initialized, STATE.dirs_listed, STATE.dirs_created,
        STATE.dirs_moved, STATE.dirs_deleted, STATE.bytes_copied);
    return buf;
}
