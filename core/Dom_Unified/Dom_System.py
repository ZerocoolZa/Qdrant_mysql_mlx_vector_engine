# [@GHOST]{[@file<Dom_System.py>][@domain<Dom_Unified>][@role<system_manager>][@auth<cascade>][@date<2026-06-28>][@ver<2.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<system_manager>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{DomSystem — single resource-first authority for service lifecycle (start/stop/suspend/resume), reference counting, lazy load/unload, idle GC, health monitoring + recovery, dependency management, and runtime state queries (IsLoaded/IsRunning/IsBusy/IsIdle) for MySQL, Neo4j, Qdrant, SQLite. RAM-budget aware. Replaces the standalone root service_manager.py.}
# [@CLASS]{DomSystem}
# [@METHOD]{Run,read_state,set_config,acquire,release,force_release,gc,purge,is_loaded,is_running,is_busy,is_idle,suspend,resume,deps,recover,start,stop,restart,status,health,check_all,start_all,stop_all}

"""
DomSystem — resource-first service authority for the Dom_Unified stack.

WHAT IT MANAGES (one class, one domain, one authority):
  - MySQL   (brew services or direct mysqld)
  - Neo4j   (brew services or neo4j binary)
  - Qdrant  (direct binary + pidfile)
  - SQLite  (always available — file-based, no process)

WHAT IT IS (resource-first, not process-first):
  The single authority responsible for:
    - Service lifecycle        : start, stop, suspend, resume
    - Resource allocation      : CPU, GPU, RAM, I/O footprint tracking
    - Reference counting        : acquire/release with refcount per service
    - Automatic load/unload     : lazy load on first acquire, unload on idle
    - Health monitoring         : periodic health checks + auto-recovery
    - Dependency management     : declared deps auto-started before the service
    - Runtime state queries     : IsLoaded, IsRunning, IsBusy, IsIdle

GENERAL FLOW:
  1. A component calls Run("acquire", {"service": "qdrant"}).
  2. DomSystem checks whether qdrant is already loaded.
  3. If loaded  -> bump refcount, return existing handle.
  4. If not     -> resolve deps, check RAM budget, create, init, register, refcount=1.
  5. While in use -> kept alive (refcount > 0).
  6. Run("release", {"service": "qdrant"}) -> decrement refcount.
  7. Run("gc") -> unload every service with refs == 0 and idle > IDLE_TIMEOUT.

USAGE:
  from Dom_Unified.Dom_System import DomSystem

  sys = DomSystem()

  # Lazy-load + refcount
  ok, handle, err = sys.Run("acquire", {"service": "qdrant"})
  # ... use qdrant ...
  ok, data, err = sys.Run("release", {"service": "qdrant"})

  # Runtime state queries
  ok, data, err = sys.Run("is_loaded",   {"service": "qdrant"})
  ok, data, err = sys.Run("is_running",  {"service": "qdrant"})
  ok, data, err = sys.Run("is_busy",     {"service": "qdrant"})
  ok, data, err = sys.Run("is_idle",     {"service": "qdrant"})

  # Idle GC (call periodically from a timer or DomExecutionEngine)
  ok, report, err = sys.Run("gc")

  # Health + auto-recovery
  ok, data, err = sys.Run("health",  {"service": "neo4j"})
  ok, data, err = sys.Run("recover", {"service": "neo4j"})

  # Direct lifecycle (bypass refcount — use sparingly)
  ok, data, err = sys.Run("start", {"service": "mysql"})
  ok, data, err = sys.Run("stop",  {"service": "mysql"})

  # Suspend/resume (stop but keep registry entry + refcount)
  ok, data, err = sys.Run("suspend", {"service": "qdrant"})
  ok, data, err = sys.Run("resume",  {"service": "qdrant"})

  # Full status report
  ok, report, err = sys.Run("status", {"service": "all"})
"""

import os
import signal
import socket
import shutil
import subprocess
import time
import datetime

from .Config import (
    DOM_SERVICES,
    DOM_SERVICE_NAMES,
    DOM_IDLE_TIMEOUT_SECONDS,
    DOM_MAX_RESTARTS,
    DOM_HEALTH_FAILS_BEFORE_RESTART,
    DOM_STOP_TIMEOUT_SECONDS,
    DOM_START_WAIT_SECONDS,
    DOM_RAM_BUDGET_MB,
    DOM_RETIRED_PLISTS_DIR,
    DOM_LAUNCH_MODE_BREW,
    DOM_LAUNCH_MODE_DIRECT,
    DOM_LAUNCH_MODE_ALWAYS,
    DOM_LAUNCH_MODE_LAUNCHD,
    DOM_SERVICE_MODES,
    DOM_SERVICE_MODE_TRANSIENT,
    DOM_SERVICE_MODE_BATCH,
    DOM_SERVICE_MODE_CONSTANT,
    DOM_SERVICE_MODE_PINNED,
)

try:
    from core.utility.package_manager import PackageManager
    HAS_PACKAGE_MANAGER = True
except Exception:
    HAS_PACKAGE_MANAGER = False


class DomSystem:
    """
    Resource-first service authority for MySQL, Neo4j, Qdrant, SQLite.
    VBStyle compliant: Run() dispatch, Tuple3 returns, self.state dict.
    No print, no decorators, no self._, no hardcoded values (all via Config).
    """

    def __init__(self, mem=None, db=None, param=None):
        cfg = param or {}
        self.state = {
            "config": {
                "idle_timeout_seconds": cfg.get("idle_timeout_seconds", DOM_IDLE_TIMEOUT_SECONDS),
                "max_restarts": cfg.get("max_restarts", DOM_MAX_RESTARTS),
                "health_fails_before_restart": cfg.get("health_fails_before_restart", DOM_HEALTH_FAILS_BEFORE_RESTART),
                "stop_timeout_seconds": cfg.get("stop_timeout_seconds", DOM_STOP_TIMEOUT_SECONDS),
                "start_wait_seconds": cfg.get("start_wait_seconds", DOM_START_WAIT_SECONDS),
                "ram_budget_mb": cfg.get("ram_budget_mb", DOM_RAM_BUDGET_MB),
                "auto_start": cfg.get("auto_start", False),
            },
            "services": {},
            "resources": {
                "ram_budget_mb": cfg.get("ram_budget_mb", DOM_RAM_BUDGET_MB),
                "ram_used_mb": 0,
                "cpu_percent_used": 0,
                "gpu_in_use": False,
                "io_services": 0,
            },
            "stats": {
                "acquires": 0,
                "releases": 0,
                "starts": 0,
                "stops": 0,
                "restarts": 0,
                "unloads": 0,
                "health_checks": 0,
                "recoveries": 0,
                "errors": 0,
            },
        }
        self._seed_registry()

    # ════════════════════════════════════════════
    # DISPATCH
    # ════════════════════════════════════════════

    def Run(self, command, params=None):
        dispatch = {
            "acquire": self._cmd_acquire,
            "release": self._cmd_release,
            "force_release": self._cmd_force_release,
            "gc": self._cmd_gc,
            "purge": self._cmd_purge,
            "is_loaded": self._cmd_is_loaded,
            "is_running": self._cmd_is_running,
            "is_busy": self._cmd_is_busy,
            "is_idle": self._cmd_is_idle,
            "suspend": self._cmd_suspend,
            "resume": self._cmd_resume,
            "deps": self._cmd_deps,
            "recover": self._cmd_recover,
            "retire_plist": self._cmd_retire_plist,
            "pin": self._cmd_pin,
            "unpin": self._cmd_unpin,
            "set_mode": self._cmd_set_mode,
            "package": self._cmd_package,
            "start": self._cmd_start,
            "stop": self._cmd_stop,
            "restart": self._cmd_restart,
            "status": self._cmd_status,
            "health": self._cmd_health,
            "check_all": self._cmd_check_all,
            "start_all": self._cmd_start_all,
            "stop_all": self._cmd_stop_all,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "Unknown command: %s" % command, 0))
        return handler(params or {})

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        if not params:
            return (0, None, ("ERR_PARAMS", "config values required", 0))
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
            if key == "ram_budget_mb":
                self.state["resources"]["ram_budget_mb"] = val
        return (1, dict(self.state["config"]), None)

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    # ════════════════════════════════════════════
    # REGISTRY SEEDING
    # ════════════════════════════════════════════

    def _seed_registry(self):
        now = datetime.datetime.now().isoformat()
        services = {}
        for name, svc in DOM_SERVICES.items():
            services[name] = {
                "name": svc["name"],
                "loaded": svc["launch_mode"] == DOM_LAUNCH_MODE_ALWAYS,
                "running": svc["launch_mode"] == DOM_LAUNCH_MODE_ALWAYS,
                "pid": None,
                "refs": 0,
                "last_used": now,
                "busy_since": None,
                "health_status": "unknown",
                "health_fails": 0,
                "restart_count": 0,
                "dependents": [],
                "launch_mode": svc["launch_mode"],
                "port": svc["port"],
                "host": svc["host"],
                "est_ram_mb": svc["est_ram_mb"],
                "est_cpu_percent": svc["est_cpu_percent"],
                "uses_gpu": svc["uses_gpu"],
                "uses_io": svc["uses_io"],
                "deps": list(svc["deps"]),
                "checked_at": now,
                "pinned_until": None,
                "pin_reason": None,
                "acquire_history": [],
                "effective_timeout": self.state["config"]["idle_timeout_seconds"],
                "mode": DOM_SERVICE_MODE_TRANSIENT,
                "mode_reason": None,
            }
        self.state["services"] = services

    def _svc_cfg(self, name):
        return DOM_SERVICES.get(name)

    def _svc_state(self, name):
        return self.state["services"].get(name)

    # ════════════════════════════════════════════
    # ACQUIRE / RELEASE / GC  (resource-first core)
    # ════════════════════════════════════════════

    def _cmd_acquire(self, params):
        name = self._p(params, "service")
        if not name:
            return (0, None, ("ERR_PARAMS", "service required", 0))
        if name not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % name, 0))
        svc = self._svc_cfg(name)
        st = self._svc_state(name)
        if svc["launch_mode"] == DOM_LAUNCH_MODE_ALWAYS:
            st["refs"] += 1
            st["last_used"] = datetime.datetime.now().isoformat()
            self._record_acquire(name)
            self.state["stats"]["acquires"] += 1
            return (1, {"service": name, "handle": name, "refs": st["refs"], "already_loaded": True}, None)
        ok, _, err = self._ensure_deps_loaded(name)
        if not ok:
            return (0, None, err)
        if st["loaded"] and st["running"]:
            st["refs"] += 1
            st["last_used"] = datetime.datetime.now().isoformat()
            self._record_acquire(name)
            self.state["stats"]["acquires"] += 1
            return (1, {"service": name, "handle": name, "refs": st["refs"], "already_loaded": True}, None)
        projected = self.state["resources"]["ram_used_mb"] + svc["est_ram_mb"]
        if projected > self.state["resources"]["ram_budget_mb"]:
            return (0, None, ("ERR_RAM_BUDGET",
                "RAM budget exceeded: %d + %d > %d MB" % (
                    self.state["resources"]["ram_used_mb"], svc["est_ram_mb"],
                    self.state["resources"]["ram_budget_mb"]), 0))
        ok, data, err = self._do_start(name)
        if not ok:
            return (0, None, err)
        st["loaded"] = True
        st["running"] = True
        st["refs"] = 1
        st["last_used"] = datetime.datetime.now().isoformat()
        st["health_status"] = "healthy"
        st["health_fails"] = 0
        self.state["resources"]["ram_used_mb"] += svc["est_ram_mb"]
        self.state["resources"]["cpu_percent_used"] += svc["est_cpu_percent"]
        if svc["uses_gpu"]:
            self.state["resources"]["gpu_in_use"] = True
        if svc["uses_io"]:
            self.state["resources"]["io_services"] += 1
        self._register_dependent(name, params)
        self._record_acquire(name)
        self.state["stats"]["acquires"] += 1
        self.state["stats"]["starts"] += 1
        return (1, {"service": name, "handle": name, "refs": 1, "started": True, "pid": data.get("pid")}, None)

    def _cmd_release(self, params):
        name = self._p(params, "service")
        if not name:
            return (0, None, ("ERR_PARAMS", "service required", 0))
        if name not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % name, 0))
        st = self._svc_state(name)
        if st["refs"] <= 0:
            return (1, {"service": name, "refs": 0, "already_zero": True}, None)
        st["refs"] -= 1
        st["last_used"] = datetime.datetime.now().isoformat()
        self.state["stats"]["releases"] += 1
        if st["refs"] == 0 and not st["deps"]:
            idle = self.state["config"]["idle_timeout_seconds"]
            if idle <= 0:
                ok, _, err = self._do_unload(name)
                if not ok:
                    return (0, None, err)
                return (1, {"service": name, "refs": 0, "unloaded": True}, None)
        return (1, {"service": name, "refs": st["refs"], "unloaded": False}, None)

    def _cmd_force_release(self, params):
        name = self._p(params, "service")
        if not name:
            return (0, None, ("ERR_PARAMS", "service required", 0))
        if name not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % name, 0))
        st = self._svc_state(name)
        st["refs"] = 0
        st["last_used"] = datetime.datetime.now().isoformat()
        self.state["stats"]["releases"] += 1
        return (1, {"service": name, "refs": 0, "force_released": True}, None)

    def _cmd_gc(self, params):
        now = time.time()
        now_dt = datetime.datetime.now()
        unloaded = []
        kept = []
        for name in DOM_SERVICE_NAMES:
            st = self._svc_state(name)
            svc = self._svc_cfg(name)
            if svc["launch_mode"] == DOM_LAUNCH_MODE_ALWAYS:
                continue
            if not st["loaded"]:
                continue
            if st["refs"] > 0:
                kept.append({"service": name, "reason": "in_use", "refs": st["refs"]})
                continue
            if st.get("pinned_until"):
                pin_epoch = self._iso_to_epoch(st["pinned_until"])
                if now < pin_epoch:
                    kept.append({"service": name, "reason": "pinned", "pinned_until": st["pinned_until"], "pin_reason": st.get("pin_reason")})
                    continue
                else:
                    st["pinned_until"] = None
                    st["pin_reason"] = None
            effective_timeout = self._adaptive_timeout(name)
            st["effective_timeout"] = effective_timeout
            last = self._iso_to_epoch(st["last_used"])
            idle_secs = now - last
            if idle_secs >= effective_timeout:
                ok, _, err = self._do_unload(name)
                if ok:
                    unloaded.append({"service": name, "idle_secs": int(idle_secs), "timeout_used": effective_timeout})
                else:
                    kept.append({"service": name, "reason": "unload_failed", "error": err})
            else:
                kept.append({"service": name, "reason": "not_idle_yet", "idle_secs": int(idle_secs), "timeout_used": effective_timeout})
        self.state["stats"]["unloads"] += len(unloaded)
        return (1, {
            "unloaded": unloaded,
            "kept": kept,
            "ram_used_mb": self.state["resources"]["ram_used_mb"],
            "checked_at": datetime.datetime.now().isoformat(),
        }, None)

    def _cmd_purge(self, params):
        import subprocess as _sp
        import gc as _gc
        import ctypes
        import mmap
        pressure_mb = self._p(params, "pressure_mb", 512)
        passes = self._p(params, "passes", 3)
        use_madvise = self._p(params, "madvise", True)
        report = {"before": {}, "after": {}, "freed_mb": 0, "passes": [], "pressured": []}

        def _scan_procs():
            out = _sp.run(["/bin/ps", "-axo", "pid,rss,command"], capture_output=True, text=True, timeout=5)
            procs = []
            for line in out.stdout.strip().split("\n")[1:]:
                parts = line.strip().split(None, 2)
                if len(parts) < 3:
                    continue
                pid_s, rss_s, cmd = parts
                try:
                    pid = int(pid_s)
                    rss_kb = int(rss_s)
                except ValueError:
                    continue
                if rss_kb < 10240:
                    continue
                procs.append({"pid": pid, "rss_mb": rss_kb // 1024, "cmd": cmd[:80]})
            procs.sort(key=lambda p: p["rss_mb"], reverse=True)
            return procs

        try:
            procs = _scan_procs()
            report["before"]["top5"] = procs[:5]
            report["before"]["total_procs"] = len(procs)
            report["before"]["total_mb"] = sum(p["rss_mb"] for p in procs)
        except Exception as exc:
            report["before"]["error"] = str(exc)

        MADV_DONTNEED = 4
        PAGE = 4096
        cur_pressure = pressure_mb
        for pidx in range(passes):
            pass_info = {"pass": pidx + 1, "pressure_mb": cur_pressure, "method": "mmap_touch_madvise" if use_madvise else "alloc_free"}
            try:
                if use_madvise:
                    buf = mmap.mmap(-1, cur_pressure * 1024 * 1024, mmap.MAP_PRIVATE | mmap.MAP_ANON, mmap.PROT_READ | mmap.PROT_WRITE)
                    mv = memoryview(buf)
                    for off in range(0, len(mv), PAGE):
                        mv[off] = 1
                    addr = ctypes.addressof(ctypes.c_char.from_buffer(buf))
                    libc = ctypes.CDLL("libc.dylib", use_errno=True)
                    libc.madvise(ctypes.c_void_p(addr), ctypes.c_size_t(cur_pressure * 1024 * 1024), ctypes.c_int(MADV_DONTNEED))
                    buf.close()
                else:
                    data = [bytearray(1024 * 1024) for _ in range(cur_pressure)]
                    del data
                _gc.collect()
                pass_info["ok"] = True
            except MemoryError:
                cur_pressure = cur_pressure // 2
                if cur_pressure < 16:
                    pass_info["ok"] = False
                    pass_info["error"] = "pressure too small after reduction"
                    report["passes"].append(pass_info)
                    break
                pass_info["ok"] = False
                pass_info["error"] = "MemoryError, reduced to %d" % cur_pressure
                pass_info["pressure_mb"] = cur_pressure
            except Exception as exc:
                pass_info["ok"] = False
                pass_info["error"] = str(exc)
            try:
                procs_mid = _scan_procs()
                pass_info["total_mb_after"] = sum(p["rss_mb"] for p in procs_mid)
                pass_info["freed_mb"] = report["before"].get("total_mb", 0) - pass_info["total_mb_after"]
            except Exception:
                pass
            report["passes"].append(pass_info)
            cur_pressure = int(cur_pressure * 1.5)

        try:
            libc = ctypes.CDLL("libc.dylib", use_errno=True)
            if hasattr(libc, "malloc_trim"):
                libc.malloc_trim(0)
                report["pressured"].append({"method": "malloc_trim"})
        except Exception:
            pass

        try:
            procs2 = _scan_procs()
            report["after"]["top5"] = procs2[:5]
            report["after"]["total_procs"] = len(procs2)
            report["after"]["total_mb"] = sum(p["rss_mb"] for p in procs2)
            report["freed_mb"] = report["before"].get("total_mb", 0) - report["after"].get("total_mb", 0)
        except Exception as exc:
            report["after"]["error"] = str(exc)
        return (1, report, None)

    def _adaptive_timeout(self, name):
        st = self._svc_state(name)
        base = self.state["config"]["idle_timeout_seconds"]
        mode = st.get("mode", DOM_SERVICE_MODE_TRANSIENT)
        mode_cfg = DOM_SERVICE_MODES.get(mode, DOM_SERVICE_MODES[DOM_SERVICE_MODE_TRANSIENT])
        multiplier = mode_cfg["timeout_multiplier"]
        if multiplier == 0:
            return 999999
        mode_timeout = base * multiplier
        history = st.get("acquire_history", [])
        if not history:
            return mode_timeout
        now = time.time()
        recent = [t for t in history if (now - t) < 1800]
        adaptive_timeout = base
        if len(recent) >= 10:
            adaptive_timeout = base * 12
        elif len(recent) >= 5:
            adaptive_timeout = base * 4
        elif len(recent) >= 3:
            adaptive_timeout = base * 2
        return max(mode_timeout, adaptive_timeout)

    def _record_acquire(self, name):
        st = self._svc_state(name)
        history = st.get("acquire_history", [])
        history.append(time.time())
        if len(history) > 50:
            history = history[-50:]
        st["acquire_history"] = history

    # ════════════════════════════════════════════
    # RUNTIME STATE QUERIES
    # ════════════════════════════════════════════

    def _cmd_is_loaded(self, params):
        name = self._p(params, "service")
        if not name:
            return (0, None, ("ERR_PARAMS", "service required", 0))
        if name not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % name, 0))
        st = self._svc_state(name)
        return (1, {"service": name, "loaded": st["loaded"], "refs": st["refs"]}, None)

    def _cmd_is_running(self, params):
        name = self._p(params, "service")
        if not name:
            return (0, None, ("ERR_PARAMS", "service required", 0))
        if name not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % name, 0))
        svc = self._svc_cfg(name)
        if svc["launch_mode"] == DOM_LAUNCH_MODE_ALWAYS:
            return (1, {"service": name, "running": True, "always_available": True}, None)
        running = self._is_process_running(name)
        st = self._svc_state(name)
        st["running"] = running
        st["checked_at"] = datetime.datetime.now().isoformat()
        return (1, {"service": name, "running": running, "pid": st["pid"]}, None)

    def _cmd_is_busy(self, params):
        name = self._p(params, "service")
        if not name:
            return (0, None, ("ERR_PARAMS", "service required", 0))
        if name not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % name, 0))
        st = self._svc_state(name)
        busy = st["refs"] > 0 and st["busy_since"] is not None
        return (1, {"service": name, "busy": busy, "refs": st["refs"], "busy_since": st["busy_since"]}, None)

    def _cmd_is_idle(self, params):
        name = self._p(params, "service")
        if not name:
            return (0, None, ("ERR_PARAMS", "service required", 0))
        if name not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % name, 0))
        st = self._svc_state(name)
        idle = st["refs"] == 0
        idle_secs = int(time.time() - self._iso_to_epoch(st["last_used"])) if idle else 0
        return (1, {"service": name, "idle": idle, "idle_secs": idle_secs, "refs": st["refs"]}, None)

    # ════════════════════════════════════════════
    # SUSPEND / RESUME
    # ════════════════════════════════════════════

    def _cmd_suspend(self, params):
        name = self._p(params, "service")
        if not name:
            return (0, None, ("ERR_PARAMS", "service required", 0))
        if name not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % name, 0))
        svc = self._svc_cfg(name)
        if svc["launch_mode"] == DOM_LAUNCH_MODE_ALWAYS:
            return (1, {"service": name, "suspended": False, "note": "always-available services cannot suspend"}, None)
        st = self._svc_state(name)
        if not st["loaded"]:
            return (1, {"service": name, "suspended": False, "note": "not loaded"}, None)
        ok, _, err = self._do_stop(name)
        if not ok:
            return (0, None, err)
        st["running"] = False
        st["health_status"] = "suspended"
        self.state["resources"]["ram_used_mb"] = max(0, self.state["resources"]["ram_used_mb"] - svc["est_ram_mb"])
        self.state["resources"]["cpu_percent_used"] = max(0, self.state["resources"]["cpu_percent_used"] - svc["est_cpu_percent"])
        if svc["uses_gpu"]:
            self.state["resources"]["gpu_in_use"] = False
        if svc["uses_io"]:
            self.state["resources"]["io_services"] = max(0, self.state["resources"]["io_services"] - 1)
        return (1, {"service": name, "suspended": True, "refs_preserved": st["refs"]}, None)

    def _cmd_resume(self, params):
        name = self._p(params, "service")
        if not name:
            return (0, None, ("ERR_PARAMS", "service required", 0))
        if name not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % name, 0))
        svc = self._svc_cfg(name)
        if svc["launch_mode"] == DOM_LAUNCH_MODE_ALWAYS:
            return (1, {"service": name, "resumed": True, "note": "always-available"}, None)
        st = self._svc_state(name)
        if not st["loaded"]:
            return (0, None, ("ERR_NOT_LOADED", "service not loaded — use acquire", 0))
        if st["running"]:
            return (1, {"service": name, "resumed": True, "already_running": True}, None)
        ok, data, err = self._do_start(name)
        if not ok:
            return (0, None, err)
        st["running"] = True
        st["health_status"] = "healthy"
        self.state["resources"]["ram_used_mb"] += svc["est_ram_mb"]
        self.state["resources"]["cpu_percent_used"] += svc["est_cpu_percent"]
        if svc["uses_gpu"]:
            self.state["resources"]["gpu_in_use"] = True
        if svc["uses_io"]:
            self.state["resources"]["io_services"] += 1
        return (1, {"service": name, "resumed": True, "pid": data.get("pid")}, None)

    # ════════════════════════════════════════════
    # DEPENDENCY MANAGEMENT
    # ════════════════════════════════════════════

    def _cmd_deps(self, params):
        name = self._p(params, "service")
        if not name:
            return (0, None, ("ERR_PARAMS", "service required", 0))
        if name not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % name, 0))
        svc = self._svc_cfg(name)
        return (1, {"service": name, "deps": list(svc["deps"])}, None)

    def _ensure_deps_loaded(self, name):
        svc = self._svc_cfg(name)
        for dep in svc["deps"]:
            dep_st = self._svc_state(dep)
            if dep_st["loaded"] and dep_st["running"]:
                continue
            ok, _, err = self._cmd_acquire({"service": dep})
            if not ok:
                return (0, None, err)
        return (1, None, None)

    def _register_dependent(self, name, params):
        requester = self._p(params, "requester")
        if not requester:
            return
        for dep in DOM_SERVICE_NAMES:
            dep_svc = self._svc_cfg(dep)
            if name in dep_svc["deps"]:
                dep_st = self._svc_state(dep)
                if requester not in dep_st["dependents"]:
                    dep_st["dependents"].append(requester)

    # ════════════════════════════════════════════
    # HEALTH MONITORING + RECOVERY
    # ════════════════════════════════════════════

    def _cmd_recover(self, params):
        name = self._p(params, "service")
        if not name:
            return (0, None, ("ERR_PARAMS", "service required", 0))
        if name not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % name, 0))
        svc = self._svc_cfg(name)
        if svc["launch_mode"] == DOM_LAUNCH_MODE_ALWAYS:
            return (1, {"service": name, "recovered": True, "note": "always-available"}, None)
        st = self._svc_state(name)
        if st["restart_count"] >= self.state["config"]["max_restarts"]:
            return (0, None, ("ERR_MAX_RESTARTS",
                "max restarts (%d) reached for %s" % (st["restart_count"], name), 0))
        ok, _, err = self._do_stop(name)
        if not ok:
            self.state["stats"]["errors"] += 1
            return (0, None, err)
        time.sleep(1)
        ok, data, err = self._do_start(name)
        if not ok:
            self.state["stats"]["errors"] += 1
            return (0, None, err)
        st["restart_count"] += 1
        st["health_status"] = "recovered"
        st["health_fails"] = 0
        self.state["stats"]["recoveries"] += 1
        self.state["stats"]["restarts"] += 1
        return (1, {"service": name, "recovered": True, "restart_count": st["restart_count"], "pid": data.get("pid")}, None)

    def _cmd_retire_plist(self, params):
        plist_path = self._p(params, "plist")
        name = self._p(params, "service")
        if not plist_path and name:
            if name in DOM_SERVICES:
                plist_path = DOM_SERVICES[name].get("plist", "")
        if not plist_path:
            return (0, None, ("ERR_PARAMS", "plist path or service required", 0))
        plist_path = os.path.expanduser(plist_path)
        if not os.path.exists(plist_path):
            return (1, {"plist": plist_path, "retired": False, "note": "already gone"}, None)
        try:
            subprocess.run(
                ["launchctl", "unload", plist_path],
                capture_output=True, timeout=15,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass
        if not os.path.exists(DOM_RETIRED_PLISTS_DIR):
            try:
                os.makedirs(DOM_RETIRED_PLISTS_DIR, exist_ok=True)
            except OSError as e:
                return (0, None, ("ERR_MKDIR", str(e), 0))
        dest = os.path.join(DOM_RETIRED_PLISTS_DIR, os.path.basename(plist_path))
        try:
            shutil.move(plist_path, dest)
        except OSError as e:
            return (0, None, ("ERR_MOVE", str(e), 0))
        self.state["stats"]["plists_retired"] = self.state["stats"].get("plists_retired", 0) + 1
        return (1, {"plist": plist_path, "retired_to": dest, "service": name}, None)

    def _cmd_pin(self, params):
        name = self._p(params, "service")
        if not name:
            return (0, None, ("ERR_PARAMS", "service required", 0))
        if name not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % name, 0))
        duration = self._p(params, "duration_minutes", 30)
        reason = self._p(params, "reason", "predicted_heavy_usage")
        st = self._svc_state(name)
        until = datetime.datetime.now() + datetime.timedelta(minutes=duration)
        st["pinned_until"] = until.isoformat()
        st["pin_reason"] = reason
        return (1, {
            "service": name,
            "pinned": True,
            "pinned_until": st["pinned_until"],
            "duration_minutes": duration,
            "reason": reason,
        }, None)

    def _cmd_unpin(self, params):
        name = self._p(params, "service")
        if not name:
            return (0, None, ("ERR_PARAMS", "service required", 0))
        if name not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % name, 0))
        st = self._svc_state(name)
        was_pinned = st.get("pinned_until") is not None
        st["pinned_until"] = None
        st["pin_reason"] = None
        return (1, {
            "service": name,
            "unpinned": True,
            "was_pinned": was_pinned,
        }, None)

    def _cmd_set_mode(self, params):
        name = self._p(params, "service")
        if not name:
            return (0, None, ("ERR_PARAMS", "service required", 0))
        if name not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % name, 0))
        mode = self._p(params, "mode", DOM_SERVICE_MODE_TRANSIENT)
        if mode not in DOM_SERVICE_MODES:
            return (0, None, ("ERR_UNKNOWN_MODE", "Unknown mode: %s. Valid: %s" % (mode, list(DOM_SERVICE_MODES.keys())), 0))
        reason = self._p(params, "reason", None)
        st = self._svc_state(name)
        old_mode = st.get("mode", DOM_SERVICE_MODE_TRANSIENT)
        st["mode"] = mode
        st["mode_reason"] = reason
        if mode == DOM_SERVICE_MODE_PINNED:
            until = datetime.datetime.now() + datetime.timedelta(hours=24)
            st["pinned_until"] = until.isoformat()
            st["pin_reason"] = reason or "mode_pinned"
        else:
            if old_mode == DOM_SERVICE_MODE_PINNED:
                st["pinned_until"] = None
                st["pin_reason"] = None
        return (1, {
            "service": name,
            "mode": mode,
            "previous_mode": old_mode,
            "reason": reason,
            "description": DOM_SERVICE_MODES[mode]["description"],
        }, None)

    def _cmd_package(self, params):
        if not HAS_PACKAGE_MANAGER:
            return (0, None, ("ERR_NO_PACKAGE_MANAGER", "core.utility.package_manager not available", 0))
        action = self._p(params, "action", "scan")
        pm = self.state.get("_pm")
        if pm is None:
            pm = PackageManager()
            self.state["_pm"] = pm
        # Forward optional flags that several PackageManager commands accept so
        # callers can drive dry-run / upgrade / python-exe through DomSystem.
        fwd = {}
        for k in ("dry_run", "upgrade", "python", "python_executable", "output"):
            if k in params:
                fwd[k] = params[k]
        if action == "install_missing":
            path = self._p(params, "path", os.getcwd())
            call = {"path": path}
            call.update(fwd)
            ok, data, err = pm.Run("install_missing", call)
        elif action == "resolve":
            module = self._p(params, "module")
            if not module:
                return (0, None, ("ERR_PARAMS", "module required for resolve", 0))
            call = {"module": module}
            call.update(fwd)
            ok, data, err = pm.Run("resolve_import", call)
        elif action == "scan":
            path = self._p(params, "path", os.getcwd())
            ok, data, err = pm.Run("scan_imports", {"path": path})
        elif action == "catalog":
            path = self._p(params, "path", os.getcwd())
            ok, data, err = pm.Run("catalog", {"path": path})
        elif action == "check":
            packages = self._p(params, "packages", [])
            ok, data, err = pm.Run("check_installed", {"packages": packages})
        elif action == "requirements":
            path = self._p(params, "path", os.getcwd())
            call = {"path": path}
            call.update(fwd)
            ok, data, err = pm.Run("generate_requirements", call)
        else:
            return (0, None, ("ERR_UNKNOWN_ACTION", "Unknown package action: %s" % action, 0))
        return (ok, data, err)

    # ════════════════════════════════════════════
    # DIRECT LIFECYCLE (bypass refcount — use sparingly)
    # ════════════════════════════════════════════

    def _cmd_start(self, params):
        name = self._p(params, "service")
        if not name:
            return (0, None, ("ERR_PARAMS", "service required", 0))
        if name not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % name, 0))
        svc = self._svc_cfg(name)
        if svc["launch_mode"] == DOM_LAUNCH_MODE_ALWAYS:
            return (1, {"service": name, "started": True, "note": "always available"}, None)
        ok, _, err = self._ensure_deps_loaded(name)
        if not ok:
            return (0, None, err)
        ok, data, err = self._do_start(name)
        if not ok:
            self.state["stats"]["errors"] += 1
            return (0, None, err)
        st = self._svc_state(name)
        st["loaded"] = True
        st["running"] = True
        st["health_status"] = "healthy"
        st["health_fails"] = 0
        self.state["resources"]["ram_used_mb"] += svc["est_ram_mb"]
        self.state["resources"]["cpu_percent_used"] += svc["est_cpu_percent"]
        if svc["uses_gpu"]:
            self.state["resources"]["gpu_in_use"] = True
        if svc["uses_io"]:
            self.state["resources"]["io_services"] += 1
        self.state["stats"]["starts"] += 1
        return (1, {"service": name, "started": True, "pid": data.get("pid")}, None)

    def _cmd_stop(self, params):
        name = self._p(params, "service")
        if not name:
            return (0, None, ("ERR_PARAMS", "service required", 0))
        if name not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % name, 0))
        svc = self._svc_cfg(name)
        if svc["launch_mode"] == DOM_LAUNCH_MODE_ALWAYS:
            return (1, {"service": name, "stopped": True, "note": "always available"}, None)
        ok, data, err = self._do_stop(name)
        if not ok:
            self.state["stats"]["errors"] += 1
            return (0, None, err)
        st = self._svc_state(name)
        st["running"] = False
        st["health_status"] = "stopped"
        self.state["resources"]["ram_used_mb"] = max(0, self.state["resources"]["ram_used_mb"] - svc["est_ram_mb"])
        self.state["resources"]["cpu_percent_used"] = max(0, self.state["resources"]["cpu_percent_used"] - svc["est_cpu_percent"])
        if svc["uses_gpu"]:
            self.state["resources"]["gpu_in_use"] = False
        if svc["uses_io"]:
            self.state["resources"]["io_services"] = max(0, self.state["resources"]["io_services"] - 1)
        self.state["stats"]["stops"] += 1
        return (1, {"service": name, "stopped": True}, None)

    def _cmd_restart(self, params):
        name = self._p(params, "service")
        if not name:
            return (0, None, ("ERR_PARAMS", "service required", 0))
        if name not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % name, 0))
        svc = self._svc_cfg(name)
        if svc["launch_mode"] == DOM_LAUNCH_MODE_ALWAYS:
            return (1, {"service": name, "restarted": True, "note": "always available"}, None)
        ok, _, err = self._do_stop(name)
        if not ok:
            return (0, None, err)
        time.sleep(1)
        ok, data, err = self._do_start(name)
        if not ok:
            return (0, None, err)
        st = self._svc_state(name)
        st["running"] = True
        st["health_status"] = "healthy"
        st["health_fails"] = 0
        self.state["stats"]["restarts"] += 1
        return (1, {"service": name, "restarted": True, "pid": data.get("pid")}, None)

    # ════════════════════════════════════════════
    # STATUS / HEALTH / BULK
    # ════════════════════════════════════════════

    def _cmd_status(self, params):
        service = self._p(params, "service", "all")
        if service == "all":
            self._refresh_runtime_status()
            return (1, {
                "services": dict(self.state["services"]),
                "resources": dict(self.state["resources"]),
                "stats": dict(self.state["stats"]),
            }, None)
        if service not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % service, 0))
        self._refresh_runtime_status()
        return (1, {"service": service, **self.state["services"].get(service, {})}, None)

    def _cmd_health(self, params):
        name = self._p(params, "service")
        if not name:
            return (0, None, ("ERR_PARAMS", "service required", 0))
        if name not in DOM_SERVICES:
            return (0, None, ("ERR_UNKNOWN_SVC", "Unknown service: %s" % name, 0))
        svc = self._svc_cfg(name)
        if svc["launch_mode"] == DOM_LAUNCH_MODE_ALWAYS:
            return (1, {"service": name, "healthy": True, "response_ms": 0, "note": "always available"}, None)
        self.state["stats"]["health_checks"] += 1
        t0 = time.time()
        if svc.get("health_check") == "process":
            healthy = self._check_process_by_pattern(svc.get("process_pattern", name))
        else:
            healthy = self._check_port(svc["host"], svc["port"])
        response_ms = int((time.time() - t0) * 1000)
        if healthy and svc["health_check"] == "http":
            healthy = self._check_http(svc.get("health_url", "http://%s:%d" % (svc["host"], svc["port"])))
        st = self._svc_state(name)
        if healthy:
            st["health_status"] = "healthy"
            st["health_fails"] = 0
        else:
            st["health_fails"] += 1
            st["health_status"] = "unhealthy"
            if st["health_fails"] >= self.state["config"]["health_fails_before_restart"]:
                if st["restart_count"] < self.state["config"]["max_restarts"]:
                    ok, _, _ = self._cmd_recover({"service": name})
                    if ok:
                        healthy = True
        st["checked_at"] = datetime.datetime.now().isoformat()
        return (1, {
            "service": name,
            "healthy": healthy,
            "response_ms": response_ms,
            "host": svc["host"],
            "port": svc["port"],
            "health_fails": st["health_fails"],
            "restart_count": st["restart_count"],
        }, None)

    def _cmd_check_all(self, params):
        self._refresh_runtime_status()
        all_running = all(
            s.get("running", False) for n, s in self.state["services"].items()
            if self._svc_cfg(n)["launch_mode"] != DOM_LAUNCH_MODE_ALWAYS
        ) and all(
            s.get("running", False) for n, s in self.state["services"].items()
            if self._svc_cfg(n)["launch_mode"] == DOM_LAUNCH_MODE_ALWAYS
        )
        return (1, {
            "services": dict(self.state["services"]),
            "resources": dict(self.state["resources"]),
            "all_running": all_running,
            "checked_at": datetime.datetime.now().isoformat(),
        }, None)

    def _cmd_start_all(self, params):
        results = {}
        for name in DOM_SERVICE_NAMES:
            svc = self._svc_cfg(name)
            if svc["launch_mode"] == DOM_LAUNCH_MODE_ALWAYS:
                results[name] = {"started": True, "note": "always available"}
                continue
            ok, data, err = self._cmd_start({"service": name})
            results[name] = {"started": data.get("started", False) if ok else False, "error": err}
        return (1, {"results": results}, None)

    def _cmd_stop_all(self, params):
        results = {}
        for name in DOM_SERVICE_NAMES:
            svc = self._svc_cfg(name)
            if svc["launch_mode"] == DOM_LAUNCH_MODE_ALWAYS:
                results[name] = {"stopped": True, "note": "always available"}
                continue
            ok, data, err = self._cmd_stop({"service": name})
            results[name] = {"stopped": data.get("stopped", False) if ok else False, "error": err}
        return (1, {"results": results}, None)

    # ════════════════════════════════════════════
    # PROCESS LAUNCH / STOP (port + PID mechanics)
    # ════════════════════════════════════════════

    def _do_start(self, name):
        svc = self._svc_cfg(name)
        if self._is_process_running(name):
            pid = self._get_pid(name)
            return (1, {"pid": pid, "already_running": True}, None)
        binary = svc["binary"]
        if binary and not os.path.exists(binary) and svc["launch_mode"] == DOM_LAUNCH_MODE_DIRECT:
            return (0, None, ("ERR_BIN_NOT_FOUND", "binary not found: %s" % binary, 0))
        logpath = svc["logfile"] or "/tmp/%s.log" % name
        logdir = os.path.dirname(logpath)
        if logdir and not os.path.exists(logdir):
            try:
                os.makedirs(logdir, exist_ok=True)
            except OSError as e:
                return (0, None, ("ERR_LOGDIR", str(e), 0))
        try:
            logfile = open(logpath, "a")
        except OSError as e:
            return (0, None, ("ERR_LOGFILE", str(e), 0))
        try:
            if svc["launch_mode"] == DOM_LAUNCH_MODE_LAUNCHD:
                plist = svc.get("plist", "")
                if not plist or not os.path.exists(plist):
                    return (0, None, ("ERR_PLIST_NOT_FOUND", "plist not found: %s" % plist, 0))
                subprocess.run(
                    ["launchctl", "load", plist],
                    capture_output=True, timeout=15,
                )
            elif svc["launch_mode"] == DOM_LAUNCH_MODE_BREW:
                brew_name = svc.get("brew_name", name)
                subprocess.Popen(
                    ["brew", "services", "start", brew_name],
                    stdout=logfile, stderr=logfile,
                    start_new_session=True,
                )
            else:
                subprocess.Popen(
                    [binary] + svc.get("args", []),
                    stdout=logfile, stderr=logfile,
                    start_new_session=True,
                )
        except OSError as e:
            logfile.close()
            return (0, None, ("ERR_START", str(e), 0))
        wait_secs = self.state["config"]["start_wait_seconds"]
        deadline = time.time() + wait_secs
        while time.time() < deadline:
            time.sleep(0.5)
            if self._is_process_running(name):
                logfile.close()
                return (1, {"pid": self._get_pid(name), "started": True}, None)
        logfile.close()
        return (0, None, ("ERR_START_TIMEOUT", "failed to start within %ds" % wait_secs, 0))

    def _do_stop(self, name):
        svc = self._svc_cfg(name)
        if not self._is_process_running(name):
            return (1, {"already_stopped": True}, None)
        try:
            if svc["launch_mode"] == DOM_LAUNCH_MODE_LAUNCHD:
                plist = svc.get("plist", "")
                if plist and os.path.exists(plist):
                    subprocess.run(
                        ["launchctl", "unload", plist],
                        capture_output=True, timeout=15,
                    )
                else:
                    pid = self._get_pid(name)
                    if pid:
                        try:
                            os.kill(pid, signal.SIGTERM)
                        except (OSError, ProcessLookupError):
                            pass
            elif svc["launch_mode"] == DOM_LAUNCH_MODE_BREW:
                stop_args = ["brew", "services", "stop", svc.get("brew_name", name)]
                subprocess.run(stop_args, capture_output=True, timeout=15)
            elif svc.get("stop_args"):
                subprocess.run([svc["binary"]] + svc["stop_args"], capture_output=True, timeout=15)
            else:
                pid = self._get_pid(name)
                if pid:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except (OSError, ProcessLookupError):
                        pass
        except subprocess.TimeoutExpired:
            pass
        except OSError:
            pass
        timeout = self.state["config"]["stop_timeout_seconds"]
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(0.5)
            if not self._is_process_running(name):
                return (1, {"stopped": True}, None)
        pid = self._get_pid(name)
        if pid:
            try:
                os.kill(pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
            time.sleep(1)
        if not self._is_process_running(name):
            return (1, {"killed": True}, None)
        return (0, None, ("ERR_STOP_TIMEOUT", "failed to stop within %ds" % timeout, 0))

    def _do_unload(self, name):
        svc = self._svc_cfg(name)
        if svc["launch_mode"] == DOM_LAUNCH_MODE_ALWAYS:
            return (1, {"unloaded": False, "note": "always available"}, None)
        ok, _, err = self._do_stop(name)
        if not ok:
            return (0, None, err)
        st = self._svc_state(name)
        st["loaded"] = False
        st["running"] = False
        st["pid"] = None
        st["refs"] = 0
        st["health_status"] = "unloaded"
        self.state["resources"]["ram_used_mb"] = max(0, self.state["resources"]["ram_used_mb"] - svc["est_ram_mb"])
        self.state["resources"]["cpu_percent_used"] = max(0, self.state["resources"]["cpu_percent_used"] - svc["est_cpu_percent"])
        if svc["uses_gpu"]:
            self.state["resources"]["gpu_in_use"] = False
        if svc["uses_io"]:
            self.state["resources"]["io_services"] = max(0, self.state["resources"]["io_services"] - 1)
        return (1, {"unloaded": True}, None)

    # ════════════════════════════════════════════
    # PID / PORT / LIVENESS HELPERS
    # ════════════════════════════════════════════

    def _is_process_running(self, name):
        svc = self._svc_cfg(name)
        if svc["launch_mode"] == DOM_LAUNCH_MODE_ALWAYS:
            return True
        if svc.get("port") and self._check_port(svc["host"], svc["port"]):
            return True
        if svc.get("health_check") == "process" and svc.get("process_pattern"):
            return self._check_process_by_pattern(svc["process_pattern"])
        pid = self._get_pid(name)
        if pid and self._pid_alive(pid):
            return True
        return False

    def _get_pid(self, name):
        svc = self._svc_cfg(name)
        pidfile = svc.get("pidfile")
        if pidfile and os.path.exists(pidfile):
            try:
                with open(pidfile, "r") as f:
                    return int(f.read().strip())
            except (ValueError, IOError):
                pass
        return self._find_pid_by_pgrep(name)

    def _find_pid_by_pgrep(self, name):
        svc = self._svc_cfg(name)
        binary = svc.get("binary")
        if not binary:
            pattern = svc.get("process_pattern", name)
            return self._find_pid_by_pattern(pattern)
        try:
            result = subprocess.run(
                ["pgrep", "-f", binary],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                pid = int(result.stdout.strip().split("\n")[0])
                st = self._svc_state(name)
                if st:
                    st["pid"] = pid
                return pid
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
        return None

    def _find_pid_by_pattern(self, pattern):
        try:
            result = subprocess.run(
                ["pgrep", "-f", pattern],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip().split("\n")[0])
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
        return None

    def _check_process_by_pattern(self, pattern):
        pid = self._find_pid_by_pattern(pattern)
        if pid and self._pid_alive(pid):
            return True
        return False

    def _pid_alive(self, pid):
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def _check_port(self, host, port):
        if not host or not port:
            return False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except (OSError, socket.timeout):
            return False

    def _check_http(self, url):
        try:
            import urllib.request
            req = urllib.request.Request(url, method="GET")
            resp = urllib.request.urlopen(req, timeout=3)
            return resp.status == 200
        except Exception:
            return False

    def _iso_to_epoch(self, iso_str):
        try:
            return datetime.datetime.fromisoformat(iso_str).timestamp()
        except (ValueError, TypeError):
            return time.time()

    def _refresh_runtime_status(self):
        now = datetime.datetime.now().isoformat()
        for name in DOM_SERVICE_NAMES:
            svc = self._svc_cfg(name)
            st = self._svc_state(name)
            if svc["launch_mode"] == DOM_LAUNCH_MODE_ALWAYS:
                st["running"] = True
                st["loaded"] = True
                st["checked_at"] = now
                continue
            running = self._is_process_running(name)
            st["running"] = running
            st["pid"] = self._get_pid(name) if running else None
            st["checked_at"] = now
            if not running and st["loaded"]:
                st["health_status"] = "unhealthy"
