//[@GHOST]{file_path="Cascade_toolStack/bcl_units/vbast.h" date="2026-07-04" author="Devin" session_id="bcl-vbast-units" context="Shared declarations for VBAST bcl_units — constants, data structures, function prototypes for all 5 vbast units"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
//[@FILEID]{id="vbast.h" domain="bcl_units" authority="VbastHeader"}
//[@SUMMARY]{summary="Shared header for 5 VBAST bcl_units — constants, data structures (ClassInfo, MethodInfo, EdgeInfo, ParseResult), function declarations"}
//[@CLASS]{class="VbastHeader" domain="bcl_units" authority="shared"}
//[@METHOD]{methods="constants,structs,prototypes,language_detection,shared_helpers"}
//
// vbast.h — Shared declarations for VBAST bcl_units
//
// 5 bcl_units share this header:
//   bcl_ast_walker.c    — tree-sitter parse, extract classes/methods/signatures
//   bcl_vbstyle_check.c — 11 VBStyle compliance checks using AST data
//   bcl_graph_builder.c — call/state/import graph edges from AST
//   bcl_bcl_stamper.c   — generate BCL header stamps from AST
//   bcl_mysql_store.c   — write to bcl_classes, bcl_methods, bcl_edges tables
//
// The ast_walker unit owns the tree-sitter parsing. The other 4 units
// call ast_init/ast_parse_file/ast_free to parse, then do their specific work.

#ifndef VBAST_H
#define VBAST_H

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

/* mysql_store.c */
int    mysql_store_results(ParseResult *r, const char *db_name);
int    mysql_store_classes(ParseResult *r, void *conn, int codebase_id);
int    mysql_store_methods(ParseResult *r, void *conn, int codebase_id);
int    mysql_store_edges(ParseResult *r, void *conn, int codebase_id);

/* vbast.c — helpers shared across modules */
char * read_file(const char *path, char *buf, size_t bufsize);
int    line_for_offset(const char *content, int offset);
void   trim(char *s);

#endif /* VBAST_H */
