"""cascade_lib.py — shared helpers for the Cascade job runner.

One module, one responsibility: the plumbing (paths, sqlite schema, job rows,
PID liveness, stale-job detection). Every command module imports this.

Schema (sqlite, state/cascade.db):

    jobs(
        job_id       TEXT PRIMARY KEY,
        command      TEXT,          -- the task name, e.g. "build dom web"
        task         TEXT,          -- first token of command
        status       TEXT,          -- pending|running|done|failed|stopped
        pid          INTEGER,
        started_at   TEXT,          -- ISO8601
        updated_at   TEXT,
        finished_at  TEXT,
        exit_code    INTEGER,
        progress     INTEGER,       -- 0..100
        checkpoint   TEXT,          -- opaque resume marker saved by the worker
        message      TEXT
    )
"""

import os
import sqlite3
import time
import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
JOBS_DIR = os.path.join(ROOT, "jobs")
LOGS_DIR = os.path.join(ROOT, "logs")
PIDS_DIR = os.path.join(ROOT, "pids")
STATE_DIR = os.path.join(ROOT, "state")
DB_PATH = os.path.join(STATE_DIR, "cascade.db")

ST_PENDING = "pending"
ST_RUNNING = "running"
ST_DONE = "done"
ST_FAILED = "failed"
ST_STOPPED = "stopped"

ACTIVE_STATUSES = (ST_PENDING, ST_RUNNING)
FINISHED_STATUSES = (ST_DONE, ST_FAILED, ST_STOPPED)


def ensure_dirs():
    for d in (JOBS_DIR, LOGS_DIR, PIDS_DIR, STATE_DIR):
        os.makedirs(d, exist_ok=True)


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def db():
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs(
            job_id       TEXT PRIMARY KEY,
            command      TEXT,
            task         TEXT,
            status       TEXT,
            pid          INTEGER,
            started_at   TEXT,
            updated_at   TEXT,
            finished_at  TEXT,
            exit_code    INTEGER,
            progress     INTEGER,
            checkpoint   TEXT,
            message      TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        """
    )
    return conn


def log_path(job_id):
    return os.path.join(LOGS_DIR, job_id + ".log")


def pid_path(job_id):
    return os.path.join(PIDS_DIR, job_id + ".pid")


def job_file_path(job_id):
    return os.path.join(JOBS_DIR, job_id + ".job")


def pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False
    return True


def read_pid_file(job_id):
    p = pid_path(job_id)
    if not os.path.exists(p):
        return None
    try:
        with open(p) as f:
            return int(f.read().strip())
    except (ValueError, OSError):
        return None


def get_job(conn, job_id):
    return conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()


def create_job(job_id, command, task, pid=None):
    conn = db()
    conn.execute(
        """INSERT INTO jobs(job_id, command, task, status, pid,
           started_at, updated_at, progress, checkpoint, message)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (job_id, command, task, ST_PENDING, pid, now_iso(), now_iso(), 0, "", ""),
    )
    conn.commit()
    conn.close()
    # also drop a tiny human-readable job file for inspection
    with open(job_file_path(job_id), "w") as f:
        f.write("job_id=%s\ncommand=%s\nstatus=%s\n" % (job_id, command, ST_PENDING))


def update_job(job_id, **fields):
    conn = db()
    fields["updated_at"] = now_iso()
    cols = ", ".join("%s = ?" % k for k in fields)
    vals = list(fields.values()) + [job_id]
    conn.execute("UPDATE jobs SET %s WHERE job_id = ?" % cols, vals)
    conn.commit()
    conn.close()


def list_jobs(status_filter=None):
    conn = db()
    if status_filter:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY started_at DESC",
            (status_filter,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM jobs ORDER BY started_at DESC").fetchall()
    conn.close()
    return rows


def reap_stale():
    """Mark running jobs whose PID is dead as failed (crash recovery)."""
    conn = db()
    rows = conn.execute(
        "SELECT job_id, pid FROM jobs WHERE status = ?", (ST_RUNNING,)
    ).fetchall()
    reaped = []
    for r in rows:
        if not pid_alive(r["pid"]):
            conn.execute(
                """UPDATE jobs SET status = ?, finished_at = ?,
                   message = COALESCE(message,'') || ' [reaped: pid dead]'
                   WHERE job_id = ?""",
                (ST_FAILED, now_iso(), r["job_id"]),
            )
            reaped.append(r["job_id"])
    conn.commit()
    conn.close()
    return reaped
