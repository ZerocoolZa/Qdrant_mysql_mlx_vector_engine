"""VBStyle domain implementation: rate_limiting.

Traffic control: token bucket, sliding window, quota enforcement.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import time
import threading
from collections import deque


class DomRateLimiting:
    """Rate limiting domain: token bucket, sliding window, quotas."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._buckets = {}
        self._windows = {}
        self._quotas = {}
        self._lock = threading.Lock()

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "check_limit": self.check_limit,
            "acquire_tokens": self.acquire_tokens,
            "release_tokens": self.release_tokens,
            "set_quota": self.set_quota,
            "get_remaining": self.get_remaining,
            "enforce_backpressure": self.enforce_backpressure,
            "get_stats": self.get_stats,
            "reset": self.reset,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def _refill(self, bucket, now):
        elapsed = now - bucket.get("last_refill", now)
        refill = elapsed * (bucket["capacity"] / bucket["refill_rate"])
        bucket["tokens"] = min(bucket["capacity"], bucket["tokens"] + refill)
        bucket["last_refill"] = now

    def check_limit(self, params=None):
        params = params or {}
        try:
            key = params.get("key", "default")
            capacity = float(params.get("capacity", 10))
            refill_rate = float(params.get("refill_rate", 1.0))
            cost = float(params.get("cost", 1.0))
            now = time.time()
            with self._lock:
                if key not in self._buckets:
                    self._buckets[key] = {"capacity": capacity, "refill_rate": refill_rate, "tokens": capacity, "last_refill": now}
                bucket = self._buckets[key]
                bucket["capacity"] = capacity
                bucket["refill_rate"] = refill_rate
                self._refill(bucket, now)
                allowed = bucket["tokens"] >= cost
                if allowed:
                    bucket["tokens"] -= cost
                remaining = bucket["tokens"]
            result = {"domain": "rate_limiting", "method": "check_limit", "data": {"key": key, "allowed": allowed, "remaining": remaining, "capacity": capacity}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_LIMIT_ERROR", str(e), 0))

    def acquire_tokens(self, params=None):
        params = params or {}
        try:
            key = params.get("key", "default")
            tokens = float(params.get("tokens", 1))
            capacity = float(params.get("capacity", 10))
            refill_rate = float(params.get("refill_rate", 1.0))
            wait = bool(params.get("wait", False))
            now = time.time()
            with self._lock:
                if key not in self._buckets:
                    self._buckets[key] = {"capacity": capacity, "refill_rate": refill_rate, "tokens": capacity, "last_refill": now}
                bucket = self._buckets[key]
                bucket["capacity"] = capacity
                bucket["refill_rate"] = refill_rate
                self._refill(bucket, now)
                acquired = 0.0
                if bucket["tokens"] >= tokens:
                    bucket["tokens"] -= tokens
                    acquired = tokens
                elif wait and tokens <= bucket["capacity"]:
                    deficit = tokens - bucket["tokens"]
                    needed = deficit / bucket["refill_rate"] if bucket["refill_rate"] > 0 else 0
                    bucket["tokens"] = 0
                    acquired = tokens
                else:
                    acquired = bucket["tokens"]
                    bucket["tokens"] = 0
                remaining = bucket["tokens"]
            result = {"domain": "rate_limiting", "method": "acquire_tokens", "data": {"key": key, "acquired": acquired, "requested": tokens, "remaining": remaining}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ACQUIRE_TOKENS_ERROR", str(e), 0))

    def release_tokens(self, params=None):
        params = params or {}
        try:
            key = params.get("key", "default")
            tokens = float(params.get("tokens", 1))
            with self._lock:
                bucket = self._buckets.get(key)
                if bucket is None:
                    return (0, None, ("RELEASE_TOKENS_ERROR", "bucket not found", 0))
                bucket["tokens"] = min(bucket["capacity"], bucket["tokens"] + tokens)
                remaining = bucket["tokens"]
            result = {"domain": "rate_limiting", "method": "release_tokens", "data": {"key": key, "released": tokens, "remaining": remaining}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RELEASE_TOKENS_ERROR", str(e), 0))

    def set_quota(self, params=None):
        params = params or {}
        try:
            key = params.get("key", "default")
            limit = int(params.get("limit", 1000))
            window = float(params.get("window", 3600.0))
            with self._lock:
                self._quotas[key] = {"limit": limit, "window": window, "used": 0, "period_start": time.time()}
                self._windows[key] = deque()
            result = {"domain": "rate_limiting", "method": "set_quota", "data": {"key": key, "limit": limit, "window": window}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SET_QUOTA_ERROR", str(e), 0))

    def get_remaining(self, params=None):
        params = params or {}
        try:
            key = params.get("key", "default")
            now = time.time()
            with self._lock:
                bucket = self._buckets.get(key)
                quota = self._quotas.get(key)
                bucket_remaining = None
                quota_remaining = None
                if bucket is not None:
                    self._refill(bucket, now)
                    bucket_remaining = bucket["tokens"]
                if quota is not None:
                    if now - quota["period_start"] >= quota["window"]:
                        quota["used"] = 0
                        quota["period_start"] = now
                    quota_remaining = max(0, quota["limit"] - quota["used"])
            result = {"domain": "rate_limiting", "method": "get_remaining", "data": {"key": key, "bucket_remaining": bucket_remaining, "quota_remaining": quota_remaining}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GET_REMAINING_ERROR", str(e), 0))

    def enforce_backpressure(self, params=None):
        params = params or {}
        try:
            key = params.get("key", "default")
            threshold = float(params.get("threshold", 0.8))
            now = time.time()
            with self._lock:
                bucket = self._buckets.get(key)
                if bucket is None:
                    return (0, None, ("ENFORCE_BACKPRESSURE_ERROR", "bucket not found", 0))
                self._refill(bucket, now)
                ratio = 1.0 - (bucket["tokens"] / bucket["capacity"]) if bucket["capacity"] > 0 else 0.0
                apply = ratio >= threshold
                delay = 0.0
                if apply:
                    deficit = bucket["capacity"] - bucket["tokens"]
                    delay = deficit / bucket["refill_rate"] if bucket["refill_rate"] > 0 else 0.0
            result = {"domain": "rate_limiting", "method": "enforce_backpressure", "data": {"key": key, "apply": apply, "ratio": ratio, "delay": delay, "threshold": threshold}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ENFORCE_BACKPRESSURE_ERROR", str(e), 0))

    def get_stats(self, params=None):
        params = params or {}
        try:
            now = time.time()
            with self._lock:
                buckets = {}
                for k, b in self._buckets.items():
                    self._refill(b, now)
                    buckets[k] = {"tokens": b["tokens"], "capacity": b["capacity"], "refill_rate": b["refill_rate"]}
                quotas = {}
                for k, q in self._quotas.items():
                    if now - q["period_start"] >= q["window"]:
                        q["used"] = 0
                        q["period_start"] = now
                    quotas[k] = {"limit": q["limit"], "used": q["used"], "window": q["window"]}
            result = {"domain": "rate_limiting", "method": "get_stats", "data": {"buckets": buckets, "quotas": quotas, "bucket_count": len(buckets), "quota_count": len(quotas)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GET_STATS_ERROR", str(e), 0))

    def reset(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            with self._lock:
                if key is None:
                    count = len(self._buckets) + len(self._quotas)
                    self._buckets.clear()
                    self._quotas.clear()
                    self._windows.clear()
                    result = {"domain": "rate_limiting", "method": "reset", "data": {"reset": "all", "count": count}}
                else:
                    removed = 0
                    if key in self._buckets:
                        del self._buckets[key]
                        removed += 1
                    if key in self._quotas:
                        del self._quotas[key]
                        removed += 1
                    if key in self._windows:
                        del self._windows[key]
                    result = {"domain": "rate_limiting", "method": "reset", "data": {"key": key, "removed": removed}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RESET_ERROR", str(e), 0))
