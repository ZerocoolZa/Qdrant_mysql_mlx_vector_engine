# [@GHOST]{[@file<cleaner.py>][@domain<utility>][@role<cleaner>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<cleaner>][@return<tuple3>][@orch<SystemCheck>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Cleaner — removes __pycache__, .pyc, temp files, empty dirs across project}
# [@WCL]{[@self_contained<true>][@removes<__pycache__|.pyc|.tmp|empty_dirs>][@dry_run<true>]}

import os
import shutil

from . import Config


class Cleaner:
    """Filesystem cleaner — removes build artifacts and empty directories.

    Removes:
    1. __pycache__ directories
    2. .pyc files
    3. .tmp files
    4. .DS_Store files
    5. Empty directories (optional)

    Usage:
        from core.utility.cleaner import Cleaner
        c = Cleaner()
        code, report, err = c.Run("clean", {"path": "/project", "dry_run": True})
    """

    SKIP_DIRS = Config.CLEANER_SKIP_DIRS
    REMOVE_DIRS = Config.CLEANER_REMOVE_DIRS
    REMOVE_EXTS = Config.CLEANER_REMOVE_EXTS

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "removed": [],
            "skipped": [],
            "stats": {},
        }

    def Run(self, command, params=None):
        if command == "clean":
            return self.clean((params or {}).get("path"), (params or {}).get("dry_run", True))
        elif command == "clean_empty_dirs":
            return self.clean_empty_dirs((params or {}).get("path"), (params or {}).get("dry_run", True))
        elif command == "get_report":
            return self.get_report()
        elif command == "read_state":
            return self.read_state()
        return (0, None, ("unknown_command", command, 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self):
        return (1, dict(self.state), None)

    def clean(self, path, dry_run=True):
        if not path or not os.path.isdir(path):
            return (0, None, ("dir_not_found", path or "none", 0))

        self.state["removed"] = []
        self.state["skipped"] = []
        dir_count = 0
        file_count = 0

        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]

            for d in list(dirs):
                if d in self.REMOVE_DIRS:
                    full = os.path.join(root, d)
                    if dry_run:
                        self.state["removed"].append({"type": "dir", "path": full, "dry_run": True})
                    else:
                        shutil.rmtree(full, ignore_errors=True)
                        self.state["removed"].append({"type": "dir", "path": full, "dry_run": False})
                    dir_count += 1
                    dirs.remove(d)

            for fname in files:
                ext = os.path.splitext(fname)[1]
                if ext in self.REMOVE_EXTS or fname in self.REMOVE_EXTS:
                    full = os.path.join(root, fname)
                    if dry_run:
                        self.state["removed"].append({"type": "file", "path": full, "dry_run": True})
                    else:
                        try:
                            os.remove(full)
                            self.state["removed"].append({"type": "file", "path": full, "dry_run": False})
                        except OSError:
                            self.state["skipped"].append({"type": "file", "path": full})
                    file_count += 1

        self.state["stats"] = {
            "dirs_removed": dir_count,
            "files_removed": file_count,
            "dry_run": dry_run,
        }
        return (1, self.state["stats"], None)

    def clean_empty_dirs(self, path, dry_run=True):
        if not path or not os.path.isdir(path):
            return (0, None, ("dir_not_found", path or "none", 0))

        removed = []
        for root, dirs, files in os.walk(path, topdown=False):
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]
            if root == path:
                continue
            if not os.listdir(root):
                if dry_run:
                    removed.append({"path": root, "dry_run": True})
                else:
                    try:
                        os.rmdir(root)
                        removed.append({"path": root, "dry_run": False})
                    except OSError:
                        pass

        self.state["removed"].extend(removed)
        self.state["stats"]["empty_dirs_removed"] = len(removed)
        return (1, {"empty_dirs": len(removed), "dry_run": dry_run}, None)

    def get_report(self):
        lines = []
        for item in self.state["removed"]:
            tag = "DRY" if item.get("dry_run") else "DEL"
            lines.append("[{}] {}".format(tag, item["path"]))
        lines.append("")
        lines.append("Removed: {} items".format(len(self.state["removed"])))
        return (1, "\n".join(lines), None)
