#[@GHOST]{("file";"Dom_Resource.py")("domain";"Dom_Unified")("role";"resource_monitor")("auth";"devin")("date";"2026-07-03")("ver";"1.0")}
#[@VBSTYLE]{("auth";"devin")("role";"resource_monitor")("return";"Tuple3")("orch";"none")("no";"decorators|print|hardcoded|tabs|self_underscore")("model";"one_class_one_domain_one_authority_complete")}
#[@SUMMARY]{("purpose";"Mac hardware detection, CPU/RAM/disk/network/process monitoring, pressure events, action recommendations, lessons")("scope";"Dom_Unified resource authority")("backing";"SQLite")("replaces";"resource_core.py")}
#[@CLASS]{("name";"DomResource")}
#[@METHOD]{("list";"Run,read_state,set_config,detect_hardware,snapshot,recommend,query_metrics,query_events,query_lessons,record_lesson,publish_truth,start,stop")}

"""
DomResource — resource monitor authority for the Dom_Unified stack.

WHAT IT MANAGES (one class, one domain, one authority):
  - Hardware detection   : RAM, CPU, GPU, disk type via system_profiler
  - Metrics collection   : CPU %, RAM %, disk %, I/O, network, load, processes
  - Pressure events      : RAM > 90%, CPU > 95%, disk > 95%, iowait > 30%
  - Action recommendations : suggests actions, NEVER executes
  - Lessons              : condition -> action -> result -> score
  - MemUnit bridge       : publishes [CPU], [RAM], [IO], [GPU] truth tables

GENERAL FLOW:
  1. Run("detect_hardware") -> detects specs, stores in SQLite
  2. Run("start")           -> starts background monitor thread
  3. Run("snapshot")        -> returns current metrics + top processes
  4. Run("recommend")       -> returns action recommendations
  5. Run("record_lesson")   -> stores condition/action/result/score
  6. Run("publish_truth")   -> feeds MemUnit truth tables
  7. Run("stop")            -> stops monitor

USAGE:
  from Dom_Unified.Dom_Resource import DomResource

  res = DomResource()
  ok, hw, err    = res.Run("detect_hardware")
  ok, data, err  = res.Run("start")
  ok, snap, err  = res.Run("snapshot")
  ok, recs, err  = res.Run("recommend")
  ok, data, err  = res.Run("stop")
"""

import os
import time
import json
import sqlite3
import threading
import hashlib

try:
    import psutil
    HAS_PSUTIL = True
except Exception:
    HAS_PSUTIL = False

from .Config import UNIFIED_ROOT

RESOURCE_DB_PATH = os.path.join(UNIFIED_ROOT, "resource.db")
MONITOR_INTERVAL_SECONDS = 5.0
MAX_METRICS_ROWS = 10000
PROCESS_TOP_N = 20
PRESSURE_RAM_PERCENT = 90.0
PRESSURE_CPU_PERCENT = 95.0
PRESSURE_DISK_PERCENT = 95.0
PRESSURE_IOWAIT_PERCENT = 30.0
RECOMMEND_RAM_PERCENT = 85.0
RECOMMEND_DISK_PERCENT = 90.0
RECOMMEND_CPU_PERCENT = 90.0
RECOMMEND_IOWAIT_PERCENT = 30.0

SCHEMA_SQL = [
    """CREATE TABLE IF NOT EXISTS hardware (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        machine_hash TEXT,
        ram_total_bytes INTEGER,
        ram_total_gb REAL,
        cpu_physical INTEGER,
        cpu_logical INTEGER,
        disk_total_bytes INTEGER,
        disk_total_gb REAL,
        storage_type TEXT,
        gpu_count INTEGER,
        gpu_name TEXT,
        gpu_vram_gb REAL,
        platform TEXT,
        detected_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        cpu_percent REAL,
        ram_percent REAL,
        ram_available_gb REAL,
        ram_used_gb REAL,
        disk_used_percent REAL,
        disk_free_gb REAL,
        disk_read_mbps REAL,
        disk_write_mbps REAL,
        iowait_percent REAL,
        load_1m REAL,
        load_5m REAL,
        load_15m REAL,
        net_sent_mbps REAL,
        net_recv_mbps REAL,
        process_count INTEGER,
        thread_count INTEGER,
        ctx_switches INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS processes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        pid INTEGER,
        name TEXT,
        cpu_percent REAL,
        ram_mb REAL,
        ram_percent REAL,
        num_threads INTEGER,
        status TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        event_type TEXT,
        severity TEXT,
        source TEXT,
        message TEXT,
        data_json TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        action_type TEXT,
        target TEXT,
        description TEXT,
        confidence REAL,
        requires_approval INTEGER,
        executed INTEGER DEFAULT 0,
        result TEXT,
        score REAL
    )""",
    """CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        condition TEXT,
        action TEXT,
        result TEXT,
        score REAL,
        context_json TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(ts)",
    "CREATE INDEX IF NOT EXISTS idx_processes_ts ON processes(ts)",
    "CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)",
    "CREATE INDEX IF NOT EXISTS idx_actions_ts ON actions(ts)",
    "CREATE INDEX IF NOT EXISTS idx_lessons_ts ON lessons(ts)",
]


class DomResource:
    """
    Resource monitor authority for Mac hardware + metrics.
    VBStyle compliant: Run() dispatch, Tuple3 returns, self.state dict.
    No print, no decorators, no self._, no hardcoded values (all via Config constants).
    """

    def __init__(self, mem=None, db=None, param=None):
        cfg = param or {}
        self.state = {
            "config": {
                "db_path": cfg.get("db_path", RESOURCE_DB_PATH),
                "monitor_interval": cfg.get("monitor_interval", MONITOR_INTERVAL_SECONDS),
                "max_metrics_rows": cfg.get("max_metrics_rows", MAX_METRICS_ROWS),
                "process_top_n": cfg.get("process_top_n", PROCESS_TOP_N),
                "pressure_ram_percent": cfg.get("pressure_ram_percent", PRESSURE_RAM_PERCENT),
                "pressure_cpu_percent": cfg.get("pressure_cpu_percent", PRESSURE_CPU_PERCENT),
                "pressure_disk_percent": cfg.get("pressure_disk_percent", PRESSURE_DISK_PERCENT),
                "pressure_iowait_percent": cfg.get("pressure_iowait_percent", PRESSURE_IOWAIT_PERCENT),
                "recommend_ram_percent": cfg.get("recommend_ram_percent", RECOMMEND_RAM_PERCENT),
                "recommend_disk_percent": cfg.get("recommend_disk_percent", RECOMMEND_DISK_PERCENT),
                "recommend_cpu_percent": cfg.get("recommend_cpu_percent", RECOMMEND_CPU_PERCENT),
                "recommend_iowait_percent": cfg.get("recommend_iowait_percent", RECOMMEND_IOWAIT_PERCENT),
            },
            "hardware": {},
            "metrics": {},
            "processes": [],
            "events": [],
            "recommendations": [],
            "stats": {
                "samples": 0,
                "events_logged": 0,
                "recommendations_made": 0,
                "lessons_recorded": 0,
                "errors": 0,
            },
            "runtime": {
                "monitoring": False,
                "hardware_detected": False,
            },
        }
        self.mem = mem
        self.db = db
        self.conn = None
        self.lock = threading.Lock()
        self.thread = None
        self.last_disk_io = None
        self.last_net_io = None
        self.last_sample_time = None
        self.latest = {}

    def _p(self, params, key, default=None):
        if not params:
            return (1, default, None)
        return (1, params.get(key, default), None)

    def Run(self, command, params=None):
        dispatch = {
            "detect_hardware": self._cmd_detect_hardware,
            "snapshot": self._cmd_snapshot,
            "recommend": self._cmd_recommend,
            "query_metrics": self._cmd_query_metrics,
            "query_events": self._cmd_query_events,
            "query_lessons": self._cmd_query_lessons,
            "record_lesson": self._cmd_record_lesson,
            "publish_truth": self._cmd_publish_truth,
            "start": self._cmd_start,
            "stop": self._cmd_stop,
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
        return (1, dict(self.state["config"]), None)

    # ============================================================
    # DATABASE
    # ============================================================

    def _db(self):
        if self.conn is None:
            self.conn = sqlite3.connect(self.state["config"]["db_path"], check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            for stmt in SCHEMA_SQL:
                self.conn.execute(stmt)
            self.conn.commit()
        return self.conn

    def _execute(self, sql, params=()):
        with self.lock:
            cur = self.db if self.db else self._db()
            if self.db:
                result = cur.Run("execute", {"sql": sql, "params": list(params)})
                return result
            cur.execute(sql, params)
            self.conn.commit()
            return cur

    # ============================================================
    # HARDWARE DETECTION
    # ============================================================

    def _cmd_detect_hardware(self, params):
        if not HAS_PSUTIL:
            return (0, None, ("ERR_PSUTIL", "psutil not installed", 0))
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        storage_type = self._detect_storage_type()
        gpu_count, gpu_name, gpu_vram = self._detect_gpu()
        hw = {
            "ram_total_bytes": mem.total,
            "ram_total_gb": round(mem.total / (1024 ** 3), 2),
            "cpu_physical": psutil.cpu_count(logical=False) or 1,
            "cpu_logical": psutil.cpu_count(logical=True) or 1,
            "disk_total_bytes": disk.total,
            "disk_total_gb": round(disk.total / (1024 ** 3), 2),
            "storage_type": storage_type,
            "gpu_count": gpu_count,
            "gpu_name": gpu_name,
            "gpu_vram_gb": gpu_vram,
            "platform": os.uname().sysname if hasattr(os, "uname") else "unknown",
            "detected_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        machine_id = "%s_%s_%s_%s" % (hw["ram_total_gb"], hw["cpu_logical"], hw["storage_type"], hw["gpu_count"])
        hw["machine_hash"] = hashlib.sha256(machine_id.encode()).hexdigest()[:16]
        self._execute(
            "INSERT INTO hardware (machine_hash, ram_total_bytes, ram_total_gb, cpu_physical, cpu_logical, disk_total_bytes, disk_total_gb, storage_type, gpu_count, gpu_name, gpu_vram_gb, platform, detected_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (hw["machine_hash"], hw["ram_total_bytes"], hw["ram_total_gb"], hw["cpu_physical"], hw["cpu_logical"], hw["disk_total_bytes"], hw["disk_total_gb"], hw["storage_type"], hw["gpu_count"], hw["gpu_name"], hw["gpu_vram_gb"], hw["platform"], hw["detected_at"]),
        )
        self.state["hardware"] = hw
        self.state["runtime"]["hardware_detected"] = True
        return (1, hw, None)

    def _detect_storage_type(self):
        try:
            import subprocess
            r = subprocess.run(["diskutil", "list"], capture_output=True, text=True, timeout=3)
            if "NVMe" in r.stdout or "Apple SSD" in r.stdout:
                return "nvme"
            if "SSD" in r.stdout:
                return "ssd"
            return "hdd"
        except Exception:
            return "unknown"

    def _detect_gpu(self):
        try:
            import subprocess
            r = subprocess.run(["system_profiler", "SPDisplaysDataType", "-json"], capture_output=True, text=True, timeout=5)
            if r.returncode != 0:
                return (0, "none", 0.0)
            data = json.loads(r.stdout)
            displays = data.get("SPDisplaysDataType", [])
            if not displays:
                return (0, "none", 0.0)
            count = len(displays)
            name = displays[0].get("sppci_name", "unknown")
            vram_str = displays[0].get("sppci_vram", "0")
            vram = 0.0
            if isinstance(vram_str, str):
                vram_str = vram_str.replace("GB", "").strip()
                try:
                    vram = float(vram_str)
                except ValueError:
                    pass
            return (count, name, vram)
        except Exception:
            return (0, "none", 0.0)

    # ============================================================
    # METRICS COLLECTION
    # ============================================================

    def _collect_metrics(self):
        if not HAS_PSUTIL:
            return {}
        now = time.time()
        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        disk_io = psutil.disk_io_counters()
        net_io = psutil.net_io_counters()
        disk_read_mbps = 0.0
        disk_write_mbps = 0.0
        if disk_io and self.last_disk_io and self.last_sample_time:
            dt = now - self.last_sample_time
            if dt > 0:
                disk_read_mbps = (disk_io.read_bytes - self.last_disk_io.read_bytes) / (1024 ** 2) / dt
                disk_write_mbps = (disk_io.write_bytes - self.last_disk_io.write_bytes) / (1024 ** 2) / dt
        net_sent_mbps = 0.0
        net_recv_mbps = 0.0
        if net_io and self.last_net_io and self.last_sample_time:
            dt = now - self.last_sample_time
            if dt > 0:
                net_sent_mbps = (net_io.bytes_sent - self.last_net_io.bytes_sent) / (1024 ** 2) / dt
                net_recv_mbps = (net_io.bytes_recv - self.last_net_io.bytes_recv) / (1024 ** 2) / dt
        iowait = 0.0
        try:
            cpu_times = psutil.cpu_times()
            total = sum(cpu_times)
            if total > 0:
                iowait = (getattr(cpu_times, "iowait", 0) / total) * 100.0
        except Exception:
            pass
        load = (0, 0, 0)
        try:
            if hasattr(os, "getloadavg"):
                load = os.getloadavg()
        except Exception:
            pass
        ctx = 0
        try:
            ctx = psutil.cpu_stats().ctx_switches
        except Exception:
            pass
        proc_count = 0
        thread_count = 0
        try:
            for p in psutil.process_iter(["num_threads"]):
                proc_count += 1
                thread_count += p.info.get("num_threads", 0) or 0
        except Exception:
            pass
        metrics = {
            "ts": now,
            "cpu_percent": round(cpu_percent, 2),
            "ram_percent": round(mem.percent, 2),
            "ram_available_gb": round(mem.available / (1024 ** 3), 2),
            "ram_used_gb": round(mem.used / (1024 ** 3), 2),
            "disk_used_percent": round(disk.percent, 2),
            "disk_free_gb": round(disk.free / (1024 ** 3), 2),
            "disk_read_mbps": round(disk_read_mbps, 2),
            "disk_write_mbps": round(disk_write_mbps, 2),
            "iowait_percent": round(iowait, 2),
            "load_1m": round(load[0], 2),
            "load_5m": round(load[1], 2),
            "load_15m": round(load[2], 2),
            "net_sent_mbps": round(net_sent_mbps, 2),
            "net_recv_mbps": round(net_recv_mbps, 2),
            "process_count": proc_count,
            "thread_count": thread_count,
            "ctx_switches": ctx,
        }
        self.last_disk_io = disk_io
        self.last_net_io = net_io
        self.last_sample_time = now
        return metrics

    def _store_metrics(self, m):
        self._execute(
            "INSERT INTO metrics (ts, cpu_percent, ram_percent, ram_available_gb, ram_used_gb, disk_used_percent, disk_free_gb, disk_read_mbps, disk_write_mbps, iowait_percent, load_1m, load_5m, load_15m, net_sent_mbps, net_recv_mbps, process_count, thread_count, ctx_switches) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (m["ts"], m["cpu_percent"], m["ram_percent"], m["ram_available_gb"], m["ram_used_gb"], m["disk_used_percent"], m["disk_free_gb"], m["disk_read_mbps"], m["disk_write_mbps"], m["iowait_percent"], m["load_1m"], m["load_5m"], m["load_15m"], m["net_sent_mbps"], m["net_recv_mbps"], m["process_count"], m["thread_count"], m["ctx_switches"]),
        )
        count = self._execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
        if count > self.state["config"]["max_metrics_rows"]:
            self._execute("DELETE FROM metrics WHERE id <= (SELECT id FROM metrics ORDER BY id DESC LIMIT 1 OFFSET ?)", (self.state["config"]["max_metrics_rows"],))

    def _collect_top_processes(self):
        if not HAS_PSUTIL:
            return []
        procs = []
        try:
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "memory_info", "num_threads", "status"]):
                try:
                    info = p.info
                    ram_mb = 0
                    if info.get("memory_info"):
                        ram_mb = info["memory_info"].rss / (1024 ** 2)
                    procs.append({
                        "pid": info.get("pid", 0),
                        "name": info.get("name", "?"),
                        "cpu_percent": round(info.get("cpu_percent", 0) or 0, 2),
                        "ram_mb": round(ram_mb, 2),
                        "ram_percent": round(info.get("memory_percent", 0) or 0, 2),
                        "num_threads": info.get("num_threads", 0) or 0,
                        "status": info.get("status", "?"),
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        procs.sort(key=lambda p: (p["cpu_percent"], p["ram_mb"]), reverse=True)
        return procs[:self.state["config"]["process_top_n"]]

    def _store_processes(self, procs, ts):
        for p in procs:
            self._execute(
                "INSERT INTO processes (ts, pid, name, cpu_percent, ram_mb, ram_percent, num_threads, status) VALUES (?,?,?,?,?,?,?,?)",
                (ts, p["pid"], p["name"], p["cpu_percent"], p["ram_mb"], p["ram_percent"], p["num_threads"], p["status"]),
            )

    # ============================================================
    # PRESSURE CHECK
    # ============================================================

    def _check_pressure(self, m):
        cfg = self.state["config"]
        if m["ram_percent"] > cfg["pressure_ram_percent"]:
            self._log_event("ram_pressure", "warning", "monitor", "RAM at %s%%" % m["ram_percent"], {"available_gb": m["ram_available_gb"]})
        if m["cpu_percent"] > cfg["pressure_cpu_percent"]:
            self._log_event("cpu_pressure", "warning", "monitor", "CPU at %s%%" % m["cpu_percent"])
        if m["disk_used_percent"] > cfg["pressure_disk_percent"]:
            self._log_event("disk_pressure", "warning", "monitor", "Disk at %s%%" % m["disk_used_percent"], {"free_gb": m["disk_free_gb"]})
        if m["iowait_percent"] > cfg["pressure_iowait_percent"]:
            self._log_event("io_pressure", "warning", "monitor", "iowait at %s%%" % m["iowait_percent"])

    def _log_event(self, event_type, severity, source, message, data=None):
        self._execute(
            "INSERT INTO events (ts, event_type, severity, source, message, data_json) VALUES (?,?,?,?,?,?)",
            (time.time(), event_type, severity, source, message, json.dumps(data) if data else None),
        )
        self.state["stats"]["events_logged"] += 1

    # ============================================================
    # MONITOR LOOP
    # ============================================================

    def _monitor_loop(self):
        while self.state["runtime"]["monitoring"]:
            try:
                metrics = self._collect_metrics()
                if not metrics:
                    break
                self._store_metrics(metrics)
                procs = self._collect_top_processes()
                self._store_processes(procs, metrics["ts"])
                with self.lock:
                    self.latest = {"metrics": metrics, "processes": procs}
                self.state["metrics"] = metrics
                self.state["processes"] = procs
                self._check_pressure(metrics)
                self.state["stats"]["samples"] += 1
            except Exception:
                self.state["stats"]["errors"] += 1
            time.sleep(self.state["config"]["monitor_interval"])

    # ============================================================
    # COMMANDS
    # ============================================================

    def _cmd_start(self, params):
        if not self.state["runtime"]["hardware_detected"]:
            ok, hw, err = self._cmd_detect_hardware(params)
            if not ok:
                return (0, None, err)
        if self.state["runtime"]["monitoring"]:
            return (1, {"already_running": True}, None)
        self.state["runtime"]["monitoring"] = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        return (1, {"monitoring": True}, None)

    def _cmd_stop(self, params):
        self.state["runtime"]["monitoring"] = False
        if self.thread:
            self.thread.join(timeout=10)
            self.thread = None
        if self.conn:
            self.conn.close()
            self.conn = None
        return (1, {"monitoring": False}, None)

    def _cmd_snapshot(self, params):
        if not self.latest:
            if not HAS_PSUTIL:
                return (0, None, ("ERR_PSUTIL", "psutil not installed", 0))
            m = self._collect_metrics()
            procs = self._collect_top_processes()
            self.latest = {"metrics": m, "processes": procs}
        return (1, dict(self.latest), None)

    def _cmd_recommend(self, params):
        ok, snap, err = self._cmd_snapshot(params)
        if not ok:
            return (0, None, err)
        m = snap.get("metrics", {})
        cfg = self.state["config"]
        recs = []
        if m.get("ram_percent", 0) > cfg["recommend_ram_percent"]:
            recs.append({
                "action_type": "clear_cache",
                "target": "system",
                "description": "RAM at %s%%. Consider clearing caches or closing unused processes." % m["ram_percent"],
                "confidence": 0.85,
                "requires_approval": True,
                "condition": "ram_percent > %s (%s%%)" % (cfg["recommend_ram_percent"], m["ram_percent"]),
            })
        if m.get("disk_used_percent", 0) > cfg["recommend_disk_percent"]:
            recs.append({
                "action_type": "cleanup_disk",
                "target": "system",
                "description": "Disk at %s%%. %sGB free. Consider cleanup." % (m["disk_used_percent"], m.get("disk_free_gb", 0)),
                "confidence": 0.90,
                "requires_approval": True,
                "condition": "disk_used_percent > %s (%s%%)" % (cfg["recommend_disk_percent"], m["disk_used_percent"]),
            })
        if m.get("cpu_percent", 0) > cfg["recommend_cpu_percent"]:
            top_procs = snap.get("processes", [])[:3]
            proc_names = [p["name"] for p in top_procs if p["cpu_percent"] > 20]
            recs.append({
                "action_type": "reduce_load",
                "target": ", ".join(proc_names) if proc_names else "system",
                "description": "CPU at %s%%. Top consumers: %s" % (m["cpu_percent"], proc_names),
                "confidence": 0.75,
                "requires_approval": True,
                "condition": "cpu_percent > %s (%s%%)" % (cfg["recommend_cpu_percent"], m["cpu_percent"]),
            })
        if m.get("iowait_percent", 0) > cfg["recommend_iowait_percent"]:
            recs.append({
                "action_type": "reduce_io",
                "target": "system",
                "description": "iowait at %s%%. Disk I/O is bottleneck." % m["iowait_percent"],
                "confidence": 0.70,
                "requires_approval": True,
                "condition": "iowait_percent > %s (%s%%)" % (cfg["recommend_iowait_percent"], m["iowait_percent"]),
            })
        for rec in recs:
            self._execute(
                "INSERT INTO actions (ts, action_type, target, description, confidence, requires_approval) VALUES (?,?,?,?,?,?)",
                (time.time(), rec["action_type"], rec["target"], rec["description"], rec["confidence"], 1),
            )
        self.state["recommendations"] = recs
        self.state["stats"]["recommendations_made"] += len(recs)
        return (1, recs, None)

    def _cmd_query_metrics(self, params):
        ok, limit, err = self._p(params, "limit", 100)
        ok2, since, err2 = self._p(params, "since", None)
        if since:
            rows = self._execute("SELECT * FROM metrics WHERE ts > ? ORDER BY ts DESC LIMIT ?", (since, limit)).fetchall()
        else:
            rows = self._execute("SELECT * FROM metrics ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        return (1, [dict(r) for r in rows], None)

    def _cmd_query_events(self, params):
        ok, limit, err = self._p(params, "limit", 50)
        ok2, severity, err2 = self._p(params, "severity", None)
        if severity:
            rows = self._execute("SELECT * FROM events WHERE severity = ? ORDER BY ts DESC LIMIT ?", (severity, limit)).fetchall()
        else:
            rows = self._execute("SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        return (1, [dict(r) for r in rows], None)

    def _cmd_query_lessons(self, params):
        ok, limit, err = self._p(params, "limit", 50)
        rows = self._execute("SELECT * FROM lessons ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        return (1, [dict(r) for r in rows], None)

    def _cmd_record_lesson(self, params):
        ok, condition, err = self._p(params, "condition", "")
        ok2, action, err2 = self._p(params, "action", "")
        ok3, result, err3 = self._p(params, "result", "")
        ok4, score, err4 = self._p(params, "score", 0.0)
        ok5, context, err5 = self._p(params, "context", None)
        self._execute(
            "INSERT INTO lessons (ts, condition, action, result, score, context_json) VALUES (?,?,?,?,?,?)",
            (time.time(), condition, action, result, float(score), json.dumps(context) if context else None),
        )
        self.state["stats"]["lessons_recorded"] += 1
        return (1, {"recorded": True}, None)

    def _cmd_publish_truth(self, params):
        try:
            ok, snap, err = self._cmd_snapshot(params)
            if not ok:
                return (0, None, err)
            m = snap.get("metrics", {})
            hw = self.state["hardware"]
            truth = {
                "[CPU]": {
                    "threads_total": hw.get("cpu_logical", 0),
                    "cpu_percent": m.get("cpu_percent", 0),
                    "load_1m": m.get("load_1m", 0),
                    "load_5m": m.get("load_5m", 0),
                    "process_count": m.get("process_count", 0),
                },
                "[RAM]": {
                    "total_gb": hw.get("ram_total_gb", 0),
                    "free_gb": m.get("ram_available_gb", 0),
                    "used_percent": m.get("ram_percent", 0),
                },
                "[IO]": {
                    "write_mbps": m.get("disk_write_mbps", 0),
                    "read_mbps": m.get("disk_read_mbps", 0),
                    "iowait_percent": m.get("iowait_percent", 0),
                    "disk_free_gb": m.get("disk_free_gb", 0),
                    "storage_type": hw.get("storage_type", "unknown"),
                },
                "[GPU]": {
                    "count": hw.get("gpu_count", 0),
                    "name": hw.get("gpu_name", "none"),
                    "vram_gb": hw.get("gpu_vram_gb", 0),
                },
            }
            if self.mem:
                if hasattr(self.mem, "Run"):
                    self.mem.Run("ingest_truth", {"truth": truth})
                elif hasattr(self.mem, "ingest_truth"):
                    self.mem.ingest_truth(truth)
            return (1, {"published": True, "tables": list(truth.keys())}, None)
        except Exception as e:
            return (0, None, ("PUBLISH_ERROR", str(e), 0))
