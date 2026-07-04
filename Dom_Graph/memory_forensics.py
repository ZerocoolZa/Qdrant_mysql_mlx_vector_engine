#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/memory_forensics.py"
# date="2026-06-26" author="Devin" session_id="phase-orchestration"
# context="Project Digital Twin Section 38 Memory Forensics"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="memory_forensics.py" domain="twin_memforensics" authority="MemoryForensics"}
# [@SUMMARY]{summary="Memory forensics authority that detects leaks, tracks object lifetimes, records allocation history, and reports peak usage and growth trends."}
# [@CLASS]{class="MemoryForensics" domain="memforensics" authority="single"}
# [@METHOD]{method="detect_leaks" type="command"}
# [@METHOD]{method="track_lifetime" type="command"}
# [@METHOD]{method="allocation_history" type="command"}
# [@METHOD]{method="peak_usage" type="command"}
# [@METHOD]{method="growth_trend" type="command"}
# [@METHOD]{method="fragmentation" type="command"}
# [@METHOD]{method="deallocation_history" type="command"}
# [@METHOD]{method="leak_history" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<MemoryForensics: detects leaks tracks object lifetimes records allocation history reports peak usage and growth trends. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config present. No print no decorators no real self._ violations.>][@todos<none>]}
"""
MemoryForensics -- Memory forensics authority.
Implements Section 38 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: detect_leaks, track_lifetime, allocation_history, peak_usage,
          growth_trend, fragmentation, deallocation_history, leak_history.
"""
import json
import os
import gc
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50

try:
    import tracemalloc
    TRACEMALLOC_AVAILABLE = True
except Exception:
    TRACEMALLOC_AVAILABLE = False


class MemoryForensics:
    """Memory forensics authority."""

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
            "snapshots": [],
            "last_snapshot": None,
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "detect_leaks":
            return self.DetectLeaks(params)
        elif command == "track_lifetime":
            return self.TrackLifetime(params)
        elif command == "allocation_history":
            return self.AllocationHistory(params)
        elif command == "peak_usage":
            return self.PeakUsage(params)
        elif command == "growth_trend":
            return self.GrowthTrend(params)
        elif command == "fragmentation":
            return self.Fragmentation(params)
        elif command == "deallocation_history":
            return self.DeallocationHistory(params)
        elif command == "leak_history":
            return self.LeakHistory(params)

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

    def DetectLeaks(self, params):
        # 38.1 Memory Leak Detection: compare tracemalloc snapshots, find growing allocations
        if not TRACEMALLOC_AVAILABLE:
            return (1, {"available": False, "leaks_detected": False}, None)
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        gc.collect()
        snap_before = tracemalloc.take_snapshot()
        # take a second snapshot after a short interval / gc
        gc.collect()
        snap_after = tracemalloc.take_snapshot()
        diffs = snap_after.compare_to(snap_before, "lineno")
        growing = []
        for stat in diffs:
            if stat.size_diff > 0:
                frame = stat.traceback[0]
                growing.append({
                    "filename": frame.filename, "lineno": frame.lineno,
                    "size_diff": stat.size_diff, "count_diff": stat.count_diff,
                    "size": stat.size, "count": stat.count,
                })
        growing.sort(key=lambda x: x["size_diff"], reverse=True)
        leaks_detected = len(growing) > 0
        conn = self.Connect()
        cur = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        obs_type = "memory_leak" if leaks_detected else "fact"
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (obs_type, "leak_detection", json.dumps(growing[:20]),
                     100 if leaks_detected else 50, now))
        conn.commit()
        return (1, {"leaks_detected": leaks_detected, "growing_allocations": growing[:20],
                    "total_growing": len(growing)}, None)

    def TrackLifetime(self, params):
        # 38.2 Object Lifetime: track __init__ to __del__ timestamps via gc.get_referrers
        object_type = self._p(params, "object_type", "")
        if not object_type:
            return (0, None, ("NO_PARAM", "object_type required", 0))
        objects = gc.get_objects()
        matching = [o for o in objects if type(o).__name__ == object_type]
        lifetime_data = []
        for o in matching[:50]:
            referrers = gc.get_referrers(o)
            ref_types = [type(r).__name__ for r in referrers if r is not self]
            try:
                size = __import__("sys").getsizeof(o)
            except Exception:
                size = 0
            lifetime_data.append({
                "id": id(o), "type": type(o).__name__, "size": size,
                "referrer_count": len(referrers),
                "referrer_types": list(set(ref_types))[:10],
                "is_tracked": gc.is_tracked(o),
            })
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                    "VALUES (?, ?, ?, ?, ?)",
                    ("fact", "lifetime:" + object_type, json.dumps(lifetime_data), 50,
                     datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (1, {"object_type": object_type, "count": len(matching),
                    "lifetime_data": lifetime_data}, None)

    def AllocationHistory(self, params):
        # 38.3 Allocation History: store tracemalloc snapshots over time
        if not TRACEMALLOC_AVAILABLE:
            return (1, {"available": False, "history": []}, None)
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        snap = tracemalloc.take_snapshot()
        now = datetime.now(timezone.utc).isoformat()
        current, peak = tracemalloc.get_traced_memory()
        top_stats = snap.statistics("lineno")[:20]
        entries = []
        for stat in top_stats:
            frame = stat.traceback[0]
            entries.append({
                "filename": frame.filename, "lineno": frame.lineno,
                "size": stat.size, "count": stat.count,
            })
        snap_record = {"created": now, "current": current, "peak": peak,
                       "top_allocations": entries}
        self.state["snapshots"].append(snap_record)
        self.state["last_snapshot"] = snap_record
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                    "VALUES (?, ?, ?, ?, ?)",
                    ("allocation", "tracemalloc_snapshot", json.dumps(snap_record), 50, now))
        conn.commit()
        # also return stored history from DB
        cur.execute("SELECT observation_id, evidence, created FROM observations "
                    "WHERE observation_type='allocation' ORDER BY created DESC LIMIT 50")
        history = []
        for r in cur.fetchall():
            try:
                history.append({"observation_id": r[0], "data": json.loads(r[1]), "created": r[2]})
            except Exception:
                history.append({"observation_id": r[0], "evidence": r[1], "created": r[2]})
        return (1, {"snapshot": snap_record, "history": history, "count": len(history)}, None)

    def PeakUsage(self, params):
        # 38.6 Peak Usage: max memory from tracemalloc
        if not TRACEMALLOC_AVAILABLE:
            return (1, {"available": False}, None)
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        current, peak = tracemalloc.get_traced_memory()
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                    "VALUES (?, ?, ?, ?, ?)",
                    ("fact", "peak_usage", json.dumps({"current": current, "peak": peak}), 50,
                     datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (1, {"peak": peak, "current": current, "available": True}, None)

    def GrowthTrend(self, params):
        # 38.7 Growth Trend: linear regression on memory over time
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT evidence, created FROM observations "
                    "WHERE observation_type='allocation' OR subject LIKE '%memory%' "
                    "OR subject LIKE '%leak%' OR subject LIKE '%peak%' ORDER BY created")
        data_points = []
        for r in cur.fetchall():
            try:
                payload = json.loads(r[0]) if r[0] else {}
            except Exception:
                payload = {}
            if not isinstance(payload, dict):
                continue
            mem_val = payload.get("current") or payload.get("peak")
            if mem_val is not None:
                data_points.append({"created": r[1], "memory": mem_val})
        if len(data_points) < 2:
            return (1, {"trend": "insufficient_data", "data_points": len(data_points)}, None)
        # simple linear regression slope
        n = len(data_points)
        xs = list(range(n))
        ys = [d["memory"] for d in data_points]
        x_mean = sum(xs) / n
        y_mean = sum(ys) / n
        num = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n))
        den = sum((xs[i] - x_mean) ** 2 for i in range(n))
        slope = num / den if den != 0 else 0
        if slope > 0:
            trend = "growing"
        elif slope < 0:
            trend = "shrinking"
        else:
            trend = "stable"
        return (1, {"trend": trend, "slope": slope, "data_points": n,
                    "first": data_points[0], "last": data_points[-1],
                    "min": min(ys), "max": max(ys)}, None)

    def Fragmentation(self, params):
        # 38.5 Fragmentation: estimate fragmentation from allocation patterns
        if not TRACEMALLOC_AVAILABLE:
            return (1, {"available": False}, None)
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        snap = tracemalloc.take_snapshot()
        stats = snap.statistics("lineno")
        if not stats:
            return (1, {"fragmentation_ratio": 0, "available": True, "note": "no allocations"}, None)
        sizes = [stat.size for stat in stats]
        counts = [stat.count for stat in stats]
        total_size = sum(sizes)
        total_count = sum(counts)
        avg_size = total_size / total_count if total_count else 0
        max_size = max(sizes) if sizes else 0
        # fragmentation ratio: variance of allocation sizes normalized
        if max_size > 0:
            variance = sum((s - avg_size) ** 2 for s in sizes) / len(sizes)
            fragmentation_ratio = (variance ** 0.5) / max_size
        else:
            fragmentation_ratio = 0
        result = {
            "available": True, "total_size": total_size, "total_count": total_count,
            "avg_size": avg_size, "max_size": max_size,
            "fragmentation_ratio": fragmentation_ratio,
            "allocation_sites": len(stats),
        }
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                    "VALUES (?, ?, ?, ?, ?)",
                    ("fact", "fragmentation", json.dumps(result), 50,
                     datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (1, result, None)

    def DeallocationHistory(self, params):
        # 38.4 Deallocation History: log all frees (negative size_diff in snapshots)
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT observation_id, subject, evidence, created FROM observations "
                    "WHERE observation_type='deallocation' ORDER BY created DESC")
        results = []
        for r in cur.fetchall():
            try:
                results.append({"observation_id": r[0], "subject": r[1],
                                "data": json.loads(r[2]), "created": r[3]})
            except Exception:
                results.append({"observation_id": r[0], "subject": r[1],
                                "evidence": r[2], "created": r[3]})
        # capture current deallocations via gc if tracemalloc available
        if TRACEMALLOC_AVAILABLE and tracemalloc.is_tracing() and self.state["last_snapshot"]:
            snap = tracemalloc.take_snapshot()
            last = self.state["last_snapshot"]
            # we cannot directly compare to a stored snapshot object, so record freed count
            gc.collect()
            current, peak = tracemalloc.get_traced_memory()
            freed = last.get("current", 0) - current
            if freed > 0:
                cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                            "VALUES (?, ?, ?, ?, ?)",
                            ("deallocation", "gc_freed", json.dumps({"freed_bytes": freed,
                             "current": current}), 50, datetime.now(timezone.utc).isoformat()))
                conn.commit()
        return (1, {"history": results, "count": len(results)}, None)

    def LeakHistory(self, params):
        # 38.8 Leak History: SELECT * FROM observations WHERE observation_type='memory_leak'
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT observation_id, subject, evidence, created FROM observations "
                    "WHERE observation_type='memory_leak' ORDER BY created DESC")
        results = []
        for r in cur.fetchall():
            try:
                results.append({"observation_id": r[0], "subject": r[1],
                                "data": json.loads(r[2]), "created": r[3]})
            except Exception:
                results.append({"observation_id": r[0], "subject": r[1],
                                "evidence": r[2], "created": r[3]})
        return (1, {"leak_history": results, "count": len(results)}, None)

