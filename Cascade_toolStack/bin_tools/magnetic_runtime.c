/* Magnetic Runtime Unified Implementation */
#include "magnetic_runtime_unified.h"
#include <ctype.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define VB_MAX_TEXT 4096
#define VB_MAX_ITEMS 128
#define VB_MAX_TOKEN 128

/* ===== COMMON HELPERS ===== */
static void vb_copy_text(char *dest, size_t size, const char *src) {
    if (!dest || size == 0) return;
    if (!src) { dest[0] = '\0'; return; }
    snprintf(dest, size, "%s", src);
}

static void vb_trim_in_place(char *text) {
    char *start;
    size_t length;
    if (!text) return;
    start = text;
    while (*start && isspace((unsigned char)*start)) start++;
    if (start != text) memmove(text, start, strlen(start) + 1);
    length = strlen(text);
    while (length > 0 && isspace((unsigned char)text[length - 1])) {
        text[length - 1] = '\0';
        length--;
    }
}

static int vb_split_csv(const char *csv, char items[][VB_MAX_TOKEN], int max_items) {
    char buffer[VB_MAX_TEXT];
    char *token;
    char *cursor;
    int count = 0;
    if (!csv || !*csv || max_items <= 0) return 0;
    vb_copy_text(buffer, sizeof(buffer), csv);
    cursor = buffer;
    while ((token = strsep(&cursor, ",")) != NULL && count < max_items) {
        vb_copy_text(items[count], VB_MAX_TOKEN, token);
        vb_trim_in_place(items[count]);
        if (items[count][0]) count++;
    }
    return count;
}

static int vb_contains_csv_item(const char *csv, const char *needle) {
    char items[VB_MAX_ITEMS][VB_MAX_TOKEN];
    int count;
    int i;
    if (!needle || !*needle) return 0;
    count = vb_split_csv(csv, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (strcmp(items[i], needle) == 0) return 1;
    return 0;
}

static int vb_count_shared_csv(const char *left, const char *right) {
    char items[VB_MAX_ITEMS][VB_MAX_TOKEN];
    int count;
    int i;
    int shared = 0;
    count = vb_split_csv(left, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (vb_contains_csv_item(right, items[i])) shared++;
    return shared;
}

static int vb_count_csv(const char *csv) {
    char items[VB_MAX_ITEMS][VB_MAX_TOKEN];
    return vb_split_csv(csv, items, VB_MAX_ITEMS);
}

static void vb_extract_value(const char *payload, const char *key, char *dest, size_t size) {
    char pattern[128];
    const char *start;
    const char *end;
    size_t length;
    if (!dest || size == 0) return;
    dest[0] = '\0';
    if (!payload || !key) return;
    snprintf(pattern, sizeof(pattern), "%s=", key);
    start = strstr(payload, pattern);
    if (!start) return;
    start += strlen(pattern);
    end = strchr(start, ';');
    if (!end) end = payload + strlen(payload);
    length = (size_t)(end - start);
    if (length >= size) length = size - 1;
    memcpy(dest, start, length);
    dest[length] = '\0';
    vb_trim_in_place(dest);
}

static double vb_extract_double(const char *payload, const char *key, double fallback) {
    char value[128];
    vb_extract_value(payload, key, value, sizeof(value));
    return value[0] ? atof(value) : fallback;
}

static int vb_extract_int(const char *payload, const char *key, int fallback) {
    char value[128];
    vb_extract_value(payload, key, value, sizeof(value));
    return value[0] ? atoi(value) : fallback;
}

/* ===== Core_MagneticSearch_v1.c ===== */
    if (!dest || size == 0) return;
    if (!src) { dest[0] = '\0'; return; }
    snprintf(dest, size, "%s", src);
}
    if (!text) return;
    start = text;
    while (*start && isspace((unsigned char)*start)) start++;
    if (start != text) memmove(text, start, strlen(start) + 1);
    length = strlen(text);
    while (length > 0 && isspace((unsigned char)text[length - 1])) {
        text[length - 1] = '\0';
    }
}
static int vb_split_csv(const char *csv, char items[][VB_MAX_TOKEN], int max_items) {
    int count = 0;
    if (!csv || !*csv || max_items <= 0) return 0;
    cursor = buffer;
    while ((token = strsep(&cursor, ",")) != NULL && count < max_items) {
        if (items[count][0]) count++;
    }
    return count;
}
static int vb_contains_csv_item(const char *csv, const char *needle) {
    if (!needle || !*needle) return 0;
    count = vb_split_csv(csv, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (strcmp(items[i], needle) == 0) return 1;
    return 0;
}
static int vb_count_shared_csv(const char *left, const char *right) {
    int shared = 0;
    count = vb_split_csv(left, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (vb_contains_csv_item(right, items[i])) shared++;
    return shared;
}
static int vb_count_csv(const char *csv) {
    return vb_split_csv(csv, items, VB_MAX_ITEMS);
}
    if (!dest || size == 0) return;
    dest[0] = '\0';
    if (!payload || !key) return;
    snprintf(pattern, sizeof(pattern), "%s=", key);
    start = strstr(payload, pattern);
    if (!start) return;
    start += strlen(pattern);
    end = strchr(start, ';');
    if (!end) end = payload + strlen(payload);
    length = (size_t)(end - start);
    if (length >= size) length = size - 1;
    memcpy(dest, start, length);
    dest[length] = '\0';
}
static double vb_extract_double(const char *payload, const char *key, double fallback) {
    return value[0] ? atof(value) : fallback;
}
static int vb_extract_int(const char *payload, const char *key, int fallback) {
    return value[0] ? atoi(value) : fallback;
}
typedef struct Core_MagneticSearch_v1_Result {
static void MGS_setup_result(Core_MagneticSearch_v1_Result *result, const char *emitter, const char *inputs, const char *outputs, const char *errors, const char *logs, const char *meta) {
    if (!result) return;
    result->emitter = emitter;
    result->inputs = inputs;
    result->outputs = outputs;
    result->errors = errors;
    result->logs = logs;
    result->meta = meta;
}
static const char *Core_MagneticSearch_v1_declaration(void) {
    return "id=Core_MagneticSearch_v1;function=search;domain=MAGNETIC_SEARCH;";
}
static char MGS_history_rows[VB_MAX_ITEMS][VB_MAX_TEXT]; static int MGS_history_count = 0;
static const char *MGS_canonical(const char *query) { if (!query) return ""; if (strcmp(query, "ram unit") == 0) return "Core_RamUnit"; if (strcmp(query, "memory db") == 0) return "MemDB"; if (strcmp(query, "memory bus") == 0) return "MemoryBus"; if (strcmp(query, "gui bus") == 0) return "Core_GuiBus"; return query; }
static int MGS_initialize(const char *payload, Core_MagneticSearch_v1_Result *result) { MGS_setup_result(result, "Core_MagneticSearch_v1", payload ? payload : "", "{\"initialized\":true,\"canonical_defaults\":4,\"relation_defaults\":2}", "{}", "search authority initialized", "{\"action\":\"initialize\"}"); return 1; }
static int MGS_search(const char *payload, Core_MagneticSearch_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char query[VB_MAX_TOKEN]; const char *canonical; const char *why_found; const char *authority; double score; vb_extract_value(payload, "query", query, sizeof(query)); canonical = MGS_canonical(query); why_found = strcmp(query, canonical) == 0 ? "exact_term_match" : "canonical_alias_match"; authority = strcmp(query, canonical) == 0 ? "CODE" : "GLOSSARY"; score = strcmp(query, canonical) == 0 ? 0.55 : 0.70; snprintf(outputs, sizeof(outputs), "{\"query\":\"%s\",\"canonical\":\"%s\",\"results\":[{\"term\":\"%s\",\"why_found\":\"%s\",\"authority\":\"%s\",\"score\":%.2f}],\"top_term\":\"%s\",\"top_score\":%.2f}", query, canonical, canonical, why_found, authority, score, canonical, score); if (MGS_history_count < VB_MAX_ITEMS) snprintf(MGS_history_rows[MGS_history_count++], VB_MAX_TEXT, "%s=>%s", query, canonical); MGS_setup_result(result, "Core_MagneticSearch_v1", payload ? payload : "", outputs, "{}", "magnetic search executed", "{\"action\":\"search\"}"); return 1; }
static int MGS_recurse(const char *payload, Core_MagneticSearch_v1_Result *result) { return MGS_search(payload, result); }
static int MGS_history(const char *payload, Core_MagneticSearch_v1_Result *result) { static char outputs[VB_MAX_TEXT]; int i; (void)payload; snprintf(outputs, sizeof(outputs), "{\"history\":["); for (i = 0; i < MGS_history_count; ++i) { char part[256]; snprintf(part, sizeof(part), "%s\"%s\"", i == 0 ? "" : ",", MGS_history_rows[i]); strcat(outputs, part); } strcat(outputs, "]}"); MGS_setup_result(result, "Core_MagneticSearch_v1", payload ? payload : "", outputs, "{}", "search history emitted", "{\"action\":\"history\"}"); return 1; }
static int MGS_publish_event(const char *payload, Core_MagneticSearch_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char event_name[VB_MAX_TOKEN]; vb_extract_value(payload, "event_name", event_name, sizeof(event_name)); snprintf(outputs, sizeof(outputs), "{\"published\":\"%s\"}", event_name[0] ? event_name : "magnetic_search"); MGS_setup_result(result, "Core_MagneticSearch_v1", payload ? payload : "", outputs, "{}", "event packet prepared", "{\"action\":\"publish_event\"}"); return 1; }

/* ===== Lib_ConvergenceRunEngine_v1.c ===== */
    if (!dest || size == 0) return;
    if (!src) { dest[0] = '\0'; return; }
    snprintf(dest, size, "%s", src);
}
    if (!text) return;
    start = text;
    while (*start && isspace((unsigned char)*start)) start++;
    if (start != text) memmove(text, start, strlen(start) + 1);
    length = strlen(text);
    while (length > 0 && isspace((unsigned char)text[length - 1])) {
        text[length - 1] = '\0';
    }
}
static int vb_split_csv(const char *csv, char items[][VB_MAX_TOKEN], int max_items) {
    int count = 0;
    if (!csv || !*csv || max_items <= 0) return 0;
    cursor = buffer;
    while ((token = strsep(&cursor, ",")) != NULL && count < max_items) {
        if (items[count][0]) count++;
    }
    return count;
}
static int vb_contains_csv_item(const char *csv, const char *needle) {
    if (!needle || !*needle) return 0;
    count = vb_split_csv(csv, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (strcmp(items[i], needle) == 0) return 1;
    return 0;
}
static int vb_count_shared_csv(const char *left, const char *right) {
    int shared = 0;
    count = vb_split_csv(left, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (vb_contains_csv_item(right, items[i])) shared++;
    return shared;
}
static int vb_count_csv(const char *csv) {
    return vb_split_csv(csv, items, VB_MAX_ITEMS);
}
    if (!dest || size == 0) return;
    dest[0] = '\0';
    if (!payload || !key) return;
    snprintf(pattern, sizeof(pattern), "%s=", key);
    start = strstr(payload, pattern);
    if (!start) return;
    start += strlen(pattern);
    end = strchr(start, ';');
    if (!end) end = payload + strlen(payload);
    length = (size_t)(end - start);
    if (length >= size) length = size - 1;
    memcpy(dest, start, length);
    dest[length] = '\0';
}
static double vb_extract_double(const char *payload, const char *key, double fallback) {
    return value[0] ? atof(value) : fallback;
}
static int vb_extract_int(const char *payload, const char *key, int fallback) {
    return value[0] ? atoi(value) : fallback;
}
typedef struct Lib_ConvergenceRunEngine_v1_Result {
static void MRN_setup_result(Lib_ConvergenceRunEngine_v1_Result *result, const char *emitter, const char *inputs, const char *outputs, const char *errors, const char *logs, const char *meta) {
    if (!result) return;
    result->emitter = emitter;
    result->inputs = inputs;
    result->outputs = outputs;
    result->errors = errors;
    result->logs = logs;
    result->meta = meta;
}
static const char *Lib_ConvergenceRunEngine_v1_declaration(void) {
    return "id=Lib_ConvergenceRunEngine_v1;domain=MAGNETIC_RUN;";
}
static int MRN_run_iteration(const char *payload, Lib_ConvergenceRunEngine_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char fields[VB_MAX_TEXT]; double pass_count = vb_extract_double(payload, "pass_count", 0.0); double fail_count = vb_extract_double(payload, "fail_count", 0.0); double bias = (pass_count + 1.0) / (pass_count + fail_count + 1.0); vb_extract_value(payload, "fields", fields, sizeof(fields)); snprintf(outputs, sizeof(outputs), "{\"iteration\":1,\"fields\":\"%s\",\"replay_bias\":%.3f,\"state\":\"staged\"}", fields, bias); MRN_setup_result(result, "Lib_ConvergenceRunEngine_v1", payload ? payload : "", outputs, "{}", "iteration executed", "{\"action\":\"run_iteration\"}"); return 1; }
static int MRN_apply_actions(const char *payload, Lib_ConvergenceRunEngine_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char actions[VB_MAX_TEXT]; vb_extract_value(payload, "actions", actions, sizeof(actions)); snprintf(outputs, sizeof(outputs), "{\"applied_actions\":\"%s\"}", actions); MRN_setup_result(result, "Lib_ConvergenceRunEngine_v1", payload ? payload : "", outputs, "{}", "actions applied", "{\"action\":\"apply_actions\"}"); return 1; }
static int MRN_assess_state(const char *payload, Lib_ConvergenceRunEngine_v1_Result *result) { static char outputs[VB_MAX_TEXT]; double fit = vb_extract_double(payload, "fit", 0.0); snprintf(outputs, sizeof(outputs), "{\"state\":\"%s\",\"fit\":%.3f}", fit >= 0.70 ? "admitted" : "partial", fit); MRN_setup_result(result, "Lib_ConvergenceRunEngine_v1", payload ? payload : "", outputs, "{}", "state assessed", "{\"action\":\"assess_state\"}"); return 1; }
static int MRN_trend_log(const char *payload, Lib_ConvergenceRunEngine_v1_Result *result) { static char outputs[VB_MAX_TEXT]; double previous = vb_extract_double(payload, "previous_fit", 0.0); double current = vb_extract_double(payload, "current_fit", 0.0); snprintf(outputs, sizeof(outputs), "{\"trend\":\"%s\",\"delta\":%.3f}", current >= previous ? "up" : "down", current - previous); MRN_setup_result(result, "Lib_ConvergenceRunEngine_v1", payload ? payload : "", outputs, "{}", "trend logged", "{\"action\":\"trend_log\"}"); return 1; }

/* ===== Lib_ConvergenceScoreEngine_v1.c ===== */
    if (!dest || size == 0) return;
    if (!src) { dest[0] = '\0'; return; }
    snprintf(dest, size, "%s", src);
}
    if (!text) return;
    start = text;
    while (*start && isspace((unsigned char)*start)) start++;
    if (start != text) memmove(text, start, strlen(start) + 1);
    length = strlen(text);
    while (length > 0 && isspace((unsigned char)text[length - 1])) {
        text[length - 1] = '\0';
    }
}
static int vb_split_csv(const char *csv, char items[][VB_MAX_TOKEN], int max_items) {
    int count = 0;
    if (!csv || !*csv || max_items <= 0) return 0;
    cursor = buffer;
    while ((token = strsep(&cursor, ",")) != NULL && count < max_items) {
        if (items[count][0]) count++;
    }
    return count;
}
static int vb_contains_csv_item(const char *csv, const char *needle) {
    if (!needle || !*needle) return 0;
    count = vb_split_csv(csv, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (strcmp(items[i], needle) == 0) return 1;
    return 0;
}
static int vb_count_shared_csv(const char *left, const char *right) {
    int shared = 0;
    count = vb_split_csv(left, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (vb_contains_csv_item(right, items[i])) shared++;
    return shared;
}
static int vb_count_csv(const char *csv) {
    return vb_split_csv(csv, items, VB_MAX_ITEMS);
}
    if (!dest || size == 0) return;
    dest[0] = '\0';
    if (!payload || !key) return;
    snprintf(pattern, sizeof(pattern), "%s=", key);
    start = strstr(payload, pattern);
    if (!start) return;
    start += strlen(pattern);
    end = strchr(start, ';');
    if (!end) end = payload + strlen(payload);
    length = (size_t)(end - start);
    if (length >= size) length = size - 1;
    memcpy(dest, start, length);
    dest[length] = '\0';
}
static double vb_extract_double(const char *payload, const char *key, double fallback) {
    return value[0] ? atof(value) : fallback;
}
static int vb_extract_int(const char *payload, const char *key, int fallback) {
    return value[0] ? atoi(value) : fallback;
}
typedef struct Lib_ConvergenceScoreEngine_v1_Result {
static void MCS_setup_result(Lib_ConvergenceScoreEngine_v1_Result *result, const char *emitter, const char *inputs, const char *outputs, const char *errors, const char *logs, const char *meta) {
    if (!result) return;
    result->emitter = emitter;
    result->inputs = inputs;
    result->outputs = outputs;
    result->errors = errors;
    result->logs = logs;
    result->meta = meta;
}
static const char *Lib_ConvergenceScoreEngine_v1_declaration(void) {
    return "id=Lib_ConvergenceScoreEngine_v1;domain=MAGNETIC_SCORE;";
}
static double MCS_overlap(const char *left, const char *right) { int total = vb_count_csv(left); int shared = vb_count_shared_csv(left, right); return total > 0 ? (double)shared / (double)total : 0.0; }
static int MCS_compare_fields(const char *payload, Lib_ConvergenceScoreEngine_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char begin[VB_MAX_TEXT]; char end[VB_MAX_TEXT]; double overlap; vb_extract_value(payload, "begin_fields", begin, sizeof(begin)); vb_extract_value(payload, "end_fields", end, sizeof(end)); overlap = MCS_overlap(begin, end); snprintf(outputs, sizeof(outputs), "{\"overlap\":%.3f,\"shared\":%d}", overlap, vb_count_shared_csv(begin, end)); MCS_setup_result(result, "Lib_ConvergenceScoreEngine_v1", payload ? payload : "", outputs, "{}", "field overlap computed", "{\"action\":\"compare_fields\"}"); return 1; }
static int MCS_projected_variance(const char *payload, Lib_ConvergenceScoreEngine_v1_Result *result) { static char outputs[VB_MAX_TEXT]; double alpha = vb_extract_double(payload, "alpha", 0.4); double beta = vb_extract_double(payload, "beta", 0.3); double gamma = vb_extract_double(payload, "gamma", 0.2); double delta = vb_extract_double(payload, "delta", 0.1); double variance = fabs(alpha - beta) + fabs(gamma - delta); snprintf(outputs, sizeof(outputs), "{\"projected_variance\":%.3f}", variance); MCS_setup_result(result, "Lib_ConvergenceScoreEngine_v1", payload ? payload : "", outputs, "{}", "variance projected", "{\"action\":\"projected_variance\"}"); return 1; }
static int MCS_contradiction_score(const char *payload, Lib_ConvergenceScoreEngine_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char contradictions[VB_MAX_TEXT]; int count; vb_extract_value(payload, "contradictions", contradictions, sizeof(contradictions)); count = vb_count_csv(contradictions); snprintf(outputs, sizeof(outputs), "{\"contradiction_score\":%.3f}", count > 0 ? 1.0 / (double)(count + 1) : 1.0); MCS_setup_result(result, "Lib_ConvergenceScoreEngine_v1", payload ? payload : "", outputs, "{}", "contradiction score computed", "{\"action\":\"contradiction_score\"}"); return 1; }
static int MCS_total_fit(const char *payload, Lib_ConvergenceScoreEngine_v1_Result *result) { static char outputs[VB_MAX_TEXT]; double overlap = MCS_overlap(strstr(payload ? payload : "", "begin_fields=") ? payload : "", strstr(payload ? payload : "", "end_fields=") ? payload : ""); Lib_ConvergenceScoreEngine_v1_Result variance_r; Lib_ConvergenceScoreEngine_v1_Result contradiction_r; double variance = 0.0; double contradiction = 1.0; MCS_projected_variance(payload, &variance_r); MCS_contradiction_score(payload, &contradiction_r); if (strstr(variance_r.outputs, "\"projected_variance\":")) variance = atof(strstr(variance_r.outputs, "\"projected_variance\":") + strlen("\"projected_variance\":")); if (strstr(contradiction_r.outputs, "\"contradiction_score\":")) contradiction = atof(strstr(contradiction_r.outputs, "\"contradiction_score\":") + strlen("\"contradiction_score\":")); snprintf(outputs, sizeof(outputs), "{\"total_fit\":%.3f,\"overlap\":%.3f,\"variance\":%.3f,\"contradiction\":%.3f}", (overlap * 0.5) + ((1.0 / (1.0 + variance)) * 0.2) + (contradiction * 0.3), overlap, variance, contradiction); MCS_setup_result(result, "Lib_ConvergenceScoreEngine_v1", payload ? payload : "", outputs, "{}", "total fit computed", "{\"action\":\"total_fit\"}"); return 1; }

/* ===== Lib_EndCandidateEngine_v1.c ===== */
    if (!dest || size == 0) return;
    if (!src) { dest[0] = '\0'; return; }
    snprintf(dest, size, "%s", src);
}
    if (!text) return;
    start = text;
    while (*start && isspace((unsigned char)*start)) start++;
    if (start != text) memmove(text, start, strlen(start) + 1);
    length = strlen(text);
    while (length > 0 && isspace((unsigned char)text[length - 1])) {
        text[length - 1] = '\0';
    }
}
static int vb_split_csv(const char *csv, char items[][VB_MAX_TOKEN], int max_items) {
    int count = 0;
    if (!csv || !*csv || max_items <= 0) return 0;
    cursor = buffer;
    while ((token = strsep(&cursor, ",")) != NULL && count < max_items) {
        if (items[count][0]) count++;
    }
    return count;
}
static int vb_contains_csv_item(const char *csv, const char *needle) {
    if (!needle || !*needle) return 0;
    count = vb_split_csv(csv, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (strcmp(items[i], needle) == 0) return 1;
    return 0;
}
static int vb_count_shared_csv(const char *left, const char *right) {
    int shared = 0;
    count = vb_split_csv(left, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (vb_contains_csv_item(right, items[i])) shared++;
    return shared;
}
static int vb_count_csv(const char *csv) {
    return vb_split_csv(csv, items, VB_MAX_ITEMS);
}
    if (!dest || size == 0) return;
    dest[0] = '\0';
    if (!payload || !key) return;
    snprintf(pattern, sizeof(pattern), "%s=", key);
    start = strstr(payload, pattern);
    if (!start) return;
    start += strlen(pattern);
    end = strchr(start, ';');
    if (!end) end = payload + strlen(payload);
    length = (size_t)(end - start);
    if (length >= size) length = size - 1;
    memcpy(dest, start, length);
    dest[length] = '\0';
}
static double vb_extract_double(const char *payload, const char *key, double fallback) {
    return value[0] ? atof(value) : fallback;
}
static int vb_extract_int(const char *payload, const char *key, int fallback) {
    return value[0] ? atoi(value) : fallback;
}
typedef struct Lib_EndCandidateEngine_v1_Result {
static void MEC_setup_result(Lib_EndCandidateEngine_v1_Result *result, const char *emitter, const char *inputs, const char *outputs, const char *errors, const char *logs, const char *meta) {
    if (!result) return;
    result->emitter = emitter;
    result->inputs = inputs;
    result->outputs = outputs;
    result->errors = errors;
    result->logs = logs;
    result->meta = meta;
}
static const char *Lib_EndCandidateEngine_v1_declaration(void) {
    return "id=Lib_EndCandidateEngine_v1;domain=MAGNETIC_ENDS;";
}
static int MEC_init_end_candidates(const char *payload, Lib_EndCandidateEngine_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char target_fields[VB_MAX_TEXT]; vb_extract_value(payload, "target_fields", target_fields, sizeof(target_fields)); snprintf(outputs, sizeof(outputs), "{\"end_candidates\":[\"%s_candidate\"]}", target_fields); MEC_setup_result(result, "Lib_EndCandidateEngine_v1", payload ? payload : "", outputs, "{}", "end candidates initialized", "{\"action\":\"init_end_candidates\"}"); return 1; }
static int MEC_rank_candidates(const char *payload, Lib_EndCandidateEngine_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char candidates[VB_MAX_TEXT]; vb_extract_value(payload, "candidates", candidates, sizeof(candidates)); snprintf(outputs, sizeof(outputs), "{\"ranked\":[\"%s\"],\"ranking\":\"attraction_then_trust\"}", candidates); MEC_setup_result(result, "Lib_EndCandidateEngine_v1", payload ? payload : "", outputs, "{}", "candidates ranked", "{\"action\":\"rank_candidates\"}"); return 1; }
static int MEC_candidate_status(const char *payload, Lib_EndCandidateEngine_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char candidate[VB_MAX_TOKEN]; vb_extract_value(payload, "candidate", candidate, sizeof(candidate)); snprintf(outputs, sizeof(outputs), "{\"candidate\":\"%s\",\"status\":\"ready_for_survivor_prune\"}", candidate); MEC_setup_result(result, "Lib_EndCandidateEngine_v1", payload ? payload : "", outputs, "{}", "candidate status emitted", "{\"action\":\"candidate_status\"}"); return 1; }

/* ===== Lib_EndStateLockEngine_v1.c ===== */
    if (!dest || size == 0) return;
    if (!src) { dest[0] = '\0'; return; }
    snprintf(dest, size, "%s", src);
}
    if (!text) return;
    start = text;
    while (*start && isspace((unsigned char)*start)) start++;
    if (start != text) memmove(text, start, strlen(start) + 1);
    length = strlen(text);
    while (length > 0 && isspace((unsigned char)text[length - 1])) {
        text[length - 1] = '\0';
    }
}
static int vb_split_csv(const char *csv, char items[][VB_MAX_TOKEN], int max_items) {
    int count = 0;
    if (!csv || !*csv || max_items <= 0) return 0;
    cursor = buffer;
    while ((token = strsep(&cursor, ",")) != NULL && count < max_items) {
        if (items[count][0]) count++;
    }
    return count;
}
static int vb_contains_csv_item(const char *csv, const char *needle) {
    if (!needle || !*needle) return 0;
    count = vb_split_csv(csv, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (strcmp(items[i], needle) == 0) return 1;
    return 0;
}
static int vb_count_shared_csv(const char *left, const char *right) {
    int shared = 0;
    count = vb_split_csv(left, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (vb_contains_csv_item(right, items[i])) shared++;
    return shared;
}
static int vb_count_csv(const char *csv) {
    return vb_split_csv(csv, items, VB_MAX_ITEMS);
}
    if (!dest || size == 0) return;
    dest[0] = '\0';
    if (!payload || !key) return;
    snprintf(pattern, sizeof(pattern), "%s=", key);
    start = strstr(payload, pattern);
    if (!start) return;
    start += strlen(pattern);
    end = strchr(start, ';');
    if (!end) end = payload + strlen(payload);
    length = (size_t)(end - start);
    if (length >= size) length = size - 1;
    memcpy(dest, start, length);
    dest[length] = '\0';
}
static double vb_extract_double(const char *payload, const char *key, double fallback) {
    return value[0] ? atof(value) : fallback;
}
static int vb_extract_int(const char *payload, const char *key, int fallback) {
    return value[0] ? atoi(value) : fallback;
}
typedef struct Lib_EndStateLockEngine_v1_Result {
static void MLK_setup_result(Lib_EndStateLockEngine_v1_Result *result, const char *emitter, const char *inputs, const char *outputs, const char *errors, const char *logs, const char *meta) {
    if (!result) return;
    result->emitter = emitter;
    result->inputs = inputs;
    result->outputs = outputs;
    result->errors = errors;
    result->logs = logs;
    result->meta = meta;
}
static const char *Lib_EndStateLockEngine_v1_declaration(void) {
    return "id=Lib_EndStateLockEngine_v1;domain=MAGNETIC_LOCK;";
}
static int MLK_lock_survivor(const char *payload, Lib_EndStateLockEngine_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char survivor[VB_MAX_TOKEN]; double fit = vb_extract_double(payload, "fit", 0.0); vb_extract_value(payload, "survivor", survivor, sizeof(survivor)); snprintf(outputs, sizeof(outputs), "{\"survivor\":\"%s\",\"locked\":%s,\"fit\":%.3f}", survivor, fit >= 0.70 ? "true" : "false", fit); MLK_setup_result(result, "Lib_EndStateLockEngine_v1", payload ? payload : "", outputs, "{}", "lock decision made", "{\"action\":\"lock_survivor\"}"); return 1; }
static int MLK_validate_lock(const char *payload, Lib_EndStateLockEngine_v1_Result *result) { static char outputs[VB_MAX_TEXT]; double fit = vb_extract_double(payload, "fit", 0.0); double validation = vb_extract_double(payload, "validation", 0.0); snprintf(outputs, sizeof(outputs), "{\"lock_valid\":%s,\"fit\":%.3f,\"validation\":%.3f}", (fit >= 0.70 && validation >= 0.70) ? "true" : "false", fit, validation); MLK_setup_result(result, "Lib_EndStateLockEngine_v1", payload ? payload : "", outputs, "{}", "lock validated", "{\"action\":\"validate_lock\"}"); return 1; }
static int MLK_emit_locked_state(const char *payload, Lib_EndStateLockEngine_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char survivor[VB_MAX_TOKEN]; vb_extract_value(payload, "survivor", survivor, sizeof(survivor)); snprintf(outputs, sizeof(outputs), "{\"locked_state\":\"%s\"}", survivor); MLK_setup_result(result, "Lib_EndStateLockEngine_v1", payload ? payload : "", outputs, "{}", "locked state emitted", "{\"action\":\"emit_locked_state\"}"); return 1; }

/* ===== Lib_EngineBootstrap_v1.c ===== */
    if (!dest || size == 0) return;
    if (!src) { dest[0] = '\0'; return; }
    snprintf(dest, size, "%s", src);
}
    if (!text) return;
    start = text;
    while (*start && isspace((unsigned char)*start)) start++;
    if (start != text) memmove(text, start, strlen(start) + 1);
    length = strlen(text);
    while (length > 0 && isspace((unsigned char)text[length - 1])) {
        text[length - 1] = '\0';
    }
}
static int vb_split_csv(const char *csv, char items[][VB_MAX_TOKEN], int max_items) {
    int count = 0;
    if (!csv || !*csv || max_items <= 0) return 0;
    cursor = buffer;
    while ((token = strsep(&cursor, ",")) != NULL && count < max_items) {
        if (items[count][0]) count++;
    }
    return count;
}
static int vb_contains_csv_item(const char *csv, const char *needle) {
    if (!needle || !*needle) return 0;
    count = vb_split_csv(csv, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (strcmp(items[i], needle) == 0) return 1;
    return 0;
}
static int vb_count_shared_csv(const char *left, const char *right) {
    int shared = 0;
    count = vb_split_csv(left, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (vb_contains_csv_item(right, items[i])) shared++;
    return shared;
}
static int vb_count_csv(const char *csv) {
    return vb_split_csv(csv, items, VB_MAX_ITEMS);
}
    if (!dest || size == 0) return;
    dest[0] = '\0';
    if (!payload || !key) return;
    snprintf(pattern, sizeof(pattern), "%s=", key);
    start = strstr(payload, pattern);
    if (!start) return;
    start += strlen(pattern);
    end = strchr(start, ';');
    if (!end) end = payload + strlen(payload);
    length = (size_t)(end - start);
    if (length >= size) length = size - 1;
    memcpy(dest, start, length);
    dest[length] = '\0';
}
static double vb_extract_double(const char *payload, const char *key, double fallback) {
    return value[0] ? atof(value) : fallback;
}
static int vb_extract_int(const char *payload, const char *key, int fallback) {
    return value[0] ? atoi(value) : fallback;
}
typedef struct Lib_EngineBootstrap_v1_Result {
static void MBT_setup_result(Lib_EngineBootstrap_v1_Result *result, const char *emitter, const char *inputs, const char *outputs, const char *errors, const char *logs, const char *meta) {
    if (!result) return;
    result->emitter = emitter;
    result->inputs = inputs;
    result->outputs = outputs;
    result->errors = errors;
    result->logs = logs;
    result->meta = meta;
}
static const char *Lib_EngineBootstrap_v1_declaration(void) {
    return "id=Lib_EngineBootstrap_v1;domain=MAGNETIC_BOOT;";
}
static int MBT_init_defaults(const char *payload, Lib_EngineBootstrap_v1_Result *result) { MBT_setup_result(result, "Lib_EngineBootstrap_v1", payload ? payload : "", "{\"defaults\":{\"field_strength\":0.85,\"threshold\":0.30}}", "{}", "defaults initialized", "{\"action\":\"init_defaults\"}"); return 1; }
static int MBT_boot_sequence(const char *payload, Lib_EngineBootstrap_v1_Result *result) { MBT_setup_result(result, "Lib_EngineBootstrap_v1", payload ? payload : "", "{\"boot_sequence\":[\"register_decl\",\"magnetic_check\",\"admit_plan\",\"execute_plan\",\"route_result\",\"cleanup\"]}", "{}", "boot sequence prepared", "{\"action\":\"boot_sequence\"}"); return 1; }
static int MBT_load_runtime_config(const char *payload, Lib_EngineBootstrap_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char profile[VB_MAX_TOKEN]; vb_extract_value(payload, "runtime_profile", profile, sizeof(profile)); snprintf(outputs, sizeof(outputs), "{\"runtime_profile\":\"%s\"}", profile[0] ? profile : "default"); MBT_setup_result(result, "Lib_EngineBootstrap_v1", payload ? payload : "", outputs, "{}", "runtime config loaded", "{\"action\":\"load_runtime_config\"}"); return 1; }

/* ===== Lib_EngineReport_v1.c ===== */
    if (!dest || size == 0) return;
    if (!src) { dest[0] = '\0'; return; }
    snprintf(dest, size, "%s", src);
}
    if (!text) return;
    start = text;
    while (*start && isspace((unsigned char)*start)) start++;
    if (start != text) memmove(text, start, strlen(start) + 1);
    length = strlen(text);
    while (length > 0 && isspace((unsigned char)text[length - 1])) {
        text[length - 1] = '\0';
    }
}
static int vb_split_csv(const char *csv, char items[][VB_MAX_TOKEN], int max_items) {
    int count = 0;
    if (!csv || !*csv || max_items <= 0) return 0;
    cursor = buffer;
    while ((token = strsep(&cursor, ",")) != NULL && count < max_items) {
        if (items[count][0]) count++;
    }
    return count;
}
static int vb_contains_csv_item(const char *csv, const char *needle) {
    if (!needle || !*needle) return 0;
    count = vb_split_csv(csv, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (strcmp(items[i], needle) == 0) return 1;
    return 0;
}
static int vb_count_shared_csv(const char *left, const char *right) {
    int shared = 0;
    count = vb_split_csv(left, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (vb_contains_csv_item(right, items[i])) shared++;
    return shared;
}
static int vb_count_csv(const char *csv) {
    return vb_split_csv(csv, items, VB_MAX_ITEMS);
}
    if (!dest || size == 0) return;
    dest[0] = '\0';
    if (!payload || !key) return;
    snprintf(pattern, sizeof(pattern), "%s=", key);
    start = strstr(payload, pattern);
    if (!start) return;
    start += strlen(pattern);
    end = strchr(start, ';');
    if (!end) end = payload + strlen(payload);
    length = (size_t)(end - start);
    if (length >= size) length = size - 1;
    memcpy(dest, start, length);
    dest[length] = '\0';
}
static double vb_extract_double(const char *payload, const char *key, double fallback) {
    return value[0] ? atof(value) : fallback;
}
static int vb_extract_int(const char *payload, const char *key, int fallback) {
    return value[0] ? atoi(value) : fallback;
}
typedef struct Lib_EngineReport_v1_Result {
static void MRP_setup_result(Lib_EngineReport_v1_Result *result, const char *emitter, const char *inputs, const char *outputs, const char *errors, const char *logs, const char *meta) {
    if (!result) return;
    result->emitter = emitter;
    result->inputs = inputs;
    result->outputs = outputs;
    result->errors = errors;
    result->logs = logs;
    result->meta = meta;
}
static const char *Lib_EngineReport_v1_declaration(void) {
    return "id=Lib_EngineReport_v1;domain=MAGNETIC_REPORT;";
}
static int MRP_format_report(const char *payload, Lib_EngineReport_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char packets[VB_MAX_TEXT]; vb_extract_value(payload, "result_packets", packets, sizeof(packets)); snprintf(outputs, sizeof(outputs), "{\"report\":\"%s\"}", packets); MRP_setup_result(result, "Lib_EngineReport_v1", payload ? payload : "", outputs, "{}", "report formatted", "{\"action\":\"format_report\"}"); return 1; }
static int MRP_route_report(const char *payload, Lib_EngineReport_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char route[VB_MAX_TOKEN]; vb_extract_value(payload, "routing_targets", route, sizeof(route)); snprintf(outputs, sizeof(outputs), "{\"route\":\"%s\"}", route[0] ? route : "ExecutionReport"); MRP_setup_result(result, "Lib_EngineReport_v1", payload ? payload : "", outputs, "{}", "report routed", "{\"action\":\"route_report\"}"); return 1; }
static int MRP_emit_fit_summary(const char *payload, Lib_EngineReport_v1_Result *result) { static char outputs[VB_MAX_TEXT]; double fit = vb_extract_double(payload, "fit", 0.0); snprintf(outputs, sizeof(outputs), "{\"fit_summary\":%.3f}", fit); MRP_setup_result(result, "Lib_EngineReport_v1", payload ? payload : "", outputs, "{}", "fit summary emitted", "{\"action\":\"emit_fit_summary\"}"); return 1; }
static int MRP_emit_survivor_summary(const char *payload, Lib_EngineReport_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char survivor[VB_MAX_TOKEN]; vb_extract_value(payload, "survivor", survivor, sizeof(survivor)); snprintf(outputs, sizeof(outputs), "{\"survivor_summary\":\"%s\"}", survivor); MRP_setup_result(result, "Lib_EngineReport_v1", payload ? payload : "", outputs, "{}", "survivor summary emitted", "{\"action\":\"emit_survivor_summary\"}"); return 1; }

/* ===== Lib_FieldExpandEngine_v1.c ===== */
    if (!dest || size == 0) return;
    if (!src) { dest[0] = '\0'; return; }
    snprintf(dest, size, "%s", src);
}
    if (!text) return;
    start = text;
    while (*start && isspace((unsigned char)*start)) start++;
    if (start != text) memmove(text, start, strlen(start) + 1);
    length = strlen(text);
    while (length > 0 && isspace((unsigned char)text[length - 1])) {
        text[length - 1] = '\0';
    }
}
static int vb_split_csv(const char *csv, char items[][VB_MAX_TOKEN], int max_items) {
    int count = 0;
    if (!csv || !*csv || max_items <= 0) return 0;
    cursor = buffer;
    while ((token = strsep(&cursor, ",")) != NULL && count < max_items) {
        if (items[count][0]) count++;
    }
    return count;
}
static int vb_contains_csv_item(const char *csv, const char *needle) {
    if (!needle || !*needle) return 0;
    count = vb_split_csv(csv, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (strcmp(items[i], needle) == 0) return 1;
    return 0;
}
static int vb_count_shared_csv(const char *left, const char *right) {
    int shared = 0;
    count = vb_split_csv(left, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (vb_contains_csv_item(right, items[i])) shared++;
    return shared;
}
static int vb_count_csv(const char *csv) {
    return vb_split_csv(csv, items, VB_MAX_ITEMS);
}
    if (!dest || size == 0) return;
    dest[0] = '\0';
    if (!payload || !key) return;
    snprintf(pattern, sizeof(pattern), "%s=", key);
    start = strstr(payload, pattern);
    if (!start) return;
    start += strlen(pattern);
    end = strchr(start, ';');
    if (!end) end = payload + strlen(payload);
    length = (size_t)(end - start);
    if (length >= size) length = size - 1;
    memcpy(dest, start, length);
    dest[length] = '\0';
}
static double vb_extract_double(const char *payload, const char *key, double fallback) {
    return value[0] ? atof(value) : fallback;
}
static int vb_extract_int(const char *payload, const char *key, int fallback) {
    return value[0] ? atoi(value) : fallback;
}
typedef struct Lib_FieldExpandEngine_v1_Result {
static void MFE_setup_result(Lib_FieldExpandEngine_v1_Result *result, const char *emitter, const char *inputs, const char *outputs, const char *errors, const char *logs, const char *meta) {
    if (!result) return;
    result->emitter = emitter;
    result->inputs = inputs;
    result->outputs = outputs;
    result->errors = errors;
    result->logs = logs;
    result->meta = meta;
}
static const char *Lib_FieldExpandEngine_v1_declaration(void) {
    return "id=Lib_FieldExpandEngine_v1;domain=MAGNETIC_FIELD;";
}
static int MFE_expand_field(const char *payload, Lib_FieldExpandEngine_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char fields[VB_MAX_TEXT]; int radius; vb_extract_value(payload, "fields", fields, sizeof(fields)); radius = vb_extract_int(payload, "radius", 1); snprintf(outputs, sizeof(outputs), "{\"expanded_fields\":\"%s\",\"radius\":%d,\"window\":%d}", fields, radius, radius * 2 + 1); MFE_setup_result(result, "Lib_FieldExpandEngine_v1", payload ? payload : "", outputs, "{}", "field expansion complete", "{\"action\":\"expand_field\"}"); return 1; }
static int MFE_derive_toward_candidates(const char *payload, Lib_FieldExpandEngine_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char fields[VB_MAX_TEXT]; vb_extract_value(payload, "fields", fields, sizeof(fields)); snprintf(outputs, sizeof(outputs), "{\"candidates\":[\"%s_toward\",\"%s_near\"]}", fields, fields); MFE_setup_result(result, "Lib_FieldExpandEngine_v1", payload ? payload : "", outputs, "{}", "toward candidates derived", "{\"action\":\"derive_toward_candidates\"}"); return 1; }
static int MFE_preserve_importance(const char *payload, Lib_FieldExpandEngine_v1_Result *result) { static char outputs[VB_MAX_TEXT]; double importance = vb_extract_double(payload, "importance", 1.0); snprintf(outputs, sizeof(outputs), "{\"importance\":%.3f,\"preserved\":true}", importance); MFE_setup_result(result, "Lib_FieldExpandEngine_v1", payload ? payload : "", outputs, "{}", "importance preserved", "{\"action\":\"preserve_importance\"}"); return 1; }

/* ===== Lib_MagneticAuthorityWeight_v1.c ===== */
    if (!dest || size == 0) return;
    if (!src) { dest[0] = '\0'; return; }
    snprintf(dest, size, "%s", src);
}
    if (!text) return;
    start = text;
    while (*start && isspace((unsigned char)*start)) start++;
    if (start != text) memmove(text, start, strlen(start) + 1);
    length = strlen(text);
    while (length > 0 && isspace((unsigned char)text[length - 1])) {
        text[length - 1] = '\0';
    }
}
static int vb_split_csv(const char *csv, char items[][VB_MAX_TOKEN], int max_items) {
    int count = 0;
    if (!csv || !*csv || max_items <= 0) return 0;
    cursor = buffer;
    while ((token = strsep(&cursor, ",")) != NULL && count < max_items) {
        if (items[count][0]) count++;
    }
    return count;
}
static int vb_contains_csv_item(const char *csv, const char *needle) {
    if (!needle || !*needle) return 0;
    count = vb_split_csv(csv, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (strcmp(items[i], needle) == 0) return 1;
    return 0;
}
static int vb_count_shared_csv(const char *left, const char *right) {
    int shared = 0;
    count = vb_split_csv(left, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (vb_contains_csv_item(right, items[i])) shared++;
    return shared;
}
static int vb_count_csv(const char *csv) {
    return vb_split_csv(csv, items, VB_MAX_ITEMS);
}
    if (!dest || size == 0) return;
    dest[0] = '\0';
    if (!payload || !key) return;
    snprintf(pattern, sizeof(pattern), "%s=", key);
    start = strstr(payload, pattern);
    if (!start) return;
    start += strlen(pattern);
    end = strchr(start, ';');
    if (!end) end = payload + strlen(payload);
    length = (size_t)(end - start);
    if (length >= size) length = size - 1;
    memcpy(dest, start, length);
    dest[length] = '\0';
}
static double vb_extract_double(const char *payload, const char *key, double fallback) {
    return value[0] ? atof(value) : fallback;
}
static int vb_extract_int(const char *payload, const char *key, int fallback) {
    return value[0] ? atoi(value) : fallback;
}
typedef struct Lib_MagneticAuthorityWeight_v1_Result {
static void MAW_setup_result(Lib_MagneticAuthorityWeight_v1_Result *result, const char *emitter, const char *inputs, const char *outputs, const char *errors, const char *logs, const char *meta) {
    if (!result) return;
    result->emitter = emitter;
    result->inputs = inputs;
    result->outputs = outputs;
    result->errors = errors;
    result->logs = logs;
    result->meta = meta;
}
static const char *Lib_MagneticAuthorityWeight_v1_declaration(void) {
    return "id=Lib_MagneticAuthorityWeight_v1;function=score_authority;domain=MAGNETIC_AUTHORITY_WEIGHT;";
}
static const char *MAW_label[] = {"LAW","Q_A","GLOSSARY","CODE","CHAT","UNKNOWN"};
static const double MAW_score[] = {1.00,0.85,0.70,0.55,0.40,0.20};
static int MAW_idx(const char *label) { int i; for (i = 0; i < 6; ++i) if (label && strcmp(label, MAW_label[i]) == 0) return i; return 5; }
static int MAW_load_defaults(const char *payload, Lib_MagneticAuthorityWeight_v1_Result *result) { MAW_setup_result(result, "Lib_MagneticAuthorityWeight_v1", payload ? payload : "", "{\"LAW\":1.0,\"Q_A\":0.85,\"GLOSSARY\":0.70,\"CODE\":0.55,\"CHAT\":0.40,\"UNKNOWN\":0.20}", "{}", "authority defaults loaded", "{\"action\":\"load_defaults\"}"); return 1; }
static int MAW_score_authority(const char *payload, Lib_MagneticAuthorityWeight_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char authority[VB_MAX_TOKEN]; int idx; vb_extract_value(payload, "authority", authority, sizeof(authority)); idx = MAW_idx(authority); snprintf(outputs, sizeof(outputs), "{\"authority\":\"%s\",\"score\":%.2f}", MAW_label[idx], MAW_score[idx]); MAW_setup_result(result, "Lib_MagneticAuthorityWeight_v1", payload ? payload : "", outputs, "{}", "authority scored", "{\"action\":\"score_authority\"}"); return 1; }
static int MAW_rank_authority(const char *payload, Lib_MagneticAuthorityWeight_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char labels[VB_MAX_TEXT]; char items[VB_MAX_ITEMS][VB_MAX_TOKEN]; int count; int i; int j; vb_extract_value(payload, "labels", labels, sizeof(labels)); if (!labels[0]) vb_copy_text(labels, sizeof(labels), "LAW,Q_A,GLOSSARY,CODE,CHAT,UNKNOWN"); count = vb_split_csv(labels, items, VB_MAX_ITEMS); for (i = 0; i < count; ++i) for (j = i + 1; j < count; ++j) if (MAW_score[MAW_idx(items[j])] > MAW_score[MAW_idx(items[i])]) { char tmp[VB_MAX_TOKEN]; vb_copy_text(tmp, sizeof(tmp), items[i]); vb_copy_text(items[i], sizeof(items[i]), items[j]); vb_copy_text(items[j], sizeof(items[j]), tmp); } snprintf(outputs, sizeof(outputs), "{\"ranked\":["); for (i = 0; i < count; ++i) { char part[256]; snprintf(part, sizeof(part), "%s{\"label\":\"%s\",\"score\":%.2f}", i == 0 ? "" : ",", items[i], MAW_score[MAW_idx(items[i])]); strcat(outputs, part); } strcat(outputs, "]}"); MAW_setup_result(result, "Lib_MagneticAuthorityWeight_v1", payload ? payload : "", outputs, "{}", "authority ranked", "{\"action\":\"rank_authority\"}"); return 1; }

/* ===== Lib_MagneticCanonicalMap_v1.c ===== */
    if (!dest || size == 0) return;
    if (!src) { dest[0] = '\0'; return; }
    snprintf(dest, size, "%s", src);
}
    if (!text) return;
    start = text;
    while (*start && isspace((unsigned char)*start)) start++;
    if (start != text) memmove(text, start, strlen(start) + 1);
    length = strlen(text);
    while (length > 0 && isspace((unsigned char)text[length - 1])) {
        text[length - 1] = '\0';
    }
}
static int vb_split_csv(const char *csv, char items[][VB_MAX_TOKEN], int max_items) {
    int count = 0;
    if (!csv || !*csv || max_items <= 0) return 0;
    cursor = buffer;
    while ((token = strsep(&cursor, ",")) != NULL && count < max_items) {
        if (items[count][0]) count++;
    }
    return count;
}
static int vb_contains_csv_item(const char *csv, const char *needle) {
    if (!needle || !*needle) return 0;
    count = vb_split_csv(csv, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (strcmp(items[i], needle) == 0) return 1;
    return 0;
}
static int vb_count_shared_csv(const char *left, const char *right) {
    int shared = 0;
    count = vb_split_csv(left, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (vb_contains_csv_item(right, items[i])) shared++;
    return shared;
}
static int vb_count_csv(const char *csv) {
    return vb_split_csv(csv, items, VB_MAX_ITEMS);
}
    if (!dest || size == 0) return;
    dest[0] = '\0';
    if (!payload || !key) return;
    snprintf(pattern, sizeof(pattern), "%s=", key);
    start = strstr(payload, pattern);
    if (!start) return;
    start += strlen(pattern);
    end = strchr(start, ';');
    if (!end) end = payload + strlen(payload);
    length = (size_t)(end - start);
    if (length >= size) length = size - 1;
    memcpy(dest, start, length);
    dest[length] = '\0';
}
static double vb_extract_double(const char *payload, const char *key, double fallback) {
    return value[0] ? atof(value) : fallback;
}
static int vb_extract_int(const char *payload, const char *key, int fallback) {
    return value[0] ? atoi(value) : fallback;
}
typedef struct Lib_MagneticCanonicalMap_v1_Result {
static void MCM_setup_result(Lib_MagneticCanonicalMap_v1_Result *result, const char *emitter, const char *inputs, const char *outputs, const char *errors, const char *logs, const char *meta) {
    if (!result) return;
    result->emitter = emitter;
    result->inputs = inputs;
    result->outputs = outputs;
    result->errors = errors;
    result->logs = logs;
    result->meta = meta;
}
static const char *Lib_MagneticCanonicalMap_v1_declaration(void) {
    return "id=Lib_MagneticCanonicalMap_v1;function=resolve;domain=MAGNETIC_CANONICAL_MAP;";
}
static char MCM_loose[VB_MAX_ITEMS][VB_MAX_TOKEN];
static char MCM_canon[VB_MAX_ITEMS][VB_MAX_TOKEN];
static int MCM_count = 0;
static void MCM_seed(void) { if (MCM_count) return; vb_copy_text(MCM_loose[MCM_count], VB_MAX_TOKEN, "ram unit"); vb_copy_text(MCM_canon[MCM_count++], VB_MAX_TOKEN, "Core_RamUnit"); vb_copy_text(MCM_loose[MCM_count], VB_MAX_TOKEN, "memory db"); vb_copy_text(MCM_canon[MCM_count++], VB_MAX_TOKEN, "MemDB"); vb_copy_text(MCM_loose[MCM_count], VB_MAX_TOKEN, "memory bus"); vb_copy_text(MCM_canon[MCM_count++], VB_MAX_TOKEN, "MemoryBus"); vb_copy_text(MCM_loose[MCM_count], VB_MAX_TOKEN, "gui bus"); vb_copy_text(MCM_canon[MCM_count++], VB_MAX_TOKEN, "Core_GuiBus"); }
static int MCM_add_alias(const char *payload, Lib_MagneticCanonicalMap_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char loose[VB_MAX_TOKEN]; char canon[VB_MAX_TOKEN]; int i; MCM_seed(); vb_extract_value(payload, "loose", loose, sizeof(loose)); vb_extract_value(payload, "canonical", canon, sizeof(canon)); for (i = 0; i < MCM_count; ++i) if (strcmp(MCM_loose[i], loose) == 0) { vb_copy_text(MCM_canon[i], VB_MAX_TOKEN, canon); snprintf(outputs, sizeof(outputs), "{\"updated\":true,\"loose\":\"%s\",\"canonical\":\"%s\"}", loose, canon); MCM_setup_result(result, "Lib_MagneticCanonicalMap_v1", payload ? payload : "", outputs, "{}", "alias updated", "{\"action\":\"add_alias\"}"); return 1; } if (MCM_count < VB_MAX_ITEMS) { vb_copy_text(MCM_loose[MCM_count], VB_MAX_TOKEN, loose); vb_copy_text(MCM_canon[MCM_count++], VB_MAX_TOKEN, canon); } snprintf(outputs, sizeof(outputs), "{\"added\":true,\"loose\":\"%s\",\"canonical\":\"%s\"}", loose, canon); MCM_setup_result(result, "Lib_MagneticCanonicalMap_v1", payload ? payload : "", outputs, "{}", "alias added", "{\"action\":\"add_alias\"}"); return 1; }
static int MCM_resolve(const char *payload, Lib_MagneticCanonicalMap_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char term[VB_MAX_TOKEN]; int i; MCM_seed(); vb_extract_value(payload, "term", term, sizeof(term)); for (i = 0; i < MCM_count; ++i) if (strcmp(MCM_loose[i], term) == 0) { snprintf(outputs, sizeof(outputs), "{\"term\":\"%s\",\"resolved\":\"%s\"}", term, MCM_canon[i]); MCM_setup_result(result, "Lib_MagneticCanonicalMap_v1", payload ? payload : "", outputs, "{}", "canonical resolved", "{\"action\":\"resolve\"}"); return 1; } snprintf(outputs, sizeof(outputs), "{\"term\":\"%s\",\"resolved\":\"%s\"}", term, term); MCM_setup_result(result, "Lib_MagneticCanonicalMap_v1", payload ? payload : "", outputs, "{}", "term already canonical", "{\"action\":\"resolve\"}"); return 1; }
static int MCM_bulk_load(const char *payload, Lib_MagneticCanonicalMap_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char mappings[VB_MAX_TEXT]; char rows[VB_MAX_ITEMS][VB_MAX_TOKEN]; int count; int i; MCM_seed(); vb_extract_value(payload, "mappings", mappings, sizeof(mappings)); count = vb_split_csv(mappings, rows, VB_MAX_ITEMS); for (i = 0; i < count && MCM_count < VB_MAX_ITEMS; ++i) { char *sep = strchr(rows[i], ':'); if (sep) { *sep = '\0'; vb_trim_in_place(rows[i]); vb_trim_in_place(sep + 1); vb_copy_text(MCM_loose[MCM_count], VB_MAX_TOKEN, rows[i]); vb_copy_text(MCM_canon[MCM_count++], VB_MAX_TOKEN, sep + 1); } } snprintf(outputs, sizeof(outputs), "{\"loaded\":%d,\"count\":%d}", count, MCM_count); MCM_setup_result(result, "Lib_MagneticCanonicalMap_v1", payload ? payload : "", outputs, "{}", "bulk mappings loaded", "{\"action\":\"bulk_load\"}"); return 1; }
static int MCM_reverse_lookup(const char *payload, Lib_MagneticCanonicalMap_v1_Result *result) { static char outputs[VB_MAX_TEXT]; char canonical[VB_MAX_TOKEN]; int i; int first = 1; MCM_seed(); vb_extract_value(payload, "canonical", canonical, sizeof(canonical)); snprintf(outputs, sizeof(outputs), "{\"canonical\":\"%s\",\"aliases\":[", canonical); for (i = 0; i < MCM_count; ++i) if (strcmp(MCM_canon[i], canonical) == 0) { char part[256]; snprintf(part, sizeof(part), "%s\"%s\"", first ? "" : ",", MCM_loose[i]); strcat(outputs, part); first = 0; } strcat(outputs, "]}"); MCM_setup_result(result, "Lib_MagneticCanonicalMap_v1", payload ? payload : "", outputs, "{}", "reverse lookup complete", "{\"action\":\"reverse_lookup\"}"); return 1; }

/* ===== Lib_MagneticComponent_v1.c ===== */
    if (!dest || size == 0) return;
    if (!src) { dest[0] = '\0'; return; }
    snprintf(dest, size, "%s", src);
}
    if (!text) return;
    start = text;
    while (*start && isspace((unsigned char)*start)) start++;
    if (start != text) memmove(text, start, strlen(start) + 1);
    length = strlen(text);
    while (length > 0 && isspace((unsigned char)text[length - 1])) {
        text[length - 1] = '\0';
    }
}
static int vb_split_csv(const char *csv, char items[][VB_MAX_TOKEN], int max_items) {
    int count = 0;
    if (!csv || !*csv || max_items <= 0) return 0;
    cursor = buffer;
    while ((token = strsep(&cursor, ",")) != NULL && count < max_items) {
        if (items[count][0]) count++;
    }
    return count;
}
static int vb_contains_csv_item(const char *csv, const char *needle) {
    if (!needle || !*needle) return 0;
    count = vb_split_csv(csv, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (strcmp(items[i], needle) == 0) return 1;
    return 0;
}
static int vb_count_shared_csv(const char *left, const char *right) {
    int shared = 0;
    count = vb_split_csv(left, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (vb_contains_csv_item(right, items[i])) shared++;
    return shared;
}
static int vb_count_csv(const char *csv) {
    return vb_split_csv(csv, items, VB_MAX_ITEMS);
}
    if (!dest || size == 0) return;
    dest[0] = '\0';
    if (!payload || !key) return;
    snprintf(pattern, sizeof(pattern), "%s=", key);
    start = strstr(payload, pattern);
    if (!start) return;
    start += strlen(pattern);
    end = strchr(start, ';');
    if (!end) end = payload + strlen(payload);
    length = (size_t)(end - start);
    if (length >= size) length = size - 1;
    memcpy(dest, start, length);
    dest[length] = '\0';
}
static double vb_extract_double(const char *payload, const char *key, double fallback) {
    return value[0] ? atof(value) : fallback;
}
static int vb_extract_int(const char *payload, const char *key, int fallback) {
    return value[0] ? atoi(value) : fallback;
}
typedef struct Lib_MagneticComponent_v1_Result {
static void MGC_setup_result(Lib_MagneticComponent_v1_Result *result, const char *emitter, const char *inputs, const char *outputs, const char *errors, const char *logs, const char *meta) {
    if (!result) return;
    result->emitter = emitter;
    result->inputs = inputs;
    result->outputs = outputs;
    result->errors = errors;
    result->logs = logs;
    result->meta = meta;
}
static const char *Lib_MagneticComponent_v1_declaration(void) {
    return "id=Lib_MagneticComponent_v1;function=calculate_attraction;domain=MAGNETIC_COMPONENT;capabilities=magnetic_properties,calculate_attraction,can_connect;requirements=capabilities,requirements,repulsions,field_strength;";
}
static int MGC_magnetic_properties(const char *payload, Lib_MagneticComponent_v1_Result *result) {
    static char outputs[VB_MAX_TEXT];
    double field_strength = vb_extract_double(payload, "field_strength", 0.85);
    snprintf(outputs, sizeof(outputs), "{\"module_id\":\"%s\",\"field_strength\":%.2f,\"capabilities\":\"%s\",\"requirements\":\"%s\",\"repulsions\":\"%s\"}", module_id, field_strength, capabilities, requirements, repulsions);
    return 1;
}
static int MGC_calculate_attraction(const char *payload, Lib_MagneticComponent_v1_Result *result) {
    static char outputs[VB_MAX_TEXT];
    double my_strength = vb_extract_double(payload, "field_strength", 0.85);
    double other_strength = vb_extract_double(payload, "other_field_strength", 0.85);
    if (vb_contains_csv_item(my_repulsions, other_id)) {
        snprintf(outputs, sizeof(outputs), "{\"attraction\":0.0,\"blocked_by_repulsion\":true}");
        return 1;
    }
    cap_matches = vb_count_shared_csv(my_caps, other_reqs);
    req_matches = vb_count_shared_csv(other_caps, my_reqs);
    other_req_count = vb_count_csv(other_reqs);
    my_req_count = vb_count_csv(my_reqs);
    cap_match = other_req_count > 0 ? (double)cap_matches / (double)other_req_count : 0.0;
    req_match = my_req_count > 0 ? (double)req_matches / (double)my_req_count : 0.0;
    attraction = ((cap_match + req_match) / 2.0) * my_strength * other_strength;
    if (attraction > 1.0) attraction = 1.0;
    snprintf(outputs, sizeof(outputs), "{\"cap_match\":%.3f,\"req_match\":%.3f,\"attraction\":%.3f}", cap_match, req_match, attraction);
    return 1;
}
static int MGC_can_connect(const char *payload, Lib_MagneticComponent_v1_Result *result) {
    static char outputs[VB_MAX_TEXT];
    double threshold = vb_extract_double(payload, "threshold", 0.30);
    double attraction = 0.0;
    marker = strstr(nested.outputs ? nested.outputs : "", "\"attraction\":");
    if (marker) attraction = atof(marker + strlen("\"attraction\":"));
    snprintf(outputs, sizeof(outputs), "{\"can_connect\":%s,\"attraction\":%.3f,\"threshold\":%.3f}", attraction > threshold ? "true" : "false", attraction, threshold);
    return 1;
}

/* ===== Lib_MagneticIndex_v1.c ===== */
    if (!dest || size == 0) return;
    if (!src) { dest[0] = '\0'; return; }
    snprintf(dest, size, "%s", src);
}
    if (!text) return;
    start = text;
    while (*start && isspace((unsigned char)*start)) start++;
    if (start != text) memmove(text, start, strlen(start) + 1);
    length = strlen(text);
    while (length > 0 && isspace((unsigned char)text[length - 1])) {
        text[length - 1] = '\0';
    }
}
static int vb_split_csv(const char *csv, char items[][VB_MAX_TOKEN], int max_items) {
    int count = 0;
    if (!csv || !*csv || max_items <= 0) return 0;
    cursor = buffer;
    while ((token = strsep(&cursor, ",")) != NULL && count < max_items) {
        if (items[count][0]) count++;
    }
    return count;
}
static int vb_contains_csv_item(const char *csv, const char *needle) {
    if (!needle || !*needle) return 0;
    count = vb_split_csv(csv, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (strcmp(items[i], needle) == 0) return 1;
    return 0;
}
static int vb_count_shared_csv(const char *left, const char *right) {
    int shared = 0;
    count = vb_split_csv(left, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (vb_contains_csv_item(right, items[i])) shared++;
    return shared;
}
static int vb_count_csv(const char *csv) {
    return vb_split_csv(csv, items, VB_MAX_ITEMS);
}
    if (!dest || size == 0) return;
    dest[0] = '\0';
    if (!payload || !key) return;
    snprintf(pattern, sizeof(pattern), "%s=", key);
    start = strstr(payload, pattern);
    if (!start) return;
    start += strlen(pattern);
    end = strchr(start, ';');
    if (!end) end = payload + strlen(payload);
    length = (size_t)(end - start);
    if (length >= size) length = size - 1;
    memcpy(dest, start, length);
    dest[length] = '\0';
}
static double vb_extract_double(const char *payload, const char *key, double fallback) {
    return value[0] ? atof(value) : fallback;
}
static int vb_extract_int(const char *payload, const char *key, int fallback) {
    return value[0] ? atoi(value) : fallback;
}
typedef struct Lib_MagneticIndex_v1_Result {
static void MGI_setup_result(Lib_MagneticIndex_v1_Result *result, const char *emitter, const char *inputs, const char *outputs, const char *errors, const char *logs, const char *meta) {
    if (!result) return;
    result->emitter = emitter;
    result->inputs = inputs;
    result->outputs = outputs;
    result->errors = errors;
    result->logs = logs;
    result->meta = meta;
}
static const char *Lib_MagneticIndex_v1_declaration(void) {
    return "id=Lib_MagneticIndex_v1;function=magnetic_check;domain=MAGNETIC_INDEX;capabilities=register_component,magnetic_check,compatibility_cache,route_lookup;requirements=registry_rows,field_strengths,thresholds;";
}
static char MGI_id[VB_MAX_ITEMS][VB_MAX_TOKEN];
static char MGI_caps[VB_MAX_ITEMS][VB_MAX_TEXT];
static char MGI_reqs[VB_MAX_ITEMS][VB_MAX_TEXT];
static char MGI_route[VB_MAX_ITEMS][VB_MAX_TOKEN];
static double MGI_strength[VB_MAX_ITEMS];
static double MGI_threshold[VB_MAX_ITEMS];
static int MGI_count = 0;
static int MGI_find(const char *id) {
    for (i = 0; i < MGI_count; ++i) if (strcmp(MGI_id[i], id) == 0) return i;
    return -1;
}
static int MGI_register_component(const char *payload, Lib_MagneticIndex_v1_Result *result) {
    static char outputs[VB_MAX_TEXT];
    if (!id[0]) {
        return 0;
    }
    index = MGI_find(id);
    if (index < 0 && MGI_count < VB_MAX_ITEMS) index = MGI_count++;
    MGI_strength[index] = vb_extract_double(payload, "field_strength", 0.85);
    MGI_threshold[index] = vb_extract_double(payload, "threshold", 0.30);
    snprintf(outputs, sizeof(outputs), "{\"registered\":\"%s\",\"count\":%d}", id, MGI_count);
    return 1;
}
static int MGI_magnetic_check(const char *payload, Lib_MagneticIndex_v1_Result *result) {
    static char outputs[VB_MAX_TEXT];
    li = MGI_find(left);
    ri = MGI_find(right);
    if (li < 0 || ri < 0) {
        return 0;
    }
    cap_match = vb_count_shared_csv(MGI_caps[li], MGI_reqs[ri]);
    req_match = vb_count_shared_csv(MGI_caps[ri], MGI_reqs[li]);
    attraction = ((cap_match > 0 ? 1.0 : 0.0) + (req_match > 0 ? 1.0 : 0.0)) / 2.0;
    attraction *= MGI_strength[li] * MGI_strength[ri];
    if (attraction > 1.0) attraction = 1.0;
    snprintf(outputs, sizeof(outputs), "{\"left\":\"%s\",\"right\":\"%s\",\"attraction\":%.3f,\"compatible\":%s}", left, right, attraction, (attraction > MGI_threshold[li] && attraction > MGI_threshold[ri]) ? "true" : "false");
    return 1;
}
static int MGI_compatibility_cache(const char *payload, Lib_MagneticIndex_v1_Result *result) {
    static char outputs[VB_MAX_TEXT];
    snprintf(outputs, sizeof(outputs), "{\"cache_key\":\"%s|%s\",\"cacheable\":true}", left, right);
    return 1;
}
static int MGI_route_lookup(const char *payload, Lib_MagneticIndex_v1_Result *result) {
    static char outputs[VB_MAX_TEXT];
    index = MGI_find(id);
    if (index < 0) {
        return 0;
    }
    snprintf(outputs, sizeof(outputs), "{\"id\":\"%s\",\"route\":\"%s\"}", id, MGI_route[index][0] ? MGI_route[index] : "ExecutionReport");
    return 1;
}

/* ===== Lib_MagneticRelationMap_v1.c ===== */
    if (!dest || size == 0) return;
    if (!src) { dest[0] = '\0'; return; }
    snprintf(dest, size, "%s", src);
}
    if (!text) return;
    start = text;
    while (*start && isspace((unsigned char)*start)) start++;
    if (start != text) memmove(text, start, strlen(start) + 1);
    length = strlen(text);
    while (length > 0 && isspace((unsigned char)text[length - 1])) {
        text[length - 1] = '\0';
    }
}
static int vb_split_csv(const char *csv, char items[][VB_MAX_TOKEN], int max_items) {
    int count = 0;
    if (!csv || !*csv || max_items <= 0) return 0;
    cursor = buffer;
    while ((token = strsep(&cursor, ",")) != NULL && count < max_items) {
        if (items[count][0]) count++;
    }
    return count;
}
static int vb_contains_csv_item(const char *csv, const char *needle) {
    if (!needle || !*needle) return 0;
    count = vb_split_csv(csv, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (strcmp(items[i], needle) == 0) return 1;
    return 0;
}
static int vb_count_shared_csv(const char *left, const char *right) {
    int shared = 0;
    count = vb_split_csv(left, items, VB_MAX_ITEMS);
    for (i = 0; i < count; ++i) if (vb_contains_csv_item(right, items[i])) shared++;
    return shared;
}
static int vb_count_csv(const char *csv) {
    return vb_split_csv(csv, items, VB_MAX_ITEMS);
}
    if (!dest || size == 0) return;
    dest[0] = '\0';
    if (!payload || !key) return;
    snprintf(pattern, sizeof(pattern), "%s=", key);
    start = strstr(payload, pattern);
    if (!start) return;
    start += strlen(pattern);
    end = strchr(start, ';');
    if (!end) end = payload + strlen(payload);
    length = (size_t)(end - start);
    if (length >= size) length = size - 1;
    memcpy(dest, start, length);
    dest[length] = '\0';
}
static double vb_extract_double(const char *payload, const char *key, double fallback) {
    return value[0] ? atof(value) : fallback;
}
static int vb_extract_int(const 