"""VBStyle domain implementation: caching.

Multi-layer cache: LRU, TTL, stampede prevention, invalidation, warming.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import time
import threading
import collections
import hashlib


class DomCaching:
    """Multi-layer cache: LRU, TTL, stampede prevention, invalidation, warming."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._cache = collections.OrderedDict()
        self._expiry = {}
        self._lock = threading.RLock()
        self._max_size = 1024
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "evictions": 0, "computes": 0}
        self._inflight = {}
        self._default_ttl = 300

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "get": self.get,
            "set": self.set,
            "invalidate": self.invalidate,
            "warm": self.warm,
            "evict": self.evict,
            "stats": self.stats,
            "clear": self.clear,
            "get_or_compute": self.get_or_compute,
            "set_ttl": self.set_ttl,
            "prevent_stampede": self.prevent_stampede,
            "backfill": self.backfill,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def _purge_expired(self):
        now = time.time()
        expired = [k for k, t in self._expiry.items() if t is not None and t < now]
        for k in expired:
            self._cache.pop(k, None)
            self._expiry.pop(k, None)
        return expired

    def _evict_lru(self):
        while len(self._cache) > self._max_size:
            k, _ = self._cache.popitem(last=False)
            self._expiry.pop(k, None)
            self._stats["evictions"] += 1

    def get(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            if key is None:
                return (0, None, ("GET_ERROR", "missing key", 0))
            with self._lock:
                self._purge_expired()
                if key in self._cache:
                    self._cache.move_to_end(key)
                    self._stats["hits"] += 1
                    value = self._cache[key]
                    result = {"domain": "caching", "method": "get", "data": {"key": key, "value": value, "found": True}}
                else:
                    self._stats["misses"] += 1
                    result = {"domain": "caching", "method": "get", "data": {"key": key, "value": None, "found": False}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GET_ERROR", str(e), 0))

    def set(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            value = params.get("value")
            ttl = params.get("ttl", self._default_ttl)
            if key is None:
                return (0, None, ("SET_ERROR", "missing key", 0))
            with self._lock:
                self._cache[key] = value
                self._cache.move_to_end(key)
                self._expiry[key] = time.time() + ttl if ttl else None
                self._evict_lru()
                self._stats["sets"] += 1
            result = {"domain": "caching", "method": "set", "data": {"key": key, "stored": True, "ttl": ttl}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SET_ERROR", str(e), 0))

    def invalidate(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            pattern = params.get("pattern")
            with self._lock:
                if pattern:
                    import fnmatch
                    matched = [k for k in self._cache if fnmatch.fnmatch(str(k), pattern)]
                    for k in matched:
                        self._cache.pop(k, None)
                        self._expiry.pop(k, None)
                    result = {"domain": "caching", "method": "invalidate", "data": {"pattern": pattern, "invalidated": len(matched)}}
                elif key is not None:
                    removed = key in self._cache
                    self._cache.pop(key, None)
                    self._expiry.pop(key, None)
                    result = {"domain": "caching", "method": "invalidate", "data": {"key": key, "invalidated": removed}}
                else:
                    return (0, None, ("INVALIDATE_ERROR", "missing key or pattern", 0))
            return (1, result, None)
        except Exception as e:
            return (0, None, ("INVALIDATE_ERROR", str(e), 0))

    def warm(self, params=None):
        params = params or {}
        try:
            entries = params.get("entries") or []
            if not isinstance(entries, list):
                return (0, None, ("WARM_ERROR", "entries must be a list", 0))
            count = 0
            with self._lock:
                for entry in entries:
                    k = entry.get("key")
                    v = entry.get("value")
                    ttl = entry.get("ttl", self._default_ttl)
                    if k is None:
                        continue
                    self._cache[k] = v
                    self._cache.move_to_end(k)
                    self._expiry[k] = time.time() + ttl if ttl else None
                    count += 1
                self._evict_lru()
            result = {"domain": "caching", "method": "warm", "data": {"warmed": count}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("WARM_ERROR", str(e), 0))

    def evict(self, params=None):
        params = params or {}
        try:
            count = int(params.get("count", 1))
            evicted = []
            with self._lock:
                for _ in range(min(count, len(self._cache))):
                    k, _ = self._cache.popitem(last=False)
                    self._expiry.pop(k, None)
                    evicted.append(k)
                    self._stats["evictions"] += 1
            result = {"domain": "caching", "method": "evict", "data": {"evicted": evicted, "count": len(evicted)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EVICT_ERROR", str(e), 0))

    def stats(self, params=None):
        params = params or {}
        try:
            with self._lock:
                self._purge_expired()
                size = len(self._cache)
                snapshot = dict(self._stats)
            snapshot["size"] = size
            snapshot["max_size"] = self._max_size
            hits = snapshot["hits"]
            total = hits + snapshot["misses"]
            snapshot["hit_rate"] = (hits / total) if total > 0 else 0.0
            result = {"domain": "caching", "method": "stats", "data": snapshot}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STATS_ERROR", str(e), 0))

    def clear(self, params=None):
        params = params or {}
        try:
            with self._lock:
                count = len(self._cache)
                self._cache.clear()
                self._expiry.clear()
            result = {"domain": "caching", "method": "clear", "data": {"cleared": count}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CLEAR_ERROR", str(e), 0))

    def get_or_compute(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            if key is None:
                return (0, None, ("GET_OR_COMPUTE_ERROR", "missing key", 0))
            ttl = params.get("ttl", self._default_ttl)
            with self._lock:
                self._purge_expired()
                if key in self._cache:
                    self._cache.move_to_end(key)
                    self._stats["hits"] += 1
                    result = {"domain": "caching", "method": "get_or_compute", "data": {"key": key, "value": self._cache[key], "computed": False}}
                    return (1, result, None)
            value = params.get("value")
            with self._lock:
                if key in self._cache:
                    self._cache.move_to_end(key)
                    self._stats["hits"] += 1
                    result = {"domain": "caching", "method": "get_or_compute", "data": {"key": key, "value": self._cache[key], "computed": False}}
                    return (1, result, None)
                self._cache[key] = value
                self._cache.move_to_end(key)
                self._expiry[key] = time.time() + ttl if ttl else None
                self._evict_lru()
                self._stats["misses"] += 1
                self._stats["computes"] += 1
            result = {"domain": "caching", "method": "get_or_compute", "data": {"key": key, "value": value, "computed": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GET_OR_COMPUTE_ERROR", str(e), 0))

    def set_ttl(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            ttl = params.get("ttl")
            if key is None or ttl is None:
                return (0, None, ("SET_TTL_ERROR", "missing key or ttl", 0))
            with self._lock:
                if key not in self._cache:
                    result = {"domain": "caching", "method": "set_ttl", "data": {"key": key, "updated": False}}
                    return (1, result, None)
                self._expiry[key] = time.time() + float(ttl) if ttl else None
            result = {"domain": "caching", "method": "set_ttl", "data": {"key": key, "ttl": ttl, "updated": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SET_TTL_ERROR", str(e), 0))

    def prevent_stampede(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            if key is None:
                return (0, None, ("PREVENT_STAMPEDE_ERROR", "missing key", 0))
            lock_key = hashlib.sha256(str(key).encode()).hexdigest()[:16]
            with self._lock:
                if lock_key in self._inflight:
                    result = {"domain": "caching", "method": "prevent_stampede", "data": {"key": key, "acquired": False, "inflight": True}}
                    return (1, result, None)
                self._inflight[lock_key] = time.time()
            result = {"domain": "caching", "method": "prevent_stampede", "data": {"key": key, "acquired": True, "inflight": False}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PREVENT_STAMPEDE_ERROR", str(e), 0))

    def backfill(self, params=None):
        params = params or {}
        try:
            entries = params.get("entries") or []
            if not isinstance(entries, list):
                return (0, None, ("BACKFILL_ERROR", "entries must be a list", 0))
            count = 0
            with self._lock:
                for entry in entries:
                    k = entry.get("key")
                    v = entry.get("value")
                    ttl = entry.get("ttl", self._default_ttl)
                    if k is None or k in self._cache:
                        continue
                    self._cache[k] = v
                    self._cache.move_to_end(k)
                    self._expiry[k] = time.time() + ttl if ttl else None
                    count += 1
                self._evict_lru()
            result = {"domain": "caching", "method": "backfill", "data": {"backfilled": count}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BACKFILL_ERROR", str(e), 0))
