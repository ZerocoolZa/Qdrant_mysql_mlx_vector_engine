/*
 * bh_report.c - Report module: ALL output goes through here
 *[@GHOST]
 *[@VBSTYLE]
 *[@FILEID] bh_report.c
 *[@SUMMARY] One report module for all Bloodhound output. No printf anywhere else.
 *[@CLASS] BloodhoundReport
 *[@METHOD] Scent, Search, Relationships, Trails, Observations, Content, Export, Decay, Watch, Stats, Scan, Sync, Status, Error
 */

#include "bh_report.h"
#include <stdio.h>
#include <string.h>

/* ---- Helpers ---- */

static void print_separator(void) {
    printf("===================================\n");
}

static void print_sub_separator(void) {
    printf("-----------------------------------\n");
}

static void print_context_block(const char *label, const char *text) {
    if (!text || !*text) return;
    printf("    %s:\n", label);
    char buf[BH_MAX_LINE * 3];
    strncpy(buf, text, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = '\0';
    char *line = strtok(buf, "\n");
    while (line) {
        printf("      %s\n", line);
        line = strtok(NULL, "\n");
    }
}

static void print_size(long bytes) {
    if (bytes > 1024 * 1024) printf(" (%.1f MB)", (double)bytes / (1024 * 1024));
    else if (bytes > 1024) printf(" (%.1f KB)", (double)bytes / 1024);
}

/* ---- Single scent evidence report ---- */

void bh_report_scent(scent_packet *pkt, const char *ctx_before, const char *ctx_match, const char *ctx_after) {
    char created_str[32];
    char updated_str[32];
    bh_format_timestamp(pkt->created_at, created_str, sizeof(created_str));
    bh_format_timestamp(pkt->updated_at, updated_str, sizeof(updated_str));

    printf("  Scent ID:    %llu\n", (unsigned long long)pkt->scent_id);
    printf("  Type:        %s\n", pkt->type);
    printf("  Language:    %s\n", pkt->language);
    printf("  Confidence:  %.2f\n", pkt->confidence);
    printf("  Seen:        %u times\n", pkt->seen_count);
    printf("  First seen:  %s\n", created_str);
    printf("  Last seen:   %s\n", updated_str);
    printf("\n");
    printf("  LOCATION\n");
    printf("    Workspace: %s\n", pkt->workspace);
    printf("    File:      %s\n", pkt->source_file);
    printf("    Path:      %s\n", pkt->relative_path);
    printf("    Line:      %u\n", pkt->line);
    printf("    Column:    %u\n", pkt->column);
    printf("\n");
    printf("  EVIDENCE\n");
    print_context_block("Before", ctx_before);
    print_context_block("Match", ctx_match);
    print_context_block("After", ctx_after);
    printf("\n");
}

/* ---- Search ---- */

void bh_report_search_header(const char *query) {
    printf("\n");
    printf("BLOODHOUND QUERY \u2014 \"%s\"\n", query);
    print_separator();
}

void bh_report_search_footer(int count) {
    if (count == 0) printf("No matches found.\n\n");
    else printf("Total matches: %d\n\n", count);
}

/* ---- Memory ---- */

void bh_report_memory_header(const char *query) {
    printf("\n");
    printf("BLOODHOUND MEMORY \u2014 \"%s\"\n", query);
    print_separator();
}

void bh_report_memory_footer(int count) {
    if (count == 0) printf("I've never smelled this before.\n\n");
    else printf("I've smelled this %d time(s).\n\n", count);
}

/* ---- Relationships ---- */

void bh_report_rel_header(uint64_t scent_id, const char *type, const char *file, uint32_t line) {
    printf("\n");
    printf("RELATIONSHIPS \u2014 scent %llu (%s)\n", (unsigned long long)scent_id, type);
    print_separator();
    printf("File: %s:%u\n\n", file, line);
}

void bh_report_rel_outgoing(relationship *rel) {
    printf("  \u2192 %-12s  scent_id=%llu  confidence=%.2f\n",
           rel->rel_type, (unsigned long long)rel->to_scent, rel->confidence);
    if (rel->evidence[0]) printf("    evidence: %s\n", rel->evidence);
}

void bh_report_rel_incoming(relationship *rel) {
    printf("  \u2190 %-12s  from_scent=%llu  confidence=%.2f\n",
           rel->rel_type, (unsigned long long)rel->from_scent, rel->confidence);
}

void bh_report_rel_footer(int outgoing_count, int incoming_count) {
    if (outgoing_count == 0 && incoming_count == 0) printf("  (none)\n");
    printf("\n");
}

/* ---- Trails ---- */

void bh_report_trails_header(void) {
    printf("\n");
    printf("BLOODHOUND TRAILS\n");
    print_separator();
}

void bh_report_trail(trail *t) {
    printf("  Trail %llu: \"%s\"\n", (unsigned long long)t->trail_id, t->origin);
    if (t->destination[0]) printf("    \u2192 %s\n", t->destination);
    if (t->reason[0]) printf("    reason: %s\n", t->reason);
    printf("    confidence: %.2f\n", t->confidence);
    printf("\n");
}

void bh_report_trails_footer(int count) {
    if (count == 0) printf("No trails recorded.\n");
    printf("\nTotal trails: %d\n\n", count);
}

void bh_report_trail_detail(trail *t, trail_step *steps, int step_count) {
    char created_str[32];
    bh_format_timestamp(t->created_at, created_str, sizeof(created_str));

    printf("\n");
    printf("TRAIL %llu\n", (unsigned long long)t->trail_id);
    print_separator();
    printf("Origin:      \"%s\"\n", t->origin);
    printf("Destination: %s\n", t->destination);
    printf("Reason:      %s\n", t->reason);
    printf("Confidence:  %.2f\n", t->confidence);
    printf("Created:     %s\n", created_str);
    printf("\n");

    printf("STEPS (%d)\n", step_count);
    for (int i = 0; i < step_count; i++) {
        printf("  Step %u: %s", steps[i].step_num, steps[i].description);
        if (steps[i].file_path[0]) printf(" \u2192 %s", steps[i].file_path);
        printf("\n");
    }
    printf("\n");
}

/* ---- Observation ---- */

void bh_report_observation(observation *obs) {
    char ts_str[32];
    bh_format_timestamp(obs->timestamp, ts_str, sizeof(ts_str));

    printf("  [%s] %s\n", ts_str, obs->action);
    printf("    workspace: %s\n", obs->workspace);
    printf("    file:      %s\n", obs->file_path);
    printf("    scent_id:  %llu\n", (unsigned long long)obs->scent_id);
}

/* ---- Recent observations ---- */

void bh_report_recent_header(int limit) {
    printf("\n");
    printf("RECENT OBSERVATIONS (last %d)\n", limit);
    print_separator();
}

void bh_report_recent_footer(int count) {
    printf("\n");
    if (count == 0) printf("No observations recorded.\n");
    else printf("Total: %d\n", count);
    printf("\n");
}

/* ---- Content search ---- */

void bh_report_content_search_header(const char *text) {
    printf("\n");
    printf("CONTENT SEARCH \u2014 \"%s\"\n", text);
    print_separator();
}

void bh_report_content_match(uint64_t file_id, const char *file_path, uint32_t line, const char *line_text) {
    printf("  file_id=%-4llu %s:%-4u %s\n",
           (unsigned long long)file_id, file_path, line, line_text);
}

void bh_report_content_search_footer(int count) {
    printf("\n");
    if (count == 0) printf("No matches found.\n");
    else printf("Total matches: %d\n", count);
    printf("\n");
}

/* ---- Export ---- */

void bh_report_export_progress(int scents, int files) {
    printf("\r  Exporting... %d scents, %d files", scents, files);
    fflush(stdout);
}

void bh_report_export_done(const char *path, int scents, int files) {
    printf("\n");
    printf("BLOODHOUND EXPORT\n");
    print_separator();
    printf("Path:         %s\n", path);
    printf("Scents:       %d\n", scents);
    printf("Files:        %d\n", files);
    printf("\n");
}

/* ---- Decay ---- */

void bh_report_decay(int count, double factor) {
    printf("Decayed %d scents by factor %.2f\n\n", count, factor);
}

/* ---- Deletions ---- */

void bh_report_deletions(uint32_t count) {
    printf("Detected %u deleted file(s).\n\n", count);
}

/* ---- Watch mode ---- */

void bh_report_watch_start(const char *path, int interval) {
    printf("\n");
    printf("BLOODHOUND WATCH\n");
    print_separator();
    printf("Path:         %s\n", path);
    printf("Interval:     %d seconds\n", interval);
    printf("\n");
    fflush(stdout);
}

void bh_report_watch_cycle(int cycle, scan_result *result) {
    printf("--- Cycle %d ---\n", cycle);
    printf("  Files:       %u\n", result->files);
    printf("  New:         %u\n", result->new_files);
    printf("  Modified:    %u\n", result->modified_files);
    printf("  Deleted:     %u\n", result->deleted_files);
    printf("  Total scents: %u\n", result->total_scents);
    printf("\n");
    fflush(stdout);
}

/* ---- Workspace ---- */

void bh_report_workspace(workspace_rec *ws) {
    char last_scan_str[32];
    char created_str[32];
    char updated_str[32];
    bh_format_timestamp(ws->last_scan, last_scan_str, sizeof(last_scan_str));
    bh_format_timestamp(ws->created_at, created_str, sizeof(created_str));
    bh_format_timestamp(ws->updated_at, updated_str, sizeof(updated_str));

    printf("\n");
    printf("WORKSPACE \u2014 %s\n", ws->name);
    print_separator();
    printf("Root path:      %s\n", ws->root_path);
    printf("Files:          %u\n", ws->file_count);
    printf("Scents:         %u\n", ws->scent_count);
    printf("Last scan:      %s\n", last_scan_str);
    printf("Created:        %s\n", created_str);
    printf("Updated:        %s\n", updated_str);
    if (ws->dominant_topics[0]) printf("Topics:         %s\n", ws->dominant_topics);
    printf("\n");
}

/* ---- Stats ---- */

void bh_report_stats(uint64_t scents, uint64_t files, uint64_t observations,
                     uint64_t relationships, uint64_t trails, uint64_t workspaces, uint64_t learning) {
    printf("\n");
    printf("BLOODHOUND STATS\n");
    print_separator();
    printf("Scents:        %llu\n", (unsigned long long)scents);
    printf("Files:         %llu\n", (unsigned long long)files);
    printf("Observations:  %llu\n", (unsigned long long)observations);
    printf("Relationships: %llu\n", (unsigned long long)relationships);
    printf("Trails:        %llu\n", (unsigned long long)trails);
    printf("Workspaces:    %llu\n", (unsigned long long)workspaces);
    printf("Learning:      %llu\n", (unsigned long long)learning);
    printf("\n");
}

/* ---- Scan result ---- */

void bh_report_scan(const char *workspace, const char *root, scan_result *result) {
    printf("\n");
    printf("SCAN COMPLETE\n");
    print_separator();
    printf("Workspace:     %s\n", workspace);
    printf("Root:          %s\n", root);
    printf("Files:         %u\n", result->files);
    printf("New files:     %u\n", result->new_files);
    printf("Modified:      %u\n", result->modified_files);
    printf("Deleted:       %u\n", result->deleted_files);
    printf("\n");
}

/* ---- Sync ---- */

void bh_report_sync(const char *source, long original, size_t compressed, const char *ts_file, const char *latest_file) {
    printf("\n");
    printf("BLOODHOUND SYNC\n");
    print_separator();
    printf("Source:        %s\n", source);
    printf("Original:      %ld bytes", original);
    print_size(original);
    printf("\n");
    printf("Compressed:    %zu bytes", compressed);
    print_size((long)compressed);
    printf("\n");
    if (original > 0) printf("Ratio:         %.1f%%\n", (double)compressed / original * 100);
    printf("Drive path:    %s\n", ts_file);
    printf("Latest:        %s\n", latest_file);
    printf("\n");
}

/* ---- Restore ---- */

void bh_report_restore(const char *source, long compressed, size_t decompressed, const char *dest) {
    printf("\n");
    printf("BLOODHOUND RESTORE\n");
    print_separator();
    printf("Source:        %s\n", source);
    printf("Compressed:    %ld bytes\n", compressed);
    printf("Decompressed:  %zu bytes\n", decompressed);
    printf("Restored to:   %s\n", dest);
    printf("\n");
}

/* ---- Status ---- */

void bh_report_status(const char *db_path, long db_size, uint64_t scents, uint64_t files,
                      uint64_t observations, uint64_t relationships, uint64_t trails, uint64_t workspaces) {
    printf("\n");
    printf("BLOODHOUND STATUS\n");
    print_separator();
    printf("DB path:       %s\n", db_path);
    printf("DB size:       %ld bytes", db_size);
    print_size(db_size);
    printf("\n");
    printf("Scents:        %llu\n", (unsigned long long)scents);
    printf("Files:         %llu\n", (unsigned long long)files);
    printf("Observations:  %llu\n", (unsigned long long)observations);
    printf("Relationships: %llu\n", (unsigned long long)relationships);
    printf("Trails:        %llu\n", (unsigned long long)trails);
    printf("Workspaces:    %llu\n", (unsigned long long)workspaces);
    printf("\n");
}

/* ---- File content ---- */

void bh_report_file(file_record *rec, const char *content) {
    char scan_time_str[32];
    bh_format_timestamp(rec->scan_time, scan_time_str, sizeof(scan_time_str));

    printf("\n");
    printf("FILE CONTENT \u2014 file %llu\n", (unsigned long long)rec->file_id);
    print_separator();
    printf("Path:          %s\n", rec->file_path);
    printf("Relative:      %s\n", rec->relative_path);
    printf("Workspace:     %s\n", rec->workspace);
    printf("Language:      %s\n", rec->language);
    printf("Original size: %llu bytes\n", (unsigned long long)rec->size);
    printf("Compressed:    %u bytes\n", rec->compressed_size);
    printf("Hash:          %s\n", rec->content_hash);
    printf("Scan time:     %s\n", scan_time_str);
    printf("\n");
    printf("---- CONTENT ----\n");
    printf("%s\n", content);
    printf("---- END ----\n\n");
}

/* ---- Confidence change ---- */

void bh_report_confidence(uint64_t scent_id, const char *action, double confidence) {
    printf("Scent %llu %s. Confidence: %.2f\n\n", (unsigned long long)scent_id, action, confidence);
}

/* ---- Error ---- */

void bh_report_error(const char *msg) {
    fprintf(stderr, "ERROR: %s\n", msg);
}

/* ---- Trail added ---- */

void bh_report_trail_added(uint64_t trail_id) {
    printf("Trail %llu added.\n\n", (unsigned long long)trail_id);
}

/* ---- Usage ---- */

void bh_report_usage(void) {
    printf("Bloodhound v1.0 - Persistent Perception Engine\n\n");
    printf("Usage: bloodhound <command> [args]\n\n");
    printf("Commands:\n");
    printf("  scan <workspace_path> [name]   Scan a workspace, extract scents, store compressed\n");
    printf("  watch <workspace_path> [name]  Watch a workspace for changes (live mode)\n");
    printf("  query <text>                   Search scents by text (full report)\n");
    printf("  remember <text>                Full memory report for a scent\n");
    printf("  query-similar <scent_id>       Find similar scents\n");
    printf("  query-rel <scent_id>           Get relationships for a scent\n");
    printf("  query-trails                   List all trails\n");
    printf("  query-trail <trail_id>         Get trail details with steps\n");
    printf("  query-workspace [name]         Get workspace summary\n");
    printf("  query-stats                    Get overall statistics\n");
    printf("  query-recent [N]               Get N most recent observations\n");
    printf("  query-file <file_id>           Get decompressed file content\n");
    printf("  search <text> [limit]          Full-text content search across files\n");
    printf("  export <format> <output_path>  Export scents/files (json/csv)\n");
    printf("  sync [workspace]               Compress + sync DB to Google Drive\n");
    printf("  restore [drive_path]           Restore DB from Google Drive\n");
    printf("  status                         Show DB status, file count, scent count\n");
    printf("  add-trail <origin> <dest> [reason]  Manually add a trail\n");
    printf("  confirm <scent_id>             Increase confidence (AI confirmed)\n");
    printf("  ignore <scent_id>              Decrease confidence (AI ignored)\n");
    printf("  forget <scent_id>              Set confidence to 0 (don't delete)\n");
    printf("  decay [factor]                 Decay all confidence (default 0.95)\n");
    printf("  detect-deletions [workspace]    Detect deleted files in a workspace\n");
    printf("\n");
}
