import time
import json
from collections import deque

class DomLogging:
    """Structured logging: levels, metrics, rotation, archive and flush."""

    LEVELS = {"trace": 0, "debug": 1, "info": 2, "warn": 3, "error": 4, "fatal": 5}

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {"level": "trace", "max_entries": 1000}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._entries = deque(maxlen=1000)
        self._archives = []
        self._metrics = {}

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "archive": self.archive,
            "debug": self.debug,
            "error": self.error,
            "event": self.event,
            "fatal": self.fatal,
            "filter": self.filter,
            "flush": self.flush,
            "info": self.info,
            "log": self.log,
            "metric": self.metric,
            "rotate": self.rotate,
            "trace": self.trace,
            "warn": self.warn,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def _level_ok(self, level):
        cfg_level = self.state["config"].get("level", "trace")
        return self.LEVELS.get(level, 0) >= self.LEVELS.get(cfg_level, 0)

    def _append(self, level, message, context=None):
        entry = {
            "ts": time.time(),
            "level": level,
            "message": message,
            "context": context or {},
        }
        self._entries.append(entry)
        return entry

    def _emit(self, level, params):
        params = params or {}
        try:
            message = params.get("message", "")
            context = params.get("context", {})
            entry = None
            if self._level_ok(level):
                entry = self._append(level, message, context)
            result = {"domain": "logging", "method": level, "data": entry, "emitted": entry is not None}
            return (1, result, None)
        except Exception as e:
            return (0, None, (f"{level.upper()}_ERROR", str(e), 0))

    def trace(self, params=None):
        return self._emit("trace", params)

    def debug(self, params=None):
        return self._emit("debug", params)

    def info(self, params=None):
        return self._emit("info", params)

    def warn(self, params=None):
        return self._emit("warn", params)

    def error(self, params=None):
        return self._emit("error", params)

    def fatal(self, params=None):
        return self._emit("fatal", params)

    def log(self, params=None):
        params = params or {}
        try:
            level = params.get("level", "info")
            message = params.get("message", "")
            context = params.get("context", {})
            entry = None
            if self._level_ok(level):
                entry = self._append(level, message, context)
            result = {"domain": "logging", "method": "log", "data": entry, "level": level, "emitted": entry is not None}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LOG_ERROR", str(e), 0))

    def event(self, params=None):
        params = params or {}
        try:
            name = params.get("name", "event")
            payload = params.get("payload", {})
            entry = self._append("info", name, {"event": True, "payload": payload})
            result = {"domain": "logging", "method": "event", "data": entry, "name": name}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EVENT_ERROR", str(e), 0))

    def metric(self, params=None):
        params = params or {}
        try:
            name = params.get("name", "")
            value = params.get("value", 0)
            op = params.get("op", "set")
            if op == "set":
                self._metrics[name] = value
            elif op == "add":
                self._metrics[name] = self._metrics.get(name, 0) + value
            elif op == "max":
                self._metrics[name] = max(self._metrics.get(name, value), value)
            elif op == "min":
                self._metrics[name] = min(self._metrics.get(name, value), value)
            result = {"domain": "logging", "method": "metric", "data": {name: self._metrics[name]}, "metrics": dict(self._metrics)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("METRIC_ERROR", str(e), 0))

    def filter(self, params=None):
        params = params or {}
        try:
            level = params.get("level")
            since = params.get("since")
            entries = list(self._entries)
            if level:
                entries = [e for e in entries if e["level"] == level]
            if since is not None:
                entries = [e for e in entries if e["ts"] >= since]
            result = {"domain": "logging", "method": "filter", "data": entries, "count": len(entries)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FILTER_ERROR", str(e), 0))

    def flush(self, params=None):
        params = params or {}
        try:
            entries = list(self._entries)
            self._entries.clear()
            result = {"domain": "logging", "method": "flush", "data": entries, "flushed": len(entries)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FLUSH_ERROR", str(e), 0))

    def rotate(self, params=None):
        params = params or {}
        try:
            entries = list(self._entries)
            self._entries.clear()
            self._archives.append(entries)
            result = {"domain": "logging", "method": "rotate", "data": {"rotated": len(entries), "archive_index": len(self._archives) - 1}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ROTATE_ERROR", str(e), 0))

    def archive(self, params=None):
        params = params or {}
        try:
            index = params.get("index")
            if index is None and self._archives:
                index = len(self._archives) - 1
            if index is None or index >= len(self._archives):
                result = {"domain": "logging", "method": "archive", "data": None, "found": False}
            else:
                serialized = json.dumps(self._archives[index])
                result = {"domain": "logging", "method": "archive", "data": serialized, "found": True, "index": index, "size": len(serialized)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ARCHIVE_ERROR", str(e), 0))
