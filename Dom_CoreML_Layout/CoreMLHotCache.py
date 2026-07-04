#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLHotCache.py
#[@SUMMARY] Hot cache manager: keeps N experts in RAM, LRU eviction, swap on demand
#[@CLASS] CoreMLHotCache
#[@METHOD] acquire, release, stats, evict, clear
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import os
import time
import subprocess
import numpy as np
from Config_CoreMLLayout import INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM

CORETOTCH_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/coretotch"

WEIGHT_SIZE_BYTES = 23050 * 4
DEFAULT_HOT_CACHE_SIZE = 2


class CoreMLHotCache:
    """Hot cache for expert model weights.

    Keeps N most-recently-used experts loaded in RAM.
    When a new expert is needed and cache is full, evicts LRU.
    Cold models stay on disk (0 RAM).
    Hot models stay in memory (fast inference, no disk reload).

    Cache states:
      HOT   — loaded in RAM, ready for inference
      WARM  — recently used but evicted, path cached for fast reload
      COLD  — on disk only, not referenced recently
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "max_hot": DEFAULT_HOT_CACHE_SIZE,
                "cache_dir": "",
            },
            "cache": {},
            "access_log": [],
            "stats": {
                "hits": 0,
                "misses": 0,
                "evictions": 0,
                "reloads": 0,
            },
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "acquire":
            return self.cmdAcquire(params)
        if command == "release":
            return self.cmdRelease(params)
        if command == "stats":
            return self.cmdStats(params)
        if command == "evict":
            return self.cmdEvict(params)
        if command == "clear":
            return self.cmdClear(params)
        if command == "set_cache_size":
            return self.cmdSetCacheSize(params)
        if command == "read_state":
            return self.readState(params)
        if command == "set_config":
            return self.setConfig(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown: " + str(command), 0))

    def p(self, params, key, fallback=None):
        if not isinstance(params, dict):
            return fallback
        return params.get(key, fallback)

    def cmdAcquire(self, params):
        """Acquire an expert for inference. Loads into hot cache if not present."""
        try:
            name = self.p(params, "name")
            weightsPath = self.p(params, "weights_path")
            if not name or not weightsPath:
                return (0, None, ("PARAMS_ERROR", "name and weights_path required", 0))
            if not os.path.exists(weightsPath):
                return (0, None, ("WEIGHTS_NOT_FOUND", weightsPath, 0))
            cache = self.state["cache"]
            maxHot = self.state["config"]["max_hot"]
            if name in cache:
                cache[name]["last_access"] = time.time()
                cache[name]["access_count"] += 1
                self.state["stats"]["hits"] += 1
                self.state["access_log"].append({
                    "action": "hit",
                    "name": name,
                    "time": time.time(),
                })
                return (1, {
                    "status": "HIT",
                    "name": name,
                    "state": "HOT",
                    "ram_bytes": WEIGHT_SIZE_BYTES,
                    "access_count": cache[name]["access_count"],
                }, None)
            if len(cache) >= maxHot:
                evicted = self.evictLRU()
                if evicted:
                    self.state["stats"]["evictions"] += 1
                    self.state["access_log"].append({
                        "action": "evict",
                        "name": evicted,
                        "time": time.time(),
                    })
            weights = np.fromfile(weightsPath, dtype=np.float32)
            if weights.shape[0] != 23050:
                return (0, None, ("WEIGHTS_SHAPE", "Expected 23050, got " + str(weights.shape[0]), 0))
            cache[name] = {
                "weights": weights,
                "weights_path": weightsPath,
                "loaded_at": time.time(),
                "last_access": time.time(),
                "access_count": 1,
                "state": "HOT",
            }
            self.state["stats"]["misses"] += 1
            self.state["stats"]["reloads"] += 1
            self.state["access_log"].append({
                "action": "load",
                "name": name,
                "time": time.time(),
            })
            return (1, {
                "status": "MISS",
                "name": name,
                "state": "HOT",
                "ram_bytes": WEIGHT_SIZE_BYTES,
                "cache_size": len(cache),
                "max_hot": maxHot,
            }, None)
        except Exception as e:
            return (0, None, ("ACQUIRE_ERROR", str(e), 0))

    def evictLRU(self):
        """Evict least recently used expert from hot cache."""
        cache = self.state["cache"]
        if not cache:
            return None
        oldestName = None
        oldestTime = float("inf")
        for name, entry in cache.items():
            if entry["last_access"] < oldestTime:
                oldestTime = entry["last_access"]
                oldestName = name
        if oldestName:
            del cache[oldestName]
            return oldestName
        return None

    def cmdRelease(self, params):
        """Manually release an expert from hot cache."""
        try:
            name = self.p(params, "name")
            if not name:
                return (0, None, ("PARAMS_ERROR", "name required", 0))
            cache = self.state["cache"]
            if name not in cache:
                return (0, None, ("NOT_CACHED", name + " not in cache", 0))
            del cache[name]
            self.state["access_log"].append({
                "action": "release",
                "name": name,
                "time": time.time(),
            })
            return (1, {"released": name, "cache_size": len(cache)}, None)
        except Exception as e:
            return (0, None, ("RELEASE_ERROR", str(e), 0))

    def cmdEvict(self, params):
        """Evict LRU expert(s) to free RAM."""
        try:
            count = int(self.p(params, "count", 1))
            evicted = []
            for _ in range(count):
                name = self.evictLRU()
                if name:
                    evicted.append(name)
                    self.state["stats"]["evictions"] += 1
                else:
                    break
            return (1, {
                "evicted": evicted,
                "cache_size": len(self.state["cache"]),
                "freed_bytes": len(evicted) * WEIGHT_SIZE_BYTES,
            }, None)
        except Exception as e:
            return (0, None, ("EVICT_ERROR", str(e), 0))

    def cmdClear(self, params):
        """Clear entire hot cache."""
        try:
            count = len(self.state["cache"])
            self.state["cache"] = {}
            return (1, {
                "cleared": count,
                "freed_bytes": count * WEIGHT_SIZE_BYTES,
            }, None)
        except Exception as e:
            return (0, None, ("CLEAR_ERROR", str(e), 0))

    def cmdSetCacheSize(self, params):
        """Set max hot cache size. Evicts if current cache exceeds new limit."""
        try:
            newSize = int(self.p(params, "size", DEFAULT_HOT_CACHE_SIZE))
            if newSize < 0:
                return (0, None, ("PARAMS_ERROR", "size must be >= 0", 0))
            self.state["config"]["max_hot"] = newSize
            cache = self.state["cache"]
            while len(cache) > newSize:
                evicted = self.evictLRU()
                if not evicted:
                    break
                self.state["stats"]["evictions"] += 1
            return (1, {
                "max_hot": newSize,
                "current_cache": len(cache),
            }, None)
        except Exception as e:
            return (0, None, ("SET_SIZE_ERROR", str(e), 0))

    def cmdStats(self, params):
        """Get cache statistics."""
        try:
            cache = self.state["cache"]
            stats = self.state["stats"].copy()
            hotModels = []
            for name, entry in cache.items():
                hotModels.append({
                    "name": name,
                    "state": entry["state"],
                    "access_count": entry["access_count"],
                    "last_access": entry["last_access"],
                    "ram_bytes": WEIGHT_SIZE_BYTES,
                })
            hitRate = 0.0
            total = stats["hits"] + stats["misses"]
            if total > 0:
                hitRate = stats["hits"] / total
            return (1, {
                "stats": stats,
                "hit_rate": round(hitRate, 4),
                "hot_models": hotModels,
                "hot_count": len(cache),
                "max_hot": self.state["config"]["max_hot"],
                "ram_used_bytes": len(cache) * WEIGHT_SIZE_BYTES,
                "ram_used_kb": round(len(cache) * WEIGHT_SIZE_BYTES / 1024, 1),
                "cold_models_on_disk": "unlimited (disk only, 0 RAM)",
            }, None)
        except Exception as e:
            return (0, None, ("STATS_ERROR", str(e), 0))

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "cache_size": len(self.state["cache"]),
            "stats": self.state["stats"],
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
