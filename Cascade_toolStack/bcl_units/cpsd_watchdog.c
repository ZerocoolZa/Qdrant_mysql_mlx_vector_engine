//[@GHOST]{file_path="Cascade_toolStack/bcl_units/cpsd_watchdog.c" date="2026-07-04" author="Devin" session_id="cpsd-microkernel" context="CPSD Layer 0: Watchdog timer — detects hung modules"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE no-print watchdog"}
//[@FILEID]{id="cpsd_watchdog.c" domain="cpsd_kernel" authority="CpsdWatchdog"}
//[@SUMMARY]{summary="Watchdog timer. Tracks per-module kick timestamps. Fires callback when module hasn't been kicked within timeout. Thread-safe."}
//[@CLASS]{class="CpsdWatchdog" domain="cpsd_kernel" authority="single"}
//[@METHOD]{methods="kern_watchdog_init,kern_watchdog_shutdown,kern_watchdog_kick,kern_watchdog_check,kern_watchdog_tick"}

#include "cpsd.h"

#include <pthread.h>
#include <time.h>
#include <string.h>
#include <stdio.h>

// ═══════════════════════════════════════════
// WATCHDOG CONSTANTS
// ═══════════════════════════════════════════

#define WATCHDOG_MAX_MODULES 16

// ═══════════════════════════════════════════
// WATCHDOG STATE
// ═══════════════════════════════════════════

typedef struct {
    int                 initialized;
    int                 timeout_sec;
    watchdog_callback_t callback;
    time_t              last_kick[WATCHDOG_MAX_MODULES];
    int                 registered[WATCHDOG_MAX_MODULES];
    pthread_mutex_t     lock;
} watchdog_state_t;

static watchdog_state_t WdState;

// ═══════════════════════════════════════════
// INTERNAL HELPERS
// ═══════════════════════════════════════════

static int WdValidModule(int module_id)
{
    if (module_id < 0 || module_id >= WATCHDOG_MAX_MODULES) {
        return 0;
    }
    return 1;
}

// ═══════════════════════════════════════════
// PUBLIC API
// ═══════════════════════════════════════════

int kern_watchdog_init(int timeout_sec, watchdog_callback_t callback)
{
    if (timeout_sec <= 0) {
        return -1;
    }
    if (callback == NULL) {
        return -1;
    }

    if (pthread_mutex_init(&WdState.lock, NULL) != 0) {
        return -1;
    }

    WdState.timeout_sec = timeout_sec;
    WdState.callback    = callback;
    WdState.initialized = 1;

    memset(WdState.last_kick, 0, sizeof(WdState.last_kick));
    memset(WdState.registered, 0, sizeof(WdState.registered));

    return 0;
}

void kern_watchdog_shutdown(void)
{
    if (!WdState.initialized) {
        return;
    }

    pthread_mutex_lock(&WdState.lock);
    WdState.initialized = 0;
    WdState.timeout_sec = 0;
    WdState.callback    = NULL;
    memset(WdState.last_kick, 0, sizeof(WdState.last_kick));
    memset(WdState.registered, 0, sizeof(WdState.registered));
    pthread_mutex_unlock(&WdState.lock);

    pthread_mutex_destroy(&WdState.lock);
}

int kern_watchdog_kick(int module_id)
{
    if (!WdState.initialized) {
        return -1;
    }
    if (!WdValidModule(module_id)) {
        return -1;
    }

    pthread_mutex_lock(&WdState.lock);

    if (!WdState.registered[module_id]) {
        WdState.registered[module_id] = 1;
    }

    WdState.last_kick[module_id] = time(NULL);

    pthread_mutex_unlock(&WdState.lock);

    return 0;
}

int kern_watchdog_check(void)
{
    int timed_out = 0;

    if (!WdState.initialized) {
        return -1;
    }

    time_t now = time(NULL);

    pthread_mutex_lock(&WdState.lock);

    for (int i = 0; i < WATCHDOG_MAX_MODULES; i++) {
        if (!WdState.registered[i]) {
            continue;
        }

        if ((now - WdState.last_kick[i]) >= WdState.timeout_sec) {
            if (WdState.callback != NULL) {
                WdState.callback(i, "timeout");
            }
            timed_out++;
        }
    }

    pthread_mutex_unlock(&WdState.lock);

    return timed_out;
}

void kern_watchdog_tick(void)
{
    if (!WdState.initialized) {
        return;
    }

    kern_watchdog_check();
}
