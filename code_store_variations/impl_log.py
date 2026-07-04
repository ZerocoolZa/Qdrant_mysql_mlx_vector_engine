import time


class DomLog:
    """Log management: write, read, filter, rotate, archive, tail, follow, purge."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._entries = []
        self._level_order = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3, "FATAL": 4}
        self._config = {"level": "INFO", "max_entries": 1000}
        self._follow_pos = 0

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "archive": self.archive,
            "category": self.category,
            "filter": self.filter,
            "follow": self.follow,
            "format": self.format,
            "level": self.level,
            "purge": self.purge,
            "read": self.read,
            "rotate": self.rotate,
            "tail": self.tail,
            "write": self.write,
        }
        if command in handlers:
            return handlers[command](params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def write(self, params=None):
        params = params or {}
        try:
            msg = params.get("message", "")
            lvl = params.get("level", "INFO").upper()
            cat = params.get("category", "general")
            entry = {"ts": time.time(), "level": lvl, "category": cat, "message": msg}
            self._entries.append(entry)
            if len(self._entries) > self._config["max_entries"]:
                self._entries = self._entries[-self._config["max_entries"]:]
            result = {"domain": "log", "method": "write", "data": {"written": True, "index": len(self._entries) - 1}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("WRITE_ERROR", str(e), 0))

    def read(self, params=None):
        params = params or {}
        try:
            count = params.get("count", 100)
            offset = params.get("offset", 0)
            entries = self._entries[offset:offset + count]
            result = {"domain": "log", "method": "read", "data": {"entries": entries, "total": len(self._entries)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("READ_ERROR", str(e), 0))

    def filter(self, params=None):
        params = params or {}
        try:
            level = params.get("level")
            category = params.get("category")
            matched = []
            for e in self._entries:
                if level and e["level"] != level.upper():
                    continue
                if category and e["category"] != category:
                    continue
                matched.append(e)
            result = {"domain": "log", "method": "filter", "data": {"entries": matched, "count": len(matched)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FILTER_ERROR", str(e), 0))

    def level(self, params=None):
        params = params or {}
        try:
            if "set" in params:
                self._config["level"] = params["set"].upper()
            result = {"domain": "log", "method": "level", "data": {"level": self._config["level"], "order": self._level_order}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LEVEL_ERROR", str(e), 0))

    def category(self, params=None):
        params = params or {}
        try:
            cats = {}
            for e in self._entries:
                cats[e["category"]] = cats.get(e["category"], 0) + 1
            result = {"domain": "log", "method": "category", "data": {"categories": cats}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CATEGORY_ERROR", str(e), 0))

    def format(self, params=None):
        params = params or {}
        try:
            fmt = params.get("format", "{ts} [{level}] {category}: {message}")
            lines = []
            for e in self._entries:
                lines.append(fmt.format(ts=e["ts"], level=e["level"], category=e["category"], message=e["message"]))
            result = {"domain": "log", "method": "format", "data": {"lines": lines, "format": fmt}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FORMAT_ERROR", str(e), 0))

    def tail(self, params=None):
        params = params or {}
        try:
            n = params.get("count", 10)
            entries = self._entries[-n:] if n > 0 else []
            result = {"domain": "log", "method": "tail", "data": {"entries": entries, "count": len(entries)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TAIL_ERROR", str(e), 0))

    def follow(self, params=None):
        params = params or {}
        try:
            new_entries = self._entries[self._follow_pos:]
            self._follow_pos = len(self._entries)
            result = {"domain": "log", "method": "follow", "data": {"entries": new_entries, "count": len(new_entries)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FOLLOW_ERROR", str(e), 0))

    def rotate(self, params=None):
        params = params or {}
        try:
            archived = list(self._entries)
            self._entries = []
            result = {"domain": "log", "method": "rotate", "data": {"rotated": len(archived), "archived_entries": archived}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ROTATE_ERROR", str(e), 0))

    def archive(self, params=None):
        params = params or {}
        try:
            import json as _json
            data = _json.dumps(self._entries, default=str)
            result = {"domain": "log", "method": "archive", "data": {"archive": data, "size": len(data), "entries": len(self._entries)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ARCHIVE_ERROR", str(e), 0))

    def purge(self, params=None):
        params = params or {}
        try:
            before = len(self._entries)
            older_than = params.get("older_than")
            if older_than is not None:
                cutoff = time.time() - older_than
                self._entries = [e for e in self._entries if e["ts"] >= cutoff]
            else:
                self._entries = []
            self._follow_pos = 0
            result = {"domain": "log", "method": "purge", "data": {"purged": before - len(self._entries), "remaining": len(self._entries)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PURGE_ERROR", str(e), 0))
