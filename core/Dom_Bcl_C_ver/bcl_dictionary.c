//[@GHOST]{file_path="core/Dom_Bcl_C_ver/bcl_dictionary.c" date="2026-06-29" author="cascade+devin" session_id="bcl-c-central-db" context="BCL C Engine Layer 1 — rich grammar dictionary with 94 tag definitions, 8 namespaces, parent/child rules, required/repeatable/max_count for Phase 1/2/3 validation"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_dictionary.c" domain="bcl_c_engine" authority="BclDictionary"}
//[@SUMMARY]{summary="BCL tag registry: 94 tags across 8 namespaces. Rich grammar schema with bcl_id, parent_tag, children_allowed, required, repeatable, max_count, datatype, validator. SQLite-backed. Phase 1: tag lookup. Phase 2: semantic rules. Phase 3: parser generation."}
//[@CLASS]{class="BclDictionary" domain="bcl_c_engine" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Populate" type="command"}
//[@METHOD]{method="Lookup" type="command"}
//[@METHOD]{method="IsValidTag" type="command"}
//[@METHOD]{method="IsValidIn" type="command"}
//[@METHOD]{method="GetRule" type="command"}
//[@METHOD]{method="Count" type="command"}
//[@METHOD]{method="Close" type="command"}
//[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Rich grammar schema. 94 tags, 8 namespaces, parent/child rules.>][@todos<none>]}

#include "bcl_engine.h"
#include <sqlite3.h>

/* ===== DIM BLOCK (declarations) ===== */

#define DB_DEFAULT_PATH "dom_graph_work.db"

/* Namespaces */
#define NS_CMD   "cmd"
#define NS_COMM  "comm"
#define NS_CFG   "cfg"
#define NS_CSTR  "cstr"
#define NS_CTRL  "ctrl"
#define NS_DESC  "desc"
#define NS_KNOW  "know"
#define NS_GRAPH "graph"

/* valid_in values */
#define VI_HEADER "header"
#define VI_BODY   "body"
#define VI_PARAM  "param"
#define VI_RESULT "result"
#define VI_ANY    "any"

/* datatypes */
#define DT_CONTAINER "container"
#define DT_STRING    "string"
#define DT_INT       "int"
#define DT_TUPLE     "tuple"
#define DT_BOOL      "bool"

/* Tag definition with full grammar rules */
typedef struct {
    const char *bcl_id;         /* "BCL0001" — stable ID */
    const char *symbol;         /* "RUN" — display name */
    const char *namespace;      /* "cmd", "comm", "cfg", etc. */
    const char *category;       /* sub-category within namespace */
    const char *valid_in;       /* header, body, param, result, any */
    const char *parent_tag;     /* which tag contains this (or "ROOT") */
    const char *children;       /* comma-separated child tags, or "*" */
    int   required;             /* 1 if must appear when parent is used */
    int   repeatable;           /* 1 if can appear multiple times */
    int   max_count;            /* 0 = unlimited, N = max */
    const char *datatype;       /* container, string, int, tuple, bool */
    const char *validator;      /* validator function name or NULL */
    const char *doc;            /* short description */
} TagDefRich;

/* ===== TAG DEFINITIONS (94 tags, rich grammar) ===== */

static const TagDefRich TAG_TABLE[DICT_TAG_COUNT] = {
    /* === IDENTITY / desc namespace (10) === */
    {"BCL0010", "GHOST",       NS_DESC, "IDENTITY",     VI_HEADER, "ROOT", "*",              1, 0, 1, DT_CONTAINER, NULL, "File identity: path, date, author, session, context"},
    {"BCL0011", "VBSTYLE",     NS_DESC, "IDENTITY",     VI_HEADER, "ROOT", "*",              1, 0, 1, DT_CONTAINER, NULL, "VBStyle standard declaration"},
    {"BCL0012", "FILEID",      NS_DESC, "IDENTITY",     VI_HEADER, "ROOT", "*",              1, 0, 1, DT_CONTAINER, NULL, "File ID: id, domain, authority"},
    {"BCL0013", "SUMMARY",     NS_DESC, "IDENTITY",     VI_HEADER, "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "File summary description"},
    {"BCL0014", "CLASS",       NS_DESC, "IDENTITY",     VI_HEADER, "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Class declaration metadata"},
    {"BCL0015", "METHOD",      NS_DESC, "IDENTITY",     VI_HEADER, "ROOT", "*",              0, 1, 0, DT_CONTAINER, NULL, "Method declaration metadata"},
    {"BCL0016", "REVIEW",      NS_DESC, "IDENTITY",     VI_HEADER, "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Code review metadata"},
    {"BCL0017", "AUTHOR",      NS_DESC, "IDENTITY",     VI_HEADER, "ROOT", "*",              0, 0, 1, DT_STRING,    NULL, "Author name"},
    {"BCL0018", "DATE",        NS_DESC, "IDENTITY",     VI_HEADER, "ROOT", "*",              0, 0, 1, DT_STRING,    NULL, "Date stamp"},
    {"BCL0019", "SESSION",     NS_DESC, "IDENTITY",     VI_HEADER, "ROOT", "*",              0, 0, 1, DT_STRING,    NULL, "Session ID"},

    /* === COMMAND / cmd namespace (8) === */
    {"BCL0001", "RUN",         NS_CMD,  "COMMAND",      VI_BODY,   "ROOT", "CMD,PARAM",      0, 1, 0, DT_CONTAINER, "RunPacket", "Execute a command packet"},
    {"BCL0002", "CMD",         NS_CMD,  "COMMAND",      VI_BODY,   "RUN",  "*",              1, 0, 1, DT_STRING,    NULL, "Command name (e.g. dict.init)"},
    {"BCL0003", "PARAM",       NS_CMD,  "COMMAND",      VI_BODY,   "RUN",  "*",              0, 1, 0, DT_CONTAINER, NULL, "Parameters block"},
    {"BCL0004", "BCL_VER",     NS_CMD,  "COMMAND",      VI_BODY,   "ROOT", "*",              0, 0, 1, DT_STRING,    NULL, "BCL version"},
    {"BCL0005", "DISPATCH",    NS_CMD,  "COMMAND",      VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Dispatch directive"},
    {"BCL0006", "EXECUTE",     NS_CMD,  "COMMAND",      VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Execute directive (alias of RUN)"},
    {"BCL0007", "QUERY",       NS_CMD,  "COMMAND",      VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Query directive"},
    {"BCL0008", "SCAN",        NS_CMD,  "COMMAND",      VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Scan directive"},

    /* === RESULT / comm namespace (10) === */
    {"BCL0020", "OK",          NS_COMM, "RESULT",       VI_RESULT, "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Success result packet"},
    {"BCL0021", "ERR",         NS_COMM, "RESULT",       VI_RESULT, "ROOT", "CODE,DESC",      0, 0, 1, DT_CONTAINER, NULL, "Error result packet"},
    {"BCL0022", "RESULT",      NS_COMM, "RESULT",       VI_RESULT, "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Generic result wrapper"},
    {"BCL0023", "STATE",       NS_COMM, "RESULT",       VI_RESULT, "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "State dump"},
    {"BCL0024", "CONFIG",      NS_COMM, "RESULT",       VI_RESULT, "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Configuration dump"},
    {"BCL0025", "COUNT",       NS_COMM, "RESULT",       VI_RESULT, "ROOT", "*",              0, 0, 1, DT_INT,       NULL, "Count value"},
    {"BCL0026", "FILES",       NS_COMM, "RESULT",       VI_RESULT, "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "File list"},
    {"BCL0027", "NODES",       NS_COMM, "RESULT",       VI_RESULT, "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Node list"},
    {"BCL0028", "EDGES",       NS_COMM, "RESULT",       VI_RESULT, "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Edge list"},
    {"BCL0029", "GRAPH",       NS_COMM, "RESULT",       VI_RESULT, "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Graph result"},

    /* === CODE_STRUCTURE / graph namespace (12) === */
    {"BCL0030", "CLASSES",     NS_GRAPH, "CODE_STRUCTURE", VI_BODY, "ROOT", "*",             0, 0, 1, DT_CONTAINER, NULL, "Class list"},
    {"BCL0031", "METHODS",     NS_GRAPH, "CODE_STRUCTURE", VI_BODY, "ROOT", "*",             0, 0, 1, DT_CONTAINER, NULL, "Method list"},
    {"BCL0032", "CALLS",       NS_GRAPH, "CODE_STRUCTURE", VI_BODY, "ROOT", "*",             0, 0, 1, DT_CONTAINER, NULL, "Call list"},
    {"BCL0033", "FLOW",        NS_GRAPH, "CODE_STRUCTURE", VI_BODY, "ROOT", "*",             0, 0, 1, DT_CONTAINER, NULL, "Flow list"},
    {"BCL0034", "INHERITANCE", NS_GRAPH, "CODE_STRUCTURE", VI_BODY, "ROOT", "*",             0, 0, 1, DT_CONTAINER, NULL, "Inheritance list"},
    {"BCL0035", "IMPORTS",     NS_GRAPH, "CODE_STRUCTURE", VI_BODY, "ROOT", "*",             0, 0, 1, DT_CONTAINER, NULL, "Import list"},
    {"BCL0036", "DECORATORS",  NS_GRAPH, "CODE_STRUCTURE", VI_BODY, "ROOT", "*",             0, 0, 1, DT_CONTAINER, NULL, "Decorator list"},
    {"BCL0037", "SIGNATURES",  NS_GRAPH, "CODE_STRUCTURE", VI_BODY, "ROOT", "*",             0, 0, 1, DT_CONTAINER, NULL, "Signature list"},
    {"BCL0038", "RETURNS",     NS_GRAPH, "CODE_STRUCTURE", VI_BODY, "ROOT", "*",             0, 0, 1, DT_CONTAINER, NULL, "Return list"},
    {"BCL0039", "ARGS",        NS_GRAPH, "CODE_STRUCTURE", VI_BODY, "ROOT", "*",             0, 0, 1, DT_CONTAINER, NULL, "Argument list"},
    {"BCL0040", "VARIABLES",   NS_GRAPH, "CODE_STRUCTURE", VI_BODY, "ROOT", "*",             0, 0, 1, DT_CONTAINER, NULL, "Variable list"},
    {"BCL0041", "CONSTANTS",   NS_GRAPH, "CODE_STRUCTURE", VI_BODY, "ROOT", "*",             0, 0, 1, DT_CONTAINER, NULL, "Constant list"},

    /* === IR / graph namespace (6) === */
    {"BCL0042", "BCL_STAMP",   NS_GRAPH, "IR",          VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "BCL stamp"},
    {"BCL0043", "IRNODE",      NS_GRAPH, "IR",          VI_BODY,   "ROOT", "*",              0, 1, 0, DT_CONTAINER, NULL, "IR node"},
    {"BCL0044", "ENDNODE",     NS_GRAPH, "IR",          VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "End IR node"},
    {"BCL0045", "FIELD",       NS_GRAPH, "IR",          VI_BODY,   "ROOT", "*",              0, 1, 0, DT_STRING,    NULL, "IR field"},
    {"BCL0046", "CERTAINTY",   NS_GRAPH, "IR",          VI_BODY,   "ROOT", "*",              0, 0, 1, DT_STRING,    NULL, "Certainty level"},
    {"BCL0047", "PROVENANCE",  NS_GRAPH, "IR",          VI_BODY,   "ROOT", "*",              0, 0, 1, DT_STRING,    NULL, "Provenance info"},

    /* === GUI / desc namespace (6) === */
    {"BCL0048", "GUI",         NS_DESC, "GUI",          VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "GUI container"},
    {"BCL0049", "WIDGET",      NS_DESC, "GUI",          VI_BODY,   "GUI",  "*",              0, 1, 0, DT_CONTAINER, NULL, "Widget definition"},
    {"BCL0050", "SIGNAL",      NS_DESC, "GUI",          VI_BODY,   "GUI",  "*",              0, 1, 0, DT_STRING,    NULL, "Signal definition"},
    {"BCL0051", "LAYOUT",      NS_DESC, "GUI",          VI_BODY,   "GUI",  "*",              0, 0, 1, DT_CONTAINER, NULL, "Layout definition"},
    {"BCL0052", "BIND",        NS_DESC, "GUI",          VI_BODY,   "GUI",  "*",              0, 1, 0, DT_STRING,    NULL, "Bind definition"},
    {"BCL0053", "EVENT",       NS_DESC, "GUI",          VI_BODY,   "GUI",  "*",              0, 1, 0, DT_STRING,    NULL, "Event definition"},

    /* === CHAT / know namespace (12) === */
    {"BCL0054", "USER_SAYS",   NS_KNOW, "CHAT",         VI_BODY,   "ROOT", "*",              0, 0, 1, DT_STRING,    NULL, "User statement"},
    {"BCL0055", "AI_SAYS",     NS_KNOW, "CHAT",         VI_BODY,   "ROOT", "*",              0, 0, 1, DT_STRING,    NULL, "AI statement"},
    {"BCL0056", "MOOD",        NS_KNOW, "CHAT",         VI_BODY,   "ROOT", "*",              0, 0, 1, DT_STRING,    NULL, "Mood indicator"},
    {"BCL0057", "INTENT",      NS_KNOW, "CHAT",         VI_BODY,   "ROOT", "*",              0, 0, 1, DT_STRING,    NULL, "Intent classification"},
    {"BCL0058", "TOKENS",      NS_KNOW, "CHAT",         VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Token list"},
    {"BCL0059", "SUCCESS",     NS_KNOW, "CHAT",         VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Success indicator"},
    {"BCL0060", "FAILED",      NS_KNOW, "CHAT",         VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Failure indicator"},
    {"BCL0061", "AI_CORRECT",  NS_KNOW, "CHAT",         VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "AI correct indicator"},
    {"BCL0062", "AI_WRONG",    NS_KNOW, "CHAT",         VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "AI wrong indicator"},
    {"BCL0063", "USER_PREF",   NS_KNOW, "CHAT",         VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "User preference"},
    {"BCL0064", "UNRESOLVED",  NS_KNOW, "CHAT",         VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Unresolved indicator"},
    {"BCL0065", "QUESTION",    NS_KNOW, "CHAT",         VI_BODY,   "ROOT", "*",              0, 0, 1, DT_STRING,    NULL, "Question"},

    /* === KNOWLEDGE / know namespace (8) === */
    {"BCL0066", "PROBLEM",     NS_KNOW, "KNOWLEDGE",    VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Problem definition"},
    {"BCL0067", "SOLUTION",    NS_KNOW, "KNOWLEDGE",    VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Solution definition"},
    {"BCL0068", "LESSON",      NS_KNOW, "KNOWLEDGE",    VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Lesson learned"},
    {"BCL0069", "ROOT_CAUSE",  NS_KNOW, "KNOWLEDGE",    VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Root cause"},
    {"BCL0070", "DECISION",    NS_KNOW, "KNOWLEDGE",    VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Decision record"},
    {"BCL0071", "FIX",         NS_KNOW, "KNOWLEDGE",    VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Fix record"},
    {"BCL0072", "ERROR",       NS_KNOW, "KNOWLEDGE",    VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Error record"},
    {"BCL0073", "GAP",         NS_KNOW, "KNOWLEDGE",    VI_BODY,   "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Gap indicator"},

    /* === META / desc namespace (12) === */
    {"BCL0074", "META",        NS_DESC, "META",         VI_ANY,    "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Meta container"},
    {"BCL0075", "CORE",        NS_DESC, "META",         VI_ANY,    "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Core metadata"},
    {"BCL0076", "STATS",       NS_DESC, "META",         VI_ANY,    "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Statistics"},
    {"BCL0077", "SPEC",        NS_DESC, "META",         VI_ANY,    "ROOT", "*",              0, 0, 1, DT_CONTAINER, NULL, "Specification"},
    {"BCL0078", "VERSION",     NS_DESC, "META",         VI_ANY,    "ROOT", "*",              0, 0, 1, DT_STRING,    NULL, "Version string"},
    {"BCL0079", "CONTEXT",     NS_DESC, "META",         VI_ANY,    "ROOT", "*",              0, 0, 1, DT_STRING,    NULL, "Context string"},
    {"BCL0080", "DOMAIN",      NS_DESC, "META",         VI_ANY,    "ROOT", "*",              0, 0, 1, DT_STRING,    NULL, "Domain name"},
    {"BCL0081", "AUTHORITY",   NS_DESC, "META",         VI_ANY,    "ROOT", "*",              0, 0, 1, DT_STRING,    NULL, "Authority name"},
    {"BCL0082", "SOURCE",      NS_DESC, "META",         VI_ANY,    "ROOT", "*",              0, 0, 1, DT_STRING,    NULL, "Source reference"},
    {"BCL0083", "STATUS",      NS_DESC, "META",         VI_ANY,    "ROOT", "*",              0, 0, 1, DT_STRING,    NULL, "Status string"},
    {"BCL0084", "WEIGHT",      NS_DESC, "META",         VI_ANY,    "ROOT", "*",              0, 0, 1, DT_INT,       NULL, "Weight value"},
    {"BCL0085", "CONFIDENCE",  NS_DESC, "META",         VI_ANY,    "ROOT", "*",              0, 0, 1, DT_STRING,    NULL, "Confidence level"},

    /* === PARAM / cfg namespace (10) === */
    {"BCL0086", "DIR",         NS_CFG,  "PARAM",        VI_PARAM,  "PARAM", "*",              0, 0, 1, DT_STRING,    NULL, "Directory path"},
    {"BCL0087", "PATH",        NS_CFG,  "PARAM",        VI_PARAM,  "PARAM", "*",              0, 0, 1, DT_STRING,    NULL, "File path"},
    {"BCL0088", "FILE_ID",     NS_CFG,  "PARAM",        VI_PARAM,  "PARAM", "*",              0, 0, 1, DT_STRING,    NULL, "File ID"},
    {"BCL0089", "DB_PATH",     NS_CFG,  "PARAM",        VI_PARAM,  "PARAM", "*",              0, 0, 1, DT_STRING,    NULL, "Database path"},
    {"BCL0090", "FILE",        NS_CFG,  "PARAM",        VI_PARAM,  "PARAM", "*",              0, 0, 1, DT_STRING,    NULL, "File name"},
    {"BCL0091", "DEPTH",       NS_CFG,  "PARAM",        VI_PARAM,  "PARAM", "*",              0, 0, 1, DT_INT,       NULL, "Depth value"},
    {"BCL0092", "ORDER",       NS_CFG,  "PARAM",        VI_PARAM,  "PARAM", "*",              0, 0, 1, DT_STRING,    NULL, "Order value"},
    {"BCL0093", "TREE",        NS_CFG,  "PARAM",        VI_PARAM,  "PARAM", "*",              0, 0, 1, DT_CONTAINER, NULL, "Tree container"},
    {"BCL0094", "EVIDENCE",    NS_CFG,  "PARAM",        VI_PARAM,  "PARAM", "*",              0, 0, 1, DT_CONTAINER, NULL, "Evidence container"},
    {"BCL0095", "ANSWER",      NS_CFG,  "PARAM",        VI_PARAM,  "PARAM", "*",              0, 0, 1, DT_STRING,    NULL, "Answer value"},
};

/* ===== INIT BLOCK ===== */

static char DICT_RESULT_BUF[DICT_MAX_RESULT];

/* ===== DIM BLOCK (dispatch) ===== */

/* DictCommand enum is defined in bcl_engine.h */

typedef const char *(*DictCmdFn)(BclDictionary *d, const char *bcl_in);

static const char *fn_dict_populate(BclDictionary *d, const char *bcl_in);
static const char *fn_dict_lookup(BclDictionary *d, const char *bcl_in);
static const char *fn_dict_is_valid_tag(BclDictionary *d, const char *bcl_in);
static const char *fn_dict_is_valid_in(BclDictionary *d, const char *bcl_in);
static const char *fn_dict_get_rule(BclDictionary *d, const char *bcl_in);
static const char *fn_dict_count(BclDictionary *d, const char *bcl_in);
static const char *fn_dict_read_state(BclDictionary *d, const char *bcl_in);
static const char *fn_dict_set_config(BclDictionary *d, const char *bcl_in);

static const DictCmdFn DICT_DISPATCH[DICT_CMD_COUNT_TOTAL] = {
    fn_dict_populate,
    fn_dict_lookup,
    fn_dict_is_valid_tag,
    fn_dict_is_valid_in,
    fn_dict_get_rule,
    fn_dict_count,
    fn_dict_read_state,
    fn_dict_set_config,
};

static const char *dict_err(int code, const char *desc) {
    snprintf(DICT_RESULT_BUF, DICT_MAX_RESULT,
        "[@ERR]{[@CODE]{%d}[@DESC]{%s}}", code, desc);
    return DICT_RESULT_BUF;
}

static int dict_open(BclDictionary *d) {
    if (d->conn) return 0;
    if (sqlite3_open(d->db_path, (sqlite3**)&d->conn) != SQLITE_OK) return -1;
    return 0;
}

static int dict_table_exists(BclDictionary *d) {
    sqlite3_stmt *stmt;
    int rc = sqlite3_prepare_v2((sqlite3*)d->conn,
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='bcl_tag_dictionary'",
        -1, &stmt, NULL);
    if (rc != SQLITE_OK) return -1;
    int count = 0;
    if (sqlite3_step(stmt) == SQLITE_ROW) count = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);
    return count;
}

/* ===== DISPATCH BLOCK ===== */

/* BCL in, BCL out — VBStyle Run dispatch */
const char *BclDictionary_Run(BclDictionary *d, DictCommand cmd, const char *bcl_in) {
    if (cmd < 0 || cmd >= DICT_CMD_COUNT_TOTAL)
        return dict_err(1, "unknown_command");
    return DICT_DISPATCH[cmd](d, bcl_in);
}

/* ===== PUBLIC API ===== */

void BclDictionary_Init(BclDictionary *d, const char *db_path) {
    memset(d, 0, sizeof(*d));
    strncpy(d->db_path, db_path ? db_path : DB_DEFAULT_PATH, DICT_MAX_PATH - 1);
    d->conn = NULL;
    d->initialized = 0;
}

void BclDictionary_Close(BclDictionary *d) {
    if (d->conn) {
        sqlite3_close((sqlite3*)d->conn);
        d->conn = NULL;
    }
    d->initialized = 0;
}

int BclDictionary_Populate(BclDictionary *d) {
    if (dict_open(d) != 0) return 0;
    sqlite3 *db = (sqlite3*)d->conn;

    /* Create rich schema table */
    const char *create_sql =
        "CREATE TABLE IF NOT EXISTS bcl_tag_dictionary ("
        "  bcl_id TEXT PRIMARY KEY,"
        "  symbol TEXT NOT NULL,"
        "  namespace TEXT NOT NULL,"
        "  category TEXT NOT NULL,"
        "  valid_in TEXT NOT NULL,"
        "  parent_tag TEXT,"
        "  children_allowed TEXT,"
        "  required INTEGER DEFAULT 0,"
        "  repeatable INTEGER DEFAULT 0,"
        "  max_count INTEGER DEFAULT 0,"
        "  datatype TEXT,"
        "  validator TEXT,"
        "  documentation TEXT,"
        "  status TEXT DEFAULT 'active',"
        "  version TEXT DEFAULT '1.0'"
        ")";
    char *err = NULL;
    if (sqlite3_exec(db, create_sql, NULL, NULL, &err) != SQLITE_OK) {
        if (err) sqlite3_free(err);
        return 0;
    }

    /* Create aliases table */
    const char *alias_sql =
        "CREATE TABLE IF NOT EXISTS bcl_tag_aliases ("
        "  alias TEXT PRIMARY KEY,"
        "  bcl_id TEXT NOT NULL"
        ")";
    if (sqlite3_exec(db, alias_sql, NULL, NULL, &err) != SQLITE_OK) {
        if (err) sqlite3_free(err);
        return 0;
    }

    /* Insert all 94 tags */
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db,
        "INSERT OR REPLACE INTO bcl_tag_dictionary "
        "(bcl_id, symbol, namespace, category, valid_in, parent_tag, children_allowed, "
        " required, repeatable, max_count, datatype, validator, documentation) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        -1, &stmt, NULL) != SQLITE_OK) return 0;

    for (int i = 0; i < DICT_TAG_COUNT; i++) {
        const TagDefRich *t = &TAG_TABLE[i];
        sqlite3_reset(stmt);
        sqlite3_bind_text(stmt, 1, t->bcl_id, -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 2, t->symbol, -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 3, t->namespace, -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 4, t->category, -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 5, t->valid_in, -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 6, t->parent_tag, -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 7, t->children, -1, SQLITE_STATIC);
        sqlite3_bind_int(stmt, 8, t->required);
        sqlite3_bind_int(stmt, 9, t->repeatable);
        sqlite3_bind_int(stmt, 10, t->max_count);
        sqlite3_bind_text(stmt, 11, t->datatype, -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 12, t->validator ? t->validator : "", -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 13, t->doc, -1, SQLITE_STATIC);
        if (sqlite3_step(stmt) != SQLITE_DONE) {
            sqlite3_finalize(stmt);
            return 0;
        }
    }
    sqlite3_finalize(stmt);

    /* Insert aliases (EXECUTE -> RUN) */
    sqlite3_prepare_v2(db, "INSERT OR REPLACE INTO bcl_tag_aliases (alias, bcl_id) VALUES (?, ?)", -1, &stmt, NULL);
    sqlite3_bind_text(stmt, 1, "EXECUTE", -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, "BCL0006", -1, SQLITE_STATIC);
    sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    d->initialized = 1;
    return 1;
}

int BclDictionary_Lookup(BclDictionary *d, const char *tag,
                         char *namespace_out, char *valid_in_out,
                         char *parent_out, char *children_out,
                         int *required, int *repeatable, int *max_count,
                         char *datatype_out) {
    if (dict_open(d) != 0) return 0;
    if (dict_table_exists(d) == 0) return 0;

    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2((sqlite3*)d->conn,
        "SELECT namespace, valid_in, parent_tag, children_allowed, "
        "       required, repeatable, max_count, datatype "
        "FROM bcl_tag_dictionary WHERE symbol = ?",
        -1, &stmt, NULL) != SQLITE_OK) return 0;
    sqlite3_bind_text(stmt, 1, tag, -1, SQLITE_TRANSIENT);

    int found = 0;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        const char *ns   = (const char*)sqlite3_column_text(stmt, 0);
        const char *vi   = (const char*)sqlite3_column_text(stmt, 1);
        const char *par  = (const char*)sqlite3_column_text(stmt, 2);
        const char *ch   = (const char*)sqlite3_column_text(stmt, 3);
        int req          = sqlite3_column_int(stmt, 4);
        int rep          = sqlite3_column_int(stmt, 5);
        int mc           = sqlite3_column_int(stmt, 6);
        const char *dt   = (const char*)sqlite3_column_text(stmt, 7);

        if (namespace_out) { strncpy(namespace_out, ns ? ns : "", DICT_MAX_NAMESPACE - 1); namespace_out[DICT_MAX_NAMESPACE - 1] = '\0'; }
        if (valid_in_out)  { strncpy(valid_in_out, vi ? vi : "", DICT_MAX_CATEGORY - 1); valid_in_out[DICT_MAX_CATEGORY - 1] = '\0'; }
        if (parent_out)    { strncpy(parent_out, par ? par : "", BCL_MAX_TAG - 1); parent_out[BCL_MAX_TAG - 1] = '\0'; }
        if (children_out)  { strncpy(children_out, ch ? ch : "", 255); children_out[255] = '\0'; }
        if (required)      *required = req;
        if (repeatable)    *repeatable = rep;
        if (max_count)     *max_count = mc;
        if (datatype_out)  { strncpy(datatype_out, dt ? dt : "", 32); datatype_out[31] = '\0'; }
        found = 1;
    }
    sqlite3_finalize(stmt);
    return found;
}

int BclDictionary_IsValidTag(BclDictionary *d, const char *tag) {
    if (!tag || !tag[0]) return 0;
    /* Fast path: check compiled table first */
    for (int i = 0; i < DICT_TAG_COUNT; i++) {
        if (strcmp(TAG_TABLE[i].symbol, tag) == 0) return 1;
    }
    /* Check aliases in DB */
    if (dict_open(d) != 0) return 0;
    if (dict_table_exists(d) == 0) return 0;
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2((sqlite3*)d->conn,
        "SELECT 1 FROM bcl_tag_aliases WHERE alias = ?",
        -1, &stmt, NULL) != SQLITE_OK) return 0;
    sqlite3_bind_text(stmt, 1, tag, -1, SQLITE_TRANSIENT);
    int found = (sqlite3_step(stmt) == SQLITE_ROW) ? 1 : 0;
    sqlite3_finalize(stmt);
    return found;
}

int BclDictionary_IsValidIn(BclDictionary *d, const char *tag, const char *context) {
    char valid_in[DICT_MAX_CATEGORY];
    if (!BclDictionary_Lookup(d, tag, NULL, valid_in, NULL, NULL, NULL, NULL, NULL, NULL))
        return 0;
    if (strcmp(valid_in, VI_ANY) == 0) return 1;
    if (strcmp(valid_in, context) == 0) return 1;
    return 0;
}

int BclDictionary_GetRule(BclDictionary *d, const char *parent_tag,
                          const char *child_tag,
                          int *required, int *min_count, int *max_count) {
    /* Look up the child tag to get its rules relative to its parent */
    char ns[DICT_MAX_NAMESPACE], vi[DICT_MAX_CATEGORY], parent[BCL_MAX_TAG], children[256];
    int req, rep, mc;
    char dt[32];

    if (!BclDictionary_Lookup(d, child_tag, ns, vi, parent, children, &req, &rep, &mc, dt))
        return 0;

    /* Check if parent allows this child in its children_allowed list */
    char parent_children[256];
    int p_req, p_rep, p_mc;
    char p_dt[32], p_ns[DICT_MAX_NAMESPACE], p_vi[DICT_MAX_CATEGORY], p_parent[BCL_MAX_TAG];
    if (BclDictionary_Lookup(d, parent_tag, p_ns, p_vi, p_parent, parent_children, &p_req, &p_rep, &p_mc, p_dt)) {
        if (strcmp(parent_children, "*") == 0) {
            /* Parent allows any child */
        } else {
            /* Check if child_tag is in the comma-separated list */
            char *p = parent_children;
            int found = 0;
            while (*p) {
                char tmp[64];
                int len = 0;
                while (*p && *p != ',' && len < 63) { tmp[len++] = *p++; }
                tmp[len] = '\0';
                if (*p == ',') p++;
                if (strcmp(tmp, child_tag) == 0) { found = 1; break; }
            }
            if (!found) return 0;
        }
    }

    if (required)   *required = req ? 1 : 0;
    if (min_count)  *min_count = req ? 1 : 0;
    if (max_count)  *max_count = (mc > 0) ? mc : (rep ? 0 : 1);
    return 1;
}

int BclDictionary_Count(BclDictionary *d) {
    if (dict_open(d) != 0) return DICT_TAG_COUNT;
    if (dict_table_exists(d) == 0) return DICT_TAG_COUNT;
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2((sqlite3*)d->conn,
        "SELECT COUNT(*) FROM bcl_tag_dictionary", -1, &stmt, NULL) != SQLITE_OK)
        return DICT_TAG_COUNT;
    int count = DICT_TAG_COUNT;
    if (sqlite3_step(stmt) == SQLITE_ROW) count = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);
    return count;
}

/* ===== DISPATCH WRAPPER FUNCTIONS (BCL in, BCL out) ===== */

/* Helper: extract [@TAG]{value} from BCL packet */
static int dict_extract_tag(const char *bcl_in, const char *tag, char *out, size_t out_sz) {
    char pattern[80];
    snprintf(pattern, sizeof(pattern), "[@%s]{", tag);
    const char *p = strstr(bcl_in, pattern);
    if (!p) return 0;
    p += strlen(pattern);
    size_t n = 0;
    int depth = 1;
    while (*p && depth > 0 && n < out_sz - 1) {
        if (*p == '{') depth++;
        else if (*p == '}') { depth--; if (depth == 0) break; }
        out[n++] = *p++;
    }
    out[n] = '\0';
    return 1;
}

/* dict.populate — create tables + insert 94 tags. No params. */
static const char *fn_dict_populate(BclDictionary *d, const char *bcl_in) {
    if (BclDictionary_Populate(d)) {
        snprintf(DICT_RESULT_BUF, DICT_MAX_RESULT,
            "[@OK]{[@COUNT]{%d}}", DICT_TAG_COUNT);
        return DICT_RESULT_BUF;
    }
    return dict_err(2, "db_open_failed");
}

/* dict.lookup — look up tag by name. Param: [@TAG]{name} */
static const char *fn_dict_lookup(BclDictionary *d, const char *bcl_in) {
    char tag[BCL_MAX_TAG];
    if (!dict_extract_tag(bcl_in, "TAG", tag, sizeof(tag)))
        return dict_err(4, "missing_param: [@TAG]{name}");
    char ns[DICT_MAX_NAMESPACE], vi[DICT_MAX_CATEGORY], parent[BCL_MAX_TAG], children[256];
    int req, rep, mc;
    char dt[32];
    if (!BclDictionary_Lookup(d, tag, ns, vi, parent, children, &req, &rep, &mc, dt))
        return dict_err(5, "tag_not_found");
    snprintf(DICT_RESULT_BUF, DICT_MAX_RESULT,
        "[@OK]{[@TAG]{%s}[@NAMESPACE]{%s}[@VALID_IN]{%s}[@PARENT]{%s}[@CHILDREN]{%s}"
        "[@REQUIRED]{%d}[@REPEATABLE]{%d}[@MAX_COUNT]{%d}[@DATATYPE]{%s}}",
        tag, ns, vi, parent, children, req, rep, mc, dt);
    return DICT_RESULT_BUF;
}

/* dict.is_valid_tag — check if tag exists. Param: [@TAG]{name} */
static const char *fn_dict_is_valid_tag(BclDictionary *d, const char *bcl_in) {
    char tag[BCL_MAX_TAG];
    if (!dict_extract_tag(bcl_in, "TAG", tag, sizeof(tag)))
        return dict_err(4, "missing_param: [@TAG]{name}");
    int valid = BclDictionary_IsValidTag(d, tag);
    snprintf(DICT_RESULT_BUF, DICT_MAX_RESULT,
        "[@OK]{[@VALID]{%d}[@TAG]{%s}}", valid, tag);
    return DICT_RESULT_BUF;
}

/* dict.is_valid_in — check if tag valid in context. Param: [@TAG]{name}[@CONTEXT]{ctx} */
static const char *fn_dict_is_valid_in(BclDictionary *d, const char *bcl_in) {
    char tag[BCL_MAX_TAG], ctx[DICT_MAX_CATEGORY];
    if (!dict_extract_tag(bcl_in, "TAG", tag, sizeof(tag)))
        return dict_err(4, "missing_param: [@TAG]{name}");
    if (!dict_extract_tag(bcl_in, "CONTEXT", ctx, sizeof(ctx)))
        return dict_err(4, "missing_param: [@CONTEXT]{ctx}");
    int valid = BclDictionary_IsValidIn(d, tag, ctx);
    snprintf(DICT_RESULT_BUF, DICT_MAX_RESULT,
        "[@OK]{[@VALID]{%d}[@TAG]{%s}[@CONTEXT]{%s}}", valid, tag, ctx);
    return DICT_RESULT_BUF;
}

/* dict.get_rule — get parent/child rule. Param: [@PARENT]{tag}[@CHILD]{tag} */
static const char *fn_dict_get_rule(BclDictionary *d, const char *bcl_in) {
    char parent[BCL_MAX_TAG], child[BCL_MAX_TAG];
    if (!dict_extract_tag(bcl_in, "PARENT", parent, sizeof(parent)))
        return dict_err(4, "missing_param: [@PARENT]{tag}");
    if (!dict_extract_tag(bcl_in, "CHILD", child, sizeof(child)))
        return dict_err(4, "missing_param: [@CHILD]{tag}");
    int req, min_c, max_c;
    if (!BclDictionary_GetRule(d, parent, child, &req, &min_c, &max_c))
        return dict_err(5, "rule_not_found");
    snprintf(DICT_RESULT_BUF, DICT_MAX_RESULT,
        "[@OK]{[@PARENT]{%s}[@CHILD]{%s}[@REQUIRED]{%d}[@MIN_COUNT]{%d}[@MAX_COUNT]{%d}}",
        parent, child, req, min_c, max_c);
    return DICT_RESULT_BUF;
}

/* dict.count — return tag count. No params. */
static const char *fn_dict_count(BclDictionary *d, const char *bcl_in) {
    int count = BclDictionary_Count(d);
    snprintf(DICT_RESULT_BUF, DICT_MAX_RESULT,
        "[@OK]{[@COUNT]{%d}}", count);
    return DICT_RESULT_BUF;
}

/* dict.read_state — return unit state. No params. */
static const char *fn_dict_read_state(BclDictionary *d, const char *bcl_in) {
    snprintf(DICT_RESULT_BUF, DICT_MAX_RESULT,
        "[@OK]{[@STATE]{[@DB_PATH]{%s}[@INITIALIZED]{%d}[@TAG_COUNT]{%d}}}",
        d->db_path, d->initialized, DICT_TAG_COUNT);
    return DICT_RESULT_BUF;
}

/* dict.set_config — set config value. Param: [@KEY]{key}[@VALUE]{val} */
static const char *fn_dict_set_config(BclDictionary *d, const char *bcl_in) {
    char key[BCL_MAX_TAG], value[DICT_MAX_PATH];
    if (!dict_extract_tag(bcl_in, "KEY", key, sizeof(key)))
        return dict_err(4, "missing_param: [@KEY]{key}");
    if (!dict_extract_tag(bcl_in, "VALUE", value, sizeof(value)))
        return dict_err(4, "missing_param: [@VALUE]{val}");
    if (strcmp(key, "DB_PATH") == 0) {
        BclDictionary_Close(d);
        strncpy(d->db_path, value, DICT_MAX_PATH - 1);
        d->db_path[DICT_MAX_PATH - 1] = '\0';
    }
    snprintf(DICT_RESULT_BUF, DICT_MAX_RESULT,
        "[@OK]{[@CONFIG]{[@KEY]{%s}[@VALUE]{%s}}}", key, value);
    return DICT_RESULT_BUF;
}
