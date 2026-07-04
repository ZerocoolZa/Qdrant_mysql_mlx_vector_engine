/*
 * bh_scanner.c - Workspace scanner for LMDB Bloodhound
 *[@GHOST]
 *[@VBSTYLE]
 *[@FILEID] bh_scanner.c
 *[@SUMMARY] Walk directory tree, detect file changes, store full file content compressed. Watch mode for continuous sniffing.
 *[@CLASS] BloodhoundScanner
 *[@METHOD] ScanWorkspace, ShouldSkip, StoreFile, LogObservation, WatchWorkspace
 */

#include "bloodhound.h"
#include "bh_report.h"

/* ---- SIGINT handler for watch mode ---- */

static volatile sig_atomic_t bh_watch_running = 1;

static void bh_watch_sigint_handler(int sig) {
    (void)sig;
    bh_watch_running = 0;
}

/* ---- Skip rules ---- */

static int should_skip(const char *name) {
    if (name[0] == '.' && (strcmp(name, ".") == 0 || strcmp(name, "..") == 0)) return 1;
    if (strcmp(name, ".git") == 0) return 1;
    if (strcmp(name, "node_modules") == 0) return 1;
    if (strcmp(name, ".build") == 0) return 1;
    if (strcmp(name, "__pycache__") == 0) return 1;
    if (strcmp(name, ".Trash") == 0) return 1;
    if (strcmp(name, "build") == 0) return 1;
    if (strcmp(name, "dist") == 0) return 1;
    if (strcmp(name, ".DS_Store") == 0) return 1;
    if (strcmp(name, "target") == 0) return 1;
    if (strcmp(name, ".next") == 0) return 1;
    if (strcmp(name, ".venv") == 0) return 1;
    if (strcmp(name, "venv") == 0) return 1;
    if (strcmp(name, ".cache") == 0) return 1;
    return 0;
}

static int has_skip_ext(const char *path) {
    const char *ext = strrchr(path, '.');
    if (!ext) return 0;
    return (strcmp(ext, ".o") == 0 || strcmp(ext, ".pyc") == 0 ||
            strcmp(ext, ".class") == 0 || strcmp(ext, ".so") == 0 ||
            strcmp(ext, ".dylib") == 0 || strcmp(ext, ".exe") == 0 ||
            strcmp(ext, ".bin") == 0 || strcmp(ext, ".png") == 0 ||
            strcmp(ext, ".jpg") == 0 || strcmp(ext, ".jpeg") == 0 ||
            strcmp(ext, ".gif") == 0 || strcmp(ext, ".pdf") == 0 ||
            strcmp(ext, ".zip") == 0 || strcmp(ext, ".gz") == 0 ||
            strcmp(ext, ".tar") == 0 || strcmp(ext, ".db") == 0 ||
            strcmp(ext, ".mdb") == 0 || strcmp(ext, ".lock") == 0);
}

static void make_relative(const char *root, const char *full, char *out, size_t out_size) {
    size_t root_len = strlen(root);
    if (strncmp(full, root, root_len) == 0) {
        const char *rel = full + root_len;
        if (*rel == '/') rel++;
        snprintf(out, out_size, "%s", rel);
    } else {
        snprintf(out, out_size, "%s", full);
    }
}

/* ---- Directory walker ---- */

static void scan_dir(bh_db *db, const char *dir_path, const char *root_path,
                     const char *workspace, scan_result *result) {
    DIR *d = opendir(dir_path);
    if (!d) return;

    struct dirent *entry;
    while ((entry = readdir(d)) != NULL) {
        if (should_skip(entry->d_name)) continue;

        char full_path[BH_MAX_PATH * 2];
        snprintf(full_path, sizeof(full_path), "%s/%s", dir_path, entry->d_name);

        struct stat st;
        if (stat(full_path, &st) != 0) continue;

        if (S_ISDIR(st.st_mode)) {
            scan_dir(db, full_path, root_path, workspace, result);
            continue;
        }

        if (!S_ISREG(st.st_mode)) continue;
        if (has_skip_ext(full_path)) continue;
        if (st.st_size > 10 * 1024 * 1024) continue; /* skip files > 10MB */

        result->files++;

        const char *language = bh_detect_language(full_path);
        char rel_path[512];
        make_relative(root_path, full_path, rel_path, sizeof(rel_path));

        /* Compute file hash */
        char content_hash[33];
        bh_compute_file_hash(full_path, content_hash, sizeof(content_hash));

        /* Check if file already exists in DB */
        uint64_t file_id = 0;
        int exists = bh_db_find_file(db, full_path, &file_id);

        char action[16] = "new";
        if (exists == 0) {
            /* Check if content changed by comparing hash */
            file_record old_rec;
            char old_content[1];
            if (bh_db_get_file(db, file_id, &old_rec, old_content, 0) == 0) {
                if (strcmp(old_rec.content_hash, content_hash) == 0) {
                    strcpy(action, "seen");
                } else {
                    strcpy(action, "updated");
                    result->modified_files++;
                }
            }
        } else {
            file_id = bh_db_next_id(db, "next_file_id");
            result->new_files++;
        }

        /* Read full file content and store compressed */
        FILE *f = fopen(full_path, "rb");
        if (!f) continue;
        fseek(f, 0, SEEK_END);
        long fsize = ftell(f);
        fseek(f, 0, SEEK_SET);
        char *content = malloc(fsize + 1);
        if (!content) { fclose(f); continue; }
        fread(content, 1, fsize, f);
        content[fsize] = '\0';
        fclose(f);

        file_record rec;
        memset(&rec, 0, sizeof(rec));
        rec.file_id = file_id;
        strncpy(rec.file_path, full_path, BH_MAX_PATH - 1);
        strncpy(rec.relative_path, rel_path, 511);
        strncpy(rec.workspace, workspace, 255);
        strncpy(rec.language, language, 15);
        rec.size = (uint64_t)fsize;
        rec.mtime = (uint64_t)st.st_mtime;
        strncpy(rec.content_hash, content_hash, 32);
        rec.scan_time = time(NULL);

        bh_db_put_file(db, &rec, content, fsize);

        /* Extract scents only for new/modified files */
        if (strcmp(action, "new") == 0 || strcmp(action, "updated") == 0) {
            bh_nose_extract(db, full_path, rel_path, workspace, content_hash, language);
        }

        /* Log observation */
        observation obs;
        memset(&obs, 0, sizeof(obs));
        obs.obs_id = bh_db_next_id(db, "next_obs_id");
        obs.timestamp = time(NULL);
        strncpy(obs.workspace, workspace, 255);
        strncpy(obs.file_path, full_path, BH_MAX_PATH - 1);
        obs.scent_id = 0;
        strncpy(obs.action, action, 15);
        strncpy(obs.observer_version, "1.0", 7);
        bh_db_put_observation(db, &obs);

        free(content);
    }
    closedir(d);
}

/* ---- Workspace scan ---- */

int bh_scan_workspace(bh_db *db, const char *root_path, const char *workspace_name, scan_result *result) {
    memset(result, 0, sizeof(*result));

    /* Derive workspace name from path if not provided */
    char ws_name[256];
    if (workspace_name && *workspace_name) {
        strncpy(ws_name, workspace_name, 255);
    } else {
        const char *base = strrchr(root_path, '/');
        if (base) base++; else base = root_path;
        strncpy(ws_name, base, 255);
    }

    /* Store/update workspace record */
    workspace_rec ws;
    memset(&ws, 0, sizeof(ws));
    strncpy(ws.name, ws_name, 255);
    strncpy(ws.root_path, root_path, BH_MAX_PATH - 1);
    ws.last_scan = time(NULL);
    ws.updated_at = time(NULL);
    ws.created_at = time(NULL);
    bh_db_put_workspace(db, &ws);

    scan_dir(db, root_path, root_path, ws_name, result);

    /* Build cross-file import relationships after all files scanned */
    bh_nose_build_import_relationships(db, ws_name);

    /* Detect deleted files and add to result */
    uint32_t deleted_count = 0;
    bh_db_detect_deletions(db, ws_name, root_path, &deleted_count);
    result->deleted_files = deleted_count;

    /* Update workspace counts */
    ws.file_count = result->files;
    ws.scent_count = result->total_scents;
    bh_db_put_workspace(db, &ws);

    return 0;
}

/* ---- Watch mode (continuous sniffing) ---- */

int bh_watch_workspace(bh_db *db, const char *root_path, const char *workspace_name, int interval) {
    /* Install SIGINT handler for clean exit */
    bh_watch_running = 1;
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = bh_watch_sigint_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;
    sigaction(SIGINT, &sa, NULL);

    /* Derive workspace name from path if not provided */
    char ws_name[256];
    if (workspace_name && *workspace_name) {
        strncpy(ws_name, workspace_name, 255);
    } else {
        const char *base = strrchr(root_path, '/');
        if (base) base++; else base = root_path;
        strncpy(ws_name, base, 255);
    }

    /* Print watch start banner */
    bh_report_watch_start(root_path, interval);

    int cycle = 0;
    while (bh_watch_running) {
        cycle++;

        scan_result result;
        bh_scan_workspace(db, root_path, ws_name, &result);

        /* Detect deletions (already done in bh_scan_workspace, but report here) */
        bh_report_watch_cycle(cycle, &result);

        if (result.deleted_files > 0) {
            bh_report_deletions(result.deleted_files);
        }

        /* Sleep between cycles, checking running flag */
        for (int i = 0; i < interval && bh_watch_running; i++) {
            sleep(1);
        }
    }

    /* Restore default SIGINT handler */
    signal(SIGINT, SIG_DFL);

    return 0;
}
