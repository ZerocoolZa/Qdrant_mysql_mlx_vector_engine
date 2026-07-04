/*
 * bh_sync.c - Google Drive sync with Zstd compression
 *[@GHOST]
 *[@VBSTYLE]
 *[@FILEID] bh_sync.c
 *[@SUMMARY] Compress LMDB file with Zstd, copy to Google Drive, restore from Drive. Output via bh_report.
 *[@CLASS] BloodhoundSync
 *[@METHOD] SyncToDrive, RestoreFromDrive
 */

#include "bh_report.h"

static int file_exists(const char *path) {
    struct stat st;
    return stat(path, &st) == 0;
}

static long file_size(const char *path) {
    struct stat st;
    if (stat(path, &st) != 0) return -1;
    return st.st_size;
}

static int ensure_dir(const char *path) {
    struct stat st;
    if (stat(path, &st) == 0) return S_ISDIR(st.st_mode) ? 0 : -1;
    char parent[BH_MAX_PATH];
    snprintf(parent, sizeof(parent), "%s", path);
    char *slash = strrchr(parent, '/');
    if (slash) { *slash = '\0'; if (parent[0]) ensure_dir(parent); }
    return mkdir(path, 0755);
}

int bh_sync_to_drive(bh_db *db, const char *workspace) {
    char drive_path[BH_MAX_PATH];
    snprintf(drive_path, sizeof(drive_path), "%s", BH_DRIVE_PATH);
    ensure_dir(drive_path);

    long src_size = file_size(db->db_path);
    if (src_size < 0) { bh_report_error("cannot find DB file"); return -1; }

    FILE *f = fopen(db->db_path, "rb");
    if (!f) { bh_report_error("cannot open DB file"); return -1; }
    char *src_data = malloc(src_size);
    if (!src_data) { fclose(f); return -1; }
    fread(src_data, 1, src_size, f);
    fclose(f);

    size_t comp_bound = ZSTD_compressBound(src_size);
    char *comp_data = malloc(comp_bound);
    if (!comp_data) { free(src_data); return -1; }
    size_t comp_size = ZSTD_compress(comp_data, comp_bound, src_data, src_size, BH_ZSTD_LEVEL);
    if (ZSTD_isError(comp_size)) {
        bh_report_error("zstd compression failed");
        free(src_data); free(comp_data);
        return -1;
    }

    time_t now = time(NULL);
    char ts_file[BH_MAX_PATH];
    snprintf(ts_file, sizeof(ts_file), "%sbloodhound_memory_%s_%ld.mdb.zst",
             drive_path, workspace ? workspace : "default", now);
    FILE *out = fopen(ts_file, "wb");
    if (!out) { bh_report_error("cannot write to drive"); free(src_data); free(comp_data); return -1; }
    fwrite(comp_data, 1, comp_size, out);
    fclose(out);

    char latest_file[BH_MAX_PATH];
    snprintf(latest_file, sizeof(latest_file), "%sbloodhound_memory_latest.mdb.zst", drive_path);
    out = fopen(latest_file, "wb");
    if (out) { fwrite(comp_data, 1, comp_size, out); fclose(out); }

    free(src_data); free(comp_data);

    bh_report_sync(db->db_path, src_size, comp_size, ts_file, latest_file);
    return 0;
}

int bh_restore_from_drive(const char *drive_path) {
    char src_path[BH_MAX_PATH];
    if (drive_path && *drive_path) snprintf(src_path, sizeof(src_path), "%s", drive_path);
    else snprintf(src_path, sizeof(src_path), "%sbloodhound_memory_latest.mdb.zst", BH_DRIVE_PATH);

    if (!file_exists(src_path)) { bh_report_error("cannot find backup"); return -1; }

    long comp_size = file_size(src_path);
    FILE *f = fopen(src_path, "rb");
    if (!f) { bh_report_error("cannot open backup"); return -1; }
    char *comp_data = malloc(comp_size);
    if (!comp_data) { fclose(f); return -1; }
    fread(comp_data, 1, comp_size, f);
    fclose(f);

    size_t orig_size = ZSTD_getFrameContentSize(comp_data, comp_size);
    if (orig_size == ZSTD_CONTENTSIZE_ERROR || orig_size == ZSTD_CONTENTSIZE_UNKNOWN)
        orig_size = 100 * 1024 * 1024;
    char *orig_data = malloc(orig_size);
    if (!orig_data) { free(comp_data); return -1; }
    size_t decomp_size = ZSTD_decompress(orig_data, orig_size, comp_data, comp_size);
    if (ZSTD_isError(decomp_size)) {
        bh_report_error("zstd decompression failed");
        free(comp_data); free(orig_data);
        return -1;
    }

    char db_path[BH_MAX_PATH];
    bh_expand_tilde("~/.bloodhound/bloodhound.mdb", db_path, sizeof(db_path));
    char dir[BH_MAX_PATH];
    snprintf(dir, sizeof(dir), "%s", db_path);
    char *slash = strrchr(dir, '/');
    if (slash) { *slash = '\0'; ensure_dir(dir); }

    FILE *out = fopen(db_path, "wb");
    if (!out) { bh_report_error("cannot write to DB path"); free(comp_data); free(orig_data); return -1; }
    fwrite(orig_data, 1, decomp_size, out);
    fclose(out);

    free(comp_data); free(orig_data);

    bh_report_restore(src_path, comp_size, decomp_size, db_path);
    return 0;
}
