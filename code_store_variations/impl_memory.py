import time
import zlib


class DomMemory:
    """In-memory key-value store with TTL, compression, and persistence hooks."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._store = {}
        self._expiry = {}

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "cache": self.cache,
            "clear": self.clear,
            "compress": self.compress,
            "expire": self.expire,
            "forget": self.forget,
            "invalidate": self.invalidate,
            "keys": self.keys,
            "load": self.load,
            "persist": self.persist,
            "recall": self.recall,
            "refresh": self.refresh,
            "restore": self.restore,
            "size": self.size,
            "store": self.store,
        }
        if command in handlers:
            return handlers[command](params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def _purge_expired(self):
        now = time.time()
        expired = [k for k, t in self._expiry.items() if t is not None and t < now]
        for k in expired:
            self._store.pop(k, None)
            self._expiry.pop(k, None)
        return expired

    def store(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            value = params.get("value")
            ttl = params.get("ttl")
            if key is None:
                return (0, None, ("STORE_ERROR", "missing key", 0))
            self._store[key] = value
            if ttl is not None:
                self._expiry[key] = time.time() + ttl
            else:
                self._expiry[key] = None
            result = {"domain": "memory", "method": "store", "data": {"key": key, "stored": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STORE_ERROR", str(e), 0))

    def recall(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            self._purge_expired()
            value = self._store.get(key)
            found = key in self._store
            result = {"domain": "memory", "method": "recall", "data": {"key": key, "value": value, "found": found}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RECALL_ERROR", str(e), 0))

    def cache(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            value = params.get("value")
            ttl = params.get("ttl", 60)
            if key is None:
                return (0, None, ("CACHE_ERROR", "missing key", 0))
            self._store[key] = value
            self._expiry[key] = time.time() + ttl
            result = {"domain": "memory", "method": "cache", "data": {"key": key, "cached": True, "ttl": ttl}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CACHE_ERROR", str(e), 0))

    def clear(self, params=None):
        params = params or {}
        try:
            count = len(self._store)
            self._store.clear()
            self._expiry.clear()
            result = {"domain": "memory", "method": "clear", "data": {"cleared": count}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CLEAR_ERROR", str(e), 0))

    def compress(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            self._purge_expired()
            value = self._store.get(key)
            if value is None:
                return (0, None, ("COMPRESS_ERROR", "key not found", 0))
            import json as _json
            raw = _json.dumps(value).encode("utf-8")
            compressed = zlib.compress(raw)
            self._store[key] = {"__compressed__": True, "data": compressed}
            result = {"domain": "memory", "method": "compress", "data": {"key": key, "original_size": len(raw), "compressed_size": len(compressed)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPRESS_ERROR", str(e), 0))

    def expire(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            ttl = params.get("ttl", 0)
            if key in self._store:
                self._expiry[key] = time.time() + ttl
                result = {"domain": "memory", "method": "expire", "data": {"key": key, "expires_at": self._expiry[key]}}
                return (1, result, None)
            return (0, None, ("EXPIRE_ERROR", "key not found", 0))
        except Exception as e:
            return (0, None, ("EXPIRE_ERROR", str(e), 0))

    def forget(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            existed = key in self._store
            self._store.pop(key, None)
            self._expiry.pop(key, None)
            result = {"domain": "memory", "method": "forget", "data": {"key": key, "forgot": existed}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FORGET_ERROR", str(e), 0))

    def invalidate(self, params=None):
        params = params or {}
        try:
            pattern = params.get("pattern", "")
            import fnmatch
            matched = [k for k in list(self._store.keys()) if fnmatch.fnmatch(str(k), pattern)]
            for k in matched:
                self._store.pop(k, None)
                self._expiry.pop(k, None)
            result = {"domain": "memory", "method": "invalidate", "data": {"invalidated": matched, "count": len(matched)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("INVALIDATE_ERROR", str(e), 0))

    def keys(self, params=None):
        params = params or {}
        try:
            self._purge_expired()
            all_keys = list(self._store.keys())
            result = {"domain": "memory", "method": "keys", "data": {"keys": all_keys, "count": len(all_keys)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("KEYS_ERROR", str(e), 0))

    def load(self, params=None):
        params = params or {}
        try:
            payload = params.get("payload", {})
            if isinstance(payload, dict):
                for k, v in payload.items():
                    self._store[k] = v
                    self._expiry[k] = None
            result = {"domain": "memory", "method": "load", "data": {"loaded": len(payload) if isinstance(payload, dict) else 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LOAD_ERROR", str(e), 0))

    def persist(self, params=None):
        params = params or {}
        try:
            import json as _json
            self._purge_expired()
            snapshot = {"store": self._store, "expiry": self._expiry}
            data = _json.dumps(snapshot, default=str)
            result = {"domain": "memory", "method": "persist", "data": {"size": len(data), "snapshot": data}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PERSIST_ERROR", str(e), 0))

    def refresh(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            ttl = params.get("ttl", 60)
            if key in self._store:
                self._expiry[key] = time.time() + ttl
                result = {"domain": "memory", "method": "refresh", "data": {"key": key, "refreshed": True, "new_expiry": self._expiry[key]}}
                return (1, result, None)
            return (0, None, ("REFRESH_ERROR", "key not found", 0))
        except Exception as e:
            return (0, None, ("REFRESH_ERROR", str(e), 0))

    def restore(self, params=None):
        params = params or {}
        try:
            import json as _json
            snapshot = params.get("snapshot", "")
            if not snapshot:
                return (0, None, ("RESTORE_ERROR", "missing snapshot", 0))
            data = _json.loads(snapshot)
            self._store = data.get("store", {})
            self._expiry = data.get("expiry", {})
            result = {"domain": "memory", "method": "restore", "data": {"restored": len(self._store)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RESTORE_ERROR", str(e), 0))

    def size(self, params=None):
        params = params or {}
        try:
            self._purge_expired()
            count = len(self._store)
            result = {"domain": "memory", "method": "size", "data": {"size": count}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SIZE_ERROR", str(e), 0))
