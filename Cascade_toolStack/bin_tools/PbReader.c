/*
 * ┌─────────────────────────────────────────────────────────────────┐
 * │ GHOST HEADER                                                    │
 * │ Author:    wws                                                  │
 * │ Domain:    pb chat decryption + search                          │
 * │ Language:  C (VBStyle-like adaptation)                          │
 * │ Standard:  POSIX + OpenSSL AES-256-GCM + SQLite in-RAM          │
 * │ Compile:   cc -O2 -I/opt/homebrew/opt/openssl@3/include \       │
 * │            PbReader.c -L/opt/homebrew/opt/openssl@3/lib \       │
 * │            -lcrypto -lsqlite3 -o PbReader                       │
 * └─────────────────────────────────────────────────────────────────┘
 */

/*
 * ┌─────────────────────────────────────────────────────────────────┐
 * │ VBSTYLE HEADER                                                  │
 * │ Run() dispatch entry point                                      │
 * │ Tuple3 (ok, data, error) returns                                │
 * │ state dict (struct, no globals for instance data)               │
 * │ No decorators (N/A in C)                                        │
 * │ No print — Report method returns strings                        │
 * │ No hardcoded paths — windsurf root from HOME env                │
 * │ PascalCase class and method names                               │
 * │ UPPERCASE constants at class level                              │
 * │ One class, one domain: pb chat decryption + search              │
 * │ Self-documenting: schema is code registry                       │
 * └─────────────────────────────────────────────────────────────────┘
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <dirent.h>
#include <sys/stat.h>
#include <errno.h>
#include <limits.h>
#include <sqlite3.h>
#include <openssl/evp.h>

/* ════════════════════════════════════════════════════════════════
 * UPPERCASE CONSTANTS (class level)
 * ════════════════════════════════════════════════════════════════ */

/* AES-256-GCM key — hardcoded in language_server_macos_arm binary */
static const unsigned char AES_KEY[32] = {
    0x73, 0x61, 0x66, 0x65, 0x43, 0x6f, 0x64, 0x65,
    0x69, 0x75, 0x6d, 0x77, 0x6f, 0x72, 0x6c, 0x64,
    0x4b, 0x65, 0x59, 0x73, 0x65, 0x63, 0x72, 0x65,
    0x74, 0x42, 0x61, 0x6c, 0x6c, 0x6f, 0x6f, 0x6e
};
/* = "safeCodeiumworldKeYsecretBalloon" */

static const int NONCE_SIZE = 12;
static const int TAG_SIZE   = 16;

/* .pb file directories under ~/.codeium/windsurf/ */
static const char* PB_DIRS[] = {"cascade", "implicit", "memories"};
static const int   PB_DIRS_COUNT = 3;

/* Protobuf wire types */
static const int WIRE_VARINT  = 0;
static const int WIRE_64BIT   = 1;
static const int WIRE_LENGTH  = 2;
static const int WIRE_32BIT   = 5;

/* CortexTrajectoryStep variant field numbers */
static const int VARIANT_USER_INPUT       = 19;
static const int VARIANT_PLANNER_RESPONSE = 20;
static const int VARIANT_RUN_COMMAND      = 28;
static const int VARIANT_CHECKPOINT       = 30;

/* Dispatch keys */
static const char* CMD_SCAN    = "scan";
static const char* CMD_LIST    = "list";
static const char* CMD_LOAD    = "load";
static const char* CMD_READ    = "read";
static const char* CMD_SEARCH  = "search";
static const char* CMD_STATS   = "stats";
static const char* CMD_STATE   = "state";
static const char* CMD_RESET   = "reset";

/* Error codes */
static const char* ERR_OK       = "OK";
static const char* ERR_BADCMD   = "BADCMD";
static const char* ERR_NOPATH   = "NOPATH";
static const char* ERR_INTERNAL = "INTERNAL";
static const char* ERR_DB       = "DBERROR";
static const char* ERR_DECRYPT  = "DECRYPT_FAILED";
static const char* ERR_FILE     = "FILE_ERROR";

/* ════════════════════════════════════════════════════════════════
 * Tuple3 — (ok, data, error)
 * ════════════════════════════════════════════════════════════════ */

typedef struct {
    const char* code;
    char        desc[512];
    int         zero;
} ErrorTuple;

typedef struct {
    int       ok;
    void*     data;
    ErrorTuple error;
} Tuple3;

static Tuple3 Tuple3_OK(void* data) {
    Tuple3 t;
    t.ok = 1;
    t.data = data;
    t.error.code = ERR_OK;
    t.error.desc[0] = '\0';
    t.error.zero = 0;
    return t;
}

static Tuple3 Tuple3_Error(const char* code, const char* desc) {
    Tuple3 t;
    t.ok = 0;
    t.data = NULL;
    t.error.code = code;
    snprintf(t.error.desc, sizeof(t.error.desc), "%s", desc ? desc : "");
    t.error.zero = 0;
    return t;
}

/* ════════════════════════════════════════════════════════════════
 * Protobuf wire-format parser (standalone, no .proto needed)
 * ════════════════════════════════════════════════════════════════ */

typedef struct {
    int   field_no;
    int   wire_type;
    int   value_offset;
    int   value_length;   /* for length-delimited */
    long  varint_value;   /* for varints */
} PbField;

/* Read a varint. Return (value, new_pos). */
static long pb_read_varint(const unsigned char* buf, int buf_len, int pos, int* out_pos) {
    long val = 0;
    int shift = 0;
    while (pos < buf_len) {
        unsigned char b = buf[pos];
        pos++;
        val |= ((long)(b & 0x7F)) << shift;
        if (!(b & 0x80)) {
            *out_pos = pos;
            return val;
        }
        shift += 7;
    }
    *out_pos = pos;
    return val;
}

/* Parse a tag. Return (field_no, wire_type). */
static void pb_parse_tag(long tag, int* field_no, int* wire_type) {
    *field_no = (int)(tag >> 3);
    *wire_type = (int)(tag & 7);
}

/* Skip a single field value. Return new pos. */
static int pb_skip_value(const unsigned char* buf, int buf_len, int pos, int wire_type) {
    if (wire_type == WIRE_VARINT) {
        int dummy;
        return pb_read_varint(buf, buf_len, pos, &dummy);
    } else if (wire_type == WIRE_64BIT) {
        return pos + 8;
    } else if (wire_type == WIRE_LENGTH) {
        int len;
        int p = pb_read_varint(buf, buf_len, pos, &len);
        return p + len;
    } else if (wire_type == WIRE_32BIT) {
        return pos + 4;
    }
    return pos;
}

/* Read a string field at given field number from a message buffer. */
static int pb_read_string_field(const unsigned char* buf, int buf_len,
                                 int target_fno, char* out, int out_max) {
    int pos = 0;
    while (pos < buf_len) {
        int tag_pos;
        long tag = pb_read_varint(buf, buf_len, pos, &tag_pos);
        pos = tag_pos;
        int fno, wt;
        pb_parse_tag(tag, &fno, &wt);
        if (wt == WIRE_VARINT) {
            int vp;
            pb_read_varint(buf, buf_len, pos, &vp);
            pos = vp;
        } else if (wt == WIRE_64BIT) {
            pos += 8;
        } else if (wt == WIRE_LENGTH) {
            int len;
            int lp = pb_read_varint(buf, buf_len, pos, &len);
            if (fno == target_fno) {
                int copy_len = len < (out_max - 1) ? len : (out_max - 1);
                memcpy(out, buf + lp, copy_len);
                out[copy_len] = '\0';
                return 1;
            }
            pos = lp + len;
        } else if (wt == WIRE_32BIT) {
            pos += 4;
        } else {
            break;
        }
    }
    return 0;
}

/* ════════════════════════════════════════════════════════════════
 * Trajectory parsing
 * ════════════════════════════════════════════════════════════════ */

typedef struct {
    char trajectory_id[256];
    char cascade_id[256];
    int  steps_count;
    /* steps stored as offsets+lengths into the plaintext buffer */
    int  step_offsets[8192];
    int  step_lengths[8192];
} TrajectoryInfo;

/* Parse top-level CortexTrajectory. */
static void parse_trajectory(const unsigned char* buf, int buf_len, TrajectoryInfo* info) {
    memset(info, 0, sizeof(TrajectoryInfo));
    int pos = 0;
    while (pos < buf_len) {
        int tag_pos;
        long tag = pb_read_varint(buf, buf_len, pos, &tag_pos);
        pos = tag_pos;
        int fno, wt;
        pb_parse_tag(tag, &fno, &wt);

        if (wt == WIRE_VARINT) {
            int vp;
            long val = pb_read_varint(buf, buf_len, pos, &vp);
            pos = vp;
            /* skip varint fields we don't need */
        } else if (wt == WIRE_64BIT) {
            pos += 8;
        } else if (wt == WIRE_LENGTH) {
            int len;
            int lp = pb_read_varint(buf, buf_len, pos, &len);
            if (fno == 1) {
                /* trajectory_id (string) */
                int copy_len = len < 255 ? len : 255;
                memcpy(info->trajectory_id, buf + lp, copy_len);
                info->trajectory_id[copy_len] = '\0';
            } else if (fno == 6) {
                /* cascade_id (string) */
                int copy_len = len < 255 ? len : 255;
                memcpy(info->cascade_id, buf + lp, copy_len);
                info->cascade_id[copy_len] = '\0';
            } else if (fno == 2) {
                /* step (repeated) */
                if (info->steps_count < 8192) {
                    info->step_offsets[info->steps_count] = lp;
                    info->step_lengths[info->steps_count] = len;
                    info->steps_count++;
                }
            }
            pos = lp + len;
        } else if (wt == WIRE_32BIT) {
            pos += 4;
        } else {
            break;
        }
    }
}

/* Parse a single step. Returns variant_field and variant_data offset+length. */
static void parse_step(const unsigned char* buf, int buf_len,
                       int* out_type, int* out_variant_field,
                       int* out_variant_offset, int* out_variant_length) {
    int pos = 0;
    *out_type = -1;
    *out_variant_field = -1;
    *out_variant_offset = 0;
    *out_variant_length = 0;
    int found_variant = 0;

    while (pos < buf_len) {
        int tag_pos;
        long tag = pb_read_varint(buf, buf_len, pos, &tag_pos);
        pos = tag_pos;
        int fno, wt;
        pb_parse_tag(tag, &fno, &wt);

        if (wt == WIRE_VARINT) {
            int vp;
            long val = pb_read_varint(buf, buf_len, pos, &vp);
            pos = vp;
            if (fno == 1) *out_type = (int)val;
        } else if (wt == WIRE_64BIT) {
            pos += 8;
        } else if (wt == WIRE_LENGTH) {
            int len;
            int lp = pb_read_varint(buf, buf_len, pos, &len);
            if (fno >= 7 && fno <= 110 && !found_variant) {
                *out_variant_field = fno;
                *out_variant_offset = lp;
                *out_variant_length = len;
                found_variant = 1;
            }
            pos = lp + len;
        } else if (wt == WIRE_32BIT) {
            pos += 4;
        } else {
            break;
        }
    }
}

/* ════════════════════════════════════════════════════════════════
 * AES-256-GCM Decryption
 * ════════════════════════════════════════════════════════════════
 *
 * File layout: [12-byte nonce][ciphertext][16-byte GCM tag]
 * OpenSSL expects: nonce, then ciphertext+tag concatenated, tag at end.
 * ════════════════════════════════════════════════════════════════ */

static int decrypt_aes_gcm(const unsigned char* input, int input_len,
                           unsigned char* output, int output_max) {
    if (input_len < NONCE_SIZE + TAG_SIZE) {
        return -1;
    }

    const unsigned char* nonce = input;
    const unsigned char* ct_and_tag = input + NONCE_SIZE;
    int ct_len = input_len - NONCE_SIZE;  /* includes tag */

    EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
    if (!ctx) return -2;

    int ret = -3;
    int out_len = 0;
    int final_len = 0;

    if (EVP_DecryptInit_ex(ctx, EVP_aes_256_gcm(), NULL, NULL, NULL) != 1) goto cleanup;
    if (EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_IVLEN, NONCE_SIZE, NULL) != 1) goto cleanup;
    if (EVP_DecryptInit_ex(ctx, NULL, NULL, AES_KEY, nonce) != 1) goto cleanup;

    if (EVP_DecryptUpdate(ctx, output, &out_len, ct_and_tag, ct_len - TAG_SIZE) != 1) goto cleanup;

    /* Set GCM tag (last 16 bytes) */
    if (EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_TAG, TAG_SIZE,
                            (void*)(ct_and_tag + ct_len - TAG_SIZE)) != 1) goto cleanup;

    if (EVP_DecryptFinal_ex(ctx, output + out_len, &final_len) != 1) goto cleanup;

    ret = out_len + final_len;

cleanup:
    EVP_CIPHER_CTX_free(ctx);
    return ret;
}

/* ════════════════════════════════════════════════════════════════
 * CLASSES HEADER
 * PbReader — domain: pb chat decryption + search
 *   One class, one domain. Decrypts .pb files, parses protobuf,
 *   stores in in-RAM SQLite, provides CLI search/read.
 * ════════════════════════════════════════════════════════════════ */

typedef struct {
    char home[PATH_MAX];
    char windsurf_root[PATH_MAX];
    sqlite3* db;
    int loaded_count;
    int scan_count;
    char report[16384];
    int report_len;
} PbReaderState;

typedef struct {
    PbReaderState state;
} PbReader;

/* ── Init ─────────────────────────────────────────────────────── */

static Tuple3 PbReader_Init(PbReader* self) {
    memset(self, 0, sizeof(PbReader));
    const char* home = getenv("HOME");
    if (!home) home = "/tmp";
    snprintf(self->state.home, sizeof(self->state.home), "%s", home);
    snprintf(self->state.windsurf_root, sizeof(self->state.windsurf_root),
             "%s/.codeium/windsurf", home);

    /* Init persistent on-disk SQLite (survives across CLI invocations) */
    char db_path[PATH_MAX];
    snprintf(db_path, sizeof(db_path), "%s/.codeium/windsurf/pb_reader.db", self->state.home);
    int rc = sqlite3_open(db_path, &self->state.db);
    if (rc != SQLITE_OK) {
        return Tuple3_Error(ERR_DB, "cannot open SQLite");
    }

    const char* schema =
        "CREATE TABLE IF NOT EXISTS trajectories ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  trajectory_id TEXT,"
        "  cascade_id TEXT,"
        "  file_path TEXT UNIQUE,"
        "  file_category TEXT,"
        "  steps_count INTEGER,"
        "  decrypted_size INTEGER"
        ");"
        "CREATE TABLE IF NOT EXISTS user_messages ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  trajectory_fk INTEGER,"
        "  step_index INTEGER,"
        "  prompt TEXT,"
        "  FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id)"
        ");"
        "CREATE TABLE IF NOT EXISTS assistant_messages ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  trajectory_fk INTEGER,"
        "  step_index INTEGER,"
        "  user_facing TEXT,"
        "  FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id)"
        ");"
        "CREATE TABLE IF NOT EXISTS commands ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  trajectory_fk INTEGER,"
        "  step_index INTEGER,"
        "  command TEXT,"
        "  FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id)"
        ");"
        "CREATE INDEX IF NOT EXISTS idx_um_traj ON user_messages(trajectory_fk);"
        "CREATE INDEX IF NOT EXISTS idx_am_traj ON assistant_messages(trajectory_fk);"
        "CREATE INDEX IF NOT EXISTS idx_cmd_traj ON commands(trajectory_fk);";

    rc = sqlite3_exec(self->state.db, schema, NULL, NULL, NULL);
    if (rc != SQLITE_OK) {
        return Tuple3_Error(ERR_DB, sqlite3_errmsg(self->state.db));
    }

    return Tuple3_OK(NULL);
}

/* ── Decrypt + Load one file ──────────────────────────────────── */

static Tuple3 PbReader_LoadFile(PbReader* self, const char* filepath, const char* category) {
    /* Read file */
    FILE* f = fopen(filepath, "rb");
    if (!f) {
        return Tuple3_Error(ERR_FILE, filepath);
    }
    fseek(f, 0, SEEK_END);
    long fsize = ftell(f);
    fseek(f, 0, SEEK_SET);
    unsigned char* input = malloc(fsize);
    if (!input) { fclose(f); return Tuple3_Error(ERR_INTERNAL, "malloc failed"); }
    fread(input, 1, fsize, f);
    fclose(f);

    /* Decrypt */
    unsigned char* plaintext = malloc(fsize);  /* plaintext <= ciphertext */
    if (!plaintext) { free(input); return Tuple3_Error(ERR_INTERNAL, "malloc failed"); }

    int pt_len = decrypt_aes_gcm(input, (int)fsize, plaintext, (int)fsize);
    free(input);

    if (pt_len < 0) {
        free(plaintext);
        char err[600];
        snprintf(err, sizeof(err), "decrypt failed (%d) for %s", pt_len, filepath);
        return Tuple3_Error(ERR_DECRYPT, err);
    }

    /* Parse trajectory */
    TrajectoryInfo info;
    parse_trajectory(plaintext, pt_len, &info);

    /* Handle ImplicitTrajectory (wraps CortexTrajectory in field 1) */
    if (info.steps_count == 0 && info.trajectory_id[0] == '\0') {
        int pos = 0;
        while (pos < pt_len) {
            int tag_pos;
            long tag = pb_read_varint(plaintext, pt_len, pos, &tag_pos);
            pos = tag_pos;
            int fno, wt;
            pb_parse_tag(tag, &fno, &wt);
            if (wt == WIRE_LENGTH) {
                int len;
                int lp = pb_read_varint(plaintext, pt_len, pos, &len);
                if (fno == 1) {
                    parse_trajectory(plaintext + lp, len, &info);
                }
                pos = lp + len;
            } else if (wt == WIRE_VARINT) {
                int vp;
                pb_read_varint(plaintext, pt_len, pos, &vp);
                pos = vp;
            } else if (wt == WIRE_64BIT) {
                pos += 8;
            } else if (wt == WIRE_32BIT) {
                pos += 4;
            } else {
                break;
            }
        }
    }

    /* Insert into DB */
    sqlite3* db = self->state.db;
    sqlite3_stmt* stmt;

    sqlite3_prepare_v2(db, "INSERT OR REPLACE INTO trajectories "
        "(trajectory_id, cascade_id, file_path, file_category, steps_count, decrypted_size) "
        "VALUES (?,?,?,?,?,?)", -1, &stmt, NULL);
    sqlite3_bind_text(stmt, 1, info.trajectory_id, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, info.cascade_id, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, filepath, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 4, category, -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 5, info.steps_count);
    sqlite3_bind_int(stmt, 6, pt_len);
    sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    long fk = sqlite3_last_insert_rowid(db);

    /* Parse and insert steps */
    char prompt[65536];
    char user_facing[65536];
    char cmd_str[8192];

    for (int i = 0; i < info.steps_count; i++) {
        int off = info.step_offsets[i];
        int len = info.step_lengths[i];
        if (off + len > pt_len) break;

        int step_type, vf, voff, vlen;
        parse_step(plaintext + off, len, &step_type, &vf, &voff, &vlen);

        if (vf == VARIANT_USER_INPUT && vlen > 0) {
            prompt[0] = '\0';
            pb_read_string_field(plaintext + off + voff, vlen, 2, prompt, sizeof(prompt));
            sqlite3_prepare_v2(db, "INSERT INTO user_messages (trajectory_fk, step_index, prompt) VALUES (?,?,?)", -1, &stmt, NULL);
            sqlite3_bind_int64(stmt, 1, fk);
            sqlite3_bind_int(stmt, 2, i);
            sqlite3_bind_text(stmt, 3, prompt, -1, SQLITE_TRANSIENT);
            sqlite3_step(stmt);
            sqlite3_finalize(stmt);
        } else if (vf == VARIANT_PLANNER_RESPONSE && vlen > 0) {
            user_facing[0] = '\0';
            pb_read_string_field(plaintext + off + voff, vlen, 1, user_facing, sizeof(user_facing));
            sqlite3_prepare_v2(db, "INSERT INTO assistant_messages (trajectory_fk, step_index, user_facing) VALUES (?,?,?)", -1, &stmt, NULL);
            sqlite3_bind_int64(stmt, 1, fk);
            sqlite3_bind_int(stmt, 2, i);
            sqlite3_bind_text(stmt, 3, user_facing, -1, SQLITE_TRANSIENT);
            sqlite3_step(stmt);
            sqlite3_finalize(stmt);
        } else if (vf == VARIANT_RUN_COMMAND && vlen > 0) {
            cmd_str[0] = '\0';
            pb_read_string_field(plaintext + off + voff, vlen, 23, cmd_str, sizeof(cmd_str));
            sqlite3_prepare_v2(db, "INSERT INTO commands (trajectory_fk, step_index, command) VALUES (?,?,?)", -1, &stmt, NULL);
            sqlite3_bind_int64(stmt, 1, fk);
            sqlite3_bind_int(stmt, 2, i);
            sqlite3_bind_text(stmt, 3, cmd_str, -1, SQLITE_TRANSIENT);
            sqlite3_step(stmt);
            sqlite3_finalize(stmt);
        }
    }

    free(plaintext);
    self->state.loaded_count++;

    char msg[512];
    snprintf(msg, sizeof(msg), "Loaded: %s (%d steps, %d bytes) — %s",
             info.trajectory_id[0] ? info.trajectory_id : "?",
             info.steps_count, pt_len, filepath);
    return Tuple3_OK(strdup(msg));
}

/* ── Scan command ─────────────────────────────────────────────── */

static Tuple3 PbReader_Scan(PbReader* self) {
    DIR* d;
    struct dirent* entry;
    int count = 0;
    char report[16384];
    int rlen = 0;

    rlen += snprintf(report + rlen, sizeof(report) - rlen, "Scanning %s\n", self->state.windsurf_root);

    for (int i = 0; i < PB_DIRS_COUNT; i++) {
        char dirpath[PATH_MAX];
        snprintf(dirpath, sizeof(dirpath), "%s/%s", self->state.windsurf_root, PB_DIRS[i]);
        d = opendir(dirpath);
        if (!d) continue;

        while ((entry = readdir(d)) != NULL) {
            if (strstr(entry->d_name, ".pb") == NULL) continue;
            char fullpath[PATH_MAX];
            snprintf(fullpath, sizeof(fullpath), "%s/%s", dirpath, entry->d_name);
            struct stat st;
            if (stat(fullpath, &st) == 0) {
                rlen += snprintf(report + rlen, sizeof(report) - rlen,
                                 "  [%s] %s (%lld KB)\n",
                                 PB_DIRS[i], entry->d_name, (long long)st.st_size / 1024);
                count++;
            }
        }
        closedir(d);
    }

    rlen += snprintf(report + rlen, sizeof(report) - rlen, "\nTotal: %d .pb files\n", count);
    self->state.scan_count = count;
    return Tuple3_OK(strdup(report));
}

/* ── List command ─────────────────────────────────────────────── */

static Tuple3 PbReader_List(PbReader* self) {
    sqlite3* db = self->state.db;
    sqlite3_stmt* stmt;
    char report[16384];
    int rlen = 0;

    rlen += snprintf(report + rlen, sizeof(report) - rlen, "Loaded trajectories (%d):\n", self->state.loaded_count);

    sqlite3_prepare_v2(db,
        "SELECT t.id, t.trajectory_id, t.file_category, t.steps_count, "
        "(SELECT COUNT(*) FROM user_messages WHERE trajectory_fk = t.id), "
        "(SELECT COUNT(*) FROM assistant_messages WHERE trajectory_fk = t.id), "
        "(SELECT COUNT(*) FROM commands WHERE trajectory_fk = t.id) "
        "FROM trajectories t ORDER BY t.id", -1, &stmt, NULL);

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        long id = sqlite3_column_int64(stmt, 0);
        const char* tid = (const char*)sqlite3_column_text(stmt, 1);
        const char* cat = (const char*)sqlite3_column_text(stmt, 2);
        int steps = sqlite3_column_int(stmt, 3);
        int um = sqlite3_column_int(stmt, 4);
        int am = sqlite3_column_int(stmt, 5);
        int cmds = sqlite3_column_int(stmt, 6);
        rlen += snprintf(report + rlen, sizeof(report) - rlen,
                         "  [%s] #%ld %s — %d steps, %d user, %d ai, %d cmds\n",
                         cat ? cat : "?", id, tid ? tid : "?", steps, um, am, cmds);
    }
    sqlite3_finalize(stmt);

    return Tuple3_OK(strdup(report));
}

/* ── Read command ─────────────────────────────────────────────── */

static Tuple3 PbReader_Read(PbReader* self, const char* filepath) {
    /* Check if loaded, if not auto-load */
    sqlite3* db = self->state.db;
    sqlite3_stmt* stmt;

    sqlite3_prepare_v2(db, "SELECT id FROM trajectories WHERE file_path = ?", -1, &stmt, NULL);
    sqlite3_bind_text(stmt, 1, filepath, -1, SQLITE_TRANSIENT);
    int found = (sqlite3_step(stmt) == SQLITE_ROW);
    long fk = found ? sqlite3_column_int64(stmt, 0) : 0;
    sqlite3_finalize(stmt);

    if (!found) {
        const char* category = "unknown";
        for (int i = 0; i < PB_DIRS_COUNT; i++) {
            if (strstr(filepath, PB_DIRS[i])) { category = PB_DIRS[i]; break; }
        }
        Tuple3 load_result = PbReader_LoadFile(self, filepath, category);
        if (!load_result.ok) return load_result;
        free(load_result.data);
        sqlite3_prepare_v2(db, "SELECT id FROM trajectories WHERE file_path = ?", -1, &stmt, NULL);
        sqlite3_bind_text(stmt, 1, filepath, -1, SQLITE_TRANSIENT);
        if (sqlite3_step(stmt) == SQLITE_ROW) fk = sqlite3_column_int64(stmt, 0);
        sqlite3_finalize(stmt);
    }

    /* Get trajectory info */
    sqlite3_prepare_v2(db, "SELECT trajectory_id, cascade_id, steps_count FROM trajectories WHERE id = ?", -1, &stmt, NULL);
    sqlite3_bind_int64(stmt, 1, fk);
    sqlite3_step(stmt);
    const char* traj_id = (const char*)sqlite3_column_text(stmt, 0);
    const char* cascade_id = (const char*)sqlite3_column_text(stmt, 1);
    int steps_count = sqlite3_column_int(stmt, 2);

    char* report = malloc(65536);
    int rlen = 0;
    rlen += snprintf(report + rlen, 65536 - rlen,
                     "====== TRAJECTORY: %s ======\nCASCADE: %s\nSTEPS: %d\n======\n",
                     traj_id ? traj_id : "?", cascade_id ? cascade_id : "?", steps_count);
    sqlite3_finalize(stmt);

    /* Get user messages */
    sqlite3_prepare_v2(db, "SELECT step_index, prompt FROM user_messages WHERE trajectory_fk = ? ORDER BY step_index", -1, &stmt, NULL);
    sqlite3_bind_int64(stmt, 1, fk);
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        int si = sqlite3_column_int(stmt, 0);
        const char* prompt = (const char*)sqlite3_column_text(stmt, 1);
        rlen += snprintf(report + rlen, 65536 - rlen,
                         "\n--- USER (step %d) ---\n%s\n", si, prompt ? prompt : "");
    }
    sqlite3_finalize(stmt);

    /* Get assistant messages */
    sqlite3_prepare_v2(db, "SELECT step_index, user_facing FROM assistant_messages WHERE trajectory_fk = ? ORDER BY step_index", -1, &stmt, NULL);
    sqlite3_bind_int64(stmt, 1, fk);
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        int si = sqlite3_column_int(stmt, 0);
        const char* text = (const char*)sqlite3_column_text(stmt, 1);
        rlen += snprintf(report + rlen, 65536 - rlen,
                         "\n--- ASSISTANT (step %d) ---\n%s\n", si, text ? text : "(no text)");
    }
    sqlite3_finalize(stmt);

    /* Get commands */
    sqlite3_prepare_v2(db, "SELECT step_index, command FROM commands WHERE trajectory_fk = ? ORDER BY step_index", -1, &stmt, NULL);
    sqlite3_bind_int64(stmt, 1, fk);
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        int si = sqlite3_column_int(stmt, 0);
        const char* cmd = (const char*)sqlite3_column_text(stmt, 1);
        rlen += snprintf(report + rlen, 65536 - rlen,
                         "\n  [CMD] (step %d): %s\n", si, cmd ? cmd : "");
    }
    sqlite3_finalize(stmt);

    return Tuple3_OK(report);
}

/* ── Search command ───────────────────────────────────────────── */

static Tuple3 PbReader_Search(PbReader* self, const char* query) {
    sqlite3* db = self->state.db;
    sqlite3_stmt* stmt;
    char* report = malloc(65536);
    int rlen = 0;
    int match_count = 0;

    char like[1024];
    snprintf(like, sizeof(like), "%%%s%%", query);

    /* Search user messages */
    sqlite3_prepare_v2(db,
        "SELECT t.trajectory_id, um.step_index, um.prompt "
        "FROM user_messages um JOIN trajectories t ON um.trajectory_fk = t.id "
        "WHERE um.prompt LIKE ? ORDER BY t.id, um.step_index", -1, &stmt, NULL);
    sqlite3_bind_text(stmt, 1, like, -1, SQLITE_TRANSIENT);
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        const char* tid = (const char*)sqlite3_column_text(stmt, 0);
        int si = sqlite3_column_int(stmt, 1);
        const char* text = (const char*)sqlite3_column_text(stmt, 2);
        rlen += snprintf(report + rlen, 65536 - rlen,
                         "[USER] traj=%s step=%d\n  %.200s\n\n",
                         tid ? tid : "?", si, text ? text : "");
        match_count++;
    }
    sqlite3_finalize(stmt);

    /* Search assistant messages */
    sqlite3_prepare_v2(db,
        "SELECT t.trajectory_id, am.step_index, am.user_facing "
        "FROM assistant_messages am JOIN trajectories t ON am.trajectory_fk = t.id "
        "WHERE am.user_facing LIKE ? ORDER BY t.id, am.step_index", -1, &stmt, NULL);
    sqlite3_bind_text(stmt, 1, like, -1, SQLITE_TRANSIENT);
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        const char* tid = (const char*)sqlite3_column_text(stmt, 0);
        int si = sqlite3_column_int(stmt, 1);
        const char* text = (const char*)sqlite3_column_text(stmt, 2);
        rlen += snprintf(report + rlen, 65536 - rlen,
                         "[AI] traj=%s step=%d\n  %.200s\n\n",
                         tid ? tid : "?", si, text ? text : "");
        match_count++;
    }
    sqlite3_finalize(stmt);

    /* Search commands */
    sqlite3_prepare_v2(db,
        "SELECT t.trajectory_id, c.step_index, c.command "
        "FROM commands c JOIN trajectories t ON c.trajectory_fk = t.id "
        "WHERE c.command LIKE ? ORDER BY t.id, c.step_index", -1, &stmt, NULL);
    sqlite3_bind_text(stmt, 1, like, -1, SQLITE_TRANSIENT);
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        const char* tid = (const char*)sqlite3_column_text(stmt, 0);
        int si = sqlite3_column_int(stmt, 1);
        const char* text = (const char*)sqlite3_column_text(stmt, 2);
        rlen += snprintf(report + rlen, 65536 - rlen,
                         "[CMD] traj=%s step=%d\n  %.200s\n\n",
                         tid ? tid : "?", si, text ? text : "");
        match_count++;
    }
    sqlite3_finalize(stmt);

    if (match_count == 0) {
        free(report);
        return Tuple3_OK(strdup("No matches found.\n"));
    }

    /* Prepend count */
    char* final_report = malloc(rlen + 256);
    int prefix = snprintf(final_report, rlen + 256, "Found %d matches for '%s':\n\n", match_count, query);
    memcpy(final_report + prefix, report, rlen);
    final_report[prefix + rlen] = '\0';
    free(report);
    return Tuple3_OK(final_report);
}

/* ── Stats command ────────────────────────────────────────────── */

static Tuple3 PbReader_Stats(PbReader* self) {
    sqlite3* db = self->state.db;
    char report[4096];
    int rlen = 0;

    int traj_count = 0, um_count = 0, am_count = 0, cmd_count = 0;
    sqlite3_stmt* stmt;

    sqlite3_prepare_v2(db, "SELECT COUNT(*) FROM trajectories", -1, &stmt, NULL);
    if (sqlite3_step(stmt) == SQLITE_ROW) traj_count = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);

    sqlite3_prepare_v2(db, "SELECT COUNT(*) FROM user_messages", -1, &stmt, NULL);
    if (sqlite3_step(stmt) == SQLITE_ROW) um_count = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);

    sqlite3_prepare_v2(db, "SELECT COUNT(*) FROM assistant_messages", -1, &stmt, NULL);
    if (sqlite3_step(stmt) == SQLITE_ROW) am_count = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);

    sqlite3_prepare_v2(db, "SELECT COUNT(*) FROM commands", -1, &stmt, NULL);
    if (sqlite3_step(stmt) == SQLITE_ROW) cmd_count = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);

    rlen += snprintf(report + rlen, sizeof(report) - rlen,
                     "RAM DB Statistics:\n  trajectories: %d\n  user_messages: %d\n  assistant_messages: %d\n  commands: %d\n  loaded_files: %d\n  scan_count: %d\n",
                     traj_count, um_count, am_count, cmd_count, self->state.loaded_count, self->state.scan_count);

    return Tuple3_OK(strdup(report));
}

/* ── State command ────────────────────────────────────────────── */

static Tuple3 PbReader_State(PbReader* self) {
    char report[4096];
    snprintf(report, sizeof(report),
             "PbReader State:\n  home: %s\n  windsurf_root: %s\n  loaded_count: %d\n  scan_count: %d\n  db: %s\n",
             self->state.home, self->state.windsurf_root,
             self->state.loaded_count, self->state.scan_count,
             self->state.db ? "connected" : "NULL");
    return Tuple3_OK(strdup(report));
}

/* ── Reset command ────────────────────────────────────────────── */

static Tuple3 PbReader_Reset(PbReader* self) {
    sqlite3* db = self->state.db;
    sqlite3_exec(db, "DELETE FROM user_messages", NULL, NULL, NULL);
    sqlite3_exec(db, "DELETE FROM assistant_messages", NULL, NULL, NULL);
    sqlite3_exec(db, "DELETE FROM commands", NULL, NULL, NULL);
    sqlite3_exec(db, "DELETE FROM trajectories", NULL, NULL, NULL);
    self->state.loaded_count = 0;
    return Tuple3_OK(strdup("DB cleared — all tables emptied.\n"));
}

/* ════════════════════════════════════════════════════════════════
 * METHOD HEADER
 * PbReader_Dispatch — internal dispatch
 * ════════════════════════════════════════════════════════════════ */

static Tuple3 PbReader_Dispatch(PbReader* self, const char* command, int argc, char** argv) {
    if (strcmp(command, CMD_SCAN) == 0) {
        return PbReader_Scan(self);
    }
    else if (strcmp(command, CMD_LIST) == 0) {
        return PbReader_List(self);
    }
    else if (strcmp(command, CMD_LOAD) == 0) {
        if (argc < 3) return Tuple3_Error(ERR_BADCMD, "usage: load <file.pb>");
        const char* category = "unknown";
        for (int i = 0; i < PB_DIRS_COUNT; i++) {
            if (strstr(argv[2], PB_DIRS[i])) { category = PB_DIRS[i]; break; }
        }
        return PbReader_LoadFile(self, argv[2], category);
    }
    else if (strcmp(command, CMD_READ) == 0) {
        if (argc < 3) return Tuple3_Error(ERR_BADCMD, "usage: read <file.pb>");
        return PbReader_Read(self, argv[2]);
    }
    else if (strcmp(command, CMD_SEARCH) == 0) {
        if (argc < 3) return Tuple3_Error(ERR_BADCMD, "usage: search <query>");
        return PbReader_Search(self, argv[2]);
    }
    else if (strcmp(command, CMD_STATS) == 0) {
        return PbReader_Stats(self);
    }
    else if (strcmp(command, CMD_STATE) == 0) {
        return PbReader_State(self);
    }
    else if (strcmp(command, CMD_RESET) == 0) {
        return PbReader_Reset(self);
    }
    else {
        return Tuple3_Error(ERR_BADCMD, command);
    }
}

/* ════════════════════════════════════════════════════════════════
 * METHOD HEADER
 * PbReader_Run — dispatch entry point
 * ════════════════════════════════════════════════════════════════ */

static Tuple3 PbReader_Run(PbReader* self, const char* command, int argc, char** argv) {
    if (!self || !command)
        return Tuple3_Error(ERR_INTERNAL, "self or command is NULL");
    return PbReader_Dispatch(self, command, argc, argv);
}

/* ════════════════════════════════════════════════════════════════
 * MAIN — CLI wrapper around the PbReader class
 *   Usage: PbReader <command> [args...]
 *   Commands:
 *     scan                  list all .pb files in ~/.codeium/windsurf/
 *     list                  list loaded trajectories in RAM
 *     load <file.pb>        load one .pb file into RAM
 *     read <file.pb>        read chat conversation
 *     search <query>        search loaded chat content
 *     stats                 show RAM DB statistics
 *     state                 show state snapshot
 * ════════════════════════════════════════════════════════════════ */

int main(int argc, char** argv) {
    if (argc < 2) {
        fprintf(stderr,
            "Usage: %s <scan|list|load|read|search|stats|state|reset> [args...]\n"
            "\n"
            "Commands:\n"
            "  scan                  list all .pb files\n"
            "  list                  list loaded trajectories\n"
            "  load <file.pb>        load one .pb file\n"
            "  read <file.pb>        read chat conversation\n"
            "  search <query>        search loaded chats\n"
            "  stats                 DB statistics\n"
            "  state                 state snapshot\n"
            "  reset                 clear DB (re-load from scratch)\n",
            argv[0]);
        return 1;
    }

    PbReader reader;
    Tuple3 init_result = PbReader_Init(&reader);
    if (!init_result.ok) {
        fprintf(stderr, "ERROR: %s — %s\n",
                init_result.error.code,
                init_result.error.desc[0] ? init_result.error.desc : "");
        return 1;
    }

    const char* command = argv[1];
    Tuple3 result = PbReader_Run(&reader, command, argc, argv);

    if (!result.ok) {
        fprintf(stderr, "ERROR: %s — %s\n",
                result.error.code,
                result.error.desc[0] ? result.error.desc : "");
        if (reader.state.db) sqlite3_close(reader.state.db);
        return 1;
    }

    /* Print result data (report method returns string, main prints) */
    if (result.data) {
        printf("%s", (const char*)result.data);
        free(result.data);
    }

    if (reader.state.db) sqlite3_close(reader.state.db);
    return 0;
}
