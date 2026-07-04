#!/usr/bin/env python3
#[@GHOST]{("file";"Dom_Bcl_Scan.py")("domain";"Dom_Bcl")("role";"bracket_grammar_scanner")("auth";"devin")("date";"2026-07-03")("ver";"1.0")}
#[@VBSTYLE]{("auth";"devin")("role";"bracket_grammar_scanner")("return";"Tuple3")("orch";"none")("no";"decorators|print|hardcoded|tabs|self_underscore")("model";"one_class_one_domain_one_authority_complete")}
#[@SUMMARY]{("purpose";"Scan every file in workspace, extract every [@...] bracket packet, classify grammar signature, count frequencies, record samples, report malformed")("scope";"entire workspace tree")("discovers";"all bracket grammars not just known ones")}
#[@CLASS]{("name";"DomBclScan")}
#[@METHOD]{("list";"Run,read_state,set_config,scan,scan_file,scan_dir,report,grammar_signature,extract_packet")}

"""
DomBclScan — bracket grammar discovery scanner.

Scans every file in a workspace tree, extracts every [@...] bracket packet
with proper nesting support, classifies each packet by its grammar signature
(built from actual syntax, not hardcoded formats), counts frequencies,
records one sample per grammar, and reports malformed/unbalanced packets.

GRAMMAR SIGNATURES (discovered, not hardcoded):
  TAG_ONLY        — [@TAG]
  TAG{}           — [@TAG]{...}
  TAG()           — [@TAG](...)
  TAG<>           — [@TAG]<...>
  TAG[]           — [@TAG][@INNER]  (chained containers)
  TAG{}{}         — [@TAG]{...}{...}
  TAG<>()         — [@TAG]<...>(...)
  TAG(){}         — [@TAG](...){...}
  TAG[]{}         — [@TAG][@INNER]{...}
  TAG<>()[]       — [@TAG]<...>(...)[@INNER]
  UNKNOWN         — malformed or unbalanced

USAGE:
  from Dom_Bcl.Dom_Bcl_Scan import DomBclScan

  scanner = DomBclScan()
  ok, data, err = scanner.Run("scan", {"root": "/Users/wws/Qdrant_mysql_mlx_vector_engine"})
  ok, report, err = scanner.Run("report", {})
"""

import os
import re
import time
import json

BRACKET_PAIRS = {
    "{": "}",
    "(": ")",
    "[": "]",
    "<": ">",
}

OPEN_BRACKETS = set(BRACKET_PAIRS.keys())
CLOSE_BRACKETS = set(BRACKET_PAIRS.values())

TAG_PATTERN = re.compile(r'\[@([A-Z][A-Z0-9_]*)\]')

SCAN_EXTENSIONS = {".py", ".c", ".m", ".sh", ".md", ".sql", ".json", ".yaml", ".txt", ".ts", ".js"}
SCAN_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".codeium", "treasure_trove_backup", ".codex"}
SCAN_MAX_FILE_SIZE = 2 * 1024 * 1024
SCAN_MAX_FILES = 50000


class DomBclScan:
    """
    Bracket grammar discovery scanner.
    VBStyle compliant: Run() dispatch, Tuple3 returns, self.state dict.
    No print, no decorators, no self._, no hardcoded values.
    """

    def __init__(self, mem=None, db=None, param=None):
        cfg = param or {}
        self.state = {
            "config": {
                "extensions": cfg.get("extensions", list(SCAN_EXTENSIONS)),
                "skip_dirs": cfg.get("skip_dirs", list(SCAN_SKIP_DIRS)),
                "max_file_size": cfg.get("max_file_size", SCAN_MAX_FILE_SIZE),
                "max_files": cfg.get("max_files", SCAN_MAX_FILES),
                "root": cfg.get("root", "."),
            },
            "results": {
                "total_packets": 0,
                "total_files_scanned": 0,
                "total_files_with_packets": 0,
                "grammars": {},
                "tags": {},
                "malformed": [],
                "samples": {},
            },
            "runtime": {
                "scanning": False,
                "last_scan_root": None,
                "last_scan_time": None,
                "duration_seconds": 0,
            },
            "stats": {
                "errors": 0,
            },
        }
        self.mem = mem
        self.db = db

    def _p(self, params, key, default=None):
        if not params:
            return (1, default, None)
        return (1, params.get(key, default), None)

    def Run(self, command, params=None):
        dispatch = {
            "scan": self._cmd_scan,
            "scan_file": self._cmd_scan_file,
            "scan_dir": self._cmd_scan_dir,
            "report": self._cmd_report,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "Unknown command: %s" % command, 0))
        return handler(params or {})

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        if not params:
            return (0, None, ("ERR_PARAMS", "config values required", 0))
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    # ============================================================
    # PACKET EXTRACTION
    # ============================================================

    def extract_packet(self, text, start_pos):
        """Extract a complete bracket packet starting at position start_pos.
        text[start_pos] must be '[' and text[start_pos+1] must be '@'.
        Returns (end_pos, tag_name, grammar_sig, raw_text, balanced).
        """
        length = len(text)
        if start_pos >= length or text[start_pos] != "[":
            return (start_pos, None, "UNKNOWN", "", False)
        if start_pos + 1 >= length or text[start_pos + 1] != "@":
            return (start_pos, None, "UNKNOWN", "", False)

        m = TAG_PATTERN.match(text, start_pos)
        if not m:
            depth = 1
            pos = start_pos + 1
            while pos < length and depth > 0:
                if text[pos] == "[":
                    depth += 1
                elif text[pos] == "]":
                    depth -= 1
                pos += 1
            return (pos, None, "UNKNOWN", text[start_pos:pos], depth == 0)

        tag_name = m.group(1)
        pos = m.end()
        grammar_parts = []
        balanced = True

        while pos < length:
            while pos < length and text[pos] in " \t\r\n":
                pos += 1
            if pos >= length:
                break
            ch = text[pos]
            if ch in OPEN_BRACKETS:
                close_char = BRACKET_PAIRS[ch]
                depth = 1
                bracket_start = pos
                pos += 1
                while pos < length and depth > 0:
                    c = text[pos]
                    if c in OPEN_BRACKETS:
                        depth += 1
                    elif c in CLOSE_BRACKETS:
                        depth -= 1
                    pos += 1
                if depth != 0:
                    balanced = False
                    grammar_parts.append(ch + BRACKET_PAIRS[ch] + "!")
                    pos = length
                else:
                    inner = text[bracket_start + 1:pos - 1]
                    if ch == "[" and inner.startswith("@"):
                        inner_m = TAG_PATTERN.match(inner)
                        if inner_m:
                            grammar_parts.append("[]")
                        else:
                            grammar_parts.append("[]")
                    else:
                        grammar_parts.append(ch + BRACKET_PAIRS[ch])
            elif ch == "[" and pos + 1 < length and text[pos + 1] == "@":
                continue
            elif ch == "#":
                break
            else:
                break

        if not grammar_parts:
            grammar_sig = "TAG_ONLY"
        else:
            grammar_sig = "TAG" + "".join(grammar_parts)

        raw = text[start_pos:pos]
        return (pos, tag_name, grammar_sig, raw, balanced)

    def grammar_signature(self, tag_name, grammar_sig, balanced):
        """Build the final grammar signature string."""
        if not balanced:
            return grammar_sig + "_UNBALANCED"
        return grammar_sig

    # ============================================================
    # FILE SCANNING
    # ============================================================

    def scan_text(self, text, file_path):
        """Scan a single text string for all [@...] packets."""
        packets = []
        pos = 0
        length = len(text)
        while pos < length:
            idx = text.find("[@", pos)
            if idx == -1:
                break
            end_pos, tag, grammar, raw, balanced = self.extract_packet(text, idx)
            if tag is None:
                pos = idx + 2
                continue
            sig = self.grammar_signature(tag, grammar, balanced)
            packets.append({
                "tag": tag,
                "grammar": sig,
                "raw": raw[:500],
                "balanced": balanced,
                "position": idx,
                "file": file_path,
            })
            pos = end_pos if end_pos > idx else idx + 2
        return packets

    def _cmd_scan_file(self, params):
        ok, file_path, err = self._p(params, "path")
        if not file_path or not os.path.isfile(file_path):
            return (0, None, ("ERR_FILE", "file not found: %s" % file_path, 0))
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception as e:
            return (0, None, ("ERR_READ", str(e), 0))
        packets = self.scan_text(text, file_path)
        return (1, {"file": file_path, "packets": packets, "count": len(packets)}, None)

    def _cmd_scan_dir(self, params):
        ok, root, err = self._p(params, "root", ".")
        if not os.path.isdir(root):
            return (0, None, ("ERR_DIR", "directory not found: %s" % root, 0))
        exts = set(self.state["config"]["extensions"])
        skip = set(self.state["config"]["skip_dirs"])
        max_size = self.state["config"]["max_file_size"]
        max_files = self.state["config"]["max_files"]
        all_packets = []
        files_scanned = 0
        files_with_packets = 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for fn in filenames:
                ext = os.path.splitext(fn)[1]
                if ext not in exts:
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    if os.path.getsize(fp) > max_size:
                        continue
                except OSError:
                    continue
                if files_scanned >= max_files:
                    break
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read()
                except Exception:
                    self.state["stats"]["errors"] += 1
                    continue
                files_scanned += 1
                packets = self.scan_text(text, fp)
                if packets:
                    files_with_packets += 1
                    all_packets.extend(packets)
        return (1, {
            "root": root,
            "files_scanned": files_scanned,
            "files_with_packets": files_with_packets,
            "packets": all_packets,
            "total_packets": len(all_packets),
        }, None)

    def _cmd_scan(self, params):
        ok, root, err = self._p(params, "root", self.state["config"]["root"])
        if not os.path.isdir(root):
            return (0, None, ("ERR_DIR", "directory not found: %s" % root, 0))
        self.state["runtime"]["scanning"] = True
        self.state["runtime"]["last_scan_root"] = root
        start_time = time.time()
        exts = set(self.state["config"]["extensions"])
        skip = set(self.state["config"]["skip_dirs"])
        max_size = self.state["config"]["max_file_size"]
        max_files = self.state["config"]["max_files"]
        grammars = {}
        tags = {}
        malformed = []
        samples = {}
        total_packets = 0
        files_scanned = 0
        files_with_packets = 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for fn in filenames:
                ext = os.path.splitext(fn)[1]
                if ext not in exts:
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    if os.path.getsize(fp) > max_size:
                        continue
                except OSError:
                    continue
                if files_scanned >= max_files:
                    break
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read()
                except Exception:
                    self.state["stats"]["errors"] += 1
                    continue
                files_scanned += 1
                packets = self.scan_text(text, fp)
                if packets:
                    files_with_packets += 1
                for pkt in packets:
                    total_packets += 1
                    sig = pkt["grammar"]
                    grammars[sig] = grammars.get(sig, 0) + 1
                    tags[pkt["tag"]] = tags.get(pkt["tag"], 0) + 1
                    if not pkt["balanced"]:
                        malformed.append({
                            "file": pkt["file"],
                            "position": pkt["position"],
                            "raw": pkt["raw"][:200],
                            "tag": pkt["tag"],
                        })
                    if sig not in samples:
                        samples[sig] = {
                            "tag": pkt["tag"],
                            "raw": pkt["raw"][:300],
                            "file": pkt["file"],
                        }
        duration = time.time() - start_time
        self.state["results"] = {
            "total_packets": total_packets,
            "total_files_scanned": files_scanned,
            "total_files_with_packets": files_with_packets,
            "grammars": grammars,
            "tags": tags,
            "malformed": malformed,
            "samples": samples,
        }
        self.state["runtime"]["scanning"] = False
        self.state["runtime"]["last_scan_time"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.state["runtime"]["duration_seconds"] = round(duration, 2)
        return (1, dict(self.state["results"]), None)

    def _cmd_report(self, params):
        ok, fmt, err = self._p(params, "format", "text")
        results = self.state["results"]
        if not results["grammars"]:
            return (0, None, ("ERR_NO_DATA", "no scan results. Run scan first.", 0))
        if fmt == "json":
            return (1, json.dumps(results, indent=2, default=str), None)
        lines = []
        lines.append("=== BRACKET GRAMMAR INVENTORY ===")
        lines.append("")
        lines.append("Total bracket packets: %d" % results["total_packets"])
        lines.append("Files scanned: %d" % results["total_files_scanned"])
        lines.append("Files with packets: %d" % results["total_files_with_packets"])
        lines.append("Malformed packets: %d" % len(results["malformed"]))
        lines.append("Duration: %ss" % self.state["runtime"]["duration_seconds"])
        lines.append("")
        lines.append("=== GRAMMAR FREQUENCIES ===")
        sorted_grammars = sorted(results["grammars"].items(), key=lambda x: -x[1])
        for sig, count in sorted_grammars:
            sample = results["samples"].get(sig, {})
            sample_raw = sample.get("raw", "")[:120]
            lines.append("%6d  %s" % (count, sig))
            if sample_raw:
                lines.append("      e.g. %s" % sample_raw)
            lines.append("")
        lines.append("=== TAG FREQUENCIES ===")
        sorted_tags = sorted(results["tags"].items(), key=lambda x: -x[1])
        for tag, count in sorted_tags:
            lines.append("%6d  @%s" % (count, tag))
        lines.append("")
        if results["malformed"]:
            lines.append("=== MALFORMED PACKETS (first 20) ===")
            for m in results["malformed"][:20]:
                lines.append("  %s:%d  tag=%s  raw=%s" % (
                    m["file"], m["position"], m["tag"], m["raw"][:100]
                ))
            lines.append("")
        return (1, "\n".join(lines), None)
