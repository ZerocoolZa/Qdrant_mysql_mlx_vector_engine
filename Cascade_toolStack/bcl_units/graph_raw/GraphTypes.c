//[@GHOST]{file_path="core/Dom_Bcl_C_ver/bcl_engine.h" date="2026-06-29" author="Devin" session_id="bcl-c-central-db" context="Shared declarations for BCL C engine — constants, data structures, function prototypes for all modules"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="bcl_engine.h" domain="bcl_c_engine" authority="GraphTypes"}
//[@SUMMARY]{summary="Shared header — constants, data structures (ClassInfo, MethodInfo, EdgeInfo, ParseResult), function declarations for all BCL C engine modules"}
//
// Modules:
//   bcl_ingestion_engine.c — tree-sitter walk, extract classes/methods/signatures
//   bcl_stamper.c          — generate [@GHOST]/[@VBSTYLE]/[@CLASS]/[@METHOD] headers
//   bcl_graph_builder.c    — call edges, state edges, import edges from AST
//   bcl_static_analyzer.c  — 11 VBStyle compliance checks (ported from vbcheck.c)
//   bcl_graph_store.c      — write to bcl_classes, bcl_methods, bcl_edges, bcl_units
//   bcl_engine_cli.c       — CLI dispatch, flags, orchestration
//
// Compile: see Makefile

#ifndef BCL_ENGINE_H
#define BCL_ENGINE_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "tree_sitter/api.h"
#include "tree_sitter/tree-sitter-python.h"
#include "tree_sitter/tree-sitter-c.h"

/* ════════════════════════════════════════════
 * CONSTANTS
 * ════════════════════════════════════════════ */

#define VBAST_BUF          65536
#define VBAST_MAXBUF       1048576
#define VBAST_MAX_CLASSES  256
#define VBAST_MAX_METHODS  2048
#define VBAST_MAX_EDGES    8192
#define VBAST_MAX_IMPORTS  128
#define VBAST_MAX_VIOLATIONS 1024
#define VBAST_MAX_NAME     128
#define VBAST_MAX_SIG      512
#define VBAST_MAX_LINE     1024

/* ════════════════════════════════════════════
 * LANGUAGE DETECTION
 * ════════════════════════════════════════════ */

typedef enum {
    LANG_PYTHON = 0,
    LANG_C = 1,
    LANG_UNKNOWN = 2
} Language;

/* ════════════════════════════════════════════
 * DATA STRUCTURES
 * ════════════════════════════════════════════ */

typedef struct {
    char name[VBAST_MAX_NAME];
    char bases[VBAST_MAX_SIG];       /* inheritance: "Foo, Bar" or empty */
    int  line_start;
    int  line_end;
    int  method_count;
    int  has_run;
    int  has_state_dict;
    int  has_mem_param;
    int  has_ghost;
    int  has_vbstyle;
    int  has_decorator;
    int  db_id;                      /* MySQL row id (set by mysql_store) */
} ClassInfo;

typedef struct {
    char name[VBAST_MAX_NAME];
    char class_name[VBAST_MAX_NAME];
    char signature[VBAST_MAX_SIG];   /* "self, mem, db, param" */
    int  line_start;
    int  line_end;
    int  has_tuple3;                 /* returns (1, ..., None) or (0, None, ...) */
    int  has_print;
    int  has_decorator;
    int  has_type_hint;
    int  is_async;
    int  db_id;                      /* MySQL row id (set by mysql_store) */
} MethodInfo;

typedef struct {
    char source[VBAST_MAX_NAME];     /* "ClassName.method_name" */
    char target[VBAST_MAX_NAME];     /* "self.foo" or "Bar.baz" or "os.path" */
    char edge_type[32];              /* "CALL", "STATE_READ", "STATE_WRITE", "IMPORT" */
    char certainty[16];              /* "CERTAIN", "PROBABLE" */
    int  line_number;
} EdgeInfo;

typedef struct {
    char module[VBAST_MAX_NAME];
    char alias[VBAST_MAX_NAME];
    int  line_number;
} ImportInfo;

typedef struct {
    char rule_name[64];
    char severity[16];               /* "error" or "warn" */
    char details[512];
    int  line_num;
} Violation;

typedef struct {
    char file_path[VBAST_MAX_LINE];
    char *source;                     /* file content */
    size_t source_len;
    Language language;                /* detected language (PYTHON, C, UNKNOWN) */
    ClassInfo  classes[VBAST_MAX_CLASSES];
    int class_count;
    MethodInfo methods[VBAST_MAX_METHODS];
    int method_count;
    EdgeInfo   edges[VBAST_MAX_EDGES];
    int edge_count;
    ImportInfo imports[VBAST_MAX_IMPORTS];
    int import_count;
    Violation  violations[VBAST_MAX_VIOLATIONS];
    int violation_count;
} ParseResult;

/* ════════════════════════════════════════════
 * FUNCTION DECLARATIONS
 * ════════════════════════════════════════════ */

/* ast_walker.c */
void   ast_init(ParseResult *r, const char *file_path);
int    ast_parse_file(ParseResult *r);
void   ast_free(ParseResult *r);
void   ast_print(ParseResult *r);
Language detect_language(const char *file_path);

/* bcl_stamper.c */
void   bcl_stamp_ghost(ParseResult *r, char *out, size_t out_sz);
void   bcl_stamp_vbstyle(ParseResult *r, char *out, size_t out_sz);
void   bcl_stamp_classes(ParseResult *r, char *out, size_t out_sz);
void   bcl_stamp_methods(ParseResult *r, char *out, size_t out_sz);
void   bcl_stamp_all(ParseResult *r, char *out, size_t out_sz);

/* graph_builder.c */
void   graph_build_edges(ParseResult *r);
void   graph_print(ParseResult *r);

/* vbstyle_check.c */
void   check_vbstyle(ParseResult *r);
void   check_print_violations(ParseResult *r);
int    check_pass_count(ParseResult *r);
int    check_fail_count(ParseResult *r);

/* bcl_graph_store.c — unified store (MySQL + SQLite + :memory:) */
int    store_results(ParseResult *r, const char *db_name);
int    store_source(ParseResult *r);
/* legacy MySQL-specific (used internally, kept for compatibility) */
int    mysql_store_results(ParseResult *r, const char *db_name);
int    mysql_store_classes(ParseResult *r, void *conn, int codebase_id);
int    mysql_store_methods(ParseResult *r, void *conn, int codebase_id);
int    mysql_store_edges(ParseResult *r, void *conn, int codebase_id);

/* bcl_engine_cli.c — helpers shared across modules */
char * read_file(const char *path, char *buf, size_t bufsize);
int    line_for_offset(const char *content, int offset);
void   trim(char *s);

/* bcl_config.c — runtime config reader (backend selectable: sqlite | mysql)
 * BclConfig struct is defined in bcl_config.c — use void* from other units. */
int          config_load(void *cfg, const char *path);
const char * config_get(void *cfg, const char *key);
int          config_get_int(void *cfg, const char *key, int default_val);
int          config_set(void *cfg, const char *key, const char *value);
int          config_save(void *cfg, const char *path);
void         config_free(void *cfg);
int          config_init_global(const char *path);
const char * config_get_global(const char *key);
int          config_get_global_int(const char *key, int default_val);
const char * config_global_backend(void);
const char * config_global_db_path(void);
const char * config_global_db_host(void);
const char * config_global_db_user(void);
const char * config_global_db_table(void);
int          config_global_db_port(void);
const char * config_global_domain(void);
void         config_free_global(void);

/* ════════════════════════════════════════════
 * BCL PARSER — syntax only (bcl_parser.c)
 * Knows ONLY [@TAG]{content} bracket syntax.
 * Does NOT know what RUN, CMD, RESULT mean.
 * All semantics are in the dictionary + validator.
 * ════════════════════════════════════════════ */

#define BCL_MAX_NODES    256
#define BCL_MAX_CONTENT  4096
#define BCL_MAX_TAG      64
#define BCL_MAX_DEPTH    32
#define BCL_MAX_BCL      65536
#define BCL_MAX_RESULT   65536

typedef struct {
    char tag[BCL_MAX_TAG];
    char content[BCL_MAX_CONTENT];
    int  start_pos;
    int  end_pos;
    int  depth;
    int  parent_idx;            /* -1 = root */
    int  child_count;
    int  children[32];          /* indices into BclParseResult.nodes */
} BclNode;

typedef struct {
    BclNode nodes[BCL_MAX_NODES];
    int     node_count;
    int     parse_ok;
    char    error_msg[256];
    int     error_pos;
} BclParseResult;

void   BclParser_Init(BclParseResult *p);
int    BclParser_Parse(BclParseResult *p, const char *bcl_text);  /* returns 1=ok, 0=error */
int    BclParser_Validate(BclParseResult *p);  /* syntax check only — no semantic validation */
int    BclParser_Extract(BclParseResult *p, const char *tag, char *out, size_t out_sz);
void   BclParser_Free(BclParseResult *p);

/* ════════════════════════════════════════════
 * BCL DICTIONARY — grammar (bcl_dictionary.c)
 * Rich schema: bcl_id, symbol, namespace, parent_tag,
 * children_allowed, required, repeatable, max_count, datatype, validator.
 * Phase 1: tag lookup + valid_in. Phase 2: semantic rules. Phase 3: generation.
 * ════════════════════════════════════════════ */

#define DICT_MAX_TAG       64
#define DICT_MAX_CATEGORY  32
#define DICT_MAX_NAMESPACE 16
#define DICT_MAX_PATH      4096
#define DICT_MAX_RESULT    65536
#define DICT_TAG_COUNT     94

typedef struct {
    char db_path[DICT_MAX_PATH];
    void *conn;                 /* sqlite3* — void to avoid header dependency */
    int  initialized;
} BclDictionary;

/* Dictionary dispatch commands (for BclDictionary_Run) */
typedef enum {
    DICT_CMD_POPULATE = 0,
    DICT_CMD_LOOKUP,
    DICT_CMD_IS_VALID_TAG,
    DICT_CMD_IS_VALID_IN,
    DICT_CMD_GET_RULE,
    DICT_CMD_COUNT,
    DICT_CMD_READ_STATE,
    DICT_CMD_SET_CONFIG,
    DICT_CMD_COUNT_TOTAL
} DictCommand;

void   BclDictionary_Init(BclDictionary *d, const char *db_path);
void   BclDictionary_Close(BclDictionary *d);
int    BclDictionary_Populate(BclDictionary *d);  /* create tables + insert 94 tags */
int    BclDictionary_Lookup(BclDictionary *d, const char *tag,
                            char *namespace_out, char *valid_in_out,
                            char *parent_out, char *children_out,
                            int *required, int *repeatable, int *max_count,
                            char *datatype_out);
int    BclDictionary_IsValidTag(BclDictionary *d, const char *tag);
int    BclDictionary_IsValidIn(BclDictionary *d, const char *tag, const char *context);
int    BclDictionary_GetRule(BclDictionary *d, const char *parent_tag,
                             const char *child_tag,
                             int *required, int *min_count, int *max_count);
int    BclDictionary_Count(BclDictionary *d);
const char *BclDictionary_Run(BclDictionary *d, DictCommand cmd, const char *bcl_in);

/* ════════════════════════════════════════════
 * BCL VALIDATOR — semantic checks (bcl_validator.c)
 * Takes parsed node tree, checks against dictionary rules.
 * Parser → Validator → Runtime.
 * ════════════════════════════════════════════ */

#define VAL_MAX_ERRORS   64
#define VAL_MAX_MSG      512

typedef struct {
    char tag[BCL_MAX_TAG];
    char problem[VAL_MAX_MSG];
    char solution[VAL_MAX_MSG];
    int  node_idx;
} ValidationError;

typedef struct {
    ValidationError errors[VAL_MAX_ERRORS];
    int error_count;
    int is_valid;
} ValidationResult;

void   BclValidator_Init(ValidationResult *v);
int    BclValidator_Validate(ValidationResult *v, BclParseResult *tree,
                             BclDictionary *dict);  /* returns 1=valid, 0=invalid */
void   BclValidator_Print(ValidationResult *v);

/* ════════════════════════════════════════════
 * MEM UNIT — in-RAM SQLite :memory: orchestration bus (bcl_mem_unit.c)
 * One C file, one SQLite connection, 6 tables, 6 sections:
 *   mu_commands | mu_results | mu_events | mu_state | mu_errors | mu_cli_registry
 * ════════════════════════════════════════════ */

#define MU_MAX_TARGET   64
#define MU_MAX_CMD      128
#define MU_MAX_BCL      65536
#define MU_MAX_KEY      128
#define MU_MAX_VAL      4096

typedef struct {
    void *conn;                 /* sqlite3* :memory: connection */
    int   initialized;
    int   command_count;
    int   result_count;
    int   event_count;
} MemUnit;

void   MemUnit_Init(MemUnit *mu);
void   MemUnit_Close(MemUnit *mu);
int    MemUnit_Dispatch(MemUnit *mu, const char *target_unit,
                        const char *command, const char *bcl_in,
                        char *bcl_out, size_t out_sz);
int    MemUnit_RegisterCommand(MemUnit *mu, const char *cmd_key,
                               const char *target_unit, const char *help_text,
                               const char *category, int requires_param,
                               const char *param_example);
int    MemUnit_SetState(MemUnit *mu, const char *key, const char *value);
const char * MemUnit_GetState(MemUnit *mu, const char *key);
int    MemUnit_LogError(MemUnit *mu, int command_id, int error_code,
                        const char *error_desc, const char *error_unit,
                        const char *error_input, const char *error_context,
                        const char *problem, const char *solution);
int    MemUnit_CommandCount(MemUnit *mu);
int    MemUnit_ResultCount(MemUnit *mu);

#endif /* BCL_ENGINE_H */
