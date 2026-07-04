//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_msearch_qdrant.c" date="2026-07-03" author="cascade" session_id="bcl-msearch-units" context="BCL unit for msearch Qdrant vector search and semantic search. Broken from msearch_v5.c sections: QDRANT VECTOR SEARCH, FULL SEMANTIC OBJECT SEARCH."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_msearch_qdrant.c" domain="cascade_tools" authority="MsearchQdrant"}
//[@SUMMARY]{summary="Qdrant vector search and semantic object search for msearch. Commands: semantic, multi, full, qstats, read_state, set_config. Calls Qdrant helper script for vector search, supports multi-dimension and full semantic object search."}
//[@CLASS]{class="MsearchQdrant" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="SemanticSearch" type="query"}
//[@METHOD]{method="MultiDimension" type="query"}
//[@METHOD]{method="FullObjectSearch" type="query"}
//[@METHOD]{method="QdrantStats" type="query"}

/*
 * bcl_msearch_qdrant.c — Qdrant vector search and semantic search
 *
 * BCL IN:  [@RUN]{[@CMD]{semantic}[@QUERY]{keyword}[@DIMENSION]{dim_semantic}[@TOP]{10}}
 *          [@RUN]{[@CMD]{multi}[@QUERY]{keyword}[@DIMENSIONS]{dim1,dim2}}
 *          [@RUN]{[@CMD]{full}[@QUERY]{keyword}[@TOP]{10}}
 *          [@RUN]{[@CMD]{qstats}[@DIMENSION]{dim_semantic}}
 *          [@RUN]{[@CMD]{read_state}}
 * BCL OUT: [@OK]{[@VECTOR]{...}[@SCORE]{0.95}[@PAYLOAD]{...}}
 * BCL ERR: [@ERR]{[@CODE]{N}[@DESC]{...}}
 */

#include "bcl_toolstack.h"
#include <mysql.h>

/* ===== DIM BLOCK ===== */

#define QDRANT_HELPER        "/Users/wws/bin/msearch_qdrant.py"
#define QDRANT_DEFAULT_COLL  "dim_semantic"
#define QDRANT_DEFAULT_TOP   10
#define QDRANT_MAX_QUERY     4096
#define QDRANT_MAX_DIM       128
#define QDRANT_MAX_OUTPUT    65536
#define QDRANT_HOST_LEN      256
#define QDRANT_USER_LEN      64
#define QDRANT_PASS_LEN      128
#define QDRANT_SOCKET_LEN    256

/* ===== STATE ===== */

static struct {
    int initialized;
    int semantic_searches;
    int multi_searches;
    int full_searches;
    int stats_requests;
    char default_collection[64];
    char helper_path[256];
    char host[QDRANT_HOST_LEN];
    char user[QDRANT_USER_LEN];
    char pass[QDRANT_PASS_LEN];
    char socket[QDRANT_SOCKET_LEN];
    int port;
    char last_error[256];
} STATE;

/* ===== UTILITIES ===== */

static void qdr_escape_like(const char *in, char *out, size_t out_sz) {
    size_t j = 0;
    for (size_t i = 0; in[i] && j + 2 < out_sz; i++) {
        if (in[i] == '%' || in[i] == '_' || in[i] == '\\')
            out[j++] = '\\';
        out[j++] = in[i];
    }
    out[j] = '\0';
}

static void qdr_clean(const char *in, char *out, size_t out_sz) {
    size_t j = 0;
    for (size_t i = 0; in[i] && j + 1 < out_sz; i++) {
        if (in[i] == '\n' || in[i] == '\r') out[j++] = ' ';
        else if (in[i] == '{' || in[i] == '}') out[j++] = ' ';
        else if (in[i] == '[' && in[i+1] == '@') out[j++] = ' ';
        else out[j++] = in[i];
    }
    out[j] = '\0';
}

static MYSQL *qdr_connect(const char *db) {
    MYSQL *conn = mysql_init(NULL);
    if (!conn) return NULL;
    const char *sock = STATE.socket[0] ? STATE.socket : "/tmp/mysql.sock";
    if (!mysql_real_connect(conn, STATE.host, STATE.user,
            STATE.pass[0] ? STATE.pass : NULL,
            db, STATE.port, sock, 0)) {
        mysql_close(conn);
        return NULL;
    }
    return conn;
}

/* ===== RUN QDRANT HELPER ===== */

static int run_qdrant(const char *query, const char *collection, int top,
                      char *out, size_t out_sz) {
    char cmd[8192];
    char esc_query[QDRANT_MAX_QUERY];
    /* Shell-escape the query */
    size_t j = 0;
    for (size_t i = 0; query[i] && j < sizeof(esc_query) - 4; i++) {
        if (query[i] == '\'') { esc_query[j++] = '\''; esc_query[j++] = '\''; }
        else esc_query[j++] = query[i];
    }
    esc_query[j] = '\0';

    snprintf(cmd, sizeof(cmd),
        "python3 %s --query '%s' --collection %s --top %d 2>/dev/null",
        STATE.helper_path, esc_query, collection, top);

    FILE *fp = popen(cmd, "r");
    if (!fp) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "popen failed for qdrant helper");
        return 0;
    }

    size_t total = fread(out, 1, out_sz - 1, fp);
    pclose(fp);
    out[total] = '\0';
    return (int)total;
}

/* ===== UNIT INTERFACE ===== */

int MsearchQdrant_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    strncpy(STATE.default_collection, QDRANT_DEFAULT_COLL, sizeof(STATE.default_collection) - 1);
    strncpy(STATE.helper_path, QDRANT_HELPER, sizeof(STATE.helper_path) - 1);
    strncpy(STATE.host, "localhost", sizeof(STATE.host) - 1);
    strncpy(STATE.user, "root", sizeof(STATE.user) - 1);
    STATE.port = 3306;
    strncpy(STATE.socket, "/tmp/mysql.sock", sizeof(STATE.socket) - 1);
    STATE.initialized = 1;
    return 1;
}

int MsearchQdrant_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) MsearchQdrant_Init();

    /* ===== SEMANTIC — Qdrant vector search ===== */
    if (strcmp(cmd, "semantic") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[QDRANT_MAX_QUERY] = {0};
        char dimension[QDRANT_MAX_DIM] = {0};
        char top_str[16] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "DIMENSION", dimension, sizeof(dimension));
        BclParser_Extract(&parse, "TOP", top_str, sizeof(top_str));
        BclParser_Free(&parse);
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        const char *coll = dimension[0] ? dimension : STATE.default_collection;
        int top = top_str[0] ? atoi(top_str) : QDRANT_DEFAULT_TOP;

        char raw_out[QDRANT_MAX_OUTPUT];
        int bytes = run_qdrant(query, coll, top, raw_out, sizeof(raw_out));
        if (bytes <= 0) {
            return BclResult_Err(bcl_out, out_sz, 30, STATE.last_error);
        }
        STATE.semantic_searches++;
        snprintf(bcl_out, out_sz, "[@OK]{[@QUERY]{%s}[@COLLECTION]{%s}[@TOP]{%d}[@RESULTS]{%.60000s}}",
            query, coll, top, raw_out);
        return 1;
    }

    /* ===== MULTI — multi-dimension search across Qdrant collections ===== */
    if (strcmp(cmd, "multi") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[QDRANT_MAX_QUERY] = {0};
        char dimensions[512] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "DIMENSIONS", dimensions, sizeof(dimensions));
        BclParser_Free(&parse);
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        STATE.multi_searches++;

        char dims[512];
        strncpy(dims, dimensions[0] ? dimensions : "dim_semantic,dim_code,dim_errors", sizeof(dims) - 1);
        dims[sizeof(dims) - 1] = '\0';

        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@OK]{[@QUERY]{%s}[@RESULTS]{", query);

        char *dim = strtok(dims, ",");
        int dim_count = 0;
        while (dim && offset < (int)out_sz - 2048) {
            while (*dim == ' ') dim++;
            char raw_out[8192];
            int bytes = run_qdrant(query, dim, QDRANT_DEFAULT_TOP, raw_out, sizeof(raw_out));
            if (bytes > 0) {
                offset += snprintf(bcl_out + offset, out_sz - offset,
                    "[@DIM]{[@NAME]{%s}[@HITS]{%.6000s}}", dim, raw_out);
                dim_count++;
            }
            dim = strtok(NULL, ",");
        }

        offset = strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset, "[@DIM_COUNT]{%d}}", dim_count);
        return 1;
    }

    /* ===== FULL — full semantic object search (12 MySQL sections) ===== */
    if (strcmp(cmd, "full") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char query[QDRANT_MAX_QUERY] = {0};
        char top_str[16] = {0};
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Extract(&parse, "TOP", top_str, sizeof(top_str));
        BclParser_Free(&parse);
        if (!query[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no QUERY in packet");
        }
        int limit = top_str[0] ? atoi(top_str) : QDRANT_DEFAULT_TOP;
        STATE.full_searches++;

        MYSQL *conn = qdr_connect("vb_shared");
        if (!conn) {
            return BclResult_Err(bcl_out, out_sz, 10, "MySQL connect failed for full search");
        }

        char esc_key[QDRANT_MAX_QUERY];
        qdr_escape_like(query, esc_key, sizeof(esc_key));

        int offset = 0;
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@OK]{[@QUERY]{%s}[@SECTIONS]{", query);

        /* 1. AUTHORITY — class_understandings */
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@AUTHORITY]{");
        {
            char q[QDRANT_MAX_QUERY];
            snprintf(q, sizeof(q),
                "SELECT class_name, cascade_understanding, layer FROM class_understandings "
                "WHERE class_name LIKE '%%%s%%' OR cascade_understanding LIKE '%%%s%%' LIMIT %d",
                esc_key, esc_key, limit > 3 ? 3 : limit);
            if (mysql_query(conn, q) == 0) {
                MYSQL_RES *res = mysql_store_result(conn);
                if (res) {
                    MYSQL_ROW row;
                    while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                        char cn[512], cu[4096];
                        qdr_clean(row[0] ? row[0] : "", cn, sizeof(cn));
                        qdr_clean(row[1] ? row[1] : "", cu, sizeof(cu));
                        offset += snprintf(bcl_out + offset, out_sz - offset,
                            "[@ENTRY]{[@CLASS]{%s}[@UNDERSTANDING]{%.500s}[@LAYER]{%s}}",
                            cn, cu, row[2] ? row[2] : "");
                    }
                    mysql_free_result(res);
                }
            }
        }
        offset += snprintf(bcl_out + offset, out_sz - offset, "}");

        /* 2. FILES — code_classes */
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@FILES]{");
        {
            char q[QDRANT_MAX_QUERY];
            snprintf(q, sizeof(q),
                "SELECT class_name, description FROM code_classes "
                "WHERE class_name LIKE '%%%s%%' LIMIT %d",
                esc_key, limit);
            if (mysql_query(conn, q) == 0) {
                MYSQL_RES *res = mysql_store_result(conn);
                if (res) {
                    MYSQL_ROW row;
                    while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                        char cn[512], desc[1024];
                        qdr_clean(row[0] ? row[0] : "", cn, sizeof(cn));
                        qdr_clean(row[1] ? row[1] : "", desc, sizeof(desc));
                        offset += snprintf(bcl_out + offset, out_sz - offset,
                            "[@ENTRY]{[@CLASS]{%s}[@DESCRIPTION]{%.300s}}", cn, desc);
                    }
                    mysql_free_result(res);
                }
            }
        }
        offset += snprintf(bcl_out + offset, out_sz - offset, "}");

        /* 3. METHODS — code_index */
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@METHODS]{");
        {
            char q[QDRANT_MAX_QUERY];
            snprintf(q, sizeof(q),
                "SELECT entity_name, entity_type, related_entity, relationship "
                "FROM code_index WHERE entity_name LIKE '%%%s%%' "
                "OR related_entity LIKE '%%%s%%' LIMIT %d",
                esc_key, esc_key, limit);
            if (mysql_query(conn, q) == 0) {
                MYSQL_RES *res = mysql_store_result(conn);
                if (res) {
                    MYSQL_ROW row;
                    while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                        char en[512], re[512];
                        qdr_clean(row[0] ? row[0] : "", en, sizeof(en));
                        qdr_clean(row[2] ? row[2] : "", re, sizeof(re));
                        offset += snprintf(bcl_out + offset, out_sz - offset,
                            "[@ENTRY]{[@ENTITY]{%s}[@TYPE]{%s}[@RELATED]{%s}[@REL]{%s}}",
                            en, row[1] ? row[1] : "", re, row[3] ? row[3] : "");
                    }
                    mysql_free_result(res);
                }
            }
        }
        offset += snprintf(bcl_out + offset, out_sz - offset, "}");

        /* 4. RELATIONSHIPS — code_co_occurrence */
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@RELATIONSHIPS]{");
        {
            char q[QDRANT_MAX_QUERY];
            snprintf(q, sizeof(q),
                "SELECT entity_a, entity_b, relationship_type, weight "
                "FROM code_co_occurrence WHERE entity_a LIKE '%%%s%%' "
                "OR entity_b LIKE '%%%s%%' LIMIT %d",
                esc_key, esc_key, limit);
            if (mysql_query(conn, q) == 0) {
                MYSQL_RES *res = mysql_store_result(conn);
                if (res) {
                    MYSQL_ROW row;
                    while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                        char ea[512], eb[512], rt[128];
                        qdr_clean(row[0] ? row[0] : "", ea, sizeof(ea));
                        qdr_clean(row[1] ? row[1] : "", eb, sizeof(eb));
                        qdr_clean(row[2] ? row[2] : "", rt, sizeof(rt));
                        offset += snprintf(bcl_out + offset, out_sz - offset,
                            "[@ENTRY]{[@A]{%s}[@B]{%s}[@TYPE]{%s}[@WEIGHT]{%s}}",
                            ea, eb, rt, row[3] ? row[3] : "1");
                    }
                    mysql_free_result(res);
                }
            }
        }
        offset += snprintf(bcl_out + offset, out_sz - offset, "}");

        /* 5. RULES — learned_rules */
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@RULES]{");
        {
            char q[QDRANT_MAX_QUERY];
            snprintf(q, sizeof(q),
                "SELECT pattern, fix_action, confidence FROM learned_rules "
                "WHERE pattern LIKE '%%%s%%' OR fix_action LIKE '%%%s%%' "
                "ORDER BY confidence DESC LIMIT %d",
                esc_key, esc_key, limit > 5 ? 5 : limit);
            if (mysql_query(conn, q) == 0) {
                MYSQL_RES *res = mysql_store_result(conn);
                if (res) {
                    MYSQL_ROW row;
                    while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                        char pat[2048], fix[2048];
                        qdr_clean(row[0] ? row[0] : "", pat, sizeof(pat));
                        qdr_clean(row[1] ? row[1] : "", fix, sizeof(fix));
                        offset += snprintf(bcl_out + offset, out_sz - offset,
                            "[@RULE]{[@PATTERN]{%.500s}[@FIX]{%.500s}[@CONFIDENCE]{%s}}",
                            pat, fix, row[2] ? row[2] : "0");
                    }
                    mysql_free_result(res);
                }
            }
        }
        offset += snprintf(bcl_out + offset, out_sz - offset, "}");

        /* 6. EXAMPLES — code_registry */
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@EXAMPLES]{");
        {
            char q[QDRANT_MAX_QUERY];
            snprintf(q, sizeof(q),
                "SELECT token_name, LEFT(code, 500) FROM code_registry "
                "WHERE token_name LIKE '%%%s%%' LIMIT %d",
                esc_key, limit > 3 ? 3 : limit);
            if (mysql_query(conn, q) == 0) {
                MYSQL_RES *res = mysql_store_result(conn);
                if (res) {
                    MYSQL_ROW row;
                    while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                        char tn[512], code[2048];
                        qdr_clean(row[0] ? row[0] : "", tn, sizeof(tn));
                        qdr_clean(row[1] ? row[1] : "", code, sizeof(code));
                        offset += snprintf(bcl_out + offset, out_sz - offset,
                            "[@ENTRY]{[@NAME]{%s}[@PREVIEW]{%.500s}}", tn, code);
                    }
                    mysql_free_result(res);
                }
            }
        }
        offset += snprintf(bcl_out + offset, out_sz - offset, "}");

        /* 7. HISTORY — execution_log */
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@HISTORY]{");
        {
            char q[QDRANT_MAX_QUERY];
            snprintf(q, sizeof(q),
                "SELECT command, status, timestamp FROM execution_log "
                "WHERE command LIKE '%%%s%%' ORDER BY timestamp DESC LIMIT %d",
                esc_key, limit > 5 ? 5 : limit);
            if (mysql_query(conn, q) == 0) {
                MYSQL_RES *res = mysql_store_result(conn);
                if (res) {
                    MYSQL_ROW row;
                    while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                        char cmd[2048];
                        qdr_clean(row[0] ? row[0] : "", cmd, sizeof(cmd));
                        offset += snprintf(bcl_out + offset, out_sz - offset,
                            "[@ENTRY]{[@COMMAND]{%.500s}[@STATUS]{%s}[@TIME]{%s}}",
                            cmd, row[1] ? row[1] : "", row[2] ? row[2] : "");
                    }
                    mysql_free_result(res);
                }
            }
        }
        offset += snprintf(bcl_out + offset, out_sz - offset, "}");

        /* 8. ERRORS — error_knowledge */
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@ERRORS]{");
        {
            char q[QDRANT_MAX_QUERY];
            snprintf(q, sizeof(q),
                "SELECT error_type, cause, solution FROM error_knowledge "
                "WHERE error_type LIKE '%%%s%%' OR cause LIKE '%%%s%%' LIMIT %d",
                esc_key, esc_key, limit > 3 ? 3 : limit);
            if (mysql_query(conn, q) == 0) {
                MYSQL_RES *res = mysql_store_result(conn);
                if (res) {
                    MYSQL_ROW row;
                    while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                        char et[512], cause[2048], sol[2048];
                        qdr_clean(row[0] ? row[0] : "", et, sizeof(et));
                        qdr_clean(row[1] ? row[1] : "", cause, sizeof(cause));
                        qdr_clean(row[2] ? row[2] : "", sol, sizeof(sol));
                        offset += snprintf(bcl_out + offset, out_sz - offset,
                            "[@ENTRY]{[@TYPE]{%s}[@CAUSE]{%.500s}[@SOLUTION]{%.500s}}",
                            et, cause, sol);
                    }
                    mysql_free_result(res);
                }
            }
        }
        offset += snprintf(bcl_out + offset, out_sz - offset, "}");

        /* 9. RELATED — code_identifier_frequency */
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@RELATED]{");
        {
            char q[QDRANT_MAX_QUERY];
            snprintf(q, sizeof(q),
                "SELECT identifier, identifier_type, authority_score "
                "FROM code_identifier_frequency WHERE identifier LIKE '%%%s%%' "
                "ORDER BY authority_score DESC LIMIT %d",
                esc_key, limit > 10 ? 10 : limit);
            if (mysql_query(conn, q) == 0) {
                MYSQL_RES *res = mysql_store_result(conn);
                if (res) {
                    MYSQL_ROW row;
                    while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                        char id[512];
                        qdr_clean(row[0] ? row[0] : "", id, sizeof(id));
                        offset += snprintf(bcl_out + offset, out_sz - offset,
                            "[@ENTRY]{[@IDENTIFIER]{%s}[@TYPE]{%s}[@AUTHORITY]{%s}}",
                            id, row[1] ? row[1] : "", row[2] ? row[2] : "0");
                    }
                    mysql_free_result(res);
                }
            }
        }
        offset += snprintf(bcl_out + offset, out_sz - offset, "}");

        /* 10. RATIONALE — designrationale */
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@RATIONALE]{");
        {
            char q[QDRANT_MAX_QUERY];
            snprintf(q, sizeof(q),
                "SELECT subject, rationale, category FROM designrationale "
                "WHERE subject LIKE '%%%s%%' OR rationale LIKE '%%%s%%' LIMIT %d",
                esc_key, esc_key, limit > 3 ? 3 : limit);
            if (mysql_query(conn, q) == 0) {
                MYSQL_RES *res = mysql_store_result(conn);
                if (res) {
                    MYSQL_ROW row;
                    while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                        char subj[512], rat[4096];
                        qdr_clean(row[0] ? row[0] : "", subj, sizeof(subj));
                        qdr_clean(row[1] ? row[1] : "", rat, sizeof(rat));
                        offset += snprintf(bcl_out + offset, out_sz - offset,
                            "[@ENTRY]{[@SUBJECT]{%s}[@RATIONALE]{%.500s}[@CATEGORY]{%s}}",
                            subj, rat, row[2] ? row[2] : "");
                    }
                    mysql_free_result(res);
                }
            }
        }
        offset += snprintf(bcl_out + offset, out_sz - offset, "}");

        /* 11. PROBLEMS — know_problems */
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@PROBLEMS]{");
        {
            char q[QDRANT_MAX_QUERY];
            snprintf(q, sizeof(q),
                "SELECT problem, description FROM know_problems "
                "WHERE problem LIKE '%%%s%%' OR description LIKE '%%%s%%' LIMIT %d",
                esc_key, esc_key, limit > 3 ? 3 : limit);
            if (mysql_query(conn, q) == 0) {
                MYSQL_RES *res = mysql_store_result(conn);
                if (res) {
                    MYSQL_ROW row;
                    while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                        char prob[512], desc[2048];
                        qdr_clean(row[0] ? row[0] : "", prob, sizeof(prob));
                        qdr_clean(row[1] ? row[1] : "", desc, sizeof(desc));
                        offset += snprintf(bcl_out + offset, out_sz - offset,
                            "[@ENTRY]{[@PROBLEM]{%s}[@DESCRIPTION]{%.500s}}", prob, desc);
                    }
                    mysql_free_result(res);
                }
            }
        }
        offset += snprintf(bcl_out + offset, out_sz - offset, "}");

        /* 12. DECISIONS — decision_trees */
        offset += snprintf(bcl_out + offset, out_sz - offset, "[@DECISIONS]{");
        {
            char q[QDRANT_MAX_QUERY];
            snprintf(q, sizeof(q),
                "SELECT tree FROM decision_trees WHERE tree LIKE '%%%s%%' LIMIT %d",
                esc_key, limit > 3 ? 3 : limit);
            if (mysql_query(conn, q) == 0) {
                MYSQL_RES *res = mysql_store_result(conn);
                if (res) {
                    MYSQL_ROW row;
                    while ((row = mysql_fetch_row(res)) != NULL && offset < (int)out_sz - 512) {
                        char tree[4096];
                        qdr_clean(row[0] ? row[0] : "", tree, sizeof(tree));
                        offset += snprintf(bcl_out + offset, out_sz - offset,
                            "[@ENTRY]{%.1000s}", tree);
                    }
                    mysql_free_result(res);
                }
            }
        }
        offset += snprintf(bcl_out + offset, out_sz - offset, "}");

        offset = strlen(bcl_out);
        snprintf(bcl_out + offset, out_sz - offset,
            "}[@ACTIONS]{open,edit,ingest,verify,reindex}}");
        mysql_close(conn);
        return 1;
    }

    /* ===== QSTATS — Qdrant collection stats ===== */
    if (strcmp(cmd, "qstats") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char dimension[QDRANT_MAX_DIM] = {0};
        BclParser_Extract(&parse, "DIMENSION", dimension, sizeof(dimension));
        BclParser_Free(&parse);
        const char *coll = dimension[0] ? dimension : STATE.default_collection;

        char cmd_str[1024];
        snprintf(cmd_str, sizeof(cmd_str),
            "python3 %s --stats --collection %s 2>/dev/null",
            STATE.helper_path, coll);
        FILE *fp = popen(cmd_str, "r");
        if (!fp) {
            return BclResult_Err(bcl_out, out_sz, 30, "popen failed for qdrant stats");
        }
        char raw_out[4096];
        size_t total = fread(raw_out, 1, sizeof(raw_out) - 1, fp);
        pclose(fp);
        raw_out[total] = '\0';
        STATE.stats_requests++;
        snprintf(bcl_out, out_sz, "[@OK]{[@COLLECTION]{%s}[@STATS]{%.4000s}}",
            coll, raw_out);
        return 1;
    }

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        char body[512];
        snprintf(body, sizeof(body),
            "[@INITIALIZED]{%d}[@SEMANTIC]{%d}[@MULTI]{%d}[@FULL]{%d}[@STATS]{%d}[@COLLECTION]{%s}[@ERROR]{%s}",
            STATE.initialized, STATE.semantic_searches, STATE.multi_searches,
            STATE.full_searches, STATE.stats_requests,
            STATE.default_collection,
            STATE.last_error[0] ? STATE.last_error : "none");
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    /* ===== SET_CONFIG ===== */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char collection[64] = {0};
        char helper[256] = {0};
        char host[QDRANT_HOST_LEN] = {0};
        char user[QDRANT_USER_LEN] = {0};
        char pass[QDRANT_PASS_LEN] = {0};
        char socket[QDRANT_SOCKET_LEN] = {0};
        char port_str[16] = {0};
        BclParser_Extract(&parse, "COLLECTION", collection, sizeof(collection));
        BclParser_Extract(&parse, "HELPER", helper, sizeof(helper));
        BclParser_Extract(&parse, "HOST", host, sizeof(host));
        BclParser_Extract(&parse, "USER", user, sizeof(user));
        BclParser_Extract(&parse, "PASS", pass, sizeof(pass));
        BclParser_Extract(&parse, "SOCKET", socket, sizeof(socket));
        BclParser_Extract(&parse, "PORT", port_str, sizeof(port_str));
        BclParser_Free(&parse);
        if (collection[0]) strncpy(STATE.default_collection, collection, sizeof(STATE.default_collection) - 1);
        if (helper[0]) strncpy(STATE.helper_path, helper, sizeof(STATE.helper_path) - 1);
        if (host[0]) strncpy(STATE.host, host, sizeof(STATE.host) - 1);
        if (user[0]) strncpy(STATE.user, user, sizeof(STATE.user) - 1);
        if (pass[0]) strncpy(STATE.pass, pass, sizeof(STATE.pass) - 1);
        if (socket[0]) strncpy(STATE.socket, socket, sizeof(STATE.socket) - 1);
        if (port_str[0]) STATE.port = atoi(port_str);
        char body[512];
        snprintf(body, sizeof(body),
            "[@COLLECTION]{%s}[@HELPER]{%s}[@HOST]{%s}[@PORT]{%d}",
            STATE.default_collection, STATE.helper_path, STATE.host, STATE.port);
        return BclResult_Ok(bcl_out, out_sz, body);
    }

    return BclResult_Err(bcl_out, out_sz, 404, "unknown command");
}

int MsearchQdrant_Close(void) {
    STATE.initialized = 0;
    return 1;
}

const char * MsearchQdrant_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "MsearchQdrant: initialized=%d semantic=%d multi=%d full=%d stats=%d",
        STATE.initialized, STATE.semantic_searches, STATE.multi_searches,
        STATE.full_searches, STATE.stats_requests);
    return buf;
}
