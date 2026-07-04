/*
 * ghostctl.c — fast native CLI for ghost maintenance
 * Uses POSIX syscalls (nftw, unlink, rmdir) — no system() for file ops.
 * Compile: cc -O2 -o ghostctl ghostctl.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <ftw.h>
#include <sys/stat.h>
#include <errno.h>

/* ── counters ── */
static long zero_files = 0;
static long empty_dirs = 0;
static long wal_files = 0;
static long shm_files = 0;
static long pyc_files = 0;
static long pycache_dirs = 0;

/* ── flags ── */
static int do_clean = 0;      /* clean mode: all file types */
static int do_pycache = 0;    /* pi mode: pyc/pycache only */

/* ── helpers ── */
static int is_ext(const char *name, const char *ext) {
    int nlen = (int)strlen(name);
    int elen = (int)strlen(ext);
    return nlen >= elen && strcmp(name + nlen - elen, ext) == 0;
}

/* get basename of path */
static const char *ghost_basename(const char *path) {
    const char *p = strrchr(path, '/');
    return p ? p + 1 : path;
}

/* ── nftw callback: single pass, handles everything ── */
static int walker(const char *fpath, const struct stat *sb,
                  int typeflag, struct FTW *ftwbuf) {
    if (typeflag == FTW_F) {
        /* 0-byte files — clean mode only */
        if (do_clean && sb->st_size == 0) {
            if (unlink(fpath) == 0) zero_files++;
            return 0;
        }
        /* .wal files — clean mode only */
        if (do_clean && is_ext(fpath, ".wal")) {
            if (unlink(fpath) == 0) wal_files++;
            return 0;
        }
        /* .shm files — clean mode only */
        if (do_clean && is_ext(fpath, ".shm")) {
            if (unlink(fpath) == 0) shm_files++;
            return 0;
        }
        /* .pyc files — both clean and pycache mode */
        if ((do_clean || do_pycache) && is_ext(fpath, ".pyc")) {
            if (unlink(fpath) == 0) pyc_files++;
            return 0;
        }
    }
    else if (typeflag == FTW_DP) {
        const char *base = ghost_basename(fpath);
        /* __pycache__ dirs — both modes, post-order (contents already gone) */
        if ((do_clean || do_pycache) && strcmp(base, "__pycache__") == 0) {
            if (rmdir(fpath) == 0) pycache_dirs++;
            return 0;
        }
        /* empty dirs — clean mode only, just try rmdir */
        if (do_clean && ftwbuf->level > 0) {
            if (rmdir(fpath) == 0) empty_dirs++;
        }
    }
    return 0;
}

/* ── commands ── */

static void cmd_clean(int argc, char **argv) {
    const char *root = (argc > 2) ? argv[2] : "/Users";
    struct stat st;
    if (stat(root, &st) != 0 || !S_ISDIR(st.st_mode)) {
        fprintf(stderr, "ERROR: %s is not a directory\n", root);
        return;
    }

    do_clean = 1;
    do_pycache = 0;
    zero_files = empty_dirs = wal_files = shm_files = 0;
    pyc_files = pycache_dirs = 0;

    printf(">> GHOST CLEAN: scanning %s <<\n", root);

    /* single nftw pass — depth-first, post-order for dir removal */
    nftw(root, walker, 512, FTW_DEPTH | FTW_PHYS);

    printf("-- 0-byte files --\n   removed: %ld\n", zero_files);
    printf("-- empty dirs --\n   removed: %ld\n", empty_dirs);
    printf("-- SQLite leftovers --\n   removed: %ld .wal, %ld .shm\n", wal_files, shm_files);
    printf("-- Python cache --\n   removed: %ld .pyc, %ld __pycache__ dirs\n", pyc_files, pycache_dirs);

    /* MySQL — only part that needs system() */
    printf("-- MySQL binlogs --\n");
    int rc = system("mysql -u root --socket=/tmp/mysql.sock -e \"PURGE BINARY LOGS BEFORE NOW();\" 2>/dev/null");
    /* TODO: replace with fork + execlp for zero-system() design */
    if (rc == 0) {
        printf("   binlogs purged\n");
    } else {
        printf("   mysql not available, skipped\n");
    }

    /* truncate error log */
    const char *err_log = "/opt/homebrew/var/mysql/nwm.err";
    FILE *ef = fopen(err_log, "w");
    if (ef) {
        fclose(ef);
        printf("   truncated: nwm.err\n");
    }

    printf(">> DONE <<\n");
}

static void cmd_pi(int argc, char **argv) {
    if (argc < 3) {
        /* ghost maintenance */
        printf(">> GHOST MAINTENANCE <<\n");

        printf("-- upgrading pip --\n");
        system("python3 -m pip install --upgrade pip");

        printf("-- purging pip cache --\n");
        system("python3 -m pip cache purge");

        printf("-- nuking pycache --\n");
        do_clean = 0;
        do_pycache = 1;
        pyc_files = pycache_dirs = 0;
        nftw(".", walker, 512, FTW_DEPTH | FTW_PHYS);
        printf("   removed: %ld .pyc, %ld __pycache__ dirs\n", pyc_files, pycache_dirs);

        printf("-- outdated packages --\n");
        system("python3 -m pip list --outdated");

        printf(">> DONE <<\n");
    } else {
        /* pip install — build command safely */
        size_t total = 64;
        for (int i = 2; i < argc; i++) {
            size_t alen = strlen(argv[i]);
            /* worst case: every char is a quote → 4x expansion + 4 for wrapping */
            total += alen * 5 + 4;
        }

        char *cmd = calloc(total, 1);
        if (!cmd) { fprintf(stderr, "OOM\n"); return; }

        strcat(cmd, "python3 -m pip install");
        for (int i = 2; i < argc; i++) {
            strcat(cmd, " '");
            /* escape single quotes: ' becomes '\'' */
            for (const char *p = argv[i]; *p; p++) {
                if (*p == '\'') {
                    strcat(cmd, "'\\\''");
                } else {
                    int pos = (int)strlen(cmd);
                    cmd[pos] = *p;
                    cmd[pos + 1] = '\0';
                }
            }
            strcat(cmd, "'");
        }
        system(cmd);
        free(cmd);
    }
}

static void cmd_py(int argc, char **argv) {
    if (argc < 3) {
        printf("Usage: ghostctl py <file.py> [args...]\n");
        return;
    }
    /* exec python3 directly — no system() */
    argv[1] = "python3";
    execvp("python3", &argv[1]);
    perror("execvp");
    exit(1);
}

static void usage(void) {
    printf("ghostctl — fast ghost maintenance\n\n");
    printf("commands:\n");
    printf("  clean [path]    remove 0-byte files, empty dirs, .wal/.shm, pycache, purge MySQL\n");
    printf("  pi [packages]   no args = maintenance; with args = pip install\n");
    printf("  py <file>       run python3 file (exec, no shell)\n");
    printf("  help            show this\n");
}

int main(int argc, char **argv) {
    if (argc < 2) {
        usage();
        return 0;
    }

    if (strcmp(argv[1], "clean") == 0) {
        cmd_clean(argc, argv);
    }
    else if (strcmp(argv[1], "pi") == 0) {
        cmd_pi(argc, argv);
    }
    else if (strcmp(argv[1], "py") == 0) {
        cmd_py(argc, argv);
    }
    else if (strcmp(argv[1], "help") == 0 || strcmp(argv[1], "--help") == 0) {
        usage();
    }
    else {
        fprintf(stderr, "unknown command: %s\n", argv[1]);
        usage();
        return 1;
    }

    return 0;
}
