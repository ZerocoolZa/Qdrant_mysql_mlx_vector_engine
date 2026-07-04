#!/usr/bin/env python3
#[@GHOST]{[@file<bcl_pattern_ctx.py>][@state<active>][@date<2026-07-01>][@ver<2.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<bcl_pattern_ctx>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}
#[@SUMMARY]{ContextRAM integration for BCL pattern findings via ctx binary subprocess}

import json
import subprocess

CTX_BINARY = "/Users/wws/contestsystem/ContextRAMSwift/.build/release/ctx"
CTX_STORE = "/Users/wws/.config/devin/contextram_store"
TIMEOUT_SECONDS = 30
TAG_BCL = "bcl"
TAG_PATTERN = "pattern"
TAG_REPAIR = "repair"
QUERY_LIMIT = 50

class BclPatternCtx:
    """ContextRAM integration for BCL pattern findings and repairs.

    Uses the ctx binary via subprocess to create and query nodes.
    All access via Run() dispatch.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "binary": CTX_BINARY,
                "store": CTX_STORE,
                "timeout": TIMEOUT_SECONDS,
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
        if command == "store_findings":
            return self.StoreFindings(params)
        elif command == "store_repair":
            return self.StoreRepair(params)
        elif command == "query_findings":
            return self.QueryFindings(params)
        elif command == "assemble":
            return self.Assemble(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        elif command == "close":
            return self.Close()
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

    def Close(self):
        """Close any open resources. Returns Tuple3."""
        return (1, {"closed": True}, None)

    def ExecCtx(self, args):
        """Execute ctx binary with given args, return (ok, stdout_dict_or_text, err)."""
        binary = self.state["config"].get("binary", CTX_BINARY)
        timeout = self.state["config"].get("timeout", TIMEOUT_SECONDS)
        cmd = [binary] + args
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return (0, None, ("CTX_TIMEOUT", "ctx binary timed out after " + str(timeout) + "s", 0))
        except FileNotFoundError:
            return (0, None, ("CTX_NOT_FOUND", "ctx binary not found at " + binary, 0))
        except Exception as exc:
            return (0, None, ("CTX_EXEC_FAILED", str(exc), 0))

        if proc.returncode != 0:
            return (0, None, ("CTX_EXIT_ERROR", proc.stderr.strip() or proc.stdout.strip(), 0))

        stdout = proc.stdout.strip()
        if not stdout:
            return (1, "", None)
        try:
            parsed = json.loads(stdout)
            return (1, parsed, None)
        except (json.JSONDecodeError, ValueError):
            return (1, stdout, None)

    def StoreFindings(self, params):
        """Create ContextRAM nodes for each pattern type."""
        patterns = self._p(params, "patterns", {})
        canonical = self._p(params, "canonical", "")
        if not patterns:
            return (0, None, ("NO_PATTERNS", "patterns param is required", 0))

        stored = []
        for pattern_name, examples in patterns.items():
            is_canonical = (pattern_name == canonical)
            content_parts = []
            content_parts.append("BCL pattern: " + pattern_name)
            content_parts.append("canonical=" + ("yes" if is_canonical else "no"))
            if isinstance(examples, list) and examples:
                content_parts.append("example_count=" + str(len(examples)))
                first = examples[0]
                if isinstance(first, dict) and "text" in first:
                    content_parts.append("sample=" + str(first["text"])[:100])
            content = "; ".join(content_parts)
            tags = TAG_BCL + "," + TAG_PATTERN + "," + pattern_name
            args = ["put", "--type", "fact", "--content", content, "--tags", tags]
            ok, data, err = self.ExecCtx(args)
            if not ok:
                return (0, None, err)
            stored.append({"pattern": pattern_name, "result": data})

        self.state["results"]["stored_findings"] = stored
        return (1, {"stored": stored, "count": len(stored)}, None)

    def StoreRepair(self, params):
        """Create ContextRAM nodes for each repair."""
        changes = self._p(params, "changes", [])
        if not changes:
            return (0, None, ("NO_CHANGES", "changes param is required", 0))

        stored = []
        for change in changes:
            if not isinstance(change, dict):
                continue
            pattern = change.get("pattern", "")
            fix_action = change.get("fix_action", change.get("fix", ""))
            if not pattern:
                continue
            content_parts = []
            content_parts.append("BCL repair for pattern: " + pattern)
            content_parts.append("fix_action=" + str(fix_action)[:200])
            content = "; ".join(content_parts)
            tags = TAG_BCL + "," + TAG_REPAIR
            args = ["put", "--type", "result", "--content", content, "--tags", tags]
            ok, data, err = self.ExecCtx(args)
            if not ok:
                return (0, None, err)
            stored.append({"pattern": pattern, "result": data})

        self.state["results"]["stored_repairs"] = stored
        return (1, {"stored": stored, "count": len(stored)}, None)

    def QueryFindings(self, params):
        """Query ContextRAM for bcl-tagged findings."""
        tag = self._p(params, "tag", TAG_BCL)
        limit = self._p(params, "limit", QUERY_LIMIT)
        args = ["query", "--tag", str(tag), "--limit", str(limit)]
        ok, data, err = self.ExecCtx(args)
        if not ok:
            return (0, None, err)
        return (1, {"findings": data, "tag": tag}, None)

    def Assemble(self, params):
        """Call ctx assemble to get relevant context for a query."""
        query = self._p(params, "query", "")
        if not query:
            return (0, None, ("NO_QUERY", "query param is required", 0))
        args = ["assemble", "--query", query]
        ok, data, err = self.ExecCtx(args)
        if not ok:
            return (0, None, err)
        return (1, {"assembled": data, "query": query}, None)
