//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_tool_main.c" date="2026-06-29" author="cascade" session_id="bcl-toolstack-units" context="Single entry point for all BCL tool units. Registers all units, parses BCL packets, dispatches to the right unit, returns BCL result packets."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_tool_main.c" domain="cascade_tools" authority="ToolStack"}
//[@SUMMARY]{summary="Entry point for BCL tool stack. CLI: bcl_tool list | bcl_tool <unit> <command> [bcl_input] | bcl_tool dispatch <bcl_packet>. Registers 17 units, dispatches BCL packets, returns BCL results."}
//[@CLASS]{class="ToolStack" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="RegisterAll" type="command"}
//[@METHOD]{method="Dispatch" type="command"}
//[@METHOD]{method="ListUnits" type="query"}
//[@METHOD]{method="read_state" type="command"}
//[@METHOD]{method="set_config" type="command"}

#include "bcl_toolstack.h"

/* ===== DIM BLOCK ===== */

static ToolStack TS;
static char RESULT_BUF[TOOL_MAX_RESULT];
static char INPUT_BUF[TOOL_MAX_BCL];

/* ===== RESULT HELPERS ===== */

int BclResult_Ok(char *out, size_t out_sz, const char *body) {
    snprintf(out, out_sz, "[@OK]{%s}", body ? body : "");
    return 1;
}

int BclResult_Err(char *out, size_t out_sz, int code, const char *desc) {
    snprintf(out, out_sz, "[@ERR]{[@CODE]{%d}[@DESC]{%s}}", code, desc ? desc : "");
    return 0;
}

int BclResult_Data(char *out, size_t out_sz, const char *key, const char *val) {
    snprintf(out, out_sz, "[@OK]{[@%s]{%s}}", key ? key : "DATA", val ? val : "");
    return 1;
}

/* ===== BCL PARSER (minimal — extracts [@TAG]{content}) ===== */

void BclParser_Init(BclParseResult *p) {
    memset(p, 0, sizeof(*p));
}

int BclParser_Parse(BclParseResult *p, const char *bcl_text) {
    if (!bcl_text || !bcl_text[0]) {
        p->parse_ok = 0;
        snprintf(p->error_msg, sizeof(p->error_msg), "empty input");
        return 0;
    }
    int pos = 0;
    int depth = 0;
    int parent_stack[BCL_MAX_DEPTH];
    int parent_top = -1;
    
    while (bcl_text[pos] && p->node_count < BCL_MAX_NODES) {
        /* Find [@ */
        if (bcl_text[pos] == '[' && bcl_text[pos + 1] == '@') {
            pos += 2;
            int tag_start = pos;
            while (bcl_text[pos] && bcl_text[pos] != ']' && bcl_text[pos] != '{') pos++;
            int tag_len = pos - tag_start;
            if (bcl_text[pos] == ']') {
                pos++;
                /* Tag closed with ] — expect { next for content */
                while (bcl_text[pos] == ' ' || bcl_text[pos] == '\t') pos++;
                if (bcl_text[pos] != '{') continue;
            }
            if (bcl_text[pos] != '{') continue;

            if (tag_len <= 0 || tag_len >= BCL_MAX_TAG) continue;
            
            int idx = p->node_count++;
            BclNode *n = &p->nodes[idx];
            memset(n, 0, sizeof(*n));
            strncpy(n->tag, bcl_text + tag_start, tag_len);
            n->tag[tag_len] = '\0';
            n->start_pos = tag_start - 2;
            n->depth = depth;
            n->parent_idx = (parent_top >= 0) ? parent_stack[parent_top] : -1;
            
            if (n->parent_idx >= 0) {
                BclNode *parent = &p->nodes[n->parent_idx];
                if (parent->child_count < 32) {
                    parent->children[parent->child_count++] = idx;
                }
            }
            
            parent_stack[++parent_top] = idx;
            depth++;
            pos++;
            
            /* Read content until matching } */
            int content_start = pos;
            int brace_depth = 1;
            while (bcl_text[pos] && brace_depth > 0) {
                if (bcl_text[pos] == '{') brace_depth++;
                else if (bcl_text[pos] == '}') brace_depth--;
                if (brace_depth > 0) pos++;
            }
            
            int content_len = pos - content_start;
            if (content_len >= BCL_MAX_CONTENT) content_len = BCL_MAX_CONTENT - 1;
            strncpy(n->content, bcl_text + content_start, content_len);
            n->content[content_len] = '\0';
            n->end_pos = pos;
            
            depth--;
            parent_top--;
            pos++;
        } else {
            pos++;
        }
    }
    
    p->parse_ok = (p->node_count > 0) ? 1 : 0;
    return p->parse_ok;
}

int BclParser_Extract(BclParseResult *p, const char *tag, char *out, size_t out_sz) {
    for (int i = 0; i < p->node_count; i++) {
        if (strcmp(p->nodes[i].tag, tag) == 0) {
            strncpy(out, p->nodes[i].content, out_sz - 1);
            out[out_sz - 1] = '\0';
            return 1;
        }
    }
    return 0;
}

void BclParser_Free(BclParseResult *p) {
    memset(p, 0, sizeof(*p));
}

/* ===== TOOLSTACK API ===== */

void ToolStack_Init(ToolStack *ts, const char *db_path) {
    memset(ts, 0, sizeof(*ts));
    strncpy(ts->db_path, db_path ? db_path : "cascade_tools.db", TOOL_MAX_PATH - 1);
    ts->initialized = 1;
}

void ToolStack_Close(ToolStack *ts) {
    for (int i = 0; i < ts->unit_count; i++) {
        if (ts->units[i].initialized && ts->units[i].close) {
            ts->units[i].close();
            ts->units[i].initialized = 0;
        }
    }
    if (ts->conn) {
        sqlite3_close((sqlite3*)ts->conn);
        ts->conn = NULL;
    }
    ts->initialized = 0;
}

int ToolStack_RegisterUnit(ToolStack *ts, const char *name,
                            const char *category, const char *help,
                            UnitInitFunc init, UnitRunFunc run,
                            UnitCloseFunc close, UnitStateFunc state) {
    if (ts->unit_count >= TOOL_MAX_UNITS) return 0;
    ToolUnit *u = &ts->units[ts->unit_count++];
    strncpy(u->name, name, TOOL_MAX_NAME - 1);
    strncpy(u->category, category, 31);
    strncpy(u->help_text, help, 255);
    u->init = init;
    u->run = run;
    u->close = close;
    u->state = state;
    u->initialized = 0;
    return 1;
}

int ToolStack_Dispatch(ToolStack *ts, const char *unit_name,
                        const char *command, const char *bcl_in,
                        char *bcl_out, size_t out_sz) {
    for (int i = 0; i < ts->unit_count; i++) {
        if (strcmp(ts->units[i].name, unit_name) == 0) {
            if (!ts->units[i].initialized && ts->units[i].init) {
                if (!ts->units[i].init()) {
                    return BclResult_Err(bcl_out, out_sz, 5, "unit init failed");
                }
                ts->units[i].initialized = 1;
            }
            if (!ts->units[i].run) {
                return BclResult_Err(bcl_out, out_sz, 6, "unit has no run function");
            }
            return ts->units[i].run(command, bcl_in, bcl_out, out_sz);
        }
    }
    return BclResult_Err(bcl_out, out_sz, 404, "unit not found");
}

int ToolStack_ListUnits(ToolStack *ts, char *out, size_t out_sz) {
    int offset = 0;
    offset += snprintf(out + offset, out_sz - offset, "[@OK]{[@COUNT]{%d}", ts->unit_count);
    for (int i = 0; i < ts->unit_count; i++) {
        offset += snprintf(out + offset, out_sz - offset,
            "[@UNIT]{[@NAME]{%s}[@CATEGORY]{%s}[@HELP]{%s}[@STATUS]{%s}}",
            ts->units[i].name,
            ts->units[i].category,
            ts->units[i].help_text,
            ts->units[i].initialized ? "active" : "pending");
    }
    offset += snprintf(out + offset, out_sz - offset, "}");
    return 1;
}

const char * ToolStack_Run(ToolStack *ts, const char *command, const char *bcl_in) {
    if (strcmp(command, "list") == 0) {
        ToolStack_ListUnits(ts, RESULT_BUF, TOOL_MAX_RESULT);
        return RESULT_BUF;
    }
    
    if (strcmp(command, "dispatch") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        if (!BclParser_Parse(&parse, bcl_in)) {
            BclResult_Err(RESULT_BUF, TOOL_MAX_RESULT, 1, "invalid BCL packet");
            return RESULT_BUF;
        }
        
        char unit_name[TOOL_MAX_NAME] = {0};
        char cmd_str[TOOL_MAX_CMD] = {0};
        BclParser_Extract(&parse, "UNIT", unit_name, sizeof(unit_name));
        BclParser_Extract(&parse, "CMD", cmd_str, sizeof(cmd_str));
        
        if (!unit_name[0]) {
            BclResult_Err(RESULT_BUF, TOOL_MAX_RESULT, 2, "no UNIT in packet");
            return RESULT_BUF;
        }
        if (!cmd_str[0]) {
            BclResult_Err(RESULT_BUF, TOOL_MAX_RESULT, 3, "no CMD in packet");
            return RESULT_BUF;
        }
        
        ToolStack_Dispatch(ts, unit_name, cmd_str, bcl_in, RESULT_BUF, TOOL_MAX_RESULT);
        BclParser_Free(&parse);
        return RESULT_BUF;
    }
    
    /* pipeline — chain multiple units: scan -> index -> check -> enforce -> report
       BCL input: [@PATH]{/path/to/dir}[@STEPS]{scan,index,check,enforce,report}
       Runs each step in sequence, passing PATH through. Returns aggregated result. */
    if (strcmp(command, "pipeline") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        if (!BclParser_Parse(&parse, bcl_in)) {
            BclResult_Err(RESULT_BUF, TOOL_MAX_RESULT, 1, "invalid BCL packet");
            return RESULT_BUF;
        }
        char path[TOOL_MAX_PATH] = {0};
        char steps_str[512] = {0};
        BclParser_Extract(&parse, "PATH", path, sizeof(path));
        BclParser_Extract(&parse, "STEPS", steps_str, sizeof(steps_str));
        BclParser_Free(&parse);
        
        if (!path[0]) {
            BclResult_Err(RESULT_BUF, TOOL_MAX_RESULT, 4, "no PATH in packet");
            return RESULT_BUF;
        }
        if (!steps_str[0]) {
            strcpy(steps_str, "scan,index,check,enforce,report");
        }
        
        char step_buf[512];
        strncpy(step_buf, steps_str, sizeof(step_buf) - 1);
        step_buf[sizeof(step_buf) - 1] = '\0';
        
        int offset = 0;
        offset += snprintf(RESULT_BUF + offset, TOOL_MAX_RESULT - offset,
            "[@OK]{[@PIPELINE]{[@PATH]{%s}[@STEPS]{%s}", path, steps_str);
        
        char *step = strtok(step_buf, ",");
        int step_count = 0;
        int step_ok = 0;
        int step_fail = 0;
        char step_input[TOOL_MAX_BCL];
        char step_output[TOOL_MAX_RESULT];
        
        while (step && offset < TOOL_MAX_RESULT - 1024) {
            while (*step == ' ') step++;
            step_count++;
            
            /* Build BCL input for this step */
            snprintf(step_input, sizeof(step_input), "[@PATH]{%s}", path);
            step_output[0] = '\0';
            
            int ok = 0;
            const char *result_str = "skipped";
            
            if (strcmp(step, "scan") == 0) {
                /* Use code_index to scan headers (no MySQL needed) */
                ok = ToolStack_Dispatch(ts, "code_index", "scan_headers", step_input, step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "index") == 0) {
                /* Use code_index to index into MySQL */
                ok = ToolStack_Dispatch(ts, "code_index", "index_dir", step_input, step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "check") == 0) {
                /* Use rule_engine to check the path */
                ok = ToolStack_Dispatch(ts, "rule_engine", "check_dir", step_input, step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "enforce") == 0) {
                /* Use rule_enforcer to enforce */
                ok = ToolStack_Dispatch(ts, "rule_enforcer", "block", step_input, step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "report") == 0) {
                /* Use rule_engine to generate report */
                ok = ToolStack_Dispatch(ts, "rule_engine", "report", step_input, step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "audit") == 0) {
                /* Use rule_enforcer to generate enforcement report */
                ok = ToolStack_Dispatch(ts, "rule_enforcer", "report", step_input, step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "read_rules") == 0) {
                /* Use rule_reader to load rules from MySQL */
                ok = ToolStack_Dispatch(ts, "rule_reader", "read", "", step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "gaps") == 0) {
                /* Use rule_gap_graph to find gaps */
                ok = ToolStack_Dispatch(ts, "rule_gap_graph", "build", "", step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "clusters") == 0) {
                /* Use rule_cluster_graph to build clusters */
                ok = ToolStack_Dispatch(ts, "rule_cluster_graph", "build", "", step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "coverage") == 0) {
                /* Use rule_coverage_graph to build coverage */
                ok = ToolStack_Dispatch(ts, "rule_coverage_graph", "build", "", step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "vbcheck") == 0) {
                /* Use vbcheck to check VBStyle compliance */
                ok = ToolStack_Dispatch(ts, "vbcheck", "check_dir", step_input, step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "reports_full") == 0) {
                /* Use reports unit for full terminal report */
                ok = ToolStack_Dispatch(ts, "reports", "full", step_input, step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "reports_overview") == 0) {
                /* Use reports unit for overview */
                ok = ToolStack_Dispatch(ts, "reports", "overview", step_input, step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "reports_compliance") == 0) {
                /* Use reports unit for compliance report */
                ok = ToolStack_Dispatch(ts, "reports", "compliance", step_input, step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "reports_enforcement") == 0) {
                /* Use reports unit for enforcement report */
                ok = ToolStack_Dispatch(ts, "reports", "enforcement", step_input, step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "reports_debug") == 0) {
                /* Use reports unit for debug view */
                ok = ToolStack_Dispatch(ts, "reports", "debug", step_input, step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "reports_replay") == 0) {
                /* Use reports unit for replay */
                ok = ToolStack_Dispatch(ts, "reports", "replay", step_input, step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "reports_table") == 0) {
                /* Use reports unit for table view */
                ok = ToolStack_Dispatch(ts, "reports", "table", step_input, step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "reports_test") == 0) {
                /* Use reports unit for ClassTester results */
                ok = ToolStack_Dispatch(ts, "reports", "test", step_input, step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "reports_code_structure") == 0) {
                /* Use reports unit for code structure view */
                ok = ToolStack_Dispatch(ts, "reports", "code_structure", step_input, step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "reports_execution_graph") == 0) {
                /* Use reports unit for execution graph */
                ok = ToolStack_Dispatch(ts, "reports", "execution_graph", step_input, step_output, sizeof(step_output));
                result_str = step_output;
            } else if (strcmp(step, "reports_profile") == 0) {
                /* Use reports unit for profile/timing analysis */
                ok = ToolStack_Dispatch(ts, "reports", "profile", step_input, step_output, sizeof(step_output));
                result_str = step_output;
            } else {
                result_str = "unknown_step";
                ok = 0;
            }
            
            if (ok) step_ok++; else step_fail++;
            
            /* Truncate step output to fit */
            int remaining = TOOL_MAX_RESULT - offset - 512;
            if (remaining > 0 && result_str[0]) {
                int rlen = (int)strlen(result_str);
                if (rlen > remaining) rlen = remaining;
                offset += snprintf(RESULT_BUF + offset, TOOL_MAX_RESULT - offset,
                    "[@STEP]{[@NAME]{%s}[@STATUS]{%s}[@RESULT]{", step, ok ? "ok" : "fail");
                /* Copy truncated result */
                int copy_len = rlen;
                if (copy_len > 2000) copy_len = 2000;
                memcpy(RESULT_BUF + offset, result_str, copy_len);
                offset += copy_len;
                offset += snprintf(RESULT_BUF + offset, TOOL_MAX_RESULT - offset, "}}");
            } else {
                offset += snprintf(RESULT_BUF + offset, TOOL_MAX_RESULT - offset,
                    "[@STEP]{[@NAME]{%s}[@STATUS]{%s}}", step, ok ? "ok" : "fail");
            }
            
            step = strtok(NULL, ",");
        }
        
        offset += snprintf(RESULT_BUF + offset, TOOL_MAX_RESULT - offset,
            "[@STEP_COUNT]{%d}[@STEP_OK]{%d}[@STEP_FAIL]{%d}[@STATUS]{pipeline_complete}}",
            step_count, step_ok, step_fail);
        return RESULT_BUF;
    }
    
    BclResult_Err(RESULT_BUF, TOOL_MAX_RESULT, 404, "unknown command");
    return RESULT_BUF;
}

/* ===== REGISTER ALL UNITS ===== */

static void RegisterAll(ToolStack *ts) {
    ToolStack_RegisterUnit(ts, "pb_reader",   "chat",   "Encrypted .pb chat file reader",     PbReader_Init, PbReader_Run, PbReader_Close, PbReader_State);
    ToolStack_RegisterUnit(ts, "chat_ingest", "chat",   "AST-based code ingester",            ChatIngest_Init, ChatIngest_Run, ChatIngest_Close, ChatIngest_State);
    ToolStack_RegisterUnit(ts, "cleaner",     "clean",  "Cache and junk cleaner",             Cleaner_Init, Cleaner_Run, Cleaner_Close, Cleaner_State);
    ToolStack_RegisterUnit(ts, "mdmerge",     "build",  "Markdown file merger",               Mdmerge_Init, Mdmerge_Run, Mdmerge_Close, Mdmerge_State);
    ToolStack_RegisterUnit(ts, "discovery",   "graph",  "Code discovery and analysis",        Discovery_Init, Discovery_Run, Discovery_Close, Discovery_State);
    ToolStack_RegisterUnit(ts, "schemalint",  "config", "Database schema linter",             Schemalint_Init, Schemalint_Run, Schemalint_Close, Schemalint_State);
    ToolStack_RegisterUnit(ts, "vbcheck",     "config", "VBStyle compliance checker",         Vbcheck_Init, Vbcheck_Run, Vbcheck_Close, Vbcheck_State);
    ToolStack_RegisterUnit(ts, "ghostctl",    "clean",  "System-wide cleanup control",        Ghostctl_Init, Ghostctl_Run, Ghostctl_Close, Ghostctl_State);
    ToolStack_RegisterUnit(ts, "smartcli",    "config", "Smart CLI executor",                 Smartcli_Init, Smartcli_Run, Smartcli_Close, Smartcli_State);
    ToolStack_RegisterUnit(ts, "wcmd",        "build",  "Window command processor",           Wcmd_Init, Wcmd_Run, Wcmd_Close, Wcmd_State);
    ToolStack_RegisterUnit(ts, "codeingest",  "graph",  "Code ingestion engine",              Codeingest_Init, Codeingest_Run, Codeingest_Close, Codeingest_State);
    ToolStack_RegisterUnit(ts, "cognitive",   "config", "Cognitive core engine",              CognitiveCore_Init, CognitiveCore_Run, CognitiveCore_Close, CognitiveCore_State);
    ToolStack_RegisterUnit(ts, "error_fix",   "config", "Error fix trainer",                  ErrorFix_Init, ErrorFix_Run, ErrorFix_Close, ErrorFix_State);
    ToolStack_RegisterUnit(ts, "windir",      "build",  "Window directory manager",           Windir_Init, Windir_Run, Windir_Close, Windir_State);
    ToolStack_RegisterUnit(ts, "search_help",      "search", "Search help and AI guidance",          MsearchHelp_Init, MsearchHelp_Run, MsearchHelp_Close, MsearchHelp_State);
    ToolStack_RegisterUnit(ts, "search_registry",  "search", "Search registry routing",              MsearchRegistry_Init, MsearchRegistry_Run, MsearchRegistry_Close, MsearchRegistry_State);
    ToolStack_RegisterUnit(ts, "search_ranking",   "search", "Search context-aware ranking",         MsearchRanking_Init, MsearchRanking_Run, MsearchRanking_Close, MsearchRanking_State);
    ToolStack_RegisterUnit(ts, "search_vector",    "search", "Qdrant vector + semantic search",      MsearchQdrant_Init, MsearchQdrant_Run, MsearchQdrant_Close, MsearchQdrant_State);
    ToolStack_RegisterUnit(ts, "search_composite", "search", "Magnetic radius + composite search",   MsearchMagnetic_Init, MsearchMagnetic_Run, MsearchMagnetic_Close, MsearchMagnetic_State);
    ToolStack_RegisterUnit(ts, "destruction_guard", "security", "Destruction guard with embedded SQLite learning", DestructionGuard_Init, DestructionGuard_Run, DestructionGuard_Close, DestructionGuard_State);
    /* Graph Engine — 10 units */
    ToolStack_RegisterUnit(ts, "graph_config",    "graph_engine", "Graph config parser",                GraphConfig_Init, GraphConfig_Run, GraphConfig_Close, GraphConfig_State);
    ToolStack_RegisterUnit(ts, "graph_view",      "graph_engine", "Programmable view lens over graph",  GraphView_Init, GraphView_Run, GraphView_Close, GraphView_State);
    ToolStack_RegisterUnit(ts, "graph_policy",    "graph_engine", "Expansion policy + executor",        GraphPolicy_Init, GraphPolicy_Run, GraphPolicy_Close, GraphPolicy_State);
    ToolStack_RegisterUnit(ts, "graph_expand",    "graph_engine", "Recursive expansion engine",         GraphExpand_Init, GraphExpand_Run, GraphExpand_Close, GraphExpand_State);
    ToolStack_RegisterUnit(ts, "graph_store",     "graph_engine", "MySQL/SQLite graph store",           GraphStore_Init, GraphStore_Run, GraphStore_Close, GraphStore_State);
    ToolStack_RegisterUnit(ts, "graph_compiler",  "graph_engine", "View to execution plan compiler",    GraphCompiler_Init, GraphCompiler_Run, GraphCompiler_Close, GraphCompiler_State);
    ToolStack_RegisterUnit(ts, "graph_optimizer", "graph_engine", "Plan optimizer with 3-part scoring", GraphOptimizer_Init, GraphOptimizer_Run, GraphOptimizer_Close, GraphOptimizer_State);
    ToolStack_RegisterUnit(ts, "graph_trace",     "graph_engine", "Immutable decision log",             GraphTrace_Init, GraphTrace_Run, GraphTrace_Close, GraphTrace_State);
    ToolStack_RegisterUnit(ts, "graph_cache",     "graph_engine", "4-layer scoped cache",               GraphCache_Init, GraphCache_Run, GraphCache_Close, GraphCache_State);
    ToolStack_RegisterUnit(ts, "graph_learning",  "graph_engine", "3-stage learning pipeline",          GraphLearning_Init, GraphLearning_Run, GraphLearning_Close, GraphLearning_State);
    /* Search units (source-based) — 3 new units, full VBSTYLE module-authority */
    ToolStack_RegisterUnit(ts, "search_web",       "search", "Web/URL search (HTTP fetch + HTML parse)",  SearchWeb_Init, SearchWeb_Run, SearchWeb_Close, SearchWeb_State);
    ToolStack_RegisterUnit(ts, "search_fs",        "search", "Filesystem search (dir walk + grep)",       SearchFs_Init, SearchFs_Run, SearchFs_Close, SearchFs_State);
    ToolStack_RegisterUnit(ts, "search_db",        "search", "MySQL database keyword search",   SearchDb_Init, SearchDb_Run, SearchDb_Close, SearchDb_State);
    /* VBAST units (tree-sitter AST) — 5 new units */
    ToolStack_RegisterUnit(ts, "ast_walker",       "vbast",  "Tree-sitter AST parse (classes/methods/imports)", AstWalker_Init, AstWalker_Run, AstWalker_Close, AstWalker_State);
    ToolStack_RegisterUnit(ts, "vbstyle_check",    "vbast",  "VBStyle compliance checks (11 rules)",          VbstyleChecker_Init, VbstyleChecker_Run, VbstyleChecker_Close, VbstyleChecker_State);
    ToolStack_RegisterUnit(ts, "graph_builder",    "vbast",  "Call/state/import graph edges from AST",        GraphBuilder_Init, GraphBuilder_Run, GraphBuilder_Close, GraphBuilder_State);
    ToolStack_RegisterUnit(ts, "bcl_stamper",      "vbast",  "BCL header stamp generator from AST",           BclStamper_Init, BclStamper_Run, BclStamper_Close, BclStamper_State);
    ToolStack_RegisterUnit(ts, "mysql_store",      "vbast",  "MySQL bcl_ir table writer (classes/methods/edges)", MysqlStore_Init, MysqlStore_Run, MysqlStore_Close, MysqlStore_State);
    /* VBStyle Rule units — 8 new units ported from core/Dom_Vsstyle/ Python domain */
    ToolStack_RegisterUnit(ts, "rule_reader",       "vsstyle", "Read rules from MySQL or JSON file",         RuleReader_Init, RuleReader_Run, RuleReader_Close, RuleReader_State);
    ToolStack_RegisterUnit(ts, "rule_writer",       "vsstyle", "Write rules to MySQL or JSON file",         RuleWriter_Init, RuleWriter_Run, RuleWriter_Close, RuleWriter_State);
    ToolStack_RegisterUnit(ts, "rule_engine",       "vsstyle", "Run VBStyle rules against code files",      RuleEngine_Init, RuleEngine_Run, RuleEngine_Close, RuleEngine_State);
    ToolStack_RegisterUnit(ts, "rule_enforcer",     "vsstyle", "Enforce rules, block violations",          RuleEnforcer_Init, RuleEnforcer_Run, RuleEnforcer_Close, RuleEnforcer_State);
    ToolStack_RegisterUnit(ts, "rule_gap_graph",    "vsstyle", "Find rule coverage gaps",                  RuleGapGraph_Init, RuleGapGraph_Run, RuleGapGraph_Close, RuleGapGraph_State);
    ToolStack_RegisterUnit(ts, "rule_cluster_graph","vsstyle", "Cluster rules by keyword similarity",      RuleClusterGraph_Init, RuleClusterGraph_Run, RuleClusterGraph_Close, RuleClusterGraph_State);
    ToolStack_RegisterUnit(ts, "rule_coverage_graph","vsstyle","Map rules to code entities",               RuleCoverageGraph_Init, RuleCoverageGraph_Run, RuleCoverageGraph_Close, RuleCoverageGraph_State);
    ToolStack_RegisterUnit(ts, "code_index",        "vsstyle", "Index code files into MySQL vb_code_test", CodeIndex_Init, CodeIndex_Run, CodeIndex_Close, CodeIndex_State);
    ToolStack_RegisterUnit(ts, "reports",           "vsstyle", "Unified report generator (LiveState+Inspector+Viewer+Config)", Reports_Init, Reports_Run, Reports_Close, Reports_State);
}

/* ===== CLI ENTRY POINT ===== */

int main(int argc, char *argv[]) {
    ToolStack_Init(&TS, NULL);
    RegisterAll(&TS);
    
    if (argc < 2) {
        fprintf(stderr, "Usage: bcl_tool list | bcl_tool pipeline <packet> | bcl_tool dispatch <packet> | bcl_tool <unit> <command> [bcl_input]\n");
        fprintf(stderr, "Units: pb_reader, chat_ingest, cleaner,\n");
        fprintf(stderr, "       mdmerge, discovery,\n");
        fprintf(stderr, "       schemalint, vbcheck, ghostctl, smartcli, wcmd,\n");
        fprintf(stderr, "       codeingest, cognitive, error_fix, windir,\n");
        fprintf(stderr, "       search_help, search_registry, search_ranking,\n");
        fprintf(stderr, "       search_vector, search_composite, destruction_guard,\n");
        fprintf(stderr, "       graph_config, graph_view, graph_policy, graph_expand,\n");
        fprintf(stderr, "       graph_store, graph_compiler, graph_optimizer,\n");
        fprintf(stderr, "       graph_trace, graph_cache, graph_learning,\n");
        fprintf(stderr, "       search_web, search_fs, search_db,\n");
        fprintf(stderr, "       ast_walker, vbstyle_check, graph_builder,\n");
        fprintf(stderr, "       bcl_stamper, mysql_store,\n");
        fprintf(stderr, "       rule_reader, rule_writer, rule_engine, rule_enforcer,\n");
        fprintf(stderr, "       rule_gap_graph, rule_cluster_graph, rule_coverage_graph,\n");
        fprintf(stderr, "       code_index, reports\n");
        return 1;
    }
    
    if (strcmp(argv[1], "list") == 0) {
        const char *result = ToolStack_Run(&TS, "list", NULL);
        printf("%s\n", result);
        ToolStack_Close(&TS);
        return 0;
    }
    
    if (strcmp(argv[1], "pipeline") == 0) {
        if (argc < 3) {
            fprintf(stderr, "Usage: bcl_tool pipeline <bcl_packet>\n");
            fprintf(stderr, "  e.g. bcl_tool pipeline '[@PATH]{/path/to/dir}[@STEPS]{scan,check,report}'\n");
            fprintf(stderr, "  Steps: scan, index, check, enforce, report, read_rules, gaps, clusters, coverage, vbcheck\n");
            ToolStack_Close(&TS);
            return 1;
        }
        const char *result = ToolStack_Run(&TS, "pipeline", argv[2]);
        printf("%s\n", result);
        ToolStack_Close(&TS);
        return 0;
    }
    
    if (strcmp(argv[1], "dispatch") == 0) {
        if (argc < 3) {
            fprintf(stderr, "Usage: bcl_tool dispatch <bcl_packet>\n");
            ToolStack_Close(&TS);
            return 1;
        }
        const char *result = ToolStack_Run(&TS, "dispatch", argv[2]);
        printf("%s\n", result);
        ToolStack_Close(&TS);
        return 0;
    }
    
    /* Direct unit dispatch: bcl_tool <unit> <command> [bcl_input] */
    if (argc >= 3) {
        const char *unit = argv[1];
        const char *cmd = argv[2];
        const char *bcl_in = (argc >= 4) ? argv[3] : "";
        int ok = ToolStack_Dispatch(&TS, unit, cmd, bcl_in, RESULT_BUF, TOOL_MAX_RESULT);
        printf("%s\n", RESULT_BUF);
        ToolStack_Close(&TS);
        return ok ? 0 : 1;
    }
    
    fprintf(stderr, "Unknown command: %s\n", argv[1]);
    ToolStack_Close(&TS);
    return 1;
}
