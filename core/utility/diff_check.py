# [@GHOST]{[@file<diff_check.py>][@domain<utility>][@role<diff>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<diff_checker>][@return<tuple3>][@orch<SystemCheck>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Diff checker — compares two index scans, shows added/removed/changed files, classes, methods}
# [@WCL]{[@self_contained<true>][@uses<Indexer>][@output<diff_report>]}

import os
from .indexer import Indexer


class DiffCheck:
    """Diff checker — compares two index snapshots.

    Takes two scan results and reports:
    1. Files added / removed
    2. Classes added / removed
    3. Methods added / removed per class
    4. Domain changes

    Usage:
        from core.utility.diff_check import DiffCheck
        from core.utility.indexer import Indexer

        idx = Indexer()
        idx.Run("scan_dir", {"path": "core/"})
        before = idx.Run("get_index")[1]

        # ... make changes ...

        idx.Run("scan_dir", {"path": "core/"})
        after = idx.Run("get_index")[1]

        dc = DiffCheck()
        code, diff, err = dc.Run("compare", {"before": before, "after": after})
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "last_diff": {},
        }

    def Run(self, command, params=None):
        if command == "compare":
            return self.compare((params or {}).get("before"), (params or {}).get("after"))
        elif command == "compare_dirs":
            return self.compare_dirs((params or {}).get("before_dir"), (params or {}).get("after_dir"))
        elif command == "get_diff":
            return (1, self.state["last_diff"], None)
        elif command == "read_state":
            return self.read_state()
        return (0, None, ("unknown_command", command, 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self):
        return (1, dict(self.state), None)

    def build_file_map(self, index):
        result = {}
        for entry in index:
            result[entry["file_path"]] = entry
        return result

    def build_class_map(self, index):
        result = {}
        for entry in index:
            for cls in entry["classes"]:
                key = "{}.{}".format(entry["file_name"], cls["name"])
                result[key] = {
                    "name": cls["name"],
                    "methods": set(cls["methods"]),
                    "file": entry["file_path"],
                    "domain": entry["domain"],
                    "line_start": cls["line_start"],
                    "line_end": cls["line_end"],
                }
        return result

    def compare(self, before, after):
        if not before or not after:
            return (0, None, ("missing_data", "before and after required", 0))

        before_files = self.build_file_map(before)
        after_files = self.build_file_map(after)
        before_classes = self.build_class_map(before)
        after_classes = self.build_class_map(after)

        files_added = sorted(set(after_files) - set(before_files))
        files_removed = sorted(set(before_files) - set(after_files))

        classes_added = sorted(set(after_classes) - set(before_classes))
        classes_removed = sorted(set(before_classes) - set(after_classes))

        methods_added = []
        methods_removed = []
        for key in set(before_classes) & set(after_classes):
            b_methods = before_classes[key]["methods"]
            a_methods = after_classes[key]["methods"]
            added = a_methods - b_methods
            removed = b_methods - a_methods
            for m in sorted(added):
                methods_added.append("{}.{}".format(key, m))
            for m in sorted(removed):
                methods_removed.append("{}.{}".format(key, m))

        before_domains = set(e["domain"] for e in before)
        after_domains = set(e["domain"] for e in after)
        domains_added = sorted(after_domains - before_domains)
        domains_removed = sorted(before_domains - after_domains)

        diff = {
            "files": {"added": files_added, "removed": files_removed},
            "classes": {"added": classes_added, "removed": classes_removed},
            "methods": {"added": methods_added, "removed": methods_removed},
            "domains": {"added": domains_added, "removed": domains_removed},
            "summary": {
                "files_added": len(files_added),
                "files_removed": len(files_removed),
                "classes_added": len(classes_added),
                "classes_removed": len(classes_removed),
                "methods_added": len(methods_added),
                "methods_removed": len(methods_removed),
            },
        }

        self.state["last_diff"] = diff
        return (1, diff, None)

    def compare_dirs(self, before_dir, after_dir):
        if not before_dir or not os.path.isdir(before_dir):
            return (0, None, ("dir_not_found", before_dir or "none", 0))
        if not after_dir or not os.path.isdir(after_dir):
            return (0, None, ("dir_not_found", after_dir or "none", 0))

        idx = Indexer()
        idx.Run("scan_dir", {"path": before_dir})
        code, before, err = idx.Run("get_index")
        if code != 1:
            return (code, None, err)

        idx2 = Indexer()
        idx2.Run("scan_dir", {"path": after_dir})
        code, after, err = idx2.Run("get_index")
        if code != 1:
            return (code, None, err)

        return self.compare(before, after)
