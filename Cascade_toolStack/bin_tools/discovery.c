/*
 * discovery.c — External Discovery Layer for msearch
 *
 * Layer 1: External intelligence (Gemini / web / APIs)
 * Purpose: discovery, exploration, candidate generation
 * Function: "What might be relevant out there?"
 *
 * This module handles HTTP requests to external APIs and returns
 * evidence packets. It does NOT do truth reconstruction — that's
 * Layer 2 (msearch.c internal MySQL queries).
 *
 * Dependencies: libcurl
 * Compile: -lcurl
 *
 * Architecture:
 *   Query → discovery_all() →
 *     GitHub API → evidence packets
 *     Stack Overflow API → evidence packets
 *     Google CSE API → evidence packets
 *     Gemini API → evidence packets
 *     Reddit API → evidence packets
 *   → Print results as "EXTERNAL DISCOVERY" dimension
 *
 * Each external source is a different axis of truth:
 *   GitHub      → implementation truth (external)
 *   Stack Overflow → failure-driven knowledge (external)
 *   Google      → broad coverage / docs
 *   Gemini      → synthesis + web-grounded answer
 *   Reddit      → community interpretation
 */

#include "discovery.h"
#include <curl/curl.h>
#include <ctype.h>

/* ── Curl write callback: accumulate response into memory ── */
struct curl_buffer {
    char *data;
    size_t size;
};

static size_t curl_write_cb(void *ptr, size_t size, size_t nmemb, void *userdata) {
    size_t total = size * nmemb;
    struct curl_buffer *buf = (struct curl_buffer *)userdata;

    char *newdata = realloc(buf->data, buf->size + total + 1);
    if (!newdata) return 0;

    buf->data = newdata;
    memcpy(buf->data + buf->size, ptr, total);
    buf->size += total;
    buf->data[buf->size] = '\0';
    return total;
}

/* ── HTTP GET helper: fetch URL, return response body ── */
static char *http_get(const char *url, const char *auth_header, int timeout) {
    CURL *curl = curl_easy_init();
    if (!curl) return NULL;

    struct curl_buffer buf = {0};
    buf.data = malloc(1);
    buf.data[0] = '\0';
    buf.size = 0;

    struct curl_slist *headers = NULL;
    if (auth_header) {
        headers = curl_slist_append(headers, auth_header);
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    }

    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_write_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &buf);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, timeout);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_USERAGENT, "msearch3/6.0 (context reconstruction engine)");

    CURLcode res = curl_easy_perform(curl);

    if (headers) curl_slist_free_all(headers);
    curl_easy_cleanup(curl);

    if (res != CURLE_OK) {
        free(buf.data);
        return NULL;
    }

    return buf.data;
}

/* ── Parallel fetch via curl_multi ── */
/* Fires multiple HTTP GETs concurrently in a single event loop */
#define MAX_PARALLEL_SOURCES 8

struct source_slot {
    char url[1024];
    char auth_header[512];
    struct curl_buffer buf;
    CURL *handle;
    int active;       /* 1 if this slot has a pending request */
    int is_post;      /* 1 if POST (Gemini), 0 if GET */
    char post_body[4096];
};

static void parallel_fetch(struct source_slot *slots, int n_slots, int timeout) {
    CURLM *multi = curl_multi_init();
    if (!multi) return;

    int active_count = 0;
    for (int i = 0; i < n_slots; i++) {
        if (!slots[i].active) continue;

        slots[i].buf.data = malloc(1);
        slots[i].buf.data[0] = '\0';
        slots[i].buf.size = 0;

        CURL *curl = curl_easy_init();
        if (!curl) { slots[i].active = 0; continue; }

        curl_easy_setopt(curl, CURLOPT_URL, slots[i].url);
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_write_cb);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &slots[i].buf);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, (long)timeout);
        curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
        curl_easy_setopt(curl, CURLOPT_USERAGENT, "msearch/6.0 (context reconstruction engine)");

        struct curl_slist *headers = NULL;
        if (slots[i].auth_header[0]) {
            headers = curl_slist_append(headers, slots[i].auth_header);
            curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
        }

        if (slots[i].is_post && slots[i].post_body[0]) {
            headers = curl_slist_append(headers, "Content-Type: application/json");
            curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
            curl_easy_setopt(curl, CURLOPT_POSTFIELDS, slots[i].post_body);
        }

        slots[i].handle = curl;
        curl_multi_add_handle(multi, curl);
        active_count++;
    }

    if (active_count == 0) {
        curl_multi_cleanup(multi);
        return;
    }

    int still_running = 1;
    do {
        CURLMcode mc = curl_multi_perform(multi, &still_running);
        if (mc == CURLM_OK && still_running)
            curl_multi_poll(multi, NULL, 0, 1000, NULL);
    } while (still_running);

    /* Cleanup — remove handles but keep buffers */
    for (int i = 0; i < n_slots; i++) {
        if (slots[i].handle) {
            curl_multi_remove_handle(multi, slots[i].handle);
            curl_easy_cleanup(slots[i].handle);
            slots[i].handle = NULL;
        }
    }
    curl_multi_cleanup(multi);
}

/* ── HTTP POST helper for Gemini API ── */
static char *http_post_json(const char *url, const char *json_body, int timeout) {
    CURL *curl = curl_easy_init();
    if (!curl) return NULL;

    struct curl_buffer buf = {0};
    buf.data = malloc(1);
    buf.data[0] = '\0';
    buf.size = 0;

    struct curl_slist *headers = NULL;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);

    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, json_body);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_write_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &buf);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, timeout);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_USERAGENT, "msearch3/6.0");

    CURLcode res = curl_easy_perform(curl);

    if (headers) curl_slist_free_all(headers);
    curl_easy_cleanup(curl);

    if (res != CURLE_OK) {
        free(buf.data);
        return NULL;
    }

    return buf.data;
}

/* ── URL encoder ── */
void discovery_url_encode(const char *in, char *out, size_t out_sz) {
    CURL *curl = curl_easy_init();
    if (!curl) {
        strncpy(out, in, out_sz - 1);
        out[out_sz - 1] = '\0';
        return;
    }

    char *encoded = curl_easy_escape(curl, in, 0);
    if (encoded) {
        strncpy(out, encoded, out_sz - 1);
        out[out_sz - 1] = '\0';
        curl_free(encoded);
    } else {
        strncpy(out, in, out_sz - 1);
        out[out_sz - 1] = '\0';
    }
    curl_easy_cleanup(curl);
}

/* ── Minimal JSON string extraction ── */
/* Finds "key":"value" or "key": "value" and copies value to out */
int discovery_json_extract(const char *json, const char *key, char *out, size_t out_sz) {
    char search[256];
    snprintf(search, sizeof(search), "\"%s\"", key);

    const char *p = strstr(json, search);
    if (!p) return 0;

    p += strlen(search);

    /* skip whitespace and colon */
    while (*p && (*p == ' ' || *p == ':' || *p == '\t' || *p == '\n')) p++;
    if (!*p) return 0;

    if (*p == '"') {
        p++;
        size_t i = 0;
        while (*p && *p != '"' && i < out_sz - 1) {
            if (*p == '\\' && p[1]) {
                p++;
                if (*p == 'n') out[i++] = '\n';
                else if (*p == 't') out[i++] = '\t';
                else if (*p == 'r') out[i++] = '\r';
                else out[i++] = *p;
            } else {
                out[i++] = *p;
            }
            p++;
        }
        out[i] = '\0';
        return 1;
    }

    return 0;
}

/* ── Minimal JSON array counter ── */
int discovery_json_count(const char *json, const char *key) {
    char search[256];
    snprintf(search, sizeof(search), "\"%s\"", key);

    const char *p = strstr(json, search);
    if (!p) return 0;

    p += strlen(search);
    while (*p && (*p == ' ' || *p == ':' || *p == '\t' || *p == '\n')) p++;
    if (!*p || *p != '[') return 0;

    int count = 0;
    int depth = 0;
    p++;
    while (*p) {
        if (*p == '{' || *p == '[') depth++;
        else if (*p == '}' || *p == ']') {
            if (depth == 0) break;
            depth--;
        }
        else if (*p == ',' && depth == 0) count++;
        p++;
    }
    count++; /* last element has no trailing comma */
    return count;
}

/* ── Config ── */
void discovery_config_init(discovery_config_t *cfg) {
    memset(cfg, 0, sizeof(*cfg));
    cfg->max_results = 5;
    cfg->timeout_seconds = 15;
}

void discovery_config_from_env(discovery_config_t *cfg) {
    const char *env;
    env = getenv("GITHUB_TOKEN");
    if (env) strncpy(cfg->github_token, env, sizeof(cfg->github_token) - 1);

    env = getenv("GEMINI_API_KEY");
    if (env) strncpy(cfg->gemini_api_key, env, sizeof(cfg->gemini_api_key) - 1);

    env = getenv("GOOGLE_API_KEY");
    if (env) strncpy(cfg->google_api_key, env, sizeof(cfg->google_api_key) - 1);

    env = getenv("GOOGLE_CX_ID");
    if (env) strncpy(cfg->google_cx_id, env, sizeof(cfg->google_cx_id) - 1);
}

/* ── Print evidence packet ── */
void evidence_print(evidence_t *ev) {
    printf("  ┌─ [%s] %s\n", ev->source, ev->title[0] ? ev->title : "(untitled)");
    if (ev->url[0])
        printf("  │  URL: %s\n", ev->url);
    if (ev->snippet[0])
        printf("  │  %.300s\n", ev->snippet);
    printf("  │  relevance: %s\n", ev->relevance);
    printf("  └─\n");
}

/* ── GitHub parse (from pre-fetched response) ── */
static int parse_github(const char *response, evidence_t *results, int max_results) {
    int count = 0;
    const char *p = response;
    char item_start[32];
    snprintf(item_start, sizeof(item_start), "\"full_name\"");

    while (count < max_results) {
        p = strstr(p, item_start);
        if (!p) break;

        char name[256], desc[512];
        name[0] = desc[0] = '\0';

        if (discovery_json_extract(p, "full_name", name, sizeof(name))) {
            const char *desc_p = p + 200;
            char desc_search[512];
            strncpy(desc_search, desc_p, sizeof(desc_search) - 1);
            desc_search[sizeof(desc_search) - 1] = '\0';
            discovery_json_extract(desc_search, "description", desc, sizeof(desc));

            char html_url[512];
            html_url[0] = '\0';
            discovery_json_extract(p, "html_url", html_url, sizeof(html_url));

            strncpy(results[count].source, "github", sizeof(results[count].source) - 1);
            strncpy(results[count].title, name, sizeof(results[count].title) - 1);
            if (html_url[0])
                strncpy(results[count].url, html_url, sizeof(results[count].url) - 1);
            else {
                snprintf(results[count].url, sizeof(results[count].url),
                    "https://github.com/%s", name);
            }
            strncpy(results[count].snippet, desc, sizeof(results[count].snippet) - 1);
            strcpy(results[count].relevance, "medium");

            count++;
        }

        p += strlen(item_start);
    }
    return count;
}

/* ── GitHub search ── */
int discovery_github(const char *keyword, discovery_config_t *cfg,
                      evidence_t *results, int max_results) {
    char encoded[512];
    discovery_url_encode(keyword, encoded, sizeof(encoded));

    char url[1024];
    snprintf(url, sizeof(url),
        "https://api.github.com/search/repositories?q=%s&sort=stars&order=desc&per_page=%d",
        encoded, max_results);

    char auth[512] = "";
    if (cfg->github_token[0])
        snprintf(auth, sizeof(auth), "Authorization: token %s", cfg->github_token);

    char *response = http_get(url, auth[0] ? auth : NULL, cfg->timeout_seconds);
    if (!response) return 0;

    int count = parse_github(response, results, max_results);
    free(response);
    return count;
}

/* ── Stack Overflow parse (from pre-fetched response) ── */
static int parse_stackoverflow(const char *response, evidence_t *results, int max_results) {
    int count = 0;
    const char *p = response;

    while (count < max_results) {
        char title[256], link[512];
        title[0] = link[0] = '\0';

        if (!discovery_json_extract(p, "title", title, sizeof(title)))
            break;

        const char *link_p = p + 100;
        char link_search[512];
        strncpy(link_search, link_p, sizeof(link_search) - 1);
        link_search[sizeof(link_search) - 1] = '\0';
        discovery_json_extract(link_search, "link", link, sizeof(link));

        char is_answered[16];
        is_answered[0] = '\0';
        discovery_json_extract(p, "is_answered", is_answered, sizeof(is_answered));

        strncpy(results[count].source, "stackoverflow", sizeof(results[count].source) - 1);
        strncpy(results[count].title, title, sizeof(results[count].title) - 1);
        strncpy(results[count].url, link, sizeof(results[count].url) - 1);
        strncpy(results[count].snippet, title, sizeof(results[count].snippet) - 1);
        strcpy(results[count].relevance,
            (is_answered[0] == 't' || (is_answered[0] == '1')) ? "high" : "medium");

        count++;
        p = strstr(p + 10, "\"title\"");
        if (!p) break;
    }
    return count;
}

/* ── Stack Overflow search ── */
int discovery_stackoverflow(const char *keyword, discovery_config_t *cfg,
                             evidence_t *results, int max_results) {
    char encoded[512];
    discovery_url_encode(keyword, encoded, sizeof(encoded));

    char url[1024];
    snprintf(url, sizeof(url),
        "https://api.stackexchange.com/2.3/search/advanced?order=desc&sort=relevance&q=%s&site=stackoverflow&pagesize=%d",
        encoded, max_results);

    char *response = http_get(url, NULL, cfg->timeout_seconds);
    if (!response) return 0;

    int count = parse_stackoverflow(response, results, max_results);
    free(response);
    return count;
}

/* ── Google parse (from pre-fetched response) ── */
static int parse_google(const char *response, evidence_t *results, int max_results) {
    int count = 0;
    const char *p = response;

    while (count < max_results) {
        char title[256], link[512], snippet[512];
        title[0] = link[0] = snippet[0] = '\0';

        if (!discovery_json_extract(p, "title", title, sizeof(title)))
            break;

        const char *next_p = p + 100;
        char search_buf[1024];
        strncpy(search_buf, next_p, sizeof(search_buf) - 1);
        search_buf[sizeof(search_buf) - 1] = '\0';
        discovery_json_extract(search_buf, "link", link, sizeof(link));
        discovery_json_extract(search_buf, "snippet", snippet, sizeof(snippet));

        strncpy(results[count].source, "google", sizeof(results[count].source) - 1);
        strncpy(results[count].title, title, sizeof(results[count].title) - 1);
        strncpy(results[count].url, link, sizeof(results[count].url) - 1);
        strncpy(results[count].snippet, snippet, sizeof(results[count].snippet) - 1);
        strcpy(results[count].relevance, "medium");

        count++;
        p = strstr(p + 10, "\"title\"");
        if (!p) break;
    }
    return count;
}

/* ── Google Custom Search ── */
int discovery_google(const char *keyword, discovery_config_t *cfg,
                      evidence_t *results, int max_results) {
    if (!cfg->google_api_key[0] || !cfg->google_cx_id[0])
        return 0;

    char encoded[512];
    discovery_url_encode(keyword, encoded, sizeof(encoded));

    char url[1024];
    snprintf(url, sizeof(url),
        "https://www.googleapis.com/customsearch/v1?q=%s&key=%s&cx=%s&num=%d",
        encoded, cfg->google_api_key, cfg->google_cx_id, max_results);

    char *response = http_get(url, NULL, cfg->timeout_seconds);
    if (!response) return 0;

    int count = parse_google(response, results, max_results);
    free(response);
    return count;
}

/* ── Gemini parse (from pre-fetched response) ── */
static int parse_gemini(const char *response, const char *keyword,
                         evidence_t *results, int max_results) {
    char text[2048];
    text[0] = '\0';

    const char *text_key = strstr(response, "\"text\"");
    if (text_key) {
        text_key += 6;
        while (*text_key && (*text_key == ' ' || *text_key == ':' || *text_key == '"')) text_key++;
        size_t i = 0;
        while (*text_key && *text_key != '"' && i < sizeof(text) - 1) {
            if (*text_key == '\\' && text_key[1]) {
                text_key++;
                if (*text_key == 'n') text[i++] = '\n';
                else text[i++] = *text_key;
            } else {
                text[i++] = *text_key;
            }
            text_key++;
        }
        text[i] = '\0';
    }

    if (text[0]) {
        strncpy(results[0].source, "gemini", sizeof(results[0].source) - 1);
        snprintf(results[0].title, sizeof(results[0].title), "Gemini synthesis: %s", keyword);
        results[0].url[0] = '\0';
        strncpy(results[0].snippet, text, sizeof(results[0].snippet) - 1);
        strcpy(results[0].relevance, "high");
        return 1;
    }
    return 0;
}

/* ── Gemini API search ── */
int discovery_gemini(const char *keyword, discovery_config_t *cfg,
                      evidence_t *results, int max_results) {
    if (!cfg->gemini_api_key[0])
        return 0;

    char url[1024];
    snprintf(url, sizeof(url),
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=%s",
        cfg->gemini_api_key);

    char prompt[1024];
    snprintf(prompt, sizeof(prompt),
        "Search the web and provide a concise summary about: %s. "
        "Include key facts, common patterns, and any important caveats. "
        "Keep it under 500 words.", keyword);

    char body[2048];
    snprintf(body, sizeof(body),
        "{\"contents\":[{\"parts\":[{\"text\":\"%s\"}]}],"
        "\"tools\":[{\"google_search\":{}}]}", prompt);

    char escaped_body[4096];
    const char *src = body;
    char *dst = escaped_body;
    while (*src && dst < escaped_body + sizeof(escaped_body) - 2) {
        if (*src == '\n') { *dst++ = '\\'; *dst++ = 'n'; }
        else *dst++ = *src;
        src++;
    }
    *dst = '\0';

    char *response = http_post_json(url, escaped_body, cfg->timeout_seconds);
    if (!response) return 0;

    int count = parse_gemini(response, keyword, results, max_results);
    free(response);
    return count;
}

/* ── Reddit parse (from pre-fetched response) ── */
static int parse_reddit(const char *response, evidence_t *results, int max_results) {
    int count = 0;
    const char *p = response;

    while (count < max_results) {
        char title[256], permalink[512], selftext[512];
        title[0] = permalink[0] = selftext[0] = '\0';

        if (!discovery_json_extract(p, "title", title, sizeof(title)))
            break;

        const char *next_p = p + 100;
        char search_buf[1024];
        strncpy(search_buf, next_p, sizeof(search_buf) - 1);
        search_buf[sizeof(search_buf) - 1] = '\0';
        discovery_json_extract(search_buf, "permalink", permalink, sizeof(permalink));
        discovery_json_extract(search_buf, "selftext", selftext, sizeof(selftext));

        strncpy(results[count].source, "reddit", sizeof(results[count].source) - 1);
        strncpy(results[count].title, title, sizeof(results[count].title) - 1);
        if (permalink[0])
            snprintf(results[count].url, sizeof(results[count].url),
                "https://reddit.com%s", permalink);
        strncpy(results[count].snippet, selftext[0] ? selftext : title,
            sizeof(results[count].snippet) - 1);
        strcpy(results[count].relevance, "low");

        count++;
        p = strstr(p + 10, "\"title\"");
        if (!p) break;
    }
    return count;
}

/* ── Reddit search ── */
int discovery_reddit(const char *keyword, discovery_config_t *cfg,
                      evidence_t *results, int max_results) {
    char encoded[512];
    discovery_url_encode(keyword, encoded, sizeof(encoded));

    char url[1024];
    snprintf(url, sizeof(url),
        "https://www.reddit.com/search.json?q=%s&limit=%d&sort=relevance",
        encoded, max_results);

    char *response = http_get(url, NULL, cfg->timeout_seconds);
    if (!response) return 0;

    int count = parse_reddit(response, results, max_results);
    free(response);
    return count;
}

/* ── DuckDuckGo parse (from pre-fetched response) ── */
static int parse_duckduckgo(const char *response, evidence_t *results, int max_results) {
    int count = 0;
    const char *p = response;

    while (count < max_results) {
        p = strstr(p, "result__a");
        if (!p) break;

        const char *tag_end = strchr(p, '>');
        if (!tag_end) break;
        tag_end++;

        const char *close_a = strstr(tag_end, "</a>");
        if (!close_a) break;

        size_t tlen = close_a - tag_end;
        if (tlen >= sizeof(results[count].title)) tlen = sizeof(results[count].title) - 1;
        size_t ti = 0;
        for (size_t i = 0; i < tlen && ti < sizeof(results[count].title) - 1; i++) {
            if (tag_end[i] == '<') {
                while (i < tlen && tag_end[i] != '>') i++;
            } else if (tag_end[i] == '&') {
                while (i < tlen && tag_end[i] != ';') i++;
            } else {
                results[count].title[ti++] = tag_end[i];
            }
        }
        results[count].title[ti] = '\0';

        const char *snip_p = strstr(close_a, "result__snippet");
        if (snip_p && snip_p < close_a + 2000) {
            const char *snip_tag = strchr(snip_p, '>');
            if (snip_tag) {
                snip_tag++;
                const char *snip_end = strstr(snip_tag, "</a>");
                if (snip_end) {
                    size_t slen = snip_end - snip_tag;
                    if (slen >= sizeof(results[count].snippet)) slen = sizeof(results[count].snippet) - 1;
                    size_t si = 0;
                    for (size_t i = 0; i < slen && si < sizeof(results[count].snippet) - 1; i++) {
                        if (snip_tag[i] == '<') {
                            while (i < slen && snip_tag[i] != '>') i++;
                        } else if (snip_tag[i] == '&') {
                            while (i < slen && snip_tag[i] != ';') i++;
                        } else {
                            results[count].snippet[si++] = snip_tag[i];
                        }
                    }
                    results[count].snippet[si] = '\0';
                }
            }
        }

        const char *href_p = strstr(p, "href=\"");
        if (href_p && href_p < tag_end) {
            href_p += 6;
            const char *href_end = strchr(href_p, '"');
            if (href_end && href_end - href_p < sizeof(results[count].url)) {
                const char *uddg = strstr(href_p, "uddg=");
                if (uddg) {
                    uddg += 5;
                    const char *uddg_end = strchr(uddg, '&');
                    if (!uddg_end) uddg_end = href_end;
                    size_t ulen = uddg_end - uddg;
                    if (ulen >= sizeof(results[count].url)) ulen = sizeof(results[count].url) - 1;
                    strncpy(results[count].url, uddg, ulen);
                    results[count].url[ulen] = '\0';
                } else {
                    size_t ulen = href_end - href_p;
                    if (ulen >= sizeof(results[count].url)) ulen = sizeof(results[count].url) - 1;
                    strncpy(results[count].url, href_p, ulen);
                    results[count].url[ulen] = '\0';
                }
            }
        }

        strncpy(results[count].source, "duckduckgo", sizeof(results[count].source) - 1);
        strcpy(results[count].relevance, "medium");

        count++;
        p = close_a + 4;
    }
    return count;
}

/* ── DuckDuckGo search (FREE, no API key) ── */
int discovery_duckduckgo(const char *keyword, discovery_config_t *cfg,
                          evidence_t *results, int max_results) {
    char encoded[512];
    discovery_url_encode(keyword, encoded, sizeof(encoded));

    char url[1024];
    snprintf(url, sizeof(url),
        "https://html.duckduckgo.com/html/?q=%s", encoded);

    char *response = http_get(url, NULL, cfg->timeout_seconds);
    if (!response) return 0;

    int count = parse_duckduckgo(response, results, max_results);
    free(response);
    return count;
}

/* ── Wikipedia parse (from pre-fetched response) ── */
static int parse_wikipedia(const char *response, evidence_t *results, int max_results) {
    int count = 0;
    const char *p = response;

    while (count < max_results) {
        char title[256], snippet[512];
        title[0] = snippet[0] = '\0';

        if (!discovery_json_extract(p, "title", title, sizeof(title)))
            break;

        const char *after_title = p + 10;
        char search_buf[1024];
        strncpy(search_buf, after_title, sizeof(search_buf) - 1);
        search_buf[sizeof(search_buf) - 1] = '\0';
        discovery_json_extract(search_buf, "snippet", snippet, sizeof(snippet));

        char clean_snippet[512];
        size_t ci = 0;
        for (size_t i = 0; snippet[i] && ci < sizeof(clean_snippet) - 1; i++) {
            if (snippet[i] == '<') {
                while (snippet[i] && snippet[i] != '>') i++;
            } else {
                clean_snippet[ci++] = snippet[i];
            }
        }
        clean_snippet[ci] = '\0';

        strncpy(results[count].source, "wikipedia", sizeof(results[count].source) - 1);
        strncpy(results[count].title, title, sizeof(results[count].title) - 1);
        snprintf(results[count].url, sizeof(results[count].url),
            "https://en.wikipedia.org/wiki/%s", title);
        strncpy(results[count].snippet, clean_snippet, sizeof(results[count].snippet) - 1);
        strcpy(results[count].relevance, "high");

        count++;
        p = strstr(p + 10, "\"title\"");
        if (!p) break;
    }
    return count;
}

/* ── Wikipedia search (FREE, no API key) ── */
int discovery_wikipedia(const char *keyword, discovery_config_t *cfg,
                         evidence_t *results, int max_results) {
    char encoded[512];
    discovery_url_encode(keyword, encoded, sizeof(encoded));

    char url[1024];
    snprintf(url, sizeof(url),
        "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=%s&format=json&srlimit=%d",
        encoded, max_results);

    char *response = http_get(url, NULL, cfg->timeout_seconds);
    if (!response) return 0;

    int count = parse_wikipedia(response, results, max_results);
    free(response);
    return count;
}

/* ── Main entry: discover from all external sources ── */
int discovery_all(const char *keyword, discovery_config_t *cfg) {
    int total = 0;
    int max_per_source = cfg->max_results;
    evidence_t *results = malloc(sizeof(evidence_t) * max_per_source);
    if (!results) return 0;

    printf("══════ EXTERNAL DISCOVERY ══════\n");
    printf("  Querying external sources for: \"%s\"\n\n", keyword);

    /* GitHub */
    {
        memset(results, 0, sizeof(evidence_t) * max_per_source);
        int n = discovery_github(keyword, cfg, results, max_per_source);
        if (n > 0) {
            printf("  ── GitHub (%d results) ──\n", n);
            for (int i = 0; i < n; i++) {
                evidence_print(&results[i]);
                total++;
            }
            printf("\n");
        } else {
            printf("  ── GitHub: no results or unavailable ──\n\n");
        }
    }

    /* Stack Overflow */
    {
        memset(results, 0, sizeof(evidence_t) * max_per_source);
        int n = discovery_stackoverflow(keyword, cfg, results, max_per_source);
        if (n > 0) {
            printf("  ── Stack Overflow (%d results) ──\n", n);
            for (int i = 0; i < n; i++) {
                evidence_print(&results[i]);
                total++;
            }
            printf("\n");
        } else {
            printf("  ── Stack Overflow: no results or unavailable ──\n\n");
        }
    }

    /* Google (requires API key) */
    if (cfg->google_api_key[0]) {
        memset(results, 0, sizeof(evidence_t) * max_per_source);
        int n = discovery_google(keyword, cfg, results, max_per_source);
        if (n > 0) {
            printf("  ── Google (%d results) ──\n", n);
            for (int i = 0; i < n; i++) {
                evidence_print(&results[i]);
                total++;
            }
            printf("\n");
        } else {
            printf("  ── Google: no results ──\n\n");
        }
    } else {
        printf("  ── Google: skipped (set GOOGLE_API_KEY + GOOGLE_CX_ID) ──\n\n");
    }

    /* Gemini (requires API key) */
    if (cfg->gemini_api_key[0]) {
        memset(results, 0, sizeof(evidence_t) * max_per_source);
        int n = discovery_gemini(keyword, cfg, results, max_per_source);
        if (n > 0) {
            printf("  ── Gemini synthesis ──\n");
            for (int i = 0; i < n; i++) {
                evidence_print(&results[i]);
                total++;
            }
            printf("\n");
        } else {
            printf("  ── Gemini: no response ──\n\n");
        }
    } else {
        printf("  ── Gemini: skipped (set GEMINI_API_KEY) ──\n\n");
    }

    /* Reddit */
    {
        memset(results, 0, sizeof(evidence_t) * max_per_source);
        int n = discovery_reddit(keyword, cfg, results, max_per_source);
        if (n > 0) {
            printf("  ── Reddit (%d results) ──\n", n);
            for (int i = 0; i < n; i++) {
                evidence_print(&results[i]);
                total++;
            }
            printf("\n");
        } else {
            printf("  ── Reddit: no results or unavailable ──\n\n");
        }
    }

    free(results);

    printf("  EXTERNAL DISCOVERY SUMMARY: %d evidence packets from 5 sources\n", total);
    printf("\n");

    return total;
}

/* ═══════════════════════════════════════════════════════════════
 * CANDIDATE COMPRESSION LAYER
 *
 * External layer proposes. Magnetic layer verifies.
 *
 * Takes raw evidence → extracts terms → scores → deduplicates
 * → returns top N high-signal entry points for magnetic expansion.
 * ═══════════════════════════════════════════════════════════════ */

/* Stop words — filtered out during term extraction */
static const char *stop_words[] = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "must", "can",
    "this", "that", "these", "those", "i", "you", "he", "she", "it",
    "we", "they", "what", "which", "who", "when", "where", "why", "how",
    "all", "each", "every", "both", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so",
    "than", "too", "very", "just", "also", "into", "from", "with",
    "for", "about", "in", "on", "at", "to", "of", "by", "as", "at",
    "if", "then", "else", "up", "out", "off", "over", "under",
    "how", "use", "using", "used", "get", "set", "new", "one", "two",
    "like", "need", "want", "try", "make", "made", "way", "thing",
    "things", "help", "problem", "issue", "error", "warning", NULL
};

static int is_stop_word(const char *word) {
    for (int i = 0; stop_words[i]; i++) {
        if (strcasecmp(word, stop_words[i]) == 0)
            return 1;
    }
    return 0;
}

/* Check if term contains the original keyword (substring) */
static int contains_keyword(const char *term, const char *keyword) {
    if (!term || !keyword) return 0;
    return strcasestr(term, keyword) != NULL;
}

/* Extract terms from a text string (simple whitespace + punctuation tokenizer) */
static int extract_terms(const char *text, char terms[][MAX_TERM_LEN], int max_terms) {
    int count = 0;
    const char *p = text;

    while (*p && count < max_terms) {
        /* Skip non-alphanumeric */
        while (*p && !isalnum(*p) && *p != '_' && *p != '-') p++;
        if (!*p) break;

        /* Extract word */
        char word[MAX_TERM_LEN];
        int wlen = 0;
        while (*p && (isalnum(*p) || *p == '_' || *p == '-') && wlen < MAX_TERM_LEN - 1) {
            word[wlen++] = tolower(*p);
            p++;
        }
        word[wlen] = '\0';

        /* Filter: skip stop words, too short (<3), too long (>40) */
        if (wlen >= 3 && wlen <= 40 && !is_stop_word(word)) {
            strncpy(terms[count], word, MAX_TERM_LEN - 1);
            terms[count][MAX_TERM_LEN - 1] = '\0';
            count++;
        }
    }

    return count;
}

/* Compress evidence into entry points */
int discovery_compress(evidence_t *evidence, int ev_count,
                            const char *keyword,
                            entry_point_t *out_points, int max_points) {
    if (ev_count == 0 || !evidence || !out_points || max_points <= 0)
        return 0;

    /* Collect all terms from all evidence */
    char all_terms[MAX_EVIDENCE_POOL * 20][MAX_TERM_LEN];
    char term_sources[MAX_EVIDENCE_POOL * 20][32]; /* which source each term came from */
    int total_terms = 0;

    for (int i = 0; i < ev_count && total_terms < MAX_EVIDENCE_POOL * 20; i++) {
        /* Extract from title */
        char terms[20][MAX_TERM_LEN];
        int n = extract_terms(evidence[i].title, terms, 20);
        for (int j = 0; j < n && total_terms < MAX_EVIDENCE_POOL * 20; j++) {
            strncpy(all_terms[total_terms], terms[j], MAX_TERM_LEN - 1);
            all_terms[total_terms][MAX_TERM_LEN - 1] = '\0';
            strncpy(term_sources[total_terms], evidence[i].source, 31);
            term_sources[total_terms][31] = '\0';
            total_terms++;
        }

        /* Extract from snippet */
        n = extract_terms(evidence[i].snippet, terms, 20);
        for (int j = 0; j < n && total_terms < MAX_EVIDENCE_POOL * 20; j++) {
            strncpy(all_terms[total_terms], terms[j], MAX_TERM_LEN - 1);
            all_terms[total_terms][MAX_TERM_LEN - 1] = '\0';
            strncpy(term_sources[total_terms], evidence[i].source, 31);
            term_sources[total_terms][31] = '\0';
            total_terms++;
        }
    }

    /* Deduplicate and count: frequency + source diversity */
    entry_point_t points[MAX_EVIDENCE_POOL * 20];
    int point_count = 0;

    for (int i = 0; i < total_terms; i++) {
        /* Check if term already exists in points */
        int found = -1;
        for (int j = 0; j < point_count; j++) {
            if (strcmp(all_terms[i], points[j].term) == 0) {
                found = j;
                break;
            }
        }

        if (found >= 0) {
            points[found].frequency++;
            /* Check if this source is new for this term */
            int source_exists = 0;
            /* We can't easily track per-term sources without more memory,
             * so we approximate: if the source string differs from the last
             * one we saw for this term, increment source_count.
             * This is an approximation but good enough for scoring. */
            if (i > 0 && strcmp(term_sources[i], term_sources[i-1]) != 0) {
                /* Double-check: is this source already counted? */
                /* Simple heuristic: just count unique source transitions */
                source_exists = 0;
                for (int k = found + 1; k < i; k++) {
                    if (strcmp(all_terms[k], points[found].term) == 0 &&
                        strcmp(term_sources[k], term_sources[i]) == 0) {
                        source_exists = 1;
                        break;
                    }
                }
                if (!source_exists) {
                    points[found].source_count++;
                }
            }
        } else if (point_count < MAX_EVIDENCE_POOL * 20) {
            strncpy(points[point_count].term, all_terms[i], MAX_TERM_LEN - 1);
            points[point_count].term[MAX_TERM_LEN - 1] = '\0';
            points[point_count].frequency = 1;
            points[point_count].source_count = 1;
            point_count++;
        }
    }

    /* Score each term:
     *   score = frequency + source_count * 3 + keyword_match * 5
     */
    for (int i = 0; i < point_count; i++) {
        points[i].score = points[i].frequency + points[i].source_count * 3;
        if (contains_keyword(points[i].term, keyword))
            points[i].score += 5;
        /* Length penalty: very short or very long terms are noise */
        int tlen = strlen(points[i].term);
        if (tlen < 4) points[i].score -= 2;
        if (tlen > 30) points[i].score -= 3;
    }

    /* Sort by score descending (simple selection sort — N is small) */
    for (int i = 0; i < point_count - 1; i++) {
        int best = i;
        for (int j = i + 1; j < point_count; j++) {
            if (points[j].score > points[best].score)
                best = j;
        }
        if (best != i) {
            entry_point_t tmp = points[i];
            points[i] = points[best];
            points[best] = tmp;
        }
    }

    /* Copy top N to output */
    int result_count = point_count < max_points ? point_count : max_points;
    for (int i = 0; i < result_count; i++) {
        out_points[i] = points[i];
    }

    return result_count;
}

/* Print entry points */
void entry_points_print(entry_point_t *points, int count) {
    printf("══════ CANDIDATE COMPRESSION ══════\n");
    printf("  External evidence compressed into %d entry points:\n\n", count);

    for (int i = 0; i < count; i++) {
        /* Visual bar based on score (max 20 chars) */
        int bar_len = points[i].score;
        if (bar_len > 20) bar_len = 20;
        if (bar_len < 1) bar_len = 1;

        printf("  [%d] %-30s  score=%-3d  freq=%-3d  sources=%d  ",
            i + 1,
            points[i].term,
            points[i].score,
            points[i].frequency,
            points[i].source_count);

        for (int b = 0; b < bar_len; b++) putchar('#');
        printf("\n");
    }

    printf("\n  ── Compression verdict ──\n");
    if (count == 0) {
        printf("  No entry points — external sources returned no signal\n");
    } else if (count <= 3) {
        printf("  TIGHT compression — %d high-signal entry points\n", count);
    } else if (count <= 7) {
        printf("  GOOD compression — %d entry points for magnetic expansion\n", count);
    } else {
        printf("  LOOSE compression — %d entry points (consider tightening)\n", count);
    }
    printf("\n");
}

/* Full pipeline: discover + compress — PARALLEL version using curl_multi */
int discovery_and_compress(const char *keyword, discovery_config_t *cfg) {
    evidence_t pool[MAX_EVIDENCE_POOL];
    memset(pool, 0, sizeof(pool));
    int pool_count = 0;
    int max_per_source = cfg->max_results;
    char encoded[512];
    discovery_url_encode(keyword, encoded, sizeof(encoded));

    /* Step 1: Build all source URLs */
    enum { SLOT_GITHUB, SLOT_SO, SLOT_GOOGLE, SLOT_GEMINI,
           SLOT_REDDIT, SLOT_DDG, SLOT_WIKI, NSLOTS };
    struct source_slot slots[NSLOTS];
    memset(slots, 0, sizeof(slots));

    /* GitHub */
    snprintf(slots[SLOT_GITHUB].url, sizeof(slots[SLOT_GITHUB].url),
        "https://api.github.com/search/repositories?q=%s&sort=stars&order=desc&per_page=%d",
        encoded, max_per_source);
    if (cfg->github_token[0])
        snprintf(slots[SLOT_GITHUB].auth_header, sizeof(slots[SLOT_GITHUB].auth_header),
            "Authorization: token %s", cfg->github_token);
    slots[SLOT_GITHUB].active = 1;

    /* Stack Overflow */
    snprintf(slots[SLOT_SO].url, sizeof(slots[SLOT_SO].url),
        "https://api.stackexchange.com/2.3/search/advanced?order=desc&sort=relevance&q=%s&site=stackoverflow&pagesize=%d",
        encoded, max_per_source);
    slots[SLOT_SO].active = 1;

    /* Google (if configured) */
    if (cfg->google_api_key[0] && cfg->google_cx_id[0]) {
        snprintf(slots[SLOT_GOOGLE].url, sizeof(slots[SLOT_GOOGLE].url),
            "https://www.googleapis.com/customsearch/v1?key=%s&cx=%s&q=%s&num=%d",
            cfg->google_api_key, cfg->google_cx_id, encoded, max_per_source);
        slots[SLOT_GOOGLE].active = 1;
    }

    /* Gemini (if configured) — POST request */
    if (cfg->gemini_api_key[0]) {
        snprintf(slots[SLOT_GEMINI].url, sizeof(slots[SLOT_GEMINI].url),
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=%s",
            cfg->gemini_api_key);
        snprintf(slots[SLOT_GEMINI].post_body, sizeof(slots[SLOT_GEMINI].post_body),
            "{\"contents\":[{\"parts\":[{\"text\":\"Search for information about: %s. Provide key facts, relevant URLs, and important technical details.\"}]}],\"tools\":[{\"google_search\":{}}]}",
            keyword);
        slots[SLOT_GEMINI].active = 1;
        slots[SLOT_GEMINI].is_post = 1;
    }

    /* Reddit */
    snprintf(slots[SLOT_REDDIT].url, sizeof(slots[SLOT_REDDIT].url),
        "https://www.reddit.com/search.json?q=%s&limit=%d", encoded, max_per_source);
    slots[SLOT_REDDIT].active = 1;

    /* DuckDuckGo */
    snprintf(slots[SLOT_DDG].url, sizeof(slots[SLOT_DDG].url),
        "https://html.duckduckgo.com/html/?q=%s", encoded);
    slots[SLOT_DDG].active = 1;

    /* Wikipedia */
    snprintf(slots[SLOT_WIKI].url, sizeof(slots[SLOT_WIKI].url),
        "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=%s&format=json&srlimit=%d",
        encoded, max_per_source);
    slots[SLOT_WIKI].active = 1;

    /* Step 2: Fire all requests in parallel via curl_multi */
    parallel_fetch(slots, NSLOTS, cfg->timeout_seconds);

    /* Step 3: Parse each response */
    for (int s = 0; s < NSLOTS && pool_count < MAX_EVIDENCE_POOL; s++) {
        if (!slots[s].active || !slots[s].buf.data || slots[s].buf.size == 0)
            continue;

        char *resp = slots[s].buf.data;
        int room = MAX_EVIDENCE_POOL - pool_count;
        int n = 0;

        switch (s) {
        case SLOT_GITHUB:
            n = parse_github(resp, &pool[pool_count], room);
            break;
        case SLOT_SO:
            n = parse_stackoverflow(resp, &pool[pool_count], room);
            break;
        case SLOT_GOOGLE:
            n = parse_google(resp, &pool[pool_count], room);
            break;
        case SLOT_GEMINI:
            n = parse_gemini(resp, keyword, &pool[pool_count], room);
            break;
        case SLOT_REDDIT:
            n = parse_reddit(resp, &pool[pool_count], room);
            break;
        case SLOT_DDG:
            n = parse_duckduckgo(resp, &pool[pool_count], room);
            break;
        case SLOT_WIKI:
            n = parse_wikipedia(resp, &pool[pool_count], room);
            break;
        }
        pool_count += n;
    }

    /* Free all response buffers */
    for (int s = 0; s < NSLOTS; s++) {
        if (slots[s].buf.data) free(slots[s].buf.data);
    }

    if (pool_count == 0) {
        printf("══════ CANDIDATE COMPRESSION ══════\n");
        printf("  No external evidence collected — all sources unavailable\n\n");
        return 0;
    }

    /* Step 2: Print raw evidence summary (compact) */
    printf("══════ EXTERNAL DISCOVERY (raw) ══════\n");
    printf("  Collected %d evidence packets from external sources\n", pool_count);
    for (int i = 0; i < pool_count; i++) {
        printf("  [%s] %s\n", pool[i].source, pool[i].title);
    }
    printf("\n");

    /* Step 3: Compress into entry points */
    entry_point_t points[MAX_ENTRY_POINTS];
    int ep_count = discovery_compress(pool, pool_count, keyword,
        points, MAX_ENTRY_POINTS);

    /* Step 4: Print compressed entry points */
    entry_points_print(points, ep_count);

    return ep_count;
}
