//[@GHOST]{file_path="core/Dom_Bloodhound/memunit_tester.c" date="2026-07-04" author="Devin" session_id="memunit-c" context="ClassTester — tests imports, classes, methods, errors against LiveState facts"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE class-tester"}
//[@FILEID]{id="memunit_tester.c" domain="dom_bloodhound" authority="MemunitTester"}
//[@SUMMARY]{summary="ClassTester. Tests imports, classes, methods, errors by querying LiveState RAM events. ANSI-colored PASS/FAIL output. Summary counters."}
//[@CLASS]{class="MemunitTester" domain="dom_bloodhound" authority="single"}
//[@METHOD]{methods="tester_init,tester_test_imports,tester_test_class,tester_test_all,tester_test_errors,get_unique_classes,has_event_kind,has_error_for"}

#include "memunit_debugger.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

/* ---- ANSI color codes ---- */

#define ANSI_GREEN   "\033[32m"
#define ANSI_RED     "\033[31m"
#define ANSI_YELLOW  "\033[33m"
#define ANSI_RESET   "\033[0m"
#define ANSI_BOLD    "\033[1m"

/* ---- Helper: has_fix_for (internal) ---- */

static int has_fix_for(live_state_t *ls, uint32_t entity)
{
    size_t i;

    if (ls == NULL) {
        return 0;
    }

    for (i = 0; i < ls->event_count; i++) {
        if (ls->events[i].kind != EVENT_FIX) {
            continue;
        }
        if (ls->events[i].entity == entity) {
            return 1;
        }
    }
    return 0;
}

/* ---- Helper functions ---- */

/*
 * get_unique_classes: scan all events, collect unique entity string IDs
 * where kind=EVENT_STATE and phase=PHASE_INIT.
 * Returns count of unique classes found.
 */
int get_unique_classes(live_state_t *ls, uint32_t out[], int max_classes)
{
    int count = 0;
    size_t i;
    int j;

    if (ls == NULL || out == NULL || max_classes <= 0) {
        return 0;
    }

    for (i = 0; i < ls->event_count && count < max_classes; i++) {
        if (ls->events[i].kind != EVENT_STATE) {
            continue;
        }
        if (ls->events[i].phase != PHASE_INIT) {
            continue;
        }
        if (ls->events[i].entity == 0) {
            continue;
        }

        /* Check if already in the list */
        for (j = 0; j < count; j++) {
            if (out[j] == ls->events[i].entity) {
                break;
            }
        }
        if (j == count) {
            out[count++] = ls->events[i].entity;
        }
    }
    return count;
}

/*
 * has_event_kind: check if any event matches given source+kind.
 * If source is 0, matches any source.
 * Returns 1 if found, 0 if not.
 */
int has_event_kind(live_state_t *ls, uint32_t source, uint32_t kind)
{
    size_t i;

    if (ls == NULL) {
        return 0;
    }

    for (i = 0; i < ls->event_count; i++) {
        if (ls->events[i].kind != kind) {
            continue;
        }
        if (source == 0) {
            return 1;
        }
        if (ls->events[i].source == source) {
            return 1;
        }
    }
    return 0;
}

/*
 * has_error_for: check if any EVENT_ERROR has matching entity.
 * Returns 1 if an error exists for that entity, 0 if not.
 */
int has_error_for(live_state_t *ls, uint32_t entity)
{
    size_t i;

    if (ls == NULL) {
        return 0;
    }

    for (i = 0; i < ls->event_count; i++) {
        if (ls->events[i].kind != EVENT_ERROR) {
            continue;
        }
        if (ls->events[i].entity == entity) {
            return 1;
        }
    }
    return 0;
}

/* ---- ClassTester functions ---- */

/*
 * tester_init: set state pointer, zero counters.
 * Returns 0 on success, -1 on error.
 */
int tester_init(class_tester_t *t, live_state_t *ls)
{
    if (t == NULL) {
        return -1;
    }
    t->state        = ls;
    t->tests_run    = 0;
    t->tests_passed = 0;
    t->tests_failed = 0;
    return 0;
}

/*
 * tester_test_imports:
 *   Query LiveState for all EVENT_IMPORT events.
 *   For each import, check if it was successful (no corresponding EVENT_ERROR
 *   with same entity). Print PASS/FAIL for each import.
 *   Update tests_run/passed/failed counters.
 *   Return number of tests run.
 */
int tester_test_imports(class_tester_t *t)
{
    size_t   count = 0;
    event_t *imports = NULL;
    size_t   i;
    int      tests_run = 0;

    if (t == NULL || t->state == NULL) {
        return 0;
    }

    imports = live_state_query_kind(t->state, EVENT_IMPORT, &count);

    if (count == 0) {
        t->tests_run++;
        t->tests_failed++;
        tests_run++;
        printf("  " ANSI_RED "[FAIL]" ANSI_RESET " test_imports: no imports found\n");
        return tests_run;
    }

    for (i = 0; i < count; i++) {
        const char *entity_str;
        int         has_err;

        tests_run++;
        t->tests_run++;

        entity_str = str_lookup(imports[i].entity);
        if (entity_str == NULL && imports[i].name != NULL) {
            entity_str = imports[i].name;
        }
        if (entity_str == NULL) {
            entity_str = "(unknown)";
        }

        has_err = has_error_for(t->state, imports[i].entity);

        if (has_err) {
            t->tests_failed++;
            printf("  " ANSI_RED "[FAIL]" ANSI_RESET
                   " test_imports: %s import failed (error recorded)\n",
                   entity_str);
        } else {
            t->tests_passed++;
            printf("  " ANSI_GREEN "[PASS]" ANSI_RESET
                   " test_imports: %s imported successfully\n",
                   entity_str);
        }
    }

    return tests_run;
}

/*
 * tester_test_class:
 *   Query LiveState for all events with source=class_name.
 *   Check:
 *     - Did the class emit at least one EVENT_STATE? (class was initialized)
 *     - Did the class emit at least one EVENT_CALL? (methods were called)
 *     - Did the class emit any EVENT_ERROR? (errors during execution)
 *     - Did the class emit EVENT_RESULT? (produced output)
 *   Print PASS/FAIL for each check.
 *   Return 1 if all passed, 0 if any failed.
 */
int tester_test_class(class_tester_t *t, const char *class_name)
{
    uint32_t source_id;
    size_t   i;
    int      event_count = 0;
    int      has_state;
    int      has_call;
    int      has_error;
    int      has_result;
    int      all_passed = 1;

    if (t == NULL || t->state == NULL || class_name == NULL) {
        return 0;
    }

    source_id = str_intern(class_name);

    /* Count events from this source */
    for (i = 0; i < t->state->event_count; i++) {
        if (t->state->events[i].source == source_id) {
            event_count++;
        }
    }

    if (event_count == 0) {
        t->tests_run++;
        t->tests_failed++;
        printf("  " ANSI_RED "[FAIL]" ANSI_RESET
               " test_class %s: no events produced by this class\n",
               class_name);
        return 0;
    }

    has_state  = has_event_kind(t->state, source_id, EVENT_STATE);
    has_call   = has_event_kind(t->state, source_id, EVENT_CALL);
    has_error  = has_event_kind(t->state, source_id, EVENT_ERROR);
    has_result = has_event_kind(t->state, source_id, EVENT_RESULT);

    /* Check 1: EVENT_STATE emitted (class was initialized) */
    t->tests_run++;
    if (has_state) {
        t->tests_passed++;
        printf("  " ANSI_GREEN "[PASS]" ANSI_RESET
               " test_class %s: EVENT_STATE emitted (class initialized)\n",
               class_name);
    } else {
        t->tests_failed++;
        all_passed = 0;
        printf("  " ANSI_RED "[FAIL]" ANSI_RESET
               " test_class %s: no EVENT_STATE emitted\n",
               class_name);
    }

    /* Check 2: EVENT_CALL emitted (methods were called) */
    t->tests_run++;
    if (has_call) {
        t->tests_passed++;
        printf("  " ANSI_GREEN "[PASS]" ANSI_RESET
               " test_class %s: EVENT_CALL emitted (methods called)\n",
               class_name);
    } else {
        t->tests_failed++;
        all_passed = 0;
        printf("  " ANSI_RED "[FAIL]" ANSI_RESET
               " test_class %s: no EVENT_CALL emitted\n",
               class_name);
    }

    /* Check 3: EVENT_ERROR — should NOT have errors (PASS if no errors) */
    t->tests_run++;
    if (!has_error) {
        t->tests_passed++;
        printf("  " ANSI_GREEN "[PASS]" ANSI_RESET
               " test_class %s: no EVENT_ERROR (clean execution)\n",
               class_name);
    } else {
        t->tests_failed++;
        all_passed = 0;
        printf("  " ANSI_RED "[FAIL]" ANSI_RESET
               " test_class %s: EVENT_ERROR emitted (errors during execution)\n",
               class_name);
    }

    /* Check 4: EVENT_RESULT emitted (produced output) */
    t->tests_run++;
    if (has_result) {
        t->tests_passed++;
        printf("  " ANSI_GREEN "[PASS]" ANSI_RESET
               " test_class %s: EVENT_RESULT emitted (produced output)\n",
               class_name);
    } else {
        t->tests_failed++;
        all_passed = 0;
        printf("  " ANSI_RED "[FAIL]" ANSI_RESET
               " test_class %s: no EVENT_RESULT emitted\n",
               class_name);
    }

    return all_passed;
}

/*
 * tester_test_errors:
 *   Query LiveState for all EVENT_ERROR events.
 *   For each error, print: source, entity, name, value, severity.
 *   Check if any errors are unresolved (no corresponding fix event).
 *   Return error count.
 */
int tester_test_errors(class_tester_t *t)
{
    size_t   count = 0;
    event_t *errors = NULL;
    size_t   i;
    int      unresolved = 0;

    if (t == NULL || t->state == NULL) {
        return 0;
    }

    errors = live_state_query_kind(t->state, EVENT_ERROR, &count);

    if (count == 0) {
        t->tests_run++;
        t->tests_passed++;
        printf("  " ANSI_GREEN "[PASS]" ANSI_RESET
               " test_errors: no errors recorded\n");
        return 0;
    }

    for (i = 0; i < count; i++) {
        const char *src_str;
        const char *entity_str;
        int         has_fix;

        src_str    = str_lookup(errors[i].source);
        entity_str = str_lookup(errors[i].entity);

        has_fix = has_fix_for(t->state, errors[i].entity);

        printf("  ");
        if (has_fix) {
            printf(ANSI_YELLOW "[WARN]" ANSI_RESET);
        } else {
            printf(ANSI_RED "[FAIL]" ANSI_RESET);
        }
        printf(" test_errors: source=%s entity=%s name=%s value=%s severity=%u",
               src_str    ? src_str    : "(null)",
               entity_str ? entity_str : "(null)",
               errors[i].name  ? errors[i].name  : "(null)",
               errors[i].value ? errors[i].value : "(null)",
               errors[i].severity);

        if (has_fix) {
            printf(" (resolved)");
        } else {
            printf(" (UNRESOLVED)");
            unresolved++;
        }
        printf("\n");
    }

    t->tests_run += (int)count;
    if (unresolved == 0) {
        /* All errors have fixes — partial pass */
        t->tests_passed++;
        printf("  " ANSI_GREEN "[PASS]" ANSI_RESET
               " test_errors: all %zu errors resolved\n",
               count);
    } else {
        t->tests_failed += unresolved;
        printf("  " ANSI_RED "[FAIL]" ANSI_RESET
               " test_errors: %d of %zu errors unresolved\n",
               unresolved, count);
    }

    return (int)count;
}

/*
 * tester_test_all:
 *   Get all unique class names from LiveState (scan events for entity field
 *   where kind=EVENT_STATE and phase=PHASE_INIT).
 *   For each class, call tester_test_class.
 *   Call tester_test_imports.
 *   Call tester_test_errors.
 *   Print summary: "Tests: N run, M passed, K failed".
 *   Return 0 if all passed, 1 if any failed.
 */
int tester_test_all(class_tester_t *t)
{
    uint32_t classes[MAX_CLASS_NAME];
    int      class_count;
    int      i;
    int      any_failed = 0;

    if (t == NULL || t->state == NULL) {
        return 1;
    }

    printf(ANSI_BOLD "=== ClassTester: test_all ===" ANSI_RESET "\n");

    /* Get unique classes from EVENT_STATE + PHASE_INIT events */
    class_count = get_unique_classes(t->state, classes, MAX_CLASS_NAME);

    if (class_count == 0) {
        printf("  " ANSI_YELLOW "[WARN]" ANSI_RESET
               " test_all: no classes found (no EVENT_STATE/PHASE_INIT events)\n");
    }

    /* Test each class */
    for (i = 0; i < class_count; i++) {
        const char *class_name;
        int         result;

        class_name = str_lookup(classes[i]);
        if (class_name == NULL) {
            continue;
        }
        result = tester_test_class(t, class_name);
        if (result == 0) {
            any_failed = 1;
        }
    }

    /* Test imports */
    tester_test_imports(t);

    /* Test errors */
    tester_test_errors(t);

    /* Print summary */
    printf("\n");
    printf(ANSI_BOLD "Tests: %d run, %d passed, %d failed" ANSI_RESET "\n",
           t->tests_run, t->tests_passed, t->tests_failed);

    if (t->tests_failed > 0) {
        any_failed = 1;
    }

    return any_failed ? 1 : 0;
}
