//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_toolstack.h" date="2026-06-29" author="cascade" session_id="bcl-toolstack-units" context="Shared header for Cascade BCL tool units — one entry point dispatches to all tool units via BCL packets"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_toolstack.h" domain="cascade_tools" authority="ToolStack"}
//[@SUMMARY]{summary="Shared header for BCL tool units. Each tool is a .c file with Run() dispatch. One entry point (bcl_tool_main.c) routes BCL packets to the right unit. Units: pb_reader, chat_ingest, cleaner, msearch, mdmerge, discovery, schemalint, vbcheck, ghostctl, smartcli, wcmd, magnetic, codeingest, cognitive_core, error_fix_trainer, ai_fix_data_gen, coretotch_fix, db_exec, windir, destruction_guard"}
//[@CLASS]{class="ToolStack" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="RegisterUnit" type="command"}
//[@METHOD]{method="Dispatch" type="command"}
//[@METHOD]{method="ListUnits" type="query"}
//[@METHOD]{method="read_state" type="command"}
//[@METHOD]{method="set_config" type="command"}

#ifndef BCL_TOOLSTACK_H
#define BCL_TOOLSTACK_H

/* ════════════════════════════════════════════════════════════════════════════
 * BCL UNIT MAP — who exists, what category, who calls who
 *
 * This header is the JUNCTION. Every .c unit #includes this file.
 * bcl_tool_main.c registers all units → dispatches BCL packets → routes
 * to the right unit's Run() function.
 *
 * 22 UNITS across 7 CATEGORIES
 * ════════════════════════════════════════════════════════════════════════════
 *
 *  ┌─────────────────────────────────────────────────────────────────┐
 *  │                    bcl_tool_main.c                              │
 *  │            (entry point + RegisterAll + Dispatch)               │
 *  └───────────────────────┬─────────────────────────────────────────┘
 *                          │
 *                    includes THIS .h
 *                          │
 *          ┌───────────────┼───────────────────────────────┐
 *          │               │                               │
 *          ▼               ▼                               ▼
 *    ┌──────────┐   ┌────────────┐   ┌──────────────────────┐
 *    │ BCL      │   │ ToolStack  │   │ BclParser            │
 *    │ Result   │   │ Registry   │   │ (packet → tags)      │
 *    │ Helpers  │   │ + Dispatch │   │                      │
 *    └──────────┘   └─────┬──────┘   └──────────────────────┘
 *                         │
 *         ┌───────────────┼───────────────────────────────┐
 *         │               │                               │
 *         ▼               ▼                               ▼
 *
 *  ── SEARCH (6 units) ──────────────────────────────────────────────
 *
 *  bcl_msearch.c ────────────── core MySQL keyword search
 *       │  (shell dispatcher: search, count, where, stats)
 *       │
 *       ├── bcl_msearch_help.c ─── help text + AI rules (LAW62, LAW63)
 *       │       "Do not stop on first result. Examine all. Reason."
 *       │
 *       ├── bcl_msearch_registry.c ─ registry routing + schema loading
 *       │       (table_registry, BCL bracket detection, SHOW TABLES)
 *       │
 *       ├── bcl_msearch_ranking.c ─ context-aware ranking + update routing
 *       │       (score relevance, class understandings, route updates)
 *       │
 *       ├── bcl_msearch_qdrant.c ─ Qdrant vector + semantic search
 *       │       (semantic, multi-dim, full object, qstats)
 *       │
 *       └── bcl_msearch_magnetic.c ─ magnetic radius + context reconstruction
 *               (magnetic, chat_radius, graph_radius, radius expansion)
 *
 *  bcl_magnetic.c ────────────── standalone magnetic radius search
 *
 *  ── CHAT (2 units) ────────────────────────────────────────────────
 *
 *  bcl_pb_reader.c ──────────── encrypted .pb chat file reader
 *  bcl_chat_ingest.c ────────── AST-based code ingester
 *
 *  ── BUILD (3 units) ───────────────────────────────────────────────
 *
 *  bcl_mdmerge.c ────────────── markdown file merger
 *  bcl_wcmd.c ───────────────── window command processor
 *  bcl_windir.c ─────────────── window directory manager
 *
 *  ── GRAPH (2 units) ───────────────────────────────────────────────
 *
 *  bcl_discovery.c ──────────── code discovery and analysis
 *  bcl_codeingest.c ─────────── code ingestion engine
 *
 *  ── CONFIG (5 units) ──────────────────────────────────────────────
 *
 *  bcl_schemalint.c ─────────── database schema linter
 *  bcl_vbcheck.c ────────────── VBStyle compliance checker
 *  bcl_smartcli.c ───────────── smart CLI executor
 *  bcl_cognitive_core.c ─────── cognitive core engine
 *  bcl_error_fix.c ──────────── error fix trainer
 *
 *  ── CLEAN (2 units) ───────────────────────────────────────────────
 *
 *  bcl_cleaner.c ────────────── cache and junk cleaner
 *  bcl_ghostctl.c ───────────── system-wide cleanup control
 *
 *  ── SECURITY (1 unit) ─────────────────────────────────────────────
 *
 *  bcl_destruction_guard.c ── destruction guard with embedded SQLite learning
 *
 * ════════════════════════════════════════════════════════════════════════════
 * DEPENDENCY GRAPH — who calls who at runtime
 * ════════════════════════════════════════════════════════════════════════════
 *
 *  bcl_tool_main.c
 *    ├──→ msearch           (core search shell)
 *    │     ├──→ msearch_help      (AI queries help/rules)
 *    │     ├──→ msearch_registry  (schema + routing lookups)
 *    │     ├──→ msearch_ranking   (relevance scoring)
 *    │     ├──→ msearch_qdrant    (vector search delegation)
 *    │     └──→ msearch_magnetic  (radius expansion)
 *    │
 *    ├──→ pb_reader         (reads .pb → feeds chat_ingest)
 *    │     └──→ chat_ingest      (ingests parsed chat)
 *    │
 *    ├──→ discovery         (code analysis)
 *    │     └──→ codeingest       (ingests discovered code)
 *    │
 *    ├──→ vbcheck           (VBStyle compliance)
 *    │     └──→ schemalint       (schema validation)
 *    │
 *    ├──→ smartcli          (CLI execution)
 *    │     └──→ error_fix        (learns from CLI failures)
 *    │
 *    ├──→ magnetic          (standalone radius search)
 *    │     └──→ msearch_magnetic (shared magnetic logic)
 *    │
 *    ├──→ cognitive_core    (reasoning engine)
 *    │     ├──→ msearch_help     (reads AI rules)
 *    │     └──→ error_fix        (applies learned fixes)
 *    │
 *    ├──→ cleaner           (cache cleanup)
 *    │     └──→ ghostctl         (system cleanup)
 *    │
 *    ├──→ mdmerge           (standalone)
 *    ├──→ wcmd              (standalone)
 *    └──→ windir            (standalone)
 *
 * ════════════════════════════════════════════════════════════════════════════
 * COMPILE MAP — all .c files link into one binary
 * ════════════════════════════════════════════════════════════════════════════
 *
 *  Makefile UNIT_SRCS:
 *
 *    bcl_tool_main.c         ← entry point (RegisterAll, Dispatch, main)
 *    bcl_pb_reader.c         ← chat category
 *    bcl_chat_ingest.c       ← chat category
 *    bcl_cleaner.c           ← clean category
 *    bcl_msearch.c           ← search category (core shell)
 *    bcl_msearch_help.c      ← search category (msearch sub-unit)
 *    bcl_msearch_registry.c  ← search category (msearch sub-unit)
 *    bcl_msearch_ranking.c   ← search category (msearch sub-unit)
 *    bcl_msearch_qdrant.c    ← search category (msearch sub-unit)
 *    bcl_msearch_magnetic.c  ← search category (msearch sub-unit)
 *    bcl_mdmerge.c           ← build category
 *    bcl_discovery.c         ← graph category
 *    bcl_schemalint.c        ← config category
 *    bcl_vbcheck.c           ← config category
 *    bcl_ghostctl.c          ← clean category
 *    bcl_smartcli.c          ← config category
 *    bcl_wcmd.c              ← build category
 *    bcl_magnetic.c          ← search category
 *    bcl_codeingest.c        ← graph category
 *    bcl_cognitive_core.c    ← config category
 *    bcl_error_fix.c         ← config category
 *    bcl_windir.c            ← build category
 *
 *  Total: 21 .c files → 1 binary (bcl_tool)
 *  All link against: -lsqlite3 -lcrypto -lmysqlclient -lz -lzstd -lresolv
 * ════════════════════════════════════════════════════════════════════════════
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <sqlite3.h>

/* ════════════════════════════════════════════
 * CONSTANTS
 * ════════════════════════════════════════════ */

#define TOOL_MAX_UNITS      48
#define TOOL_MAX_NAME       64
#define TOOL_MAX_CMD        128
#define TOOL_MAX_BCL        65536
#define TOOL_MAX_RESULT     65536
#define TOOL_MAX_PATH       4096
#define TOOL_MAX_KEY        128
#define TOOL_MAX_VAL        4096
#define TOOL_MAX_UNITS_LIST 1024

/* ════════════════════════════════════════════
 * BCL PACKET STRUCTURES (shared with engine)
 * ════════════════════════════════════════════ */

#define BCL_MAX_TAG      64
#define BCL_MAX_CONTENT  4096
#define BCL_MAX_NODES    256
#define BCL_MAX_DEPTH    32

typedef struct {
    char tag[BCL_MAX_TAG];
    char content[BCL_MAX_CONTENT];
    int  start_pos;
    int  end_pos;
    int  depth;
    int  parent_idx;
    int  child_count;
    int  children[32];
} BclNode;

typedef struct {
    BclNode nodes[BCL_MAX_NODES];
    int     node_count;
    int     parse_ok;
    char    error_msg[256];
    int     error_pos;
} BclParseResult;

/* ════════════════════════════════════════════
 * UNIT INTERFACE — every tool implements this
 * ════════════════════════════════════════════ */

/* Each unit is a struct with a Run function pointer.
   Run takes a command string and BCL input, returns BCL output.
   Returns: 1 = ok, 0 = error (error in bcl_out as [@ERR] packet) */

typedef int (*UnitRunFunc)(const char *command, const char *bcl_in,
                           char *bcl_out, size_t out_sz);

typedef int (*UnitInitFunc)(void);
typedef int (*UnitCloseFunc)(void);
typedef const char * (*UnitStateFunc)(void);

typedef struct {
    char         name[TOOL_MAX_NAME];
    char         category[32];       /* "search", "chat", "build", "clean", "graph", "config" */
    char         help_text[256];
    UnitInitFunc init;
    UnitRunFunc  run;
    UnitCloseFunc close;
    UnitStateFunc state;
    int          initialized;
} ToolUnit;

/* ════════════════════════════════════════════
 * TOOLSTACK — registry and dispatcher
 * ════════════════════════════════════════════ */

typedef struct {
    ToolUnit units[TOOL_MAX_UNITS];
    int      unit_count;
    char     db_path[TOOL_MAX_PATH];
    void     *conn;                  /* sqlite3* — shared connection (optional) */
    int      initialized;
} ToolStack;

void   ToolStack_Init(ToolStack *ts, const char *db_path);
void   ToolStack_Close(ToolStack *ts);
int    ToolStack_RegisterUnit(ToolStack *ts, const char *name,
                               const char *category, const char *help,
                               UnitInitFunc init, UnitRunFunc run,
                               UnitCloseFunc close, UnitStateFunc state);
int    ToolStack_Dispatch(ToolStack *ts, const char *unit_name,
                           const char *command, const char *bcl_in,
                           char *bcl_out, size_t out_sz);
int    ToolStack_ListUnits(ToolStack *ts, char *out, size_t out_sz);
const char * ToolStack_Run(ToolStack *ts, const char *command, const char *bcl_in);

/* ════════════════════════════════════════════
 * UNIT DECLARATIONS — one per .c tool file
 * ════════════════════════════════════════════ */

/* bcl_pb_reader.c — encrypted chat file reader */
int    PbReader_Init(void);
int    PbReader_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    PbReader_Close(void);
const char * PbReader_State(void);

/* bcl_chat_ingest.c — AST-based code ingester */
int    ChatIngest_Init(void);
int    ChatIngest_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    ChatIngest_Close(void);
const char * ChatIngest_State(void);

/* bcl_cleaner.c — cache cleaner */
int    Cleaner_Init(void);
int    Cleaner_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    Cleaner_Close(void);
const char * Cleaner_State(void);

/* bcl_mdmerge.c — markdown merger */
int    Mdmerge_Init(void);
int    Mdmerge_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    Mdmerge_Close(void);
const char * Mdmerge_State(void);

/* bcl_discovery.c — code discovery */
int    Discovery_Init(void);
int    Discovery_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    Discovery_Close(void);
const char * Discovery_State(void);

/* bcl_schemalint.c — schema linter */
int    Schemalint_Init(void);
int    Schemalint_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    Schemalint_Close(void);
const char * Schemalint_State(void);

/* bcl_vbcheck.c — VBStyle checker */
int    Vbcheck_Init(void);
int    Vbcheck_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    Vbcheck_Close(void);
const char * Vbcheck_State(void);

/* bcl_ghostctl.c — system cleanup */
int    Ghostctl_Init(void);
int    Ghostctl_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    Ghostctl_Close(void);
const char * Ghostctl_State(void);

/* bcl_smartcli.c — smart CLI */
int    Smartcli_Init(void);
int    Smartcli_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    Smartcli_Close(void);
const char * Smartcli_State(void);

/* bcl_wcmd.c — window command */
int    Wcmd_Init(void);
int    Wcmd_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    Wcmd_Close(void);
const char * Wcmd_State(void);

/* bcl_codeingest.c — code ingestion */
int    Codeingest_Init(void);
int    Codeingest_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    Codeingest_Close(void);
const char * Codeingest_State(void);

/* bcl_cognitive_core.c — cognitive core */
int    CognitiveCore_Init(void);
int    CognitiveCore_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    CognitiveCore_Close(void);
const char * CognitiveCore_State(void);

/* bcl_error_fix.c — error fix trainer */
int    ErrorFix_Init(void);
int    ErrorFix_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    ErrorFix_Close(void);
const char * ErrorFix_State(void);

/* bcl_windir.c — window directory */
int    Windir_Init(void);
int    Windir_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    Windir_Close(void);
const char * Windir_State(void);

/* bcl_msearch_help.c — msearch help and AI guidance */
int    MsearchHelp_Init(void);
int    MsearchHelp_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    MsearchHelp_Close(void);
const char * MsearchHelp_State(void);

/* bcl_msearch_registry.c — msearch registry routing and schema loading */
int    MsearchRegistry_Init(void);
int    MsearchRegistry_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    MsearchRegistry_Close(void);
const char * MsearchRegistry_State(void);

/* bcl_msearch_ranking.c — msearch context-aware ranking */
int    MsearchRanking_Init(void);
int    MsearchRanking_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    MsearchRanking_Close(void);
const char * MsearchRanking_State(void);

/* bcl_msearch_qdrant.c — msearch Qdrant vector search */
int    MsearchQdrant_Init(void);
int    MsearchQdrant_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    MsearchQdrant_Close(void);
const char * MsearchQdrant_State(void);

/* bcl_msearch_magnetic.c — msearch magnetic radius search */
int    MsearchMagnetic_Init(void);
int    MsearchMagnetic_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    MsearchMagnetic_Close(void);
const char * MsearchMagnetic_State(void);

/* bcl_destruction_guard.c — destruction guard with embedded SQLite learning */
int    DestructionGuard_Init(void);
int    DestructionGuard_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    DestructionGuard_Close(void);
const char * DestructionGuard_State(void);

/* ════════════════════════════════════════════════════════════════════════════
 * GRAPH ENGINE UNITS — 10 units for the Max Graph Engine
 * Each is a BCL unit with Init/Run/Close/State dispatch.
 * Shared types in bcl_graph_types.h, core lifecycle in bcl_graph_core.c.
 * ════════════════════════════════════════════════════════════════════════════ */

/* bcl_graph_config.c — graph config parser */
int    GraphConfig_Init(void);
int    GraphConfig_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    GraphConfig_Close(void);
const char * GraphConfig_State(void);

/* bcl_graph_view.c — programmable view lens over graph */
int    GraphView_Init(void);
int    GraphView_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    GraphView_Close(void);
const char * GraphView_State(void);

/* bcl_graph_policy.c — expansion policy + executor */
int    GraphPolicy_Init(void);
int    GraphPolicy_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    GraphPolicy_Close(void);
const char * GraphPolicy_State(void);

/* bcl_graph_expand.c — recursive expansion engine */
int    GraphExpand_Init(void);
int    GraphExpand_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    GraphExpand_Close(void);
const char * GraphExpand_State(void);

/* bcl_graph_store.c — MySQL/SQLite graph store */
int    GraphStore_Init(void);
int    GraphStore_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    GraphStore_Close(void);
const char * GraphStore_State(void);

/* bcl_graph_compiler.c — view to execution plan compiler */
int    GraphCompiler_Init(void);
int    GraphCompiler_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    GraphCompiler_Close(void);
const char * GraphCompiler_State(void);

/* bcl_graph_optimizer.c — plan optimizer with 3-part scoring */
int    GraphOptimizer_Init(void);
int    GraphOptimizer_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    GraphOptimizer_Close(void);
const char * GraphOptimizer_State(void);

/* bcl_graph_trace.c — immutable decision log */
int    GraphTrace_Init(void);
int    GraphTrace_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    GraphTrace_Close(void);
const char * GraphTrace_State(void);

/* bcl_graph_cache.c — 4-layer scoped cache */
int    GraphCache_Init(void);
int    GraphCache_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    GraphCache_Close(void);
const char * GraphCache_State(void);

/* bcl_graph_learning.c — 3-stage learning pipeline */
int    GraphLearning_Init(void);
int    GraphLearning_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    GraphLearning_Close(void);
const char * GraphLearning_State(void);

/* ════════════════════════════════════════════════════════════════════════════
 * SEARCH UNITS (source-based) — 3 new units, full VBSTYLE module-authority
 * contract. Each owns its full pipeline (retrieve -> parse -> normalize ->
 * BCL). Split by SOURCE, not by method.
 *   bcl_search_web.c  — source: online URLs (HTTP fetch + HTML parse)
 *   bcl_search_fs.c   — source: local filesystem (dir walk + grep)
 *   bcl_search_db.c   — source: MySQL databases (absorbs bcl_msearch.c core)
 * ════════════════════════════════════════════════════════════════════════════ */

/* bcl_search_web.c — web/URL search (HTTP fetch + HTML parse + text extract) */
int    SearchWeb_Init(void);
int    SearchWeb_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    SearchWeb_Close(void);
const char * SearchWeb_State(void);

/* bcl_search_fs.c — filesystem search (dir walk + ext/time/content filters) */
int    SearchFs_Init(void);
int    SearchFs_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    SearchFs_Close(void);
const char * SearchFs_State(void);

/* bcl_search_db.c — MySQL database search (absorbs bcl_msearch.c core) */
int    SearchDb_Init(void);
int    SearchDb_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    SearchDb_Close(void);
const char * SearchDb_State(void);

/* bcl_ast_walker.c — tree-sitter AST parse, extract classes/methods/imports */
int    AstWalker_Init(void);
int    AstWalker_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    AstWalker_Close(void);
const char * AstWalker_State(void);

/* bcl_vbstyle_check.c — 11 VBStyle compliance checks using AST data */
int    VbstyleChecker_Init(void);
int    VbstyleChecker_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    VbstyleChecker_Close(void);
const char * VbstyleChecker_State(void);

/* bcl_graph_builder.c — call/state/import graph edges from AST */
int    GraphBuilder_Init(void);
int    GraphBuilder_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    GraphBuilder_Close(void);
const char * GraphBuilder_State(void);

/* bcl_bcl_stamper.c — generate BCL header stamps from AST */
int    BclStamper_Init(void);
int    BclStamper_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    BclStamper_Close(void);
const char * BclStamper_State(void);

/* bcl_mysql_store.c — write AST results to MySQL bcl_ir tables */
int    MysqlStore_Init(void);
int    MysqlStore_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    MysqlStore_Close(void);
const char * MysqlStore_State(void);

/* ════════════════════════════════════════════════════════════════════════════
 * VBSTYLE RULE UNITS — 8 new units for the VBStyle rule domain
 * Each is a BCL unit with Init/Run/Close/State dispatch.
 * Source: core/Dom_Vsstyle/ Python domain → ported to C BCL units.
 * ════════════════════════════════════════════════════════════════════════════ */

/* bcl_rule_reader.c — read rules from MySQL vb_shared.rules or JSON file */
int    RuleReader_Init(void);
int    RuleReader_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    RuleReader_Close(void);
const char * RuleReader_State(void);

/* bcl_rule_writer.c — write rules to MySQL vb_shared.rules or JSON file */
int    RuleWriter_Init(void);
int    RuleWriter_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    RuleWriter_Close(void);
const char * RuleWriter_State(void);

/* bcl_rule_engine.c — run VBStyle rules against code files */
int    RuleEngine_Init(void);
int    RuleEngine_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    RuleEngine_Close(void);
const char * RuleEngine_State(void);

/* bcl_rule_enforcer.c — enforce rules, block violations exceeding threshold */
int    RuleEnforcer_Init(void);
int    RuleEnforcer_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    RuleEnforcer_Close(void);
const char * RuleEnforcer_State(void);

/* bcl_rule_gap_graph.c — find rule coverage gaps */
int    RuleGapGraph_Init(void);
int    RuleGapGraph_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    RuleGapGraph_Close(void);
const char * RuleGapGraph_State(void);

/* bcl_rule_cluster_graph.c — cluster rules by keyword similarity */
int    RuleClusterGraph_Init(void);
int    RuleClusterGraph_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    RuleClusterGraph_Close(void);
const char * RuleClusterGraph_State(void);

/* bcl_rule_coverage_graph.c — map rules to code entities */
int    RuleCoverageGraph_Init(void);
int    RuleCoverageGraph_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    RuleCoverageGraph_Close(void);
const char * RuleCoverageGraph_State(void);

/* bcl_code_index.c — index code files into MySQL vb_code_test tables */
int    CodeIndex_Init(void);
int    CodeIndex_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    CodeIndex_Close(void);
const char * CodeIndex_State(void);

/* bcl_Reports.c — unified report generator with event-bus architecture
   (LiveState + EventInspector + EventViewer + Configurator) */
int    Reports_Init(void);
int    Reports_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz);
int    Reports_Close(void);
const char * Reports_State(void);

/* ════════════════════════════════════════════
 * BCL PARSER (minimal — for packet routing)
 * ════════════════════════════════════════════ */

void   BclParser_Init(BclParseResult *p);
int    BclParser_Parse(BclParseResult *p, const char *bcl_text);
int    BclParser_Extract(BclParseResult *p, const char *tag, char *out, size_t out_sz);
void   BclParser_Free(BclParseResult *p);

/* ════════════════════════════════════════════
 * BCL RESULT HELPERS
 * ════════════════════════════════════════════ */

int    BclResult_Ok(char *out, size_t out_sz, const char *body);
int    BclResult_Err(char *out, size_t out_sz, int code, const char *desc);
int    BclResult_Data(char *out, size_t out_sz, const char *key, const char *val);

#endif /* BCL_TOOLSTACK_H */
