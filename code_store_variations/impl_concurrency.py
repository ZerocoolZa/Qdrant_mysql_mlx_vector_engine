"""VBStyle domain implementation: concurrency.

Threads, async, locks, channels, futures, atomics.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import threading
import queue
import asyncio
import concurrent.futures
import time
import uuid


class DomConcurrency:
    """Concurrency domain: threads, async, locks, channels, futures."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._threads = {}
        self._tasks = {}
        self._locks = {}
        self._channels = {}
        self._futures = {}
        self._lock = threading.Lock()
        self._executor = None

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "spawn_thread": self.spawn_thread,
            "spawn_async": self.spawn_async,
            "create_lock": self.create_lock,
            "create_channel": self.create_channel,
            "join_all": self.join_all,
            "select": self.select,
            "cancel": self.cancel,
            "get_status": self.get_status,
            "wait_any": self.wait_any,
            "map_reduce": self.map_reduce,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def spawn_thread(self, params=None):
        params = params or {}
        try:
            fn = params.get("fn")
            args = params.get("args", [])
            kwargs = params.get("kwargs", {})
            daemon = bool(params.get("daemon", True))
            if not callable(fn):
                return (0, None, ("SPAWN_THREAD_ERROR", "fn not callable", 0))
            box = {"result": None, "error": None, "done": False}
            def _runner():
                try:
                    box["result"] = fn(*args, **kwargs)
                except Exception as e:
                    box["error"] = str(e)
                finally:
                    box["done"] = True
            t = threading.Thread(target=_runner, daemon=daemon)
            t.start()
            tid = str(uuid.uuid4())
            with self._lock:
                self._threads[tid] = {"thread": t, "box": box, "started_at": time.time()}
            result = {"domain": "concurrency", "method": "spawn_thread", "data": {"id": tid, "alive": t.is_alive(), "daemon": daemon}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SPAWN_THREAD_ERROR", str(e), 0))

    def spawn_async(self, params=None):
        params = params or {}
        try:
            fn = params.get("fn")
            args = params.get("args", [])
            kwargs = params.get("kwargs", {})
            if not callable(fn):
                return (0, None, ("SPAWN_ASYNC_ERROR", "fn not callable", 0))
            loop = asyncio.new_event_loop()
            box = {"result": None, "error": None, "done": False}
            def _runner():
                asyncio.set_event_loop(loop)
                try:
                    coro = fn(*args, **kwargs)
                    if asyncio.iscoroutine(coro):
                        box["result"] = loop.run_until_complete(coro)
                    else:
                        box["result"] = coro
                except Exception as e:
                    box["error"] = str(e)
                finally:
                    box["done"] = True
                    loop.close()
            t = threading.Thread(target=_runner, daemon=True)
            t.start()
            tid = str(uuid.uuid4())
            with self._lock:
                self._tasks[tid] = {"thread": t, "box": box, "started_at": time.time()}
            result = {"domain": "concurrency", "method": "spawn_async", "data": {"id": tid, "alive": t.is_alive()}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SPAWN_ASYNC_ERROR", str(e), 0))

    def create_lock(self, params=None):
        params = params or {}
        try:
            name = params.get("name", str(uuid.uuid4()))
            kind = params.get("kind", "threading")
            if kind == "threading":
                lock = threading.Lock()
            elif kind == "rlock":
                lock = threading.RLock()
            elif kind == "semaphore":
                permits = int(params.get("permits", 1))
                lock = threading.Semaphore(permits)
            elif kind == "event":
                lock = threading.Event()
            else:
                return (0, None, ("CREATE_LOCK_ERROR", f"unknown kind: {kind}", 0))
            with self._lock:
                self._locks[name] = {"lock": lock, "kind": kind, "created_at": time.time()}
            result = {"domain": "concurrency", "method": "create_lock", "data": {"name": name, "kind": kind}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CREATE_LOCK_ERROR", str(e), 0))

    def create_channel(self, params=None):
        params = params or {}
        try:
            name = params.get("name", str(uuid.uuid4()))
            capacity = int(params.get("capacity", 0))
            if capacity <= 0:
                ch = queue.Queue()
            else:
                ch = queue.Queue(maxsize=capacity)
            with self._lock:
                self._channels[name] = {"queue": ch, "capacity": capacity, "created_at": time.time(), "sent": 0, "received": 0}
            result = {"domain": "concurrency", "method": "create_channel", "data": {"name": name, "capacity": capacity}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CREATE_CHANNEL_ERROR", str(e), 0))

    def join_all(self, params=None):
        params = params or {}
        try:
            ids = params.get("ids", [])
            timeout = float(params.get("timeout", 30.0))
            if not ids:
                with self._lock:
                    ids = list(self._threads.keys()) + list(self._tasks.keys())
            joined = []
            timed_out = []
            for tid in ids:
                with self._lock:
                    entry = self._threads.get(tid) or self._tasks.get(tid)
                if entry is None:
                    continue
                entry["thread"].join(timeout)
                if entry["thread"].is_alive():
                    timed_out.append(tid)
                else:
                    joined.append(tid)
            results = {}
            for tid in joined:
                with self._lock:
                    entry = self._threads.get(tid) or self._tasks.get(tid)
                if entry:
                    box = entry["box"]
                    results[tid] = {"result": box.get("result"), "error": box.get("error"), "done": box.get("done")}
            result = {"domain": "concurrency", "method": "join_all", "data": {"joined": joined, "timed_out": timed_out, "results": results}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("JOIN_ALL_ERROR", str(e), 0))

    def select(self, params=None):
        params = params or {}
        try:
            channels = params.get("channels", [])
            timeout = float(params.get("timeout", 0.0))
            if not channels:
                return (0, None, ("SELECT_ERROR", "no channels", 0))
            deadline = time.time() + timeout if timeout > 0 else None
            while True:
                for name in channels:
                    with self._lock:
                        ch = self._channels.get(name)
                    if ch is None:
                        continue
                    try:
                        value = ch["queue"].get_nowait()
                        ch["received"] += 1
                        result = {"domain": "concurrency", "method": "select", "data": {"channel": name, "value": value, "received": True}}
                        return (1, result, None)
                    except queue.Empty:
                        continue
                if deadline is not None and time.time() >= deadline:
                    result = {"domain": "concurrency", "method": "select", "data": {"received": False, "channels": channels}}
                    return (1, result, None)
                time.sleep(0.001)
        except Exception as e:
            return (0, None, ("SELECT_ERROR", str(e), 0))

    def cancel(self, params=None):
        params = params or {}
        try:
            tid = params.get("id")
            if tid is None:
                return (0, None, ("CANCEL_ERROR", "missing id", 0))
            with self._lock:
                entry = self._threads.get(tid) or self._tasks.get(tid)
            if entry is None:
                return (0, None, ("CANCEL_ERROR", "id not found", 0))
            alive = entry["thread"].is_alive()
            cancelled = False
            if not alive:
                cancelled = True
            result = {"domain": "concurrency", "method": "cancel", "data": {"id": tid, "alive": alive, "cancelled": cancelled}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CANCEL_ERROR", str(e), 0))

    def get_status(self, params=None):
        params = params or {}
        try:
            tid = params.get("id")
            with self._lock:
                if tid is not None:
                    entry = self._threads.get(tid) or self._tasks.get(tid)
                    if entry is None:
                        return (0, None, ("GET_STATUS_ERROR", "id not found", 0))
                    box = entry["box"]
                    status = {"id": tid, "alive": entry["thread"].is_alive(), "done": box.get("done"), "result": box.get("result"), "error": box.get("error")}
                else:
                    status = {
                        "threads": len(self._threads),
                        "tasks": len(self._tasks),
                        "locks": len(self._locks),
                        "channels": len(self._channels),
                        "ids": list(self._threads.keys()) + list(self._tasks.keys()),
                    }
            result = {"domain": "concurrency", "method": "get_status", "data": status}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GET_STATUS_ERROR", str(e), 0))

    def wait_any(self, params=None):
        params = params or {}
        try:
            ids = params.get("ids", [])
            timeout = float(params.get("timeout", 30.0))
            if not ids:
                with self._lock:
                    ids = list(self._threads.keys()) + list(self._tasks.keys())
            deadline = time.time() + timeout
            winner = None
            while time.time() < deadline:
                for tid in ids:
                    with self._lock:
                        entry = self._threads.get(tid) or self._tasks.get(tid)
                    if entry is None:
                        continue
                    if entry["box"].get("done"):
                        winner = tid
                        break
                if winner:
                    break
                time.sleep(0.001)
            result_data = {"winner": winner, "timed_out": winner is None}
            if winner:
                with self._lock:
                    entry = self._threads.get(winner) or self._tasks.get(winner)
                if entry:
                    result_data["result"] = entry["box"].get("result")
                    result_data["error"] = entry["box"].get("error")
            result = {"domain": "concurrency", "method": "wait_any", "data": result_data}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("WAIT_ANY_ERROR", str(e), 0))

    def map_reduce(self, params=None):
        params = params or {}
        try:
            data = params.get("data", [])
            mapper = params.get("mapper")
            reducer = params.get("reducer")
            max_workers = int(params.get("max_workers", 4))
            if not data:
                result = {"domain": "concurrency", "method": "map_reduce", "data": {"mapped": [], "reduced": None, "count": 0}}
                return (1, result, None)
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
            try:
                if callable(mapper):
                    mapped = list(executor.map(mapper, data))
                else:
                    mapped = list(data)
            finally:
                executor.shutdown(wait=True)
            reduced = None
            if callable(reducer):
                reduced = reducer(mapped)
            elif mapped:
                reduced = mapped
            result = {"domain": "concurrency", "method": "map_reduce", "data": {"mapped": mapped, "reduced": reduced, "count": len(mapped)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MAP_REDUCE_ERROR", str(e), 0))
