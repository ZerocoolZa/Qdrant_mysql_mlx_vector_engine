//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_msearch_help.c" date="2026-07-03" author="cascade" session_id="bcl-msearch-units" context="BCL unit for msearch help and AI guidance. Stores usage text and rules that the CLI reads out when AI queries help. Contains LAW62 and LAW63 about examining all search results before reasoning."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_msearch_help.c" domain="cascade_tools" authority="MsearchHelp"}
//[@SUMMARY]{summary="Help and AI guidance for msearch. Commands: help, rules, usage, read_state, set_config. Stores the rules about examining all results before reasoning. When the AI runs msearch help it gets back the guidance text."}
//[@CLASS]{class="MsearchHelp" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}

/*
 * bcl_msearch_help.c — Help text and AI guidance for msearch
 *
 * BCL IN:  [@RUN]{[@CMD]{help}}
 *          [@RUN]{[@CMD]{rules}}
 *          [@RUN]{[@CMD]{usage}}
 *          [@RUN]{[@CMD]{read_state}}
 * BCL OUT: [@OK]{[@HELP]{...}[@RULES]{...}[@USAGE]{...}}
 * BCL ERR: [@ERR]{[@CODE]{N}[@DESC]{...}}
 */

#include "bcl_toolstack.h"

/* ===== GUIDANCE TEXT ===== */

static const char *HELP_TEXT =
    "msearch — MySQL keyword search across knowledge databases\n"
    "\n"
    "Commands:\n"
    "  search <keyword>   Search all known tables for keyword\n"
    "  count <keyword>    Count matches per table\n"
    "  where [db]         List tables in database\n"
    "  stats              Show database statistics\n"
    "  help               Show this help text\n"
    "  rules              Show AI usage rules\n"
    "  usage              Show usage examples\n"
    "  read_state         Show current state\n"
    "  set_config         Set connection config\n"
    "\n"
    "Options:\n"
    "  --limit N          Max results per table (default 50)\n"
    "  --mode M           Match mode: exact, prefix, contains, regex\n"
    "  --json             JSON output mode\n"
    "  --all-db           Search across all databases\n"
    "  --semantic         Qdrant vector search\n"
    "  --hybrid           MySQL + Qdrant combined\n"
    "  --magnetic         Context reconstruction with radius\n"
    "  --radius N         Expansion size for magnetic mode\n"
    "  --count            Show match counts only, no rows\n"
    "  --verbose          Verbose output\n";

static const char *AI_RULES =
    "RULE 1: Do not stop on the first result. Collect all results. Reason over all of them.\n"
    "  When msearch returns multiple matches, you must examine every match before drawing conclusions.\n"
    "  Stopping at the first result and missing the answer in result 18 is a failure.\n"
    "\n"
    "RULE 2: Use the requested tool. Do not substitute.\n"
    "  When told to use msearch, use msearch. Do not substitute with MySQL queries, grep, find,\n"
    "  or any other tool. Run the exact tool the user asked for.\n"
    "\n"
    "RULE 3: Examine all search results then reason.\n"
    "  Read every match returned. Reason over the complete set. Then draw conclusions.\n"
    "  Do not look at the first result and stop. Do not skip results.\n"
    "\n"
    "RULE 4: Do not run unrequested commands.\n"
    "  When told to search for something, search for that only. Do not run tangential searches.\n"
    "  Do not run find, grep, or DROP searches that were not explicitly requested.\n"
    "\n"
    "RULE 5: Answer the question asked.\n"
    "  When asked a question, answer directly. Do not go off and do something else.\n"
    "\n"
    "RULE 6: Do not negotiate.\n"
    "  When given an instruction, execute it. Do not offer alternatives.\n"
    "  The user is not negotiating. They are giving an instruction.\n";

static const char *USAGE_TEXT =
    "Usage:\n"
    "  msearch search \"DevinSync sqlite mysql\"\n"
    "  msearch search \"sessions.db\" --limit 100\n"
    "  msearch count \"learned_rules\"\n"
    "  msearch where vb_shared\n"
    "  msearch stats\n"
    "  msearch help\n"
    "  msearch rules\n"
    "\n"
    "BCL packet format:\n"
    "  [@RUN]{[@CMD]{search}[@QUERY]{keyword}[@LIMIT]{50}}\n"
    "  [@RUN]{[@CMD]{count}[@QUERY]{keyword}}\n"
    "  [@RUN]{[@CMD]{where}[@DB]{vb_shared}}\n"
    "  [@RUN]{[@CMD]{stats}}\n"
    "  [@RUN]{[@CMD]{help}}\n"
    "  [@RUN]{[@CMD]{rules}}\n";

/* ===== STATE ===== */

static struct {
    int initialized;
    int help_requests;
    int rule_requests;
} STATE;

/* ===== UNIT INTERFACE ===== */

int MsearchHelp_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    return 1;
}

int MsearchHelp_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) MsearchHelp_Init();

    /* ===== HELP — full help text ===== */
    if (strcmp(cmd, "help") == 0) {
        STATE.help_requests++;
        return BclResult_Ok(bcl_out, out_sz, HELP_TEXT);
    }

    /* ===== RULES — AI guidance rules ===== */
    if (strcmp(cmd, "rules") == 0) {
        STATE.rule_requests++;
        return BclResult_Ok(bcl_out, out_sz, AI_RULES);
    }

    /* ===== USAGE — usage examples ===== */
    if (strcmp(cmd, "usage") == 0) {
        return BclResult_Ok(bcl_out, out_sz, USAGE_TEXT);
    }

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        char body[256];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@HELP_REQUESTS]{%d}[@RULE_REQUESTS]{%d}",
            STATE.initialized, STATE.help_requests, STATE.rule_requests);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== SET_CONFIG ===== */
    if (strcmp(cmd, "set_config") == 0) {
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }

    return BclResult_Err(bcl_out, out_sz, 404, "unknown command");
}

int MsearchHelp_Close(void) {
    STATE.initialized = 0;
    return 1;
}

const char * MsearchHelp_State(void) {
    static char buf[128];
    snprintf(buf, sizeof(buf),
        "MsearchHelp: initialized=%d help_reqs=%d rule_reqs=%d",
        STATE.initialized, STATE.help_requests, STATE.rule_requests);
    return buf;
}
