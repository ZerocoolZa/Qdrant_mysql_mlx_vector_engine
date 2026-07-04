//[@GHOST]{file_path="Cascade_toolStack/bcl_units/cpsd_signal.c" date="2026-07-04" author="Devin" session_id="cpsd-microkernel" context="CPSD Layer 0: Signal handling — SIGTERM/SIGHUP/SIGUSR1/SIGPIPE"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE no-print sigaction"}
//[@FILEID]{id="cpsd_signal.c" domain="cpsd_kernel" authority="CpsdSignal"}
//[@SUMMARY]{summary="Signal handling using sigaction. SIGTERM→graceful shutdown, SIGHUP→reload, SIGUSR1→status dump, SIGPIPE→ignore. Thread-safe handler registry."}
//[@CLASS]{class="CpsdSignal" domain="cpsd_kernel" authority="single"}
//[@METHOD]{methods="kern_signal_init,kern_signal_shutdown,kern_signal_register,kern_signal_unregister"}

#include "cpsd.h"
#include <signal.h>
#include <string.h>
#include <pthread.h>
#include <stdio.h>

#define CPSD_MAX_SIGNALS 32

static signal_handler_t g_handlers[CPSD_MAX_SIGNALS];
static pthread_mutex_t g_signal_mutex = PTHREAD_MUTEX_INITIALIZER;
static int g_initialized = 0;

// ═══════════════════════════════════════════
// DISPATCH: looks up registered handler by signo and calls it
// ═══════════════════════════════════════════

static void signal_dispatch(int signo) {
    if (signo < 1 || signo >= CPSD_MAX_SIGNALS) return;
    signal_handler_t h = g_handlers[signo];
    if (h) {
        h(signo);
    }
}

// ═══════════════════════════════════════════
// DEFAULT HANDLERS
// ═══════════════════════════════════════════

// SIGTERM → graceful shutdown → state DRAINING
static void default_sigterm_handler(int signo) {
    (void)signo;
    kern_state_transition(KERN_STATE_DRAINING);
}

// SIGHUP → config reload
static void default_sighup_handler(int signo) {
    (void)signo;
    event_t evt;
    evt.type = EVT_CONFIG_RELOAD;
    evt.timestamp = (uint64_t)time(NULL);
    evt.source_module = MODULE_KERNEL;
    evt.payload = NULL;
    evt.payload_len = 0;
    kern_event_publish(&evt);
}

// SIGUSR1 → status dump
static void default_sigusr1_handler(int signo) {
    (void)signo;
    event_t evt;
    evt.type = EVT_STATE_CHANGE;
    evt.timestamp = (uint64_t)time(NULL);
    evt.source_module = MODULE_KERNEL;
    evt.payload = NULL;
    evt.payload_len = 0;
    kern_event_publish(&evt);
}

// ═══════════════════════════════════════════
// INTERNAL: install dispatch via sigaction for a signo
// ═══════════════════════════════════════════

static int install_sigaction(int signo) {
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = signal_dispatch;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = SA_RESTART;
    if (sigaction(signo, &sa, NULL) != 0) {
        return -1;
    }
    return 0;
}

// ═══════════════════════════════════════════
// PUBLIC API
// ═══════════════════════════════════════════

int kern_signal_init(void) {
    pthread_mutex_lock(&g_signal_mutex);
    if (g_initialized) {
        pthread_mutex_unlock(&g_signal_mutex);
        return 0;
    }
    memset(g_handlers, 0, sizeof(g_handlers));

    // SIGPIPE → always ignored
    struct sigaction sp;
    memset(&sp, 0, sizeof(sp));
    sp.sa_handler = SIG_IGN;
    sigemptyset(&sp.sa_mask);
    if (sigaction(SIGPIPE, &sp, NULL) != 0) {
        pthread_mutex_unlock(&g_signal_mutex);
        return -1;
    }

    // Register default handlers and install dispatch via sigaction
    g_handlers[SIGTERM] = default_sigterm_handler;
    g_handlers[SIGHUP]  = default_sighup_handler;
    g_handlers[SIGUSR1] = default_sigusr1_handler;

    if (install_sigaction(SIGTERM) != 0 ||
        install_sigaction(SIGHUP)  != 0 ||
        install_sigaction(SIGUSR1) != 0) {
        pthread_mutex_unlock(&g_signal_mutex);
        return -1;
    }

    g_initialized = 1;
    pthread_mutex_unlock(&g_signal_mutex);
    return 0;
}

void kern_signal_shutdown(void) {
    pthread_mutex_lock(&g_signal_mutex);
    memset(g_handlers, 0, sizeof(g_handlers));
    g_initialized = 0;
    pthread_mutex_unlock(&g_signal_mutex);
}

int kern_signal_register(int signo, signal_handler_t handler) {
    if (!handler) return -1;
    if (signo < 1 || signo >= CPSD_MAX_SIGNALS) return -1;
    if (signo == SIGPIPE) return -1;  // SIGPIPE always ignored, not overridable

    int rc = -1;
    pthread_mutex_lock(&g_signal_mutex);
    if (g_initialized) {
        g_handlers[signo] = handler;
        // Ensure dispatch is installed for this signo
        if (install_sigaction(signo) != 0) {
            pthread_mutex_unlock(&g_signal_mutex);
            return -1;
        }
        rc = 0;
    }
    pthread_mutex_unlock(&g_signal_mutex);
    return rc;
}

int kern_signal_unregister(int signo) {
    if (signo < 1 || signo >= CPSD_MAX_SIGNALS) return -1;
    if (signo == SIGPIPE) return -1;

    int rc = -1;
    pthread_mutex_lock(&g_signal_mutex);
    if (g_initialized && g_handlers[signo]) {
        g_handlers[signo] = NULL;
        rc = 0;
    }
    pthread_mutex_unlock(&g_signal_mutex);
    return rc;
}
