//[@GHOST]{file_path="Cascade_toolStack/bcl_units/cpsd_state.c" date="2026-07-04" author="Devin" session_id="cpsd-microkernel" context="CPSD Layer 0: Kernel state machine — init→loading→ready→draining→stopped"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE no-print state-machine"}
//[@FILEID]{id="cpsd_state.c" domain="cpsd_kernel" authority="CpsdState"}
//[@SUMMARY]{summary="Kernel state machine. Tracks process lifecycle: INIT→LOADING→READY→RELOAD→DRAINING→STOPPED. Thread-safe via mutex. Publishes EVT_STATE_CHANGE on transitions."}
//[@CLASS]{class="CpsdState" domain="cpsd_kernel" authority="single"}
//[@METHOD]{methods="kern_state_name,kern_state_get,kern_state_transition,kern_state_is_serving"}

#include "cpsd.h"
#include <pthread.h>
#include <string.h>
#include <stdio.h>

static kern_state_t g_state = KERN_STATE_INIT;
static pthread_mutex_t g_state_mutex = PTHREAD_MUTEX_INITIALIZER;
static time_t g_state_entered = 0;

static const char* STATE_NAMES[] = {
    "INIT", "LOADING", "READY", "RELOAD", "DRAINING", "STOPPED", "FAULT"
};

const char* kern_state_name(kern_state_t s) {
    if (s < 0 || s > KERN_STATE_FAULT) return "UNKNOWN";
    return STATE_NAMES[s];
}

kern_state_t kern_state_get(void) {
    kern_state_t s;
    pthread_mutex_lock(&g_state_mutex);
    s = g_state;
    pthread_mutex_unlock(&g_state_mutex);
    return s;
}

static bool can_transition(kern_state_t from, kern_state_t to) {
    switch (from) {
        case KERN_STATE_INIT:
            return to == KERN_STATE_LOADING || to == KERN_STATE_FAULT || to == KERN_STATE_STOPPED;
        case KERN_STATE_LOADING:
            return to == KERN_STATE_READY || to == KERN_STATE_FAULT || to == KERN_STATE_STOPPED;
        case KERN_STATE_READY:
            return to == KERN_STATE_RELOAD || to == KERN_STATE_DRAINING || to == KERN_STATE_FAULT;
        case KERN_STATE_RELOAD:
            return to == KERN_STATE_READY || to == KERN_STATE_FAULT || to == KERN_STATE_DRAINING;
        case KERN_STATE_DRAINING:
            return to == KERN_STATE_STOPPED || to == KERN_STATE_FAULT;
        case KERN_STATE_STOPPED:
            return to == KERN_STATE_INIT;
        case KERN_STATE_FAULT:
            return to == KERN_STATE_STOPPED || to == KERN_STATE_DRAINING;
        default:
            return false;
    }
}

int kern_state_transition(kern_state_t target) {
    kern_state_t old;
    pthread_mutex_lock(&g_state_mutex);
    old = g_state;
    if (!can_transition(old, target)) {
        pthread_mutex_unlock(&g_state_mutex);
        return -1;
    }
    g_state = target;
    g_state_entered = time(NULL);
    pthread_mutex_unlock(&g_state_mutex);

    // Publish state change event
    event_t evt;
    evt.type = EVT_STATE_CHANGE;
    evt.timestamp = (uint64_t)time(NULL);
    evt.source_module = MODULE_KERNEL;
    evt.payload = NULL;
    evt.payload_len = 0;
    kern_event_publish(&evt);

    return 0;
}

int kern_state_is_serving(void) {
    kern_state_t s = kern_state_get();
    return (s == KERN_STATE_READY || s == KERN_STATE_RELOAD) ? 1 : 0;
}
