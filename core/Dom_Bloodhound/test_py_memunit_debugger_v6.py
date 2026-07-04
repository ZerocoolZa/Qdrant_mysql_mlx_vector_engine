#!/usr/bin/env python3
"""
test_py_memunit_debugger_v6.py — v6: Trace Engine Architecture

Evolution: Logger → Event System → Trace Engine → Observability Framework

v6 implements the full P0-P9 backlog:

P0: Bounded replay (deque maxlen), query indexes (O(1)), background SQLite thread
P1: Native values (no str()), float timing, delayed JSON, batched Rich
P2: Reduced duplicate storage, configurable replay, SoA option
P3: Consumer interface, Dispatcher fan-out, plugin callbacks
P4: dataclass(frozen=True, slots=True), numeric enums, no string formatting in core
P5: Query engine with predicates, time ranges, custom filters
P6: Statistics engine — phase/entity/source/severity/duration counts
P7: Replay engine — forward/reverse/range/filtered/by-source/by-entity
P8: Multiple viewer modes — timeline/tree/graph/stats/profiler/errors/vars/state/live
P9: Trace engine architecture — Producer → EventBus → Dispatcher → Consumers

Architecture:
                Producer
                    │
                    ▼
              EventBus (core)
              ├── ReplayStore (bounded deque)
              ├── IndexStore (O(1) query indexes)
              ├── StatsEngine (O(1) summaries)
              └── Dispatcher
                    ├── ViewerConsumer
                    ├── SQLiteConsumer (background thread)
                    ├── DebuggerConsumer
                    └── MetricsConsumer

Usage:
  python3 test_py_memunit_debugger_v6.py              # live + structure + graph + tests
  python3 test_py_memunit_debugger_v6.py 0            # silent
  python3 test_py_memunit_debugger_v6.py 2            # debug
  python3 test_py_memunit_debugger_v6.py 3            # verbose
  python3 test_py_memunit_debugger_v6.py --table      # summary table + structure + graph + tests
  python3 test_py_memunit_debugger_v6.py --overview   # AI inspection
  python3 test_py_memunit_debugger_v6.py --replay     # replay inspection
  python3 test_py_memunit_debugger_v6.py --profile    # profiler inspection
  python3 test_py_memunit_debugger_v6.py --debug      # debugger inspection
  python3 test_py_memunit_debugger_v6.py --test       # test results only
  python3 test_py_memunit_debugger_v6.py --all        # all inspections
  python3 test_py_memunit_debugger_v6.py --no-sqlite  # disable SQLite
  python3 test_py_memunit_debugger_v6.py --replay     # enable replay storage (OFF by default)
  python3 test_py_memunit_debugger_v6.py --no-replay  # explicitly disable replay (default)
  python3 test_py_memunit_debugger_v6.py --replay-limit=50000  # bounded replay (implies --replay)
  python3 test_py_memunit_debugger_v6.py --bench=100000        # benchmark
  python3 test_py_memunit_debugger_v6.py --bench-cmp           # v4 vs v6 comparison
"""

import sqlite3
import time
import sys
import json
import threading
import queue as queue_mod
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Callable, List, Dict, Set, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.live import Live

console = Console()

# ---- Integer enums (P4 #15 — numeric everywhere, convert only at render) ----

KIND_STEP = 1
KIND_RESULT = 2
KIND_ERROR = 3
KIND_VARIABLE = 4
KIND_STATE = 5
KIND_TIMING = 6
KIND_IMPORT = 7

KIND_NAMES = {1: "step", 2: "result", 3: "error", 4: "variable", 5: "state", 6: "timing", 7: "import"}
KIND_ICONS = {1: "\u25b6", 2: "\u2713", 3: "\u2717", 4: "V", 5: "S", 6: "T", 7: "I"}
KIND_COLORS = {1: "cyan", 2: "green", 3: "bold red", 4: "yellow", 5: "magenta", 6: "blue", 7: "dim cyan"}


# ---- P4 #14 — Immutable Event with slots ----

@dataclass(frozen=True, slots=True)
class Event:
    id: int
    ts_ns: int
    source: str
    phase: str
    kind: int
    entity: str
    name: str
    value: Any
    severity: int
    payload: Any


# ---- P0 #1 — ReplayStore (bounded deque, configurable) ----

class ReplayStore:
    """Bounded replay storage. Uses deque(maxlen) for O(1) append.
    Supports unlimited, limited, or disabled replay."""

    def __init__(self, max_events=None, enabled=True):
        self.enabled = enabled
        self.max_events = max_events
        if enabled:
            self.events = deque(maxlen=max_events)
        else:
            self.events = None

    def append(self, ev):
        if self.enabled:
            self.events.append(ev)

    def all(self):
        if not self.enabled:
            return []
        return list(self.events)

    def count(self):
        return len(self.events) if self.enabled else 0

    def last(self):
        if not self.enabled or not self.events:
            return None
        return self.events[-1]

    def reversed(self):
        if not self.enabled:
            return []
        return reversed(self.events)

    def range(self, start=0, end=None):
        if not self.enabled:
            return []
        events = list(self.events)
        if end is None:
            return events[start:]
        return events[start:end]


# ---- P0 #2 — IndexStore (O(1) query indexes) ----

class IndexStore:
    """Maintains indexes during emit() for O(1) or O(k) queries.
    Indexes: by_kind, by_source, by_phase, by_entity, by_severity."""

    def __init__(self):
        self.by_kind = defaultdict(list)
        self.by_source = defaultdict(list)
        self.by_phase = defaultdict(list)
        self.by_entity = defaultdict(list)
        self.by_severity = defaultdict(list)

    def index(self, ev):
        self.by_kind[ev.kind].append(ev)
        self.by_source[ev.source].append(ev)
        self.by_phase[ev.phase].append(ev)
        self.by_entity[ev.entity].append(ev)
        if ev.severity > 0:
            self.by_severity[ev.severity].append(ev)

    def query_kind(self, kind):
        return self.by_kind.get(kind, [])

    def query_source(self, source):
        return self.by_source.get(source, [])

    def query_phase(self, phase):
        return self.by_phase.get(phase, [])

    def query_entity(self, entity):
        return self.by_entity.get(entity, [])

    def query_severity_above(self, threshold):
        result = []
        for sev, events in self.by_severity.items():
            if sev > threshold:
                result.extend(events)
        return result


# ---- P6 — StatsEngine (O(1) summaries, multiple counts) ----

class StatsEngine:
    """Maintains real-time statistics during emit(). All summaries are O(1)."""

    def __init__(self):
        self.kind_counts = defaultdict(int)
        self.source_counts = defaultdict(int)
        self.phase_counts = defaultdict(int)
        self.entity_counts = defaultdict(int)
        self.severity_counts = defaultdict(int)
        self.error_count = 0
        self.total = 0
        self.first_ts = None
        self.last_ts = None
        self.timing_values = []
        self.timing_labels = []

    def update(self, ev):
        self.total += 1
        self.kind_counts[ev.kind] += 1
        self.source_counts[ev.source] += 1
        self.phase_counts[ev.phase] += 1
        self.entity_counts[ev.entity] += 1
        if ev.severity > 0:
            self.severity_counts[ev.severity] += 1
            self.error_count += 1
        if self.first_ts is None:
            self.first_ts = ev.ts_ns
        self.last_ts = ev.ts_ns
        if ev.kind == KIND_TIMING and isinstance(ev.value, (int, float)):
            self.timing_values.append(ev.value)
            self.timing_labels.append(f"{ev.phase}/{ev.entity}")

    def summary(self):
        return {
            "total": self.total,
            "steps": self.kind_counts.get(KIND_STEP, 0),
            "results": self.kind_counts.get(KIND_RESULT, 0),
            "variables": self.kind_counts.get(KIND_VARIABLE, 0),
            "states": self.kind_counts.get(KIND_STATE, 0),
            "timings": self.kind_counts.get(KIND_TIMING, 0),
            "imports": self.kind_counts.get(KIND_IMPORT, 0),
            "errors": self.error_count,
            "duration_ms": (self.last_ts - self.first_ts) / 1e6 if self.first_ts and self.last_ts else 0,
        }

    def source_summary(self):
        return dict(self.source_counts)

    def timing_stats(self):
        if not self.timing_values:
            return None
        vals = self.timing_values
        total = sum(vals)
        return {
            "count": len(vals),
            "total_ms": total,
            "avg_ms": total / len(vals),
            "min_ms": min(vals),
            "max_ms": max(vals),
            "slowest": self.timing_labels[vals.index(max(vals))],
            "fastest": self.timing_labels[vals.index(min(vals))],
        }


# ---- P3 #12 — Consumer interface ----

class Consumer:
    """Base consumer. Override consume() to process events."""
    def consume(self, ev):
        pass
    def flush(self):
        pass
    def close(self):
        pass


# ---- P3 — ViewerConsumer (batched Rich rendering) ----

class ViewerConsumer(Consumer):
    """Buffers events and renders at 10Hz. Never blocks execution."""

    def __init__(self, config):
        self.config = config
        self.buffer = deque(maxlen=500)

    def consume(self, ev):
        self.buffer.append(ev)

    def drain(self, max_events=50):
        events = []
        while len(events) < max_events and self.buffer:
            events.append(self.buffer.popleft())
        return events

    def render_batch(self, events):
        for ev in events:
            if not self.config.show_errors and ev.kind == KIND_ERROR:
                continue
            if not self.config.show_results and ev.kind in (KIND_STEP, KIND_RESULT):
                continue
            if not self.config.show_variables and ev.kind == KIND_VARIABLE:
                continue
            if not self.config.show_state and ev.kind == KIND_STATE:
                continue
            if not self.config.show_timing and ev.kind == KIND_TIMING:
                continue
            color = KIND_COLORS.get(ev.kind, "white")
            icon = KIND_ICONS.get(ev.kind, "?")
            kind_name = KIND_NAMES.get(ev.kind, "?")
            ts_str = datetime.fromtimestamp(ev.ts_ns / 1e9).strftime("%H:%M:%S.%f")[:-3]
            val_str = self._format_value(ev.value)
            if ev.severity > 0:
                console.print(f"  [dim]{ts_str}[/dim] [{color}]{icon} #{ev.id:4d}[/{color}] [bold red]!{ev.severity}[/bold red] [{color}]{ev.source}/{ev.phase}/{ev.entity}[/] {ev.name}={val_str}")
            else:
                console.print(f"  [dim]{ts_str}[/dim] [{color}]{icon} #{ev.id:4d}[/{color}] [{color}]{ev.source}/{ev.phase}/{ev.entity}[/] {ev.name}={val_str}")

    def _format_value(self, value):
        if isinstance(value, float):
            return f"{value:.3f}ms"
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)

    def drain_and_render(self):
        events = self.drain(max_events=99999)
        if events:
            self.render_batch(events)

    def flush(self):
        self.drain_and_render()


# ---- P0 #3 — SQLiteConsumer (background thread, batched) ----

class SQLiteConsumer(Consumer):
    """SQLite archival in a background thread. Producer never blocks.
    Uses queue → worker thread → executemany → commit every batch_size."""

    INSERT_SQL = "INSERT INTO event (id, timestamp, source, phase, kind, entity, name, value, severity, payload) VALUES (?,?,?,?,?,?,?,?,?,?)"

    def __init__(self, db_path=":memory:", batch_size=500):
        self.db_path = db_path
        self.queue = queue_mod.Queue(maxsize=10000)
        self.batch_size = batch_size
        self.running = True
        self.db = None
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def _worker(self):
        self.db = sqlite3.connect(self.db_path)
        self.db.executescript("PRAGMA synchronous=OFF; PRAGMA journal_mode=OFF; PRAGMA temp_store=MEMORY; PRAGMA cache_size=-100000; PRAGMA locking_mode=EXCLUSIVE;")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS event (
                id INTEGER PRIMARY KEY,
                timestamp INTEGER,
                source TEXT,
                phase TEXT,
                kind INTEGER,
                entity TEXT,
                name TEXT,
                value TEXT,
                severity INTEGER DEFAULT 0,
                payload TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_event_kind ON event(kind);
            CREATE INDEX IF NOT EXISTS idx_event_source ON event(source);
        """)
        self.db.commit()
        batch = []
        while self.running or not self.queue.empty():
            try:
                ev = self.queue.get(timeout=0.1)
                batch.append(self._serialize(ev))
                if len(batch) >= self.batch_size:
                    self.db.executemany(self.INSERT_SQL, batch)
                    self.db.commit()
                    batch.clear()
            except queue_mod.Empty:
                if batch:
                    self.db.executemany(self.INSERT_SQL, batch)
                    self.db.commit()
                    batch.clear()
            except Exception:
                pass
        if batch:
            self.db.executemany(self.INSERT_SQL, batch)
            self.db.commit()
        if self.db:
            self.db.close()
            self.db = None

    def _serialize(self, ev):
        payload_str = json.dumps(ev.payload) if ev.payload is not None else None
        value_str = str(ev.value) if ev.value is not None else None
        return (ev.id, ev.ts_ns, ev.source, ev.phase, ev.kind, ev.entity, ev.name, value_str, ev.severity, payload_str)

    def consume(self, ev):
        try:
            self.queue.put_nowait(ev)
        except queue_mod.Full:
            pass

    def flush(self):
        self.running = False
        self.thread.join(timeout=5)

    def close(self):
        self.flush()
        # db is created and owned by worker thread, closed there too


# ---- P3 #13 — Dispatcher (fan-out to consumers) ----

class Dispatcher:
    """Fans out events to all registered consumers.
    Each consumer receives the event once."""

    def __init__(self):
        self.consumers = []

    def register(self, consumer):
        self.consumers.append(consumer)

    def dispatch(self, ev):
        for c in self.consumers:
            c.consume(ev)

    def flush_all(self):
        for c in self.consumers:
            c.flush()

    def close_all(self):
        for c in self.consumers:
            c.close()


# ---- P0/P3 — EventBus (core, with ReplayStore, IndexStore, StatsEngine, Dispatcher) ----

class EventBus:
    """Core event bus. Zero I/O on emit(). Fans out to consumers.
    Maintains replay store, query indexes, and stats engine.

    emit() cost: 1 namedtuple creation + 1 deque append + 5 dict list appends + 6 dict increments + N consumer calls
    No SQLite, no JSON, no string formatting, no datetime.
    """

    def __init__(self, replay_limit=None, replay_enabled=True, sqlite_consumer=None, viewer_consumer=None):
        self.next_id = 1
        self.replay = ReplayStore(max_events=replay_limit, enabled=replay_enabled)
        self.indexes = IndexStore()
        self.stats = StatsEngine()
        self.dispatcher = Dispatcher()
        if sqlite_consumer:
            self.dispatcher.register(sqlite_consumer)
        if viewer_consumer:
            self.dispatcher.register(viewer_consumer)
        self.sqlite_consumer = sqlite_consumer
        self.viewer_consumer = viewer_consumer

    def emit(self, source, phase, kind, entity="", name="", value=None, severity=0, payload=None):
        eid = self.next_id
        self.next_id += 1
        ev = Event(eid, time.time_ns(), source, phase, kind, entity, name, value, severity, payload)
        self.replay.append(ev)
        self.indexes.index(ev)
        self.stats.update(ev)
        self.dispatcher.dispatch(ev)
        return eid

    # P5 — Query engine with predicates
    def query(self, kind=None, source=None, phase=None, entity=None, severity_above=None, time_range=None, predicate=None):
        if kind is not None:
            candidates = self.indexes.query_kind(kind)
        elif source is not None:
            candidates = self.indexes.query_source(source)
        elif phase is not None:
            candidates = self.indexes.query_phase(phase)
        elif entity is not None:
            candidates = self.indexes.query_entity(entity)
        elif severity_above is not None:
            candidates = self.indexes.query_severity_above(severity_above)
        else:
            candidates = self.replay.all()

        result = []
        for ev in candidates:
            if kind is not None and ev.kind != kind:
                continue
            if source is not None and ev.source != source:
                continue
            if phase is not None and ev.phase != phase:
                continue
            if entity is not None and ev.entity != entity:
                continue
            if severity_above is not None and ev.severity <= severity_above:
                continue
            if time_range is not None:
                t_start, t_end = time_range
                if ev.ts_ns < t_start or ev.ts_ns > t_end:
                    continue
            if predicate is not None and not predicate(ev):
                continue
            result.append(ev)
        return result

    # P7 — Replay engine
    def replay_forward(self, start=0, end=None):
        return self.replay.range(start, end)

    def replay_reverse(self):
        return list(self.replay.reversed())

    def replay_filtered(self, kind=None, source=None, entity=None):
        return self.query(kind=kind, source=source, entity=entity)

    def replay_by_source(self, source):
        return self.indexes.query_source(source)

    def replay_by_entity(self, entity):
        return self.indexes.query_entity(entity)

    def count(self):
        return self.stats.total

    def summary(self):
        return self.stats.summary()

    def close(self):
        self.dispatcher.flush_all()
        self.dispatcher.close_all()


# ---- Configurator ----

class Configurator:
    LABELS = ["SILENT", "NORMAL", "DEBUG", "VERBOSE"]

    def __init__(self, verbosity=1):
        self.verbosity = verbosity
        self.show_errors = True
        self.show_payloads = verbosity >= 2
        self.show_results = verbosity >= 1
        self.show_variables = verbosity >= 2
        self.show_state = verbosity >= 2
        self.show_timing = verbosity >= 3

    def __repr__(self):
        return f"Configurator(verbosity={self.verbosity} {self.LABELS[self.verbosity]})"

    def set_verbosity(self, level):
        self.verbosity = level
        self.show_errors = True
        self.show_payloads = level >= 2
        self.show_results = level >= 1
        self.show_variables = level >= 2
        self.show_state = level >= 2
        self.show_timing = level >= 3

    def silence(self):
        self.set_verbosity(0)

    def verbose(self):
        self.set_verbosity(3)


# ---- EventInspector (queries EventBus indexes, not SQLite) ----

class EventInspector:
    """Inspects events via EventBus indexes. O(1) for kind/source lookups."""

    def __init__(self, bus):
        self.bus = bus

    def overview(self):
        errors = self.bus.query(kind=KIND_ERROR)
        results = self.bus.query(kind=KIND_RESULT)
        states = self.bus.query(kind=KIND_STATE)
        final_state = None
        for ev in self.bus.replay_reverse():
            if ev.kind == KIND_STATE:
                final_state = ev
                break
        return {"total": self.bus.count(), "errors": errors, "results": results, "states": states, "final_state": final_state}

    def errors(self):
        return self.bus.query(kind=KIND_ERROR)

    def replay(self):
        return self.bus.replay_forward()

    def profile(self):
        stats = self.bus.stats.timing_stats()
        timings = self.bus.query(kind=KIND_TIMING)
        return {"timings": timings, "analysis": stats}

    def debug(self):
        return {"variables": self.bus.query(kind=KIND_VARIABLE), "states": self.bus.query(kind=KIND_STATE)}

    def summary(self):
        return self.bus.summary()

    def sources(self):
        return self.bus.stats.source_summary()


# ---- ClassTester ----

class ClassTester:
    """Tests each class/method by querying EventBus indexes. O(k) per class."""

    def __init__(self, bus, inspector):
        self.bus = bus
        self.inspector = inspector

    def test_imports(self):
        facts = self.bus.query(kind=KIND_IMPORT)
        imports = [f.value for f in facts]
        passed = len(imports) > 0
        return {"name": "imports", "passed": passed, "count": len(imports), "items": imports, "detail": f"{len(imports)} imports found" if passed else "NO imports found"}

    def test_class(self, class_name):
        facts = self.bus.query(source=class_name)
        if not facts:
            return {"name": class_name, "passed": False, "tests": [], "detail": "NO facts produced by this class"}
        methods = {}
        for ev in facts:
            if ev.entity not in methods:
                methods[ev.entity] = {"facts": 0, "errors": 0, "results": 0, "timing": None, "variables": 0, "kinds": set()}
            m = methods[ev.entity]
            m["facts"] += 1
            m["kinds"].add(KIND_NAMES.get(ev.kind, "?"))
            if ev.severity > 0:
                m["errors"] += 1
            if ev.kind == KIND_RESULT:
                m["results"] += 1
            elif ev.kind == KIND_TIMING:
                m["timing"] = ev.value
            elif ev.kind == KIND_VARIABLE:
                m["variables"] += 1
        tests = []
        all_passed = True
        for method_name, m in sorted(methods.items()):
            method_tests = []
            t1 = m["facts"] > 0
            method_tests.append(("produced facts", t1, f"{m['facts']} facts"))
            t2 = m["errors"] == 0
            method_tests.append(("no errors", t2, f"{m['errors']} errors"))
            if not t2:
                all_passed = False
            t3 = m["results"] > 0
            method_tests.append(("produced result", t3, f"{m['results']} results"))
            t4 = m["timing"] is not None
            timing_str = f"{m['timing']:.3f}ms" if isinstance(m["timing"], float) else (m["timing"] or "missing")
            method_tests.append(("has timing", t4, timing_str))
            tests.append({"method": method_name, "passed": all(t for _, t, _ in method_tests), "checks": method_tests, "fact_count": m["facts"], "kinds": sorted(m["kinds"])})
        class_errors = sum(1 for f in facts if f.severity > 0)
        if class_errors > 0:
            all_passed = False
        return {"name": class_name, "passed": all_passed, "tests": tests, "fact_count": len(facts), "error_count": class_errors, "method_count": len(methods), "detail": f"{len(facts)} facts, {len(methods)} methods, {class_errors} errors"}

    def test_all(self):
        results = [("imports", self.test_imports())]
        classes = set(self.bus.stats.source_counts.keys())
        classes.discard("main")
        for cls in sorted(classes):
            results.append((cls, self.test_class(cls)))
        return results

    def test_errors(self):
        errors = self.inspector.errors()
        return {"name": "error_check", "passed": len(errors) == 0, "count": len(errors), "items": [(e.source, e.phase, e.name, e.value) for e in errors], "detail": f"{len(errors)} errors found" if errors else "no errors"}

    def test_state_consistency(self):
        states = self.bus.query(kind=KIND_STATE)
        state_names = {}
        for ev in states:
            if ev.name not in state_names:
                state_names[ev.name] = []
            state_names[ev.name].append(ev.value)
        conflicts = {}
        for name, values in state_names.items():
            unique = set(str(v) for v in values)
            if len(unique) > 1:
                conflicts[name] = values
        return {"name": "state_consistency", "passed": len(conflicts) == 0, "conflicts": conflicts, "state_count": len(states), "detail": f"{len(conflicts)} conflicting states" if conflicts else f"{len(states)} states, all consistent"}


# ---- P8 — EventViewer (multiple view modes) ----

class EventViewer:
    """Renders EventInspector data. Multiple view modes.
    Final report after execution. Live rendering via ViewerConsumer."""

    def __init__(self, inspector, configurator):
        self.inspector = inspector
        self.config = configurator
        self.bus = inspector.bus

    def _fmt_val(self, value):
        if isinstance(value, float):
            return f"{value:.3f}ms"
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)

    def render_table(self):
        s = self.inspector.summary()
        console.print()
        table = Table(title=f"[bold]Execution Report[/bold]  [dim]({self.config})[/dim]", box=box.ROUNDED, show_lines=True, title_style="bold cyan")
        table.add_column("#", style="dim", width=4)
        table.add_column("Source", style="cyan", width=10)
        table.add_column("Phase", style="magenta", width=14)
        table.add_column("Kind", width=10)
        table.add_column("Entity", style="yellow", width=18)
        table.add_column("Name", style="white", width=20)
        table.add_column("Value", width=30)
        table.add_column("Sev", justify="center", width=4)
        for ev in self.bus.replay_forward():
            color = KIND_COLORS.get(ev.kind, "white")
            icon = KIND_ICONS.get(ev.kind, "?")
            kind_name = KIND_NAMES.get(ev.kind, "?")
            sev_str = f"[bold red]!{ev.severity}[/bold red]" if ev.severity > 0 else "[dim]0[/dim]"
            kind_str = f"[{color}]{icon} {kind_name}[/{color}]"
            val_str = self._fmt_val(ev.value)[:30]
            table.add_row(str(ev.id), ev.source, ev.phase, kind_str, ev.entity, ev.name, val_str, sev_str)
        console.print(table)
        summary_table = Table(box=box.SIMPLE, show_header=False)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Count", style="bold")
        summary_table.add_row("Total Events", str(s["total"]))
        summary_table.add_row("Steps", str(s["steps"]))
        summary_table.add_row("Results", str(s["results"]))
        summary_table.add_row("Variables", str(s["variables"]))
        summary_table.add_row("States", str(s["states"]))
        summary_table.add_row("Timings", str(s["timings"]))
        summary_table.add_row("[bold red]Errors[/bold red]", f"[bold red]{s['errors']}[/bold red]")
        summary_table.add_row("[dim]Duration[/dim]", f"[dim]{s['duration_ms']:.1f}ms[/dim]")
        console.print(summary_table)
        console.print()

    def render_code_structure(self):
        events = self.bus.replay_forward()
        classes = {}
        imports = set()
        for ev in events:
            if ev.kind == KIND_IMPORT:
                imports.add(self._fmt_val(ev.value))
                continue
            if ev.source not in classes:
                classes[ev.source] = {}
            if ev.entity not in classes[ev.source]:
                classes[ev.source][ev.entity] = {"events": [], "count": 0, "errors": 0, "results": [], "timing": None, "phases": set()}
            entry = classes[ev.source][ev.entity]
            entry["count"] += 1
            entry["events"].append((ev.id, ev.kind, ev.name, ev.value, ev.severity))
            entry["phases"].add(ev.phase)
            if ev.severity > 0:
                entry["errors"] += 1
            if ev.kind == KIND_RESULT:
                entry["results"].append(f"{ev.name}={self._fmt_val(ev.value)}")
            elif ev.kind == KIND_ERROR:
                entry["results"].append(f"[bold red]{ev.name}: {self._fmt_val(ev.value)}[/bold red]")
            elif ev.kind == KIND_TIMING:
                entry["timing"] = ev.value
        console.print()
        console.print(Panel("\n".join(f"  [cyan]import[/cyan] {imp}" for imp in sorted(imports)) or "  [dim](none)[/dim]", title="[bold cyan]IMPORTS[/bold cyan]", border_style="cyan", padding=(0, 1)))
        for class_name in sorted(classes.keys()):
            methods = classes[class_name]
            method_lines = []
            for method_name in sorted(methods.keys()):
                m = methods[method_name]
                status_icon = "[green]\u2713[/green]" if m["errors"] == 0 else "[bold red]\u2717[/bold red]"
                err_str = f"[bold red]{m['errors']}[/bold red]" if m["errors"] > 0 else "[green]0[/green]"
                timing_str = f"[blue]{m['timing']:.3f}ms[/blue]" if isinstance(m["timing"], float) else ("[blue]" + str(m["timing"]) + "[/blue]" if m["timing"] else "[dim]--[/dim]")
                phases_str = ", ".join(sorted(m["phases"]))
                result_str = m["results"][-1] if m["results"] else "[dim](no result)[/dim]"
                method_lines.append(f"  {status_icon} [yellow]{method_name}[/yellow]  [dim]events={m['count']}[/dim]  [dim]errors={err_str}[/dim]  {timing_str}")
                method_lines.append(f"      [dim]phases: {phases_str}[/dim]")
                method_lines.append(f"      result: {result_str}")
                method_lines.append("")
            console.print(Panel("\n".join(method_lines), title=f"[bold green]CLASS: {class_name}[/bold green]", border_style="green", padding=(0, 1)))
        console.print()

    def render_execution_graph(self):
        events = self.bus.replay_forward()
        classes = {}
        for ev in events:
            if ev.source not in classes:
                classes[ev.source] = {}
            if ev.entity not in classes[ev.source]:
                classes[ev.source][ev.entity] = {"count": 0, "errors": 0, "result": None, "phase": ev.phase, "timing": None}
            m = classes[ev.source][ev.entity]
            m["count"] += 1
            if ev.severity > 0:
                m["errors"] += 1
            if ev.kind == KIND_RESULT:
                m["result"] = f"{ev.name}={self._fmt_val(ev.value)}"
            elif ev.kind == KIND_ERROR:
                m["result"] = f"{ev.name}: {self._fmt_val(ev.value)}"
            elif ev.kind == KIND_TIMING:
                m["timing"] = ev.value
        graph_lines = ["[bold cyan]EXECUTION GRAPH[/bold cyan]", ""]
        for class_name in sorted(classes.keys()):
            methods = classes[class_name]
            method_items = sorted(methods.keys())
            graph_lines.append(f"  [bold green]{class_name}[/bold green]")
            for i, method_name in enumerate(method_items):
                m = methods[method_name]
                is_last = (i == len(method_items) - 1)
                branch = "\u2514\u2500\u2500" if is_last else "\u251c\u2500\u2500"
                status = "[green]\u2713[/green]" if m["errors"] == 0 else "[bold red]\u2717[/bold red]"
                result = m["result"] or "(no result)"
                timing = f" [blue]{m['timing']:.3f}ms[/blue]" if isinstance(m["timing"], float) else ""
                graph_lines.append(f"  {branch} {status} [yellow]{method_name}[/yellow]{timing}")
                result_escaped = result.replace("[", "\\[")
                graph_lines.append(f"      [dim]\u2192 {result_escaped}[/dim]")
                if m["errors"] > 0:
                    graph_lines.append(f"      [bold red]! {m['errors']} error(s)[/bold red]")
            graph_lines.append("")
        graph_lines.append("[bold magenta]CALL EDGES:[/bold magenta]")
        prev_class = None
        for class_name in sorted(classes.keys()):
            if prev_class:
                graph_lines.append(f"  [dim]{prev_class} \u2500\u2500calls\u2500\u2500\u25b6 {class_name}[/dim]")
            prev_class = class_name
        console.print(Panel("\n".join(graph_lines), border_style="magenta", padding=(0, 1)))
        console.print()

    def render_overview(self):
        data = self.inspector.overview()
        panel_content = []
        panel_content.append(f"[cyan]Total events:[/cyan] {data['total']}")
        panel_content.append(f"[red]Errors:[/red] {len(data['errors'])}")
        panel_content.append(f"[green]Results:[/green] {len(data['results'])}")
        panel_content.append(f"[magenta]State changes:[/magenta] {len(data['states'])}")
        if data["errors"]:
            panel_content.append("\n[bold red]WHAT WENT WRONG:[/bold red]")
            for ev in data["errors"]:
                panel_content.append(f"  [red]- [{ev.phase}/{ev.entity}] {ev.name}: {self._fmt_val(ev.value)}[/red]")
        if data["final_state"]:
            ev = data["final_state"]
            panel_content.append(f"\n[bold green]FINAL STATE:[/bold green] {ev.name} = {self._fmt_val(ev.value)}")
        console.print(Panel("\n".join(panel_content), title="[bold]Event Inspector \u2014 Overview[/bold]", border_style="cyan"))

    def render_replay(self):
        events = self.inspector.replay()
        table = Table(title=f"[bold]Replay \u2014 {len(events)} events[/bold]", box=box.ROUNDED, title_style="bold blue")
        table.add_column("Time", style="dim", width=12)
        table.add_column("#", style="dim", width=4)
        table.add_column("Kind", width=10)
        table.add_column("Source/Phase/Entity", style="cyan", width=30)
        table.add_column("Detail", width=40)
        for ev in events:
            ts_str = datetime.fromtimestamp(ev.ts_ns / 1e9).strftime("%H:%M:%S.%f")[:-3]
            color = KIND_COLORS.get(ev.kind, "white")
            icon = KIND_ICONS.get(ev.kind, "?")
            kind_name = KIND_NAMES.get(ev.kind, "?")
            location = f"{ev.source}/{ev.phase}/{ev.entity}"
            detail = f"{ev.name}={self._fmt_val(ev.value)}" if ev.name else self._fmt_val(ev.value)
            if ev.severity > 0:
                detail = f"[bold red]!{ev.severity} {detail}[/bold red]"
            table.add_row(ts_str, str(ev.id), f"[{color}]{icon} {kind_name}[/{color}]", location, detail)
        console.print(table)

    def render_profile(self):
        data = self.inspector.profile()
        timings = data["timings"]
        if not timings:
            console.print(Panel("[yellow]No timing events recorded.[/yellow]", title="Profiler", border_style="yellow"))
            return
        table = Table(title="[bold]Timing Analysis[/bold]", box=box.ROUNDED, title_style="bold blue")
        table.add_column("#", style="dim", width=4)
        table.add_column("Phase/Entity", style="cyan", width=25)
        table.add_column("Duration", style="blue", width=12)
        for ev in timings:
            val_str = f"{ev.value:.3f}ms" if isinstance(ev.value, float) else str(ev.value)
            table.add_row(str(ev.id), f"{ev.phase}/{ev.entity}", val_str)
        console.print(table)
        if data["analysis"]:
            a = data["analysis"]
            console.print(Panel(
                f"[blue]Total:[/blue] {a['total_ms']:.2f}ms\n"
                f"[red]Slowest:[/red] {a['slowest']} at {a['max_ms']:.2f}ms\n"
                f"[green]Fastest:[/green] {a['fastest']} at {a['min_ms']:.2f}ms\n"
                f"[yellow]Average:[/yellow] {a['avg_ms']:.2f}ms\n"
                f"[dim]Count: {a['count']}[/dim]",
                title="[bold]Analysis[/bold]", border_style="blue"))

    def render_stats(self):
        s = self.bus.summary()
        src_counts = self.bus.stats.source_summary()
        console.print(Panel(
            f"[cyan]Total:[/cyan] {s['total']}  [dim]Duration: {s['duration_ms']:.1f}ms[/dim]\n"
            f"[green]Steps:[/green] {s['steps']}  [green]Results:[/green] {s['results']}  "
            f"[yellow]Variables:[/yellow] {s['variables']}  [magenta]States:[/magenta] {s['states']}  "
            f"[blue]Timings:[/blue] {s['timings']}  [red]Errors:[/red] {s['errors']}\n"
            f"\n[bold]By Source:[/bold]\n" +
            "\n".join(f"  {src}: {cnt}" for src, cnt in sorted(src_counts.items(), key=lambda x: -x[1])),
            title="[bold]Statistics Engine[/bold]", border_style="cyan"))

    def render_test_results(self, tester):
        console.print()
        console.print(Panel("[bold]CLASS TESTER \u2014 testing every class, method, import, and error[/bold]", border_style="bold yellow", title="[bold]TEST RESULTS[/bold]"))
        all_results = tester.test_all()
        total_passed = 0
        total_failed = 0
        for class_name, result in all_results:
            passed = result["passed"]
            icon = "[green]\u2713 PASS[/green]" if passed else "[bold red]\u2717 FAIL[/bold red]"
            if passed:
                total_passed += 1
            else:
                total_failed += 1
            if class_name == "imports":
                imp_lines = [f"  [green]\u2713[/green] [cyan]import[/cyan] {imp}" for imp in result.get("items", [])]
                console.print(Panel("\n".join(imp_lines) or "  [dim](none)[/dim]", title=f"{icon} [bold]IMPORTS[/bold]", border_style="green" if passed else "red", padding=(0, 1)))
                continue
            method_lines = []
            for t in result["tests"]:
                m_icon = "[green]\u2713[/green]" if t["passed"] else "[bold red]\u2717[/bold red]"
                method_lines.append(f"  {m_icon} [yellow]{t['method']}[/yellow]  [dim]({t['fact_count']} facts, kinds: {', '.join(t['kinds'])})[/dim]")
                for check_name, check_passed, check_detail in t["checks"]:
                    c_icon = "[green]\u2713[/green]" if check_passed else "[bold red]\u2717[/bold red]"
                    method_lines.append(f"      {c_icon} [dim]{check_name}: {check_detail}[/dim]")
                method_lines.append("")
            border = "green" if passed else "red"
            console.print(Panel("\n".join(method_lines), title=f"{icon} [bold]CLASS: {class_name}[/bold]  [dim]({result['detail']})[/dim]", border_style=border, padding=(0, 1)))
        error_test = tester.test_errors()
        state_test = tester.test_state_consistency()
        err_icon = "[green]\u2713 PASS[/green]" if error_test["passed"] else "[bold red]\u2717 FAIL[/bold red]"
        state_icon = "[green]\u2713 PASS[/green]" if state_test["passed"] else "[bold red]\u2717 FAIL[/bold red]"
        err_lines = [f"  {err_icon} [bold]Error Check[/bold] \u2014 {error_test['detail']}"]
        if not error_test["passed"]:
            for src, phase, name, value in error_test["items"]:
                err_lines.append(f"    [red]- [{src}/{phase}] {name}: {value}[/red]")
        err_lines.append(f"  {state_icon} [bold]State Consistency[/bold] \u2014 {state_test['detail']}")
        if not state_test["passed"]:
            for name, values in state_test["conflicts"].items():
                err_lines.append(f"    [red]- {name}: {values}[/red]")
        if error_test["passed"] and state_test["passed"]:
            total_passed += 2
        else:
            total_failed += (0 if error_test["passed"] else 1) + (0 if state_test["passed"] else 1)
        console.print(Panel("\n".join(err_lines), title="[bold]ERROR + STATE TESTS[/bold]", border_style="green" if error_test["passed"] and state_test["passed"] else "red", padding=(0, 1)))
        summary = Table(box=box.SIMPLE, show_header=False)
        summary.add_column("Metric", style="cyan")
        summary.add_column("Value", style="bold")
        summary.add_row("[green]Passed[/green]", f"[green]{total_passed}[/green]")
        summary.add_row("[red]Failed[/red]", f"[red]{total_failed}[/red]")
        summary.add_row("Total Tests", str(total_passed + total_failed))
        overall = "[green]ALL PASS[/green]" if total_failed == 0 else "[bold red]HAS FAILURES[/bold red]"
        summary.add_row("[bold]Overall[/bold]", overall)
        console.print(summary)
        console.print()

    def render_debug(self):
        data = self.inspector.debug()
        variables = data["variables"]
        states = data["states"]
        var_table = Table(title=f"[bold]Variables ({len(variables)})[/bold]", box=box.ROUNDED, title_style="bold yellow")
        var_table.add_column("#", style="dim", width=4)
        var_table.add_column("Phase", style="magenta", width=14)
        var_table.add_column("Name", style="yellow", width=25)
        var_table.add_column("Value", width=30)
        for ev in variables:
            var_table.add_row(str(ev.id), ev.phase, ev.name, self._fmt_val(ev.value))
        console.print(var_table)
        state_table = Table(title=f"[bold]State ({len(states)})[/bold]", box=box.ROUNDED, title_style="bold magenta")
        state_table.add_column("#", style="dim", width=4)
        state_table.add_column("Name", style="magenta", width=20)
        state_table.add_column("Value", width=25)
        state_table.add_column("Source", style="cyan", width=12)
        for ev in states:
            state_table.add_row(str(ev.id), ev.name, self._fmt_val(ev.value), ev.source)
        console.print(state_table)


# ---- Simulated Bloodhound Scan ----

def simulate_bloodhound_scan(bus, target_dir):
    """Simulates a Bloodhound scan. Uses native values (float timing, no str())."""

    bus.emit("main", "imports", KIND_IMPORT, entity="imports", value="sqlite3")
    bus.emit("main", "imports", KIND_IMPORT, entity="imports", value="time")
    bus.emit("main", "imports", KIND_IMPORT, entity="imports", value="rich.console")
    bus.emit("main", "imports", KIND_IMPORT, entity="imports", value="rich.table")
    bus.emit("main", "imports", KIND_IMPORT, entity="imports", value="json")

    t0 = time.time()
    bus.emit("EventBus", "init", KIND_STEP, entity="__init__", name="status", value="creating EventBus (deque + indexes + stats)")
    bus.emit("EventBus", "init", KIND_VARIABLE, entity="__init__", name="bus_engine", value="deque")
    bus.emit("EventBus", "init", KIND_VARIABLE, entity="__init__", name="mode", value="RAM+indexes")
    time.sleep(0.005)
    bus.emit("EventBus", "init", KIND_RESULT, entity="__init__", name="result", value="EventBus initialized")
    bus.emit("EventBus", "init", KIND_TIMING, entity="__init__", value=(time.time() - t0) * 1000)

    t0 = time.time()
    bus.emit("ReplayStore", "init", KIND_STEP, entity="__init__", name="status", value="creating bounded deque")
    bus.emit("ReplayStore", "init", KIND_VARIABLE, entity="__init__", name="storage", value="deque(maxlen)")
    time.sleep(0.003)
    bus.emit("ReplayStore", "init", KIND_RESULT, entity="__init__", name="result", value="replay store ready")
    bus.emit("ReplayStore", "init", KIND_TIMING, entity="__init__", value=(time.time() - t0) * 1000)

    t0 = time.time()
    bus.emit("IndexStore", "init", KIND_STEP, entity="__init__", name="status", value="creating query indexes")
    bus.emit("IndexStore", "init", KIND_VARIABLE, entity="__init__", name="indexes", value="kind/source/phase/entity/severity")
    time.sleep(0.002)
    bus.emit("IndexStore", "init", KIND_RESULT, entity="__init__", name="result", value="indexes ready (O(1) queries)")
    bus.emit("IndexStore", "init", KIND_TIMING, entity="__init__", value=(time.time() - t0) * 1000)

    t0 = time.time()
    bus.emit("StatsEngine", "init", KIND_STEP, entity="__init__", name="status", value="creating stats engine")
    bus.emit("StatsEngine", "init", KIND_VARIABLE, entity="__init__", name="counts", value="kind/source/phase/entity/severity")
    time.sleep(0.002)
    bus.emit("StatsEngine", "init", KIND_RESULT, entity="__init__", name="result", value="stats ready (O(1) summary)")
    bus.emit("StatsEngine", "init", KIND_TIMING, entity="__init__", value=(time.time() - t0) * 1000)

    t0 = time.time()
    bus.emit("Dispatcher", "init", KIND_STEP, entity="__init__", name="status", value="registering consumers")
    bus.emit("Dispatcher", "init", KIND_VARIABLE, entity="__init__", name="consumers", value="ViewerConsumer+SQLiteConsumer")
    time.sleep(0.002)
    bus.emit("Dispatcher", "init", KIND_RESULT, entity="__init__", name="result", value="dispatcher ready (fan-out)")
    bus.emit("Dispatcher", "init", KIND_TIMING, entity="__init__", value=(time.time() - t0) * 1000)

    t0 = time.time()
    bus.emit("Configurator", "config", KIND_STEP, entity="__init__", name="status", value="setting verbosity=1")
    bus.emit("Configurator", "config", KIND_VARIABLE, entity="__init__", name="verbosity", value=1)
    time.sleep(0.002)
    bus.emit("Configurator", "config", KIND_RESULT, entity="__init__", name="result", value="Configurator ready")
    bus.emit("Configurator", "config", KIND_TIMING, entity="__init__", value=(time.time() - t0) * 1000)

    bus.emit("Scanner", "init", KIND_STATE, entity="Run", name="scan_phase", value="starting")
    bus.emit("Scanner", "init", KIND_STATE, entity="Run", name="target_dir", value=target_dir)
    bus.emit("Scanner", "init", KIND_STATE, entity="Run", name="workspace", value="TestTrail")

    t0 = time.time()
    bus.emit("Scanner", "boot", KIND_STEP, entity="__init__", name="status", value="opening LMDB")
    bus.emit("Scanner", "boot", KIND_VARIABLE, entity="__init__", name="db_path", value="~/.bloodhound/bloodhound.mdb")
    bus.emit("Scanner", "boot", KIND_VARIABLE, entity="__init__", name="map_size", value="1GB")
    time.sleep(0.005)
    bus.emit("Scanner", "boot", KIND_RESULT, entity="__init__", name="result", value="LMDB opened")
    bus.emit("Scanner", "boot", KIND_TIMING, entity="__init__", value=(time.time() - t0) * 1000)

    t0 = time.time()
    bus.emit("Scanner", "scan", KIND_STEP, entity="walk_dir", name="target", value=target_dir)
    file_count = 0
    scent_count = 0
    error_count = 0
    fake_files = [("bh_main.c", "c", 207, 15), ("bh_db.c", "c", 1303, 120), ("bh_nose.c", "c", 855, 80), ("bh_query.c", "c", 311, 25), ("bloodhound.h", "c", 326, 30), ("Makefile", "makefile", 30, 0), ("README.md", "markdown", 141, 10)]
    for fname, lang, lines, scents in fake_files:
        t1 = time.time()
        bus.emit("Scanner", "scan", KIND_STEP, entity="process_file", name="file", value=fname)
        bus.emit("Scanner", "scan", KIND_VARIABLE, entity="process_file", name=f"{fname}_language", value=lang)
        bus.emit("Scanner", "scan", KIND_VARIABLE, entity="process_file", name=f"{fname}_lines", value=lines)
        bus.emit("Scanner", "scan", KIND_VARIABLE, entity="process_file", name=f"{fname}_scents", value=scents)
        file_count += 1
        scent_count += scents
        if fname == "Makefile":
            bus.emit("Scanner", "scan", KIND_ERROR, entity="extract_scents", name="UNSUPPORTED_LANGUAGE", value=f"Cannot extract scents from {lang} files", severity=1, payload={"file": fname, "language": lang})
            error_count += 1
            bus.emit("Scanner", "scan", KIND_RESULT, entity="process_file", name="result", value="skipped (unsupported)", severity=1)
        else:
            bus.emit("Scanner", "scan", KIND_RESULT, entity="process_file", name="result", value=f"extracted {scents} scents")
        time.sleep(0.003)
        bus.emit("Scanner", "scan", KIND_TIMING, entity="process_file", value=(time.time() - t1) * 1000)
    bus.emit("Scanner", "scan", KIND_STATE, entity="walk_dir", name="file_count", value=file_count)
    bus.emit("Scanner", "scan", KIND_STATE, entity="walk_dir", name="scent_count", value=scent_count)
    bus.emit("Scanner", "scan", KIND_STATE, entity="walk_dir", name="error_count", value=error_count)
    bus.emit("Scanner", "scan", KIND_TIMING, entity="walk_dir", value=(time.time() - t0) * 1000)

    t0 = time.time()
    bus.emit("Nose", "relationships", KIND_STEP, entity="build_same_file", name="status", value="building same_file edges")
    rel_count = scent_count - 1
    bus.emit("Nose", "relationships", KIND_VARIABLE, entity="build_same_file", name="same_file_count", value=rel_count)
    time.sleep(0.005)
    bus.emit("Nose", "relationships", KIND_RESULT, entity="build_same_file", name="result", value=f"{rel_count} same_file edges")
    bus.emit("Nose", "relationships", KIND_TIMING, entity="build_same_file", value=(time.time() - t0) * 1000)

    t0 = time.time()
    bus.emit("Nose", "relationships", KIND_STEP, entity="build_imports", name="status", value="building import edges")
    bus.emit("Nose", "relationships", KIND_VARIABLE, entity="build_imports", name="import_count", value=45)
    time.sleep(0.003)
    bus.emit("Nose", "relationships", KIND_RESULT, entity="build_imports", name="result", value="45 import edges")
    bus.emit("Nose", "relationships", KIND_TIMING, entity="build_imports", value=(time.time() - t0) * 1000)

    t0 = time.time()
    bus.emit("Nose", "relationships", KIND_STEP, entity="build_calls", name="status", value="building call edges")
    bus.emit("Nose", "relationships", KIND_VARIABLE, entity="build_calls", name="call_count", value=30)
    time.sleep(0.003)
    bus.emit("Nose", "relationships", KIND_RESULT, entity="build_calls", name="result", value="30 call edges")
    bus.emit("Nose", "relationships", KIND_TIMING, entity="build_calls", value=(time.time() - t0) * 1000)
    bus.emit("Nose", "relationships", KIND_STATE, entity="Run", name="relationship_count", value=rel_count + 45 + 30)

    t0 = time.time()
    bus.emit("Scanner", "finalize", KIND_STEP, entity="log_observations", name="count", value=file_count)
    time.sleep(0.003)
    bus.emit("Scanner", "finalize", KIND_RESULT, entity="log_observations", name="result", value="observations stored")
    bus.emit("Scanner", "finalize", KIND_TIMING, entity="log_observations", value=(time.time() - t0) * 1000)
    bus.emit("Scanner", "finalize", KIND_STATE, entity="Run", name="scan_phase", value="complete")
    bus.emit("Scanner", "finalize", KIND_RESULT, entity="summary", name="files", value=file_count)
    bus.emit("Scanner", "finalize", KIND_RESULT, entity="summary", name="scents", value=scent_count)
    bus.emit("Scanner", "finalize", KIND_RESULT, entity="summary", name="relationships", value=rel_count + 45 + 30)
    bus.emit("Scanner", "finalize", KIND_RESULT, entity="summary", name="errors", value=error_count)
    if error_count > 0:
        bus.emit("Scanner", "finalize", KIND_ERROR, entity="check_errors", name="HAS_ERRORS", value=f"Scan completed with {error_count} errors", severity=2)


# ---- Benchmark ----

def run_benchmark(n_events):
    bus = EventBus(replay_enabled=True)
    t0 = time.time_ns()
    for i in range(n_events):
        bus.emit("Bench", "bench", KIND_STEP, entity="method_a", name="iter", value=i)
    elapsed_ns = time.time_ns() - t0
    elapsed_ms = elapsed_ns / 1e6
    per_us = elapsed_ns / n_events / 1000
    print(f"\nEventBus v6 Benchmark \u2014 {n_events:,} events")
    print(f"  Total time:    {elapsed_ms:.2f}ms")
    print(f"  Per event:     {per_us:.3f}\u00b5s")
    print(f"  Events/sec:    {n_events / elapsed_ms * 1000:,.0f}")
    print(f"  RAM events:    {bus.count():,}")
    s = bus.summary()
    print(f"  Steps:         {s['steps']:,}")
    t_stats = bus.stats.timing_stats()
    if t_stats:
        print(f"  Timing stats:  {t_stats['count']} timings, avg={t_stats['avg_ms']:.3f}ms")
    bus.close()
    print()


def run_benchmark_cmp(n_events):
    """Compare v4 (SQLite per-event) vs v6 (EventBus)."""
    print(f"\nBenchmark Comparison \u2014 {n_events:,} events\n")

    # v4
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from test_py_memunit_debugger import LiveState
        ls = LiveState()
        t0 = time.time_ns()
        for i in range(n_events):
            ls.emit("Bench", "bench", "step", entity="m", name="i", value=str(i))
        v4_ns = time.time_ns() - t0
        v4_ms = v4_ns / 1e6
        v4_us = v4_ns / n_events / 1000
        ls.close()
        print(f"  v4 (SQLite per-event):  {v4_ms:.1f}ms | {v4_us:.3f}\u00b5s/ev | {n_events/v4_ms*1000:,.0f} ev/s")
    except Exception as e:
        print(f"  v4 (SQLite per-event):  ERROR: {e}")
        v4_ms = None

    # v6 pure RAM
    bus = EventBus(replay_enabled=True)
    t0 = time.time_ns()
    for i in range(n_events):
        bus.emit("Bench", "bench", KIND_STEP, entity="m", name="i", value=i)
    v6_ns = time.time_ns() - t0
    v6_ms = v6_ns / 1e6
    v6_us = v6_ns / n_events / 1000
    bus.close()
    print(f"  v6 (EventBus pure RAM): {v6_ms:.1f}ms | {v6_us:.3f}\u00b5s/ev | {n_events/v6_ms*1000:,.0f} ev/s")

    # v6 with SQLite background thread
    sqlite_c = SQLiteConsumer()
    bus2 = EventBus(replay_enabled=True, sqlite_consumer=sqlite_c)
    t0 = time.time_ns()
    for i in range(n_events):
        bus2.emit("Bench", "bench", KIND_STEP, entity="m", name="i", value=i)
    v6sql_ns = time.time_ns() - t0
    bus2.close()
    v6sql_ms = v6sql_ns / 1e6
    v6sql_us = v6sql_ns / n_events / 1000
    print(f"  v6 (EventBus + SQLite): {v6sql_ms:.1f}ms | {v6sql_us:.3f}\u00b5s/ev | {n_events/v6sql_ms*1000:,.0f} ev/s")

    if v4_ms:
        speedup = v4_ms / v6_ms
        print(f"\n  Speedup v6 vs v4: {speedup:.1f}x (pure RAM)")
        speedup_sql = v4_ms / v6sql_ms
        print(f"  Speedup v6 vs v4: {speedup_sql:.1f}x (with SQLite background)")
    print()


# ---- Main ----

import os

def main():
    args = sys.argv[1:]
    verbosity = 1
    mode_flag = None
    use_sqlite = True
    replay_enabled = False
    replay_limit = None
    bench_n = None
    bench_cmp = False

    for a in args:
        if a == "--no-sqlite":
            use_sqlite = False
        elif a == "--replay":
            replay_enabled = True
        elif a == "--no-replay":
            replay_enabled = False
        elif a.startswith("--replay-limit="):
            replay_limit = int(a.split("=")[1])
            replay_enabled = True
        elif a == "--bench":
            bench_n = 100000
        elif a.startswith("--bench="):
            bench_n = int(a.split("=")[1])
        elif a == "--bench-cmp":
            bench_cmp = True
        elif a.startswith("--"):
            mode_flag = a
        else:
            verbosity = int(a)

    if bench_n:
        run_benchmark(bench_n)
        return

    if bench_cmp:
        run_benchmark_cmp(10000)
        return

    config = Configurator(verbosity)
    viewer_c = ViewerConsumer(config)
    sqlite_c = SQLiteConsumer() if use_sqlite else None

    bus = EventBus(
        replay_limit=replay_limit,
        replay_enabled=replay_enabled,
        sqlite_consumer=sqlite_c,
        viewer_consumer=viewer_c,
    )
    inspector = EventInspector(bus)
    viewer = EventViewer(inspector, config)
    tester = ClassTester(bus, inspector)

    console.print(Panel(
        f"[bold cyan]BLOODHOUND TRACE ENGINE v6[/bold cyan]\n"
        f"[dim]EventBus + ReplayStore + IndexStore + StatsEngine + Dispatcher + Consumers[/dim]\n"
        f"[dim]Pattern: Class \u2192 EventBus.emit() \u2192 Dispatcher \u2192 {', '.join(c.__class__.__name__ for c in bus.dispatcher.consumers)}[/dim]\n"
        f"[dim]Config: {config} | SQLite: {'ON (background thread)' if use_sqlite else 'OFF'} | Replay: {'OFF' if not replay_enabled else ('LIMITED=' + str(replay_limit) if replay_limit else 'UNLIMITED')}[/dim]",
        border_style="cyan"
    ))

    if mode_flag != "--table":
        console.print(f"\n[bold green]\u25b6 LIVE STREAM \u2014 events as they happen:[/bold green]\n")

    simulate_bloodhound_scan(bus, "core/Dom_Bloodhound/")

    viewer_c.drain_and_render()

    s = inspector.summary()
    console.print(f"\n[bold]\u2713 SCAN COMPLETE[/bold] \u2014 [cyan]{s['total']}[/cyan] events captured "
                  f"(steps={s['steps']} results={s['results']} vars={s['variables']} "
                  f"states={s['states']} timings={s['timings']} [red]errors={s['errors']}[/red]) "
                  f"[dim]duration={s['duration_ms']:.1f}ms[/dim]\n")

    if mode_flag == "--overview":
        viewer.render_overview()
    elif mode_flag == "--replay":
        viewer.render_replay()
    elif mode_flag == "--profile":
        viewer.render_profile()
    elif mode_flag == "--debug":
        viewer.render_debug()
    elif mode_flag == "--test":
        viewer.render_test_results(tester)
    elif mode_flag == "--stats":
        viewer.render_stats()
    elif mode_flag == "--table":
        viewer.render_table()
        viewer.render_code_structure()
        viewer.render_execution_graph()
        viewer.render_test_results(tester)
    elif mode_flag == "--all":
        viewer.render_stats()
        viewer.render_table()
        viewer.render_code_structure()
        viewer.render_execution_graph()
        viewer.render_test_results(tester)
        viewer.render_overview()
        viewer.render_profile()
        viewer.render_debug()
        viewer.render_replay()
    else:
        viewer.render_code_structure()
        viewer.render_execution_graph()
        viewer.render_test_results(tester)

    bus.close()


if __name__ == "__main__":
    main()
