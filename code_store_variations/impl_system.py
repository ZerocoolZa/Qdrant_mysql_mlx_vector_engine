"""VBStyle domain implementation: system.

System introspection: env, hostname, memory, processes, uptime, users.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import os
import platform
import socket
import time
import getpass
import resource
import multiprocessing


class DomSystem:
    """System domain: environment and runtime introspection."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._start = time.time()

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "env": self.env,
            "hostname": self.hostname,
            "info": self.info,
            "load": self.load,
            "memory": self.memory,
            "monitor": self.monitor,
            "network": self.network,
            "platform": self.platform,
            "processes": self.processes,
            "report": self.report,
            "uptime": self.uptime,
            "users": self.users,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def env(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            if key:
                value = os.environ.get(key)
                result = {"domain": "system", "method": "env", "data": {"key": key, "value": value}}
            else:
                result = {"domain": "system", "method": "env", "data": {"env": dict(os.environ), "count": len(os.environ)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ENV_ERROR", str(e), 0))

    def hostname(self, params=None):
        params = params or {}
        try:
            name = socket.gethostname()
            result = {"domain": "system", "method": "hostname", "data": {"hostname": name}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HOSTNAME_ERROR", str(e), 0))

    def info(self, params=None):
        params = params or {}
        try:
            info = {
                "system": platform.system(),
                "node": platform.node(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python": platform.python_version(),
            }
            result = {"domain": "system", "method": "info", "data": info}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("INFO_ERROR", str(e), 0))

    def load(self, params=None):
        params = params or {}
        try:
            try:
                load = os.getloadavg()
            except AttributeError:
                load = (0.0, 0.0, 0.0)
            result = {"domain": "system", "method": "load", "data": {"load1": load[0], "load5": load[1], "load15": load[2]}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LOAD_ERROR", str(e), 0))

    def memory(self, params=None):
        params = params or {}
        try:
            usage = resource.getrusage(resource.RUSAGE_SELF)
            data = {
                "max_rss": usage.ru_maxrss,
                "ru_idrss": getattr(usage, "ru_idrss", 0),
                "ru_ixrss": getattr(usage, "ru_ixrss", 0),
                "ru_isrss": getattr(usage, "ru_isrss", 0),
                "ru_minflt": usage.ru_minflt,
                "ru_majflt": usage.ru_majflt,
            }
            result = {"domain": "system", "method": "memory", "data": data}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MEMORY_ERROR", str(e), 0))

    def monitor(self, params=None):
        params = params or {}
        try:
            snapshot = {
                "timestamp": time.time(),
                "cpu_count": multiprocessing.cpu_count(),
                "uptime": time.time() - self._start,
            }
            self.state["results"].append(snapshot)
            result = {"domain": "system", "method": "monitor", "data": snapshot}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MONITOR_ERROR", str(e), 0))

    def network(self, params=None):
        params = params or {}
        try:
            host = params.get("host") or "localhost"
            port = int(params.get("port", 80))
            try:
                addr = socket.gethostbyname(host)
            except Exception:
                addr = None
            try:
                sock = socket.create_connection((host, port), timeout=float(params.get("timeout", 1.0)))
                reachable = True
                sock.close()
            except Exception:
                reachable = False
            result = {"domain": "system", "method": "network", "data": {"host": host, "port": port, "address": addr, "reachable": reachable}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("NETWORK_ERROR", str(e), 0))

    def platform(self, params=None):
        params = params or {}
        try:
            data = {
                "platform": platform.platform(),
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "python_implementation": platform.python_implementation(),
            }
            result = {"domain": "system", "method": "platform", "data": data}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PLATFORM_ERROR", str(e), 0))

    def processes(self, params=None):
        params = params or {}
        try:
            pids = []
            proc_dir = "/proc"
            if os.path.isdir(proc_dir):
                for entry in os.listdir(proc_dir):
                    if entry.isdigit():
                        pids.append(int(entry))
            count = len(pids) if pids else 0
            result = {"domain": "system", "method": "processes", "data": {"count": count, "pids": pids[:50]}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PROCESSES_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            report = {
                "system": platform.system(),
                "node": platform.node(),
                "uptime": time.time() - self._start,
                "cpu_count": multiprocessing.cpu_count(),
                "python": platform.python_version(),
                "timestamp": time.time(),
            }
            result = {"domain": "system", "method": "report", "data": report}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))

    def uptime(self, params=None):
        params = params or {}
        try:
            up = time.time() - self._start
            result = {"domain": "system", "method": "uptime", "data": {"uptime": up, "started": self._start}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("UPTIME_ERROR", str(e), 0))

    def users(self, params=None):
        params = params or {}
        try:
            try:
                current = getpass.getuser()
            except Exception:
                current = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
            data = {"current": current, "uid": os.getuid() if hasattr(os, "getuid") else None}
            result = {"domain": "system", "method": "users", "data": data}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("USERS_ERROR", str(e), 0))
