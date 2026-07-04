"""cascade_worker.py — the background worker.

Started by the C launcher as a detached child (setsid, stdio redirected to
logs/<job_id>.log). It:

  * registers SIGTERM/SIGINT handlers so `cascade stop` is graceful
  * marks the job running and records its own PID
  * runs the named task from a TASKS registry, passing a checkpoint so a
    stopped/failed job can be resumed
  * checkpoints progress periodically
  * on normal completion marks the job done with an exit code
  * on SIGTERM marks the job stopped and saves a checkpoint for resume

Usage:
    python3 cascade_worker.py <job_id> <task> [args...]

Adding a real task: register it in TASKS below. Each task is a function

    def my_task(ctx, args):
        ...

where ctx exposes:
    ctx.set_progress(pct)
    ctx.checkpoint(marker)        # save resume marker
    ctx.log(msg)                  # write to the job log (stdout)
    ctx.should_stop()             # True if a stop was requested
    ctx.resume_from               # checkpoint string from a previous run, or ""
"""

import os
import sys
import signal
import time
import traceback

import cascade_lib as lib


class StopRequested(Exception):
    pass


class WorkerContext:
    def __init__(self, job_id, resume_from=""):
        self.job_id = job_id
        self.resume_from = resume_from or ""
        self._stop = False

    def set_progress(self, pct):
        pct = max(0, min(100, int(pct)))
        lib.update_job(self.job_id, progress=pct)

    def checkpoint(self, marker):
        lib.update_job(self.job_id, checkpoint=str(marker))

    def log(self, msg):
        print("[%s] %s" % (lib.now_iso(), msg), flush=True)

    def request_stop(self):
        self._stop = True

    def should_stop(self):
        return self._stop


# --------------------------------------------------------------------------- #
# Task registry
#
# Each task: task_fn(ctx, args: list[str]) -> int (exit code, 0 = success)
#
# `demo` is a long, checkpointable loop so you can see run/status/stop/resume
# working end to end. Replace these with your real work (build, graph, scan...).
# --------------------------------------------------------------------------- #

def task_demo(ctx, args):
    total = 30
    start = 0
    if ctx.resume_from:
        try:
            start = int(ctx.resume_from)
        except ValueError:
            start = 0
    ctx.log("demo task starting at step %d/%d" % (start, total))
    for i in range(start, total):
        if ctx.should_stop():
            ctx.log("demo task stopped at step %d" % i)
            ctx.checkpoint(i)
            return 130  # 128 + SIGINT-ish
        ctx.log("demo step %d/%d" % (i + 1, total))
        ctx.set_progress(int((i + 1) * 100 / total))
        ctx.checkpoint(i + 1)
        time.sleep(1)
    ctx.log("demo task complete")
    return 0


def task_build(ctx, args):
    ctx.log("build args=%r (stub — plug your build pipeline in here)" % args)
    for i in range(5):
        if ctx.should_stop():
            ctx.checkpoint(i)
            return 130
        ctx.set_progress((i + 1) * 20)
        ctx.log("build phase %d" % (i + 1))
        time.sleep(1)
    return 0


def task_graph(ctx, args):
    ctx.log("graph args=%r (stub)" % args)
    ctx.set_progress(100)
    return 0


def task_scan(ctx, args):
    ctx.log("scan args=%r (stub)" % args)
    ctx.set_progress(100)
    return 0


def task_search(ctx, args):
    ctx.log("search args=%r (stub)" % args)
    ctx.set_progress(100)
    return 0


TASKS = {
    "demo": task_demo,
    "build": task_build,
    "graph": task_graph,
    "scan": task_scan,
    "search": task_search,
}


# --------------------------------------------------------------------------- #
# Worker lifecycle
# --------------------------------------------------------------------------- #

_CTX = None  # set in main so signal handlers can reach it


def _handle_stop(signum, frame):
    if _CTX is not None:
        _CTX.log("received signal %d — requesting stop" % signum)
        _CTX.request_stop()


def main(argv):
    global _CTX
    if len(argv) < 3:
        print("usage: cascade_worker.py <job_id> <task> [args...]", file=sys.stderr)
        return 2

    job_id = argv[1]
    task_name = argv[2]
    task_args = argv[3:]
    command = " ".join([task_name] + task_args)

    if task_name not in TASKS:
        print("worker: unknown task '%s'" % task_name, file=sys.stderr)
        lib.update_job(job_id, status=lib.ST_FAILED,
                       finished_at=lib.now_iso(), exit_code=2,
                       message="unknown task: %s" % task_name)
        return 2

    # If the job row doesn't exist yet (first run), create it. On resume it
    # already exists with a checkpoint.
    conn = lib.db()
    row = lib.get_job(conn, job_id)
    conn.close()
    resume_from = ""
    if row is None:
        lib.create_job(job_id, command, task_name, pid=os.getpid())
    else:
        resume_from = row["checkpoint"] or ""

    ctx = WorkerContext(job_id, resume_from)
    _CTX = ctx

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    lib.update_job(job_id, status=lib.ST_RUNNING, pid=os.getpid(),
                   message="running" + (" (resumed)" if resume_from else ""))
    ctx.log("worker pid=%d task=%s args=%r resume_from=%r"
            % (os.getpid(), task_name, task_args, resume_from))

    exit_code = 0
    try:
        exit_code = TASKS[task_name](ctx, task_args)
    except StopRequested:
        ctx.checkpoint(ctx.resume_from)
        lib.update_job(job_id, status=lib.ST_STOPPED, finished_at=lib.now_iso(),
                       exit_code=130, message="stopped by signal")
        return 130
    except Exception as exc:
        tb = traceback.format_exc()
        ctx.log("worker crashed:\n%s" % tb)
        lib.update_job(job_id, status=lib.ST_FAILED, finished_at=lib.now_iso(),
                       exit_code=1, message="error: %s" % exc)
        return 1

    if ctx.should_stop():
        lib.update_job(job_id, status=lib.ST_STOPPED, finished_at=lib.now_iso(),
                       exit_code=exit_code, message="stopped")
        return exit_code

    lib.update_job(job_id, status=lib.ST_DONE, finished_at=lib.now_iso(),
                   progress=100, exit_code=exit_code, message="completed")
    ctx.log("worker finished exit_code=%d" % exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
