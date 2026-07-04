//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_destruction_guard.c" date="2026-07-03" author="cascade" session_id="destruction-guard-impl" context="BCL unit for destruction guard with embedded SQLite learning database. Pattern matching, confidence scoring, teach mode, auto-learning. Commands: evaluate, teach_block, teach_allow, teach_list, teach_stats, teach_export, teach_import."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_destruction_guard.c" domain="cascade_tools" authority="DestructionGuard"}
//[@SUMMARY]{summary="Destruction guard with embedded SQLite learning database. Evaluates commands for destructive operations, learns from user feedback, auto-suggests patterns. Commands: evaluate, teach_block, teach_allow, teach_list, teach_stats, teach_export, teach_import, read_state, set_config."}
//[@CLASS]{class="DestructionGuard" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="Evaluate" type="command"}
//[@METHOD]{method="TeachBlock" type="command"}
//[@METHOD]{method="TeachAllow" type="command"}
//[@METHOD]{method="TeachList" type="command"}
//[@METHOD]{method="TeachStats" type="command"}
//[@METHOD]{method="TeachExport" type="command"}
//[@METHOD]{method="TeachImport" type="command"}
//[@METHOD]{method="MatchesPattern" type="query"}
//[@METHOD]{method="CalculateRisk" type="query"}
//[@METHOD]{method="CalculateConfidence" type="query"}
//[@METHOD]{method="RecordDecision" type="command"}
//[@METHOD]{method="RecordFeedback" type="command"}
//[@METHOD]{method="AutoLearn" type="command"}

#include "bcl_toolstack.h"
#include <sqlite3.h>
#include <regex.h>
#include <fnmatch.h>
#include <time.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/param.h>
#include <pwd.h>
#include <math.h>

/* ===== DIM BLOCK ===== */

#define DG_MAX_PATTERN     512
#define DG_MAX_COMMAND     8192
#define DG_MAX_DESC        256
#define DG_MAX_DB          64
#define DG_MAX_MATCHES     32
#define DG_BUF            4096
#define DG_RISK_THRESHOLD  0.4
#define DG_MAX_CACHED_REGEX 256

/* Cached regex structure */
typedef struct {
    int pattern_id;
    regex_t compiled;
    int is_compiled;
} CachedRegex;

/* Action types */
typedef enum {
    ACTION_UNKNOWN = 0,
    ACTION_BLOCK = 1,
    ACTION_ALLOW = 2,
    ACTION_WARN = 3
} ActionType;

/* Pattern types */
typedef enum {
    PATTERN_REGEX = 0,
    PATTERN_LITERAL = 1,
    PATTERN_GLOB = 2,
    PATTERN_PATH = 3
} PatternType;

/* Decision result */
typedef struct {
    ActionType action;
    double risk_score;
    double confidence;
    char reason[DG_BUF];
    char matched_ids[DG_BUF];
    int pattern_count;
} DecisionResult;

/* State */
static struct {
    sqlite3 *db;              /* Embedded patterns database */
    sqlite3 *cmd_db;          /* External command database */
    int initialized;
    int learning_enabled;
    double risk_threshold;
    int patterns_loaded;
    int decisions_made;
    int patterns_taught;
    char last_error[DG_BUF];
    CachedRegex regex_cache[DG_MAX_CACHED_REGEX];
    int regex_cache_count;
} STATE;

/* ===== SEED SQL ===== */

static const char SEED_SQL[] =
"CREATE TABLE IF NOT EXISTS patterns ("
"  id INTEGER PRIMARY KEY,"
"  pattern TEXT NOT NULL UNIQUE,"
"  pattern_type TEXT DEFAULT 'regex',"
"  action TEXT NOT NULL,"
"  category TEXT DEFAULT 'destructive',"
"  severity INTEGER DEFAULT 3,"
"  confidence REAL DEFAULT 0.5,"
"  success_count INTEGER DEFAULT 0,"
"  failure_count INTEGER DEFAULT 0,"
"  last_used INTEGER,"
"  source TEXT DEFAULT 'builtin',"
"  description TEXT"
");"

"CREATE TABLE IF NOT EXISTS decisions ("
"  id INTEGER PRIMARY KEY,"
"  command TEXT NOT NULL,"
"  matched_patterns TEXT,"
"  action TEXT NOT NULL,"
"  risk_score REAL,"
"  confidence REAL,"
"  user_override INTEGER DEFAULT 0,"
"  timestamp INTEGER DEFAULT (strftime('%s','now')),"
"  evidence TEXT"
");"

"CREATE TABLE IF NOT EXISTS feedback ("
"  id INTEGER PRIMARY KEY,"
"  decision_id INTEGER,"
"  was_correct INTEGER NOT NULL,"
"  user_action TEXT,"
"  correction TEXT,"
"  timestamp INTEGER DEFAULT (strftime('%s','now')),"
"  FOREIGN KEY(decision_id) REFERENCES decisions(id)"
");"

"CREATE TABLE IF NOT EXISTS evidence ("
"  id INTEGER PRIMARY KEY,"
"  decision_id INTEGER,"
"  evidence_type TEXT,"
"  value TEXT,"
"  risk_weight REAL DEFAULT 0.5,"
"  FOREIGN KEY(decision_id) REFERENCES decisions(id)"
");"

"CREATE TABLE IF NOT EXISTS system_state ("
"  key TEXT PRIMARY KEY,"
"  value TEXT,"
"  description TEXT"
");"

"CREATE TABLE IF NOT EXISTS builtin_patterns ("
"  id INTEGER PRIMARY KEY,"
"  pattern TEXT NOT NULL,"
"  action TEXT NOT NULL,"
"  category TEXT,"
"  severity INTEGER,"
"  description TEXT"
");"
;

/* ===== BUILT-IN PATTERNS ===== */

static const char SEED_PATTERNS[] =
"INSERT INTO builtin_patterns (pattern,action,category,severity,description) VALUES "
"('/bin/rm','block','destructive',5,'rm via full path'),"
"('(^|[^a-zA-Z0-9])rm([^a-zA-Z0-9]|$)','block','destructive',5,'rm command'),"
"('(^|[^a-zA-Z0-9])rmdir([^a-zA-Z0-9]|$)','block','destructive',5,'rmdir command'),"
"('(^|[^a-zA-Z0-9])unlink([^a-zA-Z0-9]|$)','block','destructive',5,'unlink syscall'),"
"('shutil\\.rmtree','block','destructive',5,'Python rmtree'),"
"('os\\.remove','block','destructive',5,'Python os.remove'),"
"('os\\.unlink','block','destructive',5,'Python os.unlink'),"
"('DELETE[[:space:]]+FROM','block','database',4,'SQL DELETE'),"
"('DROP[[:space:]]+TABLE','block','database',5,'SQL DROP TABLE'),"
"('TRUNCATE[[:space:]]+TABLE','block','database',4,'SQL TRUNCATE'),"
"('git[[:space:]]+push.*-f','block','git',3,'git force push'),"
"('git[[:space:]]+clean.*-f','block','git',3,'git clean force'),"
"('truncate[[:space:]]+-s[[:space:]]*0','block','filesystem',4,'truncate to zero'),"
"('(^|[^a-zA-Z0-9])dd([^a-zA-Z0-9]|$)','block','disk',5,'disk destroyer - can overwrite entire disks'),"
"('(^|[^a-zA-Z0-9])diskutil([^a-zA-Z0-9]|$)','block','disk',5,'disk utility - partition/format/erase disks'),"
"('(^|[^a-zA-Z0-9])fdisk([^a-zA-Z0-9]|$)','block','disk',5,'partition table editor - modify disk partitions'),"
"('(^|[^a-zA-Z0-9])fsck([^a-zA-Z0-9]|$)','block','filesystem',5,'filesystem check - can corrupt if misused'),"
"('(^|[^a-zA-Z0-9])gpt([^a-zA-Z0-9]|$)','block','disk',5,'GUID partition table editor'),"
"('(^|[^a-zA-Z0-9])halt([^a-zA-Z0-9]|$)','block','system',5,'halt the system'),"
"('(^|[^a-zA-Z0-9])kill([^a-zA-Z0-9]|$)','block','process',5,'terminate processes'),"
"('(^|[^a-zA-Z0-9])killall([^a-zA-Z0-9]|$)','block','process',5,'terminate all processes by name'),"
"('(^|[^a-zA-Z0-9])mount([^a-zA-Z0-9]|$)','block','filesystem',5,'mount filesystems'),"
"('(^|[^a-zA-Z0-9])shutdown([^a-zA-Z0-9]|$)','block','system',5,'shutdown the system'),"
"('(^|[^a-zA-Z0-9])srm([^a-zA-Z0-9]|$)','block','destructive',5,'secure remove - permanently delete files'),"
"('(^|[^a-zA-Z0-9])umount([^a-zA-Z0-9]|$)','block','filesystem',5,'unmount filesystems'),"
"('(^|[^a-zA-Z0-9])asr([^a-zA-Z0-9]|$)','block','system',3,'Apple Software Restore'),"
"('(^|[^a-zA-Z0-9])bless([^a-zA-Z0-9]|$)','block','system',3,'set boot volume'),"
"('(^|[^a-zA-Z0-9])chflags([^a-zA-Z0-9]|$)','block','filesystem',3,'change file flags'),"
"('(^|[^a-zA-Z0-9])chgrp([^a-zA-Z0-9]|$)','block','filesystem',3,'change group ownership'),"
"('(^|[^a-zA-Z0-9])chmod([^a-zA-Z0-9]|$)','block','filesystem',3,'change file permissions'),"
"('(^|[^a-zA-Z0-9])chown([^a-zA-Z0-9]|$)','block','filesystem',3,'change file ownership'),"
"('(^|[^a-zA-Z0-9])codesign([^a-zA-Z0-9]|$)','block','security',3,'modify code signatures'),"
"('(^|[^a-zA-Z0-9])cp([^a-zA-Z0-9]|$)','block','filesystem',3,'copy files - can overwrite'),"
"('(^|[^a-zA-Z0-9])csrutil([^a-zA-Z0-9]|$)','block','system',3,'configure System Integrity Protection'),"
"('(^|[^a-zA-Z0-9])defaults([^a-zA-Z0-9]|$)','block','system',3,'modify system preferences'),"
"('(^|[^a-zA-Z0-9])hdiutil([^a-zA-Z0-9]|$)','block','disk',3,'disk image operations'),"
"('(^|[^a-zA-Z0-9])install([^a-zA-Z0-9]|$)','block','filesystem',3,'install files - can overwrite'),"
"('(^|[^a-zA-Z0-9])launchctl([^a-zA-Z0-9]|$)','block','system',3,'control launch daemons/agents'),"
"('(^|[^a-zA-Z0-9])mv([^a-zA-Z0-9]|$)','block','filesystem',3,'move/rename files - can overwrite'),"
"('(^|[^a-zA-Z0-9])nvram([^a-zA-Z0-9]|$)','block','system',3,'modify NVRAM settings'),"
"('(^|[^a-zA-Z0-9])profiles([^a-zA-Z0-9]|$)','block','system',3,'manage configuration profiles'),"
"('(^|[^a-zA-Z0-9])rsync([^a-zA-Z0-9]|$)','block','filesystem',3,'sync files - can overwrite'),"
"('(^|[^a-zA-Z0-9])security([^a-zA-Z0-9]|$)','block','security',3,'manage keychains and certificates'),"
"('(^|[^a-zA-Z0-9])softwareupdate([^a-zA-Z0-9]|$)','block','system',3,'install system updates'),"
"('(^|[^a-zA-Z0-9])spctl([^a-zA-Z0-9]|$)','block','security',3,'control Gatekeeper'),"
"('(^|[^a-zA-Z0-9])sysctl([^a-zA-Z0-9]|$)','block','system',3,'modify system parameters'),"
"('(^|[^a-zA-Z0-9])tar([^a-zA-Z0-9]|$)','block','filesystem',3,'archive files - can overwrite'),"
"('(^|[^a-zA-Z0-9])tmutil([^a-zA-Z0-9]|$)','block','system',3,'Time Machine operations'),"
"(>)[[:space:]]*/dev/null','allow','redirect',1,'redirect to null device'),"
"(>)[[:space:]]*/dev/stdout','allow','redirect',1,'redirect to stdout'),"
"(>)[[:space:]]*/dev/stderr','allow','redirect',1,'redirect to stderr'),"
"('python.*-c','allow','interpreter',2,'inline Python code'),"
"('echo.*rm','allow','non_executing',1,'rm in echo string'),"
"('grep.*rm','allow','non_executing',1,'rm in grep pattern'),"
"('cat.*rm','allow','non_executing',1,'rm in cat string');"
;

/* ===== INITIALIZATION ===== */

int DestructionGuard_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    
    int rc = sqlite3_open(":memory:", &STATE.db);
    if (rc != SQLITE_OK) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), 
                 "sqlite3_open failed: %s", sqlite3_errmsg(STATE.db));
        return 0;
    }
    
    rc = sqlite3_exec(STATE.db, SEED_SQL, NULL, NULL, NULL);
    if (rc != SQLITE_OK) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
                 "SEED_SQL failed: %s", sqlite3_errmsg(STATE.db));
        return 0;
    }
    
    rc = sqlite3_exec(STATE.db, SEED_PATTERNS, NULL, NULL, NULL);
    if (rc != SQLITE_OK) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
                 "SEED_PATTERNS failed: %s", sqlite3_errmsg(STATE.db));
        return 0;
    }
    
    rc = sqlite3_exec(STATE.db,
        "INSERT INTO patterns (pattern,action,category,severity,confidence,source,description) "
        "SELECT pattern,action,category,severity,0.5,'builtin',description "
        "FROM builtin_patterns "
        "WHERE pattern NOT IN (SELECT pattern FROM patterns)", NULL, NULL, NULL);
    if (rc != SQLITE_OK) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
                 "pattern load failed: %s", sqlite3_errmsg(STATE.db));
        return 0;
    }
    
    STATE.initialized = 1;
    STATE.learning_enabled = 1;
    STATE.risk_threshold = DG_RISK_THRESHOLD;
    STATE.regex_cache_count = 0;
    
    /* Pre-compile regex patterns for performance */
    sqlite3_stmt *stmt;
    int rc2 = sqlite3_prepare_v2(STATE.db,
        "SELECT id, pattern FROM patterns WHERE pattern_type = 'regex'",
        -1, &stmt, NULL);
    if (rc2 != SQLITE_OK) {
        snprintf(STATE.last_error, sizeof(STATE.last_error),
                 "Failed to prepare regex cache query");
        return 0;
    }
    
    while (sqlite3_step(stmt) == SQLITE_ROW && STATE.regex_cache_count < DG_MAX_CACHED_REGEX) {
        int id = sqlite3_column_int(stmt, 0);
        const char *pattern = (const char*)sqlite3_column_text(stmt, 1);
        
        CachedRegex *cr = &STATE.regex_cache[STATE.regex_cache_count];
        cr->pattern_id = id;
        cr->is_compiled = 0;
        
        if (regcomp(&cr->compiled, pattern, REG_EXTENDED | REG_ICASE | REG_NOSUB) == 0) {
            cr->is_compiled = 1;
            STATE.regex_cache_count++;
        }
    }
    sqlite3_finalize(stmt);
    
    rc = sqlite3_prepare_v2(STATE.db, "SELECT COUNT(*) FROM patterns", -1, &stmt, NULL);
    if (rc == SQLITE_OK && sqlite3_step(stmt) == SQLITE_ROW) {
        STATE.patterns_loaded = sqlite3_column_int(stmt, 0);
    }
    sqlite3_finalize(stmt);
    
    /* Open external command database if available */
    const char *cmd_db_path = "mac_commands.db";
    rc = sqlite3_open_v2(cmd_db_path, &STATE.cmd_db, SQLITE_OPEN_READONLY, NULL);
    if (rc != SQLITE_OK) {
        STATE.cmd_db = NULL;  /* Optional, continue without it */
    }
    
    return 1;
}

/* ===== PATTERN MATCHING ===== */

int DestructionGuard_MatchesPattern(const char *command, const char *pattern, const char *pattern_type, int pattern_id) {
    if (!command || !pattern) return 0;
    
    if (strcmp(pattern_type, "literal") == 0) {
        return strstr(command, pattern) != NULL;
    } else if (strcmp(pattern_type, "regex") == 0) {
        /* Try to use cached regex first */
        for (int i = 0; i < STATE.regex_cache_count; i++) {
            if (STATE.regex_cache[i].pattern_id == pattern_id && STATE.regex_cache[i].is_compiled) {
                return regexec(&STATE.regex_cache[i].compiled, command, 0, NULL, 0) == 0;
            }
        }
        /* Fallback to compile on demand if not cached */
        regex_t re;
        if (regcomp(&re, pattern, REG_EXTENDED | REG_ICASE | REG_NOSUB) != 0) return 0;
        int match = regexec(&re, command, 0, NULL, 0) == 0;
        regfree(&re);
        return match;
    } else if (strcmp(pattern_type, "glob") == 0) {
        return fnmatch(pattern, command, FNM_CASEFOLD) == 0;
    } else if (strcmp(pattern_type, "path") == 0) {
        /* Extract path from command - handle shell argument parsing with quotes/escapes */
        char *cmd_copy = strdup(command);
        if (!cmd_copy) return 0;
        
        /* Skip the command name */
        char *space = strchr(cmd_copy, ' ');
        if (!space) {
            free(cmd_copy);
            return 0;
        }
        char *args = space + 1;
        while (*args == ' ') args++;
        
        /* Find the first non-flag argument (not starting with -) */
        /* Handle quoted strings: "file", 'file', and escaped spaces */
        char *path_arg = NULL;
        char *p = args;
        int in_quote = 0;
        char quote_char = 0;
        
        while (*p) {
            /* Skip whitespace */
            if (!in_quote && *p == ' ') {
                p++;
                continue;
            }
            
            /* Check for quote start */
            if (!in_quote && (*p == '"' || *p == '\'')) {
                quote_char = *p;
                in_quote = 1;
                p++;
                continue;
            }
            
            /* Check for quote end */
            if (in_quote && *p == quote_char) {
                in_quote = 0;
                p++;
                continue;
            }
            
            /* Check for escape sequence */
            if (*p == '\\' && *(p + 1)) {
                p += 2;
                continue;
            }
            
            /* Found start of potential path argument */
            if (!path_arg && *p != '-') {
                path_arg = p;
            }
            
            /* If we found a path arg and hit whitespace (not in quote), we're done */
            if (path_arg && !in_quote && *p == ' ') {
                *p = '\0';  /* Null-terminate the path argument */
                break;
            }
            
            p++;
        }
        
        if (!path_arg) {
            free(cmd_copy);
            return 0;
        }
        
        /* Remove surrounding quotes if present */
        if ((*path_arg == '"' || *path_arg == '\'') && path_arg[strlen(path_arg) - 1] == *path_arg) {
            path_arg++;
            path_arg[strlen(path_arg) - 1] = '\0';
        }
        
        char resolved[PATH_MAX];
        if (realpath(path_arg, resolved) == NULL) {
            free(cmd_copy);
            return 0;
        }
        
        free(cmd_copy);
        return strstr(resolved, pattern) != NULL;
    }
    
    return 0;
}

/* ===== HELPER FUNCTIONS ===== */

static void RefreshPatternCount(void) {
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(STATE.db,
            "SELECT COUNT(*) FROM patterns",
            -1,
            &stmt,
            NULL) == SQLITE_OK) {
        if (sqlite3_step(stmt) == SQLITE_ROW)
            STATE.patterns_loaded = sqlite3_column_int(stmt, 0);
        sqlite3_finalize(stmt);
    }
}

static void CompactRegexCache(void) {
    /* Compact cache by removing invalidated entries */
    int write_idx = 0;
    for (int i = 0; i < STATE.regex_cache_count; i++) {
        if (STATE.regex_cache[i].is_compiled) {
            if (write_idx != i) {
                STATE.regex_cache[write_idx] = STATE.regex_cache[i];
            }
            write_idx++;
        }
        /* Invalidated entries already freed during invalidation - skip regfree() */
    }
    STATE.regex_cache_count = write_idx;
}

/* ===== CONFIDENCE CALCULATION ===== */

double DestructionGuard_CalculateConfidence(int pattern_id) {
    sqlite3_stmt *stmt;
    int rc = sqlite3_prepare_v2(STATE.db,
        "SELECT success_count, failure_count, last_used FROM patterns WHERE id = ?",
        -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        return 0.5;
    }
    
    sqlite3_bind_int(stmt, 1, pattern_id);
    
    if (sqlite3_step(stmt) != SQLITE_ROW) {
        sqlite3_finalize(stmt);
        return 0.5;
    }
    
    int success = sqlite3_column_int(stmt, 0);
    int failure = sqlite3_column_int(stmt, 1);
    time_t last_used = sqlite3_column_int64(stmt, 2);
    sqlite3_finalize(stmt);
    
    double base = 0.5;
    int total = success + failure;
    
    if (total > 0) {
        double success_rate = (double)success / total;
        base = (0.5 + success * success_rate) / (1 + total);
    }
    
    double decay = 1.0;
    if (last_used > 0) {
        time_t now = time(NULL);
        double days_since = difftime(now, last_used) / 86400.0;
        decay = exp(-days_since / 30.0);
    }
    
    return base * decay;
}

/* ===== DECISION RECORDING ===== */

int DestructionGuard_RecordDecision(const char *command, const char *matched_ids, 
                                   ActionType action, double risk_score) {
    const char *action_str = (action == ACTION_BLOCK) ? "block" :
                             (action == ACTION_ALLOW) ? "allow" : "warn";
    
    sqlite3_stmt *stmt;
    int rc = sqlite3_prepare_v2(STATE.db,
        "INSERT INTO decisions (command, matched_patterns, action, risk_score, confidence) "
        "VALUES (?, ?, ?, ?, 0.5)", -1, &stmt, NULL);
    if (rc != SQLITE_OK) return 0;
    
    sqlite3_bind_text(stmt, 1, command, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, matched_ids, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, action_str, -1, SQLITE_TRANSIENT);
    sqlite3_bind_double(stmt, 4, risk_score);
    
    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    return rc == SQLITE_DONE;
}

/* ===== EVALUATE COMMAND ===== */

DecisionResult DestructionGuard_Evaluate(const char *command) {
    DecisionResult result = {0};
    result.action = ACTION_UNKNOWN;
    result.risk_score = 0.0;
    result.confidence = 0.5;
    strcpy(result.reason, "No decision made");
    strcpy(result.matched_ids, "");
    result.pattern_count = 0;
    
    if (!command || !*command) {
        strcpy(result.reason, "Empty command");
        return result;
    }
    
    char matched_ids[DG_BUF] = "";
    size_t matched_ids_len = 0;
    sqlite3_stmt *stmt;
    int rc = sqlite3_prepare_v2(STATE.db,
        "SELECT id, pattern, action, severity, pattern_type FROM patterns",
        -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        strcpy(result.reason, "Database error");
        return result;
    }
    
    double max_confidence = 0.0;
    double max_risk = 0.0;
    int matched_count = 0;
    
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        int id = sqlite3_column_int(stmt, 0);
        const char *pattern = (const char*)sqlite3_column_text(stmt, 1);
        const char *action = (const char*)sqlite3_column_text(stmt, 2);
        int severity = sqlite3_column_int(stmt, 3);
        const char *pattern_type = (const char*)sqlite3_column_text(stmt, 4);
        
        if (!pattern || !action || !pattern_type) {
            continue;
        }
        
        if (DestructionGuard_MatchesPattern(command, pattern, pattern_type, id)) {
            if (matched_ids_len < DG_BUF - 32) {
                matched_ids_len += snprintf(matched_ids + matched_ids_len, 
                                           DG_BUF - matched_ids_len, "%d,", id);
            } else {
                /* Overflow detected - add warning indicator */
                if (matched_ids_len < DG_BUF - 12) {
                    matched_ids_len += snprintf(matched_ids + matched_ids_len,
                                               DG_BUF - matched_ids_len, "[OVERFLOW]");
                }
                break;
            }
            result.pattern_count++;
            matched_count++;
            
            /* Use CalculateConfidence for this pattern */
            double pattern_confidence = DestructionGuard_CalculateConfidence(id);
            
            /* Track max confidence */
            if (pattern_confidence > max_confidence) {
                max_confidence = pattern_confidence;
            }
            
            /* Calculate risk contribution */
            double severity_weight = severity / 5.0;
            double contribution = severity_weight * pattern_confidence;
            
            if (strcmp(action, "block") == 0) {
                contribution *= 1.5;
                result.action = ACTION_BLOCK;
            } else if (strcmp(action, "allow") == 0 && result.action != ACTION_BLOCK) {
                contribution *= 0.3;
                result.action = ACTION_ALLOW;
            }
            
            /* Track max risk instead of summing */
            if (contribution > max_risk) {
                max_risk = contribution;
            }
        }
    }
    sqlite3_finalize(stmt);
    
    /* Set final confidence to max of all matched patterns */
    result.confidence = max_confidence > 0 ? max_confidence : 0.5;
    
    /* Use max risk instead of average */
    result.risk_score = max_risk > 1.0 ? 1.0 : max_risk;
    
    if (result.risk_score > STATE.risk_threshold) {
        result.action = ACTION_BLOCK;
        snprintf(result.reason, sizeof(result.reason), 
                 "Risk %.2f exceeds threshold %.2f", 
                 result.risk_score, STATE.risk_threshold);
    } else if (result.action == ACTION_BLOCK) {
        snprintf(result.reason, sizeof(result.reason),
                 "Pattern match requires block");
    } else {
        result.action = ACTION_ALLOW;
        snprintf(result.reason, sizeof(result.reason),
                 "No blocking patterns found");
    }
    
    strncpy(result.matched_ids, matched_ids, sizeof(result.matched_ids) - 1);
    
    DestructionGuard_RecordDecision(command, matched_ids, result.action, result.risk_score);
    STATE.decisions_made++;
    
    return result;
}

/* ===== TEACH MODE ===== */

int DestructionGuard_TeachBlock(const char *pattern, const char *description) {
    if (!pattern || !*pattern) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "Empty pattern");
        return 0;
    }
    
    /* Begin transaction */
    char *err_msg = NULL;
    int rc = sqlite3_exec(STATE.db, "BEGIN IMMEDIATE", NULL, NULL, &err_msg);
    if (rc != SQLITE_OK) {
        if (err_msg) {
            snprintf(STATE.last_error, sizeof(STATE.last_error), "Failed to begin transaction: %s", err_msg);
            sqlite3_free(err_msg);
        }
        return 0;
    }
    
    /* Check if pattern already exists to invalidate cache */
    sqlite3_stmt *check;
    rc = sqlite3_prepare_v2(STATE.db,
        "SELECT id FROM patterns WHERE pattern = ?",
        -1, &check, NULL);
    if (rc == SQLITE_OK) {
        sqlite3_bind_text(check, 1, pattern, -1, SQLITE_TRANSIENT);
        if (sqlite3_step(check) == SQLITE_ROW) {
            /* Pattern exists - invalidate cache entry */
            int existing_id = sqlite3_column_int(check, 0);
            for (int i = 0; i < STATE.regex_cache_count; i++) {
                if (STATE.regex_cache[i].pattern_id == existing_id) {
                    regfree(&STATE.regex_cache[i].compiled);
                    STATE.regex_cache[i].is_compiled = 0;
                }
            }
            CompactRegexCache();
        }
        sqlite3_finalize(check);
    }
    
    sqlite3_stmt *stmt;
    rc = sqlite3_prepare_v2(STATE.db,
        "INSERT INTO patterns "
        "(pattern,action,category,severity,confidence,source,description,pattern_type) "
        "VALUES (?, 'block', 'user-taught', 4, 0.8, 'taught', ?, 'regex') "
        "ON CONFLICT(pattern) DO UPDATE SET "
        "action='block', category='user-taught', severity=4, confidence=0.8, source='taught', description=?, pattern_type='regex'",
        -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        sqlite3_exec(STATE.db, "ROLLBACK", NULL, NULL, NULL);
        snprintf(STATE.last_error, sizeof(STATE.last_error), "Failed to prepare statement");
        return 0;
    }
    
    sqlite3_bind_text(stmt, 1, pattern, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, description ? description : "User-taught block pattern", -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, description ? description : "User-taught block pattern", -1, SQLITE_TRANSIENT);
    
    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    
    if (rc != SQLITE_DONE) {
        sqlite3_exec(STATE.db, "ROLLBACK", NULL, NULL, NULL);
        snprintf(STATE.last_error, sizeof(STATE.last_error), "Failed to add pattern");
        return 0;
    }
    
    STATE.patterns_taught++;
    RefreshPatternCount();
    
    /* Cache the new regex if it's a regex pattern */
    /* Get the pattern ID */
    sqlite3_stmt *id_stmt;
    int id_rc = sqlite3_prepare_v2(STATE.db,
        "SELECT id FROM patterns WHERE pattern = ?",
        -1, &id_stmt, NULL);
    int pattern_id = -1;
    if (id_rc == SQLITE_OK) {
        sqlite3_bind_text(id_stmt, 1, pattern, -1, SQLITE_TRANSIENT);
        if (sqlite3_step(id_stmt) == SQLITE_ROW) {
            pattern_id = sqlite3_column_int(id_stmt, 0);
        }
        sqlite3_finalize(id_stmt);
    }
    
    if (pattern_id >= 0 && STATE.regex_cache_count < DG_MAX_CACHED_REGEX) {
        CachedRegex *cr = &STATE.regex_cache[STATE.regex_cache_count];
        cr->pattern_id = pattern_id;
        cr->is_compiled = 0;
        
        if (regcomp(&cr->compiled, pattern, REG_EXTENDED | REG_ICASE | REG_NOSUB) == 0) {
            cr->is_compiled = 1;
            STATE.regex_cache_count++;
        }
    }
    
    /* Commit transaction */
    sqlite3_exec(STATE.db, "COMMIT", NULL, NULL, NULL);
    
    return 1;
}

int DestructionGuard_TeachAllow(const char *pattern, const char *description) {
    if (!pattern || !*pattern) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "Empty pattern");
        return 0;
    }
    
    /* Begin transaction */
    char *err_msg = NULL;
    int rc = sqlite3_exec(STATE.db, "BEGIN IMMEDIATE", NULL, NULL, &err_msg);
    if (rc != SQLITE_OK) {
        if (err_msg) {
            snprintf(STATE.last_error, sizeof(STATE.last_error), "Failed to begin transaction: %s", err_msg);
            sqlite3_free(err_msg);
        }
        return 0;
    }
    
    /* Check if pattern already exists to invalidate cache */
    sqlite3_stmt *check;
    rc = sqlite3_prepare_v2(STATE.db,
        "SELECT id FROM patterns WHERE pattern = ?",
        -1, &check, NULL);
    if (rc == SQLITE_OK) {
        sqlite3_bind_text(check, 1, pattern, -1, SQLITE_TRANSIENT);
        if (sqlite3_step(check) == SQLITE_ROW) {
            /* Pattern exists - invalidate cache entry */
            int existing_id = sqlite3_column_int(check, 0);
            for (int i = 0; i < STATE.regex_cache_count; i++) {
                if (STATE.regex_cache[i].pattern_id == existing_id) {
                    regfree(&STATE.regex_cache[i].compiled);
                    STATE.regex_cache[i].is_compiled = 0;
                }
            }
            CompactRegexCache();
        }
        sqlite3_finalize(check);
    }
    
    sqlite3_stmt *stmt;
    rc = sqlite3_prepare_v2(STATE.db,
        "INSERT INTO patterns "
        "(pattern,action,category,severity,confidence,source,description,pattern_type) "
        "VALUES (?, 'allow', 'user-taught', 1, 0.8, 'taught', ?, 'regex') "
        "ON CONFLICT(pattern) DO UPDATE SET "
        "action='allow', category='user-taught', severity=1, confidence=0.8, source='taught', description=?, pattern_type='regex'",
        -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        sqlite3_exec(STATE.db, "ROLLBACK", NULL, NULL, NULL);
        snprintf(STATE.last_error, sizeof(STATE.last_error), "Failed to prepare statement");
        return 0;
    }
    
    sqlite3_bind_text(stmt, 1, pattern, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, description ? description : "User-taught allow pattern", -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, description ? description : "User-taught allow pattern", -1, SQLITE_TRANSIENT);
    
    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    
    if (rc != SQLITE_DONE) {
        sqlite3_exec(STATE.db, "ROLLBACK", NULL, NULL, NULL);
        snprintf(STATE.last_error, sizeof(STATE.last_error), "Failed to add pattern");
        return 0;
    }
    
    STATE.patterns_taught++;
    RefreshPatternCount();
    
    /* Cache the new regex if it's a regex pattern */
    /* Get the pattern ID */
    sqlite3_stmt *id_stmt;
    int id_rc = sqlite3_prepare_v2(STATE.db,
        "SELECT id FROM patterns WHERE pattern = ?",
        -1, &id_stmt, NULL);
    int pattern_id = -1;
    if (id_rc == SQLITE_OK) {
        sqlite3_bind_text(id_stmt, 1, pattern, -1, SQLITE_TRANSIENT);
        if (sqlite3_step(id_stmt) == SQLITE_ROW) {
            pattern_id = sqlite3_column_int(id_stmt, 0);
        }
        sqlite3_finalize(id_stmt);
    }
    
    if (pattern_id >= 0 && STATE.regex_cache_count < DG_MAX_CACHED_REGEX) {
        CachedRegex *cr = &STATE.regex_cache[STATE.regex_cache_count];
        cr->pattern_id = pattern_id;
        cr->is_compiled = 0;
        
        if (regcomp(&cr->compiled, pattern, REG_EXTENDED | REG_ICASE | REG_NOSUB) == 0) {
            cr->is_compiled = 1;
            STATE.regex_cache_count++;
        }
    }
    
    /* Commit transaction */
    sqlite3_exec(STATE.db, "COMMIT", NULL, NULL, NULL);
    
    return 1;
}

/* ===== AUTO LEARN ===== */

int DestructionGuard_AutoLearn(void) {
    /* Begin transaction */
    char *err_msg = NULL;
    int rc = sqlite3_exec(STATE.db, "BEGIN IMMEDIATE", NULL, NULL, &err_msg);
    if (rc != SQLITE_OK) {
        if (err_msg) {
            snprintf(STATE.last_error, sizeof(STATE.last_error), "Failed to begin transaction: %s", err_msg);
            sqlite3_free(err_msg);
        }
        return 0;
    }
    
    sqlite3_stmt *stmt;
    rc = sqlite3_prepare_v2(STATE.db,
        "SELECT command, COUNT(*) as count "
        "FROM decisions WHERE action = 'block' "
        "GROUP BY command HAVING count > 5 "
        "ORDER BY count DESC", -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        sqlite3_exec(STATE.db, "ROLLBACK", NULL, NULL, NULL);
        snprintf(STATE.last_error, sizeof(STATE.last_error), "Failed to prepare statement");
        return 0;
    }
    
    int inserted = 0;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        const char *command = (const char*)sqlite3_column_text(stmt, 0);
        
        if (!command) {
            continue;
        }
        
        /* Extract base command (first word) */
        char base_cmd[DG_MAX_PATTERN] = "";
        const char *space = strchr(command, ' ');
        if (space) {
            size_t len = space - command;
            if (len < sizeof(base_cmd)) {
                strncpy(base_cmd, command, len);
                base_cmd[len] = '\0';
            }
        } else {
            strncpy(base_cmd, command, sizeof(base_cmd) - 1);
            base_cmd[sizeof(base_cmd) - 1] = '\0';
        }
        
        if (!base_cmd[0]) {
            continue;
        }
        
        /* Check if pattern already exists */
        sqlite3_stmt *check;
        rc = sqlite3_prepare_v2(STATE.db,
            "SELECT id FROM patterns WHERE pattern = ?", -1, &check, NULL);
        if (rc == SQLITE_OK) {
            sqlite3_bind_text(check, 1, base_cmd, -1, SQLITE_TRANSIENT);
            
            if (sqlite3_step(check) != SQLITE_ROW) {
                /* Pattern doesn't exist - insert it as a block pattern */
                sqlite3_stmt *insert;
                rc = sqlite3_prepare_v2(STATE.db,
                    "INSERT INTO patterns (pattern,action,category,severity,confidence,source,description,pattern_type) "
                    "VALUES (?, 'block', 'auto-learned', 4, 0.7, 'auto-learned', 'Auto-learned from blocked commands', 'literal')",
                    -1, &insert, NULL);
                if (rc == SQLITE_OK) {
                    sqlite3_bind_text(insert, 1, base_cmd, -1, SQLITE_TRANSIENT);
                    if (sqlite3_step(insert) == SQLITE_DONE) {
                        inserted++;
                        STATE.patterns_taught++;
                    }
                    sqlite3_finalize(insert);
                }
            }
            sqlite3_finalize(check);
        }
    }
    sqlite3_finalize(stmt);
    
    /* Refresh pattern count once after all inserts */
    RefreshPatternCount();
    
    /* Commit transaction */
    sqlite3_exec(STATE.db, "COMMIT", NULL, NULL, NULL);
    
    return inserted;
}

/* ===== RUN DISPATCH ===== */

int DestructionGuard_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) DestructionGuard_Init();
    
    if (strcmp(cmd, "read_state") == 0) {
        char buf[DG_BUF];
        snprintf(buf, sizeof(buf),
            "[@INITIALIZED]{%d}[@PATTERNS_LOADED]{%d}[@DECISIONS_MADE]{%d}[@PATTERNS_TAUGHT]{%d}[@LEARNING_ENABLED]{%d}[@RISK_THRESHOLD]{%.2f}",
            STATE.initialized, STATE.patterns_loaded, STATE.decisions_made, 
            STATE.patterns_taught, STATE.learning_enabled, STATE.risk_threshold);
        return BclResult_Ok(bcl_out, out_sz, buf);
    }
    
    if (strcmp(cmd, "set_config") == 0) {
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }
    
    if (strcmp(cmd, "evaluate") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        
        char command[DG_MAX_COMMAND] = "";
        BclParser_Extract(&parse, "command", command, sizeof(command));
        
        if (!*command) {
            BclParser_Free(&parse);
            return BclResult_Err(bcl_out, out_sz, 50, "no command provided");
        }
        
        DecisionResult result = DestructionGuard_Evaluate(command);
        
        char buf[DG_BUF];
        const char *action_str = (result.action == ACTION_BLOCK) ? "block" :
                                 (result.action == ACTION_ALLOW) ? "allow" : "warn";
        
        snprintf(buf, sizeof(buf),
            "[@ACTION]{%s}[@RISK]{%.2f}[@CONFIDENCE]{%.2f}[@REASON]{%s}[@MATCHED_PATTERNS]{%s}[@PATTERN_COUNT]{%d}",
            action_str, result.risk_score, result.confidence, 
            result.reason, result.matched_ids, result.pattern_count);
        
        BclParser_Free(&parse);
        return BclResult_Ok(bcl_out, out_sz, buf);
    }
    
    if (strcmp(cmd, "teach_block") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        
        char pattern[DG_MAX_PATTERN] = "";
        char description[DG_MAX_DESC] = "";
        
        BclParser_Extract(&parse, "pattern", pattern, sizeof(pattern));
        BclParser_Extract(&parse, "description", description, sizeof(description));
        
        int ok = DestructionGuard_TeachBlock(pattern, description);
        BclParser_Free(&parse);
        
        if (ok) {
            return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{pattern_added}");
        }
        return BclResult_Err(bcl_out, out_sz, 50, STATE.last_error);
    }
    
    if (strcmp(cmd, "teach_allow") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        
        char pattern[DG_MAX_PATTERN] = "";
        char description[DG_MAX_DESC] = "";
        
        BclParser_Extract(&parse, "pattern", pattern, sizeof(pattern));
        BclParser_Extract(&parse, "description", description, sizeof(description));
        
        int ok = DestructionGuard_TeachAllow(pattern, description);
        BclParser_Free(&parse);
        
        if (ok) {
            return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{pattern_added}");
        }
        return BclResult_Err(bcl_out, out_sz, 50, STATE.last_error);
    }
    
    if (strcmp(cmd, "teach_list") == 0) {
        char buf[8192] = "[@PATTERNS]{";
        size_t buf_len = strlen(buf);
        
        sqlite3_stmt *stmt;
        int rc = sqlite3_prepare_v2(STATE.db,
            "SELECT pattern, action, severity, confidence, source FROM patterns "
            "ORDER BY severity DESC, confidence DESC", -1, &stmt, NULL);
        if (rc != SQLITE_OK) {
            return BclResult_Err(bcl_out, out_sz, 50, "Database error");
        }
        
        int first = 1;
        while (sqlite3_step(stmt) == SQLITE_ROW) {
            if (!first) {
                if (buf_len < sizeof(buf) - 2) {
                    buf[buf_len++] = ';';
                    buf[buf_len] = '\0';
                }
            }
            first = 0;
            
            const char *pattern = (const char*)sqlite3_column_text(stmt, 0);
            const char *action = (const char*)sqlite3_column_text(stmt, 1);
            int severity = sqlite3_column_int(stmt, 2);
            double confidence = sqlite3_column_double(stmt, 3);
            const char *source = (const char*)sqlite3_column_text(stmt, 4);
            
            char line[DG_BUF];
            int line_len = snprintf(line, sizeof(line), "(%s;%s;%d;%.2f;%s)",
                     pattern, action, severity, confidence, source);
            
            if (buf_len + line_len < sizeof(buf) - 2) {
                memcpy(buf + buf_len, line, line_len);
                buf_len += line_len;
                buf[buf_len] = '\0';
            } else {
                /* Truncation warning */
                break;
            }
        }
        sqlite3_finalize(stmt);
        
        if (buf_len >= sizeof(buf) - 10) {
            /* Add truncation indicator */
            snprintf(buf + buf_len, sizeof(buf) - buf_len, "[TRUNCATED]");
        }
        
        if (buf_len < sizeof(buf) - 1) {
            buf[buf_len++] = '}';
            buf[buf_len] = '\0';
        }
        return BclResult_Ok(bcl_out, out_sz, buf);
    }
    
    if (strcmp(cmd, "teach_stats") == 0) {
        char buf[DG_BUF];
        snprintf(buf, sizeof(buf),
            "[@TOTAL_PATTERNS]{%d}[@DECISIONS_MADE]{%d}[@PATTERNS_TAUGHT]{%d}",
            STATE.patterns_loaded, STATE.decisions_made, STATE.patterns_taught);
        return BclResult_Ok(bcl_out, out_sz, buf);
    }
    
    if (strcmp(cmd, "auto_learn") == 0) {
        int suggestions = DestructionGuard_AutoLearn();
        char buf[DG_BUF];
        snprintf(buf, sizeof(buf), "[@SUGGESTIONS]{%d}", suggestions);
        return BclResult_Ok(bcl_out, out_sz, buf);
    }
    
    return BclResult_Err(bcl_out, out_sz, 50, "unknown command");
}

/* ===== CLOSE ===== */

int DestructionGuard_Close(void) {
    /* Free cached regex patterns */
    for (int i = 0; i < STATE.regex_cache_count; i++) {
        if (STATE.regex_cache[i].is_compiled) {
            regfree(&STATE.regex_cache[i].compiled);
        }
    }
    STATE.regex_cache_count = 0;
    
    if (STATE.db) {
        sqlite3_close(STATE.db);
        STATE.db = NULL;
    }
    
    if (STATE.cmd_db) {
        sqlite3_close(STATE.cmd_db);
        STATE.cmd_db = NULL;
    }
    
    /* Clear all state fields with memset */
    memset(&STATE, 0, sizeof(STATE));
    STATE.risk_threshold = DG_RISK_THRESHOLD;  /* Restore default */
    
    return 1;
}

/* ===== STATE ===== */

const char * DestructionGuard_State(void) {
    static char buf[DG_BUF];
    snprintf(buf, sizeof(buf),
        "DestructionGuard: initialized=%d patterns=%d decisions=%d taught=%d learning=%d threshold=%.2f",
        STATE.initialized, STATE.patterns_loaded, STATE.decisions_made,
        STATE.patterns_taught, STATE.learning_enabled, STATE.risk_threshold);
    return buf;
}
