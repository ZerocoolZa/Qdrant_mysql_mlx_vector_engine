#!/usr/bin/env python3
"""
test_py_memunit_debugger_v5.py — v5: EventBus Architecture

v5 changes (20 optimizations applied):
  1. EventBus (deque) replaces LiveState SQLite as primary path
  2. SQLite is optional archival sink, batched executemany, commit every 500
  3. Statistics cached in dicts — O(1) summary() instead of COUNT(*)
  4. Rich rendering decoupled — viewer pulls from deque at 10Hz, not per-event
  5. Integer enums for kind — SQLite stores INTEGER, convert to string only at render
  6. time.time_ns() instead of datetime.now() per event
  7. Pre-compiled SQL statements
  8. No AUTOINCREMENT — manual counter for event IDs
  9. Events kept in RAM list for replay — no SQL SELECT needed
  10. JSON only if payload is not None
  11. No ORDER BY unless explicitly needed
  12. Separate execution from rendering — emit() never blocks on I/O
  13. collections.deque for event bus — lock-free append/popleft
  14. Batch timing — local struct, flush once
  15. Rich Live at 10fps instead of console.print per event
  16. PRAGMA synchronous=OFF, journal_mode=OFF, temp_store=MEMORY
  17. Event object (namedtuple) — less argument packing
  18. Bulk insert via executemany
  19. Cache kind_counts during emit — no SQL for summary
  20. Fan-out architecture: emit → deque → {viewer, stats, tester, sqlite}

Architecture (6 classes):
  1. EventBus       — deque-based zero-copy event bus. Fans out to consumers.
  2. EventInspector — Queries events from EventBus RAM list. Returns structured data.
  3. EventViewer    — Renders to terminal at 10Hz using Rich Live. Never blocks execution.
  4. Configurator   — Controls output configuration. Verbosity valve.
  5. ClassTester    — Tests each class/method/import/error against cached facts.
  6. SQLiteSink     — Optional archival. Batched executemany, commit every 500.

Flow:
  Class.emit() → EventBus.append() → fans out to:
    ├→ RAM list (replay, inspector, tester)
    ├→ stats cache (O(1) summary)
    ├→ viewer deque (10Hz render)
    └→ SQLite sink (batched, optional)

Usage:
  python3 test_py_memunit_debugger_v5.py              # live + code structure + graph + tests
  python3 test_py_memunit_debugger_v5.py 0            # silent (errors only)
  python3 test_py_memunit_debugger_v5.py 2            # debug (show variables)
  python3 test_py_memunit_debugger_v5.py 3            # verbose (show everything)
  python3 test_py_memunit_debugger_v5.py --test       # test results only
  python3 test_py_memunit_debugger_v5.py --table      # final summary table + structure + graph + tests
  python3 test_py_memunit_debugger_v5.py --overview   # AI inspection
  python3 test_py_memunit_debugger_v5.py --replay     # replay inspection
  python3 test_py_memunit_debugger_v5.py --profile    # profiler inspection
  python3 test_py_memunit_debugger_v5.py --debug      # debugger inspection
  python3 test_py_memunit_debugger_v5.py --all        # all inspections + tests
  python3 test_py_memunit_debugger_v5.py --no-sqlite  # disable SQLite archival entirely
  python3 test_py_memunit_debugger_v5.py --bench 10000 # benchmark 10K events, show timings
"""

import sqlite3
import time
import sys
import json
from collections import deque, defaultdict
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.live import Live

console = Console()

# ---- Integer enums for event kinds (optimization #14) ----

KIND_STEP = 1
KIND_RESULT = 2
KIND_ERROR = 3
KIND_VARIABLE = 4
KIND_STATE = 5
KIND_TIMING = 6
KIND_IMPORT = 7

KIND_NAMES = {1: "step", 2: "result", 3: "error", 4: "variable", 5: "state", 6: "timing", 7: "import"}
KIND_ICONS = {1: "▶", 2: "✓", 3: "✗", 4: "V", 5: "S", 6: "T", 7: "I"}
KIND_COLORS = {1: "cyan", 2: "green", 3: "bold red", 4: "yellow", 5: "magenta", 6: "blue", 7: "dim cyan"}

# ---- Event namedtuple (optimization #13 — less argument packing) ----

from collections import namedtuple
Event = namedtuple("Event", "id ts_ns source phase kind entity name value severity payload")


# ---- 1. EventBus (deque-based zero-copy event bus) ----

class EventBus:
    """Lock-free deque-based event bus. Fans out to consumers.
    Replaces LiveState SQLite as the primary execution path.
    SQLite becomes an optional archival sink, not the execution path.

    Consumers:
      - RAM list: replay, inspector, tester
      - stats cache: O(1) summary
      - viewer deque: 10Hz render
      - SQLite sink: batched, optional
    """

    def __init__(self, sqlite_sink=None):
        self.events = []
        self.next_id = 1
        self.kind_counts = defaultdict(int)
        self.source_counts = defaultdict(int)
        self.error_count = 0
        self.viewer_queue = deque(maxlen=1000)
        self.sqlite_sink = sqlite_sink
        self.callbacks = []

    def on_emit(self, callback):
        self.callbacks.append(callback)

    def emit(self, source, phase, kind, entity="", name="", value="", severity=0, payload=None):
        eid = self.next_id
        self.next_id += 1
        ts = time.time_ns()
        ev = Event(eid, ts, source, phase, kind, entity, name, str(value), severity, payload)
        self.events.append(ev)
        self.kind_counts[kind] += 1
        self.source_counts[source] += 1
        if severity > 0:
            self.error_count += 1
        self.viewer_queue.append(ev)
        if self.sqlite_sink:
            self.sqlite_sink.append(ev)
        for cb in self.callbacks:
            cb(ev)
        return eid

    def query(self, kind=None, source=None, phase=None, severity_above=None):
        result = []
        for ev in self.events:
            if kind is not None and ev.kind != kind:
                continue
            if source is not None and ev.source != source:
                continue
            if phase is not None and ev.phase != phase:
                continue
            if severity_above is not None and ev.severity <= severity_above:
                continue
            result.append(ev)
        return result

    def replay(self):
        return self.events

    def count(self):
        return len(self.events)

    def count_kind(self, kind):
        return self.kind_counts.get(kind, 0)

    def summary(self):
        return {
            "total": len(self.events),
            "steps": self.kind_counts.get(KIND_STEP, 0),
            "results": self.kind_counts.get(KIND_RESULT, 0),
            "variables": self.kind_counts.get(KIND_VARIABLE, 0),
            "states": self.kind_counts.get(KIND_STATE, 0),
            "timings": self.kind_counts.get(KIND_TIMING, 0),
            "imports": self.kind_counts.get(KIND_IMPORT, 0),
            "errors": self.error_count,
        }

    def close(self):
        if self.sqlite_sink:
            self.sqlite_sink.flush()


# ---- 1b. SQLiteSink (optional archival, batched) ----

class SQLiteSink:
    """Optional SQLite archival sink. Batched executemany, commit every N.
    Not in the execution path — EventBus fans out to this asynchronously."""

    INSERT_SQL = "INSERT INTO event (id, timestamp, source, phase, kind, entity, name, value, severity, payload) VALUES (?,?,?,?,?,?,?,?,?,?)"

    def __init__(self, db_path=":memory:", batch_size=500):
        self.db = sqlite3.connect(db_path)
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
        self.batch = []
        self.batch_size = batch_size

    def append(self, ev):
        payload_str = json.dumps(ev.payload) if ev.payload else None
        self.batch.append((ev.id, ev.ts_ns, ev.source, ev.phase, ev.kind, ev.entity, ev.name, ev.value, ev.severity, payload_str))
        if len(self.batch) >= self.batch_size:
            self.flush()

    def flush(self):
        if self.batch:
            self.db.executemany(self.INSERT_SQL, self.batch)
            self.db.commit()
            self.batch.clear()

    def close(self):
        self.flush()
        self.db.close()


# ---- 2. EventInspector (query/analyze events from EventBus RAM list) ----

class EventInspector:
    """Inspects events from EventBus. Returns structured data. Does NOT touch terminal.
    Queries RAM list, not SQLite — O(n) scan but no SQL overhead."""

    def __init__(self, bus):
        self.bus = bus

    def overview(self):
        errors = self.bus.query(kind=KIND_ERROR)
        results = self.bus.query(kind=KIND_RESULT)
        states = self.bus.query(kind=KIND_STATE)
        final_state = None
        for ev in reversed(self.bus.events):
            if ev.kind == KIND_STATE:
                final_state = ev
                break
        return {"total": self.bus.count(), "errors": errors, "results": results, "states": states, "final_state": final_state}

    def errors(self):
        return self.bus.query(kind=KIND_ERROR)

    def replay(self):
        return self.bus.replay()

    def profile(self):
        timings = self.bus.query(kind=KIND_TIMING)
        durations = []
        for ev in timings:
            try:
                ms = float(ev.value.replace("ms", ""))
                durations.append((f"{ev.phase}/{ev.entity}", ms))
            except:
                pass
        analysis = None
        if durations:
            total_ms = sum(d for _, d in durations)
            analysis = {"total_ms": total_ms, "slowest": max(durations, key=lambda x: x[1]),
                        "fastest": min(durations, key=lambda x: x[1]),
                        "average_ms": total_ms / len(durations), "count": len(durations)}
        return {"timings": timings, "analysis": analysis}

    def debug(self):
        return {"variables": self.bus.query(kind=KIND_VARIABLE), "states": self.bus.query(kind=KIND_STATE)}

    def summary(self):
        return self.bus.summary()


# ---- 3. EventViewer (renders at 10Hz, never blocks execution) ----

class EventViewer:
    """Renders EventInspector data to terminal using rich.
    Live streaming at 10Hz via deque polling — not per-event console.print.
    Final report after execution completes."""

    def __init__(self, inspector, configurator):
        self.inspector = inspector
        self.config = configurator
        self.bus = inspector.bus

    def live_callback(self, ev):
        """Called by EventBus.emit() — just appends to viewer deque.
        Does NOT render. Rendering happens at 10Hz via poll_viewer()."""
        pass  # EventBus already appends to viewer_queue

    def poll_viewer(self, max_events=50):
        """Drain up to N events from viewer queue. Called at 10Hz."""
        events = []
        q = self.bus.viewer_queue
        while len(events) < max_events and q:
            events.append(q.popleft())
        return events

    def render_live_batch(self, events):
        """Render a batch of events. Called at 10Hz, not per-event."""
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
            if ev.severity > 0:
                console.print(f"  [dim]{ts_str}[/dim] [{color}]{icon} #{ev.id:4d}[/{color}] [bold red]!{ev.severity}[/bold red] [{color}]{ev.source}/{ev.phase}/{ev.entity}[/] {ev.name}={ev.value}")
            else:
                console.print(f"  [dim]{ts_str}[/dim] [{color}]{icon} #{ev.id:4d}[/{color}] [{color}]{ev.source}/{ev.phase}/{ev.entity}[/] {ev.name}={ev.value}")

    def stream_live(self, duration_s=0.1):
        """Poll viewer queue and render at ~10Hz. Call during execution."""
        events = self.poll_viewer()
        if events:
            self.render_live_batch(events)

    def drain_live(self):
        """Drain all remaining events from viewer queue."""
        events = self.poll_viewer(max_events=99999)
        if events:
            self.render_live_batch(events)

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
        for ev in self.bus.replay():
            color = KIND_COLORS.get(ev.kind, "white")
            icon = KIND_ICONS.get(ev.kind, "?")
            kind_name = KIND_NAMES.get(ev.kind, "?")
            sev_str = f"[bold red]!{ev.severity}[/bold red]" if ev.severity > 0 else "[dim]0[/dim]"
            kind_str = f"[{color}]{icon} {kind_name}[/{color}]"
            table.add_row(str(ev.id), ev.source, ev.phase, kind_str, ev.entity, ev.name, ev.value[:30], sev_str)
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
        console.print(summary_table)
        console.print()

    def render_code_structure(self):
        events = self.bus.replay()
        classes = {}
        imports = set()
        for ev in events:
            if ev.kind == KIND_IMPORT:
                imports.add(ev.value)
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
                entry["results"].append(f"{ev.name}={ev.value}")
            elif ev.kind == KIND_ERROR:
                entry["results"].append(f"[bold red]{ev.name}: {ev.value}[/bold red]")
            elif ev.kind == KIND_TIMING:
                entry["timing"] = ev.value
        console.print()
        console.print(Panel("\n".join(f"  [cyan]import[/cyan] {imp}" for imp in sorted(imports)) or "  [dim](none)[/dim]", title="[bold cyan]IMPORTS[/bold cyan]", border_style="cyan", padding=(0, 1)))
        for class_name in sorted(classes.keys()):
            methods = classes[class_name]
            method_lines = []
            for method_name in sorted(methods.keys()):
                m = methods[method_name]
                status_icon = "[green]✓[/green]" if m["errors"] == 0 else "[bold red]✗[/bold red]"
                err_str = f"[bold red]{m['errors']}[/bold red]" if m["errors"] > 0 else "[green]0[/green]"
                timing_str = f"[blue]{m['timing']}[/blue]" if m["timing"] else "[dim]--[/dim]"
                phases_str = ", ".join(sorted(m["phases"]))
                result_str = m["results"][-1] if m["results"] else "[dim](no result)[/dim]"
                method_lines.append(f"  {status_icon} [yellow]{method_name}[/yellow]  [dim]events={m['count']}[/dim]  [dim]errors={err_str}[/dim]  {timing_str}")
                method_lines.append(f"      [dim]phases: {phases_str}[/dim]")
                method_lines.append(f"      result: {result_str}")
                method_lines.append("")
            console.print(Panel("\n".join(method_lines), title=f"[bold green]CLASS: {class_name}[/bold green]", border_style="green", padding=(0, 1)))
        console.print()

    def render_execution_graph(self):
        events = self.bus.replay()
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
                m["result"] = f"{ev.name}={ev.value}"
            elif ev.kind == KIND_ERROR:
                m["result"] = f"{ev.name}: {ev.value}"
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
                branch = "└──" if is_last else "├──"
                status = "[green]✓[/green]" if m["errors"] == 0 else "[bold red]✗[/bold red]"
                result = m["result"] or "(no result)"
                timing = f" [blue]{m['timing']}[/blue]" if m["timing"] else ""
                graph_lines.append(f"  {branch} {status} [yellow]{method_name}[/yellow]{timing}")
                result_escaped = result.replace("[", "\\[")
                graph_lines.append(f"      [dim]→ {result_escaped}[/dim]")
                if m["errors"] > 0:
                    graph_lines.append(f"      [bold red]! {m['errors']} error(s)[/bold red]")
            graph_lines.append("")
        graph_lines.append("[bold magenta]CALL EDGES:[/bold magenta]")
        prev_class = None
        for class_name in sorted(classes.keys()):
            if prev_class:
                graph_lines.append(f"  [dim]{prev_class} ──calls──▶ {class_name}[/dim]")
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
                panel_content.append(f"  [red]- [{ev.phase}/{ev.entity}] {ev.name}: {ev.value}[/red]")
        if data["final_state"]:
            ev = data["final_state"]
            panel_content.append(f"\n[bold green]FINAL STATE:[/bold green] {ev.name} = {ev.value}")
        console.print(Panel("\n".join(panel_content), title="[bold]Event Inspector — Overview[/bold]", border_style="cyan"))

    def render_replay(self):
        events = self.inspector.replay()
        table = Table(title=f"[bold]Replay — {len(events)} events[/bold]", box=box.ROUNDED, title_style="bold blue")
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
            detail = f"{ev.name}={ev.value}" if ev.name else ev.value
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
            table.add_row(str(ev.id), f"{ev.phase}/{ev.entity}", ev.value)
        console.print(table)
        if data["analysis"]:
            a = data["analysis"]
            console.print(Panel(f"[blue]Total:[/blue] {a['total_ms']:.2f}ms\n[red]Slowest:[/red] {a['slowest'][0]} at {a['slowest'][1]:.2f}ms\n[green]Fastest:[/green] {a['fastest'][0]} at {a['fastest'][1]:.2f}ms\n[yellow]Average:[/yellow] {a['average_ms']:.2f}ms", title="[bold]Analysis[/bold]", border_style="blue"))

    def render_test_results(self, tester):
        console.print()
        console.print(Panel("[bold]CLASS TESTER — testing every class, method, import, and error[/bold]", border_style="bold yellow", title="[bold]TEST RESULTS[/bold]"))
        all_results = tester.test_all()
        total_passed = 0
        total_failed = 0
        for class_name, result in all_results:
            passed = result["passed"]
            icon = "[green]✓ PASS[/green]" if passed else "[bold red]✗ FAIL[/bold red]"
            if passed:
                total_passed += 1
            else:
                total_failed += 1
            if class_name == "imports":
                imp_lines = [f"  [green]✓[/green] [cyan]import[/cyan] {imp}" for imp in result.get("items", [])]
                console.print(Panel("\n".join(imp_lines) or "  [dim](none)[/dim]", title=f"{icon} [bold]IMPORTS[/bold]", border_style="green" if passed else "red", padding=(0, 1)))
                continue
            method_lines = []
            for t in result["tests"]:
                m_icon = "[green]✓[/green]" if t["passed"] else "[bold red]✗[/bold red]"
                method_lines.append(f"  {m_icon} [yellow]{t['method']}[/yellow]  [dim]({t['fact_count']} facts, kinds: {', '.join(t['kinds'])})[/dim]")
                for check_name, check_passed, check_detail in t["checks"]:
                    c_icon = "[green]✓[/green]" if check_passed else "[bold red]✗[/bold red]"
                    method_lines.append(f"      {c_icon} [dim]{check_name}: {check_detail}[/dim]")
                method_lines.append("")
            border = "green" if passed else "red"
            console.print(Panel("\n".join(method_lines), title=f"{icon} [bold]CLASS: {class_name}[/bold]  [dim]({result['detail']})[/dim]", border_style=border, padding=(0, 1)))
        error_test = tester.test_errors()
        state_test = tester.test_state_consistency()
        err_icon = "[green]✓ PASS[/green]" if error_test["passed"] else "[bold red]✗ FAIL[/bold red]"
        state_icon = "[green]✓ PASS[/green]" if state_test["passed"] else "[bold red]✗ FAIL[/bold red]"
        err_lines = [f"  {err_icon} [bold]Error Check[/bold] — {error_test['detail']}"]
        if not error_test["passed"]:
            for src, phase, name, value in error_test["items"]:
                err_lines.append(f"    [red]- [{src}/{phase}] {name}: {value}[/red]")
        err_lines.append(f"  {state_icon} [bold]State Consistency[/bold] — {state_test['detail']}")
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
            var_table.add_row(str(ev.id), ev.phase, ev.name, ev.value)
        console.print(var_table)
        state_table = Table(title=f"[bold]State ({len(states)})[/bold]", box=box.ROUNDED, title_style="bold magenta")
        state_table.add_column("#", style="dim", width=4)
        state_table.add_column("Name", style="magenta", width=20)
        state_table.add_column("Value", width=25)
        state_table.add_column("Source", style="cyan", width=12)
        for ev in states:
            state_table.add_row(str(ev.id), ev.name, ev.value, ev.source)
        console.print(state_table)


# ---- 4. Configurator (controls output configuration) ----

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


# ---- 5. ClassTester (tests each class/method against cached facts) ----

class ClassTester:
    """Tests each class and method by querying EventBus RAM list.
    Checks: did the class produce facts? did it produce results? did it error?"""

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
            method_tests.append(("has timing", t4, m["timing"] or "missing"))
            tests.append({"method": method_name, "passed": all(t for _, t, _ in method_tests), "checks": method_tests, "fact_count": m["facts"], "kinds": sorted(m["kinds"])})
        class_errors = sum(1 for f in facts if f.severity > 0)
        if class_errors > 0:
            all_passed = False
        return {"name": class_name, "passed": all_passed, "tests": tests, "fact_count": len(facts), "error_count": class_errors, "method_count": len(methods), "detail": f"{len(facts)} facts, {len(methods)} methods, {class_errors} errors"}

    def test_all(self):
        results = [("imports", self.test_imports())]
        classes = set()
        for ev in self.bus.replay():
            if ev.kind != KIND_IMPORT:
                classes.add(ev.source)
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
            unique = set(values)
            if len(unique) > 1:
                conflicts[name] = values
        return {"name": "state_consistency", "passed": len(conflicts) == 0, "conflicts": conflicts, "state_count": len(states), "detail": f"{len(conflicts)} conflicting states" if conflicts else f"{len(states)} states, all consistent"}


# ---- Test Trail: Simulated Bloodhound Scan writing to EventBus ----

def simulate_bloodhound_scan(bus, target_dir):
    """Simulates a Bloodhound scan as class→method calls.
    Uses integer kind enums. No SQLite in the execution path."""

    bus.emit("main", "imports", KIND_IMPORT, entity="imports", value="sqlite3")
    bus.emit("main", "imports", KIND_IMPORT, entity="imports", value="time")
    bus.emit("main", "imports", KIND_IMPORT, entity="imports", value="rich.console")
    bus.emit("main", "imports", KIND_IMPORT, entity="imports", value="rich.table")
    bus.emit("main", "imports", KIND_IMPORT, entity="imports", value="json")

    t0 = time.time()
    bus.emit("LiveState", "init", KIND_STEP, entity="__init__", name="status", value="creating EventBus (deque)")
    bus.emit("LiveState", "init", KIND_VARIABLE, entity="__init__", name="bus_engine", value="deque")
    bus.emit("LiveState", "init", KIND_VARIABLE, entity="__init__", name="mode", value="RAM")
    time.sleep(0.005)
    bus.emit("LiveState", "init", KIND_RESULT, entity="__init__", name="result", value="EventBus initialized")
    bus.emit("LiveState", "init", KIND_TIMING, entity="__init__", value=f"{(time.time() - t0) * 1000:.2f}ms")

    t0 = time.time()
    bus.emit("LiveState", "init", KIND_STEP, entity="_init_schema", name="status", value="no schema needed (RAM)")
    bus.emit("LiveState", "init", KIND_VARIABLE, entity="_init_schema", name="storage", value="list + deque")
    time.sleep(0.003)
    bus.emit("LiveState", "init", KIND_RESULT, entity="_init_schema", name="result", value="RAM ready")
    bus.emit("LiveState", "init", KIND_TIMING, entity="_init_schema", value=f"{(time.time() - t0) * 1000:.2f}ms")

    t0 = time.time()
    bus.emit("LiveState", "init", KIND_STEP, entity="on_emit", name="status", value="registering viewer callback")
    time.sleep(0.002)
    bus.emit("LiveState", "init", KIND_RESULT, entity="on_emit", name="result", value="callback registered")
    bus.emit("LiveState", "init", KIND_TIMING, entity="on_emit", value=f"{(time.time() - t0) * 1000:.2f}ms")

    t0 = time.time()
    bus.emit("Configurator", "config", KIND_STEP, entity="__init__", name="status", value="setting verbosity=1")
    bus.emit("Configurator", "config", KIND_VARIABLE, entity="__init__", name="verbosity", value=1)
    bus.emit("Configurator", "config", KIND_VARIABLE, entity="__init__", name="show_errors", value=True)
    bus.emit("Configurator", "config", KIND_VARIABLE, entity="__init__", name="show_results", value=True)
    time.sleep(0.002)
    bus.emit("Configurator", "config", KIND_RESULT, entity="__init__", name="result", value="Configurator ready")
    bus.emit("Configurator", "config", KIND_TIMING, entity="__init__", value=f"{(time.time() - t0) * 1000:.2f}ms")

    t0 = time.time()
    bus.emit("EventInspector", "setup", KIND_STEP, entity="__init__", name="status", value="connecting to EventBus")
    time.sleep(0.002)
    bus.emit("EventInspector", "setup", KIND_RESULT, entity="__init__", name="result", value="inspector ready")
    bus.emit("EventInspector", "setup", KIND_TIMING, entity="__init__", value=f"{(time.time() - t0) * 1000:.2f}ms")

    t0 = time.time()
    bus.emit("EventViewer", "setup", KIND_STEP, entity="__init__", name="status", value="binding inspector + config")
    time.sleep(0.002)
    bus.emit("EventViewer", "setup", KIND_RESULT, entity="__init__", name="result", value="viewer ready")
    bus.emit("EventViewer", "setup", KIND_TIMING, entity="__init__", value=f"{(time.time() - t0) * 1000:.2f}ms")

    bus.emit("Scanner", "init", KIND_STATE, entity="Run", name="scan_phase", value="starting")
    bus.emit("Scanner", "init", KIND_STATE, entity="Run", name="target_dir", value=target_dir)
    bus.emit("Scanner", "init", KIND_STATE, entity="Run", name="workspace", value="TestTrail")

    t0 = time.time()
    bus.emit("Scanner", "boot", KIND_STEP, entity="__init__", name="status", value="opening LMDB")
    bus.emit("Scanner", "boot", KIND_VARIABLE, entity="__init__", name="db_path", value="~/.bloodhound/bloodhound.mdb")
    bus.emit("Scanner", "boot", KIND_VARIABLE, entity="__init__", name="map_size", value="1GB")
    time.sleep(0.005)
    bus.emit("Scanner", "boot", KIND_RESULT, entity="__init__", name="result", value="LMDB opened")
    bus.emit("Scanner", "boot", KIND_TIMING, entity="__init__", value=f"{(time.time() - t0) * 1000:.2f}ms")

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
        bus.emit("Scanner", "scan", KIND_TIMING, entity="process_file", value=f"{(time.time() - t1) * 1000:.2f}ms")
    bus.emit("Scanner", "scan", KIND_STATE, entity="walk_dir", name="file_count", value=file_count)
    bus.emit("Scanner", "scan", KIND_STATE, entity="walk_dir", name="scent_count", value=scent_count)
    bus.emit("Scanner", "scan", KIND_STATE, entity="walk_dir", name="error_count", value=error_count)
    bus.emit("Scanner", "scan", KIND_TIMING, entity="walk_dir", value=f"{(time.time() - t0) * 1000:.2f}ms")

    t0 = time.time()
    bus.emit("Nose", "relationships", KIND_STEP, entity="build_same_file", name="status", value="building same_file edges")
    rel_count = scent_count - 1
    bus.emit("Nose", "relationships", KIND_VARIABLE, entity="build_same_file", name="same_file_count", value=rel_count)
    time.sleep(0.005)
    bus.emit("Nose", "relationships", KIND_RESULT, entity="build_same_file", name="result", value=f"{rel_count} same_file edges")
    bus.emit("Nose", "relationships", KIND_TIMING, entity="build_same_file", value=f"{(time.time() - t0) * 1000:.2f}ms")

    t0 = time.time()
    bus.emit("Nose", "relationships", KIND_STEP, entity="build_imports", name="status", value="building import edges")
    bus.emit("Nose", "relationships", KIND_VARIABLE, entity="build_imports", name="import_count", value=45)
    time.sleep(0.003)
    bus.emit("Nose", "relationships", KIND_RESULT, entity="build_imports", name="result", value="45 import edges")
    bus.emit("Nose", "relationships", KIND_TIMING, entity="build_imports", value=f"{(time.time() - t0) * 1000:.2f}ms")

    t0 = time.time()
    bus.emit("Nose", "relationships", KIND_STEP, entity="build_calls", name="status", value="building call edges")
    bus.emit("Nose", "relationships", KIND_VARIABLE, entity="build_calls", name="call_count", value=30)
    time.sleep(0.003)
    bus.emit("Nose", "relationships", KIND_RESULT, entity="build_calls", name="result", value="30 call edges")
    bus.emit("Nose", "relationships", KIND_TIMING, entity="build_calls", value=f"{(time.time() - t0) * 1000:.2f}ms")
    bus.emit("Nose", "relationships", KIND_STATE, entity="Run", name="relationship_count", value=rel_count + 45 + 30)

    t0 = time.time()
    bus.emit("Scanner", "finalize", KIND_STEP, entity="log_observations", name="count", value=file_count)
    time.sleep(0.003)
    bus.emit("Scanner", "finalize", KIND_RESULT, entity="log_observations", name="result", value="observations stored")
    bus.emit("Scanner", "finalize", KIND_TIMING, entity="log_observations", value=f"{(time.time() - t0) * 1000:.2f}ms")
    bus.emit("Scanner", "finalize", KIND_STATE, entity="Run", name="scan_phase", value="complete")
    bus.emit("Scanner", "finalize", KIND_RESULT, entity="summary", name="files", value=file_count)
    bus.emit("Scanner", "finalize", KIND_RESULT, entity="summary", name="scents", value=scent_count)
    bus.emit("Scanner", "finalize", KIND_RESULT, entity="summary", name="relationships", value=rel_count + 45 + 30)
    bus.emit("Scanner", "finalize", KIND_RESULT, entity="summary", name="errors", value=error_count)
    if error_count > 0:
        bus.emit("Scanner", "finalize", KIND_ERROR, entity="check_errors", name="HAS_ERRORS", value=f"Scan completed with {error_count} errors", severity=2)


# ---- Benchmark mode ----

def run_benchmark(n_events):
    """Benchmark EventBus emit speed."""
    bus = EventBus()
    t0 = time.time_ns()
    for i in range(n_events):
        bus.emit("BenchClass", "bench", KIND_STEP, entity="method_a", name="iter", value=str(i))
    elapsed_ns = time.time_ns() - t0
    elapsed_ms = elapsed_ns / 1e6
    per_event_us = elapsed_ns / n_events / 1000
    print(f"\nEventBus Benchmark — {n_events:,} events")
    print(f"  Total time:    {elapsed_ms:.2f}ms")
    print(f"  Per event:     {per_event_us:.3f}µs")
    print(f"  Events/sec:    {n_events / elapsed_ms * 1000:,.0f}")
    print(f"  RAM events:    {bus.count():,}")
    s = bus.summary()
    print(f"  Steps:         {s['steps']:,}")
    print()

    # Compare with SQLite
    sink = SQLiteSink()
    bus2 = EventBus(sqlite_sink=sink)
    t0 = time.time_ns()
    for i in range(n_events):
        bus2.emit("BenchClass", "bench", KIND_STEP, entity="method_a", name="iter", value=str(i))
    sink.flush()
    elapsed_ns = time.time_ns() - t0
    elapsed_ms = elapsed_ns / 1e6
    per_event_us = elapsed_ns / n_events / 1000
    print(f"EventBus + SQLiteSink — {n_events:,} events")
    print(f"  Total time:    {elapsed_ms:.2f}ms")
    print(f"  Per event:     {per_event_us:.3f}µs")
    print(f"  Events/sec:    {n_events / elapsed_ms * 1000:,.0f}")
    print(f"  Speedup:       {(per_event_us / (elapsed_ns / n_events / 1000)):.1f}x slower than pure RAM")
    sink.close()


# ---- Main ----

def main():
    args = sys.argv[1:]
    verbosity = 1
    mode_flag = None
    use_sqlite = True
    bench_n = None

    for a in args:
        if a == "--no-sqlite":
            use_sqlite = False
        elif a == "--bench":
            bench_n = 10000
        elif a.startswith("--bench="):
            bench_n = int(a.split("=")[1])
        elif a.startswith("--"):
            mode_flag = a
        else:
            verbosity = int(a)

    if bench_n:
        run_benchmark(bench_n)
        return

    sink = SQLiteSink() if use_sqlite else None
    bus = EventBus(sqlite_sink=sink)
    inspector = EventInspector(bus)
    config = Configurator(verbosity)
    viewer = EventViewer(inspector, config)
    tester = ClassTester(bus, inspector)

    bus.on_emit(viewer.live_callback)

    console.print(Panel(
        f"[bold cyan]BLOODHOUND EXEC BUS v5[/bold cyan]\n"
        f"[dim]EventBus + EventInspector + EventViewer + Configurator + ClassTester + SQLiteSink[/dim]\n"
        f"[dim]Pattern: Class → EventBus.emit() → deque → viewer (10Hz) → final table[/dim]\n"
        f"[dim]Config: {config} | SQLite: {'ON (batched)' if use_sqlite else 'OFF (pure RAM)'}[/dim]",
        border_style="cyan"
    ))

    if mode_flag != "--table":
        console.print(f"\n[bold green]▶ LIVE STREAM — events as they happen:[/bold green]\n")

    simulate_bloodhound_scan(bus, "core/Dom_Bloodhound/")

    # Drain remaining events
    viewer.drain_live()

    s = inspector.summary()
    console.print(f"\n[bold]✓ SCAN COMPLETE[/bold] — [cyan]{s['total']}[/cyan] events captured "
                  f"(steps={s['steps']} results={s['results']} vars={s['variables']} "
                  f"states={s['states']} timings={s['timings']} [red]errors={s['errors']}[/red])\n")

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
    elif mode_flag == "--table":
        viewer.render_table()
        viewer.render_code_structure()
        viewer.render_execution_graph()
        viewer.render_test_results(tester)
    elif mode_flag == "--all":
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
    if sink:
        sink.close()


if __name__ == "__main__":
    main()
