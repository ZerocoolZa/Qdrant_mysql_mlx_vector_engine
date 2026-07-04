/*
 * bh_query.c - Query engine: gets data from DB, passes to report module
 *[@GHOST]
 *[@VBSTYLE]
 *[@FILEID] bh_query.c
 *[@SUMMARY] Search scents, get relationships, trails, stats. All output via bh_report.
 *[@CLASS] BloodhoundQuery
 *[@METHOD] Text, Remember, Similar, Relationships, Trails, Stats, Recent, FileContent
 */

#include "bh_report.h"

/* ---- Match counter ---- */

typedef struct {
    bh_db *db;
    const char *search_text;
    int found;
    int match_num;
} search_ctx;

static int contains_ci(const char *haystack, const char *needle) {
    if (!haystack || !needle) return 0;
    size_t nlen = strlen(needle);
    if (nlen == 0) return 0;
    for (const char *p = haystack; *p; p++) {
        if (strncasecmp(p, needle, nlen) == 0) return 1;
    }
    return 0;
}

/* ---- Relationship printers (pass to report) ---- */

typedef struct { int count; } rel_ctx;

static int rel_out_cb(relationship *rel, void *user_data) {
    rel_ctx *ctx = (rel_ctx *)user_data;
    ctx->count++;
    bh_report_rel_outgoing(rel);
    return 0;
}

static int rel_in_cb(relationship *rel, void *user_data) {
    rel_ctx *ctx = (rel_ctx *)user_data;
    ctx->count++;
    bh_report_rel_incoming(rel);
    return 0;
}

/* ---- Search callback ---- */

static int search_cb(scent_packet *pkt, const char *ctx_before, const char *ctx_match,
                     const char *ctx_after, void *user_data) {
    search_ctx *ctx = (search_ctx *)user_data;
    if (contains_ci(pkt->type, ctx->search_text) ||
        contains_ci(pkt->source_file, ctx->search_text) ||
        contains_ci(pkt->workspace, ctx->search_text) ||
        contains_ci(ctx_match, ctx->search_text) ||
        contains_ci(pkt->fingerprint, ctx->search_text)) {

        ctx->found++;
        ctx->match_num++;
        printf("MATCH %d\n", ctx->match_num);
        printf("-----------------------------------\n");
        bh_report_scent(pkt, ctx_before, ctx_match, ctx_after);

        /* Relationships for this match */
        rel_ctx rctx = {0};
        printf("  RELATIONSHIPS\n");
        bh_db_iter_rels_from(ctx->db, pkt->scent_id, rel_out_cb, &rctx);
        bh_db_iter_rels_to(ctx->db, pkt->scent_id, rel_in_cb, &rctx);
        if (rctx.count == 0) printf("  (none)\n");
        printf("\n");
    }
    return 0;
}

/* ---- Query: search by text ---- */

void bh_query_text(bh_db *db, const char *text) {
    bh_report_search_header(text);
    search_ctx ctx = { .db = db, .search_text = text, .found = 0, .match_num = 0 };
    bh_db_iter_scents(db, search_cb, &ctx);
    bh_report_search_footer(ctx.found);
}

/* ---- Remember ---- */

void bh_query_remember(bh_db *db, const char *text) {
    bh_report_memory_header(text);
    search_ctx ctx = { .db = db, .search_text = text, .found = 0, .match_num = 0 };
    bh_db_iter_scents(db, search_cb, &ctx);
    bh_report_memory_footer(ctx.found);
}

/* ---- Similar ---- */

void bh_query_similar(bh_db *db, uint64_t scent_id) {
    scent_packet pkt;
    char ctx_before[BH_MAX_LINE], ctx_match[BH_MAX_LINE], ctx_after[BH_MAX_LINE];
    if (bh_db_get_scent(db, scent_id, &pkt, ctx_before, sizeof(ctx_before),
                        ctx_match, sizeof(ctx_match), ctx_after, sizeof(ctx_after))) {
        bh_report_error("scent not found");
        return;
    }
    bh_report_search_header(pkt.fingerprint);
    search_ctx ctx = { .db = db, .search_text = pkt.fingerprint, .found = 0, .match_num = 0 };
    bh_db_iter_scents(db, search_cb, &ctx);
    /* Same type in same file */
    ctx.search_text = pkt.type;
    ctx.found = 0;
    ctx.match_num = 0;
    bh_db_iter_file_scents(db, pkt.source_file, search_cb, &ctx);
    bh_report_search_footer(ctx.found);
}

/* ---- Relationships ---- */

void bh_query_relationships(bh_db *db, uint64_t scent_id) {
    scent_packet pkt;
    char ctx_before[BH_MAX_LINE], ctx_match[BH_MAX_LINE], ctx_after[BH_MAX_LINE];
    if (bh_db_get_scent(db, scent_id, &pkt, ctx_before, sizeof(ctx_before),
                        ctx_match, sizeof(ctx_match), ctx_after, sizeof(ctx_after))) {
        bh_report_error("scent not found");
        return;
    }
    bh_report_rel_header(scent_id, pkt.type, pkt.source_file, pkt.line);

    rel_ctx out_ctx = {0};
    printf("Outgoing:\n");
    bh_db_iter_rels_from(db, scent_id, rel_out_cb, &out_ctx);
    if (out_ctx.count == 0) printf("  (none)\n");

    rel_ctx in_ctx = {0};
    printf("\nIncoming:\n");
    bh_db_iter_rels_to(db, scent_id, rel_in_cb, &in_ctx);
    if (in_ctx.count == 0) printf("  (none)\n");

    bh_report_rel_footer(out_ctx.count, in_ctx.count);
}

/* ---- Trails ---- */

typedef struct { int count; } trail_ctx;

static int trail_cb(trail *t, void *user_data) {
    trail_ctx *ctx = (trail_ctx *)user_data;
    ctx->count++;
    bh_report_trail(t);
    return 0;
}

void bh_query_trails(bh_db *db) {
    bh_report_trails_header();
    trail_ctx ctx = {0};
    bh_db_iter_trails(db, trail_cb, &ctx);
    bh_report_trails_footer(ctx.count);
}

void bh_query_trail_detail(bh_db *db, uint64_t trail_id) {
    printf("\n");
    printf("TRAIL %llu\n", (unsigned long long)trail_id);
    printf("===================================\n");
    printf("(trail detail not yet implemented)\n\n");
}

/* ---- Workspace ---- */

void bh_query_workspace(bh_db *db, const char *name) {
    workspace_rec ws;
    if (bh_db_get_workspace(db, name, &ws)) {
        bh_report_error("workspace not found");
        return;
    }
    bh_report_workspace(&ws);
}

/* ---- Stats ---- */

void bh_query_stats(bh_db *db) {
    uint64_t scents = 0, files = 0, observations = 0, relationships = 0, trails = 0, workspaces = 0, learning = 0;
    bh_db_count(db, BH_DB_SCENTS, &scents);
    bh_db_count(db, BH_DB_FILES, &files);
    bh_db_count(db, BH_DB_OBSERVATIONS, &observations);
    bh_db_count(db, BH_DB_RELS, &relationships);
    bh_db_count(db, BH_DB_TRAILS, &trails);
    bh_db_count(db, BH_DB_WORKSPACES, &workspaces);
    bh_db_count(db, BH_DB_LEARNING, &learning);
    bh_report_stats(scents, files, observations, relationships, trails, workspaces, learning);
}

/* ---- Recent ---- */

void bh_query_recent(bh_db *db, int limit) {
    printf("\n");
    printf("RECENT OBSERVATIONS (last %d)\n", limit);
    printf("===================================\n");
    printf("(recent observations not yet implemented)\n\n");
}

/* ---- File content ---- */

void bh_query_file_content(bh_db *db, uint64_t file_id) {
    file_record rec;
    char *content = malloc(10 * 1024 * 1024);
    if (!content) { bh_report_error("out of memory"); return; }
    if (bh_db_get_file(db, file_id, &rec, content, 10 * 1024 * 1024)) {
        bh_report_error("file not found");
        free(content);
        return;
    }
    bh_report_file(&rec, content);
    free(content);
}

/* ---- Content Search ---- */

typedef struct {
    bh_db *db;
    const char *needle;
    int limit;
    int found;
} content_search_ctx;

static int content_search_cb(scent_packet *pkt, const char *ctx_before, const char *ctx_match,
                             const char *ctx_after, void *user_data) {
    content_search_ctx *ctx = (content_search_ctx *)user_data;
    if (ctx->found >= ctx->limit) return 1;
    if (contains_ci(ctx_before, ctx->needle) ||
        contains_ci(ctx_match, ctx->needle) ||
        contains_ci(ctx_after, ctx->needle) ||
        contains_ci(pkt->type, ctx->needle) ||
        contains_ci(pkt->source_file, ctx->needle)) {
        ctx->found++;
        bh_report_scent(pkt, ctx_before, ctx_match, ctx_after);
    }
    return 0;
}

void bh_query_content_search(bh_db *db, const char *text, int limit) {
    bh_report_search_header(text);
    content_search_ctx ctx = { .db = db, .needle = text, .limit = limit, .found = 0 };
    bh_db_iter_scents(db, content_search_cb, &ctx);
    bh_report_search_footer(ctx.found);
}

/* ---- Export ---- */

typedef struct { FILE *f; int first; } export_ctx;

static int export_json_cb(scent_packet *pkt, const char *ctx_before, const char *ctx_match,
                          const char *ctx_after, void *user_data) {
    export_ctx *c = (export_ctx *)user_data;
    if (!c->first) fprintf(c->f, ",\n");
    c->first = 0;
    fprintf(c->f, "    {\"id\": %llu, \"type\": \"%s\", \"file\": \"%s\", \"line\": %d, \"confidence\": %.2f}",
            (unsigned long long)pkt->scent_id, pkt->type, pkt->source_file, pkt->line, pkt->confidence);
    return 0;
}

typedef struct { FILE *f; int count; } text_export_ctx;

static int export_text_cb(scent_packet *pkt, const char *ctx_before, const char *ctx_match,
                          const char *ctx_after, void *user_data) {
    text_export_ctx *c = (text_export_ctx *)user_data;
    c->count++;
    fprintf(c->f, "[%d] %s:%d (%s) conf=%.2f\n  %s\n\n",
            c->count, pkt->source_file, pkt->line, pkt->type,
            pkt->confidence, ctx_match ? ctx_match : "");
    return 0;
}

void bh_query_export(bh_db *db, const char *format, const char *output_path) {
    FILE *f = fopen(output_path, "w");
    if (!f) {
        bh_report_error("cannot open output file");
        return;
    }

    if (strcmp(format, "json") == 0) {
        fprintf(f, "{\n  \"scents\": [\n");
        export_ctx ec = { .f = f, .first = 1 };
        bh_db_iter_scents(db, export_json_cb, &ec);
        fprintf(f, "\n  ]\n}\n");
    } else {
        fprintf(f, "Bloodhound Export\n=================\n\n");
        text_export_ctx tc = { .f = f, .count = 0 };
        bh_db_iter_scents(db, export_text_cb, &tc);
        fprintf(f, "\n--- Total: %d scents ---\n", tc.count);
    }

    fclose(f);
    printf("Exported to %s\n", output_path);
}

/* ---- Status ---- */

void bh_print_status(bh_db *db) {
    struct stat st;
    long db_size = 0;
    if (stat(db->db_path, &st) == 0) db_size = st.st_size;
    uint64_t scents = 0, files = 0, observations = 0, relationships = 0, trails = 0, workspaces = 0;
    bh_db_count(db, BH_DB_SCENTS, &scents);
    bh_db_count(db, BH_DB_FILES, &files);
    bh_db_count(db, BH_DB_OBSERVATIONS, &observations);
    bh_db_count(db, BH_DB_RELS, &relationships);
    bh_db_count(db, BH_DB_TRAILS, &trails);
    bh_db_count(db, BH_DB_WORKSPACES, &workspaces);
    bh_report_status(db->db_path, db_size, scents, files, observations, relationships, trails, workspaces);
}
