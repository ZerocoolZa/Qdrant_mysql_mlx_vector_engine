/*
 * bh_main.c - CLI entry point: dispatch commands, call report module
 *[@GHOST]
 *[@VBSTYLE]
 *[@FILEID] bh_main.c
 *[@SUMMARY] Command dispatch: scan, query, remember, sync, status, watch, content-search, export, decay. All output via bh_report.
 *[@CLASS] BloodhoundCLI
 *[@METHOD] Main, Dispatch
 */

#include "bh_report.h"

int main(int argc, char *argv[]) {
    if (argc < 2) {
        bh_report_usage();
        return 1;
    }

    const char *cmd = argv[1];

    if (strcmp(cmd, "help") == 0 || strcmp(cmd, "--help") == 0 || strcmp(cmd, "-h") == 0) {
        bh_report_usage();
        return 0;
    }

    /* Open DB */
    bh_db db;
    char db_path[BH_MAX_PATH];
    bh_expand_tilde("~/.bloodhound/bloodhound.mdb", db_path, sizeof(db_path));

    if (bh_db_open(&db, db_path) != 0) {
        bh_report_error("cannot open DB");
        return 1;
    }

    int rc = 0;

    if (strcmp(cmd, "scan") == 0) {
        if (argc < 3) { bh_report_error("usage: bloodhound scan <path> [name]"); rc = 1; }
        else {
            const char *ws_name = (argc >= 4) ? argv[3] : NULL;
            scan_result result;
            bh_scan_workspace(&db, argv[2], ws_name, &result);
            bh_report_scan(ws_name ? ws_name : argv[2], argv[2], &result);
        }
    }
    else if (strcmp(cmd, "watch") == 0) {
        if (argc < 3) { bh_report_error("usage: bloodhound watch <workspace_path> [name] [interval]"); rc = 1; }
        else {
            const char *ws_name = (argc >= 4) ? argv[3] : NULL;
            int interval = (argc >= 5) ? atoi(argv[4]) : BH_WATCH_INTERVAL;
            bh_watch_workspace(&db, argv[2], ws_name, interval);
        }
    }
    else if (strcmp(cmd, "query") == 0) {
        if (argc < 3) { bh_report_error("usage: bloodhound query <text>"); rc = 1; }
        else bh_query_text(&db, argv[2]);
    }
    else if (strcmp(cmd, "remember") == 0) {
        if (argc < 3) { bh_report_error("usage: bloodhound remember <text>"); rc = 1; }
        else bh_query_remember(&db, argv[2]);
    }
    else if (strcmp(cmd, "query-similar") == 0) {
        if (argc < 3) { bh_report_error("usage: bloodhound query-similar <scent_id>"); rc = 1; }
        else bh_query_similar(&db, strtoull(argv[2], NULL, 10));
    }
    else if (strcmp(cmd, "query-rel") == 0) {
        if (argc < 3) { bh_report_error("usage: bloodhound query-rel <scent_id>"); rc = 1; }
        else bh_query_relationships(&db, strtoull(argv[2], NULL, 10));
    }
    else if (strcmp(cmd, "query-trails") == 0) {
        bh_query_trails(&db);
    }
    else if (strcmp(cmd, "query-trail") == 0) {
        if (argc < 3) { bh_report_error("usage: bloodhound query-trail <trail_id>"); rc = 1; }
        else bh_query_trail_detail(&db, strtoull(argv[2], NULL, 10));
    }
    else if (strcmp(cmd, "query-workspace") == 0) {
        const char *name = (argc >= 3) ? argv[2] : "default";
        bh_query_workspace(&db, name);
    }
    else if (strcmp(cmd, "query-stats") == 0) {
        bh_query_stats(&db);
    }
    else if (strcmp(cmd, "query-recent") == 0) {
        int limit = (argc >= 3) ? atoi(argv[2]) : 10;
        bh_query_recent(&db, limit);
    }
    else if (strcmp(cmd, "query-file") == 0) {
        if (argc < 3) { bh_report_error("usage: bloodhound query-file <file_id>"); rc = 1; }
        else bh_query_file_content(&db, strtoull(argv[2], NULL, 10));
    }
    else if (strcmp(cmd, "content-search") == 0) {
        if (argc < 3) { bh_report_error("usage: bloodhound content-search <text> [limit]"); rc = 1; }
        else {
            int limit = (argc >= 4) ? atoi(argv[3]) : 50;
            bh_query_content_search(&db, argv[2], limit);
        }
    }
    else if (strcmp(cmd, "export") == 0) {
        if (argc < 4) { bh_report_error("usage: bloodhound export <format> <output_path>"); rc = 1; }
        else {
            const char *format = argv[2];
            const char *output_path = argv[3];
            if (strcmp(format, "text") != 0 && strcmp(format, "json") != 0) {
                bh_report_error("format must be 'text' or 'json'");
                rc = 1;
            } else {
                bh_query_export(&db, format, output_path);
            }
        }
    }
    else if (strcmp(cmd, "sync") == 0) {
        const char *ws = (argc >= 3) ? argv[2] : NULL;
        rc = bh_sync_to_drive(&db, ws);
    }
    else if (strcmp(cmd, "restore") == 0) {
        const char *path = (argc >= 3) ? argv[2] : NULL;
        rc = bh_restore_from_drive(path);
    }
    else if (strcmp(cmd, "status") == 0) {
        bh_print_status(&db);
    }
    else if (strcmp(cmd, "add-trail") == 0) {
        if (argc < 4) { bh_report_error("usage: bloodhound add-trail <origin> <dest> [reason]"); rc = 1; }
        else {
            trail t;
            memset(&t, 0, sizeof(t));
            t.trail_id = bh_db_next_id(&db, "next_trail_id");
            strncpy(t.origin, argv[2], 255);
            strncpy(t.destination, argv[3], 255);
            if (argc >= 5) strncpy(t.reason, argv[4], 255);
            t.confidence = 0.5;
            t.created_at = time(NULL);
            bh_db_put_trail(&db, &t);
            bh_report_trail_added(t.trail_id);
        }
    }
    else if (strcmp(cmd, "confirm") == 0) {
        if (argc < 3) { bh_report_error("usage: bloodhound confirm <scent_id>"); rc = 1; }
        else {
            uint64_t sid = strtoull(argv[2], NULL, 10);
            scent_packet pkt;
            char ctx_b[BH_MAX_LINE], ctx_m[BH_MAX_LINE], ctx_a[BH_MAX_LINE];
            if (bh_db_get_scent(&db, sid, &pkt, ctx_b, sizeof(ctx_b), ctx_m, sizeof(ctx_m), ctx_a, sizeof(ctx_a)) == 0) {
                pkt.confidence += 0.1;
                if (pkt.confidence > 0.99) pkt.confidence = 0.99;
                pkt.seen_count++;
                pkt.updated_at = time(NULL);
                bh_db_put_scent(&db, &pkt, ctx_b, ctx_m, ctx_a);
                bh_report_confidence(sid, "confirmed", pkt.confidence);
            } else {
                bh_report_error("scent not found");
                rc = 1;
            }
        }
    }
    else if (strcmp(cmd, "ignore") == 0) {
        if (argc < 3) { bh_report_error("usage: bloodhound ignore <scent_id>"); rc = 1; }
        else {
            uint64_t sid = strtoull(argv[2], NULL, 10);
            scent_packet pkt;
            char ctx_b[BH_MAX_LINE], ctx_m[BH_MAX_LINE], ctx_a[BH_MAX_LINE];
            if (bh_db_get_scent(&db, sid, &pkt, ctx_b, sizeof(ctx_b), ctx_m, sizeof(ctx_m), ctx_a, sizeof(ctx_a)) == 0) {
                pkt.confidence -= 0.1;
                if (pkt.confidence < 0.0) pkt.confidence = 0.0;
                pkt.updated_at = time(NULL);
                bh_db_put_scent(&db, &pkt, ctx_b, ctx_m, ctx_a);
                bh_report_confidence(sid, "ignored", pkt.confidence);
            } else {
                bh_report_error("scent not found");
                rc = 1;
            }
        }
    }
    else if (strcmp(cmd, "forget") == 0) {
        if (argc < 3) { bh_report_error("usage: bloodhound forget <scent_id>"); rc = 1; }
        else {
            uint64_t sid = strtoull(argv[2], NULL, 10);
            scent_packet pkt;
            char ctx_b[BH_MAX_LINE], ctx_m[BH_MAX_LINE], ctx_a[BH_MAX_LINE];
            if (bh_db_get_scent(&db, sid, &pkt, ctx_b, sizeof(ctx_b), ctx_m, sizeof(ctx_m), ctx_a, sizeof(ctx_a)) == 0) {
                pkt.confidence = 0.0;
                pkt.updated_at = time(NULL);
                bh_db_put_scent(&db, &pkt, ctx_b, ctx_m, ctx_a);
                bh_report_confidence(sid, "forgotten", 0.0);
            } else {
                bh_report_error("scent not found");
                rc = 1;
            }
        }
    }
    else if (strcmp(cmd, "decay") == 0) {
        double factor = (argc >= 3) ? atof(argv[2]) : 0.95;
        int decayed = bh_db_decay_all(&db, factor);
        bh_report_decay(decayed, factor);
    }
    else {
        bh_report_error("unknown command");
        bh_report_usage();
        rc = 1;
    }

    bh_db_close(&db);
    return rc;
}
