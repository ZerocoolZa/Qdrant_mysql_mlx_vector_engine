//@GHOST]{file_path="Cascade_toolStack/bcl_units/bcl_wcmd.c" date="2026-06-29" author="cascade" session_id="bcl-toolstack-units" context="BCL unit - Window command processor. Manages terminal/editor windows via osascript, tmux, or screen."}
//@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//@FILEID]{id="bcl_wcmd.c" domain="cascade_tools" authority="Wcmd"}
//@SUMMARY]{summary="Window command processor. Commands: list_windows, focus, split, close, send_keys, snapshot, read_state, set_config. Backends: osascript (macOS), tmux, screen."}
//@CLASS]{class="Wcmd" domain="cascade_tools" authority="single"}
//@METHOD]{method="Init" type="command"}
//@METHOD]{method="Run" type="dispatch"}
//@METHOD]{method="Close" type="command"}
//@METHOD]{method="State" type="query"}
//@METHOD]{method="list_windows" type="query"}
//@METHOD]{method="focus" type="command"}
//@METHOD]{method="split" type="command"}
//@METHOD]{method="close" type="command"}
//@METHOD]{method="send_keys" type="command"}
//@METHOD]{method="snapshot" type="query"}
//@METHOD]{method="read_state" type="query"}
//@METHOD]{method="set_config" type="command"}

#include "bcl_toolstack.h"

#define WCMD_MAX_SHELL_OUT  8192
#define WCMD_MAX_NAME       256
#define WCMD_MAX_KEYS       2048
#define WCMD_MAX_DIR        16

#define WCMD_TERM_TMUX      1
#define WCMD_TERM_SCREEN    2
#define WCMD_TERM_OSA       3

static struct {
    int  initialized;
    int  commands_run;
    int  windows_managed;
    char last_window[WCMD_MAX_NAME];
    int  terminal_type;
    char default_window[WCMD_MAX_NAME];
    char last_error[256];
} STATE;

/* Run a shell command via popen, capture stdout into out (NUL-terminated).
 * Returns byte count, or -1 on failure. */
static int Wcmd_Shell(const char *cmd, char *out, size_t out_sz) {
    if (!cmd || !out || out_sz < 2) return -1;
    out[0] = '\0';
    FILE *fp = popen(cmd, "r");
    if (!fp) return -1;
    size_t total = 0;
    char chunk[1024];
    while (fgets(chunk, sizeof(chunk), fp)) {
        size_t len = strlen(chunk);
        if (total + len + 1 >= out_sz) {
            len = out_sz - total - 1;
            if (len == 0) break;
        }
        memcpy(out + total, chunk, len);
        total += len;
        out[total] = '\0';
    }
    int rc = pclose(fp);
    if (rc != 0 && total == 0) return -1;
    return (int)total;
}

/* Strip trailing whitespace/newlines in place. */
static void Wcmd_RTrim(char *s) {
    if (!s) return;
    size_t n = strlen(s);
    while (n > 0 && (s[n - 1] == '\n' || s[n - 1] == '\r' ||
                     s[n - 1] == ' '  || s[n - 1] == '\t')) {
        s[--n] = '\0';
    }
}

/* Escape single quotes for safe embedding in a shell single-quoted string. */
static void Wcmd_EscapeSQ(const char *in, char *out, size_t out_sz) {
    if (!in || !out || out_sz < 2) { if (out && out_sz) out[0] = '\0'; return; }
    size_t j = 0;
    for (size_t i = 0; in[i] && j + 4 < out_sz; i++) {
        if (in[i] == '\'') {
            out[j++] = '\''; out[j++] = '\\'; out[j++] = '\''; out[j++] = '\'';
        } else {
            out[j++] = in[i];
        }
    }
    out[j] = '\0';
}

/* Map terminal_type int to display string. */
static const char * Wcmd_TermName(void) {
    if (STATE.terminal_type == WCMD_TERM_TMUX)   return "tmux";
    if (STATE.terminal_type == WCMD_TERM_SCREEN) return "screen";
    return "osascript";
}

int Wcmd_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.terminal_type = WCMD_TERM_OSA;
    STATE.initialized = 1;
    return 1;
}

int Wcmd_Close(void) {
    STATE.initialized = 0;
    return 1;
}

const char * Wcmd_State(void) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
        "Wcmd: initialized=%d commands=%d windows=%d last=%s term=%s",
        STATE.initialized, STATE.commands_run, STATE.windows_managed,
        STATE.last_window[0] ? STATE.last_window : "(none)", Wcmd_TermName());
    return buf;
}

static int Wcmd_ListWindows(char *bcl_out, size_t out_sz) {
    char raw[WCMD_MAX_SHELL_OUT] = {0};
    int got = -1;
    if (STATE.terminal_type == WCMD_TERM_TMUX) {
        got = Wcmd_Shell("tmux list-windows -F '#W' 2>/dev/null", raw, sizeof(raw));
    } else if (STATE.terminal_type == WCMD_TERM_SCREEN) {
        got = Wcmd_Shell("screen -list 2>/dev/null", raw, sizeof(raw));
    } else {
        got = Wcmd_Shell(
            "osascript -e 'tell application \"System Events\" to get name of every window of every process' 2>/dev/null",
            raw, sizeof(raw));
    }
    if (got < 0) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "list backend failed");
        return BclResult_Err(bcl_out, out_sz, 30, "list_windows backend failed");
    }
    Wcmd_RTrim(raw);
    /* Each non-empty line becomes a [@W] entry. */
    char body[WCMD_MAX_SHELL_OUT];
    size_t pos = 0;
    int count = 0;
    body[0] = '\0';
    char *line = raw;
    char *nl;
    while (line && *line) {
        nl = strchr(line, '\n');
        if (nl) *nl = '\0';
        Wcmd_RTrim(line);
        if (*line) {
            int w = snprintf(body + pos, sizeof(body) - pos, "[@W]{%s}", line);
            if (w < 0 || (size_t)w >= sizeof(body) - pos) break;
            pos += (size_t)w;
            count++;
        }
        if (!nl) break;
        line = nl + 1;
    }
    char final[WCMD_MAX_SHELL_OUT];
    snprintf(final, sizeof(final), "[@COUNT]{%d}%s", count, body);
    return BclResult_Ok(bcl_out, out_sz, final);
}

static int Wcmd_Focus(const char *bcl_in, char *bcl_out, size_t out_sz) {
    BclParseResult parse;
    BclParser_Init(&parse);
    BclParser_Parse(&parse, bcl_in);
    char name[WCMD_MAX_NAME] = {0};
    BclParser_Extract(&parse, "NAME", name, sizeof(name));
    BclParser_Free(&parse);
    if (!name[0]) return BclResult_Err(bcl_out, out_sz, 20, "no NAME in packet");

    char esc[WCMD_MAX_NAME * 2] = {0};
    Wcmd_EscapeSQ(name, esc, sizeof(esc));
    char cmd[1024];
    int rc;
    if (STATE.terminal_type == WCMD_TERM_TMUX) {
        snprintf(cmd, sizeof(cmd), "tmux select-window -t '%s' 2>/dev/null", esc);
        rc = system(cmd);
    } else {
        snprintf(cmd, sizeof(cmd),
            "osascript -e 'tell application \"%s\" to activate' -e "
            "'tell application \"System Events\" to set frontmost of process \"%s\" to true' 2>/dev/null",
            esc, esc);
        rc = system(cmd);
    }
    if (rc != 0) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "focus failed: %s", name);
        return BclResult_Err(bcl_out, out_sz, 31, "focus failed");
    }
    strncpy(STATE.last_window, name, sizeof(STATE.last_window) - 1);
    STATE.last_window[sizeof(STATE.last_window) - 1] = '\0';
    char body[512];
    snprintf(body, sizeof(body), "[@STATUS]{focused}[@NAME]{%s}", name);
    return BclResult_Ok(bcl_out, out_sz, body);
}

static int Wcmd_Split(const char *bcl_in, char *bcl_out, size_t out_sz) {
    BclParseResult parse;
    BclParser_Init(&parse);
    BclParser_Parse(&parse, bcl_in);
    char dir[WCMD_MAX_DIR] = {0};
    BclParser_Extract(&parse, "DIRECTION", dir, sizeof(dir));
    BclParser_Free(&parse);
    if (!dir[0]) return BclResult_Err(bcl_out, out_sz, 20, "no DIRECTION in packet");
    if (strcmp(dir, "horizontal") != 0 && strcmp(dir, "vertical") != 0) {
        return BclResult_Err(bcl_out, out_sz, 21, "DIRECTION must be horizontal or vertical");
    }
    if (STATE.terminal_type != WCMD_TERM_TMUX) {
        return BclResult_Err(bcl_out, out_sz, 40, "split requires tmux backend");
    }
    const char *flag = (strcmp(dir, "vertical") == 0) ? "-v" : "-h";
    char cmd[256];
    snprintf(cmd, sizeof(cmd), "tmux split-window %s 2>/dev/null", flag);
    if (system(cmd) != 0) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "split failed");
        return BclResult_Err(bcl_out, out_sz, 32, "split failed");
    }
    STATE.windows_managed++;
    char body[256];
    snprintf(body, sizeof(body), "[@STATUS]{split}[@DIRECTION]{%s}", dir);
    return BclResult_Ok(bcl_out, out_sz, body);
}

static int Wcmd_CloseWindow(const char *bcl_in, char *bcl_out, size_t out_sz) {
    BclParseResult parse;
    BclParser_Init(&parse);
    BclParser_Parse(&parse, bcl_in);
    char name[WCMD_MAX_NAME] = {0};
    BclParser_Extract(&parse, "NAME", name, sizeof(name));
    BclParser_Free(&parse);
    if (!name[0]) return BclResult_Err(bcl_out, out_sz, 20, "no NAME in packet");

    char esc[WCMD_MAX_NAME * 2] = {0};
    Wcmd_EscapeSQ(name, esc, sizeof(esc));
    char cmd[1024];
    int rc;
    if (STATE.terminal_type == WCMD_TERM_TMUX) {
        snprintf(cmd, sizeof(cmd), "tmux kill-window -t '%s' 2>/dev/null", esc);
        rc = system(cmd);
    } else {
        snprintf(cmd, sizeof(cmd),
            "osascript -e 'tell application \"%s\" to close every window' 2>/dev/null", esc);
        rc = system(cmd);
    }
    if (rc != 0) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "close failed: %s", name);
        return BclResult_Err(bcl_out, out_sz, 33, "close failed");
    }
    if (strcmp(STATE.last_window, name) == 0) STATE.last_window[0] = '\0';
    char body[256];
    snprintf(body, sizeof(body), "[@STATUS]{closed}[@NAME]{%s}", name);
    return BclResult_Ok(bcl_out, out_sz, body);
}

static int Wcmd_SendKeys(const char *bcl_in, char *bcl_out, size_t out_sz) {
    BclParseResult parse;
    BclParser_Init(&parse);
    BclParser_Parse(&parse, bcl_in);
    char name[WCMD_MAX_NAME] = {0};
    char keys[WCMD_MAX_KEYS] = {0};
    BclParser_Extract(&parse, "NAME", name, sizeof(name));
    BclParser_Extract(&parse, "KEYS", keys, sizeof(keys));
    BclParser_Free(&parse);
    if (!name[0] || !keys[0]) {
        return BclResult_Err(bcl_out, out_sz, 20, "no NAME or KEYS in packet");
    }
    if (STATE.terminal_type != WCMD_TERM_TMUX) {
        return BclResult_Err(bcl_out, out_sz, 40, "send_keys requires tmux backend");
    }
    char esc_name[WCMD_MAX_NAME * 2] = {0};
    char esc_keys[WCMD_MAX_KEYS * 2] = {0};
    Wcmd_EscapeSQ(name, esc_name, sizeof(esc_name));
    Wcmd_EscapeSQ(keys, esc_keys, sizeof(esc_keys));
    char cmd[WCMD_MAX_KEYS + 512];
    snprintf(cmd, sizeof(cmd),
        "tmux send-keys -t '%s' '%s' Enter 2>/dev/null", esc_name, esc_keys);
    if (system(cmd) != 0) {
        snprintf(STATE.last_error, sizeof(STATE.last_error), "send_keys failed");
        return BclResult_Err(bcl_out, out_sz, 34, "send_keys failed");
    }
    strncpy(STATE.last_window, name, sizeof(STATE.last_window) - 1);
    STATE.last_window[sizeof(STATE.last_window) - 1] = '\0';
    char body[512];
    snprintf(body, sizeof(body), "[@STATUS]{sent}[@NAME]{%s}[@KEYS]{%s}", name, keys);
    return BclResult_Ok(bcl_out, out_sz, body);
}

static int Wcmd_Snapshot(char *bcl_out, size_t out_sz) {
    char raw[WCMD_MAX_SHELL_OUT] = {0};
    int got;
    if (STATE.terminal_type == WCMD_TERM_TMUX) {
        got = Wcmd_Shell(
            "tmux list-windows -F '#{window_index}:#{window_name} #{window_layout}' 2>/dev/null",
            raw, sizeof(raw));
    } else {
        got = Wcmd_Shell(
            "osascript -e 'tell application \"System Events\" to get name of every window of every process' 2>/dev/null",
            raw, sizeof(raw));
    }
    if (got < 0) {
        return BclResult_Err(bcl_out, out_sz, 35, "snapshot backend failed");
    }
    Wcmd_RTrim(raw);
    char body[WCMD_MAX_SHELL_OUT];
    snprintf(body, sizeof(body), "[@LAYOUT]{%s}", raw);
    return BclResult_Ok(bcl_out, out_sz, body);
}

static int Wcmd_SetConfig(const char *bcl_in, char *bcl_out, size_t out_sz) {
    BclParseResult parse;
    BclParser_Init(&parse);
    BclParser_Parse(&parse, bcl_in);
    char ttype[32] = {0};
    char dwin[WCMD_MAX_NAME] = {0};
    BclParser_Extract(&parse, "TERMINAL_TYPE", ttype, sizeof(ttype));
    BclParser_Extract(&parse, "DEFAULT_WINDOW", dwin, sizeof(dwin));
    BclParser_Free(&parse);

    if (ttype[0]) {
        if (strcmp(ttype, "tmux") == 0) STATE.terminal_type = WCMD_TERM_TMUX;
        else if (strcmp(ttype, "screen") == 0) STATE.terminal_type = WCMD_TERM_SCREEN;
        else if (strcmp(ttype, "osascript") == 0) STATE.terminal_type = WCMD_TERM_OSA;
        else return BclResult_Err(bcl_out, out_sz, 22, "unknown TERMINAL_TYPE");
    }
    if (dwin[0]) {
        strncpy(STATE.default_window, dwin, sizeof(STATE.default_window) - 1);
        STATE.default_window[sizeof(STATE.default_window) - 1] = '\0';
    }
    return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
}

int Wcmd_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) Wcmd_Init();
    if (!cmd) return BclResult_Err(bcl_out, out_sz, 10, "no command provided");
    STATE.commands_run++;

    if (strcmp(cmd, "read_state") == 0) {
        char buf[512];
        snprintf(buf, sizeof(buf),
            "[@INITIALIZED]{%d}[@COMMANDS]{%d}[@WINDOWS]{%d}[@LAST_WINDOW]{%s}"
            "[@TERMINAL_TYPE]{%s}[@DEFAULT_WINDOW]{%s}",
            STATE.initialized, STATE.commands_run, STATE.windows_managed,
            STATE.last_window, Wcmd_TermName(), STATE.default_window);
        return BclResult_Ok(bcl_out, out_sz, buf);
    }
    if (strcmp(cmd, "set_config") == 0)   return Wcmd_SetConfig(bcl_in, bcl_out, out_sz);
    if (strcmp(cmd, "list_windows") == 0) return Wcmd_ListWindows(bcl_out, out_sz);
    if (strcmp(cmd, "focus") == 0)        return Wcmd_Focus(bcl_in, bcl_out, out_sz);
    if (strcmp(cmd, "split") == 0)        return Wcmd_Split(bcl_in, bcl_out, out_sz);
    if (strcmp(cmd, "close") == 0)        return Wcmd_CloseWindow(bcl_in, bcl_out, out_sz);
    if (strcmp(cmd, "send_keys") == 0)    return Wcmd_SendKeys(bcl_in, bcl_out, out_sz);
    if (strcmp(cmd, "snapshot") == 0)     return Wcmd_Snapshot(bcl_out, out_sz);

    return BclResult_Err(bcl_out, out_sz, 50, "unknown command");
}
