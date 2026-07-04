#!/usr/bin/env python3
#[@GHOST]{[@file<bcl_pattern_msearch.py>][@state<active>][@date<2026-07-01>][@ver<1.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<bcl_pattern_msearch>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}
#[@SUMMARY]{msearch integration for finding past chat discussions about BCL patterns}

import subprocess

MSEARCH_BINARY = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/bin_tools/msearch"
TIMEOUT_SECONDS = 30
DEFAULT_LIMIT = 20

class BclPatternMsearch:
    """msearch integration for finding past chat discussions about BCL patterns.

    Uses the msearch binary via subprocess to search chat history.
    All access via Run() dispatch.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "binary": MSEARCH_BINARY,
                "timeout": TIMEOUT_SECONDS,
                "limit": DEFAULT_LIMIT,
            },
            "results": {},
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "search_pattern":
            return self.SearchPattern(params)
        elif command == "search_repair":
            return self.SearchRepair(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def ExecMsearch(self, query):
        """Execute msearch binary with a query string, return (ok, output_text, err)."""
        binary = self.state["config"].get("binary", MSEARCH_BINARY)
        timeout = self.state["config"].get("timeout", TIMEOUT_SECONDS)
        cmd = [binary, query]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return (0, None, ("MSEARCH_TIMEOUT", "msearch timed out after " + str(timeout) + "s", 0))
        except FileNotFoundError:
            return (0, None, ("MSEARCH_NOT_FOUND", "msearch binary not found at " + binary, 0))
        except Exception as exc:
            return (0, None, ("MSEARCH_EXEC_FAILED", str(exc), 0))

        if proc.returncode != 0:
            return (0, None, ("MSEARCH_EXIT_ERROR", proc.stderr.strip() or proc.stdout.strip(), 0))

        return (1, proc.stdout.strip(), None)

    def SearchPattern(self, params):
        """Search chat history for discussions about a BCL pattern."""
        pattern = self._p(params, "pattern", "")
        if not pattern:
            return (0, None, ("NO_PATTERN", "pattern param is required", 0))
        query = "BCL pattern " + pattern + " bracket format"
        ok, output, err = self.ExecMsearch(query)
        if not ok:
            return (0, None, err)
        results = self.ParseResults(output)
        self.state["results"]["pattern_search"] = results
        return (1, {"results": results, "pattern": pattern, "raw": output}, None)

    def SearchRepair(self, params):
        """Search chat history for discussions about converting a pattern to canonical."""
        pattern = self._p(params, "pattern", "")
        canonical = self._p(params, "canonical", "")
        if not pattern:
            return (0, None, ("NO_PATTERN", "pattern param is required", 0))
        query = "convert BCL " + pattern + " to " + canonical + " canonical repair"
        ok, output, err = self.ExecMsearch(query)
        if not ok:
            return (0, None, err)
        results = self.ParseResults(output)
        self.state["results"]["repair_search"] = results
        return (1, {"results": results, "pattern": pattern, "canonical": canonical, "raw": output}, None)

    def ParseResults(self, output):
        """Parse msearch text output into a list of result entries."""
        if not output:
            return []
        lines = output.split("\n")
        results = []
        current = {}
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current:
                    results.append(current)
                    current = {}
                continue
            if stripped.startswith("#") or stripped.startswith("---"):
                continue
            if ":" in stripped:
                idx = stripped.index(":")
                key = stripped[:idx].strip().lower().replace(" ", "_")
                value = stripped[idx + 1:].strip()
                current[key] = value
            else:
                if "text" not in current:
                    current["text"] = stripped
                else:
                    current["text"] = current["text"] + " " + stripped
        if current:
            results.append(current)
        return results
