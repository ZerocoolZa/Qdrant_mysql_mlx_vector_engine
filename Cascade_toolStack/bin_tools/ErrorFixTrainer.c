/*
#[@GHOST]{[@file<ErrorFixTrainer.c>][@state<active>][@date<2026-06-28>][@ver<1.0>][@auth<Cascade>]}
#[@VBSTYLE]{[@auth<Cascade>][@role<ErrorFixTrainer>][@return<Tuple3>][@owner<Cascade>][@session<cli_ai_fix>]}
#[@FILEID] ErrorFixTrainer.c
#[@SUMMARY] Error-to-lesson generator combined with a SQLite trainer. Produces synthetic lessons for common Python error classes and stores them in a file-based SQLite database for downstream fix inference.
#[@CLASS] ErrorFixTrainer
#[@METHOD] main, open_db, create_schema, generate_lessons, insert_lesson, build_broken_code, build_fixed_code, now_iso, rand_conf
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] cli_ai_fix
*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "sqlite3.h"

/* ===== Constants ========================================================== */

#define LESSONS_PER_RULE 10
#define NUM_RULES 10
#define TOTAL_LESSONS (LESSONS_PER_RULE * NUM_RULES)
#define BUF_LEN 1024
#define CODE_LEN 512
#define TS_LEN 32

/* ===== Error rule table =================================================== */

typedef struct {
    const char *error_name;   /* Python error class name            */
    const char *keyword;      /* substring matched in real messages */
    const char *root_cause;   /* human readable root cause          */
    const char *repair;       /* human readable repair action       */
} ErrorRule;

static const ErrorRule RULES[NUM_RULES] = {
    { "NameError",          "is not defined",     "Undefined variable",      "Declare variable before use" },
    { "TypeError",          "unsupported operand","Type mismatch",           "Cast or convert types" },
    { "IndexError",         "out of range",       "Index exceeds bounds",    "Check length before access" },
    { "KeyError",           "keyerror",           "Missing dictionary key",  "Use dict.get()" },
    { "FileNotFoundError",  "no such file",       "Missing file path",       "Validate path" },
    { "SyntaxError",        "invalid syntax",     "Bad syntax structure",    "Fix punctuation/indent" },
    { "AttributeError",     "has no attribute",   "Invalid object member",   "Check API or use getattr" },
    { "ImportError",        "cannot import",      "Broken import path",      "Fix module name/path" },
    { "ValueError",         "invalid literal",    "Bad value conversion",    "Validate input before cast" },
    { "IndentationError",   "indent",             "Wrong indentation",       "Fix spacing" },
};

/* Variable name pools for realistic synthetic code variants */

static const char *NAMES[] = {
    "x", "y", "z", "count", "total", "value", "item", "data",
    "name", "score", "idx", "buf", "res", "tmp", "acc"
};
#define NUM_NAMES ((int)(sizeof(NAMES) / sizeof(NAMES[0])))

static const char *LISTS[] = {
    "nums", "rows", "items", "vals", "pts", "buf", "tags", "ids"
};
#define NUM_LISTS ((int)(sizeof(LISTS) / sizeof(LISTS[0])))

static const char *KEYS[] = {
    "user_id", "name", "age", "email", "role", "score", "token", "path"
};
#define NUM_KEYS ((int)(sizeof(KEYS) / sizeof(KEYS[0])))

static const char *FILES[] = {
    "config.json", "data.csv", "input.txt", "model.bin", "log.txt",
    "settings.yaml", "weights.pt", "vocab.pkl"
};
#define NUM_FILES ((int)(sizeof(FILES) / sizeof(FILES[0])))

static const char *MODS[] = {
    "nump", "pandas", "torch", "flask", "requests", "sklearn", "cv2", "yaml"
};
#define NUM_MODS ((int)(sizeof(MODS) / sizeof(MODS[0])))

static const char *ATTRS[] = {
    "split", "append", "items", "keys", "values", "shape", "size", "lower"
};
#define NUM_ATTRS ((int)(sizeof(ATTRS) / sizeof(ATTRS[0])))

/* ===== Helpers ============================================================ */

static int rand_range(int lo, int hi) {
    /* inclusive [lo, hi] */
    if (hi <= lo) return lo;
    return lo + (rand() % (hi - lo + 1));
}

static int rand_conf(void) {
    /* confidence between 50 and 100 inclusive */
    return rand_range(50, 100);
}

static void now_iso(char *out, size_t n) {
    time_t t = time(NULL);
    struct tm tmv;
    struct tm *lt = localtime_r(&t, &tmv);
    if (lt == NULL) {
        snprintf(out, n, "1970-01-01 00:00:00");
        return;
    }
    strftime(out, n, "%Y-%m-%d %H:%M:%S", lt);
}

/* ===== Realistic code generation ========================================== */

/*
 * build_broken_code / build_fixed_code produce realistic Python snippets
 * that would actually trigger (or fix) the given error class. Each variant
 * index rotates through different variable names / values so the 10 lessons
 * per rule are not identical.
 */

static void build_broken_code(const ErrorRule *r, int variant, char *out) {
    const char *n = NAMES[variant % NUM_NAMES];
    const char *lst = LISTS[(variant + 1) % NUM_LISTS];
    const char *key = KEYS[(variant + 2) % NUM_KEYS];
    const char *fn = FILES[(variant + 3) % NUM_FILES];
    const char *mod = MODS[(variant + 4) % NUM_MODS];
    const char *attr = ATTRS[(variant + 5) % NUM_ATTRS];
    int idx = 5 + (variant % 6);      /* out-of-range index */
    int num = 3 + (variant % 4);      /* small numeric value */

    if (strcmp(r->error_name, "NameError") == 0) {
        snprintf(out, CODE_LEN, "print(%s)", n);
        return;
    }
    if (strcmp(r->error_name, "TypeError") == 0) {
        snprintf(out, CODE_LEN, "result = '%d' + %d", num, num + 1);
        return;
    }
    if (strcmp(r->error_name, "IndexError") == 0) {
        snprintf(out, CODE_LEN, "%s = [1, 2, 3]\nprint(%s[%d])", lst, lst, idx);
        return;
    }
    if (strcmp(r->error_name, "KeyError") == 0) {
        snprintf(out, CODE_LEN, "d = {'%s': 1}\nprint(d['%s'])", key, KEYS[(variant + 3) % NUM_KEYS]);
        return;
    }
    if (strcmp(r->error_name, "FileNotFoundError") == 0) {
        snprintf(out, CODE_LEN, "f = open('%s', 'r')\ncontent = f.read()", fn);
        return;
    }
    if (strcmp(r->error_name, "SyntaxError") == 0) {
        snprintf(out, CODE_LEN, "if %s > %d\n    print(%s)", n, num, n);
        return;
    }
    if (strcmp(r->error_name, "AttributeError") == 0) {
        snprintf(out, CODE_LEN, "s = 123\nprint(s.%s())", attr);
        return;
    }
    if (strcmp(r->error_name, "ImportError") == 0) {
        snprintf(out, CODE_LEN, "from %s import nonexistent_func", mod);
        return;
    }
    if (strcmp(r->error_name, "ValueError") == 0) {
        snprintf(out, CODE_LEN, "n = int('abc%d')", variant);
        return;
    }
    if (strcmp(r->error_name, "IndentationError") == 0) {
        snprintf(out, CODE_LEN, "def f():\nreturn %d", num);
        return;
    }
    snprintf(out, CODE_LEN, "# unknown error class");
}

static void build_fixed_code(const ErrorRule *r, int variant, char *out) {
    const char *n = NAMES[variant % NUM_NAMES];
    const char *lst = LISTS[(variant + 1) % NUM_LISTS];
    const char *key = KEYS[(variant + 2) % NUM_KEYS];
    const char *fn = FILES[(variant + 3) % NUM_FILES];
    const char *mod = MODS[(variant + 4) % NUM_MODS];
    const char *attr = ATTRS[(variant + 5) % NUM_ATTRS];
    int idx = 5 + (variant % 6);
    int num = 3 + (variant % 4);

    if (strcmp(r->error_name, "NameError") == 0) {
        snprintf(out, CODE_LEN, "%s = 10\nprint(%s)", n, n);
        return;
    }
    if (strcmp(r->error_name, "TypeError") == 0) {
        snprintf(out, CODE_LEN, "result = '%d' + str(%d)", num, num + 1);
        return;
    }
    if (strcmp(r->error_name, "IndexError") == 0) {
        snprintf(out, CODE_LEN,
                 "%s = [1, 2, 3]\nif len(%s) > %d:\n    print(%s[%d])",
                 lst, lst, idx, lst, idx);
        return;
    }
    if (strcmp(r->error_name, "KeyError") == 0) {
        snprintf(out, CODE_LEN,
                 "d = {'%s': 1}\nprint(d.get('%s', 'default'))",
                 key, KEYS[(variant + 3) % NUM_KEYS]);
        return;
    }
    if (strcmp(r->error_name, "FileNotFoundError") == 0) {
        snprintf(out, CODE_LEN,
                 "import os\nif os.path.exists('%s'):\n    f = open('%s', 'r')\n    content = f.read()",
                 fn, fn);
        return;
    }
    if (strcmp(r->error_name, "SyntaxError") == 0) {
        snprintf(out, CODE_LEN, "if %s > %d:\n    print(%s)", n, num, n);
        return;
    }
    if (strcmp(r->error_name, "AttributeError") == 0) {
        snprintf(out, CODE_LEN, "s = str(123)\nprint(s.%s())", attr);
        return;
    }
    if (strcmp(r->error_name, "ImportError") == 0) {
        snprintf(out, CODE_LEN, "import %s\nprint(%s.__version__)", mod, mod);
        return;
    }
    if (strcmp(r->error_name, "ValueError") == 0) {
        snprintf(out, CODE_LEN,
                 "raw = 'abc%d'\nif raw.isdigit():\n    n = int(raw)\nelse:\n    n = 0",
                 variant);
        return;
    }
    if (strcmp(r->error_name, "IndentationError") == 0) {
        snprintf(out, CODE_LEN, "def f():\n    return %d", num);
        return;
    }
    snprintf(out, CODE_LEN, "# unknown error class");
}

/* ===== Database operations ================================================ */

static sqlite3 *open_db(const char *path) {
    sqlite3 *db = NULL;
    int rc = sqlite3_open(path, &db);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "[ErrorFixTrainer] cannot open db '%s': %s\n",
                path, sqlite3_errmsg(db));
        if (db) sqlite3_close(db);
        return NULL;
    }
    return db;
}

static int create_schema(sqlite3 *db) {
    const char *sql =
        "CREATE TABLE IF NOT EXISTS lessons ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  error_text TEXT NOT NULL,"
        "  error_name TEXT NOT NULL,"
        "  root_cause TEXT NOT NULL,"
        "  repair TEXT NOT NULL,"
        "  broken_code TEXT NOT NULL,"
        "  fixed_code TEXT NOT NULL,"
        "  confidence INTEGER NOT NULL,"
        "  created_at TEXT NOT NULL"
        ");";
    char *err = NULL;
    int rc = sqlite3_exec(db, sql, NULL, NULL, &err);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "[ErrorFixTrainer] schema error: %s\n", err ? err : "?");
        sqlite3_free(err);
        return rc;
    }
    return SQLITE_OK;
}

static int insert_lesson(sqlite3 *db,
                         const char *error_text,
                         const char *error_name,
                         const char *root_cause,
                         const char *repair,
                         const char *broken_code,
                         const char *fixed_code,
                         int confidence,
                         const char *created_at) {
    const char *sql =
        "INSERT INTO lessons "
        "(error_text, error_name, root_cause, repair, broken_code, fixed_code, confidence, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?);";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "[ErrorFixTrainer] prepare failed: %s\n", sqlite3_errmsg(db));
        return rc;
    }
    sqlite3_bind_text(stmt, 1, error_text, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, error_name, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, root_cause, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 4, repair, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 5, broken_code, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 6, fixed_code, -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 7, confidence);
    sqlite3_bind_text(stmt, 8, created_at, -1, SQLITE_TRANSIENT);

    rc = sqlite3_step(stmt);
    if (rc != SQLITE_DONE) {
        fprintf(stderr, "[ErrorFixTrainer] insert failed: %s\n", sqlite3_errmsg(db));
        sqlite3_finalize(stmt);
        return rc;
    }
    sqlite3_finalize(stmt);
    return SQLITE_OK;
}

/* ===== Lesson generation ================================================== */

static int generate_lessons(sqlite3 *db) {
    char error_text[BUF_LEN];
    char broken[CODE_LEN];
    char fixed[CODE_LEN];
    char ts[TS_LEN];
    int inserted = 0;

    for (int i = 0; i < NUM_RULES; i++) {
        const ErrorRule *r = &RULES[i];
        for (int v = 0; v < LESSONS_PER_RULE; v++) {
            now_iso(ts, sizeof(ts));
            build_broken_code(r, v, broken);
            build_fixed_code(r, v, fixed);

            /* Compose a realistic error_text that contains the keyword. */
            if (strcmp(r->error_name, "NameError") == 0) {
                snprintf(error_text, BUF_LEN,
                         "NameError: name '%s' is not defined",
                         NAMES[v % NUM_NAMES]);
            } else if (strcmp(r->error_name, "TypeError") == 0) {
                snprintf(error_text, BUF_LEN,
                         "TypeError: unsupported operand type(s) for +: 'str' and 'int'");
            } else if (strcmp(r->error_name, "IndexError") == 0) {
                snprintf(error_text, BUF_LEN,
                         "IndexError: list index out of range");
            } else if (strcmp(r->error_name, "KeyError") == 0) {
                snprintf(error_text, BUF_LEN,
                         "KeyError: '%s'", KEYS[(v + 3) % NUM_KEYS]);
            } else if (strcmp(r->error_name, "FileNotFoundError") == 0) {
                snprintf(error_text, BUF_LEN,
                         "FileNotFoundError: [Errno 2] No such file or directory: '%s'",
                         FILES[(v + 3) % NUM_FILES]);
            } else if (strcmp(r->error_name, "SyntaxError") == 0) {
                snprintf(error_text, BUF_LEN,
                         "SyntaxError: invalid syntax");
            } else if (strcmp(r->error_name, "AttributeError") == 0) {
                snprintf(error_text, BUF_LEN,
                         "AttributeError: 'int' object has no attribute '%s'",
                         ATTRS[(v + 5) % NUM_ATTRS]);
            } else if (strcmp(r->error_name, "ImportError") == 0) {
                snprintf(error_text, BUF_LEN,
                         "ImportError: cannot import name 'nonexistent_func' from '%s'",
                         MODS[(v + 4) % NUM_MODS]);
            } else if (strcmp(r->error_name, "ValueError") == 0) {
                snprintf(error_text, BUF_LEN,
                         "ValueError: invalid literal for int() with base 10: 'abc%d'",
                         v);
            } else if (strcmp(r->error_name, "IndentationError") == 0) {
                snprintf(error_text, BUF_LEN,
                         "IndentationError: expected an indented block");
            } else {
                snprintf(error_text, BUF_LEN, "%s: %s", r->error_name, r->keyword);
            }

            int rc = insert_lesson(db, error_text, r->error_name,
                                   r->root_cause, r->repair,
                                   broken, fixed, rand_conf(), ts);
            if (rc == SQLITE_OK) {
                inserted++;
            }
        }
    }
    return inserted;
}

/* ===== Main =============================================================== */

int main(int argc, char **argv) {
    srand((unsigned int)time(NULL));

    char db_path[BUF_LEN];
    if (argc >= 2) {
        snprintf(db_path, sizeof(db_path), "%s", argv[1]);
    } else {
        snprintf(db_path, sizeof(db_path), "ErrorFixTrainer.db");
    }

    printf("[ErrorFixTrainer] opening database: %s\n", db_path);
    sqlite3 *db = open_db(db_path);
    if (db == NULL) {
        return 1;
    }

    if (create_schema(db) != SQLITE_OK) {
        sqlite3_close(db);
        return 1;
    }

    printf("[ErrorFixTrainer] schema ready (table: lessons)\n");
    printf("[ErrorFixTrainer] generating %d lessons across %d error types...\n",
           TOTAL_LESSONS, NUM_RULES);

    int inserted = generate_lessons(db);
    printf("[ErrorFixTrainer] inserted %d lessons\n", inserted);

    sqlite3_close(db);
    printf("[ErrorFixTrainer] database closed cleanly\n");

    printf("Generated %d lessons across %d error types\n", inserted, NUM_RULES);
    return 0;
}
