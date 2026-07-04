//[@GHOST]{file_path="Cascade_toolStack/bcl_units/storage_pool.c" date="2026-07-04" author="Devin" session_id="cpsd-microkernel" context="CPSD Layer 3: Connection pool — per-backend, acquire/release, health check"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE no-print connection-pool"}
//[@FILEID]{id="storage_pool.c" domain="cpsd_storage" authority="CpsdPool"}
//[@SUMMARY]{summary="Connection pool per storage backend. Pre-creates connections, acquire/release with refcount, health check with auto-reconnect. Thread-safe."}
//[@CLASS]{class="CpsdPool" domain="cpsd_storage" authority="single"}
//[@METHOD]{methods="pool_init,pool_shutdown,pool_acquire,pool_release,pool_health_check,pool_stats"}

#include "cpsd.h"
#include <string.h>
#include <stdlib.h>
#include <pthread.h>
#include <time.h>
#include <stdio.h>

// ═══════════════════════════════════════════
// POOL INTERNALS
// ═══════════════════════════════════════════

#define CPSD_POOL_BACKENDS 8

typedef struct {
    void  *handle;
    int    in_use;
    time_t acquired_at;
    time_t last_used;
    int    health_failures;
} pool_entry_t;

typedef struct {
    pool_entry_t     entries[CPSD_POOL_SIZE];
    char            *conn_str;
    int              pool_size;
    pthread_mutex_t  mutex;
    int              initialized;
} pool_t;

static pool_t g_pools[CPSD_POOL_BACKENDS];

// ═══════════════════════════════════════════
// pool_init
// ═══════════════════════════════════════════

int pool_init(storage_backend_t backend, int pool_size, const char *conn_str)
{
    if (backend < 0 || backend >= CPSD_POOL_BACKENDS) {
        return -1;
    }
    if (conn_str == NULL) {
        return -1;
    }
    if (pool_size < 0) {
        return -1;
    }
    if (pool_size > CPSD_POOL_SIZE) {
        pool_size = CPSD_POOL_SIZE;
    }

    pool_t *pool = &g_pools[backend];

    // Defensive: if already initialized, shut it down first.
    if (pool->initialized) {
        pool_shutdown(backend);
    }

    memset(pool, 0, sizeof(*pool));

    pool->conn_str = strdup(conn_str);
    if (pool->conn_str == NULL) {
        return -1;
    }

    pool->pool_size = pool_size;

    if (pthread_mutex_init(&pool->mutex, NULL) != 0) {
        free(pool->conn_str);
        pool->conn_str = NULL;
        return -1;
    }

    // Pre-create connections for each slot.
    for (int i = 0; i < pool_size; i++) {
        pool_entry_t *entry = &pool->entries[i];
        entry->handle       = NULL;
        entry->in_use       = 0;
        entry->acquired_at  = 0;
        entry->last_used    = 0;
        entry->health_failures = 0;

        void *handle = NULL;
        if (storage_connect(backend, pool->conn_str, &handle) == 0) {
            entry->handle    = handle;
            entry->last_used = time(NULL);
        } else {
            // Connection creation failed; leave handle NULL (dead slot).
            entry->handle = NULL;
        }
    }

    pool->initialized = 1;
    return 0;
}

// ═══════════════════════════════════════════
// pool_shutdown
// ═══════════════════════════════════════════

void pool_shutdown(storage_backend_t backend)
{
    if (backend < 0 || backend >= CPSD_POOL_BACKENDS) {
        return;
    }

    pool_t *pool = &g_pools[backend];
    if (!pool->initialized) {
        return;
    }

    pthread_mutex_lock(&pool->mutex);

    for (int i = 0; i < pool->pool_size; i++) {
        pool_entry_t *entry = &pool->entries[i];
        if (entry->handle != NULL) {
            storage_disconnect(backend, entry->handle);
            entry->handle = NULL;
        }
        entry->in_use          = 0;
        entry->acquired_at     = 0;
        entry->last_used       = 0;
        entry->health_failures = 0;
    }

    if (pool->conn_str != NULL) {
        free(pool->conn_str);
        pool->conn_str = NULL;
    }

    pool->pool_size = 0;
    pool->initialized = 0;

    pthread_mutex_unlock(&pool->mutex);
    pthread_mutex_destroy(&pool->mutex);
}

// ═══════════════════════════════════════════
// pool_acquire
// ═══════════════════════════════════════════

int pool_acquire(storage_backend_t backend, void **handle)
{
    if (backend < 0 || backend >= CPSD_POOL_BACKENDS) {
        return -1;
    }
    if (handle == NULL) {
        return -1;
    }

    pool_t *pool = &g_pools[backend];
    if (!pool->initialized) {
        return -1;
    }

    pthread_mutex_lock(&pool->mutex);

    int found = -1;
    for (int i = 0; i < pool->pool_size; i++) {
        pool_entry_t *entry = &pool->entries[i];
        if (!entry->in_use && entry->handle != NULL) {
            found = i;
            break;
        }
    }

    if (found < 0) {
        pthread_mutex_unlock(&pool->mutex);
        return -1; // pool exhausted
    }

    pool_entry_t *entry = &pool->entries[found];
    entry->in_use      = 1;
    entry->acquired_at = time(NULL);
    *handle            = entry->handle;

    pthread_mutex_unlock(&pool->mutex);
    return 0;
}

// ═══════════════════════════════════════════
// pool_release
// ═══════════════════════════════════════════

int pool_release(storage_backend_t backend, void *handle)
{
    if (backend < 0 || backend >= CPSD_POOL_BACKENDS) {
        return -1;
    }
    if (handle == NULL) {
        return -1;
    }

    pool_t *pool = &g_pools[backend];
    if (!pool->initialized) {
        return -1;
    }

    pthread_mutex_lock(&pool->mutex);

    int found = -1;
    for (int i = 0; i < pool->pool_size; i++) {
        pool_entry_t *entry = &pool->entries[i];
        if (entry->handle == handle && entry->in_use) {
            found = i;
            break;
        }
    }

    if (found < 0) {
        pthread_mutex_unlock(&pool->mutex);
        return -1; // handle not found
    }

    pool_entry_t *entry = &pool->entries[found];
    entry->in_use   = 0;
    entry->last_used = time(NULL);

    pthread_mutex_unlock(&pool->mutex);
    return 0;
}

// ═══════════════════════════════════════════
// pool_health_check
// ═══════════════════════════════════════════

int pool_health_check(storage_backend_t backend)
{
    if (backend < 0 || backend >= CPSD_POOL_BACKENDS) {
        return -1;
    }

    pool_t *pool = &g_pools[backend];
    if (!pool->initialized) {
        return -1;
    }

    storage_driver_t *driver = storage_get_driver(backend);
    if (driver == NULL) {
        return -1;
    }

    pthread_mutex_lock(&pool->mutex);

    int healthy = 0;

    for (int i = 0; i < pool->pool_size; i++) {
        pool_entry_t *entry = &pool->entries[i];

        if (entry->handle == NULL) {
            // Dead slot — attempt a fresh connect.
            void *handle = NULL;
            if (storage_connect(backend, pool->conn_str, &handle) == 0) {
                entry->handle          = handle;
                entry->health_failures = 0;
                entry->last_used       = time(NULL);
                healthy++;
            }
            continue;
        }

        if (driver->ping != NULL && driver->ping(entry->handle) == 0) {
            entry->health_failures = 0;
            healthy++;
            continue;
        }

        // Ping failed.
        entry->health_failures++;

        if (entry->health_failures >= 3) {
            // Mark as dead.
            storage_disconnect(backend, entry->handle);
            entry->handle          = NULL;
            entry->health_failures = 0;
            continue;
        }

        // Try to reconnect.
        storage_disconnect(backend, entry->handle);
        entry->handle = NULL;

        void *handle = NULL;
        if (storage_connect(backend, pool->conn_str, &handle) == 0) {
            entry->handle    = handle;
            entry->last_used = time(NULL);
            healthy++;
        }
        // else: stays dead; will be retried on next health check.
    }

    pthread_mutex_unlock(&pool->mutex);
    return healthy;
}

// ═══════════════════════════════════════════
// pool_stats
// ═══════════════════════════════════════════

int pool_stats(storage_backend_t backend, int *total, int *in_use, int *idle)
{
    if (backend < 0 || backend >= CPSD_POOL_BACKENDS) {
        return -1;
    }

    pool_t *pool = &g_pools[backend];
    if (!pool->initialized) {
        if (total)  *total  = 0;
        if (in_use) *in_use = 0;
        if (idle)   *idle   = 0;
        return -1;
    }

    pthread_mutex_lock(&pool->mutex);

    int t = 0, u = 0, d = 0;
    for (int i = 0; i < pool->pool_size; i++) {
        pool_entry_t *entry = &pool->entries[i];
        if (entry->handle == NULL) {
            continue; // dead slot, not counted
        }
        t++;
        if (entry->in_use) {
            u++;
        } else {
            d++;
        }
    }

    if (total)  *total  = t;
    if (in_use) *in_use = u;
    if (idle)   *idle   = d;

    pthread_mutex_unlock(&pool->mutex);
    return 0;
}
