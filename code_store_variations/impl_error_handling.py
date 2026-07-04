"""VBStyle domain implementation: error_handling.

Error hierarchies, translation, recovery, and cause chains.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import traceback
import time
import uuid
from collections import deque


class DomErrorHandling:
    """Error handling domain: translation, context, retry classification, cause chains."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "errors": {},
            "seen": set(),
            "hierarchy": {},
        }
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "translate": self.translate,
            "create_context": self.create_context,
            "is_retryable": self.is_retryable,
            "cause_chain": self.cause_chain,
            "wrap": self.wrap,
            "classify": self.classify,
            "recover": self.recover,
            "suppress": self.suppress,
            "log_once": self.log_once,
            "get_hierarchy": self.get_hierarchy,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    @staticmethod
    def _exc(params):
        return params.get("exception") or params.get("error") or params.get("exc")

    def translate(self, params=None):
        params = params or {}
        try:
            exc = self._exc(params)
            mapping = params.get("mapping") or {}
            default = params.get("default", "UNKNOWN_ERROR")
            name = type(exc).__name__ if exc is not None else params.get("code", default)
            translated = mapping.get(name, default)
            result = {
                "domain": "error_handling",
                "method": "translate",
                "data": {"original": name, "translated": translated},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TRANSLATE_ERROR", str(e), 0))

    def create_context(self, params=None):
        params = params or {}
        try:
            ctx = {
                "id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "operation": params.get("operation", ""),
                "inputs": params.get("inputs", {}),
                "metadata": params.get("metadata", {}),
            }
            self.state["results"].append(ctx)
            result = {"domain": "error_handling", "method": "create_context", "data": ctx}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CREATE_CONTEXT_ERROR", str(e), 0))

    def is_retryable(self, params=None):
        params = params or {}
        try:
            exc = self._exc(params)
            retryable_types = params.get("retryable_types") or [
                "TimeoutError",
                "ConnectionError",
                "TransientError",
            ]
            name = type(exc).__name__ if exc is not None else params.get("code", "")
            retryable = name in retryable_types
            result = {
                "domain": "error_handling",
                "method": "is_retryable",
                "data": {"retryable": retryable, "type": name},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("IS_RETRYABLE_ERROR", str(e), 0))

    def cause_chain(self, params=None):
        params = params or {}
        try:
            exc = self._exc(params)
            chain = []
            current = exc
            seen = 0
            while current is not None and seen < 32:
                chain.append({
                    "type": type(current).__name__,
                    "message": str(current),
                })
                current = current.__cause__ or current.__context__
                seen += 1
            result = {
                "domain": "error_handling",
                "method": "cause_chain",
                "data": {"chain": chain, "depth": len(chain)},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CAUSE_CHAIN_ERROR", str(e), 0))

    def wrap(self, params=None):
        params = params or {}
        try:
            exc = self._exc(params)
            message = params.get("message", "wrapped error")
            context = params.get("context", {})
            wrapped = {
                "type": type(exc).__name__ if exc is not None else "WrappedError",
                "message": message,
                "original": str(exc) if exc is not None else None,
                "context": context,
                "timestamp": time.time(),
            }
            self.state["errors"][wrapped["type"]] = wrapped
            result = {"domain": "error_handling", "method": "wrap", "data": wrapped}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("WRAP_ERROR", str(e), 0))

    def classify(self, params=None):
        params = params or {}
        try:
            exc = self._exc(params)
            name = type(exc).__name__ if exc is not None else params.get("code", "Unknown")
            categories = {
                "transient": ["TimeoutError", "ConnectionError", "TransientError"],
                "permanent": ["ValueError", "TypeError", "KeyError", "AttributeError"],
                "security": ["PermissionError", "AuthenticationError"],
                "resource": ["MemoryError", "ResourceExhausted"],
            }
            category = "unknown"
            for cat, types in categories.items():
                if name in types:
                    category = cat
                    break
            result = {
                "domain": "error_handling",
                "method": "classify",
                "data": {"type": name, "category": category},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CLASSIFY_ERROR", str(e), 0))

    def recover(self, params=None):
        params = params or {}
        try:
            exc = self._exc(params)
            strategy = params.get("strategy", "default")
            fallback = params.get("fallback")
            recovered = fallback if fallback is not None else None
            result = {
                "domain": "error_handling",
                "method": "recover",
                "data": {
                    "recovered": recovered is not None,
                    "value": recovered,
                    "strategy": strategy,
                    "original": str(exc) if exc is not None else None,
                },
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RECOVER_ERROR", str(e), 0))

    def suppress(self, params=None):
        params = params or {}
        try:
            exc = self._exc(params)
            suppress_types = params.get("suppress_types") or ["Warning", "DeprecationWarning"]
            name = type(exc).__name__ if exc is not None else ""
            suppressed = name in suppress_types
            result = {
                "domain": "error_handling",
                "method": "suppress",
                "data": {"suppressed": suppressed, "type": name},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SUPPRESS_ERROR", str(e), 0))

    def log_once(self, params=None):
        params = params or {}
        try:
            key = params.get("key") or str(uuid.uuid4())
            message = params.get("message", "")
            if key in self.state["seen"]:
                result = {
                    "domain": "error_handling",
                    "method": "log_once",
                    "data": {"logged": False, "key": key, "duplicate": True},
                }
                return (1, result, None)
            self.state["seen"].add(key)
            entry = {"key": key, "message": message, "timestamp": time.time()}
            self.state["results"].append(entry)
            result = {
                "domain": "error_handling",
                "method": "log_once",
                "data": {"logged": True, "key": key, "duplicate": False},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LOG_ONCE_ERROR", str(e), 0))

    def get_hierarchy(self, params=None):
        params = params or {}
        try:
            exc = self._exc(params)
            if exc is None:
                cls = Exception
            else:
                cls = type(exc)
            hierarchy = []
            current = cls
            while current is not None:
                hierarchy.append(current.__name__)
                current = current.__bases__[0] if current.__bases__ else None
            result = {
                "domain": "error_handling",
                "method": "get_hierarchy",
                "data": {"hierarchy": hierarchy, "depth": len(hierarchy)},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GET_HIERARCHY_ERROR", str(e), 0))
