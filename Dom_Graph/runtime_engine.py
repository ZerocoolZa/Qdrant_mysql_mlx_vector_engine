#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/runtime_engine.py"
# date="2026-06-26" author="Devin" session_id="phase-orchestration"
# context="Project Digital Twin Section 37 Runtime Knowledge"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="runtime_engine.py" domain="twin_runtime" authority="RuntimeEngine"}
# [@SUMMARY]{summary="Runtime authority that snapshots live objects, memory, threads, and resource usage for the running system."}
# [@CLASS]{class="RuntimeEngine" domain="runtime" authority="single"}
# [@METHOD]{method="snapshot" type="command"}
# [@METHOD]{method="get_objects" type="command"}
# [@METHOD]{method="get_memory" type="command"}
# [@METHOD]{method="get_threads" type="command"}
# [@METHOD]{method="get_resources" type="command"}
# [@METHOD]{method="live_objects" type="command"}
# [@METHOD]{method="memory_map" type="command"}
# [@METHOD]{method="stack_trace" type="command"}
# [@METHOD]{method="open_files" type="command"}
# [@METHOD]{method="open_sockets" type="command"}
# [@METHOD]{method="threads_detail" type="command"}
# [@METHOD]{method="timers" type="command"}
# [@METHOD]{method="handles" type="command"}
# [@METHOD]{method="resource_usage" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<RuntimeEngine: snapshots live objects memory threads resource usage for running system. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations. Header missing Run method declaration but Run() exists in code.>][@todos<none>]}
"""
RuntimeEngine -- Runtime knowledge authority.
Implements Section 37 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: snapshot, get_objects, get_memory, get_threads, get_resources,
          live_objects, memory_map, stack_trace, open_files, open_sockets,
          threads_detail, timers, handles, resource_usage.
"""
import json
import os
import sys
import gc
import threading
import traceback
import sqlite3
from collections import Counter
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50

try:
    import tracemalloc
    TRACEMALLOC_AVAILABLE = True
except Exception:
    TRACEMALLOC_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except Exception:
    PSUTIL_AVAILABLE = False


class RuntimeEngine:
    """Runtime knowledge authority."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
            },
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "snapshot":
            return self.Snapshot(params)
        elif command == "get_objects":
            return self.GetObjects(params)
        elif command == "get_memory":
            return self.GetMemory(params)
        elif command == "get_threads":
            return self.GetThreads(params)
        elif command == "get_resources":
            return self.GetResources(params)
        elif command == "live_objects":
            return self.LiveObjects(params)
        elif command == "memory_map":
            return self.MemoryMap(params)
        elif command == "stack_trace":
            return self.StackTrace(params)
        elif command == "open_files":
            return self.OpenFiles(params)
        elif command == "open_sockets":
            return self.OpenSockets(params)
        elif command == "threads_detail":
            return self.ThreadsDetail(params)
        elif command == "timers":
            return self.Timers(params)
        elif command == "handles":
            return self.Handles(params)
        elif command == "resource_usage":
            return self.ResourceUsage(params)

        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def Connect(self):
        if self.state["db_conn"] is None:
            self.state["db_conn"] = sqlite3.connect(self.state["config"]["db_path"])
        return self.state["db_conn"]

    def Snapshot(self, params):
        # 37.1-37.10 aggregate runtime snapshot, store in observations
        snapshot = {"object_count": len(gc.get_objects()),
                    "thread_count": threading.active_count(),
                    "threads": [t.name for t in threading.enumerate()]}
        if TRACEMALLOC_AVAILABLE:
            if not tracemalloc.is_tracing():
                tracemalloc.start()
            current, peak = tracemalloc.get_traced_memory()
            snapshot["memory_current"] = current
            snapshot["memory_peak"] = peak
        else:
            snapshot["memory_available"] = False
        if PSUTIL_AVAILABLE:
            try:
                proc = psutil.Process()
                snapshot["pid"] = proc.pid
                snapshot["rss"] = proc.memory_info().rss
                snapshot["cpu_percent"] = proc.cpu_percent()
            except Exception:
                snapshot["psutil_available"] = False
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                    "VALUES (?, ?, ?, ?, ?)", ("fact", "runtime_snapshot", json.dumps(snapshot), 50,
                     datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (1, {"snapshot": snapshot}, None)

    def GetObjects(self, params):
        # 37.1 Live Objects: gc.get_objects() filtered by type
        objects = gc.get_objects()
        type_counts = Counter(type(o).__name__ for o in objects)
        top = type_counts.most_common(20)
        return (1, {"total": len(objects), "type_counts": dict(top)}, None)

    def GetMemory(self, params):
        # 37.2 Memory Map: tracemalloc snapshots
        if TRACEMALLOC_AVAILABLE:
            if not tracemalloc.is_tracing():
                tracemalloc.start()
            current, peak = tracemalloc.get_traced_memory()
            return (1, {"current": current, "peak": peak, "available": True}, None)
        return (1, {"available": False}, None)

    def GetThreads(self, params):
        # 37.7 Threads: threading.enumerate()
        threads = [{"name": t.name, "ident": t.ident, "daemon": t.daemon, "alive": t.is_alive()}
                   for t in threading.enumerate()]
        return (1, {"threads": threads, "count": len(threads)}, None)

    def GetResources(self, params):
        # 37.10 Resource Usage: psutil.Process().memory_info(), cpu_percent()
        info = {"pid": os.getpid(), "ppid": os.getppid()}
        if PSUTIL_AVAILABLE:
            try:
                proc = psutil.Process()
                mem = proc.memory_info()
                info["rss"] = mem.rss
                info["vms"] = mem.vms
                info["cpu_percent"] = proc.cpu_percent()
                info["num_threads"] = proc.num_threads()
            except Exception:
                info["psutil_available"] = False
        else:
            info["psutil_available"] = False
        return (1, {"resources": info}, None)

    def LiveObjects(self, params):
        # 37.1/37.3 Live object tracking: heap objects by type with sizes
        object_type = self._p(params, "object_type")
        objects = gc.get_objects()
        if object_type:
            filtered = [o for o in objects if type(o).__name__ == object_type]
        else:
            filtered = objects
        type_sizes = Counter()
        type_counts = Counter()
        for o in filtered:
            tname = type(o).__name__
            type_counts[tname] += 1
            try:
                size = sys.getsizeof(o)
            except Exception:
                size = 0
            type_sizes[tname] += size
        result = []
        for tname, count in type_counts.most_common(30):
            result.append({"type": tname, "count": count, "total_size": type_sizes[tname]})
        return (1, {"total": len(filtered), "by_type": result}, None)

    def MemoryMap(self, params):
        # 37.2 Memory Map: tracemalloc snapshot with per-object attribution
        if not TRACEMALLOC_AVAILABLE:
            return (1, {"available": False}, None)
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        snap = tracemalloc.take_snapshot()
        limit = self._p(params, "limit", 20)
        top_stats = snap.statistics("lineno")[:limit]
        entries = []
        for stat in top_stats:
            frame = stat.traceback[0]
            entries.append({
                "filename": frame.filename, "lineno": frame.lineno,
                "size": stat.size, "count": stat.count,
            })
        current, peak = tracemalloc.get_traced_memory()
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                    "VALUES (?, ?, ?, ?, ?)", ("fact", "memory_map", json.dumps(entries), 50,
                     datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (1, {"current": current, "peak": peak, "top_allocations": entries,
                    "count": len(entries)}, None)

    def StackTrace(self, params):
        # 37.4 Stack: traceback.format_stack() for all threads
        current_stack = traceback.format_stack()
        thread_stacks = {}
        for t in threading.enumerate():
            tid = t.ident
            frames = []
            try:
                if tid is not None:
                    frames_data = sys._current_frames().get(tid)
                    if frames_data:
                        frames = traceback.format_stack(frames_data)
            except Exception:
                frames = []
            thread_stacks[t.name] = frames
        return (1, {"current_stack": current_stack, "thread_stacks": thread_stacks,
                    "thread_count": len(thread_stacks)}, None)

    def OpenFiles(self, params):
        # 37.5 Open Files: psutil.Process().open_files()
        if not PSUTIL_AVAILABLE:
            return (1, {"available": False, "open_files": []}, None)
        try:
            proc = psutil.Process()
            files = [{"path": f.path, "fd": f.fd, "position": f.position,
                      "mode": f.mode, "flags": f.flags}
                     for f in proc.open_files()]
            return (1, {"open_files": files, "count": len(files)}, None)
        except Exception as exc:
            return (0, None, ("PSUTIL_ERROR", str(exc), 0))

    def OpenSockets(self, params):
        # 37.6 Open Sockets: psutil.Process().connections()
        if not PSUTIL_AVAILABLE:
            return (1, {"available": False, "connections": []}, None)
        try:
            proc = psutil.Process()
            conns = proc.connections()
            entries = []
            for c in conns:
                entries.append({
                    "fd": c.fd, "family": c.family, "type": c.type,
                    "laddr": str(c.laddr) if c.laddr else None,
                    "raddr": str(c.raddr) if c.raddr else None,
                    "status": c.status,
                })
            return (1, {"connections": entries, "count": len(entries)}, None)
        except Exception as exc:
            return (0, None, ("PSUTIL_ERROR", str(exc), 0))

    def ThreadsDetail(self, params):
        # 37.7 Threads with full detail
        threads = []
        frames_map = sys._current_frames()
        for t in threading.enumerate():
            entry = {
                "name": t.name, "ident": t.ident, "daemon": t.daemon,
                "alive": t.is_alive(), "native_id": getattr(t, "native_id", None),
            }
            frame = frames_map.get(t.ident) if t.ident else None
            if frame:
                entry["stack"] = traceback.format_stack(frame)
            threads.append(entry)
        return (1, {"threads": threads, "count": len(threads)}, None)

    def Timers(self, params):
        # 37.8 Timers: track threading.Timer instances
        objects = gc.get_objects()
        timers = []
        for o in objects:
            if isinstance(o, threading.Timer):
                timers.append({
                    "interval": o.interval, "function": getattr(o.function, "__name__", str(o.function)),
                    "alive": o.is_alive(), "daemon": o.daemon,
                })
        return (1, {"timers": timers, "count": len(timers)}, None)

    def Handles(self, params):
        # 37.9 Handles: psutil.Process().num_handles() (Windows) / open fd count fallback
        if PSUTIL_AVAILABLE:
            try:
                proc = psutil.Process()
                if hasattr(proc, "num_handles"):
                    return (1, {"handles": proc.num_handles()}, None)
                files = proc.open_files()
                conns = proc.connections()
                return (1, {"handles": len(files) + len(conns),
                            "open_files": len(files), "open_sockets": len(conns)}, None)
            except Exception as exc:
                return (0, None, ("PSUTIL_ERROR", str(exc), 0))
        return (1, {"available": False}, None)

    def ResourceUsage(self, params):
        # 37.10 Resource Usage with CPU time
        import resource as res_module
        usage = {"pid": os.getpid()}
        try:
            rusage = res_module.getrusage(res_module.RUSAGE_SELF)
            usage["utime"] = rusage.ru_utime
            usage["stime"] = rusage.ru_stime
            usage["maxrss"] = rusage.ru_maxrss
            usage["ixrss"] = rusage.ru_ixrss
            usage["idrss"] = rusage.ru_idrss
            usage["isrss"] = rusage.ru_isrss
            usage["minflt"] = rusage.ru_minflt
            usage["majflt"] = rusage.ru_majflt
            usage["nswap"] = rusage.ru_nswap
            usage["inblock"] = rusage.ru_inblock
            usage["oublock"] = rusage.ru_oublock
            usage["msgsnd"] = rusage.ru_msgsnd
            usage["msgrcv"] = rusage.ru_msgrcv
            usage["nsignals"] = rusage.ru_nsignals
            usage["nvcsw"] = rusage.ru_nvcsw
            usage["nivcsw"] = rusage.ru_nivcsw
        except Exception:
            usage["rusage_available"] = False
        if PSUTIL_AVAILABLE:
            try:
                proc = psutil.Process()
                cpu_times = proc.cpu_times()
                usage["cpu_user"] = cpu_times.user
                usage["cpu_system"] = cpu_times.system
                usage["cpu_percent"] = proc.cpu_percent(interval=0.1)
                mem = proc.memory_info()
                usage["rss"] = mem.rss
                usage["vms"] = mem.vms
                usage["num_threads"] = proc.num_threads()
            except Exception:
                usage["psutil_available"] = False
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                    "VALUES (?, ?, ?, ?, ?)", ("fact", "resource_usage", json.dumps(usage), 50,
                     datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (1, {"resource_usage": usage}, None)

