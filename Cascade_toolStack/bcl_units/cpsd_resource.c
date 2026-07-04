//[@GHOST]{file_path="Cascade_toolStack/bcl_units/cpsd_resource.c" date="2026-07-04" author="Devin" session_id="cpsd-microkernel" context="CPSD Layer 0: Resource limits — clients, memory, file descriptors"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE no-print setrlimit"}
//[@FILEID]{id="cpsd_resource.c" domain="cpsd_kernel" authority="CpsdResource"}
//[@SUMMARY]{summary="Resource limits. Enforces max clients, memory, file descriptors. Uses setrlimit for FD limit. Thread-safe."}
//[@CLASS]{class="CpsdResource" domain="cpsd_kernel" authority="single"}
//[@METHOD]{methods="kern_resource_init,kern_resource_shutdown,kern_resource_check_clients,kern_resource_check_memory,kern_resource_check_fd,kern_resource_get"}

#include "cpsd.h"
#include <sys/resource.h>
#include <string.h>
#include <pthread.h>
#include <stdio.h>

static resource_limits_t g_limits = {
    .max_clients               = 64,
    .max_connections_per_backend = 8,
    .max_memory_mb             = 512,
    .max_file_descriptors      = 1024,
    .max_query_time_ms         = 30000,
    .max_batch_size            = 1000
};

static pthread_mutex_t g_resource_mutex = PTHREAD_MUTEX_INITIALIZER;
static bool g_resource_initialized = false;

int kern_resource_init(resource_limits_t *limits) {
    struct rlimit rl;
    int desired_fd;

    pthread_mutex_lock(&g_resource_mutex);

    if (limits != NULL) {
        memcpy(&g_limits, limits, sizeof(resource_limits_t));
    } else {
        g_limits.max_clients               = 64;
        g_limits.max_connections_per_backend = 8;
        g_limits.max_memory_mb             = 512;
        g_limits.max_file_descriptors      = 1024;
        g_limits.max_query_time_ms         = 30000;
        g_limits.max_batch_size            = 1000;
    }

    desired_fd = g_limits.max_file_descriptors;

    if (getrlimit(RLIMIT_NOFILE, &rl) == 0) {
        if ((rlim_t)desired_fd > rl.rlim_cur) {
            rl.rlim_cur = (rlim_t)desired_fd;
            if ((rlim_t)desired_fd > rl.rlim_max) {
                rl.rlim_max = (rlim_t)desired_fd;
            }
            if (setrlimit(RLIMIT_NOFILE, &rl) != 0) {
                pthread_mutex_unlock(&g_resource_mutex);
                return -1;
            }
        }
    } else {
        pthread_mutex_unlock(&g_resource_mutex);
        return -1;
    }

    g_resource_initialized = true;
    pthread_mutex_unlock(&g_resource_mutex);
    return 0;
}

void kern_resource_shutdown(void) {
    pthread_mutex_lock(&g_resource_mutex);
    g_resource_initialized = false;
    g_limits.max_clients               = 64;
    g_limits.max_connections_per_backend = 8;
    g_limits.max_memory_mb             = 512;
    g_limits.max_file_descriptors      = 1024;
    g_limits.max_query_time_ms         = 30000;
    g_limits.max_batch_size            = 1000;
    pthread_mutex_unlock(&g_resource_mutex);
}

int kern_resource_check_clients(int current) {
    int ok;
    pthread_mutex_lock(&g_resource_mutex);
    ok = (current < g_limits.max_clients) ? 1 : 0;
    pthread_mutex_unlock(&g_resource_mutex);
    return ok;
}

int kern_resource_check_memory(size_t used_bytes) {
    int ok;
    size_t limit_bytes;
    pthread_mutex_lock(&g_resource_mutex);
    limit_bytes = (size_t)g_limits.max_memory_mb * 1024 * 1024;
    ok = (used_bytes <= limit_bytes) ? 1 : 0;
    pthread_mutex_unlock(&g_resource_mutex);
    return ok;
}

int kern_resource_check_fd(int current_fd_count) {
    int ok;
    pthread_mutex_lock(&g_resource_mutex);
    ok = (current_fd_count < g_limits.max_file_descriptors) ? 1 : 0;
    pthread_mutex_unlock(&g_resource_mutex);
    return ok;
}

const resource_limits_t* kern_resource_get(void) {
    const resource_limits_t *ptr;
    pthread_mutex_lock(&g_resource_mutex);
    ptr = &g_limits;
    pthread_mutex_unlock(&g_resource_mutex);
    return ptr;
}
