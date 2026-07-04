#!/usr/bin/env python3
"""
test_py_memunit_debugger.py  —  v4: LiveState + EventInspector + EventViewer + Configurator + ClassTester

v4 changes:
  - Live streaming: events show in colorful table AS THEY HAPPEN, not after completion
  - Colorful rich table: class/method/kind/result in inspectable rows
  - Each class and method gets its own report row
  - Per-function capture: each function emits events, table shows them live
  - ClassTester: tests every class, method, import, and error against LiveState facts

Architecture (5 distinct classes, each with its own job):

  1. LiveState       — SQLite :memory: runtime blackboard. Captures ALL execution reality.
  2. EventInspector  — Queries/analyzes events from LiveState. Returns structured data.
  3. EventViewer     — Renders to terminal using rich tables. Live streaming + final report.
  4. Configurator    — Controls output configuration. Verbosity valve.
  5. ClassTester     — Tests each class/method/import/error by querying LiveState facts.

Flow:
  Class.Run() → LiveState.emit() → EventViewer.live_print() (during execution)
                            → EventInspector.query() → EventViewer.render_table() (after)
                            → ClassTester.test_all() → EventViewer.render_test_results() (after)

Usage:
  python3 test_py_memunit_debugger.py              # live + code structure + graph + tests
  python3 test_py_memunit_debugger.py 0            # silent (errors only)
  python3 test_py_memunit_debugger.py 2            # debug (show variables)
  python3 test_py_memunit_debugger.py 3            # verbose (show everything)
  python3 test_py_memunit_debugger.py --test       # test results only
  python3 test_py_memunit_debugger.py --table      # final summary table + structure + graph + tests
  python3 test_py_memunit_debugger.py --overview   # AI inspection
  python3 test_py_memunit_debugger.py --replay     # replay inspection
  python3 test_py_memunit_debugger.py --profile    # profiler inspection
  python3 test_py_memunit_debugger.py --debug      # debugger inspection
  python3 test_py_memunit_debugger.py --all        # all inspections + tests
"""

import sqlite3
import time
import sys
import json
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.live import Live

console = Console()

# ---- 1. LiveState (SQLite :memory: runtime blackboard) ----

class LiveState:
    """In-RAM SQLite runtime blackboard. Every component writes facts here.
    Not storage — a runtime blackboard. Not a database — a command bus with queryable state.
    Supports live callbacks — when an event is emitted, viewers are notified immediately."""

    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self._init_schema()
        self._live_callbacks = []

    def _init_schema(self):
        self.db.executescript("""
            CREATE TABLE event (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                source TEXT,
                phase TEXT,
                kind TEXT,
                entity TEXT,
                name TEXT,
                value TEXT,
                severity INTEGER DEFAULT 0,
                payload TEXT,
                parentId INTEGER
            );
            CREATE INDEX idx_event_kind ON event(kind);
            CREATE INDEX idx_event_phase ON event(phase);
            CREATE INDEX idx_event_severity ON event(severity);
            CREATE INDEX idx_event_source ON event(source);
        """)
        self.db.commit()

    def on_emit(self, callback):
        """Register a live callback. Called immediately when emit() is called."""
        self._live_callbacks.append(callback)

    def emit(self, source, phase, kind, entity="", name="", value="", severity=0, payload=None, parentId=None):
        """Write a fact to the blackboard. I produced this. I observed this. I failed here.
        Notifies all live callbacks immediately — enables streaming output during execution."""
        cursor = self.db.execute(
            "INSERT INTO event (timestamp, source, phase, kind, entity, name, value, severity, payload, parentId) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (time.time(), source, phase, kind, entity, name, str(value), severity,
             json.dumps(payload) if payload else None, parentId)
        )
        self.db.commit()
        eid = cursor.lastrowid
        for cb in self._live_callbacks:
            cb(eid, source, phase, kind, entity, name, str(value), severity, payload, parentId)

    def query(self, where="1=1", params=()):
        if "ORDER BY" in where.upper():
            stmt = "SELECT id, timestamp, source, phase, kind, entity, name, value, severity, payload, parentId FROM event WHERE " + where
        else:
            stmt = "SELECT id, timestamp, source, phase, kind, entity, name, value, severity, payload, parentId FROM event WHERE " + where + " ORDER BY id"
        return self.db.execute(stmt, params).fetchall()

    def query_kind(self, kind):
        return self.query("kind = ?", (kind,))

    def query_phase(self, phase):
        return self.query("phase = ?", (phase,))

    def query_severity_above(self, level):
        return self.query("severity > ?", (level,))

    def count(self, where="1=1", params=()):
        stmt = "SELECT COUNT(*) FROM event WHERE " + where
        return self.db.execute(stmt, params).fetchone()[0]

    def count_kind(self, kind):
        return self.count("kind = ?", (kind,))

    def close(self):
        self.db.close()


# ---- 2. EventInspector (query/analyze events from LiveState) ----

class EventInspector:
    """Inspects events from LiveState. Returns structured data. Does NOT touch terminal.
    Different inspection modes = different queries against the same event table."""

    def __init__(self, live_state):
        self.ls = live_state

    def overview(self):
        """AI-style: what happened and what went wrong?"""
        return {
            "total": self.ls.count(),
            "errors": self.ls.query_kind("error"),
            "results": self.ls.query_kind("result"),
            "states": self.ls.query_kind("state"),
            "final_state": self.ls.query("kind = ? AND name = ? ORDER BY id DESC LIMIT 1", ("state", "scan_phase")),
        }

    def errors(self):
        """All error events."""
        return self.ls.query_kind("error")

    def replay(self):
        """All events in order. For replaying execution."""
        return self.ls.query("1=1 ORDER BY id")

    def profile(self):
        """Timing events with analysis."""
        timings = self.ls.query_kind("timing")
        durations = []
        for eid, ts, src, phase, kind, entity, name, value, sev, payload, pid in timings:
            try:
                ms = float(value.replace("ms", ""))
                durations.append((f"{phase}/{entity}", ms))
            except:
                pass
        analysis = None
        if durations:
            total_ms = sum(d for _, d in durations)
            analysis = {
                "total_ms": total_ms,
                "slowest": max(durations, key=lambda x: x[1]),
                "fastest": min(durations, key=lambda x: x[1]),
                "average_ms": total_ms / len(durations),
                "count": len(durations),
            }
        return {"timings": timings, "analysis": analysis}

    def debug(self):
        """Variables + state for debugging."""
        return {
            "variables": self.ls.query_kind("variable"),
            "states": self.ls.query_kind("state"),
        }

    def summary(self):
        """Quick counts by kind."""
        return {
            "total": self.ls.count(),
            "steps": self.ls.count_kind("step"),
            "results": self.ls.count_kind("result"),
            "variables": self.ls.count_kind("variable"),
            "states": self.ls.count_kind("state"),
            "timings": self.ls.count_kind("timing"),
            "errors": self.ls.count_kind("error"),
        }


# ---- 3. EventViewer (renders to terminal — the ONLY class that touches stdout) ----

class EventViewer:
    """Renders EventInspector data to terminal using rich tables.
    The only class that touches stdout.
    Supports live streaming during execution + final summary table after."""

    KIND_COLORS = {
        "step": "cyan",
        "result": "green",
        "error": "bold red",
        "variable": "yellow",
        "state": "magenta",
        "timing": "blue",
    }

    KIND_ICONS = {
        "step": "▶",
        "result": "✓",
        "error": "✗",
        "variable": "V",
        "state": "S",
        "timing": "T",
    }

    def __init__(self, inspector, configurator):
        self.inspector = inspector
        self.config = configurator
        self._live_rows = []

    def live_callback(self, eid, source, phase, kind, entity, name, value, severity, payload, parentId):
        """Called by LiveState.emit() during execution. Streams events live."""
        if not self.config.show_errors and kind == "error":
            return
        if not self.config.show_results and kind in ("step", "result"):
            return
        if not self.config.show_variables and kind == "variable":
            return
        if not self.config.show_state and kind == "state":
            return
        if not self.config.show_timing and kind == "timing":
            return

        color = self.KIND_COLORS.get(kind, "white")
        icon = self.KIND_ICONS.get(kind, "?")
        ts_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        if severity > 0:
            console.print(f"  [dim]{ts_str}[/dim] [{color}]{icon} #{eid:3d}[/{color}] [bold red]!{severity}[/bold red] [{color}]{source}/{phase}/{entity}[/] {name}={value}")
        else:
            console.print(f"  [dim]{ts_str}[/dim] [{color}]{icon} #{eid:3d}[/{color}] [{color}]{source}/{phase}/{entity}[/] {name}={value}")

    def render_table(self):
        """Final summary table — class/method/kind/result in colorful rows."""
        s = self.inspector.summary()

        console.print()
        table = Table(
            title=f"[bold]Execution Report[/bold]  [dim]({self.config})[/dim]",
            box=box.ROUNDED,
            show_lines=True,
            title_style="bold cyan",
        )

        table.add_column("#", style="dim", width=4)
        table.add_column("Source", style="cyan", width=10)
        table.add_column("Phase", style="magenta", width=14)
        table.add_column("Kind", width=10)
        table.add_column("Entity", style="yellow", width=18)
        table.add_column("Name", style="white", width=20)
        table.add_column("Value", width=30)
        table.add_column("Sev", justify="center", width=4)

        events = self.inspector.replay()
        for eid, ts, src, phase, kind, entity, name, value, sev, payload, pid in events:
            color = self.KIND_COLORS.get(kind, "white")
            icon = self.KIND_ICONS.get(kind, "?")
            sev_str = f"[bold red]!{sev}[/bold red]" if sev > 0 else "[dim]0[/dim]"
            kind_str = f"[{color}]{icon} {kind}[/{color}]"
            table.add_row(str(eid), src, phase, kind_str, entity, name, value[:30], sev_str)

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
        """Code-structure report: imports → class → methods → next class → methods.
        Each method is testable — shows events, errors, result, timing.
        Layout mirrors a code file."""
        events = self.inspector.replay()

        classes = {}
        imports = set()
        for eid, ts, src, phase, kind, entity, name, value, sev, payload, pid in events:
            if kind == "import":
                imports.add(value)
                continue
            if src not in classes:
                classes[src] = {}
            if entity not in classes[src]:
                classes[src][entity] = {"events": [], "count": 0, "errors": 0, "results": [], "timing": None, "phases": set()}
            entry = classes[src][entity]
            entry["count"] += 1
            entry["events"].append((eid, kind, name, value, sev))
            entry["phases"].add(phase)
            if sev > 0:
                entry["errors"] += 1
            if kind == "result":
                entry["results"].append(f"{name}={value}")
            elif kind == "error":
                entry["results"].append(f"[bold red]{name}: {value}[/bold red]")
            elif kind == "timing":
                entry["timing"] = value

        console.print()

        # --- IMPORTS section ---
        console.print(Panel(
            "\n".join(f"  [cyan]import[/cyan] {imp}" for imp in sorted(imports)) or "  [dim](none)[/dim]",
            title="[bold cyan]IMPORTS[/bold cyan]",
            border_style="cyan",
            padding=(0, 1)
        ))

        # --- Each CLASS with its METHODS ---
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

                method_lines.append(f"  {status_icon} [yellow]{method_name}[/yellow]"
                                    f"  [dim]events={m['count']}[/dim]"
                                    f"  [dim]errors={err_str}[/dim]"
                                    f"  {timing_str}")
                method_lines.append(f"      [dim]phases: {phases_str}[/dim]")
                method_lines.append(f"      result: {result_str}")
                method_lines.append("")

            console.print(Panel(
                "\n".join(method_lines),
                title=f"[bold green]CLASS: {class_name}[/bold green]",
                border_style="green",
                padding=(0, 1)
            ))

        console.print()

    def render_execution_graph(self):
        """Execution graph — ASCII tree showing method call flow.
        Each class → method → result, with edges showing calls."""
        events = self.inspector.replay()

        classes = {}
        for eid, ts, src, phase, kind, entity, name, value, sev, payload, pid in events:
            if src not in classes:
                classes[src] = {}
            if entity not in classes[src]:
                classes[src][entity] = {"count": 0, "errors": 0, "result": None, "phase": phase, "timing": None}
            m = classes[src][entity]
            m["count"] += 1
            if sev > 0:
                m["errors"] += 1
            if kind == "result":
                m["result"] = f"{name}={value}"
            elif kind == "error":
                m["result"] = f"{name}: {value}"
            elif kind == "timing":
                m["timing"] = value

        graph_lines = []
        graph_lines.append("[bold cyan]EXECUTION GRAPH[/bold cyan]")
        graph_lines.append("")

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

                result_escaped = result.replace("[", "\[")
                graph_lines.append(f"      [dim]→ {result_escaped}[/dim]")

                if m["errors"] > 0:
                    graph_lines.append(f"      [bold red]! {m['errors']} error(s)[/bold red]")

            graph_lines.append("")

        # Add cross-class edges
        graph_lines.append("[bold magenta]CALL EDGES:[/bold magenta]")
        prev_class = None
        for class_name in sorted(classes.keys()):
            if prev_class:
                graph_lines.append(f"  [dim]{prev_class} ──calls──▶ {class_name}[/dim]")
            prev_class = class_name

        console.print(Panel(
            "\n".join(graph_lines),
            border_style="magenta",
            padding=(0, 1)
        ))
        console.print()

    def render_overview(self):
        """AI inspection — what happened and what went wrong?"""
        data = self.inspector.overview()

        panel_content = []
        panel_content.append(f"[cyan]Total events:[/cyan] {data['total']}")
        panel_content.append(f"[red]Errors:[/red] {len(data['errors'])}")
        panel_content.append(f"[green]Results:[/green] {len(data['results'])}")
        panel_content.append(f"[magenta]State changes:[/magenta] {len(data['states'])}")

        if data["errors"]:
            panel_content.append("\n[bold red]WHAT WENT WRONG:[/bold red]")
            for eid, ts, src, phase, kind, entity, name, value, sev, payload, pid in data["errors"]:
                panel_content.append(f"  [red]- [{phase}/{entity}] {name}: {value}[/red]")
                if payload:
                    panel_content.append(f"    [dim]context: {payload}[/dim]")

        if data["final_state"]:
            eid, ts, src, phase, kind, entity, name, value, sev, payload, pid = data["final_state"][0]
            panel_content.append(f"\n[bold green]FINAL STATE:[/bold green] {name} = {value}")

        console.print(Panel("\n".join(panel_content), title="[bold]Event Inspector — Overview[/bold]", border_style="cyan"))

    def render_replay(self):
        """Replay inspection — walk events in order with rich formatting."""
        events = self.inspector.replay()

        table = Table(
            title=f"[bold]Replay — {len(events)} events[/bold]",
            box=box.ROUNDED,
            title_style="bold blue",
        )
        table.add_column("Time", style="dim", width=12)
        table.add_column("#", style="dim", width=4)
        table.add_column("Kind", width=10)
        table.add_column("Source/Phase/Entity", style="cyan", width=30)
        table.add_column("Detail", width=40)

        for eid, ts, src, phase, kind, entity, name, value, sev, payload, pid in events:
            ts_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]
            color = self.KIND_COLORS.get(kind, "white")
            icon = self.KIND_ICONS.get(kind, "?")
            location = f"{src}/{phase}/{entity}"
            detail = f"{name}={value}" if name else value
            if sev > 0:
                detail = f"[bold red]!{sev} {detail}[/bold red]"
            table.add_row(ts_str, str(eid), f"[{color}]{icon} {kind}[/{color}]", location, detail)

        console.print(table)

    def render_profile(self):
        """Profiler inspection — timing analysis with rich table."""
        data = self.inspector.profile()
        timings = data["timings"]

        if not timings:
            console.print(Panel("[yellow]No timing events recorded.[/yellow]", title="Profiler", border_style="yellow"))
            return

        table = Table(title="[bold]Timing Analysis[/bold]", box=box.ROUNDED, title_style="bold blue")
        table.add_column("#", style="dim", width=4)
        table.add_column("Phase/Entity", style="cyan", width=25)
        table.add_column("Duration", style="blue", width=12)

        for eid, ts, src, phase, kind, entity, name, value, sev, payload, pid in timings:
            table.add_row(str(eid), f"{phase}/{entity}", value)

        console.print(table)

        if data["analysis"]:
            a = data["analysis"]
            console.print(Panel(
                f"[blue]Total:[/blue] {a['total_ms']:.2f}ms\n"
                f"[red]Slowest:[/red] {a['slowest'][0]} at {a['slowest'][1]:.2f}ms\n"
                f"[green]Fastest:[/green] {a['fastest'][0]} at {a['fastest'][1]:.2f}ms\n"
                f"[yellow]Average:[/yellow] {a['average_ms']:.2f}ms",
                title="[bold]Analysis[/bold]",
                border_style="blue"
            ))

    def render_test_results(self, tester):
        """Renders ClassTester results — imports, each class/method, errors, state."""
        console.print()
        console.print(Panel(
            "[bold]CLASS TESTER — testing every class, method, import, and error[/bold]",
            border_style="bold yellow",
            title="[bold]TEST RESULTS[/bold]"
        ))

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
                imp_lines = []
                for imp in result.get("items", []):
                    imp_lines.append(f"  [green]✓[/green] [cyan]import[/cyan] {imp}")
                console.print(Panel(
                    "\n".join(imp_lines) or "  [dim](none)[/dim]",
                    title=f"[bold]{'green' if passed else 'red'}{icon} IMPORTS[/bold]",
                    border_style="green" if passed else "red",
                    padding=(0, 1)
                ))
                continue

            method_lines = []
            for t in result["tests"]:
                m_icon = "[green]✓[/green]" if t["passed"] else "[bold red]✗[/bold red]"
                method_lines.append(f"  {m_icon} [yellow]{t['method']}[/yellow]"
                                    f"  [dim]({t['fact_count']} facts, kinds: {', '.join(t['kinds'])})[/dim]")
                for check_name, check_passed, check_detail in t["checks"]:
                    c_icon = "[green]✓[/green]" if check_passed else "[bold red]✗[/bold red]"
                    method_lines.append(f"      {c_icon} [dim]{check_name}: {check_detail}[/dim]")
                method_lines.append("")

            border = "green" if passed else "red"
            console.print(Panel(
                "\n".join(method_lines),
                title=f"{icon} [bold]CLASS: {class_name}[/bold]  [dim]({result['detail']})[/dim]",
                border_style=border,
                padding=(0, 1)
            ))

        error_test = tester.test_errors()
        state_test = tester.test_state_consistency()

        err_icon = "[green]✓ PASS[/green]" if error_test["passed"] else "[bold red]✗ FAIL[/bold red]"
        state_icon = "[green]✓ PASS[/green]" if state_test["passed"] else "[bold red]✗ FAIL[/bold red]"

        err_lines = []
        err_lines.append(f"  {err_icon} [bold]Error Check[/bold] — {error_test['detail']}")
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

        console.print(Panel(
            "\n".join(err_lines),
            title="[bold]ERROR + STATE TESTS[/bold]",
            border_style="green" if error_test["passed"] and state_test["passed"] else "red",
            padding=(0, 1)
        ))

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
        """Debugger inspection — variables + state with rich formatting."""
        data = self.inspector.debug()
        variables = data["variables"]
        states = data["states"]

        var_table = Table(title=f"[bold]Variables ({len(variables)})[/bold]", box=box.ROUNDED, title_style="bold yellow")
        var_table.add_column("#", style="dim", width=4)
        var_table.add_column("Phase", style="magenta", width=14)
        var_table.add_column("Name", style="yellow", width=25)
        var_table.add_column("Value", width=30)

        for eid, ts, src, phase, kind, entity, name, value, sev, payload, pid in variables:
            var_table.add_row(str(eid), phase, name, value)

        console.print(var_table)

        state_table = Table(title=f"[bold]State ({len(states)})[/bold]", box=box.ROUNDED, title_style="bold magenta")
        state_table.add_column("#", style="dim", width=4)
        state_table.add_column("Name", style="magenta", width=20)
        state_table.add_column("Value", width=25)
        state_table.add_column("Source", style="cyan", width=12)

        for eid, ts, src, phase, kind, entity, name, value, sev, payload, pid in states:
            state_table.add_row(str(eid), name, value, src)

        console.print(state_table)


# ---- 4. Configurator (controls output configuration) ----

class Configurator:
    """The valve between execution and presentation.
    Controls what EventViewer is allowed to show.
    Classes never decide what gets shown — Configurator does."""

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


# ---- 5. ClassTester (tests each class/method against its facts) ----

class ClassTester:
    """Tests each class and method by querying LiveState facts.
    Checks: did the class produce facts? did it produce results? did it error?
    Did methods complete? did they have timing? did they have variables?
    Each test is a query — no special handling, everything is SQL."""

    def __init__(self, live_state, inspector):
        self.ls = live_state
        self.inspector = inspector

    def test_imports(self):
        facts = self.ls.query_kind("import")
        imports = [f[7] for f in facts]
        passed = len(imports) > 0
        return {
            "name": "imports",
            "passed": passed,
            "count": len(imports),
            "items": imports,
            "detail": f"{len(imports)} imports found" if passed else "NO imports found",
        }

    def test_class(self, class_name):
        facts = self.ls.query("source = ?", (class_name,))
        if not facts:
            return {"name": class_name, "passed": False, "tests": [], "detail": "NO facts produced by this class"}

        methods = {}
        for fid, ts, src, phase, kind, entity, name, value, sev, payload, pid in facts:
            if entity not in methods:
                methods[entity] = {"facts": 0, "errors": 0, "results": 0, "timing": None, "variables": 0, "kinds": set()}
            m = methods[entity]
            m["facts"] += 1
            m["kinds"].add(kind)
            if sev > 0:
                m["errors"] += 1
            if kind == "result":
                m["results"] += 1
            elif kind == "timing":
                m["timing"] = value
            elif kind == "variable":
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

            tests.append({
                "method": method_name,
                "passed": all(t for _, t, _ in method_tests),
                "checks": method_tests,
                "fact_count": m["facts"],
                "kinds": sorted(m["kinds"]),
            })

        class_errors = sum(1 for f in facts if f[8] > 0)
        if class_errors > 0:
            all_passed = False

        return {
            "name": class_name,
            "passed": all_passed,
            "tests": tests,
            "fact_count": len(facts),
            "error_count": class_errors,
            "method_count": len(methods),
            "detail": f"{len(facts)} facts, {len(methods)} methods, {class_errors} errors",
        }

    def test_all(self):
        results = []
        results.append(("imports", self.test_imports()))

        classes = set()
        all_facts = self.inspector.replay()
        for fid, ts, src, phase, kind, entity, name, value, sev, payload, pid in all_facts:
            if kind != "import":
                classes.add(src)

        for cls in sorted(classes):
            results.append((cls, self.test_class(cls)))

        return results

    def test_errors(self):
        errors = self.inspector.errors()
        return {
            "name": "error_check",
            "passed": len(errors) == 0,
            "count": len(errors),
            "items": [(e[2], e[4], e[6], e[7]) for e in errors],
            "detail": f"{len(errors)} errors found" if errors else "no errors",
        }

    def test_state_consistency(self):
        states = self.ls.query_kind("state")
        state_names = {}
        for fid, ts, src, phase, kind, entity, name, value, sev, payload, pid in states:
            if name not in state_names:
                state_names[name] = []
            state_names[name].append(value)

        conflicts = {}
        for name, values in state_names.items():
            unique = set(values)
            if len(unique) > 1:
                conflicts[name] = values

        return {
            "name": "state_consistency",
            "passed": len(conflicts) == 0,
            "conflicts": conflicts,
            "state_count": len(states),
            "detail": f"{len(conflicts)} conflicting states" if conflicts else f"{len(states)} states, all consistent",
        }


# ---- Test Trail: Simulated Bloodhound Scan writing to LiveState ----

def simulate_bloodhound_scan(live_state, target_dir):
    """Simulates a Bloodhound scan as class→method calls.
    Each emit uses source=class_name, entity=method_name.
    Structure: imports → LiveState → EventInspector → EventViewer → Configurator → Scanner → Nose."""

    # --- IMPORTS ---
    live_state.emit("main", "imports", "import", entity="imports", value="sqlite3")
    live_state.emit("main", "imports", "import", entity="imports", value="time")
    live_state.emit("main", "imports", "import", entity="imports", value="rich.console")
    live_state.emit("main", "imports", "import", entity="imports", value="rich.table")
    live_state.emit("main", "imports", "import", entity="imports", value="json")

    # --- CLASS: LiveState ---
    t0 = time.time()
    live_state.emit("LiveState", "init", "step", entity="__init__", name="status", value="creating SQLite :memory:")
    live_state.emit("LiveState", "init", "variable", entity="__init__", name="db_engine", value="sqlite3")
    live_state.emit("LiveState", "init", "variable", entity="__init__", name="mode", value=":memory:")
    time.sleep(0.005)
    live_state.emit("LiveState", "init", "result", entity="__init__", name="result", value="LiveState initialized")
    live_state.emit("LiveState", "init", "timing", entity="__init__", value=f"{(time.time() - t0) * 1000:.2f}ms")

    t0 = time.time()
    live_state.emit("LiveState", "init", "step", entity="_init_schema", name="status", value="creating event table")
    live_state.emit("LiveState", "init", "variable", entity="_init_schema", name="table", value="event")
    live_state.emit("LiveState", "init", "variable", entity="_init_schema", name="columns", value="11")
    live_state.emit("LiveState", "init", "variable", entity="_init_schema", name="indexes", value="4")
    time.sleep(0.003)
    live_state.emit("LiveState", "init", "result", entity="_init_schema", name="result", value="schema created")
    live_state.emit("LiveState", "init", "timing", entity="_init_schema", value=f"{(time.time() - t0) * 1000:.2f}ms")

    t0 = time.time()
    live_state.emit("LiveState", "init", "step", entity="on_emit", name="status", value="registering live callback")
    time.sleep(0.002)
    live_state.emit("LiveState", "init", "result", entity="on_emit", name="result", value="callback registered")
    live_state.emit("LiveState", "init", "timing", entity="on_emit", value=f"{(time.time() - t0) * 1000:.2f}ms")

    # --- CLASS: Configurator ---
    t0 = time.time()
    live_state.emit("Configurator", "config", "step", entity="__init__", name="status", value="setting verbosity=1")
    live_state.emit("Configurator", "config", "variable", entity="__init__", name="verbosity", value=1)
    live_state.emit("Configurator", "config", "variable", entity="__init__", name="show_errors", value=True)
    live_state.emit("Configurator", "config", "variable", entity="__init__", name="show_results", value=True)
    live_state.emit("Configurator", "config", "variable", entity="__init__", name="show_variables", value=False)
    time.sleep(0.002)
    live_state.emit("Configurator", "config", "result", entity="__init__", name="result", value="Configurator ready")
    live_state.emit("Configurator", "config", "timing", entity="__init__", value=f"{(time.time() - t0) * 1000:.2f}ms")

    # --- CLASS: EventInspector ---
    t0 = time.time()
    live_state.emit("EventInspector", "setup", "step", entity="__init__", name="status", value="connecting to LiveState")
    time.sleep(0.002)
    live_state.emit("EventInspector", "setup", "result", entity="__init__", name="result", value="inspector ready")
    live_state.emit("EventInspector", "setup", "timing", entity="__init__", value=f"{(time.time() - t0) * 1000:.2f}ms")

    # --- CLASS: EventViewer ---
    t0 = time.time()
    live_state.emit("EventViewer", "setup", "step", entity="__init__", name="status", value="binding inspector + config")
    time.sleep(0.002)
    live_state.emit("EventViewer", "setup", "result", entity="__init__", name="result", value="viewer ready")
    live_state.emit("EventViewer", "setup", "timing", entity="__init__", value=f"{(time.time() - t0) * 1000:.2f}ms")

    # --- CLASS: Scanner (the actual scan) ---
    live_state.emit("Scanner", "init", "state", entity="Run", name="scan_phase", value="starting")
    live_state.emit("Scanner", "init", "state", entity="Run", name="target_dir", value=target_dir)
    live_state.emit("Scanner", "init", "state", entity="Run", name="workspace", value="TestTrail")

    # Scanner.__init__
    t0 = time.time()
    live_state.emit("Scanner", "boot", "step", entity="__init__", name="status", value="opening LMDB")
    live_state.emit("Scanner", "boot", "variable", entity="__init__", name="db_path", value="~/.bloodhound/bloodhound.mdb")
    live_state.emit("Scanner", "boot", "variable", entity="__init__", name="map_size", value="1GB")
    time.sleep(0.005)
    live_state.emit("Scanner", "boot", "result", entity="__init__", name="result", value="LMDB opened")
    live_state.emit("Scanner", "boot", "timing", entity="__init__", value=f"{(time.time() - t0) * 1000:.2f}ms")

    # Scanner.walk_dir
    t0 = time.time()
    live_state.emit("Scanner", "scan", "step", entity="walk_dir", name="target", value=target_dir)

    file_count = 0
    scent_count = 0
    error_count = 0

    fake_files = [
        ("bh_main.c", "c", 207, 15),
        ("bh_db.c", "c", 1303, 120),
        ("bh_nose.c", "c", 855, 80),
        ("bh_query.c", "c", 311, 25),
        ("bloodhound.h", "c", 326, 30),
        ("Makefile", "makefile", 30, 0),
        ("README.md", "markdown", 141, 10),
    ]

    for fname, lang, lines, scents in fake_files:
        t1 = time.time()
        live_state.emit("Scanner", "scan", "step", entity="process_file", name="file", value=fname)
        live_state.emit("Scanner", "scan", "variable", entity="process_file", name=f"{fname}_language", value=lang)
        live_state.emit("Scanner", "scan", "variable", entity="process_file", name=f"{fname}_lines", value=lines)
        live_state.emit("Scanner", "scan", "variable", entity="process_file", name=f"{fname}_scents", value=scents)

        file_count += 1
        scent_count += scents

        if fname == "Makefile":
            live_state.emit("Scanner", "scan", "error", entity="extract_scents",
                     name="UNSUPPORTED_LANGUAGE",
                     value=f"Cannot extract scents from {lang} files",
                     severity=1,
                     payload={"file": fname, "language": lang})
            error_count += 1
            live_state.emit("Scanner", "scan", "result", entity="process_file",
                     name="result", value="skipped (unsupported)", severity=1)
        else:
            live_state.emit("Scanner", "scan", "result", entity="process_file",
                     name="result", value=f"extracted {scents} scents")

        time.sleep(0.003)
        live_state.emit("Scanner", "scan", "timing", entity="process_file",
                 value=f"{(time.time() - t1) * 1000:.2f}ms")

    live_state.emit("Scanner", "scan", "state", entity="walk_dir", name="file_count", value=file_count)
    live_state.emit("Scanner", "scan", "state", entity="walk_dir", name="scent_count", value=scent_count)
    live_state.emit("Scanner", "scan", "state", entity="walk_dir", name="error_count", value=error_count)
    live_state.emit("Scanner", "scan", "timing", entity="walk_dir",
             value=f"{(time.time() - t0) * 1000:.2f}ms")

    # --- CLASS: Nose (relationship builder) ---
    t0 = time.time()
    live_state.emit("Nose", "relationships", "step", entity="build_same_file",
             name="status", value="building same_file edges")
    rel_count = scent_count - 1
    live_state.emit("Nose", "relationships", "variable", entity="build_same_file", name="same_file_count", value=rel_count)
    time.sleep(0.005)
    live_state.emit("Nose", "relationships", "result", entity="build_same_file",
             name="result", value=f"{rel_count} same_file edges")
    live_state.emit("Nose", "relationships", "timing", entity="build_same_file",
             value=f"{(time.time() - t0) * 1000:.2f}ms")

    t0 = time.time()
    live_state.emit("Nose", "relationships", "step", entity="build_imports",
             name="status", value="building import edges")
    live_state.emit("Nose", "relationships", "variable", entity="build_imports", name="import_count", value=45)
    time.sleep(0.003)
    live_state.emit("Nose", "relationships", "result", entity="build_imports",
             name="result", value="45 import edges")
    live_state.emit("Nose", "relationships", "timing", entity="build_imports",
             value=f"{(time.time() - t0) * 1000:.2f}ms")

    t0 = time.time()
    live_state.emit("Nose", "relationships", "step", entity="build_calls",
             name="status", value="building call edges")
    live_state.emit("Nose", "relationships", "variable", entity="build_calls", name="call_count", value=30)
    time.sleep(0.003)
    live_state.emit("Nose", "relationships", "result", entity="build_calls",
             name="result", value="30 call edges")
    live_state.emit("Nose", "relationships", "timing", entity="build_calls",
             value=f"{(time.time() - t0) * 1000:.2f}ms")

    live_state.emit("Nose", "relationships", "state", entity="Run", name="relationship_count",
             value=rel_count + 45 + 30)

    # --- Scanner.finalize ---
    t0 = time.time()
    live_state.emit("Scanner", "finalize", "step", entity="log_observations", name="count", value=file_count)
    time.sleep(0.003)
    live_state.emit("Scanner", "finalize", "result", entity="log_observations",
             name="result", value="observations stored")
    live_state.emit("Scanner", "finalize", "timing", entity="log_observations",
             value=f"{(time.time() - t0) * 1000:.2f}ms")

    live_state.emit("Scanner", "finalize", "state", entity="Run", name="scan_phase", value="complete")
    live_state.emit("Scanner", "finalize", "result", entity="summary", name="files", value=file_count)
    live_state.emit("Scanner", "finalize", "result", entity="summary", name="scents", value=scent_count)
    live_state.emit("Scanner", "finalize", "result", entity="summary", name="relationships",
             value=rel_count + 45 + 30)
    live_state.emit("Scanner", "finalize", "result", entity="summary", name="errors", value=error_count)

    if error_count > 0:
        live_state.emit("Scanner", "finalize", "error", entity="check_errors",
                 name="HAS_ERRORS",
                 value=f"Scan completed with {error_count} errors",
                 severity=2,
                 payload="Check event table WHERE kind='error'")


# ---- Main ----

def main():
    args = sys.argv[1:]
    verbosity = 1
    mode_flag = None

    for a in args:
        if a.startswith("--"):
            mode_flag = a
        else:
            verbosity = int(a)

    ls = LiveState()
    inspector = EventInspector(ls)
    config = Configurator(verbosity)
    viewer = EventViewer(inspector, config)
    tester = ClassTester(ls, inspector)

    ls.on_emit(viewer.live_callback)

    console.print(Panel(
        f"[bold cyan]BLOODHOUND EXEC BUS v4[/bold cyan]\n"
        f"[dim]LiveState + EventInspector + EventViewer + Configurator + ClassTester[/dim]\n"
        f"[dim]Pattern: Class → LiveState.emit() → EventViewer.live_print() → final table[/dim]\n"
        f"[dim]Config: {config}[/dim]",
        border_style="cyan"
    ))

    if mode_flag != "--table":
        console.print(f"\n[bold green]▶ LIVE STREAM — events as they happen:[/bold green]\n")

    simulate_bloodhound_scan(ls, "core/Dom_Bloodhound/")

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

    ls.close()


if __name__ == "__main__":
    main()
