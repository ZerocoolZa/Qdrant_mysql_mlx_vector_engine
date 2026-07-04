#!/usr/bin/env python3
"""cascade_status.py — show job status.

    cascade status            -> table of all jobs (after reaping stale ones)
    cascade status <job_id>   -> detail for one job
"""

import sys
import cascade_lib as lib


def fmt_row(r):
    return "%-20s %-9s %3d%%  %-8s  %s" % (
        r["job_id"], r["status"], r["progress"] or 0,
        str(r["pid"] or "-"), r["command"] or "",
    )


def main(argv):
    lib.reap_stale()
    if len(argv) >= 2:
        job_id = argv[1]
        conn = lib.db()
        r = lib.get_job(conn, job_id)
        conn.close()
        if r is None:
            print("no such job: %s" % job_id, file=sys.stderr)
            return 1
        print("job_id:     %s" % r["job_id"])
        print("command:    %s" % (r["command"] or ""))
        print("status:     %s" % r["status"])
        print("progress:   %d%%" % (r["progress"] or 0))
        print("pid:        %s" % (r["pid"] or "-"))
        print("started:    %s" % (r["started_at"] or ""))
        print("updated:    %s" % (r["updated_at"] or ""))
        print("finished:   %s" % (r["finished_at"] or ""))
        print("exit_code:  %s" % (r["exit_code"] if r["exit_code"] is not None else "-"))
        print("checkpoint: %s" % (r["checkpoint"] or ""))
        print("message:    %s" % (r["message"] or ""))
        print("log:        %s" % lib.log_path(job_id))
        return 0

    rows = lib.list_jobs()
    if not rows:
        print("no jobs yet. try: cascade run demo")
        return 0
    print("%-20s %-9s %4s  %-8s  %s" % ("JOB_ID", "STATUS", "PROG", "PID", "COMMAND"))
    for r in rows:
        print(fmt_row(r))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
