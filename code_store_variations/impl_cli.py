"""VBStyle domain implementation: cli.

Command-line interface utilities: parsing, dispatch, history, piping.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import shlex
import os
import signal
import time


class DomCli:
    """CLI domain: argument parsing, command dispatch, shell utilities."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "alias": self.alias,
            "complete": self.complete,
            "dispatch": self.dispatch,
            "exit": self.exit,
            "help": self.help,
            "history": self.history,
            "parse_args": self.parse_args,
            "parse_flags": self.parse_flags,
            "parse_options": self.parse_options,
            "pipe": self.pipe,
            "redirect": self.redirect,
            "run": self.run,
            "signal": self.signal,
            "version": self.version,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def alias(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            target = params.get("target")
            aliases = self.state.setdefault("config", {}).setdefault("aliases", {})
            if name and target:
                aliases[name] = target
            result = {"domain": "cli", "method": "alias", "data": {"aliases": dict(aliases), "added": name}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ALIAS_ERROR", str(e), 0))

    def complete(self, params=None):
        params = params or {}
        try:
            fragment = params.get("fragment") or ""
            candidates = params.get("candidates") or []
            matches = [c for c in candidates if isinstance(c, str) and c.startswith(fragment)]
            result = {"domain": "cli", "method": "complete", "data": {"matches": matches, "count": len(matches)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPLETE_ERROR", str(e), 0))

    def dispatch(self, params=None):
        params = params or {}
        try:
            cmd = params.get("command") or ""
            registry = params.get("registry") or {}
            handler = registry.get(cmd)
            if handler is None:
                result = {"domain": "cli", "method": "dispatch", "data": {"found": False, "command": cmd}}
                return (1, result, None)
            args = params.get("args") or {}
            data = handler(args) if callable(handler) else handler
            result = {"domain": "cli", "method": "dispatch", "data": {"found": True, "command": cmd, "output": data}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DISPATCH_ERROR", str(e), 0))

    def exit(self, params=None):
        params = params or {}
        try:
            code = int(params.get("code", 0))
            self.state["results"].append({"event": "exit", "code": code, "ts": time.time()})
            result = {"domain": "cli", "method": "exit", "data": {"code": code, "exiting": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXIT_ERROR", str(e), 0))

    def help(self, params=None):
        params = params or {}
        try:
            commands = params.get("commands") or {}
            entries = []
            for name, desc in commands.items():
                entries.append({"command": name, "description": desc})
            result = {"domain": "cli", "method": "help", "data": {"entries": entries, "count": len(entries)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HELP_ERROR", str(e), 0))

    def history(self, params=None):
        params = params or {}
        try:
            limit = int(params.get("limit", 50))
            history = self.state.setdefault("config", {}).setdefault("history", [])
            entry = params.get("entry")
            if entry:
                history.append(entry)
            view = history[-limit:] if limit > 0 else list(history)
            result = {"domain": "cli", "method": "history", "data": {"history": view, "total": len(history)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HISTORY_ERROR", str(e), 0))

    def parse_args(self, params=None):
        params = params or {}
        try:
            raw = params.get("argv") or ""
            if isinstance(raw, list):
                tokens = [str(t) for t in raw]
            else:
                tokens = shlex.split(raw)
            result = {"domain": "cli", "method": "parse_args", "data": {"tokens": tokens, "count": len(tokens)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PARSE_ARGS_ERROR", str(e), 0))

    def parse_flags(self, params=None):
        params = params or {}
        try:
            tokens = params.get("tokens") or []
            flags = {}
            positional = []
            i = 0
            while i < len(tokens):
                t = tokens[i]
                if t.startswith("--"):
                    key = t[2:]
                    if "=" in key:
                        k, v = key.split("=", 1)
                        flags[k] = v
                    elif i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                        flags[key] = tokens[i + 1]
                        i += 1
                    else:
                        flags[key] = True
                elif t.startswith("-") and len(t) > 1:
                    flags[t[1:]] = True
                else:
                    positional.append(t)
                i += 1
            result = {"domain": "cli", "method": "parse_flags", "data": {"flags": flags, "positional": positional}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PARSE_FLAGS_ERROR", str(e), 0))

    def parse_options(self, params=None):
        params = params or {}
        try:
            tokens = params.get("tokens") or []
            spec = params.get("spec") or {}
            options = {}
            positional = []
            i = 0
            while i < len(tokens):
                t = tokens[i]
                if t in spec:
                    if i + 1 < len(tokens):
                        options[spec[t]] = tokens[i + 1]
                        i += 1
                    else:
                        options[spec[t]] = True
                elif t.startswith("--"):
                    options[t[2:]] = True
                else:
                    positional.append(t)
                i += 1
            result = {"domain": "cli", "method": "parse_options", "data": {"options": options, "positional": positional}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PARSE_OPTIONS_ERROR", str(e), 0))

    def pipe(self, params=None):
        params = params or {}
        try:
            stages = params.get("stages") or []
            data = params.get("input")
            trace = []
            for stage in stages:
                fn = stage.get("fn") if isinstance(stage, dict) else None
                if callable(fn):
                    data = fn(data)
                elif isinstance(stage, dict) and "map" in stage:
                    data = [stage["map"] for _ in [data]]
                trace.append({"stage": stage.get("name", str(len(trace))), "ok": True})
            result = {"domain": "cli", "method": "pipe", "data": {"output": data, "trace": trace, "stages": len(stages)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PIPE_ERROR", str(e), 0))

    def redirect(self, params=None):
        params = params or {}
        try:
            target = params.get("target")
            mode = params.get("mode") or "w"
            payload = params.get("payload")
            written = 0
            if target and payload is not None:
                with open(target, mode) as fh:
                    content = payload if isinstance(payload, str) else str(payload)
                    fh.write(content)
                    written = len(content)
            result = {"domain": "cli", "method": "redirect", "data": {"target": target, "bytes": written}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REDIRECT_ERROR", str(e), 0))

    def run(self, params=None):
        params = params or {}
        try:
            cmd = params.get("command") or ""
            argv = shlex.split(cmd) if isinstance(cmd, str) else list(cmd)
            if not argv:
                result = {"domain": "cli", "method": "run", "data": {"argv": [], "ok": False}}
                return (1, result, None)
            result = {"domain": "cli", "method": "run", "data": {"argv": argv, "program": argv[0], "args": argv[1:], "ok": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RUN_ERROR", str(e), 0))

    def signal(self, params=None):
        params = params or {}
        try:
            name = (params.get("name") or "TERM").upper()
            pid = int(params.get("pid", 0))
            sig = getattr(signal, f"SIG{name}", None)
            sig_num = int(sig) if sig is not None else None
            result = {"domain": "cli", "method": "signal", "data": {"name": name, "pid": pid, "signal": sig_num}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SIGNAL_ERROR", str(e), 0))

    def version(self, params=None):
        params = params or {}
        try:
            info = {
                "version": params.get("version") or "0.0.0",
                "name": params.get("name") or "cli",
                "python": os.sys.version.split()[0] if hasattr(os, "sys") else None,
            }
            result = {"domain": "cli", "method": "version", "data": info}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("VERSION_ERROR", str(e), 0))
