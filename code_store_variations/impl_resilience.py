"""VBStyle domain implementation: resilience.

Fault tolerance: retry, circuit breaker, timeout, bulkhead, fallback.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import time
import threading


class DomResilience:
    """Resilience domain: retry, circuit breaker, timeout, bulkhead, fallback."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._breakers = {}
        self._bulkheads = {}
        self._lock = threading.Lock()

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "retry": self.retry,
            "circuit_breaker": self.circuit_breaker,
            "timeout": self.timeout,
            "bulkhead": self.bulkhead,
            "fallback": self.fallback,
            "get_breaker_state": self.get_breaker_state,
            "record_outcome": self.record_outcome,
            "reset_breaker": self.reset_breaker,
            "health_check": self.health_check,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def retry(self, params=None):
        params = params or {}
        try:
            attempts = int(params.get("attempts", 3))
            delay = float(params.get("delay", 0.0))
            backoff = float(params.get("backoff", 1.0))
            fn = params.get("fn")
            args = params.get("args", [])
            kwargs = params.get("kwargs", {})
            history = []
            last_err = None
            for i in range(attempts):
                start = time.time()
                try:
                    if callable(fn):
                        value = fn(*args, **kwargs)
                    else:
                        value = None
                    history.append({"attempt": i + 1, "ok": True, "elapsed": time.time() - start})
                    result = {"domain": "resilience", "method": "retry", "data": {"value": value, "attempts": i + 1, "history": history}}
                    return (1, result, None)
                except Exception as e:
                    last_err = str(e)
                    history.append({"attempt": i + 1, "ok": False, "elapsed": time.time() - start, "error": last_err})
                    if i < attempts - 1 and delay > 0:
                        time.sleep(delay * (backoff ** i))
            result = {"domain": "resilience", "method": "retry", "data": {"value": None, "attempts": attempts, "history": history, "error": last_err}}
            return (0, result, ("RETRY_EXHAUSTED", last_err or "exhausted", attempts))
        except Exception as e:
            return (0, None, ("RETRY_ERROR", str(e), 0))

    def circuit_breaker(self, params=None):
        params = params or {}
        try:
            name = params.get("name", "default")
            threshold = int(params.get("threshold", 5))
            reset_timeout = float(params.get("reset_timeout", 30.0))
            with self._lock:
                if name not in self._breakers:
                    self._breakers[name] = {
                        "state": "closed",
                        "failures": 0,
                        "threshold": threshold,
                        "reset_timeout": reset_timeout,
                        "opened_at": None,
                        "successes": 0,
                    }
                breaker = self._breakers[name]
                breaker["threshold"] = threshold
                breaker["reset_timeout"] = reset_timeout
            result = {"domain": "resilience", "method": "circuit_breaker", "data": {"name": name, "state": breaker["state"], "threshold": threshold, "reset_timeout": reset_timeout}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CIRCUIT_BREAKER_ERROR", str(e), 0))

    def timeout(self, params=None):
        params = params or {}
        try:
            seconds = float(params.get("seconds", 1.0))
            fn = params.get("fn")
            args = params.get("args", [])
            kwargs = params.get("kwargs", {})
            if not callable(fn):
                result = {"domain": "resilience", "method": "timeout", "data": {"timed_out": False, "value": None, "seconds": seconds}}
                return (1, result, None)
            box = {}
            def _runner():
                try:
                    box["value"] = fn(*args, **kwargs)
                    box["ok"] = True
                except Exception as e:
                    box["error"] = str(e)
                    box["ok"] = False
            t = threading.Thread(target=_runner, daemon=True)
            t.start()
            t.join(seconds)
            if t.is_alive():
                result = {"domain": "resilience", "method": "timeout", "data": {"timed_out": True, "seconds": seconds}}
                return (0, result, ("TIMEOUT_EXCEEDED", f"exceeded {seconds}s", seconds))
            if box.get("ok"):
                result = {"domain": "resilience", "method": "timeout", "data": {"timed_out": False, "value": box.get("value"), "seconds": seconds}}
                return (1, result, None)
            result = {"domain": "resilience", "method": "timeout", "data": {"timed_out": False, "seconds": seconds}}
            return (0, result, ("TIMEOUT_FN_ERROR", box.get("error", "fn error"), 0))
        except Exception as e:
            return (0, None, ("TIMEOUT_ERROR", str(e), 0))

    def bulkhead(self, params=None):
        params = params or {}
        try:
            name = params.get("name", "default")
            max_concurrent = int(params.get("max_concurrent", 4))
            with self._lock:
                if name not in self._bulkheads:
                    self._bulkheads[name] = {"max_concurrent": max_concurrent, "active": 0, "rejected": 0}
                self._bulkheads[name]["max_concurrent"] = max_concurrent
                bd = self._bulkheads[name]
                accepted = bd["active"] < bd["max_concurrent"]
                if accepted:
                    bd["active"] += 1
                else:
                    bd["rejected"] += 1
            result = {"domain": "resilience", "method": "bulkhead", "data": {"name": name, "accepted": accepted, "active": bd["active"], "max_concurrent": bd["max_concurrent"], "rejected": bd["rejected"]}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BULKHEAD_ERROR", str(e), 0))

    def fallback(self, params=None):
        params = params or {}
        try:
            primary = params.get("primary")
            fallback_fn = params.get("fallback")
            args = params.get("args", [])
            kwargs = params.get("kwargs", {})
            used = "primary"
            value = None
            error = None
            try:
                if callable(primary):
                    value = primary(*args, **kwargs)
                else:
                    raise ValueError("primary not callable")
            except Exception as e:
                used = "fallback"
                error = str(e)
                if callable(fallback_fn):
                    value = fallback_fn(*args, **kwargs)
                else:
                    raise
            result = {"domain": "resilience", "method": "fallback", "data": {"value": value, "used": used, "primary_error": error}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FALLBACK_ERROR", str(e), 0))

    def get_breaker_state(self, params=None):
        params = params or {}
        try:
            name = params.get("name", "default")
            with self._lock:
                breaker = self._breakers.get(name)
                if breaker is None:
                    state = "closed"
                    failures = 0
                    successes = 0
                else:
                    if breaker["state"] == "open" and breaker["opened_at"] is not None:
                        if time.time() - breaker["opened_at"] >= breaker["reset_timeout"]:
                            breaker["state"] = "half_open"
                    state = breaker["state"]
                    failures = breaker["failures"]
                    successes = breaker["successes"]
            result = {"domain": "resilience", "method": "get_breaker_state", "data": {"name": name, "state": state, "failures": failures, "successes": successes}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GET_BREAKER_STATE_ERROR", str(e), 0))

    def record_outcome(self, params=None):
        params = params or {}
        try:
            name = params.get("name", "default")
            success = bool(params.get("success", False))
            with self._lock:
                if name not in self._breakers:
                    self._breakers[name] = {"state": "closed", "failures": 0, "threshold": 5, "reset_timeout": 30.0, "opened_at": None, "successes": 0}
                breaker = self._breakers[name]
                if success:
                    breaker["successes"] += 1
                    breaker["failures"] = 0
                    if breaker["state"] == "half_open":
                        breaker["state"] = "closed"
                        breaker["opened_at"] = None
                else:
                    breaker["failures"] += 1
                    if breaker["failures"] >= breaker["threshold"]:
                        breaker["state"] = "open"
                        breaker["opened_at"] = time.time()
                state = breaker["state"]
                failures = breaker["failures"]
                successes = breaker["successes"]
            result = {"domain": "resilience", "method": "record_outcome", "data": {"name": name, "success": success, "state": state, "failures": failures, "successes": successes}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RECORD_OUTCOME_ERROR", str(e), 0))

    def reset_breaker(self, params=None):
        params = params or {}
        try:
            name = params.get("name", "default")
            with self._lock:
                if name in self._breakers:
                    self._breakers[name]["state"] = "closed"
                    self._breakers[name]["failures"] = 0
                    self._breakers[name]["successes"] = 0
                    self._breakers[name]["opened_at"] = None
                    reset = True
                else:
                    reset = False
            result = {"domain": "resilience", "method": "reset_breaker", "data": {"name": name, "reset": reset}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RESET_BREAKER_ERROR", str(e), 0))

    def health_check(self, params=None):
        params = params or {}
        try:
            checks = {}
            overall = True
            with self._lock:
                for name, breaker in self._breakers.items():
                    healthy = breaker["state"] != "open"
                    checks[name] = {"state": breaker["state"], "healthy": healthy}
                    if not healthy:
                        overall = False
                for name, bd in self._bulkheads.items():
                    saturated = bd["active"] >= bd["max_concurrent"]
                    checks[f"bulkhead:{name}"] = {"active": bd["active"], "max": bd["max_concurrent"], "saturated": saturated}
            result = {"domain": "resilience", "method": "health_check", "data": {"healthy": overall, "checks": checks}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HEALTH_CHECK_ERROR", str(e), 0))
