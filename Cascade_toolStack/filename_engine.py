#!/usr/bin/env python3

#[@GHOST]{[@file<filename_engine.py>][@domain<Cascade_toolStack>][@role<filename_transform>][@auth<cascade>][@date<2026-06-29>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<filename_transform>][@return<Tuple3>][@no<decorators|print|hardcoded_paths>]}

"""
Filename Transformation Engine.

Deterministic filename normalization with rule-driven pipeline.
Scan -> Detect pattern -> Apply transform -> Emit rename.

Usage:
  python3 filename_engine.py scan <folder>
  python3 filename_engine.py rename <folder> [--prefix Plf_] [--case pascal] [--dry-run]
  python3 filename_engine.py rename <folder> --prefix Plf_ --case snake
"""

import os
import re
import json
import sys
from typing import List, Dict, Any, Optional, Tuple, Callable

EXT_MAP = {
    ".rmd.md": ".rmd.md",
    ".md": ".md",
    ".py": ".py",
    ".c": ".c",
    ".h": ".h",
    ".sh": ".sh",
    ".sql": ".sql",
    ".json": ".json",
    ".yaml": ".yaml",
    ".yml": ".yml",
    ".txt": ".txt",
    ".svg": ".svg",
    ".db": ".db",
    ".swift": ".swift",
    ".go": ".go",
    ".rs": ".rs",
}


class FilenameEngine:
    """Rule-driven filename transformation engine."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state = {
            "prefix": self.param.get("prefix", "Plf_"),
            "target_case": self.param.get("case", "pascal"),
            "dry_run": self.param.get("dry_run", False),
            "ext_map": self.param.get("ext_map", EXT_MAP),
            "skip_prefix": self.param.get("skip_prefix", "Plf_"),
            "stats": {"scanned": 0, "renamed": 0, "skipped": 0, "errors": 0},
        }

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        if command == "scan":
            return self.scan_folder(params)
        if command == "rename":
            return self.rename_folder(params)
        if command == "detect":
            return self.detect_pattern(params)
        if command == "transform":
            return self.transform_name(params)
        if command == "stats":
            return self.get_stats(params)
        return (0, None, (1, "unknown command", 0))

    def _split_ext(self, filename):
        for ext in sorted(self.state["ext_map"].keys(), key=len, reverse=True):
            if filename.endswith(ext):
                stem = filename[:-len(ext)]
                return stem, ext
        base, ext = os.path.splitext(filename)
        return base, ext

    def _detect_case(self, stem):
        if "_" in stem:
            return "snake"
        if re.search(r"[a-z][A-Z]", stem):
            return "camel"
        if stem == stem.upper() and len(stem) > 1:
            return "upper"
        if stem[:1].isupper():
            return "pascal"
        return "unknown"

    def _to_pascal(self, stem):
        parts = re.split(r"[_\-\s\.]+", stem)
        result = ""
        for p in parts:
            if p:
                digit_prefix = ""
                while p and p[0].isdigit():
                    digit_prefix += p[0]
                    p = p[1:]
                if p:
                    result += digit_prefix + p[:1].upper() + p[1:].lower()
                else:
                    result += digit_prefix
        return result

    def _to_snake(self, stem):
        pascal = self._to_pascal(stem)
        s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", pascal)
        s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
        return s2.lower()

    def _to_camel(self, stem):
        pascal = self._to_pascal(stem)
        if not pascal:
            return pascal
        return pascal[:1].lower() + pascal[1:]

    def _apply_case(self, stem, target_case):
        if target_case == "pascal":
            return self._to_pascal(stem)
        if target_case == "snake":
            return self._to_snake(stem)
        if target_case == "camel":
            return self._to_camel(stem)
        if target_case == "upper":
            return stem.upper().replace("-", "_").replace(" ", "_")
        return stem

    def _add_prefix(self, name, prefix):
        if prefix and not name.startswith(prefix):
            return prefix + name
        return name

    def _should_skip(self, filename):
        if filename.startswith(self.state["skip_prefix"]):
            return True
        if filename.startswith("."):
            return True
        return False

    def transform_name(self, params):
        filename = self._p(params, "filename")
        if not filename:
            return (0, None, (1, "no filename", 0))
        prefix = self._p(params, "prefix", self.state["prefix"])
        target_case = self._p(params, "case", self.state["target_case"])
        if self._should_skip(filename):
            return (1, {"original": filename, "new": filename, "skipped": True}, None)
        stem, ext = self._split_ext(filename)
        detected = self._detect_case(stem)
        transformed = self._apply_case(stem, target_case)
        final = self._add_prefix(transformed, prefix) + ext
        return (1, {
            "original": filename,
            "new": final,
            "stem": stem,
            "ext": ext,
            "detected_case": detected,
            "target_case": target_case,
            "skipped": False,
        }, None)

    def detect_pattern(self, params):
        filename = self._p(params, "filename")
        if not filename:
            return (0, None, (1, "no filename", 0))
        stem, ext = self._split_ext(filename)
        case = self._detect_case(stem)
        has_prefix = filename.startswith(self.state["skip_prefix"])
        return (1, {
            "filename": filename,
            "stem": stem,
            "ext": ext,
            "case": case,
            "has_prefix": has_prefix,
        }, None)

    def scan_folder(self, params):
        folder = self._p(params, "folder")
        if not folder or not os.path.isdir(folder):
            return (0, None, (1, "invalid folder", 0))
        prefix = self._p(params, "prefix", self.state["prefix"])
        target_case = self._p(params, "case", self.state["target_case"])
        results = []
        for f in sorted(os.listdir(folder)):
            fpath = os.path.join(folder, f)
            if not os.path.isfile(fpath):
                continue
            self.state["stats"]["scanned"] += 1
            rc, data, err = self.transform_name({
                "filename": f,
                "prefix": prefix,
                "case": target_case,
            })
            if rc == 1:
                data["folder"] = folder
                data["path"] = fpath
                if data.get("skipped"):
                    self.state["stats"]["skipped"] += 1
                elif data["original"] != data["new"]:
                    data["will_rename"] = True
                else:
                    data["will_rename"] = False
                results.append(data)
        return (1, results, None)

    def rename_folder(self, params):
        folder = self._p(params, "folder")
        if not folder or not os.path.isdir(folder):
            return (0, None, (1, "invalid folder", 0))
        prefix = self._p(params, "prefix", self.state["prefix"])
        target_case = self._p(params, "case", self.state["target_case"])
        dry_run = self._p(params, "dry_run", self.state["dry_run"])
        rc, scan_data, err = self.scan_folder({
            "folder": folder,
            "prefix": prefix,
            "case": target_case,
        })
        if rc != 1:
            return rc, scan_data, err
        results = []
        for item in scan_data:
            if not item.get("will_rename"):
                continue
            old_path = item["path"]
            new_path = os.path.join(folder, item["new"])
            entry = {
                "old": item["original"],
                "new": item["new"],
                "done": False,
            }
            if dry_run:
                entry["dry_run"] = True
            else:
                try:
                    os.rename(old_path, new_path)
                    entry["done"] = True
                    self.state["stats"]["renamed"] += 1
                except Exception as e:
                    entry["error"] = str(e)
                    self.state["stats"]["errors"] += 1
            results.append(entry)
        return (1, {
            "folder": folder,
            "prefix": prefix,
            "case": target_case,
            "dry_run": dry_run,
            "renamed": len([r for r in results if r.get("done")]),
            "planned": len(results),
            "errors": len([r for r in results if r.get("error")]),
            "details": results,
        }, None)

    def get_stats(self, params):
        return (1, dict(self.state["stats"]), None)


if __name__ == "__main__":
    engine = FilenameEngine()

    if len(sys.argv) < 2:
        sys.stderr.write("Usage: filename_engine.py <command> [args]\n")
        sys.stderr.write("Commands:\n")
        sys.stderr.write("  scan <folder> [--prefix Plf_] [--case pascal]\n")
        sys.stderr.write("  rename <folder> [--prefix Plf_] [--case pascal] [--dry-run]\n")
        sys.stderr.write("  detect <filename>\n")
        sys.stderr.write("  transform <filename> [--prefix Plf_] [--case pascal]\n")
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]
    folder = None
    filename = None
    prefix = "Plf_"
    target_case = "pascal"
    dry_run = False

    i = 0
    while i < len(args):
        if args[i] == "--prefix" and i + 1 < len(args):
            prefix = args[i + 1]
            i += 2
        elif args[i] == "--case" and i + 1 < len(args):
            target_case = args[i + 1]
            i += 2
        elif args[i] == "--dry-run":
            dry_run = True
            i += 1
        else:
            if cmd in ("scan", "rename"):
                folder = args[i]
            elif cmd in ("detect", "transform"):
                filename = args[i]
            i += 1

    if cmd == "scan":
        rc, data, err = engine.scan_folder({
            "folder": folder,
            "prefix": prefix,
            "case": target_case,
        })
        if rc == 1:
            for item in data:
                tag = "SKIP" if item.get("skipped") else ("RENAME" if item.get("will_rename") else "OK")
                sys.stdout.write(f"  [{tag}] {item['original']}")
                if item.get("will_rename"):
                    sys.stdout.write(f" -> {item['new']}")
                sys.stdout.write(f"  ({item.get('detected_case', '?')})\n")
            sys.stdout.write(f"\nScanned: {engine.state['stats']['scanned']}\n")
        else:
            sys.stderr.write(f"Error: {err}\n")
            sys.exit(1)

    elif cmd == "rename":
        rc, data, err = engine.rename_folder({
            "folder": folder,
            "prefix": prefix,
            "case": target_case,
            "dry_run": dry_run,
        })
        if rc == 1:
            mode = "DRY RUN" if data["dry_run"] else "EXECUTED"
            sys.stdout.write(f"[{mode}] Folder: {data['folder']}\n")
            sys.stdout.write(f"Prefix: {data['prefix']}  Case: {data['case']}\n")
            sys.stdout.write(f"Renamed: {data['renamed']}  Planned: {data['planned']}  Errors: {data['errors']}\n\n")
            for d in data["details"]:
                status = "OK" if d.get("done") else ("DRY" if d.get("dry_run") else "ERR")
                sys.stdout.write(f"  [{status}] {d['old']} -> {d['new']}\n")
                if d.get("error"):
                    sys.stdout.write(f"         ERROR: {d['error']}\n")
        else:
            sys.stderr.write(f"Error: {err}\n")
            sys.exit(1)

    elif cmd == "detect":
        rc, data, err = engine.detect_pattern({"filename": filename})
        if rc == 1:
            sys.stdout.write(json.dumps(data, indent=2) + "\n")
        else:
            sys.stderr.write(f"Error: {err}\n")
            sys.exit(1)

    elif cmd == "transform":
        rc, data, err = engine.transform_name({
            "filename": filename,
            "prefix": prefix,
            "case": target_case,
        })
        if rc == 1:
            sys.stdout.write(json.dumps(data, indent=2) + "\n")
        else:
            sys.stderr.write(f"Error: {err}\n")
            sys.exit(1)

    else:
        sys.stderr.write(f"Unknown command: {cmd}\n")
        sys.exit(1)
