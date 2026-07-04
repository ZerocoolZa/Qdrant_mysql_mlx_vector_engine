#!/usr/bin/env python3
"""
Auto VBStyle Header Watcher

Watches the workspace for new .py files. When a new .py file is created
that doesn't already have a [@GHOST] header, auto-stamps it with the
VBStyle identity header (date, filename, author) — zero typing needed.

Usage:
    python3 auto_header_watcher.py [--workspace /path] [--dry-run]

Runs in the background. Kill with Ctrl+C or pkill -f auto_header_watcher.
"""

import os
import sys
import time
import datetime
import fcntl

WORKSPACE = os.environ.get("WATCH_WORKSPACE", "/Users/wws/Qdrant_mysql_mlx_vector_engine")
POLL_INTERVAL = 2  # seconds
DRY_RUN = False
SKIP_DIRS = {
    "__pycache__", ".git", "node_modules", ".venv", "venv",
    "storage", "snapshots", "logs", ".tasks", ".devin",
    "code_store_variations", "_tmp_repair_tests", ".build",
}
SKIP_PREFIXES = {".", "_"}
HEADER_TEMPLATE = """#!/usr/bin/env python3
#[@GHOST]{{("file_path={relpath}";"identity={basename}";"purpose=";"date={date}";"version=1.0";"author=Cascade";"chat_link=")}}
#[@VBSTYLE]{{[@Pass]{{"CONFIG";"Tuple3";"report()";"Run()";"self.state";"PascalCase";"UPPERCASE";"spaces"}}[@Fail]{{"print";"decorators";"hardcoded";"self._";"tabs";"trailing_whitespace"}}[@Unsure]{{""}}}}
#[@FILEID]{{("session_id=auto";"context=Auto-stamped by header watcher";"purpose=")}}
#[@SUMMARY]{{("Created on {date}";"auto_stamped=true")}}

"""


def should_skip(path):
    parts = path.split(os.sep)
    for part in parts:
        if part in SKIP_DIRS:
            return True
        if part.startswith("_") and part not in "__pycache__":
            continue
    return False


def has_header(filepath):
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            first_line = f.readline()
            content = f.read(500)
        if "[@GHOST]" in content or "[@VBSTYLE]" in content:
            return True
        if first_line.startswith("#!") and "[@GHOST]" in content:
            return True
        return False
    except Exception:
        return True  # assume it has one if we can't read it


def stamp_file(filepath):
    if has_header(filepath):
        return False
    try:
        existing = ""
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            existing = f.read()
    except Exception:
        existing = ""

    basename = os.path.basename(filepath)
    relpath = os.path.relpath(filepath, WORKSPACE)
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    header = HEADER_TEMPLATE.format(basename=basename, relpath=relpath, date=date_str)

    if DRY_RUN:
        sys.stderr.write("[DRY-RUN] Would stamp: %s\n" % filepath)
        return True

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(header)
            f.write(existing)
        return True
    except Exception as e:
        sys.stderr.write("[ERROR] Could not stamp %s: %s\n" % (filepath, str(e)))
        return False


def scan_workspace(root):
    stamped = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(dirpath, fname)
            if should_skip(fpath):
                continue
            try:
                mtime = os.path.getmtime(fpath)
                age = time.time() - mtime
                if age < POLL_INTERVAL + 1:
                    if stamp_file(fpath):
                        stamped += 1
                        sys.stderr.write("[STAMPED] %s\n" % fpath)
            except Exception:
                pass
    return stamped


def main():
    global DRY_RUN, WORKSPACE
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--dry-run":
            DRY_RUN = True
        elif arg == "--workspace" and i + 1 < len(args):
            WORKSPACE = args[i + 1]

    try:
        fcntl.fcntl(sys.stdout, fcntl.F_SETFL, os.O_NONBLOCK)
    except Exception:
        pass

    sys.stderr.write("[AUTO-HEADER] Watching: %s (dry_run=%s)\n" % (WORKSPACE, DRY_RUN))
    sys.stderr.write("[AUTO-HEADER] Press Ctrl+C to stop\n")

    while True:
        try:
            scan_workspace(WORKSPACE)
        except KeyboardInterrupt:
            sys.stderr.write("\n[AUTO-HEADER] Stopped\n")
            break
        except Exception as e:
            sys.stderr.write("[AUTO-HEADER] Scan error: %s\n" % str(e))
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
