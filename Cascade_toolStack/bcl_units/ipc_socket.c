//[@GHOST]{file_path="Cascade_toolStack/bcl_units/ipc_socket.c" date="2026-07-04" author="Devin" session_id="cpsd-microkernel" context="CPSD Layer 1: Unix socket server — AF_UNIX, SOCK_STREAM, 0600 permissions"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE no-print unix-socket"}
//[@FILEID]{id="ipc_socket.c" domain="cpsd_ipc" authority="CpsdSocket"}
//[@SUMMARY]{summary="Unix domain socket server. AF_UNIX, SOCK_STREAM, 0600 permissions. Accepts connections and retrieves peer credentials. Thread-safe."}
//[@CLASS]{class="CpsdSocket" domain="cpsd_ipc" authority="single"}
//[@METHOD]{methods="ipc_socket_init,ipc_socket_accept,ipc_socket_close,ipc_socket_get_fd"}

#include "cpsd.h"

#include <sys/socket.h>
#include <sys/un.h>
#include <sys/ucred.h>
#include <sys/stat.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <stdio.h>
#include <errno.h>

// ═══════════════════════════════════════════
// MODULE STATE (static globals, mutex-guarded)
// ═══════════════════════════════════════════

static int  g_listen_fd   = -1;
static char g_socket_path[sizeof(((struct sockaddr_un *)0)->sun_path)];
static pthread_mutex_t g_socket_mutex = PTHREAD_MUTEX_INITIALIZER;

// ═══════════════════════════════════════════
// LAYER 1: IPC SOCKET TRANSPORT
// ═══════════════════════════════════════════

int ipc_socket_init(const char *path, int backlog) {
    int fd = -1;
    int rc;
    int optval = 1;
    struct sockaddr_un addr;

    if (path == NULL || path[0] == '\0') {
        return -1;
    }

    pthread_mutex_lock(&g_socket_mutex);

    // Refuse double-init without close
    if (g_listen_fd >= 0) {
        pthread_mutex_unlock(&g_socket_mutex);
        return -1;
    }

    // Create AF_UNIX / SOCK_STREAM socket
    fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) {
        pthread_mutex_unlock(&g_socket_mutex);
        return -1;
    }

    // Set SO_REUSEADDR (harmless on AF_UNIX, required by spec)
    rc = setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &optval, sizeof(optval));
    if (rc < 0) {
        close(fd);
        pthread_mutex_unlock(&g_socket_mutex);
        return -1;
    }

    // Build address — guard against path overflow
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    if (strlen(path) >= sizeof(addr.sun_path)) {
        close(fd);
        pthread_mutex_unlock(&g_socket_mutex);
        errno = ENAMETOOLONG;
        return -1;
    }
    strncpy(addr.sun_path, path, sizeof(addr.sun_path) - 1);
    addr.sun_path[sizeof(addr.sun_path) - 1] = '\0';

    // Unlink any pre-existing socket file before bind
    unlink(path);

    // Bind
    rc = bind(fd, (struct sockaddr *)&addr, sizeof(addr));
    if (rc < 0) {
        close(fd);
        pthread_mutex_unlock(&g_socket_mutex);
        return -1;
    }

    // chmod 0600 — owner read/write only (security)
    rc = chmod(path, 0600);
    if (rc < 0) {
        close(fd);
        unlink(path);
        pthread_mutex_unlock(&g_socket_mutex);
        return -1;
    }

    // listen() with default backlog if none provided
    if (backlog <= 0) {
        backlog = CPSD_MAX_CLIENTS;
    }
    rc = listen(fd, backlog);
    if (rc < 0) {
        close(fd);
        unlink(path);
        pthread_mutex_unlock(&g_socket_mutex);
        return -1;
    }

    // Commit state
    g_listen_fd = fd;
    strncpy(g_socket_path, path, sizeof(g_socket_path) - 1);
    g_socket_path[sizeof(g_socket_path) - 1] = '\0';

    pthread_mutex_unlock(&g_socket_mutex);
    return 0;
}

int ipc_socket_accept(int *client_fd, pid_t *client_pid) {
    int clientFd;
    pid_t pid = -1;

    if (client_fd == NULL || client_pid == NULL) {
        return -1;
    }

    pthread_mutex_lock(&g_socket_mutex);

    if (g_listen_fd < 0) {
        pthread_mutex_unlock(&g_socket_mutex);
        return -1;
    }

    clientFd = accept(g_listen_fd, NULL, NULL);
    if (clientFd < 0) {
        pthread_mutex_unlock(&g_socket_mutex);
        return -1;
    }

    // ── Peer credential retrieval (macOS) ──
    // LOCAL_PEERCRED returns a struct xucred containing the peer's UID.
    // LOCAL_PEERPID (if available) returns the peer's PID directly.
    // On macOS there is no portable SO_PEERCRED (that is Linux-specific).
#if defined(__APPLE__) && defined(__MACH__)
    {
        struct xucred cred;
        socklen_t credLen = sizeof(cred);
        memset(&cred, 0, sizeof(cred));

        if (getsockopt(clientFd, SOL_SOCKET, LOCAL_PEERCRED, &cred, &credLen) == 0) {
            // LOCAL_PEERCRED gives uid, not pid on macOS.
            // We stash uid into pid slot as a fallback signal; the auth
            // layer (sec_authenticate) will resolve the real PID via token.
            // Per spec: set pid to -1 if LOCAL_PEERPID unavailable.
            pid = -1;
        }
    }

    // Try LOCAL_PEERPID if defined (newer macOS / iOS)
    #ifdef LOCAL_PEERPID
    {
        pid_t peerPid = -1;
        socklen_t pidLen = sizeof(peerPid);
        if (getsockopt(clientFd, SOL_SOCKET, LOCAL_PEERPID, &peerPid, &pidLen) == 0) {
            pid = peerPid;
        }
    }
    #endif
#else
    // Linux: SO_PEERCRED gives struct ucred with pid, uid, gid
    {
        struct ucred cred;
        socklen_t credLen = sizeof(cred);
        memset(&cred, 0, sizeof(cred));
        if (getsockopt(clientFd, SOL_SOCKET, SO_PEERCRED, &cred, &credLen) == 0) {
            pid = cred.pid;
        }
    }
#endif

    *client_fd = clientFd;
    *client_pid = pid;

    pthread_mutex_unlock(&g_socket_mutex);
    return 0;
}

int ipc_socket_close(void) {
    int fd;
    char path[sizeof(g_socket_path)];

    pthread_mutex_lock(&g_socket_mutex);

    fd = g_listen_fd;
    if (fd >= 0) {
        close(fd);
        g_listen_fd = -1;
    }

    if (g_socket_path[0] != '\0') {
        memcpy(path, g_socket_path, sizeof(path));
        unlink(path);
        g_socket_path[0] = '\0';
    }

    pthread_mutex_unlock(&g_socket_mutex);
    return 0;
}

int ipc_socket_get_fd(void) {
    int fd;

    pthread_mutex_lock(&g_socket_mutex);
    fd = g_listen_fd;
    pthread_mutex_unlock(&g_socket_mutex);
    return fd;
}
