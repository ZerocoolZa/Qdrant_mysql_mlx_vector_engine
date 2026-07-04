//[@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_search_web.c" date="2026-07-04" author="Devin" session_id="bcl-search-units" context="BCL unit for web/URL search. Source: online URLs. Pipeline: URL input -> HTTP fetch (raw socket) -> HTML parse -> boilerplate strip -> text extract -> BCL output. No MySQL. No libcurl."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//[@FILEID]{id="bcl_search_web.c" domain="cascade_tools" authority="SearchWeb"}
//[@SUMMARY]{summary="Web search unit. Source = online URLs. Owns full pipeline: URL parse, HTTP GET (raw socket), HTML tag strip, text extract, BCL output. Commands: fetch, read_url, search_web, read_state, set_config. No MySQL."}
//[@CLASS]{class="SearchWeb" domain="cascade_tools" authority="single"}
//[@METHOD]{method="Init" type="command"}
//[@METHOD]{method="Run" type="dispatch"}
//[@METHOD]{method="Close" type="command"}
//[@METHOD]{method="State" type="query"}
//[@METHOD]{method="ParseUrl" type="internal"}
//[@METHOD]{method="HttpGet" type="internal"}
//[@METHOD]{method="HtmlToText" type="internal"}
//[@REVIEW]{[@date<2026-07-04>][@reviewer<devin>][@status<implementation>][@notes<Web search BCL unit. Raw socket HTTP/1.0 GET. HTML tag/script/style strip. Entity decode. No external HTTP library.>][@todos<add HTTPS support via OpenSSL if needed>]}

/*
 * bcl_search_web.c — Web/URL search BCL unit
 *
 * BCL IN:  [@RUN]{[@CMD]{fetch}[@URL]{http://example.com/page}}
 *          [@RUN]{[@CMD]{read_url}[@URL]{http://example.com/page}}
 *          [@RUN]{[@CMD]{search_web}[@QUERY]{foo}[@URL]{http://example.com/page}}
 *          [@RUN]{[@CMD]{read_state}}
 *          [@RUN]{[@CMD]{set_config}[@TIMEOUT]{10}[@MAXBYTES]{65536}}
 * BCL OUT: [@OK]{[@URL]{...}[@STATUS]{200}[@BYTES]{N}[@TEXT]{...}}
 * BCL ERR: [@ERR]{[@CODE]{N}[@DESC]{...}}
 */

#include "bcl_toolstack.h"
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>
#include <unistd.h>
#include <errno.h>

/* ===== DIM BLOCK ===== */

#define SEARCHWEB_MAX_URL       2048
#define SEARCHWEB_MAX_HOST      256
#define SEARCHWEB_MAX_PATH      2048
#define SEARCHWEB_MAX_QUERY     1024
#define SEARCHWEB_MAX_BYTES     262144
#define SEARCHWEB_DEFAULT_TIMEOUT  10
#define SEARCHWEB_DEFAULT_MAXBYTES 65536
#define SEARCHWEB_RECV_CHUNK    8192

/* State */
static struct {
    int initialized;
    int timeout_sec;
    int max_bytes;
    int strip_scripts;
    int strip_styles;
    int fetches_run;
    int bytes_fetched;
    int pages_parsed;
    int last_status;
    char last_url[SEARCHWEB_MAX_URL];
    char last_error[256];
} STATE;

/* ===== PARSE URL — split into host, port, path ===== */

static int web_parse_url(const char *url, char *host, size_t host_sz,
                         int *port, char *path, size_t path_sz) {
    const char *p = url;
    if (strncasecmp(p, "http://", 7) == 0) {
        p += 7;
        *port = 80;
    } else if (strncasecmp(p, "https://", 8) == 0) {
        return -1; /* raw socket HTTPS not supported */
    } else {
        *port = 80;
    }
    size_t hi = 0;
    while (*p && *p != '/' && *p != ':' && hi < host_sz - 1) {
        host[hi++] = *p++;
    }
    host[hi] = '\0';
    if (*p == ':') {
        p++;
        int pt = 0;
        while (*p >= '0' && *p <= '9') { pt = pt * 10 + (*p - '0'); p++; }
        if (pt > 0) *port = pt;
    }
    if (*p == '/') {
        strncpy(path, p, path_sz - 1);
        path[path_sz - 1] = '\0';
    } else {
        strncpy(path, "/", path_sz - 1);
        path[path_sz - 1] = '\0';
    }
    return 1;
}

/* ===== HTTP GET — raw socket, returns total bytes or -1 ===== */

static int web_http_get(const char *host, int port, const char *path,
                        char *buf, size_t buf_sz, int timeout_sec,
                        int *http_status, char *err, size_t err_sz) {
    struct hostent *he = gethostbyname(host);
    if (!he) { snprintf(err, err_sz, "DNS failed for %s", host); return -1; }

    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) { snprintf(err, err_sz, "socket() failed"); return -1; }

    struct timeval tv;
    tv.tv_sec = timeout_sec;
    tv.tv_usec = 0;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    memcpy(&addr.sin_addr, he->h_addr_list[0], he->h_length);

    if (connect(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        snprintf(err, err_sz, "connect failed: %s", strerror(errno));
        close(sock);
        return -1;
    }

    char request[2048];
    int reqlen = snprintf(request, sizeof(request),
        "GET %s HTTP/1.0\r\nHost: %s\r\nUser-Agent: bcl_search_web/1.0\r\n"
        "Accept: text/html,*/*;q=0.8\r\nConnection: close\r\n\r\n",
        path, host);
    if (write(sock, request, reqlen) != reqlen) {
        snprintf(err, err_sz, "write failed");
        close(sock);
        return -1;
    }

    size_t total = 0;
    ssize_t n;
    while (total < buf_sz - 1 &&
           (n = read(sock, buf + total, buf_sz - 1 - total)) > 0) {
        total += n;
    }
    buf[total] = '\0';
    close(sock);

    *http_status = 0;
    if (total > 12 && strncmp(buf, "HTTP/", 5) == 0) {
        const char *sp = strchr(buf, ' ');
        if (sp) *http_status = atoi(sp + 1);
    }
    return (int)total;
}

/* ===== FIND BODY — skip HTTP headers ===== */

static const char *web_find_body(const char *resp) {
    const char *b = strstr(resp, "\r\n\r\n");
    if (b) return b + 4;
    b = strstr(resp, "\n\n");
    if (b) return b + 2;
    return resp;
}

/* ===== HTML TO TEXT — strip tags, scripts, styles, decode entities ===== */

static int web_html_to_text(const char *html, char *out, size_t out_sz,
                            int strip_scripts, int strip_styles) {
    size_t oi = 0;
    const char *p = html;
    int in_tag = 0;
    int in_script = 0;
    int in_style = 0;

    while (*p && oi < out_sz - 2) {
        if (!in_tag && strncasecmp(p, "<script", 7) == 0 && strip_scripts) {
            in_script = 1; in_tag = 1; p += 7; continue;
        }
        if (!in_tag && strncasecmp(p, "<style", 6) == 0 && strip_styles) {
            in_style = 1; in_tag = 1; p += 6; continue;
        }
        if (*p == '<') { in_tag = 1; p++; continue; }
        if (*p == '>' && in_tag) {
            in_tag = 0; p++;
            if (oi > 0 && out[oi - 1] != ' ' && out[oi - 1] != '\n' && !in_script && !in_style)
                out[oi++] = ' ';
            continue;
        }
        if (in_tag) {
            if (in_script && strncasecmp(p, "/script>", 8) == 0) { in_script = 0; in_tag = 0; p += 8; continue; }
            if (in_style && strncasecmp(p, "/style>", 7) == 0) { in_style = 0; in_tag = 0; p += 7; continue; }
            p++;
            continue;
        }
        if (in_script || in_style) { p++; continue; }

        if (*p == '&') {
            if (strncasecmp(p, "&nbsp;", 6) == 0) { out[oi++] = ' '; p += 6; continue; }
            if (strncasecmp(p, "&amp;", 5) == 0)  { out[oi++] = '&'; p += 5; continue; }
            if (strncasecmp(p, "&lt;", 4) == 0)   { out[oi++] = '<'; p += 4; continue; }
            if (strncasecmp(p, "&gt;", 4) == 0)   { out[oi++] = '>'; p += 4; continue; }
            if (strncasecmp(p, "&quot;", 6) == 0) { out[oi++] = '"'; p += 6; continue; }
            if (strncasecmp(p, "&#39;", 5) == 0)  { out[oi++] = '\''; p += 5; continue; }
        }
        if (*p == '\r' || *p == '\t') { out[oi++] = ' '; p++; continue; }
        if (*p == '\n') {
            if (oi > 0 && out[oi - 1] != '\n') out[oi++] = '\n';
            p++; continue;
        }
        out[oi++] = *p++;
    }
    while (oi > 0 && (out[oi - 1] == ' ' || out[oi - 1] == '\n')) oi--;
    out[oi] = '\0';
    return (int)oi;
}

/* ===== CLEAN FOR BCL ===== */

static void web_clean_for_bcl(const char *in, char *out, int out_sz) {
    int ci = 0;
    for (int i = 0; in[i] && ci < out_sz - 1; i++) {
        char ch = in[i];
        if (ch == '{' || ch == '}') out[ci++] = ' ';
        else if (ch == '[' && in[i + 1] == '@') out[ci++] = ' ';
        else out[ci++] = ch;
    }
    out[ci] = '\0';
}

/* ===== UNIT INTERFACE ===== */

int SearchWeb_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.timeout_sec = SEARCHWEB_DEFAULT_TIMEOUT;
    STATE.max_bytes = SEARCHWEB_DEFAULT_MAXBYTES;
    STATE.strip_scripts = 1;
    STATE.strip_styles = 1;
    STATE.initialized = 1;
    return 1;
}

int SearchWeb_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) SearchWeb_Init();
    STATE.fetches_run++;

    /* ===== READ_STATE ===== */
    if (strcmp(cmd, "read_state") == 0) {
        return BclResult_Ok(bcl_out, out_sz,
            "[@INITIALIZED]{1}[@FETCHES]{...}[@BYTES]{...}[@PAGES]{...}");
    }

    /* ===== SET_CONFIG ===== */
    if (strcmp(cmd, "set_config") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char to[16] = {0};
        char mb[16] = {0};
        BclParser_Extract(&parse, "TIMEOUT", to, sizeof(to));
        BclParser_Extract(&parse, "MAXBYTES", mb, sizeof(mb));
        BclParser_Free(&parse);
        if (to[0]) STATE.timeout_sec = atoi(to);
        if (mb[0]) STATE.max_bytes = atoi(mb);
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }

    /* ===== FETCH / READ_URL / SEARCH_WEB ===== */
    if (strcmp(cmd, "fetch") == 0 || strcmp(cmd, "read_url") == 0 ||
        strcmp(cmd, "search_web") == 0) {
        BclParseResult parse;
        BclParser_Init(&parse);
        BclParser_Parse(&parse, bcl_in);
        char url[SEARCHWEB_MAX_URL] = {0};
        char query[SEARCHWEB_MAX_QUERY] = {0};
        BclParser_Extract(&parse, "URL", url, sizeof(url));
        BclParser_Extract(&parse, "QUERY", query, sizeof(query));
        BclParser_Free(&parse);
        if (!url[0]) {
            return BclResult_Err(bcl_out, out_sz, 20, "no URL in packet");
        }

        char host[SEARCHWEB_MAX_HOST] = {0};
        char path[SEARCHWEB_MAX_PATH] = {0};
        int port = 80;
        int pr = web_parse_url(url, host, sizeof(host), &port, path, sizeof(path));
        if (pr < 0) {
            return BclResult_Err(bcl_out, out_sz, 30,
                "HTTPS not supported; use http:// URLs");
        }
        if (pr == 0) {
            return BclResult_Err(bcl_out, out_sz, 31, "malformed URL");
        }

        int maxb = STATE.max_bytes;
        if (maxb <= 0 || maxb > SEARCHWEB_MAX_BYTES) maxb = SEARCHWEB_MAX_BYTES;
        char *raw = (char *)malloc(maxb + 1);
        if (!raw) return BclResult_Err(bcl_out, out_sz, 32, "out of memory");

        int status = 0;
        int got = web_http_get(host, port, path, raw, maxb + 1,
            STATE.timeout_sec, &status,
            STATE.last_error, sizeof(STATE.last_error));
        if (got < 0) {
            free(raw);
            return BclResult_Err(bcl_out, out_sz, 33, STATE.last_error);
        }

        STATE.last_status = status;
        STATE.bytes_fetched += got;

        const char *body = web_find_body(raw);
        char *text = (char *)malloc(maxb + 1);
        if (!text) { free(raw); return BclResult_Err(bcl_out, out_sz, 32, "oom"); }
        int tlen = web_html_to_text(body, text, maxb + 1,
            STATE.strip_scripts, STATE.strip_styles);
        STATE.pages_parsed++;
        free(raw);

        int matches = 0;
        if (strcmp(cmd, "search_web") == 0 && query[0]) {
            const char *tp = text;
            while ((tp = strcasestr(tp, query)) != NULL) {
                matches++;
                tp += strlen(query);
            }
        }

        char *clean = (char *)malloc(maxb + 1);
        if (!clean) { free(text); return BclResult_Err(bcl_out, out_sz, 32, "oom"); }
        web_clean_for_bcl(text, clean, maxb + 1);
        free(text);

        int show_len = tlen;
        if (show_len > (int)out_sz - 512) show_len = (int)out_sz - 512;
        if (show_len < 0) show_len = 0;
        clean[show_len] = '\0';

        snprintf(bcl_out, out_sz,
            "[@OK]{[@URL]{%s}[@STATUS]{%d}[@BYTES]{%d}[@TEXTLEN]{%d}[@MATCHES]{%d}[@TEXT]{%.4000s}}",
            url, status, got, tlen, matches, clean);
        free(clean);

        strncpy(STATE.last_url, url, sizeof(STATE.last_url) - 1);
        return 1;
    }

    return BclResult_Err(bcl_out, out_sz, 40, "unknown command");
}

int SearchWeb_Close(void) {
    STATE.initialized = 0;
    return 1;
}

const char * SearchWeb_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "SearchWeb: initialized=%d fetches=%d bytes=%d pages=%d last_status=%d",
        STATE.initialized, STATE.fetches_run, STATE.bytes_fetched,
        STATE.pages_parsed, STATE.last_status);
    return buf;
}
