/* cascade.c — thin C launcher for the Cascade job runner.
 *
 * Why C (not zsh): a C launcher is the ultimate "thin entry point". It forks,
 * detaches, redirects stdio, saves the PID, and exits immediately. No shell
 * complexity, no job-control quirks, no zsh timeout traps. All real logic lives
 * in the Python modules it dispatches to.
 *
 * Commands:
 *   cascade run <task> [args...]   -> start a background job, exit immediately
 *   cascade status [job_id]        -> exec cascade_status.py
 *   cascade stop  <job_id>         -> exec cascade_stop.py
 *   cascade resume <job_id>        -> exec cascade_resume.py
 *   cascade list                   -> exec cascade_list.py
 *   cascade logs  <job_id>         -> exec cascade_logs.py
 *   cascade tail  <job_id>         -> exec cascade_tail.py
 *   cascade clean [--force]        -> exec cascade_clean.py
 *
 * Build: make
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>

#define ROOT_DIR  "/Users/wws/Qdrant_mysql_mlx_vector_engine/cascade_runner"
#define PY        "python3"
#define WORKER    ROOT_DIR "/cascade_worker.py"
#define LOG_DIR   ROOT_DIR "/logs"
#define PID_DIR   ROOT_DIR "/pids"
#define DIRS_LEN  4

static const char *DIRS[DIRS_LEN] = { "jobs", "logs", "pids", "state" };

static void ensure_dirs(void) {
    char path[1024];
    for (int i = 0; i < DIRS_LEN; i++) {
        snprintf(path, sizeof(path), "%s/%s", ROOT_DIR, DIRS[i]);
        mkdir(path, 0755); /* ignore EEXIST */
    }
}

/* Build a job id like 20260704-153012-a1b2 */
static void make_job_id(char *out, size_t n) {
    time_t t = time(NULL);
    struct tm tm = *localtime(&t);
    unsigned int r = (unsigned int)((getpid() ^ t) & 0xffff);
    snprintf(out, n, "%04d%02d%02d-%02d%02d%02d-%04x",
             tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday,
             tm.tm_hour, tm.tm_min, tm.tm_sec, r);
}

static int run_background(int argc, char **argv) {
    /* argv = ["run", task, ...] */
    if (argc < 3) {
        fprintf(stderr, "usage: cascade run <task> [args...]\n");
        return 2;
    }
    ensure_dirs();

    char job_id[64];
    make_job_id(job_id, sizeof(job_id));

    char log_path[1024], pid_path[1024];
    snprintf(log_path, sizeof(log_path), "%s/%s.log", LOG_DIR, job_id);
    snprintf(pid_path, sizeof(pid_path), "%s/%s.pid", PID_DIR, job_id);

    pid_t pid = fork();
    if (pid < 0) {
        fprintf(stderr, "cascade: fork failed: %s\n", strerror(errno));
        return 1;
    }

    if (pid == 0) {
        /* ---- child: detach and become a daemon-ish worker ---- */
        setsid(); /* new session, no controlling terminal */

        /* Redirect stdout + stderr into the job log file. */
        int fd = open(log_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (fd < 0) { _exit(127); }
        dup2(fd, STDOUT_FILENO);
        dup2(fd, STDERR_FILENO);
        close(fd);

        /* Detach stdin from the terminal so the worker can't hold it. */
        int dn = open("/dev/null", O_RDONLY);
        if (dn >= 0) { dup2(dn, STDIN_FILENO); close(dn); }

        /* Build the python argv: python3 cascade_worker.py <job_id> <task> [args...] */
        int py_argc = 2 + (argc - 1); /* script + job_id + (task + extra) */
        char **py_argv = calloc(py_argc + 1, sizeof(char *));
        if (!py_argv) { _exit(127); }
        py_argv[0] = WORKER;
        py_argv[1] = job_id;
        for (int i = 2; i < argc; i++) {
            py_argv[i] = argv[i]; /* task + any extra args */
        }
        py_argv[py_argc] = NULL;

        execvp(PY, py_argv);
        /* only reached on exec failure */
        fprintf(stderr, "cascade: exec python failed: %s\n", strerror(errno));
        free(py_argv);
        _exit(127);
    }

    /* ---- parent: record PID, exit immediately ---- */
    FILE *pf = fopen(pid_path, "w");
    if (pf) {
        fprintf(pf, "%d\n", (int)pid);
        fclose(pf);
    }

    printf("%s\n", job_id);
    fflush(stdout);
    return 0;
}

/* Dispatch a subcommand to its python module (foreground, inheriting stdio). */
static int dispatch(const char *module, int argc, char **argv) {
    /* argv[0] = subcommand; pass argv[1..] through to the python module. */
    int py_argc = 1 + (argc - 1); /* script + remaining args */
    char **py_argv = calloc(py_argc + 1, sizeof(char *));
    if (!py_argv) { fprintf(stderr, "cascade: out of memory\n"); return 1; }
    py_argv[0] = (char *)module;
    for (int i = 1; i < argc; i++) py_argv[i] = argv[i];
    py_argv[py_argc] = NULL;

    execvp(PY, py_argv);
    fprintf(stderr, "cascade: exec failed for %s: %s\n", module, strerror(errno));
    free(py_argv);
    return 127;
}

static void usage(void) {
    fprintf(stderr,
        "cascade — background job runner\n\n"
        "  cascade run <task> [args...]   start a job in the background\n"
        "  cascade status [job_id]        show job status\n"
        "  cascade stop <job_id>          stop a running job\n"
        "  cascade resume <job_id>        resume a stopped/failed job\n"
        "  cascade list                   list all jobs\n"
        "  cascade logs <job_id>          print a job's log\n"
        "  cascade tail <job_id>          tail a job's log\n"
        "  cascade clean [--force]        remove old finished jobs\n");
}

int main(int argc, char **argv) {
    if (argc < 2) { usage(); return 2; }
    const char *cmd = argv[1];

    if (strcmp(cmd, "run") == 0) {
        return run_background(argc - 1, argv + 1);
    }
    if (strcmp(cmd, "status") == 0) return dispatch(ROOT_DIR "/cascade_status.py", argc - 1, argv + 1);
    if (strcmp(cmd, "stop") == 0)  return dispatch(ROOT_DIR "/cascade_stop.py",   argc - 1, argv + 1);
    if (strcmp(cmd, "resume") == 0)return dispatch(ROOT_DIR "/cascade_resume.py", argc - 1, argv + 1);
    if (strcmp(cmd, "list") == 0)  return dispatch(ROOT_DIR "/cascade_list.py",   argc - 1, argv + 1);
    if (strcmp(cmd, "logs") == 0)  return dispatch(ROOT_DIR "/cascade_logs.py",   argc - 1, argv + 1);
    if (strcmp(cmd, "tail") == 0)  return dispatch(ROOT_DIR "/cascade_tail.py",   argc - 1, argv + 1);
    if (strcmp(cmd, "clean") == 0) return dispatch(ROOT_DIR "/cascade_clean.py",  argc - 1, argv + 1);

    if (strcmp(cmd, "-h") == 0 || strcmp(cmd, "--help") == 0 || strcmp(cmd, "help") == 0) {
        usage(); return 0;
    }
    fprintf(stderr, "cascade: unknown command '%s'\n", cmd);
    usage();
    return 2;
}
