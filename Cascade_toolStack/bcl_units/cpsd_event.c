//[@GHOST]{file_path="Cascade_toolStack/bcl_units/cpsd_event.c" date="2026-07-04" author="Devin" session_id="cpsd-microkernel" context="CPSD Layer 0: Event bus — publish/subscribe for internal events"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE no-print pubsub"}
//[@FILEID]{id="cpsd_event.c" domain="cpsd_kernel" authority="CpsdEvent"}
//[@SUMMARY]{summary="Event bus. Publish/subscribe pattern. Up to 8 handlers per event type. Thread-safe via mutex. Synchronous dispatch (handlers run in publisher's thread)."}
//[@CLASS]{class="CpsdEvent" domain="cpsd_kernel" authority="single"}
//[@METHOD]{methods="kern_event_init,kern_event_shutdown,kern_event_subscribe,kern_event_unsubscribe,kern_event_publish"}

#include "cpsd.h"
#include <pthread.h>
#include <string.h>
#include <stdlib.h>

#define MAX_HANDLERS_PER_TYPE 8
#define MAX_EVENT_TYPES 64

typedef struct {
    event_handler_t handlers[MAX_HANDLERS_PER_TYPE];
    int count;
} event_slot_t;

static event_slot_t g_slots[MAX_EVENT_TYPES];
static pthread_mutex_t g_event_mutex = PTHREAD_MUTEX_INITIALIZER;
static int g_initialized = 0;

int kern_event_init(void) {
    pthread_mutex_lock(&g_event_mutex);
    memset(g_slots, 0, sizeof(g_slots));
    g_initialized = 1;
    pthread_mutex_unlock(&g_event_mutex);
    return 0;
}

void kern_event_shutdown(void) {
    pthread_mutex_lock(&g_event_mutex);
    memset(g_slots, 0, sizeof(g_slots));
    g_initialized = 0;
    pthread_mutex_unlock(&g_event_mutex);
}

int kern_event_subscribe(event_type_t type, event_handler_t handler) {
    if (!handler) return -1;
    if (type < 1 || type >= MAX_EVENT_TYPES) return -1;

    int rc = -1;
    pthread_mutex_lock(&g_event_mutex);
    if (g_initialized && g_slots[type].count < MAX_HANDLERS_PER_TYPE) {
        // Check for duplicate
        for (int i = 0; i < g_slots[type].count; i++) {
            if (g_slots[type].handlers[i] == handler) {
                pthread_mutex_unlock(&g_event_mutex);
                return 0; // already subscribed
            }
        }
        g_slots[type].handlers[g_slots[type].count++] = handler;
        rc = 0;
    }
    pthread_mutex_unlock(&g_event_mutex);
    return rc;
}

int kern_event_unsubscribe(event_type_t type, event_handler_t handler) {
    if (!handler) return -1;
    if (type < 1 || type >= MAX_EVENT_TYPES) return -1;

    int rc = -1;
    pthread_mutex_lock(&g_event_mutex);
    if (g_initialized) {
        for (int i = 0; i < g_slots[type].count; i++) {
            if (g_slots[type].handlers[i] == handler) {
                // Shift remaining handlers down
                for (int j = i; j < g_slots[type].count - 1; j++) {
                    g_slots[type].handlers[j] = g_slots[type].handlers[j + 1];
                }
                g_slots[type].count--;
                rc = 0;
                break;
            }
        }
    }
    pthread_mutex_unlock(&g_event_mutex);
    return rc;
}

int kern_event_publish(event_t *evt) {
    if (!evt) return -1;
    if (evt->type < 1 || evt->type >= MAX_EVENT_TYPES) return -1;

    // Copy handler list under lock, then dispatch outside lock
    // to prevent deadlock if handler publishes another event
    event_handler_t handlers_to_call[MAX_HANDLERS_PER_TYPE];
    int handler_count = 0;

    pthread_mutex_lock(&g_event_mutex);
    if (g_initialized) {
        handler_count = g_slots[evt->type].count;
        memcpy(handlers_to_call, g_slots[evt->type].handlers,
               handler_count * sizeof(event_handler_t));
    }
    pthread_mutex_unlock(&g_event_mutex);

    for (int i = 0; i < handler_count; i++) {
        handlers_to_call[i](evt);
    }

    return handler_count;
}
