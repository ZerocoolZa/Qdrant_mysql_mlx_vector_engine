/*
 * bh_db.c - LMDB + Zstd database layer
 *[@GHOST]
 *[@VBSTYLE]
 *[@FILEID] bh_db.c
 *[@SUMMARY] Open LMDB env, serialize/deserialize scent packets, Zstd compress, cursor queries
 *[@CLASS] BloodhoundDB
 *[@METHOD] Open, PutScent, GetScent, PutFile, GetFile, IterScents, IterRels
 */

#include "bloodhound.h"

/* ---- Little-endian helpers ---- */

void bh_put_le64(uint8_t *buf, uint64_t val) {
    for (int i = 0; i < 8; i++) buf[i] = (val >> (i * 8)) & 0xFF;
}

uint64_t bh_get_le64(const uint8_t *buf) {
    uint64_t v = 0;
    for (int i = 0; i < 8; i++) v |= ((uint64_t)buf[i]) << (i * 8);
    return v;
}

void bh_put_le32(uint8_t *buf, uint32_t val) {
    for (int i = 0; i < 4; i++) buf[i] = (val >> (i * 8)) & 0xFF;
}

uint32_t bh_get_le32(const uint8_t *buf) {
    uint32_t v = 0;
    for (int i = 0; i < 4; i++) v |= ((uint32_t)buf[i]) << (i * 8);
    return v;
}

void bh_put_le_double(uint8_t *buf, double val) {
    uint64_t *p = (uint64_t *)&val;
    bh_put_le64(buf, *p);
}

double bh_get_le_double(const uint8_t *buf) {
    uint64_t raw = bh_get_le64(buf);
    double *p = (double *)&raw;
    return *p;
}

/* ---- Tilde expansion ---- */

void bh_expand_tilde(const char *in, char *out, size_t out_size) {
    if (!in || !out || out_size == 0) return;
    if (in[0] == '~') {
        const char *home = getenv("HOME");
        if (!home) home = "/tmp";
        if (in[1] == '\0') {
            snprintf(out, out_size, "%s", home);
        } else if (in[1] == '/') {
            snprintf(out, out_size, "%s%s", home, in + 1);
        } else {
            snprintf(out, out_size, "%s", in);
        }
    } else {
        snprintf(out, out_size, "%s", in);
    }
}

/* ---- SHA256 ---- */

void bh_sha256_string(const char *input, size_t len, char *out, size_t out_size) {
#ifdef __APPLE__
    CC_SHA256_CTX ctx;
    CC_SHA256_Init(&ctx);
    CC_SHA256_Update(&ctx, input, (CC_LONG)len);
    unsigned char digest[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256_Final(digest, &ctx);
    snprintf(out, out_size,
        "%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x"
        "%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x",
        digest[0],digest[1],digest[2],digest[3],digest[4],digest[5],digest[6],digest[7],
        digest[8],digest[9],digest[10],digest[11],digest[12],digest[13],digest[14],digest[15],
        digest[16],digest[17],digest[18],digest[19],digest[20],digest[21],digest[22],digest[23],
        digest[24],digest[25],digest[26],digest[27],digest[28],digest[29],digest[30],digest[31]);
#else
    /* FNV-1a fallback */
    uint64_t h = 1469598103934665603ULL;
    for (size_t i = 0; i < len; i++) {
        h ^= (unsigned char)input[i];
        h *= 1099511628211ULL;
    }
    snprintf(out, out_size, "%016llx0000000000000000", (unsigned long long)h);
#endif
}

/* ---- Zstd helpers ---- */

static size_t bh_zstd_compress(const char *src, size_t src_size, char *dst, size_t dst_capacity) {
    return ZSTD_compress(dst, dst_capacity, src, src_size, BH_ZSTD_LEVEL);
}

static size_t bh_zstd_decompress(const char *src, size_t src_size, char *dst, size_t dst_capacity) {
    return ZSTD_decompress(dst, dst_capacity, src, src_size);
}

/* ---- Serialization ---- */

/* Scent packet serialization: fixed fields + variable context, then Zstd compress */
static size_t serialize_scent(scent_packet *pkt,
                              const char *ctx_before, const char *ctx_match, const char *ctx_after,
                              char *out, size_t out_size) {
    size_t off = 0;
    bh_put_le64((uint8_t*)(out + off), pkt->scent_id); off += 8;
    memcpy(out + off, pkt->fingerprint, 33); off += 33;
    memcpy(out + off, pkt->type, 32); off += 32;
    memcpy(out + off, pkt->language, 16); off += 16;
    memcpy(out + off, pkt->workspace, 256); off += 256;
    memcpy(out + off, pkt->source_file, BH_MAX_PATH); off += BH_MAX_PATH;
    memcpy(out + off, pkt->relative_path, 512); off += 512;
    bh_put_le32((uint8_t*)(out + off), pkt->line); off += 4;
    bh_put_le32((uint8_t*)(out + off), pkt->column); off += 4;
    bh_put_le64((uint8_t*)(out + off), pkt->byte_offset); off += 8;
    memcpy(out + off, pkt->content_hash, 33); off += 33;
    bh_put_le_double((uint8_t*)(out + off), pkt->confidence); off += 8;
    bh_put_le64((uint8_t*)(out + off), pkt->created_at); off += 8;
    bh_put_le64((uint8_t*)(out + off), pkt->updated_at); off += 8;
    bh_put_le32((uint8_t*)(out + off), pkt->seen_count); off += 4;

    uint32_t blen = ctx_before ? strlen(ctx_before) : 0;
    uint32_t mlen = ctx_match ? strlen(ctx_match) : 0;
    uint32_t alen = ctx_after ? strlen(ctx_after) : 0;
    bh_put_le32((uint8_t*)(out + off), blen); off += 4;
    bh_put_le32((uint8_t*)(out + off), mlen); off += 4;
    bh_put_le32((uint8_t*)(out + off), alen); off += 4;

    if (blen > 0) { memcpy(out + off, ctx_before, blen); off += blen; }
    if (mlen > 0) { memcpy(out + off, ctx_match, mlen); off += mlen; }
    if (alen > 0) { memcpy(out + off, ctx_after, alen); off += alen; }

    return off;
}

static int deserialize_scent(const char *data, size_t data_size,
                             scent_packet *pkt,
                             char *ctx_before, size_t before_sz,
                             char *ctx_match, size_t match_sz,
                             char *ctx_after, size_t after_sz) {
    size_t off = 0;
    pkt->scent_id = bh_get_le64((const uint8_t*)(data + off)); off += 8;
    memcpy(pkt->fingerprint, data + off, 33); off += 33;
    memcpy(pkt->type, data + off, 32); off += 32;
    memcpy(pkt->language, data + off, 16); off += 16;
    memcpy(pkt->workspace, data + off, 256); off += 256;
    memcpy(pkt->source_file, data + off, BH_MAX_PATH); off += BH_MAX_PATH;
    memcpy(pkt->relative_path, data + off, 512); off += 512;
    pkt->line = bh_get_le32((const uint8_t*)(data + off)); off += 4;
    pkt->column = bh_get_le32((const uint8_t*)(data + off)); off += 4;
    pkt->byte_offset = bh_get_le64((const uint8_t*)(data + off)); off += 8;
    memcpy(pkt->content_hash, data + off, 33); off += 33;
    pkt->confidence = bh_get_le_double((const uint8_t*)(data + off)); off += 8;
    pkt->created_at = bh_get_le64((const uint8_t*)(data + off)); off += 8;
    pkt->updated_at = bh_get_le64((const uint8_t*)(data + off)); off += 8;
    pkt->seen_count = bh_get_le32((const uint8_t*)(data + off)); off += 4;

    pkt->ctx_before_len = bh_get_le32((const uint8_t*)(data + off)); off += 4;
    pkt->ctx_match_len = bh_get_le32((const uint8_t*)(data + off)); off += 4;
    pkt->ctx_after_len = bh_get_le32((const uint8_t*)(data + off)); off += 4;

    if (ctx_before && before_sz > 0) {
        size_t copylen = pkt->ctx_before_len < before_sz - 1 ? pkt->ctx_before_len : before_sz - 1;
        memcpy(ctx_before, data + off, copylen); ctx_before[copylen] = '\0';
    }
    off += pkt->ctx_before_len;
    if (ctx_match && match_sz > 0) {
        size_t copylen = pkt->ctx_match_len < match_sz - 1 ? pkt->ctx_match_len : match_sz - 1;
        memcpy(ctx_match, data + off, copylen); ctx_match[copylen] = '\0';
    }
    off += pkt->ctx_match_len;
    if (ctx_after && after_sz > 0) {
        size_t copylen = pkt->ctx_after_len < after_sz - 1 ? pkt->ctx_after_len : after_sz - 1;
        memcpy(ctx_after, data + off, copylen); ctx_after[copylen] = '\0';
    }
    return 0;
}

/* File record serialization */
static size_t serialize_file(file_record *rec, const char *content, size_t content_len, char *out, size_t out_size) {
    size_t off = 0;
    bh_put_le64((uint8_t*)(out + off), rec->file_id); off += 8;
    memcpy(out + off, rec->file_path, BH_MAX_PATH); off += BH_MAX_PATH;
    memcpy(out + off, rec->relative_path, 512); off += 512;
    memcpy(out + off, rec->workspace, 256); off += 256;
    memcpy(out + off, rec->language, 16); off += 16;
    bh_put_le64((uint8_t*)(out + off), rec->size); off += 8;
    bh_put_le64((uint8_t*)(out + off), rec->mtime); off += 8;
    memcpy(out + off, rec->content_hash, 33); off += 33;
    bh_put_le64((uint8_t*)(out + off), rec->scan_time); off += 8;
    /* Compress content inline */
    size_t comp_bound = ZSTD_compressBound(content_len);
    if (off + comp_bound > out_size) comp_bound = out_size - off;
    size_t comp_size = ZSTD_compress(out + off + 4, comp_bound, content, content_len, BH_ZSTD_LEVEL);
    bh_put_le32((uint8_t*)(out + off), (uint32_t)comp_size); off += 4;
    off += comp_size;
    rec->compressed_size = (uint32_t)comp_size;
    return off;
}

static int deserialize_file(const char *data, size_t data_size, file_record *rec, char *content, size_t content_sz) {
    size_t off = 0;
    rec->file_id = bh_get_le64((const uint8_t*)(data + off)); off += 8;
    memcpy(rec->file_path, data + off, BH_MAX_PATH); off += BH_MAX_PATH;
    memcpy(rec->relative_path, data + off, 512); off += 512;
    memcpy(rec->workspace, data + off, 256); off += 256;
    memcpy(rec->language, data + off, 16); off += 16;
    rec->size = bh_get_le64((const uint8_t*)(data + off)); off += 8;
    rec->mtime = bh_get_le64((const uint8_t*)(data + off)); off += 8;
    memcpy(rec->content_hash, data + off, 33); off += 33;
    rec->scan_time = bh_get_le64((const uint8_t*)(data + off)); off += 8;
    rec->compressed_size = bh_get_le32((const uint8_t*)(data + off)); off += 4;
    if (content && content_sz > 0) {
        size_t decompressed = ZSTD_decompress(content, content_sz, data + off, rec->compressed_size);
        if (!ZSTD_isError(decompressed)) {
            content[decompressed] = '\0';
        } else {
            content[0] = '\0';
        }
    }
    return 0;
}

/* ---- DB Index helpers ---- */

enum { DBI_SCENTS, DBI_FP_INDEX, DBI_FILE_SCENTS, DBI_TYPE_INDEX,
       DBI_FILES, DBI_FILE_PATHS, DBI_OBSERVATIONS, DBI_OBS_RECENT,
       DBI_RELS, DBI_REL_FROM, DBI_REL_TO, DBI_TRAILS, DBI_TRAIL_STEPS,
       DBI_WORKSPACES, DBI_LEARNING, DBI_LEARN_SCENT, DBI_META, DBI_COUNT };

static const char *dbi_names[] = {
    BH_DB_SCENTS, BH_DB_FP_INDEX, BH_DB_FILE_SCENTS, BH_DB_TYPE_INDEX,
    BH_DB_FILES, BH_DB_FILE_PATHS, BH_DB_OBSERVATIONS, BH_DB_OBS_RECENT,
    BH_DB_RELS, BH_DB_REL_FROM, BH_DB_REL_TO, BH_DB_TRAILS, BH_DB_TRAIL_STEPS,
    BH_DB_WORKSPACES, BH_DB_LEARNING, BH_DB_LEARN_SCENT, BH_DB_META
};

/* ---- Open / Close ---- */

int bh_db_open(bh_db *db, const char *path) {
    memset(db, 0, sizeof(*db));
    char expanded[BH_MAX_PATH];
    bh_expand_tilde(path, expanded, sizeof(expanded));

    /* Ensure directory exists */
    char dir[BH_MAX_PATH];
    snprintf(dir, sizeof(dir), "%s", expanded);
    /* Strip filename to get dir */
    char *slash = strrchr(dir, '/');
    if (slash) {
        *slash = '\0';
        mkdir(dir, 0755);
    }

    strncpy(db->db_path, expanded, sizeof(db->db_path) - 1);

    int rc = mdb_env_create(&db->env);
    if (rc) { fprintf(stderr, "mdb_env_create: %s\n", mdb_strerror(rc)); return -1; }

    rc = mdb_env_set_maxdbs(db->env, BH_LMDB_MAX_DBS);
    if (rc) { fprintf(stderr, "mdb_env_set_maxdbs: %s\n", mdb_strerror(rc)); return -1; }

    rc = mdb_env_set_mapsize(db->env, BH_LMDB_MAP_SIZE);
    if (rc) { fprintf(stderr, "mdb_env_set_mapsize: %s\n", mdb_strerror(rc)); return -1; }

    rc = mdb_env_open(db->env, expanded, MDB_NOSUBDIR, 0644);
    if (rc) { fprintf(stderr, "mdb_env_open: %s\n", mdb_strerror(rc)); return -1; }

    /* Open all sub-DBs in one write txn */
    MDB_txn *txn;
    rc = mdb_txn_begin(db->env, NULL, 0, &txn);
    if (rc) { fprintf(stderr, "mdb_txn_begin: %s\n", mdb_strerror(rc)); return -1; }

    for (int i = 0; i < DBI_COUNT; i++) {
        unsigned int flags = MDB_CREATE;
        if (i == DBI_OBS_RECENT || i == DBI_FILE_SCENTS || i == DBI_TYPE_INDEX ||
            i == DBI_REL_FROM || i == DBI_REL_TO || i == DBI_TRAIL_STEPS ||
            i == DBI_LEARN_SCENT) {
            flags |= MDB_DUPSORT;
        }
        rc = mdb_dbi_open(txn, dbi_names[i], flags, &db->dbs[i]);
        if (rc) { fprintf(stderr, "mdb_dbi_open %s: %s\n", dbi_names[i], mdb_strerror(rc)); mdb_txn_abort(txn); return -1; }
    }

    mdb_txn_commit(txn);
    return 0;
}

void bh_db_close(bh_db *db) {
    if (db->env) {
        mdb_env_close(db->env);
        db->env = NULL;
    }
}

/* ---- Counter (meta DB) ---- */

uint64_t bh_db_next_id(bh_db *db, const char *counter_name) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, 0, &txn)) return 0;

    MDB_val key = { .mv_size = strlen(counter_name), .mv_data = (void*)counter_name };
    MDB_val val;
    uint64_t next = 1;

    int rc = mdb_get(txn, db->dbs[DBI_META], &key, &val);
    if (rc == 0 && val.mv_size >= 8) {
        next = bh_get_le64(val.mv_data) + 1;
    }

    char buf[8];
    bh_put_le64((uint8_t*)buf, next);
    val.mv_size = 8;
    val.mv_data = buf;
    mdb_put(txn, db->dbs[DBI_META], &key, &val, 0);

    mdb_txn_commit(txn);
    return next;
}

/* ---- Scent Put/Get ---- */

int bh_db_put_scent(bh_db *db, scent_packet *pkt,
                    const char *ctx_before, const char *ctx_match, const char *ctx_after) {
    /* Serialize + compress */
    size_t raw_size = sizeof(scent_packet) + 12 +
                      (ctx_before ? strlen(ctx_before) : 0) +
                      (ctx_match ? strlen(ctx_match) : 0) +
                      (ctx_after ? strlen(ctx_after) : 0);
    char *raw = malloc(raw_size + 1024);
    if (!raw) return -1;
    size_t actual = serialize_scent(pkt, ctx_before, ctx_match, ctx_after, raw, raw_size + 1024);

    size_t comp_bound = ZSTD_compressBound(actual);
    char *comp = malloc(comp_bound);
    if (!comp) { free(raw); return -1; }
    size_t comp_size = bh_zstd_compress(raw, actual, comp, comp_bound);
    if (ZSTD_isError(comp_size)) { free(raw); free(comp); return -1; }

    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, 0, &txn)) { free(raw); free(comp); return -1; }

    /* Key: scent_id as LE64 */
    uint8_t key_buf[8];
    bh_put_le64(key_buf, pkt->scent_id);
    MDB_val key = { .mv_size = 8, .mv_data = key_buf };
    MDB_val val = { .mv_size = comp_size, .mv_data = comp };
    int rc = mdb_put(txn, db->dbs[DBI_SCENTS], &key, &val, 0);
    if (rc) { fprintf(stderr, "put_scent: %s\n", mdb_strerror(rc)); mdb_txn_abort(txn); free(raw); free(comp); return -1; }

    /* fp_index: fingerprint -> scent_id */
    MDB_val fp_key = { .mv_size = 32, .mv_data = pkt->fingerprint };
    MDB_val fp_val = { .mv_size = 8, .mv_data = key_buf };
    mdb_put(txn, db->dbs[DBI_FP_INDEX], &fp_key, &fp_val, 0);

    /* file_scents: file_path\0 + scent_id -> empty (for prefix scan) */
    char fkey[BH_MAX_PATH + 8];
    size_t plen = strlen(pkt->source_file);
    memcpy(fkey, pkt->source_file, plen);
    fkey[plen] = '\0';
    memcpy(fkey + plen + 1, key_buf, 8);
    MDB_val fs_key = { .mv_size = plen + 1 + 8, .mv_data = fkey };
    MDB_val fs_val = { .mv_size = 0, .mv_data = NULL };
    mdb_put(txn, db->dbs[DBI_FILE_SCENTS], &fs_key, &fs_val, 0);

    /* type_index: type\0 + scent_id -> empty */
    char tkey[32 + 8];
    size_t tlen = strlen(pkt->type);
    memcpy(tkey, pkt->type, tlen);
    tkey[tlen] = '\0';
    memcpy(tkey + tlen + 1, key_buf, 8);
    MDB_val ti_key = { .mv_size = tlen + 1 + 8, .mv_data = tkey };
    MDB_val ti_val = { .mv_size = 0, .mv_data = NULL };
    mdb_put(txn, db->dbs[DBI_TYPE_INDEX], &ti_key, &ti_val, 0);

    mdb_txn_commit(txn);
    free(raw);
    free(comp);
    return 0;
}

int bh_db_get_scent(bh_db *db, uint64_t scent_id, scent_packet *pkt,
                    char *ctx_before, size_t before_sz,
                    char *ctx_match, size_t match_sz,
                    char *ctx_after, size_t after_sz) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;

    uint8_t key_buf[8];
    bh_put_le64(key_buf, scent_id);
    MDB_val key = { .mv_size = 8, .mv_data = key_buf };
    MDB_val val;

    int rc = mdb_get(txn, db->dbs[DBI_SCENTS], &key, &val);
    if (rc) { mdb_txn_abort(txn); return -1; }

    /* Decompress */
    size_t orig_size = ZSTD_getFrameContentSize(val.mv_data, val.mv_size);
    if (orig_size == ZSTD_CONTENTSIZE_ERROR || orig_size == ZSTD_CONTENTSIZE_UNKNOWN) {
        orig_size = sizeof(scent_packet) + 12 + BH_MAX_LINE * 3;
    }
    char *raw = malloc(orig_size);
    if (!raw) { mdb_txn_abort(txn); return -1; }
    size_t decomp = bh_zstd_decompress(val.mv_data, val.mv_size, raw, orig_size);
    if (ZSTD_isError(decomp)) { free(raw); mdb_txn_abort(txn); return -1; }

    deserialize_scent(raw, decomp, pkt, ctx_before, before_sz, ctx_match, match_sz, ctx_after, after_sz);

    free(raw);
    mdb_txn_abort(txn); /* read-only */
    return 0;
}

int bh_db_find_by_fp(bh_db *db, const char *fingerprint, uint64_t *scent_id) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;

    MDB_val key = { .mv_size = 32, .mv_data = (void*)fingerprint };
    MDB_val val;
    int rc = mdb_get(txn, db->dbs[DBI_FP_INDEX], &key, &val);
    if (rc == 0 && val.mv_size >= 8) {
        *scent_id = bh_get_le64(val.mv_data);
        mdb_txn_abort(txn);
        return 0;
    }
    mdb_txn_abort(txn);
    return -1;
}

int bh_db_update_scent_confidence(bh_db *db, uint64_t scent_id, double conf, uint32_t seen) {
    scent_packet pkt;
    char ctx_before[BH_MAX_LINE], ctx_match[BH_MAX_LINE], ctx_after[BH_MAX_LINE];
    if (bh_db_get_scent(db, scent_id, &pkt, ctx_before, sizeof(ctx_before),
                        ctx_match, sizeof(ctx_match), ctx_after, sizeof(ctx_after))) return -1;
    pkt.confidence = conf;
    pkt.seen_count = seen;
    pkt.updated_at = time(NULL);
    return bh_db_put_scent(db, &pkt, ctx_before, ctx_match, ctx_after);
}

/* ---- File Put/Get ---- */

int bh_db_put_file(bh_db *db, file_record *rec, const char *content, size_t content_len) {
    size_t raw_size = 8 + BH_MAX_PATH + 512 + 256 + 16 + 8 + 8 + 33 + 8 + 4 + ZSTD_compressBound(content_len);
    char *raw = malloc(raw_size);
    if (!raw) return -1;
    size_t actual = serialize_file(rec, content, content_len, raw, raw_size);

    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, 0, &txn)) { free(raw); return -1; }

    uint8_t key_buf[8];
    bh_put_le64(key_buf, rec->file_id);
    MDB_val key = { .mv_size = 8, .mv_data = key_buf };
    MDB_val val = { .mv_size = actual, .mv_data = raw };
    int rc = mdb_put(txn, db->dbs[DBI_FILES], &key, &val, 0);
    if (rc) { mdb_txn_abort(txn); free(raw); return -1; }

    /* file_paths: path -> file_id */
    MDB_val fp_key = { .mv_size = strlen(rec->file_path), .mv_data = rec->file_path };
    MDB_val fp_val = { .mv_size = 8, .mv_data = key_buf };
    mdb_put(txn, db->dbs[DBI_FILE_PATHS], &fp_key, &fp_val, 0);

    mdb_txn_commit(txn);
    free(raw);
    return 0;
}

int bh_db_get_file(bh_db *db, uint64_t file_id, file_record *rec, char *content, size_t content_sz) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;

    uint8_t key_buf[8];
    bh_put_le64(key_buf, file_id);
    MDB_val key = { .mv_size = 8, .mv_data = key_buf };
    MDB_val val;

    int rc = mdb_get(txn, db->dbs[DBI_FILES], &key, &val);
    if (rc) { mdb_txn_abort(txn); return -1; }

    deserialize_file(val.mv_data, val.mv_size, rec, content, content_sz);
    mdb_txn_abort(txn);
    return 0;
}

int bh_db_find_file(bh_db *db, const char *file_path, uint64_t *file_id) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;

    MDB_val key = { .mv_size = strlen(file_path), .mv_data = (void*)file_path };
    MDB_val val;
    int rc = mdb_get(txn, db->dbs[DBI_FILE_PATHS], &key, &val);
    if (rc == 0 && val.mv_size >= 8) {
        *file_id = bh_get_le64(val.mv_data);
        mdb_txn_abort(txn);
        return 0;
    }
    mdb_txn_abort(txn);
    return -1;
}

/* ---- Observation ---- */

int bh_db_put_observation(bh_db *db, observation *obs) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, 0, &txn)) return -1;

    char buf[8 + 8 + 256 + BH_MAX_PATH + 8 + 16 + 8];
    size_t off = 0;
    bh_put_le64((uint8_t*)(buf + off), obs->obs_id); off += 8;
    bh_put_le64((uint8_t*)(buf + off), obs->timestamp); off += 8;
    memcpy(buf + off, obs->workspace, 256); off += 256;
    memcpy(buf + off, obs->file_path, BH_MAX_PATH); off += BH_MAX_PATH;
    bh_put_le64((uint8_t*)(buf + off), obs->scent_id); off += 8;
    memcpy(buf + off, obs->action, 16); off += 16;
    memcpy(buf + off, obs->observer_version, 8); off += 8;

    uint8_t key_buf[8];
    bh_put_le64(key_buf, obs->obs_id);
    MDB_val key = { .mv_size = 8, .mv_data = key_buf };
    MDB_val val = { .mv_size = off, .mv_data = buf };
    mdb_put(txn, db->dbs[DBI_OBSERVATIONS], &key, &val, 0);

    /* obs_recent: timestamp + obs_id -> empty (for reverse scan) */
    char rkey[16];
    bh_put_le64((uint8_t*)rkey, obs->timestamp);
    bh_put_le64((uint8_t*)(rkey + 8), obs->obs_id);
    MDB_val rkey_val = { .mv_size = 16, .mv_data = rkey };
    MDB_val rval = { .mv_size = 0, .mv_data = NULL };
    mdb_put(txn, db->dbs[DBI_OBS_RECENT], &rkey_val, &rval, 0);

    mdb_txn_commit(txn);
    return 0;
}

/* ---- Relationship ---- */

int bh_db_put_relationship(bh_db *db, relationship *rel) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, 0, &txn)) return -1;

    char val_buf[8 + 32 + 8 + 256 + 8];
    size_t off = 0;
    bh_put_le64((uint8_t*)(val_buf + off), rel->from_scent); off += 8;
    memcpy(val_buf + off, rel->rel_type, 32); off += 32;
    bh_put_le64((uint8_t*)(val_buf + off), rel->to_scent); off += 8;
    bh_put_le_double((uint8_t*)(val_buf + off), rel->confidence); off += 8;
    memcpy(val_buf + off, rel->evidence, 256); off += 256;
    bh_put_le64((uint8_t*)(val_buf + off), rel->created_at); off += 8;

    /* rel_from: from_scent + rel_type + to_scent -> val */
    char fkey[8 + 32 + 8];
    bh_put_le64((uint8_t*)fkey, rel->from_scent);
    memcpy(fkey + 8, rel->rel_type, 32);
    bh_put_le64((uint8_t*)(fkey + 40), rel->to_scent);
    MDB_val fkey_val = { .mv_size = 48, .mv_data = fkey };
    MDB_val fval = { .mv_size = off, .mv_data = val_buf };
    mdb_put(txn, db->dbs[DBI_REL_FROM], &fkey_val, &fval, 0);

    /* rel_to: to_scent + rel_type + from_scent -> val */
    char tkey[8 + 32 + 8];
    bh_put_le64((uint8_t*)tkey, rel->to_scent);
    memcpy(tkey + 8, rel->rel_type, 32);
    bh_put_le64((uint8_t*)(tkey + 40), rel->from_scent);
    MDB_val tkey_val = { .mv_size = 48, .mv_data = tkey };
    MDB_val tval = { .mv_size = off, .mv_data = val_buf };
    mdb_put(txn, db->dbs[DBI_REL_TO], &tkey_val, &tval, 0);

    /* relationships: full key -> val */
    mdb_put(txn, db->dbs[DBI_RELS], &fkey_val, &fval, 0);

    mdb_txn_commit(txn);
    return 0;
}

/* ---- Trails ---- */

int bh_db_put_trail(bh_db *db, trail *t) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, 0, &txn)) return -1;

    char buf[8 + 256 + 256 + 256 + 8 + 8];
    size_t off = 0;
    bh_put_le64((uint8_t*)(buf + off), t->trail_id); off += 8;
    memcpy(buf + off, t->origin, 256); off += 256;
    memcpy(buf + off, t->destination, 256); off += 256;
    memcpy(buf + off, t->reason, 256); off += 256;
    bh_put_le_double((uint8_t*)(buf + off), t->confidence); off += 8;
    bh_put_le64((uint8_t*)(buf + off), t->created_at); off += 8;

    uint8_t key_buf[8];
    bh_put_le64(key_buf, t->trail_id);
    MDB_val key = { .mv_size = 8, .mv_data = key_buf };
    MDB_val val = { .mv_size = off, .mv_data = buf };
    mdb_put(txn, db->dbs[DBI_TRAILS], &key, &val, 0);

    mdb_txn_commit(txn);
    return 0;
}

int bh_db_put_trail_step(bh_db *db, trail_step *step) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, 0, &txn)) return -1;

    char buf[8 + 4 + 8 + BH_MAX_PATH + 256];
    size_t off = 0;
    bh_put_le64((uint8_t*)(buf + off), step->trail_id); off += 8;
    bh_put_le32((uint8_t*)(buf + off), step->step_num); off += 4;
    bh_put_le64((uint8_t*)(buf + off), step->scent_id); off += 8;
    memcpy(buf + off, step->file_path, BH_MAX_PATH); off += BH_MAX_PATH;
    memcpy(buf + off, step->description, 256); off += 256;

    char key_buf[12];
    bh_put_le64((uint8_t*)key_buf, step->trail_id);
    bh_put_le32((uint8_t*)(key_buf + 8), step->step_num);
    MDB_val key = { .mv_size = 12, .mv_data = key_buf };
    MDB_val val = { .mv_size = off, .mv_data = buf };
    mdb_put(txn, db->dbs[DBI_TRAIL_STEPS], &key, &val, 0);

    mdb_txn_commit(txn);
    return 0;
}

/* ---- Workspace ---- */

int bh_db_put_workspace(bh_db *db, workspace_rec *ws) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, 0, &txn)) return -1;

    char buf[256 + BH_MAX_PATH + 4 + 4 + 512 + 33 + 8 + 8 + 8];
    size_t off = 0;
    memcpy(buf + off, ws->name, 256); off += 256;
    memcpy(buf + off, ws->root_path, BH_MAX_PATH); off += BH_MAX_PATH;
    bh_put_le32((uint8_t*)(buf + off), ws->file_count); off += 4;
    bh_put_le32((uint8_t*)(buf + off), ws->scent_count); off += 4;
    memcpy(buf + off, ws->dominant_topics, 512); off += 512;
    memcpy(buf + off, ws->fingerprint, 33); off += 33;
    bh_put_le64((uint8_t*)(buf + off), ws->last_scan); off += 8;
    bh_put_le64((uint8_t*)(buf + off), ws->created_at); off += 8;
    bh_put_le64((uint8_t*)(buf + off), ws->updated_at); off += 8;

    MDB_val key = { .mv_size = strlen(ws->name), .mv_data = ws->name };
    MDB_val val = { .mv_size = off, .mv_data = buf };
    mdb_put(txn, db->dbs[DBI_WORKSPACES], &key, &val, 0);

    mdb_txn_commit(txn);
    return 0;
}

int bh_db_get_workspace(bh_db *db, const char *name, workspace_rec *ws) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;

    MDB_val key = { .mv_size = strlen(name), .mv_data = (void*)name };
    MDB_val val;
    int rc = mdb_get(txn, db->dbs[DBI_WORKSPACES], &key, &val);
    if (rc) { mdb_txn_abort(txn); return -1; }

    size_t off = 0;
    memcpy(ws->name, val.mv_data + off, 256); off += 256;
    memcpy(ws->root_path, val.mv_data + off, BH_MAX_PATH); off += BH_MAX_PATH;
    ws->file_count = bh_get_le32(val.mv_data + off); off += 4;
    ws->scent_count = bh_get_le32(val.mv_data + off); off += 4;
    memcpy(ws->dominant_topics, val.mv_data + off, 512); off += 512;
    memcpy(ws->fingerprint, val.mv_data + off, 33); off += 33;
    ws->last_scan = bh_get_le64(val.mv_data + off); off += 8;
    ws->created_at = bh_get_le64(val.mv_data + off); off += 8;
    ws->updated_at = bh_get_le64(val.mv_data + off); off += 8;

    mdb_txn_abort(txn);
    return 0;
}

/* ---- Learning ---- */

int bh_db_put_learning(bh_db *db, learning_rec *lr) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, 0, &txn)) return -1;

    char buf[8 + 8 + 32 + 8 + 8];
    size_t off = 0;
    bh_put_le64((uint8_t*)(buf + off), lr->learn_id); off += 8;
    bh_put_le64((uint8_t*)(buf + off), lr->scent_id); off += 8;
    memcpy(buf + off, lr->event, 32); off += 32;
    bh_put_le_double((uint8_t*)(buf + off), lr->confidence_delta); off += 8;
    bh_put_le64((uint8_t*)(buf + off), lr->timestamp); off += 8;

    uint8_t key_buf[8];
    bh_put_le64(key_buf, lr->learn_id);
    MDB_val key = { .mv_size = 8, .mv_data = key_buf };
    MDB_val val = { .mv_size = off, .mv_data = buf };
    mdb_put(txn, db->dbs[DBI_LEARNING], &key, &val, 0);

    /* learn_scent: scent_id + learn_id -> empty */
    char skey[16];
    bh_put_le64((uint8_t*)skey, lr->scent_id);
    bh_put_le64((uint8_t*)(skey + 8), lr->learn_id);
    MDB_val skey_val = { .mv_size = 16, .mv_data = skey };
    MDB_val sval = { .mv_size = 0, .mv_data = NULL };
    mdb_put(txn, db->dbs[DBI_LEARN_SCENT], &skey_val, &sval, 0);

    mdb_txn_commit(txn);
    return 0;
}

/* ---- Iteration (cursor-based) ---- */

int bh_db_iter_scents(bh_db *db, scent_callback cb, void *user_data) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;

    MDB_cursor *cur;
    if (mdb_cursor_open(txn, db->dbs[DBI_SCENTS], &cur)) { mdb_txn_abort(txn); return -1; }

    MDB_val key, val;
    int rc = mdb_cursor_get(cur, &key, &val, MDB_FIRST);
    int count = 0;
    while (rc == 0) {
        /* Decompress */
        size_t orig_size = ZSTD_getFrameContentSize(val.mv_data, val.mv_size);
        if (orig_size == ZSTD_CONTENTSIZE_ERROR || orig_size == ZSTD_CONTENTSIZE_UNKNOWN)
            orig_size = sizeof(scent_packet) + 12 + BH_MAX_LINE * 3;
        char *raw = malloc(orig_size);
        if (raw) {
            size_t decomp = bh_zstd_decompress(val.mv_data, val.mv_size, raw, orig_size);
            if (!ZSTD_isError(decomp)) {
                scent_packet pkt;
                char ctx_before[BH_MAX_LINE], ctx_match[BH_MAX_LINE], ctx_after[BH_MAX_LINE];
                deserialize_scent(raw, decomp, &pkt, ctx_before, sizeof(ctx_before),
                                  ctx_match, sizeof(ctx_match), ctx_after, sizeof(ctx_after));
                cb(&pkt, ctx_before, ctx_match, ctx_after, user_data);
                count++;
            }
            free(raw);
        }
        rc = mdb_cursor_get(cur, &key, &val, MDB_NEXT);
    }
    mdb_cursor_close(cur);
    mdb_txn_abort(txn);
    return count;
}

int bh_db_iter_file_scents(bh_db *db, const char *file_path, scent_callback cb, void *user_data) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;

    MDB_cursor *cur;
    if (mdb_cursor_open(txn, db->dbs[DBI_FILE_SCENTS], &cur)) { mdb_txn_abort(txn); return -1; }

    size_t plen = strlen(file_path);
    char prefix[BH_MAX_PATH + 1];
    memcpy(prefix, file_path, plen);
    prefix[plen] = '\0';

    MDB_val key = { .mv_size = plen + 1, .mv_data = prefix };
    MDB_val val;
    int rc = mdb_cursor_get(cur, &key, &val, MDB_SET_RANGE);
    int count = 0;
    while (rc == 0 && key.mv_size >= plen + 1 && memcmp(key.mv_data, prefix, plen + 1) == 0) {
        /* Extract scent_id from key (after the null) */
        uint64_t scent_id = bh_get_le64((uint8_t*)key.mv_data + plen + 1);
        scent_packet pkt;
        char ctx_before[BH_MAX_LINE], ctx_match[BH_MAX_LINE], ctx_after[BH_MAX_LINE];
        if (bh_db_get_scent(db, scent_id, &pkt, ctx_before, sizeof(ctx_before),
                            ctx_match, sizeof(ctx_match), ctx_after, sizeof(ctx_after)) == 0) {
            cb(&pkt, ctx_before, ctx_match, ctx_after, user_data);
            count++;
        }
        rc = mdb_cursor_get(cur, &key, &val, MDB_NEXT);
    }
    mdb_cursor_close(cur);
    mdb_txn_abort(txn);
    return count;
}

int bh_db_iter_type_scents(bh_db *db, const char *type, scent_callback cb, void *user_data) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;

    MDB_cursor *cur;
    if (mdb_cursor_open(txn, db->dbs[DBI_TYPE_INDEX], &cur)) { mdb_txn_abort(txn); return -1; }

    size_t tlen = strlen(type);
    char prefix[33];
    memcpy(prefix, type, tlen);
    prefix[tlen] = '\0';

    MDB_val key = { .mv_size = tlen + 1, .mv_data = prefix };
    MDB_val val;
    int rc = mdb_cursor_get(cur, &key, &val, MDB_SET_RANGE);
    int count = 0;
    while (rc == 0 && key.mv_size >= tlen + 1 && memcmp(key.mv_data, prefix, tlen + 1) == 0) {
        uint64_t scent_id = bh_get_le64((uint8_t*)key.mv_data + tlen + 1);
        scent_packet pkt;
        char ctx_before[BH_MAX_LINE], ctx_match[BH_MAX_LINE], ctx_after[BH_MAX_LINE];
        if (bh_db_get_scent(db, scent_id, &pkt, ctx_before, sizeof(ctx_before),
                            ctx_match, sizeof(ctx_match), ctx_after, sizeof(ctx_after)) == 0) {
            cb(&pkt, ctx_before, ctx_match, ctx_after, user_data);
            count++;
        }
        rc = mdb_cursor_get(cur, &key, &val, MDB_NEXT);
    }
    mdb_cursor_close(cur);
    mdb_txn_abort(txn);
    return count;
}

int bh_db_iter_rels_from(bh_db *db, uint64_t scent_id, rel_callback cb, void *user_data) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;

    MDB_cursor *cur;
    if (mdb_cursor_open(txn, db->dbs[DBI_REL_FROM], &cur)) { mdb_txn_abort(txn); return -1; }

    uint8_t prefix[8];
    bh_put_le64(prefix, scent_id);
    MDB_val key = { .mv_size = 8, .mv_data = prefix };
    MDB_val val;
    int rc = mdb_cursor_get(cur, &key, &val, MDB_SET_RANGE);
    int count = 0;
    while (rc == 0 && key.mv_size >= 8 && memcmp(key.mv_data, prefix, 8) == 0) {
        relationship rel;
        size_t off = 0;
        rel.from_scent = bh_get_le64(val.mv_data + off); off += 8;
        memcpy(rel.rel_type, val.mv_data + off, 32); off += 32;
        rel.to_scent = bh_get_le64(val.mv_data + off); off += 8;
        rel.confidence = bh_get_le_double(val.mv_data + off); off += 8;
        memcpy(rel.evidence, val.mv_data + off, 256); off += 256;
        rel.created_at = bh_get_le64(val.mv_data + off); off += 8;
        cb(&rel, user_data);
        count++;
        rc = mdb_cursor_get(cur, &key, &val, MDB_NEXT);
    }
    mdb_cursor_close(cur);
    mdb_txn_abort(txn);
    return count;
}

int bh_db_iter_rels_to(bh_db *db, uint64_t scent_id, rel_callback cb, void *user_data) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;

    MDB_cursor *cur;
    if (mdb_cursor_open(txn, db->dbs[DBI_REL_TO], &cur)) { mdb_txn_abort(txn); return -1; }

    uint8_t prefix[8];
    bh_put_le64(prefix, scent_id);
    MDB_val key = { .mv_size = 8, .mv_data = prefix };
    MDB_val val;
    int rc = mdb_cursor_get(cur, &key, &val, MDB_SET_RANGE);
    int count = 0;
    while (rc == 0 && key.mv_size >= 8 && memcmp(key.mv_data, prefix, 8) == 0) {
        relationship rel;
        size_t off = 0;
        rel.from_scent = bh_get_le64(val.mv_data + off); off += 8;
        memcpy(rel.rel_type, val.mv_data + off, 32); off += 32;
        rel.to_scent = bh_get_le64(val.mv_data + off); off += 8;
        rel.confidence = bh_get_le_double(val.mv_data + off); off += 8;
        memcpy(rel.evidence, val.mv_data + off, 256); off += 256;
        rel.created_at = bh_get_le64(val.mv_data + off); off += 8;
        cb(&rel, user_data);
        count++;
        rc = mdb_cursor_get(cur, &key, &val, MDB_NEXT);
    }
    mdb_cursor_close(cur);
    mdb_txn_abort(txn);
    return count;
}

int bh_db_iter_trails(bh_db *db, trail_callback cb, void *user_data) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;

    MDB_cursor *cur;
    if (mdb_cursor_open(txn, db->dbs[DBI_TRAILS], &cur)) { mdb_txn_abort(txn); return -1; }

    MDB_val key, val;
    int rc = mdb_cursor_get(cur, &key, &val, MDB_FIRST);
    int count = 0;
    while (rc == 0) {
        trail t;
        size_t off = 0;
        t.trail_id = bh_get_le64(val.mv_data + off); off += 8;
        memcpy(t.origin, val.mv_data + off, 256); off += 256;
        memcpy(t.destination, val.mv_data + off, 256); off += 256;
        memcpy(t.reason, val.mv_data + off, 256); off += 256;
        t.confidence = bh_get_le_double(val.mv_data + off); off += 8;
        t.created_at = bh_get_le64(val.mv_data + off); off += 8;
        cb(&t, user_data);
        count++;
        rc = mdb_cursor_get(cur, &key, &val, MDB_NEXT);
    }
    mdb_cursor_close(cur);
    mdb_txn_abort(txn);
    return count;
}

int bh_db_count(bh_db *db, const char *dbi_name, uint64_t *count) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;

    /* Find DBI by name */
    MDB_dbi dbi;
    int rc = mdb_dbi_open(txn, dbi_name, 0, &dbi);
    if (rc) { mdb_txn_abort(txn); return -1; }

    MDB_stat stat;
    mdb_stat(txn, dbi, &stat);
    *count = stat.ms_entries;
    mdb_txn_abort(txn);
    return 0;
}

/* ---- Timestamp formatter ---- */

void bh_format_timestamp(uint64_t ts, char *out, size_t out_size) {
    time_t t = (time_t)ts;
    struct tm tm_val;
    localtime_r(&t, &tm_val);
    strftime(out, out_size, "%Y-%m-%d %H:%M:%S", &tm_val);
}

/* ---- Decay all scents ---- */

int bh_db_decay_all(bh_db *db, double factor) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, 0, &txn)) return -1;

    MDB_cursor *cur;
    if (mdb_cursor_open(txn, db->dbs[DBI_SCENTS], &cur)) { mdb_txn_abort(txn); return -1; }

    MDB_val key, val;
    int rc = mdb_cursor_get(cur, &key, &val, MDB_FIRST);
    int count = 0;
    while (rc == 0) {
        size_t orig_size = ZSTD_getFrameContentSize(val.mv_data, val.mv_size);
        if (orig_size == ZSTD_CONTENTSIZE_ERROR || orig_size == ZSTD_CONTENTSIZE_UNKNOWN)
            orig_size = sizeof(scent_packet) + 12 + BH_MAX_LINE * 3;
        char *raw = malloc(orig_size);
        if (raw) {
            size_t decomp = bh_zstd_decompress(val.mv_data, val.mv_size, raw, orig_size);
            if (!ZSTD_isError(decomp)) {
                scent_packet pkt;
                char ctx_before[BH_MAX_LINE], ctx_match[BH_MAX_LINE], ctx_after[BH_MAX_LINE];
                deserialize_scent(raw, decomp, &pkt, ctx_before, sizeof(ctx_before),
                                  ctx_match, sizeof(ctx_match), ctx_after, sizeof(ctx_after));
                pkt.confidence *= factor;
                pkt.updated_at = time(NULL);

                /* Re-serialize + compress + put */
                size_t raw_sz = sizeof(scent_packet) + 12 + pkt.ctx_before_len + pkt.ctx_match_len + pkt.ctx_after_len;
                char *new_raw = malloc(raw_sz + 1024);
                if (new_raw) {
                    size_t actual = serialize_scent(&pkt, ctx_before, ctx_match, ctx_after, new_raw, raw_sz + 1024);
                    size_t comp_bound = ZSTD_compressBound(actual);
                    char *comp = malloc(comp_bound);
                    if (comp) {
                        size_t comp_size = bh_zstd_compress(new_raw, actual, comp, comp_bound);
                        if (!ZSTD_isError(comp_size)) {
                            MDB_val new_val = { .mv_size = comp_size, .mv_data = comp };
                            mdb_cursor_put(cur, &key, &new_val, MDB_CURRENT);
                            count++;
                        }
                        free(comp);
                    }
                    free(new_raw);
                }
            }
            free(raw);
        }
        rc = mdb_cursor_get(cur, &key, &val, MDB_NEXT);
    }
    mdb_cursor_close(cur);
    mdb_txn_commit(txn);
    return count;
}

/* ---- Content search ---- */

int bh_db_content_search(bh_db *db, const char *text, int limit,
                         void *user_data,
                         int (*cb)(uint64_t file_id, const char *file_path, uint32_t line, const char *line_text, void *user_data)) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;

    MDB_cursor *cur;
    if (mdb_cursor_open(txn, db->dbs[DBI_FILES], &cur)) { mdb_txn_abort(txn); return -1; }

    MDB_val key, val;
    int rc = mdb_cursor_get(cur, &key, &val, MDB_FIRST);
    int count = 0;
    while (rc == 0 && count < limit) {
        file_record rec;
        /* Get header without content first */
        size_t off = 0;
        rec.file_id = bh_get_le64(val.mv_data + off); off += 8;
        memcpy(rec.file_path, val.mv_data + off, BH_MAX_PATH); off += BH_MAX_PATH;
        memcpy(rec.relative_path, val.mv_data + off, 512); off += 512;
        memcpy(rec.workspace, val.mv_data + off, 256); off += 256;
        memcpy(rec.language, val.mv_data + off, 16); off += 16;
        rec.size = bh_get_le64(val.mv_data + off); off += 8;
        rec.mtime = bh_get_le64(val.mv_data + off); off += 8;
        memcpy(rec.content_hash, val.mv_data + off, 33); off += 33;
        rec.scan_time = bh_get_le64(val.mv_data + off); off += 8;
        rec.compressed_size = bh_get_le32(val.mv_data + off); off += 4;

        /* Decompress content */
        char *content = malloc(rec.size + 1);
        if (content) {
            size_t decomp = ZSTD_decompress(content, rec.size + 1, val.mv_data + off, rec.compressed_size);
            if (!ZSTD_isError(decomp)) {
                content[decomp] = '\0';
                /* Search line by line */
                char *line_start = content;
                uint32_t line_num = 1;
                for (size_t i = 0; i <= decomp && count < limit; i++) {
                    if (i == decomp || content[i] == '\n') {
                        content[i] = '\0';
                        /* Case-insensitive search */
                        if (strcasestr(line_start, text)) {
                            cb(rec.file_id, rec.file_path, line_num, line_start, user_data);
                            count++;
                        }
                        if (i < decomp) content[i] = '\n';
                        line_start = content + i + 1;
                        line_num++;
                    }
                }
            }
            free(content);
        }
        rc = mdb_cursor_get(cur, &key, &val, MDB_NEXT);
    }
    mdb_cursor_close(cur);
    mdb_txn_abort(txn);
    return count;
}

/* ---- Detect deletions ---- */

int bh_db_detect_deletions(bh_db *db, const char *workspace, const char *root_path, uint32_t *deleted_count) {
    *deleted_count = 0;
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;

    MDB_cursor *cur;
    if (mdb_cursor_open(txn, db->dbs[DBI_FILES], &cur)) { mdb_txn_abort(txn); return -1; }

    MDB_val key, val;
    int rc = mdb_cursor_get(cur, &key, &val, MDB_FIRST);
    while (rc == 0) {
        /* Extract file_path from record */
        char file_path[BH_MAX_PATH];
        memcpy(file_path, val.mv_data + 8, BH_MAX_PATH);
        file_path[BH_MAX_PATH - 1] = '\0';

        struct stat st;
        if (stat(file_path, &st) != 0) {
            /* File deleted */
            (*deleted_count)++;
            /* Log observation */
            observation obs;
            memset(&obs, 0, sizeof(obs));
            obs.obs_id = bh_db_next_id(db, "next_obs_id");
            obs.timestamp = time(NULL);
            strncpy(obs.workspace, workspace, 255);
            strncpy(obs.file_path, file_path, BH_MAX_PATH - 1);
            strcpy(obs.action, "deleted");
            strcpy(obs.observer_version, "1.0");
            bh_db_put_observation(db, &obs);
        }
        rc = mdb_cursor_get(cur, &key, &val, MDB_NEXT);
    }
    mdb_cursor_close(cur);
    mdb_txn_abort(txn);
    return 0;
}

/* ---- Iterate all files ---- */

int bh_db_iter_all_files(bh_db *db, file_callback cb, void *user_data) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;

    MDB_cursor *cur;
    if (mdb_cursor_open(txn, db->dbs[DBI_FILES], &cur)) { mdb_txn_abort(txn); return -1; }

    MDB_val key, val;
    int rc = mdb_cursor_get(cur, &key, &val, MDB_FIRST);
    int count = 0;
    while (rc == 0) {
        file_record rec;
        size_t off = 0;
        rec.file_id = bh_get_le64(val.mv_data + off); off += 8;
        memcpy(rec.file_path, val.mv_data + off, BH_MAX_PATH); off += BH_MAX_PATH;
        memcpy(rec.relative_path, val.mv_data + off, 512); off += 512;
        memcpy(rec.workspace, val.mv_data + off, 256); off += 256;
        memcpy(rec.language, val.mv_data + off, 16); off += 16;
        rec.size = bh_get_le64(val.mv_data + off); off += 8;
        rec.mtime = bh_get_le64(val.mv_data + off); off += 8;
        memcpy(rec.content_hash, val.mv_data + off, 33); off += 33;
        rec.scan_time = bh_get_le64(val.mv_data + off); off += 8;
        rec.compressed_size = bh_get_le32(val.mv_data + off); off += 4;

        char *content = malloc(rec.size + 1);
        if (content) {
            size_t decomp = ZSTD_decompress(content, rec.size + 1, val.mv_data + off, rec.compressed_size);
            if (!ZSTD_isError(decomp)) {
                content[decomp] = '\0';
                cb(&rec, content, decomp, user_data);
                count++;
            }
            free(content);
        }
        rc = mdb_cursor_get(cur, &key, &val, MDB_NEXT);
    }
    mdb_cursor_close(cur);
    mdb_txn_abort(txn);
    return count;
}

/* ---- Recent observations (reverse scan) ---- */

int bh_db_iter_recent_obs(bh_db *db, int limit, void *user_data,
                          int (*cb)(observation *obs, void *user_data)) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;

    MDB_cursor *cur;
    if (mdb_cursor_open(txn, db->dbs[DBI_OBS_RECENT], &cur)) { mdb_txn_abort(txn); return -1; }

    MDB_val key, val;
    /* Start from last entry and go backwards */
    int rc = mdb_cursor_get(cur, &key, &val, MDB_LAST);
    int count = 0;
    while (rc == 0 && count < limit) {
        /* Extract obs_id from key (last 8 bytes) */
        uint64_t obs_id = bh_get_le64((uint8_t*)key.mv_data + 8);

        /* Get full observation from observations DB */
        uint8_t obs_key[8];
        bh_put_le64(obs_key, obs_id);
        MDB_val okey = { .mv_size = 8, .mv_data = obs_key };
        MDB_val oval;
        if (mdb_get(txn, db->dbs[DBI_OBSERVATIONS], &okey, &oval) == 0) {
            observation obs;
            size_t off = 0;
            obs.obs_id = bh_get_le64(oval.mv_data + off); off += 8;
            obs.timestamp = bh_get_le64(oval.mv_data + off); off += 8;
            memcpy(obs.workspace, oval.mv_data + off, 256); off += 256;
            memcpy(obs.file_path, oval.mv_data + off, BH_MAX_PATH); off += BH_MAX_PATH;
            obs.scent_id = bh_get_le64(oval.mv_data + off); off += 8;
            memcpy(obs.action, oval.mv_data + off, 16); off += 16;
            memcpy(obs.observer_version, oval.mv_data + off, 8); off += 8;
            cb(&obs, user_data);
            count++;
        }
        rc = mdb_cursor_get(cur, &key, &val, MDB_PREV);
    }
    mdb_cursor_close(cur);
    mdb_txn_abort(txn);
    return count;
}

/* ---- Trail steps ---- */

int bh_db_get_trail_steps(bh_db *db, uint64_t trail_id, void *user_data,
                          int (*cb)(trail_step *step, void *user_data)) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;

    MDB_cursor *cur;
    if (mdb_cursor_open(txn, db->dbs[DBI_TRAIL_STEPS], &cur)) { mdb_txn_abort(txn); return -1; }

    uint8_t prefix[8];
    bh_put_le64(prefix, trail_id);
    MDB_val key = { .mv_size = 8, .mv_data = prefix };
    MDB_val val;
    int rc = mdb_cursor_get(cur, &key, &val, MDB_SET_RANGE);
    int count = 0;
    while (rc == 0 && key.mv_size >= 8 && memcmp(key.mv_data, prefix, 8) == 0) {
        trail_step step;
        size_t off = 0;
        step.trail_id = bh_get_le64(val.mv_data + off); off += 8;
        step.step_num = bh_get_le32(val.mv_data + off); off += 4;
        step.scent_id = bh_get_le64(val.mv_data + off); off += 8;
        memcpy(step.file_path, val.mv_data + off, BH_MAX_PATH); off += BH_MAX_PATH;
        memcpy(step.description, val.mv_data + off, 256); off += 256;
        cb(&step, user_data);
        count++;
        rc = mdb_cursor_get(cur, &key, &val, MDB_NEXT);
    }
    mdb_cursor_close(cur);
    mdb_txn_abort(txn);
    return count;
}

/* ---- Find file by hash ---- */

int bh_db_find_file_by_hash(bh_db *db, const char *hash, uint64_t *file_id) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;
    MDB_dbi dbi;
    if (mdb_dbi_open(txn, BH_DB_FILE_HASHES, 0, &dbi)) { mdb_txn_abort(txn); return -1; }
    MDB_val key = { .mv_size = strlen(hash), .mv_data = (void*)hash };
    MDB_val val;
    int rc = mdb_get(txn, dbi, &key, &val);
    if (rc == 0 && val.mv_size >= 8) {
        *file_id = bh_get_le64(val.mv_data);
        mdb_txn_abort(txn);
        return 0;
    }
    mdb_txn_abort(txn);
    return -1;
}

/* ---- Delete file ---- */

int bh_db_delete_file(bh_db *db, uint64_t file_id) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, 0, &txn)) return -1;
    uint8_t key_buf[8];
    bh_put_le64(key_buf, file_id);
    MDB_val key = { .mv_size = 8, .mv_data = key_buf };
    mdb_del(txn, db->dbs[DBI_FILES], &key, NULL);
    mdb_txn_commit(txn);
    return 0;
}

/* ---- Language index iteration ---- */

int bh_db_iter_lang_scents(bh_db *db, const char *lang, scent_callback cb, void *user_data) {
    /* Use type_index pattern but with language — for now iterate all and filter */
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;
    MDB_cursor *cur;
    if (mdb_cursor_open(txn, db->dbs[DBI_SCENTS], &cur)) { mdb_txn_abort(txn); return -1; }
    MDB_val key, val;
    int rc = mdb_cursor_get(cur, &key, &val, MDB_FIRST);
    int count = 0;
    while (rc == 0) {
        size_t orig_size = ZSTD_getFrameContentSize(val.mv_data, val.mv_size);
        if (orig_size == ZSTD_CONTENTSIZE_ERROR || orig_size == ZSTD_CONTENTSIZE_UNKNOWN)
            orig_size = sizeof(scent_packet) + 12 + BH_MAX_LINE * 3;
        char *raw = malloc(orig_size);
        if (raw) {
            size_t decomp = bh_zstd_decompress(val.mv_data, val.mv_size, raw, orig_size);
            if (!ZSTD_isError(decomp)) {
                scent_packet pkt;
                char ctx_b[BH_MAX_LINE], ctx_m[BH_MAX_LINE], ctx_a[BH_MAX_LINE];
                deserialize_scent(raw, decomp, &pkt, ctx_b, sizeof(ctx_b), ctx_m, sizeof(ctx_m), ctx_a, sizeof(ctx_a));
                if (strcmp(pkt.language, lang) == 0) {
                    cb(&pkt, ctx_b, ctx_m, ctx_a, user_data);
                    count++;
                }
            }
            free(raw);
        }
        rc = mdb_cursor_get(cur, &key, &val, MDB_NEXT);
    }
    mdb_cursor_close(cur);
    mdb_txn_abort(txn);
    return count;
}

/* ---- Workspace index iteration ---- */

int bh_db_iter_ws_scents(bh_db *db, const char *ws, scent_callback cb, void *user_data) {
    MDB_txn *txn;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn)) return -1;
    MDB_cursor *cur;
    if (mdb_cursor_open(txn, db->dbs[DBI_SCENTS], &cur)) { mdb_txn_abort(txn); return -1; }
    MDB_val key, val;
    int rc = mdb_cursor_get(cur, &key, &val, MDB_FIRST);
    int count = 0;
    while (rc == 0) {
        size_t orig_size = ZSTD_getFrameContentSize(val.mv_data, val.mv_size);
        if (orig_size == ZSTD_CONTENTSIZE_ERROR || orig_size == ZSTD_CONTENTSIZE_UNKNOWN)
            orig_size = sizeof(scent_packet) + 12 + BH_MAX_LINE * 3;
        char *raw = malloc(orig_size);
        if (raw) {
            size_t decomp = bh_zstd_decompress(val.mv_data, val.mv_size, raw, orig_size);
            if (!ZSTD_isError(decomp)) {
                scent_packet pkt;
                char ctx_b[BH_MAX_LINE], ctx_m[BH_MAX_LINE], ctx_a[BH_MAX_LINE];
                deserialize_scent(raw, decomp, &pkt, ctx_b, sizeof(ctx_b), ctx_m, sizeof(ctx_m), ctx_a, sizeof(ctx_a));
                if (strcmp(pkt.workspace, ws) == 0) {
                    cb(&pkt, ctx_b, ctx_m, ctx_a, user_data);
                    count++;
                }
            }
            free(raw);
        }
        rc = mdb_cursor_get(cur, &key, &val, MDB_NEXT);
    }
    mdb_cursor_close(cur);
    mdb_txn_abort(txn);
    return count;
}
