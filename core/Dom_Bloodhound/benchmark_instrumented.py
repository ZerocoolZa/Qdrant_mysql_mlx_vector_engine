#!/usr/bin/env python3
"""
benchmark_instrumented.py — MemUnit-instrumented ErrorAI benchmark.

Uses LiveState pattern from test_py_memunit_debugger.py:
  - Every trigger() and try_fix() emits timing events
  - Live streaming shows operations as they happen
  - Final report shows per-scenario, per-method timings
  - Identifies exactly which scenarios/operations are slow

Usage:
  python3 benchmark_instrumented.py             # 1000 runs, live streaming
  python3 benchmark_instrumented.py 10000       # 10K runs
  python3 benchmark_instrumented.py 100000      # 100K runs (no live stream, too much)
"""

import os, sys, time, io, json, sqlite3
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_error_ai_v3 import build_scenarios


# ---- LiveState (same pattern as test_py_memunit_debugger.py) ----

class LiveState:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
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
                payload TEXT
            );
            CREATE INDEX idx_event_kind ON event(kind);
            CREATE INDEX idx_event_source ON event(source);
        """)
        self.db.commit()
        self._callbacks = []

    def on_emit(self, callback):
        self._callbacks.append(callback)

    def emit(self, source, phase, kind, entity="", name="", value="", severity=0, payload=None):
        cur = self.db.execute(
            "INSERT INTO event (timestamp, source, phase, kind, entity, name, value, severity, payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (time.time(), source, phase, kind, entity, name, str(value), severity,
             json.dumps(payload) if payload else None)
        )
        self.db.commit()
        eid = cur.lastrowid
        for cb in self._callbacks:
            cb(eid, source, phase, kind, entity, name, str(value), severity)

    def query(self, where="1=1", params=()):
        return self.db.execute(
            "SELECT id, timestamp, source, phase, kind, entity, name, value, severity, payload FROM event WHERE "
            + where + " ORDER BY id", params
        ).fetchall()

    def count(self, where="1=1", params=()):
        return self.db.execute("SELECT COUNT(*) FROM event WHERE " + where, params).fetchone()[0]

    def count_kind(self, kind):
        return self.count("kind = ?", (kind,))

    def close(self):
        self.db.close()


# ---- Instrumented Scenario Runner ----

class InstrumentedRunner:
    """Wraps Scenario with LiveState event emission — same pattern as MemUnit debugger."""

    def __init__(self, scenario, live_state, verbosity=1):
        self.s = scenario
        self.ls = live_state
        self.verbosity = verbosity

    def trigger(self):
        self.ls.emit(self.s.name, "trigger", "step", "Scenario", "trigger", "starting")
        t0 = time.time()
        try:
            exec(self.s.broken_code, {})
            elapsed = (time.time() - t0) * 1000
            self.ls.emit(self.s.name, "trigger", "result", "Scenario", "trigger", "no_error", severity=1)
            self.ls.emit(self.s.name, "trigger", "timing", "Scenario", "trigger", f"{elapsed:.3f}ms")
            return False, None, "No error"
        except BaseException as e:
            elapsed = (time.time() - t0) * 1000
            etype = type(e).__name__
            matched = (etype == self.s.expected_error)
            self.ls.emit(self.s.name, "trigger", "result", "Scenario", "trigger",
                         f"error={etype} matched={matched}")
            self.ls.emit(self.s.name, "trigger", "timing", "Scenario", "trigger", f"{elapsed:.3f}ms")
            return True, etype, traceback.format_exc() if False else ""

    def try_fix(self, fname, fcode):
        self.ls.emit(self.s.name, "fix", "step", "Scenario", f"try_fix:{fname}", "starting")
        t0 = time.time()
        try:
            ns = {}
            exec(fcode, ns)
        except BaseException as e:
            elapsed = (time.time() - t0) * 1000
            self.ls.emit(self.s.name, "fix", "result", "Scenario", f"try_fix:{fname}",
                         f"fix_raised={type(e).__name__}", severity=1)
            self.ls.emit(self.s.name, "fix", "timing", "Scenario", f"try_fix:{fname}", f"{elapsed:.3f}ms")
            return False, False, f"fix raised {type(e).__name__}"
        try:
            correct = self.s.result_checker(ns)
        except BaseException as e:
            elapsed = (time.time() - t0) * 1000
            self.ls.emit(self.s.name, "fix", "result", "Scenario", f"try_fix:{fname}",
                         f"checker_raised={type(e).__name__}", severity=1)
            self.ls.emit(self.s.name, "fix", "timing", "Scenario", f"try_fix:{fname}", f"{elapsed:.3f}ms")
            return True, False, f"checker raised {type(e).__name__}"
        elapsed = (time.time() - t0) * 1000
        self.ls.emit(self.s.name, "fix", "result", "Scenario", f"try_fix:{fname}",
                     f"correct={correct}")
        self.ls.emit(self.s.name, "fix", "timing", "Scenario", f"try_fix:{fname}", f"{elapsed:.3f}ms")
        return True, correct, "ok" if correct else "result wrong"

    def encounter(self):
        triggered, actual, _ = self.trigger()
        if not triggered:
            return "not_triggered"
        matched = (actual == self.s.expected_error)
        working = []
        failing = []
        for fname, fcode in self.s.fix_candidates:
            ok, correct, _ = self.try_fix(fname, fcode)
            if ok and correct:
                working.append(fname)
            else:
                failing.append(fname)
        if working:
            return f"fixed:{working[0]}"
        return "no_fix"


# ---- Live Viewer (same pattern as EventViewer) ----

KIND_ICONS = {"step": "▶", "result": "✓", "error": "✗", "timing": "T"}
KIND_COLORS = {"step": "cyan", "result": "green", "error": "bold red", "timing": "blue"}


def live_callback(eid, source, phase, kind, entity, name, value, severity):
    color = KIND_COLORS.get(kind, "white")
    icon = KIND_ICONS.get(kind, "?")
    ts_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    if severity > 0:
        console.print(f"  [dim]{ts_str}[/dim] [{color}]{icon} #{eid:4d}[/{color}] [bold red]!{severity}[/bold red] [{color}]{source}/{phase}/{entity}[/] {name}={value}")
    else:
        console.print(f"  [dim]{ts_str}[/dim] [{color}]{icon} #{eid:4d}[/{color}] [{color}]{source}/{phase}/{entity}[/] {name}={value}")


def main():
    import traceback

    TOTAL_RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    LIVE_STREAM = TOTAL_RUNS <= 5000

    console.print(Panel(
        f"[bold]ErrorAI v3 — Instrumented Benchmark[/bold]\n"
        f"MemUnit pattern: LiveState + EventViewer + timing per operation\n"
        f"Runs: {TOTAL_RUNS:,} | Live stream: {LIVE_STREAM}",
        title="Instrumented Benchmark", border_style="cyan"
    ))

    scenarios = build_scenarios()
    n = len(scenarios)
    console.print(f"Scenarios: {n}\n")

    ls = LiveState()
    if LIVE_STREAM:
        ls.on_emit(live_callback)
        console.print("[bold cyan]▶ LIVE STREAM — events as they happen:[/bold cyan]\n")

    # Run instrumented encounters
    start = time.time()
    for run_num in range(1, TOTAL_RUNS + 1):
        for s in scenarios:
            runner = InstrumentedRunner(s, ls, verbosity=1)
            runner.encounter()

        if not LIVE_STREAM and run_num % max(1, TOTAL_RUNS // 10) == 0:
            elapsed = time.time() - start
            pct = run_num / TOTAL_RUNS * 100
            rate = run_num / elapsed
            eta = (TOTAL_RUNS - run_num) / rate
            console.print(f"  [dim]{pct:5.1f}%[/dim] run {run_num:>6,}/{TOTAL_RUNS:,} | {elapsed:.1f}s | {rate:,.0f} runs/s | ETA {eta:.0f}s | events={ls.count():,}")

    elapsed = time.time() - start

    # ---- Final Report ----
    console.print()
    console.print(Panel(f"[bold green]DONE[/bold green] — {TOTAL_RUNS:,} runs in {elapsed:.1f}s ({TOTAL_RUNS*n/elapsed:,.0f} encounters/s)", border_style="green"))

    # Summary counts
    s_total = ls.count()
    s_steps = ls.count_kind("step")
    s_results = ls.count_kind("result")
    s_timings = ls.count_kind("timing")
    s_errors = ls.count("severity > 0")

    summary_table = Table(box=box.SIMPLE, show_header=False, title="[bold]Event Summary[/bold]")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Count", style="bold")
    summary_table.add_row("Total Events", f"{s_total:,}")
    summary_table.add_row("Steps", f"{s_steps:,}")
    summary_table.add_row("Results", f"{s_results:,}")
    summary_table.add_row("Timings", f"{s_timings:,}")
    summary_table.add_row("[bold red]Errors[/bold red]", f"[bold red]{s_errors:,}[/bold red]")
    console.print(summary_table)

    # Per-scenario timing breakdown
    console.print()
    timing_table = Table(
        title="[bold]Per-Scenario Timing[/bold]  [dim](avg ms per operation)[/dim]",
        box=box.ROUNDED, show_lines=True
    )
    timing_table.add_column("Scenario", style="cyan", width=22)
    timing_table.add_column("trigger ms", justify="right", width=12)
    timing_table.add_column("fix ms", justify="right", width=12)
    timing_table.add_column("encounter ms", justify="right", width=14)
    timing_table.add_column("calls", justify="right", width=8)
    timing_table.add_column("est 100K", justify="right", width=12)

    for s in scenarios:
        # Query timings for this scenario
        trig_times = []
        fix_times = []
        for eid, ts, src, phase, kind, entity, name, value, sev, payload in ls.query("source = ? AND kind = ? AND phase = ?", (s.name, "timing", "trigger")):
            try:
                ms = float(value.replace("ms", ""))
                trig_times.append(ms)
            except:
                pass
        for eid, ts, src, phase, kind, entity, name, value, sev, payload in ls.query("source = ? AND kind = ? AND phase = ?", (s.name, "timing", "fix")):
            try:
                ms = float(value.replace("ms", ""))
                fix_times.append(ms)
            except:
                pass

        avg_trig = sum(trig_times) / max(1, len(trig_times))
        avg_fix = sum(fix_times) / max(1, len(fix_times))
        # encounter = 1 trigger + 5 fix attempts (worst case)
        avg_enc = avg_trig + avg_fix * len(s.fix_candidates)
        calls = len(trig_times) + len(fix_times)
        est_100k = avg_enc * 100000 / 1000

        flag = " [bold red]SLOW[/bold red]" if est_100k > 60 else ""
        timing_table.add_row(
            s.name,
            f"{avg_trig:.3f}",
            f"{avg_fix:.3f}",
            f"{avg_enc:.3f}",
            f"{calls:,}",
            f"{est_100k:.1f}s{flag}"
        )

    console.print(timing_table)

    # Slowest operations
    console.print()
    all_timings = []
    for eid, ts, src, phase, kind, entity, name, value, sev, payload in ls.query("kind = 'timing'"):
        try:
            ms = float(value.replace("ms", ""))
            all_timings.append((f"{src}/{phase}/{entity}", ms))
        except:
            pass

    if all_timings:
        all_timings.sort(key=lambda x: -x[1])
        slow_table = Table(title="[bold red]Top 20 Slowest Operations[/bold red]", box=box.SIMPLE)
        slow_table.add_column("#", style="dim", width=4)
        slow_table.add_column("Operation", style="cyan", width=40)
        slow_table.add_column("ms", justify="right", style="bold red", width=10)
        for i, (op, ms) in enumerate(all_timings[:20]):
            slow_table.add_row(str(i+1), op, f"{ms:.3f}")
        console.print(slow_table)

        avg_ms = sum(m for _, m in all_timings) / len(all_timings)
        console.print(f"\n  [dim]Average operation: {avg_ms:.3f}ms | Total operations: {len(all_timings):,}[/dim]")

    ls.close()


if __name__ == "__main__":
    main()
