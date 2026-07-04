//[@GHOST]{file_path="Cascade_toolStack/bcl_units/storage.c" date="2026-07-04" author="Devin" session_id="cpsd-microkernel" context="CPSD Layer 3: Storage driver registry — pluggable backends"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE no-print driver-registry"}
//[@FILEID]{id="storage.c" domain="cpsd_storage" authority="CpsdStorage"}
//[@SUMMARY]{summary="Storage driver registry. Pluggable backends (MySQL, SQLite, Qdrant, etc.). Thread-safe registration and lookup."}
//[@CLASS]{class="CpsdStorage" domain="cpsd_storage" authority="single"}
//[@METHOD]{methods="storage_register,storage_connect,storage_disconnect,storage_get_driver"}

#include "cpsd.h"

#include <string.h>
#include <pthread.h>
#include <stdio.h>

// ═══════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════

#define STORAGE_MAX_SLOTS 8

// ═══════════════════════════════════════════
// DRIVER REGISTRY (STATIC)
// ═══════════════════════════════════════════

static storage_driver_t *DriverRegistry[STORAGE_MAX_SLOTS];
static pthread_mutex_t   RegistryMutex = PTHREAD_MUTEX_INITIALIZER;

// ═══════════════════════════════════════════
// INTERNAL HELPERS
// ═══════════════════════════════════════════

static int BackendInRange(storage_backend_t backend) {
    if (backend < 0 || backend >= STORAGE_MAX_SLOTS) {
        return 0;
    }
    return 1;
}

// ═══════════════════════════════════════════
// PUBLIC API
// ═══════════════════════════════════════════

int storage_register(storage_driver_t *driver) {
    if (driver == NULL) {
        return -1;
    }
    if (!BackendInRange(driver->backend)) {
        return -1;
    }

    pthread_mutex_lock(&RegistryMutex);
    DriverRegistry[driver->backend] = driver;
    pthread_mutex_unlock(&RegistryMutex);

    return 0;
}

int storage_connect(storage_backend_t backend, const char *conn_str, void **handle) {
    if (handle == NULL) {
        return -1;
    }
    *handle = NULL;

    if (!BackendInRange(backend)) {
        return -1;
    }

    storage_driver_t *driver = NULL;

    pthread_mutex_lock(&RegistryMutex);
    driver = DriverRegistry[backend];
    pthread_mutex_unlock(&RegistryMutex);

    if (driver == NULL) {
        return -1;
    }
    if (driver->connect == NULL) {
        return -1;
    }

    int rc = driver->connect(handle, conn_str);
    if (rc != 0) {
        *handle = NULL;
        return -1;
    }

    return 0;
}

int storage_disconnect(storage_backend_t backend, void *handle) {
    if (!BackendInRange(backend)) {
        return -1;
    }

    storage_driver_t *driver = NULL;

    pthread_mutex_lock(&RegistryMutex);
    driver = DriverRegistry[backend];
    pthread_mutex_unlock(&RegistryMutex);

    if (driver == NULL) {
        return -1;
    }
    if (driver->disconnect == NULL) {
        return -1;
    }

    int rc = driver->disconnect(handle);
    if (rc != 0) {
        return -1;
    }

    return 0;
}

storage_driver_t* storage_get_driver(storage_backend_t backend) {
    if (!BackendInRange(backend)) {
        return NULL;
    }

    storage_driver_t *driver = NULL;

    pthread_mutex_lock(&RegistryMutex);
    driver = DriverRegistry[backend];
    pthread_mutex_unlock(&RegistryMutex);

    return driver;
}
