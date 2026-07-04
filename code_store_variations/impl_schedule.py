import os
import sys
import json
import re
import time
import threading


class DomSchedule:
    """Task scheduling, cron, intervals, and recurring jobs domain."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "add": self.add,
            "cancel": self.cancel,
            "cron": self.cron,
            "history": self.history,
            "interval": self.interval,
            "next": self.next,
            "once": self.once,
            "pause": self.pause,
            "recurring": self.recurring,
            "resume": self.resume,
            "run": self.run,
            "status": self.status,
        }
        handler = handlers.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def _get_jobs(self):
        if "jobs" not in self.state["config"]:
            self.state["config"]["jobs"] = {}
        return self.state["config"]["jobs"]

    def _get_history(self):
        if "history" not in self.state["config"]:
            self.state["config"]["history"] = []
        return self.state["config"]["history"]

    def add(self, params=None):
        params = params or {}
        try:
            job_id = params.get("job_id", f"job_{int(time.time())}")
            task = params.get("task", "")
            when = params.get("when", None)
            jobs = self._get_jobs()
            jobs[job_id] = {"task": task, "when": when, "status": "pending", "type": "single"}
            result = {"domain": "schedule", "method": "add", "data": {"job_id": job_id, "added": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ADD_ERROR", str(e), 0))

    def cancel(self, params=None):
        params = params or {}
        try:
            job_id = params.get("job_id", "")
            jobs = self._get_jobs()
            if job_id in jobs:
                jobs[job_id]["status"] = "cancelled"
            result = {"domain": "schedule", "method": "cancel", "data": {"job_id": job_id, "cancelled": job_id in jobs}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CANCEL_ERROR", str(e), 0))

    def cron(self, params=None):
        params = params or {}
        try:
            expr = params.get("expr", "* * * * *")
            parts = expr.split()
            valid = len(parts) == 5
            parsed = {}
            if valid:
                fields = ["minute", "hour", "day", "month", "weekday"]
                for i, field in enumerate(fields):
                    parsed[field] = parts[i]
            result = {"domain": "schedule", "method": "cron", "data": {"expr": expr, "valid": valid, "parsed": parsed}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CRON_ERROR", str(e), 0))

    def history(self, params=None):
        params = params or {}
        try:
            job_id = params.get("job_id", None)
            hist = self._get_history()
            if job_id:
                filtered = [h for h in hist if h.get("job_id") == job_id]
            else:
                filtered = hist
            result = {"domain": "schedule", "method": "history", "data": {"history": filtered, "count": len(filtered)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HISTORY_ERROR", str(e), 0))

    def interval(self, params=None):
        params = params or {}
        try:
            job_id = params.get("job_id", f"interval_{int(time.time())}")
            task = params.get("task", "")
            seconds = float(params.get("seconds", 60.0))
            jobs = self._get_jobs()
            jobs[job_id] = {"task": task, "interval": seconds, "status": "active", "type": "interval"}
            result = {"domain": "schedule", "method": "interval", "data": {"job_id": job_id, "interval": seconds, "added": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("INTERVAL_ERROR", str(e), 0))

    def next(self, params=None):
        params = params or {}
        try:
            job_id = params.get("job_id", "")
            jobs = self._get_jobs()
            job = jobs.get(job_id, {})
            if job.get("type") == "interval":
                next_time = time.time() + job.get("interval", 0)
            elif job.get("when"):
                next_time = job["when"]
            else:
                next_time = None
            result = {"domain": "schedule", "method": "next", "data": {"job_id": job_id, "next_run": next_time}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("NEXT_ERROR", str(e), 0))

    def once(self, params=None):
        params = params or {}
        try:
            job_id = params.get("job_id", f"once_{int(time.time())}")
            task = params.get("task", "")
            when = params.get("when", time.time())
            jobs = self._get_jobs()
            jobs[job_id] = {"task": task, "when": when, "status": "pending", "type": "once"}
            result = {"domain": "schedule", "method": "once", "data": {"job_id": job_id, "when": when, "added": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ONCE_ERROR", str(e), 0))

    def pause(self, params=None):
        params = params or {}
        try:
            job_id = params.get("job_id", "")
            jobs = self._get_jobs()
            if job_id in jobs:
                jobs[job_id]["status"] = "paused"
            result = {"domain": "schedule", "method": "pause", "data": {"job_id": job_id, "paused": job_id in jobs}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PAUSE_ERROR", str(e), 0))

    def recurring(self, params=None):
        params = params or {}
        try:
            job_id = params.get("job_id", f"recurring_{int(time.time())}")
            task = params.get("task", "")
            pattern = params.get("pattern", "daily")
            jobs = self._get_jobs()
            jobs[job_id] = {"task": task, "pattern": pattern, "status": "active", "type": "recurring"}
            result = {"domain": "schedule", "method": "recurring", "data": {"job_id": job_id, "pattern": pattern, "added": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RECURRING_ERROR", str(e), 0))

    def resume(self, params=None):
        params = params or {}
        try:
            job_id = params.get("job_id", "")
            jobs = self._get_jobs()
            if job_id in jobs:
                jobs[job_id]["status"] = "active"
            result = {"domain": "schedule", "method": "resume", "data": {"job_id": job_id, "resumed": job_id in jobs}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RESUME_ERROR", str(e), 0))

    def run(self, params=None):
        params = params or {}
        try:
            job_id = params.get("job_id", "")
            jobs = self._get_jobs()
            job = jobs.get(job_id, {})
            if job:
                self._get_history().append({"job_id": job_id, "ran_at": time.time(), "task": job.get("task", "")})
            result = {"domain": "schedule", "method": "run", "data": {"job_id": job_id, "ran": job_id in jobs}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RUN_ERROR", str(e), 0))

    def status(self, params=None):
        params = params or {}
        try:
            job_id = params.get("job_id", "")
            jobs = self._get_jobs()
            if job_id:
                job = jobs.get(job_id, {})
                result = {"domain": "schedule", "method": "status", "data": {"job_id": job_id, "status": job.get("status", "not_found")}}
            else:
                statuses = {jid: j.get("status", "unknown") for jid, j in jobs.items()}
                result = {"domain": "schedule", "method": "status", "data": {"jobs": statuses, "total": len(jobs)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STATUS_ERROR", str(e), 0))
