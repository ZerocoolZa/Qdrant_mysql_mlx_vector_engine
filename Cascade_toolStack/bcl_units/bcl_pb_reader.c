//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_pb_reader.c" date="2026-06-29" author="cascade" session_id="bcl-toolstack-units" context="BCL unit for encrypted .pb chat file reading — AES-256-GCM decrypt, protobuf wire-format parse, in-RAM SQLite search. Converted from chat_mover/pb_reader.py"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_pb_reader.c" domain="cascade_tools" authority="PbReader"}
//[@SUMMARY]{summary="Decrypts .pb chat files (AES-256-GCM), parses protobuf wire-format, loads into in-RAM SQLite, searches chat history. Commands: scan, load, load-all, read, search, export, stats, read_state, set_config."}
//[@CLASS]{class="PbReader" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="DecryptFile" type="command"}
//[@METHOD]{method="ParseTrajectory" type="command"}
//[@METHOD]{method="LoadToRam" type="command"}
//[@METHOD]{method="Search" type="query"}
//[@METHOD]{method="Read" type="query"}
//[@METHOD]{method="Export" type="command"}
//[@REVIEW]{[@date<2026-06-29>][@reviewer<cascade>][@status<draft>][@notes<Converted from Python pb_reader.py. AES-GCM via OpenSSL. Protobuf wire-format parser. In-RAM SQLite.>][@todos<link OpenSSL, test compile>]}

#include "bcl_toolstack.h"
#include <openssl/evp.h>
#include <openssl/aes.h>
#include <dirent.h>
#include <sys/stat.h>

/* ===== DIM BLOCK ===== */

/* AES-256-GCM key (same as language_server_macos_arm binary) */
static const unsigned char PB_AES_KEY[32] = {
    0x73, 0x61, 0x66, 0x65, 0x43, 0x6f, 0x64, 0x65,
    0x69, 0x75, 0x6d, 0x77, 0x6f, 0x72, 0x6c, 0x64,
    0x4b, 0x65, 0x59, 0x73, 0x65, 0x63, 0x72, 0x65,
    0x74, 0x42, 0x61, 0x6c, 0x6c, 0x6f, 0x6f, 0x6e
};

#define NONCE_SIZE   12
#define TAG_SIZE     16
#define MAX_PB_SIZE  10485760

/* Protobuf wire types */
#define WIRE_VARINT    0
#define WIRE_64BIT     1
#define WIRE_LENGTH    2
#define WIRE_32BIT     5
#define WIRE_GROUP_END 4

/* Variant field numbers (empirically discovered) */
#define VARIANT_USER_INPUT       19
#define VARIANT_PLANNER_RESPONSE 20
#define VARIANT_RUN_COMMAND      28
#define VARIANT_CHECKPOINT       30

/* Paths */
#define WINDSURF_ROOT_LEN 4096
static char WINDSURF_ROOT[WINDSURF_ROOT_LEN];
static const char *PB_DIRS[] = {"cascade", "implicit", "memories"};
#define PB_DIR_COUNT 3

/* State */
static struct {
    sqlite3 *db;
    int initialized;
    int files_scanned;
    int files_loaded;
    char last_error[256];
} STATE;

/* ===== PROTOBUF WIRE-FORMAT PARSING ===== */

static int read_varint(const unsigned char *buf, int buf_len, int pos, long long *val) {
    long long v = 0;
    int shift = 0;
    while (pos < buf_len) {
        unsigned char b = buf[pos++];
        v |= (long long)(b & 0x7F) << shift;
        if (!(b & 0x80)) {
            *val = v;
            return pos;
        }
        shift += 7;
        if (shift > 63) return -1;
    }
    return -1;
}

static int parse_tag(int tag, int *field_no, int *wire_type) {
    *field_no = tag >> 3;
    *wire_type = tag & 7;
    return 1;
}

static int skip_value(const unsigned char *buf, int buf_len, int pos, int wire_type) {
    long long v;
    switch (wire_type) {
        case WIRE_VARINT:
            return read_varint(buf, buf_len, pos, &v);
        case WIRE_64BIT:
            return pos + 8;
        case WIRE_LENGTH: {
            int new_pos = read_varint(buf, buf_len, pos, &v);
            if (new_pos < 0) return -1;
            return new_pos + (int)v;
        }
        case WIRE_32BIT:
            return pos + 4;
        default:
            return -1;
    }
}

static int read_string_field(const unsigned char *data, int data_len,
                              int target_fno, char *out, int out_sz) {
    int pos = 0;
    while (pos < data_len) {
        long long tag_val;
        int new_pos = read_varint(data, data_len, pos, &tag_val);
        if (new_pos < 0) return 0;
        pos = new_pos;
        int fno, wt;
        parse_tag((int)tag_val, &fno, &wt);
        if (fno == target_fno && wt == WIRE_LENGTH) {
            long long len;
            new_pos = read_varint(data, data_len, pos, &len);
            if (new_pos < 0) return 0;
            pos = new_pos;
            int copy_len = (int)len;
            if (copy_len >= out_sz) copy_len = out_sz - 1;
            memcpy(out, data + pos, copy_len);
            out[copy_len] = '\0';
            return 1;
        }
        pos = skip_value(data, data_len, pos, wt);
        if (pos < 0) return 0;
    }
    return 0;
}

/* ===== AES-256-GCM DECRYPT ===== */

static int decrypt_file(const char *path, unsigned char *out, int out_sz) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    
    fseek(f, 0, SEEK_END);
    long fsize = ftell(f);
    fseek(f, 0, SEEK_SET);
    
    if (fsize < NONCE_SIZE + TAG_SIZE || fsize > MAX_PB_SIZE) {
        fclose(f);
        return -1;
    }
    
    unsigned char *raw = malloc(fsize);
    if (!raw) { fclose(f); return -1; }
    fread(raw, 1, fsize, f);
    fclose(f);
    
    unsigned char nonce[NONCE_SIZE];
    memcpy(nonce, raw, NONCE_SIZE);
    
    int ct_len = (int)fsize - NONCE_SIZE;
    unsigned char *ciphertext = raw + NONCE_SIZE;
    
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    if (!ctx) { free(raw); return -1; }
    
    int ret = -1;
    int len = 0;
    int total = 0;
    
    if (EVP_DecryptInit_ex(ctx, EVP_aes_256_gcm(), NULL, NULL, NULL) != 1) goto done;
    if (EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_IVLEN, NONCE_SIZE, NULL) != 1) goto done;
    if (EVP_DecryptInit_ex(ctx, NULL, NULL, PB_AES_KEY, nonce) != 1) goto done;
    
    if (EVP_DecryptUpdate(ctx, out, &len, ciphertext, ct_len - TAG_SIZE) != 1) goto done;
    total = len;
    
    if (EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_TAG, TAG_SIZE,
                            ciphertext + ct_len - TAG_SIZE) != 1) goto done;
    
    if (EVP_DecryptFinal_ex(ctx, out + total, &len) != 1) goto done;
    total += len;
    ret = total;
    
done:
    EVP_CIPHER_CTX_free(ctx);
    free(raw);
    return ret;
}

/* ===== IN-RAM SQLITE SCHEMA ===== */

static int init_db(void) {
    if (STATE.db) return 1;
    if (sqlite3_open(":memory:", &STATE.db) != SQLITE_OK) return 0;
    
    const char *schema =
        "CREATE TABLE IF NOT EXISTS trajectories ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  trajectory_id TEXT, cascade_id TEXT,"
        "  file_path TEXT UNIQUE, file_category TEXT,"
        "  trajectory_type INTEGER, source INTEGER,"
        "  steps_count INTEGER, decrypted_size INTEGER,"
        "  loaded_at TEXT DEFAULT (datetime('now')));"
        "CREATE TABLE IF NOT EXISTS steps ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  trajectory_fk INTEGER, step_index INTEGER,"
        "  step_type INTEGER, step_type_name TEXT,"
        "  status INTEGER, variant_field INTEGER,"
        "  variant_data BLOB,"
        "  FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id));"
        "CREATE TABLE IF NOT EXISTS user_messages ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  trajectory_fk INTEGER, step_index INTEGER,"
        "  prompt TEXT,"
        "  FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id));"
        "CREATE TABLE IF NOT EXISTS assistant_messages ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  trajectory_fk INTEGER, step_index INTEGER,"
        "  user_facing TEXT, internal_planning TEXT,"
        "  FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id));"
        "CREATE TABLE IF NOT EXISTS commands ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  trajectory_fk INTEGER, step_index INTEGER,"
        "  command TEXT, output TEXT,"
        "  FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id));"
        "CREATE TABLE IF NOT EXISTS checkpoints ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  trajectory_fk INTEGER, step_index INTEGER,"
        "  checkpoint_index INTEGER, conversation_title TEXT,"
        "  user_intent TEXT, session_summary TEXT,"
        "  code_change_summary TEXT, memory_summary TEXT,"
        "  plan_snapshot TEXT, intent_only INTEGER,"
        "  edited_files TEXT,"
        "  FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id));"
        "CREATE INDEX IF NOT EXISTS idx_steps_traj ON steps(trajectory_fk);"
        "CREATE INDEX IF NOT EXISTS idx_user_traj ON user_messages(trajectory_fk);"
        "CREATE INDEX IF NOT EXISTS idx_asst_traj ON assistant_messages(trajectory_fk);"
        "CREATE INDEX IF NOT EXISTS idx_cmd_traj ON commands(trajectory_fk);"
        "CREATE INDEX IF NOT EXISTS idx_cp_traj ON checkpoints(trajectory_fk);";
    
    if (sqlite3_exec(STATE.db, schema, NULL, NULL, NULL) != SQLITE_OK) return 0;
    return 1;
}

/* ===== SCAN ===== */

static int scan_dir(const char *dir_path, const char *category) {
    DIR *d = opendir(dir_path);
    if (!d) return 0;
    
    struct dirent *ent;
    int count = 0;
    while ((ent = readdir(d)) != NULL) {
        if (strstr(ent->d_name, ".pb") == NULL) continue;
        count++;
    }
    closedir(d);
    return count;
}

/* ===== PARSE A STEP MESSAGE — extract variant content ===== */

/* Extract a string field from a nested protobuf message.
   data/len = the nested message bytes, target_fno = field number to find.
   Returns 1 if found, 0 if not. out/out_sz = destination. */
static int extract_step_string(const unsigned char *data, int data_len,
                                int target_fno, char *out, int out_sz) {
    int pos = 0;
    while (pos < data_len) {
        long long tag_val;
        int new_pos = read_varint(data, data_len, pos, &tag_val);
        if (new_pos < 0) return 0;
        pos = new_pos;
        int fno, wt;
        parse_tag((int)tag_val, &fno, &wt);

        if (wt == WIRE_LENGTH) {
            long long len;
            new_pos = read_varint(data, data_len, pos, &len);
            if (new_pos < 0) return 0;
            pos = new_pos;

            if (fno == target_fno) {
                int copy_len = (int)len;
                if (copy_len >= out_sz) copy_len = out_sz - 1;
                memcpy(out, data + pos, copy_len);
                out[copy_len] = '\0';
                return 1;
            }
            pos += (int)len;
        } else {
            pos = skip_value(data, data_len, pos, wt);
            if (pos < 0) return 0;
        }
    }
    return 0;
}

/* Recursively search a step message for a string field at any depth.
   Some protobuf schemas nest the variant data inside sub-messages. */
static int deep_extract_string(const unsigned char *data, int data_len,
                                int target_fno, char *out, int out_sz,
                                int depth) {
    if (depth > 6) return 0;
    int pos = 0;
    while (pos < data_len) {
        long long tag_val;
        int new_pos = read_varint(data, data_len, pos, &tag_val);
        if (new_pos < 0) return 0;
        pos = new_pos;
        int fno, wt;
        parse_tag((int)tag_val, &fno, &wt);

        if (wt == WIRE_LENGTH) {
            long long len;
            new_pos = read_varint(data, data_len, pos, &len);
            if (new_pos < 0) return 0;
            pos = new_pos;

            if (fno == target_fno) {
                int copy_len = (int)len;
                if (copy_len >= out_sz) copy_len = out_sz - 1;
                memcpy(out, data + pos, copy_len);
                out[copy_len] = '\0';
                return 1;
            }
            /* Recurse into nested messages */
            if (deep_extract_string(data + pos, (int)len, target_fno,
                                     out, out_sz, depth + 1)) {
                return 1;
            }
            pos += (int)len;
        } else {
            pos = skip_value(data, data_len, pos, wt);
            if (pos < 0) return 0;
        }
    }
    return 0;
}

/* ===== LOAD ONE FILE ===== */

static int load_one(const char *pb_path, const char *category) {
    if (!init_db()) return 0;

    static unsigned char plaintext[MAX_PB_SIZE];
    int pt_len = decrypt_file(pb_path, plaintext, MAX_PB_SIZE);
    if (pt_len < 0) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "decrypt failed: %s", pb_path);
        return 0;
    }

    /* Parse trajectory — extract trajectory_id (field 1), cascade_id (field 6) */
    char traj_id[256] = {0};
    char cascade_id[256] = {0};
    int steps_count = 0;

    /* First pass: get trajectory metadata + collect step positions */
    int step_positions[4096];
    int step_lengths[4096];
    int step_count = 0;

    int pos = 0;
    while (pos < pt_len) {
        long long tag_val;
        int new_pos = read_varint(plaintext, pt_len, pos, &tag_val);
        if (new_pos < 0) break;
        pos = new_pos;
        int fno, wt;
        parse_tag((int)tag_val, &fno, &wt);

        if (wt == WIRE_LENGTH) {
            long long len;
            new_pos = read_varint(plaintext, pt_len, pos, &len);
            if (new_pos < 0) break;
            pos = new_pos;

            if (fno == 1) {
                int copy_len = (int)len < 255 ? (int)len : 255;
                memcpy(traj_id, plaintext + pos, copy_len);
                traj_id[copy_len] = '\0';
            } else if (fno == 6) {
                int copy_len = (int)len < 255 ? (int)len : 255;
                memcpy(cascade_id, plaintext + pos, copy_len);
                cascade_id[copy_len] = '\0';
            } else if (fno == 2) {
                if (step_count < 4096) {
                    step_positions[step_count] = pos;
                    step_lengths[step_count] = (int)len;
                }
                step_count++;
                steps_count++;
            }
            pos += (int)len;
        } else {
            pos = skip_value(plaintext, pt_len, pos, wt);
            if (pos < 0) break;
        }
    }

    /* Insert into trajectories table */
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(STATE.db,
        "INSERT OR REPLACE INTO trajectories "
        "(trajectory_id, cascade_id, file_path, file_category, steps_count, decrypted_size) "
        "VALUES (?,?,?,?,?,?)", -1, &stmt, NULL);
    sqlite3_bind_text(stmt, 1, traj_id, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, cascade_id, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, pb_path, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 4, category, -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 5, steps_count);
    sqlite3_bind_int(stmt, 6, pt_len);
    sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    /* Get trajectory FK */
    sqlite3_int64 traj_fk = sqlite3_last_insert_rowid(STATE.db);

    /* Second pass: parse each step for message content */
    for (int s = 0; s < step_count && s < 4096; s++) {
        const unsigned char *step_data = plaintext + step_positions[s];
        int step_len = step_lengths[s];

        /* Insert step record */
        sqlite3_prepare_v2(STATE.db,
            "INSERT INTO steps (trajectory_fk, step_index, step_type, variant_field) "
            "VALUES (?,?,?,?)", -1, &stmt, NULL);
        sqlite3_bind_int64(stmt, 1, traj_fk);
        sqlite3_bind_int(stmt, 2, s);
        sqlite3_bind_int(stmt, 3, 0);
        sqlite3_bind_int(stmt, 4, 0);
        sqlite3_step(stmt);
        sqlite3_finalize(stmt);

        /* Try to extract user input (variant field 19) */
        char user_text[65536] = {0};
        if (deep_extract_string(step_data, step_len, VARIANT_USER_INPUT,
                                 user_text, sizeof(user_text), 0)) {
            sqlite3_prepare_v2(STATE.db,
                "INSERT INTO user_messages (trajectory_fk, step_index, prompt) "
                "VALUES (?,?,?)", -1, &stmt, NULL);
            sqlite3_bind_int64(stmt, 1, traj_fk);
            sqlite3_bind_int(stmt, 2, s);
            sqlite3_bind_text(stmt, 3, user_text, -1, SQLITE_TRANSIENT);
            sqlite3_step(stmt);
            sqlite3_finalize(stmt);
        }

        /* Try to extract assistant response (variant field 20) */
        char asst_text[65536] = {0};
        if (deep_extract_string(step_data, step_len, VARIANT_PLANNER_RESPONSE,
                                 asst_text, sizeof(asst_text), 0)) {
            sqlite3_prepare_v2(STATE.db,
                "INSERT INTO assistant_messages (trajectory_fk, step_index, user_facing) "
                "VALUES (?,?,?)", -1, &stmt, NULL);
            sqlite3_bind_int64(stmt, 1, traj_fk);
            sqlite3_bind_int(stmt, 2, s);
            sqlite3_bind_text(stmt, 3, asst_text, -1, SQLITE_TRANSIENT);
            sqlite3_step(stmt);
            sqlite3_finalize(stmt);
        }

        /* Try to extract run command (variant field 28) */
        char cmd_text[8192] = {0};
        if (deep_extract_string(step_data, step_len, VARIANT_RUN_COMMAND,
                                 cmd_text, sizeof(cmd_text), 0)) {
            sqlite3_prepare_v2(STATE.db,
                "INSERT INTO commands (trajectory_fk, step_index, command) "
                "VALUES (?,?,?)", -1, &stmt, NULL);
            sqlite3_bind_int64(stmt, 1, traj_fk);
            sqlite3_bind_int(stmt, 2, s);
            sqlite3_bind_text(stmt, 3, cmd_text, -1, SQLITE_TRANSIENT);
            sqlite3_step(stmt);
            sqlite3_finalize(stmt);
        }

        /* Try to extract checkpoint (variant field 30) */
        char cp_title[1024] = {0};
        if (deep_extract_string(step_data, step_len, VARIANT_CHECKPOINT,
                                 cp_title, sizeof(cp_title), 0)) {
            sqlite3_prepare_v2(STATE.db,
                "INSERT INTO checkpoints (trajectory_fk, step_index, conversation_title) "
                "VALUES (?,?,?)", -1, &stmt, NULL);
            sqlite3_bind_int64(stmt, 1, traj_fk);
            sqlite3_bind_int(stmt, 2, s);
            sqlite3_bind_text(stmt, 3, cp_title, -1, SQLITE_TRANSIENT);
            sqlite3_step(stmt);
            sqlite3_finalize(stmt);
        }
    }

    STATE.files_loaded++;
    return 1;
}

/* ===== UNIT INTERFACE ===== */

int PbReader_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    const char *home = getenv("HOME");
    if (home) {
        snprintf(WINDSURF_ROOT, sizeof(WINDSURF_ROOT), "%s/.codeium/windsurf", home);
    }
    STATE.initialized = 1;
    return 1;
}

int PbReader_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) PbReader_Init();
    
    if (strcmp(cmd, "scan") == 0) {
        int total = 0;
        char dir_path[WINDSURF_ROOT_LEN];
        for (int i = 0; i < PB_DIR_COUNT; i++) {
            snprintf(dir_path, sizeof(dir_path), "%s/%s", WINDSURF_ROOT, PB_DIRS[i]);
            int count = scan_dir(dir_path, PB_DIRS[i]);
            total += count;
        }
        STATE.files_scanned = total;
        char body[256];
        snprintf(body, sizeof(body), "[@COUNT]{%d}[@ROOT]{%s}", total, WINDSURF_ROOT);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    if (strcmp(cmd, "load-all") == 0) {
        if (!init_db()) return BclResult_Err(bcl_out, out_sz, 10, "db init failed");
        int loaded = 0;
        char dir_path[WINDSURF_ROOT_LEN];
        for (int i = 0; i < PB_DIR_COUNT; i++) {
            snprintf(dir_path, sizeof(dir_path), "%s/%s", WINDSURF_ROOT, PB_DIRS[i]);
            DIR *d = opendir(dir_path);
            if (!d) continue;
            struct dirent *ent;
            while ((ent = readdir(d)) != NULL) {
                if (!strstr(ent->d_name, ".pb")) continue;
                char full_path[WINDSURF_ROOT_LEN + 256];
                snprintf(full_path, sizeof(full_path), "%s/%s", dir_path, ent->d_name);
                if (load_one(full_path, PB_DIRS[i])) loaded++;
            }
            closedir(d);
        }
        char body[256];
        snprintf(body, sizeof(body), "[@LOADED]{%d}[@SCANNED]{%d}", loaded, STATE.files_scanned);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    if (strcmp(cmd, "search") == 0) {
        if (!init_db()) return BclResult_Err(bcl_out, out_sz, 10, "db init failed");
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[1024] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Free(&parse);
        if (!query[0]) return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");

        sqlite3_stmt *stmt;
        sqlite3_prepare_v2(STATE.db,
            "SELECT um.prompt, t.file_path, um.step_index "
            "FROM user_messages um JOIN trajectories t ON um.trajectory_fk = t.id "
            "WHERE um.prompt LIKE ? LIMIT 50", -1, &stmt, NULL);
        char pattern[1024];
        snprintf(pattern, sizeof(pattern), "%%%s%%", query);
        sqlite3_bind_text(stmt, 1, pattern, -1, SQLITE_TRANSIENT);

        int offset = 0;
        int match_count = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@OK]{[@COUNT]{0}");

        while (sqlite3_step(stmt) == SQLITE_ROW && offset < (int)out_sz - 512) {
            const char *prompt = (const char*)sqlite3_column_text(stmt, 0);
            const char *fpath = (const char*)sqlite3_column_text(stmt, 1);
            int step = sqlite3_column_int(stmt, 2);
            match_count++;
            offset += snprintf(bcl_out + offset, out_sz - offset,
                "[@MATCH]{[@STEP]{%d}[@FILE]{%s}[@TEXT]{%.200s}}",
                step, fpath ? fpath : "", prompt ? prompt : "");
        }
        /* Patch count */
        char count_str[32];
        snprintf(count_str, sizeof(count_str), "[@COUNT]{%d}", match_count);
        /* Overwrite the placeholder count */
        char *count_pos = strstr(bcl_out, "[@COUNT]{0}");
        if (count_pos) {
            int old_len = strlen("[@COUNT]{0}");
            int new_len = strlen(count_str);
            memmove(count_pos + new_len, count_pos + old_len, strlen(count_pos + old_len) + 1);
            memcpy(count_pos, count_str, new_len);
        }
        offset = strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "}");
        sqlite3_finalize(stmt);
        return 1;
    }
    
    if (strcmp(cmd, "stats") == 0) {
        if (!init_db()) return BclResult_Err(bcl_out, out_sz, 10, "db init failed");
        sqlite3_stmt *stmt;
        int traj_count = 0, user_count = 0, asst_count = 0, cmd_count = 0, cp_count = 0;
        sqlite3_prepare_v2(STATE.db, "SELECT COUNT(*) FROM trajectories", -1, &stmt, NULL);
        if (sqlite3_step(stmt) == SQLITE_ROW) traj_count = sqlite3_column_int(stmt, 0);
        sqlite3_finalize(stmt);
        sqlite3_prepare_v2(STATE.db, "SELECT COUNT(*) FROM user_messages", -1, &stmt, NULL);
        if (sqlite3_step(stmt) == SQLITE_ROW) user_count = sqlite3_column_int(stmt, 0);
        sqlite3_finalize(stmt);
        sqlite3_prepare_v2(STATE.db, "SELECT COUNT(*) FROM assistant_messages", -1, &stmt, NULL);
        if (sqlite3_step(stmt) == SQLITE_ROW) asst_count = sqlite3_column_int(stmt, 0);
        sqlite3_finalize(stmt);
        sqlite3_prepare_v2(STATE.db, "SELECT COUNT(*) FROM commands", -1, &stmt, NULL);
        if (sqlite3_step(stmt) == SQLITE_ROW) cmd_count = sqlite3_column_int(stmt, 0);
        sqlite3_finalize(stmt);
        sqlite3_prepare_v2(STATE.db, "SELECT COUNT(*) FROM checkpoints", -1, &stmt, NULL);
        if (sqlite3_step(stmt) == SQLITE_ROW) cp_count = sqlite3_column_int(stmt, 0);
        sqlite3_finalize(stmt);
        
        char body[512];
        snprintf(body, sizeof(body),
            "[@TRAJECTORIES]{%d}[@USER_MSGS]{%d}[@AI_MSGS]{%d}[@COMMANDS]{%d}[@CHECKPOINTS]{%d}[@SCANNED]{%d}[@LOADED]{%d}",
            traj_count, user_count, asst_count, cmd_count, cp_count,
            STATE.files_scanned, STATE.files_loaded);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@SCANNED]{%d}[@LOADED]{%d}[@DB]{%s}[@ERROR]{%s}",
            STATE.initialized, STATE.files_scanned, STATE.files_loaded,
            STATE.db ? "active" : "none",
            STATE.last_error[0] ? STATE.last_error : "none");
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char root[4096] = {0};
        BclParser_Extract(&parse, "ROOT", root, sizeof(root));
        BclParser_Free(&parse);
        if (root[0]) {
            strncpy(WINDSURF_ROOT, root, sizeof(WINDSURF_ROOT) - 1);
        }
        char body[4096];
        snprintf(body, sizeof(body), "[@ROOT]{%s}", WINDSURF_ROOT);
        return BclResult_Ok(bcl_out, out_sz, body);
    }
    
    return BclResult_Err(bcl_out, out_sz, 404, "unknown command");
}

int PbReader_Close(void) {
    if (STATE.db) {
        sqlite3_close(STATE.db);
        STATE.db = NULL;
    }
    STATE.initialized = 0;
    return 1;
}

const char * PbReader_State(void) {
    static char buf[512];
    snprintf(buf, sizeof(buf),
        "PbReader: initialized=%d scanned=%d loaded=%d db=%s",
        STATE.initialized, STATE.files_scanned, STATE.files_loaded,
        STATE.db ? "active" : "none");
    return buf;
}
