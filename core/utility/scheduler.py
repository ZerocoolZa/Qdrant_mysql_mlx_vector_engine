# [@GHOST]{[@file<scheduler.py>][@domain<utility>][@role<scheduler>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<scheduler>][@return<tuple3>][@orch<Config.SCHEDULES>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Scheduler — reads Config.SCHEDULES, runs triggers on interval, event-driven or timer-based}
# [@WCL]{[@self_contained<true>][@reads<Config.SCHEDULES>][@runs<Orchestrator>][@modes<timer|event|manual>][@automated<true>]}

import os
import time
import threading

from . import Config
from .orchestrator import Orchestrator


class Scheduler:
    """Scheduler — reads Config.SCHEDULES and runs triggers automatically.

    Two modes:
    1. Timer-based: interval > 0 — runs every N seconds in a background thread
    2. Event-based: interval = 0 — runs when fire_event() is called

    Config.SCHEDULES defines:
    - trigger: which trigger to run (maps to Config.TRIGGERS)
    - interval: seconds between runs (0 = manual/event only)
    - enabled: on/off
    - description: what it does
    - last_run: timestamp of last execution (updated by scheduler)

    Usage:
        from core.utility.scheduler import Scheduler
        sched = Scheduler()
        sched.Run("start")           # starts timer thread
        sched.Run("fire", {"name": "error", "context": {...}})  # event-driven
        sched.Run("stop")            # stops timer
        sched.Run("list")            # shows all schedules
        sched.Run("status")          # shows running state
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "running": False,
            "thread": None,
            "tick_count": 0,
            "event_count": 0,
            "timer_runs": 0,
            "last_tick": 0,
        }
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state["orch"] = Orchestrator()
        self.state["lock"] = threading.Lock()
        self.state["stop_flag"] = threading.Event()

    def Run(self, command, params=None):
        params = params or {}
        if command == "start":
            return self.start(params)
        elif command == "stop":
            return self.stop(params)
        elif command == "fire":
            return self.fire_event(params.get("name", ""), params.get("context", {}))
        elif command == "list":
            return self.list_schedules(params)
        elif command == "status":
            return self.status(params)
        elif command == "tick":
            return self.tick(params)
        elif command == "enable":
            return self.enable_schedule(params.get("name", ""))
        elif command == "disable":
            return self.disable_schedule(params.get("name", ""))
        elif command == "set_interval":
            return self.set_interval(params.get("name", ""), params.get("interval", 0))
        elif command == "read_state":
            return self.read_state()
        return (0, None, ("unknown_command", command, 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self):
        return (1, dict(self.state), None)

    def list_schedules(self, params=None):
        schedules = []
        for name, sched in Config.SCHEDULES.items():
            schedules.append({
                "name": name,
                "trigger": sched["trigger"],
                "interval": sched["interval"],
                "enabled": sched["enabled"],
                "description": sched["description"],
                "last_run": sched["last_run"],
                "mode": "timer" if sched["interval"] > 0 else "event",
            })
        return (1, {"schedules": schedules, "count": len(schedules)}, None)

    def status(self, params=None):
        due = self.get_due()
        return (1, {
            "running": self.state["running"],
            "tick_count": self.state["tick_count"],
            "event_count": self.state["event_count"],
            "timer_runs": self.state["timer_runs"],
            "due_now": [d["name"] for d in due],
            "schedules": len(Config.SCHEDULES),
        }, None)

    def start(self, params=None):
        if self.state["running"]:
            return (1, {"already_running": True}, None)
        self.state["stop_flag"].clear()
        self.state["running"] = True
        self.state["thread"] = threading.Thread(target=self.state["timer_loop"], daemon=True)
        self.state["thread"].start()
        return (1, {"running": True, "message": "scheduler started"}, None)

    def stop(self, params=None):
        self.state["stop_flag"].set()
        self.state["running"] = False
        if self.state["thread"]:
            self.state["thread"] = None
        return (1, {"running": False, "message": "scheduler stopped"}, None)

    def fire_event(self, name, context=None):
        context = context or {}
        if not name:
            return (0, None, ("missing_param", "event name required", 0))
        sched = Config.SCHEDULES.get(name)
        if not sched:
            return (0, None, ("unknown_schedule", "No schedule: " + name, 0))
        if not sched["enabled"]:
            return (0, {"skipped": True, "reason": "disabled"}, None)

        with self.state["lock"]:
            self.state["event_count"] += 1
            code, data, err = self.state["orch"].Run("trigger", {"name": sched["trigger"], "context": context})
            Config.SCHEDULES[name]["last_run"] = time.time()

        if code == 1:
            return (1, {"event": name, "result": data.get("summary", "")}, None)
        return (0, {"event": name, "result": data.get("summary", "")}, err)

    def tick(self, params=None):
        """Check all timer schedules and run any that are due. Returns count of runs."""
        due = self.get_due()
        runs = 0
        for item in due:
            with self.state["lock"]:
                code, data, err = self.state["orch"].Run("trigger", {"name": item["trigger"]})
                Config.SCHEDULES[item["name"]]["last_run"] = time.time()
                runs += 1
        self.state["tick_count"] += 1
        self.state["timer_runs"] += runs
        self.state["last_tick"] = time.time()
        return (1, {"tick": self.state["tick_count"], "runs": runs, "due": len(due)}, None)

    def get_due(self):
        now = time.time()
        due = []
        for name, sched in Config.SCHEDULES.items():
            if not sched["enabled"]:
                continue
            if sched["interval"] <= 0:
                continue
            elapsed = now - sched["last_run"]
            if elapsed >= sched["interval"]:
                due.append({"name": name, "trigger": sched["trigger"], "elapsed": elapsed})
        return due

    def timer_loop(self):
        while not self.state["stop_flag"].is_set():
            self.tick()
            self.state["stop_flag"].wait(10)

    def enable_schedule(self, name):
        if name not in Config.SCHEDULES:
            return (0, None, ("unknown_schedule", name, 0))
        Config.SCHEDULES[name]["enabled"] = True
        return (1, {"name": name, "enabled": True}, None)

    def disable_schedule(self, name):
        if name not in Config.SCHEDULES:
            return (0, None, ("unknown_schedule", name, 0))
        Config.SCHEDULES[name]["enabled"] = False
        return (1, {"name": name, "enabled": False}, None)

    def set_interval(self, name, interval):
        if name not in Config.SCHEDULES:
            return (0, None, ("unknown_schedule", name, 0))
        Config.SCHEDULES[name]["interval"] = int(interval)
        return (1, {"name": name, "interval": int(interval)}, None)
