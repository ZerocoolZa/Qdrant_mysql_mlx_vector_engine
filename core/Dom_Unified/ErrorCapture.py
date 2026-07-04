# [@GHOST]{[@file<ErrorCapture.py>][@domain<Dom_Unified>][@role<error_capture>][@auth<cascade>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<error_capture>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{Error capture pipeline — violations become reusable knowledge to prevent future errors}
# [@CLASS]{ErrorCapture}
# [@METHOD]{Run,Capture,CaptureBatch,Query,TopErrors,Prevent}

"""
Error capture pipeline for Dom_Unified.

When vbast finds VBStyle violations or parse errors, they get captured
into the SQLite error_knowledge table. Each time the same error is seen
again, its reuse_count increments — so you can see which errors are
most common and prevent them.

FLOW:
    parse file → find violations → capture each into error_knowledge
    → query top errors → fix patterns → prevent future occurrences

This is the "errors become reusable data" pipeline.
"""

import time

from .CacheDb import CacheDb


class ErrorCapture:
    """Captures violations from vbast into reusable error knowledge."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {"auto_capture": True, "min_severity": "warn"},
            "stats": {"total_captured": 0, "total_reused": 0, "files_scanned": 0},
            "cache": None,
        }
        self.cache = CacheDb()

    def Run(self, command, params=None):
        dispatch = {
            "capture": self._cmd_capture,
            "capture_batch": self._cmd_capture_batch,
            "query": self._cmd_query,
            "top_errors": self._cmd_top_errors,
            "prevent": self._cmd_prevent,
            "stats": self._cmd_stats,
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

    def close(self):
        if self.cache:
            self.cache.close()

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def _cmd_capture(self, params):
        """Capture a single violation into error knowledge."""
        file_path = params.get("file", "")
        violations = params.get("violations", [])
        if not violations:
            return (1, {"captured": 0}, None)

        captured = 0
        reused = 0
        for v in violations:
            severity = v.get("level", "error")
            if severity == "error" and self.state["config"]["min_severity"] == "error":
                pass
            ok, data, err = self.cache.Run("capture_error", {
                "file": file_path,
                "rule": v.get("rule", ""),
                "severity": severity,
                "message": v.get("message", ""),
                "line": v.get("line", 0),
            })
            if ok:
                if data.get("captured"):
                    captured += 1
                reused += 1

        self.state["stats"]["total_captured"] += captured
        self.state["stats"]["total_reused"] += reused
        self.state["stats"]["files_scanned"] += 1
        return (1, {"captured": captured, "reused": reused, "file": file_path}, None)

    def _cmd_capture_batch(self, params):
        """Capture violations from multiple files at once."""
        files_data = params.get("files", [])
        total_captured = 0
        total_reused = 0
        for fd in files_data:
            ok, data, err = self._cmd_capture(fd)
            if ok:
                total_captured += data.get("captured", 0)
                total_reused += data.get("reused", 0)
        return (1, {"captured": total_captured, "reused": total_reused, "files": len(files_data)}, None)

    def _cmd_query(self, params):
        """Query error knowledge by rule, file, or get all."""
        ok, data, err = self.cache.Run("query_errors", params)
        if not ok:
            return (0, None, err)
        return (1, data, None)

    def _cmd_top_errors(self, params):
        """Get top N most common errors by reuse_count."""
        limit = params.get("limit", 10)
        ok, data, err = self.cache.Run("query_errors", {"limit": limit})
        if not ok:
            return (0, None, err)
        # Sort by reuse_count descending
        data.sort(key=lambda x: x.get("reuse_count", 0), reverse=True)
        # Add times_seen for convenience
        for e in data:
            e["times_seen"] = e.get("reuse_count", 0) + 1
        return (1, data[:limit], None)

    def _cmd_prevent(self, params):
        """
        Given a file about to be written, check error_knowledge for
        common errors that file_path or similar files have hit.
        Returns a list of errors to watch out for.
        """
        file_path = params.get("file", "")
        rule = params.get("rule")

        if rule:
            ok, data, err = self.cache.Run("query_errors", {"rule": rule, "limit": 5})
        else:
            ok, data, err = self.cache.Run("query_errors", {"file": file_path, "limit": 10})

        if not ok:
            return (0, None, err)

        # Build prevention hints
        hints = []
        for e in data:
            hints.append({
                "rule": e["rule"],
                "severity": e.get("severity", "error"),
                "message": e["message"],
                "times_seen": e.get("reuse_count", 0) + 1,
                "prevent_hint": self._prevent_hint(e["rule"]),
            })
        return (1, hints, None)

    def _cmd_stats(self, params):
        ok, cache_stats, _ = self.cache.Run("stats", {})
        result = dict(self.state["stats"])
        result["cache"] = cache_stats
        return (1, result, None)

    # ════════════════════════════════════════════
    # PREVENTION HINTS
    # ════════════════════════════════════════════

    def _prevent_hint(self, rule):
        """Return a prevention hint for a given rule."""
        hints = {
            "no_type_hints": "Remove type annotations — VBStyle forbids type hints",
            "no_decorators": "Remove @property, @staticmethod, @classmethod — VBStyle forbids decorators",
            "no_print_outside_main": "Use self._p() instead of print() — VBStyle forbids bare print()",
            "must_return_tuple3": "All methods must return (1, data, None) or (0, None, (code, desc, 0))",
            "must_have_run": "Every class must have a Run(self, command, params=None) dispatch method",
            "must_accept_mem": "__init__ must accept (self, mem=None, db=None, param=None)",
            "no_inheritance": "VBStyle forbids inheritance — use composition instead",
            "no_hardcoded_paths": "Use Config.py for paths — no hardcoded /Users/wws/... in code",
            "no_self_underscore": "Use self.state['key'] not self._key — VBStyle forbids self._ prefix",
            "ghost_tag": "Add #[@GHOST] header to file — every file needs identity",
            "vbstyle_tag": "Add #[@VBSTYLE] header to file — every file needs VBStyle declaration",
        }
        return hints.get(rule, f"Check VBStyle rules for: {rule}")
