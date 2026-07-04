//[@GHOST]{file_path="core/Dom_Bcl_C_ver/bcl_mem_unit.c" date="2026-06-29" author="cascade+devin" session_id="bcl-c-central-db" context="BCL C Engine Layer 2 — in-RAM SQLite :memory: orchestration bus. One C file, one connection, 6 tables, 6 sections. Central dispatch — no direct unit-to-unit calls."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_mem_unit.c" domain="bcl_c_engine" authority="MemUnit"}
//[@SUMMARY]{summary="In-RAM SQLite :memory: orchestration bus. 6 tables: mu_commands, mu_results, mu_events, mu_state, mu_errors, mu_cli_registry. One connection, one owner, 6 documented sections. All commands flow through mu_commands, all results through mu_results."}
//[@CLASS]{class="MemUnit" domain="bcl_c_engine" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="Dispatch" type="command"}
//[@METHOD]{method="RegisterCommand" type="command"}
//[@METHOD]{method="SetState" type="command"}
//[@METHOD]{method="GetState" type="command"}
//[@METHOD]{method="LogError" type="command"}
//[@METHOD]{method="CommandCount" type="command"}
//[@METHOD]{method="ResultCount" type="command"}
//[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<One file, one connection, 6 tables. SQLite tables are authority boundaries.>][@todos<none>]}

#include "bcl_engine.h"
#include <sqlite3.h>
#include <string.h>
#include <stdlib.h>

/* ─────────────────────────────────────────────────────────────────────────
 * MemUnit — in-RAM SQLite :memory: orchestration bus.
 *
 * ONE C file. ONE sqlite3* connection. SIX tables. SIX documented sections.
 *
 *   mu_commands      — Transport  : every dispatched command is recorded here
 *   mu_results       — Results    : outcomes of executed commands land here
 *   mu_events        — Audit Trail: lifecycle / dispatch events
 *   mu_state         — Runtime State: key/value runtime configuration
 *   mu_errors        — Error Detail: structured error records
 *   mu_cli_registry  — Command Registry: CLI command metadata
 *
 * The SQLite tables ARE the authority boundaries. There is no direct
 * unit-to-unit calling; everything flows through mu_commands and the
 * caller (executor) is responsible for the actual target invocation.
 *
 * Conventions:
 *   - PascalCase functions, UPPERCASE constants.
 *   - Spaces only, no tabs.
 *   - No printf() calls. No global variables except static buffers.
 * ───────────────────────────────────────────────────────────────────────── */

/* Static result buffer for MemUnit_GetState (returns const char*). */
static char s_state_value_buf[MU_MAX_VAL + 1];

/* ─────────────────────────────────────────────────────────────────────────
 * Lifecycle
 * ───────────────────────────────────────────────────────────────────────── */

void MemUnit_Init(MemUnit *mu)
{
    sqlite3 *db = NULL;
    int rc;

    if (mu == NULL) {
        return;
    }

    memset(mu, 0, sizeof(MemUnit));

    rc = sqlite3_open(":memory:", &db);
    if (rc != SQLITE_OK) {
        if (db != NULL) {
            sqlite3_close(db);
        }
        mu->conn = NULL;
        mu->initialized = 0;
        return;
    }
    mu->conn = (void *)db;

    /* Create all 6 tables. SQLite tables are the authority boundaries. */

    /* ═══ SECTION 1: mu_commands (Transport) ═══ */
    const char *sql_commands =
        "CREATE TABLE IF NOT EXISTS mu_commands ("
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "    ts TEXT NOT NULL,"
        "    target_unit TEXT NOT NULL,"
        "    command TEXT NOT NULL,"
        "    bcl_in TEXT NOT NULL,"
        "    status TEXT DEFAULT 'pending'"
        ");";
    rc = sqlite3_exec(db, sql_commands, NULL, NULL, NULL);
    if (rc != SQLITE_OK) {
        sqlite3_close(db);
        mu->conn = NULL;
        mu->initialized = 0;
        return;
    }

    /* ═══ SECTION 2: mu_results (Results) ═══ */
    const char *sql_results =
        "CREATE TABLE IF NOT EXISTS mu_results ("
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "    command_id INTEGER NOT NULL,"
        "    ts TEXT NOT NULL,"
        "    bcl_out TEXT NOT NULL,"
        "    is_ok INTEGER NOT NULL,"
        "    elapsed_ms INTEGER"
        ");";
    rc = sqlite3_exec(db, sql_results, NULL, NULL, NULL);
    if (rc != SQLITE_OK) {
        sqlite3_close(db);
        mu->conn = NULL;
        mu->initialized = 0;
        return;
    }

    /* ═══ SECTION 3: mu_events (Audit Trail) ═══ */
    const char *sql_events =
        "CREATE TABLE IF NOT EXISTS mu_events ("
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "    ts TEXT NOT NULL,"
        "    event_type TEXT NOT NULL,"
        "    command_id INTEGER,"
        "    detail TEXT"
        ");";
    rc = sqlite3_exec(db, sql_events, NULL, NULL, NULL);
    if (rc != SQLITE_OK) {
        sqlite3_close(db);
        mu->conn = NULL;
        mu->initialized = 0;
        return;
    }

    /* ═══ SECTION 4: mu_state (Runtime State) ═══ */
    const char *sql_state =
        "CREATE TABLE IF NOT EXISTS mu_state ("
        "    key TEXT PRIMARY KEY,"
        "    value TEXT NOT NULL"
        ");";
    rc = sqlite3_exec(db, sql_state, NULL, NULL, NULL);
    if (rc != SQLITE_OK) {
        sqlite3_close(db);
        mu->conn = NULL;
        mu->initialized = 0;
        return;
    }

    /* ═══ SECTION 5: mu_errors (Error Detail) ═══ */
    const char *sql_errors =
        "CREATE TABLE IF NOT EXISTS mu_errors ("
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "    command_id INTEGER NOT NULL,"
        "    ts TEXT NOT NULL,"
        "    error_code INTEGER NOT NULL,"
        "    error_desc TEXT NOT NULL,"
        "    error_unit TEXT NOT NULL,"
        "    error_input TEXT,"
        "    error_context TEXT,"
        "    problem TEXT,"
        "    solution TEXT,"
        "    severity TEXT DEFAULT 'error'"
        ");";
    rc = sqlite3_exec(db, sql_errors, NULL, NULL, NULL);
    if (rc != SQLITE_OK) {
        sqlite3_close(db);
        mu->conn = NULL;
        mu->initialized = 0;
        return;
    }

    /* ═══ SECTION 6: mu_cli_registry (Command Registry) ═══ */
    const char *sql_cli =
        "CREATE TABLE IF NOT EXISTS mu_cli_registry ("
        "    cmd_key TEXT PRIMARY KEY,"
        "    target_unit TEXT NOT NULL,"
        "    help_text TEXT NOT NULL,"
        "    category TEXT NOT NULL,"
        "    requires_param INTEGER DEFAULT 0,"
        "    param_example TEXT"
        ");";
    rc = sqlite3_exec(db, sql_cli, NULL, NULL, NULL);
    if (rc != SQLITE_OK) {
        sqlite3_close(db);
        mu->conn = NULL;
        mu->initialized = 0;
        return;
    }

    mu->initialized = 1;
    mu->command_count = 0;
    mu->result_count = 0;
    mu->event_count = 0;
}

void MemUnit_Close(MemUnit *mu)
{
    if (mu == NULL) {
        return;
    }

    if (mu->conn != NULL) {
        sqlite3_close((sqlite3 *)mu->conn);
        mu->conn = NULL;
    }

    memset(mu, 0, sizeof(MemUnit));
}

/* ─────────────────────────────────────────────────────────────────────────
 * ═══ SECTION 1: mu_commands (Transport) ═══
 *
 * MemUnit_Dispatch records a command into mu_commands and emits a
 * CMD_DISPATCHED event into mu_events. It does NOT invoke the target
 * unit — the caller (executor) is responsible for the actual dispatch.
 * Returns the command_id (>0) on success, or 0 on failure.
 * ───────────────────────────────────────────────────────────────────────── */

int MemUnit_Dispatch(MemUnit *mu, const char *target_unit,
                     const char *command, const char *bcl_in,
                     char *bcl_out, size_t out_sz)
{
    sqlite3 *db;
    sqlite3_stmt *stmt = NULL;
    int rc;
    int command_id = 0;

    if (mu == NULL || mu->conn == NULL || mu->initialized == 0) {
        if (bcl_out != NULL && out_sz > 0) {
            bcl_out[0] = '\0';
        }
        return 0;
    }
    if (target_unit == NULL || command == NULL || bcl_in == NULL) {
        if (bcl_out != NULL && out_sz > 0) {
            bcl_out[0] = '\0';
        }
        return 0;
    }

    db = (sqlite3 *)mu->conn;

    /* Insert the command into mu_commands. */
    const char *sql_insert =
        "INSERT INTO mu_commands (ts, target_unit, command, bcl_in, status) "
        "VALUES (datetime('now'), ?, ?, ?, 'pending');";
    rc = sqlite3_prepare_v2(db, sql_insert, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        if (bcl_out != NULL && out_sz > 0) {
            bcl_out[0] = '\0';
        }
        return 0;
    }

    sqlite3_bind_text(stmt, 1, target_unit, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, command, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, bcl_in, -1, SQLITE_TRANSIENT);

    rc = sqlite3_step(stmt);
    if (rc != SQLITE_DONE) {
        sqlite3_finalize(stmt);
        if (bcl_out != NULL && out_sz > 0) {
            bcl_out[0] = '\0';
        }
        return 0;
    }
    sqlite3_finalize(stmt);
    stmt = NULL;

    command_id = (int)sqlite3_last_insert_rowid(db);
    if (command_id <= 0) {
        if (bcl_out != NULL && out_sz > 0) {
            bcl_out[0] = '\0';
        }
        return 0;
    }

    mu->command_count++;

    /* Emit CMD_DISPATCHED event into mu_events (Section 3). */
    const char *sql_event =
        "INSERT INTO mu_events (ts, event_type, command_id, detail) "
        "VALUES (datetime('now'), 'CMD_DISPATCHED', ?, ?);";
    rc = sqlite3_prepare_v2(db, sql_event, -1, &stmt, NULL);
    if (rc == SQLITE_OK) {
        sqlite3_bind_int(stmt, 1, command_id);
        sqlite3_bind_text(stmt, 2, command, -1, SQLITE_TRANSIENT);
        if (sqlite3_step(stmt) == SQLITE_DONE) {
            mu->event_count++;
        }
        sqlite3_finalize(stmt);
        stmt = NULL;
    }

    /* Provide a minimal BCL acknowledgement in the output buffer. */
    if (bcl_out != NULL && out_sz > 0) {
        snprintf(bcl_out, out_sz,
                 "[@CMD]{id=\"%d\" target=\"%s\" command=\"%s\" status=\"pending\"}",
                 command_id, target_unit, command);
    }

    return command_id;
}

/* ─────────────────────────────────────────────────────────────────────────
 * ═══ SECTION 2: mu_results (Results) ═══
 *
 * Results are produced by the executor after a command has actually run.
 * MemUnit tracks the running result_count. (Insertion of results is
 * performed by the executor layer; this section documents the boundary.)
 * ───────────────────────────────────────────────────────────────────────── */

int MemUnit_ResultCount(MemUnit *mu)
{
    if (mu == NULL) {
        return 0;
    }
    return mu->result_count;
}

/* ─────────────────────────────────────────────────────────────────────────
 * ═══ SECTION 3: mu_events (Audit Trail) ═══
 *
 * Lifecycle / dispatch events. CMD_DISPATCHED is emitted by
 * MemUnit_Dispatch. Other event types are emitted by the executor.
 * ───────────────────────────────────────────────────────────────────────── */

/* Event emission is performed inline within MemUnit_Dispatch above. */

/* ─────────────────────────────────────────────────────────────────────────
 * ═══ SECTION 4: mu_state (Runtime State) ═══
 *
 * Key/value runtime state. INSERT OR REPLACE semantics for upsert.
 * GetState returns a pointer into a static buffer (valid until the next
 * GetState call) or NULL if the key is absent / on error.
 * ───────────────────────────────────────────────────────────────────────── */

int MemUnit_SetState(MemUnit *mu, const char *key, const char *value)
{
    sqlite3 *db;
    sqlite3_stmt *stmt = NULL;
    int rc;

    if (mu == NULL || mu->conn == NULL || mu->initialized == 0) {
        return 0;
    }
    if (key == NULL || value == NULL) {
        return 0;
    }

    db = (sqlite3 *)mu->conn;

    const char *sql =
        "INSERT OR REPLACE INTO mu_state (key, value) VALUES (?, ?);";
    rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        return 0;
    }

    sqlite3_bind_text(stmt, 1, key, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, value, -1, SQLITE_TRANSIENT);

    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    if (rc != SQLITE_DONE) {
        return 0;
    }
    return 1;
}

const char *MemUnit_GetState(MemUnit *mu, const char *key)
{
    sqlite3 *db;
    sqlite3_stmt *stmt = NULL;
    int rc;
    const unsigned char *text_val;

    if (mu == NULL || mu->conn == NULL || mu->initialized == 0) {
        return NULL;
    }
    if (key == NULL) {
        return NULL;
    }

    db = (sqlite3 *)mu->conn;

    const char *sql = "SELECT value FROM mu_state WHERE key = ?;";
    rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        return NULL;
    }

    sqlite3_bind_text(stmt, 1, key, -1, SQLITE_TRANSIENT);

    rc = sqlite3_step(stmt);
    if (rc != SQLITE_ROW) {
        sqlite3_finalize(stmt);
        return NULL;
    }

    text_val = sqlite3_column_text(stmt, 0);
    if (text_val == NULL) {
        sqlite3_finalize(stmt);
        return NULL;
    }

    /* Copy into the static buffer so the returned pointer is stable
     * after the statement is finalized. */
    memset(s_state_value_buf, 0, sizeof(s_state_value_buf));
    strncpy(s_state_value_buf, (const char *)text_val, MU_MAX_VAL);
    s_state_value_buf[MU_MAX_VAL] = '\0';

    sqlite3_finalize(stmt);
    return s_state_value_buf;
}

/* ─────────────────────────────────────────────────────────────────────────
 * ═══ SECTION 5: mu_errors (Error Detail) ═══
 *
 * Structured error records. All fields are persisted verbatim; NULL
 * optional fields are stored as SQL NULL.
 * ───────────────────────────────────────────────────────────────────────── */

int MemUnit_LogError(MemUnit *mu, int command_id, int error_code,
                     const char *error_desc, const char *error_unit,
                     const char *error_input, const char *error_context,
                     const char *problem, const char *solution)
{
    sqlite3 *db;
    sqlite3_stmt *stmt = NULL;
    int rc;

    if (mu == NULL || mu->conn == NULL || mu->initialized == 0) {
        return 0;
    }
    if (error_desc == NULL || error_unit == NULL) {
        return 0;
    }

    db = (sqlite3 *)mu->conn;

    const char *sql =
        "INSERT INTO mu_errors "
        "(command_id, ts, error_code, error_desc, error_unit, "
        " error_input, error_context, problem, solution) "
        "VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?, ?);";
    rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        return 0;
    }

    sqlite3_bind_int(stmt, 1, command_id);
    sqlite3_bind_int(stmt, 2, error_code);
    sqlite3_bind_text(stmt, 3, error_desc, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 4, error_unit, -1, SQLITE_TRANSIENT);

    if (error_input != NULL) {
        sqlite3_bind_text(stmt, 5, error_input, -1, SQLITE_TRANSIENT);
    } else {
        sqlite3_bind_null(stmt, 5);
    }

    if (error_context != NULL) {
        sqlite3_bind_text(stmt, 6, error_context, -1, SQLITE_TRANSIENT);
    } else {
        sqlite3_bind_null(stmt, 6);
    }

    if (problem != NULL) {
        sqlite3_bind_text(stmt, 7, problem, -1, SQLITE_TRANSIENT);
    } else {
        sqlite3_bind_null(stmt, 7);
    }

    if (solution != NULL) {
        sqlite3_bind_text(stmt, 8, solution, -1, SQLITE_TRANSIENT);
    } else {
        sqlite3_bind_null(stmt, 8);
    }

    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    if (rc != SQLITE_DONE) {
        return 0;
    }
    return 1;
}

/* ─────────────────────────────────────────────────────────────────────────
 * ═══ SECTION 6: mu_cli_registry (Command Registry) ═══
 *
 * CLI command metadata. INSERT OR REPLACE semantics for upsert so a
 * command may be re-registered to refresh its help text or example.
 * ───────────────────────────────────────────────────────────────────────── */

int MemUnit_RegisterCommand(MemUnit *mu, const char *cmd_key,
                            const char *target_unit, const char *help_text,
                            const char *category, int requires_param,
                            const char *param_example)
{
    sqlite3 *db;
    sqlite3_stmt *stmt = NULL;
    int rc;

    if (mu == NULL || mu->conn == NULL || mu->initialized == 0) {
        return 0;
    }
    if (cmd_key == NULL || target_unit == NULL ||
        help_text == NULL || category == NULL) {
        return 0;
    }

    db = (sqlite3 *)mu->conn;

    const char *sql =
        "INSERT OR REPLACE INTO mu_cli_registry "
        "(cmd_key, target_unit, help_text, category, requires_param, param_example) "
        "VALUES (?, ?, ?, ?, ?, ?);";
    rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        return 0;
    }

    sqlite3_bind_text(stmt, 1, cmd_key, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, target_unit, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, help_text, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 4, category, -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 5, requires_param ? 1 : 0);

    if (param_example != NULL) {
        sqlite3_bind_text(stmt, 6, param_example, -1, SQLITE_TRANSIENT);
    } else {
        sqlite3_bind_null(stmt, 6);
    }

    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    if (rc != SQLITE_DONE) {
        return 0;
    }
    return 1;
}

/* ─────────────────────────────────────────────────────────────────────────
 * Counters
 * ───────────────────────────────────────────────────────────────────────── */

int MemUnit_CommandCount(MemUnit *mu)
{
    if (mu == NULL) {
        return 0;
    }
    return mu->command_count;
}
