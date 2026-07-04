# [@GHOST]{[@file<UnifiedAst.py>][@domain<Dom_Unified>][@role<main_api>][@auth<cascade>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<main_api>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{UnifiedAst — main API. Query SQLite cache first, parse with vbast if stale, capture errors.}
# [@CLASS]{UnifiedAst}
# [@METHOD]{Run,Parse,GetClasses,GetMethods,GetEdges,CheckVbstyle,GetBclStamps,ParseDir,Store,Prevent,TopErrors}

"""
UnifiedAst — the main API for Dom_Unified.

PIPELINE:
    1. Query SQLite cache for file
    2. If cache hit (fresh) → return cached data
    3. If cache miss/stale → parse with vbast C binary
    4. Store result in cache
    5. Capture violations into error_knowledge
    6. Return data

USAGE:
    from Dom_Unified import UnifiedAst

    ua = UnifiedAst()
    ok, data, err = ua.Run("parse", {"file": "some_file.py"})
    # data = {classes, methods, edges, violations, summary, from_cache}

    # Or direct functions:
    from Dom_Unified import get_classes, get_methods, check_vbstyle
    classes = get_classes("file.py")
"""

import json
import os
import subprocess

from .Config import VBAST_BIN, VBAST_FALLBACK, SQLITE_PATH, CACHE_TTL_SECONDS, CAPTURE_ERRORS
from .CacheDb import CacheDb
from .ErrorCapture import ErrorCapture


def _vbast_path():
    if os.path.exists(VBAST_BIN):
        return VBAST_BIN
    return VBAST_FALLBACK


def _run_vbast(file_path, flags, timeout=30):
    cmd = [_vbast_path(), file_path] + flags
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (result.stdout, result.stderr, result.returncode)
    except subprocess.TimeoutExpired:
        return ("", "timeout", -1)
    except FileNotFoundError:
        return ("", f"vbast not found at {cmd[0]}", -2)


def _parse_json_lines(stdout):
    results = []
    for line in stdout.strip().split("\n"):
        line = line.strip()
        if line.startswith("{"):
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return results


def _parse_ast_output(stdout):
    classes = []
    methods = []
    current_class = None
    for line in stdout.split("\n"):
        line = line.strip()
        if line.startswith("CLASS:"):
            current_class = {"name": "", "line_start": 0, "line_end": 0, "method_count": 0, "flags": []}
            rest = line[6:].strip()
            name = rest.split()[0] if rest else ""
            if "(" in name:
                name = name.split("(")[0]
            current_class["name"] = name
            if "[" in line:
                range_str = line[line.index("[") + 1 : line.index("]")]
                parts = range_str.replace("lines ", "").split("-")
                if len(parts) == 2:
                    current_class["line_start"] = int(parts[0])
                    current_class["line_end"] = int(parts[1])
            for flag in ["RUN", "GHOST", "VBSTYLE", "DECORATOR!"]:
                if flag in line:
                    current_class["flags"].append(flag)
            classes.append(current_class)
        elif line.startswith("METHOD:"):
            method = {"name": "", "class_name": current_class["name"] if current_class else "",
                      "signature": "", "line_start": 0, "line_end": 0, "flags": []}
            rest = line[7:].strip()
            if "[" in rest:
                sig_part = rest[: rest.index("[")].strip()
                range_str = rest[rest.index("[") + 1 : rest.index("]")]
                parts = range_str.replace("lines ", "").split("-")
                if len(parts) == 2:
                    method["line_start"] = int(parts[0])
                    method["line_end"] = int(parts[1])
            else:
                sig_part = rest
            method["signature"] = sig_part
            method["name"] = sig_part.split("(")[0] if "(" in sig_part else sig_part
            for flag in ["T3", "PRINT!", "HINT!", "DEC!"]:
                if flag in rest:
                    method["flags"].append(flag)
            methods.append(method)
    return classes, methods


def _parse_graph_output(stdout):
    edges = []
    for line in stdout.split("\n"):
        line = line.strip()
        if line.startswith("[") and "]" in line:
            edge_type = line[1 : line.index("]")].strip()
            rest = line[line.index("]") + 1 :].strip()
            if " -> " in rest:
                parts = rest.split(" -> ", 1)
                source = parts[0].strip()
                target_part = parts[1].strip()
            else:
                source = ""
                target_part = rest
            target = target_part
            line_num = 0
            certainty = "CERTAIN"
            if "(line " in target_part:
                paren_idx = target_part.rindex("(line ")
                target = target_part[:paren_idx].strip()
                meta = target_part[paren_idx:]
                if "," in meta:
                    line_str = meta.split(",")[0].replace("(line ", "").strip()
                    certainty = meta.split(",")[1].replace(")", "").strip()
                    try:
                        line_num = int(line_str)
                    except ValueError:
                        pass
            edges.append({"edge_type": edge_type, "source": source, "target": target,
                          "line_number": line_num, "certainty": certainty})
    return edges


def _parse_check_output(stdout):
    violations = []
    for line in stdout.split("\n"):
        line = line.strip()
        if line.startswith("[error]") or line.startswith("[warn]"):
            level = "error" if "[error]" in line else "warn"
            rest = line.replace("[error]", "").replace("[warn]", "").strip()
            rule = ""
            message = rest
            if ":" in rest:
                parts = rest.split(":", 1)
                rule = parts[0].strip()
                message = parts[1].strip()
            violations.append({"level": level, "rule": rule, "message": message})
    return violations


def _parse_bcl_output(stdout):
    """Parse BCL stamp output from vbast --bcl."""
    bcl = {"file_stamp": "", "vbstyle_stamp": "", "classes": [], "methods": []}
    in_stamps = False
    stamp_lines = []
    for line in stdout.split("\n"):
        line = line.strip()
        if line == "=== BCL STAMPS ===":
            in_stamps = True
            continue
        if not in_stamps:
            continue
        if line.startswith('"""'):
            if stamp_lines:
                break
            continue
        if line.startswith('#[@GHOST]'):
            bcl["file_stamp"] = line
        elif line.startswith('#[@VBSTYLE]'):
            bcl["vbstyle_stamp"] = line
        elif line.startswith('#[@CLASSES]'):
            inner = line[line.index('{') + 1:line.rindex('}')]
            inner = inner.strip('"')
            bcl["classes"] = [c.strip() for c in inner.split(';') if c.strip()]
        elif line.startswith('#[@METHODS]'):
            inner = line[line.index('{') + 1:line.rindex('}')]
            inner = inner.strip('"')
            bcl["methods"] = [m.strip() for m in inner.split(';') if m.strip()]
    return bcl


def _vbast_parse_full(file_path):
    """Run vbast on a file, return full structured data."""
    stdout, stderr, rc = _run_vbast(file_path, ["--json"])
    if rc != 0:
        return None
    results = _parse_json_lines(stdout)
    if not results:
        return None
    summary = results[0]

    stdout_ast, _, _ = _run_vbast(file_path, ["--ast"])
    classes, methods = _parse_ast_output(stdout_ast)

    stdout_graph, _, _ = _run_vbast(file_path, ["--graph"])
    edges = _parse_graph_output(stdout_graph)

    stdout_check, _, _ = _run_vbast(file_path, ["--check"])
    violations = _parse_check_output(stdout_check)

    stdout_bcl, _, _ = _run_vbast(file_path, ["--bcl"])
    bcl = _parse_bcl_output(stdout_bcl)

    return {"classes": classes, "methods": methods, "edges": edges,
            "violations": violations, "bcl": bcl, "summary": summary}


# ════════════════════════════════════════════
# MODULE-LEVEL CACHE (shared across all calls)
# ════════════════════════════════════════════

_cache = None
_error_capture = None

def _get_cache():
    global _cache
    if _cache is None:
        _cache = CacheDb()
    return _cache

def _get_error_capture():
    global _error_capture
    if _error_capture is None:
        _error_capture = ErrorCapture()
    return _error_capture


# ════════════════════════════════════════════
# PUBLIC API — use directly
# ════════════════════════════════════════════

def parse(file_path):
    """
    Full parse with cache. Returns dict with from_cache flag.
    Pipeline: cache check → vbast parse → cache store → error capture → return
    """
    cache = _get_cache()

    # Step 1: Check cache
    ok, cached, err = cache.Run("get", {"file": file_path})
    if ok:
        cached["from_cache"] = True
        cached["file"] = file_path
        return cached

    # Step 2: Parse with vbast
    data = _vbast_parse_full(file_path)
    if not data:
        return {"error": "vbast parse failed", "file": file_path}

    data["file"] = file_path
    data["from_cache"] = False

    # Step 3: Store in cache
    cache.Run("put", {"file": file_path, "data": data})

    # Step 4: Capture errors
    if CAPTURE_ERRORS and data["violations"]:
        ec = _get_error_capture()
        ec.Run("capture", {"file": file_path, "violations": data["violations"]})

    return data

def parse_dir(dir_path):
    """Parse all .py files in a directory (uses vbast directly, no cache for dirs)."""
    stdout, stderr, rc = _run_vbast(dir_path, ["--json"])
    if rc != 0:
        return [{"error": stderr, "dir": dir_path}]
    return _parse_json_lines(stdout)

def get_classes(file_path):
    """Get class names — cache first, vbast if needed."""
    data = parse(file_path)
    return [c["name"] for c in data.get("classes", [])]

def get_methods(file_path):
    """Get method names — cache first, vbast if needed."""
    data = parse(file_path)
    return [m["name"] for m in data.get("methods", [])]

def get_edges(file_path):
    """Get graph edges — cache first, vbast if needed."""
    data = parse(file_path)
    return data.get("edges", [])

def check_vbstyle(file_path):
    """Get VBStyle violations — cache first, vbast if needed."""
    data = parse(file_path)
    return data.get("violations", [])

def get_bcl_stamps(file_path):
    """Get BCL stamps — cache first (now included in parse output), live if not cached."""
    data = parse(file_path)
    bcl = data.get("bcl")
    if bcl:
        return bcl
    stdout, _, _ = _run_vbast(file_path, ["--bcl"])
    return _parse_bcl_output(stdout)

def to_json(file_path):
    """Get JSON summary — cache first."""
    data = parse(file_path)
    return data.get("summary", {})

def store(file_path, db_name="bcl_ir"):
    """Parse and store to MySQL."""
    stdout, stderr, rc = _run_vbast(file_path, ["--store", db_name])
    return rc == 0 and "ERROR" not in stderr

def prevent(file_path):
    """
    Get prevention hints for a file — what errors has it hit before?
    Uses error_knowledge to warn about common mistakes.
    """
    ec = _get_error_capture()
    ok, hints, err = ec.Run("prevent", {"file": file_path})
    return hints if ok else []

def top_errors(limit=10):
    """Get top N most common errors across all files."""
    ec = _get_error_capture()
    ok, data, err = ec.Run("top_errors", {"limit": limit})
    return data if ok else []

def cache_stats():
    """Get cache + error capture stats."""
    cache = _get_cache()
    ok, stats, _ = cache.Run("stats", {})
    return stats

def invalidate(file_path):
    """Remove a file from cache (force re-parse next time)."""
    cache = _get_cache()
    ok, _, _ = cache.Run("invalidate", {"file": file_path})
    return ok


# ════════════════════════════════════════════
# CLASS API — for stateful usage
# ════════════════════════════════════════════

class UnifiedAst:
    """
    Stateful API for Dom_Unified.
    Wraps the module-level functions with stats tracking.

    Usage:
        ua = UnifiedAst()
        ok, data, err = ua.Run("parse", {"file": "file.py"})
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {"use_cache": True, "capture_errors": CAPTURE_ERRORS},
            "stats": {"files_parsed": 0, "cache_hits": 0, "cache_misses": 0},
            "last_result": None,
            "last_file": None,
        }

    def Run(self, command, params=None):
        dispatch = {
            "parse": self._cmd_parse,
            "parse_dir": self._cmd_parse_dir,
            "get_classes": self._cmd_get_classes,
            "get_methods": self._cmd_get_methods,
            "get_edges": self._cmd_get_edges,
            "check_vbstyle": self._cmd_check,
            "get_bcl_stamps": self._cmd_bcl,
            "to_json": self._cmd_json,
            "store": self._cmd_store,
            "prevent": self._cmd_prevent,
            "top_errors": self._cmd_top_errors,
            "cache_stats": self._cmd_cache_stats,
            "invalidate": self._cmd_invalidate,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", f"Unknown: {command}", 0))
        return handler(params or {})

    def read_state(self):
        return (1, dict(self.state), None)

    def set_config(self, values):
        for key, val in values.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def _cmd_parse(self, params):
        fp = params.get("file")
        if not fp:
            return (0, None, ("ERR_NO_FILE", "params['file'] required", 0))
        data = parse(fp)
        if "error" in data:
            return (0, None, ("ERR_VBAST", data["error"], 0))
        self.state["last_result"] = data
        self.state["last_file"] = fp
        self.state["stats"]["files_parsed"] += 1
        if data.get("from_cache"):
            self.state["stats"]["cache_hits"] += 1
        else:
            self.state["stats"]["cache_misses"] += 1
        return (1, data, None)

    def _cmd_parse_dir(self, params):
        dp = params.get("dir") or params.get("file")
        if not dp:
            return (0, None, ("ERR_NO_DIR", "params['dir'] required", 0))
        return (1, parse_dir(dp), None)

    def _cmd_get_classes(self, params):
        fp = params.get("file")
        if not fp:
            return (0, None, ("ERR_NO_FILE", "params['file'] required", 0))
        return (1, get_classes(fp), None)

    def _cmd_get_methods(self, params):
        fp = params.get("file")
        if not fp:
            return (0, None, ("ERR_NO_FILE", "params['file'] required", 0))
        return (1, get_methods(fp), None)

    def _cmd_get_edges(self, params):
        fp = params.get("file")
        if not fp:
            return (0, None, ("ERR_NO_FILE", "params['file'] required", 0))
        return (1, get_edges(fp), None)

    def _cmd_check(self, params):
        fp = params.get("file")
        if not fp:
            return (0, None, ("ERR_NO_FILE", "params['file'] required", 0))
        return (1, check_vbstyle(fp), None)

    def _cmd_bcl(self, params):
        fp = params.get("file")
        if not fp:
            return (0, None, ("ERR_NO_FILE", "params['file'] required", 0))
        return (1, get_bcl_stamps(fp), None)

    def _cmd_json(self, params):
        fp = params.get("file")
        if not fp:
            return (0, None, ("ERR_NO_FILE", "params['file'] required", 0))
        return (1, to_json(fp), None)

    def _cmd_store(self, params):
        fp = params.get("file")
        db = params.get("db", "bcl_ir")
        if not fp:
            return (0, None, ("ERR_NO_FILE", "params['file'] required", 0))
        ok = store(fp, db)
        if not ok:
            return (0, None, ("ERR_STORE", "store failed", 0))
        return (1, {"stored": True, "db": db, "file": fp}, None)

    def _cmd_prevent(self, params):
        fp = params.get("file", "")
        return (1, prevent(fp), None)

    def _cmd_top_errors(self, params):
        limit = params.get("limit", 10)
        return (1, top_errors(limit), None)

    def _cmd_cache_stats(self, params):
        return (1, cache_stats(), None)

    def _cmd_invalidate(self, params):
        fp = params.get("file")
        if not fp:
            return (0, None, ("ERR_NO_FILE", "params['file'] required", 0))
        return (1, {"invalidated": invalidate(fp)}, None)
