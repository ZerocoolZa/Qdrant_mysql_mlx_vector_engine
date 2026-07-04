# [@GHOST]{[@file<error_handler.py>][@domain<utility>][@role<error_handler>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<runtime_error_handler>][@return<tuple3>][@orch<SystemCheck>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Runtime error handler — captures, classifies, recovers, retries, circuit breaks, learns from errors}
# [@WCL]{[@self_contained<true>][@source<MySQL_ErrorHandler+DomResilience>][@features<capture|classify|recover|retry|circuit_break|fallback|learn>]

import os
import time
import json
import sqlite3
import threading
import traceback

from . import Config


class ErrorHandler:
    """Runtime error handler — wraps every Tuple3 result through error pipeline.

    Features (extracted from MySQL vb_code_test):
    - ErrorHandler (29 methods): capture, classify, recover, correlate, rate limit
    - DomResilience (11 methods): retry, circuit breaker, fallback, bulkhead, health
    - ErrorTracker: MySQL learned_rules + know_problems + know_solutions

    The key method is consume_engine_result() — pass any Tuple3 from any Run()
    call and it auto-captures failures, looks up fixes, and suggests recovery.

    Usage:
        from core.utility.error_handler import ErrorHandler
        eh = ErrorHandler()

        # Wrap any engine call
        result = some_engine.Run("do_thing", params)
        code, data, err = eh.Run("consume", {"result": result, "source": "some_engine"})

        # Retry with backoff
        code, data, err = eh.Run("retry", {"fn": risky_func, "attempts": 3, "delay": 0.5})

        # Circuit breaker
        eh.Run("circuit_breaker", {"name": "db_conn", "threshold": 5})
        eh.Run("record_outcome", {"name": "db_conn", "success": False})
    """

    SEVERITY_INFO = Config.ERROR_SEVERITY_INFO
    SEVERITY_WARNING = Config.ERROR_SEVERITY_WARNING
    SEVERITY_ERROR = Config.ERROR_SEVERITY_ERROR
    SEVERITY_CRITICAL = Config.ERROR_SEVERITY_CRITICAL

    RECOVERY_IGNORE = Config.ERROR_RECOVERY_IGNORE
    RECOVERY_RETRY = Config.ERROR_RECOVERY_RETRY
    RECOVERY_ROLLBACK = Config.ERROR_RECOVERY_ROLLBACK
    RECOVERY_CANCEL = Config.ERROR_RECOVERY_CANCEL
    RECOVERY_SNAPSHOT = Config.ERROR_RECOVERY_SNAPSHOT
    RECOVERY_MARK_INVALID = Config.ERROR_RECOVERY_MARK_INVALID
    RECOVERY_REQUEST_USER = Config.ERROR_RECOVERY_REQUEST_USER

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "max_log_entries": Config.ERROR_MAX_LOG_ENTRIES,
            },
            "last_error": None,
            "error_count": 0,
            "resolved_count": 0,
        }
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state["conn"] = None
        self.state["breakers"] = {}
        self.state["bulkheads"] = {}
        self.state["lock"] = threading.Lock()
        self.state["db_path"] = Config.ERROR_HANDLER_DB
        self.init_db()

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "consume": self.consume_engine_result,
            "capture": self.capture_error,
            "classify": self.classify_error,
            "get_recovery_policy": self.get_recovery_policy,
            "execute_recovery": self.execute_recovery,
            "register_definition": self.register_error_definition,
            "get_log": self.get_error_log,
            "get_stats": self.get_error_stats,
            "resolve": self.resolve_error,
            "clear_log": self.clear_error_log,
            "retry": self.retry,
            "circuit_breaker": self.circuit_breaker,
            "record_outcome": self.record_outcome,
            "reset_breaker": self.reset_breaker,
            "get_breaker_state": self.get_breaker_state,
            "fallback": self.fallback,
            "bulkhead": self.bulkhead,
            "timeout": self.timeout,
            "health_check": self.health_check,
            "correlate": self.correlate_errors,
            "read_state": self.read_state,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", "Unknown: " + str(command), 0))
        return handler(params)

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def init_db(self):
        conn = sqlite3.connect(self.state["db_path"])
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS error_definitions (
                error_code TEXT PRIMARY KEY,
                severity TEXT DEFAULT 'error',
                category TEXT DEFAULT 'system',
                description TEXT DEFAULT '',
                user_message TEXT DEFAULT '',
                recovery_action TEXT DEFAULT 'cancel',
                recoverable INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 0,
                auto_rollback INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS error_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                error_code TEXT,
                severity TEXT,
                category TEXT,
                source_module TEXT,
                operation TEXT,
                object_id TEXT,
                raw_message TEXT,
                stack_trace TEXT,
                recovery_action TEXT,
                recovery_result TEXT DEFAULT 'pending',
                resolved INTEGER DEFAULT 0,
                correlated_group TEXT
            );
            CREATE TABLE IF NOT EXISTS recovery_policies (
                error_code TEXT,
                action TEXT,
                params TEXT,
                enabled INTEGER DEFAULT 1,
                PRIMARY KEY (error_code, action)
            );
        """)
        conn.commit()
        conn.close()

    def get_connection(self):
        if self.state["conn"] is None:
            self.state["conn"] = sqlite3.connect(self.state["db_path"], check_same_thread=False)
            self.state["conn"].row_factory = sqlite3.Row
        return self.state["conn"]

    def consume_engine_result(self, params):
        result = params.get("result")
        if not result or not isinstance(result, tuple) or len(result) < 3:
            return (0, None, ("MISSING_RESULT", "result tuple3 required", 0))
        ok = result[0]
        if ok:
            return (1, {"status": "success"}, None)
        error_tuple = result[2]
        if not error_tuple:
            return (1, {"status": "success_no_error"}, None)
        error_code = error_tuple[0] if len(error_tuple) > 0 else "UNKNOWN"
        raw_message = error_tuple[1] if len(error_tuple) > 1 else ""
        return self.capture_error({
            "error_code": str(error_code),
            "raw_message": str(raw_message),
            "source_module": params.get("source", "engine"),
            "operation": params.get("operation", ""),
            "object_id": params.get("object_id", ""),
            "exception": params.get("exception"),
        })

    def capture_error(self, params):
        error_code = params.get("error_code", "UNKNOWN")
        raw_message = params.get("raw_message", "")
        source_module = params.get("source_module", "unknown")
        operation = params.get("operation", "")
        object_id = params.get("object_id", "")
        exception = params.get("exception")

        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM error_definitions WHERE error_code = ?", (error_code,))
        row = cur.fetchone()

        if row:
            severity = row["severity"]
            category = row["category"]
            user_message = row["user_message"] or raw_message
            recovery_action = row["recovery_action"]
            recoverable = bool(row["recoverable"])
            auto_rollback = bool(row["auto_rollback"])
        else:
            severity = self.SEVERITY_ERROR
            category = "unknown"
            user_message = raw_message
            recovery_action = self.RECOVERY_CANCEL
            recoverable = False
            auto_rollback = False

        stack = ""
        if exception:
            if isinstance(exception, Exception):
                stack = traceback.format_exc()
            else:
                stack = str(exception)

        timestamp = time.time()
        cur.execute(
            "INSERT INTO error_log (timestamp, error_code, severity, category, source_module, "
            "operation, object_id, raw_message, stack_trace, recovery_action, recovery_result, resolved) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (timestamp, error_code, severity, category, source_module,
             operation, object_id, raw_message, stack, recovery_action, "pending", 0)
        )
        conn.commit()
        log_id = cur.lastrowid

        self.state["last_error"] = {
            "log_id": log_id,
            "error_code": error_code,
            "severity": severity,
            "recoverable": recoverable,
            "recovery_action": recovery_action,
            "user_message": user_message,
            "auto_rollback": auto_rollback,
        }
        self.state["error_count"] += 1

        return (1, {
            "log_id": log_id,
            "error_code": error_code,
            "severity": severity,
            "user_message": user_message,
            "recoverable": recoverable,
            "recovery_action": recovery_action,
            "auto_rollback": auto_rollback,
        }, None)

    def classify_error(self, params):
        error_code = params.get("error_code")
        log_id = params.get("log_id")
        conn = self.get_connection()
        cur = conn.cursor()
        if error_code:
            cur.execute("SELECT * FROM error_definitions WHERE error_code = ?", (error_code,))
        elif log_id:
            cur.execute("SELECT * FROM error_log WHERE id = ?", (log_id,))
        else:
            return (0, None, ("MISSING_PARAMS", "error_code or log_id", 0))
        row = cur.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", "Error not found", 0))
        data = dict(row)
        return (1, {
            "error_code": data.get("error_code", "UNKNOWN"),
            "severity": data.get("severity", self.SEVERITY_ERROR),
            "category": data.get("category", "unknown"),
            "recoverable": bool(data.get("recoverable", 0)),
            "recovery_action": data.get("recovery_action", self.RECOVERY_CANCEL),
        }, None)

    def get_recovery_policy(self, params):
        error_code = params.get("error_code")
        if not error_code:
            return (0, None, ("MISSING_PARAM", "error_code", 0))
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM recovery_policies WHERE error_code = ? AND enabled = 1", (error_code,))
        row = cur.fetchone()
        if row:
            return (1, {"error_code": error_code, "action": row["action"], "params": row["params"]}, None)
        cur.execute("SELECT recovery_action, recoverable, max_retries FROM error_definitions WHERE error_code = ?", (error_code,))
        def_row = cur.fetchone()
        if def_row:
            return (1, {
                "error_code": error_code,
                "action": def_row["recovery_action"],
                "recoverable": bool(def_row["recoverable"]),
                "max_retries": def_row["max_retries"],
            }, None)
        return (1, {"action": self.RECOVERY_CANCEL, "recoverable": False}, None)

    def execute_recovery(self, params):
        log_id = params.get("log_id")
        action = params.get("action")
        if not log_id or not action:
            return (0, None, ("MISSING_PARAMS", "log_id and action", 0))
        result_text = {
            self.RECOVERY_IGNORE: "ignored",
            self.RECOVERY_RETRY: "retry_suggested",
            self.RECOVERY_ROLLBACK: "rollback_requested",
            self.RECOVERY_CANCEL: "cancelled",
            self.RECOVERY_SNAPSHOT: "snapshot_restore_requested",
            self.RECOVERY_MARK_INVALID: "marked_invalid",
            self.RECOVERY_REQUEST_USER: "user_input_required",
        }.get(action, "unknown")
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE error_log SET recovery_result = ?, resolved = ? WHERE id = ?",
                    (result_text, 1 if result_text != "pending" else 0, log_id))
        conn.commit()
        self.state["resolved_count"] += 1
        return (1, {"log_id": log_id, "action": action, "result": result_text}, None)

    def register_error_definition(self, params):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO error_definitions "
            "(error_code, severity, category, description, user_message, recovery_action, recoverable, max_retries, auto_rollback) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                params.get("error_code", "UNKNOWN"),
                params.get("severity", self.SEVERITY_ERROR),
                params.get("category", "system"),
                params.get("description", ""),
                params.get("user_message", ""),
                params.get("recovery_action", self.RECOVERY_CANCEL),
                1 if params.get("recoverable") else 0,
                params.get("max_retries", 0),
                1 if params.get("auto_rollback") else 0,
            )
        )
        conn.commit()
        return (1, {"registered": params.get("error_code")}, None)

    def get_error_log(self, params):
        limit = int(params.get("limit", 50))
        unresolved_only = params.get("unresolved_only", False)
        conn = self.get_connection()
        cur = conn.cursor()
        if unresolved_only:
            cur.execute("SELECT * FROM error_log WHERE resolved = 0 ORDER BY id DESC LIMIT ?", (limit,))
        else:
            cur.execute("SELECT * FROM error_log ORDER BY id DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        return (1, {"entries": rows, "count": len(rows)}, None)

    def get_error_stats(self, params):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM error_log")
        total = cur.fetchone()["total"]
        cur.execute("SELECT COUNT(*) as unresolved FROM error_log WHERE resolved = 0")
        unresolved = cur.fetchone()["unresolved"]
        cur.execute("SELECT error_code, COUNT(*) as cnt FROM error_log GROUP BY error_code ORDER BY cnt DESC LIMIT 10")
        top_errors = [dict(r) for r in cur.fetchall()]
        return (1, {
            "total": total, "unresolved": unresolved,
            "resolved": total - unresolved,
            "top_errors": top_errors,
        }, None)

    def resolve_error(self, params):
        log_id = params.get("log_id")
        if not log_id:
            return (0, None, ("MISSING_PARAM", "log_id", 0))
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE error_log SET resolved = 1, recovery_result = 'resolved' WHERE id = ?", (log_id,))
        conn.commit()
        self.state["resolved_count"] += 1
        return (1, {"log_id": log_id, "resolved": True}, None)

    def clear_error_log(self, params):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM error_log")
        conn.commit()
        self.state["error_count"] = 0
        self.state["resolved_count"] = 0
        return (1, {"cleared": True}, None)

    def correlate_errors(self, params):
        window = float(params.get("window_seconds", 60))
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM error_log ORDER BY timestamp DESC LIMIT 100")
        rows = [dict(r) for r in cur.fetchall()]
        groups = []
        if rows:
            current_group = [rows[0]]
            for i in range(1, len(rows)):
                if rows[i - 1]["timestamp"] - rows[i]["timestamp"] <= window:
                    current_group.append(rows[i])
                else:
                    if len(current_group) > 1:
                        groups.append(current_group)
                    current_group = [rows[i]]
            if len(current_group) > 1:
                groups.append(current_group)
        return (1, {"groups": groups, "group_count": len(groups)}, None)

    def retry(self, params):
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
                return (1, {"value": value, "attempts": i + 1, "history": history}, None)
            except Exception as e:
                last_err = str(e)
                history.append({"attempt": i + 1, "ok": False, "elapsed": time.time() - start, "error": last_err})
                if i < attempts - 1 and delay > 0:
                    time.sleep(delay * (backoff ** i))
        return (0, {"attempts": attempts, "history": history}, ("RETRY_EXHAUSTED", last_err or "exhausted", attempts))

    def circuit_breaker(self, params):
        name = params.get("name", "default")
        threshold = int(params.get("threshold", 5))
        reset_timeout = float(params.get("reset_timeout", 30.0))
        with self.state["lock"]:
            if name not in self.state["breakers"]:
                self.state["breakers"][name] = {
                    "state": "closed", "failures": 0, "threshold": threshold,
                    "reset_timeout": reset_timeout, "opened_at": None, "successes": 0,
                }
            breaker = self.state["breakers"][name]
            breaker["threshold"] = threshold
            breaker["reset_timeout"] = reset_timeout
        return (1, {"name": name, "state": breaker["state"], "threshold": threshold, "reset_timeout": reset_timeout}, None)

    def record_outcome(self, params):
        name = params.get("name", "default")
        success = bool(params.get("success", False))
        with self.state["lock"]:
            if name not in self.state["breakers"]:
                self.state["breakers"][name] = {"state": "closed", "failures": 0, "threshold": 5, "reset_timeout": 30.0, "opened_at": None, "successes": 0}
            breaker = self.state["breakers"][name]
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
        return (1, {"name": name, "success": success, "state": state, "failures": failures, "successes": successes}, None)

    def reset_breaker(self, params):
        name = params.get("name", "default")
        with self.state["lock"]:
            if name in self.state["breakers"]:
                self.state["breakers"][name]["state"] = "closed"
                self.state["breakers"][name]["failures"] = 0
                self.state["breakers"][name]["opened_at"] = None
        return (1, {"name": name, "reset": True}, None)

    def get_breaker_state(self, params):
        name = params.get("name", "default")
        with self.state["lock"]:
            breaker = self.state["breakers"].get(name)
            if not breaker:
                return (0, None, ("NOT_FOUND", "No breaker: " + name, 0))
            if breaker["state"] == "open" and breaker["opened_at"]:
                elapsed = time.time() - breaker["opened_at"]
                if elapsed >= breaker["reset_timeout"]:
                    breaker["state"] = "half_open"
        return (1, dict(breaker) if breaker else {}, None)

    def fallback(self, params):
        primary = params.get("primary")
        fallback_fn = params.get("fallback")
        args = params.get("args", [])
        kwargs = params.get("kwargs", {})
        used = "primary"
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
                return (0, None, ("FALLBACK_FAILED", str(e), 0))
        return (1, {"value": value, "used": used, "primary_error": error}, None)

    def bulkhead(self, params):
        name = params.get("name", "default")
        max_concurrent = int(params.get("max_concurrent", 5))
        with self.state["lock"]:
            if name not in self.state["bulkheads"]:
                self.state["bulkheads"][name] = {"active": 0, "max_concurrent": max_concurrent}
            self.state["bulkheads"][name]["max_concurrent"] = max_concurrent
            bd = self.state["bulkheads"][name]
            saturated = bd["active"] >= bd["max_concurrent"]
            if not saturated:
                bd["active"] += 1
        return (1, {"name": name, "active": bd["active"], "max": bd["max_concurrent"], "acquired": not saturated}, None)

    def timeout(self, params):
        seconds = float(params.get("seconds", 30))
        fn = params.get("fn")
        args = params.get("args", [])
        kwargs = params.get("kwargs", {})
        result = [None]
        error = [None]

        def worker():
            try:
                if callable(fn):
                    result[0] = fn(*args, **kwargs)
            except Exception as e:
                error[0] = str(e)

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        t.join(seconds)
        if t.is_alive():
            return (0, None, ("TIMEOUT", "exceeded {}s".format(seconds), 0))
        if error[0]:
            return (0, None, ("EXEC_ERROR", error[0], 0))
        return (1, {"value": result[0]}, None)

    def health_check(self, params):
        checks = {}
        overall = True
        with self.state["lock"]:
            for name, breaker in self.state["breakers"].items():
                healthy = breaker["state"] != "open"
                checks[name] = {"state": breaker["state"], "healthy": healthy}
                if not healthy:
                    overall = False
            for name, bd in self.state["bulkheads"].items():
                saturated = bd["active"] >= bd["max_concurrent"]
                checks["bulkhead:" + name] = {"active": bd["active"], "max": bd["max_concurrent"], "saturated": saturated}
        checks["error_count"] = self.state["error_count"]
        checks["unresolved"] = self.state["error_count"] - self.state["resolved_count"]
        return (1, {"healthy": overall, "checks": checks}, None)
