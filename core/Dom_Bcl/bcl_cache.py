#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_cache.py"
# date="2026-06-27" author="Cascade" session_id="bcl-missing-classes"
# context="BCL Cache — dedicated incremental compilation cache manager, replaces inline .bcl_cache JSON in IRCompiler"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_cache.py" domain="BCL" authority="BCLCache"}
# [@SUMMARY]{summary="BCL Cache: manages incremental compilation cache. Stores file hashes, detects changes, invalidates stale entries. Persists to JSON file."}
# [@CLASS]{class="BCLCache" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="load" type="command"}
# [@METHOD]{method="save" type="command"}
# [@METHOD]{method="get" type="command"}
# [@METHOD]{method="set" type="command"}
# [@METHOD]{method="invalidate" type="command"}
# [@METHOD]{method="is_stale" type="command"}
# [@METHOD]{method="clear" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import hashlib
import json
import os


class BCLCache:
    """Incremental compilation cache manager."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "cache_path": os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bcl_cache"),
            },
            "entries": {},
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "load":
            return self.Load(params)
        elif command == "save":
            return self.Save(params)
        elif command == "get":
            return self.Get(params)
        elif command == "set":
            return self.Set(params)
        elif command == "invalidate":
            return self.Invalidate(params)
        elif command == "is_stale":
            return self.IsStale(params)
        elif command == "clear":
            return self.Clear(params)
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

    def Load(self, params=None):
        cache_path = self.state["config"]["cache_path"]
        if not os.path.exists(cache_path):
            self.state["entries"] = {}
            return (1, {"loaded": False, "entries": 0, "reason": "no cache file"}, None)
        try:
            with open(cache_path, "r") as f:
                self.state["entries"] = json.load(f)
        except Exception as e:
            self.state["entries"] = {}
            return (0, None, ("CACHE_LOAD_ERROR", str(e), 0))
        return (1, {"loaded": True, "entries": len(self.state["entries"])}, None)

    def Save(self, params=None):
        cache_path = self.state["config"]["cache_path"]
        try:
            with open(cache_path, "w") as f:
                json.dump(self.state["entries"], f, indent=2)
        except Exception as e:
            return (0, None, ("CACHE_SAVE_ERROR", str(e), 0))
        return (1, {"saved": True, "entries": len(self.state["entries"]), "path": cache_path}, None)

    def Get(self, params):
        key = self._p(params, "key")
        if key is None:
            return (0, None, ("MISSING_PARAM", "key required", 0))
        entry = self.state["entries"].get(key)
        if entry is None:
            return (1, {"found": False}, None)
        return (1, {"found": True, "entry": entry}, None)

    def Set(self, params):
        key = self._p(params, "key")
        file_hash = self._p(params, "file_hash")
        result = self._p(params, "result")
        if key is None:
            return (0, None, ("MISSING_PARAM", "key required", 0))
        self.state["entries"][key] = {
            "file_hash": file_hash or "",
            "result": result,
        }
        return (1, {"set": True, "key": key}, None)

    def Invalidate(self, params):
        key = self._p(params, "key")
        if key is None:
            return (0, None, ("MISSING_PARAM", "key required", 0))
        if key in self.state["entries"]:
            del self.state["entries"][key]
            return (1, {"invalidated": True, "key": key}, None)
        return (1, {"invalidated": False, "key": key}, None)

    def IsStale(self, params):
        key = self._p(params, "key")
        current_hash = self._p(params, "file_hash")
        if key is None or current_hash is None:
            return (0, None, ("MISSING_PARAM", "key and file_hash required", 0))
        entry = self.state["entries"].get(key)
        if entry is None:
            return (1, {"stale": True, "reason": "not_cached"}, None)
        if entry.get("file_hash", "") != current_hash:
            return (1, {"stale": True, "reason": "hash_mismatch"}, None)
        return (1, {"stale": False, "reason": "current"}, None)

    def Clear(self, params=None):
        count = len(self.state["entries"])
        self.state["entries"] = {}
        return (1, {"cleared": True, "removed": count}, None)

    def FileHash(self, params):
        filepath = self._p(params, "filepath")
        if filepath is None:
            return (0, None, ("MISSING_PARAM", "filepath required", 0))
        try:
            with open(filepath, "r") as f:
                content = f.read()
            return (1, hashlib.md5(content.encode()).hexdigest(), None)
        except Exception as e:
            return (0, None, ("HASH_ERROR", str(e), 0))
