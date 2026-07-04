/*
 * bh_report.h - Report module: ALL output goes through here
 *[@GHOST]
 *[@VBSTYLE]
 *[@FILEID] bh_report.h
 *[@SUMMARY] One report module for all Bloodhound output. No printf anywhere else.
 *[@CLASS] BloodhoundReport
 *[@METHOD] Scent, Search, Relationships, Trails, Observations, Content, Export, Decay, Watch, Stats, Scan, Sync, Status, Error
 */

#ifndef BH_REPORT_H
#define BH_REPORT_H

#include "bloodhound.h"

/* Single scent evidence report */
void bh_report_scent(scent_packet *pkt, const char *ctx_before, const char *ctx_match, const char *ctx_after);

/* Search results: header + N scent reports */
void bh_report_search_header(const char *query);
void bh_report_search_footer(int count);

/* Memory report (remember command) */
void bh_report_memory_header(const char *query);
void bh_report_memory_footer(int count);

/* Relationship report */
void bh_report_rel_header(uint64_t scent_id, const char *type, const char *file, uint32_t line);
void bh_report_rel_outgoing(relationship *rel);
void bh_report_rel_incoming(relationship *rel);
void bh_report_rel_footer(int outgoing_count, int incoming_count);

/* Trail reports */
void bh_report_trails_header(void);
void bh_report_trail(trail *t);
void bh_report_trails_footer(int count);
void bh_report_trail_detail(trail *t, trail_step *steps, int step_count);

/* Observation report */
void bh_report_observation(observation *obs);

/* Recent observations */
void bh_report_recent_header(int limit);
void bh_report_recent_footer(int count);

/* Content search */
void bh_report_content_search_header(const char *text);
void bh_report_content_match(uint64_t file_id, const char *file_path, uint32_t line, const char *line_text);
void bh_report_content_search_footer(int count);

/* Export progress / done */
void bh_report_export_progress(int scents, int files);
void bh_report_export_done(const char *path, int scents, int files);

/* Decay report */
void bh_report_decay(int count, double factor);

/* Deletions report */
void bh_report_deletions(uint32_t count);

/* Watch mode */
void bh_report_watch_start(const char *path, int interval);
void bh_report_watch_cycle(int cycle, scan_result *result);

/* Workspace report */
void bh_report_workspace(workspace_rec *ws);

/* Stats report */
void bh_report_stats(uint64_t scents, uint64_t files, uint64_t observations,
                     uint64_t relationships, uint64_t trails, uint64_t workspaces, uint64_t learning);

/* Scan result report */
void bh_report_scan(const char *workspace, const char *root, scan_result *result);

/* Sync report */
void bh_report_sync(const char *source, long original, size_t compressed, const char *ts_file, const char *latest_file);

/* Restore report */
void bh_report_restore(const char *source, long compressed, size_t decompressed, const char *dest);

/* Status report */
void bh_report_status(const char *db_path, long db_size, uint64_t scents, uint64_t files,
                      uint64_t observations, uint64_t relationships, uint64_t trails, uint64_t workspaces);

/* File content report */
void bh_report_file(file_record *rec, const char *content);

/* Confidence change report */
void bh_report_confidence(uint64_t scent_id, const char *action, double confidence);

/* Error report */
void bh_report_error(const char *msg);

/* Trail added report */
void bh_report_trail_added(uint64_t trail_id);

/* Usage report */
void bh_report_usage(void);

/* Query functions (declared here for bh_main.c) */
void bh_query_text(bh_db *db, const char *text);
void bh_query_remember(bh_db *db, const char *text);
void bh_query_similar(bh_db *db, uint64_t scent_id);
void bh_query_relationships(bh_db *db, uint64_t scent_id);
void bh_query_trails(bh_db *db);
void bh_query_trail_detail(bh_db *db, uint64_t trail_id);
void bh_query_workspace(bh_db *db, const char *name);
void bh_query_stats(bh_db *db);
void bh_query_recent(bh_db *db, int limit);
void bh_query_file_content(bh_db *db, uint64_t file_id);
void bh_query_content_search(bh_db *db, const char *text, int limit);
void bh_query_export(bh_db *db, const char *format, const char *output_path);
void bh_print_status(bh_db *db);

#endif /* BH_REPORT_H */
