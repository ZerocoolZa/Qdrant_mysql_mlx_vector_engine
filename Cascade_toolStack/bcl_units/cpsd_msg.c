//[@GHOST]{file_path="Cascade_toolStack/bcl_units/cpsd_msg.c" date="2026-07-04" author="Devin" session_id="cpsd-microkernel" context="CPSD Layer 0: Message bus — typed message passing between modules"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE no-print message-queue"}
//[@FILEID]{id="cpsd_msg.c" domain="cpsd_kernel" authority="CpsdMsg"}
//[@SUMMARY]{summary="Message bus for inter-module communication. Thread-safe queue with timeout recv. Messages are typed (request/response/error/notify). Used for async module-to-module communication."}
//[@CLASS]{class="CpsdMsg" domain="cpsd_kernel" authority="single"}
//[@METHOD]{methods="kern_msg_init,kern_msg_shutdown,kern_msg_send,kern_msg_recv"}

#include "cpsd.h"
#include <pthread.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>
#include <errno.h>

#define MSG_QUEUE_SIZE 256

typedef struct {
    message_t msg;
    int in_use;
} msg_slot_t;

static msg_slot_t g_queue[MSG_QUEUE_SIZE];
static int g_head = 0;
static int g_tail = 0;
static int g_count = 0;
static pthread_mutex_t g_msg_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t g_msg_cond = PTHREAD_COND_INITIALIZER;
static int g_initialized = 0;

int kern_msg_init(void) {
    pthread_mutex_lock(&g_msg_mutex);
    memset(g_queue, 0, sizeof(g_queue));
    g_head = 0;
    g_tail = 0;
    g_count = 0;
    g_initialized = 1;
    pthread_mutex_unlock(&g_msg_mutex);
    return 0;
}

void kern_msg_shutdown(void) {
    pthread_mutex_lock(&g_msg_mutex);
    // Free any pending payloads
    while (g_count > 0) {
        if (g_queue[g_head].msg.payload) {
            free(g_queue[g_head].msg.payload);
        }
        g_queue[g_head].in_use = 0;
        g_head = (g_head + 1) % MSG_QUEUE_SIZE;
        g_count--;
    }
    g_initialized = 0;
    pthread_cond_broadcast(&g_msg_cond);
    pthread_mutex_unlock(&g_msg_mutex);
}

int kern_msg_send(message_t *msg) {
    if (!msg) return -1;

    pthread_mutex_lock(&g_msg_mutex);
    if (!g_initialized) {
        pthread_mutex_unlock(&g_msg_mutex);
        return -1;
    }
    if (g_count >= MSG_QUEUE_SIZE) {
        pthread_mutex_unlock(&g_msg_mutex);
        return -1; // queue full
    }

    // Copy message struct
    g_queue[g_tail].msg = *msg;
    g_queue[g_tail].in_use = 1;

    // Deep copy payload if present
    if (msg->payload && msg->payload_len > 0) {
        void *payload_copy = malloc(msg->payload_len);
        if (!payload_copy) {
            pthread_mutex_unlock(&g_msg_mutex);
            return -1;
        }
        memcpy(payload_copy, msg->payload, msg->payload_len);
        g_queue[g_tail].msg.payload = payload_copy;
    } else {
        g_queue[g_tail].msg.payload = NULL;
        g_queue[g_tail].msg.payload_len = 0;
    }

    g_tail = (g_tail + 1) % MSG_QUEUE_SIZE;
    g_count++;

    pthread_cond_signal(&g_msg_cond);
    pthread_mutex_unlock(&g_msg_mutex);
    return 0;
}

int kern_msg_recv(message_t *msg, int timeout_ms) {
    if (!msg) return -1;

    pthread_mutex_lock(&g_msg_mutex);
    if (!g_initialized) {
        pthread_mutex_unlock(&g_msg_mutex);
        return -1;
    }

    // Wait for message or timeout
    if (g_count == 0) {
        if (timeout_ms <= 0) {
            pthread_mutex_unlock(&g_msg_mutex);
            return -1; // no message, no wait
        }

        struct timespec ts;
        clock_gettime(CLOCK_REALTIME, &ts);
        ts.tv_sec += timeout_ms / 1000;
        ts.tv_nsec += (timeout_ms % 1000) * 1000000;
        if (ts.tv_nsec >= 1000000000) {
            ts.tv_sec++;
            ts.tv_nsec -= 1000000000;
        }

        int rc = 0;
        while (g_count == 0 && rc == 0) {
            rc = pthread_cond_timedwait(&g_msg_cond, &g_msg_mutex, &ts);
            if (!g_initialized) {
                pthread_mutex_unlock(&g_msg_mutex);
                return -1;
            }
        }
        if (g_count == 0) {
            pthread_mutex_unlock(&g_msg_mutex);
            return -1; // timeout
        }
    }

    // Pop from queue
    *msg = g_queue[g_head].msg;
    g_queue[g_head].in_use = 0;
    g_head = (g_head + 1) % MSG_QUEUE_SIZE;
    g_count--;

    pthread_mutex_unlock(&g_msg_mutex);
    return 0;
}
