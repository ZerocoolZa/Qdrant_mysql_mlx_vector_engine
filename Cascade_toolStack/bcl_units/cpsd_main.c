//[@GHOST]{file_path="Cascade_toolStack/bcl_units/cpsd_main.c" date="2026-07-04" author="Devin" session_id="cpsd-microkernel" context="CPSD main entry point — startup/shutdown sequences, signal handling, event loop"}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE no-print daemon"}
//[@FILEID]{id="cpsd_main.c" domain="cpsd_kernel" authority="CpsdMain"}
//[@SUMMARY]{summary="Main entry point. 15-step startup, 16-step shutdown, signal handling, event loop. Ties all layers together."}
//[@CLASS]{class="CpsdMain" domain="cpsd_kernel" authority="single"}
//[@METHOD]{methods="main,startup_sequence,shutdown_sequence,handle_sigterm,handle_sighup,handle_sigusr1"}

#include "cpsd.h"
#include <mysql.h>
#include <signal.h>
#include <unistd.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/event.h>   // EVFILT_READ (kqueue filter constant)

// ═══════════════════════════════════════════
// UPPERCASE CONSTANTS
// ═══════════════════════════════════════════

#define EXIT_OK           0
#define EXIT_ERROR        1
#define EXIT_ARGS         2

#define DEFAULT_BACKLOG   64

// ═══════════════════════════════════════════
// GLOBAL SIGNAL FLAGS
// ═══════════════════════════════════════════

static volatile sig_atomic_t g_shutdown = 0;
static volatile sig_atomic_t g_reload   = 0;

// ═══════════════════════════════════════════
// RUNTIME CONFIG (stack/global — no heap struct needed)
// ═══════════════════════════════════════════

static char  g_config_path[1024];
static char  g_socket_path[1024];
static int   g_ipc_port;
static int   g_daemonize;
static int   g_print_version;
static int   g_print_help;

// ═══════════════════════════════════════════
// SIGNAL HANDLERS
// ═══════════════════════════════════════════

static void HandleSigterm(int signo) {
    (void)signo;
    g_shutdown = 1;
    kern_loop_stop();
}

static void HandleSighup(int signo) {
    (void)signo;
    g_reload = 1;
}

static void HandleSigusr1(int signo) {
    (void)signo;
    // Dump status to log
    kern_state_t s = kern_state_get();
    fprintf(stderr, "[cpsd] status: state=%s shutdown=%d reload=%d\n",
        kern_state_name(s), (int)g_shutdown, (int)g_reload);
}

// ═══════════════════════════════════════════
// IPC LISTEN SOCKET CALLBACK
// Fires when the listen socket has a pending accept.
// ═══════════════════════════════════════════

static void HandleListenEvent(int fd, void *userdata) {
    (void)userdata;
    int  client_fd = -1;
    pid_t client_pid = 0;

    int rc = ipc_socket_accept(&client_fd, &client_pid);
    if (rc != 0) {
        fprintf(stderr, "[cpsd] accept failed on listen fd %d\n", fd);
        return;
    }
    fprintf(stderr, "[cpsd] client connected fd=%d pid=%d\n", client_fd, (int)client_pid);
    // Phase 3: hand off client_fd to IPC protocol layer for request handling
}

// ═══════════════════════════════════════════
// ARGUMENT PARSING
// ═══════════════════════════════════════════

static void PrintUsage(const char *prog) {
    fprintf(stderr,
        "cpsd — Cascade Persistent Data Service microkernel daemon\n\n"
        "Usage:\n"
        "  %s [--config FILE] [--socket PATH] [--port N] [--daemonize] [--version] [--help]\n\n"
        "Options:\n"
        "  --config FILE    Path to config file (default: %s)\n"
        "  --socket PATH    Unix socket path for IPC (default: %s)\n"
        "  --port N         IPC port (default: 0 = Unix socket only)\n"
        "  --daemonize      Fork and detach from terminal\n"
        "  --version        Print version and exit\n"
        "  --help, -h       Print this help and exit\n\n"
        "Signals:\n"
        "  SIGTERM          Graceful shutdown\n"
        "  SIGHUP           Reload config\n"
        "  SIGUSR1          Dump status to log\n"
        "  SIGPIPE          Ignored\n",
        prog, CPSD_CONFIG_FILE, CPSD_SOCKET_PATH);
}

static int ParseArgs(int argc, char **argv) {
    int i;
    // Defaults
    strncpy(g_config_path, CPSD_CONFIG_FILE, sizeof(g_config_path) - 1);
    strncpy(g_socket_path, CPSD_SOCKET_PATH, sizeof(g_socket_path) - 1);
    g_ipc_port     = 0;
    g_daemonize    = 0;
    g_print_version = 0;
    g_print_help    = 0;

    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--version") == 0) {
            g_print_version = 1;
        } else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            g_print_help = 1;
        } else if (strcmp(argv[i], "--config") == 0 && i + 1 < argc) {
            strncpy(g_config_path, argv[++i], sizeof(g_config_path) - 1);
            g_config_path[sizeof(g_config_path) - 1] = '\0';
        } else if (strcmp(argv[i], "--socket") == 0 && i + 1 < argc) {
            strncpy(g_socket_path, argv[++i], sizeof(g_socket_path) - 1);
            g_socket_path[sizeof(g_socket_path) - 1] = '\0';
        } else if (strcmp(argv[i], "--port") == 0 && i + 1 < argc) {
            g_ipc_port = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--daemonize") == 0) {
            g_daemonize = 1;
        } else {
            fprintf(stderr, "[cpsd] unknown arg: %s (use --help)\n", argv[i]);
            return -1;
        }
    }
    return 0;
}

// ═══════════════════════════════════════════
// DAEMONIZE
// ═══════════════════════════════════════════

static int Daemonize(void) {
    pid_t pid = fork();
    if (pid < 0) {
        fprintf(stderr, "[cpsd] fork failed: %s\n", strerror(errno));
        return -1;
    }
    if (pid > 0) {
        // Parent exits
        _exit(EXIT_OK);
    }
    // Child becomes session leader
    if (setsid() < 0) {
        fprintf(stderr, "[cpsd] setsid failed: %s\n", strerror(errno));
        return -1;
    }
    // Second fork to prevent reacquiring a controlling terminal
    pid = fork();
    if (pid < 0) {
        fprintf(stderr, "[cpsd] second fork failed: %s\n", strerror(errno));
        return -1;
    }
    if (pid > 0) {
        _exit(EXIT_OK);
    }
    // Reset file mode and redirect std streams to /dev/null
    umask(0);
    chdir("/");
    freopen("/dev/null", "r", stdin);
    freopen("/dev/null", "w", stdout);
    freopen("/dev/null", "w", stderr);
    return 0;
}

// ═══════════════════════════════════════════
// STARTUP SEQUENCE (15 steps in order)
// Returns 0 on success, -1 on failure.
// ═══════════════════════════════════════════

static int StartupSequence(void) {
    int rc;

    // Step 1: Parse args, read config → state INIT
    //   (args already parsed; state starts at INIT by default)
    fprintf(stderr, "[cpsd] startup step 1: config=%s socket=%s port=%d\n",
        g_config_path, g_socket_path, g_ipc_port);
    rc = kern_state_transition(KERN_STATE_LOADING);
    if (rc != 0) {
        fprintf(stderr, "[cpsd] startup step 1 failed: cannot transition INIT→LOADING\n");
        return -1;
    }

    // Step 2: Install signal handlers (SIGTERM, SIGHUP, SIGUSR1, SIGPIPE)
    fprintf(stderr, "[cpsd] startup step 2: install signal handlers\n");
    rc = kern_signal_init();
    if (rc != 0) {
        fprintf(stderr, "[cpsd] startup step 2 failed: kern_signal_init\n");
        return -1;
    }
    kern_signal_register(SIGTERM, HandleSigterm);
    kern_signal_register(SIGHUP,  HandleSighup);
    kern_signal_register(SIGUSR1, HandleSigusr1);
    signal(SIGPIPE, SIG_IGN);  // ignored — never let SIGPIPE kill us

    // Step 3: Init event bus
    fprintf(stderr, "[cpsd] startup step 3: init event bus\n");
    rc = kern_event_init();
    if (rc != 0) {
        fprintf(stderr, "[cpsd] startup step 3 failed: kern_event_init\n");
        return -1;
    }

    // Step 4: Init event loop (kqueue)
    fprintf(stderr, "[cpsd] startup step 4: init event loop\n");
    rc = kern_loop_init();
    if (rc != 0) {
        fprintf(stderr, "[cpsd] startup step 4 failed: kern_loop_init\n");
        return -1;
    }

    // Step 5: Init logging
    fprintf(stderr, "[cpsd] startup step 5: init logging\n");
    rc = log_init(CPSD_LOG_DIR);
    if (rc != 0) {
        fprintf(stderr, "[cpsd] startup step 5 failed: log_init\n");
        return -1;
    }

    // Step 6: Register storage drivers, connect to backends, verify schema
    fprintf(stderr, "[cpsd] startup step 6: storage drivers + backends\n");
    // Phase 3: storage_init() — register drivers, connect backends, verify schema

    // Step 7: Init connection pools per backend
    fprintf(stderr, "[cpsd] startup step 7: connection pools\n");
    // Phase 3: pool_init() per backend

    // Step 8: Prepare all statements in query registry, cache them
    fprintf(stderr, "[cpsd] startup step 8: query registry + prepared statements\n");
    // Phase 3: query_registry_init() + prepare all statements

    // Step 9: Init caches, warm metadata cache
    fprintf(stderr, "[cpsd] startup step 9: caches\n");
    // Phase 3: cache_init() + warm metadata cache

    // Step 10: Load roles, ACL, tokens (security)
    fprintf(stderr, "[cpsd] startup step 10: security (roles, ACL, tokens)\n");
    // Phase 3: sec_auth_init()

    // Step 11: Load plugins, register hooks
    fprintf(stderr, "[cpsd] startup step 11: plugins + hooks\n");
    // Phase 3: plugin_init()

    // Step 12: Open WAL file, replay if needed
    fprintf(stderr, "[cpsd] startup step 12: WAL\n");
    // Phase 3: wal_init(CPSD_WAL_FILE) + wal_replay()

    // Step 13: Start health monitor
    fprintf(stderr, "[cpsd] startup step 13: health monitor\n");
    // Phase 3: health_init()

    // Step 14: Create Unix socket, start listening (IPC)
    fprintf(stderr, "[cpsd] startup step 14: IPC socket\n");
    rc = ipc_socket_init(g_socket_path, DEFAULT_BACKLOG);
    if (rc != 0) {
        fprintf(stderr, "[cpsd] startup step 14 failed: ipc_socket_init (%s)\n", g_socket_path);
        return -1;
    }
    rc = kern_loop_add(ipc_socket_get_fd(), EVFILT_READ, HandleListenEvent, NULL);
    if (rc != 0) {
        fprintf(stderr, "[cpsd] startup step 14 failed: kern_loop_add listen fd\n");
        return -1;
    }

    // Step 15: Transition to READY state
    fprintf(stderr, "[cpsd] startup step 15: transition to READY\n");
    rc = kern_state_transition(KERN_STATE_READY);
    if (rc != 0) {
        fprintf(stderr, "[cpsd] startup step 15 failed: cannot transition LOADING→READY\n");
        return -1;
    }

    fprintf(stderr, "[cpsd] startup complete — state=%s\n",
        kern_state_name(kern_state_get()));
    return 0;
}

// ═══════════════════════════════════════════
// SHUTDOWN SEQUENCE (16 steps in reverse)
// ═══════════════════════════════════════════

static void ShutdownSequence(void) {
    // Step 1: Transition to DRAINING
    fprintf(stderr, "[cpsd] shutdown step 1: transition to DRAINING\n");
    kern_state_transition(KERN_STATE_DRAINING);

    // Step 2: Stop accepting, close listen socket
    fprintf(stderr, "[cpsd] shutdown step 2: close listen socket\n");
    kern_loop_remove(ipc_socket_get_fd(), EVFILT_READ);
    ipc_socket_close();

    // Step 3: Wait for in-flight requests
    fprintf(stderr, "[cpsd] shutdown step 3: wait for in-flight requests\n");
    // Phase 3: drain in-flight request queue

    // Step 4: Flush WAL, close file
    fprintf(stderr, "[cpsd] shutdown step 4: flush WAL\n");
    // Phase 3: wal_shutdown()

    // Step 5: Unload plugins
    fprintf(stderr, "[cpsd] shutdown step 5: unload plugins\n");
    // Phase 3: plugin_shutdown()

    // Step 6: Stop health monitor
    fprintf(stderr, "[cpsd] shutdown step 6: stop health monitor\n");
    // Phase 3: health_shutdown()

    // Step 7: Flush caches
    fprintf(stderr, "[cpsd] shutdown step 7: flush caches\n");
    // Phase 3: cache_shutdown()

    // Step 8: Close prepared statements
    fprintf(stderr, "[cpsd] shutdown step 8: close prepared statements\n");
    // Phase 3: query_registry_shutdown()

    // Step 9: Close all pool connections
    fprintf(stderr, "[cpsd] shutdown step 9: close pool connections\n");
    // Phase 3: pool_shutdown() per backend

    // Step 10: Disconnect storage backends
    fprintf(stderr, "[cpsd] shutdown step 10: disconnect storage backends\n");
    // Phase 3: storage_disconnect() per backend

    // Step 11: Clear credentials from memory
    fprintf(stderr, "[cpsd] shutdown step 11: clear credentials\n");
    // Phase 3: sec_auth_shutdown() — zero credentials buffers

    // Step 12: Flush logs
    fprintf(stderr, "[cpsd] shutdown step 12: flush logs\n");
    log_shutdown();

    // Step 13: Destroy event loop
    fprintf(stderr, "[cpsd] shutdown step 13: destroy event loop\n");
    kern_loop_shutdown();

    // Step 14: Destroy event bus
    fprintf(stderr, "[cpsd] shutdown step 14: destroy event bus\n");
    kern_event_shutdown();

    // Step 15: Restore signal handlers
    fprintf(stderr, "[cpsd] shutdown step 15: restore signal handlers\n");
    kern_signal_shutdown();

    // Step 16: Transition to STOPPED, exit
    fprintf(stderr, "[cpsd] shutdown step 16: transition to STOPPED\n");
    kern_state_transition(KERN_STATE_STOPPED);
    fprintf(stderr, "[cpsd] shutdown complete — state=%s\n",
        kern_state_name(kern_state_get()));
}

// ═══════════════════════════════════════════
// MAIN ENTRY POINT
// ═══════════════════════════════════════════

int main(int argc, char **argv) {
    int rc;

    // MySQL library init — before anything else
    mysql_library_init(0, NULL, NULL);

    // Parse args
    rc = ParseArgs(argc, argv);
    if (rc != 0) {
        mysql_library_end();
        return EXIT_ARGS;
    }

    // --help
    if (g_print_help) {
        PrintUsage(argv[0]);
        mysql_library_end();
        return EXIT_OK;
    }

    // --version
    if (g_print_version) {
        fprintf(stderr, "cpsd %s (Cascade Persistent Data Service)\n", CPSD_VERSION);
        mysql_library_end();
        return EXIT_OK;
    }

    // --daemonize: fork and detach
    if (g_daemonize) {
        rc = Daemonize();
        if (rc != 0) {
            mysql_library_end();
            return EXIT_ERROR;
        }
    }

    // Run startup sequence
    rc = StartupSequence();
    if (rc != 0) {
        fprintf(stderr, "[cpsd] startup failed — running partial shutdown\n");
        // Partial shutdown: clean up whatever was initialized
        ShutdownSequence();
        mysql_library_end();
        return EXIT_ERROR;
    }

    // Enter main event loop (blocks until shutdown)
    fprintf(stderr, "[cpsd] entering main event loop\n");
    rc = kern_loop_run();
    (void)rc;

    // After loop exits (g_shutdown was set by SIGTERM), run shutdown sequence
    fprintf(stderr, "[cpsd] event loop exited — beginning shutdown\n");
    ShutdownSequence();

    // MySQL library cleanup — at the very end
    mysql_library_end();

    return EXIT_OK;
}
