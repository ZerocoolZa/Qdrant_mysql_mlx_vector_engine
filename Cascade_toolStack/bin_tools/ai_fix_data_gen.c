/*
 *[@GHOST]
 *[@VBSTYLE]
 *[@FILEID] ai_fix_data_gen.c
 *[@SUMMARY] C-native training data generator for 40->64->16 error fix neural model
 *[@CLASS] none
 *[@METHOD] main
 *[@AUTHOR] Cascade
 *[@DATE] 2026-06-28
 *[@SESSION] cli_ai_fix_coreml
 *
 * Generates synthetic error samples, extracts 40D features,
 * maps to 16D one-hot fix action targets, outputs JSON in coretotch format.
 *
 * Build: cc -O2 -o ai_fix_data_gen ai_fix_data_gen.c -lm
 * Usage: ./ai_fix_data_gen > training_data.json
 *
 * Pipeline: this generates data -> coretotch_fix trains -> cascade_cli infers
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>
#include <math.h>

/* ── Model Dimensions ── */
#define INPUT_DIM   40
#define HIDDEN_DIM  64
#define OUTPUT_DIM  16

/* ── Error type names (index = feature 0-15) ── */
static const char *ERROR_TYPES[16] = {
    "ModuleNotFoundError", "ImportError", "FileNotFoundError", "AttributeError",
    "KeyError", "IndexError", "IndentationError", "NameError",
    "ValueError", "TypeError", "SyntaxError", "RuntimeError",
    "ConnectionError", "PermissionError", "RecursionError", "UnicodeDecodeError",
};

/* ── Fix action indices (index = output neuron) ── */
typedef struct {
    const char *error_type;
    int fix_action_idx;
    const char *messages[8];
    int msg_count;
} ErrorTemplate;

static ErrorTemplate TEMPLATES[] = {
    {"ModuleNotFoundError", 0, {
        "Traceback (most recent call last):\n  File \"app.py\", line 1, in <module>\n    import nonexistent_xyz\nModuleNotFoundError: No module named 'nonexistent_xyz'",
        "Traceback (most recent call last):\n  File \"main.py\", line 5, in <module>\n    import flask_sqlalchemy\nModuleNotFoundError: No module named 'flask_sqlalchemy'",
        "Traceback (most recent call last):\n  File \"test.py\", line 2, in <module>\n    import pandas as pd\nModuleNotFoundError: No module named 'pandas'",
        "Traceback (most recent call last):\n  File \"run.py\", line 10, in <module>\n    import requests\nModuleNotFoundError: No module named 'requests'",
    }, 4},

    {"ImportError", 1, {
        "Traceback (most recent call last):\n  File \"app.py\", line 3, in <module>\n    from os import nonexistent_func\nImportError: cannot import name 'nonexistent_func' from 'os'",
        "Traceback (most recent call last):\n  File \"utils.py\", line 1, in <module>\n    from collections import xyz\nImportError: cannot import name 'xyz' from 'collections'",
        "Traceback (most recent call last):\n  File \"core.py\", line 8, in <module>\n    from typing import NotAType\nImportError: cannot import name 'NotAType'",
    }, 3},

    {"FileNotFoundError", 2, {
        "Traceback (most recent call last):\n  File \"app.py\", line 5, in <module>\n    open('missing_file.txt')\nFileNotFoundError: [Errno 2] No such file or directory: 'missing_file.txt'",
        "Traceback (most recent call last):\n  File \"loader.py\", line 12, in <module>\n    f = open('/tmp/nonexistent.json')\nFileNotFoundError: [Errno 2] No such file or directory: '/tmp/nonexistent.json'",
        "Traceback (most recent call last):\n  File \"config.py\", line 3, in <module>\n    with open('settings.yaml') as fh:\nFileNotFoundError: [Errno 2] No such file or directory: 'settings.yaml'",
    }, 3},

    {"AttributeError", 3, {
        "Traceback (most recent call last):\n  File \"app.py\", line 10, in <module>\n    obj.nonexistent_method()\nAttributeError: 'MyClass' object has no attribute 'nonexistent_method'",
        "Traceback (most recent call last):\n  File \"data.py\", line 5, in <module>\n    result = data.missing_field\nAttributeError: 'dict' object has no attribute 'missing_field'",
        "Traceback (most recent call last):\n  File \"handler.py\", line 22, in <module>\n    response.status\nAttributeError: 'NoneType' object has no attribute 'status'",
    }, 3},

    {"KeyError", 4, {
        "Traceback (most recent call last):\n  File \"app.py\", line 8, in <module>\n    val = data['missing_key']\nKeyError: 'missing_key'",
        "Traceback (most recent call last):\n  File \"parser.py\", line 15, in <module>\n    print(config['database'])\nKeyError: 'database'",
        "Traceback (most recent call last):\n  File \"cache.py\", line 3, in <module>\n    item = cache['expired']\nKeyError: 'expired'",
    }, 3},

    {"IndexError", 5, {
        "Traceback (most recent call last):\n  File \"app.py\", line 5, in <module>\n    print(my_list[10])\nIndexError: list index out of range",
        "Traceback (most recent call last):\n  File \"processor.py\", line 20, in <module>\n    result = items[100]\nIndexError: list index out of range",
        "Traceback (most recent call last):\n  File \"array.py\", line 8, in <module>\n    val = matrix[5][3]\nIndexError: list index out of range",
    }, 3},

    {"IndentationError", 6, {
        "  File \"app.py\", line 5\n    print('hello')\n    ^\nIndentationError: expected an indented block",
        "  File \"style.py\", line 10\n    if True:\n    print('bad')\n    ^\nIndentationError: unexpected indent",
        "  File \"main.py\", line 3\n    def foo():\n    return 42\n    ^\nIndentationError: expected an indented block",
    }, 3},

    {"NameError", 7, {
        "Traceback (most recent call last):\n  File \"app.py\", line 1, in <module>\n    print(undefined_var)\nNameError: name 'undefined_var' is not defined",
        "Traceback (most recent call last):\n  File \"calc.py\", line 12, in <module>\n    result = unknown_func()\nNameError: name 'unknown_func' is not defined",
        "Traceback (most recent call last):\n  File \"handler.py\", line 5, in <module>\n    data = missing_variable\nNameError: name 'missing_variable' is not defined",
    }, 3},

    {"ValueError", 8, {
        "Traceback (most recent call last):\n  File \"app.py\", line 3, in <module>\n    int('abc')\nValueError: invalid literal for int() with base 10: 'abc'",
        "Traceback (most recent call last):\n  File \"convert.py\", line 10, in <module>\n    float('not_a_number')\nValueError: could not convert string to float: 'not_a_number'",
        "Traceback (most recent call last):\n  File \"parse.py\", line 8, in <module>\n    datetime.strptime('bad', '%Y')\nValueError: time data 'bad' does not match format '%Y'",
    }, 3},

    {"TypeError", 9, {
        "Traceback (most recent call last):\n  File \"app.py\", line 1, in <module>\n    print('hello' + 5)\nTypeError: can only concatenate str (not \"int\") to str",
        "Traceback (most recent call last):\n  File \"merge.py\", line 5, in <module>\n    result = [1,2] + (3,4)\nTypeError: can only concatenate list (not \"tuple\") to list",
        "Traceback (most recent call last):\n  File \"iter.py\", line 10, in <module>\n    for x in 42:\nTypeError: 'int' object is not iterable",
    }, 3},

    {"SyntaxError", 10, {
        "  File \"app.py\", line 5\n    if True\n           ^\nSyntaxError: expected ':'",
        "  File \"main.py\", line 10\n    def foo()\n             ^\nSyntaxError: expected ':'",
        "  File \"parser.py\", line 3\n    print('hello'\n                  ^\nSyntaxError: '(' was never closed",
    }, 3},

    {"RuntimeError", 15, {
        "Traceback (most recent call last):\n  File \"app.py\", line 20, in <module>\n    raise RuntimeError('unexpected state')\nRuntimeError: unexpected state",
        "Traceback (most recent call last):\n  File \"engine.py\", line 55, in <module>\n    raise RuntimeError('max retries exceeded')\nRuntimeError: max retries exceeded",
    }, 2},

    {"ConnectionError", 12, {
        "Traceback (most recent call last):\n  File \"client.py\", line 10, in <module>\n    requests.get('http://localhost:9999')\nConnectionError: [Errno 61] Connection refused",
        "Traceback (most recent call last):\n  File \"db.py\", line 5, in <module>\n    connect('localhost', 3306)\nConnectionError: [Errno 61] Connection refused",
        "Traceback (most recent call last):\n  File \"api.py\", line 22, in <module>\n    urllib.request.urlopen(url)\nConnectionError: [Errno 61] Connection refused",
    }, 3},

    {"PermissionError", 11, {
        "Traceback (most recent call last):\n  File \"app.py\", line 5, in <module>\n    open('/etc/passwd', 'w')\nPermissionError: [Errno 13] Permission denied: '/etc/passwd'",
        "Traceback (most recent call last):\n  File \"writer.py\", line 10, in <module>\n    os.remove('/root/file.txt')\nPermissionError: [Errno 13] Permission denied: '/root/file.txt'",
    }, 2},

    {"RecursionError", 13, {
        "Traceback (most recent call last):\n  File \"app.py\", line 5, in <module>\n    factorial(10000)\nRecursionError: maximum recursion depth exceeded",
        "Traceback (most recent call last):\n  File \"tree.py\", line 20, in <module>\n    traverse(node)\nRecursionError: maximum recursion depth exceeded in comparison",
    }, 2},

    {"UnicodeDecodeError", 14, {
        "Traceback (most recent call last):\n  File \"reader.py\", line 5, in <module>\n    open('file.bin').read()\nUnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0",
        "Traceback (most recent call last):\n  File \"loader.py\", line 10, in <module>\n    data = f.read()\nUnicodeDecodeError: 'utf-8' codec can't decode byte 0x96 in position 2",
    }, 2},
};

#define N_TEMPLATES (sizeof(TEMPLATES) / sizeof(TEMPLATES[0]))

/* ── Feature extraction (matches cascade_cli.c logic) ── */
static void str_to_lower(char *dst, const char *src, int max) {
    int i;
    for (i = 0; i < max - 1 && src[i]; i++) {
        dst[i] = tolower((unsigned char)src[i]);
    }
    dst[i] = '\0';
}

static int contains(const char *hay, const char *needle) {
    return strstr(hay, needle) != NULL;
}

static int has_digit(const char *s) {
    for (; *s; s++)
        if (*s >= '0' && *s <= '9') return 1;
    return 0;
}

static void extract_error_line(char *out, int out_max, const char *text_lower) {
    int len = strlen(text_lower);
    int start = 0;
    for (int i = 0; i <= len; i++) {
        if (text_lower[i] == '\n' || text_lower[i] == '\0') {
            int line_len = i - start;
            if (line_len > 0 && line_len < out_max) {
                char tmp[2048];
                memcpy(tmp, text_lower + start, line_len);
                tmp[line_len] = '\0';
                if (contains(tmp, "error") || contains(tmp, "exception") || contains(tmp, "refused")) {
                    char *trim = tmp;
                    while (*trim == ' ' || *trim == '\t') trim++;
                    snprintf(out, out_max, "%s", trim);
                    return;
                }
            }
            start = i + 1;
        }
    }
    snprintf(out, out_max, "%s", text_lower);
}

static const char *CATEGORY_KEYWORDS[14][4] = {
    {"import", "module", "modulenotfound", NULL},
    {"syntax", "indent", "eol", "closed"},
    {"runtime", "recursion", "maximum", NULL},
    {"type", "operand", "concatenate", "iterable"},
    {"filenotfounderror", "no such file", "errno 2", NULL},
    {"attribute", "object", NULL, NULL},
    {"keyerror", "key", NULL, NULL},
    {"index", "range", NULL, NULL},
    {"name", "defined", NULL, NULL},
    {"value", "literal", "convert", NULL},
    {"permission", "errno 13", NULL, NULL},
    {"connection", "refused", "errno 61", NULL},
    {"codec", "decode", "unicode", "byte"},
    {"division", "zero", "divide", NULL},
};

static void extract_features(float *features, const char *stderr_text) {
    char text_lower[4096];
    str_to_lower(text_lower, stderr_text, 4096);

    char error_line[2048];
    extract_error_line(error_line, 2048, text_lower);

    for (int i = 0; i < INPUT_DIM; i++) features[i] = 0.0f;

    /* Features 0-15: error type one-hot */
    for (int i = 0; i < 16; i++) {
        char type_lower[64];
        str_to_lower(type_lower, ERROR_TYPES[i], 64);
        if (contains(error_line, type_lower))
            features[i] = 1.0f;
    }

    /* Features 16-29: category presence */
    for (int j = 0; j < 14; j++) {
        for (int i = 0; i < 4; i++) {
            if (CATEGORY_KEYWORDS[j][i] && contains(error_line, CATEGORY_KEYWORDS[j][i])) {
                features[16 + j] = 1.0f;
                break;
            }
        }
    }

    /* Features 30-39: text properties */
    features[30] = contains(text_lower, "traceback") ? 1.0f : 0.0f;
    features[31] = (contains(error_line, "errno 2") || contains(error_line, "no such file")) ? 1.0f : 0.0f;
    features[32] = contains(text_lower, "line") ? 1.0f : 0.0f;
    int elen = strlen(error_line);
    features[33] = (elen > 500) ? 1.0f : (float)elen / 500.0f;
    int nl_count = 0;
    for (int i = 0; text_lower[i]; i++)
        if (text_lower[i] == '\n') nl_count++;
    features[34] = (nl_count > 20) ? 1.0f : (float)nl_count / 20.0f;
    features[35] = contains(error_line, "error") ? 1.0f : 0.0f;
    features[36] = contains(error_line, "exception") ? 1.0f : 0.0f;
    features[37] = contains(error_line, "warning") ? 1.0f : 0.0f;
    features[38] = has_digit(error_line) ? 1.0f : 0.0f;
    features[39] = 1.0f;
}

/* ── Main: generate JSON training data ── */
int main(void) {
    printf("{\"episodes\":[");

    int episode = 0;
    for (int t = 0; t < (int)N_TEMPLATES; t++) {
        for (int m = 0; m < TEMPLATES[t].msg_count; m++) {
            float features[INPUT_DIM];
            extract_features(features, TEMPLATES[t].messages[m]);

            float target[OUTPUT_DIM];
            memset(target, 0, sizeof(target));
            target[TEMPLATES[t].fix_action_idx] = 1.0f;

            if (episode > 0) printf(",");
            printf("{\"episode\":%d,\"num_nodes\":1,\"steps\":[{\"state\":[", episode);
            for (int i = 0; i < INPUT_DIM; i++) {
                if (i > 0) printf(",");
                printf("%.1f", features[i]);
            }
            printf("],\"action\":[");
            for (int i = 0; i < OUTPUT_DIM; i++) {
                if (i > 0) printf(",");
                printf("%.1f", target[i]);
            }
            printf("],\"reward\":1.0}]}");

            episode++;
        }
    }

    /* Generate augmented samples: mix error types with different phrasings */
    /* This helps the model generalize rather than memorize */
    const char *augment_prefixes[] = {
        "Traceback (most recent call last):\n  File \"module_%d.py\", line %d, in <module>\n    ",
        "Traceback (most recent call last):\n  File \"test_%d.py\", line %d, in <module>\n    ",
        "Traceback (most recent call last):\n  File \"app_%d.py\", line %d, in <module>\n    ",
    };
    const char *augment_bodies[] = {
        "import missing_module_%d\nModuleNotFoundError: No module named 'missing_module_%d'",
        "print(undefined_%d)\nNameError: name 'undefined_%d' is not defined",
        "x = [1]; print(x[%d])\nIndexError: list index out of range",
        "d = {}; print(d['key_%d'])\nKeyError: 'key_%d'",
        "open('missing_%d.txt')\nFileNotFoundError: [Errno 2] No such file or directory: 'missing_%d.txt'",
        "print('hello' + %d)\nTypeError: can only concatenate str (not \"int\") to str",
        "int('bad_%d')\nValueError: invalid literal for int() with base 10: 'bad_%d'",
        "from os import fake_%d\nImportError: cannot import name 'fake_%d' from 'os'",
    };
    int augment_fix[] = {0, 7, 5, 4, 2, 9, 8, 1};
    int n_augment = sizeof(augment_bodies) / sizeof(augment_bodies[0]);

    for (int round = 0; round < 5; round++) {
        for (int a = 0; a < n_augment; a++) {
            char buf[4096];
            int n = rand() % 100 + 1;
            int pfx_idx = rand() % 3;
            snprintf(buf, sizeof(buf), augment_prefixes[pfx_idx], n, n * 3);
            char body[2048];
            snprintf(body, sizeof(body), augment_bodies[a], n, n);
            strcat(buf, body);

            float features[INPUT_DIM];
            extract_features(features, buf);

            float target[OUTPUT_DIM];
            memset(target, 0, sizeof(target));
            target[augment_fix[a]] = 1.0f;

            if (episode > 0) printf(",");
            printf("{\"episode\":%d,\"num_nodes\":1,\"steps\":[{\"state\":[", episode);
            for (int i = 0; i < INPUT_DIM; i++) {
                if (i > 0) printf(",");
                printf("%.1f", features[i]);
            }
            printf("],\"action\":[");
            for (int i = 0; i < OUTPUT_DIM; i++) {
                if (i > 0) printf(",");
                printf("%.1f", target[i]);
            }
            printf("],\"reward\":1.0}]}");

            episode++;
        }
    }

    printf("],\"config\":{\"input_dim\":%d,\"output_dim\":%d,\"samples\":%d,\"source\":\"c_native_generator\"}}\n",
           INPUT_DIM, OUTPUT_DIM, episode);

    fprintf(stderr, "Generated %d training samples\n", episode);
    return 0;
}
