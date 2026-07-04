/*
 * discovery.h — External Discovery Layer for msearch
 *
 * Layer 1: External intelligence (Gemini / web / APIs)
 * Purpose: discovery, exploration, candidate generation
 * Function: "What might be relevant out there?"
 *
 * Architecture:
 *   Layer 1 (this file): External discovery → candidate evidence
 *   Layer 2 (msearch.c):  Internal truth reconstruction → blast radius
 *   Layer 3 (future):     Reasoning model → synthesis + contradiction resolution
 *
 * Sources:
 *   - GitHub API: code search + repository search
 *   - Stack Overflow API: question search + accepted answers
 *   - Google Custom Search: broad web discovery
 *   - Gemini API: synthesis + web-grounded answers
 *   - Reddit API: community interpretation
 *
 * Each source returns evidence packets in the same format:
 *   source, title, url, snippet, relevance
 *
 * Compile with: -lcurl
 */

#ifndef DISCOVERY_H
#define DISCOVERY_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ── Evidence packet structure ── */
typedef struct {
    char source[32];     /* "github", "stackoverflow", "google", "gemini", "reddit" */
    char title[256];
    char url[512];
    char snippet[1024];
    char relevance[16];  /* "high", "medium", "low" */
} evidence_t;

/* ── Configuration ── */
typedef struct {
    char github_token[256];    /* GitHub personal access token (optional, raises rate limit) */
    char gemini_api_key[256];  /* Google Gemini API key */
    char google_api_key[256];  /* Google Custom Search API key */
    char google_cx_id[128];    /* Google Custom Search engine ID */
    int  max_results;          /* Max results per source (default: 5) */
    int  timeout_seconds;      /* HTTP timeout (default: 15) */
} discovery_config_t;

/* ── Public API ── */

/* Initialize discovery config with defaults */
void discovery_config_init(discovery_config_t *cfg);

/* Load API keys from environment variables:
 *   GITHUB_TOKEN, GEMINI_API_KEY, GOOGLE_API_KEY, GOOGLE_CX_ID
 */
void discovery_config_from_env(discovery_config_t *cfg);

/* Search GitHub for code matching keyword.
 * Uses: https://api.github.com/search/code?q=KEYWORD
 * Returns number of evidence packets found (0 on error).
 */
int discovery_github(const char *keyword, discovery_config_t *cfg,
                     evidence_t *results, int max_results);

/* Search Stack Overflow for questions matching keyword.
 * Uses: https://api.stackexchange.com/2.3/search?intitle=KEYWORD&site=stackoverflow
 * Returns number of evidence packets found (0 on error).
 */
int discovery_stackoverflow(const char *keyword, discovery_config_t *cfg,
                            evidence_t *results, int max_results);

/* Search Google Custom Search for keyword.
 * Uses: Google Custom Search JSON API
 * Returns number of evidence packets found (0 on error).
 */
int discovery_google(const char *keyword, discovery_config_t *cfg,
                     evidence_t *results, int max_results);

/* Query Gemini for a synthesis answer about keyword.
 * Uses: Gemini API generateContent endpoint
 * Returns number of evidence packets (usually 1, the answer).
 */
int discovery_gemini(const char *keyword, discovery_config_t *cfg,
                     evidence_t *results, int max_results);

/* Search Reddit for posts matching keyword.
 * Uses: https://www.reddit.com/search.json?q=KEYWORD
 * Returns number of evidence packets found (0 on error).
 */
int discovery_reddit(const char *keyword, discovery_config_t *cfg,
                     evidence_t *results, int max_results);

/* Search DuckDuckGo (FREE, no API key needed).
 * Uses: https://html.duckduckgo.com/html/?q=KEYWORD
 * Parses HTML result titles + snippets.
 * Returns number of evidence packets found (0 on error).
 */
int discovery_duckduckgo(const char *keyword, discovery_config_t *cfg,
                          evidence_t *results, int max_results);

/* Search Wikipedia API (FREE, no API key needed).
 * Uses: https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=KEYWORD&format=json
 * Returns number of evidence packets found (0 on error).
 */
int discovery_wikipedia(const char *keyword, discovery_config_t *cfg,
                         evidence_t *results, int max_results);

/* Run all enabled external sources and print results.
 * This is the main entry point called by msearch --web.
 * Prints evidence packets in the same style as internal dimensions.
 * Returns total number of evidence packets found across all sources.
 */
int discovery_all(const char *keyword, discovery_config_t *cfg);

/* Print a single evidence packet */
void evidence_print(evidence_t *ev);

/* URL-encode a string for use in API queries */
void discovery_url_encode(const char *in, char *out, size_t out_sz);

/* Minimal JSON string extraction: find "key":"value" and copy value to out */
int discovery_json_extract(const char *json, const char *key,
                           char *out, size_t out_sz);

/* Minimal JSON array element count for "key":[...] */
int discovery_json_count(const char *json, const char *key);

/* ════════════════════════════════════════════
 * CANDIDATE COMPRESSION LAYER
 *
 * External layer proposes. Magnetic layer verifies.
 *
 * This layer sits between external discovery and internal
 * magnetic expansion. It takes raw evidence packets from
 * external sources and compresses them into minimal,
 * high-signal entry points.
 *
 * Flow:
 *   External search → raw evidence (20-50 packets)
 *   → compression layer (filter, score, deduplicate, extract)
 *   → 3-7 compressed entry points (keywords)
 *   → magnetic blast-radius expansion per entry point
 *
 * Scoring:
 *   - Term frequency across all evidence
 *   - Source diversity bonus (term in 2+ sources = higher)
 *   - Original keyword match bonus
 *   - Stop word filtering
 *   - Length penalty (too short or too long = noise)
 * ════════════════════════════════════════════ */

#define MAX_ENTRY_POINTS  16
#define MAX_TERM_LEN      64
#define MAX_EVIDENCE_POOL 64

typedef struct {
    char term[MAX_TERM_LEN];
    int  frequency;         /* total occurrences across all evidence */
    int  source_count;      /* number of distinct sources containing this term */
    int  score;             /* composite score: freq + source_diversity*3 + keyword_match*5 */
} entry_point_t;

/* Compress raw evidence packets into high-signal entry points.
 * Takes array of evidence packets, extracts significant terms,
 * scores them, and returns top N entry points.
 *
 * Params:
 *   evidence    — array of evidence packets from external sources
 *   ev_count    — number of evidence packets
 *   keyword     — original search keyword (for match bonus)
 *   out_points  — output array of entry points
 *   max_points  — max entry points to return
 *
 * Returns: number of entry points produced (0 if no evidence)
 */
int discovery_compress(evidence_t *evidence, int ev_count,
                       const char *keyword,
                       entry_point_t *out_points, int max_points);

/* Print entry points in formatted output */
void entry_points_print(entry_point_t *points, int count);

/* Run full external discovery + compression pipeline.
 * This is the main entry point for --web with compression.
 *
 * 1. Query all external sources
 * 2. Collect all evidence into single pool
 * 3. Compress into entry points
 * 4. Print entry points
 *
 * Returns: number of compressed entry points
 */
int discovery_and_compress(const char *keyword, discovery_config_t *cfg);

#endif /* DISCOVERY_H */
