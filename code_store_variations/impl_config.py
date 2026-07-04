import os
import json
import time


class DomConfig:
    """Config domain: load, merge, watch, and manage configuration profiles using stdlib."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": [], "profiles": {}, "watches": {}, "env": dict(os.environ)}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        dispatch = {
            "delete": self.delete, "environment": self.environment, "import": self.import_,
            "load": self.load, "merge": self.merge, "profile": self.profile,
            "reload": self.reload, "watch": self.watch,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def delete(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            section = params.get("section")
            removed = False
            if section is not None and isinstance(self.state["config"].get(section), dict):
                removed = self.state["config"][section].pop(key, None) is not None
            elif key in self.state["config"]:
                del self.state["config"][key]
                removed = True
            result = {"domain": "config", "method": "delete", "key": key, "section": section, "removed": removed, "remaining": len(self.state["config"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DELETE_ERROR", str(e), 0))

    def environment(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            if key is not None:
                value = self.state["env"].get(key)
                result = {"domain": "config", "method": "environment", "key": key, "value": value, "found": value is not None}
            else:
                result = {"domain": "config", "method": "environment", "env_count": len(self.state["env"]), "keys": list(self.state["env"].keys())[:50]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ENVIRONMENT_ERROR", str(e), 0))

    def import_(self, params=None):
        params = params or {}
        try:
            data = params.get("data") or {}
            overwrite = params.get("overwrite", False)
            if overwrite:
                self.state["config"] = dict(data)
            else:
                self.state["config"].update(data)
            result = {"domain": "config", "method": "import", "imported_keys": len(data), "total_keys": len(self.state["config"]), "overwrite": overwrite}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("IMPORT_ERROR", str(e), 0))

    def load(self, params=None):
        params = params or {}
        try:
            path = str(params.get("path", ""))
            fmt = params.get("format", "json")
            data = {}
            if path and os.path.exists(path):
                with open(path, "r") as f:
                    content = f.read()
                if fmt == "json":
                    data = json.loads(content)
                else:
                    data = {"raw": content}
            self.state["config"] = data
            result = {"domain": "config", "method": "load", "path": path, "format": fmt, "loaded": bool(data), "keys": len(data) if isinstance(data, dict) else 0}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LOAD_ERROR", str(e), 0))

    def merge(self, params=None):
        params = params or {}
        try:
            other = params.get("config") or {}
            deep = params.get("deep", False)
            if deep:
                for k, v in other.items():
                    if isinstance(v, dict) and isinstance(self.state["config"].get(k), dict):
                        self.state["config"][k].update(v)
                    else:
                        self.state["config"][k] = v
            else:
                self.state["config"].update(other)
            result = {"domain": "config", "method": "merge", "merged_keys": len(other), "total_keys": len(self.state["config"]), "deep": deep}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MERGE_ERROR", str(e), 0))

    def profile(self, params=None):
        params = params or {}
        try:
            name = str(params.get("name", "default"))
            action = params.get("action", "save")
            if action == "save":
                self.state["profiles"][name] = {"config": dict(self.state["config"]), "ts": time.time()}
                result = {"domain": "config", "method": "profile", "name": name, "action": "save", "total_profiles": len(self.state["profiles"])}
            elif action == "load":
                prof = self.state["profiles"].get(name)
                if prof is not None:
                    self.state["config"] = dict(prof.get("config", {}))
                result = {"domain": "config", "method": "profile", "name": name, "action": "load", "found": prof is not None}
            elif action == "list":
                result = {"domain": "config", "method": "profile", "action": "list", "profiles": list(self.state["profiles"].keys())}
            else:
                result = {"domain": "config", "method": "profile", "name": name, "action": action, "error": "unknown_action"}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PROFILE_ERROR", str(e), 0))

    def reload(self, params=None):
        params = params or {}
        try:
            path = str(params.get("path", ""))
            data = {}
            if path and os.path.exists(path):
                with open(path, "r") as f:
                    data = json.load(f)
            self.state["config"] = data
            self.state["env"] = dict(os.environ)
            result = {"domain": "config", "method": "reload", "path": path, "reloaded": True, "keys": len(data)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RELOAD_ERROR", str(e), 0))

    def watch(self, params=None):
        params = params or {}
        try:
            path = str(params.get("path", ""))
            interval = int(params.get("interval", 5))
            mtime = os.path.getmtime(path) if path and os.path.exists(path) else None
            self.state["watches"][path] = {"mtime": mtime, "interval": interval, "ts": time.time()}
            result = {"domain": "config", "method": "watch", "path": path, "interval": interval, "mtime": mtime, "total_watches": len(self.state["watches"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("WATCH_ERROR", str(e), 0))
